"""15B2b-B1b-3c TEST-ONLY authority-side recovery ledger model.

Design: docs/architecture/slice-15b2b-b1b3c-recovery-epoch-witness.md.

A pure, immutable model of the authority-side state that B1b-3d must later
make durable: the broker challenge ledger (B1b-1 / B1b-3b) and the
evidence-use ledger (B1b-3b), bound to one recovery epoch, as a hash-chained
journal. Every transition returns a new `AuthorityLedgerStateV1`; a
"snapshot" is simply an older value, so restore scenarios are deterministic.
Nothing here is durable and nothing pretends to be.

Rules proven by the tests:

- creating authority (prepare, consume, issue, reserve, confirm) requires a
  RESTORE_READY result bound to the exact ledger state it evaluated;
  removing authority (expire, cancel, fail, abandon, void, quarantine,
  epoch advance) never does;
- a challenge is prepared, consumed and signed only in the current epoch;
  evidence is reserved only in the epoch that issued it;
- terminal states never reopen, in any epoch;
- an epoch advance is authorized by an owner-signed registry at the new
  epoch, with a registry version above the witness floor. It voids
  PREPARED challenges and quarantines RESERVED evidence from older epochs,
  and keeps every terminal record as history.

Recovery can only destroy pending authority. It can never create any.

The witness signer here is freshness evidence only. Its key must never be an
authority key; the readiness gate and the witness verifier enforce that.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any, Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from lilith_memory.owner_proof import OwnerProofError

from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import authority_verifier as AV
from lilith_owner_memory import recovery_contracts as R

# The journal itself (operations, states, head function, replay, refusals)
# is the shared pure `authority_ledger_journal`, which the durable B1b-3e
# PR-1S ledger also uses. Re-exported here unchanged, so this TEST model and
# the durable ledger cannot diverge.
from lilith_owner_memory.authority_ledger_journal import (  # noqa: E402,F401
    ABANDON, ABANDONED, ADVANCE_EPOCH, CANCEL, CANCELLED, CHALLENGE_TERMINAL, CONFIRM, CONSUME, CONSUMED,
    EXPIRE, EXPIRED, FAIL, FAILED, GENESIS, ISSUE, LEDGER_HEAD_DOMAIN_SEPARATOR, LEDGER_REASONS, PREPARE,
    PREPARED, QUARANTINE_USE, QUARANTINED_BY_RECOVERY, RECOVERY_REASONS, REGISTRY_VIEW, RESERVE, RESERVED,
    USE_CONSUMED, USE_TERMINAL, VOID_CHALLENGE, VOIDED_BY_RECOVERY, LedgerRefusal, replay,
)
from lilith_owner_memory.authority_ledger_journal import JournalReplay as _Replay  # noqa: E402,F401
from lilith_owner_memory.authority_ledger_journal import _epoch_dict, _refuse_unless, _valid_id  # noqa: E402,F401
from lilith_owner_memory.authority_ledger_journal import next_head as _next_head  # noqa: E402,F401
from lilith_owner_memory.authority_ledger_journal import step as _step  # noqa: E402,F401


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


# ------------------------------------------------------------- state ---

@dataclass(frozen=True)
class AuthorityLedgerStateV1:
    """One immutable authority-side ledger state: the journal plus the
    materialized rows a database would hold. A consistent state has
    `rows == replay(log).rows()`; a restored or edited DB may not."""

    log: tuple[Mapping[str, Any], ...]
    rows: Mapping[str, Any]

    @classmethod
    def from_log(cls, log: tuple[Mapping[str, Any], ...]) -> AuthorityLedgerStateV1:
        return cls(tuple(dict(op) for op in log), replay(tuple(log)).rows())

    @classmethod
    def genesis(cls, *, environment: str, recovery_epoch: A.RecoveryEpochV1, policy_version: str,
                registry_version: int, signing_key_ids: tuple[str, ...]) -> AuthorityLedgerStateV1:
        return cls.from_log(({"op": GENESIS, "environment": environment, "recoveryEpoch": recovery_epoch.to_dict(),
                              "policyVersion": policy_version, "registryVersion": registry_version,
                              "signingKeyIds": list(signing_key_ids)},))

    def replayed(self) -> _Replay:
        return replay(self.log)

    @property
    def environment(self) -> str:
        return self.replayed().environment

    @property
    def recovery_epoch(self) -> A.RecoveryEpochV1:
        return self.replayed().epoch

    @property
    def ledger_epoch(self) -> str:
        return self.replayed().ledger_epoch

    @property
    def sequence(self) -> int:
        return len(self.log)

    @property
    def head(self) -> str:
        return self.replayed().head

    def challenge(self, challenge_id: str) -> dict[str, Any] | None:
        entry = self.rows["challenges"].get(challenge_id)
        return None if entry is None else dict(entry)

    def use(self, evidence_id: str) -> dict[str, Any] | None:
        entry = self.rows["uses"].get(evidence_id)
        return None if entry is None else dict(entry)

    # ------------------------------------------------------ transitions ---

    def _append(self, op: dict[str, Any], ready: Any = None, *, creates_authority: bool) -> AuthorityLedgerStateV1:
        current = self.replayed()
        _refuse_unless(current.rows() == self.rows, "LEDGER_INTEGRITY_FAILED")
        if creates_authority:
            _refuse_unless(isinstance(ready, ReadinessResultV1) and ready.ready
                           and ready.facts.get("ledgerSequence") == self.sequence
                           and ready.facts.get("ledgerHead") == current.head, "NOT_READY_FOR_ISSUANCE")
        log = self.log + (op,)
        return AuthorityLedgerStateV1(log, replay(log).rows())

    def prepare(self, challenge_id: str, ledger_epoch: str, *, ready: Any) -> AuthorityLedgerStateV1:
        return self._append({"op": PREPARE, "challengeId": challenge_id, "ledgerEpoch": ledger_epoch}, ready,
                            creates_authority=True)

    def consume(self, challenge_id: str, *, ready: Any) -> AuthorityLedgerStateV1:
        return self._append({"op": CONSUME, "challengeId": challenge_id}, ready, creates_authority=True)

    def issue(self, challenge_id: str, evidence_id: str, evidence_digest: str, *, ready: Any) -> AuthorityLedgerStateV1:
        return self._append({"op": ISSUE, "challengeId": challenge_id, "evidenceId": evidence_id,
                             "evidenceDigest": evidence_digest}, ready, creates_authority=True)

    def reserve(self, evidence_id: str, evidence_digest: str, recovery_epoch: A.RecoveryEpochV1,
                proposal_ref_id: str, *, ready: Any) -> AuthorityLedgerStateV1:
        return self._append({"op": RESERVE, "evidenceId": evidence_id, "evidenceDigest": evidence_digest,
                             "recoveryEpoch": recovery_epoch.to_dict(), "proposalRefId": proposal_ref_id}, ready,
                            creates_authority=True)

    def confirm(self, evidence_id: str, admission_id: str, revision_id: str, *, ready: Any) -> AuthorityLedgerStateV1:
        return self._append({"op": CONFIRM, "evidenceId": evidence_id, "admissionId": admission_id,
                             "revisionId": revision_id}, ready, creates_authority=True)

    def terminate(self, kind: str, challenge_id: str) -> AuthorityLedgerStateV1:
        _refuse_unless(kind in {EXPIRE, CANCEL, FAIL}, "LEDGER_MALFORMED")
        return self._append({"op": kind, "challengeId": challenge_id}, creates_authority=False)

    def abandon(self, evidence_id: str) -> AuthorityLedgerStateV1:
        return self._append({"op": ABANDON, "evidenceId": evidence_id}, creates_authority=False)

    def record_registry(self, registry_version: int, signing_key_ids: tuple[str, ...],
                        policy_version: str) -> AuthorityLedgerStateV1:
        return self._append({"op": REGISTRY_VIEW, "registryVersion": registry_version,
                             "signingKeyIds": list(signing_key_ids), "policyVersion": policy_version},
                            creates_authority=False)


# ---------------------------------------------------- recovery ceremony ---

def _current_signing_keys(parsed: A.AuthorityRegistryV1) -> tuple[str, ...]:
    return tuple(sorted(key_id for key_id, key in parsed.keys.items()
                        if key.current and key.signing_domain == A.OWNER_ACTOR
                        and key.recovery_epoch == parsed.recovery_epoch))


def begin_recovery(state: AuthorityLedgerStateV1, *, witness: R.RecoveryWitnessV1, new_random: str,
                   registry: Mapping[str, Any], registry_root: A.TrustedRegistryRootV1,
                   reason: str) -> AuthorityLedgerStateV1:
    """Step 1 of the TEST ceremony: advance the ledger to the next epoch.

    The next epoch is `(witness.counter + 1, new_random)`: it advances from
    the independently trusted witness, never from a possibly stale ledger.
    It is authorized by the owner-signed registry at that epoch, whose
    version must exceed the witness floor. The ledger may be stale or
    restored; it is not trusted, only superseded.
    """
    _refuse_unless(reason in RECOVERY_REASONS, "RECOVERY_REASON_INVALID")
    _refuse_unless(isinstance(witness, R.RecoveryWitnessV1) and witness.environment == state.environment,
                   "RECOVERY_WITNESS_INVALID")
    try:
        new_epoch = A.RecoveryEpochV1(witness.current_recovery_epoch.counter + 1, new_random)
        A.RecoveryEpochV1.from_dict(new_epoch.to_dict())
    except OwnerProofError as exc:
        raise LedgerRefusal("RECOVERY_EPOCH_NOT_ADVANCING") from exc
    _refuse_unless(new_random != witness.current_recovery_epoch.random, "RECOVERY_EPOCH_NOT_ADVANCING")
    policy = registry.get("policyVersion") if isinstance(registry, Mapping) else None
    try:
        context = A.AuthorityVerificationContextV1(
            environment=witness.environment, purpose=A.NEW_ADMISSION, registry_root=registry_root,
            trusted_minimum_registry_version=witness.minimum_registry_version + 1,
            expected_recovery_epoch=new_epoch, policy_version=policy)
    except (TypeError, ValueError) as exc:
        raise LedgerRefusal("RECOVERY_REGISTRY_UNVERIFIED") from exc
    checked = AV.verify_authority_registry(context=context, registry=registry)
    if not checked.verified:
        raise LedgerRefusal("RECOVERY_REGISTRY_NOT_ADVANCING" if checked.reason == "REGISTRY_DOWNGRADE"
                            else "RECOVERY_REGISTRY_UNVERIFIED", checked.reason)
    parsed = A.AuthorityRegistryV1.from_verified_dict(registry)
    keys = _current_signing_keys(parsed)
    _refuse_unless(bool(keys), "RECOVERY_NO_SIGNING_KEY")
    return state._append({"op": ADVANCE_EPOCH, "previousEpoch": state.recovery_epoch.to_dict(),
                          "newEpoch": new_epoch.to_dict(), "reason": reason,
                          "fromWitnessDigest": witness.digest, "registryVersion": parsed.registry_version,
                          "signingKeyIds": list(keys), "policyVersion": parsed.policy_version},
                         creates_authority=False)


def quarantine_pre_recovery(state: AuthorityLedgerStateV1) -> AuthorityLedgerStateV1:
    """Step 3 of the TEST ceremony (after the witness records the new epoch):
    void every PREPARED challenge and quarantine every RESERVED evidence use
    bound to an older epoch. Terminal records stay as history, unchanged."""
    current = state.replayed()
    for challenge_id in sorted(current.challenges):
        entry = current.challenges[challenge_id]
        if entry["state"] == PREPARED and entry["ledgerEpoch"] != current.ledger_epoch:
            state = state._append({"op": VOID_CHALLENGE, "challengeId": challenge_id}, creates_authority=False)
    for evidence_id in sorted(current.uses):
        entry = current.uses[evidence_id]
        if entry["state"] == RESERVED and entry["recoveryEpoch"] != current.epoch.to_dict():
            state = state._append({"op": QUARANTINE_USE, "evidenceId": evidence_id}, creates_authority=False)
    return state


def recovery_transition_record(before: AuthorityLedgerStateV1, after: AuthorityLedgerStateV1, *,
                               previous_witness: R.RecoveryWitnessV1,
                               new_witness: R.RecoveryWitnessV1) -> dict[str, Any]:
    """The acknowledgement a completed TEST ceremony produces
    (`RecoveryEpochTransitionV1`). It is a record, not an authority."""
    old, new = before.replayed(), after.replayed()
    advance = next(op for op in reversed(after.log) if op["op"] == ADVANCE_EPOCH)
    voided = sorted(op["challengeId"] for op in after.log[before.sequence:] if op["op"] == VOID_CHALLENGE)
    quarantined = sorted(op["evidenceId"] for op in after.log[before.sequence:] if op["op"] == QUARANTINE_USE)
    reauthorize = sorted(set(voided) | {cid for cid, entry in new.challenges.items()
                                         if entry["state"] == CONSUMED and entry["ledgerEpoch"] != new.ledger_epoch
                                         and not any(u.get("state") == USE_CONSUMED
                                                     for eid, u in new.uses.items()
                                                     if new.issued.get(eid, {}).get("challengeId") == cid)})
    return {
        "schemaVersion": 1,
        "kind": "RecoveryEpochTransitionV1",
        "environment": new.environment,
        "reason": advance["reason"],
        "authorizationBasis": "OWNER_SIGNED_REGISTRY_AT_NEW_EPOCH",
        "previousEpoch": previous_witness.current_recovery_epoch.to_dict(),
        "restoredLedgerEpoch": old.epoch.to_dict(),
        "newEpoch": new.epoch.to_dict(),
        "previousLedgerEpoch": previous_witness.ledger_epoch,
        "newLedgerEpoch": new.ledger_epoch,
        "registryVersion": new.registry_view,
        "previousWitnessVersion": previous_witness.witness_version,
        "witnessVersion": new_witness.witness_version,
        "voidedChallengeIds": voided,
        "quarantinedEvidenceIds": quarantined,
        "retainedTerminalChallenges": sum(1 for e in new.challenges.values() if e["state"] in CHALLENGE_TERMINAL),
        "retainedTerminalEvidenceUses": sum(1 for e in new.uses.values() if e["state"] in USE_TERMINAL),
        "historicalEvidenceRetained": True,
        "ownerReauthorizationRequired": reauthorize,
        "reconciliationRequired": quarantined,
        "rollbackDetectionScope": R.ROLLBACK_DETECTION_SCOPE,
        "wholeHostRollbackProtected": R.WHOLE_HOST_ROLLBACK_PROTECTED,
    }


# ----------------------------------------------------------- witness ---

class SyntheticWitnessSignerV1:
    """TEST-ONLY witness writer. It signs only monotonic successors of the
    witness it last signed, so it can never lower the floor or rewind the
    ledger position. It is not an authority signer: it signs no evidence,
    registry, or challenge."""

    def __init__(self, *, signing_key: Ed25519PrivateKey, witness_key_id: str, environment: str):
        if not isinstance(signing_key, Ed25519PrivateKey):
            raise TypeError("signing key must be an in-process Ed25519 key object")
        if not (isinstance(witness_key_id, str) and witness_key_id.startswith(R.TEST_ONLY_WITNESS_PREFIX)):
            raise ValueError("the B1b-3c witness signer is TEST-only")
        if environment != "test":
            raise ValueError("the B1b-3c witness signer is TEST-only")
        self.__signing_key = signing_key
        self.witness_key_id = witness_key_id
        self.environment = environment
        self._last: R.RecoveryWitnessV1 | None = None

    def __reduce__(self):
        raise TypeError("the TEST witness signer is not serializable")

    def __copy__(self):
        raise TypeError("the TEST witness signer is not copyable")

    def __deepcopy__(self, memo):
        raise TypeError("the TEST witness signer is not copyable")

    def public_key_b64(self) -> str:
        return _b64(self.__signing_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))

    def sign_state(self, state: AuthorityLedgerStateV1, *, updated_at: str) -> dict[str, Any]:
        """Witness `state`, as a successor of the last witness signed."""
        r = state.replayed()
        previous = self._last
        unsigned = {
            "protocol": R.WITNESS_PROTOCOL,
            "schemaVersion": R.WITNESS_SCHEMA_VERSION,
            "environment": r.environment,
            "witnessVersion": 1 if previous is None else previous.witness_version + 1,
            "previousWitnessDigest": None if previous is None else previous.digest,
            "currentRecoveryEpoch": r.epoch.to_dict(),
            "minimumRegistryVersion": r.registry_view,
            "policyVersion": r.policy_version,
            "ledgerSequence": r.sequence,
            "ledgerHead": r.head,
            "updatedAt": updated_at,
            "witnessKeyId": self.witness_key_id,
        }
        signed = {**unsigned, "signature": _b64(self.__signing_key.sign(R.witness_signing_bytes(unsigned)))}
        parsed = R.RecoveryWitnessV1.from_verified_dict(signed)
        if previous is not None:
            reason = R.witness_succession_reason(previous, parsed)
            if reason is not None:
                raise ValueError(reason)
        self._last = parsed
        return signed

    def restore_last(self, witness: Mapping[str, Any]) -> None:
        """TEST-ONLY: model a restored witness store (the witness writer's own
        last-signed state rolled back with it)."""
        self._last = R.RecoveryWitnessV1.from_verified_dict(witness)


# ------------------------------------------------------ restore readiness ---

RESTORE_READY = "RESTORE_READY"
NOT_READY = "NOT_READY"

# Closed, ordered, fail-closed readiness taxonomy.
READINESS_REASONS = (
    "MALFORMED_INPUT",
    "AUTHORITY_STATE_MISSING",
    "WITNESS_MISSING",
    "WITNESS_KEY_IS_AUTHORITY_KEY",
    "WITNESS_INVALID",
    "ENVIRONMENT_MISMATCH",
    "LEDGER_INTEGRITY_FAILED",
    "TERMINAL_STATE_REOPENED",
    "LEDGER_EPOCH_STALE",
    "LEDGER_EPOCH_FORKED",
    "LEDGER_EPOCH_AHEAD_OF_WITNESS",
    "POLICY_VERSION_NOT_ACCEPTABLE",
    "REGISTRY_MISSING",
    "REGISTRY_DOWNGRADE",
    "REGISTRY_EPOCH_MISMATCH",
    "REGISTRY_UNVERIFIED",
    "BROKER_REGISTRY_VIEW_STALE",
    "LEDGER_BEHIND_WITNESS",
    "LEDGER_AHEAD_OF_WITNESS",
    "LEDGER_HEAD_MISMATCH",
    "REQUIRED_KEY_UNAVAILABLE",
    "NONTERMINAL_PRE_RECOVERY_WORK",
    "PRIVACY_BOUNDARY_STALE",
    "PRIVACY_BOUNDARY_UNVERIFIED",
)

# Reasons that make the witness itself suspect: historical reads must not
# trust its registry floor either.
_WITNESS_SUSPECT = frozenset({"LEDGER_EPOCH_AHEAD_OF_WITNESS", "LEDGER_AHEAD_OF_WITNESS"})


@dataclass(frozen=True)
class ReadinessResultV1:
    status: str
    reason: str | None = None
    detail: str | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)

    @property
    def ready(self) -> bool:
        return self.status == RESTORE_READY


class _NotReady(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        assert reason in READINESS_REASONS, reason
        self.reason = reason
        self.detail = detail


def _ready_unless(condition: bool, reason: str, detail: str | None = None) -> None:
    if not condition:
        raise _NotReady(reason, detail)


def _registry_public_keys(registry: Any) -> frozenset[bytes]:
    keys: set[bytes] = set()
    if isinstance(registry, Mapping) and isinstance(registry.get("keys"), list):
        for record in registry["keys"]:
            try:
                keys.add(A._public_key(record["publicKey"]))
            except (OwnerProofError, KeyError, TypeError):
                continue
    return frozenset(keys)


def _row_regressed(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> bool:
    """True when a row shows an earlier (less terminal) state than the journal."""
    for table, terminal in (("challenges", CHALLENGE_TERMINAL), ("uses", USE_TERMINAL)):
        for key, entry in expected[table].items():
            row = actual.get(table, {}).get(key)
            if entry["state"] in terminal and (row is None or row.get("state") not in terminal):
                return True
    return False


def evaluate_restore_readiness(*, state: AuthorityLedgerStateV1 | None, witness: Mapping[str, Any] | None,
                               witness_anchor: R.TrustedWitnessAnchorV1, registry: Mapping[str, Any] | None,
                               registry_root: A.TrustedRegistryRootV1, environment: str,
                               privacy: R.PrivacyBoundaryObservationV1) -> ReadinessResultV1:
    """May a restored broker/runtime resume authority issuance? Pure; fail closed.

    RESTORE_READY is LEDGER-ONLY evidence: it proves the ledger matches a
    surviving witness. A witness restored together with the ledger matches
    too, so RESTORE_READY never means whole-host rollback protection.
    """
    facts: dict[str, Any] = {
        "rollbackDetectionScope": R.ROLLBACK_DETECTION_SCOPE,
        "wholeHostRollbackProtected": R.WHOLE_HOST_ROLLBACK_PROTECTED,
        "authorityIssuanceAllowed": False,
        "historicalReadsAllowed": False,
    }
    verified_witness = None
    registry_ok = False
    try:
        _ready_unless(isinstance(witness_anchor, R.TrustedWitnessAnchorV1)
                      and isinstance(registry_root, A.TrustedRegistryRootV1)
                      and isinstance(privacy, R.PrivacyBoundaryObservationV1), "MALFORMED_INPUT")
        try:
            privacy.validate()
        except OwnerProofError as exc:
            raise _NotReady("MALFORMED_INPUT") from exc
        _ready_unless(state is not None, "AUTHORITY_STATE_MISSING")
        _ready_unless(isinstance(state, AuthorityLedgerStateV1), "MALFORMED_INPUT")
        _ready_unless(witness is not None, "WITNESS_MISSING")
        checked = R.verify_recovery_witness(anchor=witness_anchor, witness=witness, environment=environment,
                                            registry_root=registry_root,
                                            authority_public_keys=_registry_public_keys(registry))
        _ready_unless(checked.reason != "WITNESS_KEY_IS_AUTHORITY_KEY", "WITNESS_KEY_IS_AUTHORITY_KEY")
        _ready_unless(checked.verified, "WITNESS_INVALID", checked.reason)
        verified_witness = w = checked.witness
        facts.update(witnessVersion=w.witness_version, witnessLedgerEpoch=w.ledger_epoch,
                     minimumRegistryVersion=w.minimum_registry_version)

        # Registry freshness against the witness floor decides historical reads
        # too, so evaluate it now; report it in order below.
        context = R.witness_authority_context(w, registry_root=registry_root, purpose=A.NEW_ADMISSION)
        registry_result = None if registry is None else AV.verify_authority_registry(context=context,
                                                                                     registry=registry)
        registry_ok = registry_result is not None and registry_result.verified

        try:
            journal = state.replayed()
        except LedgerRefusal as exc:
            raise _NotReady("LEDGER_INTEGRITY_FAILED", exc.reason) from exc
        facts.update(ledgerSequence=journal.sequence, ledgerHead=journal.head, ledgerEpoch=journal.ledger_epoch)
        _ready_unless(journal.environment == environment == w.environment, "ENVIRONMENT_MISMATCH")
        rows = journal.rows()
        if rows != state.rows:
            _ready_unless(not _row_regressed(rows, state.rows), "TERMINAL_STATE_REOPENED")
            raise _NotReady("LEDGER_INTEGRITY_FAILED", "ROWS_DIFFER_FROM_JOURNAL")

        order = R.compare_epochs(w.current_recovery_epoch, journal.epoch)
        _ready_unless(order != R.EPOCH_OLDER, "LEDGER_EPOCH_STALE")
        _ready_unless(order != R.EPOCH_FORKED, "LEDGER_EPOCH_FORKED")
        _ready_unless(order != R.EPOCH_NEWER, "LEDGER_EPOCH_AHEAD_OF_WITNESS")
        _ready_unless(journal.policy_version == w.policy_version, "POLICY_VERSION_NOT_ACCEPTABLE")

        _ready_unless(registry is not None, "REGISTRY_MISSING")
        if not registry_ok:
            _ready_unless(registry_result.reason != "REGISTRY_DOWNGRADE", "REGISTRY_DOWNGRADE")
            _ready_unless(registry_result.reason != "REGISTRY_EPOCH_MISMATCH", "REGISTRY_EPOCH_MISMATCH")
            raise _NotReady("REGISTRY_UNVERIFIED", registry_result.reason)
        parsed = A.AuthorityRegistryV1.from_verified_dict(registry)
        _ready_unless(journal.registry_view <= parsed.registry_version, "REGISTRY_DOWNGRADE", "BELOW_BROKER_VIEW")
        _ready_unless(journal.registry_view >= w.minimum_registry_version
                      and journal.registry_view == parsed.registry_version, "BROKER_REGISTRY_VIEW_STALE")

        _ready_unless(journal.sequence >= w.ledger_sequence, "LEDGER_BEHIND_WITNESS")
        _ready_unless(journal.sequence <= w.ledger_sequence, "LEDGER_AHEAD_OF_WITNESS")
        _ready_unless(journal.head == w.ledger_head, "LEDGER_HEAD_MISMATCH")

        current_keys = set(_current_signing_keys(parsed))
        _ready_unless(bool(journal.signing_key_ids) and set(journal.signing_key_ids) <= current_keys
                      and all(not parsed.keys[k].compromised for k in journal.signing_key_ids),
                      "REQUIRED_KEY_UNAVAILABLE")

        stale_prepared = any(e["state"] == PREPARED and e["ledgerEpoch"] != journal.ledger_epoch
                             for e in journal.challenges.values())
        stale_reserved = any(e["state"] == RESERVED and e["recoveryEpoch"] != journal.epoch.to_dict()
                             for e in journal.uses.values())
        _ready_unless(not (stale_prepared or stale_reserved), "NONTERMINAL_PRE_RECOVERY_WORK")

        _ready_unless(privacy.status != R.PRIVACY_OLDER_THAN_REQUIRED, "PRIVACY_BOUNDARY_STALE")
        _ready_unless(privacy.status == R.PRIVACY_AT_OR_AFTER_REQUIRED, "PRIVACY_BOUNDARY_UNVERIFIED",
                      privacy.status)
    except _NotReady as not_ready:
        facts["historicalReadsAllowed"] = (verified_witness is not None and registry_ok
                                           and not_ready.reason not in _WITNESS_SUSPECT
                                           and not_ready.reason != "ENVIRONMENT_MISMATCH")
        return ReadinessResultV1(NOT_READY, not_ready.reason, not_ready.detail, facts)
    facts.update(authorityIssuanceAllowed=True, historicalReadsAllowed=True)
    return ReadinessResultV1(RESTORE_READY, None, None, facts)
