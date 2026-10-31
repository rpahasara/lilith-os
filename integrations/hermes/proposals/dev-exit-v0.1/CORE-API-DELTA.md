# Core API delta: PROD `519b309` to the migration target (A10)

Compared offline: `519b309` against the #306 tree, which is main plus #289 and #306. PROD wasn't accessed.

**Result: the data migration for Core API is empty.** No existing table changes. The risk is in settings and callers, not schema.

| Surface | PROD | Target | Change |
|---|---|---|---|
| Routes | 35 | 36 | adds `POST /os/conversation/evidence`; removes none |
| Tables in `app.py` | 10 | 16 | adds 6 `fi_*` capture tables, in a separate new file, `conversation-evidence.db` |
| Existing table definitions | 10 | 10 | **all byte-identical** |
| `ALTER`, `DROP` | 0 | 0 | none |
| Indexes | 17 | 17 | none |
| Lines | 3,037 | 3,587 | +550 |

## What does change at deployment

| Setting | Unset means | Needed at cutover |
|---|---|---|
| `LILITH_OS_WRITE_AUTH`, `LILITH_OS_READ_AUTH` | **every protected route refuses** | set before the code, per the auth design |
| `LILITH_OS_WRITE_TOKEN`, `LILITH_OS_READ_TOKEN` | no enforcement possible | created on PROD, never copied from DEV |
| `LILITH_OS_FOCUS_READ_ONLY` | focus can write a trace | `1` |
| `LILITH_WORLD_ERASURE_LEDGER` | no ingest guard | set with FORGET |
| `LILITH_FI_EVIDENCE_CAPTURE`, `LILITH_FI_EVIDENCE_DB`, `LILITH_OS_OWNER_CAPTURE_TOKEN` | capture stays off | **leave off** on first migration |
| `LILITH_FORGET_INTENT_PATH`, `LILITH_PRIVACY_DB_PATH` | per the FORGET wiring | decided with the FORGET authority |

## Must be checked on the copy

- **PROD's file equalled `519b309` on the last read:** the audit recorded `bb0a4139`, and that's this commit's digest. The rehearsal re-reads it. **A mismatch stops this conclusion.**
- **The real table list.** `app.py` holds 10 tables; recovered career code adds `companies`, `people`, `job_applications`, `career_activities` and `career_events`, and `os_audit_log` is named by the audit. Only the copy gives the full list.
- **Tables outside `app.py`** stay untouched: this delta says nothing about them.

**Evidence level:** source comparison only. It shrinks the migration risk; it doesn't remove A30's row-level check.
