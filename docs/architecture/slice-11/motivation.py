# -*- coding: utf-8 -*-
"""LILITH Slice 11 — Motivation / Homeostasis System V1 (cognitive layer L06).

A bounded, ephemeral, DETERMINISTIC per-turn regulatory read. It converts
already-scoped source conditions (World-Model contradiction/staleness and
unresolved goal state) into a small set of typed ORDINAL ``DriveSignal``s,
maps eligible ones to low-tier ``MOTIVATION_DRIVE`` attention candidates, and
exposes a bounded read-only summary for the reasoning lane.

Hard boundaries (mirrors workspace.py / reasoning.py):
  * owns ordinal CLASSIFICATION only — never source truth
  * no writes, no tools, no connectors, no goal/belief/task/draft mutation
  * no LLM scoring, no probabilities, NO floats for intensity — ordered classes
  * no persistence — the snapshot is ephemeral and reconstructible
  * NEVER consumes a ReasoningResult (order is Motivation -> Workspace -> Reasoning)
  * never self-amplifies: a DriveSignal is never an input to any drive
  * never raises into the caller: any internal failure yields a valid, partial
    snapshot with ``fallbackReason`` set

Only stdlib is imported. This module performs NO network I/O — the world_context
Slice-11 adapters fetch the (already scoped) source state and hand plain dicts
here, so the unit suite runs fully offline with synthetic inputs.
"""
from __future__ import annotations

import hashlib
import logging
import time

logger = logging.getLogger(__name__)

MOTIVATION_SCHEMA_VERSION = 1

DRIVE_TYPES = ("COHERENCE", "GOAL_COMPLETION", "SAFETY")

# Ordered ordinal deviation classes (index = severity; higher index = worse).
INTENSITY_CLASSES = ("SATISFIED", "MILD", "SIGNIFICANT", "CRITICAL")
_INTENSITY_RANK = {name: i for i, name in enumerate(INTENSITY_CLASSES)}

# Terminal (non-actionable) goal lifecycle states — never generate pressure.
_TERMINAL_GOAL_STATES = {"COMPLETED", "CANCELLED", "FAILED", "SUPERSEDED"}
_FAILED_TASK_STATES = {"failed", "error"}

# Keys forbidden on the durable/observable signal (no CoT/affect leakage).
_FORBIDDEN_KEYS = (
    "thinking", "scratchpad", "chain_of_thought", "reasoning_text", "cot",
    "homeostaticState",            # decision 7: no duplicate of intensityClass
    "priorIntensity", "newIntensity",  # decision 6: no transition claims
    "happy", "sad", "angry", "lonely", "excited", "affect", "emotion",
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _as_str_list(v, limit=25):
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, (list, tuple)):
        return []
    out = []
    for x in v:
        if x is None:
            continue
        s = str(x)
        if s not in out:
            out.append(s)
        if len(out) >= limit:
            break
    return out


def _worse(a, b):
    """Return the higher-severity of two intensity classes."""
    return a if _INTENSITY_RANK.get(a, 0) >= _INTENSITY_RANK.get(b, 0) else b


def _drive_id(drive_type):
    return "drive:%s" % drive_type


# ── DriveSignal construction ─────────────────────────────────────────────────

def make_drive(drive_type, intensity_class, *, source_refs=None, cause_codes=None,
               related_goal_ids=None, related_belief_refs=None, related_task_ids=None,
               target_apps=None, evidence_counts=None, resolution_conditions=None,
               candidate_eligible=False, channel=None):
    """Build one whitelisted, forbidden-key-free DriveSignal (ordinal only)."""
    if drive_type not in DRIVE_TYPES:
        drive_type = "COHERENCE"
    if intensity_class not in INTENSITY_CLASSES:
        intensity_class = "SATISFIED"
    sig = {
        "schemaVersion": MOTIVATION_SCHEMA_VERSION,
        "driveId": _drive_id(drive_type),
        "driveType": drive_type,
        "intensityClass": intensity_class,           # decision 7: the ONE ordinal field
        "sourceRefs": _as_str_list(source_refs),
        "causeCodes": _as_str_list(cause_codes),
        "relatedGoalIds": _as_str_list(related_goal_ids),
        "relatedBeliefRefs": _as_str_list(related_belief_refs),
        "relatedTaskIds": _as_str_list(related_task_ids),
        "targetApps": _as_str_list(target_apps),
        "evidenceCounts": {k: int(v) for k, v in (evidence_counts or {}).items()
                           if isinstance(v, (int, float))},
        "resolutionConditions": _as_str_list(resolution_conditions),
        "candidateEligible": bool(candidate_eligible),
        "persistenceClass": "reconstructed",
        "provenance": "motivation@%s" % (channel or "?"),
    }
    for k in _FORBIDDEN_KEYS:
        sig.pop(k, None)
    return sig


def is_active(drive):
    return _INTENSITY_RANK.get((drive or {}).get("intensityClass"), 0) > 0


# ── COHERENCE (World-Model contradiction / staleness) ────────────────────────
# Consumes ONLY lifecycle ∈ {CONFLICTED, STALE} (+ contradicted_by). Epistemic
# (OBSERVED/VERIFIED/USER_ASSERTED/INFERRED) is carried as evidence, never as a
# severity input. UNKNOWN is absence and produces nothing here.

def classify_coherence(belief_conditions, *, critical_belief_keys=None, channel=None):
    """belief_conditions: list of dicts {key, entity_id, lifecycle, contradicted, epistemic}
    already SCOPED by the caller (from ws_cands belief candidates — no global scan).
    critical_belief_keys: exact belief keys provably referenced by a selected
    blocker's relatedBeliefRefs or the focus goal's blockedBy (decision 4)."""
    crit_keys = set(_as_str_list(critical_belief_keys))
    conflicted, stale = [], []
    refs, apps, causes = [], [], []
    provable_critical = False
    for b in (belief_conditions or []):
        life = (b or {}).get("lifecycle")
        key = (b or {}).get("key")
        contradicted = bool((b or {}).get("contradicted"))
        if life == "CONFLICTED" or contradicted:
            conflicted.append(key)
            if key is not None and str(key) in crit_keys:
                provable_critical = True
        elif life == "STALE":
            stale.append(key)
        else:
            continue  # ACTIVE / SUPERSEDED / anything else is not coherence pressure
        if key is not None:
            refs.append(key)
        app = (b or {}).get("entity_id")
        if app is not None:
            apps.append(str(app))

    if conflicted:
        intensity = "CRITICAL" if provable_critical else "SIGNIFICANT"  # decision 4 cap
        causes.append("WORLD_CONFLICTED")
        if provable_critical:
            causes.append("CONFLICT_BLOCKS_SELECTED_TARGET")
    elif stale:
        intensity = "MILD"
        causes.append("WORLD_STALE")
    else:
        intensity = "SATISFIED"

    return make_drive(
        "COHERENCE", intensity,
        source_refs=refs, cause_codes=causes,
        related_belief_refs=refs, target_apps=apps,
        evidence_counts={"conflicted": len(conflicted), "stale": len(stale)},
        resolution_conditions=(
            ["belief reconciled to ACTIVE or refreshed (no longer CONFLICTED/STALE)"]
            if intensity != "SATISFIED" else []),
        channel=channel,
    )


# ── GOAL_COMPLETION (unresolved goal state) ──────────────────────────────────
# Scoped: only goals that are the Executive focus, explicitly user-referenced,
# or present in ws_cands (the caller passes exactly those). CRITICAL requires a
# typed hard blocker: goal.blockedBy references a FAILED/ERROR task.

def classify_goal_completion(goal_conditions, *, channel=None):
    """goal_conditions: list of dicts {goalId, lifecycleState, isFocus, userReferenced,
    source, blockedBy:[...], targetApp, hardBlockerFailedTaskIds:[...]}
    already SCOPED by the caller (no global scan)."""
    intensity = "SATISFIED"
    refs, apps, gids, tids, causes = [], [], [], [], []
    blocked_count = 0
    for g in (goal_conditions or []):
        g = g or {}
        state = g.get("lifecycleState")
        if state in _TERMINAL_GOAL_STATES or state != "BLOCKED":
            continue  # only BLOCKED, non-terminal goals create pressure
        blocked_count += 1
        gid = g.get("goalId")
        if gid is not None:
            gids.append(str(gid))
            refs.append(str(gid))
        app = g.get("targetApp")
        if app is not None:
            apps.append(str(app))

        is_focus = bool(g.get("isFocus"))
        user_req_ref = bool(g.get("userReferenced")) and str(g.get("source")) == "USER_REQUESTED"
        hard = _as_str_list(g.get("hardBlockerFailedTaskIds"))

        if hard:
            # decision 5: CRITICAL only with a typed hard blocker (failed task in blockedBy)
            this = "CRITICAL"
            causes.append("HARD_BLOCKER_FAILED_TASK")
            for t in hard:
                tids.append(t)
        elif is_focus:
            this = "SIGNIFICANT"
            causes.append("GOAL_BLOCKED_FOCUS")
        elif user_req_ref:
            this = "SIGNIFICANT"
            causes.append("GOAL_USER_REQUESTED_BLOCKED")
        else:
            this = "MILD"
            causes.append("GOAL_BLOCKED_NONFOCUS")
        intensity = _worse(intensity, this)

    return make_drive(
        "GOAL_COMPLETION", intensity,
        source_refs=refs, cause_codes=causes,
        related_goal_ids=gids, related_task_ids=tids, target_apps=apps,
        evidence_counts={"blocked": blocked_count},
        resolution_conditions=(
            ["blocker cleared / goal COMPLETED or CANCELLED / user drops it"]
            if intensity != "SATISFIED" else []),
        channel=channel,
    )


# ── SAFETY (synthetic / test-only; decision 13) ──────────────────────────────
# No live producer. Emitted ONLY when the caller passes an explicit synthetic
# source (tests). build_snapshot never derives this from real GETs.

def classify_safety_synthetic(synthetic, *, channel=None):
    if not synthetic:
        return make_drive("SAFETY", "SATISFIED", channel=channel)
    intensity = synthetic.get("intensityClass") if isinstance(synthetic, dict) else None
    if intensity not in INTENSITY_CLASSES or intensity == "SATISFIED":
        intensity = "SIGNIFICANT"
    return make_drive(
        "SAFETY", intensity,
        cause_codes=["SAFETY_SYNTHETIC"],
        source_refs=(synthetic.get("sourceRefs") if isinstance(synthetic, dict) else None),
        resolution_conditions=["synthetic safety source cleared (test-only)"],
        channel=channel,
    )


# ── snapshot assembly ────────────────────────────────────────────────────────

def build_snapshot(*, coherence, goal_completion, safety=None,
                   raw_refs=None, correlation_id=None, channel=None,
                   source_availability=None, partial=False):
    """Assemble the ephemeral MotivationSnapshot. Never raises.

    coherence / goal_completion / safety are DriveSignal dicts (or None).
    raw_refs: the set of exact refs already represented by RAW ws_cands, used to
    decide candidateEligible per drive (decision 9 dedup)."""
    t0 = time.time()
    fallback = None
    drives = []
    try:
        for d in (coherence, goal_completion, safety):
            if d is not None:
                drives.append(d)
        raw = _raw_ref_set(raw_refs)
        for d in drives:
            d["candidateEligible"] = bool(is_active(d) and not _refs_represented(d, raw))
        active = [d["driveType"] for d in drives if is_active(d)]
        satisfied = [d["driveType"] for d in drives if not is_active(d)]
        highest = "SATISFIED"
        for d in drives:
            highest = _worse(highest, d.get("intensityClass"))
    except Exception:
        logger.debug("motivation: build_snapshot failed (fail-open)", exc_info=True)
        drives, active, satisfied, highest = [], [], [], "SATISFIED"
        fallback = "exception"

    corr = correlation_id or ("m." + hashlib.sha256(
        (str(channel) + "|" + str(t0)).encode("utf-8")).hexdigest()[:16])
    return {
        "schemaVersion": MOTIVATION_SCHEMA_VERSION,
        "correlationId": corr,
        "timestamp": _now_iso(),
        "channel": channel,
        "drives": drives,
        "activeDrives": active,
        "satisfiedDrives": satisfied,          # decision 6: renamed from resolvedDrives
        "highestIntensityClass": highest,      # trace only; NOT an aggregate utility
        "sourceAvailability": dict(source_availability or {}),
        "partial": bool(partial or fallback),
        "fallbackReason": fallback,
        "_durationMs": round((time.time() - t0) * 1000),
    }


def _raw_ref_set(raw_refs):
    s = set()
    for x in (raw_refs or []):
        if x is not None:
            s.add(str(x))
    return s


def _refs_represented(drive, raw_ref_set):
    """True if ANY exact causal ref of this drive is already a raw ws_cand ref."""
    if not raw_ref_set:
        return False
    for field in ("relatedGoalIds", "relatedBeliefRefs", "relatedTaskIds",
                  "sourceRefs", "targetApps"):
        for r in (drive.get(field) or []):
            if str(r) in raw_ref_set:
                return True
    return False


# ── drive -> attention candidate (low MOTIVATION_PRESSURE tier) ──────────────

def to_attention_candidates(snapshot, channel=None):
    """Emit a MOTIVATION_DRIVE AttentionCandidate for each candidateEligible,
    active drive. Sets ONLY motivationDrive/motivationIntensity so workspace
    classify_salience assigns MOTIVATION_PRESSURE (never a higher class)."""
    out = []
    for d in (snapshot or {}).get("drives", []):
        if not (d.get("candidateEligible") and is_active(d)):
            continue
        out.append({
            "sourceType": "MOTIVATION_DRIVE",
            "sourceRef": d["driveId"],
            "category": "motivation",
            "summary": "%s pressure %s (standing): %s" % (
                d["driveType"], d["intensityClass"],
                ", ".join(d.get("causeCodes") or []) or "unresolved condition"),
            "motivationDrive": True,
            "motivationIntensity": d["intensityClass"],
            "relatedGoalId": (d.get("relatedGoalIds") or [None])[0],
            "relatedBeliefRefs": list(d.get("relatedBeliefRefs") or []),
            "relatedTaskIds": list(d.get("relatedTaskIds") or []),
            "targetApps": list(d.get("targetApps") or []),
            "lifecycle": "until_resolved",
            "provenance": "motivation@%s" % (channel or "?"),
        })
    return out


# ── bounded reasoning summary (decision 10) ──────────────────────────────────

def bounded_summary(snapshot, selected_refs, selected_candidate_sourcerefs=None):
    """Return ONLY drives that (a) had their MOTIVATION_DRIVE candidate selected,
    or (b) support a selected raw candidate through EXACT shared refs. Unselected,
    unrelated drive state cannot bypass the Workspace boundary into Reasoning."""
    sel = _raw_ref_set(selected_refs)
    sel_cands = _raw_ref_set(selected_candidate_sourcerefs)
    out = []
    for d in (snapshot or {}).get("drives", []):
        if not is_active(d):
            continue
        selected_as_candidate = d.get("driveId") in sel_cands
        supports_selected = _refs_represented(d, sel)
        if selected_as_candidate or supports_selected:
            out.append({
                "driveType": d["driveType"],
                "intensityClass": d["intensityClass"],
                "causeCodes": list(d.get("causeCodes") or []),
                "refs": (list(d.get("relatedGoalIds") or [])
                         + list(d.get("relatedBeliefRefs") or [])),
                "basis": ("selected_candidate" if selected_as_candidate
                          else "supports_selected"),
            })
    return out


# ── safe, non-CoT trace ──────────────────────────────────────────────────────

def build_trace(snapshot):
    s = snapshot or {}
    per = []
    for d in s.get("drives", []):
        per.append({
            "driveType": d.get("driveType"),
            "intensityClass": d.get("intensityClass"),   # evaluated class; NO prior/new
            "causeCodes": list(d.get("causeCodes") or []),
            "sourceRefCount": len(d.get("sourceRefs") or []),
            "candidateEligible": bool(d.get("candidateEligible")),
            "resolutionConditions": list(d.get("resolutionConditions") or []),
            "relatedGoalIds": list(d.get("relatedGoalIds") or []),
        })
    return {
        "correlation_id": s.get("correlationId"),
        "channel": s.get("channel"),
        "drive_count": len(s.get("drives") or []),
        "active_drive_types": list(s.get("activeDrives") or []),
        "satisfied_drive_types": list(s.get("satisfiedDrives") or []),
        "highest_intensity_class": s.get("highestIntensityClass"),
        "per_drive": per,
        "source_availability": s.get("sourceAvailability"),
        "partial": bool(s.get("partial")),
        "duration_ms": s.get("_durationMs"),
        "fallback_reason": s.get("fallbackReason"),
        "schema_version": MOTIVATION_SCHEMA_VERSION,
        "timestamp": s.get("timestamp"),
    }
