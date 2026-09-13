# -*- coding: utf-8 -*-
"""Offline unit tests for Slice 9 Reasoning Extraction V1 (no network, no Hermes).
Import path is set by the runner (staged dir or the lilith_router package)."""
import json
import unittest

try:
    from lilith_router import reasoning as R
    from lilith_router import world_context as wc
except Exception:  # staged flat dir
    import reasoning as R
    import world_context as wc


VALID_JSON = json.dumps({
    "answer": "Here's what we know, and here's what's uncertain.",
    "interpretation": "Evidence is partial.",
    "outcome": "OK",
    "assumptions": ["a1"],
    "evidenceRefs": ["career.application:14:status"],
    "uncertainties": ["recruiter response unknown"],
    "conflicts": [],
    "blockingConditions": [],
    "candidateNextSteps": [
        {"description": "Reconcile the duplicate drafts", "type": "reconcile",
         "requiredCapabilities": ["career.discard_draft"], "requiresApproval": True,
         "blockedBy": []}],
    "informationNeeded": ["recruiter reply"],
    "answerIntent": "explain_evidence_and_uncertainty",
    "escalationNeeded": False,
    "confidenceBasis": "observed beliefs, medium confidence",
    "thinking": "SECRET private chain of thought that must be dropped",
})


class DetectTests(unittest.TestCase):
    def d(self, m):
        return wc.detect_reasoning_intent(m)

    def test_uncertainty_claimed(self):
        i = self.d("What do we know about application 14, and what is uncertain?")
        self.assertTrue(i["any"]); self.assertEqual(i["mode"], "UNCERTAINTY_ANALYSIS")
        self.assertEqual(i["app_id"], "14")

    def test_blocker_claimed(self):
        i = self.d("Why can't you follow up on application 14 right now?")
        self.assertTrue(i["any"]); self.assertEqual(i["mode"], "BLOCKER_ANALYSIS")

    def test_options_claimed(self):
        i = self.d("What could we do next for application 14?")
        self.assertTrue(i["any"]); self.assertEqual(i["mode"], "OPTION_GENERATION")

    def test_action_yields(self):
        # ACTION PRECEDENCE: explicit draft request stays on the existing path
        i = self.d("Create a follow-up draft for application 17, but do not send it")
        self.assertFalse(i["any"])
        self.assertTrue(wc.detect_intent(
            "Create a follow-up draft for application 17, but do not send it")["draft"])

    def test_goal_create_yields(self):
        self.assertFalse(self.d("Track application 14 as a goal")["any"])

    def test_goal_query_yields_to_slice8(self):
        self.assertFalse(self.d("Which goal has priority right now?")["any"])

    def test_pending_yields_to_slice72(self):
        self.assertFalse(self.d("What drafts are pending?")["any"])

    def test_plain_belief_yields(self):
        # no analytic marker -> Slice 7.2 belief path keeps it
        self.assertFalse(self.d("What do you know about application 14?")["any"])

    def test_casual_not_reasoning(self):
        for m in ("hey how are you", "good morning", "thanks!"):
            self.assertFalse(self.d(m)["any"], m)


class NoToolConstructionTests(unittest.TestCase):
    def test_reasoning_agent_kwargs_no_tools(self):
        orig_m, orig_k = R._resolve_model, R._resolve_kwargs
        R._resolve_model = lambda: "gpt-5.6-sol"
        R._resolve_kwargs = lambda: {"api_key": "k", "provider": "p", "base_url": "u"}
        try:
            kw = R.reasoning_agent_kwargs()
        finally:
            R._resolve_model, R._resolve_kwargs = orig_m, orig_k
        self.assertEqual(kw["enabled_toolsets"], [])      # PRIMARY no-tool boundary
        self.assertIsNone(kw["disabled_toolsets"])
        self.assertTrue(kw["skip_memory"])
        self.assertTrue(kw["skip_context_files"])
        self.assertEqual(kw["max_iterations"], 1)
        self.assertEqual(kw["ephemeral_system_prompt"], R.REASONING_SYSTEM)
        self.assertEqual(kw["model"], "gpt-5.6-sol")
        # no positive tool exposure of any kind
        self.assertNotIn("tools", kw)
        self.assertNotIn("tool_schemas", kw)

    def test_default_model_call_constructs_toolless_agent(self):
        captured = {}

        class FakeAgent:
            def __init__(self, **kw):
                captured.update(kw)
            def run_conversation(self, user_message=None, **kw):
                return {"final_response": '{"answer":"ok"}'}
            def release_clients(self):
                pass

        orig = (R._resolve_model, R._resolve_kwargs, R._construct_agent)
        R._resolve_model = lambda: "m"
        R._resolve_kwargs = lambda: {}
        R._construct_agent = lambda **kw: FakeAgent(**kw)
        try:
            out = R._default_model_call("prompt")
        finally:
            R._resolve_model, R._resolve_kwargs, R._construct_agent = orig
        self.assertEqual(captured["enabled_toolsets"], [])
        self.assertTrue(captured["skip_memory"])
        self.assertTrue(captured["skip_context_files"])
        self.assertIn("answer", out)


class ValidationTests(unittest.TestCase):
    def _ri(self, mode="UNCERTAINTY_ANALYSIS"):
        return {"correlationId": "r.test", "mode": mode,
                "relevantBeliefs": [{"key": "k", "value": "v"}]}

    def test_valid_parses_and_drops_cot(self):
        res, tr = R.run_reasoning(self._ri(), model_call=lambda p: VALID_JSON)
        self.assertIsNotNone(res)
        self.assertTrue(res["answer"])
        self.assertEqual(res["outcome"], "OK")
        # NO chain-of-thought / scratchpad leaks into the typed result
        for k in ("thinking", "scratchpad", "chain_of_thought"):
            self.assertNotIn(k, res)
        self.assertNotIn("SECRET", json.dumps(res))
        # candidate step is a proposal (never executed) with approval preserved
        self.assertTrue(res["candidateNextSteps"][0]["requiresApproval"])
        # trace is safe (counts only, no answer text)
        self.assertEqual(tr["candidate_count"], 1)
        self.assertNotIn("answer", tr)

    def test_malformed_is_rejected(self):
        res, tr = R.run_reasoning(self._ri(), model_call=lambda p: "not json at all")
        self.assertIsNone(res)                 # fail-safe
        self.assertEqual(tr["fallback_reason"], "unparseable_output")

    def test_missing_answer_rejected(self):
        res, _ = R.run_reasoning(self._ri(), model_call=lambda p: '{"outcome":"OK"}')
        self.assertIsNone(res)

    def test_outcome_enum_coerced(self):
        res, _ = R.run_reasoning(self._ri(),
                                 model_call=lambda p: '{"answer":"hi","outcome":"WEIRD"}')
        self.assertEqual(res["outcome"], "OK")

    def test_model_exception_fail_open(self):
        def boom(p):
            raise RuntimeError("model down")
        res, tr = R.run_reasoning(self._ri(), model_call=boom)
        self.assertIsNone(res)
        self.assertEqual(tr["fallback_reason"], "exception")

    def test_prompt_preserves_epistemic_labels(self):
        ri = {"correlationId": "r.x", "mode": "FACTUAL_INTERPRETATION",
              "userIntent": "q",
              "relevantBeliefs": [{"key": "k", "value": "applied",
                                   "lifecycle": "CONFLICTED", "epistemic": "OBSERVED",
                                   "confidence": "0.6 (medium)", "provenanceRefs": ["career_events/14"]}],
              "policyVisibleConstraints": ["mail.send_email is PROHIBITED"]}
        prompt = R.render_input_prompt(ri)
        self.assertIn("CONFLICTED", prompt)
        self.assertIn("PROHIBITED", prompt)
        self.assertIn("career_events/14", prompt)


class SymbolConformanceTests(unittest.TestCase):
    def test_reasoning_performs_no_io(self):
        # reasoning.py must do NO network / DB / process I/O and touch NO
        # mutation endpoints — it only constructs a tool-less model call.
        import inspect
        src = inspect.getsource(R)
        for sym in ("subprocess", "smtplib", "urllib", "requests.", "socket.",
                    "sqlite3", "/os/drafts", "/os/goals", "/os/tasks",
                    "submit_observation", "apply_verified_delta"):
            self.assertNotIn(sym, src, "reasoning.py must not reference: " + sym)


if __name__ == "__main__":
    unittest.main(verbosity=2)
