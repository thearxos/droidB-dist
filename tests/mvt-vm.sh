#!/bin/sh
# Run only in the disposable initramfs VM; all engines/devices below are mocks.
set -eu
if ! grep -q 'droidb_test_vm=1' /proc/cmdline; then
    echo 'Refusing: requires the disposable droidB regression VM' >&2
    exit 1
fi
mkdir -p /tmp/mvt-test/bin /tmp/mvt-test/input
export HOME=/tmp/mvt-test/home
export PATH=/tmp/mvt-test/bin:/usr/bin:/bin
CLI=/test/droidb-cli
cat > /tmp/mvt-test/bin/mvt-android <<'MOCK'
#!/bin/sh
out=''
while [ "$#" -gt 0 ]; do
    case "$1" in --output) shift; out=$1;; esac
    shift
done
[ -n "$out" ] || exit 0
case "${MVT_MOCK_CASE:-ok}" in
  fail) printf '[]' > "$out/alerts.json"; exit 7;;
  empty) exit 0;;
  corrupt) printf '{' > "$out/alerts.json"; exit 0;;
  match) printf '[{"module":"sms","matched_indicator":{"value":"example.invalid"}}]' > "$out/alerts.json";;
  *) printf '[]' > "$out/alerts.json"; printf '[]' > "$out/sms.json";;
esac
MOCK
chmod +x /tmp/mvt-test/bin/mvt-android
expect_fail() {
    if "$@" > /tmp/last-output 2>&1; then cat /tmp/last-output; echo 'Unexpected success'; exit 1; fi
    if grep -q 'no spyware indicators matched' /tmp/last-output; then cat /tmp/last-output; exit 1; fi
}
expect_fail "$CLI" mvt report /tmp/mvt-test/missing
: > /tmp/mvt-test/empty.ab
expect_fail "$CLI" mvt backup /tmp/mvt-test/empty.ab --out /tmp/mvt-test/out-empty-input
for mode in fail empty corrupt; do
    export MVT_MOCK_CASE=$mode
    expect_fail "$CLI" mvt androidqf /tmp/mvt-test/input --out "/tmp/mvt-test/out-$mode"
    expect_fail "$CLI" mvt report "/tmp/mvt-test/out-$mode"
done
export MVT_MOCK_CASE=ok
: > /tmp/mvt-test/input/backup.ab
"$CLI" mvt androidqf /tmp/mvt-test/input --out /tmp/mvt-test/out-ok > /tmp/last-output
grep -q 'backup.ab is empty' /tmp/last-output
grep -q 'no spyware indicators matched' /tmp/last-output
expect_fail "$CLI" mvt androidqf /tmp/mvt-test/input --out /tmp/mvt-test/out-ok
"$CLI" mvt report /tmp/mvt-test/out-ok > /tmp/last-output
grep -q 'no spyware indicators matched' /tmp/last-output
export MVT_MOCK_CASE=match
"$CLI" mvt androidqf /tmp/mvt-test/input --out /tmp/mvt-test/out-match > /tmp/last-output
grep -q '1 detection(s)' /tmp/last-output
echo 'MVT_CLI_REGRESSIONS_PASS'
# Cleanup is simulated. A fake exit-zero Failure must stop before uninstall.
cat > /tmp/mvt-test/bin/adb <<'MOCK'
#!/bin/sh
shift 3
cmd=$1
printf '%s\n' "$cmd" >> /tmp/cleanup-commands
case "$cmd" in
  'dumpsys device_policy') exit 0;;
  'settings get secure enabled_accessibility_services'|'settings get secure enabled_notification_listeners') printf 'null\n';;
  'which su || command -v su || true') printf '/system/bin/su\n';;
  'pm list packages -s com.example') exit 0;;
  'dumpsys package com.example')
    printf '  runtime permissions:\n'
    if [ ! -f /tmp/permission-revoked ]; then printf '    android.permission.CAMERA: granted=true\n'; fi;;
  'pm revoke --user 0 com.example android.permission.CAMERA') : > /tmp/permission-revoked;;
  'pm clear com.example') printf 'Failure [MOCK_DENIED]\n';;
  *) printf 'Error: unexpected mock command\n'; exit 1;;
esac
MOCK
chmod +x /tmp/mvt-test/bin/adb
expect_fail "$CLI" clean app com.example --serial MOCK --evidence-saved --i-understand-they-will-notice
grep -q 'pm revoke --user 0 com.example android.permission.CAMERA' /tmp/cleanup-commands
if grep -q 'reset-permissions\|pm uninstall' /tmp/cleanup-commands; then cat /tmp/cleanup-commands; exit 1; fi
expect_fail "$CLI" clean app com.example --serial MOCK --purge-messages --evidence-saved --i-understand-they-will-notice
echo 'CLEANUP_CLI_REGRESSIONS_PASS'
