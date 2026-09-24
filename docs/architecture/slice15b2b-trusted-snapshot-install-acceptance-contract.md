# B1b-2b trusted snapshot installation acceptance contract repair

This source-only repair supersedes the installation ordering in
`slice15b2b-trusted-dev-snapshot-tool.md`. It does not authorize staging or
installing a release on DEV, changing `current`, restarting services, or
executing the old selected but unaccepted release. PR #38 remains separate.

## Pre-mutation continuity gate

`Stage2AcceptedInstallAnchorV1` is a small direct, read-only continuity check,
not `POST_STAGE_II_ACCEPTED_V1`, a replacement lifecycle validator, or a new
semantic baseline. The old unaccepted release must never be used to run the
pre-install gate. The trusted installer exposes `--check-anchor` as a
non-mutating mode for the owner-governed pre-stage command-channel check; its
normal install path re-runs the same gate before any release mutation. A
future owner-authorized operation must complete the direct gate before
staging the installation artifact. No installer or validator distribution is
performed by this source change.

The anchor requires the exact DEV GCE project, zone, instance name and ID,
hostname, and machine ID and rejects PROD. It pins API PID 88740, boot ID
`24d1771d-e1b5-4e5f-816d-da08ad8b367a`, kernel start ticks 86941441,
`NRestarts=0`, loaded/active/running state, and healthy database result. It
pins broker PID 96650, start ticks 91036598 on that boot, invocation
`5c1eb955e2dc44e78139c416f0c9469a`, start timestamp
`Thu 2026-09-24 06:51:22 UTC`, installed broker release
`817a83e44cec8965479fd97fc30b7a0b3ae49ab2`, service/socket state,
and listening `owner.sock` custody. Exact accepted SHA-256 plus UID/GID/mode
pins cover API app, unit, legacy DB and canonical-runtime, broker unit,
socket unit, DEV config, identities, owner DB and evidence DB. The DB hashes
are `939b5a0e4c5471bac5843f9c17de9548494ab49bfa54a062994f57900de2b7bb`
and `a4ff3d076a51019a6287c2a492a44e755dae5e9a7da55c9d9e942d9b9362c785`;
the read-only immutable SQLite count observations must be exactly 24
challenges, 24 requests, 2 claims and 2 evidence rows. File identities are
read before and after counts to fail on concurrent churn. The accepted
semantic lifecycle baseline
`abc33ebf8d43e8805f43ff11e663a4757bf558d9b62eda9669dabecbb7c9839a`
remains historical until the new release itself reproduces it.

## Exact fixed transition

The installer accepts only the source-pinned new release
`36a3c93e5cb3556f5f2deb00bd4e4e0f72b71146b9f182f820b04bfa03db1aec`
with `current` pointing to the preserved, unaccepted old release
`8b4dbee055f5ca6b8e899d9cab8130ed4a6cbd9abb27fa71b7bbee88c41c6958`.
It validates the host and direct anchor, verifies the exact incoming archive
and manifest, runtime pins and existing release/selector state, and requires
the new release directory to be absent. It installs alongside the old
release, then re-opens the installed directory and verifies its exact file
set, directory/file custody, manifest identity and every payload hash before
executing anything or changing `current`.

The installer-private first self-test derives the exact new release path
from protected source constants. It gathers the two fixed root-side `sudo`
policy observations, runs the installed CLI through the same transient
systemd confinement properties, and invokes the CLI's `collect()` directly
against that fixed release path. The installed CLI checks its own release
and runtime, DEV host, confinement and full accepted lifecycle. Within the
same confined unit, a fixed probe opens representative authority DB,
configuration, canonical-runtime and release files for write *without
writing bytes* and requires denial. The successful read-only lifecycle plus
the write-denial marker supply the evidence fields. The public installed
CLI and invoker still accept no caller-selected release path. The invoker is
part of the release payload and is not modified by this repair.

The first framed `BrokerCandidateDevSnapshotV1` must pass the fixed release,
profile `POST_STAGE_II_ACCEPTED_V1`, accepted semantic baseline, canonical
frame and complete snapshot digest checks. The installer retains that digest
in `selfTestCompleteSnapshotDigest`. If the first test fails, the new
directory remains installed but unselected/unaccepted, `current` remains
old, the result is `NEW_RELEASE_INSTALLED_UNSELECTED_UNACCEPTED` with bounded
diagnostics, and there is no automatic retry, deletion or rollback.

Only after the first test passes does the installer atomically select the
new release and verify the pointer. It runs one second snapshot through the
normal selected invoker, checks the same contract, and requires exact first
and second complete-digest equality. Only then may it report
`TRUSTED_SNAPSHOT_RELEASE_ACCEPTED`, including both digests, lifecycle,
baseline, preserved old identity and final `current` target. If the second
digest differs, it reports `SELECTED_BUT_UNACCEPTED_DIGEST_MISMATCH` and
leaves both releases present without inventing rollback. Other second-test
failures are also selected but unaccepted. No persistent authority-state
acceptance row is written.

This repair changes only the protected source installer, focused tests and
this architecture record. `TrustedBrokerSnapshotReleaseV1` payloads are the
CLI, invoker and lifecycle validator; none are changed. The pre-existing
authorized release identity therefore remains byte-identical subject to
artifact verification at the later owner-authorized installation gate.
