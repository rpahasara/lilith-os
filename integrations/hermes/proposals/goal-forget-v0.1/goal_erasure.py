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
