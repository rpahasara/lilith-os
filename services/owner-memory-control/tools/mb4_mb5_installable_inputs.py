"""15B2b-B1b-3e M-B4/M-B5: governed derivation of the installable canonical representations (offline, public-only).

Records:
- docs/architecture/slice-15b2b-b1b3e-mb4-mb5-installable-representation-owner-decision.md (the owner rules);
- docs/architecture/slice-15b2b-b1b3e-mb4-mb5-trust-install-remediation.md (G-1 … G-7).

The accepted M-B1/M-B2/M-B3 artifacts are stored in the owner tools' stdout
form (RFC 8785 JCS plus one newline, and for E-21 a `{registryRoot,
publicKeySha256}` wrapper). The installer (`install_authority_dev.py
_canonical_document`) and the runtime (`witness_readiness.parse_document_bytes`)
accept exact JCS bytes only. This module derives, from the exact accepted
source bytes and nothing else, the three installable representations:

    trust/registry-root.json           <- E-21 wrapper 300a57dc…   (extract `registryRoot`, JCS)
    trust/witness-anchor.json          <- K-WIT publication 9e9dd078… (witness anchor document, JCS)
    registry/authority-registry.v1.json <- signed transport 3f0a59c0… (remove exactly one terminal LF)

Every rule fails closed: a wrong source SHA, schema, key identity,
fingerprint, digest, signature or canonical form is a refusal. There is no
fallback, no whitespace normalization, no re-signing and no regeneration.
A derived SHA-256 is an installation representation pin; it never replaces
the Registry V1 digest, E-21 or the K-WIT identity.

    derived representation != new identity      derivation != installation
    installable bytes      != installed bytes    nothing here is authority

It reads public bytes only. It never opens, loads or decrypts K-ROOT or
K-WIT, contacts nothing, and writes only into a new output directory the
caller names (the `derive` form).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parents[2]
for _path in (_ROOT / "services/core-api", _ROOT / "services/owner-memory-control", _TOOLS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import mb3_registry_ceremony as L  # noqa: E402
from lilith_memory.owner_proof import OwnerProofError  # noqa: E402
from lilith_owner_memory import authority_contracts as A  # noqa: E402
from lilith_owner_memory import authority_verifier as AV  # noqa: E402
from lilith_owner_memory import pr1_bootstrap as B  # noqa: E402
from lilith_owner_memory import recovery_contracts as R  # noqa: E402
from lilith_owner_memory import rotation_contracts as RC  # noqa: E402
from lilith_owner_memory import witness_readiness as WR  # noqa: E402
from lilith_owner_memory.contracts import ContractViolation, _canonical  # noqa: E402

ENVIRONMENT = "dev"
REGISTRY_VERSION = 1
ROOT_ANCHOR_NAME = "registry-root.json"
WITNESS_ANCHOR_NAME = "witness-anchor.json"
REGISTRY_NAME = "authority-registry.v1.json"
DERIVED_NAMES = (ROOT_ANCHOR_NAME, WITNESS_ANCHOR_NAME, REGISTRY_NAME)
# Where each installable file goes on DEV (install_authority_dev.py P1B-4 / P1B-5).
INSTALL_TARGETS = {
    ROOT_ANCHOR_NAME: "/etc/lilith-authority-dev/trust/registry-root.json",
    WITNESS_ANCHOR_NAME: "/etc/lilith-authority-dev/trust/witness-anchor.json",
    REGISTRY_NAME: "/etc/lilith-authority-dev/registry/authority-registry.v1.json",
}
# The accepted M-B3 export members the derivation reads (and nothing else).
EXPORT_MEMBERS = {
    "registry": "lilith-mb3-registry-public/authority-registry.v1.json",
    "manifest": "lilith-mb3/mb3-inputs.json",
    "root": "lilith-mb3/inputs/root-anchor.json",
    "kact": "lilith-mb3/inputs/kact-publication.json",
    "kwit": "lilith-mb3/inputs/kwit-publication.json",
}
MAX_MEMBER = 64 * 1024
VERIFIED_TOKEN = "MB4_MB5_INSTALLABLE_INPUTS_VERIFIED"
NON_AUTHORITY = "installation representation only; not installed; not effective; authorizes nothing"


class DerivationRefusal(Exception):
    """A closed refusal code. A refusal is a STOP; there is no fallback."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DerivationRefusal(code)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(bytes(data)).hexdigest()


@dataclass(frozen=True)
class SourcePinsV1:
    """The exact accepted source identities. Public values only."""

    export_sha256: str
    registry_transport_sha256: str
    manifest_sha256: str
    root_wrapper_sha256: str
    kact_publication_sha256: str
    kwit_publication_sha256: str
    registry_digest: str
    accepted: L.AcceptedIdentitiesV1


# M-B3 completion §1/§11 (attempt 2), M-B2 completion, M-B1 completion (E-21).
ACCEPTED_SOURCES = SourcePinsV1(
    export_sha256="c4ea3d66fdef3f6b30c63a1f7f4903a3d2d5427f0419c6e1bd7aadd12c9564d8",
    registry_transport_sha256="3f0a59c0a104934730184d28bc16e1c9215bdaa6ec1f9d94753722862f486156",
    manifest_sha256="9ce94816a28cac159b768f998d072c829b4a7fdd36d1dba3b88c2e57572aa319",
    root_wrapper_sha256="300a57dc01690868f7e6fa5dede4f7ca7278505e95b4fbbf0a2d505a18ffdb3f",
    kact_publication_sha256="d76479762007afef828f3901591647dc4a2fb2205f4afac527b66d2cc9c6b032",
    kwit_publication_sha256="9e9dd0787b3d6df8d40730c6abab728cacbe5136269ca4421160da830bb23472",
    registry_digest="fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc",
    accepted=L.ACCEPTED,
)

# The installation representation pins, derived twice off-host and byte-equal
# (remediation record §3). Representation pins, never identities.
DERIVED_SHA256 = {
    ROOT_ANCHOR_NAME: "bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687",
    WITNESS_ANCHOR_NAME: "be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a",
    REGISTRY_NAME: "46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e",
}


# ------------------------------------------------------------ strict parsing ---

def _refuse_float(_value: str) -> Any:
    raise ValueError("floats are not part of any installable document")


def _refuse_constant(_value: str) -> Any:
    raise ValueError("NaN / Infinity are not JSON")


def strict_object(raw: bytes, code: str) -> dict[str, Any]:
    """One JSON object: ASCII only, no duplicate keys, no floats, no NaN/Infinity."""
    try:
        text = bytes(raw).decode("ascii")
    except UnicodeDecodeError as exc:
        raise DerivationRefusal(code + "_NOT_ASCII") from exc
    try:
        value = json.loads(text, object_pairs_hook=L._no_duplicate_keys, parse_float=_refuse_float,
                           parse_constant=_refuse_constant)
    except (ValueError, RecursionError) as exc:
        raise DerivationRefusal(code + "_MALFORMED") from exc
    _require(isinstance(value, dict), code + "_MALFORMED")
    return value


def installable_bytes(value: Mapping[str, Any], code: str) -> bytes:
    """RFC 8785 JCS with no trailing newline, proven equal to the installer's
    and the runtime's own canonical-byte acceptance forms (neither is changed)."""
    try:
        data = _canonical(dict(value))
    except ContractViolation as exc:
        raise DerivationRefusal(code + "_NOT_CANONICALIZABLE") from exc
    installer_form = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    _require(data == installer_form, code + "_INSTALLER_FORM_DIFFERS")
    _require(value.get("environment") == ENVIRONMENT, code + "_ENVIRONMENT")
    try:
        _require(WR.parse_document_bytes(data) == dict(value), code + "_RUNTIME_FORM_DIFFERS")
    except ContractViolation as exc:
        raise DerivationRefusal(code + "_RUNTIME_FORM_DIFFERS") from exc
    _require(not data.endswith(b"\n") and strict_object(data, code) == dict(value), code + "_NOT_CANONICAL")
    return data


def _pin(raw: bytes, expected: str, code: str) -> None:
    _require(isinstance(raw, (bytes, bytearray)) and sha256_hex(raw) == expected, code + "_SHA256_MISMATCH")


# --------------------------------------------------------------- derivations ---

def derive_root_anchor(wrapper_raw: bytes, pins: SourcePinsV1 = ACCEPTED_SOURCES) -> bytes:
    """E-21 rule: extract ONLY `registryRoot` from the exact accepted wrapper."""
    _pin(wrapper_raw, pins.root_wrapper_sha256, "ROOT_WRAPPER")
    try:
        # the reviewed M-B3 schema: exactly {registryRoot, publicKeySha256}, JCS + LF,
        # fingerprint field = recomputed = E-21, accepted root keyId, `dev`, test-only
        wrapper, root = L.verify_root_anchor_bytes(bytes(wrapper_raw), pins.accepted)
    except L.Mb3Refusal as refusal:
        raise DerivationRefusal("ROOT_WRAPPER_" + refusal.code) from refusal
    inner = wrapper["registryRoot"]
    _require(isinstance(inner, dict) and set(inner) == A.TRUSTED_ROOT_FIELDS, "ROOT_ANCHOR_FIELDS")
    _require(type(inner["schemaVersion"]) is int and inner["schemaVersion"] == 1, "ROOT_ANCHOR_SCHEMA_VERSION")
    _require(inner["algorithm"] == A.ALGORITHM == "Ed25519", "ROOT_ANCHOR_ALGORITHM")
    _require(inner["rootKeyId"] == L.ROOT_KEY_ID and inner["environment"] == ENVIRONMENT, "ROOT_ANCHOR_SCOPE")
    data = installable_bytes(inner, "ROOT_ANCHOR")
    parsed = A.TrustedRegistryRootV1.from_dict(WR.parse_document_bytes(data))
    fingerprint = sha256_hex(parsed.public_key)
    _require(fingerprint == pins.accepted.kroot_public_key_sha256 == wrapper["publicKeySha256"]
             and parsed.public_key == root.public_key, "ROOT_ANCHOR_NOT_E21")
    _require(parsed.root_key_id == L.ROOT_KEY_ID and parsed.environment == ENVIRONMENT and parsed.test_only,
             "ROOT_ANCHOR_SCOPE")
    return data


def derive_witness_anchor(kwit_publication_raw: bytes, pins: SourcePinsV1 = ACCEPTED_SOURCES) -> bytes:
    """K-WIT rule: the witness anchor document of the exact accepted publication."""
    _pin(kwit_publication_raw, pins.kwit_publication_sha256, "KWIT_PUBLICATION")
    try:
        _, kwit = L.verify_kwit_publication_bytes(bytes(kwit_publication_raw), pins.accepted)
    except L.Mb3Refusal as refusal:
        raise DerivationRefusal("KWIT_PUBLICATION_" + refusal.code) from refusal
    document = B.witness_anchor_document(kwit)
    _require(set(document) == R.ANCHOR_FIELDS, "WITNESS_ANCHOR_FIELDS")
    data = installable_bytes(document, "WITNESS_ANCHOR")
    anchor = R.TrustedWitnessAnchorV1.from_dict(WR.parse_document_bytes(data))
    _require(anchor.witness_key_id == pins.accepted.kwit_key_id, "WITNESS_ANCHOR_KEY_ID")
    _require(sha256_hex(anchor.public_key) == pins.accepted.kwit_public_key_sha256, "WITNESS_ANCHOR_NOT_KWIT")
    _require(anchor.environment == ENVIRONMENT, "WITNESS_ANCHOR_ENVIRONMENT")
    return data


def derive_registry(transport_raw: bytes, *, manifest_raw: bytes, root_wrapper_raw: bytes, kact_raw: bytes,
                    kwit_raw: bytes, pins: SourcePinsV1 = ACCEPTED_SOURCES) -> bytes:
    """Registry rule: remove exactly one terminal LF, only if every accepted check passes."""
    _pin(transport_raw, pins.registry_transport_sha256, "REGISTRY_TRANSPORT")
    _pin(manifest_raw, pins.manifest_sha256, "MANIFEST")
    _pin(root_wrapper_raw, pins.root_wrapper_sha256, "ROOT_WRAPPER")
    _pin(kact_raw, pins.kact_publication_sha256, "KACT_PUBLICATION")
    _pin(kwit_raw, pins.kwit_publication_sha256, "KWIT_PUBLICATION")
    transport = bytes(transport_raw)
    # the accepted M-B3 verification over the transport file: E-21 signature,
    # frozen manifest (digest, unsigned fields), K-ACT single current, K-WIT absent
    check = L.verify_signed_registry(registry_raw=transport, manifest_raw=bytes(manifest_raw),
                                     root_anchor_raw=bytes(root_wrapper_raw), kact_raw=bytes(kact_raw),
                                     kwit_raw=bytes(kwit_raw), accepted=pins.accepted)
    _require(check.verified, "MB3_VERIFICATION_" + str(check.reason))
    _require(check.registry_digest == pins.registry_digest, "REGISTRY_DIGEST_NOT_ACCEPTED")
    # exactly one terminal LF, and no other line break or trailing whitespace
    _require(transport.endswith(b"\n") and transport.count(b"\n") == 1 and transport.count(b"\r") == 0,
             "REGISTRY_TRANSPORT_NOT_ONE_TERMINAL_LF")
    candidate = transport[:-1]
    _require(candidate[-1:] == b"}", "REGISTRY_TRANSPORT_TRAILING_BYTES")
    value = strict_object(candidate, "REGISTRY")
    try:
        _require(_canonical(value) == candidate, "REGISTRY_NOT_JCS")
    except ContractViolation as exc:
        raise DerivationRefusal("REGISTRY_NOT_JCS") from exc
    _require(installable_bytes(value, "REGISTRY") == candidate, "REGISTRY_NOT_INSTALLABLE")
    _require(set(value) == A.REGISTRY_FIELDS, "REGISTRY_FIELDS")
    _require(value["registryVersion"] == REGISTRY_VERSION and value["environment"] == ENVIRONMENT, "REGISTRY_SCOPE")
    _require(RC.registry_digest(value) == pins.registry_digest, "REGISTRY_DIGEST_CHANGED")
    manifest = strict_object(bytes(manifest_raw).rstrip(b"\n"), "MANIFEST")
    unsigned = {name: value[name] for name in A.REGISTRY_SIGNED_FIELDS}
    _require(sha256_hex(L.canonical_bytes(unsigned)) == manifest["unsignedRegistrySha256"],
             "REGISTRY_SIGNED_FIELDS_NOT_FROZEN")
    # the E-21 signature still verifies over the derived representation's own fields
    wrapper, root = L.verify_root_anchor_bytes(bytes(root_wrapper_raw), pins.accepted)
    context = A.AuthorityVerificationContextV1(
        environment=ENVIRONMENT, purpose=A.NEW_ADMISSION, registry_root=root, trusted_minimum_registry_version=1,
        expected_recovery_epoch=A.RecoveryEpochV1(L.E0_COUNTER, manifest["epochRandom"]),
        policy_version=manifest["policyVersion"])
    try:
        verified = AV.verify_authority_registry(context=context, registry=WR.parse_document_bytes(candidate))
    except (OwnerProofError, ContractViolation) as exc:
        raise DerivationRefusal("REGISTRY_E21_SIGNATURE") from exc
    _require(verified.verified, "REGISTRY_E21_SIGNATURE")
    _require(json.loads(transport.decode("ascii")) == value, "REGISTRY_SEMANTICS_CHANGED")
    return candidate


@dataclass(frozen=True)
class DerivationV1:
    files: Mapping[str, bytes]
    tokens: tuple[str, ...]

    def sha256(self) -> dict[str, str]:
        return {name: sha256_hex(self.files[name]) for name in DERIVED_NAMES}


def derive_from_members(members: Mapping[str, bytes], pins: SourcePinsV1 = ACCEPTED_SOURCES) -> DerivationV1:
    """All three representations from the accepted M-B3 export members."""
    _require(set(members) == set(EXPORT_MEMBERS), "EXPORT_MEMBERS")
    root = derive_root_anchor(members["root"], pins)
    witness = derive_witness_anchor(members["kwit"], pins)
    registry = derive_registry(members["registry"], manifest_raw=members["manifest"], root_wrapper_raw=members["root"],
                               kact_raw=members["kact"], kwit_raw=members["kwit"], pins=pins)
    manifest = strict_object(members["manifest"].rstrip(b"\n"), "MANIFEST")
    # consistency with the witness anchor M-B3 froze (JCS + LF form; not a source)
    _require(sha256_hex(witness + b"\n") == manifest["witnessAnchorSha256"], "WITNESS_ANCHOR_NOT_MB3_FROZEN")
    root_key = A.TrustedRegistryRootV1.from_dict(json.loads(root)).public_key
    witness_key = R.TrustedWitnessAnchorV1.from_dict(json.loads(witness)).public_key
    registry_keys = {A._public_key(record["publicKey"]) for record in json.loads(registry)["keys"]}
    _require(root_key != witness_key and root_key not in registry_keys and witness_key not in registry_keys,
             "KROOT_KWIT_KACT_NOT_DISTINCT")
    tokens = ("SOURCE_PINS_EXACT", "ROOT_ANCHOR_EXTRACTED_E21", "WITNESS_ANCHOR_KWIT", "MB3_VERIFICATION_PASS",
              "REGISTRY_ONE_TERMINAL_LF_REMOVED", "REGISTRY_JCS_EXACT", "REGISTRY_DIGEST_UNCHANGED",
              "REGISTRY_SIGNED_FIELDS_FROZEN", "REGISTRY_E21_SIGNATURE_VERIFIED", "WITNESS_ANCHOR_EQUALS_MB3_FROZEN",
              "KROOT_KWIT_KACT_DISTINCT", "INSTALLER_AND_RUNTIME_FORMS_EQUAL")
    return DerivationV1({ROOT_ANCHOR_NAME: root, WITNESS_ANCHOR_NAME: witness, REGISTRY_NAME: registry}, tokens)


def read_export(path: Path, pins: SourcePinsV1 = ACCEPTED_SOURCES) -> dict[str, bytes]:
    """The five members, read from the exact accepted export without extracting it."""
    source = Path(path)
    _require(source.is_file() and not source.is_symlink(), "EXPORT_UNREADABLE")
    _pin(source.read_bytes(), pins.export_sha256, "EXPORT")
    members: dict[str, bytes] = {}
    with tarfile.open(source, mode="r:") as archive:
        index: dict[str, tarfile.TarInfo] = {}
        for info in archive.getmembers():
            _require(info.name not in index, "EXPORT_DUPLICATE_MEMBER")
            index[info.name] = info
        for key, name in EXPORT_MEMBERS.items():
            info = index.get(name)
            _require(info is not None and info.isreg() and info.size <= MAX_MEMBER, "EXPORT_MEMBER:" + key)
            handle = archive.extractfile(info)
            _require(handle is not None, "EXPORT_MEMBER:" + key)
            members[key] = handle.read()
    return members


def check_pins(derivation: DerivationV1, expected: Mapping[str, str] = DERIVED_SHA256) -> None:
    _require(derivation.sha256() == dict(expected), "DERIVED_SHA256_NOT_PINNED")


def report(derivation: DerivationV1, pins: SourcePinsV1 = ACCEPTED_SOURCES) -> dict[str, Any]:
    return {
        "reportType": "LILITH_MB4_MB5_INSTALLABLE_INPUTS", "schemaVersion": 1, "environment": ENVIRONMENT,
        "sources": {"export": pins.export_sha256, "registryTransport": pins.registry_transport_sha256,
                    "manifest": pins.manifest_sha256, "rootWrapper": pins.root_wrapper_sha256,
                    "kactPublication": pins.kact_publication_sha256, "kwitPublication": pins.kwit_publication_sha256},
        "registryDigest": pins.registry_digest, "derivedSha256": derivation.sha256(),
        "derivedBytes": {name: len(derivation.files[name]) for name in DERIVED_NAMES},
        "installTargets": dict(INSTALL_TARGETS), "tokens": list(derivation.tokens), "nonAuthority": NON_AUTHORITY,
        "installed": False, "effective": False, "authorityGranted": False,
    }


def _write_outputs(out: Path, derivation: DerivationV1) -> None:
    _require(not out.exists() and not out.is_symlink(), "OUTPUT_DIRECTORY_EXISTS")
    out.mkdir(mode=0o700)
    for name in DERIVED_NAMES:
        fd = os.open(out / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
        try:
            os.write(fd, derivation.files[name])
            os.fsync(fd)
        finally:
            os.close(fd)


def check_files(directory: Path, expected: Mapping[str, str] = DERIVED_SHA256) -> dict[str, str]:
    """The staged copies are exactly the three pinned representations (nothing else)."""
    base = Path(directory)
    _require(base.is_dir() and not base.is_symlink(), "STAGED_DIRECTORY_UNREADABLE")
    _require(sorted(entry.name for entry in base.iterdir()) == sorted(DERIVED_NAMES), "STAGED_DIRECTORY_LISTING")
    observed = {}
    for name in DERIVED_NAMES:
        path = base / name
        _require(path.is_file() and not path.is_symlink(), "STAGED_FILE:" + name)
        observed[name] = sha256_hex(path.read_bytes())
    _require(observed == dict(expected), "STAGED_SHA256_NOT_PINNED")
    return observed


USAGE = ("usage: mb4_mb5_installable_inputs.py derive <export.tar> <new-output-dir> | check <export.tar> | "
         "check-files <dir>")


def main(argv: list[str]) -> int:
    try:
        if argv[:1] == ["derive"] and len(argv) == 3:
            derivation = derive_from_members(read_export(Path(argv[1])))
            _write_outputs(Path(argv[2]), derivation)
            result = report(derivation)
        elif argv[:1] == ["check"] and len(argv) == 2:
            derivation = derive_from_members(read_export(Path(argv[1])))
            check_pins(derivation)
            result = dict(report(derivation), result=VERIFIED_TOKEN)
        elif argv[:1] == ["check-files"] and len(argv) == 2:
            result = {"stagedSha256": check_files(Path(argv[1])), "result": "MB4_MB5_STAGED_FILES_PINNED",
                      "authorityGranted": False}
        else:
            print(USAGE, file=sys.stderr)
            return 2
    except DerivationRefusal as refusal:
        print(f"mb4_mb5_installable_inputs: STOP {refusal.code}", file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
