"""Governed DB registry and legacy-containment readiness loaders."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, FrozenSet, Iterable, Mapping, Optional, Tuple

from . import canonical_contracts as C
from . import legacy_canonical_containment as legacy
from . import memory_v2
from . import slice15b2a_migration


class RegistryLoadError(RuntimeError):
    pass


def _policy_semantics(policy: memory_v2.MemoryTuplePolicyV1) -> Tuple[object, ...]:
    return (
        policy.memory_class,
        policy.subject_namespace,
        policy.subject_key,
        policy.value_schema,
        policy.capability,
        policy.read_allowed,
        policy.write_allowed,
        policy.requires_consent,
    )


class GovernedRegistryLoader:
    """Load immutable rows only when server-reviewed policy matches exactly."""

    def __init__(
        self,
        path: Path,
        *,
        approved_policies: Iterable[memory_v2.MemoryTuplePolicyV1] = (),
        allowed_memory_classes: FrozenSet[str] = frozenset(),
    ):
        self.path = Path(path)
        approved = tuple(approved_policies)
        identities = tuple(value.identity for value in approved)
        if len(identities) != len(set(identities)):
            raise RegistryLoadError("approved tuple policy is duplicated")
        if any(value.memory_class not in allowed_memory_classes for value in approved):
            raise RegistryLoadError("approved memory class is not closed")
        self._approved: Dict[
            Tuple[str, str, str], memory_v2.MemoryTuplePolicyV1
        ] = {value.identity: value for value in approved}
        self._allowed_classes = frozenset(allowed_memory_classes)

    def load(self) -> memory_v2.CanonicalTupleRegistry:
        if not self.path.is_file():
            raise RegistryLoadError("registry database is unavailable")
        conn = sqlite3.connect(f"file:{self.path.resolve()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            existing = {
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            if not memory_v2.REGISTRY_TABLES.issubset(existing):
                raise RegistryLoadError("registry schema is unavailable")
            expected_fp = slice15b2a_migration.schema_fingerprint(
                conn, memory_v2.REGISTRY_SCHEMA_OBJECTS
            )
            ledger = conn.execute(
                "SELECT version,schema_fingerprint FROM memory_registry_schema_migration "
                "ORDER BY version DESC LIMIT 1"
            ).fetchone()
            if ledger is None or int(ledger[0]) != 1 or str(ledger[1]) != expected_fp:
                raise RegistryLoadError("registry schema fingerprint is invalid")
            rows = conn.execute(
                "SELECT memory_class,subject_namespace,subject_key,value_schema,"
                "capability,read_allowed,write_allowed,requires_consent "
                "FROM memory_registry_entry ORDER BY memory_class,subject_namespace,subject_key"
            ).fetchall()
        except sqlite3.Error as exc:
            raise RegistryLoadError("registry database is malformed") from exc
        finally:
            conn.close()
        loaded = []
        seen = set()
        for row in rows:
            if any(row[key] is None for key in row.keys()):
                raise RegistryLoadError("registry row is incomplete")
            policy = memory_v2.MemoryTuplePolicyV1(
                memory_class=str(row["memory_class"]),
                subject_namespace=str(row["subject_namespace"]),
                subject_key=str(row["subject_key"]),
                value_schema=str(row["value_schema"]),
                capability=str(row["capability"]),
                read_allowed=int(row["read_allowed"]) == 1,
                write_allowed=int(row["write_allowed"]) == 1,
                requires_consent=int(row["requires_consent"]) == 1,
            )
            if policy.identity in seen or policy.memory_class not in self._allowed_classes:
                raise RegistryLoadError("registry row is duplicate or outside closed classes")
            seen.add(policy.identity)
            approved = self._approved.get(policy.identity)
            if approved is None or _policy_semantics(approved) != _policy_semantics(policy):
                raise RegistryLoadError("registry row has no exact server approval")
            loaded.append(policy)
        if set(seen) != set(self._approved):
            raise RegistryLoadError("approved and durable registry rows differ")
        try:
            return memory_v2.CanonicalTupleRegistry(loaded)
        except (C.ContractError, ValueError) as exc:
            raise RegistryLoadError("registry policy validation failed") from exc


@dataclass(frozen=True)
class ContainmentReadiness:
    gate: legacy.LegacyCanonicalContainmentGate
    identities: FrozenSet[Tuple[str, str, str]]

    def ready_for(self, identity: Tuple[str, str, str]) -> bool:
        return identity in self.identities


def load_containment(
    registry_path: Path,
    *,
    secret: bytes,
    canonical_registry: memory_v2.CanonicalTupleRegistry,
) -> ContainmentReadiness:
    """Load an exact containment file; missing/malformed always fails closed."""
    path = Path(registry_path)
    if not path.is_file() or len(secret) < 32:
        raise RegistryLoadError("legacy containment is unavailable")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RegistryLoadError("legacy containment is malformed") from exc
    if not isinstance(raw, dict) or set(raw) != {"schemaVersion", "protectedTuples"}:
        raise RegistryLoadError("legacy containment document is not closed")
    if raw["schemaVersion"] != 1 or not isinstance(raw["protectedTuples"], list):
        raise RegistryLoadError("legacy containment schema is unsupported")
    entries = []
    for item in raw["protectedTuples"]:
        if not isinstance(item, dict) or set(item) != {
            "schemaVersion",
            "memoryClass",
            "subjectNamespace",
            "subjectKey",
            "valueFingerprints",
            "actionDigests",
        }:
            raise RegistryLoadError("legacy containment entry is not closed")
        if not isinstance(item["valueFingerprints"], list) or not isinstance(
            item["actionDigests"], list
        ):
            raise RegistryLoadError("legacy containment digest sets are malformed")
        entry = legacy.ProtectedCanonicalTupleV1(
            schema_version=item["schemaVersion"],
            memory_class=item["memoryClass"],
            subject_namespace=item["subjectNamespace"],
            subject_key=item["subjectKey"],
            value_fingerprints=tuple(item["valueFingerprints"]),
            action_digests=tuple(item["actionDigests"]),
        )
        try:
            entry.validate()
        except (TypeError, ValueError) as exc:
            raise RegistryLoadError("legacy containment entry is invalid") from exc
        if canonical_registry.resolve(*entry.identity) is None:
            raise RegistryLoadError("containment tuple has no canonical registry entry")
        entries.append(entry)
    identities = tuple(value.identity for value in entries)
    if len(identities) != len(set(identities)):
        raise RegistryLoadError("legacy containment identity is duplicated")
    if frozenset(identities) != frozenset(canonical_registry.active_keys()):
        raise RegistryLoadError("registry and containment readiness differ")
    gate = legacy.LegacyCanonicalContainmentGate(
        secret=secret,
        registry_provider=lambda: tuple(entries),
    )
    return ContainmentReadiness(gate=gate, identities=frozenset(identities))
