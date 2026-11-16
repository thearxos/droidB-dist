#!/usr/bin/env bash
# setup-homelink.sh [serial] — ONE TAP to turn an Android phone into a persistent home node for
# droidB. NO ROOT, NO ACCOUNT REMOVAL, NO FACTORY RESET, NO GOOGLE. Run once with the phone on USB
# and debugging on; everything else is automatic:
#   - installs Termux, Termux:API, Termux:Boot (open source, from F-Droid, one signing key)
#   - grants the permissions they need (storage, boot, keep-alive, remote control)
#   - exempts them from battery optimisation so the tunnel never gets killed
#   - runs the in-Termux bootstrap (tailscale free tunnel + boot scripts) without a cable
#   - HIDES the launcher icons (pm disable-user) so the child cannot open or uninstall them, while
#     the boot receiver and background services keep running
#   - turns on wireless debugging so droidB reconnects over LAN/WAN after this
#
# The three APKs must share ONE signing key or the addons refuse to talk to Termux, so all come from
# F-Droid at pinned versions and every download is sha256-checked before it is installed.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
S="${1:-}"; A=(adb); [ -n "$S" ] && A=(adb -s "$S")
say(){ printf '  %s\n' "$*"; }
warn(){ printf '  ! %s\n' "$*"; }

# --- the APK pack: pinned version + sha256; bundled copy wins, else fetched + verified, then cached
TERMUX_VER=1002; TERMUX_API_VER=1002; TERMUX_BOOT_VER=1000
declare -A SHA=(
  [com.termux_1002.apk]="e6265a57eb5ca363808488e3b01955958bed93bc0c8a0d281849b363b11027ec"
  [com.termux.api_1002.apk]="4497dbbf81906df52e59ed387a5223d225aa0de3aca817cc557a621e4dadda44"
  [com.termux.boot_1000.apk]="6f7cf9b94f539d3efd4af3544ff819947b49395275d8cfa7e5f80de14f3d9cf8"
)
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/arxos/homelink"
PACK_DIRS=("$HERE/apks" "/usr/share/droidB/homelink" "$CACHE")
mkdir -p "$CACHE"

# locate a verified APK, downloading it once if no bundled/cached copy matches its pinned hash
apk_path(){
  local name="$1" want="${SHA[$1]}" d got
  for d in "${PACK_DIRS[@]}"; do
    [ -f "$d/$name" ] || continue
    got=$(sha256sum "$d/$name" | awk '{print $1}')
    [ "$got" = "$want" ] && { printf '%s\n' "$d/$name"; return 0; }
  done
  # not present (or hash mismatch): fetch once into the cache and verify against the pin. The ArxOS
  # R2 mirror is tried first (fast on the owner's link); F-Droid is the authoritative fallback. The
  # sha256 check is identical for both, so the mirror can never serve a different binary.
  local base r2="https://pub-d5ff3efb1d204998aa120ded02d070b9.r2.dev/tools/droidB/homelink"
  for base in "$r2" "https://f-droid.org/repo"; do
    say "fetching $name ($base, one time)…" >&2
    curl -fsSL -o "$CACHE/$name" "$base/$name" || continue
    got=$(sha256sum "$CACHE/$name" | awk '{print $1}')
    [ "$got" = "$want" ] && { printf '%s\n' "$CACHE/$name"; return 0; }
    warn "$name from $base failed its checksum; trying the next source" >&2
  done
  rm -f "$CACHE/$name"; warn "could not get a verified $name" >&2; return 1
}

say "checking the phone is reachable…"
"${A[@]}" get-state >/dev/null 2>&1 || { echo "no device over adb; connect USB with debugging on"; exit 1; }
MODEL=$("${A[@]}" shell getprop ro.product.model 2>/dev/null | tr -d '\r')
say "device: ${MODEL:-unknown}"

say "1/8 installing Termux, Termux:API, Termux:Boot (verified, one key)…"
for name in "com.termux_${TERMUX_VER}.apk" "com.termux.api_${TERMUX_API_VER}.apk" "com.termux.boot_${TERMUX_BOOT_VER}.apk"; do
  p=$(apk_path "$name") || { warn "skipped $name"; continue; }
  # -r reinstall keeping data, -g grant runtime permissions at install
  out=$("${A[@]}" install -r -g "$p" 2>&1) && say "   installed ${name%_*}" || {
    # a differently-signed older copy already on the phone blocks the install; say so plainly
    echo "$out" | grep -qi 'signatures do not match' \
      && warn "   ${name%_*}: a different build is already installed. Uninstall it first (keep ONE source)." \
      || warn "   ${name%_*}: install failed: $(echo "$out" | tail -1)"
  }
done

say "2/8 storage access for Termux (so it can read the boot scripts, no dialog)"
"${A[@]}" shell appops set com.termux MANAGE_EXTERNAL_STORAGE allow >/dev/null 2>&1 \
  && say "   storage granted" || warn "   could not grant storage; termux-setup-storage will ask once"

say "3/8 permissions: re-enable wireless debugging on boot, and let droidB drive Termux"
"${A[@]}" shell pm grant com.termux android.permission.WRITE_SECURE_SETTINGS >/dev/null 2>&1 \
  && say "   WRITE_SECURE_SETTINGS granted" || warn "   grant failed (is Termux the F-Droid build?)"
"${A[@]}" shell pm grant com.termux com.termux.permission.RUN_COMMAND >/dev/null 2>&1 || true

say "4/8 battery: exempt Termux so the OS never kills the tunnel"
"${A[@]}" shell dumpsys deviceidle whitelist +com.termux >/dev/null 2>&1 \
  && say "   Termux battery-whitelisted" || warn "   set Termux to Unrestricted in Settings > Battery"

say "5/8 pushing the boot + monitor scripts to the phone"
for f in arxlink-boot.sh arxlink-port.sh arxlink-status.sh arxlink-find.sh arxlink-bootstrap.sh; do
  "${A[@]}" push "$HERE/$f" "/sdcard/$f" >/dev/null 2>&1 && say "   pushed $f"
done

say "6/8 first-run setup inside Termux (tailscale tunnel + boot scripts), no cable needed after this"
"${A[@]}" shell am start -n com.termux/.app.TermuxActivity >/dev/null 2>&1
say "   waiting for Termux to initialise…"; sleep 25
# type the one bootstrap command into the Termux terminal and run it (first run only; afterwards
# droidB drives Termux remotely through the RUN_COMMAND permission granted above)
BOOT_CMD="bash /sdcard/arxlink-bootstrap.sh"
[ -n "${ARXLINK_TS_AUTHKEY:-}" ] && BOOT_CMD="ARXLINK_TS_AUTHKEY=${ARXLINK_TS_AUTHKEY} $BOOT_CMD"
"${A[@]}" shell input text "$(printf '%s' "$BOOT_CMD" | sed 's/ /%s/g')" >/dev/null 2>&1
"${A[@]}" shell input keyevent 66 >/dev/null 2>&1
say "   bootstrap started in Termux; it installs tailscale and the boot scripts (give it a minute)"

say "7/8 hiding the Termux launcher icons (background stays running)"
for comp in com.termux/.app.TermuxActivity com.termux.boot/.BootActivity com.termux.api/.TermuxAPIActivity; do
  "${A[@]}" shell pm disable-user --user 0 "$comp" >/dev/null 2>&1 && say "   hid $comp" || true
done

say "8/8 turning on wireless debugging (persists)"
"${A[@]}" shell settings put global adb_wifi_enabled 1 >/dev/null 2>&1
"${A[@]}" tcpip 5555 >/dev/null 2>&1 && say "   wireless ADB on (port 5555)"
IP=$("${A[@]}" shell ip -f inet addr show wlan0 2>/dev/null | grep -o 'inet [0-9.]*' | awk '{print $2}')
[ -n "$IP" ] && say "   LAN address for a first test: ${IP}:5555"

echo
say "one-time, outside this script (phone screen):"
say "  - Settings > Security and privacy > Auto Blocker: OFF (it kills USB/ADB otherwise)"
[ -z "${ARXLINK_TS_AUTHKEY:-}" ] && say "  - finish the tailscale login once (a URL was printed in Termux), or re-run with ARXLINK_TS_AUTHKEY=<key>"
say "then add the phone's tailscale address in droidB (Screen > Connect, Keep connected). The cable is no longer needed."
