# Slice 15B2b-B1b-3c — Recovery Epoch and Registry Witness Semantics

Status:

- **SOURCE IMPLEMENTED**
- **TEST PROVEN**
- **LIVE WITNESS ABSENT**
- **WHOLE-HOST ROLLBACK UNRESOLVED**
- **REAL AUTHORITY ABSENT**

This is the third implementation slice of the
[B1b-3 custody isolation design](slice-15b2b-b1b3-custody-isolation-design.md),
built on [B1b-3a](slice-15b2b-b1b3a-authority-registry-contracts.md) and
[B1b-3b](slice-15b2b-b1b3b-broker-signing-l04-v2-adapter.md). It is exercised
only by synthetic tests. It does **not** mark B1b-3, Level 2 isolation,
Privacy custody, real owner authority, First Memory, or Stage III as done.
Level 3 is not claimed. Off-host monotonicity is not claimed.

No DEV, PROD, IAM, WIF, systemd, broker, Privacy DB, or live L04 state was
contacted or changed. No real key, witness, credential, owner authority, or
memory was created. No Stage III authorization was consumed.

## Property proven

```text
RESTORE != AUTHORITY RESTORATION
old valid evidence != permission for a new post-recovery admission
```

A restored, stale, rolled-back, or pre-recovery authority-side state cannot
silently revive authority that is no longer current, **as long as an
independently surviving witness exists** (ledger-only rollback). Historical
evidence stays verifiable as history.

Two rules carry the whole slice:

1. **Removing authority never needs readiness; creating it always does.**
   Prepare, consume, issue, reserve, and confirm require a `RESTORE_READY`
   result bound to the exact ledger sequence and head it evaluated. Expire,
   cancel, fail, abandon, void, quarantine, and epoch advance need none.
2. **Recovery can only destroy pending authority, never create any.** After
   `E1 → E2`, every E1 artifact is epoch-bound: an E1 challenge cannot be
   prepared, consumed, or signed in E2, and E1 evidence cannot be reserved in
   E2. Lost terminal state (for example, a consumption made after the
   snapshot and lost by the restore) is therefore harmless once the epoch
   advances.

## Location and delivery impact

| Path | Role |
| --- | --- |
| `services/owner-memory-control/lilith_owner_memory/recovery_contracts.py` | epoch encoding/digest/ordering, `ledger_epoch_id`, `RecoveryWitnessV1`, `TrustedWitnessAnchorV1`, witness verifier and succession rules, `witness_authority_context`, Privacy boundary slot |
| `services/owner-memory-control/lilith_owner_memory/recovery_admission.py` | `RecoveryBoundAdmissionGateV1` (NEW_ADMISSION_AUTHORITY) and `verify_historical_accepted_memory` (HISTORICAL_VALIDITY) |
| `services/owner-memory-control/lilith_authority_signer/synthetic_recovery_ledger.py` | pure authority-side ledger model, recovery ceremony, TEST witness signer, restore-readiness gate |
| `services/owner-memory-control/tests/synthetic_b1b3c.py`, `test_b1b3c_recovery_epoch_witness.py`, `b1b3c_golden.json` | fixtures, 63 tests, vectors |
| `docs/architecture/README.md` | index row |

No existing module, contract, or vector changed. `RecoveryEpochV1`,
`OwnerMemoryChallengeV2`, `OwnerEvidenceV2`, `AuthorityRegistryV1`, the B2a,
B1b-3a, and B1b-3b golden files and their SHA-256 pins are unchanged (tested).

Delivery impact:

- Nothing is under `services/core-api/**`: the PROD workflow path filter is
  **not** triggered.
- Nothing is under `services/memory-broker/`: the broker file set is
  unchanged.
- `ci.yml` is unchanged. Its Core API job already runs
  `unittest discover -s services/owner-memory-control/tests`, so the new
  tests run in CI on a PR and on `main`. CI does not run for a pushed branch
  without a PR (`pull_request` / `push: main` triggers only).
- On merge, `scripts/classify_dev_deployment.py` classifies these paths as
  `DEPLOY_REQUIRED` (they are not control-only), so the routine DEV Core API
  deployment runs, as after B2a, B1b-3a, and B1b-3b. The bundle is built only
  from `services/core-api/`; no file from this slice ships, and no runtime
  code imports the new modules (tested).

## 1. Epoch inventory

| Concept | Exact current meaning | Owner | Persistence | Mutable | Who advances | Protects | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `broker_schema_v1.authority_epoch` | 128-bit random hex written once at ledger init; startup only checks it is non-empty | broker ledger (`owner_control.db`) | SQLite row | no path to change it | nobody (D8) | nothing today; no challenge is bound to it | IMPLEMENTED, semantically inert |
| `OwnerMemoryChallengeV2.ledgerEpoch` | opaque identifier the owner signs; B2a checks equality with the trusted context and with the ledger record | owner challenge | inside the signed challenge | immutable per challenge | chosen by the challenge builder (fixtures use an opaque constant) | void a challenge prepared before a ledger restore (design intent) | IMPLEMENTED field; binding **PROPOSED → now defined** |
| `OwnerChallengeLedgerRecordV2.ledgerEpoch` | TEST view of the challenge row plus ledger epoch | B2a TEST view | none (typed view) | — | — | row ↔ challenge epoch equality | IMPLEMENTED (TEST) |
| `AcceptanceContextV1.ledger_epoch` | trusted expected ledger epoch | caller | none | — | caller | stale-challenge rejection | IMPLEMENTED (TEST) |
| `RecoveryEpochV1 (counter, random)` | B1b-3a epoch in registries, key records, OwnerEvidenceV2 | owner-signed registry / signer config | signed registry and evidence | immutable per artifact | owner (registry root) signs a registry at a new epoch | cross-epoch evidence use | IMPLEMENTED (TEST) |
| `AuthorityVerificationContextV1.expected_recovery_epoch` | trusted current epoch for NEW_ADMISSION | caller | none | — | caller (B1b-3a); **witness (B1b-3c)** | new admission requires current epoch | IMPLEMENTED; source now defined |
| `registryVersion` (registry document) | monotonic authority key registry version | owner-signed registry | registry document | new version per publication | registry root | downgrade detection | IMPLEMENTED (TEST) |
| `AuthorityKeyRecordV1.registryVersion` | version in which the key was first published; immutable | registry | key record | immutable | — | evidence may not claim a pre-publication version | IMPLEMENTED (TEST) |
| `OwnerEvidenceV2.registryVersion` | registry version the signer claims; any from key publication to verified registry | signer | evidence | immutable | signer config (static) | registry-lifecycle checks | IMPLEMENTED (TEST) |
| `trusted_minimum_registry_version` | monotonic floor | caller | none | — | caller (B1b-3a); **witness (B1b-3c)** | REGISTRY_DOWNGRADE | IMPLEMENTED; source now defined |
| `registryTupleVersion` | memory tuple/class registry version | owner challenge | inside the signed challenge | immutable per challenge | tuple-registry loader | an in-flight approval cannot be reinterpreted by a tuple-registry change | IMPLEMENTED |
| `policyVersion` | policy version on challenge, registry, key, evidence, context | several | signed artifacts | immutable per artifact | registry publication | cross-policy use | IMPLEMENTED (TEST) |
| challenge state | B1a/broker `PREPARED`, `CONSUMED`, `CANCELLED`, `EXPIRED`; TEST signer adds "evidence issued" | broker ledger | SQLite / in memory | forward only | broker | single use of owner proof | IMPLEMENTED |
| evidence-use state | `RESERVED`, `CONSUMED`, `ABANDONED` | authority side (B1b-3b) | in memory only | forward only | adapter via ledger | one evidence → one durable effect | IMPLEMENTED (TEST, in memory) |
| recovery witness | none before this slice | — | — | — | — | — | **PROPOSED → TEST contract here** |
| snapshot/restore marker | none; B1c/Stage II snapshot tooling records file hashes, not authority epochs | — | — | — | — | — | absent |

Not merged: `authority_epoch` (broker DB) and `RecoveryEpochV1` are different
things today. B1b-3c does not reinterpret the broker column. B1b-3d must
either retire it or define it as `epoch_digest(RecoveryEpochV1, env)`; until
then it carries no authority meaning.

## 2. `RecoveryEpochV1` exact contract

Unchanged B1b-3a shape: `{"counter": int, "random": 32 lowercase hex}`.
`counter` is a JSON-safe integer ≥ 0 (`bool` rejected); `random` is 128 bits.

- **Canonical bytes:** RFC 8785 of `{"counter","random"}`, e.g.
  `{"counter":3,"random":"…"}`. These are the exact bytes registries and
  evidence already sign, so no vector changes.
- **Digest:** `sha256("LILITH_RECOVERY_EPOCH_V1\0" ‖ JCS{counter, environment, random})`.
- **Equality:** exact on both parts.
- **Ordering (partial):** `EQUAL`; `FORKED` (same counter, different random);
  otherwise `OLDER` / `NEWER` by counter.

Fields evaluated and **not** added to the epoch itself:

| Field | Decision | Why |
| --- | --- | --- |
| `schemaVersion`, `reason`, `createdAt`, `previousEpochDigest` | on the transition record / journal, not the epoch | epoch identity must not depend on time or narrative; changing the epoch shape would change every B1b-3a/3b signature |
| `environment` | bound in the digest and `ledgerEpoch`, not a field | the same `(counter, random)` in two environments must be two epochs, without changing the signed shape |
| `authorityDomain` | not added | one epoch covers the broker for both signing domains |
| `policyVersion`, `registryVersion` | not added | independently monotonic; bound through the witness and registry |
| `witnessVersion` | on the witness | witness chain position, not epoch identity |

Counter alone fails (two divergent restores reach the same counter); random
alone fails (no ordering). Both are required.

## 3. `ledgerEpoch` binding

```text
ledgerEpoch = "lep1." + epoch_digest(RecoveryEpochV1, environment)   # 69 chars, valid B1a id
```

There is exactly one derivation, so `ledgerEpoch` and the recovery epoch are
never independently mutable. The NEW_ADMISSION gate requires:

- `owner_context.ledger_epoch == ledger_epoch_id(witness.currentRecoveryEpoch)`;
- the challenge's `ledgerEpoch` equals it (`STALE_EPOCH_CHALLENGE`);
- the evidence `recoveryEpoch` equals the witness epoch (`STALE_EPOCH_EVIDENCE`);
- the adapter's B1b-3a context equals `witness_authority_context(witness)`.

The B1b-3b fixture's opaque `ledgerEpoch` matches no epoch; the gate refuses
it (`LEDGER_EPOCH_NOT_BOUND_TO_WITNESS`). B1b-3b behaviour without the gate is
unchanged.

## 4. Historical validity vs new admission authority

| Question | Owner challenge checked against | Authority context | Result |
| --- | --- | --- | --- |
| `NEW_ADMISSION_AUTHORITY` | the witness's current ledger epoch | `NEW_ADMISSION`, epoch and floor from the witness | L04_ADMITTED, `authorizesNewAdmission: true` |
| `HISTORICAL_VALIDITY` | `ledger_epoch_id(evidence.recoveryEpoch)` | `HISTORICAL_VERIFICATION`, current registry, floor from the witness | ACCEPTED_MEMORY, `authorizesNewAdmission: false` |

The evidence's own epoch is not taken on trust: B1b-3a requires it to equal
its key record's epoch in the **current** owner-signed registry. After
`E1 → E2`, an E1 admission still verifies historically
(`RETIRED_AFTER_ISSUANCE`, `evidenceEpochIsCurrent: false`), while the same
E1 evidence is refused for any new admission by the gate, and by the adapter
itself when the gate is bypassed (`LEDGER_EPOCH_MISMATCH`,
`REGISTRY_EPOCH_MISMATCH`). Current compromise and downgrade rules still apply
to history. History is never rewritten.

## 5. Challenge-state recovery semantics

| Pre-recovery state | After `E1 → E2` | Reusable in E2 |
| --- | --- | --- |
| `PREPARED` | `VOIDED_BY_RECOVERY` (PROPOSED terminal) | never (`CHALLENGE_NOT_PREPARED`; re-prepare `CHALLENGE_ALREADY_KNOWN`) |
| `CONSUMED`, no evidence | stays `CONSUMED` | cannot be signed (`STALE_EPOCH_CHALLENGE`); owner re-authorizes |
| `CONSUMED`, evidence issued | stays `CONSUMED` | evidence cannot be reserved (`STALE_EPOCH_EVIDENCE`) |
| `EXPIRED`, `CANCELLED`, `FAILED` | unchanged | never reopen |

Any new challenge carrying an E1 `ledgerEpoch` is refused
(`CHALLENGE_EPOCH_NOT_CURRENT`; the real TEST signer: `CHALLENGE_CONTEXT_MISMATCH`).
Terminal records are retained unchanged (tested, row by row).

## 6. Recovery witness

`RecoveryWitnessV1`, signed with separator `LILITH_RECOVERY_WITNESS_V1\0`:

| Field | Meaning |
| --- | --- |
| `protocol`, `schemaVersion` | `LILITH_RECOVERY_WITNESS`, `1` |
| `environment` | exactly one environment |
| `witnessVersion` | +1 per update |
| `previousWitnessDigest` | SHA-256 of the previous signed witness bytes; null only at version 1 |
| `currentRecoveryEpoch` | the only epoch in which authority may be issued |
| `minimumRegistryVersion` | the trusted authority-registry floor |
| `policyVersion` | acceptable policy |
| `ledgerSequence`, `ledgerHead` | broker journal length and hash-chain head, so a restore **within** an epoch is detected |
| `updatedAt` | monotonic |
| `witnessKeyId`, `signature` | a `test-only.witness.` key |

`witness != authority`: the witness key must differ from the registry root
and every registry key (`WITNESS_KEY_IS_AUTHORITY_KEY`); it signs no evidence,
registry, or challenge, and evidence or a registry signed with it is rejected
(tested). Succession is monotonic (closed reasons in `SUCCESSION_REASONS`):
version +1, chain digest, epoch equal or counter +1, floor never lower and
strictly higher on advance, policy change only with a registry change, ledger
never rewound within an epoch, time never backwards. On an epoch advance the
journal may restart from a restored (shorter) ledger; that is safe by rule 2.
The TEST witness writer refuses to sign a non-successor.

## 7. Registry version relationship

- `registryTupleVersion` (memory tuple registry) is **owner-bound**: it is in
  the owner challenge and reaches evidence only through `challengeDigest`. A
  tuple-registry change cannot reinterpret an in-flight approval.
- `registryVersion` (authority key registry) is **signer-bound** in
  `OwnerEvidenceV2`, and its floor comes from the witness. It is intentionally
  **not** owner-bound: a routine key rotation during an in-flight approval
  must not burn the owner's proof, and compromise is handled retroactively by
  the current registry.
- The witness floors the authority registry only. No contract was
  strengthened.

## 8. Trusted minimum registry version

Source: `witness.minimumRegistryVersion`, via `witness_authority_context`.
With floor N: N allowed, N+1 allowed, N-1 `REGISTRY_DOWNGRADE`. A restored
broker that thinks N-1 is current: with its old registry,
`REGISTRY_DOWNGRADE`; with the current registry, `BROKER_REGISTRY_VIEW_STALE`.
Only a restored witness (whole-host) lets N-1 through.

## 9. Compromised-key rollback

Registry v10: K valid. v11: K `COMPROMISED`, next key published; witness floor
11. K evidence → `KEY_COMPROMISED` (both purposes, backdated `issuedAt`
included). Restore v10 → `REGISTRY_DOWNGRADE` for evidence, history, and
readiness. Routine retirement at v11 instead keeps K's pre-retirement evidence
historically valid (`RETIRED_AFTER_ISSUANCE`): compromise ≠ routine
retirement. With witness, registry, and ledger all rolled back to v10, K
verifies again: **unresolved** (whole-host).

## 10. Recovery-epoch advancement (TEST ceremony)

1. **Requested** by the broker readiness gate or the owner (conceptually; the
   application cannot request it). **Authorized** by an owner-signed registry
   at the new epoch: `newEpoch = (witness.counter + 1, fresh random)` —
   from the witness, never from a stale ledger — with `registryVersion >
   witness.minimumRegistryVersion` and at least one current Owner/Actor key at
   the new epoch. Every current E1 key is retired at the recovery instant.
2. `ADVANCE_EPOCH` is journalled; the witness is updated to the new epoch
   (**point of no return**).
3. Pre-recovery work is quarantined: PREPARED → `VOIDED_BY_RECOVERY`, RESERVED
   → `QUARANTINED_BY_RECOVERY`. The witness is updated again.
4. The acknowledgement `RecoveryEpochTransitionV1` records previous, restored,
   and new epochs and ledger epochs, registry and witness versions, voided and
   quarantined IDs, retained terminal counts, `ownerReauthorizationRequired`,
   `reconciliationRequired`, `historicalEvidenceRetained: true`,
   `rollbackDetectionScope: LEDGER_ONLY`, `wholeHostRollbackProtected: false`.
   It is a record, not an authority.

A crash between steps 2 and 3 leaves `NONTERMINAL_PRE_RECOVERY_WORK` until the
quarantine completes. Refusals: `RECOVERY_REASON_INVALID`,
`RECOVERY_WITNESS_INVALID`, `RECOVERY_EPOCH_NOT_ADVANCING`,
`RECOVERY_REGISTRY_NOT_ADVANCING`, `RECOVERY_REGISTRY_UNVERIFIED`,
`RECOVERY_NO_SIGNING_KEY`. No real owner key or ceremony exists.

## 11. Restore readiness gate

`evaluate_restore_readiness` → `RESTORE_READY` or `NOT_READY(reason)`. Pure,
fail closed, closed and ordered taxonomy (every reason reachable, tested):

`MALFORMED_INPUT`, `AUTHORITY_STATE_MISSING`, `WITNESS_MISSING`,
`WITNESS_KEY_IS_AUTHORITY_KEY`, `WITNESS_INVALID`, `ENVIRONMENT_MISMATCH`,
`LEDGER_INTEGRITY_FAILED`, `TERMINAL_STATE_REOPENED`, `LEDGER_EPOCH_STALE`,
`LEDGER_EPOCH_FORKED`, `LEDGER_EPOCH_AHEAD_OF_WITNESS`,
`POLICY_VERSION_NOT_ACCEPTABLE`, `REGISTRY_MISSING`, `REGISTRY_DOWNGRADE`,
`REGISTRY_EPOCH_MISMATCH`, `REGISTRY_UNVERIFIED`, `BROKER_REGISTRY_VIEW_STALE`,
`LEDGER_BEHIND_WITNESS`, `LEDGER_AHEAD_OF_WITNESS`, `LEDGER_HEAD_MISMATCH`,
`REQUIRED_KEY_UNAVAILABLE`, `NONTERMINAL_PRE_RECOVERY_WORK`,
`PRIVACY_BOUNDARY_STALE`, `PRIVACY_BOUNDARY_UNVERIFIED`.

The journal is authoritative over materialized rows: rows that show a terminal
record as nonterminal are `TERMINAL_STATE_REOPENED`; other divergence is
`LEDGER_INTEGRITY_FAILED`. Every result reports `authorityIssuanceAllowed`,
`historicalReadsAllowed`, `rollbackDetectionScope: LEDGER_ONLY`, and
`wholeHostRollbackProtected: false`. Historical reads are blocked when the
registry does not verify against the witness floor, or the witness itself is
behind the ledger. `LEDGER_AHEAD_OF_WITNESS` covers both a restored witness
and a crash between ledger commit and witness update; they are
indistinguishable, so both fail closed and resolve by an epoch advance.

## 12. Evidence-use recovery semantics

| State | After recovery | Rule |
| --- | --- | --- |
| `CONSUMED` | unchanged | never reusable (`EVIDENCE_ALREADY_USED`, `USE_NOT_RESERVED`) |
| `RESERVED` | `QUARANTINED_BY_RECOVERY` | never silently reactivated; confirm refused; reconciliation required |
| `ABANDONED` | unchanged | unusable |
| issued, unreserved | unchanged | reserve refused `STALE_EPOCH_EVIDENCE`, even if relabelled with the new epoch (the ledger recorded the issuing epoch) |
| state missing | — | `AUTHORITY_STATE_MISSING`; acceptance `EVIDENCE_USE_MISSING` |

The B1b-3b `SyntheticEvidenceUseLedgerV1` is still in memory and unchanged.
These are pure transition rules for B1b-3d to implement durably; no
persistence is claimed.

## 13. Privacy interaction

There is **no canonical Privacy epoch** in this repository
(`CANONICAL_PRIVACY_EPOCH_EXISTS = False`); none is invented. Readiness takes
a `PrivacyBoundaryObservationV1` whose only B1b-3c source is
`TEST_SYNTHETIC`. Only `AT_OR_AFTER_REQUIRED` is ready; `OLDER_THAN_REQUIRED`
→ `PRIVACY_BOUNDARY_STALE`; `UNAVAILABLE` / `NOT_MODELLED` →
`PRIVACY_BOUNDARY_UNVERIFIED`. Recovery never bypasses the Privacy hold: a
newer restore suppression still blocks a fresh E2 admission
(`PRIVACY_HOLD_ACTIVE`, tested). **Gap for B1b-3f:** the source, ordering,
and custody of a Privacy boundary.

## 14. Snapshot / restore matrix

Base: c1 fully admitted; snapshot S with c2 PREPARED; then c2 consumed and
its evidence issued. All rows report `wholeHostRollbackProtected: false`.

| # | Scenario | Detected as | Issuance | Historical reads | Unresolved |
| --- | --- | --- | --- | --- | --- |
| 1 | clean restart | `RESTORE_READY` | allowed | allowed | — |
| 2 | broker ledger restored, witness current | `LEDGER_BEHIND_WITNESS` | blocked | allowed | — |
| 3 | witness restored, broker current | `LEDGER_AHEAD_OF_WITNESS` | blocked | blocked | — |
| 4 | both restored together | `RESTORE_READY` (**not detected**) | allowed | allowed | whole-host rollback |
| 5 | old registry, current witness | `REGISTRY_DOWNGRADE` | blocked | blocked | — |
| 6 | current registry, old ledger | `BROKER_REGISTRY_VIEW_STALE` | blocked | allowed | — |
| 7 | consumed challenge reopened by stale DB rows | `TERMINAL_STATE_REOPENED` | blocked | allowed | — |
| 8 | prepared challenge resurrected after E2 | `LEDGER_EPOCH_STALE` | blocked | allowed | — |
| 9 | retired key resurrected | `REGISTRY_DOWNGRADE` | blocked | blocked | — |
| 10 | compromised key state rolled back | `REGISTRY_DOWNGRADE` | blocked | blocked | — |
| 11 | old evidence replayed after E2 | ready; reserve `STALE_EPOCH_EVIDENCE` | blocked for it | allowed | — |
| 12 | stale application DB, current broker | ready; reserve `EVIDENCE_ALREADY_USED` | blocked for it | allowed | — |
| 13 | stale broker, current application DB | `LEDGER_BEHIND_WITNESS` | blocked | allowed | — |
| 14 | duplicate counter, different nonce | `LEDGER_EPOCH_FORKED` | blocked | allowed | — |
| 15 | same epoch object, wrong environment | `ENVIRONMENT_MISMATCH` | blocked | blocked | — |

The application databases are never consulted by the gate, so a stale or
forged application DB can neither block nor revive authority-side state.
Frozen in `b1b3c_golden.json` (`restoreMatrix`).

## 15. Crash model with recovery epochs (input to the fresh A1–A7 rehearsal)

Recovery between each B1b-3b step (tested in the pure model; S5 also against
real L04 with the B1b-3b fault hook):

| Point | Old-epoch artifacts after recovery | New-epoch behaviour | Retry | Quarantine / reconciliation | Owner re-authorization |
| --- | --- | --- | --- | --- | --- |
| S1 prepare (A1) | challenge `VOIDED_BY_RECOVERY` | cannot consume / re-prepare | no | voided | yes |
| S2 consume (A2) | challenge `CONSUMED`, unsigned | cannot sign | no | — | yes |
| S3 sign (A5) | evidence issued in E1 | cannot reserve; historical only if it ever reached acceptance (it did not) | no | — | yes |
| S4 reserve (A′) | use `QUARANTINED_BY_RECOVERY` | cannot confirm | no | reconcile (nothing applied) | yes |
| S5 L04 commit (A, B) | use quarantined; L04 row may exist, unlinked | never L04_ADMITTED / ACCEPTED_MEMORY (`ADMISSION_LINK_MISSING`) | no | reconcile the stored-but-unaccepted row | yes |
| S6 link, confirm lost (B′) | same as S5 on the authority side | never accepted | no | reconcile | yes |
| S6 confirmed (C) | use `CONSUMED` | historical ACCEPTED_MEMORY under E2 | not needed | — | no |

Reconciliation of quarantined rows is not implemented. It must never produce
new authority; at most it may label a row historically valid under the old
epoch, and that needs a separate owner-approved design.

## 16. Whole-host limit

| Threat | Result |
| --- | --- |
| **A. LEDGER-ONLY ROLLBACK** (broker state rolled back, witness survives) | detected (`LEDGER_BEHIND_WITNESS`, `LEDGER_EPOCH_STALE`, `LEDGER_HEAD_MISMATCH`, `REGISTRY_DOWNGRADE`, `BROKER_REGISTRY_VIEW_STALE`) |
| **B. WHOLE-HOST / WHOLE-DISK ROLLBACK** (ledger, registry, and same-host witness rolled back together) | **not detected** |

A test restores ledger, registry, witness, and the witness writer's own state
together: readiness reports `RESTORE_READY`, a challenge consumed after the
snapshot is `PREPARED` again and can be consumed again, and a compromised key
verifies again. A same-host witness plus broker state cannot establish
whole-host rollback protection. `WHOLE_HOST_ROLLBACK_PROTECTED` is never set.

A future anchor is required, one of: an off-host monotonic witness;
owner-held state (for example an owner-signed checkpoint the owner keeps);
an external durable monotonic service; a hardware-backed monotonic counter;
or another independently versioned anchor. None is selected here.

## 17. Proposed B1b-3d DEV witness shape (not installed)

| Option | Shape | Detects | Limits |
| --- | --- | --- | --- |
| A. root-owned protected file | `RecoveryWitnessV1` payload in a root-owned file (0644 root:root, or 0600 for a dedicated witness identity), written only by a fixed root helper after each ledger commit; `lilith` and the routine deployer denied write | ledger-only rollback, if the file survives | no signature: integrity is OS permission only; same disk; root (Level 3) out of scope |
| B. owner-signed local witness | same payload signed by a witness key held outside `lilith` and the broker service identity (or owner-countersigned checkpoints) | ledger-only rollback; tamper by a non-root writer | still same host/disk; key custody question |
| C. external / off-host witness | witness held by an independent service or the owner | whole-host rollback, if truly independent | new trust dependency, availability, network; out of scope for DEV synthetic |

Recommendation for **B1b-3d DEV_SYNTHETIC**: B on top of A — a signed
witness (this contract, a DEV-synthetic `test-only.`-style key, not an
authority key) stored in a root-owned file outside the broker state
directory, updated by a fixed helper, with OS denial proof for `lilith` and
the deployer. It proves ledger-only rollback detection on DEV and nothing
more. It is not installed or authorized by this record.

## 18. Open owner decisions and ambiguities

1. Who may request vs. authorize an epoch advance; whether an owner signature
   beyond the registry root is required (carried from the design, decision 6).
2. Fate of the static `broker_schema_v1.authority_epoch` (retire, or define as
   `epoch_digest`).
3. The off-host / independently monotonic anchor, and when it becomes
   mandatory (design decision 2).
4. Witness key custody for B1b-3d, and whether option A alone is acceptable
   for DEV.
5. Witness write frequency (every authority transition, as modelled, vs.
   checkpoints) and its availability cost.
6. Reconciliation of quarantined `RESERVED` evidence and stored-but-unaccepted
   L04 rows.
7. Privacy boundary source and ordering (B1b-3f).
8. `VOIDED_BY_RECOVERY`, `FAILED`, and `QUARANTINED_BY_RECOVERY` are PROPOSED
   states; the broker SQLite `CHECK` constraints do not contain them. Adding
   them is B1b-3d broker work (`services/memory-broker/`, broker validation).
9. Every recovery retires all current keys (a key belongs to one epoch, per
   B1b-3a). Whether that forced rotation is acceptable operationally.

## Explicitly not done

- No DEV or PROD contact; no IAM, WIF, or systemd change.
- No real key, witness, registry signer, credential, owner authority, or memory.
- No live broker, live L04, or Privacy DB change; no live witness file.
- No Stage III retry; the preserved Stage III authorization is not consumed.
- No change to existing contracts, vectors, workflows, or path filters.
- No claim of whole-host rollback protection, Level 3, or off-host monotonicity.
