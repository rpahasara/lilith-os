# Slice 7 — World Model + Working Memory: Production Deployment Record

> Operational record of the Slice 7 Phase B production deployment. No secrets, credentials, or private user data are recorded here.

## Summary
| | |
|---|---|
| **Deployment date** | 2026-09-07 |
| **Target** | `lilith-01` (GCE, IAP tunnel) · service `lilith-os-api.service` (uvicorn, port 8765) |
| **Backend file** | `/home/lilith/.hermes/lilith-os/api/app.py` (single-file FastAPI) |
| **Database** | `/home/lilith/.hermes/lilith-os/data/lilith.db` (SQLite, `journal_mode=delete`) |
| **Change shape** | One appended, delimited `# BEGIN/END SLICE 7` block. Additive only; no edits to Slice 1–6 code or tables. |
| **Verdict** | **PASSED** |

## Hashes
| Artifact | Value |
|---|---|
| `app.py` starting sha256 | `340358764024a83b4425484423b45417d70b4cf75d4e204c4576a89c26ff6c9e` |
| `app.py` final sha256 | `90083ddb4a64ae350850d3a1b53d56bf9d86f48dc7ef963eb990fc75293e8cde` |
| appended block sha256 | `14ca491eb6a10812f3f0927315da021f17c0c4f38f7a221c923e4ef6a7560d91` (23,914 bytes) |
| `app.py` size | 60,327 → 84,241 bytes |

## Backup paths (created before any change)
- Code: `/home/lilith/.hermes/lilith-os/api/app.py.bak.20260907-170850` (sha256 `340358764024…`, exact copy).
- Database: `/home/lilith/.hermes/lilith-os/data/lilith.before-world-model.db` (proper SQLite `.backup()`, `integrity_check=ok`).

## Tables added (additive; existing tables untouched)
`world_belief`, `world_belief_evidence`, `world_belief_conflict`, `world_belief_trace`, `world_working_seed`.
Created via inline `_ensure_world_schema()` (`CREATE TABLE IF NOT EXISTS`; no migration file; `PRAGMA user_version` unchanged = 0).

## Test results
**18 / 18** A–R backend conformance tests PASS (`test_world_model.py`, run against a throwaway temp DB, `TEST_EXIT=0`). Covers: observation→belief, canonical-key dedup, idempotency, newer-supersedes, VERIFIED>INFERRED, stale sweep, conflict retention, UNKNOWN absence, unavailable-no-overwrite, no-mutation-route, no-generic-setter, working-set subset & capacity bound, reconstruction, trace-per-mutation, provenance persistence, career ingestion, Slice 1–6 route integrity.

## Production acceptance summary
- Ingested real `job_applications`: **8 applications → 31 observations**; second run idempotent (no duplicate beliefs).
- `/os/world` = 200; 31 beliefs, all `ACTIVE`/`OBSERVED`; predicates `company, last_activity, role, status` (mapped to real columns; no fabricated `follow_up_state`).
- Sample: `career.application:14:status = "applied"`, confidence 0.85 (`observed+1corrob`), full provenance chain (`origin_ref=job_applications/14`).
- Single-key HTTP read (colon key) = 200; bounded working set (capacity 5) reconstructed with focus entity ranked first.
- Controlled conflict → `CONFLICTED` (value not overwritten, both chains retained); stale → `STALE` (value retained); unavailable source → `noop/source_unavailable_noop` (no overwrite); unknown → 404. Synthetic demo rows cleaned up; real beliefs untouched.

## Restart-persistence evidence
Restart (restart-only; PID 202798 → 203178): 31 beliefs persist; `career.application:14:status` intact with 2 provenance rows; durable counts beliefs=31 / evidence=62 / trace=62 (trace persists); `world_working_seed=0` and identical working set after restart → **Working Memory reconstructed from durable state, never stored as truth**.

## Service / integrity status (post-deploy)
- Service `active/running`, port 8765 listening, `/os/world`=200; **no tracebacks/errors** in the journal across the deploy window.
- Slice 1–6 endpoints all 200; data unchanged (`tasks=7, drafts=6, job_applications=8, career_events=11, os_audit_log=1`); `integrity_check=ok`.
- `NeedDaemonReload=yes` is **pre-existing and untouched** (deploy was restart-only; **no `daemon-reload` performed**).

## Known gaps (at end of Phase B; addressed by Slice 7.1)
1. Ingestion was a manual one-off (`world_ingest_career()`), not wired to the observation pipeline. → **Slice 7.1**
2. `world_freshness_sweep()` existed but was unscheduled. → **Slice 7.1**
3. `follow_up` not emitted (no source column; derive later as `INFERRED` only if a `career_activities` signal exists).
4. `apply_verified_delta` (VERIFIED path) implemented/tested but unused until a Verification layer exists.
5. The one on-disk `Environment=` line should be eyeballed before any *future* `daemon-reload` (out of scope).

## Rollback procedure (verified staged; not needed — deploy passed cleanly)
Run over the authorized IAP SSH session, as `lilith`:
```bash
# 1. restore code from the timestamped backup
sudo -u lilith cp -a /home/lilith/.hermes/lilith-os/api/app.py.bak.20260907-170850 \
     /home/lilith/.hermes/lilith-os/api/app.py
# 2. (only if a DB problem is suspected — world_* tables are additive/inert otherwise)
sudo -u lilith cp -a /home/lilith/.hermes/lilith-os/data/lilith.before-world-model.db \
     /home/lilith/.hermes/lilith-os/data/lilith.db
# 3. restart on the restored code (restart only — never daemon-reload)
sudo systemctl restart lilith-os-api.service
# 4. verify recovery
systemctl is-active lilith-os-api.service
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8765/system/status   # expect 200
sudo sha256sum /home/lilith/.hermes/lilith-os/api/app.py                        # expect 340358764024...
```

## Deploy method (for reproducibility)
`gcloud compute ssh --tunnel-through-iap` (read/verify); block staged via `gcloud compute scp` to `/tmp`; appended with `sudo -u lilith tee -a app.py`; `ast.parse` syntax gate before restart; `sudo systemctl restart lilith-os-api.service` (no `daemon-reload`); health + regression checks. Belief writes have no HTTP surface — ingestion is internal Python only; `VERIFIED` only via the verification path.
