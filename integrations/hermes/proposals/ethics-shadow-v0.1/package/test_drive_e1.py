"""drive_e1.py against a scripted fake host. TEST_ONLY; no network. python -B test_drive_e1.py"""
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
for candidate in (HERE, HERE.parent / "scripts"):
    if (candidate / "drive_e1.py").exists():
        sys.path.insert(0, str(candidate))
        break
import drive_e1 as D

GOOD = {"p0": "P0_E1 PASS (x)", "s1": "S1_STOP_P1 PASS (x)", "s2": "CHUNK1 OK x", "s2b": "CHUNK2 OK x", "s2c": "CHUNK OK x", "s3": "S3_INSTALL_E1 PASS (x)", "s4": "S4_START_E1 PASS (x)", "s5": "S5_POST_VERIFY PASS (x)", "s6": "S6_SHADOW_TEST PASS (x)",
        "s7": "S7_FINAL_VERIFY PASS (x)", "r1": "R1_RETURN_STOP PASS (x)", "r2": "R2_RETURN_REVERT PASS (x)", "r3": "R3_RETURN_START_P1 PASS (x)", "r4": "R4_FINAL_VERIFY PASS (x)"}
BAD = {"p0": "P0_E1 FAIL: ledger", "s1": "S1_STOP_P1 FAIL (x)", "s2": "CHUNK MISMATCH x", "s2b": "CHUNK1_NOT_IN_PLACE", "s2c": "CHUNK2_NOT_IN_PLACE", "s3": "S3_INSTALL_E1 FAIL: lanes", "s4": "S4_START_E1 FAIL (x)", "s5": "S5_POST_VERIFY FAIL: x", "s6": "S6_SHADOW_TEST FAIL: core_api", "s7": "S7_FINAL_VERIFY FAIL: x",
       "r1": "R1_RETURN_STOP FAIL", "r2": "R2_RETURN_REVERT FAIL", "r3": "R3_RETURN_START_P1 FAIL", "r4": "R4_FINAL_VERIFY FAIL: x"}
STATUS = "MARKERS {m}\nGATE ActiveState={g} MainPID=1 NRestarts=0 HEALTH x\nWINDOW_SCRIPTS_RUNNING {r}\n"
FORWARD = ["p0", "s1", "s2", "s2b", "s2c", "s3", "s4", "s5", "s6", "s7"]
BACK = ["r1", "r2", "r3", "r4"]


class Host:
    def __init__(self, outputs=None, markers="", gate="active", running=0):
        self.outputs, self.calls = outputs or {}, []
        self.status = STATUS.format(m=markers, g=gate, r=running)

    def __call__(self, name, script):
        self.calls.append(name)
        return self.status if name == "status_probe" else self.outputs.get(name, GOOD[name]) + "\nT1 x\n"


def forward(*names):
    return [n for n in FORWARD[:FORWARD.index(names[-1]) + 1]]


class Drive(unittest.TestCase):
    def run_host(self, host):
        return D.drive(host, say=lambda _: None), host.calls

    def test_all_pass_never_touches_the_rollback(self):
        self.assertEqual(self.run_host(Host()), ("DRIVE_COMPLETE", FORWARD))

    def test_p0_failure_changes_nothing(self):
        self.assertEqual(self.run_host(Host({"p0": BAD["p0"]})), ("DRIVE_NOCHANGE", ["p0"]))

    def test_s1_abort_before_the_stop_changes_nothing(self):
        self.assertEqual(self.run_host(Host({"s1": "S1_STOP_ABORTED ledger differs"})), ("DRIVE_NOCHANGE", ["p0", "s1"]))

    def test_every_later_failure_returns_to_p1_and_stops_going_forward(self):
        for step in FORWARD[1:]:
            with self.subTest(step=step):
                result, calls = self.run_host(Host({step: BAD[step]}))
                self.assertEqual(result, "DRIVE_RETURNED_TO_P1")
                self.assertEqual(calls, forward(step) + BACK)

    def test_no_step_runs_twice(self):
        for step in FORWARD:
            _, calls = self.run_host(Host({step: BAD[step]}))
            self.assertEqual(len(calls), len(set(calls)), calls)

    def test_lost_transport_with_the_pass_marker_continues(self):
        result, calls = self.run_host(Host({"s3": ""}, markers="s1.pass@1 s3.pass@2 "))
        self.assertEqual(result, "DRIVE_COMPLETE")
        self.assertEqual(calls, ["p0", "s1", "s2", "s2b", "s2c", "s3", "status_probe", "s4", "s5", "s6", "s7"])

    def test_lost_transport_without_a_marker_returns_to_p1(self):
        result, calls = self.run_host(Host({"s4": ""}, markers="s1.pass@1 s3.pass@2 "))
        self.assertEqual(result, "DRIVE_RETURNED_TO_P1")
        self.assertEqual(calls, ["p0", "s1", "s2", "s2b", "s2c", "s3", "s4", "status_probe"] + BACK)

    def test_lost_transport_with_a_script_still_running_holds(self):
        result, calls = self.run_host(Host({"s3": ""}, markers="s1.pass@1 ", running=1))
        self.assertEqual(result, "DRIVE_HOLD")
        self.assertEqual(calls[-1], "status_probe")

    def test_lost_transport_with_the_gate_stopped_holds(self):
        self.assertEqual(self.run_host(Host({"s6": ""}, gate="inactive"))[0], "DRIVE_HOLD")

    def test_an_unreadable_probe_holds(self):
        host = Host({"s4": ""})
        host.status = ""
        self.assertEqual(self.run_host(host)[0], "DRIVE_HOLD")

    def test_a_failed_rollback_step_stops_at_once(self):
        for step in BACK:
            with self.subTest(step=step):
                result, calls = self.run_host(Host({"s4": BAD["s4"], step: BAD[step]}))
                self.assertEqual(result, "DRIVE_ROLLBACK_FAILED")
                self.assertEqual(calls[-1], step)

    def test_lost_transport_in_the_rollback_uses_the_marker(self):
        result, calls = self.run_host(Host({"s4": BAD["s4"], "r2": ""}, markers="r1.pass@1 r2.pass@2 "))
        self.assertEqual(result, "DRIVE_RETURNED_TO_P1")
        self.assertIn("status_probe", calls)

    def test_nothing_runs_on_a_manifest_mismatch(self):
        source = Path(D.__file__).read_text(encoding="utf-8")
        self.assertIn('if got != MANIFEST_APPROVED():', source)
        self.assertLess(source.index("if got != MANIFEST_APPROVED()"), source.index("result = execute(real_run)"))


class Detached(unittest.TestCase):
    """The findings of DRIVER-REVIEW.md: completion evidence, partial runs and duplicates, with no terminal watching."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.raw = Path(self.dir.name) / "raw"

    def run_it(self, host):
        return D.execute(host, raw=self.raw, say=lambda _: None)

    def test_before_any_run_the_status_is_not_started(self):
        self.raw.mkdir()
        self.assertEqual(D.status(self.raw), ("NOT_STARTED", None))

    def test_a_finished_run_reports_its_result_last(self):
        self.assertEqual(self.run_it(Host()), "DRIVE_COMPLETE")
        self.assertEqual(D.status(self.raw), ("FINISHED", "DRIVE_COMPLETE"))
        lines = (self.raw / "drive.journal").read_text(encoding="ascii").splitlines()
        self.assertIn(" RESULT DRIVE_COMPLETE", lines[-1])

    def test_the_journal_records_every_step_and_verdict(self):
        self.run_it(Host())
        text = (self.raw / "drive.journal").read_text(encoding="ascii")
        for step in FORWARD:
            self.assertIn("BEGIN " + step, text)
            self.assertIn("END " + step, text)
            self.assertIn("STEP %s PASS" % step, text)

    def test_a_returned_run_is_not_reported_as_complete(self):
        self.assertEqual(self.run_it(Host({"s4": BAD["s4"]})), "DRIVE_RETURNED_TO_P1")
        self.assertEqual(D.status(self.raw), ("FINISHED", "DRIVE_RETURNED_TO_P1"))

    def test_a_driver_that_dies_mid_step_is_interrupted_and_names_the_step(self):
        class Dies(Host):
            def __call__(self, name, script):
                if name == "s4":
                    raise KeyboardInterrupt
                return super().__call__(name, script)
        with self.assertRaises(KeyboardInterrupt):
            self.run_it(Dies())
        self.assertEqual(D.status(self.raw), ("INTERRUPTED", "s4"))

    def test_a_dead_driver_does_not_start_a_rollback_or_resume(self):
        class Dies(Host):
            def __call__(self, name, script):
                if name == "s4":
                    raise KeyboardInterrupt
                return super().__call__(name, script)
        host = Dies()
        with self.assertRaises(KeyboardInterrupt):
            self.run_it(host)
        self.assertFalse(set(host.calls) & set(BACK))
        again = Host()
        self.assertEqual(self.run_it(again), "DRIVE_REFUSED_ALREADY_STARTED")
        self.assertEqual(again.calls, [])

    def test_a_finished_window_never_starts_again(self):
        self.run_it(Host())
        again = Host()
        self.assertEqual(self.run_it(again), "DRIVE_REFUSED_ALREADY_STARTED")
        self.assertEqual(again.calls, [])

    def test_a_refused_second_run_does_not_touch_the_journal(self):
        self.run_it(Host())
        before = (self.raw / "drive.journal").read_bytes()
        self.run_it(Host())
        self.assertEqual((self.raw / "drive.journal").read_bytes(), before)

    def test_a_second_process_is_refused_and_sees_running(self):
        self.raw.mkdir()
        code = ("import sys,time;sys.path.insert(0,%r);import drive_e1 as D;from pathlib import Path;r=Path(%r);h=D.lock(r/'drive.lock');(r/'drive.started').write_text('pid 1');print('held',flush=True);time.sleep(30)"
                % (str(Path(D.__file__).parent), str(self.raw)))
        child = subprocess.Popen([sys.executable, "-B", "-c", code], stdout=subprocess.PIPE, text=True)
        self.addCleanup(child.stdout.close)
        try:
            self.assertEqual(child.stdout.readline().strip(), "held")
            again = Host()
            self.assertEqual(self.run_it(again), "DRIVE_REFUSED_RUNNING")
            self.assertEqual(again.calls, [])
            self.assertEqual(D.status(self.raw), ("RUNNING", None))
        finally:
            child.kill()
            child.wait()
        time.sleep(0.2)
        self.assertEqual(D.status(self.raw), ("INTERRUPTED", None))   # the OS freed the lock when the process died

    def test_status_changes_nothing(self):
        self.run_it(Host())
        before = {p.name: p.read_bytes() for p in self.raw.iterdir()}
        D.status(self.raw)
        self.assertEqual({p.name: p.read_bytes() for p in self.raw.iterdir()}, before)

    def test_every_journal_line_is_flushed_to_disk(self):
        source = Path(D.__file__).read_text(encoding="utf-8")
        self.assertIn("os.fsync(self.file.fileno())", source)


if __name__ == "__main__":
    unittest.main()
