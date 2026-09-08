# Slice 9 — Reasoning Extraction V1 (Design Record)

> **Status:** Approved (Phase 1) · Phase 2 implementation record.
> **Target:** `lilith-01` backend, `~/.hermes/lilith_router/` + one minimal additive hook in `gateway/run.py`. No `app.py`/DB/frontend change.
> **Scope rule:** Reasoning is a bounded, tool-less cognitive component that *analyzes* — it never acts, mutates state, or gains permission. Planning is out of scope. Slice 10 NOT STARTED.

## 0. Principle
`Planner proposes · Policy governs · Connectors perform I/O · Verifier proves`. Reasoning sits **before** action: it interprets bounded cognitive context and returns typed proposals + explicit uncertainty. It has **zero** tool/connector/write/approval authority.

## 1. Current coupling (inspected, read-only)
The live Home/Telegram turn path is one method in `gateway/run.py`: `route_turn` hook (5764) → agent build (5786, `enabled_toolsets=ctx.enabled_toolsets` → **platform tools exposed**) → `run_conversation` (6457) → `final_response` (6515) → `enforce_reply`/social guard (6527). Reasoning today is emergent behavior of that single **tool-exposed** agent; the 7.2/8 lanes inject grounding but never revoke tools. A **tool-less, side-effect-free** bounded call already exists in production (`social_guard._default_regenerate`) using `AIAgent(..., skip_memory=True, skip_context_files=True, max_iterations=1)` — the extraction seam.

## 2. Chosen design (Option A)
A dedicated **tool-less Reasoning component** invoked by an additive reasoning lane (mirrors 7.2/8), returning a validated typed `ReasoningResult` whose natural `answer` is the user-facing reply; typed fields are logged as safe (non-CoT) trace. Integration via **one minimal additive fail-open short-circuit** in `run.py`: when `route_turn` returns a `final_response`, `run_sync` uses it as `result` **instead of** running the main agent — and it still flows through `enforce_reply` exactly as a normal final response (no parallel reply path, no guard bypass).

### run.py hook (exact, two narrow additive points; backed up)
- After the existing `route_turn` override block (~5785): `_reasoning_fr = _lr_res.get("final_response") if isinstance(_lr_res, dict) else None`.
- At the `run_conversation` call (6457):
  ```python
  if _reasoning_fr is not None:
      try:
          _rmsgs = list(agent_history) + [
              {"role": "user", "content": _api_run_message},
              {"role": "assistant", "content": _reasoning_fr}]
      except Exception:
          _rmsgs = []
      result = {"final_response": _reasoning_fr, "completed": True,
                "messages": _rmsgs, "api_calls": 0}
  else:
      result = agent.run_conversation(_api_run_message, **_conversation_kwargs)
  ```
  Fail-open: reasoning lane failure ⇒ no `final_response` key ⇒ `_reasoning_fr is None` ⇒ normal path. `messages` are supplied so the turn **persists** to session history like a normal turn (fail-safe to `[]` if history shape is unavailable). Normal non-reasoning turns are untouched.

## 3. Intent scope (conservative — Decision 2)
Reasoning V1 owns **new analytic framings only**: "what does the evidence imply / what is uncertain / why is X blocked / what could we do next / what information is missing / analyze the goal/situation". It runs **after** the 7.2 cognitive and 8 goal lanes in `_route_turn_impl`, so those accepted paths keep their intents. Defensive: `detect_reasoning_intent` yields (returns no-match) whenever the 7.2 `draft` intent or 8 `goal_create` intent is present — **explicit action requests never reach Reasoning** (Additional Requirement A).

## 4. `ReasoningInput` (bounded)
`{ schemaVersion, correlationId, timestamp, channel, userIntent, mode, relevantBeliefs[] (top-k: key,predicate,value,lifecycle,epistemic,confidence,provenanceRefs), workingMemorySummary, currentGoal?, currentFocus?, goalCandidates[], relevantTasks[], relevantDrafts[], policyVisibleConstraints[], capabilityAvailabilitySummary?, conversationSummary?, explicitUserConstraints? }` — bounded only; no raw DB/session/memory dump; provenance by ref; UNKNOWN/STALE/CONFLICTED preserved; no mutable handles.

## 5. `ReasoningResult` (typed, non-CoT)
`{ schemaVersion, correlationId, mode, outcome (OK|INSUFFICIENT_EVIDENCE|CONFLICTED|ERROR), interpretation, answer (natural), assumptions[], evidenceRefs[], uncertainties[], conflicts[], blockingConditions[], candidateNextSteps[], answerIntent?, escalationNeeded?, informationNeeded[], confidenceBasis, traceMetadata }`. **No** scratchpad/thinking/token-level text. `CandidateNextStep { type, description, target?, rationaleSummary, requiredCapabilities[], requiresApproval, blockedBy[] }` — proposals only; never executed.

## 6. Decision 4 — persona separation
`load_soul_identity=True` (natural cross-channel voice). Persona may shape **only** the wording of `answer`. All typed fields (evidenceRefs, assumptions, uncertainties, conflicts, blockingConditions, candidateNextSteps, requiredCapabilities, requiresApproval, confidenceBasis, epistemic interpretation, policy-visible constraints) are **evidence-grounded and persona-neutral** — the prompt states this explicitly and the deterministic parts (beliefs/goal blockers/policy constraints) are carried from data, not generated.

## 7. No-tool guarantee (Additional Requirement B)
Primary boundary: **`enabled_toolsets=[]`** ⇒ zero tool schemas in the model request. Secondary bounds: `skip_memory=True`, `skip_context_files=True`, `max_iterations=1`. Tests prove: the reasoning call passes `enabled_toolsets=[]`, `skip_memory=True`, `skip_context_files=True` (offline, mocked AIAgent capturing kwargs), and a live check confirms the constructed agent exposes zero tool schemas. `max_iterations=1` is NOT treated as the tool-isolation mechanism.

## 8. World / Executive / Policy relationships
Read-only beliefs (lifecycle/epistemic/provenance/confidence; UNKNOWN→insufficient, STALE→flag, CONFLICTED→surface, VERIFIED→top authority); never reconciles/writes. Reads Executive goals/focus; explains blocked/focus/options; never activates/completes/blocks/creates/reprioritizes. Names policy-visible constraints (send requires approval; connector unavailable; prohibited) but makes **no** final permission decision — the existing approval-gated draft path stays authoritative.

## 9. Trace / durability / failure
Safe non-CoT trace to `decisions.log` (correlation, mode, counts, answer_intent, model id, duration, success/fallback). **Full `ReasoningResult` ephemeral; no DB/table, no reasoning corpus.** Failure (context/model/parse/schema/timeout) ⇒ lane returns `None` ⇒ normal existing path answers ⇒ never fabricates state/action.

## 10. Files (Phase 2)
NEW `lilith_router/reasoning.py`, `lilith_router/tests/test_reasoning.py`. EDIT `world_context.py` (detect_reasoning_intent + build_reasoning_input), `gateway_integration.py` (reasoning lane + `_log_reasoning`), `config.py` + `router.yaml` (`reasoning_enabled`/`reasoning_mode`, channels reuse `cognitive_channels`), one hook in `gateway/run.py`. Backups per file. One gateway restart. No `daemon-reload`.

## 11. Tests (A–V + additions)
A bounded input · B beliefs carry epistemic state · C goal read-only · D no raw dump · E `enabled_toolsets=[]`/skip_memory/skip_context_files · F no connector call · G no goal mutation · H no world mutation · I valid JSON parses · J malformed rejected→fail-safe · K/L/M UNKNOWN/STALE/CONFLICTED preserved · N candidate steps proposal-only · O policy approval constraint represented · P failure→no side effect+fall-through · Q Home/Telegram parity · R 7.2 intact · S 8 intact · T explicit draft path unchanged · U classifier/social_guard green · V frontend 67/67. Plus: action-precedence (draft/goal-create not intercepted), symbol-absence (no tool/connector/write imports in reasoning.py), no-CoT (no scratchpad field).

## 12. Live acceptance
1. "What do we know about application 14, and what is uncertain?" 2. "Why can't you follow up on application 14 right now?" 3. "What could we do next for application 14?" 4. "Which goal deserves attention and why?" 5. "Create a follow-up draft for application 17, but do not send it" (stays on existing durable-action path). Home + Telegram semantically equivalent. No external send.

## 13. Rollback / gaps
`reasoning_enabled: false` (no restart) disables the lane; or restore `.bak` files (incl. run.py) + one gateway restart. Zero durable footprint. **Known V1 gap:** if history-shape reconstruction fails, a reasoning turn is answered but not persisted (fail-safe branch); reasoning reads durable state so this is low-impact. **Slice 10 (Global Workspace): NOT STARTED.**
