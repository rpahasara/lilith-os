# -*- coding: utf-8 -*-
"""LILITH Slice 7.2 — World-Model-first cognitive context for the SHARED
conversation runtime (Home ``lilith_os`` + Telegram, both via Router V2 /
``run_sync``).

This is the backend Context Builder. It gives free-chat turns the same
World-Model-first read semantics and durable-draft/pending-state action
semantics that the frontend Cognitive Core already has for structured commands —
so both transports share ONE authoritative cognitive path.

Design invariants
-----------------
* READ-ONLY toward the World Model (``GET /os/world`` only) — never mutates it.
* Durable drafts reuse the EXISTING Slice-4 path (``POST /os/drafts``) — no second
  draft store, idempotent, no external send.
* Pending state is read from durable ``/os/tasks`` + ``/os/drafts`` only — never
  inferred from conversational prose.
* No ``app.py`` / DB / World-Model schema change.
* Bounded top-k working set; entity-focused where an application id is present.
* Everything is best-effort and FAIL-OPEN: on any error the caller gets no
  grounding and the native gpt-5.6-sol path is used unchanged.

Only stdlib is imported so this module (and its unit tests) run offline with no
Hermes dependency.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

# The local FastAPI service (lilith-os-api) on this VM. Same origin the frontend
# proxy reaches over the IAP tunnel; here it is a plain localhost call.
API_BASE = "http://127.0.0.1:8765"
_GET_TIMEOUT = 2.5
_POST_TIMEOUT = 4.0

# Bounded working-memory capacity — mirrors the frontend
# DEFAULT_WORKING_CAPACITY so Home structured + free-chat stay consistent.
TOPK = 12

# ── Intent detection (pure, deterministic, offline) ─────────────────────────

# A request for a *specimen* — prose only, never a durable object.
_EXAMPLE_RE = re.compile(
    r"\b(example|sample|mock|template|hypothetical|for reference|"
    r"what would .*(look like|say)|draft up an example)\b",
    re.IGNORECASE,
)
# Imperative that asks LILITH to persist/prepare something.
_DRAFT_VERB_RE = re.compile(
    r"\b(create|save|prepare|queue|draft|compose|write|make|set up|put together)\b",
    re.IGNORECASE,
)
# The object of a durable follow-up draft (deliberately EXCLUDES "note" —
# note bodies are free text and out of scope for auto-create this phase).
_DRAFT_OBJ_RE = re.compile(
    r"\b(follow[- ]?up|draft|reply|response|message)\b", re.IGNORECASE
)
# Belief / knowledge-state questions.
_BELIEF_RE = re.compile(
    r"\b(believe|belief|what do you (currently )?(know|think|believe)|know about|"
    r"where did .*(come from|information)|provenance|source of|confirmed|"
    r"observ(ed|ation)|uncertain|unknown|conflict|stale|distinguish)\b",
    re.IGNORECASE,
)
# Pending durable-state questions.
_PENDING_RE = re.compile(
    r"\b(pending|awaiting approval|outstanding|what('?s| is| are)?\s*"
    r"(tasks?|approvals?|drafts?)\b.*\b(pending|open|waiting|outstanding)?|"
    r"(tasks?|approvals?|drafts?)\s+(are\s+)?(pending|open|waiting|outstanding)|"
    r"do i have (any )?(pending|open))\b",
    re.IGNORECASE,
)
# Career framing that, with a question mark, is treated as a belief-read.
_CAREER_HINT_RE = re.compile(
    r"\b(application|applications|job|jobs|recruiter|role|position|"
    r"follow[- ]?up|career)\b",
    re.IGNORECASE,
)
_APP_ID_RE = re.compile(
    r"\b(?:application|app|job|role|position|#)\s*#?\s*(\d{1,6})\b", re.IGNORECASE
)


def detect_intent(message):
    """Classify a message into the cognitive lanes. Pure; never raises."""
    m = message or ""
    example_only = bool(_EXAMPLE_RE.search(m))
    app_id = None
    mm = _APP_ID_RE.search(m)
    if mm:
        app_id = mm.group(1)
    draft = (
        bool(_DRAFT_VERB_RE.search(m))
        and bool(_DRAFT_OBJ_RE.search(m))
        and not example_only
    )
    pending = bool(_PENDING_RE.search(m))
    belief = bool(_BELIEF_RE.search(m)) or (
        bool(_CAREER_HINT_RE.search(m)) and "?" in m
    )
    # A durable action or a pending query is not itself a belief-read.
    if draft or pending:
        belief = belief and not (draft or pending)
    any_ = bool(draft or pending or belief)
    return {
        "any": any_,
        "draft": draft,
        "pending": pending,
        "belief": belief,
        "example_only": example_only,
        "app_id": app_id,
    }


# ── HTTP helpers (localhost; fail-open) ─────────────────────────────────────

def _get_json(path, timeout=_GET_TIMEOUT):
    try:
        req = urllib.request.Request(
            API_BASE + path, headers={"accept": "application/json"}, method="GET"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "null")
    except Exception:
        logger.debug("world_context: GET %s failed", path, exc_info=True)
        return None


def _post_draft(payload):
    try:
        req = urllib.request.Request(
            API_BASE + "/os/drafts",
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json", "accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_POST_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except Exception:
        logger.debug("world_context: POST /os/drafts failed", exc_info=True)
        return None


# ── World Model reads ───────────────────────────────────────────────────────

def fetch_world(entity_type=None, entity_id=None):
    q = []
    if entity_type:
        q.append("entity_type=" + urllib.parse.quote(str(entity_type)))
    if entity_id:
        q.append("entity_id=" + urllib.parse.quote(str(entity_id)))
    path = "/os/world" + (("?" + "&".join(q)) if q else "")
    data = _get_json(path)
    return data if isinstance(data, dict) else None


def _summarize_value(v):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    s = str(s)
    return s if len(s) <= 120 else (s[:117] + "...")


def _provenance_summary(prov):
    seen = []
    for p in prov or []:
        sc = p.get("source_class") or p.get("sourceClass") or "?"
        sid = p.get("source_id") or p.get("sourceId") or ""
        fresh = p.get("freshness") or ""
        tag = sc + (":" + sid if sid else "") + (" (" + fresh + ")" if fresh else "")
        if tag not in seen:
            seen.append(tag)
    return ", ".join(seen[:4]) if seen else "none recorded"


def build_belief_block(world, focus_entity_id=None, topk=TOPK):
    """Render a bounded, provenance-preserving belief block. Returns (text, total)."""
    beliefs = list((world or {}).get("beliefs") or [])
    if focus_entity_id:
        focused = [b for b in beliefs if str(b.get("entity_id")) == str(focus_entity_id)]
        beliefs = focused or beliefs
    total = len(beliefs)
    beliefs = beliefs[: max(0, int(topk))]
    lines = []
    for b in beliefs:
        conf = b.get("confidence") or {}
        lines.append(
            "- {et}:{eid} · {pred} = {val} "
            "[lifecycle={life}, epistemic={epi}, "
            "confidence={cv} ({tier}; {basis}), sources={src}]".format(
                et=b.get("entity_type"),
                eid=b.get("entity_id"),
                pred=b.get("predicate"),
                val=_summarize_value(b.get("value")),
                life=b.get("lifecycle_state"),
                epi=b.get("epistemic_state"),
                cv=conf.get("value"),
                tier=conf.get("tier"),
                basis=conf.get("basis"),
                src=_provenance_summary(b.get("provenance")),
            )
        )
    meta = (world or {}).get("meta") or {}
    header = (
        "WORLD MODEL BELIEFS (durable, reconciled; showing {shown} of {total}; "
        "conflicted={c}, stale={s}, last_reconciled={lr}):".format(
            shown=len(beliefs),
            total=total,
            c=meta.get("conflicted", 0),
            s=meta.get("stale", 0),
            lr=meta.get("last_reconciled_at"),
        )
    )
    body = "\n".join(lines) if lines else "(no beliefs are recorded for this focus)"
    return header + "\n" + body, total


# ── Durable pending state ───────────────────────────────────────────────────

_PENDING_TASK_STATUSES = {
    "waiting_for_approval", "created", "planning", "running", "verifying",
}


def build_pending_block():
    tasks = _get_json("/os/tasks?limit=200") or {}
    drafts = _get_json("/os/drafts?limit=200") or {}
    tlist = tasks.get("tasks") if isinstance(tasks, dict) else None
    dlist = drafts.get("drafts") if isinstance(drafts, dict) else None
    tlist = tlist or []
    dlist = dlist or []
    pending_tasks = [
        t for t in tlist
        if t.get("status") in _PENDING_TASK_STATUSES
        or t.get("approvalState") in ("required", "expired")
    ]
    open_drafts = [d for d in dlist if d.get("status") == "created"]
    lines = []
    for t in pending_tasks[:20]:
        lines.append(
            "- TASK {tid}: {title} — status={st}, approval={ap}".format(
                tid=t.get("taskId"), title=t.get("title"),
                st=t.get("status"), ap=t.get("approvalState"),
            )
        )
    for d in open_drafts[:20]:
        tg = d.get("target") or {}
        lines.append(
            "- DRAFT {did}: {kind} for application {aid} — status={st} (UNSENT), subject={sub}".format(
                did=d.get("draftId"), kind=d.get("kind"), aid=tg.get("id"),
                st=d.get("status"), sub=_summarize_value(d.get("subject") or ""),
            )
        )
    header = (
        "DURABLE PENDING STATE (read from /os/tasks and /os/drafts — the ONLY "
        "source of truth for pending items; do not infer any others):"
    )
    body = "\n".join(lines) if lines else (
        "(no pending tasks, approvals, or unsent drafts exist in durable state)"
    )
    return header + "\n" + body


# ── Durable follow-up draft (reuses Slice-4 /os/drafts) ─────────────────────

def _fetch_application(app_id):
    data = _get_json("/career/applications")
    apps = data.get("applications") if isinstance(data, dict) else data
    if not isinstance(apps, list):
        return None
    for a in apps:
        if str(a.get("id")) == str(app_id):
            return a
    return None


def compose_followup(app):
    app = app or {}
    role = app.get("role_title") or app.get("role") or "the role"
    company = app.get("company") or app.get("company_name") or "the company"
    subject = "Following up on my application - {role}".format(role=role)
    body = (
        "Hello,\n\n"
        "I wanted to follow up on my application for the {role} role at {company}. "
        "I remain very interested in the opportunity and would welcome any update "
        "on the next steps.\n\n"
        "Thank you for your time and consideration.\n\n"
        "Best regards".format(role=role, company=company)
    )
    return subject, body


def _draft_is_unresolved(d):
    """A draft is 'unresolved' (unsent / active) while its Slice-4 status is
    'created'. 'discarded' is the resolved/soft-deleted terminal state."""
    return (d or {}).get("status") == "created"


def find_unresolved_followups(app_id):
    """Slice 7.3 deterministic de-dup lookup: existing UNSENT career_followup
    drafts for this application in the durable store. Exact-match only — no LLM,
    no fuzzy matching. Returns a list (possibly empty), or None on a lookup error
    (the caller then proceeds to create, i.e. behaviour is no worse than before
    de-dup)."""
    data = _get_json("/os/drafts?target_id=" + urllib.parse.quote(str(app_id)))
    if not isinstance(data, dict):
        return None
    out = []
    for d in data.get("drafts") or []:
        tgt = d.get("target") or {}
        if (
            str(tgt.get("id")) == str(app_id)
            and (tgt.get("type") or "application") == "application"
            and d.get("kind") == "career_followup"
            and _draft_is_unresolved(d)
        ):
            out.append(d)
    return out


def create_followup_draft(app_id, session_key, message):
    """Create (idempotently) a durable, UNSENT internal follow-up draft via the
    existing Slice-4 endpoint. Returns the ``{draft, created}`` dict or None."""
    app = _fetch_application(app_id)
    subject, body = compose_followup(app)
    h = hashlib.sha256(
        (str(session_key) + "|" + str(app_id) + "|" + (message or "")).encode("utf-8")
    ).hexdigest()[:16]
    payload = {
        "draftId": "d.os2.{aid}.{h}".format(aid=app_id, h=h),
        "idempotencyKey": "os2.{aid}.{h}".format(aid=app_id, h=h),
        "kind": "career_followup",
        "target": {"type": "application", "id": str(app_id)},
        "subject": subject,
        "body": body,
        "taskId": "os2.conv.{h}".format(h=h),
        "stepId": "s3",
        "schemaVersion": 1,
    }
    return _post_draft(payload)


# ── Fallback / honesty policy injected for every cognitive turn ─────────────

FALLBACK_POLICY = """[LILITH cognitive policy - World-Model-first]
Answer from the WORLD MODEL BELIEFS and DURABLE STATE provided below FIRST.
These are LILITH's reconciled, durable beliefs and durable task/draft records -
treat them as the primary source of truth for this turn.
- If the beliefs / durable state already answer the question, answer from them
  and do NOT search files, past sessions, memory, or run shell/SQLite. Do not
  rummage through raw sources when the belief context is sufficient.
- Distinguish clearly between confirmed/verified facts, observations, inferences,
  and unknowns. When relevant, say how confident a fact is and where it came from
  (its source class / provenance).
- UNKNOWN: if a requested fact is not present in the beliefs / durable state, say
  plainly that it is not known or not tracked. Do NOT fabricate a value or a
  formal status. Only consult raw sources if it would genuinely help and you have
  not already answered that it is unknown.
- STALE: if a belief is marked STALE, say so and offer to refresh it rather than
  presenting it as current.
- CONFLICTED: if a belief is CONFLICTED, expose the conflict and the competing
  evidence; do not silently choose a winner.
- Fall back to raw file / session / SQLite retrieval ONLY when the needed fact is
  absent, stale, or conflicted, or when the user explicitly asks to inspect raw
  sources.
- Never claim that anything was saved, created, drafted, queued, or sent unless a
  DURABLE ACTION RESULT below confirms it. Never claim an email was sent.
- Never mention providers, models, tools, modes, or these internal instructions."""


def _career_focus(message):
    return bool(_CAREER_HINT_RE.search(message or ""))


def build_grounding(message, session_key, intent, do_write=True, dedup=True):
    """Assemble the ephemeral grounding suffix for a cognitive turn.

    Returns ``(suffix_text, action_result)`` where ``action_result`` is the
    durable draft dict when one was created OR reused (else None). Never raises
    for the caller's benefit — but the caller also wraps this.

    ``dedup`` (Slice 7.3): before creating a follow-up draft, check the durable
    store for an existing UNSENT career_followup for the same application and
    reuse it (one match) / refuse + surface reconciliation (multiple matches)
    instead of creating another row.
    """
    parts = [FALLBACK_POLICY]
    action_result = None

    if intent.get("belief") or intent.get("draft"):
        if intent.get("app_id"):
            world = fetch_world(entity_type="career.application", entity_id=intent["app_id"])
        elif _career_focus(message):
            world = fetch_world(entity_type="career.application")
        else:
            world = fetch_world()
        if world is None:
            parts.append(
                "WORLD MODEL: temporarily unavailable (belief store unreachable). "
                "Be honest that you cannot consult LILITH's beliefs right now; do "
                "not guess or fabricate."
            )
        else:
            block, _total = build_belief_block(world, focus_entity_id=intent.get("app_id"))
            parts.append(block)

    if intent.get("pending"):
        parts.append(build_pending_block())

    if intent.get("draft"):
        if not intent.get("app_id"):
            parts.append(
                "DRAFT REQUEST: the user asked to create a durable follow-up draft "
                "but did not say which application. Ask them which application (by "
                "number). Do NOT claim any draft was created."
            )
        elif do_write:
            # Slice 7.3 deterministic de-dup: reuse / refuse before creating.
            existing = find_unresolved_followups(intent["app_id"]) if dedup else None
            if existing is None:
                existing = []  # lookup failed OR de-dup disabled -> create (fail-open)
            if dedup and len(existing) == 1:
                d = existing[0]
                action_result = d
                parts.append(
                    "DURABLE ACTION RESULT (existing draft reused): an UNSENT follow-up "
                    "draft already exists for application {aid}, so it was reused and NO "
                    "new draft was created.\n"
                    "draft_id={did}, status={st} (UNSENT). Report this EXISTING draft id; "
                    "do not claim a new one was made. It was NOT sent anywhere. You may "
                    "show the subject/body.\nSUBJECT: {sub}\nBODY:\n{body}".format(
                        aid=intent["app_id"],
                        did=d.get("draftId"),
                        st=d.get("status"),
                        sub=d.get("subject"),
                        body=d.get("body"),
                    )
                )
            elif dedup and len(existing) > 1:
                ids = ", ".join(str(d.get("draftId")) for d in existing[:10])
                parts.append(
                    "DUPLICATE DRAFTS EXIST: {n} unsent follow-up drafts already exist for "
                    "application {aid} (ids: {ids}). A new draft was NOT created. Tell the "
                    "user that duplicate drafts already exist, list these ids, and say they "
                    "must be reconciled (kept/discarded) before any send. Nothing was "
                    "sent.".format(n=len(existing), aid=intent["app_id"], ids=ids)
                )
            else:
                res = create_followup_draft(intent["app_id"], session_key, message)
                draft = (res or {}).get("draft")
                if draft:
                    action_result = draft
                    parts.append(
                        "DURABLE ACTION RESULT: a real internal follow-up draft has been "
                        "saved to LILITH's durable draft store (/os/drafts).\n"
                        "draft_id={did}, target=application {aid}, status={st} (UNSENT), "
                        "created={created}. It was NOT emailed or sent anywhere and is "
                        "reversible (it can be discarded). Report this accurately; you may "
                        "show the subject/body. Do not claim it was sent.\n"
                        "SUBJECT: {sub}\nBODY:\n{body}".format(
                            did=draft.get("draftId"),
                            aid=(draft.get("target") or {}).get("id"),
                            st=draft.get("status"),
                            created=(res or {}).get("created"),
                            sub=draft.get("subject"),
                            body=draft.get("body"),
                        )
                    )
                else:
                    parts.append(
                        "DRAFT REQUEST: attempted to save a durable draft but the store "
                        "did not confirm it. Tell the user you could not save the draft "
                        "right now; do NOT claim it was saved."
                    )
        else:
            parts.append(
                "DRAFT REQUEST (shadow): a durable draft WOULD be created here; not "
                "executed in shadow mode."
            )

    return "\n\n".join(parts), action_result


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


# ============================================================================
# BEGIN SLICE 13 — ETHICS lane input + intent  [additive; append-only]
# Detects EXPLICIT ethical/normative questions only ("is this okay?", "would it
# be okay to ...", "is that fair/appropriate?", "any concerns?", "should we ...?"
# + a privacy/third-party/bypass/constraint cue) and builds a BOUNDED
# EthicalInput for exactly ONE USER_INTENT subject, with an ephemeral TurnEvidence
# whose refs are the ONLY things a concern may cite (sourceOwner=TURN) alongside
# real durable owners. Conservative precedence: YIELDS (any=False) to explicit
# action (7.2 draft / 8 goal_create), goal-state queries, pending, AND planning —
# so those accepted paths stay authoritative. READ-ONLY; advisory only; NO writes.
# ============================================================================


def _ethics_mod():
    try:
        from . import ethics as _e
    except Exception:
        import ethics as _e
    return _e


# ── intent detection ─────────────────────────────────────────────────────────

_E13_MARKER_RE = re.compile(
    r"\b("
    r"(is|are|was|were|would|isn'?t) (this|that|it|these|those) (be )?(really |actually )?"
    r"(ok|okay|alright|ethical|fair|appropriate|right|wrong|acceptable|a good idea|a problem)\b|"
    r"would it be (ok|okay|alright|fine|appropriate|acceptable) to\b|"
    r"is it (ok|okay|ethical|fair|appropriate|right|acceptable|alright) to\b|"
    r"(any|what) (are the )?(ethical )?(concerns?|risks?|implications?|issues?)\b|"
    r"is (this|that|it) (even )?(ethical|fair|appropriate|right|ok|okay)\b|"
    r"could (this|that|it) (affect|harm|hurt|upset|impact) (someone|anyone|them|him|her|people)\b|"
    r"should (i|we) (be )?(worried|concerned) about\b"
    r")",
    re.IGNORECASE,
)
_E13_SOFT_RE = re.compile(r"\bshould (we|i|you)\b", re.IGNORECASE)
_E13_CUE_RE = re.compile(
    r"\b(private|personal|confidential|sensitive|salary|my notes|application notes|"
    r"without asking|without (my |your )?(ok|okay|approval|permission|consent|confirmation)|"
    r"the recruiter|my manager|the hiring manager|the customer|the client|my boss|"
    r"do ?n'?t (contact|share|send|tell|reveal)|do not (contact|share|send|tell|reveal))\b",
    re.IGNORECASE,
)


def _ethics_none():
    return {"any": False, "mode": None, "app_id": None, "trigger": None}


def detect_ethics_intent(message):
    """Classify a message for the Ethics lane. Pure; never raises. Explicit
    ethical/normative framings only; yields to action / goal / pending / planning."""
    m = message or ""
    marker = bool(_E13_MARKER_RE.search(m))
    soft = bool(_E13_SOFT_RE.search(m))
    if not (marker or soft):
        return _ethics_none()
    try:
        ci = detect_intent(m)              # Slice 7.2: belief / pending / draft
        gi = detect_goal_intent(m)         # Slice 8: goal_create / goal_query
        pintent = detect_planning_intent(m)  # Slice 12: explicit plan verbs
    except Exception:
        return _ethics_none()
    if pintent.get("any"):
        return _ethics_none()              # planning owns
    if gi.get("goal_create") or gi.get("goal_query"):
        return _ethics_none()              # goal track / goal-state -> Slice 8
    if ci.get("pending"):
        return _ethics_none()              # pending -> Slice 7.2

    app_id = ci.get("app_id")
    if marker:
        # an explicit ethical question owns even over a draft-shaped phrasing —
        # a question about okayness is not an action command.
        return {"any": True, "mode": "ETHICS", "app_id": app_id, "trigger": "marker"}
    # soft "should we ..." only owns with a genuine ethical cue present
    if soft and _E13_CUE_RE.search(m):
        return {"any": True, "mode": "ETHICS", "app_id": app_id, "trigger": "soft"}
    return _ethics_none()


# ── TurnEvidence extraction (ephemeral; sourceOwner=TURN) ────────────────────

_E13_CONSTRAINT_PATTERNS = [
    (re.compile(r"do ?n'?t (contact|email|message|reach out to)|do not (contact|email|message|reach out to)", re.I),
     "NO_CONTACT"),
    (re.compile(r"do ?n'?t (send|share|disclose|reveal|tell)|do not (send|share|disclose|reveal|tell)|without sharing", re.I),
     "NO_SHARE_OR_SEND"),
    (re.compile(r"always ask me( first)?|ask me (first|before)|check with me first", re.I),
     "REQUIRE_CONFIRMATION"),
]
_E13_DELETE_RE = re.compile(r"\b(permanently )?(delete|erase|wipe|destroy)\b|\bremove\b[\w ]{0,20}\bpermanently\b", re.I)
_E13_SEND_RE = re.compile(
    r"\bsend (an?|the )?(e-?mail|message|text|mail)\b|"
    r"\be-?mail(ing)?\s+(the\s+\w+|to\b|him\b|her\b|them\b|[\w.]+@)", re.I)
_E13_DISCLOSE_VERB_RE = re.compile(r"\b(include|add|attach|put|share|disclose|reveal)\b", re.I)
_E13_DISCLOSE_DEST_RE = re.compile(r"\b(in|into|to) (the|an?|my|your) (e-?mail|message|report|document|note|reply)\b", re.I)
_E13_INTERNAL_RE = re.compile(r"\b(follow[- ]?up|draft)\b", re.I)
_E13_NOTE_RE = re.compile(r"\bnote\b", re.I)
_E13_CONTACT_RE = re.compile(r"\b(contact|reach out to|notify|tell)\b", re.I)
_E13_BYPASS_RE = re.compile(
    r"\bwithout (asking|checking with|clearing (it )?with|confirming with) (me|you|us)( first)?\b|"
    r"\bwithout (my |your )?(ok|okay|approval|permission|consent|confirmation|sign[- ]?off)\b|"
    r"\bbefore (asking|checking with) (me|you)\b", re.I)
_E13_DATA_PATTERNS = [
    re.compile(r"\bmy salary\b", re.I),
    re.compile(r"\bmy (private|personal|confidential|sensitive) [\w ]{0,25}?(notes|data|information|details|number|address|records|messages)\b", re.I),
    re.compile(r"\b(private|personal|confidential|sensitive) (application )?(notes|data|information|details)\b", re.I),
    re.compile(r"\ball (of )?(my |the )?[\w ]{0,20}?(notes|details|data|records|messages)\b", re.I),
    re.compile(r"\bapplication notes\b", re.I),
]
_E13_THIRD_PARTY_RE = re.compile(
    r"\b(the recruiter|my manager|the hiring manager|the customer|the client|my boss|the interviewer|their manager)\b", re.I)
_E13_MULTI_RE = re.compile(
    r"\b(everyone|all (of )?(the )?(recruiters|contacts|people|applicants)|the (whole|entire) team|(\d{2,})\s+(people|recruiters|contacts|applicants))\b", re.I)


def _e13_action(m):
    """Deterministic referenced-action classification (first match wins)."""
    if _E13_DELETE_RE.search(m):
        return {"ref": None, "verb": "delete", "capabilityRef": None,
                "impactClass": "IRREVERSIBLE_DELETION", "bypassConfirmation": False}
    if _E13_SEND_RE.search(m):
        return {"ref": None, "verb": "send_external", "capabilityRef": "mail.send_email",
                "impactClass": "EXTERNAL_DISCLOSURE", "bypassConfirmation": False}
    if _E13_DISCLOSE_VERB_RE.search(m) and (_E13_DISCLOSE_DEST_RE.search(m)
                                            or any(p.search(m) for p in _E13_DATA_PATTERNS)):
        return {"ref": None, "verb": "disclose", "capabilityRef": None,
                "impactClass": "DATA_DISCLOSURE", "bypassConfirmation": False}
    if _E13_INTERNAL_RE.search(m):
        return {"ref": None, "verb": "internal_write", "capabilityRef": "career.create_followup_draft",
                "impactClass": "REVERSIBLE_INTERNAL", "bypassConfirmation": False}
    if _E13_NOTE_RE.search(m):
        return {"ref": None, "verb": "internal_write", "capabilityRef": "career.add_note",
                "impactClass": "REVERSIBLE_INTERNAL", "bypassConfirmation": False}
    if _E13_CONTACT_RE.search(m):
        return {"ref": None, "verb": "contact", "capabilityRef": None,
                "impactClass": None, "bypassConfirmation": False}
    return None


def build_turn_evidence(message, corr):
    """Ephemeral current-turn evidence with deterministic correlation-bound refs.
    NOT durable memory. Identity of any third party is NEVER fabricated."""
    m = message or ""
    base = "turn:%s" % corr
    ev = {
        "turnRef": base,
        "correlationId": corr,
        "normalizedIntent": " ".join(m.split())[:400],
        "explicitConstraints": [],
        "referencedTargets": [],
        "referencedAction": None,
        "referencedDataScope": [],
        "referencedThirdPartyRoles": [],
        "subjectScope": {},
        "actionScope": {},
    }
    # constraints
    for i, (rx, kind) in enumerate(_E13_CONSTRAINT_PATTERNS):
        mm = rx.search(m)
        if mm:
            ev["explicitConstraints"].append(
                {"ref": "%s:constraint:%d" % (base, len(ev["explicitConstraints"])),
                 "text": mm.group(0), "kind": kind})
    # targets
    for mm in _APP_ID_RE.finditer(m):
        ev["referencedTargets"].append(
            {"ref": "%s:target:%d" % (base, len(ev["referencedTargets"])),
             "targetRef": "application:%s" % mm.group(1), "appId": mm.group(1)})
    # action
    a = _e13_action(m)
    if a:
        a["ref"] = "%s:action" % base
        a["bypassConfirmation"] = bool(_E13_BYPASS_RE.search(m))
        if ev["referencedTargets"]:
            a["target"] = ev["referencedTargets"][0]["targetRef"]
        ev["referencedAction"] = a
    # data scope
    seen = set()
    for rx in _E13_DATA_PATTERNS:
        for mm in rx.finditer(m):
            txt = mm.group(0).strip()
            key = txt.lower()
            if key in seen:
                continue
            seen.add(key)
            ev["referencedDataScope"].append(
                {"ref": "%s:data-scope:%d" % (base, len(ev["referencedDataScope"])),
                 "assertion": txt, "userAsserted": True,
                 "overBroad": bool(re.match(r"\ball\b", txt, re.I))})
    # third-party roles (identity never resolved / never fabricated)
    for mm in _E13_THIRD_PARTY_RE.finditer(m):
        role = re.sub(r"^(the|my|their)\s+", "", mm.group(0), flags=re.I)
        ev["referencedThirdPartyRoles"].append(
            {"ref": "%s:third-party:%d" % (base, len(ev["referencedThirdPartyRoles"])),
             "role": role, "identityResolved": False})
    # scopes (proportionality only)
    if ev["referencedTargets"]:
        ev["subjectScope"] = {"ref": ev["referencedTargets"][0]["ref"],
                              "kind": "application", "targetCount": 1}
    mm = _E13_MULTI_RE.search(m)
    if mm:
        n = None
        for g in mm.groups():
            if g and g.isdigit():
                n = int(g)
        ev["actionScope"] = {"ref": "%s:action-scope" % base, "kind": "recipients",
                             "targetCount": n or 10}
    return ev


# ── subject + bounded input ─────────────────────────────────────────────────

def build_ethical_subject(message, eintent, corr, turn_evidence):
    """Resolve EXACTLY ONE EthicalSubject. Live V1: USER_INTENT only; ref is the
    turnRef (NEVER raw user text — that lives in TurnEvidence.normalizedIntent)."""
    a = (turn_evidence or {}).get("referencedAction") or {}
    return {
        "kind": "USER_INTENT",
        "ref": "turn:%s" % corr,
        "targetAppId": eintent.get("app_id"),
        "referencedCapabilityRef": a.get("capabilityRef"),
    }


def build_ethical_input(message, session_key, eintent, snapshot, channel=None):
    """Assemble a BOUNDED EthicalInput for ONE subject. Reuses the Slice-10/11
    Workspace-bounded cognitive context (mot_snapshot=None — Motivation must not
    influence ethical correctness), attaches the single USER_INTENT subject, the
    ephemeral TurnEvidence, and the NON-AUTHORITATIVE static capability view.
    NO motivationSummary, NO reasoningResult (corrections 16/17). Fail-open."""
    import hashlib as _hl
    import time as _t
    corr = "e." + _hl.sha256(
        (str(session_key) + "|" + (message or "") + "|" + str(_t.time())).encode("utf-8")
    ).hexdigest()[:16]

    rintent = {"any": True, "mode": "ETHICS",
               "app_id": eintent.get("app_id"), "subtype": eintent.get("trigger")}
    try:
        base = select_reasoning_input_m(
            message, session_key, rintent, snapshot, None, channel=channel) or {}
    except Exception:
        logger.debug("world_context: ethics base ri failed (fail-open)", exc_info=True)
        base = {}

    te = build_turn_evidence(message, corr)
    subject = build_ethical_subject(message, eintent, corr, te)
    caps = _plan_caps_mod()

    return {
        "schemaVersion": 1,
        "correlationId": corr,
        "timestamp": _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime()),
        "channel": channel,
        "mode": "ETHICS",
        "userIntent": message,
        "ethicalSubject": subject,
        "turnEvidence": te,
        "explicitUserConstraints": [c.get("text") for c in te.get("explicitConstraints") or []],
        "relevantBeliefs": (base.get("relevantBeliefs") or [])[:8],
        "relevantTasks": (base.get("relevantTasks") or [])[:8],
        "relevantDrafts": (base.get("relevantDrafts") or [])[:8],
        "workspaceFocus": base.get("workspaceFocus"),
        "capabilityView": caps.view_summary(),
        "worldUnavailable": bool(base.get("worldUnavailable")),
        # NOTE: motivationSummary and reasoningResult are intentionally absent.
    }


def ethics_trace(result):
    try:
        return (result or {}).get("traceMetadata") or {}
    except Exception:
        return {"fallback_reason": "trace_error"}

# ============================================================================
# END SLICE 13 — ETHICS lane input + intent
# ============================================================================
