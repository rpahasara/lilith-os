# Cognitive evaluation tools (P-1)

Small, standard-library tools from roadmap P-1 ([tasks](../../docs/research/cognitive-rd-plan-2026-11/13-p1-implementation-tasks.md)).
None makes a model call except `replay.py`, and none writes to LILITH's state.

| Tool | Task | Runs on | Does |
| --- | --- | --- | --- |
| `trace_summary.py` | T-3 | the LILITH host, as the log owner | Read-only aggregates of `decisions.log`: turns, lanes, routes, answered-by, models, fallback / guard / D1 rates, tokens, latency p50/p95, tone keys. Prints only counts and allow-listed labels, never free text |
| `replay.py` | T-4 | the LILITH host, as `lilith` | Offline A/B replay of the lean reply (`mode: lean`) or the full agent without tools (`mode: agent`) for synthetic scenarios. No session DB, memory or tools. Token budget per run (≤50K by default) |
| `blind.py` | T-5 | anywhere | `make` builds a blind sheet, a sealed key and a verdict template; `score` joins the owner's 1–5 ratings with the key and reports per-arm means, scenario wins, ties and skips |
| `scenarios/` | — | — | Small focused **synthetic** scenario sets. `social_tone_v1.json` is the 14-scenario set from the 2026-11-07 tone-note A/B |

**Rules:**
- Synthetic scenarios only.
- Never commit blind sheets, keys, verdicts or raw replies; they stay with the operator.
- Start with 5–10 scenarios per experiment and grow only when the evidence warrants it (P-1 owner clarification).
- Getting the scripts onto the host is operator-local (the SSH transport is not in this repository).
