# Slice 15B2b-B1b-3a — Authority Evidence and Key Registry Contracts

Status: **SOURCE IMPLEMENTED / TEST PROVEN. LIVE CUSTODY ABSENT.**

This is the first implementation slice of the
[B1b-3 custody isolation design](slice-15b2b-b1b3-custody-isolation-design.md).
It defines contracts and a pure verifier, exercised only by synthetic tests.
It does **not** mark any of the following as complete or ready:

- B1b-3;
- Level 2 isolation;
- real owner authority;
- real memory;
- Privacy custody.

It proves nothing about Stage III.

Every item in the design's *Current implemented debt* table (D1–D8) is still
open.

## Location and delivery impact

The code lives in `services/owner-memory-control/`, next to B2a:

- `lilith_owner_memory/authority_contracts.py`
- `lilith_owner_memory/authority_verifier.py`
- `tests/synthetic_authority.py`
- `tests/test_authority_registry_contracts.py`
- `tests/authority_b1b3a_golden.json`

It sits outside two paths:

- **`services/core-api/**`**, whose changes trigger the PROD workflow.
- **`services/memory-broker/`**, whose exact file set is enforced by broker
  validation.

The existing Core API CI step already compiles this package and runs its
tests. Nothing in the broker, L04, the Privacy DB, systemd, DEV, or PROD
imports or uses it; a test asserts that no runtime package imports it.

B2a (`contracts.py`, `verifier.py`, and its golden file) and the B1a V1
contracts are unchanged. B1b-3a reuses only the RFC 8785 canonicalization and
the B1a field validators. It does not promote `BrokerVerificationKeyV1`,
caller-supplied broker key maps, B2a's revoked-after-issuance acceptance, or
the TEST-only admission record.

## Contracts

**Domain separators** (frozen in golden vectors):

| Artifact | Separator |
| --- | --- |
| Registry | `LILITH_AUTHORITY_REGISTRY_V1\x00` |
| Owner/Actor evidence | `LILITH_ACTOR_EVIDENCE_V2\x00` |
| Privacy authorization | `LILITH_PRIVACY_AUTHORIZATION_V2\x00` |

Each signature is Ed25519 over `separator ‖ RFC 8785 canonical bytes` of every
field except `signature`.

**Authority domains** are a closed set: `OWNER_ACTOR` (evidence type
`OWNER_MEMORY_OPERATION`) and `PRIVACY` (evidence type
`PRIVACY_ERASURE_AUTHORIZATION`). Containment is not an authority domain.

- **`RecoveryEpochV1`** — `{counter, random}`. `counter` is a JSON-safe
  integer of at least 0. `random` is 32 lowercase hex characters. Two epochs
  are equal only when both parts are equal, so divergent restores to the same
  counter stay distinguishable.
- **`AuthorityKeyRecordV1`** — `schemaVersion` (1), `keyId`,
  `authorityDomain`, `evidenceTypes`, `environment`, `algorithm`,
  `publicKey`, `createdAt`, `notBefore`, `retiredAt`, `revokedAt`,
  `revocationReason`, `compromisedSince`, `recoveryEpoch`, `policyVersion`,
  `registryVersion`.
  - `evidenceTypes` is a sorted, non-empty subset of the key's own domain.
  - `algorithm` must be `Ed25519`.
  - `publicKey` is 32 bytes, base64url.
  - `revocationReason` is `ROUTINE`, `COMPROMISED`, or `SUPERSEDED`.
    `COMPROMISED` holds if and only if `compromisedSince` is set, and
    `compromisedSince` must not be later than `revokedAt`.
  - `registryVersion` is the registry version that first published the key.
- **`AuthorityRegistryV1`** — `protocol` (`LILITH_AUTHORITY_REGISTRY`),
  `schemaVersion` (1), `environment`, `registryVersion`, `recoveryEpoch`,
  `policyVersion`, `registryRootKeyId`, `issuedAt`, `keys`, and `signature`.
  The signature binds the exact contents, schema, environment, registry
  version, recovery epoch, and policy version. Registry invariants:
  - key IDs are strictly ascending;
  - public keys are unique, so no key serves two roles or domains;
  - every record's environment equals the registry's;
  - no record timestamp is later than `issuedAt`;
  - no record is from a future or forked epoch;
  - a current key (neither retired nor revoked) must be in the current epoch
    and policy version;
  - the registry root's public key never appears as an authority key.
- **`TrustedRegistryRootV1`** — the caller's trust anchor: `rootKeyId`,
  `environment`, `Ed25519` public key. It is a separate synthetic signer, not
  the B1c activation key, an owner key, or a WebAuthn credential. B1b-3a
  refuses any root whose ID does not begin `test-only.`; a real root needs a
  new, reviewed contract version.
- **`OwnerEvidenceV2`** — `protocol` (`LILITH_ACTOR_EVIDENCE`),
  `schemaVersion` (2), `evidenceId`, `evidenceNonce`, `challengeId`,
  `challengeDigest`, `credentialRecordId`, `assertionDigest`, `actionDigest`,
  `requestDigest`, `payloadDigest`, `authorityDomain`, `evidenceType`,
  `environment`, `logicalOwnerId`, `keyId`, `registryVersion`,
  `recoveryEpoch`, `policyVersion`, `issuedAt`, and `signature`.
  `evidenceNonce` must equal `challengeId`, as in B1b-1.
- **`PrivacyAuthorizationV2`** — `protocol`
  (`LILITH_PRIVACY_AUTHORIZATION`), `schemaVersion` (2), `authorizationId`,
  `executionNonce`, `forgetRequestId`, `holdId`, `ownerEvidenceId`,
  `memoryClass`, `subjectNamespace`, `subjectKey`, `memoryItemId`,
  `actionDigest`, `resourceOwners` (sorted, unique), `authorityDomain`,
  `evidenceType`, `environment`, `logicalOwnerId`, `keyId`,
  `registryVersion`, `recoveryEpoch`, `policyVersion`, `issuedAt`, and
  `signature`. The field set follows the 15B2a `ErasureAuthorizationV1`;
  `ownerEvidenceId` replaces the HMAC-era actor evidence reference.
- **`AuthorityVerificationContextV1`** — trusted caller input: `environment`,
  `purpose` (`NEW_ADMISSION` \| `HISTORICAL_VERIFICATION`), `registry_root`,
  `trusted_minimum_registry_version`, `expected_recovery_epoch`,
  `policy_version`. The expectation types (`OwnerEvidenceExpectationV2`,
  `PrivacyAuthorizationExpectationV2`) carry what the caller has already
  verified independently.

## Verifier

- `verify_authority_registry` returns `VERIFIED_REGISTRY` or
  `NOT_ACCEPTED(reason)`.
- `verify_owner_evidence` and `verify_privacy_authorization` return
  `VERIFIED_AUTHORITY_EVIDENCE` or `NOT_ACCEPTED(reason)`.
- Reasons come from a closed, ordered 43-reason taxonomy
  (`authority_verifier.REASONS`).

The registry signature is verified before any record content is trusted.

A positive result is **not** `ACCEPTED_MEMORY`. Its facts always carry
`memoryAcceptance: false`, `truthClaim: false`, and `authorizesNewAdmission`,
which is true only for `NEW_ADMISSION`.

**Semantics:**

- **Routine retirement, and non-compromise revocation.**
  - Under `HISTORICAL_VERIFICATION`, evidence is valid only when
    `notBefore ≤ issuedAt < retiredAt` (or `< revokedAt`).
  - A retired or revoked key never supports `NEW_ADMISSION`
    (`KEY_RETIRED` / `KEY_REVOKED`).
- **Compromise** is retroactive: `KEY_COMPROMISED` for every piece of evidence
  the key signed, in every purpose, whatever its signer-controlled `issuedAt`.
  Re-attestation is not implemented.
- **Environment, domain, and type.**
  - Cross-environment use is always rejected, whether through the registry,
    the key record, or the evidence.
  - The evidence domain and type must match the contract, and the key's
    domain and types must match the evidence.
  - Actor keys never verify Privacy authorizations, and Privacy keys never
    verify Actor evidence.
- **Epoch.**
  - Evidence must be in its key's epoch.
  - `NEW_ADMISSION` also requires the context's expected epoch.
  - Old-epoch evidence verifies only as history.
- **Registry version.**
  - Evidence must satisfy
    `key.registryVersion ≤ evidence.registryVersion ≤ registry.registryVersion`.
  - `NEW_ADMISSION` requires equality with the current registry version.
  - A registry below `trusted_minimum_registry_version` is `REGISTRY_DOWNGRADE`.
- **Policy version.** Evidence must carry its key's policy version.
  `NEW_ADMISSION` also requires the context's policy version.

**Honest limits:**

- The verifier detects stale-epoch evidence only against a trusted expected
  epoch. It does not provide witness files or runtime restore behaviour.
- It does **not** detect whole-host or whole-disk rollback.
- Where the trusted minimum registry version comes from is out of scope. Local
  filesystem state is not assumed to be a monotonic authority.

## Evidence

- Golden vectors for:
  - the registry, `OwnerEvidenceV2`, and `PrivacyAuthorizationV2` (full signed
    artifacts plus signing digests);
  - nine frozen outcomes: retirement accepted as history, retirement rejected
    for new admission, backdated compromise, old epoch as history only, old
    epoch rejected for new admission, three cross-domain cases, and a
    cross-environment replay.
- A 131-case negative matrix that asserts the exact reason for each case and
  covers every reason in the taxonomy.
- A mutation of every signed registry and evidence field is rejected.
- Pinned B2a golden file and B1a/B2a separators; the new separators are
  distinct from each other and from the B1a/B2a separators (seven in total).
- An isolation scan:
  - no private-key type, file, environment, network, SQLite, broker, L04, or
    Privacy import in the contract modules;
  - all fixture keys are distinct TEST_ONLY seeds, the registry root differs
    from every authority key and from B2a's synthetic broker key, and no
    runtime package imports the modules.

## Explicitly not done

- No keys on disk, no real registry signer, and no real credentials.
- No broker runtime change, no L04 runtime change, and no Privacy DB or
  selector PRF movement.
- No systemd, IAM, WIF, DEV, or PROD change.
- No Stage III action.
- No real owner authority or memory.
