# DEV release candidate `f293e72-f9c2-cog1-wm1-g2`: Goals LIVE, World Model shadow (CANDIDATE, not installed)

This release is `f293e72-f9c2-cog1-wm1-g1`, which is installed on DEV with Goals shadow accepted on 2026-10-30
([`../dev-f9c2-cog1-wm1-g1/ACCEPTANCE-20261030.md`](../dev-f9c2-cog1-wm1-g1/ACCEPTANCE-20261030.md)). It switches
**only** the Slice 8 Goals/Executive lane to **live**, for the `lilith_os` console only. The World Model lane stays in
**shadow**, and every other lane stays off. Nothing here has been installed. Merging this PR deploys nothing: every
change is a new file under `integrations/hermes/`.

## What changes against g1

[`RELEASE-DELTA.json`](RELEASE-DELTA.json) lists the three members that change:

| Member | g1 | g2 |
|---|---|---|
| `RELEASE_ID` | `f293e72-f9c2-cog1-wm1-g1` | `f293e72-f9c2-cog1-wm1-g2` |
| `lilith_router/router.yaml` | `d931f1b6…`, Goals `shadow` | [`home/router.yaml`](home/router.yaml): `goals_mode: live`; everything else identical |
| `bin/verify_release.py` | g1 template `839a52b8…` | [`templates/bin/verify_release.py.tmpl`](templates/bin/verify_release.py.tmpl): the lane policy and a goal-schema requirement |

The governed adapter (`07a763e1…`), the PROD Working Memory (`46b8187e…`), the hardened gateway (`5ce4bbd4…`), the
`lilith_os` adapter, the provider gate, FORGET and every other file are identical.

**The start-time gate refuses unless all of these hold:**
- **Lanes:** `cognitive_enabled` and `goals_enabled` are exactly `true`; `cognitive_mode` is exactly `shadow` and
  `goals_mode` exactly `live`, with case and presence enforced.
- **Channels:** `cognitive_channels` and `live_channels` are exactly `["lilith_os"]`.
- **Router mode:** the router's own `mode` is `shadow`.
- **Everything else:** every other lane is `false`, and every other `*_mode` key is `shadow`.
- **Keys:** `router.yaml` holds no key the router does not read. The allowlist is tested against `config.py`.
- **Goal schema:** the `goal` and `goal_trace` tables must **already exist** in the DEV DB
  (`/home/lilith/.hermes/lilith-os-dev/data/lilith-dev.db`) with exactly the Slice 8 columns. The check is
  read-only (`mode=ro`, `PRAGMA table_info` only) and never creates anything. Otherwise the gate fails with
  `GOAL_SCHEMA_NOT_BOOTSTRAPPED`, `GOAL_SCHEMA_MISMATCH`, `GOAL_DB_MISSING` or `GOAL_DB_UNREADABLE`.

The gate also still pins the adapter and the PROD module. The installed g1 verifier refuses this router, and this
verifier refuses the g1 router.

## Goals live boundaries (from source; each proven offline against the real Core API code)

| Boundary | Behaviour | Control |
|---|---|---|
| **Schema bootstrap** | Core API `_goals_db()` runs `CREATE TABLE IF NOT EXISTS goal / goal_trace` (and 6 indexes) on its first goal request per process. On today's DEV DB, which has no goal tables, the first live read would therefore be a **schema change caused by a GET** (contrast test) | A **separate, owner-approved goal-schema bootstrap gate** must create the tables first. g2's verifier then refuses to start without them. The installer itself never touches the DB: the simulation proves an install on a DB without the tables fails at `verify --full`, reverts to g1 automatically and leaves the DB byte-identical |
| **Focus trace** | `GET /os/goals/focus` writes one `goal_trace` `arbitration` row **only when the computed focus changes**. With 0 goals the focus is `None`, as before, so nothing is written. With one goal, the first read writes exactly 1 row and later reads write nothing | Accepted Slice 8 audit behaviour. An empty-store live window writes nothing; a populated synthetic test needs a cleanup gate |
| **Reads per goal turn** | exactly `GET /os/goals?limit=200` and `GET /os/goals/focus`. A "track as a goal" turn first tries `GET /career/applications` for the title (500 on DEV, where the career tables are absent) | The adapter allowlist allows GET only, at most 16 reads per call, with a 30 s breaker. An unrelated turn makes 0 reads |
| **Unauthorized goal creation** | Core API `POST /os/goals` has no caller authentication or approval gate | The governed adapter **never sends** `POST /os/goals` (`writes_enabled` false; `writes_refused` counted). The turn tells the user it "could not track the goal". Proven: 0 goal rows after create turns |
| **Provider exposure** | A live goal turn appends `GOAL_POLICY` plus the durable goal state (titles, lifecycle states, priorities, focus and arbitration text) to that turn's prompt, which goes to the provider through the DEV gate | Empty or synthetic store only, until the owner decides goal content may reach the provider. The grounding is ephemeral (not persisted to `system_prompts`), and request dumps are content-free (F9-B) |
| **Retention and FORGET** | `goal` and `goal_trace` rows live in `lilith-dev.db` and are **not** covered by the 7-day retention or by FORGET. Session data and decision records are covered | With creation disabled, rows can come only from an approved synthetic seed and must be removed by an approved cleanup. Real goals need a FORGET/retention decision first |
| **Decision log** | the goal record stays content-free in live mode (`goal_mode: live`, intent flags, sizes) | Tested: no message text |
| **Detector false positives** | the PROD detector treats casual prose ("my goal for the weekend is to relax") as a goal query. In live mode that turn makes the 2 reads and receives goal grounding; it never writes | Known limitation, accepted in shadow. Review the live window with it in mind; no detector change in this release |

## Operational order (each step needs its own approval; nothing here authorizes it)

1. **G-S goal-schema bootstrap gate.** This is a DB change:
   - root-only backup;
   - run the pinned Core API's own `_goals_db()` in an isolated interpreter;
   - prove that only the goal tables and indexes were added, with 0 rows;
   - record the new reference fingerprint;
   - dispose of the backup separately.

   g2 cannot start before this.
2. **Provider decision:** whether goal content may reach the provider (empty and synthetic only, until decided).
3. **Budget:** DEV is **5/5 exhausted**. A live window needs an approved `gate_budget.sh reset --owner-approved`, for
   example 2 requests: one empty-state goal query and one control.
4. **Window, as the wm2 W1–W7 window:**
   - P0;
   - stop g1;
   - `install_g2.sh install`;
   - start;
   - the turns;
   - stop;
   - `install_g2.sh revert` (back to g1);
   - start;
   - read-only checks.

[`bin/install_g2.sh`](bin/install_g2.sh) is the merged `install_g1.sh` moved one release step (base and revert target
g1). A test checks this line by line. Its guard functions are the g1, wm2, wm1 and cog1 ones verbatim:
- FORGET executor lock;
- fully stopped gateway;
- pinned payload;
- render-on-host for the gate token;
- staging quarantine;
- automatic revert after the first change;
- idempotent revert;
- the `F8_SIM` guard.

**Rollback:**
- **g2 → g1:** `install_g2.sh revert`.
- **g1 → wm1:** `install_g1.sh revert`.
- **wm1 → cog1:** `install_wm1.sh revert`.

The simulation exercises all three. **Dependency:** f9c2, cog1, wm1 and g1 must stay in place while g2 is current.

## Tests

```bash
python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g2/tests -p "test_*.py"
sudo COG1_RUN_SIM=1 python3 -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g2/tests -p "test_*.py"
```

- **`test_g2_release.py`:**
  - the release definition and the exact router and verifier diffs;
  - the goal-schema constant equal to the Core API DDL, and the router-key allowlist;
  - g1 and g2 verifiers on fixture hosts: acceptance on a bootstrapped DB;
  - refusal of a DB without the goal tables (with the check proven to create nothing and leave no journal), a drifted
    schema, a missing or corrupt DB, the g1 router, missing, uppercase or unknown modes, World Model live, `*`,
    Telegram, Discord, chat-scoped and separate channels, unknown or misspelt keys, router live mode and every other
    lane.
- **`test_g2_core_api_compat.py`** (the real `services/core-api/app.py` behind the adapter transport; HTTP 500s pass
  through as on uvicorn):
  - empty store: exactly 2 reads, honest "no goals / focus none" grounding, schema and rows unchanged, content-free
    `goal_mode: live` record;
  - "track as a goal": GET only, POST never sent, 0 goals;
  - an unrelated turn: 0 reads;
  - the casual-prose false positive: reads only;
  - pre-bootstrap contrast: the first read creates the tables;
  - one synthetic goal: the first focus read writes exactly 1 trace row, the second none.
- **`test_g2_live.py`** (the real gateway and adapter, sockets blocked):
  - non-goal routing and logs identical to g1; goal turns `live`, with only allowlisted reads and no writes;
  - creation refused; no message text; no other lane or memory module; no `HERMES_HOME` change;
  - Telegram ignored; router revert restores g1 shadow.
- **`test_g2_installer.py`:**
  - payload pins; guards identical to g1, wm2, wm1 and cog1;
  - the text equal to `install_g1.sh` apart from the release step;
  - no service control, deletion, DB, DDL, budget or Core API access.
- **`sim_install_g2.sh`** (root, private namespace and overlays):
  - builds cog1, then wm1, then g1 with the merged installers;
  - an install without the goal schema fails closed and reverts, with the DB untouched;
  - after a bootstrap stand-in: refusals, FORGET races, staging and revert failures, install, revert, and the
    further rollbacks to wm1 and cog1.
