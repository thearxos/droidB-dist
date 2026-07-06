<div align="center">

# droidB

**The ArxOS Android toolkit.** A single fully graphical app for device management,
debloating, backup, flashing, rooting, and mobile security testing. No TUI, no
memorising `adb` incantations. Connect a device and click.

`v0.0.1` · ADB / fastboot · debloat · backup · Frida · MITM · Magisk / TWRP / GSI · MediaTek + Samsung flashing

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
- **Vendor flashing** - MediaTek (BROM / preloader) and Samsung (Download mode) firmware
  flashing with the tools installed on demand.
- **Threaded + confirming** - long transfers run in the background; anything destructive
  asks first.

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
Part of <b>ArxOS</b> · offensive and defensive security, finished.
</div>
