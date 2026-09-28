"""Durable DEV_SYNTHETIC authority recovery ledger (B1b-3e PR-1S, S-9).

Design: docs/architecture/slice-15b2b-b1b3e-pr1-live-install-preflight.md §14;
B1b-3d design §12. Record: docs/architecture/slice-15b2b-b1b3e-pr1s-runtime-wiring.md.

`/var/lib/lilith-authority-dev/authority_ledger.db`, owned by the authority
signer (sole writer). SQLite, WAL, `synchronous=FULL`, foreign keys, an exact
schema fingerprint, append-only journal triggers, and terminal-row triggers.
The journal is the durable form of the B1b-3c `AuthorityLedgerStateV1`: every
write replays the complete journal plus the new operations through the shared
pure `authority_ledger_journal.replay` (same ops, same head function, same
refusals) and materializes exactly the replayed rows in one transaction.

    ledger provisioned != authority state accepted
    ledger existence   != authority

There is no auto-initialisation. `open_existing` never creates a file: a
missing ledger is `AUTHORITY_STATE_MISSING`. `provision` is the one explicit
provisioning action: it refuses an existing file (or WAL / SHM sidecar),
requires the signer-owned `0700` state directory, creates the file `0600`
exclusively, and writes exactly one `GENESIS` operation (sequence 1).

The public writer accepts only the C-4 recovery operations (`ADVANCE_EPOCH`,
`VOID_CHALLENGE`, `QUARANTINE_USE`). Nothing here can prepare, consume,
issue, reserve, confirm, or abandon: issuance stays unwired (RR-39). The
ledger never touches the broker ledgers or L04.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from lilith_owner_memory import authority_ledger_journal as J
from lilith_owner_memory import recovery_contracts as R
from lilith_owner_memory import rotation_contracts as RC
from lilith_owner_memory.contracts import _canonical

from .profile import LEDGER_PATH, PROFILE

SCHEMA_VERSION = 1
LEDGER_ENVIRONMENTS = frozenset({"dev", "test"})  # never prod; the caller passes its exact expected value

_TERMINAL_CHALLENGE = "('CONSUMED','EXPIRED','CANCELLED','FAILED','VOIDED_BY_RECOVERY')"
_TERMINAL_USE = "('CONSUMED','ABANDONED','QUARANTINED_BY_RECOVERY')"
SCHEMA = (
    "CREATE TABLE authority_meta_v1 (singleton INTEGER PRIMARY KEY CHECK (singleton = 1), "
    "schema_version INTEGER NOT NULL CHECK (schema_version = 1), "
    "environment TEXT NOT NULL CHECK (environment IN ('dev','test')), "
    "profile TEXT NOT NULL CHECK (profile = 'DEV_SYNTHETIC')) STRICT",
    "CREATE TABLE authority_journal_v1 (seq INTEGER PRIMARY KEY CHECK (seq >= 1), "
    "op TEXT NOT NULL CHECK (op IN ('GENESIS','PREPARE','CONSUME','EXPIRE','CANCEL','FAIL','ISSUE','RESERVE',"
    "'CONFIRM','ABANDON','REGISTRY_VIEW','ADVANCE_EPOCH','VOID_CHALLENGE','QUARANTINE_USE')), "
    "payload BLOB NOT NULL, prev_head TEXT NOT NULL CHECK (length(prev_head) = 64), "
    "head TEXT NOT NULL UNIQUE CHECK (length(head) = 64), ledger_epoch TEXT NOT NULL) STRICT",
    "CREATE TRIGGER authority_journal_v1_append_only_update BEFORE UPDATE ON authority_journal_v1 "
    "BEGIN SELECT RAISE(ABORT, 'JOURNAL_APPEND_ONLY'); END",
    "CREATE TRIGGER authority_journal_v1_append_only_delete BEFORE DELETE ON authority_journal_v1 "
    "BEGIN SELECT RAISE(ABORT, 'JOURNAL_APPEND_ONLY'); END",
    "CREATE TRIGGER authority_journal_v1_contiguous BEFORE INSERT ON authority_journal_v1 "
    "WHEN NEW.seq != COALESCE((SELECT MAX(seq) FROM authority_journal_v1), 0) + 1 "
    "OR NEW.prev_head != COALESCE((SELECT head FROM authority_journal_v1 ORDER BY seq DESC LIMIT 1), "
    f"'{R.LEDGER_HEAD_GENESIS}') "
    "BEGIN SELECT RAISE(ABORT, 'JOURNAL_NOT_CONTIGUOUS'); END",
    "CREATE TABLE authority_epoch_v1 (adoption_seq INTEGER PRIMARY KEY REFERENCES authority_journal_v1(seq), "
    "counter INTEGER NOT NULL CHECK (counter >= 0), random TEXT NOT NULL CHECK (length(random) = 32), "
    "epoch_digest TEXT NOT NULL UNIQUE, ledger_epoch TEXT NOT NULL UNIQUE) STRICT",
    "CREATE TRIGGER authority_epoch_v1_immutable BEFORE UPDATE ON authority_epoch_v1 "
    "BEGIN SELECT RAISE(ABORT, 'EPOCH_IMMUTABLE'); END",
    "CREATE TRIGGER authority_epoch_v1_no_delete BEFORE DELETE ON authority_epoch_v1 "
    "BEGIN SELECT RAISE(ABORT, 'EPOCH_IMMUTABLE'); END",
    "CREATE TABLE authority_challenge_v2 (challenge_id TEXT PRIMARY KEY, ledger_epoch TEXT NOT NULL, "
    "state TEXT NOT NULL CHECK (state IN ('PREPARED','CONSUMED','CANCELLED','EXPIRED','FAILED',"
    "'VOIDED_BY_RECOVERY')), evidence_id TEXT) STRICT",
    "CREATE TRIGGER authority_challenge_v2_no_delete BEFORE DELETE ON authority_challenge_v2 "
    "BEGIN SELECT RAISE(ABORT, 'CHALLENGE_NEVER_DELETED'); END",
    "CREATE TRIGGER authority_challenge_v2_terminal BEFORE UPDATE ON authority_challenge_v2 "
    f"WHEN (OLD.state IN {_TERMINAL_CHALLENGE} AND NEW.state != OLD.state) "
    "OR NEW.ledger_epoch != OLD.ledger_epoch OR NEW.challenge_id != OLD.challenge_id "
    "OR (OLD.evidence_id IS NOT NULL AND NEW.evidence_id IS NOT OLD.evidence_id) "
    "OR (NEW.evidence_id IS NOT NULL AND NEW.state != 'CONSUMED') "
    "BEGIN SELECT RAISE(ABORT, 'TERMINAL_CHALLENGE_NEVER_REOPENS'); END",
    "CREATE TABLE authority_evidence_v2 (evidence_id TEXT PRIMARY KEY, "
    "challenge_id TEXT NOT NULL UNIQUE REFERENCES authority_challenge_v2(challenge_id), "
    "evidence_digest TEXT NOT NULL UNIQUE CHECK (length(evidence_digest) = 64), recovery_epoch BLOB NOT NULL) STRICT",
    "CREATE TRIGGER authority_evidence_v2_immutable BEFORE UPDATE ON authority_evidence_v2 "
    "BEGIN SELECT RAISE(ABORT, 'EVIDENCE_IMMUTABLE'); END",
    "CREATE TRIGGER authority_evidence_v2_no_delete BEFORE DELETE ON authority_evidence_v2 "
    "BEGIN SELECT RAISE(ABORT, 'EVIDENCE_IMMUTABLE'); END",
    "CREATE TABLE authority_evidence_use_v1 (evidence_id TEXT PRIMARY KEY "
    "REFERENCES authority_evidence_v2(evidence_id), evidence_digest TEXT NOT NULL, recovery_epoch BLOB NOT NULL, "
    "proposal_ref_id TEXT NOT NULL, state TEXT NOT NULL CHECK (state IN ('RESERVED','CONSUMED','ABANDONED',"
    "'QUARANTINED_BY_RECOVERY')), admission_id TEXT, revision_id TEXT, reconciliation_outcome TEXT "
    "CHECK (reconciliation_outcome IS NULL OR reconciliation_outcome IN ('ABANDON',"
    "'REQUIRE_OWNER_REAUTHORIZATION'))) STRICT",
    "CREATE TRIGGER authority_evidence_use_v1_no_delete BEFORE DELETE ON authority_evidence_use_v1 "
    "BEGIN SELECT RAISE(ABORT, 'USE_NEVER_DELETED'); END",
    "CREATE TRIGGER authority_evidence_use_v1_terminal BEFORE UPDATE ON authority_evidence_use_v1 "
    f"WHEN (OLD.state IN {_TERMINAL_USE} AND (NEW.state != OLD.state OR NEW.admission_id IS NOT OLD.admission_id "
    "OR NEW.revision_id IS NOT OLD.revision_id)) OR NEW.evidence_digest != OLD.evidence_digest "
    "OR NEW.recovery_epoch != OLD.recovery_epoch OR NEW.proposal_ref_id != OLD.proposal_ref_id "
    "BEGIN SELECT RAISE(ABORT, 'TERMINAL_USE_NEVER_REOPENS'); END",
)


def schema_fingerprint_of(statements: Sequence[str]) -> str:
    return hashlib.sha256("\n".join(sorted(statements)).encode("utf-8")).hexdigest()


SCHEMA_FINGERPRINT = schema_fingerprint_of(SCHEMA)

LEDGER_ERROR_REASONS = (
    "AUTHORITY_STATE_MISSING",
    "LEDGER_PATH_UNSAFE",
    "LEDGER_ALREADY_EXISTS",
    "LEDGER_ENVIRONMENT_INVALID",
    "LEDGER_GENESIS_INVALID",
    "LEDGER_SCHEMA_MISMATCH",
    "LEDGER_META_MISMATCH",
    "LEDGER_JOURNAL_INVALID",
    "LEDGER_HEAD_STALE",
    "LEDGER_OPERATION_NOT_PERMITTED",
    "LEDGER_REFUSED",
    "LEDGER_IO_ERROR",
)


class LedgerError(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        assert reason in LEDGER_ERROR_REASONS, reason
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _connect(path: Path) -> sqlite3.Connection:
    # `mode=rw` never creates a file: absence stays absence.
    conn = sqlite3.connect(f"file:{path}?mode=rw", uri=True, isolation_level=None, timeout=5.0)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA trusted_schema = OFF")
    conn.execute("PRAGMA synchronous = FULL")
    return conn


def _schema_statements(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'")
    return [row[0] for row in rows]


def _journal(conn: sqlite3.Connection) -> tuple[dict[str, Any], ...]:
    log = []
    previous = R.LEDGER_HEAD_GENESIS
    for seq, op, payload, prev_head, head in conn.execute(
            "SELECT seq, op, payload, prev_head, head FROM authority_journal_v1 ORDER BY seq"):
        value = json.loads(bytes(payload).decode("utf-8"))
        if (not isinstance(value, dict) or value.get("op") != op or _canonical(value) != bytes(payload)
                or seq != len(log) + 1 or prev_head != previous or J.next_head(prev_head, value) != head):
            raise LedgerError("LEDGER_JOURNAL_INVALID", str(seq))
        log.append(value)
        previous = head
    return tuple(log)


def _rows(conn: sqlite3.Connection) -> dict[str, Any]:
    challenges = {cid: {"ledgerEpoch": epoch, "state": state, "evidenceId": evidence}
                  for cid, epoch, state, evidence in conn.execute(
                      "SELECT challenge_id, ledger_epoch, state, evidence_id FROM authority_challenge_v2")}
    uses = {eid: {"evidenceDigest": digest, "recoveryEpoch": json.loads(bytes(epoch).decode("utf-8")),
                  "proposalRefId": proposal, "state": state, "admissionId": admission, "revisionId": revision}
            for eid, digest, epoch, proposal, state, admission, revision in conn.execute(
                "SELECT evidence_id, evidence_digest, recovery_epoch, proposal_ref_id, state, admission_id, "
                "revision_id FROM authority_evidence_use_v1")}
    return {"challenges": challenges, "uses": uses}


def _write_ops(conn: sqlite3.Connection, log: tuple[Mapping[str, Any], ...],
               ops: Sequence[Mapping[str, Any]]) -> J.JournalReplay:
    """Journal `ops` after `log` and materialize the replayed rows.

    Module-private. Callers hold an IMMEDIATE transaction. Every op is
    replayed through the shared pure journal first; a refused op writes
    nothing (the caller rolls back).
    """
    before = J.replay(tuple(log)) if log else J.JournalReplay()
    after = J.replay(tuple(log) + tuple(ops))
    replayed = J.JournalReplay()
    head = R.LEDGER_HEAD_GENESIS
    for op in tuple(log) + tuple(ops):
        J.step(replayed, op)
        if replayed.sequence > before.sequence:
            payload = _canonical(op)
            conn.execute("INSERT INTO authority_journal_v1 (seq, op, payload, prev_head, head, ledger_epoch) "
                         "VALUES (?, ?, ?, ?, ?, ?)",
                         (replayed.sequence, op["op"], payload, head, replayed.head, replayed.ledger_epoch))
            if op["op"] in (J.GENESIS, J.ADVANCE_EPOCH):
                conn.execute("INSERT INTO authority_epoch_v1 (adoption_seq, counter, random, epoch_digest, "
                             "ledger_epoch) VALUES (?, ?, ?, ?, ?)",
                             (replayed.sequence, replayed.epoch.counter, replayed.epoch.random,
                              R.epoch_digest(replayed.epoch, replayed.environment), replayed.ledger_epoch))
        head = replayed.head
    _materialize(conn, after)
    return after


def _materialize(conn: sqlite3.Connection, state: J.JournalReplay) -> None:
    for cid, entry in sorted(state.challenges.items()):
        conn.execute("INSERT INTO authority_challenge_v2 (challenge_id, ledger_epoch, state, evidence_id) "
                     "VALUES (?, ?, ?, ?) ON CONFLICT(challenge_id) DO UPDATE SET state = excluded.state, "
                     "evidence_id = excluded.evidence_id WHERE authority_challenge_v2.state IS NOT excluded.state "
                     "OR authority_challenge_v2.evidence_id IS NOT excluded.evidence_id",
                     (cid, entry["ledgerEpoch"], entry["state"], entry["evidenceId"]))
    for eid, issued in sorted(state.issued.items()):
        conn.execute("INSERT OR IGNORE INTO authority_evidence_v2 (evidence_id, challenge_id, evidence_digest, "
                     "recovery_epoch) VALUES (?, ?, ?, ?)",
                     (eid, issued["challengeId"], issued["evidenceDigest"], _canonical(issued["recoveryEpoch"])))
    for eid, entry in sorted(state.uses.items()):
        conn.execute("INSERT INTO authority_evidence_use_v1 (evidence_id, evidence_digest, recovery_epoch, "
                     "proposal_ref_id, state, admission_id, revision_id) VALUES (?, ?, ?, ?, ?, ?, ?) "
                     "ON CONFLICT(evidence_id) DO UPDATE SET state = excluded.state, "
                     "admission_id = excluded.admission_id, revision_id = excluded.revision_id "
                     "WHERE authority_evidence_use_v1.state IS NOT excluded.state",
                     (eid, entry["evidenceDigest"], _canonical(entry["recoveryEpoch"]), entry["proposalRefId"],
                      entry["state"], entry["admissionId"], entry["revisionId"]))


def _check_file(path: Path, *, expected_uid: int) -> None:
    try:
        meta = os.lstat(path)
    except FileNotFoundError as exc:
        raise LedgerError("AUTHORITY_STATE_MISSING") from exc
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid != expected_uid or stat.S_IMODE(meta.st_mode) & 0o077:
        raise LedgerError("LEDGER_PATH_UNSAFE", "file")


def _check_directory(directory: Path, *, expected_uid: int) -> None:
    try:
        meta = os.lstat(directory)
    except FileNotFoundError as exc:
        raise LedgerError("LEDGER_PATH_UNSAFE", "state directory absent") from exc
    if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != expected_uid or stat.S_IMODE(meta.st_mode) != 0o700:
        raise LedgerError("LEDGER_PATH_UNSAFE", "state directory")


class DurableAuthorityLedgerV1:
    """The signer-owned recovery ledger. One process writes it (the signer)."""

    def __init__(self, conn: sqlite3.Connection, path: Path, environment: str):
        self._conn = conn
        self.path = path
        self.environment = environment

    def __reduce__(self):
        raise TypeError("the authority ledger is not serializable")

    # ---------------------------------------------------------- open / create ---

    @classmethod
    def open_existing(cls, path: Path | str = LEDGER_PATH, *, environment: str,
                      expected_uid: int | None = None) -> DurableAuthorityLedgerV1:
        """Open an existing ledger. Never creates one (`AUTHORITY_STATE_MISSING`)."""
        if environment not in LEDGER_ENVIRONMENTS:
            raise LedgerError("LEDGER_ENVIRONMENT_INVALID")
        path = Path(path)
        _check_file(path, expected_uid=os.getuid() if expected_uid is None else expected_uid)
        try:
            conn = _connect(path)
        except sqlite3.Error as exc:
            raise LedgerError("LEDGER_IO_ERROR") from exc
        ledger = cls(conn, path, environment)
        try:
            ledger._verify_schema()
        except BaseException:
            conn.close()
            raise
        return ledger

    @classmethod
    def provision(cls, path: Path | str = LEDGER_PATH, *, environment: str, genesis: Mapping[str, Any],
                  expected_uid: int | None = None) -> RC.AuthorityLedgerObservationV1:
        """The one explicit provisioning action (M-B6). Refuses any existing state.

        `genesis` is the GENESIS op (`authority_ledger_journal.genesis_op` of
        the verified registry v1). The result is the sequence-1 position.
        """
        if environment not in LEDGER_ENVIRONMENTS:
            raise LedgerError("LEDGER_ENVIRONMENT_INVALID")
        path = Path(path)
        uid = os.getuid() if expected_uid is None else expected_uid
        _check_directory(path.parent, expected_uid=uid)
        for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm"), Path(f"{path}-journal")):
            if os.path.lexists(candidate):
                raise LedgerError("LEDGER_ALREADY_EXISTS", candidate.name)
        try:
            J.replay((dict(genesis),))
        except J.LedgerRefusal as exc:
            raise LedgerError("LEDGER_GENESIS_INVALID", exc.reason) from exc
        if genesis.get("op") != J.GENESIS or genesis.get("environment") != environment:
            raise LedgerError("LEDGER_GENESIS_INVALID")
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        except FileExistsError as exc:
            raise LedgerError("LEDGER_ALREADY_EXISTS") from exc
        os.close(fd)
        try:
            conn = _connect(path)
            try:
                if conn.execute("PRAGMA journal_mode = WAL").fetchone()[0].lower() != "wal":
                    raise LedgerError("LEDGER_IO_ERROR", "WAL")
                conn.execute("BEGIN IMMEDIATE")
                for statement in SCHEMA:
                    conn.execute(statement)
                conn.execute("INSERT INTO authority_meta_v1 (singleton, schema_version, environment, profile) "
                             "VALUES (1, ?, ?, ?)", (SCHEMA_VERSION, environment, PROFILE))
                _write_ops(conn, (), (dict(genesis),))
                conn.execute("COMMIT")
            finally:
                conn.close()
        except (sqlite3.Error, J.LedgerRefusal) as exc:
            raise LedgerError("LEDGER_IO_ERROR", type(exc).__name__) from exc
        _fsync_directory(path.parent)
        ledger = cls.open_existing(path, environment=environment, expected_uid=uid)
        try:
            return ledger.observe()
        finally:
            ledger.close()

    def _verify_schema(self) -> None:
        try:
            if schema_fingerprint_of(_schema_statements(self._conn)) != SCHEMA_FINGERPRINT:
                raise LedgerError("LEDGER_SCHEMA_MISMATCH")
            meta = self._conn.execute("SELECT schema_version, environment, profile FROM authority_meta_v1").fetchall()
            if meta != [(SCHEMA_VERSION, self.environment, PROFILE)]:
                raise LedgerError("LEDGER_META_MISMATCH")
            if self._conn.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
                raise LedgerError("LEDGER_SCHEMA_MISMATCH", "journal_mode")
        except sqlite3.Error as exc:
            raise LedgerError("LEDGER_SCHEMA_MISMATCH") from exc

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------- reading ---

    def journal(self) -> tuple[dict[str, Any], ...]:
        return _journal(self._conn)

    def observe(self) -> RC.AuthorityLedgerObservationV1:
        """Story 4: replay the journal and report its position (never repairs)."""
        try:
            log = _journal(self._conn)
            replayed = J.replay(log)
            rows = _rows(self._conn)
        except J.LedgerRefusal as exc:
            raise LedgerError("LEDGER_JOURNAL_INVALID", exc.reason) from exc
        except sqlite3.Error as exc:
            raise LedgerError("LEDGER_IO_ERROR") from exc
        if replayed.environment != self.environment:
            raise LedgerError("LEDGER_META_MISMATCH", "journal environment")
        return J.observation(replayed, rows=rows)

    def replay(self) -> J.JournalReplay:
        return J.replay(_journal(self._conn))

    # ------------------------------------------------------------- writing ---

    def append_recovery(self, ops: Sequence[Mapping[str, Any]], *, expected_sequence: int,
                        expected_head: str) -> RC.AuthorityLedgerObservationV1:
        """Journal destroy/narrow-only recovery ops in ONE transaction (C-4).

        The caller names the exact position it evaluated; a ledger that moved
        (`LEDGER_HEAD_STALE`) writes nothing. CONSUMED / terminal rows never
        reopen: the replay refuses, and the triggers refuse again.
        """
        ops = [dict(op) for op in ops]
        if not ops or any(op.get("op") not in J.RECOVERY_OPERATIONS for op in ops):
            raise LedgerError("LEDGER_OPERATION_NOT_PERMITTED")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                log = _journal(self._conn)
                current = J.replay(log)
                if (current.sequence, current.head) != (expected_sequence, expected_head):
                    raise LedgerError("LEDGER_HEAD_STALE")
                if _rows(self._conn) != current.rows():
                    raise LedgerError("LEDGER_JOURNAL_INVALID", "rows differ from journal")
                try:
                    _write_ops(self._conn, log, ops)
                except J.LedgerRefusal as exc:
                    raise LedgerError("LEDGER_REFUSED", exc.reason) from exc
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
        except sqlite3.Error as exc:
            raise LedgerError("LEDGER_IO_ERROR", type(exc).__name__) from exc
        return self.observe()


def _fsync_directory(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _on_copy(path: Path | str, *, environment: str, read):
    """Root forensic read (service stopped): copy the DB and its WAL to a
    private temporary directory and read the copy. The live file is never
    opened for writing and never opened in place."""
    path = Path(path)
    if not os.path.lexists(path):
        raise LedgerError("AUTHORITY_STATE_MISSING")
    with tempfile.TemporaryDirectory(prefix="lilith-ledger-observe.") as scratch:
        os.chmod(scratch, 0o700)
        target = Path(scratch) / path.name
        for suffix in ("", "-wal"):
            source = Path(f"{path}{suffix}")
            if not os.path.lexists(source):
                continue
            meta = os.lstat(source)
            if not stat.S_ISREG(meta.st_mode):
                raise LedgerError("LEDGER_PATH_UNSAFE", source.name)
            fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            out = os.open(f"{target}{suffix}", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                          0o600)
            with os.fdopen(fd, "rb") as reader, os.fdopen(out, "wb") as writer:
                shutil.copyfileobj(reader, writer)
        ledger = DurableAuthorityLedgerV1.open_existing(target, environment=environment,
                                                        expected_uid=os.getuid())
        try:
            return read(ledger)
        finally:
            ledger.close()


def observe_copy(path: Path | str, *, environment: str) -> RC.AuthorityLedgerObservationV1:
    return _on_copy(path, environment=environment, read=lambda ledger: ledger.observe())


def journal_copy(path: Path | str, *, environment: str) -> tuple[dict[str, Any], ...]:
    return _on_copy(path, environment=environment, read=lambda ledger: ledger.journal())
