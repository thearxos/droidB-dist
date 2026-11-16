#!/usr/bin/python3
"""aapt2 for the test VM: the real one, except for named stand-in APKs the real tool cannot read.

The host has no platform android.jar, so an APK whose package is com.google.android.gms, or one
carrying native code, cannot be built for the tests. For files listed in $FAKE_AAPT_BADGING the
badging text given there is printed; every other file goes to the real aapt2 (/opt/aapt2/aapt2).
"""
import json, os, sys

table = json.load(open(os.environ["FAKE_AAPT_BADGING"])) if os.environ.get("FAKE_AAPT_BADGING") else {}
if sys.argv[1:3] == ["dump", "badging"] and os.path.basename(sys.argv[-1]) in table:
    print(table[os.path.basename(sys.argv[-1])])
    sys.exit(0)
os.execv("/opt/aapt2/aapt2", ["aapt2", *sys.argv[1:]])
