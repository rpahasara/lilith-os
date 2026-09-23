# Slice 15B2b-B1b-2b trusted first-install control

This control change does not install or activate the Memory Broker. The first
operational mutation needs a separate owner decision and a manual invocation.
The selected inert release is the exact governed-main source
`817a83e44cec8965479fd97fc30b7a0b3ae49ab2`; the earlier `e3cd6ee`
archive remains validation evidence only. The 23 payload hashes are identical
between those releases. The new archive has SHA-256
`b4cb4c1412908c1702d9cdf00717dff77574e70fc47abf31f05ff782eca04d87`
and manifest SHA-256
`7a46ac83001411a29b1bc4be7e0f91f09c5879967386c452b2620e23d16e4614`.

## Identity and owner decision

The workflow is `workflow_dispatch` only, on protected `main`, with a
fixed owner actor, exact release SHA, closed Stage-I choice, and explicit
confirmation text. It uses the existing GCP workload identity/IAP deployer;
it does not change IAM. The trusted workflow reads the GCP control-plane
instance ID/name/status. On the VM, the trusted-main installer independently
checks GCP metadata project/zone/instance ID/name plus local FQDN and
machine ID. Production identity and unknown identity fail closed.

The first-run marker is root-owned `0600` at
`/etc/lilith-memory-broker/b1b2b-authorization.json`. Only the trusted
`authorize-dev` operation materializes its closed schema after identity,
collision, and exact-artifact verification. It contains no secret:
schema version 2, purpose `B1B2B_DEV_FIRST_INSTALL`, pinned project, zone,
instance ID, FQDN and machine ID, selected SHA, `SYNTHETIC_ONLY`,
`DISABLED`, `B1B2B_I`, owner actor, random authorization ID, issuance
and 30-minute expiry. It cannot authorize Stage II, Stage III, or rollback.
After every preflight gate succeeds, the installer atomically moves the marker
to a root-owned used record before creating accounts. It is single-use even
when a later operation fails. A failed partial install is evidence and
requires a fresh owner recovery decision, not an automatic retry.

The current root-capable deployer can still bypass controls if compromised.
That is the separate B1c limitation; this is not Level 2 root isolation.

## Stage boundaries

- **B1B2B_I / PROVISION_ONLY:** after all preflight gates, create only the
  approved local broker/relay accounts and IPC group, root-owned immutable
  release/config and inert units, and broker-owned synthetic owner-control
  and evidence state. Do not daemon-reload, enable, or start units.
- **B1B2B_II / ACTIVATE_AND_ISOLATION_TEST:** needs a new owner decision,
  stage-II marker, and a separately reviewed activation harness. Test socket
  permissions, kernel `SO_PEERCRED`, relay-positive and ordinary-user-negative
  access, broker breakout/network denial, and only the four synthetic
  operations. A Stage-I marker is rejected by `activate-dev`.
- **B1B2B_III / FAULT_AND_RESTART_TEST:** needs another decision and harness.
  Test clean restart, SIGKILL, WAL-present restart, transaction fault,
  socket/service failure and repeated failed startup; no VM reboot is
  included. A Stage-I marker cannot authorize this stage.

The synthetic test scalar stays in a trusted transient test harness, never in
the release, marker, config, state DBs, journal, or persistent DEV files.
The relay sends a challenge to the harness; the harness creates a one-time
assertion outside broker custody and returns only that assertion through the
relay-identity socket client. The broker holds only the public synthetic
credential. No real owner credential, authority key, personal memory,
cognitive DB, or Privacy DB is part of this stage.

## Failure and rollback

Stop on wrong host identity, any unexpected account/path/unit/drop-in/socket
or staging collision, artifact mismatch, account contract failure, API
degradation, or any PROD change. Do not repair unknown state in place.

- Stage I failure: keep service/socket inactive; preserve any accounts,
  release, DB/WAL/SHM, marker, and journal evidence. Require owner-approved
  recovery; do not repeat first install automatically.
- Stage II failure: stop/disable only broker units, restore prior active
  release pointer or no-active-broker state, preserve accounts and all
  synthetic state, and verify the existing DEV API remains healthy.
- Stage III failure: first stop the broker/socket, preserve fault and WAL
  evidence, then use the separately authorized Stage-II rollback path.

Every stage captures host identity, release/manifest hashes, account mapping,
ownership/modes, unit hashes, service credentials, socket inode/permissions,
peer-credential and denial probes, synthetic proof/replay state, API health,
and production darkness. The installer records OS-assigned UID/GID values in
root-owned `identities.json`; later stages must match them exactly.

This control-only PR must not run the manual workflow. After protected merge,
recheck DEV identity and absence of all broker operational state, then stop
for explicit B1B2B_I owner authorization.
