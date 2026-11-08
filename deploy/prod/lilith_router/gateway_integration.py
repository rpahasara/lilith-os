"""Bridge between the Hermes gateway turn-builder and the LILITH router.

The gateway core calls exactly one function — :func:`route_turn` — from a small
guarded block in ``gateway/run.py``. This function decides whether the current
turn should be served by the Groq social brain and, if so, returns the
overrides the core applies for that single turn. It NEVER raises into the core
(all paths are wrapped) and returns ``None`` to mean "do nothing, use the native
gpt-5.6-sol path".

Contract with the core patch
----------------------------
``route_turn(...) -> Optional[dict]`` where the dict may contain:
    turn_route          -- replacement for the local ``turn_route``
    combined_ephemeral  -- replacement ephemeral system prompt (SOUL still loads)
    force_rebuild       -- when True the core sets ``agent = None`` to rebuild
    mode                -- decided mode (for logging only)

Safety model
------------
* Master flag OFF (default) or shadow mode  -> always returns None.
* Only ``social`` turns on an allow-listed live channel produce an override.
* Groq creds missing / any exception         -> returns None (fail open).
* Fallback to gpt-5.6-sol on a Groq runtime failure is handled natively by the
  agent's ``fallback_model`` chain, carrying this turn's social ephemeral prompt.

Slice 7.2 — cognitive lane
--------------------------
An additive, independently-flagged lane (``cognitive_*`` in router.yaml) gives
belief / pending / durable-draft turns a World-Model-first grounding on the
WORK brain (native gpt-5.6-sol), shared identically by Home (``lilith_os``) and
Telegram. It runs BEFORE the social/technical/work decision, governs ONLY those
turns, and — like everything here — is fully fail-open. See ``world_context``.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import re
import time
import uuid

from . import config as _config
from . import policy as _policy
from . import social_guard as _social_guard
from . import social_lean as _social_lean
from . import canonical_memory as _canonical_memory
from . import owner_link as _owner_link
from . import social_preferences as _social_prefs
from . import turn_context as _tc
from . import world_context as _world_context
from .classifier import SOCIAL, WORK, classify
from .state import STATE

logger = logging.getLogger(__name__)


def _platform_name(source) -> str:
    plat = getattr(source, "platform", None)
    return getattr(plat, "value", None) or str(plat)


def _message_meta(message) -> dict:
    """Non-content audit metadata for a decision record (F9-A D-2).

    No message text and no hash of it: a random per-record event id plus the
    message length in characters and lines.
    """
    text = message or ""
    return {"event_id": uuid.uuid4().hex, "msg_chars": len(text), "msg_lines": len(text.splitlines())}


# P-1 T-1 (2026-11-08): one id per turn on every decision-log record, so the lanes of a turn can be joined.
# Metadata only (never message text or model reasoning). `turn_trace_enabled: false` in router.yaml stops the stamp.
_turn_id = contextvars.ContextVar("lilith_turn_id", default=None)
_turn_started = contextvars.ContextVar("lilith_turn_started", default=None)


def _begin_turn(cfg) -> None:
    enabled = getattr(cfg, "turn_trace_enabled", True) is not False
    _turn_id.set(uuid.uuid4().hex[:16] if enabled else None)
    _turn_started.set(time.monotonic() if enabled else None)


def current_turn_id():
    return _turn_id.get()


_turn_mode = contextvars.ContextVar("lilith_turn_mode", default=None)
_turn_route = contextvars.ContextVar("lilith_turn_route", default=None)
_agent_tokens_seen: dict = {}          # session key -> (prompt, completion) cumulative totals at the last turn end


def log_turn_end(ctx, *, agent=None, result=None, guard_changed=False, d1_recorded=False,
                 reply_chars=0) -> None:
    """P-1 T-2: one `lane: "turn"` record per turn: how it was routed and answered. Numbers, labels and model names
    only; never message text or reasoning. Called once from run.py after the social guard. Never raises."""
    try:
        tid = _turn_id.get()
        if not tid:
            return
        cfg = _config.load()
        source = getattr(ctx, "source", None)
        platform = _platform_name(source) if source is not None else None
        session_key = getattr(ctx, "session_key", None) or ""
        result = result if isinstance(result, dict) else {}
        api_calls = int(result.get("api_calls", 0) or 0)
        lean = _social_lean.LAST_USAGE.get()
        rec = {"lane": "turn", "platform": platform, "channel": _canonical_memory.current_channel(),
               "owner": _canonical_memory.owner_turn(), "mode": _turn_mode.get(), "route": _turn_route.get(),
               "api_calls": api_calls, "guard_changed": bool(guard_changed), "d1_recorded": bool(d1_recorded),
               "reply_chars": int(reply_chars or 0)}
        if api_calls > 0 and agent is not None:
            p_tot = int(getattr(agent, "session_prompt_tokens", 0) or 0)
            c_tot = int(getattr(agent, "session_completion_tokens", 0) or 0)
            p0, c0 = _agent_tokens_seen.get(session_key, (0, 0))
            _agent_tokens_seen[session_key] = (p_tot, c_tot)
            rec.update({"answered_by": "agent", "provider": getattr(agent, "provider", None),
                        "model": getattr(agent, "model", None),
                        "fallback_activated": bool(getattr(agent, "_fallback_activated", False)),
                        "tokens_in": p_tot - p0 if p_tot >= p0 else p_tot,
                        "tokens_out": c_tot - c0 if c_tot >= c0 else c_tot})
        elif lean:
            rec.update({"answered_by": "lean", **lean})
        else:
            rec["answered_by"] = "router"               # a ready answer (reasoning / planning / ethics / link)
        started = _turn_started.get()
        if started is not None:
            rec["duration_ms"] = int((time.monotonic() - started) * 1000)
        try:
            rec.update(_tc.current().summary())          # P-3: typed TurnContext summary (keys, ids, flags)
        except Exception:
            pass
        _append_log(cfg, rec)
    except Exception:
        logger.debug("lilith_router: turn-end record failed", exc_info=True)


def _rotate_if_full(path, max_bytes: int) -> None:
    """P-1 T-6: bounded retention. At max_bytes the log moves to `<name>.1` (replacing the previous one), so at most
    about 2 x max_bytes is kept. Never raises."""
    try:
        if path.stat().st_size >= max_bytes:
            path.replace(path.with_name(path.name + ".1"))
    except OSError:
        pass


def _append_log(cfg, record: dict) -> None:
    """Append one JSON record to the decision log, stamped with this turn's id. Never raises."""
    try:
        tid = _turn_id.get()
        if tid:
            record.setdefault("turn_id", tid)
        record.setdefault("ts", round(time.time(), 3))
        path = cfg.resolved_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        _rotate_if_full(path, getattr(cfg, "decision_log_max_bytes", 2_000_000))
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        logger.debug("lilith_router: decision log write failed", exc_info=True)


def _log_decision(cfg, platform, chat_id, decision, live, message) -> None:
    """Append one JSON line describing the routing decision. Never raises.

    No secrets and no message text are logged (F9-A D-2): only the decision
    and non-content metadata from :func:`_message_meta`.
    """
    try:
        record = {
            "ts": round(time.time(), 3),
            "platform": platform,
            "chat_id": str(chat_id or ""),
            "mode": decision.mode,
            "confidence": decision.confidence,
            "reason": decision.reason,
            "signals": decision.signals,
            "live": bool(live),
            **_message_meta(message),
        }
        _append_log(cfg, record)
    except Exception:
        logger.debug("lilith_router: decision log write failed", exc_info=True)


def _log_cognitive(cfg, platform, chat_id, intent, cog_mode, message) -> None:
    """Append one JSON line describing a cognitive-lane decision. Never raises."""
    try:
        record = {
            "ts": round(time.time(), 3),
            "platform": platform,
            "chat_id": str(chat_id or ""),
            "lane": "cognitive",
            "cognitive_mode": cog_mode,
            "intent": {
                k: intent.get(k)
                for k in ("belief", "pending", "draft", "example_only", "app_id")
            },
            **_message_meta(message),
        }
        _append_log(cfg, record)
    except Exception:
        logger.debug("lilith_router: cognitive log write failed", exc_info=True)


def _log_goal(cfg, platform, chat_id, gintent, goal_mode, message) -> None:
    """Append one JSON line describing a goal-lane decision. Never raises."""
    try:
        record = {
            "ts": round(time.time(), 3),
            "platform": platform,
            "chat_id": str(chat_id or ""),
            "lane": "goal",
            "goal_mode": goal_mode,
            "intent": {k: gintent.get(k) for k in ("goal_query", "goal_create", "app_id", "subtype")},
            **_message_meta(message),
        }
        _append_log(cfg, record)
    except Exception:
        logger.debug("lilith_router: goal log write failed", exc_info=True)


def _log_reasoning(cfg, platform, chat_id, rintent, mode, message, trace) -> None:
    """Append one JSON line describing a reasoning-lane decision (safe, non-CoT)."""
    try:
        record = {
            "ts": round(time.time(), 3),
            "platform": platform,
            "chat_id": str(chat_id or ""),
            "lane": "reasoning",
            "reasoning_mode": mode,
            "intent": {"mode": rintent.get("mode"), "subtype": rintent.get("subtype"),
                       "app_id": rintent.get("app_id")},
            "trace": trace,
            **_message_meta(message),
        }
        _append_log(cfg, record)
    except Exception:
        logger.debug("lilith_router: reasoning log write failed", exc_info=True)


def _log_workspace(cfg, platform, chat_id, snapshot, mode, message, trace) -> None:
    """Append one JSON line describing a workspace-lane decision (safe, non-CoT)."""
    try:
        record = {
            "ts": round(time.time(), 3),
            "platform": platform,
            "chat_id": str(chat_id or ""),
            "lane": "workspace",
            "workspace_mode": mode,
            "trace": trace,
            **_message_meta(message),
        }
        _append_log(cfg, record)
    except Exception:
        logger.debug("lilith_router: workspace log write failed", exc_info=True)


def _log_motivation(cfg, platform, chat_id, snapshot, mode, message, trace) -> None:
    """Append one JSON line describing a motivation-lane decision (safe, non-CoT)."""
    try:
        record = {
            "ts": round(time.time(), 3),
            "platform": platform,
            "chat_id": str(chat_id or ""),
            "lane": "motivation",
            "motivation_mode": mode,
            "trace": trace,
            **_message_meta(message),
        }
        _append_log(cfg, record)
    except Exception:
        logger.debug("lilith_router: motivation log write failed", exc_info=True)


def _log_planning(cfg, platform, chat_id, pintent, mode, message, trace) -> None:
    """Append one JSON line describing a planning-lane decision (safe, non-CoT)."""
    try:
        record = {
            "ts": round(time.time(), 3),
            "platform": platform,
            "chat_id": str(chat_id or ""),
            "lane": "planning",
            "planning_mode": mode,
            "intent": {"subtype": (pintent or {}).get("subtype"),
                       "app_id": (pintent or {}).get("app_id")},
            "trace": trace,
            **_message_meta(message),
        }
        _append_log(cfg, record)
    except Exception:
        logger.debug("lilith_router: planning log write failed", exc_info=True)


def _log_ethics(cfg, platform, chat_id, eintent, mode, message, trace) -> None:
    """Append one JSON line describing an ethics-lane decision (safe, non-CoT)."""
    try:
        record = {
            "ts": round(time.time(), 3),
            "platform": platform,
            "chat_id": str(chat_id or ""),
            "lane": "ethics",
            "ethics_mode": mode,
            "intent": {"trigger": (eintent or {}).get("trigger"),
                       "app_id": (eintent or {}).get("app_id")},
            "trace": trace,
            **_message_meta(message),
        }
        _append_log(cfg, record)
    except Exception:
        logger.debug("lilith_router: ethics log write failed", exc_info=True)


def _log_social_cognition(cfg, trace) -> None:
    """Append one safe Slice-14 observer trace. Never logs turn text or roles."""
    try:
        _append_log(cfg, dict(trace))
    except Exception:
        logger.debug("lilith_router: social cognition trace write failed", exc_info=True)


# P-3: the tone lines, the P-2 preferences and the correction flag are typed fields of this turn's TurnContext
# (turn_context.py); one renderer produces the approved wording for both reply paths.
_PREFERENCES = _social_prefs.ApprovedPreferenceSource(os.environ.get("LILITH_OS_API_URL", "http://127.0.0.1:8765"))


def _apply_social_preferences(cfg, decision, message: str) -> None:
    """P-2 (owner turns only). Two independent switches:
    - preferences (off / shadow / live): select approved preferences whose scope fits this turn; live sets the note,
      shadow only logs the selection;
    - corrections (off / live): an explicit durable correction sets the proposal hint, which also moves the turn off
      the lean path to the tool-capable agent. Ordinary one-off corrections stay where they are.
    Never raises; no text logged."""
    tctx = _tc.current()
    try:
        prefs_active = cfg.social_preferences_is_active()
        corrections_live = cfg.social_corrections_is_live()
        if not ((prefs_active or corrections_live) and _canonical_memory.owner_turn()):
            return
        correction = _social_prefs.durable_correction(message)
        if corrections_live and correction:
            tctx.correction = True
        rec = {"lane": "social_preferences", "mode": cfg.social_preferences_mode,
               "corrections_mode": "live" if corrections_live else "off", "durable_correction": correction,
               "correction_routed": bool(corrections_live and correction)}
        if prefs_active:
            focused = decision.mode != SOCIAL or bool((decision.signals or {}).get("tech"))
            available = _PREFERENCES.current()
            chosen = _social_prefs.select(available, focused=focused, message=message)
            tctx.preferences = tuple(chosen)
            tctx.preferences_live = cfg.social_preferences_is_live()
            tctx.style = _tc.dataclasses_replace(tctx.style, preference_refs=tuple(p.entry_id for p in chosen))
            rec.update(focused=focused, available=len(available), selected=[p.entry_id for p in chosen],
                       kinds=[p.kind for p in chosen], scopes=[p.scope.split(":", 1)[0] for p in chosen])
        _append_log(cfg, rec)
    except Exception:
        tctx.preferences, tctx.preferences_live, tctx.correction = (), False, False
        logger.debug("lilith_router: social preferences failed (none applied)", exc_info=True)


def _observe_social_cognition(cfg, platform: str, chat_id: str,
                              session_key: str, message: str):
    """Run the TURN-only Slice-14 observer. Returns the validated snapshot (or None); only the live owner tone note
    built from it may influence the reply."""
    if not cfg.social_cognition_is_active(platform, str(chat_id)):
        return None

    started = time.perf_counter()
    correlation_id = None
    try:
        from . import presence_contract
        from . import social_cognition

        correlation_id = social_cognition.make_correlation_id(session_key, message)
        social_input = social_cognition.build_social_input(
            message, correlation_id, platform,
            session_actor_ref=f"router:{correlation_id}:session-actor",
        )
        snapshot = social_cognition.build_social_context(social_input)
        presence_hint = presence_contract.derive_presence_hint(snapshot)
        trace = social_cognition.build_trace(
            snapshot,
            presence_hint,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        _log_social_cognition(cfg, trace)
        return snapshot
    except Exception as exc:
        _log_social_cognition(cfg, {
            "lane": "social_cognition",
            "correlation_id": correlation_id,
            "social_semantic_fingerprint": None,
            "participant_count": 0,
            "participant_kinds": [],
            "audience_context_class": None,
            "constraint_types": [],
            "cue_types": [],
            "conflict_types": [],
            "information_need_codes": [],
            "source_availability": "TURN_ONLY_BY_DESIGN",
            "presence_social_tone": None,
            "presence_formality_hint": None,
            "presence_playfulness": None,
            "validation_status": "INVALID",
            "fallback_reason": type(exc).__name__,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "schema_version": 1,
            "timestamp": round(time.time(), 3),
        })
        logger.debug("lilith_router: social cognition observer failed (fail-open)", exc_info=True)
    return None


def _evict(runner, session_key) -> None:
    fn = getattr(runner, "_evict_cached_agent", None)
    if callable(fn) and session_key:
        try:
            fn(session_key)
        except Exception:
            logger.debug("lilith_router: cached-agent eviction failed", exc_info=True)


# Social route health. Hermes imports provider plugins lazily (on the first
# get_provider_profile call), and nothing on the gateway's turn path makes that
# call, so the Groq plugin never ran and never exported GROQ_API_KEY from
# ~/.hermes/groq.env: every social turn silently fell back to the native model.
_ROUTE_WARN_EVERY_S = 600.0
_route_warned: dict = {}


def _ensure_provider_plugins(provider: str) -> None:
    """Run Hermes' own provider-plugin discovery once (idempotent, never raises)."""
    try:
        from providers import get_provider_profile

        get_provider_profile(provider)
    except Exception:
        logger.debug("lilith_router: provider plugin discovery failed", exc_info=True)


def _resolve_provider_runtime(runner, provider):
    """Hermes' per-provider credential resolver. It is a gateway.run module function in the
    deployed Hermes (not a runner method), which made every social turn fail with AttributeError."""
    fn = getattr(runner, "_resolve_runtime_agent_kwargs_for_provider", None)
    if fn is None:
        from gateway.run import _resolve_runtime_agent_kwargs_for_provider as fn
    return fn(provider)


# Questions about memory, shared history or personal context need Hermes' own
# recall (memory and session-search tools, full history). They keep the original
# native route: no social override, no lean reply.
_RECALL_RE = re.compile(
    r"\b(remember|recall|memor(y|ies)|forg[eo]t|know about me|what do you know|about me|about us|"
    r"last time|we talked|we spoke|you said|i told you|our (history|past|story|conversations?)|"
    r"do you still)\b",
    re.IGNORECASE,
)

# Questions about the user's own goals, priorities, progress, plans or projects. The lean reply has none of
# that context and once answered "what am I working toward right now?" with LILITH's own mission (owner
# acceptance test 4, 2026-11-03). They take the native recall route plus the user's tracked goals, read-only.
# Statements ("my only goal this weekend is relaxing") and leisure plans ("what's my plan for dinner?") never match.
_SELF_STATUS_RE = re.compile(
    r"\bwhat (am i|i'?m) (currently |really |actually )?(working|aiming|heading|striving|building|pushing) (toward|towards|for|on)\b|"
    r"\bwhat (am i|i'?m) (currently )?(focus(ed|ing) on|prioriti[sz]ing)\b|"
    r"\bwhat('?s| is| are) my (current |main |top |biggest |long[- ]term |career )?(goals?|priorit(y|ies)|focus|ambitions?|projects?)\b|"
    r"\bwhat('?s| is| are) my (current |main |big |long[- ]term |career )?plans?\s*(right now|now|at the moment|these days)?\s*[?.!]*$|"
    r"\bhow('?s| is| are) my (goals?|projects?|progress)\b|"
    r"\bhow am i (doing|progressing|tracking) (on|with|toward|towards) (my )?(goals?|projects?|plans?|career|priorities)\b|"
    r"\bwhere am i (at )?(with|on) (my )?(goals?|projects?|plans?|career|priorities)\b|"
    r"\bwhat projects (am i|i'?m) (working on|doing)\b",
    re.IGNORECASE,
)
SELF_STATUS_NOTE = """[LILITH turn note - the user's own goals]
The user is asking about THEIR OWN goals, priorities, progress, plans or projects, not about you.
Keep two kinds of things apart:
- Ongoing: their goals, career direction and ambitions, certifications and active projects (from their
  profile, your memory, earlier conversations and their tracked goals below, if any).
- Short-term: plans for today, tonight or this weekend, and casual or leisure talk from recent chat.
For what they are working toward, their goals, priorities, progress or direction, answer with the ongoing
ones first and with specifics; a short-term plan from recent chat gets at most one brief line, only if
relevant. If they explicitly ask about today, tonight, this weekend or a recent conversation, answer that
directly. Answer in the second person. Never answer with your own role, mission or development. If you
do not know something, say so; never invent goals."""

# E-T4 (2026-11-08): the note above sits in the system prompt, and twice the model still let a casual weekend plan
# from the last turn outweigh the durable goals. The same instruction, short, on the current message itself
# (API-only, like the tone note; never stored) is what the model weighs most. Owner turns only.
SELF_STATUS_HINT = ("[About this question: they mean their ongoing goals and direction - career, certifications, "
                    "active projects and the tracked goals in your notes - not today's or this weekend's plans from "
                    "recent chat. Lead with those, specifically, in the second person.]")


def _self_status_route(runner, cfg, platform, chat_id, session_key, turn_route, combined_ephemeral,
                       cached_agent, mode):
    """The native model with full recall, plus the user's tracked goals read through the Goals lane's own
    read path (no write: no goal_create, do_write False). Fail-open to the note alone."""
    _note_social_route(cfg, platform, chat_id, "native_self_status")
    parts = [SELF_STATUS_NOTE]
    owner = _canonical_memory.owner_turn()
    if owner and cfg.goals_is_live(platform, str(chat_id)):
        try:
            suffix, _unused = _world_context.build_goal_grounding(
                message="", session_key=session_key, do_write=False,
                gintent={"any": True, "goal_query": True, "goal_create": False, "app_id": None, "subtype": "general"})
            lines = [l for l in (suffix or "").splitlines() if l.startswith(("- GOAL ", "CURRENT FOCUS"))]
        except Exception:
            lines = []
            logger.debug("lilith_router: self-status goal read failed (fail-open)", exc_info=True)
        if lines:
            parts.append("THE USER'S TRACKED GOALS (durable, read-only):\n" + "\n".join(lines))
    suffix = "\n\n".join(parts)
    base = (combined_ephemeral or "").strip()
    STATE.set_native_social_agent(session_key, False)
    if getattr(cached_agent, "model", None) == cfg.groq_model:
        _evict(runner, session_key)
    out = {"turn_route": turn_route, "combined_ephemeral": (base + "\n\n" + suffix) if base else suffix,
           "force_rebuild": True, "mode": mode}
    if owner:
        out["self_status_hint"] = SELF_STATUS_HINT
    return out


def _groq_runtime(runner, cfg):
    """Return ``(runtime, "")`` for a usable Groq runtime, else ``(None, reason)``."""
    _ensure_provider_plugins(cfg.groq_provider)
    try:
        runtime = _resolve_provider_runtime(runner, cfg.groq_provider)
    except Exception as exc:
        return None, "resolve_error:%s" % type(exc).__name__
    if not (runtime.get("api_key") or runtime.get("credential_pool")):
        return None, "no_api_key"
    return runtime, ""


def _note_social_route(cfg, platform, chat_id, route, reason="") -> None:
    """Record which brain a live social turn used. Never raises, never logs secrets.

    Fallbacks are WARNING-level (at most once per reason per 10 minutes) so a
    broken social route can no longer hide at DEBUG level.
    """
    if route == "native_with_policy":
        now = time.monotonic()
        if now - _route_warned.get(reason, -_ROUTE_WARN_EVERY_S) >= _ROUTE_WARN_EVERY_S:
            _route_warned[reason] = now
            logger.warning("lilith_router: social route unavailable (%s); "
                           "native model with social policy", reason)
    try:
        _turn_route.set(route)
        record = {"ts": round(time.time(), 3), "platform": platform, "chat_id": str(chat_id or ""),
                  "lane": "social_route", "route": route, "route_reason": reason or None}
        _append_log(cfg, record)
    except Exception:
        logger.debug("lilith_router: social route log write failed", exc_info=True)


def route_turn(
    *,
    runner,
    ctx,
    model,
    runtime_kwargs,
    turn_route,
    combined_ephemeral,
    reasoning_config=None,
    cached_agent=None,
):
    # Canonical memory (read-only; off unless lilith_router/canonical_memory.json enables it): the note for this
    # turn's channel. Personal memory only for an owner channel the owner's grant lists; never Discord or groups.
    # Hermes' personal memory (USER.md / MEMORY.md) follows the same owner rule: `owner_memory` in the result tells
    # gateway/run.py whether this turn's agent may keep its memory store; the lean path reads owner_turn().
    note, session_key, owner = None, None, False
    try:
        _begin_turn(_config.load())
    except Exception:
        _turn_id.set(None)
    _turn_mode.set(None)
    _turn_route.set(None)
    _social_lean.LAST_USAGE.set(None)
    _canonical_memory.set_owner_turn(False)
    tctx = _tc.begin()                                   # P-3: a fresh, ephemeral TurnContext for this turn
    try:
        source = getattr(ctx, "source", None)
        if source is not None:
            platform = _platform_name(source)
            session_key = getattr(ctx, "session_key", None) or f"{platform}:{getattr(source, 'chat_id', '') or ''}"
            settings = _canonical_memory.load_settings(_config._hermes_home())
            channel = _canonical_memory.channel_for(settings, platform, source)
            owner = channel != _canonical_memory.PUBLIC
            _canonical_memory.set_owner_turn(owner, channel)
            tctx.channel, tctx.owner = channel, owner
            # Discord owner-DM link challenge (a ready reply, no model call; never on an owner channel)
            if not owner:
                link = _owner_link.handle(settings, platform, source, getattr(ctx, "message", "") or "",
                                          home=_config._hermes_home())
                if link:
                    _turn_mode.set("owner_link")
                    return _with_owner_memory({"final_response": link, "mode": "owner_link"}, False)
            note = _canonical_memory.turn_note(settings, platform, source, session_key)
    except Exception:
        note, owner = None, False
        _canonical_memory.set_owner_turn(False)
        tctx.owner = False
    try:
        result = _route_turn_impl(
            runner=runner,
            ctx=ctx,
            model=model,
            runtime_kwargs=runtime_kwargs,
            turn_route=turn_route,
            combined_ephemeral=combined_ephemeral,
            reasoning_config=reasoning_config,
            cached_agent=cached_agent,
        )
    except Exception:
        # Absolute guarantee: the router can never break a turn.
        logger.debug("lilith_router: route_turn failed (fail-open)", exc_info=True)
        result = None
    _turn_mode.set(result.get("mode") if isinstance(result, dict) else None)
    if session_key is None:
        return _with_fallback_chain(_with_owner_memory(result, False))
    try:
        merged = _canonical_memory.merge(result, note=note, combined_ephemeral=combined_ephemeral,
                                         session_key=session_key, cached_agent=cached_agent)
    except Exception:
        logger.debug("lilith_router: canonical memory merge failed (no note)", exc_info=True)
        merged = result
    return _with_fallback_chain(_with_social_note(_with_owner_memory(merged, owner)))


def _with_fallback_chain(out: dict) -> dict:
    """Full-agent provider fallback: router.yaml `full_agent_fallback` rides on every routed turn as Hermes'
    `fallback_model` chain, after the social route's own fallback (run.py also applies it to a cached agent).
    A ready reply needs none; a bad config leaves the turn exactly as before."""
    try:
        cfg = _config.load()
        chain = list(cfg.full_agent_fallback) if cfg.enabled else []
        if not chain or "final_response" in out:
            return out
        merged = [dict(e) for e in (out.get("fallback_model") or []) if isinstance(e, dict)]
        seen = {(e.get("provider"), e.get("model")) for e in merged}
        merged += [dict(e) for e in chain if (e["provider"], e["model"]) not in seen]
        out["fallback_model"] = merged
    except Exception:
        logger.debug("lilith_router: fallback chain not applied", exc_info=True)
    return out


def _with_social_note(out: dict) -> dict:
    """The owner tone note rides on the current user message, API-only (run.py `turn_hint`), so the cached agent and
    its prompt stay as they are. A ready reply (lean, Reasoning, Planning, Ethics) gets none here."""
    status = out.pop("self_status_hint", None)                       # a goals question needs no tone note
    tctx = _tc.current()
    hint = _tc.agent_hint(tctx, status) if _canonical_memory.owner_turn() else None
    if hint and "final_response" not in out:
        out["turn_hint"] = hint
    return out


# D1 (2026-11-08): when the social guard replaces a reply, Hermes has already stored the rejected original -- and
# its provider replay items (codex_message_items etc.) would resend the original text on the next turn. Make the
# stored row say what the user actually saw. One row, this session's latest assistant reply, and only when it is
# the reply the guard replaced; replay columns are cleared (costs one prompt-cache boundary). Never raises.
_REPLAY_COLUMNS = ("api_content", "codex_message_items", "codex_reasoning_items", "reasoning", "reasoning_content",
                   "reasoning_details")


def record_delivered_reply(session_db, session_id, original, delivered) -> bool:
    try:
        if not (session_id and isinstance(original, str) and isinstance(delivered, str)):
            return False
        if not delivered.strip() or delivered == original:
            return False
        db = getattr(session_db, "_db", session_db)
        if db is None or not hasattr(db, "_execute_write"):
            return False
        want = _social_guard.clean(original)

        def _do(conn):
            row = conn.execute(
                "SELECT id, content FROM messages WHERE session_id = ? AND role = 'assistant' AND active = 1 "
                "AND (tool_calls IS NULL OR tool_calls = '' OR tool_calls = '[]') ORDER BY id DESC LIMIT 1",
                (session_id,)).fetchone()
            if row is None or not isinstance(row[1], str) or _social_guard.clean(row[1]) != want:
                return False
            cols = set(db._message_column_names(conn))
            sets = ["content = ?"] + ["%s = NULL" % c for c in _REPLAY_COLUMNS if c in cols]
            conn.execute("UPDATE messages SET %s WHERE id = ?" % ", ".join(sets), (delivered, row[0]))
            return True

        return bool(db._execute_write(_do))
    except Exception:
        logger.debug("lilith_router: delivered-reply record failed (transcript unchanged)", exc_info=True)
        return False


def _with_owner_memory(result, owner: bool):
    """Always a dict carrying `owner_memory` (run.py drops the agent's memory store unless it is True)."""
    out = dict(result) if isinstance(result, dict) else {}
    out["owner_memory"] = owner is True
    return out


def _route_turn_impl(
    *, runner, ctx, model, runtime_kwargs, turn_route, combined_ephemeral,
    reasoning_config, cached_agent,
):
    cfg = _config.load()
    if not cfg.enabled:
        return None

    source = getattr(ctx, "source", None)
    if source is None:
        return None
    platform = _platform_name(source)
    chat_id = getattr(source, "chat_id", "") or ""
    session_key = getattr(ctx, "session_key", None) or f"{platform}:{chat_id}"
    message = getattr(ctx, "message", "") or ""

    # -- Slice 14 social cognition observer (TURN-only; SHADOW-only) --
    # Computes validated, ephemeral semantics and a renderer-independent
    # Presence contract, writes a safe trace, discards both, and continues.
    # It has no authority over models, prompts, routing, replies, or guards.
    _social_snapshot = _observe_social_cognition(cfg, platform, str(chat_id), session_key, message)
    # -- end Slice 14 social cognition observer --

    # Decide the mode from message + bounded recent turns + previous mode.
    recent = STATE.recent(session_key, cfg.recent_turns)
    previous_mode = STATE.previous_mode(session_key)
    decision = classify(message, recent, previous_mode)
    tctx = _tc.current()
    tctx.mode = decision.mode
    # focused: a technical / work route, or a technical subject inside a social turn (routing unchanged)
    tctx.focused = decision.mode != SOCIAL or bool((decision.signals or {}).get("tech"))

    # -- Slice 14 live tone note (owner turns only; a light hint, never a script) --
    if _social_snapshot is not None and _canonical_memory.owner_turn() \
            and cfg.social_cognition_is_live(platform, str(chat_id)):
        try:
            from . import social_cognition as _sc
            focused = tctx.focused
            tone_ctx = _sc.tone_context(message, recent)
            keys = _sc.tone_note_keys(_social_snapshot, focused=focused, context=tone_ctx)
            tctx.style = _tc.directive(keys, focused=focused)
            _log_social_cognition(cfg, {"lane": "social_cognition_live", "mode": decision.mode,
                                        "tone_note_keys": keys, "focused": focused,
                                        "context": sorted(k for k, v in tone_ctx.items() if v),
                                        "timestamp": round(time.time(), 3)})
        except Exception:
            tctx.style = _tc.directive((), focused=tctx.focused)
            logger.debug("lilith_router: social tone note failed (no note)", exc_info=True)
    _apply_social_preferences(cfg, decision, message)

    # ── Slice 7.2 cognitive lane (additive; belief / pending / draft turns) ──
    # Runs BEFORE the social/technical/work model decision so a belief or pending
    # question that would otherwise be misrouted (e.g. "what's pending" reads as
    # social) is grounded on the WORK brain with World-Model context. Governs
    # ONLY these turns; every other turn falls through to the unchanged routing.
    # -- Slice 9 reasoning lane (additive; analytic framings only; TOOL-LESS) --
    # Runs before the 7.2/8 lanes but detect_reasoning_intent YIELDS to their
    # intents, so accepted paths stay authoritative. Produces a natural answer via
    # a bounded TOOL-LESS reasoning call and returns it as the turn's
    # final_response (run.py short-circuit), which still flows through
    # enforce_reply. Fully fail-open: any failure -> fall through unchanged.
    # -- Slice 12 planning lane (additive; EXPLICIT plan framings only; PROPOSAL-ONLY) --
    # Runs before the reasoning lane, but detect_planning_intent YIELDS to explicit
    # action (7.2 draft / 8 goal_create), goal-state queries, and pending, so those
    # accepted paths stay authoritative. Builds a BOUNDED PlanningInput for ONE
    # subject, runs the deterministic planner (template fast-path; the bounded
    # no-tool LLM candidate path is implemented + unit-tested but NOT wired into
    # this live call in V1), validates, and — in live mode — returns a
    # PLAN_PROPOSED / USER_DECISION_REQUIRED answer as the turn's final_response
    # (reuses the Slice-9 run.py short-circuit). NO writes, NO execution, NO tools,
    # NO approval/verification claim. Fully fail-open: any failure or non-proposal
    # outcome -> fall through to the existing lanes unchanged.
    if cfg.planning_is_active(platform, str(chat_id)):
        try:
            pintent = _world_context.detect_planning_intent(message)
        except Exception:
            pintent = None
        if pintent and pintent.get("any"):
            planning_live = cfg.planning_is_live(platform, str(chat_id))
            _p_ws = None
            _p_mot = None
            if cfg.workspace_is_active(platform, str(chat_id)):
                try:
                    from . import workspace as _workspace
                    _p_cands = _world_context.build_attention_candidates(
                        message, session_key, pintent, channel=platform)
                    if cfg.motivation_is_active(platform, str(chat_id)):
                        try:
                            _p_mot = _world_context.build_motivation_snapshot(
                                message, session_key, pintent, _p_cands, channel=platform)
                            if cfg.motivation_is_live(platform, str(chat_id)):
                                _p_cands = list(_p_cands) + _world_context.motivation_candidates(_p_mot)
                        except Exception:
                            _p_mot = None
                    _p_ws = _workspace.build_workspace_snapshot(
                        _p_cands, capacity=cfg.workspace_capacity, channel=platform)
                except Exception:
                    _p_ws = None
                    logger.debug("lilith_router: planning attention build failed (fail-open)", exc_info=True)
            _p_ws_live = _p_ws is not None and cfg.workspace_is_live(platform, str(chat_id))
            try:
                pin = _world_context.build_planning_input(
                    message, session_key, pintent,
                    _p_ws if _p_ws_live else None,
                    _p_mot if _p_ws_live else None, channel=platform)
                from . import planning as _planning
                p_result, p_trace = _planning.run_planning(pin, max_steps=cfg.planning_max_steps)
                _log_planning(cfg, platform, chat_id, pintent,
                              "live" if planning_live else "shadow", message, p_trace)
                if (planning_live and p_result and p_result.get("answer")
                        and p_result.get("outcome") in ("PLAN_PROPOSED", "USER_DECISION_REQUIRED")):
                    # Record WORK so the social guard leaves this grounded planning
                    # answer untouched; it flows through enforce_reply as normal.
                    STATE.record(session_key, message, WORK)
                    return {"final_response": p_result["answer"], "mode": "planning"}
                # shadow, or no viable proposal -> fall through to existing lanes
            except Exception:
                logger.debug("lilith_router: planning lane failed (fail-open)", exc_info=True)
    # -- end planning lane --
    # -- Slice 13 ethics lane (additive; EXPLICIT ethical questions only; ADVISORY-ONLY) --
    # Runs after the planning lane and before the reasoning lane, but
    # detect_ethics_intent YIELDS to explicit action (7.2 draft / 8 goal_create),
    # goal-state queries, pending, AND planning, so those accepted paths stay
    # authoritative. Builds a BOUNDED EthicalInput (with ephemeral TURN evidence)
    # for ONE USER_INTENT subject, runs the deterministic advisory deliberator
    # (the bounded no-tool LLM candidate path is built + unit-tested but NOT wired
    # live), and -- in live mode -- returns the advisory answer as the turn's
    # final_response (reuses the Slice-9 run.py short-circuit). Ethics NEVER returns
    # ALLOW/DENY, never acts/approves/verifies, never mutates goals/plans/beliefs/
    # drafts, never impersonates Policy. Fully fail-open.
    if cfg.ethics_is_active(platform, str(chat_id)):
        try:
            eintent = _world_context.detect_ethics_intent(message)
        except Exception:
            eintent = None
        if eintent and eintent.get("any"):
            ethics_live = cfg.ethics_is_live(platform, str(chat_id))
            _e_ws = None
            if cfg.workspace_is_active(platform, str(chat_id)):
                try:
                    from . import workspace as _workspace
                    _e_cands = _world_context.build_attention_candidates(
                        message, session_key, eintent, channel=platform)
                    _e_ws = _workspace.build_workspace_snapshot(
                        _e_cands, capacity=cfg.workspace_capacity, channel=platform)
                except Exception:
                    _e_ws = None
                    logger.debug("lilith_router: ethics attention build failed (fail-open)", exc_info=True)
            _e_ws_live = _e_ws is not None and cfg.workspace_is_live(platform, str(chat_id))
            try:
                ein = _world_context.build_ethical_input(
                    message, session_key, eintent,
                    _e_ws if _e_ws_live else None, channel=platform)
                from . import ethics as _ethics
                e_result, e_trace = _ethics.run_ethics(
                    ein, max_concerns=cfg.ethics_max_concerns,
                    max_tensions=cfg.ethics_max_tensions)
                _log_ethics(cfg, platform, chat_id, eintent,
                            "live" if ethics_live else "shadow", message, e_trace)
                if ethics_live and e_result and e_result.get("answer"):
                    # Record WORK so the social guard leaves this grounded advisory
                    # answer untouched; it flows through enforce_reply as normal.
                    STATE.record(session_key, message, WORK)
                    return {"final_response": e_result["answer"], "mode": "ethics"}
                # shadow -> fall through to existing lanes
            except Exception:
                logger.debug("lilith_router: ethics lane failed (fail-open)", exc_info=True)
    # -- end ethics lane --
    if cfg.reasoning_is_active(platform, str(chat_id)):
        try:
            rintent = _world_context.detect_reasoning_intent(message)
        except Exception:
            rintent = None
        if rintent and rintent.get("any"):
            reasoning_live = cfg.reasoning_is_live(platform, str(chat_id))
            # -- Slice 10 Global Workspace: bounded attention selection --
            # Build an ephemeral WorkspaceSnapshot from durable source refs and
            # log it (shadow or live). In workspace-live mode a successful
            # snapshot is the REAL selection boundary for the Slice 9
            # ReasoningInput (bounded support expansion around the SELECTED refs
            # only); shadow / failure / no-primary falls back to the exact
            # existing builder. Fully fail-open; performs NO writes.
            _ws_snapshot = None
            _mot_snapshot = None
            if cfg.workspace_is_active(platform, str(chat_id)):
                try:
                    from . import workspace as _workspace
                    _ws_cands = _world_context.build_attention_candidates(
                        message, session_key, rintent, channel=platform)
                    # -- Slice 11 Motivation / Homeostasis: bounded ordinal drives --
                    # Build+log an ephemeral MotivationSnapshot scoped to this pool
                    # + user-referenced target + Executive focus. In motivation-live
                    # mode, eligible (dedup-safe) MOTIVATION_DRIVE candidates merge
                    # into the pool BEFORE arbitration. Fully fail-open; NO writes.
                    if cfg.motivation_is_active(platform, str(chat_id)):
                        try:
                            _mot_snapshot = _world_context.build_motivation_snapshot(
                                message, session_key, rintent, _ws_cands, channel=platform)
                            _log_motivation(
                                cfg, platform, chat_id, _mot_snapshot,
                                "live" if cfg.motivation_is_live(platform, str(chat_id)) else "shadow",
                                message, _world_context.motivation_trace(_mot_snapshot))
                            if cfg.motivation_is_live(platform, str(chat_id)):
                                _ws_cands = list(_ws_cands) + _world_context.motivation_candidates(_mot_snapshot)
                        except Exception:
                            _mot_snapshot = None
                            logger.debug("lilith_router: motivation lane failed (fail-open)", exc_info=True)
                    _ws_snapshot = _workspace.build_workspace_snapshot(
                        _ws_cands, capacity=cfg.workspace_capacity, channel=platform)
                    _log_workspace(
                        cfg, platform, chat_id, _ws_snapshot,
                        "live" if cfg.workspace_is_live(platform, str(chat_id)) else "shadow",
                        message, _workspace.build_trace(_ws_snapshot))
                except Exception:
                    _ws_snapshot = None
                    logger.debug("lilith_router: workspace lane failed (fail-open)", exc_info=True)
            _ws_live = _ws_snapshot is not None and cfg.workspace_is_live(platform, str(chat_id))
            try:
                if reasoning_live:
                    ri = _world_context.select_reasoning_input_m(
                        message, session_key, rintent,
                        _ws_snapshot if _ws_live else None,
                        _mot_snapshot if _ws_live else None, channel=platform)
                    from . import reasoning as _reasoning
                    r_result, r_trace = _reasoning.run_reasoning(ri)
                    _log_reasoning(cfg, platform, chat_id, rintent, "live", message, r_trace)
                    if r_result and r_result.get("answer"):
                        # Record WORK so the social guard leaves this grounded
                        # reasoning answer untouched; it still passes through
                        # enforce_reply exactly as a normal final response.
                        STATE.record(session_key, message, WORK)
                        return {"final_response": r_result["answer"], "mode": "reasoning"}
                    # reasoning failed/invalid -> fall through to existing lanes
                else:
                    _log_reasoning(cfg, platform, chat_id, rintent, "shadow", message, None)
            except Exception:
                logger.debug("lilith_router: reasoning lane failed (fail-open)", exc_info=True)
    # -- end reasoning lane --
    if cfg.cognitive_is_active(platform, str(chat_id)):
        try:
            intent = _world_context.detect_intent(message)
        except Exception:
            intent = None
        if intent and intent.get("any"):
            cog_live = cfg.cognitive_is_live(platform, str(chat_id))
            _log_cognitive(
                cfg, platform, chat_id, intent, "live" if cog_live else "shadow", message
            )
            if cog_live:
                # Record a non-social mode so the social-reply guard leaves this
                # grounded WORK turn untouched, and continuity stays sane.
                STATE.record(session_key, message, WORK)
                try:
                    suffix, _action = _world_context.build_grounding(
                        message=message,
                        session_key=session_key,
                        intent=intent,
                        do_write=True,
                        dedup=cfg.cognitive_draft_dedup,
                    )
                except Exception:
                    suffix = None
                    logger.debug("lilith_router: build_grounding failed", exc_info=True)
                if suffix:
                    base = (combined_ephemeral or "").strip()
                    grounded = (base + "\n\n" + suffix) if base else suffix
                    # Ensure the WORK brain (native gpt-5.6-sol) runs, not a
                    # lingering Groq social agent.
                    if getattr(cached_agent, "model", None) == cfg.groq_model:
                        _evict(runner, session_key)
                    return {
                        "turn_route": turn_route,          # native model unchanged
                        "combined_ephemeral": grounded,
                        "force_rebuild": True,             # guarantee grounding applies
                        "mode": "cognitive",
                    }
                # Grounding unavailable -> fall through to normal routing below.
            # Shadow mode -> observed + logged only; fall through unchanged.
    # ── end cognitive lane ──

    # -- Slice 8 goal / executive lane (additive; goal-state + tracking turns) --
    # Runs after the cognitive lane and before the social/technical decision, so a
    # goal-state question ('what are you trying to do', 'what is blocked', 'which
    # goal has priority') is grounded on the WORK brain from durable Goal state,
    # and an explicit 'track as a goal' creates a durable goal (server-side dedup).
    # Governs ONLY these turns; fully fail-open.
    if cfg.goals_is_active(platform, str(chat_id)):
        try:
            gintent = _world_context.detect_goal_intent(message)
        except Exception:
            gintent = None
        if gintent and gintent.get("any"):
            goals_live = cfg.goals_is_live(platform, str(chat_id))
            _log_goal(cfg, platform, chat_id, gintent, "live" if goals_live else "shadow", message)
            if goals_live:
                STATE.record(session_key, message, WORK)
                try:
                    suffix, _gaction = _world_context.build_goal_grounding(
                        message=message, session_key=session_key, gintent=gintent,
                        do_write=True,
                    )
                except Exception:
                    suffix = None
                    logger.debug("lilith_router: build_goal_grounding failed", exc_info=True)
                if suffix:
                    base = (combined_ephemeral or "").strip()
                    grounded = (base + "\n\n" + suffix) if base else suffix
                    if getattr(cached_agent, "model", None) == cfg.groq_model:
                        _evict(runner, session_key)
                    return {
                        "turn_route": turn_route,
                        "combined_ephemeral": grounded,
                        "force_rebuild": True,
                        "mode": "goal",
                    }
                # Grounding unavailable -> fall through to normal routing below.
            # Shadow mode -> observed + logged only; fall through unchanged.
    # -- end goal lane --

    STATE.record(session_key, message, decision.mode)

    live = cfg.channel_is_live(platform, str(chat_id))
    _log_decision(cfg, platform, chat_id, decision, live, message)

    # Shadow (or channel not live-enabled): observe only, never switch.
    if not live:
        return None

    if _SELF_STATUS_RE.search(message):
        return _self_status_route(runner, cfg, platform, chat_id, session_key, turn_route, combined_ephemeral,
                                  cached_agent, decision.mode)

    cached_model = getattr(cached_agent, "model", None)
    groq_model = cfg.groq_model
    recall = decision.mode == SOCIAL and bool(_RECALL_RE.search(message or ""))
    if recall:
        _note_social_route(cfg, platform, chat_id, "native_recall")

    if decision.mode == SOCIAL and not recall:
        # Already running on the Groq social agent — reuse it.
        if cached_agent is not None and cached_model == groq_model:
            _note_social_route(cfg, platform, chat_id, "groq", "cached")
            return None
        ephemeral = _policy.social_ephemeral(combined_ephemeral)

        def native_with_policy(reason):
            # Stay on the native model but KEEP the social policy. The cached
            # agent's prompt is fixed at creation, so rebuild it once unless the
            # router already built it with the policy.
            _note_social_route(cfg, platform, chat_id, "native_with_policy", reason)
            if cached_agent is not None and STATE.native_social_agent(session_key):
                return None
            if cached_agent is not None:
                _evict(runner, session_key)
            STATE.set_native_social_agent(session_key, True)
            return {"combined_ephemeral": ephemeral, "force_rebuild": cached_agent is not None,
                    "mode": SOCIAL}

        groq_runtime, why = _groq_runtime(runner, cfg)
        if groq_runtime is None:
            return native_with_policy(why)
        if cfg.social_lean_is_on(platform):
            # Groq Free cannot take the full ~23K-token agent request, so casual
            # turns go through one lean, tool-less call; everything else (and any
            # lean failure) takes the native model with the social policy.
            why = _social_lean.skip_reason(message)
            if not why and tctx.correction:
                why = "durable_correction"           # P-2: the tool-capable agent may propose remembering it
            if not why:
                text, why = _social_lean.reply(
                    runner=runner, cfg=cfg, home=_config._hermes_home(), session_key=session_key,
                    message=message, runtime=groq_runtime, include_profile=_canonical_memory.owner_turn(),
                    policy=_policy.SOCIAL_POLICY + ("\n\n" + _canonical_memory.current_note()
                                                    if _canonical_memory.current_note() else "")
                    + _tc.lean_suffix(tctx))      # P-3: one renderer (tone lines, approved preferences)
                if text:
                    _note_social_route(cfg, platform, chat_id, "groq_lean")
                    return {"final_response": text, "mode": SOCIAL}
            return native_with_policy("lean:" + why)
        groq_route = runner._resolve_turn_agent_config(
            message, groq_model, dict(groq_runtime)
        )
        _note_social_route(cfg, platform, chat_id, "groq")
        STATE.set_native_social_agent(session_key, False)
        force = cached_agent is not None  # exists but non-groq -> rebuild
        if force:
            _evict(runner, session_key)
        # Per-turn fallback: if the Groq turn fails / rate-limits / times out,
        # Hermes' native fallback chain retries on gpt-5.6-sol carrying THIS
        # turn's social ephemeral prompt (= "GPT-5.6 Sol with social policy").
        fallback = [{"provider": cfg.hermes_provider, "model": cfg.hermes_model}]
        return {
            "turn_route": groq_route,
            "combined_ephemeral": ephemeral,
            "fallback_model": fallback,
            "force_rebuild": force,
            "mode": SOCIAL,
        }

    # technical / work / recall -> native gpt-5.6-sol. Only intervene to switch
    # BACK from a lingering Groq social agent, or from a native agent the router
    # built with the social policy.
    native_social = STATE.native_social_agent(session_key)
    if native_social:
        STATE.set_native_social_agent(session_key, False)
    if cached_agent is not None and (cached_model == groq_model or native_social):
        _evict(runner, session_key)
        return {"force_rebuild": True, "mode": decision.mode}
    return None


def enforce_reply(final_response, ctx):
    """Post-generation social-response guard. Returns the reply to deliver.

    Runs ONLY for a live social turn (this session's last routed mode is social
    on a live channel). Strips residual reasoning wrappers and, on empty/leaky
    output, regenerates a clean reply on gpt-5.6-sol under the social policy so
    the user always receives a normal LILITH message. NEVER raises into the
    core: on any error it returns the original reply unchanged (fail open).

    Cognitive-lane turns record mode WORK, so the ``previous_mode == SOCIAL``
    guard below leaves their grounded replies untouched.
    """
    try:
        cfg = _config.load()
        if not cfg.enabled:
            return final_response
        source = getattr(ctx, "source", None)
        if source is None:
            return final_response
        platform = _platform_name(source)
        chat_id = getattr(source, "chat_id", "") or ""
        session_key = getattr(ctx, "session_key", None) or f"{platform}:{chat_id}"
        # Only guard turns we actually route live to the social brain.
        if not cfg.channel_is_live(platform, str(chat_id)):
            return final_response
        if STATE.previous_mode(session_key) != SOCIAL:
            return final_response
        last_reply = STATE.last_social_reply(session_key)
        delivered = _social_guard.enforce_social_reply(
            final_response,
            user_message=getattr(ctx, "message", "") or "",
            recent=STATE.recent(session_key, cfg.recent_turns),
            last_reply=last_reply,
        )
        # Remember the delivered reply so the next social turn can enforce the
        # adjacent pet-name rule against what the user actually saw.
        try:
            if isinstance(delivered, str) and delivered.strip():
                STATE.record_social_reply(session_key, delivered)
        except Exception:
            logger.debug("lilith_router: record_social_reply failed", exc_info=True)
        return delivered
    except Exception:
        logger.debug("lilith_router: enforce_reply failed (fail-open)", exc_info=True)
        return final_response
