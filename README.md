<div align="center">

# droidB

**The ArxOS Android toolkit.** A single fully graphical app for device management,
debloating, backup, flashing, rooting, and mobile security testing. No TUI, no
memorising `adb` incantations. Connect a device and click.

`v0.0.1` · ADB / fastboot · debloat · backup · **spyware scanning** · Frida · MITM · Magisk / TWRP / GSI · MediaTek + Samsung flashing

</div>

---

## What it does

droidB started life as a debloater and grew into a complete mobile workbench. Every
panel talks to the device over ADB/fastboot with threaded calls, so the window never
freezes, and the destructive actions always confirm first.

| Panel | What you get |
|---|---|
| **Device** | live model / Android / SoC / battery / storage, reboot modes, and a **Device access** hub that works with or without USB debugging: enable-debugging override, screen control (scrcpy - drive a dead display from your PC), blind PIN unlock, and OTG HID |
| **Apps** | list packages (filter, user-only), install an APK, uninstall, disable / enable, clear data |
| **Logcat** | live streaming log with a text filter, pause and clear |
| **Files** | a real-time device file browser: navigate, multi-select, concurrent pull / push, batch move / delete, mkdir, rename |
| **Screen** | screenshot, 10s screen record, and live mirror via scrcpy |
| **Debloat** | **mass debloat** - scan installed packages, flag known OEM / carrier bloatware, then uninstall (keeps the APK) or disable, one at a time or **Remove ALL likely bloat** in a click |
| **Backup** | **one rescue backup grabs everything** - contacts, call logs, SMS, media, app list + app data to `~/droidB-rescue` (do this before any risky flash), plus **Authorize this PC** (ADB-key failsafe) and per-app data (root) |
| **Fastboot** | detect, reboot modes, flash a partition, unlock / lock the bootloader |
| **Shell** | an in-window `adb shell` with output |
| **Frida** | install the right `frida-server` for the device arch, start / stop it, list processes, attach or spawn an app |
| **Security** | point the device at your **MITM proxy** (Burp / mitmproxy), install a **CA certificate** for HTTPS interception, and capture traffic with **tcpdump** to a pcap |
| **Spyware Scan** | check a phone for spyware and stalkerware with the **Mobile Verification Toolkit**, Android and iPhone both. Scans a whole fleet a few phones at a time, streams every line as it happens, and tells you what matched and what to do about it |
| **Root / ROM** | Magisk boot patch, TWRP flash / boot, GSI install, custom-ROM sideload + fastboot update, and payload.bin / super.img extraction |
| **Flash** | full **MediaTek** (mtkclient: read GPT, payload bypass, per-partition read / write / erase, backup all, unlock / lock) and full **Samsung Odin** — two backends: **odin4** (recommended; pulls the device PIT itself, so no partition-name guessing) and **heimdall** (corrected PIT map that fixes the `dspso→DSP` / `hypvm→HYP` mismatch class). BL / AP / CP / CSC / USERDATA slots, Download-mode device detect, Auto-Reboot / Keep-data / Nand-Erase |

## Install

Ships with ArxOS. Standalone on Arch:

```bash
sudo ./install.sh          # installs droidB-gui + the droidB-samsung / droidB-mod helpers + android-tools
```

Launch from the menu (**droidB**) or run `droidB-gui`.

## Highlights

- **Mass debloat** - the fastest way to strip a new device: scan, review, and remove
  dozens of bloatware packages at once. Uninstall-for-user keeps the APK so an OTA can
  restore it; disable is fully reversible.
- **Security testing built in** - set the system proxy, drop in a CA cert, run Frida,
  and capture packets without leaving the app.
- **Spyware scanning, for real phones and whole fleets** - droidB drives MVT to check a
  device against the public indicator sets that identify Pegasus and commodity stalkerware.
  It handles 100+ attached phones by queueing them and scanning a few at a time, so the
  machine stays usable instead of thrashing.
- **Samsung flashing without a closed blob** - droidB links `libodin4` from droidB-thor
  directly through its C ABI when the library is present, and falls back to driving the
  `odin4` CLI as a subprocess when it is not, so the portable binary still runs on a machine
  that has neither. Nothing is hard-linked at build time, because that would make the binary
  refuse to start and take every other droidB feature down with it.
- **Vendor flashing** - MediaTek (BROM / preloader) and Samsung (Download mode) firmware
  flashing with the tools installed on demand.
- **Threaded + confirming** - long transfers run in the background; anything destructive
  asks first.


## Spyware Scan

Point it at a phone and it answers one question: is there anything on here that matches a
known surveillance tool.

Two things are worth understanding before you use it.

**It works in two stages.** MVT analyses artifacts, not live phones (upstream removed the
old over-the-wire check), so droidB copies the data off first - `adb bugreport` on Android,
an `idevicebackup2` backup on iPhone - and then checks what came off. Copying is usually the
slow half, which is why the panel tells you which stage each device is in.

**A clean result is not a clean bill of health.** It means nothing matched the indicators you
currently hold. Refresh them often; the panel does it for you if you leave updates on
automatic, and you can set it to ask first or never update.

**"Worth a look" is not "infected".** MVT writes a `<module>_detected.json` for heuristic
findings as well as real indicator matches, and the two mean very different things. droidB
reports them separately:

- **Detections** matched a published spyware indicator and require investigation.
- **Observations** matched nothing; MVT simply noticed something unusual.

Intentional rooting can explain observations about Magisk or system mounts. Other
observations, such as old patches, disabled app verification, or unexpected executable files,
still need review. Accessibility access alone is not proof of spyware. Indicator matches
also require investigation; droidB does not label a phone infected from a match alone.

```bash
droidB mvt setup                 # install everything needed, Android and iPhone
droidB mvt devices               # what is attached
droidB mvt fleet --workers 4     # scan them all, 4 at a time
droidB mvt bugreport <file.zip>  # or check something already saved
droidB mvt report <results-dir>  # re-read a finished scan without rescanning
```

Many phones at once is the normal case, not an edge case. A fleet is queued and
scanned a few at a time (`--workers`), because 100 simultaneous acquisitions would
thrash CPU, disk and USB bandwidth and finish slower than a queue. Every line is
tagged with the device it came from, and each phone reports which stage it is in.

### Scan coverage and failures

Use a fresh `--out` directory for each analysis. Existing output is preserved and rejected
as a new destination. Failed commands, empty acquisition files, missing results, interrupted
wrapper runs, and malformed result JSON do not produce a successful no-match verdict.
Partial output remains available for inspection.

The default Android live scan collects a bug report only. For broader acquisition, collect
with AndroidQF and use `droidB mvt androidqf <acquisition-directory>`. An empty `backup.ab`
is reported as a coverage gap while the other artifacts are checked. The wrapper does not
automatically enable backup encryption, root a device, or recover missing private data.

`mvt report` reads MVT's structured alerts, keeping observations separate from indicator
matches and avoiding duplicate per-module alerts. Imported results without the wrapper's
run record have unverified completion status. Missing indicator metadata and logged MVT
processing errors are shown as limitations. Output directories created by the scanner are
restricted to the local account. Device identifiers and private records must stay out of
source-control fixtures.

### Knowing how a phone is rooted

`droidB clean inspect` reads what a phone currently grants and never changes anything:
device administrators, what can read the screen, what can read notifications, and whether
it is rooted.

Root is not one thing, and `su` on PATH is the weakest possible signal: Magisk in DenyList
mode hides from it, KernelSU and APatch ship no classic `su` at all, and a leftover binary
on an unrooted phone is a false positive. So several signals are collected in one round
trip (it runs per device, and a fleet is 100+ phones) and the method is named with its
version, with every signal that fired listed so the finding can be argued with:

```
● rooted via Magisk 29.0:MAGISK:R (29000)
    · magisk binary at /apex/com.android.runtime/bin/magisk
    · 7 mount(s) backed by magisk
    · app installed: com.topjohnwu.magisk
    · su at /apex/com.android.runtime/bin/su
```

Magisk, KernelSU and APatch are each detected. test-keys builds, `ro.debuggable=1` and a
permissive SELinux are reported as evidence but never decide the verdict on their own,
because they describe a development build rather than root.

Why it matters here: root is what makes individual text messages and call-log entries
reachable. Without it those providers refuse writes from `adb` and a deep clean can strip
an app of its power but not scrub what it left behind.

### If something is found

droidB can strip a detected app of its power and remove it (`droidB clean app <package>`:
deactivate its device-admin rights, revoke accessibility and notification access, take back
permissions, clear its data, uninstall or disable it). That path is deliberately gated behind
two acknowledgements, because both matter more than convenience:

- **Removing it destroys the evidence** the scan just produced. If the phone may need to be
  shown to an investigator or a lawyer, save the results first.
- **Whoever installed it will notice it stopped reporting.** Stalkerware is usually installed
  by someone with physical access and an ongoing relationship to the person being watched,
  and losing surveillance can escalate the danger to them. That decision belongs to the person
  holding the phone, after a safety plan, not to a tool that tidied up on their behalf.

Message and call-log deletion is not implemented by `clean app`. The
`--purge-messages` option returns an error, including on rooted devices. Root alone does
not guarantee that Android's provider accepted a write. App cleanup revokes only the
target package's granted runtime permissions, checks command results and available state,
and stops after a failed step. It never resets permissions for all apps.

## Helpers

| File | Purpose |
|---|---|
| `droidB-gui` | the GTK application (all panels) |
| `droidB-mod` | Magisk boot patch, payload.bin + super.img extraction |
| `droidB-samsung` | Samsung firmware flasher — **odin4** (default) + **heimdall** (PIT-corrected) backends, Download-mode device detect |
| `droidB-rescue` | **emergency backup + ADB auth failsafe** — pulls contacts, call logs, SMS, media, app list + app data before a risky flash; `--authorize` injects this PC's ADB key so the shell trusts it with no on-screen prompt (cracked-screen / no-debugging recovery). Works over normal **or recovery** adb |
| `droidB-adb` | **works with or without USB debugging** — detects the live access path (adb / recovery / sideload / fastboot / download / raw USB) and can **override** (turn USB debugging on) from a recovery or root shell: trusts this PC, sets `adb_enabled=1`, enables the adb interface. `access` gets you in and then opens **full screen control** (scrcpy), so a dead-screen / debugging-off device is usable like a normal one. Honest about the one wall (locked + stock recovery + debugging off = Android security) |

## Notes

- Enable **USB debugging** on the device and accept the RSA prompt.
- Root-only actions (per-app data backup, system CA cert, tcpdump) need `su` on the device.
- Frida needs `frida-tools` on the host (`arx install python-frida-tools`).

---

<div align="center">
Part of <b>ArxOS</b> · offensive and defensive security, finished.<br>
<sub>built by <b>Stingray Labs</b> · スティングレイ</sub>
</div>
