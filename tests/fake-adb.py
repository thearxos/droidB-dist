#!/usr/bin/python3
"""A scripted phone for the sideload and Google-services tests (runs only inside the test VM).

State comes from $FAKE_ADB_STATE (JSON); every call is appended to $FAKE_ADB_LOG as one JSON line.
A command this fixture does not know exits 99 and is logged as UNEXPECTED, so a test can never pass
because an unknown call silently "worked".
"""
import json, os, shlex, shutil, sys

state = json.load(open(os.environ["FAKE_ADB_STATE"]))
log = open(os.environ["FAKE_ADB_LOG"], "a")
args = sys.argv[1:]


def record(kind, **kw):
    log.write(json.dumps({"kind": kind, "args": args, **kw}) + "\n")
    log.flush()


def done(text="", rc=0):
    if text:
        print(text)
    sys.exit(rc)


def unexpected():
    record("UNEXPECTED")
    sys.stderr.write("fake-adb: unexpected call %r\n" % args)   # stderr: never mistaken for phone output
    sys.exit(99)


def local(remote):
    """Map a phone path under /sdcard to the fixture's storage folder."""
    if not remote.startswith("/sdcard/"):
        unexpected()
    return os.path.join(state["sdcard"], remote[len("/sdcard/"):])


def save():
    json.dump(state, open(os.environ["FAKE_ADB_STATE"], "w"))


if args == ["devices"]:
    record("devices")
    done("List of devices attached\n" + "".join("%s\t%s\n" % (s, st) for s, st in state["devices"]))
if args and args[0] != "-s":
    # the GUI calls adb without -s: adb then uses $ANDROID_SERIAL, or the only phone
    ready = [s for s, st in state["devices"] if st == "device"]
    first = os.environ.get("ANDROID_SERIAL") or (ready[0] if len(ready) == 1 else None)
    if args == ["get-state"]:
        record("get-state")
        done("device" if first else "error: no devices/emulators found", 0 if first else 1)
    if not first:
        unexpected()
    args = ["-s", first] + args
if len(args) < 3 or args[0] != "-s":
    unexpected()
serial, cmd, rest = args[1], args[2], args[3:]
if serial not in [s for s, st in state["devices"] if st == "device"]:
    record("bad-serial")
    done("adb: device '%s' not found" % serial, 1)

pk = state.setdefault("packages", {})

if cmd in ("install", "install-multiple"):
    flags = [a for a in rest if a.startswith("-")]
    files = [a for a in rest if not a.startswith("-")]
    record(cmd, flags=flags, files=[os.path.basename(f) for f in files])
    for rule in state.get("install_rules", []):
        if rule["unless"] not in flags:
            done("Failure [%s: fixture]" % rule["code"], 1)
    if state.get("fail_code"):
        done("Failure [%s: fixture]" % state["fail_code"], 1)
    done("Performing Streamed Install\nSuccess")

if cmd == "push":
    src, dst = rest
    record("push", src=os.path.basename(src), dst=dst)
    target = local(dst)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if state.get("short_push"):
        with open(src, "rb") as f, open(target, "wb") as g:
            g.write(f.read()[:-1])
    else:
        shutil.copyfile(src, target)
    done("%s: 1 file pushed." % src)

if cmd != "shell" or not rest:
    unexpected()
argv = shlex.split(" ".join(rest))   # adb joins its arguments with spaces for the phone's shell
record("shell", argv=argv)

if argv[:1] == ["getprop"] and len(argv) == 2:
    done(state["props"].get(argv[1], ""))
if argv[:2] == ["mkdir", "-p"] and len(argv) == 3:
    os.makedirs(local(argv[2]), exist_ok=True)
    done()
if argv[:3] == ["stat", "-c", "%s"] and len(argv) == 4:
    p = local(argv[3])
    done(str(os.path.getsize(p)) if os.path.exists(p) else "stat: No such file", 0 if os.path.exists(p) else 1)
if argv[:3] == ["pm", "list", "packages"]:
    flags = argv[3:]
    out = []
    for name, p in sorted(pk.items()):
        if "-s" in flags and not p.get("system"):
            continue
        if "-3" in flags and p.get("system"):
            continue
        if "-d" in flags and not p.get("disabled"):
            continue
        if "--user" in flags and not p.get("user0"):
            continue
        if "-u" not in flags and "--user" not in flags and not p.get("user0"):
            continue
        out.append("package:" + name)
    done("\n".join(out))
if argv == ["pm", "list", "permissions"]:
    done("All Permissions:\n\n" + "".join("permission:%s\n" % p for p in state.get("perms", [])))
if argv[:2] == ["dumpsys", "package"] and len(argv) == 3:
    p = pk.get(argv[2])
    done(p.get("dumpsys", "Packages:\n  Package [%s]\n    versionCode=1 minSdk=21\n    versionName=1.0\n" % argv[2]) if p else "")
if argv == ["dumpsys", "deviceidle", "whitelist"]:
    done("".join("user,%s,10%03d\n" % (p, n) for n, p in enumerate(state.get("idle", []))))
if argv[:5] == ["cmd", "package", "install-existing", "--user", "0"] and len(argv) == 6:
    p = pk.get(argv[5])
    if not p or not p.get("system"):
        done("Package %s doesn't exist" % argv[5], 1)
    p["user0"] = True
    save()
    done("Package %s installed for user: 0" % argv[5])
if argv[:4] == ["pm", "enable", "--user", "0"] and len(argv) == 5:
    if argv[4] in pk:
        pk[argv[4]]["disabled"] = False
        save()
    done("Package %s new state: enabled" % argv[4])
if argv[:3] == ["cmd", "deviceidle", "whitelist"] and len(argv) == 4 and argv[3].startswith("+"):
    state.setdefault("idle", []).append(argv[3][1:])
    save()
    done("Added: %s" % argv[3][1:])
if argv[:2] == ["am", "start"]:
    done("Starting: Intent { act=%s }" % argv[3])
unexpected()
