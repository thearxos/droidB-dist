#!/usr/bin/env bash
D=$(cd "$(dirname "$0")" && pwd); S=""; [ "$(id -u)" -ne 0 ] && S=sudo
for f in droidB-gui droidB-samsung droidB-mod droidB-rescue droidB-adb droidB; do [ -f "$D/$f" ] && $S install -Dm755 "$D/$f" /usr/local/bin/$f; done
# curated OEM/Samsung bloatware list (383 pkgs) that the Debloat panel exact-matches
[ -f "$D/samsung-bloat.txt" ] && $S install -Dm644 "$D/samsung-bloat.txt" /usr/share/droidB/samsung-bloat.txt
$S install -Dm644 /dev/stdin /usr/share/applications/droidB.desktop <<DESK
[Desktop Entry]
Type=Application
Name=droidB
GenericName=Android Toolkit
Comment=ARXOS Android toolkit (ADB, fastboot, flashing, root/ROM)
Exec=droidB-gui
Icon=phone
Terminal=false
Categories=System;Utility;
DESK
# udev rule so droidB talks to a phone without root (plugdev + uaccess for the active session).
# The rule lives in data/ in both the source tree and droidB-dist; the top level is kept as a
# fallback for older layouts. This used to test only the top level, so every install silently
# skipped the rule and nothing said so. A missing rule is now reported, because without it a
# phone is only reachable as root and that looks like a driver fault rather than a packaging one.
UDEV_RULE=""
for _c in "$D/data/51-droidB-android.rules" "$D/51-droidB-android.rules"; do
    [ -f "$_c" ] && { UDEV_RULE=$_c; break; }
done
if [ -z "$UDEV_RULE" ]; then
    echo "warning: 51-droidB-android.rules not found beside install.sh or in data/; phones will need root until it is installed."
else
    $S install -Dm644 "$UDEV_RULE" /etc/udev/rules.d/51-droidB-android.rules
    $S getent group plugdev >/dev/null 2>&1 || $S groupadd plugdev 2>/dev/null || true
    $S usermod -aG plugdev "${SUDO_USER:-$USER}" 2>/dev/null || true
    $S udevadm control --reload 2>/dev/null || true
    $S udevadm trigger 2>/dev/null || true
    echo "udev rule installed (re-plug the phone, or re-login, for non-root access)"
fi
# All device drivers, so a fresh install talks to Android AND iPhone with nothing
# else to add. Android: android-tools (adb/fastboot). iPhone: libimobiledevice
# (idevice_id/ideviceinfo/idevicebackup2), usbmuxd (the USB muxer every iOS tool
# talks through), ifuse (mount an iPhone's files). mvt is the spyware scanner the
# Spyware Scan panel drives. droidB also self-heals these on demand via `mvt setup`,
# but installing them here means the first scan does not stop to fetch a driver.
$S pacman -S --noconfirm --needed \
    android-tools libimobiledevice usbmuxd ifuse mvt >/dev/null 2>&1 || \
    echo "note: some device drivers could not be installed automatically; run 'droidB mvt setup' or install: android-tools libimobiledevice usbmuxd ifuse mvt"

# usbmuxd must be running or no iPhone is ever seen. It is socket-activated on most
# systems; enable it so a plugged-in iPhone is picked up without a manual start.
if command -v systemctl >/dev/null 2>&1; then
    $S systemctl enable --now usbmuxd.service >/dev/null 2>&1 || \
    $S systemctl enable --now usbmuxd.socket  >/dev/null 2>&1 || true
fi
# Everything below comes from the droidB-dist release: compiled artifacts whose Rust
# source is private. Each one is checksum-verified before it is installed, and a failed
# fetch never leaves a half-broken install -- the bash toolkit above already works.
DIST="https://github.com/thearxos/droidB-dist/releases/latest/download"

# Fetch one release asset, verify it against its published .sha256, install it.
# Returns non-zero (quietly) on any failure so the caller decides what to say: a
# missing download must never abort the install, because the bash toolkit already
# works by this point. An asset that downloads but fails its checksum is dropped,
# not installed -- a wrong binary is worse than an absent one.
#
# When arx installs droidB it ships the binaries INSIDE its R2 archive, next to this
# script, so no download is needed and nothing depends on GitHub. Those copies are
# checked exactly like downloaded ones: against their own .sha256, after being copied
# to a private temp file, so the bytes that are hashed are the bytes that get installed.
fetch_asset() {
    _name=$1; _dest=$2
    _t=$(mktemp) || _t=/tmp/$_name.$$
    _rc=1; _have=0
    if [ -f "$D/$_name" ] && [ -f "$D/$_name.sha256" ]; then
        cp -- "$D/$_name" "$_t" && cp -- "$D/$_name.sha256" "$_t.sha" && _have=1
    elif command -v curl >/dev/null 2>&1; then
        curl -fsSL "$DIST/$_name" -o "$_t" && curl -fsSL "$DIST/$_name.sha256" -o "$_t.sha" 2>/dev/null && _have=1
    fi
    if [ "$_have" = 1 ]; then
        _want=$(awk '{print $1}' "$_t.sha")
        _got=$(sha256sum "$_t" | awk '{print $1}')
        if [ -n "$_want" ] && [ "$_want" = "$_got" ]; then
            $S install -Dm755 "$_t" "$_dest" && _rc=0
        else
            echo "warning: $_name checksum did not match; skipped."
            _rc=2
        fi
    fi
    rm -f "$_t" "$_t.sha" 2>/dev/null || true
    return $_rc
}

# The native engine ships as a compiled release asset, not source (its Rust source
# is private). It carries what the bash toolkit does not: the Spyware Scan, the fleet
# queue, deep clean, root detection, and Samsung flashing with libodin4 linked in.
# rc 2 means the download arrived but its checksum was wrong, which fetch_asset has
# already reported. Do not follow that with "offline?", because a bad checksum is a
# corrupted or tampered file, not a network problem, and saying otherwise buries it.
fetch_asset droidB-native /usr/local/bin/droidB-native; _r=$?
if [ "$_r" -eq 0 ]; then
    echo "droidB native engine installed (Spyware Scan, fleet, clean, flashing)"
elif [ "$_r" -ne 2 ]; then
    echo "note: could not fetch the droidB native engine (offline?). The bash toolkit is installed; re-run install.sh to get it."
fi

# The native GUI (Tauri) ships as an AppImage because it needs its webview bundle
# alongside the binary. It drives droidB-native above, which is why it is fetched
# second: the engine is on PATH by the time the GUI can look for it.
fetch_asset droidB-gui-native.AppImage /usr/local/lib/droidB/droidB-gui-native.AppImage; _r=$?
if [ "$_r" -eq 0 ]; then
    # An AppImage normally self-mounts through FUSE. Rather than make FUSE a hard
    # requirement, launch through a wrapper that falls back to extract-and-run, so
    # the GUI still starts on a system without fuse2 (containers, minimal installs).
    $S install -Dm755 /dev/stdin /usr/local/bin/droidB-gui-native <<'WRAP'
#!/usr/bin/env bash
A=/usr/local/lib/droidB/droidB-gui-native.AppImage
# An AppImage self-mounts through libfuse2. Probe for it rather than trying and
# falling back: once exec replaces this shell, a non-zero exit can no longer be
# caught, so the decision has to be made before launching.
if ldconfig -p 2>/dev/null | grep -q 'libfuse\.so\.2'; then exec "$A" "$@"; fi
exec env APPIMAGE_EXTRACT_AND_RUN=1 "$A" "$@"
WRAP
    $S install -Dm644 /dev/stdin /usr/share/applications/droidB-native.desktop <<DESK
[Desktop Entry]
Type=Application
Name=droidB (Native)
GenericName=Android and iOS Toolkit
Comment=Spyware Scan, fleet scanning, deep clean, flashing
Exec=droidB-gui-native
Icon=phone
Terminal=false
Categories=System;Security;Utility;
DESK
    echo "droidB native GUI installed (run: droidB-gui-native)"
elif [ "$_r" -ne 2 ]; then
    echo "note: the native GUI was not installed; the Python GUI (droidB-gui) and CLI still work."
fi

echo "droidB installed"
