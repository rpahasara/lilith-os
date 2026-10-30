"""Candidate Reasoning detector (NOT IN ANY RELEASE). TEST_ONLY; no network.

    python -m unittest discover -s integrations/hermes/overlays/dev-reasoning-hardening/tests -p "test_*.py"

The expected-failure sets below are measurements. They hold every held-out miss and false match, and are not fixed by tuning.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1/tests"))
import holdout_corpus as H  # noqa: E402
import redteam_corpus as RT  # noqa: E402
import validation_pool as VP  # noqa: E402
import test_r1_detector_corpus as R1  # noqa: E402

BASE = REPO / "integrations/hermes/overlays/dev-goals-hardening/lilith_router/world_context.py"
DEPLOYED = REPO / "integrations/hermes/overlays/dev-unified-cognition/lilith_router/world_context.py"
PROD = REPO / "integrations/hermes/home/variants/prod-lilith-01/lilith_router/world_context.py"
CANDIDATE = HERE / "lilith_router" / "world_context.py"
LOOKUPS = ["where is the interview?", "who is the recruiter?", "is the interview tomorrow?", "did the offer arrive?", "which company is the job at?",
           "what's the salary?", "is application 9 open?", "was the application sent?", "who did I send the offer to?", "what's the job title?"]
LOOKUPS_MATCHED = ["did the offer arrive?", "is application 9 open?", "is the interview tomorrow?", "was the application sent?", "what's the job title?", "what's the salary?", "where is the interview?", "which company is the job at?", "who did I send the offer to?", "who is the recruiter?"]
SCORED = ("ANALYTIC", "CASUAL", "NEGATED", "YIELDS", "MULTI_INTENT", "ADVERSARIAL")
# Measured on the final candidate. Each entry is a defect or a limit, not an accepted behaviour.
EXPECTED_FAILURES = json.loads((Path(__file__).with_name("holdout_results.json")).read_text(encoding="utf-8"))


def load(path, name, directory):
    target = directory / f"{name}.py"
    shutil.copy2(path, target)
    shutil.copy2(PROD, directory / "_prod_world_context.py")
    spec = importlib.util.spec_from_file_location(name, target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._LEGACY is not None, module._UNAVAILABLE_REASON
    return module


def failures(detect):
    hit = lambda m: detect(m)["any"]
    short = lambda m: m if len(m) < 80 else m[:20] + f"...({len(m)})"
    return {"ANALYTIC": sorted(m for m in H.ANALYTIC if not hit(m)),
            "CASUAL": sorted(m for m in H.CASUAL if hit(m)),
            "NEGATED": sorted(m for m in H.NEGATED if hit(m)),
            "YIELDS": sorted(m for m, _ in H.YIELDS if hit(m)),
            "MULTI_INTENT": sorted(m for m in H.MULTI_INTENT if not hit(m)),
            "ADVERSARIAL": sorted(short(m) for m in H.ADVERSARIAL if hit(m))}


class Detector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="rdet-", ignore_cleanup_errors=True)
        directory = Path(cls.tmp.name)
        cls.cand = load(CANDIDATE, "cand_rdet", directory)
        cls.dep = load(DEPLOYED, "dep_rdet", directory)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_original_50(self):
        d = self.cand.detect_reasoning_intent
        missed = sorted(m for m in R1.ANALYTIC if not d(m)["any"])
        false = sorted(m for m in R1.CASUAL if d(m)["any"])
        print(f"\nORIGINAL_50 analytic {25 - len(missed)}/25 casual_false {len(false)}/25 missed {missed} false {false}")
        self.assertEqual(false, [])
        self.assertLessEqual(len(missed), 4)

    def test_holdout_measured(self):
        got = failures(self.cand.detect_reasoning_intent)
        dep = failures(self.dep.detect_reasoning_intent)
        n = {k: len(getattr(H, k)) for k in SCORED}
        print("\nHOLDOUT candidate", {k: f"{len(v)}/{n[k]} wrong" for k, v in got.items()})
        print("HOLDOUT deployed", {k: f"{len(v)}/{n[k]} wrong" for k, v in dep.items()})
        print("HOLDOUT detail", json.dumps(got, indent=0))
        print("AMBIGUOUS", {m: self.cand.detect_reasoning_intent(m)["any"] for m in H.AMBIGUOUS})
        self.assertEqual(got, EXPECTED_FAILURES)

    def test_redteam_measured(self):
        d = self.cand.detect_reasoning_intent
        got = {"MISSED": sorted(m for m in RT.MUST_MATCH if not d(m)["any"]), "FALSE": sorted(m for m in RT.MUST_NOT_MATCH if d(m)["any"])}
        print(f"\nREDTEAM matched {20 - len(got['MISSED'])}/20 false {len(got['FALSE'])}/25")
        self.assertEqual(got, json.loads(Path(__file__).with_name("redteam_results.json").read_text(encoding="utf-8")))

    def test_validation_half_measured(self):
        d = self.cand.detect_reasoning_intent
        tp = [m for m in VP.POSITIVE if not VP.in_tune(m)]
        tn = [m for m in VP.NEGATIVE if not VP.in_tune(m)]
        got = {"MISSED": sorted(m for m in tp if not d(m)["any"]), "FALSE": sorted(m for m in tn if d(m)["any"])}
        print(f"\nVALIDATION matched {len(tp) - len(got['MISSED'])}/{len(tp)} false {len(got['FALSE'])}/{len(tn)}")
        self.assertEqual(got, json.loads(Path(__file__).with_name("validation_results.json").read_text(encoding="utf-8")))

    def test_measured_weakness_plain_lookups_about_work_still_match(self):
        # Finding: these want a fact, not analysis. The broad rule cannot tell them apart. Pinned so a fix shows up here.
        d = self.cand.detect_reasoning_intent
        matched = sorted(m for m in LOOKUPS if d(m)["any"])
        print(f"\nLOOKUPS matched {len(matched)}/{len(LOOKUPS)}", matched)
        self.assertEqual(matched, LOOKUPS_MATCHED)

    def test_every_accepted_r1_turn_keeps_its_result(self):
        d = self.cand.detect_reasoning_intent
        self.assertEqual(d("TEST_ONLY what are my options for application 14?")["mode"], "OPTION_GENERATION")
        self.assertEqual(d("TEST_ONLY what information is missing to resolve this?")["mode"], "UNCERTAINTY_ANALYSIS")
        self.assertFalse(d("TEST_ONLY which goal has priority?")["any"])
        self.assertFalse(d("TEST_ONLY hey how are you")["any"])

    def test_accepted_lanes_keep_their_priority(self):
        for message, owner in H.YIELDS:
            g, c = self.cand.detect_goal_intent(message), self.cand.detect_intent(message)
            self.assertTrue({"goal": g["any"], "pending": c.get("pending"), "draft": c.get("draft")}[owner], message)

    def test_result_shape_is_unchanged_and_carries_no_text(self):
        for m in H.ANALYTIC + H.CASUAL + H.ADVERSARIAL:
            d = self.cand.detect_reasoning_intent(m)
            self.assertEqual(set(d), {"any", "mode", "app_id", "subtype"})
            self.assertTrue(d["app_id"] is None or d["app_id"].isdigit())

    def test_no_io_in_the_detector(self):
        legacy = self.cand._LEGACY
        real, calls = legacy._get_json, []
        legacy._get_json = lambda *a, **k: calls.append(a)
        try:
            for m in H.ANALYTIC + H.CASUAL:
                self.cand.detect_reasoning_intent(m)
        finally:
            legacy._get_json = real
        self.assertEqual(calls, [])

    def test_never_raises_and_stays_fast_on_hostile_input(self):
        for m in (None, "", "\x00", "why is " * 5000, "what does " * 5000, "'" * 9000, '"' * 9000):
            start = time.monotonic()
            self.assertFalse(self.cand.detect_reasoning_intent(m)["any"])
            self.assertLess(time.monotonic() - start, 0.5)

    def test_the_candidate_is_the_goals_candidate_plus_one_addition(self):
        base, cand = (p.read_text(encoding="utf-8").splitlines() for p in (BASE, CANDIDATE))
        self.assertEqual([l for l in base if l not in cand], [])
        self.assertIn("        module.detect_reasoning_intent = hardened_reasoning_intent", cand)

    def test_prod_bytes_and_the_installed_r1_router_are_untouched(self):
        self.assertEqual(hashlib.sha256(PROD.read_bytes()).hexdigest(), "46b8187e3f6f2ac72c920de9dab12fd9c2841551f6c2aa7c20fd91941e3f0104")
        router = REPO / "integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1/home/router.yaml"
        self.assertEqual(hashlib.sha256(router.read_bytes().replace(b"\r\n", b"\n")).hexdigest(), "47579562bbaa2c217657efa478d960b3fb7f0949ba534012823f9f293ebea0d7")


if __name__ == "__main__":
    unittest.main()
