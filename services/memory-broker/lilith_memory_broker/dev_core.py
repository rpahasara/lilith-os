"""Persistent DEV-only synthetic broker; never issues ActorEvidence."""

from __future__ import annotations

import base64
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable

from lilith_memory import owner_proof as P

from .dev_config import DevConfig
from .dev_proof import DevSyntheticProofVerifier
from .dev_state import DevOwnerControlState
from .protocol import BrokerMessageV1
from .request import SYNTHETIC_ACCESS_IDENTITY, SYNTHETIC_FIXTURE_ID, construct_synthetic_request
from .synthetic_evidence import SyntheticEvidenceStore, schema_fingerprint as evidence_schema_fingerprint


class DevBrokerError(RuntimeError):
    pass


class DevSyntheticBrokerCore:
    def __init__(
        self, config: DevConfig, state: DevOwnerControlState, evidence: SyntheticEvidenceStore,
        *, hostname: str, machine_id: str, release_sha: str,
        now_fn: Callable[[], datetime] | None = None,
        challenge_id_fn: Callable[[], str] | None = None,
        nonce_fn: Callable[[], bytes] | None = None,
    ):
        config.validate_runtime(hostname=hostname, machine_id=machine_id, release_sha=release_sha)
        if state.config != config or evidence.release_sha != config.release_sha or evidence_schema_fingerprint() != config.evidence_schema_fingerprint:
            raise DevBrokerError("DEV_STATE_BINDING_MISMATCH")
        if state.path.resolve() == evidence.path.resolve() or state.path.parent.resolve() == evidence.path.parent.resolve():
            raise DevBrokerError("SYNTHETIC_STORES_NOT_SEPARATED")
        state.validate_startup()
        evidence.validate_startup()
        self.config = config
        self.state = state
        self.evidence = evidence
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self.challenge_id_fn = challenge_id_fn or (lambda: "och." + uuid.uuid4().hex)
        self.nonce_fn = nonce_fn or (lambda: secrets.token_bytes(32))

    def prepare_synthetic(self, fixture_id: str = SYNTHETIC_FIXTURE_ID) -> P.OwnerMemoryChallengeV1:
        challenge_id = self.challenge_id_fn()
        request = construct_synthetic_request(challenge_id, fixture_id)
        now = self.now_fn()
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise DevBrokerError("INVALID_BROKER_CLOCK")
        nonce = self.nonce_fn()
        if not isinstance(nonce, bytes) or len(nonce) != 32:
            raise DevBrokerError("INVALID_BROKER_NONCE")
        challenge = P.OwnerMemoryChallengeV1.from_dict({
            "protocol": P.PROTOCOL, "schemaVersion": 1,
            "ownerPrincipal": request.access_identity,
            "challengeId": request.challenge_id,
            "actionDigest": request.action.action_digest,
            "requestDigest": request.request_digest,
            "payloadDigest": request.action.payload_digest,
            "operation": request.action.operation,
            "memoryClass": request.action.memory_class,
            "subjectNamespace": request.action.subject_namespace,
            "subjectKey": request.action.subject_key,
            "purpose": request.action.purpose,
            "memoryItemId": request.memory_item_id,
            "expectedActiveRevisionId": request.action.expected_active_revision_id,
            "restoreTargetRevisionId": request.action.restore_revision_id,
            "restoreTargetDigest": request.restore_target_digest,
            "privacyNoticeVersion": request.privacy_notice_version,
            "nonce": base64.urlsafe_b64encode(nonce).rstrip(b"=").decode("ascii"),
            "issuedAt": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "expiresAt": (now + timedelta(seconds=60)).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "rpId": P.SYNTHETIC_RP_ID,
        })
        self.state.challenge_store.prepare(challenge)
        self.state.save_request_after_prepare(request)
        return challenge

    def confirm_synthetic(self, challenge_id: str, assertion: P.OwnerAssertionV1, *, fault_hook: Callable[[str], None] | None = None) -> dict[str, str]:
        request = self.state.request(challenge_id)
        if request.access_identity != SYNTHETIC_ACCESS_IDENTITY:
            raise DevBrokerError("ACCESS_IDENTITY_MISMATCH")
        proof = DevSyntheticProofVerifier(self.state.challenge_store, now_fn=self.now_fn).verify_and_consume(
            challenge_id, assertion, expected_action=request.action,
            expected_request_digest=request.request_digest,
            expected_memory_item_id=request.memory_item_id,
            expected_restore_target_digest=request.restore_target_digest,
            expected_privacy_notice_version=request.privacy_notice_version,
        )
        if fault_hook:
            fault_hook("after_proof_consumed")
        self.state.claim(proof)
        if fault_hook:
            fault_hook("after_claim_commit")
        evidence = self.evidence.commit_once(
            challenge_id=challenge_id, request_digest=request.request_digest,
            action_digest=request.action.action_digest,
            credential_record_id=proof.credential_record_id,
            fixture_marker=SYNTHETIC_FIXTURE_ID,
        )
        if fault_hook:
            fault_hook("after_evidence_commit")
        self.state.link_evidence(challenge_id, evidence.synthetic_evidence_id, request.request_digest, request.action.action_digest)
        return {"status": "SYNTHETIC_EVIDENCE_COMMITTED", "challengeId": challenge_id}

    def recover(self, challenge_id: str) -> dict[str, str]:
        """Reconcile an existing synthetic record; never issue during recovery."""
        request = self.state.request(challenge_id)
        claim = self.state.claim_row(challenge_id)
        if claim is None:
            if self.state.challenge_store.state(challenge_id) == "CONSUMED":
                return {"status": "PROOF_BURNED_NO_CLAIM", "challengeId": challenge_id}
            return {"status": "NO_CLAIM", "challengeId": challenge_id}
        _, request_digest, action_digest, credential_id, status, evidence_id = claim
        if request_digest != request.request_digest or action_digest != request.action.action_digest:
            raise DevBrokerError("CLAIM_BINDING_MISMATCH")
        evidence = self.evidence.find(challenge_id)
        if evidence is None:
            if status == "CLAIMED":
                self.state.abandon(challenge_id)
            return {"status": "EVIDENCE_ABSENT_NO_REISSUE", "challengeId": challenge_id}
        if (evidence.request_digest, evidence.action_digest, evidence.synthetic_credential_record_id, evidence.fixture_marker) != (
            request_digest, action_digest, credential_id, SYNTHETIC_FIXTURE_ID,
        ) or (evidence_id is not None and evidence_id != evidence.synthetic_evidence_id):
            raise DevBrokerError("SYNTHETIC_EVIDENCE_BINDING_MISMATCH")
        self.state.link_evidence(challenge_id, evidence.synthetic_evidence_id, request_digest, action_digest)
        return {"status": "EXISTING_SYNTHETIC_EVIDENCE_RECONCILED", "challengeId": challenge_id}

    def dispatch(self, message: BrokerMessageV1) -> dict:
        if os.environ.get("LILITH_ENV") != "dev":
            raise DevBrokerError("DEV_ONLY")
        if message.operation == "HEALTH":
            return {"status": "SYNTHETIC_DEV_ONLY", "schemaVersion": 1}
        if message.operation == "PREPARE_SYNTHETIC":
            return {"challenge": self.prepare_synthetic(message.payload["fixtureId"]).to_dict()}
        if message.operation == "CANCEL":
            self.state.challenge_store.cancel(message.payload["challengeId"])
            return {"status": "CANCELLED_OR_TERMINAL"}
        if message.operation == "CONFIRM_SYNTHETIC":
            assertion = P.OwnerAssertionV1.from_dict(message.payload["assertion"])
            return self.confirm_synthetic(message.payload["challengeId"], assertion)
        raise DevBrokerError("UNSUPPORTED_DEV_OPERATION")
