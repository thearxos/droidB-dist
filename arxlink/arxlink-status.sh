#!/data/data/com.termux/files/usr/bin/sh
# arxlink-status.sh — serve the device's status as JSON over the tunnel so droidB can show "what is
# the phone doing" at a glance (transparent parental monitoring of a minor's own device, over the
# parent's own tunnel, no Google, no cloud). Run from Termux:Boot. Fixed status port: 8098.
# Reports: screen on/off, foreground app, recent app usage, battery, and (when granted) location.
export PATH=/data/data/com.termux/files/usr/bin:$PATH
PORT=8098

json() {
  scr=$(dumpsys power 2>/dev/null | grep -m1 -oE "mWakefulness=[A-Za-z]+" | cut -d= -f2)
  fg=$(dumpsys activity activities 2>/dev/null | grep -m1 -oE "topResumedActivity=.*\{[^ ]* [^ ]* [^/]*/[^ }]*" | grep -oE "[a-zA-Z0-9_.]+/[a-zA-Z0-9_.]+" | head -1)
  bat=$(termux-battery-status 2>/dev/null | tr -d '\n' | sed 's/  */ /g')
  [ -n "$bat" ] || bat="{}"
  # app usage today (local UsageStats via dumpsys, no Google)
  usage=$(dumpsys usagestats 2>/dev/null | grep -oE "package=[a-zA-Z0-9_.]+ totalTime=[0-9]+" | head -20 | sed 's/.*/"&"/' | paste -sd, -)
  # location only if the parent granted it (termux-location); may be slow, so time-limited
  loc=$(timeout 15 termux-location -p network 2>/dev/null | tr -d '\n' | sed 's/  */ /g')
  [ -n "$loc" ] || loc="{}"
  printf '{"screen":"%s","foreground":"%s","battery":%s,"location":%s,"usage":[%s]}\n' \
    "${scr:-unknown}" "${fg:-unknown}" "$bat" "$loc" "${usage:-}"
}

while :; do
  BODY=$(json)
  printf 'HTTP/1.0 200 OK\r\nContent-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\n\r\n%s' "$BODY" | nc -l -p "$PORT" >/dev/null 2>&1 || sleep 2
done
