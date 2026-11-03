#!/data/data/com.termux/files/usr/bin/bash
# arxlink-bootstrap.sh — runs ONCE inside Termux on the home phone, driven by setup-homelink.sh over
# USB. It finishes everything that has to happen inside Termux: the packages, the boot scripts, the
# free tunnel, and the setting that lets droidB drive Termux remotely afterwards. NO ROOT.
#
# Everything here is open source and has no Google dependency. It is idempotent: running it again
# repairs a half-done setup rather than doubling anything.
set -u
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
HOME="${HOME:-/data/data/com.termux/files/home}"
BOOT="$HOME/.termux/boot"
log(){ printf 'arxlink: %s\n' "$*"; }

# An auth key lets the tunnel come up with no browser. setup-homelink.sh passes it in the environment
# (ARXLINK_TS_AUTHKEY) when the parent supplied one; without it, tailscale prints a login URL once.
AUTHKEY="${ARXLINK_TS_AUTHKEY:-}"

log "1/5 storage access (so the boot scripts can be read from /sdcard)"
yes | termux-setup-storage >/dev/null 2>&1 || true
sleep 2

log "2/5 packages: tailscale (free WireGuard tunnel), openssh, termux-api"
pkg update -y >/dev/null 2>&1 || log "   (pkg update could not reach a mirror; retrying install anyway)"
pkg install -y tailscale openssh termux-api termux-services >/dev/null 2>&1 \
  && log "   installed" || log "   WARNING: a package did not install; re-run when the phone has internet"

log "3/5 boot scripts into Termux:Boot (run on every power-on, survives blackouts)"
mkdir -p "$BOOT"
for f in arxlink-boot.sh arxlink-port.sh arxlink-status.sh arxlink-find.sh; do
  for src in "/sdcard/$f" "/sdcard/Download/$f" "$HOME/storage/shared/$f"; do
    [ -f "$src" ] && { cp "$src" "$BOOT/$f"; chmod +x "$BOOT/$f"; log "   installed $f"; break; }
  done
done

log "4/5 let droidB drive Termux remotely (so future changes need no cable)"
mkdir -p "$HOME/.termux"
props="$HOME/.termux/termux.properties"
touch "$props"
grep -q '^allow-external-apps' "$props" 2>/dev/null \
  && sed -i 's/^allow-external-apps.*/allow-external-apps = true/' "$props" \
  || printf 'allow-external-apps = true\n' >> "$props"

log "5/5 bring the tunnel up now"
# userspace networking needs no root or VPN permission dialog
pgrep -f 'tailscaled' >/dev/null 2>&1 || \
  (tailscaled --tun=userspace-networking --socks5-server=localhost:1055 >/dev/null 2>&1 &)
sleep 3
if [ -n "$AUTHKEY" ]; then
  tailscale up --authkey="$AUTHKEY" --hostname=arxlink-phone --ssh >/dev/null 2>&1 \
    && log "   tunnel up (authkey)" || log "   tunnel auth failed; check the key"
else
  log "   run 'tailscale up --hostname=arxlink-phone --ssh' and open the printed URL once to log in"
  tailscale up --hostname=arxlink-phone --ssh 2>&1 | grep -i 'https://login' || true
fi

ADDR="$(tailscale ip -4 2>/dev/null | head -1)"
[ -n "$ADDR" ] && log "DONE. Tunnel address: $ADDR  (add it in droidB: Screen > Connect, Keep connected)" \
  || log "DONE inside Termux. Finish the tailscale login, then note 'tailscale ip -4' in droidB."
