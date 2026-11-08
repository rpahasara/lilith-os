"""Versioned memory-action contract layer for the families beyond the project codename.

`canonical_contracts` stays byte-identical: it is a governed shared module of the signer and broker releases
(sha256 f93d26d8...). Codename actions keep using its unchanged `FrozenMemoryActionV1`, so their meaning and every
digest are unchanged. This module adds a closed set of versioned families on top, each exactly one tuple, one purpose,
one capability, one value schema and one epistemic basis. Every family is CREATE (FORGET stays Privacy-owned); the
relationship-origin family also allows an owner-approved SUPERSEDE (a corrected successor revision of the same item,
bound to the active revision it replaces; schema v4, `relationship_origin_correction_migration`):

- FM-02 First Interaction: purpose `OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION`, capability
  `canonical_memory.first_interaction.create`, basis `RECORDED_INTERACTION`, value schema `FirstInteractionEpisodeV1`,
  tuple (`OWNER_DIRECTED_FIRST_INTERACTION`, `lilith.core.autobiographical`, `episode.first-interaction`). Its identity
  is permanently suppressed (F9c2 FORGET); the family exists so that suppression and erasure stay exact.
- Relationship origin: purpose `LONG_TERM_OWNER_RELATIONSHIP_ORIGIN_RECALL`, capability
  `canonical_memory.relationship_origin.create`, basis `USER_ASSERTED` (the owner's own words, never a transcript or an
  inference), value schema `OwnerRelationshipOriginV1`, tuple (`OWNER_PROVIDED_RELATIONSHIP_ORIGIN`,
  `lilith.core.relationship`, `origin.owner-statement`), sensitivity `OWNER_PERSONAL`.

A family action subclasses `FrozenMemoryActionV1` without new fields: `semantic_dict` and `action_digest` are
inherited, so the encoding is identical. Its `validate` runs the unchanged base `validate` on a codename-purpose copy
(the only purpose-dependent base check is the purpose allowlist) and then applies the family rules. Build every action
through `action_from_fields`: it returns the family subclass for a family purpose, the unchanged class otherwise, and
refuses a family tuple under any other purpose.

Nothing here activates a family. The canonical config, the tuple registry and the signer's own purpose allowlist each
gate it separately.
"""

from __future__ import annotations

import dataclasses
from types import MappingProxyType
from typing import Any, Mapping, Optional, Tuple

try:
    from . import canonical_contracts as C
except ImportError:  # deploy-exact flat-directory tests
    import canonical_contracts as C


USER_ASSERTED = "USER_ASSERTED"
RECORDED_INTERACTION = "RECORDED_INTERACTION"
OWNER_PERSONAL = "OWNER_PERSONAL"
PROJECT_FACT = "PROJECT_FACT"


@dataclasses.dataclass(frozen=True)
class VersionedFamilyV1:
    """One closed versioned family. `label` names it in refusals; `table_prefix` names its L18 tables."""

    label: str
    purpose: str
    capability: str
    identity: Tuple[str, str, str]
    value_schema: str
    epistemic_basis: str
    sensitivity: str
    proposal_family: str
    descriptor_family: str
    table_prefix: str
    # Value-bearing L04 operations the family admits (Privacy FORGET is always separate). CREATE only unless widened.
    operations: frozenset = frozenset({C.CREATE})


OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION = "OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION"
CANONICAL_MEMORY_FIRST_INTERACTION_CREATE = "canonical_memory.first_interaction.create"
FIRST_INTERACTION_IDENTITY = (
    "OWNER_DIRECTED_FIRST_INTERACTION",
    "lilith.core.autobiographical",
    "episode.first-interaction",
)
FIRST_INTERACTION_VALUE_SCHEMA = "FirstInteractionEpisodeV1"

LONG_TERM_OWNER_RELATIONSHIP_ORIGIN_RECALL = "LONG_TERM_OWNER_RELATIONSHIP_ORIGIN_RECALL"
CANONICAL_MEMORY_RELATIONSHIP_ORIGIN_CREATE = "canonical_memory.relationship_origin.create"
RELATIONSHIP_ORIGIN_IDENTITY = (
    "OWNER_PROVIDED_RELATIONSHIP_ORIGIN",
    "lilith.core.relationship",
    "origin.owner-statement",
)
RELATIONSHIP_ORIGIN_VALUE_SCHEMA = "OwnerRelationshipOriginV1"

FIRST_INTERACTION = VersionedFamilyV1(
    label="First Interaction", purpose=OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION,
    capability=CANONICAL_MEMORY_FIRST_INTERACTION_CREATE, identity=FIRST_INTERACTION_IDENTITY,
    value_schema=FIRST_INTERACTION_VALUE_SCHEMA, epistemic_basis=RECORDED_INTERACTION, sensitivity=OWNER_PERSONAL,
    proposal_family="OWNER_DIRECTED_FIRST_INTERACTION_V1", descriptor_family="FIRST_INTERACTION_V1",
    table_prefix="learning_fi")
RELATIONSHIP_ORIGIN = VersionedFamilyV1(
    label="Relationship origin", purpose=LONG_TERM_OWNER_RELATIONSHIP_ORIGIN_RECALL,
    capability=CANONICAL_MEMORY_RELATIONSHIP_ORIGIN_CREATE, identity=RELATIONSHIP_ORIGIN_IDENTITY,
    value_schema=RELATIONSHIP_ORIGIN_VALUE_SCHEMA, epistemic_basis=USER_ASSERTED, sensitivity=OWNER_PERSONAL,
    proposal_family="OWNER_DIRECTED_RELATIONSHIP_ORIGIN_V1", descriptor_family="RELATIONSHIP_ORIGIN_V1",
    table_prefix="learning_ro", operations=frozenset({C.CREATE, C.SUPERSEDE}))
VERSIONED_FAMILIES = (FIRST_INTERACTION, RELATIONSHIP_ORIGIN)
_FAMILY_BY_PURPOSE = MappingProxyType({family.purpose: family for family in VERSIONED_FAMILIES})
_FAMILY_BY_IDENTITY = MappingProxyType({family.identity: family for family in VERSIONED_FAMILIES})

PURPOSES = frozenset({C.LONG_TERM_PERSONAL_PROJECT_RECALL, *_FAMILY_BY_PURPOSE})
# Closed, read-only per-purpose maps. The purpose is inside the signed action digest, so everything derived from it is bound
# to signed content.
CAPABILITY_BY_PURPOSE = MappingProxyType({
    C.LONG_TERM_PERSONAL_PROJECT_RECALL: C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE,
    **{family.purpose: family.capability for family in VERSIONED_FAMILIES},
})
EPISTEMIC_BASIS_BY_PURPOSE = MappingProxyType({
    C.LONG_TERM_PERSONAL_PROJECT_RECALL: USER_ASSERTED,
    **{family.purpose: family.epistemic_basis for family in VERSIONED_FAMILIES},
})
SENSITIVITY_BY_PURPOSE = MappingProxyType({
    C.LONG_TERM_PERSONAL_PROJECT_RECALL: PROJECT_FACT,
    **{family.purpose: family.sensitivity for family in VERSIONED_FAMILIES},
})
KNOWN_CAPABILITIES = frozenset(CAPABILITY_BY_PURPOSE.values())


def family_for_purpose(purpose: Any) -> Optional[VersionedFamilyV1]:
    try:
        return _FAMILY_BY_PURPOSE.get(purpose)
    except TypeError:
        return None


def family_for_identity(identity: Any) -> Optional[VersionedFamilyV1]:
    try:
        return _FAMILY_BY_IDENTITY.get(tuple(identity))
    except TypeError:
        return None


def family_for_proposal_family(proposal_family: Any) -> Optional[VersionedFamilyV1]:
    return next((family for family in VERSIONED_FAMILIES if family.proposal_family == proposal_family), None)


def is_first_interaction(purpose: Any) -> bool:
    return purpose == OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION


def is_relationship_origin(purpose: Any) -> bool:
    return purpose == LONG_TERM_OWNER_RELATIONSHIP_ORIGIN_RECALL


def capability_for_purpose(purpose: Any) -> str:
    try:
        return CAPABILITY_BY_PURPOSE[purpose]
    except (KeyError, TypeError):
        raise C.ContractError("purpose is unsupported") from None


def epistemic_basis_for_purpose(purpose: Any) -> str:
    try:
        return EPISTEMIC_BASIS_BY_PURPOSE[purpose]
    except (KeyError, TypeError):
        raise C.ContractError("purpose is unsupported") from None


def _refuse_operation(family: VersionedFamilyV1, what: str = "memory") -> C.ContractError:
    if family.operations == frozenset({C.CREATE}):
        return C.ContractError(f"{family.label} {what} is CREATE-only")
    return C.ContractError(f"{family.label} {what} is " + "/".join(sorted(family.operations)) + " only")


def require_family_scope(purpose: Any, operation: Any, identity: Tuple[str, str, str]) -> None:
    """A family purpose and its tuple imply each other; a family admits only its own operations (or Privacy FORGET)."""
    family = family_for_purpose(purpose)
    if family != family_for_identity(identity):
        raise C.ContractError("purpose and memory tuple do not match")
    if family is not None and operation not in family.operations | {C.FORGET}:
        raise _refuse_operation(family)


def _as_codename(value: Any, **extra: Any) -> Any:
    """A copy of a governed V1 dataclass with the codename purpose, so its UNCHANGED validator checks every field
    except the purpose allowlist (and, for Policy, the capability that is paired with it)."""
    fields = {f.name: getattr(value, f.name) for f in dataclasses.fields(value)}
    fields.update(purpose=C.LONG_TERM_PERSONAL_PROJECT_RECALL, **extra)
    return _base_type(value)(**fields)


def _base_type(value: Any) -> type:
    for cls in (C.FrozenMemoryActionV1, C.ConsentRefV1, C.PolicyDecisionRefV1):
        if isinstance(value, cls):
            return cls
    raise C.ContractError("unsupported contract value")


@dataclasses.dataclass(frozen=True)
class VersionedFamilyActionV1(C.FrozenMemoryActionV1):
    """A versioned-family action: same fields and digest encoding as `FrozenMemoryActionV1`."""

    def validate(self) -> None:
        family = family_for_purpose(self.purpose)
        if family is None:
            raise C.ContractError("purpose is unsupported")
        _as_codename(self).validate()
        require_family_scope(self.purpose, self.operation, self.identity)
        if self.operation in {C.CREATE, C.SUPERSEDE} and self.value_schema != family.value_schema:
            raise C.ContractError(f"{family.label} value schema is invalid")


@dataclasses.dataclass(frozen=True)
class FirstInteractionActionV1(VersionedFamilyActionV1):
    """A First Interaction action (the FM-02 name, kept for its callers)."""

    def validate(self) -> None:
        if not is_first_interaction(self.purpose):
            raise C.ContractError("purpose is unsupported")
        super().validate()


@dataclasses.dataclass(frozen=True)
class RelationshipOriginActionV1(VersionedFamilyActionV1):
    """A relationship-origin action."""

    def validate(self) -> None:
        if not is_relationship_origin(self.purpose):
            raise C.ContractError("purpose is unsupported")
        super().validate()


_ACTION_CLASS = MappingProxyType({
    OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION: FirstInteractionActionV1,
    LONG_TERM_OWNER_RELATIONSHIP_ORIGIN_RECALL: RelationshipOriginActionV1,
})


def action_from_fields(**fields: Any) -> C.FrozenMemoryActionV1:
    """The one constructor for actions that may belong to any family."""
    purpose = fields.get("purpose")
    cls = _ACTION_CLASS.get(purpose, C.FrozenMemoryActionV1) if isinstance(purpose, str) else C.FrozenMemoryActionV1
    action = cls(**fields)
    if family_for_purpose(action.purpose) is None and family_for_identity(action.identity) is not None:
        raise C.ContractError("purpose and memory tuple do not match")
    return action


def action_from_row(row: Mapping[str, Any]) -> C.FrozenMemoryActionV1:
    return action_from_fields(
        schema_version=1,
        actor_ref_id=str(row["actor_ref_id"]),
        operation=str(row["operation"]),
        memory_class=str(row["memory_class"]),
        subject_namespace=str(row["subject_namespace"]),
        subject_key=str(row["subject_key"]),
        value_schema=row["value_schema"],
        payload_digest=str(row["payload_digest"]),
        expected_active_revision_id=row["expected_active_revision_id"],
        restore_revision_id=row["restore_revision_id"],
        purpose=str(row["purpose"]),
    )


def validate_consent(consent: C.ConsentRefV1) -> None:
    """Codename consents: the unchanged `validate_shape`. Family consents: the same checks on a codename copy, plus
    the family scope (exact tuple, CREATE)."""
    identity = (consent.memory_class, consent.subject_namespace, consent.subject_key)
    family = family_for_purpose(consent.purpose)
    if family is None:
        consent.validate_shape()
        if family_for_identity(identity) is not None:
            raise C.ContractError("purpose and memory tuple do not match")
        return
    _as_codename(consent).validate_shape()
    require_family_scope(consent.purpose, consent.operation, identity)
    if consent.operation not in family.operations:
        raise _refuse_operation(family, "consent")


def validate_policy(decision: C.PolicyDecisionRefV1) -> None:
    """Codename decisions: the unchanged `validate_shape`. Family decisions: the paired capability, the same checks
    on a codename copy, plus the family scope."""
    identity = (decision.memory_class, decision.subject_namespace, decision.subject_key)
    family = family_for_purpose(decision.purpose)
    if family is None:
        decision.validate_shape()
        if family_for_identity(identity) is not None:
            raise C.ContractError("purpose and memory tuple do not match")
        return
    if decision.capability != family.capability:
        raise C.ContractError("policy capability is unsupported")
    _as_codename(decision, capability=C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE).validate_shape()
    require_family_scope(decision.purpose, decision.operation, identity)
    if decision.operation not in family.operations:
        raise _refuse_operation(family, "policy")
