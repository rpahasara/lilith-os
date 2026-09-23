"""TEST_ONLY synthetic WebAuthn owner-proof contracts; never enrolls a user."""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fido2 import cbor
from fido2.cose import ES256

CORE_API = Path(__file__).resolve().parents[1]
if str(CORE_API) not in sys.path:
    sys.path.insert(0, str(CORE_API))

from lilith_memory import canonical_contracts as C
from lilith_memory import owner_proof as P


OWNER = "user:synthetic-owner@example.invalid"
RP = P.SYNTHETIC_RP_ID
ORIGIN = P.SYNTHETIC_ORIGIN
NOW = datetime(2026, 9, 23, 12, 0, 20, tzinfo=timezone.utc)
# Deliberately fixed, TEST_ONLY fixture scalar. It is not packaged in DEV.
TEST_ONLY_PRIVATE_SCALAR = 0x8A98159F36D8F33E8F26E728AFCB09F3


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def action(operation: str = "CREATE") -> C.FrozenMemoryActionV1:
    return C.FrozenMemoryActionV1(
        schema_version=1,
        actor_ref_id="actor.synthetic",
        operation=operation,
        memory_class="PROJECT_CODENAME_FACT",
        subject_namespace="project.homelab",
        subject_key="codename",
        value_schema="HomelabCodenameV1" if operation in {"CREATE", "SUPERSEDE"} else None,
        payload_digest=hashlib.sha256(
            b"TEST_ONLY old value" if operation == "RESTORE" else b"TEST_ONLY synthetic value binding"
        ).hexdigest(),
        expected_active_revision_id="mrev.synthetic-current" if operation in {"SUPERSEDE", "RESTORE"} else None,
        restore_revision_id="mrev.synthetic-history" if operation == "RESTORE" else None,
        purpose=C.LONG_TERM_PERSONAL_PROJECT_RECALL,
    )


def challenge(operation: str = "CREATE") -> P.OwnerMemoryChallengeV1:
    a = action(operation)
    return P.OwnerMemoryChallengeV1.from_dict({
        "protocol": P.PROTOCOL,
        "schemaVersion": 1,
        "ownerPrincipal": OWNER,
        "challengeId": "och.synthetic-" + operation.lower(),
        "actionDigest": a.action_digest,
        "payloadDigest": a.payload_digest,
        "operation": operation,
        "memoryClass": a.memory_class,
        "subjectNamespace": a.subject_namespace,
        "subjectKey": a.subject_key,
        "purpose": a.purpose,
        "memoryItemId": None if operation == "CREATE" else "mitem.synthetic",
        "expectedActiveRevisionId": a.expected_active_revision_id,
        "restoreTargetRevisionId": a.restore_revision_id,
        "restoreTargetDigest": a.payload_digest if operation == "RESTORE" else None,
        "privacyNoticeVersion": "privacy.synthetic.v1",
        "nonce": b64(bytes(range(32))),
        "issuedAt": "2026-09-23T12:00:00Z",
        "expiresAt": "2026-09-23T12:01:00Z",
        "rpId": RP,
    })


def key(scalar: int = TEST_ONLY_PRIVATE_SCALAR):
    return ec.derive_private_key(scalar, ec.SECP256R1())


def credential(private=None, *, status="ACTIVE", algorithm=-7, owner=OWNER, rp=RP, last_count=0):
    private = private or key()
    return P.OwnerCredentialV1.from_dict({
        "schemaVersion": 1,
        "recordId": "ocred.synthetic",
        "ownerPrincipal": owner,
        "credentialId": b64(b"TEST_ONLY_CREDENTIAL_ID_00001"),
        "publicKeyCose": b64(cbor.encode(ES256.from_cryptography_key(private.public_key()))),
        "algorithm": algorithm,
        "rpId": rp,
        "status": status,
        "createdAt": "2026-09-23T11:00:00Z",
        "revokedAt": "2026-09-23T11:30:00Z" if status == "REVOKED" else None,
        "lastObservedSignCount": last_count,
    })


def assertion(ch: P.OwnerMemoryChallengeV1, private=None, *, credential_id=None,
              client_type="webauthn.get", origin=ORIGIN, rp=RP, flags=0x05,
              counter=0, client_raw=None, auth_raw=None, signature=None):
    private = private or key()
    cred = credential()
    client_raw = client_raw if client_raw is not None else json.dumps({
        "type": client_type, "challenge": b64(ch.webauthn_challenge()),
        "origin": origin, "crossOrigin": False,
    }, separators=(",", ":")).encode()
    auth_raw = auth_raw if auth_raw is not None else hashlib.sha256(rp.encode()).digest() + bytes([flags]) + counter.to_bytes(4, "big")
    signature = signature if signature is not None else private.sign(
        auth_raw + hashlib.sha256(client_raw).digest(), ec.ECDSA(hashes.SHA256())
    )
    return P.OwnerAssertionV1.from_dict({
        "credentialRecordId": cred.record_id,
        "credentialId": credential_id or cred.credential_id,
        "clientDataJSON": b64(client_raw),
        "authenticatorData": b64(auth_raw),
        "signature": b64(signature),
    })


class OwnerProofCase(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"LILITH_ENV": "test"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = P.DurableOwnerChallengeStore(Path(self.tmp.name) / "owner-control.test.db")
        self.store.initialize()
        self.store.replace_synthetic_test_credential(credential())
        self.current_now = NOW
        self.verifier = P.OwnerProofVerifier(self.store, owner_principal=OWNER, rp_id=RP, origin=ORIGIN, test_mode=True, now_fn=lambda: self.current_now)

    def verify(self, ch=None, proof=None, a=None, *,
               item=None, restore_digest=None, notice="privacy.synthetic.v1"):
        ch = ch or challenge()
        a = a or action(ch.operation)
        proof = proof or assertion(ch)
        item = item if item is not None else ch.memory_item_id
        restore_digest = restore_digest if restore_digest is not None else ch.restore_target_digest
        return self.verifier.verify_and_consume(
            ch.challenge_id, proof, expected_action=a,
            expected_memory_item_id=item,
            expected_restore_target_digest=restore_digest,
            expected_privacy_notice_version=notice,
        )

    def test_valid_proof_is_only_observation_and_one_use(self):
        ch = challenge()
        self.store.prepare(ch)
        result = self.verify(ch)
        self.assertEqual(result.status, "VERIFIED_PROOF_ONLY")
        self.assertEqual(result.action_digest, action().action_digest)
        self.assertFalse(hasattr(result, "actor_evidence_ref_id"))
        self.assertEqual(self.store.state(ch.challenge_id), "CONSUMED")
        with self.assertRaises(P.OwnerProofError):
            self.verify(ch)

    def test_restart_persists_consumed_and_cancelled(self):
        ch = challenge()
        self.store.prepare(ch)
        self.verify(ch)
        reopened = P.DurableOwnerChallengeStore(self.store.path)
        self.assertEqual(reopened.state(ch.challenge_id), "CONSUMED")
        other = dataclasses.replace(ch, challenge_id="och.synthetic-cancel")
        reopened.prepare(other)
        reopened.cancel(other.challenge_id)
        self.assertEqual(P.DurableOwnerChallengeStore(self.store.path).state(other.challenge_id), "CANCELLED")
        with self.assertRaises(P.OwnerProofError):
            self.verify(other)

    def test_parallel_confirmation_consumes_only_once(self):
        ch = challenge()
        self.store.prepare(ch)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: self._attempt(ch), range(2)))
        self.assertEqual(sorted(outcomes), ["CHALLENGE_NOT_PREPARED", "VERIFIED_PROOF_ONLY"])
        self.assertEqual(self.store.state(ch.challenge_id), "CONSUMED")

    def _attempt(self, ch):
        try:
            return self.verify(ch).status
        except P.OwnerProofError as exc:
            return exc.code

    def test_expiry_is_durable_and_never_revives(self):
        ch = challenge()
        self.store.prepare(ch)
        self.current_now = datetime(2026, 9, 23, 12, 1, 0, tzinfo=timezone.utc)
        with self.assertRaisesRegex(P.OwnerProofError, "CHALLENGE_EXPIRED"):
            self.verify(ch)
        self.assertEqual(self.store.state(ch.challenge_id), "EXPIRED")
        with self.assertRaises(P.OwnerProofError):
            self.verify(ch)

    def test_wrong_credentials_and_public_key_cannot_sign(self):
        ch = challenge()
        self.store.prepare(ch)
        cases = (
            (credential(status="REVOKED"), assertion(ch)),
            (credential(owner="user:other@example.invalid"), assertion(ch)),
            (credential(), assertion(ch, credential_id=b64(b"TEST_ONLY_OTHER_CREDENTIAL_01"))),
            (credential(key(TEST_ONLY_PRIVATE_SCALAR + 1)), assertion(ch)),
            (credential(), assertion(ch, private=key(TEST_ONLY_PRIVATE_SCALAR + 1))),
        )
        for cred, proof in cases:
            with self.subTest(cred=cred.owner_principal, proof=proof.credential_id):
                self.store.replace_synthetic_test_credential(cred)
                with self.assertRaises(P.OwnerProofError):
                    self.verify(ch, proof)
                self.assertEqual(self.store.state(ch.challenge_id), "PREPARED")
        self.store.replace_synthetic_test_credential(credential())
        with self.assertRaises(P.OwnerProofError):
            self.store.replace_synthetic_test_credential(credential(rp="other.invalid"))
        unknown = dataclasses.replace(assertion(ch), credential_record_id="ocred.unknown")
        with self.assertRaisesRegex(P.OwnerProofError, "UNKNOWN_CREDENTIAL"):
            self.verify(ch, proof=unknown)
        with self.assertRaises(P.OwnerProofError):
            credential(algorithm=-257)

    def test_webauthn_adversarial(self):
        ch = challenge()
        self.store.prepare(ch)
        bad = (
            assertion(ch, client_type="webauthn.create"),
            assertion(ch, origin="https://wrong.invalid"),
            assertion(ch, rp="wrong.invalid"),
            assertion(ch, flags=0x04),
            assertion(ch, flags=0x01),
            assertion(ch, client_raw=b"not-json"),
            assertion(ch, client_raw=b'{"type":"webauthn.get","type":"webauthn.get"}'),
            assertion(ch, auth_raw=hashlib.sha256(RP.encode()).digest() + b"\x05\x00\x00\x00\x01trailing"),
            assertion(ch, signature=b"invalid"),
        )
        for proof in bad:
            with self.subTest(proof=proof):
                with self.assertRaises(P.OwnerProofError):
                    self.verify(ch, proof)
                self.assertEqual(self.store.state(ch.challenge_id), "PREPARED")
        with self.assertRaises(P.OwnerProofError):
            assertion(ch, auth_raw=b"short")

    def test_all_action_fields_bound(self):
        ch = challenge("RESTORE")
        self.store.prepare(ch)
        mutations = {
            "action_digest": "f" * 64,
            "payload_digest": "e" * 64,
            "operation": "SUPERSEDE",
            "memory_class": "OTHER_CLASS",
            "subject_namespace": "project.other",
            "subject_key": "other",
            "purpose": "OTHER_PURPOSE",
            "expected_active_revision_id": "mrev.other",
            "restore_revision_id": "mrev.other",
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                if field == "action_digest":
                    altered = dataclasses.replace(ch, action_digest=value)
                    with self.assertRaises(P.OwnerProofError):
                        self.verify(ch, proof=assertion(altered))
                else:
                    altered_action = dataclasses.replace(action("RESTORE"), **{field: value})
                    with self.assertRaises((P.OwnerProofError, C.ContractError)):
                        self.verify(ch, a=altered_action)
        for field, value in (
            ("memory_item_id", "mitem.other"),
            ("restore_target_digest", "a" * 64),
            ("privacy_notice_version", "privacy.other"),
            ("nonce", b64(b"X" * 32)),
            ("issued_at", "2026-09-23T12:00:01Z"),
            ("expires_at", "2026-09-23T12:00:59Z"),
        ):
            with self.subTest(field=field):
                altered = dataclasses.replace(ch, **{field: value})
                with self.assertRaises(P.OwnerProofError):
                    self.verify(ch, proof=assertion(altered))
        with self.assertRaises(P.OwnerProofError):
            self.verify(ch, item="mitem.other")
        with self.assertRaises(P.OwnerProofError):
            self.verify(ch, restore_digest="b" * 64)
        with self.assertRaises(P.OwnerProofError):
            self.verify(ch, notice="privacy.other")

    def test_forged_caller_fields_do_not_authorize(self):
        ch = challenge()
        self.store.prepare(ch)
        proof = assertion(ch)
        for extra in ({"verified": True}, {"actor": "local-owner"}, {"unixUid": 476420618}, {"modelText": "remember this"}):
            with self.assertRaises(P.OwnerProofError):
                P.OwnerAssertionV1.from_dict({
                    "credentialRecordId": proof.credential_record_id,
                    "credentialId": proof.credential_id,
                    "clientDataJSON": proof.client_data_json,
                    "authenticatorData": proof.authenticator_data,
                    "signature": proof.signature,
                    **extra,
                })
        with self.assertRaises(P.OwnerProofError):
            self.verify(ch, proof=dataclasses.replace(proof, credential_record_id=""))
        self.assertEqual(self.store.state(ch.challenge_id), "PREPARED")

    def test_counter_is_evidence_not_replay_control(self):
        ch = challenge()
        self.store.prepare(ch)
        self.store.replace_synthetic_test_credential(credential(last_count=5))
        result = self.verify(ch, proof=assertion(ch, counter=0))
        self.assertFalse(result.counter_risk)
        other = dataclasses.replace(ch, challenge_id="och.synthetic-counter")
        self.store.prepare(other)
        result = self.verify(other, proof=assertion(other, counter=4))
        self.assertTrue(result.counter_risk)
        third = dataclasses.replace(ch, challenge_id="och.synthetic-counter-next")
        self.store.prepare(third)
        result = self.verify(third, proof=assertion(third, counter=6))
        self.assertFalse(result.counter_risk)
        conn = sqlite3.connect(self.store.path)
        try:
            raw = conn.execute("SELECT credential_json FROM owner_proof_test_credential_v1 WHERE record_id=?", ("ocred.synthetic",)).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(json.loads(raw)["lastObservedSignCount"], 6)

    def test_synthetic_rp_rejected_outside_test(self):
        with patch.dict(os.environ, {"LILITH_ENV": "prod"}):
            with self.assertRaisesRegex(P.OwnerProofError, "SYNTHETIC_RP_FORBIDDEN"):
                P.OwnerProofVerifier(self.store, owner_principal=OWNER, rp_id=RP, origin=ORIGIN, test_mode=True)
        with patch.dict(os.environ, {"LILITH_ENV": "test"}):
            with self.assertRaisesRegex(P.OwnerProofError, "SYNTHETIC_RP_FORBIDDEN"):
                P.OwnerProofVerifier(self.store, owner_principal=OWNER, rp_id=RP, origin=ORIGIN)
        ch = challenge()
        self.store.prepare(ch)
        with patch.dict(os.environ, {"LILITH_ENV": "prod"}):
            with self.assertRaisesRegex(P.OwnerProofError, "SYNTHETIC_RP_FORBIDDEN"):
                self.verify(ch)
            with self.assertRaisesRegex(P.OwnerProofError, "TEST_CREDENTIAL_INSTALL_FORBIDDEN"):
                self.store.replace_synthetic_test_credential(credential())

    def test_closed_schema_and_lifetime(self):
        valid = challenge().to_dict()
        for changed in (
            {**valid, "unexpected": True},
            {key: value for key, value in valid.items() if key != "nonce"},
            {**valid, "schemaVersion": 2},
            {**valid, "nonce": "bad"},
            {**valid, "expiresAt": valid["issuedAt"]},
            {**valid, "expiresAt": "2026-09-23T12:02:00Z"},
            {**valid, "issuedAt": "not-time"},
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(P.OwnerProofError):
                    P.OwnerMemoryChallengeV1.from_dict(changed)

    def test_golden_vectors(self):
        expected = {
            "CREATE": ("f762bbecc8bd9937e7f2474b1891786b1b0f24a838a4bfe84360857a525e864a", "01606536f41781a60bfea4849a92e39790cc9721e22ebd1f90fff5dde3aef6b5"),
            "SUPERSEDE": ("1e727047338000f873262b6ddf5b259a4673cd3619f4ac33dcd385c31a48c625", "705c5f7f40b856e2f4a4b8250ce3ec7abadaacd3b1d27440d60b9785c5e77638"),
            "RESTORE": ("4b733259a726f2c9864a2a4d2974e559b7410b3ac7327515eac6b9ff46e0a975", "ae45386cb0159c0a13a2dddfbd600a77529cf15cb5d4dfec943517360b657858"),
            "FORGET": ("f7fe26056b5edffb046a0aad6ec9fbbc750911156ea781bcf803778ca5691115", "fad5e93d2be6c4cfe928e82346d77213e67a1cff83ac429a81ba9be7d1351bae"),
        }
        lines = (Path(__file__).parent / "owner_proof_golden.jsonl").read_bytes().splitlines()
        vector_bytes = {json.loads(line)["operation"]: line for line in lines}
        self.assertEqual(set(vector_bytes), set(expected))
        for operation in ("CREATE", "SUPERSEDE", "RESTORE", "FORGET"):
            ch = challenge(operation)
            self.assertEqual(ch.canonical_bytes(), P.OwnerMemoryChallengeV1.from_dict(dict(reversed(list(ch.to_dict().items())))).canonical_bytes())
            self.assertEqual(ch.canonical_bytes(), vector_bytes[operation])
            self.assertEqual(hashlib.sha256(ch.canonical_bytes()).hexdigest(), expected[operation][0])
            self.assertEqual(ch.webauthn_challenge().hex(), expected[operation][1])

    def test_no_canonical_db_access(self):
        with self.assertRaisesRegex(P.OwnerProofError, "GOVERNED_DATABASE_FORBIDDEN"):
            P.DurableOwnerChallengeStore(Path(self.tmp.name) / "cognitive_memory.db")
        conn = sqlite3.connect(self.store.path)
        try:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            conn.close()
        self.assertEqual(tables, {"owner_proof_challenge_v1", "owner_proof_test_credential_v1"})

    def test_stored_challenge_must_be_canonical_and_id_bound(self):
        ch = challenge()
        self.store.prepare(ch)
        conn = sqlite3.connect(self.store.path)
        try:
            conn.execute("UPDATE owner_proof_challenge_v1 SET challenge_json=? WHERE challenge_id=?", (json.dumps(ch.to_dict()).encode(), ch.challenge_id))
            conn.commit()
        finally:
            conn.close()
        with self.assertRaisesRegex(P.OwnerProofError, "NONCANONICAL_STORED_CHALLENGE"):
            self.verify(ch)
        with self.assertRaisesRegex(P.OwnerProofError, "UNKNOWN_CHALLENGE"):
            self.verifier.verify_and_consume(
                "och.unknown", assertion(ch), expected_action=action(),
                expected_memory_item_id=None, expected_restore_target_digest=None,
                expected_privacy_notice_version="privacy.synthetic.v1",
            )


if __name__ == "__main__":
    unittest.main()
