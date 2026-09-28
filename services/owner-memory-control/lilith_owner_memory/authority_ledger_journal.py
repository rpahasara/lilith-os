"""15B2b-B1b-3e PR-1S: the authority recovery ledger journal (pure).

Design: docs/architecture/slice-15b2b-b1b3e-pr1-live-install-preflight.md §14.
Record: docs/architecture/slice-15b2b-b1b3e-pr1s-runtime-wiring.md.

The journal semantics of the B1b-3c TEST recovery ledger model, moved here
unchanged so the durable ledger (`lilith_authority_dev.ledger`) and the TEST
model share one implementation: the same operations, the same head function
`sha256(LILITH_AUTHORITY_LEDGER_HEAD_V1\\0 ‖ prevHead ‖ JCS(op))`, the same
replay, and the same refusals. The TEST model re-exports these names; this
module never imports it.

Also here, pure and deterministic:

- `genesis_op` / `initial_position`: the one `GENESIS` op a K-ROOT registry
  implies, and its `(1, head)` position. No timestamp enters it, so the
  owner can recompute the head offline (preflight §12).
- `epoch_adoption_op`: the pre-witness `ADVANCE_EPOCH` record of C-4, with
  the checks of the TEST `adopt_authorized_epoch`.
- `stale_prepared_challenges` / `stale_reserved_uses`: the pre-recovery work
  `VOID_CHALLENGE` / `QUARANTINE_USE` destroy.

Nothing here reads a file, the environment, a database, or a credential,
and nothing signs. A journal is story-4 evidence, never authority:

    ledger provisioned != authority state accepted
    ledger evidence    != registry authority
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping

from lilith_memory.owner_proof import OwnerProofError, _id

from . import authority_contracts as A
from . import authority_verifier as AV
from . import recovery_contracts as R
from . import rotation_contracts as RC
from .contracts import _canonical

LEDGER_HEAD_DOMAIN_SEPARATOR = b"LILITH_AUTHORITY_LEDGER_HEAD_V1\x00"

# Journal operations.
GENESIS = "GENESIS"
PREPARE = "PREPARE"
CONSUME = "CONSUME"
EXPIRE = "EXPIRE"
CANCEL = "CANCEL"
FAIL = "FAIL"
ISSUE = "ISSUE"
RESERVE = "RESERVE"
CONFIRM = "CONFIRM"
ABANDON = "ABANDON"
REGISTRY_VIEW = "REGISTRY_VIEW"
ADVANCE_EPOCH = "ADVANCE_EPOCH"
VOID_CHALLENGE = "VOID_CHALLENGE"
QUARANTINE_USE = "QUARANTINE_USE"
OPERATIONS = frozenset({GENESIS, PREPARE, CONSUME, EXPIRE, CANCEL, FAIL, ISSUE, RESERVE, CONFIRM, ABANDON,
                        REGISTRY_VIEW, ADVANCE_EPOCH, VOID_CHALLENGE, QUARANTINE_USE})
# The destroy/narrow-only recovery operations C-4 may journal.
RECOVERY_OPERATIONS = frozenset({ADVANCE_EPOCH, VOID_CHALLENGE, QUARANTINE_USE})

# Owner challenge states.
PREPARED = "PREPARED"
CONSUMED = "CONSUMED"
EXPIRED = "EXPIRED"
CANCELLED = "CANCELLED"
FAILED = "FAILED"
VOIDED_BY_RECOVERY = "VOIDED_BY_RECOVERY"
CHALLENGE_STATES = frozenset({PREPARED, CONSUMED, EXPIRED, CANCELLED, FAILED, VOIDED_BY_RECOVERY})
CHALLENGE_TERMINAL = frozenset({CONSUMED, EXPIRED, CANCELLED, FAILED, VOIDED_BY_RECOVERY})

# Evidence-use states.
RESERVED = "RESERVED"
USE_CONSUMED = "CONSUMED"
ABANDONED = "ABANDONED"
QUARANTINED_BY_RECOVERY = "QUARANTINED_BY_RECOVERY"
USE_STATES = frozenset({RESERVED, USE_CONSUMED, ABANDONED, QUARANTINED_BY_RECOVERY})
USE_TERMINAL = frozenset({USE_CONSUMED, ABANDONED, QUARANTINED_BY_RECOVERY})

# Closed set of recognized reasons for an epoch advance.
RECOVERY_REASONS = frozenset({
    "LEDGER_RESTORE_DETECTED", "WITNESS_LEDGER_MISMATCH", "KEY_COMPROMISE", "OPERATOR_RECOVERY",
})

# Closed, ordered ledger refusal taxonomy.
LEDGER_REASONS = (
    "LEDGER_MALFORMED",
    "LEDGER_INTEGRITY_FAILED",
    "NOT_READY_FOR_ISSUANCE",
    "CHALLENGE_ALREADY_KNOWN",
    "CHALLENGE_EPOCH_NOT_CURRENT",
    "CHALLENGE_UNKNOWN",
    "CHALLENGE_NOT_PREPARED",
    "CHALLENGE_NOT_CONSUMED",
    "STALE_EPOCH_CHALLENGE",
    "EVIDENCE_ALREADY_ISSUED",
    "EVIDENCE_NOT_ISSUED_HERE",
    "EVIDENCE_DIGEST_MISMATCH",
    "STALE_EPOCH_EVIDENCE",
    "EVIDENCE_ALREADY_USED",
    "USE_NOT_RESERVED",
    "STALE_EPOCH_RESERVATION",
    "REGISTRY_VIEW_NOT_ADVANCING",
    "RECOVERY_REASON_INVALID",
    "RECOVERY_WITNESS_INVALID",
    "RECOVERY_EPOCH_NOT_ADVANCING",
    "RECOVERY_REGISTRY_NOT_ADVANCING",
    "RECOVERY_REGISTRY_UNVERIFIED",
    "RECOVERY_NO_SIGNING_KEY",
    "NOT_PRE_RECOVERY_WORK",
)


class LedgerRefusal(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        assert reason in LEDGER_REASONS, reason
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _refuse_unless(condition: bool, reason: str, detail: str | None = None) -> None:
    if not condition:
        raise LedgerRefusal(reason, detail)


def _epoch_dict(value: Any) -> dict[str, Any]:
    try:
        return A.RecoveryEpochV1.from_dict(value).to_dict()
    except (OwnerProofError, TypeError, AttributeError) as exc:
        raise LedgerRefusal("LEDGER_MALFORMED") from exc


def _valid_id(value: Any) -> str:
    try:
        return _id(value, "ledger_id")
    except OwnerProofError as exc:
        raise LedgerRefusal("LEDGER_MALFORMED") from exc


def next_head(head: str, op: Mapping[str, Any]) -> str:
    """The one ledger head function (B1b-3c): sep ‖ prevHead ‖ JCS(op)."""
    return hashlib.sha256(LEDGER_HEAD_DOMAIN_SEPARATOR + bytes.fromhex(head) + _canonical(op)).hexdigest()


# ------------------------------------------------------------ replay ---

@dataclass
class JournalReplay:
    environment: str = ""
    epoch: A.RecoveryEpochV1 | None = None
    policy_version: str = ""
    registry_view: int = 0
    signing_key_ids: tuple[str, ...] = ()
    challenges: dict[str, dict[str, Any]] = field(default_factory=dict)
    uses: dict[str, dict[str, Any]] = field(default_factory=dict)
    issued: dict[str, dict[str, Any]] = field(default_factory=dict)
    digests: set[str] = field(default_factory=set)
    sequence: int = 0
    head: str = R.LEDGER_HEAD_GENESIS

    @property
    def ledger_epoch(self) -> str:
        return R.ledger_epoch_id(self.epoch, self.environment)

    def rows(self) -> dict[str, Any]:
        return {"challenges": {k: dict(v) for k, v in self.challenges.items()},
                "uses": {k: dict(v) for k, v in self.uses.items()}}


def _challenge(r: JournalReplay, challenge_id: Any) -> dict[str, Any]:
    entry = r.challenges.get(challenge_id) if isinstance(challenge_id, str) else None
    _refuse_unless(entry is not None, "CHALLENGE_UNKNOWN")
    return entry


def _use(r: JournalReplay, evidence_id: Any) -> dict[str, Any]:
    entry = r.uses.get(evidence_id) if isinstance(evidence_id, str) else None
    _refuse_unless(entry is not None and entry["state"] == RESERVED, "USE_NOT_RESERVED")
    return entry


def step(r: JournalReplay, op: Mapping[str, Any]) -> None:
    kind = op.get("op") if isinstance(op, Mapping) else None
    _refuse_unless(isinstance(kind, str), "LEDGER_MALFORMED")
    _refuse_unless((kind == GENESIS) == (r.sequence == 0), "LEDGER_MALFORMED")
    if kind == GENESIS:
        r.environment = op["environment"]
        _refuse_unless(r.environment in {"test", "dev", "prod"}, "LEDGER_MALFORMED")
        r.epoch = A.RecoveryEpochV1.from_dict(_epoch_dict(op["recoveryEpoch"]))
        r.policy_version, r.registry_view = _valid_id(op["policyVersion"]), op["registryVersion"]
        r.signing_key_ids = tuple(_valid_id(k) for k in op["signingKeyIds"])
    elif kind == PREPARE:
        challenge_id = _valid_id(op["challengeId"])
        _refuse_unless(challenge_id not in r.challenges, "CHALLENGE_ALREADY_KNOWN")
        _refuse_unless(op["ledgerEpoch"] == r.ledger_epoch, "CHALLENGE_EPOCH_NOT_CURRENT")
        r.challenges[challenge_id] = {"ledgerEpoch": op["ledgerEpoch"], "state": PREPARED, "evidenceId": None}
    elif kind == CONSUME:
        entry = _challenge(r, op["challengeId"])
        _refuse_unless(entry["state"] == PREPARED, "CHALLENGE_NOT_PREPARED")
        _refuse_unless(entry["ledgerEpoch"] == r.ledger_epoch, "STALE_EPOCH_CHALLENGE")
        entry["state"] = CONSUMED
    elif kind in {EXPIRE, CANCEL, FAIL}:
        entry = _challenge(r, op["challengeId"])
        _refuse_unless(entry["state"] == PREPARED, "CHALLENGE_NOT_PREPARED")
        entry["state"] = {EXPIRE: EXPIRED, CANCEL: CANCELLED, FAIL: FAILED}[kind]
    elif kind == ISSUE:
        entry = _challenge(r, op["challengeId"])
        _refuse_unless(entry["state"] == CONSUMED, "CHALLENGE_NOT_CONSUMED")
        _refuse_unless(entry["evidenceId"] is None, "EVIDENCE_ALREADY_ISSUED")
        _refuse_unless(entry["ledgerEpoch"] == r.ledger_epoch, "STALE_EPOCH_CHALLENGE")
        evidence_id, digest = _valid_id(op["evidenceId"]), op["evidenceDigest"]
        _refuse_unless(isinstance(digest, str) and len(digest) == 64, "LEDGER_MALFORMED")
        _refuse_unless(evidence_id not in r.issued and digest not in r.digests, "EVIDENCE_ALREADY_ISSUED")
        entry["evidenceId"] = evidence_id
        r.issued[evidence_id] = {"challengeId": op["challengeId"], "evidenceDigest": digest,
                                 "recoveryEpoch": r.epoch.to_dict()}
        r.digests.add(digest)
    elif kind == RESERVE:
        evidence_id = _valid_id(op["evidenceId"])
        issued = r.issued.get(evidence_id)
        _refuse_unless(issued is not None, "EVIDENCE_NOT_ISSUED_HERE")
        _refuse_unless(op["evidenceDigest"] == issued["evidenceDigest"], "EVIDENCE_DIGEST_MISMATCH")
        claimed = _epoch_dict(op["recoveryEpoch"])
        _refuse_unless(claimed == issued["recoveryEpoch"] == r.epoch.to_dict(), "STALE_EPOCH_EVIDENCE")
        _refuse_unless(evidence_id not in r.uses, "EVIDENCE_ALREADY_USED")
        r.uses[evidence_id] = {"evidenceDigest": issued["evidenceDigest"], "recoveryEpoch": claimed,
                               "proposalRefId": _valid_id(op["proposalRefId"]), "state": RESERVED,
                               "admissionId": None, "revisionId": None}
    elif kind == CONFIRM:
        entry = _use(r, op["evidenceId"])
        _refuse_unless(entry["recoveryEpoch"] == r.epoch.to_dict(), "STALE_EPOCH_RESERVATION")
        entry.update(state=USE_CONSUMED, admissionId=_valid_id(op["admissionId"]),
                     revisionId=_valid_id(op["revisionId"]))
    elif kind == ABANDON:
        _use(r, op["evidenceId"])["state"] = ABANDONED
    elif kind == REGISTRY_VIEW:
        _refuse_unless(type(op["registryVersion"]) is int and op["registryVersion"] > r.registry_view,
                       "REGISTRY_VIEW_NOT_ADVANCING")
        r.registry_view, r.policy_version = op["registryVersion"], _valid_id(op["policyVersion"])
        r.signing_key_ids = tuple(_valid_id(k) for k in op["signingKeyIds"])
    elif kind == ADVANCE_EPOCH:
        _refuse_unless(op["reason"] in RECOVERY_REASONS, "RECOVERY_REASON_INVALID")
        _refuse_unless(_epoch_dict(op["previousEpoch"]) == r.epoch.to_dict(), "LEDGER_MALFORMED")
        new_epoch = A.RecoveryEpochV1.from_dict(_epoch_dict(op["newEpoch"]))
        _refuse_unless(new_epoch.counter > r.epoch.counter, "RECOVERY_EPOCH_NOT_ADVANCING")
        _refuse_unless(type(op["registryVersion"]) is int and op["registryVersion"] > r.registry_view,
                       "RECOVERY_REGISTRY_NOT_ADVANCING")
        r.epoch, r.registry_view = new_epoch, op["registryVersion"]
        r.policy_version = _valid_id(op["policyVersion"])
        r.signing_key_ids = tuple(_valid_id(k) for k in op["signingKeyIds"])
    elif kind == VOID_CHALLENGE:
        entry = _challenge(r, op["challengeId"])
        _refuse_unless(entry["state"] == PREPARED and entry["ledgerEpoch"] != r.ledger_epoch,
                       "NOT_PRE_RECOVERY_WORK")
        entry["state"] = VOIDED_BY_RECOVERY
    elif kind == QUARANTINE_USE:
        entry = _use(r, op["evidenceId"])
        _refuse_unless(entry["recoveryEpoch"] != r.epoch.to_dict(), "NOT_PRE_RECOVERY_WORK")
        entry["state"] = QUARANTINED_BY_RECOVERY
    else:
        raise LedgerRefusal("LEDGER_MALFORMED")
    r.sequence += 1
    r.head = next_head(r.head, op)


def replay(log: tuple[Mapping[str, Any], ...]) -> JournalReplay:
    """Rebuild authority-side state from its journal. Raises `LedgerRefusal`."""
    _refuse_unless(isinstance(log, tuple) and len(log) > 0, "LEDGER_MALFORMED")
    r = JournalReplay()
    for op in log:
        try:
            step(r, op)
        except (KeyError, TypeError, ValueError, AttributeError, OwnerProofError) as exc:
            raise LedgerRefusal("LEDGER_MALFORMED") from exc
    return r


def terminal_reopened(journal_rows: Mapping[str, Any], actual_rows: Mapping[str, Any]) -> bool:
    """True when a stored row shows an earlier (less terminal) state than the journal."""
    for table, terminal in (("challenges", CHALLENGE_TERMINAL), ("uses", USE_TERMINAL)):
        for key, entry in journal_rows[table].items():
            row = actual_rows.get(table, {}).get(key)
            if entry["state"] in terminal and (row is None or row.get("state") not in terminal):
                return True
    return False


def observation(r: JournalReplay, *, rows: Mapping[str, Any]) -> RC.AuthorityLedgerObservationV1:
    """Story 4: the ledger's position from its journal, with row divergence reported."""
    journal_rows = r.rows()
    return RC.AuthorityLedgerObservationV1(
        environment=r.environment, recovery_epoch=r.epoch, sequence=r.sequence, head=r.head,
        registry_view=r.registry_view, signing_key_ids=tuple(r.signing_key_ids),
        rows_consistent=journal_rows == rows, terminal_reopened=terminal_reopened(journal_rows, rows))


# ---------------------------------------------------------- genesis op ---

def _current_signing_keys(parsed: A.AuthorityRegistryV1) -> tuple[str, ...]:
    return tuple(sorted(key_id for key_id, key in parsed.keys.items()
                        if key.current and key.signing_domain == A.OWNER_ACTOR
                        and key.recovery_epoch == parsed.recovery_epoch))


def genesis_op(registry: Mapping[str, Any]) -> dict[str, Any]:
    """The one GENESIS op a verified K-ROOT registry implies (preflight §14).

    `{environment, recoveryEpoch, policyVersion, registryVersion,
    signingKeyIds}` from the registry itself; no timestamp, no operator text.
    The caller must have verified the registry under K-ROOT; this function
    only derives the op from its already-accepted content.
    """
    try:
        parsed = A.AuthorityRegistryV1.from_verified_dict(registry)
    except (OwnerProofError, TypeError, KeyError) as exc:
        raise LedgerRefusal("RECOVERY_REGISTRY_UNVERIFIED") from exc
    keys = _current_signing_keys(parsed)
    _refuse_unless(bool(keys), "RECOVERY_NO_SIGNING_KEY")
    return {"op": GENESIS, "environment": parsed.environment, "recoveryEpoch": parsed.recovery_epoch.to_dict(),
            "policyVersion": parsed.policy_version, "registryVersion": parsed.registry_version,
            "signingKeyIds": list(keys)}


def initial_position(registry: Mapping[str, Any]) -> tuple[int, str]:
    """`(1, H(0^32, GENESIS op))`: the ledger position a V2 genesis must bind."""
    op = genesis_op(registry)
    return 1, next_head(R.LEDGER_HEAD_GENESIS, op)


# -------------------------------------------------- C-4 epoch adoption ---

ADOPTION_REASONS = (
    "LEDGER_INTEGRITY_FAILED",
    "WITNESS_NOT_V2",
    "AUTHORIZATION_NOT_VERIFIED",
    "PRIOR_WITNESS_MISMATCH",
    "PRIOR_EPOCH_MISMATCH",
    "TARGET_REGISTRY_MISMATCH",
    "TARGET_REGISTRY_UNVERIFIED",
    "LEDGER_REFUSED",
)


class AdoptionRefusal(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        assert reason in ADOPTION_REASONS, reason
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def epoch_adoption_op(log: tuple[Mapping[str, Any], ...], *, authorization: Mapping[str, Any],
                      witness: RC.RecoveryWitnessV2, target_registry: Mapping[str, Any],
                      registry_root: A.TrustedRegistryRootV1) -> dict[str, Any]:
    """The pre-witness `ADVANCE_EPOCH` record (C-4), checked as the TEST
    `adopt_authorized_epoch` checks it, and replayed onto `log` before return.

    Destroy/narrow-only: it names the K-ROOT authorization, the successor
    epoch, the target registry version, and the prior witness digest. Its
    `signingKeyIds` is an observation of the authorized registry, never a
    grant.
    """
    try:
        current = replay(tuple(log))
    except LedgerRefusal as exc:
        raise AdoptionRefusal("LEDGER_INTEGRITY_FAILED", exc.reason) from exc
    if not isinstance(witness, RC.RecoveryWitnessV2):
        raise AdoptionRefusal("WITNESS_NOT_V2")
    checked = RC.verify_epoch_advance_authorization(authorization=authorization, registry_root=registry_root,
                                                    environment=witness.environment)
    if not checked.verified:
        raise AdoptionRefusal("AUTHORIZATION_NOT_VERIFIED", checked.reason)
    auth: RC.EpochAdvanceAuthorizationV1 = checked.authorization
    if auth.expected_prior_witness_digest != witness.digest \
            or auth.expected_prior_witness_version != witness.witness_version:
        raise AdoptionRefusal("PRIOR_WITNESS_MISMATCH")
    if auth.prior_recovery_epoch != witness.current_recovery_epoch:
        raise AdoptionRefusal("PRIOR_EPOCH_MISMATCH")
    try:
        head = RC.registry_head(target_registry)
        context = A.AuthorityVerificationContextV1(
            environment=witness.environment, purpose=A.NEW_ADMISSION, registry_root=registry_root,
            trusted_minimum_registry_version=witness.registry_version + 1,
            expected_recovery_epoch=auth.successor_recovery_epoch, policy_version=target_registry["policyVersion"])
        context.validate()
    except (OwnerProofError, TypeError, KeyError, ValueError) as exc:
        raise AdoptionRefusal("TARGET_REGISTRY_MISMATCH") from exc
    if head != auth.target:
        raise AdoptionRefusal("TARGET_REGISTRY_MISMATCH")
    verified = AV.verify_authority_registry(context=context, registry=target_registry)
    if not verified.verified:
        raise AdoptionRefusal("TARGET_REGISTRY_UNVERIFIED", verified.reason)
    parsed = A.AuthorityRegistryV1.from_verified_dict(target_registry)
    op = {"op": ADVANCE_EPOCH, "previousEpoch": current.epoch.to_dict(),
          "newEpoch": auth.successor_recovery_epoch.to_dict(), "reason": auth.reason,
          "fromWitnessDigest": witness.digest, "authorizationId": auth.authorization_id,
          "registryVersion": head.version, "signingKeyIds": list(_current_signing_keys(parsed)),
          "policyVersion": parsed.policy_version}
    try:
        replay(tuple(log) + (op,))
    except LedgerRefusal as exc:
        raise AdoptionRefusal("LEDGER_REFUSED", exc.reason) from exc
    return op


def stale_prepared_challenges(r: JournalReplay) -> tuple[str, ...]:
    """PREPARED challenges bound to an older epoch, in deterministic order."""
    return tuple(cid for cid in sorted(r.challenges)
                 if r.challenges[cid]["state"] == PREPARED and r.challenges[cid]["ledgerEpoch"] != r.ledger_epoch)


def stale_reserved_uses(r: JournalReplay) -> tuple[str, ...]:
    """RESERVED evidence uses bound to an older epoch, in deterministic order."""
    return tuple(eid for eid in sorted(r.uses)
                 if r.uses[eid]["state"] == RESERVED and r.uses[eid]["recoveryEpoch"] != r.epoch.to_dict())
