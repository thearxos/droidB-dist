# ArxOS Link (arxlink) - our own on-device companion for a no-root, always-on home device

Owner (2026-11-02): build OUR trusted app (not Tailscale, not Tasker), drop it on the phone via adb
the way we build ArxOS, so the phone becomes a forever-reachable home server / TV remote. It must:
run forever, never be killed by battery optimization, be invisible to the kid (no launcher icon,
like Play Services - visible only in Settings > Apps), be very hard to delete (the kid clears storage
for games on a 4GB phone and has deleted apps before), stay tiny (low RAM/footprint), and keep ADB +
the tunnel up - all with NO root and WITHOUT debloating the phone.

## The honest constraint, and the no-root answer
- A true **/system (system app)** install needs root or a writable system partition. Not available
  on a stock locked Samsung without root. So we do NOT need /system.
- **Device Admin** gives the owner's ACTUAL goals with NO root:
  - **Unremovable by the kid:** an active Device Admin app cannot be uninstalled until admin is
    disabled (which lives behind Settings > Security, not the app drawer). The kid cannot casually
    delete it while clearing space for games.
  - **No icon:** declare no LAUNCHER activity -> no app-drawer icon (like Play Services). It only
    appears in Settings > Apps.
  - **Never killed by battery optimization:** granted the exemption over adb, no root:
    `adb shell dumpsys deviceidle whitelist +com.arxos.link`.
  - **Runs forever:** a foreground service (Android requires a minimal notification on O+; we keep it
    the lowest-priority, no-sound, "ArxOS Link active" line) + START_STICKY + a BOOT_COMPLETED
    receiver to relaunch after a reboot.
  - **Re-enables wireless debugging on boot (no root):** granted `WRITE_SECURE_SETTINGS` once over adb
    (`adb shell pm grant com.arxos.link android.permission.WRITE_SECURE_SETTINGS`); on boot it sets
    `settings put global adb_wifi_enabled 1`, so ADB-over-network comes back by itself.
- Strongest no-root option is **Device Owner** (`adb shell dpm set-device-owner`), which can hide,
  block uninstall and exempt battery centrally - but it needs a phone with NO accounts (factory
  state). The A16 already has the kid's accounts, so Device Admin (no reset) is the pragmatic choice;
  Device Owner is an option only on a fresh device.

## The tunnel, inside our app (free, no separate Tailscale app)
Our app embeds the OPEN-SOURCE tunnel client so the user installs only ONE app - ours:
- **Tailscale is open source (BSD-3).** We embed its client (tsnet / the Android library) so arxlink
  itself joins the tailnet: free DERP relays, NAT/CGNAT traversal, a stable 100.x address, device
  auth - with no separate Tailscale app. OR embed **wireguard-go** (Apache-2.0) for a plain
  WireGuard tunnel to an owned endpoint. Default: embed Tailscale's client for the free relays.
- ADB binds to the tunnel interface only, never the public internet.

## Footprint (4GB phone, kid games)
- No UI/Activity beyond a tiny Device-Admin receiver and the settings deep-link used during setup.
- One lightweight foreground service; the tunnel client is the only heavy dependency, and Go-based
  WireGuard/Tailscale is a few MB. Target < 15 MB installed, a few MB RAM resident, no wakelock beyond
  the tunnel's keepalive. No Play Services dependency.

## How droidB installs it (one-time, over USB, no root)
A "Set up home remote" button in droidB runs, over one USB connection:
1. `adb install arxlink.apk`
2. `adb shell dpm set-active-admin com.arxos.link/.AdminReceiver`   (unremovable)
3. `adb shell pm grant com.arxos.link android.permission.WRITE_SECURE_SETTINGS`
4. `adb shell dumpsys deviceidle whitelist +com.arxos.link`          (battery-exempt)
5. `adb shell settings put global adb_wifi_enabled 1; adb tcpip 5555`
6. open arxlink once to log it into the tailnet (or load a pre-made WireGuard config)
7. save the phone's 100.x address in droidB as a kept device
After this the cable is never needed again; droidB-link keeps the laptop side connected.

## Build
A real Android app: Android SDK + Gradle (+ NDK for the Go tunnel). Host has build-tools
(apksigner/aapt2/d8). This is a substantial build; this file is the design and the manifest scaffold
is next. NOTHING here is a working APK yet - do not treat it as shipped.

## Samsung caveat
Samsung's Auto Blocker / Knox may still fight a no-root persistent debugger. Device Admin + battery
whitelist covers the app; `adb_wifi_enabled` persistence across reboot is the OEM-dependent part. If
Samsung forces it off, the fallback is the phone not rebooting (battery + cellular through blackouts)
or root for full automation.

## Privilege elevation without root: Device Owner (owner, 2026-11-02)

"Part of the system, safely, without compromising root" = **Device Owner**, Android's built-in,
Google-sanctioned MDM privilege. It is NOT root and does NOT touch the verified-boot / SELinux /
root security model - it is the official way a management app gets near-system power on a stock
device, no root.
- Set over adb, no root: `adb shell dpm set-device-owner com.arxos.link/.AdminReceiver`.
- **Catch:** it can only be set when the device has NO accounts (factory state). The A16 already has
  the kid's accounts, so this needs a ONE-TIME factory reset (or set it on the spare phone before
  adding his accounts), then re-add his games/apps. After that, full no-root control forever.
- What Device Owner grants our app, no root: unremovable, auto-grant its own permissions, exempt
  itself from battery optimization, keep ADB-over-wifi on, install/suspend/hide apps, set app time
  limits and schedules, read usage, enforce policy, lock. This is exactly what parental-control and
  MDM products use. Device Admin (no reset) is the weaker fallback if a reset is not acceptable.

## This is parental control of a minor's device - keep it transparent
The use case is a parent managing and monitoring their own child's device (homework vs games, app
limits, safety from online predators) plus remote access to home devices. That is legitimate. Build
it as TRANSPARENT parental control, not covert surveillance: the child should know the device is
managed (healthiest, and the cleanest legally). The app is a visible "managed by a parent" device,
like Family Link, not hidden stalkerware. (The no-launcher-icon choice is to stop the child DELETING
it, not to hide that management exists - the managed state is shown in Settings.)

## Features this enables (all no-root under Device Owner)
- **Always-on scrcpy over LAN/WAN:** persistent ADB-over-wifi on the tunnel, kept up by the service;
  droidB-link + scrcpy auto-relaunch -> control the phone (and through it the Vidaa TV app) from
  anywhere, same-network or not.
- **Homework vs games:** schedule/suspend game packages during homework hours; allow them after.
- **Safety monitoring (transparent):** app-usage reports via UsageStatsManager; optional content/DNS
  filtering for safer browsing. Prefer pairing with **Google Family Link** (Google-made, no root, no
  reset: downtime, app limits, activity reports, location) for the monitoring/limits, while ArxOS
  Link owns the always-on remote access + home-device control. Do NOT build covert message/keystroke
  capture; that crosses from parental control into stalkerware.
- **Home devices on the router:** once the phone is a reachable node on the tunnel, it bridges to
  other home devices on its LAN.

## Termux / hooking Samsung apps - assessed
- **Termux:** can run a tunnel/sshd on boot (Termux:Boot), but it is a normal app (battery-killed,
  deletable by the kid, heavier). Worse than our Device-Owner app for "unremovable + forever".
- **Hooking into Samsung's system apps:** needs root to modify system apps; rejected (compromises the
  security model the owner wants to keep). Device Owner is the clean, root-free equivalent.

## Device Owner WITHOUT a factory reset (owner: family's data must stay)

`dpm set-device-owner` refuses when accounts exist, but it does NOT need a factory reset - it needs
no ACCOUNTS at the moment it is set. The no-data-loss path:
1. Settings > Accounts > remove each account (Google, Samsung, etc.). This removes ONLY the account
   links. Photos, messages, apps, files, the kid's games - everything stays.
2. `adb shell dpm set-device-owner com.arxos.link/.AdminReceiver`  (no root)
3. Re-add the accounts.
Nothing is wiped. If a stubborn account or an existing device-admin blocks it, remove that admin
first (Settings > Security > Device admin apps). This is the documented no-reset route; verify on the
A16 when its debugging is back.

## Why debugging keeps dying on this A16, and the fix (investigation)
Observed repeatedly this session: USB/wireless debugging turns itself off. Most likely cause on a
recent One UI Samsung: **Auto Blocker** (Settings > Security and privacy > Auto Blocker) - it blocks
USB commands and can disable debugging. Fix path (one-time, no root):
1. **Auto Blocker OFF.** This is almost certainly the main culprit; off, it stops killing ADB.
2. Developer options: USB debugging ON, Wireless debugging ON, tick "Always allow from this computer"
   on the RSA prompt; do not let "Revoke USB debugging authorizations" fire.
3. `adb shell settings put global adb_wifi_enabled 1` (persistent wireless debugging).
4. ArxOS Link (Device Owner) re-asserts adb_wifi_enabled=1 on boot via WRITE_SECURE_SETTINGS, keeps
   itself battery-exempt, and is unremovable - so after any reboot ADB comes back on its own.
Rejected as the primary cause: a plain wireless-debugging reboot reset (would not drop it while still
on USB, which we saw); the kid toggling it (pattern too regular). Confirm by reading Auto Blocker +
adb_wifi_enabled on the device next time it is up.

## NO Google / NO telemetry (owner, firm)
Drop Family Link entirely - it is Google telemetry, the opposite of ArxOS. All parental features are
LOCAL and Google-free:
- app usage: Android's on-device UsageStatsManager (local, no network, no Google).
- game-vs-homework: Device Owner suspends/enables packages on a schedule, on-device.
- safer browsing: a local DNS filter, no cloud account.
Nothing phones home. The app has no analytics. This matches AnonKit's stance.

## Frida and Termux:API - assessed honestly
- **Frida** is dynamic instrumentation; it needs root or a frida-gadget inside a target app. It does
  NOT grant persistent ADB and does NOT bypass Auto Blocker. It is not the persistence mechanism;
  do not sell it as one. (It stays in droidB for its real job: app analysis.)
- **Termux:API app** (termux-sms, termux-location, termux-battery, etc.) + Termux:Boot could run a
  tunnel and device-access scripts on boot with no root - a faster prototype. But Termux is a normal
  app: battery-killable (whitelist helps) and the kid can DELETE it (no Device-Admin protection), and
  it is heavier on a 4GB phone. Use it to prototype the scripting if wanted, but ArxOS Link as a
  Device-Owner/Admin app is the durable, unremovable answer. Not a Google dependency either.

## DECISION (owner, 2026-11-02): Termux path, no account removal, no root, no Google

The owner will NOT remove accounts or reset. So the primary path is Termux (all from F-Droid, open
source, zero Google/telemetry), not Device Owner. Device Owner stays a future option for the
permanent replacement device (set before accounts are added, so no removal needed there).

### What Termux gives, no-root, no-reset, persistent across reboots/blackouts
- **Termux + Termux:Boot + Termux:API** (F-Droid). Battery-exempt via adb
  (`dumpsys deviceidle whitelist +com.termux`), granted `WRITE_SECURE_SETTINGS` via adb once.
- **Tunnel:** Tailscale in Termux, userspace (`tailscaled --tun=userspace-networking`), no root. Stable
  100.x address reachable over Wi-Fi AND cellular, so the phone is reachable at home, at grandma's,
  or anywhere the kid goes. Termux:Boot restarts it after a reboot.
- **Boot persistence:** arxlink-boot.sh (written) runs on boot: wake-lock, re-enable wireless
  debugging, start the tunnel. Survives blackouts (phone's own battery + cellular keep it up; a real
  reboot is recovered by the boot script).
- **Monitoring the kid safely when he is out, and anti-theft if the phone is taken/lost** (legitimate
  for a parent's minor child): Termux:API scripts over the tunnel — `termux-location` (where is the
  phone / the kid), `termux-battery-status`, app usage via `dumpsys usagestats` (local, no Google),
  and scrcpy to see the screen. If taken/misplaced: locate it, see it, sound it. All local + over the
  owned tunnel, no third-party tracking service. Keep it transparent (the child knows the phone is
  parent-managed).
- **Multiple home devices:** the setup is per-device and droidB's device registry
  (~/.config/droidB/devices.json) already holds many kept devices; the picker selects among them.
  setup-homelink.sh takes a serial, so repeat it per phone. Works for the A16 now and the permanent
  device later, side by side.

### The one honest nuance: scrcpy's fixed port after a reboot
scrcpy needs an ADB connection. `adb tcpip 5555` gives a FIXED port but it resets on reboot, and
pinning it permanently needs root. `settings adb_wifi_enabled=1` persists (and the boot script
re-sets it) but Android 11+ then uses a DYNAMIC wireless-debug port. So after a genuine reboot the
port can change. Handling, no root:
- The phone is a plugged-in, battery-backed home server, so it rarely truly reboots (blackouts do not
  reboot it — cellular + battery carry it), and a held session just stays up.
- On a real reboot, arxlink-boot.sh re-enables wireless debugging; a small helper in Termux reads the
  current adb port and publishes it over the tunnel (a file droidB reads, or mDNS which Tailscale can
  carry), and droidB reconnects to 100.x:<port> automatically.
- Bulletproof fixed-port-across-reboot is the one thing that is clean only with root/Device Owner; on
  the permanent device, Device Owner (set with no accounts, no removal) makes even this automatic.
So: monitoring, tunnel, anti-theft, multi-device = fully no-root now. scrcpy after a rare real reboot
needs the port-republish helper (buildable) or root on the permanent device.

### Files (scaffold, not yet device-verified)
- arxlink-boot.sh — Termux:Boot script (syntax-checked).
- setup-homelink.sh <serial> — one-time USB setup driver (syntax-checked): battery whitelist, grant,
  push boot script, enable wireless ADB, print the one-time reminders.
- To build: the Termux port-republish helper, droidB auto-discovery of the republished port, and the
  droidB "Set up home remote" button that runs setup-homelink.sh and guides the F-Droid installs.
