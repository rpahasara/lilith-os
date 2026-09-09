

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
