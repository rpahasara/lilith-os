# Slice 15B2b — trusted DEV snapshot tool foundation

Status: installation-path design only. No DEV installation, workflow switch, A2
experiment, or A2 merge is authorized by this record.

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
broker release or candidate SHA. The manifest binds a protected-main source
commit, exact sorted payload list with byte lengths and SHA-256 hashes,
dependency/runtime identity, manifest schema, supported lifecycle profile
(`POST_STAGE_II_ACCEPTED_V1` only), supported output schema
(`BrokerCandidateDevSnapshotV1` only), and the accepted baseline identity.
The builder emits a deterministic archive plus separate hash attestation from
an exact source commit; it rejects unknown paths, symlinks, duplicates and
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

The present protected-main classifier sends this design record and all
proposed tool/builder/installer/workflow files to `DEPLOY_REQUIRED`. That
route invokes the Core API deployment/restart, which is forbidden for this
control transition. A narrow, protected-main-derived
`TRUSTED_DEV_CONTROL_INSTALL` mode is therefore proposed for an exact closed
set of snapshot-tool source, release builder, installer, tests, documentation
and workflow controls. Unknown, deleted, mixed, symlinked, broker, Core API,
authority, or dependency changes remain `DEPLOY_REQUIRED`. A PR in this lane
builds and tests an exact artifact **without** installing it; its required
status must report `DEV_MUTATION=NONE`, not falsely claim an installation.
Only a separate protected-main, exact-release, owner-authorized action may
install/upgrade the tool on DEV. The lane cannot select itself via candidate
metadata, and its introducing governance PR cannot self-certify. The earlier
one-time ruleset bypass is consumed; a fresh exact-PR/head bootstrap decision
is required before any bypass. Pending checks must remain visibly pending in
such a bridge. Do not broaden branch protection or reuse the old exception.

Proposed reviewed path inventory (final names must be frozen before a mode is
implemented): existing lifecycle source
`scripts/verify_broker_dev_lifecycle.py`; new fixed CLI
`scripts/trusted_broker_snapshot.py`, release builder
`scripts/trusted_broker_snapshot_release.py`, installer
`scripts/trusted_broker_snapshot_installer.py`, and their dedicated tests;
existing lifecycle tests `scripts/test_broker_dev_lifecycle.py`; existing
snapshot runner/parser `scripts/broker_candidate_dev_snapshot.py` and
`scripts/test_broker_candidate_dev_snapshot.py`; workflow
`.github/workflows/deploy-dev.yml` and
`scripts/test_broker_only_dev_workflow.py`; classifier
`scripts/classify_dev_deployment.py` and
`scripts/test_classify_dev_deployment.py`; and this architecture record.
Phase A must separately review the classifier/workflow control edits.
Phase B admits only the frozen tool, builder, installer, and directly related
tests/docs under the already-merged mode. Phase D admits only the frozen
workflow/runner/parser switch under the protected-main mode, after the tool
is installed. No wildcard admits future files by directory. The current
classifier still classifies every one of these proposed changes as
`DEPLOY_REQUIRED` until a governance bridge is merged.

Minimum safe phases:

1. Owner decides the narrow governance/bootstrap path; merge only the
   independently reviewed install-mode bridge (no DEV mutation).
2. Build/test/review the snapshot source, release builder and installer under
   the protected-main mode; merge exact code without automatic installation.
3. Obtain a fresh owner authorization for the exact release, then perform
   one governed DEV-only install and verify tool self-test, accepted baseline
   digest `abc33ebf8d43e8805f43ff11e663a4757bf558d9b62eda9669dabecbb7c9839a`,
   API PID 88740/NRestarts 0, broker PID 96650/invocation and release
   `817a83e44cec8965479fd97fc30b7a0b3ae49ab2`, 24/24/2/2 history, and
   unchanged complete snapshots. No candidate is installed.
4. Change the broker-only workflow to invoke the pinned installed tool and
   remove SCP, stdin and packed lifecycle-source publication, including its
   run-bound executable staging. Prove PRE, hosted candidate, POST and exact
   equality with no per-run executable transfer.
5. Only then rerun PR #38 through normal checks. Do not merge A2 merely
   because ordinary Core API checks are green.

Required tests before Phase 2/3 cover exact manifest/payload/dependency and
custody failures; wrong/missing release; fixed operation/host/PROD refusal;
closed output, framing and deterministic digest; DB/WAL/SHM read-only and
concurrency failure; no broker/API mutation; installer collision, wrong-host
and idempotent refusal; and workflow no-transfer, candidate isolation,
preflight block, postflight same-release and equality. Run lifecycle,
snapshot-guard, classifier, workflow, release-builder and installer tests,
repository validation, static checks and `git diff --check` on the eventual
implementation. This design record alone is not those test results.
