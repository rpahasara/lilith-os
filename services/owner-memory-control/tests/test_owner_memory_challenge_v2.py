"""15B2b-B2a OwnerMemoryChallengeV2 and evidence-envelope contracts (TEST_ONLY)."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

import synthetic_chain as S
from lilith_memory import owner_proof as P
from lilith_owner_memory import contracts as K

GOLDEN = json.loads((Path(__file__).with_name("owner_memory_b2a_golden.json")).read_text(encoding="utf-8"))
V1_GOLDEN = S.ROOT / "services/core-api/tests/owner_proof_golden.jsonl"


class ChallengeV2GoldenTests(unittest.TestCase):
    def test_challenge_v2_golden_vectors_are_reproduced(self):
        self.assertEqual([v["operation"] for v in GOLDEN["challengeV2"]], ["CREATE", "SUPERSEDE", "RESTORE", "FORGET"])
        for vector in GOLDEN["challengeV2"]:
            with self.subTest(operation=vector["operation"]):
                challenge = K.OwnerMemoryChallengeV2.from_dict(S.challenge_dict(S.action(vector["operation"])))
                self.assertEqual(challenge.canonical_bytes().decode("utf-8"), vector["canonicalBytes"])
                self.assertEqual(challenge.webauthn_challenge().hex(), vector["webauthnChallengeSha256"])
                self.assertEqual(
                    hashlib.sha256(K.CHALLENGE_V2_DOMAIN_SEPARATOR + vector["canonicalBytes"].encode()).hexdigest(),
                    vector["webauthnChallengeSha256"])
                self.assertEqual(challenge.challenge_digest(), vector["webauthnChallengeSha256"])

    def test_evidence_golden_vector_is_deterministic_and_verifies(self):
        vector = GOLDEN["evidenceV1"][0]
        envelope = K.BrokerMemoryEvidenceEnvelopeV1.from_dict(vector["envelope"])
        self.assertEqual(envelope.evidence_digest(), vector["evidenceDigest"])
        public = Ed25519PublicKey.from_public_bytes(
            P._b64u_decode(vector["brokerPublicKey"], "public_key", 32, 32))
        public.verify(envelope.signature, envelope.signing_bytes())
        unsigned = {k: v for k, v in vector["envelope"].items() if k != "signature"}
        self.assertEqual(S.sign_evidence(unsigned), vector["envelope"])  # Ed25519 is deterministic

    def test_canonical_bytes_are_key_order_independent(self):
        value = S.challenge_dict(S.action())
        reordered = dict(reversed(list(value.items())))
        self.assertEqual(K.OwnerMemoryChallengeV2.from_dict(value).canonical_bytes(),
                         K.OwnerMemoryChallengeV2.from_dict(reordered).canonical_bytes())


class V1ImmutabilityTests(unittest.TestCase):
    def test_v1_constants_and_golden_vectors_are_unchanged(self):
        self.assertEqual(P.DOMAIN_SEPARATOR, b"LILITH_OWNER_MEMORY_CHALLENGE_V1\x00")
        self.assertEqual(P.SCHEMA_VERSION, 1)
        # Byte-exact V1 golden file as accepted on protected main.
        self.assertEqual(hashlib.sha256(V1_GOLDEN.read_bytes()).hexdigest(),
                         "e810a36be8d9a0f3233a174a5ddf4e33eafb4671d110abdfe503ded3d330d390")
        webauthn = {  # V1 expectations copied from services/core-api/tests/test_owner_proof.py
            "CREATE": "4315f79cabab0baa730379c7af273e2219174a72d19663260934ba9eb1eb61b4",
            "SUPERSEDE": "ff5322ed9351be77f8eb1d69fe2a6d91d20bddbdf88e5dac6c77a77cd11ab15b",
            "RESTORE": "562ac19384eed7db38eee29fe7749a497d18fff5e01db82e4eb2f5215e5d911c",
            "FORGET": "ff60120c401c14bd7907adf93c7cd9944a5ee6e51176bf9f0d71145aedcb553a",
        }
        for line in V1_GOLDEN.read_bytes().splitlines():
            challenge = P.OwnerMemoryChallengeV1.from_dict(json.loads(line))
            self.assertEqual(challenge.canonical_bytes(), line)
            self.assertEqual(challenge.webauthn_challenge().hex(), webauthn[challenge.operation])

    def test_v2_has_its_own_version_and_domain_separator(self):
        self.assertEqual(K.CHALLENGE_V2_SCHEMA_VERSION, 2)
        self.assertEqual(K.CHALLENGE_V2_DOMAIN_SEPARATOR, b"LILITH_OWNER_MEMORY_CHALLENGE_V2\x00")
        self.assertNotEqual(K.CHALLENGE_V2_DOMAIN_SEPARATOR, P.DOMAIN_SEPARATOR)

    def test_v1_and_v2_never_interchange(self):
        v2 = S.challenge_dict(S.action())
        with self.assertRaises(P.OwnerProofError) as caught:
            P.OwnerMemoryChallengeV1.from_dict(v2)
        self.assertEqual(caught.exception.code, "INVALID_FIELDS")
        v1 = {k: v2[k] for k in P._CHALLENGE_FIELDS}
        v1["schemaVersion"] = 1
        with self.assertRaises(K.ContractViolation) as caught:
            K.OwnerMemoryChallengeV2.from_dict(v1)
        self.assertEqual(caught.exception.code, "UNSUPPORTED_SCHEMA_VERSION")
        same_shared_v1 = P.OwnerMemoryChallengeV1.from_dict(v1)
        self.assertNotEqual(same_shared_v1.webauthn_challenge(),
                            K.OwnerMemoryChallengeV2.from_dict(v2).webauthn_challenge())


class ChallengeV2FieldSetTests(unittest.TestCase):
    def test_exact_field_set_is_v1_plus_logical_authority_context(self):
        extras = {"deploymentEnvironment", "authorityDomain", "logicalOwnerId",
                  "policyVersion", "registryTupleVersion", "ledgerEpoch"}
        self.assertEqual(K.CHALLENGE_V2_FIELDS, P._CHALLENGE_FIELDS | extras)
        self.assertEqual(len(K.CHALLENGE_V2_FIELDS), 27)

    def test_no_host_broker_key_or_charter_binding(self):
        lowered = {name.lower() for name in K.CHALLENGE_V2_FIELDS}
        for fragment in ("host", "instance", "machine", "brokerkey", "charter"):
            self.assertFalse(any(fragment in name for name in lowered), fragment)
        for name in ("vmId", "vmName", "brokerPid", "processId", "brokerKeyId", "identityCharterRef",
                     "lilithIdentityId"):
            self.assertNotIn(name, K.CHALLENGE_V2_FIELDS)
        self.assertIn("brokerKeyId", K.EVIDENCE_FIELDS)

    def test_unknown_missing_and_version_mutations_are_rejected(self):
        base = S.challenge_dict(S.action())
        cases = {
            "extra": ({**base, "brokerKeyId": "bkey.synthetic-1"}, "INVALID_FIELDS"),
            "missing": ({k: v for k, v in base.items() if k != "ledgerEpoch"}, "INVALID_FIELDS"),
            "schema3": ({**base, "schemaVersion": 3}, "UNSUPPORTED_SCHEMA_VERSION"),
            "bool-version": ({**base, "schemaVersion": True}, "UNSUPPORTED_SCHEMA_VERSION"),
            "protocol": ({**base, "protocol": "OTHER"}, "UNSUPPORTED_SCHEMA_VERSION"),
            "environment": ({**base, "deploymentEnvironment": "staging"}, "INVALID_DEPLOYMENT_ENVIRONMENT"),
            "owner": ({**base, "logicalOwnerId": "ravindu"}, "INVALID_LOGICAL_OWNER_ID"),
            "domain": ({**base, "authorityDomain": ""}, "INVALID_AUTHORITY_DOMAIN"),
            "epoch": ({**base, "ledgerEpoch": "has space"}, "INVALID_LEDGER_EPOCH"),
            "lifetime": ({**base, "expiresAt": "2026-09-26T12:05:00Z"}, "INVALID_LIFETIME"),
            "shape": ({**base, "memoryItemId": "mitem.x"}, "INVALID_ACTION_SHAPE"),
        }
        for name, (value, code) in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(P.OwnerProofError) as caught:
                    K.OwnerMemoryChallengeV2.from_dict(value)
                self.assertEqual(caught.exception.code, code)


class EvidenceEnvelopeContractTests(unittest.TestCase):
    def setUp(self):
        self.signed = GOLDEN["evidenceV1"][0]["envelope"]

    def test_envelope_rejects_unknown_missing_and_versions(self):
        cases = {
            "extra": {**self.signed, "acceptanceStatus": "ACCEPTED"},
            "missing": {k: v for k, v in self.signed.items() if k != "brokerKeyId"},
            "release": {**self.signed, "brokerRelease": "not-a-sha"},
            "signature": {**self.signed, "signature": "AAAA"},
        }
        for name, value in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(P.OwnerProofError):
                    K.BrokerMemoryEvidenceEnvelopeV1.from_dict(value)
        with self.assertRaises(K.ContractViolation) as caught:
            K.BrokerMemoryEvidenceEnvelopeV1.from_dict({**self.signed, "schemaVersion": 2})
        self.assertEqual(caught.exception.code, "UNSUPPORTED_SCHEMA_VERSION")

    def test_every_signed_field_changes_the_signing_bytes(self):
        envelope = K.BrokerMemoryEvidenceEnvelopeV1.from_dict(self.signed)
        for name in sorted(K.EVIDENCE_SIGNED_FIELDS - {"protocol", "schemaVersion"}):
            with self.subTest(field=name):
                changed = dict(envelope.fields)
                value = changed[name]
                changed[name] = ("f" * 64 if len(value) == 64 else "e" * 40 if len(value) == 40
                                 else "2026-09-26T12:00:22Z" if name == "issuedAt"
                                 else "prod" if name == "deploymentEnvironment"
                                 else "owner.other.v1" if name == "logicalOwnerId"
                                 else "INFERRED" if name == "epistemicBasis" else value + ".x")
                self.assertNotEqual(K.evidence_signing_bytes(changed), envelope.signing_bytes())


if __name__ == "__main__":
    unittest.main()
