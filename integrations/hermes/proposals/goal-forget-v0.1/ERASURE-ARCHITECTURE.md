# Erasure architecture (PROPOSAL, nothing wired)

**The requirement: an authorized deletion must not be undone by the next ingestion job, restore or replay.** Deleting rows isn't enough, so every store below is paired with the routes that could rebuild it. Nothing here touches DEV or PROD data. Wiring it changes FORGET and needs its own Privacy approval.

## Principle

**Two records survive an erasure, both outside the database:** a ledger, because the database is what a restore brings back, and a key held apart from that ledger. Tombstones are keyed hashes, so the ledger never holds what it protects. **Every route back reads the ledger, and refuses when it can't.**

## Stores

| Store | Erased by | State |
|---|---|---|
| `world_belief`, evidence, trace, conflict, working seed | `erase_principal` | candidate, tested on the real `app.py` |
| `world_ingest_cursor` | `erase_principal`; the boundary moves to the ledger's `through_event_id` | candidate, tested |
| `goal`, `goal_trace` | `erase_principal` | candidate, tested |
| `tasks`, `drafts` | `erase_principal` | candidate, tested |
| `career_events`, `job_applications`, `companies`, `people`, `career_activities` | `erase_principal` with `source_too` | candidate, tested. **Whether it runs is decision 1** |
| `os_audit_log` | nothing yet | **decision 2.** `ALLOWED_TABLES` refuses PROD's schema until it's named |
| `state.db`, `USER.md`, decision log | Privacy on DEV; V1 config on PROD | **outside this candidate.** Decision 5 |
| Restored backups | replay on a quarantine copy | candidate, tested |
| Snapshots | nothing: named as `PREDATES_ERASURE` only | **decision 3** |

## Routes back

| Route | What happens without a control | Control | State |
|---|---|---|---|
| New `career_events` row | ingest re-reads `job_applications` and rebuilds the belief; **the kept cursor doesn't stop it** | ingest guard, entity tombstones | on #306's branch, tested |
| `POST` to the full career ingest | rebuilds everything | same guard | same |
| **Gmail redelivery** | **New finding.** The extractor's only memory is `career_activities.source_message_id`. Erasing that table makes it forget, so the same mail is ingested again **under a new id no id tombstone matches** | **message tombstones:** `message_erased` before ingest | candidate, 9 tests, using the recovered extractor's own `already_processed`. **The extractor isn't patched** |
| Backup restore | rows return | `restore_decision`, replay on quarantine | candidate; whole cycle tested |
| Replay on a newer backup | would destroy newer data | needs `taken_at`; unknown age with rows refuses | candidate, tested |
| Crash mid-erasure | rows gone, tombstones unwritten | `PENDING` first; re-run finishes it; ingest and restore refuse while open | candidate, tested |
| Unreadable ledger | could read as "nothing erased" | raises, and ingest and restore refuse | candidate, tested |
| Lost key | tombstones can't be matched | **design only:** the key is backed up apart from the ledger, and a guard that can't load it refuses ingest | decision 4 |
| Other connectors | **not reviewed:** only Gmail's extractor was traced | each needs a stable source id before it may ingest | open |

**Order at a restore:** quarantine copy, `restore_decision`, replay, zero-rows check, go live, then allow ingest.

## Limits

- **`source_too=False` keeps the text in the file.** Tombstones stop the beliefs returning, but the source remains. A test proves it.
- **The ledger shows that erasure happened, and how much.** That's the cost of being able to enforce it.
- **Today's erasure is a whole principal.** LILITH has one owner, so that fits, but erasing one application needs a scoped variant: not designed.
- **A snapshot still holds the data until it expires.** The gate stops it returning through a restore, not someone reading the disk.
- **Message ids depend on Gmail keeping them stable.** A forwarded copy has a new id and would ingest.

## Synthetic proof

`test_core_erasure.py`: 33 tests with `CORE_API_DIR` at the #306 tree. **Skips the whole-cycle test without the guard.** `test_goal_erasure.py`: 21. No DEV or PROD data involved.

## Wiring order, each needing Privacy approval

1. Decisions below.
2. Core API guard merged, ledger configured, with no erasure yet: ingest behaves as today.
3. Executor calls `erase_principal` under its lock, on DEV, with canaries.
4. Extractor calls `message_erased`, before OAuth is repaired on PROD. **Repairing OAuth first would re-deliver anything already erased.**
5. Restore procedure uses the gate.
6. Drill: seed canaries, erase, fire every route, restore, replay, check bytes.

## Decisions needed from the owner

| # | Decision | Recommendation |
|---|---|---|
| 1 | Does principal FORGET erase career source data, or only what's derived from it? | **Erase it, with tombstones.** Keeping it keeps the text |
| 2 | `os_audit_log` on erasure: erase, keep, or strip content? | Read it on the rehearsal copy first, then decide |
| 3 | Snapshots and backups predating an erasure: expire on a schedule, delete on erasure, or keep and gate? | **Keep, gated, with a short fixed expiry** such as 30 days, which sets the honest answer to "when is it really gone" |
| 4 | Where the tombstone key lives, and its backup | Separate from the ledger and every database backup |
| 5 | Which authority owns FORGET on PROD: DEV's F9-C, or PROD's V1 config? And does it cover `state.db` and `USER.md`? | F9-C, which is tested. V1 doesn't cover either |
| 6 | Retention ages for tasks | No default until set |
| 7 | Are forwarded copies of erased mail in scope? | Accept as a known limit at first |
