"""Deterministic pre-install, Stage-I, accepted Stage-II, and PROD regressions."""

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


def failed_fixture() -> dict:
    snapshot = post_fixture()
    snapshot["profile"] = gate.POST_STAGE_II_FAILED_INERT_V1
    snapshot["files"] = {path: {"sha256": sha, "uid": uid, "gid": gid, "mode": mode}
                         for path, (sha, uid, gid, mode) in gate.FAILED_FILES.items()}
    snapshot["absent"] = {path: True for path in gate.FAILED_ABSENT}
    snapshot["runtimeDirectory"] = {"uid": 0, "gid": 988, "mode": 0o710, "children": []}
    snapshot["broker_uid_processes"] = []
    snapshot["usedAuthorization"] = {
        "sha256": gate.FAILED_USED_MARKER_SHA,
        "authorizationId": gate.FAILED_AUTHORIZATION_ID,
        "schemaVersion": 2, "stage": "B1B2B_II / ACTIVATE_AND_ISOLATION_TEST",
        "authorityMode": "SYNTHETIC_ONLY", "canonicalCapability": "DISABLED",
        "releaseSha": gate.RELEASE_SHA, "ownerActor": "rpahasara",
        "apiBaselineDigest": "0fbed57b7746be3051e3de623990c6402daaa1f88197e614d60499419e1cdbd5",
    }
    sidecars = {
        "-wal": {"sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                 "uid": 999, "gid": 987, "mode": 0o600, "size": 0},
        "-shm": {"sha256": "fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb",
                 "uid": 999, "gid": 987, "mode": 0o600, "size": 32768},
    }
    owner = snapshot["databases"]["owner"]
    evidence = snapshot["databases"]["evidence"]
    owner["counts"] = dict(gate.FAILED_OWNER_COUNTS)
    owner["sidecars"] = copy.deepcopy(sidecars)
    owner["challengeStates"] = dict(gate.FAILED_CHALLENGES)
    owner["requestDigests"] = dict(gate.FAILED_REQUESTS)
    owner["consumedCredential"] = [gate.FAILED_CONSUMED_CHALLENGE,
                                   "ocred.synthetic", "2026-09-23T21:54:26Z"]
    owner["claims"] = [[gate.FAILED_CONSUMED_CHALLENGE, gate.FAILED_REQUEST_DIGEST,
                        gate.FAILED_ACTION_DIGEST, "ocred.synthetic",
                        "SYNTHETIC_EVIDENCE_COMMITTED", gate.FAILED_EVIDENCE_ID]]
    evidence["counts"] = dict(gate.FAILED_EVIDENCE_COUNTS)
    evidence["sidecars"] = copy.deepcopy(sidecars)
    evidence["evidenceRows"] = [[gate.FAILED_CONSUMED_CHALLENGE, gate.FAILED_EVIDENCE_ID,
                                 gate.FAILED_REQUEST_DIGEST, gate.FAILED_ACTION_DIGEST,
                                 "owner.ravindu.v1", "ocred.synthetic",
                                 "fixture.b1b1.synthetic-codename.v1", "SYNTHETIC_COMMITTED"]]
    snapshot["historicalBaseline"] = gate.historical_baseline(
        owner, evidence, snapshot["usedAuthorization"])
    snapshot["api"]["custody"][str(gate.API_ROOT / "data/lilith-dev.db")]["sha256"] = \
        "e4080d47ac782dc5578c4537b8aab277e73b27546e704ee2fff6fda506f67e6c"
    snapshot["api"]["custody"][str(gate.API_ROOT / "data/canonical-runtime.json")]["sha256"] = \
        "65ac5077486cfe25665fc8f5815661b1653878182492a0309ec974e9394c08e7"
    return snapshot


def accepted_fixture() -> dict:
    snapshot = failed_fixture()
    snapshot["profile"] = gate.POST_STAGE_II_ACCEPTED_V1
    snapshot["files"] = {path: {"sha256": sha, "uid": uid, "gid": gid, "mode": mode}
                         for path, (sha, uid, gid, mode) in gate.ACCEPTED_FILES.items()}
    snapshot["absent"] = {path: True for path in gate.ACCEPTED_ABSENT}
    snapshot["runtimeDirectory"]["children"] = ["owner.sock"]
    snapshot["ownerSocket"] = {"uid": 999, "gid": 988, "mode": 0o660,
                               "type": "socket", "listening": True}
    snapshot["usedAuthorizations"] = {
        "attempt1": copy.deepcopy(snapshot["usedAuthorization"]),
        "retry2": {
            "sha256": gate.ACCEPTED_RETRY_USED_SHA,
            "authorizationId": gate.ACCEPTED_RETRY_AUTHORIZATION_ID,
            "schemaVersion": 2, "stage": "B1B2B_II / ACTIVATE_AND_ISOLATION_TEST",
            "releaseSha": gate.RELEASE_SHA, "ownerActor": "rpahasara",
            "apiBaselineDigest": "3d039d4b1bf3eb1483f9e885a9a953f41883b56f2fe08d107d4ea6c2c16d71e4",
            "consumedAt": "2026-09-24T06:51:21.170362Z",
        },
    }
    snapshot["databases"]["owner"]["counts"] = dict(gate.ACCEPTED_OWNER_COUNTS)
    snapshot["databases"]["evidence"]["counts"] = dict(gate.ACCEPTED_EVIDENCE_COUNTS)
    snapshot["databases"]["owner"]["rowHashes"] = copy.deepcopy(gate.ACCEPTED_ROW_HASHES["owner"])
    snapshot["databases"]["evidence"]["rowHashes"] = copy.deepcopy(gate.ACCEPTED_ROW_HASHES["evidence"])
    snapshot["databases"]["owner"]["challengeStates"] = copy.deepcopy(gate.ACCEPTED_CHALLENGE_STATES)
    snapshot["databases"]["owner"]["requestDigests"] = copy.deepcopy(gate.ACCEPTED_REQUEST_DIGESTS)
    snapshot["databases"]["owner"]["claims"] = copy.deepcopy(gate.ACCEPTED_CLAIMS)
    snapshot["databases"]["evidence"]["evidenceRows"] = copy.deepcopy(gate.ACCEPTED_EVIDENCE_ROWS)
    snapshot["units"][gate.SERVICE] = {
        "LoadState": "loaded", "ActiveState": "active", "SubState": "running",
        "MainPID": "96650", "UnitFileState": "static", "NRestarts": "0",
        "ExecMainStartTimestamp": gate.ACCEPTED_SERVICE_STARTED,
        "InvocationID": gate.ACCEPTED_SERVICE_INVOCATION,
        "FragmentPath": "/etc/systemd/system/lilith-memory-broker.service", "DropInPaths": "",
    }
    snapshot["units"][gate.SOCKET] = {
        "LoadState": "loaded", "ActiveState": "active", "SubState": "running",
        "UnitFileState": "disabled",
        "FragmentPath": "/etc/systemd/system/lilith-memory-broker.socket", "DropInPaths": "",
    }
    snapshot["broker_processes"] = [96650]
    snapshot["broker_uid_processes"] = [96650]
    snapshot["brokerProcess"] = {
        "pid": 96650, "uid": [999] * 4, "gid": [987] * 4,
        "groups": [987], "ppid": 1,
        "cmdline": "/opt/lilith-memory-broker/current/venv/bin/python -B -m lilith_memory_broker.server",
    }
    snapshot["runtimeIncarnations"] = {
        "broker": {"pid": 96650, "bootId": gate.ACCEPTED_BROKER_BOOT_ID,
                   "startTicks": gate.ACCEPTED_BROKER_START_TICKS},
    }
    snapshot["api"]["custody"][str(gate.API_ROOT / "data/lilith-dev.db")].update(
        {"uid": 1001, "gid": 1002, "mode": 0o644})
    snapshot["api"]["custody"][str(gate.API_ROOT / "data/canonical-runtime.json")].update(
        {"uid": 1001, "gid": 1002, "mode": 0o600})
    snapshot["stage2AcceptedBaseline"] = gate.stage2_accepted_baseline(snapshot)
    return snapshot


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
        self.assertEqual(gate.TRUSTED_DEV_PROFILE, gate.POST_STAGE_II_ACCEPTED_V1)
        snapshot = post_fixture()
        snapshot["profile"] = gate.POST_STAGE_II
        with self.assertRaises(gate.LifecycleError):
            gate.validate_post(snapshot)

    def test_failed_inert_exact_history_passes_and_pristine_stays_strict(self):
        gate.validate_post(post_fixture())
        snapshot = failed_fixture()
        gate.validate_failed_inert(snapshot)
        with self.assertRaises(gate.LifecycleError):
            gate.validate(snapshot)
        with self.assertRaises(gate.LifecycleError):
            gate.validate_post(snapshot)
        snapshot["profile"] = gate.POST_STAGE_I
        with self.assertRaises(gate.LifecycleError):
            gate.validate_post(snapshot)
        self.assertEqual(snapshot["historicalBaseline"]["schemaVersion"], 1)
        self.assertEqual(snapshot["historicalBaseline"]["authorizationId"],
                         gate.FAILED_AUTHORIZATION_ID)
        self.assertEqual(snapshot["historicalBaseline"]["challengeStates"],
                         gate.FAILED_CHALLENGES)

    def test_failed_inert_unknown_history_and_reused_authorization_fail(self):
        mutations = (
            lambda s: s["databases"]["evidence"]["evidenceRows"][0].__setitem__(1, "se.unknown"),
            lambda s: s["databases"]["owner"]["challengeStates"].__setitem__("och.unknown", "CANCELLED"),
            lambda s: s["databases"]["owner"]["requestDigests"].__setitem__("och.unknown", "0" * 64),
            lambda s: s["databases"]["owner"]["claims"].append(["och.unknown"]),
            lambda s: s["databases"]["owner"]["challengeStates"].__setitem__(
                gate.FAILED_EXPIRED_CHALLENGE, "CANCELLED"),
            lambda s: s.__setitem__("usedAuthorization", {}),
            lambda s: s["usedAuthorization"].__setitem__("authorizationId", "new-id"),
            lambda s: s["absent"].__setitem__(str(gate.CONFIG / "b1b2b-stage2-authorization.json"), False),
            lambda s: s["usedAuthorization"].__setitem__("sha256", "0" * 64),
        )
        self._reject_failed(mutations)

    def test_failed_inert_runtime_and_integrity_fail_closed(self):
        mutations = (
            lambda s: s["units"][gate.SERVICE].__setitem__("ActiveState", "active"),
            lambda s: s["units"][gate.SERVICE].__setitem__("MainPID", "42"),
            lambda s: s["units"][gate.SOCKET].__setitem__("ActiveState", "active"),
            lambda s: s["units"][gate.SOCKET].__setitem__("UnitFileState", "enabled"),
            lambda s: s["broker_uid_processes"].append(42),
            lambda s: s["absent"].__setitem__(str(gate.RUNTIME / "owner.sock"), False),
            lambda s: s["runtimeDirectory"]["children"].append("unexpected"),
            lambda s: s["databases"]["owner"].__setitem__("integrity", "corrupt"),
            lambda s: s["databases"]["owner"].__setitem__("foreignKeyViolations", 1),
            lambda s: s["databases"]["owner"].__setitem__("fingerprint", "0" * 64),
            lambda s: s["databases"]["evidence"].__setitem__("fingerprint", "0" * 64),
            lambda s: s["databases"]["owner"]["sidecars"]["-wal"].__setitem__("mode", 0o644),
            lambda s: s["files"][str(gate.OWNER_DB)].__setitem__("mode", 0o644),
            lambda s: s["files"][str(gate.OWNER_DB)].__setitem__("sha256", "0" * 64),
            lambda s: s["files"][str(gate.EVIDENCE_DB)].__setitem__("sha256", "0" * 64),
            lambda s: s["databases"]["owner"].__setitem__("credentialCount", 2),
            lambda s: s["databases"]["evidence"]["counts"].__setitem__("actor_evidence", 1),
            lambda s: s["api"]["custody"][str(gate.API_ROOT / "data/canonical-runtime.json")].__setitem__("sha256", "0" * 64),
        )
        self._reject_failed(mutations)

    def test_accepted_stage_ii_exact_and_separate_from_prior_lifecycles(self):
        accepted = accepted_fixture()
        gate.validate_accepted(accepted)
        gate.validate(accepted)
        self.assertEqual(accepted["stage2AcceptedBaseline"]["schema"], "Stage2AcceptedBaselineV1")
        self.assertEqual(accepted["stage2AcceptedBaseline"]["acceptedStage2RunId"], "35965971283")
        self.assertEqual(accepted["stage2AcceptedBaseline"]["installedBrokerReleaseSha"], gate.RELEASE_SHA)
        self.assertEqual(
            accepted["stage2AcceptedBaseline"]["stage2AcceptedBaselineDigest"],
            "abc33ebf8d43e8805f43ff11e663a4757bf558d9b62eda9669dabecbb7c9839a")
        with self.assertRaises(gate.LifecycleError):
            gate.validate_failed_inert(accepted)
        with self.assertRaises(gate.LifecycleError):
            gate.validate_accepted(post_fixture())
        with self.assertRaises(gate.LifecycleError):
            gate.validate_accepted(failed_fixture())

    def test_accepted_history_hashes_and_authority_fail_closed(self):
        mutations = (
            lambda s: s["databases"]["evidence"]["rowHashes"]["synthetic_evidence_v1"].pop(
                gate.FAILED_CONSUMED_CHALLENGE),
            lambda s: s["databases"]["evidence"]["rowHashes"]["synthetic_evidence_v1"].pop(
                gate.ACCEPTED_RETRY_CHALLENGE),
            lambda s: s["databases"]["evidence"]["rowHashes"]["synthetic_evidence_v1"].__setitem__(
                gate.ACCEPTED_RETRY_CHALLENGE, "0" * 64),
            lambda s: s["databases"]["evidence"]["rowHashes"]["synthetic_evidence_v1"].__setitem__(
                "och.third", "0" * 64),
            lambda s: s["databases"]["owner"]["rowHashes"]["owner_proof_challenge_v1"].__setitem__(
                gate.ACCEPTED_RETRY_CHALLENGE, "0" * 64),
            lambda s: s["databases"]["owner"]["rowHashes"]["owner_request_v1"].__setitem__(
                gate.ACCEPTED_RETRY_CHALLENGE, "0" * 64),
            lambda s: s["databases"]["owner"]["rowHashes"]["synthetic_claim_v1"].__setitem__(
                gate.ACCEPTED_RETRY_CHALLENGE, "0" * 64),
            lambda s: s["databases"]["owner"]["challengeStates"].__setitem__(
                gate.ACCEPTED_RETRY_CHALLENGE, "CANCELLED"),
            lambda s: s["databases"]["owner"]["requestDigests"].__setitem__(
                gate.ACCEPTED_RETRY_CHALLENGE, "0" * 64),
            lambda s: s["databases"]["owner"]["claims"][0].__setitem__(5, "se.wrong"),
            lambda s: s["databases"]["evidence"]["evidenceRows"][1].__setitem__(1, "se.wrong"),
            lambda s: s["usedAuthorizations"].__setitem__("attempt1", {}),
            lambda s: s["usedAuthorizations"].__setitem__("retry2", {}),
            lambda s: s["usedAuthorizations"]["retry2"].__setitem__("sha256", "0" * 64),
            lambda s: s["absent"].__setitem__(
                str(gate.CONFIG / "b1b2b-stage2-retry2-authorization.json"), False),
            lambda s: s["absent"].__setitem__(
                str(gate.CONFIG / "b1b2b-stage2-retry2-authorization.used.json.pending"), False),
            lambda s: s["databases"]["owner"].__setitem__("credentialCount", 2),
            lambda s: s["databases"]["owner"]["rowHashes"]["owner_credential_v1"].__setitem__(
                "ocred.real", "0" * 64),
            lambda s: s["databases"]["evidence"]["counts"].__setitem__("actor_evidence", 1),
            lambda s: s["api"]["custody"][str(gate.API_ROOT / "data/canonical-runtime.json")].__setitem__(
                "sha256", "0" * 64),
        )
        self._reject_accepted(mutations)

    def test_accepted_runtime_integrity_release_and_api_fail_closed(self):
        mutations = (
            lambda s: s["databases"]["owner"].__setitem__("fingerprint", "0" * 64),
            lambda s: s["databases"]["evidence"].__setitem__("fingerprint", "0" * 64),
            lambda s: s["databases"]["owner"].__setitem__("integrity", "corrupt"),
            lambda s: s["databases"]["evidence"].__setitem__("foreignKeyViolations", 1),
            lambda s: s["databases"]["owner"]["sidecars"]["-wal"].__setitem__("mode", 0o644),
            lambda s: s["files"][str(gate.OWNER_DB)].__setitem__("mode", 0o644),
            lambda s: s["accounts"]["broker"].__setitem__("uid", 998),
            lambda s: s["broker_uid_processes"].append(12345),
            lambda s: s["brokerProcess"].__setitem__("groups", [987, 988]),
            lambda s: s["units"][gate.SOCKET].__setitem__("ActiveState", "inactive"),
            lambda s: s["units"][gate.SOCKET].__setitem__("UnitFileState", "enabled"),
            lambda s: s["ownerSocket"].__setitem__("listening", False),
            lambda s: s["ownerSocket"].__setitem__("mode", 0o666),
            lambda s: s["runtimeDirectory"]["children"].clear(),
            lambda s: s["release"].__setitem__("candidateSha", "0" * 40),
            lambda s: s["units"][gate.SERVICE].__setitem__("InvocationID", "ungoverned"),
            lambda s: s["api"]["health"].__setitem__("status", "down"),
            lambda s: s["files"][str(gate.API_ROOT / "current/app.py")].__setitem__(
                "sha256", "0" * 64),
        )
        self._reject_accepted(mutations)

    def test_accepted_broker_incarnation_is_pinned_but_not_durable_identity(self):
        snapshot = accepted_fixture()
        original_digest = snapshot["stage2AcceptedBaseline"]["stage2AcceptedBaselineDigest"]
        snapshot["units"][gate.SERVICE]["MainPID"] = "96651"
        snapshot["broker_processes"] = [96651]
        snapshot["broker_uid_processes"] = [96651]
        snapshot["brokerProcess"]["pid"] = 96651
        with self.assertRaises(gate.LifecycleError):
            gate.validate_accepted(snapshot)
        self.assertEqual(gate.stage2_accepted_baseline(snapshot)["stage2AcceptedBaselineDigest"],
                         original_digest)

    def test_accepted_broker_start_ticks_cannot_drift(self):
        snapshot = accepted_fixture()
        snapshot["runtimeIncarnations"]["broker"]["startTicks"] += 1
        with self.assertRaises(gate.LifecycleError):
            gate.validate_accepted(snapshot)

    def _reject_accepted(self, mutations):
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                snapshot = accepted_fixture()
                mutation(snapshot)
                with self.assertRaises(gate.LifecycleError):
                    gate.validate_accepted(snapshot)

    def _reject_failed(self, mutations):
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                snapshot = failed_fixture()
                mutation(snapshot)
                with self.assertRaises(gate.LifecycleError):
                    gate.validate_failed_inert(snapshot)

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
