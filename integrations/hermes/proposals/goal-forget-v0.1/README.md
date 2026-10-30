# Goal data before real goals are allowed (PROPOSAL, nothing wired)

**Rule until this is done:** only `TEST_ONLY` synthetic goals, with mandatory cleanup. Goal rows are outside the 7-day retention and FORGET today.

## Changes needed

| # | Change | Owner | State |
|---|---|---|---|
| 1 | Erasure and retention logic | Core API | candidate [`goal_erasure.py`](goal_erasure.py), 5 tests on the real schema |
| 2 | Allowlisted step in `hermes_forget_executor.py`: run erasure after the `state.db` purge, under the executor's lock, and add `goal_rows_zero` to its checks. An unknown table fails the run | Privacy | design only |
| 3 | Daily retention call beside `hermes-gateway-dev-retention`, as `lilith` | Core API | design only |
| 4 | Hold handling: a FORGET hold blocks both 2 and 3 | Privacy | design only |
| 5 | Restore gate: restoring a backup after FORGET must not bring goal rows back. Backups holding goal rows are forbidden, or listed in the erasure ledger | Privacy | decision needed |
| 6 | Conversation provenance: `provenance_json.sourceChannel` holds a session key; store a non-identifying channel name | Core API | design only |
| 7 | DB mode 0600 and `UMask=0077` | Core API | plan in `goals-privacy-v0.2` |
| 8 | Decision-log goal ids | Router | the counts-only trace removes Workspace ids; `app_id` stays under 7-day retention |

Changes 2, 4 and 5 alter FORGET and need their own Privacy approval.

## Proof needed on DEV, with synthetic data

1. Seed canary goals, run a real FORGET drill, and find the canary gone from file bytes and from every checked location.
2. A held FORGET leaves rows in place and reports held.
3. Retention removes an old terminal goal and keeps an old active one.
4. A restored backup cannot resurrect a canary.

## Open owner decisions

Decisions 1 to 8 in [`goals-privacy-v0.2/PLAN.md`](../goals-privacy-v0.2/PLAN.md) section 2 still apply.
