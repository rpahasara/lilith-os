"""TEST_ONLY synthetic fixtures for 15B2b-B1b-3b.

Builds, entirely in-process and inside a temporary directory:

- the real, unchanged L04 `CanonicalMemoryStoreV2` with its 15B2a V1
  authorities (the V1 Actor HMAC secret here is a labelled TEST_ONLY constant);
- a synthetic owner chain (ES256 WebAuthn assertion over an
  OwnerMemoryChallengeV2) reusing the B2a fixtures;
- a TEST_ONLY broker signer with its own Ed25519 key, published in a registry
  signed by the B1b-3a synthetic registry root.

The broker key is distinct from the registry root, from every B1b-3a
authority key, and from the B2a synthetic broker key. No key is read from or
written to disk, the environment, a user directory, or a credential store.
No real owner, memory, registry, or authority exists.
"""

from __future__ import annotations

import dataclasses
import hashlib
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import synthetic_authority as SA
import synthetic_chain as SC
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from lilith_authority_signer import synthetic_broker as B
from lilith_memory import backup
from lilith_memory import canonical_authority as CA
from lilith_memory import canonical_contracts as C
from lilith_memory import canonical_migration
from lilith_memory import canonical_store
from lilith_memory import learning_v2
from lilith_memory import memory_store
from lilith_memory import memory_v2
from lilith_memory import slice15b2a_migration
from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import contracts as K
from lilith_owner_memory import l04_v2_adapter as AD

# ------------------------------------------------------------- constants ---

L04_CLASS = "SYNTHETIC_PROJECT_CODENAME_FACT"
L04_NAMESPACE = "project.synthetic"
L04_KEY = "codename"
L04_CAPABILITY = C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE
# Labelled TEST_ONLY stand-in for the application-owned 15B2a Actor HMAC key.
TEST_ONLY_V1_ACTOR_HMAC_SECRET = hashlib.sha256(b"TEST_ONLY 15B2a actor HMAC secret").digest()

BROKER_KEY_ID = "actor.b1b3b-broker-1"
TEST_ONLY_BROKER_SEED = hashlib.sha256(b"TEST_ONLY B1b-3b broker owner-actor signing key 1").digest()
TEST_ONLY_ROGUE_APP_SEED = hashlib.sha256(b"TEST_ONLY B1b-3b compromised application key").digest()
NEXT_KEY_ID = "actor.b1b3b-next-2"
TEST_ONLY_NEXT_SEED = hashlib.sha256(b"TEST_ONLY B1b-3b next broker key 2").digest()

CHALLENGE_ISSUED = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)


def l04_stamp(seconds: int = 0) -> datetime:
    return datetime(2026, 9, 22, 1, 0, tzinfo=timezone.utc) + timedelta(seconds=seconds)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class PrivacyState:
    """Synthetic Privacy resolver with the real `is_held` contract: a hold or a
    restore suppression both block. It can also be made unavailable."""

    def __init__(self) -> None:
        self.held = False
        self.suppressed = False
        self.unavailable = False

    def is_held(self, *_identity: str) -> bool:
        if self.unavailable:
            raise RuntimeError("privacy governance database is unavailable")
        return self.held or self.suppressed


class Clock:
    def __init__(self, value: datetime):
        self.value = value

    def __call__(self) -> datetime:
        return self.value


# ------------------------------------------------------------------ L04 ---

class L04Harness:
    """The real, unchanged L04 V2 store plus its V1 authorities in a temp dir."""

    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "cognitive.test.db"
        self.now = l04_stamp()
        memory_store.migrate(self.db, production_path=self.root / "not-production.db",
                             applied_at=CA.utc_now(l04_stamp()))
        old_proof = memory_store.create_verified_backup(self.db, self.root / "pre-15b2a.db")
        slice15b2a_migration.migrate_cognitive(self.db, verified_backup=old_proof, production_path=self.db,
                                               applied_at=CA.utc_now(l04_stamp(1)))
        manifest = backup.create_backup(self.db, self.root / "pre-15b2b.db",
                                        self.root / "pre-15b2b.manifest.json", role="cognitive")
        canonical_migration.migrate(self.db, backup_manifest=manifest, applied_at=CA.utc_now(l04_stamp(2)))
        self.privacy = PrivacyState()
        self.actor = CA.LocalOwnerAuthority(self.db, TEST_ONLY_V1_ACTOR_HMAC_SECRET, now_fn=lambda: self.now)
        self.policy = CA.MemoryPolicyStore(self.db, self.actor, active_capabilities=frozenset({L04_CAPABILITY}),
                                           now_fn=lambda: self.now)
        self.consent = CA.ConsentStore(self.db, self.actor, policy_store=self.policy, now_fn=lambda: self.now)
        self.rollback = CA.RollbackAuthority(self.db, self.actor, self.consent, now_fn=lambda: self.now)
        self.learning = learning_v2.LearningV2Store(
            self.db, privacy_hold_resolver=self.privacy, containment_ready=lambda: True,
            actor_authority=self.actor, policy_store=self.policy, consent_store=self.consent,
            now_fn=lambda: self.now)
        self.registry_policy = memory_v2.MemoryTuplePolicyV1(
            memory_class=L04_CLASS, subject_namespace=L04_NAMESPACE, subject_key=L04_KEY,
            value_schema=learning_v2.VALUE_SCHEMA, capability=L04_CAPABILITY, read_allowed=True,
            write_allowed=True)
        self.tuple_registry = memory_v2.CanonicalTupleRegistry((self.registry_policy,))

    def close(self) -> None:
        self.tmp.cleanup()

    def store(self, **overrides: Any) -> canonical_store.CanonicalMemoryStoreV2:
        values = {
            "enabled_provider": lambda: True,
            "capability_provider": lambda capability: capability == L04_CAPABILITY,
            "family_registry": memory_v2.ProposalFamilyRegistry(
                (learning_v2.V2_PROPOSAL_FAMILY, learning_v2.V1_PROPOSAL_FAMILY)),
            "memory_registry": self.tuple_registry,
            "containment_ready": lambda identity: identity == (L04_CLASS, L04_NAMESPACE, L04_KEY),
            "actor_authority": self.actor,
            "policy_store": self.policy,
            "consent_store": self.consent,
            "rollback_authority": self.rollback,
            "privacy_hold_resolver": self.privacy,
            "now_fn": lambda: CA.utc_now(l04_stamp(20)),
        }
        values.update(overrides)
        return canonical_store.CanonicalMemoryStoreV2(self.db, self.learning, **values)

    def action(self, value: str | None, *, operation: str = C.CREATE, expected: str | None = None,
               restore: str | None = None, restore_digest: str | None = None, subject_key: str = L04_KEY):
        if operation in {C.CREATE, C.SUPERSEDE}:
            encoded, payload = learning_v2.normalize_project_codename({"codename": value})
            schema = learning_v2.VALUE_SCHEMA
        else:
            encoded, payload, schema = None, str(restore_digest), None
        return C.FrozenMemoryActionV1(
            schema_version=1, actor_ref_id=self.actor.ACTOR.actor_ref_id, operation=operation,
            memory_class=L04_CLASS, subject_namespace=L04_NAMESPACE, subject_key=subject_key,
            value_schema=schema, payload_digest=payload, expected_active_revision_id=expected,
            restore_revision_id=restore, purpose=C.LONG_TERM_PERSONAL_PROJECT_RECALL), encoded

    def proposal(self, action: C.FrozenMemoryActionV1, encoded: str | None, *, nonce: str,
                 memory_item_id: str | None = None) -> str:
        """Create the V1-era internal-state rows L04 requires (Actor evidence,
        Policy, Consent, candidate, optional Rollback) and the V2 proposal
        reference. These rows are application-owned internal state."""
        evidence = self.actor.issue(action=action, request_digest=digest("request:" + nonce), nonce=nonce)
        decision = self.policy.decide(action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                                      capability=L04_CAPABILITY)
        challenge = self.consent.create_challenge(action=action,
                                                  actor_evidence_ref_id=evidence.actor_evidence_ref_id,
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
        rollback_id = None
        if action.operation == C.RESTORE:
            rollback_id = self.rollback.authorize(
                action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                consent_ref_id=consent.consent_id, memory_item_id=str(memory_item_id),
                confirmation_event_ref="confirm." + nonce).rollback_authorization_ref_id
        _proposal, ref = self.learning.create_proposal(candidate_id=candidate.candidate_id, action=action,
                                                       rollback_authorization_ref_id=rollback_id)
        self.last = {"actor_evidence": evidence, "policy": decision, "consent": consent, "rollback": rollback_id}
        return ref.proposal_ref_id

    def counts(self) -> dict[str, int]:
        conn = sqlite3.connect(self.db)
        try:
            return {table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
                    for table in ("memory_item", "memory_revision", "memory_revision_source", "memory_admission",
                                  "memory_apply_audit", "memory_active_revision", "rollback_consumption")}
        finally:
            conn.close()

    def raw(self) -> sqlite3.Connection:
        """A direct cognitive-DB writer: no authorizer, no store API."""
        conn = sqlite3.connect(self.db)
        conn.execute("PRAGMA foreign_keys=OFF")
        return conn


# ----------------------------------------------------------- authority ---

def broker_private() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(TEST_ONLY_BROKER_SEED)


def public_b64(seed: bytes) -> str:
    return SA.public_b64(Ed25519PrivateKey.from_private_bytes(seed))


def broker_key_record(**overrides: Any) -> dict[str, Any]:
    return SA.key_record(BROKER_KEY_ID, seed_name="actor.current-2", publicKey=public_b64(TEST_ONLY_BROKER_SEED),
                         createdAt="2026-09-26T00:00:00Z", notBefore="2026-09-26T00:00:00Z",
                         registryVersion=3, **overrides)


def registry_keys(*extra: dict[str, Any], broker: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    keys = SA.default_keys() + [broker or broker_key_record(), *extra]
    return sorted(keys, key=lambda record: record["keyId"])


def registry(*, version: int = SA.REGISTRY_VERSION, keys: list[dict[str, Any]] | None = None,
             issued_at: str = SA.REGISTRY_ISSUED_AT, signer: str = "root") -> dict[str, Any]:
    return SA.registry(signer, keys=registry_keys() if keys is None else keys, registryVersion=version,
                       issuedAt=issued_at)


def authority_context(**overrides: Any) -> A.AuthorityVerificationContextV1:
    return SA.context(**overrides)


def owner_context(**overrides: Any) -> K.AcceptanceContextV1:
    # The owner challenge names the same policy as the authority registry.
    return SC.context(policy_version=SA.POLICY, **overrides)


def signer_config(**overrides: Any) -> B.BrokerSignerConfigV1:
    value = dict(environment="test", key_id=BROKER_KEY_ID, authority_domain=SA.LOGICAL_AUTHORITY_DOMAIN,
                 logical_owner_id=SA.LOGICAL_OWNER, registry_version=SA.REGISTRY_VERSION,
                 recovery_epoch=SA.EPOCH, policy_version=SA.POLICY)
    value.update(overrides)
    return B.BrokerSignerConfigV1(**value)


def broker(clock: Clock, *, key: Ed25519PrivateKey | None = None, **config: Any) -> B.SyntheticBrokerAuthorityV1:
    return B.SyntheticBrokerAuthorityV1(signing_key=key or broker_private(), config=signer_config(**config),
                                        owner_context=owner_context(), now_fn=clock)


# -------------------------------------------------------------- owner ---

@dataclasses.dataclass
class OwnerProof:
    action: C.FrozenMemoryActionV1
    challenge: K.OwnerMemoryChallengeV2
    challenge_json: bytes
    assertion: dict[str, Any]
    credential: dict[str, Any]


def owner_proof(action: C.FrozenMemoryActionV1, challenge_id: str, *, memory_item_id: str | None = None,
                **challenge_overrides: Any) -> OwnerProof:
    """A synthetic owner WebAuthn proof over a V2 challenge for `action`."""
    value = SC.challenge_dict(action, challengeId=challenge_id, policyVersion=SA.POLICY,
                              requestDigest=digest("TEST_ONLY owner request:" + challenge_id),
                              memoryItemId=memory_item_id)
    value.update(challenge_overrides)
    challenge = K.OwnerMemoryChallengeV2.from_dict(value)
    return OwnerProof(action, challenge, challenge.canonical_bytes(),
                      SC.assertion_dict(challenge.webauthn_challenge()), SC.credential_dict())


class Flow:
    """One complete synthetic V2 flow over a real temporary L04."""

    def __init__(self, harness: L04Harness | None = None) -> None:
        self.l04 = harness or L04Harness()
        self.clock = Clock(CHALLENGE_ISSUED + timedelta(seconds=20))
        self.broker = broker(self.clock)
        self.registry_doc = registry()
        self.links = AD.AdmissionLinkStoreV1()
        self.adapter = self.make_adapter()

    def make_adapter(self, **context: Any) -> AD.L04V2AdmissionAdapter:
        return AD.L04V2AdmissionAdapter(self.l04.store(), owner_context=owner_context(),
                                        authority_context=authority_context(**context),
                                        registry_provider=lambda: self.registry_doc, link_store=self.links)

    def signed(self, proof: OwnerProof) -> dict[str, Any]:
        """Owner proof → challenge consumed → broker-signed OwnerEvidenceV2."""
        assert self.broker.prepare_challenge(proof.challenge_json).status == B.PREPARED
        self.clock.value = CHALLENGE_ISSUED + timedelta(seconds=20)
        consumed = self.broker.consume_owner_proof(proof.challenge["challengeId"], action=proof.action,
                                                   assertion=proof.assertion, owner_credential=proof.credential)
        assert consumed.status == B.CONSUMED, consumed
        self.clock.value = CHALLENGE_ISSUED + timedelta(seconds=21)
        issued = self.broker.issue_owner_evidence(B.OwnerEvidenceRequestV1(
            proof.challenge["challengeId"], proof.action, proof.assertion, proof.credential))
        assert issued.status == B.ISSUED, issued
        return dict(issued.evidence)

    def request(self, proposal_ref_id: str, proof: OwnerProof, evidence: Any, /, **replace: Any):
        value = dict(proposal_ref_id=proposal_ref_id, evidence=evidence, challenge_json=proof.challenge_json,
                     challenge_record=self.broker.ledger_record(proof.challenge["challengeId"]),
                     assertion=proof.assertion, owner_credential=proof.credential)
        value.update(replace)
        return AD.V2AdmissionRequestV1(**value)

    def create(self, value: str = "SYNTH-ALPHA", nonce: str = "b1b3b.create"):
        action, encoded = self.l04.action(value)
        proposal = self.l04.proposal(action, encoded, nonce=nonce)
        proof = owner_proof(action, "och." + nonce)
        evidence = self.signed(proof)
        return action, proposal, proof, evidence

    def acceptance_kwargs(self, proof: OwnerProof, evidence: Any, proposal_ref_id: str, /, **replace: Any):
        value = dict(owner_context=owner_context(), authority_context=authority_context(), action=proof.action,
                     challenge_json=proof.challenge_json,
                     challenge_record=self.broker.ledger_record(proof.challenge["challengeId"]),
                     assertion=proof.assertion, owner_credential=proof.credential, registry=self.registry_doc,
                     evidence=evidence, admission=AD.read_l04_admission_view(self.l04.db, proposal_ref_id,
                                                                            proof.action),
                     link=self.links.get(proposal_ref_id))
        value.update(replace)
        return value


def resign(evidence: dict[str, Any], seed: bytes = TEST_ONLY_BROKER_SEED, **overrides: Any) -> dict[str, Any]:
    """Re-sign evidence with a raw key: models an attacker or a misused key,
    never the signer's normal path."""
    unsigned = {k: v for k, v in evidence.items() if k != "signature"}
    unsigned.update(overrides)
    key = Ed25519PrivateKey.from_private_bytes(seed)
    return {**unsigned, "signature": SA.b64(key.sign(A.owner_evidence_signing_bytes(unsigned)))}
