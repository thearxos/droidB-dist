<div align="center">

# droidB

**The ArxOS Android toolkit.** A single fully graphical app for device management,
debloating, backup, flashing, rooting, and mobile security testing. No TUI, no
memorising `adb` incantations. Connect a device and click.

Native engine `0.4.1` · ADB / fastboot · debloat · backup · **spyware scanning** · Frida · MITM · Magisk / TWRP / GSI · MediaTek + Samsung flashing

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

On ArxOS, `arx tools` installs or updates droidB from the R2 tools index. Standalone
on Arch, run the installer from the toolkit checkout:

```bash
sudo ./install.sh
```

The installer installs the toolkit and attempts to fetch the native components and
device dependencies:

| | |
| --- | --- |
| `droidB-gui` | the GTK application (every panel) |
| `droidB`, `droidB-samsung`, `droidB-mod`, `droidB-rescue`, `droidB-adb` | the CLI helpers |
| `droidB-native` | the native engine: Spyware Scan, fleet queue, deep clean, root detection, flashing |
| `droidB-gui-native` | the native GUI, fetched as an AppImage |
| drivers | `android-tools` (adb/fastboot), `libimobiledevice` + `usbmuxd` + `ifuse` (iPhone), `mvt` |
| udev + usbmuxd | installs the rule from `data/` or the older top-level layout; attempts to enable/start usbmuxd |

The installer first uses each compiled asset and its `.sha256` file bundled beside
it, as supplied in the R2 archive. If that pair is absent, it downloads from the
[droidB-dist](https://github.com/thearxos/droidB-dist) release. Both paths verify
SHA-256 before installation. The engine is installed first, then the GUI.
A checksum mismatch skips that asset and prints a warning.
A failed native download leaves the legacy toolkit installed, but a fresh installation
will lack the affected native features. Re-run `install.sh` to retry. Package installation
and usbmuxd startup are best effort; use `droidB-native mvt setup` to check dependencies.

The installer checks `data/51-droidB-android.rules` first, then the older location
beside the script, and warns if neither exists. Reconnect the phone or log in again
after USB permission/group changes. Maintainers with the private source checkout can
use `NATIVE.md` for source installation.

The GUI launcher uses FUSE when `ldconfig` reports `libfuse.so.2`, otherwise it requests
AppImage extraction and execution. The GUI still needs `droidB-native` on `PATH`.

Launch from the menu (**droidB**) or run `droidB-gui`. The native GUI, which carries the
Spyware Scan panel, is **droidB (Native)** in the menu or `droidB-gui-native`. Both are
installed side by side: the native one is the direction of travel, the GTK one is what
has shipped longest.

## Highlights

- **Mass debloat** - the fastest way to strip a new device: scan, review, and remove
  dozens of bloatware packages at once. Uninstall-for-user keeps the APK so an OTA can
  restore it; disable is fully reversible.
- **Security testing built in** - set the system proxy, drop in a CA cert, run Frida,
  and capture packets without leaving the app.
- **Spyware scanning, for real phones and whole fleets** - droidB drives MVT to check a
  device against the public indicator sets that identify Pegasus and commodity stalkerware.
  A bounded worker queue scans a few devices at a time. Capacity with 100+ attached
  phones has not been validated on hardware.
- **Samsung flashing without a closed blob** - native builds prefer droidB-thor's
  `libodin4_static.a` through its primitive-only C API. Other system libraries remain
  dynamic dependencies. A build with only the shared Thor library requires that library
  at runtime and emits a build warning. Builds without a usable Thor library/header use
  the `odin4` subprocess path, which requires the CLI for Samsung operations.
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
droidB-native mvt setup                 # check/install acquisition dependencies
droidB-native mvt devices               # what is attached
droidB-native mvt fleet --workers 4      # scan them all, 4 at a time
droidB-native mvt bugreport <file.zip>    # or check something already saved
droidB-native mvt report <results-dir>   # re-read a finished scan without rescanning
```

Use the installed `droidB-native` command for these workflows; `droidB` is the separate
legacy shell toolkit. Fleet output identifies the device and acquisition/analysis stage.
Carriage-return progress repaints update one terminal line; piped progress, including
the GUI stream, is limited to about one update per second. A child process silent for
about ten seconds gets an elapsed-time heartbeat. This signals waiting, not a measured
completion percentage. Hardware confirmation of the new streaming behavior is pending.

### Scan coverage and failures

Use a fresh `--out` directory for each analysis. Existing output is preserved and rejected
as a new destination. Failed commands, empty acquisition files, missing results, interrupted
wrapper runs, and malformed result JSON do not produce a successful no-match verdict.
Partial output remains available for inspection.

The default Android live scan collects a bug report only. For broader acquisition, collect
with AndroidQF and use `droidB-native mvt androidqf <acquisition-directory>`. An empty `backup.ab`
is reported as a coverage gap while the other artifacts are checked. The wrapper does not
automatically enable backup encryption, root a device, or recover missing private data.

The latest recorded iPhone fleet run failed during backup with `mobilebackup2 (-4)`
after roughly 4.2 GB. Completion of that live wrapper path remains unverified; the
failed acquisition must not be treated as a no-match scan. See
[validation evidence](tests/VALIDATION.md) for the scope of recorded checks.

`mvt report` reads MVT's structured alerts, keeping observations separate from indicator
matches and avoiding duplicate per-module alerts. Imported results without the wrapper's
run record have unverified completion status. Missing indicator metadata and logged MVT
processing errors are shown as limitations. Output directories created by the scanner are
restricted to the local account. Device identifiers and private records must stay out of
source-control fixtures.

### Knowing how a phone is rooted

`droidB-native clean inspect` reads device administrators, accessibility services,
notification listeners and visible root signals without changing device settings.

The root probe checks binaries, directories, mounts, package names and build properties
in one ADB call. It names Magisk (with a version when available), KernelSU, APatch or
a visible `su` binary when the corresponding signals are found. Example output:

```
● rooted via Magisk 29.0:MAGISK:R (29000)
    · magisk binary at /apex/com.android.runtime/bin/magisk
    · 7 mount(s) backed by magisk
    · app installed: com.topjohnwu.magisk
    · su at /apex/com.android.runtime/bin/su
```

These are heuristic signals. An installed manager or leftover binary does not prove
active root access; hidden or renamed components can be missed. Since `0.4.1`, the
probe requires both a successful ADB exit and its closing marker. A failed or
incomplete check reports an unknown result, even when partial output contains root
signals or the closing marker arrived before a transport error. A completed check
with no visible signals still does not prove the phone is unrooted.
`test-keys`, `ro.debuggable=1` and permissive SELinux are supporting
observations and do not independently set the root verdict.

Root signals do not prove access to SMS or call-log providers. The wrapper does not
implement message deletion.

### If something is found

droidB can strip a detected app of its power and remove it (`droidB-native clean app <package>`:
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
| `droidB-gui-native` | the native GUI (Tauri), shipped as an AppImage; carries the Spyware Scan panel and drives `droidB-native` |
| `droidB-native` | the native engine behind the newer features: Spyware Scan, fleet queue, deep clean, root detection, `libodin4` flashing |
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
