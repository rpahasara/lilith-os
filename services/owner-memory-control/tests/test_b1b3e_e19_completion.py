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
for _p in (TOOLS, ROOT / "services/authority-dev", ROOT / "services/owner-memory-control",
           ROOT / "services/core-api"):
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
    def __init__(self, result=None, w10=None, rc="0\n", identity=None, identity_rc="0\n"):
        self.path = Path(tempfile.mkdtemp())
        if identity is not None:
            (self.path / "identity.out").write_text(identity, encoding="ascii")
        if identity_rc is not None:
            (self.path / "identity.rc").write_text(identity_rc, encoding="ascii")
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
        # The readiness and PR-3 pins moved on to the E-22 release at E-22 V7 (record slice-15b2b-b1b3e-e22-completion.md).
        import e22_judge_upgrade as J
        self.assertEqual((PM.DEV_EXPECTED["releaseSha"], PM.DEV_EXPECTED["releaseManifestSha256"]),
                         (J.NEW_RELEASE, J.NEW_MANIFEST_SHA256))
        self.assertEqual((RI.DEV_PINS["releaseSha"], RI.DEV_PINS["attestedManifestSha256"]),
                         (J.NEW_RELEASE, J.NEW_MANIFEST_SHA256))
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


MERGE = "1" * 40
MERGED_AT, RUN_CREATED, RUN_DONE = "2026-10-15T01:00:00Z", "2026-10-15T01:02:00Z", "2026-10-15T01:08:00Z"
RUN_ID = "40000000000"


def identity(at="2026-10-15T01:20:00Z", host="lilith-dev-01", boot=E.BOOT_ID):
    return f"{at}\n{host}\n{C.DEV_MACHINE_ID}\n{boot}\n7.0.0-1014-gcp\nREBOOT_REQUIRED=absent\n"


class FakeGitHub:
    """Synthetic GitHub records for a hypothetical merged PR #195 and its first deploy (tests only)."""

    def __init__(self, log: bytes, **overrides):
        self.repository = C.REPOSITORY
        self._log = log
        self.pr = {"number": 195, "merged": True, "merge_commit_sha": MERGE, "merged_at": MERGED_AT,
                   "base": {"ref": "main"}}
        self.runrec = {"id": int(RUN_ID), "name": C.DEPLOY_WORKFLOW_NAME, "path": C.DEPLOY_WORKFLOW_PATH,
                       "repository": {"full_name": C.REPOSITORY}, "event": "workflow_run", "head_branch": "main",
                       "status": "completed", "conclusion": "success", "head_sha": MERGE,
                       "created_at": RUN_CREATED, "updated_at": RUN_DONE}
        self.listing = {"workflow_runs": [dict(self.runrec),
                                          {"id": 38504051046, "event": "workflow_run",
                                           "created_at": "2026-10-14T03:00:56Z"}]}
        for key, value in overrides.items():
            setattr(self, key, value)

    def pull(self, number):
        return copy.deepcopy(self.pr) if number == 195 else None

    def run(self, run_id):
        return copy.deepcopy(self.runrec) if str(self.runrec.get("id")) == run_id else {"id": -1}

    def deploy_runs(self):
        return copy.deepcopy(self.listing)

    def log(self, run_id):
        return self._log


class FreezeGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, _, w10 = fixture_texts()
        cls.new_log = log_for(E.derive_release_swap(w10[T10.RUNNING_HELD]["texts"], old=OLD, new=NEW)).encode()
        cls.old_log = log_for(w10[T10.RUNNING_HELD]["texts"]).encode()

    def host(self, **kw):
        kw.setdefault("identity", identity())
        return HostDir(HOST_RESULT, W10_RUNNING, **kw)

    def acceptance(self, host, github):
        evidence = C.completion_evidence(host, RUN_ID, github)
        statement = C.render_completion_statement(host, RUN_ID, github)
        return {"statement": statement.decode("ascii"), "record": C.acceptance_record(evidence, statement)}

    def refused(self, host, github, acceptance=None, run=RUN_ID):
        ok, reason = C.freeze_lift_admissible(host, run, acceptance, github)
        self.assertFalse(ok, reason)
        return reason

    def test_genuine_synthetic_provenance_with_the_exact_statement_is_admissible(self):
        with self.host() as host:
            github = FakeGitHub(self.new_log)
            acc = self.acceptance(host, github)
            self.assertEqual(C.freeze_lift_admissible(host, RUN_ID, acc, github), (True, "FREEZE_LIFT_ADMISSIBLE"))
            evidence = C.completion_evidence(host, RUN_ID, github)
            self.assertEqual(evidence["provenance"]["logSha256"], sha(self.new_log))
            self.assertEqual(evidence["comparison"]["result"], "EQUAL")
        self.assertEqual(C.load_record()["deploymentFreeze"], "ACTIVE")                # a judgement writes nothing

    def test_no_caller_verdict_is_accepted(self):
        """The gate takes no comparison: a forged EQUAL document has nowhere to go, and the recomputed one decides."""
        import inspect
        self.assertEqual(list(inspect.signature(C.freeze_lift_admissible).parameters),
                         ["host_dir", "run_id", "acceptance", "github"])
        with self.host() as host:
            github = FakeGitHub(self.old_log)                    # the deploy log does NOT carry the NEW texts
            forged = {"resultType": "LILITH_E19_DR5_PHASE_COMPARISON", "result": "EQUAL"}
            self.assertIn("DR5_NOT_EQUAL", self.refused(host, github, {"statement": "x", "record": forged}))

    def test_missing_deployment_or_unmerged_pr_is_not_admissible(self):
        with self.host() as host:
            unmerged = FakeGitHub(self.new_log, pr={"number": 195, "merged": False, "merge_commit_sha": None})
            self.assertIn("PR_NOT_MERGED", self.refused(host, unmerged))
            other_source = FakeGitHub(self.new_log, repository="someone/else")      # never contacted
            self.assertIn("PROVENANCE_SOURCE_REPOSITORY", self.refused(host, other_source))
            pr_missing = FakeGitHub(self.new_log, pr=None)
            self.assertIn("PR_NOT_MERGED", self.refused(host, pr_missing))
            listing_missing = FakeGitHub(self.new_log, listing={})
            self.assertIn("RUN_LISTING_UNAVAILABLE", self.refused(host, listing_missing))

    def test_wrong_run_workflow_conclusion_sha_or_order_is_refused(self):
        good = FakeGitHub(self.new_log).runrec
        cases = {
            "RUN_WRONG_WORKFLOW": dict(good, name="Repository validation", path=".github/workflows/ci.yml"),
            "RUN_WRONG_TRIGGER": dict(good, event="workflow_dispatch"),
            "RUN_NOT_SUCCESSFUL": dict(good, conclusion="failure"),
            "RUN_NOT_THE_MERGE_COMMIT": dict(good, head_sha="2" * 40),
            "RUN_WRONG_REPOSITORY": dict(good, repository={"full_name": "someone/else"}),
            "RUN_TIMES": dict(good, created_at="2026-10-15T00:59:00Z"),                # before the merge
        }
        for reason, runrec in cases.items():
            with self.subTest(reason=reason), self.host() as host:
                self.assertIn(reason, self.refused(host, FakeGitHub(self.new_log, runrec=runrec)))
        stub = dict(good, name="LILITH DEV deployment", path=".github/workflows/ci.yml", event="pull_request")
        with self.host() as host:                                         # the PR-only CI stub is never a deploy
            self.assertIn("RUN_WRONG_WORKFLOW", self.refused(host, FakeGitHub(self.new_log, runrec=stub)))
        earlier = {"workflow_runs": [dict(good), {"id": 39999999999, "event": "workflow_run",
                                                   "created_at": "2026-10-15T01:01:00Z"}]}
        with self.host() as host:                                         # not the FIRST deploy after the merge
            self.assertIn("RUN_NOT_THE_FIRST_AFTER_MERGE", self.refused(host, FakeGitHub(self.new_log, listing=earlier)))
        with self.host() as host:
            self.assertIn("RUN_NOT_FOUND", self.refused(host, FakeGitHub(self.new_log), run="40000000001"))
            self.assertIn("DEPLOY_RUN_ID", self.refused(host, FakeGitHub(self.new_log), run="not-a-run"))

    def test_log_digest_is_bound(self):
        with self.host() as host:
            github = FakeGitHub(self.new_log)
            acc = self.acceptance(host, github)
            tampered = FakeGitHub(self.new_log + b"\n")                  # another log body: another digest
            self.assertIn("COMPLETION_STATEMENT_NOT_CANONICAL", self.refused(host, tampered, acc))
            self.assertIn("RUN_LOG_UNAVAILABLE", self.refused(host, FakeGitHub(b"")))

    def test_pre_deployment_or_stale_host_evidence_is_refused(self):
        github = FakeGitHub(self.new_log)
        for label, kw in {"before deploy completed": {"identity": identity(at="2026-10-15T01:05:00Z")},
                          "the real pre-merge host U5 instant": {"identity": identity(at="2026-10-14T07:31:33Z")},
                          "equal to completion": {"identity": identity(at=RUN_DONE)}}.items():
            with self.subTest(case=label), self.host(**kw) as host:
                self.assertIn("HOST_READ_NOT_AFTER_DEPLOY", self.refused(host, github))
        with self.host(identity=identity(host="lilith-01")) as host:
            self.assertIn("HOST_NOT_DEV_THIS_BOOT", self.refused(host, github))
        with self.host(identity=identity(boot="0" * 8 + "-0000-0000-0000-" + "0" * 12)) as host:
            self.assertIn("HOST_NOT_DEV_THIS_BOOT", self.refused(host, github))
        with self.host(identity=None) as host:
            self.assertIn("HOST_IDENTITY_MISSING", self.refused(host, github))
        with self.host(identity_rc="1\n") as host:
            self.assertIn("HOST_IDENTITY_MISSING", self.refused(host, github))
        with self.host(identity="garbage\n") as host:
            self.assertIn("HOST_IDENTITY_MALFORMED", self.refused(host, github))

    def test_drift_or_unaccepted_evidence_never_lifts_the_freeze(self):
        with self.host() as host:
            self.assertIn("DR5_NOT_EQUAL", self.refused(host, FakeGitHub(self.old_log)))
            github = FakeGitHub(self.new_log)
            self.assertIn("COMPLETION_ACCEPTANCE_MISSING", self.refused(host, github, None))
            acc = self.acceptance(host, github)
            reworded = dict(acc, statement=acc["statement"].replace("I accept", "I  accept"))
            self.assertIn("COMPLETION_STATEMENT_NOT_CANONICAL", self.refused(host, github, reworded))
            bad = copy.deepcopy(acc)
            bad["record"]["evidenceSha256"] = "0" * 64
            self.assertIn("COMPLETION_ACCEPTANCE_RECORD_MISMATCH", self.refused(host, github, bad))
        with HostDir(HOST_RESULT, dict(W10_RUNNING, witnessInvocationId="0" * 32), identity=identity()) as host:
            self.assertIn("NO_BASELINE_STOP", self.refused(host, FakeGitHub(self.new_log)))


class Mb11ExactPinTests(unittest.TestCase):
    def test_the_alternative_pins_are_exactly_the_two_repinned_mb11_tools(self):
        self.assertEqual(set(C.MB11_REPINNED_SHA256), {"services/owner-memory-control/tools/mb11_signer_verifier.py",
                                                       "services/owner-memory-control/tools/mb11_restart_boundary_install.py"})
        self.assertTrue(set(C.MB11_REPINNED_SHA256) <= set(C.REPINNED_TO_NEW))
        for path, digest in C.MB11_REPINNED_SHA256.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), digest, path)
            row = [line for line in RECORD_DOC.read_text(encoding="utf-8").splitlines() if line.startswith(f"| `{path}` |")]
            self.assertEqual(len(row), 1, path)
            self.assertTrue(row[0].rstrip().endswith(f"`{digest}` |"), path)

    def test_unrelated_hashes_never_match(self):
        self.assertIsNone(C.MB11_REPINNED_SHA256.get("services/owner-memory-control/tools/mb11_dr5_target.py"))
        verifier = "services/owner-memory-control/tools/mb11_signer_verifier.py"
        for unrelated in (D.COMPLETION_RECORD_SHA256, E.NEW_MANIFEST_SHA256,
                          C.MB11_REPINNED_SHA256["services/owner-memory-control/tools/mb11_restart_boundary_install.py"]):
            self.assertNotEqual(C.MB11_REPINNED_SHA256[verifier], unrelated)


if __name__ == "__main__":
    unittest.main()
