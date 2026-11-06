# -*- coding: utf-8 -*-
"""LILITH Slice 12 — PLANNING CAPABILITY VIEW (non-authoritative).

This is NOT a capability registry and NOT a runtime availability/health source.
The authoritative capability registry + Policy engine + Connector fabric live in
the frontend RealCommandCore (browser-only) and are NOT reachable on the Router
V2 path. This module declares only the *planning-visible capability semantics*
currently proven / declared for planning on this Router path, so the Planner can:

  * recognise a declared capability          (CAPABILITY_REFERENCE_VALID),
  * refuse to invent capabilities            (unknown -> UNEXECUTABLE),
  * mark a known-prohibited capability as never-executable,

without ever claiming a live Policy decision or live runtime availability.

Hard rules encoded here (see Slice 12 design refinements 4/5/6/7):
  * ``runtimeAvailability`` is ALWAYS ``UNKNOWN`` — no real owner supplies health
    on this path, so static support NEVER becomes live availability.
  * ``policyCompatibility`` is planning-visible only: KNOWN_PROHIBITED /
    NO_KNOWN_STATIC_CONFLICT / NOT_EVALUATED. ``NO_KNOWN_STATIC_CONFLICT`` is
    NOT a Policy ALLOW.
  * ``supportStatus``: ROUTER_PATH_SUPPORTED | KNOWN_UNAVAILABLE | NOT_DECLARED.

Ownership: this small view lives in planning.py's own module (planning owns its
capability view), NOT in world_context.py (which owns bounded source assembly).
"""
from __future__ import annotations

PLANNING_CAPABILITY_VIEW_VERSION = 1

# supportStatus values
SUPPORT_ROUTER_SUPPORTED = "ROUTER_PATH_SUPPORTED"
SUPPORT_KNOWN_UNAVAILABLE = "KNOWN_UNAVAILABLE"
SUPPORT_NOT_DECLARED = "NOT_DECLARED"

# policyCompatibility values (planning-visible only; never a Policy decision)
POLICY_KNOWN_PROHIBITED = "KNOWN_PROHIBITED"
POLICY_NO_STATIC_CONFLICT = "NO_KNOWN_STATIC_CONFLICT"
POLICY_NOT_EVALUATED = "NOT_EVALUATED"

# runtimeAvailability is never asserted here
RUNTIME_UNKNOWN = "UNKNOWN"

# The narrow set of capability semantics planning may reference on this path.
_VIEW = {
    "career.create_followup_draft": {
        "capabilityRef": "career.create_followup_draft",
        "supportStatus": SUPPORT_ROUTER_SUPPORTED,
        "policyCompatibility": POLICY_NO_STATIC_CONFLICT,
        "reversibilityClass": "REVERSIBLE",     # /os/drafts soft-discard exists
        "idempotencyClass": "IDEMPOTENT",       # idempotency_key os2.<appid>.<hash>
        "runtimeAvailability": RUNTIME_UNKNOWN,
        "declaredVia": "POST /os/drafts (kind=career_followup)",
        "verificationMethod": "bounded read-back of /os/drafts (status=created)",
        "note": ("reversible internal write proven on the Router path; "
                 "runtime health is not owned here"),
    },
    "career.add_note": {
        "capabilityRef": "career.add_note",
        "supportStatus": SUPPORT_ROUTER_SUPPORTED,
        "policyCompatibility": POLICY_NO_STATIC_CONFLICT,
        "reversibilityClass": "REVERSIBLE",
        "idempotencyClass": "IDEMPOTENT",
        "runtimeAvailability": RUNTIME_UNKNOWN,
        "declaredVia": "POST /os/drafts (kind=career_note)",
        "verificationMethod": "bounded read-back of /os/drafts (kind=career_note)",
        "note": ("reversible internal write declared on the Router path; "
                 "runtime health is not owned here"),
    },
    "mail.send_email": {
        "capabilityRef": "mail.send_email",
        "supportStatus": SUPPORT_KNOWN_UNAVAILABLE,
        "policyCompatibility": POLICY_KNOWN_PROHIBITED,
        "reversibilityClass": "IRREVERSIBLE",
        "idempotencyClass": "UNKNOWN",
        "runtimeAvailability": RUNTIME_UNKNOWN,
        "declaredVia": "no external send capability exists on this path",
        "verificationMethod": None,
        "note": "PROHIBITED — no external send capability exists",
    },
}

# capability families known unavailable on this path (e.g. google-workspace.*)
_UNAVAILABLE_PREFIXES = ("google-workspace", "gmail", "calendar")


def describe(capability_ref):
    """Return the planning-visible descriptor for a capability ref.

    Never returns None: an unknown ref yields a NOT_DECLARED descriptor so the
    planner treats it as UNEXECUTABLE rather than inventing capability semantics.
    """
    ref = str(capability_ref or "").strip()
    if ref in _VIEW:
        return dict(_VIEW[ref])
    for pfx in _UNAVAILABLE_PREFIXES:
        if ref == pfx or ref.startswith(pfx + "."):
            return {
                "capabilityRef": ref,
                "supportStatus": SUPPORT_KNOWN_UNAVAILABLE,
                "policyCompatibility": POLICY_NOT_EVALUATED,
                "reversibilityClass": "UNKNOWN",
                "idempotencyClass": "UNKNOWN",
                "runtimeAvailability": RUNTIME_UNKNOWN,
                "declaredVia": "connector unavailable (OAuth not connected)",
                "verificationMethod": None,
                "note": "known unavailable on the Router path",
            }
    return {
        "capabilityRef": ref or "(none)",
        "supportStatus": SUPPORT_NOT_DECLARED,
        "policyCompatibility": POLICY_NOT_EVALUATED,
        "reversibilityClass": "UNKNOWN",
        "idempotencyClass": "UNKNOWN",
        "runtimeAvailability": RUNTIME_UNKNOWN,
        "declaredVia": None,
        "verificationMethod": None,
        "note": "not declared for planning on the Router path",
    }


def is_reference_valid(capability_ref):
    """CAPABILITY_REFERENCE_VALID: planning recognises the declared capability
    semantics. NOT a runtime-availability or Policy-allow check."""
    return describe(capability_ref)["supportStatus"] in (
        SUPPORT_ROUTER_SUPPORTED, SUPPORT_KNOWN_UNAVAILABLE)


def is_executable_reference(capability_ref):
    """True only when the capability is router-path-supported AND not known
    prohibited. This is a CAPABILITY_REFERENCE check — it is explicitly NOT a
    runtime-availability decision and NOT a Policy ALLOW."""
    d = describe(capability_ref)
    return (d["supportStatus"] == SUPPORT_ROUTER_SUPPORTED
            and d["policyCompatibility"] != POLICY_KNOWN_PROHIBITED)


def is_known_prohibited(capability_ref):
    return describe(capability_ref)["policyCompatibility"] == POLICY_KNOWN_PROHIBITED


def view_summary():
    """Bounded, safe, explicitly non-authoritative summary for PlanningInput."""
    return {
        "viewVersion": PLANNING_CAPABILITY_VIEW_VERSION,
        "authoritative": False,
        "capabilities": [
            {
                "capabilityRef": k,
                "supportStatus": v["supportStatus"],
                "policyCompatibility": v["policyCompatibility"],
                "runtimeAvailability": v["runtimeAvailability"],
            }
            for k, v in _VIEW.items()
        ],
        "note": ("planning-visible capability view; NOT a runtime registry; "
                 "runtime availability is UNKNOWN unless a real owner supplies it"),
    }
