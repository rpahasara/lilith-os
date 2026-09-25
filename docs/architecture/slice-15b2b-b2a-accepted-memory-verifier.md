# Slice 15B2b-B2a — Accepted-Memory Contract and Verifier

Status: **SOURCE IMPLEMENTED / TEST PROVEN. LIVE AUTHORITY ABSENT.**

This is the first implementation slice of the
[15B2b-B Owner Memory Control design](slice-15b2b-b-owner-memory-control-design.md).
It defines contracts and a pure verifier, exercised only by synthetic tests. It
does **not** mark 15B2b-B, B1b-3, real owner authority, or First Memory as
complete or ready, and it proves nothing about Stage III.

## Location and delivery impact

The code lives in `services/owner-memory-control/`:

- `lilith_owner_memory/contracts.py`
- `lilith_owner_memory/verifier.py`
- `tests/`

It imports the canonical B1a (`lilith_memory.owner_proof`) and 15B2a
(`lilith_memory.canonical_contracts`) modules unchanged.

It deliberately sits outside two paths:

- **`services/core-api/**`**, whose changes trigger the PROD workflow.
- **`services/memory-broker/`**, whose exact file set is enforced by broker
  validation.

No DEV bundle, broker release, workflow deployment step, or VM state includes
or uses it. Core API CI compiles the package and runs its tests.

## Contracts

- **`OwnerMemoryChallengeV2`**
  - Protocol `LILITH_OWNER_MEMORY_PROOF`, `schemaVersion` 2, domain separator
    `LILITH_OWNER_MEMORY_CHALLENGE_V2\x00`.
  - Canonical bytes are RFC 8785 JSON. The WebAuthn challenge is
    `SHA-256(separator ‖ canonical bytes)`.
  - It carries the 21 B1a fields, validated by the unchanged V1 contract, plus
    six logical authority fields:
    - `deploymentEnvironment` (`test` \| `dev` \| `prod`);
    - `authorityDomain`;
    - `logicalOwnerId`;
    - `policyVersion`;
    - `registryTupleVersion`;
    - `ledgerEpoch`, an opaque identifier equal to the broker ledger's
      `authority_epoch`.
  - It has no host, VM, instance, process, broker-key, or identity-charter
    field; charter binding remains a deferred extension. V1 and V2 never
    interchange.
- **`BrokerMemoryEvidenceEnvelopeV1`**
  - Protocol `LILITH_BROKER_MEMORY_EVIDENCE`, schema 1, domain separator
    `LILITH_BROKER_MEMORY_EVIDENCE_V1\x00`, Ed25519 signature over the
    canonical unsigned fields.
  - It binds evidence ID and nonce (the nonce must equal `challengeId`,
    following B1b-1), the challenge digest, the owner-proof reference
    (credential record plus assertion digest), the proposal ref, the
    action/request/payload digests, the epistemic basis, the logical
    authority context, `brokerKeyId`, `brokerRelease`, and `issuedAt`.
- **`BrokerVerificationKeyV1`**: public Ed25519 key, scoped to one environment
  and authority domain, with `ACTIVE`/`REVOKED` status.
- **`OwnerChallengeLedgerRecordV2`** and **`CanonicalAdmissionRecordV1`**:
  TEST-ONLY typed views of the B1a durable challenge row plus ledger epoch, and
  of the L04 terminal admission/apply audit. The admission's `brokerEvidenceId`
  link is a PROPOSED provenance extension.
- **`AcceptanceContextV1`**: trusted caller expectations. It is never read from
  artifacts.

## Verifier

`verify_accepted_memory(...)` returns `ACCEPTED_MEMORY` only when the complete
chain verifies:

1. the trusted context;
2. the frozen action;
3. the V2 challenge's canonical bytes and its logical context;
4. challenge-to-action binding;
5. the durable challenge was `CONSUMED` by this credential inside its window;
6. the owner credential and the unchanged B1a WebAuthn sequence;
7. broker evidence: key scope, signature, revocation, release allowlist;
8. evidence binding to the exact owner proof and challenge;
9. the L04 admission and provenance.

Otherwise it returns `NOT_ACCEPTED(reason)`, drawn from a closed, ordered
43-reason taxonomy (`verifier.REASONS`).

The verifier writes nothing, mints nothing, infers or repairs nothing, and uses
no model, runtime, network, environment variable, or file. In this slice it
refuses any context other than `deploymentEnvironment=test` with a `.invalid`
relying party.

A positive result means the chain establishes that the operation was owner
authorized, broker attested, and L04 admitted. It is not a truth claim:
`truthClaim` is always false, and the epistemic basis is returned unchanged.

Revocation of an owner credential or broker key after use is reported, not
applied retroactively. Broker-key rotation leaves owner authorizations valid.

## Evidence

The tests use only synthetic `.invalid` credentials and in-process test keys:

- golden vectors for V2 (CREATE/SUPERSEDE/RESTORE/FORGET) and a deterministic
  evidence vector;
- V1 constants and golden-file bytes pinned;
- an 89-case tamper matrix asserting the exact reason for every entry, and
  covering every reason in the taxonomy;
- every signed challenge field mutated after signing is rejected;
- forbidden equalities (model output, proposal, row, apply, execution, broker
  evidence alone, owner proof alone, cached flag, matching value) are all
  `NOT_ACCEPTED`;
- `USER_ASSERTED` and the other bases survive acceptance unchanged;
- content-type genericity, with no affect model;
- no model, runtime, or I/O dependency.

## Explicitly not done

- No B1b-3 custody move: Actor, Privacy, and containment keys stay where they
  are.
- No broker integration, no live broker change, no enrollment, no real key,
  grant, credential, or memory, and no activation.
- No Stage III action.
- No IAM, WIF, DEV, or PROD change.
