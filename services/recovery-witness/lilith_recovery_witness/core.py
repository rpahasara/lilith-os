"""Recovery-witness dispatch (PR-1S).

Every request is interpreted against fixed on-host inputs read at request
time (anchors, installed registries, the on-host pin and register copies;
`lilith_authority_host.inputs`), never against caller-supplied trust. The
caller supplies only: which installed registry version a transition names,
the exact K-ROOT authorization bytes, the complete root hold-store snapshot,
and the ledger position the root caller observed. Each is re-verified.

`HEALTH` and `READ_WITNESS` never write, never take the store lock for
writing, and never roll a pointer forward. Service startup performs only
the Prep A recovery scan (`writer.recover`), which produces no witness.

    service startup    != transition
    READ / HEALTH      != mutation
"""

from __future__ import annotations

import hashlib
from typing import Any, Callable, Mapping

from lilith_authority_host.inputs import HostInputsV1, authority_public_keys
from lilith_memory.owner_proof import OwnerProofError
from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import pr1_acceptance as PA
from lilith_owner_memory import pr1_bootstrap as B
from lilith_owner_memory import rotation_contracts as RC
from lilith_owner_memory import witness_readiness as WR

from . import protocol as W
from .storage import StorageLocked
from .writer import DevSyntheticWitnessWriterV1, GenesisCommitMismatch, WitnessRefusal, observe

OK = "OK"
REFUSED = "REFUSED"
STOP = "STOP"


def ledger_observation_from(value: Mapping[str, Any]) -> RC.AuthorityLedgerObservationV1:
    """Strict wire form -> observation. Types are exact; nothing is defaulted."""
    if not isinstance(value, Mapping) or set(value) != W.LEDGER_OBSERVATION_FIELDS:
        raise ValueError("ledger observation fields")
    if type(value["sequence"]) is not int or type(value["registryView"]) is not int \
            or type(value["rowsConsistent"]) is not bool or type(value["terminalReopened"]) is not bool \
            or not isinstance(value["signingKeyIds"], list) or not all(isinstance(k, str) for k in value["signingKeyIds"]) \
            or not isinstance(value["head"], str) or not isinstance(value["environment"], str):
        raise ValueError("ledger observation types")
    return RC.AuthorityLedgerObservationV1(
        environment=value["environment"], recovery_epoch=A.RecoveryEpochV1.from_dict(value["recoveryEpoch"]),
        sequence=value["sequence"], head=value["head"], registry_view=value["registryView"],
        signing_key_ids=tuple(value["signingKeyIds"]), rows_consistent=value["rowsConsistent"],
        terminal_reopened=value["terminalReopened"])


def ledger_observation_document(observation: RC.AuthorityLedgerObservationV1) -> dict[str, Any]:
    return {"environment": observation.environment, "recoveryEpoch": observation.recovery_epoch.to_dict(),
            "sequence": observation.sequence, "head": observation.head, "registryView": observation.registry_view,
            "signingKeyIds": list(observation.signing_key_ids), "rowsConsistent": observation.rows_consistent,
            "terminalReopened": observation.terminal_reopened}


def _registry(inputs: HostInputsV1, version: int) -> dict[str, Any] | None:
    for registry in inputs.registries:
        if registry.get("registryVersion") == version:
            return registry
    return None


def _registry_by_digest(inputs: HostInputsV1, digest: str) -> dict[str, Any] | None:
    for registry in inputs.registries:
        if RC.registry_digest(registry) == digest:
            return registry
    return None


class RecoveryWitnessCoreV1:
    def __init__(self, *, writer: DevSyntheticWitnessWriterV1, storage: Any, inputs: Callable[[], HostInputsV1],
                 clock: Callable[[], str]):
        if not isinstance(writer, DevSyntheticWitnessWriterV1):
            raise TypeError("the DEV_SYNTHETIC witness writer is required")
        self._writer = writer
        self._storage = storage
        self._inputs = inputs
        self._clock = clock
        self.profile = writer.profile

    def _context(self, inputs: HostInputsV1) -> WR.WitnessStoreContextV1:
        return inputs.store_context(authority_public_keys=authority_public_keys(inputs))

    def _read_inputs(self) -> HostInputsV1:
        inputs = self._inputs()
        if not isinstance(inputs, HostInputsV1) or inputs.environment != self.profile.environment:
            raise WitnessRefusal("CONTEXT_NOT_THIS_WITNESS", "INPUT_ENVIRONMENT")
        return inputs

    def health(self) -> dict[str, Any]:
        inputs = self._inputs()
        classification = "INPUTS_INCOMPLETE"
        if isinstance(inputs, HostInputsV1) and inputs.registry_root is not None and inputs.witness_anchor is not None:
            try:
                classification = WR.classify_witness_store(observation=observe(self._storage),
                                                           context=self._context(inputs)).classification
            except OSError:
                classification = "STORE_UNREADABLE"
        return {"profile": B.WITNESS_PROFILE, "environment": self.profile.environment,
                "witnessKeyId": self.profile.witness_key_id,
                "publicKeySha256": hashlib.sha256(self._writer.public_key()).hexdigest(),
                "classification": classification,
                "inputs": list(inputs.reasons) if isinstance(inputs, HostInputsV1) else ["INPUTS_UNREADABLE"],
                "genericSigning": "NOT_AVAILABLE", "authorityGranted": False}

    def dispatch(self, role: str, message: W.WitnessMessageV1) -> dict[str, Any]:
        if not isinstance(message, W.WitnessMessageV1) or role not in W.ROLE_OPERATIONS \
                or message.operation not in W.ROLE_OPERATIONS[role]:
            return {"status": REFUSED, "reason": "UNSUPPORTED_OPERATION"}
        try:
            if message.operation == W.HEALTH:
                return {"status": OK, "health": self.health()}
            if message.operation == W.READ_WITNESS:
                return self._read_witness()
            return self._mutate(message)
        except WitnessRefusal as exc:
            return {"status": REFUSED, "reason": exc.reason, "detail": exc.detail}
        except GenesisCommitMismatch as exc:
            return {"status": STOP, "reason": "GENESIS_COMMIT_MISMATCH", "detail": str(exc)}
        except StorageLocked:
            return {"status": REFUSED, "reason": "STORE_BUSY"}
        except (OwnerProofError, ValueError, TypeError, KeyError):
            return {"status": REFUSED, "reason": "INPUT_MALFORMED"}
        except OSError:
            return {"status": REFUSED, "reason": "STORE_IO_ERROR"}

    def _read_witness(self) -> dict[str, Any]:
        inputs = self._read_inputs()
        scan = WR.classify_witness_store(observation=observe(self._storage), context=self._context(inputs))
        if scan.classification != WR.CONSISTENT:
            return {"status": REFUSED, "reason": "WITNESS_NOT_CONSISTENT", "classification": scan.classification}
        return {"status": OK, "classification": scan.classification,
                "witness": WR.parse_document_bytes(scan.head_bytes)}

    def _mutate(self, message: W.WitnessMessageV1) -> dict[str, Any]:
        inputs = self._read_inputs()
        context = self._context(inputs)
        payload = message.payload
        if message.operation == W.BOOTSTRAP:
            registry = _registry(inputs, payload["registryVersion"])
            if registry is None:
                raise WitnessRefusal("GENESIS_CANDIDATE_REFUSED", "REGISTRY_NOT_INSTALLED")
            signed = self._writer.bootstrap(registry=registry,
                                            ledger_observation=ledger_observation_from(payload["ledgerObservation"]),
                                            context=context, updated_at=payload["updatedAt"])
            return {"status": OK, "witness": signed, "genesisDigest": RC.witness_v2_digest(signed)}
        if message.operation == W.RECORD_LEDGER_ADVANCE:
            signed = self._writer.record_ledger_advance(
                previous_witness_digest=payload["previousWitnessDigest"], ledger_sequence=payload["ledgerSequence"],
                ledger_head=payload["ledgerHead"], context=context, updated_at=self._clock())
            return {"status": OK, "witness": signed}
        scan = WR.classify_witness_store(observation=observe(self._storage), context=context)
        if scan.classification != WR.CONSISTENT:
            raise WitnessRefusal("STORE_NOT_CONSISTENT", scan.classification)
        prior = _registry_by_digest(inputs, scan.head.registry_digest)
        target = _registry(inputs, payload["targetRegistryVersion"])
        if prior is None or target is None:
            raise WitnessRefusal("PLAN_REFUSED", "REGISTRY_NOT_INSTALLED")
        holds, reason, detail = PA.parse_hold_snapshot(payload["holdStore"], environment=self.profile.environment)
        if holds is None:
            raise WitnessRefusal("HOLD_STORE_INVALID", reason)
        if message.operation == W.EXECUTE_REGISTRY_HEAD_ADVANCE:
            signed = self._writer.execute_registry_head_advance(
                authorization=payload["authorization"], prior_registry=prior, target_registry=target,
                hold_store=holds, context=context, updated_at=self._clock())
        else:
            signed = self._writer.execute_epoch_advance(
                authorization=payload["authorization"], prior_registry=prior, target_registry=target,
                adoption_record=payload["adoptionRecord"], ledger_sequence=payload["ledgerSequence"],
                ledger_head=payload["ledgerHead"], hold_store=holds, context=context, updated_at=self._clock())
        return {"status": OK, "witness": signed}
