# PROD data: preserve, erase, keep deleted (PLAN, offline only)

Prepared without PROD access. Counts come from the read-only audit of 2026-10-27 and must be re-read in a rehearsal. **Nothing here touches PROD.**

## Stores

| Store | On PROD when audited | Preserve at migration | Erase when authorized |
|---|---|---|---|
| `world_belief*` | 31 beliefs, 93 evidence rows, cursor 17 | yes, row-exact | `erase_world_model`, with the source decision below |
| `goal`, `goal_trace` | 3 goals, 11 traces | yes | `erase_all_goals`. Needs a provenance review: `sourceChannel` holds a session key |
| `tasks` | 7 | yes | `erase_tasks_and_drafts` |
| `drafts` | 10 | yes | `erase_tasks_and_drafts` |
| `career_events` | present | yes | **owner decision** |
| `cognitive_memory.db` | L04 0 rows, L18 3 shadow | yes | canonical route, not this code |
| Hermes `state.db` | unread | yes | existing FORGET design, once PROD has it |

## Preserve

1. Rehearse on an isolated copy of a snapshot, with no route to PROD and provider access off.
2. Take per-table counts and digests before and after, on the same logical digest used on DEV.
3. Schema changes are additive only. `app.py` moves from `519b309`, so list every table the newer code would create.
4. Reads must not create schema: bootstrap as a deliberate gate, as on DEV.
5. The verifier's empty-goal-store rule **cannot apply to PROD**, because PROD has goals. So a focus read will write a trace. Before cutover, remove that write from the read path, or accept it in writing.

## Erase correctly

Each erase runs in one transaction, under the FORGET lock, refuses unknown tables, honours a hold, and is checked by a separate zero-rows read. `secure_delete` and `VACUUM` remove the text from the file.

**The candidates refuse PROD's schema today.** `ALLOWED_TABLES` lacks PROD's tables, on purpose. Its list must come from the rehearsal, not from this document.

## Keep deleted

| Route back | Control | State |
|---|---|---|
| World Model rebuilt from `career_events` | Keep the cursor, and decide whether the source goes too | candidate |
| Re-ingest of old events after a cursor reset | Never reset the cursor as part of erasure | candidate, tested |
| Backup restore | Restore gate: a backup holding erased classes is refused, or replayed through an erasure ledger | candidate, needs a ledger |
| Snapshots, including the 2026-10-27 preservation snapshots | Same rule. **A snapshot holds everything**, so FORGET is incomplete while one exists, and that needs an explicit owner policy | **open** |
| Watchers and connectors re-delivering the same item | Source-level tombstones by content id | **not designed** |
| Hermes session history and learning | Existing FORGET scope | exists on DEV only |
| Decision log | 7-day retention and purge | exists on DEV only |

## Owner decisions

1. Does principal FORGET erase `career_events`, or only what is derived from it?
2. How long do snapshots stay, and do they count against FORGET?
3. Do erased items need tombstones, which keep a small hash after deletion?
4. Retention age for completed tasks.
5. Should goals created by conversation on PROD migrate as they are, or be re-confirmed?

## Order

1. Decisions above.
2. Wire FORGET and retention on DEV, under Privacy approval, and drill with canaries.
3. Rehearse on the isolated copy: preserve, then erase, then restore, and show that nothing returns.
4. Only then a PROD plan.
