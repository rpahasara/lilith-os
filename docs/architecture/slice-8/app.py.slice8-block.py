

# ============================================================================
# BEGIN SLICE 8 — GOAL / EXECUTIVE SYSTEM V1  [additive; append-only]
# Uses existing module globals: app, db, DB, sqlite3, json, re, datetime,
# timezone, HTTPException, _Body, _world_ro_conn (Slice 7). No changes to
# Slice 1-7.1 code above this marker.
#
# Executive decides WHAT should be pursued now. Planning (HOW) is out of scope.
# Goal != Task: the `tasks` table (Slice 3) is the execution substrate and is
# NOT touched here; a Goal is a durable continuity object that LINKS tasks/drafts
# and owns lifecycle + focus. Focus is DERIVED (never stored). Arbitration is
# deterministic (typed ranks; no LLM, no opaque scores).
#
# WORLD MODEL OWNERSHIP BOUNDARY (strict): this block READS beliefs only, via the
# read-only connection helper `_world_ro_conn()`. It NEVER calls, imports, or
# references any World Model belief-write or reconciliation helper. A conformance
# test asserts those mutation symbols are absent from this block. The Executive
# also invokes no external integration or tool, and performs no external send.
# ============================================================================

GOAL_SCHEMA_VERSION = 1

_GOAL_LIFECYCLE = (
    "PENDING", "ACTIVE", "BLOCKED", "SUSPENDED", "COMPLETED", "CANCELLED", "FAILED",
)
_GOAL_TERMINAL = frozenset(("COMPLETED", "CANCELLED", "FAILED"))
_GOAL_NONTERMINAL = frozenset(("PENDING", "ACTIVE", "BLOCKED", "SUSPENDED"))
_GOAL_SOURCES = ("USER_REQUESTED", "TASK_DERIVED", "SYSTEM_MAINTENANCE", "SCHEDULED")
_GOAL_PRIORITIES = ("URGENT", "HIGH", "NORMAL", "LOW")
_GOAL_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_GOAL_OP_RE = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
_MAX_GOAL_BYTES = 64 * 1024

# action -> (allowed_from_states, target_state, timestamp_column)
# Explicit, validated FSM. Terminal -> active never happens implicitly; the only
# terminal exit is `reopen` and it lands in PENDING (never directly ACTIVE).
_GOAL_ACTIONS = {
    "activate": (frozenset(("PENDING",)), "ACTIVE", "started_at"),
    "block":    (frozenset(("PENDING", "ACTIVE")), "BLOCKED", "blocked_at"),
    "unblock":  (frozenset(("BLOCKED",)), "ACTIVE", "started_at"),
    "suspend":  (frozenset(("ACTIVE",)), "SUSPENDED", "suspended_at"),
    "resume":   (frozenset(("SUSPENDED",)), "ACTIVE", "started_at"),
    "complete": (frozenset(("ACTIVE",)), "COMPLETED", "completed_at"),
    "fail":     (frozenset(("ACTIVE", "BLOCKED")), "FAILED", "failed_at"),
    "cancel":   (frozenset(("PENDING", "ACTIVE", "BLOCKED", "SUSPENDED")), "CANCELLED", "cancelled_at"),
    "reopen":   (frozenset(("COMPLETED", "CANCELLED", "FAILED")), "PENDING", None),
}

# Arbitration rank tables (lower = preferred). Deterministic + explainable.
_GOAL_LIFE_RANK = {"ACTIVE": 0, "PENDING": 1}
_GOAL_PRIO_RANK = {p: i for i, p in enumerate(_GOAL_PRIORITIES)}
_GOAL_SOURCE_RANK = {
    "USER_REQUESTED": 0, "TASK_DERIVED": 1, "SCHEDULED": 2, "SYSTEM_MAINTENANCE": 3,
}
# Ordered arbitration rules (index = precedence). Used for explainable traces.
_GOAL_ARB_RULES = ("lifecycle", "priority", "deadline", "source", "recency", "id")

_goal_schema_ready = False


def _goal_now():
    return datetime.now(timezone.utc).isoformat()


def _goal_log(op, **fields):
    """Structured, secret-free observability line (captured by journald)."""
    try:
        print("lilith.goals " + json.dumps({"op": op, **fields},
                                            separators=(",", ":")), flush=True)
    except Exception:
        pass


def _goals_db():
    """Open the shared DB and ensure the goal schema exists (idempotent inline
    bootstrap — production has no migration runner; mirrors tasks/drafts)."""
    global _goal_schema_ready
    conn = db()
    if not _goal_schema_ready:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS goal (
                goal_id           TEXT PRIMARY KEY,
                schema_version    INTEGER NOT NULL,
                type              TEXT NOT NULL,
                title             TEXT NOT NULL,
                description       TEXT,
                source            TEXT NOT NULL,
                owner             TEXT NOT NULL,
                lifecycle_state   TEXT NOT NULL,
                priority          TEXT NOT NULL,
                parent_goal_id    TEXT,
                linked_task_ids   TEXT NOT NULL DEFAULT '[]',
                target_json       TEXT,
                target_key        TEXT NOT NULL DEFAULT '',
                deadline          TEXT,
                blocked_reason    TEXT,
                blocked_by_json   TEXT,
                resume_conditions TEXT,
                created_at        TEXT NOT NULL,
                updated_at        TEXT NOT NULL,
                started_at        TEXT,
                blocked_at        TEXT,
                suspended_at      TEXT,
                completed_at      TEXT,
                cancelled_at      TEXT,
                failed_at         TEXT,
                provenance_json   TEXT,
                revision          INTEGER NOT NULL DEFAULT 1,
                last_operation_id TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_goal_lifecycle ON goal(lifecycle_state);
            CREATE INDEX IF NOT EXISTS idx_goal_parent ON goal(parent_goal_id);
            CREATE INDEX IF NOT EXISTS idx_goal_type ON goal(type);
            CREATE INDEX IF NOT EXISTS idx_goal_dedup ON goal(type, owner, target_key);
            CREATE TABLE IF NOT EXISTS goal_trace (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                correlation_id TEXT NOT NULL,
                goal_id        TEXT,
                at             TEXT NOT NULL,
                kind           TEXT NOT NULL,
                prior_state    TEXT,
                new_state      TEXT,
                action         TEXT,
                reason         TEXT NOT NULL,
                source         TEXT,
                arbitration_winner        TEXT,
                arbitration_alternatives_json TEXT,
                priority_inputs_json      TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_goal_trace_goal ON goal_trace(goal_id, at);
            CREATE INDEX IF NOT EXISTS idx_goal_trace_corr ON goal_trace(correlation_id);
            """
        )
        conn.commit()
        _goal_schema_ready = True
    return conn


def _goal_target_key(target):
    """Canonical dedup key for a typed target (sorted-keys JSON, '' when none)."""
    if not target or not isinstance(target, dict):
        return ""
    return json.dumps(target, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _goal_trace_insert(conn, correlation_id, goal_id, kind, reason,
                       prior_state=None, new_state=None, action=None, source=None,
                       arb_winner=None, arb_alternatives=None, priority_inputs=None):
    conn.execute(
        "INSERT INTO goal_trace (correlation_id, goal_id, at, kind, prior_state,"
        " new_state, action, reason, source, arbitration_winner,"
        " arbitration_alternatives_json, priority_inputs_json)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (correlation_id or ("g_" + _goal_now()), goal_id, _goal_now(), kind,
         prior_state, new_state, action, reason, source, arb_winner,
         json.dumps(arb_alternatives) if arb_alternatives is not None else None,
         json.dumps(priority_inputs) if priority_inputs is not None else None),
    )


def _row_to_goal(row):
    return {
        "goalId": row["goal_id"],
        "schemaVersion": row["schema_version"],
        "type": row["type"],
        "title": row["title"],
        "description": row["description"],
        "source": row["source"],
        "owner": row["owner"],
        "lifecycleState": row["lifecycle_state"],
        "priority": row["priority"],
        "parentGoalId": row["parent_goal_id"],
        "linkedTaskIds": json.loads(row["linked_task_ids"] or "[]"),
        "target": json.loads(row["target_json"]) if row["target_json"] else None,
        "deadline": row["deadline"],
        "blockedReason": row["blocked_reason"],
        "blockedBy": json.loads(row["blocked_by_json"]) if row["blocked_by_json"] else None,
        "resumeConditions": row["resume_conditions"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "startedAt": row["started_at"],
        "blockedAt": row["blocked_at"],
        "suspendedAt": row["suspended_at"],
        "completedAt": row["completed_at"],
        "cancelledAt": row["cancelled_at"],
        "failedAt": row["failed_at"],
        "provenance": json.loads(row["provenance_json"]) if row["provenance_json"] else None,
        "revision": row["revision"],
    }


def _goal_by_id(conn, goal_id):
    return conn.execute("SELECT * FROM goal WHERE goal_id=?", (goal_id,)).fetchone()


# ── World Model READ boundary (strict, read-only) ───────────────────────────
# The Executive may READ belief state to inform decisions. This helper uses the
# Slice-7 read-only connection (mode=ro) and only ever runs SELECT statements, so
# it is structurally incapable of mutating a belief. It must remain the ONLY way
# the Executive touches the World Model.

def _exec_read_beliefs(entity_type=None, entity_id=None):
    """Return current beliefs (read-only) for optional entity focus. Never writes."""
    try:
        conn = _world_ro_conn()
    except Exception:
        return []
    try:
        q = "SELECT key, entity_type, entity_id, predicate, value_json,"           " lifecycle_state, epistemic_state, confidence FROM world_belief"           " WHERE lifecycle_state != 'SUPERSEDED'"
        args = []
        if entity_type:
            q += " AND entity_type=?"; args.append(str(entity_type))
        if entity_id:
            q += " AND entity_id=?"; args.append(str(entity_id))
        rows = conn.execute(q, args).fetchall()
        out = []
        for r in rows:
            out.append({
                "key": r["key"], "entity_type": r["entity_type"],
                "entity_id": r["entity_id"], "predicate": r["predicate"],
                "value": json.loads(r["value_json"]),
                "lifecycle_state": r["lifecycle_state"],
                "epistemic_state": r["epistemic_state"],
                "confidence": r["confidence"],
            })
        return out
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def _exec_world_conflicted(entity_type, entity_id):
    """True when any belief for this entity is CONFLICTED — the Executive must
    then block/escalate rather than silently progress (design §6)."""
    for b in _exec_read_beliefs(entity_type, entity_id):
        if b.get("lifecycle_state") == "CONFLICTED":
            return True
    return False


def _exec_unresolved_followups(conn, app_id):
    """Read-only: created (UNSENT) career_followup drafts for an application.
    Reuses the durable drafts substrate (Slice 4). Real blocker evidence for the
    application-14 duplicate-draft case."""
    try:
        rows = conn.execute(
            "SELECT draft_id FROM drafts WHERE target_type='application' AND"
            " target_id=? AND kind='career_followup' AND status='created'"
            " ORDER BY created_at", (str(app_id),)).fetchall()
        return [r["draft_id"] for r in rows]
    except sqlite3.OperationalError:
        return []


# ── Controlled create (with deterministic USER_REQUESTED de-dup) ────────────

def _goal_validate_create(payload):
    gtype = payload.get("type")
    title = payload.get("title")
    source = payload.get("source", "USER_REQUESTED")
    owner = payload.get("owner", "user")
    priority = payload.get("priority", "NORMAL")
    if not isinstance(gtype, str) or not gtype.strip():
        raise HTTPException(status_code=400, detail="type required")
    if not isinstance(title, str) or not title.strip():
        raise HTTPException(status_code=400, detail="title required")
    if source not in _GOAL_SOURCES:
        raise HTTPException(status_code=422, detail="invalid source")
    if priority not in _GOAL_PRIORITIES:
        raise HTTPException(status_code=422, detail="invalid priority")
    if not isinstance(owner, str) or not owner.strip():
        raise HTTPException(status_code=400, detail="owner required")
    sv = payload.get("schemaVersion", GOAL_SCHEMA_VERSION)
    if not isinstance(sv, int) or sv < 1:
        raise HTTPException(status_code=422, detail="invalid schemaVersion")
    if sv > GOAL_SCHEMA_VERSION:
        raise HTTPException(status_code=422, detail="unsupported schemaVersion %s" % sv)
    return gtype, title, source, owner, priority, sv


def _create_goal_impl(conn, payload):
    """Internal controlled create. Returns (goal_dict, created_bool). Applies the
    deterministic (type,target,owner) de-dup for USER_REQUESTED goals."""
    gtype, title, source, owner, priority, sv = _goal_validate_create(payload)
    operation_id = payload.get("operationId")
    target = payload.get("target")
    target_key = _goal_target_key(target)
    now = _goal_now()

    # Idempotent replay by operation_id (exact retry -> same row).
    if operation_id:
        prev = conn.execute(
            "SELECT * FROM goal WHERE last_operation_id=?", (operation_id,)).fetchone()
        if prev is not None:
            return _row_to_goal(prev), False

    # Deterministic semantic de-dup for USER_REQUESTED goals (design §4):
    # exact (type,target_key,owner) match among NON-TERMINAL goals.
    if source == "USER_REQUESTED":
        rows = conn.execute(
            "SELECT * FROM goal WHERE type=? AND owner=? AND target_key=? AND"
            " lifecycle_state IN ('PENDING','ACTIVE','BLOCKED','SUSPENDED')"
            " ORDER BY created_at", (gtype, owner, target_key)).fetchall()
        if len(rows) == 1:
            _goal_log("create.reused", goalId=rows[0]["goal_id"], type=gtype)
            return _row_to_goal(rows[0]), False
        if len(rows) > 1:
            ids = [r["goal_id"] for r in rows]
            _goal_log("create.reconciliation_required", type=gtype, count=len(ids))
            raise HTTPException(status_code=409, detail={
                "error": "reconciliation_required",
                "reason": "multiple equivalent non-terminal goals exist",
                "goalIds": ids})

    import uuid as _uuid
    goal_id = payload.get("goalId") or ("g." + _uuid.uuid4().hex)
    if not _GOAL_ID_RE.match(goal_id):
        raise HTTPException(status_code=400, detail="invalid goalId")
    corr = payload.get("correlationId") or ("g_" + now)
    provenance = {
        "source": source,
        "sourceChannel": payload.get("sourceChannel"),
        "correlationId": corr,
        "createdVia": payload.get("createdVia", "api"),
    }
    deadline = payload.get("deadline")  # only if genuinely provided; never invented
    conn.execute(
        "INSERT INTO goal (goal_id, schema_version, type, title, description, source,"
        " owner, lifecycle_state, priority, parent_goal_id, linked_task_ids,"
        " target_json, target_key, deadline, created_at, updated_at, provenance_json,"
        " revision, last_operation_id) VALUES (?,?,?,?,?,?,?, 'PENDING', ?,?, '[]',"
        " ?,?,?,?,?,?, 1, ?)",
        (goal_id, sv, gtype, title, payload.get("description"), source, owner,
         priority, payload.get("parentGoalId"),
         json.dumps(target) if target else None, target_key, deadline, now, now,
         json.dumps(provenance), operation_id),
    )
    _goal_trace_insert(conn, corr, goal_id, "transition", "goal_created",
                       prior_state=None, new_state="PENDING", action="create",
                       source=source)
    conn.commit()
    _goal_log("create", goalId=goal_id, type=gtype, source=source)
    stored = _goal_by_id(conn, goal_id)
    return _row_to_goal(stored), True


# ── Controlled transition (FSM-validated, revision-guarded, idempotent) ──────

def _goal_completion_block(conn, goal):
    """Evidence gate for `complete` (design §3 completion is evidence-based).
    Returns a human reason string when completion must be REFUSED, else None.
    Honest: a `career.followup` (a SEND objective) can never be system-completed
    because no send capability exists; a `career.prepare_followup` completes only
    when a durable follow-up draft actually exists for its target."""
    gtype = goal["type"]
    target = json.loads(goal["target_json"]) if goal["target_json"] else None
    app_id = (target or {}).get("id") if isinstance(target, dict) else None
    if gtype == "career.followup":
        return ("no send capability exists, so an external follow-up cannot be"
                " verified as sent — completion is not evidence-backed")
    if gtype == "career.prepare_followup":
        if not app_id:
            return "no target application to check for a prepared draft"
        drafts = _exec_unresolved_followups(conn, app_id)
        if not drafts:
            return "no prepared follow-up draft exists for the target yet"
        return None
    return None  # generic goals: no special evidence rule in V1


def _transition_goal_impl(conn, goal_id, payload):
    action = payload.get("action")
    operation_id = payload.get("operationId")
    expected_revision = payload.get("expectedRevision")
    row = _goal_by_id(conn, goal_id)
    if row is None:
        raise HTTPException(status_code=404, detail="goal not found")
    # Idempotent replay: same operationId already applied -> no-op.
    if operation_id and row["last_operation_id"] == operation_id:
        _goal_log("transition.replay", goalId=goal_id, operationId=operation_id)
        return _row_to_goal(row), False
    if action not in _GOAL_ACTIONS:
        raise HTTPException(status_code=400, detail="unknown action")
    allowed_from, target_state, ts_col = _GOAL_ACTIONS[action]
    if expected_revision is not None and expected_revision != row["revision"]:
        raise HTTPException(status_code=409, detail={
            "error": "revision_conflict", "current": _row_to_goal(row),
            "revision": row["revision"]})
    cur_state = row["lifecycle_state"]
    if cur_state not in allowed_from:
        _goal_log("transition.illegal", goalId=goal_id,
                  **{"from": cur_state, "action": action})
        raise HTTPException(status_code=409, detail={
            "error": "illegal_transition", "from": cur_state, "action": action,
            "allowedFrom": sorted(allowed_from)})
    # Evidence-based completion gate.
    if action == "complete":
        block = _goal_completion_block(conn, row)
        if block:
            raise HTTPException(status_code=409, detail={
                "error": "evidence_required", "reason": block})
    now = _goal_now()
    corr = payload.get("correlationId") or ("g_" + now)
    reason = payload.get("reason") or ("action:" + action)
    new_rev = row["revision"] + 1

    sets = ["lifecycle_state=?", "updated_at=?", "revision=?", "last_operation_id=?"]
    args = [target_state, now, new_rev, operation_id or row["last_operation_id"]]
    if ts_col:
        sets.append(ts_col + "=?"); args.append(now)
    if action == "block":
        sets.append("blocked_reason=?"); args.append(payload.get("blockedReason") or reason)
        bb = payload.get("blockedBy")
        sets.append("blocked_by_json=?"); args.append(json.dumps(bb) if bb is not None else None)
        sets.append("resume_conditions=?"); args.append(payload.get("resumeConditions"))
    if action in ("unblock", "resume"):
        # Clear the blocker annotations on an explicit return to ACTIVE.
        sets.append("blocked_reason=?"); args.append(None)
        sets.append("blocked_by_json=?"); args.append(None)
        sets.append("resume_conditions=?"); args.append(payload.get("resumeConditions"))
    # Optimistic-concurrency guard: only lands if revision unchanged.
    args += [goal_id, row["revision"]]
    cur = conn.execute(
        "UPDATE goal SET " + ", ".join(sets) + " WHERE goal_id=? AND revision=?", args)
    if cur.rowcount == 0:
        conn.rollback()
        fresh = _goal_by_id(conn, goal_id)
        raise HTTPException(status_code=409, detail={
            "error": "revision_conflict", "current": _row_to_goal(fresh),
            "revision": fresh["revision"]})
    _goal_trace_insert(conn, corr, goal_id, "transition", reason,
                       prior_state=cur_state, new_state=target_state, action=action,
                       source=row["source"])
    conn.commit()
    _goal_log("transition", goalId=goal_id, action=action,
              **{"from": cur_state, "to": target_state, "revision": new_rev})
    return _row_to_goal(_goal_by_id(conn, goal_id)), True


def _goal_autoblock_followup(conn, goal_id):
    """Evidence-derived, traced auto-block for a career.followup goal whose target
    has >=2 unresolved (UNSENT) follow-up drafts — the real application-14 case.
    Deterministic; performs an explicit PENDING/ACTIVE -> BLOCKED transition with
    an explainable reason. Does NOT touch or delete the drafts."""
    row = _goal_by_id(conn, goal_id)
    if row is None or row["type"] != "career.followup":
        return None
    if row["lifecycle_state"] not in ("PENDING", "ACTIVE"):
        return None
    target = json.loads(row["target_json"]) if row["target_json"] else None
    app_id = (target or {}).get("id") if isinstance(target, dict) else None
    if not app_id:
        return None
    drafts = _exec_unresolved_followups(conn, app_id)
    if len(drafts) < 2:
        return None
    return _transition_goal_impl(conn, goal_id, {
        "action": "block",
        "reason": "duplicate_unsent_followup_drafts_require_reconciliation",
        "blockedReason": ("%d unresolved unsent follow-up drafts for application %s"
                          " require reconciliation before this goal can proceed"
                          % (len(drafts), app_id)),
        "blockedBy": ["draft:" + d for d in drafts],
        "resumeConditions": ("reconcile to a single unresolved follow-up draft for"
                             " application %s (keep one, discard the rest)" % app_id),
    })[0]


# ── Deterministic arbitration + derived focus (design §5) ───────────────────

def _goal_epoch(iso):
    if not iso:
        return 0.0
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _goal_sort_key(g):
    life = _GOAL_LIFE_RANK.get(g["lifecycle_state"], 9)
    prio = _GOAL_PRIO_RANK.get(g["priority"], 9)
    has_deadline = 0 if g["deadline"] else 1
    deadline = g["deadline"] or ""
    src = _GOAL_SOURCE_RANK.get(g["source"], 9)
    recency = -_goal_epoch(g["updated_at"])
    return (life, prio, has_deadline, deadline, src, recency, g["goal_id"])


def _goal_rule_values(g):
    return {
        "lifecycle": g["lifecycle_state"],
        "priority": g["priority"],
        "deadline": g["deadline"],
        "source": g["source"],
        "recency": g["updated_at"],
        "id": g["goal_id"],
    }


def _goal_first_distinguishing_rule(winner, loser):
    """Return the first arbitration rule (by precedence) whose comparison places
    winner strictly ahead of loser — the reason winner beats this loser."""
    wk = _goal_sort_key(winner)
    lk = _goal_sort_key(loser)
    for i, rule in enumerate(_GOAL_ARB_RULES):
        if wk[i] != lk[i]:
            return rule
    return "id"


def _arbitrate(conn):
    """Compute the single current-focus goal deterministically from durable rows.
    Candidates = ACTIVE or PENDING (BLOCKED/SUSPENDED/terminal excluded)."""
    rows = conn.execute(
        "SELECT * FROM goal WHERE lifecycle_state IN ('ACTIVE','PENDING')").fetchall()
    cands = sorted(rows, key=_goal_sort_key)
    if not cands:
        return {"focus": None, "candidates": [], "arbitration": {
            "winner": None, "ruleFired": None, "alternatives": [],
            "reason": "no active or pending goals"}}
    winner = cands[0]
    alternatives = []
    for l in cands[1:]:
        alternatives.append({
            "goalId": l["goal_id"],
            "eliminatedBy": _goal_first_distinguishing_rule(winner, l),
            "lifecycle": l["lifecycle_state"], "priority": l["priority"],
            "source": l["source"],
        })
    return {
        "focus": _row_to_goal(winner),
        "candidates": [_row_to_goal(c) for c in cands],
        "arbitration": {
            "winner": winner["goal_id"],
            "ruleFired": _GOAL_ARB_RULES[0],
            "priorityInputs": _goal_rule_values(winner),
            "alternatives": alternatives,
            "reason": ("deterministic rank over %s" % ", ".join(_GOAL_ARB_RULES)),
        },
    }


def _record_focus_trace(conn, result):
    """Write an arbitration trace only when the computed winner changes vs the
    last recorded arbitration winner (avoids trace spam; focus stays derived)."""
    winner = result["arbitration"]["winner"]
    last = conn.execute(
        "SELECT arbitration_winner FROM goal_trace WHERE kind='arbitration'"
        " ORDER BY id DESC LIMIT 1").fetchone()
    last_winner = last["arbitration_winner"] if last else None
    if winner != last_winner:
        _goal_trace_insert(
            conn, "g_arb_" + _goal_now(), winner, "arbitration",
            result["arbitration"]["reason"], arb_winner=winner,
            arb_alternatives=result["arbitration"]["alternatives"],
            priority_inputs=result["arbitration"].get("priorityInputs"))
        conn.commit()


# ── Read API (GET) ──────────────────────────────────────────────────────────

@app.get("/os/goals")
def list_goals(limit: int = 50, state: str = None, type: str = None, owner: str = None):
    limit = max(1, min(int(limit or 50), 200))
    conn = _goals_db()
    try:
        q = "SELECT * FROM goal"
        clauses, args = [], []
        if state:
            clauses.append("lifecycle_state=?"); args.append(state)
        if type:
            clauses.append("type=?"); args.append(type)
        if owner:
            clauses.append("owner=?"); args.append(owner)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        rows = conn.execute(q, args).fetchall()
        return {"goals": [_row_to_goal(r) for r in rows], "count": len(rows),
                "schemaVersion": GOAL_SCHEMA_VERSION}
    finally:
        conn.close()


@app.get("/os/goals/focus")
def goal_focus():
    conn = _goals_db()
    try:
        result = _arbitrate(conn)
        _record_focus_trace(conn, result)
        return result
    finally:
        conn.close()


@app.get("/os/goals/{goal_id}")
def get_goal(goal_id: str):
    if not _GOAL_ID_RE.match(goal_id or ""):
        raise HTTPException(status_code=400, detail="invalid goalId")
    conn = _goals_db()
    try:
        row = _goal_by_id(conn, goal_id)
        if row is None:
            raise HTTPException(status_code=404, detail="goal not found")
        return {"goal": _row_to_goal(row)}
    finally:
        conn.close()


# ── Controlled write API (typed operations; NO generic setGoal/setState) ────

@app.post("/os/goals")
def post_goal(payload: dict = _Body(default=None)):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    conn = _goals_db()
    try:
        goal, created = _create_goal_impl(conn, payload)
        # Optional evidence-derived auto-block for career.followup (design §12):
        # reflects the REAL duplicate-draft blocker; explicit + traced, drafts
        # untouched. Only when the caller asks (the cognitive lane sets this).
        if created and payload.get("evaluateBlock") and goal["type"] == "career.followup":
            blocked = _goal_autoblock_followup(conn, goal["goalId"])
            if blocked is not None:
                goal = blocked
        return {"goal": goal, "created": created}
    finally:
        conn.close()


@app.post("/os/goals/{goal_id}/transition")
def post_goal_transition(goal_id: str, payload: dict = _Body(default=None)):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    if not _GOAL_ID_RE.match(goal_id or ""):
        raise HTTPException(status_code=400, detail="invalid goalId")
    op = payload.get("operationId")
    if op is not None and not _GOAL_OP_RE.match(str(op)):
        raise HTTPException(status_code=400, detail="invalid operationId")
    conn = _goals_db()
    try:
        goal, applied = _transition_goal_impl(conn, goal_id, payload)
        return {"goal": goal, "applied": applied}
    finally:
        conn.close()


@app.post("/os/goals/{goal_id}/link_task")
def post_goal_link_task(goal_id: str, payload: dict = _Body(default=None)):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    if not _GOAL_ID_RE.match(goal_id or ""):
        raise HTTPException(status_code=400, detail="invalid goalId")
    task_id = payload.get("taskId")
    operation_id = payload.get("operationId")
    if not isinstance(task_id, str) or not _TASK_ID_RE.match(task_id):
        raise HTTPException(status_code=400, detail="invalid taskId")
    conn = _goals_db()
    try:
        row = _goal_by_id(conn, goal_id)
        if row is None:
            raise HTTPException(status_code=404, detail="goal not found")
        if operation_id and row["last_operation_id"] == operation_id:
            return {"goal": _row_to_goal(row), "applied": False}
        # Validate the task exists (read-only; tasks table is NOT mutated here).
        texists = conn.execute("SELECT 1 FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if texists is None:
            raise HTTPException(status_code=404, detail="task not found")
        links = json.loads(row["linked_task_ids"] or "[]")
        if task_id in links:
            return {"goal": _row_to_goal(row), "applied": False}
        links.append(task_id)
        now = _goal_now()
        new_rev = row["revision"] + 1
        conn.execute(
            "UPDATE goal SET linked_task_ids=?, updated_at=?, revision=?,"
            " last_operation_id=? WHERE goal_id=? AND revision=?",
            (json.dumps(links), now, new_rev, operation_id or row["last_operation_id"],
             goal_id, row["revision"]))
        _goal_trace_insert(conn, "g_" + now, goal_id, "transition",
                           "task_linked:" + task_id, prior_state=row["lifecycle_state"],
                           new_state=row["lifecycle_state"], action="link_task",
                           source=row["source"])
        conn.commit()
        _goal_log("link_task", goalId=goal_id, taskId=task_id)
        return {"goal": _row_to_goal(_goal_by_id(conn, goal_id)), "applied": True}
    finally:
        conn.close()

# ============================================================================
# END SLICE 8 — GOAL / EXECUTIVE SYSTEM V1
# ============================================================================
