"""V2 genesis candidate and PIN-BEFORE-COMMIT bootstrap orchestration (PR-1S, RR-35).

- `candidate`: read-only. Registry v1 as installed, a private copy of the
  live ledger (it must sit at sequence 1 with the head registry v1
  implies), the fixed K-WIT keyId, and the owner-chosen `updatedAt` ->
  the exact unsigned genesis and its digest (steps 1-2). The owner
  reproduces the same digest off-host (step 3) and installs the pin copy.
- `bootstrap`: re-derives the candidate from a FRESH ledger copy; refuses
  unless the installed on-host pin equals it (step 4); asks the witness to
  `BOOTSTRAP` (the witness rebuilds and re-checks everything itself and signs
  only that exact body, step 5-6); then re-reads the witness store and
  proves the committed genesis equals the pin (step 7). A mismatch after
  commit is STOP: no second genesis is ever created (RR-40).

The ledger position is never caller-supplied: it is observed here and
re-verified by the witness against the registry-implied initial position.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from lilith_authority_dev.ledger import LedgerError, observe_copy
from lilith_authority_host import inputs as HI
from lilith_authority_host import paths as P
from lilith_authority_host.store_observer import observe_witness_state
from lilith_owner_memory import pr1_bootstrap as B
from lilith_owner_memory import witness_readiness as WR
from lilith_recovery_witness import protocol as WP
from lilith_recovery_witness.core import ledger_observation_document

GENESIS_TOOL_ERRORS = (
    "GENESIS_INPUTS_INCOMPLETE",
    "GENESIS_REGISTRY_NOT_INSTALLED",
    "GENESIS_LEDGER_ABSENT",
    "GENESIS_LEDGER_INVALID",
    "GENESIS_CANDIDATE_REFUSED",
    "GENESIS_PIN_NOT_CANDIDATE",
    "GENESIS_WITNESS_REFUSED",
    "GENESIS_COMMITTED_NOT_PINNED",
)


class GenesisToolError(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        assert reason in GENESIS_TOOL_ERRORS, reason
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def candidate(*, environment: str, registry_version: int, updated_at: str, root: Path | str = Path("/"),
              owner_uid: int = 0) -> tuple[B.GenesisCandidateV1, HI.HostInputsV1, Any]:
    root = Path(root)
    inputs = HI.read_host_inputs(environment=environment, root=root, owner_uid=owner_uid)
    if inputs.registry_root is None or inputs.witness_anchor is None:
        raise GenesisToolError("GENESIS_INPUTS_INCOMPLETE", ",".join(inputs.reasons))
    registry = next((r for r in inputs.registries if r.get("registryVersion") == registry_version), None)
    if registry is None:
        raise GenesisToolError("GENESIS_REGISTRY_NOT_INSTALLED")
    try:
        ledger = observe_copy(root / P.AUTHORITY_LEDGER.lstrip("/"), environment=environment)
    except LedgerError as exc:
        raise GenesisToolError("GENESIS_LEDGER_ABSENT" if exc.reason == "AUTHORITY_STATE_MISSING"
                               else "GENESIS_LEDGER_INVALID", exc.reason) from exc
    built = B.build_genesis_candidate(registry=registry, registry_root=inputs.registry_root,
                                      ledger_observation=ledger, updated_at=updated_at,
                                      profile=B.witness_profile(environment))
    if not built.built:
        raise GenesisToolError("GENESIS_CANDIDATE_REFUSED", built.reason)
    return built, inputs, ledger


def candidate_report(built: B.GenesisCandidateV1) -> dict[str, Any]:
    return {"candidateDigest": built.digest, "unsignedGenesis": dict(built.unsigned),
            "pin": WR.OwnerGenesisPinV1(built.unsigned["environment"], built.digest).to_dict(),
            "genesis": False, "authorityGranted": False}


def bootstrap(*, environment: str, registry_version: int, updated_at: str,
              witness_owner: Callable[[str, Mapping[str, Any]], Mapping[str, Any]], root: Path | str = Path("/"),
              owner_uid: int = 0) -> dict[str, Any]:
    root = Path(root)
    built, inputs, ledger = candidate(environment=environment, registry_version=registry_version,
                                      updated_at=updated_at, root=root, owner_uid=owner_uid)
    reason = B.candidate_pin_reason(inputs.genesis_pin, built, environment=environment)
    if reason is not None:
        raise GenesisToolError("GENESIS_PIN_NOT_CANDIDATE", reason)
    reply = witness_owner(WP.BOOTSTRAP, {"registryVersion": registry_version,
                                         "ledgerObservation": ledger_observation_document(ledger),
                                         "updatedAt": updated_at})
    if reply.get("status") != "OK":
        raise GenesisToolError("GENESIS_WITNESS_REFUSED", f"{reply.get('reason')}:{reply.get('detail')}")
    scan = WR.classify_witness_store(observation=observe_witness_state(root / P.WITNESS_STATE.lstrip("/")),
                                     context=inputs.store_context(authority_public_keys=HI.authority_public_keys(inputs)))
    if scan.classification != WR.CONSISTENT or scan.genesis is None \
            or WR.genesis_pin_reason(inputs.genesis_pin, scan.genesis, environment=environment) is not None \
            or scan.genesis.digest != built.digest:
        raise GenesisToolError("GENESIS_COMMITTED_NOT_PINNED", scan.classification)
    return {"genesisDigest": scan.genesis.digest, "pinned": True, "classification": scan.classification,
            "authorityGranted": False}
