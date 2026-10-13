"""15B2b-B1b-3e E-19 witness restart boundary: install and read-only verification (TEST-ONLY, synthetic host).

Record: docs/architecture/slice-15b2b-b1b3e-e19-witness-restart-boundary.md. No live system: the host is a temporary
directory; systemd is a fake that derives each unit's EFFECTIVE properties from the drop-in files it last "loaded"
(parsed with the reviewed `mb11_restart_boundary.parse_unit`) and reports `NeedDaemonReload=yes` while the files on
disk differ from what it loaded. `daemon_reload()` is the fake owner command; the tool never calls it.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _p in (TOOLS, ROOT / "services/authority-dev", ROOT / "services/owner-memory-control",
           ROOT / "services/core-api"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import e19_maintenance_observer as O  # noqa: E402
import e19_p1b10_upgrade as E  # noqa: E402
import e19_witness_restart_boundary_install as W  # noqa: E402
import mb10_dr5_target as T10  # noqa: E402
import mb11_restart_boundary as B  # noqa: E402

POSIX = os.name == "posix"
H32 = lambda label: hashlib.sha256(label.encode()).hexdigest()[:32]  # noqa: E731
SEQ = H32("journal seqnum id")


def cursor(i: str) -> str:
    return f"s={SEQ};i={i};b={E.BOOT_ID.replace('-', '')};m=1a2b;t=5f1e2d3c4b5a6;x=9c8d7e6f"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FakeSystemd:
    """Effective properties = release defaults overridden by the LOADED drop-ins. NeedDaemonReload follows REAL
    systemd 255 (PR #190 review probe on a disposable host): adding drop-ins leaves it `no`; only a loaded drop-in
    that disappeared from disk sets it. `flag_added_dropins=True` models a systemd that also flags added ones. A
    reload never touches the running witness unless told to misbehave."""

    def __init__(self, root: Path):
        self.root = root
        self.loaded = {unit: {} for unit in W.UNITS}
        self.identity = E.ENDING_INCARNATION
        self.state = "RUNNING"
        self.n_restarts = "0"
        self.loads: list[str] = []
        self.restart_on_reload = False
        self.ignore = set()                    # (unit, key) a broken systemd would not apply
        self.fragment_path = {}
        self.fail = False
        self.flag_added_dropins = False

    def on_disk(self, unit: str) -> dict[str, bytes]:
        directory = self.root / f"etc/systemd/system/{unit}.d"
        if not directory.is_dir():
            return {}
        return {f"/etc/systemd/system/{unit}.d/{p.name}": p.read_bytes() for p in sorted(directory.iterdir())
                if p.name.endswith(".conf")}

    def need_reload(self, unit: str) -> str:
        disk, loaded = self.on_disk(unit), self.loaded[unit]
        if disk == loaded:
            return "no"
        return "yes" if self.flag_added_dropins or set(loaded) - set(disk) else "no"

    def daemon_reload(self):
        self.loaded = {unit: self.on_disk(unit) for unit in W.UNITS}
        if self.restart_on_reload:            # a misbehaving reload: a new incarnation, one more K-WIT load
            self.identity = (H32("restarted by reload"), "4242")
            self.loads.append(self.identity[0])

    def units(self, names):
        if self.fail:
            return None
        out = {}
        for unit in names:
            props = dict(W.RELEASE_DEFAULTS[unit])
            for data in self.loaded[unit].values():
                for _section, key, value in B.parse_unit(data.decode("ascii")):
                    if (unit, key) not in self.ignore:
                        props[key] = value
            running = self.state == "RUNNING"
            base = {"Id": unit, "LoadState": "loaded", "UnitFileState": "static",
                    "FragmentPath": self.fragment_path.get(unit, f"/etc/systemd/system/{unit}"),
                    "DropInPaths": " ".join(sorted(self.loaded[unit])),
                    "NeedDaemonReload": self.need_reload(unit),
                    "ActiveState": "active" if running else "inactive", "SubState": "running" if running else "dead",
                    "InvocationID": "", "MainPID": "0", "NRestarts": "0"}
            if unit == E.WITNESS_SERVICE:
                base.update(InvocationID=self.identity[0] if running else "",
                            MainPID=self.identity[1] if running else "0", NRestarts=self.n_restarts)
            elif self.state != "RUNNING":
                base.update(ActiveState="inactive", SubState="dead")
            else:
                base.update(SubState="listening")
            base.update(props)
            out[unit] = base
        return out


@unittest.skipUnless(POSIX, "the synthetic host needs POSIX modes")
class BoundaryTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.owner = (os.getuid(), os.getgid())
        unit_dir = self.root / "etc/systemd/system"
        unit_dir.mkdir(parents=True)
        for unit in W.UNITS:
            target = unit_dir / unit
            shutil.copyfile(ROOT / "services/recovery-witness/deploy" / unit, target)
            os.chmod(target, 0o644)
        self.systemd = FakeSystemd(self.root)
        self.tail = cursor("1f4a")
        self.retained = True
        self.activation = E.ACTIVATION_LINE_E19

    def kw(self):
        return dict(units=self.systemd.units, activation=lambda: self.activation, journal_tail=lambda: self.tail,
                    invocations=lambda unit, after: list(self.systemd.loads),
                    cursor_retained=lambda c: self.retained, owner=self.owner)

    def classify(self, after=None):
        return W.classify(W.observe(self.root, after_cursor=after, **self.kw()))

    def plan(self):
        return W.plan(root=self.root, **self.kw())

    def install(self, digest, plan_cursor):
        return W.install(digest, plan_cursor, root=self.root, chown=False, **self.kw())


class InstallationPhaseTests(BoundaryTestCase):
    def test_wrb0_plan_install_reload_effective_without_restart_or_load(self):
        self.assertEqual(self.classify()["phase"], W.WRB_0)
        plan = self.plan()
        self.assertEqual(plan["planCursor"], cursor("1f4a"))
        self.tail = cursor("2001")
        result = self.install(plan["planDigest"], plan["planCursor"])
        self.assertEqual(result["result"], "WRB_INSTALLED")
        self.assertEqual(result["readBack"]["phase"], W.WRB_1)
        self.assertIs(result["reloadPerformedByTool"], False)
        units = self.systemd.units(W.UNITS)
        self.assertEqual([units[u]["NeedDaemonReload"] for u in W.UNITS], ["no"] * 3)  # real systemd 255
        self.assertEqual([units[u]["DropInPaths"] for u in W.UNITS], [""] * 3)        # not yet loaded
        self.assertEqual(units[E.WITNESS_SERVICE]["Restart"], "on-failure")          # not yet effective
        self.systemd.daemon_reload()                                                    # the owner's own command
        self.tail = cursor("2101")
        verdict = self.classify(after=plan["planCursor"])
        self.assertEqual((verdict["phase"], verdict["reasons"]), (W.WRB_2, []))
        units = self.systemd.units(W.UNITS)
        self.assertEqual((units[E.WITNESS_SERVICE]["InvocationID"], units[E.WITNESS_SERVICE]["MainPID"],
                          units[E.WITNESS_SERVICE]["NRestarts"]), (*E.ENDING_INCARNATION, "0"))
        self.assertEqual(self.systemd.loads, [])                                        # no K-WIT load
        for unit, expected in E.RESTART_BOUNDARY["units"].items():
            self.assertEqual({k: units[unit][k] for k in expected}, expected)
        # The E-19 observer's own boundary check agrees with the effective state this stage produces.
        shaped = {"units": {u: {k: units[u].get(k) for k in e} for u, e in E.RESTART_BOUNDARY["units"].items()},
                  "dropIns": {p: O._sha_file(self.root / p.lstrip("/")) for p in E.WITNESS_DROPINS}}
        self.assertEqual(O.boundary_reasons({"witness": {"restartBoundary": shaped}}), [])
        for unit in W.UNITS:
            self.assertEqual(sha((self.root / W.candidate_path(unit).lstrip("/")).read_bytes()), W.DROPINS[unit][1])

    def test_a_reload_that_restarts_the_witness_is_a_halt(self):
        plan = self.plan()
        self.install(plan["planDigest"], plan["planCursor"])
        self.systemd.restart_on_reload = True
        self.systemd.daemon_reload()
        verdict = self.classify(after=plan["planCursor"])
        self.assertEqual(verdict["phase"], W.WRB_WITNESS)
        self.assertIn("WITNESS_NOT_THE_ACCEPTED_INCARNATION", verdict["reasons"])
        self.assertIn("WITNESS_LOADED_AFTER_THE_PLAN_CURSOR", verdict["reasons"])

    def test_a_restart_or_load_between_plan_and_install_refuses_the_install(self):
        plan = self.plan()
        for mutate in (lambda s: s.loads.append(H32("a load")), lambda s: setattr(s, "n_restarts", "1"),
                       lambda s: setattr(s, "identity", (H32("other"), "77")), lambda s: setattr(s, "state", "STOP")):
            self.setUp()
            plan = self.plan()
            mutate(self.systemd)
            with self.subTest(mutate=mutate), self.assertRaises(E.Refused) as caught:
                self.install(plan["planDigest"], plan["planCursor"])
            self.assertEqual((caught.exception.reason, caught.exception.detail), ("NOT_WRB_0", W.WRB_WITNESS))
            self.assertFalse((self.root / f"etc/systemd/system/{E.WITNESS_SERVICE}.d").exists())

    def test_the_plan_is_state_bound_and_single_use(self):
        plan = self.plan()
        for digest, cur, reason in (("0" * 64, plan["planCursor"], "PLAN_DIGEST_MISMATCH"),
                                    ("xyz", plan["planCursor"], "PLAN_DIGEST_INVALID"),
                                    (plan["planDigest"], "has space", "PLAN_CURSOR_INVALID"),
                                    (plan["planDigest"], "", "PLAN_CURSOR_INVALID")):
            with self.subTest(reason=reason), self.assertRaises(E.Refused) as caught:
                self.install(digest, cur)
            self.assertEqual(caught.exception.reason, reason)
        self.activation = "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=true"
        with self.assertRaises(E.Refused):
            self.install(plan["planDigest"], plan["planCursor"])                      # the state moved: WRB_DARK
        self.activation = E.ACTIVATION_LINE_E19
        self.install(plan["planDigest"], plan["planCursor"])
        with self.assertRaises(E.Refused) as caught:                                    # second use: not WRB_0
            self.install(plan["planDigest"], plan["planCursor"])
        self.assertEqual((caught.exception.reason, caught.exception.detail), ("NOT_WRB_0", W.WRB_1))
        self.systemd.fail = True
        with self.assertRaises(E.Refused):
            W.plan(root=self.root, **self.kw())

    def test_install_never_overwrites_an_existing_drop_in(self):
        plan = self.plan()
        foreign = self.root / f"etc/systemd/system/{E.WITNESS_SERVICE}.d"
        foreign.mkdir(mode=0o755)
        (foreign / "10-no-implicit-restart.conf").write_bytes(b"[Service]\nRestart=always\n")
        with self.assertRaises(E.Refused):
            self.install(plan["planDigest"], plan["planCursor"])
        # Even if the pre-state check were bypassed, the write path refuses to replace anything.
        with mock.patch.object(W, "classify", return_value={"phase": W.WRB_0}), \
                mock.patch.object(W, "plan_digest", return_value=plan["planDigest"]):
            with self.assertRaises(FileExistsError):
                self.install(plan["planDigest"], plan["planCursor"])
        self.assertEqual((foreign / "10-no-implicit-restart.conf").read_bytes(), b"[Service]\nRestart=always\n")

    def test_r1_wrb1_holds_whether_or_not_systemd_flags_added_drop_ins(self):
        """PR #190 review R1: real systemd 255 reports NeedDaemonReload=no after the drop-ins are written."""
        for flag in (False, True):
            self.setUp()
            self.systemd.flag_added_dropins = flag
            plan = self.plan()
            result = self.install(plan["planDigest"], plan["planCursor"])
            with self.subTest(flag=flag):
                self.assertEqual((result["result"], result["readBack"]["phase"]), ("WRB_INSTALLED", W.WRB_1))
                self.systemd.daemon_reload()
                self.assertEqual(self.classify(after=plan["planCursor"])["phase"], W.WRB_2)
        self.setUp()                                   # not loaded, yet a property already differs: never WRB_1
        plan = self.plan()
        self.install(plan["planDigest"], plan["planCursor"])
        real = self.systemd.units

        def half(names):
            out = real(names)
            out[E.WITNESS_SERVICE]["Restart"] = "no"
            return out

        self.systemd.units = half
        self.assertEqual(self.classify(after=plan["planCursor"])["phase"], W.UNCLASSIFIED)

    def test_r2_the_running_incarnations_own_journal_entries_are_not_loads(self):
        """PR #190 review R2: `journalctl -u --after-cursor` returns the running invocation's log and stop lines."""
        self.systemd.loads.append(E.ENDING_INCARNATION[0])          # a log line of the running witness
        plan = self.plan()
        self.install(plan["planDigest"], plan["planCursor"])
        self.systemd.daemon_reload()
        self.assertEqual(self.classify(after=plan["planCursor"])["phase"], W.WRB_2)
        self.systemd.loads.append(H32("a new invocation"))
        verdict = self.classify(after=plan["planCursor"])
        self.assertEqual(verdict["phase"], W.WRB_WITNESS)
        self.assertIn("WITNESS_LOADED_AFTER_THE_PLAN_CURSOR", verdict["reasons"])


class StateRefusalTests(BoundaryTestCase):
    def install_prefix(self, steps: int, *, empty_last: bool = False):
        """The install's own writes, interrupted after `steps` (directory, file) actions in order."""
        actions = []
        for unit in W.UNITS:
            actions += [("dir", unit), ("file", unit)]
        for index, (kind, unit) in enumerate(actions[:steps]):
            directory = self.root / f"etc/systemd/system/{unit}.d"
            if kind == "dir":
                directory.mkdir(mode=0o755)
                os.chmod(directory, 0o755)
            else:
                path = directory / W.DROPINS[unit][0]
                path.write_bytes(b"" if empty_last and index == steps - 1 else W.candidate_bytes(unit))
                os.chmod(path, 0o644)

    def test_every_interrupted_install_is_partial(self):
        for steps in range(1, 6):
            self.setUp()
            self.install_prefix(steps)
            with self.subTest(steps=steps):
                self.assertEqual(self.classify()["phase"], W.WRB_PARTIAL)
        self.setUp()
        self.install_prefix(2, empty_last=True)                     # O_EXCL created, bytes not yet written
        self.assertEqual(self.classify()["phase"], W.WRB_PARTIAL)

    def test_foreign_or_altered_overlays(self):
        def socket_first(t):
            (t.root / f"etc/systemd/system/{E.OWNER_SOCKET}.d").mkdir(mode=0o755)

        def altered(t):
            t.install_prefix(6)
            (t.root / W.candidate_path(E.SIGNER_SOCKET).lstrip("/")).write_bytes(b"[Unit]\nStopWhenUnneeded=no\n")

        def extra(t):
            t.install_prefix(6)
            (t.root / f"etc/systemd/system/{E.WITNESS_SERVICE}.d/20-extra.conf").write_bytes(b"[Service]\n")

        def mode(t):
            t.install_prefix(6)
            os.chmod(t.root / W.candidate_path(E.OWNER_SOCKET).lstrip("/"), 0o666)

        def symlinked(t):
            t.install_prefix(5)
            os.symlink(E.DROPIN_SOURCE / f"{E.SIGNER_SOCKET}.d/10-no-reactivation.conf",
                       t.root / W.candidate_path(E.SIGNER_SOCKET).lstrip("/"))

        def shadow_unit(t):
            target = t.root / f"run/systemd/system/{E.WITNESS_SERVICE}"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"[Service]\nExecStart=/bin/true\n")

        def shadow_dropin(t):
            (t.root / f"run/systemd/system/{E.OWNER_SOCKET}.d").mkdir(parents=True)

        for mutate in (socket_first, altered, extra, mode, symlinked, shadow_unit, shadow_dropin):
            self.setUp()
            mutate(self)
            with self.subTest(mutate=mutate.__name__):
                self.assertEqual(self.classify()["phase"], W.WRB_FOREIGN)

    def test_unknown_evidence_is_unclassified(self):
        cases = {"units": lambda t: setattr(t.systemd, "fail", True),
                 "cursor not retained": lambda t: setattr(t, "retained", False),
                 "cursor unknown": lambda t: setattr(t, "retained", None),
                 "activation silent": lambda t: setattr(t, "activation", None)}
        for name, mutate in cases.items():
            self.setUp()
            mutate(self)
            with self.subTest(name=name):
                self.assertEqual(self.classify()["phase"], W.UNCLASSIFIED)
        self.setUp()
        self.activation = "ACTIVATION=ACCEPTED {} advisoryConfigEnabled=false"
        self.assertEqual(self.classify()["phase"], W.WRB_DARK)

    def test_unit_state_not_exact(self):
        def fragment(t):
            (t.root / f"etc/systemd/system/{E.WITNESS_SERVICE}").write_bytes(b"[Service]\nRestart=always\n")

        cases = {
            "fragment bytes": fragment,
            "fragment path": lambda t: t.systemd.fragment_path.update({E.SIGNER_SOCKET: "/run/systemd/transient/x"}),
            "reload pending at WRB_0": lambda t: t.systemd.loaded.update(
                {E.WITNESS_SERVICE: {"/etc/systemd/system/old.conf": b"[Service]\n"}}),
        }
        for name, mutate in cases.items():
            self.setUp()
            mutate(self)
            with self.subTest(name=name):
                self.assertEqual(self.classify()["phase"], W.WRB_UNIT)

    def test_after_reload_every_effective_property_must_match(self):
        for unit, key in ((E.WITNESS_SERVICE, "Restart"), (E.OWNER_SOCKET, "StopWhenUnneeded"),
                          (E.SIGNER_SOCKET, "RefuseManualStart")):
            self.setUp()
            plan = self.plan()
            self.install(plan["planDigest"], plan["planCursor"])
            self.systemd.ignore.add((unit, key))
            self.systemd.daemon_reload()
            verdict = self.classify(after=plan["planCursor"])
            with self.subTest(unit=unit, key=key):
                self.assertEqual(verdict["phase"], W.WRB_UNIT)
                self.assertIn(f"{unit}:{key}", verdict["reasons"])
        self.setUp()                                                   # only some units reloaded
        plan = self.plan()
        self.install(plan["planDigest"], plan["planCursor"])
        self.systemd.loaded[E.WITNESS_SERVICE] = self.systemd.on_disk(E.WITNESS_SERVICE)
        self.assertEqual(self.classify(after=plan["planCursor"])["phase"], W.WRB_UNIT)

    def test_the_witness_must_be_the_accepted_running_incarnation(self):
        cases = {"stopped": lambda s: setattr(s, "state", "STOP"), "restarted": lambda s: setattr(s, "n_restarts", "2"),
                 "other identity": lambda s: setattr(s, "identity", (H32("x"), "1580")),
                 "historical B3": lambda s: setattr(s, "identity", E.HISTORICAL_INCARNATIONS[0]),
                 "a load": lambda s: s.loads.append(H32("load"))}
        for name, mutate in cases.items():
            self.setUp()
            mutate(self.systemd)
            with self.subTest(name=name):
                self.assertEqual(self.classify()["phase"], W.WRB_WITNESS)


class PinAndStaticTests(unittest.TestCase):
    def test_pins_are_the_merged_contract_and_the_release_fragments(self):
        self.assertEqual({W.candidate_path(u): pin for u, (_n, pin) in W.DROPINS.items()}, dict(E.WITNESS_DROPINS))
        for unit in W.UNITS:
            self.assertEqual(sha(W.candidate_bytes(unit)), W.DROPINS[unit][1])
            self.assertEqual(sha((ROOT / "services/recovery-witness/deploy" / unit).read_bytes()), W.FRAGMENTS[unit])
        import release_file_set as RFS

        payloads = RFS.runtime_payloads(ROOT)
        for unit in W.UNITS:
            self.assertEqual(sha(payloads[f"assets/{unit}"]), W.FRAGMENTS[unit])
        self.assertEqual(W.SHADOW_BASES, O.SHADOW_BASES)
        self.assertEqual(W.ACCEPTED_INCARNATION, E.ENDING_INCARNATION)
        self.assertEqual(sha((TOOLS / "e19_p1b10_upgrade.py").read_bytes()), O.E19_CONTRACT_SHA256)

    def test_a_tampered_candidate_is_refused(self):
        with tempfile.TemporaryDirectory() as work:
            fake = Path(work)
            for unit in W.UNITS:
                (fake / f"{unit}.d").mkdir()
                (fake / f"{unit}.d" / W.DROPINS[unit][0]).write_bytes(W.candidate_bytes(unit) + b"# x\n")
            with mock.patch.object(E, "DROPIN_SOURCE", fake), self.assertRaises(E.Refused):
                W.candidate_bytes(E.WITNESS_SERVICE)

    def test_dr5_output_is_unchanged_by_the_overlay(self):
        script = (ROOT / T10.DR5_SCRIPT).read_bytes()
        self.assertEqual(W.prove_dr5_unaffected(script), {"dr5Delta": "EMPTY_PROVEN_FROM_PINNED_SCRIPT",
                                                          "unitDirWriteDeniedParent": True,
                                                          "unitPropertiesRead": False})
        mutations = {
            "DR5_OBSERVES_THE_OVERLAY": script.decode().replace(
                'readonly AB_LATER="', 'readonly AB_LATER="/etc/systemd/system/lilith-recovery-witness.service.d '),
            "DR5_READS_UNIT_PROPERTIES": script.decode().replace('readonly AB_UNIT_VERBS="start ',
                                                                 'readonly AB_UNIT_VERBS="show start '),
            "DR5_UNPINNED_SYSTEMCTL_USE": script.decode() + "\n/usr/bin/systemctl show lilith-recovery-witness\n",
        }
        for reason, text in mutations.items():
            data = text.encode()
            with self.subTest(reason=reason), mock.patch.object(T10, "DR5_SCRIPT_SHA256", sha(data)):
                with self.assertRaises(E.Refused) as caught:
                    W.prove_dr5_unaffected(data)
                self.assertEqual(caught.exception.reason, reason)

    def test_the_tool_never_reloads_starts_or_writes_outside_install(self):
        source = (TOOLS / "e19_witness_restart_boundary_install.py").read_text(encoding="utf-8")
        code = source.replace(ast.get_docstring(ast.parse(source), clean=False), "")
        for needle in ('"daemon-reload"', '"start"', '"stop"', '"restart"', '"enable"', '"reload"', "import socket",
                       "socket.socket",
                       "connect(", "unlink", "rmtree", "os.remove", ".rename(", "os.replace", "plink", "gcloud"):
            self.assertNotIn(needle, code, needle)
        tree = ast.parse(source)
        writers = {"mkdir", "chmod", "chown", "fchmod", "fchown", "write"}
        for function in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
            calls = {n.func.attr for n in ast.walk(function) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Attribute) and n.func.attr in writers
                     and isinstance(n.func.value, ast.Name) and n.func.value.id == "os"}
            if function.name != "install":
                self.assertEqual(calls, set(), function.name)
        self.assertEqual(source.count("os.O_CREAT"), 1)
        self.assertIn("os.O_EXCL", source)
        self.assertIn("sys.dont_write_bytecode = True", source)

    @staticmethod
    def facts(installed, identity=E.ENDING_INCARNATION):
        show = {u: {"Id": u, "ActiveState": "active", "DropInPaths": W.candidate_path(u) if installed else ""}
                for u in W.UNITS}
        show[E.WITNESS_SERVICE].update(InvocationID=identity[0], MainPID=identity[1], NRestarts="0")
        units = {"show": show, "enablementOrDropInEntries": sorted(W.candidate_path(u).lstrip("/") for u in W.UNITS)
                 if installed else []}
        inventory = {"/etc/systemd/system": sorted(list(W.UNITS) + ([f"{u}.d" for u in W.UNITS] if installed else []))}
        return {"host": {"bootId": "b", "uptimeSeconds": "2" if installed else "1", "utcNow": "t"},
                "units": units, "namespaceInventory": inventory, "currentBlob": {"sha256": "c"}}

    def test_exactly_the_expected_host_observer_delta_and_nothing_else(self):
        pre = self.facts(False)
        self.assertEqual(W.observer_delta_reasons(pre, self.facts(True)), [])
        restarted = self.facts(True, identity=(H32("restarted"), "4242"))
        self.assertIn("OBSERVER_SECTION_CHANGED:units", W.observer_delta_reasons(pre, restarted))
        post = self.facts(True)
        post["units"]["enablementOrDropInEntries"].append(f"etc/systemd/system/{E.WITNESS_SERVICE}.d/x.conf")
        self.assertIn("DROPIN_ENTRIES_NOT_EXACTLY_THE_CANDIDATES", W.observer_delta_reasons(pre, post))
        post = self.facts(True)
        post["namespaceInventory"]["/etc/systemd/system"].append("other.service.d")
        self.assertIn("UNIT_DIR_INVENTORY_NOT_EXACTLY_THE_CANDIDATE_DIRECTORIES", W.observer_delta_reasons(pre, post))
        self.assertIn("POST_DROPINPATHS_NOT_EXACT:" + E.SIGNER_SOCKET, W.observer_delta_reasons(pre, pre))
        post = self.facts(True)
        post["currentBlob"]["sha256"] = "d"
        self.assertIn("OBSERVER_SECTION_CHANGED:currentBlob", W.observer_delta_reasons(pre, post))

    def test_results_grant_nothing(self):
        for phase in W.PHASES:
            result = W._result(phase, [], "EMPTY")
            self.assertEqual((result["reloadPerformedByTool"], result["witnessRestartedByTool"], result["u0Accepted"],
                              result["authorityGranted"]), (False, False, False, False))
        self.assertEqual(set(W.ROUTES), set(W.PHASES))


if __name__ == "__main__":
    unittest.main()
