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

import json
import logging
import time

from . import config as _config
from . import policy as _policy
from . import social_guard as _social_guard
from . import world_context as _world_context
from .classifier import SOCIAL, WORK, classify
from .state import STATE

logger = logging.getLogger(__name__)


def _platform_name(source) -> str:
    plat = getattr(source, "platform", None)
    return getattr(plat, "value", None) or str(plat)


def _log_decision(cfg, platform, chat_id, decision, live, message) -> None:
    """Append one JSON line describing the routing decision. Never raises.

    No secrets are logged. A short message preview (≤60 chars) is included for
    auditing — consistent with the gateway's own inbound-message logging.
    """
    try:
        path = cfg.resolved_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": round(time.time(), 3),
            "platform": platform,
            "chat_id": str(chat_id or ""),
            "mode": decision.mode,
            "confidence": decision.confidence,
            "reason": decision.reason,
            "signals": decision.signals,
            "live": bool(live),
            "preview": (message or "")[:60].replace("\n", " "),
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        logger.debug("lilith_router: decision log write failed", exc_info=True)


def _log_cognitive(cfg, platform, chat_id, intent, cog_mode, message) -> None:
    """Append one JSON line describing a cognitive-lane decision. Never raises."""
    try:
        path = cfg.resolved_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
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
            "preview": (message or "")[:60].replace("\n", " "),
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        logger.debug("lilith_router: cognitive log write failed", exc_info=True)


def _log_goal(cfg, platform, chat_id, gintent, goal_mode, message) -> None:
    """Append one JSON line describing a goal-lane decision. Never raises."""
    try:
        path = cfg.resolved_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": round(time.time(), 3),
            "platform": platform,
            "chat_id": str(chat_id or ""),
            "lane": "goal",
            "goal_mode": goal_mode,
            "intent": {k: gintent.get(k) for k in ("goal_query", "goal_create", "app_id", "subtype")},
            "preview": (message or "")[:60].replace("\n", " "),
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        logger.debug("lilith_router: goal log write failed", exc_info=True)


def _log_reasoning(cfg, platform, chat_id, rintent, mode, message, trace) -> None:
    """Append one JSON line describing a reasoning-lane decision (safe, non-CoT)."""
    try:
        path = cfg.resolved_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": round(time.time(), 3),
            "platform": platform,
            "chat_id": str(chat_id or ""),
            "lane": "reasoning",
            "reasoning_mode": mode,
            "intent": {"mode": rintent.get("mode"), "subtype": rintent.get("subtype"),
                       "app_id": rintent.get("app_id")},
            "trace": trace,
            "preview": (message or "")[:60].replace("\n", " "),
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        logger.debug("lilith_router: reasoning log write failed", exc_info=True)


def _log_workspace(cfg, platform, chat_id, snapshot, mode, message, trace) -> None:
    """Append one JSON line describing a workspace-lane decision (safe, non-CoT)."""
    try:
        path = cfg.resolved_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": round(time.time(), 3),
            "platform": platform,
            "chat_id": str(chat_id or ""),
            "lane": "workspace",
            "workspace_mode": mode,
            "trace": trace,
            "preview": (message or "")[:60].replace("\n", " "),
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        logger.debug("lilith_router: workspace log write failed", exc_info=True)


def _log_motivation(cfg, platform, chat_id, snapshot, mode, message, trace) -> None:
    """Append one JSON line describing a motivation-lane decision (safe, non-CoT)."""
    try:
        path = cfg.resolved_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": round(time.time(), 3),
            "platform": platform,
            "chat_id": str(chat_id or ""),
            "lane": "motivation",
            "motivation_mode": mode,
            "trace": trace,
            "preview": " ".join(((message or "")[:60]).splitlines()),
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        logger.debug("lilith_router: motivation log write failed", exc_info=True)


def _log_planning(cfg, platform, chat_id, pintent, mode, message, trace) -> None:
    """Append one JSON line describing a planning-lane decision (safe, non-CoT)."""
    try:
        path = cfg.resolved_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": round(time.time(), 3),
            "platform": platform,
            "chat_id": str(chat_id or ""),
            "lane": "planning",
            "planning_mode": mode,
            "intent": {"subtype": (pintent or {}).get("subtype"),
                       "app_id": (pintent or {}).get("app_id")},
            "trace": trace,
            "preview": " ".join(((message or "")[:60]).splitlines()),
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        logger.debug("lilith_router: planning log write failed", exc_info=True)


def _log_ethics(cfg, platform, chat_id, eintent, mode, message, trace) -> None:
    """Append one JSON line describing an ethics-lane decision (safe, non-CoT)."""
    try:
        path = cfg.resolved_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": round(time.time(), 3),
            "platform": platform,
            "chat_id": str(chat_id or ""),
            "lane": "ethics",
            "ethics_mode": mode,
            "intent": {"trigger": (eintent or {}).get("trigger"),
                       "app_id": (eintent or {}).get("app_id")},
            "trace": trace,
            "preview": " ".join(((message or "")[:60]).splitlines()),
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        logger.debug("lilith_router: ethics log write failed", exc_info=True)


def _log_social_cognition(cfg, trace) -> None:
    """Append one safe Slice-14 observer trace. Never logs turn text or roles."""
    try:
        path = cfg.resolved_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(trace, ensure_ascii=True) + "\n")
    except Exception:
        logger.debug("lilith_router: social cognition trace write failed", exc_info=True)


def _observe_social_cognition(cfg, platform: str, chat_id: str,
                              session_key: str, message: str) -> None:
    """Run the TURN-only Slice-14 observer without influencing the turn."""
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
        del social_input, snapshot, presence_hint, trace
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
    try:
        return _route_turn_impl(
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
        return None


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
    _observe_social_cognition(cfg, platform, str(chat_id), session_key, message)
    # -- end Slice 14 social cognition observer --

    # Decide the mode from message + bounded recent turns + previous mode.
    recent = STATE.recent(session_key, cfg.recent_turns)
    previous_mode = STATE.previous_mode(session_key)
    decision = classify(message, recent, previous_mode)

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

    cached_model = getattr(cached_agent, "model", None)
    groq_model = cfg.groq_model

    if decision.mode == SOCIAL:
        # Already running on the Groq social agent — reuse it.
        if cached_agent is not None and cached_model == groq_model:
            return None
        # Resolve Groq credentials natively; bail (fail open) if unauthenticated.
        try:
            groq_runtime = runner._resolve_runtime_agent_kwargs_for_provider(
                cfg.groq_provider
            )
        except Exception:
            logger.debug("lilith_router: groq creds unresolved; fail open", exc_info=True)
            return None
        if not (groq_runtime.get("api_key") or groq_runtime.get("credential_pool")):
            return None
        groq_route = runner._resolve_turn_agent_config(
            message, groq_model, dict(groq_runtime)
        )
        ephemeral = _policy.social_ephemeral(combined_ephemeral)
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

    # technical / work -> native gpt-5.6-sol. Only intervene to switch BACK
    # from a lingering Groq social agent.
    if cached_agent is not None and cached_model == groq_model:
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
