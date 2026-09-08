# -*- coding: utf-8 -*-
"""Offline unit tests for Slice 10 Global Workspace / Attention V1.
No network, no Hermes, no VM. World/Goal/Task/Draft reads are faked by
monkeypatching world_context module attributes. Import path is set by the runner
(staged flat dir or the lilith_router package)."""
import unittest

try:
    from lilith_router import workspace as W
    from lilith_router import world_context as wc
except Exception:  # staged flat dir
    import workspace as W
    import world_context as wc


# ── helpers ──────────────────────────────────────────────────────────────────

def cand(**kw):
    base = {"sourceType": "GOAL", "sourceRef": "g.x", "category": "goal",
            "summary": "goal g.x"}
    base.update(kw)
    return base


def snap(cands, capacity=4, channel="lilith_os"):
    return W.build_workspace_snapshot(cands, capacity=capacity,
                                      correlation_id="w.test", channel=channel)


# ── A/D/E bounded construction, one primary, capacity ────────────────────────

class SnapshotShapeTests(unittest.TestCase):
    def test_bounded_construction_and_one_primary(self):  # A, D
        s = snap([cand(sourceRef="g.1", isFocusGoal=True),
                  cand(sourceRef="g.2"), cand(sourceRef="g.3")])
        self.assertIsNotNone(s["primaryFocus"])
        self.assertEqual(s["schemaVersion"], W.WORKSPACE_SCHEMA_VERSION)
        self.assertIsInstance(s["secondaryItems"], list)
        # exactly one primary (a dict, not a list)
        self.assertIsInstance(s["primaryFocus"], dict)

    def test_capacity_enforced_and_clamped(self):  # E
        many = [cand(sourceRef="g.%d" % i) for i in range(20)]
        s = snap(many, capacity=4)
        self.assertLessEqual(len(s["secondaryItems"]), 4)
        # overflow suppressed with CAPACITY_LIMIT
        reasons = {x["suppressionReason"] for x in s["suppressedItems"]}
        self.assertIn("CAPACITY_LIMIT", reasons)
        # hard clamp: capacity 999 -> MAX_SECONDARY_CAPACITY
        s2 = snap(many, capacity=999)
        self.assertEqual(s2["capacity"]["secondary"], W.MAX_SECONDARY_CAPACITY)
        s3 = snap(many, capacity=-5)
        self.assertEqual(s3["capacity"]["secondary"], 0)

    def test_exact_ref_preservation(self):  # B
        c = cand(sourceRef="g.1", relatedGoalId="g.1", relatedDraftIds=["d.1", "d.2"],
                 targetApps=["14"])
        s = snap([c])
        p = s["primaryFocus"]
        self.assertEqual(p["relatedGoalId"], "g.1")
        self.assertEqual(p["relatedDraftIds"], ["d.1", "d.2"])
        self.assertEqual(p["targetApps"], ["14"])


# ── C dedup / O collapse ─────────────────────────────────────────────────────

class DedupTests(unittest.TestCase):
    def test_same_sourceref_collapses(self):  # C
        s = snap([cand(sourceRef="g.1", userReferenced=True),
                  cand(sourceRef="g.1")])
        ids = [W._candidate_id  # noqa: just ensure only one kept
               ]
        kept = ([s["primaryFocus"]] if s["primaryFocus"] else []) + s["secondaryItems"]
        refs = [c["sourceRef"] for c in kept]
        self.assertEqual(refs.count("g.1"), 1)
        self.assertTrue(any(x["suppressionReason"] == "DUPLICATE" for x in s["suppressedItems"]))

    def test_goal_and_draft_blocker_collapse(self):  # O
        goal_blocker = cand(sourceType="GOAL", sourceRef="blocker:g.1", category="blocker",
                            relatedGoalId="g.1", relatedDraftIds=["d.1"], userReferenced=True)
        draft_blocker = cand(sourceType="DRAFT", sourceRef="d.1", category="blocker",
                             relatedGoalId="g.1", relatedDraftIds=["d.1"], userReferenced=True)
        s = snap([goal_blocker, draft_blocker])
        kept = ([s["primaryFocus"]] if s["primaryFocus"] else []) + s["secondaryItems"]
        blockers = [c for c in kept if c["category"] == "blocker"]
        self.assertEqual(len(blockers), 1)
        # merged winner is the GOAL-sourced blocker carrying the draft ref
        self.assertEqual(blockers[0]["sourceType"], "GOAL")
        self.assertIn("d.1", blockers[0]["relatedDraftIds"])


# ── F/G/H user-directed vs Executive focus ───────────────────────────────────

class SalienceTests(unittest.TestCase):
    def test_user_override_beats_focus_continuity(self):  # F
        focus = cand(sourceRef="g.17", isFocusGoal=True)
        override = cand(sourceRef="g.14", userOverrideTarget=True, targetApps=["14"])
        s = snap([focus, override])
        self.assertEqual(s["primaryFocus"]["sourceRef"], "g.14")
        self.assertEqual(s["selectionReason"], "USER_OVERRIDE_TARGET")

    def test_user_referenced_blocker_beats_focus(self):  # F/K
        focus = cand(sourceRef="g.17", isFocusGoal=True)
        ref_blocker = cand(sourceType="GOAL", sourceRef="blocker:g.14", category="blocker",
                          userReferenced=True, relatedGoalId="g.14", targetApps=["14"])
        s = snap([focus, ref_blocker])
        self.assertEqual(s["primaryFocus"]["sourceRef"], "blocker:g.14")
        self.assertEqual(s["selectionReason"], "USER_REFERENCED_BLOCKER")

    def test_deterministic_and_explainable(self):  # R, S
        cands = [cand(sourceRef="g.17", isFocusGoal=True),
                 cand(sourceType="GOAL", sourceRef="blocker:g.14", category="blocker",
                      userReferenced=True, relatedGoalId="g.14")]
        s1 = snap(cands)
        s2 = snap(list(reversed(cands)))
        self.assertEqual(s1["primaryFocus"]["sourceRef"], s2["primaryFocus"]["sourceRef"])
        self.assertTrue(s1["arbitrationTrace"])
        self.assertTrue(any("by USER_REFERENCED_BLOCKER" in t for t in s1["arbitrationTrace"]))

    def test_system_critical_defined_but_synthetic(self):  # Decision 5
        self.assertIn("SYSTEM_CRITICAL", W.SALIENCE_CLASSES)
        sc = cand(sourceType="SYSTEM_HEALTH", sourceRef="gw", category="system_health",
                  systemCritical=True)
        other = cand(sourceRef="g.1", isFocusGoal=True)
        s = snap([other, sc])
        self.assertEqual(s["primaryFocus"]["sourceRef"], "gw")
        self.assertEqual(s["selectionReason"], "SYSTEM_CRITICAL")


# ── J/P/Q/T suppression, expiry, malformed ───────────────────────────────────

class SuppressionTests(unittest.TestCase):
    def test_stale_belief_suppressed(self):  # J
        stale = cand(sourceType="WORLD_BELIEF", sourceRef="k.stale", category="belief",
                     stale=True)
        s = snap([cand(sourceRef="g.1", isFocusGoal=True), stale])
        self.assertTrue(any(x["suppressionReason"] == "STALE" for x in s["suppressedItems"]))

    def test_expired_excluded(self):  # P
        expired = cand(sourceRef="g.old", expiresAt="2000-01-01T00:00:00Z")
        s = snap([expired])
        self.assertIsNone(s["primaryFocus"])
        self.assertTrue(any(x["suppressionReason"] == "EXPIRED" for x in s["deferredItems"]))

    def test_suppression_reasons_recorded(self):  # Q
        s = snap([cand(sourceRef="g.%d" % i) for i in range(10)], capacity=2)
        for x in s["suppressedItems"]:
            self.assertIn(x["suppressionReason"], W.SUPPRESSION_REASONS)

    def test_malformed_rejected(self):  # T
        self.assertIsNone(W.normalize_candidate({"sourceType": "GOAL"}))       # missing fields
        self.assertIsNone(W.normalize_candidate({"sourceType": "GOAL", "sourceRef": "x",
                                                 "category": "goal"}))          # no summary
        self.assertIsNone(W.normalize_candidate("not a dict"))
        s = snap([{"bogus": 1}, cand(sourceRef="g.1")])
        self.assertEqual(s["primaryFocus"]["sourceRef"], "g.1")


# ── trace ─────────────────────────────────────────────────────────────────────

class TraceTests(unittest.TestCase):
    def test_trace_is_safe_and_non_cot(self):
        s = snap([cand(sourceRef="g.1", isFocusGoal=True), cand(sourceRef="g.2")])
        tr = W.build_trace(s)
        for k in ("correlation_id", "candidate_count", "selected_primary_id",
                  "deciding_rule", "capacity", "duration_ms", "schema_version"):
            self.assertIn(k, tr)
        # no chain-of-thought fields leak
        for forbidden in ("thinking", "scratchpad", "chain_of_thought"):
            self.assertNotIn(forbidden, tr)


# ── world_context extraction (faked sources) ─────────────────────────────────

class _Fakes:
    """Install/restore world_context source fakes."""
    def __init__(self, goals, focus, drafts=None, tasks=None, world=None,
                 world_by_app=None):
        self.goals, self.focus = goals, focus
        self.drafts, self.tasks = drafts or {"drafts": []}, tasks or {"tasks": []}
        self.world, self.world_by_app = world or {"beliefs": []}, world_by_app or {}
        self.posted = []  # capture any POST attempts (must stay empty)

    def __enter__(self):
        self._orig = {k: getattr(wc, k) for k in
                      ("fetch_goals", "fetch_goal_focus", "fetch_world", "_get_json")}
        wc.fetch_goals = lambda *a, **k: self.goals
        wc.fetch_goal_focus = lambda *a, **k: self.focus
        def _fw(entity_type=None, entity_id=None):
            if entity_id is not None:
                return self.world_by_app.get(str(entity_id), {"beliefs": []})
            return self.world
        wc.fetch_world = _fw
        def _gj(path, timeout=None):
            if path.startswith("/os/drafts"):
                return self.drafts
            if path.startswith("/os/tasks"):
                return self.tasks
            return None
        wc._get_json = _gj
        # guard: any POST helper call is a violation
        for name in ("_post_draft", "_post_goal_json"):
            if hasattr(wc, name):
                self._orig[name] = getattr(wc, name)
                setattr(wc, name, self._blowup(name))
        return self

    def _blowup(self, name):
        def f(*a, **k):
            self.posted.append(name)
            raise AssertionError("workspace attempted a write via %s" % name)
        return f

    def __exit__(self, *exc):
        for k, v in self._orig.items():
            setattr(wc, k, v)


APP14_BLOCKED_GOAL = {"goalId": "g.14", "title": "Follow up on 14", "type": "career.followup",
                      "lifecycleState": "BLOCKED", "priority": "NORMAL",
                      "blockedReason": "unsent drafts", "blockedBy": ["d.1", "d.2"],
                      "target": {"type": "career.application", "id": "14"},
                      "updatedAt": "2026-09-08T00:00:00Z"}
APP17_ACTIVE_GOAL = {"goalId": "g.17", "title": "Prepare app 17", "type": "career.prep",
                     "lifecycleState": "ACTIVE", "priority": "HIGH",
                     "target": {"type": "career.application", "id": "17"},
                     "updatedAt": "2026-09-08T00:00:00Z"}
FOCUS_17 = {"focus": {"goalId": "g.17", "title": "Prepare app 17"},
            "arbitration": {"ruleFired": "priority"}}
DRAFTS_14 = {"drafts": [
    {"draftId": "d.1", "kind": "career_followup", "status": "created",
     "target": {"id": "14"}, "updatedAt": "2026-09-08T00:00:00Z"},
    {"draftId": "d.2", "kind": "career_followup", "status": "created",
     "target": {"id": "14"}, "updatedAt": "2026-09-08T00:00:00Z"},
    {"draftId": "d.9", "kind": "career_followup", "status": "sent",
     "target": {"id": "99"}}]}


class ExtractionTests(unittest.TestCase):
    def test_user_referenced_marks_target_without_override_phrase(self):  # B, extra
        ov = wc.detect_attention_override("Why is application 14 blocked?")
        self.assertFalse(ov["override"])
        self.assertEqual(ov["referenced_app_id"], "14")

    def test_override_distinguished_from_reference(self):  # B, extra
        ov = wc.detect_attention_override("Forget application 17 for now; focus on application 14.")
        self.assertTrue(ov["override"])
        self.assertEqual(ov["override_app_id"], "14")   # new target (last)

    def test_referenced_blocker_becomes_primary_focus_not_executive(self):  # G/H/K
        with _Fakes(goals={"goals": [APP17_ACTIVE_GOAL, APP14_BLOCKED_GOAL]},
                    focus=FOCUS_17, drafts=DRAFTS_14) as fk:
            rintent = wc.detect_reasoning_intent("Why is application 14 blocked?")
            cands = wc.build_attention_candidates(
                "Why is application 14 blocked?", "lilith_os:home", rintent, channel="lilith_os")
            s = snap(cands)
            # Workspace primary is the app14 blocker...
            self.assertEqual(s["primaryFocus"]["category"], "blocker")
            self.assertIn("14", (s["primaryFocus"].get("targetApps") or []))
            self.assertEqual(s["selectionReason"], "USER_REFERENCED_BLOCKER")
            # ...Executive focus is untouched (still g.17) and NO write happened.
            self.assertEqual(fk.focus["focus"]["goalId"], "g.17")
            self.assertEqual(fk.posted, [])

    def test_unrelated_draft_not_selected(self):  # L
        with _Fakes(goals={"goals": [APP14_BLOCKED_GOAL]}, focus=FOCUS_17,
                    drafts=DRAFTS_14):
            rintent = wc.detect_reasoning_intent("Why is application 14 blocked?")
            cands = wc.build_attention_candidates(
                "Why is application 14 blocked?", "k", rintent, channel="lilith_os")
            refs = [c["sourceRef"] for c in cands]
            self.assertNotIn("d.9", refs)   # sent draft for app99 is not a candidate

    def test_belief_conflict_candidate_stale_flagged(self):  # I/J
        world14 = {"14": {"beliefs": [
            {"key": "career.application:14:status", "entity_type": "career.application",
             "entity_id": "14", "predicate": "status", "value": "unclear",
             "lifecycle_state": "CONFLICTED", "epistemic_state": "OBSERVED",
             "confidence": {"value": 0.5, "tier": "medium"}, "updated_at": "2026-09-01T00:00:00Z",
             "contradicted_by": ["career.application:14:status#alt"]},
            {"key": "career.application:14:role", "entity_type": "career.application",
             "entity_id": "14", "predicate": "role", "value": "SWE",
             "lifecycle_state": "STALE", "epistemic_state": "OBSERVED",
             "confidence": {"value": 0.4, "tier": "low"}, "updated_at": "2026-01-01T00:00:00Z"}]}}
        with _Fakes(goals={"goals": [APP14_BLOCKED_GOAL]}, focus=FOCUS_17,
                    drafts=DRAFTS_14, world_by_app=world14):
            rintent = wc.detect_reasoning_intent("What is uncertain about application 14?")
            cands = wc.build_attention_candidates(
                "What is uncertain about application 14?", "k", rintent, channel="lilith_os")
            beliefs = [c for c in cands if c["sourceType"] == "WORLD_BELIEF"]
            self.assertTrue(any(c.get("conflict") for c in beliefs))
            self.assertTrue(any(c.get("stale") for c in beliefs))


# ── bounded ReasoningInput (Refinement C) ────────────────────────────────────

class BoundedReasoningInputTests(unittest.TestCase):
    def _snapshot_primary_app14(self):
        primary = cand(sourceType="GOAL", sourceRef="blocker:g.14", category="blocker",
                       relatedGoalId="g.14", relatedDraftIds=["d.1", "d.2"], targetApps=["14"],
                       userReferenced=True)
        return snap([primary])

    def test_excludes_unrelated_unselected_rows(self):  # Refinement C test 1
        world14 = {"14": {"beliefs": [
            {"key": "career.application:14:status", "entity_type": "career.application",
             "entity_id": "14", "predicate": "status", "value": "await",
             "lifecycle_state": "ACTIVE", "epistemic_state": "OBSERVED",
             "confidence": {"value": 0.8, "tier": "high"}, "provenance": []}]}}
        goals = {"goals": [APP14_BLOCKED_GOAL, APP17_ACTIVE_GOAL,
                           {"goalId": "g.99", "title": "unrelated", "type": "x",
                            "lifecycleState": "ACTIVE", "priority": "LOW",
                            "target": {"type": "career.application", "id": "99"}}]}
        drafts = {"drafts": DRAFTS_14["drafts"] + [
            {"draftId": "d.99", "kind": "career_followup", "status": "created",
             "target": {"id": "99"}}]}
        with _Fakes(goals=goals, focus=FOCUS_17, drafts=drafts, world_by_app=world14):
            rintent = wc.detect_reasoning_intent("Why is application 14 blocked?")
            s = self._snapshot_primary_app14()
            ri = wc.build_reasoning_input_bounded("Why is application 14 blocked?",
                                                  "k", rintent, s, channel="lilith_os")
            self.assertIsNotNone(ri)
            self.assertEqual(ri["boundedBy"], "workspace")
            # unrelated app99 goal/draft excluded
            self.assertFalse(any("g.99" in g for g in ri["goalCandidates"]))
            self.assertFalse(any("d.99" in d for d in ri["relevantDrafts"]))
            # unrelated app99 beliefs never fetched (world_by_app has only 14)

    def test_support_expansion_retains_linked(self):  # Refinement C test 2
        goals = {"goals": [APP14_BLOCKED_GOAL, APP17_ACTIVE_GOAL]}
        with _Fakes(goals=goals, focus=FOCUS_17, drafts=DRAFTS_14):
            rintent = wc.detect_reasoning_intent("Why is application 14 blocked?")
            s = self._snapshot_primary_app14()
            ri = wc.build_reasoning_input_bounded("Why is application 14 blocked?",
                                                  "k", rintent, s, channel="lilith_os")
            # linked goal g.14 retained; linked drafts d.1/d.2 retained
            self.assertTrue(any("g.14" in g for g in ri["goalCandidates"]))
            self.assertTrue(any("d.1" in d for d in ri["relevantDrafts"]))
            self.assertTrue(any("d.2" in d for d in ri["relevantDrafts"]))
            # Executive focus goal g.17 retained for continuity reporting
            self.assertTrue(any("g.17" in g for g in ri["goalCandidates"]))
            self.assertIn("g.17", ri["currentFocus"])

    def test_no_primary_returns_none(self):
        empty = snap([])
        ri = wc.build_reasoning_input_bounded("x", "k", {"mode": None}, empty)
        self.assertIsNone(ri)

    def test_failure_restores_slice9_builder(self):  # Refinement C test 3
        called = {"base": 0}
        orig = wc.build_reasoning_input
        wc.build_reasoning_input = lambda *a, **k: (called.__setitem__("base", called["base"] + 1) or {"boundedBy": None, "base": True})
        orig_bounded = wc.build_reasoning_input_bounded
        wc.build_reasoning_input_bounded = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            s = self._snapshot_primary_app14()
            ri = wc.select_reasoning_input("x", "k", {"mode": None}, s, channel="lilith_os")
            self.assertEqual(called["base"], 1)     # fell back to Slice 9 builder
            self.assertTrue(ri.get("base"))
        finally:
            wc.build_reasoning_input = orig
            wc.build_reasoning_input_bounded = orig_bounded

    def test_shadow_uses_base_builder(self):
        called = {"base": 0}
        orig = wc.build_reasoning_input
        wc.build_reasoning_input = lambda *a, **k: (called.__setitem__("base", called["base"] + 1) or {"base": True})
        try:
            ri = wc.select_reasoning_input("x", "k", {"mode": None}, None)  # snapshot=None => shadow/off
            self.assertEqual(called["base"], 1)
        finally:
            wc.build_reasoning_input = orig


if __name__ == "__main__":
    unittest.main()
