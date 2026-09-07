"""Slice 7 World Model A-R tests. Runs against a THROWAWAY temp DB — never lilith.db."""
import sys, os, tempfile, sqlite3, json, traceback

API_DIR = "/home/lilith/.hermes/lilith-os/api"
sys.path.insert(0, API_DIR)
import app  # imports the live app.py (same module the service runs)

# Redirect all DB access to a throwaway temp file. NEVER touch lilith.db.
_tmpdir = tempfile.mkdtemp(prefix="wm_test_")
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

def evidence(key):
    c = raw()
    try:
        return [dict(x) for x in c.execute(
            "SELECT * FROM world_belief_evidence WHERE belief_key=? ORDER BY id", (key,)).fetchall()]
    finally:
        c.close()

def trace_count():
    c = raw()
    try:
        return c.execute("SELECT COUNT(*) n FROM world_belief_trace").fetchone()[0]
    finally:
        c.close()

# A — observation creates provenance-stamped belief
try:
    app.submit_observation("t.app", "1", "status", "discovered", source_id="career-store",
                           origin_ref="career_events/1", observed_at="2026-01-01T00:00:00Z")
    b = belief("t.app:1:status"); ev = evidence("t.app:1:status")
    check("A_observation_creates_belief",
          b and b["lifecycle_state"] == "ACTIVE" and b["epistemic_state"] == "OBSERVED"
          and ev and ev[0]["source_class"] == "LIVE_CONNECTOR" and ev[0]["origin_ref"] == "career_events/1",
          b)
except Exception:
    check("A_observation_creates_belief", False, traceback.format_exc())

# B — canonical key prevents duplicate rows
try:
    app.submit_observation("t.app", "2", "stage", "discovered", observed_at="2026-01-01T00:00:00Z")
    app.submit_observation("t.app", "2", "stage", "discovered", observed_at="2026-01-02T00:00:00Z")
    c = raw(); n = c.execute("SELECT COUNT(*) n FROM world_belief WHERE key=?", ("t.app:2:stage",)).fetchone()[0]; c.close()
    check("B_no_duplicate_rows", n == 1, "rows=%s" % n)
except Exception:
    check("B_no_duplicate_rows", False, traceback.format_exc())

# C — identical repeat is idempotent
try:
    app.submit_observation("t.app", "3", "stage", "x", observed_at="2026-01-01T00:00:00Z")
    r2 = app.submit_observation("t.app", "3", "stage", "x", observed_at="2026-01-01T00:00:00Z")
    b = belief("t.app:3:stage"); ev = evidence("t.app:3:stage")
    check("C_idempotent_repeat", r2["reason"] == "idempotent_corroboration" and len(ev) == 2 and b["revision"] == 1,
          "r2=%s ev=%d rev=%s" % (r2, len(ev), b["revision"]))
except Exception:
    check("C_idempotent_repeat", False, traceback.format_exc())

# D — newer equal-authority observation supersedes
try:
    app.submit_observation("t.app", "4", "stage", "discovered", observed_at="2026-01-01T00:00:00Z")
    r = app.submit_observation("t.app", "4", "stage", "interviewing", observed_at="2026-06-01T00:00:00Z")
    b = belief("t.app:4:stage")
    check("D_newer_supersedes",
          json.loads(b["value_json"]) == "interviewing" and r["action"] == "superseded" and b["revision"] == 2, b)
except Exception:
    check("D_newer_supersedes", False, traceback.format_exc())

# E — VERIFIED outranks INFERRED
try:
    app.submit_inference_candidate("t.app", "5", "stage", "guessed", observed_at="2026-01-01T00:00:00Z")
    app.apply_verified_delta("t.app", "5", "stage", "confirmed")
    b = belief("t.app:5:stage")
    check("E_verified_outranks_inferred",
          json.loads(b["value_json"]) == "confirmed" and b["epistemic_state"] == "VERIFIED" and b["confidence"] >= 0.9, b)
except Exception:
    check("E_verified_outranks_inferred", False, traceback.format_exc())

# F — stale (freshness sweep)
try:
    app.submit_observation("t.app", "6", "stage", "discovered", observed_at="2020-01-01T00:00:00Z",
                           expires_at="2020-06-01T00:00:00Z")
    sweep = app.world_freshness_sweep(now="2026-01-01T00:00:00Z")
    b = belief("t.app:6:stage")
    check("F_stale", b["lifecycle_state"] == "STALE" and json.loads(b["value_json"]) == "discovered",
          "life=%s sweep=%s" % (b["lifecycle_state"], sweep))
except Exception:
    check("F_stale", False, traceback.format_exc())

# G — equal-authority conflict -> CONFLICTED, both chains retained
try:
    app.submit_observation("t.app", "7", "stage", "alpha", observed_at="2026-01-01T00:00:00Z")
    app.submit_observation("t.app", "7", "stage", "beta", observed_at="2026-01-01T00:00:00Z")
    b = belief("t.app:7:stage"); ev = evidence("t.app:7:stage")
    c = raw(); confl = c.execute("SELECT COUNT(*) n FROM world_belief_conflict WHERE belief_key=?",
                                 ("t.app:7:stage",)).fetchone()[0]; c.close()
    check("G_conflict", b["lifecycle_state"] == "CONFLICTED" and len(ev) == 2 and confl >= 1,
          "life=%s ev=%d confl=%d" % (b["lifecycle_state"], len(ev), confl))
except Exception:
    check("G_conflict", False, traceback.format_exc())

# H — UNKNOWN stays unknown
try:
    check("H_unknown_absent", belief("t.app:999:nope") is None, "expected None")
except Exception:
    check("H_unknown_absent", False, traceback.format_exc())

# I — unavailable source does not overwrite, no trace
try:
    app.submit_observation("t.app", "8", "stage", "discovered", observed_at="2026-01-01T00:00:00Z")
    tc0 = trace_count()
    r = app.submit_observation("t.app", "8", "stage", None)
    b = belief("t.app:8:stage"); ev = evidence("t.app:8:stage"); tc1 = trace_count()
    check("I_unavailable_no_overwrite",
          r["reason"] == "source_unavailable_noop" and json.loads(b["value_json"]) == "discovered"
          and len(ev) == 1 and tc1 == tc0,
          "r=%s val=%s ev=%d dtrace=%d" % (r, b["value_json"], len(ev), tc1 - tc0))
except Exception:
    check("I_unavailable_no_overwrite", False, traceback.format_exc())

# J — no HTTP mutation route on the world model
try:
    world_routes = [(str(getattr(rt, "path", "")), getattr(rt, "methods", None))
                    for rt in app.app.routes if str(getattr(rt, "path", "")).startswith("/os/world")]
    mutating = [wr for wr in world_routes if wr[1] and (set(wr[1]) & {"POST", "PUT", "PATCH", "DELETE"})]
    check("J_no_world_mutation_route", len(world_routes) >= 1 and len(mutating) == 0, "routes=%s" % world_routes)
except Exception:
    check("J_no_world_mutation_route", False, traceback.format_exc())

# K — no generic setter; only controlled ingestion exists
try:
    has_setter = any(hasattr(app, n) for n in ["set_belief", "setBelief", "world_set", "upsert_belief"])
    have_controlled = all(hasattr(app, n) for n in
                          ["submit_observation", "submit_user_assertion", "submit_inference_candidate", "apply_verified_delta"])
    check("K_no_generic_setter", (not has_setter) and have_controlled,
          "setter=%s controlled=%s" % (has_setter, have_controlled))
except Exception:
    check("K_no_generic_setter", False, traceback.format_exc())

# L — working memory is a selected subset only
try:
    for i in range(20):
        app.submit_observation("t.ws", str(i), "p", "v%d" % i, observed_at="2026-01-01T00:00:00Z")
    ws = app.build_working_set("sessL", focus_entities=[("t.ws", "0")], capacity=5)
    check("L_subset", len(ws["activeBeliefIds"]) == 5, "n=%d" % len(ws["activeBeliefIds"]))
except Exception:
    check("L_subset", False, traceback.format_exc())

# M — capacity bound respected
try:
    ws3 = app.build_working_set("sessM", capacity=3)
    ws0 = app.build_working_set("sessM", capacity=0)
    check("M_capacity_bound", len(ws3["activeBeliefIds"]) <= 3 and len(ws0["activeBeliefIds"]) == 0,
          "c3=%d c0=%d" % (len(ws3["activeBeliefIds"]), len(ws0["activeBeliefIds"])))
except Exception:
    check("M_capacity_bound", False, traceback.format_exc())

# N — reconstructs identically after a simulated reload; not durably stored
try:
    a = app.build_working_set("sessN", focus_entities=[("t.ws", "1")], capacity=8)
    app._world_schema_ready = False  # simulate process reload
    b = app.build_working_set("sessN", focus_entities=[("t.ws", "1")], capacity=8)
    c = raw(); seed = c.execute("SELECT COUNT(*) n FROM world_working_seed").fetchone()[0]; c.close()
    check("N_reconstruct_identical", a["activeBeliefIds"] == b["activeBeliefIds"] and seed == 0,
          "eq=%s seed=%d" % (a["activeBeliefIds"] == b["activeBeliefIds"], seed))
except Exception:
    check("N_reconstruct_identical", False, traceback.format_exc())

# O — a trace row for every mutation
try:
    before = trace_count()
    app.submit_observation("t.o", "1", "p", "a", observed_at="2026-01-01T00:00:00Z")
    app.submit_observation("t.o", "2", "p", "a", observed_at="2026-01-01T00:00:00Z")
    app.submit_observation("t.o", "3", "p", "a", observed_at="2026-01-01T00:00:00Z")
    after = trace_count()
    check("O_trace_per_mutation", after - before == 3, "delta=%d" % (after - before))
except Exception:
    check("O_trace_per_mutation", False, traceback.format_exc())

# P — provenance + correlation persist across a reopen
try:
    app.submit_observation("t.p", "1", "p", "v", correlation_id="corrP", source_id="sidP",
                           observed_at="2026-01-01T00:00:00Z")
    c = raw(); ev = c.execute("SELECT correlation_id, source_id FROM world_belief_evidence WHERE belief_key=?",
                              ("t.p:1:p",)).fetchall(); c.close()
    check("P_provenance_persists", any(e["correlation_id"] == "corrP" and e["source_id"] == "sidP" for e in ev),
          "ev=%s" % [dict(e) for e in ev])
except Exception:
    check("P_provenance_persists", False, traceback.format_exc())

# Q — Career ingestion works against the real column shape
try:
    c = raw()
    c.executescript(
        "CREATE TABLE IF NOT EXISTS companies (id INTEGER PRIMARY KEY, name TEXT);"
        "CREATE TABLE IF NOT EXISTS job_applications (id INTEGER PRIMARY KEY, company_id INTEGER,"
        " role_title TEXT, stage TEXT, status TEXT, source_account TEXT, last_activity TEXT);")
    c.execute("INSERT INTO companies (id,name) VALUES (1,'Acme')")
    c.execute("INSERT INTO job_applications (id,company_id,role_title,stage,status,source_account,last_activity)"
              " VALUES (1,1,'Engineer','interviewing','active','gmail','2026-09-01T00:00:00Z')")
    c.commit(); c.close()
    r = app.world_ingest_career()
    b = belief("career.application:1:status")
    check("Q_career_ingest", r["observations"] >= 1 and b and json.loads(b["value_json"]) == "interviewing",
          "r=%s b=%s" % (r, b))
except Exception:
    check("Q_career_ingest", False, traceback.format_exc())

# R — Slice 1-6 routes intact
try:
    paths = set(str(getattr(rt, "path", "")) for rt in app.app.routes)
    needed = ["/os/tasks", "/os/drafts", "/career/activity", "/system/status",
              "/memory/records", "/os/overview", "/os/conversation"]
    missing = [p for p in needed if p not in paths]
    check("R_slice1_6_routes_intact", not missing, "missing=%s" % missing)
except Exception:
    check("R_slice1_6_routes_intact", False, traceback.format_exc())

# ---- report ----
print("=== SLICE 7 A-R TEST RESULTS ===")
passed = 0
for name, ok, detail in results:
    line = "%-38s %s" % (name, "PASS" if ok else "FAIL")
    if not ok:
        line += "  :: " + detail.replace("\n", " | ")[:400]
    print(line)
    passed += 1 if ok else 0
print("SUMMARY: %d/%d passed" % (passed, len(results)))

import shutil
shutil.rmtree(_tmpdir, ignore_errors=True)
sys.exit(0 if passed == len(results) else 1)
