

# ============================================================================
# BEGIN SLICE 11 — MOTIVATION / HOMEOSTASIS  [additive; append-only]
# Derives bounded ORDINAL DriveSignals (COHERENCE, GOAL_COMPLETION; SAFETY is
# synthetic/test-only) from state ALREADY SCOPED to the current turn's Workspace
# candidate pool + explicit user-referenced target + durable Executive focus.
# NO broad global scan. READ-ONLY (GET only). Fail-open throughout: any failure
# yields a valid partial MotivationSnapshot (or None) and the Slice-10/9 path is
# unchanged. Performs NO writes. Never consumes a ReasoningResult.
# ============================================================================

_MOT_PEND_TASK = {"waiting_for_approval", "created", "planning", "running", "verifying"}


def _mot_mod():
    """Load the motivation module in both the package (VM) and flat (offline
    test) layouts."""
    try:
        from . import motivation as _m
    except Exception:
        import motivation as _m
    return _m


def _mot_referenced_apps(message, rintent):
    """Same reference/override detection the Slice-10 candidate builder uses."""
    try:
        ov = detect_attention_override(message)
    except Exception:
        ov = {"app_ids": []}
    referenced = set(ov.get("app_ids") or [])
    if rintent and rintent.get("app_id"):
        referenced.add(str(rintent["app_id"]))
    return referenced


def _mot_raw_refs(ws_cands):
    """Every exact ref already represented by a RAW ws candidate (for dedup)."""
    refs = set()
    for c in (ws_cands or []):
        for k in ("sourceRef", "relatedGoalId"):
            v = c.get(k)
            if v is not None:
                refs.add(str(v))
        for field in ("relatedBeliefRefs", "relatedTaskIds", "relatedDraftIds", "targetApps"):
            for v in (c.get(field) or []):
                refs.add(str(v))
    return refs


def _mot_coherence_inputs(ws_cands):
    """CONFLICTED/STALE belief conditions taken ONLY from ws_cands belief
    candidates (Slice-10 already scoped them). No new world scan."""
    conds = []
    for c in (ws_cands or []):
        if c.get("sourceType") != "WORLD_BELIEF":
            continue
        if not (c.get("conflict") or c.get("stale")):
            continue
        conds.append({
            "key": c.get("sourceRef"),
            "entity_id": (c.get("targetApps") or [None])[0],
            "lifecycle": "CONFLICTED" if c.get("conflict") else "STALE",
            "contradicted": bool(c.get("conflict")),
        })
    return conds


def _mot_critical_belief_keys(ws_cands, focus_goal):
    """Belief keys provably referenced by a selected/focus blocker or the focus
    goal's blockedBy (decision 4). Typically empty in the current schema, so
    COHERENCE caps at SIGNIFICANT — that is the honest outcome."""
    keys = set()
    for c in (ws_cands or []):
        if c.get("category") == "blocker" and (c.get("blockingImpact") or c.get("userReferenced")):
            for k in (c.get("relatedBeliefRefs") or []):
                keys.add(str(k))
    for b in ((focus_goal or {}).get("blockedBy") or []):
        keys.add(str(b))
    return keys


def _mot_scoped_goal_ids(ws_cands, referenced, focus_goal_id, goals_by_app):
    gids = set()
    if focus_goal_id:
        gids.add(str(focus_goal_id))
    for c in (ws_cands or []):
        if c.get("sourceType") == "GOAL" and c.get("relatedGoalId"):
            gids.add(str(c["relatedGoalId"]))
    for app in referenced:
        for gid in goals_by_app.get(str(app), []):
            gids.add(str(gid))
    return gids


def build_motivation_snapshot(message, session_key, rintent, ws_cands, channel=None):
    """Assemble the ephemeral MotivationSnapshot for this turn. Never raises."""
    _motivation = _mot_mod()
    avail = {"world": True, "goals": False, "tasks": False, "drafts": False}
    partial = False
    try:
        referenced = _mot_referenced_apps(message, rintent)

        # ── goals (scoped) ────────────────────────────────────────────────
        goals_doc = fetch_goals()
        focus_doc = fetch_goal_focus()
        avail["goals"] = goals_doc is not None
        if goals_doc is None:
            partial = True
        goals = (goals_doc.get("goals") or []) if isinstance(goals_doc, dict) else []
        goals_index = {}
        goals_by_app = {}
        for g in goals:
            gid = g.get("goalId")
            if gid is None:
                continue
            goals_index[str(gid)] = g
            app = _ws_goal_target_app(g)
            if app:
                goals_by_app.setdefault(str(app), []).append(str(gid))
        focus = ((focus_doc or {}).get("focus") or {}) if isinstance(focus_doc, dict) else {}
        focus_goal_id = focus.get("goalId")
        focus_goal = goals_index.get(str(focus_goal_id)) if focus_goal_id else None

        # ── tasks (only to resolve typed hard blockers; scoped lookups) ───
        tasks_doc = _get_json("/os/tasks?limit=200")
        avail["tasks"] = tasks_doc is not None
        tasks_index = {}
        for t in ((tasks_doc.get("tasks") or []) if isinstance(tasks_doc, dict) else []):
            tid = t.get("taskId")
            if tid is not None:
                tasks_index[str(tid)] = t

        scoped_gids = _mot_scoped_goal_ids(ws_cands, referenced, focus_goal_id, goals_by_app)
        goal_conditions = []
        for gid in scoped_gids:
            g = goals_index.get(str(gid))
            if not g:
                continue
            blocked_by = [str(x) for x in (g.get("blockedBy") or [])]
            hard = [b for b in blocked_by
                    if str((tasks_index.get(b) or {}).get("status")) in _motivation._FAILED_TASK_STATES]
            app = _ws_goal_target_app(g)
            goal_conditions.append({
                "goalId": gid,
                "lifecycleState": g.get("lifecycleState"),
                "isFocus": bool(focus_goal_id and str(gid) == str(focus_goal_id)),
                "userReferenced": bool(app and app in referenced),
                "source": g.get("source"),
                "blockedBy": blocked_by,
                "targetApp": app,
                "hardBlockerFailedTaskIds": hard,
            })

        # ── coherence (from ws_cands belief candidates only) ──────────────
        coherence = _motivation.classify_coherence(
            _mot_coherence_inputs(ws_cands),
            critical_belief_keys=_mot_critical_belief_keys(ws_cands, focus_goal),
            channel=channel)
        goal_completion = _motivation.classify_goal_completion(goal_conditions, channel=channel)

        snap = _motivation.build_snapshot(
            coherence=coherence, goal_completion=goal_completion, safety=None,
            raw_refs=_mot_raw_refs(ws_cands), channel=channel,
            source_availability=avail, partial=partial)
        return snap
    except Exception:
        logger.debug("world_context: build_motivation_snapshot failed (fail-open)", exc_info=True)
        try:
            return _motivation.build_snapshot(
                coherence=None, goal_completion=None, safety=None,
                raw_refs=None, channel=channel,
                source_availability=avail, partial=True)
        except Exception:
            return None


def motivation_candidates(mot_snapshot):
    """Eligible MOTIVATION_DRIVE candidates for the Workspace pool. Never raises."""
    try:
        return _mot_mod().to_attention_candidates(
            mot_snapshot, channel=(mot_snapshot or {}).get("channel"))
    except Exception:
        logger.debug("world_context: motivation_candidates failed (fail-open)", exc_info=True)
        return []


def motivation_trace(mot_snapshot):
    try:
        return _mot_mod().build_trace(mot_snapshot)
    except Exception:
        return {"fallback_reason": "trace_error"}


def select_reasoning_input_m(message, session_key, rintent, snapshot, mot_snapshot, channel=None):
    """Slice-10 select_reasoning_input, then attach a read-only motivationSummary
    BOUNDED to the Workspace-selected/supporting drives (decision 10). Fail-open:
    the base ReasoningInput is returned unchanged on any motivation error."""
    ri = select_reasoning_input(message, session_key, rintent, snapshot, channel=channel)
    try:
        if ri is not None and mot_snapshot and snapshot and snapshot.get("primaryFocus"):
            _motivation = _mot_mod()
            sel, apps, goal_ids, draft_ids, task_ids, belief_keys = _ws_collect_refs(snapshot)
            selected_refs = set(apps) | set(goal_ids) | set(draft_ids) | set(task_ids) | set(belief_keys)
            sel_cand_refs = [c.get("sourceRef") for c in sel if c.get("sourceRef")]
            ri["motivationSummary"] = _motivation.bounded_summary(
                mot_snapshot, selected_refs, sel_cand_refs)
    except Exception:
        logger.debug("world_context: motivationSummary attach failed (fail-open)", exc_info=True)
    return ri

# ============================================================================
# END SLICE 11 — MOTIVATION / HOMEOSTASIS
# ============================================================================
