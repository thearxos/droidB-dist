#!/usr/bin/python3
"""droidB-sideload and droidB-gms regression cases. Run ONLY in the diskless test VM
(tests/build-sideload-initramfs.py): adb and the phone are the fixture in tests/fake-adb.py.

Real APKs (Termux:Boot, Termux:API, F-Droid builds) exercise the real aapt2. Bundles, OBBs and
hostile archives are made here. Prints SIDELOAD_CASES pass=N fail=M and exits non-zero on a failure.
"""
import json, os, shutil, subprocess, sys, zipfile

T = "/tmp/cases"
BIN = "/test/bin"
BOOT, API = "/test/apks/com.termux.boot_1000.apk", "/test/apks/com.termux.api_1002.apk"
passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print("  PASS %s" % name)
    else:
        failed += 1
        print("  FAIL %s %s" % (name, detail))


def phone(**over):
    """A fresh scripted phone: one device, Android 14, arm64 + x86_64."""
    st = {"devices": [["SER1", "device"]], "sdcard": T + "/sdcard",
          "props": {"ro.build.version.sdk": "34", "ro.product.cpu.abilist": "arm64-v8a,x86_64", "ro.product.cpu.abi": "arm64-v8a",
                    "ro.product.model": "Fixture", "ro.product.manufacturer": "droidB", "ro.build.version.release": "14"},
          "packages": {}, "perms": [], "idle": []}
    st.update(over)
    shutil.rmtree(T + "/sdcard", ignore_errors=True)
    json.dump(st, open(T + "/state.json", "w"))
    open(T + "/adb.log", "w").close()


def calls(kind=None):
    out = [json.loads(l) for l in open(T + "/adb.log") if l.strip()]
    return [c for c in out if kind is None or c["kind"] == kind]


def run(tool, *args):
    r = subprocess.run([BIN + "/" + tool, *args, "--json"] if "--json" not in args else [BIN + "/" + tool, *args],
                       capture_output=True, text=True, env=ENV)
    try:
        out = json.loads(r.stdout)
    except ValueError:
        out = {"_raw": r.stdout + r.stderr}
    return r.returncode, out


def make_zip(path, entries, links=()):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in entries:
            z.writestr(name, open(data, "rb").read() if isinstance(data, str) and os.path.exists(data) else data)
        for name in links:
            info = zipfile.ZipInfo(name)
            info.external_attr = (0o120777 << 16)
            z.writestr(info, "/etc/passwd")
    return path


def blob(size, seed):
    return bytes((i * 31 + seed) & 0xFF for i in range(size))


os.makedirs(T, exist_ok=True)
ENV = dict(os.environ, PATH="/test/fixtures:/usr/bin:/bin", FAKE_ADB_STATE=T + "/state.json", FAKE_ADB_LOG=T + "/adb.log",
           FAKE_AAPT_BADGING=T + "/badging.json", HOME=T + "/home", XDG_CACHE_HOME=T + "/cache", XDG_DATA_HOME=T + "/data")
json.dump({
    "gmscore-fake.apk": "package: name='com.google.android.gms' versionCode='240000' versionName='0.3.6.244735'\nminSdkVersion:'21'\ntargetSdkVersion:'31'",
    "gsfproxy-fake.apk": "package: name='com.google.android.gsf' versionCode='8' versionName='v0.1.0'\nminSdkVersion:'9'\ntargetSdkVersion:'19'",
    "abi-arm.apk": "package: name='org.fixture.native' versionCode='5' versionName='5'\nminSdkVersion:'21'\ntargetSdkVersion:'33'\nnative-code: 'armeabi-v7a'",
}, open(T + "/badging.json", "w"))
for n in ("gmscore-fake.apk", "gsfproxy-fake.apk", "abi-arm.apk"):
    shutil.copyfile(BOOT, T + "/" + n)

print("== sideload ==")
phone()
rc, r = run("droidB-sideload", "inspect", BOOT)
check("inspect real APK", rc == 0 and r["kind"] == "apk" and r["package"] == "com.termux.boot" and r["version_code"] == "1000"
      and r["apks"][0]["min_sdk"] == 21 and r["apks"][0]["target_sdk"] == 28 and r["checksum"]["state"] == "none", r)

spaced = T + "/my games/boot.apk"
os.makedirs(os.path.dirname(spaced), exist_ok=True)
shutil.copyfile(BOOT, spaced)
rc, r = run("droidB-sideload", "inspect", "'%s'" % spaced)
check("pasted path with quotes and a space", rc == 0 and r["package"] == "com.termux.boot", r)

good = T + "/sum/boot.apk"
os.makedirs(T + "/sum", exist_ok=True)
shutil.copyfile(BOOT, good)
open(good + ".sha256", "w").write(r["sha256"] + "  boot.apk\n")
rc, r = run("droidB-sideload", "inspect", good)
check("checksum file matches", r.get("checksum", {}).get("state") == "match", r)
open(good + ".sha256", "w").write("0" * 64 + "\n")
phone()
rc, r = run("droidB-sideload", "install", good)
check("checksum mismatch stops before the phone", rc == 1 and "CHECKSUM MISMATCH" in r.get("error", "") and not calls("install"), r)

phone()
rc, r = run("droidB-sideload", "install", BOOT)
check("install single APK", rc == 0 and r["package"] == "com.termux.boot" and calls("install")[0]["flags"] == ["-r"], r)

obb = blob(3 * 1024 * 1024 + 17, 7)
xapk = make_zip(T + "/game.xapk", [
    ("manifest.json", json.dumps({"package_name": "com.termux.boot", "expansions": [
        {"file": "Android/obb/com.termux.boot/main.1000.com.termux.boot.obb", "install_location": "EXTERNAL_STORAGE",
         "install_path": "Android/obb/com.termux.boot/main.1000.com.termux.boot.obb"}]})),
    ("com.termux.boot.apk", BOOT), ("Android/obb/com.termux.boot/main.1000.com.termux.boot.obb", obb)])
phone()
rc, r = run("droidB-sideload", "install", xapk)
dest = T + "/sdcard/Android/obb/com.termux.boot/main.1000.com.termux.boot.obb"
check("XAPK: APK installed, OBB pushed under its own name and size-checked",
      rc == 0 and r["obbs"] and r["obbs"][0]["verified"] and os.path.getsize(dest) == len(obb)
      and r["obbs"][0]["remote"] == "/sdcard/Android/obb/com.termux.boot/main.1000.com.termux.boot.obb", r)

apks = make_zip(T + "/split.apks", [("base.apk", BOOT), ("split_config.x86_64.apk", BOOT), ("toc.pb", b"x")])
phone()
rc, r = run("droidB-sideload", "install", apks)
im = calls("install-multiple")
check("APKS split set goes in one install-multiple", rc == 0 and im and len(im[0]["files"]) == 2, r)

mixed = make_zip(T + "/mixed.apkm", [("base.apk", BOOT), ("other.apk", API)])
phone()
rc, r = run("droidB-sideload", "install", mixed)
check("set of two different apps refused", rc == 1 and "different apps" in r.get("error", "") and not calls("install-multiple"), r)

evil = make_zip(T + "/evil.zip", [("../../evil.apk", BOOT)])
rc, r = run("droidB-sideload", "install", evil)
check("path traversal refused", rc == 1 and "unsafe path" in r.get("error", ""), r)
linky = make_zip(T + "/link.xapk", [("a.txt", b"x")], links=["data.obb"])
rc, r = run("droidB-sideload", "install", linky, "--obb", linky)
check("link in archive refused", rc == 1 and ("link" in r.get("error", "") or "No OBB" in r.get("error", "")), r)

aab = make_zip(T + "/app.aab", [("BundleConfig.pb", b"x"), ("base/manifest/AndroidManifest.xml", b"x")])
rc, r = run("droidB-sideload", "install", aab)
check("AAB reported, not installed", rc == 1 and "App Bundle" in r.get("error", ""), r)

os.makedirs(T + "/7z", exist_ok=True)
shutil.copyfile(BOOT, T + "/7z/boot.apk")
open(T + "/7z/main.1000.com.termux.boot.obb", "wb").write(blob(70000, 3))
made = subprocess.run(["7z", "a", "-bd", T + "/game.7z", T + "/7z/boot.apk", T + "/7z/main.1000.com.termux.boot.obb"], capture_output=True, text=True)
check("7z test archive made", made.returncode == 0, made.stdout + made.stderr)
phone()
rc, r = run("droidB-sideload", "install", T + "/game.7z")
check("7z bundle: APK + OBB", rc == 0 and len(r["obbs"]) == 1 and calls("install"), r)

wrong = T + "/main.999.com.other.game.obb"
open(wrong, "wb").write(blob(5000, 9))
phone()
rc, r = run("droidB-sideload", "install", BOOT, "--obb", wrong)
check("OBB for another app asks first, installs nothing", rc == 3 and r["need"] == "obb_mismatch" and not calls("install"), r)
rc, r = run("droidB-sideload", "install", BOOT, "--obb", wrong, "--allow-obb-mismatch")
check("with consent: pushed to the app's own folder", rc == 0 and os.path.exists(T + "/sdcard/Android/obb/com.termux.boot/main.999.com.other.game.obb"), r)

phone(install_rules=[{"unless": "-d", "code": "INSTALL_FAILED_VERSION_DOWNGRADE"}])
rc, r = run("droidB-sideload", "install", BOOT)
check("downgrade needs consent", rc == 3 and r["need"] == "downgrade", r)
rc, r = run("droidB-sideload", "install", BOOT, "--allow-downgrade")
check("downgrade with consent uses -d", rc == 0 and "-d" in calls("install")[-1]["flags"], r)

phone(install_rules=[{"unless": "--bypass-low-target-sdk-block", "code": "INSTALL_FAILED_DEPRECATED_SDK_VERSION"}])
rc, r = run("droidB-sideload", "install", BOOT)
check("old target SDK needs consent", rc == 3 and r["need"] == "old_target", r)
rc, r = run("droidB-sideload", "install", BOOT, "--allow-old-target")
check("old target with consent lifts the block", rc == 0 and "--bypass-low-target-sdk-block" in calls("install")[-1]["flags"], r)

phone(fail_code="INSTALL_FAILED_UPDATE_INCOMPATIBLE")
rc, r = run("droidB-sideload", "install", BOOT)
check("other signer explained", rc == 1 and "signed by someone else" in r.get("error", ""), r)

phone(props={"ro.build.version.sdk": "34", "ro.product.cpu.abilist": "x86_64", "ro.product.cpu.abi": "x86_64"})
rc, r = run("droidB-sideload", "install", T + "/abi-arm.apk")
check("wrong processor refused before installing", rc == 1 and "armeabi-v7a" in r.get("error", "") and not calls("install"), r)

phone(props={"ro.build.version.sdk": "19", "ro.product.cpu.abilist": "arm64-v8a"})
rc, r = run("droidB-sideload", "install", BOOT)
check("too old Android refused", rc == 1 and "needs Android SDK 21" in r.get("error", "") and not calls("install"), r)

phone(devices=[["SER1", "device"], ["SER2", "device"]])
rc, r = run("droidB-sideload", "install", BOOT)
check("two phones: asks which", rc == 3 and r["need"] == "device" and r["devices"] == ["SER1", "SER2"], r)
rc, r = run("droidB-sideload", "install", BOOT, "--serial", "SER1")
check("chosen phone used", rc == 0, r)
phone(devices=[])
rc, r = run("droidB-sideload", "install", BOOT)
check("no phone", rc == 1 and "No phone connected" in r.get("error", ""), r)
phone(devices=[["SER1", "unauthorized"]])
rc, r = run("droidB-sideload", "install", BOOT)
check("unauthorized phone", rc == 1 and "Allow USB debugging" in r.get("error", ""), r)

phone(short_push=True)
rc, r = run("droidB-sideload", "install", xapk)
check("short OBB copy detected", rc == 1 and "different size" in r.get("error", ""), r)

raw = T + "/main.1000.com.termux.boot.obb"
open(raw, "wb").write(blob(4096, 1))
phone()
rc, r = run("droidB-sideload", "push-obb", raw)
check("raw OBB: package from its name", rc == 0 and r["package"] == "com.termux.boot", r)
odd = T + "/data.obb"
open(odd, "wb").write(b"x")
rc, r = run("droidB-sideload", "push-obb", odd)
check("unnamed OBB asks for the package", rc == 1 and "--package" in r.get("error", ""), r)

scan = T + "/scan"
os.makedirs(scan, exist_ok=True)
for src in (BOOT, xapk, apks, T + "/game.7z", raw, aab):
    shutil.copyfile(src, os.path.join(scan, os.path.basename(src)))
make_zip(scan + "/photos.zip", [("a.jpg", b"x")])
open(scan + "/notes.txt", "w").write("x")
rc, r = run("droidB-sideload", "scan", scan)
kinds = sorted(i["kind"] for i in r.get("items", []))
check("folder scan lists Android files only", rc == 0 and kinds == ["aab", "apk", "bundle", "bundle", "bundle", "obb"], kinds)

print("== Google services ==")
GOOGLE = "Packages:\n  Package [com.google.android.gms]\n    versionCode=244735037 minSdk=31\n    versionName=24.47.35\n"
MICROG = ("Packages:\n  Package [com.google.android.gms]\n    versionCode=240913008\n    versionName=0.3.6.244735\n"
          "  Activity Resolver Table:\n    com.google.android.gms/org.microg.gms.ui.SettingsActivity\n"
          "    install permissions:\n      android.permission.FAKE_PACKAGE_SIGNATURE: granted=true\n")
phone(packages={"com.google.android.gms": {"user0": True, "system": True, "dumpsys": GOOGLE}})
rc, r = run("droidB-gms", "status")
gms = [c for c in r.get("components", []) if c["package"] == "com.google.android.gms"]
check("Google Play services recognised", rc == 0 and gms and gms[0]["flavor"] == "Google" and gms[0]["version"] == "24.47.35", r)

phone(packages={"com.google.android.gms": {"user0": True, "dumpsys": MICROG}}, perms=["android.permission.FAKE_PACKAGE_SIGNATURE"])
rc, r = run("droidB-gms", "status")
gms = [c for c in r.get("components", []) if c["package"] == "com.google.android.gms"]
check("microG recognised, spoofing granted", rc == 0 and gms[0]["flavor"] == "microG" and gms[0]["spoof_granted"] is True and r["spoof_offered"], r)
phone(packages={"com.google.android.gms": {"user0": True, "dumpsys": MICROG.replace("granted=true", "granted=false")}})
rc, r = run("droidB-gms", "status")
check("ROM without signature spoofing explained", "does not offer signature spoofing" in r.get("summary", ""), r)

phone(packages={"com.android.vending": {"user0": False, "system": True}})
rc, r = run("droidB-gms", "restore", "com.android.vending")
sh = [c["argv"] for c in calls("shell")]
check("restore a removed system app for the user", rc == 0 and ["cmd", "package", "install-existing", "--user", "0", "com.android.vending"] in sh
      and ["pm", "enable", "--user", "0", "com.android.vending"] in sh, r)
phone()
rc, r = run("droidB-gms", "restore", "com.example.notthere")
check("restore refuses what the image does not hold", rc == 1 and not any(c["argv"][:2] == ["cmd", "package"] for c in calls("shell")), r)
phone()
rc, r = run("droidB-gms", "restore", "a;reboot")
check("restore refuses a non-package name", rc == 1 and not calls("shell"), r)

phone()
rc, r = run("droidB-gms", "install-microg", "--gmscore", BOOT)
check("wrong APK for the GmsCore role refused", rc == 1 and "not com.google.android.gms" in r.get("error", "") and not calls("install"), r)
phone(packages={"com.google.android.gms": {"user0": True, "system": True, "dumpsys": GOOGLE}})
rc, r = run("droidB-gms", "install-microg", "--gmscore", T + "/gmscore-fake.apk")
check("microG over Google's own services refused", rc == 1 and "cannot replace it" in r.get("error", "") and not calls("install"), r)
phone()
rc, r = run("droidB-gms", "install-microg", "--gmscore", T + "/gmscore-fake.apk", "--gsfproxy", T + "/gsfproxy-fake.apk")
ins = calls("install")
check("microG installed; GsfProxy gets the old-target lift on Android 14",
      rc == 0 and len(ins) == 2 and "--bypass-low-target-sdk-block" not in ins[0]["flags"] and "--bypass-low-target-sdk-block" in ins[1]["flags"], r)

phone(packages={"com.google.android.gms": {"user0": True, "dumpsys": MICROG}, "com.android.vending": {"user0": True}}, idle=["com.android.vending"])
rc, r = run("droidB-gms", "battery", "--apply")
wl = [c["argv"] for c in calls("shell") if c["argv"][:3] == ["cmd", "deviceidle", "whitelist"]]
check("battery: only the missing exemption added", rc == 0 and wl == [["cmd", "deviceidle", "whitelist", "+com.google.android.gms"]], r)

game = make_zip(T + "/game.apk", [("AndroidManifest.xml", "com.android.vending.CHECK_LICENSE".encode("utf-16-le")),
                                   ("classes.dex", b"dex\n035\x00 Lcom/google/android/gms/games/Games; ")])
rc, r = run("droidB-gms", "game", game)
check("game: Play Games + licensing found, licensing flagged", rc == 0 and any(d.startswith("Play Games") for d in r["depends_on"])
      and any(d.startswith("Play licensing") for d in r["depends_on"]) and "microG cannot answer" in r["verdict"], r)
rc, r = run("droidB-gms", "game", BOOT)
check("game: plain app has no Google names", rc == 0 and r["depends_on"] == [], r)

phone(packages={"com.google.android.gms": {"user0": True, "dumpsys": MICROG}})
rc, r = run("droidB-gms", "backup")
check("backup writes status and package state", rc == 0 and "status.json" in r["files"] and "com.google.android.gms.dumpsys.txt" in r["files"], r)
rc, r = run("droidB-gms", "settings", "com.google.android.gms")
check("open app settings", rc == 0 and any(c["argv"][:2] == ["am", "start"] and "package:com.google.android.gms" in c["argv"] for c in calls("shell")), r)

unexpected = calls("UNEXPECTED")
check("no unexpected phone commands", not unexpected, unexpected)
print("SIDELOAD_CASES pass=%d fail=%d" % (passed, failed))
sys.exit(1 if failed else 0)
