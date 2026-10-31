"""Candidate principal FORGET for the whole Core API database (NOT WIRED, nothing calls this).

Builds on goal_erasure.py. Pure stdlib. Fail-closed. What it adds:

- One transaction across goals, tasks, drafts and the World Model, so a failure can't leave half an erasure.
- An erasure ledger outside the database, because the database is what a restore brings back. It holds keyed hashes and counts, never content.
- A restore gate: a backup is replayed through the ledger on a quarantine copy, or it is refused.

Ledger lines, one JSON object each: {"erasure_id", "state": "PENDING"|"COMPLETE"|"ABORTED", "at", "through_event_id", "tombstones": [hex], "counts": {...}}. A replay's COMPLETE adds "replay": true.
Tombstone: HMAC-SHA256 of "<entity_type>|<entity_id>" under a key held apart from the ledger, because application ids are small numbers a plain hash would give away.
"""

import hashlib
import hmac
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

from goal_erasure import ALLOWED_TABLES, WORLD_TABLES, Refused

OWNER_TABLES = ("goal_trace", "goal", "tasks", "drafts") + WORLD_TABLES
# Sources of what the World Model derives. Erased only when the owner decides so: decision 1 in PROD-DATA-MIGRATION.md.
SOURCE_TABLES = ("career_events", "job_applications", "companies")


def tombstone(entity_type, entity_id, key):
    return hmac.new(key, ("%s|%s" % (entity_type, entity_id)).encode("utf-8"), hashlib.sha256).hexdigest()


class Ledger:
    def __init__(self, path):
        self.path = Path(path)

    def append(self, entry):
        """One line, flushed to disk before the caller goes on. The file is created 0600 and is never rewritten."""
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, (json.dumps(entry, sort_keys=True) + "\n").encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)

    def entries(self):
        """Every entry. A ledger that can't be read in full raises Refused: an unreadable ledger must never read as 'nothing erased'."""
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
            return [json.loads(line) for line in lines if line]
        except FileNotFoundError:
            return []
        except (OSError, ValueError):
            raise Refused("ledger_unreadable")

    def complete(self):
        return [e for e in self.entries() if e.get("state") == "COMPLETE"]

    def boundary(self):
        """When the latest real erasure finished. A replay re-applies an old erasure to an old copy, so it must not move this: a newer backup would look older than it is."""
        return max((e["at"] for e in self.complete() if not e.get("replay")), default=None)

    def unfinished(self):
        entries = self.entries()
        done = {e.get("erasure_id") for e in entries if e.get("state") in ("COMPLETE", "ABORTED")}
        return sorted({e.get("erasure_id") for e in entries if e.get("state") == "PENDING"} - done)


def _tables(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _open(db, allow):
    conn = sqlite3.connect(db, timeout=0, isolation_level=None)
    tables = _tables(conn)
    if tables - ALLOWED_TABLES - set(allow) or not {"goal", "goal_trace"} <= tables:
        conn.close()
        raise Refused("unexpected_schema")
    conn.execute("PRAGMA secure_delete=ON")
    return conn


def _tombstones(conn, tables, key):
    """What must not come back: every entity the World Model or a draft refers to. Read before the rows go."""
    found = set()
    if "world_belief" in tables:
        found |= {(a, b) for a, b in conn.execute("SELECT entity_type, entity_id FROM world_belief")}
    if "drafts" in tables:
        found |= {("career.application", t) for (t,) in conn.execute("SELECT target_id FROM drafts WHERE target_type='career.application'")}
    if "job_applications" in tables:
        found |= {("career.application", i) for (i,) in conn.execute("SELECT id FROM job_applications")}
    return sorted(tombstone(a, b, key) for a, b in found)


def _through(conn, tables):
    if "career_events" not in tables:
        return 0
    return conn.execute("SELECT COALESCE(MAX(id), 0) FROM career_events").fetchone()[0]


def _delete(conn, tables, source_too):
    counts = {}
    for table in OWNER_TABLES + (SOURCE_TABLES if source_too else ()):
        if table in tables:
            counts[table] = conn.execute(f'DELETE FROM "{table}"').rowcount
    if "sqlite_sequence" in tables:
        conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('goal', 'goal_trace') OR name LIKE 'world_%'")
    return counts


def rows_left(db):
    """The independent check: a read-only count of every owner store."""
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        tables = _tables(conn)
        return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in OWNER_TABLES if t in tables}
    finally:
        conn.close()


def _hold(hold_path):
    try:
        return hold_path.exists()
    except OSError:
        return True


def _open_erasure(ledger):
    """An erasure that never reached COMPLETE: its ids, tombstones and event floor. A crash after the commit leaves its rows gone, so only the ledger still knows them."""
    ids = ledger.unfinished()
    lines = [e for e in ledger.entries() if e.get("erasure_id") in ids]
    return ids, {t for e in lines for t in e.get("tombstones", [])}, max((e.get("through_event_id", 0) for e in lines), default=0)


def erase_principal(db, ledger, key, hold_path, source_too=False, allow=(), replay=False):
    """Everything in one transaction, or nothing. Ledger PENDING goes to disk before any row does, so a crash leaves a trace, and a re-run finishes that same erasure."""
    if _hold(hold_path):
        return {"result": "held"}
    if len(key) < 32:
        raise Refused("weak_key")
    conn = _open(db, allow)
    resumed, old_marks, old_through = _open_erasure(ledger)
    eid = resumed[0] if resumed else "er." + uuid.uuid4().hex
    try:
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError:
            raise Refused("locked")
        tables = _tables(conn)
        marks, through = sorted(set(_tombstones(conn, tables, key)) | old_marks), max(_through(conn, tables), old_through)
        if not resumed:
            ledger.append({"erasure_id": eid, "state": "PENDING", "at": time.time(), "through_event_id": through, "tombstones": marks, "counts": {}})
        try:
            counts = _delete(conn, tables, source_too)
            if any(conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in OWNER_TABLES if t in tables):
                raise Refused("not_empty")
        except Exception:
            conn.execute("ROLLBACK")
            if not resumed:     # a resumed erasure stays open: its first run may already have committed, and its tombstones must survive
                ledger.append({"erasure_id": eid, "state": "ABORTED", "at": time.time(), "through_event_id": through, "tombstones": [], "counts": {}})
            raise
        conn.execute("COMMIT")
        conn.execute("VACUUM")
    finally:
        conn.close()
    left = rows_left(db)
    if any(left.values()):
        raise Refused("rows_remain")
    done = {"state": "COMPLETE", "at": time.time(), "through_event_id": through, "tombstones": marks, "counts": counts}
    if replay:
        done["replay"] = True
    for finished in resumed or [eid]:
        ledger.append({"erasure_id": finished, **done})
    return {"result": "erased", "erasure_id": eid, "counts": counts, "rows_left": left}


def restore_decision(backup_db, ledger, taken_at):
    """CLEAN: nothing to remove. REPLAY: usable only after replay_after_restore. REFUSE: the ledger can't be trusted, or a copy holding rows has no known age.

    The age matters: rows in a backup taken after the latest erasure are newer data, not erased data."""
    try:
        latest = ledger.boundary()
        if ledger.unfinished():
            return "REFUSE"
    except Refused:
        return "REFUSE"
    if latest is None or not any(rows_left(backup_db).values()):
        return "CLEAN"
    if taken_at is None:
        return "REFUSE"
    return "CLEAN" if taken_at > latest else "REPLAY"


def replay_after_restore(quarantine_db, live_db, ledger, key, hold_path, taken_at, source_too=False, allow=()):
    """Runs on a quarantine copy, never on the live file. The copy goes live only after this returns with zero rows, or reports it clean."""
    if Path(quarantine_db).resolve() == Path(live_db).resolve():
        raise Refused("not_a_quarantine_copy")
    decision = restore_decision(quarantine_db, ledger, taken_at)
    if decision == "REFUSE":
        raise Refused("ledger_refused")
    if decision == "CLEAN":
        return {"result": "clean"}
    return erase_principal(quarantine_db, ledger, key, hold_path, source_too=source_too, allow=allow, replay=True)


def snapshot_report(snapshots, ledger):
    """Names each snapshot taken before the latest erasure. It only reports: deleting a snapshot is an owner decision, and this code deletes nothing."""
    latest = ledger.boundary()
    return {name: ("PREDATES_ERASURE" if latest is not None and taken < latest else "AFTER_ERASURE") for name, taken in snapshots.items()}


def text_gone(db, canaries):
    """Bytes on disk, not rows: secure_delete and VACUUM must take the text out of the file too."""
    data = Path(db).read_bytes()
    return not any(c.encode("utf-8") in data for c in canaries)
