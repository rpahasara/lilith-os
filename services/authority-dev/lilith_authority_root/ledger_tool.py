"""The one explicit authority-ledger provisioning step (PR-1S, S-9; M-B6).

Two halves, one fixed CLI (`lilith-authority-ledger-dev`):

1. `provision <registryVersion>` as root: verify that the named installed
   registry verifies under the installed `TrustedRegistryRootV1` at its own
   epoch with a single current OWNER_ACTOR key, derive its GENESIS op, create
   `/var/lib/lilith-authority-dev` as `lilith-authority-dev 0700` only if it
   is absent (adopt it unchanged only if exactly that), refuse any existing
   ledger file, then re-run the CLI as the signer uid (`runuser`);
2. `provision-as-signer <registryVersion>` as the signer uid only: re-read
   and re-verify the same inputs and create the ledger (sequence 1).

Root application tooling never becomes the ledger writer: the database file
is created and written by the signer uid. The step is forward custody state,
not authority (`ledger provisioned != authority state accepted`).
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any, Callable, Mapping

from lilith_authority_dev.ledger import DurableAuthorityLedgerV1, LedgerError
from lilith_authority_host import inputs as HI
from lilith_authority_host import paths as P
from lilith_owner_memory import authority_ledger_journal as J
from lilith_owner_memory import rotation_contracts as RC

LEDGER_TOOL_ERRORS = (
    "LEDGER_TOOL_NOT_ROOT",
    "LEDGER_TOOL_NOT_SIGNER",
    "LEDGER_TOOL_INPUTS_INCOMPLETE",
    "LEDGER_TOOL_REGISTRY_NOT_INSTALLED",
    "LEDGER_TOOL_REGISTRY_UNVERIFIED",
    "LEDGER_TOOL_STATE_DIRECTORY_UNSAFE",
    "LEDGER_TOOL_ALREADY_PROVISIONED",
    "LEDGER_TOOL_SIGNER_STEP_FAILED",
)


# The genesis plan needs *a* ledger position only to validate the registry;
# the real position is derived from the op (sequence 1), never chosen.
R_GENESIS_HEAD = "0" * 64


class LedgerToolError(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        assert reason in LEDGER_TOOL_ERRORS, reason
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def verified_genesis_op(*, environment: str, registry_version: int, root: Path | str = Path("/"),
                        owner_uid: int = 0) -> tuple[dict[str, Any], Mapping[str, Any]]:
    """(GENESIS op, registry) for one installed registry verified at its own epoch."""
    inputs = HI.read_host_inputs(environment=environment, root=root, owner_uid=owner_uid)
    if inputs.registry_root is None:
        raise LedgerToolError("LEDGER_TOOL_INPUTS_INCOMPLETE", ",".join(inputs.reasons))
    registry = next((r for r in inputs.registries if r.get("registryVersion") == registry_version), None)
    if registry is None:
        raise LedgerToolError("LEDGER_TOOL_REGISTRY_NOT_INSTALLED")
    plan = RC.plan_witness_v2_genesis(environment=environment, registry=registry, registry_root=inputs.registry_root,
                                      ledger_sequence=1, ledger_head=R_GENESIS_HEAD, updated_at="2000-01-01T00:00:00Z")
    if not plan.planned:
        raise LedgerToolError("LEDGER_TOOL_REGISTRY_UNVERIFIED", plan.detail or plan.reason)
    try:
        return J.genesis_op(registry), registry
    except J.LedgerRefusal as exc:
        raise LedgerToolError("LEDGER_TOOL_REGISTRY_UNVERIFIED", exc.reason) from exc


def prepare_state_directory(*, root: Path | str = Path("/"), signer_uid: int, signer_gid: int,
                            chown: bool = True) -> str:
    """Root half: the signer-owned 0700 state directory, created if absent."""
    directory = Path(root) / P.AUTHORITY_STATE.lstrip("/")
    ledger = Path(root) / P.AUTHORITY_LEDGER.lstrip("/")
    try:
        meta = os.lstat(directory)
    except FileNotFoundError:
        os.mkdir(directory, 0o700)
        if chown:
            os.chown(directory, signer_uid, signer_gid)
        os.chmod(directory, 0o700)
        _fsync(directory.parent)
        return "CREATED"
    if not stat.S_ISDIR(meta.st_mode) or (meta.st_uid, meta.st_gid) != (signer_uid, signer_gid) \
            or stat.S_IMODE(meta.st_mode) != 0o700:
        raise LedgerToolError("LEDGER_TOOL_STATE_DIRECTORY_UNSAFE")
    for suffix in ("", "-wal", "-shm", "-journal"):
        if os.path.lexists(f"{ledger}{suffix}"):
            raise LedgerToolError("LEDGER_TOOL_ALREADY_PROVISIONED")
    return "ADOPTED_NO_MUTATION"


def provision_as_signer(*, environment: str, registry_version: int, root: Path | str = Path("/"),
                        owner_uid: int = 0, euid: int, signer_uid: int) -> RC.AuthorityLedgerObservationV1:
    """Signer half: re-verify and create the ledger at sequence 1."""
    if euid != signer_uid or euid == 0:
        raise LedgerToolError("LEDGER_TOOL_NOT_SIGNER")
    op, _registry = verified_genesis_op(environment=environment, registry_version=registry_version, root=root,
                                        owner_uid=owner_uid)
    try:
        return DurableAuthorityLedgerV1.provision(Path(root) / P.AUTHORITY_LEDGER.lstrip("/"),
                                                  environment=environment, genesis=op, expected_uid=signer_uid)
    except LedgerError as exc:
        raise LedgerToolError("LEDGER_TOOL_ALREADY_PROVISIONED" if exc.reason == "LEDGER_ALREADY_EXISTS"
                              else "LEDGER_TOOL_SIGNER_STEP_FAILED", exc.reason) from exc


def provision(*, environment: str, registry_version: int, euid: int, signer_uid: int, signer_gid: int,
              run_as_signer: Callable[[int], int], root: Path | str = Path("/"), owner_uid: int = 0,
              chown: bool = True) -> dict[str, Any]:
    """Root half, then the signer half through `run_as_signer` (runuser)."""
    if euid != 0:
        raise LedgerToolError("LEDGER_TOOL_NOT_ROOT")
    op, registry = verified_genesis_op(environment=environment, registry_version=registry_version, root=root,
                                       owner_uid=owner_uid)
    directory = prepare_state_directory(root=root, signer_uid=signer_uid, signer_gid=signer_gid, chown=chown)
    if run_as_signer(registry_version) != 0:
        raise LedgerToolError("LEDGER_TOOL_SIGNER_STEP_FAILED")
    sequence, head = J.initial_position(registry)
    return {"stateDirectory": directory, "ledgerSequence": sequence, "ledgerHead": head, "genesisOp": op,
            "authorityGranted": False}


def _fsync(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
