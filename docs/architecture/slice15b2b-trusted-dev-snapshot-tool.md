# Slice 15B2b — trusted DEV snapshot tool foundation

Status: source foundation implemented, subject to Linux proof and governed
source-only merge. No DEV installation, A2 experiment, or A2 merge is
authorized by this record. The broker-only workflow source has been changed
to require the installed tool and therefore fails closed before first install.

## Decision and trust boundary

The broker-only lane will no longer transfer executable trusted lifecycle source
to DEV on each PR. The required property is **execute the exact approved trusted
snapshot implementation**, not **successfully transport that implementation on
every PR**. Hosted-Linux SCP/SFTP, SSH stdin, and packed SSH command-channel
publication all failed to establish a reliable per-run path. Their exact Linux
root cause is unproven. The earlier bounded local packed-payload feasibility
probe does not overturn the hosted failure. These methods remain historical
evidence, not fallbacks or candidates for a fourth transport variant.

Proposed utility: `lilith-broker-dev-snapshot`, a persistent, fixed-purpose,
read-only CLI on the pinned DEV VM. It is not a daemon, API, broker, authority
service, or general remote executor. Its V1 operation set contains only
`SNAPSHOT_ACCEPTED_STAGE2`; no arbitrary command, Python, shell, SQL, path,
service, PID, profile, candidate SHA, or executable selector is accepted.
Its fixed operation observes only the existing `POST_STAGE_II_ACCEPTED_V1`
contract: host and account identity; accepted lifecycle/baseline; API and
broker process, unit, release, socket, file and configuration custody; owner
and synthetic-evidence DB integrity, schema, counts and row identities/hashes;
used authorization and evidence identities; and the existing absent-path and
residue checks. No unrelated diagnostic surface is added.

The utility must never write either DB or its sidecars; create a challenge,
request, claim, evidence, authorization, or Stage-III arm; stop, signal, or
restart either service; change any release pointer, unit, configuration, socket,
canonical or Privacy/key custody; or deploy candidate bytes. Candidate code
continues to build and run only on the credential-free hosted Linux runner.
Nothing from PR #38 supplies tool code, profile, paths, release expectation, or
lifecycle rules.

## Separate trusted release and custody

Use `/opt/lilith-trusted-controls/broker-snapshot/releases/<release-id>/` with
a root-owned `current` pointer to a reviewed release. `<release-id>` is the
SHA-256 of the canonical `TrustedBrokerSnapshotReleaseV1` manifest, not the
broker release or candidate SHA. The manifest binds the exact sorted payload
list with byte lengths and SHA-256 hashes, dependency/runtime identity,
manifest schema, supported lifecycle profile
(`POST_STAGE_II_ACCEPTED_V1` only), supported output schema
(`BrokerCandidateDevSnapshotV1` only), and fixed operation. The accepted
baseline is enforced by the reused lifecycle validator. Source commit is
recorded separately in the attestation so identical bytes yield the same
release identity across commits. The builder emits a deterministic archive
from exact committed payloads; it rejects unknown paths, symlinks, duplicates and
noncanonical metadata. The broker release and snapshot-control release remain
independent trust artifacts.

The minimum proposed installed payload closure is a small fixed CLI wrapper,
the reviewed `verify_broker_dev_lifecycle.py` implementation (imported rather
than copied or forked), and its manifest. The builder and installer remain
protected-main controls, not installed runtime modules. The current validator
imports only Python standard-library modules; it invokes fixed absolute system
commands and reads `/etc/shadow`, broker-owned mode-0600 DBs, `/proc`, systemd,
local API health, and instance metadata. Root is currently the minimum proven
read identity. Root by itself has broad **write** authority, so a bare root
Python invocation does not satisfy the no-write requirement. Before any DEV
installation, the fixed entry point must prove an OS-enforced confinement
profile for the snapshot process and its fixed subprocesses: an isolated
read-only view of production files/DBs/sidecars/units/configuration, no
write-capable bind or host temporary directory, dropped unnecessary
capabilities, no privilege regain, and denied filesystem/service mutation.
The permitted metadata, local health and systemd read channels must still
work. The exact Linux mechanism and controls require a DEV-compatible test;
if that cannot be proven, installation is blocked. Do not grant broker UID
999, relay UID 997, or `lilith` new read access. Before implementation,
inventory and pin the actual
DEV `/usr/bin/python3` binary, Python and SQLite versions, relevant stdlib and
system-command package identities; run with isolated Python mode and bytecode
disabled. A venv is not required for the presently stdlib-only closure; if
the final inventory reveals an external package, build a root-controlled
immutable environment from exact offline wheel hashes instead of using ad hoc
packages. A runtime identity change is a release mismatch, not an implicit
upgrade.

Expected custody: `/opt/lilith-trusted-controls`, `broker-snapshot`, and
`releases` root:root 0755; each immutable release and internal directory
root:root 0755; regular code/manifest files root:root 0644 with one link and
no writable parent; only the fixed entry point may be executable (0755).
The `current` symlink is root-owned, has one relative target matching the
approved release-id grammar, and resolves only inside `releases`. No symlink
appears within a release payload. Root-owned world-readable source does not
confer write authority. The installer may write this dedicated control tree
only during a separate owner-authorized transition; normal snapshot execution
opens no write-capable path.

The tool checks exact DEV project, zone, instance name/id, hostname and machine
ID; PROD and any mismatched host hard-fail. Before output it checks the
`current` pointer, parent and release custody, exact manifest bytes/hash,
complete no-extra-file payload inventory and hashes, dependency/runtime
identity, fixed configuration and effective confinement state.
Protected-main preflight and postflight
also pin the **expected** installed release-id and manifest hash. A returned
claim is not sufficient against a compromised root host: authenticated SSH,
root custody and host identity remain the trust boundary. Mismatch fails the
required check as `TRUSTED_SNAPSHOT_RELEASE_MISMATCH`, with no source-transfer
or auto-install fallback. A later lifecycle change requires a distinct
reviewed release and governed upgrade.

## Snapshot, read-only behavior, and comparison

`BrokerCandidateDevSnapshotV1` is a closed wrapper containing schema,
operation, profile, tool release and manifest identities, explicit validation
result, the complete existing accepted lifecycle snapshot, its SHA-256 digest,
and the accepted baseline digest. Unknown fields, malformed types, wrong
profile/identity, excessive size, or failed validation are rejected. The
inner snapshot retains the existing `collect_accepted()` and
`validate_accepted()` semantics; repository tests and the installed tool use
this same source, so there is no second lifecycle implementation. The inner
snapshot digest is SHA-256 of sorted-key, compact, UTF-8 JSON with the existing
POSIX path keys; its complete bytes (including PID/incarnation/custody) must
equal between PRE and POST. The existing `Stage2AcceptedBaselineV1` digest
remains separate and intentionally excludes volatile PIDs. Neither digest is
an authorization.

One bounded stdout frame carries one canonical JSON result with byte length
and SHA-256; diagnostics go to bounded stderr. The protected-main parser must
reject extra stdout, transport chatter, invalid framing, unknown schema,
noncanonical JSON, digest mismatch or oversized output. No secrets, source
code or dynamic executable material are emitted. The fixed SSH/IAP command
contains no candidate parameter and selects only the installed entry point
and closed operation. Preflight and postflight invoke the same expected
release, validate it independently, and compare complete snapshots exactly;
preflight failure blocks the credential-free candidate job. PROD remains a
separate read-only darkness audit.

The existing DB reader uses SQLite URI `mode=ro&immutable=1` plus
`PRAGMA query_only=ON`, fixed read queries, `integrity_check` and
`foreign_key_check`; it hashes/records the accepted WAL and SHM files, and
does not checkpoint, migrate, vacuum, or normalize them. `immutable=1` can
ignore live WAL content and can encounter a read-only/journal-mode mismatch;
the accepted zero-length WAL is a pinned observation, not a general guarantee.
Do not silently switch to a mode that might create or mutate sidecars. Tests
must compare DB/WAL/SHM bytes and metadata before/after an invocation, cover
nonempty WAL and read-only journal modes, and fail closed if the accepted
read-only interpretation is not proven. This is not a cross-file atomic
snapshot of a running broker. V1 retains the existing accepted row/history
reconciliation and exact PRE/POST equality; it has no general retry loop.
Concurrent churn, torn observations, or unknown sidecar states fail rather
than trigger a pause, checkpoint, or stop-the-world operation. Any proposed
bounded retry is a separately reviewed semantic change.

## Installer, governance, and transition sequence

The dedicated root installer must accept only an exact protected-main
release/attestation and separate owner authorization; verify DEV identity
before writing; verify archive, manifest and every payload; reject existing
collisions, symlink substitution, unknown files and non-root custody; create a
new immutable release through exclusive staging and fsync; atomically select
the exact approved `current`; reverify custody and run a read-only self-test
and accepted snapshot. It must never touch broker/API files, releases, units,
services, DBs or authorization history, and must never target PROD. An
existing release is never overwritten. Rollback to a previously verified
release needs a new explicit authorization, not silent fallback.

The owner-approved minimal path does **not** add a general
`TRUSTED_DEV_CONTROL_INSTALL` mode. The current protected-main classifier
classifies this source/workflow change `DEPLOY_REQUIRED`, whose normal path
restarts the accepted DEV API. This is a source-governance bootstrap conflict,
not a reason to restart that API. The owner has authorized a one-time,
exact-PR/head source-only bridge after independent Linux tests and final-diff
review. Any skip must be transparent; required checks stay pending, not
falsely green. Only the owner PR-only ruleset bypass may be added temporarily
and must be removed immediately after that exact merge. No DEV install,
broker/API restart, or PR #38 merge is included in the exception.

The implementation adds `scripts/trusted_broker_snapshot.py` (fixed CLI),
`scripts/trusted_broker_snapshot_release.py` (deterministic builder),
`scripts/trusted_broker_snapshot_installer.py` (first-install-only installer),
`scripts/trusted_broker_snapshot_invocation.py` (fixed systemd confinement
policy), focused tests, and the broker-only runner/workflow change. It reuses
the unchanged `scripts/verify_broker_dev_lifecycle.py`. The installed release
contains only the CLI and that validator. No candidate checkout selects any
of those controls. The workflow's broker-only pre/post phases invoke the
installed tool; until the separately authorized installation, they fail
closed with a missing or mismatched release.

The fixed transient systemd invocation applies `ProtectSystem=strict`,
`ProtectHome=read-only`, `NoNewPrivileges=yes`, a capability bound retaining
only `CAP_DAC_READ_SEARCH` for broker-owned mode-0600 DB reads, `PrivateTmp`,
`PrivateDevices`, kernel/control-group protections, and read-only `/run`.
Network remains available because accepted-state verification reads local
API health and instance metadata. The tool checks effective read-only mount
state, no-new-privileges, and effective capabilities. Credential-free Linux
CI must demonstrate reads from representative broker-owned authority data
and denial of writes to authority, release and configuration fixtures.
This transient unit does not alter the broker/API units or their lifecycle.

The narrow first installer accepts only the owner-reviewed release ID pinned
in its source. A later authorized operator must stage the exact reviewed
installer bundle, archive and attestation in root-controlled
`/opt/lilith-trusted-controls/broker-snapshot/incoming/<release-id>/`; the
installer rejects unknown files and any pre-existing release or `current`
pointer. It verifies the archive before creating the immutable release,
atomically selects that release, and runs the fixed confined snapshot
self-test. It is implemented and tested here but must not run on DEV until
`FIRST_DEV_TRUSTED_SNAPSHOT_INSTALL` is separately authorized.

Safe sequence:

1. Review and merge this source/workflow change through the exact one-time
   source-only bridge if `DEPLOY_REQUIRED` would restart the API. No DEV
   installation occurs.
2. Stop. Obtain fresh owner authorization for the exact release and allowed
   `/opt/lilith-trusted-controls/broker-snapshot/` first-install mutation.
3. Install only that release, then verify self-test, accepted baseline digest,
   API PID 88740/NRestarts 0, broker PID 96650/invocation and release
   `817a83e44cec8965479fd97fc30b7a0b3ae49ab2`, 24/24/2/2 history, and
   unchanged complete snapshots. No candidate is installed.
4. Rerun PR #38 through normal PRE, credential-free hosted candidate, POST,
   equality and PROD-darkness checks. Do not merge A2 on ordinary Core API
   checks alone.

Required tests before Phase 2/3 cover exact manifest/payload/dependency and
custody failures; wrong/missing release; fixed operation/host/PROD refusal;
closed output, framing and deterministic digest; DB/WAL/SHM read-only and
concurrency failure; no broker/API mutation; installer collision, wrong-host
and idempotent refusal; and workflow no-transfer, candidate isolation,
preflight block, postflight same-release and equality. Run lifecycle,
snapshot-guard, classifier, workflow, release-builder and installer tests,
repository validation, static checks and `git diff --check` on the eventual
implementation. This design record alone is not those test results.
