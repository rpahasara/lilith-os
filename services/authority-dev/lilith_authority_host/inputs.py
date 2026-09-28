"""Fixed-path, read-only public on-host inputs (PR-1S).

The trust anchors, every installed K-ROOT registry generation, and the
on-host copies of the owner genesis pin and authorization register. All are
public verification material or owner-held references, installed by root
(`root:root`, `0644` files in `0755` directories), stored as RFC 8785 JCS
bytes. Every file is parsed strictly and refused on any unexpected name,
type, owner, mode, or byte form. Absence is reported per input; nothing is
defaulted, and nothing here is authority:

    registry storage != accepted registry head   (the witness decides the head)
    owner pin copy   != authority
"""

from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from lilith_memory.owner_proof import OwnerProofError
from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import recovery_contracts as R
from lilith_owner_memory import rotation_contracts as RC
from lilith_owner_memory import witness_readiness as WR

from . import paths as P
from .store_observer import ObservationError, read_regular

MAX_INPUT_BYTES = 64 * 1024
MAX_REGISTRIES = 4096
_REGISTRY_NAME = re.compile(r"authority-registry\.v([1-9][0-9]{0,15})\.json\Z")

INPUT_REASONS = (
    "REGISTRY_ROOT_ANCHOR_MISSING",
    "REGISTRY_ROOT_ANCHOR_INVALID",
    "WITNESS_ANCHOR_MISSING",
    "WITNESS_ANCHOR_INVALID",
    "REGISTRY_STORE_MISSING",
    "REGISTRY_STORE_INVALID",
    "GENESIS_PIN_COPY_MISSING",
    "GENESIS_PIN_COPY_INVALID",
    "AUTHORIZATION_REGISTER_COPY_MISSING",
    "AUTHORIZATION_REGISTER_COPY_INVALID",
    "INPUT_ENVIRONMENT_MISMATCH",
)


def authority_public_keys(inputs: "HostInputsV1") -> frozenset[bytes]:
    """K-ROOT plus every installed registry key: a witness key may equal none."""
    keys: set[bytes] = set()
    if inputs.registry_root is not None:
        keys.add(inputs.registry_root.public_key)
    for registry in inputs.registries:
        for record in registry.get("keys", []):
            try:
                keys.add(A._public_key(record["publicKey"]))
            except (OwnerProofError, KeyError, TypeError):
                continue
    return frozenset(keys)


def registry_file_name(version: int) -> str:
    return f"authority-registry.v{A._int(version, 'registry_version', 1)}.json"


@dataclass(frozen=True)
class HostInputsV1:
    environment: str
    registry_root: A.TrustedRegistryRootV1 | None = None
    witness_anchor: R.TrustedWitnessAnchorV1 | None = None
    registries: tuple[dict[str, Any], ...] = ()
    genesis_pin: dict[str, Any] | None = None
    owner_register: dict[str, Any] | None = None
    documents: Mapping[str, bytes] = field(default_factory=dict)   # path -> exact bytes read
    reasons: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.reasons

    def store_context(self, *, authority_public_keys: frozenset[bytes] = frozenset()) -> WR.WitnessStoreContextV1:
        if self.registry_root is None or self.witness_anchor is None:
            raise ValueError("trust anchors are not installed")
        return WR.WitnessStoreContextV1(anchor=self.witness_anchor, environment=self.environment,
                                        registry_root=self.registry_root, genesis_pin=self.genesis_pin,
                                        owner_register=self.owner_register,
                                        authority_public_keys=authority_public_keys)


def _host(root: Path, absolute: str) -> Path:
    return root / absolute.lstrip("/")


def _read_document(root: Path, absolute: str, *, owner_uid: int) -> tuple[dict[str, Any] | None, bytes | None, str]:
    """(document, bytes, status) with status ABSENT | INVALID | OK."""
    path = _host(root, absolute)
    try:
        meta = os.lstat(path)
    except FileNotFoundError:
        return None, None, "ABSENT"
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid != owner_uid or stat.S_IMODE(meta.st_mode) != 0o644:
        return None, None, "INVALID"
    try:
        raw = read_regular(path, limit=MAX_INPUT_BYTES)
        return WR.parse_document_bytes(raw), raw, "OK"
    except (OSError, ObservationError, OwnerProofError):
        return None, None, "INVALID"


def _directory_ok(path: Path, *, owner_uid: int) -> bool:
    try:
        meta = os.lstat(path)
    except FileNotFoundError:
        return False
    return stat.S_ISDIR(meta.st_mode) and meta.st_uid == owner_uid and stat.S_IMODE(meta.st_mode) == 0o755


def read_host_inputs(*, environment: str, root: Path | str = Path("/"), owner_uid: int = 0) -> HostInputsV1:
    """Read every public on-host input. `root` and `owner_uid` are TEST seams."""
    root = Path(root)
    reasons: list[str] = []
    documents: dict[str, bytes] = {}
    values: dict[str, Any] = {}

    def load(absolute: str, missing: str, invalid: str, parser):
        document, raw, status = _read_document(root, absolute, owner_uid=owner_uid)
        if status == "ABSENT":
            reasons.append(missing)
            return None
        if status == "INVALID":
            reasons.append(invalid)
            return None
        try:
            parsed = parser(document)
        except (OwnerProofError, TypeError, KeyError, ValueError):
            reasons.append(invalid)
            return None
        if getattr(parsed, "environment", document.get("environment")) != environment:
            reasons.append("INPUT_ENVIRONMENT_MISMATCH")
            return None
        documents[absolute] = raw
        return parsed

    values["root"] = load(P.REGISTRY_ROOT_ANCHOR, "REGISTRY_ROOT_ANCHOR_MISSING", "REGISTRY_ROOT_ANCHOR_INVALID",
                          A.TrustedRegistryRootV1.from_dict)
    values["anchor"] = load(P.WITNESS_ANCHOR, "WITNESS_ANCHOR_MISSING", "WITNESS_ANCHOR_INVALID",
                            R.TrustedWitnessAnchorV1.from_dict)
    pin = load(P.GENESIS_PIN_COPY, "GENESIS_PIN_COPY_MISSING", "GENESIS_PIN_COPY_INVALID",
               WR.OwnerGenesisPinV1.from_dict)
    register = load(P.AUTHORIZATION_REGISTER_COPY, "AUTHORIZATION_REGISTER_COPY_MISSING",
                    "AUTHORIZATION_REGISTER_COPY_INVALID", WR.OwnerAuthorizationRegisterV1.from_dict)
    registries = _read_registries(root, environment=environment, owner_uid=owner_uid, reasons=reasons,
                                  documents=documents)
    return HostInputsV1(
        environment=environment, registry_root=values["root"], witness_anchor=values["anchor"],
        registries=registries,
        genesis_pin=None if pin is None else WR.parse_document_bytes(documents[P.GENESIS_PIN_COPY]),
        owner_register=None if register is None else WR.parse_document_bytes(
            documents[P.AUTHORIZATION_REGISTER_COPY]),
        documents=documents, reasons=tuple(sorted(set(reasons), key=INPUT_REASONS.index)))


def _read_registries(root: Path, *, environment: str, owner_uid: int, reasons: list[str],
                     documents: dict[str, bytes]) -> tuple[dict[str, Any], ...]:
    directory = _host(root, P.REGISTRY_DIR)
    if not _directory_ok(directory, owner_uid=owner_uid):
        reasons.append("REGISTRY_STORE_MISSING" if not os.path.lexists(directory) else "REGISTRY_STORE_INVALID")
        return ()
    names = sorted(os.listdir(directory))
    if not names:
        reasons.append("REGISTRY_STORE_MISSING")
        return ()
    if len(names) > MAX_REGISTRIES:
        reasons.append("REGISTRY_STORE_INVALID")
        return ()
    registries = []
    for name in names:
        match = _REGISTRY_NAME.fullmatch(name)
        absolute = f"{P.REGISTRY_DIR}/{name}"
        document, raw, status = _read_document(root, absolute, owner_uid=owner_uid)
        try:
            valid = (match is not None and status == "OK"
                     and A._int(document["registryVersion"], "registry_version", 1) == int(match.group(1))
                     and document.get("environment") == environment)
            RC.registry_digest(document) if valid else None
        except (OwnerProofError, TypeError, KeyError, ValueError):
            valid = False
        if not valid:
            reasons.append("REGISTRY_STORE_INVALID")
            return ()
        documents[absolute] = raw
        registries.append(document)
    return tuple(registries)
