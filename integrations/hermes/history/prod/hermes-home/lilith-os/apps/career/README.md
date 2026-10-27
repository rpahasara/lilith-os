# PROD career CRM pipeline (historical source, `lilith-01`)

These are the ten career scripts deployed on PROD at `/home/lilith/.hermes/lilith-os/apps/career/`, recovered on
2026-10-27 by the bounded read-only export. They feed the World Model events behind PROD's existing career beliefs.

**This is preserved historical source, not an active service.**
- Nothing here is installed, scheduled or run.
- It is not a second career pipeline.
- On PROD the watcher has failed since its Google OAuth grant expired (`invalid_grant`). Repairing it, and any
  integration into DEV, is separate work.

Bytes equal PROD except in four files, where the owner's two mailbox addresses are replaced by
`__OWNER_PRIMARY_EMAIL__` and `__OWNER_SECONDARY_EMAIL__`. Per-file hashes and transforms are in
`../../../../provenance/career-ingestion.json`.

## Files

| File | Role |
|---|---|
| `career_watcher.py` | Entry point. `lilith-career-watcher.timer` runs it every 15 min. It runs the extractor, then the entity resolver, and notifies Discord via `automation/productivity/discord_notifier.py` |
| `career_extractor_v2.py` | Gmail ingestion and classification; writes the CRM tables and `career_events` |
| `career_extractor_v2.before-incremental.py`, `career_extractor.py` | earlier versions (before the incremental cursor, and V1) |
| `entity_resolver.py` | merges duplicate companies and applications; asks the model whether two records are the same |
| `init_db.py` | creates the CRM schema in `lilith.db` |
| `reconcile_crm.py`, `repair_counterparties.py`, `remove_owner_test_mail.py`, `view_crm.py` | one-off repair and inspection tools |

## Ingestion contract (reconstructed statically)

1. **Source.** The two Gmail accounts are read with `google.oauth2` user tokens (`token.json` per account, kept on the
   host and never in Git). The query is `after:<epoch>`, read-only.
2. **Cursor.** Per-account `last_scan_epoch` lives in `~/.hermes/lilith-os/data/career_ingest_state.json` (mode
   0600). It is written atomically (temp file, then `replace`).
3. **Idempotency.** A message is skipped when its id already appears in `career_activities.source_message_id`.
4. **Classification.**
   - A deterministic noise and score filter runs first.
   - Remaining messages go to `lilith_classify`, which runs the Hermes CLI (`~/.local/bin/hermes --reasoning
     minimal`). **This is a provider call through Hermes.**
   - Results under 0.60 confidence are recorded as `lilith_low_confidence`.
5. **Writes** go to the SQLite file `lilith.db` (schema in `init_db.py`):
   - `companies`, `people`, `job_applications` (stages only move forward), `career_activities`;
   - one `career_events` row per classified message: `event_type='career.<stage>'`,
     `entity_type='job_application'`, `entity_id=<application id>`, `source='gmail'`, `confidence`, and `payload_json`
     holding the account, message id, thread id and classification source;
   - `processed` defaults to 0.
6. **World Model consumer.** This side is already in the repository: `services/core-api/app.py`, "Automatic
   event-driven ingestion from career_events".
   - It reads `career_events` rows with `id >` the `world_ingest_cursor['career_events']` value, joined with
     `job_applications` and `companies`.
   - It submits observations with `origin_ref='career_events/<id>'`.
   - It skips identical evidence, so reprocessing after a crash is safe.
   - The pipeline never writes World Model tables directly.
7. **Failure behaviour.**
   - A Gmail auth failure raises, and the watcher unit fails.
   - Classifier errors fall back to the deterministic result.
   - No retry loop beyond the next timer tick.

The schema test in `integrations/hermes/history/prod/tests/test_career_source.py` builds `init_db.py`'s schema in an
in-memory database. It checks that the table has every column the Core API consumer reads.
