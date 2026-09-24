# Slice 15B2b: accepted Stage-II lifecycle bridge

Status: bridge record for accepted synthetic DEV state; not a Stage-III authorization.

## Acceptance identity

The closed `POST_STAGE_II_ACCEPTED_V1` trusted-main profile describes the
formally accepted Stage-II run `35965971283` from governed source
`ab78b63b2011392f1991e720e7b795348e93fb98`. The installed, manifest-pinned
broker release is independently `817a83e44cec8965479fd97fc30b7a0b3ae49ab2`.
Changing repository HEAD does not accept a new installed broker release.

Stage-I host, accounts, groups, directories, manifest, 23 release payloads,
configuration, units, and DEV API files retain their exact hashes. The two
owner-control SQLite databases are broker-owned mode 0600, retain the accepted
schema fingerprints, pass integrity and foreign-key checks, and have precisely
24 challenges, 24 requests, two synthetic claims, and two synthetic evidence
rows. Every row in every accepted table has an identity and full-column SHA-256
hash pinned by the validator. BLOB columns are represented as `hex:<hex>`
before canonical sorted-key, compact JSON serialization. The challenge states
are exactly 20 CANCELLED, two CONSUMED, and two EXPIRED. Counts are only one
guard; unknown or altered rows fail even if totals remain unchanged.

Attempt #1 authorization `4006ead71ca04c219b3b41e6818010f2`, its consumed
record hash `d75394b18906546095650851b0c18aac3208ac3fb04bde43655c80482602ef51`,
and evidence `se.68b647fc14aeea4fb32bdd7d0fada54d8f4af7c272ec6784f5d22c4c8980e7b5`
remain terminal history. Accepted Retry #2 authorization
`317c11bba95441369af17c2292e6b1d0`, its
`Stage2UsedAuthorizationV2` record hash
`ad43a9e3b822390b227d4e72d4a29a9f2915773f646b192015d98f7f9e720249`,
and evidence `se.8f51f58203a4218a1ffe16540400db3526261864b2cab87bd87e0e8a2166ee7c`
are separately pinned. Both claim-to-evidence links are exact. An active
authorization or pending used-record publication fails.

## Runtime and authority boundary

The accepted broker service is active/running and static (not enabled);
the socket is active/listening but disabled at boot. The only broker process
must be the service MainPID, running with UID/GID 999/987, no supplementary
group beyond 987, the accepted release working directory, and the expected
command and executable. The UNIX `owner.sock` must be kernel-listening,
broker-owned, group 988, mode 0660 in the root-owned runtime directory.

PID 96650 is an observation from the accepted run, not durable lifecycle
identity and not part of the accepted baseline digest. The accepted systemd
invocation ID and start time are pinned to detect an unexpected restart before
Stage III. A later governed restart must carry its own separately approved
incarnation/experiment baseline; a new PID alone does not alter this validator
or establish authority. This V1 profile does not accept a new invocation or
an instrumented release by inference.

The DEV API PID is also observational. Service health, app and unit hashes,
DEV DB/canonical-runtime custody hashes, and host identity remain required.
The only broker credential is public synthetic `ocred.synthetic`. No real
credential, owner ActorEvidence, Policy/Consent authority, canonical memory,
or cognitive/Privacy custody is granted. PROD retains its independent
`PRE_B1B2B` darkness gate.

## Machine-readable baseline

`Stage2AcceptedBaselineV1` is emitted within the read-only lifecycle
snapshot. It contains the lifecycle and acceptance identities; host and
Stage-I release/schema identities; both used authorization identities and
hashes; all owner/evidence row identities and hashes; database fingerprints,
counts and WAL/SHM metadata; service/socket configuration identity; and
DEV API configuration/custody hashes. The
`stage2AcceptanceEvidenceDigestSha256` hashes the history and database
evidence subset. `stage2AcceptedBaselineDigest` hashes the complete
baseline excluding itself, using sorted-key compact UTF-8 JSON with POSIX
path keys. Capture time and volatile PIDs are deliberately excluded. A digest
is descriptive evidence, never authorization. The fixture and pre-merge live
read-only DEV observation both yield
`abc33ebf8d43e8805f43ff11e663a4757bf558d9b62eda9669dabecbb7c9839a`;
live post-merge validation must independently confirm it.

The observed zero-length WAL is an accepted file-state pin, not proof of
crash recovery. The profile makes no fault-seam, restart, or crash claim.

## Governance dependency

The pre-bridge protected-main validator selects
`POST_STAGE_II_FAILED_INERT_V1` and rejects the now accepted active broker.
The deployment classifier treats this trust-root edit as `DEPLOY_REQUIRED`;
the required deployment workflow would deploy/restart the DEV API before
trying the old lifecycle validator. That is an accepted-Stage-II lifecycle
bootstrap deadlock, not a reason to stop the accepted broker. If the owner
uses the exact-PR, exact-SHA one-time ruleset exception, the checks must
remain visibly pending rather than falsely successful, and the bypass must
be removed immediately after this bridge merges. No Stage-III seam or
experiment belongs to this bridge.
