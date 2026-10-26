"""First Memory: the minimum DEV_SYNTHETIC conversation -> consent -> L04 -> recall composition (no new authority).

One LILITH memory, never Hermes chat history: a value is remembered only through the canonical L04 V2 chain and
recalled only through the accepted-memory read facade, so a recall in any later session depends on canonical
storage alone (no session, transcript or Hermes state is read or written here).

    offer(session, text)        an explicit owner directive ("remember my project codename is X") becomes ONE
                                frozen action and ONE owner challenge. Nothing is written: an offer is not memory.
    consent(offer, assertion)   the owner's authenticated consent (a WebAuthn assertion over that challenge) goes to
                                the evidence issuer, i.e. the trusted signer. Only if it issues OwnerEvidenceV2 are
                                L04's internal rows (Actor, Policy, Consent, intent, candidate, proposal) created
                                and the unchanged `L04V2AdmissionAdapter` asked to admit. A refusal writes nothing.
    recall(session, text)       "what is my project codename" -> `AcceptedMemoryReadFacadeV2.read_accepted`.

Composition only. Every rule stays with its owner: the issuer verifies the owner proof and signs; the adapter
re-verifies the evidence, the Privacy hold and every L04 rule; the accepted read re-verifies the whole chain. This
module never signs, holds no key, chooses no signed digest and never reads a private key.

Privacy (Track B): every operation first requires `PrivacyBindingV1.require_ready()`: the ONE authoritative Privacy
DB (the activated DEV_SYNTHETIC store), refused while the stale Core API Privacy path exists (a second source of
truth), and the current-boot `PrivacyFreshnessGate` READY. The same binding supplies the restore-gated hold resolver
that the L04 stores and the read facade must be built with (`memory_v2.restore_gated_hold_resolver`).

The First Interaction identity is permanently suppressed (F9c2 FORGET) and is refused at construction; this module
only composes the codename tuple the installed signer supports (`LONG_TERM_PERSONAL_PROJECT_RECALL`).
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Protocol

from lilith_memory import canonical_contracts as C
from lilith_memory import learning_v2
from lilith_memory import memory_action_v2 as MA
from lilith_memory import memory_v2
from lilith_memory import privacy_freshness as F

from . import accepted_read_v2 as AR
from . import admission_v2 as V2
from . import contracts as K
from . import l04_v2_adapter as AD

ENVIRONMENT = "DEV_SYNTHETIC"
AUTHORITATIVE_PRIVACY_DB = Path("/home/lilith/.hermes/lilith-os-dev/f9-drill/privacy_governance.f9drill.db")
STALE_PRIVACY_DB = Path("/home/lilith/.hermes/lilith-os-dev/data/privacy_governance.dev.db")
CHALLENGE_TTL = timedelta(seconds=60)

OFFERED = "OFFERED"
NOT_A_MEMORY_REQUEST = "NOT_A_MEMORY_REQUEST"
ADMITTED = "ADMITTED"
NOT_ADMITTED = "NOT_ADMITTED"
RECALLED = "RECALLED"
NOTHING_RECALLED = "NOTHING_RECALLED"

# Closed directive grammar: an explicit owner instruction, never inferred from ordinary dialogue.
_REMEMBER = re.compile(r"\A\s*remember\s+(?:that\s+)?my\s+project\s+codename\s+is\s+(?P<value>\S(?:.*\S)?)\s*\Z",
                       re.IGNORECASE | re.DOTALL)
_RECALL = re.compile(r"\A\s*what\s+is\s+my\s+project\s+codename\s*\??\s*\Z", re.IGNORECASE)
_SESSION = re.compile(r"\A[A-Za-z0-9._:-]{1,128}\Z")
# Trusted challenge context: the deployment's owner, RP, authority domain, policy and ledger (never from a request).
CHALLENGE_CONTEXT_FIELDS = frozenset({
    "protocol", "schemaVersion", "ownerPrincipal", "privacyNoticeVersion", "rpId", "deploymentEnvironment",
    "authorityDomain", "logicalOwnerId", "policyVersion", "registryTupleVersion", "ledgerEpoch"})


class FirstMemoryRefused(RuntimeError):
    """Explicit refusal; `code` never carries memory values or dialogue text."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _need(condition: bool, code: str) -> None:
    if not condition:
        raise FirstMemoryRefused(code)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _instant(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------------------------------------ Privacy ---

class PrivacyBindingV1:
    """The one authoritative Privacy DB and the current-boot freshness gate, re-checked on every call.

    `authoritative` and `stale` default to the DEV_SYNTHETIC paths; tests pass temporary ones. The binding refuses a
    Privacy DB that is not the authoritative one, and refuses while anything exists at the stale path."""

    def __init__(self, privacy_db: Path, privacy_store: Any, cognitive_db: Path, *,
                 authoritative: Path = AUTHORITATIVE_PRIVACY_DB, stale: Path = STALE_PRIVACY_DB,
                 freshness: Optional[F.PrivacyFreshnessGate] = None):
        self.privacy_db, self._stale = Path(privacy_db), Path(stale)
        _need(self.privacy_db == Path(authoritative) and self.privacy_db != self._stale,
              "PRIVACY_DB_NOT_AUTHORITATIVE")
        self._check_stale()
        self.freshness = freshness if freshness is not None else F.PrivacyFreshnessGate(
            self.privacy_db, environment=ENVIRONMENT)
        _need(isinstance(self.freshness, F.PrivacyFreshnessGate), "FRESHNESS_GATE_REQUIRED")
        self.resolver = memory_v2.restore_gated_hold_resolver(privacy_store, Path(cognitive_db),
                                                              freshness=self.freshness)

    def _check_stale(self) -> None:
        _need(not (self._stale.exists() or self._stale.is_symlink()), "STALE_PRIVACY_PATH_PRESENT")

    def require_ready(self) -> None:
        self._check_stale()
        result = self.freshness.check()
        _need(result.ready, "PRIVACY_FRESHNESS_NOT_READY:" + result.status)


# ------------------------------------------------------------------------------------------------- issuer ---

@dataclass(frozen=True)
class IssuedEvidenceV1:
    evidence: Mapping[str, Any]
    challenge_record: Mapping[str, Any]


class OwnerEvidenceIssuerV1(Protocol):
    """The trusted signer seam. `prepare` registers the challenge with the signer's own ledger; `issue` lets the
    signer verify and consume the owner proof and sign OwnerEvidenceV2, or refuse (`FirstMemoryRefused`)."""

    def prepare(self, challenge_json: bytes) -> None: ...

    def issue(self, challenge_id: str, action: C.FrozenMemoryActionV1, assertion: Mapping[str, Any],
              credential: Mapping[str, Any]) -> IssuedEvidenceV1: ...


@dataclass(frozen=True)
class L04ComponentsV1:
    """The L04 internal-state owners (built with `PrivacyBindingV1.resolver`). Necessary for L04, never authority."""

    actor: Any            # canonical_authority.LocalOwnerAuthority
    policy: Any           # canonical_authority.MemoryPolicyStore
    consent: Any          # canonical_authority.ConsentStore
    learning: Any         # learning_v2.LearningV2Store


# ------------------------------------------------------------------------------------------------ results ---

@dataclass(frozen=True)
class OfferV1:
    status: str
    offer_id: Optional[str] = None
    session_id: Optional[str] = None
    codename: Optional[str] = None
    challenge_json: Optional[bytes] = None
    webauthn_challenge: Optional[bytes] = None      # what the owner's authenticator signs


@dataclass(frozen=True)
class ConsentResultV1:
    status: str
    reason: Optional[str] = None
    proposal_ref_id: Optional[str] = None


@dataclass(frozen=True)
class RecallResultV1:
    status: str
    codename: Optional[str] = None
    reason: Optional[str] = None


@dataclass(frozen=True)
class _Pending:
    session_id: str
    codename: str
    action: C.FrozenMemoryActionV1
    encoded: str
    challenge: K.OwnerMemoryChallengeV2
    challenge_json: bytes


# ------------------------------------------------------------------------------------------- composition ---

class FirstMemoryConversationV1:
    def __init__(self, *, privacy: PrivacyBindingV1, l04: L04ComponentsV1,
                 adapter: Callable[[], AD.L04V2AdmissionAdapter],
                 reader: Callable[[], AR.AcceptedMemoryReadFacadeV2], issuer: OwnerEvidenceIssuerV1,
                 tuple_policy: memory_v2.MemoryTuplePolicyV1, challenge_context: Mapping[str, Any],
                 now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        _need(isinstance(privacy, PrivacyBindingV1), "PRIVACY_BINDING_REQUIRED")
        _need(tuple(tuple_policy.identity) != tuple(MA.FIRST_INTERACTION_IDENTITY),
              "FIRST_INTERACTION_IDENTITY_SUPPRESSED")                       # F9c2: never reused
        _need(tuple_policy.value_schema == learning_v2.VALUE_SCHEMA
              and tuple_policy.capability == C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE
              and tuple_policy.read_allowed and tuple_policy.write_allowed, "TUPLE_NOT_A_CODENAME_TUPLE")
        _need(set(challenge_context) == CHALLENGE_CONTEXT_FIELDS, "CHALLENGE_CONTEXT_INVALID")
        self._privacy, self._l04, self._adapter, self._reader = privacy, l04, adapter, reader
        self._issuer, self._tuple, self._context, self._now = issuer, tuple_policy, dict(challenge_context), now_fn
        self._pending: dict[str, _Pending] = {}

    # ----------------------------------------------------------------------------------------------- offer ---

    def offer(self, session_id: str, text: str) -> OfferV1:
        self._privacy.require_ready()
        _need(isinstance(session_id, str) and _SESSION.match(session_id) is not None, "SESSION_INVALID")
        match = _REMEMBER.match(text) if isinstance(text, str) else None
        if match is None:
            return OfferV1(NOT_A_MEMORY_REQUEST)
        try:
            encoded, payload_digest = learning_v2.normalize_project_codename({"codename": match.group("value")})
        except learning_v2.LearningV2Error as exc:
            raise FirstMemoryRefused("VALUE_REFUSED") from exc
        identity = self._tuple.identity
        _need(not self._privacy.resolver.is_held(*identity), "IDENTITY_HELD_OR_SUPPRESSED")
        action = C.FrozenMemoryActionV1(
            schema_version=1, actor_ref_id=self._l04.actor.ACTOR.actor_ref_id, operation=C.CREATE,
            memory_class=identity[0], subject_namespace=identity[1], subject_key=identity[2],
            value_schema=learning_v2.VALUE_SCHEMA, payload_digest=payload_digest, expected_active_revision_id=None,
            restore_revision_id=None, purpose=C.LONG_TERM_PERSONAL_PROJECT_RECALL)
        action.validate()
        offer_id = "och.fm1." + secrets.token_hex(16)
        issued = self._now()
        request = {"sessionId": session_id, "textSha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                   "actionDigest": action.action_digest}
        challenge = K.OwnerMemoryChallengeV2.from_dict({
            **self._context, "challengeId": offer_id, "actionDigest": action.action_digest,
            "requestDigest": hashlib.sha256(json.dumps(request, sort_keys=True).encode("ascii")).hexdigest(),
            "payloadDigest": action.payload_digest, "operation": action.operation,
            "memoryClass": action.memory_class, "subjectNamespace": action.subject_namespace,
            "subjectKey": action.subject_key, "purpose": action.purpose, "memoryItemId": None,
            "expectedActiveRevisionId": None, "restoreTargetRevisionId": None, "restoreTargetDigest": None,
            "nonce": _b64(secrets.token_bytes(32)), "issuedAt": _instant(issued),
            "expiresAt": _instant(issued + CHALLENGE_TTL)})
        challenge_json = challenge.canonical_bytes()
        self._issuer.prepare(challenge_json)
        codename = json.loads(encoded)["codename"]
        self._pending[offer_id] = _Pending(session_id, codename, action, encoded, challenge, challenge_json)
        return OfferV1(OFFERED, offer_id, session_id, codename, challenge_json, challenge.webauthn_challenge())

    # --------------------------------------------------------------------------------------------- consent ---

    def consent(self, offer_id: str, session_id: str, assertion: Mapping[str, Any],
                credential: Mapping[str, Any]) -> ConsentResultV1:
        self._privacy.require_ready()
        pending = self._pending.pop(offer_id, None)                          # single use, refused or not
        _need(pending is not None, "NO_SUCH_OFFER")
        _need(pending.session_id == session_id, "OFFER_OF_ANOTHER_SESSION")
        try:
            issued = self._issuer.issue(offer_id, pending.action, assertion, credential)
        except FirstMemoryRefused as exc:
            return ConsentResultV1(NOT_ADMITTED, "SIGNER_REFUSED:" + exc.code)   # no L04 row was written
        proposal_ref_id = self._proposal(pending)
        result = self._adapter().admit(AD.V2AdmissionRequestV1(
            proposal_ref_id=proposal_ref_id, evidence=dict(issued.evidence), challenge_json=pending.challenge_json,
            challenge_record=issued.challenge_record, assertion=assertion, owner_credential=credential))
        if result.status != AD.L04_ADMITTED:
            return ConsentResultV1(NOT_ADMITTED, result.reason, proposal_ref_id)
        return ConsentResultV1(ADMITTED, None, proposal_ref_id)

    def _proposal(self, pending: _Pending) -> str:
        """L04's internal-state rows for exactly the consented action (the existing V1-era sequence)."""
        actor, policy, consent, learning = self._l04.actor, self._l04.policy, self._l04.consent, self._l04.learning
        action, nonce = pending.action, pending.challenge["challengeId"]
        evidence = actor.issue(action=action, request_digest=pending.challenge["requestDigest"], nonce=nonce)
        decision = policy.decide(action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                                 capability=self._tuple.capability)
        challenge = consent.create_challenge(action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                                             policy_decision_ref_id=decision.decision_ref_id)
        intent_ref_id = "intent." + nonce
        confirmed = consent.confirm(challenge.challenge_id, action=action, issuer_ref="owner-webauthn:" + nonce,
                                    intent_ref_id=intent_ref_id,
                                    privacy_notice_version=pending.challenge["privacyNoticeVersion"])
        intent = learning.create_intent(action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                                        normalized_value_json=pending.encoded, intent_ref_id=intent_ref_id)
        candidate = learning.create_candidate(
            action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id, intent_ref_id=intent.intent_ref_id,
            policy_decision_ref_id=decision.decision_ref_id, consent_ref_id=confirmed.consent_id)
        _need(learning.assess(candidate.candidate_id) == learning_v2.REAL_ELIGIBLE, "CANDIDATE_NOT_ELIGIBLE")
        _proposal, ref = learning.create_proposal(candidate_id=candidate.candidate_id, action=action,
                                                  rollback_authorization_ref_id=None)
        return ref.proposal_ref_id

    # ---------------------------------------------------------------------------------------------- recall ---

    def recall(self, session_id: str, text: str) -> RecallResultV1:
        self._privacy.require_ready()
        _need(isinstance(session_id, str) and _SESSION.match(session_id) is not None, "SESSION_INVALID")
        if not isinstance(text, str) or _RECALL.match(text) is None:
            return RecallResultV1(NOT_A_MEMORY_REQUEST)
        identity = self._tuple.identity
        result = self._reader().read_accepted(actor=self._l04.actor.ACTOR, memory_class=identity[0],
                                              subject_namespace=identity[1], subject_key=identity[2])
        if result.status != V2.ACCEPTED_MEMORY:
            return RecallResultV1(NOTHING_RECALLED, reason=result.reason)
        return RecallResultV1(RECALLED, json.loads(result.row["normalized_value_json"])["codename"])
