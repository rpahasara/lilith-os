"""15B2b-B1b-3e PR-1S: K-WIT identity, witness publication, and the V2 genesis
candidate (pure).

Design: docs/architecture/slice-15b2b-b1b3e-pr1-live-install-preflight.md
§10-§14 (RR-35, RR-36, RR-37).
Record: docs/architecture/slice-15b2b-b1b3e-pr1s-runtime-wiring.md.

- `WitnessProfileV1`: the fixed DEV_SYNTHETIC RecoveryWitness identity
  (account, unit, keyId, runtime credential name, the RR-36 credential
  source, state paths). Structurally distinct from K-ACT: every identifier
  that could alias the authority signer is refused.
- `WitnessKeyPublicationV1`: the K-WIT keygen's public output. A distinct
  publication type from the K-ACT publication, so neither parses as the
  other. `witness_anchor_document` derives the `TrustedWitnessAnchorV1`.
- `witness_distinctness_reason`: preflight §11 distinctness evidence.
- `build_genesis_candidate` (RR-35 PIN-BEFORE-COMMIT steps 1-2): the exact
  unsigned V2 genesis over registry v1 and the ledger's INITIAL position
  (sequence 1, the head the registry implies), and its canonical digest,
  which excludes the K-WIT signature and so exists before K-WIT signs.
  `candidate_pin_reason` is step 4.

Pure: no file, environment, network, database, or credential is read and
nothing is signed. Every result is non-authority:

    genesis candidate digest != genesis
    owner pin                != authority
    K-WIT credential exists  != witness exists
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from lilith_memory.owner_proof import OwnerProofError, _digest, _exact, _id, _instant

from . import authority_contracts as A
from . import authority_ledger_journal as J
from . import recovery_contracts as R
from . import rotation_contracts as RC
from . import successor_custody as SC
from . import witness_readiness as WR
from .contracts import DEPLOYMENT_ENVIRONMENTS, ContractViolation, _choice


class _Reject(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _require(condition: bool, reason: str, detail: str | None = None) -> None:
    if not condition:
        raise _Reject(reason, detail)


# ------------------------------------------------------- witness profile ---

# Fixed by accepted records (B1b-3d §4, §6, §10; preflight §10, RR-36).
WITNESS_PROFILE = "DEV_SYNTHETIC"
WITNESS_KEY_ID = "test-only.witness.dev-synthetic.b1b3d.1"
WITNESS_CREDENTIAL_NAME = "recovery-witness-signing-key"
WITNESS_SERVICE_USER = "lilith-recovery-witness"
WITNESS_SERVICE_UNIT = "lilith-recovery-witness.service"
# RR-36: the separate root-only K-WIT credential source. The filename is the
# B1b-3d §15 basename (SOURCE DETAIL); the credstore path is superseded.
WITNESS_CREDENTIAL_ROOT = "/etc/lilith-recovery-witness/credentials"
WITNESS_BLOB_NAME = "lilith-recovery-witness.witness.cred"
WITNESS_CREDENTIAL_PATH = WITNESS_CREDENTIAL_ROOT + "/" + WITNESS_BLOB_NAME
SUPERSEDED_CREDSTORE_WITNESS_PATH = "/etc/credstore.encrypted/lilith-recovery-witness.witness.cred"
WITNESS_STATE_DIR = "/var/lib/lilith-recovery-witness"
WITNESS_RUNTIME_DIR = "/run/lilith-recovery-witness"
WITNESS_OWNER_SOCKET = WITNESS_RUNTIME_DIR + "/owner.sock"
WITNESS_SIGNER_SOCKET = WITNESS_RUNTIME_DIR + "/signer.sock"

# The authority signer identity K-WIT must never alias.
AUTHORITY_SERVICE_USER = "lilith-authority-dev"
AUTHORITY_SERVICE_UNIT = "lilith-authority-dev.service"
AUTHORITY_STATE_DIR = "/var/lib/lilith-authority-dev"


@dataclass(frozen=True)
class WitnessProfileV1:
    """The fixed RecoveryWitness identity. Logical contract, never authority."""

    profile: str
    environment: str
    witness_key_id: str
    credential_name: str
    credential_path: str
    service_user: str
    service_unit: str
    state_dir: str


DEV_SYNTHETIC_WITNESS_PROFILE = WitnessProfileV1(
    profile=WITNESS_PROFILE, environment="dev", witness_key_id=WITNESS_KEY_ID,
    credential_name=WITNESS_CREDENTIAL_NAME, credential_path=WITNESS_CREDENTIAL_PATH,
    service_user=WITNESS_SERVICE_USER, service_unit=WITNESS_SERVICE_UNIT, state_dir=WITNESS_STATE_DIR)

WITNESS_PROFILE_REASONS = (
    "WITNESS_PROFILE_MALFORMED",
    "WITNESS_PROFILE_PROD",
    "WITNESS_PROFILE_ALTERED",
    "WITNESS_KEY_ID_NOT_TEST_ONLY",
    "WITNESS_KEY_ID_IS_AUTHORITY_KEY_ID",
    "WITNESS_CREDENTIAL_NAME_IS_AUTHORITY_NAME",
    "WITNESS_CREDENTIAL_IN_AUTHORITY_CUSTODY",
    "WITNESS_ACCOUNT_IS_AUTHORITY_ACCOUNT",
    "WITNESS_STATE_IN_AUTHORITY_STATE",
)


def witness_profile_reason(profile: Any) -> str | None:
    """None only for the fixed DEV_SYNTHETIC witness profile, bound to one
    exact expected environment (never `prod`). Each K-ACT alias is refused by
    name, so an altered profile says which boundary it crossed."""
    if not isinstance(profile, WitnessProfileV1) or profile.environment not in DEPLOYMENT_ENVIRONMENTS:
        return "WITNESS_PROFILE_MALFORMED"
    if profile.environment == "prod":
        return "WITNESS_PROFILE_PROD"
    if profile.witness_key_id == SC.INITIAL_KEY_ID or SC.successor_ordinal_of_key_id(profile.witness_key_id) is not None:
        return "WITNESS_KEY_ID_IS_AUTHORITY_KEY_ID"
    if not isinstance(profile.witness_key_id, str) or not profile.witness_key_id.startswith(R.TEST_ONLY_WITNESS_PREFIX):
        return "WITNESS_KEY_ID_NOT_TEST_ONLY"
    if profile.credential_name == SC.CREDENTIAL_NAME:
        return "WITNESS_CREDENTIAL_NAME_IS_AUTHORITY_NAME"
    if not isinstance(profile.credential_path, str) or profile.credential_path.startswith(
            (SC.CREDSTORE_DIR + "/", SC.CUSTODY_ROOT + "/")) or profile.credential_path in (
            SC.CURRENT_PATH, SC.PREPARED_PATH, SC.RETIRED_PATH):
        return "WITNESS_CREDENTIAL_IN_AUTHORITY_CUSTODY"
    if profile.service_user == AUTHORITY_SERVICE_USER or profile.service_unit == AUTHORITY_SERVICE_UNIT:
        return "WITNESS_ACCOUNT_IS_AUTHORITY_ACCOUNT"
    if not isinstance(profile.state_dir, str) or profile.state_dir == AUTHORITY_STATE_DIR \
            or profile.state_dir.startswith(AUTHORITY_STATE_DIR + "/"):
        return "WITNESS_STATE_IN_AUTHORITY_STATE"
    if dataclasses.replace(profile, environment="dev") != DEV_SYNTHETIC_WITNESS_PROFILE:
        return "WITNESS_PROFILE_ALTERED"
    return None


def witness_profile(expected_environment: str) -> WitnessProfileV1:
    """The DEV_SYNTHETIC witness profile bound to one exact expected environment."""
    profile = dataclasses.replace(DEV_SYNTHETIC_WITNESS_PROFILE, environment=expected_environment)
    reason = witness_profile_reason(profile)
    if reason is not None:
        raise ContractViolation(reason)
    return profile


# -------------------------------------------------- witness publication ---

WITNESS_PUBLICATION_TYPE = "LILITH_WITNESS_KEY_PUBLICATION"
WITNESS_PUBLICATION_SCHEMA_VERSION = 1
_WITNESS_PUBLICATION_FIELDS = frozenset({"publicationType", "schemaVersion", "profile", "witnessKey",
                                         "custodyEvidence"})
_WITNESS_KEY_FIELDS = frozenset({"witnessKeyId", "environment", "algorithm", "publicKey", "publicKeySha256"})
_WITNESS_CUSTODY_FIELDS = frozenset({"credentialName", "credentialPath", "withKey", "machineId", "blobByteSize",
                                     "blobSha256"})


def _b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class WitnessKeyPublicationV1:
    """K-WIT's public keygen output. Public only; never a registry record."""

    witness_key_id: str
    environment: str
    public_key: bytes
    public_key_sha256: str
    credential_name: str
    credential_path: str
    blob_sha256: str

    @classmethod
    def from_dict(cls, value: Any) -> WitnessKeyPublicationV1:
        _exact(value, _WITNESS_PUBLICATION_FIELDS)
        if value["publicationType"] != WITNESS_PUBLICATION_TYPE or type(value["schemaVersion"]) is not int \
                or value["schemaVersion"] != WITNESS_PUBLICATION_SCHEMA_VERSION:
            raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
        if value["profile"] != WITNESS_PROFILE:
            raise ContractViolation("WITNESS_PUBLICATION_PROFILE")
        key, custody = value["witnessKey"], value["custodyEvidence"]
        _exact(key, _WITNESS_KEY_FIELDS)
        _exact(custody, _WITNESS_CUSTODY_FIELDS)
        if key["algorithm"] != A.ALGORITHM:
            raise ContractViolation("UNSUPPORTED_ALGORITHM")
        if custody["withKey"] != SC.KEY_PUBLICATION_WITH_KEY:
            raise ContractViolation("WITNESS_PUBLICATION_WITH_KEY")
        public_key = A._public_key(key["publicKey"])
        fingerprint = _digest(key["publicKeySha256"], "public_key_sha256")
        if hashlib.sha256(public_key).hexdigest() != fingerprint:
            raise ContractViolation("WITNESS_PUBLICATION_FINGERPRINT_INVALID")
        A._int(custody["blobByteSize"], "blob_byte_size", 1)
        return cls(_id(key["witnessKeyId"], "witness_key_id"),
                   _choice(key["environment"], DEPLOYMENT_ENVIRONMENTS, "environment"), public_key, fingerprint,
                   _id(custody["credentialName"], "credential_name"), str(custody["credentialPath"]),
                   _digest(custody["blobSha256"], "blob_sha256"))


def witness_publication(public_key: bytes, ciphertext: bytes, machine_id: str, *,
                        profile: WitnessProfileV1 = DEV_SYNTHETIC_WITNESS_PROFILE) -> dict[str, Any]:
    """The one K-WIT publication shape (what the keygen `witness` form prints)."""
    if not isinstance(public_key, bytes) or len(public_key) != 32:
        raise ContractViolation("WITNESS_PUBLIC_KEY_INVALID")
    if not isinstance(ciphertext, bytes) or not ciphertext:
        raise ContractViolation("WITNESS_CIPHERTEXT_INVALID")
    reason = witness_profile_reason(profile)
    if reason is not None:
        raise ContractViolation(reason)
    return {
        "publicationType": WITNESS_PUBLICATION_TYPE, "schemaVersion": WITNESS_PUBLICATION_SCHEMA_VERSION,
        "profile": WITNESS_PROFILE,
        "witnessKey": {"witnessKeyId": profile.witness_key_id, "environment": profile.environment,
                       "algorithm": A.ALGORITHM, "publicKey": _b64u(public_key),
                       "publicKeySha256": hashlib.sha256(public_key).hexdigest()},
        "custodyEvidence": {"credentialName": profile.credential_name, "credentialPath": profile.credential_path,
                            "withKey": SC.KEY_PUBLICATION_WITH_KEY, "machineId": machine_id,
                            "blobByteSize": len(ciphertext), "blobSha256": hashlib.sha256(ciphertext).hexdigest()},
    }


def witness_anchor_document(publication: WitnessKeyPublicationV1) -> dict[str, Any]:
    """The `TrustedWitnessAnchorV1` document a K-WIT publication implies."""
    return {"schemaVersion": 1, "witnessKeyId": publication.witness_key_id, "environment": publication.environment,
            "algorithm": A.ALGORITHM, "publicKey": _b64u(publication.public_key)}


def parse_publication_document(raw: Any) -> dict[str, Any]:
    """The keygen's exact stdout bytes (sorted keys, no whitespace, one newline)."""
    if not isinstance(raw, (bytes, bytearray)):
        raise ContractViolation("PUBLICATION_MALFORMED")
    try:
        value = json.loads(bytes(raw).decode("ascii"), object_pairs_hook=SC._no_duplicate_keys)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ContractViolation("PUBLICATION_MALFORMED") from exc
    if not isinstance(value, dict) or SC.canonical_publication_bytes(value) != bytes(raw):
        raise ContractViolation("PUBLICATION_NOT_CANONICAL")
    return value


# -------------------------------------------------------- distinctness ---

DISTINCTNESS_REASONS = (
    "DISTINCTNESS_INPUT_MALFORMED",
    "WITNESS_PUBLICATION_PROFILE_MISMATCH",
    "WITNESS_KEY_EQUALS_ACTOR_KEY",
    "WITNESS_KEY_EQUALS_ROOT_KEY",
    "WITNESS_KEY_ID_IN_REGISTRY",
    "WITNESS_KEY_IN_REGISTRY",
    "WITNESS_BLOB_EQUALS_ACTOR_BLOB",
    "WITNESS_ANCHOR_MISMATCH",
)


def witness_distinctness_reason(*, witness_publication: Any, actor_publication: Any,
                                registry: Mapping[str, Any] | None, registry_root: A.TrustedRegistryRootV1,
                                anchor: Any, profile: WitnessProfileV1 = DEV_SYNTHETIC_WITNESS_PROFILE) -> str | None:
    """Preflight §11: K-WIT fingerprint != K-ACT; K-WIT keyId and key not in
    registry v1; K-WIT != K-ROOT; blob hashes differ; the anchor names K-WIT
    and nothing else. Identical TEST keys fail here."""
    try:
        try:
            witness = WitnessKeyPublicationV1.from_dict(witness_publication)
            actor = RC.KeyPublicationV1.from_dict(actor_publication)
            parsed_anchor = R.TrustedWitnessAnchorV1.from_dict(anchor)
            parsed = A.AuthorityRegistryV1.from_verified_dict(registry)
        except (OwnerProofError, TypeError, KeyError) as exc:
            raise _Reject("DISTINCTNESS_INPUT_MALFORMED", getattr(exc, "code", None)) from exc
        _require(isinstance(registry_root, A.TrustedRegistryRootV1), "DISTINCTNESS_INPUT_MALFORMED")
        _require(witness_profile_reason(profile) is None and witness.witness_key_id == profile.witness_key_id
                 and witness.environment == profile.environment and witness.credential_name == profile.credential_name
                 and witness.credential_path == profile.credential_path, "WITNESS_PUBLICATION_PROFILE_MISMATCH")
        _require(witness.public_key != actor.public_key and witness.public_key_sha256 != actor.public_key_sha256,
                 "WITNESS_KEY_EQUALS_ACTOR_KEY")
        _require(witness.public_key != registry_root.public_key, "WITNESS_KEY_EQUALS_ROOT_KEY")
        _require(witness.witness_key_id not in parsed.keys, "WITNESS_KEY_ID_IN_REGISTRY")
        _require(all(record.public_key != witness.public_key for record in parsed.keys.values()),
                 "WITNESS_KEY_IN_REGISTRY")
        _require(witness.blob_sha256 != actor.blob_sha256, "WITNESS_BLOB_EQUALS_ACTOR_BLOB")
        _require((parsed_anchor.witness_key_id, parsed_anchor.environment, parsed_anchor.public_key)
                 == (witness.witness_key_id, witness.environment, witness.public_key), "WITNESS_ANCHOR_MISMATCH")
    except _Reject as rejected:
        return rejected.reason
    return None


# ------------------------------------------------ genesis candidate (RR-35) ---

GENESIS_CANDIDATE_REASONS = (
    "GENESIS_CANDIDATE_INPUT_MALFORMED",
    "GENESIS_PROFILE_INVALID",
    "GENESIS_REGISTRY_UNVERIFIED",
    "GENESIS_LEDGER_ABSENT",
    "GENESIS_LEDGER_INCONSISTENT",
    "GENESIS_LEDGER_ENVIRONMENT_MISMATCH",
    "GENESIS_LEDGER_NOT_INITIAL",
    "GENESIS_LEDGER_HEAD_MISMATCH",
    "GENESIS_LEDGER_REGISTRY_MISMATCH",
) + WR.GENESIS_REASONS


@dataclass(frozen=True)
class GenesisCandidateV1:
    """The exact unsigned V2 genesis (with `witnessKeyId`) and its digest.

    `digest` is `witness_v2_digest` of the future signed genesis: the signed
    fields exclude `signature`, so K-WIT signing this exact body preserves
    it. Candidate != genesis; the digest is compared with the owner pin.
    """

    status: str
    reason: str | None = None
    detail: str | None = None
    unsigned: Mapping[str, Any] | None = None
    digest: str | None = None
    expectation: WR.WitnessV2GenesisExpectationV1 | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)

    @property
    def built(self) -> bool:
        return self.status == "GENESIS_CANDIDATE_BUILT"


def candidate_digest(unsigned: Mapping[str, Any]) -> str:
    """SHA-256 of the V2 signed-field bytes (excludes `signature`)."""
    return hashlib.sha256(RC.witness_v2_signing_bytes(unsigned)).hexdigest()


def build_genesis_candidate(*, registry: Mapping[str, Any] | None, registry_root: A.TrustedRegistryRootV1,
                            ledger_observation: RC.AuthorityLedgerObservationV1 | None, updated_at: str,
                            profile: WitnessProfileV1 = DEV_SYNTHETIC_WITNESS_PROFILE) -> GenesisCandidateV1:
    """RR-35 steps 1-2, from exact inputs only.

    The ledger position is never caller-chosen: it must be the observed
    ledger at exactly sequence 1 whose head equals the GENESIS op registry v1
    implies, with a consistent journal, the registry's epoch and version, and
    the registry's current signing keys. A ledger that changed (sequence 2,
    another head) yields no candidate.
    """
    facts: dict[str, Any] = {"authorityGranted": False, "genesis": False, "pinned": False}
    try:
        _require(witness_profile_reason(profile) is None, "GENESIS_PROFILE_INVALID", witness_profile_reason(profile))
        _require(isinstance(registry, Mapping) and isinstance(registry_root, A.TrustedRegistryRootV1),
                 "GENESIS_CANDIDATE_INPUT_MALFORMED")
        try:
            _instant(updated_at)
            genesis_op = J.genesis_op(registry)
            sequence, head = J.initial_position(registry)
            epoch = A.RecoveryEpochV1.from_dict(registry["recoveryEpoch"])
            registry_head = RC.registry_head(registry)
        except (OwnerProofError, J.LedgerRefusal, TypeError, KeyError, ValueError) as exc:
            raise _Reject("GENESIS_CANDIDATE_INPUT_MALFORMED", getattr(exc, "reason", getattr(exc, "code", None))) \
                from exc
        facts.update(expectedLedgerSequence=sequence, expectedLedgerHead=head,
                     registryHead=registry_head.to_dict())
        observed = ledger_observation
        _require(observed is not None, "GENESIS_LEDGER_ABSENT")
        _require(isinstance(observed, RC.AuthorityLedgerObservationV1), "GENESIS_CANDIDATE_INPUT_MALFORMED")
        _require(observed.rows_consistent and not observed.terminal_reopened, "GENESIS_LEDGER_INCONSISTENT")
        _require(observed.environment == profile.environment == registry.get("environment"),
                 "GENESIS_LEDGER_ENVIRONMENT_MISMATCH")
        _require(observed.sequence == sequence, "GENESIS_LEDGER_NOT_INITIAL", str(observed.sequence))
        _require(observed.head == head, "GENESIS_LEDGER_HEAD_MISMATCH")
        _require(observed.recovery_epoch == epoch and observed.registry_view == registry_head.version
                 and tuple(observed.signing_key_ids) == tuple(genesis_op["signingKeyIds"]),
                 "GENESIS_LEDGER_REGISTRY_MISMATCH")
        expectation = WR.WitnessV2GenesisExpectationV1(
            environment=profile.environment, registry_head=registry_head, recovery_epoch=epoch,
            policy_version=registry["policyVersion"], ledger_sequence=sequence, ledger_head=head)
        plan = WR.plan_bound_witness_v2_genesis(expectation=expectation, registry=registry,
                                                registry_root=registry_root, updated_at=updated_at)
        _require(plan.planned, plan.reason if plan.reason in GENESIS_CANDIDATE_REASONS else "GENESIS_REGISTRY_UNVERIFIED",
                 plan.detail)
        unsigned = {**plan.successor_unsigned, "witnessKeyId": profile.witness_key_id}
        digest = candidate_digest(unsigned)
    except _Reject as rejected:
        return GenesisCandidateV1("GENESIS_CANDIDATE_REFUSED", rejected.reason, rejected.detail, facts=facts)
    facts["candidateDigest"] = digest
    return GenesisCandidateV1("GENESIS_CANDIDATE_BUILT", unsigned=unsigned, digest=digest, expectation=expectation,
                              facts=facts)


CANDIDATE_PIN_REASONS = ("GENESIS_PIN_MISSING", "GENESIS_PIN_MALFORMED", "GENESIS_PIN_ENVIRONMENT_MISMATCH",
                         "GENESIS_CANDIDATE_NOT_BUILT", "GENESIS_PIN_CANDIDATE_MISMATCH")


def candidate_pin_reason(pin: Mapping[str, Any] | None, candidate: GenesisCandidateV1, *,
                         environment: str) -> str | None:
    """RR-35 step 4: None only when the owner pin equals the candidate digest."""
    if pin is None:
        return "GENESIS_PIN_MISSING"
    try:
        parsed = WR.OwnerGenesisPinV1.from_dict(pin)
    except (OwnerProofError, TypeError):
        return "GENESIS_PIN_MALFORMED"
    if parsed.environment != environment:
        return "GENESIS_PIN_ENVIRONMENT_MISMATCH"
    if not isinstance(candidate, GenesisCandidateV1) or not candidate.built:
        return "GENESIS_CANDIDATE_NOT_BUILT"
    if parsed.genesis_witness_digest != candidate.digest:
        return "GENESIS_PIN_CANDIDATE_MISMATCH"
    return None
