# Slice 15B2b-B1b-3b — Broker-only Signing and L04 V2 Verification Adapter

Status:

- **SOURCE IMPLEMENTED**
- **TEST PROVEN**
- **LIVE SIGNING ABSENT**
- **LIVE L04 V2 ADMISSION ABSENT**
- **REAL CUSTODY ABSENT**

This is the second implementation slice of the
[B1b-3 custody isolation design](slice-15b2b-b1b3-custody-isolation-design.md),
built on the [B1b-3a contracts](slice-15b2b-b1b3a-authority-registry-contracts.md)
and the [B2a verifier](slice-15b2b-b2a-accepted-memory-verifier.md). It
is exercised only by synthetic tests. It does **not** mark any of the
following as complete or ready:

- B1b-3;
- Level 2 isolation;
- Privacy custody;
- real owner authority;
- First Memory;
- Stage III.

Every item in the design's *Current implemented debt* table (D1–D8) is still
open. No DEV, PROD, IAM, WIF, systemd, broker, Privacy DB, or live L04 state
was contacted or changed. No real key, credential, owner authority, or memory
was created.

## Property proven

For the V2 path, a compromised application, Hermes instance, model path, or
direct cognitive-DB writer cannot create a V2 admission (`L04_ADMITTED`) or
`ACCEPTED_MEMORY` by writing local rows or by using the old
application-owned HMAC authority. Only evidence signed by the
authority-domain (broker) key and published in the owner-signed registry is
accepted.

| Party | May | May not |
| --- | --- | --- |
| Application | build a proposal (`OwnerEvidenceRequestV1`); receive signed evidence; submit a `V2AdmissionRequestV1` | hold or reach a signing key; choose any signed digest, domain, epoch, or version |
| Broker / authority signer | hold the synthetic private key; own its challenge ledger; sign **after** it has itself verified a consumed owner proof | sign raw memory text, caller-chosen digests, or on a caller-supplied ledger state |
| Verifier / L04 V2 adapter | hold the public registry; verify | sign |

## Location and delivery impact

| Path | Role |
| --- | --- |
| `services/owner-memory-control/lilith_authority_signer/__init__.py` | TEST signer package, physically separate from the verifiers |
| `services/owner-memory-control/lilith_authority_signer/synthetic_broker.py` | `SyntheticBrokerAuthorityV1`, `BrokerSignerConfigV1`, `OwnerEvidenceRequestV1` |
| `services/owner-memory-control/lilith_owner_memory/admission_v2.py` | V2 owner-authority chain, `AdmissionAuthorityLinkV1`, `L04AdmissionViewV1`, `verify_accepted_memory_v2` |
| `services/owner-memory-control/lilith_owner_memory/l04_v2_adapter.py` | `L04V2AdmissionAdapter`, `AdmissionLinkStoreV1`, read-only L04 view |
| `services/owner-memory-control/lilith_owner_memory/verifier.py` | B2a steps 1–6 extracted as `verify_owner_proof` (behaviour-preserving) |
| `services/owner-memory-control/tests/synthetic_b1b3b.py`, `test_b1b3b_broker_signing_l04_v2.py`, `b1b3b_golden.json` | fixtures, tests, vectors |

Delivery impact:

- Nothing is under `services/core-api/**`, so the PROD workflow's path filter
  is **not** triggered.
- Nothing is under `services/memory-broker/`, so the broker file set is
  unchanged.
- The existing Core API CI step runs these tests. Its `compileall` line names
  only `lilith_owner_memory`. The new signer package is compiled when the
  tests import it. `ci.yml` is unchanged.
- A merge to `main` is classified `DEPLOY_REQUIRED` by
  `scripts/classify_dev_deployment.py`, because these paths are neither
  control-only nor broker-candidate paths. That starts a routine DEV
  deployment of the Core API bundle, as after B2a and B1b-3a. The bundle is
  built only from `services/core-api/` (`scripts/build_core_api_bundle.py`),
  so no file from this slice is shipped. No runtime package imports it; tests
  assert this.

## Recovered V1 admission chain (unchanged)

`CanonicalMemoryStoreV2.apply(proposal_ref_id)` (`lilith_memory/canonical_store.py`):

1. It checks the kill switch and replays any existing admission or apply
   audit.
2. It opens a `BEGIN IMMEDIATE` transaction and prevalidates:
   1. resolve the proposal reference (V2 family only);
   2. rebuild the frozen action from the proposal row, and check the
      reference, action-digest, and proposal fingerprints (these cover the
      Actor, Policy, Consent, and Rollback reference IDs);
   3. check the tuple registry (`write_allowed`, value schema), the
      capability provider, and containment readiness;
   4. check the Privacy hold (`is_held` covers both holds and restore
      suppression);
   5. check value normalization and its digest;
   6. `LocalOwnerAuthority.validate_existing(require_consumed=True)`: the
      `actor_evidence_ref` row, an **HMAC-SHA256 fingerprint under the
      application-owned secret**, actor and action binding, the TTL, and a
      matching `actor_evidence_consumption` row;
   7. `MemoryPolicyStore.resolve`: the `policy_decision` row is `ALLOWED`,
      with a fingerprint that is a **plain SHA-256** of its semantics;
   8. `ConsentStore.resolve`: the `consent_grant` row is not revoked, with a
      plain SHA-256 fingerprint, and binds the intent and actor evidence;
   9. exact binding to the learning candidate, assessment, and source rows.
3. It checks preconditions: the item exists or is new, the expected revision,
   and capacity.
4. For RESTORE only, `RollbackAuthority.resolve_and_consume_in_transaction`
   checks the `rollback_authorization` row (plain SHA-256 fingerprint) and
   inserts consumption in the same transaction.
5. It checks the Privacy hold again, then writes `memory_item`,
   `memory_admission`, `memory_revision` (`USER_ASSERTED`,
   `OWNER_DIRECTED_EXACT_ACTION`), the source row, the apply audit, and the
   active pointer. It checks the Privacy hold once more before commit.

Rows L04 trusts:

- Actor evidence and consumption rows. These are protected only by an
  application-held HMAC key.
- Policy, Consent, and Rollback rows. Their SHA-256 fingerprints can be
  recomputed by anyone who can write to the DB. Tests show forged Policy and
  Consent rows resolving `CONFIRMED` (D3).
- The learning proposal, candidate, assessment, source, and intent rows.
- Injected providers and the Privacy resolver.

**Historical compatibility versus new admission authority.** The V1 rows
and HMAC evidence remain how the unchanged store works, and their historical
semantics are untouched. None of them is authority for a V2 NEW admission.

## V1 compatibility rule

- **LEGACY / HISTORICAL V1.** `ActorEvidenceRefV1`, the HMAC verification,
  and the V1 rows are neither deleted nor reinterpreted, and no rows are
  migrated. A test pins that the V1 path still admits exactly as before.
- **NEW V2 ADMISSION.** Only an asymmetric `OwnerEvidenceV2` that verifies
  against the owner-signed registry authorizes.
  - The V2 adapter and acceptance verifier recognise `ActorEvidenceRefV1`
    (as an object or a dict) and the B2a TEST broker envelope. They refuse
    both with `NON_V2_EVIDENCE_NOT_ACCEPTED`.
  - Old V1 evidence is never claimed to carry V2 guarantees.
  - A proposal already admitted through the V1 path cannot later be
    linked to genuine V2 evidence (`L04_NOT_ADMITTED:ALREADY_APPLIED`). This
    prevents laundering.

## Synthetic broker signer

`SyntheticBrokerAuthorityV1(signing_key, config, owner_context, now_fn)`:

- **Key.** An in-process `Ed25519PrivateKey` object supplied by the test,
  with `signingDomain=OWNER_ACTOR` and key `actor.b1b3b-broker-1`.
  - The key is distinct from the registry root, from every B1b-3a key, from
    both B2a broker keys, and from the V1 HMAC secret.
  - It lives in a name-mangled attribute with no accessor.
  - Pickling and copying raise.
  - The package contains no seed literal and reads no disk, environment,
    home directory, or network.
- **Environment.** Construction refuses any environment other than `test`,
  any RP not ending in `.invalid`, a signing-domain name used as the logical
  `authorityDomain`, and an owner context that disagrees with the config.
- **Ledger.** The signer owns its ledger:
  - `prepare_challenge` records the challenge as `PREPARED` and signs
    nothing. It refuses FORGET (`PRIVACY_OWNED_OPERATION`) and any foreign
    environment, authority domain, owner, policy, ledger epoch, or RP.
  - `consume_owner_proof` verifies the WebAuthn assertion with B2a steps
    1–6, then consumes exactly once (B1a semantics). A failed assertion
    leaves the challenge `PREPARED`. An expired challenge becomes `EXPIRED`.
- **Signing.** `issue_owner_evidence(OwnerEvidenceRequestV1)` signs only when
  all of these hold:
  - the challenge is in the signer's own ledger;
  - it is `CONSUMED`;
  - no evidence has been issued for it yet;
  - B2a steps 1–6 re-verify against the signer's **own** ledger row. An
    application-held ledger view is never read; forging it grants nothing.
- **Bindings.** Every signed field comes from verified inputs or the
  signer's config:
  - the consumed owner proof (`credentialRecordId`, `assertionDigest`);
  - `challengeId` and `challengeDigest`;
  - `requestDigest`, `actionDigest`, and `payloadDigest`, taken from the
    verified challenge;
  - `authorityDomain`, `signingDomain`, `environment`, `evidenceType`,
    `registryVersion`, `recoveryEpoch`, `policyVersion`, and
    `logicalOwnerId`;
  - `evidenceNonce == challengeId`;
  - `evidenceId = "aev." + SHA-256(LILITH_B1B3B_OWNER_EVIDENCE_ID_V1\0 ‖ challengeDigest)[:32]`.
- **Refusals.** The signer uses a closed 11-reason refusal taxonomy
  (`SIGNER_REASONS`).

## L04 V2 adapter API

```python
adapter = L04V2AdmissionAdapter(
    store,                     # the unchanged CanonicalMemoryStoreV2
    owner_context=...,         # B2a AcceptanceContextV1 (TEST .invalid RP)
    authority_context=...,     # B1b-3a context; purpose must be NEW_ADMISSION
    registry_provider=...,     # returns the public, owner-signed registry
    link_store=AdmissionLinkStoreV1(),
)
result = adapter.admit(V2AdmissionRequestV1(proposal_ref_id, evidence,
                                            challenge_json, challenge_record,
                                            assertion, owner_credential))
# result.status: L04_ADMITTED | NOT_ACCEPTED (reason, detail)
```

The adapter checks these in order and fails closed at the first miss:

1. The request shape.
2. That evidence is present.
3. That the evidence is not a non-V2 kind.
4. The candidate operation, resolved from the immutable V2 proposal
   reference. The caller never supplies it.
5. That the operation is not FORGET, either in the proposal or in the
   challenge.
6. The Privacy hold and suppression, using L04's own resolver. An
   unavailable resolver is `PRIVACY_STATE_UNAVAILABLE`.
7. The owner proof, B2a steps 1–6, against the resolved action.
8. That the challenge policy equals the authority policy.
9. `verify_owner_evidence` (B1b-3a, `NEW_ADMISSION`), with an expectation
   built from the verified proof and action. This covers the signature, key,
   signing domain, logical authority domain, environment, evidence type,
   epoch, registry version bounds, policy, lifecycle, and downgrade.
10. That the evidence was issued no earlier than the consumption it attests.
11. That the evidence and challenge have not already been linked to an
    admission.
12. `store.apply`. All existing L04 rules run unchanged, including the
    in-transaction Privacy checks.
13. Reading the L04 rows read-only (`mode=ro`), then recording the link.

The V2 reasons form a closed, ordered 20-reason taxonomy
(`admission_v2.REASONS`). `detail` carries the underlying B2a reason, B1b-3a
reason, legacy kind, or L04 outcome.

## Evidence ↔ admission linkage

`AdmissionAuthorityLinkV1` records:

- `proposalRefId`, `admissionId`, `applyAuditId`, `memoryItemId`, and
  `revisionId`;
- `authorityEvidenceId` and `authorityEvidenceDigest` (SHA-256 of the exact
  signed bytes);
- `challengeId`, `actionDigest`, and `payloadDigest`.

It is held in an in-process `AdmissionLinkStoreV1`: one link per proposal,
per evidence, and per challenge.

`L04AdmissionViewV1` is read from the unchanged L04 tables:

- the payload digest is **recomputed from the stored value JSON**, so a
  rewritten value cannot hide behind an unchanged `value_digest` column;
- the epistemic and admission bases are pinned to the constants that the
  L04 V2 apply writes.

**This is TEST-level only.** The L04 schema has no evidence link, and its
schema fingerprint forbids extra objects. A **production schema migration is
required** before any live V2 admission. The link must be written in the same
L04 transaction as the admission, which touches `services/core-api` and
therefore the PROD path. In this slice the link is recorded after L04
commits. A crash in between leaves an admission with no link. Acceptance
refuses that admission (fail closed), and a retry is refused as
`ALREADY_APPLIED`, so the memory is stuck until a reconciliation mechanism
exists.

## Policy, Consent, and Rollback rows: internal state, not authority

- The rows remain, because the unchanged L04 store consumes them. Tests show
  they are still **necessary**: valid V2 evidence plus revoked Consent gives
  `L04_NOT_ADMITTED:REJECTED:CONSENT_REVOKED`.
- They are never **sufficient**. Forged Policy, Consent, Rollback, and
  `ActorEvidenceRefV1` rows, including Policy and Consent rows that resolve
  `CONFIRMED` under V1, admit nothing on the V2 path. L04 is not touched.
- `admission_v2.py` and `l04_v2_adapter.py` never reference the Policy,
  Consent, Rollback, or Actor stores. A static test enforces this.

## B2a acceptance integration

The path is: owner proof → broker-signed `OwnerEvidenceV2` → V2 L04 admission
→ `verify_accepted_memory_v2` → `ACCEPTED_MEMORY`.

- **B2a reuse.** The acceptance verifier reuses B2a steps 1–6 through the
  extracted `verify_owner_proof`, and B2a's `ACCEPTED_MEMORY` result
  constant.
- **Registry replaces broker keys.** B2a's broker-envelope step (a caller key
  map) is replaced by B1b-3a registry verification. B2a's
  `verify_accepted_memory`, its envelope, its 43 reasons, and its vectors are
  unchanged.
- **Independent evidence identity.** The expected evidence identity comes
  from the link, independently of the evidence.
- **Purpose.** Acceptance may run under `NEW_ADMISSION` or
  `HISTORICAL_VERIFICATION`.

The stages stay distinct, and tests assert each boundary:

```text
VERIFIED_AUTHORITY_EVIDENCE  !=  L04_ADMITTED  !=  ACCEPTED_MEMORY  !=  TRUTH
```

- Verified evidence without an admission is `ADMISSION_LINK_MISSING`.
- An admitted row with a broken owner-proof link is `NOT_ACCEPTED`.
- `truthClaim` is always false, and the source epistemic basis
  (`USER_ASSERTED`) is returned unchanged.

## Threat tests

- **Direct DB writer.** The writer:
  - inserts Policy, Consent, Rollback, and `ActorEvidenceRefV1` rows;
  - inserts a complete L04-looking admission (item, revision, admission,
    audit, active pointer);
  - forges link metadata;
  - rewrites the admitted value JSON or the epistemic basis after dropping
    triggers.

  Every case is `NOT_ACCEPTED` with an exact reason. DB access is not
  authority.
- **Old application HMAC key.**
  - The synthetic secret mints V1 evidence that verifies under V1
    semantics.
  - That evidence is refused on the V2 path.
  - It cannot be turned into `OwnerEvidenceV2`: an HMAC tag used as the
    signature, an Ed25519 key derived from the secret, and the secret used
    as an Ed25519 seed all fail (`SIGNATURE_INVALID` or `KEY_UNKNOWN`).
  - A fully V1-forged chain that L04 admits is never `ACCEPTED_MEMORY` on
    the new chain.
- **Privacy.**
  - A hold, a suppression, or an unavailable resolver each fail closed, even
    with valid or forged evidence.
  - L04's in-transaction hold check still applies.
  - Valid `OwnerEvidenceV2` for a FORGET is `PRIVACY_OWNED_OPERATION`.
  - Owner evidence never verifies as a `PrivacyAuthorizationV2`.
  - Privacy authority and the Privacy DB are **not** migrated (B1b-3f).
- **Registry evolution.**
  - In-flight evidence survives a harmless v3→v4 key addition.
  - Later `COMPROMISED` status rejects both pending admission and historical
    acceptance (retroactive).
  - Routine retirement keeps pre-retirement evidence valid and rejects
    later signatures.
  - `signingDomain` and `authorityDomain` are reported separately.
  - No persistent registry history is implemented.

## Evidence

- **Tests.** 42 test methods in `test_b1b3b_broker_signing_l04_v2.py`,
  including a 43-case adapter negative matrix. Each case asserts the exact
  reason and detail and that L04 row counts are unchanged, followed by the
  valid request succeeding. A taxonomy check requires every V2 and signer
  reason to appear in the tests.
- **Suite totals.**
  - owner-memory-control: 113 tests (71 before);
  - Core API: 70 tests;
  - Slice 8–15 regressions: 382;
  - broker CI validation: passed;
  - repository validation: passed.
- **Golden vectors.**
  - `b1b3b_golden.json` holds the stage names, semantics, taxonomies, the
    evidence-ID separator, the broker key record, a broker-signed
    `OwnerEvidenceV2` vector and its digest, and the link and view field
    sets.
  - The SHA-256 of the B1a, B2a, and B1b-3a golden files is pinned
    unchanged.
- **Isolation.** Static tests show:
  - no private-key type, signer import, or seed in `lilith_owner_memory`;
  - no network, environment, subprocess, or config import in the V2
    modules;
  - one read-only SQLite connection in the adapter;
  - a self-contained signer package;
  - no runtime (`services/core-api`, `services/memory-broker`, `scripts`)
    reference to the new modules;
  - verifier entry points that take no key, seed, or signer parameter.

## Stage III implications

Stage III is not touched or retried. The proposed transaction sequence below
supersedes the old claim/evidence topology and is what a future **fresh**
A1–A7 crash design needs:

| Step | Action | Crash point |
| --- | --- | --- |
| S1 | app proposes; broker `prepare_challenge` | A1: challenge/request gap |
| S2 | owner WebAuthn; broker verify + consume | A2: consumed, no evidence yet |
| S3 | broker signs `OwnerEvidenceV2` and marks it issued | A3/A4 collapse if consume + sign + record are one broker transaction; in this TEST signer they are separate calls |
| S4 | app → adapter: verify, then L04 apply | A6: evidence durable, L04 not committed; a retry is permitted (evidence not yet linked) |
| S5 | L04 commit + link | A6′ (TEST only): committed, link not recorded, fails closed; removed by writing the link in the L04 transaction |
| S6 | acknowledgement to broker/owner | A7: committed and linked, acknowledgement lost |
| — | lost response after S3 | A5: the broker must re-deliver the **stored** signed evidence. Signing again would change `issuedAt`. The TEST signer issues once and has no re-delivery. |

## Ambiguities and honest limits

1. **B2a integration shape.** `verify_accepted_memory` takes the B2a envelope
   and a caller key map, which B1b-3a declined to promote. The V2 chain
   therefore uses a V2 acceptance verifier that reuses B2a steps 1–6. Owner
   confirmation requested.
2. **`ledgerEpoch` versus `RecoveryEpochV1`.** The B2a challenge `ledgerEpoch`
   is an opaque broker `authority_epoch`. It is not bound to the B1b-3a
   `RecoveryEpochV1` here; B1b-3c must define the relationship.
3. **`registryTupleVersion` versus `registryVersion`.** The challenge's
   `registryTupleVersion` (a string) and the authority `registryVersion` (an
   integer) are different things and remain unbound.
4. **New policy rule.** The V2 path adds `challenge.policyVersion ==
   authority policy`. The B2a and B1b-3a fixtures used different synthetic
   policy values.
5. **Unsigned proposal reference and basis.** `OwnerEvidenceV2` signs no
   `proposalRefId` and no epistemic basis; the B2a envelope did. Binding is
   by action, request, and payload digests plus single use, and the basis is
   pinned to the L04 V2 constants. A later evidence version may sign both.
6. **Application-held single use.** Evidence single use is enforced only in
   the application-held link store. A DB writer who also forges that store
   could duplicate an admission of the **identical**, already-authorized
   action. Closing this needs an authority-side record: a broker
   acknowledgement (A7) or a signed admission receipt.
7. **V1 apply still callable.** The unchanged V1 `apply` remains callable
   and still admits on V1 rows. The V2 guarantee sits at the adapter and
   acceptance, not at the L04 write barrier. Moving it into L04 changes
   `services/core-api`, and therefore the PROD path.
8. **Read facade.** The L04 read facade does not consult V2 acceptance.
9. **Signer registry version.** The signer's `registryVersion` is static
   config. A real broker must track registry publication.
10. **Grounding evidence for Privacy.** B1b-3a allows owner evidence over a
    FORGET action digest, as grounding evidence for Privacy. The adapter
    refuses such evidence and the TEST signer does not issue it. How grounding
    evidence is produced is B1b-3f.
11. **Link written after commit.** A production migration is required (see
    *Evidence ↔ admission linkage*).

## Explicitly not done

- No DEV or PROD contact; no IAM, WIF, or systemd change.
- No real key, registry signer, credential, owner authority, or memory.
- No live broker, live L04, or Privacy DB change; no migration of old rows.
- No WebAuthn enrollment and no activation.
- No Stage III retry, and the preserved Stage III authorization is not
  consumed.
- No B1c authority change and no deployment-filter change.
