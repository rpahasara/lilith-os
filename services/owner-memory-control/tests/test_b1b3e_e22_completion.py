"""15B2b-B1b-3e M-B12 E-22 completion: the post-V7 DR-5 target and comparison, and the installed-release re-pin.

Record: docs/architecture/slice-15b2b-b1b3e-e22-completion.md. TEST-ONLY: synthetic deploy logs built from the
accepted post-M-B6 fixture texts and a synthetic E-22 operator workdir. Nothing contacts DEV.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _path in (TOOLS, HERE, ROOT / "services/core-api", ROOT / "services/owner-memory-control"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import e22_dr5_target as D  # noqa: E402
import e22_judge_upgrade as J  # noqa: E402
import mb11_dr5_target as D11  # noqa: E402
import mb12_pr3_material as PM  # noqa: E402
import mb12_readiness_inputs as RI  # noqa: E402
import test_b1b3e_mb11_signer_start as T11  # noqa: E402  (helpers only: the accepted fixture texts and script)

T9 = D.T9


def log_for(texts) -> str:
    """A synthetic deploy-log body whose extraction is exactly `texts` (the result set carries both blocks)."""
    return "\n".join(texts["result-set"]) + "\n"


def v7_workdir(root: Path, *, retire="E22_RETIRE_REACHED_" + J.V7, post="E22_SIGNER_POST_VERIFIED", kact=2,
               accepted=True) -> Path:
    work = root / "workdir"
    (work / "steps/07-RETIRE").mkdir(parents=True)
    (work / "attempts").mkdir()
    (work / "attempts/e22-retire.json").write_text("{}\n", encoding="ascii")
    (work / "steps/07-RETIRE/STEP.json").write_text(json.dumps({"result": retire}), encoding="ascii")
    (work / "posts/02-SIGNER").mkdir(parents=True)
    (work / "posts/02-SIGNER/POST.json").write_text(json.dumps({
        "result": post, "w11Phase": D.W11_1, "kActLoadCount": kact, "release": J.NEW_RELEASE,
        "invocationId": "e" * 32, "mainPid": "128648"}), encoding="ascii")
    (work / "acceptance").mkdir()
    for name in ("SIGNER_ACCEPTANCE.json", "WITNESS_ACCEPTANCE.json") if accepted else ():
        (work / "acceptance" / name).write_text("{}\n", encoding="ascii")
    return work


class TargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mb11 = D11.derive(T11.accepted_sets(), T11.SCRIPT)["targets"][D11.RUNNING_SIGNER_HELD]["texts"]
        cls.e22 = J.E19.derive_release_swap(cls.mb11, old=J.OLD_RELEASE, new=J.NEW_RELEASE)

    def test_derive_reproduces_the_merged_pin(self):
        out = D.derive(T11.accepted_sets(), T11.SCRIPT)
        self.assertEqual({k: (v["lines"], v["sha256"]) for k, v in out["sets"].items()},
                         {k: tuple(v) for k, v in J.NEW_DR5_TARGETS[D.TARGET].items()})
        self.assertEqual((out["status"], out["accepted"]), ("DERIVED_PINNED_NOT_ACCEPTED", False))

    def test_compare_is_equal_only_for_the_swapped_text_on_a_verified_v7_workdir(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = v7_workdir(Path(tmp))
            self.assertEqual(D.compare(work, log_for(self.e22))["result"], "EQUAL")
            stale = D.compare(work, log_for(self.mb11))                  # the pre-swap (E-19) text names OLD
            self.assertEqual(stale["result"], "DRIFT")
            self.assertGreater(stale["oldReleaseLines"], 0)

    def test_compare_refuses_without_the_verified_v7_evidence(self):
        cases = {"no V7": {"retire": "E22_RETIRE_STOP"}, "post not verified": {"post": "E22_SIGNER_POST_STOP"},
                 "K-ACT count": {"kact": 3}, "not accepted": {"accepted": False}}
        for name, kw in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(D.TargetError) as caught:
                    D.compare(v7_workdir(Path(tmp), **kw), log_for(self.e22))
                self.assertTrue(caught.exception.reason.startswith("NO_BASELINE_STOP"))


class RepinTests(unittest.TestCase):
    def test_the_installed_release_pins_name_the_e22_release(self):
        self.assertEqual((RI.DEV_PINS["releaseSha"], RI.DEV_PINS["attestedManifestSha256"]),
                         (J.NEW_RELEASE, J.NEW_MANIFEST_SHA256))
        self.assertEqual((PM.DEV_EXPECTED["releaseSha"], PM.DEV_EXPECTED["releaseManifestSha256"]),
                         (J.NEW_RELEASE, J.NEW_MANIFEST_SHA256))

    def test_the_record_states_the_pins_and_the_live_results(self):
        text = (ROOT / "docs/architecture/slice-15b2b-b1b3e-e22-completion.md").read_text(encoding="utf-8")
        for value in (J.NEW_RELEASE, J.NEW_MANIFEST_SHA256, *[d for _n, d in J.NEW_DR5_TARGETS[D.TARGET].values()]):
            self.assertIn(f"`{value}`", text)
        state = text.split("## 6. State", 1)[1]
        for line in ("E-22 TRANSITION = V7 REACHED", "K-ACT LOAD COUNT = 2", "M-B12 = NOT PASSED"):
            self.assertIn(line, state)


if __name__ == "__main__":
    unittest.main()
