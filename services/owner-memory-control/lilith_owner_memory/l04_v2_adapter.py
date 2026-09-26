"""15B2b-B1b-3b TEST-ONLY L04 V2 admission adapter.

Design: docs/architecture/slice-15b2b-b1b3-custody-isolation-design.md.

The adapter wraps the unchanged `lilith_memory.canonical_store.
CanonicalMemoryStoreV2`; it does not patch or migrate it. For a V2 NEW
admission it requires, in order, and fails closed at the first miss:

1. a trusted NEW_ADMISSION authority context and owner context;
2. authority evidence that is OwnerEvidenceV2. V1 `ActorEvidenceRefV1` HMAC
   evidence and the B2a TEST broker envelope are refused;
3. the candidate memory operation, resolved from the immutable L04 V2
   proposal reference, never from the caller;
4. an operation L04 owns (FORGET is Privacy-owned and refused);
5. no current Privacy hold or restore suppression for the identity;
6. a consumed owner proof bound to that exact action (B2a steps 1-6);
7. OwnerEvidenceV2 verified against the public registry (B1b-3a) and bound
   to that owner proof and to:
   - the exact request, action, and payload digests;
   - the logical authority domain and owner;
   - the environment, signing domain, and evidence type;
   - the recovery epoch, policy version, and registry lifecycle;
8. a successful authority-side reservation of the evidence. One evidence
   instance gives at most one durable effect, recorded outside application
   custody;
9. every existing L04 rule, by delegating to `CanonicalMemoryStoreV2.apply`,
   which still re-checks the Privacy hold inside its transaction.

**V2 admission mode.** The store must be in V2 admission mode: its
`actor_authority` is a `V2AdmissionActorGate`. The gate refuses every
`validate_existing` call except during this adapter's own apply, for exactly
the action it just verified. A direct `apply` on that store, even with valid
V1 HMAC Actor evidence and every V1 row, is therefore rejected by L04 itself
(`ACTOR_UNRESOLVED`). HISTORICAL_V1 rows stay readable and V1-verifiable,
through `V2AdmissionActorGate.verify_historical_v1` or the inner authority.
NEW_ADMISSION requires V2 authority.

After L04 commits, the adapter records an `AdmissionAuthorityLinkV1`, with
the public chain artifacts needed to re-verify on read, and then confirms
the authority-side consumption. Policy, Consent, Rollback, and
ActorEvidenceRefV1 rows remain internal L04 state that the unchanged store
consumes. They are necessary for L04 but never sufficient for V2.

Honest limits (TEST-only):

- the link and the authority confirmation are written after L04 commits, so
  a crash in between leaves a stored row that is not accepted (fail closed,
  tested). Production needs the link in the L04 transaction (a schema
  migration) and a durable authority acknowledgement;
- the V2 guarantee holds for stores built in V2 admission mode. An unguarded
  `CanonicalMemoryStoreV2` over the same database can still write a V1 row.
  Such a row is never L04_ADMITTED, ACCEPTED_MEMORY, or returned by the
  accepted-memory read facade. A write barrier inside L04 itself is later
  core-api work.

The adapter holds public registry material only and never signs.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from lilith_memory import canonical_authority as CA
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
FAULT_POINTS = ("before_apply", "after_l04_commit", "after_link", "after_confirm")


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

    One link per proposal. It is **application-held metadata**, like the L04
    rows themselves. It also archives the public chain artifacts (evidence,
    owner challenge, assertion, credential) so the accepted-memory read
    facade can re-verify. Forging or duplicating an entry grants nothing:
    acceptance re-verifies every artifact and requires the authority-side
    evidence-use record. This store is **not** the single-use authority.
    """

    def __init__(self) -> None:
        self._by_proposal: dict[str, dict[str, Any]] = {}
        self._chains: dict[str, dict[str, Any]] = {}

    def record(self, link: AdmissionAuthorityLinkV1, chain: Mapping[str, Any]) -> None:
        if link["proposalRefId"] in self._by_proposal:
            raise ValueError("admission link already recorded")
        self._by_proposal[link["proposalRefId"]] = dict(link.fields)
        self._chains[link["proposalRefId"]] = dict(chain)

    def get(self, proposal_ref_id: str) -> dict[str, Any] | None:
        link = self._by_proposal.get(proposal_ref_id)
        return None if link is None else dict(link)

    def chain(self, proposal_ref_id: str) -> dict[str, Any] | None:
        chain = self._chains.get(proposal_ref_id)
        return None if chain is None else dict(chain)


class V2AdmissionActorGate:
    """Puts an L04 store into V2 admission mode.

    It wraps the 15B2a `LocalOwnerAuthority` that the unchanged store
    consults during `apply`. Outside the adapter's own apply of a verified
    V2 action, every NEW-admission `validate_existing` is refused, whatever
    V1 HMAC evidence or rows exist. Inside it, the V1 check still runs as
    internal-state validation: necessary, never sufficient.
    """

    def __init__(self, inner: CA.LocalOwnerAuthority):
        if not isinstance(inner, CA.LocalOwnerAuthority):
            raise TypeError("the gate wraps the 15B2a LocalOwnerAuthority")
        self._inner = inner
        self._pending_action_digest: str | None = None
        self.ACTOR = inner.ACTOR

    @contextlib.contextmanager
    def admitting(self, action_digest: str):
        if self._pending_action_digest is not None:
            raise RuntimeError("a V2 admission is already in progress")
        self._pending_action_digest = action_digest
        try:
            yield
        finally:
            self._pending_action_digest = None

    def validate_existing(self, reference_id: str, *, action: C.FrozenMemoryActionV1,
                          request_digest: str | None = None, require_consumed: bool = False):
        if self._pending_action_digest is None or action.action_digest != self._pending_action_digest:
            raise CA.ActorEvidenceError(C.ACTOR_UNRESOLVED)
        return self._inner.validate_existing(reference_id, action=action, request_digest=request_digest,
                                             require_consumed=require_consumed)

    def verify_historical_v1(self, reference_id: str, *, action: C.FrozenMemoryActionV1):
        """HISTORICAL_V1 verification with its unchanged semantics. Never an
        admission, and never V2 acceptance."""
        return self._inner.validate_existing(reference_id, action=action, require_consumed=True)


def v2_admission_store(store: S.CanonicalMemoryStoreV2) -> S.CanonicalMemoryStoreV2:
    """A V2-admission-mode view of an unchanged store: same database and
    rules, with its Actor authority wrapped by `V2AdmissionActorGate`."""
    if not isinstance(store, S.CanonicalMemoryStoreV2):
        raise TypeError("store must be the unchanged CanonicalMemoryStoreV2")
    if isinstance(store.actor_authority, V2AdmissionActorGate):
        return store
    guarded = S.CanonicalMemoryStoreV2.__new__(S.CanonicalMemoryStoreV2)
    guarded.__dict__.update(store.__dict__)
    guarded.actor_authority = V2AdmissionActorGate(store.actor_authority)
    return guarded


def resolve_v2_action(store: S.CanonicalMemoryStoreV2, proposal_ref_id: Any) -> C.FrozenMemoryActionV1:
    """The frozen action named by an immutable L04 V2 proposal reference."""
    try:
        ref, proposal = store.learning_store.resolve_proposal_ref(proposal_ref_id)
        require(ref.proposal_family == L.V2_PROPOSAL_FAMILY, "PROPOSAL_UNRESOLVED", "V1_PROPOSAL_FAMILY")
        action = S.CanonicalMemoryStoreV2._action(proposal)
        action.validate()
    except Reject:
        raise
    except Exception as exc:
        raise Reject("PROPOSAL_UNRESOLVED") from exc
    return action


LEDGER_METHODS = ("reserve", "confirm", "abandon", "lookup")


def check_evidence_use_ledger(ledger: Any) -> None:
    if isinstance(ledger, AdmissionLinkStoreV1) or not all(callable(getattr(ledger, m, None))
                                                           for m in LEDGER_METHODS):
        raise TypeError("an authority-side evidence-use ledger is required")


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


def _read_only(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True)


def read_l04_admission_view(path: Path, proposal_ref_id: str, action: C.FrozenMemoryActionV1) -> dict[str, Any] | None:
    """Read one admission from the unchanged L04 rows, read-only."""
    conn = _read_only(path)
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


def proposal_for_revision(path: Path, revision_id: str) -> str | None:
    """The proposal reference that created one revision, read-only."""
    conn = _read_only(path)
    try:
        row = conn.execute("SELECT created_from_proposal_ref_id FROM memory_revision WHERE revision_id=?",
                           (revision_id,)).fetchone()
    finally:
        conn.close()
    return None if row is None else str(row[0])


class L04V2AdmissionAdapter:
    """V2 NEW admission gate around the unchanged L04 store (TEST-ONLY)."""

    def __init__(self, store: S.CanonicalMemoryStoreV2, *, owner_context: K.AcceptanceContextV1,
                 authority_context: A.AuthorityVerificationContextV1,
                 registry_provider: Callable[[], Mapping[str, Any] | None],
                 link_store: AdmissionLinkStoreV1, evidence_use_ledger: Any,
                 fault_hook: Callable[[str], None] | None = None):
        if not isinstance(store, S.CanonicalMemoryStoreV2):
            raise TypeError("store must be the unchanged CanonicalMemoryStoreV2")
        if not isinstance(store.actor_authority, V2AdmissionActorGate):
            raise TypeError("the store must be in V2 admission mode (v2_admission_store)")
        if not isinstance(owner_context, K.AcceptanceContextV1):
            raise TypeError("owner context is invalid")
        if not isinstance(authority_context, A.AuthorityVerificationContextV1) \
                or authority_context.purpose != A.NEW_ADMISSION:
            raise TypeError("the V2 adapter admits only under a NEW_ADMISSION context")
        if not callable(registry_provider) or not isinstance(link_store, AdmissionLinkStoreV1):
            raise TypeError("registry provider or link store is invalid")
        check_evidence_use_ledger(evidence_use_ledger)
        self.store = store
        self.owner_context = owner_context
        self.authority_context = authority_context
        self.registry_provider = registry_provider
        self.link_store = link_store
        self.evidence_use_ledger = evidence_use_ledger
        self.fault_hook = fault_hook

    def _fault(self, point: str) -> None:
        if self.fault_hook is not None:
            self.fault_hook(point)

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
            action = resolve_v2_action(self.store, request.proposal_ref_id)
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
            # Authority-side single use, recorded before any durable effect.
            reserved = self.evidence_use_ledger.reserve(
                evidence_id=envelope["evidenceId"], evidence_digest=authority.evidence_digest,
                challenge_id=envelope["challengeId"], proposal_ref_id=request.proposal_ref_id,
                action_digest=envelope["actionDigest"])
            require(reserved.status == "RESERVED", "EVIDENCE_ALREADY_CONSUMED", reserved.reason)
            self._fault("before_apply")

            # Every existing L04 rule applies unchanged, including its own
            # in-transaction Privacy hold checks and V1 internal-state rows.
            with self.store.actor_authority.admitting(action.action_digest):
                applied = self.store.apply(request.proposal_ref_id)
            if applied.outcome != S.ACCEPTED:
                self.evidence_use_ledger.abandon(evidence_id=envelope["evidenceId"],
                                                 proposal_ref_id=request.proposal_ref_id)
            require(applied.outcome == S.ACCEPTED, "L04_NOT_ADMITTED",
                    applied.outcome if applied.failure_code is None
                    else f"{applied.outcome}:{applied.failure_code}")
            self._fault("after_l04_commit")
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
            self.link_store.record(linked, {
                "evidence": dict(request.evidence), "challengeJson": bytes(request.challenge_json),
                "assertion": dict(request.assertion), "ownerCredential": dict(request.owner_credential),
            })
            self._fault("after_link")
            confirmed = self.evidence_use_ledger.confirm(
                evidence_id=envelope["evidenceId"], proposal_ref_id=request.proposal_ref_id,
                admission_id=view["admissionId"], revision_id=view["revisionId"])
            require(confirmed.status == "CONSUMED", "EVIDENCE_USE_MISMATCH", confirmed.reason)
            self._fault("after_confirm")
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
