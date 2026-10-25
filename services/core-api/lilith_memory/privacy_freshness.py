"""Track B: fail-closed Privacy freshness for memory serving, and the root boot-freshness steps (path b, manual).

Design record: F9-C anchor design revision 1 §1-§2, §4-§5 (owner-approved final architecture, 2026-10-24).

* ``PrivacyFreshnessGate`` (Core API, read-only, re-evaluated on every call; no readiness flag): memory reads and
  admissions are served only while ALL of these hold:
    - a root-published freshness marker exists for THIS boot (tmpfs; gone after every reboot, so a whole-host
      rollback can never inherit one), root-owned and not group/world-writable;
    - no FORGET intent is pending (hold-first defense in depth);
    - the local Privacy suppression set equals the anchored set S the marker names (L == S). A restored or replaced
      Privacy database (L strictly older) is OLDER_THAN_ANCHOR, a FORGET not yet anchored and checkpointed is
      ANCHOR_BEHIND, anything else DIVERGED. All refuse; none is ever reported as "not held".
* ``FreshPrivacyHoldResolver``: the freshness gate composed in front of the existing restore-suppression resolver
  (F9-C ``GatedPrivacyHoldResolver``). ``memory_v2.restore_gated_hold_resolver`` requires one.
* ``DurabilityBarrier``: durable-before-erase for the FORGET runner. Owners may erase only when the CURRENT local
  suppression set (including the new FORGET's rows) is anchored and covered by a verified owner checkpoint.
* Root steps (``issue_challenge`` / ``apply_unlock`` / ``apply_checkpoint``): verify with the pure contracts in
  ``privacy_anchor_contracts`` and publish the marker. They hold no key; the K-PCK signature comes from the owner
  device and the K-PAN anchor chain from the witness.

Not covered here (governed, separate approval): the witness K-PAN module and credential, K-PAN/K-PCK custody
ceremonies, root units/installation, and the unattended path (a) service E.
"""

from __future__ import annotations

import json
import os
import sqlite3
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

try:
    from . import privacy_anchor_contracts as A
except ImportError:  # deploy-exact flat-directory tests
    import privacy_anchor_contracts as A

MARKER_VERSION = 1
MARKER_FIELDS = frozenset({"v", "environment", "bootId", "anchorVersion", "anchorDigest", "setHead",
                           "suppressionCount", "checkpointSeq", "checkpointDigest", "checkpointAnchorVersion",
                           "unlockDigest", "verifiedAt"})
DEFAULT_MARKER = Path("/run/lilith-privacy-fresh/verified")
DEFAULT_INTENT_DIR = Path("/var/lib/hermes-forget/intent")
BOOT_ID_PATH = Path("/proc/sys/kernel/random/boot_id")

READY = "READY"
MARKER_UNAVAILABLE = "FRESHNESS_MARKER_UNAVAILABLE"
MARKER_UNTRUSTED = "FRESHNESS_MARKER_UNTRUSTED"
MARKER_INVALID = "FRESHNESS_MARKER_INVALID"
STALE_BOOT = "FRESHNESS_STALE_BOOT"
INTENT_PENDING = "FORGET_INTENT_PENDING"
PRIVACY_UNREADABLE = "PRIVACY_STATE_UNREADABLE"
ANCHOR_BEHIND = "ANCHOR_BEHIND"
OLDER_THAN_ANCHOR = "OLDER_THAN_ANCHOR"
DIVERGED = "DIVERGED"
CHECKPOINT_PENDING = "CHECKPOINT_PENDING"


class PrivacyFreshnessNotReady(PermissionError):
    """Memory serving refused: Privacy freshness is not established (an explicit refusal, never a miss)."""

    def __init__(self, code: str):
        super().__init__("PRIVACY_FRESHNESS_NOT_READY:" + code)
        self.code = code


class FreshnessStepRefused(RuntimeError):
    """A root freshness step refused; nothing was published."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def read_boot_id(path: Path = BOOT_ID_PATH) -> str:
    return path.read_text(encoding="ascii").strip()


def local_suppression_entries(privacy_db: Path) -> list:
    """Read-only: the (suppression_ref_id, identity_selector) set of Privacy's append-only manifest."""
    conn = sqlite3.connect(f"{Path(privacy_db).resolve().as_uri()}?mode=ro", uri=True)
    try:
        return [(str(r[0]), str(r[1])) for r in conn.execute(
            "SELECT suppression_ref_id, identity_selector FROM privacy_restore_suppression_manifest")]
    finally:
        conn.close()


def local_set_state(privacy_db: Path, environment: str) -> tuple:
    entries = local_suppression_entries(privacy_db)
    return len(entries), A.suppression_set_head(environment, entries)


@dataclass(frozen=True)
class FreshnessCheck:
    status: str
    marker: Optional[Mapping[str, Any]] = None
    local_count: int = 0

    @property
    def ready(self) -> bool:
        return self.status == READY


def _trusted_file(path: Path, require_root: bool) -> bool:
    st = os.lstat(path)
    if not stat.S_ISREG(st.st_mode):
        return False
    if os.name != "posix":                    # no owner/mode semantics: only an untrusting test setup may pass
        return not require_root
    return not st.st_mode & 0o022 and (not require_root or st.st_uid == 0)


def load_marker(path: Path, *, require_root: bool = True) -> Mapping[str, Any]:
    try:
        if not _trusted_file(path, require_root):
            raise PrivacyFreshnessNotReady(MARKER_UNTRUSTED)
        doc = json.loads(path.read_bytes().decode("ascii"))
    except FileNotFoundError as exc:
        raise PrivacyFreshnessNotReady(MARKER_UNAVAILABLE) from exc
    except PrivacyFreshnessNotReady:
        raise
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise PrivacyFreshnessNotReady(MARKER_INVALID) from exc
    if not isinstance(doc, dict) or set(doc) != MARKER_FIELDS or doc["v"] != MARKER_VERSION:
        raise PrivacyFreshnessNotReady(MARKER_INVALID)
    return doc


class PrivacyFreshnessGate:
    """Read-only pre-serve freshness gate (see the module docstring). Every call re-reads the marker, the intent
    directory and the Privacy manifest; there is no cached state and no tolerance flag."""

    def __init__(self, privacy_db: Path, *, environment: str, marker_path: Path = DEFAULT_MARKER,
                 intent_dir: Path = DEFAULT_INTENT_DIR, boot_id: Callable[[], str] = read_boot_id,
                 require_root_marker: bool = True):
        self._privacy_db = Path(privacy_db)
        self._environment = environment
        self._marker_path = Path(marker_path)
        self._intent_dir = Path(intent_dir)
        self._boot_id = boot_id
        self._require_root = require_root_marker

    def _set_status(self, marker: Mapping[str, Any]) -> FreshnessCheck:
        try:
            count, head = local_set_state(self._privacy_db, self._environment)
        except A.PrivacyAnchorError:
            return FreshnessCheck(DIVERGED, marker)              # duplicated / malformed suppression rows
        except (sqlite3.Error, OSError):
            return FreshnessCheck(PRIVACY_UNREADABLE, marker)
        if head == marker["setHead"] and count == marker["suppressionCount"]:
            return FreshnessCheck(READY, marker, count)
        if count > marker["suppressionCount"]:
            return FreshnessCheck(ANCHOR_BEHIND, marker, count)
        if count < marker["suppressionCount"]:
            return FreshnessCheck(OLDER_THAN_ANCHOR, marker, count)
        return FreshnessCheck(DIVERGED, marker, count)

    def _marker(self) -> Mapping[str, Any]:
        marker = load_marker(self._marker_path, require_root=self._require_root)
        if marker["environment"] != self._environment:
            raise PrivacyFreshnessNotReady(MARKER_INVALID)
        try:
            current = self._boot_id()
        except OSError as exc:
            raise PrivacyFreshnessNotReady(STALE_BOOT) from exc
        if marker["bootId"] != current:
            raise PrivacyFreshnessNotReady(STALE_BOOT)
        return marker

    def check(self) -> FreshnessCheck:
        try:
            marker = self._marker()
        except PrivacyFreshnessNotReady as exc:
            return FreshnessCheck(exc.code)
        try:
            pending = any(p.name.endswith(".intent") for p in self._intent_dir.iterdir())
        except FileNotFoundError:
            pending = False
        except OSError:
            return FreshnessCheck(INTENT_PENDING, marker)        # cannot prove there is none: refuse
        if pending:
            return FreshnessCheck(INTENT_PENDING, marker)
        return self._set_status(marker)

    def durability(self) -> FreshnessCheck:
        """For the FORGET runner's barrier: the marker of this boot, L == S, and S covered by the owner checkpoint.
        Ignores the pending intent (the FORGET being run is that intent)."""
        try:
            marker = self._marker()
        except PrivacyFreshnessNotReady as exc:
            return FreshnessCheck(exc.code)
        result = self._set_status(marker)
        if result.ready and marker["checkpointAnchorVersion"] != marker["anchorVersion"]:
            return FreshnessCheck(CHECKPOINT_PENDING, marker, result.local_count)
        return result

    def require_ready(self) -> None:
        result = self.check()
        if not result.ready:
            raise PrivacyFreshnessNotReady(result.status)


class FreshPrivacyHoldResolver:
    """The privacy_hold_resolver for memory serving: Privacy freshness first (a stale Privacy store makes every
    suppression answer meaningless), then the F9-C restore-suppression resolver, then Privacy's hold answer."""

    def __init__(self, inner: Any, freshness: PrivacyFreshnessGate):
        if not isinstance(freshness, PrivacyFreshnessGate):
            raise TypeError("a PrivacyFreshnessGate is required")
        if not callable(getattr(inner, "require_ready", None)) or not callable(getattr(inner, "is_held", None)):
            raise TypeError("a gated Privacy hold resolver is required")
        self._inner = inner
        self._freshness = freshness

    def require_ready(self) -> None:
        self._freshness.require_ready()
        self._inner.require_ready()

    def is_held(self, memory_class: str, subject_namespace: str, subject_key: str) -> bool:
        self._freshness.require_ready()
        return self._inner.is_held(memory_class, subject_namespace, subject_key)


class DurabilityBarrier:
    """Durable-before-erase (revision 1 §1): returns None when owners may erase, else a stable refusal code."""

    def __init__(self, freshness: PrivacyFreshnessGate):
        if not isinstance(freshness, PrivacyFreshnessGate):
            raise TypeError("a PrivacyFreshnessGate is required")
        self._freshness = freshness

    def __call__(self) -> Optional[str]:
        result = self._freshness.durability()
        return None if result.ready else "DURABILITY_BARRIER:" + result.status


# ------------------------------------------------------------------------------------------- root steps ---

@dataclass(frozen=True)
class FreshnessKeys:
    """Public keys and key ids only (pins installed by the governed release; never private material)."""

    environment: str
    anchor_key: Any
    anchor_key_id: str
    checkpoint_key: Any
    checkpoint_key_id: str


def _chain(keys: FreshnessKeys, anchor_docs: Sequence[Any]) -> A.AnchorChainV1:
    try:
        return A.verify_anchor_chain(anchor_docs, keys.anchor_key, environment=keys.environment,
                                     key_id=keys.anchor_key_id)
    except A.PrivacyAnchorError as exc:
        raise FreshnessStepRefused("ANCHOR_CHAIN_" + exc.code) from exc


def _require_local_equals(chain: A.AnchorChainV1, privacy_db: Path) -> None:
    try:
        entries = local_suppression_entries(privacy_db)
        head = A.suppression_set_head(chain.environment, entries)
    except (A.PrivacyAnchorError, sqlite3.Error, OSError) as exc:
        raise FreshnessStepRefused(PRIVACY_UNREADABLE) from exc
    local = set(entries)
    if head == chain.set_head and len(local) == chain.count:
        return
    if chain.entries < local:
        raise FreshnessStepRefused(ANCHOR_BEHIND)
    if local < chain.entries:
        raise FreshnessStepRefused(OLDER_THAN_ANCHOR)
    raise FreshnessStepRefused(DIVERGED)


def write_marker(path: Path, marker: Mapping[str, Any]) -> None:
    """Atomic publish (root): temp file, fsync, rename, directory fsync. Mode 0644 so the Core API can read it."""
    if set(marker) != MARKER_FIELDS:
        raise FreshnessStepRefused(MARKER_INVALID)
    path = Path(path)
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    data = json.dumps(dict(marker), sort_keys=True, separators=(",", ":")).encode("ascii")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o644)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)
    if hasattr(os, "O_DIRECTORY"):
        dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)


def issue_challenge(keys: FreshnessKeys, anchor_docs: Sequence[Any], privacy_db: Path, *, boot_id: str,
                    nonce: str, issued_at: str) -> Mapping[str, Any]:
    """Boot step 1 (root): the host's challenge. Refuses unless the local Privacy set equals the anchored set."""
    chain = _chain(keys, anchor_docs)
    _require_local_equals(chain, privacy_db)
    return A.make_challenge(chain, environment=keys.environment, boot_id=boot_id, nonce=nonce, issued_at=issued_at)


def apply_unlock(keys: FreshnessKeys, anchor_docs: Sequence[Any], privacy_db: Path, challenge: Mapping[str, Any],
                 unlock: Mapping[str, Any], checkpoint: Mapping[str, Any], *, boot_id: str, nonce: str,
                 verified_at: str, marker_path: Path = DEFAULT_MARKER) -> Mapping[str, Any]:
    """Boot step 2 (root): verify the owner's K-PCK unlock for THIS boot's challenge and publish the marker."""
    chain = _chain(keys, anchor_docs)
    result = A.classify_boot_freshness(challenge, unlock, checkpoint, chain, keys.checkpoint_key,
                                       environment=keys.environment, checkpoint_key_id=keys.checkpoint_key_id,
                                       boot_id=boot_id, nonce=nonce)
    if not result.fresh:
        raise FreshnessStepRefused(result.status + (":" + result.code if result.code else ""))
    _require_local_equals(chain, privacy_db)
    marker = {"v": MARKER_VERSION, "environment": keys.environment, "bootId": boot_id,
              "anchorVersion": chain.version, "anchorDigest": chain.digest, "setHead": chain.set_head,
              "suppressionCount": chain.count, "checkpointSeq": result.checkpoint_seq,
              "checkpointDigest": A.checkpoint_digest(checkpoint),
              "checkpointAnchorVersion": result.checkpoint_anchor_version, "unlockDigest": result.unlock_digest,
              "verifiedAt": verified_at}
    write_marker(marker_path, marker)
    return marker


def apply_checkpoint(keys: FreshnessKeys, anchor_docs: Sequence[Any], privacy_db: Path,
                     checkpoint: Mapping[str, Any], *, boot_id: str, verified_at: str,
                     marker_path: Path = DEFAULT_MARKER, require_root_marker: bool = True) -> Mapping[str, Any]:
    """After a FORGET's anchor advance (root): accept the owner's next checkpoint, which must extend the one this
    boot's marker was unlocked with and cover the CURRENT anchor head, then republish the marker (L == S again).
    This is the only way past the durability barrier."""
    try:
        current = load_marker(marker_path, require_root=require_root_marker)
    except PrivacyFreshnessNotReady as exc:
        raise FreshnessStepRefused(exc.code) from exc
    if current["bootId"] != boot_id or current["environment"] != keys.environment:
        raise FreshnessStepRefused(STALE_BOOT)
    chain = _chain(keys, anchor_docs)
    try:
        A.verify_checkpoint(checkpoint, keys.checkpoint_key, environment=keys.environment,
                            key_id=keys.checkpoint_key_id)
    except A.PrivacyAnchorError as exc:
        raise FreshnessStepRefused("CHECKPOINT_" + exc.code) from exc
    if checkpoint["checkpointSeq"] != current["checkpointSeq"] + 1 or \
            checkpoint["previousCheckpointDigest"] != current["checkpointDigest"] or \
            checkpoint["anchorVersion"] <= current["checkpointAnchorVersion"]:
        raise FreshnessStepRefused("CHECKPOINT_NOT_AN_EXTENSION")
    if checkpoint["anchorVersion"] != chain.version:
        raise FreshnessStepRefused("CHECKPOINT_NOT_CURRENT_HEAD")
    status = A.checkpoint_matches_anchor(checkpoint, chain)
    if status != A.FRESH:
        raise FreshnessStepRefused(status)
    if current["anchorVersion"] > chain.version or chain.at(current["anchorVersion"])[0] != current["anchorDigest"]:
        raise FreshnessStepRefused(DIVERGED)                      # the host chain does not extend this boot's
    _require_local_equals(chain, privacy_db)
    marker = dict(current)
    marker.update({"anchorVersion": chain.version, "anchorDigest": chain.digest, "setHead": chain.set_head,
                   "suppressionCount": chain.count, "checkpointSeq": checkpoint["checkpointSeq"],
                   "checkpointDigest": A.checkpoint_digest(checkpoint),
                   "checkpointAnchorVersion": checkpoint["anchorVersion"], "verifiedAt": verified_at})
    write_marker(marker_path, marker)
    return marker
