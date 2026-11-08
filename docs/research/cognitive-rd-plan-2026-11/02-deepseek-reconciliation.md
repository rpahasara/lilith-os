# 02. DeepSeek independent review: reconciliation

The DeepSeek review (2026-11-08) inspected the public repository.
- It read `social_cognition.py`, `_prod_world_context.py` and `canonical_store.py`, the architecture specification,
  the evolution record, the acceptance ledger, the RQ-040 finding, the charter and the register.
- By its own account it could not read `run.py`, `canonical_memory.py` or `classifier.py`, and did not execute the
  system.
- This page states, point by point, what we **accept**, **adapt** or **reject**, and corrects claims that newer
  evidence contradicts.
- Its literature citations were **EXTERNAL-CLAIM** until R-0. **R-0 is complete** ([12](12-r0-citation-verification.md)):
  - 6 are verified as described;
  - 4 exist but with a narrower scope than stated;
  - 3 are preprints, not published work;
  - none were not found.
  - No decision below changes; two are strengthened (D8 deterministic appraisal by CoRE; behavioural measurement by
    the ToM position paper).

## 1. Factual corrections (the review is out of date or misread)

| Review claim | Current evidence | Effect on the plan |
| --- | --- | --- |
| "Production memory apply remains disabled" (from the README) | Two governed canonical memories are admitted on PROD and recalled on owner channels (OPERATOR-REPORTED 2026-11-06); the README was corrected in #357 | L04 is LIVE-NARROW, not design-only; consolidation can build on a working apply path |
| "Oh great, another meeting" is not detected as sarcasm | #346 added sarcasm markers that select the approved *mixed* line; the detector still covers only explicit patterns | The direction holds (regex cannot cover the long tail), but the specific example is partly handled |
| Self-status hints (aaa4a55 / #351) are "metacognition reporting" | That path is **goal grounding** for "what am I working toward?" (E-T4), owner-confirmed 2026-11-08. There is no metacognition implementation | L16 is ABSENT, not PARTIAL |
| Experiment 1, "tone note efficacy", is proposed | Already **MEASURED**: a 14-scenario blind A/B (work note §3a). The note helped on mixed, teasing and no-sleep turns, was neutral elsewhere, and hurt technical turns until the #346 gate | Experiment 1 is done; its method becomes the harness for every later experiment |
| "Two owner memories reportedly admitted, but full autobiographical admission… incomplete" | Correct | — |
| Cost "~$0.005–$0.01 per turn" for an interpretation call | Our binding constraint is **provider quota**, not dollars: 200K Groq tokens a day for all casual chat, and a ChatGPT-plan model for the agent. One extra call on every social turn would take 30–45% of the daily fast-path budget | Interpretation must be gated to ambiguous turns and budgeted in tokens ([09-roadmap.md §4](09-roadmap.md)) |

## 2. Recommendations: accept, adapt or reject

| # | DeepSeek recommendation | Decision | Why |
| --- | --- | --- | --- |
| D1 | Keep the governance separation, fail-closed validation, forbidden keys and atomic apply boundary | **ACCEPT** | Matches COMP-01..09 and our owner directive |
| D2 | Keep the 19 layers as a reference map, not a build plan | **ACCEPT** | Same position as Cognitive Architecture V1 §0 and §19 |
| D3 | Keep ordinal, non-emotional drives; no scalar emotion labels | **ACCEPT** | Matches the RQ-040 finding and AP-02/AP-19 |
| D4 | Keep the deterministic cue detector as a fast trigger, not the solution | **ACCEPT** | Our own A/B reached the same conclusion |
| D5 | "Simplify the 19 layers into two tiers / loops" | **ADAPT** | We adopt a *runtime view* of two loops (fast per-turn, deliberate when needed) **mapped onto** the 19 layers ([04](04-target-architecture.md)). The layers stay as ownership and contract boundaries; collapsing them would discard the owner-domain separation that COMP-06/07 depends on |
| D6 | Priority 1: a Social Interpretation Proposal, as an extra model call on ambiguous turns | **ADAPT, as an experiment, not a build** | Our evidence says the native model already interprets context well. The call must (a) beat a **no-extra-call** arm that gives the reply model better context (approved preferences, recent cues), (b) fire only on a gated ambiguous subset, (c) fit a token budget. See E-3 in [10](10-experiments.md) |
| D7 | Persistent social beliefs in the World Model | **ACCEPT, re-scoped** | The persistence path already exists: owner-approved owner-memory beliefs plus L18 events. What is missing is a typed *preference / boundary* category and its use in tone and response selection. Moved ahead of D6 |
| D8 | One appraisal dimension first: expectation violation from World Model prediction error | **ADAPT** | The World Model has no predictions today. The cheapest grounded signal is **commitment and goal-state change** (a goal deadline passed, a plan step failed, a correction contradicting a belief), computed deterministically. Prediction error comes later, once predictions exist |
| D9 | Metacognitive gating on calibrated uncertainty | **ADAPT** | We have no calibrated confidence, and model self-reported confidence is not calibration (SM-19/20). Start with **observable** signals (retrieval coverage, contradiction present, fallback model active, guard regeneration, explicit correction) gating three cheap actions (escalate model, widen retrieval, ask a clarifying question) |
| D10 | Reflective memory management (prospective / retrospective reflection) for social preferences | **ADAPT** | Prospective reflection maps to the existing nightly owner-memory review, which already proposes. Retrospective reflection (RL over retrieval) is out of scope; replace it with a measured retrieval-usefulness log |
| D11 | CRSA-style pragmatic reasoning | **DEFER** | Conceptually useful framing for E-3's schema (the user's private information, shared goals); no implementation |
| D12 | Use long-term memory benchmarks (ES-MemEval, LoCoMo-Plus, Memora, AgentMemBench) | **ADAPT** | Names unverified (R-0). We build a small *LILITH-specific* suite first, because our failure modes are personal. Public benchmarks only after verification and licence check |
| D13 | Don't build: an emotion classifier, a social reasoning lane, a fine-tuned social model, regex expansion, raw emotion labels in memory | **ACCEPT** | Matches owner directives (no new lanes) and AP-02 / ML-32 / RC-23 |
| D14 | "Metacognition that doesn't gate is decorative" | **ACCEPT** | Becomes a design rule: every proposed signal must name the behaviour it changes and the metric that shows it ([04 §4](04-target-architecture.md)) |

## 3. Where we go further than the review

- **Evaluation foundation first.** The review's success criteria (blind human preference, a cost cap, a latency cap)
  need a harness, a rater protocol and frozen scenario suites. Two of three past tone-note decisions were settled by
  measurement. Phase 1 of [09](09-roadmap.md) builds this before any mechanism.
- **Correction learning before interpretation.** The cheapest high-value loop is "the owner corrects LILITH, and the
  behaviour does not recur". It reuses existing approval and memory paths and needs no new inference.
- **Model swap as a continuity test bed.** Live traffic already crosses three models (Groq Qwen, gpt-5.6-sol, Copilot
  gpt-4.1). This gives a natural identity-continuity experiment that the review does not mention ([08](08-identity-and-other.md)).
- **Affect stays ephemeral until a research gate.** Per AP-35 and CR-30, any appraisal state resets at session and
  migration boundaries. No slow mood persists before preregistered evidence.
