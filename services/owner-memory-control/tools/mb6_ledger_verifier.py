#!/usr/bin/env python3
"""15B2b-B1b-3e M-B6 PROVISION_LEDGER: READ-ONLY ledger POST verifier and W6 crash classifier (DEV).

Record: docs/architecture/slice-15b2b-b1b3e-mb6-ledger-remediation.md §3, §4.

M-B6 is `lilith-authority-ledger-dev provision 1`: a root half that creates
`/var/lib/lilith-authority-dev` and a signer half (runuser) that creates
`authority_ledger.db` with exactly one ledger-journal `GENESIS` op at
sequence 1. This tool judges the host after (or instead of) that one
invocation. It produces, from observed content, the three evidence items
the sequencer requires for `PROVISION_LEDGER` (`pr1b_sequencing.STEPS`):

    ledgerSequenceIsOne   ledgerHeadEqualsOwnerComputed   ledgerSchemaFingerprintVerified

and classifies the host into exactly one W6 host phase. It is never a
shape-only check: `install_authority_dev.py status --expect P1B-6` stays the
owner of the path/mode contract, and the accepted M-B4/M-B5 content verifier
(`mb4_mb5_trust_install_verifier.evaluate`, imported unchanged) stays the
judge of the installed trust anchors and Registry V1.

The ledger is read WITHOUT opening it: the database file and its WAL are
read as bytes through bounded `O_NOFOLLOW` descriptors, the committed state
is rebuilt in memory by the SQLite WAL recovery rule (header and frame
checksums, salts, last commit frame), and that image is examined through an
in-memory `sqlite3` connection (`deserialize`). Nothing is written: no
temporary copy, no `-shm`, no checkpoint, no lock on the live file.

It runs on DEV as root with the installed release interpreter, streamed by
the M-B6 operator as one hash-gated bundle together with the W5 verifier:

    sudo /opt/lilith-authority-dev/current/venv/bin/python -I -B -c <bundle bootstrap> <pins> observe <head>
    ...                                                                                 expect <PHASE> <head>

`<head>` is the owner-computed expected ledger head (64 hex), never a host
value. It takes no path argument. It never opens a credential, the
credstore, the host credential key or the K-WIT blob; never decrypts,
signs, starts, stops, reloads or enables anything; and contacts nothing.

    ledger provisioned != authority state accepted     ledger existence != authority
    ledger GENESIS op != witness genesis candidate != OwnerGenesisPinV1 != committed witness genesis
    LEDGER_COMMITTED_EXACT != owner acceptance != M-B7 authorization
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

VERIFIER_TYPE = "LILITH_MB6_LEDGER_VERIFICATION"
ENVIRONMENT = "dev"
PROFILE = "DEV_SYNTHETIC"
DEV_HOSTNAME = "lilith-dev-01"
DEV_MACHINE_ID = "ae929170e6fa4c8ab9cc7b9547238d9d"
RELEASE_TREE = "/opt/lilith-authority-dev/current"
SIGNER_USER = "lilith-authority-dev"

STATE_DIR = "/var/lib/lilith-authority-dev"
LEDGER = STATE_DIR + "/authority_ledger.db"
LEDGER_NAME = "authority_ledger.db"
WAL_NAME = LEDGER_NAME + "-wal"
SHM_NAME = LEDGER_NAME + "-shm"
STATE_NAMES = frozenset({LEDGER_NAME, WAL_NAME, SHM_NAME})   # a `-journal` is never produced: unclassified
OWNER_INPUT_DIR = "/etc/lilith-authority-dev/owner"
HOLD_STORE = "/var/lib/lilith-authority-custody/holds"
# M-B8 and later host state. Any one present: this tool's scope has ended.
LATER_PATHS = (
    "/var/lib/lilith-recovery-witness",                         # M-B9a witness state (and the genesis chain)
    "/run/credentials/lilith-recovery-witness.service",          # witness running
    "/run/credentials/lilith-authority-dev.service",             # signer running (K-ACT loaded)
    "/run/lilith-authority-dev/owner.sock",
    "/run/lilith-recovery-witness/owner.sock",
    "/run/lilith-recovery-witness/signer.sock",
)
EMPTY_LISTINGS = (OWNER_INPUT_DIR, HOLD_STORE)                  # M-B8 owner copies; M-B10 HELD
# M-B6 never clears these: they stay until M-B8 (`install-owner-inputs`).
EXPECTED_HOST_INPUT_REASONS = frozenset({"AUTHORIZATION_REGISTER_COPY_MISSING", "GENESIS_PIN_COPY_MISSING"})

MAX_LEDGER_BYTES = 4 * 1024 * 1024
LEDGER_HEAD_DOMAIN_SEPARATOR = b"LILITH_AUTHORITY_LEDGER_HEAD_V1\x00"
GENESIS_HEAD = "0" * 64

EVIDENCE = ("ledgerSequenceIsOne", "ledgerHeadEqualsOwnerComputed", "ledgerSchemaFingerprintVerified")

# ------------------------------------------------------------------ phases ---
# Host phases (what the host alone shows).
W6_0 = "W6_0_NO_MB6_MUTATION"
W6_1 = "W6_1_STATE_DIRECTORY_INEXACT"
W6_2 = "W6_2_STATE_DIRECTORY_EXACT_EMPTY"
W6_3 = "W6_3_LEDGER_INCOMPLETE"
COMMITTED = "LEDGER_COMMITTED_EXACT"          # W6-4, W6-5 or W6-6: only the sequence records tell them apart
LATER_STATE = "OUT_OF_SCOPE_LATER_STATE"
UNCLASSIFIED = "UNCLASSIFIED_STOP"
HOST_PHASES = (W6_0, W6_1, W6_2, W6_3, COMMITTED, LATER_STATE, UNCLASSIFIED)
# Sequence phases (host phase + the operator's attempt marker, transcript and POST record).
W6_4 = "W6_4_COMMITTED_CLI_INCOMPLETE"
W6_5 = "W6_5_CLI_SUCCEEDED_POST_PENDING"
W6_6 = "W6_6_POST_VERIFIED_ACCEPTANCE_PENDING"
SEQUENCE_PHASES = (W6_0, W6_1, W6_2, W6_3, W6_4, W6_5, W6_6, LATER_STATE, UNCLASSIFIED)

# Transcript classes of the one `provision 1` invocation (classify_transcript).
NOT_INVOKED = "NOT_INVOKED"
CLI_SUCCESS_EXACT = "CLI_SUCCESS_EXACT"
CLI_REFUSED = "CLI_REFUSED"
CLI_FAILED_UNCLASSIFIED = "CLI_FAILED_UNCLASSIFIED"
GUARD_STOPPED = "GUARD_STOPPED"                # the host guard exited before the CLI ran
TRANSPORT_FAILED = "TRANSPORT_FAILED"          # ssh/IAP: whether the CLI ran is unknown
TRANSCRIPT_CLASSES = (NOT_INVOKED, CLI_SUCCESS_EXACT, CLI_REFUSED, CLI_FAILED_UNCLASSIFIED, GUARD_STOPPED,
                      TRANSPORT_FAILED)


@dataclass(frozen=True)
class LedgerPinsV1:
    """Accepted identities the M-B6 ledger is judged against. TEST seam: tests pass their own."""

    schema_fingerprint: str
    kact_key_id: str
    epoch_counter: int
    epoch_random: str
    policy_version: str
    registry_version: int


# `lilith_authority_dev.ledger.SCHEMA_FINGERPRINT` of release aee323e (unchanged at control), and the
# Registry V1 values accepted at M-B3 / W5 (completion record §1; W5 verifier ACCEPTED_PINS).
ACCEPTED_PINS = LedgerPinsV1(
    schema_fingerprint="65127a68c61d4dba390e01c61d01a76fdc54e830c374cb05069b0ab0c50d9cb7",
    kact_key_id="test-only.dev-synthetic.actor.b1b3d.1",
    epoch_counter=1,
    epoch_random="11f184889f333dece054f3b91a301632",
    policy_version="policy.dev-synthetic.v1",
    registry_version=1,
)


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class WalError(Exception):
    """The WAL cannot be applied deterministically (for example a page-size disagreement)."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(bytes(data)).hexdigest()


def _host(root: Path, absolute: str) -> Path:
    return root / absolute.lstrip("/")


def _jcs(value: Any) -> bytes:
    """RFC 8785 for the ledger op's value class (ASCII strings, small non-negative ints, lists, objects)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def ledger_head(op: Mapping[str, Any], previous: str = GENESIS_HEAD) -> str:
    """The accepted ledger head function, restated: sha256(sep ‖ prevHead ‖ JCS(op))."""
    return hashlib.sha256(LEDGER_HEAD_DOMAIN_SEPARATOR + bytes.fromhex(previous) + _jcs(op)).hexdigest()


def pinned_genesis_op(pins: LedgerPinsV1 = ACCEPTED_PINS) -> dict[str, Any]:
    """The GENESIS op that Registry V1, as accepted, implies (`authority_ledger_journal.genesis_op`)."""
    return {"op": "GENESIS", "environment": ENVIRONMENT,
            "recoveryEpoch": {"counter": pins.epoch_counter, "random": pins.epoch_random},
            "policyVersion": pins.policy_version, "registryVersion": pins.registry_version,
            "signingKeyIds": [pins.kact_key_id]}


# ------------------------------------------------------------- byte reads ---

def _lstat(path: Path) -> os.stat_result | None:
    try:
        return os.lstat(path)
    except FileNotFoundError:
        return None


def _facts(meta: os.stat_result | None) -> dict[str, Any]:
    if meta is None:
        return {"state": "ABSENT"}
    kind = ("symlink" if stat.S_ISLNK(meta.st_mode) else "dir" if stat.S_ISDIR(meta.st_mode)
            else "file" if stat.S_ISREG(meta.st_mode) else "other")
    return {"state": "PRESENT", "kind": kind, "uid": meta.st_uid, "gid": meta.st_gid,
            "mode": format(stat.S_IMODE(meta.st_mode), "04o"), "size": meta.st_size, "inode": meta.st_ino}


def _read(path: Path, limit: int = MAX_LEDGER_BYTES) -> bytes:
    """Bytes of one bounded regular file, never through a symlink; never opened for writing."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > limit:
            raise Refused("LEDGER_FILE_UNBOUNDED")
        chunks, total = [], 0
        while chunk := os.read(fd, 65536):
            total += len(chunk)
            if total > limit:
                raise Refused("LEDGER_FILE_UNBOUNDED")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def _listing(root: Path, absolute: str) -> list[str] | None:
    path = _host(root, absolute)
    meta = _lstat(path)
    if meta is None:
        return None
    if not stat.S_ISDIR(meta.st_mode):
        return ["<not-a-directory>"]
    return sorted(os.listdir(path))


# ------------------------------------------------------- WAL (in memory) ---

WAL_MAGIC_LE, WAL_MAGIC_BE = 0x377F0682, 0x377F0683
WAL_VERSION = 3007000
WAL_HEADER = 32
FRAME_HEADER = 24


def _checksum(data: bytes, s0: int, s1: int, big_endian: bool) -> tuple[int, int]:
    words = struct.unpack((">" if big_endian else "<") + f"{len(data) // 4}I", data)
    for i in range(0, len(words), 2):
        s0 = (s0 + words[i] + s1) & 0xFFFFFFFF
        s1 = (s1 + words[i + 1] + s0) & 0xFFFFFFFF
    return s0, s1


def parse_wal(wal: bytes) -> dict[str, Any]:
    """SQLite WAL recovery, read-only: the valid frames up to the last commit frame.

    The header is valid only with the magic, version 3007000, a power-of-two
    page size in [512, 65536] and a matching header checksum; an invalid
    header means SQLite ignores the WAL. Frames are read in order while their
    salts equal the header salts, the page number is non-zero and the
    cumulative checksum matches; reading stops at the first invalid frame.
    Only frames up to the last commit frame (non-zero database size) count."""
    facts: dict[str, Any] = {"size": len(wal), "headerValid": False, "pageSize": None, "validFrames": 0,
                             "committedFrames": 0, "commitSizePages": None, "trailingBytes": 0}
    if len(wal) < WAL_HEADER:
        facts["trailingBytes"] = len(wal)
        return dict(facts, frames=[])
    magic, version, page_size, _checkpoint, salt1, salt2, c1, c2 = struct.unpack(">8I", wal[:WAL_HEADER])
    big = magic == WAL_MAGIC_BE
    if (magic not in (WAL_MAGIC_LE, WAL_MAGIC_BE) or version != WAL_VERSION or page_size < 512
            or page_size > 65536 or page_size & (page_size - 1)
            or _checksum(wal[:24], 0, 0, big) != (c1, c2)):
        return dict(facts, frames=[])
    facts.update(headerValid=True, pageSize=page_size)
    s0, s1 = c1, c2
    frames, committed, offset = [], [], WAL_HEADER
    while offset + FRAME_HEADER + page_size <= len(wal):
        header = wal[offset:offset + FRAME_HEADER]
        page = wal[offset + FRAME_HEADER:offset + FRAME_HEADER + page_size]
        pgno, commit, f_salt1, f_salt2, f_c1, f_c2 = struct.unpack(">6I", header)
        if (f_salt1, f_salt2) != (salt1, salt2) or pgno == 0:
            break
        n0, n1 = _checksum(header[:8], s0, s1, big)
        n0, n1 = _checksum(page, n0, n1, big)
        if (n0, n1) != (f_c1, f_c2):
            break
        s0, s1 = n0, n1
        frames.append((pgno, commit, page))
        if commit:
            committed = list(frames)
        offset += FRAME_HEADER + page_size
    facts.update(validFrames=len(frames), committedFrames=len(committed), trailingBytes=len(wal) - offset,
                 commitSizePages=committed[-1][1] if committed else None)
    return dict(facts, frames=committed)


def committed_image(db: bytes, wal: bytes | None) -> tuple[bytes, dict[str, Any]]:
    """The committed database image: the main file with every committed WAL frame applied."""
    if wal is None:
        return bytes(db), {"present": False}
    parsed = parse_wal(wal)
    frames = parsed.pop("frames")
    facts = dict(parsed, present=True)
    if not frames:
        return bytes(db), facts
    page_size = parsed["pageSize"]
    if len(db) >= 100:
        declared = struct.unpack(">H", db[16:18])[0]
        if (65536 if declared == 1 else declared) != page_size:
            raise WalError("WAL_PAGE_SIZE_DIFFERS_FROM_DATABASE")
    elif db:
        raise WalError("DATABASE_HEADER_TRUNCATED")
    image = bytearray(db)
    for pgno, _commit, page in frames:
        start = (pgno - 1) * page_size
        if len(image) < start + page_size:
            image.extend(b"\x00" * (start + page_size - len(image)))
        image[start:start + page_size] = page
    size = frames[-1][1] * page_size
    image = image[:size] if len(image) >= size else image + b"\x00" * (size - len(image))
    return bytes(image), facts


# ------------------------------------------------------- image (in memory) ---

def examine_image(image: bytes) -> dict[str, Any]:
    """Every fact the POST needs, from an in-memory copy of the committed image."""
    if not image:
        return {"state": "EMPTY"}
    if len(image) < 100 or image[:16] != b"SQLite format 3\x00":
        return {"state": "NOT_A_DATABASE", "imageSha256": _sha(image)}
    facts: dict[str, Any] = {"imageSha256": _sha(image), "walModeHeader": [image[18], image[19]]}
    patched = bytearray(image)
    patched[18] = patched[19] = 1          # the in-memory VFS has no WAL; the original flags are reported above
    conn = sqlite3.connect(":memory:")
    try:
        conn.deserialize(bytes(patched))
        conn.execute("PRAGMA trusted_schema = OFF")
        conn.execute("PRAGMA query_only = ON")
        facts["integrity"] = [row[0] for row in conn.execute("PRAGMA integrity_check")]
        statements = [row[0] for row in conn.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'")]
        facts["schemaStatements"] = len(statements)
        if not statements:
            return dict(facts, state="NO_SCHEMA")
        facts["schemaFingerprint"] = _sha("\n".join(sorted(statements)).encode("utf-8"))
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        required = {"authority_meta_v1", "authority_journal_v1", "authority_epoch_v1", "authority_challenge_v2",
                    "authority_evidence_v2", "authority_evidence_use_v1"}
        if not required <= names:
            return dict(facts, state="SCHEMA_INEXACT")
        facts["meta"] = [list(row) for row in conn.execute(
            "SELECT singleton, schema_version, environment, profile FROM authority_meta_v1 ORDER BY singleton")]
        facts["journal"] = [[seq, op, bytes(payload).decode("utf-8", "replace"), prev, head, epoch]
                            for seq, op, payload, prev, head, epoch in conn.execute(
                                "SELECT seq, op, payload, prev_head, head, ledger_epoch FROM authority_journal_v1 "
                                "ORDER BY seq")]
        facts["epochs"] = [list(row) for row in conn.execute(
            "SELECT adoption_seq, counter, random, epoch_digest, ledger_epoch FROM authority_epoch_v1 "
            "ORDER BY adoption_seq")]
        facts["otherRows"] = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                              for table in ("authority_challenge_v2", "authority_evidence_v2",
                                            "authority_evidence_use_v1")}
        return dict(facts, state="COMMITTED")
    except sqlite3.Error as exc:
        return dict(facts, state="NOT_A_DATABASE", error=type(exc).__name__)
    finally:
        conn.close()


# ---------------------------------------------------------------- evaluate ---

def _release_modules():
    import mb4_mb5_trust_install_verifier as V5
    from lilith_authority_dev import ledger as L
    from lilith_authority_host import inputs as HI
    from lilith_owner_memory import authority_contracts as A
    from lilith_owner_memory import authority_ledger_journal as J
    from lilith_owner_memory import recovery_contracts as R
    from lilith_owner_memory.contracts import _canonical
    return V5, L, HI, A, J, R, _canonical


def _signer_ids() -> tuple[int, int]:
    import pwd

    entry = pwd.getpwnam(SIGNER_USER)
    return entry.pw_uid, entry.pw_gid


def evaluate(expected_head: str, *, root: Path | str = Path("/"), owner_uid: int = 0, owner_gid: int = 0,
             signer: tuple[int, int] | None = None, pins: LedgerPinsV1 = ACCEPTED_PINS,
             trust_pins: Any = None) -> dict[str, Any]:
    """One read-only observation and judgment. `root`, `owner_*`, `signer`, `pins`, `trust_pins` are TEST seams."""
    if not (isinstance(expected_head, str) and len(expected_head) == 64
            and all(c in "0123456789abcdef" for c in expected_head)):
        raise Refused("EXPECTED_HEAD_INVALID")
    V5, L, HI, A, J, R, canonical = _release_modules()
    root = Path(root)
    signer_uid, signer_gid = signer if signer is not None else _signer_ids()
    failures: list[str] = []

    # Trust anchors and Registry V1: the accepted W5 content judgment, unchanged.
    trust = V5.evaluate(root=root, owner_uid=owner_uid, owner_gid=owner_gid,
                        **({} if trust_pins is None else {"pins": trust_pins}))
    trust_exact = all(trust["evidence"].get(name) is True for name in V5.EVIDENCE)
    if not trust_exact:
        failures.append("TRUST_REGISTRY_NOT_EXACT")
    host = HI.read_host_inputs(environment=ENVIRONMENT, root=root, owner_uid=owner_uid)
    reasons = set(host.reasons)
    gaps_preserved = reasons == EXPECTED_HOST_INPUT_REASONS
    if not gaps_preserved:
        failures.append("HOST_INPUT_REASONS_NOT_EXACTLY_W5_GAPS")

    # The genesis op: derived from the INSTALLED registry by the release journal, and from the accepted pins.
    expected_op = pinned_genesis_op(pins)
    registry_op = None
    registry = next((r for r in host.registries if r.get("registryVersion") == pins.registry_version), None)
    if registry is not None:
        try:
            registry_op = J.genesis_op(registry)
        except Exception:  # noqa: BLE001 - any refusal of the installed registry fails closed
            registry_op = None
    op_matches_registry = registry_op == expected_op
    if not op_matches_registry:
        failures.append("GENESIS_OP_NOT_REGISTRY_V1")
    head_of_op = ledger_head(expected_op)
    owner_head_consistent = head_of_op == expected_head and J.next_head(GENESIS_HEAD, expected_op) == expected_head
    if not owner_head_consistent:
        failures.append("OWNER_HEAD_NOT_THE_HEAD_OF_REGISTRY_V1")

    # M-B8-and-later state.
    later = {path: _lstat(_host(root, path)) is not None for path in LATER_PATHS}
    listings = {path: _listing(root, path) for path in EMPTY_LISTINGS}
    later_absent = not any(later.values()) and all(listings[path] == [] for path in EMPTY_LISTINGS)
    if not later_absent:
        failures.append("LATER_STATE_PRESENT")

    # The state directory and the ledger artifacts.
    state_path = _host(root, STATE_DIR)
    state_meta = _lstat(state_path)
    directory = _facts(state_meta)
    entries = sorted(os.listdir(state_path)) if state_meta is not None and stat.S_ISDIR(state_meta.st_mode) else None
    files = {name: _facts(_lstat(state_path / name)) for name in sorted(STATE_NAMES)} if entries is not None else {}
    directory_exact = (directory.get("kind") == "dir"
                       and (directory["uid"], directory["gid"], directory["mode"]) == (signer_uid, signer_gid, "0700"))
    ledger_file_exact = (files.get(LEDGER_NAME, {}).get("kind") == "file"
                         and (files[LEDGER_NAME]["uid"], files[LEDGER_NAME]["gid"], files[LEDGER_NAME]["mode"])
                         == (signer_uid, signer_gid, "0600"))
    sidecars = [name for name in (WAL_NAME, SHM_NAME) if files.get(name, {}).get("state") == "PRESENT"]
    clean = entries == [LEDGER_NAME]

    image_facts: dict[str, Any] = {"state": "NOT_READ"}
    wal_facts: dict[str, Any] = {"present": False}
    content: dict[str, bool] = {}
    phase = None
    if not later_absent:
        phase = LATER_STATE              # M-B8 or later happened (or began): out of this tool's scope
    elif not trust_exact or not gaps_preserved or not op_matches_registry or not owner_head_consistent:
        phase = UNCLASSIFIED
    elif state_meta is None:
        phase = W6_0
    elif entries is None or directory.get("kind") != "dir":
        phase = UNCLASSIFIED
        failures.append("STATE_PATH_NOT_A_DIRECTORY")
    elif not set(entries) <= STATE_NAMES:
        phase = UNCLASSIFIED
        failures.append("STATE_DIRECTORY_UNEXPECTED_ENTRY")
    elif not entries:
        if directory_exact:
            phase = W6_2
        elif (directory["uid"], directory["gid"]) == (owner_uid, owner_gid) and int(directory["mode"], 8) & 0o077 == 0:
            phase = W6_1                     # mkdir done, chown/chmod not: the root half was interrupted
        else:
            phase = UNCLASSIFIED
            failures.append("STATE_DIRECTORY_UNSAFE")
    elif not directory_exact:
        phase = UNCLASSIFIED
        failures.append("STATE_DIRECTORY_INEXACT_WITH_ENTRIES")
    elif LEDGER_NAME not in entries:
        phase = UNCLASSIFIED
        failures.append("SIDECAR_WITHOUT_LEDGER")
    elif any(files[name].get("kind") != "file" or files[name]["uid"] != signer_uid
             or int(files[name]["mode"], 8) & 0o077 for name in entries):
        phase = UNCLASSIFIED
        failures.append("LEDGER_ARTIFACT_UNSAFE")
    else:
        try:
            db = _read(state_path / LEDGER_NAME)
            wal = _read(state_path / WAL_NAME) if WAL_NAME in entries else None
            image, wal_facts = committed_image(db, wal)
            image_facts = examine_image(image)
        except (Refused, WalError, OSError) as exc:
            phase = UNCLASSIFIED
            failures.append("LEDGER_UNREADABLE:" + (getattr(exc, "reason", None) or str(exc) or type(exc).__name__))
        if phase is None:
            if wal_facts.get("present") and wal_facts["size"] and not wal_facts["headerValid"] \
                    and image_facts["state"] != "EMPTY":
                phase = UNCLASSIFIED      # a torn WAL header over a non-empty database: owner adjudication
                failures.append("WAL_HEADER_INVALID")
            elif image_facts["state"] in ("EMPTY", "NO_SCHEMA"):
                phase = W6_3              # the one M-B6 transaction (schema + GENESIS row) never committed
            elif image_facts["state"] != "COMMITTED":
                phase = UNCLASSIFIED
                failures.append("LEDGER_IMAGE_" + image_facts["state"])
            else:
                content = _content_checks(image_facts, expected_op, expected_head, pins, L, J, R, A, canonical)
                failed = [name for name, ok in content.items() if not ok]
                failures.extend("LEDGER_CONTENT:" + name for name in failed)
                if not ledger_file_exact:
                    failures.append("LEDGER_FILE_INEXACT")
                phase = COMMITTED if not failed and ledger_file_exact else UNCLASSIFIED

    committed = phase == COMMITTED
    evidence = {
        "ledgerSequenceIsOne": committed and content.get("sequenceIsOne", False),
        "ledgerHeadEqualsOwnerComputed": committed and content.get("headEqualsOwnerComputed", False),
        "ledgerSchemaFingerprintVerified": committed and content.get("schemaFingerprintVerified", False),
    }
    return {
        "verifierType": VERIFIER_TYPE, "schemaVersion": 1, "environment": ENVIRONMENT, "phase": phase,
        "evidence": evidence, "ledgerClean": committed and clean, "sidecars": sidecars,
        "expectedLedgerHead": expected_head, "expectedGenesisOp": expected_op,
        "observedLedgerHead": (image_facts.get("journal") or [[None] * 5])[0][4] if committed else None,
        "checks": {"trustRegistryExact": trust_exact, "hostInputReasonsExactlyW5Gaps": gaps_preserved,
                   "genesisOpEqualsRegistryV1": op_matches_registry, "ownerHeadIsHeadOfRegistryV1": owner_head_consistent,
                   "stateDirectoryExact": directory_exact, "ledgerFileExact": ledger_file_exact,
                   "laterStateAbsent": later_absent, **{"content." + k: v for k, v in content.items()}},
        "stateDirectory": directory, "entries": entries, "files": files, "wal": wal_facts, "image": image_facts,
        "laterState": later, "listings": listings, "hostInputReasons": sorted(reasons),
        "ownerRegisterCopyPresent": "AUTHORIZATION_REGISTER_COPY_MISSING" not in reasons,
        "genesisPinCopyPresent": "GENESIS_PIN_COPY_MISSING" not in reasons,
        "witnessGenesisPresent": later["/var/lib/lilith-recovery-witness"],
        "trust": {"phase": trust["phase"], "evidence": trust["evidence"], "registryDigest": trust["registryDigest"]},
        "failures": failures, "registryEffective": False, "authorityActive": False, "authorityGranted": False,
    }


def _content_checks(image: Mapping[str, Any], op: Mapping[str, Any], expected_head: str, pins: LedgerPinsV1,
                    L, J, R, A, canonical) -> dict[str, bool]:
    epoch = A.RecoveryEpochV1(pins.epoch_counter, pins.epoch_random)
    ledger_epoch = R.ledger_epoch_id(epoch, ENVIRONMENT)
    journal, epochs = image.get("journal", []), image.get("epochs", [])
    payload = canonical(dict(op)).decode("utf-8")
    row = journal[0] if len(journal) == 1 else None
    try:
        parsed = json.loads(row[2]) if row else None
    except ValueError:
        parsed = None
    return {
        "integrityOk": image.get("integrity") == ["ok"],
        "walModeHeader": image.get("walModeHeader") == [2, 2],
        "schemaFingerprintVerified": image.get("schemaFingerprint") == pins.schema_fingerprint == L.SCHEMA_FINGERPRINT,
        "metaExact": image.get("meta") == [[1, L.SCHEMA_VERSION, ENVIRONMENT, PROFILE]],
        "sequenceIsOne": row is not None and row[0] == 1 and len(epochs) == 1 and epochs[0][0] == 1,
        "journalOpIsGenesis": row is not None and row[1] == "GENESIS",
        "genesisOpEqualsRegistryV1": row is not None and parsed == dict(op) and row[2] == payload,
        "signingKeyIdsEqualKAct": parsed is not None and parsed.get("signingKeyIds") == [pins.kact_key_id],
        "recoveryEpochPolicyRegistryVersionExact": parsed is not None
        and parsed.get("recoveryEpoch") == {"counter": pins.epoch_counter, "random": pins.epoch_random}
        and parsed.get("policyVersion") == pins.policy_version and parsed.get("registryVersion") == pins.registry_version,
        "previousHeadIsGenesisConstant": row is not None and row[3] == GENESIS_HEAD,
        "headChainValid": row is not None and parsed is not None and J.next_head(row[3], parsed) == row[4],
        "headEqualsOwnerComputed": row is not None and row[4] == expected_head,
        "ledgerEpochExact": row is not None and row[5] == ledger_epoch,
        "epochRowExact": epochs == [[1, pins.epoch_counter, pins.epoch_random, R.epoch_digest(epoch, ENVIRONMENT),
                                     ledger_epoch]],
        "noOtherRows": image.get("otherRows") == {"authority_challenge_v2": 0, "authority_evidence_v2": 0,
                                                  "authority_evidence_use_v1": 0},
    }


# ------------------------------------------------------------- sequence ---

def expected_cli_stdout(expected_head: str, state_directory: str, pins: LedgerPinsV1 = ACCEPTED_PINS) -> bytes:
    """The exact stdout of one successful `provision 1`: the signer half's line, then the root half's."""
    signer = {"authorityGranted": False, "ledgerHead": expected_head, "ledgerSequence": 1}
    root = {"authorityGranted": False, "genesisOp": pinned_genesis_op(pins), "ledgerHead": expected_head,
            "ledgerSequence": 1, "stateDirectory": state_directory}
    return b"".join(json.dumps(v, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
                    for v in (signer, root))


def classify_transcript(returncode: int | None, stdout: bytes, stderr: bytes, *, expected_head: str,
                        state_directory: str, pins: LedgerPinsV1 = ACCEPTED_PINS) -> tuple[str, str | None]:
    """(class, detail) of the one invocation. Only an exact two-line stdout, empty stderr and exit 0 is success."""
    if returncode is None:
        return TRANSPORT_FAILED, "NO_RETURN_CODE"
    out = stdout.replace(b"\r\n", b"\n") if stdout.count(b"\r\n") == stdout.count(b"\n") else stdout
    if returncode == 0:
        if out == expected_cli_stdout(expected_head, state_directory, pins) and stderr == b"":
            return CLI_SUCCESS_EXACT, None
        return CLI_FAILED_UNCLASSIFIED, "EXIT_0_OUTPUT_NOT_EXACT"
    if returncode in (96, 97):
        return GUARD_STOPPED, str(returncode)
    if returncode == 255:
        return TRANSPORT_FAILED, "SSH_255"
    text = stderr.decode("utf-8", "replace").strip()
    prefix = "lilith-authority-ledger-dev: REFUSED "
    if returncode == 2 and text.startswith(prefix) and "\n" not in text:
        return CLI_REFUSED, text[len(prefix):]
    return CLI_FAILED_UNCLASSIFIED, f"EXIT_{returncode}"


def classify_sequence(*, host_phase: str, ledger_clean: bool, attempt_consumed: bool, transcript: str,
                      post_verified: bool) -> str:
    """The W6 sequence phase from the host phase and the operator's own records (pure)."""
    if host_phase not in HOST_PHASES or transcript not in TRANSCRIPT_CLASSES:
        return UNCLASSIFIED
    if host_phase in (LATER_STATE, UNCLASSIFIED):
        return host_phase
    if not attempt_consumed:
        return W6_0 if host_phase == W6_0 and transcript == NOT_INVOKED and not post_verified else UNCLASSIFIED
    if transcript == NOT_INVOKED:
        return UNCLASSIFIED             # a marker is always followed by exactly one recorded invocation
    if host_phase != COMMITTED:
        return host_phase if transcript != CLI_SUCCESS_EXACT and not post_verified else UNCLASSIFIED
    if transcript in (CLI_REFUSED, GUARD_STOPPED):
        return UNCLASSIFIED             # a refusal never leaves a committed ledger behind
    if transcript == CLI_SUCCESS_EXACT and ledger_clean:
        return W6_6 if post_verified else W6_5
    return W6_4 if not post_verified else UNCLASSIFIED


# ------------------------------------------------------------------ entry ---

def require_dev_root(*, euid: Callable[[], int] | None = None, root: Path = Path("/"),
                     hostname: Callable[[], str] = lambda: os.uname().nodename) -> None:
    if (euid or os.geteuid)() != 0:
        raise Refused("NOT_ROOT")
    try:
        machine_id = (root / "etc/machine-id").read_text(encoding="ascii").strip()
    except OSError as exc:
        raise Refused("NOT_DEV_HOST") from exc
    if machine_id != DEV_MACHINE_ID or hostname().split(".", 1)[0] != DEV_HOSTNAME:
        raise Refused("NOT_DEV_HOST")


def main(argv: list[str]) -> int:
    try:
        if len(argv) == 2 and argv[0] == "observe":
            head = argv[1]
        elif len(argv) == 3 and argv[0] == "expect" and argv[1] in HOST_PHASES:
            head = argv[2]
        else:
            raise Refused("USAGE")
        require_dev_root()
        if RELEASE_TREE not in sys.path:
            sys.path.insert(0, RELEASE_TREE)
        report = evaluate(head)
    except Refused as exc:
        print(f"mb6_ledger_verifier: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(report, sort_keys=True, indent=2) + "\n")
    if argv[0] == "expect":
        return 0 if report["phase"] == argv[1] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
