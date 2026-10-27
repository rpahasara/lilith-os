"""Slice 14 Social Cognition V1: deterministic, turn-only observation.

This module owns ephemeral social evidence and semantic context only. It does
not own personality, prompt construction, reply wording, affect, relationship
state, World truth, tools, or persistence. Validation is fail-closed:
unsupported meaning is rejected rather than repaired.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple


SCHEMA_VERSION = 1
SOURCE_TURN = "TURN"
TURN_ONLY = "TURN_ONLY_BY_DESIGN"
MAX_ITEMS = 8

CURRENT_TURN_SENDER = "CURRENT_TURN_SENDER"
THIRD_PARTY = "THIRD_PARTY"
SESSION_BOUND = "SESSION_BOUND"
ROLE_ONLY = "ROLE_ONLY"

PROFESSIONAL = "PROFESSIONAL"
UNSPECIFIED = "UNSPECIFIED"

E_ROLE = "THIRD_PARTY_ROLE_MENTION"
E_RECIPIENT = "INTENDED_RECIPIENT_RELATION"
E_FORMAL = "EXPLICIT_FORMALITY_REQUEST"
E_CASUAL = "EXPLICIT_CASUAL_STYLE_REQUEST"
E_HUMOR = "EXPLICIT_HUMOR_REQUEST"
E_PLAYFUL = "PLAYFUL_CONTEXT_CUE"
E_SUPPORT = "EXPLICIT_SUPPORT_REQUEST"
E_DIFFICULTY = "EXPLICIT_DIFFICULTY_SELF_REPORT"
E_CORRECTION = "USER_CORRECTION"

C_HUMOR = E_HUMOR
C_PLAYFUL = E_PLAYFUL
C_SUPPORT = E_SUPPORT
C_DIFFICULTY = E_DIFFICULTY
C_CORRECTION = E_CORRECTION

_EVIDENCE_TYPES = frozenset({
    E_ROLE, E_RECIPIENT, E_FORMAL, E_CASUAL, E_HUMOR, E_PLAYFUL,
    E_SUPPORT, E_DIFFICULTY, E_CORRECTION,
})
_CUE_TYPES = frozenset({C_HUMOR, C_PLAYFUL, C_SUPPORT, C_DIFFICULTY, C_CORRECTION})
_ROLE_LABELS = ("manager", "recruiter", "sister", "partner", "coworker")
_PROFESSIONAL_ROLES = frozenset({"manager", "recruiter"})
_ROLE_ALT = "|".join(_ROLE_LABELS)

_ROLE_RE = re.compile(
    rf"\b(?:my|the|our|their|your)\s+(?P<role>{_ROLE_ALT})\b",
    re.IGNORECASE,
)
_RECIPIENT_PATTERNS = (
    re.compile(
        rf"\b(?:write|draft|compose|prepare)\b.{{0,64}}?"
        rf"\b(?:message|reply|note|email)\b.{{0,20}}?\b(?:to|for)\s+"
        rf"(?:my|the|our)\s+(?P<role>{_ROLE_ALT})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bwhat\s+should\s+i\s+(?:say|write|reply)\s+to\s+"
        rf"(?:my|the|our)\s+(?P<role>{_ROLE_ALT})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\breply\s+to\s+(?:my|the|our)\s+(?P<role>{_ROLE_ALT})\b",
        re.IGNORECASE,
    ),
)
_FORMAL_RE = re.compile(
    r"\b(?:(?:reply|write|word|say|make\s+it|keep\s+it|sound)\s+"
    r"(?:this\s+)?(?:formally|professionally)|formal\s+(?:reply|response|message|tone))\b",
    re.IGNORECASE,
)
_CASUAL_RE = re.compile(
    r"\b(?:(?:reply|write|word|say|make\s+it|keep\s+it|sound)\s+"
    r"(?:this\s+)?(?:casually|informally)|casual\s+(?:reply|response|message|tone))\b",
    re.IGNORECASE,
)
_HUMOR_RE = re.compile(
    r"\b(?:make\s+(?:it|this|that)\s+funny|be\s+funny|add\s+(?:some\s+)?humou?r|use\s+humou?r)\b",
    re.IGNORECASE,
)
_PLAYFUL_LEXICAL_RE = re.compile(
    r"\b(?:this\s+\w+\s+is\s+trolling\s+me|\w+\s+is\s+trolling\s+me|"
    r"this\s+\w+\s+is\s+roasting\s+me|\w+\s+is\s+roasting\s+me)\b",
    re.IGNORECASE,
)
_LAUGHTER_RE = re.compile(r"(?:😂|🤣|\blol\b|\blmao\b)", re.IGNORECASE)
_SUPPORT_RE = re.compile(
    r"\b(?:(?:can|could|would)\s+you\s+(?:please\s+)?"
    r"(?:reassure|support|comfort)\s+me|i\s+need\s+(?:reassurance|support))\b",
    re.IGNORECASE,
)
_DIFFICULTY_RE = re.compile(
    r"\b(?:i\s+am|i['’]?m|im|i\s+feel)\s+"
    r"(?:frustrated|overwhelmed|stuck|struggling)\b",
    re.IGNORECASE,
)
_CORRECTION_RE = re.compile(r"^\s*(?:no|actually|correction)\b", re.IGNORECASE)

_INTERACTION_MAP = {
    E_FORMAL: ("FORMALITY", "PROFESSIONAL"),
    E_CASUAL: ("FORMALITY", "CASUAL"),
}
_EVIDENCE_ALLOWED_KEYS = frozenset({
    "evidenceRef", "evidenceType", "sourceRange", "literalRoleLabel",
    "assertionStatus", "constraintDimension", "constraintValue",
    "relatedSourceRefs",
})
_FORBIDDEN_KEYS = frozenset({
    "currentUser", "authenticatedHuman", "worldReferences", "worldReference",
    "epistemic", "epistemicState", "lifecycle", "lifecycleState",
    "relationship", "relationshipClass", "relationshipStrength", "trust",
    "closeness", "familiarity", "friendshipScore", "emotion", "mood",
    "sentiment", "valence", "arousal", "userAssertedAffect", "personality",
    "personalityProfile", "interactionStyle", "final_response", "prompt",
    "promptText", "policyResult", "goals", "tasks", "drafts", "execution",
    "animation", "pose", "bone", "blendshape", "camera", "gaze", "timing",
    "intensity", "energy", "responsePhase", "socialSnapshotId",
})


class SocialValidationError(ValueError):
    """Raised when an object carries unsupported or ungrounded meaning."""


def make_correlation_id(session_key: str, message: str, now_ns: Optional[int] = None) -> str:
    """Create a non-identifying, turn-local correlation id."""
    stamp = time.time_ns() if now_ns is None else int(now_ns)
    seed = f"{session_key}|{message}|{stamp}".encode("utf-8")
    return "sc." + hashlib.sha256(seed).hexdigest()[:16]


def _range(match: re.Match, group: Optional[str] = None) -> Dict[str, int]:
    start, end = match.span(group) if group else match.span()
    return {"start": start, "endExclusive": end}


def _raw_item(kind: str, match: re.Match, **values: Any) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "evidenceType": kind,
        "sourceRange": _range(match),
        "_sort": (match.start(), kind),
    }
    item.update(values)
    return item


def _role_is_negated(message: str, match: re.Match) -> bool:
    return message[:match.start()].rstrip().lower().endswith("not")


def build_social_turn_evidence(message: str, correlation_id: str) -> Dict[str, Any]:
    """Extract bounded TURN-TEXT evidence only; session metadata is excluded."""
    text = message if isinstance(message, str) else ""
    corr = str(correlation_id or "").strip()
    if not corr:
        raise SocialValidationError("correlationId is required")
    turn_ref = f"turn:{corr}"
    raw: List[Dict[str, Any]] = []
    role_entries: List[Dict[str, Any]] = []

    for match in _ROLE_RE.finditer(text):
        role = match.group("role").lower()
        span = match.span("role")
        item = {
            "evidenceType": E_ROLE,
            "sourceRange": {"start": span[0], "endExclusive": span[1]},
            "literalRoleLabel": role,
            "assertionStatus": "NEGATED" if _role_is_negated(text, match) else "ASSERTED",
            "_sort": (span[0], E_ROLE),
            "_role_key": (span[0], span[1], role),
        }
        raw.append(item)
        role_entries.append(item)

    for pattern in _RECIPIENT_PATTERNS:
        for match in pattern.finditer(text):
            role = match.group("role").lower()
            rspan = match.span("role")
            raw.append(_raw_item(
                E_RECIPIENT, match, literalRoleLabel=role,
                _target_role_key=(rspan[0], rspan[1], role),
            ))

    for pattern, kind in ((_FORMAL_RE, E_FORMAL), (_CASUAL_RE, E_CASUAL)):
        for match in pattern.finditer(text):
            dimension, value = _INTERACTION_MAP[kind]
            raw.append(_raw_item(
                kind, match, constraintDimension=dimension, constraintValue=value,
            ))

    for pattern, kind in (
        (_HUMOR_RE, E_HUMOR), (_SUPPORT_RE, E_SUPPORT), (_DIFFICULTY_RE, E_DIFFICULTY),
    ):
        for match in pattern.finditer(text):
            raw.append(_raw_item(kind, match))

    playful_lex = _PLAYFUL_LEXICAL_RE.search(text)
    laughter = _LAUGHTER_RE.search(text)
    if playful_lex and laughter:
        start = min(playful_lex.start(), laughter.start())
        end = max(playful_lex.end(), laughter.end())
        raw.append({
            "evidenceType": E_PLAYFUL,
            "sourceRange": {"start": start, "endExclusive": end},
            "_sort": (start, E_PLAYFUL),
        })

    correction = _CORRECTION_RE.search(text)
    asserted_roles = [i for i in role_entries if i["assertionStatus"] == "ASSERTED"]
    negated_roles = [i for i in role_entries if i["assertionStatus"] == "NEGATED"]
    if correction and asserted_roles and negated_roles:
        raw.append(_raw_item(
            E_CORRECTION, correction, _correction_roles=asserted_roles + negated_roles,
        ))

    unique: List[Dict[str, Any]] = []
    seen = set()
    for item in sorted(raw, key=lambda value: value["_sort"]):
        sr = item["sourceRange"]
        key = (
            item["evidenceType"], sr["start"], sr["endExclusive"],
            item.get("literalRoleLabel"), item.get("constraintValue"),
        )
        if key not in seen:
            seen.add(key)
            unique.append(item)
    selected = unique[:MAX_ITEMS]

    role_ref_by_key: Dict[Tuple[int, int, str], str] = {}
    for index, item in enumerate(selected):
        item["evidenceRef"] = f"{turn_ref}:evidence:{index}"
        if item["evidenceType"] == E_ROLE:
            role_ref_by_key[item["_role_key"]] = item["evidenceRef"]

    final_items: List[Dict[str, Any]] = []
    for item in selected:
        if item["evidenceType"] == E_RECIPIENT:
            role_ref = role_ref_by_key.get(item["_target_role_key"])
            if not role_ref:
                continue
            item["relatedSourceRefs"] = [role_ref]
        elif item["evidenceType"] == E_CORRECTION:
            refs = [
                role_ref_by_key.get(role_item.get("_role_key"))
                for role_item in item.get("_correction_roles", [])
            ]
            item["relatedSourceRefs"] = sorted(ref for ref in refs if ref)
            if len(item["relatedSourceRefs"]) < 2:
                continue
        final_items.append({key: value for key, value in item.items() if not key.startswith("_")})

    result = {
        "schemaVersion": SCHEMA_VERSION,
        "correlationId": corr,
        "turnRef": turn_ref,
        "sourceOwner": SOURCE_TURN,
        "evidenceItems": final_items,
        "sourceRefs": [turn_ref] + [item["evidenceRef"] for item in final_items],
    }
    validate_social_turn_evidence(result, text)
    return result


def build_social_input(
    message: str,
    correlation_id: str,
    channel: str,
    session_actor_ref: Optional[str] = None,
) -> Dict[str, Any]:
    """Keep Router/session actor provenance separate from TURN-TEXT evidence."""
    corr = str(correlation_id or "").strip()
    actor_ref = session_actor_ref or f"router:{corr}:session-actor"
    result = {
        "schemaVersion": SCHEMA_VERSION,
        "correlationId": corr,
        "channel": str(channel or ""),
        "sessionActor": {
            "actorRef": actor_ref,
            "bindingType": "CURRENT_TURN_SENDER_BINDING",
            "participantKind": CURRENT_TURN_SENDER,
            "identityStatus": SESSION_BOUND,
        },
        "socialTurnEvidence": build_social_turn_evidence(message, corr),
    }
    validate_social_input(result, message)
    return result


def _refs(values: Iterable[Dict[str, Any]]) -> List[str]:
    return sorted({ref for value in values for ref in (value.get("sourceRefs") or [])})


def _semantic_payload(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    role_for_ref = {
        participant["participantRef"]: participant.get("literalRoleLabel")
        for participant in snapshot.get("participants", [])
    }
    audience = snapshot.get("audienceContext")
    return {
        "participants": sorted(
            (participant["participantKind"], participant["identityStatus"],
             participant.get("literalRoleLabel") or "")
            for participant in snapshot.get("participants", [])
        ),
        "audience": None if not audience else (
            audience["audienceContextClass"], role_for_ref.get(audience["audienceRef"]) or ""
        ),
        "constraints": sorted(
            (item["dimension"], item["value"])
            for item in snapshot.get("explicitInteractionConstraints", [])
        ),
        "cues": sorted(item["cueType"] for item in snapshot.get("socialCues", [])),
        "conflicts": sorted(item["conflictType"] for item in snapshot.get("conflicts", [])),
        "informationNeeded": sorted(
            item["code"] for item in snapshot.get("informationNeeded", [])
        ),
        "sourceAvailability": snapshot.get("sourceAvailability"),
    }


def semantic_fingerprint(snapshot: Dict[str, Any]) -> str:
    """Content fingerprint excluding channel, clock, ids, refs, and offsets."""
    canonical = json.dumps(
        _semantic_payload(snapshot), sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    )
    return "scf." + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def build_social_context(social_input: Dict[str, Any]) -> Dict[str, Any]:
    """Build the minimal ephemeral SocialContextSnapshot."""
    _validate_social_input_shape(social_input)
    evidence = social_input["socialTurnEvidence"]
    items = evidence["evidenceItems"]
    actor = social_input["sessionActor"]
    turn_ref = evidence["turnRef"]
    corr = social_input["correlationId"]

    participants: List[Dict[str, Any]] = [{
        "participantRef": f"social:{corr}:participant:sender",
        "participantKind": CURRENT_TURN_SENDER,
        "identityStatus": SESSION_BOUND,
        "sourceRefs": [actor["actorRef"]],
    }]
    role_participant_by_ref: Dict[str, Dict[str, Any]] = {}
    for item in items:
        if item["evidenceType"] != E_ROLE or item.get("assertionStatus") != "ASSERTED":
            continue
        participant = {
            "participantRef": f"social:{corr}:participant:{len(participants)}",
            "participantKind": THIRD_PARTY,
            "identityStatus": ROLE_ONLY,
            "literalRoleLabel": item["literalRoleLabel"],
            "sourceRefs": [item["evidenceRef"]],
        }
        participants.append(participant)
        role_participant_by_ref[item["evidenceRef"]] = participant
        if len(participants) >= MAX_ITEMS:
            break

    constraints = []
    cues = []
    for item in items:
        kind = item["evidenceType"]
        if kind in _INTERACTION_MAP:
            dimension, value = _INTERACTION_MAP[kind]
            constraints.append({
                "dimension": dimension, "value": value,
                "sourceRefs": [item["evidenceRef"]],
            })
        if kind in _CUE_TYPES:
            source_refs = [item["evidenceRef"]] + list(item.get("relatedSourceRefs") or [])
            cues.append({"cueType": kind, "sourceRefs": sorted(set(source_refs))})

    recipient_candidates: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for item in items:
        if item["evidenceType"] != E_RECIPIENT:
            continue
        for related_ref in item.get("relatedSourceRefs") or []:
            participant = role_participant_by_ref.get(related_ref)
            if participant:
                recipient_candidates.append((item, participant))

    conflicts: List[Dict[str, Any]] = []
    information_needed: List[Dict[str, Any]] = []
    formal_refs = _refs(value for value in constraints if value["value"] == "PROFESSIONAL")
    casual_refs = _refs(value for value in constraints if value["value"] == "CASUAL")
    if formal_refs and casual_refs:
        both = sorted(set(formal_refs + casual_refs))
        conflicts.append({
            "conflictType": "CONTRADICTORY_FORMALITY_REQUESTS", "sourceRefs": both,
        })
        information_needed.append({
            "code": "FORMALITY_REQUEST_UNCLEAR", "sourceRefs": both,
        })

    for cue in cues:
        if cue["cueType"] == C_CORRECTION:
            conflicts.append({
                "conflictType": "CURRENT_TURN_ROLE_CORRECTION",
                "sourceRefs": cue["sourceRefs"],
            })

    audience = None
    unique_audiences = {
        participant["participantRef"]: (item, participant)
        for item, participant in recipient_candidates
    }
    if len(unique_audiences) == 1:
        item, participant = next(iter(unique_audiences.values()))
        role = participant.get("literalRoleLabel")
        audience = {
            "audienceRef": participant["participantRef"],
            "audienceContextClass": PROFESSIONAL if role in _PROFESSIONAL_ROLES else UNSPECIFIED,
            "sourceRefs": sorted(set(participant["sourceRefs"] + [item["evidenceRef"]])),
        }
    elif len(unique_audiences) > 1:
        refs = sorted({item["evidenceRef"] for item, _ in unique_audiences.values()})
        conflicts.append({
            "conflictType": "AMBIGUOUS_RECIPIENT_RELATION", "sourceRefs": refs,
        })
        information_needed.append({"code": "RECIPIENT_UNCLEAR", "sourceRefs": refs})

    snapshot: Dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "socialSemanticFingerprint": "",
        "turnRef": turn_ref,
        "channel": social_input["channel"],
        "participants": participants[:MAX_ITEMS],
        "explicitInteractionConstraints": constraints[:MAX_ITEMS],
        "socialCues": cues[:MAX_ITEMS],
        "conflicts": conflicts[:MAX_ITEMS],
        "informationNeeded": information_needed[:MAX_ITEMS],
        "sourceRefs": sorted(set([actor["actorRef"]] + evidence["sourceRefs"])),
        "sourceAvailability": TURN_ONLY,
    }
    if audience is not None:
        snapshot["audienceContext"] = audience
    snapshot["socialSemanticFingerprint"] = semantic_fingerprint(snapshot)
    validate_social_context(snapshot)
    return snapshot


def _walk(value: Any) -> Iterable[Tuple[Optional[str], Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield None, child
            yield from _walk(child)


def _reject_forbidden(value: Any) -> None:
    for key, child in _walk(value):
        if key in _FORBIDDEN_KEYS:
            raise SocialValidationError(f"unsupported field: {key}")
        if isinstance(child, str) and child in {
            "CURRENT_USER", "WORLD_REFERENCED", "USER_ASSERTED_AFFECT", "WARM",
        }:
            raise SocialValidationError(f"unsupported value: {child}")


def _exact_keys(value: Dict[str, Any], required: set, optional: set = set()) -> None:
    keys = set(value)
    if not required.issubset(keys) or not keys.issubset(required | optional):
        raise SocialValidationError(
            f"invalid fields: required={sorted(required)} actual={sorted(keys)}"
        )


def validate_social_turn_evidence(evidence: Dict[str, Any], message: str) -> None:
    _reject_forbidden(evidence)
    _exact_keys(evidence, {
        "schemaVersion", "correlationId", "turnRef", "sourceOwner",
        "evidenceItems", "sourceRefs",
    })
    if evidence["schemaVersion"] != SCHEMA_VERSION or evidence["sourceOwner"] != SOURCE_TURN:
        raise SocialValidationError("invalid TURN evidence owner/version")
    if evidence["turnRef"] != f"turn:{evidence['correlationId']}":
        raise SocialValidationError("turnRef/correlationId mismatch")
    items = evidence["evidenceItems"]
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        raise SocialValidationError("evidenceItems exceeds capacity")
    refs = set()
    for item in items:
        if not isinstance(item, dict) or not set(item).issubset(_EVIDENCE_ALLOWED_KEYS):
            raise SocialValidationError("invalid evidence item fields")
        _exact_keys(
            item, {"evidenceRef", "evidenceType", "sourceRange"},
            set(_EVIDENCE_ALLOWED_KEYS) - {"evidenceRef", "evidenceType", "sourceRange"},
        )
        if item["evidenceType"] not in _EVIDENCE_TYPES:
            raise SocialValidationError("unsupported evidence type")
        if not str(item["evidenceRef"]).startswith(evidence["turnRef"] + ":evidence:"):
            raise SocialValidationError("evidence ref is not turn-bound")
        if item["evidenceRef"] in refs:
            raise SocialValidationError("duplicate evidence ref")
        refs.add(item["evidenceRef"])
        sr = item["sourceRange"]
        _exact_keys(sr, {"start", "endExclusive"})
        start, end = sr["start"], sr["endExclusive"]
        if (
            not isinstance(start, int) or not isinstance(end, int) or start < 0
            or end <= start or end > len(message)
        ):
            raise SocialValidationError("invalid direct source range")
        if item["evidenceType"] == E_ROLE:
            label = item.get("literalRoleLabel")
            if label not in _ROLE_LABELS or message[start:end].lower() != label:
                raise SocialValidationError("literal role is not directly grounded")
            if item.get("assertionStatus") not in {"ASSERTED", "NEGATED"}:
                raise SocialValidationError("role assertion status missing")
        if item["evidenceType"] in _INTERACTION_MAP:
            if (
                item.get("constraintDimension"), item.get("constraintValue")
            ) != _INTERACTION_MAP[item["evidenceType"]]:
                raise SocialValidationError("invalid interaction constraint")
    if set(evidence["sourceRefs"]) != ({evidence["turnRef"]} | refs):
        raise SocialValidationError("TURN sourceRefs do not resolve exactly")
    for item in items:
        if not set(item.get("relatedSourceRefs") or []).issubset(refs):
            raise SocialValidationError("related TURN source ref does not resolve")


def _validate_social_input_shape(social_input: Dict[str, Any]) -> None:
    _reject_forbidden(social_input)
    _exact_keys(social_input, {
        "schemaVersion", "correlationId", "channel", "sessionActor", "socialTurnEvidence",
    })
    if social_input["schemaVersion"] != SCHEMA_VERSION:
        raise SocialValidationError("invalid SocialInput version")
    actor = social_input["sessionActor"]
    _exact_keys(actor, {"actorRef", "bindingType", "participantKind", "identityStatus"})
    if actor["bindingType"] != "CURRENT_TURN_SENDER_BINDING":
        raise SocialValidationError("invalid session binding type")
    if actor["participantKind"] != CURRENT_TURN_SENDER or actor["identityStatus"] != SESSION_BOUND:
        raise SocialValidationError("session actor must remain non-authenticated CURRENT_TURN_SENDER")
    evidence = social_input["socialTurnEvidence"]
    if evidence.get("correlationId") != social_input["correlationId"]:
        raise SocialValidationError("SocialInput/evidence correlation mismatch")
    if actor["actorRef"] in set(evidence.get("sourceRefs") or []):
        raise SocialValidationError("Router/session actor was mislabeled as TURN evidence")


def validate_social_input(social_input: Dict[str, Any], message: str) -> None:
    _validate_social_input_shape(social_input)
    validate_social_turn_evidence(social_input["socialTurnEvidence"], message)


def validate_social_context(snapshot: Dict[str, Any]) -> None:
    _reject_forbidden(snapshot)
    required = {
        "schemaVersion", "socialSemanticFingerprint", "turnRef", "channel",
        "participants", "explicitInteractionConstraints", "socialCues", "conflicts",
        "informationNeeded", "sourceRefs", "sourceAvailability",
    }
    _exact_keys(snapshot, required, {"audienceContext"})
    if snapshot["schemaVersion"] != SCHEMA_VERSION or snapshot["sourceAvailability"] != TURN_ONLY:
        raise SocialValidationError("invalid SocialContextSnapshot version/source")
    for field in (
        "participants", "explicitInteractionConstraints", "socialCues", "conflicts",
        "informationNeeded",
    ):
        if not isinstance(snapshot[field], list) or len(snapshot[field]) > MAX_ITEMS:
            raise SocialValidationError(f"{field} exceeds capacity")
    source_refs = set(snapshot["sourceRefs"])
    if not source_refs or not all(isinstance(ref, str) and ref for ref in source_refs):
        raise SocialValidationError("invalid snapshot sourceRefs")

    participants = snapshot["participants"]
    sender_count = 0
    participant_refs = set()
    for participant in participants:
        _exact_keys(
            participant, {"participantRef", "participantKind", "identityStatus", "sourceRefs"},
            {"literalRoleLabel"},
        )
        if participant["participantRef"] in participant_refs:
            raise SocialValidationError("duplicate participantRef")
        participant_refs.add(participant["participantRef"])
        if participant["participantKind"] == CURRENT_TURN_SENDER:
            sender_count += 1
            if participant["identityStatus"] != SESSION_BOUND or "literalRoleLabel" in participant:
                raise SocialValidationError("invalid current sender")
        elif participant["participantKind"] == THIRD_PARTY:
            if participant["identityStatus"] not in {ROLE_ONLY, "UNRESOLVED"}:
                raise SocialValidationError("invalid third-party identity status")
            if participant.get("literalRoleLabel") not in _ROLE_LABELS:
                raise SocialValidationError("unsupported literal role")
        else:
            raise SocialValidationError("unsupported participant kind in V1")
        if not set(participant["sourceRefs"]).issubset(source_refs):
            raise SocialValidationError("participant source ref unresolved")
    if sender_count != 1:
        raise SocialValidationError("exactly one current-turn sender is required")

    for constraint in snapshot["explicitInteractionConstraints"]:
        _exact_keys(constraint, {"dimension", "value", "sourceRefs"})
        if (constraint["dimension"], constraint["value"]) not in {
            ("FORMALITY", "PROFESSIONAL"), ("FORMALITY", "CASUAL"),
        }:
            raise SocialValidationError("unsupported interaction constraint")
        if not constraint["sourceRefs"] or not set(constraint["sourceRefs"]).issubset(source_refs):
            raise SocialValidationError("constraint provenance missing")

    for cue in snapshot["socialCues"]:
        _exact_keys(cue, {"cueType", "sourceRefs"})
        if cue["cueType"] not in _CUE_TYPES or not cue["sourceRefs"]:
            raise SocialValidationError("unsupported/unproven social cue")
        if not set(cue["sourceRefs"]).issubset(source_refs):
            raise SocialValidationError("cue provenance unresolved")

    audience = snapshot.get("audienceContext")
    if audience:
        _exact_keys(audience, {"audienceRef", "audienceContextClass", "sourceRefs"})
        if audience["audienceRef"] not in participant_refs:
            raise SocialValidationError("audience participant unresolved")
        participant = next(p for p in participants if p["participantRef"] == audience["audienceRef"])
        role = participant.get("literalRoleLabel")
        if audience["audienceContextClass"] == PROFESSIONAL:
            if role not in _PROFESSIONAL_ROLES or len(audience["sourceRefs"]) < 2:
                raise SocialValidationError("unsupported professional audience")
        elif audience["audienceContextClass"] != UNSPECIFIED:
            raise SocialValidationError("unsupported audience class")
        if not set(audience["sourceRefs"]).issubset(source_refs):
            raise SocialValidationError("audience provenance unresolved")

    for conflict in snapshot["conflicts"]:
        _exact_keys(conflict, {"conflictType", "sourceRefs"})
        if conflict["conflictType"] not in {
            "CONTRADICTORY_FORMALITY_REQUESTS", "CURRENT_TURN_ROLE_CORRECTION",
            "AMBIGUOUS_RECIPIENT_RELATION",
        }:
            raise SocialValidationError("unsupported conflict")
        if not conflict["sourceRefs"] or not set(conflict["sourceRefs"]).issubset(source_refs):
            raise SocialValidationError("conflict provenance unresolved")

    for need in snapshot["informationNeeded"]:
        _exact_keys(need, {"code", "sourceRefs"})
        if need["code"] not in {"FORMALITY_REQUEST_UNCLEAR", "RECIPIENT_UNCLEAR"}:
            raise SocialValidationError("unsupported information need")
        if not need["sourceRefs"] or not set(need["sourceRefs"]).issubset(source_refs):
            raise SocialValidationError("information-need provenance unresolved")

    if snapshot["socialSemanticFingerprint"] != semantic_fingerprint(snapshot):
        raise SocialValidationError("semantic fingerprint mismatch")


def build_trace(
    snapshot: Dict[str, Any],
    presence_hint: Dict[str, Any],
    *,
    duration_ms: int,
    validation_status: str = "VALID",
    fallback_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a safe, non-CoT trace. Literal roles and raw text are excluded."""
    return {
        "lane": "social_cognition",
        "correlation_id": snapshot["turnRef"].removeprefix("turn:"),
        "social_semantic_fingerprint": snapshot["socialSemanticFingerprint"],
        "participant_count": len(snapshot["participants"]),
        "participant_kinds": sorted(p["participantKind"] for p in snapshot["participants"]),
        "audience_context_class": (snapshot.get("audienceContext") or {}).get("audienceContextClass"),
        "constraint_types": sorted(c["dimension"] for c in snapshot["explicitInteractionConstraints"]),
        "cue_types": sorted(c["cueType"] for c in snapshot["socialCues"]),
        "conflict_types": sorted(c["conflictType"] for c in snapshot["conflicts"]),
        "information_need_codes": sorted(n["code"] for n in snapshot["informationNeeded"]),
        "source_availability": snapshot["sourceAvailability"],
        "presence_social_tone": presence_hint["socialTone"],
        "presence_formality_hint": presence_hint["formalityHint"],
        "presence_playfulness": presence_hint["playfulness"],
        "validation_status": validation_status,
        "fallback_reason": fallback_reason,
        "duration_ms": max(0, int(duration_ms)),
        "schema_version": SCHEMA_VERSION,
        "timestamp": round(time.time(), 3),
    }

