"""15B2b-B1b-3b: broker-only signing + L04 V2 verification adapter (TEST-ONLY).

Every key, owner, credential, value, and database here is synthetic and lives
in-process or in a temporary directory. No DEV, PROD, broker, Privacy DB, or
live L04 state is touched.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import hmac
import inspect
import json
import pickle
import re
import unittest
from datetime import timedelta
from pathlib import Path

import synthetic_authority as SA
import synthetic_b1b3b as T
import synthetic_chain as SC
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from lilith_authority_signer import synthetic_broker as B
from lilith_memory import canonical_authority as CA
from lilith_memory import canonical_contracts as C
from lilith_memory import canonical_store
from lilith_memory import learning_v2
from lilith_owner_memory import admission_v2 as V2
from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import authority_verifier as AV
from lilith_owner_memory import contracts as K
from lilith_owner_memory import l04_v2_adapter as AD
from lilith_owner_memory import verifier as B2A

PACKAGE = Path(V2.__file__).resolve().parent
SIGNER_PACKAGE = Path(B.__file__).resolve().parent
GOLDEN_PATH = Path(__file__).with_name("b1b3b_golden.json")


class FlowCase(unittest.TestCase):
    def setUp(self) -> None:
        self.flow = T.Flow()
        self.addCleanup(self.flow.l04.close)

    def admit(self, proposal, proof, evidence, /, **replace):
        return self.flow.adapter.admit(self.flow.request(proposal, proof, evidence, **replace))

    def accept(self, proof, evidence, proposal, /, **replace):
        return V2.verify_accepted_memory_v2(**self.flow.acceptance_kwargs(proof, evidence, proposal, **replace))

    def assertRejected(self, result, reason, detail=None):
        self.assertEqual((result.status, result.reason, result.detail), (V2.NOT_ACCEPTED, reason, detail), result)


# --------------------------------------------------- 1. current V1 chain ---

class V1HistoricalChainTests(FlowCase):
    def test_v1_chain_is_unchanged_and_admits_through_application_rows(self):
        """Documents the existing V1 admission chain: application-owned HMAC
        ActorEvidenceRefV1 + Policy + Consent (+ Rollback) rows are what the
        unchanged L04 store trusts. This slice does not rewrite it."""
        l04 = self.flow.l04
        action, encoded = l04.action("SYNTH-V1")
        proposal = l04.proposal(action, encoded, nonce="v1.history")
        evidence = l04.last["actor_evidence"]
        self.assertEqual(l04.actor.validate_existing(evidence.actor_evidence_ref_id, action=action,
                                                      require_consumed=True), evidence)
        self.assertEqual(l04.policy.resolve(l04.last["policy"].decision_ref_id, action=action,
                                            capability=T.L04_CAPABILITY).status, CA.CONFIRMED)
        self.assertEqual(l04.store().apply(proposal).outcome, canonical_store.ACCEPTED)

    def test_b2a_and_b1a_verifier_semantics_are_unchanged_by_the_owner_proof_extraction(self):
        chain = SC.Chain()
        self.assertEqual(B2A.verify_accepted_memory(**chain.kwargs()).status, B2A.ACCEPTED_MEMORY)
        proof = B2A.verify_owner_proof(context=chain.context, action=chain.action,
                                       challenge_json=chain.challenge_json, challenge_record=chain.challenge_record,
                                       assertion=chain.assertion, owner_credential=chain.owner_credential)
        self.assertEqual(proof.status, B2A.VERIFIED_OWNER_PROOF)
        broken = B2A.verify_owner_proof(context=chain.context, action=chain.action,
                                        challenge_json=chain.challenge_json,
                                        challenge_record={**chain.challenge_record, "state": "PREPARED",
                                                          "consumedCredentialRecordId": None, "consumedAt": None},
                                        assertion=chain.assertion, owner_credential=chain.owner_credential)
        self.assertEqual((broken.status, broken.reason), (B2A.NOT_ACCEPTED, "CHALLENGE_NOT_CONSUMED"))
        self.assertEqual(len(B2A.REASONS), 43)


# ------------------------------------------------ 3/4/8. broker signing ---

class BrokerSignerTests(FlowCase):
    def setUp(self) -> None:
        super().setUp()
        self.action, _ = self.flow.l04.action("SYNTH-SIGN")
        self.proof = T.owner_proof(self.action, "och.sign")
        self.broker = self.flow.broker
        self.clock = self.flow.clock

    def request(self, **replace):
        value = dict(challenge_id="och.sign", action=self.action, assertion=self.proof.assertion,
                     owner_credential=self.proof.credential)
        value.update(replace)
        return B.OwnerEvidenceRequestV1(**value)

    def consume(self, **replace):
        value = dict(action=self.action, assertion=self.proof.assertion, owner_credential=self.proof.credential)
        value.update(replace)
        return self.broker.consume_owner_proof("och.sign", **value)

    def test_proposal_alone_is_not_signed_evidence(self):
        result = self.broker.issue_owner_evidence(self.request())
        self.assertEqual((result.status, result.reason, result.evidence), (B.REFUSED, "CHALLENGE_UNKNOWN", None))

    def test_challenge_alone_is_not_signed_evidence(self):
        self.assertEqual(self.broker.prepare_challenge(self.proof.challenge_json).status, B.PREPARED)
        result = self.broker.issue_owner_evidence(self.request())
        self.assertEqual((result.status, result.reason), (B.REFUSED, "CHALLENGE_NOT_CONSUMED"))

    def test_valid_assertion_over_unconsumed_challenge_is_not_signed_evidence(self):
        self.broker.prepare_challenge(self.proof.challenge_json)
        # The assertion is genuinely valid, but the challenge was never consumed.
        result = self.broker.issue_owner_evidence(self.request())
        self.assertEqual((result.status, result.reason), (B.REFUSED, "CHALLENGE_NOT_CONSUMED"))
        # A forged "CONSUMED" ledger view held by the app changes nothing.
        view = dict(self.broker.ledger_record("och.sign"))
        view.update(state="CONSUMED", consumedCredentialRecordId="ocred.synthetic", consumedAt="2026-09-26T12:00:20Z")
        self.assertEqual(self.broker.ledger_record("och.sign")["state"], B.PREPARED)
        self.assertEqual(self.broker.issue_owner_evidence(self.request()).reason, "CHALLENGE_NOT_CONSUMED")

    def test_consumed_valid_owner_proof_with_correct_context_is_signed(self):
        self.broker.prepare_challenge(self.proof.challenge_json)
        self.assertEqual(self.consume().status, B.CONSUMED)
        self.clock.value = T.CHALLENGE_ISSUED + timedelta(seconds=21)
        issued = self.broker.issue_owner_evidence(self.request())
        self.assertEqual(issued.status, B.ISSUED)
        evidence = issued.evidence
        challenge = self.proof.challenge
        self.assertEqual({k: evidence[k] for k in (
            "challengeId", "evidenceNonce", "challengeDigest", "credentialRecordId", "assertionDigest",
            "actionDigest", "requestDigest", "payloadDigest", "signingDomain", "authorityDomain", "evidenceType",
            "environment", "logicalOwnerId", "keyId", "registryVersion", "recoveryEpoch", "policyVersion",
            "issuedAt")}, {
            "challengeId": "och.sign", "evidenceNonce": "och.sign",
            "challengeDigest": challenge.challenge_digest(),
            "credentialRecordId": "ocred.synthetic",
            "assertionDigest": K.assertion_digest(B2A.P.OwnerAssertionV1.from_dict(self.proof.assertion)),
            "actionDigest": self.action.action_digest, "requestDigest": challenge["requestDigest"],
            "payloadDigest": self.action.payload_digest, "signingDomain": A.OWNER_ACTOR,
            "authorityDomain": SA.LOGICAL_AUTHORITY_DOMAIN, "evidenceType": A.OWNER_MEMORY_OPERATION,
            "environment": "test", "logicalOwnerId": SA.LOGICAL_OWNER, "keyId": T.BROKER_KEY_ID,
            "registryVersion": SA.REGISTRY_VERSION, "recoveryEpoch": SA.EPOCH.to_dict(),
            "policyVersion": SA.POLICY, "issuedAt": "2026-09-26T12:00:21Z"})
        self.assertTrue(evidence["evidenceId"].startswith("aev."))

    def test_consumption_requires_a_valid_owner_assertion_and_happens_once(self):
        self.broker.prepare_challenge(self.proof.challenge_json)
        forged = SC.assertion_dict(self.proof.challenge.webauthn_challenge(), SC.owner_key(SC.TEST_ONLY_ATTACKER_SCALAR))
        result = self.consume(assertion=forged)
        self.assertEqual((result.reason, result.detail), ("OWNER_PROOF_REJECTED", "OWNER_SIGNATURE_INVALID"))
        self.assertEqual(self.broker.ledger_record("och.sign")["state"], B.PREPARED)
        self.assertEqual(self.consume().status, B.CONSUMED)
        self.assertEqual(self.consume().reason, "CHALLENGE_NOT_PREPARED")

    def test_expired_challenge_cannot_be_consumed_or_signed(self):
        self.broker.prepare_challenge(self.proof.challenge_json)
        self.clock.value = T.CHALLENGE_ISSUED + timedelta(seconds=60)
        self.assertEqual(self.consume().reason, "CHALLENGE_EXPIRED")
        self.assertEqual(self.broker.ledger_record("och.sign")["state"], B.EXPIRED)
        self.assertEqual(self.broker.issue_owner_evidence(self.request()).reason, "CHALLENGE_NOT_CONSUMED")

    def test_evidence_is_issued_at_most_once_per_consumed_proof(self):
        self.broker.prepare_challenge(self.proof.challenge_json)
        self.consume()
        self.assertEqual(self.broker.issue_owner_evidence(self.request()).status, B.ISSUED)
        self.assertEqual(self.broker.issue_owner_evidence(self.request()).reason, "EVIDENCE_ALREADY_ISSUED")

    def test_signer_never_signs_a_different_action_than_the_owner_approved(self):
        self.broker.prepare_challenge(self.proof.challenge_json)
        self.consume()
        other, _ = self.flow.l04.action("SYNTH-SWAPPED")
        result = self.broker.issue_owner_evidence(self.request(action=other))
        self.assertEqual((result.reason, result.detail), ("OWNER_PROOF_REJECTED", "PAYLOAD_DIGEST_MISMATCH"))
        self.assertEqual(self.broker.issue_owner_evidence(self.request(challenge_id=123)).reason,
                         "REQUEST_MALFORMED")
        self.assertEqual(self.broker.issue_owner_evidence("raw memory text").reason, "REQUEST_MALFORMED")

    def test_signer_refuses_foreign_context_and_privacy_owned_forget(self):
        for override in ({"authorityDomain": "authority.synthetic.privacy"}, {"deploymentEnvironment": "dev"},
                         {"logicalOwnerId": "owner.attacker.v1"}, {"policyVersion": "policy.synthetic.v1"},
                         {"ledgerEpoch": "ffffffffffffffffffffffffffffffff"}):
            with self.subTest(override=override):
                proof = T.owner_proof(self.action, "och.ctx", **override)
                self.assertEqual(self.broker.prepare_challenge(proof.challenge_json).reason,
                                 "CHALLENGE_CONTEXT_MISMATCH")
        forget, _ = self.flow.l04.action(None, operation=C.FORGET, restore_digest=T.digest("forget"))
        proof = T.owner_proof(forget, "och.forget", memory_item_id="mitem.synthetic")
        self.assertEqual(self.broker.prepare_challenge(proof.challenge_json).reason, "PRIVACY_OWNED_OPERATION")
        self.assertEqual(self.broker.prepare_challenge(b"{not canonical").reason, "CHALLENGE_MALFORMED")
        self.broker.prepare_challenge(self.proof.challenge_json)
        self.assertEqual(self.broker.prepare_challenge(self.proof.challenge_json).reason,
                         "CHALLENGE_ALREADY_PREPARED")

    def test_signer_construction_is_test_only(self):
        with self.assertRaises(B.SignerConfigurationError):
            T.broker(self.clock, environment="dev")
        with self.assertRaises(B.SignerConfigurationError):
            T.broker(self.clock, authority_domain=A.OWNER_ACTOR)
        with self.assertRaises(B.SignerConfigurationError):
            B.SyntheticBrokerAuthorityV1(signing_key=T.TEST_ONLY_BROKER_SEED, config=T.signer_config(),
                                         owner_context=T.owner_context(), now_fn=self.clock)
        with self.assertRaises(B.SignerConfigurationError):
            B.SyntheticBrokerAuthorityV1(signing_key=T.broker_private(), config=T.signer_config(),
                                         owner_context=SC.context(), now_fn=self.clock)  # policy disagrees
        with self.assertRaises(B.SignerConfigurationError):
            B.SyntheticBrokerAuthorityV1(signing_key=T.broker_private(), config=T.signer_config(),
                                         owner_context=T.owner_context(rp_id="owner.lilith.example",
                                                                       origin="https://owner.lilith.example"),
                                         now_fn=self.clock)

    def test_signing_is_deterministic_for_identical_verified_inputs(self):
        results = []
        for _ in range(2):
            broker = T.broker(T.Clock(T.CHALLENGE_ISSUED + timedelta(seconds=20)))
            broker.prepare_challenge(self.proof.challenge_json)
            broker.consume_owner_proof("och.sign", action=self.action, assertion=self.proof.assertion,
                                       owner_credential=self.proof.credential)
            results.append(broker.issue_owner_evidence(self.request()).evidence)
        self.assertEqual(results[0], results[1])

    def test_signer_key_is_not_exposed_serialized_or_copied(self):
        self.assertNotIn("private", repr(self.broker).lower())
        with self.assertRaises(TypeError):
            pickle.dumps(self.broker)
        with self.assertRaises(TypeError):
            copy.copy(self.broker)
        with self.assertRaises(TypeError):
            copy.deepcopy(self.broker)
        for name in dir(self.broker):
            if name.startswith("_"):
                continue
            value = getattr(self.broker, name)
            self.assertNotIsInstance(value, Ed25519PrivateKey, name)
            self.assertNotEqual(value, T.TEST_ONLY_BROKER_SEED, name)

    def test_broker_key_is_distinct_from_root_b1b3a_keys_and_b2a_broker(self):
        broker_public = self.broker.public_key_b64()
        self.assertEqual(broker_public, T.public_b64(T.TEST_ONLY_BROKER_SEED))
        others = {SA.public_b64(name) for name in SA.SEEDS} | {SA.public_b64(SC.broker_key()),
                                                              SA.public_b64(SC.broker_key(SC.TEST_ONLY_BROKER_SEED_2))}
        self.assertNotIn(broker_public, others)
        self.assertNotEqual(T.TEST_ONLY_BROKER_SEED, T.TEST_ONLY_V1_ACTOR_HMAC_SECRET)


# ----------------------------------------- 5/9/16. adapter + end-to-end ---

class PositiveEndToEndTests(FlowCase):
    def test_complete_synthetic_path_ends_in_accepted_memory_not_truth(self):
        flow = self.flow
        action, proposal, proof, evidence = flow.create("SYNTH-E2E", "e2e")
        # Stage 1: authority evidence verifies, and is nothing more.
        authority = AV.verify_owner_evidence(
            context=T.authority_context(), registry=flow.registry_doc, evidence=evidence,
            expectation=A.OwnerEvidenceExpectationV2(
                evidence_id=evidence["evidenceId"], challenge_id=proof.challenge["challengeId"],
                challenge_digest=proof.challenge.challenge_digest(), credential_record_id="ocred.synthetic",
                assertion_digest=evidence["assertionDigest"], action_digest=action.action_digest,
                request_digest=proof.challenge["requestDigest"], payload_digest=action.payload_digest,
                logical_owner_id=SA.LOGICAL_OWNER, authority_domain=SA.LOGICAL_AUTHORITY_DOMAIN))
        self.assertEqual(authority.status, AV.VERIFIED_AUTHORITY_EVIDENCE)
        self.assertFalse(authority.facts["memoryAcceptance"])
        # Verified evidence is not an admission and not acceptance.
        self.assertRejected(self.accept(proof, evidence, proposal), "ADMISSION_LINK_MISSING")
        self.assertEqual(flow.l04.counts()["memory_admission"], 0)

        # Stage 2: L04 admits, linked to the exact evidence. Still not acceptance.
        admitted = self.admit(proposal, proof, evidence)
        self.assertEqual(admitted.status, AD.L04_ADMITTED)
        self.assertEqual((admitted.facts["memoryAcceptance"], admitted.facts["truthClaim"]), (False, False))
        link = admitted.facts["link"]
        self.assertEqual((link["authorityEvidenceId"], link["authorityEvidenceDigest"], link["proposalRefId"]),
                         (evidence["evidenceId"], V2.evidence_digest(evidence), proposal))
        self.assertEqual(flow.links.get(proposal), link)

        # Stage 3: the complete chain re-verifies into ACCEPTED_MEMORY.
        accepted = self.accept(proof, evidence, proposal)
        self.assertEqual(accepted.status, V2.ACCEPTED_MEMORY)
        self.assertIs(accepted.facts["truthClaim"], False)
        self.assertEqual(accepted.facts["epistemicBasis"], "USER_ASSERTED")  # source basis preserved
        self.assertEqual(accepted.facts["authority"]["signingDomain"], A.OWNER_ACTOR)
        self.assertEqual(accepted.facts["authority"]["authorityDomain"], SA.LOGICAL_AUTHORITY_DOMAIN)
        self.assertEqual(accepted.facts["revisionId"], admitted.facts["admission"]["revisionId"])
        historical = self.accept(proof, evidence, proposal, authority_context=SA.historical_context())
        self.assertEqual(historical.status, V2.ACCEPTED_MEMORY)

        # Stage 4: never truth. The stage names stay distinct.
        stages = {AV.VERIFIED_AUTHORITY_EVIDENCE, AD.L04_ADMITTED, V2.ACCEPTED_MEMORY}
        self.assertEqual(len(stages), 3)
        self.assertNotIn("TRUTH", "".join(stages))
        # L04_ADMITTED != ACCEPTED_MEMORY: a broken owner-proof link still fails
        # acceptance for a row that L04 admitted.
        self.assertRejected(self.accept(proof, evidence, proposal, challenge_record=None),
                            "OWNER_PROOF_REJECTED", "CHALLENGE_STATE_MISSING")

    def test_supersede_and_restore_through_the_v2_path(self):
        flow = self.flow
        _, created_ref, proof, evidence = flow.create("SYNTH-ONE", "chain.create")
        created = self.admit(created_ref, proof, evidence).facts["admission"]
        item, first_revision = created["memoryItemId"], created["revisionId"]
        first_digest = created["payloadDigest"]

        action2, encoded2 = flow.l04.action("SYNTH-TWO", operation=C.SUPERSEDE, expected=first_revision)
        ref2 = flow.l04.proposal(action2, encoded2, nonce="chain.supersede")
        proof2 = T.owner_proof(action2, "och.chain.supersede", memory_item_id=item)
        evidence2 = flow.signed(proof2)
        second = self.admit(ref2, proof2, evidence2)
        self.assertEqual(second.status, AD.L04_ADMITTED, second)
        self.assertEqual(self.accept(proof2, evidence2, ref2).status, V2.ACCEPTED_MEMORY)

        action3, _ = flow.l04.action(None, operation=C.RESTORE, expected=second.facts["admission"]["revisionId"],
                                     restore=first_revision, restore_digest=first_digest)
        ref3 = flow.l04.proposal(action3, None, nonce="chain.restore", memory_item_id=item)
        proof3 = T.owner_proof(action3, "och.chain.restore", memory_item_id=item)
        evidence3 = flow.signed(proof3)
        third = self.admit(ref3, proof3, evidence3)
        self.assertEqual(third.status, AD.L04_ADMITTED, third)
        accepted = self.accept(proof3, evidence3, ref3)
        self.assertEqual((accepted.status, accepted.facts["operation"]), (V2.ACCEPTED_MEMORY, C.RESTORE))
        self.assertEqual(flow.l04.counts()["rollback_consumption"], 1)


# ------------------------------------------------ 15. negative matrix ---

class NegativeMatrixTests(FlowCase):
    """Every case is rejected before L04 is touched, then the untouched valid
    request still admits, proving the rejections were not setup failures."""

    def setUp(self) -> None:
        super().setUp()
        flow = self.flow
        self.action, self.proposal, self.proof, self.evidence = flow.create("SYNTH-MATRIX", "matrix")
        other_action, other_encoded = flow.l04.action("SYNTH-OTHER-MEMORY")
        self.other_proposal = flow.l04.proposal(other_action, other_encoded, nonce="matrix.other")
        self.other_proof = T.owner_proof(other_action, "och.matrix.other")
        self.other_evidence = flow.signed(self.other_proof)
        forget, _ = flow.l04.action(None, operation=C.FORGET, restore_digest=T.digest("forget"))
        self.forget_proof = T.owner_proof(forget, "och.matrix.forget", memory_item_id="mitem.synthetic")
        forget_challenge = self.forget_proof.challenge
        # A registry-valid OwnerEvidenceV2 for a FORGET (e.g. the grounding
        # owner evidence a Privacy authorization references).
        self.forget_evidence = T.resign(
            self.evidence, evidenceId="aev.synthetic-forget", challengeId="och.matrix.forget",
            evidenceNonce="och.matrix.forget", challengeDigest=forget_challenge.challenge_digest(),
            actionDigest=forget.action_digest, payloadDigest=forget.payload_digest,
            requestDigest=forget_challenge["requestDigest"])
        self.baseline = flow.l04.counts()

    def registry_with_broker(self, **broker_overrides):
        return T.registry(version=4, issued_at="2026-09-26T13:00:00Z",
                          keys=T.registry_keys(broker=T.broker_key_record(**broker_overrides)))

    def v1_evidence(self):
        return self.flow.l04.last["actor_evidence"]

    def cases(self):
        e, rs = self.evidence, T.resign
        rogue = T.TEST_ONLY_ROGUE_APP_SEED
        tampered = lambda **o: {**e, **o}  # noqa: E731 - changed after signing
        v1 = self.v1_evidence()
        chain = SC.Chain()
        return [
            ("no authority evidence", {"evidence": None}, None, "AUTHORITY_EVIDENCE_MISSING", None),
            ("malformed evidence", {"evidence": {"evidenceId": "aev.synthetic"}}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "EVIDENCE_MALFORMED"),
            ("unsupported evidence schema", {"evidence": {**e, "schemaVersion": 1}}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "UNSUPPORTED_SCHEMA_VERSION"),
            ("non-mapping evidence", {"evidence": "raw evidence text"}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "EVIDENCE_MALFORMED"),
            ("unsigned evidence", {"evidence": {k: v for k, v in e.items() if k != "signature"}}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "EVIDENCE_MALFORMED"),
            ("zero signature", {"evidence": tampered(signature=SA.b64(bytes(64)))}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "SIGNATURE_INVALID"),
            ("wrong signer", {"evidence": rs(e, rogue)}, None, "AUTHORITY_EVIDENCE_REJECTED", "SIGNATURE_INVALID"),
            ("unknown keyId", {"evidence": rs(e, rogue, keyId="actor.unknown-9")}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "KEY_UNKNOWN"),
            ("wrong signingDomain", {"evidence": rs(e, signingDomain=A.PRIVACY)}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "SIGNING_DOMAIN_MISMATCH"),
            ("wrong authorityDomain", {"evidence": rs(e, authorityDomain="authority.synthetic.privacy")}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "AUTHORITY_DOMAIN_MISMATCH"),
            ("wrong environment", {"evidence": rs(e, environment="dev")}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "ENVIRONMENT_MISMATCH"),
            ("wrong evidenceType", {"evidence": rs(e, evidenceType=A.PRIVACY_ERASURE_AUTHORIZATION)}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "EVIDENCE_TYPE_MISMATCH"),
            ("wrong epoch", {"evidence": rs(e, recoveryEpoch=SA.FORK_EPOCH.to_dict())}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "RECOVERY_EPOCH_MISMATCH"),
            ("wrong registry version (future)", {"evidence": rs(e, registryVersion=9)}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "REGISTRY_VERSION_MISMATCH"),
            ("wrong registry version (before key)", {"evidence": rs(e, registryVersion=2)}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "REGISTRY_VERSION_MISMATCH"),
            ("wrong policy version", {"evidence": rs(e, policyVersion="policy.synthetic.v1")}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "POLICY_VERSION_MISMATCH"),
            ("compromised key", {}, self.registry_with_broker(
                revokedAt="2026-09-26T12:30:00Z", revocationReason="COMPROMISED",
                compromisedSince="2026-09-26T12:10:00Z"), "AUTHORITY_EVIDENCE_REJECTED", "KEY_COMPROMISED"),
            ("evidence after retirement", {}, self.registry_with_broker(retiredAt="2026-09-26T12:00:00Z"),
             "AUTHORITY_EVIDENCE_REJECTED", "KEY_RETIRED"),
            ("evidence after revocation", {}, self.registry_with_broker(
                revokedAt="2026-09-26T12:00:10Z", revocationReason="ROUTINE"),
             "AUTHORITY_EVIDENCE_REJECTED", "KEY_REVOKED"),
            ("registry missing", {}, "MISSING", "AUTHORITY_EVIDENCE_REJECTED", "REGISTRY_MISSING"),
            ("registry signed by attacker root", {}, T.registry(signer="attacker-root"),
             "AUTHORITY_EVIDENCE_REJECTED", "REGISTRY_SIGNATURE_INVALID"),
            ("payloadDigest substitution (re-signed)", {"evidence": rs(e, payloadDigest=T.digest("x"))}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "PAYLOAD_DIGEST_MISMATCH"),
            ("payloadDigest substitution (tampered)", {"evidence": tampered(payloadDigest=T.digest("x"))}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "SIGNATURE_INVALID"),
            ("actionDigest substitution (re-signed)", {"evidence": rs(e, actionDigest=T.digest("x"))}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "ACTION_DIGEST_MISMATCH"),
            ("actionDigest substitution (tampered)", {"evidence": tampered(actionDigest=T.digest("x"))}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "SIGNATURE_INVALID"),
            ("requestDigest substitution (re-signed)", {"evidence": rs(e, requestDigest=T.digest("x"))}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "REQUEST_DIGEST_MISMATCH"),
            ("requestDigest substitution (tampered)", {"evidence": tampered(requestDigest=T.digest("x"))}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "SIGNATURE_INVALID"),
            ("challenge substitution", {"evidence": rs(e, challengeId="och.other", evidenceNonce="och.other")},
             None, "AUTHORITY_EVIDENCE_REJECTED", "CHALLENGE_REFERENCE_MISMATCH"),
            ("challenge digest substitution", {"evidence": rs(e, challengeDigest=T.digest("x"))}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "CHALLENGE_REFERENCE_MISMATCH"),
            ("owner substitution", {"evidence": rs(e, logicalOwnerId="owner.attacker.v1")}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "LOGICAL_OWNER_MISMATCH"),
            ("owner credential substitution", {"evidence": rs(e, credentialRecordId="ocred.attacker")}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "OWNER_PROOF_REFERENCE_MISMATCH"),
            ("evidence ID substitution", {"evidence": tampered(evidenceId="aev.substituted")}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "SIGNATURE_INVALID"),
            ("nonce substitution", {"evidence": rs(e, evidenceNonce="nonce.other")}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "EVIDENCE_NONCE_MISMATCH"),
            ("V1 HMAC evidence object", {"evidence": v1}, None,
             "NON_V2_EVIDENCE_NOT_ACCEPTED", V2.ACTOR_EVIDENCE_REF_V1),
            ("V1 HMAC evidence dict", {"evidence": {"actorEvidenceRefId": v1.actor_evidence_ref_id,
                                                    "evidenceFingerprint": v1.evidence_fingerprint}}, None,
             "NON_V2_EVIDENCE_NOT_ACCEPTED", V2.ACTOR_EVIDENCE_REF_V1),
            ("B2a TEST broker envelope", {"evidence": chain.evidence}, None,
             "NON_V2_EVIDENCE_NOT_ACCEPTED", V2.B2A_BROKER_EVIDENCE_V1),
            ("owner proof missing", {"assertion": None}, None, "OWNER_PROOF_REJECTED", "OWNER_PROOF_MISSING"),
            ("app-forged unconsumed ledger view", {"challenge_record": {
                **self.flow.broker.ledger_record("och.matrix"), "state": "PREPARED",
                "consumedCredentialRecordId": None, "consumedAt": None}}, None,
             "OWNER_PROOF_REJECTED", "CHALLENGE_NOT_CONSUMED"),
            ("valid evidence bound to another memory", {"evidence": self.other_evidence}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "CHALLENGE_REFERENCE_MISMATCH"),
            ("another memory's whole bundle", {"evidence": self.other_evidence,
                                               "challenge_json": self.other_proof.challenge_json,
                                               "challenge_record": self.flow.broker.ledger_record("och.matrix.other"),
                                               "assertion": self.other_proof.assertion}, None,
             "OWNER_PROOF_REJECTED", "PAYLOAD_DIGEST_MISMATCH"),
            ("valid OwnerEvidenceV2 performing a Privacy-owned FORGET", {
                "evidence": self.forget_evidence, "challenge_json": self.forget_proof.challenge_json,
                "assertion": self.forget_proof.assertion}, None, "PRIVACY_OWNED_OPERATION", None),
            ("unknown proposal", {"proposal_ref_id": "proposal-ref.unknown"}, None, "PROPOSAL_UNRESOLVED", None),
            ("Privacy authorization as owner evidence", {"evidence": SA.privacy_authorization()}, None,
             "AUTHORITY_EVIDENCE_REJECTED", "EVIDENCE_MALFORMED"),
        ]

    def test_negative_matrix(self):
        seen = set()
        for name, replace, registry, reason, detail in self.cases():
            with self.subTest(case=name):
                saved = self.flow.registry_doc
                if registry is not None:
                    self.flow.registry_doc = None if registry == "MISSING" else registry
                try:
                    proposal = replace.pop("proposal_ref_id", self.proposal)
                    result = self.admit(proposal, self.proof, replace.pop("evidence", self.evidence), **replace)
                finally:
                    self.flow.registry_doc = saved
                self.assertRejected(result, reason, detail)
                self.assertEqual(self.flow.l04.counts(), self.baseline)
                self.assertIsNone(self.flow.links.get(self.proposal))
                seen.add(reason)
        # Stage-3 negatives for the evidence-ID link and the downgrade.
        valid = self.admit(self.proposal, self.proof, self.evidence)
        self.assertEqual(valid.status, AD.L04_ADMITTED, valid)
        self.assertGreaterEqual(len(self.cases()), 40)
        self.assertTrue({"AUTHORITY_EVIDENCE_MISSING", "AUTHORITY_EVIDENCE_REJECTED", "NON_V2_EVIDENCE_NOT_ACCEPTED",
                         "OWNER_PROOF_REJECTED", "PRIVACY_OWNED_OPERATION", "PROPOSAL_UNRESOLVED"} <= seen)

    def test_replay_and_reuse_after_admission(self):
        self.assertEqual(self.admit(self.proposal, self.proof, self.evidence).status, AD.L04_ADMITTED)
        after = self.flow.l04.counts()
        # Same request again: the evidence is already consumed by an admission.
        self.assertRejected(self.admit(self.proposal, self.proof, self.evidence), "EVIDENCE_ALREADY_CONSUMED")
        # Same evidence replayed for another operation on another proposal.
        action2, encoded2 = self.flow.l04.action("SYNTH-MATRIX", operation=C.SUPERSEDE,
                                                 expected=self.flow.links.get(self.proposal)["revisionId"])
        ref2 = self.flow.l04.proposal(action2, encoded2, nonce="matrix.replay")
        self.assertRejected(self.admit(ref2, self.proof, self.evidence), "OWNER_PROOF_REJECTED", "OPERATION_MISMATCH")
        self.assertEqual(self.flow.l04.counts(), after)

    def test_acceptance_rejects_evidence_id_and_link_substitution(self):
        self.admit(self.proposal, self.proof, self.evidence)
        link = self.flow.links.get(self.proposal)
        cases = [
            ({"link": {**link, "authorityEvidenceId": "aev.substituted"}}, "AUTHORITY_EVIDENCE_REJECTED",
             "EVIDENCE_ID_MISMATCH"),
            ({"link": {**link, "authorityEvidenceDigest": T.digest("x")}}, "ADMISSION_LINK_MISMATCH", None),
            ({"link": {**link, "revisionId": "mrev.forged"}}, "ADMISSION_LINK_MISMATCH", None),
            ({"link": {**link, "schemaVersion": 2}}, "ADMISSION_LINK_MALFORMED", None),
            ({"link": None}, "ADMISSION_LINK_MISSING", None),
            ({"admission": None}, "ADMISSION_MISSING", None),
            ({"evidence": None}, "AUTHORITY_EVIDENCE_MISSING", None),
            ({"evidence": self.v1_evidence()}, "NON_V2_EVIDENCE_NOT_ACCEPTED", V2.ACTOR_EVIDENCE_REF_V1),
            ({"authority_context": T.authority_context(trusted_minimum_registry_version=4)},
             "AUTHORITY_EVIDENCE_REJECTED", "REGISTRY_DOWNGRADE"),
            ({"action": None}, "PROPOSAL_UNRESOLVED", None),
        ]
        for replace, reason, detail in cases:
            with self.subTest(replace=sorted(replace)):
                self.assertRejected(self.accept(self.proof, self.evidence, self.proposal, **replace), reason, detail)
        self.assertEqual(self.accept(self.proof, self.evidence, self.proposal).status, V2.ACCEPTED_MEMORY)

    def test_remaining_reasons_and_taxonomy_coverage(self):
        flow = self.flow
        self.assertRejected(flow.adapter.admit("not a request"), "MALFORMED_CONTEXT")
        self.assertRejected(self.accept(self.proof, self.evidence, self.proposal,
                                        owner_context=T.owner_context(deployment_environment="dev")),
                            "MALFORMED_CONTEXT")
        # Evidence claiming to predate the consumption it attests.
        early = T.resign(self.evidence, issuedAt="2026-09-26T12:00:10Z")
        self.assertRejected(self.admit(self.proposal, self.proof, early), "EVIDENCE_ORDER_INVALID")
        self.assertEqual(self.flow.l04.counts(), self.baseline)
        self.admit(self.proposal, self.proof, self.evidence)
        view = AD.read_l04_admission_view(flow.l04.db, self.proposal, self.action)
        # An owner challenge under another policy than the authority registry.
        v1_policy = T.owner_proof(self.action, "och.matrix.policy", policyVersion="policy.synthetic.v1")
        record = {"schemaVersion": 1, "challengeId": "och.matrix.policy", "state": "CONSUMED",
                  "consumedCredentialRecordId": "ocred.synthetic", "consumedAt": "2026-09-26T12:00:20Z",
                  "ledgerEpoch": SC.LEDGER_EPOCH}
        self.assertRejected(self.accept(v1_policy, self.evidence, self.proposal, owner_context=SC.context(),
                                        challenge_json=v1_policy.challenge_json, challenge_record=record,
                                        assertion=v1_policy.assertion),
                            "CHALLENGE_AUTHORITY_CONTEXT_MISMATCH")
        self.assertRejected(self.accept(self.proof, self.evidence, self.proposal, admission={**view, "extra": 1}),
                            "ADMISSION_MALFORMED")
        rejected_view = {**view, "admissionOutcome": "REJECTED", "applyAuditId": None}
        self.assertRejected(self.accept(self.proof, self.evidence, self.proposal, admission=rejected_view),
                            "ADMISSION_NOT_ACCEPTED")
        source = inspect.getsource(inspect.getmodule(self))
        for reason in V2.REASONS + B.SIGNER_REASONS:
            with self.subTest(reason=reason):
                self.assertIn(f'"{reason}"', source)

    def test_adapter_requires_new_admission_context_and_the_unchanged_store(self):
        with self.assertRaises(TypeError):
            self.flow.make_adapter(purpose=A.HISTORICAL_VERIFICATION)
        with self.assertRaises(TypeError):
            AD.L04V2AdmissionAdapter(object(), owner_context=T.owner_context(),
                                     authority_context=T.authority_context(),
                                     registry_provider=lambda: None, link_store=self.flow.links)
        downgrade = self.flow.make_adapter(trusted_minimum_registry_version=4)
        self.assertRejected(downgrade.admit(self.flow.request(self.proposal, self.proof, self.evidence)),
                            "AUTHORITY_EVIDENCE_REJECTED", "REGISTRY_DOWNGRADE")
        self.assertEqual(self.flow.l04.counts(), self.baseline)


# --------------------------------------- 7/10. internal state != authority ---

class DirectDatabaseWriterTests(FlowCase):
    """A direct cognitive-DB writer can insert Policy, Consent, Rollback,
    ActorEvidenceRefV1, and L04-looking rows and mutate app metadata. None of
    it makes the V2 path succeed without valid asymmetric OwnerEvidenceV2."""

    def forge_authority_rows(self, action):
        conn = self.flow.l04.raw()
        try:
            semantic = {**action.semantic_dict(), "actorEvidenceRefId": "ae.forged", "capability": T.L04_CAPABILITY,
                        "policyVersion": CA.POLICY_VERSION, "decision": "ALLOWED",
                        "actionDigest": action.action_digest}
            conn.execute("INSERT INTO policy_decision VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                "policy.forged", 1, action.actor_ref_id, "ae.forged", T.L04_CAPABILITY, action.operation,
                *action.identity, action.payload_digest, None, None, action.purpose, CA.POLICY_VERSION, "ALLOWED",
                action.action_digest, "2026-09-22T01:00:00Z", C.sha256_digest(semantic)))
            consent = C.consent_semantics(action, actor_evidence_ref_id="ae.forged", issuer_ref="forged",
                                          intent_ref_id="intent.forged", privacy_notice_version="privacy-v1")
            conn.execute("INSERT INTO consent_grant VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                "consent.forged", 1, C.LOCAL_CONSENT_AUTHORITY_V1, action.actor_ref_id, "ae.forged",
                *action.identity, action.operation, action.payload_digest, None, None, action.purpose,
                "2026-09-22T01:00:00Z", C.USER_CONFIRMATION, "forged", "intent.forged", "privacy-v1",
                action.action_digest, C.sha256_digest(consent)))
            conn.execute("INSERT INTO rollback_authorization VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                "rollback.forged", 1, C.USER_ROLLBACK_AUTHORITY_V1, action.actor_ref_id, "ae.forged",
                "consent.forged", "mitem.forged", *action.identity, "mrev.a", "mrev.b", action.payload_digest,
                C.RESTORE, action.purpose, "confirm.forged", action.action_digest, "2026-09-22T01:00:00Z",
                T.digest("forged rollback")))
            conn.execute("INSERT INTO actor_evidence_ref VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                "ae.forged", 1, action.actor_ref_id, C.LOCAL_OWNER_AUTHORITY_V1, T.digest("r"), action.action_digest,
                "nonce.forged", "2026-09-22T01:00:00Z", "2026-09-22T01:01:00Z", "forged", T.digest("fp")))
            conn.commit()
        finally:
            conn.close()

    def test_forged_policy_consent_rollback_and_actor_rows_do_not_authorize_v2(self):
        flow = self.flow
        action, proposal, proof, evidence = flow.create("SYNTH-DB", "db.rows")
        self.forge_authority_rows(action)
        # The forged Policy and Consent rows even resolve under V1 semantics
        # (plain SHA-256 fingerprints): this is D3, and why they are not authority.
        self.assertEqual(flow.l04.policy.resolve("policy.forged", action=action, capability=T.L04_CAPABILITY).status,
                         CA.CONFIRMED)
        self.assertEqual(flow.l04.consent.resolve("consent.forged", action=action).status, CA.CONFIRMED)
        with self.assertRaises(CA.ActorEvidenceError):  # without the HMAC key
            flow.l04.actor.validate_existing("ae.forged", action=action)
        baseline = flow.l04.counts()
        rogue = T.resign(evidence, T.TEST_ONLY_ROGUE_APP_SEED)
        for label, candidate, reason, detail in (
                ("rows only", None, "AUTHORITY_EVIDENCE_MISSING", None),
                ("V1 actor evidence row", flow.l04.last["actor_evidence"], "NON_V2_EVIDENCE_NOT_ACCEPTED",
                 V2.ACTOR_EVIDENCE_REF_V1),
                ("app-signed V2 lookalike", rogue, "AUTHORITY_EVIDENCE_REJECTED", "SIGNATURE_INVALID")):
            with self.subTest(label=label):
                self.assertRejected(self.admit(proposal, proof, candidate), reason, detail)
                self.assertEqual(flow.l04.counts(), baseline)
        self.assertEqual(self.admit(proposal, proof, evidence).status, AD.L04_ADMITTED)

    def test_internal_rows_are_still_consumed_but_never_sufficient(self):
        flow = self.flow
        action, proposal, proof, evidence = flow.create("SYNTH-REVOKED", "db.revoked")
        # Valid V2 evidence does not bypass L04's own internal-state rules.
        consent = flow.l04.last["consent"]
        revoke_evidence = flow.l04.actor.issue(action=action, request_digest=T.digest("revoke"), nonce="db.revoke")
        flow.l04.actor.resolve_and_consume(revoke_evidence.actor_evidence_ref_id, action=action,
                                           consumer_ref="test.revoke")
        flow.l04.consent.revoke(consent.consent_id, actor_evidence_ref_id=revoke_evidence.actor_evidence_ref_id,
                                action=action)
        self.assertRejected(self.admit(proposal, proof, evidence), "L04_NOT_ADMITTED", "REJECTED:CONSENT_REVOKED")
        self.assertIsNone(flow.links.get(proposal))

    def test_v1_path_row_is_never_laundered_into_v2(self):
        flow = self.flow
        action, proposal, proof, evidence = flow.create("SYNTH-LAUNDER", "db.launder")
        # A compromised app drives the unchanged V1 apply directly.
        self.assertEqual(flow.l04.store().apply(proposal).outcome, canonical_store.ACCEPTED)
        self.assertRejected(self.accept(proof, evidence, proposal), "ADMISSION_LINK_MISSING")
        # Even genuine owner authority cannot be attached after the fact.
        self.assertRejected(self.admit(proposal, proof, evidence), "L04_NOT_ADMITTED", "ALREADY_APPLIED")
        self.assertIsNone(flow.links.get(proposal))

    def test_db_only_admission_rows_and_forged_links_are_not_accepted(self):
        flow = self.flow
        action, proposal, proof, evidence = flow.create("SYNTH-REAL", "db.only")
        forged_action, forged_encoded = flow.l04.action("SYNTH-FORGED")
        forged_ref = flow.l04.proposal(forged_action, forged_encoded, nonce="db.forged")
        conn = flow.l04.raw()
        try:
            conn.execute("INSERT INTO memory_item VALUES (?,?,?,?,?)",
                         ("mitem.forged", *forged_action.identity, "2026-09-22T01:00:20Z"))
            conn.execute("INSERT INTO memory_admission VALUES (?,?,?,?,?,?)",
                         ("madm.forged", forged_ref, 1, "ACCEPTED", None, "2026-09-22T01:00:20Z"))
            conn.execute("INSERT INTO memory_revision VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                "mrev.forged", "mitem.forged", 1, learning_v2.VALUE_SCHEMA, forged_encoded,
                forged_action.payload_digest, forged_ref, None, None, "USER_ASSERTED", "OWNER_DIRECTED_EXACT_ACTION",
                None, None, None, "2026-09-22T01:00:20Z"))
            conn.execute("INSERT INTO memory_apply_audit VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                "mop.forged", forged_ref, "madm.forged", 1, C.CREATE, "mitem.forged", None, "mrev.forged",
                "mrev.forged", None, "2026-09-22T01:00:20Z"))
            conn.execute("INSERT INTO memory_active_revision VALUES (?,?,?,?)",
                         ("mitem.forged", "mrev.forged", "2026-09-22T01:00:20Z", "mop.forged"))
            conn.commit()
        finally:
            conn.close()
        view = AD.read_l04_admission_view(flow.l04.db, forged_ref, forged_action)
        self.assertEqual(view["admissionOutcome"], "ACCEPTED")  # it looks admitted
        forged_link = {"schemaVersion": 1, "proposalRefId": forged_ref, "admissionId": "madm.forged",
                       "applyAuditId": "mop.forged", "memoryItemId": "mitem.forged", "revisionId": "mrev.forged",
                       "authorityEvidenceId": evidence["evidenceId"],
                       "authorityEvidenceDigest": V2.evidence_digest(evidence),
                       "challengeId": evidence["challengeId"], "actionDigest": evidence["actionDigest"],
                       "payloadDigest": evidence["payloadDigest"]}
        base = dict(admission=view, link=forged_link)
        for label, replace, reason, detail in (
                ("no evidence", {"evidence": None, "link": None, "action": forged_action},
                 "AUTHORITY_EVIDENCE_MISSING", None),
                ("forged action vs real owner proof", {"action": forged_action}, "OWNER_PROOF_REJECTED",
                 "PAYLOAD_DIGEST_MISMATCH"),
                ("real authority, forged rows", {}, "ADMISSION_BINDING_MISMATCH", None),
                ("app-signed evidence", {"evidence": T.resign(evidence, T.TEST_ONLY_ROGUE_APP_SEED)},
                 "AUTHORITY_EVIDENCE_REJECTED", "SIGNATURE_INVALID")):
            with self.subTest(label=label):
                self.assertRejected(self.accept(proof, evidence, proposal, **{**base, **replace}), reason, detail)

    def test_db_writer_cannot_rewrite_the_admitted_value_or_basis(self):
        flow = self.flow
        _, proposal, proof, evidence = flow.create("SYNTH-KEEP", "db.rewrite")
        revision = self.admit(proposal, proof, evidence).facts["admission"]["revisionId"]
        self.assertEqual(self.accept(proof, evidence, proposal).status, V2.ACCEPTED_MEMORY)
        forged_value, _ = learning_v2.normalize_project_codename({"codename": "SYNTH-SWAPPED"})
        for column, value in (("normalized_value_json", forged_value), ("epistemic_basis", "MODEL_INFERRED")):
            with self.subTest(column=column):
                conn = flow.l04.raw()
                try:
                    triggers = {n: s for n, s in conn.execute(
                        "SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name='memory_revision'")}
                    for name in triggers:
                        conn.execute(f'DROP TRIGGER "{name}"')
                    original = conn.execute(f"SELECT {column} FROM memory_revision WHERE revision_id=?",
                                            (revision,)).fetchone()[0]
                    conn.execute(f"UPDATE memory_revision SET {column}=? WHERE revision_id=?", (value, revision))
                    conn.commit()
                    self.assertRejected(self.accept(proof, evidence, proposal), "ADMISSION_BINDING_MISMATCH")
                    conn.execute(f"UPDATE memory_revision SET {column}=? WHERE revision_id=?", (original, revision))
                    for sql in triggers.values():
                        conn.execute(sql)
                    conn.commit()
                finally:
                    conn.close()
        self.assertEqual(self.accept(proof, evidence, proposal).status, V2.ACCEPTED_MEMORY)

    def test_v2_modules_never_read_policy_consent_rollback_or_actor_rows(self):
        for module in (V2, AD):
            tree = ast.parse(inspect.getsource(module))
            names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)} | \
                    {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
            for forbidden in ("policy_store", "consent_store", "rollback_authority", "actor_authority",
                              "validate_existing", "resolve_and_consume"):
                with self.subTest(module=module.__name__, name=forbidden):
                    self.assertNotIn(forbidden, names)


# ------------------------------------------------ 11. old app HMAC key ---

class OldApplicationHmacKeyTests(FlowCase):
    def test_hmac_key_mints_v1_evidence_that_never_authorizes_v2(self):
        flow = self.flow
        action, proposal, proof, evidence = flow.create("SYNTH-HMAC", "hmac")
        attacker = CA.LocalOwnerAuthority(flow.l04.db, T.TEST_ONLY_V1_ACTOR_HMAC_SECRET, issuer_ref="attacker-app",
                                          now_fn=lambda: flow.l04.now)
        minted = attacker.issue(action=action, request_digest=T.digest("attacker"), nonce="hmac.attacker")
        # It verifies under V1 historical semantics...
        self.assertEqual(flow.l04.actor.validate_existing(minted.actor_evidence_ref_id, action=action), minted)
        baseline = flow.l04.counts()
        # ...but never on the V2 path, in object or dict form.
        for candidate in (minted, dict(minted.__dict__),
                          {"actorEvidenceRefId": minted.actor_evidence_ref_id,
                           "evidenceFingerprint": minted.evidence_fingerprint}):
            self.assertRejected(self.admit(proposal, proof, candidate), "NON_V2_EVIDENCE_NOT_ACCEPTED",
                                V2.ACTOR_EVIDENCE_REF_V1)
        self.assertEqual(flow.l04.counts(), baseline)

    def test_hmac_key_cannot_be_transformed_into_owner_evidence_v2(self):
        flow = self.flow
        action, proposal, proof, evidence = flow.create("SYNTH-HMAC2", "hmac2")
        secret = T.TEST_ONLY_V1_ACTOR_HMAC_SECRET
        unsigned = {k: v for k, v in evidence.items() if k != "signature"}
        mac = hmac.new(secret, A.owner_evidence_signing_bytes(unsigned), hashlib.sha512).digest()
        hmac_derived = hashlib.sha256(b"derive" + secret).digest()
        attempts = [
            ("HMAC tag as signature", {**unsigned, "signature": SA.b64(mac)}, "SIGNATURE_INVALID"),
            ("Ed25519 key derived from HMAC secret", T.resign(evidence, hmac_derived), "SIGNATURE_INVALID"),
            ("HMAC-derived key under a new keyId", T.resign(evidence, hmac_derived, keyId="actor.app-hmac"),
             "KEY_UNKNOWN"),
            ("HMAC secret used directly as an Ed25519 seed", T.resign(evidence, secret), "SIGNATURE_INVALID"),
        ]
        registered = {record["publicKey"] for record in flow.registry_doc["keys"]}
        self.assertNotIn(T.public_b64(hmac_derived), registered)
        self.assertNotIn(T.public_b64(secret), registered)
        for label, forged, detail in attempts:
            with self.subTest(label=label):
                self.assertRejected(self.admit(proposal, proof, forged), "AUTHORITY_EVIDENCE_REJECTED", detail)
        # And the full V1-forged chain cannot reach ACCEPTED_MEMORY on the new chain.
        self.assertEqual(flow.l04.store().apply(proposal).outcome, canonical_store.ACCEPTED)
        self.assertRejected(self.accept(proof, flow.l04.last["actor_evidence"], proposal),
                            "NON_V2_EVIDENCE_NOT_ACCEPTED", V2.ACTOR_EVIDENCE_REF_V1)
        self.assertRejected(self.accept(proof, attempts[1][1], proposal), "ADMISSION_LINK_MISSING")


# ---------------------------------------------------------- 12. Privacy ---

class PrivacyTests(FlowCase):
    def test_privacy_hold_suppression_and_unavailability_fail_closed(self):
        flow = self.flow
        _, proposal, proof, evidence = flow.create("SYNTH-PRIV", "privacy")
        baseline = flow.l04.counts()
        for attribute, reason in (("held", "PRIVACY_HOLD_ACTIVE"), ("suppressed", "PRIVACY_HOLD_ACTIVE"),
                                  ("unavailable", "PRIVACY_STATE_UNAVAILABLE")):
            with self.subTest(state=attribute):
                setattr(flow.l04.privacy, attribute, True)
                try:
                    self.assertRejected(self.admit(proposal, proof, evidence), reason)
                    # A forged or re-signed artifact cannot override Privacy either.
                    self.assertRejected(self.admit(proposal, proof, T.resign(evidence, T.TEST_ONLY_ROGUE_APP_SEED)),
                                        reason)
                finally:
                    setattr(flow.l04.privacy, attribute, False)
                self.assertEqual(flow.l04.counts(), baseline)
        self.assertEqual(self.admit(proposal, proof, evidence).status, AD.L04_ADMITTED)

    def test_l04_in_transaction_privacy_check_still_applies(self):
        flow = self.flow
        _, proposal, proof, evidence = flow.create("SYNTH-RACE", "privacy.race")
        calls = {"n": 0}

        def is_held(*_identity):
            calls["n"] += 1
            return calls["n"] > 1  # clear for the adapter's check, held inside L04

        flow.l04.privacy.is_held = is_held
        self.assertRejected(self.admit(proposal, proof, evidence), "L04_NOT_ADMITTED", "REJECTED:PRIVACY_HOLD_ACTIVE")
        self.assertIsNone(flow.links.get(proposal))

    def test_owner_evidence_never_verifies_as_privacy_authorization(self):
        flow = self.flow
        _, _, _, evidence = flow.create("SYNTH-ERASE", "privacy.erase")
        result = AV.verify_privacy_authorization(context=T.authority_context(), registry=flow.registry_doc,
                                                 authorization=evidence, expectation=SA.privacy_expectation())
        self.assertEqual((result.status, result.reason), (AV.NOT_ACCEPTED, "EVIDENCE_MALFORMED"))


# ------------------------------------------------ 13. registry evolution ---

class RegistryEvolutionTests(FlowCase):
    def next_key(self):
        return SA.key_record(T.NEXT_KEY_ID, seed_name="actor.current-2", publicKey=T.public_b64(T.TEST_ONLY_NEXT_SEED),
                             createdAt="2026-09-26T12:10:00Z", notBefore="2026-09-26T12:10:00Z", registryVersion=4)

    def test_in_flight_evidence_survives_harmless_update_and_dies_on_compromise(self):
        flow = self.flow
        _, proposal, proof, evidence = flow.create("SYNTH-FLIGHT", "registry.flight")
        _, pending_ref, pending_proof, pending = flow.create("SYNTH-PENDING", "registry.pending")
        # Harmless monotonic update: a new key is published at version 4.
        flow.registry_doc = T.registry(version=4, keys=T.registry_keys(self.next_key()),
                                       issued_at="2026-09-26T12:30:00Z")
        flow.adapter = flow.make_adapter(trusted_minimum_registry_version=4)
        admitted = self.admit(proposal, proof, evidence)
        self.assertEqual(admitted.status, AD.L04_ADMITTED, admitted)
        self.assertEqual((admitted.facts["authority"]["evidenceRegistryVersion"],
                          admitted.facts["authority"]["registryVersion"]), (3, 4))
        self.assertIs(admitted.facts["authority"]["historicalRegistrySnapshotVerified"], False)
        self.assertEqual(self.accept(proof, evidence, proposal,
                                     authority_context=T.authority_context(trusted_minimum_registry_version=4)
                                     ).status, V2.ACCEPTED_MEMORY)
        # Later COMPROMISED status invalidates every piece of evidence the key signed.
        flow.registry_doc = T.registry(version=5, issued_at="2026-09-26T13:00:00Z", keys=T.registry_keys(
            self.next_key(), broker=T.broker_key_record(revokedAt="2026-09-26T12:45:00Z",
                                                        revocationReason="COMPROMISED",
                                                        compromisedSince="2026-09-26T12:40:00Z")))
        flow.adapter = flow.make_adapter(trusted_minimum_registry_version=5)
        self.assertRejected(self.admit(pending_ref, pending_proof, pending), "AUTHORITY_EVIDENCE_REJECTED",
                            "KEY_COMPROMISED")
        historical = SA.historical_context(trusted_minimum_registry_version=5)
        self.assertRejected(self.accept(proof, evidence, proposal, authority_context=historical),
                            "AUTHORITY_EVIDENCE_REJECTED", "KEY_COMPROMISED")

    def test_routine_retirement_keeps_admitted_history_and_in_flight_evidence(self):
        flow = self.flow
        _, proposal, proof, evidence = flow.create("SYNTH-RETIRE", "registry.retire")
        created = self.admit(proposal, proof, evidence)
        self.assertEqual(created.status, AD.L04_ADMITTED)
        # Signed before the rotation, admitted after it.
        item = created.facts["admission"]["memoryItemId"]
        action2, encoded2 = flow.l04.action("SYNTH-RETIRE2", operation=C.SUPERSEDE,
                                            expected=created.facts["admission"]["revisionId"])
        pending_ref = flow.l04.proposal(action2, encoded2, nonce="registry.retire2")
        pending_proof = T.owner_proof(action2, "och.registry.retire2", memory_item_id=item)
        pending = flow.signed(pending_proof)
        flow.registry_doc = T.registry(version=4, issued_at="2026-09-26T13:00:00Z", keys=T.registry_keys(
            self.next_key(), broker=T.broker_key_record(retiredAt="2026-09-26T12:50:00Z")))
        flow.adapter = flow.make_adapter(trusted_minimum_registry_version=4)
        pending_result = self.admit(pending_ref, pending_proof, pending)
        self.assertEqual(pending_result.status, AD.L04_ADMITTED, pending_result)
        self.assertEqual(pending_result.facts["authority"]["keyStatus"], "RETIRED_AFTER_ISSUANCE")
        accepted = self.accept(proof, evidence, proposal,
                               authority_context=SA.historical_context(trusted_minimum_registry_version=4))
        self.assertEqual(accepted.status, V2.ACCEPTED_MEMORY)
        self.assertEqual(accepted.facts["authority"]["keyStatus"], "RETIRED_AFTER_ISSUANCE")
        # A new signature after retirement is refused for admission.
        late = T.resign(pending, issuedAt="2026-09-26T12:55:00Z")
        self.assertRejected(self.admit(pending_ref, pending_proof, late), "AUTHORITY_EVIDENCE_REJECTED", "KEY_RETIRED")


# -------------------------------------------- 14/17. structural isolation ---

def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            found.add(node.module or "")
            found |= {f"{node.module}.{alias.name}" for alias in node.names}
    return found


class StructuralIsolationTests(unittest.TestCase):
    def test_verifier_adapter_and_contract_modules_hold_no_private_key_or_signer(self):
        for path in sorted(PACKAGE.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            with self.subTest(module=path.name):
                for forbidden in ("Ed25519PrivateKey", "from_private_bytes", "private_bytes", "lilith_authority_signer",
                                  "synthetic_broker", "TEST_ONLY_BROKER_SEED", "SyntheticBrokerAuthority"):
                    self.assertNotIn(forbidden, source)
                self.assertFalse(any(name.startswith("lilith_authority_signer") for name in _imports(path)))

    def test_v2_modules_have_no_network_env_subprocess_or_config(self):
        for module in (V2, AD):
            imported = _imports(Path(module.__file__))
            source = inspect.getsource(module)
            with self.subTest(module=module.__name__):
                for forbidden in ("os", "subprocess", "socket", "urllib", "http", "requests", "lilith_memory_broker",
                                  "lilith_memory.config", "lilith_memory.privacy_governance"):
                    self.assertFalse(any(name == forbidden or name.startswith(forbidden + ".") for name in imported),
                                     forbidden)
                for forbidden in ("os.environ", "getenv", "open(", "LILITH_ENV", "/home/", '"prod"', '"dev"'):
                    self.assertNotIn(forbidden, source)
        # The adapter opens the L04 database read-only, and only to build a view.
        adapter_source = inspect.getsource(AD)
        self.assertEqual(adapter_source.count("sqlite3.connect("), 1)
        self.assertIn("?mode=ro", adapter_source)

    def test_signer_package_is_self_contained_and_side_effect_free(self):
        for path in sorted(SIGNER_PACKAGE.glob("*.py")):
            imported = _imports(path)
            source = path.read_text(encoding="utf-8")
            with self.subTest(module=path.name):
                for forbidden in ("os", "sys", "subprocess", "socket", "pathlib", "sqlite3", "urllib", "http",
                                  "requests", "lilith_memory_broker", "lilith_memory.config"):
                    self.assertFalse(any(name == forbidden or name.startswith(forbidden + ".") for name in imported),
                                     forbidden)
                # No seed or key literal: the key object always comes from the caller.
                for forbidden in ("open(", "os.environ", "getenv", 'b"TEST_ONLY', '"TEST_ONLY ', "from_private_bytes",
                                  "Path(", "sha256(b"):
                    self.assertNotIn(forbidden, source)

    def test_signer_and_v2_modules_are_not_reachable_from_runtime_code(self):
        root = SA.ROOT
        runtime = [p for p in list((root / "services/core-api").rglob("*.py"))
                   + list((root / "services/memory-broker").rglob("*.py")) + list((root / "scripts").rglob("*.py"))
                   if ".venv" not in p.parts and "tests" not in p.parts]
        self.assertTrue(runtime)
        for path in runtime:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for forbidden in ("lilith_authority_signer", "synthetic_broker", "l04_v2_adapter", "admission_v2",
                              "lilith_owner_memory"):
                with self.subTest(path=path.name, forbidden=forbidden):
                    # Whole identifiers only (L04's own `memory_admission_v2_new` table is not a reference).
                    self.assertIsNone(re.search(rf"(?<![A-Za-z0-9_]){forbidden}(?![A-Za-z0-9_])", text))
        package_init = (PACKAGE / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("import", package_init.split('"""', 2)[2])

    def test_verifier_entry_points_take_public_material_only(self):
        for function in (V2.verify_owner_authority, V2.verify_accepted_memory_v2, AD.L04V2AdmissionAdapter.__init__,
                         AV.verify_owner_evidence):
            parameters = set(inspect.signature(function).parameters)
            with self.subTest(function=function.__qualname__):
                self.assertFalse({p for p in parameters if "key" in p or "private" in p or "signer" in p
                                  or "seed" in p})


# ----------------------------------------------- 21. vectors and pins ---

GOLDEN_SHA256 = {
    "services/owner-memory-control/tests/authority_b1b3a_golden.json":
        "b7b09af86b51d16a5a4d4a53d54a21f70deace854c16c1b537ab04c1b1ab55c9",
    "services/owner-memory-control/tests/owner_memory_b2a_golden.json":
        "86c439583b0e7f74d5bec78f046f0d410cd4915d76bb3ee3f590fc47666f3a25",
    "services/core-api/tests/owner_proof_golden.jsonl":
        "e810a36be8d9a0f3233a174a5ddf4e33eafb4671d110abdfe503ded3d330d390",
}


def golden_document() -> dict:
    unsigned = SA.owner_evidence_unsigned(keyId=T.BROKER_KEY_ID)
    evidence = T.resign({**unsigned, "signature": ""})
    return {
        "note": "TEST_ONLY synthetic vectors for 15B2b-B1b-3b. No real key, owner, registry, memory, or authority.",
        "stages": [AV.VERIFIED_AUTHORITY_EVIDENCE, AD.L04_ADMITTED, V2.ACCEPTED_MEMORY],
        "semantics": {"admission": AD.ADMISSION_SEMANTICS, "acceptance": V2.ACCEPTANCE_V2_SEMANTICS},
        "l04V2Basis": {"epistemicBasis": V2.L04_V2_EPISTEMIC_BASIS, "admissionBasis": V2.L04_V2_ADMISSION_BASIS},
        "v2Reasons": list(V2.REASONS),
        "signerReasons": list(B.SIGNER_REASONS),
        "evidenceIdDomainSeparator": B.EVIDENCE_ID_DOMAIN_SEPARATOR.decode("ascii"),
        "brokerKeyId": T.BROKER_KEY_ID,
        "brokerPublicKey": T.public_b64(T.TEST_ONLY_BROKER_SEED),
        "brokerKeyRecord": T.broker_key_record(),
        "brokerSignedOwnerEvidenceV2": evidence,
        "brokerSignedOwnerEvidenceDigest": V2.evidence_digest(evidence),
        "linkFields": sorted(V2.LINK_FIELDS),
        "admissionViewFields": sorted(V2.ADMISSION_VIEW_FIELDS),
    }


class VectorTests(unittest.TestCase):
    def test_historical_vectors_are_unchanged(self):
        for relative, expected in GOLDEN_SHA256.items():
            with self.subTest(path=relative):
                self.assertEqual(hashlib.sha256((SA.ROOT / relative).read_bytes()).hexdigest(), expected)
        self.assertEqual(len(AV.REASONS), 44)
        self.assertEqual(A.OWNER_EVIDENCE_DOMAIN_SEPARATOR, b"LILITH_ACTOR_EVIDENCE_V2\x00")

    def test_b1b3b_golden_vectors(self):
        document = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        self.assertEqual(document, json.loads(json.dumps(golden_document())))
        evidence = document["brokerSignedOwnerEvidenceV2"]
        registry = T.registry()
        result = AV.verify_owner_evidence(context=T.authority_context(), registry=registry, evidence=evidence,
                                          expectation=SA.owner_expectation())
        self.assertEqual(result.status, AV.VERIFIED_AUTHORITY_EVIDENCE)
        self.assertEqual(len(set(V2.REASONS)), len(V2.REASONS))
        self.assertEqual(len(set(B.SIGNER_REASONS)), len(B.SIGNER_REASONS))


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["--write-golden"]:
        with GOLDEN_PATH.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(golden_document(), indent=2, sort_keys=True) + "\n")
    else:
        unittest.main()
