"""Slice 7.1 World Model Operationalization tests. THROWAWAY temp DB — never lilith.db."""
import sys, os, tempfile, sqlite3, json, traceback

API_DIR = "/home/lilith/.hermes/lilith-os/api"
sys.path.insert(0, API_DIR)
import app

_tmpdir = tempfile.mkdtemp(prefix="wm71_")
TMPDB = os.path.join(_tmpdir, "test.db")
app.DB = TMPDB
app._world_schema_ready = False

results = []
def check(name, cond, detail=""):
    results.append((name, bool(cond), "" if cond else str(detail)))

def raw():
    c = sqlite3.connect(TMPDB); c.row_factory = sqlite3.Row; return c

def belief(key):
    c = raw()
    try:
        r = c.execute("SELECT * FROM world_belief WHERE key=?", (key,)).fetchone()
        return dict(r) if r else None
    finally:
        c.close()

def evcount(key=None):
    c = raw()
    try:
        if key:
            return c.execute("SELECT COUNT(*) n FROM world_belief_evidence WHERE belief_key=?", (key,)).fetchone()[0]
        return c.execute("SELECT COUNT(*) n FROM world_belief_evidence").fetchone()[0]
    finally:
        c.close()

def cursor_val():
    c = raw()
    try:
        r = c.execute("SELECT last_id FROM world_ingest_cursor WHERE name='career_events'").fetchone()
        return r["last_id"] if r else None
    finally:
        c.close()

# Build a minimal, realistic Slice-1 fixture in the temp DB.
def seed_career():
    c = raw()
    c.executescript(
        "CREATE TABLE IF NOT EXISTS companies (id INTEGER PRIMARY KEY, name TEXT);"
        "CREATE TABLE IF NOT EXISTS job_applications (id INTEGER PRIMARY KEY, company_id INTEGER,"
        " role_title TEXT, stage TEXT, status TEXT, source_account TEXT, last_activity TEXT);"
        "CREATE TABLE IF NOT EXISTS career_events (id INTEGER PRIMARY KEY, event_type TEXT,"
        " entity_type TEXT, entity_id INTEGER, source TEXT, confidence REAL, payload_json TEXT,"
        " created_at TEXT, processed INTEGER DEFAULT 0);")
    c.execute("INSERT OR REPLACE INTO companies (id,name) VALUES (1,'Acme')")
    c.execute("INSERT OR REPLACE INTO job_applications (id,company_id,role_title,stage,status,source_account,last_activity)"
              " VALUES (4,1,'Engineer','applied','active','acct1','2026-09-01T00:00:00Z')")
    c.execute("INSERT OR REPLACE INTO career_events (id,event_type,entity_type,entity_id,source,confidence,created_at)"
              " VALUES (4,'career.applied','job_application',4,'gmail',0.8,'2026-09-01T00:00:00Z')")
    c.commit(); c.close()

# T1 — a career event automatically reaches the World Model (no manual world_ingest_career)
try:
    seed_career()
    r = app.world_ingest_from_events()
    b = belief("career.application:4:status")
    ev = raw(); prov = ev.execute("SELECT origin_ref FROM world_belief_evidence WHERE belief_key='career.application:4:status'").fetchall(); ev.close()
    check("T1_event_reaches_world",
          r["new_events"] == 1 and b and json.loads(b["value_json"]) == "applied"
          and any(p["origin_ref"] == "career_events/4" for p in prov),
          "r=%s b=%s prov=%s" % (r, b, [dict(p) for p in prov]))
except Exception:
    check("T1_event_reaches_world", False, traceback.format_exc())

# T2 — repeated processing is idempotent (cursor stable, no duplicate evidence)
try:
    ev_before = evcount("career.application:4:status")
    cur_before = cursor_val()
    r2 = app.world_ingest_from_events()
    ev_after = evcount("career.application:4:status")
    check("T2_idempotent_reprocess",
          r2["new_events"] == 0 and ev_after == ev_before and cursor_val() == cur_before,
          "r2=%s ev %s->%s cur=%s" % (r2, ev_before, ev_after, cursor_val()))
except Exception:
    check("T2_idempotent_reprocess", False, traceback.format_exc())

# T3 — restart does not duplicate (cursor persists across a simulated reload)
try:
    app._world_schema_ready = False  # simulate process restart
    ev_before = evcount()
    r3 = app.world_ingest_from_events()
    check("T3_restart_no_duplicate",
          r3["new_events"] == 0 and evcount() == ev_before and cursor_val() == 4,
          "r3=%s ev=%s cur=%s" % (r3, evcount(), cursor_val()))
except Exception:
    check("T3_restart_no_duplicate", False, traceback.format_exc())

# T4a — event referencing a non-existent application is skipped (no fabrication)
try:
    c = raw()
    c.execute("INSERT INTO career_events (id,event_type,entity_type,entity_id,source,confidence,created_at)"
              " VALUES (5,'career.discovered','job_application',99999,'gmail',0.8,'2026-09-02T00:00:00Z')")
    c.commit(); c.close()
    app.world_ingest_from_events()
    check("T4a_missing_app_skipped", belief("career.application:99999:status") is None, "should be None")
except Exception:
    check("T4a_missing_app_skipped", False, traceback.format_exc())

# T4b — malformed/unavailable field (NULL stage) cannot corrupt an existing belief
try:
    before = belief("career.application:4:status")  # 'applied'
    c = raw()
    c.execute("UPDATE job_applications SET stage=NULL WHERE id=4")
    c.execute("INSERT INTO career_events (id,event_type,entity_type,entity_id,source,confidence,created_at)"
              " VALUES (6,'career.applied','job_application',4,'gmail',0.8,'2026-09-03T00:00:00Z')")
    c.commit(); c.close()
    app.world_ingest_from_events()
    after = belief("career.application:4:status")
    check("T4b_null_no_overwrite",
          after and json.loads(after["value_json"]) == "applied" and after["lifecycle_state"] == "ACTIVE",
          "before=%s after=%s" % (before and before["value_json"], after and after["value_json"]))
except Exception:
    check("T4b_null_no_overwrite", False, traceback.format_exc())

# T5 — freshness maintenance marks an expired belief STALE via the maintenance tick
try:
    app.submit_observation("t.fresh", "1", "x", "v", observed_at="2020-01-01T00:00:00Z",
                           expires_at="2020-06-01T00:00:00Z")
    tick = app._world_maint_tick()
    b = belief("t.fresh:1:x")
    check("T5_tick_marks_stale",
          b["lifecycle_state"] == "STALE" and "sweep" in tick and tick["sweep"]["staled"] >= 1,
          "b_life=%s tick=%s" % (b["lifecycle_state"], tick))
except Exception:
    check("T5_tick_marks_stale", False, traceback.format_exc())

# T6 — a fresh belief (no expiry) stays ACTIVE across a maintenance tick
try:
    app.submit_observation("t.fresh", "2", "x", "v", observed_at="2026-01-01T00:00:00Z")
    app._world_maint_tick()
    b = belief("t.fresh:2:x")
    check("T6_fresh_stays_active", b["lifecycle_state"] == "ACTIVE", "life=%s" % b["lifecycle_state"])
except Exception:
    check("T6_fresh_stays_active", False, traceback.format_exc())

# T7 — a failing ingestion step does not corrupt the store and the tick still sweeps
try:
    b_before = belief("career.application:4:status")
    orig = app.world_ingest_from_events
    def boom(*a, **k):
        raise RuntimeError("simulated ingest failure")
    app.world_ingest_from_events = boom
    tick = app._world_maint_tick()
    app.world_ingest_from_events = orig  # restore
    b_after = belief("career.application:4:status")
    check("T7_failure_no_corruption",
          "ingest_error" in tick and "sweep" in tick
          and b_after and b_after["value_json"] == b_before["value_json"],
          "tick=%s belief_stable=%s" % (tick, b_after and b_after["value_json"] == b_before["value_json"]))
except Exception:
    try:
        app.world_ingest_from_events = orig
    except Exception:
        pass
    check("T7_failure_no_corruption", False, traceback.format_exc())

# T8 — a genuinely new event is picked up incrementally and advances the cursor
try:
    c = raw()
    c.execute("UPDATE job_applications SET stage='interviewing' WHERE id=4")
    c.execute("INSERT INTO career_events (id,event_type,entity_type,entity_id,source,confidence,created_at)"
              " VALUES (7,'career.applied','job_application',4,'gmail',0.9,'2026-09-04T00:00:00Z')")
    c.commit(); c.close()
    r = app.world_ingest_from_events()
    b = belief("career.application:4:status")
    check("T8_incremental_new_event",
          r["new_events"] == 1 and json.loads(b["value_json"]) == "interviewing" and cursor_val() == 7,
          "r=%s b=%s cur=%s" % (r, b and b["value_json"], cursor_val()))
except Exception:
    check("T8_incremental_new_event", False, traceback.format_exc())

# ---- report ----
print("=== SLICE 7.1 OPERATIONAL TEST RESULTS ===")
passed = 0
for name, ok, detail in results:
    line = "%-34s %s" % (name, "PASS" if ok else "FAIL")
    if not ok:
        line += "  :: " + detail.replace("\n", " | ")[:400]
    print(line)
    passed += 1 if ok else 0
print("SUMMARY: %d/%d passed" % (passed, len(results)))
import shutil
shutil.rmtree(_tmpdir, ignore_errors=True)
sys.exit(0 if passed == len(results) else 1)
