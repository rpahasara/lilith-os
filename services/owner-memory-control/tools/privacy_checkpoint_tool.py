"""Track B: owner-device K-PCK tool (off-host only; never installed on a LILITH host; outside every release set).

Design record: F9-C anchor design revision 1 §1-§2 (C-10 checkpoint, C-8 path (b) manual unlock).

The owner's Privacy checkpoint key (K-PCK) and the extension-only checkpoint chain live in ONE owner custody
directory on the owner device. This tool is the only writer of that directory:

    python services/owner-memory-control/tools/privacy_checkpoint_tool.py keygen     --custody DIR --environment ENV --key-id ID
    python services/owner-memory-control/tools/privacy_checkpoint_tool.py checkpoint --custody DIR --anchor-chain FILE
                                                                     --anchor-pin FILE --at TIME
    python services/owner-memory-control/tools/privacy_checkpoint_tool.py unlock     --custody DIR --challenge FILE
                                                                     --anchor-chain FILE --anchor-pin FILE --at TIME
    python services/owner-memory-control/tools/privacy_checkpoint_tool.py show       --custody DIR

* ``keygen`` creates the custody directory (0700) with ``kpck.key`` (raw private key, 0600), ``kpck.pin.json`` (the
  public pin the host installs) and an empty ``checkpoints.jsonl``. It refuses an existing directory.
* ``checkpoint`` verifies the host anchor chain under the K-PAN pin and appends the next checkpoint over its head,
  only as a strict extension (``checkpoint_extends``). A non-extension is refused and recorded in ``alarms.jsonl``
  (fork alarm): that is how a rolled-back host that tries to continue is noticed.
* ``unlock`` answers one host boot challenge with the latest checkpoint, but only after the tool's own comparison
  (``classify_boot_freshness`` against a self-signed trial) says FRESH. A rolled-back or forked host gets nothing.

No network, no LILITH host access, no cloud. Keys of other families (K-ROOT, K-WIT, K-PAN, authority, broker) are
never read; the key id must carry the ``kpck.`` prefix.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

_CORE_API = Path(__file__).resolve().parents[2] / "core-api"   # the pure contracts only (no runtime, no I/O)
if str(_CORE_API) not in sys.path:
    sys.path.insert(0, str(_CORE_API))

from lilith_memory import privacy_anchor_contracts as A  # noqa: E402

KEY_FILE = "kpck.key"
PIN_FILE = "kpck.pin.json"
CHAIN_FILE = "checkpoints.jsonl"
ALARM_FILE = "alarms.jsonl"
PIN_TYPE = "LILITH_PRIVACY_KEY_PIN_V1"
_BINARY = getattr(os, "O_BINARY", 0)   # Windows: never let the C runtime translate newlines in key or chain bytes


class ToolRefusal(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fsync_dir(path: Path) -> None:
    if hasattr(os, "O_DIRECTORY"):
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _write_new(path: Path, data: bytes, mode: int) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _BINARY, mode)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def _append_line(path: Path, doc: Dict[str, Any]) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | _BINARY, 0o600)
    try:
        os.write(fd, (json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii"))
        os.fsync(fd)
    finally:
        os.close(fd)


def public_pin(public_key: Ed25519PublicKey, *, environment: str, key_id: str, family: str) -> Dict[str, Any]:
    raw = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return {"type": PIN_TYPE, "family": family, "environment": environment, "keyId": key_id,
            "publicKeyHex": raw.hex()}


def load_pin(path: Path, *, family: str, prefix: str) -> tuple:
    doc = json.loads(Path(path).read_text(encoding="ascii"))
    if not isinstance(doc, dict) or set(doc) != {"type", "family", "environment", "keyId", "publicKeyHex"} \
            or doc["type"] != PIN_TYPE or doc["family"] != family or not str(doc["keyId"]).startswith(prefix):
        raise ToolRefusal("PIN_INVALID")
    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(doc["publicKeyHex"])), doc


def keygen(custody: Path, *, environment: str, key_id: str) -> Dict[str, Any]:
    if not key_id.startswith(A.KPCK_KEY_PREFIX):
        raise ToolRefusal("KEY_FAMILY_INVALID")
    A.suppression_set_head(environment, [])                     # validates the environment token
    custody = Path(custody)
    if custody.exists():
        raise ToolRefusal("CUSTODY_EXISTS")
    custody.mkdir(mode=0o700, parents=False)
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                            serialization.NoEncryption())
    _write_new(custody / KEY_FILE, raw, 0o600)
    pin = public_pin(key.public_key(), environment=environment, key_id=key_id, family="K-PCK")
    _write_new(custody / PIN_FILE, (json.dumps(pin, sort_keys=True, indent=2) + "\n").encode("ascii"), 0o644)
    _write_new(custody / CHAIN_FILE, b"", 0o600)
    _fsync_dir(custody)
    return {"status": "KPCK_GENERATED", "custody": str(custody), "pin": pin}


class Custody:
    def __init__(self, path: Path):
        self.path = Path(path)
        st = os.lstat(self.path / KEY_FILE)
        if not stat.S_ISREG(st.st_mode) or (os.name == "posix" and st.st_mode & 0o077):
            raise ToolRefusal("KEY_FILE_UNSAFE")
        self.public_key, self.pin = load_pin(self.path / PIN_FILE, family="K-PCK", prefix=A.KPCK_KEY_PREFIX)
        self.environment, self.key_id = self.pin["environment"], self.pin["keyId"]

    def _key(self) -> Ed25519PrivateKey:
        key = Ed25519PrivateKey.from_private_bytes((self.path / KEY_FILE).read_bytes())
        if key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex() \
                != self.pin["publicKeyHex"]:
            raise ToolRefusal("KEY_PIN_MISMATCH")
        return key

    def chain(self) -> List[Dict[str, Any]]:
        lines = (self.path / CHAIN_FILE).read_text(encoding="ascii").splitlines()
        docs = [json.loads(line) for line in lines if line.strip()]
        if docs:
            A.verify_checkpoint_chain(docs, self.public_key, environment=self.environment, key_id=self.key_id)
        return docs

    def latest(self) -> Optional[Dict[str, Any]]:
        docs = self.chain()
        return docs[-1] if docs else None

    def sign(self, kind: str, body: Dict[str, Any]) -> Dict[str, Any]:
        return {**body, "signature": self._key().sign(A.signing_bytes(kind, body)).hex()}


def _host_chain(anchor_chain: Path, anchor_pin: Path, environment: str) -> A.AnchorChainV1:
    key, pin = load_pin(anchor_pin, family="K-PAN", prefix=A.KPAN_KEY_PREFIX)
    if pin["environment"] != environment:
        raise ToolRefusal("ENVIRONMENT_MISMATCH")
    docs = json.loads(Path(anchor_chain).read_text(encoding="ascii"))
    try:
        return A.verify_anchor_chain(docs, key, environment=environment, key_id=pin["keyId"])
    except A.PrivacyAnchorError as exc:
        raise ToolRefusal("ANCHOR_CHAIN_" + exc.code) from exc


def checkpoint(custody_path: Path, *, anchor_chain: Path, anchor_pin: Path, at: str) -> Dict[str, Any]:
    custody = Custody(custody_path)
    chain = _host_chain(anchor_chain, anchor_pin, custody.environment)
    latest = custody.latest()
    try:
        body = A.unsigned_checkpoint(latest, chain, environment=custody.environment, checkpointed_at=at,
                                     key_id=custody.key_id)
        if latest is not None and A.checkpoint_matches_anchor(latest, chain) != A.FRESH:
            raise A.PrivacyAnchorError("CHECKPOINT_FORK_ALARM")   # the host chain does not extend our latest
    except A.PrivacyAnchorError as exc:
        _append_line(custody.path / ALARM_FILE, {"alarm": exc.code, "at": at, "hostAnchorVersion": chain.version,
                                                 "hostAnchorDigest": chain.digest})
        raise ToolRefusal(exc.code) from exc
    doc = custody.sign("checkpoint", body)
    _append_line(custody.path / CHAIN_FILE, doc)
    return doc


def unlock(custody_path: Path, *, challenge: Path, anchor_chain: Path, anchor_pin: Path, at: str) -> Dict[str, Any]:
    custody = Custody(custody_path)
    latest = custody.latest()
    if latest is None:
        raise ToolRefusal("NO_CHECKPOINT")
    chain = _host_chain(anchor_chain, anchor_pin, custody.environment)
    doc = json.loads(Path(challenge).read_text(encoding="ascii"))
    try:
        body = A.unsigned_unlock(doc, latest, unlocked_at=at, key_id=custody.key_id)
    except A.PrivacyAnchorError as exc:
        raise ToolRefusal(exc.code) from exc
    signed = custody.sign("unlock", body)
    trial = A.classify_boot_freshness(doc, signed, latest, chain, custody.public_key,
                                      environment=custody.environment, checkpoint_key_id=custody.key_id,
                                      boot_id=doc.get("bootId"), nonce=doc.get("nonce"))
    if not trial.fresh:
        _append_line(custody.path / ALARM_FILE, {"alarm": "UNLOCK_REFUSED:" + trial.status, "at": at,
                                                 "hostAnchorVersion": chain.version})
        raise ToolRefusal("UNLOCK_REFUSED:" + trial.status)
    return signed


def show(custody_path: Path) -> Dict[str, Any]:
    custody = Custody(custody_path)
    docs = custody.chain()
    alarms = custody.path / ALARM_FILE
    return {"environment": custody.environment, "keyId": custody.key_id, "checkpoints": len(docs),
            "latest": {k: docs[-1][k] for k in ("checkpointSeq", "anchorVersion", "anchorDigest")} if docs else None,
            "alarms": len(alarms.read_text().splitlines()) if alarms.exists() else 0}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="privacy_checkpoint_tool")
    sub = parser.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("keygen"); k.add_argument("--custody", required=True); k.add_argument("--environment", required=True)
    k.add_argument("--key-id", required=True)
    for name in ("checkpoint", "unlock"):
        p = sub.add_parser(name); p.add_argument("--custody", required=True); p.add_argument("--anchor-chain", required=True)
        p.add_argument("--anchor-pin", required=True); p.add_argument("--at", required=True)
        p.add_argument("--out", required=True)
        if name == "unlock":
            p.add_argument("--challenge", required=True)
    s = sub.add_parser("show"); s.add_argument("--custody", required=True)
    args = parser.parse_args(argv)
    try:
        if args.cmd == "keygen":
            result = keygen(Path(args.custody), environment=args.environment, key_id=args.key_id)
        elif args.cmd == "show":
            result = show(Path(args.custody))
        else:
            if args.cmd == "checkpoint":
                result = checkpoint(Path(args.custody), anchor_chain=Path(args.anchor_chain),
                                    anchor_pin=Path(args.anchor_pin), at=args.at)
            else:
                result = unlock(Path(args.custody), challenge=Path(args.challenge),
                                anchor_chain=Path(args.anchor_chain), anchor_pin=Path(args.anchor_pin), at=args.at)
            _write_new(Path(args.out), (json.dumps(result, sort_keys=True) + "\n").encode("ascii"), 0o644)
    except ToolRefusal as exc:
        print(json.dumps({"status": "REFUSED", "code": exc.code}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
