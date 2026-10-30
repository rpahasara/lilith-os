"""Candidate FORGET and retention step for Core API goal rows (NOT WIRED, nothing calls this).

Pure stdlib. Fail-closed: an unexpected table or a held lock refuses before any change. Implements section 2 of
proposals/goals-privacy-v0.2/PLAN.md, pending owner decision P-2.
"""

import sqlite3
from datetime import datetime, timedelta, timezone

ALLOWED_TABLES = {"goal", "goal_trace", "sqlite_sequence", "tasks", "drafts", "world_belief", "world_belief_conflict", "world_belief_evidence",
                  "world_belief_trace", "world_ingest_cursor", "world_working_seed"}
TERMINAL = ("COMPLETED", "CANCELLED", "FAILED")


class Refused(Exception):
    pass


def _open(db):
    conn = sqlite3.connect(db, timeout=0, isolation_level=None)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if tables - ALLOWED_TABLES or not {"goal", "goal_trace"} <= tables:
        conn.close()
        raise Refused("unexpected_schema")
    conn.execute("PRAGMA secure_delete=ON")
    return conn


def _finish(conn):
    conn.execute("COMMIT")
    conn.execute("VACUUM")                 # freed pages can otherwise keep text; this file is not in WAL mode


def erase_all_goals(db):
    """Principal FORGET: every goal, every trace, and the counter that reveals past activity. Idempotent."""
    conn = _open(db)
    try:
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError:
            raise Refused("locked")
        conn.execute("DELETE FROM goal_trace")
        conn.execute("DELETE FROM goal")
        conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('goal', 'goal_trace')")
        if conn.execute("SELECT (SELECT COUNT(*) FROM goal) + (SELECT COUNT(*) FROM goal_trace)").fetchone()[0]:
            conn.execute("ROLLBACK")
            raise Refused("not_empty")
        _finish(conn)
    finally:
        conn.close()


def prune_terminal_goals(db, days=30, now=None):
    """Daily retention: terminal goals older than `days`, with their traces. Active, blocked and suspended goals never age out."""
    cutoff = ((now or datetime.now(timezone.utc)) - timedelta(days=days)).isoformat()
    conn = _open(db)
    try:
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError:
            raise Refused("locked")
        marks = ",".join("?" * len(TERMINAL))
        ids = [r[0] for r in conn.execute(f"SELECT goal_id FROM goal WHERE lifecycle_state IN ({marks}) AND updated_at < ?", (*TERMINAL, cutoff))]
        for goal_id in ids:
            conn.execute("DELETE FROM goal_trace WHERE goal_id=?", (goal_id,))
            conn.execute("DELETE FROM goal WHERE goal_id=?", (goal_id,))
        _finish(conn)
        return len(ids)
    finally:
        conn.close()


def goal_rows_zero(db):
    """The check the FORGET executor would add: read-only, and an absent goal table counts as zero only if the table was never made."""
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return all(conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] == 0 for t in tables & {"goal", "goal_trace"})
    finally:
        conn.close()


def forget_goals_unless_held(db, hold_active):
    """A FORGET hold blocks both erasure and retention. Returns 'held', with nothing changed, or 'erased' after an independent check."""
    if hold_active:
        return "held"
    erase_all_goals(db)
    if not goal_rows_zero(db):
        raise Refused("rows_remain")
    return "erased"


def backup_restore_allowed(backup_db):
    """Restore gate: a backup holding goal rows could resurrect erased data, so it is refused until listed in an erasure ledger."""
    return goal_rows_zero(backup_db)


def channel_label(source_channel):
    """Provenance: keep the channel name, drop the session key after it. `lilith_os:chat-123` becomes `lilith_os`."""
    name = str(source_channel or "").split(":", 1)[0].strip().lower()
    return name if name.replace("_", "").isalnum() else "unknown"
