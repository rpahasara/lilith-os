"""F9-C Privacy rollback anchor: LOCAL PROTOTYPE of the proposed contracts (not a governed module; not installed).

Proposal (F9C-ROLLBACK-ANCHOR-DESIGN.md): the recovery WITNESS (an established, independently keyed freshness
boundary: "freshness evidence only, never authority") keeps a signed, hash-chained anchor of Privacy's suppression
state. Privacy itself is unchanged: its restore-suppression manifest is append-only and immutable, so the SET of its
(suppression_ref_id, identity_selector) entries identifies the suppression state exactly. The commitment is over the
sorted set, never over SQLite rowids (VACUUM may renumber rowids of tables without an INTEGER PRIMARY KEY):

    head = H("LILITH-PRIVACY-SUPPRESSION-SET-V1" | environment | sorted entries)   (selectors are opaque keyed HMACs)

An anchor advance carries the newly added entries; the witness rebuilds its anchored set from its own history, so it
verifies "new set = anchored set + new entries" without any Privacy access. The pre-serve check compares the local set
L with the anchored set S of the witness's current signed anchor (S is served by the witness and must hash to the
signed head):

    L == S                         -> AT_OR_AFTER_REQUIRED   (the only serving state)
    L strictly contains S          -> ANCHOR_BEHIND          (suppression not yet anchored)
    L strictly contained in S      -> OLDER_THAN_REQUIRED    (rolled back / restored)
    neither                        -> DIVERGED               (forked, tampered, inconsistent)
    no / invalid / replayed anchor -> UNAVAILABLE / UNVERIFIABLE / REPLAYED

Statuses map onto recovery_contracts.PrivacyBoundaryObservationV1 (AT_OR_AFTER_REQUIRED / OLDER_THAN_REQUIRED /
UNAVAILABLE). A governed recovery re-appends the anchored entries a restored Privacy lost (opaque values only).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

SET_DOMAIN = b"LILITH-PRIVACY-SUPPRESSION-SET-V1"
ANCHOR_DOMAIN = b"LILITH-PRIVACY-ANCHOR-V1\x00"
PROTOCOL, SCHEMA = "lilith.privacy-anchor", 1
AT_OR_AFTER, OLDER, DIVERGED, AHEAD = "AT_OR_AFTER_REQUIRED", "OLDER_THAN_REQUIRED", "DIVERGED", "ANCHOR_BEHIND"
UNAVAILABLE, UNVERIFIABLE, REPLAYED = "UNAVAILABLE", "UNVERIFIABLE", "REPLAYED"
SIGNED_FIELDS = ("protocol", "schemaVersion", "environment", "anchorVersion", "previousAnchorDigest",
                 "suppressionCount", "setHead", "appended", "updatedAt", "witnessKeyId")
Entry = Tuple[str, str]


class AnchorError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _h(*parts: bytes) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(len(p).to_bytes(4, "big") + p)
    return h.hexdigest()


def set_head(environment: str, entries: Sequence[Entry]) -> str:
    parts = [SET_DOMAIN, environment.encode()]
    for ref, selector in sorted(set(map(tuple, entries))):
        parts += [ref.encode(), selector.encode()]
    return _h(*parts)


def suppression_entries(privacy_db: Path) -> List[Entry]:
    """Read-only. The manifest is append-only and immutable (Privacy triggers); order is irrelevant (a set)."""
    conn = sqlite3.connect(f"{Path(privacy_db).resolve().as_uri()}?mode=ro", uri=True)
    try:
        return [(str(r[0]), str(r[1])) for r in conn.execute(
            "SELECT suppression_ref_id, identity_selector FROM privacy_restore_suppression_manifest")]
    finally:
        conn.close()


def high_water(privacy_db: Path, environment: str) -> Tuple[int, str, List[Entry]]:
    entries = suppression_entries(privacy_db)
    if len(set(entries)) != len(entries):
        raise AnchorError(DIVERGED)                         # duplicated suppression rows: an inconsistent store
    return len(entries), set_head(environment, entries), entries


def _canonical(doc: Mapping[str, Any]) -> bytes:
    return json.dumps({k: doc[k] for k in SIGNED_FIELDS}, sort_keys=True, separators=(",", ":")).encode("ascii")


def anchor_digest(doc: Mapping[str, Any]) -> str:
    return hashlib.sha256(ANCHOR_DOMAIN + _canonical(doc)).hexdigest()


def verify_anchor(doc: Mapping[str, Any], public_key: Ed25519PublicKey, *, environment: str,
                  witness_key_id: str) -> None:
    if not isinstance(doc, Mapping) or set(doc) != set(SIGNED_FIELDS) | {"signature"}:
        raise AnchorError(UNVERIFIABLE)
    if doc["protocol"] != PROTOCOL or doc["schemaVersion"] != SCHEMA or doc["environment"] != environment \
            or doc["witnessKeyId"] != witness_key_id:
        raise AnchorError(UNVERIFIABLE)
    try:
        public_key.verify(bytes.fromhex(doc["signature"]), ANCHOR_DOMAIN + _canonical(doc))
    except (InvalidSignature, ValueError) as exc:
        raise AnchorError(UNVERIFIABLE) from exc


class WitnessAnchorStore:
    """The witness side (simulated): the only signer of anchors; accepts an advance only as a verified set extension.
    Persistence is atomic (all or nothing); a failed advance leaves the current anchor unchanged."""

    def __init__(self, environment: str, key_id: str = "test-only.witness.privacy-anchor", *,
                 key: Optional[Ed25519PrivateKey] = None, path: Optional[Path] = None):
        self.environment, self.key_id = environment, key_id
        self._key = key or Ed25519PrivateKey.generate()
        self.public_key = self._key.public_key()
        self.path = path
        self.history: List[Dict[str, Any]] = []
        self.fail_next_persist = False

    @property
    def current(self) -> Optional[Dict[str, Any]]:
        return self.history[-1] if self.history else None

    def anchored_entries(self) -> List[Entry]:
        return [tuple(e) for doc in self.history for e in doc["appended"]]

    def _sign(self, unsigned: Dict[str, Any]) -> Dict[str, Any]:
        return {**unsigned, "signature": self._key.sign(ANCHOR_DOMAIN + _canonical(unsigned)).hex()}

    def _persist(self, doc: Dict[str, Any]) -> None:
        if self.fail_next_persist:                         # power loss / disk error before the durable write
            self.fail_next_persist = False
            raise AnchorError("ANCHOR_WRITE_FAILED")
        self.history.append(doc)
        if self.path is not None:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.history))
            tmp.replace(self.path)

    def genesis(self, count: int, head: str, entries: Sequence[Entry], at: str) -> Dict[str, Any]:
        """Owner-approved ceremony: anchors the CURRENT Privacy suppression state (migration of an existing DB)."""
        if self.history:
            raise AnchorError("ANCHOR_ALREADY_PROVISIONED")
        if set_head(self.environment, entries) != head or len(set(map(tuple, entries))) != count:
            raise AnchorError("ANCHOR_GENESIS_INCONSISTENT")
        doc = self._sign({"protocol": PROTOCOL, "schemaVersion": SCHEMA, "environment": self.environment,
                          "anchorVersion": 1, "previousAnchorDigest": None, "suppressionCount": count,
                          "setHead": head, "appended": sorted(list(e) for e in entries), "updatedAt": at,
                          "witnessKeyId": self.key_id})
        self._persist(doc)
        return doc

    def advance(self, appended: Sequence[Entry], new_head: str, at: str) -> Dict[str, Any]:
        cur = self.current
        if cur is None:
            raise AnchorError("ANCHOR_NOT_PROVISIONED")
        if not appended:
            return cur                                     # idempotent: nothing new to anchor
        anchored = set(self.anchored_entries())
        added = set(map(tuple, appended))
        if len(added) != len(appended) or added & anchored or set_head(self.environment, anchored | added) != new_head:
            raise AnchorError("ANCHOR_NOT_AN_EXTENSION")   # duplicate, already anchored, or not this set
        if at < cur["updatedAt"]:
            raise AnchorError("ANCHOR_TIME_REGRESSION")
        doc = self._sign({"protocol": PROTOCOL, "schemaVersion": SCHEMA, "environment": self.environment,
                          "anchorVersion": cur["anchorVersion"] + 1, "previousAnchorDigest": anchor_digest(cur),
                          "suppressionCount": len(anchored | added), "setHead": new_head,
                          "appended": sorted(list(e) for e in added), "updatedAt": at, "witnessKeyId": self.key_id})
        self._persist(doc)
        return doc


def advance_from_privacy(store: WitnessAnchorStore, privacy_db: Path, at: str) -> Dict[str, Any]:
    """The Privacy-side client: send exactly the entries the witness has not anchored yet (idempotent retry)."""
    _count, head, entries = high_water(privacy_db, store.environment)
    if store.current is None:
        raise AnchorError("ANCHOR_NOT_PROVISIONED")
    anchored, local = set(store.anchored_entries()), set(entries)
    if not anchored <= local:
        raise AnchorError(OLDER if local < anchored else DIVERGED)
    return store.advance(sorted(local - anchored), head, at)


@dataclass(frozen=True)
class AnchorCheck:
    status: str
    local_count: int = 0
    anchor_count: int = 0

    @property
    def ready(self) -> bool:
        return self.status == AT_OR_AFTER


def check(privacy_db: Path, anchor: Optional[Mapping[str, Any]], public_key: Ed25519PublicKey, *,
          environment: str, witness_key_id: str, last_seen_version: int = 0,
          anchored_entries: Optional[Sequence[Entry]] = None) -> AnchorCheck:
    """The pre-serve comparison. Fails closed on anything but exact agreement with a verified, fresh anchor.
    ``anchored_entries`` is the anchored set as served by the witness; it must hash to the signed head."""
    if anchor is None:
        return AnchorCheck(UNAVAILABLE)
    try:
        verify_anchor(anchor, public_key, environment=environment, witness_key_id=witness_key_id)
    except AnchorError:
        return AnchorCheck(UNVERIFIABLE)
    a_count = int(anchor["suppressionCount"])
    if anchor["anchorVersion"] < last_seen_version:
        return AnchorCheck(REPLAYED, anchor_count=a_count)
    try:
        count, head, entries = high_water(privacy_db, environment)
    except AnchorError:
        return AnchorCheck(DIVERGED, anchor_count=a_count)
    except (sqlite3.Error, OSError):
        return AnchorCheck(UNAVAILABLE)
    if head == anchor["setHead"] and count == a_count:
        return AnchorCheck(AT_OR_AFTER, count, a_count)
    if anchored_entries is None or set_head(environment, anchored_entries) != anchor["setHead"] \
            or len(set(map(tuple, anchored_entries))) != a_count:
        return AnchorCheck(UNVERIFIABLE, count, a_count)  # cannot classify the mismatch: still refused
    local, anchored = set(entries), set(map(tuple, anchored_entries))
    if anchored < local:
        return AnchorCheck(AHEAD, count, a_count)
    if local < anchored:
        return AnchorCheck(OLDER, count, a_count)
    return AnchorCheck(DIVERGED, count, a_count)


def resuppress_from_anchor(privacy_db: Path, store: WitnessAnchorStore, *, authority: str, at: str) -> int:
    """Governed recovery after a legitimate restore of an older Privacy DB: re-add exactly the opaque suppression rows
    the restore lost. Refuses unless the restored DB's set is contained in the anchored set. (A real tool runs offline
    with the Core API stopped, as an owner-approved recovery procedure.)"""
    anchored = set(store.anchored_entries())
    local = set(suppression_entries(privacy_db))
    if not local <= anchored:
        raise AnchorError(DIVERGED)                         # the restored DB holds suppressions the anchor never saw
    missing = sorted(anchored - local)
    conn = sqlite3.connect(privacy_db)
    try:
        conn.execute("BEGIN IMMEDIATE")
        for ref, selector in missing:
            conn.execute("INSERT INTO privacy_restore_suppression_manifest VALUES (?,?,?,?,?,?)",
                         (ref, authority, selector, "ACTIVE", at, None))
        conn.commit()
    finally:
        conn.close()
    return len(missing)


def utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
