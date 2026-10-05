# Contract Source Review Manifest

```text
NON-AUTHORITATIVE
TRIAGE / PROVENANCE ONLY
NO SOURCE OR CLAUSE ACCEPTED
```

| Field | Value |
| --- | --- |
| Record type | Non-authoritative source review manifest (provenance, integrity, triage, dependencies, disposition) |
| Manifest version | 0.1 (draft for owner review) |
| Date | 2026-10-05 |
| Repository baseline | `7e4ab6ba1bd6d4f6fa27753853c8d411c892f1f2` |
| Governing rule | [ADR-0014](../../adr/0014-proposed-cognitive-sources-enter-architecture-through-native-acceptance.md) — **Accepted** (2026-10-05) as the source-governance mechanism only; it does not make this manifest authoritative |
| Sources covered | All 16 documents of the [Cognitive Architecture Contract Set v0.1](v0.1/README.md) |
| Ledger decision | D-9 — RESOLVED by ADR-0014 (2026-10-05) as source governance only; no source or clause accepted |
| Private archive accessed | No |
| Source text in this manifest | None. No clause wording exists in the repository |

## 1. What this manifest is and is not

This manifest tracks provenance, integrity metadata, triage, dependencies and
disposition for the 16 proposed sources. It is **not** an ADR, a contract, a
policy, an acceptance record, an authority grant or a controlling architecture
source. Under ADR-0014 (SG-10) it is also not a "versioned
contract" for the [document authority order](../../README.md#document-authority).

- No field, status or value in this manifest makes a source or clause
  accepted. There is no `ACCEPTED` status.
- No entry is `REVIEW_READY`.
- Dispositions are triage labels. They are revisable and carry no authority.
- If semantics from a clause are later accepted in a native record (an ADR,
  domain contract or policy), the entry may record
  `TRANSLATED_INTO <native record>`. The native record controls; this
  manifest only points to it.
- Accepted native architecture controls over every entry here.

```text
manifest disposition  ≠  architecture
REVIEW_READY          ≠  accepted
ALREADY_COVERED       ≠  verified textual equivalence
ledger paraphrase     ≠  source text
```

This file sits outside `v0.1/` on purpose. The index states that `v0.1/`
holds only its README and the hash list, and a later source version is a new
review input (ADR-0014 SG-12), so the manifest is not part of any one source
package.

## 2. Disposition vocabulary

| Status | Meaning (triage only) |
| --- | --- |
| `NEEDS_SOURCE_TEXT` | No reviewable clause text is in the repository. **Applies to every entry today** in addition to any status below |
| `SOURCE_INTEGRITY_BLOCKED` | Source provenance blocks review whatever text is supplied (sources 07, 08). It is the **controlling blocker** for those sources: they also lack repository-readable text, but supplying text alone never makes them `REVIEW_READY`. Only an explicit owner provenance decision could change this; none is made |
| `ALREADY_COVERED_BY_NATIVE_ARCHITECTURE` | An accepted native record already governs the topic. Based on topic overlap with the ledger paraphrase, **not** on verified textual equivalence. Not reviewed merely to create duplicate law |
| `TRANSLATED_INTO_NATIVE_RECORD` | A native record now controls the semantics. **No entry has this status** |
| `DEFER_DEPENDENCY` | An unresolved decision, policy or design must come first. Stays deferred even if text later appears |
| `REJECT_REDUNDANT` | Recommendation not to review: the clause family adds no architectural semantics (for example, a pure non-authorization statement already made by the index). Reversible; not a rejection of the source |
| `CONFLICT_RISK_REVIEW_REQUIRED` | The paraphrase suggests the clause may draw an accepted boundary differently. Not a confirmed conflict |
| `OUT_OF_SCOPE` | Not a subject for source review; existing repository records control |
| `REVIEW_READY` | Eligibility for owner review only, once ADR-0014 SG-6 is met. **No entry has this status** |

Queue hints (`Q-03` … `Q-15`, §5) are notes, not statuses.

## 3. Pinning and identifiers

- Every entry is pinned to source number, version `0.1` and the SHA-256 in
  §4. No derivative exists, so every derivative digest is `NONE`.
- A later version, a different file or a regenerated edition is a new review
  input and inherits no disposition (ADR-0014 SG-12).
- Clause IDs are **source-qualified**: `01:ID-01`, never bare `ID-01`.
  Source 01's `ID-`, `AUTH-` and `AFF-` clause IDs collide with ledger row
  IDs. Ledger rows are always written "ledger ID-01".
- Clause IDs are copied from the ledger's "Source clauses" column. Clause
  IDs the ledger does not cite are not listed; whether they exist is
  UNKNOWN.
- IDs for sources 07 and 08 are local to the regenerated editions.

## 4. Source register (all 16)

Common to every source: version `0.1`; derivative digest `NONE`; text
availability `INDEX_METADATA_ONLY` (ledger paraphrase only for cited clauses);
authorship / provenance author `UNKNOWN / not recorded`; status in the index
PROPOSED / NOT ACCEPTED. The private conversation identifier the PDFs cite is
not authorship and is not reproduced here.

| # | Title | Source SHA-256 | Provenance state | Source-level disposition | Native overlap (topic) | Principal dependencies | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 01 | LILITH Identity Invariant Specification v0.1 | `3e07a2c05157b0129a26532603b20a68f806df520d291fc76d974210767d00f7` | Direct design artifact; bytes private | NEEDS_SOURCE_TEXT; mostly DEFER_DEPENDENCY | ADR-0001, ADR-0002, ADR-0008 | Identity charter (15B2b-B owner decision 2); C-07; substrate-drift policy | Clause IDs collide with ledger rows |
| 02 | LILITH First Memory Semantic & Acceptance Specification v0.1 | `d9e1d38f8c2c5a16ad4057468e679bac73901c7c83c1722a7e3fd62ffa43b47a` | Direct; private | NEEDS_SOURCE_TEXT; DEFER_DEPENDENCY | ADR-0006 | 15B2b-C; owner decisions 2/3/4/6/7; First Memory NOT AUTHORIZED | Review of semantics would not be authorization in any case |
| 03 | LILITH Continuity Benchmark & Evaluation Protocol v0.1 | `9996bcf0a7f362218e9ca943a38732e97a5ca70191d09918fd068d18e865ab95` | Direct; private | NEEDS_SOURCE_TEXT; queue hint Q-03 | ADR-0001 (Validation), ADR-0003 | — | Evaluation protocol; no accepted ADR covers it |
| 04 | LILITH Model / Runtime Adapter & Handoff Specification v0.1 | `0e4e6bae3b0177cc5e35f9c29a4b4ba66b8988aa330638d9fe03fc93848380a1` | Direct; private | NEEDS_SOURCE_TEXT; DEFER_DEPENDENCY; one CONFLICT_RISK entry | ADR-0001, ADR-0009, ADR-0011 | Adapter / handoff contract; privacy / model-route policy; G2, R1 | ADR-0011 declined to adopt the handoff state machine |
| 05 | LILITH Memory Lifecycle & Reappraisal Specification v0.1 | `44c0952df8409e639f2dab689d1708641dbba27de9850b1b47fc5a3120b2db27` | Direct; private | NEEDS_SOURCE_TEXT; queue hint Q-05 | ADR-0006, ADR-0002 | 15B2b owner decisions 3/6/7; C-08 (memory scope); identity charter | — |
| 06 | LILITH Personality Evolution Specification v0.1 | `ffab7feb8cb29d6bb8c665ffe6eabfa26d7f6914d7292e2611db8776515083ae` | Direct; private | NEEDS_SOURCE_TEXT; DEFER_DEPENDENCY | ADR-0008, ADR-0001, ADR-0007 | Personality-domain design (no writer or acceptor designated); C-11; R6 | — |
| 07 | LILITH Relationship Continuity Specification v0.1 | `0c21de4a50073cfbea1265807bc4db7348d5a10a3d752ec8696e5e3070d61cce` | **Regenerated edition; original unavailable; not certified byte-identical** | **SOURCE_INTEGRITY_BLOCKED** | ADR-0001, ADR-0007 | Owner provenance decision (not made); relationship owner design | Supplying regenerated text does not unblock (ADR-0014 SG-8) |
| 08 | LILITH Affect / Appraisal Research Protocol v0.1 | `e1a670820694da18b77ed5e8c6c725eb9a20926aaa8e9bfbb1248e5dc436e632` | **Regenerated edition; original unavailable; not certified byte-identical** | **SOURCE_INTEGRITY_BLOCKED** | None (affect deferred by Slice 11 decision 1) | Owner provenance decision (not made); affect deferral | Supplying regenerated text does not unblock (ADR-0014 SG-8) |
| 09 | LILITH Cognitive Recovery, Migration & Multi-Device Continuity Specification v0.1 | `bfdf6aff8434dae45e3a4bd7b011ed9bf10eaa25832ffaa6da6167d2044e1933` | Direct; private | NEEDS_SOURCE_TEXT; mostly DEFER_DEPENDENCY | ADR-0001, ADR-0002, ADR-0003, ADR-0006 | C-07; C-15; C-16; substrate-drift policy; session / presence ownership | — |
| 10 | LILITH Hsin Semantic Integration & Session Presence Specification v0.1 | `edb0e2470ec8c77d85641933790f0bc61af0d8d6490140ba5888491a2bf76155` | Direct; private | NEEDS_SOURCE_TEXT; queue hint Q-10 | ADR-0001, ADR-0004, ADR-0009 | Session / presence ownership; privacy policy | Repository "Hsin" is an avatar renderer only |
| 11 | LILITH Goal, Commitment & Intention Continuity Specification v0.1 | `ce8389147bb3581d4599297c6898c65a3195b4e1543406120ee363f1aabd022b` | Direct; private | NEEDS_SOURCE_TEXT; queue hint Q-11 | ADR-0012, ADR-0003, ADR-0007, ADR-0009 | GOAL-04; C-18; C-07; privacy policy | `11:GC-16` is not accepted; ADR-0012 decided D-7 independently |
| 12 | LILITH Initiative, Interruption & Autonomous Action Specification v0.1 | `8aaf1ea910898305d9ec93288164a59f10494c1685be96c346b5b96df173a79b` | Direct; private | NEEDS_SOURCE_TEXT; DEFER_DEPENDENCY | ADR-0003, ADR-0004, ADR-0009 | R13 inventory; capability policy; G1, G2, R1; RQ-025/030..032 | Work-lease clauses touch an ADR-0009 revisit trigger |
| 13 | LILITH Learning, Skill Acquisition & Competence Development Specification v0.1 | `99b023fe69d4d7bf2e6acc587b53c07f49da51c6b5fbbdf209b0178f830a60da` | Direct; private; collected later on 2026-10-04; matches document 16's register | NEEDS_SOURCE_TEXT; ALREADY_COVERED / DEFER_DEPENDENCY | ADR-0010, ADR-0006, ADR-0003 | C-20; Procedural Skill domain design; G1 | C-20 is not resolved here |
| 14 | LILITH Self-Model, Metacognition & Capability Awareness Specification v0.1 | `51984caab58cf3208e1004fd45401ea7462c01df7a7b5a83b6d3df496b8b84db` | Direct; private | NEEDS_SOURCE_TEXT; queue hint Q-14 | ADR-0001, ADR-0008, ADR-0013 | Self-model owner (none designated); G1 | — |
| 15 | LILITH Epistemic Integrity, Belief State & Uncertainty Governance Specification v0.1 | `ac653b8ff30847c73e0eda3ea47f5f8e6993314c82898651a2096b8fa4a47d6e` | Direct; private | NEEDS_SOURCE_TEXT; queue hint Q-15 | ADR-0013, ADR-0003 | EPI-11; C-22; EPI-08; source-trust policy | `15:E-25`, `15:E-26` are not accepted; ADR-0013 decided D-8 independently |
| 16 | LILITH Integrated Cognitive Architecture & Composition Contract v0.1 | `69dfd5fa998111fff4e2ddf96e35afb140b9de81bb07007c5674986c1ec6ce3f` | Direct; private; composition / index document. Its register cross-pins 01–15; the index records that every entry that could be extracted automatically matched, not which entries were checked | NEEDS_SOURCE_TEXT; mostly ALREADY_COVERED | ADR-0007 and all others | Adapter contract; EPI-08 | COMP-30 and COMP-36 are existing enforcement concerns (ledger §2.1) |

## 5. Conditional review queue (hints only)

These families are the D-9 discovery candidate set (owner-reviewed
2026-10-05) of families that may add to accepted architecture. The initial
queue is kept aligned with that set; it does not expand during manifest
drafting (§5.1). **They are based on ledger paraphrases only.** Queue
inclusion is not a semantic endorsement and grants no precedence or
authority. Every family is `NEEDS_SOURCE_TEXT`, none is `REVIEW_READY`, none
is accepted, the exact source text must be reviewed before any native record
is drafted from it, and a dependency may still defer a family after text
appears.

| Hint | Families (source-qualified) | Ledger rows | Why listed (paraphrase-based) | Possible dependency |
| --- | --- | --- | --- | --- |
| Q-03 | `03:CB-03`…`03:CB-21`, `03:CB-23`, `03:CB-24` | EVAL-02 … EVAL-07 | Evaluation protocol; ADR-0001 validation needs scenarios; no native protocol exists | RQ-044, RQ-045 design |
| Q-05 | `05:ML-07`, `05:ML-19`, `05:ML-20` (archive / activity axis); `05:ML-15`, `05:ML-16` (reappraisal) | MEM-05; MEM-09 | Not decided by ADR-0006 | Memory-class profiles (owner decision 3) |
| Q-10 | `10:HS-26`…`10:HS-28` (expression ≠ affect) | HSIN-10 | Presentation-honesty semantics not decided natively | C-13 |
| Q-11 | `11:GC-03`, `11:GC-04`, `11:GC-27`…`11:GC-31`; `11:GC-17`…`11:GC-20`; `11:GC-21`, `11:GC-22`; `11:GC-23`, `11:GC-24` | GOAL-01; GOAL-07; GOAL-08; GOAL-09 | Goal distinctions, arbitration, completion evidence and cancellation states not decided by ADR-0012 | — |
| Q-14 | `14:SM-03`, `14:SM-04`, `14:SM-11`, `14:SM-12`; `14:SM-17`, `14:SM-18`, `14:SM-32` | META-01; META-06 | Capability awareness ≠ grant (Router-path view); known-unknown states | G1 for the frontend part |
| Q-15 | `15:E-03`, `15:E-04`, `15:E-29`; `15:E-10`, `15:E-11`; `15:E-21`; `15:E-22`…`15:E-24`; `15:E-35`…`15:E-37` | EPI-01; EPI-05; EPI-09; EPI-10; EPI-12 | Observation ≠ fact, abstention, absence of evidence, uncertainty, tool success ≠ proposition; not decided by ADR-0013 | Source-trust policy for any ranking element |

### 5.1 Reconciliation with the D-9 discovery candidate set

The queue was checked family by family against the discovery set. The
discovery report is owner-reviewed session output, not a repository record;
the ledger rows cited are the repository evidence.

| Item | Discovery set | Result in this manifest | Evidence and reason |
| --- | --- | --- | --- |
| Q-03 | "03 CB-*" (evaluation protocol) | `03:CB-03`…`21`, `23`, `24` | Narrowed, not expanded. `03:CB-01`, `02`, `22` (ledger EVAL-01) are excluded because discovery classed them as redundant non-authorization statements (entry 03-a, REJECT_REDUNDANT). `03:CB-S20`, `03:CB-S23` are cited by the ledger only in ID-08 as identity regression cues and stay DEFER_DEPENDENCY on the identity verifier (entry 03-h). Owner review may restore either |
| Q-05 | "05 ML-05/19/20" and "ML-15/16" | `05:ML-07`, `19`, `20`; `05:ML-15`, `16` | **Discovery identifier corrected.** Ledger row MEM-05 (archive ≠ active memory; activity axis) cites `ML-07, ML-19, ML-20`. `ML-05` appears in the ledger only in row MEM-04 (`ML-05..ML-08`: identity / branch binding, typed missing states), which is DEFER_DEPENDENCY on the identity charter (entry 05-d). Discovery's "ML-05" conflated ledger row MEM-05 with clause `05:ML-05`. No claim is made about either clause's meaning beyond the ledger paraphrase |
| Q-10 | "10 HS-26..28" | `10:HS-26`…`28` | Aligned. Note for owner review: the proposal-pass direction described this hint as "session / floor families", while discovery named the expression ≠ affect family (HSIN-10). The queue follows discovery |
| Q-11 | "GC-03/04/27..31, GC-17..20, GC-21/22, GC-23/24" | Same | Aligned |
| Q-14 | "SM-03/04/11/12 (Router-path view), SM-17/18/32" | Same | Aligned |
| Q-15 | "E-03/04/29, E-10/11, E-21, E-22..24, E-35..37" | Same | Aligned |

Families added during manifest drafting and **removed from the initial
queue** under the conservative initial-queue rule. Each stays in §6 with its
ordinary disposition; none is rejected or deferred by this removal.

| Family | Ledger row and paraphrase (non-authoritative) | Why it looked possibly additive | Dependency | Disposition now |
| --- | --- | --- | --- | --- |
| `10:HS-10`…`10:HS-12` | HSIN-05: floor (speak / listen / interrupt / render / act) separate from authority; focus, proximity, wake words grant nothing | A non-grant rule; no native record decides floor semantics | Session / presence ownership could defer it | 10-e: NEEDS_SOURCE_TEXT (not queued) |
| `10:HS-17`, `10:HS-18`, `10:HS-40`…`10:HS-42` | HSIN-07: intent / synthesis / dispatch / delivery / ack distinct; stale callbacks cannot act | Effect-stage separation for speech; no native record | None recorded | 10-g: NEEDS_SOURCE_TEXT (not queued) |
| `11:GC-05`, `11:GC-07`, `11:GC-08`, `11:GC-14`, `11:GC-15` | GOAL-02: typed pursuit classes incl. commitment, obligation, reminder, intention; "I promise" never creates a commitment | ADR-0012 does not decide pursuit classes | GOAL-04 for any commitment writer | 11-b: NEEDS_SOURCE_TEXT (not queued) |
| `14:SM-39`, `14:SM-40` | META-11: projections never turn qualified estimates into certainty or old belief into current fact | Projection honesty outside the World Model; ADR-0013 EP-15 covers the World Model only | None recorded | 14-k: NEEDS_SOURCE_TEXT (not queued) |

None of these four was in the discovery candidate set. They were introduced
while drafting the manifest. The owner may add any of them in a later
review; until then they are not queue hints.

## 6. Clause-family entries

Columns: **Entry** (manifest key) · **Clauses** (source-qualified, as cited by
the ledger) · **Ledger row** · **Disposition** · **Native overlap / dependency**
· **Triage note (paraphrase-based)**. Every entry is also `NEEDS_SOURCE_TEXT`
(§2). Triage notes summarize the ledger's paraphrase; they are not clause
text.

### 6.1 Source 01 — Identity Invariant

| Entry | Clauses | Ledger row | Disposition | Native overlap / dependency | Triage note |
| --- | --- | --- | --- | --- | --- |
| 01-a | `01:Core-invariant`, `01:REP-01`, `01:PORT-02` (with `04:AH-03`, `04:AH-04`, `16:COMP-04`) | ID-01 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0001; ADR-0008 | Identity not owned by model, runtime, prompt, DB or device |
| 01-b | `01:ID-01`, `01:ID-03`…`01:ID-05`, `01:AUTH-01` | ID-02 | DEFER_DEPENDENCY | Identity charter (owner decision 2; N-34) | Opaque identity ID |
| 01-c | `01:ID-02`, `01:CLAIM-01`, `01:CLAIM-02`, `01:L0`…`01:L6` (with `16:COMP-16`) | ID-03 | DEFER_DEPENDENCY | Identity charter | Continuity claim vector |
| 01-d | `01:ENV-01`…`01:ENV-03`, `01:CAN-01`…`01:CAN-07` (with `16:COMP-31`) | ID-04 | DEFER_DEPENDENCY | Identity charter | Identity envelope; canonical digest profile |
| 01-e | `01:VAL-01`…`01:VAL-03` | ID-05 | DEFER_DEPENDENCY | Identity charter | Identity verifier |
| 01-f | `01:AUTH-01`…`01:AUTH-03`, `01:§07-matrix` | ID-06, AUTH-01, AUTH-06 | DEFER_DEPENDENCY | Identity charter; substrate-drift policy; B-5 WITHHELD | Identity and authority never validate each other |
| 01-g | `01:FORK-01`…`01:FORK-04`, `01:MERGE-01`…`01:MERGE-03` (with `16:COMP-33`, `16:COMP-34`) | ID-07 | DEFER_DEPENDENCY | ADR-0002 (no naive LWW); C-07; RQ-003 | One acceptance order; no auto-merge |
| 01-h | `01:NEG-01`, `01:NEG-02` (with `03:CB-S20`, `03:CB-S23`) | ID-08 | DEFER_DEPENDENCY | ADR-0001; ADR-0008; identity verifier | Insufficient identity cues |
| 01-i | `01:EV-01`…`01:EV-04`, `01:AFF-01` | ID-09 | DEFER_DEPENDENCY | ADR-0006 (memory); ADR-0008; personality-domain design | Change is not identity loss |

### 6.2 Source 02 — First Memory

| Entry | Clauses | Ledger row | Disposition | Native overlap / dependency | Triage note |
| --- | --- | --- | --- | --- | --- |
| 02-a | `02:FM-GOV-01`…`02:FM-GOV-03` | FM-01 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0006; contract index | Non-authorization; L18 proposes, L04 applies |
| 02-b | `02:FM-SEM-01`…`02:FM-SEM-04`, `02:FM-SCH-05`, `02:Gate-A` | FM-02 | DEFER_DEPENDENCY | 15B2b-C; owner decisions 3/4/6/7 | Semantic readiness |
| 02-c | `02:Gate-C`, `02:FM-BIND-04`, `02:FM-GOV-02` | FM-03 | DEFER_DEPENDENCY | First Memory NOT AUTHORIZED; B-5 WITHHELD | Authority prerequisites |
| 02-d | `02:FM-TIME-04`, `02:Gate-C`, `02:T06` | FM-04 | DEFER_DEPENDENCY | FRESHNESS UNKNOWN; substrate-drift policy | Freshness prerequisites |
| 02-e | `02:Gate-D`, `02:FM-SCH-04` | FM-05 | DEFER_DEPENDENCY | A1–A7 design; 15B2b-C | Owner acceptance of candidate |
| 02-f | `02:Gate-E`, `02:FM-GATE-02`, `02:FM-GATE-03`, `02:T12`, `02:T14` | FM-06 | DEFER_DEPENDENCY | First Memory NOT AUTHORIZED | Separate operational authorization |
| 02-g | `02:FM-SEM-02`, `02:FM-BIND-01`…`02:FM-BIND-03`, `02:FM-HEAD-02` | FM-07 | DEFER_DEPENDENCY | Identity charter | Binds to accepted identity |
| 02-h | `02:FM-TAX-01`…`02:FM-TAX-03`, `02:FM-EPI-01`, `02:FM-EPI-02` | FM-08 | DEFER_DEPENDENCY | 15B2b-C class profile | Independent dimensions |
| 02-i | `02:FM-TAX-02`, `02:FM-READ-01`, `02:T07` | FM-09 | DEFER_DEPENDENCY | 15B2b-C; principle P-07 governs the UI debt now | Projections preserve UNKNOWN |
| 02-j | `02:FM-SCH-01`…`02:FM-SCH-05` | FM-10 | DEFER_DEPENDENCY | ADR-0006; 15B2b-C | First Memory record schema |
| 02-k | `02:FM-TIME-01`…`02:FM-TIME-03`, `02:FM-HEAD-01`…`02:FM-HEAD-05` | FM-11 | DEFER_DEPENDENCY | 15B2b-C | Times, firstness, atomic head |
| 02-l | `02:FM-CONS-01`…`04`, `02:FM-READ-01`…`05`, `02:FM-COR-01`…`05`, `02:FM-PRIV-01`…`05`, `02:FM-NEG`, `02:FM-BENCH`, `02:FM-TRACE` | FM-12 | DEFER_DEPENDENCY | Owner decision 6; ADR-0006 (RESTORE) | Reads, correction, privacy, test suite |

### 6.3 Source 03 — Continuity Benchmark

| Entry | Clauses | Ledger row | Disposition | Native overlap / dependency | Triage note |
| --- | --- | --- | --- | --- | --- |
| 03-a | `03:CB-01`, `03:CB-02`, `03:CB-22` | EVAL-01 | REJECT_REDUNDANT | Contract index; repository acceptance-dimension practice | Non-authorization and dimension separation already stated |
| 03-b | `03:CB-03`…`03:CB-05`, `03:CB-14`, `03:CB-15` | EVAL-02 | NEEDS_SOURCE_TEXT (Q-03) | Research charter §15 | Claim vector, preregistration, arms |
| 03-c | `03:CB-07`…`03:CB-09` | EVAL-03 | NEEDS_SOURCE_TEXT (Q-03) | ADR-0001 Validation; ADR-0011; RQ-045 | Handoff cells, runtime portability |
| 03-d | `03:CB-06`, `03:CB-10`…`03:CB-13` | EVAL-04 | NEEDS_SOURCE_TEXT (Q-03) | `testing-strategy.md`; RQ-044 | Scenarios, oracle, metrics |
| 03-e | `03:CB-16` | EVAL-05 | NEEDS_SOURCE_TEXT (Q-03) | ADR-0003 (principle) | Blinded human scoring |
| 03-f | `03:CB-17`, `03:CB-19`…`03:CB-21` | EVAL-06 | NEEDS_SOURCE_TEXT (Q-03) | Repository STOP-record practice | Hard failures not averaged |
| 03-g | `03:CB-18`, `03:CB-23`, `03:CB-24` | EVAL-07 | NEEDS_SOURCE_TEXT (Q-03) | RQ namespace records | Longitudinal; namespaces |
| 03-h | `03:CB-S20`, `03:CB-S23` | ID-08 | DEFER_DEPENDENCY | Identity verifier | Scenario IDs used as identity regression cues |

### 6.4 Source 04 — Model / Runtime Adapter & Handoff

| Entry | Clauses | Ledger row | Disposition | Native overlap / dependency | Triage note |
| --- | --- | --- | --- | --- | --- |
| 04-a | `04:AH-05` | ADAPT-01 | DEFER_DEPENDENCY | Adapter contract (ADR-0001; ADR-0011 follow-up) | Model adapter |
| 04-b | `04:AH-06` | ADAPT-02 | DEFER_DEPENDENCY | Adapter contract | Runtime adapter lifecycle; continuity check: deployment ≠ activation; runtime ≠ semantic owner |
| 04-c | `04:AH-07`…`04:AH-10`, `04:AH-21`, `04:AH-22` (with `16:COMP-37`) | ADAPT-03 | DEFER_DEPENDENCY | Privacy / model-route policy; adapter contract | Projection manifest, minimum context |
| 04-d | `04:AH-11` (with `16:COMP-07`, `16:COMP-08`) | ADAPT-04 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0006; ADR-0007; ADR-0011 | Outputs are proposals; runtime-agent gap is implementation debt |
| 04-e | `04:AH-12` (with `16:COMP-36`) | ADAPT-05, ACT-03 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0009; ADR-0004; runtime path: R5, G2, R1 | Enforcement boundary placement |
| 04-f | `04:AH-17`…`04:AH-20`, `04:AH-23` (with `16:COMP-32`) | ADAPT-06 | CONFLICT_RISK_REVIEW_REQUIRED | ADR-0011 controls (CX-3…CX-7); ADR-0011 declined to adopt the handoff state machine | Risk only: a state machine treating every engine change as a handoff would differ from CX-3 |
| 04-g | `04:AH-13`…`04:AH-16`, `04:AH-24` | ADAPT-07 | DEFER_DEPENDENCY | ADR-0011 CX-5, CX-8; adapter / coordination contract | Pending work; writer fence |
| 04-h | `04:AH-25`, `04:AH-26` | ADAPT-08 | DEFER_DEPENDENCY | Adapter contract; privacy policy | Versioned contracts; evidence packet |
| 04-i | `04:AH-27`…`04:AH-30`, `04:G0`…`04:G4` | ADAPT-09 | DEFER_DEPENDENCY | Adapter contract first | Paired fixtures; gates |

### 6.5 Source 05 — Memory Lifecycle

| Entry | Clauses | Ledger row | Disposition | Native overlap / dependency | Triage note |
| --- | --- | --- | --- | --- | --- |
| 05-a | `05:ML-01`, `05:ML-02` | MEM-01 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0006 | Non-authorization; precedence |
| 05-b | `05:ML-03` | MEM-02 | NEEDS_SOURCE_TEXT | ADR-0006 (storage ≠ acceptance); active / retrieval parts additive | Distinct memory notions |
| 05-c | `05:ML-04` | MEM-03 | DEFER_DEPENDENCY | Owner decision 3 (class profiles) | Memory kind |
| 05-d | `05:ML-05`…`05:ML-08` | MEM-04 | DEFER_DEPENDENCY | Identity charter (identity / branch binding) | Record binding; `05:ML-07` also in Q-05 |
| 05-e | `05:ML-07`, `05:ML-19`, `05:ML-20` | MEM-05 | NEEDS_SOURCE_TEXT (Q-05) | No native record | Archive ≠ active memory |
| 05-f | `05:ML-09`, `05:ML-10` | MEM-06 | DEFER_DEPENDENCY | ADR-0006; owner decisions 6/7 | Admission gate |
| 05-g | `05:ML-11`, `05:ML-12` | MEM-07 | DEFER_DEPENDENCY | Canonical consolidation deferred (15A) | Consolidation |
| 05-h | `05:ML-13`, `05:ML-14` | MEM-08 | DEFER_DEPENDENCY | Owner decision 6 | Governed retrieval |
| 05-i | `05:ML-15`, `05:ML-16` | MEM-09 | NEEDS_SOURCE_TEXT (Q-05) | No native record | Reappraisal as linked interpretation |
| 05-j | `05:ML-17`, `05:ML-18` | MEM-10 | DEFER_DEPENDENCY | C-08 (memory scope, unresolved) | Disagreement ≠ deletion |
| 05-k | `05:ML-21`…`05:ML-25` (with `16:COMP-18`) | MEM-11 | NEEDS_SOURCE_TEXT | ADR-0006 (privacy precedence); C-10 tension with tested code | Retention; erasure receipts |
| 05-l | `05:ML-26`, `05:ML-27` | MEM-12 | NEEDS_SOURCE_TEXT | ADR-0006 (backup cannot outrank suppression) | Restored state quarantined |
| 05-m | `05:ML-28`…`05:ML-32` | MEM-13 | DEFER_DEPENDENCY | Adapter / projection contract; privacy / model-route policy; personality and relationship domains | Memory projection |
| 05-n | `05:ML-33`…`05:ML-40` | MEM-14 | DEFER_DEPENDENCY | ADR-0006; A1–A7 crash design | Acceptance order; receipts |

### 6.6 Source 06 — Personality Evolution

| Entry | Clauses | Ledger row | Disposition | Native overlap / dependency | Triage note |
| --- | --- | --- | --- | --- | --- |
| 06-a | `06:PE-03`, `06:PE-04` | PER-01 | DEFER_DEPENDENCY | ADR-0001; C-11; personality-domain design | Separate layers |
| 06-b | `06:PE-05`, `06:PE-06`, `06:PE-11` | PER-02 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0008 | Prose / SOUL never silently becomes personality |
| 06-c | `06:PE-07`…`06:PE-10`, `06:PE-12`…`06:PE-15` | PER-03 | DEFER_DEPENDENCY | Personality-domain design (no writer or acceptor); continuity check: proposal ≠ acceptance | Change packet; no self-acceptance |
| 06-d | `06:PE-18`, `06:PE-19` | PER-04 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0008; ADR-0011 | New model ≠ new personality; overlay lifecycle detail additive |
| 06-e | `06:PE-22`…`06:PE-25` | PER-05 | DEFER_DEPENDENCY | ADR-0008; ADR-0010 (SKILL-8); personality-domain design | Memory informs, never authorizes |
| 06-f | `06:PE-26`, `06:PE-27` | PER-06 | DEFER_DEPENDENCY | Adapter contract; privacy / model-route policy | Personality projection |
| 06-g | `06:PE-16`, `06:PE-17`, `06:PE-20`, `06:PE-21`, `06:PE-28`, `06:PE-29` | PER-07 | DEFER_DEPENDENCY | Personality-domain design | Gradual / abrupt change; restore |
| 06-h | `06:PE-30`…`06:PE-32` | PER-08 | DEFER_DEPENDENCY | Personality-domain design; R6 | Trait loops; persona-file instructions |
| 06-i | `06:PE-33`…`06:PE-40` | PER-09 | DEFER_DEPENDENCY | Personality-domain design | Sink binding; drift metrics |

### 6.7 Source 07 — Relationship Continuity (regenerated edition)

All entries: **SOURCE_INTEGRITY_BLOCKED**, the controlling blocker. Supplying
the regenerated text alone does not make any entry `REVIEW_READY`; no owner
provenance decision is made. Clause IDs are local to the regenerated edition.
The dependency column lists what would still apply after any such decision.

| Entry | Clauses | Ledger row | Disposition | Native overlap / dependency | Triage note |
| --- | --- | --- | --- | --- | --- |
| 07-a | `07:RC-03`, `07:RC-04` | REL-01 | SOURCE_INTEGRITY_BLOCKED | ADR-0001; relationship owner design | Typed relationship state |
| 07-b | `07:RC-05`…`07:RC-07`, `07:RC-30`…`07:RC-33` | REL-02 | SOURCE_INTEGRITY_BLOCKED | G1 | Familiarity grants nothing |
| 07-c | `07:RC-08`…`07:RC-10` | REL-03 | SOURCE_INTEGRITY_BLOCKED | Privacy / consent policy | Consent scoped and revocable |
| 07-d | `07:RC-17`…`07:RC-19` | REL-04 | SOURCE_INTEGRITY_BLOCKED | C-12 | No punitive decay |
| 07-e | `07:RC-20`…`07:RC-23` | REL-05 | SOURCE_INTEGRITY_BLOCKED | C-13 | No romance mode |
| 07-f | `07:RC-11`…`07:RC-16` | REL-06 | SOURCE_INTEGRITY_BLOCKED | Relationship owner design | Relational deltas |
| 07-g | `07:RC-24`…`07:RC-29`, `07:RC-34`…`07:RC-36` | REL-07 | SOURCE_INTEGRITY_BLOCKED | Adapter contract; privacy policy | Relationship projection |
| 07-h | `07:RC-37`…`07:RC-40` | REL-08 | SOURCE_INTEGRITY_BLOCKED | Relationship owner design | Metrics; gates |

### 6.8 Source 08 — Affect / Appraisal (regenerated edition)

All entries: **SOURCE_INTEGRITY_BLOCKED**, the controlling blocker. Supplying
the regenerated text alone does not make any entry `REVIEW_READY`; no owner
provenance decision is made. The affect deferral (Slice 11 decision 1) also
applies to all of them.

| Entry | Clauses | Ledger row | Disposition | Native overlap / dependency | Triage note |
| --- | --- | --- | --- | --- | --- |
| 08-a | `08:AP-01`, `08:AP-35`, `08:AP-36`, `08:AP-40` | AFF-01 | SOURCE_INTEGRITY_BLOCKED | Affect deferral | Research protocol only |
| 08-b | `08:AP-02`, `08:AP-11`, `08:AP-14` | AFF-02 | SOURCE_INTEGRITY_BLOCKED | Affect deferral; C-13 | State / interpretation / expression distinct |
| 08-c | `08:AP-03`…`08:AP-06` | AFF-03 | SOURCE_INTEGRITY_BLOCKED | Affect deferral | Appraisal state |
| 08-d | `08:AP-07`…`08:AP-10` | AFF-04 | SOURCE_INTEGRITY_BLOCKED | Affect deferral | Fast affect; mood |
| 08-e | `08:AP-12`, `08:AP-13`, `08:AP-24`…`08:AP-29` | AFF-05 | SOURCE_INTEGRITY_BLOCKED | Affect deferral | Declared influence interfaces |
| 08-f | `08:AP-18`…`08:AP-20` | AFF-06 | SOURCE_INTEGRITY_BLOCKED | Affect deferral | Decay; loop budget |
| 08-g | `08:AP-15`…`08:AP-17`, `08:AP-21`…`08:AP-23` | AFF-07 | SOURCE_INTEGRITY_BLOCKED | Affect deferral | No engineered pathology |
| 08-h | `08:AP-30`…`08:AP-34`, `08:AP-37`…`08:AP-39` | AFF-08 | SOURCE_INTEGRITY_BLOCKED | Affect deferral | Baselines; gates |

### 6.9 Source 09 — Cognitive Recovery, Migration & Multi-Device

| Entry | Clauses | Ledger row | Disposition | Native overlap / dependency | Triage note |
| --- | --- | --- | --- | --- | --- |
| 09-a | `09:CR-03`, `09:CR-04` | REC-01 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0001; ADR-0002; C-14 recorded | A device is never LILITH |
| 09-b | `09:CR-05`…`09:CR-08` | REC-02 | DEFER_DEPENDENCY | Identity charter | Continuity bundle |
| 09-c | `09:CR-09`, `09:CR-10`, `09:CR-32` | REC-03 | DEFER_DEPENDENCY | Session / presence ownership; no second device | Device enrollment |
| 09-d | `09:CR-11`, `09:CR-12` | REC-04 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0002; ADR-0004; ADR-0009 | Reader / proposer / writer rights |
| 09-e | `09:CR-13`…`09:CR-15` (with `16:COMP-33`, `16:COMP-34`) | REC-05 | DEFER_DEPENDENCY | C-07; RQ-003 | Partitions; DIVERGED |
| 09-f | `09:CR-16`, `09:CR-17` (with `16:COMP-19`) | REC-06, AUTH-01, AUTH-05 | DEFER_DEPENDENCY | C-15; substrate-drift policy | Historical validity ≠ currentness |
| 09-g | `09:CR-18` | REC-07 | DEFER_DEPENDENCY | Session / presence ownership; no second device | Stale device rejoin |
| 09-h | `09:CR-19`…`09:CR-21` | REC-08 | DEFER_DEPENDENCY | Adapter contract; ADR-0001 Validation; continuity check: deployment ≠ activation | Ordered migration |
| 09-i | `09:CR-22`, `09:CR-23`, `09:CR-38`, `09:CR-39` (with `16:COMP-35`) | REC-09, ACT-05 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0003; ADR-0011 CX-8; implementation debt R9 | Unknown effect stays unknown |
| 09-j | `09:CR-24`, `09:CR-25` | REC-10 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0006 (privacy precedence) | Suppression across replicas |
| 09-k | `09:CR-26`, `09:CR-27` | REC-11 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0006 (RESTORE); First Memory part DEFER_DEPENDENCY | Restore as new successor |
| 09-l | `09:CR-28`…`09:CR-30` | REC-12 | DEFER_DEPENDENCY | Personality-domain design; relationship owner; affect deferral | Stale personality / consent |
| 09-m | `09:CR-31`, `09:CR-33` | REC-13 | DEFER_DEPENDENCY | Session / presence ownership | Presence consumes continuity |
| 09-n | `09:CR-34`…`09:CR-37` | REC-14 | NEEDS_SOURCE_TEXT | Existing canonicalization convention (authority domain) | Encoding profile; lossless migration |
| 09-o | `09:CR-40`…`09:CR-45`, `09:CR-47` | REC-15 | DEFER_DEPENDENCY | C-16; substrate-drift policy | Verdict vector; `09:CR-46` uncited |

### 6.10 Source 10 — Hsin Semantic Integration & Session Presence

| Entry | Clauses | Ledger row | Disposition | Native overlap / dependency | Triage note |
| --- | --- | --- | --- | --- | --- |
| 10-a | `10:HS-01`, `10:HS-02`, `10:HS-48` | HSIN-01 | REJECT_REDUNDANT | Contract index | Non-authorization (separate gate records not covered) |
| 10-b | `10:HS-03`, `10:HS-04`, `10:HS-35` | HSIN-02 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0001; C-17 UI copy | Hsin never owns identity |
| 10-c | `10:HS-05`…`10:HS-08` | HSIN-03 | DEFER_DEPENDENCY | Session / presence ownership | Session manifest |
| 10-d | `10:HS-09`, `10:HS-15`, `10:HS-16`, `10:HS-36` | HSIN-04 | DEFER_DEPENDENCY | Session / presence ownership | Session lifecycle; endpoint handoff |
| 10-e | `10:HS-10`…`10:HS-12` | HSIN-05 | NEEDS_SOURCE_TEXT | Session / presence ownership may still defer | Floor ≠ authority; not queued (§5.1) |
| 10-f | `10:HS-13`, `10:HS-14` | HSIN-06 | DEFER_DEPENDENCY | Multi-embodiment deferral | Simultaneous embodiments |
| 10-g | `10:HS-17`, `10:HS-18`, `10:HS-40`…`10:HS-42` | HSIN-07 | NEEDS_SOURCE_TEXT | — | Intent / dispatch / delivery distinct; not queued (§5.1) |
| 10-h | `10:HS-19`…`10:HS-22` | HSIN-08 | DEFER_DEPENDENCY | Privacy policy; no capture path | Sensor consent |
| 10-i | `10:HS-23`…`10:HS-25`, `10:HS-38`, `10:HS-39` | HSIN-09 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0009; ADR-0004 | Effects need scoped permission |
| 10-j | `10:HS-26`…`10:HS-28` | HSIN-10 | NEEDS_SOURCE_TEXT (Q-10) | C-13 | Expression ≠ affect truth |
| 10-k | `10:HS-29`…`10:HS-33` | HSIN-11 | NEEDS_SOURCE_TEXT | ADR-0006 (memory apply) | Bounded local state |
| 10-l | `10:HS-34`, `10:HS-37` | HSIN-12 | DEFER_DEPENDENCY | Session / presence ownership; `09:CR-18` | Stale rejoin; degraded modes |
| 10-m | `10:HS-43`…`10:HS-47` | HSIN-13 | DEFER_DEPENDENCY | Session contract first | Evidence; metrics |

### 6.11 Source 11 — Goal, Commitment & Intention Continuity

| Entry | Clauses | Ledger row | Disposition | Native overlap / dependency | Triage note |
| --- | --- | --- | --- | --- | --- |
| 11-a | `11:GC-03`, `11:GC-04`, `11:GC-27`…`11:GC-31` | GOAL-01 | NEEDS_SOURCE_TEXT (Q-11) | Slice 8 record (not an ADR) | Thought / plan / goal / task / permission distinct |
| 11-b | `11:GC-05`, `11:GC-07`, `11:GC-08`, `11:GC-14`, `11:GC-15` | GOAL-02 | NEEDS_SOURCE_TEXT | GOAL-04 for any commitment writer | Typed pursuit classes; not queued (§5.1) |
| 11-c | `11:GC-06`, `11:GC-09` | GOAL-03 | DEFER_DEPENDENCY | Identity charter; expiry policy | Goal state binding |
| 11-d | `11:GC-10`, `11:GC-11`, `11:GC-13`, `11:GC-25`, `11:GC-26`, `11:GC-42` | GOAL-04 | DEFER_DEPENDENCY | GOAL-04; C-18 | Origin ≠ acceptance; named acceptor |
| 11-e | `11:GC-12`, `11:GC-37`, `11:GC-38` | GOAL-05, ACT-06 | NEEDS_SOURCE_TEXT | ADR-0003; ADR-0011 CX-8; R8 domain contract | Exact transitions; payload-bound keys |
| 11-f | `11:GC-16` | GOAL-06 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0012 (non-resumption point only, decided independently); CANCEL_REQUESTED part NEEDS_SOURCE_TEXT | Not accepted; ledger GOAL-06 stays CONFLICT |
| 11-g | `11:GC-17`…`11:GC-20` | GOAL-07 | NEEDS_SOURCE_TEXT (Q-11) | — | Priority orders only |
| 11-h | `11:GC-21`, `11:GC-22` | GOAL-08 | NEEDS_SOURCE_TEXT (Q-11) | ADR-0003; ADR-0012 creates no completion requirement | Completion needs criteria and proof |
| 11-i | `11:GC-23`, `11:GC-24` | GOAL-09 | NEEDS_SOURCE_TEXT (Q-11) | — | CANCEL_REQUESTED ≠ CANCELLED |
| 11-j | `11:GC-32`…`11:GC-34` | GOAL-10 | NEEDS_SOURCE_TEXT | ADR-0003 | Intent / effect / completion distinct |
| 11-k | `11:GC-35`, `11:GC-36`, `11:GC-39` | GOAL-11 | DEFER_DEPENDENCY | C-07; RQ-003; continuity check: historical goal truth | Migration; forks |
| 11-l | `11:GC-40`, `11:GC-41` | GOAL-12 | DEFER_DEPENDENCY | Privacy policy | Goal visibility; deletion |
| 11-m | `11:GC-43`, `11:GC-44` | GOAL-13 | DEFER_DEPENDENCY | Worker delegation deferred; capability policy | Budgets; delegated workers |
| 11-n | `11:GC-46`, `11:GC-47` | GOAL-14 | NEEDS_SOURCE_TEXT | ADR-0003 | Evidence bundles |
| 11-o | `11:GC-01`, `11:GC-02`, `11:GC-45` | GOAL-15 | REJECT_REDUNDANT | Contract index; Slice 8 record | Non-authorization |

### 6.12 Source 12 — Initiative, Interruption & Autonomous Action

| Entry | Clauses | Ledger row | Disposition | Native overlap / dependency | Triage note |
| --- | --- | --- | --- | --- | --- |
| 12-a | `12:IA-03`…`12:IA-05` | INIT-01 | DEFER_DEPENDENCY | R13 proactive-channel inventory; capability policy; C-18 | Initiative ≠ authority ≠ interruption |
| 12-b | `12:IA-06`, `12:IA-10` | INIT-02 | DEFER_DEPENDENCY | R13; initiative contract | Triggers; opportunity assessment |
| 12-c | `12:IA-07`, `12:IA-08`, `12:IA-13`…`12:IA-15`, `12:IA-18` | INIT-03 | DEFER_DEPENDENCY | R13; privacy policy | Initiative / interruption records |
| 12-d | `12:IA-16` | INIT-04 | DEFER_DEPENDENCY | R13 | Bounded reminders |
| 12-e | `12:IA-17`, `12:IA-19` | INIT-05, ACT-03, ACT-04 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE (boundary placement); DEFER_DEPENDENCY (check dimensions) | ADR-0009; ADR-0004; G1, G2, R1; capability policy | Point-of-dispatch checks |
| 12-f | `12:IA-20`…`12:IA-22` | INIT-06 | DEFER_DEPENDENCY | Relationship, affect and personality domains; privacy policy | No contact rights from relationship |
| 12-g | `12:IA-23`…`12:IA-25` | INIT-07 | DEFER_DEPENDENCY | R13; capability policy | Budgets; stop / mute / revoke |
| 12-h | `12:IA-09`, `12:IA-28`, `12:IA-29`, `12:IA-38` | INIT-08 | DEFER_DEPENDENCY | Capability policy; ADR-0009 revisit trigger (bounded autonomous approval); continuity check: semantic ownership ≠ action permission | Work leases |
| 12-i | `12:IA-11`, `12:IA-12`, `12:IA-37` | INIT-09 | DEFER_DEPENDENCY | R13 | Background cognition |
| 12-j | `12:IA-27`, `12:IA-30`, `12:IA-32`, `12:IA-39` | INIT-10 | NEEDS_SOURCE_TEXT | ADR-0003; ADR-0011 CX-8 | Restart never blindly resumes |
| 12-k | `12:IA-26`, `12:IA-33`…`12:IA-35` | INIT-11 | DEFER_DEPENDENCY | RQ-025, RQ-030…RQ-032 deferral | Human escalation |
| 12-l | `12:IA-31`, `12:IA-36`, `12:IA-40`…`12:IA-43`, `12:IA-46`…`12:IA-48` | INIT-12 | DEFER_DEPENDENCY | Initiative contract; principle P-08 | Evidence chain; benchmark |

### 6.13 Source 13 — Learning, Skill Acquisition & Competence

| Entry | Clauses | Ledger row | Disposition | Native overlap / dependency | Triage note |
| --- | --- | --- | --- | --- | --- |
| 13-a | `13:LS-01`, `13:LS-02`, `13:LS-47`, `13:LS-48` | LEARN-01 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0006; ADR-0010 | Non-authorization; L18 / L04 |
| 13-b | `13:LS-03`, `13:LS-05`, `13:LS-20` | LEARN-02 | DEFER_DEPENDENCY | C-20 (not resolved here) | Exposure ≠ learning |
| 13-c | `13:LS-04`, `13:LS-06`, `13:LS-29` | LEARN-03 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0010; prompt / weight / tool change classes undecided | No ungoverned skill store |
| 13-d | `13:LS-07`…`13:LS-10` | LEARN-04 | DEFER_DEPENDENCY | Procedural Skill domain design (ADR-0010 follow-up) | Typed skill records |
| 13-e | `13:LS-11`, `13:LS-12`, `13:LS-16`…`13:LS-18` | LEARN-05 | DEFER_DEPENDENCY | C-20 (`13:LS-16`); ADR-0003 | Independent assessor |
| 13-f | `13:LS-13`, `13:LS-14`, `13:LS-22`, `13:LS-31`, `13:LS-32` | LEARN-06 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0010 (SKILL-9, SKILL-14); continuity check: skill acceptance ≠ tool permission | No autonomous learning by default |
| 13-g | `13:LS-15`, `13:LS-40` | LEARN-07 | NEEDS_SOURCE_TEXT | ADR-0003 | Exact transitions; UNKNOWN_EFFECT |
| 13-h | `13:LS-19`, `13:LS-33`, `13:LS-34` | LEARN-08 | DEFER_DEPENDENCY | Privacy policy; Procedural Skill domain design | Erasure propagation |
| 13-i | `13:LS-21`, `13:LS-23`, `13:LS-24` | LEARN-09 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE (`13:LS-21`); DEFER_DEPENDENCY (`13:LS-23` affect deferral, `13:LS-24` consent ownership) | ADR-0010 (SKILL-8) | Learning does not rewrite personality |
| 13-j | `13:LS-25`, `13:LS-26` | LEARN-10 | DEFER_DEPENDENCY | G1; capability policy; ADR-0009 | Tool knowledge grants no access |
| 13-k | `13:LS-27`, `13:LS-28`, `13:LS-37`…`13:LS-39` | LEARN-11 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0010 (SKILL-3, SKILL-10, SKILL-11); ADR-0011 | Provider update ≠ LILITH learning |
| 13-l | `13:LS-41`…`13:LS-46` | LEARN-12 | NEEDS_SOURCE_TEXT | RQ-037, RQ-044 | Evidence vocabulary; gates |

### 6.14 Source 14 — Self-Model, Metacognition & Capability Awareness

| Entry | Clauses | Ledger row | Disposition | Native overlap / dependency | Triage note |
| --- | --- | --- | --- | --- | --- |
| 14-a | `14:SM-03`, `14:SM-04`, `14:SM-11`, `14:SM-12` | META-01 | NEEDS_SOURCE_TEXT (Q-14) | G1 for frontend registry | Capability awareness ≠ grant |
| 14-b | `14:SM-05`…`14:SM-08` | META-02 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0001; ADR-0008 | Prose self-description is a projection |
| 14-c | `14:SM-09`, `14:SM-10`, `14:SM-21`, `14:SM-22` | META-03 | DEFER_DEPENDENCY | Self-model owner (ADR-0007; none designated) | Self-model state |
| 14-d | `14:SM-13`, `14:SM-14`, `14:SM-19`, `14:SM-20` | META-04 | NEEDS_SOURCE_TEXT | RQ-023, RQ-037 | Attributed metacognition; calibration |
| 14-e | `14:SM-15`, `14:SM-16`, `14:SM-28`, `14:SM-33`, `14:SM-34` | META-05 | NEEDS_SOURCE_TEXT | ADR-0010 (SKILL-10/11); ADR-0011 | Observation before interpretation |
| 14-f | `14:SM-17`, `14:SM-18`, `14:SM-32` | META-06 | NEEDS_SOURCE_TEXT (Q-14) | — | Known-unknown states |
| 14-g | `14:SM-23`, `14:SM-24` | META-07 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE (World Model scope); DEFER_DEPENDENCY (self-model scope) | ADR-0013 (EP-1, EP-8, EP-10); self-model owner | Retain unresolved tension |
| 14-h | `14:SM-25`, `14:SM-26`, `14:SM-31` | META-08 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0007; ADR-0009 | Metacognition cannot escalate authority |
| 14-i | `14:SM-27`, `14:SM-29`, `14:SM-30` | META-09 | DEFER_DEPENDENCY | ADR-0008; self-model owner; R14 | Self-belief never updates personality |
| 14-j | `14:SM-35`…`14:SM-38` | META-10 | DEFER_DEPENDENCY | C-07; self-model owner | Migration; branches |
| 14-k | `14:SM-39`, `14:SM-40` | META-11 | NEEDS_SOURCE_TEXT | Principle P-07; ADR-0013 EP-15 (World Model only) | Projection honesty; not queued (§5.1) |
| 14-l | `14:SM-41`…`14:SM-48` | META-12 | NEEDS_SOURCE_TEXT | RQ-037, RQ-044 | Evidence packets; gates |

### 6.15 Source 15 — Epistemic Integrity, Belief State & Uncertainty

| Entry | Clauses | Ledger row | Disposition | Native overlap / dependency | Triage note |
| --- | --- | --- | --- | --- | --- |
| 15-a | `15:E-03`, `15:E-04`, `15:E-29` | EPI-01 | NEEDS_SOURCE_TEXT (Q-15) | Principle P-07 (not an ADR) | Observation ≠ fact |
| 15-b | `15:E-05`, `15:E-38` | EPI-02 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0007; ADR-0009; ADR-0013 (EP-12, EP-16) | No belief mints authority |
| 15-c | `15:E-06`…`15:E-08` | EPI-03 | DEFER_DEPENDENCY | Confidence policy (ADR-0013 follow-up); source-trust policy | Typed statuses; no hidden scalar |
| 15-d | `15:E-09`, `15:E-15` | EPI-04 | DEFER_DEPENDENCY | Source-trust policy | Source class not coerced |
| 15-e | `15:E-10`, `15:E-11` | EPI-05 | NEEDS_SOURCE_TEXT (Q-15) | — | Abstention permitted |
| 15-f | `15:E-13`, `15:E-14`, `15:E-17`, `15:E-18` (with `16:COMP-21`) | EPI-06 | DEFER_DEPENDENCY | C-22; source-trust policy | No circular corroboration |
| 15-g | `15:E-25`, `15:E-26` (with `16:COMP-20`) | EPI-07 | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0013 (decided independently) | Not accepted; ledger EPI-07 stays CONFLICT |
| 15-h | `15:E-19`, `15:E-20` | EPI-08 | DEFER_DEPENDENCY | EPI-08 (TTL / absent clock) | Separate times; missing expiry ≠ current |
| 15-i | `15:E-21` | EPI-09 | NEEDS_SOURCE_TEXT (Q-15) | — | Absence of evidence ≠ evidence of absence |
| 15-j | `15:E-22`…`15:E-24` | EPI-10 | NEEDS_SOURCE_TEXT (Q-15) | — | Uncertainty components; causal claims |
| 15-k | `15:E-27`, `15:E-28`, `15:E-39` | EPI-11 | DEFER_DEPENDENCY | EPI-11; continuity check: projection ≠ canonical state | Proposal → accept → apply |
| 15-l | `15:E-35`…`15:E-37` | EPI-12 | NEEDS_SOURCE_TEXT (Q-15) | ADR-0003 | Tool success never proves a proposition |
| 15-m | `15:E-40`…`15:E-42`, `15:E-45` (with `16:COMP-17`, `16:COMP-37`) | EPI-13 | NEEDS_SOURCE_TEXT | Repository invariants; ledger §8 / R3 | Fixtures labelled; projections carry limits |

### 6.16 Source 16 — Integrated Cognitive Architecture & Composition Contract

| Entry | Clauses | Ledger row | Disposition | Native overlap / dependency | Triage note |
| --- | --- | --- | --- | --- | --- |
| 16-a | `16:COMP-06`, `16:COMP-07`, `16:COMP-09` | COMP-A | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0007 (decided independently) | Owner-domain principle |
| 16-b | `16:COMP-08` | COMP-B | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0007; ADR-0006 | No circular authority |
| 16-c | `16:COMP-14` | COMP-C | NEEDS_SOURCE_TEXT | Repository acceptance-dimension practice | Acceptance dimensions separate |
| 16-d | `16:COMP-15`, `16:COMP-16` | COMP-D | NEEDS_SOURCE_TEXT | `docs/README.md` labels | Evidence categories |
| 16-e | `16:COMP-17`, `16:COMP-37` | COMP-E | NEEDS_SOURCE_TEXT | Principle P-07 | Typed absence survives |
| 16-f | `16:COMP-18` | COMP-F | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0006 (privacy precedence) | Privacy outranks completeness |
| 16-g | `16:COMP-19` | COMP-G | DEFER_DEPENDENCY | EPI-08; substrate-drift policy | Separate clocks |
| 16-h | `16:COMP-36` | COMP-H | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0009; ADR-0004 | Content never becomes policy |
| 16-i | `16:COMP-31`, `16:COMP-32` | COMP-I | DEFER_DEPENDENCY | Adapter / handoff contract; identity charter | Integrated manifest; fencing |
| 16-j | `16:COMP-35` | COMP-J | ALREADY_COVERED_BY_NATIVE_ARCHITECTURE | ADR-0003; ADR-0011 CX-8; implementation debt | Unknown forbids blind replay |
| 16-k | `16:COMP-40`, `16:COMP-41` | COMP-K | NEEDS_SOURCE_TEXT | Repository STOP-record practice | Hard failures block promotion |
| 16-l | `16:COMP-45`, `16:COMP-47`, `16:COMP-48` | COMP-L | NEEDS_SOURCE_TEXT | ADR-0014 governs source review; COMP-48 entry criteria not claimed met | Ledger reconstruction; slice entry criteria |
| 16-m | `16:COMP-23` (personality), `16:COMP-24` (relationship), `16:COMP-25` (goals / initiative / action), `16:COMP-26` (learning), `16:COMP-27` (Hsin), `16:COMP-28` (adapter / recovery), `16:COMP-29` (First Memory) | Section headers 6.4–6.13 | Follow the entries of the matching source above | ADR-0007 decides the general principle; per-domain owners per ADR-0008 / ADR-0010 or undecided | Cited only as domain-assignment references |

### 6.17 Citations in existing-enforcement rows (OUT_OF_SCOPE)

The ledger's AUTH and ACT rows are controlled by existing repository records,
not by the proposed sources (ledger §2.1, §6.16). Their source citations are
`OUT_OF_SCOPE` for source review as AUTH / ACT rows. Where the same clause
also has an entry above, that entry governs its triage.

| Clauses cited | Ledger rows | Disposition | Note |
| --- | --- | --- | --- |
| `16:COMP-30`, `16:§20`, `16:COMP-03`, `16:COMP-44` | AUTH-01 … AUTH-07 | OUT_OF_SCOPE | Authority / currentness records control. B-5 WITHHELD; FRESHNESS UNKNOWN; M-B1 NOT AUTHORIZED |
| `01:AUTH-01`…`01:AUTH-03`, `09:CR-16` | AUTH-01, AUTH-05, AUTH-06 | OUT_OF_SCOPE (as AUTH rows); see 01-f, 09-f | — |
| `04:AH-12`, `12:IA-17`, `11:GC-12`, `16:COMP-35`, `16:COMP-36`, `09:CR-22`, `09:CR-23` | ACT-01 … ACT-06 | OUT_OF_SCOPE (as ACT rows); see 04-e, 12-e, 11-e, 16-j, 16-h, 09-i | G1, G2 OPEN; ADR-0004, ADR-0009 control |

## 7. Independence of accepted ADRs

ADR-0007 through ADR-0013 were decided without accepting any proposed source.
Entries above that cite them as native overlap record topic overlap only.
They do not make `11:GC-16`, `15:E-25`, `15:E-26`, any `04:AH-*`, `13:LS-*`,
`06:PE-*` or `16:COMP-*` clause, or any other clause, accepted. Each accepted
ADR remains the sole controlling source for its decision.

## 8. Dependency register (not resolved by D-9)

C-20 · GOAL-04 · EPI-11 · C-22 · EPI-08 · G1 · G2 · R1 · C-07 · C-15 ·
substrate-drift policy · identity charter (15B2b-B owner decision 2) · First
Memory authorization · affect deferral · capability policy · privacy /
model-route policy · source-trust policy · session / presence ownership. Also
cited above and also unchanged: C-08, C-10, C-11, C-12, C-13, C-16, C-18,
R13, R14, RQ-003, 15B2b-C and owner decisions 3/4/6/7.

## 9. Integrity status

| Check | Status |
| --- | --- |
| Clause text in repository | NONE (all 16) |
| Public-safe derivatives | NONE; none authorized by this manifest |
| Source digests | Recorded (§4); not re-verified in this pass; the private archive was not accessed |
| Authorship | UNKNOWN / not recorded (all 16) |
| Document 16 register cross-check | Partial record only (see source 16 note) |
| Regenerated editions | Sources 07, 08: SOURCE_INTEGRITY_BLOCKED pending an explicit owner provenance decision (not made) |
| Private conversation identifier | Not reproduced |

## 10. Operational effect

None. This manifest accepts no source or clause, changes no ledger coverage
classification or total, changes D-10 in no way, and touches no code, schema,
runtime, deployment, authority, freshness or live state.
