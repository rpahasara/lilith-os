"""15B2b-B1b-3b TEST-ONLY accepted-memory read boundary.

storage ≠ acceptance. An L04 row is not accepted memory.

`AcceptedMemoryReadFacadeV2.read_accepted` returns a row as
`ACCEPTED_MEMORY` only when both of these hold:

1. the existing L04 read facade returns it. That facade enforces the actor,
   the tuple registry, the Privacy hold and restore suppression, and the
   Consent revision; the V2 read never bypasses it;
2. the complete V2 chain for the revision that created that row re-verifies
   (`verify_accepted_memory_v2`, normally under HISTORICAL_VERIFICATION):
   - owner proof → broker-signed OwnerEvidenceV2 → registry;
   - the linked L04 admission;
   - the authority-side evidence-use record for exactly that admission.

A row with no chain, a V1-only row, a forged row, an admission whose link or
authority confirmation is missing, or a duplicate admission of the same
evidence is not returned as accepted memory.

`read_historical_v1` is a separate, explicitly labelled path. Its rows are
`HISTORICAL_V1_UNVERIFIED_FOR_V2` and never carry acceptance. Raw storage and
debug reads (`CanonicalMemoryStoreV2.get_active`) remain separate again.

Neither result is a truth claim. Nothing here is wired into a production
route.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from lilith_memory import canonical_contracts as C
from lilith_memory import canonical_store as S

from . import authority_contracts as A
from . import contracts as K
from .admission_v2 import ACCEPTED_MEMORY, NOT_ACCEPTED, Reject, require, verify_accepted_memory_v2
from .l04_v2_adapter import (
    AdmissionLinkStoreV1,
    check_evidence_use_ledger,
    proposal_for_revision,
    read_l04_admission_view,
    resolve_v2_action,
)

ACCEPTED_V2_READ = "ACCEPTED_V2"
HISTORICAL_V1_READ = "HISTORICAL_V1_UNVERIFIED_FOR_V2"


@dataclass(frozen=True)
class AcceptedReadResultV1:
    status: str
    reason: str | None = None
    detail: str | None = None
    row: Mapping[str, Any] | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HistoricalReadResultV1:
    read_class: str
    row: Mapping[str, Any] | None
    accepted_memory: bool = False
    truth_claim: bool = False


class AcceptedMemoryReadFacadeV2:
    def __init__(self, l04_read_facade: Any, store: S.CanonicalMemoryStoreV2, *,
                 owner_context: K.AcceptanceContextV1, authority_context: A.AuthorityVerificationContextV1,
                 registry_provider: Callable[[], Mapping[str, Any] | None],
                 challenge_record_provider: Callable[[str], Mapping[str, Any] | None],
                 link_store: AdmissionLinkStoreV1, evidence_use_ledger: Any):
        if not callable(getattr(l04_read_facade, "read_exact", None)):
            raise TypeError("the existing L04 read facade is required")
        if not isinstance(store, S.CanonicalMemoryStoreV2) or not isinstance(link_store, AdmissionLinkStoreV1):
            raise TypeError("store or link store is invalid")
        check_evidence_use_ledger(evidence_use_ledger)
        self._facade = l04_read_facade
        self._store = store
        self._owner_context = owner_context
        self._authority_context = authority_context
        self._registry_provider = registry_provider
        self._challenge_record_provider = challenge_record_provider
        self._links = link_store
        self._ledger = evidence_use_ledger

    def read_accepted(self, *, actor: C.ActorRefV1 | None, memory_class: str, subject_namespace: str,
                      subject_key: str) -> AcceptedReadResultV1:
        row = self._facade.read_exact(actor=actor, memory_class=memory_class,
                                      subject_namespace=subject_namespace, subject_key=subject_key)
        try:
            require(row is not None, "NOT_READABLE")
            revision_id = str(row["revision_id"])
            proposal_ref_id = proposal_for_revision(self._store.path, revision_id)
            require(proposal_ref_id is not None, "ADMISSION_MISSING")
            link = self._links.get(proposal_ref_id)
            chain = self._links.chain(proposal_ref_id)
            require(link is not None and chain is not None, "ADMISSION_LINK_MISSING")
            action = resolve_v2_action(self._store, proposal_ref_id)
            evidence = chain["evidence"]
            challenge_id = evidence.get("challengeId") if isinstance(evidence, Mapping) else None
            result = verify_accepted_memory_v2(
                owner_context=self._owner_context, authority_context=self._authority_context, action=action,
                challenge_json=chain["challengeJson"],
                challenge_record=self._challenge_record_provider(challenge_id) if isinstance(challenge_id, str)
                else None,
                assertion=chain["assertion"], owner_credential=chain["ownerCredential"],
                registry=self._registry_provider(), evidence=evidence,
                admission=read_l04_admission_view(self._store.path, proposal_ref_id, action), link=link,
                evidence_use=self._ledger.lookup(link.get("authorityEvidenceId")))
            require(result.status == ACCEPTED_MEMORY, result.reason or "ADMISSION_NOT_ACCEPTED", result.detail)
            require(result.facts["revisionId"] == revision_id, "ACTIVE_REVISION_MISMATCH")
        except Reject as rejected:
            return AcceptedReadResultV1(NOT_ACCEPTED, rejected.reason, rejected.detail)
        return AcceptedReadResultV1(ACCEPTED_MEMORY, None, None, dict(row), {
            **result.facts, "readClass": ACCEPTED_V2_READ, "truthClaim": False,
        })

    def read_historical_v1(self, *, actor: C.ActorRefV1 | None, memory_class: str, subject_namespace: str,
                           subject_key: str) -> HistoricalReadResultV1:
        """Historical access through the existing L04 facade. Explicitly not
        V2 accepted memory, whatever path wrote the row."""
        row = self._facade.read_exact(actor=actor, memory_class=memory_class,
                                      subject_namespace=subject_namespace, subject_key=subject_key)
        return HistoricalReadResultV1(HISTORICAL_V1_READ, None if row is None else dict(row))
