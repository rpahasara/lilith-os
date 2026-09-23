# Slice 15B2b-B1b-1 — isolated broker software foundation

Status: local implementation candidate, **synthetic only**. This record does
not authorize merge, service installation, PROD deployment, OS custody, real
enrollment, or real canonical memory.

## Owner and request contracts

`owner.ravindu.v1` is the stable logical owner ID. A Google OS Login identity
may later be mapped as an access identity, but it is not the owner ID and is
not enrolled by this slice. The only executable fixture uses
`user:synthetic-owner@example.invalid`; no real credential or RP/origin is
selected.

`OwnerRequestV1` is a closed object containing exactly `protocol`,
`schemaVersion`, `challengeId`, `logicalOwnerId`, `accessIdentity`,
`actorRefId`, `action`, `actionDigest`, `memoryItemId`,
`expectedActiveRevisionId`, `restoreTargetRevisionId`,
`restoreTargetDigest`, `privacyNoticeVersion`, `intentRefId`, `operation`,
`purpose`, `memoryClass`, `subjectNamespace`, and `subjectKey`. `action` is
exactly the existing `FrozenMemoryActionV1.semantic_dict()` fields. Duplicated
top-level fields must equal that action; unknown/missing fields fail closed.
Only broker code constructs the one governed synthetic action. The action
digest continues to use the *unchanged* canonical-contract serialization.

The broker request digest is lowercase SHA-256 of:

```text
ASCII("LILITH_OWNER_MEMORY_REQUEST_V1") || 0x00 ||
RFC8785_UTF8(OwnerRequestV1.to_dict())
```

The signed B1a challenge stores this exact digest, the B1a verifier receives
it as `expected_request_digest`, and the synthetic handoff passes it without
normalization to `LocalOwnerAuthority.issue`. The fixture golden vector is
`services/memory-broker/tests/owner_request_golden.json`.

## Protocol and state

The V1 parser accepts exactly one four-byte big-endian length-prefixed,
RFC8785-canonical JSON envelope of at most 16 KiB: `protocol`,
`schemaVersion`, `operation`, `payload`. It rejects duplicate fields,
noncanonical bytes, trailing data, unknown versions/operations, and excess
payload fields. Operations are only `HEALTH`, `ACCESS_CONTEXT`,
`PREPARE_SYNTHETIC`, `CONFIRM_SYNTHETIC`, and `CANCEL`. No socket or listener
exists. No real memory verb, SQL, path, module selector, or model approval is
accepted. `ACCESS_CONTEXT` explicitly labels its assurance as unverified.

The separate `owner_control.db` V1 schema contains:

- `broker_schema_v1`: version, schema fingerprint, `SYNTHETIC_TEST` or
  `PRODUCTION_GOVERNED` mode, recovery epoch, creation time;
- `owner_identity_v1` and `owner_access_identity_v1`: logical owner and
  separately governed access mapping substrate;
- B1a-compatible `owner_proof_challenge_v1` and closed
  `owner_request_v1` with canonical request bytes/digest;
- `owner_credential_v1`: public-only `OwnerCredentialV1` JSON; a compatibility
  view/trigger supplies B1a's existing credential lookup/counter update;
- `owner_authority_claim_v1`: unique `challenge_id`, exact request/action
  digests, `CLAIMED`/`EVIDENCE_COMMITTED`/`ABANDONED`, unique optional evidence
  reference, and timestamps/failure code.

All broker SQLite connections require WAL, `synchronous=FULL`, foreign keys,
and a 5-second busy timeout. Startup checks file existence/mode, integrity,
foreign keys, exact schema fingerprint/version/mode, logical owner, and public
credential shape. It never initializes a missing production ledger. Only an
explicit test initializer under the OS temp directory with `LILITH_ENV=test`
may create state and install `.invalid` public credentials. There is no
production ledger initializer or enrollment endpoint in B1b-1. A restored
ledger epoch policy remains an operational B1b-2/B1b-3 gate.

## Proof-to-authority crash model

The B1a verifier alone consumes a prepared challenge at decisive post-crypto
time. Its `VERIFIED_PROOF_ONLY` result is broker-internal and never serialized
as a capability. The broker commits a one-time claim keyed by `challengeId`
*before* calling the synthetic `LocalOwnerAuthority.issue`, passing
`nonce=challengeId`. The cognitive Actor table already enforces unique nonce.
There is no transaction spanning the two SQLite databases.

| Crash point | Conservative recovery |
| --- | --- |
| Before proof consumption | Original PREPARED/cancel/expiry behavior. |
| Consumed, no claim | Burn proof; require new confirmation. |
| Claim, no evidence | Never issue again; mark terminal/abandoned. |
| Evidence committed, no linkage | Find by unique nonce, validate exact action/request evidence, link the **same** evidence. |
| Link committed | Return bounded completion status; no new evidence. |

If Actor evidence is missing after Privacy erasure, recovery never reissues.
If existing evidence cannot validate (including expiry), it remains unusable
and is never replaced from the consumed proof. Deterministic fault hooks and
barrier-based concurrent tests cover these points in temporary databases.
The synthetic test credential's private scalar stays in B1a test code; it is
not part of broker state, logs, responses, or a bundle.

## Explicit exclusions and trusted-control gate

No broker Unix account/group, systemd unit/socket, relay, IAM change, PROD
installation/restart, DB or key ownership move, real RP/origin, authenticator
enrollment, real Owner authority, or REMEMBER/CORRECT/RESTORE/FORGET operation
is implemented. Operational Level 2 isolation is **not** achieved.

Existing repository CI compiles/runs Core API tests but does not discover
`services/memory-broker/tests`. The trusted exact-SHA DEV bundle allowlist in
`scripts/build_core_api_bundle.py` excludes the new package. A separate
minimal trusted-control bootstrap must add broker dependency/test/compile
coverage and explicitly attest broker source/tests in the DEV validation
path, while preserving the current PROD path filter and darkness audit. The
candidate must not edit its own trusted workflow or claim DEV validation.
