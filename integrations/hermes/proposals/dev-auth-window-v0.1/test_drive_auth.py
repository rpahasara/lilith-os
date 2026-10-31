"""drive_auth.py against a scripted fake host. TEST_ONLY; no network. python -B test_drive_auth.py"""
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
for candidate in (HERE, HERE.parent / "scripts"):
    if (candidate / "drive_auth.py").exists():
        sys.path.insert(0, str(candidate))
        break
import drive_auth as D

TAGS = {s[0]: s[2] for steps in D.PHASES.values() for s in steps} | {"ra": "RA_REMOVE", "rb": "RB_RECOVER"}
STATUS = "MARKERS {m}\nGATE ActiveState={g} MainPID=1\nAPI ActiveState=active MainPID=2\nWINDOW_SCRIPTS_RUNNING {r}\n"
PRE, POST = ["a0", "a1"], ["b0", "b1", "b2", "b3", "b4", "b5", "b6"]


class Host:
    def __init__(self, bad=(), lost=(), markers="", gate="active", running=0):
        self.bad, self.lost, self.calls = set(bad), set(lost), []
        self.status = STATUS.format(m=markers, g=gate, r=running)

    def __call__(self, name, script):
        self.calls.append(name)
        if name == "status_probe":
            return self.status
        if name in self.lost:
            return ""
        return f"{TAGS[name]} {'FAIL: x' if name in self.bad else 'PASS'}\n"


class Drive(unittest.TestCase):
    def go(self, phase, host):
        return D.drive(phase, host, say=lambda _: None), host.calls

    def test_pre_passes(self):
        self.assertEqual(self.go("pre", Host()), ("DRIVE_COMPLETE", PRE))

    def test_a_failed_preflight_changes_nothing(self):
        self.assertEqual(self.go("pre", Host(bad=["a0"])), ("DRIVE_NOCHANGE", ["a0"]))

    def test_a_failed_dropin_is_removed(self):
        self.assertEqual(self.go("pre", Host(bad=["a1"])), ("DRIVE_RECOVERED", PRE + ["ra"]))

    def test_post_passes_without_recovery(self):
        self.assertEqual(self.go("post", Host()), ("DRIVE_COMPLETE", POST))

    def test_a_failed_deploy_check_changes_nothing(self):
        self.assertEqual(self.go("post", Host(bad=["b0"])), ("DRIVE_NOCHANGE", ["b0"]))

    def test_every_later_failure_recovers_once_and_stops(self):
        for i, step in enumerate(POST[1:], 1):
            with self.subTest(step=step):
                self.assertEqual(self.go("post", Host(bad=[step])), ("DRIVE_RECOVERED", POST[:i + 1] + ["rb"]))

    def test_a_failed_recovery_stops(self):
        self.assertEqual(self.go("post", Host(bad=["b3", "rb"]))[0], "DRIVE_RECOVERY_FAILED")

    def test_a_model_failure_changes_nothing_else(self):
        self.assertEqual(self.go("model", Host(bad=["m1"])), ("DRIVE_MODEL_FAILED", ["m1"]))

    def test_lost_with_marker_continues(self):
        result, calls = self.go("post", Host(lost=["b2"], markers="b2.pass@ "))
        self.assertEqual(result, "DRIVE_COMPLETE")
        self.assertIn("status_probe", calls)

    def test_lost_without_marker_recovers(self):
        self.assertEqual(self.go("post", Host(lost=["b3"]))[0], "DRIVE_RECOVERED")

    def test_lost_with_a_script_running_holds(self):
        self.assertEqual(self.go("post", Host(lost=["b3"], running=1))[0], "DRIVE_HOLD")

    def test_lost_with_the_gate_stopped_holds(self):
        self.assertEqual(self.go("post", Host(lost=["b4"], gate="inactive"))[0], "DRIVE_HOLD")

    def test_no_step_runs_twice(self):
        for step in POST:
            _, calls = self.go("post", Host(bad=[step]))
            self.assertEqual(len(calls), len(set(calls)))


class Order(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.raw = Path(self.dir.name) / "raw"

    def run_it(self, phase, host):
        return D.execute(phase, host, raw=self.raw, say=lambda _: None)

    def test_post_needs_pre_complete(self):
        host = Host()
        self.assertEqual(self.run_it("post", host), "DRIVE_REFUSED_ORDER")
        self.assertEqual(host.calls, [])

    def test_a_failed_pre_blocks_post(self):
        self.run_it("pre", Host(bad=["a1"]))
        self.assertEqual(self.run_it("post", Host()), "DRIVE_REFUSED_ORDER")

    def test_model_needs_post_complete(self):
        self.run_it("pre", Host())
        self.assertEqual(self.run_it("model", Host()), "DRIVE_REFUSED_ORDER")
        self.run_it("post", Host())
        self.assertEqual(self.run_it("model", Host()), "DRIVE_COMPLETE")

    def test_no_phase_starts_twice(self):
        self.run_it("pre", Host())
        again = Host()
        self.assertEqual(self.run_it("pre", again), "DRIVE_REFUSED_ALREADY_STARTED")
        self.assertEqual(again.calls, [])

    def test_status_tracks_phases(self):
        self.raw.mkdir()
        self.assertEqual(D.status(self.raw), ("NOT_STARTED", None))
        self.run_it("pre", Host())
        self.assertEqual(D.status(self.raw), ("FINISHED", "pre DRIVE_COMPLETE"))

    def test_a_dead_driver_is_interrupted_and_names_the_step(self):
        class Dies(Host):
            def __call__(self, name, script):
                if name == "a1":
                    raise KeyboardInterrupt
                return super().__call__(name, script)
        with self.assertRaises(KeyboardInterrupt):
            self.run_it("pre", Dies())
        self.assertEqual(D.status(self.raw), ("INTERRUPTED", "a1"))


if __name__ == "__main__":
    unittest.main()
