# -*- coding: utf-8 -*-
"""LILITH Slice 13 — Ethical Deliberation V1 (advisory only).

Ethics may deliberate. Policy governs. This module SURFACES ethically relevant
concerns, value tensions, information-needs and advisory recommendations for a
single EthicalSubject. It NEVER:

  * returns ALLOW / DENY / approved / safe / legal / compliant
  * grants, denies, downgrades or overrides Policy
  * executes, approves, verifies, or mutates goals / plans / beliefs / drafts
  * fabricates a Policy or legal verdict, a data-sensitivity label, a third-party
    identity, or a user preference
  * re-litigates a hard known prohibition
  * uses tools / connectors / POST / shell / DB
  * emits a numeric or ordinal moral score, or a hidden utility

Pipeline (grounder and validator are SEPARATE responsibilities):
    bounded EthicalInput (with TURN evidence)
      -> deterministic principle applicability (three-way)
      -> deterministic concern triggers  OR  bounded no-tool LLM candidates
      -> deterministic Grounder   (resolve TURN/source refs, attach principle
         refs + resolution conditions, canonicalise ids; drop unresolved)
      -> deterministic Validator  (schema / principle-exists / source-refs-exist /
         no fabricated preference|third-party|privacy-class|harm|Policy|legal;
         bound counts; drops invalid; NEVER synthesises concerns)
      -> EthicalResult (answer rendered deterministically FROM the typed result)

Only stdlib at module load; Hermes internals are imported lazily inside the
optional bounded model call so unit tests run fully offline. Live posture:
DETERMINISTIC ONLY (model_call=None); the LLM candidate path is built + tested
but not wired live (mirrors Slice 12).
"""
from __future__ import annotations

import json
import logging
import re
import time

try:
    from . import ethics_principles as _pr
except Exception:  # staged flat dir (offline tests)
    import ethics_principles as _pr
try:
    from . import planning_capabilities as _caps
except Exception:
    import planning_capabilities as _caps

logger = logging.getLogger(__name__)

ETHICS_SCHEMA_VERSION = 1
DEFAULT_MAX_CONCERNS = 4
DEFAULT_MAX_TENSIONS = 3

# ── Outcomes (NO ALLOW/DENY/SAFE/APPROVED/LEGAL/COMPLIANT) ────────────────────
OUT_NO_CONCERN = "NO_GROUNDED_CONCERN_IDENTIFIED"
OUT_CONCERNS = "CONCERNS_IDENTIFIED"
OUT_HUMAN_REVIEW = "HUMAN_REVIEW_RECOMMENDED"
OUT_INSUFFICIENT = "INSUFFICIENT_CONTEXT"
OUT_SKIPPED_PROHIBITION = "SKIPPED_KNOWN_PROHIBITION"
_OUTCOMES = (OUT_NO_CONCERN, OUT_CONCERNS, OUT_HUMAN_REVIEW,
             OUT_INSUFFICIENT, OUT_SKIPPED_PROHIBITION)

# ── Concern taxonomy (correction 20) ─────────────────────────────────────────
C_CONSTRAINT_CONFLICT = "USER_CONSTRAINT_CONFLICT"
C_CONSENT_UNCLEAR = "EXECUTION_CONSENT_UNCLEAR"
C_PRIVACY = "PRIVACY_EXPOSURE"
C_SCOPE = "UNNECESSARY_SCOPE"
C_IRREVERSIBLE = "IRREVERSIBILITY_UNDER_UNCERTAINTY"
C_THIRD_PARTY = "THIRD_PARTY_IMPACT"
_CONCERN_TYPES = (C_CONSTRAINT_CONFLICT, C_CONSENT_UNCLEAR, C_PRIVACY,
                  C_SCOPE, C_IRREVERSIBLE, C_THIRD_PARTY)

# concernType -> the declared principle ids it may cite (validator-enforced)
CONCERN_PRINCIPLES = {
    C_CONSTRAINT_CONFLICT: [_pr.P_USER_AUTONOMY],
    C_CONSENT_UNCLEAR: [_pr.P_USER_AUTONOMY],
    C_PRIVACY: [_pr.P_PRIVACY],
    C_SCOPE: [_pr.P_PROPORTIONALITY],
    C_IRREVERSIBLE: [_pr.P_NON_MALEFICENCE],
    C_THIRD_PARTY: [_pr.P_NON_MALEFICENCE, _pr.P_USER_AUTONOMY],
}

# resolution conditions per concern type (deterministic; attached by grounder)
_RESOLUTIONS = {
    C_CONSTRAINT_CONFLICT: ["honour the stated constraint, or get the user's explicit go-ahead to override it"],
    C_CONSENT_UNCLEAR: ["get the user's explicit confirmation before acting"],
    C_PRIVACY: ["narrow the disclosed data to what the goal needs", "confirm the user wants that data included"],
    C_SCOPE: ["narrow the action to the subject's scope", "confirm the wider scope is intended"],
    C_IRREVERSIBLE: ["establish the uncertain precondition first", "prefer a reversible alternative", "get explicit human review before proceeding"],
    C_THIRD_PARTY: ["clarify who the affected party is", "confirm the user authorises contacting/affecting them"],
}

# advisory recommendation per concern type (proposals only)
_RECOMMENDATIONS = {
    C_CONSTRAINT_CONFLICT: "request_user_confirmation",
    C_CONSENT_UNCLEAR: "request_user_confirmation",
    C_PRIVACY: "minimize_disclosed_data",
    C_SCOPE: "narrow_scope",
    C_IRREVERSIBLE: "prefer_reversible_step",
    C_THIRD_PARTY: "clarify_affected_party",
}

# cause codes (source-owned epistemics; NOT a severity/uncertainty scale)
CC_CONSTRAINT_CONFLICT = "CONSTRAINT_CONFLICT"
CC_BYPASS = "BYPASS_CONFIRMATION_REQUESTED"
CC_PRIVATE_DATA = "USER_ASSERTED_PRIVATE_DATA"
CC_OVER_BROAD = "OVER_BROAD_DATA_SCOPE"
CC_MULTI_TARGET = "MULTI_TARGET_SCOPE"
CC_IRREVERSIBLE = "IRREVERSIBLE_IMPACT"
CC_WORLD_STALE = "WORLD_STALE"
CC_WORLD_CONFLICTED = "WORLD_CONFLICTED"
CC_TARGET_UNKNOWN = "TARGET_UNKNOWN"
CC_RECIPIENT_UNRESOLVED = "RECIPIENT_UNRESOLVED"
CC_THIRD_PARTY = "THIRD_PARTY_ROLE_PRESENT"

# information-need codes
IN_TARGET_UNKNOWN = "which target/application are you asking about?"
IN_DATA_SCOPE = "which specific data fields would be involved?"
IN_RECIPIENT = "who exactly is the affected party?"
IN_SUBJECT = "what action or decision would you like me to weigh?"

# failure taxonomy (never ETHICALLY_WRONG=true)
F_CONTEXT_INSUFFICIENT = "ETHICAL_CONTEXT_INSUFFICIENT"
F_SUBJECT_UNRESOLVED = "SUBJECT_UNRESOLVED"
F_EXCEPTION = "exception"

# real source owners a concern ref may resolve to
_SOURCE_OWNERS = ("TURN", "world", "goals", "tasks", "drafts")

# vocabulary Ethics must never emit (Policy / legal / safety verdicts)
_BANNED_TERMS = ("allow", "deny", "denied", "approved", "approve", "authoris",
                 "authoriz", "permitted", "permission granted", "safe to",
                 "is safe", "legal", "illegal", "compliant", "compliance ok",
                 "gdpr", "prohibited action is fine")

# Keys the model must never smuggle into observable output (no CoT).
_FORBIDDEN_KEYS = (
    "thinking", "scratchpad", "chain_of_thought", "chainOfThought",
    "reasoning_text", "deliberation", "cot", "internal_monologue", "rationale_chain",
)


# ── small helpers (mirror planning.py idioms) ────────────────────────────────

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


def _te(ei):
    te = (ei or {}).get("turnEvidence")
    return te if isinstance(te, dict) else {}


def _action(ei):
    a = _te(ei).get("referencedAction")
    return a if isinstance(a, dict) else None


# ── uncertainty from bounded World evidence (real refs; no invented scale) ────

def _uncertainty_signals(ei):
    """Return [(causeCode, sourceRef)] from real bounded evidence: CONFLICTED /
    STALE / UNKNOWN beliefs, and an unknown action target. Never a numeric score."""
    out = []
    beliefs = (ei or {}).get("relevantBeliefs") or []
    for i, b in enumerate(beliefs[:8]):
        s = b if isinstance(b, str) else json.dumps(b, ensure_ascii=False)
        low = s.lower()
        if "epistemic=conflicted" in low or "conflicted" == low.strip():
            out.append((CC_WORLD_CONFLICTED, "world:relevantBelief:%d" % i))
        elif "lifecycle=stale" in low or "epistemic=stale" in low:
            out.append((CC_WORLD_STALE, "world:relevantBelief:%d" % i))
        elif "epistemic=unknown" in low:
            out.append((CC_WORLD_STALE, "world:relevantBelief:%d" % i))
    # unknown target: action names a target neither grounded in refs nor resolvable
    a = _action(ei)
    if a and a.get("target") and not _te(ei).get("referencedTargets"):
        out.append((CC_TARGET_UNKNOWN, a.get("ref") or "turn:action"))
    return out


def _discloses(a):
    return bool(a) and a.get("verb") in ("disclose", "send_external")


def _communicates_third_party(a):
    return bool(a) and a.get("verb") in ("disclose", "send_external", "contact")


# ── deterministic principle applicability (three-way) ────────────────────────

def principle_applicability(ei):
    """Deterministic three-way applicability per declared principle. Missing
    evidence is INSUFFICIENT_EVIDENCE, never silently NOT_APPLICABLE."""
    te = _te(ei)
    a = _action(ei)
    constraints = te.get("explicitConstraints") or []
    dscope = te.get("referencedDataScope") or []
    tparties = te.get("referencedThirdPartyRoles") or []
    subj_scope = te.get("subjectScope") or {}
    act_scope = te.get("actionScope") or {}
    unc = _uncertainty_signals(ei)
    third_comm = bool(tparties) and _communicates_third_party(a)

    out = {}

    # USER_AUTONOMY
    if constraints or (a and a.get("bypassConfirmation")) or third_comm:
        out[_pr.P_USER_AUTONOMY] = (_pr.APPLIC_APPLICABLE, "explicit constraint / bypass / third-party communication")
    else:
        out[_pr.P_USER_AUTONOMY] = (_pr.APPLIC_NOT_APPLICABLE, "no consent/autonomy signal in the turn")

    # PRIVACY_MINIMIZATION
    if _discloses(a) and dscope:
        out[_pr.P_PRIVACY] = (_pr.APPLIC_APPLICABLE, "disclosure action + user-asserted/typed data scope")
    elif _discloses(a) and not dscope:
        out[_pr.P_PRIVACY] = (_pr.APPLIC_INSUFFICIENT, "disclosure action but data scope unknown")
    else:
        out[_pr.P_PRIVACY] = (_pr.APPLIC_NOT_APPLICABLE, "no disclosure of personal data")

    # NON_MALEFICENCE
    irreversible = bool(a) and a.get("impactClass") == "IRREVERSIBLE_DELETION"
    if (irreversible and unc) or third_comm:
        out[_pr.P_NON_MALEFICENCE] = (_pr.APPLIC_APPLICABLE, "irreversible impact under uncertainty / third-party impact")
    elif irreversible and not unc:
        out[_pr.P_NON_MALEFICENCE] = (_pr.APPLIC_INSUFFICIENT, "irreversible impact but no uncertain precondition established")
    else:
        out[_pr.P_NON_MALEFICENCE] = (_pr.APPLIC_NOT_APPLICABLE, "no concrete irreversible/harmful impact class")

    # PROPORTIONALITY
    sc, ac = subj_scope.get("targetCount"), act_scope.get("targetCount")
    if isinstance(sc, int) and isinstance(ac, int):
        if ac > sc:
            out[_pr.P_PROPORTIONALITY] = (_pr.APPLIC_APPLICABLE, "action scope exceeds subject scope")
        else:
            out[_pr.P_PROPORTIONALITY] = (_pr.APPLIC_NOT_APPLICABLE, "action scope within subject scope")
    elif isinstance(ac, int) and not isinstance(sc, int):
        out[_pr.P_PROPORTIONALITY] = (_pr.APPLIC_INSUFFICIENT, "action scope present but subject scope unknown")
    else:
        out[_pr.P_PROPORTIONALITY] = (_pr.APPLIC_NOT_APPLICABLE, "no comparable typed scope")

    return out


def _applicability_list(applic):
    return [{"principleId": pid, "status": st, "basis": basis, "sourceRefs": []}
            for pid, (st, basis) in applic.items()]


# ── deterministic concern triggers (each grounded in real refs) ──────────────

def deterministic_concern_candidates(ei, applic):
    """Return raw concern candidates from evidence. A candidate is emitted only
    for a principle whose applicability is APPLICABLE. Never fabricates refs."""
    te = _te(ei)
    a = _action(ei)
    constraints = te.get("explicitConstraints") or []
    dscope = te.get("referencedDataScope") or []
    tparties = te.get("referencedThirdPartyRoles") or []
    act_scope = te.get("actionScope") or {}
    unc = _uncertainty_signals(ei)
    cands = []

    def ap(pid):
        return applic.get(pid, (_pr.APPLIC_NOT_APPLICABLE, ""))[0] == _pr.APPLIC_APPLICABLE

    # USER_CONSTRAINT_CONFLICT — a standing constraint the action would violate
    if ap(_pr.P_USER_AUTONOMY) and constraints and a:
        for c in constraints:
            kind = c.get("kind")
            conflict = (
                (kind == "NO_CONTACT" and _communicates_third_party(a))
                or (kind == "NO_SHARE_OR_SEND" and a.get("verb") in ("disclose", "send_external"))
            )
            if conflict:
                cands.append({
                    "concernType": C_CONSTRAINT_CONFLICT,
                    "sourceRefs": [c.get("ref"), a.get("ref")],
                    "causeCodes": [CC_CONSTRAINT_CONFLICT],
                    "rationaleSummary": "the contemplated action conflicts with your stated constraint (%s)"
                                        % _clip(c.get("text"), 80),
                    "sourceScope": "USER_SPECIFIC",
                })
                break

    # EXECUTION_CONSENT_UNCLEAR — explicit bypass-confirmation framing only
    if ap(_pr.P_USER_AUTONOMY) and a and a.get("bypassConfirmation"):
        cands.append({
            "concernType": C_CONSENT_UNCLEAR,
            "sourceRefs": [a.get("ref")],
            "causeCodes": [CC_BYPASS],
            "rationaleSummary": "the request is about acting without your explicit confirmation first",
        })

    # PRIVACY_EXPOSURE — disclosure + real data scope
    if ap(_pr.P_PRIVACY) and dscope and a:
        codes = [CC_PRIVATE_DATA]
        if any(d.get("overBroad") for d in dscope):
            codes.append(CC_OVER_BROAD)
        cands.append({
            "concernType": C_PRIVACY,
            "sourceRefs": [d.get("ref") for d in dscope] + [a.get("ref")],
            "causeCodes": codes,
            "rationaleSummary": "the action would disclose personal data you flagged (%s)"
                                % _clip(", ".join(d.get("assertion", "") for d in dscope), 80),
            "sourceScope": "USER_SPECIFIC",
        })

    # UNNECESSARY_SCOPE — comparable typed scope, action exceeds subject
    if ap(_pr.P_PROPORTIONALITY):
        cands.append({
            "concernType": C_SCOPE,
            "sourceRefs": [act_scope.get("ref"), te.get("subjectScope", {}).get("ref")],
            "causeCodes": [CC_MULTI_TARGET],
            "rationaleSummary": "the action's scope (%s targets) is wider than the subject's (%s)"
                                % (act_scope.get("targetCount"),
                                   te.get("subjectScope", {}).get("targetCount")),
        })

    # IRREVERSIBILITY_UNDER_UNCERTAINTY — irreversible impact + real uncertainty
    if ap(_pr.P_NON_MALEFICENCE) and a and a.get("impactClass") == "IRREVERSIBLE_DELETION" and unc:
        cands.append({
            "concernType": C_IRREVERSIBLE,
            "sourceRefs": [a.get("ref")] + [ref for (_c, ref) in unc],
            "causeCodes": [CC_IRREVERSIBLE] + [c for (c, _r) in unc],
            "rationaleSummary": "this is an irreversible action while a relevant fact is stale/conflicted/unknown",
        })

    # THIRD_PARTY_IMPACT — a real role + a concrete communication/impact action
    if tparties and _communicates_third_party(a):
        codes = [CC_THIRD_PARTY]
        if any(not t.get("identityResolved") for t in tparties):
            codes.append(CC_RECIPIENT_UNRESOLVED)
        cands.append({
            "concernType": C_THIRD_PARTY,
            "sourceRefs": [t.get("ref") for t in tparties] + [a.get("ref")],
            "causeCodes": codes,
            "rationaleSummary": "the action would affect another party (%s)"
                                % _clip(", ".join(t.get("role", "") for t in tparties), 60),
        })

    return cands


# ── deterministic Grounder (resolve refs, attach principles; NO verdicts) ────

def _valid_ref(ref, ei):
    if not isinstance(ref, str) or ":" not in ref:
        return False
    owner = ref.split(":", 1)[0]
    if ref.startswith("turn:"):
        owner = "TURN"
    return owner in _SOURCE_OWNERS


def ground_concerns(candidates, ei):
    """Resolve refs, attach declared principle refs + resolution conditions,
    canonicalise concernIds. Deterministic. Assigns no outcome verdict."""
    grounded = []
    for i, c in enumerate(list(candidates or [])[:16], start=1):
        if not isinstance(c, dict):
            continue
        ctype = c.get("concernType")
        if ctype not in _CONCERN_TYPES:
            continue
        refs = [r for r in _as_str_list(c.get("sourceRefs")) if _valid_ref(r, ei)]
        principle_refs = list(CONCERN_PRINCIPLES.get(ctype, []))
        grounded.append({
            "concernId": "ec.%d" % i,
            "concernType": ctype,
            "principleRefs": principle_refs,
            "sourceRefs": refs,
            "causeCodes": _as_str_list(c.get("causeCodes")),
            "rationaleSummary": _clip(c.get("rationaleSummary") or ctype, 200),
            "resolutionConditions": list(_RESOLUTIONS.get(ctype, [])),
            "sourceScope": c.get("sourceScope"),
            "advisoryOnly": True,
        })
    return grounded


# ── deterministic Validator (verdicts + drops; NEVER synthesises concerns) ────

def validate_concerns(grounded, ei, applic, max_concerns=DEFAULT_MAX_CONCERNS):
    """Return (concerns, dropped, summary). Pure checks + drops only."""
    summary = {
        "SCHEMA_STATUS": "PASS",
        "PRINCIPLE_REFERENCE_STATUS": "PASS",
        "SOURCE_REFERENCE_STATUS": "PASS",
        "FABRICATION_STATUS": "PASS",
        "VOCABULARY_STATUS": "PASS",
    }
    kept, dropped = [], []
    cap = max(1, min(int(max_concerns or DEFAULT_MAX_CONCERNS), 4))
    for c in list(grounded or []):
        why = None
        # principle refs must all be declared AND APPLICABLE for that principle
        prefs = c.get("principleRefs") or []
        if not prefs or any(not _pr.is_principle(p) for p in prefs):
            why = "PRINCIPLE_REFERENCE"
            summary["PRINCIPLE_REFERENCE_STATUS"] = "DROPPED_PRESENT"
        elif any(applic.get(p, (_pr.APPLIC_NOT_APPLICABLE,))[0] != _pr.APPLIC_APPLICABLE for p in prefs):
            why = "PRINCIPLE_NOT_APPLICABLE"
            summary["PRINCIPLE_REFERENCE_STATUS"] = "DROPPED_PRESENT"
        # every concern must carry at least one resolvable source ref
        elif not c.get("sourceRefs"):
            why = "NO_SOURCE_REF"
            summary["SOURCE_REFERENCE_STATUS"] = "DROPPED_PRESENT"
        else:
            blob = json.dumps(c, ensure_ascii=False).lower()
            if any(t in blob for t in _BANNED_TERMS):
                why = "BANNED_VOCABULARY"
                summary["VOCABULARY_STATUS"] = "DROPPED_PRESENT"
        if why:
            dropped.append({"concernType": c.get("concernType"), "reason": why})
        else:
            kept.append(c)
    if len(kept) > cap:
        kept = kept[:cap]
    return kept, dropped, summary


# ── tensions / human-review / outcome / recommendations / info-needs ─────────

def derive_tensions(concerns, ei, max_tensions=DEFAULT_MAX_TENSIONS):
    """A tension only when two APPLICABLE principles genuinely pull apart on the
    same subject (e.g. the user wants an act that is irreversible under
    uncertainty). Reported UNRESOLVED; never double-counts an event as a concern
    AND a hidden score."""
    tensions = []
    types = {c["concernType"] for c in concerns}
    # user wants to proceed (autonomy) vs the act is irreversible-uncertain (non-mal)
    if (C_CONSENT_UNCLEAR in types or C_CONSTRAINT_CONFLICT in types) and C_IRREVERSIBLE in types:
        refs = sorted({r for c in concerns
                       if c["concernType"] in (C_CONSENT_UNCLEAR, C_CONSTRAINT_CONFLICT, C_IRREVERSIBLE)
                       for r in c.get("sourceRefs", [])})
        tensions.append({
            "tensionId": "et.1",
            "principleRefs": [_pr.P_USER_AUTONOMY, _pr.P_NON_MALEFICENCE],
            "sourceRefs": refs,
            "description": "acting as asked pulls against caution about an irreversible outcome under uncertainty",
            "resolutionStatus": "UNRESOLVED",
        })
    return tensions[:max_tensions]


def derive_human_review(concerns, tensions, ei, applic):
    """humanReviewRecommended from typed conditions only (correction 9)."""
    types = {c["concernType"] for c in concerns}
    if C_IRREVERSIBLE in types:
        return True, "irreversible action under uncertainty"
    if any(t.get("resolutionStatus") == "UNRESOLVED" for t in tensions) and C_IRREVERSIBLE in types:
        return True, "unresolved tension over a consequential impact"
    if C_THIRD_PARTY in types:
        # relevant consent/relationship unresolved (identity unresolved)
        tparties = _te(ei).get("referencedThirdPartyRoles") or []
        if any(not t.get("identityResolved") for t in tparties):
            return True, "third-party impact with the affected party unresolved"
    # context insufficient for an explicitly consequential/irreversible subject
    a = _action(ei)
    if a and a.get("impactClass") == "IRREVERSIBLE_DELETION" \
            and applic.get(_pr.P_NON_MALEFICENCE, ("",))[0] == _pr.APPLIC_INSUFFICIENT:
        return True, "irreversible subject but the situation is under-specified"
    return False, None


def derive_recommendations(concerns):
    seen, recs = set(), []
    for c in concerns:
        r = _RECOMMENDATIONS.get(c["concernType"])
        if r and r not in seen:
            seen.add(r)
            recs.append({"recommendation": r, "rationaleSummary": c["rationaleSummary"],
                         "forConcernId": c["concernId"], "advisory": True})
    return recs


def derive_information_needed(ei, applic, concerns):
    needs = []
    if applic.get(_pr.P_PRIVACY, ("",))[0] == _pr.APPLIC_INSUFFICIENT:
        needs.append(IN_DATA_SCOPE)
    tparties = _te(ei).get("referencedThirdPartyRoles") or []
    if any(not t.get("identityResolved") for t in tparties) and any(
            c["concernType"] == C_THIRD_PARTY for c in concerns):
        needs.append(IN_RECIPIENT)
    for (_c, ref) in _uncertainty_signals(ei):
        if _c == CC_TARGET_UNKNOWN and IN_TARGET_UNKNOWN not in needs:
            needs.append(IN_TARGET_UNKNOWN)
    return needs


def _subject_is_groundable(ei):
    """True when there is *something* concrete to weigh (an action, target, data
    scope, third party, or explicit constraint). Else the turn is too vague."""
    te = _te(ei)
    return bool(te.get("referencedAction") or te.get("referencedTargets")
                or te.get("referencedDataScope") or te.get("referencedThirdPartyRoles")
                or te.get("explicitConstraints"))


def _referenced_prohibited(ei):
    """True when the subject's referenced action is KNOWN_PROHIBITED in the static
    capability mirror (NOT a live Policy evaluation)."""
    a = _action(ei)
    cap = (a or {}).get("capabilityRef")
    return bool(cap) and _caps.is_known_prohibited(cap)


# ── deterministic natural answer (rendered FROM the typed result; no CoT) ─────

def _compose_answer(result):
    outcome = result["outcome"]
    if outcome == OUT_SKIPPED_PROHIBITION:
        return ("That action isn't available on this path — it's a hard prohibition, so there's "
                "nothing for me to weigh. Policy governs that, not me.")
    if outcome == OUT_INSUFFICIENT:
        needs = result.get("informationNeeded") or [IN_SUBJECT]
        return ("I can't weigh that yet — I'd need to know: " + "; ".join(needs[:3])
                + ". (This is an advisory read, not a decision.)")
    if outcome == OUT_NO_CONCERN:
        return ("Given what I can see and my working principles, I don't have a specific ethical "
                "concern to flag here. That's not me saying it's a good idea or clearing it — just "
                "that nothing concrete stands out.")
    # CONCERNS_IDENTIFIED / HUMAN_REVIEW_RECOMMENDED
    lines = ["A couple of things worth thinking about before you decide — this is advisory only, "
             "I'm not the one who says yes or no:"]
    for c in result["concerns"]:
        pnames = ", ".join(p.replace("_", " ").lower() for p in c["principleRefs"])
        lines.append("- %s (%s): %s" % (
            c["concernType"].replace("_", " ").lower(), pnames, c["rationaleSummary"]))
        if c.get("resolutionConditions"):
            lines.append("  what would ease it: %s" % c["resolutionConditions"][0])
    for t in result.get("tensions") or []:
        lines.append("- competing values: %s" % t["description"])
    if result.get("humanReviewRecommended"):
        lines.append("Given the stakes, I'd genuinely want your call on this one before anything moves.")
    return "\n".join(lines)


# ── bounded tool-less model call (indirections patchable for offline tests) ──

ETHICS_SYSTEM = """You are LILITH's ETHICAL DELIBERATION component. You are ADVISORY ONLY.
You surface ethically relevant concerns; you NEVER decide whether an action is
allowed, and you have NO tools.

You are given a single ethical SUBJECT and bounded, read-only TURN + world
evidence, plus a FIXED list of four principles: USER_AUTONOMY,
PRIVACY_MINIMIZATION, NON_MALEFICENCE, PROPORTIONALITY.

Hard rules:
- Reference ONLY those four principle ids. Never invent a principle.
- Raise a concern ONLY from the evidence refs provided. Never invent a user
  preference, a third-party identity, a data-sensitivity label, or a fact.
- Never output allow / deny / approved / safe / legal / compliant.
- Never re-argue a hard prohibition.
- Never expose private chain-of-thought or a scratchpad.

Output ONLY one JSON object (no prose, no code fences):
{ "concernCandidates": [
    { "concernType": "USER_CONSTRAINT_CONFLICT|EXECUTION_CONSENT_UNCLEAR|PRIVACY_EXPOSURE|UNNECESSARY_SCOPE|IRREVERSIBILITY_UNDER_UNCERTAINTY|THIRD_PARTY_IMPACT",
      "principleRefs": [string], "sourceRefs": [string], "rationaleSummary": string } ] }"""


def _resolve_model():
    from gateway.run import _resolve_gateway_model
    return _resolve_gateway_model()


def _resolve_kwargs():
    from gateway.run import _resolve_runtime_agent_kwargs
    return _resolve_runtime_agent_kwargs()


def _construct_agent(**kwargs):
    from run_agent import AIAgent
    return AIAgent(**kwargs)


def ethics_agent_kwargs():
    """Exact construction of the tool-less ethics agent (kept pure so a test can
    assert the no-tool boundary without a network call)."""
    kwargs = dict(_resolve_kwargs() or {})
    kwargs.update(
        model=_resolve_model(),
        quiet_mode=True,
        verbose_logging=False,
        skip_context_files=True,
        skip_memory=True,
        load_soul_identity=False,     # concern candidates are persona-neutral
        enabled_toolsets=[],          # PRIMARY no-tool boundary
        disabled_toolsets=None,
        ephemeral_system_prompt=ETHICS_SYSTEM,
        max_iterations=1,
    )
    return kwargs


def render_ethics_input(ei):
    ei = ei or {}
    te = _te(ei)
    subj = ei.get("ethicalSubject") or {}
    lines = ["ETHICAL SUBJECT: kind=%s ref=%s target=%s" % (
        subj.get("kind"), subj.get("ref"), subj.get("targetAppId"))]
    lines.append("NORMALIZED INTENT: %s" % _clip(te.get("normalizedIntent"), 200))
    a = te.get("referencedAction")
    if a:
        lines.append("ACTION[%s]: verb=%s cap=%s impact=%s bypass=%s" % (
            a.get("ref"), a.get("verb"), a.get("capabilityRef"),
            a.get("impactClass"), a.get("bypassConfirmation")))
    for c in te.get("explicitConstraints") or []:
        lines.append("CONSTRAINT[%s]: %s" % (c.get("ref"), _clip(c.get("text"), 100)))
    for d in te.get("referencedDataScope") or []:
        lines.append("DATA-SCOPE[%s]: %s" % (d.get("ref"), _clip(d.get("assertion"), 80)))
    for t in te.get("referencedThirdPartyRoles") or []:
        lines.append("THIRD-PARTY[%s]: role=%s identityResolved=%s" % (
            t.get("ref"), t.get("role"), t.get("identityResolved")))
    lines.append("PRINCIPLES: %s" % ", ".join(_pr.PRINCIPLE_IDS))
    lines.append("\nReturn ONLY the concernCandidates JSON object described in your instructions.")
    return "\n".join(lines)


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


def _llm_concern_candidates(ei, model_call):
    try:
        raw = model_call(render_ethics_input(ei))
        obj = _extract_json(raw)
        if not obj or not isinstance(obj.get("concernCandidates"), list):
            return None
        return obj.get("concernCandidates")
    except Exception:
        logger.debug("ethics: llm concern candidates failed (fail-open)", exc_info=True)
        return None


# ── Orchestration ────────────────────────────────────────────────────────────

def run_ethics(ethical_input, model_call=None, concern_candidates=None,
               max_concerns=None, max_tensions=None):
    """Run one bounded ethical deliberation turn. Returns (EthicalResult, trace).
    Never raises; any failure returns a typed non-fatal result so the caller falls
    open. DETERMINISTIC live path (model_call=None)."""
    ei = ethical_input or {}
    corr = ei.get("correlationId")
    subj = ei.get("ethicalSubject") or {}
    t0 = time.time()
    mc = max(1, min(int(max_concerns or DEFAULT_MAX_CONCERNS), 4))
    mt = max(1, min(int(max_tensions or DEFAULT_MAX_TENSIONS), 3))
    fallback = None
    cand_source = None
    try:
        # Hard known prohibition short-circuit — NO moral balancing (correction 19)
        if _referenced_prohibited(ei):
            result = _result(ei, OUT_SKIPPED_PROHIBITION, [], [], [], [], [], False,
                             prohibition=True)
            return result, build_trace(ei, result, "prohibition_skip", None, t0)

        applic = principle_applicability(ei)

        if concern_candidates is not None:
            raw = concern_candidates
            cand_source = "injected"
        elif model_call is not None:
            raw = _llm_concern_candidates(ei, model_call)
            cand_source = "llm" if raw is not None else None
            if raw is None:
                raw = []
        else:
            raw = deterministic_concern_candidates(ei, applic)
            cand_source = "deterministic"

        grounded = ground_concerns(raw, ei)
        concerns, dropped, vsummary = validate_concerns(grounded, ei, applic, max_concerns=mc)
        tensions = derive_tensions(concerns, ei, max_tensions=mt)
        human_review, hr_basis = derive_human_review(concerns, tensions, ei, applic)
        recs = derive_recommendations(concerns)
        info = derive_information_needed(ei, applic, concerns)

        if concerns:
            outcome = OUT_HUMAN_REVIEW if human_review else OUT_CONCERNS
        elif human_review:
            outcome = OUT_HUMAN_REVIEW
        elif not _subject_is_groundable(ei):
            outcome = OUT_INSUFFICIENT
            if not info:
                info = [IN_SUBJECT]
        elif info:
            outcome = OUT_INSUFFICIENT
        else:
            outcome = OUT_NO_CONCERN

        result = _result(ei, outcome, concerns, tensions, recs, info,
                         _applicability_list(applic), human_review,
                         validation=vsummary, dropped=dropped, hr_basis=hr_basis)
        return result, build_trace(ei, result, cand_source, fallback, t0)
    except Exception:
        logger.debug("ethics: run_ethics failed (fail-open)", exc_info=True)
        result = _result(ei, OUT_INSUFFICIENT, [], [], [], [IN_SUBJECT], [], False,
                         fallback=F_EXCEPTION)
        return result, build_trace(ei, result, cand_source, F_EXCEPTION, t0)


def _result(ei, outcome, concerns, tensions, recs, info, applicability, human_review,
            validation=None, dropped=None, prohibition=False, hr_basis=None, fallback=None):
    subj = (ei or {}).get("ethicalSubject") or {}
    ev_refs = sorted({r for c in concerns for r in (c.get("sourceRefs") or [])})
    # Seed the ephemeral snapshot id from SEMANTIC CONTENT only (normalized intent
    # + referenced action + outcome + concern types/cause-codes) so it is
    # independent of the per-turn correlationId, session, channel and clock: the
    # same grounded assessment yields the same id on Home and Telegram (parity),
    # while distinct assessments stay distinct. NOT a durable ethicalCaseId.
    _te2 = _te(ei)
    _a2 = _action(ei) or {}
    snapshot_seed = _hash(json.dumps({
        "intent": _te2.get("normalizedIntent"),
        "action": [_a2.get("verb"), _a2.get("impactClass"),
                   _a2.get("capabilityRef"), bool(_a2.get("bypassConfirmation"))],
        "outcome": outcome,
        "concerns": sorted([(c["concernType"], tuple(sorted(c.get("causeCodes") or [])))
                            for c in concerns]),
    }, sort_keys=True, default=str))
    res = {
        "schemaVersion": ETHICS_SCHEMA_VERSION,
        "ethicalSnapshotId": "es." + snapshot_seed[:16],
        "subject": subj,
        "outcome": outcome if outcome in _OUTCOMES else OUT_INSUFFICIENT,
        "concerns": concerns,
        "tensions": tensions,
        "advisoryRecommendations": recs,
        "informationNeeded": _as_str_list(info),
        "evidenceRefs": ev_refs,
        "principleApplicability": applicability,
        "humanReviewRecommended": bool(human_review),
        "principleSetVersion": _pr.PRINCIPLE_SET_VERSION,
        "validationSummary": validation or {},
        "traceMetadata": {"schemaVersion": ETHICS_SCHEMA_VERSION},
    }
    if prohibition:
        res["prohibitionBasis"] = "STATIC_POLICY_MIRROR"
        res["authoritativePolicyEvaluation"] = False
    if hr_basis:
        res["humanReviewBasis"] = hr_basis
    res["answer"] = _compose_answer(res)
    return res


def build_trace(ei, result, cand_source, fallback, t0):
    ei = ei or {}
    r = result or {}
    subj = r.get("subject") or {}
    concerns = r.get("concerns") or []
    return {
        "correlation_id": ei.get("correlationId"),
        "ethical_subject_kind": subj.get("kind"),
        "ethical_subject_ref": subj.get("ref"),
        "candidate_source": cand_source,
        "applicable_principles": sorted({p for c in concerns for p in c.get("principleRefs", [])}),
        "concern_types": sorted({c.get("concernType") for c in concerns}),
        "concern_count": len(concerns),
        "tension_count": len(r.get("tensions") or []),
        "outcome": r.get("outcome"),
        "source_ref_count": len(r.get("evidenceRefs") or []),
        "human_review_recommended": bool(r.get("humanReviewRecommended")),
        "prohibition_basis": r.get("prohibitionBasis"),
        "authoritative_policy_evaluation": r.get("authoritativePolicyEvaluation", False),
        "principle_set_version": _pr.PRINCIPLE_SET_VERSION,
        "validation_summary": r.get("validationSummary"),
        "duration_ms": round((time.time() - t0) * 1000),
        "fallback_reason": fallback,
        "schema_version": ETHICS_SCHEMA_VERSION,
        "ts": round(time.time(), 3),
    }
