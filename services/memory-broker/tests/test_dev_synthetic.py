"""Local-only persistent synthetic DEV boundary tests; no VM paths or accounts."""

from __future__ import annotations

import os
import json
import signal
import socket
import sqlite3
import stat
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import rfc8785


ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "services" / "core-api"), str(ROOT / "services" / "core-api" / "tests"), str(ROOT / "services" / "memory-broker")]

from lilith_memory import canonical_contracts as C
from lilith_memory import owner_proof as P
from lilith_memory_broker import dev_config, dev_core, dev_state, protocol, request, server, synthetic_evidence
import test_owner_proof as b1a_fixture


NOW = datetime(2026, 9, 23, 12, 0, 20, tzinfo=timezone.utc)
SHA = "b" * 40
MACHINE = dev_config.DEV_MACHINE_ID


def config_value(credential):
    return {
        "deploymentEnvironment": "dev", "authorityMode": "SYNTHETIC_ONLY",
        "stateProfile": dev_config.PROFILE, "canonicalCapability": "DISABLED",
        "expectedHost": dev_config.DEV_HOST, "machineId": MACHINE,
        "releaseSha": SHA, "logicalOwnerId": request.LOGICAL_OWNER_ID,
        "accessIdentity": request.SYNTHETIC_ACCESS_IDENTITY,
        "fixtureId": request.SYNTHETIC_FIXTURE_ID,
        "fixtureFingerprint": dev_config.fixture_fingerprint(),
        "credentialFingerprint": dev_config.credential_fingerprint(credential),
        "rpId": P.SYNTHETIC_RP_ID, "origin": P.SYNTHETIC_ORIGIN,
        "ownerSchemaFingerprint": dev_state.schema_fingerprint(),
        "evidenceSchemaFingerprint": synthetic_evidence.schema_fingerprint(),
        "custody": {name: "ABSENT" for name in ("cognitiveDb", "privacyDb", "actorKey", "privacyKey", "containmentKey")},
    }


def a2_arm(challenge, *, release=SHA):
    return {
        "schemaVersion": 1, "experimentId": dev_core.A2_EXPERIMENT_ID,
        "stage": "B1B2B_III_A", "faultPoint": dev_core.A2_FAULT_POINT,
        "deploymentEnvironment": "DEV", "authorityMode": "SYNTHETIC_ONLY",
        "stateProfile": dev_config.PROFILE, "canonicalCapability": "DISABLED",
        "logicalOwnerId": request.LOGICAL_OWNER_ID,
        "accessIdentity": request.SYNTHETIC_ACCESS_IDENTITY,
        "credentialRecordId": "ocred.synthetic",
        "fixtureId": request.SYNTHETIC_FIXTURE_ID,
        "fixtureFingerprint": dev_config.fixture_fingerprint(),
        "instrumentedReleaseId": release,
        "stage2AcceptedBaselineDigest": dev_core.A2_ACCEPTED_BASELINE_DIGEST,
        "stage3AuthorizationId": "auth.stage3.fixture",
        "challengeId": challenge.challenge_id,
        "requestDigest": challenge.request_digest,
        "actionDigest": challenge.action_digest,
        "issuedAt": NOW.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "expiresAt": (NOW + timedelta(seconds=30)).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "armNonce": "a" * 64,
    }


def parsed_a2_arm(challenge, config):
    return dev_core.Stage3FaultArmV1.from_bytes(
        rfc8785.dumps(a2_arm(challenge)), config=config, now=NOW)


class DevSyntheticCase(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"LILITH_ENV": "dev"})
        env.start()
        self.addCleanup(env.stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "owner-control").mkdir()
        (self.root / "state").mkdir()
        self.credential = b1a_fixture.credential()
        self.config = dev_config.DevConfig.from_dict(config_value(self.credential))
        self.owner_path = self.root / "owner-control" / "owner_control.db"
        self.evidence_path = self.root / "state" / "synthetic_evidence.db"

    def provision(self):
        owner = dev_state.DevOwnerControlState.provision(self.owner_path, self.config, self.credential, expected_uid=os.getuid() if hasattr(os, "getuid") else None)
        evidence = synthetic_evidence.SyntheticEvidenceStore.provision(self.evidence_path, release_sha=SHA, expected_uid=os.getuid() if hasattr(os, "getuid") else None)
        broker = dev_core.DevSyntheticBrokerCore(
            self.config, owner, evidence, hostname="lilith-dev-01", machine_id=MACHINE,
            release_sha=SHA, now_fn=lambda: NOW, nonce_fn=lambda: bytes(range(32)),
        )
        return owner, evidence, broker

    def test_closed_dev_config_and_b1a_guard(self):
        value = config_value(self.credential)
        for key, replacement in (("deploymentEnvironment", "prod"), ("authorityMode", "LIVE"), ("canonicalCapability", "ENABLED"), ("credentialFingerprint", "bad"), ("releaseSha", "bad"), ("rpId", "real.example")):
            bad = dict(value, **{key: replacement})
            with self.subTest(key=key), self.assertRaises(dev_config.DevConfigError):
                dev_config.DevConfig.from_dict(bad)
        bad = dict(value, custody={**value["custody"], "cognitiveDb": "/home/lilith/cognitive_memory.db"})
        with self.assertRaises(dev_config.DevConfigError):
            dev_config.DevConfig.from_dict(bad)
        with self.assertRaises(P.OwnerProofError):
            P.OwnerProofVerifier(None, owner_principal=request.SYNTHETIC_ACCESS_IDENTITY, rp_id=P.SYNTHETIC_RP_ID, origin=P.SYNTHETIC_ORIGIN, test_mode=True)
        with self.assertRaises(dev_config.DevConfigError):
            self.config.validate_runtime(hostname="lilith-01", machine_id=MACHINE, release_sha=SHA)
        with self.assertRaises(dev_config.DevConfigError):
            self.config.validate_runtime(hostname="lilith-dev-01", machine_id=MACHINE, release_sha="c" * 40)

    def test_provision_then_start_never_auto_creates(self):
        with self.assertRaises(dev_state.legacy.StateError):
            dev_state.DevOwnerControlState(self.owner_path, self.config).validate_startup()
        with self.assertRaises(synthetic_evidence.SyntheticEvidenceError):
            synthetic_evidence.SyntheticEvidenceStore(self.evidence_path, release_sha=SHA).validate_startup()
        owner, evidence, broker = self.provision()
        self.assertEqual(broker.dispatch(type("Message", (), {"operation": "HEALTH", "payload": {}})())["status"], "SYNTHETIC_DEV_ONLY")
        with self.assertRaises(dev_state.legacy.StateError):
            dev_state.DevOwnerControlState.provision(self.owner_path, self.config, self.credential)
        owner.validate_startup()
        evidence.validate_startup()
        self.assertFalse((self.root / "cognitive_memory.db").exists())
        self.assertFalse((self.root / "privacy_governance.db").exists())
        with patch.dict(os.environ, {"LILITH_ENV": "prod"}):
            with self.assertRaises(dev_config.DevConfigError):
                dev_core.DevSyntheticBrokerCore(self.config, owner, evidence, hostname="lilith-dev-01", machine_id=MACHINE, release_sha=SHA)

    def test_one_proof_one_synthetic_evidence_and_restart(self):
        owner, evidence, broker = self.provision()
        challenge = broker.prepare_synthetic()
        result = broker.confirm_synthetic(challenge.challenge_id, b1a_fixture.assertion(challenge))
        self.assertEqual(result["status"], "SYNTHETIC_EVIDENCE_COMMITTED")
        item = evidence.find(challenge.challenge_id)
        self.assertTrue(item.synthetic_evidence_id.startswith("se."))
        with self.assertRaises(TypeError):
            C.ActorEvidenceRefV1(**item.__dict__)
        reopened = dev_core.DevSyntheticBrokerCore(
            self.config, dev_state.DevOwnerControlState(self.owner_path, self.config),
            synthetic_evidence.SyntheticEvidenceStore(self.evidence_path, release_sha=SHA),
            hostname="lilith-dev-01", machine_id=MACHINE, release_sha=SHA, now_fn=lambda: NOW,
        )
        self.assertEqual(reopened.recover(challenge.challenge_id)["status"], "EXISTING_SYNTHETIC_EVIDENCE_RECONCILED")
        with self.assertRaises(P.OwnerProofError):
            reopened.confirm_synthetic(challenge.challenge_id, b1a_fixture.assertion(challenge))
        with closing(sqlite3.connect(self.evidence_path)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM synthetic_evidence_v1").fetchone()[0], 1)

    def test_crash_before_claim_burns_proof(self):
        _, evidence, broker = self.provision()
        challenge = broker.prepare_synthetic()
        with self.assertRaisesRegex(RuntimeError, "crash"):
            broker.confirm_synthetic(challenge.challenge_id, b1a_fixture.assertion(challenge), fault_hook=lambda point: (_ for _ in ()).throw(RuntimeError("crash")) if point == "after_proof_consumed" else None)
        self.assertEqual(broker.recover(challenge.challenge_id)["status"], "PROOF_BURNED_NO_CLAIM")
        self.assertIsNone(evidence.find(challenge.challenge_id))

    def test_a2_exact_placement_counter_recovery_and_replay(self):
        owner, evidence, broker = self.provision()
        challenge = broker.prepare_synthetic()
        arm = parsed_a2_arm(challenge, self.config)
        class BarrierReached(RuntimeError):
            pass
        with patch.object(dev_core, "_load_stage3_arm", return_value=arm) as loader, \
             patch.object(dev_core, "_a2_barrier", side_effect=BarrierReached) as barrier:
            with self.assertRaises(BarrierReached):
                broker.confirm_synthetic(challenge.challenge_id,
                                         b1a_fixture.assertion(challenge, counter=4))
            self.assertEqual(owner.challenge_store.state(challenge.challenge_id), "CONSUMED")
            with closing(sqlite3.connect(self.owner_path)) as conn:
                self.assertEqual(conn.execute(
                    "SELECT COUNT(*) FROM owner_request_v1 WHERE challenge_id=?",
                    (challenge.challenge_id,)).fetchone()[0], 1)
                self.assertEqual(conn.execute(
                    "SELECT COUNT(*) FROM synthetic_claim_v1 WHERE challenge_id=?",
                    (challenge.challenge_id,)).fetchone()[0], 0)
                raw = conn.execute("SELECT credential_json FROM owner_credential_v1").fetchone()[0]
                self.assertEqual(P.OwnerCredentialV1.from_dict(json.loads(raw)).last_observed_sign_count, 4)
            self.assertIsNone(evidence.find(challenge.challenge_id))
            self.assertEqual(broker.recover(challenge.challenge_id)["status"],
                             "PROOF_BURNED_NO_CLAIM")
            with self.assertRaises(P.OwnerProofError):
                broker.confirm_synthetic(challenge.challenge_id,
                                         b1a_fixture.assertion(challenge, counter=4))
            self.assertEqual(loader.call_count, 1)
            barrier.assert_called_once_with(arm, NOW)

    def test_a2_arm_cannot_trigger_unrelated_transaction(self):
        owner, evidence, broker = self.provision()
        x = broker.prepare_synthetic()
        arm = parsed_a2_arm(x, self.config)
        y = broker.prepare_synthetic()
        with patch.object(dev_core, "_load_stage3_arm", return_value=arm), \
             patch.object(dev_core, "_a2_barrier") as barrier:
            result = broker.confirm_synthetic(y.challenge_id, b1a_fixture.assertion(y))
        self.assertEqual(result["status"], "SYNTHETIC_EVIDENCE_COMMITTED")
        self.assertEqual(owner.challenge_store.state(x.challenge_id), "PREPARED")
        self.assertEqual(owner.challenge_store.state(y.challenge_id), "CONSUMED")
        self.assertIsNone(evidence.find(x.challenge_id))
        self.assertIsNotNone(evidence.find(y.challenge_id))
        barrier.assert_not_called()

    def test_a2_wrong_request_or_action_binding_never_barriers(self):
        _, evidence, broker = self.provision()
        for field in ("requestDigest", "actionDigest"):
            with self.subTest(field=field):
                challenge = broker.prepare_synthetic()
                arm = dev_core.Stage3FaultArmV1.from_bytes(
                    rfc8785.dumps({**a2_arm(challenge), field: "0" * 64}),
                    config=self.config, now=NOW)
                with patch.object(dev_core, "_load_stage3_arm", return_value=arm), \
                     patch.object(dev_core, "_a2_barrier") as barrier:
                    result = broker.confirm_synthetic(
                        challenge.challenge_id, b1a_fixture.assertion(challenge))
                self.assertEqual(result["status"], "SYNTHETIC_EVIDENCE_COMMITTED")
                self.assertIsNotNone(evidence.find(challenge.challenge_id))
                barrier.assert_not_called()

    def test_a2_arm_closed_guards_binding_and_time(self):
        _, _, broker = self.provision()
        challenge = broker.prepare_synthetic()
        valid = a2_arm(challenge)
        cases = {
            "schemaVersion": 2, "experimentId": "A1", "stage": "B1B2B_III_B",
            "faultPoint": "A3_AFTER_CLAIM", "deploymentEnvironment": "PROD",
            "authorityMode": "LIVE", "stateProfile": "UNKNOWN",
            "canonicalCapability": "ENABLED", "logicalOwnerId": "owner.other",
            "accessIdentity": "user:real@example.com", "credentialRecordId": "ocred.real",
            "fixtureId": "fixture.other", "fixtureFingerprint": "0" * 64,
            "instrumentedReleaseId": "c" * 40,
            "stage2AcceptedBaselineDigest": "0" * 64,
            "stage3AuthorizationId": "bad id", "armNonce": "bad",
            "issuedAt": (NOW + timedelta(seconds=1)).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "expiresAt": NOW.isoformat(timespec="seconds").replace("+00:00", "Z"),
        }
        for field, wrong in cases.items():
            with self.subTest(field=field), self.assertRaises(dev_core.DevBrokerError):
                dev_core.Stage3FaultArmV1.from_bytes(
                    rfc8785.dumps({**valid, field: wrong}), config=self.config, now=NOW)
        for field, wrong in (("challengeId", "och.other"),
                             ("requestDigest", "0" * 64), ("actionDigest", "0" * 64)):
            altered = dev_core.Stage3FaultArmV1.from_bytes(
                rfc8785.dumps({**valid, field: wrong}), config=self.config, now=NOW)
            req = broker.state.request(challenge.challenge_id)
            proof = P.OwnerProofVerificationResultV1(
                challenge.challenge_id, "ocred.synthetic", request.SYNTHETIC_ACCESS_IDENTITY,
                challenge.action_digest, challenge.request_digest, 0, False)
            with self.subTest(field=field):
                self.assertFalse(altered.matches(proof, req))
        for raw in (b"{", b"\xff", b"{}", rfc8785.dumps({**valid, "extra": 1}),
                    b'{"schemaVersion":1,"schemaVersion":1}'):
            with self.subTest(raw=raw), self.assertRaises(dev_core.DevBrokerError):
                dev_core.Stage3FaultArmV1.from_bytes(raw, config=self.config, now=NOW)
        with self.assertRaises(dev_core.DevBrokerError):
            dev_core.Stage3FaultArmV1.from_bytes(
                rfc8785.dumps(valid), config=dev_config.DevConfig.from_dict(
                    {**config_value(self.credential), "releaseSha": dev_core.A2_ACCEPTED_RELEASE}), now=NOW)

    @unittest.skipUnless(os.name == "posix", "Linux-only safe-open custody checks")
    def test_a2_fixed_safe_open_rejects_substitution_and_bad_custody(self):
        arm_dir = self.root / "a2-arm"
        arm_dir.mkdir(mode=0o750)
        arm_file = arm_dir / dev_core.A2_ARM_NAME
        _, _, broker = self.provision()
        challenge = broker.prepare_synthetic()
        raw = rfc8785.dumps(a2_arm(challenge))
        arm_file.write_bytes(raw)
        arm_file.chmod(0o640)
        actual_fstat = os.fstat
        def root_owned(fd):
            item = actual_fstat(fd)
            return SimpleNamespace(st_mode=item.st_mode, st_uid=0, st_gid=os.getgid(),
                                   st_nlink=item.st_nlink, st_size=item.st_size)
        with patch.object(dev_core, "A2_ARM_DIRECTORY", arm_dir), \
             patch.object(dev_core.os, "fstat", side_effect=root_owned):
            self.assertEqual(dev_core._load_stage3_arm(self.config, NOW),
                             parsed_a2_arm(challenge, self.config))
            arm_file.chmod(0o600)
            with self.assertRaises(dev_core.DevBrokerError):
                dev_core._load_stage3_arm(self.config, NOW)
            arm_file.chmod(0o640)
            def wrong_uid(fd):
                item = root_owned(fd)
                if stat.S_ISREG(item.st_mode):
                    item.st_uid = 1001
                return item
            def wrong_gid(fd):
                item = root_owned(fd)
                if stat.S_ISREG(item.st_mode):
                    item.st_gid = os.getgid() + 1
                return item
            with patch.object(dev_core.os, "fstat", side_effect=wrong_uid):
                with self.assertRaises(dev_core.DevBrokerError):
                    dev_core._load_stage3_arm(self.config, NOW)
            with patch.object(dev_core.os, "fstat", side_effect=wrong_gid):
                with self.assertRaises(dev_core.DevBrokerError):
                    dev_core._load_stage3_arm(self.config, NOW)
            arm_file.write_bytes(b"x" * (dev_core.A2_MAX_ARM_BYTES + 1))
            with self.assertRaises(dev_core.DevBrokerError):
                dev_core._load_stage3_arm(self.config, NOW)
            arm_file.unlink()
            arm_file.symlink_to(self.owner_path)
            with self.assertRaises(OSError):
                dev_core._load_stage3_arm(self.config, NOW)
            arm_file.unlink()
        with patch.object(dev_core, "A2_ARM_DIRECTORY", self.root / "absent"):
            self.assertIsNone(dev_core._load_stage3_arm(self.config, NOW))

    def test_a2_barrier_is_fixed_non_secret_event_then_sigstop(self):
        _, _, broker = self.provision()
        challenge = broker.prepare_synthetic()
        arm = parsed_a2_arm(challenge, self.config)
        class StopSubstituted(RuntimeError):
            pass
        expected_stop = getattr(signal, "SIGSTOP", 19)
        with patch.object(dev_core.signal, "SIGSTOP", expected_stop, create=True), \
             patch.object(dev_core.os, "write", return_value=1) as emit, \
             patch.object(dev_core.os, "kill", side_effect=StopSubstituted) as stop:
            with self.assertRaises(StopSubstituted):
                dev_core._a2_barrier(arm, NOW)
        self.assertEqual(emit.call_args.args[0], 2)
        event = json.loads(emit.call_args.args[1])
        self.assertEqual(set(event), {"eventType", "experimentId", "faultPoint", "brokerPid",
                                      "instrumentedReleaseId", "challengeId", "requestDigest",
                                      "actionDigest", "timestamp"})
        self.assertEqual(event["faultPoint"], dev_core.A2_FAULT_POINT)
        self.assertEqual(event["challengeId"], challenge.challenge_id)
        stop.assert_called_once_with(os.getpid(), expected_stop)

    def test_a2_no_ipc_arming_and_disarmed_confirmation(self):
        _, evidence, broker = self.provision()
        self.assertEqual(server.ALLOWED_IPC_OPERATIONS,
                         frozenset({"HEALTH", "PREPARE_SYNTHETIC", "CONFIRM_SYNTHETIC", "CANCEL"}))
        challenge = broker.prepare_synthetic()
        with patch.object(dev_core, "_load_stage3_arm", return_value=None), \
             patch.object(dev_core, "_a2_barrier") as barrier:
            self.assertEqual(broker.confirm_synthetic(
                challenge.challenge_id, b1a_fixture.assertion(challenge))["status"],
                "SYNTHETIC_EVIDENCE_COMMITTED")
        barrier.assert_not_called()
        self.assertIsNotNone(evidence.find(challenge.challenge_id))

    def test_crash_after_claim_never_issues(self):
        _, evidence, broker = self.provision()
        challenge = broker.prepare_synthetic()
        with self.assertRaisesRegex(RuntimeError, "crash"):
            broker.confirm_synthetic(challenge.challenge_id, b1a_fixture.assertion(challenge), fault_hook=lambda point: (_ for _ in ()).throw(RuntimeError("crash")) if point == "after_claim_commit" else None)
        self.assertEqual(broker.recover(challenge.challenge_id)["status"], "EVIDENCE_ABSENT_NO_REISSUE")
        self.assertIsNone(evidence.find(challenge.challenge_id))

    def test_crash_after_evidence_reconciles_same_record(self):
        _, evidence, broker = self.provision()
        challenge = broker.prepare_synthetic()
        with self.assertRaisesRegex(RuntimeError, "crash"):
            broker.confirm_synthetic(challenge.challenge_id, b1a_fixture.assertion(challenge), fault_hook=lambda point: (_ for _ in ()).throw(RuntimeError("crash")) if point == "after_evidence_commit" else None)
        before = evidence.find(challenge.challenge_id)
        self.assertEqual(broker.recover(challenge.challenge_id)["status"], "EXISTING_SYNTHETIC_EVIDENCE_RECONCILED")
        self.assertEqual(evidence.find(challenge.challenge_id), before)
        with closing(sqlite3.connect(self.evidence_path)) as conn:
            conn.execute("DELETE FROM synthetic_evidence_v1 WHERE challenge_id=?", (challenge.challenge_id,))
            conn.commit()
        self.assertEqual(broker.recover(challenge.challenge_id)["status"], "EVIDENCE_ABSENT_NO_REISSUE")

    def test_invalid_mode_or_state_rejected(self):
        owner, evidence, _ = self.provision()
        with closing(sqlite3.connect(self.owner_path)) as conn:
            conn.execute("UPDATE owner_access_identity_v1 SET access_identity='user:wrong@example.invalid'")
            conn.commit()
        with self.assertRaises(dev_state.legacy.StateError):
            owner.validate_startup()
        with self.assertRaises(dev_state.legacy.StateError):
            dev_core.DevSyntheticBrokerCore(self.config, owner, evidence, hostname="lilith-dev-01", machine_id=MACHINE, release_sha=SHA)
        with closing(sqlite3.connect(self.owner_path)) as conn:
            conn.execute("UPDATE owner_access_identity_v1 SET access_identity=?", (request.SYNTHETIC_ACCESS_IDENTITY,))
            conn.execute("CREATE TABLE unexpected_authority_state (value TEXT)")
            conn.commit()
        with self.assertRaises(dev_state.legacy.StateError):
            owner.validate_startup()
        with closing(sqlite3.connect(self.owner_path)) as conn:
            conn.execute("DROP TABLE unexpected_authority_state")
            conn.commit()
        self.owner_path.write_bytes(b"not a sqlite database")
        with self.assertRaises((dev_state.legacy.StateError, sqlite3.DatabaseError)):
            owner.validate_startup()

    def test_wrong_credential_fingerprint_or_owner_mode(self):
        wrong = config_value(self.credential)
        wrong["credentialFingerprint"] = "0" * 64
        with self.assertRaises(dev_config.DevConfigError):
            dev_config.DevConfig.from_dict(wrong)
        owner, _, _ = self.provision()
        real = self.credential.to_dict()
        real["ownerPrincipal"] = "user:real@example.com"
        real["rpId"] = "real.example"
        with closing(sqlite3.connect(self.owner_path)) as conn:
            conn.execute("UPDATE owner_credential_v1 SET credential_json=?", (rfc8785.dumps(real),))
            conn.commit()
        with self.assertRaises(dev_state.legacy.StateError):
            owner.validate_startup()
        if os.name != "nt":
            os.chmod(self.owner_path, 0o644)
            with self.assertRaises(dev_state.legacy.StateError):
                owner.validate_startup()
            os.chmod(self.owner_path, 0o600)

    def test_dev_proof_rejects_wrong_origin_and_signature(self):
        _, evidence, broker = self.provision()
        challenge = broker.prepare_synthetic()
        bad_origin = b1a_fixture.assertion(challenge, origin="https://attacker.invalid")
        with self.assertRaises(P.OwnerProofError):
            broker.confirm_synthetic(challenge.challenge_id, bad_origin)
        bad_signature = b1a_fixture.assertion(challenge, signature=b"not-a-valid-signature")
        with self.assertRaises(P.OwnerProofError):
            broker.confirm_synthetic(challenge.challenge_id, bad_signature)
        self.assertIsNone(evidence.find(challenge.challenge_id))

    def test_shared_engine_is_the_only_proof_path(self):
        _, _, broker = self.provision()
        challenge = broker.prepare_synthetic()
        with patch.object(P.DevSyntheticOwnerProofVerifier, "verify_and_consume", side_effect=RuntimeError("SHARED_ENGINE_CALLED")):
            with self.assertRaisesRegex(RuntimeError, "SHARED_ENGINE_CALLED"):
                broker.confirm_synthetic(challenge.challenge_id, b1a_fixture.assertion(challenge))

    def test_runtime_public_credential_pin_fails_closed(self):
        owner, evidence, broker = self.provision()
        challenge = broker.prepare_synthetic()
        changed = self.credential.to_dict()
        changed["credentialId"] = P._b64u(b"x" * 32)
        with closing(sqlite3.connect(self.owner_path)) as conn:
            conn.execute("UPDATE owner_credential_v1 SET credential_json=?", (rfc8785.dumps(changed),))
            conn.commit()
        with self.assertRaises(dev_state.legacy.StateError):
            broker.confirm_synthetic(challenge.challenge_id, b1a_fixture.assertion(challenge))
        self.assertEqual(owner.challenge_store.state(challenge.challenge_id), "PREPARED")
        self.assertIsNone(evidence.find(challenge.challenge_id))

    def test_dev_policy_cannot_run_as_test_or_live(self):
        owner, _, broker = self.provision()
        challenge = broker.prepare_synthetic()
        for environment in ("test", "prod"):
            with self.subTest(environment=environment), patch.dict(os.environ, {"LILITH_ENV": environment}):
                with self.assertRaises(P.OwnerProofError):
                    P.DevSyntheticOwnerProofVerifier(owner.challenge_store)
                with self.assertRaises(P.OwnerProofError):
                    broker.confirm_synthetic(challenge.challenge_id, b1a_fixture.assertion(challenge))

    def test_peer_logical_owner_and_proof_are_separate(self):
        owner, evidence, broker = self.provision()
        challenge = broker.prepare_synthetic()
        assertion = b1a_fixture.assertion(challenge)
        payload = {
            "challengeId": challenge.challenge_id,
            "assertion": {
                "credentialRecordId": assertion.credential_record_id,
                "credentialId": assertion.credential_id,
                "clientDataJSON": assertion.client_data_json,
                "authenticatorData": assertion.authenticator_data,
                "signature": assertion.signature,
            },
        }
        frame = protocol.encode_frame("CONFIRM_SYNTHETIC", payload)

        def exchange(peer: int, body: bytes) -> bytes:
            client, accepted = socket.socketpair()
            try:
                client.sendall(body)
                server.serve_connection(accepted, broker, authorized_uid=1001, peer_uid_reader=lambda _sock: peer)
                try:
                    return client.recv(16388)
                except ConnectionResetError:
                    return b""
            finally:
                client.close()

        # A valid WebAuthn assertion from the wrong Linux peer is not dispatched.
        self.assertEqual(exchange(1002, frame), b"")
        self.assertEqual(owner.challenge_store.state(challenge.challenge_id), "PREPARED")
        self.assertIsNone(evidence.find(challenge.challenge_id))
        # A logical owner string supplied in JSON is not a credential or peer proof.
        with self.assertRaises(protocol.ProtocolError):
            protocol.encode_frame("PREPARE_SYNTHETIC", {
                "fixtureId": request.SYNTHETIC_FIXTURE_ID,
                "logicalOwnerId": request.LOGICAL_OWNER_ID,
            })
        # The correct peer alone does not confer proof: malformed assertion is rejected.
        bad = dict(payload, assertion={**payload["assertion"], "signature": P._b64u(b"invalid")})
        self.assertEqual(exchange(1001, protocol.encode_frame("CONFIRM_SYNTHETIC", bad)), b"")
        self.assertEqual(owner.challenge_store.state(challenge.challenge_id), "PREPARED")
        self.assertIn(b"SYNTHETIC_EVIDENCE_COMMITTED", exchange(1001, frame))
        self.assertIsNotNone(evidence.find(challenge.challenge_id))


if __name__ == "__main__":
    unittest.main()
