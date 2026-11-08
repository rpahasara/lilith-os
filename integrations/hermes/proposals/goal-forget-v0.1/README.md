# Goal data before real goals are allowed (PROPOSAL, nothing wired)

**Rule until this is done:** only `TEST_ONLY` synthetic goals, with mandatory cleanup. Goal rows are outside the 7-day retention and FORGET today.

## Changes needed

| # | Change | Owner | State |
|---|---|---|---|
| 1 | Erasure and retention logic | Core API | candidate [`goal_erasure.py`](goal_erasure.py), 21 tests; `retention_step` is the one daily call, stopped by a hold |
| 2 | Allowlisted step in `hermes_forget_executor.py`: run erasure after the `state.db` purge, under the executor's lock, and add `goal_rows_zero` to its checks. An unknown table fails the run | Privacy | candidate functions, tested; not wired |
| 3 | Daily retention call beside `hermes-gateway-dev-retention`, as `lilith` | Core API | design only |
| 4 | Hold handling: a FORGET hold blocks both 2 and 3 | Privacy | candidate `forget_goals_unless_held`, tested; not wired |
| 5 | Restore gate: restoring a backup after FORGET must not bring goal rows back. Backups holding goal rows are forbidden, or listed in the erasure ledger | Privacy | candidate `backup_restore_allowed`, tested; decision needed |
| 6 | Conversation provenance: `provenance_json.sourceChannel` holds a session key; store a non-identifying channel name | Core API | candidate `channel_label`, tested; not wired |
| 7 | DB mode 0600 and `UMask=0077` | Core API | plan in `goals-privacy-v0.2` |
| 8 | Decision-log goal ids | Router | the counts-only trace removes Workspace ids; `app_id` stays under 7-day retention |

| 12 | Principal FORGET across every Core API owner store, in one transaction, with an erasure ledger outside the database | Core API, Privacy | candidate [`core_erasure.py`](core_erasure.py), 24 tests on the real `app.py`; not wired. A crash before `COMPLETE` is finished by re-running, under the same id and tombstones |
| 13 | Reconstruction: a new `career_events` row, or the career ingest, rebuilds an erased belief. **The kept cursor doesn't stop it** | Core API | ingest guard on the implementation branch; not deployed |
| 14 | Restore: replay on a quarantine copy, refuse on an untrusted ledger, and name snapshots from before an erasure. **A restore now needs the backup's age:** rows in a backup newer than the erasure are newer data and stay, and a replay doesn't move the boundary | Privacy | candidate, tested; the whole cycle passes against the implementation branch; snapshot policy is an owner decision |

Changes 2, 4, 5, 12 and 14 alter FORGET and need their own Privacy approval.

**Wiring shape:** the executor calls `forget_step(db, hold_path)` under its lock and adds `goal_rows_zero` to its checks. The retention timer runs `goal_erasure.py prune <db>` as `lilith`. Neither exists on any host.

**Before real goals, also:** G3's negative control and title criterion are still unproven live. See `release/dev-f9c2-cog1-wm1-g2/G3-RESULT-20261030.md`.

| 9 | Goal detector: the deployed `detect_goal_intent` matches casual uses of the word `goal`, which on a populated store sends every title to the provider and writes a trace | Router | fixed in the w1 adapter, proven offline with Goals live on a populated store; not deployed |
| 10 | Title presentation: nothing told the model to name a goal by its title | Router | rule added to the w1 adapter and proven in the prompt; **model behaviour unproven live** |
| 11 | Tasks and drafts have the same gap as goals | Core API, Privacy | candidate `erase_tasks_and_drafts`, `prune_discarded_drafts` and `prune_terminal_tasks`, tested. **Tasks are kept until their age is decided:** `retention_step` reports `not_decided`, and there's no default |

## Proof needed on DEV, with synthetic data

1. Seed canary goals, run a real FORGET drill, and find the canary gone from file bytes and from every checked location.
2. A held FORGET leaves rows in place and reports held.
3. Retention removes an old terminal goal and keeps an old active one.
4. A restored backup cannot resurrect a canary.

## Open owner decisions

Decisions 1 to 8 in [`goals-privacy-v0.2/PLAN.md`](../goals-privacy-v0.2/PLAN.md) section 2 still apply.
