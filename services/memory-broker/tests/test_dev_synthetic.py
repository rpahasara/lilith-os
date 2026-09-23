"""Local-only persistent synthetic DEV boundary tests; no VM paths or accounts."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "services" / "core-api"), str(ROOT / "services" / "core-api" / "tests"), str(ROOT / "services" / "memory-broker")]

from lilith_memory import canonical_contracts as C
from lilith_memory import owner_proof as P
from lilith_memory_broker import dev_config, dev_core, dev_state, request, synthetic_evidence
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

    def test_wrong_credential_fingerprint_or_owner_mode(self):
        wrong = config_value(self.credential)
        wrong["credentialFingerprint"] = "0" * 64
        with self.assertRaises(dev_config.DevConfigError):
            dev_config.DevConfig.from_dict(wrong)
        owner, _, _ = self.provision()
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


if __name__ == "__main__":
    unittest.main()
