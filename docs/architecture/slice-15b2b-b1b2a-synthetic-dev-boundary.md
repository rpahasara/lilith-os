# Slice 15B2b-B1b-2a — persistent synthetic DEV boundary candidate

Status: feature implementation candidate. No VM account, group, release,
configuration, state, service, socket, or IAM resource is created by this PR.
B1b-2b requires a separate owner decision.

## Closed runtime modes

The existing B1b-1 TEST path remains explicitly test-only and the Core API
B1a owner-proof guard remains unchanged. The new `DEV_SYNTHETIC` path uses
the shared owner-proof verification engine and a broker-local state adapter.
It refuses `LILITH_ENV=test` or
`prod`, requires the exact DEV host/machine marker, synthetic-only authority
mode, disabled canonical capability, fixed `.invalid` RP/origin, fixed public
credential fingerprint, exact release SHA, both schema fingerprints, and
explicit absence of cognitive/Privacy/key custody. There is no live mode.

The broker constructs the fixed `DevSyntheticOwnerProofVerifier` policy
from the shared module. That policy permits the pinned synthetic RP/origin
only in DEV; the existing B1a TEST-only constructor retains its prior guard.
The shared engine alone performs WebAuthn verification and durable proof
consumption. The operational release contains its contracts but no Core API
`app.py` or `canonical_authority.py`. Negative WebAuthn and B1a golden
vectors remain mandatory CI gates before any DEV installation.

## Synthetic evidence, not Actor authority

`owner_control.db` has a distinct DEV schema with
`synthetic_claim_v1`. A separate `synthetic_evidence.db` has only synthetic
metadata and a unique `challenge_id`. Its IDs start `se.` and its structure
cannot deserialize as `ActorEvidenceRefV1`; it has no HMAC key or memory
payload. Consumed-without-claim burns proof; claimed-without-evidence becomes
terminal; evidence-without-link reconciles the same record; deleted evidence
never permits reissue. Neither store opens the actual cognitive or Privacy DB.

Provisioning is one-time and explicit. Startup validates file mode/UID,
integrity, foreign keys, WAL and FULL sync, metadata, exact schemas and public
fixture. It never creates missing state. The B1b-2b installer must create
parent directories and own the privileged file operations.

## Future OS boundary

The proposed service uses `lilith-memory-broker` with no supplementary
privileges, strict filesystem/network hardening and an inherited socket.
`/run/lilith-memory` must be `root:lilith-memory-ipc 0710`; `owner.sock`
must be `lilith-memory-broker:lilith-memory-ipc 0660`. A future local
`lilith-memory-relay` identity is the only positive client UID. Its `SO_PEERCRED`
proves only the connecting Linux process, not Ravindu or WebAuthn ownership.

The trusted control PR must independently define a closed exact-SHA release
and fixed-purpose root installer. It may be merged under normal protection
only if no VM install occurs. The feature PR itself is not merge-authorized.
No PROD deploy trigger, live credential, real authority, or real memory is
part of B1b-2a.
