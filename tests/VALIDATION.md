# Validation: 22 September 2026

Local source changes based on main c956230. No commit, push, mirror, release, or
host installation was performed.

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

Claude Code completed a read-only review after one transient API failure. Its
review confirmed the SMS write-verification gap, exact package matching, and
refusal of unsupported purge. It also identified overstated root wording,
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
