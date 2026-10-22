"""TEST-ONLY synthetic harness for the FM-02 First Interaction L04 family.

Extends the B1b-3b harness: the same real L04, the same synthetic owner WebAuthn proof, broker signer, evidence-use
ledger and durable A1-A7 link store, over a temporary database that this harness migrates to schema v2 with the
reviewed `first_interaction_migration`. Both families are registered; the codename path is untouched. Nothing here
creates a real identity, conversation or memory: the value is the labelled synthetic FM-02 fixture.
"""

from __future__ import annotations

import os
from typing import Any

import synthetic_b1b3b as T
import synthetic_first_memory as SF
from lilith_memory import backup
from lilith_memory import canonical_authority as CA
from lilith_memory import canonical_contracts as C
from lilith_memory import first_interaction_migration as FIM
from lilith_memory import learning_v2
from lilith_memory import memory_action_v2 as MA
from lilith_memory import memory_v2
from lilith_memory import privacy_governance as P
from lilith_memory import slice15b2a_migration

FI_CLASS, FI_NAMESPACE, FI_KEY = MA.FIRST_INTERACTION_IDENTITY
FI_CAPABILITY = MA.CANONICAL_MEMORY_FIRST_INTERACTION_CREATE
FI_PURPOSE = MA.OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION
TEST_ONLY_PRIVACY_SECRET = b"TEST_ONLY FM-02 privacy governance secret, 32+ bytes"


def migrate_v2(harness: T.L04Harness, *, tag: str = "fm02", **kwargs: Any) -> dict[str, str]:
    manifest = backup.create_backup(harness.db, harness.root / f"pre-{tag}.db",
                                    harness.root / f"pre-{tag}.manifest.json", role="cognitive")
    return FIM.migrate(harness.db, backup_manifest=manifest, applied_at=CA.utc_now(T.l04_stamp(3)), **kwargs)


class FirstInteractionHarness(T.L04Harness):
    """The B1b-3b L04 harness at schema v2, with both families registered."""

    def __init__(self, *, migrate: bool = True) -> None:
        super().__init__()
        if migrate:
            self.fingerprints = migrate_v2(self)
        both = frozenset({T.L04_CAPABILITY, FI_CAPABILITY})
        self.policy = CA.MemoryPolicyStore(self.db, self.actor, active_capabilities=both, now_fn=lambda: self.now)
        self.consent = CA.ConsentStore(self.db, self.actor, policy_store=self.policy, now_fn=lambda: self.now)
        self.rollback = CA.RollbackAuthority(self.db, self.actor, self.consent, now_fn=lambda: self.now)
        self.learning = learning_v2.LearningV2Store(
            self.db, privacy_hold_resolver=self.privacy, containment_ready=lambda: True,
            actor_authority=self.actor, policy_store=self.policy, consent_store=self.consent,
            now_fn=lambda: self.now)
        self.fi_policy = memory_v2.MemoryTuplePolicyV1(
            memory_class=FI_CLASS, subject_namespace=FI_NAMESPACE, subject_key=FI_KEY,
            value_schema=MA.FIRST_INTERACTION_VALUE_SCHEMA, capability=FI_CAPABILITY, read_allowed=True,
            write_allowed=True)
        self.tuple_registry = memory_v2.CanonicalTupleRegistry((self.registry_policy, self.fi_policy))

    def store(self, **overrides: Any):
        values = {
            "capability_provider": lambda capability: capability in {T.L04_CAPABILITY, FI_CAPABILITY},
            "family_registry": memory_v2.ProposalFamilyRegistry(
                (learning_v2.V2_PROPOSAL_FAMILY, learning_v2.V1_PROPOSAL_FAMILY,
                 learning_v2.FIRST_INTERACTION_PROPOSAL_FAMILY)),
            "containment_ready": lambda identity: identity in {(T.L04_CLASS, T.L04_NAMESPACE, T.L04_KEY),
                                                               MA.FIRST_INTERACTION_IDENTITY},
        }
        values.update(overrides)
        return super().store(**values)

    def fi_action(self, value: dict | None = None, *, operation: str = C.CREATE, **fields: Any):
        """(action, canonical) for the synthetic FM-02 value, built with the L04-owned normalizer."""
        encoded, payload = learning_v2.normalize_for_purpose(FI_PURPOSE, SF.value() if value is None else value)
        spec = dict(schema_version=1, actor_ref_id=self.actor.ACTOR.actor_ref_id, operation=operation,
                    memory_class=FI_CLASS, subject_namespace=FI_NAMESPACE, subject_key=FI_KEY,
                    value_schema=MA.FIRST_INTERACTION_VALUE_SCHEMA, payload_digest=payload,
                    expected_active_revision_id=None, restore_revision_id=None, purpose=FI_PURPOSE)
        spec.update(fields)
        return MA.action_from_fields(**spec), encoded

    def proposal(self, action: C.FrozenMemoryActionV1, encoded: str | None, *, nonce: str,
                 memory_item_id: str | None = None) -> str:
        """The B1b-3b internal-state rows with the capability the action's purpose selects."""
        evidence = self.actor.issue(action=action, request_digest=T.digest("request:" + nonce), nonce=nonce)
        decision = self.policy.decide(action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                                      capability=MA.capability_for_purpose(action.purpose))
        challenge = self.consent.create_challenge(action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                                                  policy_decision_ref_id=decision.decision_ref_id)
        intent_ref_id = "intent." + nonce
        consent = self.consent.confirm(challenge.challenge_id, action=action,
                                       issuer_ref="synthetic-home-confirmation", intent_ref_id=intent_ref_id,
                                       privacy_notice_version="privacy-v1")
        intent = self.learning.create_intent(action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                                             normalized_value_json=encoded, intent_ref_id=intent_ref_id)
        candidate = self.learning.create_candidate(
            action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            intent_ref_id=intent.intent_ref_id, policy_decision_ref_id=decision.decision_ref_id,
            consent_ref_id=consent.consent_id)
        assert self.learning.assess(candidate.candidate_id) == learning_v2.REAL_ELIGIBLE
        _proposal, ref = self.learning.create_proposal(candidate_id=candidate.candidate_id, action=action)
        self.last = {"actor_evidence": evidence, "policy": decision, "consent": consent, "candidate": candidate}
        return ref.proposal_ref_id

    def privacy_store(self) -> P.PrivacyGovernanceStore:
        """The real Privacy Governance store in its own database (hold + monotonic restore suppression)."""
        path = self.root / "privacy.test.db"
        if not path.exists():
            slice15b2a_migration.migrate_privacy(path, applied_at=CA.utc_now(T.l04_stamp(4)))
            if os.name != "nt":
                os.chmod(path, 0o600)
        return P.PrivacyGovernanceStore(path, TEST_ONLY_PRIVACY_SECRET, self.actor, now_fn=lambda: self.now)


class FirstInteractionFlow(T.Flow):
    """One complete synthetic V2 flow for the First Interaction family, durable A1-A7 links."""

    def __init__(self, harness: FirstInteractionHarness | None = None, *, durable: bool = True) -> None:
        super().__init__(harness or FirstInteractionHarness(), durable=durable)

    def create_fi(self, value: dict | None = None, nonce: str = "fm02.create"):
        action, encoded = self.l04.fi_action(value)
        proposal = self.l04.proposal(action, encoded, nonce=nonce)
        proof = T.owner_proof(action, "och." + nonce)
        evidence = self.signed(proof)
        return action, proposal, proof, evidence

    def read_fi(self, reader=None, actor: Any = "owner"):
        return (reader or self.reader()).read_accepted(
            actor=self.l04.actor.ACTOR if actor == "owner" else actor,
            memory_class=FI_CLASS, subject_namespace=FI_NAMESPACE, subject_key=FI_KEY)
