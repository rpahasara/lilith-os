"""F2/F3 over the synthetic V2 First Interaction flow: evidence-gated candidates and verified identity environment.

- The L18 V2 evidence gate (Core API `conversation_evidence.FirstInteractionEvidenceGate`) runs inside the genuine
  candidate path: a value whose identity binding is not the trusted IdentityProfileV1's, or whose transcript is not
  sealed evidence, never becomes an intent or candidate.
- Candidate creation is not acceptance: before an admission verifies, V2 reads NOT_READABLE and Identity V1 refuses.
- F3: IDENTITY_BOUND requires the trusted profile's environment to equal the environment of the owner-authority
  evidence that V2 verification verified. A profile and identity context from another environment are refused even
  when the admitted value carries that profile's exact binding.

Synthetic fixtures only (labelled TEST_ONLY dialogue, synthetic owner proof, test-harness signer, synthetic profile).
"""

from __future__ import annotations

import sqlite3
import unittest

import synthetic_first_memory as SF
import synthetic_fm02_l04 as FX
import synthetic_identity as SI
from lilith_memory import learning_v2
from lilith_owner_memory import admission_v2 as V2
from lilith_owner_memory import identity_profile as IP
from lilith_owner_memory import l04_v2_adapter as AD


class GatedFlowCase(unittest.TestCase):
    def setUp(self):
        self.flow = FX.FirstInteractionFlow()
        self.addCleanup(self.flow.l04.close)

    def fi_rows(self) -> int:
        conn = sqlite3.connect(self.flow.l04.db)
        try:
            return sum(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                       for t in ("learning_fi_intent_v1", "learning_fi_candidate_v1"))
        finally:
            conn.close()


class CandidateGateTests(GatedFlowCase):
    def test_trusted_identity_is_the_identity_profile_binding(self):
        trusted = IP.first_interaction_trusted_identity(SI.profile())
        self.assertEqual((trusted.environment, trusted.binding), ("test", SI.profile().binding()))
        with self.assertRaises(IP.IdentityContractViolation):
            IP.first_interaction_trusted_identity(SI.profile().binding())

    def test_payload_identity_or_unsealed_transcript_never_becomes_a_candidate(self):
        other = SI.profile(lilith_identity_id="lid1." + "cd" * 16)
        invented = SF.value(transcript=dict(SF.value()["transcript"], evidenceRef="evidence.test-only.invented"))
        for i, (value, reason) in enumerate(((SF.value(identityBinding=other.binding()), "IDENTITY_BINDING_MISMATCH"),
                                             (invented, "EVIDENCE_UNKNOWN"))):
            with self.subTest(reason=reason):
                with self.assertRaisesRegex(learning_v2.LearningV2Error, reason):
                    self.flow.create_fi(value, f"fm02.refused.{i}")
                self.assertEqual(self.fi_rows(), 0)

    def test_candidate_creation_is_not_first_memory_acceptance(self):
        action, proposal, proof, evidence = self.flow.create_fi()
        self.assertEqual(self.fi_rows(), 2)                                   # one intent, one candidate
        self.assertEqual(self.flow.read_fi().reason, "NOT_READABLE")
        bound = IP.verify_identity_bound_memory_v1(
            admitted_value=SF.canonical(), identity_context=SI.context(),
            **self.flow.acceptance_kwargs(proof, evidence, proposal))
        self.assertEqual((bound.status, bound.reason), (IP.IDENTITY_NOT_BOUND, "ACCEPTED_MEMORY_REQUIRED"))


class VerifiedEnvironmentTests(GatedFlowCase):
    def test_identity_environment_must_equal_the_verified_authority_environment(self):
        dev = SI.profile(environment="dev")
        dev_context = SI.context(environment="dev", trusted_profile=dev)
        # The candidate gate trusts the dev profile for a dev deployment; the V2 authority that verifies is TEST.
        self.flow.l04.learning.first_interaction_evidence_gate = FX.evidence_gate(
            self.flow.l04.evidence, profile=dev, deployment_environment="dev")
        value = SF.value(identityBinding=dev.binding())
        _action, proposal, proof, evidence = self.flow.create_fi(value, "fm02.dev")
        self.assertEqual(self.flow.adapter.admit(self.flow.request(proposal, proof, evidence)).status,
                         AD.L04_ADMITTED)
        v2_inputs = self.flow.acceptance_kwargs(proof, evidence, proposal)
        accepted = V2.verify_accepted_memory_v2(**v2_inputs)
        self.assertEqual((accepted.status, accepted.facts["authority"]["environment"]), (V2.ACCEPTED_MEMORY, "test"))
        admitted = self.flow.read_fi().row["normalized_value_json"]
        bound = IP.verify_identity_bound_memory_v1(admitted_value=admitted, identity_context=dev_context, **v2_inputs)
        self.assertEqual((bound.status, bound.reason), (IP.IDENTITY_NOT_BOUND, "IDENTITY_ENVIRONMENT_MISMATCH"))

    def test_matching_environment_still_binds(self):
        _action, proposal, proof, evidence = self.flow.create_fi()
        self.assertEqual(self.flow.adapter.admit(self.flow.request(proposal, proof, evidence)).status,
                         AD.L04_ADMITTED)
        bound = IP.verify_identity_bound_memory_v1(
            admitted_value=self.flow.read_fi().row["normalized_value_json"], identity_context=SI.context(),
            **self.flow.acceptance_kwargs(proof, evidence, proposal))
        self.assertEqual(bound.status, IP.IDENTITY_BOUND, bound)


if __name__ == "__main__":
    unittest.main()
