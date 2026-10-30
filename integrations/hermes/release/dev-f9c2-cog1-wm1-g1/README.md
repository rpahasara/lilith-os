# DEV release candidate `f293e72-f9c2-cog1-wm1-g1`: World Model and Goals lanes in shadow (CANDIDATE, not installed)

This release is `f293e72-f9c2-cog1-wm1`, which is installed and running on DEV. It keeps the Slice 7.2 World Model lane
in **shadow** and turns on **one more** lane: the Slice 8 Goals/Executive lane, also in **shadow**, for the
`lilith_os` console only. Every other lane stays off. Nothing here has been installed, and the live router
configuration is unchanged.

## What changes against wm1

[`RELEASE-DELTA.json`](RELEASE-DELTA.json) lists the three members that change:

| Member | wm1 | g1 |
|---|---|---|
| `RELEASE_ID` | `f293e72-f9c2-cog1-wm1` | `f293e72-f9c2-cog1-wm1-g1` |
| `lilith_router/router.yaml` | `4035f0a1…`: World Model shadow, Goals off | [`home/router.yaml`](home/router.yaml): `goals_enabled: true`, `goals_mode: shadow`; everything else identical |
| `bin/verify_release.py` | wm1 template `b69b2344…` | [`templates/bin/verify_release.py.tmpl`](templates/bin/verify_release.py.tmpl): only the lane policy changes |

The governed adapter, the PROD Working Memory, the hardened gateway, the `lilith_os` adapter, the provider gate,
FORGET, and every other file are identical. The Goals lane has no channel setting of its own: it uses
`cognitive_channels`, which stays `["lilith_os"]`.

**The new start-time gate refuses unless all of these hold:**
- `cognitive_enabled` and `goals_enabled` are each exactly `true`;
- `cognitive_mode` and `goals_mode` are each present and exactly `shadow`;
- `cognitive_channels` and `live_channels` are each exactly `["lilith_os"]`;
- the router's own `mode` is `shadow`;
- every other lane is `false`, and every other `*_mode` key is `shadow`;
- `router.yaml` holds no key that the router does not read. This catches a misspelt lane or mode, which the router
  would otherwise silently default. A test checks the allowlist against `lilith_router/config.py`.

The gate still pins the adapter and the PROD module. A live mode, `*`, Telegram, a chat-scoped channel, a separate
channel list, or any other lane stops the gateway from starting. The installed wm1 verifier refuses this router
(`LANE_NOT_OFF goals_enabled`), and this verifier refuses the wm1 router.

## Why Goals shadow touches no data

In shadow, the DEV gateway's goal branch does exactly two things:
1. it runs the recovered PROD `detect_goal_intent`, which is pure regular-expression matching;
2. it appends one decision-log record.

Goal grounding, `GET /os/goals`, `GET /os/goals/focus`, goal creation and the model are reached only in **live** mode.
That matters on DEV. The Core API's `_goals_db()` creates the `goal` and `goal_trace` tables on its first use in a
process, and those tables are absent from the DEV database. `GET /os/goals/focus` also writes a `goal_trace`
arbitration row whenever the chosen goal changes. With no request sent, neither can happen.

| Effect (offline tests: real gateway and adapter; real Core API source for the last two rows) | Measured |
|---|---|
| Core API reads, including `/os/goals` and **`/os/goals/focus`** | **0** |
| Core API writes; goal creation attempts | 0 and 0. Even a "track that as a goal" turn attempts nothing |
| Model or provider calls, network connections | 0 |
| User-visible routing | identical to wm1 for every test message |
| World Model shadow records and routing records | identical to wm1 |
| Other lanes, canonical memory, Privacy and learning modules | not imported, not run |
| Files under `HERMES_HOME` | none changed apart from the decision log |
| Other platforms (for example Telegram) | not observed |
| Real Core API, DEV database shape: schema and rows | unchanged; `goal` and `goal_trace` stay absent; `_goals_db()` never runs |
| Contrast: the same turn with `goals_mode: live` (test-only copy) | reads `/os/goals` and `/os/goals/focus` and **creates both goal tables**. This is why live Goals is out of scope here |

## Decision-log records, retention and redaction

**Records added.** One record per `lilith_os` turn that the PROD goal detector matches. In the tests, 6 of 13 varied
messages matched. One of them is casual prose ("my goal for the weekend is to relax"), which the detector treats as a
goal query. In shadow that only adds a record. In live it would add goal grounding, so it is something for the live
review. Each record's fields are fixed by the reviewed DEV gateway:
- `platform`, `chat_id`;
- `lane: goal`, `goal_mode: shadow`;
- `intent`: `goal_query`, `goal_create`, `app_id` (a digit string such as `"14"`, or null), and `subtype` (one of
  `general`, `why_blocked`, `blocked`, `priority`, `resume`, `active`);
- `msg_chars`, `msg_lines`, `event_id` (random), `ts`.

**What the records never contain:** message text, Core API data, memory content or the model reply. The tests check
this with canary text and message-only words, and they check that every string value is a short label.

**Rules:** the existing wm1 rules apply unchanged:
- **Retention:** 7 days, via `hermes-gateway-dev-retention.timer`.
- **FORGET:** the executor purges `HERMES_HOME/logs`.
- **Handling:** the records are treated as conversation metadata.
- **Observation:** counts and flags only; the log never leaves the host.

## Provider data and budget

Goals shadow sends nothing new to any model provider. It makes no model call and adds nothing to
`combined_ephemeral`. The installer neither touches the provider gate nor resets the budget; a test refuses
`gate_budget` and `reset` in its code. Live Goals would put goal state into the prompt, which is a separate decision
that this verifier refuses.

## Installing and rolling back (each step needs its own approval)

[`bin/install_g1.sh`](bin/install_g1.sh) is the merged `install_wm2.sh`, which has the same base (wm1) and the same
revert target, with only the release step renamed. A test checks this line by line. Its guard functions are the
wm2, wm1 and cog1 ones verbatim:
- it holds the FORGET executor lock;
- it accepts only a fully stopped gateway;
- it uses a digest-pinned payload, render-on-host for the gate token, and staging quarantine;
- it reverts automatically after the first change if anything fails;
- the revert is idempotent;
- the `F8_SIM` guard applies.

| Step | Gate | Operation | Effect |
|---|---|---|---|
| 1 | A | read-only preflight (as the wm1 P0) | none |
| 2 | D | stop `hermes-gateway-dev` | console downtime starts |
| 3 | E | `install_g1.sh install <payload>` (5 files: the g1 and wm1 routers, the g1 and wm1 verifier templates, `RELEASE_ID`) | stages `releases/f293e72-f9c2-cog1-wm1-g1`, replaces `router.yaml`, switches `current`, re-pins, passes `verify --full` |
| 4 | D | `reset-failed` + start | the g1 start-time gate runs; both shadow lanes are active in the process |
| 5 | A | read-only post-start check, then a bounded shadow window (provider gate refusing locally, as the wm1 shadow test) | record counts and flags only |

**Rollback:** stop the gateway, run `install_g1.sh revert <payload>`, then `reset-failed` + start.
- The revert restores the wm1 `router.yaml` (World Model shadow, Goals off) and switches `current` back to wm1.
- wm1's own `verify --full` must pass.
- No memory, Privacy, authority, Core API or provider state is involved.
- `install_wm1.sh revert` remains the second step back, to cog1 (every lane off). The simulation exercises both.

**Dependency:** the g1 venv resolves into `releases/f293e72-f9c2`, so **f9c2, cog1 and wm1 must all stay in place**
while g1 is current. The two inert retired wm2 copies and the wm2 release are not touched.

## Tests

```bash
python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g1/tests -p "test_*.py"
sudo COG1_RUN_SIM=1 python3 -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g1/tests -p "test_*.py"
```

- **`test_g1_shadow.py`:** the real gateway and adapter on an assembled cog1 home, in a fresh process with sockets
  blocked. It covers:
  - one content-free goal record per detected goal turn, including create and query;
  - routing parity and unchanged World Model records;
  - zero Core API and provider traffic, and no write attempt;
  - no message text in the log;
  - no other lane or memory module, and no `HERMES_HOME` change;
  - other platforms ignored, and router revert.
- **`test_g1_core_api_compat.py`:** the real `services/core-api/app.py` behind the adapter's transport, on the DEV
  database shape. Goal turns in shadow make no request and change no schema or row; the live contrast creates the goal
  tables.
- **`test_g1_release.py`:** the release definition, the exact router and verifier diffs, and the router-key allowlist
  against `config.py`. It runs the wm1 and g1 verifiers on the same fixture hosts and covers acceptance, plus refusal
  of the wm1 router, live modes, missing or empty modes, other channels, unknown keys, router live mode and every
  other lane. It also checks that the adapter and PROD pins are kept.
- **`test_g1_installer.py`:** payload pins; guards identical to wm2, wm1 and cog1; the text equal to `install_wm2.sh`
  apart from the renames; no service control, deletion, database or budget access; and the simulation.
- **`sim_install_g1.sh`:** root, private namespace and overlays. It installs cog1 and then wm1 with the merged
  installers, then covers refusals, FORGET races, staging and revert failures, install, revert, and the second
  rollback to cog1.
