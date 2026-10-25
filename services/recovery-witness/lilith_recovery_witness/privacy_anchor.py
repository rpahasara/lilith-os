"""Track B B2: the witness-held Privacy rollback anchor (K-PAN), DEV only. SOURCE PREPARED / NOT INSTALLED.

Design: F9-C anchor design revision 1 §1, §3 (owner-approved final architecture); Track B record TRACKB-B1-RESULT.md.

The witness keeps a second, independent chain: ``PrivacyAnchorV1`` documents (pure contract
``lilith_memory.privacy_anchor_contracts``) over the SET of Privacy's append-only restore-suppression entries. It
holds no Privacy database, secret or content: the root advance helper sends only opaque ``(suppression_ref_id,
identity_selector)`` pairs, and the witness signs only a strict extension of its own verified chain.

Isolation from the RecoveryWitnessV2 service:

- its own protocol id ``LILITH_PRIVACY_ANCHOR_DEV`` with its own closed operations, accepted on the OWNER socket only
  (peer uid 0). The signer socket keeps parsing with ``protocol.py`` (byte-identical), which refuses this id, as does
  any witness binary without this module (a downgrade fails closed: no anchor -> the Core API gate refuses);
- its own key K-PAN (``PrivacyAnchorSigningKeyV1``, credential ``privacy-anchor-signing-key``); K-WIT never signs an
  anchor and K-PAN never signs a RecoveryWitnessV2 body;
- its own state directory ``/var/lib/lilith-privacy-anchor`` with its own lock. The RecoveryWitnessV2 recovery scan
  (pinned ``witness_readiness``) admits no extra entry under ``/var/lib/lilith-recovery-witness``, so the anchor
  must never live there.

Commit order of one anchor version (pin before commit):
    staging/<v>.json O_EXCL write -> fsync -> link to chain/<v>.json (never overwrites) -> chain/ fsync (commit)
    -> unlink the staging entry.
A crash before the link leaves only a staging file (ignored, removed under the lock next time); after it the version
is committed. Any chain that does not verify end to end makes every operation refuse ``ANCHOR_STORE_FAIL_CLOSED``;
the witness never repairs it.

Operations (owner socket):
    READ_PRIVACY_ANCHOR    {fromVersion}                       -> chain documents from that version
    GENESIS_PRIVACY_ANCHOR {entries, expectedSetHead}          -> v1, only on an empty store (owner ceremony, B6)
    ADVANCE_PRIVACY_ANCHOR {previousAnchorDigest, entries, expectedSetHead} -> v+1 (strict extension only)
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

import rfc8785
from lilith_memory import privacy_anchor_contracts as PA

from .credential import PrivacyAnchorSigningKeyV1

PROTOCOL = "LILITH_PRIVACY_ANCHOR_DEV"
VERSION = 1
MAX_FRAME_BYTES = 64 * 1024
STATE_DIR = "/var/lib/lilith-privacy-anchor"
ENVIRONMENT = "DEV_SYNTHETIC"          # the Privacy environment the Core API gate names (not LILITH_ENV)

READ_PRIVACY_ANCHOR = "READ_PRIVACY_ANCHOR"
GENESIS_PRIVACY_ANCHOR = "GENESIS_PRIVACY_ANCHOR"
ADVANCE_PRIVACY_ANCHOR = "ADVANCE_PRIVACY_ANCHOR"
OPERATIONS = frozenset({READ_PRIVACY_ANCHOR, GENESIS_PRIVACY_ANCHOR, ADVANCE_PRIVACY_ANCHOR})
MUTATING_OPERATIONS = frozenset({GENESIS_PRIVACY_ANCHOR, ADVANCE_PRIVACY_ANCHOR})
PAYLOAD_FIELDS = {
    READ_PRIVACY_ANCHOR: frozenset({"fromVersion"}),
    GENESIS_PRIVACY_ANCHOR: frozenset({"entries", "expectedSetHead"}),
    ADVANCE_PRIVACY_ANCHOR: frozenset({"previousAnchorDigest", "entries", "expectedSetHead"}),
}
MAX_ENTRIES_PER_ADVANCE = 256
CHAIN = "chain"
STAGING = "staging"
LOCK = "anchor.lock"
_CHAIN_NAME = re.compile(r"(\d{8})\.json\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_ENVELOPE = frozenset({"protocol", "schemaVersion", "operation", "payload"})
_O_DIR = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
FILE_MODE = 0o600
DIRECTORY_MODE = 0o700

FaultHook = Callable[[str], None]
FAULT_POINTS = ("AFTER_STAGING_WRITE", "AFTER_STAGING_FSYNC", "AFTER_CHAIN_LINK", "AFTER_CHAIN_DIRECTORY_FSYNC")


class AnchorProtocolError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class AnchorMessageV1:
    operation: str
    payload: dict[str, Any]


# ----------------------------------------------------------------------------------------------- framing ---

def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AnchorProtocolError("DUPLICATE_FIELD")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise AnchorProtocolError("INVALID_JSON_CONSTANT")


def _decode(frame: bytes) -> dict[str, Any]:
    if not isinstance(frame, bytes) or len(frame) < 4:
        raise AnchorProtocolError("TRUNCATED_FRAME")
    length = struct.unpack(">I", frame[:4])[0]
    if length == 0 or length > MAX_FRAME_BYTES or len(frame) != length + 4:
        raise AnchorProtocolError("INVALID_FRAME_LENGTH")
    raw = frame[4:]
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
    except AnchorProtocolError:
        raise
    except (UnicodeError, ValueError, TypeError) as exc:
        raise AnchorProtocolError("INVALID_JSON") from exc
    try:
        if raw != rfc8785.dumps(value):
            raise AnchorProtocolError("NONCANONICAL_JSON")
    except (rfc8785.CanonicalizationError, OverflowError) as exc:
        raise AnchorProtocolError("INVALID_CANONICAL_JSON") from exc
    if not isinstance(value, dict):
        raise AnchorProtocolError("INVALID_ENVELOPE")
    return value


def is_anchor_frame(frame: bytes) -> bool:
    """True only for a well-formed frame carrying this module's protocol id (routing, never authorization)."""
    try:
        return _decode(frame).get("protocol") == PROTOCOL
    except AnchorProtocolError:
        return False


def _entries(value: Any) -> list[list[str]]:
    if not isinstance(value, list) or len(value) > MAX_ENTRIES_PER_ADVANCE:
        raise AnchorProtocolError("INVALID_PAYLOAD_VALUE")
    for item in value:
        if not isinstance(item, list) or len(item) != 2 or not all(isinstance(x, str) for x in item):
            raise AnchorProtocolError("INVALID_PAYLOAD_VALUE")
    return value


def parse_frame(frame: bytes) -> AnchorMessageV1:
    value = _decode(frame)
    if set(value) != _ENVELOPE:
        raise AnchorProtocolError("INVALID_ENVELOPE")
    if value["protocol"] != PROTOCOL or type(value["schemaVersion"]) is not int or value["schemaVersion"] != VERSION:
        raise AnchorProtocolError("UNSUPPORTED_VERSION")
    operation, payload = value["operation"], value["payload"]
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise AnchorProtocolError("UNSUPPORTED_OPERATION")
    if not isinstance(payload, dict) or set(payload) != PAYLOAD_FIELDS[operation]:
        raise AnchorProtocolError("INVALID_PAYLOAD_FIELDS")
    if operation == READ_PRIVACY_ANCHOR:
        if type(payload["fromVersion"]) is not int or payload["fromVersion"] < 1:
            raise AnchorProtocolError("INVALID_PAYLOAD_VALUE")
    else:
        _entries(payload["entries"])
        if not isinstance(payload["expectedSetHead"], str) or _HEX64.fullmatch(payload["expectedSetHead"]) is None:
            raise AnchorProtocolError("INVALID_PAYLOAD_VALUE")
        if operation == ADVANCE_PRIVACY_ANCHOR and (not isinstance(payload["previousAnchorDigest"], str)
                                                    or _HEX64.fullmatch(payload["previousAnchorDigest"]) is None):
            raise AnchorProtocolError("INVALID_PAYLOAD_VALUE")
    return AnchorMessageV1(operation, payload)


def encode_frame(operation: str, payload: dict[str, Any]) -> bytes:
    raw = rfc8785.dumps({"protocol": PROTOCOL, "schemaVersion": VERSION, "operation": operation, "payload": payload})
    if not 0 < len(raw) <= MAX_FRAME_BYTES:
        raise AnchorProtocolError("INVALID_FRAME_LENGTH")
    return struct.pack(">I", len(raw)) + raw


def encode_response(payload: dict[str, Any]) -> bytes:
    raw = rfc8785.dumps({"protocol": PROTOCOL, "schemaVersion": VERSION, "payload": payload})
    if not 0 < len(raw) <= MAX_FRAME_BYTES:
        raw = rfc8785.dumps({"protocol": PROTOCOL, "schemaVersion": VERSION,
                             "payload": {"status": "REFUSED", "reason": "RESPONSE_TOO_LARGE"}})
    return struct.pack(">I", len(raw)) + raw


def parse_response(frame: bytes) -> dict[str, Any]:
    value = _decode(frame)
    if set(value) != {"protocol", "schemaVersion", "payload"} or value["protocol"] != PROTOCOL \
            or value["schemaVersion"] != VERSION or not isinstance(value["payload"], dict):
        raise AnchorProtocolError("INVALID_RESPONSE")
    return value["payload"]


# ----------------------------------------------------------------------------------------------- storage ---

class AnchorStoreFailClosed(RuntimeError):
    """The stored chain does not verify end to end. Owner investigation; never repaired."""


class AnchorStoreV1:
    """Durable, append-only anchor chain under one witness-owned directory (dir-fd, O_EXCL, link, fsync, flock)."""

    def __init__(self, state_dir: Path | str = STATE_DIR, *, fault: Optional[FaultHook] = None):
        self.state_dir = Path(state_dir)
        self._fault = fault or (lambda _point: None)

    def _dir(self, name: str = "") -> int:
        root = os.open(self.state_dir, _O_DIR)
        if not name:
            return root
        try:
            try:
                os.mkdir(name, DIRECTORY_MODE, dir_fd=root)
            except FileExistsError:
                pass
            return os.open(name, _O_DIR, dir_fd=root)
        finally:
            os.close(root)

    @contextlib.contextmanager
    def lock(self) -> Iterator[None]:
        import fcntl

        root = self._dir()
        try:
            fd = os.open(LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, FILE_MODE, dir_fd=root)
        finally:
            os.close(root)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)   # a second holder is refused, never waited for
            yield
        finally:
            os.close(fd)

    def documents(self) -> list[dict[str, Any]]:
        folder = self._dir(CHAIN)
        try:
            names = sorted(os.listdir(folder))
            docs, expected = [], 1
            for name in names:
                match = _CHAIN_NAME.fullmatch(name)
                if match is None or int(match.group(1)) != expected:
                    raise AnchorStoreFailClosed("UNEXPECTED_CHAIN_ENTRY")
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=folder)
                try:
                    raw = b""
                    while chunk := os.read(fd, 65536):
                        raw += chunk
                finally:
                    os.close(fd)
                try:
                    docs.append(json.loads(raw.decode("ascii")))
                except (UnicodeError, ValueError) as exc:
                    raise AnchorStoreFailClosed("CHAIN_ENTRY_CORRUPT") from exc
                expected += 1
            return docs
        finally:
            os.close(folder)

    def commit(self, version: int, document: dict[str, Any]) -> None:
        data = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("ascii")
        name = f"{version:08d}.json"
        staging, chain = self._dir(STAGING), self._dir(CHAIN)
        try:
            for stale in os.listdir(staging):                   # interrupted earlier attempts (under the lock)
                os.unlink(stale, dir_fd=staging)
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, FILE_MODE,
                         dir_fd=staging)
            try:
                view = memoryview(data)
                while view:
                    view = view[os.write(fd, view):]
                self._fault("AFTER_STAGING_WRITE")
                os.fsync(fd)
            finally:
                os.close(fd)
            self._fault("AFTER_STAGING_FSYNC")
            os.link(name, name, src_dir_fd=staging, dst_dir_fd=chain, follow_symlinks=False)   # never overwrites
            self._fault("AFTER_CHAIN_LINK")
            os.fsync(chain)                                     # commit point
            self._fault("AFTER_CHAIN_DIRECTORY_FSYNC")
            os.unlink(name, dir_fd=staging)
        finally:
            os.close(staging)
            os.close(chain)


# ----------------------------------------------------------------------------------------------- service ---

def _refused(reason: str) -> dict[str, Any]:
    return {"status": "REFUSED", "reason": reason}


class PrivacyAnchorServiceV1:
    """Dispatch of the three anchor operations over one store and one K-PAN signer (or none: then every operation
    refuses ``ANCHOR_KEY_ABSENT`` and the RecoveryWitnessV2 service is unaffected)."""

    def __init__(self, *, store: AnchorStoreV1, signing_key: Optional[PrivacyAnchorSigningKeyV1],
                 clock: Callable[[], str], environment: str = ENVIRONMENT):
        if signing_key is not None and not isinstance(signing_key, PrivacyAnchorSigningKeyV1):
            raise TypeError("a PrivacyAnchorSigningKeyV1 is required")
        self._store = store
        self._key = signing_key
        self._clock = clock
        self._environment = environment

    def _chain(self, docs: list[dict[str, Any]]) -> Optional[PA.AnchorChainV1]:
        if not docs:
            return None
        try:
            return PA.verify_anchor_chain(docs, self._key.verifying_key(), environment=self._environment,
                                          key_id=self._key.anchor_key_id)
        except PA.PrivacyAnchorError as exc:
            raise AnchorStoreFailClosed("CHAIN_UNVERIFIED:" + exc.code) from exc

    def dispatch(self, message: AnchorMessageV1) -> dict[str, Any]:
        if self._key is None:
            return _refused("ANCHOR_KEY_ABSENT")
        try:
            with self._store.lock():
                docs = self._store.documents()
                chain = self._chain(docs)
                if message.operation == READ_PRIVACY_ANCHOR:
                    start = message.payload["fromVersion"]
                    return {"status": "OK" if chain else "UNINITIALIZED", "anchorKeyId": self._key.anchor_key_id,
                            "anchorVersion": chain.version if chain else 0,
                            "anchorDigest": chain.digest if chain else None, "documents": docs[start - 1:]}
                return self._mutate(message, docs, chain)
        except BlockingIOError:
            return _refused("ANCHOR_STORE_LOCKED")
        except OSError:
            return _refused("ANCHOR_STORE_UNAVAILABLE")             # e.g. the state directory is not installed
        except AnchorStoreFailClosed as exc:
            return _refused("ANCHOR_STORE_FAIL_CLOSED:" + str(exc))

    def _mutate(self, message: AnchorMessageV1, docs: list[dict[str, Any]],
                chain: Optional[PA.AnchorChainV1]) -> dict[str, Any]:
        payload = message.payload
        if message.operation == GENESIS_PRIVACY_ANCHOR and chain is not None:
            return _refused("ANCHOR_ALREADY_PROVISIONED")
        if message.operation == ADVANCE_PRIVACY_ANCHOR:
            if chain is None:
                return _refused("ANCHOR_NOT_PROVISIONED")
            if payload["previousAnchorDigest"] != chain.digest:
                return _refused("ANCHOR_HEAD_MOVED")
        try:
            body = PA.unsigned_anchor_advance(chain, payload["entries"], environment=self._environment,
                                              updated_at=self._clock(), key_id=self._key.anchor_key_id)
        except PA.PrivacyAnchorError as exc:
            return _refused(exc.code)
        if body["setHead"] != payload["expectedSetHead"]:
            return _refused("ANCHOR_PIN_MISMATCH")                 # pin before commit: nothing is signed
        try:
            signed = self._key.sign_privacy_anchor(docs, body)
        except ValueError:
            return _refused("ANCHOR_SIGNING_REFUSED")
        self._store.commit(body["anchorVersion"], signed)
        committed = self._chain(self._store.documents())
        if committed is None or committed.digest != PA.anchor_digest(signed):
            raise AnchorStoreFailClosed("COMMIT_MISMATCH")
        return {"status": "COMMITTED", "anchorVersion": committed.version, "anchorDigest": committed.digest,
                "setHead": committed.set_head, "suppressionCount": committed.count, "document": signed}
