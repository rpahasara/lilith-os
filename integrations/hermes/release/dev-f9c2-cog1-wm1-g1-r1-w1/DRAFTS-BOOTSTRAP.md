# `drafts` schema bootstrap gate (PREPARED, NOT RUN)

Workspace shadow calls `GET /os/drafts`, and `_drafts_db()` runs `CREATE TABLE IF NOT EXISTS`. Without this gate, the first
analytic turn would change the DEV schema from inside a GET. The gate makes that change deliberate, reversible and pinned, as
the G-S goal-schema gate did.

**Host scripts:** generated from the executed G-S scripts by asserted replacements, and kept outside the repository like every
gate package, because they pin live PIDs: `C:\Users\edufo\lilith-dev-drafts-schema-20261030`.

## Steps

One script, `ds_bootstrap.sh`, run once with the gateway up on r1, which makes no Core API reads. It stops before the schema write
on any failed check.

| Phase | Action |
|---|---|
| A, read-only | r1 current and its router; gateway 378068; gate 370064; budget 3/5; ledger 29 lines; FORGET idle; protected services; no `-journal`, `-wal` or `-shm`; DB digest `b291372517…` |
| B, rehearsal | Core API interpreter matches the running process; `app.py` is `a9fc562f…`; the same code runs on a throwaway DB, including exact rollback and three refusals |
| C, backup | sqlite online backup to `/var/backups/lilith-drafts-schema-20261030/` (root 0700, file 0600); logical digest equal to the reference |
| D, write | the Core API's own `_drafts_db()` once, as `lilith`, with an empty `HERMES_HOME`. Any post-condition failure drops the table in one transaction, back to the exact reference |
| E, verify | independent read-only check, as root |

**New reference:** `88b76a7910fdcb27dc3b7c02e9f18c2c92b8154d10afc9f15f4bc9da90a84e79`, computed from the real Core API. It adds exactly
`drafts`, 3 named indexes and 2 automatic ones. Every table has 0 rows.

## Rollback

`ds_rollback.sh`: `DROP TABLE drafts` in one transaction, committing only if the digest then equals `b291372517…`.

**It refuses** if `drafts` has any row, if anything else differs, or if r1 is not current. Nothing on DEV writes drafts: the
adapter refuses them.

## Offline evidence

`tests/dspy_check.py`, on the pinned `app.py`, passes 21 checks and 24 rehearsal checks: refusal on a wrong digest or a foreign table,
an injected post-condition failure rolled back exactly, a second bootstrap and rollback refused, rollback refused with a draft
row, and the three scripts identical except their `MODE` line. `ds_status_ro.sh` classified the live DB as the prior reference.

**Not proven:** the write has not run on DEV. The check ran with Python on Windows, not the Core API interpreter; phase B is what
covers that on the host.

## Effect on other packages

The DB reference changes, so every package pinned to `b291372517…` must be regenerated: the G3 package in particular. G3 compares
the full logical digest, and its seed and cleanup would refuse a DB with the `drafts` table. G3 ran once on 2026-10-30, so this gate is regenerated for the state it left (manifest `d25fb1b3…`). **Any G3 re-run must come
before this gate, or be regenerated after it.**

## Not in scope

No retention or FORGET change. `drafts` holds no rows, and the adapter refuses draft writes. If drafts are ever enabled, they need
the same retention and FORGET decision as goal rows.
