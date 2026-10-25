"""Track B: Privacy rollback-protection contracts (pure; no I/O, no key material, no clock).

Design record: F9-C anchor design revision 1 (owner-approved final architecture, 2026-10-24), C-1 / C-8 / C-10.

Three signed documents, three distinct signing domains, two distinct key families:

* ``PrivacyAnchorV1`` (K-PAN, held by the recovery witness): a hash chain over the SET of Privacy's append-only
  restore-suppression manifest entries ``(suppression_ref_id, identity_selector)``. Each advance appends only new
  entries; the commitment is over the sorted set, never SQLite rowids (VACUUM may renumber them).
* ``PrivacyDurabilityCheckpointV1`` (K-PCK, owner-held, never on the host): an off-host, extension-only chain that
  signs an anchor head. Durable-before-erase: a FORGET's owners erase only after its anchor version is checkpointed.
* ``PrivacyFreshnessUnlockV1`` (K-PCK): the manual boot unlock (path b). It answers one host challenge (fresh nonce,
  boot id, the host anchor head) with the owner's latest checkpoint, so a replayed or stale statement never passes.

K-PAN and K-PCK are separate from K-ROOT, K-WIT and every authority or broker key: their key ids carry their own
prefixes and every document is verified under its own domain, so no key of one family can sign another's document.

``classify_boot_freshness`` is the host-side rule: a whole-host rollback (host anchor older than the owner's
checkpoint) is OLDER_THAN_CHECKPOINT, a fork is DIVERGED, a mismatched nonce or boot is REPLAYED, and anything
unverifiable is UNVERIFIABLE. Only FRESH passes.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SET_DOMAIN = b"LILITH-PRIVACY-SUPPRESSION-SET-V1"
ANCHOR_DOMAIN = b"LILITH-PRIVACY-ANCHOR-V1\x00"
CHECKPOINT_DOMAIN = b"LILITH-PRIVACY-CHECKPOINT-V1\x00"
CHALLENGE_DOMAIN = b"LILITH-PRIVACY-FRESHNESS-CHALLENGE-V1\x00"
UNLOCK_DOMAIN = b"LILITH-PRIVACY-FRESHNESS-UNLOCK-V1\x00"

ANCHOR_PROTOCOL = "lilith.privacy-anchor"
CHECKPOINT_PROTOCOL = "lilith.privacy-checkpoint"
CHALLENGE_PROTOCOL = "lilith.privacy-freshness-challenge"
UNLOCK_PROTOCOL = "lilith.privacy-freshness-unlock"
SCHEMA_VERSION = 1

KPAN_KEY_PREFIX = "kpan."   # Privacy anchor signing key (witness-custodied)
KPCK_KEY_PREFIX = "kpck."   # Privacy checkpoint key (owner-held, off-host)

ANCHOR_FIELDS = ("protocol", "schemaVersion", "environment", "anchorVersion", "previousAnchorDigest",
                 "suppressionCount", "setHead", "appended", "updatedAt", "anchorKeyId")
CHECKPOINT_FIELDS = ("protocol", "schemaVersion", "environment", "checkpointSeq", "previousCheckpointDigest",
                     "anchorVersion", "anchorDigest", "setHead", "suppressionCount", "checkpointedAt",
                     "checkpointKeyId")
CHALLENGE_FIELDS = ("protocol", "schemaVersion", "environment", "bootId", "nonce", "anchorVersion", "anchorDigest",
                    "setHead", "suppressionCount", "issuedAt")
UNLOCK_FIELDS = ("protocol", "schemaVersion", "environment", "bootId", "nonce", "challengeDigest", "checkpointSeq",
                 "checkpointDigest", "unlockedAt", "checkpointKeyId")

# Boot freshness statuses (only FRESH passes).
FRESH = "FRESH"
OLDER_THAN_CHECKPOINT = "OLDER_THAN_CHECKPOINT"
DIVERGED = "DIVERGED"
REPLAYED = "REPLAYED"
UNVERIFIABLE = "UNVERIFIABLE"

Entry = Tuple[str, str]
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_KEY_ID = re.compile(r"^[a-z0-9][a-z0-9._:-]{2,126}$")
_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$")
_TOKEN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class PrivacyAnchorError(ValueError):
    """Stable, content-free refusal code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PrivacyAnchorError(code)


def _h(*parts: bytes) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(len(part).to_bytes(4, "big") + part)
    return h.hexdigest()


def _entries(entries: Iterable[Sequence[str]]) -> FrozenSet[Entry]:
    out: List[Entry] = []
    for entry in entries:
        _require(isinstance(entry, (list, tuple)) and len(entry) == 2, "ENTRY_INVALID")
        ref, selector = entry
        _require(isinstance(ref, str) and _TOKEN.match(ref) is not None, "ENTRY_INVALID")
        _require(isinstance(selector, str) and _HEX64.match(selector) is not None, "ENTRY_INVALID")
        out.append((ref, selector))
    result = frozenset(out)
    _require(len(result) == len(out), "ENTRY_DUPLICATED")
    return result


def suppression_set_head(environment: str, entries: Iterable[Sequence[str]]) -> str:
    """The commitment over a suppression set (order-free; duplicates are an inconsistent store and refused)."""
    _require(isinstance(environment, str) and _TOKEN.match(environment) is not None, "ENVIRONMENT_INVALID")
    parts = [SET_DOMAIN, environment.encode("ascii")]
    for ref, selector in sorted(_entries(entries)):
        parts += [ref.encode("ascii"), selector.encode("ascii")]
    return _h(*parts)


def _canonical(doc: Mapping[str, Any], fields: Sequence[str]) -> bytes:
    return json.dumps({k: doc[k] for k in fields}, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def _digest(domain: bytes, doc: Mapping[str, Any], fields: Sequence[str]) -> str:
    return hashlib.sha256(domain + _canonical(doc, fields)).hexdigest()


def signing_bytes(kind: str, doc: Mapping[str, Any]) -> bytes:
    """The exact bytes a signer signs (used by the witness, the owner tool and tests; verification uses the same)."""
    domain, fields = _KINDS[kind]
    return domain + _canonical(doc, fields)


def _check_shape(doc: Any, fields: Sequence[str], signed: bool) -> None:
    _require(isinstance(doc, Mapping), "DOCUMENT_INVALID")
    expected = set(fields) | ({"signature"} if signed else set())
    _require(set(doc) == expected, "DOCUMENT_FIELDS_INVALID")


def _verify_signature(kind: str, doc: Mapping[str, Any], public_key: Ed25519PublicKey) -> None:
    signature = doc.get("signature")
    _require(isinstance(signature, str) and re.fullmatch(r"[0-9a-f]{128}", signature) is not None,
             "SIGNATURE_INVALID")
    try:
        public_key.verify(bytes.fromhex(signature), signing_bytes(kind, doc))
    except (InvalidSignature, ValueError) as exc:
        raise PrivacyAnchorError("SIGNATURE_INVALID") from exc


def _common(doc: Mapping[str, Any], protocol: str, environment: str) -> None:
    _require(doc["protocol"] == protocol and doc["schemaVersion"] == SCHEMA_VERSION, "PROTOCOL_INVALID")
    _require(doc["environment"] == environment, "ENVIRONMENT_MISMATCH")


def _positive(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _key_id(value: Any, prefix: str) -> None:
    _require(isinstance(value, str) and _KEY_ID.match(value) is not None and value.startswith(prefix),
             "KEY_FAMILY_INVALID")


def _time(value: Any) -> None:
    _require(isinstance(value, str) and _TIME.match(value) is not None, "TIME_INVALID")


# ---------------------------------------------------------------------------------------------------- anchor ---

def anchor_digest(doc: Mapping[str, Any]) -> str:
    return _digest(ANCHOR_DOMAIN, doc, ANCHOR_FIELDS)


def verify_anchor(doc: Any, public_key: Ed25519PublicKey, *, environment: str, key_id: str) -> None:
    """One anchor document: shape, family, signature (K-PAN)."""
    _check_shape(doc, ANCHOR_FIELDS, True)
    _common(doc, ANCHOR_PROTOCOL, environment)
    _key_id(doc["anchorKeyId"], KPAN_KEY_PREFIX)
    _require(doc["anchorKeyId"] == key_id, "KEY_ID_MISMATCH")
    _require(_positive(doc["anchorVersion"]) and _count(doc["suppressionCount"]), "ANCHOR_INVALID")
    _require(isinstance(doc["setHead"], str) and _HEX64.match(doc["setHead"]) is not None, "ANCHOR_INVALID")
    _require(isinstance(doc["appended"], list), "ANCHOR_INVALID")
    _time(doc["updatedAt"])
    _verify_signature("anchor", doc, public_key)


@dataclass(frozen=True)
class AnchorChainV1:
    """A verified anchor chain: the anchored set S and every version's digest / head / count."""

    environment: str
    entries: FrozenSet[Entry]
    digests: Tuple[str, ...]          # digests[v - 1] = digest of version v
    heads: Tuple[str, ...]
    counts: Tuple[int, ...]

    @property
    def version(self) -> int:
        return len(self.digests)

    @property
    def digest(self) -> str:
        return self.digests[-1]

    @property
    def set_head(self) -> str:
        return self.heads[-1]

    @property
    def count(self) -> int:
        return self.counts[-1]

    def at(self, version: int) -> Tuple[str, str, int]:
        _require(1 <= version <= self.version, "ANCHOR_VERSION_UNKNOWN")
        return self.digests[version - 1], self.heads[version - 1], self.counts[version - 1]


def verify_anchor_chain(docs: Sequence[Any], public_key: Ed25519PublicKey, *, environment: str,
                        key_id: str) -> AnchorChainV1:
    """The whole chain from genesis: each advance is version + 1, links the previous digest, appends only entries the
    chain has never seen (genesis may be empty), and its head/count are exactly those of the accumulated set."""
    _require(isinstance(docs, (list, tuple)) and len(docs) >= 1, "ANCHOR_CHAIN_EMPTY")
    entries: FrozenSet[Entry] = frozenset()
    digests: List[str] = []
    heads: List[str] = []
    counts: List[int] = []
    previous: Optional[Mapping[str, Any]] = None
    for index, doc in enumerate(docs):
        verify_anchor(doc, public_key, environment=environment, key_id=key_id)
        _require(doc["anchorVersion"] == index + 1, "ANCHOR_CHAIN_GAP")
        if previous is None:
            _require(doc["previousAnchorDigest"] is None, "ANCHOR_CHAIN_LINK")
        else:
            _require(doc["previousAnchorDigest"] == digests[-1], "ANCHOR_CHAIN_LINK")
            _require(len(doc["appended"]) >= 1, "ANCHOR_EMPTY_ADVANCE")
            _require(doc["updatedAt"] >= previous["updatedAt"], "ANCHOR_TIME_REGRESSION")
        added = _entries(doc["appended"])
        _require(not (added & entries), "ANCHOR_NOT_AN_EXTENSION")
        _require(doc["appended"] == sorted([list(e) for e in added]), "ANCHOR_APPENDED_NOT_CANONICAL")
        entries = entries | added
        _require(doc["setHead"] == suppression_set_head(environment, entries), "ANCHOR_HEAD_MISMATCH")
        _require(doc["suppressionCount"] == len(entries), "ANCHOR_COUNT_MISMATCH")
        digests.append(anchor_digest(doc))
        heads.append(doc["setHead"])
        counts.append(doc["suppressionCount"])
        previous = doc
    return AnchorChainV1(environment, entries, tuple(digests), tuple(heads), tuple(counts))


def unsigned_anchor_advance(chain: Optional[AnchorChainV1], new_entries: Iterable[Sequence[str]], *,
                            environment: str, updated_at: str, key_id: str) -> Dict[str, Any]:
    """The next anchor body (unsigned) a K-PAN holder may sign: genesis when ``chain`` is None, otherwise a strict
    extension. Refuses anything that is not an extension, so a signer that uses it can never sign a regression."""
    _key_id(key_id, KPAN_KEY_PREFIX)
    _time(updated_at)
    added = _entries(new_entries)
    base = chain.entries if chain is not None else frozenset()
    _require(not (added & base), "ANCHOR_NOT_AN_EXTENSION")
    _require(chain is None or len(added) >= 1, "ANCHOR_EMPTY_ADVANCE")
    full = base | added
    return {"protocol": ANCHOR_PROTOCOL, "schemaVersion": SCHEMA_VERSION, "environment": environment,
            "anchorVersion": (chain.version + 1) if chain else 1,
            "previousAnchorDigest": chain.digest if chain else None,
            "suppressionCount": len(full), "setHead": suppression_set_head(environment, full),
            "appended": sorted([list(e) for e in added]), "updatedAt": updated_at, "anchorKeyId": key_id}


# ------------------------------------------------------------------------------------------------ checkpoint ---

def checkpoint_digest(doc: Mapping[str, Any]) -> str:
    return _digest(CHECKPOINT_DOMAIN, doc, CHECKPOINT_FIELDS)


def verify_checkpoint(doc: Any, public_key: Ed25519PublicKey, *, environment: str, key_id: str) -> None:
    _check_shape(doc, CHECKPOINT_FIELDS, True)
    _common(doc, CHECKPOINT_PROTOCOL, environment)
    _key_id(doc["checkpointKeyId"], KPCK_KEY_PREFIX)
    _require(doc["checkpointKeyId"] == key_id, "KEY_ID_MISMATCH")
    _require(_positive(doc["checkpointSeq"]) and _positive(doc["anchorVersion"])
             and _count(doc["suppressionCount"]), "CHECKPOINT_INVALID")
    for field in ("anchorDigest", "setHead"):
        _require(isinstance(doc[field], str) and _HEX64.match(doc[field]) is not None, "CHECKPOINT_INVALID")
    _time(doc["checkpointedAt"])
    _verify_signature("checkpoint", doc, public_key)


def checkpoint_extends(previous: Optional[Mapping[str, Any]], doc: Mapping[str, Any]) -> None:
    """The holder's extension-only rule: sequence + 1, chained digest, anchor version STRICTLY increasing, count never
    decreasing. A submission at or below the latest anchor version is refused (and is a fork alarm for the holder)."""
    if previous is None:
        _require(doc["checkpointSeq"] == 1 and doc["previousCheckpointDigest"] is None, "CHECKPOINT_GENESIS_INVALID")
        return
    _require(doc["checkpointSeq"] == previous["checkpointSeq"] + 1, "CHECKPOINT_NOT_AN_EXTENSION")
    _require(doc["previousCheckpointDigest"] == checkpoint_digest(previous), "CHECKPOINT_NOT_AN_EXTENSION")
    _require(doc["anchorVersion"] > previous["anchorVersion"], "CHECKPOINT_FORK_ALARM")
    _require(doc["suppressionCount"] >= previous["suppressionCount"], "CHECKPOINT_FORK_ALARM")
    _require(doc["checkpointedAt"] >= previous["checkpointedAt"], "CHECKPOINT_TIME_REGRESSION")


def verify_checkpoint_chain(docs: Sequence[Any], public_key: Ed25519PublicKey, *, environment: str,
                            key_id: str) -> Mapping[str, Any]:
    """Verifies an owner-held checkpoint chain end to end; returns its latest checkpoint."""
    _require(isinstance(docs, (list, tuple)) and len(docs) >= 1, "CHECKPOINT_CHAIN_EMPTY")
    previous = None
    for doc in docs:
        verify_checkpoint(doc, public_key, environment=environment, key_id=key_id)
        checkpoint_extends(previous, doc)
        previous = doc
    return previous


def checkpoint_matches_anchor(doc: Mapping[str, Any], chain: AnchorChainV1) -> str:
    """FRESH when the checkpointed anchor version is in the host chain with the same digest, head and count;
    OLDER_THAN_CHECKPOINT when the host chain has not reached it (a rolled-back host); DIVERGED otherwise."""
    if doc["anchorVersion"] > chain.version:
        return OLDER_THAN_CHECKPOINT
    digest, head, count = chain.at(doc["anchorVersion"])
    if (digest, head, count) != (doc["anchorDigest"], doc["setHead"], doc["suppressionCount"]):
        return DIVERGED
    return FRESH


def unsigned_checkpoint(previous: Optional[Mapping[str, Any]], chain: AnchorChainV1, *, environment: str,
                        checkpointed_at: str, key_id: str) -> Dict[str, Any]:
    """The next checkpoint body (unsigned) over the host chain's CURRENT head; refuses a non-extension."""
    _key_id(key_id, KPCK_KEY_PREFIX)
    _time(checkpointed_at)
    _require(chain.environment == environment, "ENVIRONMENT_MISMATCH")
    doc = {"protocol": CHECKPOINT_PROTOCOL, "schemaVersion": SCHEMA_VERSION, "environment": environment,
           "checkpointSeq": (previous["checkpointSeq"] + 1) if previous else 1,
           "previousCheckpointDigest": checkpoint_digest(previous) if previous else None,
           "anchorVersion": chain.version, "anchorDigest": chain.digest, "setHead": chain.set_head,
           "suppressionCount": chain.count, "checkpointedAt": checkpointed_at, "checkpointKeyId": key_id}
    checkpoint_extends(previous, doc)
    return doc


# ------------------------------------------------------------------------------------- boot freshness (b) ---

def challenge_digest(doc: Mapping[str, Any]) -> str:
    return _digest(CHALLENGE_DOMAIN, doc, CHALLENGE_FIELDS)


def make_challenge(chain: AnchorChainV1, *, environment: str, boot_id: str, nonce: str, issued_at: str
                   ) -> Dict[str, Any]:
    """The host's boot challenge (unsigned; its integrity comes from the owner's unlock signing its digest)."""
    _require(chain.environment == environment, "ENVIRONMENT_MISMATCH")
    _require(isinstance(boot_id, str) and _TOKEN.match(boot_id) is not None, "BOOT_ID_INVALID")
    _require(isinstance(nonce, str) and _HEX64.match(nonce) is not None, "NONCE_INVALID")
    _time(issued_at)
    return {"protocol": CHALLENGE_PROTOCOL, "schemaVersion": SCHEMA_VERSION, "environment": environment,
            "bootId": boot_id, "nonce": nonce, "anchorVersion": chain.version, "anchorDigest": chain.digest,
            "setHead": chain.set_head, "suppressionCount": chain.count, "issuedAt": issued_at}


def unlock_digest(doc: Mapping[str, Any]) -> str:
    return _digest(UNLOCK_DOMAIN, doc, UNLOCK_FIELDS)


def unsigned_unlock(challenge: Mapping[str, Any], latest_checkpoint: Mapping[str, Any], *, unlocked_at: str,
                    key_id: str) -> Dict[str, Any]:
    """The owner's unlock body (unsigned): binds this challenge to the owner's LATEST checkpoint. The owner tool must
    compare first (see ``classify_boot_freshness``) and sign only a FRESH result."""
    _key_id(key_id, KPCK_KEY_PREFIX)
    _time(unlocked_at)
    _check_shape(challenge, CHALLENGE_FIELDS, False)
    return {"protocol": UNLOCK_PROTOCOL, "schemaVersion": SCHEMA_VERSION, "environment": challenge["environment"],
            "bootId": challenge["bootId"], "nonce": challenge["nonce"], "challengeDigest": challenge_digest(challenge),
            "checkpointSeq": latest_checkpoint["checkpointSeq"],
            "checkpointDigest": checkpoint_digest(latest_checkpoint), "unlockedAt": unlocked_at,
            "checkpointKeyId": key_id}


@dataclass(frozen=True)
class BootFreshnessV1:
    status: str
    code: Optional[str] = None
    checkpoint_seq: int = 0
    checkpoint_anchor_version: int = 0
    unlock_digest: Optional[str] = None

    @property
    def fresh(self) -> bool:
        return self.status == FRESH


def classify_boot_freshness(challenge: Any, unlock: Any, checkpoint: Any, chain: AnchorChainV1,
                            checkpoint_key: Ed25519PublicKey, *, environment: str, checkpoint_key_id: str,
                            boot_id: str, nonce: str) -> BootFreshnessV1:
    """Host-side verification of a manual boot unlock against this boot's own challenge and the host anchor chain.

    ``boot_id`` / ``nonce`` are the values the host generated and kept for this boot (never read from the inputs).
    The host chain may be AHEAD of the checkpoint (an advance whose checkpoint is still pending: its FORGET has not
    erased anything yet, durable-before-erase); it must never be behind it or disagree with it."""
    try:
        _check_shape(challenge, CHALLENGE_FIELDS, False)
        _common(challenge, CHALLENGE_PROTOCOL, environment)
        verify_checkpoint(checkpoint, checkpoint_key, environment=environment, key_id=checkpoint_key_id)
        _check_shape(unlock, UNLOCK_FIELDS, True)
        _common(unlock, UNLOCK_PROTOCOL, environment)
        _key_id(unlock["checkpointKeyId"], KPCK_KEY_PREFIX)
        _require(unlock["checkpointKeyId"] == checkpoint_key_id, "KEY_ID_MISMATCH")
        _time(unlock["unlockedAt"])
        _verify_signature("unlock", unlock, checkpoint_key)
    except PrivacyAnchorError as exc:
        return BootFreshnessV1(UNVERIFIABLE, exc.code)
    if (challenge["bootId"], challenge["nonce"]) != (boot_id, nonce) or \
            (unlock["bootId"], unlock["nonce"]) != (boot_id, nonce) or \
            unlock["challengeDigest"] != challenge_digest(challenge):
        return BootFreshnessV1(REPLAYED, "CHALLENGE_NOT_THIS_BOOT")
    if unlock["checkpointDigest"] != checkpoint_digest(checkpoint) or \
            unlock["checkpointSeq"] != checkpoint["checkpointSeq"]:
        return BootFreshnessV1(UNVERIFIABLE, "UNLOCK_CHECKPOINT_MISMATCH")
    if (challenge["anchorVersion"], challenge["anchorDigest"], challenge["setHead"], challenge["suppressionCount"]) \
            != (chain.version, chain.digest, chain.set_head, chain.count):
        return BootFreshnessV1(DIVERGED, "CHALLENGE_NOT_HOST_CHAIN")
    status = checkpoint_matches_anchor(checkpoint, chain)
    if status != FRESH:
        return BootFreshnessV1(status, status)
    return BootFreshnessV1(FRESH, None, checkpoint["checkpointSeq"], checkpoint["anchorVersion"],
                           unlock_digest(unlock))


_KINDS = {
    "anchor": (ANCHOR_DOMAIN, ANCHOR_FIELDS),
    "checkpoint": (CHECKPOINT_DOMAIN, CHECKPOINT_FIELDS),
    "unlock": (UNLOCK_DOMAIN, UNLOCK_FIELDS),
}
