# Slice 7 Phase B — Production Change Set (FOR REVIEW — NOT APPLIED)

> **Status:** Proposed. **Nothing in here has been applied to the VM.** No `app.py` edit, no `lilith.db` change, no service restart, no `daemon-reload`.
> **Target:** `lilith-01` · `/home/lilith/.hermes/lilith-os/api/app.py` · DB `/home/lilith/.hermes/lilith-os/data/lilith.db` · service `lilith-os-api.service` (port 8765).
> **Baseline checksums (recon 2026-09-07):** `app.py` sha256 `340358764024a83b4425484423b45417d70b4cf75d4e204c4576a89c26ff6c9e`; `lilith.db` sha256 `90330456578d3642ff05b6b8e5d345f20cf32129225decd4432bb11d5b68e3c8`.
> **Spec:** [slice-7-world-model-backend-spec.md](./slice-7-world-model-backend-spec.md) (reconciled to production).

## A. Shape of the change
- **One file touched:** `app.py`. The change is a single **appended block** (delimited by `# BEGIN/END SLICE 7`) — no edits to existing Slice 1–6 lines. Route handlers and helpers appended at end resolve `app`, `DB`, `db`, `sqlite3`, `json`, `datetime`, `timezone`, `HTTPException` — all already imported/defined at the top of `app.py` (verified in recon).
- **Additive DB only:** new `world_*` tables created lazily via `_ensure_world_schema()` on first world-path access (mirrors the existing inline `tasks`/`drafts` bootstrap). No change to existing tables. `PRAGMA user_version` stays 0.
- **Reads are read-only** (`mode=ro` + `busy_timeout`) — safe under `journal_mode=delete`.
- **No new HTTP mutation surface.** Belief writes happen only through internal Python functions; the only new routes are two **GET** reads.

---

## B. Exact proposed `app.py` addition

Appended verbatim (finalized/tested at apply-time). Reuses existing module names.

```python
# ============================================================================
# BEGIN SLICE 7 — WORLD MODEL + WORKING MEMORY (Phase B)  [additive; append-only]
# Uses existing module globals: app, DB, db, sqlite3, json, datetime, timezone,
# HTTPException. No changes to Slice 1-6 code above this marker.
# ============================================================================

WORLD_SCHEMA_VERSION = 1

_WORLD_EPISTEMIC = ("OBSERVED", "USER_ASSERTED", "INFERRED", "VERIFIED")
_EPI_RANK = {"INFERRED": 1, "OBSERVED": 2, "USER_ASSERTED": 2, "VERIFIED": 3}
_EPI_BASE = {"VERIFIED": 0.98, "OBSERVED": 0.80, "USER_ASSERTED": 0.80, "INFERRED": 0.45}
_EPI_WEIGHT = {"VERIFIED": 1.0, "OBSERVED": 0.7, "USER_ASSERTED": 0.7, "INFERRED": 0.4}
_LIFECYCLE_WEIGHT = {"ACTIVE": 1.0, "CONFLICTED": 0.6, "STALE": 0.4, "SUPERSEDED": 0.0}
_ACTIVE_CONFIDENCE_FLOOR = 0.15
_DEFAULT_WORKING_CAPACITY = 12
_world_schema_ready = False


def _wm_now():
    return datetime.now(timezone.utc).isoformat()


def _world_key(entity_type, entity_id, predicate):
    return "%s:%s:%s" % (entity_type, entity_id, predicate)


def _ensure_world_schema(conn):
    """Idempotent inline bootstrap — production has no migration runner."""
    global _world_schema_ready
    if _world_schema_ready:
        return
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS world_belief (
          key TEXT PRIMARY KEY, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
          predicate TEXT NOT NULL, value_json TEXT NOT NULL,
          lifecycle_state TEXT NOT NULL, epistemic_state TEXT NOT NULL,
          confidence REAL NOT NULL, confidence_tier TEXT NOT NULL, confidence_basis TEXT NOT NULL,
          observed_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          expires_at TEXT, revision INTEGER NOT NULL DEFAULT 1);
        CREATE INDEX IF NOT EXISTS ix_world_belief_entity ON world_belief(entity_type, entity_id);
        CREATE INDEX IF NOT EXISTS ix_world_belief_lifecycle ON world_belief(lifecycle_state);
        CREATE TABLE IF NOT EXISTS world_belief_evidence (
          id INTEGER PRIMARY KEY AUTOINCREMENT, belief_key TEXT NOT NULL,
          source_class TEXT NOT NULL, source_id TEXT, source_type TEXT, correlation_id TEXT,
          value_json TEXT NOT NULL, epistemic_state TEXT NOT NULL, confidence REAL NOT NULL,
          observed_at TEXT, ingested_at TEXT NOT NULL, origin_ref TEXT, content_hash TEXT,
          note TEXT, superseded INTEGER NOT NULL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS ix_world_evidence_key ON world_belief_evidence(belief_key, ingested_at);
        CREATE TABLE IF NOT EXISTS world_belief_conflict (
          belief_key TEXT NOT NULL, conflict_ref TEXT NOT NULL, detected_at TEXT NOT NULL,
          reason TEXT NOT NULL, resolved_at TEXT, PRIMARY KEY (belief_key, conflict_ref));
        CREATE TABLE IF NOT EXISTS world_belief_trace (
          id INTEGER PRIMARY KEY AUTOINCREMENT, correlation_id TEXT NOT NULL,
          belief_key TEXT NOT NULL, at TEXT NOT NULL, prev_lifecycle TEXT,
          new_lifecycle TEXT NOT NULL, prev_epistemic TEXT, new_epistemic TEXT NOT NULL,
          confidence REAL NOT NULL, confidence_basis TEXT NOT NULL, source_class TEXT NOT NULL,
          reconciliation_reason TEXT NOT NULL, superseded_keys TEXT, conflict_keys TEXT);
        CREATE INDEX IF NOT EXISTS ix_world_trace_key ON world_belief_trace(belief_key, at);
        CREATE INDEX IF NOT EXISTS ix_world_trace_corr ON world_belief_trace(correlation_id);
        CREATE TABLE IF NOT EXISTS world_working_seed (
          session_id TEXT PRIMARY KEY, task_id TEXT, focus_json TEXT,
          capacity INTEGER NOT NULL DEFAULT 12, updated_at TEXT NOT NULL);
        """
    )
    conn.commit()
    _world_schema_ready = True


def _world_ro_conn():
    """Read-only connection (mode=ro + busy_timeout) — safe under rollback journal."""
    conn = sqlite3.connect("file:" + str(DB) + "?mode=ro", uri=True, timeout=2.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout=2000")
    except sqlite3.OperationalError:
        pass
    return conn


def _world_confidence(epistemic, corroborations, lifecycle):
    """Explainable, rule-derived confidence (spec S7). Returns (value, tier, basis)."""
    base = _EPI_BASE.get(epistemic, 0.45)
    basis = epistemic.lower()
    adj = 0.0
    if corroborations > 0:
        adj += min(0.15, 0.05 * corroborations)
        basis = "%s+%dcorrob" % (epistemic.lower(), corroborations)
    if lifecycle == "CONFLICTED":
        adj -= 0.20
        basis = "conflicted_penalty"
    elif lifecycle == "STALE":
        adj -= 0.15
        basis = "stale_penalty"
    val = max(0.0, min(1.0, base + adj))
    tier = ("high" if val >= 0.80 else "medium" if val >= 0.55
            else "low" if val >= _ACTIVE_CONFIDENCE_FLOOR else "unknown")
    return round(val, 4), tier, basis


def _world_trace(conn, corr, key, at, prev_life, new_life, prev_epi, new_epi,
                 conf, basis, source_class, reason, superseded=None, conflict=None):
    conn.execute(
        "INSERT INTO world_belief_trace (correlation_id, belief_key, at, prev_lifecycle,"
        " new_lifecycle, prev_epistemic, new_epistemic, confidence, confidence_basis,"
        " source_class, reconciliation_reason, superseded_keys, conflict_keys)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (corr, key, at, prev_life, new_life, prev_epi, new_epi, conf, basis,
         source_class, reason, json.dumps(superseded or []), json.dumps(conflict or [])),
    )


def _world_reconcile(conn, entity_type, entity_id, predicate, value, epistemic,
                     source_class, source_id=None, source_type=None,
                     correlation_id=None, observed_at=None, origin_ref=None,
                     note=None, expires_at=None):
    """Deterministic reconciliation R0-R8. INTERNAL ONLY (no HTTP surface)."""
    if epistemic not in _WORLD_EPISTEMIC:
        raise ValueError("bad epistemic state")
    _ensure_world_schema(conn)
    key = _world_key(entity_type, str(entity_id), predicate)
    now = _wm_now()
    corr = correlation_id or ("wm_" + now)
    vjson = json.dumps(value, sort_keys=True, ensure_ascii=False)

    conn.execute(
        "INSERT INTO world_belief_evidence (belief_key, source_class, source_id, source_type,"
        " correlation_id, value_json, epistemic_state, confidence, observed_at, ingested_at,"
        " origin_ref, note, superseded) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)",
        (key, source_class, source_id, source_type, corr, vjson, epistemic,
         _EPI_BASE.get(epistemic, 0.45), observed_at, now, origin_ref, note),
    )
    row = conn.execute("SELECT * FROM world_belief WHERE key=?", (key,)).fetchone()

    # R0 — no current belief
    if row is None:
        conf, tier, basis = _world_confidence(epistemic, 0, "ACTIVE")
        conn.execute(
            "INSERT INTO world_belief (key, entity_type, entity_id, predicate, value_json,"
            " lifecycle_state, epistemic_state, confidence, confidence_tier, confidence_basis,"
            " observed_at, created_at, updated_at, expires_at, revision)"
            " VALUES (?,?,?,?,?, 'ACTIVE', ?,?,?,?,?,?,?,?, 1)",
            (key, entity_type, str(entity_id), predicate, vjson, epistemic, conf, tier,
             basis, observed_at, now, now, expires_at),
        )
        _world_trace(conn, corr, key, now, None, "ACTIVE", None, epistemic, conf, basis,
                     source_class, "first_evidence")
        conn.commit()
        return {"key": key, "action": "created", "revision": 1, "reason": "first_evidence"}

    cur_life, cur_epi, cur_val, rev = (row["lifecycle_state"], row["epistemic_state"],
                                       row["value_json"], row["revision"])
    new_rank, cur_rank = _EPI_RANK[epistemic], _EPI_RANK.get(cur_epi, 1)

    # R1 — identical value: idempotent corroboration
    if vjson == cur_val:
        corrob = conn.execute(
            "SELECT COUNT(*) c FROM world_belief_evidence WHERE belief_key=? AND value_json=?",
            (key, vjson)).fetchone()["c"] - 1
        life = "ACTIVE" if cur_life in ("STALE", "CONFLICTED") else cur_life
        eff_epi = epistemic if new_rank >= cur_rank else cur_epi
        conf, tier, basis = _world_confidence(eff_epi, corrob, life)
        conn.execute("UPDATE world_belief SET lifecycle_state=?, epistemic_state=?, confidence=?,"
                     " confidence_tier=?, confidence_basis=?, updated_at=? WHERE key=?",
                     (life, eff_epi, conf, tier, basis, now, key))
        if life != cur_life:
            conn.execute("UPDATE world_belief_conflict SET resolved_at=? WHERE belief_key=?"
                         " AND resolved_at IS NULL", (now, key))
        _world_trace(conn, corr, key, now, cur_life, life, cur_epi, eff_epi, conf, basis,
                     source_class, "idempotent_corroboration")
        conn.commit()
        return {"key": key, "action": "updated" if life != cur_life else "noop",
                "revision": rev, "reason": "idempotent_corroboration"}

    # R2 — new higher authority supersedes
    if new_rank > cur_rank:
        conn.execute("UPDATE world_belief_evidence SET superseded=1 WHERE belief_key=? AND id <"
                     " (SELECT MAX(id) FROM world_belief_evidence WHERE belief_key=?)", (key, key))
        rev += 1
        conf, tier, basis = _world_confidence(epistemic, 0, "ACTIVE")
        reason = ("verified_outranks_%s" % cur_epi.lower() if epistemic == "VERIFIED"
                  else "higher_authority_supersedes")
        conn.execute("UPDATE world_belief SET value_json=?, lifecycle_state='ACTIVE',"
                     " epistemic_state=?, confidence=?, confidence_tier=?, confidence_basis=?,"
                     " observed_at=?, updated_at=?, expires_at=?, revision=? WHERE key=?",
                     (vjson, epistemic, conf, tier, basis, observed_at, now, expires_at, rev, key))
        conn.execute("UPDATE world_belief_conflict SET resolved_at=? WHERE belief_key=?"
                     " AND resolved_at IS NULL", (now, key))
        _world_trace(conn, corr, key, now, cur_life, "ACTIVE", cur_epi, epistemic, conf, basis,
                     source_class, reason, superseded=[key])
        conn.commit()
        return {"key": key, "action": "superseded", "revision": rev, "reason": reason}

    # R5 — new lower authority, disagreeing: current stands; keep evidence (superseded)
    if new_rank < cur_rank:
        conn.execute("UPDATE world_belief_evidence SET superseded=1 WHERE belief_key=? AND"
                     " value_json=?", (key, vjson))
        _world_trace(conn, corr, key, now, cur_life, cur_life, cur_epi, cur_epi,
                     row["confidence"], row["confidence_basis"], source_class,
                     "lower_authority_ignored_kept")
        conn.commit()
        return {"key": key, "action": "noop", "revision": rev, "reason": "lower_authority_ignored_kept"}

    # equal authority, differing value
    # R3 — newer comparable observation supersedes (recency ONLY at equal authority)
    if observed_at and (row["observed_at"] is None or observed_at > row["observed_at"]):
        rev += 1
        conf, tier, basis = _world_confidence(epistemic, 0, "ACTIVE")
        conn.execute("UPDATE world_belief SET value_json=?, lifecycle_state='ACTIVE',"
                     " epistemic_state=?, confidence=?, confidence_tier=?, confidence_basis=?,"
                     " observed_at=?, updated_at=?, revision=? WHERE key=?",
                     (vjson, epistemic, conf, tier, basis, observed_at, now, rev, key))
        _world_trace(conn, corr, key, now, cur_life, "ACTIVE", cur_epi, epistemic, conf, basis,
                     source_class, "newer_comparable_supersedes", superseded=[key])
        conn.commit()
        return {"key": key, "action": "superseded", "revision": rev, "reason": "newer_comparable_supersedes"}

    # R4 — equal authority, disagreeing, not clearly newer -> CONFLICTED (retain both)
    rev += 1
    conf, tier, basis = _world_confidence(cur_epi, 0, "CONFLICTED")
    conn.execute("UPDATE world_belief SET lifecycle_state='CONFLICTED', confidence=?,"
                 " confidence_tier=?, confidence_basis=?, updated_at=?, revision=? WHERE key=?",
                 (conf, tier, basis, now, rev, key))
    conn.execute("INSERT OR IGNORE INTO world_belief_conflict (belief_key, conflict_ref,"
                 " detected_at, reason) VALUES (?,?,?, 'equal_authority_disagree')",
                 (key, "evidence:" + now, now))
    _world_trace(conn, corr, key, now, cur_life, "CONFLICTED", cur_epi, cur_epi, conf, basis,
                 source_class, "equal_authority_disagree", conflict=[key])
    conn.commit()
    return {"key": key, "action": "conflicted", "revision": rev, "reason": "equal_authority_disagree"}


# ---- Controlled ingestion boundary (INTERNAL functions; NO generic setBelief) ----
# R7 (source unavailable) and R8 (unknown) are enforced HERE: never call reconcile
# with a None/empty value from a failed/absent source.

def submit_observation(entity_type, entity_id, predicate, value,
                       source_class="LIVE_CONNECTOR", conn=None, **kw):
    if value is None:  # R7 — emptiness is never evidence of a value
        return {"key": _world_key(entity_type, str(entity_id), predicate),
                "action": "noop", "reason": "source_unavailable_noop"}
    own = conn is None
    conn = conn or db()
    try:
        return _world_reconcile(conn, entity_type, entity_id, predicate, value, "OBSERVED",
                                source_class, **kw)
    finally:
        if own:
            conn.close()


def submit_user_assertion(entity_type, entity_id, predicate, value, conn=None, **kw):
    own = conn is None
    conn = conn or db()
    try:
        return _world_reconcile(conn, entity_type, entity_id, predicate, value,
                                "USER_ASSERTED", "USER", **kw)
    finally:
        if own:
            conn.close()


def submit_inference_candidate(entity_type, entity_id, predicate, value, basis=None,
                               conn=None, **kw):
    own = conn is None
    conn = conn or db()
    kw.setdefault("note", basis or "inference")
    try:
        return _world_reconcile(conn, entity_type, entity_id, predicate, value, "INFERRED",
                                "INFERENCE", **kw)
    finally:
        if own:
            conn.close()


def apply_verified_delta(entity_type, entity_id, predicate, value, verification_ref=None,
                         mirror_audit=False, conn=None, **kw):
    own = conn is None
    conn = conn or db()
    kw.setdefault("origin_ref", verification_ref)
    try:
        res = _world_reconcile(conn, entity_type, entity_id, predicate, value, "VERIFIED",
                               "VERIFICATION", **kw)
        if mirror_audit:  # optional convenience mirror; world trace stays authoritative
            conn.execute(
                "INSERT INTO os_audit_log (app, action, entity_type, entity_id, actor,"
                " confidence, reason, before_json, after_json, reversible)"
                " VALUES ('world-model','belief.verified',?,?, 'verification', 0.98, ?, NULL, ?, 0)",
                (entity_type, str(entity_id), res.get("reason"), json.dumps(value)))
            conn.commit()
        return res
    finally:
        if own:
            conn.close()


def world_freshness_sweep(now=None):
    """R6 — mark ACTIVE beliefs past expires_at as STALE (value retained)."""
    now = now or _wm_now()
    conn = db()
    try:
        _ensure_world_schema(conn)
        rows = conn.execute("SELECT key, epistemic_state FROM world_belief WHERE"
                            " expires_at IS NOT NULL AND expires_at < ? AND lifecycle_state='ACTIVE'",
                            (now,)).fetchall()
        for r in rows:
            conf, tier, basis = _world_confidence(r["epistemic_state"], 0, "STALE")
            conn.execute("UPDATE world_belief SET lifecycle_state='STALE', confidence=?,"
                         " confidence_tier=?, confidence_basis=?, updated_at=? WHERE key=?",
                         (conf, tier, basis, now, r["key"]))
            _world_trace(conn, "sweep_" + now, r["key"], now, "ACTIVE", "STALE",
                         r["epistemic_state"], r["epistemic_state"], conf, basis, "SYSTEM",
                         "freshness_expired")
        conn.commit()
        return {"staled": len(rows)}
    finally:
        conn.close()


def world_ingest_career(limit=200):
    """First live domain. Reads job_applications (+companies). NULL fields skipped
    (R7/R8 — never ingest emptiness). follow_up is NOT emitted here (no column)."""
    conn = db()
    try:
        _ensure_world_schema(conn)
        apps = conn.execute(
            "SELECT ja.id, ja.role_title, ja.stage, ja.status, ja.last_activity,"
            " ja.source_account, c.name AS company FROM job_applications ja"
            " LEFT JOIN companies c ON c.id = ja.company_id LIMIT ?", (limit,)).fetchall()
        n = 0
        for a in apps:
            eid = a["id"]
            prov = dict(source_type="career.application", source_id="career-store",
                        origin_ref="job_applications/%s" % eid, observed_at=a["last_activity"],
                        note=("acct:%s" % a["source_account"]) if a["source_account"] else None)
            for pred, val in (("status", a["stage"]), ("role", a["role_title"]),
                              ("company", a["company"]), ("last_activity", a["last_activity"])):
                if val is not None:
                    submit_observation("career.application", eid, pred, val, conn=conn, **prov)
                    n += 1
        return {"applications": len(apps), "observations": n}
    finally:
        conn.close()


# ---- Working Memory reconstruction (mirrors src/lib/world/working-memory.ts) ----

def _wm_recency(iso, now_ts):
    if not iso:
        return 0.0
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0
    return 0.5 ** (max(0.0, (now_ts - t) / 86400.0) / 14.0)


def _wm_score(b, focus_entities, focus_predicates, now_ts):
    if b["lifecycle_state"] == "SUPERSEDED" or b["confidence"] < _ACTIVE_CONFIDENCE_FLOOR:
        return 0.0
    rel = 0.0
    if (b["entity_type"], str(b["entity_id"])) in focus_entities:
        rel += 1.0
    if b["predicate"] in focus_predicates:
        rel += 0.5
    return (3.0 * rel + 1.5 * _EPI_WEIGHT.get(b["epistemic_state"], 0.4)
            + 1.2 * b["confidence"] + 0.8 * _wm_recency(b["updated_at"] or b["observed_at"], now_ts)
            + 0.5 * _LIFECYCLE_WEIGHT.get(b["lifecycle_state"], 0.4))


def build_working_set(session_id, focus_entities=None, focus_predicates=None,
                      capacity=_DEFAULT_WORKING_CAPACITY, task_id=None):
    """Ephemeral, reconstructible. Reads durable beliefs read-only; no WM persistence."""
    fe = set((et, str(eid)) for et, eid in (focus_entities or []))
    fp = set(focus_predicates or [])
    now = _wm_now()
    now_ts = datetime.now(timezone.utc).timestamp()
    conn = _world_ro_conn()
    try:
        rows = conn.execute("SELECT * FROM world_belief WHERE lifecycle_state != 'SUPERSEDED'").fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()
    scored = [(r, _wm_score(r, fe, fp, now_ts)) for r in rows]
    scored = sorted([s for s in scored if s[1] > 0], key=lambda s: (-s[1], s[0]["key"]))
    active = scored[:max(0, int(capacity))]
    return {"sessionId": session_id, "taskId": task_id,
            "activeBeliefIds": [r["key"] for r, _ in active],
            "activeEntities": [{"entityType": r["entity_type"], "entityId": r["entity_id"]}
                               for r, _ in active],
            "capacity": int(capacity), "createdAt": now, "updatedAt": now}


# ---- Read API (GET only; snake_case wire matching src/lib/world/client.ts) ----

def _world_ensure_once():
    global _world_schema_ready
    if not _world_schema_ready:
        c = db()
        try:
            _ensure_world_schema(c)
        finally:
            c.close()


def _belief_to_wire(r, conn):
    ev = conn.execute("SELECT source_class, source_id, source_type, correlation_id, observed_at,"
                      " confidence, origin_ref, note FROM world_belief_evidence WHERE belief_key=?"
                      " AND superseded=0 ORDER BY id DESC", (r["key"],)).fetchall()
    contradicted = [c["conflict_ref"] for c in conn.execute(
        "SELECT conflict_ref FROM world_belief_conflict WHERE belief_key=? AND resolved_at IS NULL",
        (r["key"],)).fetchall()]
    return {
        "key": r["key"], "entity_type": r["entity_type"], "entity_id": r["entity_id"],
        "predicate": r["predicate"], "value": json.loads(r["value_json"]),
        "lifecycle_state": r["lifecycle_state"], "epistemic_state": r["epistemic_state"],
        "confidence": {"value": r["confidence"], "tier": r["confidence_tier"], "basis": r["confidence_basis"]},
        "provenance": [{"source_class": e["source_class"], "source_id": e["source_id"],
                        "source_type": e["source_type"], "correlation_id": e["correlation_id"],
                        "observed_at": e["observed_at"], "confidence": e["confidence"],
                        "origin_ref": e["origin_ref"], "note": e["note"]} for e in ev],
        "observed_at": r["observed_at"], "created_at": r["created_at"], "updated_at": r["updated_at"],
        "expires_at": r["expires_at"], "revision": r["revision"],
        "supersedes": [], "contradicted_by": contradicted,
    }


@app.get("/os/world")
def os_world(entity_type: str = None, entity_id: str = None,
             include_superseded: int = 0, limit: int = 200):
    _world_ensure_once()
    conn = _world_ro_conn()
    try:
        q, args = "SELECT * FROM world_belief WHERE 1=1", []
        if not include_superseded:
            q += " AND lifecycle_state != 'SUPERSEDED'"
        if entity_type:
            q += " AND entity_type=?"; args.append(entity_type)
        if entity_id:
            q += " AND entity_id=?"; args.append(str(entity_id))
        q += " ORDER BY entity_type, entity_id, predicate LIMIT ?"; args.append(int(limit))
        rows = conn.execute(q, args).fetchall()
        beliefs = [_belief_to_wire(r, conn) for r in rows]
        by_life, by_epi = {}, {}
        for r in conn.execute("SELECT lifecycle_state, epistemic_state, COUNT(*) c FROM world_belief"
                              " GROUP BY lifecycle_state, epistemic_state").fetchall():
            by_life[r["lifecycle_state"]] = by_life.get(r["lifecycle_state"], 0) + r["c"]
            by_epi[r["epistemic_state"]] = by_epi.get(r["epistemic_state"], 0) + r["c"]
        last = conn.execute("SELECT MAX(updated_at) m FROM world_belief").fetchone()["m"]
        meta = {"total": sum(by_life.values()), "by_lifecycle": by_life, "by_epistemic": by_epi,
                "conflicted": by_life.get("CONFLICTED", 0), "stale": by_life.get("STALE", 0),
                "last_reconciled_at": last}
        return {"beliefs": beliefs, "meta": meta}
    finally:
        conn.close()


@app.get("/os/world/{key}")
def os_world_key(key: str):
    _world_ensure_once()
    conn = _world_ro_conn()
    try:
        r = conn.execute("SELECT * FROM world_belief WHERE key=?", (key,)).fetchone()
        if r is None:
            raise HTTPException(status_code=404, detail="no belief for key")  # honest UNKNOWN
        return _belief_to_wire(r, conn)
    finally:
        conn.close()

# ============================================================================
# END SLICE 7 — WORLD MODEL + WORKING MEMORY (Phase B)
# ============================================================================
```

### Design notes
- **`_ensure_world_schema`** mirrors the existing inline `tasks`/`drafts` bootstrap; guarded by a process flag so the DB write happens once.
- **Ingestion boundary:** the four `submit_*` / `apply_verified_delta` functions are the only writers. There is **no HTTP mutation route** and **no generic `setBelief`** — the authorization boundary is structural (nothing exposes belief writes to a caller; tests J/K assert it). `VERIFIED` is reachable only via `apply_verified_delta`.
- **R7/R8** live at the ingestion edge (skip `None`/absent), so a failed/empty source never overwrites a valid belief and unknown stays unknown.
- **Reads** use `_world_ro_conn()` (`mode=ro` + `busy_timeout`); a `404` on `/os/world/{key}` is honest UNKNOWN (the frontend already renders it).
- **Career wiring** maps to the real columns (`stage`→status, `role_title`→role, `companies.name`→company, `last_activity`); `follow_up` is intentionally not emitted (no column; would be a derived `INFERRED` belief only if a `career_activities` signal exists).

---

## C. systemd unit drift analysis (read-only; NOT fixed)

Compared the **loaded** (running) definition vs the **on-disk** unit fragment.

| Field | Loaded (running) | On-disk fragment | Match? |
|---|---|---|---|
| `FragmentPath` | `/etc/systemd/system/lilith-os-api.service` | (same) | — |
| `ExecStart` | `…/api-venv/bin/uvicorn app:app --host 0.0.0.0 --port 8765` | identical | ✅ |
| `WorkingDirectory` | `/home/lilith/.hermes/lilith-os/api` | identical | ✅ |
| `User` / `Group` | `lilith` / `lilith` | identical | ✅ |
| `Type` | `simple` | `simple` | ✅ |
| `Restart` / `RestartSec` | `on-failure` / 5s | `on-failure` / 5 | ✅ |
| Port | 8765 | 8765 | ✅ |
| `DropInPaths` | none | none | ✅ |
| `Environment=` lines | (not value-compared — secrets) | **1 line present** | not compared by value |

- `NeedDaemonReload=yes` — **pre-existing**; the on-disk fragment mtime is `2026-08-25 12:10:09` (last daemon-reload predates that edit). **I did not cause it and did not reload.**
- **Does the drift affect WorkingDirectory, ExecStart, user/group, port, or restart behavior?** **No** — every operational field is identical between loaded and on-disk.
- **Environment:** there is exactly one `Environment=` line on disk; its value was deliberately **not printed** (possible secret). Whatever it is, it is irrelevant to a restart because a restart does not re-read the file (see below). If you ever `daemon-reload`, that single line is the only thing that could change behavior — worth eyeballing manually before a future reload, but not needed for this deploy.
- **Will a normal restart WITHOUT `daemon-reload` keep the current safe config?** **Yes.** `systemctl restart` re-executes the **currently loaded** in-memory unit; it does not parse unit files. Only `daemon-reload` re-reads them. So `systemctl restart lilith-os-api.service` runs the exact config the service runs now.

**Conclusion:** the drift is benign for a restart-only deploy. **Do not `daemon-reload`** during Phase B.

---

## D. Deployment + rollback plan (to run at apply-time — NOT executed here)

All commands run over the authorized IAP SSH session, as the `lilith` owner via `sudo -u lilith` (preserves `lilith:lilith` ownership). **Nothing below has been run.**

### D.1 Pre-flight (read-only)
```bash
sudo -n sha256sum /home/lilith/.hermes/lilith-os/api/app.py   # expect 340358764024...
systemctl is-active lilith-os-api.service                     # expect active
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8765/system/status   # expect 200
```

### D.2 Backups created (exact paths)
```bash
TS=$(date +%Y%m%d-%H%M%S)
sudo -n -u lilith cp -a /home/lilith/.hermes/lilith-os/api/app.py \
     /home/lilith/.hermes/lilith-os/api/app.py.bak.$TS          # matches existing app.py.bak.* convention
sudo -n -u lilith cp -a /home/lilith/.hermes/lilith-os/data/lilith.db \
     /home/lilith/.hermes/lilith-os/data/lilith.before-world-model.db   # matches lilith.<label>.db convention
sudo -n -u lilith sha256sum /home/lilith/.hermes/lilith-os/api/app.py.bak.$TS \
     /home/lilith/.hermes/lilith-os/data/lilith.before-world-model.db   # record for rollback verification
```

### D.3 Apply (append the reviewed block)
- Transfer the reviewed block (section B) to the VM and append it, delimited by the `# BEGIN/END SLICE 7` markers, to `app.py`:
```bash
# <block> staged at /tmp/slice7_block.py by an authorized transfer, then:
sudo -n -u lilith tee -a /home/lilith/.hermes/lilith-os/api/app.py < /tmp/slice7_block.py >/dev/null
sudo -n -u lilith /home/lilith/.hermes/lilith-os/api-venv/bin/python -c "import ast,sys; ast.parse(open('/home/lilith/.hermes/lilith-os/api/app.py').read()); print('AST OK')"
```
(`ast.parse` is a syntax check **before** restart — no import side effects.)

### D.4 Restart (restart only — NO daemon-reload)
```bash
sudo -n systemctl restart lilith-os-api.service
```

### D.5 Health checks after restart
```bash
systemctl is-active lilith-os-api.service                                   # expect: active
curl -s -o /dev/null -w 'status=%{http_code}\n' http://localhost:8765/system/status   # 200 (Slice1-6 alive)
curl -s -o /dev/null -w 'tasks=%{http_code}\n'  http://localhost:8765/os/tasks         # 200 (Slice3 regression)
curl -s -o /dev/null -w 'drafts=%{http_code}\n' http://localhost:8765/os/drafts        # 200 (Slice4 regression)
curl -s -o /dev/null -w 'world=%{http_code}\n'  http://localhost:8765/os/world         # 200 (new; empty beliefs OK)
sudo -n journalctl -u lilith-os-api.service -n 40 --no-pager                            # no tracebacks
```
Then seed the first domain and verify:
```bash
# one-off in-process ingest (authorized admin task), then read back:
curl -s 'http://localhost:8765/os/world?entity_type=career.application' | head -c 800
```

### D.6 Rollback (if AST check, startup, or health checks fail)
```bash
# 1. restore code (always safe; world_* tables are additive and simply go unused)
sudo -n -u lilith cp -a /home/lilith/.hermes/lilith-os/api/app.py.bak.$TS \
     /home/lilith/.hermes/lilith-os/api/app.py
# 2. (only if the DB was somehow left bad — normally NOT needed, schema is additive)
sudo -n -u lilith cp -a /home/lilith/.hermes/lilith-os/data/lilith.before-world-model.db \
     /home/lilith/.hermes/lilith-os/data/lilith.db
# 3. restart on the restored code (still no daemon-reload)
sudo -n systemctl restart lilith-os-api.service
# 4. verify baseline restored
systemctl is-active lilith-os-api.service
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8765/system/status   # expect 200
sudo -n sha256sum /home/lilith/.hermes/lilith-os/api/app.py                     # expect 340358764024...
```
Rollback is fast and low-risk: the change is one appended, delimited block plus additive tables. Restoring `app.py` from the timestamped backup fully reverts behavior; the `world_*` tables (if created) are inert once the code is gone.

---

## E. Test implementation plan (backend)

New file `tests/test_world_model.py` (or alongside `app.py`), stdlib `unittest`, run against a **throwaway temp DB** (never `lilith.db`):
```bash
sudo -n -u lilith /home/lilith/.hermes/lilith-os/api-venv/bin/python -m unittest -v tests/test_world_model.py
```
Each maps to a spec rule/invariant; all deterministic (fixed clock injected):

| # | Test | Anchor |
|---|---|---|
| A | observation creates provenance-stamped belief | R0 |
| B | canonical key: two obs of same key → one `world_belief` row | §4/R1 |
| C | identical repeat is idempotent (corroboration, no dup) | R1 |
| D | newer equal-authority observation supersedes | R3 |
| E | VERIFIED value beats prior INFERRED; inferred kept superseded | R2 |
| F | belief past `expires_at` → STALE after `world_freshness_sweep` | R6 |
| G | equal-authority disagreement → CONFLICTED + both chains + conflict row | R4 |
| H | absent key → no belief synthesized | R8 |
| I | `submit_observation(..., None)` → `noop/source_unavailable_noop`; existing belief untouched | R7 |
| J | no HTTP route mutates beliefs (only GET world routes exist) | §8 |
| K | `_world_reconcile` reachable only via the four `submit_*` wrappers (no generic setter) | §8 |
| L | `build_working_set` returns a subset (not all beliefs) | §13 |
| M | `len(activeBeliefIds) <= capacity` | §13 |
| N | working set rebuilt identically after reopening the DB | §13 |
| O | every reconcile writes a `world_belief_trace` row | §1/§12 |
| P | provenance + correlation persist across a reopen | §1 |
| Q | Career reasoning still works (Slice 2 route unaffected) | §14 |
| R | Slice 1–6 endpoints unchanged (route table + smoke) | §0 |

Frontend Phase A already covers L/M/N semantics for the TS mirror (`buildWorkingSet`); the backend re-proves them plus A–K, O–R server-side.

---

## READY / NOT READY

**READY for Phase B deployment — pending your explicit go-ahead to apply.**

Rationale:
- The change is **additive and single-file**: one delimited append to `app.py` + additive `world_*` tables via inline bootstrap (matches production's existing pattern). No edits to Slice 1–6 code or tables.
- **Reversible**: timestamped `app.py` backup + labelled DB snapshot (both existing conventions); rollback is a file restore + restart.
- **systemd drift is benign** for a restart-only deploy: all operational fields match loaded vs on-disk, and `systemctl restart` won't re-read the file. **We will not `daemon-reload`.**
- **Safety invariants intact**: no external writes, no new connectors, no Policy weakening, no Hsin/OAuth/Presence changes; reads are `mode=ro`; belief writes have no HTTP surface.

Residual items to confirm at apply-time (not blockers):
1. The single on-disk `Environment=` line differs from the loaded unit in an unknown way — irrelevant to restart, but worth a manual eyeball before any *future* `daemon-reload` (out of scope for Phase B).
2. `ast.parse` gate must pass before restart; if it fails, abort (no restart) and the tree is already backed up.
3. Deployment itself is a **separate authorized action** — this document changes nothing on the VM.

*Draft for review. No production changes performed.*
