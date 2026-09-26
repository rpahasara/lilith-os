"""15B2b-B1b-3b TEST-ONLY L04 V2 admission adapter.

Design: docs/architecture/slice-15b2b-b1b3-custody-isolation-design.md.

The adapter wraps the unchanged `lilith_memory.canonical_store.
CanonicalMemoryStoreV2`; it does not replace, patch, or migrate it. For a V2
NEW admission it requires, in order, and fails closed on the first miss:

1. a trusted NEW_ADMISSION authority context and owner context;
2. authority evidence that is OwnerEvidenceV2 (V1 `ActorEvidenceRefV1` HMAC
   evidence and the B2a TEST broker envelope are refused);
3. the candidate memory operation, resolved from the immutable L04 V2
   proposal reference (never from the caller);
4. an operation L04 owns (FORGET is Privacy-owned and refused);
5. no current Privacy hold or restore suppression for the identity;
6. a consumed owner proof bound to that exact action (B2a steps 1-6);
7. OwnerEvidenceV2 verified against the public registry (B1b-3a) and bound
   to that owner proof and the exact request, action, and payload digests,
   logical authority domain, owner, environment, signing domain, evidence
   type, recovery epoch, policy version, and registry lifecycle;
8. evidence and challenge not already used for an admission;
9. every existing L04 rule, by delegating to `CanonicalMemoryStoreV2.apply`
   (which still re-checks the Privacy hold inside its transaction).

Only then does it record an `AdmissionAuthorityLinkV1`. Policy, Consent,
Rollback, and ActorEvidenceRefV1 rows remain internal L04 state that the
unchanged store consumes; they are necessary for L04 but never sufficient for
V2, and the adapter never treats them as authority.

Honest limits (TEST-only):

- the link is held in an in-process `AdmissionLinkStoreV1`, recorded after
  L04 commits. A crash between the two leaves an admission with no link,
  which acceptance refuses (fail closed). Production needs the link written
  in the L04 transaction, i.e. a schema migration;
- the unchanged V1 `CanonicalMemoryStoreV2.apply` remains directly callable.
  The adapter cannot stop a V1-path row; it guarantees only that such a row
  is never L04_ADMITTED or ACCEPTED_MEMORY on the V2 path.

The adapter holds public registry material only and never signs.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from lilith_memory import canonical_contracts as C
from lilith_memory import canonical_store as S
from lilith_memory import learning_v2 as L

from . import authority_contracts as A
from . import contracts as K
from . import verifier as B2A
from .admission_v2 import (
    NOT_ACCEPTED,
    AdmissionAuthorityLinkV1,
    Reject,
    V2ResultV1,
    check_admission_link,
    non_v2_evidence_kind,
    require,
    verify_owner_authority,
)

L04_ADMITTED = "L04_ADMITTED"
ADMISSION_SEMANTICS = "L04_APPLIED_AND_LINKED_TO_VERIFIED_AUTHORITY_NOT_MEMORY_ACCEPTANCE"


@dataclass(frozen=True)
class V2AdmissionRequestV1:
    """What the application submits: a proposal reference, the broker-signed
    evidence it received, and the owner-proof artifacts. None of it is trusted."""

    proposal_ref_id: str
    evidence: Any
    challenge_json: bytes | None
    challenge_record: Mapping[str, Any] | None
    assertion: Mapping[str, Any] | None
    owner_credential: Mapping[str, Any] | None


class AdmissionLinkStoreV1:
    """TEST-ONLY in-memory admission ↔ evidence link store.

    One link per proposal, per evidence ID, and per challenge. It is
    application-held metadata: forging an entry grants nothing, because
    acceptance re-verifies the evidence it names.
    """

    def __init__(self) -> None:
        self._by_proposal: dict[str, dict[str, Any]] = {}
        self._evidence: set[str] = set()
        self._challenges: set[str] = set()

    def used(self, evidence_id: str, challenge_id: str) -> bool:
        return evidence_id in self._evidence or challenge_id in self._challenges

    def record(self, link: AdmissionAuthorityLinkV1) -> None:
        if (link["proposalRefId"] in self._by_proposal
                or self.used(link["authorityEvidenceId"], link["challengeId"])):
            raise ValueError("admission link already recorded")
        self._by_proposal[link["proposalRefId"]] = dict(link.fields)
        self._evidence.add(link["authorityEvidenceId"])
        self._challenges.add(link["challengeId"])

    def get(self, proposal_ref_id: str) -> dict[str, Any] | None:
        link = self._by_proposal.get(proposal_ref_id)
        return None if link is None else dict(link)


def _stored_value_digest(revision: sqlite3.Row | tuple) -> str | None:
    """The digest of the value L04 actually stores, recomputed from the stored
    JSON. None (fail closed) if the stored value does not re-normalize to
    itself and to its recorded digest, so a rewritten value cannot hide
    behind an unchanged `value_digest` column."""
    value_digest, value_schema, value_json = str(revision[0]), revision[3], revision[4]
    if value_schema != L.VALUE_SCHEMA:
        return None
    try:
        canonical, recomputed = L.normalize_project_codename(json.loads(str(value_json)))
    except Exception:
        return None
    return recomputed if canonical == str(value_json) and recomputed == value_digest else None


def read_l04_admission_view(path: Path, proposal_ref_id: str, action: C.FrozenMemoryActionV1) -> dict[str, Any] | None:
    """Read one admission from the unchanged L04 rows, read-only."""
    conn = sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True)
    try:
        admission = conn.execute(
            "SELECT admission_id,outcome FROM memory_admission WHERE proposal_ref_id=?",
            (proposal_ref_id,)).fetchone()
        if admission is None:
            return None
        audit = conn.execute(
            "SELECT operation_id,operation,memory_item_id,created_revision_id FROM memory_apply_audit "
            "WHERE proposal_ref_id=? AND admission_id=?", (proposal_ref_id, admission[0])).fetchone()
        revision = item = None
        if audit is not None:
            revision = conn.execute(
                "SELECT value_digest,epistemic_basis,admission_basis,value_schema,normalized_value_json "
                "FROM memory_revision "
                "WHERE revision_id=? AND memory_item_id=?", (audit[3], audit[2])).fetchone()
            item = conn.execute(
                "SELECT memory_class,subject_namespace,subject_key FROM memory_item WHERE memory_item_id=?",
                (audit[2],)).fetchone()
    finally:
        conn.close()
    identity = tuple(item) if item is not None else action.identity
    return {
        "schemaVersion": 1,
        "proposalRefId": proposal_ref_id,
        "admissionId": str(admission[0]),
        "admissionOutcome": str(admission[1]),
        "applyAuditId": None if audit is None else str(audit[0]),
        "memoryItemId": None if audit is None else str(audit[2]),
        "revisionId": None if audit is None else str(audit[3]),
        "operation": None if audit is None else str(audit[1]),
        "memoryClass": identity[0],
        "subjectNamespace": identity[1],
        "subjectKey": identity[2],
        "payloadDigest": None if revision is None else _stored_value_digest(revision),
        "actionDigest": action.action_digest,
        "epistemicBasis": None if revision is None else str(revision[1]),
        "admissionBasis": None if revision is None else str(revision[2]),
    }


class L04V2AdmissionAdapter:
    """V2 NEW admission gate around the unchanged L04 store (TEST-ONLY)."""

    def __init__(self, store: S.CanonicalMemoryStoreV2, *, owner_context: K.AcceptanceContextV1,
                 authority_context: A.AuthorityVerificationContextV1,
                 registry_provider: Callable[[], Mapping[str, Any] | None],
                 link_store: AdmissionLinkStoreV1):
        if not isinstance(store, S.CanonicalMemoryStoreV2):
            raise TypeError("store must be the unchanged CanonicalMemoryStoreV2")
        if not isinstance(owner_context, K.AcceptanceContextV1):
            raise TypeError("owner context is invalid")
        if not isinstance(authority_context, A.AuthorityVerificationContextV1) \
                or authority_context.purpose != A.NEW_ADMISSION:
            raise TypeError("the V2 adapter admits only under a NEW_ADMISSION context")
        if not callable(registry_provider) or not isinstance(link_store, AdmissionLinkStoreV1):
            raise TypeError("registry provider or link store is invalid")
        self.store = store
        self.owner_context = owner_context
        self.authority_context = authority_context
        self.registry_provider = registry_provider
        self.link_store = link_store

    def _resolve_action(self, proposal_ref_id: Any) -> C.FrozenMemoryActionV1:
        try:
            ref, proposal = self.store.learning_store.resolve_proposal_ref(proposal_ref_id)
            require(ref.proposal_family == L.V2_PROPOSAL_FAMILY, "PROPOSAL_UNRESOLVED", "V1_PROPOSAL_FAMILY")
            action = S.CanonicalMemoryStoreV2._action(proposal)
            action.validate()
        except Reject:
            raise
        except Exception as exc:
            raise Reject("PROPOSAL_UNRESOLVED") from exc
        return action

    def _privacy_clear(self, action: C.FrozenMemoryActionV1) -> None:
        try:
            held = self.store.privacy_hold_resolver.is_held(*action.identity)
        except Exception as exc:
            raise Reject("PRIVACY_STATE_UNAVAILABLE") from exc
        require(held is False, "PRIVACY_HOLD_ACTIVE")

    def admit(self, request: V2AdmissionRequestV1) -> V2ResultV1:
        """Return L04_ADMITTED only when V2 authority verifies and L04 applies."""
        try:
            require(isinstance(request, V2AdmissionRequestV1), "MALFORMED_CONTEXT")
            require(request.evidence is not None, "AUTHORITY_EVIDENCE_MISSING")
            legacy = non_v2_evidence_kind(request.evidence)
            require(legacy is None, "NON_V2_EVIDENCE_NOT_ACCEPTED", legacy)
            action = self._resolve_action(request.proposal_ref_id)
            require(action.operation != C.FORGET, "PRIVACY_OWNED_OPERATION")
            try:
                challenge_operation = B2A.parse_challenge_v2(request.challenge_json)["operation"]
            except Exception:
                challenge_operation = None  # malformed: the owner-proof check reports it
            require(challenge_operation != C.FORGET, "PRIVACY_OWNED_OPERATION")
            self._privacy_clear(action)

            authority = verify_owner_authority(
                owner_context=self.owner_context, authority_context=self.authority_context, action=action,
                challenge_json=request.challenge_json, challenge_record=request.challenge_record,
                assertion=request.assertion, owner_credential=request.owner_credential,
                registry=self.registry_provider(), evidence=request.evidence, expected_evidence_id=None)
            envelope = authority.evidence
            require(not self.link_store.used(envelope["evidenceId"], envelope["challengeId"]),
                    "EVIDENCE_ALREADY_CONSUMED")

            # Every existing L04 rule applies unchanged, including its own
            # in-transaction Privacy hold checks and V1 internal-state rows.
            applied = self.store.apply(request.proposal_ref_id)
            require(applied.outcome == S.ACCEPTED, "L04_NOT_ADMITTED",
                    applied.outcome if applied.failure_code is None
                    else f"{applied.outcome}:{applied.failure_code}")
            view = read_l04_admission_view(self.store.path, request.proposal_ref_id, action)
            require(view is not None, "ADMISSION_MISSING")
            link = {
                "schemaVersion": 1,
                "proposalRefId": request.proposal_ref_id,
                "admissionId": view["admissionId"],
                "applyAuditId": view["applyAuditId"],
                "memoryItemId": view["memoryItemId"],
                "revisionId": view["revisionId"],
                "authorityEvidenceId": envelope["evidenceId"],
                "authorityEvidenceDigest": authority.evidence_digest,
                "challengeId": envelope["challengeId"],
                "actionDigest": envelope["actionDigest"],
                "payloadDigest": envelope["payloadDigest"],
            }
            _admitted, linked = check_admission_link(authority, action, view, link)
            self.link_store.record(linked)
        except Reject as rejected:
            return V2ResultV1(NOT_ACCEPTED, rejected.reason, rejected.detail)
        return V2ResultV1(L04_ADMITTED, None, None, {
            "semantics": ADMISSION_SEMANTICS,
            "stage": L04_ADMITTED,
            "memoryAcceptance": False,
            "truthClaim": False,
            "admission": view,
            "link": dict(linked.fields),
            "authority": dict(authority.authority_facts),
        })
