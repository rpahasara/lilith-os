# -*- coding: utf-8 -*-
"""Slice 8 — Goal / Executive System V1 backend tests.

Runs against a THROWAWAY temp DB (never lilith.db). Deterministic. Exercises the
internal controlled functions and the route handlers directly (no network). Maps
to the design-doc test list A-U plus de-dup and idempotency/revision cases.

Run on the VM:
  sudo -n -u lilith .../api-venv/bin/python -m pytest -q tests/test_goal_executive.py
  (or: python -m unittest -v tests.test_goal_executive)
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # api/ dir
import app  # noqa: E402
from fastapi import HTTPException  # noqa: E402


def _fresh_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    app.DB = Path(path)
    app._goal_schema_ready = False
    app._world_schema_ready = False
    # touch the DB + goal schema
    c = app._goals_db(); c.close()
    return path


def _seed_task(task_id="t1"):
    c = app._tasks_db()
    try:
        c.execute(
            "INSERT OR IGNORE INTO tasks (task_id, schema_version, revision, source,"
            " kind, status, title, created_at, updated_at, ended_at,"
            " last_operation_id, record_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (task_id, 1, 1, "core", "career", "succeeded", "seed task",
             1, 2, None, None, json.dumps({"taskId": task_id, "status": "succeeded",
                                            "createdAt": 1, "updatedAt": 2})))
        c.commit()
    finally:
        c.close()


def _seed_draft(draft_id, app_id, status="created"):
    c = app._drafts_db()
    try:
        c.execute(
            "INSERT OR IGNORE INTO drafts (draft_id, schema_version, kind, status,"
            " target_type, target_id, subject, body, content_hash, idempotency_key,"
            " task_id, step_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (draft_id, 1, "career_followup", status, "application", str(app_id),
             "s", "b", "h", "idem." + draft_id, None, "s3", 1, 2))
        c.commit()
    finally:
        c.close()


def _seed_belief(entity_id, predicate, value, lifecycle="ACTIVE"):
    c = app.db()
    try:
        app._ensure_world_schema(c)
        now = app._wm_now() if hasattr(app, "_wm_now") else "2026-01-01T00:00:00+00:00"
        c.execute(
            "INSERT OR REPLACE INTO world_belief (key, entity_type, entity_id,"
            " predicate, value_json, lifecycle_state, epistemic_state, confidence,"
            " confidence_tier, confidence_basis, observed_at, created_at, updated_at,"
            " expires_at, revision) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
            ("career.application:%s:%s" % (entity_id, predicate), "career.application",
             str(entity_id), predicate, json.dumps(value), lifecycle, "OBSERVED",
             0.8, "high", "observed", now, now, now, None))
        c.commit()
    finally:
        c.close()


def _mk(payload):
    conn = app._goals_db()
    try:
        g, created = app._create_goal_impl(conn, payload)
        return g, created
    finally:
        conn.close()


def _trans(goal_id, payload):
    conn = app._goals_db()
    try:
        return app._transition_goal_impl(conn, goal_id, payload)
    finally:
        conn.close()


class GoalExecutiveTests(unittest.TestCase):
    def setUp(self):
        self.path = _fresh_db()

    def tearDown(self):
        try:
            os.unlink(self.path)
        except OSError:
            pass

    # A — durable create
    def test_A_durable_create(self):
        g, created = _mk({"type": "career.followup", "title": "Follow up 14",
                          "source": "USER_REQUESTED", "owner": "user",
                          "target": {"type": "career.application", "id": "14"}})
        self.assertTrue(created)
        self.assertEqual(g["lifecycleState"], "PENDING")
        got = app.get_goal(g["goalId"])["goal"]
        self.assertEqual(got["goalId"], g["goalId"])

    # B / S — survives reopen (new connection == service restart durability)
    def test_B_survives_reopen(self):
        g, _ = _mk({"type": "x", "title": "t", "source": "SYSTEM_MAINTENANCE",
                    "owner": "system"})
        # brand new connection to the same file
        c2 = sqlite3.connect(self.path)
        c2.row_factory = sqlite3.Row
        row = c2.execute("SELECT * FROM goal WHERE goal_id=?", (g["goalId"],)).fetchone()
        c2.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["title"], "t")

    # C — valid transitions
    def test_C_valid_transitions(self):
        g, _ = _mk({"type": "x", "title": "t", "source": "TASK_DERIVED", "owner": "system"})
        gid = g["goalId"]
        self.assertEqual(_trans(gid, {"action": "activate"})[0]["lifecycleState"], "ACTIVE")
        self.assertEqual(_trans(gid, {"action": "suspend"})[0]["lifecycleState"], "SUSPENDED")
        self.assertEqual(_trans(gid, {"action": "resume"})[0]["lifecycleState"], "ACTIVE")
        self.assertEqual(_trans(gid, {"action": "complete"})[0]["lifecycleState"], "COMPLETED")

    # D — invalid transition rejected (409 illegal_transition)
    def test_D_invalid_transition(self):
        g, _ = _mk({"type": "x", "title": "t", "source": "TASK_DERIVED", "owner": "system"})
        with self.assertRaises(HTTPException) as ctx:
            _trans(g["goalId"], {"action": "complete"})  # PENDING -> COMPLETED illegal
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail["error"], "illegal_transition")

    # E — parent/subgoal
    def test_E_parent_subgoal(self):
        p, _ = _mk({"type": "epic", "title": "parent", "source": "USER_REQUESTED",
                    "owner": "user"})
        c, _ = _mk({"type": "task", "title": "child", "source": "USER_REQUESTED",
                    "owner": "user", "parentGoalId": p["goalId"]})
        self.assertEqual(c["parentGoalId"], p["goalId"])

    # F — task can link to goal ; G — tasks table unchanged
    def test_F_G_task_link_and_tasks_untouched(self):
        _seed_task("t1")
        before = app._tasks_db()
        n_before = before.execute("SELECT COUNT(*) c FROM tasks").fetchone()["c"]
        before.close()
        g, _ = _mk({"type": "x", "title": "t", "source": "USER_REQUESTED", "owner": "user"})
        res = app.post_goal_link_task(g["goalId"], {"taskId": "t1", "operationId": "op1"})
        self.assertIn("t1", res["goal"]["linkedTaskIds"])
        after = app._tasks_db()
        n_after = after.execute("SELECT COUNT(*) c FROM tasks").fetchone()["c"]
        trow = after.execute("SELECT status FROM tasks WHERE task_id='t1'").fetchone()
        after.close()
        self.assertEqual(n_before, n_after)          # G: no task rows added/removed
        self.assertEqual(trow["status"], "succeeded")  # G: task state unchanged

    # H — deterministic arbitration winner
    def test_H_arbitration_deterministic(self):
        # g1 ACTIVE HIGH user ; g2 PENDING URGENT user -> lifecycle rule wins for g1
        g1, _ = _mk({"type": "a", "title": "active-high", "source": "USER_REQUESTED",
                     "owner": "user", "priority": "HIGH"})
        _trans(g1["goalId"], {"action": "activate"})
        g2, _ = _mk({"type": "b", "title": "pending-urgent", "source": "USER_REQUESTED",
                     "owner": "user", "priority": "URGENT"})
        conn = app._goals_db()
        try:
            r1 = app._arbitrate(conn)
            r2 = app._arbitrate(conn)
        finally:
            conn.close()
        self.assertEqual(r1["arbitration"]["winner"], g1["goalId"])
        self.assertEqual(r2["arbitration"]["winner"], g1["goalId"])  # stable
        alt = r1["arbitration"]["alternatives"][0]
        self.assertEqual(alt["goalId"], g2["goalId"])
        self.assertEqual(alt["eliminatedBy"], "lifecycle")

    # I — blocked cannot silently activate ; J — explicit unblock works
    def test_I_J_blocked(self):
        g, _ = _mk({"type": "x", "title": "t", "source": "USER_REQUESTED", "owner": "user"})
        gid = g["goalId"]
        _trans(gid, {"action": "block", "blockedReason": "waiting"})
        with self.assertRaises(HTTPException) as ctx:
            _trans(gid, {"action": "activate"})  # BLOCKED -> ACTIVE not allowed
        self.assertEqual(ctx.exception.status_code, 409)
        # blocked goal is excluded from arbitration candidates (I: no silent focus)
        conn = app._goals_db()
        try:
            self.assertIsNone(app._arbitrate(conn)["focus"])
        finally:
            conn.close()
        out = _trans(gid, {"action": "unblock"})[0]  # J: explicit unblock
        self.assertEqual(out["lifecycleState"], "ACTIVE")
        self.assertIsNone(out["blockedReason"])

    # K — suspended resumes
    def test_K_suspend_resume(self):
        g, _ = _mk({"type": "x", "title": "t", "source": "USER_REQUESTED", "owner": "user"})
        gid = g["goalId"]
        _trans(gid, {"action": "activate"})
        _trans(gid, {"action": "suspend"})
        self.assertEqual(_trans(gid, {"action": "resume"})[0]["lifecycleState"], "ACTIVE")

    # L — completed/cancelled does not silently reactivate; reopen is explicit+traced
    def test_L_terminal_no_silent_reactivation(self):
        g, _ = _mk({"type": "x", "title": "t", "source": "USER_REQUESTED", "owner": "user"})
        gid = g["goalId"]
        _trans(gid, {"action": "activate"})
        _trans(gid, {"action": "complete"})
        with self.assertRaises(HTTPException) as ctx:
            _trans(gid, {"action": "activate"})  # COMPLETED -> ACTIVE illegal
        self.assertEqual(ctx.exception.status_code, 409)
        out = _trans(gid, {"action": "reopen"})[0]  # explicit
        self.assertEqual(out["lifecycleState"], "PENDING")
        conn = app._goals_db()
        try:
            row = conn.execute("SELECT COUNT(*) c FROM goal_trace WHERE goal_id=?"
                               " AND action='reopen'", (gid,)).fetchone()
        finally:
            conn.close()
        self.assertEqual(row["c"], 1)

    # M — world model can inform Executive read-only
    def test_M_world_read(self):
        _seed_belief("14", "status", "applied")
        beliefs = app._exec_read_beliefs("career.application", "14")
        self.assertTrue(any(b["predicate"] == "status" for b in beliefs))

    # N — conflicted belief prevents unsafe silent progression
    def test_N_conflicted_blocks(self):
        _seed_belief("14", "status", "applied", lifecycle="CONFLICTED")
        self.assertTrue(app._exec_world_conflicted("career.application", "14"))
        self.assertFalse(app._exec_world_conflicted("career.application", "99"))

    # O — Executive cannot mutate World Model directly (structural)
    def test_O_no_world_mutation_symbols(self):
        src = Path(app.__file__).read_text(encoding="utf-8")
        begin = src.index("BEGIN SLICE 8")
        end = src.index("END SLICE 8")
        block = src[begin:end]
        for sym in ("submit_observation", "submit_user_assertion",
                    "submit_inference_candidate", "apply_verified_delta",
                    "_world_reconcile"):
            self.assertNotIn(sym, block, "forbidden world-mutation symbol: " + sym)
        self.assertIn("_world_ro_conn", block)  # reads only via the ro connection
        # the read path uses a read-only connection: writing through it fails
        ro = app._world_ro_conn()
        try:
            with self.assertRaises(sqlite3.OperationalError):
                ro.execute("INSERT INTO world_belief (key, entity_type, entity_id,"
                           " predicate, value_json, lifecycle_state, epistemic_state,"
                           " confidence, confidence_tier, confidence_basis, created_at,"
                           " updated_at, revision) VALUES"
                           " ('x','y','z','p','1','ACTIVE','OBSERVED',0.5,'low','b',"
                           " 'n','n',1)")
                ro.commit()
        finally:
            ro.close()

    # P — Executive invokes no connector/tool/network/send
    def test_P_no_connector_or_send(self):
        src = Path(app.__file__).read_text(encoding="utf-8")
        block = src[src.index("BEGIN SLICE 8"):src.index("END SLICE 8")]
        for sym in ("urllib", "subprocess", "smtplib", "requests.", "socket.",
                    "http.client", "connector"):
            self.assertNotIn(sym, block, "forbidden i/o symbol: " + sym)

    # Q — trace emitted for every transition
    def test_Q_trace_per_transition(self):
        g, _ = _mk({"type": "x", "title": "t", "source": "USER_REQUESTED", "owner": "user"})
        gid = g["goalId"]
        _trans(gid, {"action": "activate"})
        _trans(gid, {"action": "suspend"})
        _trans(gid, {"action": "resume"})
        conn = app._goals_db()
        try:
            rows = conn.execute("SELECT action FROM goal_trace WHERE goal_id=? AND"
                                " kind='transition' ORDER BY id", (gid,)).fetchall()
        finally:
            conn.close()
        actions = [r["action"] for r in rows]
        self.assertEqual(actions, ["create", "activate", "suspend", "resume"])

    # R — arbitration trace explainable
    def test_R_arbitration_trace(self):
        g1, _ = _mk({"type": "a", "title": "u", "source": "USER_REQUESTED", "owner": "user"})
        g2, _ = _mk({"type": "b", "title": "s", "source": "SCHEDULED", "owner": "system"})
        _trans(g1["goalId"], {"action": "activate"})
        res = app.goal_focus()
        self.assertEqual(res["arbitration"]["winner"], g1["goalId"])
        self.assertTrue(res["arbitration"]["alternatives"])
        self.assertIn("ruleFired", res["arbitration"])
        conn = app._goals_db()
        try:
            t = conn.execute("SELECT arbitration_alternatives_json FROM goal_trace"
                             " WHERE kind='arbitration' ORDER BY id DESC LIMIT 1").fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(t)
        self.assertTrue(json.loads(t["arbitration_alternatives_json"]))

    # dedup S — exactly one existing -> reuse
    def test_dedup_reuse(self):
        p = {"type": "career.followup", "title": "Follow up 14",
             "source": "USER_REQUESTED", "owner": "user",
             "target": {"type": "career.application", "id": "14"}}
        g1, c1 = _mk(p)
        g2, c2 = _mk(dict(p))
        self.assertTrue(c1)
        self.assertFalse(c2)                 # reused, not created
        self.assertEqual(g1["goalId"], g2["goalId"])
        conn = app._goals_db()
        try:
            n = conn.execute("SELECT COUNT(*) c FROM goal").fetchone()["c"]
        finally:
            conn.close()
        self.assertEqual(n, 1)

    # dedup T — multiple existing -> reconciliation required, create nothing
    def test_dedup_reconciliation_required(self):
        p = {"type": "career.followup", "title": "Follow up 14",
             "source": "USER_REQUESTED", "owner": "user",
             "target": {"type": "career.application", "id": "14"}}
        # The deduping create path can never MAKE two equivalents; simulate the
        # anomalous pre-existing state by inserting the second row directly.
        g1, _ = _mk(p)
        conn = app._goals_db()
        try:
            row = conn.execute("SELECT * FROM goal WHERE goal_id=?",
                               (g1["goalId"],)).fetchone()
            now = app._goal_now()
            conn.execute(
                "INSERT INTO goal (goal_id, schema_version, type, title, source, owner,"
                " lifecycle_state, priority, linked_task_ids, target_json, target_key,"
                " created_at, updated_at, revision) VALUES (?,?,?,?,?,?,?,?, '[]', ?,?,"
                " ?,?,1)",
                ("g.dup2", 1, row["type"], row["title"], row["source"], row["owner"],
                 "PENDING", "NORMAL", row["target_json"], row["target_key"], now, now))
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(HTTPException) as ctx:
            _mk(dict(p))
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail["error"], "reconciliation_required")
        self.assertEqual(len(ctx.exception.detail["goalIds"]), 2)

    # U — real career goal (app 14) blocked on duplicate unsent drafts
    def test_U_app14_blocked_on_duplicate_drafts(self):
        _seed_draft("d.os2.14.a81a87acd64c2d46", "14")
        _seed_draft("d.os2.14.01caa11f61d6395d", "14")
        res = app.post_goal({"type": "career.followup", "title": "Follow up 14",
                             "source": "USER_REQUESTED", "owner": "user",
                             "target": {"type": "career.application", "id": "14"},
                             "evaluateBlock": True})
        g = res["goal"]
        self.assertEqual(g["lifecycleState"], "BLOCKED")
        self.assertIn("reconciliation", (g["blockedReason"] or "").lower())
        self.assertEqual(sorted(g["blockedBy"]), sorted([
            "draft:d.os2.14.01caa11f61d6395d", "draft:d.os2.14.a81a87acd64c2d46"]))

    # completion evidence — career.followup (send) can never be completed
    def test_completion_followup_refused(self):
        g, _ = _mk({"type": "career.followup", "title": "t", "source": "USER_REQUESTED",
                    "owner": "user", "target": {"type": "career.application", "id": "17"}})
        _trans(g["goalId"], {"action": "activate"})
        with self.assertRaises(HTTPException) as ctx:
            _trans(g["goalId"], {"action": "complete"})
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail["error"], "evidence_required")

    # completion evidence — prepare_followup completes only with a real draft
    def test_completion_prepare_requires_draft(self):
        g, _ = _mk({"type": "career.prepare_followup", "title": "prep",
                    "source": "USER_REQUESTED", "owner": "user",
                    "target": {"type": "career.application", "id": "21"}})
        _trans(g["goalId"], {"action": "activate"})
        with self.assertRaises(HTTPException):
            _trans(g["goalId"], {"action": "complete"})  # no draft yet
        _seed_draft("d.prep.21", "21")
        out = _trans(g["goalId"], {"action": "complete"})[0]
        self.assertEqual(out["lifecycleState"], "COMPLETED")

    # idempotency + revision guard
    def test_idempotency_and_revision(self):
        g, _ = _mk({"type": "x", "title": "t", "source": "USER_REQUESTED", "owner": "user"})
        gid = g["goalId"]
        r1 = _trans(gid, {"action": "activate", "operationId": "opA"})
        self.assertTrue(r1[1])
        r2 = _trans(gid, {"action": "activate", "operationId": "opA"})  # replay
        self.assertFalse(r2[1])              # not applied again
        with self.assertRaises(HTTPException) as ctx:
            _trans(gid, {"action": "suspend", "expectedRevision": 999})
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail["error"], "revision_conflict")


if __name__ == "__main__":
    unittest.main(verbosity=2)
