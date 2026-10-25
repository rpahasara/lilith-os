"""Track B E-23 completion: the post-E8 installed-release re-pin, the derived DR-5 target and its comparison.

Record: docs/architecture/trackb-e23-completion.md. TEST-ONLY: synthetic deploy logs built from the accepted post-M-B6
fixture texts and a synthetic E-23 operator workdir. Nothing contacts DEV.
"""

from __future__ import annotations

import hashlib
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

import e19_witness_restart_boundary_install as WRB  # noqa: E402
import e22_dr5_target as D22  # noqa: E402
import e23_dr5_target as D  # noqa: E402
import e23_privacy_anchor_upgrade as E23  # noqa: E402
import mb12_pr3_material as PM  # noqa: E402
import mb12_readiness_inputs as RI  # noqa: E402
import test_b1b3e_mb11_signer_start as T11  # noqa: E402  (helpers only: the accepted fixture texts and script)
from test_b1b3e_e22_completion import log_for  # noqa: E402

RECORD = ROOT / "docs/architecture/trackb-e23-completion.md"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def e8_workdir(root: Path, *, retire="E23_RETIRE_REACHED_" + D.E8, verify="E23_SIGNER_VERIFIED",
               release=E23.NEW_RELEASE, accepted=("SIGNER", "WITNESS")) -> Path:
    work = root / "workdir"
    (work / "steps/08-RETIRE").mkdir(parents=True)
    (work / "attempts").mkdir()
    (work / "attempts/e23-retire.json").write_text("{}\n", encoding="ascii")
    (work / "steps/08-RETIRE/STEP.json").write_text(json.dumps({"result": retire}), encoding="ascii")
    (work / "verify/02-SIGNER").mkdir(parents=True)
    (work / "verify/02-SIGNER/VERIFY.json").write_text(json.dumps({
        "result": verify, "release": release, "invocationId": "6" * 32, "mainPid": "281830"}), encoding="ascii")
    (work / "acceptance").mkdir()
    for kind in accepted:
        (work / "acceptance" / f"{kind}_ACCEPTANCE.json").write_text("{}\n", encoding="ascii")
    return work


class TargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e23 = D.texts(T11.accepted_sets(), T11.SCRIPT)
        mb11 = D.D11.derive(T11.accepted_sets(), T11.SCRIPT)["targets"][D22.SOURCE]["texts"]
        cls.e22 = D.E19.derive_release_swap(mb11, old=D.J.OLD_RELEASE, new=D.J.NEW_RELEASE)

    def test_derive_reproduces_the_pin_by_the_accepted_release_swap(self):
        out = D.derive(T11.accepted_sets(), T11.SCRIPT)
        self.assertEqual({k: (v["lines"], v["sha256"]) for k, v in out["sets"].items()},
                         {k: tuple(v) for k, v in D.TARGET_SETS.items()})
        self.assertEqual((out["status"], out["accepted"], out["release"]),
                         ("DERIVED_PINNED_NOT_ACCEPTED", False, E23.NEW_RELEASE))
        for name in D.SETS:                                   # exactly the release lines moved, nothing else
            changed = [(a, b) for a, b in zip(self.e22[name], self.e23[name]) if a != b]
            self.assertEqual(len(self.e22[name]), len(self.e23[name]))
            self.assertTrue(all(E23.OLD_RELEASE in a and E23.NEW_RELEASE in b for a, b in changed), name)
            self.assertFalse(any(old in line for line in self.e23[name] for old in D.RETIRED), name)
        self.assertEqual(D.TARGET_SETS["predeploy-block"], tuple(D.J.NEW_DR5_TARGETS[D22.TARGET]["predeploy-block"]))

    def test_compare_is_equal_only_for_the_e23_text_on_the_e8_workdir(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = e8_workdir(Path(tmp))
            self.assertEqual(D.compare(work, log_for(self.e23))["result"], "EQUAL")
            stale = D.compare(work, log_for(self.e22))                    # the E-22 text names the retired OLD
            self.assertEqual(stale["result"], "DRIFT")
            self.assertGreater(stale["retiredReleaseLines"], 0)

    def test_compare_refuses_without_the_e8_evidence(self):
        cases = {"no E8": {"retire": "E23_RETIRE_STOP"}, "signer not verified": {"verify": "E23_SIGNER_STOP"},
                 "signer on another release": {"release": E23.OLD_RELEASE}, "not accepted": {"accepted": ("SIGNER",)}}
        for name, kw in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(D.TargetError) as caught:
                    D.compare(e8_workdir(Path(tmp), **kw), log_for(self.e23))
                self.assertTrue(caught.exception.reason.startswith("NO_BASELINE_STOP"))


class RepinTests(unittest.TestCase):
    def test_the_installed_release_pins_name_the_e23_release(self):
        pins = (E23.NEW_RELEASE, E23.NEW_MANIFEST_SHA256)
        self.assertEqual(pins, ("57bff671fbfe5df4e59248d5d69338dc0ba05846",
                                "fc29a23cbb411704f2799b418f8c7fd7fadf215489174e9ac9d370db2e78368c"))
        self.assertEqual((RI.DEV_PINS["releaseSha"], RI.DEV_PINS["attestedManifestSha256"]), pins)
        self.assertEqual((PM.DEV_EXPECTED["releaseSha"], PM.DEV_EXPECTED["releaseManifestSha256"]), pins)

    def test_the_installed_witness_unit_pin_is_the_e23_unit(self):
        member = "assets/lilith-recovery-witness.service"
        self.assertEqual(WRB.FRAGMENTS[WRB.E.WITNESS_SERVICE], E23.PAYLOAD_DELTA[member][1])
        self.assertEqual(sha((ROOT / "services/recovery-witness/deploy/lilith-recovery-witness.service").read_bytes()),
                         E23.PAYLOAD_DELTA[member][1])
        for socket in (WRB.E.OWNER_SOCKET, WRB.E.SIGNER_SOCKET):        # the sockets did not change in E-23
            self.assertEqual(sha((ROOT / f"services/recovery-witness/deploy/{socket}").read_bytes()),
                             WRB.FRAGMENTS[socket])

    def test_the_record_states_the_pins_target_and_state(self):
        text = RECORD.read_text(encoding="utf-8")
        for value in (E23.NEW_RELEASE, E23.NEW_MANIFEST_SHA256, E23.PAYLOAD_DELTA["assets/lilith-recovery-witness"
                                                                                  ".service"][1],
                      *[digest for _n, digest in D.TARGET_SETS.values()]):
            self.assertIn(f"`{value}`", text)
        state = text.split("## 7. State", 1)[1]
        for line in ("E-23 TRANSITION = E8 REACHED", "K-ACT LOAD COUNT = 3", "E-23 DR-5 = DERIVED, NOT YET COMPARED"):
            self.assertIn(line, state)


if __name__ == "__main__":
    unittest.main()
