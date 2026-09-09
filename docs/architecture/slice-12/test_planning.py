# -*- coding: utf-8 -*-
"""Offline unit tests for Slice 12 Planning / Replanning V1.
No network, no Hermes, no VM. All source state is synthetic; world_context source
adapters are faked by monkeypatching module attributes. Proposal-only: these tests
prove Planning never acts, never claims Policy/verification, and honestly separates
grounding from validation. Import path supports the package (VM) or a flat dir."""
import io
import json
import os
import re
import unittest

try:
    from lilith_router import planning as P
    from lilith_router import planning_capabilities as C
    from lilith_router import world_context as wc
except Exception:  # staged flat dir
    import planning as P
    import planning_capabilities as C
    import world_context as wc


def _pi(target_app="14", followups=(), eligible=True, subj_kind="GOAL",
        goal_type="career.followup", constraints=()):
    subj = {"kind": subj_kind, "goalRef": ("g.x" if subj_kind == "GOAL" else None),
            "goalType": goal_type, "targetRef": ("application:%s" % target_app) if target_app else None,
            "targetAppId": (str(target_app) if target_app else None), "userIntentRef": None}
    fu = None if followups is None else [
        {"draftId": d, "status": "created", "target": {"type": "application", "id": target_app}}
        for d in followups]
    return {
        "correlationId": "p.test", "planningSubject": subj,
        "subjectEvidence": {"sourceRefs": ["application:%s" % target_app] if target_app else [],
                            "unresolvedFollowups": fu},
        "templateEligible": eligible, "maxSteps": 6,
        "explicitUserConstraints": list(constraints),
        "capabilityView": C.view_summary(),
    }


def _states(res):
    return [(s["stepId"], s["kind"], s["state"]) for s in res["planSnapshot"]["steps"]]


class TemplatePath(unittest.TestCase):
    def test_app14_two_duplicates_user_decision(self):
        res, tr = P.run_planning(_pi("14", followups=("d.a", "d.b")))
        self.assertEqual(res["outcome"], P.OUTCOME_USER_DECISION)
        self.assertEqual(res["planSnapshot"]["planStatus"], "USER_DECISION_REQUIRED")
        kinds = {k: st for (_i, k, st) in _states(res)}
        self.assertEqual(kinds["USER_DECISION"], P.S_BLOCKED)
        self.assertEqual(kinds["STATE_CHANGE"], P.S_BLOCKED)  # create blocked by dups
        self.assertEqual(tr["candidate_source"], "template")

    def test_app_zero_drafts_plan_proposed_ready(self):
        res, _ = P.run_planning(_pi("17", followups=()))
        self.assertEqual(res["outcome"], P.OUTCOME_PLAN_PROPOSED)
        sc = [s for s in res["planSnapshot"]["steps"] if s["kind"] == "STATE_CHANGE"][0]
        self.assertEqual(sc["state"], P.S_READY)
        self.assertEqual(sc["requiredCapabilities"], ["career.create_followup_draft"])

    def test_app_one_draft_already_satisfied(self):
        res, _ = P.run_planning(_pi("22", followups=("d.only",)))
        sc = [s for s in res["planSnapshot"]["steps"] if s["kind"] == "STATE_CHANGE"][0]
        self.assertEqual(sc["state"], P.S_ALREADY_SATISFIED)
        self.assertEqual(res["outcome"], P.OUTCOME_PLAN_PROPOSED)

    def test_lookup_unavailable_is_info_not_fabricated(self):
        res, _ = P.run_planning(_pi("14", followups=None))  # lookup failed
        self.assertIn(res["outcome"], (P.OUTCOME_INSUFFICIENT, P.OUTCOME_NO_VIABLE_PLAN))
        # never proposes a create when the store was unavailable
        self.assertFalse(any(s["kind"] == "STATE_CHANGE" and s["state"] == P.S_READY
                             for s in (res["planSnapshot"] or {}).get("steps", [])))

    def test_template_not_eligible_returns_none(self):
        self.assertIsNone(P.deterministic_template(_pi("14", eligible=False)))


class GrounderValidatorSeparation(unittest.TestCase):
    def _cg(self):
        return {"candidateSteps": [
            {"ref": "c1", "kind": "INFORMATION_GATHERING", "title": "read", "target": "application:9",
             "dependsOn": [], "rationale": "r"},
            {"ref": "c2", "kind": "STATE_CHANGE", "title": "draft", "capabilityRef": "career.create_followup_draft",
             "target": "application:9", "dependsOn": ["c1"], "rationale": "r"},
        ]}

    def test_grounder_produces_no_verdicts(self):
        g = P.ground_candidate_graph(self._cg(), _pi("9", followups=()))
        self.assertIn("steps", g)
        self.assertNotIn("validationSummary", g)  # grounder does not judge validity

    def test_validator_adds_no_new_steps(self):
        g = P.ground_candidate_graph(self._cg(), _pi("9", followups=()))
        n = len(g["steps"])
        plan, summary, failure = P.validate_plan(g, _pi("9", followups=()))
        self.assertIsNone(failure)
        self.assertEqual(len(plan["steps"]), n)  # never synthesizes steps
        self.assertIn("STRUCTURAL_STATUS", summary)

    def test_deterministic_same_candidate_same_plan(self):
        pi = _pi("9", followups=())
        r1, _ = P.run_planning(pi, candidate_graph=self._cg())
        r2, _ = P.run_planning(pi, candidate_graph=self._cg())
        self.assertEqual(r1["planSnapshot"]["planSnapshotId"], r2["planSnapshot"]["planSnapshotId"])
        self.assertEqual(_states(r1), _states(r2))


class CapabilityAndPolicySemantics(unittest.TestCase):
    def test_capability_view_is_not_authoritative(self):
        vs = C.view_summary()
        self.assertFalse(vs["authoritative"])
        for c in vs["capabilities"]:
            self.assertEqual(c["runtimeAvailability"], "UNKNOWN")

    def test_static_support_never_becomes_runtime_health(self):
        d = C.describe("career.create_followup_draft")
        self.assertEqual(d["supportStatus"], "ROUTER_PATH_SUPPORTED")
        self.assertEqual(d["runtimeAvailability"], "UNKNOWN")  # no live health owner

    def test_unknown_capability_no_viable_missing(self):
        cg = {"candidateSteps": [
            {"ref": "c1", "kind": "STATE_CHANGE", "title": "deploy",
             "capabilityRef": "deploy.k8s_rollout", "target": "prod", "dependsOn": []}]}
        res, _ = P.run_planning(_pi("9", followups=()), candidate_graph=cg)
        self.assertEqual(res["outcome"], P.OUTCOME_NO_VIABLE_PLAN)
        self.assertIn(P.R_MISSING_CAPABILITY, res["blockers"])
        sc = res["planSnapshot"]["steps"][0]
        self.assertEqual(sc["state"], P.S_UNEXECUTABLE)

    def test_prohibited_capability_blocked_not_policy_evaluated(self):
        cg = {"candidateSteps": [
            {"ref": "c1", "kind": "STATE_CHANGE", "title": "send",
             "capabilityRef": "mail.send_email", "target": "x", "dependsOn": []}]}
        res, _ = P.run_planning(_pi("9", followups=()), candidate_graph=cg)
        self.assertEqual(res["outcome"], P.OUTCOME_NO_VIABLE_PLAN)
        self.assertIn(P.R_BLOCKED_BY_POLICY, res["blockers"])
        # NEVER claims a full Policy evaluation / ALLOW / POLICY_ELIGIBLE
        vs = res["validationSummary"]
        self.assertEqual(vs["POLICY_COMPATIBILITY_STATUS"], "KNOWN_PROHIBITED_PRESENT")
        self.assertNotIn("POLICY_ELIGIBLE", vs)
        joined = json.dumps(vs)
        self.assertNotIn("ALLOW", joined)

    def test_no_policy_eligible_or_runtime_available_claims(self):
        res, _ = P.run_planning(_pi("17", followups=()))
        vs = res["validationSummary"]
        self.assertEqual(vs["POLICY_COMPATIBILITY_STATUS"], "STATIC_ONLY")
        self.assertNotIn("POLICY_ELIGIBLE", vs)
        self.assertNotIn("CAPABILITY_RUNTIME_AVAILABLE", vs)

    def test_execution_requirements_carry_capability_policy_approval_connector_verify(self):
        res, _ = P.run_planning(_pi("17", followups=()))
        sc = [s for s in res["planSnapshot"]["steps"] if s["kind"] == "STATE_CHANGE"][0]
        kinds = {r["kind"] for r in sc["executionRequirements"]}
        self.assertEqual(kinds, {"CAPABILITY_REQUIRED", "POLICY_EVALUATION_REQUIRED",
                                 "APPROVAL_MAY_BE_REQUIRED", "CONNECTOR_AVAILABILITY_REQUIRED",
                                 "VERIFICATION_REQUIRED"})

    def test_source_preconditions_only_real_owners(self):
        res, _ = P.run_planning(_pi("14", followups=("d.a", "d.b")))
        for s in res["planSnapshot"]["steps"]:
            for pc in s.get("preconditions") or []:
                self.assertIn(pc["sourceOwner"], ("world", "goals", "tasks", "drafts"))


class VerificationAndSatisfaction(unittest.TestCase):
    def test_verification_requirement_declared_only(self):
        res, _ = P.run_planning(_pi("17", followups=()))
        vreqs = [s["verificationRequirement"] for s in res["planSnapshot"]["steps"]
                 if s.get("verificationRequirement")]
        self.assertTrue(vreqs)
        for v in vreqs:
            self.assertEqual(v["status"], "DECLARED_ONLY")
            self.assertIn("evidenceSourceOwner", v)  # a spec, not an endpoint-as-proof

    def test_already_satisfied_is_not_executed_or_verified(self):
        res, _ = P.run_planning(_pi("22", followups=("d.only",)))
        sc = [s for s in res["planSnapshot"]["steps"] if s["kind"] == "STATE_CHANGE"][0]
        self.assertEqual(sc["state"], P.S_ALREADY_SATISFIED)
        # ALREADY_SATISFIED derives from source evidence, never claims executed/verified
        self.assertNotIn("executed", sc)
        self.assertNotIn("verified", sc)

    def test_expected_effect_never_becomes_precondition_truth(self):
        # a create step's expected effect must NOT satisfy its own draft precondition
        res, _ = P.run_planning(_pi("17", followups=()))
        sc = [s for s in res["planSnapshot"]["steps"] if s["kind"] == "STATE_CHANGE"][0]
        self.assertTrue(sc["expectedEffects"])          # it declares an expected effect
        # the precondition is satisfiedBySource (0 dups), not by the expected effect
        pcs = [pc for pc in sc["preconditions"] if pc["kind"] == "DRAFT_STATE"]
        self.assertTrue(all(pc["satisfiedBySource"] for pc in pcs))


class LLMHybridPath(unittest.TestCase):
    def test_llm_candidate_grounded_not_copied(self):
        # LLM proposes one hallucinated cap + one valid cap; grounder must reject the
        # hallucinated one and ground the valid one (never verbatim-copy).
        cg = {"candidateSteps": [
            {"ref": "c1", "kind": "STATE_CHANGE", "title": "magic",
             "capabilityRef": "teleport.now", "target": "application:9", "dependsOn": []},
            {"ref": "c2", "kind": "STATE_CHANGE", "title": "draft",
             "capabilityRef": "career.create_followup_draft", "target": "application:9", "dependsOn": []},
        ]}
        model_call = lambda prompt: json.dumps(cg)
        pi = _pi("9", followups=(), eligible=False)  # no template -> forces LLM path
        res, tr = P.run_planning(pi, model_call=model_call)
        self.assertEqual(tr["candidate_source"], "llm")
        by_cap = {tuple(s["requiredCapabilities"]): s for s in res["planSnapshot"]["steps"]}
        self.assertEqual(by_cap[("teleport.now",)]["state"], P.S_UNEXECUTABLE)
        good = by_cap[("career.create_followup_draft",)]
        self.assertIn(good["state"], (P.S_READY, P.S_BLOCKED, P.S_PENDING))
        # grounded step carries structure the raw candidate never had
        self.assertIn("executionRequirements", good)
        self.assertIn("verificationRequirement", good)

    def test_llm_same_candidate_same_validated_result(self):
        cg = {"candidateSteps": [
            {"ref": "c1", "kind": "STATE_CHANGE", "capabilityRef": "career.create_followup_draft",
             "title": "d", "target": "application:9", "dependsOn": []}]}
        pi = _pi("9", followups=(), eligible=False)
        r1, _ = P.run_planning(pi, model_call=lambda p: json.dumps(cg))
        r2, _ = P.run_planning(pi, model_call=lambda p: json.dumps(cg))
        self.assertEqual(_states(r1), _states(r2))  # semantic determinism of the machinery

    def test_llm_unparseable_falls_open(self):
        pi = _pi("9", followups=(), eligible=False)
        res, tr = P.run_planning(pi, model_call=lambda p: "not json at all")
        self.assertEqual(res["outcome"], P.OUTCOME_INSUFFICIENT)


class StructureAndBounds(unittest.TestCase):
    def test_cycle_rejected(self):
        cg = {"candidateSteps": [
            {"ref": "c1", "kind": "INFORMATION_GATHERING", "title": "a", "dependsOn": ["c2"]},
            {"ref": "c2", "kind": "INFORMATION_GATHERING", "title": "b", "dependsOn": ["c1"]}]}
        res, _ = P.run_planning(_pi("9"), candidate_graph=cg)
        self.assertEqual(res["outcome"], P.OUTCOME_NO_VIABLE_PLAN)
        self.assertIn(P.R_DEPENDENCY_UNSATISFIED, res["blockers"])

    def test_unknown_dependency_ref_dropped(self):
        cg = {"candidateSteps": [
            {"ref": "c1", "kind": "INFORMATION_GATHERING", "title": "a", "dependsOn": ["ghost"]}]}
        g = P.ground_candidate_graph(cg, _pi("9"))
        self.assertEqual(g["steps"][0]["dependencyStepIds"], [])  # dangling ref dropped

    def test_bounded_step_count(self):
        cg = {"candidateSteps": [
            {"ref": "c%d" % i, "kind": "INFORMATION_GATHERING", "title": "s%d" % i, "dependsOn": []}
            for i in range(12)]}
        res, _ = P.run_planning(_pi("9"), candidate_graph=cg, max_steps=6)
        self.assertLessEqual(len(res["planSnapshot"]["steps"]), 6)


class ReplanningIsFixtureOnly(unittest.TestCase):
    def test_no_prior_plan_is_not_replanning(self):
        out = P.run_replanning({"failedStep": "p2"})
        self.assertEqual(out["outcome"], "NOT_REPLANNING_WITHOUT_PRIOR_PLAN")

    def test_prior_plan_preserves_verified_and_invalidates_downstream(self):
        prior = {"planSnapshotId": "ps.1", "revision": 1, "steps": [
            {"stepId": "p1", "dependencyStepIds": []},
            {"stepId": "p2", "dependencyStepIds": ["p1"]},
            {"stepId": "p3", "dependencyStepIds": ["p2"]}]}
        out = P.run_replanning({"priorPlan": prior, "verifiedCompletedSteps": ["p1"],
                                "failedStep": "p2"})
        self.assertEqual(out["outcome"], "REPLAN_PROPOSED")
        self.assertEqual(out["preservedSteps"], ["p1"])       # verified preserved
        self.assertIn("p3", out["invalidatedSteps"])          # downstream invalidated
        self.assertNotIn("p1", out["invalidatedSteps"])       # never re-does verified
        self.assertIn("STEP_EXECUTION_FAILED", out["replanReasonCodes"])
        self.assertEqual(out["newRevision"], 2)


class LiveSnapshotShape(unittest.TestCase):
    def test_no_fake_cross_turn_lineage(self):
        res, _ = P.run_planning(_pi("17", followups=()))
        ps = res["planSnapshot"]
        self.assertIn("planSnapshotId", ps)
        for k in ("revision", "supersedesPlanId", "derivedFromPlanId"):
            self.assertNotIn(k, ps)
        self.assertNotIn("replanReasonCodes", res)  # only in an explicit replan

    def test_no_confidence_floats_or_durations(self):
        res, _ = P.run_planning(_pi("17", followups=()))
        blob = json.dumps(res["planSnapshot"])
        self.assertNotIn("confidence", blob)
        self.assertNotIn("estimatedMinutes", blob)
        self.assertNotIn("durationEstimate", blob)


class NoToolNoSideEffect(unittest.TestCase):
    def test_agent_kwargs_are_tool_less(self):
        orig_m, orig_k = P._resolve_model, P._resolve_kwargs
        P._resolve_model = lambda: "fake-model"
        P._resolve_kwargs = lambda: {"provider": "x"}
        try:
            kw = P.planning_agent_kwargs()
        finally:
            P._resolve_model, P._resolve_kwargs = orig_m, orig_k
        self.assertEqual(kw["enabled_toolsets"], [])   # primary no-tool boundary
        self.assertTrue(kw["skip_memory"])
        self.assertTrue(kw["skip_context_files"])
        self.assertEqual(kw["max_iterations"], 1)

    def test_no_cot_or_forbidden_keys_survive(self):
        obj = P._extract_json(json.dumps({"candidateSteps": [], "thinking": "secret",
                                          "scratchpad": "x"}))
        self.assertNotIn("thinking", obj)
        self.assertNotIn("scratchpad", obj)

    def test_source_has_no_write_or_tool_symbols(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        src = io.open(os.path.join(here, "planning.py"), encoding="utf-8").read()
        low = src.lower()
        # real I/O / execution / mutation call tokens (not doc words like "connector")
        for bad in ("_post_draft", "requests.post", "urllib.request.urlopen",
                    "_get_json(", "subprocess", "os.system(",
                    "apply_verified_delta", "submit_observation", "_world_reconcile"):
            self.assertNotIn(bad, low, "planning.py must not reference %r" % bad)

    def test_run_planning_never_raises(self):
        for bad in (None, {}, {"planningSubject": None}, {"subjectEvidence": 5}):
            res, tr = P.run_planning(bad)
            self.assertIn(res["outcome"], P._OUTCOMES)


class DetectorAndSubject(unittest.TestCase):
    def setUp(self):
        self._orig = {k: getattr(wc, k, None) for k in
                      ("detect_intent", "detect_goal_intent", "fetch_goals",
                       "fetch_goal_focus", "find_unresolved_followups",
                       "select_reasoning_input_m")}
        wc.detect_intent = lambda m: {"draft": False, "pending": False, "belief": False, "any": False}
        wc.detect_goal_intent = lambda m: {"goal_create": False, "goal_query": False, "any": False}

    def tearDown(self):
        for k, v in self._orig.items():
            if v is not None:
                setattr(wc, k, v)

    def test_yields_to_bare_draft_action(self):
        # a genuine draft action with an incidental plan verb but NO plan-only cue
        wc.detect_intent = lambda m: {"draft": True, "pending": False, "any": True}
        self.assertFalse(wc.detect_planning_intent("plan how to draft a follow-up for app 14")["any"])

    def test_owns_plan_only_despite_draft(self):
        # explicit "plan how to create ... but do not do it" -> Planning owns it
        wc.detect_intent = lambda m: {"draft": True, "pending": False, "any": True}
        self.assertTrue(wc.detect_planning_intent(
            "plan how to create a follow-up draft for application 17, but do not do it")["any"])
        # a "just plan / don't actually create" framing also owns
        self.assertTrue(wc.detect_planning_intent(
            "just plan the steps to create a follow-up draft for app 17; don't create it")["any"])

    def test_yields_to_goal_create_and_query_and_pending(self):
        wc.detect_goal_intent = lambda m: {"goal_create": True, "goal_query": False, "any": True}
        self.assertFalse(wc.detect_planning_intent("plan how to track app 14")["any"])
        wc.detect_goal_intent = lambda m: {"goal_create": False, "goal_query": True, "any": True}
        self.assertFalse(wc.detect_planning_intent("what would we need to do for app 14")["any"])
        wc.detect_goal_intent = lambda m: {"goal_create": False, "goal_query": False, "any": False}
        wc.detect_intent = lambda m: {"draft": False, "pending": True, "any": True}
        self.assertFalse(wc.detect_planning_intent("plan the steps for app 14")["any"])

    def test_matches_explicit_plan_verbs(self):
        for msg in ("plan how to create a follow-up draft for application 17",
                    "what would we need to do to resolve application 14",
                    "outline the steps to follow up on app 14",
                    "map out a plan for application 17"):
            self.assertTrue(wc.detect_planning_intent(msg)["any"], msg)

    def test_generic_next_steps_not_planning(self):
        # "what could we do next?" is Reasoning's, not Planning's explicit verb
        self.assertFalse(wc.detect_planning_intent("what could we do next?")["any"])

    def test_single_subject_never_a_list(self):
        wc.fetch_goals = lambda state=None: {"goals": [
            {"goalId": "g.14", "type": "career.followup", "lifecycleState": "BLOCKED",
             "target": {"type": "application", "id": "14"}}]}
        wc.fetch_goal_focus = lambda: {"focus": None}
        subj = wc.build_planning_subject("plan app 14", {"app_id": "14", "subtype": "followup"})
        self.assertEqual(subj["kind"], "GOAL")
        self.assertEqual(subj["goalRef"], "g.14")
        self.assertIsInstance(subj, dict)  # exactly one subject, not a candidate list

    def test_subject_user_intent_when_no_goal(self):
        wc.fetch_goals = lambda state=None: {"goals": []}
        wc.fetch_goal_focus = lambda: {"focus": None}
        subj = wc.build_planning_subject("plan app 99", {"app_id": "99", "subtype": "followup"})
        self.assertEqual(subj["kind"], "USER_INTENT")
        self.assertEqual(subj["targetAppId"], "99")

    def test_input_has_no_goal_candidates_arbitration(self):
        wc.fetch_goals = lambda state=None: {"goals": []}
        wc.fetch_goal_focus = lambda: {"focus": None}
        wc.find_unresolved_followups = lambda a: []
        wc.select_reasoning_input_m = lambda *a, **k: {"currentFocus": "g.x — t (winner)",
                                                       "relevantBeliefs": [], "relevantDrafts": []}
        pin = wc.build_planning_input("plan a follow-up for app 17", "s", {"app_id": "17", "subtype": "followup"},
                                      None, None, channel="lilith_os")
        self.assertNotIn("goalCandidates", pin)          # no goal arbitration in planning
        self.assertIn("planningSubject", pin)
        self.assertTrue(pin["capabilityView"]["authoritative"] is False)
        self.assertTrue(pin["templateEligible"])


if __name__ == "__main__":
    unittest.main()
