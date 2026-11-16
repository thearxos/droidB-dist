#!/usr/bin/env python3
"""Drive the Files panel's own functions on a scratch folder of the connected phone.

usage: DISPLAY=:0 python3 tests/gui_files_test.py [path/to/droidB-gui]

Everything happens inside /sdcard/Download/droidB-test, which must not exist beforehand and is
removed at the end. The decoy check is the one that matters: deleting a folder whose name has a
space ("a b") must not delete its neighbour "a".
"""
import importlib.machinery, importlib.util, os, subprocess, sys, tempfile, time

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "droidB-gui")
loader = importlib.machinery.SourceFileLoader("droidb_gui_files", path)
spec = importlib.util.spec_from_loader("droidb_gui_files", loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)
Gtk = m.Gtk

ROOT = "/sdcard/Download"
TEST = ROOT + "/droidB-test"

def sh(*cmd):
    return subprocess.run(["adb", "shell", *cmd], capture_output=True, text=True).stdout

def exists(p):
    # one quoted argument, so this check is not fooled by the same quoting bug it looks for
    return sh("test -e '%s' && echo yes || echo no" % p.replace("'", "'\\''")).strip() == "yes"

if exists(TEST):
    print("STOP: %s already exists; refusing to touch it" % TEST); sys.exit(2)

answers = []
def sync_run(self, fn, done=None):
    out = fn()
    if done: done(out)
m.DroidB._run_async = sync_run
m.DroidB._prompt = lambda self, title, ph, default="": answers.pop(0)
m.DroidB._confirm = lambda self, t, b: True   # only ever asked about things inside TEST
m.DroidB._msg = lambda self, t, b: print("  message:", t, "-", b)

def pump(s=0.4):
    end = time.time() + s
    while time.time() < end:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.02)

w = m.DroidB(); pump(1.0)

def go(p):
    w._fb_go(p); pump(0.6)

def select(*names):
    sel = w.f_view.get_selection(); sel.unselect_all()
    found = 0
    for i, row in enumerate(w.f_store):
        if row[1] in names:
            sel.select_path(Gtk.TreePath.new_from_indices([i])); found += 1
    return found == len(names)

results = []
def check(name, ok, detail=""):
    results.append((name, ok)); print("%-44s %s %s" % (name, "pass" if ok else "FAIL", detail))

try:
    go(ROOT)
    answers.append("droidB-test"); w._fb_mkdir(); pump()
    check("mkdir droidB-test", exists(TEST))

    go(TEST)
    answers.append("m n"); w._fb_mkdir(); pump()
    check("mkdir 'm n' (name with a space)", exists(TEST + "/m n"))

    # fixtures made with correct quoting, independent of the code under test, so the delete
    # check below is real: 'a b' must exist before Delete is pressed on it
    sh("mkdir -p '%s/a' '%s/a b'" % (TEST, TEST))
    check("fixture: 'a' and 'a b' exist", exists(TEST + "/a") and exists(TEST + "/a b"))

    # put something in the decoy so a wrong delete loses real content
    tmp = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False); tmp.write("decoy\n"); tmp.close()
    subprocess.run(["adb", "push", tmp.name, TEST + "/a/keep.txt"], capture_output=True)
    go(TEST)
    check("decoy file present", exists(TEST + "/a/keep.txt"))

    check("'a b' is selectable in the panel", select("a b"))
    w._fb_delete(); pump(); go(TEST)
    check("delete 'a b' removed it", not exists(TEST + "/a b"))
    check("delete 'a b' kept neighbour 'a' and its file", exists(TEST + "/a/keep.txt"))

    subprocess.run(["adb", "push", tmp.name, TEST + "/x y.txt"], capture_output=True); go(TEST)
    check("'x y.txt' is selectable", select("x y.txt"))
    answers.append("z w.txt"); w._fb_rename(); pump(); go(TEST)
    check("rename 'x y.txt' -> 'z w.txt'", exists(TEST + "/z w.txt") and not exists(TEST + "/x y.txt"))

    select("z w.txt"); answers.append(TEST + "/a/"); w._fb_move(); pump(); go(TEST)
    check("move 'z w.txt' into a/", exists(TEST + "/a/z w.txt"))
finally:
    sh("rm -rf '%s'" % TEST)
    print("cleanup: %s %s" % (TEST, "removed" if not exists(TEST) else "STILL PRESENT"))

bad = [n for n, ok in results if not ok]
print("\n%d checks, %d failed" % (len(results), len(bad)))
sys.exit(1 if bad else 0)
