"""Isolated source contracts; never run systemctl or contact DEV."""

from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import memory_broker_stage2_control as stage2
from scripts import memory_broker_stage3_guard_worker as worker
from scripts import memory_broker_stage3_liveness as guard
from scripts import memory_broker_stage3_transition as transition


class Stage3LivenessContracts(unittest.TestCase):
    def test_worker_source_and_closed_synthetic_identity_are_pinned(self):
        raw = Path(worker.__file__).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), guard.GUARD_WORKER_SHA)
        with patch.object(guard, "controller_identity",
                          return_value=(123, "a" * 36, 456)):
            value = guard.config_value("b" * 32)
        worker.validate_config(value)
        self.assertEqual(value["authorityMode"], "SYNTHETIC_ONLY")
        self.assertEqual(value["canonicalCapability"], "DISABLED")
        self.assertEqual(value["candidateRelease"], stage2.STAGE3_RELEASE)
        for field, invalid in (("candidateRelease", stage2.RELEASE),
                               ("authorityMode", "PRODUCTION_GOVERNED"),
                               ("controllerStartTicks", 0),
                               ("authorizationId", "c" * 31)):
            changed = dict(value, **{field: invalid})
            with self.subTest(field=field), self.assertRaisesRegex(
                    worker.GuardError, "GUARD_CLOSED_CONFIG"):
                worker.validate_config(changed)

    def test_unit_dependencies_cover_service_and_socket_without_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = guard.Paths(systemd=Path(directory) / "systemd",
                                drop_root=Path(directory) / "etc",
                                runtime=Path(directory) / "runtime",
                                vault=Path(directory) / "vault")
            unit = guard.guard_unit_bytes(paths).decode()
            self.assertIn("Type=notify\nNotifyAccess=main", unit)
            self.assertIn("Restart=no", unit)
            self.assertNotIn("ExecStart=/usr/bin/systemctl", unit)
            self.assertIn("ReadWritePaths=/var/lib/.lilith-memory-broker-stage3-a2", unit)
            self.assertEqual(guard.DROPIN.count("BindsTo="), 1)
            self.assertIn("BindsTo=" + guard.GUARD, guard.DROPIN)
            self.assertIn("After=" + guard.GUARD, guard.DROPIN)
            self.assertIn("AssertPathExists=" + guard.Paths().ready.as_posix(),
                          guard.DROPIN)
            self.assertEqual(guard.ORIGINAL_UNITS[stage2.SERVICE],
                             Path("/etc/systemd/system/lilith-memory-broker.service"))
            self.assertEqual(guard.ORIGINAL_UNITS[stage2.SOCKET],
                             Path("/etc/systemd/system/lilith-memory-broker.socket"))
            self.assertEqual(paths.drop(stage2.SERVICE).name, guard.DROP_NAME)
            self.assertEqual(paths.drop(stage2.SOCKET).name, guard.DROP_NAME)
            with self.assertRaisesRegex(guard.LivenessError, "GUARD_UNIT_SCOPE"):
                paths.drop("unrelated.service")

    def test_observed_socket_dependency_must_match_service_dependency(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = guard.Paths(systemd=Path(directory) / "systemd",
                                drop_root=Path(directory) / "etc")
            for unit in (stage2.SERVICE, stage2.SOCKET):
                paths.drop_directory(unit).mkdir(parents=True)
                paths.drop(unit).write_bytes(guard.DROPIN.encode())

            def observed(unit):
                return {"BindsTo": guard.GUARD if unit == stage2.SERVICE else "",
                        "After": guard.GUARD,
                        "DropInPaths": paths.drop(unit).as_posix()}

            with patch.object(guard, "unit_state", side_effect=observed), \
                 patch.object(guard, "regular",
                              side_effect=lambda path, **_: path.read_bytes()), \
                 self.assertRaisesRegex(guard.LivenessError,
                                        "GUARD_DEPENDENCY_DRIFT"):
                guard.require_dependencies(paths, present=True)

    def test_local_install_and_release_order_preserve_one_shot_files(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            paths = guard.Paths(systemd=base / "systemd", drop_root=base / "etc",
                                runtime=base / "runtime",
                                vault=base / "vault")
            paths.systemd.mkdir()
            paths.drop_root.mkdir()
            paths.vault.mkdir()
            commands = []

            def record(*args):
                if args == ("/usr/bin/systemctl", "start", guard.GUARD):
                    self.assertFalse(paths.ready.exists())
                commands.append(args)

            with patch.object(stage2, "assert_host"), \
                 patch.object(guard, "require_inert"), \
                 patch.object(guard, "require_dependencies"), \
                 patch.object(guard, "source_bytes", return_value=b"reviewed-worker"), \
                 patch.object(guard, "original_unit_hashes",
                              return_value={"service": "unchanged", "socket": "unchanged"}), \
                 patch.object(guard, "config_value", return_value={"test": "fixed"}), \
                 patch.object(guard, "regular",
                              side_effect=lambda path, **_: path.read_bytes()), \
                 patch.object(guard, "verify_guard",
                              return_value={"guardPid": 7, "claimSha256": "c" * 64}), \
                 patch.object(guard, "verify", return_value={"guardPid": 7}), \
                 patch.object(stage2, "run_fixed", side_effect=record), \
                 patch.object(stage2, "show", return_value={"ActiveState": "inactive"}):
                guard.prepare_inert(paths)
                result = guard.install(paths, "a" * 32)
                self.assertEqual(result["guardPid"], 7)
                self.assertEqual(paths.worker.read_bytes(), b"reviewed-worker")
                self.assertEqual(paths.drop(stage2.SERVICE).read_text(), guard.DROPIN)
                self.assertEqual(paths.drop(stage2.SOCKET).read_text(), guard.DROPIN)
                self.assertLess(commands.index(("/usr/bin/systemctl", "daemon-reload")),
                                commands.index(("/usr/bin/systemctl", "start", guard.GUARD)))
                self.assertTrue(paths.ready.is_file())
                guard.close_gate(paths)
                self.assertFalse(paths.ready.exists())
                commands.clear()
                guard.release(paths, "a" * 32)
            self.assertFalse(paths.drop(stage2.SERVICE).exists())
            self.assertFalse(paths.drop(stage2.SOCKET).exists())
            self.assertTrue(paths.guard_unit.exists())  # Retained, not reusable.
            self.assertTrue(paths.worker.exists())
            self.assertLess(commands.index(("/usr/bin/systemctl", "daemon-reload")),
                            commands.index(("/usr/bin/systemctl", "stop", guard.GUARD)))
            self.assertFalse(any("mask" in call or "unmask" in call
                                 for call in commands))

    def test_phase_journal_requires_guard_before_candidate_start(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            journal = transition.Journal(parent / "vault")
            journal.create({"stateDevice": parent.stat().st_dev})
            for phase in ("QUIESCED", "ACCEPTED_VAULTED", "FORK_READY",
                          "BINDINGS_SWITCHED"):
                journal.append(phase, {})
            with self.assertRaisesRegex(transition.TransitionError,
                                        "STAGE3_JOURNAL_ILLEGAL_TRANSITION"):
                journal.append("CANDIDATE_ACTIVE", {})
            journal.append("LIVENESS_BOUND", {"guardPid": 7})
            journal.append("CANDIDATE_ACTIVE", {"invocationId": "synthetic"})
            self.assertEqual(journal.last()[0], "CANDIDATE_ACTIVE")

    def test_activation_closes_both_paths_before_candidate_binding_change(self):
        source = Path(transition.__file__).read_text(encoding="utf-8")
        activate = source.split("    def activate(self) -> dict:", 1)[1].split(
            "    def seal_evidence", 1)[0]
        self.assertLess(activate.index("liveness.prepare_inert(self.guard)"),
                        activate.index("exclusive(p.vault / \"accepted-dev.json\""))
        self.assertLess(activate.index("liveness.prepare_inert(self.guard)"),
                        activate.index("replace_selector(p.current"))
        self.assertLess(activate.index("liveness.install(self.guard"),
                        activate.index("\"start\", control.SOCKET"))


if __name__ == "__main__":
    unittest.main()
