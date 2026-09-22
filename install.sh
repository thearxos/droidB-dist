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
# udev rule so droidB talks to a phone without root (plugdev + uaccess for the active session)
if [ -f "$D/51-droidB-android.rules" ]; then
    $S install -Dm644 "$D/51-droidB-android.rules" /etc/udev/rules.d/51-droidB-android.rules
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
echo "droidB installed"
