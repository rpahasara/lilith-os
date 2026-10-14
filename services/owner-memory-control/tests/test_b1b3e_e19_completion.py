"""15B2b-B1b-3e E-19 completion record: record bindings, post-U5 release bindings, the E-19 DR-5 comparison and the
deployment-freeze gate. Synthetic only: no host, no deploy log from DEV; a local test is never DR-5 EQUAL evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _p in (TOOLS, ROOT / "services/authority-dev", ROOT / "services/owner-memory-control"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import e19_completion as C  # noqa: E402
import e19_dr5_target as D  # noqa: E402
import e19_operator as X  # noqa: E402
import e19_p1b10_upgrade as E  # noqa: E402
import mb9_dr5_target as T9  # noqa: E402
import mb10_dr5_target as T10  # noqa: E402

OLD, NEW = E.OLD_RELEASE, E.NEW_RELEASE
REPLACEMENT = ("90b28f9d06fd48a1a1bdc3ae39474fb1", "69238")
RECORD_DOC = ROOT / "docs/architecture/slice-15b2b-b1b3e-e19-completion-record.md"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fixture_texts():
    fx = json.loads((HERE / "b1b3e_mb9_post_mb6_dr5_baseline.json").read_text(encoding="utf-8"))
    base = {name: T9.encode(lines) for name, lines in fx["sets"].items()}
    script = (ROOT / T10.DR5_SCRIPT).read_bytes()
    return base, script, T10.derive(base, script)["targets"]


def log_for(texts) -> str:
    """A synthetic deploy-log body whose extraction is exactly `texts` (the result set carries both blocks)."""
    return "\n".join(texts["result-set"]) + "\n"


HOST_RESULT = {"codes": {name: 0 for name in D.HOST_CODES}, "e19State": "E19_OLD_RETIRED",
               "phase": E.U5, "readinessExact": True, "result": D.HOST_U5_PASS, "selectedRelease": NEW,
               "tmpResidue": []}
W10_RUNNING = {"phase": "W10_1_HELD_EXACT", "failures": [], "witnessInvocationId": REPLACEMENT[0],
               "witnessMainPid": REPLACEMENT[1], "witnessNRestarts": "0", "authorityActive": False,
               "registryEffective": False, "issuanceAuthority": "NONE"}


class HostDir:
    def __init__(self, result=None, w10=None, rc="0\n"):
        self.path = Path(tempfile.mkdtemp())
        if result is not None:
            (self.path / "HOST_RESULT.json").write_text(json.dumps(result, sort_keys=True) + "\n", encoding="ascii")
        if w10 is not None:
            (self.path / "w10verifier.out").write_text(json.dumps(w10, sort_keys=True) + "\n", encoding="ascii")
        if rc is not None:
            (self.path / "w10verifier.rc").write_text(rc, encoding="ascii")

    def __enter__(self):
        return self.path

    def __exit__(self, *exc):
        shutil.rmtree(self.path, ignore_errors=True)


class RecordTests(unittest.TestCase):
    def test_the_record_is_pinned_and_not_owner_accepted(self):
        record = C.load_record()
        self.assertEqual(sha(D.COMPLETION_RECORD.read_bytes()), D.COMPLETION_RECORD_SHA256)
        self.assertEqual(record["status"], "TRANSITION_COMPLETE_U5_OWNER_COMPLETION_NOT_ACCEPTED")
        self.assertIsNone(record["ownerCompletionAcceptance"])
        self.assertEqual(record["deploymentFreeze"], "ACTIVE")
        self.assertEqual(record["firstPostTransitionDeploy"]["targetStatus"], "DERIVED_PINNED_NOT_ACCEPTED")
        self.assertIsNone(record["firstPostTransitionDeploy"]["dr5Comparison"])
        self.assertEqual(E.NEW_DR5_TARGETS_STATUS, "DERIVED_PINNED_NOT_ACCEPTED")

    def test_the_record_binds_the_transition(self):
        record = C.load_record()
        self.assertEqual((record["newRelease"]["releaseSha"], record["newRelease"]["manifestSha256"]),
                         (NEW, E.NEW_MANIFEST_SHA256))
        self.assertEqual(record["oldRelease"]["state"], "RETIRED")
        self.assertEqual(tuple(record["witness"]["acceptedReplacement"]), REPLACEMENT)
        self.assertEqual(record["witness"]["kWitLoadsAfterU0Cursor"], 1)
        self.assertEqual(record["u0Baseline"]["acceptanceSha256"],
                         "8c0c30fc806c32b229e47c0318ab1c10eec43574c566ca5261d3d56dea030052")
        self.assertEqual(record["replacementAcceptance"]["acceptanceSha256"],
                         "90e81b284eb87078fcc0495a961cd995fd8d3aaf8478a88536b24bb6ecaf9f3e")
        self.assertEqual(record["post9aR"]["evidenceSha256"],
                         "d44d1c4bcf767b90471da83f86a19c15f0c77c5fdffd209b41018500e7fb08b8")
        self.assertEqual(record["finalU5"]["observationSha256"],
                         "cb22dd2607755ff0822c12287a89e4c7117a487e74d3ac88373eeee4ce2d9256")
        self.assertEqual(record["finalHostU5"]["result"], "E19_HOST_U5_OLD_RETIRED_REPLACEMENT_ACCEPTED_PASS")
        self.assertEqual([s["goSha256"][:8] for s in record["transitionSteps"]],
                         ["2264de72", "a958e13a", "57151f43", "2034b887", "594aa7a9"])
        self.assertEqual(record["evidenceManifests"]["lilith-e19-retire-3cdee90"],
                         "60bcaf4cf0500c7f6d4162258e86cefe396b624e255ff89a7209bb8510f77168")
        self.assertEqual(record["evidenceManifests"]["lilith-e19-host-u5-3cdee90"],
                         "bc2dc210c35832869e01b9768d6e9bfc45281db966a857394ce1ea6a81a1722e")

    def test_a_tampered_or_accepted_record_is_refused(self):
        original = D.COMPLETION_RECORD_SHA256
        try:
            D.COMPLETION_RECORD_SHA256 = "0" * 64
            with self.assertRaises(C.CompletionError):
                C.load_record()
        finally:
            D.COMPLETION_RECORD_SHA256 = original

    def test_the_record_document_names_the_pins(self):
        text = RECORD_DOC.read_text(encoding="utf-8")
        for value in (D.COMPLETION_RECORD_SHA256, NEW, E.NEW_MANIFEST_SHA256, REPLACEMENT[0],
                      sha((TOOLS / "e19_dr5_target.py").read_bytes()), sha((TOOLS / "e19_completion.py").read_bytes()),
                      sha((TOOLS / "e19_operator.py").read_bytes())):
            self.assertIn(f"`{value}`", text)
        self.assertIn("DERIVED_PINNED_NOT_ACCEPTED", text)
        self.assertIn("FREEZE = ACTIVE", text)


class ReleaseBindingTests(unittest.TestCase):
    def test_current_bindings_name_new_and_historical_tools_are_byte_identical(self):
        import mb11_restart_boundary_install as RBI
        import mb11_signer_verifier as V
        import mb12_pr3_material as PM
        import mb12_readiness_inputs as RI
        self.assertEqual((V.RELEASE_SHA, V.RELEASE_CWD), (NEW, "/opt/lilith-authority-dev/releases/" + NEW))
        self.assertEqual(RBI.RELEASE_SHA, NEW)
        self.assertEqual((PM.DEV_EXPECTED["releaseSha"], PM.DEV_EXPECTED["releaseManifestSha256"]),
                         (NEW, E.NEW_MANIFEST_SHA256))
        self.assertEqual((RI.DEV_PINS["releaseSha"], RI.DEV_PINS["attestedManifestSha256"]),
                         (NEW, E.NEW_MANIFEST_SHA256))
        self.assertEqual(RI.E19_DEFECTIVE_RELEASES, frozenset({OLD}))
        # signer fragments are identical in OLD and NEW (the payload delta is pr1_acceptance only)
        self.assertNotIn("assets/lilith-authority-dev.service", E.PAYLOAD_DELTA)
        # completed ceremonies stay byte-identical
        self.assertEqual(sha((TOOLS / "mb6_operator.py").read_bytes()),
                         "4a91d98421e38326858e141152180c127f5a67306eebe51a8ca8762f0504dcc5")
        self.assertEqual(sha((TOOLS / "mb9_operator.py").read_bytes()),
                         "2312e26a9cc8c2076539ae8bdde98cc5d79c2bbeb5138d66d07863ec3303c928")
        self.assertEqual(X.TOOL_PINS[X.RESTART_BOUNDARY_INSTALL], sha((TOOLS / "mb11_restart_boundary_install.py").read_bytes()))

    def test_the_routine_successor_read_validates_new_without_old(self):
        self.assertEqual(X.HOST_PHASES[E.U5], ("NEW", "E19_OLD_RETIRED"))
        self.assertEqual(X.release_modules(NEW, NEW), E.new_release_module_pins(X.release_modules(OLD, NEW)))
        self.assertIn("host", C.ROUTINE_HOST_READ)
        self.assertIn(E.U5, C.ROUTINE_HOST_READ)


class Dr5DeriveTests(unittest.TestCase):
    def test_derive_re_derives_the_merged_pins(self):
        base, script, _ = fixture_texts()
        first, second = D.derive(base, script), D.derive(base, script)
        self.assertEqual(first, second)
        for target, data in first["targets"].items():
            for name in T9.SETS:
                self.assertEqual((data["sets"][name]["lines"], data["sets"][name]["sha256"]),
                                 tuple(E.NEW_DR5_TARGETS[target][name]))
        self.assertIs(first["accepted"], False)

    def test_historical_w10_targets_and_phase_map_are_untouched(self):
        self.assertEqual(T10.TARGETS[T10.RUNNING_HELD]["result-set"],
                         (192, "593c90e1778b0e90326cdf96314b328948c00b2207960d27be2b41874d05ff65"))
        self.assertEqual(T10.PHASE_TARGETS, {"W10_1_HELD_EXACT": T10.RUNNING_HELD,
                                             "W10_1S_HELD_EXACT_WITNESS_STOPPED": T10.STOPPED_HELD})
        self.assertEqual(set(D.PHASE_TARGETS.values()), set(E.NEW_DR5_TARGETS))
        self.assertTrue(set(D.PHASE_TARGETS.values()).isdisjoint(T10.PHASE_TARGETS.values()))


class Dr5CompareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, _, w10 = fixture_texts()
        cls.old = {t: w10[s]["texts"] for t, s in E.NEW_DR5_SOURCES.items()}
        cls.new = {t: E.derive_release_swap(texts, old=OLD, new=NEW) for t, texts in cls.old.items()}

    def test_equal_only_for_the_exact_new_texts_with_a_verified_host_u5(self):
        with HostDir(HOST_RESULT, W10_RUNNING) as host:
            out = D.compare(host, log_for(self.new[D.RUNNING_HELD_E19]))
            self.assertEqual((out["result"], out["target"], out["accepted"], out["targetAccepted"]),
                             ("EQUAL", D.RUNNING_HELD_E19, False, False))
            self.assertEqual(out["targetStatus"], "DERIVED_PINNED_NOT_ACCEPTED")
            stale = D.compare(host, log_for(self.old[D.RUNNING_HELD_E19]))      # the pre-transition W10_1 texts
            self.assertEqual((stale["result"], stale["oldReleaseLines"]), ("DRIFT", 4))
            other = D.compare(host, log_for(self.new[D.STOPPED_HELD_E19]))
            self.assertEqual(other["result"], "DRIFT")

    def test_stopped_phase_maps_to_the_stopped_target(self):
        w10 = dict(W10_RUNNING, phase="W10_1S_HELD_EXACT_WITNESS_STOPPED", witnessInvocationId=None,
                   witnessMainPid="0")
        with HostDir(HOST_RESULT, w10) as host:
            out = D.compare(host, log_for(self.new[D.STOPPED_HELD_E19]))
            self.assertEqual((out["result"], out["target"]), ("EQUAL", D.STOPPED_HELD_E19))

    def test_fail_closed(self):
        log = log_for(self.new[D.RUNNING_HELD_E19])
        cases = {
            "missing host result": (None, W10_RUNNING, "0\n"),
            "missing w10": (HOST_RESULT, None, "0\n"),
            "missing w10 rc": (HOST_RESULT, W10_RUNNING, None),
            "w10 rc nonzero": (HOST_RESULT, W10_RUNNING, "1\n"),
            "not U5 pass": (dict(HOST_RESULT, result="E19_HOST_U5_OLD_RETIRED_REPLACEMENT_ACCEPTED_NOT_PASS"),
                            W10_RUNNING, "0\n"),
            "release mismatch": (dict(HOST_RESULT, selectedRelease=OLD), W10_RUNNING, "0\n"),
            "state": (dict(HOST_RESULT, e19State="E19_NEW_SELECTED"), W10_RUNNING, "0\n"),
            "a code nonzero": (dict(HOST_RESULT, codes=dict(HOST_RESULT["codes"], custody=1)), W10_RUNNING, "0\n"),
            "a code missing": (dict(HOST_RESULT, codes={k: 0 for k in list(D.HOST_CODES)[1:]}), W10_RUNNING, "0\n"),
            "wrong phase": (HOST_RESULT, dict(W10_RUNNING, phase="W9_LATER_STATE"), "0\n"),
            "w10 failures": (HOST_RESULT, dict(W10_RUNNING, failures=["X"]), "0\n"),
            "unexpected witness": (HOST_RESULT, dict(W10_RUNNING, witnessInvocationId="0" * 32), "0\n"),
            "ending witness": (HOST_RESULT, dict(W10_RUNNING, witnessInvocationId=E.ENDING_INCARNATION[0],
                                                 witnessMainPid=E.ENDING_INCARNATION[1]), "0\n"),
            "restarted": (HOST_RESULT, dict(W10_RUNNING, witnessNRestarts="1"), "0\n"),
            "authority active": (HOST_RESULT, dict(W10_RUNNING, authorityActive=True), "0\n"),
        }
        for label, (result, w10, rc) in cases.items():
            with self.subTest(case=label), HostDir(result, w10, rc) as host, self.assertRaises(D.TargetError):
                D.compare(host, log)
        with HostDir(HOST_RESULT, W10_RUNNING) as host:
            with self.assertRaises(D.TargetError):
                D.compare(host, "")                                                       # no DR-5 sets
            release_line = E.DR5_RELEASE_LINE.format(sha=NEW)                # inside the DR-5 block
            allowed = log.replace(release_line, release_line.replace("DENIED: ", "ALLOWED: ", 1), 1)
            self.assertNotEqual(allowed, log)
            try:
                result = D.compare(host, allowed)["result"]
            except D.TargetError:
                result = "REFUSED"
            self.assertIn(result, ("DRIFT", "REFUSED"))


class FreezeGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, _, w10 = fixture_texts()
        texts = E.derive_release_swap(w10[T10.RUNNING_HELD]["texts"], old=OLD, new=NEW)
        host = HostDir(HOST_RESULT, W10_RUNNING)
        with host as path:
            cls.equal = D.compare(path, log_for(texts))
            cls.drift = D.compare(path, log_for(w10[T10.RUNNING_HELD]["texts"]))

    def acceptance(self, comparison, run="40000000000"):
        statement = C.render_completion_statement(comparison, run)
        record = {"recordType": C.COMPLETION_ACCEPTANCE_TYPE, "schemaVersion": 1, "mode": E.MODE,
                  "completionRecordSha256": D.COMPLETION_RECORD_SHA256, "deployRunId": run,
                  "dr5ComparisonSha256": sha(C._canonical(comparison)), "statementSha256": sha(statement)}
        return {"statement": statement.decode("ascii"), "record": record}

    def test_missing_or_unaccepted_evidence_never_lifts_the_freeze(self):
        run = "40000000000"
        self.assertFalse(C.freeze_lift_admissible(None, run, None)[0])
        self.assertFalse(C.freeze_lift_admissible(self.drift, run, None)[0])
        self.assertFalse(C.freeze_lift_admissible(self.equal, run, None)[0])                   # no owner acceptance
        self.assertFalse(C.freeze_lift_admissible(self.equal, None, self.acceptance(self.equal))[0])
        with self.assertRaises(C.CompletionError):
            C.render_completion_statement(self.drift, run)
        acc = self.acceptance(self.equal, run)
        reworded = dict(acc, statement=acc["statement"].replace("I accept", "I  accept"))
        self.assertFalse(C.freeze_lift_admissible(self.equal, run, reworded)[0])
        other_run = self.acceptance(self.equal, "40000000001")
        self.assertFalse(C.freeze_lift_admissible(self.equal, run, other_run)[0])
        tampered = copy.deepcopy(self.equal)
        tampered["observed"]["dr5-block"]["sha256"] = "0" * 64
        self.assertFalse(C.freeze_lift_admissible(tampered, run, acc)[0])
        stopped = dict(self.equal, target=D.STOPPED_HELD_E19)
        self.assertFalse(C.freeze_lift_admissible(stopped, run, acc)[0])
        bad_record = copy.deepcopy(acc)
        bad_record["record"]["completionRecordSha256"] = "0" * 64
        self.assertFalse(C.freeze_lift_admissible(self.equal, run, bad_record)[0])

    def test_the_exact_owner_statement_over_an_equal_comparison_is_admissible(self):
        run = "40000000000"
        ok, reason = C.freeze_lift_admissible(self.equal, run, self.acceptance(self.equal, run))
        self.assertEqual((ok, reason), (True, "FREEZE_LIFT_ADMISSIBLE"))
        self.assertEqual(C.load_record()["deploymentFreeze"], "ACTIVE")                      # a judgement writes nothing


if __name__ == "__main__":
    unittest.main()
