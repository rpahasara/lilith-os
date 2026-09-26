"""15B2b-B1b-3b TEST-ONLY authority-side evidence-use ledger.

Invariant: one authority evidence instance must not create more than one
independent durable effect.

The ledger belongs to the broker/authority domain, not to the cognitive
application or its database. Nothing the application writes to the L04 DB or
to its admission-link metadata can reset, rebind, or rewrite an entry.

Lifecycle of one evidence ID (identified by ID and by digest of its signed
bytes):

    (absent) -> RESERVED(proposalRefId)  before L04 apply
    RESERVED -> CONSUMED(admissionId, revisionId)  after L04 commit and link
    RESERVED -> ABANDONED  when L04 did not admit

Every state is terminal for reuse: a second `reserve` of the same evidence is
refused whatever its state, so an exact replay, a replay against another
proposal or admission, and a replay after forged cognitive-DB or link state
are all refused. RESERVED is fail-closed. After a crash between reservation
and confirmation, the evidence is never reusable; the owner re-authorizes.

TEST-ONLY and in memory. Production (B1b-3d and later) needs durable
authority-side storage, outside application custody, whose restore semantics
are defined by B1b-3c.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

RESERVED = "RESERVED"
CONSUMED = "CONSUMED"
ABANDONED = "ABANDONED"
RESERVE_OK = "RESERVED"
REFUSED = "REFUSED"

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class LedgerResultV1:
    status: str
    reason: str | None = None
    record: Mapping[str, Any] | None = None


def _valid(value: Any, pattern: re.Pattern[str]) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


class SyntheticEvidenceUseLedgerV1:
    """In-memory authority-side record of which admission consumed which
    evidence. Callers receive copies only; there is no reset or delete."""

    def __init__(self) -> None:
        self.__entries: dict[str, dict[str, Any]] = {}
        self.__digests: set[str] = set()

    def __reduce__(self):
        raise TypeError("the TEST evidence ledger is not serializable")

    def __copy__(self):
        raise TypeError("the TEST evidence ledger is not copyable")

    def __deepcopy__(self, memo):
        raise TypeError("the TEST evidence ledger is not copyable")

    def reserve(self, *, evidence_id: str, evidence_digest: str, challenge_id: str,
                proposal_ref_id: str, action_digest: str) -> LedgerResultV1:
        if not (_valid(evidence_id, _ID) and _valid(challenge_id, _ID) and _valid(proposal_ref_id, _ID)
                and _valid(evidence_digest, _HEX64) and _valid(action_digest, _HEX64)):
            return LedgerResultV1(REFUSED, "RESERVATION_MALFORMED")
        existing = self.__entries.get(evidence_id)
        if existing is not None:
            return LedgerResultV1(REFUSED, "EVIDENCE_ALREADY_" + existing["state"], dict(existing))
        if evidence_digest in self.__digests:
            return LedgerResultV1(REFUSED, "EVIDENCE_DIGEST_ALREADY_USED")
        record = {
            "schemaVersion": 1, "evidenceId": evidence_id, "evidenceDigest": evidence_digest,
            "challengeId": challenge_id, "proposalRefId": proposal_ref_id, "actionDigest": action_digest,
            "state": RESERVED, "admissionId": None, "revisionId": None,
        }
        self.__entries[evidence_id] = record
        self.__digests.add(evidence_digest)
        return LedgerResultV1(RESERVE_OK, None, dict(record))

    def confirm(self, *, evidence_id: str, proposal_ref_id: str, admission_id: str,
                revision_id: str) -> LedgerResultV1:
        entry = self.__entries.get(evidence_id)
        if entry is None or entry["state"] != RESERVED or entry["proposalRefId"] != proposal_ref_id \
                or not (_valid(admission_id, _ID) and _valid(revision_id, _ID)):
            return LedgerResultV1(REFUSED, "CONFIRMATION_REFUSED", None if entry is None else dict(entry))
        entry.update(state=CONSUMED, admissionId=admission_id, revisionId=revision_id)
        return LedgerResultV1(CONSUMED, None, dict(entry))

    def abandon(self, *, evidence_id: str, proposal_ref_id: str) -> LedgerResultV1:
        entry = self.__entries.get(evidence_id)
        if entry is None or entry["state"] != RESERVED or entry["proposalRefId"] != proposal_ref_id:
            return LedgerResultV1(REFUSED, "ABANDON_REFUSED", None if entry is None else dict(entry))
        entry.update(state=ABANDONED)
        return LedgerResultV1(ABANDONED, None, dict(entry))

    def lookup(self, evidence_id: Any) -> Mapping[str, Any] | None:
        entry = self.__entries.get(evidence_id) if isinstance(evidence_id, str) else None
        return None if entry is None else dict(entry)
