#!/usr/bin/env python3
"""The GUI's install, game-data and Google-services flows, against the scripted phone.

    xvfb-run -s '-screen 0 1280x800x24' python3 tests/gui_sideload_test.py OUTDIR

No real phone: adb is tests/fake-adb.py (it changes nothing outside OUTDIR). The real droidB-gui,
droidB-sideload, droidB-gms and aapt2 run. File choosers, confirmations and messages are answered
by the test and recorded, so every dialog the user would see is checked by its title. Screenshots
of the Apps and Google services panels are written to OUTDIR. Prints GUI_SIDELOAD pass=N fail=M.
"""
import importlib.machinery, importlib.util, json, os, shutil, subprocess, sys, time, zipfile

out = os.path.abspath(sys.argv[1])
shutil.rmtree(out, ignore_errors=True)
os.makedirs(out)
repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
apks = os.path.join(os.path.dirname(os.path.dirname(repo)), "vendor", "termux-fdroid")
BOOT = os.path.join(apks, "com.termux.boot_1000.apk")
fx = os.path.join(out, "fixtures")
os.makedirs(fx)
os.symlink(os.path.join(repo, "tests", "fake-adb.py"), os.path.join(fx, "adb"))
MICROG = ("Packages:\n  Package [com.google.android.gms]\n    versionCode=240913008\n    versionName=0.3.6.244735\n"
          "    com.google.android.gms/org.microg.gms.ui.SettingsActivity\n      android.permission.FAKE_PACKAGE_SIGNATURE: granted=true\n")


def phone(**over):
    st = {"devices": [["SER1", "device"]], "sdcard": out + "/sdcard",
          "props": {"ro.build.version.sdk": "34", "ro.product.cpu.abilist": "arm64-v8a,x86_64", "ro.product.model": "Fixture"},
          "packages": {"com.google.android.gms": {"user0": True, "dumpsys": MICROG}}, "perms": ["android.permission.FAKE_PACKAGE_SIGNATURE"], "idle": []}
    st.update(over)
    json.dump(st, open(out + "/state.json", "w"))
    open(out + "/adb.log", "w").close()


def calls(kind):
    return [json.loads(l) for l in open(out + "/adb.log") if l.strip() and json.loads(l)["kind"] == kind]


os.environ.update(PATH=fx + ":" + os.environ["PATH"], FAKE_ADB_STATE=out + "/state.json", FAKE_ADB_LOG=out + "/adb.log",
                  HOME=out + "/home", XDG_CACHE_HOME=out + "/cache", XDG_DATA_HOME=out + "/data")
os.environ.pop("ANDROID_SERIAL", None)
os.makedirs(out + "/home", exist_ok=True)
phone()

xapk = out + "/game.xapk"
with zipfile.ZipFile(xapk, "w") as z:
    z.write(BOOT, "com.termux.boot.apk")
    z.writestr("Android/obb/com.termux.boot/main.1000.com.termux.boot.obb", os.urandom(200000))
obb = out + "/main.1000.com.termux.boot.obb"
open(obb, "wb").write(os.urandom(5000))

loader = importlib.machinery.SourceFileLoader("droidb_gui", os.path.join(repo, "droidB-gui"))
spec = importlib.util.spec_from_loader("droidb_gui", loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)
Gtk, GLib = m.Gtk, m.GLib
w = m.DroidB()
w.show_all()
seen, answers = [], {}
w._confirm = lambda title, body: (seen.append(("confirm", title, body)), answers.get(title, True))[1]
w._msg = lambda title, body: seen.append(("msg", title, body))
w._choose = lambda title, patterns, label: chosen.pop(0)
w._prompt = lambda title, placeholder, default="": default
passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    passed, failed = passed + bool(cond), failed + (not cond)
    print("  %s %s%s" % ("PASS" if cond else "FAIL", name, "" if cond else "  " + str(detail)[:600]))


def pump(until, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        if until():
            return True
        time.sleep(0.05)
    return False


def shot(name):
    pump(lambda: False, 1.5)
    subprocess.run(["import", "-window", "root", os.path.join(out, name)], check=False)


w.stack.set_visible_child_name("apps")
chosen = [xapk]
w._install_apk()
ok = pump(lambda: w.app_status.get_text().startswith(("Installed", "Not installed")))
titles = [s[1] for s in seen]
check("install bundle: summary asked, then installed", ok and w.app_status.get_text().startswith("Installed")
      and "Install com.termux.boot?" in titles and "Installed" in titles, (w.app_status.get_text(), seen))
check("install bundle: game data pushed and size-checked", any("size checked" in s[2] for s in seen if s[1] == "Installed")
      and os.path.getsize(out + "/sdcard/Android/obb/com.termux.boot/main.1000.com.termux.boot.obb") == 200000, seen)
shot("apps.png")

seen.clear()
phone(install_rules=[{"unless": "-d", "code": "INSTALL_FAILED_VERSION_DOWNGRADE"}])
chosen = [BOOT]
w._install_apk()
ok = pump(lambda: w.app_status.get_text().startswith(("Installed", "Not installed")))
check("downgrade asks, then installs with -d", ok and "Install an older version?" in [s[1] for s in seen]
      and "-d" in calls("install")[-1]["flags"], (w.app_status.get_text(), seen))

seen.clear()
phone(install_rules=[{"unless": "-d", "code": "INSTALL_FAILED_VERSION_DOWNGRADE"}])
answers["Install an older version?"] = False
chosen = [BOOT]
w._install_apk()
ok = pump(lambda: w.app_status.get_text() == "Not installed.")
check("declined downgrade installs nothing", ok and all("-d" not in c["flags"] for c in calls("install")), seen)
answers.clear()

seen.clear()
phone()
chosen = [obb]
w._push_obb()
ok = pump(lambda: w.app_status.get_text().startswith(("Game data copied", "Not copied")))
check("push game data", ok and w.app_status.get_text() == "Game data copied for com.termux.boot.", (w.app_status.get_text(), seen))

seen.clear()
phone()
w.stack.set_visible_child_name("gms")
w._gms_status()
ok = pump(lambda: "microG is installed" in w.gms_out.get_text())
check("Google services: microG shown with spoofing granted", ok and "spoofing granted" in w.gms_out.get_text(), w.gms_out.get_text())
shot("google-services.png")

seen.clear()
w._gms_battery()
ok = pump(lambda: any(s[1] == "Battery exemptions" for s in seen))
wl = [c for c in calls("shell") if c["argv"][:3] == ["cmd", "deviceidle", "whitelist"]]
check("battery exemption asked and applied", ok and any(s[1] == "Exempt from battery saving?" for s in seen)
      and wl and wl[-1]["argv"][3] == "+com.google.android.gms", seen)

print("GUI_SIDELOAD pass=%d fail=%d" % (passed, failed))
w.destroy()
sys.exit(1 if failed else 0)
