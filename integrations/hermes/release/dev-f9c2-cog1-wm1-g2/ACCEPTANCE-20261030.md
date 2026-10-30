# Acceptance record: Goals live window on DEV (`f293e72-f9c2-cog1-wm1-g2`), 2026-10-30

**Status:** prepared for owner decision. All criteria of the one approved window were met. Recommendation: accept as
**PASS for live Goals plumbing on an empty store only**. This is not proof of goal prioritisation, and it authorizes
nothing further. DEV was returned to g1 (Goals shadow); g2 is not running.

## Runtime tested

| Item | Value |
|---|---|
| Host | `lilith-dev-01` (boot `cb0d71da…`, unchanged throughout) |
| Release under test | `f293e72-f9c2-cog1-wm1-g2` (PR #286, merged as `96e29fe`); gateway on g2 09:23:45 to about 09:25:00Z (PID 362242) |
| Lanes under test | Goals `goals_enabled: true` / `goals_mode: live`; World Model `cognitive_mode: shadow`; `cognitive_channels: [lilith_os]`; the other eight lanes `false`; router `mode: shadow` |
| Goal store | `goal` and `goal_trace` present (bootstrapped by a separate gate), **0 rows** |
| Hashes | adapter `07a763e1…`, PROD Working Memory `46b8187e…`, gateway `5ce4bbd4…`, g2 router `9c0ce4e2…`, plugin adapter `8c3b0055…`, Core API `a9fc562f…` |
| Provider-data decision | owner decision P-1, for this experiment only: empty store, two synthetic `TEST_ONLY` messages |

Console downtime was 09:20:33 to 09:27:13Z, about 6 min 40 s.

## Window results (each step run once, rc 0, empty stderr)

The first package failed final review before anything ran: line 1 of `w6_turns.sh` read `et -u`. The corrected package
v2 (manifest `5fbe9b97…`) was approved and run. Preflight P0b passed earlier the same day.

| Step | Result |
|---|---|
| W1 stop g1 | PASS. Hermes exit status 1 as usual; port 9901 closed; other units unchanged |
| W2 transfer | PASS. `CHUNK OK 4b0e8eed…` |
| W3 install g2 | PASS. Bundle `54bb3b47…`; `G2_INSTALLED`; `verify --full` PASS including the goal-schema rule; exactly 8 paths changed; 0 changes under Privacy, broker, authority, witness and FORGET |
| W4 budget reset | PASS. One owner-approved reset, 5/5 to 0/5; ledger prefix unchanged, +1 line; 0 forwards; no cron job |
| W5 start g2 | PASS. Stable at +20 s, 0 restarts; 0 provider requests at startup |
| W6 turns | PASS, below |
| W7 stop g2 | PASS |
| W8 revert | PASS. `G2_REVERTED`; router `d931f1b6…`; g1 `verify --full` PASS; g1, wm1, cog1 and f9c2 manifests intact |
| W9 start g1 | PASS. PID 363555 stable, 0 restarts; 0 provider requests at startup |
| W10 final read-only | PASS |

### W6, the two synthetic turns

**L1, `TEST_ONLY which goal has priority?` (session `g2-live-l1-20261030`):**

| Criterion | Result |
|---|---|
| Reply | 200 `completed`: "There are currently no recorded goals in the durable Goal/Executive state, so there is no priority to report." |
| Provider | exactly 1 FORWARDED, status 200, `openai/gpt-oss-120b`, 984 prompt / 43 completion tokens |
| Core API | exactly `GET /os/goals?limit=200` 200 and `GET /os/goals/focus` 200; **0 writes** |
| Database | digest unchanged at `b2913725…`; 0 `goal` and 0 `goal_trace` rows; file mtime and size unchanged |
| Decision log | exactly 1 new record: the goal lane, `goal_mode: live`, intent `goal_query: true`, `subtype: priority`, `app_id: null`; only the approved metadata fields; no routing record; no message text |
| Other | 0 request dumps; same gateway PID |

**L2, the unrelated control `TEST_ONLY hey how are you` (session `g2-live-l2-20261030`):**

| Criterion | Result |
|---|---|
| Reply | 200 `completed`: "I'm doing well, thank you! How can I assist you today?" |
| Provider | 1 FORWARDED, status 200, 717 prompt / 28 completion tokens (2 in total) |
| Core API | **0** new requests |
| Decision log | exactly 1 routing record (`live: false`), 0 goal records; no message text |

The 267-token prompt difference between L1 and L2 shows extra content reached the model on L1, consistent with the goal
policy and empty-state block. It is not a direct capture of the prompt.

**Gate refusals:** 17 since the g2 start, against 12 in the earlier windows. W6 counts them but does not record their
paths. Earlier windows showed them to be Hermes model-metadata probes refused locally; the 17 were not itemised.
Budget and forward counts rule out any effect on the provider: forwards were exactly 2.

## Final state of DEV (W10, 09:27:46 to 09:28:24Z)

| Item | Value |
|---|---|
| Release | `f293e72-f9c2-cog1-wm1-g1`; World Model and Goals shadow; other lanes off; `verify --full` PASS |
| Gateway | active, 0 restarts; 0 Core API requests since the g1 restart |
| Database | `b2913725…`, integrity ok, every table 0 rows |
| Provider gate | key loaded, **2 of 5 used, 3 requests remain open**; ledger 27 lines `a05fe17e…`; forwards since the reset = 2 |
| FORGET | 0 intents, no marker; path and timer units active |
| Protected services | gate, Core API, broker, authority and witness active on their original PIDs, 0 restarts; no failed units |
| Rollback | g1 and wm1 revert payloads present; f9c2, cog1, wm1 and g1 manifests intact |

## Limitations (not claimed)

**Empty-state only.** The store held no goals, so this window does **not** validate:
- goal prioritisation, or which goal wins arbitration;
- focus selection, the focus-change trace write, or blocked-goal reporting;
- grounding that contains a real or synthetic goal title, or an answer that uses one;
- goal creation, which stays refused by the adapter.

**Also not shown:**
- **Causation:** the reply is consistent with the grounding, but one model reply does not prove the grounding caused it.
- **Coverage:** one question, one phrasing, one model, one channel.
- **Detector precision:** only a true positive and one true negative ran. The detector's known over-matching remains.
- **Long-run behaviour:** g2 ran for about 75 seconds, and it is not running now.

## Open items, separate from this record

- **Provider data:** P-1 covered this experiment only. Decisions P-2 (retention and FORGET for goal rows) and P-3
  (authentication on `POST /os/goals`) remain open.
- **Budget:** 3 open requests must not be spent or reset without authorization.
- **Retained artifacts:** the two Hermes sessions and two decision records follow the 7-day retention and FORGET. Ledger
  lines are append-only metadata. The g2 release and staging directory stay on DEV for inspection. The root-only G-S
  backup is kept; its disposition needs separate approval.
- **Security finding:** the DB file mode 644 is pre-existing and unchanged.

## Evidence (owner workstation, `%USERPROFILE%`; not in Git)

| Folder | Manifests |
|---|---|
| `lilith-dev-g2-p0-20261030` | `SHA256SUMS` `35872a3a…` |
| `lilith-dev-g2-goal-schema-20261030` | `SHA256SUMS` `d64c2f3f…` |
| `lilith-dev-g2-window-20261030` | failed v1, kept with `FAILED-REVIEW-20261030.md`; holds the P0b output |
| `lilith-dev-g2-window-v2-20261030` | `SHA256SUMS` `5fbe9b97…`, `SHA256SUMS.run` `43bf26dc…` |
