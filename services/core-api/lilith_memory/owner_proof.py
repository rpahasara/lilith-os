"""Synthetic-only Slice 15B2b-B1a owner-proof verification contracts.

This module has no owner-authority issuer, route, registration ceremony, or
canonical-memory connection. A successful result is NOT ActorEvidence.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping

import rfc8785
from fido2 import cbor
from fido2.cose import CoseKey
from fido2.server import Fido2Server
from fido2.webauthn import (
    AttestedCredentialData,
    AuthenticationResponse,
    AuthenticatorAssertionResponse,
    AuthenticatorData,
    CollectedClientData,
    PublicKeyCredentialRpEntity,
    UserVerificationRequirement,
)

from .canonical_contracts import FrozenMemoryActionV1


PROTOCOL = "LILITH_OWNER_MEMORY_PROOF"
SCHEMA_VERSION = 1
DOMAIN_SEPARATOR = b"LILITH_OWNER_MEMORY_CHALLENGE_V1\x00"
SYNTHETIC_RP_ID = "owner.lilith.invalid"
SYNTHETIC_ORIGIN = "https://owner.lilith.invalid"
MAX_CHALLENGE_SECONDS = 60
MAX_ASSERTION_BYTES = 4096
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_B64U = re.compile(r"[A-Za-z0-9_-]+\Z")

# python-fido2 logs raw credential IDs at INFO on success. Only the record ID
# belongs in B1a operational logging; suppress the dependency's INFO output.
logging.getLogger("fido2.server").setLevel(logging.WARNING)


class OwnerProofError(ValueError):
    """Closed failure; never contains assertion bytes or memory values."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _exact(data: Mapping[str, Any], fields: frozenset[str]) -> None:
    if not isinstance(data, Mapping) or set(data) != fields:
        raise OwnerProofError("INVALID_FIELDS")


def _text(value: Any, name: str, maximum: int = 128) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise OwnerProofError("INVALID_" + name.upper())
    return value


def _id(value: Any, name: str) -> str:
    if not _ID.fullmatch(_text(value, name)):
        raise OwnerProofError("INVALID_" + name.upper())
    return value


def _digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise OwnerProofError("INVALID_" + name.upper())
    return value


def _optional_id(value: Any, name: str) -> str | None:
    return None if value is None else _id(value, name)


def _b64u_decode(value: Any, name: str, minimum: int, maximum: int) -> bytes:
    if not isinstance(value, str) or not _B64U.fullmatch(value):
        raise OwnerProofError("INVALID_" + name.upper())
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, base64.binascii.Error) as exc:
        raise OwnerProofError("INVALID_" + name.upper()) from exc
    if not minimum <= len(raw) <= maximum or _b64u(raw) != value:
        raise OwnerProofError("INVALID_" + name.upper())
    return raw


def _b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _instant(value: Any) -> datetime:
    if not isinstance(value, str) or not _TIME.fullmatch(value):
        raise OwnerProofError("INVALID_TIMESTAMP")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise OwnerProofError("INVALID_TIMESTAMP") from exc


def _json_object(raw: bytes, *, allowed: frozenset[str]) -> dict[str, Any]:
    if len(raw) > MAX_ASSERTION_BYTES:
        raise OwnerProofError("ASSERTION_TOO_LARGE")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise OwnerProofError("DUPLICATE_JSON_FIELD")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except (UnicodeError, ValueError, TypeError) as exc:
        raise OwnerProofError("INVALID_CLIENT_DATA") from exc
    if not isinstance(value, dict) or not set(value) <= allowed:
        raise OwnerProofError("INVALID_CLIENT_DATA")
    return value


_CHALLENGE_FIELDS = frozenset({
    "protocol", "schemaVersion", "ownerPrincipal", "challengeId",
    "actionDigest", "requestDigest", "payloadDigest", "operation", "memoryClass",
    "subjectNamespace", "subjectKey", "purpose", "memoryItemId",
    "expectedActiveRevisionId", "restoreTargetRevisionId",
    "restoreTargetDigest", "privacyNoticeVersion", "nonce", "issuedAt",
    "expiresAt", "rpId",
})


@dataclass(frozen=True)
class OwnerMemoryChallengeV1:
    protocol: str
    schema_version: int
    owner_principal: str
    challenge_id: str
    action_digest: str
    request_digest: str
    payload_digest: str
    operation: str
    memory_class: str
    subject_namespace: str
    subject_key: str
    purpose: str
    memory_item_id: str | None
    expected_active_revision_id: str | None
    restore_target_revision_id: str | None
    restore_target_digest: str | None
    privacy_notice_version: str
    nonce: str
    issued_at: str
    expires_at: str
    rp_id: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> OwnerMemoryChallengeV1:
        _exact(value, _CHALLENGE_FIELDS)
        result = cls(
            value["protocol"], value["schemaVersion"], value["ownerPrincipal"],
            value["challengeId"], value["actionDigest"], value["requestDigest"], value["payloadDigest"],
            value["operation"], value["memoryClass"], value["subjectNamespace"],
            value["subjectKey"], value["purpose"], value["memoryItemId"],
            value["expectedActiveRevisionId"], value["restoreTargetRevisionId"],
            value["restoreTargetDigest"], value["privacyNoticeVersion"],
            value["nonce"], value["issuedAt"], value["expiresAt"], value["rpId"],
        )
        result.validate()
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "schemaVersion": self.schema_version,
            "ownerPrincipal": self.owner_principal,
            "challengeId": self.challenge_id,
            "actionDigest": self.action_digest,
            "requestDigest": self.request_digest,
            "payloadDigest": self.payload_digest,
            "operation": self.operation,
            "memoryClass": self.memory_class,
            "subjectNamespace": self.subject_namespace,
            "subjectKey": self.subject_key,
            "purpose": self.purpose,
            "memoryItemId": self.memory_item_id,
            "expectedActiveRevisionId": self.expected_active_revision_id,
            "restoreTargetRevisionId": self.restore_target_revision_id,
            "restoreTargetDigest": self.restore_target_digest,
            "privacyNoticeVersion": self.privacy_notice_version,
            "nonce": self.nonce,
            "issuedAt": self.issued_at,
            "expiresAt": self.expires_at,
            "rpId": self.rp_id,
        }

    def validate(self) -> None:
        if self.protocol != PROTOCOL or type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise OwnerProofError("UNSUPPORTED_CHALLENGE_VERSION")
        _text(self.owner_principal, "owner_principal", 256)
        if not self.owner_principal.startswith("user:"):
            raise OwnerProofError("INVALID_OWNER")
        _id(self.challenge_id, "challenge_id")
        _digest(self.action_digest, "action_digest")
        _digest(self.request_digest, "request_digest")
        _digest(self.payload_digest, "payload_digest")
        if self.operation not in {"CREATE", "SUPERSEDE", "RESTORE", "FORGET"}:
            raise OwnerProofError("INVALID_OPERATION")
        _id(self.memory_class, "memory_class")
        _id(self.subject_namespace, "subject_namespace")
        _id(self.subject_key, "subject_key")
        _id(self.purpose, "purpose")
        _optional_id(self.memory_item_id, "memory_item_id")
        _optional_id(self.expected_active_revision_id, "expected_revision")
        _optional_id(self.restore_target_revision_id, "restore_revision")
        if self.restore_target_digest is not None:
            _digest(self.restore_target_digest, "restore_digest")
        _id(self.privacy_notice_version, "privacy_notice_version")
        if len(_b64u_decode(self.nonce, "nonce", 32, 32)) != 32:
            raise OwnerProofError("INVALID_NONCE")
        issued, expires = _instant(self.issued_at), _instant(self.expires_at)
        if not 0 < (expires - issued).total_seconds() <= MAX_CHALLENGE_SECONDS:
            raise OwnerProofError("INVALID_LIFETIME")
        _text(self.rp_id, "rp_id", 253)
        if self.operation == "CREATE" and any((self.memory_item_id, self.expected_active_revision_id, self.restore_target_revision_id, self.restore_target_digest)):
            raise OwnerProofError("INVALID_ACTION_SHAPE")
        if self.operation == "SUPERSEDE" and (not self.memory_item_id or not self.expected_active_revision_id or self.restore_target_revision_id or self.restore_target_digest):
            raise OwnerProofError("INVALID_ACTION_SHAPE")
        if self.operation == "RESTORE" and not all((self.memory_item_id, self.expected_active_revision_id, self.restore_target_revision_id, self.restore_target_digest)):
            raise OwnerProofError("INVALID_ACTION_SHAPE")
        if self.operation == "FORGET" and (self.expected_active_revision_id or self.restore_target_revision_id or self.restore_target_digest):
            raise OwnerProofError("INVALID_ACTION_SHAPE")
        if self.operation == "RESTORE" and self.restore_target_digest != self.payload_digest:
            raise OwnerProofError("INVALID_RESTORE_DIGEST")

    def canonical_bytes(self) -> bytes:
        self.validate()
        try:
            return rfc8785.dumps(self.to_dict())
        except rfc8785.CanonicalizationError as exc:
            raise OwnerProofError("INVALID_CANONICALIZATION") from exc

    def webauthn_challenge(self) -> bytes:
        return hashlib.sha256(DOMAIN_SEPARATOR + self.canonical_bytes()).digest()


_CREDENTIAL_FIELDS = frozenset({
    "schemaVersion", "recordId", "ownerPrincipal", "credentialId",
    "publicKeyCose", "algorithm", "rpId", "status", "createdAt",
    "revokedAt", "lastObservedSignCount",
})


@dataclass(frozen=True)
class OwnerCredentialV1:
    schema_version: int
    record_id: str
    owner_principal: str
    credential_id: str
    public_key_cose: str
    algorithm: int
    rp_id: str
    status: str
    created_at: str
    revoked_at: str | None
    last_observed_sign_count: int

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> OwnerCredentialV1:
        _exact(value, _CREDENTIAL_FIELDS)
        result = cls(*(value[key] for key in (
            "schemaVersion", "recordId", "ownerPrincipal", "credentialId",
            "publicKeyCose", "algorithm", "rpId", "status", "createdAt",
            "revokedAt", "lastObservedSignCount",
        )))
        result.validate()
        return result

    def validate(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise OwnerProofError("UNSUPPORTED_CREDENTIAL_VERSION")
        _id(self.record_id, "record_id")
        _text(self.owner_principal, "owner_principal", 256)
        _b64u_decode(self.credential_id, "credential_id", 16, 1024)
        _b64u_decode(self.public_key_cose, "public_key", 16, 2048)
        if type(self.algorithm) is not int or self.algorithm != -7:
            raise OwnerProofError("UNSUPPORTED_ALGORITHM")
        _text(self.rp_id, "rp_id", 253)
        if self.status not in {"ACTIVE", "REVOKED"}:
            raise OwnerProofError("INVALID_CREDENTIAL_STATUS")
        _instant(self.created_at)
        if self.status == "ACTIVE" and self.revoked_at is not None:
            raise OwnerProofError("INVALID_REVOCATION")
        if self.status == "REVOKED" and (self.revoked_at is None or _instant(self.revoked_at) < _instant(self.created_at)):
            raise OwnerProofError("INVALID_REVOCATION")
        if type(self.last_observed_sign_count) is not int or not 0 <= self.last_observed_sign_count <= 2**32 - 1:
            raise OwnerProofError("INVALID_SIGN_COUNT")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schemaVersion": self.schema_version,
            "recordId": self.record_id,
            "ownerPrincipal": self.owner_principal,
            "credentialId": self.credential_id,
            "publicKeyCose": self.public_key_cose,
            "algorithm": self.algorithm,
            "rpId": self.rp_id,
            "status": self.status,
            "createdAt": self.created_at,
            "revokedAt": self.revoked_at,
            "lastObservedSignCount": self.last_observed_sign_count,
        }


_ASSERTION_FIELDS = frozenset({"credentialRecordId", "credentialId", "clientDataJSON", "authenticatorData", "signature"})


@dataclass(frozen=True)
class OwnerAssertionV1:
    credential_record_id: str
    credential_id: str
    client_data_json: str
    authenticator_data: str
    signature: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> OwnerAssertionV1:
        _exact(value, _ASSERTION_FIELDS)
        result = cls(*(value[key] for key in (
            "credentialRecordId", "credentialId", "clientDataJSON",
            "authenticatorData", "signature",
        )))
        result.validate()
        return result

    def validate(self) -> None:
        _id(self.credential_record_id, "record_id")
        _b64u_decode(self.credential_id, "credential_id", 16, 1024)
        _b64u_decode(self.client_data_json, "client_data", 1, 2048)
        _b64u_decode(self.authenticator_data, "authenticator_data", 37, 1024)
        _b64u_decode(self.signature, "signature", 1, 512)


@dataclass(frozen=True)
class OwnerProofVerificationResultV1:
    """Proof observation only: NOT ActorEvidence or mutation permission."""

    challenge_id: str
    credential_record_id: str
    owner_principal: str
    action_digest: str
    request_digest: str
    observed_sign_count: int
    counter_risk: bool
    status: str = "VERIFIED_PROOF_ONLY"


class DurableOwnerChallengeStore:
    """Separate B1a ledger; no canonical or Privacy database access."""

    def __init__(self, path: Path):
        self.path = Path(path)
        if self.path.name in {"cognitive_memory.db", "privacy_governance.db", "lilith.db"}:
            raise OwnerProofError("GOVERNED_DATABASE_FORBIDDEN")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=5, isolation_level=None)
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def initialize(self) -> None:
        if not self.path.parent.is_dir():
            raise OwnerProofError("STORE_PARENT_UNAVAILABLE")
        with closing(self._connect()) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS owner_proof_challenge_v1 (
                challenge_id TEXT PRIMARY KEY,
                challenge_json BLOB NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('PREPARED','CANCELLED','EXPIRED','CONSUMED')),
                consumed_credential_record_id TEXT,
                consumed_at TEXT
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS owner_proof_test_credential_v1 (
                record_id TEXT PRIMARY KEY,
                credential_json BLOB NOT NULL
            )""")

    def replace_synthetic_test_credential(self, credential: OwnerCredentialV1) -> None:
        """Fixture provisioning only; not a registration or enrollment API."""
        credential.validate()
        if os.environ.get("LILITH_ENV") != "test" or credential.rp_id != SYNTHETIC_RP_ID or not credential.owner_principal.endswith("@example.invalid"):
            raise OwnerProofError("TEST_CREDENTIAL_INSTALL_FORBIDDEN")
        with closing(self._connect()) as conn:
            conn.execute("INSERT OR REPLACE INTO owner_proof_test_credential_v1(record_id,credential_json) VALUES(?,?)", (credential.record_id, rfc8785.dumps(credential.to_dict())))

    def prepare(self, challenge: OwnerMemoryChallengeV1) -> None:
        canonical = challenge.canonical_bytes()
        with closing(self._connect()) as conn:
            try:
                conn.execute("INSERT INTO owner_proof_challenge_v1(challenge_id,challenge_json,state) VALUES(?,?,'PREPARED')", (challenge.challenge_id, canonical))
            except sqlite3.IntegrityError as exc:
                raise OwnerProofError("CHALLENGE_EXISTS") from exc

    def cancel(self, challenge_id: str) -> None:
        _id(challenge_id, "challenge_id")
        with closing(self._connect()) as conn:
            conn.execute("UPDATE owner_proof_challenge_v1 SET state='CANCELLED' WHERE challenge_id=? AND state='PREPARED'", (challenge_id,))

    def state(self, challenge_id: str) -> str:
        _id(challenge_id, "challenge_id")
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT state FROM owner_proof_challenge_v1 WHERE challenge_id=?", (challenge_id,)).fetchone()
        return str(row[0]) if row else "UNKNOWN"


class _OwnerProofPolicyKind(Enum):
    B1A_EXISTING = "B1A_EXISTING"
    B1A_EXISTING_TEST_MODE = "B1A_EXISTING_TEST_MODE"
    DEV_SYNTHETIC = "DEV_SYNTHETIC"


_DEV_SYNTHETIC_OWNER = "user:synthetic-owner@example.invalid"


@dataclass(frozen=True)
class _OwnerProofVerificationPolicyV1:
    """Trusted construction policy; never parsed from an assertion or request.

    The shared engine owns every verification and durable-consumption step.
    This policy only pins the expected identity, RP, origin and environment.
    """

    kind: _OwnerProofPolicyKind
    owner_principal: str
    rp_id: str
    origin: str

    def _b1a_test_allowed(self) -> bool:
        return self.kind is _OwnerProofPolicyKind.B1A_EXISTING_TEST_MODE and os.environ.get("LILITH_ENV") == "test"

    def validate_construction(self) -> None:
        if type(self.kind) is not _OwnerProofPolicyKind:
            raise OwnerProofError("UNSUPPORTED_OWNER_PROOF_POLICY")
        if self.kind in (_OwnerProofPolicyKind.B1A_EXISTING, _OwnerProofPolicyKind.B1A_EXISTING_TEST_MODE):
            # Preserve the existing B1a constructor guard and error ordering.
            if (self.rp_id.endswith(".invalid") or self.origin.endswith(".invalid")) and not self._b1a_test_allowed():
                raise OwnerProofError("SYNTHETIC_RP_FORBIDDEN")
        elif self.kind is _OwnerProofPolicyKind.DEV_SYNTHETIC:
            self._validate_dev()
        else:
            raise OwnerProofError("UNSUPPORTED_OWNER_PROOF_POLICY")
        if not self.origin.startswith("https://") or not (self.origin == "https://" + self.rp_id or self.origin.endswith("." + self.rp_id)):
            raise OwnerProofError("INVALID_ORIGIN_CONFIGURATION")

    def validate_verification(self) -> None:
        if type(self.kind) is not _OwnerProofPolicyKind:
            raise OwnerProofError("UNSUPPORTED_OWNER_PROOF_POLICY")
        if self.kind in (_OwnerProofPolicyKind.B1A_EXISTING, _OwnerProofPolicyKind.B1A_EXISTING_TEST_MODE):
            # B1a historically checks the synthetic RP again at use time.
            if self.rp_id.endswith(".invalid") and not self._b1a_test_allowed():
                raise OwnerProofError("SYNTHETIC_RP_FORBIDDEN")
        elif self.kind is _OwnerProofPolicyKind.DEV_SYNTHETIC:
            self._validate_dev()
        else:
            raise OwnerProofError("UNSUPPORTED_OWNER_PROOF_POLICY")

    def _validate_dev(self) -> None:
        if os.environ.get("LILITH_ENV") != "dev":
            raise OwnerProofError("DEV_SYNTHETIC_ENV_REQUIRED")
        if (self.owner_principal, self.rp_id, self.origin) != (
            _DEV_SYNTHETIC_OWNER, SYNTHETIC_RP_ID, SYNTHETIC_ORIGIN
        ):
            raise OwnerProofError("INVALID_DEV_SYNTHETIC_POLICY")


class _OwnerProofVerificationEngine:
    """Only assertion-verification and atomic-consumption implementation."""

    def __init__(self, store: DurableOwnerChallengeStore, policy: _OwnerProofVerificationPolicyV1, *, now_fn: Callable[[], datetime] | None = None):
        policy.validate_construction()
        self.store = store
        self.__policy = policy
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))

    @property
    def owner_principal(self) -> str:
        return self.__policy.owner_principal

    @property
    def rp_id(self) -> str:
        return self.__policy.rp_id

    @property
    def origin(self) -> str:
        return self.__policy.origin

    def verify_and_consume(
        self, challenge_id: str, assertion: OwnerAssertionV1,
        *, expected_action: FrozenMemoryActionV1,
        expected_request_digest: str,
        expected_memory_item_id: str | None,
        expected_restore_target_digest: str | None,
        expected_privacy_notice_version: str,
    ) -> OwnerProofVerificationResultV1:
        _id(challenge_id, "challenge_id")
        self.__policy.validate_verification()
        assertion.validate()
        expected_action.validate()
        _digest(expected_request_digest, "request_digest")
        conn = self.store._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT challenge_json,state FROM owner_proof_challenge_v1 WHERE challenge_id=?", (challenge_id,)).fetchone()
            if row is None:
                raise OwnerProofError("UNKNOWN_CHALLENGE")
            if row[1] != "PREPARED":
                raise OwnerProofError("CHALLENGE_NOT_PREPARED")
            raw = bytes(row[0])
            challenge_data = _json_object(raw, allowed=_CHALLENGE_FIELDS)
            challenge = OwnerMemoryChallengeV1.from_dict(challenge_data)
            if raw != challenge.canonical_bytes():
                raise OwnerProofError("NONCANONICAL_STORED_CHALLENGE")
            now = self._trusted_now()
            if now >= _instant(challenge.expires_at):
                conn.execute("UPDATE owner_proof_challenge_v1 SET state='EXPIRED' WHERE challenge_id=? AND state='PREPARED'", (challenge_id,))
                conn.commit()
                raise OwnerProofError("CHALLENGE_EXPIRED")
            if now < _instant(challenge.issued_at):
                raise OwnerProofError("CHALLENGE_NOT_YET_VALID")
            if (
                challenge.challenge_id != challenge_id
                or challenge.owner_principal != self.owner_principal
                or challenge.rp_id != self.rp_id
                or challenge.action_digest != expected_action.action_digest
                or challenge.request_digest != expected_request_digest
                or challenge.payload_digest != expected_action.payload_digest
                or challenge.operation != expected_action.operation
                or challenge.memory_class != expected_action.memory_class
                or challenge.subject_namespace != expected_action.subject_namespace
                or challenge.subject_key != expected_action.subject_key
                or challenge.purpose != expected_action.purpose
                or challenge.expected_active_revision_id != expected_action.expected_active_revision_id
                or challenge.restore_target_revision_id != expected_action.restore_revision_id
                or challenge.memory_item_id != expected_memory_item_id
                or challenge.restore_target_digest != expected_restore_target_digest
                or challenge.privacy_notice_version != expected_privacy_notice_version
            ):
                raise OwnerProofError("ACTION_BINDING_MISMATCH")
            credential_row = conn.execute("SELECT credential_json FROM owner_proof_test_credential_v1 WHERE record_id=?", (assertion.credential_record_id,)).fetchone()
            if credential_row is None:
                raise OwnerProofError("UNKNOWN_CREDENTIAL")
            credential_bytes = bytes(credential_row[0])
            credential_data = _json_object(credential_bytes, allowed=_CREDENTIAL_FIELDS)
            credential = OwnerCredentialV1.from_dict(credential_data)
            if credential_bytes != rfc8785.dumps(credential.to_dict()):
                raise OwnerProofError("NONCANONICAL_CREDENTIAL")
            if credential.status != "ACTIVE" or credential.owner_principal != self.owner_principal or credential.rp_id != self.rp_id:
                raise OwnerProofError("CREDENTIAL_NOT_AUTHORIZED")
            if assertion.credential_record_id != credential.record_id or assertion.credential_id != credential.credential_id:
                raise OwnerProofError("CREDENTIAL_MISMATCH")
            client_raw = _b64u_decode(assertion.client_data_json, "client_data", 1, 2048)
            client_fields = _json_object(client_raw, allowed=frozenset({"type", "challenge", "origin", "crossOrigin"}))
            if set(client_fields) not in ({"type", "challenge", "origin"}, {"type", "challenge", "origin", "crossOrigin"}) or client_fields.get("crossOrigin", False) is not False:
                raise OwnerProofError("INVALID_CLIENT_DATA")
            auth_raw = _b64u_decode(assertion.authenticator_data, "authenticator_data", 37, 1024)
            signature = _b64u_decode(assertion.signature, "signature", 1, 512)
            cose_raw = _b64u_decode(credential.public_key_cose, "public_key", 16, 2048)
            try:
                cose_map, rest = cbor.decode_from(cose_raw)
                if rest or not isinstance(cose_map, dict) or cose_map.get(3) != -7:
                    raise ValueError("unsupported COSE key")
                cose_key = CoseKey.parse(cose_map)
                public_credential = AttestedCredentialData.create(b"\x00" * 16, _b64u_decode(credential.credential_id, "credential_id", 16, 1024), cose_key)
                response = AuthenticationResponse(
                    raw_id=public_credential.credential_id,
                    response=AuthenticatorAssertionResponse(
                        client_data=CollectedClientData(client_raw),
                        authenticator_data=AuthenticatorData(auth_raw),
                        signature=signature,
                    ),
                )
                server = Fido2Server(PublicKeyCredentialRpEntity(name="LILITH owner proof", id=self.rp_id), verify_origin=lambda value: value == self.origin)
                _, state = server.authenticate_begin([public_credential], user_verification=UserVerificationRequirement.REQUIRED, challenge=challenge.webauthn_challenge())
                server.authenticate_complete(state, [public_credential], response)
                observed = response.response.authenticator_data.counter
            except (ValueError, TypeError, KeyError, IndexError, OverflowError) as exc:
                raise OwnerProofError("INVALID_WEBAUTHN_ASSERTION") from exc
            # A proof can cross expiry during crypto verification or lock wait.
            # This is the decisive sample for the durable consumption transition.
            now = self._trusted_now()
            if now >= _instant(challenge.expires_at):
                conn.execute("UPDATE owner_proof_challenge_v1 SET state='EXPIRED' WHERE challenge_id=? AND state='PREPARED'", (challenge_id,))
                conn.commit()
                raise OwnerProofError("CHALLENGE_EXPIRED")
            if now < _instant(challenge.issued_at):
                raise OwnerProofError("CHALLENGE_NOT_YET_VALID")
            consumed_at = now.isoformat(timespec="seconds").replace("+00:00", "Z")
            changed = conn.execute("UPDATE owner_proof_challenge_v1 SET state='CONSUMED',consumed_credential_record_id=?,consumed_at=? WHERE challenge_id=? AND state='PREPARED'", (credential.record_id, consumed_at, challenge_id)).rowcount
            if changed != 1:
                raise OwnerProofError("REPLAY")
            counter_risk = observed > 0 and credential.last_observed_sign_count > 0 and observed <= credential.last_observed_sign_count
            if observed > credential.last_observed_sign_count:
                updated = replace(credential, last_observed_sign_count=observed)
                conn.execute("UPDATE owner_proof_test_credential_v1 SET credential_json=? WHERE record_id=?", (rfc8785.dumps(updated.to_dict()), credential.record_id))
            conn.commit()
            return OwnerProofVerificationResultV1(
                challenge_id, credential.record_id, self.owner_principal,
                challenge.action_digest, challenge.request_digest, observed, counter_risk,
            )
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _trusted_now(self) -> datetime:
        now = self.now_fn()
        if now.tzinfo is None or now.utcoffset() != timezone.utc.utcoffset(now):
            raise OwnerProofError("INVALID_NOW")
        return now


class OwnerProofVerifier(_OwnerProofVerificationEngine):
    """Existing B1a API; its TEST-only synthetic-RP rule is unchanged."""

    def __init__(self, store: DurableOwnerChallengeStore, *, owner_principal: str, rp_id: str, origin: str, test_mode: bool = False, now_fn: Callable[[], datetime] | None = None):
        self.test_mode = test_mode
        policy = _OwnerProofVerificationPolicyV1(
            _OwnerProofPolicyKind.B1A_EXISTING_TEST_MODE if test_mode else _OwnerProofPolicyKind.B1A_EXISTING,
            _text(owner_principal, "owner_principal", 256),
            _text(rp_id, "rp_id", 253),
            _text(origin, "origin", 512),
        )
        super().__init__(store, policy, now_fn=now_fn)


class DevSyntheticOwnerProofVerifier(_OwnerProofVerificationEngine):
    """Future broker seam: fixed synthetic identity, never a live policy."""

    def __init__(self, store: DurableOwnerChallengeStore, *, now_fn: Callable[[], datetime] | None = None):
        policy = _OwnerProofVerificationPolicyV1(
            _OwnerProofPolicyKind.DEV_SYNTHETIC,
            _DEV_SYNTHETIC_OWNER,
            SYNTHETIC_RP_ID,
            SYNTHETIC_ORIGIN,
        )
        super().__init__(store, policy, now_fn=now_fn)
