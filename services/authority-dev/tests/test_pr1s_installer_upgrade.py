"""15B2b-B1b-3e PR-1S installer tests: UPGRADE_EXISTING_DEV_SYNTHETIC and the PR-1 phases.

Everything runs against a temporary host tree with injected OS lookups and
commands (the L2 `FakeHost`). The installer never runs `systemctl start`,
`enable`, `daemon-reload`, `systemd-creds`, or a keygen here, and no test
touches `/`, DEV, or PROD. The OLD release is a synthetic stand-in for the
installed `9ac7de2` (the accepted SHA string, different unit/CLI bytes).
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import pr1s_fixtures as X
import test_custody_preparation as L2
from test_custody_preparation import FakeHost, build_archive, fake_wheels

import install_authority_dev as I

POSIX = os.name == "posix"
OLD = I.ACCEPTED_OLD_RELEASE
NEW = L2.SHA
STAND_IN_CURRENT = b"TEST_ONLY stand-in CURRENT ciphertext (never a credential)"
OLD_SERVICE = (X.ROOT / "services/authority-dev/deploy/lilith-authority-dev.service").read_bytes().replace(
    b" /var/lib/lilith-authority-custody /etc/lilith-recovery-witness", b"")
OLD_KEYGEN = (X.ROOT / "services/authority-dev/ceremony/lilith_authority_keygen_dev.py").read_bytes() + b"\n# 9ac7de2\n"


@contextlib.contextmanager
def accepted_current():
    """The accepted CURRENT SHA-256 is the real `6a61c350…`; tests pin the stand-in's."""
    saved = I.ACCEPTED_CURRENT_SHA256
    I.ACCEPTED_CURRENT_SHA256 = hashlib.sha256(STAND_IN_CURRENT).hexdigest()
    try:
        yield
    finally:
        I.ACCEPTED_CURRENT_SHA256 = saved


def old_host(directory: str) -> tuple[FakeHost, I.System]:
    """A host exactly at `status --expect L2b.2 <OLD>` (the accepted live closure shape)."""
    host = FakeHost(directory)
    system = host.system()
    I.stage_accounts(system)
    top = host.root / f"opt/lilith-authority-dev/releases/{OLD}"
    for member, data in {"assets/lilith-authority-dev.service": OLD_SERVICE,
                         "assets/lilith-authority-dev.socket": (X.ROOT / "services/authority-dev/deploy/"
                                                                "lilith-authority-dev.socket").read_bytes(),
                         "assets/lilith-authority-dev.tmpfiles.conf": b"d /run/lilith-authority-dev 0700 root root -\n",
                         I.CLI_PATH: OLD_KEYGEN}.items():
        path = top / member
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    for directory_, subdirs, files in os.walk(host.root / "opt/lilith-authority-dev"):
        os.chmod(directory_, 0o755)
    os.symlink(f"releases/{OLD}", host.root / "opt/lilith-authority-dev/current")
    for member, target in I.UNIT_TARGETS.items():
        (host.root / target.lstrip("/")).write_bytes((top / member).read_bytes())
        os.chmod(host.root / target.lstrip("/"), 0o644)
    host.daemon_reload()
    keygen = host.root / I.KEYGEN_CLI.lstrip("/")
    keygen.write_bytes(OLD_KEYGEN)
    os.chmod(keygen, 0o755)
    host.systemd_creds_setup()
    store = host.root / "etc/credstore.encrypted"
    store.mkdir(mode=0o700)
    os.chmod(store, 0o700)
    blob = store / "lilith-authority-dev.owner-actor.cred"
    blob.write_bytes(STAND_IN_CURRENT)
    os.chmod(blob, 0o600)
    return host, system


def baseline_file(directory: str, system: I.System, **overrides) -> Path:
    observed = I.observe_baseline(system, OLD)
    value = {key: observed[key] for key in I.BASELINE_FIELDS}
    value.update(overrides)
    path = Path(directory) / "baseline.json"
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return path


def mark_reload_needed(host: FakeHost) -> None:
    host.units["lilith-authority-dev.service"]["NeedDaemonReload"] = "yes"


def full_upgrade(host: FakeHost, system: I.System, baseline: dict, archive: Path, attestation: Path) -> list[dict]:
    reports = [I.stage_upgrade_stage(system, OLD, NEW, archive, attestation, baseline),
               I.stage_upgrade_select(system, OLD, NEW, baseline),
               I.stage_upgrade_units(system, OLD, NEW, baseline)]
    mark_reload_needed(host)
    reports.append(I.upgrade_status(system, OLD, NEW, baseline))
    host.daemon_reload()  # the owner's separate M-A4 command
    reports += [I.stage_upgrade_cli(system, OLD, NEW, baseline), I.stage_upgrade_retire_old(system, OLD, NEW, baseline)]
    return reports


@unittest.skipUnless(POSIX, "owner and mode semantics are POSIX")
class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self._stack = contextlib.ExitStack()
        self.directory = self._stack.enter_context(tempfile.TemporaryDirectory())
        self.out = self._stack.enter_context(tempfile.TemporaryDirectory())
        self.wheels = self._stack.enter_context(fake_wheels())
        self._stack.enter_context(accepted_current())
        self.host, self.system = old_host(self.directory)
        self.archive, self.attestation, _ = build_archive(Path(self.out), self.wheels)
        self.baseline = I.parse_baseline(baseline_file(self.out, self.system), OLD)

    def tearDown(self):
        self._stack.close()

    def current(self):
        return I.current_blob_observation(self.system)

    def test_accepted_old_baseline_is_recognised(self):
        self.assertEqual(I.status(self.system, "L2b.2", OLD)["result"], "PASS",
                         I.status(self.system, "L2b.2", OLD)["failures"])
        report = I.upgrade_status(self.system, OLD, NEW, self.baseline)
        self.assertEqual((report["state"], report["result"]), (I.EXISTING_ACCEPTED_OLD_RELEASE, "PASS"))
        observed = I.observe_baseline(self.system, OLD)
        self.assertTrue(observed["acceptedOldRelease"] and observed["acceptedCurrentSha256"])
        self.assertEqual(observed["hostKey"]["kind"], "file")  # stat only; the key is never read

    def test_full_upgrade_ends_at_the_unchanged_l2b2_contract_for_new(self):
        before = self.current()
        start = len(self.host.calls)  # the OLD host's own L1a..L2b.2 ladder created the signer account
        reports = full_upgrade(self.host, self.system, self.baseline, self.archive, self.attestation)
        self.assertEqual([r["state"] for r in reports],
                         [I.STAGED_NEW_RELEASE, I.SELECTED_NEW_RELEASE, I.UNITS_RELOADED, I.UNITS_UPDATED,
                          I.CLI_UPDATED, I.COMPLETE_NEW_RELEASE])
        for report in reports:
            self.assertEqual(report["failures"], [], report)
        self.assertEqual(reports[-1]["statusL2b2New"], "PASS")
        self.assertEqual(I.status(self.system, "L2b.2", NEW)["result"], "PASS")
        self.assertEqual(self.current(), before)  # CURRENT byte- and identity-identical, ctime included
        self.assertFalse((self.host.root / f"opt/lilith-authority-dev/releases/{OLD}").exists())
        for call in self.host.calls[start:]:
            name = Path(call[0]).name
            self.assertNotIn(name, ("systemd-creds", "lilith-authority-keygen-dev"))
            if name == "systemctl":
                self.assertEqual(call[1], "show")
            if name == "useradd":
                self.fail("the signer account is adopted, never recreated")
        for target in I.CLI_TARGETS.values():
            self.assertEqual(os.stat(self.host.root / target.lstrip("/")).st_mode & 0o777, 0o755)

    def test_every_stage_is_idempotent_or_refused(self):
        stage = lambda: I.stage_upgrade_stage(self.system, OLD, NEW, self.archive, self.attestation, self.baseline)
        self.assertEqual(stage()["mutation"], "STAGED")
        self.assertEqual(stage()["mutation"], "ALREADY_COMPLETE")   # staged release already complete
        with self.assertRaises(I.InstallError):
            I.stage_upgrade_units(self.system, OLD, NEW, self.baseline)  # out of order
        self.assertEqual(I.stage_upgrade_select(self.system, OLD, NEW, self.baseline)["mutation"], "SELECTED")
        self.assertEqual(I.stage_upgrade_select(self.system, OLD, NEW, self.baseline)["mutation"], "ALREADY_COMPLETE")
        with self.assertRaises(I.InstallError):
            I.stage_upgrade_stage(self.system, OLD, NEW, self.archive, self.attestation, self.baseline)
        self.assertEqual(I.stage_upgrade_units(self.system, OLD, NEW, self.baseline)["mutation"], "REPLACED")
        self.assertEqual(I.stage_upgrade_units(self.system, OLD, NEW, self.baseline)["mutation"], "ALREADY_COMPLETE")
        mark_reload_needed(self.host)
        with self.assertRaises(I.InstallError) as caught:
            I.stage_upgrade_cli(self.system, OLD, NEW, self.baseline)  # units new, reload pending
        self.assertIn(I.UNITS_UPDATED, caught.exception.reason)
        self.host.daemon_reload()
        self.assertEqual(I.stage_upgrade_cli(self.system, OLD, NEW, self.baseline)["mutation"], "REPLACED")
        self.assertEqual(I.stage_upgrade_cli(self.system, OLD, NEW, self.baseline)["mutation"], "ALREADY_COMPLETE")
        self.assertEqual(I.stage_upgrade_retire_old(self.system, OLD, NEW, self.baseline)["mutation"], "RETIRED")
        self.assertEqual(I.stage_upgrade_retire_old(self.system, OLD, NEW, self.baseline)["mutation"],
                         "ALREADY_COMPLETE")

    def test_valid_intermediate_states_classify_and_mixed_states_stop(self):
        I.stage_upgrade_stage(self.system, OLD, NEW, self.archive, self.attestation, self.baseline)
        root = self.host.root
        # selector old / units new -> INCONSISTENT
        service = root / I.SERVICE_UNIT.lstrip("/")
        saved = service.read_bytes()
        service.write_bytes((root / f"opt/lilith-authority-dev/releases/{NEW}/assets/lilith-authority-dev.service")
                            .read_bytes())
        self.assertEqual(I.upgrade_status(self.system, OLD, NEW, self.baseline)["state"], I.INCONSISTENT)
        service.write_bytes(saved)
        I.stage_upgrade_select(self.system, OLD, NEW, self.baseline)
        # new release selected, old CLI present -> the valid SELECTED stage
        self.assertEqual(I.upgrade_status(self.system, OLD, NEW, self.baseline)["state"], I.SELECTED_NEW_RELEASE)
        I.stage_upgrade_units(self.system, OLD, NEW, self.baseline)
        # units new / CLI old -> the valid UNITS stage
        self.assertEqual(I.upgrade_status(self.system, OLD, NEW, self.baseline)["state"], I.UNITS_RELOADED)
        # half the CLIs -> INCONSISTENT
        new_cli = root / "usr/local/sbin/lilith-authority-hold-dev"
        new_cli.write_bytes((root / f"opt/lilith-authority-dev/releases/{NEW}/cli/lilith-authority-hold-dev").read_bytes())
        os.chmod(new_cli, 0o755)
        self.assertEqual(I.upgrade_status(self.system, OLD, NEW, self.baseline)["state"], I.INCONSISTENT)
        new_cli.unlink()
        # an unknown extra release directory -> INCONSISTENT
        extra = root / f"opt/lilith-authority-dev/releases/{'1' * 40}"
        extra.mkdir()
        self.assertEqual(I.upgrade_status(self.system, OLD, NEW, self.baseline)["state"], I.INCONSISTENT)
        extra.rmdir()
        # an active or enabled unit -> INCONSISTENT
        self.host.units["lilith-authority-dev.socket"]["ActiveState"] = "active"
        self.assertEqual(I.upgrade_status(self.system, OLD, NEW, self.baseline)["state"], I.INCONSISTENT)
        with self.assertRaises(I.InstallError):
            I.stage_upgrade_cli(self.system, OLD, NEW, self.baseline)
        self.host.units["lilith-authority-dev.socket"]["ActiveState"] = "inactive"
        self.assertEqual(I.upgrade_status(self.system, OLD, NEW, self.baseline)["state"], I.UNITS_RELOADED)

    def test_the_baseline_precheck_fails_closed(self):
        root = self.host.root
        blob = root / "etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred"
        cases = []

        def expect(prepare, needle, undo):
            prepare()
            try:
                report = I.upgrade_status(self.system, OLD, NEW, self.baseline)
                self.assertTrue(any(needle in failure for failure in report["failures"]), (needle, report["failures"]))
                with self.assertRaises(I.InstallError):
                    I.stage_upgrade_stage(self.system, OLD, NEW, self.archive, self.attestation, self.baseline)
            finally:
                undo()
        expect(lambda: os.chmod(blob, 0o644), "PRESERVATION:CURRENT_MODE", lambda: os.chmod(blob, 0o600))
        # The chmod round trip itself moved CURRENT's ctime: the owner re-records the baseline, as on a host.
        self.baseline = I.parse_baseline(baseline_file(self.out, self.system), OLD)
        stray = root / "etc/credstore.encrypted/other.cred"
        expect(lambda: stray.write_bytes(b"x"), "CREDSTORE_NOT_EXACTLY_CURRENT", stray.unlink)
        witness = root / I.SUPERSEDED_WITNESS_CREDSTORE.lstrip("/")
        expect(lambda: witness.write_bytes(b"x"), "PRESERVATION:", witness.unlink)
        uid = self.host.users[I.SERVICE_USER].pw_uid
        expect(lambda: setattr(self.host.users[I.SERVICE_USER], "pw_uid", uid + 7), "PRESERVATION:SIGNER_ACCOUNT",
               lambda: setattr(self.host.users[I.SERVICE_USER], "pw_uid", uid))
        cases.append("custody root present")
        custody = root / "etc/lilith-authority-custody"
        custody.mkdir(mode=0o700)
        with self.assertRaises(I.InstallError) as caught:
            I.stage_upgrade_stage(self.system, OLD, NEW, self.archive, self.attestation, self.baseline)
        self.assertIn("UPGRADE_UNEXPECTED_PRESENT", caught.exception.reason)
        custody.rmdir()
        # CURRENT rewritten with identical bytes: the ctime/inode still differ -> STOP.
        data = blob.read_bytes()
        blob.unlink()
        blob.write_bytes(data)
        os.chmod(blob, 0o600)
        report = I.upgrade_status(self.system, OLD, NEW, self.baseline)
        self.assertTrue(any(f.startswith("PRESERVATION:CURRENT_") for f in report["failures"]), report["failures"])

    def test_baseline_document_is_closed_and_pins_the_accepted_values(self):
        for overrides, reason in (({"oldRelease": NEW}, "BASELINE_OLD_RELEASE_NOT_ACCEPTED"),
                                  ({"extra": 1}, "BASELINE_MALFORMED"),
                                  ({"signerAccount": {"uid": 1}}, "BASELINE_MALFORMED")):
            path = baseline_file(self.out, self.system, **overrides)
            with self.assertRaises(I.InstallError) as caught:
                I.parse_baseline(path, OLD)
            self.assertEqual(caught.exception.reason, reason)
        path = baseline_file(self.out, self.system)
        with self.assertRaises(I.InstallError) as caught:
            I.parse_baseline(path, NEW)
        self.assertEqual(caught.exception.reason, "BASELINE_OLD_RELEASE_NOT_ACCEPTED")
        value = json.loads(path.read_text(encoding="utf-8"))
        value["currentBlob"]["sha256"] = "0" * 64
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(I.InstallError) as caught:
            I.parse_baseline(path, OLD)
        self.assertEqual(caught.exception.reason, "BASELINE_CURRENT_SHA256_NOT_ACCEPTED")

    def test_staged_tree_is_verified_against_its_manifest(self):
        I.stage_upgrade_stage(self.system, OLD, NEW, self.archive, self.attestation, self.baseline)
        top = self.host.root / f"opt/lilith-authority-dev/releases/{NEW}"
        self.assertEqual(I.release_tree_failures(self.system, NEW), [])
        (top / "lilith_authority_dev/extra.py").write_bytes(b"x = 1\n")
        self.assertIn("TREE_EXTRA_FILE:lilith_authority_dev/extra.py", I.release_tree_failures(self.system, NEW))
        (top / "lilith_authority_dev/extra.py").unlink()
        core = top / "lilith_authority_dev/core.py"
        core.write_bytes(core.read_bytes() + b"# tampered\n")
        self.assertIn("TREE_FILE:lilith_authority_dev/core.py", I.release_tree_failures(self.system, NEW))
        with self.assertRaises(I.InstallError) as caught:
            I.stage_upgrade_select(self.system, OLD, NEW, self.baseline)
        self.assertIn("STAGED_TREE_INVALID", caught.exception.reason)

    def test_main_dispatch_and_refusals(self):
        path = baseline_file(self.out, self.system)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(I.main(["upgrade-status", OLD, NEW, str(path)], self.system), 0)
            self.assertEqual(I.main(["upgrade-select", OLD, NEW, str(path)], self.system), 2)
            self.assertEqual(I.main(["upgrade-stage", OLD, NEW, str(path)], self.system), 2)  # USAGE
            self.assertEqual(I.main(["upgrade-status", OLD, OLD, str(path)], self.system), 2)
        self.assertIn(I.EXISTING_ACCEPTED_OLD_RELEASE, out.getvalue())
        self.assertIn("REFUSED", err.getvalue())


@unittest.skipUnless(POSIX, "owner and mode semantics are POSIX")
class Pr1aContinuationTests(unittest.TestCase):
    """After the upgrade: custody, witness identity and units, skeleton (PR-1A)."""

    def test_pr1a_phases_on_the_new_release(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as out, fake_wheels() as wheels, \
                accepted_current():
            host, system = old_host(directory)
            archive, attestation, _ = build_archive(Path(out), wheels)
            baseline = I.parse_baseline(baseline_file(out, system), OLD)
            before = I.current_blob_observation(system)
            full_upgrade(host, system, baseline, archive, attestation)
            self.assertEqual(I.stage_custody(system, NEW)["result"], "PASS")
            report = I.stage_witness_account(system, NEW)
            self.assertEqual(report["result"], "PASS", report["failures"])
            witness, signer = host.users[I.WITNESS_USER], host.users[I.SERVICE_USER]
            self.assertNotEqual((witness.pw_uid, witness.pw_gid), (signer.pw_uid, signer.pw_gid))
            with self.assertRaises(I.InstallError):
                I.stage_witness_account(system, NEW)  # never corrects an existing identity
            self.assertEqual(I.stage_witness_units(system, NEW)["result"], "PASS")
            self.assertEqual(I.status(system, "P1A-8c", NEW)["result"], "FAIL")  # not yet reloaded
            host.daemon_reload()
            report = I.stage_skeleton(system, NEW)
            self.assertEqual(report["result"], "PASS", report["failures"])
            for directory_, mode in I.SKELETON_DIRS:
                self.assertEqual(os.stat(host.root / directory_.lstrip("/")).st_mode & 0o7777, mode, directory_)
            for leaf in (I.TRUST_DIR, I.REGISTRY_DIR, I.OWNER_INPUT_DIR, I.WITNESS_CREDENTIAL_ROOT, I.HOLD_STORE):
                self.assertEqual(os.listdir(host.root / leaf.lstrip("/")), [], leaf)  # structure only, no content
            self.assertEqual(I.current_blob_observation(system), before)
            names = {Path(call[0]).name for call in host.calls}
            self.assertLessEqual(names, {"useradd", "systemctl", "sudo", "python3", "python", "runuser"})
            self.assertEqual([c[-1] for c in host.calls if Path(c[0]).name == "useradd"],
                             [I.SERVICE_USER, I.WITNESS_USER])
            for unit in I.WITNESS_UNITS:
                self.assertIn(unit, report["observed"])

    def test_witness_account_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            host = FakeHost(directory)
            I.stage_accounts(host.system())
            host.run(["/usr/sbin/useradd", I.WITNESS_USER])
            I.verify_witness_account_contract(host.system())
            host.groups[I.SERVICE_GROUP].gr_mem.append(I.WITNESS_USER)
            with self.assertRaises(I.InstallError) as caught:
                I.verify_witness_account_contract(host.system())
            self.assertEqual(caught.exception.reason, "WITNESS_IN_SIGNER_GROUP")
            host.groups[I.SERVICE_GROUP].gr_mem.clear()
            host.users[I.WITNESS_USER].pw_uid = host.users[I.SERVICE_USER].pw_uid
            with self.assertRaises(I.InstallError) as caught:
                I.verify_witness_account_contract(host.system())
            self.assertEqual(caught.exception.reason, "ACCOUNT_UID_COLLISION")

    def test_witness_state_and_runtime_directories_are_optional_until_their_phase(self):
        at_l2b2 = I.expected_paths("L2b.2", NEW)
        for path in (I.WITNESS_STATE, I.WITNESS_RUNTIME, I.AUTHORITY_RUNTIME, I.AUTHORITY_LEDGER, I.HOLD_STORE,
                     I.WITNESS_BLOB, I.SUPERSEDED_WITNESS_CREDSTORE, *[p for p, _ in I.SKELETON_DIRS]):
            self.assertIsNone(at_l2b2[path], path)
        later = I.expected_paths("P1A-9", NEW)
        self.assertIsInstance(later[I.AUTHORITY_RUNTIME], I.RuntimeDirectory)
        self.assertIsInstance(later[I.WITNESS_RUNTIME], I.RuntimeDirectory)
        self.assertIsNone(later[I.WITNESS_STATE])
        final = I.expected_paths("P1B-11", NEW)
        self.assertEqual(final[I.WITNESS_STATE], ("dir", "wit", "svc", "2750"))
        self.assertEqual(final[I.AUTHORITY_LEDGER], ("file", "svc", "svc", "0600"))
        self.assertIsNone(final[I.SUPERSEDED_WITNESS_CREDSTORE])  # RR-36, at every phase

    def test_units_may_run_only_from_their_pr1b_phase_and_never_enabled(self):
        with tempfile.TemporaryDirectory() as directory:
            host = FakeHost(directory)
            for unit, earliest in (("lilith-recovery-witness.service", "P1B-9a"),
                                   ("lilith-authority-dev.service", "P1B-11")):
                host.units[unit]["ActiveState"] = "active"
                before = I.STAGES[I.STAGES.index(earliest) - 1]
                self.assertIn(f"UNIT_ACTIVE:{unit}", I.status(host.system(), before, NEW)["failures"])
                self.assertNotIn(f"UNIT_ACTIVE:{unit}", I.status(host.system(), earliest, NEW)["failures"])
                host.units[unit]["UnitFileState"] = "enabled"
                self.assertIn(f"UNIT_ENABLEABLE_OR_ENABLED:{unit}", I.status(host.system(), "P1B-11", NEW)["failures"])
                host.units[unit].update(ActiveState="inactive", UnitFileState="")

    def test_public_input_stages_are_write_once_and_shape_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            good = Path(directory) / "anchor.json"
            good.write_bytes(json.dumps({"environment": "dev", "schemaVersion": 1}, sort_keys=True,
                                        separators=(",", ":")).encode())
            self.assertEqual(I._canonical_document(good)[:1], b"{")
            for body in (b'{"environment": "dev"}', b'{"environment":"dev","x":1.5}', b'{"environment":"prod"}',
                         b"[1]", "{\"environment\":\"dév\"}".encode()):
                bad = Path(directory) / "bad.json"
                bad.write_bytes(body)
                with self.assertRaises(I.InstallError):
                    I._canonical_document(bad)
            link = Path(directory) / "link.json"
            os.symlink(good, link)
            with self.assertRaises(I.InstallError):
                I._canonical_document(link)

    def test_installer_never_starts_enables_reloads_or_generates(self):
        code = L2.code_only(L2.INSTALLER_SOURCE)
        for needle in ('"enable"', '"start"', '"restart"', '"daemon-reload"', "systemd-creds", "systemd-tmpfiles",
                       "Ed25519PrivateKey", '"--now"', "keygen-dev actor", "os.unlink(system.path(CREDENTIAL"):
            self.assertNotIn(needle, code, needle)
        self.assertNotIn("_write_new(system, system.path(CREDENTIAL", code)
        self.assertNotIn("chmod(system.path(CREDENTIAL", code)
        self.assertNotIn("rename(system.path(CREDENTIAL", code)


if __name__ == "__main__":
    unittest.main()
