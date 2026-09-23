"""Deterministic pre-install, Stage-I, and PROD broker lifecycle regressions."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from scripts import audit_core_api_production_read_only as prod
from scripts import verify_broker_dev_lifecycle as gate


def post_fixture() -> dict:
    manifest_files = {f"payload/{i:02d}": {"sha256": f"{i:064x}", "byteSize": i + 1}
                      for i in range(23)}
    return {
        "profile": gate.POST_STAGE_I,
        "host": gate.expected_host(),
        "accounts": {
            "broker": {"uid": 999, "gid": 987, "home": "/nonexistent", "shell": "/usr/sbin/nologin", "groups": [987]},
            "relay": {"uid": 997, "gid": 986, "home": "/nonexistent", "shell": "/usr/sbin/nologin", "groups": [986, 988]},
            "ipc": {"gid": 988, "members": ["lilith-memory-relay"]},
        },
        "groups": {"broker": 987, "relay": 986},
        "directories": {
            str(gate.ROOT): [0, 0, 0o755], str(gate.ROOT / "releases"): [0, 0, 0o755],
            str(gate.CONFIG): [0, 0, 0o755], str(gate.STATE): [999, 987, 0o700],
            str(gate.STATE / "owner-control"): [999, 987, 0o700],
            str(gate.STATE / "state"): [999, 987, 0o700],
        },
        "release": {
            "target": f"releases/{gate.RELEASE_SHA}", "manifestSha256": gate.MANIFEST_SHA,
            "candidateSha": gate.RELEASE_SHA, "deploymentEnvironment": "dev",
            "ownerSchemaFingerprint": gate.OWNER_SCHEMA, "evidenceSchemaFingerprint": gate.EVIDENCE_SCHEMA,
            "manifestFiles": manifest_files, "payloads": copy.deepcopy(manifest_files),
        },
        "files": {path: {"sha256": sha, "uid": uid, "gid": gid, "mode": mode}
                  for path, (sha, uid, gid, mode) in gate.FILE_CONTRACT.items()},
        "databases": {
            "owner": {
                "integrity": "ok", "foreignKeyViolations": 0, "fingerprint": gate.OWNER_SCHEMA,
                "version": 2, "mode": "B1B2_SYNTHETIC_DEV_V1", "counts": dict(gate.OWNER_COUNTS),
                "accessIdentity": ["owner.ravindu.v1", "user:synthetic-owner@example.invalid", "ACTIVE"],
                "credentialCount": 1,
            },
            "evidence": {
                "integrity": "ok", "foreignKeyViolations": 0, "fingerprint": gate.EVIDENCE_SCHEMA,
                "profile": "B1B2_SYNTHETIC_EVIDENCE_V1", "releaseSha": gate.RELEASE_SHA,
                "counts": dict(gate.EVIDENCE_COUNTS),
            },
        },
        "units": {
            gate.SERVICE: {"LoadState": "loaded", "ActiveState": "inactive", "SubState": "dead",
                           "MainPID": "0", "UnitFileState": "static", "NRestarts": "0",
                           "ExecMainStartTimestamp": ""},
            gate.SOCKET: {"LoadState": "loaded", "ActiveState": "inactive", "SubState": "dead",
                          "UnitFileState": "disabled"},
        },
        "absent": {path: True for path in gate.POST_ABSENT},
        "broker_processes": [],
        "api": {
            "ActiveState": "active", "NRestarts": "0", "MainPID": "86416",
            "ExecMainStartTimestamp": "Wed 2026-09-23 18:09:34 UTC",
            "health": {"status": "ok", "database": True},
            "custody": {
                str(gate.API_ROOT / "data/lilith-dev.db"): {"sha256": "a" * 64},
                str(gate.API_ROOT / "data/canonical-runtime.json"): {"sha256": "b" * 64},
            },
        },
    }


def pre_fixture() -> dict:
    return {
        "profile": gate.PRE_B1B2B, "host": gate.expected_host(),
        "accounts": {"broker": None, "relay": None, "ipc": None},
        "groups": {"broker": None, "relay": None},
        "persistent_paths": {path: False for path in gate.pre_absent_paths()},
        "units": {name: {"LoadState": "not-found", "ActiveState": "inactive"}
                  for name in (gate.SERVICE, gate.SOCKET)},
        "broker_processes": [],
    }


def prod_fixture() -> dict:
    return {
        "accounts": {name: False for name in ("lilith-memory-broker", "lilith-memory-relay")},
        "groups": {name: False for name in ("lilith-memory-broker", "lilith-memory-relay", "lilith-memory-ipc")},
        "paths": {str(path): False for path in prod.BROKER_PATHS},
        "units": {name: {"LoadState": "not-found", "ActiveState": "inactive"}
                  for name in (gate.SERVICE, gate.SOCKET)},
        "processes": [],
    }


class LifecyclePolicyTests(unittest.TestCase):
    def test_pre_install_absence_passes(self):
        gate.validate_pre(pre_fixture())

    def test_pre_install_footprint_and_accounts_fail(self):
        for mutation in (
            lambda s: s["persistent_paths"].__setitem__(str(gate.STATE), True),
            lambda s: s["accounts"].__setitem__("broker", {"uid": 999}),
            lambda s: s["groups"].__setitem__("relay", 986),
            lambda s: s["units"][gate.SOCKET].__setitem__("LoadState", "loaded"),
            lambda s: s["broker_processes"].append(9),
        ):
            with self.subTest(mutation=mutation):
                snapshot = pre_fixture()
                mutation(snapshot)
                with self.assertRaises(gate.LifecycleError):
                    gate.validate_pre(snapshot)

    def test_exact_post_stage_i_passes(self):
        gate.validate_post(post_fixture())

    def test_post_stage_i_wrong_identity_or_release_fails(self):
        mutations = (
            lambda s: s["accounts"].__setitem__("broker", None),
            lambda s: s["groups"].__setitem__("broker", 998),
            lambda s: s["accounts"]["broker"].__setitem__("uid", 998),
            lambda s: s["accounts"]["relay"].__setitem__("gid", 988),
            lambda s: s["accounts"]["ipc"].__setitem__("members", []),
            lambda s: s["release"].__setitem__("manifestSha256", "0" * 64),
            lambda s: s["release"]["payloads"]["payload/00"].__setitem__("sha256", "f" * 64),
        )
        self._reject_all(mutations)

    def test_post_stage_i_file_and_db_drift_fails(self):
        mutations = (
            lambda s: s["files"][str(gate.CONFIG / "dev.json")].__setitem__("sha256", "0" * 64),
            lambda s: s["files"][str(gate.CONFIG / "identities.json")].__setitem__("sha256", "0" * 64),
            lambda s: s["files"][str(gate.CONFIG / "b1b2b-authorization.used.json")].__setitem__("sha256", "0" * 64),
            lambda s: s["files"]["/etc/systemd/system/lilith-memory-broker.service"].__setitem__("sha256", "0" * 64),
            lambda s: s["files"][str(gate.OWNER_DB)].__setitem__("mode", 0o644),
            lambda s: s["databases"]["owner"].__setitem__("fingerprint", "0" * 64),
            lambda s: s["databases"]["evidence"].__setitem__("fingerprint", "0" * 64),
            lambda s: s["databases"]["owner"]["counts"].__setitem__("owner_proof_challenge_v1", 1),
            lambda s: s["databases"]["owner"]["counts"].__setitem__("owner_request_v1", 1),
            lambda s: s["databases"]["owner"]["counts"].__setitem__("synthetic_claim_v1", 1),
            lambda s: s["databases"]["evidence"]["counts"].__setitem__("synthetic_evidence_v1", 1),
            lambda s: s["databases"]["owner"].__setitem__("credentialCount", 2),
            lambda s: s["databases"]["owner"].__setitem__("accessIdentity", ["live-owner", "real", "ACTIVE"]),
        )
        self._reject_all(mutations)

    def test_post_stage_i_activation_and_markers_fail(self):
        mutations = (
            lambda s: s["units"][gate.SERVICE].__setitem__("ActiveState", "active"),
            lambda s: s["units"][gate.SERVICE].__setitem__("MainPID", "42"),
            lambda s: s["units"][gate.SOCKET].__setitem__("ActiveState", "active"),
            lambda s: s["units"][gate.SOCKET].__setitem__("UnitFileState", "enabled"),
            lambda s: s["absent"].__setitem__(str(gate.RUNTIME), False),
            lambda s: s["absent"].__setitem__(str(gate.RUNTIME / "owner.sock"), False),
            lambda s: s["absent"].__setitem__(str(gate.CONFIG / "b1b2b-stage2-authorization.json"), False),
            lambda s: s["absent"].__setitem__(str(gate.CONFIG / "b1b2b-stage2-authorization.used.json"), False),
            lambda s: s["absent"].__setitem__(str(gate.CONFIG / "b1b2b-authorization.json"), False),
            lambda s: s["broker_processes"].append(42),
        )
        self._reject_all(mutations)

    def test_unaccepted_stage_ii_profile_cannot_be_selected(self):
        self.assertEqual(gate.TRUSTED_DEV_PROFILE, gate.POST_STAGE_I)
        snapshot = post_fixture()
        snapshot["profile"] = gate.POST_STAGE_II
        with self.assertRaises(gate.LifecycleError):
            gate.validate_post(snapshot)

    def test_runner_and_workflow_use_trusted_source_and_compare_snapshots(self):
        root = Path(__file__).resolve().parent.parent
        runner = (root / "scripts/run_memory_broker_dev_validation.sh").read_text(encoding="utf-8")
        workflow = (root / ".github/workflows/deploy-dev.yml").read_text(encoding="utf-8")
        self.assertIn('test "$#" -eq 6', runner)
        self.assertIn('BEFORE_LIFECYCLE="$(sudo -n /usr/bin/python3 -B "$LIFECYCLE" snapshot)"', runner)
        self.assertIn('AFTER_LIFECYCLE="$(sudo -n /usr/bin/python3 -B "$LIFECYCLE" snapshot)"', runner)
        self.assertIn('test "$BEFORE_LIFECYCLE" = "$AFTER_LIFECYCLE"', runner)
        self.assertIn('scripts/verify_broker_dev_lifecycle.py "${GCP_INSTANCE}:${REMOTE_BROKER_DIR}/lifecycle.py"', workflow)
        self.assertNotIn('candidate/scripts/verify_broker_dev_lifecycle.py', workflow)
        self.assertNotIn('systemctl start', runner)

    def _reject_all(self, mutations):
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                snapshot = post_fixture()
                mutation(snapshot)
                with self.assertRaises(gate.LifecycleError):
                    gate.validate_post(snapshot)


class ProductionAbsenceTests(unittest.TestCase):
    def test_production_broker_absent_passes(self):
        prod.validate_broker_absence(prod_fixture())

    def test_production_footprint_fails(self):
        mutations = (
            lambda s: s["accounts"].__setitem__("lilith-memory-broker", True),
            lambda s: s["groups"].__setitem__("lilith-memory-ipc", True),
            lambda s: s["paths"].__setitem__(str(gate.ROOT), True),
            lambda s: s["units"][gate.SERVICE].__setitem__("LoadState", "loaded"),
            lambda s: s["processes"].append("123 broker"),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                snapshot = prod_fixture()
                mutation(snapshot)
                with self.assertRaises(prod.AuditError):
                    prod.validate_broker_absence(snapshot)


if __name__ == "__main__":
    unittest.main()
