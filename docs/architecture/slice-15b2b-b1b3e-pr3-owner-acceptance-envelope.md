# Slice 15B2b-B1b-3e PR-3 P3-6: Owner Acceptance Envelope Foundation

**Status: P3-6 DESIGN + PURE SOURCE + OFFLINE TOOLING + TESTS.**

- No real owner acceptance and no real acceptance envelope exist. There is
  no real record 1.
- Real-profile acceptance is **hard-blocked** in source while P3-3 is
  `P3_3_STORAGE_INCOMPLETE` (superseded: lifted by [B-3](slice-15b2b-b1b3e-b3-real-acceptance.md)).
- Real freshness remains `FRESHNESS_UNKNOWN`.
- There was no DEV contact, no cloud contact, and no owner key.
- PR-1B, A1–A7, and First Memory are not authorized.

| Field | Value |
| --- | --- |
| Depends on | [PR-3 foundation](slice-15b2b-b1b3e-pr3-owner-offhost-foundation.md) (PR3-D1, PR3-D2, D6, D12; §24 tooling); [P3-5 sequencing](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md) (R1 package) |
| Pure source | `services/owner-memory-control/lilith_owner_memory/owner_acceptance.py` |
| Tooling | `owner_freshness_tool.py`: `init-acceptance-store`, `verify-acceptance-store`, `build-review-package`, `propose-envelope`, `append-envelope`, `classify-acceptance` |
| Tests | `…/tests/test_b1b3e_pr3_p36_acceptance_envelope.py`, plus the P3-5 sequencer tests |

```text
record identity != acceptance evidence
signature       != acceptance
file existence  != acceptance
model output    != acceptance
unsigned != unauthenticated storage
signed != owner accepted
acceptance envelope complete != any authorization
acceptance envelope complete != First Memory authorized
envelope chaining != independent freshness
```

## 1. Contract: `OwnerFreshnessAcceptanceEnvelopeV1`

One envelope per freshness record, one to one: envelope *N* evidences the
owner's acceptance of record *N*. Every field is required.

| Field | Security purpose |
| --- | --- |
| `envelopeType` = `LILITH_OWNER_FRESHNESS_ACCEPTANCE_ENVELOPE`, `schemaVersion` = 1 | type confusion; closed versioning |
| `environment`, `authorityProfile` | isolation. They must agree with each other and with the store and register. An envelope copied from another environment or profile is refused |
| `freshnessRecordVersion` | the envelope sequence: equal to the bound record version. There is no second counter that could disagree |
| `freshnessRecordDigest` | the exact accepted object. **It binds the record; it never wraps or re-encodes it**, so record identity is unchanged (tested byte for byte) |
| `decision` | must equal the record's decision (`ACCEPT_CURRENT` / `REJECT_CANDIDATE`). The owner accepts rejections as decisions too |
| `previousAcceptanceEnvelopeDigest` | acceptance history. `null` if and only if version 1 |
| `genesisPinDigest` | the lineage anchor document the owner reviewed (D12): `sha256(domain ‖ JCS(pin))` |
| `ownerReviewPackageDigest` | the exact reviewed package (§3) |
| `replicaSetDigest` | the participating owner custody set (§4) |
| `ceremonyVersion` = `LILITH_OWNER_FRESHNESS_CEREMONY_V1` | names the procedure performed (§6), so a later ceremony cannot be confused with this one |
| `acceptanceMethod` = `EXPLICIT_OWNER_DIGEST_CONFIRMATION` | the only V1 method (PR3-D2). `HARDWARE_OWNER_PRESENCE_V1` is reserved and refused |

**Excluded fields:**

- a self-digest, which would be circular;
- any timestamp. There is no trusted time, and an informational time would
  still look like evidence;
- a signature. V1 is unsigned, and an envelope carrying a `signature` field
  is malformed;
- paths, devices, and hostnames.

**Digest:** `sha256("LILITH_OWNER_FRESHNESS_ACCEPTANCE_ENVELOPE_V1\0" ‖ RFC 8785 JCS(envelope))`.

**Scope.** The envelope attests only this: *the owner explicitly accepted
this exact reviewed freshness decision and package.* It authorizes **no**
K-ROOT transition, registry change, RecoveryEpoch change, memory admission,
privacy action, activation, recovery execution, or First Memory. It is not
a freshness result, and `freshness_gate` refuses it (tested).

## 2. Authority semantics and acceptance method

For DEV_SYNTHETIC V1 the envelope is **unsigned**. Its authority comes only
from two things:

- the owner ceremony: the owner repeats the envelope digest
  (`--confirm-digest`), and the tool re-derives every input;
- custody of the two owner copies (D6).

```text
unsigned != unauthenticated storage   (authority = owner-only custody + ceremony)
signed   != owner accepted            (a signature proves a key operated, not what the owner decided)
```

**Stated limitation.** An envelope written out of band into the owner
copies is structurally indistinguishable from a ceremony-written one; a
test demonstrates this. That is why D6 custody (no agent or automation can
write the copies) is a precondition. A file's existence is never
acceptance.

## 3. Review-package binding: `OwnerFreshnessReviewPackageV1`

The package is built at ceremony step 1, **before** the append, by
`build_review_package`. It is independently reproducible from owner-held
inputs: every field except `attachedEvidence` is re-derived, and the
candidate record is re-proposed from the prior register and the chain.

| Field | Content | R1 item (P3-5 §11) |
| --- | --- | --- |
| `packageKind` | `RECORD_1` or `SUCCESSOR` | — |
| `decision`, `candidateRecordVersion`, `candidateRecordDigest` | the candidate owner record | R1-8 |
| `priorRecordDigest` | the prior owner record (null for record 1) | — |
| `genesisPinDigest` | the pin document | R1-5 |
| `replicaSetDigest` | the custody set | R1-7 |
| `trustInputsDigest` | the pinned K-WIT anchor, registry root, and registries | R1-1, R1-2, R1-3 |
| `presentedChainDigest`, `presentedChainLength` | the authentic chain from genesis, as its list of witness digests | R1-1 |
| `presentedHead` | witness version and digest, RecoveryEpoch, registry head, ledger sequence and head, K-WIT key ID, consumed authorization IDs | R1-3, R1-4, R1-5, R1-6 |
| `freshnessBefore` | authenticity, freshness, and reason against the prior register: `FRESHNESS_UNKNOWN` (empty) for record 1, `AHEAD_UNACCEPTED` or `CONFLICTING` later | R1-7 |
| `attachedEvidence` | `{name: sha256}` of owner-held evidence outside the tool. Record 1 **requires** `PR2_REVALIDATION` and `P3_3_INDEPENDENCE` | R1-9, P3-3 |

The environment and profile are also package fields.

**Digest:** `sha256("LILITH_OWNER_FRESHNESS_REVIEW_PACKAGE_V1\0" ‖ JCS(package))`.

At envelope time, `append-envelope` rebuilds the package from the
replicas' records before the bound one, the chain, the trust inputs, the
pin, and the bound record. It refuses unless the rebuild is identical, so a
hand-edited package is refused (tested).

## 4. Replica-set binding

`replicaSetDigest = sha256(domain ‖ JCS({environment, authorityProfile, replicaIds: sorted}))`.
It takes exactly two distinct replica IDs, so order does not matter.

It never binds paths, device names, mount points, timestamps, or host
metadata. It records **which owner custody set participated**, not where
the OS mounted it.

## 5. Chaining, and the relationship to the freshness chain

- Envelope 1 has a `null` predecessor.
- Envelope *N* binds envelope *N−1*'s digest.
- A skipped, duplicated, or forked envelope chain fails closed (§8).

The envelope chain is **evidence history**. It does not replace the
`previousRecordDigest` chain of the freshness records, and it gives no
independent freshness:

```text
envelope chaining != independent freshness
```

It does add one cross-check. If the freshness replicas are rolled back
while the acceptance stores are not, envelope *N* names a record that no
longer exists. The result is `ACCEPTANCE_CONFLICTING` /
`ENVELOPE_AHEAD_OF_REGISTER`, even though freshness alone (the joint-rollback
limitation) would call the old world CURRENT (tested). It detects nothing if
both are rolled back together.

## 6. Storage layout (future; not created)

The strict replica root admits only `REPLICA.json` and `records/`, so
acceptance evidence lives in a **sibling** store per custody copy. Its
creation is refused inside a replica.

```text
<owner custody copy A>/
  <replica A>/                            P3-2 replica: REPLICA.json, records/NNNNNN-<recordDigest>.json
  <replica A acceptance store>/
    ACCEPTANCE.json                       {storeType, schemaVersion, custodyCopyId = replica A's replicaId, environment, authorityProfile}
    envelopes/NNNNNN-<envelopeDigest>.json   JCS {"envelope": …, "package": …}   (create-only)
<owner custody copy B>/                   the same, for replica B
```

- **One bundle file per version.** Writing the envelope and its package as
  one create-only file makes the write atomic: there is no orphan package
  and no envelope without its package.
- **Cross-binding.** Each store names its paired replica (`custodyCopyId`),
  and both stores must pair exactly with the two replicas
  (`ACCEPTANCE_STORES_NOT_PAIRED_WITH_REPLICAS`). Envelope *N* binds record
  *N*.
- **Strict read and write.** Reading applies the P3-2 rules: exact entries,
  canonical names and bytes, contiguous versions, pending-write refusal, no
  repair. Writing follows the same algorithm: O_EXCL pending file, file
  fsync, hard link with no overwrite, directory fsync, post-write re-read.
- **Real replicas.** Neither real replica has a store yet, and none is
  created until P3-3 is complete.

## 7. Ceremony order (future real acceptance)

| # | Step | Tool |
| --- | --- | --- |
| 1 | reproduce the owner review package (before any append) | `build-review-package` |
| 2 | verify the authentic chain | `inspect-chain` |
| 3 | classify the candidate world | `classify` |
| 4 | compare both replicas | `compare-replicas` |
| 5 | verify the exact candidate record digest (the package binds it) | read the package and candidate |
| 6 | the owner explicitly confirms the record digest | — |
| 7 | append the freshness record to Replica A | `append` |
| 8 | observe `FRESHNESS_UNKNOWN` | `classify` |
| 9 | append the freshness record to Replica B | `append` |
| 10 | verify the replicas are identical and the world is `CURRENT` | `compare-replicas`, `classify` |
| 11 | construct the envelope binding the exact record and package | `propose-envelope` |
| 12 | the owner confirms the envelope digest | — |
| 13 | persist the envelope to store A (`ACCEPTANCE_PARTIAL`), then to store B (`ACCEPTANCE_COMPLETE`) | `append-envelope` (twice) |

**Steps 11–13 happen after CURRENT.** CURRENT depends only on the freshness
records. The envelope depends on CURRENT, because `append-envelope`
re-classifies an `ACCEPT_CURRENT` record as `AUTHENTIC` + `CURRENT`. So
there is no cycle. Rejection envelopes skip the CURRENT check, since the
rejected world is never current.

## 8. Acceptance-evidence states

`classify_acceptance` returns a state that is kept separate from freshness.
It is never `CURRENT`/`STALE`, and neither kind of state downgrades into the
other.

| State | Meaning |
| --- | --- |
| `ACCEPTANCE_COMPLETE` | both copies identical; envelopes 1…N valid and chained; each binds its record, package, pin, and custody set; N = the latest record |
| `ACCEPTANCE_PARTIAL` | the latest envelope is on one copy only |
| `ACCEPTANCE_NOT_PRESENT` | the latest record has no envelope on either copy |
| `ACCEPTANCE_CONFLICTING` | the copies fork, or an envelope names a record the register does not have (a rollback signal) |
| `ACCEPTANCE_INVALID` | any binding fails: record, decision, package, pin, custody set, environment, profile, previous digest, version |
| `ACCEPTANCE_UNKNOWN` | a copy is missing or unreadable, a store refuses to load (duplicate or skipped version, unexpected entry, pending write), the stores are not paired, or the register is not verified |

## 9. Crash windows

| Window | Freshness | Acceptance | Action |
| --- | --- | --- | --- |
| record accepted (both replicas) / envelope absent | `CURRENT` | `NOT_PRESENT` | build or reuse the package; propose; confirm; append (SAFE_RETRY) |
| envelope on copy A only | `CURRENT` | `PARTIAL` | append the same envelope to B |
| envelope copies divergent | unchanged | `CONFLICTING` | STOP; the owner resolves by hand; nothing is auto-repaired |
| envelope written for the wrong package | unchanged | `INVALID` (`ENVELOPE_PACKAGE_MISMATCH` / `PACKAGE_BINDING_MISMATCH`); the tool cannot write it (`PACKAGE_NOT_REPRODUCIBLE`) | STOP |
| envelope written for a stale record | — | `ENVELOPE_NOT_NEXT` at propose time; out-of-band, `INVALID`/`CONFLICTING` | STOP |
| freshness records rolled back, envelope survives | may falsely read `CURRENT` (joint-rollback limitation) | `CONFLICTING` / `ENVELOPE_AHEAD_OF_REGISTER` | STOP: evidence of rollback |
| envelope rolled back, freshness record survives | `CURRENT` | `NOT_PRESENT` (evidenced version N−1) | re-run steps 11–13 for record N |
| append interrupted (pending file) | unchanged | `UNKNOWN` (`ACCEPTANCE_PENDING_WRITE`) | manual inspection; never auto-deleted |

## 10. Relation to INITIAL_CUSTODY (P3-5 sequencer)

The P3-5 state machine now has two envelope steps after record 1 is
CURRENT: `APPEND_ENVELOPE_1_COPY_A` → `OWNER_ACCEPTANCE_EVIDENCE_PARTIAL`,
then `APPEND_ENVELOPE_1_COPY_B` → `OWNER_ACCEPTANCE_EVIDENCED`. Both are
`REQUIRED_CURRENT`; no new special case is added.

| Step | Requires |
| --- | --- |
| `APPEND_RECORD_1_REPLICA_B` (reaching CURRENT) | CURRENT only: never the envelope (no cycle) |
| `APPEND_ENVELOPE_1_COPY_A` | CURRENT |
| `APPEND_ENVELOPE_1_COPY_B` | CURRENT + `ACCEPTANCE_COMPLETE` (its own result) |
| `WRITE_HELD` (INITIAL_CUSTODY HELD) | CURRENT + `ACCEPTANCE_COMPLETE` |
| `START_SIGNER` | CURRENT + `ACCEPTANCE_COMPLETE` |
| `EVALUATE_ELIGIBILITY` (READY) | CURRENT + `ACCEPTANCE_COMPLETE` |
| `OWNER_ACCEPTANCE` (owner package; adds **E-28**: the record-1 envelope digest and acceptance state) | CURRENT + `ACCEPTANCE_COMPLETE` |
| `WRITE_RELEASED` | CURRENT + `ACCEPTANCE_COMPLETE` for the latest record |
| `EVALUATE_FULL_READINESS` | CURRENT + `ACCEPTANCE_COMPLETE` |

The sequencer accepts only a real `AcceptanceResultV1`. `PARTIAL`,
`NOT_PRESENT`, `CONFLICTING`, `INVALID`, and `UNKNOWN` all block HELD
(tested).

## 11. P3-3 hard block

> **Superseded ([B-3](slice-15b2b-b1b3e-b3-real-acceptance.md)).** `REAL_ACCEPTANCE_ENABLED` is now `True`. The
> reversible disable reason is `REAL_ACCEPTANCE_DISABLED_IN_SOURCE`, and
> `P3_3_STORAGE_INCOMPLETE` is no longer used. The text below records the
> P3-6 state. A synthetic envelope still never satisfies the real gate.

- `owner_acceptance.REAL_ACCEPTANCE_ENABLED = False`, with reason
  `P3_3_STORAGE_INCOMPLETE`. Only a reviewed source change can lift it.
- Both the freshness `append` and `append-envelope` refuse the real profile
  (`DEV_SYNTHETIC`) with `REAL_ACCEPTANCE_DISABLED`.
- `real_acceptance_gate` returns BLOCKED:
  - for `TEST_ONLY`, as `SYNTHETIC_PROFILE`: **a synthetic envelope never
    satisfies the real gate**;
  - for `DEV_SYNTHETIC`, as `P3_3_STORAGE_INCOMPLETE`.

  Both are regression-tested.

## 12. Future hardware owner presence

A later, separately scoped hardware owner-presence proof would:

- be a **separate artifact** that binds the envelope digest, for example a
  sibling proof file, or a v2 bundle key outside the envelope;
- never be inside the envelope digest, and never inside the freshness
  record digest, which neither the envelope nor a proof ever changes;
- use its own credential and relying-party domain, **never** the memory
  WebAuthn credential (D9);
- be reserved as `acceptanceMethod = HARDWARE_OWNER_PRESENCE_V1`, which
  V1 refuses. A bundle with an extra `presenceProof` key is refused in V1.

DEV_SYNTHETIC does not depend on it. No key is generated and no WebAuthn
enrollment happens.

## 13. First Memory

```text
acceptance envelope complete != First Memory authorized
```

First Memory remains behind: PR-1B FULL_READINESS, then fresh A1–A7, then
proof acceptance, then a First Memory eligibility review. `first_memory_gate`
is unchanged and still blocks at FULL_READINESS until A1–A7 are complete
(tested).

## 14. Hidden assumption

> What assumption could make the acceptance envelope appear authoritative while it is wrong?

1. **"If an acceptance envelope exists, the owner must have accepted it."**
   Rejected. A file can be written by anything that can write the store, and
   an out-of-band envelope is indistinguishable (tested). The envelope is
   evidence of a ceremony only under D6 custody, and only when written by
   the re-deriving tool after the owner repeats its digest.
2. **"If it is signed, it must represent owner intent."** Rejected. A
   signature proves that a key operated. If the key sits in an
   agent-reachable process, it proves nothing about the owner. Owner
   intent needs an owner-presence ceremony. Even then, a signature gives no
   freshness, and an old signed envelope replays. V1 therefore carries no
   signature, and future presence proofs stay outside both digests.
3. **"A complete envelope means the world is current."** Rejected.
   Acceptance and freshness are separate states. A complete envelope for
   record N says nothing if DEV has since advanced (`AHEAD_UNACCEPTED`), or
   if everything was rolled back together.
4. **"The envelope authorizes the next step."** Rejected. It attests one
   past decision. Every authority step keeps its own gate (K-ROOT, witness,
   hold store, owner package).

## 15. Nonclaims

P3-6 does **not** establish any of the following:

- P3-3 completion (`P3_3_STORAGE_INCOMPLETE` remains);
- real owner freshness or a real acceptance envelope;
- record 1;
- an owner key, or hardware owner presence;
- K-ROOT, K-WIT, registry, ledger, witness genesis, hold, RecoveryEpoch, or
  INITIAL_CUSTODY;
- PR-1B eligibility;
- A1–A7;
- First Memory;
- whole-host rollback resistance.

```text
P3-6 ACCEPTANCE ENVELOPE FOUNDATION ONLY   P3-3 REMAINS STORAGE_INCOMPLETE   REAL FRESHNESS REMAINS UNKNOWN
NO REAL RECORD 1   NO REAL ACCEPTANCE ENVELOPE   NO DEV CONTACT   NO CLOUD CONTACT   NO OWNER KEY
NO K-ROOT ACTIVITY   NO K-WIT   NO REGISTRY   NO LEDGER   NO WITNESS STATE   NO HOLD   NO RECOVERY EPOCH
NO INITIAL_CUSTODY   NO REBOOT   PR-1B NOT AUTHORIZED   A1-A7 NOT AUTHORIZED   FIRST MEMORY NOT AUTHORIZED
```
