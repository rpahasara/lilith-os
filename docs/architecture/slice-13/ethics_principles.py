# -*- coding: utf-8 -*-
"""LILITH Slice 13 — ETHICAL PRINCIPLE SET (fixed, architecture-defined).

Advisory only. These four principles are the ONLY normative sources Ethics may
reference. They are declared here as immutable constants so the LLM candidate
path can NEVER invent a principle id — the grounder/validator reject any concern
whose principleRefs are not in this set.

Hard rules (see Slice 13 corrections 6/7/12):
  * exactly four principles: USER_AUTONOMY, PRIVACY_MINIMIZATION,
    NON_MALEFICENCE, PROPORTIONALITY. No TRANSPARENCY / FAIRNESS / HUMAN_OVERSIGHT
    / generic HARM / cultural / legal / org / personal-LILITH principles.
  * advisoryOnly is True for every principle — Ethics never authorises.
  * NO weights, NO scores, NO precedence hierarchy.
  * principle applicability is THREE-WAY (APPLICABLE / NOT_APPLICABLE /
    INSUFFICIENT_EVIDENCE) — missing evidence is never silently NOT_APPLICABLE.
"""
from __future__ import annotations

PRINCIPLE_SET_VERSION = 1

# ── Principle ids (the ONLY valid ids) ───────────────────────────────────────
P_USER_AUTONOMY = "USER_AUTONOMY"
P_PRIVACY = "PRIVACY_MINIMIZATION"
P_NON_MALEFICENCE = "NON_MALEFICENCE"
P_PROPORTIONALITY = "PROPORTIONALITY"

PRINCIPLE_IDS = (P_USER_AUTONOMY, P_PRIVACY, P_NON_MALEFICENCE, P_PROPORTIONALITY)

# ── Three-way applicability (correction 12) ──────────────────────────────────
APPLIC_APPLICABLE = "APPLICABLE"
APPLIC_NOT_APPLICABLE = "NOT_APPLICABLE"
APPLIC_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"
APPLICABILITY_STATES = (APPLIC_APPLICABLE, APPLIC_NOT_APPLICABLE, APPLIC_INSUFFICIENT)

PRINCIPLES = {
    P_USER_AUTONOMY: {
        "principleId": P_USER_AUTONOMY,
        "name": "User autonomy & consent",
        "definition": ("Respect the user's explicit intent, consent and control "
                       "over consequential actions taken on their behalf."),
        "source": "architecture-defined",
        "scope": ["standing user constraint", "action bypassing user confirmation"],
        "advisoryOnly": True,
    },
    P_PRIVACY: {
        "principleId": P_PRIVACY,
        "name": "Privacy minimisation",
        "definition": ("Avoid unnecessary exposure or use of personal data; "
                       "disclose no more than the goal requires."),
        "source": "architecture-defined",
        "scope": ["disclosure action + real personal-data scope"],
        "advisoryOnly": True,
    },
    P_NON_MALEFICENCE: {
        "principleId": P_NON_MALEFICENCE,
        "name": "Non-maleficence",
        "definition": ("Avoid reasonably foreseeable unnecessary concrete impact; "
                       "be cautious with irreversible actions under uncertainty."),
        "source": "architecture-defined",
        "scope": ["concrete impact class (irreversible deletion / external "
                  "disclosure) + source-backed uncertainty"],
        "advisoryOnly": True,
    },
    P_PROPORTIONALITY: {
        "principleId": P_PROPORTIONALITY,
        "name": "Proportionality",
        "definition": ("Prefer actions whose scope/intrusion matches the scope of "
                       "the subject/goal."),
        "source": "architecture-defined",
        "scope": ["comparable typed subject scope vs action scope"],
        "advisoryOnly": True,
    },
}


def is_principle(principle_id):
    """True only for one of the four declared principle ids."""
    return principle_id in PRINCIPLES


def principle(principle_id):
    """Return a copy of the declared principle, or None for an unknown id.
    Never fabricates a principle."""
    p = PRINCIPLES.get(principle_id)
    return dict(p) if p else None


def summary():
    """Bounded, safe description of the fixed principle set (for the trace / input)."""
    return {
        "principleSetVersion": PRINCIPLE_SET_VERSION,
        "advisoryOnly": True,
        "principleIds": list(PRINCIPLE_IDS),
    }
