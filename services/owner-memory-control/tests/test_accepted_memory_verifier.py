"""15B2b-B2a accepted-memory verifier: positive path, forbidden equalities,
tamper/forgery matrix, memory != truth, and runtime independence (TEST_ONLY)."""

from __future__ import annotations

import inspect
import json
import unittest
from pathlib import Path

import synthetic_chain as S
from lilith_memory import owner_proof as P
from lilith_owner_memory import contracts as K
from lilith_owner_memory import verifier as V

OTHER = "f" * 64


def verify(chain: S.Chain, **replace):
    return V.verify_accepted_memory(**chain.kwargs(**replace))


def rebuilt_challenge(chain: S.Chain, **fields) -> bytes:
    """Mutate the owner challenge AFTER signing; assertion/evidence stay original."""
    return K.OwnerMemoryChallengeV2.from_dict({**chain.challenge.fields, **fields}).canonical_bytes()


def resigned(chain: S.Chain, signer=None, **fields) -> dict:
    unsigned = {k: v for k, v in chain.evidence.items() if k != "signature"}
    return S.sign_evidence({**unsigned, **fields}, signer)


def tampered(chain: S.Chain, **fields) -> dict:
    """Change signed evidence fields WITHOUT re-signing."""
    return {**chain.evidence, **fields}


# (name, callable returning a result, expected NOT_ACCEPTED reason)
CASES = [
    # Environment / context
    ("context-not-test", lambda: verify(S.Chain(), context=S.context(deployment_environment="dev")), "ENVIRONMENT_NOT_SUPPORTED"),
    ("context-real-rp", lambda: verify(S.Chain(), context=S.context(rp_id="owner.example.com", origin="https://owner.example.com")), "ENVIRONMENT_NOT_SUPPORTED"),
    ("context-not-a-context", lambda: verify(S.Chain(), context={"deploymentEnvironment": "test"}), "MALFORMED_ARTIFACT"),
    # Intended operation
    ("action-missing", lambda: verify(S.Chain(), action=None), "ACTION_MISSING"),
    ("action-is-model-text", lambda: verify(S.Chain(), action="The owner wants me to remember this."), "MALFORMED_ARTIFACT"),
    ("forget-is-privacy-owned", lambda: verify(S.Chain(), action=S.action("FORGET")), "OPERATION_NOT_SUPPORTED"),
    # Owner proof presence and form
    ("missing-owner-assertion", lambda: verify(S.Chain(), assertion=None), "OWNER_PROOF_MISSING"),
    ("missing-challenge", lambda: verify(S.Chain(), challenge_json=None), "OWNER_PROOF_MISSING"),
    ("missing-owner-credential", lambda: verify(S.Chain(), owner_credential=None), "OWNER_PROOF_MISSING"),
    ("noncanonical-challenge-bytes", lambda: verify(S.Chain(), challenge_json=json.dumps(S.Chain().challenge.to_dict(), indent=1).encode()), "MALFORMED_ARTIFACT"),
    ("duplicate-key-challenge", lambda: verify(S.Chain(), challenge_json=b'{"protocol":"x","protocol":"y"}'), "MALFORMED_ARTIFACT"),
    ("non-json-challenge", lambda: verify(S.Chain(), challenge_json=b"\xff\xfe"), "MALFORMED_ARTIFACT"),
    ("v1-challenge-rejected", lambda: verify(S.Chain(), challenge_json=P.OwnerMemoryChallengeV1.from_dict({**{k: S.Chain().challenge[k] for k in P._CHALLENGE_FIELDS}, "schemaVersion": 1}).canonical_bytes()), "UNSUPPORTED_SCHEMA_VERSION"),
    # Challenge vs trusted context (cross-owner / cross-environment substitution)
    ("wrong-rp", lambda: verify(S.Chain(challenge_overrides={"rpId": "other.lilith.invalid"})), "RP_MISMATCH"),
    ("wrong-logical-owner", lambda: verify(S.Chain(challenge_overrides={"logicalOwnerId": "owner.other.v1"})), "LOGICAL_OWNER_MISMATCH"),
    ("cross-owner-context", lambda: verify(S.Chain(), context=S.context(logical_owner_id="owner.other.v1")), "LOGICAL_OWNER_MISMATCH"),
    ("wrong-owner-principal", lambda: verify(S.Chain(challenge_overrides={"ownerPrincipal": "user:other@example.invalid"})), "LOGICAL_OWNER_MISMATCH"),
    ("wrong-authority-domain", lambda: verify(S.Chain(challenge_overrides={"authorityDomain": "authority.other"})), "AUTHORITY_DOMAIN_MISMATCH"),
    ("wrong-deployment-environment", lambda: verify(S.Chain(challenge_overrides={"deploymentEnvironment": "dev"})), "DEPLOYMENT_ENVIRONMENT_MISMATCH"),
    ("prod-authorization-in-test", lambda: verify(S.Chain(challenge_overrides={"deploymentEnvironment": "prod"})), "DEPLOYMENT_ENVIRONMENT_MISMATCH"),
    ("wrong-policy-version", lambda: verify(S.Chain(challenge_overrides={"policyVersion": "policy.other.v1"})), "POLICY_VERSION_MISMATCH"),
    ("wrong-registry-version", lambda: verify(S.Chain(challenge_overrides={"registryTupleVersion": "registry.other.v1"})), "REGISTRY_VERSION_MISMATCH"),
    ("wrong-ledger-epoch", lambda: verify(S.Chain(challenge_overrides={"ledgerEpoch": "e" * 32})), "LEDGER_EPOCH_MISMATCH"),
    ("stale-epoch-after-ledger-restore", lambda: verify(S.Chain(), context=S.context(ledger_epoch="d" * 32)), "LEDGER_EPOCH_MISMATCH"),
    ("wrong-privacy-notice", lambda: verify(S.Chain(challenge_overrides={"privacyNoticeVersion": "privacy.other.v1"})), "PRIVACY_NOTICE_MISMATCH"),
    # Challenge vs intended action
    ("wrong-operation", lambda: verify(S.Chain(challenge_overrides={"operation": "FORGET"})), "OPERATION_MISMATCH"),
    ("wrong-memory-class", lambda: verify(S.Chain(challenge_overrides={"memoryClass": "OTHER_CLASS"})), "MEMORY_IDENTITY_MISMATCH"),
    ("wrong-namespace", lambda: verify(S.Chain(challenge_overrides={"subjectNamespace": "project.other"})), "MEMORY_IDENTITY_MISMATCH"),
    ("wrong-subject-key", lambda: verify(S.Chain(challenge_overrides={"subjectKey": "other"})), "MEMORY_IDENTITY_MISMATCH"),
    ("wrong-expected-revision", lambda: verify(S.Chain("SUPERSEDE", challenge_overrides={"expectedActiveRevisionId": "mrev.other"})), "MEMORY_IDENTITY_MISMATCH"),
    ("mutated-payload", lambda: verify(S.Chain(action_overrides={"payload_digest": OTHER})), "PAYLOAD_DIGEST_MISMATCH"),
    ("payload-digest-mismatch", lambda: verify(S.Chain(challenge_overrides={"payloadDigest": OTHER})), "PAYLOAD_DIGEST_MISMATCH"),
    ("action-digest-mismatch", lambda: verify(S.Chain(action_overrides={"actor_ref_id": "actor.other"})), "ACTION_DIGEST_MISMATCH"),
    ("challenge-action-digest-substituted", lambda: verify(S.Chain(challenge_overrides={"actionDigest": OTHER})), "ACTION_DIGEST_MISMATCH"),
    # Durable challenge state (replay / consumption)
    ("challenge-state-missing", lambda: verify(S.Chain(), challenge_record=None), "CHALLENGE_STATE_MISSING"),
    ("ledger-record-other-challenge", lambda: verify(S.Chain(record_overrides={"challengeId": "och.other"})), "CHALLENGE_LEDGER_MISMATCH"),
    ("ledger-record-other-epoch", lambda: verify(S.Chain(record_overrides={"ledgerEpoch": "c" * 32})), "CHALLENGE_LEDGER_MISMATCH"),
    ("consumed-by-other-credential", lambda: verify(S.Chain(record_overrides={"consumedCredentialRecordId": "ocred.other"})), "CHALLENGE_LEDGER_MISMATCH"),
    ("challenge-prepared-not-consumed", lambda: verify(S.Chain(record_overrides={"state": "PREPARED", "consumedCredentialRecordId": None, "consumedAt": None})), "CHALLENGE_NOT_CONSUMED"),
    ("challenge-cancelled", lambda: verify(S.Chain(record_overrides={"state": "CANCELLED", "consumedCredentialRecordId": None, "consumedAt": None})), "CHALLENGE_NOT_CONSUMED"),
    ("challenge-expired-state", lambda: verify(S.Chain(record_overrides={"state": "EXPIRED", "consumedCredentialRecordId": None, "consumedAt": None})), "CHALLENGE_NOT_CONSUMED"),
    ("consumed-before-issue", lambda: verify(S.Chain(record_overrides={"consumedAt": "2026-09-26T11:59:59Z"})), "CHALLENGE_NOT_YET_VALID"),
    ("expired-challenge", lambda: verify(S.Chain(record_overrides={"consumedAt": "2026-09-26T12:01:00Z"})), "CHALLENGE_EXPIRED"),
    ("malformed-ledger-record", lambda: verify(S.Chain(record_overrides={"state": "CONSUMED", "consumedAt": None})), "MALFORMED_ARTIFACT"),
    # Owner credential and signature
    ("assertion-credential-mismatch", lambda: verify(S.Chain(assertion_options={"credential_id": S.b64(b"TEST_ONLY_OTHER_CREDENTIAL")})), "OWNER_CREDENTIAL_MISMATCH"),
    ("credential-other-owner", lambda: verify(S.Chain(credential_overrides={"ownerPrincipal": "user:other@example.invalid"})), "OWNER_CREDENTIAL_NOT_AUTHORIZED"),
    ("credential-other-rp", lambda: verify(S.Chain(credential_overrides={"rpId": "other.lilith.invalid"})), "OWNER_CREDENTIAL_NOT_AUTHORIZED"),
    ("credential-revoked-before-use", lambda: verify(S.Chain(credential_overrides={"status": "REVOKED", "revokedAt": "2026-09-26T12:00:10Z"})), "OWNER_CREDENTIAL_REVOKED"),
    ("credential-bad-algorithm", lambda: verify(S.Chain(credential_overrides={"algorithm": -8})), "MALFORMED_ARTIFACT"),
    ("invalid-owner-signature", lambda: verify(S.Chain(signing_owner=S.owner_key(S.TEST_ONLY_ATTACKER_SCALAR))), "OWNER_SIGNATURE_INVALID"),
    ("wrong-owner-credential-key", lambda: verify(S.Chain(), owner_credential=S.credential_dict(S.owner_key(S.TEST_ONLY_ATTACKER_SCALAR))), "OWNER_SIGNATURE_INVALID"),
    ("user-verification-absent", lambda: verify(S.Chain(assertion_options={"flags": 0x01})), "OWNER_SIGNATURE_INVALID"),
    ("wrong-origin", lambda: verify(S.Chain(assertion_options={"origin": "https://evil.lilith.invalid"})), "OWNER_SIGNATURE_INVALID"),
    ("wrong-rp-hash", lambda: verify(S.Chain(assertion_options={"rp": "evil.lilith.invalid"})), "OWNER_SIGNATURE_INVALID"),
    ("create-type-not-get", lambda: verify(S.Chain(assertion_options={"client_type": "webauthn.create"})), "OWNER_SIGNATURE_INVALID"),
    ("challenge-mutated-after-signing", lambda: (lambda c: verify(c, challenge_json=rebuilt_challenge(c, nonce=S.b64(bytes(range(1, 33))))))(S.Chain()), "OWNER_SIGNATURE_INVALID"),
    # Broker evidence
    ("missing-broker-evidence", lambda: verify(S.Chain(), evidence=None), "BROKER_EVIDENCE_MISSING"),
    ("unknown-broker-key-id", lambda: verify(S.Chain(evidence_overrides={"brokerKeyId": "bkey.unknown"})), "BROKER_KEY_UNKNOWN"),
    ("no-trusted-broker-keys", lambda: verify(S.Chain(), broker_keys=[]), "BROKER_KEY_UNKNOWN"),
    ("broker-key-other-environment", lambda: verify(S.Chain(), broker_keys=[S.broker_key_dict(deploymentEnvironment="prod")]), "BROKER_KEY_SCOPE_MISMATCH"),
    ("broker-key-other-domain", lambda: verify(S.Chain(), broker_keys=[S.broker_key_dict(authorityDomain="authority.other")]), "BROKER_KEY_SCOPE_MISMATCH"),
    ("wrong-broker-signature", lambda: verify(S.Chain(evidence_signer=S.broker_key(S.TEST_ONLY_BROKER_SEED_2))), "BROKER_SIGNATURE_INVALID"),
    ("substituted-broker-release", lambda: (lambda c: verify(c, evidence=tampered(c, brokerRelease="e" * 40)))(S.Chain()), "BROKER_SIGNATURE_INVALID"),
    ("substituted-evidence-payload-unsigned", lambda: (lambda c: verify(c, evidence=tampered(c, payloadDigest=OTHER)))(S.Chain()), "BROKER_SIGNATURE_INVALID"),
    ("broker-key-revoked-before-issue", lambda: verify(S.Chain(), broker_keys=[S.broker_key_dict(status="REVOKED", revokedAt="2026-09-26T12:00:00Z")]), "BROKER_KEY_REVOKED"),
    ("broker-release-not-allowed", lambda: (lambda c: verify(c, evidence=resigned(c, brokerRelease="e" * 40)))(S.Chain()), "BROKER_RELEASE_NOT_ALLOWED"),
    ("evidence-nonce-substitution", lambda: verify(S.Chain(evidence_overrides={"evidenceNonce": "och.other"})), "EVIDENCE_NONCE_MISMATCH"),
    ("evidence-bound-to-other-challenge", lambda: verify(S.Chain(evidence_overrides={"challengeDigest": OTHER})), "EVIDENCE_CHALLENGE_MISMATCH"),
    ("evidence-replayed-from-other-chain", lambda: verify(S.Chain(), evidence=S.Chain("SUPERSEDE").evidence), "EVIDENCE_NONCE_MISMATCH"),
    ("evidence-other-owner-proof", lambda: verify(S.Chain(evidence_overrides={"assertionDigest": OTHER})), "EVIDENCE_OWNER_PROOF_MISMATCH"),
    ("evidence-other-credential", lambda: verify(S.Chain(evidence_overrides={"credentialRecordId": "ocred.other"})), "EVIDENCE_OWNER_PROOF_MISMATCH"),
    ("request-digest-mismatch", lambda: verify(S.Chain(evidence_overrides={"requestDigest": OTHER})), "REQUEST_DIGEST_MISMATCH"),
    ("evidence-bound-to-other-payload", lambda: verify(S.Chain(evidence_overrides={"payloadDigest": OTHER})), "EVIDENCE_BINDING_MISMATCH"),
    ("evidence-other-policy", lambda: verify(S.Chain(evidence_overrides={"policyVersion": "policy.other.v1"})), "EVIDENCE_BINDING_MISMATCH"),
    ("evidence-cross-environment-with-matching-key", lambda: verify(S.Chain(evidence_overrides={"deploymentEnvironment": "prod"}), broker_keys=[S.broker_key_dict(deploymentEnvironment="prod")]), "EVIDENCE_BINDING_MISMATCH"),
    ("evidence-issued-before-consumption", lambda: verify(S.Chain(evidence_overrides={"issuedAt": "2026-09-26T12:00:19Z"})), "EVIDENCE_ORDER_INVALID"),
    ("evidence-unknown-field", lambda: (lambda c: verify(c, evidence={**c.evidence, "ownerAuthorized": True}))(S.Chain()), "MALFORMED_ARTIFACT"),
    ("evidence-future-schema", lambda: (lambda c: verify(c, evidence={**c.evidence, "schemaVersion": 2}))(S.Chain()), "UNSUPPORTED_SCHEMA_VERSION"),
    # L04 admission / apply evidence and provenance
    ("missing-admission-evidence", lambda: verify(S.Chain(), admission=None), "ADMISSION_EVIDENCE_MISSING"),
    ("admission-rejected", lambda: verify(S.Chain(admission_overrides={"admissionOutcome": "REJECTED", "applyAuditId": None})), "ADMISSION_NOT_ACCEPTED"),
    ("admission-precondition-failed", lambda: verify(S.Chain(admission_overrides={"admissionOutcome": "PRECONDITION_FAILED", "applyAuditId": None})), "ADMISSION_NOT_ACCEPTED"),
    ("admission-other-evidence", lambda: verify(S.Chain(admission_overrides={"brokerEvidenceId": "bev.other"})), "ADMISSION_BINDING_MISMATCH"),
    ("admission-other-payload", lambda: verify(S.Chain(admission_overrides={"payloadDigest": OTHER})), "ADMISSION_BINDING_MISMATCH"),
    ("admission-other-item-on-supersede", lambda: verify(S.Chain("SUPERSEDE", admission_overrides={"memoryItemId": "mitem.other"})), "ADMISSION_BINDING_MISMATCH"),
    ("altered-provenance-proposal", lambda: verify(S.Chain(admission_overrides={"proposalRefId": "proposal-ref.other"})), "PROVENANCE_MISMATCH"),
    ("altered-provenance-epistemic-upgrade", lambda: verify(S.Chain(admission_overrides={"epistemicBasis": "OBSERVED"})), "PROVENANCE_MISMATCH"),
    ("orphan-database-row", lambda: verify(S.Chain(), evidence=None, admission=S.Chain().admission), "BROKER_EVIDENCE_MISSING"),
    ("forged-acceptance-cache-field", lambda: (lambda c: verify(c, admission={**c.admission, "acceptanceStatus": "accepted"}))(S.Chain()), "MALFORMED_ARTIFACT"),
    ("admission-future-schema", lambda: (lambda c: verify(c, admission={**c.admission, "schemaVersion": 2}))(S.Chain()), "UNSUPPORTED_SCHEMA_VERSION"),
]


class PositivePathTests(unittest.TestCase):
    def test_complete_chain_is_accepted_for_each_admission_operation(self):
        for operation in ("CREATE", "SUPERSEDE", "RESTORE"):
            with self.subTest(operation=operation):
                result = verify(S.Chain(operation))
                self.assertEqual((result.status, result.reason), (V.ACCEPTED_MEMORY, None))
                self.assertTrue(result.accepted)
                self.assertEqual(result.facts["operation"], operation)
                self.assertEqual(result.facts["challengeDigest"], S.Chain(operation).challenge.challenge_digest())
                self.assertEqual(result.facts["brokerKeyId"], S.BROKER_KEY_ID)

    def test_revocation_after_authorization_is_reported_not_retroactive(self):
        chain = S.Chain(credential_overrides={"status": "REVOKED", "revokedAt": "2026-09-26T12:30:00Z"})
        result = verify(chain, broker_keys=[S.broker_key_dict(status="REVOKED", revokedAt="2026-09-26T12:30:00Z")])
        self.assertTrue(result.accepted, result.reason)
        self.assertEqual(result.facts["ownerCredentialStatus"], "REVOKED_AFTER_AUTHORIZATION")
        self.assertEqual(result.facts["brokerKeyStatus"], "REVOKED_AFTER_ISSUANCE")

    def test_broker_key_rotation_does_not_touch_owner_authorization(self):
        rotated = S.broker_key(S.TEST_ONLY_BROKER_SEED_2)
        chain = S.Chain(evidence_overrides={"brokerKeyId": "bkey.synthetic-2"}, evidence_signer=rotated)
        keys = [S.broker_key_dict(), S.broker_key_dict(rotated, brokerKeyId="bkey.synthetic-2")]
        result = verify(chain, broker_keys=keys)
        self.assertTrue(result.accepted, result.reason)
        self.assertEqual(result.facts["challengeDigest"], S.Chain().challenge.challenge_digest())

    def test_result_is_deterministic(self):
        chain = S.Chain()
        self.assertEqual(verify(chain), verify(chain))


class TamperMatrixTests(unittest.TestCase):
    def test_every_tamper_case_is_not_accepted_with_the_exact_reason(self):
        for name, run, reason in CASES:
            with self.subTest(case=name):
                result = run()
                self.assertEqual((result.status, result.reason), (V.NOT_ACCEPTED, reason))
                self.assertEqual(dict(result.facts), {})

    def test_every_reason_in_the_taxonomy_is_exercised(self):
        self.assertEqual({reason for _, _, reason in CASES}, set(V.REASONS))
        self.assertEqual(len(V.REASONS), len(set(V.REASONS)))

    def test_every_signed_challenge_field_mutated_after_signing_is_rejected(self):
        alternatives = {
            "ownerPrincipal": "user:other@example.invalid", "challengeId": "och.other",
            "actionDigest": OTHER, "requestDigest": OTHER, "payloadDigest": OTHER, "operation": "FORGET",
            "memoryClass": "OTHER_CLASS", "subjectNamespace": "project.other", "subjectKey": "other",
            "purpose": "OTHER_PURPOSE", "privacyNoticeVersion": "privacy.other.v1",
            "nonce": S.b64(bytes(range(1, 33))), "issuedAt": "2026-09-26T12:00:05Z",
            "expiresAt": "2026-09-26T12:00:50Z", "rpId": "other.lilith.invalid",
            "deploymentEnvironment": "dev", "authorityDomain": "authority.other",
            "logicalOwnerId": "owner.other.v1", "policyVersion": "policy.other.v1",
            "registryTupleVersion": "registry.other.v1", "ledgerEpoch": "e" * 32,
        }
        per_operation = {
            "SUPERSEDE": {"memoryItemId": "mitem.other", "expectedActiveRevisionId": "mrev.other"},
            "RESTORE": {"restoreTargetRevisionId": "mrev.other"},
        }
        covered = set(alternatives) | {name for fields in per_operation.values() for name in fields}
        # protocol/schemaVersion are version identity; restoreTargetDigest must equal payloadDigest.
        self.assertEqual(covered | {"protocol", "schemaVersion", "restoreTargetDigest"}, K.CHALLENGE_V2_FIELDS)
        cases = [("CREATE", alternatives)] + list(per_operation.items())
        for operation, fields in cases:
            chain = S.Chain(operation)
            for name, value in fields.items():
                with self.subTest(operation=operation, field=name):
                    result = verify(chain, challenge_json=rebuilt_challenge(chain, **{name: value}))
                    self.assertEqual(result.status, V.NOT_ACCEPTED)


class ForbiddenEqualityTests(unittest.TestCase):
    """Each forbidden equality is proven false."""

    def assertNotAccepted(self, result):
        self.assertEqual(result.status, V.NOT_ACCEPTED)
        self.assertFalse(result.accepted)

    def test_model_output_is_not_accepted_memory(self):
        model_output = {"status": "ACCEPTED_MEMORY", "note": "I have remembered this for you."}
        self.assertNotAccepted(V.verify_accepted_memory(
            context=S.context(), action=S.action(), challenge_json=json.dumps(model_output).encode(),
            challenge_record=model_output, assertion=model_output, owner_credential=model_output,
            evidence=model_output, broker_keys=[], admission=model_output))

    def test_proposal_existing_is_not_accepted_memory(self):
        self.assertEqual(verify(S.Chain(), challenge_json=None, assertion=None, owner_credential=None,
                                challenge_record=None, evidence=None, admission=None).reason, "OWNER_PROOF_MISSING")

    def test_database_row_existing_is_not_accepted_memory(self):
        chain = S.Chain()
        self.assertNotAccepted(verify(chain, challenge_json=None, assertion=None, owner_credential=None,
                                      challenge_record=None, evidence=None))

    def test_l04_apply_success_is_not_accepted_memory(self):
        self.assertEqual(verify(S.Chain(), evidence=None).reason, "BROKER_EVIDENCE_MISSING")

    def test_execution_success_is_not_accepted_memory(self):
        # Broker evidence and an L04 apply both "succeeded", but no owner proof exists.
        self.assertEqual(verify(S.Chain(), assertion=None).reason, "OWNER_PROOF_MISSING")

    def test_broker_evidence_alone_is_not_owner_authorization(self):
        self.assertEqual(verify(S.Chain(signing_owner=S.owner_key(S.TEST_ONLY_ATTACKER_SCALAR))).reason,
                         "OWNER_SIGNATURE_INVALID")

    def test_owner_proof_alone_is_not_durable_accepted_memory(self):
        self.assertEqual(verify(S.Chain(), evidence=None, admission=None).reason, "BROKER_EVIDENCE_MISSING")
        self.assertEqual(verify(S.Chain(), admission=None).reason, "ADMISSION_EVIDENCE_MISSING")

    def test_cached_acceptance_flag_is_not_authority(self):
        chain = S.Chain()
        for container in ("admission", "evidence", "challenge_record"):
            with self.subTest(container=container):
                forged = {**getattr(chain, container), "acceptanceStatus": "accepted"}
                self.assertNotAccepted(verify(chain, **{container: forged}))

    def test_matching_approved_value_is_not_authority(self):
        approved = S.Chain()
        # Same approved value and digest, but authority for a different identity.
        other = S.Chain(challenge_overrides={"subjectKey": "other"})
        self.assertEqual(verify(approved, challenge_json=other.challenge_json).status, V.NOT_ACCEPTED)
        self.assertEqual(verify(approved, challenge_json=None).reason, "OWNER_PROOF_MISSING")


class MemoryIsNotTruthTests(unittest.TestCase):
    def test_user_asserted_value_remains_user_asserted_after_acceptance(self):
        result = verify(S.Chain(epistemic_basis="USER_ASSERTED"))
        self.assertTrue(result.accepted)
        self.assertEqual(result.facts["epistemicBasis"], "USER_ASSERTED")
        self.assertIs(result.facts["truthClaim"], False)
        self.assertEqual(result.facts["semantics"], V.ACCEPTANCE_SEMANTICS)
        self.assertIn("NOT_A_TRUTH_CLAIM", V.ACCEPTANCE_SEMANTICS)

    def test_every_source_epistemic_basis_is_preserved_unchanged(self):
        for basis in ("USER_ASSERTED", "OBSERVED", "INFERRED", "DERIVED"):
            with self.subTest(basis=basis):
                self.assertEqual(verify(S.Chain(epistemic_basis=basis)).facts["epistemicBasis"], basis)

    def test_result_never_names_truth_or_verification_of_content(self):
        facts = verify(S.Chain()).facts
        self.assertFalse(any(key.lower() in {"true", "verified", "istrue", "truth"} for key in facts))


class ContentGenericityTests(unittest.TestCase):
    def test_authority_verification_is_independent_of_content_type(self):
        for memory_class in ("PROJECT_CODENAME_FACT", "AUTOBIOGRAPHICAL_EVENT", "RELATIONSHIP_FACT",
                             "AFFECTIVE_REFLECTION", "REFLECTIVE_NOTE"):
            with self.subTest(memory_class=memory_class):
                self.assertTrue(verify(S.Chain(memory_class=memory_class)).accepted)

    def test_no_affect_model_in_the_authority_verifier(self):
        source = Path(V.__file__).read_text(encoding="utf-8").lower()
        for term in ("happy", "sad", "love", "emotion", "affect", "valence", "arousal", "sentiment"):
            self.assertNotIn(term, source)


class IndependenceAndSideEffectTests(unittest.TestCase):
    def test_verifier_inputs_contain_no_model_runtime_or_persona_object(self):
        parameters = set(inspect.signature(V.verify_accepted_memory).parameters)
        self.assertEqual(parameters, {"context", "action", "challenge_json", "challenge_record", "assertion",
                                      "owner_credential", "evidence", "broker_keys", "admission"})

    def test_verifier_and_contracts_have_no_io_model_runtime_or_network_dependency(self):
        for module in (V, K):
            source = Path(module.__file__).read_text(encoding="utf-8")
            for forbidden in ("import sqlite3", "import socket", "import requests", "urllib", "http.client",
                              "subprocess", "hermes", "openai", "anthropic", "os.environ", "open(",
                              "sys.path", "write_text", "write_bytes"):
                self.assertNotIn(forbidden, source, (module.__name__, forbidden))

    def test_same_chain_same_result_regardless_of_caller_supplied_persona(self):
        chain = S.Chain()
        results = {verify(chain).status for _persona in ("terse", "warm", "formal", "model-a", "model-b")}
        self.assertEqual(results, {V.ACCEPTED_MEMORY})

    def test_verification_does_not_mutate_supplied_artifacts(self):
        chain = S.Chain()
        before = json.dumps(chain.kwargs(context=None, action=None), sort_keys=True, default=str)
        verify(chain)
        self.assertEqual(json.dumps(chain.kwargs(context=None, action=None), sort_keys=True, default=str), before)


if __name__ == "__main__":
    unittest.main()
