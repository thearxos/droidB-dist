#!/data/data/com.termux/files/usr/bin/sh
# arxlink-find.sh — anti-theft responder served over the tunnel (fixed port 8097). On GET /locate it
# returns the phone's location; on GET /ring it sounds a full-volume alert. Legitimate find-my-device
# for the owner's own phone. Run from Termux:Boot.
export PATH=/data/data/com.termux/files/usr/bin:$PATH
PORT=8097
handle() {
  req=$(head -1)
  case "$req" in
    *GET\ /locate*) timeout 20 termux-location -p gps 2>/dev/null || timeout 15 termux-location -p network 2>/dev/null || echo '{}' ;;
    *GET\ /ring*)   ( termux-volume music 15 2>/dev/null; termux-media-player play /system/media/audio/ringtones/*.ogg 2>/dev/null; sleep 20; termux-media-player stop 2>/dev/null ) & echo "ringing" ;;
    *) echo "usage: /locate or /ring" ;;
  esac
}
while :; do
  BODY=$( { handle; } )
  printf 'HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n%s' "$BODY" | nc -l -p "$PORT" >/dev/null 2>&1 || sleep 2
done
