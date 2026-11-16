# Native and CLI regression tests

Build on the host. Execute the native suite, build-script tests and mock CLI checks
only in the diskless test VM. It has no network, disks or USB passthrough. All ADB
and MVT subprocesses in the CLI tests are fixtures; no real device is mutated.

```sh
export CARGO_TARGET_DIR="$HOME/.cache/droidB-target-codex"
python3 tests/build-mvt-initramfs.py "$CARGO_TARGET_DIR/vm-regression-new"
qemu-system-x86_64 -enable-kvm -m 1024 -smp 2 \
  -kernel /boot/vmlinuz-linux \
  -initrd "$CARGO_TARGET_DIR/vm-regression-new/test-initramfs.cpio" \
  -append 'console=ttyS0 rdinit=/init droidb_test_vm=1 panic=-1' \
  -nographic -no-reboot -nic none
```

Choose a new output directory. The helper compiles the CLI and unit-test executable
with locked Cargo commands, then selects their exact paths from Cargo JSON output.
It honors `CARGO_TARGET_DIR` and does not copy a possibly stale CLI from repo `target/`.
It also compiles the real `build.rs` as a standalone test binary. No test binary is
executed on the host, and neither existing libvirt guest is started.

The guest runs the full native suite once, including `mvt::repaint_tests` and root
unit tests, then the four build-script discovery tests, CLI regressions and production
frontend log classifier. Ignored tests remain ignored. Success requires all of:

- Native and build-script test summaries with zero failures.
- `MVT_CLI_REGRESSIONS_PASS` and `ROOT_CLI_REGRESSIONS_PASS`.
- `CLEANUP_CLI_REGRESSIONS_PASS` and `MVT_LOG_CLASSIFIER_PASS`.
- `DROIDB_TEST_RESULT unit=0 build=0 cli=0 log=0`.

A VM shutdown or QEMU exit zero alone is not a test result. The old
`unit=0 clean=0 cli=0 log=0` marker covered selected unit groups only; it must not
be confused with this full-suite run.

The ADB fixture explicitly handles complete unrooted and Magisk probes plus six
unknown outcomes: offline, unauthorized, empty output, legacy error text, a truncated
rooted payload and a complete payload followed by ADB exit 7. Any unexpected command
is a harness failure, so an obsolete mock cannot silently stand in for a clean result.
Cleanup asserts its intended failure reason, package-specific permission revocation,
no uninstall after a failed clear, and no destructive command for unsupported SMS purge.

MVT cases cover partial failed output, empty acquisition/results, malformed JSON,
reused output, imported reports, coverage gaps and indicator matches. The helper needs
Python, Cargo/rustc, Node.js, ldd, bash, cpio, the host kernel, QEMU/KVM and standard
coreutils/util-linux commands. Host compilation can require the normal project build
dependencies. Keep each agent's build and VM artifact directories separate.

These tests do not establish hidden-root detection, successful vendor cleanup,
installer behavior, real-device progress timing or rendered GUI behavior. See
[VALIDATION.md](VALIDATION.md) for source versions, results and remaining limits.

## Sideload and Google services

`droidB-sideload` and `droidB-gms` have their own diskless VM run. The image carries Python, the
real aapt2 and 7-Zip, two real F-Droid APKs (Termux:Boot, Termux:API from
`ARXOS/vendor/termux-fdroid`), the tools and `tests/fake-adb.py` as adb:

```sh
python3 tests/build-sideload-initramfs.py OUT
qemu-system-x86_64 -enable-kvm -m 2048 -smp 2 -kernel /boot/vmlinuz-linux-arxos \
  -initrd OUT/test-initramfs.cpio -append 'console=ttyS0 rdinit=/init panic=-1 quiet' \
  -nographic -no-reboot -nic none
```

Success is `SIDELOAD_CASES pass=45 fail=0` and `DROIDB_SIDELOAD_RESULT rc=0`. The fake phone logs
every call and fails any command it does not model, so "no unexpected phone commands" is a case.
An APK named com.google.android.gms, or one with native code, cannot be built without a platform
android.jar, so `tests/fake-aapt2.py` answers for those named test files only.

The GUI flows (install with its consent dialogs, game data, Google services, battery exemptions)
run the real GUI and helpers against the same fake phone on a virtual display:

```sh
xvfb-run -a -s '-screen 0 1280x800x24' python3 tests/gui_sideload_test.py OUT
```

Success is `GUI_SIDELOAD pass=7 fail=0`; screenshots land in OUT. Neither run proves a real phone
accepts the installs: that needs a device test.
