"""15B2b-B1b-3e M-B11 PR-A2: the P1B-10R restart-boundary install / status tool on synthetic roots (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-mb11-restart-boundary-p1b10r.md. No live system, no daemon-reload, no
unit start: unit properties come from a fake `systemctl show`, whose "reload" is simulated by the test.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _p in (TOOLS, ROOT / "services/authority-dev"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import mb10_dr5_target as T10  # noqa: E402
import mb11_restart_boundary as B  # noqa: E402
import mb11_restart_boundary_install as I  # noqa: E402
import mb11_signer_verifier as V  # noqa: E402

POSIX = os.name == "posix"
OWNER = (os.getuid(), os.getgid()) if POSIX else (0, 0)
DEPLOY = ROOT / "services/authority-dev/deploy"
DARK = lambda: I.ACTIVATION_DARK  # noqa: E731


class FakeSystemd:
    """`systemctl show` for the two signer units. `reload()` simulates the owner's daemon-reload from the files."""

    def __init__(self, root: Path):
        self.root = root
        self.state = {u: {"Id": u, "LoadState": "loaded", "ActiveState": "inactive", "SubState": "dead",
                          "UnitFileState": "static", "NeedDaemonReload": "no", "FragmentPath": f"{I.UNIT_DIR}/{u}",
                          "DropInPaths": "", "InvocationID": "", "MainPID": "0",
                          **I.RELEASE_DEFAULTS[u]} for u in I.UNITS}

    def __call__(self, names):
        return {name: dict(self.state[name]) for name in names}

    def files_changed(self):
        for u in I.UNITS:
            self.state[u]["NeedDaemonReload"] = "yes"

    def reload(self):
        for u in I.UNITS:
            directory = self.root / f"etc/systemd/system/{u}.d"
            paths = sorted(f"{I.UNIT_DIR}/{u}.d/{n}" for n in os.listdir(directory)) if directory.is_dir() else []
            facts = dict(I.RELEASE_DEFAULTS[u])
            for path in paths:
                for _s, key, value in B.parse_unit((self.root / path.lstrip("/")).read_text(encoding="utf-8")):
                    facts[key] = value
            self.state[u].update(facts, DropInPaths=" ".join(paths), NeedDaemonReload="no")


def make_root(directory: str) -> Path:
    root = Path(directory)
    unit_dir = root / "etc/systemd/system"
    unit_dir.mkdir(parents=True)
    for unit in I.UNITS:
        (unit_dir / unit).write_bytes((DEPLOY / unit).read_bytes())
        os.chmod(unit_dir / unit, I.FRAGMENT_MODE)
    return root


def obs(root, systemd, activation=DARK):
    return I.observe(root, units=systemd, activation=activation, owner=OWNER)


def phase(root, systemd, activation=DARK):
    return I.classify(obs(root, systemd, activation))["phase"]


class PinTests(unittest.TestCase):
    def test_candidate_and_release_fragment_pins_are_the_repository_bytes(self):
        for unit in I.UNITS:
            self.assertEqual(hashlib.sha256(B.candidate_bytes(unit)).hexdigest(), B.DROPINS[unit][1])
            self.assertEqual(hashlib.sha256((DEPLOY / unit).read_bytes()).hexdigest(), I.FRAGMENTS[unit])
        self.assertEqual(B.DROPINS[B.SERVICE_UNIT][1],
                         "e3faf9efa91f0238ee6110a33cf6c9f024aca1029fe05bd26fba4c21679c6b92")
        self.assertEqual(B.DROPINS[B.SOCKET_UNIT][1],
                         "85589f80764311f7e1152cf0e9ea51208662bce25806ceb524777961f579b9b9")
        self.assertEqual(I.RELEASE_SHA, V.RELEASE_SHA)

    def test_the_tool_stays_outside_the_release_tree(self):
        import release_file_set as RFS

        RFS.check_source_tree(ROOT)
        self.assertFalse(any("mb11" in path for path in RFS.SOURCE_FILES))


@unittest.skipUnless(POSIX, "POSIX ownership and modes")
class StageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_root(self.tmp.name)
        self.systemd = FakeSystemd(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def install(self, digest=None):
        digest = digest or I.plan_digest(obs(self.root, self.systemd))
        result = None
        with mock.patch.object(I.os, "fsync", wraps=os.fsync):
            result = I.install(digest, root=self.root, units=self.systemd, activation=DARK, chown=False, owner=OWNER)
        return result

    def test_exact_flow_install_then_separate_reload_then_effective(self):
        self.assertEqual(phase(self.root, self.systemd), I.P10R_0)
        digest = I.plan_digest(obs(self.root, self.systemd))
        original_classify = I.classify

        def readback(observation):                  # systemd flags NeedDaemonReload once the files exist
            if observation["overlay"][B.SERVICE_UNIT]["entries"]:
                self.systemd.files_changed()
                observation["units"] = self.systemd(I.UNITS)
            return original_classify(observation)
        with mock.patch.object(I, "classify", side_effect=readback):
            result = I.install(digest, root=self.root, units=self.systemd, activation=DARK, chown=False, owner=OWNER)
        self.assertEqual(result["result"], "P1B10R_INSTALLED", result)
        self.assertFalse(result["reloadPerformedByTool"])
        self.assertEqual(phase(self.root, self.systemd), I.P10R_1)
        for unit in I.UNITS:
            path = self.root / I.candidate_path(unit).lstrip("/")
            self.assertEqual(path.read_bytes(), B.candidate_bytes(unit))
            self.assertEqual(oct(os.stat(path).st_mode & 0o777), oct(I.FILE_MODE))
            self.assertEqual(oct(os.stat(path.parent).st_mode & 0o777), oct(I.DIR_MODE))
        self.systemd.reload()                       # the owner's separate daemon-reload (simulated)
        observed = obs(self.root, self.systemd)
        self.assertEqual(I.classify(observed)["phase"], I.P10R_2, I.classify(observed)["reasons"])
        self.assertEqual(I.boundary_reasons(observed), [])
        for name in ("startupAuthorized", "authorityGranted", "registryEffective", "authorityActive", "accepted"):
            self.assertIs(I.classify(observed)[name], False)

    def test_replay_and_stale_or_wrong_plans_are_refused(self):
        digest = I.plan_digest(obs(self.root, self.systemd))
        for bad, reason in (("x", "PLAN_DIGEST_INVALID"), ("0" * 64, "PLAN_DIGEST_MISMATCH")):
            with self.assertRaises(I.Refused) as caught:
                self.install(bad)
            self.assertEqual(caught.exception.reason, reason)
        self.systemd.state[B.SERVICE_UNIT]["TimeoutStartSec"] = "x"     # not observed: digest unaffected
        self.install(digest)
        self.systemd.files_changed()
        with self.assertRaises(I.Refused) as caught:                    # replay after the write
            self.install(digest)
        self.assertEqual(caught.exception.reason, "NOT_P10R_0:" + I.P10R_1)
        self.systemd.reload()
        with self.assertRaises(I.Refused) as caught:                    # replay after the reload
            self.install(digest)
        self.assertEqual(caught.exception.reason, "NOT_P10R_0:" + I.P10R_2)

    def test_a_changed_pre_state_invalidates_the_plan(self):
        digest = I.plan_digest(obs(self.root, self.systemd))
        self.systemd.state[B.SOCKET_UNIT]["UnitFileState"] = ""         # still P10R_0, different facts
        with self.assertRaises(I.Refused) as caught:
            self.install(digest)
        self.assertEqual(caught.exception.reason, "PLAN_DIGEST_MISMATCH")

    def test_partial_installs_stop_and_are_never_completed(self):
        svc = self.root / f"etc/systemd/system/{B.SERVICE_UNIT}.d"
        sock = self.root / f"etc/systemd/system/{B.SOCKET_UNIT}.d"
        steps = [lambda: os.mkdir(svc, 0o755),
                 lambda: (svc / B.DROPINS[B.SERVICE_UNIT][0]).write_bytes(B.candidate_bytes(B.SERVICE_UNIT)),
                 lambda: os.mkdir(sock, 0o755)]
        for step in steps:
            step()
            for path in (svc, sock, svc / B.DROPINS[B.SERVICE_UNIT][0]):
                if path.exists():
                    os.chmod(path, 0o755 if path.is_dir() else 0o644)
            self.assertEqual(phase(self.root, self.systemd), I.P10R_PARTIAL)
            with self.assertRaises(I.Refused) as caught:
                self.install("0" * 64)
            self.assertEqual(caught.exception.reason, "NOT_P10R_0:" + I.P10R_PARTIAL)

    def test_an_interrupted_install_leaves_a_partial_state_and_no_rollback(self):
        digest = I.plan_digest(obs(self.root, self.systemd))
        calls = {"n": 0}
        real_write = os.write

        def failing(fd, data):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("simulated crash")
            return real_write(fd, data)
        with mock.patch.object(I.os, "write", side_effect=failing):
            with self.assertRaises(OSError):
                I.install(digest, root=self.root, units=self.systemd, activation=DARK, chown=False, owner=OWNER)
        socket_file = self.root / I.candidate_path(B.SOCKET_UNIT).lstrip("/")
        self.assertTrue(socket_file.exists())                           # the empty O_EXCL file stays: no repair
        self.assertEqual(socket_file.read_bytes(), b"")
        self.assertEqual(phase(self.root, self.systemd), I.P10R_PARTIAL)  # the install's own window: STOP
        socket_file.write_bytes(b"[Unit]\n")                             # a torn write is not a prefix: HALT
        self.assertEqual(phase(self.root, self.systemd), I.P10R_FOREIGN)

    def test_foreign_altered_and_shadow_state_halts(self):
        def fresh():
            self.tmp.cleanup()
            self.tmp = tempfile.TemporaryDirectory()
            self.root = make_root(self.tmp.name)
            self.systemd = FakeSystemd(self.root)
            self.install()
            self.systemd.files_changed()

        mutations = {
            "extra file": lambda d: (d / "20-foreign.conf").write_bytes(b"[Service]\nRestart=always\n"),
            "altered bytes": lambda d: (d / B.DROPINS[B.SERVICE_UNIT][0]).write_bytes(b"[Service]\nRestart=no\n"),
            "wrong mode": lambda d: os.chmod(d / B.DROPINS[B.SERVICE_UNIT][0], 0o666),
            "symlinked file": lambda d: (os.unlink(d / B.DROPINS[B.SERVICE_UNIT][0]),
                                         os.symlink(str(TOOLS / "mb11_restart_boundary_dropins" / f"{B.SERVICE_UNIT}.d"
                                                        / B.DROPINS[B.SERVICE_UNIT][0]),
                                                    d / B.DROPINS[B.SERVICE_UNIT][0])),
            "extra hard link": lambda d: os.link(d / B.DROPINS[B.SERVICE_UNIT][0], self.root / "link.conf"),
        }
        for label, mutate in mutations.items():
            with self.subTest(case=label):
                fresh()
                mutate(self.root / f"etc/systemd/system/{B.SERVICE_UNIT}.d")
                self.assertEqual(phase(self.root, self.systemd), I.P10R_FOREIGN)
        for shadow in (f"run/systemd/system/{B.SERVICE_UNIT}.d", f"etc/systemd/system.control/{B.SOCKET_UNIT}.d",
                       f"run/systemd/transient/{B.SERVICE_UNIT}"):
            with self.subTest(shadow=shadow):
                self.tmp.cleanup()
                self.tmp = tempfile.TemporaryDirectory()
                self.root = make_root(self.tmp.name)
                self.systemd = FakeSystemd(self.root)
                (self.root / shadow).mkdir(parents=True)
                self.assertEqual(phase(self.root, self.systemd), I.P10R_FOREIGN)
                with self.assertRaises(I.Refused):
                    self.install("0" * 64)
        self.tmp.cleanup()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_root(self.tmp.name)
        self.systemd = FakeSystemd(self.root)
        os.mkdir(self.root / f"etc/systemd/system/{B.SOCKET_UNIT}.d", 0o755)   # not a prefix of the install order
        self.assertEqual(phase(self.root, self.systemd), I.P10R_FOREIGN)

    def test_unit_signer_and_authority_preconditions(self):
        cases = {
            "fragment changed": (lambda: (self.root / f"etc/systemd/system/{B.SERVICE_UNIT}").write_bytes(b"x"),
                                 I.P10R_UNIT),
            "enabled": (lambda: self.systemd.state[B.SERVICE_UNIT].update(UnitFileState="enabled"), I.P10R_UNIT),
            "fragment elsewhere": (lambda: self.systemd.state[B.SOCKET_UNIT].update(
                FragmentPath="/run/systemd/system/x"), I.P10R_UNIT),
            "reload pending": (lambda: self.systemd.state[B.SERVICE_UNIT].update(NeedDaemonReload="yes"), I.P10R_UNIT),
            "unexpected drop-in path": (lambda: self.systemd.state[B.SERVICE_UNIT].update(
                DropInPaths="/usr/lib/systemd/system/service.d/x.conf"), I.P10R_UNIT),
            "signer active": (lambda: self.systemd.state[B.SERVICE_UNIT].update(ActiveState="active",
                                                                                InvocationID="a" * 32), I.P10R_ACTIVE),
            "socket active": (lambda: self.systemd.state[B.SOCKET_UNIT].update(ActiveState="active"), I.P10R_ACTIVE),
        }
        for label, (mutate, expected) in cases.items():
            with self.subTest(case=label):
                self.tearDown()
                self.setUp()
                mutate()
                self.assertEqual(phase(self.root, self.systemd), expected)
                with self.assertRaises(I.Refused):
                    self.install("0" * 64)
        self.assertEqual(phase(self.root, FakeSystemd(self.root), activation=lambda: "ACTIVATION=ACCEPTED x"),
                         I.P10R_DARK)
        self.assertEqual(phase(self.root, FakeSystemd(self.root), activation=lambda: None), I.UNCLASSIFIED)
        self.assertEqual(phase(self.root, lambda names: (_ for _ in ()).throw(I.Refused("UNITS_UNREADABLE"))),
                         I.UNCLASSIFIED)

    def test_effective_property_mismatches_after_reload_fail_closed(self):
        self.install()
        self.systemd.files_changed()
        cases = {
            "restart not reloaded": {B.SERVICE_UNIT: {"Restart": "on-failure"}},
            "socket stop not effective": {B.SOCKET_UNIT: {"StopWhenUnneeded": "no"}},
            "manual start not refused": {B.SOCKET_UNIT: {"RefuseManualStart": "no"}},
            "extra drop-in path": {B.SERVICE_UNIT: {"DropInPaths": I.candidate_path(B.SERVICE_UNIT)
                                                    + " /etc/systemd/system/service.d/x.conf"}},
            "reload still pending on one unit": {B.SOCKET_UNIT: {"NeedDaemonReload": "yes"}},
        }
        for label, changes in cases.items():
            with self.subTest(case=label):
                self.systemd.reload()
                for unit, values in changes.items():
                    self.systemd.state[unit].update(values)
                result = I.classify(obs(self.root, self.systemd))
                self.assertNotIn(result["phase"], (I.P10R_2, I.P10R_0), (label, result))
        self.systemd.reload()
        self.systemd.state[B.SERVICE_UNIT].update(NeedDaemonReload="yes")
        self.systemd.state[B.SOCKET_UNIT].update(NeedDaemonReload="yes")
        self.assertEqual(phase(self.root, self.systemd), I.UNCLASSIFIED)    # reload pending yet partly effective

    def test_the_w11_verifier_reads_the_same_boundary(self):
        self.assertNotEqual(V._restart_boundary(self.root, self.systemd)["reasons"], [])
        self.install()
        self.systemd.files_changed()
        self.systemd.reload()
        observed = I.observe(self.root, units=self.systemd, activation=None, owner=OWNER)
        self.assertEqual(I.boundary_reasons(observed), [])
        self.assertFalse(observed["activationChecked"])
        # the W11 reader is exactly this tool's judgement with the production owner (root:root)
        production = I.observe(self.root, units=self.systemd, activation=None)
        self.assertEqual(V._restart_boundary(self.root, self.systemd)["reasons"], I.boundary_reasons(production))
        if OWNER != (0, 0):
            self.assertTrue(any("METADATA" in r for r in I.boundary_reasons(production)))


class ObserverDeltaTests(unittest.TestCase):
    def facts(self, installed):
        units = {"show": {u: {"Id": u, "ActiveState": "inactive",
                              "DropInPaths": I.candidate_path(u) if installed else ""} for u in I.UNITS},
                 "enablementOrDropInEntries": sorted(I.candidate_path(u).lstrip("/") for u in I.UNITS)
                 if installed else []}
        inventory = {"/etc/systemd/system": sorted(["lilith-authority-dev.service", "lilith-authority-dev.socket"]
                                                   + ([f"{u}.d" for u in I.UNITS] if installed else []))}
        return {"host": {"bootId": "b", "uptimeSeconds": "2" if installed else "1", "utcNow": "t"},
                "units": units, "namespaceInventory": inventory, "currentBlob": {"sha256": "c"}}

    def test_exactly_the_expected_observer_delta_and_nothing_else(self):
        self.assertEqual(I.observer_delta_reasons(self.facts(False), self.facts(True)), [])
        post = self.facts(True)
        post["currentBlob"]["sha256"] = "d"
        self.assertIn("OBSERVER_SECTION_CHANGED:currentBlob", I.observer_delta_reasons(self.facts(False), post))
        post = self.facts(True)
        post["units"]["enablementOrDropInEntries"].append("etc/systemd/system/lilith-authority-dev.service.d/x")
        self.assertIn("DROPIN_ENTRIES_NOT_EXACTLY_THE_CANDIDATES", I.observer_delta_reasons(self.facts(False), post))
        post = self.facts(True)
        post["units"]["show"][B.SERVICE_UNIT]["ActiveState"] = "active"
        self.assertIn("OBSERVER_SECTION_CHANGED:units", I.observer_delta_reasons(self.facts(False), post))
        self.assertIn("POST_DROPINPATHS_NOT_EXACT:" + B.SOCKET_UNIT,
                      I.observer_delta_reasons(self.facts(False), self.facts(False)))
        post = self.facts(True)
        post["host"]["bootId"] = "other"
        self.assertIn("OBSERVER_SECTION_CHANGED:host", I.observer_delta_reasons(self.facts(False), post))


class Dr5AndStaticTests(unittest.TestCase):
    SCRIPT = (ROOT / T10.DR5_SCRIPT).read_bytes()

    def test_the_overlay_adds_no_dr5_line(self):
        self.assertEqual(I.prove_dr5_unaffected(self.SCRIPT)["dr5Delta"], "EMPTY_PROVEN_FROM_PINNED_SCRIPT")
        mutated = self.SCRIPT.decode().replace('readonly AB_LATER="',
                                               'readonly AB_LATER="/etc/systemd/system/lilith-authority-dev.service.d ')
        data = mutated.encode()
        with mock.patch.object(T10, "DR5_SCRIPT_SHA256", hashlib.sha256(data).hexdigest()):
            with self.assertRaises(I.Refused) as caught:
                I.prove_dr5_unaffected(data)
        self.assertTrue(caught.exception.reason.startswith("DR5_OBSERVES_THE_OVERLAY"))

    def test_the_tool_never_reloads_starts_or_writes_outside_install(self):
        source = (TOOLS / "mb11_restart_boundary_install.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        for needle in ('"daemon-reload"', '"start"', '"stop"', '"restart"', '"enable"', "socket.", "connect(",
                       "rmtree", "os.unlink", "os.remove", "os.rename", "os.replace", "O_TRUNC"):
            self.assertNotIn(needle, source, needle)
        writers = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for call in ast.walk(node):
                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) \
                            and isinstance(call.func.value, ast.Name) and call.func.value.id == "os" \
                            and call.func.attr in ("mkdir", "write", "chmod", "fchmod", "chown", "fchown"):
                        writers.setdefault(node.name, set()).add(call.func.attr)
                    if isinstance(call, ast.Attribute) and call.attr == "O_CREAT":
                        writers.setdefault(node.name, set()).add("O_CREAT")
        self.assertEqual(set(writers), {"install"}, writers)
        commands = [node for node in ast.walk(tree) if isinstance(node, ast.List) and node.elts
                    and isinstance(node.elts[0], ast.Name) and node.elts[0].id == "SYSTEMCTL"]
        self.assertEqual([ast.literal_eval(c.elts[1]) for c in commands], ["show"])

    def test_the_transitions_stay_separate(self):
        source = (TOOLS / "mb11_restart_boundary_install.py").read_text(encoding="utf-8")
        self.assertIn("This tool never reloads", source)
        self.assertIn("never starts, stops or enables a unit", source)
        result = I._result(I.P10R_2, [], "EXACT")
        self.assertFalse(result["startupAuthorized"])
        self.assertFalse(result["reloadPerformedByTool"])
        self.assertEqual(json.loads(json.dumps(I.expected_observer_changes()))["units.show.DropInPaths"],
                         {u: I.candidate_path(u) for u in I.UNITS})


class RecordTests(unittest.TestCase):
    RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-mb11-restart-boundary-p1b10r.md"

    def test_the_record_pins_names_and_keeps_every_boundary(self):
        text = self.RECORD.read_text(encoding="utf-8")
        for value in (*(pin for _n, pin in B.DROPINS.values()), *I.FRAGMENTS.values(),
                      hashlib.sha256((TOOLS / "mb11_restart_boundary_install.py").read_bytes()).hexdigest(),
                      hashlib.sha256((TOOLS / "mb11_signer_verifier.py").read_bytes()).hexdigest()):
            self.assertTrue(value in text, value)
        for name in I.PHASES:
            self.assertTrue(f"`{name}`" in text, name)
        for od in (11, 16, 17, 18, 19, 20):
            self.assertTrue(f"OD-M11-{od}" in text, od)
        state = text.split("## 9. State", 1)[1]
        for line in ("P1B_10R = DESIGN / REPOSITORY ONLY; NOT RUN", "OVERLAY = NOT INSTALLED ON DEV",
                     "OD-M11-11 = PROPOSED (O2-D); NOT ACCEPTED", "E6_RR33_AMENDMENT = PROPOSED; NOT ACCEPTED",
                     "M-B11 = NOT AUTHORIZED", "SIGNER = INACTIVE", "K_ACT_LOADS = 0", "AUTHORITY_ACTIVE = NO",
                     "FIRST_MEMORY_READY = NOT REACHED", "PROD = NOT AUTHORIZED"):
            self.assertIn(line, state.splitlines())
        for claim in ("OD-M11-11 = ACCEPTED", "OVERLAY = INSTALLED", "M-B11 = AUTHORIZED", "AMENDMENT = ACCEPTED"):
            self.assertNotIn(claim, text)


if __name__ == "__main__":
    unittest.main()
