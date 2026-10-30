# Acceptance: Goals/Executive shadow on DEV (`f293e72-f9c2-cog1-wm1-g1`), 2026-10-30

**Decision:** owner-accepted as **PASS** on 2026-10-30, for **Goals shadow behaviour only**. Live goal grounding,
focus arbitration and goal prioritisation were **not** validated. Nothing here authorizes Goals live or any other lane.

## Runtime accepted

| Item | Value |
|---|---|
| Host | `lilith-dev-01` (boot `cb0d71da…`, unchanged throughout) |
| Release | `f293e72-f9c2-cog1-wm1-g1` (PR #285, merged as `7db9b51`); installed 04:37–04:38Z; gateway started 04:42:06Z (PID 357537) |
| Lanes | World Model `cognitive_enabled: true` / `cognitive_mode: shadow`; Goals `goals_enabled: true` / `goals_mode: shadow`; `cognitive_channels: [lilith_os]`; the other eight lanes `false`; router `mode: shadow` |
| Start-time gate | `F8_VERIFY_PASS pre-start f293e72-f9c2-cog1-wm1-g1` (ExecStartPre status 0) |
| Hashes | adapter `07a763e1…`, PROD Working Memory `46b8187e…`, gateway `5ce4bbd4…`, router `d931f1b6…`, plugin adapter `8c3b0055…` |
| Rollback | `f293e72-f9c2-cog1-wm1` (`install_g1.sh revert`), then `f293e72-f9c2-cog1` (`install_wm1.sh revert`); f9c2, cog1 and wm1 manifests intact |

Console downtime for the install was 04:31:13–04:42:06Z, about 10 min 53 s.

## Evidence

### Gates (each run once, rc 0, empty stderr, command byte-identical to the approved script)

| Gate | Result |
|---|---|
| P0 read-only preflight | PASS. wm1 baseline; DB at the pre-S1 reference, no goal tables |
| Gate D stop | PASS. The known Hermes exit status 1 (`failed/failed`, `Result=exit-code`); port 9901 closed; other units unchanged |
| Gate E transfer + install | PASS. Bundle `921f2ff0…` (built byte-exact from `7db9b51`); `G1_INSTALLED`; `verify --full` PASS. Exactly 8 paths changed; 0 changes under Privacy, broker, authority, witness and FORGET; DB and budget unchanged |
| Gate D start | PASS. PID 357537 stable at +20 s, 0 restarts; no provider request at startup |
| Post-install verification | PASS. DB at the pre-S1 reference, goal tables absent; 0 Core API requests since start; rollback payloads present |

### The synthetic shadow turn (04:52:37Z)

**Turn:** one console turn, `TEST_ONLY which goal has priority?`, in the fresh session `g1-goals-shadow-20261030`.
It used the one remaining provider request, as authorized.

| Criterion | Result |
|---|---|
| Reply | 200 `completed`, generic (shadow adds no goal grounding) |
| Provider | exactly 1 FORWARDED, status 200, `openai/gpt-oss-120b`; budget 4/5 → 5/5 (exhausted); no other model call |
| Core API | **0** accesses: no `/os/goals` or `/os/goals/focus` read, no write |
| Goal schema | `goal` / `goal_trace` still absent; DB logical digest = pre-S1 reference; file mtime and size unchanged |
| Decision log | exactly 2 records: **1 Goals shadow record** (`goal_mode: shadow`, intent `goal_query: true`, `subtype: priority`, `app_id: null`; only the approved metadata fields) and 1 routing record (`live: false`); 0 World Model or other-lane records |
| Content | **no message text** in the decision log; 0 request dumps |
| Gateway and services | same PID; lanes unchanged; the other 15 units identical; FORGET idle |

**Gate refusals:** the gate refused 12 requests since start: Hermes model-metadata probes, refused locally and not
forwarded (the same pattern as earlier windows). The final read-only check passed after the turn.

### Offline evidence before the turn

- the g1 release suite: 28 tests OK;
- the exact message through the real gateway, adapter and real Core API source: 12/12;
- the turn-sender review against the accepted S2-C sender: 20/20.

### Evidence folders (owner workstation, `%USERPROFILE%`; not in Git)

| Folder | Manifests |
|---|---|
| `lilith-dev-g1-p0-20261030` | `SHA256SUMS.run` `d018af8f…` |
| `lilith-dev-g1-gates-20261030` | `SHA256SUMS` `dd141220…`, `.gd_stop-run` `4a239905…`, `.ge-run` `7b132a9d…`, `.gd_start-run` `245c21b8…`, `.pv-run` `faa8a3c5…` |
| `lilith-dev-g1-goals-shadow-20261030` | `SHA256SUMS` `61f1b427…`, `.run` `ed7a44f8…` |

## Limitations (not claimed)

- **Coverage:** one message, one phrasing, one session, the `lilith_os` channel only.
- **What shadow shows:** detection and content-free logging only. It does not exercise goal grounding, Core API goal
  reads, focus arbitration or goal-state answers.
- **Detector breadth:** the PROD goal detector also matches casual prose such as "my goal for the weekend is to
  relax". In shadow this adds one record.

## Retained artifacts

- **Sessions and logs:** the Hermes session `g1-goals-shadow-20261030` (the turn and reply) and the 2 decision
  records follow the 7-day retention and FORGET.
- **Ledger:** 2 ledger lines (append-only metadata).
- **Markers:** an empty root-only marker dir.
- **Rollback payload:** the g1 staging dir (kept as the rollback payload).
- **Budget:** 5/5, exhausted.
