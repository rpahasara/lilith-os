#!/usr/bin/env python3
"""15B2b-B1b-3e M-B12 PR-B1: PR-3 off-host material assembly and validation (owner side, pure).

Record: docs/architecture/slice-15b2b-b1b3e-mb12-prb1-prerequisite-tooling.md.
REPOSITORY ONLY. It reads no host and no private key. It takes the owner's retained PUBLIC bytes (K-ACT and K-WIT
publications, the registry-root anchor, Registry V1, the genesis pin, the authorization register, the successor
ceremony register), checks each against the accepted repository records, and assembles one candidate of the
`OwnerOffHostMaterialV1` package input (preflight §19 E-21, §22; `pr1_acceptance.OwnerOffHostMaterialV1`).

    candidate assembled != PR-3 full material accepted;  owner confirmation != owner acceptance of the package
    register entry != authorization;  pin != K-ROOT, != K-WIT;  PR-3 holds records, never authority

What it never does: invent a fingerprint (each comes from the owner's bytes and must equal the record), fill the
authorization-ID list or the burned-ordinal register (both must be EMPTY at PR-1: E-21, and the registers must say
so), create the successor ceremony register (the owner supplies it), or emit `status=PRESENT` unless an owner
confirmation of this exact candidate digest is ESTABLISHED. A SYNTHETIC_FIXTURE is never a package input.

Owner-confirmation trust boundary. A caller-supplied confirmation document is never evidence of an owner decision by
itself (DEV_SYNTHETIC owner acts are unsigned). Its only established binding is a merged owner record pinned in
source: `DEV_ACCEPTED_CANDIDATES` (candidate digest -> confirmation record SHA-256), which is EMPTY, so every DEV
package input is REFUSED. `package_input` assembles the candidate itself from the owner inputs; it never takes an
assembled object. DEV expectations and pins cannot be overridden; TEST must pass an explicit `Pr3TrustV1`.

E-25 … E-28 (owner freshness, record 1, P3-3 storage, envelope 1) are NOT bound here: the verifier input has no field
for them (OD-M11-13). `offhost_reproduction` is the RR-38 B comparison of this material with a PR-1 package.

Forms (off-host, owner workstation; stdlib + rfc8785 + the repository's lilith_owner_memory):

    ... candidate <inputs.json>                       the candidate and its digest
    ... package-input <inputs.json> <confirmation.json>  the E-21 verifier input, or REFUSED
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
_OWNER_MEMORY = HERE.parent
if str(_OWNER_MEMORY) not in sys.path:
    sys.path.insert(0, str(_OWNER_MEMORY))

import rfc8785  # noqa: E402

from lilith_owner_memory import authority_contracts as A  # noqa: E402
from lilith_owner_memory import authority_verifier as AV  # noqa: E402
from lilith_owner_memory import burned_identities as BI  # noqa: E402
from lilith_owner_memory import pr1_bootstrap as B  # noqa: E402
from lilith_owner_memory import rotation_contracts as RC  # noqa: E402
from lilith_owner_memory import successor_custody as SC  # noqa: E402
from lilith_owner_memory import witness_readiness as WR  # noqa: E402

CANDIDATE_TYPE = "LILITH_PR3_OFFHOST_MATERIAL_CANDIDATE"
CANDIDATE_SCHEMA_VERSION = 1
CANDIDATE_DOMAIN = b"LILITH_PR3_OFFHOST_MATERIAL_CANDIDATE_V1\x00"
CONFIRMATION_TYPE = "LILITH_PR3_MATERIAL_OWNER_CONFIRMATION"
SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"
OWNER_RETAINED = "OWNER_RETAINED_PUBLIC_BYTES"
EVIDENCE_CLASSES = (SYNTHETIC_FIXTURE, OWNER_RETAINED)

INPUT_TYPE = "LILITH_PR3_MATERIAL_INPUTS"
INPUT_FIELDS = frozenset({"inputType", "schemaVersion", "environment", "evidenceClass", "kActPublication",
                          "kWitPublication", "registryRoot", "registry", "genesisPin", "authorizationRegister",
                          "ceremonyRegister"})
CONFIRMATION_FIELDS = frozenset({"confirmationType", "schemaVersion", "environment", "confirmedCandidateDigest",
                                 "confirmationRecordSha256", "confirmedAt"})
SOURCES = ("kActPublication", "kWitPublication", "registryRoot", "registry", "genesisPin", "authorizationRegister",
           "ceremonyRegister")

# The accepted DEV records (public values only; each names its repository record).
DEV_EXPECTED = {
    "kActPublicationFileSha256": "d76479762007afef828f3901591647dc4a2fb2205f4afac527b66d2cc9c6b032",  # M-B11 §12
    "kActPublicKeySha256": "dd13a1fb302375a4e7ec81131a72920e23e365e06a0b6dc9bb7ab124dadc01ed",        # B3, M-B3
    "kWitPublicKeySha256": "5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf",        # M-B2
    "kRootPublicKeySha256": "cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf",       # E-21, M-B1
    "registryHead": {"registryVersion": 1,                                                             # M-B3
                     "registryDigest": "fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc"},
    "genesisPinDigest": "ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4",           # Package A
    "genesisPinFileSha256": "357477369ab53790245b42cbecbe2a630110477bede5b599696699e4f5c3a590",       # E-12 copy
    "authorizationRegisterFileSha256": "8d5ab87564d0e531b7d1467c18b6d106f2a468d5d155ce9f2acb64758df85575",
    "releaseSha": "aee323e94412accbe321bc84eae78c5b8cf95afc",                                          # PR-1A
    "releaseManifestSha256": "1d578ca707a95134dab218c826408b4380e7af0b5839160f47ede37232b94e8f",      # PR-1A
}
EXPECTED_FIELDS = frozenset(DEV_EXPECTED)
# Owner PR-3 confirmations established by a merged owner record: candidate digest -> confirmation record SHA-256.
DEV_ACCEPTED_CANDIDATES: Mapping[str, str] = {}
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
NONCLAIMS = ("candidate assembled != PR-3 full material accepted", "register entry != authorization",
             "pin != K-ROOT, != K-WIT", "E-25..E-28 owner-side bindings: NOT BOUND (OD-M11-13)",
             "authorityGranted: false")


@dataclass(frozen=True)
class Pr3TrustV1:
    """What PR-3 material is judged against. DEV: `trust_for("dev", None)` only; never caller-supplied."""

    expected: Mapping[str, Any]
    accepted_candidates: Mapping[str, str]


class Refused(ValueError):
    def __init__(self, reason: str, detail: str | None = None):
        super().__init__(reason if detail is None else f"{reason}:{detail}")
        self.reason = reason
        self.detail = detail


def _need(condition: bool, reason: str, detail: str | None = None) -> None:
    if not condition:
        raise Refused(reason, detail)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _b64u(value: Any, name: str) -> bytes:
    _need(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]+", value) is not None, "INPUT_MALFORMED", name)
    raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    _need(base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") == value, "INPUT_MALFORMED", name)
    return raw


def _strict_json(raw: bytes, name: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=SC._no_duplicate_keys)
    except (UnicodeDecodeError, ValueError) as exc:
        raise Refused("INPUT_MALFORMED", name) from exc
    _need(isinstance(value, dict), "INPUT_MALFORMED", name)
    return value


def candidate_digest(candidate: Mapping[str, Any]) -> str:
    """SHA-256(LILITH_PR3_OFFHOST_MATERIAL_CANDIDATE_V1\\0 ‖ JCS(candidate))."""
    return _sha256(CANDIDATE_DOMAIN + rfc8785.dumps(dict(candidate)))


def trust_for(environment: str, trust: Pr3TrustV1 | None) -> Pr3TrustV1:
    """DEV: the pinned trust only (a caller value is refused). Elsewhere: an explicit, complete `Pr3TrustV1`."""
    if environment == "dev":
        _need(trust is None, "DEV_TRUST_NOT_OVERRIDABLE")
        return Pr3TrustV1(dict(DEV_EXPECTED), dict(DEV_ACCEPTED_CANDIDATES))
    _need(isinstance(trust, Pr3TrustV1) and isinstance(trust.expected, Mapping)
          and set(trust.expected) == EXPECTED_FIELDS and isinstance(trust.accepted_candidates, Mapping),
          "TRUST_REQUIRED")
    return trust


def assemble(inputs: Any, *, environment: str, trust: Pr3TrustV1 | None = None) -> dict[str, Any]:
    """The candidate (`material` in the exact E-21 verifier form, `sources`, `digest`) or Refused.

    Every value is derived from the owner's bytes and compared with the trust's expectations (`DEV_EXPECTED`)."""
    expected = trust_for(environment, trust).expected
    _need(isinstance(inputs, Mapping) and set(inputs) == INPUT_FIELDS, "INPUT_MALFORMED", "fields")
    _need(inputs["inputType"] == INPUT_TYPE and type(inputs["schemaVersion"]) is int
          and inputs["schemaVersion"] == 1, "INPUT_MALFORMED", "type")
    _need(inputs["environment"] == environment, "ENVIRONMENT_MISMATCH", str(inputs["environment"]))
    _need(inputs["evidenceClass"] in EVIDENCE_CLASSES, "INPUT_MALFORMED", "evidenceClass")
    raw = {name: _b64u(inputs[name], name) for name in SOURCES}

    # K-ACT (E-2): the exact keygen bytes, = the record file, = B3.
    try:
        _value, kact = SC.parse_publication_bytes(raw["kActPublication"])
    except Exception as exc:  # noqa: BLE001 - any parse failure is a refusal, never a default
        raise Refused("KACT_PUBLICATION_INVALID", getattr(exc, "code", type(exc).__name__)) from exc
    _need(_sha256(raw["kActPublication"]) == expected["kActPublicationFileSha256"], "KACT_PUBLICATION_NOT_RECORD")
    _need(kact.public_key_sha256 == expected["kActPublicKeySha256"], "KACT_FINGERPRINT_MISMATCH")

    # K-WIT (E-10): publication fingerprint = the record.
    try:
        kwit = B.WitnessKeyPublicationV1.from_dict(B.parse_publication_document(raw["kWitPublication"]))
    except Exception as exc:  # noqa: BLE001
        raise Refused("KWIT_PUBLICATION_INVALID", getattr(exc, "code", type(exc).__name__)) from exc
    _need(kwit.public_key_sha256 == expected["kWitPublicKeySha256"], "KWIT_FINGERPRINT_MISMATCH")

    # K-ROOT (E-13 provenance): the registry-root anchor public key = the E-21 fingerprint.
    try:
        root = A.TrustedRegistryRootV1.from_dict(WR.parse_document_bytes(raw["registryRoot"]))
    except Exception as exc:  # noqa: BLE001
        raise Refused("KROOT_ANCHOR_INVALID", getattr(exc, "code", type(exc).__name__)) from exc
    _need(root.environment == environment, "KROOT_ANCHOR_ENVIRONMENT_MISMATCH")
    _need(_sha256(root.public_key) == expected["kRootPublicKeySha256"], "KROOT_FINGERPRINT_MISMATCH")

    # Registry V1 (E-13): its signature verifies under that root (the canonical verifier); head = the record.
    try:
        registry = WR.parse_document_bytes(raw["registry"])
        epoch = A.RecoveryEpochV1.from_dict(registry["recoveryEpoch"])
        context = A.AuthorityVerificationContextV1(
            environment=environment, purpose=A.NEW_ADMISSION, registry_root=root, trusted_minimum_registry_version=1,
            expected_recovery_epoch=epoch, policy_version=registry["policyVersion"])
        verified = AV.verify_authority_registry(context=context, registry=registry)
    except Exception as exc:  # noqa: BLE001
        raise Refused("REGISTRY_INVALID", getattr(exc, "code", type(exc).__name__)) from exc
    _need(verified.verified, "REGISTRY_NOT_VERIFIED", verified.reason)
    head = RC.registry_head(registry)
    _need(head.to_dict() == dict(expected["registryHead"]), "REGISTRY_HEAD_MISMATCH")

    # Genesis pin (E-12): the owner pin = the accepted candidate; its bytes = the recorded on-host copy.
    try:
        pin = WR.OwnerGenesisPinV1.from_dict(WR.parse_document_bytes(raw["genesisPin"]))
    except Exception as exc:  # noqa: BLE001
        raise Refused("GENESIS_PIN_INVALID", getattr(exc, "code", type(exc).__name__)) from exc
    _need(pin.environment == environment, "GENESIS_PIN_ENVIRONMENT_MISMATCH")
    _need(pin.genesis_witness_digest == expected["genesisPinDigest"], "GENESIS_PIN_MISMATCH")
    _need(_sha256(raw["genesisPin"]) == expected["genesisPinFileSha256"], "GENESIS_PIN_COPY_MISMATCH")

    # Authorization register (§22): no authorization at PR-1; exactly the genesis head.
    try:
        register = WR.OwnerAuthorizationRegisterV1.from_dict(WR.parse_document_bytes(raw["authorizationRegister"]))
    except Exception as exc:  # noqa: BLE001
        raise Refused("AUTHORIZATION_REGISTER_INVALID", getattr(exc, "code", type(exc).__name__)) from exc
    _need(register.environment == environment, "AUTHORIZATION_REGISTER_ENVIRONMENT_MISMATCH")
    _need(_sha256(raw["authorizationRegister"]) == expected["authorizationRegisterFileSha256"],
          "AUTHORIZATION_REGISTER_COPY_MISMATCH")
    _need(not register.authorizations, "AUTHORIZATION_LIST_NOT_EMPTY_AT_PR1")
    _need(register.head_registries == frozenset({head}), "AUTHORIZATION_REGISTER_HEADS_NOT_GENESIS_ONLY")

    # Successor ceremony register (§22): the burned-ordinal model, empty (no successor exists).
    try:
        ceremonies = SC.SuccessorCeremonyRegisterV1.from_dict(_strict_json(raw["ceremonyRegister"],
                                                                           "ceremonyRegister"))
    except Exception as exc:  # noqa: BLE001
        raise Refused("CEREMONY_REGISTER_INVALID", getattr(exc, "code", type(exc).__name__)) from exc
    _need(ceremonies.environment == environment, "CEREMONY_REGISTER_ENVIRONMENT_MISMATCH")
    _need(not ceremonies.entries, "BURNED_ORDINALS_NOT_EMPTY_AT_PR1")

    burned = BI.burned_identity(public_keys=(root.public_key, kwit.public_key, kact.public_key),
                                registry_digests=(head.digest,), genesis_witness_digests=(pin.genesis_witness_digest,))
    _need(burned is None, BI.BURNED_REHEARSAL_IDENTITY, burned)

    material = {
        "status": "PRESENT", "registerSha256": _sha256(raw["authorizationRegister"]),
        "genesisPinDigest": pin.genesis_witness_digest, "kRootPublicKeySha256": _sha256(root.public_key),
        "kWitPublicKeySha256": kwit.public_key_sha256,
        "kActPublicationSha256": _sha256(SC.canonical_publication_bytes(_value)),
        "registryHead": head.to_dict(), "releaseSha": expected["releaseSha"],
        "releaseManifestSha256": expected["releaseManifestSha256"], "authorizationIds": [], "burnedOrdinals": []}
    candidate = {"candidateType": CANDIDATE_TYPE, "schemaVersion": CANDIDATE_SCHEMA_VERSION,
                 "environment": environment, "evidenceClass": inputs["evidenceClass"], "material": material,
                 "sources": {name: _sha256(raw[name]) for name in SOURCES}}
    return {"candidate": candidate, "candidateDigest": candidate_digest(candidate), "ownerConfirmed": False,
            "pr3FullMaterialAccepted": False, "authorityGranted": False, "nonclaims": list(NONCLAIMS)}


def package_input(inputs: Any, confirmation: Any, *, environment: str, trust: Pr3TrustV1 | None = None
                  ) -> dict[str, Any]:
    """The E-21 `offHostMaterial` verifier input: assembled here from the owner inputs, and only when the owner's
    confirmation of exactly that candidate digest is established by `trust.accepted_candidates`."""
    trust = trust_for(environment, trust)
    assembled = assemble(inputs, environment=environment, trust=trust)
    candidate = assembled["candidate"]
    _need(candidate["evidenceClass"] == OWNER_RETAINED, "SYNTHETIC_FIXTURE_NOT_PACKAGE_INPUT")
    _need(confirmation is not None, "OWNER_CONFIRMATION_ABSENT")
    _need(isinstance(confirmation, Mapping) and set(confirmation) == CONFIRMATION_FIELDS
          and confirmation["confirmationType"] == CONFIRMATION_TYPE and type(confirmation["schemaVersion"]) is int
          and confirmation["schemaVersion"] == 1 and confirmation["environment"] == environment
          and isinstance(confirmation["confirmationRecordSha256"], str)
          and _HEX64.fullmatch(confirmation["confirmationRecordSha256"]) is not None
          and isinstance(confirmation["confirmedAt"], str) and _INSTANT.fullmatch(confirmation["confirmedAt"]),
          "OWNER_CONFIRMATION_MALFORMED")
    _need(confirmation["confirmedCandidateDigest"] == assembled["candidateDigest"],
          "OWNER_CONFIRMATION_DIGEST_MISMATCH")
    _need(trust.accepted_candidates.get(assembled["candidateDigest"]) == confirmation["confirmationRecordSha256"],
          "OWNER_CONFIRMATION_NOT_ESTABLISHED")
    return dict(candidate["material"])


def offhost_reproduction(material: Mapping[str, Any], package: Mapping[str, Any]) -> list[str]:
    """RR-38 B (E-18), owner side: every value the package evidence shows must equal the owner material.

    Returns the mismatches (empty = reproduced). It never trusts the package's own E-18 verdict."""
    evidence = package.get("evidence") or {}
    observed = {
        "genesisPinDigest": [(evidence.get("genesisPin") or {}).get("onHostDigest"),
                             (evidence.get("witness") or {}).get("genesisDigest")],
        "registryHead": [{"registryVersion": (evidence.get("registry") or {}).get("version"),
                          "registryDigest": (evidence.get("registry") or {}).get("digest")}],
        "kWitPublicKeySha256": [(evidence.get("kWit") or {}).get("publicKeySha256")],
        "kActPublicationSha256": [(evidence.get("kActPublication") or {}).get("publicationSha256")],
        "releaseSha": [(evidence.get("installedRelease") or {}).get("releaseSha")],
        "releaseManifestSha256": [(evidence.get("installedRelease") or {}).get("manifestSha256")],
    }
    mismatches = [f"{name}" for name, values in observed.items() if any(v != material.get(name) for v in values)]
    bound = {name: value for name, value in material.items() if name != "status"}
    if package.get("environment") is None or evidence.get("offHostRegister") not in (None, bound):
        mismatches.append("offHostRegister")
    for flag in ("authorityGranted", "activationGranted", "issuanceWired"):
        if package.get(flag) is not False:
            mismatches.append(f"NOT_DARK:{flag}")
    return mismatches


def _load(path: str) -> Any:
    return _strict_json(Path(path).read_bytes(), path)


def main(argv: list[str]) -> int:
    try:
        if len(argv) == 2 and argv[0] == "candidate":
            out = assemble(_load(argv[1]), environment="dev")
        elif len(argv) == 3 and argv[0] == "package-input":
            out = package_input(_load(argv[1]), _load(argv[2]), environment="dev")   # DEV trust: pins only
        else:
            raise Refused("USAGE")
    except (Refused, ValueError, OSError) as exc:
        print(f"mb12_pr3_material: REFUSED {getattr(exc, 'reason', type(exc).__name__)}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(out, sort_keys=True, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
