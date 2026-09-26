# Research Question Numbering Reconciliation

Status: **RECONCILIATION RECORD — OWNER DECISION REQUIRED.** No RQ is
renumbered, reworded, added, or removed by this record. No RQ-122 or later is
assigned.

> **Correction — primary-source pass (2026-09-26).** This record was first
> written without the Master documents. Both Master editions are now archived
> ([source manifest](source-material/source-manifest.md)) and the full
> 121 × 50 comparison is in the [REPO ↔ MASTER crosswalk](rq-register-crosswalk.md).
> Verified results: MASTER:RQ-001–121 exist exactly as the brief said; RQ-122+
> exists nowhere; all five example mismatches in section B are confirmed; the
> conclusion in section B is refined (the registers likely share an ancestor).
> Namespaces are now written `REPO:RQ-NNN` and `MASTER:RQ-NNN` (section C).
> First-pass wording is kept below, with corrected cells marked
> *(corrected)*.

## A. Highest RQ number actually discovered

| Question | Answer | Evidence |
| --- | --- | --- |
| Highest RQ defined in the repository | **RQ-050** | [research-question-register.md](research-question-register.md), created in `1eee09b` (2026-09-13) and never modified since |
| RQ-051 or later anywhere in the repository | **None** | `git grep` for `RQ-[0-9]{3}` over `origin/main`; see the [source-material README](source-material/README.md) |
| RQ-051 or later in the local workspace | *(corrected)* **MASTER:RQ-051–121**, in the archived Master v1.0 and v1.1 PDFs; the first-pass search missed them (truncated output) | [Crosswalk](rq-register-crosswalk.md#namespaces) |
| RQ-101–RQ-121 | *(corrected)* **VERIFIED** — present in both Master editions: RQ-101–120 as research proposals, RQ-121 as the accepted affective-continuity addition | Archived Master v1.1 §Q |
| RQ-122 or later | **None found anywhere**; none assigned | — |
| Questions existing only in notes or conversations | Seven candidate topics in the brief (affect, relational continuity, substrate continuity, etc.); none canonically registered. See [rq-candidates.md](rq-candidates.md). | Brief |

Uses of RQ numbers in the repository (all in-repo numbering):
register (50 rows); ADR-0001 (RQ-001, 004, 007); ADR-0002 (RQ-004, 005, 008,
049); ADR-0003 (RQ-033–037); ADR-0004 (RQ-026, 028, 047, 048); roadmap Phase 3
(RQ-028, 033, 034, 036); `scripts/validate_repository.py` enforces unique,
sequential rows from RQ-001 in the register.

## B. Two incompatible numbering schemes

The brief quotes Master v1.1 topics by number. Comparing those quotations with
the in-repo register shows that **the same number means different questions**:

| Number | Master v1.1 topic (as quoted in the brief) | In-repo register topic | Same question? |
| --- | --- | --- | --- |
| RQ-001 | Identity continuity *(verified: "What fundamentally makes LILITH 'LILITH'?")* | What makes LILITH the same LILITH after components are replaced? | **SEMANTIC MATCH** *(corrected)* |
| RQ-003 | What deserves to become memory? | Can an old state be restored without creating a competing identity? | **No** — memory admission is in-repo RQ-009 |
| RQ-005 | Forgetting | Leader, leases, or capability-level ownership for multi-runtime execution? | **No** — forgetting is in-repo RQ-011 |
| RQ-007 | Belief / provenance | How are model and runtime behavioural differences normalized? | **No** — provenance is in-repo RQ-013 |
| RQ-009 | Inference becoming false memory | What deserves to become durable memory? | **No** — inference/false memory is in-repo RQ-015 |
| RQ-036 | Memory poisoning (if applicable) | How much evidence is sufficient? | **No** — poisoning has no in-repo RQ; threat model T-08 covers it |
| RQ-051–RQ-100 | Includes RQ-097 replaceable components and RQ-100 "big research question" | Not defined | n/a |
| RQ-101–RQ-121 | Frontier extensions incl. RQ-104 identity versioning, RQ-105 relationship as first-class entity, RQ-108 permission gradient, RQ-114 explanation contract, RQ-115 forgetfulness contract, RQ-117 memory immune system, RQ-118 preference/policy separation, RQ-119 narrative identity, RQ-120 living research register, RQ-121 affective continuity | Not defined | n/a |

**Conclusion.** These are two separate registers, not one register with a gap.
The in-repo register is an independent 50-question portfolio created with the
repository foundation; the Master is an out-of-repo 121-question portfolio. The
order in which they were written, whether one derived from the other, and
whether any question was dropped, renumbered, or reworded between them
**cannot be determined** without the Master originals.

*(Corrected.)* With the Masters archived: the REPO register (2026-09-13)
predates Master v1.0 (2026-09-14); the Master preserves an older original
Problem Register (still missing); and REPO:RQ-001–050 track MASTER:RQ-001–050
topics in largely the same order. A shared ancestor is therefore likely
(INFERRED), but the Problem Register itself is needed to confirm it. See the
[crosswalk findings](rq-register-crosswalk.md#findings-about-the-two-registers).

Duplicate numbers **within** the in-repo register: none (validator-enforced).
Conflicting wording within the in-repo register: none found. Duplicates or
conflicts within the Master: unknown (source unavailable). *(Corrected: none — 121 unique numbers; titles identical in v1.0 and v1.1.)*

## C. Interim citation convention (used by this branch only)

To avoid silent collisions until the owner decides:

- `RQ-NNN` — the **in-repo register** number (the only numbering ADRs cite).
- `Master RQ-NNN` — a number quoted from Master v1.1 via the brief; wording
  unverified.

*(Corrected.)* From the primary-source pass onward, use explicit prefixes:
`REPO:RQ-NNN` and `MASTER:RQ-NNN`. "Master RQ-NNN" in first-pass text means
`MASTER:RQ-NNN`, now verified.

## D. Crosswalk: Master topics named in the brief → in-repo questions

*(Superseded by the full [crosswalk](rq-register-crosswalk.md), which classifies every pair.)*

This crosswalk is topical, not an equivalence claim. Evidence for each in-repo
RQ is in the [RQ evidence map](rq-evidence-map.md).

| Master topic (brief) | Closest in-repo RQ(s) | Coverage |
| --- | --- | --- |
| Master RQ-001 identity continuity | RQ-001, RQ-002, RQ-003 | Covered |
| Master RQ-003 memory admission | RQ-009 | Covered |
| Master RQ-005 forgetting | RQ-011, RQ-016 | Covered |
| Master RQ-007 belief / provenance | RQ-013, RQ-038 | Covered |
| Master RQ-009 inference → false memory | RQ-015 | Covered |
| Master RQ-036 memory poisoning | none (threat T-08; RQ-015, RQ-047 adjacent) | **Gap in repo register** |
| Master RQ-097 replaceable components | RQ-001, RQ-007, RQ-045 | Partial |
| Master RQ-100 big research question | none | *(corrected)* Wording now verified: "How can a persistent personal AI become increasingly capable and autonomous over years while preserving identity continuity, truthfulness, user authority, privacy, safety, explainability, and trust?" — overarching; RELATED to every REPO RQ |
| Master RQ-104 identity versioning | RQ-002 | Partial |
| Master RQ-105 relationship as first-class entity | none (RQ-043 adjacent) | **Gap** |
| Master RQ-108 permission gradient | RQ-026, RQ-027, RQ-031, RQ-032 | Partial |
| Master RQ-114 explanation contract | RQ-013, RQ-038 | Partial |
| Master RQ-115 forgetfulness contract | RQ-011, RQ-016 | Partial |
| Master RQ-117 memory immune system | RQ-015 (+ T-08) | Partial |
| Master RQ-118 preference / policy separation | RQ-027, RQ-042 | Partial |
| Master RQ-119 narrative identity | none | **Gap** |
| Master RQ-120 living research register | none (this reconciliation is itself evidence) | **Gap** |
| Master RQ-121 affective continuity | none | **Gap** |

## E. Evidence deltas for the Master topics named in the brief

Conservative assessment from recent work (15B2b-B1c, 15B2b-B design,
15B2b-B2a) and earlier slices. "Gained evidence" never means answered.

| Master topic | Gained evidence? | What the evidence is | What it is **not** |
| --- | --- | --- | --- |
| RQ-001 identity continuity | Design only | 15B2b-B binds owner authority to logical context (`logicalOwnerId`, environment, authority domain, ledger epoch), never to host/VM, so continuity survives runtime replacement; B2a implements that challenge field set (TEST) | Not a LILITH identity invariant; no charter exists (N-34) |
| RQ-003 memory admission | Yes (mechanics) | Owner-directed, consent/policy/actor-gated admission; B2a acceptance verifier; 15A shadow candidates | No real admission; no selection criteria tested |
| RQ-005 forgetting | Yes (mechanics) | 15B2a FORGET = hold → erasure (TEST); suppression replay precedes restore; crypto-erasure PROPOSED | No decay policy; backups not covered |
| RQ-007 belief / provenance | Yes | World Model evidence/trace live pre-DEV; L04 provenance; B2a chain verifier | Not an explanation interface |
| RQ-009 inference → false memory | Yes | Epistemic basis never promoted (15B2b-A DEV, B2a `truthClaim=false`) | No adversarial promotion corpus |
| RQ-036 memory poisoning | Indirect | Only owner-proof-bound writes can be accepted (B2a TEST); app can still mint evidence today (N-35) | Not a poisoning study |
| RQ-097 replaceable components | Indirect | Tool-less reasoning component (Slice 9); B1c deployment ≠ activation | No model-swap evaluation |
| RQ-100 | Indirect *(corrected: wording verified)* | Every slice contributes a narrow part | Not answerable as one question |
| RQ-104 identity versioning | No | Charter binding explicitly deferred (15B2b-B). *(Added: Master v1.0/v1.1 §03 already DESIGNED identity versioning, 2026-09-14.)* | — |
| RQ-105 relationship entity | No (negative) | Slice 14 deliberately forbids relationship state. *(Added: Master §08 DESIGNED "relationship as a first-class entity", 2026-09-14; Slice 14's prohibition is a deliberate V1 scope limit, not a rejection.)* | — |
| RQ-108 permission gradient | Yes | Slice 5 classes; activation vs per-action owner proof as separate mechanisms (15B2b-B); B1c authority tiers | No contextual risk |
| RQ-114 explanation contract | Partial | B2a returns ordered reasons; provenance explanation test in 15B1 | No user-facing explanation contract |
| RQ-115 forgetfulness contract | Partial | Same as RQ-005 | — |
| RQ-117 memory immune system | Partial | Acceptance verifier rejects every reachable forgery (TEST); containment gates | No detection of poisoned but authorized content |
| RQ-118 preference / policy separation | Partial | Learning has no path to policy; ethics advisory only | No preference store |
| RQ-119 narrative identity | No | *(Added: Master §03 DESIGNED narrative identity as a derived, revisable account that cannot overwrite primary evidence.)* | — |
| RQ-120 living register | This branch | Reconciliation artifacts | Not yet canonical |
| RQ-121 affective continuity | No project evidence (constraints only) | CA-V1 §10 no-suffering invariant; Slices 11 and 14 forbid affect. *(Added: Master v1.0/v1.1 §08 DESIGNED a functional affect architecture — drives → appraisal → fast affect → slow mood → expression — with an epistemic boundary and anti-manipulation / anti-suffering constraints, 2026-09-14.)* | No affect implementation exists |

## F. Owner decision required

Options (no action taken):

1. **Namespace both (recommended).** Keep the in-repo register numbers
   unchanged (ADRs depend on them). Import the Master as a separate register
   (for example `master-register-v1.1.md`) with its own prefix, plus an
   authoritative crosswalk. Requires changing `validate_repository.py` only if
   the Master is placed in the same file.
2. **Adopt the Master numbering.** Renumber the in-repo register and update
   ADR-0001–0004 and the roadmap references. Breaks existing citations; needs
   an ADR-level correction record.
3. **Adopt the in-repo numbering.** Re-home Master questions into RQ-051+.
   Loses Master citation stability.

Until decided, new candidates stay un-numbered.
