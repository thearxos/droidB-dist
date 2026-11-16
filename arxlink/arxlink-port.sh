#!/data/data/com.termux/files/usr/bin/sh
# arxlink-port.sh — serve the device's CURRENT wireless-ADB port on a fixed port over the tunnel, so
# droidB always knows where to connect even though Android 11+ changes the adb-wifi port each boot.
# No root. Run from Termux:Boot after the tunnel + adb-wifi are up. Fixed discovery port: 8099.
export PATH=/data/data/com.termux/files/usr/bin:$PATH
DISCOVERY_PORT=8099
getport() {
  # the live wireless-debug port: try the TLS adb port prop, then the classic tcp port prop
  p=$(getprop service.adb.tls.port 2>/dev/null)
  [ -n "$p" ] && [ "$p" != "0" ] || p=$(getprop service.adb.tcp.port 2>/dev/null)
  [ -n "$p" ] && [ "$p" != "0" ] || p=5555
  echo "$p"
}
# a tiny loop server: every request gets the current adb port. droidB reads http://100.x:8099/
while :; do
  PORT=$(getport)
  # one-shot responder with nc (busybox nc in Termux); re-arm each request
  printf 'HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\n\r\n%s\n' "$PORT" | nc -l -p "$DISCOVERY_PORT" >/dev/null 2>&1 || sleep 2
done
