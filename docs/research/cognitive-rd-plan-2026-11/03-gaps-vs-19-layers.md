# 03. What is missing from the original 19-layer design

For each layer:
- the column "V1 intent" paraphrases the layer's responsibility in
  [Cognitive Architecture V1](../../architecture/cognitive-architecture-v1.md) §2–7;
- "Today" summarizes [01](01-as-is-maturity.md);
- the gap is rated **critical** (blocks a planned capability), **important** (limits quality) or **acceptable**
  (deliberately deferred);
- "Plan" points to the workstream that addresses it.

**One V1 statement is superseded.** V1 §16 says L18 is the *only* writer to LTM and that contradiction resolution is
"never destructive delete". Master v1.1 and ADR-0006 (cited as superseding by contract ML-02) instead have L18
**propose** and L04 **apply** through the governed path, with privacy erasure able to override retention. This package
follows the newer rule.

| Layer | V1 intent | Today | Gap | Rating | Plan |
| --- | --- | --- | --- | --- | --- |
| L01 Perception | One typed, provenance-stamped `PerceptEvent` for every signal (chat, timers, devices, connector callbacks) | Hermes adapters plus the router's channel and owner resolution; timers and watchers are separate systemd jobs, not percepts | Proactive events (calendar, mail, goal deadlines) never enter cognition as percepts. Blocked partly by OAuth | important | [07](07-goals-initiative-learning.md) §2 |
| L02 Workspace | Salience bids from every source compete; the winner is *broadcast* to memory, reasoning, goals and social; owns the interruption budget | Arbitration only for the Reasoning input; no broadcast; lanes claim turns independently | **No shared per-turn context**: social, goal and memory signals never meet. No interruption budget, because there is no initiative | **critical** | [04](04-target-architecture.md) §2 |
| L03 Working Memory | Ephemeral, bounded working set of focus, retrieved memories, beliefs and goals | Built per lane (World-Model top-k); not shared across lanes | Same as L02: no single working set per turn | important | [04](04-target-architecture.md) |
| L04 LTM | Episodic, semantic and procedural stores with provenance and confidence | Canonical store (2 memories) plus profile projections; episodic history lives only in Hermes `state.db` (unstructured) | **No episodic layer** (what happened, when, with what outcome) and no procedural recipes | **critical** for autobiographical memory | [06](06-metacognition-memory.md) §3 |
| L05 World Model | Belief graph with confidence, TTL, conflict records, and `PredictionError` / novelty | Beliefs and evidence; conflict table (0 conflicts); **no predictions, so no prediction error** | No expectations to violate; confidence is mostly categorical | important | [05](05-social-affect.md) §3, [06](06-metacognition-memory.md) |
| L06 Motivation | Drive vector from measurable proxies → salience and goal weights | 3 ordinal drives; SAFETY has no producer; affects only the Reasoning bound | Drives don't weight goals or initiative; the eight V1 drives (Master p. 15) are not all represented | acceptable (deliberate) | [05](05-social-affect.md) §3 |
| L07 Goals / Executive | Goal stack, arbitration, preemption, durable continuity | Goal store, FSM, grounding, explicit creation | No commitments (promises made in conversation); no staleness detection (RQ-020); no completion proof (GC-21) | important | [07](07-goals-initiative-learning.md) |
| L08 Reasoning | Bounded inference engine; confidence estimates; structured interpretation | Tool-less reasoning lane plus the main model | No **structured interpretation** output and no confidence estimate | important | [05](05-social-affect.md) §2, [06](06-metacognition-memory.md) §2 |
| L09 Ethics | Advisory review under ambiguity | Live, advisory-only | Adequate for now | acceptable | — |
| L10 Planning | Plans, replanning on failure or disproved assumptions | Proposal-only plans; no replanning from outcomes | No plan → execution → outcome → replan loop | important | [07](07-goals-initiative-learning.md) §3 |
| L11 Social / Personality | Relationship model, theory of mind, style directives | Turn-only cues; tone note; personality = SOUL.md plus profile | **No relationship model, no persistent preferences in tone selection, no interpretation**; `StyleDirective` is free text, not typed | **critical** | [05](05-social-affect.md) §1–2 |
| L12 Policy | Single action gate | Live | Adequate | acceptable | — |
| L13 Runtime | Execute approved capabilities, idempotency | Live (Hermes tools) | Adequate for the current scope | acceptable | — |
| L14 Connectors | Health-gated typed I/O | Live; Google degraded | Operational fix at migration (OAuth) | important (operational) | migration |
| L15 Verification | Prove effects; feed outcomes to the World Model and Learning | Write read-back only | **Outcomes don't feed learning**; conversational commitments are never verified | important | [07](07-goals-initiative-learning.md) §3 |
| L16 Meta-Cognition | Signals (confidence, latency, contradiction, drive tension, loops, budget, persona drift) → bounded controls; the **cognitive trace** | None. Decision logs exist per lane but are not correlated per turn | **No monitor, no trace, no gating** | **critical** | [06](06-metacognition-memory.md) §1–2 |
| L17 Presence | Render `PresenceIntent` | Console only | Messaging channels have no presence semantics (by design) | acceptable | — |
| L18 Learning | Offline consolidation: extract, reconcile, reinforce from proof, gated value learning | Event ledger plus owner-approved learning; Slice 15A shadow worker on a stale source | **No episodic→semantic extraction, no reinforcement from verified outcomes, no reappraisal** | **critical** | [06](06-metacognition-memory.md) §3 |
| L19 Sync | One identity frame across devices and sessions | Shared durable stores across three owner channels; separate conversation sessions | No cross-channel working continuity ("as I said on Telegram…"); no `IdentityFrame` | important | [08](08-identity-and-other.md) §1 |

## Gaps that are deliberate, not omissions

- **Persistent affect and mood.** AP-35: persistence stays deferred until a research gate. CR-30: ephemeral appraisal
  resets at recovery.
- **Self-directed goals.** GC-25 treats them as research; GC-26 requires a bounded autonomous-goal policy first.
- **Personality evolution by the model.** PE-15: autonomy needs a separately accepted policy. PE-30: no
  self-reinforcing trait acceptance.
- **Romance mode and dependency reward.** AP-26, RC-22 and RC-30 permanently exclude engagement coercion.

## Gaps the original design did not anticipate

1. **Quota-constrained inference.** V1 assumes per-layer model calls are available. Production shows a shared daily
   token budget for all casual chat. Cost-aware gating is therefore an architectural concern, not tuning.
2. **Multiple live models per conversation.** Lean Groq, native Sol and the Copilot fallback mean identity and style
   continuity must hold *within* one conversation across models, not only across replacements.
3. **Owner-approval as the learning bottleneck.** All durable learning is owner-approved (by design). Consolidation
   must produce few, high-quality proposals, or approval fatigue becomes the failure mode.
