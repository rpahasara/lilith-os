"""15B2b-B1b-3e M-B3 / SIGN_REGISTRY_V1: public-only ceremony logic (S25 PREPARE / SIGN and laptop verification).

Records:
- docs/architecture/slice-15b2b-b1b3e-mb3-signing-continuity-owner-decision.md (the accepted model);
- docs/architecture/slice-15b2b-b1b3e-mb3-registry-ceremony-package.md (the reviewed package).

This module is control tooling, never runtime payload. It reads public bytes
only. It never opens, loads, or decrypts K-ROOT or K-WIT, never asks for a
passphrase, and never signs. The one real K-ROOT signature is made by the
unchanged `lilith_authority_owner_dev.py registry-v1` form, run once by the
reviewed phone script under a separate owner go.

    candidate manifest != authority      prompt or flag != authorization
    PREPARE != owner go != SIGN != REGISTRY_SIGNED != owner acceptance
    REGISTRY_SIGNED != installed != effective != M-B4/M-B5 authorized

The registry is built by the owner tool's own `registry_v1` function. PREPARE
calls it with `CaptureSigner`, which records the exact signing bytes and
returns a placeholder; no key is involved. Ed25519 is deterministic, so SIGN
with the same frozen arguments signs exactly those bytes.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping

from lilith_memory.owner_proof import OwnerProofError
from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import authority_verifier as AV
from lilith_owner_memory import burned_identities as BI
from lilith_owner_memory import pr1_bootstrap as B
from lilith_owner_memory import rotation_contracts as RC
from lilith_owner_memory import successor_custody as SC
from lilith_owner_memory.contracts import ContractViolation, _canonical

CONTINUITY = "OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_ATTEMPT_OFFHOST"
PROFILE = "DEV_SYNTHETIC"
ENVIRONMENT = "dev"
POLICY_VERSION = "policy.dev-synthetic.v1"
ROOT_KEY_ID = "test-only.registry-root.dev-synthetic.b1b3d.1"
E0_COUNTER = 1
REGISTRY_VERSION = 1
TERMINAL_STATE = "REGISTRY_SIGNED"
OWNER_TOOL = "services/authority-dev/ceremony/lilith_authority_owner_dev.py"
SIGNER_FORM = "registry-v1"
S25_KEY_PATH = "~/lilith-kroot-dev-synthetic/k-root.der"
S25_KACT_INPUT = "~/lilith-mb3/inputs/kact-publication.json"
MANIFEST_NAME = "mb3-inputs.json"
MANIFEST_TYPE = "LILITH_MB3_CANDIDATE_MANIFEST"
MANIFEST_SCHEMA_VERSION = 1
NON_AUTHORITY = ("evidence and input freezing only; not LILITH authority state; not authorization; "
                 "authorizes nothing")

_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


class Mb3Refusal(Exception):
    """A closed refusal code. Refusals never grant anything."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Mb3Refusal(code)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(bytes(data)).hexdigest()


def _b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    """RFC 8785 JCS plus one newline: the owner tool's stdout form."""
    return _canonical(value) + b"\n"


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def load_canonical(raw: bytes, code: str) -> dict[str, Any]:
    """One JSON object, no duplicate keys, byte-equal to `canonical_bytes`."""
    try:
        value = json.loads(bytes(raw).decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, ValueError, RecursionError, TypeError) as exc:
        raise Mb3Refusal(code + "_MALFORMED") from exc
    _require(isinstance(value, dict), code + "_MALFORMED")
    try:
        _require(canonical_bytes(value) == bytes(raw), code + "_NOT_CANONICAL")
    except ContractViolation as exc:
        raise Mb3Refusal(code + "_NOT_CANONICAL") from exc
    return value


# ------------------------------------------------------- accepted identities ---

@dataclass(frozen=True)
class AcceptedIdentitiesV1:
    """The accepted public identities M-B3 compares against. Public values only."""

    kroot_public_key_sha256: str
    kwit_public_key_sha256: str
    kwit_key_id: str
    kwit_blob_sha256: str
    kwit_publication_sha256: str
    kact_key_id: str
    kact_public_key_sha256: str
    kact_blob_sha256: str


# M-B1 completion (E-21), M-B2 completion §1/§5/§6, live-install preflight §24.
ACCEPTED = AcceptedIdentitiesV1(
    kroot_public_key_sha256="cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf",
    kwit_public_key_sha256="5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf",
    kwit_key_id="test-only.witness.dev-synthetic.b1b3d.1",
    kwit_blob_sha256="f87593701ee5e9272363a473a115b87cc06179df3c0b233af4aa62bb5b9b97be",
    kwit_publication_sha256="9e9dd0787b3d6df8d40730c6abab728cacbe5136269ca4421160da830bb23472",
    kact_key_id="test-only.dev-synthetic.actor.b1b3d.1",
    kact_public_key_sha256="dd13a1fb302375a4e7ec81131a72920e23e365e06a0b6dc9bb7ab124dadc01ed",
    kact_blob_sha256="6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3",
)


# ------------------------------------------------------ candidate parameters ---

def new_epoch_random(token_hex: Callable[[int], str] = secrets.token_hex) -> str:
    """Exactly one 16-byte random value, `secrets.token_hex(16)`, generated on the S25."""
    value = token_hex(16)
    _require(isinstance(value, str) and _HEX32.fullmatch(value) is not None, "EPOCH_RANDOM_INVALID")
    return value


def new_issued_at(now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> str:
    """One UTC RFC 3339 timestamp at second resolution, generated on the S25."""
    moment = now()
    _require(isinstance(moment, datetime) and moment.utcoffset() is not None
             and moment.utcoffset().total_seconds() == 0, "ISSUED_AT_NOT_UTC")
    value = moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _require(_INSTANT.fullmatch(value) is not None, "ISSUED_AT_INVALID")
    return value


# ------------------------------------------------------------- public inputs ---

def verify_root_anchor_bytes(raw: bytes, accepted: AcceptedIdentitiesV1 = ACCEPTED
                             ) -> tuple[dict[str, Any], A.TrustedRegistryRootV1]:
    """The S25 public copy written at M-B1: exactly the `root-keygen` output."""
    value = load_canonical(raw, "ROOT_ANCHOR")
    _require(set(value) == {"registryRoot", "publicKeySha256"}, "ROOT_ANCHOR_FIELDS")
    try:
        root = A.TrustedRegistryRootV1.from_dict(value["registryRoot"])
    except (OwnerProofError, ContractViolation, KeyError, TypeError) as exc:
        raise Mb3Refusal("ROOT_ANCHOR_INVALID") from exc
    recomputed = sha256_hex(root.public_key)
    _require(recomputed == value["publicKeySha256"], "ROOT_FINGERPRINT_FIELD_INVALID")
    _require(recomputed == accepted.kroot_public_key_sha256, "ROOT_FINGERPRINT_NOT_E21")
    _require(root.root_key_id == ROOT_KEY_ID and root.environment == ENVIRONMENT and root.test_only,
             "ROOT_ANCHOR_SCOPE")
    return value, root


def verify_kact_publication_bytes(raw: bytes, expected_file_sha256: str,
                                  accepted: AcceptedIdentitiesV1 = ACCEPTED) -> tuple[dict[str, Any], RC.KeyPublicationV1]:
    """The K-ACT L2b.2 publication from the fresh read-only DEV re-proof, pinned by its file SHA-256.

    The fingerprint is recomputed from `publicKey`; the `publicKeySha256` field
    is never trusted on its own.
    """
    _require(isinstance(expected_file_sha256, str) and _HEX64.fullmatch(expected_file_sha256) is not None,
             "KACT_PUBLICATION_PIN_INVALID")
    _require(sha256_hex(raw) == expected_file_sha256, "KACT_PUBLICATION_SHA256_MISMATCH")
    try:
        value, parsed = SC.parse_publication_bytes(raw)
    except (OwnerProofError, ContractViolation, KeyError, TypeError) as exc:
        raise Mb3Refusal("KACT_PUBLICATION_MALFORMED") from exc
    reason = SC.publication_profile_reason(value, parsed, profile=SC.DEV_SYNTHETIC_CUSTODY_PROFILE,
                                           key_id=accepted.kact_key_id, credential_path=SC.CURRENT_PATH)
    _require(reason is None, "KACT_" + str(reason))
    recomputed = sha256_hex(parsed.public_key)
    _require(recomputed == parsed.public_key_sha256, "KACT_FINGERPRINT_FIELD_INVALID")
    _require(recomputed == accepted.kact_public_key_sha256, "KACT_FINGERPRINT_NOT_ACCEPTED")
    _require(parsed.blob_sha256 == accepted.kact_blob_sha256, "KACT_BLOB_NOT_CURRENT")
    return value, parsed


def verify_kwit_publication_bytes(raw: bytes, accepted: AcceptedIdentitiesV1 = ACCEPTED
                                  ) -> tuple[dict[str, Any], B.WitnessKeyPublicationV1]:
    """The accepted M-B2 K-WIT publication. Used only to prove K-WIT distinctness."""
    _require(sha256_hex(raw) == accepted.kwit_publication_sha256, "KWIT_PUBLICATION_SHA256_MISMATCH")
    try:
        value = B.parse_publication_document(raw)
        parsed = B.WitnessKeyPublicationV1.from_dict(value)
    except (OwnerProofError, ContractViolation, KeyError, TypeError) as exc:
        raise Mb3Refusal("KWIT_PUBLICATION_MALFORMED") from exc
    _require(sha256_hex(parsed.public_key) == accepted.kwit_public_key_sha256, "KWIT_FINGERPRINT_NOT_ACCEPTED")
    _require(parsed.witness_key_id == accepted.kwit_key_id, "KWIT_KEY_ID_NOT_ACCEPTED")
    _require(parsed.blob_sha256 == accepted.kwit_blob_sha256, "KWIT_BLOB_NOT_ACCEPTED")
    _require(parsed.environment == ENVIRONMENT, "KWIT_ENVIRONMENT")
    return value, parsed


def witness_anchor(kwit: B.WitnessKeyPublicationV1) -> dict[str, Any]:
    return B.witness_anchor_document(kwit)


# ------------------------------------------------------------------ candidate ---

class CaptureSigner:
    """Stands in for K-ROOT in PREPARE: records the exact bytes, returns a placeholder.

    It holds no key and makes no signature. The placeholder never leaves
    `capture_candidate`.
    """

    def __init__(self) -> None:
        self.captured: bytes | None = None

    def sign(self, data: bytes) -> bytes:
        _require(self.captured is None, "CAPTURE_REPEATED")
        self.captured = bytes(data)
        return bytes(64)


@dataclass(frozen=True)
class CandidateV1:
    unsigned: Mapping[str, Any]
    signing_bytes: bytes
    registry_digest: str


def capture_candidate(registry_v1: Callable[..., dict[str, Any]], kact_publication: Mapping[str, Any], *,
                      epoch_random: str, policy_version: str, issued_at: str) -> CandidateV1:
    """Run the owner tool's own `registry_v1` with `CaptureSigner`: the exact bytes SIGN will sign."""
    capture = CaptureSigner()
    built = registry_v1(capture, dict(kact_publication), epoch_random=epoch_random,
                        policy_version=policy_version, issued_at=issued_at)
    _require(capture.captured is not None and isinstance(built, dict) and set(built) == A.REGISTRY_FIELDS,
             "CAPTURE_FAILED")
    unsigned = {name: built[name] for name in A.REGISTRY_SIGNED_FIELDS}
    signing = A.registry_signing_bytes(unsigned)
    _require(signing == capture.captured, "CAPTURE_MISMATCH")
    digest = sha256_hex(signing)
    _require(RC.registry_digest(built) == digest, "CAPTURE_DIGEST_MISMATCH")
    return CandidateV1(unsigned, signing, digest)


def expected_kact_record(kact: RC.KeyPublicationV1, *, epoch_random: str, policy_version: str,
                         issued_at: str) -> dict[str, Any]:
    """The one K-ACT key record registry v1 must hold, derived from the accepted publication."""
    return {"schemaVersion": 1, "keyId": kact.key_id, "signingDomain": A.OWNER_ACTOR,
            "evidenceTypes": sorted(kact.evidence_types), "environment": ENVIRONMENT, "algorithm": A.ALGORITHM,
            "publicKey": _b64u(kact.public_key), "createdAt": issued_at, "notBefore": issued_at,
            "retiredAt": None, "revokedAt": None, "revocationReason": None, "compromisedSince": None,
            "recoveryEpoch": {"counter": E0_COUNTER, "random": epoch_random}, "policyVersion": policy_version,
            "registryVersion": REGISTRY_VERSION}


def kact_record_reason(registry: Mapping[str, Any], kact: RC.KeyPublicationV1, *, epoch_random: str,
                       policy_version: str, issued_at: str) -> str | None:
    """None when registry v1 holds exactly one key record, equal to the accepted K-ACT publication."""
    keys = registry.get("keys")
    if not isinstance(keys, list) or len(keys) != 1:
        return "REGISTRY_KEY_COUNT"
    expected = expected_kact_record(kact, epoch_random=epoch_random, policy_version=policy_version,
                                    issued_at=issued_at)
    if _canonical(keys[0]) != _canonical(expected):
        return "KACT_RECORD_NOT_PUBLICATION"
    return None


def _shape_reason(registry: Mapping[str, Any], *, epoch_random: str, policy_version: str, issued_at: str) -> str | None:
    expected = {"protocol": A.REGISTRY_PROTOCOL, "schemaVersion": A.REGISTRY_SCHEMA_VERSION,
                "environment": ENVIRONMENT, "registryVersion": REGISTRY_VERSION,
                "recoveryEpoch": {"counter": E0_COUNTER, "random": epoch_random}, "policyVersion": policy_version,
                "registryRootKeyId": ROOT_KEY_ID, "issuedAt": issued_at}
    if set(registry) - {"signature", "keys"} != set(expected):
        return "REGISTRY_FIELDS"
    for name, value in expected.items():
        if _canonical({"v": registry[name]}) != _canonical({"v": value}):
            return "REGISTRY_FIELD_" + name
    return None


def _structure_tokens(registry: Mapping[str, Any], digest: str, *, root: A.TrustedRegistryRootV1,
                      kact_value: Mapping[str, Any], kact: RC.KeyPublicationV1, kwit_value: Mapping[str, Any],
                      kwit: B.WitnessKeyPublicationV1, epoch_random: str, policy_version: str, issued_at: str,
                      real_registry_burns: Iterable[Mapping[str, Any]]) -> list[str]:
    """Checks shared by PREPARE (placeholder signature) and verification (real signature).

    `from_verified_dict` is parse-only here: it never verifies a signature.
    """
    tokens: list[str] = []
    _require(policy_version == POLICY_VERSION, "POLICY_VERSION_NOT_ACCEPTED")
    _require(_HEX32.fullmatch(epoch_random) is not None, "EPOCH_RANDOM_INVALID")
    _require(_INSTANT.fullmatch(issued_at) is not None, "ISSUED_AT_INVALID")
    reason = _shape_reason(registry, epoch_random=epoch_random, policy_version=policy_version, issued_at=issued_at)
    _require(reason is None, str(reason))
    tokens.append("REGISTRY_FIELDS_EXACT")
    try:
        parsed = A.AuthorityRegistryV1.from_verified_dict(registry)
    except (OwnerProofError, ContractViolation, KeyError, TypeError) as exc:
        raise Mb3Refusal("REGISTRY_SCHEMA_INVALID") from exc
    tokens.append("REGISTRY_SCHEMA_VALID")
    _require(RC.single_current_key_reason(parsed) is None, "MULTIPLE_CURRENT_ISSUANCE_KEYS")
    current = [record.key_id for record in parsed.keys.values() if record.current]
    _require(current == [kact.key_id], "KACT_NOT_SINGLE_CURRENT")
    tokens.append("SINGLE_CURRENT_KACT")
    reason = kact_record_reason(registry, kact, epoch_random=epoch_random, policy_version=policy_version,
                                issued_at=issued_at)
    _require(reason is None, str(reason))
    tokens.append("KACT_RECORD_EQUALS_PUBLICATION")
    _require(sha256_hex(kact.public_key) == kact.public_key_sha256, "KACT_FINGERPRINT_FIELD_INVALID")
    tokens.append("KACT_FINGERPRINT_RECOMPUTED")
    _require(kwit.witness_key_id not in parsed.keys
             and all(record.public_key != kwit.public_key for record in parsed.keys.values()), "KWIT_IN_REGISTRY")
    tokens.append("KWIT_NOT_IN_REGISTRY")
    reason = B.witness_distinctness_reason(witness_publication=kwit_value, actor_publication=kact_value,
                                           registry=registry, registry_root=root, anchor=witness_anchor(kwit))
    _require(reason is None, "KWIT_" + str(reason))
    _require(root.public_key not in (kact.public_key, kwit.public_key), "KROOT_NOT_DISTINCT")
    tokens.append("KWIT_KACT_KROOT_DISTINCT")
    every = BI.BURNED_PUBLIC_KEY_SHA256 | BI.BURNED_REGISTRY_DIGESTS | BI.BURNED_GENESIS_WITNESS_DIGESTS
    _require(len(every) == BI.CANONICAL_COUNT, "BURNED_SET_NOT_CANONICAL")
    burned = BI.burned_identity(public_keys=(root.public_key, kact.public_key, kwit.public_key),
                                registry_digests=(digest,))
    _require(burned is None, "BURNED_IDENTITY")
    tokens.append("NOT_A_BURNED_IDENTITY")
    _require(digest not in known_burned_registry_digests(real_registry_burns), "KNOWN_REAL_REGISTRY_BURN")
    tokens.append("NOT_A_KNOWN_REAL_REGISTRY_BURN")
    return tokens


def presign_tokens(candidate: CandidateV1, *, root: A.TrustedRegistryRootV1, kact_value: Mapping[str, Any],
                   kact: RC.KeyPublicationV1, kwit_value: Mapping[str, Any], kwit: B.WitnessKeyPublicationV1,
                   epoch_random: str, policy_version: str, issued_at: str,
                   real_registry_burns: Iterable[Mapping[str, Any]] = ()) -> list[str]:
    """PREPARE checks before any K-ROOT use, on the unsigned candidate."""
    placeholder = {**candidate.unsigned, "signature": _b64u(bytes(64))}
    tokens = _structure_tokens(placeholder, candidate.registry_digest, root=root, kact_value=kact_value, kact=kact,
                               kwit_value=kwit_value, kwit=kwit, epoch_random=epoch_random,
                               policy_version=policy_version, issued_at=issued_at,
                               real_registry_burns=real_registry_burns)
    _require(sha256_hex(candidate.signing_bytes) == candidate.registry_digest, "DIGEST_NOT_OVER_SIGNING_BYTES")
    tokens.append("EXPECTED_DIGEST_FROZEN_BEFORE_SIGNING")
    return tokens


# ------------------------------------------------------------------- manifest ---

MANIFEST_FIELDS = frozenset({
    "manifestType", "schemaVersion", "continuity", "profile", "environment", "authoritative", "authorizes",
    "nonAuthority", "controlSha", "bundleSha256", "sourceCommit", "scriptSha256", "krootPublicKeySha256",
    "registryRootKeyId", "rootAnchorSha256", "kactPublicationSha256", "kactPublicKeySha256", "kactKeyId",
    "kactBlobSha256", "kwitPublicKeySha256", "kwitKeyId", "kwitBlobSha256", "kwitPublicationSha256",
    "witnessAnchorSha256", "policyVersion", "epochRandom", "issuedAt", "recoveryEpoch", "registryVersion",
    "expectedRegistryDigest", "unsignedRegistrySha256", "signerCommand", "inputFiles", "terminalStateOnSuccess",
    "presignTokens",
})
INPUT_FILES = ("kact-publication.json", "kwit-publication.json", "root-anchor.json", "witness-anchor.json")


def signer_command(*, epoch_random: str, policy_version: str, issued_at: str) -> dict[str, Any]:
    """The exact signer semantics a go names. The passphrase is never part of it."""
    return {"tool": OWNER_TOOL, "form": SIGNER_FORM,
            "argv": [SIGNER_FORM, S25_KEY_PATH, S25_KACT_INPUT, epoch_random, policy_version, issued_at],
            "keyPath": S25_KEY_PATH, "invocations": 1, "automaticRetry": False,
            "passphrase": "typed only into getpass on the local S25 Termux TTY; never stored or passed"}


def build_manifest(*, control_sha: str, bundle_sha256: str, source_commit: str, script_sha256: str,
                   accepted: AcceptedIdentitiesV1, root_anchor_sha256: str, kact_publication_sha256: str,
                   kact: RC.KeyPublicationV1, kwit_publication_sha256: str, witness_anchor_sha256: str,
                   epoch_random: str, issued_at: str, candidate: CandidateV1, input_files: Mapping[str, str],
                   presign: Iterable[str]) -> dict[str, Any]:
    manifest = {
        "manifestType": MANIFEST_TYPE, "schemaVersion": MANIFEST_SCHEMA_VERSION, "continuity": CONTINUITY,
        "profile": PROFILE, "environment": ENVIRONMENT, "authoritative": False, "authorizes": "NOTHING",
        "nonAuthority": NON_AUTHORITY, "controlSha": control_sha, "bundleSha256": bundle_sha256,
        "sourceCommit": source_commit, "scriptSha256": script_sha256,
        "krootPublicKeySha256": accepted.kroot_public_key_sha256, "registryRootKeyId": ROOT_KEY_ID,
        "rootAnchorSha256": root_anchor_sha256, "kactPublicationSha256": kact_publication_sha256,
        "kactPublicKeySha256": sha256_hex(kact.public_key), "kactKeyId": kact.key_id,
        "kactBlobSha256": kact.blob_sha256, "kwitPublicKeySha256": accepted.kwit_public_key_sha256,
        "kwitKeyId": accepted.kwit_key_id, "kwitBlobSha256": accepted.kwit_blob_sha256,
        "kwitPublicationSha256": kwit_publication_sha256, "witnessAnchorSha256": witness_anchor_sha256,
        "policyVersion": POLICY_VERSION, "epochRandom": epoch_random, "issuedAt": issued_at,
        "recoveryEpoch": {"counter": E0_COUNTER, "random": epoch_random}, "registryVersion": REGISTRY_VERSION,
        "expectedRegistryDigest": candidate.registry_digest,
        "unsignedRegistrySha256": sha256_hex(canonical_bytes(candidate.unsigned)),
        "signerCommand": signer_command(epoch_random=epoch_random, policy_version=POLICY_VERSION,
                                        issued_at=issued_at),
        "inputFiles": dict(sorted(input_files.items())), "terminalStateOnSuccess": TERMINAL_STATE,
        "presignTokens": list(presign),
    }
    parse_manifest(canonical_bytes(manifest), accepted)
    return manifest


def parse_manifest(raw: bytes, accepted: AcceptedIdentitiesV1 = ACCEPTED) -> dict[str, Any]:
    """Strict: canonical bytes, exact fields, fixed values, and no authority claim."""
    m = load_canonical(raw, "MANIFEST")
    _require(set(m) == MANIFEST_FIELDS, "MANIFEST_FIELDS")
    fixed = {"manifestType": MANIFEST_TYPE, "schemaVersion": MANIFEST_SCHEMA_VERSION, "continuity": CONTINUITY,
             "profile": PROFILE, "environment": ENVIRONMENT, "authorizes": "NOTHING", "nonAuthority": NON_AUTHORITY,
             "krootPublicKeySha256": accepted.kroot_public_key_sha256, "registryRootKeyId": ROOT_KEY_ID,
             "kactPublicKeySha256": accepted.kact_public_key_sha256, "kactKeyId": accepted.kact_key_id,
             "kactBlobSha256": accepted.kact_blob_sha256, "kwitPublicKeySha256": accepted.kwit_public_key_sha256,
             "kwitKeyId": accepted.kwit_key_id, "kwitBlobSha256": accepted.kwit_blob_sha256,
             "kwitPublicationSha256": accepted.kwit_publication_sha256, "policyVersion": POLICY_VERSION,
             "registryVersion": REGISTRY_VERSION, "terminalStateOnSuccess": TERMINAL_STATE}
    for name, value in fixed.items():
        _require(m[name] == value and type(m[name]) is type(value), "MANIFEST_" + name)
    _require(m["authoritative"] is False, "MANIFEST_CLAIMS_AUTHORITY")
    for name in ("controlSha", "sourceCommit"):
        _require(isinstance(m[name], str) and _SHA40.fullmatch(m[name]) is not None, "MANIFEST_" + name)
    _require(m["controlSha"] == m["sourceCommit"], "MANIFEST_SOURCE_NOT_CONTROL")
    for name in ("bundleSha256", "scriptSha256", "rootAnchorSha256", "kactPublicationSha256", "witnessAnchorSha256",
                 "expectedRegistryDigest", "unsignedRegistrySha256"):
        _require(isinstance(m[name], str) and _HEX64.fullmatch(m[name]) is not None, "MANIFEST_" + name)
    _require(isinstance(m["epochRandom"], str) and _HEX32.fullmatch(m["epochRandom"]) is not None,
             "MANIFEST_epochRandom")
    _require(isinstance(m["issuedAt"], str) and _INSTANT.fullmatch(m["issuedAt"]) is not None, "MANIFEST_issuedAt")
    _require(m["recoveryEpoch"] == {"counter": E0_COUNTER, "random": m["epochRandom"]}, "MANIFEST_recoveryEpoch")
    _require(m["signerCommand"] == signer_command(epoch_random=m["epochRandom"], policy_version=POLICY_VERSION,
                                                  issued_at=m["issuedAt"]), "MANIFEST_signerCommand")
    files = m["inputFiles"]
    _require(isinstance(files, dict) and tuple(sorted(files)) == tuple(sorted(INPUT_FILES))
             and all(isinstance(v, str) and _HEX64.fullmatch(v) for v in files.values()), "MANIFEST_inputFiles")
    _require(files["kact-publication.json"] == m["kactPublicationSha256"]
             and files["kwit-publication.json"] == m["kwitPublicationSha256"]
             and files["root-anchor.json"] == m["rootAnchorSha256"]
             and files["witness-anchor.json"] == m["witnessAnchorSha256"], "MANIFEST_inputFiles")
    _require(isinstance(m["presignTokens"], list) and all(isinstance(t, str) for t in m["presignTokens"]),
             "MANIFEST_presignTokens")
    return m


# --------------------------------------------------------------- verification ---

@dataclass(frozen=True)
class VerificationV1:
    verified: bool
    reason: str | None
    tokens: tuple[str, ...]
    registry_digest: str | None = None


def verify_signed_registry(*, registry_raw: bytes, manifest_raw: bytes, root_anchor_raw: bytes, kact_raw: bytes,
                           kwit_raw: bytes, accepted: AcceptedIdentitiesV1 = ACCEPTED,
                           real_registry_burns: Iterable[Mapping[str, Any]] = (),
                           registry_v1: Callable[..., dict[str, Any]] | None = None) -> VerificationV1:
    """The accepted M-B3 verification, run on the S25 before export and on the laptop after it.

    Public bytes only. A pass is technical evidence for `REGISTRY_SIGNED`; it
    is not owner acceptance and authorizes nothing.
    """
    tokens: list[str] = []
    digest: str | None = None
    try:
        m = parse_manifest(manifest_raw, accepted)
        tokens.append("MANIFEST_VALID_NON_AUTHORITATIVE")
        _require(sha256_hex(root_anchor_raw) == m["rootAnchorSha256"], "ROOT_ANCHOR_NOT_MANIFEST")
        _, root = verify_root_anchor_bytes(root_anchor_raw, accepted)
        tokens.append("ROOT_FINGERPRINT_E21")
        kact_value, kact = verify_kact_publication_bytes(kact_raw, m["kactPublicationSha256"], accepted)
        tokens.append("KACT_PUBLICATION_PINNED_AND_RECOMPUTED")
        kwit_value, kwit = verify_kwit_publication_bytes(kwit_raw, accepted)
        _require(sha256_hex(canonical_bytes(witness_anchor(kwit))) == m["witnessAnchorSha256"],
                 "WITNESS_ANCHOR_NOT_MANIFEST")
        tokens.append("KWIT_PUBLICATION_ACCEPTED")
        registry = load_canonical(registry_raw, "REGISTRY")
        tokens.append("REGISTRY_BYTES_CANONICAL")
        _require(set(registry) == A.REGISTRY_FIELDS, "REGISTRY_FIELDS")
        unsigned = {name: registry[name] for name in A.REGISTRY_SIGNED_FIELDS}
        signing = A.registry_signing_bytes(unsigned)
        digest = sha256_hex(signing)
        _require(RC.registry_digest(registry) == digest, "REGISTRY_DIGEST_FUNCTION_MISMATCH")
        _require(digest == m["expectedRegistryDigest"], "REGISTRY_DIGEST_NOT_EXPECTED")
        _require(sha256_hex(canonical_bytes(unsigned)) == m["unsignedRegistrySha256"], "UNSIGNED_NOT_EXPECTED")
        tokens.append("SIGNING_BYTES_AND_DIGEST_EXPECTED")
        context = A.AuthorityVerificationContextV1(
            environment=ENVIRONMENT, purpose=A.NEW_ADMISSION, registry_root=root, trusted_minimum_registry_version=1,
            expected_recovery_epoch=A.RecoveryEpochV1(E0_COUNTER, m["epochRandom"]), policy_version=POLICY_VERSION)
        result = AV.verify_authority_registry(context=context, registry=registry)
        _require(result.verified, "KROOT_SIGNATURE_" + str(result.reason))
        tokens.append("KROOT_SIGNATURE_VERIFIED")
        tokens += _structure_tokens(registry, digest, root=root, kact_value=kact_value, kact=kact,
                                    kwit_value=kwit_value, kwit=kwit, epoch_random=m["epochRandom"],
                                    policy_version=m["policyVersion"], issued_at=m["issuedAt"],
                                    real_registry_burns=real_registry_burns)
        if registry_v1 is not None:
            rebuilt = capture_candidate(registry_v1, kact_value, epoch_random=m["epochRandom"],
                                        policy_version=m["policyVersion"], issued_at=m["issuedAt"])
            _require(rebuilt.signing_bytes == signing, "OWNER_TOOL_RECONSTRUCTION_DIFFERS")
            tokens.append("OWNER_TOOL_RECONSTRUCTION_EQUAL")
    except Mb3Refusal as refusal:
        return VerificationV1(False, refusal.code, tuple(tokens), digest)
    except (OwnerProofError, ContractViolation, KeyError, TypeError, ValueError) as exc:
        return VerificationV1(False, "VERIFICATION_INPUT_MALFORMED:" + type(exc).__name__, tuple(tokens), digest)
    return VerificationV1(True, None, tuple(tokens), digest)


# ------------------------------------------------------- SIGN outcome classes ---

OUTCOME_A = "A_NO_SIGNATURE"                      # go consumed; no burn
OUTCOME_B = "B_SIGNED_PENDING_OWNER_ACCEPTANCE"   # technical REGISTRY_SIGNED after verification
OUTCOME_C = "C_SIGNED_INVALID_BURN"               # burn the known signed digest
OUTCOME_D = "D_SIGNATURE_UNCERTAIN_BURN_FROZEN"   # burn the pre-sign frozen digest
OUTCOME_E = "E_UNKNOWN_REAL_REGISTRY_BURN"        # tombstone; never an invented digest
_REFUSED_LINE = re.compile(rb"lilith_authority_owner_dev: REFUSED [^\n]*\n\Z")


def classify_signer_exit(*, exit_code: int | None, stdout: bytes, stderr: bytes) -> str:
    """Before verification. Grounded in the owner tool's `main`:

    every exception inside its `try` (key load, wrong passphrase, input checks,
    the signature itself) prints exactly one `REFUSED` line, exits 2 and writes
    nothing to stdout; no signature escapes. The stdout write is outside that
    `try`, so a failure after signing is never a `REFUSED` exit 2. Anything else
    (a signal, a traceback, partial output) is uncertain and handled as D.
    """
    if exit_code == 0 and stdout:
        return OUTCOME_B
    if exit_code == 2 and stdout == b"" and _REFUSED_LINE.fullmatch(stderr or b""):
        return OUTCOME_A
    return OUTCOME_D


# ------------------------------------------------------------- burn records ---

KNOWN_BURN_TYPE = "LILITH_REAL_REGISTRY_V1_BURN"
UNKNOWN_BURN_TYPE = "UNKNOWN_REAL_REGISTRY_BURN"
BURN_SCHEMA_VERSION = 1
KNOWN_BURN_CASES = ("C_VERIFICATION_FAILED", "C_OWNER_REJECTED", "C_OTHERWISE_INVALID", "D_OUTPUT_LOST_OR_UNCERTAIN")
DIGEST_SOURCES = ("SIGNED_OUTPUT", "PRE_SIGN_FROZEN_MANIFEST")
KNOWN_BURN_FIELDS = frozenset({"burnType", "schemaVersion", "profile", "environment", "registryVersion",
                               "registryDigest", "digestSource", "case", "controlSha", "manifestSha256",
                               "recordedAt", "status", "neverInstall", "neverResign"})
UNKNOWN_BURN_FIELDS = frozenset({"burnType", "schemaVersion", "profile", "environment", "registryVersion",
                                 "registryDigest", "failureWindow", "controlSha", "manifestSha256", "provenance",
                                 "recordedAt", "status", "neverInstall", "neverResign"})
BURN_STATUS = "PERMANENTLY_BURNED"


def known_real_registry_burn(*, registry_digest: str, digest_source: str, case: str, control_sha: str,
                             manifest_sha256: str, recorded_at: str) -> dict[str, Any]:
    entry = {"burnType": KNOWN_BURN_TYPE, "schemaVersion": BURN_SCHEMA_VERSION, "profile": PROFILE,
             "environment": ENVIRONMENT, "registryVersion": REGISTRY_VERSION, "registryDigest": registry_digest,
             "digestSource": digest_source, "case": case, "controlSha": control_sha,
             "manifestSha256": manifest_sha256, "recordedAt": recorded_at, "status": BURN_STATUS,
             "neverInstall": True, "neverResign": True}
    validate_burn_entry(entry)
    return entry


def unknown_real_registry_burn(*, failure_window: str, control_sha: str, manifest_sha256: str | None,
                               provenance: str, recorded_at: str) -> dict[str, Any]:
    """Only when a real signed candidate existed and its identity cannot be recovered. Never a digest."""
    entry = {"burnType": UNKNOWN_BURN_TYPE, "schemaVersion": BURN_SCHEMA_VERSION, "profile": PROFILE,
             "environment": ENVIRONMENT, "registryVersion": REGISTRY_VERSION, "registryDigest": "UNKNOWN",
             "failureWindow": failure_window, "controlSha": control_sha, "manifestSha256": manifest_sha256,
             "provenance": provenance, "recordedAt": recorded_at, "status": BURN_STATUS, "neverInstall": True,
             "neverResign": True}
    validate_burn_entry(entry)
    return entry


def validate_burn_entry(entry: Any) -> None:
    _require(isinstance(entry, Mapping), "BURN_ENTRY_MALFORMED")
    kind = entry.get("burnType")
    _require(kind in (KNOWN_BURN_TYPE, UNKNOWN_BURN_TYPE), "BURN_TYPE")
    _require(set(entry) == (KNOWN_BURN_FIELDS if kind == KNOWN_BURN_TYPE else UNKNOWN_BURN_FIELDS), "BURN_FIELDS")
    _require(entry["schemaVersion"] == BURN_SCHEMA_VERSION and entry["profile"] == PROFILE
             and entry["environment"] == ENVIRONMENT and entry["registryVersion"] == REGISTRY_VERSION,
             "BURN_SCOPE")
    _require(entry["status"] == BURN_STATUS and entry["neverInstall"] is True and entry["neverResign"] is True,
             "BURN_STATUS")
    _require(isinstance(entry["controlSha"], str) and _SHA40.fullmatch(entry["controlSha"]) is not None,
             "BURN_CONTROL_SHA")
    _require(isinstance(entry["recordedAt"], str) and _INSTANT.fullmatch(entry["recordedAt"]) is not None,
             "BURN_RECORDED_AT")
    if kind == KNOWN_BURN_TYPE:
        _require(isinstance(entry["registryDigest"], str) and _HEX64.fullmatch(entry["registryDigest"]) is not None,
                 "BURN_DIGEST")
        _require(entry["digestSource"] in DIGEST_SOURCES and entry["case"] in KNOWN_BURN_CASES, "BURN_CASE")
        _require(isinstance(entry["manifestSha256"], str) and _HEX64.fullmatch(entry["manifestSha256"]) is not None,
                 "BURN_MANIFEST")
    else:
        _require(entry["registryDigest"] == "UNKNOWN", "TOMBSTONE_INVENTS_DIGEST")
        _require(entry["manifestSha256"] is None
                 or (isinstance(entry["manifestSha256"], str) and _HEX64.fullmatch(entry["manifestSha256"])),
                 "BURN_MANIFEST")
        _require(isinstance(entry["failureWindow"], str) and entry["failureWindow"]
                 and isinstance(entry["provenance"], str) and entry["provenance"], "TOMBSTONE_PROVENANCE")


def append_burn(register: Iterable[Mapping[str, Any]], entry: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Append-only: the old entries are kept exactly, in order; a known digest is never recorded twice."""
    old = [dict(e) for e in register]
    for existing in old:
        validate_burn_entry(existing)
    validate_burn_entry(entry)
    if entry["burnType"] == KNOWN_BURN_TYPE:
        _require(entry["registryDigest"] not in known_burned_registry_digests(old), "BURN_DUPLICATE")
    return old + [dict(entry)]


def register_extends(old: Iterable[Mapping[str, Any]], new: Iterable[Mapping[str, Any]]) -> bool:
    """True only when `new` is `old` with entries appended (no edit, removal, or reorder)."""
    old_list, new_list = [_canonical(dict(e)) for e in old], [_canonical(dict(e)) for e in new]
    return len(new_list) >= len(old_list) and new_list[:len(old_list)] == old_list


def known_burned_registry_digests(register: Iterable[Mapping[str, Any]]) -> frozenset[str]:
    digests = set()
    for entry in register:
        validate_burn_entry(entry)
        if entry["burnType"] == KNOWN_BURN_TYPE:
            digests.add(entry["registryDigest"])
    return frozenset(digests)
