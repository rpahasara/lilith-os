# PROD with real data: what DEV's safety doesn't prove (offline review)

**DEV's guarantees come from empty stores.** No PROD access was used. Sources: the 2026-10-27 audit, recovered PROD source, and synthetic stores of PROD's shape.

| Concern | Why DEV doesn't cover it | Evidence | Fix or design | State |
|---|---|---|---|---|
| **Focus-trace writes** | DEV has no goals, so a focus read never writes. PROD has 3 goals and 11 traces | Focus is the only GET that writes, and only when focus changes | `LILITH_OS_FOCUS_READ_ONLY=1` | tested on #306; off |
| **Every lane's focus read** | Each matching turn reads focus | same | the flag must be on **before** the new stack reads PROD data | rehearsal check |
| **Schema** | `ALLOWED_TABLES` is DEV's list. PROD also has `people`, `career_activities`, `os_audit_log` | recovered `init_db.py` | erasure refuses PROD until they're named, on purpose | `ALLOWED` needs PROD's real list, read on the copy |
| **Additive migration** | `app.py` moves from `519b309` to main | not reviewed | list every schema change; additive only | offline next |
| **Ingestion** | DEV has no career data. On PROD, a new event re-reads the source | test | ingest guard | #306 |
| **Dead connectors waking** | OAuth failed 08-31. Repairing it re-delivers everything since, in one burst, and erased mail too | recovered extractor | tombstones first; rate limit the first run | design |
| **Retention** | PROD's decision log has no purge | audit: 213 lines | apply DEV's 7-day rule, with signed loss: it's the only trace of past lanes | owner |
| **Live semantics** | PROD's detectors fire far more; a reply may depend on it | A3 not run | compare on the fixed prompt set | rehearsal |
| **Provider exposure** | With real rows, prompts hold real titles and beliefs. DEV's prompts held nothing | privacy tests cover records, **not prompts** | measure bytes per lane; check what a provider would receive | A23, rehearsal with provider off |
| **Auth compatibility** | PROD has no auth code; adapter sends no header | adapter source | staged design | #306 |
| **`state.db`** | 35 MB, unread | audit | its own Privacy decision | owner |
| **Read limits** | `limit=200` is plenty for 3 goals; memo and bounded reads were sized on empty stores | not measured | measure latency on the copy | rehearsal |
| **Concurrency** | Hermes and watchers write while lanes read | none | run with watchers on the copy; WAL checked | rehearsal |

## What this means for order

1. Flag on, auth wired and FORGET ready come **before** the new stack sees PROD data, including on the rehearsal copy.
2. OAuth repair comes **after** tombstones.
3. **The most useful next read:** the cloud-only network preflight in #306's `PROD-API-EXPOSURE.md`. It connects to nothing on PROD and changes nothing. Recorded evidence says 8765 isn't public; that record is days old.
