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


# ------------------------------------------------------------------ deployment (OWNER_PROD, 2026-11) ---

DEV_DEPLOYMENT = ("dev", "DEV_SYNTHETIC")
PROD_DEPLOYMENT = ("prod", "OWNER_PROD")
DEPLOYMENT_FIELDS = frozenset({"schemaVersion", "environment", "profile"})


def read_deployment(*, root: Path | str = Path("/"), owner_uid: int = 0) -> tuple[str, str]:
    """(environment, profile) of this host. No `deployment.json` (every DEV host today) is DEV_SYNTHETIC, exactly as
    before. A present file must be root-owned, not group/other-writable and exactly one of the two fixed pairs; any
    other content raises (fail closed: a host never silently falls back to another profile). `root` and `owner_uid`
    are TEST seams."""
    root = Path(root)
    path = _host(root, P.DEPLOYMENT)
    if not os.path.lexists(path):
        return DEV_DEPLOYMENT
    document, _raw, status = _read_document(root, P.DEPLOYMENT, owner_uid=owner_uid)
    if status != "OK" or not isinstance(document, dict) or set(document) != DEPLOYMENT_FIELDS \
            or document["schemaVersion"] != 1 or type(document["schemaVersion"]) is not int:
        raise ValueError("DEPLOYMENT_INVALID")
    pair = (document["environment"], document["profile"])
    if pair not in (DEV_DEPLOYMENT, PROD_DEPLOYMENT):
        raise ValueError("DEPLOYMENT_INVALID")
    return pair


# ------------------------------------------------- owner registration (First Memory, DEV_SYNTHETIC) ---

OWNER_REGISTRATION_PROTOCOL = "LILITH_OWNER_REGISTRATION_DEV"
# OWNER_PROD: its own protocol name, so a DEV registration can never be read as a PROD one or the reverse.
OWNER_REGISTRATION_PROTOCOLS = {"dev": OWNER_REGISTRATION_PROTOCOL, "prod": "LILITH_OWNER_REGISTRATION_PROD"}
OWNER_REGISTRATION_FIELDS = frozenset({
    "protocol", "schemaVersion", "environment", "ownerPrincipal", "rpId", "origin", "registryTupleVersion",
    "privacyNoticeVersion", "brokerReleases", "credentials"})
MAX_OWNER_CREDENTIALS = 8
OWNER_REGISTRATION_MISSING = "OWNER_REGISTRATION_MISSING"
OWNER_REGISTRATION_INVALID = "OWNER_REGISTRATION_INVALID"


@dataclass(frozen=True)
class OwnerRegistrationV1:
    """The registered owner PUBLIC credentials and the deployment's owner-proof settings (root-installed).

    Only the fixed DEV_SYNTHETIC owner identity is admissible (`owner_proof._DEV_SYNTHETIC_OWNER`, the `.invalid`
    relying party): a synthetic owner, never proof of a real human identity. A registered credential is a host-root
    installation of the owner's public key, not authority: every issuance still needs a fresh WebAuthn assertion
    over the exact challenge.

        registered credential != owner proof != issuance permission
    """

    owner_principal: str
    rp_id: str
    origin: str
    registry_tuple_version: str
    privacy_notice_version: str
    broker_releases: frozenset[str]
    credentials: tuple[dict[str, Any], ...]


def parse_owner_registration(document: Mapping[str, Any], *, environment: str) -> OwnerRegistrationV1:
    """Strict parse. Raises `ValueError` on any deviation; nothing is defaulted."""
    from lilith_memory import owner_proof as OP

    if not isinstance(document, Mapping) or set(document) != OWNER_REGISTRATION_FIELDS:
        raise ValueError("OWNER_REGISTRATION_FIELDS")
    if (document["protocol"], document["schemaVersion"], document["environment"]) != (
            OWNER_REGISTRATION_PROTOCOLS.get(environment, OWNER_REGISTRATION_PROTOCOL), 1, environment) \
            or type(document["schemaVersion"]) is not int:
        raise ValueError("OWNER_REGISTRATION_CONTEXT")
    identity = (document["ownerPrincipal"], document["rpId"], document["origin"])
    if environment == "prod":
        _require_prod_owner(identity, OP)
    elif identity != (OP._DEV_SYNTHETIC_OWNER, OP.SYNTHETIC_RP_ID, OP.SYNTHETIC_ORIGIN):
        raise ValueError("OWNER_REGISTRATION_NOT_DEV_SYNTHETIC")
    for name in ("registryTupleVersion", "privacyNoticeVersion"):
        if not isinstance(document[name], str) or not 0 < len(document[name]) <= 128:
            raise ValueError("OWNER_REGISTRATION_" + name.upper())
    releases = document["brokerReleases"]
    if not isinstance(releases, list) or not releases or releases != sorted(set(releases)) \
            or not all(isinstance(r, str) and 0 < len(r) <= 128 for r in releases):
        raise ValueError("OWNER_REGISTRATION_BROKER_RELEASES")
    credentials = document["credentials"]
    if not isinstance(credentials, list) or not 0 < len(credentials) <= MAX_OWNER_CREDENTIALS:
        raise ValueError("OWNER_REGISTRATION_CREDENTIALS")
    parsed = []
    for value in credentials:
        try:
            credential = OP.OwnerCredentialV1.from_dict(value)
        except (OwnerProofError, TypeError, KeyError) as exc:
            raise ValueError("OWNER_REGISTRATION_CREDENTIAL") from exc
        if (credential.owner_principal, credential.rp_id) != (identity[0], identity[1]):
            raise ValueError("OWNER_REGISTRATION_CREDENTIAL_IDENTITY")
        parsed.append(credential.to_dict())
    if len({c["recordId"] for c in parsed}) != len(parsed) or len({c["credentialId"] for c in parsed}) != len(parsed):
        raise ValueError("OWNER_REGISTRATION_DUPLICATE_CREDENTIAL")
    return OwnerRegistrationV1(identity[0], identity[1], identity[2], document["registryTupleVersion"],
                               document["privacyNoticeVersion"], frozenset(releases), tuple(parsed))


_PROD_PRINCIPAL = re.compile(r"user:[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,190}\Z")
_RP_ID = re.compile(r"(?=.{1,253}\Z)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\Z")


def _require_prod_owner(identity: tuple, OP: Any) -> None:
    """OWNER_PROD: the owner's own principal and a real relying party; never the synthetic DEV identity or `.invalid`."""
    principal, rp_id, origin = identity
    if not (isinstance(principal, str) and _PROD_PRINCIPAL.match(principal) and isinstance(rp_id, str)
            and _RP_ID.match(rp_id) and not rp_id.endswith(".invalid") and isinstance(origin, str)
            and (origin == "https://" + rp_id or (origin.startswith("https://") and origin.endswith("." + rp_id)))
            and principal != OP._DEV_SYNTHETIC_OWNER and not principal.endswith(".invalid")):
        raise ValueError("OWNER_REGISTRATION_NOT_OWNER_PROD")


def read_owner_registration(*, environment: str, root: Path | str = Path("/"),
                            owner_uid: int = 0) -> tuple[OwnerRegistrationV1 | None, str | None]:
    """(registration, None) or (None, OWNER_REGISTRATION_MISSING | OWNER_REGISTRATION_INVALID). Read per request.
    `root` and `owner_uid` are TEST seams."""
    root = Path(root)
    if not _directory_ok(_host(root, P.OWNER_REGISTRATION_DIR), owner_uid=owner_uid):
        return None, (OWNER_REGISTRATION_MISSING if not os.path.lexists(_host(root, P.OWNER_REGISTRATION_DIR))
                      else OWNER_REGISTRATION_INVALID)
    if sorted(os.listdir(_host(root, P.OWNER_REGISTRATION_DIR))) not in ([], ["owner-registration.json"]):
        return None, OWNER_REGISTRATION_INVALID
    document, _raw, status = _read_document(root, P.OWNER_REGISTRATION, owner_uid=owner_uid)
    if status != "OK":
        return None, OWNER_REGISTRATION_MISSING if status == "ABSENT" else OWNER_REGISTRATION_INVALID
    try:
        return parse_owner_registration(document, environment=environment), None
    except ValueError:
        return None, OWNER_REGISTRATION_INVALID
