"""Slice 14 renderer-independent Presence semantic contract.

Hints are orthogonal, deterministic context permissions. They are not affect,
emotion, personality, animation, styling, or renderer commands.
"""

from __future__ import annotations

from typing import Any, Dict, List

from . import social_cognition as _social


SCHEMA_VERSION = 1
_ALLOWED_KEYS = frozenset({
    "schemaVersion", "correlationId", "socialSemanticFingerprint",
    "socialTone", "formalityHint", "playfulness", "sourceRefs",
})


class PresenceValidationError(ValueError):
    """Raised when a hint exceeds the semantic-only V1 contract."""


def _cue_refs(snapshot: Dict[str, Any], cue_types: set) -> List[str]:
    return sorted({
        ref
        for cue in snapshot.get("socialCues", [])
        if cue.get("cueType") in cue_types
        for ref in cue.get("sourceRefs", [])
    })


def _constraint_refs(snapshot: Dict[str, Any], value: str) -> List[str]:
    return sorted({
        ref
        for constraint in snapshot.get("explicitInteractionConstraints", [])
        if constraint.get("dimension") == "FORMALITY" and constraint.get("value") == value
        for ref in constraint.get("sourceRefs", [])
    })


def derive_presence_hint(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Derive independent semantic axes from a validated SocialContextSnapshot."""
    _social.validate_social_context(snapshot)
    source_refs = set()

    supportive_refs = _cue_refs(snapshot, {_social.C_SUPPORT, _social.C_DIFFICULTY})
    social_tone = "SUPPORTIVE" if supportive_refs else "NEUTRAL"
    source_refs.update(supportive_refs)

    formal_refs = _constraint_refs(snapshot, "PROFESSIONAL")
    casual_refs = _constraint_refs(snapshot, "CASUAL")
    formality = "NEUTRAL"
    if formal_refs and not casual_refs:
        formality = "PROFESSIONAL"
        source_refs.update(formal_refs)
    elif not formal_refs and not casual_refs:
        audience = snapshot.get("audienceContext") or {}
        if audience.get("audienceContextClass") == _social.PROFESSIONAL:
            formality = "PROFESSIONAL"
            source_refs.update(audience.get("sourceRefs") or [])
    # CASUAL or contradictory explicit requests intentionally yield the default
    # NEUTRAL value. V1 uses no source refs for default values.

    playful_refs = _cue_refs(snapshot, {_social.C_HUMOR, _social.C_PLAYFUL})
    playfulness = "PERMITTED" if playful_refs else "RESTRAINED"
    source_refs.update(playful_refs)

    hint = {
        "schemaVersion": SCHEMA_VERSION,
        "correlationId": snapshot["turnRef"].removeprefix("turn:"),
        "socialSemanticFingerprint": snapshot["socialSemanticFingerprint"],
        "socialTone": social_tone,
        "formalityHint": formality,
        "playfulness": playfulness,
        "sourceRefs": sorted(source_refs),
    }
    validate_presence_hint(hint, snapshot)
    return hint


def validate_presence_hint(hint: Dict[str, Any], snapshot: Dict[str, Any]) -> None:
    """Reject unsupported renderer/affect semantics; never repair them."""
    if not isinstance(hint, dict) or set(hint) != set(_ALLOWED_KEYS):
        raise PresenceValidationError("invalid PresenceSemanticHint fields")
    if hint["schemaVersion"] != SCHEMA_VERSION:
        raise PresenceValidationError("invalid Presence schema version")
    if hint["correlationId"] != snapshot["turnRef"].removeprefix("turn:"):
        raise PresenceValidationError("Presence correlation mismatch")
    if hint["socialSemanticFingerprint"] != snapshot["socialSemanticFingerprint"]:
        raise PresenceValidationError("Presence fingerprint mismatch")
    if hint["socialTone"] not in {"NEUTRAL", "SUPPORTIVE"}:
        raise PresenceValidationError("unsupported social tone")
    if hint["formalityHint"] not in {"NEUTRAL", "PROFESSIONAL"}:
        raise PresenceValidationError("unsupported formality hint")
    if hint["playfulness"] not in {"RESTRAINED", "PERMITTED"}:
        raise PresenceValidationError("unsupported playfulness hint")
    if not isinstance(hint["sourceRefs"], list):
        raise PresenceValidationError("Presence sourceRefs must be a list")
    if len(hint["sourceRefs"]) != len(set(hint["sourceRefs"])):
        raise PresenceValidationError("Presence sourceRefs must be unique")
    if not set(hint["sourceRefs"]).issubset(set(snapshot["sourceRefs"])):
        raise PresenceValidationError("Presence source ref does not resolve")

    expected = set()
    if hint["socialTone"] == "SUPPORTIVE":
        expected.update(_cue_refs(snapshot, {_social.C_SUPPORT, _social.C_DIFFICULTY}))
    if hint["formalityHint"] == "PROFESSIONAL":
        formal_refs = _constraint_refs(snapshot, "PROFESSIONAL")
        casual_refs = _constraint_refs(snapshot, "CASUAL")
        if formal_refs and not casual_refs:
            expected.update(formal_refs)
        elif not formal_refs and not casual_refs:
            expected.update((snapshot.get("audienceContext") or {}).get("sourceRefs") or [])
    if hint["playfulness"] == "PERMITTED":
        expected.update(_cue_refs(snapshot, {_social.C_HUMOR, _social.C_PLAYFUL}))
    if set(hint["sourceRefs"]) != expected:
        raise PresenceValidationError("Presence provenance is not exactly causal")
