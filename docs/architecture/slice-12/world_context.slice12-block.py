

# ============================================================================
# BEGIN SLICE 12 — PLANNING lane input + intent  [additive; append-only]
# Detects EXPLICIT planning framings only ("plan how to...", "outline the steps
# to...", "what would we need to do to...", "map out a plan for...") and builds a
# BOUNDED PlanningInput for exactly ONE PlanningSubject. Conservative precedence:
# it YIELDS (any=False) to explicit action (7.2 draft / 8 goal_create), to Slice 8
# goal-state queries, and to Slice 7.2 pending — so those accepted paths stay
# authoritative. Generic "what could we do next?" stays with Reasoning (Slice 9).
# READ-ONLY throughout; NO writes; Planning proposes only.
# ============================================================================


def _plan_mod():
    """Load the planning module in both package (VM) and flat (offline) layouts."""
    try:
        from . import planning as _p
    except Exception:
        import planning as _p
    return _p


def _plan_caps_mod():
    try:
        from . import planning_capabilities as _c
    except Exception:
        import planning_capabilities as _c
    return _c


_P_PLAN_RE = re.compile(
    r"\b("
    r"plan (how|out|for|a way|the steps|to)\b|"
    r"make a plan\b|draw up a plan\b|come up with a plan\b|devise a plan\b|"
    r"outline (the |a )?(steps|plan|approach)\b|"
    r"map out\b|lay out (the |a )?(steps|plan)\b|sketch (out )?a plan\b|"
    r"what would (we|i|you) need to do( to| in order to)?\b|"
    r"what steps (are|would be) (needed|required)\b|"
    r"how would (we|you|i) (go about|approach|plan)\b|"
    r"what('?s| is) the plan (to|for)\b"
    r")",
    re.IGNORECASE,
)
_P_FOLLOWUP_RE = re.compile(r"\b(follow[- ]?up|draft)\b", re.IGNORECASE)
# Explicit "plan only — do NOT act" cues. When an explicit plan verb is combined
# with a draft-shaped action AND one of these, the user is asking to PLAN the
# action, not perform it, so Planning owns the turn instead of yielding to the
# 7.2 draft path (which would otherwise create a draft, ignoring "do not do it").
_P_PLANONLY_RE = re.compile(
    r"\b(do ?n'?t (do|create|send|make|actually)|do not (do|create|send|make|actually)|"
    r"but (do ?n'?t|do not)|without (creating|doing|sending|making)|"
    r"just (plan|outline|map|sketch)|only plan|not yet)\b",
    re.IGNORECASE,
)


def _planning_none():
    return {"any": False, "mode": None, "app_id": None, "subtype": None}


def detect_planning_intent(message):
    """Classify a message for the Planning lane. Pure; never raises. Explicit
    plan framings only, and yields to existing accepted paths.

    Precedence (refinement 27, reconciled with acceptance B): requires an explicit
    plan verb; yields to Slice-8 goal create/query and Slice-7.2 pending; yields to
    a genuine 7.2 draft action UNLESS the turn is explicitly framed as plan-only
    ("plan how to create ... but do not do it"), where Planning owns it."""
    m = message or ""
    if not _P_PLAN_RE.search(m):
        return _planning_none()        # no explicit plan verb -> not a planning turn
    try:
        ci = detect_intent(m)          # Slice 7.2: belief / pending / draft
        gi = detect_goal_intent(m)     # Slice 8: goal_query / goal_create
    except Exception:
        return _planning_none()
    if gi.get("goal_create") or gi.get("goal_query"):
        return _planning_none()        # explicit goal track / goal-state -> Slice 8
    if ci.get("pending"):
        return _planning_none()        # pending -> Slice 7.2 authoritative
    if ci.get("draft") and not _P_PLANONLY_RE.search(m):
        return _planning_none()        # genuine draft action -> Slice 7.2 (unless plan-only)

    app_id = None
    mm = _APP_ID_RE.search(m)
    if mm:
        app_id = mm.group(1)
    subtype = "followup" if _P_FOLLOWUP_RE.search(m) else "general"
    return {"any": True, "mode": "PLANNING", "app_id": app_id, "subtype": subtype}


# ── Single PlanningSubject resolution (Planning NEVER arbitrates goals) ──────

def _plan_goal_for_app(app_id):
    """The single non-terminal durable goal for this application target, if any.
    Deterministic first-match on the durable goal rows; Planning does not choose
    among competing goals (Executive owns WHAT)."""
    doc = fetch_goals() or {}
    for g in (doc.get("goals") or []):
        tgt = g.get("target") or {}
        if (str(tgt.get("id")) == str(app_id)
                and g.get("lifecycleState") not in ("COMPLETED", "CANCELLED", "FAILED")):
            return g
    return None


def build_planning_subject(message, pintent):
    """Resolve EXACTLY ONE PlanningSubject. With an explicit target, plan for the
    durable Goal owning that target if one exists, else plan against USER_INTENT
    for that target. With no target, defer to the Executive-derived focus goal
    (already selected by Executive — not a Planning arbitration), else USER_INTENT."""
    app_id = pintent.get("app_id")
    if app_id:
        g = _plan_goal_for_app(app_id)
        if g:
            return {"kind": "GOAL", "goalRef": g.get("goalId"),
                    "goalType": g.get("type"),
                    "targetRef": "application:%s" % app_id, "targetAppId": str(app_id),
                    "userIntentRef": None}
        return {"kind": "USER_INTENT", "goalRef": None, "goalType": None,
                "targetRef": "application:%s" % app_id, "targetAppId": str(app_id),
                "userIntentRef": message}
    focus_doc = fetch_goal_focus() or {}
    foc = focus_doc.get("focus")
    if foc:
        tgt = foc.get("target") or {}
        tid = tgt.get("id")
        return {"kind": "GOAL", "goalRef": foc.get("goalId"), "goalType": foc.get("type"),
                "targetRef": ("application:%s" % tid) if tid else None,
                "targetAppId": (str(tid) if tid else None),
                "userIntentRef": None}
    return {"kind": "USER_INTENT", "goalRef": None, "goalType": None,
            "targetRef": None, "targetAppId": None, "userIntentRef": message}


def _plan_constraints(message):
    m = (message or "").lower()
    cons = []
    if re.search(r"do ?n'?t (send|do it)|do not (send|do it)|but do not|but don'?t|without sending",
                 m):
        cons.append("do not execute/send — plan only")
    return cons


def build_planning_input(message, session_key, pintent, snapshot, mot_snapshot, channel=None):
    """Assemble a BOUNDED PlanningInput for ONE subject. Reuses the Slice-10/11
    workspace-bounded cognitive context, then attaches the single PlanningSubject,
    the NON-AUTHORITATIVE planning capability view, and (for a supported subject)
    real subject evidence. NO broad goalCandidates[] (Planning does not arbitrate).
    Read-only; provenance by ref; fail-open."""
    import hashlib as _hl
    import time as _t
    corr = "p." + _hl.sha256(
        (str(session_key) + "|" + (message or "") + "|" + str(_t.time())).encode("utf-8")
    ).hexdigest()[:16]

    # Reuse the bounded cognitive context (beliefs / focus / pending) exactly as
    # Reasoning does, honouring the Workspace attention boundary when present.
    rintent = {"any": True, "mode": "PLANNING",
               "app_id": pintent.get("app_id"), "subtype": pintent.get("subtype")}
    try:
        base = select_reasoning_input_m(
            message, session_key, rintent, snapshot, mot_snapshot, channel=channel) or {}
    except Exception:
        logger.debug("world_context: planning base ri failed (fail-open)", exc_info=True)
        base = {}

    subject = build_planning_subject(message, pintent)
    caps = _plan_caps_mod()

    # Subject evidence from REAL owners only (drafts store) for the supported
    # career follow-up subject; never fabricated.
    subject_evidence = {"sourceRefs": [], "unresolvedFollowups": None}
    app_id = subject.get("targetAppId")
    if app_id:
        subject_evidence["sourceRefs"].append("application:%s" % app_id)
        try:
            fu = find_unresolved_followups(app_id)   # list | None (lookup error)
        except Exception:
            fu = None
        if isinstance(fu, list):
            subject_evidence["unresolvedFollowups"] = [
                {"draftId": d.get("draftId"),
                 "target": (d.get("target") or {}),
                 "status": d.get("status")} for d in fu]
            subject_evidence["sourceRefs"].extend(
                [d.get("draftId") for d in fu if d.get("draftId")])

    template_eligible = bool(
        app_id and (pintent.get("subtype") == "followup"
                    or subject.get("goalType") == "career.followup"))

    return {
        "schemaVersion": 1,
        "correlationId": corr,
        "timestamp": _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime()),
        "channel": channel,
        "mode": "PLANNING",
        "userIntent": message,
        "explicitUserConstraints": _plan_constraints(message),
        "planningSubject": subject,
        "subjectEvidence": subject_evidence,
        "templateEligible": template_eligible,
        "maxSteps": 6,
        # bounded cognitive context (by ref); NO broad goalCandidates arbitration
        "currentFocus": base.get("currentFocus"),
        "relevantBeliefs": (base.get("relevantBeliefs") or [])[:8],
        "relevantTasks": (base.get("relevantTasks") or [])[:8],
        "relevantDrafts": (base.get("relevantDrafts") or [])[:8],
        "workspaceFocus": base.get("workspaceFocus"),
        "motivationSummary": base.get("motivationSummary"),
        # non-authoritative capability view (planning owns this, via planning_capabilities)
        "capabilityView": caps.view_summary(),
        # Reasoning candidateNextSteps are OPTIONAL raw material only; absent in the
        # V1 standalone planning lane. When present they are grounded/validated the
        # same as any candidate — never copied verbatim into a PlanStep.
        "reasoningResult": None,
        "worldUnavailable": bool(base.get("worldUnavailable")),
    }


def planning_trace(result):
    try:
        return (result or {}).get("traceMetadata") or {}
    except Exception:
        return {"fallback_reason": "trace_error"}

# ============================================================================
# END SLICE 12 — PLANNING lane input + intent
# ============================================================================
