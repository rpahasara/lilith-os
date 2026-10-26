"""RR-39: the governed DEV_SYNTHETIC `ISSUE_OWNER_EVIDENCE` path (source only; unwired in the DEV runtime).

The one path on which the existing `OwnerActorEvidenceMinterV1` is constructed. Every input is either read by the
signer itself from fixed paths (its `SignerViewV1`: anchors, every installed K-ROOT registry, the witness chain; its
own durable ledger; its own loaded credential) or is exactly what the accepted recovery-handler pattern already
takes from a root caller: the COMPLETE root hold-store snapshot, re-judged as a whole (RR-34). The request adds only
the owner's own artifacts: the exact owner challenge, the frozen action, the WebAuthn assertion and the public
credential it names. Nothing signed is chosen by the caller.

In order, each a closed refusal (nothing is journalled or signed before the last check passes):

1. the complete hold snapshot parses, and under FULL_READINESS dominance the governing ceremony is RELEASED, bound
   to the verified head, with no HELD record anywhere (`successor_readiness.governing_hold_reason`);
2. the signer's own view is complete; the witness chain verifies from the owner-pinned genesis and every head
   registry verifies under the pinned K-ROOT trust root (`successor_readiness.verify_history`); no compromise
   marking is open (`compromise_epoch_reason`); the head's one current issuance key is this profile's key;
3. the durable ledger replays, its rows equal its journal, and its position equals the witness exactly
   (`rotation_contracts.authority_ledger_position_reason`: epoch, sequence, head, registry view);
4. the owner challenge is this deployment's (profile, owner policy, the ledger's own current epoch), not
   expired, and the credential is one of the REGISTERED owner credentials (exact record);
5. the owner proof verifies against that challenge, action and credential (`verifier.verify_owner_proof`);
6. the loaded K-ACT key equals the head registry's record and the minter's own guards accept the evidence
   (`OwnerActorEvidenceMinterV1`): domain, type, environment, key id, epoch, policy, validity;
7. `PREPARE`, `CONSUME`, `ISSUE` are journalled in ONE transaction at the evaluated position (single use: a known
   challenge, an issued evidence id or digest, or a moved ledger refuses), then the witness records the new
   position (`RECORD_LEDGER_ADVANCE`). Only then is the evidence released. A ledger that committed but was not
   witnessed is `LEDGER_AHEAD_OF_WITNESS` and the evidence is withheld.

Acceptance stays exclusively with the B1b-3a verifier (the signer never imports it): the minter's guards only
narrow what is signed, and every consumer re-verifies the evidence against the registry.

First Memory wiring: the DEV runtime constructs this handler (`server.build_core`) with fixed-path readers only. The
owner-proof settings and the registered owner PUBLIC credentials are re-read per request from the root-installed owner
registration (`lilith_authority_host.inputs.read_owner_registration`); absent or invalid, every request is refused
before any other state is read. The ISSUE journal op also binds the challenge's `actionDigest`, so the evidence-use
transport (`handle_use`: RESERVE / CONFIRM / ABANDON under the same readiness gate, and a read-only LOOKUP) reports
exactly the action this evidence authorizes. A use write, like issuance, is released only after the witness records
the new ledger position.

    loaded credential   != issuance permission
    issued evidence     != L04 admission != accepted memory
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

import rfc8785
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from lilith_memory.owner_proof import OwnerProofError
from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import authority_ledger_journal as J
from lilith_owner_memory import contracts as K
from lilith_owner_memory import pr1_acceptance as PA
from lilith_owner_memory import rotation_contracts as RC
from lilith_owner_memory import successor_custody as SC
from lilith_owner_memory import successor_readiness as SR
from lilith_owner_memory import verifier as B2A
from lilith_owner_memory import witness_readiness as WR

from .evidence_minter import MinterConfigurationError, MintRefused, OwnerActorEvidenceMinterV1
from .ledger import DurableAuthorityLedgerV1, LedgerError
from .profile import DevSyntheticSignerProfileV1, ProfileError
from . import protocol as W
from .protocol import IssueOwnerEvidenceRequestV1
from .recovery import SignerViewV1

ISSUED = "ISSUED"
REFUSED = "REFUSED"
LEDGER_AHEAD_OF_WITNESS = "LEDGER_AHEAD_OF_WITNESS"
EVIDENCE_ID_DOMAIN_SEPARATOR = b"LILITH_AUTHORITY_DEV_OWNER_EVIDENCE_ID_V1\x00"

ISSUANCE_REASONS = (
    "OWNER_REGISTRATION_MISSING",
    "OWNER_REGISTRATION_INVALID",
    "HOLD_SNAPSHOT_INVALID",
    "HOLD_INVALID",
    "SIGNER_INPUTS_INCOMPLETE",
    "HISTORY_NOT_VERIFIED",
    "COMPROMISE_EPOCH_OPEN",
    "KEY_TRANSITION_NOT_VERIFIED",
    "HOLD_NOT_RELEASED_FOR_ISSUANCE",
    "PROFILE_KEY_NOT_HEAD_CURRENT",
    "AUTHORITY_STATE_MISSING",
    "LEDGER_UNAVAILABLE",
    "LEDGER_NOT_AT_WITNESS",
    "CHALLENGE_MALFORMED",
    "CHALLENGE_REFERENCE_MISMATCH",
    "CHALLENGE_CONTEXT_MISMATCH",
    "CHALLENGE_NOT_YET_VALID",
    "CHALLENGE_EXPIRED",
    "OWNER_CREDENTIAL_NOT_REGISTERED",
    "OWNER_PROOF_REJECTED",
    "SIGNING_KEY_UNAVAILABLE",
    "LOADED_KEY_NOT_REGISTRY_KEY",
    "MINT_REFUSED",
    "LEDGER_WRITE_REFUSED",
    "USE_REQUEST_INVALID",
    "EVIDENCE_NOT_ISSUED_HERE",
    "EVIDENCE_BINDING_MISMATCH",
    "USE_NOT_RESERVED_FOR_PROPOSAL",
)
RESERVED = "RESERVED"
CONSUMED = "CONSUMED"
ABANDONED = "ABANDONED"
OK = "OK"
_USE_RESULT = {W.RESERVE_EVIDENCE_USE: RESERVED, W.CONFIRM_EVIDENCE_USE: CONSUMED, W.ABANDON_EVIDENCE_USE: ABANDONED}


@dataclass(frozen=True)
class OwnerProofSettingsV1:
    """The deployment's trusted owner-proof expectations (never from a request). The ledger epoch is not here: it
    is always the signer's own durable ledger epoch, read per request."""

    owner_principal: str
    rp_id: str
    origin: str
    registry_tuple_version: str
    privacy_notice_version: str
    broker_releases: frozenset[str]


def _refused(reason: str, detail: str | None = None) -> dict[str, Any]:
    assert reason in ISSUANCE_REASONS, reason
    return {"status": REFUSED, "reason": reason, "detail": detail, "authorityGranted": False}


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _instant(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


class IssuanceHandlerV1:
    """Constructed only with fixed-path readers and trusted settings; holds no key between requests."""

    def __init__(self, *, profile: DevSyntheticSignerProfileV1, view: Callable[[], SignerViewV1],
                 open_ledger: Callable[[], DurableAuthorityLedgerV1],
                 load_signing_key: Callable[[], Ed25519PrivateKey],
                 record_ledger_advance: Callable[[str, int, str], Mapping[str, Any]],
                 owner_proof: OwnerProofSettingsV1 | None = None,
                 registered_credentials: Callable[[], tuple[Mapping[str, Any], ...]] | None = None,
                 registration: Callable[[], tuple[Any, str | None]] | None = None,
                 now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 custody_profile: SC.CustodyProfileV1 | None = None):
        """Either fixed `owner_proof` + `registered_credentials` (TEST seams), or `registration`, the per-request
        reader of the root-installed owner registration (the DEV runtime). Never both, never neither."""
        if not isinstance(profile, DevSyntheticSignerProfileV1):
            raise ProfileError("a DEV_SYNTHETIC signer profile is required")
        profile.validate()
        fixed = owner_proof is not None or registered_credentials is not None
        if registration is not None:
            if fixed or not callable(registration):
                raise ProfileError("owner registration is either fixed or read, never both")
        elif not (isinstance(owner_proof, OwnerProofSettingsV1) and callable(registered_credentials)):
            raise ProfileError("owner-proof settings are required")
        self._profile = profile
        self._owner = owner_proof
        self._registration = registration
        self._custody = SC.require_dev_synthetic(custody_profile or SC.custody_profile(profile.environment))
        self._view, self._open_ledger, self._load_key = view, open_ledger, load_signing_key
        self._credentials, self._record_ledger_advance, self._now = registered_credentials, record_ledger_advance, now_fn

    def __reduce__(self):
        raise TypeError("the issuance handler is not serializable")

    # -------------------------------------------------------------------------------------------- entry ---

    def _owner_settings(self) -> tuple[OwnerProofSettingsV1, tuple[Mapping[str, Any], ...]] | dict[str, Any]:
        """The trusted owner-proof settings and registered credentials, re-read per request (or the TEST seams)."""
        if self._registration is None:
            return self._owner, tuple(self._credentials())
        try:
            registration, reason = self._registration()
        except (OSError, ValueError) as exc:
            return _refused("OWNER_REGISTRATION_INVALID", type(exc).__name__)
        if registration is None:
            return _refused(reason if reason in ("OWNER_REGISTRATION_MISSING", "OWNER_REGISTRATION_INVALID")
                            else "OWNER_REGISTRATION_INVALID")
        settings = OwnerProofSettingsV1(registration.owner_principal, registration.rp_id, registration.origin,
                                        registration.registry_tuple_version, registration.privacy_notice_version,
                                        frozenset(registration.broker_releases))
        return settings, tuple(registration.credentials)

    def handle(self, request: IssueOwnerEvidenceRequestV1) -> dict[str, Any]:
        if not isinstance(request, IssueOwnerEvidenceRequestV1) or not request.governed:
            return _refused("HOLD_SNAPSHOT_INVALID", "LEGACY_REQUEST_FORM")
        owner = self._owner_settings()
        if isinstance(owner, dict):
            return owner
        gated = self._gate(request.hold_store)
        if isinstance(gated, dict):
            return gated
        view, history, record = gated
        try:
            ledger = self._open_ledger()
        except LedgerError as exc:
            return _refused("AUTHORITY_STATE_MISSING" if exc.reason == "AUTHORITY_STATE_MISSING"
                            else "LEDGER_UNAVAILABLE", exc.reason)
        try:
            return self._issue(request, view, history, record, ledger, *owner)
        finally:
            ledger.close()

    def _gate(self, hold_store: Any):
        """Steps 1-2 (and the head-current key): the complete hold snapshot and the signer's own verified view.
        Returns (view, history, record) or a refusal. Shared by issuance and every evidence-use write."""
        holds, reason, detail = PA.parse_hold_snapshot(hold_store, environment=self._profile.environment)
        if holds is None:
            return _refused("HOLD_SNAPSHOT_INVALID", reason)
        parsed_holds, reason, detail = SC.parse_hold_store(holds, profile=self._custody)
        if parsed_holds is None:
            return _refused("HOLD_INVALID", reason)
        view = self._view()
        if not isinstance(view, SignerViewV1) or view.context is None or view.incomplete:
            return _refused("SIGNER_INPUTS_INCOMPLETE", ",".join(getattr(view, "incomplete", ())) or None)
        history, reason, detail = SR.verify_history(store=view.context, witness_store=view.witness_store,
                                                    head_registries=view.registries)
        if history is None:
            return _refused("HISTORY_NOT_VERIFIED", reason)
        reason, detail = SR.compromise_epoch_reason(history)
        if reason is not None:
            return _refused("COMPROMISE_EPOCH_OPEN", reason)
        transition, reason, detail = SR.derive_key_transition(history, profile=self._custody)
        if transition is None:
            return _refused("KEY_TRANSITION_NOT_VERIFIED", reason)
        _governing, reason, detail = SR.governing_hold_reason(parsed_holds, mode=SR.FULL_READINESS,
                                                              transition=transition, history=history,
                                                              inventory_phase=WR.STEADY)
        if reason is not None:
            return _refused("HOLD_NOT_RELEASED_FOR_ISSUANCE", reason)
        record = history.head_registry.keys.get(self._profile.key_id)
        current = RC.current_issuance_keys(history.head_registry).get(SR.SCOPE, ())
        if record is None or tuple(current) != (self._profile.key_id,):
            return _refused("PROFILE_KEY_NOT_HEAD_CURRENT")
        return view, history, record

    # -------------------------------------------------------------------------------------------- issue ---

    def _issue(self, request: IssueOwnerEvidenceRequestV1, view: SignerViewV1, history: SR.VerifiedHistoryV1,
               record: A.AuthorityKeyRecordV1, ledger: DurableAuthorityLedgerV1, owner: OwnerProofSettingsV1,
               registered: tuple[Mapping[str, Any], ...]) -> dict[str, Any]:
        try:
            observation = ledger.observe()
            replayed = ledger.replay()
        except (LedgerError, J.LedgerRefusal) as exc:
            return _refused("LEDGER_UNAVAILABLE", getattr(exc, "reason", None))
        position = RC.authority_ledger_position_reason(observation, history.head)
        if position is not None:
            return _refused("LEDGER_NOT_AT_WITNESS", position)
        ledger_epoch = replayed.ledger_epoch
        try:
            challenge_json = rfc8785.dumps(dict(request.challenge))
            challenge = B2A.parse_challenge_v2(challenge_json)
        except (OwnerProofError, TypeError, ValueError, rfc8785.CanonicalizationError) as exc:
            return _refused("CHALLENGE_MALFORMED", getattr(exc, "code", None))
        if challenge["challengeId"] != request.challenge_id:
            return _refused("CHALLENGE_REFERENCE_MISMATCH")
        profile = self._profile
        if (challenge["deploymentEnvironment"], challenge["authorityDomain"], challenge["logicalOwnerId"],
                challenge["policyVersion"], challenge["ledgerEpoch"]) != (
                profile.environment, profile.authority_domain, profile.logical_owner_id, profile.policy_version,
                ledger_epoch):
            return _refused("CHALLENGE_CONTEXT_MISMATCH")
        now = self._now()
        if now < _instant(challenge["issuedAt"]):
            return _refused("CHALLENGE_NOT_YET_VALID")
        if now >= _instant(challenge["expiresAt"]):
            return _refused("CHALLENGE_EXPIRED")
        credential = request.owner_credential.to_dict()
        if not any(isinstance(c, Mapping) and dict(c) == credential and c.get("status") == "ACTIVE"
                   for c in registered):
            return _refused("OWNER_CREDENTIAL_NOT_REGISTERED")
        context = K.AcceptanceContextV1(
            deployment_environment=profile.environment, authority_domain=profile.authority_domain,
            logical_owner_id=profile.logical_owner_id, owner_principal=owner.owner_principal, rp_id=owner.rp_id,
            origin=owner.origin, policy_version=profile.policy_version,
            registry_tuple_version=owner.registry_tuple_version, ledger_epoch=ledger_epoch,
            privacy_notice_version=owner.privacy_notice_version, broker_releases=owner.broker_releases)
        consumed_at = _stamp(now)
        challenge_record = {"schemaVersion": 1, "challengeId": challenge["challengeId"], "state": "CONSUMED",
                            "consumedCredentialRecordId": request.assertion.credential_record_id,
                            "consumedAt": consumed_at, "ledgerEpoch": ledger_epoch}
        verified = B2A.verify_owner_proof(context=context, action=request.action, challenge_json=challenge_json,
                                          challenge_record=challenge_record, assertion=request.raw_assertion,
                                          owner_credential=credential)
        if not verified.verified:
            return _refused("OWNER_PROOF_REJECTED", verified.reason)
        proof = verified.proof
        digest = challenge.challenge_digest()
        unsigned = {
            "protocol": A.OWNER_EVIDENCE_PROTOCOL, "schemaVersion": A.OWNER_EVIDENCE_SCHEMA_VERSION,
            "evidenceId": "aev." + hashlib.sha256(EVIDENCE_ID_DOMAIN_SEPARATOR + bytes.fromhex(digest)).hexdigest()[:32],
            "evidenceNonce": challenge["challengeId"], "challengeId": challenge["challengeId"],
            "challengeDigest": digest, "credentialRecordId": proof.credential.record_id,
            "assertionDigest": proof.assertion_digest, "actionDigest": challenge["actionDigest"],
            "requestDigest": challenge["requestDigest"], "payloadDigest": challenge["payloadDigest"],
            "signingDomain": A.OWNER_ACTOR, "authorityDomain": profile.authority_domain,
            "evidenceType": A.OWNER_MEMORY_OPERATION, "environment": profile.environment,
            "logicalOwnerId": profile.logical_owner_id, "keyId": record.key_id,
            "registryVersion": history.head_registry.registry_version, "recoveryEpoch": record.recovery_epoch.to_dict(),
            "policyVersion": profile.policy_version, "issuedAt": consumed_at,
        }
        try:
            key = self._load_key()
        except (OSError, ValueError, TypeError) as exc:
            return _refused("SIGNING_KEY_UNAVAILABLE", type(exc).__name__)
        try:
            minter = OwnerActorEvidenceMinterV1(signing_key=key, profile=profile, key_record=record)
        except MinterConfigurationError as exc:
            return _refused("LOADED_KEY_NOT_REGISTRY_KEY", str(exc))
        finally:
            del key
        try:
            evidence = minter.mint(unsigned)
        except MintRefused as exc:
            return _refused("MINT_REFUSED", str(exc))
        finally:
            del minter
        evidence_digest = hashlib.sha256(A.OwnerEvidenceV2.from_dict(evidence).signing_bytes()).hexdigest()
        ops = [{"op": J.PREPARE, "challengeId": challenge["challengeId"], "ledgerEpoch": ledger_epoch},
               {"op": J.CONSUME, "challengeId": challenge["challengeId"]},
               {"op": J.ISSUE, "challengeId": challenge["challengeId"], "evidenceId": evidence["evidenceId"],
                "evidenceDigest": evidence_digest,
                # First Memory: the authorized action, journalled (hash-chained) with the evidence it binds.
                "actionDigest": challenge["actionDigest"]}]
        try:
            after = ledger.append_issuance(ops, expected_sequence=observation.sequence,
                                           expected_head=observation.head)
        except LedgerError as exc:
            return _refused("LEDGER_WRITE_REFUSED", exc.detail or exc.reason)
        result = {"status": ISSUED, "ledgerSequence": after.sequence, "ledgerHead": after.head,
                  "authorityGranted": False}
        try:
            witnessed = self._record_ledger_advance(history.head.digest, after.sequence, after.head)
        except (OSError, ValueError) as exc:
            witnessed = {"status": REFUSED, "reason": type(exc).__name__}
        if not isinstance(witnessed, Mapping) or witnessed.get("status") != "OK":
            # Committed (the challenge is spent), not witnessed: fail closed, the evidence is never released.
            result.update(status=LEDGER_AHEAD_OF_WITNESS,
                          witness=dict(witnessed) if isinstance(witnessed, Mapping) else None)
            return result
        result.update(evidence=evidence, challengeRecord=challenge_record, witness="RECORDED")
        return result

    # ------------------------------------------------------------------------------------ evidence use ---

    def handle_use(self, operation: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        """The authority-side evidence-use transport for the L04 V2 adapter (B1b-3b lifecycle, durable here).

        RESERVE / CONFIRM / ABANDON pass the same readiness gate as issuance, need the ledger exactly at the witness,
        journal one op, and are released only after the witness records the new position. LOOKUP only reads."""
        try:
            request = W.parse_use_request(dict(payload), operation)
        except (W.ProtocolError, TypeError):
            return _refused("USE_REQUEST_INVALID")
        if operation == W.LOOKUP_EVIDENCE_USE:
            try:
                ledger = self._open_ledger()
            except LedgerError as exc:
                return _refused("AUTHORITY_STATE_MISSING" if exc.reason == "AUTHORITY_STATE_MISSING"
                                else "LEDGER_UNAVAILABLE", exc.reason)
            try:
                return {"status": OK, "use": use_record(ledger.replay(), ledger.journal(), request["evidenceId"]),
                        "authorityGranted": False}
            except (LedgerError, J.LedgerRefusal) as exc:
                return _refused("LEDGER_UNAVAILABLE", getattr(exc, "reason", None))
            finally:
                ledger.close()
        gated = self._gate(request["holdStore"])
        if isinstance(gated, dict):
            return gated
        _view, history, _record = gated
        try:
            ledger = self._open_ledger()
        except LedgerError as exc:
            return _refused("AUTHORITY_STATE_MISSING" if exc.reason == "AUTHORITY_STATE_MISSING"
                            else "LEDGER_UNAVAILABLE", exc.reason)
        try:
            return self._use(operation, request, history, ledger)
        finally:
            ledger.close()

    def _use(self, operation: str, request: Mapping[str, Any], history: SR.VerifiedHistoryV1,
             ledger: DurableAuthorityLedgerV1) -> dict[str, Any]:
        try:
            observation = ledger.observe()
            replayed = ledger.replay()
            journal = ledger.journal()
        except (LedgerError, J.LedgerRefusal) as exc:
            return _refused("LEDGER_UNAVAILABLE", getattr(exc, "reason", None))
        position = RC.authority_ledger_position_reason(observation, history.head)
        if position is not None:
            return _refused("LEDGER_NOT_AT_WITNESS", position)
        evidence_id = request["evidenceId"]
        if operation == W.RESERVE_EVIDENCE_USE:
            issued = replayed.issued.get(evidence_id)
            if issued is None:
                return _refused("EVIDENCE_NOT_ISSUED_HERE")
            bound = use_record(replayed, journal, evidence_id, reserving=True)
            if (issued["evidenceDigest"], issued["challengeId"], bound["actionDigest"]) != (
                    request["evidenceDigest"], request["challengeId"], request["actionDigest"]):
                return _refused("EVIDENCE_BINDING_MISMATCH")
            op = {"op": J.RESERVE, "evidenceId": evidence_id, "evidenceDigest": issued["evidenceDigest"],
                  "recoveryEpoch": replayed.epoch.to_dict(), "proposalRefId": request["proposalRefId"]}
        else:
            use = replayed.uses.get(evidence_id)
            if use is None or use["state"] != RESERVED or use["proposalRefId"] != request["proposalRefId"]:
                return _refused("USE_NOT_RESERVED_FOR_PROPOSAL")
            op = ({"op": J.CONFIRM, "evidenceId": evidence_id, "admissionId": request["admissionId"],
                   "revisionId": request["revisionId"]} if operation == W.CONFIRM_EVIDENCE_USE
                  else {"op": J.ABANDON, "evidenceId": evidence_id})
        try:
            after = ledger.append_use(op, expected_sequence=observation.sequence, expected_head=observation.head)
        except LedgerError as exc:
            return _refused("LEDGER_WRITE_REFUSED", exc.detail or exc.reason)
        result = {"status": _USE_RESULT[operation], "reason": None, "ledgerSequence": after.sequence,
                  "ledgerHead": after.head, "authorityGranted": False}
        try:
            witnessed = self._record_ledger_advance(history.head.digest, after.sequence, after.head)
        except (OSError, ValueError) as exc:
            witnessed = {"status": REFUSED, "reason": type(exc).__name__}
        if not isinstance(witnessed, Mapping) or witnessed.get("status") != "OK":
            # Committed, not witnessed: fail closed (the caller sees no RESERVED / CONSUMED / ABANDONED).
            result.update(status=LEDGER_AHEAD_OF_WITNESS, reason=LEDGER_AHEAD_OF_WITNESS,
                          witness=dict(witnessed) if isinstance(witnessed, Mapping) else None)
            return result
        result.update(record=use_record(ledger.replay(), ledger.journal(), evidence_id), witness="RECORDED")
        return result


def use_record(replayed: J.JournalReplay, journal: tuple[Mapping[str, Any], ...], evidence_id: str, *,
               reserving: bool = False) -> dict[str, Any] | None:
    """The evidence-use record in the L04 V2 shape, derived only from the signer's own journal: the use row, the
    issued evidence it names, and the `actionDigest` the ISSUE op bound. `reserving` describes an issued evidence
    before its RESERVE (only its binding is meaningful)."""
    issued = replayed.issued.get(evidence_id)
    use = replayed.uses.get(evidence_id)
    if issued is None or (use is None and not reserving):
        return None
    action_digest = next((op.get("actionDigest") for op in journal
                          if op.get("op") == J.ISSUE and op.get("evidenceId") == evidence_id), None)
    use = use or {}
    return {"schemaVersion": 1, "evidenceId": evidence_id, "evidenceDigest": issued["evidenceDigest"],
            "challengeId": issued["challengeId"], "proposalRefId": use.get("proposalRefId"),
            "actionDigest": action_digest, "state": use.get("state"), "admissionId": use.get("admissionId"),
            "revisionId": use.get("revisionId")}
