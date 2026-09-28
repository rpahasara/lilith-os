"""TEST_ONLY fixtures for the PR-1S recovery-witness suite (repository only).

The live-capable writer runs here in the TEST environment `test` (a profile
bound to that exact environment; nothing maps it onto dev) with the fixed
K-WIT keyId and the existing TEST_ONLY fixture seed. Storage is either the
Source Prep A in-memory durability model (crash = lose everything not
fsynced) or the real filesystem port over a temporary directory.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
for path in (ROOT / "services/core-api", ROOT / "services/owner-memory-control",
             ROOT / "services/owner-memory-control/tests", ROOT / "services/authority-dev",
             ROOT / "services/recovery-witness"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import synthetic_b1b3e as F  # noqa: E402
import synthetic_b1b3e_prep_a as PA_FX  # noqa: E402
import synthetic_b1b3e_prep_b as PB  # noqa: E402
from lilith_owner_memory import authority_contracts as A  # noqa: E402
from lilith_owner_memory import authority_ledger_journal as J  # noqa: E402
from lilith_owner_memory import pr1_bootstrap as B  # noqa: E402
from lilith_owner_memory import rotation_contracts as RC  # noqa: E402
from lilith_owner_memory import successor_custody as SC  # noqa: E402
from lilith_owner_memory import successor_readiness as SR  # noqa: E402
from lilith_owner_memory import witness_readiness as WR  # noqa: E402
from lilith_recovery_witness import writer as W  # noqa: E402
from lilith_recovery_witness.credential import WitnessSigningKeyV1  # noqa: E402

ENV = "test"
PROFILE = B.witness_profile(ENV)
CUSTODY = SC.custody_profile(ENV)
T0 = "2026-09-26T07:00:00Z"


def key(name: str = "witness") -> WitnessSigningKeyV1:
    return WitnessSigningKeyV1(F.private(name))


def anchor(name: str = "witness") -> Any:
    return F.anchor(name, key_id=B.WITNESS_KEY_ID)


def initial_ledger(registry: dict[str, Any]) -> RC.AuthorityLedgerObservationV1:
    op = J.genesis_op(registry)
    sequence, head = J.initial_position(registry)
    return RC.AuthorityLedgerObservationV1(ENV, A.RecoveryEpochV1.from_dict(registry["recoveryEpoch"]), sequence,
                                           head, registry["registryVersion"], tuple(op["signingKeyIds"]))


class Harness:
    """One live-capable witness over one storage port, with its owner inputs."""

    def __init__(self, storage: Any = None, *, registry: dict[str, Any] | None = None, fault_hook=None):
        self.storage = storage if storage is not None else PA_FX.SimulatedDurableStorage()
        self.registry = registry or PB.g1()
        self.registries = [self.registry]
        self.heads = {RC.registry_head(self.registry)}
        self.issued: dict[str, tuple[str, str]] = {}
        self.fault = None
        self.writer = W.DevSyntheticWitnessWriterV1(signing_key=key(), storage=self.storage, profile=PROFILE,
                                                    fault_hook=lambda point: self.fault and self.fault(point))
        self.ledger_log: list[dict[str, Any]] = [J.genesis_op(self.registry)]
        self.ticks = 0
        self.pin: dict[str, Any] | None = None

    def tick(self) -> str:
        self.ticks += 1
        return F.stamp(self.ticks)

    @property
    def ledger(self) -> RC.AuthorityLedgerObservationV1:
        r = J.replay(tuple(self.ledger_log))
        return J.observation(r, rows=r.rows())

    def candidate(self, updated_at: str = T0) -> B.GenesisCandidateV1:
        return B.build_genesis_candidate(registry=self.registry, registry_root=F.root(),
                                         ledger_observation=self.ledger, updated_at=updated_at, profile=PROFILE)

    def register(self) -> dict[str, Any]:
        return PA_FX.owner_register(self.issued, self.heads)

    def context(self, **overrides: Any) -> WR.WitnessStoreContextV1:
        value = dict(anchor=anchor(), environment=ENV, registry_root=F.root(), genesis_pin=self.pin,
                     owner_register=self.register(), authority_public_keys=frozenset())
        value.update(overrides)
        return WR.WitnessStoreContextV1(**value)

    def pin_candidate(self, updated_at: str = T0) -> None:
        self.pin = WR.OwnerGenesisPinV1(ENV, self.candidate(updated_at).digest).to_dict()

    def bootstrap(self, updated_at: str = T0) -> dict[str, Any]:
        if self.pin is None:
            self.pin_candidate(updated_at)
        return self.writer.bootstrap(registry=self.registry, ledger_observation=self.ledger, context=self.context(),
                                     updated_at=updated_at)

    def scan(self) -> WR.WitnessRecoveryResultV1:
        return WR.classify_witness_store(observation=W.observe(self.storage), context=self.context())

    @property
    def head(self) -> RC.RecoveryWitnessV2:
        return self.scan().head

    def record_ledger(self) -> dict[str, Any]:
        ledger = self.ledger
        return self.writer.record_ledger_advance(previous_witness_digest=self.head.digest,
                                                 ledger_sequence=ledger.sequence, ledger_head=ledger.head,
                                                 context=self.context(), updated_at=self.tick())

    # K-ROOT / owner side --------------------------------------------------
    def issue_head_advance(self, target: dict[str, Any], *, reason: str, authorization_id: str) -> dict[str, Any]:
        authorization = F.head_authorization(self.registries[-1], target, reason=reason,
                                             recoveryEpoch=self.head.current_recovery_epoch.to_dict(),
                                             authorizationId=authorization_id,
                                             nonce=F.nonce("pr1s " + authorization_id))
        name, value = PA_FX.register_entry(authorization, WR.REGISTRY_HEAD_ADVANCE)
        self.issued[name] = value
        self.heads.add(RC.registry_head(target))
        self.registries.append(target)
        return authorization

    def issue_epoch_advance(self, target: dict[str, Any], *, reason: str = SR.KEY_COMPROMISE,
                            authorization_id: str = "eaa.pr1s-recovery-1") -> dict[str, Any]:
        authorization = F.epoch_authorization(self.head, target, reason=reason, authorizationId=authorization_id,
                                              successorRecoveryEpoch=target["recoveryEpoch"],
                                              nonce=F.nonce("pr1s " + authorization_id))
        name, value = PA_FX.register_entry(authorization, WR.EPOCH_ADVANCE)
        self.issued[name] = value
        self.heads.add(RC.registry_head(target))
        self.registries.append(target)
        return authorization


def hold(**overrides: Any) -> dict[str, Any]:
    return PB.hold(**overrides)
