#!/usr/bin/env python3
"""15B2b-B1b-3e M-B10 (WRITE_HELD): the OFF-HOST owner-side eligibility evidence, taken immediately before M-B10.

Record: docs/architecture/slice-15b2b-b1b3e-mb10-held-package.md §5.

The host cannot see owner-record custody. P3-5 step 12 (`WRITE_HELD`) needs `REQUIRED_CURRENT` and
`ACCEPTANCE_COMPLETE`, re-classified for that step. OD-M10-5 (owner-accepted 2026-10-10): the proven C3 / C4B
views alone are NOT sufficient; a FRESH read-only S25 observation of Replica B and acceptance store B, taken after
D1, is required and bound here. This tool proves, on the owner laptop (WSL, the pinned `rfc8785` / `fido2` /
`cryptography`), from the M-B10 work directory of ONE sequence:

- Package C is accepted: `C5_ACCEPTANCE.json` and the binding are the accepted bytes;
- Replica A holds exactly record 1 and store A exactly envelope 1 (digests exact; no pending file);
- laptop freshness is AUTHENTIC + CURRENT and acceptance `ACCEPTANCE_COMPLETE` (the canonical classifiers, via the
  pinned Package C operator, unchanged);
- the sequence's fresh chain export (its RECEIPT names this sequence) is byte-identical to the bound genesis-only
  chain, so the witness has not advanced;
- the sequence's fresh S25 observation (`mb10_s25_phone.sh`, recorded by the operator after D1) is EXACT against
  the expectation computed here: Replica B exactly record 1 (same bytes as Replica A's record file), store B exactly
  envelope 1 (same bytes as store A's envelope file), no pending artifact, AUTHENTIC + CURRENT, ACCEPTANCE_COMPLETE,
  the A views equal to the live laptop copies.

It writes ONE new JSON record and nothing else. Any missing, unreadable or unexpected input is
`MB10_OWNER_REVALIDATE` with a reason: UNKNOWN is never eligibility. The empty hold store is a HOST fact, proven by
the W10 verifier in the gate.

    evaluate <mb10-workdir> <export-name> <s25-name> <pkgc-workdir> <replica-a> <store-a> <out.json>

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
GENESIS = "ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4"
S25_BUNDLE_SHA256 = "77eeb7d57c7e2e67365fc61207e99c0e817cf2bc685ea18f2f226799faa06610"
REPLICA_B_MANIFEST_SHA256 = "c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4"
STORE_B_MANIFEST_SHA256 = "df7737bd6ae55a292c002e0020dfd71e2421de233aa9c2e8686115100503c6c4"
REPLICA_A_ID = "owner-primary-dev-synthetic-01"
ELIGIBLE = "MB10_OWNER_ELIGIBLE"
REVALIDATE = "MB10_OWNER_REVALIDATE"
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_NAME = re.compile(r"[0-9]{2}-[0-9A-Za-z_]+\Z")


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_pkgc():
    """The pinned Package C operator (its readers, the canonical classifiers, `s25_check`), hash-gated."""
    source = HERE / "pkgc_operator.py"
    if _sha(source.read_bytes()) != PKGC_OPERATOR_SHA256:
        raise Refused("PKGC_OPERATOR_PIN_MISMATCH")
    import pkgc_operator

    return pkgc_operator


def s25_expected(sequence: str, *, a_tree: str, store_tree: str, record_file_sha256: str,
                 envelope_file_sha256: str) -> list[str]:
    """The exact `mb10_s25_pre` result block for this sequence (pure)."""
    return [
        "MB10_S25_STAGE=MB10_PRE", f"MB10_SEQUENCE={sequence}", f"BUNDLE_SHA256={S25_BUNDLE_SHA256}", "BUNDLE_VERIFIED",
        "CRYPTOGRAPHY_ED25519_SELFTEST=PASS", "CHAIN_AUTHENTICITY=AUTHENTIC", "CHAIN_ENTRIES=1",
        f"CHAIN_GENESIS={GENESIS}", f"A_VIEW_TREE_SHA256={a_tree}", f"A_STORE_VIEW_TREE_SHA256={store_tree}",
        f"REPLICA_B_MANIFEST_SHA256={REPLICA_B_MANIFEST_SHA256}", "REPLICA_B_LISTING=REPLICA.json records",
        "REPLICA_B_RECORDS=1", f"REPLICA_B_HEAD={RECORD_1}", f"REPLICA_B_FILE=000001-{RECORD_1}.json",
        f"REPLICA_B_FILE_SHA256={record_file_sha256}", "STORE_B=ACCEPTANCE_STORE_VERIFIED",
        f"STORE_B_MANIFEST_SHA256={STORE_B_MANIFEST_SHA256}", "STORE_B_LISTING=ACCEPTANCE.json envelopes",
        "STORE_B_ENVELOPES=1", f"STORE_B_FILE=000001-{ENVELOPE_1}.json", f"STORE_B_FILE_SHA256={envelope_file_sha256}",
        "PENDING=0", "FRESHNESS=AUTHENTIC:CURRENT", "ACCEPTANCE=ACCEPTANCE_COMPLETE",
    ]


def result_block_sha256(lines: list[str]) -> str:
    return _sha(("\n".join(lines) + "\n").encode("utf-8"))


def s25_check(expected: list[str], transcription: str) -> dict[str, Any]:
    """Exact, ordered equality with the expectation, then the phone's block hash over exactly those lines (the
    Package C rule, restated)."""
    lines = [line.strip() for line in transcription.splitlines() if line.strip()]
    block = lines[:-1] if lines and lines[-1].startswith("RESULT_BLOCK_SHA256=") else lines
    hashed = bool(lines) and lines[-1] == "RESULT_BLOCK_SHA256=" + result_block_sha256(expected)
    return {"exact": block == list(expected) and hashed, "missing": [x for x in expected if x not in block],
            "unexpected": [x for x in block if x not in expected], "evidenceClass": "OWNER_SCREEN_TRANSCRIPTION"}


def _pending(*roots: Path) -> int:
    count = 0
    for root in roots:
        for _dirpath, _dirs, files in os.walk(root):
            count += sum("pending" in name for name in files)
    return count


def _one_file(directory: Path) -> Path:
    files = sorted(directory.iterdir())
    if len(files) != 1:
        raise Refused("NOT_EXACTLY_ONE_FILE:" + directory.name)
    return files[0]


def gather(mb10_workdir: Path, export_name: str, s25_name: str, pkgc_workdir: Path, replica_a: Path, store_a: Path,
           *, pkgc=None) -> dict[str, Any]:
    """Every observed fact; nothing is judged here. Any failure to observe is recorded as UNKNOWN."""
    P = pkgc or load_pkgc()
    w, m = Path(pkgc_workdir), Path(mb10_workdir)
    export = m / "exports" / export_name
    s25 = m / "s25" / s25_name
    facts: dict[str, Any] = {}

    def observe(name: str, function: Callable[[], Any]) -> None:
        try:
            facts[name] = function()
        except Exception as exc:  # noqa: BLE001 - any failure is UNKNOWN, never eligibility
            facts[name] = None
            facts.setdefault("unknown", []).append(f"{name}:{type(exc).__name__}:{getattr(exc, 'reason', '')}")

    observe("mb10Sequence", lambda: json.loads((m / "sequence" / "D1_OPENING.json").read_text("utf-8"))["sequenceId"])
    observe("mb10OpenedAt", lambda: json.loads((m / "sequence" / "D1_OPENING.json").read_text("utf-8"))["openedAt"])
    observe("exportReceipt", lambda: json.loads((export / "RECEIPT.json").read_text("utf-8")))
    observe("exportReceiptSha256", lambda: _sha((export / "RECEIPT.json").read_bytes()))
    observe("s25Record", lambda: json.loads((s25 / "RECORD.json").read_text("utf-8")))
    observe("s25RecordSha256", lambda: _sha((s25 / "RECORD.json").read_bytes()))
    observe("sequenceId", lambda: json.loads((w / "C1_OPENING.json").read_text(encoding="utf-8"))["sequenceId"])
    observe("c5AcceptanceSha256", lambda: _sha((w / "C5_ACCEPTANCE.json").read_bytes()))
    observe("stopPresent", lambda: (w / "STOP.json").exists())
    observe("bindingSha256", lambda: P.load_binding(w)[1])
    observe("replicaADigests", lambda: list(P.T.load_replica(Path(replica_a)).digests))
    observe("replicaAId", lambda: P.T.load_replica(Path(replica_a)).replica_id)
    observe("storeADigests", lambda: list(P.T.load_acceptance_store(Path(store_a)).digests))
    observe("storeACustody", lambda: P.T.load_acceptance_store(Path(store_a)).custody_copy_id)
    observe("freshness", lambda: (lambda f: [f.authenticity, f.freshness])(
        P.laptop_freshness(w, Path(replica_a), "replica-b-1")))
    observe("acceptance", lambda: P.laptop_acceptance(w, Path(replica_a), Path(store_a), "replica-b-1",
                                                      "store-b-1").state)
    observe("pendingFiles", lambda: _pending(Path(replica_a), Path(store_a)))
    observe("freshChainSha256", lambda: _sha((export / "export" / "chain-1.json").read_bytes()))
    observe("freshPointerSha256", lambda: _sha((export / "export" / "witness.json").read_bytes()))
    observe("freshChainEqualsBinding", lambda: P._canonical_list(
        [P._json((export / "export" / "chain-1.json").read_bytes(), "GENESIS_INVALID")])
        == (w / P.BINDING_DIR / P.CHAIN_FILE).read_bytes())

    def s25_result() -> dict[str, Any]:
        expected = s25_expected(
            facts["mb10Sequence"], a_tree=P.tree_digest(Path(replica_a)), store_tree=P.tree_digest(Path(store_a)),
            record_file_sha256=_sha(_one_file(Path(replica_a) / "records").read_bytes()),
            envelope_file_sha256=_sha(_one_file(Path(store_a) / "envelopes").read_bytes()))
        transcription = (s25 / "TRANSCRIPTION.txt").read_bytes()
        result = s25_check(expected, transcription.decode("utf-8"))
        return {"exact": result["exact"], "missing": result["missing"], "unexpected": result["unexpected"],
                "transcriptionSha256": _sha(transcription), "resultBlockSha256": result_block_sha256(expected)}

    observe("s25", s25_result)
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
    sequence = facts.get("mb10Sequence")
    if not isinstance(sequence, str) or _HEX32.fullmatch(sequence) is None:
        reasons.append("UNKNOWN:mb10Sequence")
    receipt, record = facts.get("exportReceipt"), facts.get("s25Record")
    if not isinstance(receipt, Mapping) or receipt.get("sequenceId") != sequence:
        reasons.append("EXPORT_NOT_OF_THIS_SEQUENCE")
    if not isinstance(record, Mapping) or record.get("sequenceId") != sequence:
        reasons.append("S25_NOT_OF_THIS_SEQUENCE")
    elif not str(facts.get("mb10OpenedAt")) <= str(record.get("recordedAt")):
        reasons.append("S25_NOT_AFTER_D1")
    s25 = facts.get("s25")
    if not isinstance(s25, Mapping):
        reasons.append("UNKNOWN:s25")
    elif s25.get("exact") is not True:
        reasons.append("S25_OBSERVATION_NOT_EXACT")
    elif isinstance(record, Mapping) and record.get("transcriptionSha256") != s25.get("transcriptionSha256"):
        reasons.append("S25_TRANSCRIPTION_NOT_THE_RECORDED_ONE")
    reasons = sorted(set(reasons))
    return {"result": ELIGIBLE if not reasons else REVALIDATE, "reasons": reasons}


def evaluate(mb10_workdir: Path, export_name: str, s25_name: str, pkgc_workdir: Path, replica_a: Path,
             store_a: Path, out: Path, *, pkgc=None, now: Callable[[], datetime] | None = None) -> dict[str, Any]:
    for name in (export_name, s25_name):
        if not isinstance(name, str) or _NAME.fullmatch(name) is None:
            raise Refused("EVIDENCE_NAME_INVALID")
    facts = gather(mb10_workdir, export_name, s25_name, pkgc_workdir, replica_a, store_a, pkgc=pkgc)
    verdict = judge(facts)
    record = {"recordType": "LILITH_MB10_OWNER_ELIGIBILITY", "schemaVersion": 1,
              "observedAt": (now or (lambda: datetime.now(timezone.utc)))().strftime("%Y-%m-%dT%H:%M:%SZ"),
              "sequenceId": facts.get("mb10Sequence"), "exportName": export_name, "s25Name": s25_name,
              "exportReceiptSha256": facts.get("exportReceiptSha256"), "s25RecordSha256": facts.get("s25RecordSha256"),
              "pkgcOperatorSha256": PKGC_OPERATOR_SHA256,
              "accepted": {"record1": RECORD_1, "envelope1": ENVELOPE_1, "binding": BINDING_SHA256,
                           "c5Acceptance": C5_ACCEPTANCE_SHA256, "chain1": CHAIN_1_SHA256},
              "facts": facts, **verdict, "authorityGranted": False,
              "note": "owner-side evidence only: not an M-B10 authorization; the hold store is judged on the host"}
    data = json.dumps(record, sort_keys=True, indent=1, default=str).encode("utf-8") + b"\n"
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
        if len(argv) != 8 or argv[0] != "evaluate":
            raise Refused("USAGE")
        result = evaluate(Path(argv[1]), argv[2], argv[3], Path(argv[4]), Path(argv[5]), Path(argv[6]), Path(argv[7]))
    except Refused as exc:
        print(f"mb10_owner_eligibility: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(dict(result, authorityGranted=False), sort_keys=True, indent=2) + "\n")
    return 0 if result["result"] == ELIGIBLE else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
