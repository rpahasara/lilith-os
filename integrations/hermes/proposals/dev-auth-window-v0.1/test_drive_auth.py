"""drive_auth.py, resume edition, against a scripted fake host; plus static checks on the scripts. TEST_ONLY; no network. python -B test_drive_auth.py"""
import re
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

TAGS = {s[0]: s[2] for steps in D.PHASES.values() for s in steps} | {"rb": "RB_RESTORE"}
STATUS = "MARKERS {m}\nGATE ActiveState={g} MainPID=1\nAPI ActiveState=active MainPID=2\nWINDOW_SCRIPTS_RUNNING {r}\n"
POST = ["c0", "b1b", "b2", "b3", "b4", "b5", "b6"]
SCRIPTS = HERE.parent / "scripts"


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

    def test_post_passes_without_recovery(self):
        self.assertEqual(self.go("post", Host()), ("DRIVE_COMPLETE", POST))

    def test_a_failed_resume_preflight_changes_nothing(self):
        self.assertEqual(self.go("post", Host(bad=["c0"])), ("DRIVE_NOCHANGE", ["c0"]))

    def test_every_later_failure_restores_once_and_stops(self):
        for i, step in enumerate(POST[1:], 1):
            with self.subTest(step=step):
                self.assertEqual(self.go("post", Host(bad=[step])), ("DRIVE_RECOVERED", POST[:i + 1] + ["rb"]))

    def test_a_failed_recovery_stops(self):
        self.assertEqual(self.go("post", Host(bad=["b3", "rb"]))[0], "DRIVE_RECOVERY_FAILED")

    def test_a_model_failure_changes_nothing_else(self):
        self.assertEqual(self.go("model", Host(bad=["m1"])), ("DRIVE_MODEL_FAILED", ["m1"]))

    def test_lost_with_marker_continues(self):
        self.assertEqual(self.go("post", Host(lost=["b2"], markers="b2.pass@ "))[0], "DRIVE_COMPLETE")

    def test_lost_without_marker_recovers(self):
        self.assertEqual(self.go("post", Host(lost=["b3"]))[0], "DRIVE_RECOVERED")

    def test_lost_with_a_script_running_holds(self):
        self.assertEqual(self.go("post", Host(lost=["b3"], running=1))[0], "DRIVE_HOLD")

    def test_lost_with_the_gate_stopped_holds(self):
        self.assertEqual(self.go("post", Host(lost=["b4"], gate="inactive"))[0], "DRIVE_HOLD")


class Gates(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.raw = self.root / "raw"

    def run_it(self, phase, host):
        return D.execute(phase, host, raw=self.raw, say=lambda _: None)

    def test_model_needs_post_complete(self):
        self.assertEqual(self.run_it("model", Host()), "DRIVE_REFUSED_ORDER")
        self.run_it("post", Host(bad=["b3"]))
        self.assertEqual(self.run_it("model", Host()), "DRIVE_REFUSED_ORDER")

    def test_no_phase_starts_twice(self):
        self.run_it("post", Host())
        again = Host()
        self.assertEqual(self.run_it("post", again), "DRIVE_REFUSED_ALREADY_STARTED")
        self.assertEqual(again.calls, [])

    def test_the_model_phase_needs_its_own_approval(self):
        self.assertFalse(D.model_approved("abc", self.root))
        (self.root / "APPROVED_MODEL").write_text("abd", encoding="ascii")
        self.assertFalse(D.model_approved("abc", self.root))
        (self.root / "APPROVED_MODEL").write_text("abc", encoding="ascii")
        self.assertTrue(D.model_approved("abc", self.root))

    def test_a_dead_driver_is_interrupted_and_names_the_step(self):
        class Dies(Host):
            def __call__(self, name, script):
                if name == "b3":
                    raise KeyboardInterrupt
                return super().__call__(name, script)
        with self.assertRaises(KeyboardInterrupt):
            self.run_it("post", Dies())
        self.assertEqual(D.status(self.raw), ("INTERRUPTED", "b3"))


@unittest.skipUnless((SCRIPTS / "c0_resume_preflight_ro.sh").exists(), "run from the package")
class Static(unittest.TestCase):
    """The operator is not root. The B1 defect: a redirect is opened by the shell before sudo runs, so the simulation, which runs as root, never saw it."""

    def lines(self):
        for path in sorted(SCRIPTS.glob("*.sh")):
            for number, line in enumerate(path.read_text(encoding="ascii").splitlines(), 1):
                if not line.startswith(("ENVF=", "W=", "F=", "D=", "#")):
                    yield path.name, number, line

    def test_no_root_only_path_is_opened_by_the_unprivileged_shell(self):
        for name, number, line in self.lines():
            if "sudo -n bash -c" in line:
                continue                   # the whole command runs as root, redirect included
            self.assertNotRegex(line, r"<\s*\$\{(ENVF|W|F)\}", f"{name}:{number}")
            self.assertNotRegex(line, r">>?\s*\$\{(ENVF|W|F)", f"{name}:{number}")
            self.assertNotRegex(line, r"sudo -n [^|\"]*<\s*/", f"{name}:{number}")

    def test_every_root_only_path_goes_through_sudo(self):
        for name, number, line in self.lines():
            if re.search(r"\$\{(ENVF|W)\}", line):
                self.assertIn("sudo -n", line, f"{name}:{number}")

    def test_the_resume_preflight_cannot_change_anything(self):
        body = (SCRIPTS / "c0_resume_preflight_ro.sh").read_text(encoding="ascii").split('[ "$(hostname)" = lilith-dev-01 ]')[1]
        for word in ("tee", "touch", "mv", "rm", "ln", "restart", "daemon-reload", "stop", "start", "conf", "link"):
            self.assertNotRegex(body, r"(^|[\s;(])" + word + r"(\s|$)", word)


if __name__ == "__main__":
    unittest.main()
