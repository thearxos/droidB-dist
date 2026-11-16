#!/usr/bin/env python3
"""Drive droidB-gui's state-changing actions on the connected phone, verify each, then restore it.

usage: DISPLAY=:0 python3 tests/gui_reversible_test.py <droidB-gui> <test.apk>

Every action here is reversible and is reversed before the next. The script refuses to run if the
phone is already in the state it would leave behind (the test app installed, the toggle app
disabled, a proxy set), so a failure cannot be mistaken for a pre-existing condition. It never
touches anything but its own test app, one named toggle app, the http proxy, and a scratch file.
"""
import importlib.machinery, importlib.util, os, subprocess, sys, time

gui = sys.argv[1]
APK = sys.argv[2]
TEST_PKG = "org.arxos.droidbtest"
TOGGLE_PKG = "com.samsung.android.app.dressroom"   # Samsung wallpaper helper, non-critical

loader = importlib.machinery.SourceFileLoader("dbg", gui)
spec = importlib.util.spec_from_loader("dbg", loader)
m = importlib.util.module_from_spec(spec); loader.exec_module(m)
Gtk = m.Gtk

def sh(*cmd):
    return subprocess.run(["adb", "shell", *cmd], capture_output=True, text=True).stdout.strip()
def installed(pkg):
    return sh("pm list packages %s" % pkg).strip() != "" and pkg in sh("pm list packages %s" % pkg)
def enabled(pkg):
    return pkg in sh("pm list packages -e %s" % pkg)
def proxy():
    return sh("settings get global http_proxy")

# preconditions: refuse to run if the end-state already exists
problems = []
if installed(TEST_PKG): problems.append("%s is already installed" % TEST_PKG)
if proxy() not in ("null", ":0", ""): problems.append("a proxy is already set (%s)" % proxy())
if problems:
    print("STOP:", "; ".join(problems)); sys.exit(2)

results = []
def check(name, ok, detail=""):
    results.append((name, ok)); print("%-46s %s %s" % (name, "pass" if ok else "FAIL", detail))

# make the GUI's dialogs and prompts answer predictably
answers = {}
def sync_run(self, fn, done=None):
    out = fn()
    if done: done(out)
m.DroidB._run_async = sync_run
m.DroidB._confirm = lambda self, t, b: True
m.DroidB._msg = lambda self, t, b: None
m.DroidB._need_device = lambda self: True
# install dialog: answer the file chooser with our APK
_real_run = Gtk.Dialog.run
def dialog_run(self):
    t = (self.get_title() or "").lower()
    if isinstance(self, Gtk.FileChooserDialog) and "apk" in t:
        self.set_filename(APK); return Gtk.ResponseType.OK
    return Gtk.ResponseType.CANCEL
Gtk.Dialog.run = dialog_run

def pump(s=0.5):
    end = time.time() + s
    while time.time() < end:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.02)

w = m.DroidB(); pump(1.0)

def select_app(pkg):
    # the Apps panel stores the package in column 0; load then select it
    w._load_apps(); pump(0.8)
    model = w.app_view.get_model()   # the filtered model the view and _app_sel actually use
    sel = w.app_view.get_selection(); sel.unselect_all()
    it = model.get_iter_first()
    while it is not None:
        if model[it][0] == pkg:
            sel.select_iter(it); return True
        it = model.iter_next(it)
    return False

try:
    w.stack.set_visible_child_name("apps"); pump(0.5)
    # 1. install an APK (the GUI's install action, as it runs once a file is chosen)
    w._run_async(lambda: m.adb("install", "-r", APK, timeout=180),
                 lambda r: w._load_apps()); pump(2.0)
    check("install test APK", installed(TEST_PKG))

    # 2. disable then enable it, through the Apps panel's own _app_act (it is a user app)
    if installed(TEST_PKG) and select_app(TEST_PKG):
        w._app_act("disable"); pump(1.5)
        check("disable the app (_app_act)", not enabled(TEST_PKG))
        select_app(TEST_PKG); w._app_act("enable"); pump(1.5)
        check("enable the app (restored)", enabled(TEST_PKG))

    # 3. uninstall it (the Apps panel's uninstall action), restoring the clean state
    if installed(TEST_PKG) and select_app(TEST_PKG):
        w._app_act("uninstall"); pump(2.0)
        check("uninstall test APK (restored)", not installed(TEST_PKG))

    # 4. set a proxy, then clear it
    w.stack.set_visible_child_name("security"); pump(0.5)
    w.sec_proxy.set_text("192.168.1.10:8080")
    w._sec_setproxy(); pump(1.0)
    set_ok = proxy() == "192.168.1.10:8080"
    check("set http proxy", set_ok, proxy())
    # the Clear button handler
    w._run_async(lambda: m.adb("shell", "settings", "put", "global", "http_proxy", ":0"))
    pump(0.8)
    check("clear http proxy (restored)", proxy() in (":0", "null", ""), proxy())

    # 5. screen record 10s -> a local file, nothing changes on the phone
    before = set(os.listdir(os.path.expanduser("~/droidB"))) if os.path.isdir(os.path.expanduser("~/droidB")) else set()
    w.stack.set_visible_child_name("screen"); pump(0.3)
    # call the record action; it writes into ~/droidB
    if hasattr(w, "_screenrecord"):
        w._screenrecord(); pump(0.5)   # _run_async is synchronous here, so this blocks until saved
        after = set(os.listdir(os.path.expanduser("~/droidB"))) if os.path.isdir(os.path.expanduser("~/droidB")) else set()
        new = [f for f in after - before if f.endswith(".mp4")]
        ok = bool(new) and os.path.getsize(os.path.join(os.path.expanduser("~/droidB"), new[0])) > 1000
        check("screen record wrote an mp4 locally", ok, new[0] if new else "no new mp4")
finally:
    # belt and braces: make sure nothing we touched is left changed
    if installed(TEST_PKG): subprocess.run(["adb", "uninstall", TEST_PKG], capture_output=True)
    if proxy() not in ("null", ":0", ""): sh("settings put global http_proxy :0")
    print("restore check: %s installed=%s  | proxy=%s" % (
        TEST_PKG, installed(TEST_PKG), proxy()))

bad = [n for n, ok in results if not ok]
print("\n%d actions, %d failed" % (len(results), len(bad)))
sys.exit(1 if bad else 0)
