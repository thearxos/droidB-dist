#!/data/data/com.termux/files/usr/bin/sh
# arxlink-boot.sh — runs on device boot via Termux:Boot (no root, no Google).
# Place at ~/.termux/boot/arxlink-boot.sh (chmod +x). It brings the phone back as a reachable home
# node after a reboot/blackout: holds a wake-lock, starts the Tailscale tunnel in userspace, and
# re-enables wireless debugging so droidB can reach adb/scrcpy over LAN/WAN.

export PATH=/data/data/com.termux/files/usr/bin:$PATH
LOG="$HOME/arxlink-boot.log"
echo "$(date) arxlink boot start" >> "$LOG"

# 1. keep the CPU awake so the tunnel and adb stay up while the screen is off (Termux:API)
termux-wake-lock 2>>"$LOG" || true

# 2. persistent wireless debugging. Needs WRITE_SECURE_SETTINGS granted to Termux ONCE over adb:
#    adb shell pm grant com.termux android.permission.WRITE_SECURE_SETTINGS
settings put global adb_wifi_enabled 1 2>>"$LOG" || echo "$(date) could not set adb_wifi_enabled (grant WRITE_SECURE_SETTINGS to com.termux)" >> "$LOG"

# 3. start the tunnel in userspace (no root). Tailscale gives a stable 100.x address reachable over
#    Wi-Fi or cellular, so the phone is reachable at home, at grandma's, anywhere.
if command -v tailscaled >/dev/null 2>&1; then
    pgrep -f "tailscaled" >/dev/null 2>&1 || \
      nohup tailscaled --tun=userspace-networking --statedir="$HOME/.tailscale" >>"$LOG" 2>&1 &
    sleep 3
    tailscale up --hostname="$(getprop ro.product.model | tr ' ' '-')" >>"$LOG" 2>&1 || true
    IP=$(tailscale ip -4 2>/dev/null | head -1)
    echo "$(date) tailscale ip $IP" >> "$LOG"
fi
# 4. start the tunnel-served helpers (port republish, status, find) if present
for h in arxlink-port.sh arxlink-status.sh arxlink-find.sh; do
    if [ -x "$HOME/.termux/boot/$h" ]; then
        pgrep -f "$h" >/dev/null 2>&1 || nohup "$HOME/.termux/boot/$h" >>"$LOG" 2>&1 &
    fi
done
echo "$(date) arxlink boot done" >> "$LOG"
