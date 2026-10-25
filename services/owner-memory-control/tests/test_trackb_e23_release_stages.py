"""Track B E-23: `e23_release_stages` (E0 … E8 of `UPGRADE_E23_PRIVACY_ANCHOR_DEV_SYNTHETIC`) on a synthetic DEV root.

Record: docs/architecture/trackb-e23-transition.md. A fake-systemd rehearsal: the E-19 synthetic root (fake
systemctl / venv / runuser, archive writer) with the witness host files, `daemon-reload` / `NeedDaemonReload`,
`systemd-tmpfiles --create`, credential blobs (synthetic bytes, never keys), /proc users and an installer `status`
seam that reports what the real one does for these facts. Nothing contacts DEV.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _path in (ROOT / "services/core-api", ROOT / "services/owner-memory-control", HERE):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import test_b1b3e_e19_transition as T19  # noqa: E402  (fixtures: StageHost, write_tree, archive_for, wheels)
from test_b1b3e_e19_transition import I  # noqa: E402

import e23_privacy_anchor_upgrade as E23  # noqa: E402
import e23_release_stages as S  # noqa: E402
import installed_layout as IL  # noqa: E402

OLD = E23.OLD_RELEASE
NEW = "e23" + "0" * 37
SIGNER_REPLACEMENT = ("5" * 32, "4242")
WITNESS_REPLACEMENT = ("6" * 32, "4343")
FOREIGN = {unit: {"ActiveState": "active", "SubState": "running", "MainPID": str(7000 + i),
                  "InvocationID": f"{i:x}" * 32, "NRestarts": "0"} for i, unit in enumerate(S.FOREIGN_UNITS, 1)}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class E23Host(T19.StageHost):
    """The synthetic root at E0: OLD = 129f2be selected, the E-22 accepted signer and witness running from it, the
    OLD witness host files loaded, K-WIT present, K-PAN absent (keygen is its own, separately authorized ceremony)."""

    def __init__(self, root: Path, old_payloads: dict[str, bytes]):  # noqa: D107 - same seams as StageHost
        self.root, self.calls, self.status_calls, self.installer_failures = root, [], [], []
        (root / "etc").mkdir(parents=True)
        (root / "etc/machine-id").write_text(I.DEV_MACHINE_ID + "\n", encoding="ascii")
        (root / "proc").mkdir()
        self.units = {u: {"ActiveState": "inactive", "SubState": "dead", "MainPID": "0", "InvocationID": "",
                          "NRestarts": "0"} for u in I.WITNESS_UNITS + I.AUTHORITY_UNITS}
        self.foreign = {unit: dict(facts) for unit, facts in FOREIGN.items()}
        T19.write_tree(root, OLD, old_payloads)
        os.symlink(f"releases/{OLD}", root / "opt/lilith-authority-dev/current")
        for member, target in I.WITNESS_UNIT_TARGETS.items():                # the installed witness unit files
            self.write(target, old_payloads[member])
        self.loaded = self.unit_sha()                                # what systemd last loaded
        (root / "var/lib/lilith-recovery-witness").mkdir(parents=True)
        self.custody = {p: f"synthetic {p}".encode() for p in (
            "/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred", S.KWIT_BLOB,
            "/var/lib/lilith-authority-dev/authority_ledger.db", "/var/lib/lilith-recovery-witness/witness.json")}
        for path, data in self.custody.items():
            self.write(path, data)
        os.chmod(self.p(S.KWIT_BLOB), 0o600)
        self.running(S.ENDING_WITNESS_INCARNATION, OLD)
        self.signer_running(S.ENDING_SIGNER_INCARNATION, OLD)

    def p(self, absolute: str) -> Path:
        return self.root / absolute.lstrip("/")

    def write(self, absolute: str, data: bytes) -> None:
        self.p(absolute).parent.mkdir(parents=True, exist_ok=True)
        self.p(absolute).write_bytes(data)

    def unit_sha(self) -> str:
        return sha(self.p(S.WITNESS_HOST_FILES["assets/lilith-recovery-witness.service"]).read_bytes())

    def keygen(self, mode=0o600) -> None:
        """Stands in for the separately authorized K-PAN keygen: an opaque blob, 0600 (never a key)."""
        self.write(S.KPAN_BLOB, b"synthetic encrypted credential blob")
        os.chmod(self.p(S.KPAN_BLOB), mode)

    # ---- units and processes ----
    def _proc(self, pid, release) -> None:
        link = self.root / f"proc/{pid}/cwd"
        link.parent.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(link):
            link.unlink()
        os.symlink(f"{I.RELEASES}/{release}", link)

    def running(self, identity, release) -> None:
        self.units[S.WITNESS_SERVICE].update(ActiveState="active", SubState="running", MainPID=identity[1],
                                             InvocationID=identity[0], NRestarts="0")
        for socket in (S.OWNER_SOCKET, S.WITNESS_SIGNER_SOCKET):
            self.units[socket].update(ActiveState="active", SubState="listening")
        self._proc(identity[1], release)
        new_unit = E23.PAYLOAD_DELTA["assets/lilith-recovery-witness.service"][1]
        names = S.WITNESS_CREDENTIALS_NEW if self.loaded == new_unit else S.WITNESS_CREDENTIALS_OLD
        creds = self.p(S.WITNESS_RUNTIME_CREDENTIALS)
        shutil.rmtree(creds, ignore_errors=True)
        creds.mkdir(parents=True)
        for name in names:
            (creds / name).write_bytes(b"")

    def stopped(self) -> None:
        shutil.rmtree(self.root / "proc" / self.units[S.WITNESS_SERVICE]["MainPID"], ignore_errors=True)
        super().stopped()
        shutil.rmtree(self.p(S.WITNESS_RUNTIME_CREDENTIALS), ignore_errors=True)

    def signer_running(self, identity, release, restarts="0") -> None:
        self.units[S.SIGNER_SERVICE].update(ActiveState="active", SubState="running", MainPID=identity[1],
                                            InvocationID=identity[0], NRestarts=restarts)
        self.units[S.SIGNER_SOCKET].update(ActiveState="active", SubState="listening")
        self._proc(identity[1], release)
        (self.p(S.SIGNER_RUNTIME_CREDENTIALS)).mkdir(parents=True, exist_ok=True)
        (self.p(S.SIGNER_RUNTIME_CREDENTIALS) / "authority-signing-key").write_bytes(b"")

    def signer_stopped(self) -> None:
        shutil.rmtree(self.root / "proc" / self.units[S.SIGNER_SERVICE]["MainPID"], ignore_errors=True)
        self.units[S.SIGNER_SERVICE].update(ActiveState="inactive", SubState="dead", MainPID="0", InvocationID="")
        self.units[S.SIGNER_SOCKET].update(ActiveState="inactive", SubState="dead")
        shutil.rmtree(self.p(S.SIGNER_RUNTIME_CREDENTIALS), ignore_errors=True)

    # ---- fake systemd ----
    def run(self, argv, cwd=None, **_kw):
        argv = list(argv)
        name = Path(argv[0]).name
        if name == "systemctl" and argv[1] == "show":
            self.calls.append(argv)
            unit = argv[-1]
            facts = dict(self.units.get(unit) or self.foreign[unit])
            facts["NeedDaemonReload"] = "yes" if unit == S.WITNESS_SERVICE and self.unit_sha() != self.loaded else "no"
            wanted = argv[2].split("=", 1)[1].split(",")
            return T19.subprocess.CompletedProcess(argv, 0, "\n".join(f"{k}={facts[k]}" for k in wanted), "")
        if name == "systemctl" and argv[1:] == ["daemon-reload"]:
            self.calls.append(argv)
            self.loaded = self.unit_sha()
            return T19.subprocess.CompletedProcess(argv, 0, "", "")
        if name == "systemd-tmpfiles":
            self.calls.append(argv)
            for line in self.p(argv[2]).read_text(encoding="ascii").splitlines():
                kind, path, mode = line.split()[:3]
                assert kind == "d"
                self.p(path).mkdir(parents=True, exist_ok=True)
                os.chmod(self.p(path), int(mode, 8))
            return T19.subprocess.CompletedProcess(argv, 0, "", "")
        return super().run(argv, cwd=cwd)

    def status(self, system: I.System, stage: str, release: str) -> dict:
        """The installer `status --expect P1B-10 <release>` seam: what the real one reports for these facts."""
        self.status_calls.append((stage, release))
        entries = [e for e in I._release_entries(system) if not e.startswith(".")]
        failures = ["RELEASE_SET"] if entries != [release] else []
        if self.units[S.SIGNER_SERVICE]["ActiveState"] == "active":
            failures += sorted(S.S22.SIGNER_RUNNING_INSTALLER_FAILURES)
        if os.listdir(self.p(S.CREDENTIAL_DIR)) != [Path(S.KWIT_BLOB).name]:
            failures.append("LISTING:" + S.CREDENTIAL_DIR)
        for member, target in I.WITNESS_UNIT_TARGETS.items():
            asset = self.p(f"{I.RELEASES}/{release}/{member}")
            if not self.p(target).is_file() or sha(self.p(target).read_bytes()) != sha(asset.read_bytes()):
                failures.append("UNIT_BYTES:" + target)
        if self.unit_sha() != self.loaded:
            failures.append("UNIT_NOT_LOADED:" + S.WITNESS_SERVICE)
        failures += list(self.installer_failures)
        return {"result": "FAIL" if failures else "PASS", "failures": failures}


@unittest.skipUnless(T19.POSIX, "release trees need POSIX modes and symlinks")
class StageTests(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        house = stack.enter_context(T19.stand_in_wheels())
        self.root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        self.out = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        self.new_payloads = IL._build_v2(ROOT, house)                              # the merged E-23 payload
        self.old_payloads = IL.installed_layout(self.new_payloads)                 # the installed 129f2be payload
        self.host = E23Host(self.root, self.old_payloads)
        self.system = self.host.system()
        with S.layout_v2():
            self.archive, self.stamp, self.manifest = T19.archive_for(self.out, NEW, self.new_payloads)
        # A synthetic archive cannot carry the attested manifest: the stages run against these synthetic pins
        # (`PinnedReleaseTests` shows the merged pins refuse them).
        stack.enter_context(mock.patch.object(E23, "NEW_RELEASE", NEW))
        stack.enter_context(mock.patch.object(E23, "NEW_MANIFEST_SHA256", self.manifest))
        stack.enter_context(mock.patch.object(S.I, "verify_archive", self.verify_v2))

    def verify_v2(self, archive, attestation, expected):
        """The installer's archive verification; `layout_v2` is bound by the stage tool (asserted here)."""
        assert set(E23.PAYLOAD_ADDED) <= I.EXPECTED_PATHS, "stage must bind layout v2"
        return T19_VERIFY(archive, attestation, expected)

    def status(self):
        return S.e23_status(self.system, OLD, NEW, status=self.host.status)

    def stage(self, manifest=None, archive=None, stamp=None):
        return S.stage_e23_stage(self.system, OLD, NEW, manifest or self.manifest, archive or self.archive,
                                 stamp or self.stamp, status=self.host.status)

    def select(self):
        return S.stage_e23_select(self.system, OLD, NEW, status=self.host.status)

    def units(self):
        return S.stage_e23_witness_units(self.system, OLD, NEW, status=self.host.status)

    def retire(self, signer=SIGNER_REPLACEMENT[0], witness=WITNESS_REPLACEMENT[0]):
        return S.stage_e23_retire_old(self.system, OLD, NEW, signer, witness, status=self.host.status)

    def refused(self, reason_prefix, call, *args, **kwargs):
        with self.assertRaises(I.InstallError) as caught:
            call(*args, **kwargs)
        self.assertTrue(caught.exception.reason.startswith(reason_prefix), caught.exception.reason)

    def to_e4(self):
        self.stage()
        self.host.signer_stopped()
        self.host.stopped()
        self.select()

    def test_e0_is_old_only_with_both_ending_incarnations(self):
        report = self.status()
        self.assertEqual((report["state"], report["result"], report["phase"]), (S.OLD_ONLY, "PASS", S.E0),
                         report["failures"])
        self.assertEqual((report["kPan"], report["witnessUnits"], report["witnessCredentials"]),
                         ("ABSENT", "OLD", S.WITNESS_CREDENTIALS_OLD))
        self.host.keygen()                                                 # K-PAN may exist before the transition
        self.assertEqual((self.status()["phase"], self.status()["kPan"]), (S.E0, "PRESENT_EXACT"))

    def test_the_full_e0_to_e8_rehearsal_in_the_e22_order(self):
        before = self.host.snapshot()
        seen = [self.status()["phase"]]
        seen.append(self.stage()["phase"])
        self.host.signer_stopped()                                         # the operator's SIGNER_STOP_COMMAND
        seen.append(self.status()["phase"])
        self.host.stopped()                                                # the operator's WITNESS_STOP_COMMAND
        seen.append(self.status()["phase"])
        seen.append(self.select()["phase"])
        self.host.keygen()                                                 # the separate K-PAN ceremony (B3 live)
        report = self.units()
        seen.append(report["phase"])
        self.assertEqual((report["witnessUnits"], report["anchor"]["names"]), ("NEW", []))
        self.host.running(WITNESS_REPLACEMENT, NEW)                        # one start: K-WIT + K-PAN
        report = self.status()
        seen.append(report["phase"])
        self.assertEqual(report["witnessCredentials"], S.WITNESS_CREDENTIALS_NEW)
        self.host.signer_running(SIGNER_REPLACEMENT, NEW)                  # one start: K-ACT
        seen.append(self.status()["phase"])
        retired = self.retire()
        seen.append(retired["phase"])
        self.assertEqual(seen, list(S.PHASES))
        self.assertEqual((retired["state"], retired["result"]), (S.RETIRED, "PASS"), retired["failures"])
        self.assertFalse(self.host.p(f"{I.RELEASES}/{OLD}").exists())
        self.assertEqual(self.host.snapshot(), before)                     # custody, ledger, witness state untouched
        self.assertEqual(retired["foreignUnits"], FOREIGN)
        mutating = [c for c in self.host.calls if Path(c[0]).name in ("systemctl", "systemd-tmpfiles")
                    and c[1] != "show"]
        self.assertEqual(mutating, [list(S.DAEMON_RELOAD), list(S.TMPFILES_CREATE)])   # never start / stop / enable

    def test_missing_kpan_refuses_before_any_witness_unit_change(self):
        self.to_e4()
        self.refused("E23_KPAN_CREDENTIAL_REQUIRED_BEFORE_WITNESS_UNITS", self.units)
        self.assertEqual(self.host.unit_sha(), E23.PAYLOAD_DELTA["assets/lilith-recovery-witness.service"][0])
        self.assertFalse(self.host.p(S.ANCHOR_DIR).exists())
        self.host.keygen(mode=0o644)                                       # present but unsafe: a STOP, not a go
        self.assertEqual(self.status()["phase"], S.STOP_KPAN)
        self.refused("E23_PRE_PHASE:" + S.STOP_KPAN, self.units)

    def test_kpan_removed_after_the_units_is_a_stop_never_a_witness_start_phase(self):
        self.to_e4()
        self.host.keygen()
        self.units()
        os.unlink(self.host.p(S.KPAN_BLOB))
        self.assertEqual(self.status()["phase"], S.STOP_KPAN)

    def test_an_interrupted_witness_units_step_never_advances(self):
        self.to_e4()
        self.host.keygen()
        target = S.WITNESS_HOST_FILES["assets/lilith-recovery-witness.service"]
        with mock.patch.object(S.I.System, "fixed", side_effect=I.InstallError("COMMAND_FAILED:systemctl")):
            self.refused("COMMAND_FAILED", self.units)                     # files replaced, reload never ran
        self.assertEqual(sha(self.host.p(target).read_bytes()), E23.PAYLOAD_DELTA["assets/lilith-recovery-witness"
                                                                                  ".service"][1])
        report = self.status()
        self.assertEqual(report["phase"], S.STOP_UNITS)                    # reload pending: never E5
        self.refused("E23_PRE_PHASE:" + S.STOP_UNITS, self.units)          # never re-run, never repaired

    def test_a_pending_reload_at_e5_is_a_stop(self):
        self.to_e4()
        self.host.keygen()
        self.assertEqual(self.units()["phase"], S.E5)
        self.host.loaded = "0" * 64                                         # systemd reports NeedDaemonReload=yes
        self.host.installer_failures.clear()
        report = S.e23_status(self.system, OLD, NEW, status=lambda *_a: {"result": "PASS", "failures": []})
        self.assertEqual((report["witnessReloadPending"], report["phase"]), ("yes", S.STOP_UNITS))

    def test_a_staged_tree_that_is_not_the_delta_is_a_stop_even_with_its_own_manifest(self):
        payloads = {**self.new_payloads, "lilith_authority_dev/core.py":
                    self.new_payloads["lilith_authority_dev/core.py"] + b"\n"}
        T19.write_tree(self.root, NEW, payloads)
        manifest = sha(I.canonical(I.manifest_for(NEW, payloads)))
        with mock.patch.object(E23, "NEW_MANIFEST_SHA256", manifest):    # even if it were the pinned manifest
            report = self.status()
        self.assertTrue(any(f.startswith("E23_DELTA_NOT_EXACT:") for f in report["failures"]), report["failures"])
        self.assertEqual(report["phase"], S.STOP_INCONSISTENT)

    def test_select_and_units_need_both_units_stopped(self):
        self.stage()
        self.refused("E23_PRE_PHASE:E1_NEW_STAGED", self.select)
        self.host.signer_stopped()
        self.refused("E23_PRE_PHASE:E2_SIGNER_STOPPED", self.select)
        self.host.signer_running(S.ENDING_SIGNER_INCARNATION, OLD)
        self.host.stopped()
        self.refused("E23_PRE_PHASE:" + S.STOP_UNKNOWN, self.select)        # witness stopped, signer still running
        self.assertEqual(os.readlink(self.root / "opt/lilith-authority-dev/current"), f"releases/{OLD}")
        self.host.keygen()
        self.refused("E23_PRE_PHASE", self.units)                          # only from E4

    def test_stage_refuses_any_other_payload_or_manifest(self):
        cases = {
            "witness credential unchanged": {**self.new_payloads, "lilith_recovery_witness/credential.py":
                                             self.old_payloads["lilith_recovery_witness/credential.py"]},
            "a signer member": {**self.new_payloads, "lilith_authority_dev/core.py":
                                self.new_payloads["lilith_authority_dev/core.py"] + b"\n"},
            "an added member missing": {k: v for k, v in self.new_payloads.items()
                                        if k != "lilith_recovery_witness/privacy_anchor.py"},
        }
        for label, payloads in cases.items():
            with self.subTest(label=label):
                out = Path(tempfile.mkdtemp(dir=self.out))
                with S.layout_v2():
                    archive, stamp, manifest = T19.archive_for(out, NEW, payloads)
                self.refused("E23_MANIFEST_PIN_INVALID", self.stage, manifest, archive, stamp)     # not the pin
                with mock.patch.object(E23, "NEW_MANIFEST_SHA256", manifest):                    # past the pin
                    # a missing layout-v2 member is the installer's own refusal; the rest are the contract delta
                    self.refused("" if label == "an added member missing" else "E23_PAYLOAD_DELTA", self.stage,
                                 manifest, archive, stamp)
        self.refused("E23_MANIFEST_PIN_INVALID", self.stage, "0" * 64)
        self.assertEqual(sorted(os.listdir(self.root / "opt/lilith-authority-dev/releases")), [OLD])
        self.stage()
        self.refused("E23_PRE_PHASE:E1_NEW_STAGED", self.stage)            # never re-run, never overwritten

    def test_unexpected_service_identity_or_state_refuses(self):
        self.host.signer_running(("7" * 32, "77"), OLD)                     # not the E-22 accepted signer
        self.refused("E23_PRE_PHASE:" + S.STOP_RESTARTED, self.stage)
        self.host.signer_running(S.ENDING_SIGNER_INCARNATION, OLD, restarts="1")
        self.refused("E23_PRE_PHASE:" + S.STOP_RESTARTED, self.stage)
        self.host.signer_running(S.ENDING_SIGNER_INCARNATION, OLD)
        self.host.units[S.WITNESS_SERVICE].update(ActiveState="activating", SubState="start")
        self.refused("E23_PRE_PHASE:" + S.STOP_TRANSITIONAL, self.stage)
        self.host.running(S.ENDING_WITNESS_INCARNATION, OLD)
        self.host.installer_failures.append("UNIT_ACTIVE:lilith-recovery-witness.service")
        self.refused("E23_PRE_PHASE:" + S.STOP_INCONSISTENT, self.stage)
        self.assertEqual(sorted(os.listdir(self.root / "opt/lilith-authority-dev/releases")), [OLD])

    def test_old_cannot_be_retired_while_anything_uses_it(self):
        self.to_e4()
        self.host.keygen()
        self.units()
        self.host.running(WITNESS_REPLACEMENT, NEW)
        self.refused("E23_PRE_PHASE:E6_WITNESS_RUNNING", self.retire)      # signer not yet replaced
        self.host.signer_running(SIGNER_REPLACEMENT, NEW)
        self.refused("E23_REPLACEMENT_INVOCATION_INVALID", self.retire, S.ENDING_SIGNER_INCARNATION[0])
        self.refused("E23_ACCEPTED_REPLACEMENTS_NOT_RUNNING", self.retire, "8" * 32)
        stray = self.root / "proc/999"                                      # e.g. an operator shell in OLD
        stray.mkdir()
        os.symlink(f"{I.RELEASES}/{OLD}/venv", stray / "cwd")
        self.refused("E23_OLD_RELEASE_IN_USE:999", self.retire)
        os.unlink(stray / "cwd")
        (stray / "maps").write_text(f"7f00-7f10 r-xp 0 08:01 1 {I.RELEASES}/{OLD}/venv/lib/x.so\n", encoding="ascii")
        self.refused("E23_OLD_RELEASE_IN_USE:999", self.retire)
        shutil.rmtree(stray)
        self.assertTrue(self.host.p(f"{I.RELEASES}/{OLD}").is_dir())
        self.assertEqual(self.retire()["phase"], S.E8)

    def test_stops_are_never_a_phase(self):
        self.to_e4()
        self.host.signer_running(S.ENDING_SIGNER_INCARNATION, OLD)          # the ending signer across the select
        self.assertEqual(self.status()["phase"], S.STOP_ACROSS_SELECT)
        self.host.signer_stopped()
        self.host.running(WITNESS_REPLACEMENT, NEW)                         # witness started before the units
        self.assertNotIn(self.status()["phase"], S.PHASES)
        self.host.stopped()
        self.host.keygen()
        self.units()
        (self.host.p(S.ANCHOR_DIR) / "chain").mkdir()
        (self.host.p(S.ANCHOR_DIR) / "chain/00000001.json").write_bytes(b"{}")   # an anchor write: never E-23's
        self.assertEqual(self.status()["phase"], S.STOP_UNITS)

    def test_release_arguments_are_closed(self):
        self.refused("E23_OLD_RELEASE_NOT_THE_INSTALLED_RELEASE", S.e23_status, self.system, "a" * 40, NEW)
        self.refused("E23_NEW_RELEASE_INVALID", S.e23_status, self.system, OLD, OLD)
        self.refused("E23_NEW_RELEASE_NOT_THE_PINNED_RELEASE", S.e23_status, self.system, OLD, "b" * 40)

    def test_a_non_dev_host_is_refused_by_every_mutating_form(self):
        system = self.host.system(hostname=lambda: "lilith-prod-01")
        for form in (["e23-stage", OLD, NEW, self.manifest, str(self.archive), str(self.stamp)],
                     ["e23-select", OLD, NEW], ["e23-witness-units", OLD, NEW], ["e23-status", OLD, NEW],
                     ["e23-retire-old", OLD, NEW, "5" * 32, "6" * 32]):
            with self.subTest(form=form[0]):
                self.assertEqual(S.main(form, system=system), 2)
        self.assertEqual(S.main(["e23-start", OLD, NEW], system=self.system), 2)


T19_VERIFY = I.verify_archive


class PinnedReleaseTests(unittest.TestCase):
    def test_the_merged_pins_refuse_any_other_release_or_manifest(self):
        self.assertEqual(E23.NEW_RELEASE, "57bff671fbfe5df4e59248d5d69338dc0ba05846")
        with self.assertRaises(I.InstallError) as caught:
            S._releases(OLD, NEW)
        self.assertEqual(caught.exception.reason, "E23_NEW_RELEASE_NOT_THE_PINNED_RELEASE")
        S._releases(OLD, E23.NEW_RELEASE)
        with tempfile.TemporaryDirectory() as tmp:
            system = I.System(root=Path(tmp), run=lambda *a, **k: None, user=lambda _n: None, group=lambda _n: None,
                              grouplist=lambda _n, gid: [gid], euid=lambda: 0, hostname=lambda: I.DEV_HOSTNAME)
            Path(tmp, "etc").mkdir()
            Path(tmp, "etc/machine-id").write_text(I.DEV_MACHINE_ID + "\n", encoding="ascii")
            with self.assertRaises(I.InstallError) as caught:
                S.stage_e23_stage(system, OLD, E23.NEW_RELEASE, "9" * 64, Path(tmp) / "a", Path(tmp) / "s")
        self.assertEqual(caught.exception.reason, "E23_MANIFEST_PIN_INVALID")

    def test_ending_incarnations_are_the_e22_accepted_replacements(self):
        record = (ROOT / "docs/architecture/slice-15b2b-b1b3e-e22-completion.md").read_text(encoding="utf-8")
        self.assertIn(f"witness {S.ENDING_WITNESS_INCARNATION[0][:8]}…/{S.ENDING_WITNESS_INCARNATION[1]}", record)
        self.assertIn(f"signer {S.ENDING_SIGNER_INCARNATION[0][:8]}…/{S.ENDING_SIGNER_INCARNATION[1]}", record)
        self.assertIn(S.ENDING_WITNESS_INCARNATION[0], record)
        self.assertIn(S.ENDING_SIGNER_INCARNATION[0], record)


class SourceTests(unittest.TestCase):
    def test_layout_v2_binding_equals_the_accepted_v2_installer(self):
        import install_authority_dev_v2 as V2

        self.assertEqual(frozenset(E23.PAYLOAD_ADDED), V2.ADDED_RUNTIME_PATHS)
        with S.layout_v2():
            self.assertEqual(I.EXPECTED_PATHS, V2.EXPECTED_PATHS)
        self.assertEqual(I.EXPECTED_PATHS, V2.EXPECTED_PATHS - V2.ADDED_RUNTIME_PATHS)

    def test_why_v2_is_not_bundled_it_would_put_the_remote_cwd_on_sys_path(self):
        source = (ROOT / "services/authority-dev/ceremony/install_authority_dev_v2.py").read_text(encoding="utf-8")
        module = types.ModuleType("install_authority_dev_v2")
        module.__file__ = "<mb6-bundle:install_authority_dev_v2>"
        before = list(sys.path)
        try:
            with tempfile.TemporaryDirectory() as cwd, contextlib.chdir(cwd), \
                    mock.patch.dict(sys.modules, {"install_authority_dev": I}):
                exec(compile(source, module.__file__, "exec"), module.__dict__)  # noqa: S102 - the reviewed source
            self.assertNotEqual(sys.path, before)
        finally:
            sys.path[:] = before

    def test_bundled_stage_tool_and_contract_never_touch_sys_path(self):
        for name in ("e23_release_stages", "e23_privacy_anchor_upgrade"):
            source = (ROOT / f"services/owner-memory-control/tools/{name}.py").read_text(encoding="utf-8")
            module = types.ModuleType(name)
            module.__file__ = f"<mb6-bundle:{name}>"
            before = list(sys.path)
            exec(compile(source, module.__file__, "exec"), module.__dict__)  # noqa: S102 - the reviewed source
            self.assertEqual(sys.path, before, name)

    def test_never_starts_stops_or_reads_a_credential(self):
        source = (ROOT / "services/owner-memory-control/tools/e23_release_stages.py").read_text(encoding="utf-8")
        for needle in ("\"start\"", "\"stop\"", "\"restart\"", "\"enable\"", "systemd-creds", "subprocess",
                       "read_bytes()", "open("):
            if needle == "read_bytes()":
                self.assertEqual(source.count(needle), 1, needle)          # the one NEW release asset read
                continue
            self.assertNotIn(needle, source, needle)

    def test_the_e22_and_e19_tools_are_reused_unchanged(self):
        import e22_operator as E22OP

        for path in (E22OP.STAGES, E22OP.X.STAGES, E22OP.M9.INSTALLER):
            self.assertEqual(sha((ROOT / path).read_bytes()), E22OP.TOOL_PINS[path], path)


if __name__ == "__main__":
    unittest.main()
