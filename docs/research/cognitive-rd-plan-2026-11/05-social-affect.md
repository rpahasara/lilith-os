# 05. Social Cognition, relationship continuity and appraisal-driven functional affect

Topics 3 and 4. Experiment IDs (E-n) refer to [10-experiments.md](10-experiments.md); phases (P-n) refer to
[09-roadmap.md](09-roadmap.md).

## 1. Relationship continuity and persistent social preferences

**Goal.** LILITH remembers *how* the owner wants to be treated (humour limits, topics to avoid, preferred directness,
what comfort looks like, nicknames) and uses it consistently across channels and models. A correction changes future
behaviour without over-generalizing (RQ-042).

**Design anchor.** The Relationship Continuity contract (RC). This edition is a *regenerated reconstruction*; its
original text was unrecoverable, so it is treated as a design aid, not a canonical source.
- Familiarity ≠ trust ≠ closeness ≠ consent (RC-05..08).
- Boundaries take precedence (RC-09).
- Preferences are scoped (RC-10).
- Conflicts are represented (RC-14), repair is evidenced (RC-15), absence is not betrayal (RC-17).
- No engagement coercion (RC-30) and no fabricated mutual history (RC-32).

| Component | Responsibility | Reuses | New |
| --- | --- | --- | --- |
| `PreferenceClaim` category in owner memory | Store an approved, scoped preference or boundary with evidence refs and scope (all channels / casual only / topic) | World Model owner-memory beliefs (#339), L18 events (#341), approval path (#340) | a `kind` (preference / boundary) and `scope` fields on owner-memory records |
| Preference proposer | Propose a claim from (a) an explicit owner statement, (b) a repeated correction, (c) the nightly review | in-chat proposals (#338), nightly review prompt, rejection memory | correction-pattern trigger (deterministic: the same correction cue twice within N days) |
| Preference retrieval | Put ≤3 relevant approved claims into `TurnContext.preferences` | canonical / profile note path | relevance by scope and cue overlap (deterministic) |
| Style composer | Map cues, preferences and the explicit request to a typed `StyleDirective`; a boundary always wins | `tone_note_keys` (#346) | preference-aware selection; `confidence=low` ⇒ no line |
| Relationship ledger (later) | Repair, conflict and absence as evidenced events, not scores | L18 events | RC-14/15 event kinds. **No closeness or trust scores** |

**Dependencies.** The evaluation foundation (P-1); typed owner-memory fields (Core API change); the nightly review
including Discord DM sessions (pending owner decision).

**Inference cost.**
- No extra per-turn call.
- Retrieval is deterministic.
- Proposals reuse the nightly review run, adding roughly 1–3K tokens per night on the agent model.

**Experiments.** E-2 (preference recall and over-generalization) and E-6 (correction recurrence).

**What not to do.**
- Infer preferences from one message.
- Store "the owner is sensitive about X" as a fact without approval.
- Let a preference become permission (RC-08, COMP-24).

## 2. From detection to interpretation (DeepSeek D6, as an experiment)

**Problem.** The cue detector has high precision but low recall (13/150 in shadow) and no notion of implicature ("I'm
fine" after frustration). The reply model already reads context well (MEASURED), so the open question is narrow:
**on the turns where the reply goes wrong, would a structured interpretation fix it, and is it cheaper than better
context?**

**Gate.** All of these must hold, so the call runs on a few percent of turns, not every turn:
- an owner turn;
- the turn is ambiguous: conflicting cues, a brush-off after a difficulty, laughter together with a difficulty, sarcasm
  markers, or a correction cue;
- no explicit request is present;
- the budget is available.

**Schema** (proposal-only, never stored):
- `interpretation`: literal | playful | sarcastic | masking | supportive-request | corrective | ambiguous
- `confidence`: low | medium | high
- `evidence[]`: cue ids and turn refs
- `assumption`: one line
- `style_hint`: register, humour, support, directness

A low-confidence or `ambiguous` result maps to "no line" plus, when stakes are high, permission to ask a gentle
clarifying question.

**Arms (E-3):**
1. current behaviour;
2. **better context, no extra call** (preferences plus last-turn cue summary);
3. an interpretation call on the cheapest adequate model;
4. an interpretation call on the reply model.

Arm 2 must be beaten for arms 3 or 4 to be promoted.

**Cost.**
- About 1.5–2.2K tokens per gated call: roughly 600 tokens of schema and instructions, 600–1,200 of recent turns, 200
  of cues and preferences, and 150 of output.
- At an estimated 4–6 gated turns a day, that is about 6–13K tokens a day, or 3–7% of the Groq daily budget.
- Latency: plus one round-trip, about 0.5–1.5 s on Groq, on gated turns only.

## 3. Appraisal-driven functional affect and event-history-dependent behaviour

**Design anchor.**
- **Master v1.1 §08 (p. 19):** drives → appraisal → affective state → cognition and expression → outcome → memory / mood.
- **Affect-Appraisal Research Protocol (AP),** also a regenerated reconstruction:
  - affective state ≠ interpretation ≠ expression (AP-02);
  - no self-corroborating emotional history (AP-19), a finite loop budget (AP-20), no engineered pathology (AP-21);
  - no absence or jealousy loop (AP-25), no romance mode or dependency reward (AP-26);
  - persistence deferred (AP-35), and no activation by research success (AP-40).

**Re-scoping (DeepSeek D8, adapted).** Prediction error needs predictions the World Model does not make yet. The first
appraisal dimensions use **state the system already has**:

| Dimension (ephemeral, per turn) | Computed from | Example behaviour change |
| --- | --- | --- |
| **Goal relevance** | message entities ∩ active goals and commitments (L07) | prefer task-supportive replies; retrieve goal context |
| **Goal congruence** (progress / setback) | goal state transitions, plan step results, explicit outcome statements ("rejected", "passed") | acknowledge the setback before advising; no forced cheer |
| **Commitment violation** | `CommitmentRecord` due or broken (L07, later) | LILITH owns a missed follow-up instead of ignoring it |
| **Correction / norm violation** | correction cue against an approved preference | apologise briefly, comply, propose a preference update (E-6) |
| **Expectation violation** (later) | World Model prediction vs observation, once predictions exist | widen retrieval; ask |

**Event-history dependence without persistent mood.**
- History reaches the next turn through **approved, evidenced records**: episodes, outcomes, preferences and
  commitments in [06 §3](06-metacognition-memory.md).
- It never arrives through a hidden mood variable. *"You had two rejections this week"* is a fact the owner can see and
  correct.
- *"LILITH is sad"* is not stored (ML-32, AP-19).

**Slow mood: research gate, not roadmap.** A decaying, bounded, inspectable state that biases tone over days is
allowed to be *studied* (AP-08 hypothesis) only after all of these:
- E-4 shows per-turn appraisal changes behaviour in ways the owner prefers;
- a welfare and manipulation review (AP-22, AP-25, AP-26);
- a preregistered study (AP-32);
- four baselines and causal ablations (AP-30/31).

**Components.**
- A deterministic appraiser module (pure function over `TurnContext`).
- `AppraisalSignal` in `TurnContext`.
- A mapping to `StyleDirective` and retrieval scope.
- **No model call. No persistence.**

**Inference cost.** Zero additional calls. CPU only.

**Experiments.** E-4 (appraisal ablation: with vs without appraisal signals, the same reply model, blind owner rating).
