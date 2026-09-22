#!/usr/bin/env python3
"""Build a diskless regression VM image from host-built droidB binaries.

Does not execute droidB or attach host disks, networking, or USB devices.
"""
import argparse
import json
import pathlib,shutil,subprocess,re,os
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output', type=pathlib.Path)
args = parser.parse_args()
base=args.output.resolve(); base.mkdir(parents=True, exist_ok=True)
r=base/'rootfs';r.mkdir()
repo=pathlib.Path(__file__).resolve().parent.parent
for d in ['dev','proc','sys','tmp','test','bin','usr/bin','lib64']: (r/d).mkdir(exist_ok=True,parents=True)
seen=set()
def add(src,dst=None):
 src=pathlib.Path(src);dest=r/str(dst or src).lstrip('/')
 dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest);dest.chmod(src.stat().st_mode & 0o777)
 key=str(src)
 if key in seen:return
 seen.add(key)
 p=subprocess.run(['ldd',str(src)],capture_output=True,text=True)
 for line in p.stdout.splitlines():
  m=re.search(r'=> (/\S+)',line) or re.match(r'\s*(/\S+)',line)
  if m:add(m.group(1))
for name in ['bash','mount','cat','mkdir','chmod','grep','poweroff','node']:
 add(shutil.which(name),'/usr/bin/'+name)
add('/bin/bash','/bin/sh')
add('/lib64/ld-linux-x86-64.so.2','/lib64/ld-linux-x86-64.so.2')
add(repo/'target/debug/droidB-native','/test/droidb-cli')
build = subprocess.run(
    ['cargo', 'test', '-p', 'droidB', '--bin', 'droidB-native', '--no-run', '--locked', '--message-format=json'],
    cwd=repo, capture_output=True, text=True)
if build.returncode:
    raise SystemExit(build.stderr + build.stdout)
artifacts = [json.loads(line) for line in build.stdout.splitlines() if line.startswith('{')]
units = [a['executable'] for a in artifacts if a.get('reason') == 'compiler-artifact'
         and a.get('profile', {}).get('test') and a.get('executable')]
if len(units) != 1: raise SystemExit('Expected exactly one unit test executable from Cargo')
add(units[0], '/test/unit')
shutil.copyfile(repo/'tests/mvt-vm.sh',r/'test/mvt-vm.sh')
shutil.copyfile(repo/'tests/mvt-log.js',r/'test/mvt-log.js')
shutil.copyfile(repo/'ui/app.js',r/'test/app.js')
(r/'init').write_text('''#!/bin/sh
export PATH=/usr/bin:/bin
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
/test/unit mvt::tests --test-threads=1
unit_rc=$?
/test/unit clean::tests --test-threads=1
clean_rc=$?
/bin/sh /test/mvt-vm.sh
cli_rc=$?
node /test/mvt-log.js
log_rc=$?
echo "DROIDB_TEST_RESULT unit=$unit_rc clean=$clean_rc cli=$cli_rc log=$log_rc"
poweroff -f -f
''');(r/'init').chmod(0o755)
with (base/'test-initramfs.cpio').open('wb') as f:
 p=subprocess.run(['bash','-c','find . -print0 | cpio --null -o --format=newc'],cwd=r,stdout=f,stderr=subprocess.PIPE)
 p.check_returncode()
print('VM initramfs built')
