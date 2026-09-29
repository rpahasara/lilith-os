# Slice 15B2b-B1b-3e PR-3: Owner / Off-Host Freshness Foundation

**Status: PR-3 DESIGN + SOURCE FOUNDATION + P3-2 OFFLINE TOOLING + P3-3 STORAGE (`P3_3_STORAGE_INCOMPLETE`) + P3-4 SYNTHETIC REHEARSAL (PASSED; does not close P3-3).**
- The pure, offline contract and the offline owner-workstation tooling are
  implemented and test proven.
- Owner decisions PR3-D1..PR3-D12 are **ACCEPTED** (§19).
- P3-3: real Replica A is initialized and **empty**. There is no second
  medium, so Replica B does not exist (§25). No freshness record exists.
  No owner key has been generated.
- No DEV or cloud contact was made.
- PR-1B is not authorized. First Memory is not
  authorized.

| Field | Value |
| --- | --- |
| Gate | live-rehearsal gate §14 row PR-3; PR-1 preflight §20 (PR-3 foundation precedes the V2 genesis commit; PR-3 full material precedes `INITIAL_CUSTODY` `RELEASED`) |
| Accepted pre-state | PR-1A ACCEPTED (`P1A-9`, AUTHORITY_BOUNDARY PASS `L1c.3`); PR-2 ACCEPTED ([record](slice-15b2b-b1b3e-pr2-acceptance.md)) |
| Starting main | `f3a8add08d1aa114615fc5397ba3c919e35931bf` |
| Source | `services/owner-memory-control/lilith_owner_memory/owner_freshness.py` (pure, offline); `…/owner_freshness_tool.py` (P3-2 offline workstation tooling, §24) |
| Tests | `…/tests/test_b1b3e_pr3_owner_freshness.py` (27), `…_p32_owner_freshness_tool.py` (19), `…_p33_storage_gate.py` (16), and `…_p34_ceremony_rehearsal.py` (10), over real K-WIT-signed TEST chains |

PR-2 found that DEV holds every authority and custody object in one
rollback domain:

```text
WHOLE-HOST / WHOLE-DISK ROLLBACK CAN PRESENT A SELF-CONSISTENT OLD AUTHORITY WORLD.
WHOLE-HOST ROLLBACK RESISTANCE = NOT ESTABLISHED.
INDEPENDENTLY PERSISTED FRESHNESS STATE = NONE.
```

PR-3 does not change DEV. It adds an owner-side domain in which such a world
can be identified as stale.

```text
storage != acceptance            file existence != owner authority
DEV proposal != owner acceptance signature validity != freshness
K-ROOT authorization != owner off-host freshness acceptance
RecoveryWitness freshness != owner off-host freshness
memory authorization != authority-bootstrap acceptance
detect != authorize recovery != execute recovery != accept recovered state
freshness precondition met != authorization
```

## 1. Goal

A DEV host restored to an old but cryptographically valid state must not be
able, **by itself**, to establish that its authority world is current. PR-3
supplies the minimum needed for that:

1. an owner record kept outside the DEV rollback domain;
2. a deterministic comparison of a presented DEV world against it;
3. rules that keep DEV, agents, storage, and signatures from defining
   "latest".

The work is kept small on purpose. PR-3 builds no service, database, cloud
resource, hardware dependency, or new key.

## 2. Central security property: `OFF_HOST_OWNER_FRESHNESS_ANCHOR`

**Definition.** For one `(environment, authorityProfile)`, the owner holds,
outside the DEV rollback domain, a hash-chained register of owner decisions.
Its last `ACCEPT_CURRENT` record names exactly one authentic witness head:
the *latest owner-accepted world*. A presented DEV world counts as `CURRENT`
only if all of these hold:

1. its K-WIT-verified witness chain descends from the register's genesis;
2. its chain contains every accepted checkpoint it reaches;
3. its head is exactly the latest accepted witness head.

It means:

| Clause | How it holds |
| --- | --- |
| Owner-controlled state exists outside the DEV rollback domain | the register lives only in owner custody (§6). No copy DEV holds has any effect |
| The owner can compare a presented DEV world against the latest owner-accepted state | `classify_presented_world` (§8) |
| A DEV rollback cannot silently redefine "latest" | "Latest" is read only from the owner's copies. A restored DEV head at a lower witness version is `STALE`, and a divergent one is `CONFLICTING` |
| DEV cannot advance owner freshness by itself | a DEV head beyond the latest record is `AHEAD_UNACCEPTED` until the owner appends a record. DEV holds no write path into the owner's copies |
| Old authentic state stays authentic but can be identified as stale | `authenticity` and `freshness` are separate result fields; `AUTHENTIC` + `STALE` is a normal result |

**Explicitly not claimed.** PR-3 provides none of the following:

- globally trusted time;
- anti-rollback hardware, or TPM-backed freshness;
- consensus of any kind;
- automatic disaster recovery;
- PROD readiness;
- freshness finer than the owner's latest checkpoint;
- detection if every owner copy is rolled back together.

## 3. Threat model

| Actor / event | Assumed capability | In scope |
| --- | --- | --- |
| DEV root / root-equivalent (PR-2 OR-2) | read, copy, restore, or rewrite any DEV file; present any authentic old world; fabricate nothing that needs K-WIT or K-ROOT | yes: the main adversary |
| Cloud snapshot principal (PR-2 OR-3) | restore the whole DEV disk to any earlier time | yes: equivalent to DEV root for freshness |
| Agent / automation on the owner workstation (Claude, Codex, CI) | write files in the working tree and push to GitHub; produce candidate records | yes: it must not be able to accept |
| GitHub compromise | rewrite or delete any repository copy | yes |
| Owner workstation rollback | restore an owner copy to an older state | yes |
| Theft of owner signing material | only relevant if PR3-D2 adopts a key | yes (§14) |
| Owner error | accept a stale world; create two competing records | yes |
| K-ROOT or K-WIT key compromise | out of scope for PR-3; handled by B1b-3e recovery | no |

## 4. The owner register contract

### 4.1 Naming

The suggested name `OwnerAuthorityRegisterV1` was **not used**, for two
reasons. It is one letter-group away from the existing, different
`OwnerAuthorizationRegisterV1` (SW-7). And the object grants no authority.
The contract is `OwnerFreshnessRecordV1`; the ordered list of records is the
*owner freshness register*.

### 4.2 `OwnerFreshnessRecordV1`

| Field | Class | Security purpose |
| --- | --- | --- |
| `recordType` = `LILITH_OWNER_FRESHNESS_RECORD` | REQUIRED | type confusion with every other contract |
| `schemaVersion` = `1` | REQUIRED | closed versioning (a `bool` is refused) |
| `environment` | REQUIRED | isolation; must equal the profile's environment |
| `authorityProfile` ∈ {`TEST_ONLY`→`test`, `DEV_SYNTHETIC`→`dev`} | REQUIRED | TEST / DEV_SYNTHETIC isolation; PROD is not modelled |
| `recordVersion` (≥ 1) | REQUIRED | owner register sequence (§9) |
| `previousRecordDigest` (null iff version 1) | REQUIRED | chain; detects splices and reordering against another copy (§10) |
| `decision` ∈ {`ACCEPT_CURRENT`, `REJECT_CANDIDATE`} | REQUIRED | owner decision; the reject decision is terminal (§11) |
| `genesisWitnessDigest` | REQUIRED | lineage root; must equal the SW-8 `OwnerGenesisPinV1` |
| `witnessVersion` | REQUIRED | ordering against the presented chain |
| `witnessDigest` | REQUIRED | exact identity of the decided world. It commits, under K-WIT, to epoch, registry head, policy, ledger sequence and head, consumed authorization, and K-WIT key ID |
| `recoveryEpoch` `{counter, random}` | REQUIRED copy | orders a presented world that is *off* the owner's lineage (epoch regression / fork). Must equal the named witness |
| `registryVersion`, `registryDigest` | REQUIRED copy | orders an off-lineage world by registry; lets the owner read what they accept. Must equal the named witness |

The record digest is
`sha256("LILITH_OWNER_FRESHNESS_RECORD_V1\0" ‖ RFC 8785 JCS(record))`. It
is **computed**, never stored, so there is no self-digest field. The stored
byte form is exactly the JCS bytes: non-canonical bytes and duplicate keys
are refused. Any acceptance envelope (PR3-D2) lies **outside** the digested
bytes, so adding one later does not change a record's identity.

**Structural rules.**

- Record 1 is `ACCEPT_CURRENT` of the genesis witness:
  `witnessVersion = 1` and `witnessDigest = genesisWitnessDigest`.
- `witnessVersion = 1` if and only if `witnessDigest = genesisWitnessDigest`.
- The genesis is never rejectable.

### 4.3 Suggested fields that were excluded

| Field | Why excluded |
| --- | --- |
| `witnessSequence` | same as `witnessVersion` |
| `authorityLedgerHead` / sequence | committed inside `witnessDigest`. The ledger-versus-witness check already exists (`authority_ledger_position_reason`). A second copy would be a second source of truth that could disagree |
| current `OWNER_ACTOR` / `PRIVACY` key IDs | derivable from the registry through the single-current-key rule (`select_current_issuance_key`). `registryDigest` binds them |
| current K-WIT key ID | committed inside `witnessDigest` and pinned by the witness anchor |
| `policyVersion` | committed inside `witnessDigest` and the registry |
| `acceptedAt` | no trusted time exists (§2). An owner-asserted clock would look like freshness evidence without being it |
| `registerDigest` (stored) | circular. It is computed instead (`record_digest`) |
| `ownerDecision` / status | kept, as `decision` |

## 5. What gives the register authority

**Authority comes from the owner's decision, not from storage.** A record is
an owner acceptance only when:

- the owner has personally reviewed a candidate against an authentic chain
  (§8), through a ceremony agents cannot perform; and
- the owner has appended that candidate to the owner's authoritative copies
  (§6).

Until PR3-D1 and PR3-D2 are decided, the only evidence of that decision is
where the record sits: in owner-custodied copies that no agent or DEV
principal can write.

A record does **not** gain authority because:

| It… | Why that is not authority |
| --- | --- |
| exists as a JSON file | any process with file access can create one |
| is committed or pushed to Git | agents and CI push to this repository. A commit proves who had push access, not what the owner decided |
| is referenced by DEV | DEV is the party being judged |
| was produced by a model | models produce **candidates** (`propose_*`). `OwnerRecordCandidateV1` is explicitly not an acceptance |
| was reported by the witness | the witness proves what it observed and advanced. It cannot accept on the owner's behalf |
| verifies under a signature | signature validity is not freshness, and not owner intent (§7) |

**Where the comparison runs.** Freshness is judged **only on the owner
side**, against the owner's own copies. DEV never evaluates its own
freshness and never holds the owner's copies. A DEV-side verifier that
wanted an owner freshness statement would need a challenge-bound,
owner-authenticated attestation (PR3-D2), so that DEV cannot replay an old
one. V1 builds none.

## 6. Off-host custody (PR3-D6)

The requirement: **the authoritative owner record must not depend on the
DEV boot disk, and must not be writable by DEV, agents, or automation.**

| Location | Outside DEV rollback domain | Owner-only writable | Survives workstation loss | Verdict |
| --- | --- | --- | --- | --- |
| owner workstation working tree | yes | **no**: agents run here with write access | no | mirror only |
| owner-controlled Git repository / GitHub | yes | **no**: agents and CI push; history can be force-pushed | yes | mirror only |
| signed owner artifact | depends on where it is stored | as its signing key (PR3-D2) | depends | a form, not a location |
| removable offline copy (USB, offline drive) | yes | **yes** while offline | yes, if kept apart | **authoritative candidate** |
| password manager / secure vault (secure note) | yes | **yes**: owner credential, no agent access | yes | **authoritative candidate** |
| second cloud account / project | yes | only with IAM excluding every automation principal | yes | not needed (over-built for V1) |
| hardware token / authenticator | yes | yes | if backed up | a signing option (PR3-D2), not storage |

**Proposed minimum model (PR3-D6).**

- At least **two** authoritative copies, both outside the DEV domain and both
  owner-only writable. For example, one password-manager secure note and one
  offline removable copy.
- They must not share a sync or backup path that could roll them back
  together.
- `reconcile_owner_replicas(minimum_replicas=2)` requires every copy present
  to be **identical**.
- GitHub may hold an extra, **non-authoritative** mirror. The repository is
  public, which is acceptable because records hold only digests and
  versions, never keys.

**Is GitHub alone sufficient? No.**

1. Agents and CI can write it, so presence there is not acceptance.
2. An account or repository compromise, or a force-push, silently rewrites
   the "latest" record.
3. It is one custody domain, so there is no second copy to reveal a
   rollback.

```text
Git history / remote storage != owner acceptance authority
```

## 7. Owner signing / approval model (PR3-D1, PR3-D2)

| Criterion | A: explicit owner ceremony, unsigned | B: distinct owner freshness key (K-OWNER-FRESH) | C: bound to the existing memory WebAuthn ceremony | C′: separate WebAuthn credential and domain for authority acceptance |
| --- | --- | --- | --- | --- |
| Custody independence from DEV | yes (storage) | yes, if the key never touches DEV | yes | yes |
| Independence from agents | only as good as the owner-only stores | a software key on the agent workstation is **not** independent; a hardware key is | user presence: agents cannot touch the authenticator | user presence |
| Replay resistance | none needed for an owner-local check; nothing to replay onto DEV | signs a record digest; replay of an *old* signed record is still possible, since signatures give no freshness | challenge-bound | challenge (= record digest) bound |
| Rollback detection | from replica comparison, not the mechanism | same; the mechanism adds nothing | same | same |
| Operational complexity | lowest | new keygen, custody, rotation, recovery | reuse, but merges two authorities | an enrollment ceremony plus a verifier over the existing B1a contracts |
| Recoverability | copy the records | a lost key needs a re-anchoring ceremony | as the credential | re-enroll, with a pinned credential list |
| Risk of becoming root authority | none: it signs nothing | **real**: a key that "accepts worlds" drifts toward K-ROOT | **real**: a memory approval could be replayed as authority acceptance | limited, if the scope is fixed to freshness records |
| Exists off-host | yes | only if the owner holds it offline or in hardware | yes | yes |

**Recommendation (accepted for DEV_SYNTHETIC as PR3-D2, §19).**

- **V1 / DEV_SYNTHETIC:** option **A**. The record digest is
  envelope-independent, so a later B or C′ envelope needs no contract
  change. This follows the accepted precedent `OwnerGenesisPinV1`
  ("deliberately unsigned; integrity from owner custody off-host").
- **Before any non-synthetic authority:** move to C′, or to B held in
  hardware. The deciding property is that no agent-accessible process can
  produce an acceptance.
- **C is rejected:** it merges memory authorization with authority-bootstrap
  acceptance.

If B is chosen later, its scope is fixed:

- It signs **only** `OwnerFreshnessRecordV1` digests, under its own domain
  separator.
- It is **not** root authority. It signs no registry, authorization, epoch,
  key, or evidence, and K-ROOT never accepts it.
- It is recoverable only through an owner re-anchoring ceremony that starts
  a new register.
- It must be held in hardware or offline, and never on DEV or in the
  repository.

**No key is generated in PR-3.**

## 8. Freshness semantics

`classify_presented_world(register, chain, environment, authority_profile)`
returns `FreshnessResultV1(authenticity, freshness, reason, detail, facts)`.

- **Authenticity** is the caller's K-WIT verification of the whole
  presented chain from genesis (`verify_witness_v2_chain`): `AUTHENTIC` or
  `NOT_AUTHENTIC`.
- **Freshness** comes only from the owner register.

The two are never collapsed.

| State | Meaning | Reasons |
| --- | --- | --- |
| `CURRENT` | authentic; head is exactly the latest accepted witness; every reached checkpoint is on the chain | — |
| `STALE` (`DEV_STATE_STALE`) | authentic, on the owner's lineage, behind the latest accepted record | `EARLIER_ACCEPTED_STATE`, `RECOVERY_EPOCH_REGRESSION`, `REGISTRY_REGRESSION`, `WITNESS_SEQUENCE_REGRESSION` |
| `AHEAD_UNACCEPTED` | authentic descendant of the latest accepted record; the owner has not accepted it | `AHEAD_LEDGER_ONLY` (no consumed authorization; same epoch and registry head), `AHEAD_AUTHORITY_CHANGING` |
| `CONFLICTING` | authentic, but not reconcilable with owner history | `GENESIS_MISMATCH`, `SAME_VERSION_DIGEST_MISMATCH`, `FORKED_FROM_ACCEPTED_HISTORY`, `RECOVERY_EPOCH_FORKED`, `OWNER_REJECTED_LINEAGE` |
| `FRESHNESS_UNKNOWN` | no owner judgment possible | `OWNER_REGISTER_NOT_VERIFIED` (unavailable, below quorum, divergent, malformed), `PRESENTED_NOT_AUTHENTIC`, `OWNER_RECORD_INCONSISTENT` |
| `REFUSED` | the question is ill-posed | `MALFORMED_INPUT`, `ENVIRONMENT_MISMATCH`, `PROFILE_MISMATCH` |

**Required fail-closed cases.**

| Case | Result |
| --- | --- |
| DEV older than the owner record | `STALE`; `EARLIER_ACCEPTED_STATE` if the head is itself an earlier checkpoint |
| DEV newer than the owner record | `AHEAD_UNACCEPTED`. Never `CURRENT` |
| digests differ at the same witness version | `CONFLICTING` / `SAME_VERSION_DIGEST_MISMATCH` |
| `recoveryEpoch` differs | older epoch: `STALE` / `RECOVERY_EPOCH_REGRESSION`; same counter with a different random: `CONFLICTING` / `RECOVERY_EPOCH_FORKED`; newer epoch while behind in witness version: `CONFLICTING` (`DIVERGENT_BEHIND`) |
| witness sequence regresses | `STALE` / `WITNESS_SEQUENCE_REGRESSION`, or `CONFLICTING` if a reached checkpoint differs |
| owner register unavailable | `FRESHNESS_UNKNOWN` (§16) |
| multiple owner records / copies conflict | `REPLICAS_DIVERGENT` → `FRESHNESS_UNKNOWN` (§11) |
| the record's copied fields disagree with the witness it names | `FRESHNESS_UNKNOWN` / `OWNER_RECORD_INCONSISTENT` |

**Granularity limit.** Freshness is relative to the latest checkpoint.
Suppose DEV is ahead ledger-only and is then restored to a point between
the checkpoint and its true head. That restore is **not detectable**. It
still classifies `AHEAD_UNACCEPTED`, or `CURRENT` if it lands exactly on the
checkpoint.

## 9. Monotonicity (PR3-D4, PR3-D5)

Not every number is independently monotonic.

| Field | Rule | Where enforced |
| --- | --- | --- |
| `recordVersion` | every record = previous + 1, from 1; counts **decisions** (accept and reject) | `verify_owner_register` |
| `witnessVersion` | strictly increasing across **accepted** records only | same |
| `recoveryEpoch` | across accepted records, partial order: `EQUAL` or `NEWER`. `OLDER` → `ACCEPTED_EPOCH_REGRESSION`; same counter, different random → `ACCEPTED_EPOCH_FORKED` | same |
| `registryVersion` | non-decreasing across accepted records; equal version requires equal digest | same |
| authority ledger sequence / head | **not** an owner-register field. Monotonic inside the witness chain (`plan_ledger_advance`) and bound by `witnessDigest` | existing contracts |
| rejected records | carry the rejected witness's fields and are not ordered against accepts | — |

**`ownerRegisterVersion` = `recordVersion`.** It is needed: freshness
advances only on accept, but the register must also detect a copy missing a
*rejection*. The genesis record is version 1.

## 10. Chaining

Each record commits to the previous record's digest through
`previousRecordDigest`. The digest construction is in §4.2.

The chain detects:

| It detects | Condition |
| --- | --- |
| an edited, reordered, or spliced earlier record | inside one copy (`PREVIOUS_RECORD_DIGEST_MISMATCH`, `RECORD_VERSION_NOT_SUCCESSOR`) |
| a skipped accepted state | when two copies are compared (`REPLICAS_DIVERGENT` `PREFIX`) |
| a forked owner history | when two copies are compared (`REPLICAS_DIVERGENT` `FORK`) |
| a truncated copy | only by comparison with another copy |

**Limit, stated plainly.** Links point backwards only. An edited **latest**
record still links correctly; it is caught only against the witness it
names (`OWNER_RECORD_INCONSISTENT`) or against another copy.

```text
a hash chain stored only in one rollback domain does not independently establish freshness
```

## 11. Fork and conflict handling (PR3-D7)

- **Witness first execution wins (preserved).** Competing K-ROOT
  authorizations from the same prior head are still settled by the witness.
  The register records only witness heads that exist. It never picks among
  authorizations.
- **Competing candidates from one accepted record.** The owner can accept
  at most one successor lineage. Once one is accepted, every other branch
  classifies `CONFLICTING` (`FORKED_FROM_ACCEPTED_HISTORY` or
  `SAME_VERSION_DIGEST_MISMATCH`). `propose_acceptance` refuses to propose
  it.
- **Owner rejection.** A `REJECT_CANDIDATE` record is terminal. It:
  - leaves the latest accepted record unchanged;
  - makes every chain that *contains* the rejected head `CONFLICTING` /
    `OWNER_REJECTED_LINEAGE`, including later descendants;
  - means any later record for the same witness digest fails
    (`WITNESS_DECIDED_TWICE`).
  A current or stale world cannot be rejected, because that would rewrite
  accepted history.
- **Stale candidate.** A stale candidate is never proposable for acceptance.
- **Ambiguous recovery.** It is `CONFLICTING` or `FRESHNESS_UNKNOWN`. It is
  never auto-resolved.
- **Divergent owner copies.** They are never resolved by length, newest
  file, or last write. Both a copy behind and a copy ahead give
  `REPLICAS_DIVERGENT`, because under option A, "longest wins" would let
  anyone who can append to one copy accept a world. The owner resolves the
  divergence by ceremony, and while it lasts every gated operation stays
  blocked.

## 12. Relation to K-ROOT

```text
K-ROOT authorization != owner off-host freshness acceptance
```

| | K-ROOT | Owner freshness register |
| --- | --- | --- |
| Role | authorizes registries, registry-head advances, and epoch advances | records which resulting world the owner accepts as latest |
| Proves | authenticity and permission of a transition | the owner's current choice among authentic worlds |
| Cannot | say which authentic registry or epoch is latest | authorize any transition, sign anything, or make a key current |

Neither subsumes the other. **Proposed owner practice (PR3-D1):** before
issuing any K-ROOT authorization, the owner confirms the presented prior
head is `CURRENT`. That is the `REGISTRY_HEAD_ADVANCE` /
`RECOVERY_EPOCH_ADVANCE` gate (§16). Meeting it is a precondition, not an
authorization.

## 13. Relation to K-WIT / RecoveryWitness

```text
RecoveryWitness freshness != owner off-host freshness
```

- **K-WIT proves** what the witness observed and advanced. Its chain orders
  heads **within one lineage on one host**, and survives only while that
  host's state does.
- **The owner register proves** which of those heads the owner accepted as
  the latest world, and it survives outside the host.

The witness never self-authorizes acceptance:

- the witness's output is the *presented chain*;
- `propose_*` produces only a candidate;
- only the owner appends.

A witness that reports a newer head yields `AHEAD_UNACCEPTED`, never
`CURRENT`.

## 14. Relation to owner WebAuthn (PR3-D9)

```text
memory authorization != authority-bootstrap acceptance
```

The memory owner-proof (B1a/B2a) approves memory operations. **Proposed:**
it neither approves owner-register records nor gates any authority
transition. If owner hardware user presence is later wanted for
acceptance, it should be C′ (§7): a separate credential with its own RP
and challenge domain and its own verifier path. The challenge is the
record digest, so a memory assertion can never be replayed as authority
acceptance, or the reverse.

## 15. Recovery semantics (PR3-D10)

**DEV restored from an old disk snapshot while the owner holds a newer
record:** the presented world classifies `STALE` = **`DEV_STATE_STALE`**.

| Step | Owner of the step | What PR-3 does |
| --- | --- | --- |
| detect | owner-side classification | `STALE`, `CONFLICTING`, or `FRESHNESS_UNKNOWN` |
| authorize recovery | owner + K-ROOT, under the B1b-3e recovery design | nothing: it authorizes nothing |
| execute recovery | the reviewed ceremony / witness | nothing: it executes nothing, and DEV is **not** repaired automatically |
| accept recovered state | owner, by a new record | only through a normal proposal and owner append |

**Structural consequence.** A DEV restored to witness version *k* < *n*
(the latest accepted) cannot rejoin the owner's lineage. Any new successor
at *k*+1 differs from the accepted one and classifies `CONFLICTING`. The
newer witness state it lost exists nowhere else (PR-2: no backups). So the
options are:

- **(R-1, recommended)** re-establish custody. This means fresh custody
  material per RR-20b, a new V2 genesis, a new genesis pin, and a **new**
  owner register lineage. The old register is retained as history and
  closed.
- **(R-2, not implemented)** a future "recovered lineage" record type that
  explicitly supersedes the old lineage under a K-ROOT epoch advance. It
  would need its own design.

V1 implements neither. It only guarantees that the stale world is never
`CURRENT`.

## 16. Owner register unavailable (PR3-D8)

If no verifiable, quorate, identical set of owner copies can be read, the
result is `FRESHNESS_UNKNOWN`. There is **no fallback** to "DEV is
internally consistent, therefore current".

`freshness_gate(result, operation)` meets its precondition **only** for
`AUTHENTIC` + `CURRENT`. Every other state blocks all six gated
operations. That includes `AHEAD_LEDGER_ONLY`, so the owner must checkpoint
before any gated step.

| Gated operation | While `FRESHNESS_UNKNOWN` / `STALE` / `AHEAD_*` / `CONFLICTING` |
| --- | --- |
| `REGISTRY_HEAD_ADVANCE` (owner issuing K-ROOT authorization) | blocked |
| `RECOVERY_EPOCH_ADVANCE` | blocked |
| `SUCCESSOR_READINESS` | blocked |
| `INITIAL_CUSTODY_RELEASE` | blocked |
| `AUTHORITY_CHANGING_ISSUANCE` (PR3-D11; added in P3-4) | blocked |
| `FIRST_MEMORY` | blocked |

DEV itself changes nothing; the gate is an owner-side precondition.
**PR3-D11 (ACCEPTED):** `AHEAD_UNACCEPTED` blocks authority-changing
issuance. Any bounded window for routine, non-authority-changing issuance
after First Memory would be a new decision in the First Memory design; V1
grants none.

## 17. Compromise matrix

| Threat | Result | Why |
| --- | --- | --- |
| attacker deletes an owner record / copy | **DETECTS** | the copies diverge, or fall below quorum → `FRESHNESS_UNKNOWN`; the other copy remains |
| attacker deletes every owner copy | **LIMITS** | `FRESHNESS_UNKNOWN` blocks all gated operations (fail closed); nothing is recoverable from DEV |
| attacker rolls back the owner workstation | **DETECTS** if at least one other copy is unaffected (`REPLICAS_DIVERGENT`); **DOES_NOT_SOLVE** if every copy rolls back together | so the copies must not share a sync or backup path |
| attacker compromises GitHub | **PREVENTS** effect on freshness | GitHub is a non-authoritative mirror only |
| attacker copies owner signing material | **DOES_NOT_SOLVE** under B; **N/A** under A | an owner-grade key would forge acceptances, which is why B must be hardware or offline if chosen |
| owner loses a device | **LIMITS** | the remaining copies still verify; with none left, `FRESHNESS_UNKNOWN` and R-1 |
| owner creates two competing records | **DETECTS** | the copies diverge (`FORK`), or `WITNESS_DECIDED_TWICE` / monotonicity refusal within one copy |
| malicious DEV proposes a higher version | **PREVENTS** acceptance by DEV | `AHEAD_UNACCEPTED`, never `CURRENT`. An inconsistent claimed record is `OWNER_RECORD_INCONSISTENT`; a forged chain is `NOT_AUTHENTIC` |
| owner accidentally accepts a stale state | **PREVENTS** in tooling; **LIMITS** overall | `propose_acceptance` refuses anything but `AHEAD_UNACCEPTED`. A hand-written record that regresses is refused by the monotonicity rules. An owner who bypasses tooling *and* the rules is not prevented |
| DEV restored while ahead ledger-only | **DOES_NOT_SOLVE** | granularity limit (§8) |
| DEV restored below the latest checkpoint | **DETECTS** | `STALE` |

## 18. Hidden assumptions

> What assumption could make this design appear correct while it is wrong?

1. **"Because the owner record is off-host, it is automatically
   trustworthy."** False. Off-host means only "outside the DEV rollback
   domain". The record is trustworthy only because:
   - acceptance semantics exist (§5);
   - custody excludes every non-owner writer (§6);
   - rollback and fork handling exists (§10, §11);
   - authenticity and freshness are separate (§8).

   Without these, it is just another file.
2. **"The owner workstation is owner-controlled."** Only partly. Agents run
   there with write access and push to GitHub. A record in the working tree
   or the repository is a candidate or mirror, never acceptance.
3. **"Two copies are independent."** Only if they share no sync or backup
   path. Two copies in one synced folder roll back together.
4. **"A valid hash chain proves the latest record."** It proves internal
   order within a copy. The latest record is established only by comparing
   copies, and an edited last record needs the witness cross-check.
5. **"`CURRENT` means safe."** It means only "equal to the owner's latest
   checkpoint". If every owner copy is rolled back together, an old world
   is `CURRENT` (a test demonstrates this).
6. **"A signed owner record is fresh."** Signature validity is not
   freshness; an old signed record replays.

## 19. Decisions (OWNER-ACCEPTED, 2026-09-29)

| ID | Question | Accepted decision | Status |
| --- | --- | --- | --- |
| PR3-D1 | owner register authority mechanism | **explicit owner ceremony.** The owner reviews a tool-derived candidate against an authentic chain, then appends it to the owner-only replicas by an explicit digest confirmation. Storage, Git, DEV, models, and the witness never confer authority | **ACCEPTED** |
| PR3-D2 | owner signing method | **unsigned ceremony (option A) for DEV_SYNTHETIC.** The record digest stays envelope-independent. Any signed or C′ envelope is a later, separate decision, taken before non-synthetic authority | **ACCEPTED** |
| PR3-D3 | canonical fields | the §4.2 `OwnerFreshnessRecordV1` fields, with the §4.3 exclusions | **ACCEPTED** |
| PR3-D4 | monotonic fields | the §9 rules | **ACCEPTED** |
| PR3-D5 | register sequence semantics | `recordVersion` is mandatory and strictly +1 per decision (accept or reject), contiguous from 1. Freshness moves on accept only | **ACCEPTED** |
| PR3-D6 | storage model | **two independent owner-controlled replicas** outside the DEV rollback domain, sharing no sync or backup path; `minimum_replicas = 2`. A GitHub mirror is non-authoritative | **ACCEPTED** |
| PR3-D7 | conflict resolution | conflicts fail closed. There is no automatic resolution by length, newest file, or last write. Rejection is terminal | **ACCEPTED** |
| PR3-D8 | unavailable-register behavior | `FRESHNESS_UNKNOWN`: fail closed, with every gated operation blocked | **ACCEPTED** |
| PR3-D9 | WebAuthn relationship | memory WebAuthn remains separate from authority-bootstrap acceptance | **ACCEPTED** |
| PR3-D10 | recovery relationship | a stale DEV is recovered only through fresh custody material, a new V2 genesis, and a **new owner register lineage** (R-1). It is never repaired or rebased | **ACCEPTED** |
| PR3-D11 | issuance while DEV is ahead of the owner | `AHEAD_UNACCEPTED` blocks authority-changing issuance. Every gated operation requires `CURRENT` | **ACCEPTED** |
| PR3-D12 | relation to `OwnerGenesisPinV1` and `OwnerAuthorizationRegisterV1` | three distinct contracts. Neither the pin nor the authorization register substitutes for the freshness register. Record 1 must bind the accepted genesis pin, and every P3-2 proposal and append re-checks the pin | **ACCEPTED** |

## 20. Nonclaims

PR-3 does **not** establish:

- real K-ROOT custody;
- K-WIT custody;
- registry publication;
- an authority ledger;
- witness genesis;
- live witness execution;
- `INITIAL_CUSTODY`;
- PR-1B completion;
- whole-host rollback prevention: **WHOLE-HOST ROLLBACK RESISTANCE = NOT
  ESTABLISHED** on DEV;
- First Memory readiness;
- a live owner register: the one real replica holds no record, and two-replica storage is incomplete (§25);
- an owner key.

It establishes only **owner-controlled freshness observation and
acceptance semantics**, plus offline tooling to apply them.

## 21. Acceptance criteria for PR-3 foundation

1. PR3-D1..PR3-D12 are decided (§19). **Done.**
2. The contract and the classification have been reviewed, and the 15
   required synthetic cases pass. Each case N maps to `test_NN`
   (1 → `test_01` through 15 → `test_15`). Supporting tests cover:
   - determinism and monotonicity;
   - the genesis pin;
   - replica divergence and joint rollback;
   - non-authentic chains and genesis mismatch;
   - the gate and proposal refusals;
   - rejection terminality and candidate ≠ acceptance;
   - source purity.
3. The P3-2 tooling tests pass (§24).
4. Both PR3-D6 replicas exist, are empty, pass the P3-3 gate, and are shown
   to be independent. **Not yet met:** Replica A exists; Replica B is
   waiting for an independent medium (§25).
5. There is no live effect. PR-3 creates no register content; record 1 can
   exist only after the V2 genesis commit.

## 22. Implementation plan

| Step | Content | Status |
| --- | --- | --- |
| P3-1 | pure contract, digest, register verification, replica reconciliation, classification, gate, and proposals, with synthetic tests | **done** (`368b36c`) |
| P3-2 | offline owner-workstation tooling (§24) | **done (this revision)** |
| P3-3 | real owner storage per PR3-D6, with the §24.4 write items resolved (§25.1) | **`P3_3_COMPLETE`** ([storage acceptance](slice-15b2b-b1b3e-pr3-p33-storage-acceptance.md)): Replica A on the laptop (WSL ext4) and Replica B on the S25 (Termux private storage, `RENAME_NOREPLACE_V1`), both empty; two independent storage domains. It was `P3_3_STORAGE_INCOMPLETE` until P3-3B (§25 is kept as the historical state) |
| P3-3A | Android-safe create-only publication: backend abstraction (`RENAME_NOREPLACE_V1` preferred, `HARDLINK_PUBLISH_V1`; `DIRECT_O_EXCL_V1` not admitted), per-backend probe, strict-read refinements, Termux probe ([record](slice-15b2b-b1b3e-pr3-android-replica-publication.md)) | **done (compatibility only)**; S25 not admitted; P3-3 still incomplete |
| P3-4 | synthetic owner freshness ceremony rehearsal (§26) and runbook template | **PASSED**; does not close P3-3 |
| P3-5 | PR-1B bootstrap sequencing design: dependency DAG, state machine (`pr1b_sequencing.py`), freshness-gate placement, PONRs, crash matrix, owner packages ([sequencing record](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md)) | **done (design only)**; PR-1B eligibility FALSE while P3-3 is incomplete |
| P3-6 | owner acceptance envelope foundation: unsigned `OwnerFreshnessAcceptanceEnvelopeV1` binding the record digest, the review package, the pin, and the custody set, in sibling acceptance stores ([envelope record](slice-15b2b-b1b3e-pr3-owner-acceptance-envelope.md)); a real-profile hard block while P3-3 is incomplete | **done (foundation only)**; a future hardware owner-presence proof stays a separate, later decision |

## 23. Validation

- `git diff --check`: clean.
- `python scripts/validate_repository.py`: pass.
- Offline unit tests, run in WSL with the pinned wheels:
  - `test_b1b3e_pr3_owner_freshness.py`: 27 tests, OK;
  - `test_b1b3e_pr3_p32_owner_freshness_tool.py`: 19 tests, OK;
  - `test_b1b3e_pr3_p33_storage_gate.py`: 16 tests, OK;
  - `test_b1b3e_pr3_p34_ceremony_rehearsal.py`: 10 tests, OK;
  - `test_b1b3e_pr3_p35_pr1b_sequencing.py`: 19 tests, OK (P3-5);
  - `test_b1b3e_pr3_p36_acceptance_envelope.py`: 23 tests, OK (P3-6);
  - `test_b1b3e_pr3_p33a_create_only_publication.py`: 30 tests, OK (P3-3A, including the probe-portability regressions);
  - full suites, all OK: `services/owner-memory-control` (634),
    `services/authority-dev` (240), and `services/recovery-witness` (44).
- No network, DEV, or cloud access.

## 24. P3-2: offline owner workstation tooling

Source: `services/owner-memory-control/lilith_owner_memory/owner_freshness_tool.py`.

This is a filesystem and CLI layer over the pure contract. It uses only the
standard library (`argparse`, `json`, `os`, `re`, `stat`, `sys`, `pathlib`,
`dataclasses`, `typing`) and the repository contracts. It has:

- no network, process, Git, cloud, DEV, or cryptography-library dependency;
- no key, and no signing;
- no use of file mtimes or ctimes.

### 24.1 Commands

```text
python -m lilith_owner_memory.owner_freshness_tool <command> [options]
```

| Command | Effect | Writes |
| --- | --- | --- |
| `init-replica --replica DIR --replica-id ID --environment E --profile P` | creates an empty replica in a directory that must **not** exist | the new directory only |
| `inspect-chain --trust T --chain C --environment E --profile P` | K-WIT-verifies an exported chain and prints authenticity and head facts, **never** freshness | nothing |
| `verify-replica --replica DIR` | strictly reads one replica | nothing |
| `compare-replicas --replica A --replica B` | reports identical, `REPLICAS_DIVERGENT` (`PREFIX` / `FORK`), or a load refusal | nothing |
| `classify --replica A --replica B --trust T --chain C --environment E --profile P` | reports authenticity, freshness, and the gate status of every gated operation | nothing |
| `propose-genesis --trust T --chain C --pin PIN --out F …` | produces a record-1 candidate. The chain must be the genesis only, and the pin must bind it | a **new** candidate file (O_EXCL) |
| `propose-accept` / `propose-reject --replica A --replica B --trust T --chain C --pin PIN --out F …` | produces an `ACCEPT_CURRENT` candidate (only from `AHEAD_UNACCEPTED`) or a `REJECT_CANDIDATE` candidate (only from `AHEAD_UNACCEPTED` or `CONFLICTING`) | a **new** candidate file |
| `append --replica TARGET --peer OTHER --candidate F --trust T --chain C --pin PIN --confirm-digest D …` | performs the owner ceremony write, into ONE replica | one record file in TARGET |

**Inputs.**

- **Trust inputs** (`LILITH_OWNER_FRESHNESS_TRUST_INPUTS`): the pinned K-WIT
  anchor, the registry root, and the registries whose keys must never sign a
  witness. Their environments must agree.
- **Chain export:** a JSON array of V2 witness documents, genesis first.
- **Pin:** an `OwnerGenesisPinV1`.

**Exit codes:** `0` OK, `2` usage, `3` refused. `classify` exits 0 and
reports the state.

### 24.2 Replica layout (explicit identity, canonical names)

```text
<replica>/
  REPLICA.json                      {"replicaType":"LILITH_OWNER_FRESHNESS_REPLICA","schemaVersion":1,
                                     "replicaId":"<id>","environment":"<env>","authorityProfile":"<profile>"}  (JCS)
  records/
    000001-<recordDigest>.json      exact JCS record bytes
    000002-<recordDigest>.json
```

**Replica identity.**

- Each replica has a `replicaId` matching `[a-z0-9][a-z0-9._-]{0,63}`.
- Two replicas must have distinct IDs, be distinct locations (`samefile`),
  and share the environment and profile.
- A copied directory is refused as `REPLICA_ID_DUPLICATED`. A replica
  compared with itself is refused as `REPLICA_SAME_LOCATION`.

**Strict read (`load_replica`).** Each of the following refuses the replica:

- the root holds anything other than exactly `REPLICA.json` and `records/`,
  including `.git` (`REPLICA_UNEXPECTED_ENTRY`);
- a file that is a symlink or not a regular file;
- a record name that does not match `NNNNNN-<64 hex>.json`;
- a gap in the versions, which must run contiguously from 1
  (`RECORD_VERSION_GAP`);
- a duplicated version (`RECORD_VERSION_DUPLICATED`);
- content that is not canonical or does not parse as a record;
- a name that disagrees with the content's version or digest
  (`RECORD_NAME_MISMATCH`);
- records that do not match the manifest profile, or a chain that does not
  verify.

Order comes from content only. File order, mtimes, Git history, and commit
times are never read. **Git metadata and timestamps have zero freshness
authority.**

**Candidate file** (`LILITH_OWNER_FRESHNESS_CANDIDATE`). It carries
`"accepted": false`, the decision, the record digest, and the record. A
candidate is not a record:

- dropped into `records/`, it is an unexpected entry;
- a candidate claiming `accepted: true` is malformed.

### 24.3 `append`: the only record writer

1. **Owner confirmation.** `--confirm-digest` must exactly equal the
   candidate's record digest, or the write refuses with
   `OWNER_CONFIRMATION_REQUIRED` / `OWNER_CONFIRMATION_MISMATCH`. This guards
   against mistakes. It is not a defense against a hostile process running
   as the owner; D6 custody is.
2. **Replica state.** Target and peer both load cleanly and are distinct.
   One of two states must hold:
   - they are identical: the first half of the ceremony (`PEER_PENDING`);
   - the peer equals the target plus exactly this record: the second half
     (`REPLICAS_IDENTICAL`).

   Anything else is `REPLICAS_NOT_APPENDABLE`. **The tool never copies
   between replicas;** each replica is written by its own owner invocation.
3. **Re-derivation.** The candidate is re-derived from the target
   replica's register, the K-WIT-verified chain, and the genesis pin (D12).
   It must be byte-identical, or the write refuses with
   `CANDIDATE_NOT_ACCEPTABLE`. Consequences:
   - a STALE, CONFLICTING, NOT_AUTHENTIC, rejected-lineage, malformed,
     version-skipping, or hand-edited candidate can never be written;
   - `AHEAD_UNACCEPTED` is accepted only through this explicit owner step.
4. **Atomic, create-only write.**
   - `records/.pending-NNNNNN-<digest>.tmp` is opened with
     `O_CREAT | O_EXCL` (plus `O_NOFOLLOW` where available), fully written,
     and **fsynced**.
   - (P3-3A: published through the admitted create-only backend. With `RENAME_NOREPLACE_V1` the pending file is renamed without replacement, so exactly one name exists after a crash. The hard-link description below is `HARDLINK_PUBLISH_V1`.)
   - It is hard-linked to `NNNNNN-<digest>.json`. The link fails if the
     name exists, so there is **no overwrite**. Any existing file with the
     same version refuses first (`RECORD_EXISTS`).
   - The pending name is unlinked, and the `records/` directory is fsynced.
5. **Post-write check.** The target is reloaded and must equal the prior
   state plus exactly this record.

**Degraded states.**

- Between the two halves of a ceremony the replicas differ, so `classify`
  reports `FRESHNESS_UNKNOWN`. This is intended, and it ends when the owner
  appends the same candidate to the peer.
- A missing, empty, or single replica is also `FRESHNESS_UNKNOWN`, with
  every gated operation blocked.

### 24.4 Items for P3-3 review (not decided here)

| Item | Current behavior | To review at P3-3 |
| --- | --- | --- |
| directory fsync | `PERFORMED` on POSIX. On Windows it is reported as `UNSUPPORTED_PLATFORM`, because NTFS offers no directory fsync through Python | whether owner replicas live on a POSIX filesystem, or a Windows-specific flush (`FlushFileBuffers` on a directory handle) is required |
| create-only publication | P3-3A: `RENAME_NOREPLACE_V1` or `HARDLINK_PUBLISH_V1`, whichever the probe admits. FAT/exFAT supports neither hard links nor necessarily `renameat2`, so it is expected to be `NONE` | resolved by [P3-3A](slice-15b2b-b1b3e-pr3-android-replica-publication.md); still needs a probe of each real medium |
| crash residue | a leftover `.pending-*` makes every read refuse (`REPLICA_PENDING_WRITE`). It is never auto-deleted | the owner's manual inspection procedure |
| password-manager / vault replica | not a filesystem, so the tool cannot write it | an export/import procedure that keeps the exact record bytes and names |
| replica placement | code enforces only identity and location checks | physical independence: no shared sync or backup path (D6) |
| GitHub mirror | never read or written by the tool | whether to keep a mirror at all, as a one-way export |

### 24.5 Tests

`test_b1b3e_pr3_p32_owner_freshness_tool.py` has 19 tests. They cover:

- the full two-replica genesis ceremony and its layout;
- explicit owner confirmation;
- candidate ≠ acceptance, including a dropped-in candidate, a forged
  candidate, and no overwriting of a candidate file;
- record 1 binding the genesis pin, at both propose and append;
- an accepted record that cannot be overwritten;
- a skipped `recordVersion`;
- a duplicate version with a different digest;
- divergent replicas (`PREFIX` and `FORK`);
- a missing or single replica → `FRESHNESS_UNKNOWN`;
- stale DEV never accepted as current;
- ahead DEV never accepted automatically (the D11 gate);
- rejected lineage, including descendants, staying rejected;
- Git metadata and timestamps having zero freshness authority;
- refusal of a hand-edited candidate;
- the authorization register and the pin never substituting for the
  freshness register;
- replica identity and layout rules;
- a pending write that refuses without repair;
- `inspect-chain` reporting authenticity only;
- no network, process, or key dependency.

## 25. P3-3: owner off-host storage foundation

> **Superseded status (2026-09-29).** P3-3 is now **`P3_3_COMPLETE`**. Replica B was initialized on the S25 Ultra (P3-3B) and accepted in the [P3-3 storage acceptance](slice-15b2b-b1b3e-pr3-p33-storage-acceptance.md). This section records the earlier `P3_3_STORAGE_INCOMPLETE` state. Both replicas remain empty, real freshness remains `FRESHNESS_UNKNOWN`, and the real-profile acceptance block stays in source until a separately reviewed change.

**Result: `P3_3_STORAGE_INCOMPLETE`.** Replica A exists and is empty. There
is no suitable second medium, so Replica B was not created. The two-copy
policy (D6) is therefore unsatisfied, and **`FRESHNESS_UNKNOWN` remains
mandatory**.

The rest of this section records:

- the accepted P3-3 storage decisions;
- the gate that enforces them;
- the actual state of each replica.

### 25.1 Decisions (P3-3, owner-given)

| Decision | Rule | Enforced by |
| --- | --- | --- |
| directory fsync REQUIRED | a real replica needs a strict directory fsync; there is no warning-only mode | `probe_storage` (`_directory_fsync_strict`), and `init_real_replica` requires `directoryFsync = PERFORMED` |
| ~~hard links REQUIRED~~ → **a reviewed create-only backend REQUIRED** (amended by [P3-3A](slice-15b2b-b1b3e-pr3-android-replica-publication.md)) | at least one admitted backend (`RENAME_NOREPLACE_V1` preferred, `HARDLINK_PUBLISH_V1`) must pass the create-only contract. There is never a fallback to an overwriting rename, and `DIRECT_O_EXCL_V1` is not admitted | `probe_storage` (`backends`, `admittedBackend`) |
| location policy | no Git working tree; no automatically synchronized root; not on DEV; not in the same tree as the other replica | `location_policy`, `init_real_replica --other-replica` |
| independence | two directories are not two rollback domains; same device refused | `check_independence`; owner evidence (§25.4) |
| no record creation | P3-3 never proposes or appends | no P3-3 command writes a record |

P3-2's generic behavior is unchanged: `init-replica` still reports
directory fsync rather than requiring it. Only `init-real-replica` applies
the P3-3 gate.

### 25.2 Gate source (commit `7880df8`)

These additions are in `owner_freshness_tool.py`.

- **`probe-storage --probe-parent DIR`.** It creates only a fresh
  `.lilith-p3-probe-<random>` directory and removes it afterwards. It
  refuses to run inside an initialized replica. It checks, in order:
  - exclusive create;
  - file fsync;
  - hard-link creation;
  - that a hard link cannot replace an existing path;
  - strict directory fsync;
  - rename within a directory;
  - symlink detection (a symlink is refused as not a regular file);
  - canonical reread;
  - cleanup.

  The result is `P3_STORAGE_CAPABLE` or `P3_STORAGE_INCAPABLE`.
- **`location-check --path P`.** It refuses:
  - `LOCATION_IN_GIT_WORKTREE`: any ancestor holds `.git`, whether a
    directory or a worktree file;
  - `LOCATION_AUTO_SYNC_ROOT`: a path component names a known sync root
    (OneDrive, Dropbox, Google Drive / My Drive, iCloud, Box, Nextcloud,
    ownCloud, pCloud, MEGA, Syncthing, Resilio), or the path is under an
    `OneDrive*`/`Dropbox*` environment root.

  Unknown sync or backup mechanisms cannot be excluded by code.
- **`init-real-replica --replica DIR --replica-id ID --environment dev --profile DEV_SYNTHETIC [--other-replica OTHER]`.**
  Admission runs in this order:
  1. profile and ID are checked;
  2. the location policy is applied;
  3. the path must not exist;
  4. against `--other-replica`: a distinct ID, and a distinct `st_dev`
     (`REPLICA_SAME_DEVICE`);
  5. the probe must pass on the parent;
  6. `init_replica` runs, with directory fsync required;
  7. an empty-replica proof follows.
- **`check-independence --replica A --replica B`.** It refuses the same
  ID, the same location, or the same device. A result of
  `DISTINCT_DEVICES_OBSERVED` is necessary evidence only.

Tests are in `test_b1b3e_pr3_p33_storage_gate.py` (16 tests). They cover:

- a capable probe that cleans up;
- hard links unsupported → incapable;
- a link that replaces an existing path → incapable;
- directory fsync unsupported → incapable, and `init-real-replica` refuses
  with nothing created;
- directory fsync reported but not performed → refused;
- symlinks unavailable → incapable;
- a probe refused inside a replica;
- an initialized replica staying empty;
- an existing directory refused;
- Git working-tree locations refused (directory and `.git` file);
- known auto-sync locations refused (path components and the OneDrive
  environment root);
- the same replica ID refused;
- the same device refused;
- the same replica path refused;
- the CLI.

### 25.3 Replica state

**Replica A: owner primary, DEV_SYNTHETIC.**

| Property | Value |
| --- | --- |
| Storage class | the owner workstation's WSL2 Ubuntu-24.04 distribution: an ext4 filesystem inside a WSL virtual disk (VHDX) on the workstation's internal NVMe SSD |
| Replica ID | `owner-primary-dev-synthetic-01` (the tool's replica-ID grammar is lowercase, so this is the lowercase form of the suggested `OWNER-PRIMARY-DEV-SYNTHETIC-01`) |
| Environment / profile | `dev` / `DEV_SYNTHETIC` |
| Capability probe | **`P3_STORAGE_CAPABLE`**: all nine checks true, including strict directory fsync and hard-link no-replace |
| Initialization | **`REAL_REPLICA_INITIALIZED_EMPTY`**, via `init-real-replica` from the tool at commit `7880df8`, staged outside any Git tree |
| Contents | `REPLICA.json` (166 bytes, SHA-256 `fbdd045c…`), plus `records/`, **empty**. No other entry. `verify-replica` gives `REPLICA_VERIFIED`, `records = 0`, `headDigest = null` |
| Permissions | replica directory and `records/` are `0700`; `REPLICA.json` is `0600`; owner `root:root` (the WSL default user) |
| Filesystem identity | ext4 root of the distribution, one `st_dev` for the whole distribution. The raw device and UUID are private |
| Git relationship | none: no `.git` in any ancestor; outside the LILITH repository and every worktree |
| Auto-sync | none observed. The VHDX is under the user's local application-data directory, not under OneDrive, which backs up only Documents and Desktop. The distribution has Windows drive automount **disabled** and Windows interop **disabled** |
| Backup relationship | File History is not configured, and no image-backup tool was observed. Windows restore points / VSS were **not examined** (that needs administrator rights): UNKNOWN |
| Rollback paths | `wsl --export`/`--import`, a copy of the VHDX, any whole-disk image of the NVMe, restore points if enabled, and `wsl --unregister` (destruction) |

**Replica B: owner offline.**

| Property | Value |
| --- | --- |
| Candidate media | **none.** The workstation has exactly one physical disk (the internal NVMe, one `C:` volume) and no removable, USB, or secondary drive |
| Capability probe | **not run**: there is no candidate filesystem to probe. A probe of another directory on the same NVMe would prove nothing about independence |
| Initialization | **not performed.** Per §7 and §13 of the P3-3 task, Replica B is not fabricated on the same WSL virtual disk or on the same physical disk |
| Replica ID reserved | `owner-offline-dev-synthetic-01` |

### 25.4 Independence

> Can one ordinary rollback operation restore both replicas together?

This is **not applicable yet**, because only one replica exists.
Independence is **NOT ESTABLISHED**.

A future Replica B must satisfy all of the following:

- its own physical medium, with a filesystem that passes the probe. That
  means ext4, or another filesystem with hard links and directory fsync.
  FAT/exFAT is not assumed acceptable, and NTFS through WSL drvfs is not
  admitted unless it passes;
- a distinct `st_dev` from Replica A;
- no shared sync or backup path with Replica A;
- initialization through `init-real-replica --other-replica <Replica A>`.

Once both replicas exist, answering the question above will still require
owner evidence about backups. Distinct devices are necessary but not
sufficient.

```text
two directories   != two rollback domains
two replica IDs   != independent custody
removable media   != safe media
offline           != authoritative
storage capability != owner acceptance
```

### 25.5 Limitations

1. **Agent reachability.** Replica A sits in a WSL distribution that the
   same workstation's agent tooling can reach as root. D6 requires replicas
   that no agent or automation can write, and a WSL location on the agent
   workstation does **not** meet that requirement on its own. Before record
   1, at least one of these must hold:
   - Replica B, offline and disconnected when not in use, provides the
     agent-unreachable copy;
   - access to Replica A is otherwise separated from agent sessions.

   This is an open custody item. P3-3 does not resolve it.
2. **One physical disk.** Replica A shares the NVMe with the whole
   workstation, so a workstation-level image restore rolls it back.
3. **Restore points / VSS** were not examined.
4. **Staged tool copy.** The tool copy used for initialization remains in
   the WSL home directory, outside any Git tree.

### 25.6 Privacy and redaction

Public documentation records:

- the storage class, independence property, capability result, and replica
  IDs;
- the replica contents digest.

The following stay private (off-repository evidence, `SHA256SUMS`
`f1f69883…`):

- absolute paths;
- VHDX location, device numbers, and filesystem UUIDs;
- disk model.

Neither real replica, nor any real `REPLICA.json`, is committed or placed
on GitHub.

### 25.7 Failure semantics and next step

- Replica A is **kept**: it is not deleted.
- No second replica is fabricated.
- Every `classify` against the real replicas must be `FRESHNESS_UNKNOWN`
  (`REPLICA_QUORUM_UNMET` or `REPLICA_MISSING`), with every gated operation
  blocked.
- **To complete P3-3:** the owner attaches an independent medium, then
  runs, in order:
  1. `probe-storage` on it;
  2. `init-real-replica --replica <B> --replica-id owner-offline-dev-synthetic-01 --environment dev --profile DEV_SYNTHETIC --other-replica <A>`;
  3. `check-independence`.

  The owner also supplies the backup evidence for §25.4.

**No freshness record exists.**

- No `propose-*` or `append` was run against any real replica.
- Replica A's `records/` is empty.
- The accepted record count is **0**, and there is no record 1.

## 26. P3-4: synthetic owner freshness ceremony rehearsal

**Result: P3-4 PASSED.** This result does NOT close P3-3. **P3-3 remains
`P3_3_STORAGE_INCOMPLETE`** and is blocked on independent storage. Real
Replica A remains empty and non-authoritative, and every real
classification remains `FRESHNESS_UNKNOWN`.

```text
synthetic ceremony success != real owner freshness established
```

### 26.1 How it was run

The tests are in `test_b1b3e_pr3_p34_ceremony_rehearsal.py` (10 tests).
They drive the P3-2 CLI (`T.run`) through the runbook's ten steps, over two
**temporary** replica directories created per test with distinct IDs.

The authority worlds are real K-WIT-signed TEST chains from the B1b-3e
synthetic scenario, under the `TEST_ONLY` profile. The synthetic witness
writer admits only `test`; a `DEV_SYNTHETIC` rehearsal would need
DEV-environment chains, which exist nowhere.

The real Replica A is never read or written. The runbook is at
[slice-15b2b-b1b3e-pr3-owner-ceremony-runbook.md](slice-15b2b-b1b3e-pr3-owner-ceremony-runbook.md).

### 26.2 Rehearsal results

| Case | Result |
| --- | --- |
| Genesis | Before any record: `FRESHNESS_UNKNOWN`. A proposal leaves both replicas empty (proposal ≠ acceptance). Record 1 equals the synthetic pin. After the first `--confirm-digest` append: `FRESHNESS_UNKNOWN` (`REPLICAS_DIVERGENT … PREFIX`), with every gate blocked. After the second: the replicas are byte-identical and `compare-replicas` returns `OWNER_REGISTER_VERIFIED`. The matching world is `AUTHENTIC` + `CURRENT`, with every gate met |
| Successor acceptance | Before: `AHEAD_UNACCEPTED` / `AHEAD_AUTHORITY_CHANGING`, every gate `BLOCKED`. After replica A only: `FRESHNESS_UNKNOWN`. After replica B: `CURRENT`. `recordVersion` runs 1 → 2; `previousRecordDigest` is null for record 1 and record 1's digest for record 2 |
| Stale DEV | The older world, presented after the newer acceptance: `AUTHENTIC` + `STALE` / `EARLIER_ACCEPTED_STATE` (`DEV_STATE_STALE`). All gates are blocked. The replicas are unchanged, and there is no repair |
| Conflict | Competing successors from one accepted head. Branch B is longer and later-stamped; both are `AHEAD_UNACCEPTED` until the owner decides, so there is no automatic witness preference. After the owner accepts A, B is `CONFLICTING` / `FORKED_FROM_ACCEPTED_HISTORY`: no longest-chain rule. Proposing B is refused: no last-write-wins. Injected owner-copy divergence gives `REPLICAS_DIVERGENT … FORK` → `FRESHNESS_UNKNOWN`, even when mtimes favor the diverging copy: no timestamp rule. A `.git` entry in a replica gives `REPLICA_UNEXPECTED_ENTRY`: no Git rule |
| Rejection | The chained record 2 is `REJECT_CANDIDATE`, with `previousRecordDigest` = record 1. The chain export is byte-unchanged (DEV not mutated). The rejected head and a later descendant are `CONFLICTING` / `OWNER_REJECTED_LINEAGE`, and the descendant can never be proposed for acceptance. Every gate stays blocked, the previously accepted world stays `CURRENT`, and the rejection record is not an authorization-register input (rejection ≠ recovery authorization) |
| Register loss | Replica A missing: `FRESHNESS_UNKNOWN` (`REPLICA_MISSING`). Replica B missing: the same. One copy behind: `FRESHNESS_UNKNOWN` (`REPLICAS_DIVERGENT:replica1:PREFIX`). Both missing: `FRESHNESS_UNKNOWN`. Every gate is blocked in all four cases |
| Joint rollback (**limitation**) | With both copies restored to the same old history, the register verifies and the **old world classifies falsely `CURRENT`**, while the true latest world classifies `AHEAD_UNACCEPTED`. Only an independently newer copy, or the owner's own memory, reveals this. This is preserved as an explicit limitation (§17, runbook) |
| Recovery detection | The owner accepts world N−1 and then N; DEV presents N−1. The result is `AUTHENTIC` + `STALE` (`DEV_STATE_STALE`), with every gate blocked. The tool has no recover, repair, or rollback command, and detection writes nothing |

```text
detect != authorize recovery;  authorize != execute;  execute != accept recovered state
```

### 26.3 Gate matrix

`freshness_gate` over the six gated operations. `AUTHORITY_CHANGING_ISSUANCE`
was added in P3-4, which makes D11 explicit.

| Presented state | Registry-head advance | RecoveryEpoch advance | Successor-key readiness | INITIAL_CUSTODY release | Authority-changing issuance | First Memory |
| --- | --- | --- | --- | --- | --- | --- |
| `AUTHENTIC` + `CURRENT` | MET | MET | MET | MET | MET | MET |
| `STALE` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED |
| `AHEAD_UNACCEPTED` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED |
| `CONFLICTING` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED |
| `FRESHNESS_UNKNOWN` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED |
| `NOT_AUTHENTIC` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED |
| `REFUSED` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED |

Only `AUTHENTIC` + `CURRENT` meets the freshness precondition, and meeting
it authorizes nothing. A hand-built `NOT_AUTHENTIC` + `CURRENT` result is
also blocked.

### 26.4 Real-state guard

`RealStateGuard` models the real P3-3 state in temporary directories: one
empty Replica A, and no Replica B. It asserts that this state yields
`FRESHNESS_UNKNOWN`, with every gate blocked, whether one or two `--replica`
paths are given. It further asserts:

- that holds even after a synthetic record 1 exists in the single replica;
- `append` refuses a replica as its own peer;
- `MINIMUM_REPLICAS` = 2.

It also asserts that this record keeps `P3_3_STORAGE_INCOMPLETE` and
`FRESHNESS_UNKNOWN`, and that the runbook contains no private path or
device identifiers.

**This guard must stay until real P3-3 completion.** A read-only
`verify-replica` of the real Replica A, taken after P3-4, reports 0
records.

```text
P3-4 SYNTHETIC REHEARSAL ONLY — P3-4 PASSED; P3-3 REMAINS P3_3_STORAGE_INCOMPLETE
REAL REPLICA A REMAINS EMPTY      NO REAL RECORD 1      FRESHNESS_UNKNOWN REMAINS REQUIRED
NO OWNER KEY    NO DEV CONTACT    NO CLOUD CONTACT      NO K-WIT     NO REGISTRY
NO LEDGER       NO WITNESS STATE  NO HOLD               NO RECOVERY EPOCH
NO INITIAL_CUSTODY                PR-1B NOT AUTHORIZED  FIRST MEMORY NOT AUTHORIZED
```
