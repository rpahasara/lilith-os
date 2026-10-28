# DEV release candidate `f293e72-f9c2-cog1-wm2`: World Model lane LIVE (CANDIDATE, not installed)

This release is `f293e72-f9c2-cog1-wm1` (installed and running on DEV since 2026-10-28, shadow acceptance PASS) with
the Slice 7.2 World Model lane switched from **shadow** to **live**, still for the `lilith_os` console only. Every
other lane stays off, and the router's own `mode` stays `shadow`, so there is no social switch to the Groq model. This
is step **B** of [`LIVE-WORLD-MODEL-PLAN.md`](../dev-f9c2-cog1-wm1/LIVE-WORLD-MODEL-PLAN.md) (PR #282). Nothing here
has been installed. The release does not touch the provider budget. At the last observation (2026-10-28) the DEV
provider gate was `BUDGET_EXHAUSTED`, which refuses provider calls locally. The budget reset is a separate Gate F
step (G2), and G1a must re-check the gate state.

## What changes against wm1

[`RELEASE-DELTA.json`](RELEASE-DELTA.json) lists the three members that change:

| Member | wm1 | wm2 |
|---|---|---|
| `RELEASE_ID` | `f293e72-f9c2-cog1-wm1` | `f293e72-f9c2-cog1-wm2` |
| `lilith_router/router.yaml` | `4035f0a1…`, `cognitive_mode: shadow` | [`home/router.yaml`](home/router.yaml) `47c487d6…`: `cognitive_mode: live`; everything else identical |
| `bin/verify_release.py` | wm1 template `b69b2344…` | [`templates/bin/verify_release.py.tmpl`](templates/bin/verify_release.py.tmpl) `60c91ad1…`: only the lane policy changes |

The governed adapter (draft and goal writes refused), the PROD Working Memory, the hardened gateway, the `lilith_os`
adapter, the provider gate, FORGET, and every other file are identical.

**The new start-time gate refuses unless all of these hold:**
- `cognitive_enabled` is exactly `true`, `cognitive_mode` is exactly `live`, and `cognitive_channels` is exactly
  `["lilith_os"]`;
- the router `mode` is exactly `shadow`;
- every other lane is `false`, and every other `*_mode` key is `shadow`.

It still pins the adapter and the PROD module. The wm1 gate refuses the wm2 router (`SHADOW_LANE_NOT_SHADOW`), and
the wm2 gate refuses the wm1 router (`WM_LANE_NOT_LIVE`), so neither release can start with the other's
configuration.

## What a live turn does (offline tests, every socket blocked)

The real DEV gateway and the governed adapter run in a fresh process on an assembled cog1 home with the exact wm2
`router.yaml`. A fake Core API stands in for `127.0.0.1:8765` ([`test_wm2_live.py`](tests/test_wm2_live.py)). The
real `services/core-api/app.py` also runs on a database shaped like F1's DEV findings
([`test_wm2_core_api_compat.py`](tests/test_wm2_core_api_compat.py)).

**The two planned G3 turns, against DEV's empty World Model:**

| Turn | Core API | Prompt suffix | Records |
|---|---|---|---|
| "what do you believe about application 999?" | exactly one `GET /os/world?entity_type=career.application&entity_id=999` (200 on the real Core API); no table or row changes | `FALLBACK_POLICY` + `WORLD MODEL BELIEFS (… showing 0 of 0 …)` / `(no beliefs are recorded for this focus)` | one `cognitive_mode: live` record (`belief: true`, `app_id: "999"`); no routing record for this turn, because a grounded turn returns before the routing decision |
| "hey how are you" (control) | none | none | the same routing record as wm1 |

The route and model are unchanged (`turn_route` passes through), and `force_rebuild` is set so the grounding applies.

**Other behaviour checked:**
- Only turns that the PROD detector matches change. Every other turn routes exactly as on wm1, with no Core API call.
- Beliefs are capped at 12 (`showing 12 of 20`), values are cut to 120 characters, and provenance shows only
  `source_class:source_id (freshness)`. `origin_ref` and `note` never appear.
- The grounding text never reaches the decision log, which holds flags and counts only.
- **Pending and draft turns read `/os/tasks` and `/os/drafts`.** On the real Core API, the first `/os/drafts` read
  creates the empty `drafts` table. Draft writes are refused (`writes_refused`), and the model is told that the draft
  was not saved. This is why G3 has no pending or draft turn.
- **The detector also treats "make a plan to follow up on application 999" as a draft request.** It attempts a
  refused write and reads `/os/drafts`. The kubernetes "pending" question is a pending-state question, and the
  salary/recruiter question is a belief question. G3 must use only the two messages above.
- If the Core API is unavailable, the turn is told so honestly ("temporarily unavailable … do not guess"). After one
  attempt, the 30 s breaker skips further reads.
- Other platforms (Telegram) get no grounding and no Core API call.
- Nothing under `HERMES_HOME` changes apart from the decision log. No memory, Privacy, learning or other lane module
  is imported.
- Restoring the wm1 router stops every read.

What reaches the provider on a live turn, where grounding can persist, and the stop conditions are in the plan (F1b,
F2 and G3–G5) and are not repeated here.

## Installing and rolling back (each step needs its own approval)

[`bin/install_wm2.sh`](bin/install_wm2.sh) is `install_wm1.sh` with the release step moved on. A test requires that
its body is `install_wm1.sh` with only these changes:
- ids and payload names renamed;
- the revert target is now wm1 (World Model shadow);
- the lane wording in the messages.

Its guard functions are the wm1 and cog1 ones verbatim:
- it holds the FORGET executor lock;
- it accepts only a fully stopped gateway;
- it uses a digest-pinned payload, render-on-host for the gate token, and staging quarantine;
- it reverts automatically after the first change if anything fails;
- the revert is idempotent;
- the `F8_SIM` guard applies.

The script never touches the provider budget.

| Step | Gate | Operation | Effect |
|---|---|---|---|
| G1a | A | read-only preflight (as the wm1 P0) | none |
| G1b | D | stop `hermes-gateway-dev` | console downtime starts |
| G1c | E | `install_wm2.sh install <payload>` (5 files: the wm2 and wm1 routers, the wm2 and wm1 verifier templates, `RELEASE_ID`) | stages `releases/f293e72-f9c2-cog1-wm2`, replaces `router.yaml`, switches `current`, re-pins, passes `verify --full` |
| G1d | D | `reset-failed` + start | the wm2 start-time gate runs; the World Model lane is live for `lilith_os`; while the gate stays `BUDGET_EXHAUSTED`, a console turn is refused locally before any provider call |
| G2 | F | budget reset (`gate_budget.sh reset --owner-approved "wm2-live-test"`) | not part of this release |
| G3–G5 | G, A | immediate F1 recheck, two `TEST_ONLY` turns, aggregate evidence | as in the plan |

**Rollback:** stop the gateway, run `install_wm2.sh revert <payload>`, then `reset-failed` + start.
- This restores the wm1 `router.yaml` (World Model shadow) and switches `current` back to wm1. wm1's own
  `verify --full` must pass.
- `install_wm1.sh revert` (its own payload) then goes back to cog1, with every lane off. The simulation runs both
  steps.
- Nothing in canonical memory, Privacy, authority, Core API data or provider state needs reverting.

**Dependency:** the wm2 venv resolves into `releases/f293e72-f9c2`, so **f9c2, cog1 and wm1 must all stay in place**
while wm2 is current.

## Tests

```bash
python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm2/tests -p "test_*.py"
sudo COG1_RUN_SIM=1 python3 -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm2/tests -p "test_*.py"
```

- **`test_wm2_live.py`:** the G3 turns and the live scope described above.
- **`test_wm2_core_api_compat.py`:** the G3 turns against the real Core API on a database shaped like DEV's. It is
  skipped when FastAPI is not installed.
- **`test_wm2_release.py`:** the release definition, the exact router and verifier diffs, and the wm1 and wm2
  verifiers run on the same fixture hosts. It checks acceptance, refusal of the wm1 and cog1 routers, a live router,
  other channels and any other lane, and that the adapter and PROD pins are kept.
- **`test_wm2_installer.py`:** payload pins, guards identical to wm1 and cog1, the body equal to `install_wm1.sh`
  apart from the release step, no service control, deletion or budget change, and the simulation.
- **`sim_install_wm2.sh`:** root, private namespace and overlays. It installs cog1 and then wm1 with the merged
  installers. It covers refusals, FORGET races, staging and revert failures, install, revert, and the second
  rollback to cog1.
