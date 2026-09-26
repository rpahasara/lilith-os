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
| `services/owner-memory-control/lilith_owner_memory/l04_v2_adapter.py` | `L04V2AdmissionAdapter`, `V2AdmissionActorGate`, `v2_admission_store`, `AdmissionLinkStoreV1`, read-only L04 views |
| `services/owner-memory-control/lilith_owner_memory/accepted_read_v2.py` | `AcceptedMemoryReadFacadeV2`: accepted-memory read boundary and labelled historical V1 read |
| `services/owner-memory-control/lilith_authority_signer/synthetic_evidence_ledger.py` | `SyntheticEvidenceUseLedgerV1`: authority-side evidence single use |
| `services/owner-memory-control/lilith_owner_memory/verifier.py` | B2a steps 1–6 extracted as `verify_owner_proof` (behaviour-preserving) |
| `services/owner-memory-control/tests/synthetic_b1b3b.py`, `test_b1b3b_broker_signing_l04_v2.py`, `test_b1b3b_hardening.py`, `b1b3b_golden.json` | fixtures, tests, vectors |

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
store = v2_admission_store(unchanged_store)   # V2 admission mode (Actor gate)
adapter = L04V2AdmissionAdapter(
    store,
    owner_context=...,         # B2a AcceptanceContextV1 (TEST .invalid RP)
    authority_context=...,     # B1b-3a context; purpose must be NEW_ADMISSION
    registry_provider=...,     # returns the public, owner-signed registry
    link_store=AdmissionLinkStoreV1(),          # app-held metadata
    evidence_use_ledger=authority_side_ledger,  # broker/authority domain
    fault_hook=None,           # TEST seam: before_apply, after_l04_commit,
)                              #            after_link, after_confirm
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
11. An **authority-side reservation** of the evidence, bound to this
    proposal (`EVIDENCE_ALREADY_CONSUMED` otherwise).
12. `store.apply`, run inside the gate's one-shot window for exactly this
    action. All existing L04 rules run unchanged, including the
    in-transaction Privacy checks. If L04 does not admit, the reservation
    becomes `ABANDONED`.
13. Reading the L04 rows read-only (`mode=ro`), binding them, recording the
    link and the public chain artifacts, and then **confirming** the
    authority-side consumption for exactly this admission.

The V2 reasons form a closed, ordered 24-reason taxonomy
(`admission_v2.REASONS`). `detail` carries the underlying B2a reason, B1b-3a
reason, legacy kind, ledger state, or L04 outcome.

## Pre-PR hardening

Section numbers follow the pre-PR hardening review items. Item 8 (deferrals) is in
*Deferred to B1b-3c*, item 10 is in *Stage III implications and future sequence*, and item 11 is in
*Required invariants*. The hardening uses the canonical
[Cognitive Continuity research charter](../research/charters/lilith-cognitive-continuity-research-charter-v0.1.md)
as its governing reference (storage ≠ acceptance, memory ≠ truth, historical preservation ≠ active recall,
execution ≠ verification). The charter is unchanged.

### 1. V1 new-write escape hatch

**Call graph (`CanonicalMemoryStoreV2.apply`), inspected, not assumed:**

| Caller | Nature |
| --- | --- |
| `services/core-api/app.py` (PROD API) | **Never imports** `lilith_memory` canonical modules. PROD installs only `app.py` (15B2b-A: PROD DARK, capability inactive, empty registry). |
| `scripts/run_core_api_dev_durability_probe.py` | Trusted DEV-only synthetic durability probe run by the fixed DEV helper, with its own probe key and probe paths. It uses the V1 path. |
| core-api tests; the 15B1 and 15B2a artifacts under `docs/architecture/` | Tests and archived artifacts, not runtime |
| `services/memory-broker` | Uses `LocalOwnerAuthority` only in its TEST-mode synthetic broker. It never calls `apply`. |
| `lilith_owner_memory.l04_v2_adapter` | The V2 path |

**Findings:**

- **No route exists.** No production route reaches V1 admission today.
- **The capability exists.** Any in-process code holding the application
  HMAC key and the DB could still call `apply` on an ordinary store, and
  would create a NEW row.
- **Nothing distinguishes the two.** Historical V1 verification and new V1
  admission were indistinguishable.
- **Rows would be served.** The unchanged `CanonicalMemoryReadFacade` would
  serve such a row.

So V1 new admission was reachable in code.

**Correction (TEST/source, `services/owner-memory-control` only):**

- `V2AdmissionActorGate` and `v2_admission_store(store)` put an unchanged
  store into **V2 admission mode**. The gate replaces only the store's Actor
  authority. It refuses every NEW-admission `validate_existing` except inside
  the adapter's own apply of the action it has just verified.
  - A direct `apply` on a V2-mode store, even with valid HMAC Actor evidence
    and every V1 row, is `REJECTED:ACTOR_UNRESOLVED` by L04 itself.
  - `verify_historical_v1` keeps HISTORICAL_V1 verification, with its
    unchanged semantics.
- The adapter refuses any store that is not in V2 admission mode.
- A static test requires the set of runtime `.apply(` callers to be exactly
  the DEV probe and the V2 adapter. It also checks that `app.py` never
  imports `lilith_memory`.

**Guarantee established:**

- NEW_ADMISSION through a V2-mode store requires V2 authority.
- No runtime caller reaches V1 admission except the allow-listed trusted DEV
  probe, which writes synthetic V1 rows only.
- Any row an unguarded store writes is storage only: never `L04_ADMITTED`,
  never `ACCEPTED_MEMORY`, never an accepted read.

**Not established:** a write barrier *inside* L04. That would change
`services/core-api`, which is the PROD path, and is left to a later,
separately authorized change.

### 2. Accepted-memory read boundary

`AcceptedMemoryReadFacadeV2` (`accepted_read_v2.py`):

- **`read_accepted`** returns a row as `ACCEPTED_MEMORY` (`readClass:
  ACCEPTED_V2`, `truthClaim: false`) only when two conditions hold:
  - the unchanged L04 read facade returns it (actor, tuple registry, Privacy
    hold and suppression, and Consent revision);
  - the complete V2 chain for the revision that created that row
    re-verifies under HISTORICAL_VERIFICATION:
    - owner proof, evidence, and registry;
    - the linked admission;
    - the authority-side evidence-use record;
    - the active revision equals the chain's revision.
- **`read_historical_v1`** is a separate path, labelled
  `HISTORICAL_V1_UNVERIFIED_FOR_V2`, with `accepted_memory` and `truth_claim`
  both false.
- **Raw access.** `get_active` remains raw storage and debug access.

These are all excluded from accepted reads, and tested:

- no row;
- a V1-only row;
- a complete forged row set;
- a forged revision under an invented proposal;
- an active revision that disagrees with the chain;
- a later V1 supersede;
- an admission with a missing link or missing authority confirmation;
- an active Privacy hold;
- revoked Consent.

`storage ≠ acceptance`: tests show the unchanged L04 facade *would* return
forged and V1-only rows that the V2 facade refuses. The facade is not wired
into any production route.

### 3. Evidence single use (authority side)

Invariant: **one authority evidence instance must not create more than one
independent durable effect.**

`lilith_authority_signer.synthetic_evidence_ledger.SyntheticEvidenceUseLedgerV1`
belongs to the broker/authority domain, separate from the signer object and
from every application store. Each evidence ID and digest moves through:

```text
(absent) → RESERVED(proposalRefId) → CONSUMED(admissionId, revisionId)
                                   → ABANDONED
```

- **No reuse.** A second `reserve` is refused in every state.
- **Tamper resistance.** Callers get copies. There is no reset or delete,
  and pickling and copying raise.
- **Acceptance.** `verify_accepted_memory_v2` now requires the ledger
  record, which must show `CONSUMED` by exactly the linked proposal,
  admission, and revision. The app-held link store is no longer a
  single-use authority.

**Replay tests.** Each of these is refused deterministically, with L04
counts unchanged:

- an exact replay (repeated);
- a replay against another admission;
- a replay after the application wipes its link metadata;
- a forged duplicate admission record (`EVIDENCE_USE_MISMATCH`);
- a missing ledger record (`EVIDENCE_USE_MISSING`);
- a replay after an L04 refusal (`ABANDONED`).

**Durability.** The ledger is in memory. B1b-3d and production broker
custody need **durable authority-side storage** outside application custody,
with restore semantics from B1b-3c.

### 4. `proposalRefId` and epistemic-basis binding graph

```text
OwnerEvidenceV2.signature ─ covers ─┬─ challengeDigest = SHA-256(V2 challenge)
                                    │    challenge ⊇ actionDigest, payloadDigest, requestDigest,
                                    │                operation, class/namespace/key, purpose,
                                    │                expected/restore revision, memoryItemId,
                                    │                authority context, nonce, expiry
                                    ├─ actionDigest = SHA-256(FrozenMemoryActionV1 semantic dict:
                                    │    actorRefId, operation, class, namespace, key, valueSchema,
                                    │    payloadDigest, expected/restore revision, purpose)
                                    ├─ payloadDigest (L04 re-normalizes the stored value to it)
                                    └─ requestDigest (opaque owner request)

proposalRefId ─ L04 proposal fingerprint covers the action ─→ actionDigest
              ─ learning_candidate_v2.action_digest is UNIQUE ─→ one candidate/proposal per action
              ─ authority ledger RESERVED(proposalRefId) at first use
epistemicBasis ─ fixed by L04 apply ("USER_ASSERTED", "OWNER_DIRECTED_EXACT_ACTION");
                 no proposal column can select it; acceptance pins both
```

- **`proposalRefId`.** It is not directly signed, but it cannot be
  substituted to change the admitted operation:
  - the adapter resolves the action from the proposal and requires its
    digest to equal the evidence's `actionDigest`;
  - L04's UNIQUE `learning_candidate_v2.action_digest` means a second
    proposal with an identical action cannot exist (tested:
    `IntegrityError`);
  - the authority-side ledger records the proposal at first use.

  Tests: a different-action proposal is `OWNER_PROOF_REJECTED`; creating an
  identical-action twin fails; the ledger binds the first proposal. No
  contract field is added.
- **`epistemicBasis`.** It is intentionally **not** owner-selectable. L04's
  V2 apply writes fixed bases, the proposal schema has no basis column
  (tested), and acceptance pins both values and refuses a rewritten basis.
  Authority to record a claim is not the truth of the claim: acceptance
  never sets `truthClaim`.

### 5. Post-commit link crash: fail-closed proof

TEST fault injection. Production atomicity is **not** claimed.

| Point | Injected where | Durable state after crash | Acceptance / accepted read | Retry |
| --- | --- | --- | --- | --- |
| A — before L04 commit | L04 `before_commit` hook | none (L04 rolled back); ledger `RESERVED` | not readable | deterministic `EVIDENCE_ALREADY_CONSUMED:RESERVED` |
| A′ — after reservation, before apply | adapter `before_apply` | none; ledger `RESERVED` | not readable | same |
| B — after L04 commit, before link | adapter `after_l04_commit` | L04 row exists (raw read sees it); no link; ledger `RESERVED` | `ADMISSION_LINK_MISSING`; excluded from accepted reads | same, repeated; no second item or audit |
| B′ — after link, before authority confirmation | adapter `after_link` | row + link; ledger `RESERVED` | `EVIDENCE_USE_MISMATCH`; excluded | same |
| C — after link and confirmation, before verification | adapter `after_confirm` | complete | `ACCEPTED_MEMORY`; returned | `EVIDENCE_ALREADY_CONSUMED:CONSUMED` |

- **What A and B cost.** They burn the owner authorization: the owner
  re-authorizes. They never create a second independent durable effect.
- **The B row.** It stays stored-but-not-accepted until a reconciliation
  mechanism exists.
- **Production fix.** Atomic production linkage (link and authority
  acknowledgement in the L04 transaction, or an equivalent protocol)
  requires a later schema/transaction migration and a crash rehearsal.

### 6. Policy / Consent / Rollback

Earlier coverage is retained: forged rows resolve under V1 but never produce
V2 authority or `ACCEPTED_MEMORY`. The accepted read facade does not return
a row whose only support is internal rows, including complete, valid V1 rows
applied by an unguarded store.

Valid V2 authority does not override:

- a real Privacy hold (at admission and at read);
- revoked Consent (at admission, where L04 rejects, and at read, where the
  row is excluded).

### 7. B2a integration review

A new test runs every one of B2a's 89 tamper-matrix cases through both
`verify_accepted_memory` and the extracted `verify_owner_proof`:

- whenever steps 1–6 fail, both return the **same** reason;
- whenever steps 1–6 pass, the full verifier fails only later, never with a
  reason that only steps 1–6 produce. (`MALFORMED_ARTIFACT` and
  `UNSUPPORTED_SCHEMA_VERSION` can also arise in steps 7–9.)

The following are unchanged:

- B2a's `REASONS` (43, in the same order), challenge parsing
  (`parse_challenge_v2` wraps the same function), evidence binding, and
  facts;
- `truthClaim: false` and the returned epistemic basis;
- the B1a, B2a, and B1b-3a golden hashes.

In V2, `memoryAcceptance: false` stays on authority and admission facts, and
only `verify_accepted_memory_v2` produces `ACCEPTED_MEMORY`.

**Result: equivalent. This integration shape is IMPLEMENTED/TEST PROVEN for
B1b-3b, pending review.**

### 9. Policy-equality rule

`challenge.policyVersion == authority_context.policy_version` (the registry
and evidence policy):

- **Not required by an existing canonical contract.** The 15B2b-B design
  lists `policyVersion` in the V2 challenge, and B1b-3 binds keys to a
  policy version. No contract relates the two.
- **Decision.** Kept as a **sound new B1b-3b binding**: the owner approves
  an operation under a policy, and the authority evidence must be issued
  under the same policy. Otherwise evidence minted under one policy could
  authorize an owner approval given under another.
- **Label.** **PROPOSED / IMPLEMENTED (TEST)** until B1b-3b acceptance.
- **Tests.**
  - Positive: equal policies admit.
  - Negative: an adapter-level mismatch is refused before any authority-side
    reservation, and an acceptance-level mismatch is refused.

## Evidence ↔ admission linkage

`AdmissionAuthorityLinkV1` records:

- `proposalRefId`, `admissionId`, `applyAuditId`, `memoryItemId`, and
  `revisionId`;
- `authorityEvidenceId` and `authorityEvidenceDigest` (SHA-256 of the exact
  signed bytes);
- `challengeId`, `actionDigest`, and `payloadDigest`.

It is held, with the public chain artifacts, in the application-held
`AdmissionLinkStoreV1` (one link per proposal). Single use is the
authority-side ledger's job, not the link store's.

`L04AdmissionViewV1` is read from the unchanged L04 tables:

- the payload digest is **recomputed from the stored value JSON**;
- the epistemic and admission bases are pinned.

**This is TEST-level only.** The L04 schema has no evidence link, and its
schema fingerprint forbids extra objects. A **production schema migration is
required** before any live V2 admission. The link and the authority
acknowledgement must be atomic with the admission, which touches
`services/core-api` and therefore the PROD path. The crash behaviour of the
current post-commit sequence is in *Pre-PR hardening §5*.

## Policy, Consent, and Rollback rows: internal state, not authority

- The rows remain, because the unchanged L04 store consumes them. Tests show
  they are still **necessary**: valid V2 evidence plus revoked Consent gives
  `L04_NOT_ADMITTED:REJECTED:CONSENT_REVOKED`.
- They are never **sufficient**. Forged Policy, Consent, Rollback, and
  `ActorEvidenceRefV1` rows admit nothing on the V2 path and are never
  returned as accepted memory.
- `admission_v2.py`, `accepted_read_v2.py`, and `l04_v2_adapter.py` never
  reference the Policy, Consent, or Rollback stores. In the adapter, the
  Actor authority appears only inside `V2AdmissionActorGate`. Static tests
  enforce both.

## B2a acceptance integration

The path is: owner proof → broker-signed `OwnerEvidenceV2` → V2 L04 admission
→ `verify_accepted_memory_v2` → `ACCEPTED_MEMORY` → accepted read.

- **B2a reuse.** It reuses B2a steps 1–6 (`verify_owner_proof`, proven
  equivalent in §7) and B2a's `ACCEPTED_MEMORY` constant.
- **Registry replaces broker keys.** B2a's broker-envelope step is replaced
  by B1b-3a registry verification and the authority-side evidence-use
  record.
- **Unchanged B2a.** B2a's `verify_accepted_memory`, its envelope, its
  reasons, and its vectors are unchanged.

The stages stay distinct:

```text
VERIFIED_AUTHORITY_EVIDENCE != L04_ADMITTED != ACCEPTED_MEMORY != TRUTH
L04 stored row != accepted memory
```

## Threat tests

- **Direct DB writer.** The writer inserts Policy, Consent, Rollback, and
  `ActorEvidenceRefV1` rows, complete L04-looking admissions, forged
  revisions, forged links, and forged duplicate admission records. It also
  rewrites value JSON or the epistemic basis. Every case is `NOT_ACCEPTED`
  and excluded from accepted reads.
- **Old application HMAC key.**
  - The synthetic secret mints V1 evidence that verifies under V1
    semantics.
  - That evidence is refused on the V2 path.
  - It cannot create new memory through a V2-mode store.
  - It cannot be turned into `OwnerEvidenceV2`.
  - A V1-forged chain that an unguarded store admits is never accepted.
- **Privacy.**
  - A hold, a suppression, or an unavailable resolver each fail closed at
    admission, and a hold or revoked Consent excludes a row at read.
  - A FORGET is `PRIVACY_OWNED_OPERATION`.
  - Owner evidence never verifies as a `PrivacyAuthorizationV2`.
  - Privacy custody is not migrated (B1b-3f).
- **Registry evolution.**
  - In-flight evidence survives a harmless update.
  - Later `COMPROMISED` status is retroactive.
  - Routine retirement keeps history.

## Required invariants (all asserted by tests)

| Invariant | Where |
| --- | --- |
| old app HMAC ≠ V2 new authority | `OldApplicationHmacKeyTests`, `V1EscapeHatchTests` |
| DB write ≠ authority | `DirectDatabaseWriterTests`, `AcceptedReadBoundaryTests` |
| L04 stored row ≠ accepted memory | `AcceptedReadBoundaryTests`, `PostCommitCrashTests` (B, B′) |
| accepted memory ≠ truth | `PositiveEndToEndTests`, accepted read `truthClaim: false` |
| valid evidence ≠ unlimited reuse | `EvidenceSingleUseTests` |
| historical V1 ≠ new V2 admission | `V1EscapeHatchTests` |
| proposal substitution ≠ valid authority | `BindingGraphTests`, negative matrix |
| missing admission link ≠ accepted memory | `PostCommitCrashTests`, `NegativeMatrixTests` |
| Privacy hold > Actor/Owner admission attempt | `PrivacyTests`, `AcceptedReadBoundaryTests` |
| application cannot sign OwnerEvidenceV2 | `StructuralIsolationTests`, `BrokerSignerTests` |

## Evidence

- **Tests.** 70 B1b-3b test methods:
  - 42 in `test_b1b3b_broker_signing_l04_v2.py`, including the 43-case
    adapter negative matrix;
  - 28 in `test_b1b3b_hardening.py`.

  Every V2 and signer reason must appear in the tests.
- **Suite totals.**
  - owner-memory-control: 141 tests (71 before B1b-3b);
  - Core API: 70 tests;
  - Slice 8–15 regressions: 382;
  - broker CI validation, repository validation, and classifier/path-filter
    tests: passed.
- **Golden vectors.** `b1b3b_golden.json` (new in this slice) is regenerated
  for the extended taxonomy. The B1a, B2a, and B1b-3a golden files are
  pinned unchanged by SHA-256.
- **Isolation.** Static tests show:
  - no private-key type, signer import, or seed in `lilith_owner_memory`;
  - no network, environment, subprocess, or config import in the V2
    modules;
  - one read-only SQLite connection helper in the adapter;
  - a self-contained signer package (signer and ledger);
  - no runtime reference to the new modules;
  - verifier entry points that take no key, seed, or signer parameter.

## Stage III implications and future sequence

Stage III is not touched or retried. This proposed sequence supersedes the
old claim/evidence topology; a future **fresh** A1–A7 design must rehearse
it:

| Step | Action | Crash point |
| --- | --- | --- |
| S1 | app proposes; broker `prepare_challenge` | **A1**: challenge prepared, owner never answers → expires; nothing signed |
| S2 | owner WebAuthn; broker verify + consume | **A2**: consumed, no evidence yet → the owner proof is burned; no re-issue in TEST |
| S3 | broker signs `OwnerEvidenceV2`, marks it issued | **A5**: signed, response lost → the broker must re-deliver the **stored** evidence (the TEST signer cannot) |
| S4 | adapter verifies, then reserves the evidence authority-side | **A3/A4** are obsolete under atomic consume + sign; replaced by: reserved, nothing applied (tested A′) |
| S5 | L04 commit (gated apply) | **A6**: reservation durable, L04 not committed (tested A); committed, link absent (tested B) |
| S6 | link recorded, then authority confirmation (acknowledgement) | **A7**: committed and linked, confirmation lost (tested B′); fully confirmed (tested C) |

**Atomicity guarantees that do NOT exist yet:**

- broker consume + sign + record as one durable transaction;
- durable authority-side reservation and confirmation;
- the admission link inside the L04 transaction;
- durable acknowledgement delivery to the owner;
- reconciliation of B/B′ stored-but-unaccepted rows;
- re-delivery of issued evidence.

## Deferred to B1b-3c (not solved here)

- **`ledgerEpoch` ↔ `RecoveryEpochV1`.** The 15B2b-B design says the V2
  challenge's `ledgerEpoch` is "bound to the canonical broker recovery
  epoch". B1b-3a defines `RecoveryEpochV1 = (counter, random)`. B1b-3b checks
  `ledgerEpoch` only against the trusted owner context, and the evidence
  epoch only against the registry and authority context. The two are not
  bound. B1b-3c must define the canonical encoding and the equality or
  derivation rule, so that a challenge prepared before a restore is void
  after it.
- **Recovery witness, monotonic external state, whole-host rollback,
  persistent registry history.** These are not implemented. B1b-3c covers
  ledger-only restore detection. Whole-host rollback remains unresolved.
- **`registryTupleVersion` versus `registryVersion`.** These are distinct
  concepts and are not equated.
  - `registryTupleVersion` (challenge, a string) is the version of the
    canonical **memory tuple registry**: which memory classes and subjects
    are writable or readable (`memory_v2.CanonicalTupleRegistry`, and the
    15B2b-A registry loader).
  - `registryVersion` (evidence and key registry, an integer) is the version
    of the owner-signed **authority key registry** (B1b-3a).

  B1b-3c does not need to equate them. It should decide whether the
  authority registry, or the owner challenge, must bind the tuple-registry
  version it was issued against, so that a tuple-registry change cannot
  reinterpret an in-flight approval.

## Ambiguities and honest limits

1. **Write barrier inside L04.** V2 admission mode is enforced by wrapping
   the store's Actor authority, in `owner-memory-control`. An unguarded store
   can still write a V1 row, which is never accepted. An L04-internal
   barrier is later core-api (PROD-path) work.
2. **Durable authority-side ledger.** The ledger is in memory. Durable
   authority-side storage is B1b-3d and later.
3. **Stuck rows after a crash.** Crash points A, A′, B, and B′ burn the
   owner authorization and may leave stored-but-unaccepted rows. There is no
   reconciliation yet.
4. **Signer registry version.** The signer's `registryVersion` is static
   config.
5. **Grounding evidence for Privacy.** How it is produced is B1b-3f.
6. **Chain artifacts in the link store.** The archived public chain
   artifacts sit in app-held storage. Tampering fails verification. Loss
   makes a memory unreadable as accepted (fail closed).

## Explicitly not done

- No DEV or PROD contact; no IAM, WIF, or systemd change.
- No real key, registry signer, credential, owner authority, or memory.
- No live broker, live L04, or Privacy DB change; no migration of old rows.
- No WebAuthn enrollment and no activation.
- No Stage III retry, and the preserved Stage III authorization is not
  consumed.
- No B1c authority change and no deployment-filter change.
