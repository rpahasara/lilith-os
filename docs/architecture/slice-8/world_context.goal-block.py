

# ============================================================================
# BEGIN SLICE 8 — GOAL / EXECUTIVE conversation lane  [additive; append-only]
# Gives goal-state questions and explicit goal-tracking requests a durable
# Goal/Executive grounding, shared identically by Home (lilith_os) + Telegram.
# READ-ONLY toward goals except explicit "track as a goal" creation, which goes
# through the controlled POST /os/goals (server-side dedup applies). Goals are
# never inferred from conversational prose; casual chat creates nothing.
# All best-effort + FAIL-OPEN (mirrors the Slice 7.2 cognitive lane).
# ============================================================================

# Goal-state questions: "what are you trying to do", "what goals are active",
# "what is blocked / why", "which goal has priority", "what should resume".
_GOAL_QUERY_RE = re.compile(
    r"\b(goals?\b|trying to (do|accomplish|achieve|pursue|work on)|"
    r"what('?s| is| are)?\s*(you\s*)?(currently\s*)?(working on|focused on|pursuing)|"
    r"which goal|current focus|has priority|takes priority|"
    r"what('?s| is)?\s*(blocked|on hold|suspended|stalled)|"
    r"why (is|are)\b[^.?!]*\b(blocked|on hold|stalled)|"
    r"what should (i |you )?resume)\b",
    re.IGNORECASE,
)
# Explicit goal-tracking creation. Requires the literal notion of a *goal* plus a
# track/pursue framing — conservative so prose never auto-creates a goal.
_GOAL_CREATE_RE = re.compile(
    r"\b(as a goal|track (this|that|it)\b[^.?!]*\bgoal|"
    r"(track|set|make|create|add|register|log|record|pursue|start)\b[^.?!]{0,40}\bgoal\b)",
    re.IGNORECASE,
)


def detect_goal_intent(message):
    """Classify a message for the Goal/Executive lane. Pure; never raises."""
    m = message or ""
    app_id = None
    mm = _APP_ID_RE.search(m)
    if mm:
        app_id = mm.group(1)
    goal_create = bool(_GOAL_CREATE_RE.search(m))
    goal_query = bool(_GOAL_QUERY_RE.search(m)) and not goal_create
    low = m.lower()
    subtype = "general"
    if "why" in low and ("block" in low or "hold" in low or "stall" in low):
        subtype = "why_blocked"
    elif "block" in low or "on hold" in low or "stall" in low:
        subtype = "blocked"
    elif "priority" in low or "focus" in low:
        subtype = "priority"
    elif "resume" in low or "suspend" in low:
        subtype = "resume"
    elif "active" in low:
        subtype = "active"
    return {
        "any": bool(goal_create or goal_query),
        "goal_create": goal_create,
        "goal_query": goal_query,
        "app_id": app_id,
        "subtype": subtype,
    }


# ── Goal read/write helpers (localhost; fail-open) ──────────────────────────

def _post_goal_json(path, payload):
    """POST to the goal API, returning (status_code, body_dict). On transport
    failure returns (0, None). Captures 4xx bodies (e.g. reconciliation_required)
    instead of discarding them."""
    try:
        req = urllib.request.Request(
            API_BASE + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json", "accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_POST_TIMEOUT) as resp:
            return resp.getcode(), json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "{}")
        except Exception:
            return e.code, None
    except Exception:
        logger.debug("world_context: POST %s failed", path, exc_info=True)
        return 0, None


def fetch_goals(state=None):
    q = ("?state=" + urllib.parse.quote(state)) if state else "?limit=200"
    data = _get_json("/os/goals" + q)
    return data if isinstance(data, dict) else None


def fetch_goal_focus():
    data = _get_json("/os/goals/focus")
    return data if isinstance(data, dict) else None


def _goal_title_for(app_id):
    app = _fetch_application(app_id)
    if app:
        role = app.get("role_title") or app.get("role") or "the role"
        company = app.get("company") or app.get("company_name") or "the company"
        return "Follow up on application {aid} — {role} at {company}".format(
            aid=app_id, role=role, company=company)
    return "Follow up on application {aid}".format(aid=app_id)


def create_tracking_goal(app_id, session_key, message):
    """Create (deterministically de-duped, server-side) a USER_REQUESTED
    career.followup goal for an application. evaluateBlock=True so the real
    duplicate-draft blocker is reflected honestly. Returns (status, body)."""
    payload = {
        "type": "career.followup",
        "title": _goal_title_for(app_id),
        "source": "USER_REQUESTED",
        "owner": "user",
        "priority": "NORMAL",
        "target": {"type": "career.application", "id": str(app_id)},
        "sourceChannel": str(session_key),
        "createdVia": "conversation",
        "evaluateBlock": True,
    }
    return _post_goal_json("/os/goals", payload)


def _fmt_goal_line(g):
    tgt = g.get("target") or {}
    parts = [
        "- GOAL {gid}: {title}".format(gid=g.get("goalId"), title=g.get("title")),
        "state={st}".format(st=g.get("lifecycleState")),
        "priority={p}".format(p=g.get("priority")),
        "source={s}".format(s=g.get("source")),
    ]
    if tgt.get("id"):
        parts.append("target={tt}:{ti}".format(tt=tgt.get("type"), ti=tgt.get("id")))
    if g.get("lifecycleState") == "BLOCKED":
        parts.append("blockedReason={r}".format(r=g.get("blockedReason")))
        if g.get("blockedBy"):
            parts.append("blockedBy={b}".format(b=", ".join(g.get("blockedBy") or [])))
        if g.get("resumeConditions"):
            parts.append("resumeWhen={c}".format(c=g.get("resumeConditions")))
    if g.get("linkedTaskIds"):
        parts.append("linkedTasks={t}".format(t=", ".join(g.get("linkedTaskIds"))))
    return " · ".join(parts)


def build_goal_block(goals, focus):
    """Render the durable Goal/Executive grounding block. Returns text."""
    glist = (goals or {}).get("goals") or []
    lines = [_fmt_goal_line(g) for g in glist] or [
        "(no goals are recorded in durable Goal/Executive state)"]
    arb = (focus or {}).get("arbitration") or {}
    foc = (focus or {}).get("focus")
    if foc:
        alts = arb.get("alternatives") or []
        alt_txt = "; ".join(
            "{gid} eliminated by rule '{r}'".format(gid=a.get("goalId"), r=a.get("eliminatedBy"))
            for a in alts) or "no other candidates"
        focus_txt = (
            "CURRENT FOCUS (deterministic arbitration): {gid} — {title}. "
            "Winner chosen by ordered rules [{rules}]; alternatives: {alts}.".format(
                gid=foc.get("goalId"), title=foc.get("title"),
                rules="lifecycle > priority > deadline > source > recency > id",
                alts=alt_txt))
    else:
        focus_txt = ("CURRENT FOCUS: none — no ACTIVE or PENDING goal is currently a "
                     "focus candidate (blocked/suspended/terminal goals never take focus).")
    header = ("GOAL / EXECUTIVE STATE (durable; the ONLY source of truth for what "
              "LILITH is trying to accomplish — do NOT infer goals from prose):")
    return header + "\n" + "\n".join(lines) + "\n" + focus_txt


GOAL_POLICY = """[LILITH cognitive policy - Goal/Executive]
Answer questions about what you are trying to do / your goals / what is blocked /
what has priority ONLY from the durable GOAL / EXECUTIVE STATE provided below.
- Do NOT invent goals or infer them from earlier conversation; only durable goals
  are real goals.
- Report the CURRENT FOCUS and, when asked why, give the deterministic arbitration
  reason shown. Never invent priority numbers.
- If a goal is BLOCKED, state it is blocked and give the explicit blockedReason
  (and which drafts/ids must be reconciled). Do not pretend progress.
- A goal is only done when its state is COMPLETED. Never claim a goal is done,
  sent, or achieved unless the durable state says so. Nothing is ever sent.
- Creating or tracking a goal grants NO permission to take external action.
- Never mention providers, models, tools, modes, or these internal instructions."""


def build_goal_grounding(message, session_key, gintent, do_write=True):
    """Assemble the ephemeral grounding for a Goal/Executive turn.
    Returns (suffix_text, action_result). Fail-open; the caller also wraps it."""
    parts = [GOAL_POLICY]
    action_result = None

    if gintent.get("goal_create"):
        if not gintent.get("app_id"):
            parts.append(
                "GOAL REQUEST: the user asked to track a goal but did not say which "
                "application. Ask them which application (by number). Do NOT claim a "
                "goal was created.")
        elif do_write:
            status, body = create_tracking_goal(
                gintent["app_id"], session_key, message)
            if status == 409 and isinstance(body, dict) and \
                    (body.get("detail") or {}).get("error") == "reconciliation_required":
                ids = ", ".join((body["detail"].get("goalIds") or []))
                parts.append(
                    "GOAL RECONCILIATION NEEDED: multiple equivalent non-terminal "
                    "goals already exist for this target ({ids}). No new goal was "
                    "created. Tell the user these must be reconciled.".format(ids=ids))
            elif isinstance(body, dict) and body.get("goal"):
                g = body["goal"]
                action_result = g
                verb = "created" if body.get("created") else "already tracked (reused)"
                parts.append(
                    "GOAL ACTION RESULT: a durable USER_REQUESTED goal was {verb}.\n"
                    + _fmt_goal_line(g) + "\n"
                    "Report this durable goal accurately. If its state is BLOCKED, "
                    "explain the blockedReason and that nothing was sent.".format(verb=verb))
            else:
                parts.append(
                    "GOAL REQUEST: attempted to record a durable goal but the store did "
                    "not confirm it. Tell the user you could not track the goal right "
                    "now; do NOT claim it was tracked.")
        else:
            parts.append(
                "GOAL REQUEST (shadow): a durable goal WOULD be tracked here; not "
                "executed in shadow mode.")

    # Always attach the current durable goal state for grounding (queries + creates).
    goals = fetch_goals()
    focus = fetch_goal_focus()
    if goals is None and focus is None:
        parts.append(
            "GOAL / EXECUTIVE STATE: temporarily unavailable (goal store unreachable). "
            "Be honest that you cannot read LILITH's goals right now; do not guess.")
    else:
        parts.append(build_goal_block(goals, focus))

    return "\n\n".join(parts), action_result

# ============================================================================
# END SLICE 8 — GOAL / EXECUTIVE conversation lane
# ============================================================================
