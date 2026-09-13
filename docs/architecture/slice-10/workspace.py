# -*- coding: utf-8 -*-
"""LILITH Slice 10 — Global Workspace / Attention System V1.

A bounded, ephemeral, DETERMINISTIC per-turn attention mechanism (cognitive
layer L02). It receives normalized ``AttentionCandidate`` dicts (produced by
``world_context.build_attention_candidates`` from durable source refs), collapses
duplicates, ranks them by typed ordered salience CLASSES, and returns a bounded
``WorkspaceSnapshot`` (one primary + a small secondary set) plus explicit
suppression/defer reasons and a safe, non-CoT trace.

Boundaries (hard):
  * owns SELECTION only — never source truth
  * no writes, no tools, no connectors, no goal/belief/task/draft mutation
  * no LLM scoring, no probabilities — arbitration is ordered typed classes
  * no persistence — the snapshot is ephemeral and reconstructible
  * never raises into the caller: any internal failure yields a valid snapshot
    with ``fallback_reason`` set (the router then falls open to Slice 9).

Only stdlib is imported. This module is import-safe offline and unit-tested with
purely synthetic candidates (no network, no world_context, no VM).
"""
from __future__ import annotations

import hashlib
import logging
import time

logger = logging.getLogger(__name__)

WORKSPACE_SCHEMA_VERSION = 1

# Secondary-capacity hard bound. workspace_capacity is clamped into [0, MAX].
MAX_SECONDARY_CAPACITY = 8
DEFAULT_SECONDARY_CAPACITY = 4

# ── Ordered typed salience classes (rank = index; lower rank wins) ──────────
# The named class is ALWAYS the explainable deciding reason in the trace.
SALIENCE_CLASSES = (
    "SYSTEM_CRITICAL",          # 0  synthetic/test-only in V1 (no real producer)
    "USER_OVERRIDE_TARGET",     # 1  target of an explicit attention override
    "USER_REFERENCED_BLOCKER",  # 2  blocker on a user-referenced object
    "USER_REFERENCED_OBJECT",   # 3  object explicitly named by the user this turn
    "BLOCKER_ON_FOCUS",         # 4  blocker affecting the current Executive focus
    "FOCUS_CONTINUITY",         # 5  the current Executive focus goal
    "UNRESOLVED_APPROVAL",      # 6  approval-pending draft/task
    "DEADLINE_URGENCY",         # 7
    "WORLD_CONFLICT",           # 8  CONFLICTED/STALE belief on a relevant entity
    "TASK_FAILURE",             # 9
    "RECENT_UNRESOLVED",        # 10
    "BACKGROUND_MAINT",         # 11 connector/health; synthetic/test-only in V1
)
_CLASS_RANK = {name: i for i, name in enumerate(SALIENCE_CLASSES)}
_LOWEST_RANK = len(SALIENCE_CLASSES)  # unknown/missing class => lowest priority

SUPPRESSION_REASONS = (
    "LOWER_SALIENCE", "CAPACITY_LIMIT", "STALE", "DUPLICATE",
    "IRRELEVANT_TO_CURRENT_TURN", "SUPERSEDED", "EXPIRED",
)


# ── Salience classification (deterministic; flags -> named class) ───────────

def classify_salience(cand):
    """Return the ordered salience class for a candidate from its flags. Pure.

    First rule that matches wins — this ordering IS the arbitration policy and
    the explanation. No numeric score decides the class."""
    c = cand or {}
    category = c.get("category")
    if c.get("systemCritical"):
        return "SYSTEM_CRITICAL"
    if c.get("userOverrideTarget"):
        return "USER_OVERRIDE_TARGET"
    if c.get("userReferenced") and category == "blocker":
        return "USER_REFERENCED_BLOCKER"
    if c.get("userReferenced"):
        return "USER_REFERENCED_OBJECT"
    if category == "blocker" and c.get("blockingImpact"):
        return "BLOCKER_ON_FOCUS"
    if c.get("isFocusGoal"):
        return "FOCUS_CONTINUITY"
    if c.get("approvalPending"):
        return "UNRESOLVED_APPROVAL"
    if c.get("deadline"):
        return "DEADLINE_URGENCY"
    if c.get("conflict"):
        return "WORLD_CONFLICT"
    if c.get("taskFailure"):
        return "TASK_FAILURE"
    if category in ("connector_state", "system_health"):
        return "BACKGROUND_MAINT"
    if c.get("recentlyChanged"):
        return "RECENT_UNRESOLVED"
    return "BACKGROUND_MAINT"


# ── Normalization / validation ──────────────────────────────────────────────

_REQUIRED = ("sourceType", "sourceRef", "category")


def normalize_candidate(raw, correlation_id=None):
    """Return a normalized candidate dict, or None if malformed (dropped).

    Whitelists fields, coerces flags to bool, fills a deterministic candidateId
    and the assigned salienceClass. A candidate missing a sourceType/sourceRef/
    category or a usable summary is rejected (test T)."""
    if not isinstance(raw, dict):
        return None
    for k in _REQUIRED:
        v = raw.get(k)
        if not isinstance(v, str) or not v.strip():
            return None
    summary = raw.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return None
    source_type = raw["sourceType"].strip()
    source_ref = raw["sourceRef"].strip()
    cand = {
        "schemaVersion": WORKSPACE_SCHEMA_VERSION,
        "correlationId": correlation_id or raw.get("correlationId"),
        "sourceType": source_type,
        "sourceRef": source_ref,
        "category": raw["category"].strip(),
        "summary": summary.strip()[:280],
        "systemCritical": bool(raw.get("systemCritical", False)),
        "userReferenced": bool(raw.get("userReferenced", False)),
        "userOverrideTarget": bool(raw.get("userOverrideTarget", False)),
        "isFocusGoal": bool(raw.get("isFocusGoal", False)),
        "blockingImpact": bool(raw.get("blockingImpact", False)),
        "approvalPending": bool(raw.get("approvalPending", False)),
        "deadline": bool(raw.get("deadline", False)),
        "conflict": bool(raw.get("conflict", False)),
        "taskFailure": bool(raw.get("taskFailure", False)),
        "recentlyChanged": bool(raw.get("recentlyChanged", False)),
        "recency": _as_float(raw.get("recency")),
        "relatedGoalId": raw.get("relatedGoalId"),
        "relatedBeliefRefs": _as_str_list(raw.get("relatedBeliefRefs")),
        "relatedTaskIds": _as_str_list(raw.get("relatedTaskIds")),
        "relatedDraftIds": _as_str_list(raw.get("relatedDraftIds")),
        "targetApps": _as_str_list(raw.get("targetApps")),
        "lifecycle": raw.get("lifecycle") or "turn_bound",
        "createdAt": raw.get("createdAt") or _now_iso(),
        "expiresAt": raw.get("expiresAt"),
        "suppressionReason": None,
        "provenance": raw.get("provenance") or "workspace",
    }
    # A stale/superseded candidate is still normalized but flagged for suppression.
    if raw.get("stale"):
        cand["_stale"] = True
    if raw.get("superseded"):
        cand["_superseded"] = True
    cand["salienceClass"] = classify_salience(cand)
    cand["candidateId"] = _candidate_id(cand)
    return cand


def _as_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _as_str_list(v, limit=20):
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, (list, tuple)):
        return []
    return [str(x) for x in v if x is not None][:limit]


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _candidate_id(cand):
    key = "%s|%s|%s" % (cand.get("sourceType"), cand.get("sourceRef"),
                        cand.get("correlationId") or "")
    return "wc." + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


# ── Deduplication / collapse ────────────────────────────────────────────────

def deduplicate_candidates(cands):
    """Collapse duplicates deterministically. Exact keys only (no fuzzy merge).

    1. Same (sourceType, sourceRef) -> keep the higher-salience instance, union
       the related-ref lists.
    2. A blocker surfaced via both a GOAL and a DRAFT (same relatedGoalId) is
       merged into ONE blocker candidate carrying both goal + draft refs.
    Returns (kept, collapsed) where collapsed carries DUPLICATE suppression."""
    kept = {}
    order = []
    collapsed = []
    for c in cands:
        if c is None:
            continue
        key = (c["sourceType"], c["sourceRef"])
        if key not in kept:
            kept[key] = c
            order.append(key)
        else:
            prev = kept[key]
            winner, loser = _pick_higher(prev, c)
            _union_refs(winner, loser)
            kept[key] = winner
            collapsed.append(_suppressed(loser, "DUPLICATE"))

    # Blocker collapse across source types by (relatedGoalId).
    blockers = [k for k in order if kept[k]["category"] == "blocker"
                and kept[k].get("relatedGoalId")]
    by_goal = {}
    for k in blockers:
        g = kept[k]["relatedGoalId"]
        by_goal.setdefault(g, []).append(k)
    for g, keys in by_goal.items():
        if len(keys) <= 1:
            continue
        # canonical winner = the GOAL-sourced blocker if present, else highest.
        winner_key = None
        for k in keys:
            if kept[k]["sourceType"] == "GOAL":
                winner_key = k
                break
        if winner_key is None:
            winner_key = _highest_key(kept, keys)
        for k in keys:
            if k == winner_key:
                continue
            _union_refs(kept[winner_key], kept[k])
            collapsed.append(_suppressed(kept[k], "DUPLICATE"))
            order.remove(k)
            del kept[k]
    return [kept[k] for k in order], collapsed


def _pick_higher(a, b):
    ra, rb = _CLASS_RANK.get(a.get("salienceClass"), _LOWEST_RANK), \
        _CLASS_RANK.get(b.get("salienceClass"), _LOWEST_RANK)
    return (a, b) if ra <= rb else (b, a)


def _highest_key(kept, keys):
    return min(keys, key=lambda k: _CLASS_RANK.get(kept[k].get("salienceClass"), _LOWEST_RANK))


def _union_refs(winner, loser):
    for field in ("relatedBeliefRefs", "relatedTaskIds", "relatedDraftIds", "targetApps"):
        seen = list(winner.get(field) or [])
        for x in (loser.get(field) or []):
            if x not in seen:
                seen.append(x)
        winner[field] = seen
    if not winner.get("relatedGoalId") and loser.get("relatedGoalId"):
        winner["relatedGoalId"] = loser["relatedGoalId"]


def _suppressed(c, reason):
    return {"candidateId": c.get("candidateId"), "sourceType": c.get("sourceType"),
            "sourceRef": c.get("sourceRef"), "suppressionReason": reason,
            "expiresAt": c.get("expiresAt")}


# ── Ranking (deterministic comparator) ──────────────────────────────────────

def _sort_key(c):
    rank = _CLASS_RANK.get(c.get("salienceClass"), _LOWEST_RANK)
    rec = c.get("recency")
    rec = rec if isinstance(rec, (int, float)) else 0.0
    # ascending rank; then higher recency first (negate); then stable sourceRef.
    return (rank, -rec, str(c.get("sourceRef") or ""))


def rank_candidates(cands):
    """Return candidates sorted by (class rank, recency desc, sourceRef asc)."""
    return sorted([c for c in cands if c is not None], key=_sort_key)


# ── Snapshot assembly ───────────────────────────────────────────────────────

def _clamp_capacity(capacity):
    try:
        n = int(capacity)
    except (TypeError, ValueError):
        n = DEFAULT_SECONDARY_CAPACITY
    return max(0, min(MAX_SECONDARY_CAPACITY, n))


def build_workspace_snapshot(candidates, capacity=DEFAULT_SECONDARY_CAPACITY,
                             correlation_id=None, channel=None, now_ms=None):
    """Build a bounded, ephemeral WorkspaceSnapshot. Never raises.

    Pipeline: normalize -> drop expired/superseded -> dedup -> rank -> select
    (1 primary + <=capacity secondary) -> record suppressed/deferred + trace."""
    t0 = time.time()
    cap = _clamp_capacity(capacity)
    corr = correlation_id or ("w." + hashlib.sha256(
        (str(channel) + "|" + str(t0)).encode("utf-8")).hexdigest()[:16])
    fallback_reason = None
    suppressed = []
    deferred = []
    trace = []
    try:
        raw = candidates or []
        norm = []
        for r in raw:
            c = normalize_candidate(r, correlation_id=corr)
            if c is None:
                trace.append("dropped malformed candidate")
                continue
            # Expiry / lifecycle exclusion (turn-bound recompute; explicit only).
            if c.pop("_superseded", False):
                suppressed.append(_suppressed(c, "SUPERSEDED"))
                continue
            if c.pop("_stale", False):
                suppressed.append(_suppressed(c, "STALE"))
                continue
            if _is_expired(c, now_ms):
                deferred.append(_suppressed(c, "EXPIRED"))
                continue
            norm.append(c)

        kept, collapsed = deduplicate_candidates(norm)
        suppressed.extend(collapsed)
        ranked = rank_candidates(kept)

        primary = ranked[0] if ranked else None
        rest = ranked[1:] if ranked else []
        secondary = rest[:cap]
        for c in rest[cap:]:
            suppressed.append(_suppressed(c, "CAPACITY_LIMIT"))

        # Trace: named deciding rule + per-candidate class.
        if primary is not None:
            trace.append("primary=%s by %s" % (primary["candidateId"], primary["salienceClass"]))
        for c in secondary:
            trace.append("secondary=%s (%s)" % (c["candidateId"], c["salienceClass"]))
        for s in suppressed:
            trace.append("suppressed=%s: %s" % (s.get("candidateId"), s.get("suppressionReason")))
        for d in deferred:
            trace.append("deferred=%s: %s" % (d.get("candidateId"), d.get("suppressionReason")))

        selection_reason = (primary["salienceClass"] if primary is not None
                            else "NO_CANDIDATE")
    except Exception:  # absolute safety — attention must never break a turn
        logger.debug("workspace: build_workspace_snapshot failed", exc_info=True)
        primary, secondary = None, []
        selection_reason = "ERROR"
        fallback_reason = "exception"

    return {
        "schemaVersion": WORKSPACE_SCHEMA_VERSION,
        "correlationId": corr,
        "timestamp": _now_iso(),
        "channel": channel,
        "primaryFocus": primary,
        "secondaryItems": secondary,
        "suppressedItems": suppressed,
        "deferredItems": deferred,
        "capacity": {"primary": 1, "secondary": cap},
        "selectionReason": selection_reason,
        "arbitrationTrace": trace,
        "fallbackReason": fallback_reason,
        "expiresAt": None,  # turn-bound; consumed within the turn
        "_durationMs": round((time.time() - t0) * 1000),
    }


def _is_expired(cand, now_ms):
    exp = cand.get("expiresAt")
    if not exp:
        return False
    try:
        import datetime as _dt
        t = _dt.datetime.fromisoformat(str(exp).replace("Z", "+00:00")).timestamp() * 1000
    except Exception:
        return False
    now = now_ms if now_ms is not None else time.time() * 1000
    return t < now


# ── Consumption helpers ──────────────────────────────────────────────────────

def selected_candidates(snapshot):
    """Primary + secondary as a flat list (the workspace-selected attention set)."""
    s = snapshot or {}
    out = []
    if s.get("primaryFocus"):
        out.append(s["primaryFocus"])
    out.extend(s.get("secondaryItems") or [])
    return out


def has_primary(snapshot):
    return bool((snapshot or {}).get("primaryFocus"))


def explain_selection(snapshot):
    """Human-readable ordered explanation of the selection (no CoT)."""
    return list((snapshot or {}).get("arbitrationTrace") or [])


# ── Safe, non-CoT trace for decisions.log ────────────────────────────────────

def build_trace(snapshot):
    s = snapshot or {}
    prim = s.get("primaryFocus") or {}
    counts = {}
    for c in selected_candidates(s):
        counts[c.get("sourceType")] = counts.get(c.get("sourceType"), 0) + 1
    return {
        "correlation_id": s.get("correlationId"),
        "candidate_count": len(selected_candidates(s)) + len(s.get("suppressedItems") or [])
        + len(s.get("deferredItems") or []),
        "source_type_counts": counts,
        "selected_primary_id": prim.get("candidateId"),
        "selected_primary_class": prim.get("salienceClass"),
        "selected_secondary_ids": [c.get("candidateId") for c in (s.get("secondaryItems") or [])],
        "suppressed_ids": [x.get("candidateId") for x in (s.get("suppressedItems") or [])],
        "arbitration_rules_applied": len(SALIENCE_CLASSES),
        "deciding_rule": s.get("selectionReason"),
        "capacity": s.get("capacity"),
        "duration_ms": s.get("_durationMs"),
        "fallback_reason": s.get("fallbackReason"),
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "timestamp": s.get("timestamp"),
    }
