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
# Root inspection and cleanup are simulated. Unexpected adb calls are test failures.
: > /tmp/unexpected-adb
cat > /tmp/mvt-test/bin/adb <<'MOCK'
#!/bin/sh
if [ "$#" -ne 4 ] || [ "$1" != '-s' ] || [ "$2" != MOCK ] || [ "$3" != shell ]; then
    printf 'Unexpected adb arguments\n' >> /tmp/unexpected-adb
    exit 1
fi
cmd=$4
printf '%s\n' "$cmd" >> /tmp/cleanup-commands
case "$cmd" in
  'dumpsys device_policy') exit 0;;
  'settings get secure enabled_accessibility_services'|'settings get secure enabled_notification_listeners') printf 'null\n';;
  'echo SU='*'echo DROIDB_PROBE_END=ok')
    case "${ROOT_MOCK_CASE:-unrooted}" in
      offline|unauthorized) printf 'error: device %s\n' "$ROOT_MOCK_CASE" >&2; exit 1;;
      empty) exit 0;;
      legacy-error) printf 'Error: unexpected mock command\n'; exit 1;;
      truncated) printf 'SU=/system/bin/su\nMB=/sbin/magisk\n'; exit 0;;
      unrooted|completed-nonzero)
        printf 'SU=\nMB=\nMV=\nMD=\nMM=0\nKSU=\nMNT=0\nTAGS=release-keys\nDBG=0\nSEL=Enforcing\nPKG=\n';;
      rooted)
        printf 'SU=/system/bin/su\nMB=/sbin/magisk\nMV=27.0\nMD=yes\nMM=2\nKSU=\nMNT=3\nTAGS=release-keys\nDBG=0\nSEL=Enforcing\nPKG=package:com.topjohnwu.magisk\n';;
      *) printf 'Unknown root fixture\n' >> /tmp/unexpected-adb; exit 1;;
    esac
    printf 'DROIDB_PROBE_END=ok\n'
    if [ "${ROOT_MOCK_CASE:-unrooted}" = completed-nonzero ]; then
        printf 'error: transport failed after output\n' >&2
        exit 7
    fi;;
  'pm list packages -s com.example') exit 0;;
  'dumpsys package com.example')
    printf '  runtime permissions:\n'
    if [ ! -f /tmp/permission-revoked ]; then printf '    android.permission.CAMERA: granted=true\n'; fi;;
  'pm revoke --user 0 com.example android.permission.CAMERA') : > /tmp/permission-revoked;;
  'pm clear com.example') printf 'Failure [MOCK_DENIED]\n';;
  *) printf '%s\n' "$cmd" >> /tmp/unexpected-adb; printf 'Error: unexpected mock command\n'; exit 1;;
esac
MOCK
chmod +x /tmp/mvt-test/bin/adb

export ROOT_MOCK_CASE=unrooted
"$CLI" clean inspect --serial MOCK > /tmp/last-output 2>&1
grep -q 'no root signals' /tmp/last-output
if grep -q 'root check did not complete\|rooted via' /tmp/last-output; then cat /tmp/last-output; exit 1; fi
export ROOT_MOCK_CASE=rooted
"$CLI" clean inspect --serial MOCK > /tmp/last-output 2>&1
grep -q 'rooted via' /tmp/last-output
grep -q 'Magisk 27.0' /tmp/last-output
if grep -q 'root check did not complete\|no root signals' /tmp/last-output; then cat /tmp/last-output; exit 1; fi
for mode in offline unauthorized empty legacy-error truncated completed-nonzero; do
    export ROOT_MOCK_CASE=$mode
    "$CLI" clean inspect --serial MOCK > /tmp/last-output 2>&1
    if ! grep -q 'root check did not complete' /tmp/last-output; then
        cat /tmp/last-output
        printf 'Root fixture %s was not reported as unknown\n' "$mode"
        exit 1
    fi
    if grep -q 'no root signals\|rooted via' /tmp/last-output; then cat /tmp/last-output; exit 1; fi
done
if [ -s /tmp/unexpected-adb ]; then cat /tmp/unexpected-adb; exit 1; fi
echo 'ROOT_CLI_REGRESSIONS_PASS'

# A recognized rooted fixture reaches pm clear; its exit-zero Failure must stop removal.
export ROOT_MOCK_CASE=rooted
: > /tmp/cleanup-commands
expect_fail "$CLI" clean app com.example --serial MOCK --evidence-saved --i-understand-they-will-notice
grep -q 'MOCK_DENIED' /tmp/last-output
grep -q 'pm revoke --user 0 com.example android.permission.CAMERA' /tmp/cleanup-commands
if grep -q 'reset-permissions\|pm uninstall' /tmp/cleanup-commands; then cat /tmp/cleanup-commands; exit 1; fi
: > /tmp/cleanup-commands
expect_fail "$CLI" clean app com.example --serial MOCK --purge-messages --evidence-saved --i-understand-they-will-notice
grep -q 'message deletion is not implemented' /tmp/last-output
if grep -q 'pm clear\|pm revoke\|reset-permissions\|pm uninstall' /tmp/cleanup-commands; then cat /tmp/cleanup-commands; exit 1; fi
if [ -s /tmp/unexpected-adb ]; then cat /tmp/unexpected-adb; exit 1; fi
echo 'CLEANUP_CLI_REGRESSIONS_PASS'
