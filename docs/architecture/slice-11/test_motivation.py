# -*- coding: utf-8 -*-
"""Offline unit tests for Slice 11 Motivation / Homeostasis V1.
No network, no Hermes, no VM. All source state is synthetic. World/Goal/Task
reads (world_context adapters) are faked by monkeypatching module attributes.
Import path supports the lilith_router package (VM) or a staged flat dir."""
import unittest

try:
    from lilith_router import motivation as M
    from lilith_router import workspace as W
    from lilith_router import world_context as wc
except Exception:  # staged flat dir
    import motivation as M
    import workspace as W
    import world_context as wc


def bcond(key, lifecycle, entity="14", contradicted=False):
    return {"key": key, "entity_id": entity, "lifecycle": lifecycle,
            "contradicted": contradicted}


def gcond(gid, state="BLOCKED", **kw):
    d = {"goalId": gid, "lifecycleState": state, "isFocus": False,
         "userReferenced": False, "source": "SYSTEM", "blockedBy": [],
         "targetApp": None, "hardBlockerFailedTaskIds": []}
    d.update(kw)
    return d


class Coherence(unittest.TestCase):
    def test_none_satisfied(self):  # T-UNK: absence, never fabricated
        d = M.classify_coherence([])
        self.assertEqual(d["intensityClass"], "SATISFIED")
        self.assertEqual(d["sourceRefs"], [])

    def test_stale_only_mild(self):  # F
        d = M.classify_coherence([bcond("b.1", "STALE")])
        self.assertEqual(d["intensityClass"], "MILD")
        self.assertIn("WORLD_STALE", d["causeCodes"])

    def test_conflicted_significant(self):  # E
        d = M.classify_coherence([bcond("b.1", "CONFLICTED")])
        self.assertEqual(d["intensityClass"], "SIGNIFICANT")
        self.assertIn("WORLD_CONFLICTED", d["causeCodes"])

    def test_critical_requires_provable_dep(self):  # T-CRIT / decision 4
        conflicted = [bcond("b.crit", "CONFLICTED")]
        capped = M.classify_coherence(conflicted)
        self.assertEqual(capped["intensityClass"], "SIGNIFICANT")  # not provable -> cap
        crit = M.classify_coherence(conflicted, critical_belief_keys=["b.crit"])
        self.assertEqual(crit["intensityClass"], "CRITICAL")       # provable typed dep

    def test_orthogonality_epistemic_not_lifecycle(self):  # T-ORTH
        # VERIFIED/OBSERVED are epistemic; supplied as a (wrong) lifecycle they
        # are NOT coherence pressure — only CONFLICTED/STALE lifecycle counts.
        for wrong in ("VERIFIED", "OBSERVED", "ACTIVE", "USER_ASSERTED", "INFERRED"):
            d = M.classify_coherence([bcond("b.x", wrong)])
            self.assertEqual(d["intensityClass"], "SATISFIED", wrong)

    def test_contradicted_flag_is_conflict(self):
        d = M.classify_coherence([bcond("b.1", "ACTIVE", contradicted=True)])
        self.assertEqual(d["intensityClass"], "SIGNIFICANT")


class GoalCompletion(unittest.TestCase):
    def test_no_blocked_satisfied(self):  # H
        d = M.classify_goal_completion([gcond("g.1", state="ACTIVE"),
                                        gcond("g.2", state="COMPLETED")])
        self.assertEqual(d["intensityClass"], "SATISFIED")

    def test_nonfocus_blocked_mild(self):
        d = M.classify_goal_completion([gcond("g.1")])
        self.assertEqual(d["intensityClass"], "MILD")

    def test_focus_blocked_significant(self):  # G
        d = M.classify_goal_completion([gcond("g.1", isFocus=True)])
        self.assertEqual(d["intensityClass"], "SIGNIFICANT")
        self.assertIn("GOAL_BLOCKED_FOCUS", d["causeCodes"])

    def test_user_requested_ref_significant(self):
        d = M.classify_goal_completion([gcond("g.1", userReferenced=True, source="USER_REQUESTED")])
        self.assertEqual(d["intensityClass"], "SIGNIFICANT")
        self.assertIn("GOAL_USER_REQUESTED_BLOCKED", d["causeCodes"])

    def test_failed_linked_task_not_in_blockedby_not_critical(self):  # T-NOPATH / decision 5
        # A failed linked task that is NOT a typed blocker never yields CRITICAL.
        d = M.classify_goal_completion([gcond("g.1", isFocus=True,
                                              hardBlockerFailedTaskIds=[])])
        self.assertEqual(d["intensityClass"], "SIGNIFICANT")

    def test_typed_hard_blocker_failed_task_critical(self):  # T-CRIT
        d = M.classify_goal_completion([gcond("g.1", isFocus=True,
                                              hardBlockerFailedTaskIds=["t.9"])])
        self.assertEqual(d["intensityClass"], "CRITICAL")
        self.assertIn("HARD_BLOCKER_FAILED_TASK", d["causeCodes"])
        self.assertIn("t.9", d["relatedTaskIds"])


class Schema(unittest.TestCase):
    def test_no_float_intensity(self):  # B
        d = M.classify_goal_completion([gcond("g.1", isFocus=True)])
        self.assertIn(d["intensityClass"], M.INTENSITY_CLASSES)
        self.assertNotIn("intensity", d)
        for v in d.values():
            self.assertNotIsInstance(v, float)

    def test_no_transition_fields(self):  # T-NOTRANS
        d = M.classify_coherence([bcond("b.1", "CONFLICTED")])
        for k in ("priorIntensity", "newIntensity", "homeostaticState"):
            self.assertNotIn(k, d)  # T-NODUP + decision 6

    def test_no_affect_keys(self):  # Z / AA / AB
        d = M.classify_coherence([bcond("b.1", "CONFLICTED")])
        for k in ("happy", "sad", "lonely", "affect", "emotion", "curiosity", "social"):
            self.assertNotIn(k, d)

    def test_drive_types_fixed(self):  # AA/AB no social/curiosity drive
        self.assertEqual(set(M.DRIVE_TYPES), {"COHERENCE", "GOAL_COMPLETION", "SAFETY"})


class Snapshot(unittest.TestCase):
    def _snap(self, raw_refs=None):
        return M.build_snapshot(
            coherence=M.classify_coherence([bcond("b.1", "CONFLICTED")]),
            goal_completion=M.classify_goal_completion([gcond("g.1", isFocus=True)]),
            safety=None, raw_refs=raw_refs, correlation_id="m.test", channel="lilith_os")

    def test_two_drives_coexist(self):  # L / M
        s = self._snap()
        self.assertEqual(len(s["drives"]), 2)
        self.assertEqual(set(s["activeDrives"]), {"COHERENCE", "GOAL_COMPLETION"})
        # M: no single aggregate numeric utility that decides.
        self.assertIsInstance(s["highestIntensityClass"], str)
        self.assertNotIn("utility", s)
        self.assertNotIn("score", s)

    def test_satisfied_drives_field(self):  # T-SAT
        s = M.build_snapshot(coherence=M.classify_coherence([]),
                             goal_completion=M.classify_goal_completion([]),
                             correlation_id="m.test", channel="x")
        self.assertIn("satisfiedDrives", s)
        self.assertNotIn("resolvedDrives", s)
        self.assertEqual(set(s["satisfiedDrives"]), {"COHERENCE", "GOAL_COMPLETION"})

    def test_deterministic(self):  # D / AD restart-identical
        self.assertEqual(self._snap()["drives"], self._snap()["drives"])

    def test_source_unavailable_partial_no_fabrication(self):  # K
        s = M.build_snapshot(coherence=None, goal_completion=None, safety=None,
                             partial=True, correlation_id="m.t", channel="x")
        self.assertTrue(s["partial"])
        self.assertEqual(s["drives"], [])
        self.assertEqual(s["activeDrives"], [])

    def test_dedup_candidate_eligibility(self):  # T-SLOT
        # ref represented by a raw candidate -> NOT eligible (no extra slot).
        s = self._snap(raw_refs={"b.1", "g.1"})
        for d in s["drives"]:
            self.assertFalse(d["candidateEligible"])
        self.assertEqual(M.to_attention_candidates(s), [])
        # unrepresented -> eligible.
        s2 = self._snap(raw_refs=set())
        self.assertTrue(any(d["candidateEligible"] for d in s2["drives"]))
        self.assertTrue(len(M.to_attention_candidates(s2)) >= 1)

    def test_safety_synthetic_only(self):  # decision 13
        s = self._snap()
        self.assertNotIn("SAFETY", [d["driveType"] for d in s["drives"]])
        saf = M.classify_safety_synthetic({"intensityClass": "SIGNIFICANT"})
        self.assertEqual(saf["intensityClass"], "SIGNIFICANT")
        self.assertEqual(M.classify_safety_synthetic(None)["intensityClass"], "SATISFIED")


class WorkspaceIntegration(unittest.TestCase):
    def test_motivation_candidate_maps_to_pressure(self):  # T
        s = M.build_snapshot(
            coherence=M.classify_coherence([bcond("b.1", "CONFLICTED")]),
            goal_completion=M.classify_goal_completion([]),
            raw_refs=set(), correlation_id="m.t", channel="x")
        cands = M.to_attention_candidates(s)
        self.assertTrue(cands)
        norm = W.normalize_candidate(cands[0], correlation_id="w.t")
        self.assertEqual(norm["salienceClass"], "MOTIVATION_PRESSURE")
        self.assertTrue(norm["motivationDrive"])

    def test_user_override_outranks_motivation(self):  # U / V / W / X
        override = {"sourceType": "GOAL", "sourceRef": "g.ov", "category": "goal",
                    "summary": "override target", "userOverrideTarget": True,
                    "targetApps": ["17"]}
        mot = M.to_attention_candidates(M.build_snapshot(
            coherence=M.classify_coherence([bcond("b.1", "CONFLICTED")]),
            goal_completion=M.classify_goal_completion([]),
            raw_refs=set(), channel="x"))[0]
        snap = W.build_workspace_snapshot([mot, override], capacity=4,
                                          correlation_id="w.t", channel="x")
        self.assertEqual(snap["primaryFocus"]["salienceClass"], "USER_OVERRIDE_TARGET")
        self.assertEqual(snap["primaryFocus"]["sourceRef"], "g.ov")

    def test_motivation_never_beats_focus_or_blocker(self):
        focus = {"sourceType": "GOAL", "sourceRef": "g.f", "category": "goal",
                 "summary": "focus", "isFocusGoal": True}
        mot = M.to_attention_candidates(M.build_snapshot(
            coherence=M.classify_coherence([bcond("b.1", "CONFLICTED")]),
            goal_completion=M.classify_goal_completion([]),
            raw_refs=set(), channel="x"))[0]
        snap = W.build_workspace_snapshot([mot, focus], capacity=4,
                                          correlation_id="w.t", channel="x")
        self.assertEqual(snap["primaryFocus"]["salienceClass"], "FOCUS_CONTINUITY")


class BoundedSummary(unittest.TestCase):
    def _snap(self):
        return M.build_snapshot(
            coherence=M.classify_coherence([bcond("b.1", "CONFLICTED", entity="14")]),
            goal_completion=M.classify_goal_completion(
                [gcond("g.1", isFocus=True, targetApp="14")]),
            raw_refs=set(), correlation_id="m.t", channel="x")

    def test_only_selected_supporting(self):  # T-SUMSEL
        s = self._snap()
        # selected refs include g.1 -> GOAL_COMPLETION supports; b.1 not selected.
        summ = M.bounded_summary(s, selected_refs={"g.1"}, selected_candidate_sourcerefs=[])
        types = {x["driveType"] for x in summ}
        self.assertIn("GOAL_COMPLETION", types)
        self.assertNotIn("COHERENCE", types)

    def test_unselected_cannot_bypass(self):  # T-BYPASS
        s = self._snap()
        summ = M.bounded_summary(s, selected_refs=set(), selected_candidate_sourcerefs=[])
        self.assertEqual(summ, [])

    def test_selected_candidate_included(self):
        s = self._snap()
        summ = M.bounded_summary(s, selected_refs=set(),
                                 selected_candidate_sourcerefs=["drive:COHERENCE"])
        self.assertEqual({x["driveType"] for x in summ}, {"COHERENCE"})


# ── world_context adapter integration (monkeypatched fakes; no network) ──────

class Adapters(unittest.TestCase):
    def setUp(self):
        self._orig = {k: getattr(wc, k, None) for k in
                      ("fetch_goals", "fetch_goal_focus", "_get_json", "_post_draft", "_post_goal_json")}
        # writes must never happen:
        wc._post_draft = lambda *a, **k: (_ for _ in ()).throw(AssertionError("POST draft"))
        wc._post_goal_json = lambda *a, **k: (_ for _ in ()).throw(AssertionError("POST goal"))
        self.gets = []
        def fake_get(path, *a, **k):
            self.gets.append(path)
            if path.startswith("/os/tasks"):
                return {"tasks": []}
            return {}
        wc._get_json = fake_get

    def tearDown(self):
        for k, v in self._orig.items():
            if v is not None:
                setattr(wc, k, v)

    def test_no_global_goal_scan(self):  # T-NOGSCAN-G
        wc.fetch_goals = lambda *a, **k: {"goals": [
            {"goalId": "g.focus", "lifecycleState": "BLOCKED", "source": "USER_REQUESTED",
             "target": {"type": "career.application", "id": "17"}, "blockedBy": []},
            {"goalId": "g.unrelated", "lifecycleState": "BLOCKED", "source": "SYSTEM",
             "target": {"type": "career.application", "id": "99"}, "blockedBy": []},
        ]}
        wc.fetch_goal_focus = lambda *a, **k: {"focus": {"goalId": "g.focus"}}
        # ws_cands empty, no referenced app -> only the focus goal is in scope.
        snap = wc.build_motivation_snapshot("hello", "s", {"any": True}, [], channel="lilith_os")
        gc = [d for d in snap["drives"] if d["driveType"] == "GOAL_COMPLETION"][0]
        self.assertIn("g.focus", gc["relatedGoalIds"])
        self.assertNotIn("g.unrelated", gc["relatedGoalIds"])  # never scanned into pressure

    def test_no_global_belief_scan(self):  # T-NOGSCAN-B
        wc.fetch_goals = lambda *a, **k: {"goals": []}
        wc.fetch_goal_focus = lambda *a, **k: {"focus": {}}
        # No belief candidate in ws_cands -> COHERENCE must be SATISFIED (no world scan).
        snap = wc.build_motivation_snapshot("hi", "s", {"any": True}, [], channel="x")
        coh = [d for d in snap["drives"] if d["driveType"] == "COHERENCE"][0]
        self.assertEqual(coh["intensityClass"], "SATISFIED")

    def test_reads_only_no_writes(self):  # N/O/P/Q/R/S
        wc.fetch_goals = lambda *a, **k: {"goals": []}
        wc.fetch_goal_focus = lambda *a, **k: {"focus": {}}
        wc.build_motivation_snapshot("hi", "s", {"any": True}, [], channel="x")
        # only GET-style task read observed; POST fakes would have raised.
        self.assertTrue(all(g.startswith("/os/") for g in self.gets))

    def test_coherence_from_ws_cands_belief(self):
        wc.fetch_goals = lambda *a, **k: {"goals": []}
        wc.fetch_goal_focus = lambda *a, **k: {"focus": {}}
        ws_cands = [{"sourceType": "WORLD_BELIEF", "sourceRef": "b.k", "category": "belief",
                     "conflict": True, "targetApps": ["14"], "relatedBeliefRefs": ["b.k"]}]
        snap = wc.build_motivation_snapshot("q", "s", {"any": True}, ws_cands, channel="x")
        coh = [d for d in snap["drives"] if d["driveType"] == "COHERENCE"][0]
        self.assertEqual(coh["intensityClass"], "SIGNIFICANT")
        # dedup: belief ref already in ws_cands -> motivation candidate not eligible.
        self.assertFalse(coh["candidateEligible"])


if __name__ == "__main__":
    unittest.main()
