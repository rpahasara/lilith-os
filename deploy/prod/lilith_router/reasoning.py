# -*- coding: utf-8 -*-
"""LILITH Slice 9 — Reasoning Extraction V1.

A bounded, TOOL-LESS cognitive component. It receives a bounded ReasoningInput,
runs ONE side-effect-free model call, and returns a typed ReasoningResult with a
natural-language ``answer`` plus persona-neutral, evidence-grounded cognitive
artifacts (assumptions / uncertainties / conflicts / blockers / candidate next
steps). It NEVER acts:

  * no tools (enabled_toolsets=[] is the primary security boundary)
  * no memory / context files (skip_memory / skip_context_files)
  * no World Model / Goal / task / draft mutation
  * no connector / shell / browser / email / filesystem / DB access
  * no approval decision, no verified-completion claim
  * no hidden chain-of-thought in the output

Only stdlib is imported at module load; Hermes internals (gateway.run, run_agent)
are imported lazily inside the model call so unit tests run offline. The model
call, model resolver, and agent constructor are module-level indirections so
tests can inject fakes and assert the exact no-tool construction (Requirement B).
"""
from __future__ import annotations

import json
import logging
import re
import time

logger = logging.getLogger(__name__)

REASONING_SCHEMA_VERSION = 1

_OUTCOMES = ("OK", "INSUFFICIENT_EVIDENCE", "CONFLICTED", "ERROR")
_MODES = (
    "FACTUAL_INTERPRETATION", "GOAL_ANALYSIS", "BLOCKER_ANALYSIS",
    "OPTION_GENERATION", "UNCERTAINTY_ANALYSIS", "CONVERSATIONAL_SYNTHESIS",
)
# Keys the model must never smuggle into the durable/observable result. Dropped
# on validation so a "thinking"/scratchpad field can never become trusted state.
_FORBIDDEN_KEYS = (
    "thinking", "scratchpad", "chain_of_thought", "chainOfThought",
    "reasoning_text", "deliberation", "cot", "internal_monologue",
)

# ── Dedicated bounded role prompt (analysis only; no tools; typed contract) ──
REASONING_SYSTEM = """You are LILITH's REASONING component. You ANALYZE only. You never act.

Hard rules:
- You have NO tools, NO memory access, NO ability to run anything. Do not claim to.
- Use ONLY the bounded context provided in the user message. Do NOT invent facts,
  goals, tasks, drafts, statuses, deadlines, or provenance that are not given.
- Preserve epistemic honesty from the evidence: if a fact is UNKNOWN/not tracked,
  say so; if a belief is STALE, flag it and suggest refreshing; if CONFLICTED,
  surface the conflict and do not silently pick a side; VERIFIED is highest authority.
- You do NOT decide permissions. If an action would need approval or a connector
  that is unavailable or is prohibited, say so as a constraint — never as a decision.
- Candidate next steps are PROPOSALS ONLY; they are never executed by you.
- Respect the Executive: report the current focus / arbitration as given; do not
  override or change goal state.
- Never expose private chain-of-thought, token-by-token reasoning, or a scratchpad.

Output: return ONLY one JSON object (no prose around it, no code fences) with keys:
{
  "answer": string,               // natural, in-LILITH-voice reply for the user
  "interpretation": string,       // one-sentence observable conclusion (no deliberation)
  "outcome": "OK"|"INSUFFICIENT_EVIDENCE"|"CONFLICTED"|"ERROR",
  "assumptions": [string],
  "evidenceRefs": [string],       // refs to provided evidence (belief keys / ids)
  "uncertainties": [string],
  "conflicts": [string],
  "blockingConditions": [string],
  "candidateNextSteps": [ { "type": string, "description": string,
     "target": string|null, "rationaleSummary": string,
     "requiredCapabilities": [string], "requiresApproval": true|false,
     "blockedBy": [string] } ],
  "informationNeeded": [string],
  "answerIntent": string,
  "escalationNeeded": true|false,
  "confidenceBasis": string
}
PERSONA SEPARATION: your persona/tone may shape ONLY the wording of "answer".
Every other field must be factual, evidence-grounded, and persona-neutral.
The "answer" must never claim anything was created, saved, sent, approved, or
completed. Nothing is ever sent."""


# ── Bounded input rendering ─────────────────────────────────────────────────

def _clip(s, n=400):
    s = "" if s is None else (s if isinstance(s, str) else json.dumps(s, ensure_ascii=False))
    return s if len(s) <= n else (s[: n - 3] + "...")


def render_input_prompt(ri):
    """Render the bounded ReasoningInput as a compact text prompt. No raw dumps."""
    ri = ri or {}
    lines = []
    lines.append("REASONING MODE: %s" % ri.get("mode", "CONVERSATIONAL_SYNTHESIS"))
    lines.append("USER INTENT: %s" % _clip(ri.get("userIntent"), 500))
    if ri.get("explicitUserConstraints"):
        lines.append("USER CONSTRAINTS: %s" % _clip(ri.get("explicitUserConstraints"), 300))

    beliefs = ri.get("relevantBeliefs") or []
    lines.append("\nBELIEFS (durable, reconciled; %d shown):" % len(beliefs))
    if beliefs:
        for b in beliefs:
            lines.append(
                "- %s = %s [lifecycle=%s, epistemic=%s, confidence=%s, sources=%s]" % (
                    b.get("key") or b.get("predicate"), _clip(b.get("value"), 120),
                    b.get("lifecycle"), b.get("epistemic"), b.get("confidence"),
                    _clip(b.get("provenanceRefs"), 120)))
    else:
        lines.append("- (no beliefs provided for this focus)")

    if ri.get("currentFocus") or ri.get("goalCandidates"):
        lines.append("\nGOAL / EXECUTIVE STATE (durable; read-only):")
        foc = ri.get("currentFocus")
        lines.append("- current focus: %s" % (_clip(foc, 200) if foc else "none"))
        for gg in (ri.get("goalCandidates") or []):
            lines.append("- goal %s" % _clip(gg, 220))
    if ri.get("relevantTasks") or ri.get("relevantDrafts"):
        lines.append("\nPENDING DURABLE STATE:")
        for t in (ri.get("relevantTasks") or []):
            lines.append("- task %s" % _clip(t, 180))
        for d in (ri.get("relevantDrafts") or []):
            lines.append("- draft %s" % _clip(d, 180))

    if ri.get("policyVisibleConstraints"):
        lines.append("\nPOLICY-VISIBLE CONSTRAINTS (you do NOT decide permission):")
        for c in ri["policyVisibleConstraints"]:
            lines.append("- %s" % _clip(c, 160))
    if ri.get("capabilityAvailabilitySummary"):
        lines.append("CAPABILITY AVAILABILITY: %s" % _clip(ri.get("capabilityAvailabilitySummary"), 200))

    lines.append("\nAnalyze the above and return ONLY the JSON object described in your instructions.")
    return "\n".join(lines)


# ── Output parsing + strict validation (stdlib; no new dependency) ──────────

def _extract_json(text):
    if not isinstance(text, str) or not text.strip():
        return None
    s = text.strip()
    # tolerate ```json fenced blocks
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", s, re.DOTALL)
    if m:
        s = m.group(1)
    else:
        i, j = s.find("{"), s.rfind("}")
        if i == -1 or j == -1 or j <= i:
            return None
        s = s[i: j + 1]
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _as_str_list(v, limit=12):
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list):
        return []
    return [str(x) for x in v if x is not None][:limit]


def _norm_step(s):
    if not isinstance(s, dict):
        return None
    desc = s.get("description")
    if not isinstance(desc, str) or not desc.strip():
        return None
    return {
        "type": str(s.get("type") or "proposal"),
        "description": desc,
        "target": (str(s["target"]) if s.get("target") is not None else None),
        "rationaleSummary": str(s.get("rationaleSummary") or ""),
        "requiredCapabilities": _as_str_list(s.get("requiredCapabilities")),
        "requiresApproval": bool(s.get("requiresApproval", True)),
        "blockedBy": _as_str_list(s.get("blockedBy")),
    }


def validate_reasoning_result(obj, correlation_id, reasoning_input=None):
    """Return a normalized, whitelisted ReasoningResult dict, or None if invalid.
    Whitelisting drops any forbidden/CoT keys the model may have emitted."""
    if not isinstance(obj, dict):
        return None
    answer = obj.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        return None  # a reasoning result must carry a natural answer
    outcome = obj.get("outcome")
    if outcome not in _OUTCOMES:
        outcome = "OK"
    steps = []
    for s in (obj.get("candidateNextSteps") or []):
        ns = _norm_step(s)
        if ns is not None:
            steps.append(ns)
        if len(steps) >= 10:
            break
    ri = reasoning_input or {}
    result = {
        "schemaVersion": REASONING_SCHEMA_VERSION,
        "correlationId": correlation_id,
        "mode": ri.get("mode") or "CONVERSATIONAL_SYNTHESIS",
        "outcome": outcome,
        "interpretation": str(obj.get("interpretation") or "")[:600],
        "answer": answer.strip(),
        "assumptions": _as_str_list(obj.get("assumptions")),
        "evidenceRefs": _as_str_list(obj.get("evidenceRefs")),
        "uncertainties": _as_str_list(obj.get("uncertainties")),
        "conflicts": _as_str_list(obj.get("conflicts")),
        "blockingConditions": _as_str_list(obj.get("blockingConditions")),
        "candidateNextSteps": steps,
        "informationNeeded": _as_str_list(obj.get("informationNeeded")),
        "answerIntent": (str(obj["answerIntent"]) if obj.get("answerIntent") else None),
        "escalationNeeded": bool(obj.get("escalationNeeded", False)),
        "confidenceBasis": str(obj.get("confidenceBasis") or "unspecified"),
    }
    # Defensive: guarantee no forbidden/CoT key survives.
    for k in _FORBIDDEN_KEYS:
        result.pop(k, None)
    return result


# ── Safe, non-CoT trace ─────────────────────────────────────────────────────

def build_trace(reasoning_input, result, meta):
    ri = reasoning_input or {}
    r = result or {}
    return {
        "correlation_id": ri.get("correlationId"),
        "reasoning_mode": ri.get("mode"),
        "channel": ri.get("channel"),
        "input_summary": {
            "belief_count": len(ri.get("relevantBeliefs") or []),
            "goal_count": len(ri.get("goalCandidates") or []),
            "task_count": len(ri.get("relevantTasks") or []),
            "draft_count": len(ri.get("relevantDrafts") or []),
        },
        "evidence_ref_count": len(r.get("evidenceRefs") or []),
        "uncertainty_count": len(r.get("uncertainties") or []),
        "conflict_count": len(r.get("conflicts") or []),
        "candidate_count": len(r.get("candidateNextSteps") or []),
        "selected_answer_intent": r.get("answerIntent"),
        "outcome": r.get("outcome"),
        "duration_ms": (meta or {}).get("duration_ms"),
        "success": bool(result is not None),
        "fallback_reason": (meta or {}).get("fallback_reason"),
        "schema_version": REASONING_SCHEMA_VERSION,
    }


# ── Tool-less model call (indirections are patchable for offline tests) ─────

def _resolve_model():
    from gateway.run import _resolve_gateway_model
    return _resolve_gateway_model()


def _resolve_kwargs():
    from gateway.run import _resolve_runtime_agent_kwargs
    return _resolve_runtime_agent_kwargs()


def _construct_agent(**kwargs):
    from run_agent import AIAgent
    return AIAgent(**kwargs)


def reasoning_agent_kwargs():
    """The exact construction of the tool-less reasoning agent. Kept as a pure
    function so a test can assert the no-tool boundary without a network call."""
    kwargs = dict(_resolve_kwargs() or {})
    kwargs.update(
        model=_resolve_model(),
        quiet_mode=True,
        verbose_logging=False,
        skip_context_files=True,   # no context-file rummaging
        skip_memory=True,          # no curated-memory access
        load_soul_identity=True,   # persona affects ONLY the natural answer
        enabled_toolsets=[],       # PRIMARY no-tool boundary → zero tool schemas
        disabled_toolsets=None,
        ephemeral_system_prompt=REASONING_SYSTEM,
        max_iterations=1,          # secondary execution bound, NOT the isolation
    )
    return kwargs


def _default_model_call(prompt):
    agent = _construct_agent(**reasoning_agent_kwargs())
    try:
        res = agent.run_conversation(user_message=prompt)
        return (res or {}).get("final_response", "") or ""
    finally:
        try:
            agent.release_clients()
        except Exception:
            pass


def run_reasoning(reasoning_input, model_call=None):
    """Run one bounded, tool-less reasoning turn. Returns (result|None, trace).
    Never raises; any failure returns (None, trace) so the caller falls open."""
    model_call = model_call or _default_model_call
    corr = (reasoning_input or {}).get("correlationId")
    t0 = time.time()
    result = None
    fallback = None
    try:
        prompt = render_input_prompt(reasoning_input)
        raw = model_call(prompt)
        obj = _extract_json(raw)
        if obj is None:
            fallback = "unparseable_output"
        else:
            result = validate_reasoning_result(obj, corr, reasoning_input)
            if result is None:
                fallback = "schema_invalid"
    except Exception:
        logger.debug("reasoning: run_reasoning failed (fail-open)", exc_info=True)
        fallback = "exception"
    meta = {"duration_ms": round((time.time() - t0) * 1000), "fallback_reason": fallback}
    return result, build_trace(reasoning_input, result, meta)
