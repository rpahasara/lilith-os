"""Versioned memory-action contract layer for the FM-02 First Interaction family.

`canonical_contracts` stays byte-identical: it is a governed shared module of the signer and broker releases
(sha256 f93d26d8...). Codename actions keep using its unchanged `FrozenMemoryActionV1`, so their meaning and every
digest are unchanged. This module adds exactly one second family on top:

- purpose `OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION`, capability `canonical_memory.first_interaction.create`,
  epistemic basis `RECORDED_INTERACTION`, value schema `FirstInteractionEpisodeV1`;
- the one tuple (`OWNER_DIRECTED_FIRST_INTERACTION`, `lilith.core.autobiographical`, `episode.first-interaction`);
- CREATE only (FORGET stays Privacy-owned).

`FirstInteractionActionV1` subclasses `FrozenMemoryActionV1` without new fields: `semantic_dict` and `action_digest` are
inherited, so the encoding is identical. Its `validate` runs the unchanged base `validate` on a codename-purpose copy
(the only purpose-dependent base check is the purpose allowlist) and then applies the family rules. Build every action
through `action_from_fields`: it returns the subclass for this purpose, the unchanged class otherwise, and refuses the
First Interaction tuple under any other purpose.

Nothing here activates the family. The installed signer still validates with `canonical_contracts` only and refuses
this purpose until a reviewed signer release adopts this module.
"""

from __future__ import annotations

import dataclasses
from types import MappingProxyType
from typing import Any, Mapping, Tuple

try:
    from . import canonical_contracts as C
except ImportError:  # deploy-exact flat-directory tests
    import canonical_contracts as C


OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION = "OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION"
CANONICAL_MEMORY_FIRST_INTERACTION_CREATE = "canonical_memory.first_interaction.create"
FIRST_INTERACTION_IDENTITY = (
    "OWNER_DIRECTED_FIRST_INTERACTION",
    "lilith.core.autobiographical",
    "episode.first-interaction",
)
FIRST_INTERACTION_VALUE_SCHEMA = "FirstInteractionEpisodeV1"
USER_ASSERTED = "USER_ASSERTED"
RECORDED_INTERACTION = "RECORDED_INTERACTION"

PURPOSES = frozenset({C.LONG_TERM_PERSONAL_PROJECT_RECALL, OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION})
# Closed, read-only per-purpose maps. The purpose is inside the signed action digest, so everything derived from it is bound
# to signed content.
CAPABILITY_BY_PURPOSE = MappingProxyType({
    C.LONG_TERM_PERSONAL_PROJECT_RECALL: C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE,
    OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION: CANONICAL_MEMORY_FIRST_INTERACTION_CREATE,
})
EPISTEMIC_BASIS_BY_PURPOSE = MappingProxyType({
    C.LONG_TERM_PERSONAL_PROJECT_RECALL: USER_ASSERTED,
    OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION: RECORDED_INTERACTION,
})
KNOWN_CAPABILITIES = frozenset(CAPABILITY_BY_PURPOSE.values())


def is_first_interaction(purpose: Any) -> bool:
    return purpose == OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION


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


def require_family_scope(purpose: Any, operation: Any, identity: Tuple[str, str, str]) -> None:
    """The First Interaction purpose and tuple imply each other; the family is CREATE (or Privacy FORGET) only."""
    first = is_first_interaction(purpose)
    if first != (tuple(identity) == FIRST_INTERACTION_IDENTITY):
        raise C.ContractError("purpose and memory tuple do not match")
    if first and operation not in {C.CREATE, C.FORGET}:
        raise C.ContractError("First Interaction memory is CREATE-only")


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
class FirstInteractionActionV1(C.FrozenMemoryActionV1):
    """A First Interaction action: same fields and digest encoding as `FrozenMemoryActionV1`."""

    def validate(self) -> None:
        if not is_first_interaction(self.purpose):
            raise C.ContractError("purpose is unsupported")
        _as_codename(self).validate()
        require_family_scope(self.purpose, self.operation, self.identity)
        if self.operation == C.CREATE and self.value_schema != FIRST_INTERACTION_VALUE_SCHEMA:
            raise C.ContractError("First Interaction value schema is invalid")


def action_from_fields(**fields: Any) -> C.FrozenMemoryActionV1:
    """The one constructor for actions that may belong to either family."""
    cls = FirstInteractionActionV1 if is_first_interaction(fields.get("purpose")) else C.FrozenMemoryActionV1
    action = cls(**fields)
    if not is_first_interaction(action.purpose) and tuple(action.identity) == FIRST_INTERACTION_IDENTITY:
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
    """Codename consents: the unchanged `validate_shape`. First Interaction consents: the same checks on a codename
    copy, plus the family scope (exact tuple, CREATE)."""
    if not is_first_interaction(consent.purpose):
        consent.validate_shape()
        identity = (consent.memory_class, consent.subject_namespace, consent.subject_key)
        if identity == FIRST_INTERACTION_IDENTITY:
            raise C.ContractError("purpose and memory tuple do not match")
        return
    _as_codename(consent).validate_shape()
    require_family_scope(consent.purpose, consent.operation,
                         (consent.memory_class, consent.subject_namespace, consent.subject_key))
    if consent.operation != C.CREATE:
        raise C.ContractError("First Interaction consent is CREATE-only")


def validate_policy(decision: C.PolicyDecisionRefV1) -> None:
    """Codename decisions: the unchanged `validate_shape`. First Interaction decisions: the paired capability, the
    same checks on a codename copy, plus the family scope."""
    if not is_first_interaction(decision.purpose):
        decision.validate_shape()
        identity = (decision.memory_class, decision.subject_namespace, decision.subject_key)
        if identity == FIRST_INTERACTION_IDENTITY:
            raise C.ContractError("purpose and memory tuple do not match")
        return
    if decision.capability != CANONICAL_MEMORY_FIRST_INTERACTION_CREATE:
        raise C.ContractError("policy capability is unsupported")
    _as_codename(decision, capability=C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE).validate_shape()
    require_family_scope(decision.purpose, decision.operation,
                         (decision.memory_class, decision.subject_namespace, decision.subject_key))
    if decision.operation != C.CREATE:
        raise C.ContractError("First Interaction policy is CREATE-only")
