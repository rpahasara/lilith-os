"""15B2b-B1b-3e Source Prep B: successor custody contracts (SW-1, SW-2; TEST-ONLY, pure).

Design: docs/architecture/slice-15b2b-b1b3e-source-prep-b-design.md.
Record: docs/architecture/slice-15b2b-b1b3e-source-prep-b-successor-custody.md.

Pure parsers and verifiers over caller-supplied bytes and observations.
Nothing here reads a file, the environment, a network, or a credential,
holds a private key, or signs. Every result reports `authorityGranted: false`.

The pieces, and what each one is NOT:

- successor identity (RR-11-D1): `successor <N>` derives exactly one keyId
  and one ceremonyId from the ordinal N. `keyId` alone is not authority; the
  K-ROOT registry record is.
- `SuccessorCeremonyRecordV1` (RR-27): non-authority provenance binding
  ceremony, ordinal, keyId, the exact publication bytes, the blob, and the
  reviewed release. Not registry authority, not K-ROOT authorization, not
  witness freshness; it cannot make a key current or release a hold.
- `SuccessorCeremonyRegisterV1`: the burned-ordinal model (anti-reuse). It
  prevents unsafe source/custody reuse; registry history stays the authority
  owner of key identity. Not a cryptographic root.
- custody observation, states, and transitions (RR-26, SW-1): CURRENT /
  PREPARED / RETIRED facts, same-filesystem proof, forward-only renames.
  `filesystem path != authority`; `slot role != authority`;
  `same-filesystem proof != authority`.
- `CeremonyHoldV1` (RR-24, RR-30): HELD / RELEASED gating container.
  `hold != authority`; `hold release != authority`; `missing hold != released`.
- predecessor destruction evidence (RR-29, §13): logical unlink facts only.
  `logical destruction != media zeroization`; `destruction != revocation`.

Every check that needs authority (who is current at the witnessed head, the
compromise-epoch rule, S_CURRENT) lives in `successor_readiness`.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping

from lilith_memory.owner_proof import OwnerProofError, _digest, _exact, _id

from . import authority_contracts as A
from . import rotation_contracts as RC
from . import witness_readiness as WR
from .contracts import _RELEASE, DEPLOYMENT_ENVIRONMENTS, ContractViolation, _choice


class _Reject(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _require(condition: bool, reason: str, detail: str | None = None) -> None:
    if not condition:
        raise _Reject(reason, detail)


# ------------------------------------------------------------- profile ---

PROFILE = "DEV_SYNTHETIC"
ENVIRONMENT = "dev"
# The initial B1b-3d K-ACT (authority-dev `profile.PROPOSED_K_ACT_KEY_ID`).
INITIAL_KEY_ID = "test-only.dev-synthetic.actor.b1b3d.1"
SUCCESSOR_KEY_ID_PREFIX = "test-only.dev-synthetic.actor.b1b3e."
SUCCESSOR_CEREMONY_ID_PREFIX = "dev-synthetic.owner-actor.successor."
CUSTODY_DEBT_SUFFIX = ".custody-debt"
# SOURCE DETAIL: four decimal digits (design §5 C). 2 .. 9999.
SUCCESSOR_ORDINAL_MIN = 2
SUCCESSOR_ORDINAL_MAX = 9999
_ORDINAL_TEXT = re.compile(r"[1-9][0-9]{0,3}\Z")

CREDENTIAL_NAME = "owner-actor-signing-key"
SLOT_NAME = "lilith-authority-dev.owner-actor.cred"
CREDSTORE_DIR = "/etc/credstore.encrypted"
CURRENT_PATH = CREDSTORE_DIR + "/" + SLOT_NAME
CUSTODY_ROOT = "/etc/lilith-authority-custody"
PREPARED_DIR = CUSTODY_ROOT + "/prepared"
RETIRED_DIR = CUSTODY_ROOT + "/retired"
PREPARED_PATH = PREPARED_DIR + "/" + SLOT_NAME
RETIRED_PATH = RETIRED_DIR + "/" + SLOT_NAME
CUSTODY_ROOT_NAMES = ("prepared", "retired")

KEY_PUBLICATION_PROFILE = "DEV_SYNTHETIC"
KEY_PUBLICATION_WITH_KEY = "host"


@dataclass(frozen=True)
class CustodyProfileV1:
    """The fixed DEV_SYNTHETIC custody profile. Logical contract, never authority.

    Five identifiers are kept apart and are never aliases (RR-11-D2):
    `credential_name` (the one systemd runtime name), keyIds, ceremonyIds,
    slot roles, and filesystem paths.
    """

    profile: str
    environment: str
    initial_key_id: str
    credential_name: str
    current_path: str
    prepared_path: str
    retired_path: str
    signing_domain: str = A.OWNER_ACTOR
    evidence_type: str = A.OWNER_MEMORY_OPERATION


DEV_SYNTHETIC_CUSTODY_PROFILE = CustodyProfileV1(
    profile=PROFILE, environment=ENVIRONMENT, initial_key_id=INITIAL_KEY_ID, credential_name=CREDENTIAL_NAME,
    current_path=CURRENT_PATH, prepared_path=PREPARED_PATH, retired_path=RETIRED_PATH)


# `test` is admitted only as the TEST-only stand-in environment of every
# B1b-3e synthetic writer (the TEST witness writers refuse any other). Every
# other profile value must equal DEV_SYNTHETIC exactly; `prod` never passes.
_DEV_SYNTHETIC_ENVIRONMENTS = frozenset({ENVIRONMENT, "test"})


def is_dev_synthetic(profile: Any) -> bool:
    return (isinstance(profile, CustodyProfileV1) and profile.environment in _DEV_SYNTHETIC_ENVIRONMENTS
            and dataclasses.replace(profile, environment=ENVIRONMENT) == DEV_SYNTHETIC_CUSTODY_PROFILE)


def require_dev_synthetic(profile: Any) -> CustodyProfileV1:
    """The only accepted profile. PROD and any other value are refused."""
    if not is_dev_synthetic(profile):
        raise ContractViolation("PROFILE_NOT_DEV_SYNTHETIC")
    return profile


# --------------------------------------------------- successor identity ---

@dataclass(frozen=True)
class SuccessorIdentityV1:
    """What one ordinal N derives. Burned forever once used (RR-11-D1)."""

    ordinal: int
    key_id: str
    ceremony_id: str


def _checked_ordinal(value: Any) -> int:
    if type(value) is not int or not SUCCESSOR_ORDINAL_MIN <= value <= SUCCESSOR_ORDINAL_MAX:
        raise ContractViolation("SUCCESSOR_ORDINAL_OUT_OF_RANGE")
    return value


def successor_identity(ordinal: int) -> SuccessorIdentityV1:
    n = _checked_ordinal(ordinal)
    return SuccessorIdentityV1(n, SUCCESSOR_KEY_ID_PREFIX + str(n), SUCCESSOR_CEREMONY_ID_PREFIX + str(n))


def _suffix_ordinal(value: Any, prefix: str) -> int | None:
    if not isinstance(value, str) or not value.startswith(prefix):
        return None
    text = value[len(prefix):]
    if not text.isascii() or _ORDINAL_TEXT.fullmatch(text) is None:
        return None
    number = int(text)
    return number if SUCCESSOR_ORDINAL_MIN <= number <= SUCCESSOR_ORDINAL_MAX else None


def successor_ordinal_of_key_id(key_id: Any) -> int | None:
    return _suffix_ordinal(key_id, SUCCESSOR_KEY_ID_PREFIX)


def successor_ordinal_of_ceremony_id(ceremony_id: Any) -> int | None:
    return _suffix_ordinal(ceremony_id, SUCCESSOR_CEREMONY_ID_PREFIX)


def initial_ceremony_id(environment: str, initial_key_id: str) -> str:
    """RR-30: the one INITIAL_CUSTODY ceremony ID, from fixed context only.

    SOURCE DETAIL encoding: `<environment>.initial-custody.<initialKeyId>`.
    No operator text, timestamp, or random name enters it.
    """
    _choice(environment, DEPLOYMENT_ENVIRONMENTS, "environment")
    return _id(f"{environment}.initial-custody.{_id(initial_key_id, 'initial_key_id')}", "ceremony_id")


def custody_debt_ceremony_id(ceremony_id: str) -> str:
    """The availability-hold ceremony after a destruction failure (§4.1, §13).

    A released ceremony can never be HELD again (RELEASED -> HELD is refused),
    so the availability hold engaged after `S_CURRENT` is a new, deterministic
    ceremony derived only from the successor ceremony. SOURCE DETAIL.
    """
    if successor_ordinal_of_ceremony_id(ceremony_id) is None:
        raise ContractViolation("CUSTODY_DEBT_NEEDS_SUCCESSOR_CEREMONY")
    return ceremony_id + CUSTODY_DEBT_SUFFIX


def primary_ceremony_id(ceremony_id: str) -> str:
    return ceremony_id[:-len(CUSTODY_DEBT_SUFFIX)] if ceremony_id.endswith(CUSTODY_DEBT_SUFFIX) else ceremony_id


# ------------------------------------------------------------ publication ---

def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def canonical_publication_bytes(value: Mapping[str, Any]) -> bytes:
    """The keygen's exact stdout form: sorted keys, no whitespace, ASCII, one newline."""
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def publication_digest(raw: bytes) -> str:
    """SHA-256 of the exact canonical publication bytes (RR-27 `publicationDigest`)."""
    if not isinstance(raw, (bytes, bytearray)):
        raise ContractViolation("PUBLICATION_MALFORMED")
    return hashlib.sha256(bytes(raw)).hexdigest()


def parse_publication_bytes(raw: Any) -> tuple[dict[str, Any], RC.KeyPublicationV1]:
    """Strict: one JSON object, no duplicate keys, exactly the canonical bytes,
    and a valid unchanged v1 key publication."""
    if not isinstance(raw, (bytes, bytearray)) or not raw:
        raise ContractViolation("PUBLICATION_MALFORMED")
    try:
        value = json.loads(bytes(raw).decode("ascii"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ContractViolation("PUBLICATION_MALFORMED") from exc
    if not isinstance(value, dict) or canonical_publication_bytes(value) != bytes(raw):
        raise ContractViolation("PUBLICATION_NOT_CANONICAL")
    return value, RC.KeyPublicationV1.from_dict(value)


def publication_profile_reason(value: Mapping[str, Any], parsed: RC.KeyPublicationV1, *, profile: CustodyProfileV1,
                               key_id: str, credential_path: str) -> str | None:
    """None when the publication is the fixed DEV_SYNTHETIC shape for `key_id`."""
    custody = value.get("custodyEvidence")
    if not isinstance(custody, Mapping):
        return "PUBLICATION_PROFILE_MISMATCH"
    if (value.get("profile") != KEY_PUBLICATION_PROFILE or parsed.environment != profile.environment
            or parsed.signing_domain != profile.signing_domain or parsed.evidence_types != (profile.evidence_type,)
            or custody.get("credentialName") != profile.credential_name
            or custody.get("withKey") != KEY_PUBLICATION_WITH_KEY):
        return "PUBLICATION_PROFILE_MISMATCH"
    if parsed.key_id != key_id:
        return "PUBLICATION_KEY_ID_MISMATCH"
    if custody.get("credentialPath") != credential_path:
        return "PUBLICATION_CREDENTIAL_PATH_MISMATCH"
    if hashlib.sha256(parsed.public_key).hexdigest() != parsed.public_key_sha256:
        return "PUBLICATION_FINGERPRINT_INVALID"
    return None


# ----------------------------------------------- SuccessorCeremonyRecordV1 ---

CEREMONY_RECORD_TYPE = "LILITH_SUCCESSOR_CEREMONY_RECORD"
CEREMONY_RECORD_SCHEMA_VERSION = 1
CREATED_FOR_ROLE = "PREPARED"
CEREMONY_RECORD_FIELDS = frozenset({
    "recordType", "schemaVersion", "ceremonyId", "successorOrdinal", "keyId", "publicationDigest",
    "credentialBlobSha256", "reviewedReleaseSha", "createdForRole",
})


@dataclass(frozen=True)
class SuccessorCeremonyRecordV1:
    """RR-27 non-authority provenance of one successor preparation.

    `createdForRole = PREPARED` is historical creation provenance only: where
    the keygen wrote the blob, never the blob's current slot role (only the
    inventory observes that). Environment, domain, and type are not
    duplicated here: they are verified from the bound publication.
    """

    ceremony_id: str
    successor_ordinal: int
    key_id: str
    publication_digest: str
    credential_blob_sha256: str
    reviewed_release_sha: str
    created_for_role: str = CREATED_FOR_ROLE

    authority_granted: ClassVar[bool] = False

    @classmethod
    def from_dict(cls, value: Any) -> SuccessorCeremonyRecordV1:
        _exact(value, CEREMONY_RECORD_FIELDS)
        if value["recordType"] != CEREMONY_RECORD_TYPE or type(value["schemaVersion"]) is not int \
                or value["schemaVersion"] != CEREMONY_RECORD_SCHEMA_VERSION:
            raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
        if value["createdForRole"] != CREATED_FOR_ROLE:
            raise ContractViolation("CREATED_FOR_ROLE_INVALID")
        if not isinstance(value["reviewedReleaseSha"], str) or not _RELEASE.fullmatch(value["reviewedReleaseSha"]):
            raise ContractViolation("INVALID_REVIEWED_RELEASE_SHA")
        return cls(_id(value["ceremonyId"], "ceremony_id"), _checked_ordinal(value["successorOrdinal"]),
                   _id(value["keyId"], "key_id"), _digest(value["publicationDigest"], "publication_digest"),
                   _digest(value["credentialBlobSha256"], "credential_blob_sha256"), value["reviewedReleaseSha"])

    def to_dict(self) -> dict[str, Any]:
        return {"recordType": CEREMONY_RECORD_TYPE, "schemaVersion": CEREMONY_RECORD_SCHEMA_VERSION,
                "ceremonyId": self.ceremony_id, "successorOrdinal": self.successor_ordinal, "keyId": self.key_id,
                "publicationDigest": self.publication_digest, "credentialBlobSha256": self.credential_blob_sha256,
                "reviewedReleaseSha": self.reviewed_release_sha, "createdForRole": self.created_for_role}


CEREMONY_RECORD_VERIFIED = "CEREMONY_RECORD_VERIFIED"
CEREMONY_RECORD_NOT_VERIFIED = "CEREMONY_RECORD_NOT_VERIFIED"

# Closed, ordered ceremony-record taxonomy.
CEREMONY_RECORD_REASONS = (
    "CEREMONY_INPUT_MALFORMED",
    "PROFILE_NOT_DEV_SYNTHETIC",
    "CEREMONY_RECORD_MISSING",
    "CEREMONY_RECORD_MALFORMED",
    "UNSUPPORTED_SCHEMA_VERSION",
    "CREATED_FOR_ROLE_INVALID",
    "SUCCESSOR_ORDINAL_OUT_OF_RANGE",
    "CEREMONY_ID_MISMATCH",
    "KEY_ID_MISMATCH",
    "PUBLICATION_MISSING",
    "PUBLICATION_MALFORMED",
    "PUBLICATION_NOT_CANONICAL",
    "PUBLICATION_DIGEST_MISMATCH",
    "PUBLICATION_PROFILE_MISMATCH",
    "PUBLICATION_KEY_ID_MISMATCH",
    "PUBLICATION_CREDENTIAL_PATH_MISMATCH",
    "PUBLICATION_FINGERPRINT_INVALID",
    "CREDENTIAL_BLOB_MISMATCH",
    "REVIEWED_RELEASE_UNOBSERVED",
    "REVIEWED_RELEASE_MISMATCH",
    "PREPARED_BLOB_MISMATCH",
)


@dataclass(frozen=True)
class CeremonyRecordResultV1:
    status: str
    reason: str | None = None
    detail: str | None = None
    record: SuccessorCeremonyRecordV1 | None = None
    publication: RC.KeyPublicationV1 | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)

    @property
    def verified(self) -> bool:
        return self.status == CEREMONY_RECORD_VERIFIED


def build_successor_ceremony_record(*, publication_bytes: bytes, reviewed_release_sha: str,
                                    profile: CustodyProfileV1 = DEV_SYNTHETIC_CUSTODY_PROFILE) -> dict[str, Any]:
    """The record for one successor publication, as owner tooling produces it.

    `reviewed_release_sha` must come from the installer evidence (release
    directory, selector, and `CLI_BYTES`); it is provenance, never authority.
    """
    require_dev_synthetic(profile)
    value, parsed = parse_publication_bytes(publication_bytes)
    ordinal = successor_ordinal_of_key_id(parsed.key_id)
    if ordinal is None:
        raise ContractViolation("PUBLICATION_KEY_ID_MISMATCH")
    identity = successor_identity(ordinal)
    reason = publication_profile_reason(value, parsed, profile=profile, key_id=identity.key_id,
                                        credential_path=profile.prepared_path)
    if reason is not None:
        raise ContractViolation(reason)
    record = SuccessorCeremonyRecordV1(identity.ceremony_id, identity.ordinal, identity.key_id,
                                       publication_digest(publication_bytes), parsed.blob_sha256,
                                       reviewed_release_sha)
    return SuccessorCeremonyRecordV1.from_dict(record.to_dict()).to_dict()


def verify_successor_ceremony_record(*, record: Any, publication_bytes: Any, reviewed_release_sha: str | None,
                                     observed_prepared_blob_sha256: str | None = None,
                                     profile: CustodyProfileV1 = DEV_SYNTHETIC_CUSTODY_PROFILE,
                                     ) -> CeremonyRecordResultV1:
    """RR-27: is `record` the provenance of exactly this publication, blob, and release?

    Anti-substitution: the ceremony, ordinal, and keyId must be the one
    derivation of N; the publication must hash to `publicationDigest` and be
    the fixed PREPARED-form DEV_SYNTHETIC publication of that keyId; its
    `blobSha256` must equal the record; the reviewed release must equal the
    installer evidence; and, when given, the observed PREPARED blob hash must
    equal both. A verified record grants nothing.
    """
    facts: dict[str, Any] = {"authorityGranted": False, "makesKeyCurrent": False, "releasesHold": False}
    try:
        _require(isinstance(profile, CustodyProfileV1), "CEREMONY_INPUT_MALFORMED")
        _require(is_dev_synthetic(profile), "PROFILE_NOT_DEV_SYNTHETIC")
        _require(record is not None, "CEREMONY_RECORD_MISSING")
        try:
            parsed = SuccessorCeremonyRecordV1.from_dict(record)
        except OwnerProofError as exc:
            code = exc.code if exc.code in CEREMONY_RECORD_REASONS else "CEREMONY_RECORD_MALFORMED"
            raise _Reject(code) from exc
        identity = successor_identity(parsed.successor_ordinal)
        _require(parsed.ceremony_id == identity.ceremony_id, "CEREMONY_ID_MISMATCH")
        _require(parsed.key_id == identity.key_id, "KEY_ID_MISMATCH")
        _require(publication_bytes is not None, "PUBLICATION_MISSING")
        try:
            value, published = parse_publication_bytes(publication_bytes)
        except OwnerProofError as exc:
            raise _Reject("PUBLICATION_NOT_CANONICAL" if exc.code == "PUBLICATION_NOT_CANONICAL"
                          else "PUBLICATION_MALFORMED") from exc
        _require(publication_digest(publication_bytes) == parsed.publication_digest, "PUBLICATION_DIGEST_MISMATCH")
        reason = publication_profile_reason(value, published, profile=profile, key_id=parsed.key_id,
                                            credential_path=profile.prepared_path)
        _require(reason is None, reason or "")
        _require(published.blob_sha256 == parsed.credential_blob_sha256, "CREDENTIAL_BLOB_MISMATCH")
        _require(isinstance(reviewed_release_sha, str) and _RELEASE.fullmatch(reviewed_release_sha) is not None,
                 "REVIEWED_RELEASE_UNOBSERVED")
        _require(parsed.reviewed_release_sha == reviewed_release_sha, "REVIEWED_RELEASE_MISMATCH")
        if observed_prepared_blob_sha256 is not None:
            _require(observed_prepared_blob_sha256 == parsed.credential_blob_sha256, "PREPARED_BLOB_MISMATCH")
    except _Reject as rejected:
        return CeremonyRecordResultV1(CEREMONY_RECORD_NOT_VERIFIED, rejected.reason, rejected.detail, facts=facts)
    facts.update(ceremonyId=parsed.ceremony_id, successorOrdinal=parsed.successor_ordinal, keyId=parsed.key_id,
                 credentialBlobSha256=parsed.credential_blob_sha256, reviewedReleaseSha=parsed.reviewed_release_sha)
    return CeremonyRecordResultV1(CEREMONY_RECORD_VERIFIED, record=parsed, publication=published, facts=facts)


# ------------------------------------------- burned ordinals (anti-reuse) ---

CEREMONY_REGISTER_TYPE = "LILITH_SUCCESSOR_CEREMONY_REGISTER"
CEREMONY_REGISTER_SCHEMA_VERSION = 1
CEREMONY_REGISTER_FIELDS = frozenset({"registerType", "schemaVersion", "environment", "ceremonies"})
_REGISTER_ENTRY_FIELDS = frozenset({"successorOrdinal", "keyId", "ceremonyId", "publicationDigest",
                                    "credentialBlobSha256"})

# Closed, ordered register taxonomy.
CEREMONY_REGISTER_REASONS = (
    "REGISTER_MISSING",
    "REGISTER_MALFORMED",
    "REGISTER_ENVIRONMENT_MISMATCH",
    "REGISTER_ENTRY_NOT_DERIVED",
    "REGISTER_ORDINAL_DUPLICATED",
    "REGISTER_KEY_ID_DUPLICATED",
    "REGISTER_CEREMONY_ID_DUPLICATED",
    "REGISTER_MATERIAL_DUPLICATED",
    "ORDINAL_BURNED",
    "KEY_ID_BURNED",
    "CEREMONY_ID_BURNED",
    "MATERIAL_ALREADY_REGISTERED",
    "CEREMONY_NOT_REGISTERED",
    "ORDINAL_MATERIAL_MISMATCH",
    "KEY_ID_ORDINAL_CONFLICT",
    "CEREMONY_ID_ORDINAL_CONFLICT",
)


@dataclass(frozen=True)
class CeremonyRegisterEntryV1:
    successor_ordinal: int
    key_id: str
    ceremony_id: str
    publication_digest: str
    credential_blob_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {"successorOrdinal": self.successor_ordinal, "keyId": self.key_id, "ceremonyId": self.ceremony_id,
                "publicationDigest": self.publication_digest, "credentialBlobSha256": self.credential_blob_sha256}


@dataclass(frozen=True)
class SuccessorCeremonyRegisterV1:
    """The owner's burned-ordinal register (the successor part of PR-3). Not authority.

    An ordinal is burned once it produced material or a publication, even if
    the ceremony is later abandoned; so are its keyId and ceremonyId.
    """

    environment: str
    entries: tuple[CeremonyRegisterEntryV1, ...]

    authority_granted: ClassVar[bool] = False

    @classmethod
    def from_dict(cls, value: Any) -> SuccessorCeremonyRegisterV1:
        _exact(value, CEREMONY_REGISTER_FIELDS)
        if value["registerType"] != CEREMONY_REGISTER_TYPE or type(value["schemaVersion"]) is not int \
                or value["schemaVersion"] != CEREMONY_REGISTER_SCHEMA_VERSION:
            raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
        if not isinstance(value["ceremonies"], list):
            raise ContractViolation("REGISTER_MALFORMED")
        entries: list[CeremonyRegisterEntryV1] = []
        for item in value["ceremonies"]:
            _exact(item, _REGISTER_ENTRY_FIELDS)
            entry = CeremonyRegisterEntryV1(
                _checked_ordinal(item["successorOrdinal"]), _id(item["keyId"], "key_id"),
                _id(item["ceremonyId"], "ceremony_id"), _digest(item["publicationDigest"], "publication_digest"),
                _digest(item["credentialBlobSha256"], "credential_blob_sha256"))
            identity = successor_identity(entry.successor_ordinal)
            if (entry.key_id, entry.ceremony_id) != (identity.key_id, identity.ceremony_id):
                raise ContractViolation("REGISTER_ENTRY_NOT_DERIVED")
            for other in entries:
                if other.successor_ordinal == entry.successor_ordinal:
                    raise ContractViolation("REGISTER_ORDINAL_DUPLICATED")
                if other.key_id == entry.key_id:
                    raise ContractViolation("REGISTER_KEY_ID_DUPLICATED")
                if other.ceremony_id == entry.ceremony_id:
                    raise ContractViolation("REGISTER_CEREMONY_ID_DUPLICATED")
                if other.credential_blob_sha256 == entry.credential_blob_sha256 \
                        or other.publication_digest == entry.publication_digest:
                    raise ContractViolation("REGISTER_MATERIAL_DUPLICATED")
            entries.append(entry)
        return cls(_choice(value["environment"], DEPLOYMENT_ENVIRONMENTS, "environment"), tuple(entries))

    def to_dict(self) -> dict[str, Any]:
        return {"registerType": CEREMONY_REGISTER_TYPE, "schemaVersion": CEREMONY_REGISTER_SCHEMA_VERSION,
                "environment": self.environment,
                "ceremonies": [e.to_dict() for e in sorted(self.entries, key=lambda e: e.successor_ordinal)]}


def empty_ceremony_register(environment: str = ENVIRONMENT) -> dict[str, Any]:
    return SuccessorCeremonyRegisterV1(_choice(environment, DEPLOYMENT_ENVIRONMENTS, "environment"), ()).to_dict()


@dataclass(frozen=True)
class RegisterResultV1:
    reason: str | None = None
    detail: str | None = None
    register: dict[str, Any] | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.reason is None


def _parse_register(register: Any, environment: str) -> SuccessorCeremonyRegisterV1:
    _require(register is not None, "REGISTER_MISSING")
    try:
        parsed = register if isinstance(register, SuccessorCeremonyRegisterV1) \
            else SuccessorCeremonyRegisterV1.from_dict(register)
    except (OwnerProofError, TypeError) as exc:
        code = getattr(exc, "code", None)
        raise _Reject(code if code in CEREMONY_REGISTER_REASONS else "REGISTER_MALFORMED") from exc
    _require(parsed.environment == environment, "REGISTER_ENVIRONMENT_MISMATCH")
    return parsed


def check_ordinal_unburned(register: Any, ordinal: int, *,
                           profile: CustodyProfileV1 = DEV_SYNTHETIC_CUSTODY_PROFILE) -> RegisterResultV1:
    """Before any preparation: N, its keyId, and its ceremonyId are all unused."""
    try:
        parsed = _parse_register(register, profile.environment)
        try:
            identity = successor_identity(ordinal)
        except OwnerProofError as exc:
            raise _Reject("REGISTER_ENTRY_NOT_DERIVED") from exc
        for entry in parsed.entries:
            _require(entry.successor_ordinal != identity.ordinal, "ORDINAL_BURNED", str(identity.ordinal))
            _require(entry.key_id != identity.key_id, "KEY_ID_BURNED", identity.key_id)
            _require(entry.ceremony_id != identity.ceremony_id, "CEREMONY_ID_BURNED", identity.ceremony_id)
    except _Reject as rejected:
        return RegisterResultV1(rejected.reason, rejected.detail, facts={"authorityGranted": False})
    return RegisterResultV1(facts={"authorityGranted": False, "ordinal": identity.ordinal})


def register_successor_ceremony(register: Any, record: Any, *,
                                profile: CustodyProfileV1 = DEV_SYNTHETIC_CUSTODY_PROFILE) -> RegisterResultV1:
    """Burn one ordinal: the register with `record` appended, or a closed refusal.

    Refuses a duplicate ordinal, keyId, or ceremonyId (even for an abandoned
    ceremony) and a second ordinal for already-registered material.
    """
    try:
        parsed = _parse_register(register, profile.environment)
        try:
            entry_record = SuccessorCeremonyRecordV1.from_dict(record)
        except (OwnerProofError, TypeError) as exc:
            raise _Reject("REGISTER_MALFORMED") from exc
        identity = successor_identity(entry_record.successor_ordinal)
        _require((entry_record.key_id, entry_record.ceremony_id) == (identity.key_id, identity.ceremony_id),
                 "REGISTER_ENTRY_NOT_DERIVED")
        for entry in parsed.entries:
            _require(entry.successor_ordinal != identity.ordinal, "ORDINAL_BURNED", str(identity.ordinal))
            _require(entry.key_id != identity.key_id, "KEY_ID_BURNED")
            _require(entry.ceremony_id != identity.ceremony_id, "CEREMONY_ID_BURNED")
            _require(entry.credential_blob_sha256 != entry_record.credential_blob_sha256
                     and entry.publication_digest != entry_record.publication_digest, "MATERIAL_ALREADY_REGISTERED")
        extended = SuccessorCeremonyRegisterV1(parsed.environment, parsed.entries + (CeremonyRegisterEntryV1(
            identity.ordinal, identity.key_id, identity.ceremony_id, entry_record.publication_digest,
            entry_record.credential_blob_sha256),))
    except _Reject as rejected:
        return RegisterResultV1(rejected.reason, rejected.detail, facts={"authorityGranted": False})
    return RegisterResultV1(register=extended.to_dict(), facts={"authorityGranted": False})


def verify_registered_ceremony(register: Any, record: Any, *,
                               profile: CustodyProfileV1 = DEV_SYNTHETIC_CUSTODY_PROFILE) -> RegisterResultV1:
    """Is `record` exactly the material registered for its ordinal?

    Same ordinal with different material, a keyId registered under another
    ordinal, and a ceremonyId registered under another ordinal all refuse.
    """
    try:
        parsed = _parse_register(register, profile.environment)
        try:
            candidate = SuccessorCeremonyRecordV1.from_dict(record)
        except (OwnerProofError, TypeError) as exc:
            raise _Reject("REGISTER_MALFORMED") from exc
        for entry in parsed.entries:
            if entry.key_id == candidate.key_id and entry.successor_ordinal != candidate.successor_ordinal:
                raise _Reject("KEY_ID_ORDINAL_CONFLICT")
            if entry.ceremony_id == candidate.ceremony_id and entry.successor_ordinal != candidate.successor_ordinal:
                raise _Reject("CEREMONY_ID_ORDINAL_CONFLICT")
        matches = [e for e in parsed.entries if e.successor_ordinal == candidate.successor_ordinal]
        _require(len(matches) == 1, "CEREMONY_NOT_REGISTERED")
        entry = matches[0]
        _require((entry.key_id, entry.ceremony_id, entry.publication_digest, entry.credential_blob_sha256)
                 == (candidate.key_id, candidate.ceremony_id, candidate.publication_digest,
                     candidate.credential_blob_sha256), "ORDINAL_MATERIAL_MISMATCH")
    except _Reject as rejected:
        return RegisterResultV1(rejected.reason, rejected.detail, facts={"authorityGranted": False})
    return RegisterResultV1(facts={"authorityGranted": False, "ordinal": candidate.successor_ordinal})


# ----------------------------------------------- custody observation (RR-26) ---

CURRENT = "CURRENT"
PREPARED = "PREPARED"
RETIRED = "RETIRED"
# Prep A location role names for the same slots.
_LOCATION = {CURRENT: WR.CREDSTORE, PREPARED: WR.PREPARED, RETIRED: WR.RETIRED}


@dataclass(frozen=True)
class CustodyRootFactsV1:
    """lstat facts of `/etc/lilith-authority-custody` and its entry names."""

    kind: str
    uid: int | None = None
    gid: int | None = None
    mode: int | None = None
    names: tuple[str, ...] = ()


@dataclass(frozen=True)
class CustodyObservationV1:
    """Story 4: one root-observed custody snapshot. Never authority.

    - `inventory`: the Prep A slot inventory (CREDSTORE / PREPARED / RETIRED);
    - `devices`: `st_dev` of the credstore, PREPARED, and RETIRED directories;
    - `custody_root`: the custody root's own facts;
    - `current_identity`: `(st_dev, st_ino)` of the CURRENT blob, if any.
    """

    inventory: WR.CredentialInventoryObservationV1
    devices: Mapping[str, int | None]
    custody_root: CustodyRootFactsV1 | None
    current_identity: tuple[int, int] | None = None


# Custody states relative to one ceremony (P predecessor, S successor).
PREDECESSOR_STEADY = "PREDECESSOR_STEADY"   # CURRENT=P                      (STEADY)
STATE_A_PREPARED = "A_PREPARED"             # CURRENT=P, PREPARED=S          (SUCCESSOR_PREPARED)
STATE_B_VACATED = "B_VACATED"               # PREPARED=S, RETIRED=P          (CUTOVER_VACATED)
STATE_C_INSTALLED = "C_INSTALLED"           # CURRENT=S, RETIRED=P           (CUTOVER_INSTALLED)
SUCCESSOR_STEADY = "SUCCESSOR_STEADY"       # CURRENT=S                      (STEADY)
CUSTODY_STATES = (PREDECESSOR_STEADY, STATE_A_PREPARED, STATE_B_VACATED, STATE_C_INSTALLED, SUCCESSOR_STEADY)
_STATE_PHASE = {PREDECESSOR_STEADY: WR.STEADY, STATE_A_PREPARED: WR.SUCCESSOR_PREPARED,
                STATE_B_VACATED: WR.CUTOVER_VACATED, STATE_C_INSTALLED: WR.CUTOVER_INSTALLED,
                SUCCESSOR_STEADY: WR.STEADY}

# Closed, ordered custody taxonomy (after the Prep A inventory reasons).
CUSTODY_REASONS = (
    "CUSTODY_INPUT_MALFORMED",
    "CUSTODY_ROOT_MISSING",
    "CUSTODY_ROOT_NOT_DIRECTORY",
    "CUSTODY_ROOT_CUSTODY",
    "CUSTODY_ROOT_UNEXPECTED_ENTRY",
    "CUSTODY_DIRECTORY_MISSING",
    "CUSTODY_SLOT_NAME_UNEXPECTED",
    "SAME_FILESYSTEM_UNPROVEN",
    "CUSTODY_FILESYSTEM_MISMATCH",
    "CUSTODY_INVENTORY_NOT_VERIFIED",
    "CUSTODY_PHASE_UNRECOGNIZED",
    "WRONG_PREDECESSOR_BLOB",
    "WRONG_SUCCESSOR_BLOB",
    "UNEXPECTED_CUSTODY_STATE",
)


@dataclass(frozen=True)
class CustodyCeremonyV1:
    """The blob hashes one ceremony expects. Hashes come from verified
    publications (P: the head predecessor's; S: the ceremony record's)."""

    ceremony_id: str
    predecessor_key_id: str
    predecessor_blob_sha256: str
    successor_key_id: str
    successor_blob_sha256: str


@dataclass(frozen=True)
class CustodyResultV1:
    reason: str | None
    detail: str | None = None
    phase: str | None = None
    state: str | None = None
    hashes: Mapping[str, str | None] = field(default_factory=dict)
    facts: Mapping[str, Any] = field(default_factory=dict)

    @property
    def verified(self) -> bool:
        return self.reason is None


def same_filesystem_reason(observation: CustodyObservationV1) -> str | None:
    """None when CURRENT, PREPARED, and RETIRED directories share one `st_dev`.

    Required before PREPARE and again before every rename. `same-filesystem
    proof != authority`.
    """
    if not isinstance(observation, CustodyObservationV1) or not isinstance(observation.devices, Mapping):
        return "SAME_FILESYSTEM_UNPROVEN"
    devices = [observation.devices.get(role) for role in (CURRENT, PREPARED, RETIRED)]
    if any(type(device) is not int for device in devices):
        return "SAME_FILESYSTEM_UNPROVEN"
    return None if len(set(devices)) == 1 else "CUSTODY_FILESYSTEM_MISMATCH"


def _custody_root(observation: CustodyObservationV1, contract: WR.CredentialSlotContractV1) -> None:
    root = observation.custody_root
    _require(root is not None and root.kind != WR.ABSENT, "CUSTODY_ROOT_MISSING")
    _require(root.kind == WR.DIRECTORY, "CUSTODY_ROOT_NOT_DIRECTORY")
    _require((root.uid, root.gid, root.mode) == (contract.owner_uid, contract.owner_gid, contract.directory_mode),
             "CUSTODY_ROOT_CUSTODY")
    _require(tuple(sorted(root.names)) == CUSTODY_ROOT_NAMES, "CUSTODY_ROOT_UNEXPECTED_ENTRY")


# Prep A reasons that only say "these counts are not the probed phase".
_COUNT_REASONS = frozenset({"CURRENT_SLOT_MISSING", "CURRENT_SLOT_NOT_PERMITTED", "PREPARED_SLOT_MISSING",
                            "PREPARED_SLOT_NOT_PERMITTED", "RETIRED_SLOT_MISSING", "RETIRED_SLOT_NOT_PERMITTED"})


def observe_custody(observation: Any,
                    contract: WR.CredentialSlotContractV1 = WR.DEV_SYNTHETIC_SLOT_CONTRACT) -> CustodyResultV1:
    """Which inventory phase the observed slots are in, with every RR-26 fact.

    Fails closed on: a missing or wrongly owned custody root; unexpected
    names; a missing PREPARED or RETIRED directory; a slot blob under any name
    other than the fixed slot name; an unproven or mismatched filesystem; and
    anything the Prep A inventory refuses (symlinks, non-regular entries,
    owner, mode, extra or duplicate blobs). It selects no key.
    """
    facts = {"authorityGranted": False, "selectsAuthoritativeKey": False}
    try:
        _require(isinstance(observation, CustodyObservationV1)
                 and isinstance(observation.inventory, WR.CredentialInventoryObservationV1), "CUSTODY_INPUT_MALFORMED")
        _custody_root(observation, contract)
        by_role = {getattr(loc, "role", None): loc for loc in observation.inventory.locations}
        for role in (WR.PREPARED, WR.RETIRED):
            location = by_role.get(role)
            _require(location is not None and location.kind != WR.ABSENT, "CUSTODY_DIRECTORY_MISSING", role)
            for entry in location.entries:
                _require(getattr(entry, "name", None) == SLOT_NAME, "CUSTODY_SLOT_NAME_UNEXPECTED",
                         f"{role}/{getattr(entry, 'name', '?')}")
        reason = same_filesystem_reason(observation)
        _require(reason is None, reason or "")
        counts = tuple(len(by_role[role].entries) if role in by_role and by_role[role].kind != WR.ABSENT else 0
                       for role in (WR.CREDSTORE, WR.PREPARED, WR.RETIRED))
        phases = [phase for phase, expected in WR.INVENTORY_PHASES.items() if expected == counts]
        if not phases:
            # Let the Prep A inventory name the exact refusal (duplicates, extras).
            probe = WR.verify_credential_inventory(inventory=observation.inventory, phase=WR.STEADY, contract=contract)
            _require(probe.verified or probe.reason in _COUNT_REASONS, "CUSTODY_INVENTORY_NOT_VERIFIED", probe.reason)
            raise _Reject("CUSTODY_PHASE_UNRECOGNIZED", str(counts))
        phase = phases[0]
        slots = WR.verify_credential_inventory(inventory=observation.inventory, phase=phase, contract=contract)
        _require(slots.verified, "CUSTODY_INVENTORY_NOT_VERIFIED", slots.reason)
    except _Reject as rejected:
        return CustodyResultV1(rejected.reason, rejected.detail, facts=facts)
    hashes = {CURRENT: slots.facts["currentSlotSha256"], PREPARED: slots.facts["preparedSha256"],
              RETIRED: slots.facts["retiredSha256"]}
    return CustodyResultV1(None, phase=phase, hashes=hashes, facts={**facts, "loadableBlobs": slots.facts["loadableBlobs"]})


def custody_state(observation: Any, ceremony: CustodyCeremonyV1,
                  contract: WR.CredentialSlotContractV1 = WR.DEV_SYNTHETIC_SLOT_CONTRACT) -> CustodyResultV1:
    """The named A/B/C (or steady) state of `ceremony`, by exact blob hashes."""
    observed = observe_custody(observation, contract)
    if not observed.verified:
        return observed
    p, s = ceremony.predecessor_blob_sha256, ceremony.successor_blob_sha256
    expected = {
        PREDECESSOR_STEADY: {CURRENT: p, PREPARED: None, RETIRED: None},
        STATE_A_PREPARED: {CURRENT: p, PREPARED: s, RETIRED: None},
        STATE_B_VACATED: {CURRENT: None, PREPARED: s, RETIRED: p},
        STATE_C_INSTALLED: {CURRENT: s, PREPARED: None, RETIRED: p},
        SUCCESSOR_STEADY: {CURRENT: s, PREPARED: None, RETIRED: None},
    }
    for state, roles in expected.items():
        if _STATE_PHASE[state] == observed.phase and dict(observed.hashes) == roles:
            return CustodyResultV1(None, phase=observed.phase, state=state, hashes=observed.hashes,
                                   facts=observed.facts)
    hashes = observed.hashes
    successor_roles = {PREPARED} if observed.phase in (WR.SUCCESSOR_PREPARED, WR.CUTOVER_VACATED) else {CURRENT}
    if observed.phase in (WR.CUTOVER_VACATED, WR.CUTOVER_INSTALLED) and hashes[RETIRED] != p:
        reason = "WRONG_PREDECESSOR_BLOB"
    elif observed.phase == WR.SUCCESSOR_PREPARED and hashes[CURRENT] != p:
        reason = "WRONG_PREDECESSOR_BLOB"
    elif observed.phase != WR.STEADY and any(hashes[role] != s for role in successor_roles):
        reason = "WRONG_SUCCESSOR_BLOB"
    else:
        reason = "UNEXPECTED_CUSTODY_STATE"
    return CustodyResultV1(reason, observed.phase, phase=observed.phase, hashes=hashes, facts=observed.facts)


# ------------------------------------------ forward-only transitions (SW-1) ---

PREPARE = "PREPARE"     # PREDECESSOR_STEADY -> A  (keygen `successor <N>`; CURRENT untouched)
ABANDON = "ABANDON"     # A -> PREDECESSOR_STEADY  (destroy PREPARED S; before the authority PONR only)
VACATE = "VACATE"       # A -> B  (rename CURRENT -> RETIRED; after the authority PONR only)
INSTALL = "INSTALL"     # B -> C  (rename PREPARED -> CURRENT; after the authority PONR only)
DESTROY = "DESTROY"     # C -> SUCCESSOR_STEADY  (unlink RETIRED P; after S_CURRENT only)
CUSTODY_STEPS = {PREPARE: (PREDECESSOR_STEADY, STATE_A_PREPARED), ABANDON: (STATE_A_PREPARED, PREDECESSOR_STEADY),
                 VACATE: (STATE_A_PREPARED, STATE_B_VACATED), INSTALL: (STATE_B_VACATED, STATE_C_INSTALLED),
                 DESTROY: (STATE_C_INSTALLED, SUCCESSOR_STEADY)}
_STEPS_BEFORE_PONR = frozenset({PREPARE, ABANDON})
_STEPS_AFTER_PONR = frozenset({VACATE, INSTALL, DESTROY})


def custody_transition_reason(from_state: str, to_state: str, *, authority_ponr_passed: bool) -> str | None:
    """None when `from_state -> to_state` is one allowed step for the PONR phase.

    Before the authority PONR only PREPARE / ABANDON exist (P never leaves
    CURRENT). After it the only direction is A -> B -> C -> steady(S): no
    B -> A, no C -> A, no C -> B, and never a return of P to CURRENT.
    """
    step = next((name for name, pair in CUSTODY_STEPS.items() if pair == (from_state, to_state)), None)
    if step is None:
        if authority_ponr_passed and to_state in (PREDECESSOR_STEADY, STATE_A_PREPARED):
            return "PREDECESSOR_RESTORE_FORBIDDEN"
        return "CUSTODY_TRANSITION_NOT_DEFINED"
    if authority_ponr_passed and step in _STEPS_BEFORE_PONR:
        return "PREDECESSOR_RESTORE_FORBIDDEN" if step == ABANDON else "AUTHORITY_PONR_ALREADY_PASSED"
    if not authority_ponr_passed and step in _STEPS_AFTER_PONR:
        return "AUTHORITY_PONR_NOT_REACHED"
    return None


@dataclass(frozen=True)
class CustodyStepPlanV1:
    """Filesystem preconditions of one custody step. Never sufficient alone:
    `successor_readiness.authorize_custody_step` adds the authority head and
    the hold. A plan moves nothing."""

    status: str
    reason: str | None = None
    detail: str | None = None
    step: str | None = None
    operation: tuple[str, ...] = ()
    expected_sha256: str | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)

    @property
    def planned(self) -> bool:
        return self.status == RC.PLANNED


def plan_custody_filesystem_step(*, step: str, observation: Any, ceremony: CustodyCeremonyV1,
                                 profile: CustodyProfileV1 = DEV_SYNTHETIC_CUSTODY_PROFILE) -> CustodyStepPlanV1:
    """Same-filesystem proof, the exact from-state with exact P / S hashes,
    every RR-26 custody fact, and the one rename or unlink the step names."""
    facts = {"authorityGranted": False, "filesystemContentsAlone": "NEVER_SUFFICIENT"}
    try:
        _require(step in CUSTODY_STEPS and step != PREPARE, "CUSTODY_STEP_UNKNOWN", str(step))
        require_dev_synthetic(profile)
        _require(isinstance(ceremony, CustodyCeremonyV1)
                 and ceremony.predecessor_blob_sha256 != ceremony.successor_blob_sha256
                 and ceremony.predecessor_key_id != ceremony.successor_key_id, "CUSTODY_INPUT_MALFORMED")
        reason = same_filesystem_reason(observation) if isinstance(observation, CustodyObservationV1) \
            else "CUSTODY_INPUT_MALFORMED"
        _require(reason is None, reason or "")
        state = custody_state(observation, ceremony)
        _require(state.verified, state.reason or "", state.detail)
        source, target = CUSTODY_STEPS[step]
        _require(state.state == source, "CUSTODY_STATE_NOT_FROM_STATE", f"{state.state}!={source}")
        if step == VACATE:
            operation, expected = ("RENAME", profile.current_path, profile.retired_path), ceremony.predecessor_blob_sha256
        elif step == INSTALL:
            operation, expected = ("RENAME", profile.prepared_path, profile.current_path), ceremony.successor_blob_sha256
        elif step == DESTROY:
            operation, expected = ("UNLINK", profile.retired_path), ceremony.predecessor_blob_sha256
        else:
            operation, expected = ("UNLINK", profile.prepared_path), ceremony.successor_blob_sha256
    except (_Reject, OwnerProofError) as rejected:
        reason = rejected.reason if isinstance(rejected, _Reject) else rejected.code
        return CustodyStepPlanV1(RC.REFUSED, reason, getattr(rejected, "detail", None), step, facts=facts)
    return CustodyStepPlanV1(RC.PLANNED, None, None, step, operation, expected,
                             facts={**facts, "fromState": source, "toState": target})


def verify_preparation(*, before: Any, after: Any, ceremony: CustodyCeremonyV1,
                       current_facts_before: tuple | None = None, current_facts_after: tuple | None = None,
                       ) -> CustodyResultV1:
    """§7.3 step 5 / gate SW-2: PREPARE left CURRENT unchanged and created only PREPARED.

    `before` must be PREDECESSOR_STEADY and `after` A_PREPARED for the same
    ceremony; CURRENT's `(st_dev, st_ino)` and the keygen's own full CURRENT
    facts (identity, owner, mode, size, SHA-256), when given, must be equal.
    """
    first = custody_state(before, ceremony)
    if not first.verified:
        return first
    if first.state != PREDECESSOR_STEADY:
        return CustodyResultV1("CURRENT_NOT_PREDECESSOR_BEFORE_PREPARE", first.state, phase=first.phase)
    second = custody_state(after, ceremony)
    if not second.verified:
        return second
    if second.state != STATE_A_PREPARED:
        return CustodyResultV1("PREPARED_NOT_CREATED", second.state, phase=second.phase)
    if before.current_identity is None or before.current_identity != after.current_identity:
        return CustodyResultV1("CURRENT_CHANGED", "IDENTITY", phase=second.phase)
    if current_facts_before is not None and current_facts_before != current_facts_after:
        return CustodyResultV1("CURRENT_CHANGED", "KEYGEN_FACTS", phase=second.phase)
    return CustodyResultV1(None, phase=second.phase, state=second.state, hashes=second.hashes,
                           facts={"authorityGranted": False, "currentByteIdentical": True,
                                  "retiredWritten": False})


# ---------------------------------------------------- CeremonyHoldV1 (RR-24) ---

HOLD_PROTOCOL = "LILITH_CEREMONY_HOLD"
HOLD_SCHEMA_VERSION = 1
HOLD_FIELDS = frozenset({
    "protocol", "schemaVersion", "environment", "ceremonyId", "transitionKind", "state", "reason",
    "expectedPredecessorKeyId", "expectedSuccessorKeyId", "observedWitnessDigest",
})
HELD = "HELD"
RELEASED = "RELEASED"
HOLD_STATES = frozenset({HELD, RELEASED})
INITIAL_CUSTODY = "INITIAL_CUSTODY"
ROTATION = "ROTATION"
KEY_COMPROMISE_RECOVERY = "KEY_COMPROMISE_RECOVERY"
TRANSITION_KINDS = frozenset({INITIAL_CUSTODY, ROTATION, KEY_COMPROMISE_RECOVERY})
# SOURCE DETAIL: closed, informational reason taxonomy.
INITIAL_CUSTODY_BOOTSTRAP = "INITIAL_CUSTODY_BOOTSTRAP"
ROTATION_IN_PROGRESS = "ROTATION_IN_PROGRESS"
KEY_COMPROMISE_RECOVERY_IN_PROGRESS = "KEY_COMPROMISE_RECOVERY_IN_PROGRESS"
PREDECESSOR_DESTRUCTION_INCOMPLETE = "PREDECESSOR_DESTRUCTION_INCOMPLETE"
OWNER_RELEASE_AFTER_ELIGIBILITY = "OWNER_RELEASE_AFTER_ELIGIBILITY"
HOLD_REASONS = frozenset({INITIAL_CUSTODY_BOOTSTRAP, ROTATION_IN_PROGRESS, KEY_COMPROMISE_RECOVERY_IN_PROGRESS,
                          PREDECESSOR_DESTRUCTION_INCOMPLETE, OWNER_RELEASE_AFTER_ELIGIBILITY})
_HELD_REASON = {INITIAL_CUSTODY: INITIAL_CUSTODY_BOOTSTRAP, ROTATION: ROTATION_IN_PROGRESS,
                KEY_COMPROMISE_RECOVERY: KEY_COMPROMISE_RECOVERY_IN_PROGRESS}

# Closed, ordered hold taxonomy.
HOLD_REASON_CODES = (
    "HOLD_MISSING",
    "HOLD_MALFORMED",
    "HOLD_UNSUPPORTED_VERSION",
    "HOLD_STATE_UNKNOWN",
    "HOLD_TRANSITION_KIND_UNKNOWN",
    "HOLD_REASON_UNKNOWN",
    "HOLD_ENVIRONMENT_MISMATCH",
    "HOLD_REASON_STATE_MISMATCH",
    "HOLD_INITIAL_PREDECESSOR_NOT_NULL",
    "HOLD_INITIAL_SUCCESSOR_MISMATCH",
    "HOLD_INITIAL_CEREMONY_MISMATCH",
    "HOLD_PREDECESSOR_REQUIRED",
    "HOLD_CEREMONY_NOT_DERIVED",
    "HOLD_SUCCESSOR_REQUIRED",
    "HOLD_SUCCESSOR_NOT_DERIVED",
    "HOLD_PREDECESSOR_IS_SUCCESSOR",
)


@dataclass(frozen=True)
class CeremonyHoldV1:
    """RR-24 / RR-30: a pure, versioned, NON-AUTHORITY gating container.

    Every field is unauthenticated (design §9.1); its integrity is root
    custody of wherever it is kept. HELD blocks issuance readiness; a bound
    RELEASED passes only the hold check. Nothing here creates registry
    authority, substitutes for K-ROOT or K-WIT, makes a credential current,
    or grants issuance. There is no `createdAt`: timestamps are not authority.
    """

    environment: str
    ceremony_id: str
    transition_kind: str
    state: str
    reason: str
    expected_predecessor_key_id: str | None
    expected_successor_key_id: str | None
    observed_witness_digest: str

    authority_granted: ClassVar[bool] = False

    @property
    def custody_debt(self) -> bool:
        return self.ceremony_id.endswith(CUSTODY_DEBT_SUFFIX)

    @classmethod
    def from_dict(cls, value: Any, *, profile: CustodyProfileV1 = DEV_SYNTHETIC_CUSTODY_PROFILE) -> CeremonyHoldV1:
        if not isinstance(value, Mapping):
            raise ContractViolation("HOLD_MALFORMED")
        if value.get("protocol") != HOLD_PROTOCOL or type(value.get("schemaVersion")) is not int \
                or value.get("schemaVersion") != HOLD_SCHEMA_VERSION:
            raise ContractViolation("HOLD_UNSUPPORTED_VERSION")
        try:
            _exact(value, HOLD_FIELDS)
            ceremony_id = _id(value["ceremonyId"], "ceremony_id")
            predecessor = None if value["expectedPredecessorKeyId"] is None \
                else _id(value["expectedPredecessorKeyId"], "expected_predecessor_key_id")
            successor = None if value["expectedSuccessorKeyId"] is None \
                else _id(value["expectedSuccessorKeyId"], "expected_successor_key_id")
            witness_digest = _digest(value["observedWitnessDigest"], "observed_witness_digest")
            environment = _choice(value["environment"], DEPLOYMENT_ENVIRONMENTS, "environment")
        except OwnerProofError as exc:
            raise ContractViolation("HOLD_MALFORMED") from exc
        state, kind, reason = value["state"], value["transitionKind"], value["reason"]
        if state not in HOLD_STATES:
            raise ContractViolation("HOLD_STATE_UNKNOWN")
        if kind not in TRANSITION_KINDS:
            raise ContractViolation("HOLD_TRANSITION_KIND_UNKNOWN")
        if reason not in HOLD_REASONS:
            raise ContractViolation("HOLD_REASON_UNKNOWN")
        if environment != profile.environment:
            raise ContractViolation("HOLD_ENVIRONMENT_MISMATCH")
        hold = cls(environment, ceremony_id, kind, state, reason, predecessor, successor, witness_digest)
        code = hold._structure_reason(profile)
        if code is not None:
            raise ContractViolation(code)
        return hold

    def _structure_reason(self, profile: CustodyProfileV1) -> str | None:
        debt = self.custody_debt and self.transition_kind != INITIAL_CUSTODY
        if self.state == RELEASED:
            expected_reason = OWNER_RELEASE_AFTER_ELIGIBILITY
        else:
            expected_reason = PREDECESSOR_DESTRUCTION_INCOMPLETE if debt else _HELD_REASON[self.transition_kind]
        if self.reason != expected_reason:
            return "HOLD_REASON_STATE_MISMATCH"
        if self.transition_kind == INITIAL_CUSTODY:
            if self.expected_predecessor_key_id is not None:
                return "HOLD_INITIAL_PREDECESSOR_NOT_NULL"
            if self.expected_successor_key_id != profile.initial_key_id:
                return "HOLD_INITIAL_SUCCESSOR_MISMATCH"
            if self.ceremony_id != initial_ceremony_id(profile.environment, profile.initial_key_id):
                return "HOLD_INITIAL_CEREMONY_MISMATCH"
            return None
        # ROTATION / KEY_COMPROMISE_RECOVERY: null predecessor is never valid here.
        if self.expected_predecessor_key_id is None:
            return "HOLD_PREDECESSOR_REQUIRED"
        ordinal = successor_ordinal_of_ceremony_id(primary_ceremony_id(self.ceremony_id))
        if ordinal is None or (debt and primary_ceremony_id(self.ceremony_id) + CUSTODY_DEBT_SUFFIX
                               != self.ceremony_id):
            return "HOLD_CEREMONY_NOT_DERIVED"
        if self.expected_successor_key_id is None:
            # Unknown successor only while HELD before preparation.
            return None if self.state == HELD and not debt else "HOLD_SUCCESSOR_REQUIRED"
        if self.expected_successor_key_id != successor_identity(ordinal).key_id:
            return "HOLD_SUCCESSOR_NOT_DERIVED"
        if self.expected_predecessor_key_id == self.expected_successor_key_id:
            return "HOLD_PREDECESSOR_IS_SUCCESSOR"
        return None

    def to_dict(self) -> dict[str, Any]:
        return {"protocol": HOLD_PROTOCOL, "schemaVersion": HOLD_SCHEMA_VERSION, "environment": self.environment,
                "ceremonyId": self.ceremony_id, "transitionKind": self.transition_kind, "state": self.state,
                "reason": self.reason, "expectedPredecessorKeyId": self.expected_predecessor_key_id,
                "expectedSuccessorKeyId": self.expected_successor_key_id,
                "observedWitnessDigest": self.observed_witness_digest}


def parse_ceremony_hold(value: Any, *, profile: CustodyProfileV1 = DEV_SYNTHETIC_CUSTODY_PROFILE
                        ) -> tuple[CeremonyHoldV1 | None, str | None]:
    """(hold, None) or (None, closed reason). Missing is never RELEASED."""
    if value is None:
        return None, "HOLD_MISSING"
    if isinstance(value, CeremonyHoldV1):
        value = value.to_dict()
    try:
        return CeremonyHoldV1.from_dict(value, profile=profile), None
    except (OwnerProofError, TypeError, KeyError) as exc:
        code = getattr(exc, "code", None)
        return None, code if code in HOLD_REASON_CODES else "HOLD_MALFORMED"


HOLD_TRANSITION_REASONS = (
    "HOLD_PROPOSED_INVALID",
    "HOLD_PREVIOUS_INVALID",
    "HOLD_MUST_START_HELD",
    "HOLD_ALREADY_RELEASED",
    "HOLD_BINDING_CHANGED",
)


def hold_transition_reason(previous: Any, proposed: Any, *,
                           profile: CustodyProfileV1 = DEV_SYNTHETIC_CUSTODY_PROFILE) -> str | None:
    """None when `previous -> proposed` is a permitted hold lifecycle step.

    missing -> HELD -> RELEASED only. Never missing -> RELEASED, never
    RELEASED -> HELD for the same ceremony, and never RELEASED -> RELEASED
    with different bindings (an identical re-assertion is a no-op). HELD may
    be re-asserted only to fill a null successor with the derived keyId. A
    new ceremony starts again from missing. This decides a record step only;
    whether a RELEASED hold may be written at all is HOLD_RELEASE_ELIGIBILITY.
    """
    new, reason = parse_ceremony_hold(proposed, profile=profile)
    if new is None:
        return "HOLD_PROPOSED_INVALID"
    old = None
    if previous is not None:
        old, reason = parse_ceremony_hold(previous, profile=profile)
        if old is None:
            return "HOLD_PREVIOUS_INVALID"
        if old.ceremony_id != new.ceremony_id:
            old = None  # a different ceremony: a new lifecycle
    if old is None:
        return None if new.state == HELD else "HOLD_MUST_START_HELD"
    if old.state == RELEASED:
        return None if new == old else "HOLD_ALREADY_RELEASED"
    same = (old.environment, old.transition_kind, old.expected_predecessor_key_id) == \
        (new.environment, new.transition_kind, new.expected_predecessor_key_id)
    if not same or (old.expected_successor_key_id is not None
                    and old.expected_successor_key_id != new.expected_successor_key_id):
        return "HOLD_BINDING_CHANGED"
    if new.state == HELD and new.observed_witness_digest != old.observed_witness_digest:
        return "HOLD_BINDING_CHANGED"
    return None


# ------------------------------------------ predecessor destruction (§13) ---

DESTRUCTION_RECORD_TYPE = "LILITH_PREDECESSOR_DESTRUCTION_RECORD"
DESTRUCTION_RECORD_SCHEMA_VERSION = 1
DESTROYED = "DESTROYED_FROM_ACTIVE_CUSTODY"
DESTRUCTION_INCOMPLETE = "DESTRUCTION_INCOMPLETE"
KNOWN_CUSTODY_DEBT = "KNOWN_CUSTODY_DEBT"
MEDIA_ZEROIZATION = "NOT_CLAIMED"

DESTRUCTION_EVIDENCE_REASONS = (
    "DESTRUCTION_INPUT_MALFORMED",
    "RETIRED_BLOB_NOT_OBSERVED_BEFORE",
    "RETIRED_BLOB_CUSTODY_BEFORE",
    "RETIRED_BLOB_HASH_MISMATCH",
    "UNLINK_NOT_CONFIRMED",
    "DIRECTORY_FSYNC_NOT_CONFIRMED",
    "RETIRED_BLOB_STILL_PRESENT",
    "STEADY_INVENTORY_NOT_VERIFIED",
    "STEADY_CURRENT_NOT_SUCCESSOR",
)


@dataclass(frozen=True)
class DestructionObservationV1:
    """What root tooling observed around one logical unlink of RETIRED P."""

    before: WR.CredentialFileObservationV1 | None
    unlink_succeeded: bool
    directory_fsynced: bool
    after_lookup: str                     # WR.ABSENT when lstat finds nothing
    after: CustodyObservationV1 | None


@dataclass(frozen=True)
class DestructionOutcomeV1:
    status: str
    reason: str | None = None
    record: dict[str, Any] | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)

    @property
    def destroyed(self) -> bool:
        return self.status == DESTROYED


def evaluate_destruction_evidence(evidence: Any, ceremony: CustodyCeremonyV1, *, readiness_digest: str,
                                  contract: WR.CredentialSlotContractV1 = WR.DEV_SYNTHETIC_SLOT_CONTRACT,
                                  ) -> DestructionOutcomeV1:
    """RR-29 / §13: is the required logical-destruction evidence complete?

    Proves only: the expected RETIRED blob existed as a root 0600 regular
    file whose SHA-256 equalled P's publication; the unlink succeeded; the
    RETIRED directory was fsynced; lstat is then absent; and the inventory is
    STEADY with CURRENT = S. Anything short of that is DESTRUCTION_INCOMPLETE:
    KNOWN_CUSTODY_DEBT under an availability hold, owner retry, and never an
    authority rollback or a restore of P. Media zeroization, journal / SSD /
    page-cache remanence, process memory, and snapshot or backup copies are
    NOT claimed. `destruction != revocation`.
    """
    base = {"authorityGranted": False, "authorityRollbackPermitted": False, "predecessorRestorePermitted": False,
            "mediaZeroization": MEDIA_ZEROIZATION, "revocationEffect": "NONE"}
    try:
        _require(isinstance(evidence, DestructionObservationV1) and isinstance(ceremony, CustodyCeremonyV1),
                 "DESTRUCTION_INPUT_MALFORMED")
        _digest(readiness_digest, "readiness_digest")
        before = evidence.before
        _require(isinstance(before, WR.CredentialFileObservationV1) and before.name == SLOT_NAME,
                 "RETIRED_BLOB_NOT_OBSERVED_BEFORE")
        _require((before.kind, before.uid, before.gid, before.mode)
                 == (WR.REGULAR, contract.owner_uid, contract.owner_gid, contract.blob_mode),
                 "RETIRED_BLOB_CUSTODY_BEFORE")
        _require(before.sha256 == ceremony.predecessor_blob_sha256, "RETIRED_BLOB_HASH_MISMATCH")
        _require(evidence.unlink_succeeded is True, "UNLINK_NOT_CONFIRMED")
        _require(evidence.directory_fsynced is True, "DIRECTORY_FSYNC_NOT_CONFIRMED")
        _require(evidence.after_lookup == WR.ABSENT, "RETIRED_BLOB_STILL_PRESENT")
        after = custody_state(evidence.after, ceremony, contract)
        _require(after.verified and after.phase == WR.STEADY, "STEADY_INVENTORY_NOT_VERIFIED", after.reason)
        _require(after.state == SUCCESSOR_STEADY, "STEADY_CURRENT_NOT_SUCCESSOR")
    except (_Reject, OwnerProofError) as rejected:
        reason = rejected.reason if isinstance(rejected, _Reject) else "DESTRUCTION_INPUT_MALFORMED"
        return DestructionOutcomeV1(DESTRUCTION_INCOMPLETE, reason, facts={
            **base, "custodyClass": KNOWN_CUSTODY_DEBT, "availabilityHoldRequired": True, "ownerRetryRequired": True,
            "predecessorMaterialDestroyedFromActiveCustody": False})
    record = {
        "recordType": DESTRUCTION_RECORD_TYPE, "schemaVersion": DESTRUCTION_RECORD_SCHEMA_VERSION,
        "ceremonyId": ceremony.ceremony_id, "predecessorKeyId": ceremony.predecessor_key_id,
        "predecessorBlobSha256": ceremony.predecessor_blob_sha256, "retiredPath": RETIRED_PATH,
        "preUnlink": {"kind": before.kind, "uid": before.uid, "gid": before.gid, "mode": format(before.mode, "04o"),
                      "sha256": before.sha256},
        "unlinkSucceeded": True, "directoryFsynced": True, "postLookup": WR.ABSENT,
        "postInventoryPhase": WR.STEADY, "postCurrentSha256": ceremony.successor_blob_sha256,
        "successorCurrentReadinessDigest": readiness_digest,
        "predecessorMaterialDestroyedFromActiveCustody": True, "mediaZeroization": MEDIA_ZEROIZATION,
        "authorityGranted": False,
    }
    return DestructionOutcomeV1(DESTROYED, record=record, facts={
        **base, "custodyClass": None, "availabilityHoldRequired": False, "ownerRetryRequired": False,
        "predecessorMaterialDestroyedFromActiveCustody": True})


def record_digest(record: Mapping[str, Any]) -> str:
    """SHA-256 of a record's RFC 8785 bytes (for cross-references only)."""
    return hashlib.sha256(WR.document_bytes(record)).hexdigest()
