"""15B2b-B1b-3e Source Prep A: witness durability, recovery, and readiness (TEST-ONLY).

Gate: docs/architecture/slice-15b2b-b1b3e-live-rehearsal-gate.md (SW-3 .. SW-8).
Record: docs/architecture/slice-15b2b-b1b3e-source-prep-a-witness-readiness.md.

Pure verifiers over caller-supplied observations. Nothing here reads a file,
the environment, a network, or a credential; nothing here holds a private key
or produces a signature. The TEST-only durable writer that applies these rules
to a storage port lives in the signer package.

The pieces, and what each one is NOT:

- `WitnessV2GenesisExpectationV1` / `verify_witness_v2_genesis` (SW-4): the
  owner-accepted bootstrap inputs and the check that a V2 genesis binds
  exactly them. Genesis creation != permission for any later head transition.
- `OwnerGenesisPinV1` (SW-8): an owner-held, off-host readiness input naming
  the accepted genesis digest. Not K-ROOT authority, not K-WIT freshness, not
  a registry, not an authorization, not an external monotonic head service.
  `genesis pinned != external monotonicity`.
- `OwnerAuthorizationRegisterV1` + `verify_authorization_history` (SW-7): the
  owner register of issued authorization digests and of every head registry,
  and independent K-ROOT re-verification of every authority-changing witness
  transition. Retained authorization bytes are story-4 evidence, never
  authority. `K-WIT assertion != K-ROOT authorization`.
- `classify_witness_store` (SW-5, RR-9 §6.3): the deterministic recovery
  scan. It never produces a witness, never uses K-WIT, never rolls backward,
  and never picks between candidates. `witness pointer != witness state`;
  `chain entry exists != committed transition`; `file exists / newest mtime
  != current`.
- `verify_credential_inventory` (SW-6, RR-19): root-observed slot
  inventory. `inventory result != authority`; it never selects a key.
- `verify_current_credential_binding` (SW-3, GC-3): the B1-B4 binding plus the
  fixed embedded credential name and "no other authority blob".
  `credential loaded != current authority`.
- `evaluate_witness_readiness`: every condition above, reported per check.
  `all readiness checks passing != live-entry authorization`.

Threat limit (unchanged): a witness protects only while it survives. A chain,
pointer, registry, and authority recovery ledger restored together are
`CONSISTENT` at an old head. Whole-host rollback is not detected here.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from lilith_memory.owner_proof import OwnerProofError, _digest, _exact, _id, _instant

from . import authority_contracts as A
from . import recovery_contracts as R
from . import rotation_contracts as RC
from .contracts import DEPLOYMENT_ENVIRONMENTS, ContractViolation, _canonical, _choice


class _Reject(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _require(condition: bool, reason: str, detail: str | None = None) -> None:
    if not condition:
        raise _Reject(reason, detail)


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _json(raw: Any) -> Any:
    if not isinstance(raw, (bytes, bytearray)) or not raw:
        raise ContractViolation("DOCUMENT_MALFORMED")
    try:
        return json.loads(bytes(raw).decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ContractViolation("DOCUMENT_MALFORMED") from exc


# ------------------------------------------------------------ stored bytes ---

def document_bytes(document: Mapping[str, Any]) -> bytes:
    """The one on-store byte form of a signed document: RFC 8785 JCS.

    Chain entries, the derived pointer, and retained authorizations are all
    stored in exactly this form, so "complete serialized bytes" is decidable:
    a truncated or re-encoded file never parses back to itself.
    """
    if not isinstance(document, Mapping):
        raise ContractViolation("DOCUMENT_MALFORMED")
    return _canonical(document)


def parse_document_bytes(raw: Any) -> dict[str, Any]:
    """Strict parse: one JSON object, no duplicate keys, canonical bytes only."""
    value = _json(raw)
    if not isinstance(value, dict) or _canonical(value) != bytes(raw):
        raise ContractViolation("DOCUMENT_MALFORMED")
    return value


def authorization_sha256(raw: bytes) -> str:
    """SHA-256 of exact retained authorization bytes (the owner register value)."""
    if not isinstance(raw, (bytes, bytearray)):
        raise ContractViolation("DOCUMENT_MALFORMED")
    return hashlib.sha256(bytes(raw)).hexdigest()


# ----------------------------------------------------------- store layout ---

# RR-9 §6.1. The state directory holds only these names. Filenames are
# naming only: they never decide authority, order, or currency.
CHAIN_DIRECTORY = "chain"
AUTHORIZATION_DIRECTORY = "authorizations"
POINTER_NAME = "witness.json"
POINTER_SCRATCH_NAME = ".witness.json.tmp"
LOCK_NAME = "witness.lock"

REGULAR = "REGULAR"
DIRECTORY = "DIRECTORY"
SYMLINK = "SYMLINK"
OTHER = "OTHER"
ABSENT = "ABSENT"
ENTRY_KINDS = frozenset({REGULAR, DIRECTORY, SYMLINK, OTHER})

STATE_ENTRY_KINDS = {CHAIN_DIRECTORY: DIRECTORY, AUTHORIZATION_DIRECTORY: DIRECTORY, POINTER_NAME: REGULAR,
                     POINTER_SCRATCH_NAME: REGULAR, LOCK_NAME: REGULAR}

_CHAIN_NAME = re.compile(r"([1-9][0-9]{0,15})\.json\Z")
_RETAINED_NAME = re.compile(r"[0-9a-f]{64}\.json\Z")


def chain_entry_name(witness_version: int) -> str:
    """`chain/<witnessVersion>.json`: one entry per version, created exclusively."""
    return f"{A._int(witness_version, 'witness_version', 1)}.json"


def retained_authorization_name(authorization_id: str) -> str:
    """A portable, deterministic name for one retained authorization.

    Derived from the authorization ID only. The recovery scan checks that the
    bytes inside name the same ID; the name never proves anything itself.
    """
    return hashlib.sha256(_id(authorization_id, "authorization_id").encode("utf-8")).hexdigest() + ".json"


@dataclass(frozen=True)
class StoreEntryV1:
    """One directory entry as observed (no following of links)."""

    name: str
    kind: str
    data: bytes | None = None  # regular files only


@dataclass(frozen=True)
class WitnessStoreObservationV1:
    """Story 4: one read of the witness state directory. Never authority.

    `chain_entries` and `authorization_entries` are empty when the directory
    is absent; the state listing says whether it exists.
    """

    state_entries: tuple[StoreEntryV1, ...]
    chain_entries: tuple[StoreEntryV1, ...] = ()
    authorization_entries: tuple[StoreEntryV1, ...] = ()


# ------------------------------------------------- V2 genesis (SW-4, RR-18) ---

@dataclass(frozen=True)
class WitnessV2GenesisExpectationV1:
    """The owner-accepted inputs a V2 genesis must bind exactly.

    Readiness / bootstrap input only. It names the accepted registry head,
    epoch, policy, and authority recovery ledger position; it authorizes no
    head transition and is not a registry.
    """

    environment: str
    registry_head: RC.RegistryHeadV1
    recovery_epoch: A.RecoveryEpochV1
    policy_version: str
    ledger_sequence: int
    ledger_head: str

    def validate(self) -> None:
        _choice(self.environment, DEPLOYMENT_ENVIRONMENTS, "environment")
        if not isinstance(self.registry_head, RC.RegistryHeadV1) or not isinstance(self.recovery_epoch,
                                                                                    A.RecoveryEpochV1):
            raise ContractViolation("INVALID_GENESIS_EXPECTATION")
        A._int(self.registry_head.version, "registry_version", 1)
        _digest(self.registry_head.digest, "registry_digest")
        _id(self.policy_version, "policy_version")
        A._int(self.ledger_sequence, "ledger_sequence", 1)
        _digest(self.ledger_head, "ledger_head")


GENESIS_VERIFIED = "GENESIS_VERIFIED"
GENESIS_NOT_VERIFIED = "GENESIS_NOT_VERIFIED"

# Closed, ordered genesis taxonomy.
GENESIS_REASONS = (
    "GENESIS_INPUT_MALFORMED",
    "GENESIS_NOT_GENESIS",
    "GENESIS_WITNESS_UNVERIFIED",
    "GENESIS_ENVIRONMENT_MISMATCH",
    "GENESIS_EPOCH_MISMATCH",
    "GENESIS_REGISTRY_VERSION_MISMATCH",
    "GENESIS_REGISTRY_DIGEST_MISMATCH",
    "GENESIS_POLICY_MISMATCH",
    "GENESIS_LEDGER_POSITION_MISMATCH",
    "GENESIS_REGISTRY_UNVERIFIED",
    "GENESIS_REGISTRY_NOT_SINGLE_CURRENT",
)


@dataclass(frozen=True)
class GenesisResultV1:
    status: str
    reason: str | None = None
    detail: str | None = None
    witness: RC.RecoveryWitnessV2 | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)

    @property
    def verified(self) -> bool:
        return self.status == GENESIS_VERIFIED


def genesis_expectation_reason(genesis: RC.RecoveryWitnessV2,
                               expectation: WitnessV2GenesisExpectationV1) -> str | None:
    """None when a parsed V2 witness is a genesis binding exactly `expectation`."""
    if genesis.witness_version != 1 or genesis.previous_witness_digest is not None \
            or genesis.consumed_authorization_id is not None:
        return "GENESIS_NOT_GENESIS"
    if genesis.environment != expectation.environment:
        return "GENESIS_ENVIRONMENT_MISMATCH"
    if genesis.current_recovery_epoch != expectation.recovery_epoch:
        return "GENESIS_EPOCH_MISMATCH"
    if genesis.registry_version != expectation.registry_head.version:
        return "GENESIS_REGISTRY_VERSION_MISMATCH"
    if genesis.registry_digest != expectation.registry_head.digest:
        return "GENESIS_REGISTRY_DIGEST_MISMATCH"
    if genesis.policy_version != expectation.policy_version:
        return "GENESIS_POLICY_MISMATCH"
    if (genesis.ledger_sequence, genesis.ledger_head) != (expectation.ledger_sequence, expectation.ledger_head):
        return "GENESIS_LEDGER_POSITION_MISMATCH"
    return None


def _genesis_registry(genesis: RC.RecoveryWitnessV2, registry: Any, registry_root: A.TrustedRegistryRootV1) -> None:
    at_head = RC.verify_registry_at_witness_head(witness=genesis, registry=registry, registry_root=registry_root)
    _require(at_head.verified, "GENESIS_REGISTRY_UNVERIFIED", at_head.reason)
    _require(RC.single_current_key_reason(at_head.registry) is None, "GENESIS_REGISTRY_NOT_SINGLE_CURRENT")


def plan_bound_witness_v2_genesis(*, expectation: WitnessV2GenesisExpectationV1, registry: Mapping[str, Any] | None,
                                  registry_root: A.TrustedRegistryRootV1, updated_at: str) -> RC.ExecutionPlanV1:
    """The unsigned V2 genesis for an owner `BOOTSTRAP`, bound to `expectation`.

    It reuses `rotation_contracts.plan_witness_v2_genesis` (registry verifies
    under K-ROOT at its own epoch; single current key) and then refuses
    unless every bound field equals the owner-accepted expectation. Genesis
    semantics: `witnessVersion = 1`, `previousWitnessDigest = null`,
    `consumedAuthorizationId = null`. No transition authorization is invented
    for genesis, and none is consumed.
    """
    try:
        try:
            _require(isinstance(expectation, WitnessV2GenesisExpectationV1), "GENESIS_INPUT_MALFORMED")
            expectation.validate()
        except OwnerProofError as exc:
            raise _Reject("GENESIS_INPUT_MALFORMED", exc.code) from exc
        plan = RC.plan_witness_v2_genesis(environment=expectation.environment, registry=registry,
                                          registry_root=registry_root, ledger_sequence=expectation.ledger_sequence,
                                          ledger_head=expectation.ledger_head, updated_at=updated_at)
        _require(plan.planned, "GENESIS_REGISTRY_UNVERIFIED", plan.detail or plan.reason)
        parsed = RC.RecoveryWitnessV2.from_verified_dict(
            {**plan.successor_unsigned, "witnessKeyId": "unsigned-plan", "signature": "unsigned-plan"})
        reason = genesis_expectation_reason(parsed, expectation)
        _require(reason is None, reason or "")
    except _Reject as rejected:
        return RC.ExecutionPlanV1(RC.REFUSED, rejected.reason, rejected.detail)
    return plan


def verify_witness_v2_genesis(*, anchor: R.TrustedWitnessAnchorV1, genesis: Mapping[str, Any] | None,
                              expectation: WitnessV2GenesisExpectationV1, registry: Mapping[str, Any] | None,
                              registry_root: A.TrustedRegistryRootV1,
                              authority_public_keys: frozenset[bytes] = frozenset()) -> GenesisResultV1:
    """Is `genesis` a K-WIT-signed V2 genesis binding exactly `expectation`,
    over a head registry that verifies under K-ROOT?

    A V1 document is refused (`UNSUPPORTED_SCHEMA_VERSION`): the live witness
    starts at V2 genesis (RR-18) and no V1 -> V2 migration exists.
    """
    try:
        try:
            _require(isinstance(expectation, WitnessV2GenesisExpectationV1) and isinstance(genesis, Mapping),
                     "GENESIS_INPUT_MALFORMED")
            expectation.validate()
        except OwnerProofError as exc:
            raise _Reject("GENESIS_INPUT_MALFORMED", exc.code) from exc
        # Genesis shape is refused before anything is trusted.
        _require(genesis.get("witnessVersion") == 1 and genesis.get("previousWitnessDigest") is None
                 and genesis.get("consumedAuthorizationId") is None, "GENESIS_NOT_GENESIS")
        checked = RC.verify_recovery_witness_v2(anchor=anchor, witness=genesis, environment=expectation.environment,
                                                registry_root=registry_root,
                                                authority_public_keys=authority_public_keys)
        _require(checked.verified, "GENESIS_WITNESS_UNVERIFIED", checked.reason)
        parsed = checked.witness
        reason = genesis_expectation_reason(parsed, expectation)
        _require(reason is None, reason or "")
        _genesis_registry(parsed, registry, registry_root)
    except _Reject as rejected:
        return GenesisResultV1(GENESIS_NOT_VERIFIED, rejected.reason, rejected.detail)
    return GenesisResultV1(GENESIS_VERIFIED, witness=parsed, facts={
        "genesisWitnessDigest": parsed.digest,
        "registryHead": parsed.registry_head.to_dict(),
        "authorityGranted": False,
        "headTransitionPermitted": False,
    })


# -------------------------------------------- owner genesis pin (SW-8, RR-21) ---

GENESIS_PIN_TYPE = "LILITH_RECOVERY_WITNESS_V2_GENESIS_PIN"
GENESIS_PIN_SCHEMA_VERSION = 1
GENESIS_PIN_FIELDS = frozenset({"pinType", "schemaVersion", "environment", "genesisWitnessDigest"})


@dataclass(frozen=True)
class OwnerGenesisPinV1:
    """The owner's off-host record of the accepted V2 genesis digest.

    Deliberately unsigned and minimal: the accepted design defines no
    authority-bearing contract for it, so none is invented. Its integrity
    comes from owner custody off-host. It anchors the accepted genesis
    lineage only: not K-ROOT authority, not K-WIT freshness, not a registry,
    not a transition authorization, not an external monotonic head.
    """

    environment: str
    genesis_witness_digest: str

    @classmethod
    def from_dict(cls, value: Any) -> OwnerGenesisPinV1:
        _exact(value, GENESIS_PIN_FIELDS)
        if value["pinType"] != GENESIS_PIN_TYPE or type(value["schemaVersion"]) is not int \
                or value["schemaVersion"] != GENESIS_PIN_SCHEMA_VERSION:
            raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
        return cls(_choice(value["environment"], DEPLOYMENT_ENVIRONMENTS, "environment"),
                   _digest(value["genesisWitnessDigest"], "genesis_witness_digest"))

    def to_dict(self) -> dict[str, Any]:
        return {"pinType": GENESIS_PIN_TYPE, "schemaVersion": GENESIS_PIN_SCHEMA_VERSION,
                "environment": self.environment, "genesisWitnessDigest": self.genesis_witness_digest}


GENESIS_PIN_REASONS = ("GENESIS_PIN_MISSING", "GENESIS_PIN_MALFORMED", "GENESIS_PIN_ENVIRONMENT_MISMATCH",
                       "GENESIS_NOT_GENESIS", "GENESIS_MISMATCH")


def genesis_pin_reason(pin: Mapping[str, Any] | None, genesis: RC.RecoveryWitnessV2, *,
                       environment: str) -> str | None:
    """None when the computed genesis digest equals the owner-pinned digest.

    `genesis` must already be a verified V2 witness; the pin never substitutes
    for its K-WIT signature (the digest excludes the signature), for any
    K-ROOT authorization, or for any later witness.
    """
    if pin is None:
        return "GENESIS_PIN_MISSING"
    try:
        parsed = OwnerGenesisPinV1.from_dict(pin)
    except (OwnerProofError, TypeError):
        return "GENESIS_PIN_MALFORMED"
    if not isinstance(genesis, RC.RecoveryWitnessV2):
        return "GENESIS_NOT_GENESIS"
    if parsed.environment != environment or genesis.environment != environment:
        return "GENESIS_PIN_ENVIRONMENT_MISMATCH"
    if genesis.witness_version != 1 or genesis.previous_witness_digest is not None:
        return "GENESIS_NOT_GENESIS"
    if genesis.digest != parsed.genesis_witness_digest:
        return "GENESIS_MISMATCH"
    return None


# ------------------------------- owner authorization register (SW-7, RR-20a) ---

REGISTRY_HEAD_ADVANCE = "REGISTRY_HEAD_ADVANCE"
EPOCH_ADVANCE = "EPOCH_ADVANCE"
AUTHORIZATION_KINDS = {REGISTRY_HEAD_ADVANCE: RC.REGISTRY_HEAD_ADVANCE_AUTHORIZATION_PROTOCOL,
                       EPOCH_ADVANCE: RC.EPOCH_ADVANCE_AUTHORIZATION_PROTOCOL}

REGISTER_TYPE = "LILITH_OWNER_AUTHORIZATION_REGISTER"
REGISTER_SCHEMA_VERSION = 1
REGISTER_FIELDS = frozenset({"registerType", "schemaVersion", "environment", "authorizations", "headRegistries"})
_REGISTER_AUTHORIZATION_FIELDS = frozenset({"authorizationId", "kind", "authorizationSha256"})
_REGISTER_HEAD_FIELDS = frozenset({"registryVersion", "registryDigest"})


@dataclass(frozen=True)
class OwnerAuthorizationRegisterV1:
    """The owner's off-host register (RR-20a §6.8 item 1), as a readiness input.

    - `authorizations`: every issued K-ROOT transition authorization ID
      (executed or not), its kind, and the SHA-256 of its exact signed bytes.
      One ID maps to exactly one digest.
    - `head_registries`: every registry generation that became a witness-bound
      head, genesis included. One version maps to exactly one digest.

    The register is reproducibility / provenance evidence. It is not an
    authority root and it authorizes nothing; K-ROOT signatures do that.
    """

    environment: str
    authorizations: Mapping[str, tuple[str, str]]
    head_registries: frozenset[RC.RegistryHeadV1]

    @classmethod
    def from_dict(cls, value: Any) -> OwnerAuthorizationRegisterV1:
        _exact(value, REGISTER_FIELDS)
        if value["registerType"] != REGISTER_TYPE or type(value["schemaVersion"]) is not int \
                or value["schemaVersion"] != REGISTER_SCHEMA_VERSION:
            raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
        if not isinstance(value["authorizations"], list) or not isinstance(value["headRegistries"], list):
            raise ContractViolation("INVALID_REGISTER")
        authorizations: dict[str, tuple[str, str]] = {}
        for item in value["authorizations"]:
            _exact(item, _REGISTER_AUTHORIZATION_FIELDS)
            authorization_id = _id(item["authorizationId"], "authorization_id")
            if authorization_id in authorizations:
                raise ContractViolation("REGISTER_AUTHORIZATION_ID_DUPLICATED")
            authorizations[authorization_id] = (_choice(item["kind"], frozenset(AUTHORIZATION_KINDS), "kind"),
                                                _digest(item["authorizationSha256"], "authorization_sha256"))
        heads: dict[int, str] = {}
        for item in value["headRegistries"]:
            _exact(item, _REGISTER_HEAD_FIELDS)
            version = A._int(item["registryVersion"], "registry_version", 1)
            if version in heads:
                raise ContractViolation("REGISTER_HEAD_VERSION_DUPLICATED")
            heads[version] = _digest(item["registryDigest"], "registry_digest")
        return cls(_choice(value["environment"], DEPLOYMENT_ENVIRONMENTS, "environment"), authorizations,
                   frozenset(RC.RegistryHeadV1(v, d) for v, d in heads.items()))


VERIFIED_HISTORY = "VERIFIED_AUTHORIZATION_HISTORY"
HISTORY_NOT_VERIFIED = "AUTHORIZATION_HISTORY_NOT_VERIFIED"

# Closed, ordered authorization-history taxonomy.
AUTHORIZATION_HISTORY_REASONS = (
    "HISTORY_INPUT_MALFORMED",
    "REGISTER_MISSING",
    "REGISTER_MALFORMED",
    "REGISTER_ENVIRONMENT_MISMATCH",
    "HEAD_NOT_REGISTERED",
    "AUTHORIZATION_REPLAYED",
    "RETAINED_AUTHORIZATION_MISSING",
    "AUTHORIZATION_NOT_REGISTERED",
    "RETAINED_AUTHORIZATION_DIGEST_MISMATCH",
    "RETAINED_AUTHORIZATION_MALFORMED",
    "TRANSITION_TYPE_MISMATCH",
    "AUTHORIZATION_NOT_VERIFIED",
    "AUTHORIZATION_ID_MISMATCH",
    "PRIOR_WITNESS_MISMATCH",
    "PRIOR_HEAD_MISMATCH",
    "TARGET_HEAD_MISMATCH",
    "EPOCH_MISMATCH",
    "AUTHORIZATION_NOT_YET_VALID",
    "AUTHORIZATION_EXPIRED",
)


@dataclass(frozen=True)
class AuthorizationHistoryResultV1:
    status: str
    reason: str | None = None
    detail: str | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)

    @property
    def verified(self) -> bool:
        return self.status == VERIFIED_HISTORY


def parse_owner_register(register: Any) -> OwnerAuthorizationRegisterV1:
    """The register as an owner input (a mapping) or already parsed."""
    if isinstance(register, OwnerAuthorizationRegisterV1):
        return register
    return OwnerAuthorizationRegisterV1.from_dict(register)


def _transition_authorization(previous: RC.RecoveryWitnessV2, entry: RC.RecoveryWitnessV2, raw: bytes, *,
                              register: OwnerAuthorizationRegisterV1, registry_root: A.TrustedRegistryRootV1) -> str:
    authorization_id = entry.consumed_authorization_id
    registered = register.authorizations.get(authorization_id)
    _require(registered is not None, "AUTHORIZATION_NOT_REGISTERED")
    kind, registered_sha256 = registered
    _require(authorization_sha256(raw) == registered_sha256, "RETAINED_AUTHORIZATION_DIGEST_MISMATCH")
    try:
        document = parse_document_bytes(raw)
    except OwnerProofError as exc:
        raise _Reject("RETAINED_AUTHORIZATION_MALFORMED") from exc
    epoch_changed = R.compare_epochs(previous.current_recovery_epoch, entry.current_recovery_epoch) != R.EPOCH_EQUAL
    expected_kind = EPOCH_ADVANCE if epoch_changed else REGISTRY_HEAD_ADVANCE
    _require(kind == expected_kind and document.get("protocol") == AUTHORIZATION_KINDS[expected_kind],
             "TRANSITION_TYPE_MISMATCH", expected_kind)
    if epoch_changed:
        checked = RC.verify_epoch_advance_authorization(authorization=document, registry_root=registry_root,
                                                        environment=entry.environment)
    else:
        checked = RC.verify_registry_head_advance_authorization(authorization=document, registry_root=registry_root,
                                                                environment=entry.environment)
    _require(checked.verified, "AUTHORIZATION_NOT_VERIFIED", checked.reason)
    auth = checked.authorization
    _require(auth.authorization_id == authorization_id, "AUTHORIZATION_ID_MISMATCH")
    if epoch_changed:
        _require(auth.expected_prior_witness_version == previous.witness_version
                 and auth.expected_prior_witness_digest == previous.digest, "PRIOR_WITNESS_MISMATCH")
        _require(auth.target == entry.registry_head, "TARGET_HEAD_MISMATCH")
        _require(auth.prior_recovery_epoch == previous.current_recovery_epoch
                 and auth.successor_recovery_epoch == entry.current_recovery_epoch, "EPOCH_MISMATCH")
    else:
        _require(auth.prior == previous.registry_head, "PRIOR_HEAD_MISMATCH")
        _require(auth.target == entry.registry_head, "TARGET_HEAD_MISMATCH")
        _require(auth.recovery_epoch == previous.current_recovery_epoch == entry.current_recovery_epoch,
                 "EPOCH_MISMATCH")
    # Defence in depth only: the replay boundary is the chain binding above.
    _require(entry.updated_at >= auth.issued_at, "AUTHORIZATION_NOT_YET_VALID")
    _require(entry.updated_at <= auth.not_after, "AUTHORIZATION_EXPIRED")
    return expected_kind


def verify_authorization_history(*, chain: RC.WitnessChainFactsV1, retained: Mapping[str, bytes],
                                 register: Any, registry_root: A.TrustedRegistryRootV1) -> AuthorizationHistoryResultV1:
    """RR-20a: re-verify the K-ROOT authorization behind every transition entry.

    `chain` is a verified linear V2 chain. For each entry with a non-null
    `consumedAuthorizationId`, the on-host retained copy (`retained`, keyed by
    authorization ID) must exist, its SHA-256 must equal the owner register,
    its bytes must verify under the pinned K-ROOT, and its fields must bind
    both sides of the transition: head advance (prior head = predecessor
    head, target = entry head, epoch = both entries' epoch) or epoch advance
    (expected prior witness = predecessor, prior / successor epoch = the two
    entries' epochs, target = entry head). Every head the chain ever held must
    be in the register. A valid K-WIT chain alone never passes.
    """
    try:
        _require(isinstance(chain, RC.WitnessChainFactsV1) and isinstance(retained, Mapping)
                 and isinstance(registry_root, A.TrustedRegistryRootV1), "HISTORY_INPUT_MALFORMED")
        _require(register is not None, "REGISTER_MISSING")
        try:
            owner = parse_owner_register(register)
        except (OwnerProofError, TypeError) as exc:
            raise _Reject("REGISTER_MALFORMED", getattr(exc, "code", None)) from exc
        _require(owner.environment == chain.head.environment, "REGISTER_ENVIRONMENT_MISMATCH")
        for witness in chain.witnesses:
            _require(witness.registry_head in owner.head_registries, "HEAD_NOT_REGISTERED",
                     f"{witness.witness_version}:{witness.registry_version}")
        seen: set[str] = set()
        transitions = []
        for previous, entry in zip(chain.witnesses, chain.witnesses[1:]):
            authorization_id = entry.consumed_authorization_id
            if authorization_id is None:
                continue
            detail = f"{entry.witness_version}:{authorization_id}"
            try:
                _require(authorization_id not in seen, "AUTHORIZATION_REPLAYED")
                seen.add(authorization_id)
                raw = retained.get(authorization_id)
                _require(raw is not None, "RETAINED_AUTHORIZATION_MISSING")
                kind = _transition_authorization(previous, entry, raw, register=owner, registry_root=registry_root)
            except _Reject as rejected:
                raise _Reject(rejected.reason, detail if rejected.detail is None else f"{detail}:{rejected.detail}")
            transitions.append({"witnessVersion": entry.witness_version, "authorizationId": authorization_id,
                                "kind": kind})
    except _Reject as rejected:
        return AuthorizationHistoryResultV1(HISTORY_NOT_VERIFIED, rejected.reason, rejected.detail)
    return AuthorizationHistoryResultV1(VERIFIED_HISTORY, facts={
        "verifiedTransitions": transitions,
        "unexecutedRetained": sorted(set(retained) - seen),
        "authorityGranted": False,
    })


# ------------------------------------------------ recovery scan (SW-5, RR-9) ---

UNINITIALIZED = "UNINITIALIZED"
CONSISTENT = "CONSISTENT"
POINTER_BEHIND_BY_ONE = "POINTER_BEHIND_BY_ONE"
POINTER_MISSING = "POINTER_MISSING"
POINTER_CORRUPT = "POINTER_CORRUPT"
POINTER_BEHIND_MULTI = "POINTER_BEHIND_MULTI"
POINTER_AHEAD = "POINTER_AHEAD"
FORK = "FORK"
CHAIN_CORRUPT = "CHAIN_CORRUPT"
TORN_TAIL = "TORN_TAIL"
ORPHAN = "ORPHAN"
REPLAY_IN_CHAIN = "REPLAY_IN_CHAIN"
AUTHORIZATION_HISTORY_INVALID = "AUTHORIZATION_HISTORY_INVALID"
GENESIS_MISMATCH = "GENESIS_MISMATCH"
CHAIN_MISSING = "CHAIN_MISSING"
SCRATCH_ORDERING_VIOLATION = "SCRATCH_ORDERING_VIOLATION"
UNEXPECTED_ENTRY = "UNEXPECTED_ENTRY"
RETENTION_CORRUPT = "RETENTION_CORRUPT"
RECOVERY_INPUT_INVALID = "RECOVERY_INPUT_INVALID"

# Closed classification set: RR-9 §6.3 names, plus the discovery / input
# refusals the gate's R1 requires ("unexpected names -> fail closed").
RECOVERY_CLASSIFICATIONS = (
    UNINITIALIZED, CONSISTENT, POINTER_BEHIND_BY_ONE, POINTER_MISSING, POINTER_CORRUPT, POINTER_BEHIND_MULTI,
    POINTER_AHEAD, FORK, CHAIN_CORRUPT, TORN_TAIL, ORPHAN, REPLAY_IN_CHAIN, AUTHORIZATION_HISTORY_INVALID,
    GENESIS_MISMATCH, CHAIN_MISSING, SCRATCH_ORDERING_VIOLATION, UNEXPECTED_ENTRY, RETENTION_CORRUPT,
    RECOVERY_INPUT_INVALID,
)

NO_ACTION = "NO_ACTION"
ROLL_FORWARD = "ROLL_FORWARD"
OWNER_BOOTSTRAP_REQUIRED = "OWNER_BOOTSTRAP_REQUIRED"
FAIL_CLOSED = "FAIL_CLOSED"
RECOVERY_DECISIONS = (NO_ACTION, ROLL_FORWARD, OWNER_BOOTSTRAP_REQUIRED, FAIL_CLOSED)

# The only automatic outcomes (RR-9 §6.5). Everything else is owner work.
_AUTOMATIC = {CONSISTENT: NO_ACTION, POINTER_BEHIND_BY_ONE: ROLL_FORWARD, POINTER_MISSING: ROLL_FORWARD,
              POINTER_CORRUPT: ROLL_FORWARD, UNINITIALIZED: OWNER_BOOTSTRAP_REQUIRED}


@dataclass(frozen=True)
class WitnessStoreContextV1:
    """Everything the scan verifies against, all owner- or root-supplied.

    `genesis_pin` and `owner_register` are off-host owner inputs (SW-8,
    SW-7). None of these values are authority for a new transition.
    """

    anchor: R.TrustedWitnessAnchorV1
    environment: str
    registry_root: A.TrustedRegistryRootV1
    genesis_pin: Mapping[str, Any] | None = None
    owner_register: Any = None
    authority_public_keys: frozenset[bytes] = frozenset()


@dataclass(frozen=True)
class WitnessRecoveryResultV1:
    """The scan outcome. `decision` is the only action the store may take."""

    classification: str
    decision: str
    detail: str | None = None
    head: RC.RecoveryWitnessV2 | None = None
    head_bytes: bytes | None = None
    discard_scratch: bool = False
    genesis: RC.RecoveryWitnessV2 | None = None
    chain: RC.WitnessChainFactsV1 | None = None
    retained: Mapping[str, bytes] = field(default_factory=dict)
    facts: Mapping[str, Any] = field(default_factory=dict)

    @property
    def fail_closed(self) -> bool:
        return self.decision == FAIL_CLOSED


class _Outcome(Exception):
    def __init__(self, classification: str, detail: str | None = None):
        super().__init__(classification)
        self.classification = classification
        self.detail = detail


def _witness(raw: bytes, context: WitnessStoreContextV1, *, canonical: bool) -> tuple[RC.RecoveryWitnessV2 | None, str]:
    """(parsed, reason) for one stored witness document; parsed is None when INVALID."""
    try:
        document = parse_document_bytes(raw) if canonical else _json(raw)
    except OwnerProofError:
        return None, "DOCUMENT_MALFORMED"
    checked = RC.verify_recovery_witness_v2(anchor=context.anchor, witness=document, environment=context.environment,
                                            registry_root=context.registry_root,
                                            authority_public_keys=context.authority_public_keys)
    if not checked.verified:
        return None, checked.reason or "WITNESS_NOT_VERIFIED"
    return checked.witness, "VALID"


def _discover(observation: WitnessStoreObservationV1) -> tuple[bytes | None, bytes | None]:
    names: set[str] = set()
    pointer = scratch = None
    for entry in observation.state_entries:
        _outcome_unless(isinstance(entry, StoreEntryV1) and entry.kind in ENTRY_KINDS, UNEXPECTED_ENTRY, "state")
        _outcome_unless(entry.name not in names and STATE_ENTRY_KINDS.get(entry.name) == entry.kind,
                        UNEXPECTED_ENTRY, entry.name)
        names.add(entry.name)
        if entry.name == POINTER_NAME:
            pointer = entry.data if entry.data is not None else b""
        elif entry.name == POINTER_SCRATCH_NAME:
            scratch = entry.data if entry.data is not None else b""
    for directory, entries, pattern in ((CHAIN_DIRECTORY, observation.chain_entries, _CHAIN_NAME),
                                        (AUTHORIZATION_DIRECTORY, observation.authorization_entries, _RETAINED_NAME)):
        _outcome_unless(directory in names or not entries, RECOVERY_INPUT_INVALID, directory)
        seen: set[str] = set()
        for entry in entries:
            _outcome_unless(isinstance(entry, StoreEntryV1) and entry.kind == REGULAR and entry.name not in seen
                            and pattern.fullmatch(entry.name) is not None and isinstance(entry.data, bytes),
                            UNEXPECTED_ENTRY, f"{directory}/{getattr(entry, 'name', '?')}")
            seen.add(entry.name)
    return pointer, scratch


def _outcome_unless(condition: bool, classification: str, detail: str | None = None) -> None:
    if not condition:
        raise _Outcome(classification, detail)


def _retained(observation: WitnessStoreObservationV1) -> dict[str, bytes]:
    retained: dict[str, bytes] = {}
    for entry in observation.authorization_entries:
        try:
            document = parse_document_bytes(entry.data)
            authorization_id = _id(document.get("authorizationId"), "authorization_id")
        except OwnerProofError as exc:
            raise _Outcome(RETENTION_CORRUPT, entry.name) from exc
        _outcome_unless(retained_authorization_name(authorization_id) == entry.name and authorization_id not in retained,
                        RETENTION_CORRUPT, entry.name)
        retained[authorization_id] = entry.data
    return retained


def classify_witness_store(*, observation: WitnessStoreObservationV1,
                           context: WitnessStoreContextV1) -> WitnessRecoveryResultV1:
    """RR-9 §6.3 recovery scan: R1 discover .. R7 decide. Pure and deterministic.

    Never mtime, never filename order, never "last file wins": the head is the
    end of the digest-linked lineage from the owner-pinned genesis, and the
    pointer is compared to it byte for byte. The only automatic decisions are
    NO_ACTION and ROLL_FORWARD to a unique, fully verified head (pointer one
    behind, missing, or corrupt). Everything ambiguous fails closed.
    """
    facts: dict[str, Any] = {"entries": [], "producesWitness": False, "usesWitnessKey": False,
                             "rollbackDetectionScope": R.ROLLBACK_DETECTION_SCOPE,
                             "wholeHostRollbackProtected": R.WHOLE_HOST_ROLLBACK_PROTECTED}
    genesis: RC.RecoveryWitnessV2 | None = None
    chain_facts: RC.WitnessChainFactsV1 | None = None
    retained: dict[str, bytes] = {}
    head_raw: bytes | None = None
    lineage: list[RC.RecoveryWitnessV2] = []
    discard = False
    try:
        _outcome_unless(isinstance(observation, WitnessStoreObservationV1)
                        and isinstance(context, WitnessStoreContextV1)
                        and isinstance(context.anchor, R.TrustedWitnessAnchorV1)
                        and isinstance(context.registry_root, A.TrustedRegistryRootV1)
                        and context.environment in DEPLOYMENT_ENVIRONMENTS, RECOVERY_INPUT_INVALID, "context")
        # R1 DISCOVER
        pointer, scratch = _discover(observation)
        facts.update(pointerPresent=pointer is not None, scratchPresent=scratch is not None,
                     pointerSha256=None if pointer is None else hashlib.sha256(pointer).hexdigest())
        if not observation.chain_entries:
            _outcome_unless(pointer is None and scratch is None and not observation.authorization_entries,
                            CHAIN_MISSING)
            raise _Outcome(UNINITIALIZED)
        # Owner inputs: missing or malformed pin / register fail closed (SW-8, SW-7).
        _outcome_unless(context.genesis_pin is not None, RECOVERY_INPUT_INVALID, "GENESIS_PIN_MISSING")
        try:
            pin = OwnerGenesisPinV1.from_dict(context.genesis_pin)
        except (OwnerProofError, TypeError) as exc:
            raise _Outcome(RECOVERY_INPUT_INVALID, "GENESIS_PIN_MALFORMED") from exc
        facts["genesisDigestPinned"] = pin.genesis_witness_digest
        _outcome_unless(context.owner_register is not None, RECOVERY_INPUT_INVALID, "REGISTER_MISSING")
        try:
            parse_owner_register(context.owner_register)
        except (OwnerProofError, TypeError) as exc:
            raise _Outcome(RECOVERY_INPUT_INVALID, "REGISTER_MALFORMED") from exc
        # R2 VERIFY each entry alone (filename number must equal witnessVersion).
        entries: dict[int, tuple[bytes, RC.RecoveryWitnessV2 | None]] = {}
        for entry in observation.chain_entries:
            version = int(_CHAIN_NAME.fullmatch(entry.name).group(1))
            parsed, reason = _witness(entry.data, context, canonical=True)
            if parsed is not None and parsed.witness_version != version:
                parsed, reason = None, "FILENAME_VERSION_MISMATCH"
            entries[version] = (entry.data, parsed)
            facts["entries"].append({"witnessVersion": version, "valid": parsed is not None, "result": reason,
                                     "digest": None if parsed is None else parsed.digest})
        facts["entries"].sort(key=lambda item: item["witnessVersion"])
        # R3 LINEAGE from the owner-pinned genesis.
        _outcome_unless(1 in entries, ORPHAN, "GENESIS_ABSENT")
        genesis = entries[1][1]
        _outcome_unless(genesis is not None, CHAIN_CORRUPT, "1:GENESIS_INVALID")
        facts["genesisDigestObserved"] = genesis.digest
        pin_reason = genesis_pin_reason(context.genesis_pin, genesis, environment=context.environment)
        _outcome_unless(pin_reason is None, GENESIS_MISMATCH, pin_reason)
        lineage = [genesis]
        top = max(entries)
        torn_at = None
        for version in range(2, top + 1):
            _outcome_unless(version in entries, ORPHAN, f"GAP:{version}")
            parsed = entries[version][1]
            if parsed is None:
                _outcome_unless(version == top, CHAIN_CORRUPT, str(version))
                torn_at = version
                break
            reason = RC.witness_v2_succession_reason(lineage[-1], parsed)
            _outcome_unless(reason is None, ORPHAN, f"{version}:{reason}")
            lineage.append(parsed)
        head = lineage[-1]
        head_raw = entries[head.witness_version][0]
        facts.update(headWitnessVersion=head.witness_version, headDigest=head.digest,
                     chainLength=len(entries))
        if torn_at is not None:
            # INVALID only at H+1 with the pointer still at H: not committed.
            _outcome_unless(pointer == head_raw, CHAIN_CORRUPT, f"{torn_at}:TAIL")
            raise _Outcome(TORN_TAIL, str(torn_at))
        # R4 FACTS and the authorization history.
        chain_result = RC.witness_v2_chain_facts(lineage)
        if not chain_result.verified:
            raise _Outcome(REPLAY_IN_CHAIN if chain_result.reason == "CHAIN_AUTHORIZATION_REPLAYED"
                           else CHAIN_CORRUPT, chain_result.detail or chain_result.reason)
        chain_facts = chain_result.facts
        retained = _retained(observation)
        history = verify_authorization_history(chain=chain_facts, retained=retained, register=context.owner_register,
                                               registry_root=context.registry_root)
        facts["authorizationHistory"] = history.reason or history.status
        _outcome_unless(history.verified, AUTHORIZATION_HISTORY_INVALID,
                        f"{history.reason}:{history.detail}" if history.detail else history.reason)
        facts["unexecutedRetainedAuthorizations"] = list(history.facts["unexecutedRetained"])
        # R5 HEAD is `head`; R6 POINTER / scratch compared with it.
        by_digest = {w.digest: w.witness_version for w in lineage}
        raws = {w.witness_version: entries[w.witness_version][0] for w in lineage}
        classification = _pointer_class(pointer, head, raws, by_digest, context)
        _outcome_unless(classification in _AUTOMATIC, classification)
        if scratch is not None:
            discard = _scratch_is_discardable(scratch, head, raws, by_digest, context)
        raise _Outcome(classification)
    except _Outcome as outcome:
        decision = _AUTOMATIC.get(outcome.classification, FAIL_CLOSED)
        discard_scratch = decision in {NO_ACTION, ROLL_FORWARD} and discard
        facts["classification"] = outcome.classification
        head = lineage[-1] if lineage else None
        return WitnessRecoveryResultV1(outcome.classification, decision, outcome.detail,
                                       head=head, head_bytes=head_raw if head is not None else None,
                                       discard_scratch=bool(discard_scratch), genesis=genesis, chain=chain_facts,
                                       retained=dict(retained), facts=facts)


def _pointer_class(pointer: bytes | None, head: RC.RecoveryWitnessV2, raws: Mapping[int, bytes],
                   by_digest: Mapping[str, int], context: WitnessStoreContextV1) -> str:
    if pointer is None:
        return POINTER_MISSING
    if pointer == raws[head.witness_version]:
        return CONSISTENT
    if head.witness_version > 1 and pointer == raws[head.witness_version - 1]:
        return POINTER_BEHIND_BY_ONE
    if pointer in raws.values():
        return POINTER_BEHIND_MULTI
    parsed, _ = _witness(pointer, context, canonical=False)
    if parsed is None:
        return POINTER_CORRUPT
    known = by_digest.get(parsed.digest)
    if known is not None:
        # A re-encoded copy of a chain entry: derived state, rewritten from H,
        # unless it names a head more than one behind.
        if known >= head.witness_version - 1:
            return POINTER_CORRUPT
        return POINTER_BEHIND_MULTI
    if parsed.witness_version <= head.witness_version:
        return FORK
    return POINTER_AHEAD


def _scratch_is_discardable(scratch: bytes, head: RC.RecoveryWitnessV2, raws: Mapping[int, bytes],
                            by_digest: Mapping[str, int], context: WitnessStoreContextV1) -> bool:
    if scratch in raws.values():
        return True
    parsed, _ = _witness(scratch, context, canonical=False)
    if parsed is None or parsed.digest in by_digest:
        return True
    if parsed.witness_version <= head.witness_version:
        raise _Outcome(FORK, "scratch")
    raise _Outcome(SCRATCH_ORDERING_VIOLATION, str(parsed.witness_version))


# ------------------------------------------------ registry history (readiness) ---

REGISTRY_HISTORY_VERIFIED = "REGISTRY_HISTORY_VERIFIED"
REGISTRY_HISTORY_REASONS = ("REGISTRY_HISTORY_INPUT_MALFORMED", "REGISTRY_MISSING", "REGISTRY_UNVERIFIED",
                            "REGISTRY_NOT_SINGLE_CURRENT", "REGISTRY_SUCCESSION_INVALID")


def verify_head_registry_history(*, chain: RC.WitnessChainFactsV1, registries: Sequence[Mapping[str, Any]],
                                 registry_root: A.TrustedRegistryRootV1) -> tuple[str | None, str | None]:
    """(reason, detail); (None, None) when every head the chain ever held has
    registry bytes that verify under K-ROOT at that entry, and every head
    change is an additive `verify_registry_succession` step (RR-20a §6.8)."""
    try:
        _require(isinstance(chain, RC.WitnessChainFactsV1) and isinstance(registries, (list, tuple)),
                 "REGISTRY_HISTORY_INPUT_MALFORMED")
        by_digest: dict[str, Mapping[str, Any]] = {}
        for registry in registries:
            try:
                by_digest.setdefault(RC.registry_digest(registry), registry)
            except (OwnerProofError, TypeError, KeyError) as exc:
                raise _Reject("REGISTRY_HISTORY_INPUT_MALFORMED") from exc
        previous: RC.RecoveryWitnessV2 | None = None
        for witness in chain.witnesses:
            detail = str(witness.witness_version)
            registry = by_digest.get(witness.registry_digest)
            _require(registry is not None, "REGISTRY_MISSING", detail)
            at_head = RC.verify_registry_at_witness_head(witness=witness, registry=registry,
                                                         registry_root=registry_root)
            _require(at_head.verified, "REGISTRY_UNVERIFIED", f"{detail}:{at_head.reason}")
            _require(RC.single_current_key_reason(at_head.registry) is None, "REGISTRY_NOT_SINGLE_CURRENT", detail)
            if previous is not None and previous.registry_head != witness.registry_head:
                succession = RC.verify_registry_succession(by_digest[previous.registry_digest], registry,
                                                           trusted_head=previous.registry_head)
                _require(succession.succeeds, "REGISTRY_SUCCESSION_INVALID", f"{detail}:{succession.reason}")
            previous = witness
    except _Reject as rejected:
        return rejected.reason, rejected.detail
    return None, None


# --------------------------------------------- credential inventory (SW-6) ---

@dataclass(frozen=True)
class CredentialSlotContractV1:
    """The credential-slot contract a profile fixes. Logical, not authority.

    Only the CURRENT slot has a fixed path under current source (SF-1, SF-3).
    The PREPARED and RETIRED locations are logical roles: their paths and the
    successor's embedded name are open details of the successor-capable
    release (RR-11-D1, RR-11-D2, SW-2) and are deliberately not fixed here.
    """

    unit_name: str
    credential_name: str
    credstore_directory: str
    current_slot_name: str
    owner_uid: int = 0
    owner_gid: int = 0
    blob_mode: int = 0o600
    directory_mode: int = 0o700

    @property
    def current_slot_path(self) -> str:
        return self.credstore_directory + "/" + self.current_slot_name


# The DEV_SYNTHETIC values of current source (authority-dev profile, keygen,
# and signer unit); a test pins them against those files.
DEV_SYNTHETIC_SLOT_CONTRACT = CredentialSlotContractV1(
    unit_name="lilith-authority-dev.service", credential_name="owner-actor-signing-key",
    credstore_directory="/etc/credstore.encrypted", current_slot_name="lilith-authority-dev.owner-actor.cred")

CREDSTORE = "CREDSTORE"   # holds exactly the CURRENT slot, the only unit-loadable one
PREPARED = "PREPARED"     # at most one successor blob; referenced by no unit
RETIRED = "RETIRED"       # the predecessor between cutover and retirement
LOCATION_ROLES = (CREDSTORE, PREPARED, RETIRED)

# Gate §11 phases -> (CURRENT, PREPARED, RETIRED) blob counts.
STEADY = "STEADY"                           # L3e-0..2, and after L3e-12
SUCCESSOR_PREPARED = "SUCCESSOR_PREPARED"   # L3e-3..7
CUTOVER_VACATED = "CUTOVER_VACATED"         # L3e-8a
CUTOVER_INSTALLED = "CUTOVER_INSTALLED"     # L3e-8b..11
INVENTORY_PHASES = {STEADY: (1, 0, 0), SUCCESSOR_PREPARED: (1, 1, 0), CUTOVER_VACATED: (0, 1, 1),
                    CUTOVER_INSTALLED: (1, 0, 1)}
# Phases in which the single CURRENT blob may satisfy issuance readiness.
READINESS_INVENTORY_PHASES = frozenset({STEADY, CUTOVER_INSTALLED})


@dataclass(frozen=True)
class CredentialFileObservationV1:
    """One root-observed entry (lstat; no decryption; no link following)."""

    name: str
    kind: str
    uid: int | None
    gid: int | None
    mode: int | None
    sha256: str | None


@dataclass(frozen=True)
class CredentialLocationObservationV1:
    role: str
    kind: str  # DIRECTORY, ABSENT, or anything else observed at that path
    uid: int | None = None
    gid: int | None = None
    mode: int | None = None
    entries: tuple[CredentialFileObservationV1, ...] = ()


@dataclass(frozen=True)
class CredentialInventoryObservationV1:
    """Story 4: one root-observed credential-slot inventory. Never authority."""

    locations: tuple[CredentialLocationObservationV1, ...]


INVENTORY_VERIFIED = "INVENTORY_VERIFIED"
INVENTORY_NOT_VERIFIED = "INVENTORY_NOT_VERIFIED"

# Closed, ordered inventory taxonomy.
INVENTORY_REASONS = (
    "INVENTORY_INPUT_MALFORMED",
    "INVENTORY_PHASE_UNKNOWN",
    "UNEXPECTED_LOCATION",
    "CREDSTORE_MISSING",
    "LOCATION_NOT_DIRECTORY",
    "LOCATION_OWNER_MISMATCH",
    "LOCATION_GROUP_MISMATCH",
    "LOCATION_MODE_MISMATCH",
    "CREDENTIAL_ENTRY_NOT_REGULAR",
    "CREDENTIAL_OWNER_MISMATCH",
    "CREDENTIAL_GROUP_MISMATCH",
    "CREDENTIAL_MODE_MISMATCH",
    "CREDENTIAL_HASH_UNOBSERVED",
    "UNEXPECTED_CREDENTIAL_BLOB",
    "CURRENT_SLOT_MISSING",
    "CURRENT_SLOT_NOT_PERMITTED",
    "PREPARED_SLOT_MISSING",
    "PREPARED_SLOT_NOT_PERMITTED",
    "MULTIPLE_PREPARED_CANDIDATES",
    "RETIRED_SLOT_MISSING",
    "RETIRED_SLOT_NOT_PERMITTED",
    "MULTIPLE_RETIRED_BLOBS",
    "DUPLICATE_CREDENTIAL_BLOB",
)


@dataclass(frozen=True)
class InventoryResultV1:
    status: str
    reason: str | None = None
    detail: str | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)

    @property
    def verified(self) -> bool:
        return self.status == INVENTORY_VERIFIED


def _location_metadata(location: CredentialLocationObservationV1, contract: CredentialSlotContractV1) -> None:
    _require(location.kind == DIRECTORY, "LOCATION_NOT_DIRECTORY", location.role)
    _require(location.uid == contract.owner_uid, "LOCATION_OWNER_MISMATCH", location.role)
    _require(location.gid == contract.owner_gid, "LOCATION_GROUP_MISMATCH", location.role)
    _require(location.mode == contract.directory_mode, "LOCATION_MODE_MISMATCH", location.role)
    for entry in location.entries:
        detail = f"{location.role}/{entry.name}"
        _require(entry.kind == REGULAR, "CREDENTIAL_ENTRY_NOT_REGULAR", detail)
        _require(entry.uid == contract.owner_uid, "CREDENTIAL_OWNER_MISMATCH", detail)
        _require(entry.gid == contract.owner_gid, "CREDENTIAL_GROUP_MISMATCH", detail)
        _require(entry.mode == contract.blob_mode, "CREDENTIAL_MODE_MISMATCH", detail)
        try:
            _digest(entry.sha256, "sha256")
        except OwnerProofError as exc:
            raise _Reject("CREDENTIAL_HASH_UNOBSERVED", detail) from exc


def verify_credential_inventory(*, inventory: CredentialInventoryObservationV1 | None, phase: str,
                                contract: CredentialSlotContractV1 = DEV_SYNTHETIC_SLOT_CONTRACT) -> InventoryResultV1:
    """RR-19: is the observed credential-slot inventory exactly what `phase` permits?

    Fail closed on: a missing credstore; a non-directory or wrongly owned /
    moded location; any non-regular entry (symlink, directory, special
    file); wrong owner, group, or mode; any credstore name other than the
    fixed CURRENT slot; a CURRENT / PREPARED / RETIRED count the phase does not
    permit (including a second prepared candidate); or two slots holding the
    same blob. A verified result never selects the authoritative key: it only
    reports the single CURRENT blob hash for the binding to compare.
    """
    facts: dict[str, Any] = {"phase": phase, "authorityGranted": False, "selectsAuthoritativeKey": False}
    try:
        _require(isinstance(inventory, CredentialInventoryObservationV1)
                 and isinstance(contract, CredentialSlotContractV1)
                 and all(isinstance(loc, CredentialLocationObservationV1) for loc in inventory.locations)
                 and all(isinstance(e, CredentialFileObservationV1)
                         for loc in inventory.locations for e in loc.entries), "INVENTORY_INPUT_MALFORMED")
        _require(phase in INVENTORY_PHASES, "INVENTORY_PHASE_UNKNOWN")
        by_role: dict[str, CredentialLocationObservationV1] = {}
        for location in inventory.locations:
            _require(location.role in LOCATION_ROLES and location.role not in by_role, "UNEXPECTED_LOCATION",
                     str(location.role))
            by_role[location.role] = location
        credstore = by_role.get(CREDSTORE)
        _require(credstore is not None and credstore.kind != ABSENT, "CREDSTORE_MISSING")
        blobs: dict[str, list[str]] = {}
        for role in LOCATION_ROLES:
            location = by_role.get(role)
            if location is None or location.kind == ABSENT:
                _require(not (location and location.entries), "INVENTORY_INPUT_MALFORMED", role)
                blobs[role] = []
                continue
            _location_metadata(location, contract)
            blobs[role] = [entry.sha256 for entry in location.entries]
        for entry in credstore.entries:
            _require(entry.name == contract.current_slot_name, "UNEXPECTED_CREDENTIAL_BLOB", entry.name)
        current, prepared, retired = INVENTORY_PHASES[phase]
        _require(len(blobs[CREDSTORE]) >= current, "CURRENT_SLOT_MISSING")
        _require(len(blobs[CREDSTORE]) <= current, "CURRENT_SLOT_NOT_PERMITTED")
        _require(len(blobs[PREPARED]) <= 1, "MULTIPLE_PREPARED_CANDIDATES")
        _require(len(blobs[PREPARED]) >= prepared, "PREPARED_SLOT_MISSING")
        _require(len(blobs[PREPARED]) <= prepared, "PREPARED_SLOT_NOT_PERMITTED")
        _require(len(blobs[RETIRED]) <= 1, "MULTIPLE_RETIRED_BLOBS")
        _require(len(blobs[RETIRED]) >= retired, "RETIRED_SLOT_MISSING")
        _require(len(blobs[RETIRED]) <= retired, "RETIRED_SLOT_NOT_PERMITTED")
        every = [digest for role in LOCATION_ROLES for digest in blobs[role]]
        _require(len(every) == len(set(every)), "DUPLICATE_CREDENTIAL_BLOB")
    except _Reject as rejected:
        return InventoryResultV1(INVENTORY_NOT_VERIFIED, rejected.reason, rejected.detail, facts)
    facts.update(currentSlotSha256=blobs[CREDSTORE][0] if blobs[CREDSTORE] else None,
                 preparedSha256=blobs[PREPARED][0] if blobs[PREPARED] else None,
                 retiredSha256=blobs[RETIRED][0] if blobs[RETIRED] else None,
                 loadableBlobs=len(blobs[CREDSTORE]))
    return InventoryResultV1(INVENTORY_VERIFIED, facts=facts)


# ---------------------------------------- GC-3 credential binding (SW-3) ---

LOAD_CREDENTIAL_ENCRYPTED = "LoadCredentialEncrypted"


@dataclass(frozen=True)
class UnitCredentialReferenceV1:
    directive: str
    credential_name: str
    source_path: str


@dataclass(frozen=True)
class UnitCredentialObservationV1:
    """Story 4: every credential directive root observed in the signer unit
    (`LoadCredential*=`, `SetCredential*=`, `ImportCredential=`), as given."""

    unit_name: str
    references: tuple[UnitCredentialReferenceV1, ...]


# The RR-14 binding taxonomy plus the GC-3 conditions (design §11.2).
CREDENTIAL_BINDING_REASONS = RC.BINDING_REASONS + (
    "UNIT_MISMATCH",
    "UNIT_CREDENTIAL_REFERENCES_UNEXPECTED",
    "UNIT_CREDENTIAL_DIRECTIVE_UNEXPECTED",
    "CREDENTIAL_NAME_MISMATCH",
    "UNIT_CREDENTIAL_PATH_MISMATCH",
    "PUBLICATION_CREDENTIAL_NAME_MISMATCH",
    "CREDENTIAL_INVENTORY_NOT_VERIFIED",
    "CREDENTIAL_INVENTORY_PHASE_NOT_READY",
    "INVENTORY_CURRENT_BLOB_MISMATCH",
)


def verify_current_credential_binding(*, registry_root: A.TrustedRegistryRootV1, witness: RC.RecoveryWitnessV2 | None,
                                      head_registry: Mapping[str, Any] | None, signing_domain: str,
                                      evidence_type: str, observed_blob_sha256: str | None,
                                      publication: Mapping[str, Any] | None, health: Mapping[str, Any] | None,
                                      unit_credentials: UnitCredentialObservationV1 | None,
                                      inventory: CredentialInventoryObservationV1 | None, inventory_phase: str,
                                      contract: CredentialSlotContractV1 = DEV_SYNTHETIC_SLOT_CONTRACT,
                                      ) -> RC.BindingResultV1:
    """GC-3 / SW-3: the RR-14 B1-B4 binding plus the two design §11.2
    conditions it did not implement (SF-8):

    - **fixed embedded credential name.** The signer unit references exactly
      one credential, by `LoadCredentialEncrypted=`, under the contract's
      fixed name, from the contract's CURRENT slot path; and the ceremony
      publication records that the blob was encrypted under that same name
      (`custodyEvidence.credentialName`). systemd decrypts an encrypted
      credential only under the name embedded at encryption, so a blob minted
      under another name cannot be delivered as this one;
    - **no other authority blob.** The RR-19 inventory verifies for a phase in
      which the CURRENT blob may be ready, and its single CURRENT blob hash
      equals B2.

    Both are readiness inputs (story 4), never authority. A positive result
    still reports `authorityGranted: false`.
    """
    try:
        _require(unit_credentials is not None, "BINDING_INPUT_MISSING", "B5_UNIT_CREDENTIALS")
        _require(inventory is not None, "BINDING_INPUT_MISSING", "B6_CREDENTIAL_INVENTORY")
        _require(isinstance(unit_credentials, UnitCredentialObservationV1)
                 and all(isinstance(r, UnitCredentialReferenceV1) for r in unit_credentials.references)
                 and isinstance(contract, CredentialSlotContractV1), "BINDING_INPUT_MALFORMED", "B5_UNIT_CREDENTIALS")
        base = RC.verify_loaded_key_binding(registry_root=registry_root, witness=witness, head_registry=head_registry,
                                            signing_domain=signing_domain, evidence_type=evidence_type,
                                            observed_blob_sha256=observed_blob_sha256, publication=publication,
                                            health=health)
        _require(base.verified, base.reason or "BINDING_INPUT_MALFORMED", base.detail)
        _require(unit_credentials.unit_name == contract.unit_name, "UNIT_MISMATCH")
        _require(len(unit_credentials.references) == 1, "UNIT_CREDENTIAL_REFERENCES_UNEXPECTED",
                 str(len(unit_credentials.references)))
        reference = unit_credentials.references[0]
        _require(reference.directive == LOAD_CREDENTIAL_ENCRYPTED, "UNIT_CREDENTIAL_DIRECTIVE_UNEXPECTED")
        _require(reference.credential_name == contract.credential_name, "CREDENTIAL_NAME_MISMATCH")
        _require(reference.source_path == contract.current_slot_path, "UNIT_CREDENTIAL_PATH_MISMATCH")
        custody = publication.get("custodyEvidence")
        _require(isinstance(custody, Mapping) and custody.get("credentialName") == contract.credential_name,
                 "PUBLICATION_CREDENTIAL_NAME_MISMATCH")
        slots = verify_credential_inventory(inventory=inventory, phase=inventory_phase, contract=contract)
        _require(slots.verified, "CREDENTIAL_INVENTORY_NOT_VERIFIED", slots.reason)
        _require(inventory_phase in READINESS_INVENTORY_PHASES, "CREDENTIAL_INVENTORY_PHASE_NOT_READY",
                 inventory_phase)
        _require(slots.facts["currentSlotSha256"] == observed_blob_sha256, "INVENTORY_CURRENT_BLOB_MISMATCH")
    except _Reject as rejected:
        return RC.BindingResultV1(RC.BINDING_NOT_VERIFIED, rejected.reason, rejected.detail)
    return RC.BindingResultV1(RC.BINDING_VERIFIED, facts={
        **base.facts,
        "credentialName": contract.credential_name,
        "unitCredentialReferences": 1,
        "inventoryPhase": inventory_phase,
        "otherAuthorityBlobsInCredstore": 0,
        "independentInputs": ["B1", "B2", "B3", "B5", "B6"],
        "authorityGranted": False,
    })


# ------------------------------------------------ readiness aggregation ---

PASS = "PASS"
FAIL = "FAIL"
NOT_EVALUATED = "NOT_EVALUATED"
READY = "READY"
NOT_READY = "NOT_READY"

# Every condition is its own check; none is omitted because another looks
# equivalent.
READINESS_CHECKS = (
    "WITNESS_CHAIN",
    "GENESIS_PIN",
    "AUTHORIZATION_HISTORY",
    "HEAD_REGISTRY",
    "REGISTRY_HISTORY",
    "SINGLE_CURRENT_KEY",
    "AUTHORITY_LEDGER_POSITION",
    "CREDENTIAL_INVENTORY",
    "LOADED_KEY_BINDING",
    "CEREMONY_HOLD",
)


@dataclass(frozen=True)
class CheckOutcomeV1:
    status: str
    reason: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class WitnessReadinessInputsV1:
    """Everything issuance readiness considers. Every item is story-4 input
    until the check that names it verifies it."""

    environment: str
    signing_domain: str
    evidence_type: str
    store: WitnessStoreContextV1
    witness_store: WitnessStoreObservationV1
    head_registries: tuple[Mapping[str, Any], ...]
    ledger_observation: RC.AuthorityLedgerObservationV1 | None
    observed_blob_sha256: str | None
    publication: Mapping[str, Any] | None
    health: Mapping[str, Any] | None
    unit_credentials: UnitCredentialObservationV1 | None
    credential_inventory: CredentialInventoryObservationV1 | None
    inventory_phase: str
    hold_present: bool | None
    slot_contract: CredentialSlotContractV1 = DEV_SYNTHETIC_SLOT_CONTRACT


@dataclass(frozen=True)
class WitnessReadinessResultV1:
    status: str
    reasons: tuple[str, ...]
    checks: Mapping[str, CheckOutcomeV1]
    facts: Mapping[str, Any]

    @property
    def ready(self) -> bool:
        return self.status == READY


def _registry_for(head: RC.RecoveryWitnessV2, registries: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    for registry in registries:
        try:
            if RC.registry_digest(registry) == head.registry_digest:
                return registry
        except (OwnerProofError, TypeError, KeyError):
            continue
    return None


def evaluate_witness_readiness(inputs: WitnessReadinessInputsV1) -> WitnessReadinessResultV1:
    """Pure, fail-closed issuance readiness over the B1b-3e witness state.

    Each check in `READINESS_CHECKS` is reported with its own closed reason.
    Checks that need a verified witness head are NOT_EVALUATED without one,
    which is itself NOT_READY. Readers never repair: a stale pointer is
    `WITNESS_POINTER_STALE` here, and only the witness's own recovery may roll
    it forward. READY never grants authority and never authorizes live entry.
    """
    checks: dict[str, CheckOutcomeV1] = {}

    def record(name: str, reason: str | None, detail: str | None = None) -> None:
        checks[name] = CheckOutcomeV1(PASS) if reason is None else CheckOutcomeV1(FAIL, reason, detail)

    def skip(name: str, detail: str) -> None:
        checks[name] = CheckOutcomeV1(NOT_EVALUATED, "PREREQUISITE_NOT_VERIFIED", detail)

    facts: dict[str, Any] = {"authorityGranted": False, "liveEntryAuthorized": False, "issuanceReady": False,
                             "rollbackDetectionScope": R.ROLLBACK_DETECTION_SCOPE,
                             "wholeHostRollbackProtected": R.WHOLE_HOST_ROLLBACK_PROTECTED}
    if not isinstance(inputs, WitnessReadinessInputsV1) or not isinstance(inputs.store, WitnessStoreContextV1):
        checks = {name: CheckOutcomeV1(FAIL, "MALFORMED_INPUT") for name in READINESS_CHECKS}
        return WitnessReadinessResultV1(NOT_READY, tuple(f"{n}:MALFORMED_INPUT" for n in READINESS_CHECKS),
                                        checks, facts)
    recovery = classify_witness_store(observation=inputs.witness_store, context=inputs.store)
    facts["witnessClassification"] = recovery.classification
    if recovery.classification == CONSISTENT:
        record("WITNESS_CHAIN", None)
    elif recovery.classification in {POINTER_BEHIND_BY_ONE, POINTER_MISSING, POINTER_CORRUPT}:
        record("WITNESS_CHAIN", "WITNESS_POINTER_STALE", recovery.classification)
    else:
        record("WITNESS_CHAIN", recovery.classification, recovery.detail)

    if recovery.genesis is None:
        skip("GENESIS_PIN", "WITNESS_CHAIN")
    else:
        record("GENESIS_PIN", genesis_pin_reason(inputs.store.genesis_pin, recovery.genesis,
                                                 environment=inputs.environment))

    chain = recovery.chain
    if chain is None:
        for name in READINESS_CHECKS[2:7] + ("LOADED_KEY_BINDING",):
            skip(name, "WITNESS_CHAIN")
    else:
        head = chain.head
        facts["witnessedHead"] = head.registry_head.to_dict()
        history = verify_authorization_history(chain=chain, retained=recovery.retained,
                                               register=inputs.store.owner_register,
                                               registry_root=inputs.store.registry_root)
        record("AUTHORIZATION_HISTORY", history.reason, history.detail)
        head_registry = _registry_for(head, inputs.head_registries)
        at_head = RC.verify_registry_at_witness_head(witness=head, registry=head_registry,
                                                     registry_root=inputs.store.registry_root)
        record("HEAD_REGISTRY", at_head.reason, at_head.detail)
        record("REGISTRY_HISTORY", *verify_head_registry_history(chain=chain, registries=inputs.head_registries,
                                                                 registry_root=inputs.store.registry_root))
        if at_head.verified:
            single = RC.single_current_key_reason(at_head.registry)
            if single is None:
                try:
                    RC.select_current_issuance_key(at_head.registry, inputs.signing_domain, inputs.evidence_type)
                except OwnerProofError as exc:
                    single = exc.code
            record("SINGLE_CURRENT_KEY", single)
        else:
            skip("SINGLE_CURRENT_KEY", "HEAD_REGISTRY")
        if inputs.ledger_observation is None:
            record("AUTHORITY_LEDGER_POSITION", "LEDGER_OBSERVATION_ABSENT")
        else:
            record("AUTHORITY_LEDGER_POSITION", RC.authority_ledger_position_reason(inputs.ledger_observation, head))
        binding = verify_current_credential_binding(
            registry_root=inputs.store.registry_root, witness=head, head_registry=head_registry,
            signing_domain=inputs.signing_domain, evidence_type=inputs.evidence_type,
            observed_blob_sha256=inputs.observed_blob_sha256, publication=inputs.publication, health=inputs.health,
            unit_credentials=inputs.unit_credentials, inventory=inputs.credential_inventory,
            inventory_phase=inputs.inventory_phase, contract=inputs.slot_contract)
        record("LOADED_KEY_BINDING", binding.reason, binding.detail)
        if binding.verified:
            facts["loadedKeyBinding"] = dict(binding.facts)

    slots = verify_credential_inventory(inventory=inputs.credential_inventory, phase=inputs.inventory_phase,
                                        contract=inputs.slot_contract)
    if slots.verified and inputs.inventory_phase not in READINESS_INVENTORY_PHASES:
        record("CREDENTIAL_INVENTORY", "CREDENTIAL_INVENTORY_PHASE_NOT_READY", inputs.inventory_phase)
    else:
        record("CREDENTIAL_INVENTORY", slots.reason, slots.detail)

    if inputs.hold_present is None:
        record("CEREMONY_HOLD", "CEREMONY_HOLD_UNOBSERVED")
    else:
        record("CEREMONY_HOLD", "CEREMONY_HOLD_PRESENT" if inputs.hold_present else None)

    ordered = {name: checks[name] for name in READINESS_CHECKS}
    reasons = tuple(f"{name}:{outcome.reason}" for name, outcome in ordered.items() if outcome.status != PASS)
    ready = not reasons
    facts["issuanceReady"] = ready
    return WitnessReadinessResultV1(READY if ready else NOT_READY, reasons, ordered, facts)
