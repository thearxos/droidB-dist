# MVT and cleanup regression tests

Build on the host. Run binaries and mock CLI tests only in the diskless test VM.
The VM has no network, disks, or USB passthrough. All adb and MVT subprocesses in
the CLI tests are shell fixtures. No real device is mutated.

```sh
cargo test -p droidB --bin droidB-native --no-run --locked
cargo build -p droidB --bin droidB-native --locked
python3 tests/build-mvt-initramfs.py /tmp/droidb-mvt-vm-new
qemu-system-x86_64 -enable-kvm -m 1024 -smp 2 \
  -kernel /boot/vmlinuz-linux \
  -initrd /tmp/droidb-mvt-vm-new/test-initramfs.cpio \
  -append 'console=ttyS0 rdinit=/init droidb_test_vm=1 panic=-1' \
  -nographic -no-reboot -nic none
```

Use a new output directory. Success requires both test suites to pass,
`MVT_CLI_REGRESSIONS_PASS`, `CLEANUP_CLI_REGRESSIONS_PASS`, `MVT_LOG_CLASSIFIER_PASS`, and
`DROIDB_TEST_RESULT unit=0 clean=0 cli=0 log=0`. A VM exit alone is not a test result.

The helper needs Python, Cargo, Node.js, ldd, bash, cpio, the host kernel, QEMU/KVM, and standard
coreutils/util-linux commands. It uses Cargo metadata to select the test executable, compiling without running tests on the host. It copies only the built binaries and runtime
libraries into an initramfs; it does not start either existing libvirt VM.

Coverage includes process failure with partial results, silent empty success,
corrupt and missing output, duplicate alert representations, explicit coverage
gaps, unsupported SMS purge, exact package boundaries, package-specific permission
revocation, and cleanup stopping on an exit-zero failure response.
