# Validation evidence

## 23 September 2026: full harness on the 0.4.1 implementation

Implementation base: `39355a1`, including root fixes `d4ea121` and `56e4879`, with
the updated test helper and CLI fixtures. Host compilation used
`CARGO_TARGET_DIR=$HOME/.cache/droidB-target-codex`. Cargo JSON selected both the CLI
and unit-test executable from that directory; no repo `target/` binary was reused.
All runtime checks ran in a fresh QEMU/KVM initramfs guest with 1 GiB RAM, two vCPUs,
no network, no disks and no USB passthrough. No device operation or host installation
was performed.

- Full native suite: **111 passed, 0 failed, 2 ignored**, including repaint and root tests.
- Real `build.rs` standalone tests: **4 passed, 0 failed**.
- MVT, root-inspection and cleanup CLI regression markers passed.
- The production frontend log classifier passed its Node.js checks.
- Final marker: `DROIDB_TEST_RESULT unit=0 build=0 cli=0 log=0`.
- Shell/Python syntax and `git diff --check` passed.

The root CLI cases cover complete unrooted and Magisk probes, plus offline,
unauthorized, empty, legacy-error, truncated and completed-but-nonzero ADB responses.
Unexpected mock commands fail the harness. Cleanup must fail for the expected reason,
stop before uninstall after a failed clear, and reject SMS purge without mutation.

The same completed-but-nonzero case reproduced the defect on `d4ea121` on 22 September:
the CLI printed no root signals and the gate was `unit=0 build=0 cli=1 log=0` while
109 native tests and 4 build-script tests passed. `56e4879` requires both successful
ADB exit and the closing marker; the current run demonstrates the regression now passes.

VM logs are retained in the private workspace at
`ARXOS/validation/droidb-root-probe-before-20260922.txt` and
`ARXOS/validation/droidb-regressions-20260923.txt`. Fixtures contain no private device
records. The source tests do not revalidate the released binary's byte identity;
release-byte and R2 installation checks are separately recorded in the maintainer handoff.

## 22 September 2026: original hardening pass, later committed as 931fc97

The tested changes were originally local on top of `c956230` and were subsequently
committed as `931fc97`. The original validation itself performed no commit, push,
mirror update, release or host installation.

- Host: locked Cargo build and unit-test compilation succeeded. The compiler emits dead-code
  warnings; the touched files pass `git diff --check`.
- Diskless QEMU/KVM VM: 12 MVT unit tests and 6 cleanup unit tests passed.
- Mock CLI checks passed for MVT failure, empty acquisition/output, malformed JSON,
  reused output, imported report handling, empty AndroidQF backup coverage,
  indicator matches, package-specific permission revocation, stop-on-failure, and
  unsupported SMS purge.
- The production frontend log classifier passed Node.js assertions inside the same VM. No layout or stylesheet changes were made.
- Final marker: `DROIDB_TEST_RESULT unit=0 clean=0 cli=0 log=0`.
- VM used the host kernel with a temporary initramfs, 1 GiB RAM, no disks,
  no network and no USB passthrough. Both existing libvirt VMs remained off.

A separate read-only review confirmed the SMS write-verification gap, exact package
matching, and refusal of unsupported purge. It also identified overstated root wording,
removed dead purge code, and the lack of a dedicated GUI cleanup acknowledgment
flow. Root wording was corrected. No new GUI cleanup action was added.

No new destructive path was tested on the owner's phone. Existing authorized
hardware inspection established that Android provider writes can silently fail
with exit zero. The regression fixtures contain invented identifiers and no
private phone records.

Remaining scope limits: default Android fleet acquisition is bug-report-only;
AndroidQF is an explicit artifact-analysis command. Rooted SMS collection/deletion
is not a wrapper feature. These tests exercise the native CLI and mocks, not
vendor-specific live cleanup or a rendered GUI.

## Recorded follow-up evidence

The maintainer handoff records these earlier results. They remain separate from the
23 September source-harness run:

- `ce8a9bc`: three deterministic `mvt::repaint_tests` added; native suite reported
  102 passed, 0 failed, 2 ignored. The maintainer later confirmed that run was on the
  host, so it is not disposable-VM evidence. The reader tests cover carriage-return
  handling, not live heartbeat timing or GUI behavior. The old helper selected only
  `mvt::tests` and `clean::tests`; the updated helper runs the full suite.
- Live fleet: Android and iPhone enumerated and acquired concurrently. Android produced
  a roughly 14 MB bug report and 22 module outputs. Re-reading the earlier output
  distinguished observations from indicator matches. This does not establish that
  the device is free of compromise, or validate capacity with 100+ devices.
- iPhone live wrapper acquisition failed after roughly 4.2 GB with
  `mobilebackup2 (-4)`, exit 255. There is no completed wrapper scan from that run.
- Distribution `v0.4.0`: native engine (1,907,248 bytes) and GUI AppImage
  (102,435,320 bytes) were reported downloaded through the installer's release URL
  and checksum-verified. AppImage launch produced WebKit child processes. Earlier
  browser checks covered CSS and keyboard focus, but packaged-window pixels were
  not confirmed.

## Current limitations and pending checks

Root probing now reports an unknown result on missing/incomplete output or unsuccessful
ADB exit. A completed no-signal result still cannot rule out hidden root, and detected
root signals do not establish provider-write access. SMS/call-log deletion is unsupported.

Static-only Thor discovery and the installer udev path were fixed in `d4ea121`.
Static Thor builds still need dynamic system libraries; the shared fallback requires
`libodin4.so`. Installer temporary-file handling, destination failures and launch-fallback
portability remain review topics outside this regression harness.

Real-device heartbeat/throttle confirmation, the iPhone `mobilebackup2 (-4)` acquisition
failure, an intermittent AppImage build failure despite `NO_STRIP=1`, and pixel-level
packaged-GUI verification remain open. These mock tests do not establish successful
cleanup on a vendor device or capacity with 100+ phones.

The maintainer reports GitHub v0.4.1 and R2 delivery checks, including installation from
bundled assets without download calls. The mirror guard added in `10a59ca` excludes
Rust/Cargo files from new syncs; historical public commits remain retrievable. No mirror,
release artifact or R2 index was changed by this test/documentation follow-up.
