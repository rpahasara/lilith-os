#!/usr/bin/env python3
"""15B2b-B1b-3e M-B10 (WRITE_HELD): the OFF-HOST owner-side eligibility evidence, taken immediately before M-B10.

Record: docs/architecture/slice-15b2b-b1b3e-mb10-held-package.md §5.

The host cannot see owner-record custody. P3-5 step 12 (`WRITE_HELD`) needs `REQUIRED_CURRENT` and
`ACCEPTANCE_COMPLETE`, re-classified for that step. This tool proves, on the owner laptop (WSL, the pinned
`rfc8785` / `fido2` / `cryptography`), from the accepted Package C state and ONE fresh, receipt-bound chain export
of this M-B10 sequence:

- Package C is accepted: `C5_ACCEPTANCE.json` is the accepted bytes; the binding is the accepted binding;
- Replica A holds exactly record 1 and store A exactly envelope 1 (digests exact; no pending file);
- the proven Replica B and store B views (the C3 / C4B owner transcriptions) are the accepted views;
- laptop freshness is AUTHENTIC + CURRENT and acceptance `ACCEPTANCE_COMPLETE` (the canonical classifiers, via
  the pinned Package C operator, unchanged);
- the fresh chain export is byte-identical to the bound genesis-only chain (`chain/1.json` = `witness.json` =
  the committed genesis), so the witness has not advanced since the binding.

It writes ONE new JSON record and nothing else; it never writes a replica, a store, a view or HELD, and never
contacts DEV or the S25. Any missing, unreadable or unexpected input is `MB10_OWNER_REVALIDATE` with a reason:
UNKNOWN is never eligibility. The hold store being empty is a HOST fact, proven by the W10 verifier in the gate,
not here.

    evaluate <pkgc-workdir> <replica-a> <store-a> <fresh-export-dir> <export-receipt-sha256> <out.json>

    eligibility evidence != M-B10 authorization;  ELIGIBLE != go;  CURRENT != HELD != signer != authority
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

PKGC_OPERATOR_SHA256 = "c5e5a5cc265f48721715e43b4bec40ccbaf865c4149d095c86c853331c2767c0"
SEQUENCE = "e6b7a3334cda25efe9259741cda1b3ae"
BINDING_SHA256 = "bd1c35e79c3833710196f51186741160e81c0532632f5050fd5134fc0ca70793"
RECORD_1 = "77752db11d80eef50eaeaa8b931d65a489bb919f9e864584fbf8d00746e2cec6"
ENVELOPE_1 = "95da36cd6edd49c2bae244611cc429a174dee72ec2454c4f73c57a83bfcb0f0c"
C5_ACCEPTANCE_SHA256 = "16afa08a0e5dae54d1a9dbf0cceb4857ca6bf34284515bd6a97a6d69ca4cf755"
CHAIN_1_SHA256 = "252c32204bebf3fa1ca0981d8791115e2abb6cd8ddb0925285c64213317cfb99"
REPLICA_A_ID = "owner-primary-dev-synthetic-01"
REPLICA_B_ID = "owner-offline-dev-synthetic-01"
VIEWS = {"replica-b-1": "2534bda866d14c0ae7c6f1e64658bbb88dc8b358ca226324a8bfd05507897c94",
         "store-b-1": "5cb0bc77318a91a02d8890ac0ad636960d8432a387e055ba13f7eebe05ed56d1"}
ELIGIBLE = "MB10_OWNER_ELIGIBLE"
REVALIDATE = "MB10_OWNER_REVALIDATE"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_pkgc():
    """The pinned Package C operator (its readers and the canonical classifiers behind them), hash-gated."""
    source = HERE / "pkgc_operator.py"
    if _sha(source.read_bytes()) != PKGC_OPERATOR_SHA256:
        raise Refused("PKGC_OPERATOR_PIN_MISMATCH")
    import pkgc_operator

    return pkgc_operator


def _pending(*roots: Path) -> int:
    count = 0
    for root in roots:
        for _dirpath, _dirs, files in os.walk(root):
            count += sum("pending" in name for name in files)
    return count


def gather(pkgc_workdir: Path, replica_a: Path, store_a: Path, export: Path, *, pkgc=None) -> dict[str, Any]:
    """Every observed fact; nothing is judged here. Any failure to observe is recorded as UNKNOWN."""
    P = pkgc or load_pkgc()
    w = Path(pkgc_workdir)
    facts: dict[str, Any] = {}

    def observe(name: str, function: Callable[[], Any]) -> None:
        try:
            facts[name] = function()
        except Exception as exc:  # noqa: BLE001 - any failure is UNKNOWN, never eligibility
            facts[name] = None
            facts.setdefault("unknown", []).append(f"{name}:{type(exc).__name__}:{getattr(exc, 'code', '')}")

    observe("sequenceId", lambda: json.loads((w / "C1_OPENING.json").read_text(encoding="utf-8"))["sequenceId"])
    observe("c5AcceptanceSha256", lambda: _sha((w / "C5_ACCEPTANCE.json").read_bytes()))
    observe("stopPresent", lambda: (w / "STOP.json").exists())
    observe("bindingSha256", lambda: P.load_binding(w)[1])
    observe("replicaADigests", lambda: list(P.T.load_replica(Path(replica_a)).digests))
    observe("replicaAId", lambda: P.T.load_replica(Path(replica_a)).replica_id)
    observe("storeADigests", lambda: list(P.T.load_acceptance_store(Path(store_a)).digests))
    observe("storeACustody", lambda: P.T.load_acceptance_store(Path(store_a)).custody_copy_id)
    observe("views", lambda: {kind: P.tree_digest(P.load_view(w, kind)) for kind in VIEWS})
    observe("storeBViewDigests", lambda: list(P.T.load_acceptance_store(P.load_view(w, "store-b-1")).digests))
    observe("storeBViewCustody", lambda: P.T.load_acceptance_store(P.load_view(w, "store-b-1")).custody_copy_id)
    observe("envelopeBytesIdentical", lambda: P.OF.record_bytes(
        P.T.load_acceptance_store(Path(store_a)).bundles[0]) == P.OF.record_bytes(
        P.T.load_acceptance_store(P.load_view(w, "store-b-1")).bundles[0]))
    observe("freshness", lambda: (lambda f: [f.authenticity, f.freshness])(
        P.laptop_freshness(w, Path(replica_a), "replica-b-1")))
    observe("acceptance", lambda: P.laptop_acceptance(w, Path(replica_a), Path(store_a), "replica-b-1",
                                                      "store-b-1").state)
    observe("pendingFiles", lambda: _pending(Path(replica_a), Path(store_a)))
    observe("freshChainSha256", lambda: _sha((Path(export) / "chain-1.json").read_bytes()))
    observe("freshPointerSha256", lambda: _sha((Path(export) / "witness.json").read_bytes()))
    observe("freshChainEqualsBinding", lambda: P._canonical_list(
        [P._json((Path(export) / "chain-1.json").read_bytes(), "GENESIS_INVALID")])
        == (w / P.BINDING_DIR / P.CHAIN_FILE).read_bytes())
    return facts


def judge(facts: Mapping[str, Any]) -> dict[str, Any]:
    """Pure. ELIGIBLE only when every required fact is observed and exact; anything else is REVALIDATE."""
    reasons: list[str] = [f"UNKNOWN:{item}" for item in facts.get("unknown", [])]
    expect = {
        "sequenceId": (SEQUENCE, "SEQUENCE_NOT_PACKAGE_C"),
        "c5AcceptanceSha256": (C5_ACCEPTANCE_SHA256, "C5_NOT_THE_ACCEPTED_RECORD"),
        "stopPresent": (False, "PACKAGE_C_STOPPED"),
        "bindingSha256": (BINDING_SHA256, "BINDING_CHANGED"),
        "replicaADigests": ([RECORD_1], "REPLICA_A_NOT_RECORD_1_ONLY"),
        "replicaAId": (REPLICA_A_ID, "REPLICA_A_ID"),
        "storeADigests": ([ENVELOPE_1], "STORE_A_NOT_ENVELOPE_1_ONLY"),
        "storeACustody": (REPLICA_A_ID, "STORE_A_CUSTODY"),
        "views": (VIEWS, "PEER_VIEW_NOT_THE_PROVEN_VIEW"),
        "storeBViewDigests": ([ENVELOPE_1], "STORE_B_VIEW_NOT_ENVELOPE_1_ONLY"),
        "storeBViewCustody": (REPLICA_B_ID, "STORE_B_VIEW_CUSTODY"),
        "envelopeBytesIdentical": (True, "ENVELOPE_COPIES_DIFFER"),
        "freshness": (["AUTHENTIC", "CURRENT"], "FRESHNESS_NOT_AUTHENTIC_CURRENT"),
        "acceptance": ("ACCEPTANCE_COMPLETE", "ACCEPTANCE_NOT_COMPLETE"),
        "pendingFiles": (0, "PENDING_FILES"),
        "freshChainSha256": (CHAIN_1_SHA256, "FRESH_CHAIN_NOT_THE_COMMITTED_GENESIS"),
        "freshPointerSha256": (CHAIN_1_SHA256, "FRESH_POINTER_NOT_GENESIS"),
        "freshChainEqualsBinding": (True, "FRESH_CHAIN_NOT_THE_BOUND_CHAIN"),
    }
    for name, (value, reason) in expect.items():
        if name not in facts:
            reasons.append("UNKNOWN:" + name)
        elif facts[name] is not None and facts[name] != value:
            reasons.append(reason)
    reasons = sorted(set(reasons))
    return {"result": ELIGIBLE if not reasons else REVALIDATE, "reasons": reasons}


def evaluate(pkgc_workdir: Path, replica_a: Path, store_a: Path, export: Path, receipt: str, out: Path, *,
             pkgc=None, now: Callable[[], datetime] | None = None) -> dict[str, Any]:
    if not isinstance(receipt, str) or _HEX64.fullmatch(receipt) is None:
        raise Refused("RECEIPT_SHA256_INVALID")
    facts = gather(pkgc_workdir, replica_a, store_a, export, pkgc=pkgc)
    verdict = judge(facts)
    record = {"recordType": "LILITH_MB10_OWNER_ELIGIBILITY", "schemaVersion": 1,
              "observedAt": (now or (lambda: datetime.now(timezone.utc)))().strftime("%Y-%m-%dT%H:%M:%SZ"),
              "exportReceiptSha256": receipt, "pkgcOperatorSha256": PKGC_OPERATOR_SHA256,
              "accepted": {"record1": RECORD_1, "envelope1": ENVELOPE_1, "binding": BINDING_SHA256,
                           "c5Acceptance": C5_ACCEPTANCE_SHA256, "chain1": CHAIN_1_SHA256},
              "facts": facts, **verdict, "authorityGranted": False,
              "note": "owner-side evidence only: not an M-B10 authorization; the hold store is judged on the host"}
    data = json.dumps(record, sort_keys=True, indent=1).encode("utf-8") + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(out, flags, 0o600)
    except FileExistsError as exc:
        raise Refused("OUTPUT_EXISTS") from exc
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    return {"result": verdict["result"], "reasons": verdict["reasons"], "eligibilitySha256": _sha(data)}


def main(argv: list[str]) -> int:
    try:
        if len(argv) != 7 or argv[0] != "evaluate":
            raise Refused("USAGE")
        result = evaluate(*(Path(a) for a in argv[1:5]), argv[5], Path(argv[6]))
    except Refused as exc:
        print(f"mb10_owner_eligibility: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(dict(result, authorityGranted=False), sort_keys=True, indent=2) + "\n")
    return 0 if result["result"] == ELIGIBLE else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
