# PROD `lilith-01` Router V2 variant

Files that exist only in the PROD deployment of Router V2. Everything PROD shares with DEV, or that is already tracked
elsewhere, is referenced from [`../../MODULES.json`](../../MODULES.json) instead of copied.

On 2026-10-27, a bounded read-only export recovered the files below from `lilith-01`. Each was hash-verified against
the read-only PROD audit of the same day. [`PROD-RECOVERY.json`](PROD-RECOVERY.json) maps every recovered file to its
full SHA-256. Together with `MODULES.json`, it forms the complete deployed `lilith_router` tree.
[`tools/assemble_prod_complete.py`](../../tools/assemble_prod_complete.py) builds that tree and checks every byte.

**This is historical deployed source, not active code.** Nothing installs or runs it. DEV keeps its own 723-byte
`world_context.py` stub and its shadow `router.yaml`, with every lane off. Enabling any lane anywhere is separate,
approved work.

## `lilith_router/world_context.py`: Working Memory and the seven-lane wiring

The file is 91,351 bytes, SHA-256 `46b8187e3f6f2ac72c920de9dab12fd9c2841551f6c2aa7c20fd91941e3f0104`, byte-exact.

It assembles each turn's grounded Working Memory and builds the inputs every cognitive lane consumes. PROD's
`gateway_integration.py` calls it (`variants/prod-lilith-01/lilith_router/gateway_integration.py`):

| Lane (slice) | Functions in `world_context.py` | Lane module it hands off to |
|---|---|---|
| World Model grounding (7.2) | `detect_intent`, `fetch_world`, `build_belief_block`, `build_pending_block`, `build_grounding`, follow-up drafts | Core API `GET /os/world`, `GET /os/tasks`, `GET\|POST /os/drafts`, `GET /career/applications` |
| Goals / Executive (8) | `detect_goal_intent`, `fetch_goals`, `build_goal_block`, `build_goal_grounding`, `create_tracking_goal` | Core API `GET /os/goals`, `GET /os/goals/focus`, `POST /os/goals` |
| Reasoning (9) | `detect_reasoning_intent`, `build_reasoning_input` | `reasoning.py` (called from `gateway_integration`) |
| Global Workspace (10) | `build_attention_candidates`, `build_reasoning_input_bounded`, `select_reasoning_input` | `workspace.py` (called from `gateway_integration`) |
| Motivation (11) | `build_motivation_snapshot`, `motivation_candidates`, `motivation_trace`, `select_reasoning_input_m` | `motivation.py` (lazy import) |
| Planning (12) | `detect_planning_intent`, `build_planning_subject`, `build_planning_input`, `planning_trace` | `planning.py`, `planning_capabilities.py` (lazy import) |
| Ethics (13) | `detect_ethics_intent`, `build_turn_evidence`, `build_ethical_input`, `ethics_trace` | `ethics.py` (lazy import) |

- **Dependencies:** the Python standard library and the lane modules. It reaches the Core API over plain HTTP at
  `http://127.0.0.1:8765`, with 2.5 s and 4 s timeouts. Every call fails open.
- **Core API endpoints:** every endpoint it uses still exists in the current `services/core-api/app.py`.
- **Writes:** the only writes are `POST /os/drafts` and `POST /os/goals`, through the existing governed endpoints.
- **Relation to the repo's slice blocks:** all six per-slice blocks under `docs/architecture/slice-8..13/` appear in
  it verbatim. The part they could not provide, the Slice 7.2 base, is the history stage
  `integrations/hermes/history/prod/world_context/world_context.py.bak.20260908-091656`.

## `router.yaml.tmpl`

The deployed `lilith_router/router.yaml` (`7d14b571…`) records PROD's live state:
- the main routing lane is live;
- Slices 7.2 to 13 are all `live` on the channels `lilith_os` and `telegram`;
- Slice 14 Social Cognition is `shadow`;
- Slice 15A consolidation is `SHADOW`;
- `canonical_ltm_enabled` is `false`.

That is an observed historical setting, not an instruction for any environment.

The one Discord channel id is replaced with `__LILITH_DISCORD_CHANNEL_ID__`, so the template is **not byte-identical**
to the deployed file. `assemble_prod_complete.py --channel-id-file …` restores the exact bytes from a value held in
owner custody, and was verified to reproduce `7d14b571…`. PROD keeps this file inside `lilith_router/`; the DEV
release keeps its own `router.yaml` at the `HERMES_HOME` root.

## `lilith_router/tests/`

PROD runs 13 Router V2 test modules plus an empty `__init__.py`:
- 7 are new to Git and stored here;
- 6 are byte-identical to files already under `docs/architecture/slice-*` and are referenced from `PROD-RECOVERY.json`.

They were run offline, with network blocked, against the tree assembled from Git:
- 11 modules pass;
- `test_classifier` passes when console output is UTF-8;
- `test_social_presence` passes 47 of 49; its two remaining checks read the PROD host's Hermes `run.py` and `SOUL.md`
  archive, which are not part of this tree.

An offline import test does not show that this cognition works on modern DEV. Integration on DEV is separate work.
