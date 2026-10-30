# `drafts` schema bootstrap: design for a future gate (NOT RUN)

Workspace shadow calls `GET /os/drafts`, and `_drafts_db()` runs `CREATE TABLE IF NOT EXISTS`. Without this gate, the first
analytic turn would change the DEV schema from inside a GET. The gate makes that change deliberate, reversible and pinned, as
the G-S goal-schema gate did.

## Steps

Modelled on the accepted G-S gate. One script, run once, with the gateway running on r1, which makes no Core API reads.

1. **Preflight, read-only:** r1 current; DB digest exactly `b291372517…`; no `-journal`; FORGET idle; `app.py` is `a9fc562f…`.
2. **Backup:** sqlite online backup to `/var/backups/lilith-drafts-schema-<date>/` (root 0700, file 0600), with its digest
   recorded and its logical digest proven equal to the reference.
3. **Create:** run the Core API's own `_drafts_db()` once, in a separate process, as `lilith`, with an empty `HERMES_HOME`.
4. **Verify:** the digest equals the new pinned reference. It adds exactly `drafts` and its 3 named and 2 automatic indexes. Every
   table has 0 rows.

**New reference:** computed offline from the post-bootstrap DB when the gate is packaged, then pinned in the scripts. The test
`DraftsBootstrap` proves the change is additive and idempotent on the real Core API.

## Rollback

`DROP TABLE drafts` in one transaction, which also drops its indexes, committing only if the digest then equals
`b291372517…`. The test proves this returns to the exact prior logical state, on an empty table.

**Refuse rollback if `drafts` has any row.** Nothing on DEV writes drafts: the adapter refuses them.

## Effect on other packages

The DB reference changes, so every package pinned to `b291372517…` must be regenerated: the G3 package in particular. G3 compares
the full logical digest, and its seed and cleanup would refuse a DB with the `drafts` table. **Run G3 before this gate, or
regenerate it after.**

## Not in scope

No retention or FORGET change. `drafts` holds no rows, and the adapter refuses draft writes. If drafts are ever enabled, they need
the same retention and FORGET decision as goal rows.
