# Independent architecture review: source index (2026-11-08)

Status: **REVIEW INPUT INDEX, read-only.** The review was received 2026-11-08 and is reconciled in [the cognitive R&D planning package](cognitive-rd-plan-2026-11/README.md). This page lists the existing designs, research questions, implementations
and deferred proposals an independent reviewer (DeepSeek) should read before any new advanced-cognition plan is
written. It proposes nothing, accepts nothing and authorizes nothing. No new architecture roadmap is written until that
review is back (owner decision 2026-11-08).

**Privacy.** Every linked file is already in this public repository, and the historical originals passed the
public-safety review recorded in [source-manifest.md](source-material/source-manifest.md). Excluded from the review:
credentials and keys; personal memory contents (canonical memories, `USER.md`, `MEMORY.md`, World Model owner
beliefs); conversation transcripts (`state.db`); operator folders and logs; the private infrastructure documents (S3
series); and the 16 private contract PDFs (section 6), which can be shared separately only after a public-safe
derivative review.

Labels: **SOURCE-VERIFIED** means it is in code and tests here. **OPERATOR-REPORTED** means it was observed on the
running hosts and recorded in [the PROD work note](../engineering/prod-work-note-2026-11-07.md).

## 1. Canonical architecture (read first)

| Document | Why |
| --- | --- |
| [Cognitive Architecture V1](../architecture/cognitive-architecture-v1.md) | The 19 layers (L01–L19) and their legal call directions. §10 motivational/homeostatic model, §14 meta-cognition (L16), §15 personality and social-cognition boundary (L11), §16 learning and consolidation (L18), L19 device and session synchronization |
| [Cognitive Architecture V1, original PDF](source-material/originals/LILITH_Cognitive_Architecture_V1.pdf) | The authoritative original of the above |
| [Architecture & Research Master v1.1 (PDF, 14 Sep 2026)](source-material/originals/LILITH_Architecture_and_Research_Master_v1.1.pdf) | **§08 "Relationship and affective continuity", p. 19:** the functional affect architecture (drives, appraisal, fast affect, slow mood, expression, outcome memory) and its constraints. p. 15: the eight V1 drives and their measurable proxies. pp. 26–42: the complete research-question register (RQ-120/121 on affect, p. 42). p. 44: the plain-English recovery summary of causal functional affect |
| [Identity charter v1 (draft)](../architecture/lilith-identity-charter-v1-draft.md) | What must stay invariant across runtime and model changes |
| [Current-architecture acceptance ledger](../architecture/current-architecture-acceptance-ledger-v0.1.md) | What was accepted and on what evidence |
| [ADR-0014](../adr/0014-proposed-cognitive-sources-enter-architecture-through-native-acceptance.md), [ADR-0013](../adr/0013-world-model-preserves-claims-separates-epistemic-projection.md), [ADR-0007](../adr/0007-owner-domain-canonical-state-ownership.md), [ADR-0009](../adr/0009-governed-effects-authorized-at-trusted-effect-boundary.md) | How new cognitive sources may enter, epistemic projection, owner-domain state and the effect boundary |

## 2. Research questions and findings

- [Research-question register](research-question-register.md), [candidates](rq-candidates.md),
  [numbering reconciliation](rq-numbering-reconciliation.md), [evidence map](rq-evidence-map.md),
  [negative results](negative-results-register.md)
- Findings most relevant to affect, social cognition and continuity:
  [RQ-040 attention, motivation, affect](findings/rq-040-attention-motivation-affect.md),
  [RQ-001 identity continuity](findings/rq-001-identity-continuity.md),
  [RQ-004 shared state across channels](findings/rq-004-shared-state-across-channels.md),
  [RQ-015 inference is not memory](findings/rq-015-inference-is-not-memory.md),
  [RQ-012 contradiction and supersession](findings/rq-012-contradiction-and-supersession.md),
  [RQ-044 evaluation and regression](findings/rq-044-evaluation-and-regression.md)
- [Cognitive continuity research charter v0.1](charters/lilith-cognitive-continuity-research-charter-v0.1.md),
  [architecture evolution](architecture-evolution.md), [slice history](slice-history.md)

## 3. What is implemented (lanes as built)

| Layer | Design | PROD source (SOURCE-VERIFIED) | Status (OPERATOR-REPORTED) |
| --- | --- | --- | --- |
| L08 Reasoning | [Slice 9](../architecture/slice-9-reasoning-extraction-design.md) | `deploy/prod/lilith_router/reasoning.py` | live, owner channels |
| L02 Workspace | [Slice 10](../architecture/slice-10-global-workspace-design.md) | `workspace.py` | live |
| L06 Motivation | [Slice 11](../architecture/slice-11-motivation-homeostasis-design.md) | `motivation.py` | live: ordinal drive pressure into the Workspace; no affect state |
| L10 Planning | [Slice 12](../architecture/slice-12-planning-design.md) | `planning.py` | live, proposal-only |
| L09 Ethics | [Slice 13](../architecture/slice-13-ethical-deliberation-design.md) | `ethics.py` | live, advisory-only |
| L11 Social Cognition | [Slice 14](../architecture/slice-14-social-cognition-presence-design.md) | `social_cognition.py` | live for owner turns: deterministic cues plus optional tone note; no appraisal |
| L18 Learning | [Slice 15A](../architecture/slice-15a-learning-consolidation-foundations-design.md) | `learning_worker.py`, `learning_store.py` | consolidation shadow only; L18 event ledger live |
| L05 World Model / L07 Goals | [Cognitive Architecture V1 §13](../architecture/cognitive-architecture-v1.md) | `world_context.py`, `services/core-api` | live |
| L04 Canonical memory | [PROD integration plan](../architecture/canonical-memory-prod-integration-plan.md) | `canonical_memory.py` plus the governed stack | live for owner channels (2 admissions) |
| L16 Meta-cognition, L19 Sync | Cognitive Architecture V1 §14, L19 | none dedicated | not implemented as layers; one identity across the console, Telegram and (in activation) a Discord DM |

## 4. Deferred proposals and measured evidence

- [PROD work note §6](../engineering/prod-work-note-2026-11-07.md): the advanced affect and Social Cognition research note
  (appraisal from observable goal or outcome changes, not a surprise predictor; measure before promoting). §3a: the
  measured offline A/B of the Social Cognition tone note (14 scenarios) and its limitations.
- [Cognition proposals](../../integrations/hermes/proposals/): cross-lane, Workspace integration, Planning and Ethics
  shadow, Goals hardening and privacy proposals; PR #296 (pending owner go): cognition dependencies, goal erasure.
- [Social Cognition record](../architecture/slice-14/DEPLOYMENT-RECORD.md), [Motivation record](../architecture/slice-11/DEPLOYMENT-RECORD.md)

## 5. Operational reality (for grounding, not for review of operations)

- [AS-IS current state](../architecture/as-is.md) and [the PROD work note](../engineering/prod-work-note-2026-11-07.md):
  what is live, broken (Google OAuth) or deferred, and the VM migration before 2026-11-18.

## 6. Private material, named only (not in this repository)

The **Cognitive Architecture Contract Set v0.1** ([index](../architecture/cognitive-contracts/v0.1/README.md)): 16
PROPOSED / NOT ACCEPTED design PDFs in the owner's private archive. They include the *Affect-Appraisal Research
Protocol*, *Personality Evolution*, *Relationship Continuity*, *Self-Model, Metacognition and Capability Awareness*,
*Identity Invariant*, *Continuity Benchmark and Evaluation Protocol* and the *Integrated Cognitive Architecture and
Composition Contract*. They are the most detailed prior work on the topics under review. Share them with the reviewer
only after the owner's own public-safety check.

## 7. What the reviewer is asked to assess (scope only, no plan)

1. Whether the 19-layer architecture and the Master v1.1 affect design are coherent with what is actually built (§3),
   and where they conflict.
2. Which deferred items (affect and appraisal, slow mood, persistent social preferences, meta-cognition, L18
   consolidation) are well-founded given the measured evidence, and which lack an evaluation method.
3. Risks: over-inference, manipulation and dependency shaping, governance bypass, identity drift under model or runtime
   change.
