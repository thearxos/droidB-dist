#!/usr/bin/env python3
"""Press every droidB-gui button that only reads, against the connected device, and report.

usage: DISPLAY=:0 python3 tests/gui_feature_sweep.py [path/to/droidB-gui]

Read-only actions run for real. Anything that changes the device is not pressed: it is listed so
the owner can decide. Every dialog answers Cancel and every confirmation answers No, so a button
that was meant to be read-only but asks first cannot change anything either. Output carries no
serial numbers or file names, only what each button did.
"""
import importlib.machinery, importlib.util, os, sys, time, traceback

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "droidB-gui")
loader = importlib.machinery.SourceFileLoader("droidb_gui", path)
spec = importlib.util.spec_from_loader("droidb_gui", loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)
Gtk, GLib = m.Gtk, m.GLib

# panel -> buttons that only read from the device (or write only to the local ~/droidB folder)
READ_ONLY = {
    "device": {"Refresh"},
    "apps": {"Reload"},
    "logcat": {"Start"},
    "files": {"Home", "Reload", "Go"},
    "screen": {"Screenshot"},
    "fastboot": set(),
    "shell": {"Run"},
    "flash": {"Detect device"},
    "debloat": {"Scan"},
    "backup": set(),
    "frida": {"List processes"},
    "security": set(),
    "mod": set(),
}

buttons, events, current = [], [], [None]

orig_act = m.DroidB._act
def rec_act(self, label, cb, danger=False):
    buttons.append((current[0], label, cb, danger))
    return orig_act(self, label, cb, danger)
m.DroidB._act = rec_act

for name in [n for n in dir(m.DroidB) if n.startswith("_p_")]:
    f = getattr(m.DroidB, name)
    def wrap(f=f, panel=name[3:]):
        def w(self, *a, **k):
            prev, current[0] = current[0], panel
            try:
                return f(self, *a, **k)
            finally:
                current[0] = prev
        return w
    setattr(m.DroidB, name, wrap())

def sync_run(self, fn, done=None):
    try:
        out = fn()
    except Exception:
        events.append(("EXCEPTION", traceback.format_exc().strip().splitlines()[-1])); return
    if done:
        try:
            done(out)
        except Exception:
            events.append(("EXCEPTION in result", traceback.format_exc().strip().splitlines()[-1])); return
    events.append(("ok", (str(out) if out is not None else "").strip()))
m.DroidB._run_async = sync_run
m.DroidB._msg = lambda self, title, body: events.append(("message", "%s: %s" % (title, str(body)[:160])))
m.DroidB._confirm = lambda self, title, body: (events.append(("refused (asks first)", title)), False)[1]
m.DroidB._pick = lambda self, *a, **k: None
Gtk.Dialog.run = lambda self: (events.append(("dialog cancelled", self.get_title() or "")), Gtk.ResponseType.CANCEL)[1]

# Buttons that open a terminal window are captured, not opened: the command they would run is
# run here, headless, with a time limit, and judged by its exit status.
terminal_cmds = []
_real_popen = m.subprocess.Popen
def capture_popen(argv, *a, **k):
    if argv and os.path.basename(str(argv[0])) in ("xfce4-terminal", "konsole", "xterm"):
        script = argv[-1] if argv else ""
        terminal_cmds.append(script); events.append(("terminal", script))
        class Dummy:
            def poll(self): return 0
            def wait(self, *a, **k): return 0
        return Dummy()
    return _real_popen(argv, *a, **k)
m.subprocess.Popen = capture_popen
if hasattr(m.DroidB, "_termrun"):
    m.DroidB._termrun = lambda self, title, cmd, *a, **k: (terminal_cmds.append(cmd), events.append(("terminal", cmd)))[1]

def run_headless(script):
    import re, subprocess
    script = re.sub(r";\s*echo;\s*read -rp.*$", "", script).strip()
    try:
        r = subprocess.run(["bash", "-lc", script], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=45)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "timed out after 45s"

def pump(seconds=0.3):
    end = time.time() + seconds
    while time.time() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.02)

w = m.DroidB()
pump(1.5)
import subprocess as _sp
MODEL = _sp.run(["adb", "shell", "getprop", "ro.product.model"], capture_output=True, text=True).stdout.strip()
if hasattr(w, "sh_in"):
    w.sh_in.set_text("getprop ro.product.model")

def text_of(widget):
    try:
        if isinstance(widget, Gtk.Label): return widget.get_text()
        if isinstance(widget, Gtk.TextView):
            b = widget.get_buffer(); return b.get_text(b.get_start_iter(), b.get_end_iter(), False)
    except Exception:
        return ""
    return ""

rows = []
for panel, label, cb, danger in buttons:
    if label not in READ_ONLY.get(panel, set()):
        rows.append((panel, label, "not run", "changes the device" if danger or panel in ("flash", "fastboot", "mod", "security", "backup") else "changes the device or needs a choice"))
        continue
    events.clear()
    t0 = time.time()
    try:
        cb(None)
    except Exception:
        events.append(("EXCEPTION", traceback.format_exc().strip().splitlines()[-1]))
    pump(2.0 if label == "Start" else 0.6)
    if panel == "logcat" and label == "Start":
        try:
            cb(None)  # stop again
        except Exception:
            pass
    bad = [e for e in events if e[0].startswith("EXCEPTION")]
    # what the button actually showed, where it shows anything
    shown = None
    if panel == "shell" and hasattr(w, "sh_out"):
        shown = text_of(w.sh_out)
        if MODEL and MODEL not in shown: bad.append(("FAIL", "shell output lacks the model name"))
    if panel == "logcat" and hasattr(w, "lc_view"):
        shown = text_of(w.lc_view)
        if not shown.strip(): bad.append(("FAIL", "logcat showed nothing in 2 s"))
    for e in [e for e in events if e[0] == "terminal"]:
        rc, out = run_headless(e[1])
        if rc != 0: bad.append(("FAIL", "terminal command exited %d: %s" % (rc, out.splitlines()[-1][:120] if out else "")))
        else: shown = out
    status = "FAIL" if bad else "pass"
    detail = bad[0][1] if bad else ("shows %d lines" % len(shown.splitlines()) if shown is not None else
              "; ".join(k if not v else "%s (%d chars)" % (k, len(v)) for k, v in events[:3]) or "no output")
    rows.append((panel, label, status, "%s [%.1fs]" % (detail, time.time() - t0)))

# the panels' own read-on-load text, which is what the owner sees first
if hasattr(w, "dev_info"):
    t = text_of(w.dev_info)
    rows.append(("device", "(info text)", "FAIL" if (not t or "error" in t.lower()) else "pass", "%d lines" % len(t.splitlines())))

width = max(len(p or "") for p, *_ in rows) + 1
for p, l, s, d in rows:
    print("%-*s %-28s %-7s %s" % (width, p, l[:28], s, d))
ran = [r for r in rows if r[2] in ("pass", "FAIL")]
print("\n%d buttons: %d run (%d pass, %d fail), %d not run because they change the device or need a choice" % (
    len(rows), len(ran), sum(r[2] == "pass" for r in ran), sum(r[2] == "FAIL" for r in ran), sum(r[2] == "not run" for r in rows)))
sys.exit(1 if any(r[2] == "FAIL" for r in rows) else 0)
