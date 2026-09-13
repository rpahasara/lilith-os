# Slice 7.1 — World Model Operationalization: Deployment Record

> Makes the already-passed World Model maintain itself automatically from the existing Slice 1 observation infrastructure. **Not** Slice 8: no Goal/Executive, Global Workspace, Motivation, Reasoning, Ethics, connectors, OAuth, or Hsin/Presence changes.

## Summary
| | |
|---|---|
| **Date** | 2026-09-07 |
| **Target** | `lilith-01` · `app.py` · `lilith.db` · `lilith-os-api.service` (port 8765) |
| **Change shape** | One appended `# BEGIN/END SLICE 7.1` block. Additive; no edits to Slice 1–7 code; one additive `world_*` table (`world_ingest_cursor`). |
| **Verdict** | **PASSED** |

## Hashes
| Artifact | Value |
|---|---|
| `app.py` starting sha256 (Slice 7) | `90083ddb4a64ae350850d3a1b53d56bf9d86f48dc7ef963eb990fc75293e8cde` |
| `app.py` final sha256 (Slice 7.1) | `f44396c58e2f34dc9e1820ce69bebf217eb088ecf9ea3b5853c878843dd48d45` |
| appended 7.1 block sha256 | `f0916380dbd88bb187704b5deb238537d47df4321e6aa2b48ca163b98a356e4e` (7,021 bytes) |
| `app.py` size | 84,241 → 91,262 bytes |

## Backups (created before change)
- `/home/lilith/.hermes/lilith-os/api/app.py.bak.20260907-173941` (Slice 7 baseline, sha `90083ddb…`).
- `/home/lilith/.hermes/lilith-os/data/lilith.before-world-7-1.db` (proper SQLite `.backup()`).

## Automatic ingestion architecture
`career_events` (Slice 1 watcher output) → **`world_ingest_from_events()`** → `submit_observation()` → deterministic reconciliation → World Model.
- **Cursor:** additive `world_ingest_cursor` table stores a highwater on `career_events.id`. `career_events.processed` is **left untouched** (nothing in `app.py` uses it). Restart-safe: the cursor persists in the DB.
- **Idempotency (defence in depth):** the cursor skips already-seen events; additionally `_world_ingest_one()` skips when identical evidence for the same `(belief_key, origin_ref, value)` already exists — so reprocessing after a crash-before-cursor-advance never duplicates evidence.
- **Event-time semantics:** an observation is timestamped with the **event's `created_at`** (the event *is* the observation), so a newer `career_event` supersedes an older belief value (reconciliation R3); equal-time differing values become `CONFLICTED`, never silently overwritten.
- **No fabrication:** only real predicates `status` (`job_applications.stage`), `role` (`role_title`), `company` (`companies.name`), `last_activity` are emitted; a missing application row or NULL field is skipped, never written as empty. `follow_up` is still not emitted.
- **No new HTTP mutation surface;** ingestion remains internal Python only.

## Scheduler design
**Smallest production-compatible mechanism: an in-process daemon thread** inside the existing single-worker uvicorn process, started by a `@app.on_event("startup")` hook.
- Chosen deliberately to require **zero systemd/cron changes** (the existing systemd-unit drift stays out of scope; **no `daemon-reload`**).
- Restart-safe (starts on every service start); **not** started on a bare `import app`, so tests/one-offs never spawn it.
- Each tick runs `world_ingest_from_events()` + `world_freshness_sweep()`, each guarded so one failing step neither aborts the other nor corrupts the store.
- Interval: `WORLD_MAINT_INTERVAL_SEC` env (default **120s**, floor 15s). No busy loop (`time.sleep`).
- Observable: every tick logs `[world-maint] {…}` to the service journal.

## Tests
- **Slice 7 A–R: 18/18 PASS** (regression, re-run against the updated `app.py`).
- **Slice 7.1 operational: 9/9 PASS** (`test_world_operational.py`): event→world, idempotent reprocess, restart-no-duplicate, missing-app skipped, NULL-field no-overwrite, tick marks stale, fresh stays active, failing-step no-corruption, incremental new-event supersede.

## Live production acceptance
- On restart the scheduler logged `scheduler started` then an **automatic** first tick — `ingest: {new_events: 11, beliefs_touched: 31, cursor: 17}` — ingesting the 11 real `career_events` **without** any manual `world_ingest_career()` call.
- `career.application:14:status` now carries **event-sourced provenance**: origins `["career_events/14", "job_applications/14"]`, 3 evidence rows, trace present; value `"applied"`, `ACTIVE`.
- Cursor persisted at 17; durable counts beliefs=31, evidence 62→93 (one `career_events` evidence per belief).
- **Periodic scheduling proven:** a second tick fired 120s later (`sweep: {staled: 1}`), automatically marking a seeded expired belief `STALE` — scheduled freshness working. Synthetic demo rows cleaned up; real beliefs untouched (31).

## Restart-persistence (7.1)
Second restart (PID 204314→204602): scheduler re-started; startup tick `new_events:0, cursor:17` → **cursor persisted, no duplicate processing**; evidence stable at 93; beliefs 31.

## Regressions / integrity
Slice 1–6 endpoints all 200; `integrity_check=ok`; `tasks=7, drafts=6, job_applications=8, career_events=11` unchanged. `NeedDaemonReload=yes` remains pre-existing/untouched.

## Known gaps
- Interval is fixed by env (default 120s); no jitter/backoff (not needed at this scale).
- `career_events` payload fields (message_id/thread_id/account) are not ingested — only the reconciled application state is observed (privacy-preserving; `source_account` is recorded as a bare `acct` marker, not its value).
- `apply_verified_delta` (VERIFIED) still unused pending a Verification layer.
- Freshness has no TTL policy yet — career beliefs carry no `expires_at`, so they never auto-stale; the sweep is proven but only acts on beliefs that set an expiry.

## Rollback procedure
```bash
sudo -u lilith cp -a /home/lilith/.hermes/lilith-os/api/app.py.bak.20260907-173941 \
     /home/lilith/.hermes/lilith-os/api/app.py     # restores Slice 7 (sha 90083ddb…)
sudo systemctl restart lilith-os-api.service        # restart only — never daemon-reload
systemctl is-active lilith-os-api.service
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8765/system/status   # expect 200
```
The `world_ingest_cursor` table is additive and inert once the 7.1 code is gone; no DB rollback is required (snapshot `lilith.before-world-7-1.db` is available if ever needed).
