"""B1b-1 synthetic-only broker foundation tests; never touches a live path."""

from __future__ import annotations

import dataclasses
import json
import os
import sqlite3
import struct
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import rfc8785

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services" / "core-api"))
sys.path.insert(0, str(ROOT / "services" / "core-api" / "tests"))
sys.path.insert(0, str(ROOT / "services" / "memory-broker"))

from lilith_memory import canonical_authority as A
from lilith_memory import owner_proof as P
from lilith_memory_broker import core, protocol, request, state
import test_owner_proof as b1a_fixture


NOW = datetime(2026, 9, 23, 12, 0, 20, tzinfo=timezone.utc)


class InjectedCrash(RuntimeError):
    pass


@contextmanager
def connection(path):
    conn = sqlite3.connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


class BrokerCase(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"LILITH_ENV": "test"})
        env.start()
        self.addCleanup(env.stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.ledger = self.root / "owner_control.db"
        self.state = state.OwnerControlState.initialize_test(self.ledger)
        self.state.install_synthetic_credential(b1a_fixture.credential())
        self.cognitive = self.root / "cognitive.synthetic.db"
        with connection(self.cognitive) as conn:
            for statement in A.AUTHORITY_MIGRATION_STATEMENTS:
                conn.execute(statement)
        self.actor = A.LocalOwnerAuthority(self.cognitive, b"SYNTHETIC_ACTOR_AUTHORITY_TEST_KEY!", now_fn=lambda: NOW)
        self.broker = core.SyntheticBrokerCore(
            self.state, self.actor, now_fn=lambda: NOW,
            nonce_fn=lambda: bytes(range(32)),
        )

    def prepared(self):
        challenge = self.broker.prepare_synthetic()
        return challenge, b1a_fixture.assertion(challenge)

    def test_request_golden_and_closed_binding(self):
        item = request.construct_synthetic_request("och.synthetic-golden")
        golden = json.loads((Path(__file__).parent / "owner_request_golden.json").read_text())
        self.assertEqual(item.canonical_bytes().decode(), golden["canonicalJson"])
        self.assertEqual(item.request_digest, golden["requestDigest"])
        self.assertEqual(
            request.construct_synthetic_request(golden["secondChallengeId"]).request_digest,
            golden["secondRequestDigest"],
        )
        self.assertEqual(item.action.action_digest, golden["actionDigest"])
        self.assertEqual(len(item.request_digest), 64)
        self.assertEqual(request.OwnerRequestV1.from_dict(item.to_dict()), item)
        for field in ("logicalOwnerId", "intentRefId", "actionDigest", "actorRefId", "memoryClass", "expectedActiveRevisionId", "restoreTargetRevisionId", "operation"):
            mutated = item.to_dict()
            mutated[field] = "tampered"
            with self.subTest(field=field), self.assertRaises(request.RequestError):
                request.OwnerRequestV1.from_dict(mutated)
        for field in ("privacyNoticeVersion", "subjectKey", "subjectNamespace", "purpose"):
            mutated = item.to_dict()
            mutated[field] = "tampered"
            with self.subTest(field=field), self.assertRaises(request.RequestError):
                request.OwnerRequestV1.from_dict(mutated)
        for variant in (dict(item.to_dict(), arbitrary=True), {k: v for k, v in item.to_dict().items() if k != "intentRefId"}):
            with self.assertRaises(request.RequestError):
                request.OwnerRequestV1.from_dict(variant)
        with self.assertRaises(request.RequestError):
            request.synthetic_action("PROJECT_CODENAME_FACT")

    def test_protocol_closed_and_framed(self):
        good = protocol.encode_frame("PREPARE_SYNTHETIC", {"fixtureId": request.SYNTHETIC_FIXTURE_ID})
        self.assertEqual(protocol.parse_frame(good).operation, "PREPARE_SYNTHETIC")
        bad = [
            b"", good[:3], good + b"x", good[:-1],
            struct.pack(">I", 16385) + b"x",
            struct.pack(">I", 0),
        ]
        for value in bad:
            with self.subTest(value=value[:10]), self.assertRaises(protocol.ProtocolError):
                protocol.parse_frame(value)
        for operation, payload in (
            ("REMEMBER", {}), ("FORGET", {}), ("SQL", {"query": "DELETE"}),
            ("PREPARE_SYNTHETIC", {"fixtureId": request.SYNTHETIC_FIXTURE_ID, "path": "/tmp/x"}),
            ("PREPARE_SYNTHETIC", {"fixtureId": request.SYNTHETIC_FIXTURE_ID, "method": "issue"}),
            ("HEALTH", {"uid": 1002}), ("HEALTH", {"approved": True}),
        ):
            with self.subTest(operation=operation), self.assertRaises(protocol.ProtocolError):
                protocol.encode_frame(operation, payload)
        value = {"protocol": protocol.PROTOCOL, "schemaVersion": 2, "operation": "HEALTH", "payload": {}}
        raw = rfc8785.dumps(value)
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_frame(struct.pack(">I", len(raw)) + raw)
        raw = b'{"protocol":"LILITH_MEMORY_BROKER","protocol":"LILITH_MEMORY_BROKER","schemaVersion":1,"operation":"HEALTH","payload":{}}'
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_frame(struct.pack(">I", len(raw)) + raw)
        raw = b'{ "protocol":"LILITH_MEMORY_BROKER","schemaVersion":1,"operation":"HEALTH","payload":{} }'
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_frame(struct.pack(">I", len(raw)) + raw)

    def test_ledger_startup_fails_closed(self):
        self.state.validate_startup()
        with closing(self.state._connect()) as conn:
            self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            self.assertEqual(conn.execute("PRAGMA synchronous").fetchone()[0], 2)
            self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertTrue(Path(str(self.ledger) + "-wal").exists())
            self.assertTrue(Path(str(self.ledger) + "-shm").exists())
        self.assertIsNotNone(state.expected_schema_fingerprint())
        with self.assertRaises(state.StateError):
            state.OwnerControlState(self.root / "missing.db", mode=state.PRODUCTION_MODE).validate_startup()
        with self.assertRaises(state.StateError):
            state.OwnerControlState.initialize_test(self.ledger)
        with connection(self.ledger) as conn:
            conn.execute("UPDATE broker_schema_v1 SET fingerprint='0' || substr(fingerprint,2)")
        with self.assertRaises(state.StateError):
            self.state.validate_startup()

    def test_corruption_and_production_mode_reject_synthetic(self):
        corrupt = self.root / "corrupt.db"
        corrupt.write_bytes(b"not a sqlite database")
        with self.assertRaises(state.StateError):
            state.OwnerControlState(corrupt, mode=state.PRODUCTION_MODE).validate_startup()
        with self.assertRaises(state.StateError):
            state.OwnerControlState(self.ledger, mode=state.PRODUCTION_MODE).validate_startup()
        with patch.dict(os.environ, {"LILITH_ENV": "production"}):
            with self.assertRaises(state.StateError):
                self.state.install_synthetic_credential(b1a_fixture.credential())
            with self.assertRaises(core.BrokerError):
                core.SyntheticBrokerCore(self.state, self.actor)

    def test_unknown_schema_and_foreign_key_fail_closed(self):
        with connection(self.ledger) as conn:
            conn.execute("CREATE TABLE unexpected_authority(x TEXT)")
        with self.assertRaisesRegex(state.StateError, "SCHEMA_MISMATCH"):
            self.state.validate_startup()
        with connection(self.ledger) as conn:
            conn.execute("DROP TABLE unexpected_authority")
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute("INSERT INTO owner_credential_v1 VALUES ('orphan','absent',X'7B7D')")
        with self.assertRaisesRegex(state.StateError, "FOREIGN_KEY_VIOLATION"):
            self.state.validate_startup()

    def test_public_credential_registry_and_b1a_view(self):
        with connection(self.ledger) as conn:
            public = conn.execute("SELECT credential_json FROM owner_credential_v1").fetchone()[0]
            viewed = conn.execute("SELECT credential_json FROM owner_proof_test_credential_v1").fetchone()[0]
        self.assertEqual(public, viewed)
        self.assertEqual(set(json.loads(public)), P._CREDENTIAL_FIELDS)
        self.assertNotIn("privateKey", json.loads(public))
        challenge, proof = self.prepared()
        self.broker.confirm_synthetic(challenge.challenge_id, proof)
        revoked = b1a_fixture.credential(status="REVOKED")
        with connection(self.ledger) as conn:
            conn.execute("UPDATE owner_credential_v1 SET credential_json=? WHERE record_id=?", (rfc8785.dumps(revoked.to_dict()), revoked.record_id))
        challenge, proof = self.prepared()
        with self.assertRaisesRegex(P.OwnerProofError, "CREDENTIAL_NOT_AUTHORIZED"):
            self.broker.confirm_synthetic(challenge.challenge_id, proof)

    def test_exact_proof_to_evidence_and_restart(self):
        challenge, proof = self.prepared()
        result = self.broker.confirm_synthetic(challenge.challenge_id, proof)
        self.assertEqual(result["status"], "SYNTHETIC_EVIDENCE_COMMITTED")
        self.assertEqual(self.state.challenge_store.state(challenge.challenge_id), "CONSUMED")
        row = self.state.claim_row(challenge.challenge_id)
        self.assertEqual(row[3], "EVIDENCE_COMMITTED")
        with connection(self.cognitive) as conn:
            evidence = conn.execute("SELECT request_digest,action_digest,nonce FROM actor_evidence_ref").fetchone()
        self.assertEqual(evidence, (challenge.request_digest, challenge.action_digest, challenge.challenge_id))
        self.assertEqual(evidence[0], self.state.request(challenge.challenge_id).request_digest)
        self.assertEqual(self.broker.recover(challenge.challenge_id)["status"], "EXISTING_EVIDENCE_RECONCILED")
        reopened = state.OwnerControlState(self.ledger, mode=state.TEST_MODE)
        reopened.validate_startup()
        self.assertEqual(reopened.claim_row(challenge.challenge_id)[3], "EVIDENCE_COMMITTED")
        with self.assertRaises(P.OwnerProofError):
            self.broker.confirm_synthetic(challenge.challenge_id, proof)

    def test_claim_requires_consumed_exact_proof(self):
        challenge, _ = self.prepared()
        request_digest = self.state.request(challenge.challenge_id).request_digest
        fake = P.OwnerProofVerificationResultV1(challenge.challenge_id, "ocred.synthetic", request.SYNTHETIC_ACCESS_IDENTITY, challenge.action_digest, request_digest, 0, False)
        with self.assertRaisesRegex(state.StateError, "CONSUMED_CHALLENGE_REQUIRED"):
            self.state.claim(fake)
        with self.assertRaisesRegex(state.StateError, "PROOF_BINDING_MISMATCH"):
            self.state.claim(dataclasses.replace(fake, request_digest="0" * 64))
        with self.assertRaisesRegex(state.StateError, "PROOF_BINDING_MISMATCH"):
            self.state.claim(dataclasses.replace(fake, action_digest="0" * 64))

    def test_concurrent_claim_insert_is_unique(self):
        challenge, assertion = self.prepared()
        req = self.state.request(challenge.challenge_id)
        proof = self.broker._verifier().verify_and_consume(
            challenge.challenge_id, assertion,
            expected_action=req.action,
            expected_request_digest=req.request_digest,
            expected_memory_item_id=None,
            expected_restore_target_digest=None,
            expected_privacy_notice_version=req.privacy_notice_version,
        )
        barrier = threading.Barrier(2)
        def attempt(_):
            barrier.wait()
            try:
                self.state.claim(proof)
                return "CLAIMED"
            except state.StateError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(sorted(results), ["CLAIMED", "CLAIM_ALREADY_EXISTS"])
        self.assertEqual(self.state.claim_row(challenge.challenge_id)[3], "CLAIMED")

    def test_crash_points_and_no_reissue(self):
        cases = {
            "after_proof_consumed": (None, "PROOF_BURNED_NO_CLAIM", 0),
            "before_claim_insert": (None, "PROOF_BURNED_NO_CLAIM", 0),
            "after_claim_commit": ("CLAIMED", "EVIDENCE_ABSENT_NO_REISSUE", 0),
            "before_evidence_issue": ("CLAIMED", "EVIDENCE_ABSENT_NO_REISSUE", 0),
            "after_evidence_commit": ("CLAIMED", "EXISTING_EVIDENCE_RECONCILED", 1),
            "before_claim_linkage": ("CLAIMED", "EXISTING_EVIDENCE_RECONCILED", 1),
            "after_linkage": ("EVIDENCE_COMMITTED", "EXISTING_EVIDENCE_RECONCILED", 1),
        }
        for point, (before, recovered, count) in cases.items():
            with self.subTest(point=point):
                challenge, proof = self.prepared()
                def fault(name):
                    if name == point:
                        raise InjectedCrash(name)
                with self.assertRaises(InjectedCrash):
                    self.broker.confirm_synthetic(challenge.challenge_id, proof, fault_hook=fault)
                row = self.state.claim_row(challenge.challenge_id)
                self.assertEqual(row[3] if row else None, before)
                self.assertEqual(self.broker.recover(challenge.challenge_id)["status"], recovered)
                with connection(self.cognitive) as conn:
                    actual = conn.execute("SELECT COUNT(*) FROM actor_evidence_ref WHERE nonce=?", (challenge.challenge_id,)).fetchone()[0]
                self.assertEqual(actual, count)
                with self.assertRaises(P.OwnerProofError):
                    self.broker.confirm_synthetic(challenge.challenge_id, proof)

    def test_concurrent_confirmation_one_claim_one_evidence(self):
        challenge, proof = self.prepared()
        barrier = threading.Barrier(2)
        def attempt(_):
            barrier.wait()
            try:
                return self.broker.confirm_synthetic(challenge.challenge_id, proof)["status"]
            except P.OwnerProofError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(sorted(results), ["CHALLENGE_NOT_PREPARED", "SYNTHETIC_EVIDENCE_COMMITTED"])
        with connection(self.ledger) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM owner_authority_claim_v1 WHERE challenge_id=?", (challenge.challenge_id,)).fetchone()[0], 1)
        with connection(self.cognitive) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM actor_evidence_ref WHERE nonce=?", (challenge.challenge_id,)).fetchone()[0], 1)

    def test_privacy_erasure_simulation_never_reissues(self):
        challenge, proof = self.prepared()
        self.broker.confirm_synthetic(challenge.challenge_id, proof)
        # A synthetic isolated fixture simulates the authorized Privacy owner
        # removing an evidence row. No PROD trigger or file is changed.
        with connection(self.cognitive) as conn:
            conn.execute("DROP TRIGGER actor_evidence_ref_no_delete")
            conn.execute("DELETE FROM actor_evidence_ref WHERE nonce=?", (challenge.challenge_id,))
        self.assertEqual(self.broker.recover(challenge.challenge_id)["status"], "EVIDENCE_ABSENT_NO_REISSUE")
        self.assertEqual(self.state.claim_row(challenge.challenge_id)[3], "EVIDENCE_COMMITTED")

    def test_erasure_before_claim_linkage_never_reissues(self):
        challenge, proof = self.prepared()
        def fault(name):
            if name == "after_evidence_commit":
                raise InjectedCrash(name)
        with self.assertRaises(InjectedCrash):
            self.broker.confirm_synthetic(challenge.challenge_id, proof, fault_hook=fault)
        with connection(self.cognitive) as conn:
            conn.execute("DROP TRIGGER actor_evidence_ref_no_delete")
            conn.execute("DELETE FROM actor_evidence_ref WHERE nonce=?", (challenge.challenge_id,))
        self.assertEqual(self.broker.recover(challenge.challenge_id)["status"], "EVIDENCE_ABSENT_NO_REISSUE")
        self.assertEqual(self.state.claim_row(challenge.challenge_id)[3], "ABANDONED")

    def test_access_context_not_authority(self):
        msg = protocol.parse_frame(protocol.encode_frame("ACCESS_CONTEXT", {}))
        result = self.broker.dispatch(msg)
        self.assertEqual(result["logicalOwnerId"], request.LOGICAL_OWNER_ID)
        self.assertNotEqual(result["logicalOwnerId"], result["accessIdentity"])
        self.assertEqual(result["assurance"], "UNVERIFIED_TRANSPORT_CONTEXT")
        self.assertNotIn("actorEvidenceRefId", result)


if __name__ == "__main__":
    unittest.main()
