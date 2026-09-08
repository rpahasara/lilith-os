

# ============================================================================
# BEGIN SLICE 10 — GLOBAL WORKSPACE / ATTENTION candidate extraction + bounded
# ReasoningInput  [additive; append-only]
# Extracts normalized AttentionCandidate refs from durable World + Goal + Task +
# Draft state (READ-ONLY), and — when a live WorkspaceSnapshot selects a primary
# — assembles a ReasoningInput BOUNDED to the selected refs plus bounded support
# expansion (Refinement C). Fail-open throughout: any failure yields the exact
# existing Slice 9 build_reasoning_input. Deterministic phrase/entity detection
# only; no LLM salience. Workspace performs NO writes.
# ============================================================================

# Explicit "switch attention away" cues (ATTENTION_OVERRIDE). Naming an entity
# WITHOUT one of these is USER_REFERENCED (relevance), not an override.
_WS_OVERRIDE_RE = re.compile(
    r"\b(forget (about )?(that|it|the (last|previous)|app\w*|application|job|role)|"
    r"never ?mind (that|it)|ignore (that|it|the (last|previous))|"
    r"drop (that|it|the (last|previous))|set (that|it) aside|put (that|it) aside|"
    r"instead|for now|(switch|change|move) (to|focus)|"
    r"(focus on|look at|attend to|let'?s look at)\b[^.?!]*\binstead)\b",
    re.IGNORECASE,
)
_WS_TERMINAL_GOAL_STATES = {"COMPLETED", "CANCELLED", "FAILED"}


def detect_attention_override(message):
    """Distinguish USER_REFERENCED (entity named) from ATTENTION_OVERRIDE (switch
    away). Pure; never raises. Deterministic phrase + entity detection only.

    override_app_id: the NEW target (last app id, since 'instead/focus on X' and
    'forget A, look at X' put the new target last). referenced_app_id: first id."""
    m = message or ""
    override = bool(_WS_OVERRIDE_RE.search(m))
    ids = [mm.group(1) for mm in _APP_ID_RE.finditer(m)]
    return {
        "override": override,
        "override_app_id": (ids[-1] if (override and ids) else None),
        "referenced_app_id": (ids[0] if ids else None),
        "app_ids": ids,
    }


def _ws_recency(iso, now_ts=None):
    """Deterministic recency in [0,1], ~14-day half-life (mirrors _wm_recency)."""
    if not iso:
        return 0.0
    try:
        import datetime as _dt
        t = _dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0
    import time as _t
    now = now_ts if now_ts is not None else _t.time()
    return 0.5 ** (max(0.0, (now - t) / 86400.0) / 14.0)


def _ws_recent(iso, now_ts=None):
    """recentlyChanged: source updated within ~3 days. Source-timestamp derived
    only — V1 claims NO cross-turn novelty (Refinement D)."""
    return _ws_recency(iso, now_ts) >= 0.86  # ~0.5**(3/14)


def _ws_goal_target_app(g):
    tgt = (g or {}).get("target") or {}
    if tgt.get("type") == "career.application" and tgt.get("id") is not None:
        return str(tgt.get("id"))
    return None


def build_attention_candidates(message, session_key, rintent, channel=None):
    """Produce normalized AttentionCandidate dicts from durable source refs.
    READ-ONLY (GET only); never raises; never fabricates. Returns a list."""
    try:
        ov = detect_attention_override(message)
    except Exception:
        ov = {"override": False, "override_app_id": None, "referenced_app_id": None, "app_ids": []}
    referenced = set(ov.get("app_ids") or [])
    ref_first = ov.get("referenced_app_id")
    if rintent and rintent.get("app_id"):
        referenced.add(str(rintent["app_id"]))
        ref_first = ref_first or str(rintent["app_id"])
    override_app = ov.get("override_app_id") if ov.get("override") else None

    cands = []
    goals_doc = fetch_goals() or {}
    focus_doc = fetch_goal_focus() or {}
    focus = (focus_doc.get("focus") or {})
    focus_goal_id = focus.get("goalId")

    # Map blockedBy draft-id -> blocked goalId so the goal+draft blocker collapses.
    draft_to_goal = {}
    goals = (goals_doc.get("goals") or []) if isinstance(goals_doc, dict) else []
    for g in goals:
        state = g.get("lifecycleState")
        if state in _WS_TERMINAL_GOAL_STATES:
            continue
        gid = g.get("goalId")
        app = _ws_goal_target_app(g)
        is_ref = bool(app and app in referenced)
        is_override = bool(app and override_app and app == override_app)
        rec = _ws_recency(g.get("updatedAt") or g.get("createdAt"))
        recent = _ws_recent(g.get("updatedAt") or g.get("createdAt"))
        # GOAL candidate
        cands.append({
            "sourceType": "GOAL", "sourceRef": gid, "category": "goal",
            "summary": _goal_summary(g),
            "userReferenced": is_ref, "userOverrideTarget": is_override,
            "isFocusGoal": bool(gid and gid == focus_goal_id),
            "deadline": bool(g.get("deadline")),
            "recency": rec, "recentlyChanged": recent,
            "relatedGoalId": gid,
            "targetApps": ([app] if app else []),
            "lifecycle": "until_resolved", "provenance": "goal-store@%s" % (channel or "?"),
        })
        # BLOCKER candidate for a BLOCKED goal
        if state == "BLOCKED":
            blocked_by = [str(x) for x in (g.get("blockedBy") or [])]
            for d in blocked_by:
                draft_to_goal[d] = gid
            cands.append({
                "sourceType": "GOAL", "sourceRef": "blocker:%s" % gid, "category": "blocker",
                "summary": "goal %s BLOCKED: %s (blockedBy=%s)" % (
                    gid, g.get("blockedReason"), ",".join(blocked_by) or "-"),
                "userReferenced": is_ref, "userOverrideTarget": is_override,
                "blockingImpact": bool(gid and gid == focus_goal_id),
                "recency": rec, "recentlyChanged": recent,
                "relatedGoalId": gid, "relatedDraftIds": blocked_by,
                "targetApps": ([app] if app else []),
                "lifecycle": "until_resolved", "provenance": "goal-store@%s" % (channel or "?"),
            })

    # DRAFT candidates (UNSENT). relatedGoalId links to a blocked goal so the
    # goal-blocker + draft collapse deterministically in the workspace.
    drafts_doc = _get_json("/os/drafts?limit=200") or {}
    for d in ((drafts_doc.get("drafts") or []) if isinstance(drafts_doc, dict) else [])[:50]:
        if d.get("status") != "created":
            continue  # dormant/sent drafts are not attention candidates
        did = d.get("draftId")
        tg = d.get("target") or {}
        app = str(tg.get("id")) if tg.get("id") is not None else None
        cands.append({
            "sourceType": "DRAFT", "sourceRef": did, "category": "blocker"
            if did in draft_to_goal else "draft",
            "summary": "%s kind=%s target=application:%s status=created(UNSENT)" % (
                did, d.get("kind"), app),
            "userReferenced": bool(app and app in referenced),
            "userOverrideTarget": bool(app and override_app and app == override_app),
            "approvalPending": True,
            "blockingImpact": bool(draft_to_goal.get(did) and draft_to_goal.get(did) == focus_goal_id),
            "recency": _ws_recency(d.get("updatedAt") or d.get("createdAt")),
            "recentlyChanged": _ws_recent(d.get("updatedAt") or d.get("createdAt")),
            "relatedGoalId": draft_to_goal.get(did),
            "relatedDraftIds": [did], "targetApps": ([app] if app else []),
            "lifecycle": "until_resolved", "provenance": "draft-store@%s" % (channel or "?"),
        })

    # TASK candidates (pending / failed only).
    tasks_doc = _get_json("/os/tasks?limit=200") or {}
    pend = {"waiting_for_approval", "created", "planning", "running", "verifying"}
    for t in ((tasks_doc.get("tasks") or []) if isinstance(tasks_doc, dict) else [])[:50]:
        st = t.get("status")
        appr = t.get("approvalState")
        failed = st in ("failed", "error")
        if not (st in pend or appr in ("required", "expired") or failed):
            continue
        tid = t.get("taskId")
        tg = t.get("target") or {}
        app = str(tg.get("id")) if tg.get("id") is not None else None
        cands.append({
            "sourceType": "TASK", "sourceRef": tid, "category": "task",
            "summary": "%s [%s] %s" % (tid, st, t.get("title")),
            "userReferenced": bool(app and app in referenced),
            "userOverrideTarget": bool(app and override_app and app == override_app),
            "approvalPending": bool(st == "waiting_for_approval" or appr in ("required", "expired")),
            "taskFailure": bool(failed),
            "recency": _ws_recency(t.get("updatedAt") or t.get("createdAt")),
            "recentlyChanged": _ws_recent(t.get("updatedAt") or t.get("createdAt")),
            "relatedTaskIds": [tid], "targetApps": ([app] if app else []),
            "lifecycle": "until_resolved", "provenance": "task-store@%s" % (channel or "?"),
        })

    # WORLD_BELIEF candidates — ONLY conflicted/stale beliefs on a relevant entity
    # (normal beliefs are support context, not attention candidates). UNKNOWN is
    # absence -> no candidate.
    world = None
    if referenced:
        for app in list(referenced)[:5]:
            w = fetch_world(entity_type="career.application", entity_id=app)
            for b in ((w or {}).get("beliefs") or []):
                life = b.get("lifecycle_state")
                contradicted = bool(b.get("contradicted_by"))
                if life in ("CONFLICTED", "STALE") or contradicted:
                    cands.append(_ws_belief_candidate(b, referenced, override_app, channel))
    else:
        world = fetch_world()
        for b in ((world or {}).get("beliefs") or []):
            life = b.get("lifecycle_state")
            if life in ("CONFLICTED", "STALE") or bool(b.get("contradicted_by")):
                cands.append(_ws_belief_candidate(b, referenced, override_app, channel))

    return cands


def _ws_belief_candidate(b, referenced, override_app, channel):
    app = str(b.get("entity_id")) if b.get("entity_id") is not None else None
    life = b.get("lifecycle_state")
    return {
        "sourceType": "WORLD_BELIEF", "sourceRef": b.get("key"), "category": "belief",
        "summary": "%s:%s %s=%s [%s]" % (
            b.get("entity_type"), app, b.get("predicate"),
            _summarize_value(b.get("value")), life),
        "userReferenced": bool(app and app in referenced),
        "userOverrideTarget": bool(app and override_app and app == override_app),
        "conflict": bool(life == "CONFLICTED" or b.get("contradicted_by")),
        "stale": bool(life == "STALE"),
        "recency": _ws_recency(b.get("updated_at") or b.get("observed_at")),
        "recentlyChanged": _ws_recent(b.get("updated_at") or b.get("observed_at")),
        "relatedBeliefRefs": [b.get("key")], "targetApps": ([app] if app else []),
        "lifecycle": "until_resolved", "provenance": "world-model@%s" % (channel or "?"),
    }


# ── Bounded ReasoningInput (Refinement C): selection is the real boundary ────

def _ws_collect_refs(snapshot):
    sel = []
    if (snapshot or {}).get("primaryFocus"):
        sel.append(snapshot["primaryFocus"])
    sel.extend((snapshot or {}).get("secondaryItems") or [])
    apps, goal_ids, draft_ids, task_ids, belief_keys = set(), set(), set(), set(), set()
    for c in sel:
        for a in (c.get("targetApps") or []):
            apps.add(str(a))
        if c.get("relatedGoalId"):
            goal_ids.add(str(c["relatedGoalId"]))
        for d in (c.get("relatedDraftIds") or []):
            draft_ids.add(str(d))
        for t in (c.get("relatedTaskIds") or []):
            task_ids.add(str(t))
        for k in (c.get("relatedBeliefRefs") or []):
            belief_keys.add(str(k))
    return sel, apps, goal_ids, draft_ids, task_ids, belief_keys


def build_reasoning_input_bounded(message, session_key, rintent, snapshot, channel=None):
    """Assemble a ReasoningInput BOUNDED to the workspace-selected refs plus
    bounded support expansion (linked goal/draft/task + target-entity beliefs).
    Excludes unrelated unselected rows (Refinement C). Returns None when the
    snapshot has no primary (caller falls open to build_reasoning_input)."""
    import time as _t
    if not (snapshot or {}).get("primaryFocus"):
        return None
    sel, apps, goal_ids, draft_ids, task_ids, belief_keys = _ws_collect_refs(snapshot)

    # Beliefs: ONLY for selected target entities / selected belief keys.
    rel_beliefs = []
    world_seen = False
    for app in list(apps)[:5]:
        w = fetch_world(entity_type="career.application", entity_id=app)
        if w is not None:
            world_seen = True
        for b in ((w or {}).get("beliefs") or []):
            rel_beliefs.append(_belief_to_ref(b))
    if not apps and belief_keys:
        w = fetch_world()
        if w is not None:
            world_seen = True
        for b in ((w or {}).get("beliefs") or []):
            if str(b.get("key")) in belief_keys:
                rel_beliefs.append(_belief_to_ref(b))
    rel_beliefs = rel_beliefs[:TOPK]

    # Goals: ONLY selected goal ids + the Executive focus goal (for continuity).
    goals_doc = fetch_goals() or {}
    focus_doc = fetch_goal_focus() or {}
    foc = (focus_doc.get("focus") or {})
    focus_goal_id = foc.get("goalId")
    keep_goal_ids = set(goal_ids)
    if focus_goal_id:
        keep_goal_ids.add(str(focus_goal_id))
    goal_candidates = [
        _goal_summary(g) for g in ((goals_doc.get("goals") or []))
        if str(g.get("goalId")) in keep_goal_ids
    ][:10]
    arb = (focus_doc.get("arbitration") or {})
    current_focus = None
    if foc:
        current_focus = "%s — %s (winner by %s)" % (
            foc.get("goalId"), foc.get("title"), arb.get("ruleFired"))

    # Tasks/drafts: ONLY selected refs, or (bounded) pending items on a selected app.
    tasks_doc = _get_json("/os/tasks?limit=200") or {}
    pend = {"waiting_for_approval", "created", "planning", "running", "verifying"}
    rel_tasks = []
    for t in ((tasks_doc.get("tasks") or []) if isinstance(tasks_doc, dict) else []):
        tid = str(t.get("taskId"))
        tg = t.get("target") or {}
        app = str(tg.get("id")) if tg.get("id") is not None else None
        selected = tid in task_ids
        on_app = bool(app and app in apps and (
            t.get("status") in pend or t.get("approvalState") in ("required", "expired")))
        if selected or on_app:
            rel_tasks.append("%s [%s] %s" % (t.get("taskId"), t.get("status"), t.get("title")))
    rel_tasks = rel_tasks[:10]

    drafts_doc = _get_json("/os/drafts?limit=200") or {}
    rel_drafts = []
    for d in ((drafts_doc.get("drafts") or []) if isinstance(drafts_doc, dict) else []):
        did = str(d.get("draftId"))
        tg = d.get("target") or {}
        app = str(tg.get("id")) if tg.get("id") is not None else None
        selected = did in draft_ids
        on_app = bool(app and app in apps and d.get("status") == "created")
        if selected or on_app:
            rel_drafts.append("%s kind=%s target=application:%s status=created(UNSENT)" % (
                d.get("draftId"), d.get("kind"), app))
    rel_drafts = rel_drafts[:10]

    prim = snapshot["primaryFocus"]
    return {
        "schemaVersion": 1,
        "correlationId": snapshot.get("correlationId"),
        "timestamp": _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime()),
        "channel": channel,
        "userIntent": message,
        "mode": rintent.get("mode") or "CONVERSATIONAL_SYNTHESIS",
        "relevantBeliefs": rel_beliefs,
        "workingMemorySummary": "workspace-bounded: %d selected attention item(s)" % len(sel),
        "currentFocus": current_focus,
        "workspaceFocus": prim.get("summary"),
        "workspaceSelectionReason": snapshot.get("selectionReason"),
        "goalCandidates": goal_candidates,
        "relevantTasks": rel_tasks,
        "relevantDrafts": rel_drafts,
        "policyVisibleConstraints": list(_POLICY_VISIBLE_CONSTRAINTS),
        "capabilityAvailabilitySummary": _CAPABILITY_AVAILABILITY,
        "worldUnavailable": (not world_seen) and bool(apps or belief_keys),
        "boundedBy": "workspace",
    }


def select_reasoning_input(message, session_key, rintent, snapshot, channel=None):
    """Choose the ReasoningInput: workspace-bounded when a live snapshot selects a
    primary, else the exact existing Slice 9 builder. Fail-open: any exception in
    the bounded path falls back to build_reasoning_input (Refinement C test 3)."""
    if snapshot is not None and (snapshot or {}).get("primaryFocus"):
        try:
            ri = build_reasoning_input_bounded(message, session_key, rintent, snapshot, channel=channel)
            if ri is not None:
                return ri
        except Exception:
            logger.debug("world_context: bounded reasoning input failed (fail-open)", exc_info=True)
    return build_reasoning_input(message, session_key, rintent, channel=channel)

# ============================================================================
# END SLICE 10 — GLOBAL WORKSPACE / ATTENTION
# ============================================================================
