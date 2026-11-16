#!/usr/bin/env python3
"""Build the diskless VM that runs the droidB-sideload / droidB-gms regression cases.

Nothing is executed on the host except copying files and ldd. The VM has no network, disks or
USB: adb is tests/fake-adb.py. Real Termux:Boot and Termux:API APKs (F-Droid builds, from
ARXOS/vendor/termux-fdroid) feed the real aapt2. Run:

    python3 tests/build-sideload-initramfs.py OUT
    qemu-system-x86_64 -enable-kvm -m 2048 -smp 2 -kernel /boot/vmlinuz-linux \\
      -initrd OUT/test-initramfs.cpio -append 'console=ttyS0 rdinit=/init panic=-1' \\
      -nographic -no-reboot -nic none
"""
import argparse, pathlib, re, shutil, subprocess, sys, sysconfig

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("output", type=pathlib.Path)
args = ap.parse_args()
base = args.output.resolve()
base.mkdir(parents=True, exist_ok=True)
r = base / "rootfs"
if r.exists():
    shutil.rmtree(r)
r.mkdir()
repo = pathlib.Path(__file__).resolve().parent.parent
vendor = repo.parent.parent / "vendor" / "termux-fdroid"
seen = set()


def add(src, dst=None):
    src = pathlib.Path(src)
    dest = r / str(dst or src).lstrip("/")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    dest.chmod(src.stat().st_mode & 0o777)
    if str(src) in seen:
        return
    seen.add(str(src))
    out = subprocess.run(["ldd", str(src)], capture_output=True, text=True).stdout
    for line in out.splitlines():
        m = re.search(r"=> (/\S+)", line) or re.match(r"\s*(/\S+)", line)
        if m:
            add(m.group(1))


for d in ["dev", "proc", "sys", "tmp", "test/bin", "test/fixtures", "test/apks", "usr/bin", "lib64", "opt/aapt2"]:
    (r / d).mkdir(parents=True, exist_ok=True)
for name in ["bash", "mount", "poweroff", "python3", "env"]:   # env: the tools start with #!/usr/bin/env
    add(shutil.which(name), "/usr/bin/" + name)
add("/bin/bash", "/bin/sh")
add("/lib64/ld-linux-x86-64.so.2")
add("/usr/lib/7zip/7z", "/usr/lib/7zip/7z")
add("/usr/lib/7zip/7z.so", "/usr/lib/7zip/7z.so")      # 7z loads its codecs from here at run time (not in ldd)
(r / "usr/bin/7z").write_text('#!/bin/sh\nexec /usr/lib/7zip/7z "$@"\n')
(r / "usr/bin/7z").chmod(0o755)
add(pathlib.Path("/opt/android-sdk/build-tools/36.1.0/aapt2").resolve(), "/opt/aapt2/aapt2")

# the Python standard library (no site-packages: the tools use the standard library only)
stdlib = pathlib.Path(sysconfig.get_paths()["stdlib"])
skip = {"site-packages", "test", "idlelib", "tkinter", "turtledemo", "ensurepip", "__pycache__"}
for p in stdlib.rglob("*"):
    rel = p.relative_to(stdlib)
    if p.is_file() and not (set(rel.parts) & skip):
        if p.suffix == ".so":
            add(p)
        else:
            dest = r / str(p).lstrip("/")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dest)

for tool in ["droidB-sideload", "droidB-gms"]:
    shutil.copyfile(repo / tool, r / "test/bin" / tool)
    (r / "test/bin" / tool).chmod(0o755)
for fixture, name in [("fake-adb.py", "adb"), ("fake-aapt2.py", "aapt2")]:
    shutil.copyfile(repo / "tests" / fixture, r / "test/fixtures" / name)
    (r / "test/fixtures" / name).chmod(0o755)
shutil.copyfile(repo / "tests/sideload_cases.py", r / "test/sideload_cases.py")
for apk in ["com.termux.boot_1000.apk", "com.termux.api_1002.apk"]:
    shutil.copyfile(vendor / apk, r / "test/apks" / apk)

(r / "init").write_text("""#!/bin/sh
export PATH=/usr/bin:/bin
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
mount -t tmpfs tmpfs /tmp
python3 /test/sideload_cases.py
echo "DROIDB_SIDELOAD_RESULT rc=$?"
poweroff -f -f
""")
(r / "init").chmod(0o755)
with (base / "test-initramfs.cpio").open("wb") as f:
    p = subprocess.run(["bash", "-c", "find . -print0 | cpio --null -o --format=newc"], cwd=r, stdout=f, stderr=subprocess.PIPE)
    p.check_returncode()
print("VM initramfs built:", base / "test-initramfs.cpio")
