"""drive_c1.py against a scripted fake host and fake gcloud and gh; plus static checks on the guest stages. TEST_ONLY; no network. python -B test_drive_c1.py"""
import json
import os
import re
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import drive_c1 as D

TAGS = {s[0]: s[2] for steps in D.PHASES.values() for s in steps}
STATUS = "MARKERS {m}\nGATE ActiveState={g} MainPID=1\nAPI ActiveState=active MainPID=2\nWINDOW_SCRIPTS_RUNNING {r}\n"
WINDOW = ["w0", "snap", "w1", "deploy", "w2", "w3", "w4", "w5"]


class Host:
    def __init__(self, bad=(), lost=(), markers="", gate="active", running=0):
        self.bad, self.lost, self.calls = set(bad), set(lost), []
        self.status = STATUS.format(m=markers, g=gate, r=running)

    def __call__(self, name, stage):
        self.calls.append(name)
        if name == "status_probe":
            return self.status
        if name in self.lost:
            return ""
        return f"{TAGS[name]} {'FAIL: x' if name in self.bad else 'PASS'}\n"


class Drive(unittest.TestCase):
    def go(self, phase, host):
        return D.drive(phase, host, say=lambda _: None), host.calls

    def test_window_passes_with_no_return(self):
        self.assertEqual(self.go("window", Host()), ("DRIVE_COMPLETE", WINDOW))

    def test_snapshot_comes_before_any_change_and_deploy_after_tokens(self):
        self.assertLess(WINDOW.index("snap"), WINDOW.index("w1"))
        self.assertLess(WINDOW.index("w1"), WINDOW.index("deploy"))

    def test_failures_up_to_the_snapshot_change_nothing(self):
        for i, step in enumerate(("w0", "snap")):
            with self.subTest(step=step):
                self.assertEqual(self.go("window", Host(bad=[step])), ("DRIVE_NOCHANGE", WINDOW[:i + 1]))

    def test_every_later_failure_returns_once_and_stops(self):
        for i, step in enumerate(WINDOW[2:], 2):
            with self.subTest(step=step):
                self.assertEqual(self.go("window", Host(bad=[step])), ("DRIVE_RECOVERED", WINDOW[:i + 1] + ["rb"]))

    def test_a_failed_return_stops(self):
        self.assertEqual(self.go("window", Host(bad=["w3", "rb"]))[0], "DRIVE_RECOVERY_FAILED")

    def test_lost_with_marker_continues(self):
        self.assertEqual(self.go("window", Host(lost=["w3"], markers="w3.pass@ "))[0], "DRIVE_COMPLETE")

    def test_lost_without_marker_returns(self):
        self.assertEqual(self.go("window", Host(lost=["w4"]))[0], "DRIVE_RECOVERED")

    def test_lost_local_step_is_a_failure_and_reads_no_host_status(self):
        host = Host(lost=["deploy"])
        self.assertEqual(self.go("window", host), ("DRIVE_RECOVERED", WINDOW[:4] + ["rb"]))

    def test_gateway_down_or_script_running_holds(self):
        self.assertEqual(self.go("window", Host(lost=["w3"], gate="failed"))[0], "DRIVE_HOLD")
        self.assertEqual(self.go("window", Host(lost=["w3"], running=1))[0], "DRIVE_HOLD")

    def test_return_alone_runs_one_step(self):
        self.assertEqual(self.go("return", Host()), ("DRIVE_COMPLETE", ["rb"]))
        self.assertEqual(self.go("return", Host(bad=["rb"]))[0], "DRIVE_RECOVERY_FAILED")


class Execute(unittest.TestCase):
    def test_window_needs_a_passed_preflight_and_never_runs_twice(self):
        with tempfile.TemporaryDirectory() as t:
            raw = Path(t)
            self.assertEqual(D.execute("window", Host(), raw, lambda _: None), "DRIVE_REFUSED_ORDER")
            self.assertEqual(D.execute("preflight", Host(), raw, lambda _: None), "DRIVE_COMPLETE")
            self.assertEqual(D.execute("preflight", Host(), raw, lambda _: None), "DRIVE_REFUSED_ALREADY_STARTED")
            self.assertEqual(D.execute("window", Host(), raw, lambda _: None), "DRIVE_COMPLETE")
            self.assertEqual(D.execute("window", Host(), raw, lambda _: None), "DRIVE_REFUSED_ALREADY_STARTED")
            self.assertEqual(D.status(raw)[0], "FINISHED")

    def test_approval_files(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            self.assertFalse(D.approved("preflight", "abc", root))
            (root / "APPROVED_PREPARE").write_text("abc\n")
            self.assertTrue(D.approved("preflight", "abc", root))
            self.assertFalse(D.approved("preflight", "other", root))
            (root / "APPROVED_WINDOW").write_text("abc\n")
            self.assertFalse(D.approved("window", "abc", root))
            (root / "BASELINE-SIGNED.txt").write_text("x")
            (root / "ACCEPTANCE-SIGNED.txt").write_text("x")
            self.assertTrue(D.approved("window", "abc", root))


class Deploy(unittest.TestCase):
    def fake(self, seq):
        calls = []

        def call(*args, **_):
            calls.append(args)
            return seq.pop(0)
        D.call, saved = call, D.call
        self.addCleanup(lambda: setattr(D, "call", saved))
        return calls

    def run_list(self, rid, status="completed", conclusion="success", sha=D.TARGET):
        return 0, json.dumps([{"databaseId": rid, "status": status, "conclusion": conclusion, "headSha": sha}])

    def test_refuses_when_main_moved(self):
        self.fake([(0, "f" * 40)])
        self.assertIn("not the sealed commit", D.deploy(0, 1))

    def test_passes_only_on_a_new_successful_run_at_the_target(self):
        calls = self.fake([(0, D.TARGET), self.run_list(5), (0, ""), self.run_list(5), self.run_list(6, "in_progress"), self.run_list(6)])
        self.assertTrue(D.deploy(0, 5).startswith("DEPLOY PASS"))
        self.assertIn("approved_main_sha=" + D.TARGET, calls[2])

    def test_a_failed_run_fails(self):
        self.fake([(0, D.TARGET), self.run_list(5), (0, ""), self.run_list(6, conclusion="failure")])
        self.assertTrue(D.deploy(0, 2).startswith("DEPLOY FAIL"))

    def test_no_result_fails(self):
        self.fake([(0, D.TARGET), self.run_list(5), (0, "")] + [self.run_list(5)] * 3)
        self.assertTrue(D.deploy(0, 3).startswith("DEPLOY FAIL"))

    def test_snapshot_must_be_ready(self):
        self.fake([(0, ""), (0, "CREATING\n")])
        self.assertTrue(D.snap().startswith("SNAP FAIL"))
        self.fake([(0, ""), (0, "READY\n")])
        self.assertTrue(D.snap().startswith("SNAP PASS"))


class Transport(unittest.TestCase):
    def test_a_timeout_is_lost_transport_not_a_crash(self):
        self.assertEqual(D.call(sys.executable, "-c", "import time; time.sleep(5)", timeout=0.2), (124, ""))


class Guest(unittest.TestCase):
    text = (ROOT / "guest_c1.sh").read_text(encoding="ascii")

    def test_every_stage_named_by_the_driver_exists(self):
        for steps in D.PHASES.values():
            for _, stage, _, marker in steps:
                if stage:
                    self.assertRegex(self.text, r"(?m)^%s\)" % stage.split()[0])

    def test_no_sudo_because_it_runs_as_root_and_no_token_is_echoed(self):
        self.assertNotIn("sudo", self.text)
        for line in self.text.splitlines():
            self.assertNotRegex(line, r"echo .*(TOKEN|\$\{ENVF\})(?!.*auth\.env)")

    def test_touches_only_the_named_paths(self):
        for word in ("router.yaml >", "rm -rf", "DROP ", "ALTER ", "systemctl restart ${GW}", "systemctl stop"):
            self.assertNotIn(word, self.text)

    def test_every_variable_used_is_assigned(self):
        assigned = set(re.findall(r"(?:^|[\s;(])(?:local )?([A-Za-z_][A-Za-z0-9_]*)=", self.text, re.M)) | {"Q", "q", "x", "p", "_"}
        used = set(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)[}:]", self.text))
        self.assertEqual(used - assigned - {"C1_ROOT", "C1_PY", "C1_NIC", "C1_TICK", "C1_AS", "C1_OWNER"}, set())


if __name__ == "__main__":
    unittest.main(verbosity=1)
