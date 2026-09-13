

# ============================================================================
# BEGIN SLICE 9 — REASONING lane input + intent  [additive; append-only]
# Detects NEW analytic framings only (uncertainty / blocker / options / info /
# analyze) and builds a BOUNDED ReasoningInput from durable World + Goal + pending
# state. Conservative precedence: it YIELDS (any=False) to explicit action
# (7.2 draft / 8 goal_create), to Slice 8 goal-state queries, and to Slice 7.2
# pending — so those accepted paths stay authoritative. READ-ONLY throughout.
# ============================================================================

_R_BLOCKER = re.compile(
    r"\b(why (can'?t|cannot|can not|are you unable to|is it not possible to)\b|"
    r"why (is|are)\b[^.?!]*\b(blocked|on hold|stalled|stuck)|"
    r"what('?s| is) blocking|what is in the way|what('?s| is) stopping)\b",
    re.IGNORECASE,
)
_R_OPTIONS = re.compile(
    r"\b(what (could|should|can) (we|you|i)\b[^.?!]*\bdo\b|"
    r"what are (my|our|the) options|what next|next steps?|"
    r"how (should|could|do) (we|i) proceed|what do we do (about|for|next))\b",
    re.IGNORECASE,
)
_R_INFO = re.compile(
    r"\b(what (information|info|else) (is|do you|would)\b[^.?!]*\b(need|missing|help|resolve|clarify)|"
    r"what would (resolve|clarify|settle)|what('?s| is) missing)\b",
    re.IGNORECASE,
)
_R_UNCERTAIN = re.compile(
    r"\b(uncertain|uncertainty|unknown|unsure|not sure|how (confident|sure) are you|"
    r"what('?s| is) unclear|what('?s| is) not known|what are the unknowns)\b",
    re.IGNORECASE,
)
_R_ANALYZE = re.compile(
    r"\b(analyz(e|se)|assess|evaluate|interpret|implications?|"
    r"what does (this|that|the evidence|it) (mean|imply|suggest|tell us)|"
    r"what do you make of)\b",
    re.IGNORECASE,
)

_REASONING_MODES = (
    "FACTUAL_INTERPRETATION", "GOAL_ANALYSIS", "BLOCKER_ANALYSIS",
    "OPTION_GENERATION", "UNCERTAINTY_ANALYSIS", "CONVERSATIONAL_SYNTHESIS",
)


def _reasoning_none():
    return {"any": False, "mode": None, "app_id": None, "subtype": None}


def detect_reasoning_intent(message):
    """Classify a message for the Reasoning lane. Pure; never raises.
    Conservative — analytic framings only, and yields to existing accepted paths."""
    m = message or ""
    # Precedence: explicit action or an already-accepted lane owns the turn.
    try:
        ci = detect_intent(m)          # Slice 7.2: belief / pending / draft
        gi = detect_goal_intent(m)     # Slice 8: goal_query / goal_create
    except Exception:
        return _reasoning_none()
    if ci.get("draft") or gi.get("goal_create"):
        return _reasoning_none()       # explicit action -> existing durable path
    if gi.get("goal_query"):
        return _reasoning_none()       # goal-state -> Slice 8 authoritative
    if ci.get("pending"):
        return _reasoning_none()       # pending -> Slice 7.2 authoritative

    blocker = bool(_R_BLOCKER.search(m))
    options = bool(_R_OPTIONS.search(m))
    info = bool(_R_INFO.search(m))
    uncertain = bool(_R_UNCERTAIN.search(m))
    analyze = bool(_R_ANALYZE.search(m))
    if not (blocker or options or info or uncertain or analyze):
        return _reasoning_none()

    if blocker:
        mode, subtype = "BLOCKER_ANALYSIS", "blocker"
    elif options:
        mode, subtype = "OPTION_GENERATION", "options"
    elif info or uncertain:
        mode, subtype = "UNCERTAINTY_ANALYSIS", "uncertainty"
    else:
        mode, subtype = "FACTUAL_INTERPRETATION", "analyze"

    app_id = None
    mm = _APP_ID_RE.search(m)
    if mm:
        app_id = mm.group(1)
    return {"any": True, "mode": mode, "app_id": app_id, "subtype": subtype}


# ── Bounded ReasoningInput assembly (durable, read-only, provenance by ref) ──

# Policy-visible constraints the Reasoning component may NAME (never decide). These
# reflect the durable policy posture; Reasoning does not evaluate permission.
_POLICY_VISIBLE_CONSTRAINTS = [
    "external follow-up send requires explicit approval (no autonomous send)",
    "mail.send_email is PROHIBITED — no external send capability exists",
    "creating an internal draft is reversible and requires approval (internal write)",
    "google-workspace connector is unavailable (OAuth not connected)",
]
_CAPABILITY_AVAILABILITY = (
    "internal-career-store: available; google-workspace: unavailable")


def _belief_to_ref(b):
    prov = []
    for p in (b.get("provenance") or [])[:3]:
        r = p.get("origin_ref") or p.get("source_id") or p.get("source_class")
        if r and r not in prov:
            prov.append(r)
    conf = b.get("confidence") or {}
    return {
        "key": b.get("key"),
        "predicate": b.get("predicate"),
        "value": _summarize_value(b.get("value")),
        "lifecycle": b.get("lifecycle_state"),
        "epistemic": b.get("epistemic_state"),
        "confidence": "%s (%s)" % (conf.get("value"), conf.get("tier")),
        "provenanceRefs": prov,
    }


def _goal_summary(g):
    tgt = g.get("target") or {}
    s = "%s [%s] type=%s priority=%s" % (
        g.get("goalId"), g.get("lifecycleState"), g.get("type"), g.get("priority"))
    if tgt.get("id"):
        s += " target=%s:%s" % (tgt.get("type"), tgt.get("id"))
    if g.get("lifecycleState") == "BLOCKED":
        s += " blockedReason=%s blockedBy=%s" % (
            g.get("blockedReason"), ",".join(g.get("blockedBy") or []))
    return s


def build_reasoning_input(message, session_key, rintent, channel=None):
    """Assemble a BOUNDED ReasoningInput dict from durable World + Goal + pending
    state. No raw DB/session/memory dump; provenance by ref; epistemic preserved.
    Fail-open: missing sources are simply omitted (never fabricated)."""
    import hashlib as _hl
    import time as _t
    corr = "r." + _hl.sha256(
        (str(session_key) + "|" + (message or "") + "|" + str(_t.time())).encode("utf-8")
    ).hexdigest()[:16]
    app_id = rintent.get("app_id")

    if app_id:
        world = fetch_world(entity_type="career.application", entity_id=app_id)
    elif _career_focus(message):
        world = fetch_world(entity_type="career.application")
    else:
        world = fetch_world()
    beliefs = list((world or {}).get("beliefs") or [])
    if app_id:
        focused = [b for b in beliefs if str(b.get("entity_id")) == str(app_id)]
        beliefs = focused or beliefs
    rel_beliefs = [_belief_to_ref(b) for b in beliefs[:TOPK]]

    goals_doc = fetch_goals()
    focus_doc = fetch_goal_focus()
    goal_candidates = [_goal_summary(g) for g in ((goals_doc or {}).get("goals") or [])[:10]]
    foc = (focus_doc or {}).get("focus")
    arb = (focus_doc or {}).get("arbitration") or {}
    current_focus = None
    if foc:
        current_focus = "%s — %s (winner by %s)" % (
            foc.get("goalId"), foc.get("title"), arb.get("ruleFired"))

    tasks_doc = _get_json("/os/tasks?limit=200") or {}
    drafts_doc = _get_json("/os/drafts?limit=200") or {}
    pend_task_statuses = {"waiting_for_approval", "created", "planning", "running", "verifying"}
    rel_tasks = [
        "%s [%s] %s" % (t.get("taskId"), t.get("status"), t.get("title"))
        for t in ((tasks_doc.get("tasks") or []) if isinstance(tasks_doc, dict) else [])
        if t.get("status") in pend_task_statuses or t.get("approvalState") in ("required", "expired")
    ][:10]
    rel_drafts = []
    for d in ((drafts_doc.get("drafts") or []) if isinstance(drafts_doc, dict) else []):
        if d.get("status") == "created":
            tg = d.get("target") or {}
            rel_drafts.append("%s kind=%s target=application:%s status=created(UNSENT)" % (
                d.get("draftId"), d.get("kind"), tg.get("id")))
    rel_drafts = rel_drafts[:10]

    return {
        "schemaVersion": 1,
        "correlationId": corr,
        "timestamp": _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime()),
        "channel": channel,
        "userIntent": message,
        "mode": rintent.get("mode") or "CONVERSATIONAL_SYNTHESIS",
        "relevantBeliefs": rel_beliefs,
        "workingMemorySummary": "top-%d durable beliefs by relevance" % len(rel_beliefs),
        "currentFocus": current_focus,
        "goalCandidates": goal_candidates,
        "relevantTasks": rel_tasks,
        "relevantDrafts": rel_drafts,
        "policyVisibleConstraints": list(_POLICY_VISIBLE_CONSTRAINTS),
        "capabilityAvailabilitySummary": _CAPABILITY_AVAILABILITY,
        "worldUnavailable": world is None,
    }

# ============================================================================
# END SLICE 9 — REASONING lane input + intent
# ============================================================================
