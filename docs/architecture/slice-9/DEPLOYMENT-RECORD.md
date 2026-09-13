# Slice 9 — Reasoning Extraction V1 · Deployment Record (PASS)

**Date:** 2026-09-08 · **Target:** `lilith-01` backend + one minimal `gateway/run.py` hook. No `app.py`/DB/frontend change.

## Starting hashes (pre → post; sha256 prefixes) · backups `.bak.20260908-141508`
| File | pre | post |
|---|---|---|
| `gateway/run.py` | `dba8b053183a1c01` | `2774eee5e585d80c` |
| `lilith_router/config.py` | `09906dac04ee459e` | `0572d9add5b3489c` |
| `lilith_router/gateway_integration.py` | `3d1e7a1b7ee8e489` | `92c01c49252ef2be` |
| `lilith_router/world_context.py` | `673edebddbadcd19` | `1a6724daff499164` |
| `lilith_router/router.yaml` | `4c9865aa91f3e9fb` | (appended) |
| `lilith_router/reasoning.py` | (new) | `57284ff2425d3fb8` |

## Files changed (all additive)
- **NEW** `reasoning.py` — ReasoningInput/Result contract, stdlib validator, `REASONING_SYSTEM` prompt, tool-less model call (`enabled_toolsets=[]`, `skip_memory`, `skip_context_files`, `max_iterations=1`, `load_soul_identity=True`); Hermes internals lazy-imported; `_resolve_model`/`_resolve_kwargs`/`_construct_agent` injectable.
- **EDIT** `world_context.py` — `detect_reasoning_intent` (analytic framings only; yields to 7.2 draft/pending + 8 goal_create/goal_query) + `build_reasoning_input` (bounded; provenance by ref; epistemic preserved).
- **EDIT** `gateway_integration.py` — reasoning lane in `_route_turn_impl` (before 7.2/8 but yields to them; records WORK; returns `{"final_response": answer}`) + `_log_reasoning`.
- **EDIT** `config.py` + `router.yaml` — `reasoning_enabled`/`reasoning_mode`, channels reuse `cognitive_channels`.
- **EDIT** `gateway/run.py` — see below.

## Exact run.py hook (minimal, additive, fail-open)
After the existing router override block (~5786): `_reasoning_fr = _lr_res.get("final_response") if isinstance(_lr_res, dict) else None`.
At the `run_conversation` call (~6457):
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
**Proof social_guard remains downstream:** the hook sets `result` at ~6457; the method then extracts `final_response = result.get("final_response")` (~6515) and calls `final_response = enforce_reply(final_response, ctx)` (~6527). The reasoning answer therefore passes through `enforce_reply` exactly as a normal (WORK-mode) final response — it is delivered intact (not a parallel reply path). Normal turns are untouched; a reasoning-lane failure yields no `final_response` ⇒ `_reasoning_fr is None` ⇒ the normal agent runs (fail-open).

## No-tool proof (live)
Constructed the real reasoning agent: `enabled_toolsets=[]`, `disabled_toolsets=None`, `skip_memory=True`, `skip_context_files=True`, `max_iterations=1`, prompt is `REASONING_SYSTEM`; agent tool containers all empty (`tools=0`, `valid_tool_names=0`, `enabled_toolsets=0`, `_context_engine_tool_names=0`). Zero tool schemas. Offline tests additionally capture the construction kwargs.

## Tests
reasoning **18/18** · classifier **18/18** · social_guard **34/34** · world_context all · goal_context **9/9** · frontend core **67/67**. (app.py/DB untouched → Slice 8 goal store + backend suites unaffected.)

## Live acceptance (PASS, Home `/os/conversation`; lane routing from decisions.log)
- "What could we do next for application 14?" → `lane: reasoning` OPTION_GENERATION — approval-gated proposals (reconcile drafts), no send.
- "What do we know about application 14, and what is uncertain?" → `lane: reasoning` UNCERTAINTY_ANALYSIS — facts vs explicit unknowns.
- "Why can't you follow up on application 14 right now?" → `lane: reasoning` BLOCKER_ANALYSIS — two unsent drafts + approval/connector/prohibited constraints, no mutation.
- **Action precedence:** "Create a follow-up draft for application 17, but do not send it" → `lane: cognitive` (draft, app 17) — reasoning YIELDED; no 3rd draft, both existing drafts listed, nothing sent.
- "Which goal deserves attention and why?" → `lane: goal` (Slice 8) — respects Executive focus (app 17).
- Regression: "What do you know about application 14?" → `lane: cognitive` (Slice 7.2 intact).

## Telegram parity
`reasoning_is_live` True for lilith_os and telegram; `build_reasoning_input` produces identical bounded durable core (beliefs/focus/goals/policy) for home vs telegram.

## Deploy / rollback
One gateway restart (PID 225891, NRestarts=0); flag flips per-turn (no restart); **no `daemon-reload`**. Rollback: `reasoning_enabled: false` (no restart) or restore `.bak.20260908-141508` (incl. run.py) + one gateway restart.

## Known gap
If turn-history reconstruction fails in the short-circuit, a reasoning turn is answered but not persisted (fail-safe branch); low impact (reasoning reads durable state). **Slice 10 (Global Workspace): NOT STARTED.**
