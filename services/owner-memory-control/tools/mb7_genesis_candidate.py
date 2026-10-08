#!/usr/bin/env python3
"""15B2b-B1b-3e Package A (M-B7 PREPARE_GENESIS_CANDIDATE): OFF-HOST owner genesis-candidate derivation.

Record: docs/architecture/slice-15b2b-b1b3e-mb7-mb8-genesis-prep-package.md §3, §4.

Owner workstation only (WSL with the pinned wheels). It reads the three
owner-held accepted installables, writes nothing except under `emit` into a
NEW directory, and contacts nothing. It never touches K-ROOT, K-WIT or K-ACT
private material.

The candidate is the exact unsigned V2 witness genesis that the witness will
later sign at M-B9b, and its digest (`witness_v2_digest`, the signed-field
bytes; `signature` excluded). It is computed twice:

1. by the reviewed owner form `lilith_authority_owner_dev.py reproduce`
   (unchanged; `pr1_bootstrap.build_genesis_candidate` over registry v1, the
   root anchor and the registry-implied ledger position), and
2. by an independent restatement from the accepted public identities alone
   (`sha256("LILITH_RECOVERY_WITNESS_V2\\0" ‖ JCS(unsigned))`).

Both must agree, the ledger position must equal the owner-ACCEPTED M-B6 head,
and the anchor must name K-WIT.

| Form | Effect |
| --- | --- |
| `derive <authority-registry.v1.json> <registry-root.json> <witness-anchor.json> <updatedAt>` | the candidate, its digest, the exact install bytes of the pin and the register, and the exact expected stdout of the host M-B7 command; writes nothing |
| `emit <same four> <out-dir>` | derive twice, compare, refuse any value other than an already recorded P-A pin record, and write a NEW `<out-dir>` (`O_EXCL` files): `genesis-pin.json`, `authorization-register.json`, `pin-record.json`, `expected-host-stdout.txt`, `candidate.json`, `SHA256SUMS` |
| `compare-host <out-dir> <host-stdout>` | `MB7_HOST_CANDIDATE_EQUAL` only on byte equality of the host M-B7 stdout with `expected-host-stdout.txt` |
| `record-p-a <out-dir>` | ACT 2 only (record §14.2): the create-only P-A owner record in `/root/lilith-genesis-pin-dev-synthetic` (laptop WSL): the three record files, each `O_EXCL`; a byte-identical existing record is `OWNER_PIN_ALREADY_RECORDED_EQUAL`; anything else is a STOP |
| `check-copy <out-dir> <pin-dir>` | `OWNER_COPY_EQUAL` only if `<pin-dir>` holds exactly the three record files, each separately hashed and equal to the emitted bytes (P-A, a P-B transfer copy) |

`MB7_MB8_UPDATED_AT` (owner decision OD-2) is supplied by the owner and
captured once at the opening of the live sequence; no tool chooses or
replaces it. It must be a whole UTC second (`YYYY-MM-DDTHH:MM:SSZ`), not
earlier than Registry V1 `issuedAt`, and not later than the owner's clock now
(a future value would make every later witness successor fail
`WITNESS_TIME_REGRESSION`). A different value is a different candidate. Once
the P-A pin record exists, `emit` refuses any other value
(`UPDATED_AT_ALREADY_PINNED`).

    candidate != pin != committed genesis;  derived != owner-accepted;  digest equality != authorization
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OWNER_TOOL = ROOT / "services/authority-dev/ceremony/lilith_authority_owner_dev.py"

RESULT_TYPE = "LILITH_MB7_OWNER_GENESIS_CANDIDATE"
ENVIRONMENT = "dev"
WITNESS_V2_SEPARATOR = b"LILITH_RECOVERY_WITNESS_V2\x00"
WITNESS_PROTOCOL = "LILITH_RECOVERY_WITNESS"
WITNESS_V2_SCHEMA_VERSION = 2
PIN_TYPE = "LILITH_RECOVERY_WITNESS_V2_GENESIS_PIN"
REGISTER_TYPE = "LILITH_OWNER_AUTHORIZATION_REGISTER"
MAX_INPUT = 64 * 1024
_INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")

PIN_FILE = "genesis-pin.json"
REGISTER_FILE = "authorization-register.json"
HOST_STDOUT_FILE = "expected-host-stdout.txt"
CANDIDATE_FILE = "candidate.json"
RECORD_FILE = "pin-record.json"
SUMS_FILE = "SHA256SUMS"
EMITTED = (PIN_FILE, REGISTER_FILE, RECORD_FILE, HOST_STDOUT_FILE, CANDIDATE_FILE)
RECORD_TYPE = "LILITH_MB7_MB8_OWNER_PIN_RECORD"
# OD-3: the owner record files kept byte-identically in P-A and P-B (never the owner freshness register).
OWNER_RECORD_FILES = (PIN_FILE, REGISTER_FILE, RECORD_FILE)
# B-4 "dedicated pin directory" outside Replica A (`/root/lilith-owner-freshness/owner-primary-dev-synthetic-01`)
# and its parent, in the laptop WSL owner home. P-B is the same name in S25 Termux `$HOME` (procedural).
P_A_DIR = "/root/lilith-genesis-pin-dev-synthetic"
P_B_DIR = "$HOME/lilith-genesis-pin-dev-synthetic"


@dataclass(frozen=True)
class CandidatePinsV1:
    registry_sha256: str
    root_anchor_sha256: str
    witness_anchor_sha256: str
    registry_digest: str
    registry_issued_at: str
    ledger_head: str
    kwit_key_id: str
    kwit_public_key_sha256: str
    epoch_random: str
    policy_version: str


# The owner-accepted installables (M-B4/M-B5 decision; W5 verifier ACCEPTED_PINS), Registry V1 `issuedAt`
# (M-B3 completion record §1), and the owner-ACCEPTED M-B6 ledger head (sequence 1).
ACCEPTED_PINS = CandidatePinsV1(
    registry_sha256="46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e",
    root_anchor_sha256="bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687",
    witness_anchor_sha256="be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a",
    registry_digest="fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc",
    registry_issued_at="2026-10-06T15:16:21Z",
    ledger_head="19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630",
    kwit_key_id="test-only.witness.dev-synthetic.b1b3d.1",
    kwit_public_key_sha256="5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf",
    epoch_random="11f184889f333dece054f3b91a301632",
    policy_version="policy.dev-synthetic.v1",
)


class CandidateError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _need(condition: bool, reason: str) -> None:
    if not condition:
        raise CandidateError(reason)


def _sha(data: bytes) -> str:
    return hashlib.sha256(bytes(data)).hexdigest()


def independent_jcs(value: Any) -> bytes:
    """RFC 8785 restated for this value class only: objects, lists, null, printable-ASCII strings, ints < 2^53."""
    def check(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                _need(isinstance(key, str) and key.isascii() and key.isprintable(), "VALUE_NOT_SIMPLE")
                check(child)
        elif isinstance(item, list):
            for child in item:
                check(child)
        elif item is None:
            return
        elif isinstance(item, bool):
            raise CandidateError("VALUE_NOT_SIMPLE")
        elif isinstance(item, int):
            _need(0 <= item < 2 ** 53, "VALUE_NOT_SIMPLE")
        else:
            _need(isinstance(item, str) and item.isascii() and item.isprintable() and '"' not in item
                  and "\\" not in item, "VALUE_NOT_SIMPLE")
    check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def document_bytes(value: dict[str, Any]) -> bytes:
    """The one stored form of a public owner input (installer `_canonical_document`; no trailing newline)."""
    return independent_jcs(value)


def expected_unsigned(updated_at: str, pins: CandidatePinsV1 = ACCEPTED_PINS) -> dict[str, Any]:
    """The genesis body from the accepted identities alone (preflight §12; genesis semantics)."""
    return {
        "protocol": WITNESS_PROTOCOL, "schemaVersion": WITNESS_V2_SCHEMA_VERSION, "environment": ENVIRONMENT,
        "witnessVersion": 1, "previousWitnessDigest": None,
        "currentRecoveryEpoch": {"counter": 1, "random": pins.epoch_random},
        "registryVersion": 1, "registryDigest": pins.registry_digest, "policyVersion": pins.policy_version,
        "ledgerSequence": 1, "ledgerHead": pins.ledger_head, "consumedAuthorizationId": None,
        "updatedAt": updated_at, "witnessKeyId": pins.kwit_key_id,
    }


def independent_digest(unsigned: dict[str, Any]) -> str:
    return _sha(WITNESS_V2_SEPARATOR + independent_jcs(unsigned))


def pin_document(digest: str) -> dict[str, Any]:
    return {"pinType": PIN_TYPE, "schemaVersion": 1, "environment": ENVIRONMENT, "genesisWitnessDigest": digest}


def register_document(pins: CandidatePinsV1 = ACCEPTED_PINS) -> dict[str, Any]:
    """`authorizations: []` (genesis consumes none); `headRegistries: [(1, Registry V1)]` (preflight §22)."""
    return {"registerType": REGISTER_TYPE, "schemaVersion": 1, "environment": ENVIRONMENT, "authorizations": [],
            "headRegistries": [{"registryVersion": 1, "registryDigest": pins.registry_digest}]}


def pin_record_document(digest: str, updated_at: str, pin_bytes: bytes, register_bytes: bytes,
                        pins: CandidatePinsV1 = ACCEPTED_PINS) -> dict[str, Any]:
    """The owner bootstrap record binding `MB7_MB8_UPDATED_AT` to the pinned candidate (P-A, P-B)."""
    return {"recordType": RECORD_TYPE, "schemaVersion": 1, "environment": ENVIRONMENT, "updatedAt": updated_at,
            "candidateDigest": digest, "ledgerSequence": 1, "ledgerHead": pins.ledger_head,
            "registryDigest": pins.registry_digest, "genesisPinSha256": _sha(pin_bytes),
            "authorizationRegisterSha256": _sha(register_bytes)}


def host_stdout(digest: str, unsigned: dict[str, Any]) -> bytes:
    """`lilith-authority-verify-dev genesis-candidate 1 <updatedAt>` stdout (`genesis.candidate_report`, cli main)."""
    report = {"candidateDigest": digest, "unsignedGenesis": unsigned, "pin": pin_document(digest),
              "genesis": False, "authorityGranted": False}
    return json.dumps(report, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"


def check_updated_at(updated_at: str, *, now: datetime, pins: CandidatePinsV1 = ACCEPTED_PINS) -> None:
    _need(isinstance(updated_at, str) and _INSTANT.fullmatch(updated_at) is not None, "UPDATED_AT_INVALID")
    try:
        instant = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise CandidateError("UPDATED_AT_INVALID") from exc
    issued = datetime.strptime(pins.registry_issued_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    _need(instant >= issued, "UPDATED_AT_BEFORE_REGISTRY_ISSUED_AT")
    _need(instant <= now, "UPDATED_AT_IN_THE_FUTURE")


def load_owner_tool():
    """The reviewed owner form, unchanged; registered in `sys.modules` before execution."""
    name = "lilith_authority_owner_dev_mb7"
    spec = importlib.util.spec_from_file_location(name, OWNER_TOOL)
    _need(spec is not None and spec.loader is not None, "OWNER_TOOL_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        if sys.modules.get(name) is module:
            del sys.modules[name]
        raise CandidateError("OWNER_TOOL_LOAD_FAILED") from exc
    return module


def _document(data: bytes) -> dict[str, Any]:
    def no_duplicates(pairs):
        value = {}
        for key, item in pairs:
            _need(key not in value, "INPUT_DUPLICATE_KEY")
            value[key] = item
        return value
    try:
        value = json.loads(data.decode("ascii"), object_pairs_hook=no_duplicates)
    except (UnicodeDecodeError, ValueError) as exc:
        raise CandidateError("INPUT_NOT_JSON") from exc
    _need(isinstance(value, dict), "INPUT_NOT_JSON")
    return value


def derive(registry_bytes: bytes, root_bytes: bytes, anchor_bytes: bytes, updated_at: str, *,
           pins: CandidatePinsV1 = ACCEPTED_PINS, now: Callable[[], datetime] | None = None,
           owner_tool=None) -> dict[str, Any]:
    """`pins`, `now` and `owner_tool` are TEST seams."""
    check_updated_at(updated_at, now=(now or (lambda: datetime.now(timezone.utc)))(), pins=pins)
    _need(_sha(registry_bytes) == pins.registry_sha256, "REGISTRY_NOT_THE_ACCEPTED_INSTALLABLE")
    _need(_sha(root_bytes) == pins.root_anchor_sha256, "ROOT_ANCHOR_NOT_THE_ACCEPTED_INSTALLABLE")
    _need(_sha(anchor_bytes) == pins.witness_anchor_sha256, "WITNESS_ANCHOR_NOT_THE_ACCEPTED_INSTALLABLE")
    registry, root, anchor = _document(registry_bytes), _document(root_bytes), _document(anchor_bytes)
    _need(registry.get("issuedAt") == pins.registry_issued_at, "REGISTRY_ISSUED_AT_NOT_ACCEPTED")
    tool = owner_tool or load_owner_tool()
    try:
        reproduced = tool.reproduce(registry, root, anchor, updated_at)
    except Exception as exc:  # noqa: BLE001 - any refusal of the reviewed form fails closed
        raise CandidateError("REPRODUCE_REFUSED:" + type(exc).__name__) from exc
    _need(reproduced.get("registryVerified") is True, "REGISTRY_NOT_VERIFIED")
    _need(reproduced.get("registryHead") == {"registryVersion": 1, "registryDigest": pins.registry_digest},
          "REGISTRY_HEAD_NOT_ACCEPTED")
    _need((reproduced.get("ledgerSequence"), reproduced.get("ledgerHead")) == (1, pins.ledger_head),
          "LEDGER_POSITION_NOT_OWNER_ACCEPTED")
    _need(reproduced.get("witnessKeyId") == pins.kwit_key_id, "WITNESS_ANCHOR_NOT_KWIT")
    _need(anchor.get("witnessKeyId") == pins.kwit_key_id and anchor.get("environment") == ENVIRONMENT,
          "WITNESS_ANCHOR_NOT_KWIT")
    unsigned = expected_unsigned(updated_at, pins)
    _need(reproduced.get("unsignedGenesis") == unsigned, "UNSIGNED_GENESIS_DISAGREES")
    digest = independent_digest(unsigned)
    _need(reproduced.get("genesisCandidateDigest") == digest, "CANDIDATE_DIGEST_DISAGREES")
    _need(_HEX64.fullmatch(digest) is not None, "CANDIDATE_DIGEST_DISAGREES")
    pin, register = pin_document(digest), register_document(pins)
    _need(reproduced.get("genesisPin") == pin, "PIN_DISAGREES")
    _need(reproduced.get("authorizationRegister") == register, "REGISTER_DISAGREES")
    pin_bytes, register_bytes, stdout = document_bytes(pin), document_bytes(register), host_stdout(digest, unsigned)
    record_bytes = document_bytes(pin_record_document(digest, updated_at, pin_bytes, register_bytes, pins))
    return {
        "resultType": RESULT_TYPE, "schemaVersion": 1, "environment": ENVIRONMENT,
        "inputs": {"registrySha256": _sha(registry_bytes), "rootAnchorSha256": _sha(root_bytes),
                   "witnessAnchorSha256": _sha(anchor_bytes)},
        "updatedAt": updated_at, "ledgerSequence": 1, "ledgerHead": pins.ledger_head,
        "registryHead": {"registryVersion": 1, "registryDigest": pins.registry_digest},
        "witnessKeyId": pins.kwit_key_id, "unsignedGenesis": unsigned,
        "unsignedGenesisJcsSha256": _sha(independent_jcs(unsigned)), "candidateDigest": digest,
        "genesisPin": pin, "genesisPinBytes": pin_bytes.decode("ascii"), "genesisPinSha256": _sha(pin_bytes),
        "authorizationRegister": register, "authorizationRegisterBytes": register_bytes.decode("ascii"),
        "authorizationRegisterSha256": _sha(register_bytes),
        "pinRecordBytes": record_bytes.decode("ascii"), "pinRecordSha256": _sha(record_bytes),
        "expectedHostStdout": stdout.decode("ascii"), "expectedHostStdoutSha256": _sha(stdout),
        "ownerComputed": True, "accepted": False, "pinned": False, "genesis": False, "authorityGranted": False,
    }


def _write_new(path: Path, data: bytes) -> None:
    # O_BINARY: on Windows a text-mode descriptor would turn every LF into CRLF and change the install bytes.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def recorded_pin(pin_dir: Path | str = P_A_DIR) -> dict[str, Any] | None:
    """The owner pin record already in `pin_dir`, or None when none is recorded."""
    path = Path(pin_dir) / RECORD_FILE
    if not path.exists() and not path.is_symlink():
        return None
    _need(path.is_file() and not path.is_symlink(), "OWNER_RECORD_UNSAFE")
    return _document(path.read_bytes())


def emit(registry_bytes: bytes, root_bytes: bytes, anchor_bytes: bytes, updated_at: str, out: Path, *,
         pin_dir: Path | str = P_A_DIR, **seams: Any) -> dict[str, Any]:
    """`pin_dir` is a TEST seam: the real P-A record is the only prior value that binds (OD-2)."""
    prior = recorded_pin(pin_dir)
    if prior is not None:
        _need(prior.get("updatedAt") == updated_at, "UPDATED_AT_ALREADY_PINNED")
    first = derive(registry_bytes, root_bytes, anchor_bytes, updated_at, **seams)
    second = derive(registry_bytes, root_bytes, anchor_bytes, updated_at, **seams)
    _need(first == second, "DERIVATION_NOT_DETERMINISTIC")
    if prior is not None:
        _need(prior.get("candidateDigest") == first["candidateDigest"], "CANDIDATE_ALREADY_PINNED")
    return write_emitted(first, out)


def write_emitted(first: dict[str, Any], out: Path) -> dict[str, Any]:
    """Write one derivation into a NEW directory (`O_EXCL` files, then SHA256SUMS)."""
    out = Path(out)
    _need(not out.exists() and not out.is_symlink(), "OUT_DIRECTORY_EXISTS")
    out.mkdir(mode=0o700)
    files = {PIN_FILE: first["genesisPinBytes"].encode("ascii"),
             REGISTER_FILE: first["authorizationRegisterBytes"].encode("ascii"),
             RECORD_FILE: first["pinRecordBytes"].encode("ascii"),
             HOST_STDOUT_FILE: first["expectedHostStdout"].encode("ascii"),
             CANDIDATE_FILE: (json.dumps(first, sort_keys=True, indent=2) + "\n").encode("ascii")}
    for name, data in files.items():
        _write_new(out / name, data)
    sums = "".join(f"{_sha(files[name])}  {name}\n" for name in sorted(files)).encode("ascii")
    _write_new(out / SUMS_FILE, sums)
    return {"resultType": RESULT_TYPE, "candidateDigest": first["candidateDigest"], "updatedAt": first["updatedAt"],
            "files": {name: _sha(data) for name, data in sorted(files.items())}, "sha256sums": _sha(sums),
            "accepted": False, "pinned": False, "authorityGranted": False,
            "result": "MB7_OWNER_CANDIDATE_EMITTED_FOR_OWNER_DECISION"}


def load_emitted(out: Path) -> dict[str, bytes]:
    out = Path(out)
    _need(out.is_dir() and not out.is_symlink(), "EMITTED_DIRECTORY_ABSENT")
    _need(sorted(p.name for p in out.iterdir()) == sorted(EMITTED + (SUMS_FILE,)), "EMITTED_DIRECTORY_INEXACT")
    files = {name: (out / name).read_bytes() for name in EMITTED}
    sums = "".join(f"{_sha(files[name])}  {name}\n" for name in sorted(files)).encode("ascii")
    _need((out / SUMS_FILE).read_bytes() == sums, "EMITTED_SHA256SUMS_MISMATCH")
    candidate = json.loads(files[CANDIDATE_FILE].decode("ascii"))
    _need(files[PIN_FILE] == candidate["genesisPinBytes"].encode("ascii")
          and files[REGISTER_FILE] == candidate["authorizationRegisterBytes"].encode("ascii")
          and files[RECORD_FILE] == candidate["pinRecordBytes"].encode("ascii")
          and files[HOST_STDOUT_FILE] == candidate["expectedHostStdout"].encode("ascii"), "EMITTED_FILES_INCONSISTENT")
    return files


def compare_host(out: Path, host: bytes) -> dict[str, Any]:
    files = load_emitted(out)
    candidate = json.loads(files[CANDIDATE_FILE].decode("ascii"))
    expected = files[HOST_STDOUT_FILE]
    host = bytes(host)
    equal = host == expected
    differing: list[str] = []
    if not equal:
        try:
            observed = json.loads(host.decode("utf-8"))
            reference = json.loads(expected.decode("ascii"))
            differing = sorted(k for k in set(observed) | set(reference) if observed.get(k) != reference.get(k))
        except (UnicodeDecodeError, ValueError):
            differing = ["<not-json>"]
    return {"resultType": "LILITH_MB7_HOST_CANDIDATE_COMPARISON", "candidateDigest": candidate["candidateDigest"],
            "expectedSha256": _sha(expected), "observedSha256": _sha(host), "differingFields": differing,
            "result": "MB7_HOST_CANDIDATE_EQUAL" if equal else "MB7_HOST_CANDIDATE_DIFFERS",
            "accepted": False, "authorityGranted": False}


def _owner_listing(pin_dir: Path) -> list[str]:
    _need(pin_dir.is_dir() and not pin_dir.is_symlink(), "OWNER_RECORD_DIRECTORY_ABSENT")
    names = sorted(p.name for p in pin_dir.iterdir())
    _need(set(names) <= set(OWNER_RECORD_FILES), "OWNER_RECORD_DIRECTORY_UNEXPECTED_ENTRY")
    return names


def check_copy(out: Path, pin_dir: Path) -> dict[str, Any]:
    """Each owner record file in `pin_dir`, separately hashed, against the emitted bytes."""
    files, pin_dir = load_emitted(out), Path(pin_dir)
    names = _owner_listing(pin_dir)
    observed = {}
    for name in OWNER_RECORD_FILES:
        path = pin_dir / name
        _need(name not in names or (path.is_file() and not path.is_symlink()), "OWNER_RECORD_UNSAFE")
        observed[name] = _sha(path.read_bytes()) if name in names else None
    expected = {name: _sha(files[name]) for name in OWNER_RECORD_FILES}
    return {"observed": observed, "expected": expected,
            "result": "OWNER_COPY_EQUAL" if observed == expected else "OWNER_COPY_DIFFERS", "authorityGranted": False}


def record(out: Path, pin_dir: Path | str = P_A_DIR) -> dict[str, Any]:
    """ACT 2 only: the create-only P-A owner record. Never replaces a byte; a different record is a STOP."""
    files, pin_dir = load_emitted(out), Path(pin_dir)
    if not pin_dir.exists() and not pin_dir.is_symlink():
        pin_dir.mkdir(mode=0o700)
    names = _owner_listing(pin_dir)
    for name in names:
        path = pin_dir / name
        _need(path.is_file() and not path.is_symlink() and path.read_bytes() == files[name], "OWNER_RECORD_CONFLICT")
    written = [name for name in OWNER_RECORD_FILES if name not in names]
    for name in written:
        _write_new(pin_dir / name, files[name])
    if written and os.name == "posix":
        fd = os.open(pin_dir, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    result = check_copy(out, pin_dir)
    _need(result["result"] == "OWNER_COPY_EQUAL", "OWNER_RECORD_INCOMPLETE")
    return dict(result, written=written,
                result="OWNER_PIN_RECORDED" if written else "OWNER_PIN_ALREADY_RECORDED_EQUAL")


def _read(path: str, limit: int = MAX_INPUT) -> bytes:
    data = Path(path).read_bytes()
    _need(len(data) <= limit, "INPUT_TOO_LARGE")
    return data


def main(argv: list[str]) -> int:
    try:
        if len(argv) == 5 and argv[0] == "derive":
            result = derive(_read(argv[1]), _read(argv[2]), _read(argv[3]), argv[4])
        elif len(argv) == 6 and argv[0] == "emit":
            result = emit(_read(argv[1]), _read(argv[2]), _read(argv[3]), argv[4], Path(argv[5]))
        elif len(argv) == 3 and argv[0] == "compare-host":
            result = compare_host(Path(argv[1]), _read(argv[2]))
        elif len(argv) == 3 and argv[0] == "check-copy":
            result = check_copy(Path(argv[1]), Path(argv[2]))
        elif len(argv) == 2 and argv[0] == "record-p-a":
            result = record(Path(argv[1]))
        else:
            raise CandidateError("USAGE")
    except (CandidateError, OSError) as exc:
        print(f"mb7_genesis_candidate: REFUSED {getattr(exc, 'reason', type(exc).__name__)}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return 0 if result.get("result") in (None, "MB7_HOST_CANDIDATE_EQUAL", "OWNER_COPY_EQUAL", "OWNER_PIN_RECORDED",
                                         "OWNER_PIN_ALREADY_RECORDED_EQUAL",
                                         "MB7_OWNER_CANDIDATE_EMITTED_FOR_OWNER_DECISION") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
