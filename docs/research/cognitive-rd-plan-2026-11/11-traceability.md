# 11. Traceability

## 1. Sources and how they are used

| Code | Source | Status | Use in this package |
| --- | --- | --- | --- |
| V1 | [Cognitive Architecture V1](../../architecture/cognitive-architecture-v1.md) | design reference | layer IDs, responsibilities, §14 meta-cognition, §16 consolidation |
| MRA | [Architecture & Research Master v1.1](../source-material/originals/LILITH_Architecture_and_Research_Master_v1.1.pdf) | canonical reference (2026-09-14) | affect loop (§08, p. 19), drives (p. 15), Master RQ-101–121 |
| I, F, B, H | Identity Invariant; First Memory; Continuity Benchmark; Model-Runtime Adapter & Handoff | PROPOSED / NOT ACCEPTED (private) | identity, autobiographical head, evaluation, model swap |
| M (ML) | Memory Lifecycle & Reappraisal | PROPOSED (private) | consolidation, reappraisal, forgetting |
| P (PE) | Personality Evolution | PROPOSED (private) | no prompt-as-person; no self-reinforcing traits |
| R (RC) | Relationship Continuity | PROPOSED, **regenerated reconstruction** (private) | preferences, boundaries, no closeness scores |
| AP | Affect / Appraisal Research Protocol | PROPOSED, **regenerated reconstruction** (private) | appraisal scope, persistence deferral, welfare limits |
| SM | Self-Model, Metacognition & Capability Awareness | PROPOSED (private) | calibration, introspection boundary, gates |
| E | Epistemic Integrity, Belief State & Uncertainty | PROPOSED (private) | memory ≠ truth; preserve disagreement |
| GC | Goal Commitment & Intention Continuity | PROPOSED (private) | commitments, completion proof, self-directed goals as research |
| IA | Initiative, Interruption & Autonomous Action | PROPOSED (private) | initiative gates, quiet hours, cooldowns |
| LS | Learning, Skill Acquisition & Competence | PROPOSED (private) | procedural recipes, no silent promotion |
| CR | Cognitive Recovery, Migration & Multi-Device Continuity | PROPOSED (private) | migration, ephemeral appraisal reset |
| HS | Hsin Semantic Integration & Session Presence | PROPOSED (private) | deferred embodiment parity |
| COMP | Integrated Cognitive Architecture & Composition Contract | PROPOSED (private) | composition-only; no super-owner; owner-domain rule |
| WN | [PROD work note](../../engineering/prod-work-note-2026-11-07.md) | live record | measured evidence, constraints |
| DS | DeepSeek independent review, 2026-11-08 (owner-provided) | external critique | reconciled in [02](02-deepseek-reconciliation.md) |

**About the private contracts.**
- They are in the owner's archive and verified against [ORIGINALS.sha256](../../architecture/cognitive-contracts/v0.1/ORIGINALS.sha256)
  (16 of 16 matched on 2026-11-08).
- This package cites requirement IDs and paraphrases them; no contract text is reproduced.
- Two contracts (RC, AP) state that they are regenerated reconstructions of unrecoverable originals. Treat them as
  design aids, not authoritative wording.

## 2. Topic → research questions → contracts

| Topic | Repo RQs | Master RQs | Contracts |
| --- | --- | --- | --- |
| 1 AS-IS maturity | RQ-044 | — | COMP-14/15 |
| 2 Gaps vs 19 layers | — | — | V1; ML-02 (writer-authority supersession) |
| 3 Social and relationship | RQ-042, RQ-043 | RQ-105 relationship as a first-class entity (gap), RQ-118 preference/policy separation | RC-05..10, RC-14/15, RC-30, RC-32; COMP-24 |
| 4 Appraisal and affect | RQ-040 (finding) | RQ-121 affective continuity (gap) | AP-02..08, AP-19..26, AP-35, AP-40; ML-32 |
| 5 Metacognition | RQ-023, RQ-037 | RQ-114 explanation contract | SM-08, SM-14, SM-19/20, SM-25, SM-39/40; V1 L16 |
| 6 Consolidation and memory | RQ-009..016 | RQ-115 forgetfulness contract, RQ-117 memory immune system, RQ-119 narrative identity (gap) | ML-03, ML-11, ML-14..16, ML-20..23; F |
| 7 Goals, initiative, learning | RQ-018..022, RQ-031, RQ-034, RQ-040, RQ-041 | RQ-108 permission gradient | GC-03..08, GC-15, GC-21, GC-25/26, GC-45; IA-06, IA-13/14, IA-20..25, IA-37; LS-12, LS-16, LS-21..25 |
| 8 Coordination | RQ-014, RQ-038 | — | COMP-02, COMP-06/07, COMP-21; V1 L02/L03 |
| 9 Identity continuity | RQ-001..004, RQ-007, RQ-045, RQ-049 | RQ-104 identity versioning | I; AH-03/04, AH-10, AH-25; CR-03, CR-27, CR-30, CR-35; PE-18 |
| 10 Other | RQ-013, RQ-038, RQ-046 | RQ-117 | RC-24; E-15, E-29; PE-31 |

## 3. External citations: R-0 completed 2026-11-08

All 13 citations in the DeepSeek review were checked against primary listings. Per-citation results, actual findings,
limits and applicability are in [12-r0-citation-verification.md](12-r0-citation-verification.md). Summary:

| Status | Citations |
| --- | --- |
| VERIFIED (citable with stated limits) | CoRE (NeurIPS 2025); Reflective Memory Management (ACL 2025); metacognitive architecture (AAAI 2026); LoCoMo-Plus (ACL 2026); Memora (Findings ACL 2026); ToM position paper (ICML 2025) |
| VERIFIED, SCOPE DIFFERS (conceptual use only) | Third-Person Appraisal Agent (needs RL fine-tuning); MASC (multi-agent); CRSA (referential and template dialogs); ES-MemEval (emotional-support specific, *more* relevant) |
| PREPRINT (not support) | Human Emotion Verification by Action Languages (under consideration at TPLP); Think² (arXiv, 8B models); AgentMemBench (single-author, under submission) |
| NOT FOUND | none |

Dataset and code licences were not checked; check each before any use.
