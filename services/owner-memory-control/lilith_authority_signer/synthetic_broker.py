"""15B2b-B1b-3b TEST-ONLY broker/authority-domain signer for OwnerEvidenceV2.

Design: docs/architecture/slice-15b2b-b1b3-custody-isolation-design.md.

Custody split proven here:

- the application may *propose* (`OwnerEvidenceRequestV1`) and may *receive*
  signed evidence, but holds no signing key and cannot choose any signed
  digest, domain, epoch, or version;
- this signer holds the only private key (an in-process TEST_ONLY object
  supplied by the caller), owns its own challenge ledger, and signs only
  after it has itself verified a consumed owner proof;
- verifiers (`lilith_owner_memory.authority_verifier`, the L04 V2 adapter)
  hold public registry material only and never sign.

Signing is bound to: the consumed owner proof (credential record + assertion
digest), `challengeId`/`challengeDigest`, the exact request, action, and
payload digests taken from the verified owner challenge, the logical
`authorityDomain`, `signingDomain=OWNER_ACTOR`, environment, evidence type,
registry version, recovery epoch, policy version, logical owner, and the
evidence identity and nonce (`evidenceNonce == challengeId`, B1b-1).

The signer never accepts raw memory text, caller-chosen digests, or a
caller-supplied ledger state. It reads no file, environment variable, user or
home directory, network, cloud, database, or live broker; it refuses any
environment other than `test`. It is not a production broker.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from lilith_memory import canonical_contracts as C
from lilith_memory import owner_proof as P
from lilith_memory.owner_proof import OwnerProofError, _id, _instant

from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import contracts as K
from lilith_owner_memory import verifier as B2A

PREPARED = "PREPARED"
CONSUMED = "CONSUMED"
EXPIRED = "EXPIRED"
ISSUED = "ISSUED"
REFUSED = "REFUSED"

EVIDENCE_ID_DOMAIN_SEPARATOR = b"LILITH_B1B3B_OWNER_EVIDENCE_ID_V1\x00"

# Closed, ordered refusal taxonomy for the TEST signer.
SIGNER_REASONS = (
    "REQUEST_MALFORMED",
    "CHALLENGE_MALFORMED",
    "CHALLENGE_CONTEXT_MISMATCH",
    "PRIVACY_OWNED_OPERATION",
    "CHALLENGE_ALREADY_PREPARED",
    "CHALLENGE_UNKNOWN",
    "CHALLENGE_NOT_PREPARED",
    "CHALLENGE_EXPIRED",
    "CHALLENGE_NOT_CONSUMED",
    "OWNER_PROOF_REJECTED",
    "EVIDENCE_ALREADY_ISSUED",
)


class SignerConfigurationError(ValueError):
    """The signer was constructed outside its TEST-only envelope."""


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _stamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise SignerConfigurationError("signer clock must be timezone-aware")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class BrokerSignerConfigV1:
    """Everything the signer binds that does not come from the owner proof."""

    environment: str
    key_id: str
    authority_domain: str
    logical_owner_id: str
    registry_version: int
    recovery_epoch: A.RecoveryEpochV1
    policy_version: str

    def validate(self) -> None:
        if self.environment != "test":
            raise SignerConfigurationError("the B1b-3b signer is TEST-only")
        try:
            _id(self.key_id, "key_id")
            _id(self.policy_version, "policy_version")
            if _id(self.authority_domain, "authority_domain") in A.SIGNING_DOMAINS:
                raise SignerConfigurationError("authorityDomain is a logical context, not a signing domain")
            K._pattern(self.logical_owner_id, K._LOGICAL_OWNER, "logical_owner_id")
            A._int(self.registry_version, "registry_version", 1)
            A.RecoveryEpochV1.from_dict(self.recovery_epoch.to_dict())
        except OwnerProofError as exc:
            raise SignerConfigurationError(exc.code) from exc
        except AttributeError as exc:
            raise SignerConfigurationError("recovery epoch is invalid") from exc


@dataclass(frozen=True)
class OwnerEvidenceRequestV1:
    """What the application may send: a proposal to attest one owner operation.

    It names the challenge and carries the owner's assertion and public
    credential. It carries no digest, domain, epoch, version, or ledger
    state: the signer derives every signed value itself.
    """

    challenge_id: str
    action: C.FrozenMemoryActionV1
    assertion: Mapping[str, Any]
    owner_credential: Mapping[str, Any]


@dataclass(frozen=True)
class SignerResultV1:
    status: str
    reason: str | None = None
    detail: str | None = None
    evidence: Mapping[str, Any] | None = None


class _Refuse(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        assert reason in SIGNER_REASONS, reason
        self.reason = reason
        self.detail = detail


@dataclass
class _LedgerEntry:
    challenge_json: bytes
    challenge: K.OwnerMemoryChallengeV2
    state: str = PREPARED
    consumed_credential_record_id: str | None = None
    consumed_at: str | None = None
    evidence_id: str | None = None


class SyntheticBrokerAuthorityV1:
    """TEST-ONLY authority-domain signer for Owner/Actor evidence.

    The private key is held in a name-mangled attribute with no accessor, is
    never serialized, and is used only by `issue_owner_evidence`. The object
    refuses pickling and copying.
    """

    def __init__(self, *, signing_key: Ed25519PrivateKey, config: BrokerSignerConfigV1,
                 owner_context: K.AcceptanceContextV1, now_fn: Callable[[], datetime]):
        if not isinstance(signing_key, Ed25519PrivateKey):
            raise SignerConfigurationError("signing key must be an in-process Ed25519 key object")
        if not isinstance(config, BrokerSignerConfigV1):
            raise SignerConfigurationError("config is invalid")
        config.validate()
        if not isinstance(owner_context, K.AcceptanceContextV1):
            raise SignerConfigurationError("owner context is invalid")
        try:
            owner_context.validate()
        except OwnerProofError as exc:
            raise SignerConfigurationError(exc.code) from exc
        if not (owner_context.deployment_environment == config.environment == "test"
                and owner_context.rp_id.endswith(".invalid")):
            raise SignerConfigurationError("the B1b-3b signer is TEST-only")
        if (owner_context.authority_domain, owner_context.logical_owner_id, owner_context.policy_version) \
                != (config.authority_domain, config.logical_owner_id, config.policy_version):
            raise SignerConfigurationError("owner context and signer config disagree")
        self.__signing_key = signing_key
        self.__ledger: dict[str, _LedgerEntry] = {}
        self._config = config
        self._owner_context = owner_context
        self._now_fn = now_fn

    # ----------------------------------------------------------- hygiene ---

    def __repr__(self) -> str:
        return f"SyntheticBrokerAuthorityV1(keyId={self._config.key_id!r}, environment='test')"

    def __reduce__(self):
        raise TypeError("the TEST signer is not serializable")

    def __copy__(self):
        raise TypeError("the TEST signer is not copyable")

    def __deepcopy__(self, memo):
        raise TypeError("the TEST signer is not copyable")

    @property
    def key_id(self) -> str:
        return self._config.key_id

    def public_key_b64(self) -> str:
        """Public verification material, for publication in a registry."""
        return _b64(self.__signing_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))

    # ------------------------------------------------------------ ledger ---

    def prepare_challenge(self, challenge_json: bytes) -> SignerResultV1:
        """Record an owner challenge as PREPARED. A challenge alone is not
        evidence: nothing is signed here."""
        try:
            try:
                challenge = B2A.parse_challenge_v2(challenge_json)
            except (OwnerProofError, TypeError, ValueError) as exc:
                raise _Refuse("CHALLENGE_MALFORMED") from exc
            self._check_challenge_context(challenge)
            if challenge["challengeId"] in self.__ledger:
                raise _Refuse("CHALLENGE_ALREADY_PREPARED")
            self.__ledger[challenge["challengeId"]] = _LedgerEntry(bytes(challenge_json), challenge)
        except _Refuse as refused:
            return SignerResultV1(REFUSED, refused.reason, refused.detail)
        return SignerResultV1(PREPARED)

    def consume_owner_proof(self, challenge_id: str, *, action: C.FrozenMemoryActionV1,
                            assertion: Mapping[str, Any],
                            owner_credential: Mapping[str, Any]) -> SignerResultV1:
        """Verify the owner's WebAuthn assertion over a PREPARED challenge and
        consume it exactly once (B1a semantics). Nothing is signed here."""
        try:
            entry = self._entry(challenge_id)
            if entry.state != PREPARED:
                raise _Refuse("CHALLENGE_NOT_PREPARED")
            now = self._now()
            if _instant(now) >= _instant(entry.challenge["expiresAt"]):
                entry.state = EXPIRED
                raise _Refuse("CHALLENGE_EXPIRED")
            credential_record_id = assertion.get("credentialRecordId") if isinstance(assertion, Mapping) else None
            candidate = self._record(entry, CONSUMED, credential_record_id, now)
            verified = B2A.verify_owner_proof(
                context=self._owner_context, action=action, challenge_json=entry.challenge_json,
                challenge_record=candidate, assertion=assertion, owner_credential=owner_credential)
            if not verified.verified:
                raise _Refuse("OWNER_PROOF_REJECTED", verified.reason)
            entry.state = CONSUMED
            entry.consumed_credential_record_id = verified.proof.credential.record_id
            entry.consumed_at = now
        except _Refuse as refused:
            return SignerResultV1(REFUSED, refused.reason, refused.detail)
        return SignerResultV1(CONSUMED)

    def ledger_record(self, challenge_id: str) -> Mapping[str, Any] | None:
        """Read-only app-facing view of one challenge row. Forging this view
        grants nothing: the signer never reads a caller-supplied record."""
        entry = self.__ledger.get(challenge_id)
        if entry is None:
            return None
        return self._record(entry, entry.state, entry.consumed_credential_record_id, entry.consumed_at)

    # ----------------------------------------------------------- signing ---

    def issue_owner_evidence(self, request: OwnerEvidenceRequestV1) -> SignerResultV1:
        """Sign OwnerEvidenceV2 for one consumed owner proof, at most once."""
        try:
            if not isinstance(request, OwnerEvidenceRequestV1) or not isinstance(request.challenge_id, str):
                raise _Refuse("REQUEST_MALFORMED")
            entry = self._entry(request.challenge_id)
            if entry.state != CONSUMED:
                raise _Refuse("CHALLENGE_NOT_CONSUMED")
            if entry.evidence_id is not None:
                raise _Refuse("EVIDENCE_ALREADY_ISSUED")
            # Re-verify against the signer's OWN ledger row, never a caller view.
            verified = B2A.verify_owner_proof(
                context=self._owner_context, action=request.action, challenge_json=entry.challenge_json,
                challenge_record=self._record(entry, entry.state, entry.consumed_credential_record_id,
                                              entry.consumed_at),
                assertion=request.assertion, owner_credential=request.owner_credential)
            if not verified.verified:
                raise _Refuse("OWNER_PROOF_REJECTED", verified.reason)
            proof = verified.proof
            challenge = proof.challenge
            digest = challenge.challenge_digest()
            issued_at = self._now()
            config = self._config
            unsigned = {
                "protocol": A.OWNER_EVIDENCE_PROTOCOL,
                "schemaVersion": A.OWNER_EVIDENCE_SCHEMA_VERSION,
                "evidenceId": "aev." + hashlib.sha256(
                    EVIDENCE_ID_DOMAIN_SEPARATOR + bytes.fromhex(digest)).hexdigest()[:32],
                "evidenceNonce": challenge["challengeId"],
                "challengeId": challenge["challengeId"],
                "challengeDigest": digest,
                "credentialRecordId": proof.credential.record_id,
                "assertionDigest": proof.assertion_digest,
                "actionDigest": challenge["actionDigest"],
                "requestDigest": challenge["requestDigest"],
                "payloadDigest": challenge["payloadDigest"],
                "signingDomain": A.OWNER_ACTOR,
                "authorityDomain": config.authority_domain,
                "evidenceType": A.OWNER_MEMORY_OPERATION,
                "environment": config.environment,
                "logicalOwnerId": config.logical_owner_id,
                "keyId": config.key_id,
                "registryVersion": config.registry_version,
                "recoveryEpoch": config.recovery_epoch.to_dict(),
                "policyVersion": config.policy_version,
                "issuedAt": issued_at,
            }
            signature = self.__signing_key.sign(A.owner_evidence_signing_bytes(unsigned))
            entry.evidence_id = unsigned["evidenceId"]
        except _Refuse as refused:
            return SignerResultV1(REFUSED, refused.reason, refused.detail)
        return SignerResultV1(ISSUED, evidence={**unsigned, "signature": _b64(signature)})

    # ----------------------------------------------------------- helpers ---

    def _now(self) -> str:
        return _stamp(self._now_fn())

    def _entry(self, challenge_id: Any) -> _LedgerEntry:
        entry = self.__ledger.get(challenge_id) if isinstance(challenge_id, str) else None
        if entry is None:
            raise _Refuse("CHALLENGE_UNKNOWN")
        return entry

    def _record(self, entry: _LedgerEntry, state: str, credential_record_id: Any,
                consumed_at: str | None) -> dict[str, Any]:
        consumed = state == CONSUMED
        return {
            "schemaVersion": 1,
            "challengeId": entry.challenge["challengeId"],
            "state": state,
            "consumedCredentialRecordId": credential_record_id if consumed else None,
            "consumedAt": consumed_at if consumed else None,
            "ledgerEpoch": self._owner_context.ledger_epoch,
        }

    def _check_challenge_context(self, challenge: K.OwnerMemoryChallengeV2) -> None:
        context, config = self._owner_context, self._config
        if challenge["operation"] == C.FORGET:
            # Erasure is Privacy-owned; the Owner/Actor signer never attests it.
            raise _Refuse("PRIVACY_OWNED_OPERATION")
        expected = (config.environment, config.authority_domain, config.logical_owner_id,
                    config.policy_version, context.ledger_epoch, context.rp_id, context.owner_principal,
                    P.PROTOCOL)
        actual = (challenge["deploymentEnvironment"], challenge["authorityDomain"], challenge["logicalOwnerId"],
                  challenge["policyVersion"], challenge["ledgerEpoch"], challenge["rpId"],
                  challenge["ownerPrincipal"], challenge["protocol"])
        if actual != expected:
            raise _Refuse("CHALLENGE_CONTEXT_MISMATCH")
