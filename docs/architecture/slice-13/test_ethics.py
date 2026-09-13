# -*- coding: utf-8 -*-
"""Offline unit tests for Slice 13 Ethical Deliberation V1.
No network, no Hermes, no VM. All source state is synthetic; world_context source
adapters are faked by monkeypatching. Proves Ethics is advisory only: no
ALLOW/DENY, never acts/approves/verifies/mutates, never fabricates a Policy/legal
verdict, a data-sensitivity label, a third-party identity, or a user preference,
never re-litigates a hard prohibition, and separates grounding from validation.
Import path supports the package (VM) or a flat dir."""
import io
import json
import os
import unittest

try:
    from lilith_router import ethics as E
    from lilith_router import ethics_principles as PR
    from lilith_router import world_context as wc
except Exception:  # staged flat dir
    import ethics as E
    import ethics_principles as PR
    import world_context as wc


def _ei(message, beliefs=(), corr="e.test", channel="lilith_os"):
    """Build an EthicalInput straight from the real TurnEvidence extractor."""
    te = wc.build_turn_evidence(message, corr)
    eintent = {"app_id": (te["referencedTargets"][0]["appId"] if te["referencedTargets"] else None),
               "trigger": "marker"}
    subj = wc.build_ethical_subject(message, eintent, corr, te)
    return {
        "schemaVersion": 1, "correlationId": corr, "channel": channel, "mode": "ETHICS",
        "userIntent": message, "ethicalSubject": subj, "turnEvidence": te,
        "explicitUserConstraints": [c["text"] for c in te["explicitConstraints"]],
        "relevantBeliefs": list(beliefs), "relevantDrafts": [], "relevantTasks": [],
        "capabilityView": {"authoritative": False, "capabilities": []},
    }


def _types(res):
    return {c["concernType"] for c in res["concerns"]}


# ── acceptance-shaped cases ───────────────────────────────────────────────────

class AcceptanceCases(unittest.TestCase):
    def test_A_consent_unclear_reversible_followup(self):
        res, tr = E.run_ethics(_ei(
            "Would it be okay to send this follow-up for application 17 without asking me first?"))
        self.assertNotEqual(res["outcome"], E.OUT_SKIPPED_PROHIBITION)  # follow-up != prohibited send
        self.assertIn(E.C_CONSENT_UNCLEAR, _types(res))
        self.assertEqual(res["concerns"][0]["principleRefs"], [PR.P_USER_AUTONOMY])
        self.assertFalse(res["humanReviewRecommended"])
        self.assertEqual(res["outcome"], E.OUT_CONCERNS)

    def test_B_privacy_from_turn_asserted_data(self):
        res, _ = E.run_ethics(_ei("Should we include all my private application notes in the email?"))
        self.assertIn(E.C_PRIVACY, _types(res))
        c = [c for c in res["concerns"] if c["concernType"] == E.C_PRIVACY][0]
        self.assertTrue(any(r.startswith("turn:") and "data-scope" in r for r in c["sourceRefs"]))
        self.assertEqual(c["principleRefs"], [PR.P_PRIVACY])

    def test_C_email_recruiter_is_skipped_prohibition_not_moralised(self):
        res, tr = E.run_ethics(_ei("Would it be okay to email the recruiter about application 14?"))
        self.assertEqual(res["outcome"], E.OUT_SKIPPED_PROHIBITION)
        self.assertEqual(res["concerns"], [])
        self.assertEqual(res["prohibitionBasis"], "STATIC_POLICY_MIRROR")
        self.assertFalse(res["authoritativePolicyEvaluation"])
        # recruiter still captured as an unresolved third-party role (no fabricated identity)
        ev = _ei("Would it be okay to email the recruiter about application 14?")["turnEvidence"]
        self.assertTrue(ev["referencedThirdPartyRoles"])
        self.assertFalse(ev["referencedThirdPartyRoles"][0]["identityResolved"])

    def test_D_prohibited_fixture(self):
        ei = _ei("email the recruiter")
        ei["turnEvidence"]["referencedAction"] = {
            "ref": "turn:e.test:action", "verb": "send_external",
            "capabilityRef": "mail.send_email", "impactClass": "EXTERNAL_DISCLOSURE",
            "bypassConfirmation": False}
        ei["ethicalSubject"]["referencedCapabilityRef"] = "mail.send_email"
        res, _ = E.run_ethics(ei)
        self.assertEqual(res["outcome"], E.OUT_SKIPPED_PROHIBITION)
        self.assertNotIn("ALLOW", json.dumps(res))

    def test_E_irreversible_under_uncertainty_human_review(self):
        beliefs = ["application:999 · status = ? [lifecycle=STALE, epistemic=CONFLICTED, confidence=..]"]
        res, _ = E.run_ethics(_ei("Would it be okay to permanently delete application 999's record?",
                                   beliefs=beliefs))
        self.assertIn(E.C_IRREVERSIBLE, _types(res))
        self.assertTrue(res["humanReviewRecommended"])
        self.assertEqual(res["outcome"], E.OUT_HUMAN_REVIEW)
        self.assertEqual(res["concerns"][0]["principleRefs"], [PR.P_NON_MALEFICENCE])
        self.assertNotIn("score", json.dumps(res).lower())

    def test_F_proportionality_typed_scope(self):
        res, _ = E.run_ethics(_ei("Would it be okay to send follow-ups to everyone for application 17?"))
        self.assertIn(E.C_SCOPE, _types(res))
        c = [c for c in res["concerns"] if c["concernType"] == E.C_SCOPE][0]
        self.assertEqual(c["principleRefs"], [PR.P_PROPORTIONALITY])

    def test_G_vague_question_insufficient_context(self):
        res, _ = E.run_ethics(_ei("Is this even ethical?"))
        self.assertEqual(res["outcome"], E.OUT_INSUFFICIENT)
        self.assertEqual(res["concerns"], [])
        self.assertTrue(res["informationNeeded"])


# ── evidence / TURN source owner ─────────────────────────────────────────────

class TurnEvidenceModel(unittest.TestCase):
    def test_raw_text_never_a_source_ref(self):
        res, _ = E.run_ethics(_ei("Should we include my private salary in the email?"))
        for c in res["concerns"]:
            for r in c["sourceRefs"]:
                self.assertRegex(r, r"^(turn|world|goals|tasks|drafts):")
                self.assertNotIn("include my private salary", r)

    def test_turn_is_explicit_source_owner(self):
        te = wc.build_turn_evidence("don't contact the recruiter", "e.abc")
        self.assertTrue(te["explicitConstraints"])
        self.assertTrue(te["explicitConstraints"][0]["ref"].startswith("turn:e.abc:constraint"))

    def test_refs_are_correlation_bound(self):
        te = wc.build_turn_evidence("email the recruiter about application 14 with my private notes", "e.zzz")
        blob = json.dumps(te)
        self.assertIn("turn:e.zzz:", blob)
        self.assertNotIn("turn:e.abc:", blob)

    def test_third_party_role_without_fabricated_identity(self):
        te = wc.build_turn_evidence("email the recruiter", "e.t")
        tp = te["referencedThirdPartyRoles"][0]
        self.assertEqual(tp["role"], "recruiter")
        self.assertFalse(tp["identityResolved"])
        self.assertNotIn("email", tp)         # no fabricated contact detail
        self.assertNotIn("identity", tp)


# ── autonomy / consent narrowing (correction 3) ──────────────────────────────

class AutonomyNarrowing(unittest.TestCase):
    def test_absence_of_confirmation_alone_is_not_a_concern(self):
        # a hypothetical action with NO bypass framing -> no consent concern
        res, _ = E.run_ethics(_ei("Would it be okay to create a follow-up draft for application 17?"))
        self.assertNotIn(E.C_CONSENT_UNCLEAR, _types(res))
        self.assertEqual(res["outcome"], E.OUT_NO_CONCERN)

    def test_explicit_bypass_triggers_consent_concern(self):
        res, _ = E.run_ethics(_ei("Would it be okay to draft a follow-up for app 17 without asking me first?"))
        self.assertIn(E.C_CONSENT_UNCLEAR, _types(res))

    def test_standing_constraint_conflict_triggers_autonomy(self):
        res, _ = E.run_ethics(_ei(
            "You said don't contact the recruiter — is it okay to reach out to the recruiter for application 14?"))
        self.assertIn(E.C_CONSTRAINT_CONFLICT, _types(res))
        c = [c for c in res["concerns"] if c["concernType"] == E.C_CONSTRAINT_CONFLICT][0]
        self.assertEqual(c["sourceScope"], "USER_SPECIFIC")


# ── non-maleficence narrowing (correction 4) ─────────────────────────────────

class NonMaleficenceNarrowing(unittest.TestCase):
    def test_unavailable_capability_is_not_a_harm_concern(self):
        ei = _ei("is it okay to do that?")
        ei["turnEvidence"]["referencedAction"] = {
            "ref": "turn:e.test:action", "verb": "contact", "capabilityRef": "gmail.send",
            "impactClass": None, "bypassConfirmation": False}
        res, _ = E.run_ethics(ei)
        self.assertNotIn(E.C_IRREVERSIBLE, _types(res))

    def test_external_action_alone_is_not_harm(self):
        res, _ = E.run_ethics(_ei("Would it be okay to reach out about this?"))
        self.assertNotIn(E.C_IRREVERSIBLE, _types(res))

    def test_reversible_internal_action_no_auto_concern(self):
        res, _ = E.run_ethics(_ei("Would it be okay to draft a follow-up for application 17?"))
        self.assertEqual(res["concerns"], [])
        self.assertEqual(res["outcome"], E.OUT_NO_CONCERN)


# ── principle set / no score / taxonomy ──────────────────────────────────────

class PrincipleSetAndTaxonomy(unittest.TestCase):
    def test_exactly_four_principles(self):
        self.assertEqual(set(PR.PRINCIPLE_IDS),
                         {"USER_AUTONOMY", "PRIVACY_MINIMIZATION", "NON_MALEFICENCE", "PROPORTIONALITY"})

    def test_transparency_absent(self):
        self.assertNotIn("TRANSPARENCY", PR.PRINCIPLE_IDS)
        self.assertFalse(PR.is_principle("TRANSPARENCY"))

    def test_no_misleading_representation_concern(self):
        self.assertNotIn("MISLEADING_REPRESENTATION", E._CONCERN_TYPES)

    def test_no_conflicting_values_concern(self):
        self.assertNotIn("CONFLICTING_VALUES", E._CONCERN_TYPES)

    def test_no_insufficient_context_concern(self):
        self.assertNotIn("INSUFFICIENT_ETHICAL_CONTEXT", E._CONCERN_TYPES)
        self.assertNotIn("INSUFFICIENT_CONTEXT", E._CONCERN_TYPES)

    def test_no_importance_or_uncertainty_class_or_score(self):
        res, _ = E.run_ethics(_ei("Should we include all my private application notes in the email?"))
        blob = json.dumps(res).lower()
        for bad in ("importanceclass", "uncertaintyclass", "score", "weight", "severity"):
            self.assertNotIn(bad, blob)

    def test_principle_set_version_explicit(self):
        res, _ = E.run_ethics(_ei("is this ethical?"))
        self.assertEqual(res["principleSetVersion"], PR.PRINCIPLE_SET_VERSION)


# ── applicability three-way (correction 12) ──────────────────────────────────

class Applicability(unittest.TestCase):
    def test_privacy_insufficient_evidence_not_not_applicable(self):
        # a disclosure action with UNKNOWN data scope -> INSUFFICIENT, not a concern
        ei = _ei("Would it be okay to include that in the email?")
        applic = E.principle_applicability(ei)
        self.assertEqual(applic[PR.P_PRIVACY][0], PR.APPLIC_INSUFFICIENT)
        res, _ = E.run_ethics(ei)
        self.assertNotIn(E.C_PRIVACY, _types(res))
        self.assertIn(E.IN_DATA_SCOPE, res["informationNeeded"])

    def test_privacy_requires_real_data_scope(self):
        res, _ = E.run_ethics(_ei("Should we include all my private application notes in the email?"))
        self.assertIn(E.C_PRIVACY, _types(res))

    def test_no_typed_scope_no_proportionality(self):
        res, _ = E.run_ethics(_ei("Would it be okay to draft a follow-up for application 17?"))
        self.assertNotIn(E.C_SCOPE, _types(res))


# ── human review typed conditions ────────────────────────────────────────────

class HumanReview(unittest.TestCase):
    def test_privacy_only_is_not_human_review(self):
        res, _ = E.run_ethics(_ei("Should we include all my private application notes in the email?"))
        self.assertFalse(res["humanReviewRecommended"])

    def test_irreversible_uncertain_is_human_review(self):
        res, _ = E.run_ethics(_ei("permanently delete application 999",
                                   beliefs=["x [epistemic=CONFLICTED]"]))
        self.assertTrue(res["humanReviewRecommended"])


# ── outcome semantics ────────────────────────────────────────────────────────

class OutcomeSemantics(unittest.TestCase):
    def test_no_grounded_concern_not_safe_or_allowed(self):
        res, _ = E.run_ethics(_ei("Would it be okay to draft a follow-up for application 17?"))
        self.assertEqual(res["outcome"], E.OUT_NO_CONCERN)
        low = res["answer"].lower()
        for bad in ("allow", "denied", "approved", "is safe", "legal", "compliant", "permitted"):
            self.assertNotIn(bad, low)

    def test_static_prohibition_not_live_policy(self):
        res, tr = E.run_ethics(_ei("Would it be okay to email the recruiter?"))
        self.assertFalse(tr["authoritative_policy_evaluation"])
        self.assertEqual(tr["prohibition_basis"], "STATIC_POLICY_MIRROR")

    def test_no_allow_deny_anywhere(self):
        for msg in ("Would it be okay to email the recruiter?",
                    "Should we include all my private notes in the email?",
                    "is this ethical?"):
            res, _ = E.run_ethics(_ei(msg))
            self.assertNotIn(res["outcome"], ("ALLOW", "DENY", "APPROVED", "SAFE"))

    def test_answer_rendered_from_typed_result(self):
        res, _ = E.run_ethics(_ei("Should we include all my private application notes in the email?"))
        # the answer is composed from the validated concern, not free-form
        self.assertIn("disclose", res["answer"].lower())
        self.assertIn(res["concerns"][0]["resolutionConditions"][0].split()[0], res["answer"])


# ── grounder != validator ────────────────────────────────────────────────────

class GrounderValidatorSeparation(unittest.TestCase):
    def test_grounder_produces_no_outcome(self):
        ei = _ei("Should we include all my private application notes in the email?")
        applic = E.principle_applicability(ei)
        cands = E.deterministic_concern_candidates(ei, applic)
        grounded = E.ground_concerns(cands, ei)
        self.assertTrue(grounded)
        for g in grounded:
            self.assertNotIn("outcome", g)
            self.assertIn("principleRefs", g)   # grounder attaches principle refs

    def test_validator_adds_no_concerns_and_drops_invalid(self):
        ei = _ei("is this ethical?")
        applic = E.principle_applicability(ei)
        # fabricated principle + fabricated concern type + banned vocabulary
        bad = [
            {"concernType": E.C_PRIVACY, "principleRefs": ["MADE_UP"], "sourceRefs": ["turn:e.test:x"]},
            {"concernType": "NONSENSE", "principleRefs": [PR.P_PRIVACY], "sourceRefs": ["turn:e.test:x"]},
        ]
        grounded = E.ground_concerns(bad, ei)   # NONSENSE dropped at grounding
        kept, dropped, summary = E.validate_concerns(grounded, ei, applic)
        self.assertEqual(kept, [])               # validator synthesises nothing
        self.assertIn("SCHEMA_STATUS", summary)

    def test_banned_vocabulary_dropped(self):
        ei = _ei("Should we include all my private application notes in the email?")
        applic = E.principle_applicability(ei)
        c = [{"concernType": E.C_PRIVACY, "principleRefs": [PR.P_PRIVACY],
              "sourceRefs": ["turn:e.test:data-scope:0"],
              "rationaleSummary": "this is legal and allowed"}]  # banned terms
        grounded = E.ground_concerns(c, ei)
        kept, dropped, summary = E.validate_concerns(grounded, ei, applic)
        self.assertEqual(kept, [])
        self.assertEqual(summary["VOCABULARY_STATUS"], "DROPPED_PRESENT")


# ── LLM candidate path (built, disabled live) ────────────────────────────────

class LLMCandidatePath(unittest.TestCase):
    def test_llm_candidate_grounded_and_validated_not_copied(self):
        ei = _ei("Should we include all my private application notes in the email?")
        cg = {"concernCandidates": [
            {"concernType": E.C_PRIVACY, "principleRefs": [PR.P_PRIVACY],
             "sourceRefs": ["turn:e.test:data-scope:0"], "rationaleSummary": "discloses personal data"},
            {"concernType": "FABRICATED", "principleRefs": ["MADE_UP"],
             "sourceRefs": ["turn:e.test:data-scope:0"], "rationaleSummary": "x"}]}
        res, tr = E.run_ethics(ei, model_call=lambda p: json.dumps(cg))
        self.assertEqual(tr["candidate_source"], "llm")
        self.assertEqual(_types(res), {E.C_PRIVACY})   # fabricated one dropped

    def test_llm_cannot_invent_principle(self):
        ei = _ei("is this ethical?")
        cg = {"concernCandidates": [
            {"concernType": E.C_PRIVACY, "principleRefs": ["OMNISCIENCE"],
             "sourceRefs": ["turn:e.test:x"], "rationaleSummary": "x"}]}
        res, _ = E.run_ethics(ei, concern_candidates=cg["concernCandidates"])
        self.assertEqual(res["concerns"], [])

    def test_llm_unparseable_falls_open_to_no_concern_or_insufficient(self):
        res, _ = E.run_ethics(_ei("is this ethical?"), model_call=lambda p: "not json")
        self.assertIn(res["outcome"], (E.OUT_INSUFFICIENT, E.OUT_NO_CONCERN))

    def test_agent_kwargs_are_tool_less(self):
        orig_m, orig_k = E._resolve_model, E._resolve_kwargs
        E._resolve_model = lambda: "fake-model"
        E._resolve_kwargs = lambda: {"provider": "x"}
        try:
            kw = E.ethics_agent_kwargs()
        finally:
            E._resolve_model, E._resolve_kwargs = orig_m, orig_k
        self.assertEqual(kw["enabled_toolsets"], [])
        self.assertTrue(kw["skip_memory"])
        self.assertTrue(kw["skip_context_files"])
        self.assertEqual(kw["max_iterations"], 1)
        self.assertFalse(kw["load_soul_identity"])

    def test_no_cot_keys_survive(self):
        obj = E._extract_json(json.dumps({"concernCandidates": [], "thinking": "secret",
                                          "scratchpad": "x", "deliberation": "y"}))
        for k in ("thinking", "scratchpad", "deliberation"):
            self.assertNotIn(k, obj)


# ── determinism / parity / bounds / no-side-effect ───────────────────────────

class DeterminismParityBounds(unittest.TestCase):
    def test_same_input_same_snapshot(self):
        r1, _ = E.run_ethics(_ei("Should we include all my private application notes in the email?"))
        r2, _ = E.run_ethics(_ei("Should we include all my private application notes in the email?"))
        self.assertEqual(r1["ethicalSnapshotId"], r2["ethicalSnapshotId"])
        self.assertEqual(_types(r1), _types(r2))

    def test_home_telegram_parity(self):
        # DIFFERENT correlation ids per channel -> snapshot id must still match,
        # proving the id is seeded from semantic content, not the per-turn corr.
        msg = "Should we include all my private application notes in the email?"
        rh, _ = E.run_ethics(_ei(msg, corr="e.home", channel="lilith_os"))
        rt, _ = E.run_ethics(_ei(msg, corr="e.tg", channel="telegram"))
        self.assertEqual(rh["ethicalSnapshotId"], rt["ethicalSnapshotId"])
        self.assertEqual(rh["outcome"], rt["outcome"])

    def test_concerns_bounded(self):
        res, _ = E.run_ethics(_ei(
            "You said don't contact the recruiter; without asking me, permanently delete "
            "application 14 and include all my private notes in the email to everyone.",
            beliefs=["x [epistemic=CONFLICTED]"]), max_concerns=4)
        self.assertLessEqual(len(res["concerns"]), 4)

    def test_run_ethics_never_raises(self):
        for bad in (None, {}, {"ethicalSubject": None}, {"turnEvidence": 5}):
            res, tr = E.run_ethics(bad)
            self.assertIn(res["outcome"], E._OUTCOMES)

    def test_no_cross_turn_resolution_keys(self):
        res, _ = E.run_ethics(_ei("Should we include all my private application notes in the email?"))
        for k in ("resolvedConcerns", "transition", "ethicalCaseId", "previousOutcome"):
            self.assertNotIn(k, res)
        self.assertIn("ethicalSnapshotId", res)   # ephemeral id only

    def test_no_action_gate_or_mutation_keys(self):
        res, _ = E.run_ethics(_ei("Would it be okay to draft a follow-up for application 17?"))
        for k in ("allow", "deny", "decision", "approved", "gate", "verified", "executed"):
            self.assertNotIn(k, res)

    def test_source_has_no_write_or_tool_symbols(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        src = io.open(os.path.join(here, "ethics.py"), encoding="utf-8").read().lower()
        for bad in ("_post_draft", "requests.post", "urllib.request.urlopen", "_get_json(",
                    "subprocess", "os.system(", "apply_verified_delta", "submit_observation",
                    "_world_reconcile", "fetch_goals(", "create_goal("):
            self.assertNotIn(bad, src, "ethics.py must not reference %r" % bad)


# ── input boundedness (Motivation/Reasoning absent) ──────────────────────────

class InputBoundedness(unittest.TestCase):
    def setUp(self):
        self._orig = getattr(wc, "select_reasoning_input_m", None)
        wc.select_reasoning_input_m = lambda *a, **k: {
            "relevantBeliefs": ["b1"], "relevantDrafts": [], "relevantTasks": [],
            "workspaceFocus": "wf", "motivationSummary": "SHOULD_NOT_APPEAR"}

    def tearDown(self):
        if self._orig is not None:
            wc.select_reasoning_input_m = self._orig

    def test_motivation_and_reasoning_absent_from_input(self):
        ei = wc.build_ethical_input("is it okay to draft a follow-up for app 17?", "s",
                                    {"app_id": "17", "trigger": "marker"}, None, channel="lilith_os")
        self.assertNotIn("motivationSummary", ei)
        self.assertNotIn("reasoningResult", ei)
        self.assertIn("turnEvidence", ei)
        self.assertEqual(ei["ethicalSubject"]["kind"], "USER_INTENT")
        self.assertTrue(ei["ethicalSubject"]["ref"].startswith("turn:"))


# ── detector precedence (action/goal/pending/planning own) ───────────────────

class DetectorPrecedence(unittest.TestCase):
    def setUp(self):
        self._orig = {k: getattr(wc, k, None) for k in
                      ("detect_intent", "detect_goal_intent", "detect_planning_intent")}
        wc.detect_intent = lambda m: {"draft": False, "pending": False, "belief": False, "any": False, "app_id": None}
        wc.detect_goal_intent = lambda m: {"goal_create": False, "goal_query": False, "any": False}
        wc.detect_planning_intent = lambda m: {"any": False}

    def tearDown(self):
        for k, v in self._orig.items():
            if v is not None:
                setattr(wc, k, v)

    def test_marker_owns_explicit_ethics_question(self):
        self.assertTrue(wc.detect_ethics_intent("would it be okay to send this without asking me first?")["any"])

    def test_yields_to_planning(self):
        wc.detect_planning_intent = lambda m: {"any": True}
        self.assertFalse(wc.detect_ethics_intent("is it okay — plan how to follow up on app 14")["any"])

    def test_yields_to_goal_and_pending(self):
        wc.detect_goal_intent = lambda m: {"goal_create": True, "goal_query": False, "any": True}
        self.assertFalse(wc.detect_ethics_intent("is it okay to track app 14 as a goal")["any"])
        wc.detect_goal_intent = lambda m: {"goal_create": False, "goal_query": False, "any": False}
        wc.detect_intent = lambda m: {"pending": True, "draft": False, "any": True, "app_id": None}
        self.assertFalse(wc.detect_ethics_intent("is it okay, what's pending?")["any"])

    def test_soft_requires_cue(self):
        # "should we ..." with NO ethical cue -> not ethics (yields to reasoning/planning)
        self.assertFalse(wc.detect_ethics_intent("should we do that next")["any"])
        # "should we ..." with a privacy cue -> ethics owns
        self.assertTrue(wc.detect_ethics_intent("should we include my private notes")["any"])

    def test_plain_action_command_not_ethics(self):
        self.assertFalse(wc.detect_ethics_intent("create a follow-up draft for application 17")["any"])


if __name__ == "__main__":
    unittest.main()
