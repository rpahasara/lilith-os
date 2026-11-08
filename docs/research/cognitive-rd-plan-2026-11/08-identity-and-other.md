# 08. Runtime-independent identity continuity, and other capabilities worth considering

Topics 9 and 10.

## 1. Runtime-independent identity continuity

**Design anchors.**
- **Identity Invariant Specification (I):** core invariant and dimensions; replacement and portable state;
  model-swap acceptance benchmark.
- **Model-Runtime Adapter & Handoff (AH):**
  - ownership separation (AH-03) and permissive model containment (AH-04);
  - minimum-sufficient context (AH-10);
  - compatibility is semantic (AH-25).
- **Cognitive Recovery, Migration & Multi-Device Continuity (CR):**
  - a device is never LILITH (CR-03);
  - no silent lossy migration (CR-35);
  - First Memory is not recreated (CR-27).
- **Personality Evolution (PE):** a new model is not a new personality (PE-18).
- **Continuity Benchmark & Evaluation Protocol (B).**
- **Repo RQs:** RQ-001, RQ-002, RQ-004, RQ-007, RQ-045, RQ-049.

**What carries identity today** (OPERATOR-REPORTED). It all lives *outside* the model:
- SOUL.md (persona core);
- approved profile memory (USER.md as a projection of World Model owner records);
- canonical memories (2);
- World Model beliefs and goals;
- L18 event history.

The same identity is served by three models in live traffic (Groq Qwen, gpt-5.6-sol, Copilot gpt-4.1) and across three
owner channels.

**What is missing.**

| Gap | Why it matters | Proposal | Cost |
| --- | --- | --- | --- |
| No identity-consistency measurement across models | Fallback and lean turns may drift in voice, values or recall | **E-10**: a fixed 20-prompt identity suite (from the Cutover baseline prompts) run on each live model; blind owner rating of "this is LILITH"; a recall-correctness score | ~20 calls per model per run; run before and after any model change |
| No `IdentityFrame` (L19) | Cross-channel references ("as I said on Telegram") fail; a session is per channel | A small per-owner *recent cross-channel summary*, composed from episode records (C-1), rendered only on owner channels | none per turn (deterministic); nightly summarization optional (~2K tokens) |
| Migration risk (2026-11-14) | The whole identity substrate moves hosts | Migration plan: inventory, off-project backup, restore verification, re-seal host-bound credentials; identity suite (E-10) before and after the switch | operational |
| Model-change governance | A provider or model change can silently alter judgment (RQ-045) | Rule: any default-model change requires E-10 to pass, with no regression on the canonical recall items | evaluation only |

## 2. Other research-backed capabilities worth considering (ranked by value ÷ cost)

| Capability | Value | Why now or later | Reuse | Status |
| --- | --- | --- | --- | --- |
| **Owner-visible "what I know about you" view** (explainability, RQ-013/038; RC-24 read-only projection) | Trust; lets the owner correct; feeds E-6 | Now-ish: all data exists (World Model owner beliefs, canonical, L18) | Core API read routes; console | PROPOSED, P-2 |
| **Clarifying-question policy** (ask vs guess) | Cuts confident errors; cheap | With G-ASK | L16 gate | PROPOSED, P-3 |
| **Epistemic hygiene in replies**: separate "I remember / I infer / I'm guessing" | Honesty (E-15 source class ≠ truth; E-29 memory ≠ truth) | Prompt-level style plus grounding labels | canonical note renderer | PROPOSED, P-3 |
| **Topic and thread continuity within a channel** | Fewer "what were we talking about" failures after Hermes session resets | With episode records | C-1 | PROPOSED, P-4 |
| **Voice and presence parity** (Hsin on messaging) | Embodiment | Later: console-only today; the HS contract is heavy | presence contract | DEFERRED |
| **Counterfactual and planning simulation** | Better plans | Later: needs a verified-outcome history first | Planning lane | DEFERRED |
| **Learned interruption policy** (RQ-040) | Smarter proactivity | Only after weeks of E-9 logs | initiative log | DEFERRED |
| **Adversarial-memory defense** (Master RQ-117) | Injected content can't become memory or preference | Partially present (approval gate, instructions-in-evidence-are-data PE-31) | approval path | CONTINUOUS |

**Explicitly not recommended** (agreeing with DeepSeek D13 unless noted):
- an emotion classifier or emotion labels in memory;
- a new social or affect lane;
- fine-tuning;
- Theory-of-Mind benchmark chasing;
- persistent mood before the AP research gate;
- self-directed goals before GC-26;
- scalar trust or closeness scores. This one goes further than the review, per RC-05..07.
