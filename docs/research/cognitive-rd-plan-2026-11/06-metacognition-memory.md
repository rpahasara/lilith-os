# 06. Metacognitive monitoring, adaptive control, consolidation and autobiographical memory

Topics 5 and 6.

## 1. Metacognitive monitoring (L16): the cognitive trace first

**Design anchors.**
- **V1 L16 and §14:** read-only meta-signals, narrow controls, "not a second brain".
- **Self-Model, Metacognition & Capability Awareness contract (SM):**
  - calibration must be independent of the model (SM-19);
  - detect miscalibration and scope mismatch (SM-20);
  - introspection has a boundary (SM-14);
  - checks cannot escalate authority (SM-25);
  - calibrated honesty beats consistency (SM-39);
  - resist narrative and social pressure (SM-40).

**Step 1: correlated cognitive trace** (prerequisite for everything else).
- One `turn_id` is attached to every existing decision-log record: route, lanes fired, tone keys, focus, fallback used,
  guard regeneration, latency and tokens.
- Records hold metadata only; message text is never written.
- A read-only summarizer produces per-day aggregates: lane mix, gate firings, regeneration rate, fallback rate, token
  use.
- **Reuses** `decisions.log` and the lane trace helpers.
- **Cost:** none (local I/O).

**Step 2: a capability self-model as data, not prose** (SM-08: prose is a projection).
- A small, versioned, *operator-maintained* record of what LILITH can and cannot currently do. For example: Google
  connectors unavailable until the migration; fallback model active; Discord DM is an owner channel.
- It is rendered into the prompt only when relevant, such as a user asking for calendar data.
- This stops confident claims about broken capabilities, a real failure mode while OAuth is down.
- **Reuses** the connector health gate (Slice 6) and fallback activation events.

## 2. Adaptive control: gates that change behaviour (DeepSeek D9, adapted)

The model's own stated confidence is **not** used as calibration: SM-19, and the review's own cited caution. The gates
use the observable signals in [04 §4](04-target-architecture.md):

| Gate | Trigger | Action | Cost | Kill criterion |
| --- | --- | --- | --- | --- |
| G-ASK | personal-fact question with no grounding hit | answer "I don't have that", or ask, instead of guessing | none | the owner rates asks as annoying more often than they are useful |
| G-WIDEN | contradiction present, or a goal-relevant appraisal | add the conflict record and related beliefs to the context (bounded) | about 200–600 tokens on that turn | no measurable accuracy gain on E-5 |
| G-ESCALATE | lean turn needs grounding (recall miss, technical drift, guard regeneration twice) | route this turn to the full agent | one agent call instead of a lean call | latency complaints, or no quality gain |
| G-DEGRADE | fallback model or budget pressure | conservative style; defer risky claims | none | — |

**Calibration study (later).** Once the trace exists, log the gate decision against the owner's correction within N
turns. That gives an empirical error rate per signal, the first real calibration data (SM-19). Only then may scalar
confidence be considered.

**Experiment.** E-5 (gated vs ungated on a frozen suite of personal-fact, contradiction and technical-drift
scenarios).

## 3. L18 consolidation, autobiographical memory and reappraisal

**Design anchors.**
- **V1 §16** offline consolidation, superseded on writer authority by ML-02 / ADR-0006: L18 proposes, L04 applies.
- **Memory Lifecycle & Reappraisal contract (ML):**
  - storage ≠ acceptance ≠ truth (ML-03);
  - consolidation preserves evidence (ML-11), and reconstruction cannot manufacture memory (ML-14);
  - event history is separate from appraisal (ML-15), and *then and now* views keep separate lineage (ML-16);
  - forgetting without falsification (ML-20);
  - capacity cannot silently erase continuity (ML-22);
  - privacy takes precedence (ML-23);
  - affect does not become autobiography by expression (ML-32).
- **First Memory specification** for the autobiographical head (separately gated).

**Current reality.**
- The Slice 15A worker exists but reads only `career_events`, which have been stale since 08-31.
- Owner learning (in-chat plus nightly review) is the live consolidation path, and it already produces approved
  semantic facts and preferences.
- Episodic history exists only as raw transcripts in `state.db`.

**Staged plan.**

| Stage | What | Reuses | Persistence | Gate |
| --- | --- | --- | --- | --- |
| C-1 | **Episode records**: at turn end, a small structured record (turn_id, channel, topic tags, goal refs, outcome / correction flags, appraisal ids). No raw text; points to the transcript row | trace (§1), L18 event table pattern | Core API table, owner-only, inside FORGET scope (a new profile is needed before canonical promotion) | owner go; privacy review |
| C-2 | **Nightly consolidation proposals**: the existing nightly review also reads the episode records and proposes ≤3 items per night (preferences, recurring facts, commitments) | nightly review job, rejection memory, L18 events | proposals only | approval-fatigue metric (proposals rejected or ignored > 50% ⇒ tighten) |
| C-3 | **Outcome reinforcement**: verified outcomes (goal completed, commitment kept or broken) adjust *priority*, not truth, of related beliefs and goals | L15 read-back, goal FSM | goal and belief metadata | E-7 |
| C-4 | **Reappraisal**: when a new approved fact contradicts an old belief, propose a supersession that keeps both lineages (*then* vs *now*) | World Model conflict table, supersession (`SUPERSEDED` events exist) | proposals only | owner approval |
| C-5 | **Autobiographical memory**: canonical episodes ("the day we first talked", project milestones) admitted through the governed path; needs a FORGET profile per memory family | canonical store, privacy FORGET runner | canonical | separate owner ceremony per family; First Memory spec |
| C-6 | Restart the Slice 15A worker on a live source (career events after OAuth recovery), shadow | `learning_worker.py` | shadow | needs OAuth (migration) |

**Inference cost.**
- C-1, C-3 and C-4 detection need no model calls.
- C-2 adds roughly 2–5K tokens per night to the existing nightly run.
- C-5 is human-paced.

**Benchmarks (DeepSeek D12, adapted).** A LILITH-specific recall suite comes first (E-2, E-8).
- R-0 ([12](12-r0-citation-verification.md)) verified ES-MemEval (WWW '26; emotional-support specific), LoCoMo-Plus (ACL 2026) and Memora (Findings ACL 2026).
- AgentMemBench is only a preprint.
- Two verified patterns are adopted in experiment design: LoCoMo-Plus's cue → later-trigger structure, and Memora's
  obsolete-memory penalty (FAMA-style).
- ES-MemEval is a candidate external check after a licence review.
- Public suites evaluate the *retrieval architecture*, not personal correctness.
