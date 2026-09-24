"""Persistent DEV-only synthetic broker; never issues ActorEvidence."""

from __future__ import annotations

import base64
import json
import os
import re
import secrets
import signal
import stat
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import rfc8785

from lilith_memory import owner_proof as P

from .dev_config import DevConfig, PROFILE, fixture_fingerprint
from .dev_state import DevOwnerControlState
from .protocol import BrokerMessageV1
from .request import LOGICAL_OWNER_ID, SYNTHETIC_ACCESS_IDENTITY, SYNTHETIC_FIXTURE_ID, OwnerRequestV1, construct_synthetic_request
from .synthetic_evidence import SyntheticEvidenceStore, schema_fingerprint as evidence_schema_fingerprint


class DevBrokerError(RuntimeError):
    pass


A2_FAULT_POINT = "A2_AFTER_PROOF_CONSUME_BEFORE_CLAIM"
A2_EXPERIMENT_ID = "B1B2B_III_A_A2_V1"
A2_ARM_DIRECTORY = Path("/run/lilith-memory-stage3")
A2_ARM_NAME = "a2-arm.json"
A2_ACCEPTED_BASELINE_DIGEST = "abc33ebf8d43e8805f43ff11e663a4757bf558d9b62eda9669dabecbb7c9839a"
A2_ACCEPTED_RELEASE = "817a83e44cec8965479fd97fc30b7a0b3ae49ab2"
A2_MAX_ARM_BYTES = 4096
_A2_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_A2_HEX = re.compile(r"[0-9a-f]{64}\Z")
_A2_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_A2_FIELDS = frozenset({
    "schemaVersion", "experimentId", "stage", "faultPoint",
    "deploymentEnvironment", "authorityMode", "stateProfile", "canonicalCapability",
    "logicalOwnerId", "accessIdentity", "credentialRecordId", "fixtureId",
    "fixtureFingerprint", "instrumentedReleaseId", "stage2AcceptedBaselineDigest",
    "stage3AuthorizationId", "challengeId", "requestDigest", "actionDigest",
    "issuedAt", "expiresAt", "armNonce",
})


def _a2_unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise DevBrokerError("A2_ARM_DUPLICATE_FIELD")
        result[key] = value
    return result


def _a2_utc(value: object) -> datetime:
    if not isinstance(value, str) or not _A2_UTC.fullmatch(value):
        raise DevBrokerError("A2_ARM_TIME_FORMAT")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DevBrokerError("A2_ARM_TIME_INVALID") from exc


@dataclass(frozen=True)
class Stage3FaultArmV1:
    experiment_id: str
    authorization_id: str
    release_id: str
    challenge_id: str
    request_digest: str
    action_digest: str
    arm_nonce: str

    @classmethod
    def from_bytes(cls, raw: bytes, *, config: DevConfig, now: datetime) -> Stage3FaultArmV1:
        try:
            value = json.loads(raw.decode("utf-8"), object_pairs_hook=_a2_unique_pairs,
                               parse_constant=lambda _item: (_ for _ in ()).throw(ValueError("constant")))
            if not isinstance(value, dict) or set(value) != _A2_FIELDS or raw != rfc8785.dumps(value):
                raise DevBrokerError("A2_ARM_SCHEMA")
        except (UnicodeError, ValueError, TypeError, OverflowError, rfc8785.CanonicalizationError) as exc:
            raise DevBrokerError("A2_ARM_JSON") from exc
        expected = {
            "schemaVersion": 1, "experimentId": A2_EXPERIMENT_ID,
            "stage": "B1B2B_III_A", "faultPoint": A2_FAULT_POINT,
            "deploymentEnvironment": "DEV", "authorityMode": "SYNTHETIC_ONLY",
            "stateProfile": PROFILE, "canonicalCapability": "DISABLED",
            "logicalOwnerId": LOGICAL_OWNER_ID,
            "accessIdentity": SYNTHETIC_ACCESS_IDENTITY,
            "credentialRecordId": "ocred.synthetic", "fixtureId": SYNTHETIC_FIXTURE_ID,
            "fixtureFingerprint": fixture_fingerprint(),
            "instrumentedReleaseId": config.release_sha,
            "stage2AcceptedBaselineDigest": A2_ACCEPTED_BASELINE_DIGEST,
        }
        if (type(value["schemaVersion"]) is not int or
                any(value[key] != required for key, required in expected.items()) or
                config.release_sha == A2_ACCEPTED_RELEASE):
            raise DevBrokerError("A2_ARM_GUARD")
        for key in ("stage3AuthorizationId", "challengeId"):
            if not isinstance(value[key], str) or not _A2_ID.fullmatch(value[key]):
                raise DevBrokerError("A2_ARM_ID")
        for key in ("requestDigest", "actionDigest", "armNonce"):
            if not isinstance(value[key], str) or not _A2_HEX.fullmatch(value[key]):
                raise DevBrokerError("A2_ARM_HEX")
        issued = _a2_utc(value["issuedAt"])
        expires = _a2_utc(value["expiresAt"])
        if (now.tzinfo is None or now.utcoffset() != timedelta(0) or
                not issued <= now < expires or
                not timedelta(0) < expires - issued <= timedelta(seconds=60)):
            raise DevBrokerError("A2_ARM_EXPIRED_OR_INVALID_WINDOW")
        return cls(value["experimentId"], value["stage3AuthorizationId"],
                   value["instrumentedReleaseId"], value["challengeId"],
                   value["requestDigest"], value["actionDigest"], value["armNonce"])

    def matches(self, proof: P.OwnerProofVerificationResultV1, request: OwnerRequestV1) -> bool:
        return (self.challenge_id == proof.challenge_id == request.challenge_id and
                self.request_digest == proof.request_digest == request.request_digest and
                self.action_digest == proof.action_digest == request.action.action_digest and
                proof.credential_record_id == "ocred.synthetic" and
                proof.owner_principal == SYNTHETIC_ACCESS_IDENTITY and
                request.access_identity == SYNTHETIC_ACCESS_IDENTITY)


def _load_stage3_arm(config: DevConfig, now: datetime) -> Stage3FaultArmV1 | None:
    """Fixed root:broker 0750 directory and root:broker 0640 file; never create."""
    if os.name != "posix" or not all(hasattr(os, item) for item in ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC")):
        return None  # Operational A2 is Linux-only; no fallback to an unsafe open.
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        parent_fd = os.open(A2_ARM_DIRECTORY, flags)
    except FileNotFoundError:
        return None
    try:
        parent = os.fstat(parent_fd)
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0 or
                parent.st_gid != os.getgid() or stat.S_IMODE(parent.st_mode) != 0o750 or
                os.geteuid() == 0):
            raise DevBrokerError("A2_ARM_DIRECTORY_CUSTODY")
        try:
            arm_fd = os.open(A2_ARM_NAME, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                             dir_fd=parent_fd)
        except FileNotFoundError:
            return None
        try:
            arm = os.fstat(arm_fd)
            if (not stat.S_ISREG(arm.st_mode) or arm.st_uid != 0 or
                    arm.st_gid != os.getgid() or stat.S_IMODE(arm.st_mode) != 0o640 or
                    arm.st_nlink != 1 or not 0 < arm.st_size <= A2_MAX_ARM_BYTES):
                raise DevBrokerError("A2_ARM_FILE_CUSTODY")
            raw = os.read(arm_fd, A2_MAX_ARM_BYTES + 1)
            if len(raw) != arm.st_size or len(raw) > A2_MAX_ARM_BYTES:
                raise DevBrokerError("A2_ARM_SIZE_CHANGED")
            return Stage3FaultArmV1.from_bytes(raw, config=config, now=now)
        finally:
            os.close(arm_fd)
    finally:
        os.close(parent_fd)


def _a2_barrier(arm: Stage3FaultArmV1, now: datetime) -> None:
    """Evidence-only stderr event, then deterministic whole-process stop; never kill."""
    event = {
        "eventType": "STAGE3_A2_BARRIER_V1", "experimentId": arm.experiment_id,
        "faultPoint": A2_FAULT_POINT, "brokerPid": os.getpid(),
        "instrumentedReleaseId": arm.release_id, "challengeId": arm.challenge_id,
        "requestDigest": arm.request_digest, "actionDigest": arm.action_digest,
        "timestamp": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    os.write(2, rfc8785.dumps(event) + b"\n")
    os.kill(os.getpid(), signal.SIGSTOP)


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
        # Recheck the pinned public credential before each proof. The shared
        # engine owns verification; this guard closes a mutable-state gap
        # between broker startup and a later synthetic confirmation.
        self.state.validate_startup()
        request = self.state.request(challenge_id)
        if request.access_identity != SYNTHETIC_ACCESS_IDENTITY:
            raise DevBrokerError("ACCESS_IDENTITY_MISMATCH")
        proof = P.DevSyntheticOwnerProofVerifier(self.state.challenge_store, now_fn=self.now_fn).verify_and_consume(
            challenge_id, assertion, expected_action=request.action,
            expected_request_digest=request.request_digest,
            expected_memory_item_id=request.memory_item_id,
            expected_restore_target_digest=request.restore_target_digest,
            expected_privacy_notice_version=request.privacy_notice_version,
        )
        # The shared verifier has committed CONSUMED (and any counter update).
        # A2 is the sole operational fault point, before claim() opens its transaction.
        a2_now = self.now_fn()
        arm = _load_stage3_arm(self.config, a2_now)
        if arm is not None and arm.matches(proof, request):
            _a2_barrier(arm, a2_now)
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
