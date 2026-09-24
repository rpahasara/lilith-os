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
`c4d60b9c19debc9fcfece256641a9f83ca82b15b5343cd15cb81a1988c1c6261`
with `current` pointing to the preserved, unaccepted old release
`8b4dbee055f5ca6b8e899d9cab8130ed4a6cbd9abb27fa71b7bbee88c41c6958`.
Before installation, the release directory set must contain exactly that old
release and the two previously installed but failed/unaccepted releases:
`36a3c93e5cb3556f5f2deb00bd4e4e0f72b71146b9f182f820b04bfa03db1aec`
(nested-sudo self-test) and
`b2d6a45094d74e23c18a92d171e439ef52527c31f0369ac46ea85c72bf3e0055`
(boot-ID-format self-test). All three historical directories remain preserved.
The new target must be absent.
It validates the host and direct anchor, verifies the exact incoming archive
and manifest, runtime pins and existing release/selector state, and requires
the new release directory to be absent. It installs alongside all three historical
releases, then re-opens the installed directory and verifies its exact file
set, directory/file custody, manifest identity and every payload hash before
executing anything or changing `current`.
At that post-install/pre-first-test boundary the set is exactly the old,
both failed historical releases, and `c4d60b9c...`; `current` still points
to `8b4dbee...`. The new release is installed, unselected and unaccepted.

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
baseline, preserved historical identities and final `current` target. If the second
digest differs, it reports `SELECTED_BUT_UNACCEPTED_DIGEST_MISMATCH` and
leaves all four releases present without inventing rollback. Other second-test
failures are also selected but unaccepted. No persistent authority-state
acceptance row is written.

This follow-up repair changes only protected snapshot-control source, focused
tests, the exact deployment-classifier allowlist, and this architecture record;
it does not authorize a DEV deployment or tool installation.
`TrustedBrokerSnapshotReleaseV1` payloads are the CLI, invoker and lifecycle
validator; none were changed by that pin repair, so its release identity
remained byte-identical at that point. The subsequent first-test diagnosis
below supersedes its installation readiness.

## B2D6 first-test diagnosis

The owner-authorized `b2d6a45094d74e23c18a92d171e439ef52527c31f0369ac46ea85c72bf3e0055`
installation stopped at its first confined test with
`NEW_RELEASE_INSTALLED_UNSELECTED_UNACCEPTED`. The installed bytes matched the
immutable manifest. `current` remained on `8b4dbee055f5ca6b8e899d9cab8130ed4a6cbd9abb27fa71b7bbee88c41c6958`;
the historical failed `36a3c93e5cb3556f5f2deb00bd4e4e0f72b71146b9f182f820b04bfa03db1aec`
and new candidate remained preserved. Direct accepted-state anchors passed
before and after the failure. No second snapshot or selector change occurred.

The single confined diagnostic identified `ACCEPTED_BROKER_INCARNATION`:
the validator compared an unhyphenated boot-ID constant with the hyphenated
UUID returned by `/proc/sys/kernel/random/boot_id`. PID `96650` and start
ticks `91036598` matched, as did the broker process identity. The durable
accepted baseline remained
`abc33ebf8d43e8805f43ff11e663a4757bf558d9b62eda9669dabecbb7c9839a`;
the corrected boot-ID representation does not change that semantic claim.
Because the correction changes the immutable lifecycle-validator payload,
`b2d6a450...` remains unaccepted historical evidence. The corrected validator
is in the new `c4d60b9c...` immutable payload, and the fixed installer target
and protected snapshot expected-release pin now name that release. This source
contract does not authorize staging, installation, a self-test, selector change,
or DEV cleanup. A fresh exact owner authorization is required before DEV action.
