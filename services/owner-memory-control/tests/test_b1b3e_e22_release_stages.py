"""15B2b-B1b-3e M-B12: `e22_release_stages` (V0 … V7 of `UPGRADE_E22_JUDGE_DEV_SYNTHETIC`) on a synthetic DEV root.

Record: docs/architecture/slice-15b2b-b1b3e-e22-judge-transition.md. Reuses the E-19 transition test fixtures
(synthetic root, fake systemctl / venv / runuser, archive writer). Nothing contacts DEV.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _path in (ROOT / "services/core-api", ROOT / "services/owner-memory-control", HERE):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import test_b1b3e_e19_transition as T19  # noqa: E402  (fixtures: StageHost, write_tree, archive_for, wheels)
from test_b1b3e_e19_transition import BUILD, I  # noqa: E402

import e22_judge_upgrade as J  # noqa: E402
import e22_release_stages as S  # noqa: E402

OLD = J.OLD_RELEASE
NEW = "e22" + "0" * 37
E19_BYTES = (HERE / "fixtures/e19_new_pr1_acceptance.py.txt").read_bytes()
SIGNER_REPLACEMENT = ("5" * 32, "4242")
WITNESS_REPLACEMENT = ("6" * 32, "4343")


class E22Host(T19.StageHost):
    """The E-19 synthetic root, at the E-22 V0: OLD = ba943e1 selected; the accepted signer and witness running."""

    def __init__(self, root: Path, old_payloads: dict[str, bytes]):  # noqa: D107 - same seams as StageHost
        self.root, self.calls, self.status_calls, self.installer_failures = root, [], [], []
        (root / "etc").mkdir(parents=True)
        (root / "etc/machine-id").write_text(I.DEV_MACHINE_ID + "\n", encoding="ascii")
        (root / "proc").mkdir()
        self.units = {u: {"ActiveState": "inactive", "SubState": "dead", "MainPID": "0", "InvocationID": "",
                          "NRestarts": "0"} for u in I.WITNESS_UNITS + I.AUTHORITY_UNITS}
        T19.write_tree(root, OLD, old_payloads)
        os.symlink(f"releases/{OLD}", root / "opt/lilith-authority-dev/current")
        self.running(J.ENDING_WITNESS_INCARNATION, OLD)
        self.signer_running(J.ENDING_SIGNER_INCARNATION, OLD)
        self.custody = {p: f"synthetic {p}".encode() for p in (
            "/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred",
            "/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred",
            "/var/lib/lilith-authority-dev/authority_ledger.db")}
        for path, data in self.custody.items():
            target = root / path.lstrip("/")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)

    def signer_running(self, identity, release, restarts="0") -> None:
        self.units[S.SIGNER_SERVICE].update(ActiveState="active", SubState="running", MainPID=identity[1],
                                            InvocationID=identity[0], NRestarts=restarts)
        self.units[S.SIGNER_SOCKET].update(ActiveState="active", SubState="listening")
        link = self.root / f"proc/{identity[1]}/cwd"
        link.parent.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(link):
            link.unlink()
        os.symlink(f"{I.RELEASES}/{release}", link)
        (self.root / "run/credentials" / S.SIGNER_SERVICE).mkdir(parents=True, exist_ok=True)   # systemd, per start

    def signer_stopped(self) -> None:
        self.units[S.SIGNER_SERVICE].update(ActiveState="inactive", SubState="dead", MainPID="0", InvocationID="")
        self.units[S.SIGNER_SOCKET].update(ActiveState="inactive", SubState="dead")
        shutil.rmtree(self.root / "run/credentials" / S.SIGNER_SERVICE, ignore_errors=True)


@unittest.skipUnless(T19.POSIX, "release trees need POSIX modes and symlinks")
class StageTests(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        house = stack.enter_context(T19.stand_in_wheels())
        self.root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        self.out = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        self.new_payloads = BUILD.build_payloads(ROOT, house)                        # the merged judge (d3df4cfc)
        self.assertEqual(T19.sha(self.new_payloads[S.DELTA_MEMBER]), S.DELTA_NEW_SHA256)
        self.old_payloads = {**self.new_payloads, S.DELTA_MEMBER: E19_BYTES}          # the installed E-19 judge
        self.host = E22Host(self.root, self.old_payloads)
        self.system = self.host.system()
        self.archive, self.stamp, self.manifest = T19.archive_for(self.out, NEW, self.new_payloads)
        # A synthetic archive cannot carry the attested manifest: the stages run against these synthetic pins
        # (`PinnedReleaseTests` shows the merged pins refuse them).
        stack.enter_context(mock.patch.object(J, "NEW_RELEASE", NEW))
        stack.enter_context(mock.patch.object(J, "NEW_MANIFEST_SHA256", self.manifest))

    def status(self):
        return S.e22_status(self.system, OLD, NEW, status=self.host.status)

    def stage(self, manifest=None, archive=None, stamp=None):
        return S.stage_e22_stage(self.system, OLD, NEW, manifest or self.manifest, archive or self.archive,
                                 stamp or self.stamp, status=self.host.status)

    def select(self):
        return S.stage_e22_select(self.system, OLD, NEW, status=self.host.status)

    def retire(self, signer=SIGNER_REPLACEMENT[0], witness=WITNESS_REPLACEMENT[0]):
        return S.stage_e22_retire_old(self.system, OLD, NEW, signer, witness, status=self.host.status)

    def refused(self, reason_prefix, call, *args, **kwargs):
        with self.assertRaises(I.InstallError) as caught:
            call(*args, **kwargs)
        self.assertTrue(caught.exception.reason.startswith(reason_prefix), caught.exception.reason)

    def to_v3(self):
        self.stage()
        self.host.signer_stopped()
        self.host.stopped()

    def test_v0_is_old_only_with_both_ending_incarnations(self):
        report = self.status()
        self.assertEqual((report["state"], report["result"], report["phase"]), (S.OLD_ONLY, "PASS", J.V0),
                         report["failures"])
        self.assertEqual((report["signer"], report["witness"]), ("RUNNING", "RUNNING"))
        self.assertEqual(report["signerCwd"], f"{I.RELEASES}/{OLD}")

    def test_the_full_v0_to_v7_sequence_with_custody_untouched(self):
        before = self.host.snapshot()
        seen = [self.status()["phase"]]
        self.assertEqual(self.stage()["phase"], J.V1)
        seen.append(J.V1)
        self.host.signer_stopped()                                       # the operator's SIGNER_STOP_COMMAND
        seen.append(self.status()["phase"])
        self.host.stopped()                                              # the operator's WITNESS_STOP_COMMAND
        seen.append(self.status()["phase"])
        seen.append(self.select()["phase"])
        self.host.running(WITNESS_REPLACEMENT, NEW)                      # one K-WIT load
        seen.append(self.status()["phase"])
        self.host.signer_running(SIGNER_REPLACEMENT, NEW)                # one K-ACT load (the second)
        seen.append(self.status()["phase"])
        retired = self.retire()
        seen.append(retired["phase"])
        self.assertEqual(seen, list(J.PHASES))
        J.check_phase_order(seen)
        self.assertEqual((retired["state"], retired["result"]), (S.RETIRED, "PASS"), retired["failures"])
        self.assertFalse((self.root / f"opt/lilith-authority-dev/releases/{OLD}").exists())
        self.assertEqual(self.host.snapshot(), before)
        self.assertFalse(any(Path(c[0]).name == "systemctl" and c[1] in ("start", "stop", "restart")
                             for c in self.host.calls))                   # the tool never starts or stops a unit

    def test_select_needs_both_units_stopped(self):
        self.stage()
        self.refused("E22_PRE_PHASE:V1_NEW_STAGED", self.select)
        self.host.signer_stopped()
        self.refused("E22_PRE_PHASE:V2_SIGNER_STOPPED", self.select)
        self.host.signer_running(J.ENDING_SIGNER_INCARNATION, OLD)
        self.host.stopped()
        self.refused("E22_PRE_PHASE:VS_UNKNOWN", self.select)              # witness stopped, signer still running
        self.assertEqual(os.readlink(self.root / "opt/lilith-authority-dev/current"), f"releases/{OLD}")

    def test_stage_refuses_any_other_payload_or_manifest(self):
        cases = {
            "judge unchanged": {**self.new_payloads, S.DELTA_MEMBER: E19_BYTES},
            "another member": {**self.new_payloads, "lilith_authority_dev/core.py":
                               self.new_payloads["lilith_authority_dev/core.py"] + b"\n"},
        }
        for label, payloads in cases.items():
            with self.subTest(label=label):
                out = Path(tempfile.mkdtemp(dir=self.out))
                archive, stamp, manifest = T19.archive_for(out, NEW, payloads)
                self.refused("E22_MANIFEST_PIN_INVALID", self.stage, manifest, archive, stamp)   # not the pin
                with mock.patch.object(J, "NEW_MANIFEST_SHA256", manifest):                  # past the pin
                    self.refused("E22_PAYLOAD_DELTA", self.stage, manifest, archive, stamp)
        self.refused("E22_MANIFEST_PIN_INVALID", self.stage, "0" * 64)
        with mock.patch.object(J, "NEW_MANIFEST_SHA256", "0" * 64):                          # archive is not it
            self.refused("E22_MANIFEST_NOT_THE_PINNED_MANIFEST", self.stage, "0" * 64)
        self.refused("E22_MANIFEST_PIN_INVALID", self.stage, "nope")
        self.assertEqual(sorted(os.listdir(self.root / "opt/lilith-authority-dev/releases")), [OLD])
        self.stage()
        self.refused("E22_PRE_PHASE:V1_NEW_STAGED", self.stage)            # never re-run, never overwritten

    def test_stage_needs_v0(self):
        self.host.signer_stopped()
        self.refused("E22_PRE_PHASE", self.stage)
        self.host.signer_running(("7" * 32, "77"), OLD)                    # a different signer than the accepted one
        self.refused("E22_PRE_PHASE:VS_ENDING_INCARNATION_CHANGED", self.stage)

    def test_retire_only_for_the_accepted_replacements_both_on_new(self):
        self.to_v3()
        self.select()
        self.host.running(WITNESS_REPLACEMENT, NEW)
        self.refused("E22_PRE_PHASE:V5_WITNESS_RUNNING", self.retire)      # signer not yet replaced
        self.host.signer_running(SIGNER_REPLACEMENT, NEW)
        self.refused("E22_REPLACEMENT_INVOCATION_INVALID", self.retire, J.ENDING_SIGNER_INCARNATION[0])
        self.refused("E22_REPLACEMENT_INVOCATION_INVALID", self.retire, "x")
        self.refused("E22_ACCEPTED_REPLACEMENTS_NOT_RUNNING", self.retire, "8" * 32)
        self.assertTrue((self.root / f"opt/lilith-authority-dev/releases/{OLD}").is_dir())
        self.assertEqual(self.retire()["phase"], J.V7)

    def test_phase_stops_are_never_a_phase(self):
        self.to_v3()
        self.select()
        self.host.signer_running(J.ENDING_SIGNER_INCARNATION, OLD)          # the ending signer across the select
        self.assertEqual(self.status()["phase"], S.STOP_ACROSS_SELECT)
        self.host.signer_running(SIGNER_REPLACEMENT, NEW, restarts="1")      # an implicit restart
        self.assertEqual(self.status()["phase"], S.STOP_RESTARTED)
        self.host.signer_running(SIGNER_REPLACEMENT, "f" * 40)               # a tree that is neither release
        self.assertEqual(self.status()["phase"], S.STOP_RETIRED_TREE)
        self.host.units[S.SIGNER_SERVICE].update(ActiveState="activating", SubState="start")
        self.assertEqual(self.status()["phase"], S.STOP_TRANSITIONAL)
        self.host.signer_stopped()
        self.host.installer_failures.append("UNIT_FRAGMENT_CHANGED")
        self.assertEqual(self.status()["phase"], S.STOP_INCONSISTENT)

    def test_a_new_incarnation_on_old_is_a_stop(self):
        self.stage()
        self.host.signer_running(("9" * 32, "99"), OLD)
        self.assertEqual(self.status()["phase"], S.STOP_RESTARTED)

    def test_release_arguments_are_closed(self):
        self.refused("E22_OLD_RELEASE_NOT_THE_INSTALLED_RELEASE", S.e22_status, self.system, "a" * 40, NEW)
        self.refused("E22_NEW_RELEASE_INVALID", S.e22_status, self.system, OLD, OLD)
        self.refused("E22_NEW_RELEASE_INVALID", S.e22_status, self.system, OLD, "not-a-sha")

    def test_cli_refuses_unknown_forms(self):
        self.assertEqual(S.main(["e22-start", OLD, NEW], system=self.system), 2)
        self.assertEqual(S.main([], system=self.system), 2)


# The installer report retained from the first live `e22-status` (2026-10-18, evidence
# lilith-e22-transfer-v0-4873a9f, observations/01-V0): the host was exactly V0, the report FAIL only for these.
RETAINED_DEV_V0_INSTALLER_FAILURES = ["UNEXPECTED_PRESENT:/run/credentials/lilith-authority-dev.service",
                                      "UNIT_ACTIVE:lilith-authority-dev.service", "UNIT_ACTIVE:lilith-authority-dev.socket"]


@unittest.skipUnless(T19.POSIX, "release trees need POSIX modes and symlinks")
class RunningSignerInstallerStatusTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.host = E22Host(Path(tmp.name), {"lilith_owner_memory/pr1_acceptance.py": E19_BYTES})
        self.system = self.host.system()

    def replay(self, *extra):
        return lambda *_a: {"result": "FAIL", "failures": RETAINED_DEV_V0_INSTALLER_FAILURES + list(extra)}

    def test_the_retained_dev_v0_report_is_v0_and_only_while_the_signer_runs(self):
        report = S.e22_status(self.system, OLD, J.NEW_RELEASE, status=self.replay())
        self.assertEqual((report["result"], report["phase"], report["failures"]), ("PASS", J.V0, []))
        self.assertEqual(report["installerStatus"]["failures"], RETAINED_DEV_V0_INSTALLER_FAILURES)   # recorded as-is
        self.host.signer_stopped()                                     # the same facts with the signer stopped
        report = S.e22_status(self.system, OLD, J.NEW_RELEASE, status=self.replay())
        self.assertEqual(report["phase"], S.STOP_INCONSISTENT)

    def test_any_other_installer_failure_stays_a_stop(self):
        for extra in ("UNIT_ACTIVE:lilith-recovery-witness.service", "CREDSTORE_NOT_EMPTY", "RELEASE_SET",
                      "UNEXPECTED_PRESENT:/run/lilith-authority-dev/other"):
            with self.subTest(extra=extra):
                report = S.e22_status(self.system, OLD, J.NEW_RELEASE, status=self.replay(extra))
                self.assertEqual(report["phase"], S.STOP_INCONSISTENT)
                self.assertEqual(report["failures"], ["INSTALLER:" + extra])

    def test_the_real_installer_status_differs_by_exactly_the_admitted_set(self):
        running = set(I.status(self.system, S.INSTALLED_STAGE, OLD)["failures"])
        self.host.signer_stopped()
        stopped = set(I.status(self.system, S.INSTALLED_STAGE, OLD)["failures"])
        self.assertEqual(running - stopped, S.SIGNER_RUNNING_INSTALLER_FAILURES)
        self.assertEqual(stopped - running, set())
        self.assertEqual(sorted(S.SIGNER_RUNNING_INSTALLER_FAILURES), sorted(RETAINED_DEV_V0_INSTALLER_FAILURES))


class PinnedReleaseTests(unittest.TestCase):
    def test_the_merged_pins_refuse_any_other_release_or_manifest(self):
        self.assertEqual(J.NEW_RELEASE, "129f2bed617334be61dcac5204cd409946a7a566")
        with self.assertRaises(I.InstallError) as caught:
            S._releases(OLD, NEW)
        self.assertEqual(caught.exception.reason, "E22_NEW_RELEASE_NOT_THE_PINNED_RELEASE")
        S._releases(OLD, J.NEW_RELEASE)
        with tempfile.TemporaryDirectory() as tmp:
            host = E22Host(Path(tmp), {})
            with self.assertRaises(I.InstallError) as caught:
                S.stage_e22_stage(host.system(), OLD, J.NEW_RELEASE, "9" * 64, Path(tmp) / "a", Path(tmp) / "s",
                                  status=host.status)
        self.assertEqual(caught.exception.reason, "E22_MANIFEST_PIN_INVALID")


class SourceTests(unittest.TestCase):
    def test_reuses_the_e19_tool_and_never_runs_a_unit_command(self):
        source = (ROOT / "services/owner-memory-control/tools/e22_release_stages.py").read_text(encoding="utf-8")
        self.assertIn("import e19_release_stages as S19", source)
        for needle in ("systemctl\", \"start", "systemctl\", \"stop", "daemon-reload", "systemd-creds", "subprocess"):
            self.assertNotIn(needle, source, needle)

    def test_the_e19_tools_are_unchanged(self):
        import mb11_operator as M11
        self.assertEqual(M11.TOOL_PINS[M11.E19_OPERATOR], T19.sha((ROOT / M11.E19_OPERATOR).read_bytes()))


if __name__ == "__main__":
    unittest.main()
