

# ============================================================================
# BEGIN SLICE 7.1 — WORLD MODEL OPERATIONALIZATION  [additive; append-only]
# Automatic event-driven ingestion from career_events + scheduled freshness.
# Reuses Slice 7 primitives (submit_observation, world_freshness_sweep,
# _ensure_world_schema, _world_key, _wm_now, db, DB, json). No Slice 1-6 changes;
# no new HTTP mutation surface; no schema change to existing tables (adds one
# additive world_* table: world_ingest_cursor). NOT Goal/Executive/Workspace/
# Motivation/Ethics/Reasoning — pure maintenance of the existing belief store.
# ============================================================================

def _ensure_world_ingest_schema(conn):
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS world_ingest_cursor ("
        " name TEXT PRIMARY KEY, last_id INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL);"
    )
    conn.commit()


def _world_cursor_get(conn, name):
    r = conn.execute("SELECT last_id FROM world_ingest_cursor WHERE name=?", (name,)).fetchone()
    return r["last_id"] if r else 0


def _world_cursor_set(conn, name, last_id):
    conn.execute(
        "INSERT INTO world_ingest_cursor (name, last_id, updated_at) VALUES (?,?,?) "
        "ON CONFLICT(name) DO UPDATE SET last_id=excluded.last_id, updated_at=excluded.updated_at",
        (name, int(last_id), _wm_now()))


def _world_ingest_one(conn, entity_type, entity_id, predicate, value, prov):
    """Idempotent single-observation ingest. Skips when identical evidence for the
    same (belief_key, origin_ref, value) already exists (defence-in-depth beyond
    the cursor), and skips None values (unavailable field never overwrites).
    Returns True iff an observation was actually submitted."""
    if value is None:
        return False
    key = _world_key(entity_type, str(entity_id), predicate)
    origin = prov.get("origin_ref")
    vj = json.dumps(value, sort_keys=True, ensure_ascii=False)
    if origin:
        dup = conn.execute(
            "SELECT 1 FROM world_belief_evidence WHERE belief_key=? AND origin_ref=? AND value_json=? LIMIT 1",
            (key, origin, vj)).fetchone()
        if dup:
            return False
    submit_observation(entity_type, entity_id, predicate, value, conn=conn, **prov)
    return True


def world_ingest_from_events(limit=1000):
    """Event-driven World Model ingestion. Consumes NEW career_events (id > cursor)
    and refreshes the affected application beliefs from job_applications (the
    watcher's reconciled current state), then advances the cursor. Idempotent and
    restart-safe: the cursor marks progress; per-evidence dedup guarantees no
    duplicate evidence even if the same events are reprocessed after a crash before
    the cursor advanced. Never fabricates predicates; a missing application or NULL
    field is skipped, never written as an empty value."""
    conn = db()
    try:
        _ensure_world_schema(conn)
        _ensure_world_ingest_schema(conn)
        last = _world_cursor_get(conn, "career_events")
        events = conn.execute(
            "SELECT id, entity_type, entity_id, source, confidence, created_at "
            "FROM career_events WHERE id > ? ORDER BY id LIMIT ?", (last, limit)).fetchall()
        if not events:
            return {"new_events": 0, "beliefs_touched": 0, "cursor": last}
        max_id = last
        latest_evt = {}  # application id -> (event_id, source, confidence, created_at)
        for e in events:
            if e["id"] > max_id:
                max_id = e["id"]
            et = (e["entity_type"] or "").lower()
            if et in ("job_application", "application", "job_applications") and e["entity_id"] is not None:
                latest_evt[e["entity_id"]] = (e["id"], e["source"], e["confidence"], e["created_at"])
        touched = 0
        for aid, (evid, src, conf, cat) in latest_evt.items():
            row = conn.execute(
                "SELECT ja.id, ja.role_title, ja.stage, ja.last_activity, ja.source_account, "
                "c.name AS company FROM job_applications ja LEFT JOIN companies c ON c.id = ja.company_id "
                "WHERE ja.id=?", (aid,)).fetchone()
            if row is None:
                continue  # event referenced an application not present -> skip (no fabrication)
            prov = dict(source_type="career.application", source_id="career-events",
                        origin_ref="career_events/%s" % evid,
                        observed_at=cat or row["last_activity"],
                        correlation_id="evt_%s" % evid,
                        note=("acct" if row["source_account"] else None))
            for pred, val in (("status", row["stage"]), ("role", row["role_title"]),
                              ("company", row["company"]), ("last_activity", row["last_activity"])):
                if _world_ingest_one(conn, "career.application", aid, pred, val, prov):
                    touched += 1
        _world_cursor_set(conn, "career_events", max_id)
        conn.commit()
        return {"new_events": len(events), "beliefs_touched": touched, "cursor": max_id}
    finally:
        conn.close()


def _world_maint_tick():
    """One maintenance tick: event ingestion + freshness sweep. Each guarded so a
    failure in one step neither aborts the other nor corrupts the store."""
    out = {}
    try:
        out["ingest"] = world_ingest_from_events()
    except Exception as e:
        out["ingest_error"] = repr(e)
    try:
        out["sweep"] = world_freshness_sweep()
    except Exception as e:
        out["sweep_error"] = repr(e)
    return out


def _world_maintenance_loop():
    import os, time
    try:
        interval = max(15, int(os.environ.get("WORLD_MAINT_INTERVAL_SEC", "120")))
    except Exception:
        interval = 120
    while True:
        res = _world_maint_tick()
        try:
            print("[world-maint] " + json.dumps(res), flush=True)
        except Exception:
            pass
        time.sleep(interval)


_world_maint_thread = None


@app.on_event("startup")
def _world_maint_start():
    """Start the in-process maintenance scheduler when the ASGI app starts (under
    uvicorn). Not started on a bare `import app`, so tests/one-offs never spawn it.
    Smallest production-compatible scheduler: a daemon thread inside the existing
    single-worker uvicorn process — no systemd/cron changes, restart-safe, and
    failures are visible in the service journal."""
    global _world_maint_thread
    if _world_maint_thread is not None:
        return
    import threading
    _world_maint_thread = threading.Thread(target=_world_maintenance_loop, name="world-maint", daemon=True)
    _world_maint_thread.start()
    print("[world-maint] scheduler started", flush=True)

# ============================================================================
# END SLICE 7.1 — WORLD MODEL OPERATIONALIZATION
# ============================================================================
