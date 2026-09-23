"""Synthetic broker orchestration; no listener, live credential, or B2 operation."""

from __future__ import annotations

import base64
import os
import secrets
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from typing import Callable

from lilith_memory import canonical_authority as A
from lilith_memory import owner_proof as P

from .protocol import BrokerMessageV1
from .request import (
    LOGICAL_OWNER_ID, SYNTHETIC_ACCESS_IDENTITY, SYNTHETIC_FIXTURE_ID,
    construct_synthetic_request,
)
from .state import OwnerControlState, TEST_MODE


class BrokerError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class SyntheticBrokerCore:
    """Only explicit test-mode construction can reach the synthetic issuer."""

    def __init__(
        self,
        state: OwnerControlState,
        authority: A.LocalOwnerAuthority,
        *,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        challenge_id_fn: Callable[[], str] = lambda: "och." + uuid.uuid4().hex,
        nonce_fn: Callable[[], bytes] = lambda: secrets.token_bytes(32),
    ):
        if state.mode != TEST_MODE or os.environ.get("LILITH_ENV") != "test":
            raise BrokerError("SYNTHETIC_BROKER_ONLY")
        if not isinstance(authority, A.LocalOwnerAuthority):
            raise BrokerError("SYNTHETIC_AUTHORITY_REQUIRED")
        state.validate_startup()
        self.state = state
        self.authority = authority
        self.now_fn = now_fn
        self.challenge_id_fn = challenge_id_fn
        self.nonce_fn = nonce_fn

    def _verifier(self) -> P.OwnerProofVerifier:
        return P.OwnerProofVerifier(
            self.state.challenge_store,
            owner_principal=SYNTHETIC_ACCESS_IDENTITY,
            rp_id=P.SYNTHETIC_RP_ID,
            origin=P.SYNTHETIC_ORIGIN,
            test_mode=True,
            now_fn=self.now_fn,
        )

    def prepare_synthetic(self, fixture_id: str = SYNTHETIC_FIXTURE_ID) -> P.OwnerMemoryChallengeV1:
        challenge_id = self.challenge_id_fn()
        request = construct_synthetic_request(challenge_id, fixture_id)
        now = self.now_fn()
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise BrokerError("INVALID_BROKER_CLOCK")
        nonce = self.nonce_fn()
        if not isinstance(nonce, bytes) or len(nonce) != 32:
            raise BrokerError("INVALID_BROKER_NONCE")
        encoded_nonce = base64.urlsafe_b64encode(nonce).rstrip(b"=").decode("ascii")
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
            "nonce": encoded_nonce,
            "issuedAt": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "expiresAt": (now + timedelta(seconds=60)).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "rpId": P.SYNTHETIC_RP_ID,
        })
        self.state.challenge_store.prepare(challenge)
        self.state.save_request_after_prepare(request)
        return challenge

    def confirm_synthetic(
        self,
        challenge_id: str,
        assertion: P.OwnerAssertionV1,
        *,
        fault_hook: Callable[[str], None] | None = None,
    ) -> dict[str, str]:
        request = self.state.request(challenge_id)
        if request.access_identity != SYNTHETIC_ACCESS_IDENTITY:
            raise BrokerError("ACCESS_IDENTITY_MISMATCH")
        proof = self._verifier().verify_and_consume(
            challenge_id, assertion,
            expected_action=request.action,
            expected_request_digest=request.request_digest,
            expected_memory_item_id=request.memory_item_id,
            expected_restore_target_digest=request.restore_target_digest,
            expected_privacy_notice_version=request.privacy_notice_version,
        )
        self._fault(fault_hook, "after_proof_consumed")
        self._fault(fault_hook, "before_claim_insert")
        self.state.claim(proof)
        self._fault(fault_hook, "after_claim_commit")
        self._fault(fault_hook, "before_evidence_issue")
        evidence = self.authority.issue(
            action=request.action,
            request_digest=request.request_digest,
            nonce=challenge_id,
        )
        self._fault(fault_hook, "after_evidence_commit")
        self._fault(fault_hook, "before_claim_linkage")
        self.state.link_evidence(
            challenge_id, evidence.actor_evidence_ref_id,
            request.request_digest, request.action.action_digest,
        )
        self._fault(fault_hook, "after_linkage")
        return {"status": "SYNTHETIC_EVIDENCE_COMMITTED", "challengeId": challenge_id}

    @staticmethod
    def _fault(hook: Callable[[str], None] | None, point: str) -> None:
        if hook:
            hook(point)

    def recover(self, challenge_id: str) -> dict[str, str]:
        """Never calls issue. Reconciliation can only link existing evidence."""
        request = self.state.request(challenge_id)
        claim = self.state.claim_row(challenge_id)
        if claim is None:
            if self.state.challenge_store.state(challenge_id) == "CONSUMED":
                return {"status": "PROOF_BURNED_NO_CLAIM", "challengeId": challenge_id}
            return {"status": "NO_CLAIM", "challengeId": challenge_id}
        if claim[1] != request.request_digest or claim[2] != request.action.action_digest:
            raise BrokerError("CLAIM_BINDING_MISMATCH")
        evidence = self._existing_evidence(challenge_id)
        if evidence is None:
            if claim[3] in {"CLAIMED", "ABANDONED"}:
                self.state.abandon(challenge_id, "EVIDENCE_ABSENT")
            return {"status": "EVIDENCE_ABSENT_NO_REISSUE", "challengeId": challenge_id}
        try:
            self.authority.validate_existing(
                evidence, action=request.action, request_digest=request.request_digest,
            )
        except A.ActorEvidenceError:
            if claim[3] == "CLAIMED":
                self.state.abandon(challenge_id, "EVIDENCE_INVALID")
            return {"status": "EVIDENCE_INVALID_NO_REISSUE", "challengeId": challenge_id}
        self.state.link_evidence(
            challenge_id, evidence, request.request_digest, request.action.action_digest,
        )
        return {"status": "EXISTING_EVIDENCE_RECONCILED", "challengeId": challenge_id}

    def _existing_evidence(self, challenge_id: str) -> str | None:
        # This seam is test-only; the later custody stage supplies a broker-owned
        # query adapter rather than granting a relay cognitive-DB access.
        path = self.authority.path
        if not path.is_file():
            raise BrokerError("SYNTHETIC_COGNITIVE_DB_MISSING")
        with closing(sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=5)) as conn:
            conn.execute("PRAGMA query_only=ON")
            row = conn.execute("SELECT actor_evidence_ref_id FROM actor_evidence_ref WHERE nonce=?", (challenge_id,)).fetchone()
        return str(row[0]) if row else None

    def dispatch(self, message: BrokerMessageV1) -> dict:
        """In-memory protocol adapter; proof observations never leave this method."""
        if message.operation == "HEALTH":
            return {"status": "SYNTHETIC_ONLY", "schemaVersion": 1}
        if message.operation == "ACCESS_CONTEXT":
            return {
                "logicalOwnerId": LOGICAL_OWNER_ID,
                "accessIdentity": SYNTHETIC_ACCESS_IDENTITY,
                "assurance": "UNVERIFIED_TRANSPORT_CONTEXT",
            }
        if message.operation == "PREPARE_SYNTHETIC":
            return {"challenge": self.prepare_synthetic(message.payload["fixtureId"]).to_dict()}
        if message.operation == "CANCEL":
            self.state.challenge_store.cancel(message.payload["challengeId"])
            return {"status": "CANCELLED_OR_TERMINAL"}
        if message.operation == "CONFIRM_SYNTHETIC":
            assertion = P.OwnerAssertionV1.from_dict(message.payload["assertion"])
            return self.confirm_synthetic(message.payload["challengeId"], assertion)
        raise BrokerError("UNSUPPORTED_OPERATION")
