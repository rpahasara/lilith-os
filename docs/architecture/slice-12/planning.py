# -*- coding: utf-8 -*-
"""LILITH Slice 12 — Planning / Replanning V1 (proposal-only HOW layer).

Planning answers HOW a selected Goal / user intent *could* be reached. It is a
bounded, ephemeral, revisable PROPOSAL layer:

  planner PROPOSES · Policy GOVERNS · connectors PERFORM I/O · verifier PROVES

This module NEVER acts. Hard boundaries (enforced by tests + symbol absence):
  * no tools (enabled_toolsets=[] on the bounded planner call)
  * no POST / no /os writes / no draft or goal or task or belief mutation
  * no connector / shell / browser / email / filesystem / DB access
  * no approval decision, no Policy decision, no verification claim
  * no task materialization / no execution handoff
  * expected effects NEVER become truth; ALREADY_SATISFIED derives only from
    externally-owned source evidence read BEFORE planning
  * no hidden chain-of-thought in any output

Pipeline (grounder and validator are SEPARATE responsibilities):
    bounded PlanningInput
      -> deterministic template  OR  bounded no-tool LLM CandidateGraph
      -> deterministic Grounder / Normalizer   (resolve refs, map declared
         capabilities, attach source preconditions + execution requirements +
         expected effects + verification requirements, derive dependency refs,
         insert mandatory USER_DECISION / VERIFICATION structure, canonicalize)
      -> deterministic Validator   (schema / reference / capability-reference /
         dependency / boundedness / policy-compat / source-precondition verdicts;
         drops invalid; NEVER synthesizes new plan semantics)
      -> PlanSnapshot proposal  OR  typed failure

Only stdlib at module load; Hermes internals are imported lazily inside the
bounded model call so unit tests run fully offline.
"""
from __future__ import annotations

import json
import logging
import re
import time

try:
    from . import planning_capabilities as _caps
except Exception:  # staged flat dir (offline tests)
    import planning_capabilities as _caps

logger = logging.getLogger(__name__)

PLANNING_SCHEMA_VERSION = 1
DEFAULT_MAX_STEPS = 6
HARD_MAX_STEPS = 8

# PlanningResult.outcome
OUTCOME_PLAN_PROPOSED = "PLAN_PROPOSED"
OUTCOME_NO_VIABLE_PLAN = "NO_VIABLE_PLAN"
OUTCOME_USER_DECISION = "USER_DECISION_REQUIRED"
OUTCOME_INSUFFICIENT = "INSUFFICIENT_INFORMATION"
_OUTCOMES = (OUTCOME_PLAN_PROPOSED, OUTCOME_NO_VIABLE_PLAN,
             OUTCOME_USER_DECISION, OUTCOME_INSUFFICIENT)

# PlanStep.kind
K_INFO = "INFORMATION_GATHERING"
K_STATE = "STATE_CHANGE"
K_POLICY = "POLICY_GATE"
K_VERIFY = "VERIFICATION"
K_DECISION = "USER_DECISION"
_KINDS = (K_INFO, K_STATE, K_POLICY, K_VERIFY, K_DECISION)

# PlanStep.state (planning states; DISTINCT from Task/execution lifecycle)
S_PENDING = "PENDING"
S_READY = "READY"
S_BLOCKED = "BLOCKED"
S_UNEXECUTABLE = "UNEXECUTABLE"
S_INFO_NEEDED = "INFO_NEEDED"
S_ALREADY_SATISFIED = "ALREADY_SATISFIED"   # by current source evidence ONLY

# no-viable typed reasons
R_MISSING_CAPABILITY = "MISSING_CAPABILITY"
R_BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"
R_INSUFFICIENT_INFO = "INSUFFICIENT_INFORMATION"
R_UNRESOLVED_CONFLICT = "UNRESOLVED_CONFLICT"
R_USER_DECISION = "USER_DECISION_REQUIRED"
R_DEPENDENCY_UNSATISFIED = "DEPENDENCY_UNSATISFIED"
R_NO_CANDIDATE = "NO_CANDIDATE_GRAPH"

# Keys the model must never smuggle into the observable result (no CoT).
_FORBIDDEN_KEYS = (
    "thinking", "scratchpad", "chain_of_thought", "chainOfThought",
    "reasoning_text", "deliberation", "cot", "internal_monologue",
)

# ── Bounded planner role prompt (candidate graph only; no tools; typed) ──────
PLANNING_SYSTEM = """You are LILITH's PLANNING component. You PROPOSE a course of action only.
You never act, never send, never create anything, and you have NO tools.

You are given a single PLANNING SUBJECT and bounded, read-only context (durable
beliefs, the current goal/focus, pending tasks/drafts, and a NON-AUTHORITATIVE
capability view). Propose a small, dependency-aware CANDIDATE GRAPH of steps that
COULD move the subject toward its outcome.

Hard rules:
- Use ONLY the bounded context provided. Do NOT invent facts, ids, emails,
  capabilities, statuses, or drafts. Do NOT choose among goals — the subject is
  already selected for you.
- Reference ONLY capabilities present in the capability view. If the needed
  operation has no declared capability, say so with capabilityRef=null; do not
  invent one. Never propose sending email — no such capability exists.
- Steps are PROPOSALS. You never execute, approve, verify, or mark anything done.
- Keep it small (a handful of steps). Prefer ordering via dependsOn.
- Never expose private chain-of-thought or a scratchpad.

Output ONLY one JSON object (no prose, no code fences):
{
  "candidateSteps": [
    { "ref": "c1", "kind": "INFORMATION_GATHERING|STATE_CHANGE|POLICY_GATE|VERIFICATION|USER_DECISION",
      "title": string, "objective": string,
      "capabilityRef": string|null, "target": string|null,
      "dependsOn": [string], "rationale": string }
  ],
  "notes": string
}
Do NOT claim anything was created, saved, sent, approved, or completed."""


# ── small helpers ───────────────────────────────────────────────────────────

def _clip(s, n=240):
    s = "" if s is None else (s if isinstance(s, str) else json.dumps(s, ensure_ascii=False))
    return s if len(s) <= n else (s[: n - 3] + "...")


def _as_str_list(v, limit=12):
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list):
        return []
    return [str(x) for x in v if x is not None][:limit]


def _hash(*parts):
    import hashlib as _hl
    return _hl.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


# ── VerificationRequirement / ExecutionRequirement / preconditions builders ──

def _verification_requirement(expected_predicate, target_ref, source_owner, method):
    """A specification only. Planning performs NO verification (status DECLARED_ONLY)."""
    return {
        "expectedPredicate": expected_predicate,
        "targetRef": target_ref,
        "evidenceSourceOwner": source_owner,      # world | goals | tasks | drafts
        "observationMethod": method,
        "status": "DECLARED_ONLY",
    }


def _execution_requirements(descriptor):
    """Future-execution declarations (owners unavailable on the Router path)."""
    reqs = [
        {"kind": "CAPABILITY_REQUIRED",
         "detail": descriptor.get("capabilityRef"),
         "referenceValid": descriptor.get("supportStatus") == _caps.SUPPORT_ROUTER_SUPPORTED,
         "runtimeAvailability": descriptor.get("runtimeAvailability")},  # UNKNOWN
        {"kind": "POLICY_EVALUATION_REQUIRED",
         "policyCompatibility": descriptor.get("policyCompatibility"),  # not a decision
         "note": "authoritative Policy decision not available on this path"},
        {"kind": "APPROVAL_MAY_BE_REQUIRED",
         "note": "authorization owner decides at execution time; not satisfied here"},
        {"kind": "CONNECTOR_AVAILABILITY_REQUIRED",
         "detail": descriptor.get("declaredVia"),
         "runtimeAvailability": descriptor.get("runtimeAvailability")},  # UNKNOWN
        {"kind": "VERIFICATION_REQUIRED",
         "note": "verifier proves the effect; declared only"},
    ]
    return reqs


def _source_precondition(kind, owner, source_ref, expected_state, satisfied, required=True):
    return {
        "kind": kind,               # TARGET_EXISTS | DRAFT_STATE | BELIEF_STATE | GOAL_STATE
        "sourceOwner": owner,       # world | goals | tasks | drafts (real owners ONLY)
        "sourceRef": source_ref,
        "expectedState": expected_state,
        "satisfiedBySource": bool(satisfied),   # from evidence read BEFORE planning
        "required": bool(required),
    }


# ── Deterministic template (narrow: career follow-up subject) ───────────────

def deterministic_template(pi):
    """Return a CandidateGraph (with pre-grounded structure) for the narrow,
    supported career follow-up subject, else None. Uses ONLY real refs from the
    bounded PlanningInput. Never creates anything."""
    if not (pi or {}).get("templateEligible"):
        return None
    subj = pi.get("planningSubject") or {}
    target_ref = subj.get("targetRef")
    app_id = subj.get("targetAppId")
    if not app_id:
        return None
    ev = (pi.get("subjectEvidence") or {})
    followups = ev.get("unresolvedFollowups")   # list | None (lookup failed)
    count = len(followups) if isinstance(followups, list) else None
    ids = [d.get("draftId") for d in followups] if isinstance(followups, list) else []

    steps = []
    steps.append({
        "ref": "c1", "kind": K_INFO,
        "title": "Inspect the application target and existing follow-up drafts",
        "objective": "Confirm the target and any existing UNSENT follow-up drafts",
        "capabilityRef": None, "target": target_ref, "dependsOn": [],
        "rationale": "target + draft store already inspected this turn",
        "_alreadySatisfied": True,
    })
    if count is None:
        # draft-store lookup unavailable -> honest info gap, no create proposed
        steps.append({
            "ref": "c2", "kind": K_INFO,
            "title": "Re-check the draft store before any write",
            "objective": "Draft store was unavailable; a pre-execution re-check is required",
            "capabilityRef": None, "target": target_ref, "dependsOn": ["c1"],
            "rationale": "draft lookup failed this turn", "_infoNeeded": True,
        })
        return {"candidateSteps": steps, "notes": "draft store unavailable",
                "_templateOutcomeHint": OUTCOME_INSUFFICIENT}
    if count > 1:
        steps.append({
            "ref": "c2", "kind": K_DECISION,
            "title": "Reconcile duplicate unsent follow-up drafts",
            "objective": "Choose which of the %d existing unsent follow-up drafts to keep (%s)"
                         % (count, ", ".join([str(x) for x in ids])),
            "capabilityRef": None, "target": target_ref, "dependsOn": ["c1"],
            "rationale": "multiple unresolved follow-up drafts exist for this target",
            "_userDecision": True,
        })
        steps.append({
            "ref": "c3", "kind": K_STATE,
            "title": "Create a follow-up draft (only after reconciliation)",
            "objective": "Propose one reversible internal follow-up draft for the target",
            "capabilityRef": "career.create_followup_draft", "target": target_ref,
            "dependsOn": ["c2"],
            "rationale": "blocked until duplicates are reconciled",
            "_blockedByDuplicates": True,
        })
    elif count == 1:
        steps.append({
            "ref": "c2", "kind": K_STATE,
            "title": "A follow-up draft already exists",
            "objective": "An unsent follow-up draft already exists (%s); creating another is unnecessary"
                         % (ids[0] if ids else "existing"),
            "capabilityRef": "career.create_followup_draft", "target": target_ref,
            "dependsOn": ["c1"],
            "rationale": "one unresolved follow-up draft already present",
            "_alreadySatisfied": True,
        })
    else:  # count == 0
        steps.append({
            "ref": "c2", "kind": K_STATE,
            "title": "Create a follow-up draft",
            "objective": "Propose one reversible internal follow-up draft for the target",
            "capabilityRef": "career.create_followup_draft", "target": target_ref,
            "dependsOn": ["c1"],
            "rationale": "no unsent follow-up draft exists yet",
        })
    steps.append({
        "ref": "cV", "kind": K_VERIFY,
        "title": "Confirm a created follow-up draft exists for the target",
        "objective": "Declared verification requirement (a verifier proves it later)",
        "capabilityRef": None, "target": target_ref,
        "dependsOn": [s["ref"] for s in steps if s["kind"] == K_STATE][-1:] or ["c1"],
        "rationale": "expected effect must be independently proven, not assumed",
    })
    return {"candidateSteps": steps, "notes": "career.followup template"}


# ── Deterministic Grounder / Normalizer (SEPARATE from validation) ───────────

def ground_candidate_graph(candidate_graph, pi):
    """Resolve refs, map declared capabilities, attach source preconditions +
    execution requirements + expected effects + verification requirements, derive
    dependency step ids, insert mandatory deterministic structure, canonicalize
    ids/order. Deterministic. Does NOT decide validity verdicts."""
    subj = (pi or {}).get("planningSubject") or {}
    target_ref = subj.get("targetRef")
    ev = (pi.get("subjectEvidence") or {})
    followups = ev.get("unresolvedFollowups")
    dup_count = len(followups) if isinstance(followups, list) else None

    raw = list((candidate_graph or {}).get("candidateSteps") or [])
    # assign canonical stepIds in given order; keep a ref->stepId map
    ref_map = {}
    grounded = []
    for i, c in enumerate(raw[:HARD_MAX_STEPS], start=1):
        if not isinstance(c, dict):
            continue
        sid = "p%d" % i
        ref_map[str(c.get("ref") or sid)] = sid
        grounded.append((sid, c))

    steps = []
    for sid, c in grounded:
        kind = c.get("kind") if c.get("kind") in _KINDS else None
        cap_ref = c.get("capabilityRef")
        # coerce kind honestly
        if cap_ref and kind not in (K_STATE, K_POLICY):
            kind = K_STATE
        if not cap_ref and kind == K_STATE:
            kind = K_INFO
        if not kind:
            kind = K_STATE if cap_ref else K_INFO

        target = c.get("target") or target_ref
        deps = [ref_map[d] for d in (c.get("dependsOn") or []) if d in ref_map]

        step = {
            "stepId": sid,
            "kind": kind,
            "title": _clip(c.get("title") or c.get("objective") or kind, 160),
            "objective": _clip(c.get("objective") or "", 240),
            "target": target,
            "dependencyStepIds": deps,
            "requiredCapabilities": [cap_ref] if cap_ref else [],
            "preconditions": [],
            "executionRequirements": [],
            "expectedEffects": [],
            "verificationRequirement": None,
            "reversibilityClass": None,
            "idempotencyClass": None,
            "policyCompatibility": None,
            "state": S_PENDING,
            "rationale": {
                "purpose": _clip(c.get("rationale") or c.get("objective") or "", 200),
                "dependencyBasis": ("depends on " + ", ".join(deps)) if deps else "no prerequisites",
                "sourceRefs": _as_str_list(ev.get("sourceRefs")),
            },
        }

        if kind == K_STATE and cap_ref:
            d = _caps.describe(cap_ref)
            step["reversibilityClass"] = d.get("reversibilityClass")
            step["idempotencyClass"] = d.get("idempotencyClass")
            step["policyCompatibility"] = d.get("policyCompatibility")
            step["executionRequirements"] = _execution_requirements(d)
            step["expectedEffects"] = [{
                "description": "a %s effect for the target would be produced" % cap_ref,
                "targetRef": target,
                "effectPredicate": ("career_followup draft status=created"
                                    if cap_ref == "career.create_followup_draft"
                                    else "%s effect present" % cap_ref),
            }]
            step["verificationRequirement"] = _verification_requirement(
                step["expectedEffects"][0]["effectPredicate"], target, "drafts",
                d.get("verificationMethod") or "bounded read-back")
            # state from capability reference (NOT runtime availability / NOT policy allow)
            if _caps.is_known_prohibited(cap_ref):
                step["state"] = S_UNEXECUTABLE
            elif not _caps.is_executable_reference(cap_ref):
                step["state"] = S_UNEXECUTABLE       # unknown / not declared
            else:
                # duplicate-draft precondition (real source owner: drafts)
                dup_unmet = (cap_ref == "career.create_followup_draft"
                             and isinstance(dup_count, int) and dup_count > 1)
                step["preconditions"].append(_source_precondition(
                    "DRAFT_STATE", "drafts",
                    "/os/drafts?target_id=%s&kind=career_followup" % (subj.get("targetAppId") or ""),
                    "no unresolved duplicate follow-up drafts",
                    satisfied=not dup_unmet))
                if c.get("_alreadySatisfied"):
                    step["state"] = S_ALREADY_SATISFIED
                elif dup_unmet:
                    step["state"] = S_BLOCKED
                elif deps:
                    step["state"] = S_PENDING
                else:
                    step["state"] = S_READY
        elif kind == K_INFO:
            if c.get("_alreadySatisfied"):
                step["state"] = S_ALREADY_SATISFIED   # planner already read it
            elif c.get("_infoNeeded"):
                step["state"] = S_INFO_NEEDED
            else:
                step["state"] = S_READY
        elif kind == K_DECISION:
            step["state"] = S_BLOCKED   # awaits the user; not a failure
        elif kind == K_VERIFY:
            step["verificationRequirement"] = _verification_requirement(
                "expected effect present", target, "drafts", "bounded read-back")
            step["state"] = S_PENDING if deps else S_READY
        elif kind == K_POLICY:
            step["state"] = S_PENDING

        steps.append(step)

    # Deterministic dependency-resolution pass (steps are already in dependency
    # order: a dep always references an earlier ref). A PENDING STATE_CHANGE /
    # VERIFICATION becomes READY only when every dependency is ALREADY_SATISFIED
    # (or there are none); it becomes BLOCKED if any dependency is itself blocked /
    # unexecutable / awaiting a decision / needing info. Never upgrades a step the
    # capability/precondition layer already marked BLOCKED or UNEXECUTABLE.
    state_by_id = {s["stepId"]: s["state"] for s in steps}
    for s in steps:
        if s["kind"] in (K_STATE, K_VERIFY) and s["state"] == S_PENDING:
            deps = s["dependencyStepIds"]
            dep_states = [state_by_id.get(d) for d in deps]
            if any(ds in (S_BLOCKED, S_UNEXECUTABLE, S_INFO_NEEDED) for ds in dep_states):
                s["state"] = S_BLOCKED
            elif not deps or all(ds == S_ALREADY_SATISFIED for ds in dep_states):
                s["state"] = S_READY
            # else: a not-yet-done READY dependency remains -> stay PENDING
            state_by_id[s["stepId"]] = s["state"]

    dependency_edges = [[d, s["stepId"]] for s in steps for d in s["dependencyStepIds"]]
    return {
        "steps": steps,
        "dependencyEdges": dependency_edges,
        "subject": subj,
        "supportEvidenceRefs": _as_str_list(ev.get("sourceRefs")),
    }


# ── Deterministic Validator (verdicts + drops; NEVER synthesizes steps) ──────

def _has_cycle(steps):
    graph = {s["stepId"]: list(s.get("dependencyStepIds") or []) for s in steps}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {k: WHITE for k in graph}

    def visit(n):
        color[n] = GRAY
        for m in graph.get(n, []):
            if m not in color:
                continue
            if color[m] == GRAY:
                return True
            if color[m] == WHITE and visit(m):
                return True
        color[n] = BLACK
        return False

    return any(color[n] == WHITE and visit(n) for n in graph)


def validate_plan(grounded, pi, max_steps=DEFAULT_MAX_STEPS):
    """Return (plan|None, validation_summary, failure_reason). Pure verdicts and
    drops only — no new plan semantics are created here."""
    steps = list((grounded or {}).get("steps") or [])
    ids = {s["stepId"] for s in steps}
    summary = {
        "STRUCTURAL_STATUS": "PASS",
        "REFERENCE_STATUS": "PASS",
        "CAPABILITY_REFERENCE_STATUS": "PASS",
        "SOURCE_PRECONDITION_STATUS": "PASS",
        "POLICY_COMPATIBILITY_STATUS": "STATIC_ONLY",   # never claims Policy ALLOW
        "EXECUTION_REQUIREMENT_STATUS": "DECLARED",
    }
    cap = max(1, min(int(max_steps or DEFAULT_MAX_STEPS), HARD_MAX_STEPS))

    if not steps:
        summary["STRUCTURAL_STATUS"] = "FAIL"
        return None, summary, R_NO_CANDIDATE
    if len(steps) > cap:
        steps = steps[:cap]
        summary["STRUCTURAL_STATUS"] = "CLAMPED"
        ids = {s["stepId"] for s in steps}

    # reference: dependency refs must resolve to kept steps
    for s in steps:
        s["dependencyStepIds"] = [d for d in s.get("dependencyStepIds") or [] if d in ids]
        if any(d not in ids for d in (s.get("dependencyStepIds") or [])):
            summary["REFERENCE_STATUS"] = "FAIL"

    # dependency: no cycles
    if _has_cycle(steps):
        summary["STRUCTURAL_STATUS"] = "FAIL"
        return None, summary, R_DEPENDENCY_UNSATISFIED

    # capability-reference + policy compatibility (per STATE_CHANGE)
    unknown_cap = False
    prohibited = False
    for s in steps:
        if s["kind"] == K_STATE:
            crefs = s.get("requiredCapabilities") or []
            if not crefs:
                unknown_cap = True
            for cr in crefs:
                if _caps.is_known_prohibited(cr):
                    prohibited = True
                elif not _caps.is_reference_valid(cr):
                    unknown_cap = True
    if unknown_cap:
        summary["CAPABILITY_REFERENCE_STATUS"] = "UNKNOWN_PRESENT"
    if prohibited:
        summary["POLICY_COMPATIBILITY_STATUS"] = "KNOWN_PROHIBITED_PRESENT"

    # source-precondition status
    if any(not pc.get("satisfiedBySource") and pc.get("required")
           for s in steps for pc in (s.get("preconditions") or [])):
        summary["SOURCE_PRECONDITION_STATUS"] = "UNMET_PRESENT"

    plan = {
        "schemaVersion": PLANNING_SCHEMA_VERSION,
        "planSnapshotId": "ps." + _hash(
            (grounded.get("subject") or {}).get("targetRef"),
            json.dumps([s["stepId"] + ":" + s["kind"] + ":" + s["state"] for s in steps],
                       sort_keys=True),
            json.dumps(summary, sort_keys=True))[:16],
        "planningSubject": grounded.get("subject"),
        "planStatus": _plan_status(steps, summary),
        "steps": steps,
        "dependencyEdges": [[d, s["stepId"]] for s in steps for d in s["dependencyStepIds"]],
        "supportEvidenceRefs": grounded.get("supportEvidenceRefs") or [],
    }
    return plan, summary, None


def _actionable(steps):
    return [s for s in steps if s["kind"] in (K_STATE,)]


def _plan_status(steps, summary):
    acts = _actionable(steps)
    if any(s["kind"] == K_DECISION and s["state"] == S_BLOCKED for s in steps):
        return "USER_DECISION_REQUIRED"
    if acts and all(s["state"] in (S_UNEXECUTABLE,) for s in acts):
        return "BLOCKED"
    if any(s["state"] == S_INFO_NEEDED for s in steps) and not any(
            s["state"] in (S_READY, S_ALREADY_SATISFIED) for s in acts):
        return "NEEDS_INFORMATION"
    if acts and any(s["state"] in (S_READY, S_ALREADY_SATISFIED, S_BLOCKED, S_PENDING) for s in acts):
        return "PROPOSED"
    if not acts:
        # info/verify-only plan is still a (weak) proposal if anything READY
        if any(s["state"] in (S_READY, S_ALREADY_SATISFIED) for s in steps):
            return "PROPOSED"
        return "NEEDS_INFORMATION"
    return "PROPOSED"


# ── Outcome + deterministic natural answer (no overclaim, no CoT) ────────────

def _compose_answer(plan, summary):
    subj = plan.get("planningSubject") or {}
    label = subj.get("targetRef") or subj.get("userIntentRef") or "this subject"
    lines = ["Here is a proposed plan for %s. Nothing has been created, sent, or approved — this is a proposal only." % label]
    for s in plan["steps"]:
        tag = {
            S_ALREADY_SATISFIED: "already satisfied by current state",
            S_BLOCKED: "blocked",
            S_UNEXECUTABLE: "not executable on this path",
            S_INFO_NEEDED: "needs information",
            S_READY: "ready to propose",
            S_PENDING: "pending prerequisites",
        }.get(s["state"], s["state"].lower())
        lines.append("- [%s] %s (%s)" % (s["kind"], s["title"], tag))
    if plan["planStatus"] == "USER_DECISION_REQUIRED":
        lines.append("A decision from you is required before any write can be proposed.")
    if summary.get("CAPABILITY_REFERENCE_STATUS") == "UNKNOWN_PRESENT":
        lines.append("One or more steps need a capability that is not available on this path.")
    if summary.get("POLICY_COMPATIBILITY_STATUS") == "KNOWN_PROHIBITED_PRESENT":
        lines.append("One step is a prohibited action and cannot be executed.")
    return "\n".join(lines)


def _no_viable_answer(reason):
    msgs = {
        R_MISSING_CAPABILITY: "I can't propose a viable plan for that here — it needs a capability that isn't available on this path.",
        R_BLOCKED_BY_POLICY: "I can't propose that — it would require a prohibited action.",
        R_INSUFFICIENT_INFO: "I don't have enough grounded information to propose a plan for that yet.",
        R_NO_CANDIDATE: "I couldn't form a grounded plan for that.",
        R_DEPENDENCY_UNSATISFIED: "I couldn't form a consistent step ordering for that.",
    }
    return msgs.get(reason, "I couldn't form a viable plan for that right now.")


# ── bounded tool-less model call (indirections patchable for offline tests) ──

def _resolve_model():
    from gateway.run import _resolve_gateway_model
    return _resolve_gateway_model()


def _resolve_kwargs():
    from gateway.run import _resolve_runtime_agent_kwargs
    return _resolve_runtime_agent_kwargs()


def _construct_agent(**kwargs):
    from run_agent import AIAgent
    return AIAgent(**kwargs)


def planning_agent_kwargs():
    """Exact construction of the tool-less planner agent (kept pure so a test can
    assert the no-tool boundary without a network call)."""
    kwargs = dict(_resolve_kwargs() or {})
    kwargs.update(
        model=_resolve_model(),
        quiet_mode=True,
        verbose_logging=False,
        skip_context_files=True,
        skip_memory=True,
        load_soul_identity=False,     # candidate graph is persona-neutral
        enabled_toolsets=[],          # PRIMARY no-tool boundary
        disabled_toolsets=None,
        ephemeral_system_prompt=PLANNING_SYSTEM,
        max_iterations=1,
    )
    return kwargs


def _default_model_call(prompt):
    agent = _construct_agent(**planning_agent_kwargs())
    try:
        res = agent.run_conversation(user_message=prompt)
        return (res or {}).get("final_response", "") or ""
    finally:
        try:
            agent.release_clients()
        except Exception:
            pass


def _extract_json(text):
    if not isinstance(text, str) or not text.strip():
        return None
    s = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", s, re.DOTALL)
    if m:
        s = m.group(1)
    else:
        i, j = s.find("{"), s.rfind("}")
        if i == -1 or j == -1 or j <= i:
            return None
        s = s[i:j + 1]
    try:
        obj = json.loads(s)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    for k in _FORBIDDEN_KEYS:
        obj.pop(k, None)
    return obj


def render_planning_input(pi):
    pi = pi or {}
    subj = pi.get("planningSubject") or {}
    lines = ["PLANNING SUBJECT: kind=%s target=%s goal=%s intent=%s" % (
        subj.get("kind"), subj.get("targetRef"), subj.get("goalRef"),
        _clip(subj.get("userIntentRef"), 160))]
    if pi.get("explicitUserConstraints"):
        lines.append("USER CONSTRAINTS: %s" % _clip(pi.get("explicitUserConstraints"), 200))
    if pi.get("currentFocus"):
        lines.append("EXECUTIVE FOCUS (read-only): %s" % _clip(pi.get("currentFocus"), 200))
    for b in (pi.get("relevantBeliefs") or [])[:8]:
        lines.append("- belief %s" % _clip(b, 160))
    for d in (pi.get("relevantDrafts") or [])[:8]:
        lines.append("- draft %s" % _clip(d, 160))
    cv = pi.get("capabilityView") or {}
    lines.append("CAPABILITY VIEW (non-authoritative): %s" % _clip(
        [c.get("capabilityRef") + ":" + c.get("supportStatus") for c in cv.get("capabilities") or []], 300))
    lines.append("\nReturn ONLY the candidate-graph JSON object described in your instructions.")
    return "\n".join(lines)


def _llm_candidate_graph(pi, model_call):
    try:
        raw = model_call(render_planning_input(pi))
        obj = _extract_json(raw)
        if not obj or not isinstance(obj.get("candidateSteps"), list):
            return None
        return obj
    except Exception:
        logger.debug("planning: llm candidate graph failed (fail-open)", exc_info=True)
        return None


# ── Orchestration ───────────────────────────────────────────────────────────

def run_planning(planning_input, model_call=None, candidate_graph=None, max_steps=None):
    """Run one bounded planning turn. Returns (PlanningResult, trace). Never
    raises; any failure returns a typed non-fatal result so the caller falls open."""
    corr = (planning_input or {}).get("correlationId")
    t0 = time.time()
    mx = max_steps or (planning_input or {}).get("maxSteps") or DEFAULT_MAX_STEPS
    fallback = None
    cg_source = None
    plan = None
    summary = None
    failure = None
    try:
        cg = candidate_graph
        if cg is not None:
            cg_source = "injected"
        else:
            cg = deterministic_template(planning_input)
            if cg is not None:
                cg_source = "template"
            elif model_call is not None:
                cg = _llm_candidate_graph(planning_input, model_call)
                cg_source = "llm" if cg is not None else None
        if cg is None:
            fallback = "no_candidate_graph"
            result = _result(corr, OUTCOME_INSUFFICIENT, _no_viable_answer(R_INSUFFICIENT_INFO),
                             None, [R_INSUFFICIENT_INFO], planning_input, None)
            return result, build_trace(planning_input, result, None, cg_source, fallback, t0)

        grounded = ground_candidate_graph(cg, planning_input)
        plan, summary, failure = validate_plan(grounded, planning_input, max_steps=mx)
        if plan is None:
            reason = failure or R_NO_CANDIDATE
            result = _result(corr, OUTCOME_NO_VIABLE_PLAN, _no_viable_answer(reason),
                             None, [reason], planning_input, summary)
            return result, build_trace(planning_input, result, plan, cg_source, reason, t0)

        outcome, blockers = _outcome_for(plan, summary)
        if outcome == OUTCOME_PLAN_PROPOSED:
            answer = _compose_answer(plan, summary)
        elif outcome == OUTCOME_USER_DECISION:
            answer = _compose_answer(plan, summary)
        else:
            answer = _no_viable_answer(blockers[0] if blockers else R_INSUFFICIENT_INFO)
        result = _result(corr, outcome, answer, plan, blockers, planning_input, summary)
        return result, build_trace(planning_input, result, plan, cg_source, None, t0)
    except Exception:
        logger.debug("planning: run_planning failed (fail-open)", exc_info=True)
        result = _result(corr, OUTCOME_INSUFFICIENT, _no_viable_answer(R_INSUFFICIENT_INFO),
                         None, [R_INSUFFICIENT_INFO], planning_input, summary)
        return result, build_trace(planning_input, result, plan, cg_source, "exception", t0)


def _outcome_for(plan, summary):
    steps = plan["steps"]
    acts = _actionable(steps)
    blockers = []
    if any(s["kind"] == K_DECISION and s["state"] == S_BLOCKED for s in steps):
        blockers.append(R_USER_DECISION)
        return OUTCOME_USER_DECISION, blockers
    if acts and all(s["state"] == S_UNEXECUTABLE for s in acts):
        if summary.get("POLICY_COMPATIBILITY_STATUS") == "KNOWN_PROHIBITED_PRESENT":
            blockers.append(R_BLOCKED_BY_POLICY)
        else:
            blockers.append(R_MISSING_CAPABILITY)
        return OUTCOME_NO_VIABLE_PLAN, blockers
    if plan["planStatus"] == "NEEDS_INFORMATION":
        blockers.append(R_INSUFFICIENT_INFO)
        return OUTCOME_INSUFFICIENT, blockers
    return OUTCOME_PLAN_PROPOSED, blockers


def _result(corr, outcome, answer, plan, blockers, pi, summary):
    info_needed = []
    ev_refs = []
    if plan:
        ev_refs = plan.get("supportEvidenceRefs") or []
        info_needed = [s["title"] for s in plan["steps"] if s["state"] == S_INFO_NEEDED]
    return {
        "schemaVersion": PLANNING_SCHEMA_VERSION,
        "correlationId": corr,
        "mode": "PLANNING",
        "outcome": outcome if outcome in _OUTCOMES else OUTCOME_INSUFFICIENT,
        "answer": answer,
        "planSnapshot": plan,
        "blockers": _as_str_list(blockers),
        "informationNeeded": _as_str_list(info_needed),
        "evidenceRefs": _as_str_list(ev_refs),
        "validationSummary": summary or {},
        "traceMetadata": {"schemaVersion": PLANNING_SCHEMA_VERSION},
    }


def build_trace(pi, result, plan, cg_source, fallback, t0):
    pi = pi or {}
    r = result or {}
    subj = (pi.get("planningSubject") or {})
    steps = (plan or {}).get("steps") or []
    return {
        "correlation_id": pi.get("correlationId"),
        "subject_kind": subj.get("kind"),
        "subject_target": subj.get("targetRef"),
        "goal_ref": subj.get("goalRef"),
        "candidate_source": cg_source,
        "outcome": r.get("outcome"),
        "plan_snapshot_id": (plan or {}).get("planSnapshotId"),
        "plan_status": (plan or {}).get("planStatus"),
        "step_count": len(steps),
        "dependency_count": len((plan or {}).get("dependencyEdges") or []),
        "blocked_steps": sum(1 for s in steps if s["state"] == S_BLOCKED),
        "unexecutable_steps": sum(1 for s in steps if s["state"] == S_UNEXECUTABLE),
        "required_capabilities": sorted({c for s in steps for c in (s.get("requiredCapabilities") or [])}),
        "validation_summary": r.get("validationSummary"),
        "source_refs_count": len(r.get("evidenceRefs") or []),
        "duration_ms": round((time.time() - t0) * 1000),
        "fallback_reason": fallback,
        "schema_version": PLANNING_SCHEMA_VERSION,
        "ts": round(time.time(), 3),
    }


# ── Replanning (DESIGN + FIXTURE ONLY — requires an explicit priorPlan) ──────

def run_replanning(replanning_input):
    """Future/fixture-only. TRUE replanning requires an explicit priorPlan; without
    one this is Planning, not Replanning, and is refused structurally. No live
    executor exists on the Router path, so this is exercised by tests only."""
    ri = replanning_input or {}
    prior = ri.get("priorPlan")
    if not prior or not isinstance(prior, dict) or not prior.get("planSnapshotId"):
        return {
            "outcome": "NOT_REPLANNING_WITHOUT_PRIOR_PLAN",
            "priorPlanId": None,
            "note": "no priorPlan supplied -> this is Planning, not Replanning",
        }
    verified = list(ri.get("verifiedCompletedSteps") or [])
    failed = ri.get("failedStep")
    invalidated = list(ri.get("invalidatedPreconditions") or [])
    reasons = list(ri.get("replanReasonCodes") or [])
    if failed:
        reasons.append("STEP_EXECUTION_FAILED")
    prior_steps = {s.get("stepId"): s for s in prior.get("steps") or []}
    verified_ids = {v for v in verified if v in prior_steps}
    # preserve verified (esp. irreversible) completed steps; never duplicate them
    preserved = sorted(verified_ids)
    # invalidate only downstream of the failure / invalidated preconditions
    invalid_ids = set()
    if failed and failed in prior_steps:
        # steps depending (transitively) on the failed step are invalidated
        changed = True
        invalid_ids.add(failed)
        while changed:
            changed = False
            for sid, s in prior_steps.items():
                if sid in invalid_ids:
                    continue
                if any(d in invalid_ids for d in s.get("dependencyStepIds") or []):
                    invalid_ids.add(sid)
                    changed = True
        invalid_ids.discard(failed)
    return {
        "outcome": "REPLAN_PROPOSED",
        "priorPlanId": prior.get("planSnapshotId"),
        "priorRevision": prior.get("revision", 1),
        "newRevision": prior.get("revision", 1) + 1,
        "preservedSteps": preserved,
        "invalidatedSteps": sorted(invalid_ids),
        "removedSteps": [],
        "newSteps": [],
        "replanReasonCodes": reasons,
        "invalidatedPreconditions": invalidated,
    }
