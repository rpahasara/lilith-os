# Dependencies for Reasoning Live, Workspace Live, Motivation and Planning (ANALYSIS, nothing activated)

Based on the recovered PROD code in Git. Line references are to `home/variants/dev-f9c2/lilith_router/gateway_integration.py`.

## Finding that shapes everything

**`reasoning.py`, `motivation.py` and `planning.py` are not installed on DEV.** They exist in Git only under
`docs/architecture/slice-9`, `-11` and `-12`. The gateway imports them lazily (`from . import reasoning`), so turning a lane on without
shipping the file fails open silently: a lane can look enabled and do nothing. Each needs to be a release member with a digest and a
verifier check.

## Reasoning Live

| Dependency | State |
|---|---|
| Module shipped | no |
| Model path | `run_reasoning` resolves the gateway model and builds an agent. Must be proven to go through the gate, count against budget, and have no tools |
| **Extra provider call** | a live match makes its own call and, if valid, returns as the turn's answer, skipping the main agent (line 549). If invalid it falls through, so **one turn can cost 2 requests** |
| Detector | recall is poor: 1 of 20 red-team paraphrases. Measure on real shadow records first; a rule list may not be enough |
| Input data | `select_reasoning_input_m` reads goals, world, tasks and drafts, so **provider exposure is wider than Goals**: a new owner decision |
| Governed reads | the adapter allow-list and budget must fit the read set |
| Drafts schema | required |
| Retention and FORGET | goal rows must be covered first if any real goal is present |
| Answer safety | `final_response` still passes `enforce_reply`. Needs a test that the reply claims no action |

**Order:** detector on real records, ship module, synthetic-only live window, then provider decision for real data.

## Workspace Live

| Dependency | State |
|---|---|
| Workspace shadow accepted | not yet: needs #295 and the counts-only trace in the release |
| Runs only inside Reasoning | Workspace live only changes `select_reasoning_input_m`'s input, so **it has no effect without Reasoning Live** |
| Goal store | the w1 verifier refuses goals, because a focus read writes a trace. Must be redesigned before Workspace runs with any goal |
| Empty-store limit | shadow on empty stores shows plumbing, not salience quality. Needs synthetic populated data |

**Order:** Workspace Live comes after Reasoning Live, and cannot be tested usefully before it.

## Motivation

Recovered: `build_motivation_snapshot`, `motivation_candidates`, `select_reasoning_input_m`. Deterministic, ordinal, no writes.

**Design:** shadow ships as one release after Workspace shadow. Enable `motivation_enabled` in shadow. It only acts inside the Reasoning and
Planning branches (lines 408 to 411), so it inherits their detector.

| Concern | Plan |
|---|---|
| Reads | the snapshot reuses goal and task reads. Measure the count offline before release |
| Record | must be counts and classes only, as with the trace candidate. Check for ids |
| Live | adds candidates to Workspace, so it depends on Workspace Live |
| Module | `motivation.py` must be a release member |

## Planning

Recovered: `detect_planning_intent`, `build_planning_input`, `run_planning`. Proposal-only.

**Shadow is not like the other lanes.** At lines 421 to 432 the planning path builds the input and calls `run_planning` even in shadow, so a
match makes durable-state reads. The gateway passes no `model_call`, and `run_planning` then uses only `deterministic_template`, so the
code shows no model call in shadow. A release test must pin that, because `planning.py` also holds an LLM path.

| Concern | Plan |
|---|---|
| Priority | it runs before Reasoning, so its detector needs the same hardening review |
| Reads | `build_planning_input` reads durable state on every match |
| Live | a successful result becomes the turn's answer. Proposal-only must be tested: no task, draft or goal writes |
| Module | `planning.py` must be a release member |

## Recommended sequence

1. G3, or skip it.
2. `drafts` gate.
3. Combined release: detector candidate plus Workspace shadow with counts-only trace.
4. Collect real shadow records; decide on the detector.
5. Motivation shadow, then Planning shadow, each proven to spend nothing.
6. Write authentication, FORGET and retention before any real goal.
7. Reasoning Live on synthetic data, then Workspace Live.

Steps 1 to 5 need no real goal data. Step 6 must finish before real goals are stored.
