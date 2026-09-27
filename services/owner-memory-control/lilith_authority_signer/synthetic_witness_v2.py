"""15B2b-B1b-3e TEST-ONLY RecoveryWitnessV2 writer and authority recovery ledger
epoch adoption.

Design: docs/architecture/slice-15b2b-b1b3e-rotation-revocation-recovery.md.

Two pure TEST-only pieces, both outside any live path:

- `SyntheticWitnessV2SignerV1`: signs only successors that the pure
  `rotation_contracts` planners produced. It executes a head advance or an
  epoch advance only under a K-ROOT authorization the planner verified. It
  never signs evidence, registries, or authorizations. Witness freshness is
  not authority.
- `adopt_authorized_epoch`: the pre-witness `ADVANCE_EPOCH` record (C-4
  order) on the **authority recovery ledger** (`AuthorityLedgerStateV1`,
  owned by the authority signer boundary). It is destroy/narrow-only: it
  records adoption of a K-ROOT-authorized successor epoch, names that
  authorization, and changes no row. It never mints evidence, reopens a
  terminal state, grants authority, or makes any key current. It has no
  access to, and no notion of, the memory-broker ledgers
  (`owner_control.db`, `synthetic_evidence.db`) or L04.

Nothing here reads a file, the environment, the network, or a credential.
"""

from __future__ import annotations

import base64
from typing import Any, Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from lilith_memory.owner_proof import OwnerProofError

from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import authority_verifier as AV
from lilith_owner_memory import recovery_contracts as R
from lilith_owner_memory import rotation_contracts as RC

from . import synthetic_recovery_ledger as RL


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


class WitnessV2Refusal(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        assert reason in RC.EXECUTION_REASONS or reason in RC.WITNESS_V2_SUCCESSION_REASONS \
            or reason in RC.CHAIN_REASONS, reason
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


class SyntheticWitnessV2SignerV1:
    """TEST-ONLY V2 witness writer. It keeps its own linear chain and signs a
    successor only after a planner accepted it, then re-checks succession."""

    def __init__(self, *, signing_key: Ed25519PrivateKey, witness_key_id: str, environment: str):
        if not isinstance(signing_key, Ed25519PrivateKey):
            raise TypeError("signing key must be an in-process Ed25519 key object")
        if not (isinstance(witness_key_id, str) and witness_key_id.startswith(R.TEST_ONLY_WITNESS_PREFIX)):
            raise ValueError("the B1b-3e witness writer is TEST-only")
        if environment != "test":
            raise ValueError("the B1b-3e witness writer is TEST-only")
        self.__signing_key = signing_key
        self.witness_key_id = witness_key_id
        self.environment = environment
        self._chain: list[dict[str, Any]] = []

    def __reduce__(self):
        raise TypeError("the TEST witness writer is not serializable")

    def __copy__(self):
        raise TypeError("the TEST witness writer is not copyable")

    def __deepcopy__(self, memo):
        raise TypeError("the TEST witness writer is not copyable")

    def public_key_b64(self) -> str:
        return _b64(self.__signing_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))

    @property
    def chain(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(entry) for entry in self._chain)

    @property
    def witness(self) -> dict[str, Any]:
        return dict(self._chain[-1])

    def facts(self) -> RC.WitnessChainFactsV1:
        result = RC.witness_v2_chain_facts([RC.RecoveryWitnessV2.from_verified_dict(w) for w in self._chain])
        if not result.verified:
            raise WitnessV2Refusal(result.reason, result.detail)
        return result.facts

    def _sign(self, plan: RC.ExecutionPlanV1) -> dict[str, Any]:
        if not plan.planned:
            raise WitnessV2Refusal(plan.reason, plan.detail)
        unsigned = {**plan.successor_unsigned, "witnessKeyId": self.witness_key_id}
        signed = {**unsigned, "signature": _b64(self.__signing_key.sign(RC.witness_v2_signing_bytes(unsigned)))}
        parsed = RC.RecoveryWitnessV2.from_verified_dict(signed)
        if self._chain:
            reason = RC.witness_v2_succession_reason(RC.RecoveryWitnessV2.from_verified_dict(self._chain[-1]),
                                                     parsed)
            if reason is not None:
                raise WitnessV2Refusal(reason)
        self._chain.append(signed)
        return dict(signed)

    def genesis(self, *, registry: Mapping[str, Any], registry_root: A.TrustedRegistryRootV1,
                ledger: RL.AuthorityLedgerStateV1, updated_at: str) -> dict[str, Any]:
        if self._chain:
            raise WitnessV2Refusal("MALFORMED_INPUT", "GENESIS_OVER_EXISTING_CHAIN")
        return self._sign(RC.plan_witness_v2_genesis(environment=self.environment, registry=registry,
                                                     registry_root=registry_root, ledger_sequence=ledger.sequence,
                                                     ledger_head=ledger.head, updated_at=updated_at))

    def record_ledger_advance(self, *, ledger: RL.AuthorityLedgerStateV1, updated_at: str) -> dict[str, Any]:
        return self._sign(RC.plan_ledger_advance(chain=self.facts(), ledger_sequence=ledger.sequence,
                                                 ledger_head=ledger.head, updated_at=updated_at))

    def execute_registry_head_advance(self, *, authorization: Mapping[str, Any], prior_registry: Mapping[str, Any],
                                      target_registry: Mapping[str, Any], registry_root: A.TrustedRegistryRootV1,
                                      updated_at: str) -> dict[str, Any]:
        return self._sign(RC.plan_registry_head_advance(
            chain=self.facts(), authorization=authorization, registry_root=registry_root,
            prior_registry=prior_registry, target_registry=target_registry, updated_at=updated_at))

    def execute_epoch_advance(self, *, authorization: Mapping[str, Any], prior_registry: Mapping[str, Any],
                              target_registry: Mapping[str, Any], registry_root: A.TrustedRegistryRootV1,
                              ledger: RL.AuthorityLedgerStateV1, updated_at: str) -> dict[str, Any]:
        return self._sign(RC.plan_epoch_advance(
            chain=self.facts(), authorization=authorization, registry_root=registry_root,
            prior_registry=prior_registry, target_registry=target_registry, adoption_record=ledger.log[-1],
            ledger_sequence=ledger.sequence, ledger_head=ledger.head, updated_at=updated_at))

    def restore_chain(self, chain: tuple[Mapping[str, Any], ...]) -> None:
        """TEST-ONLY: model a restored witness store (its own chain rolled back)."""
        self._chain = [dict(entry) for entry in chain]


# ------------------------------------------ authority recovery ledger adoption ---

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


def adopt_authorized_epoch(state: RL.AuthorityLedgerStateV1, *, authorization: Mapping[str, Any],
                           witness: RC.RecoveryWitnessV2, target_registry: Mapping[str, Any],
                           registry_root: A.TrustedRegistryRootV1) -> RL.AuthorityLedgerStateV1:
    """Journal the pre-witness `ADVANCE_EPOCH` on the authority recovery ledger.

    The record names the authorization, the K-ROOT-signed successor epoch, the
    target registry version, and the prior witness digest, so the witness can
    bind exactly this adoption (C-4: ledger adoption, then witness execution
    over the post-journal head, then quarantine, then witness again). It is a
    destroy/narrow-only journal record: rows change only through the unchanged
    B1b-3c replay, and its `signingKeyIds` is an observation of the authorized
    registry that readiness re-derives, never a grant.
    """
    try:
        current = state.replayed()
    except RL.LedgerRefusal as exc:
        raise AdoptionRefusal("LEDGER_INTEGRITY_FAILED", exc.reason) from exc
    if current.rows() != state.rows:
        raise AdoptionRefusal("LEDGER_INTEGRITY_FAILED")
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
    signing = tuple(sorted(key_id for key_id, key in parsed.keys.items()
                           if key.current and key.signing_domain == A.OWNER_ACTOR
                           and key.recovery_epoch == parsed.recovery_epoch))
    op = {"op": RL.ADVANCE_EPOCH, "previousEpoch": current.epoch.to_dict(),
          "newEpoch": auth.successor_recovery_epoch.to_dict(), "reason": auth.reason,
          "fromWitnessDigest": witness.digest, "authorizationId": auth.authorization_id,
          "registryVersion": head.version, "signingKeyIds": list(signing), "policyVersion": parsed.policy_version}
    try:
        return RL.AuthorityLedgerStateV1.from_log(state.log + (op,))
    except RL.LedgerRefusal as exc:
        raise AdoptionRefusal("LEDGER_REFUSED", exc.reason) from exc


def observe_authority_recovery_ledger(state: RL.AuthorityLedgerStateV1) -> RC.AuthorityLedgerObservationV1:
    """Story 4: replay the authority recovery ledger and report its position.
    The journal is authoritative over rows; divergence is reported, not hidden."""
    journal = state.replayed()
    rows = journal.rows()
    reopened = False
    for table, terminal in (("challenges", RL.CHALLENGE_TERMINAL), ("uses", RL.USE_TERMINAL)):
        for key, entry in rows[table].items():
            row = state.rows.get(table, {}).get(key)
            if entry["state"] in terminal and (row is None or row.get("state") not in terminal):
                reopened = True
    return RC.AuthorityLedgerObservationV1(
        environment=journal.environment, recovery_epoch=journal.epoch, sequence=journal.sequence,
        head=journal.head, registry_view=journal.registry_view, signing_key_ids=tuple(journal.signing_key_ids),
        rows_consistent=rows == state.rows, terminal_reopened=reopened)
