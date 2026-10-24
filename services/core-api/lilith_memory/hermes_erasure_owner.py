"""F9-C Slice 2: the HERMES_DEV_CONVERSATION erasure owner (Core API side) under Privacy Governance.

Privacy Governance stays the only FORGET authority: this owner never creates or widens an authorization, never names a
Hermes session, and never reports COMPLETE because a request was merely queued. It follows the existing owner contract
(``erase_authorized(authorization_ref_id, execution_nonce)``):

1. independently resolve the authorization through Privacy (owner listed, exact nonce, HMAC integrity, hold ACTIVE)
   and require the First Interaction scope the DEV floor binds it to;
2. hand the executor a request that carries ONLY the owner, the authorization reference and the nonce (the executor
   validates the authorization again on its own and derives the erasure scope from it, never from the caller);
3. wait (bounded) for the executor's DURABLE receipt and verify it is bound to this exact authorization (reference,
   nonce, authorization fingerprint, hold, identity scope), is COMPLETE in every required phase and check, claims only
   logical erasure, and carries a correct digest;
4. re-resolve the authorization, then record COMPLETE. Any failure raises and records nothing, so the Privacy hold
   stays ACTIVE and the same authorization can be retried; a retry reuses an existing receipt or an existing COMPLETE
   result instead of submitting again.

This is the interim V1 (HMAC) path, enabled for DEV_SYNTHETIC only; a signed PrivacyAuthorizationV2 is required before
any live owner conversation. No privileged operation lives here: the executor is an interface (synthetic in tests).
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable, Dict, Mapping, Optional, Protocol

try:
    from . import memory_action_v2 as MA
    from . import privacy_governance as P
except ImportError:  # deploy-exact flat-directory tests
    import memory_action_v2 as MA
    import privacy_governance as P

OWNER = P.HERMES_DEV_CONVERSATION
DEV_SYNTHETIC = "DEV_SYNTHETIC"
REQUEST_VERSION = 1
RECEIPT_VERSION = 1
SCOPE = "WHOLE_STORE_SINGLE_PRINCIPAL"
CLAIM = "LOGICAL_ERASURE_VERIFIED"
PROVIDER_ERASURE = "ATTESTED_ZDR_NOT_VERIFIED"
COMPLETE, REJECTED, FAILED = "COMPLETE", "REJECTED", "FAILED"
REQUIRED_PHASES = ("VALIDATE", "STOP", "SQLITE", "FILES", "JOURNAL", "BACKUPS", "EPOCH")
REQUIRED_CHECKS = (
    "single_principal", "sessions_zero", "messages_zero", "fts_zero", "wal_truncated", "integrity_ok",
    "files_purged", "journal_vacuumed", "backups_conversation_free", "protected_files_unchanged",
)
REQUEST_FIELDS = frozenset({"v", "owner", "authorizationRefId", "executionNonce"})
RECEIPT_FIELDS = frozenset({
    "v", "owner", "authorizationRefId", "executionNonce", "authorizationFingerprint", "holdId", "identityScope",
    "scope", "status", "phases", "checks", "erasureEpoch", "claim", "providerErasure", "completedAt",
    "receiptDigest",
})
IDENTITY_FIELDS = frozenset({"memoryClass", "subjectNamespace", "subjectKey"})


class HermesErasureError(RuntimeError):
    """Raised for every non-COMPLETE outcome; the code is the stable, content-free reason."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class HermesErasureExecutor(Protocol):
    """The privileged executor as seen from the Core API. ``submit`` only queues (it must be idempotent per
    authorization reference); ``read_receipt`` returns the executor's durable receipt for that reference, if any."""

    def submit(self, request: Mapping[str, Any]) -> None: ...

    def read_receipt(self, authorization_ref_id: str) -> Optional[Mapping[str, Any]]: ...


def erasure_request(authorization_ref_id: str, execution_nonce: str) -> Dict[str, Any]:
    """The complete request: no session ids, paths, scope or any other caller-chosen field."""
    return {"v": REQUEST_VERSION, "owner": OWNER, "authorizationRefId": authorization_ref_id,
            "executionNonce": execution_nonce}


def receipt_digest(receipt: Mapping[str, Any]) -> str:
    body = {key: value for key, value in receipt.items() if key != "receiptDigest"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                          .encode("ascii")).hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise HermesErasureError(code)


def verify_receipt(receipt: Any, authorization: P.ErasureAuthorizationV1) -> Dict[str, Any]:
    """Accept only a COMPLETE receipt bound to exactly this authorization; raise with a reason code otherwise."""
    _require(isinstance(receipt, Mapping) and set(receipt) == RECEIPT_FIELDS, "RECEIPT_MALFORMED")
    _require(receipt["v"] == RECEIPT_VERSION and receipt["owner"] == OWNER, "RECEIPT_MALFORMED")
    _require(receipt["authorizationRefId"] == authorization.authorization_ref_id
             and receipt["executionNonce"] == authorization.execution_nonce, "RECEIPT_AUTHORIZATION_MISMATCH")
    _require(receipt["authorizationFingerprint"] == authorization.authorization_fingerprint
             and receipt["holdId"] == authorization.hold_id, "RECEIPT_AUTHORIZATION_MISMATCH")
    identity = receipt["identityScope"]
    _require(isinstance(identity, Mapping) and set(identity) == IDENTITY_FIELDS
             and (identity["memoryClass"], identity["subjectNamespace"], identity["subjectKey"])
             == authorization.identity, "RECEIPT_SCOPE_MISMATCH")
    _require(isinstance(receipt["receiptDigest"], str) and receipt["receiptDigest"] == receipt_digest(receipt),
             "RECEIPT_DIGEST_MISMATCH")
    _require(receipt["status"] != REJECTED, "EXECUTOR_REJECTED")
    _require(receipt["status"] != FAILED, "EXECUTOR_FAILED")
    _require(receipt["status"] == COMPLETE, "RECEIPT_INCOMPLETE")
    _require(receipt["scope"] == SCOPE, "RECEIPT_SCOPE_MISMATCH")
    phases, checks = receipt["phases"], receipt["checks"]
    _require(isinstance(phases, Mapping) and set(phases) == set(REQUIRED_PHASES)
             and all(phases[name] == COMPLETE for name in REQUIRED_PHASES), "RECEIPT_INCOMPLETE")
    _require(isinstance(checks, Mapping) and set(checks) == set(REQUIRED_CHECKS)
             and all(checks[name] is True for name in REQUIRED_CHECKS), "RECEIPT_INCOMPLETE")
    _require(isinstance(receipt["erasureEpoch"], int) and not isinstance(receipt["erasureEpoch"], bool)
             and receipt["erasureEpoch"] >= 1, "RECEIPT_INCOMPLETE")
    _require(receipt["claim"] == CLAIM and receipt["providerErasure"] == PROVIDER_ERASURE, "RECEIPT_OVERCLAIM")
    _require(isinstance(receipt["completedAt"], str) and bool(receipt["completedAt"]), "RECEIPT_MALFORMED")
    return {"receiptDigest": receipt["receiptDigest"], "erasureEpoch": receipt["erasureEpoch"]}


class HermesConversationErasureOwner:
    """Peer erasure owner for the Hermes DEV conversation store (whole store, single principal, DEV_SYNTHETIC)."""

    OWNER = OWNER

    def __init__(
        self,
        privacy_authority: Any,
        executor: Optional[HermesErasureExecutor],
        *,
        deployment_environment: str,
        timeout_seconds: float = 300.0,
        poll_seconds: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        if deployment_environment != DEV_SYNTHETIC:
            raise HermesErasureError("INTERIM_V1_PATH_DEV_SYNTHETIC_ONLY")
        if not 0 < float(timeout_seconds) <= 3600 or not 0 < float(poll_seconds) <= float(timeout_seconds):
            raise HermesErasureError("INVALID_WAIT_BOUNDS")
        self.privacy_authority = privacy_authority
        self.executor = executor
        self.timeout_seconds = float(timeout_seconds)
        self.poll_seconds = float(poll_seconds)
        self._sleep = sleep
        self._monotonic = monotonic

    def _resolve(self, authorization_ref_id: str, execution_nonce: str) -> P.ErasureAuthorizationV1:
        authorization = self.privacy_authority.resolve_erasure_authorization(
            authorization_ref_id, owner=self.OWNER, execution_nonce=execution_nonce)
        if authorization is None:
            raise PermissionError("PRIVACY_ERASURE_NOT_AUTHORIZED")
        _require(authorization.identity == MA.FIRST_INTERACTION_IDENTITY, "AUTHORIZATION_OUT_OF_SCOPE")
        return authorization

    def _read(self, authorization_ref_id: str) -> Optional[Mapping[str, Any]]:
        try:
            return self.executor.read_receipt(authorization_ref_id)
        except Exception as exc:
            raise HermesErasureError("EXECUTOR_UNAVAILABLE") from exc

    def erase_authorized(self, authorization_ref_id: str, execution_nonce: str) -> Dict[str, Any]:
        authorization = self._resolve(authorization_ref_id, execution_nonce)
        prior = self.privacy_authority.owner_result(authorization_ref_id, execution_nonce, self.OWNER)
        if prior == COMPLETE:                                       # retry after a recorded COMPLETE: no resubmit
            return {"owner": self.OWNER, "status": COMPLETE, "idempotent": True}
        _require(prior is None, "OWNER_RESULT_TERMINAL")
        _require(self.executor is not None, "EXECUTOR_UNAVAILABLE")
        receipt = self._read(authorization_ref_id)                   # a durable result from an interrupted attempt
        if receipt is None:
            try:
                self.executor.submit(erasure_request(authorization_ref_id, execution_nonce))
            except Exception as exc:
                raise HermesErasureError("EXECUTOR_UNAVAILABLE") from exc
            deadline = self._monotonic() + self.timeout_seconds
            while receipt is None:
                if self._monotonic() >= deadline:
                    raise HermesErasureError("EXECUTOR_TIMEOUT")    # queued is never COMPLETE
                self._sleep(self.poll_seconds)
                receipt = self._read(authorization_ref_id)
        bound = verify_receipt(receipt, authorization)
        self._resolve(authorization_ref_id, execution_nonce)                   # still authorized, hold still ACTIVE
        result = {"owner": self.OWNER, "status": COMPLETE, **bound}
        self.privacy_authority.record_owner_result(authorization_ref_id, execution_nonce, result)
        return result
