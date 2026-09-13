"""Legacy persistence containment for future canonical-memory identities.

Production loads an empty protected registry in Slice 15B2a.  Test registries
use keyed fingerprints of synthetic current and historical values; plaintext
protected values are never required in production configuration or pending
records.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, Mapping, Optional, Sequence, Tuple


LEGACY_CONTAINMENT_NOT_READY = "LEGACY_CONTAINMENT_NOT_READY"
PROTECTED_CANONICAL_VALUE = "PROTECTED_CANONICAL_VALUE"
PROTECTED_CANONICAL_TUPLE = "PROTECTED_CANONICAL_TUPLE"
SCHEMA_VERSION = 1

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_WORD_RE = re.compile(r"[^\W_]+(?:[._-][^\W_]+)*", re.UNICODE)


class ContainmentError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class LegacyContainmentMarkerV1:
    schema_version: int
    exclude_from_legacy_background_review: bool
    recognized_canonical_action: bool
    memory_class: Optional[str]
    subject_namespace: Optional[str]
    subject_key: Optional[str]
    action_digest: Optional[str]

    @property
    def identity(self) -> Optional[Tuple[str, str, str]]:
        if self.memory_class and self.subject_namespace and self.subject_key:
            return (self.memory_class, self.subject_namespace, self.subject_key)
        return None


@dataclass(frozen=True)
class ProtectedCanonicalTupleV1:
    schema_version: int
    memory_class: str
    subject_namespace: str
    subject_key: str
    value_fingerprints: Tuple[str, ...]
    action_digests: Tuple[str, ...] = ()

    @property
    def identity(self) -> Tuple[str, str, str]:
        return (self.memory_class, self.subject_namespace, self.subject_key)

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("protected tuple schema version is unsupported")
        if not self.memory_class or not self.subject_namespace or not self.subject_key:
            raise ValueError("protected tuple identity is incomplete")
        if not all(_HEX64_RE.fullmatch(v) for v in self.value_fingerprints):
            raise ValueError("protected value fingerprint is invalid")
        if not all(_HEX64_RE.fullmatch(v) for v in self.action_digests):
            raise ValueError("protected action digest is invalid")


@dataclass(frozen=True)
class ContainmentDecision:
    allowed: bool
    failure_code: Optional[str]
    matched_identity: Optional[Tuple[str, str, str]] = None


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def _normalize_value(value: str) -> str:
    return unicodedata.normalize("NFC", value.strip())


def value_fingerprint(secret: bytes, value: str) -> str:
    normalized = _normalize_value(value)
    return hmac.new(
        secret,
        _canonical({"kind": "legacy-canonical-value-v1", "value": normalized}),
        hashlib.sha256,
    ).hexdigest()


def make_protected_tuple(
    *,
    secret: bytes,
    memory_class: str,
    subject_namespace: str,
    subject_key: str,
    protected_values: Iterable[str],
    action_digests: Iterable[str] = (),
) -> ProtectedCanonicalTupleV1:
    entry = ProtectedCanonicalTupleV1(
        schema_version=1,
        memory_class=memory_class,
        subject_namespace=subject_namespace,
        subject_key=subject_key,
        value_fingerprints=tuple(sorted({
            value_fingerprint(secret, value) for value in protected_values
        })),
        action_digests=tuple(sorted(set(action_digests))),
    )
    entry.validate()
    return entry


def _iter_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(key, str):
                yield key
            yield from _iter_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_strings(item)


def _candidate_fragments(text: str) -> Iterator[str]:
    normalized = _normalize_value(text)
    if normalized:
        yield normalized
    words = [m.group(0) for m in _WORD_RE.finditer(normalized)]
    # Future codename values are at most 64 scalars.  Bounded 1..8 token spans
    # catch standalone and embedded multiword values without quadratic scans
    # over large skill documents.
    for start in range(len(words)):
        for width in range(1, min(8, len(words) - start) + 1):
            candidate = " ".join(words[start : start + width])
            if len(candidate) <= 64:
                yield candidate


class LegacyCanonicalContainmentGate:
    def __init__(
        self,
        *,
        secret: bytes,
        registry_provider: Callable[[], Iterable[ProtectedCanonicalTupleV1]],
    ):
        if len(secret) < 32:
            raise ValueError("containment secret must be at least 32 bytes")
        self._secret = bytes(secret)
        self._registry_provider = registry_provider

    def _registry(self) -> Tuple[ProtectedCanonicalTupleV1, ...]:
        entries = tuple(self._registry_provider())
        for entry in entries:
            entry.validate()
        identities = [entry.identity for entry in entries]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate protected canonical identity")
        return entries

    def evaluate(
        self,
        payload: Any,
        *,
        marker: Optional[LegacyContainmentMarkerV1] = None,
    ) -> ContainmentDecision:
        try:
            registry = self._registry()
        except Exception:
            if marker is not None and marker.recognized_canonical_action:
                return ContainmentDecision(False, LEGACY_CONTAINMENT_NOT_READY)
            return ContainmentDecision(True, None)
        if marker is not None:
            if marker.schema_version != 1:
                return ContainmentDecision(False, LEGACY_CONTAINMENT_NOT_READY)
            if marker.recognized_canonical_action:
                for entry in registry:
                    if marker.identity == entry.identity:
                        return ContainmentDecision(False, PROTECTED_CANONICAL_TUPLE, entry.identity)
                    if marker.action_digest and marker.action_digest in entry.action_digests:
                        return ContainmentDecision(False, PROTECTED_CANONICAL_TUPLE, entry.identity)
                # A typed canonical-memory action that is not present in the
                # closed registry is not an ordinary legacy write.  This is
                # especially important while the production registry is empty:
                # the lane must stay closed instead of falling through.
                return ContainmentDecision(False, LEGACY_CONTAINMENT_NOT_READY)
        protected = {
            fingerprint: entry.identity
            for entry in registry
            for fingerprint in entry.value_fingerprints
        }
        if not protected:
            return ContainmentDecision(True, None)
        seen = set()
        for text in _iter_strings(payload):
            for candidate in _candidate_fragments(text):
                if candidate in seen:
                    continue
                seen.add(candidate)
                match = protected.get(value_fingerprint(self._secret, candidate))
                if match is not None:
                    return ContainmentDecision(False, PROTECTED_CANONICAL_VALUE, match)
        return ContainmentDecision(True, None)

    def require_allowed(
        self,
        payload: Any,
        *,
        marker: Optional[LegacyContainmentMarkerV1] = None,
    ) -> None:
        decision = self.evaluate(payload, marker=marker)
        if not decision.allowed:
            raise ContainmentError(str(decision.failure_code))


def _default_secret_path() -> Path:
    home = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
    configured = os.environ.get("LILITH_LEGACY_CONTAINMENT_KEY_FILE")
    return Path(configured) if configured else (
        home / "lilith-os" / "data" / "legacy_containment.key"
    )


def _default_registry_path() -> Path:
    home = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
    configured = os.environ.get("LILITH_LEGACY_CONTAINMENT_REGISTRY_FILE")
    return Path(configured) if configured else (
        home / "lilith-os" / "data" / "legacy_containment_registry.json"
    )


def _load_production_registry() -> Iterable[ProtectedCanonicalTupleV1]:
    """Missing registry means the approved Slice 15B2a empty registry."""
    path = _default_registry_path()
    if not path.exists():
        return ()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schemaVersion") != 1:
        raise ValueError("containment registry is malformed")
    entries = raw.get("protectedTuples")
    if not isinstance(entries, list):
        raise ValueError("containment registry entries are malformed")
    result = []
    for item in entries:
        if not isinstance(item, dict) or set(item) != {
            "schemaVersion", "memoryClass", "subjectNamespace", "subjectKey",
            "valueFingerprints", "actionDigests",
        }:
            raise ValueError("containment registry entry is not closed")
        result.append(ProtectedCanonicalTupleV1(
            schema_version=item["schemaVersion"],
            memory_class=item["memoryClass"],
            subject_namespace=item["subjectNamespace"],
            subject_key=item["subjectKey"],
            value_fingerprints=tuple(item["valueFingerprints"]),
            action_digests=tuple(item["actionDigests"]),
        ))
    return tuple(result)


_production_gate: Optional[LegacyCanonicalContainmentGate] = None


def production_gate() -> LegacyCanonicalContainmentGate:
    global _production_gate
    if _production_gate is None:
        secret_path = _default_secret_path()
        secret = secret_path.read_bytes()
        if len(secret) < 32:
            raise ValueError("containment secret is too short")
        if os.name != "nt" and stat.S_IMODE(secret_path.stat().st_mode) != 0o600:
            raise PermissionError("containment secret must be mode 0600")
        _production_gate = LegacyCanonicalContainmentGate(
            secret=secret,
            registry_provider=_load_production_registry,
        )
    return _production_gate


def marker_from_payload(payload: Any) -> Optional[LegacyContainmentMarkerV1]:
    if not isinstance(payload, Mapping):
        return None
    raw = payload.get("legacyContainment")
    if not isinstance(raw, Mapping):
        return None
    allowed = {
        "schemaVersion", "excludeFromLegacyBackgroundReview",
        "recognizedCanonicalAction", "memoryClass", "subjectNamespace",
        "subjectKey", "actionDigest",
    }
    if not set(raw).issubset(allowed):
        return LegacyContainmentMarkerV1(0, False, True, None, None, None, None)
    return LegacyContainmentMarkerV1(
        schema_version=raw.get("schemaVersion"),
        exclude_from_legacy_background_review=(
            raw.get("excludeFromLegacyBackgroundReview") is True
        ),
        recognized_canonical_action=raw.get("recognizedCanonicalAction") is True,
        memory_class=raw.get("memoryClass"),
        subject_namespace=raw.get("subjectNamespace"),
        subject_key=raw.get("subjectKey"),
        action_digest=raw.get("actionDigest"),
    )


def check_legacy_payload(payload: Any) -> ContainmentDecision:
    marker = marker_from_payload(payload)
    try:
        return production_gate().evaluate(payload, marker=marker)
    except Exception:
        if marker is not None and marker.recognized_canonical_action:
            return ContainmentDecision(False, LEGACY_CONTAINMENT_NOT_READY)
        # If the registry/key is unavailable, no recognized memory-lane action
        # may fall through.  Ordinary legacy behavior is unchanged until a
        # typed marker exists (the 15B2a production registry is empty).
        return ContainmentDecision(True, None)


def filter_background_review_messages(messages: Sequence[Any]) -> list[Any]:
    """Exclude typed memory-lane turns before the reviewer sees their value."""
    filtered = []
    for message in messages or ():
        marker = marker_from_payload(message)
        metadata = message.get("metadata") if isinstance(message, Mapping) else None
        if marker is None and isinstance(metadata, Mapping):
            marker = marker_from_payload(metadata)
        if marker is not None and marker.exclude_from_legacy_background_review:
            continue
        filtered.append(message)
    return filtered


class PendingErasureOwner:
    OWNER = "PENDING"

    def __init__(
        self,
        pending_root: Path,
        gate: LegacyCanonicalContainmentGate,
        privacy_authority: Any,
    ):
        self.pending_root = Path(pending_root)
        self.gate = gate
        self.privacy_authority = privacy_authority

    def erase_authorized(self, authorization_ref_id: str, execution_nonce: str) -> Dict[str, Any]:
        authorization = self.privacy_authority.resolve_erasure_authorization(
            authorization_ref_id, owner=self.OWNER, execution_nonce=execution_nonce
        )
        if authorization is None:
            raise PermissionError("PRIVACY_ERASURE_NOT_AUTHORIZED")
        removed = 0
        if self.pending_root.exists():
            for path in self.pending_root.rglob("*.json"):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                decision = self.gate.evaluate(payload)
                if not decision.allowed and decision.matched_identity == authorization.identity:
                    path.unlink()
                    removed += 1
        result = {"owner": self.OWNER, "status": "COMPLETE", "deleted": removed}
        self.privacy_authority.record_owner_result(
            authorization_ref_id, execution_nonce, result
        )
        return result


class _LegacyTextErasureOwner:
    """Remove only lines matching the authorized tuple's keyed fingerprints."""

    OWNER = ""

    def __init__(
        self,
        paths_provider: Callable[[], Iterable[Path]],
        gate: LegacyCanonicalContainmentGate,
        privacy_authority: Any,
    ):
        self.paths_provider = paths_provider
        self.gate = gate
        self.privacy_authority = privacy_authority

    def erase_authorized(self, authorization_ref_id: str, execution_nonce: str) -> Dict[str, Any]:
        authorization = self.privacy_authority.resolve_erasure_authorization(
            authorization_ref_id, owner=self.OWNER, execution_nonce=execution_nonce
        )
        if authorization is None:
            raise PermissionError("PRIVACY_ERASURE_NOT_AUTHORIZED")
        removed = 0
        touched = 0
        for supplied in self.paths_provider():
            path = Path(supplied)
            if not path.is_file() or path.is_symlink():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            kept = []
            file_removed = 0
            for line in text.splitlines(keepends=True):
                decision = self.gate.evaluate(line)
                if not decision.allowed and decision.matched_identity == authorization.identity:
                    file_removed += 1
                else:
                    kept.append(line)
            if file_removed:
                mode = path.stat().st_mode
                temporary = path.with_name(path.name + ".privacy.tmp")
                temporary.write_text("".join(kept), encoding="utf-8")
                os.chmod(temporary, mode)
                os.replace(temporary, path)
                removed += file_removed
                touched += 1
        result = {
            "owner": self.OWNER,
            "status": "COMPLETE",
            "deleted": removed,
            "filesTouched": touched,
        }
        self.privacy_authority.record_owner_result(
            authorization_ref_id, execution_nonce, result
        )
        return result


class LegacyMemoryErasureOwner(_LegacyTextErasureOwner):
    """Privileged exact erasure for the configured MEMORY.md/USER.md files."""

    OWNER = "LEGACY_MEMORY"

    def __init__(
        self,
        memory_path: Path,
        user_path: Path,
        gate: LegacyCanonicalContainmentGate,
        privacy_authority: Any,
    ):
        paths = (Path(memory_path), Path(user_path))
        super().__init__(lambda: paths, gate, privacy_authority)


class LegacySkillErasureOwner(_LegacyTextErasureOwner):
    """Privileged exact erasure for text files below one configured skill root."""

    OWNER = "LEGACY_SKILLS"

    def __init__(
        self,
        skill_root: Path,
        gate: LegacyCanonicalContainmentGate,
        privacy_authority: Any,
    ):
        root = Path(skill_root).resolve()

        def paths() -> Iterable[Path]:
            if not root.is_dir():
                return ()
            return tuple(
                path
                for path in root.rglob("*")
                if path.is_file() and not path.is_symlink()
            )

        super().__init__(paths, gate, privacy_authority)
