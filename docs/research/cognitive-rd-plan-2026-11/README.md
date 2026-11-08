# LILITH Advanced Cognition: R&D Planning Package v0.1 (2026-11-08)

Status: **PROPOSED / DOCUMENTATION ONLY.** The architecture and research direction were approved by the owner on
2026-11-08 *as a documentation proposal*. Implementation of advanced cognition starts only after the migration and OAuth
recovery, phase by phase, each with its own go.
- It authorizes no implementation, PROD deployment, live experiment, memory or personality mutation, or new lane.
- Every mechanism here is a candidate that must earn promotion through the experiments in
  [10-experiments.md](10-experiments.md).
- Each phase in [09-roadmap.md](09-roadmap.md) needs its own owner go.

## Purpose

This is one coherent engineering and research plan for LILITH's next cognitive capabilities. It is built from what
already exists and what has been measured, not from a blank page. It **preserves the original architecture**: the
19-layer Cognitive Architecture V1 stays the reference map. It **challenges assumptions where the evidence does**,
including several in the independent DeepSeek review.

## Inputs

| Input | Where | Role here |
| --- | --- | --- |
| Cognitive Architecture V1 (19 layers) | [cognitive-architecture-v1.md](../../architecture/cognitive-architecture-v1.md) | Reference functional map; layer IDs L01–L19 are used throughout |
| Architecture & Research Master v1.1 | [PDF](../source-material/originals/LILITH_Architecture_and_Research_Master_v1.1.pdf) | Functional affect design (§08, p. 19), drives (p. 15), Master RQ-101–121 (pp. 26–42) |
| Cognitive Architecture Contract Set v0.1 (16 PDFs) | private archive; [index](../../architecture/cognitive-contracts/v0.1/README.md) | Detailed proposed contracts. Cited by short code and requirement ID, paraphrased, never reproduced (see [11-traceability.md](11-traceability.md)) |
| Research charter and RQ register | [charter](../charters/lilith-cognitive-continuity-research-charter-v0.1.md), [register](../research-question-register.md), [reconciliation](../rq-numbering-reconciliation.md) | The questions each workstream answers |
| Current PROD implementation | `deploy/prod/lilith_router/`, `services/core-api/`, [AS-IS](../../architecture/as-is.md) | What is live today |
| PROD work note | [prod-work-note-2026-11-07.md](../../engineering/prod-work-note-2026-11-07.md) | Measured evidence (Social Cognition A/B, E-T4), operational limits |
| DeepSeek independent review (2026-11-08) | summarized and reconciled in [02-deepseek-reconciliation.md](02-deepseek-reconciliation.md) | External critique; accepted, adapted or rejected point by point |

## Reading order

| # | File | Answers |
| --- | --- | --- |
| 01 | [01-as-is-maturity.md](01-as-is-maturity.md) | What exists, at what maturity, and how a turn flows today (topic 1) |
| 02 | [02-deepseek-reconciliation.md](02-deepseek-reconciliation.md) | What the external review gets right, wrong or outdated |
| 03 | [03-gaps-vs-19-layers.md](03-gaps-vs-19-layers.md) | What is missing from the original design, layer by layer (topic 2) |
| 04 | [04-target-architecture.md](04-target-architecture.md) | Two-loop runtime view over the 19 layers; shared turn context; missing interfaces; cross-lane coordination (topic 8) |
| 05 | [05-social-affect.md](05-social-affect.md) | Social Cognition and relationship continuity (3); appraisal-driven functional affect (4) |
| 06 | [06-metacognition-memory.md](06-metacognition-memory.md) | Metacognitive monitoring and adaptive control (5); L18 consolidation, autobiographical memory and reappraisal (6) |
| 07 | [07-goals-initiative-learning.md](07-goals-initiative-learning.md) | Autonomous goals, initiative, planning and verified outcome learning (7) |
| 08 | [08-identity-and-other.md](08-identity-and-other.md) | Runtime-independent identity continuity (9); other capabilities worth considering (10) |
| 09 | [09-roadmap.md](09-roadmap.md) | Phases, dependencies, gates, inference costs |
| 10 | [10-experiments.md](10-experiments.md) | Registered experiments: hypotheses, baselines, metrics, kill criteria |
| 11 | [11-traceability.md](11-traceability.md) | Requirement and source mapping (contracts, Master RQs, repo RQs) |
| 12 | [12-r0-citation-verification.md](12-r0-citation-verification.md) | R-0: the 13 external citations verified, with status, findings, limits and applicability |
| 13 | [13-p1-implementation-tasks.md](13-p1-implementation-tasks.md) | P-1 prepared: log and tool inventory, tasks T-1..T-6 (turn id, turn-end record, summarizer, harness in Git, owner rating, retention) |

## Evidence labels

- **SOURCE-VERIFIED**: in code, tests or merged PRs in this repository.
- **OPERATOR-REPORTED**: observed on the running hosts and recorded in the work note.
- **MEASURED**: an offline or live experiment with a recorded method and result.
- **PROPOSED**: this package, or a contract that is not accepted.
- **EXTERNAL-CLAIM**: a statement or citation from the DeepSeek review that we have not independently verified. It
  stays marked unverified until roadmap task R-0 checks it. R-0 was completed 2026-11-08; see [12](12-r0-citation-verification.md).

## The plan in five sentences

1. Do not add layers or lanes. Make a few existing mechanisms **causally effective** and **measured**.
2. First build the **evaluation foundation** (scenario suites, blind owner rating, cost and latency accounting), because
   two of three past tone-note decisions were settled by measurement, not by design.
3. Then, in order: **owner-approved social preferences** in the existing World Model (reusing natural learning);
   **correction learning**; a **quota-gated social interpretation** experiment on ambiguous turns only; and one
   **appraisal dimension** (expectation and commitment violation) computed without an extra model call.
4. **Metacognition** starts with cheap, causal gates (escalate, widen retrieval, ask) driven by signals the system
   already has. Model self-reports are not used as confidence.
5. Everything persistent goes through the existing propose / approve / apply path (L18 proposes; L04 / World Model
   apply). Affect stays ephemeral until a research gate says otherwise.

## Constraints that shape every choice

- **Quota is the binding cost, not dollars** (OPERATOR-REPORTED).
  - The fast path (Groq `qwen3.8-27b`) has 8K tokens per minute and a rolling 200K tokens per day; one lean reply is
    about 2.7K tokens.
  - The full agent runs on a ChatGPT-plan model; its fallback is Copilot Free (200 requests a month).
  - Offline experiments are capped at about 50K Groq tokens a day.
- **Latency:** casual replies are fast today. A serial extra call adds a full round-trip.
- **Governance:** the propose / apply separation, fail-closed validation, owner-only memory isolation and
  `_FORBIDDEN_KEYS` in Social Cognition stay intact.
- **Migration** (2026-11-14, trial expiry 2026-11-18) comes before any of this.
