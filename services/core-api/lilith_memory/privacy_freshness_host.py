"""Track B: the root host steps of Privacy activation (DEV_SYNTHETIC). Glue only: no key, no new contract, no service.

It connects pieces that already exist and are already verified:

* the recovery witness's K-PAN anchor (``lilith_recovery_witness.privacy_anchor``), reached over the witness OWNER
  socket (peer uid 0) with that module's exact frame (4-byte length + RFC 8785 JSON) and closed operations
  ``READ_PRIVACY_ANCHOR`` / ``GENESIS_PRIVACY_ANCHOR`` / ``ADVANCE_PRIVACY_ANCHOR``; every chain the witness returns is
  re-verified here under the INSTALLED K-PAN public pin, never trusted;
* the owner device's K-PCK tool (``privacy_checkpoint_tool.py``, off-host): this tool writes the files it consumes
  (``export-anchor`` -> ``--anchor-chain``, ``challenge`` -> ``--challenge``) and accepts the files it produces
  (``checkpoint`` / ``unlock`` documents);
* the root freshness steps and the marker (``privacy_freshness.issue_challenge`` / ``apply_unlock`` /
  ``apply_checkpoint``), which stay the only writers of the marker the Core API gate reads.

Forms (root on the DEV host; each is one explicit owner-directed step, nothing runs by itself):

    status                                   read-only: gate check, durability, anchor head vs local Privacy set
    plan                                     read-only: GENESIS or ADVANCE entries and the expected set head
    export-anchor --out FILE                 read-only: the verified anchor chain for the owner tool
    genesis --expected-set-head H            witness anchor v1 (only on an empty anchor; H from `plan`)
    advance --expected-set-head H            witness anchor v+1 = exactly the local suppression rows not yet anchored
    challenge --out FILE                     this boot's challenge (fresh nonce); state kept for this boot only
    unlock --unlock FILE --checkpoint FILE   verify the owner's K-PCK unlock for THIS boot's challenge; publish marker
    checkpoint --checkpoint FILE             accept the owner's next checkpoint (durable-before-erase); republish

Configuration: ``--privacy-db`` (default ``$LILITH_PRIVACY_DB_PATH``), ``--kpan-pin`` / ``--kpck-pin`` (public pins,
``LILITH_PRIVACY_KEY_PIN_V1``), ``--witness-socket``. A missing or malformed pin, an unverifiable chain, a challenge
of another boot or an unlock that is not FRESH is an explicit refusal; nothing is published.

    anchored != checkpointed != unlocked;  this tool never signs, never generates a key and never reads a private key
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import sqlite3
import struct
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

import rfc8785
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

try:
    from . import privacy_anchor_contracts as A
    from . import privacy_freshness as F
except ImportError:  # deploy-exact flat-directory tests
    import privacy_anchor_contracts as A
    import privacy_freshness as F

ENVIRONMENT = "DEV_SYNTHETIC"
PIN_TYPE = "LILITH_PRIVACY_KEY_PIN_V1"
PIN_FIELDS = frozenset({"type", "family", "environment", "keyId", "publicKeyHex"})
DEFAULT_PIN_DIR = Path("/etc/lilith-privacy-fresh")
DEFAULT_KPAN_PIN = DEFAULT_PIN_DIR / "kpan.pin.json"
DEFAULT_KPCK_PIN = DEFAULT_PIN_DIR / "kpck.pin.json"
DEFAULT_WITNESS_SOCKET = Path("/run/lilith-recovery-witness/owner.sock")
CHALLENGE_STATE = F.DEFAULT_MARKER.parent / "challenge.json"       # tmpfs, root 0600: gone at every reboot

# The witness anchor protocol (``lilith_recovery_witness.privacy_anchor``; a test proves byte compatibility).
ANCHOR_PROTOCOL = "LILITH_PRIVACY_ANCHOR_DEV"
ANCHOR_PROTOCOL_VERSION = 1
MAX_FRAME_BYTES = 64 * 1024
MAX_ENTRIES_PER_ADVANCE = 256
READ, GENESIS, ADVANCE = "READ_PRIVACY_ANCHOR", "GENESIS_PRIVACY_ANCHOR", "ADVANCE_PRIVACY_ANCHOR"


class HostStepRefused(RuntimeError):
    """A host step refused; nothing was sent to the witness or published."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _need(condition: bool, code: str) -> None:
    if not condition:
        raise HostStepRefused(code)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# --------------------------------------------------------------------------------------------------- pins ---

def load_pin(path: Path, *, family: str, prefix: str, environment: str = ENVIRONMENT) -> tuple:
    """(public key, key id) of one installed public pin; the owner tool's format, refused on any deviation."""
    try:
        doc = json.loads(Path(path).read_text(encoding="ascii"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise HostStepRefused(f"{family}_PIN_UNAVAILABLE") from exc
    _need(isinstance(doc, dict) and set(doc) == PIN_FIELDS and doc["type"] == PIN_TYPE and doc["family"] == family
          and isinstance(doc["keyId"], str) and doc["keyId"].startswith(prefix)
          and doc["environment"] == environment, f"{family}_PIN_INVALID")
    try:
        return Ed25519PublicKey.from_public_bytes(bytes.fromhex(doc["publicKeyHex"])), doc["keyId"]
    except (ValueError, TypeError) as exc:
        raise HostStepRefused(f"{family}_PIN_INVALID") from exc


def load_keys(kpan_pin: Path, kpck_pin: Path, *, environment: str = ENVIRONMENT) -> F.FreshnessKeys:
    anchor_key, anchor_id = load_pin(kpan_pin, family="K-PAN", prefix=A.KPAN_KEY_PREFIX, environment=environment)
    checkpoint_key, checkpoint_id = load_pin(kpck_pin, family="K-PCK", prefix=A.KPCK_KEY_PREFIX,
                                             environment=environment)
    return F.FreshnessKeys(environment, anchor_key, anchor_id, checkpoint_key, checkpoint_id)


# ------------------------------------------------------------------------------------------ witness client ---

def encode_request(operation: str, payload: Mapping[str, Any]) -> bytes:
    raw = rfc8785.dumps({"protocol": ANCHOR_PROTOCOL, "schemaVersion": ANCHOR_PROTOCOL_VERSION,
                         "operation": operation, "payload": dict(payload)})
    _need(0 < len(raw) <= MAX_FRAME_BYTES, "WITNESS_FRAME_TOO_LARGE")
    return struct.pack(">I", len(raw)) + raw


def decode_response(frame: bytes) -> Dict[str, Any]:
    _need(isinstance(frame, bytes) and len(frame) >= 4, "WITNESS_RESPONSE_INVALID")
    length = struct.unpack(">I", frame[:4])[0]
    _need(0 < length <= MAX_FRAME_BYTES and len(frame) == length + 4, "WITNESS_RESPONSE_INVALID")
    try:
        value = json.loads(frame[4:].decode("utf-8"))
        canonical = rfc8785.dumps(value) == frame[4:]
    except (ValueError, UnicodeDecodeError, rfc8785.CanonicalizationError) as exc:
        raise HostStepRefused("WITNESS_RESPONSE_INVALID") from exc
    _need(canonical and isinstance(value, dict) and set(value) == {"protocol", "schemaVersion", "payload"}
          and value["protocol"] == ANCHOR_PROTOCOL and value["schemaVersion"] == ANCHOR_PROTOCOL_VERSION
          and isinstance(value["payload"], dict), "WITNESS_RESPONSE_INVALID")
    return value["payload"]


def unix_socket_transport(path: Path, *, timeout: float = 10.0) -> Callable[[bytes], bytes]:
    """One frame, one response, close (the witness owner socket serves exactly that)."""
    def send(frame: bytes) -> bytes:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(timeout)
            conn.connect(str(path))
            conn.sendall(frame)
            data = b""
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    return data
                data += chunk
                if len(data) >= 4 and len(data) >= struct.unpack(">I", data[:4])[0] + 4:
                    return data
    return send


class WitnessAnchorClient:
    """The witness's three anchor operations; every chain it returns is verified under the installed K-PAN pin."""

    def __init__(self, transport: Callable[[bytes], bytes], keys: F.FreshnessKeys):
        self._send = transport
        self._keys = keys

    def _request(self, operation: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        try:
            response = decode_response(self._send(encode_request(operation, payload)))
        except OSError as exc:
            raise HostStepRefused("WITNESS_UNREACHABLE") from exc
        _need(response.get("status") != "REFUSED", "WITNESS_REFUSED:" + str(response.get("reason")))
        return response

    def chain_documents(self) -> List[Dict[str, Any]]:
        """The whole anchor chain ([] when the witness reports UNINITIALIZED), verified end to end."""
        response = self._request(READ, {"fromVersion": 1})
        docs = response.get("documents")
        _need(isinstance(docs, list), "WITNESS_RESPONSE_INVALID")
        if response.get("status") == "UNINITIALIZED":
            _need(docs == [] and response.get("anchorVersion") == 0, "WITNESS_RESPONSE_INVALID")
            return []
        _need(response.get("status") == "OK" and response.get("anchorKeyId") == self._keys.anchor_key_id,
              "WITNESS_RESPONSE_INVALID")
        chain = verify_chain(self._keys, docs)
        _need((chain.version, chain.digest) == (response.get("anchorVersion"), response.get("anchorDigest")),
              "WITNESS_RESPONSE_INVALID")
        return docs

    def commit(self, operation: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        response = self._request(operation, payload)
        _need(response.get("status") == "COMMITTED", "WITNESS_NOT_COMMITTED")
        return response


def verify_chain(keys: F.FreshnessKeys, docs: Sequence[Any]) -> A.AnchorChainV1:
    try:
        return A.verify_anchor_chain(docs, keys.anchor_key, environment=keys.environment, key_id=keys.anchor_key_id)
    except A.PrivacyAnchorError as exc:
        raise HostStepRefused("ANCHOR_CHAIN_" + exc.code) from exc


# -------------------------------------------------------------------------------------------------- steps ---

@dataclass(frozen=True)
class AnchorPlan:
    kind: str                      # GENESIS | ADVANCE | CURRENT
    entries: List[List[str]]       # the local suppression rows not yet anchored (sorted)
    expected_set_head: str         # the head of the whole local set the step would anchor
    anchor_version: int
    anchor_digest: Optional[str]


def plan(client: WitnessAnchorClient, keys: F.FreshnessKeys, privacy_db: Path) -> AnchorPlan:
    """Read-only: what the next anchor step would sign. The local set must EXTEND the anchored set, never shrink or
    diverge from it (a restored Privacy store is refused here, before the witness is asked for anything)."""
    docs = client.chain_documents()
    chain = verify_chain(keys, docs) if docs else None
    try:
        local = set(F.local_suppression_entries(privacy_db))
        head = A.suppression_set_head(keys.environment, local)
    except (A.PrivacyAnchorError, sqlite3.Error, OSError) as exc:   # refused, never guessed
        raise HostStepRefused(F.PRIVACY_UNREADABLE) from exc
    anchored = chain.entries if chain else frozenset()
    if not anchored <= local:
        raise HostStepRefused(F.OLDER_THAN_ANCHOR if local < anchored else F.DIVERGED)
    added = sorted([list(e) for e in local - anchored])
    kind = "GENESIS" if chain is None else ("ADVANCE" if added else "CURRENT")
    return AnchorPlan(kind, added, head, chain.version if chain else 0, chain.digest if chain else None)


def _commit(client: WitnessAnchorClient, keys: F.FreshnessKeys, privacy_db: Path, *, kind: str,
            expected_set_head: str) -> Dict[str, Any]:
    step = plan(client, keys, privacy_db)
    _need(step.kind == kind, f"{kind}_NOT_APPLICABLE:{step.kind}")
    _need(expected_set_head == step.expected_set_head, "EXPECTED_SET_HEAD_MISMATCH")   # the owner's explicit pin
    _need(len(step.entries) <= MAX_ENTRIES_PER_ADVANCE, "TOO_MANY_ENTRIES")
    payload: Dict[str, Any] = {"entries": step.entries, "expectedSetHead": expected_set_head}
    if kind == "ADVANCE":
        payload["previousAnchorDigest"] = step.anchor_digest
    response = client.commit(GENESIS if kind == "GENESIS" else ADVANCE, payload)
    chain = verify_chain(keys, client.chain_documents())                 # re-read and verify, never trust a reply
    _need((chain.version, chain.set_head, chain.digest) == (step.anchor_version + 1, expected_set_head,
                                                            response.get("anchorDigest")), "WITNESS_COMMIT_MISMATCH")
    return {"result": kind + "_COMMITTED", "anchorVersion": chain.version, "anchorDigest": chain.digest,
            "setHead": chain.set_head, "suppressionCount": chain.count}


def genesis(client: WitnessAnchorClient, keys: F.FreshnessKeys, privacy_db: Path, *,
            expected_set_head: str) -> Dict[str, Any]:
    return _commit(client, keys, privacy_db, kind="GENESIS", expected_set_head=expected_set_head)


def advance(client: WitnessAnchorClient, keys: F.FreshnessKeys, privacy_db: Path, *,
            expected_set_head: str) -> Dict[str, Any]:
    return _commit(client, keys, privacy_db, kind="ADVANCE", expected_set_head=expected_set_head)


def _write_private(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o600)
    try:
        os.write(fd, json.dumps(dict(doc), sort_keys=True, separators=(",", ":")).encode("ascii"))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)


def challenge(client: WitnessAnchorClient, keys: F.FreshnessKeys, privacy_db: Path, *, boot_id: str,
              state_path: Path = CHALLENGE_STATE, issued_at: Optional[str] = None,
              nonce: Optional[str] = None) -> Dict[str, Any]:
    """This boot's challenge over the verified anchor head (refused unless L == S); the challenge is kept, root-only,
    for this boot only, so an unlock can only ever answer it."""
    docs = client.chain_documents()
    _need(bool(docs), "ANCHOR_NOT_PROVISIONED")
    try:
        doc = F.issue_challenge(keys, docs, privacy_db, boot_id=boot_id, nonce=nonce or secrets.token_hex(32),
                                issued_at=issued_at or utc_now())
    except F.FreshnessStepRefused as exc:
        raise HostStepRefused(exc.code) from exc
    _write_private(Path(state_path), {"bootId": boot_id, "challenge": doc})
    return doc


def unlock(client: WitnessAnchorClient, keys: F.FreshnessKeys, privacy_db: Path, unlock_doc: Mapping[str, Any],
           checkpoint_doc: Mapping[str, Any], *, boot_id: str, state_path: Path = CHALLENGE_STATE,
           marker_path: Path = F.DEFAULT_MARKER, verified_at: Optional[str] = None) -> Mapping[str, Any]:
    """Verify the owner's unlock for THIS boot's kept challenge and publish the marker; the challenge is single-use."""
    try:
        state = json.loads(Path(state_path).read_text(encoding="ascii"))
    except FileNotFoundError as exc:
        raise HostStepRefused("NO_CHALLENGE_FOR_THIS_BOOT") from exc
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise HostStepRefused("CHALLENGE_STATE_INVALID") from exc
    _need(isinstance(state, dict) and state.get("bootId") == boot_id and isinstance(state.get("challenge"), dict),
          "NO_CHALLENGE_FOR_THIS_BOOT")
    kept = state["challenge"]
    try:
        marker = F.apply_unlock(keys, client.chain_documents(), privacy_db, kept, unlock_doc, checkpoint_doc,
                                boot_id=boot_id, nonce=kept.get("nonce"), verified_at=verified_at or utc_now(),
                                marker_path=marker_path)
    except F.FreshnessStepRefused as exc:
        raise HostStepRefused(exc.code) from exc
    Path(state_path).unlink()
    return marker


def checkpoint(client: WitnessAnchorClient, keys: F.FreshnessKeys, privacy_db: Path,
               checkpoint_doc: Mapping[str, Any], *, boot_id: str, marker_path: Path = F.DEFAULT_MARKER,
               verified_at: Optional[str] = None, require_root_marker: bool = True) -> Mapping[str, Any]:
    try:
        return F.apply_checkpoint(keys, client.chain_documents(), privacy_db, checkpoint_doc, boot_id=boot_id,
                                  verified_at=verified_at or utc_now(), marker_path=marker_path,
                                  require_root_marker=require_root_marker)
    except F.FreshnessStepRefused as exc:
        raise HostStepRefused(exc.code) from exc


def status(client: WitnessAnchorClient, keys: F.FreshnessKeys, privacy_db: Path, *, boot_id: str,
           marker_path: Path = F.DEFAULT_MARKER, require_root_marker: bool = True) -> Dict[str, Any]:
    gate = F.PrivacyFreshnessGate(privacy_db, environment=keys.environment, marker_path=marker_path,
                                  boot_id=lambda: boot_id, require_root_marker=require_root_marker)
    out: Dict[str, Any] = {"gate": gate.check().status, "durability": gate.durability().status}
    try:
        step = plan(client, keys, privacy_db)
        out.update(anchorVersion=step.anchor_version, pendingAnchorEntries=len(step.entries), nextStep=step.kind)
    except HostStepRefused as exc:
        out.update(anchor="REFUSED:" + exc.code)
    return out


# ----------------------------------------------------------------------------------------------------- CLI ---

def _read_json(path: str) -> Dict[str, Any]:
    try:
        doc = json.loads(Path(path).read_text(encoding="ascii"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise HostStepRefused("INPUT_UNREADABLE") from exc
    _need(isinstance(doc, dict), "INPUT_UNREADABLE")
    return doc


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Track B Privacy activation host steps (root, DEV_SYNTHETIC)")
    parser.add_argument("--privacy-db", default=os.environ.get("LILITH_PRIVACY_DB_PATH", ""))
    parser.add_argument("--kpan-pin", default=str(DEFAULT_KPAN_PIN))
    parser.add_argument("--kpck-pin", default=str(DEFAULT_KPCK_PIN))
    parser.add_argument("--witness-socket", default=str(DEFAULT_WITNESS_SOCKET))
    sub = parser.add_subparsers(dest="form", required=True)
    sub.add_parser("status")
    sub.add_parser("plan")
    sub.add_parser("export-anchor").add_argument("--out", required=True)
    for name in ("genesis", "advance"):
        sub.add_parser(name).add_argument("--expected-set-head", required=True)
    sub.add_parser("challenge").add_argument("--out", required=True)
    u = sub.add_parser("unlock")
    u.add_argument("--unlock", required=True)
    u.add_argument("--checkpoint", required=True)
    sub.add_parser("checkpoint").add_argument("--checkpoint", required=True)
    args = parser.parse_args(argv)
    try:
        _need(hasattr(os, "geteuid") and os.geteuid() == 0, "NOT_ROOT")
        _need(bool(args.privacy_db) and Path(args.privacy_db).is_file(), F.PRIVACY_UNREADABLE)
        keys = load_keys(Path(args.kpan_pin), Path(args.kpck_pin))
        client = WitnessAnchorClient(unix_socket_transport(Path(args.witness_socket)), keys)
        db = Path(args.privacy_db)
        boot_id = F.read_boot_id()
        if args.form == "status":
            out: Any = status(client, keys, db, boot_id=boot_id)
        elif args.form == "plan":
            step = plan(client, keys, db)
            out = {"kind": step.kind, "entries": len(step.entries), "expectedSetHead": step.expected_set_head,
                   "anchorVersion": step.anchor_version}
        elif args.form == "export-anchor":
            docs = client.chain_documents()
            _need(bool(docs), "ANCHOR_NOT_PROVISIONED")
            Path(args.out).write_text(json.dumps(docs, sort_keys=True), encoding="ascii")
            out = {"result": "EXPORTED", "anchorVersion": len(docs)}
        elif args.form in ("genesis", "advance"):
            out = (genesis if args.form == "genesis" else advance)(client, keys, db,
                                                                   expected_set_head=args.expected_set_head)
        elif args.form == "challenge":
            doc = challenge(client, keys, db, boot_id=boot_id)
            Path(args.out).write_text(json.dumps(doc, sort_keys=True), encoding="ascii")
            out = {"result": "CHALLENGE_ISSUED", "bootId": boot_id, "anchorVersion": doc["anchorVersion"]}
        elif args.form == "unlock":
            marker = unlock(client, keys, db, _read_json(args.unlock), _read_json(args.checkpoint), boot_id=boot_id)
            out = {"result": "UNLOCKED", **{k: marker[k] for k in ("anchorVersion", "checkpointSeq", "bootId")}}
        else:
            marker = checkpoint(client, keys, db, _read_json(args.checkpoint), boot_id=boot_id)
            out = {"result": "CHECKPOINT_APPLIED", **{k: marker[k] for k in ("anchorVersion", "checkpointSeq")}}
    except HostStepRefused as exc:
        print(json.dumps({"result": "REFUSED", "code": exc.code}))
        return 2
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
