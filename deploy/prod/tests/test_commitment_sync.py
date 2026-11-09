"""P-4 P4-4: scheduler jobs from owner channels become typed goals; outcomes come only from the scheduler's own run
records; nothing is ever concluded from missing evidence (owner review 2026-11-09). Uses an in-memory fake of the
Goals API that applies the Core API's FSM and revisions."""
import importlib.util
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

os.environ["LILITH_OS_API_URL"] = "http://127.0.0.1:9"
ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("commitment_sync", ROOT / "deploy/prod/hermes_scripts/commitment_sync.py")
CS = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CS)

OWNER = "1111794198"
T0 = 1_800_000_000.0
ACTIONS = {"activate": ({"PENDING"}, "ACTIVE"), "block": ({"PENDING", "ACTIVE"}, "BLOCKED"),
           "unblock": ({"BLOCKED"}, "ACTIVE"), "suspend": ({"ACTIVE"}, "SUSPENDED"),
           "resume": ({"SUSPENDED"}, "ACTIVE"), "complete": ({"ACTIVE"}, "COMPLETED"),
           "fail": ({"ACTIVE", "BLOCKED"}, "FAILED"),
           "cancel": ({"PENDING", "ACTIVE", "BLOCKED", "SUSPENDED"}, "CANCELLED")}


class FakeGoals:
    def __init__(self):
        self.goals, self.calls = {}, []

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == "GET":
            q = parse_qs(urlparse(path).query)
            return {"goals": [g for g in self.goals.values() if g["type"] == q["type"][0]]}
        if path == "/os/goals":
            gid = "g.%d" % (len(self.goals) + 1)
            self.goals[gid] = dict(body, goalId=gid, lifecycleState="PENDING", revision=1, trace=[],
                                   createdAt=CS._iso(T0))
            return {"goal": self.goals[gid]}
        g = self.goals[path.split("/")[3]]
        allowed, target = ACTIONS[body["action"]]
        if g["lifecycleState"] not in allowed:
            raise CS.urllib.error.HTTPError(path, 409, "invalid_transition", None, None)
        g["lifecycleState"] = target
        g["revision"] += 1
        g["trace"].append(body["reason"])
        return {"goal": g}

    def writes(self):
        return [c for c in self.calls if c[0] == "POST"]


iso = CS._iso


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / "lilith_router").mkdir()
        (self.home / "lilith_router" / "canonical_memory.json").write_text(json.dumps(
            {"schemaVersion": 1, "enabled": True, "ownerTelegramUserIds": [OWNER],
             "ownerDiscordDms": [{"userId": "77", "chatId": "88"}]}), encoding="ascii")
        (self.home / "cron").mkdir()
        self.make_db()
        self.api = FakeGoals()

    def tearDown(self):
        self.tmp.cleanup()

    def make_db(self):
        con = sqlite3.connect(self.home / "cron" / "executions.db")
        con.execute("CREATE TABLE IF NOT EXISTS executions (id TEXT PRIMARY KEY, job_id TEXT NOT NULL, source TEXT, "
                    "process_id TEXT, pid INTEGER, process_started_at INTEGER, status TEXT NOT NULL, "
                    "claimed_at TEXT NOT NULL, started_at TEXT, finished_at TEXT, error TEXT)")
        con.commit()
        con.close()

    def jobs(self, *jobs):
        (self.home / "cron" / "jobs.json").write_text(json.dumps({"jobs": list(jobs)}), encoding="utf-8")

    def run_record(self, job_id, status, at, finished=True):
        con = sqlite3.connect(self.home / "cron" / "executions.db")
        con.execute("INSERT INTO executions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (job_id + status + str(at), job_id, "tick", "p", 1, 0, status, iso(at - 5), iso(at - 5),
                     iso(at) if finished else None, None))
        con.commit()
        con.close()

    def job(self, jid, chat=OWNER, platform="telegram", due=T0 + 3600, kind="once", **kw):
        j = {"id": jid, "name": "Call mum", "origin": {"platform": platform, "chat_id": chat},
             "schedule": {"kind": kind}, "repeat": {"times": 1 if kind == "once" else None, "completed": 0},
             "next_run_at": iso(due), "created_at": iso(T0), "enabled": True, "state": "scheduled",
             "prompt": "PRIVATE-PROMPT"}
        j.update(kw)
        return j

    def sync(self, now):
        return CS.sync(self.home, now=now, api=self.api)

    def goal(self, n=1):
        return self.api.goals["g.%d" % n]

    def state_bytes(self):
        return (self.home / CS.STATE).read_bytes()


class LifecycleTests(Base):
    def test_completed_run_after_auto_delete_is_not_called_delivered(self):
        self.jobs(self.job("j1"))
        first = self.sync(T0 + 10)
        self.assertEqual([e["event"] for e in first], ["state_rebuilt", "created", "active"])     # first pass: empty rebuild
        g = self.goal()
        self.assertEqual((g["type"], g["lifecycleState"], g["source"]), ("commitment.once", "ACTIVE", "SCHEDULED"))
        self.assertEqual((g["target"], g["deadline"], g["sourceChannel"]),
                         ({"type": "hermes.cron", "id": "j1"}, iso(T0 + 3600), "telegram_owner_dm"))
        self.jobs()                                                   # Hermes deletes a one-time job after its run
        self.run_record("j1", "completed", T0 + 3605)
        self.sync(T0 + 3700)
        self.assertEqual(g["lifecycleState"], "COMPLETED")
        self.assertIn("delivery to the chat not verified", g["trace"][-1])
        self.assertNotIn("PRIVATE-PROMPT", json.dumps(self.api.calls))

    def test_kept_job_without_delivery_error_is_stated_precisely(self):
        self.jobs(self.job("j1"))
        self.sync(T0 + 10)
        self.run_record("j1", "completed", T0 + 3605)
        self.jobs(self.job("j1", state="completed", last_status="ok", next_run_at=None))   # PROD 2026-11-09: kept
        self.sync(T0 + 3700)
        self.assertEqual(self.goal()["lifecycleState"], "COMPLETED")
        self.assertIn("recorded no delivery error (receipt by the owner not confirmed)", self.goal()["trace"][-1])

    def test_visible_delivery_error_is_a_failure(self):
        self.jobs(self.job("j1"))
        self.sync(T0 + 10)
        self.run_record("j1", "completed", T0 + 3605)
        self.jobs(self.job("j1", last_delivery_error="platform down"))
        self.sync(T0 + 3700)
        self.assertEqual(self.goal()["lifecycleState"], "FAILED")
        self.assertIn("delivery failed", self.goal()["trace"][-1])

    def test_missed_then_resolved_and_failed_runs(self):
        self.jobs(self.job("j1"))
        self.sync(T0 + 10)
        self.sync(T0 + 3600 + CS.GRACE_S + 60)                         # due, still present, never run: missed
        self.assertEqual(self.goal()["lifecycleState"], "BLOCKED")
        self.run_record("j1", "completed", T0 + 3600 + CS.GRACE_S + 120)
        self.jobs()
        self.sync(T0 + 3600 + CS.GRACE_S + 200)
        self.assertEqual(self.goal()["lifecycleState"], "COMPLETED")
        self.jobs(self.job("j2"))
        self.sync(T0 + 20)
        self.run_record("j2", "failed", T0 + 3601)
        self.sync(T0 + 3650)
        self.assertEqual(self.goal(2)["lifecycleState"], "FAILED")

    def test_cancel_only_when_gone_before_due_without_any_run(self):
        self.jobs(self.job("j1"))
        self.sync(T0 + 10)
        self.jobs()
        self.sync(T0 + 100)
        self.assertEqual(self.goal()["lifecycleState"], "CANCELLED")
        self.assertIn("before it was due", self.goal()["trace"][-1])

    def test_pause_resume_and_routine(self):
        self.jobs(self.job("j1", kind="cron", state="paused", enabled=False))
        self.sync(T0 + 10)
        g = self.goal()
        self.assertEqual((g["type"], g["lifecycleState"]), ("commitment.routine", "SUSPENDED"))
        self.assertNotIn("deadline", g)
        self.jobs(self.job("j1", kind="cron"))
        self.sync(T0 + 20)
        self.assertEqual(g["lifecycleState"], "ACTIVE")
        self.run_record("j1", "completed", T0 + 3605)
        self.sync(T0 + 3700)
        self.assertEqual(g["lifecycleState"], "ACTIVE")
        self.jobs()
        self.sync(T0 + 3800)
        self.assertEqual(g["lifecycleState"], "CANCELLED")

    def test_only_owner_channels_and_agent_jobs(self):
        self.jobs(self.job("other", chat="42"), self.job("group", chat="-1001"),
                  self.job("disc", platform="discord", chat="88"), self.job("disc_other", platform="discord", chat="99"),
                  self.job("con", platform="lilith_os", chat="x"), self.job("sys", script="snap.py"),
                  self.job("noagent", no_agent=True), self.job("noorigin", origin=None))
        self.sync(T0 + 10)
        self.assertEqual(sorted(g["target"]["id"] for g in self.api.goals.values()), ["con", "disc"])

    def test_idempotent(self):
        self.jobs(self.job("j1"))
        self.sync(T0 + 10)
        n = len(self.api.writes())
        self.assertEqual(self.sync(T0 + 20), [])
        self.assertEqual(len(self.api.writes()), n)
        self.assertEqual(json.loads(self.state_bytes())["jobs"]["j1"]["status"], "ACTIVE")

    def test_refused_transition_does_not_stop_the_pass(self):
        self.jobs(self.job("j1"), self.job("j2"))
        self.sync(T0 + 10)
        self.goal(1)["lifecycleState"] = "COMPLETED"                   # changed elsewhere (e.g. by the owner)
        self.jobs()
        self.run_record("j1", "completed", T0 + 3605)
        self.run_record("j2", "completed", T0 + 3605)
        events = {e["job"]: e["event"] for e in self.sync(T0 + 3700)}
        self.assertEqual(events["j1"], "transition_refused")
        self.assertEqual(self.goal(2)["lifecycleState"], "COMPLETED")


class FailSafeTests(Base):
    """Owner review 2026-11-09: a read failure is never evidence."""

    def tracked(self):
        self.jobs(self.job("j1"))
        self.sync(T0 + 10)
        return self.state_bytes(), len(self.api.writes())

    def test_unreadable_or_malformed_jobs_file_aborts_without_writes(self):
        before, writes = self.tracked()
        for bad in (None, "{not json", json.dumps({"jobs": "nope"}), json.dumps(42)):
            path = self.home / "cron" / "jobs.json"
            if bad is None:
                path.unlink()
            else:
                path.write_text(bad, encoding="utf-8")
            with self.assertRaises(CS.SyncAborted):
                self.sync(T0 + 100)
            self.assertEqual(self.state_bytes(), before)
            self.assertEqual(len(self.api.writes()), writes)
            self.assertEqual(self.goal()["lifecycleState"], "ACTIVE")

    def test_verified_empty_scheduler_still_cancels_a_job_removed_before_due(self):
        self.tracked()
        self.jobs()                                                    # a jobs.json that parses, with no jobs
        self.sync(T0 + 100)
        self.assertEqual(self.goal()["lifecycleState"], "CANCELLED")

    def test_unreadable_execution_evidence_holds_instead_of_cancelling(self):
        self.tracked()
        self.jobs()
        (self.home / "cron" / "executions.db").unlink()
        events = self.sync(T0 + 3700)
        self.assertEqual(self.goal()["lifecycleState"], "ACTIVE")
        self.assertEqual(events[-1]["event"], "held")
        self.assertIn("evidence unavailable", events[-1]["reason"])
        self.assertEqual(self.sync(T0 + 3760), [])                      # reported once, not every pass
        (self.home / "cron" / "executions.db").write_bytes(b"this is not sqlite")
        self.assertEqual(self.sync(T0 + 3800), [])
        self.assertEqual(self.goal()["lifecycleState"], "ACTIVE")
        (self.home / "cron" / "executions.db").unlink()
        self.make_db()
        self.run_record("j1", "completed", T0 + 3605)                  # evidence back: resolved correctly
        self.sync(T0 + 3900)
        self.assertEqual(self.goal()["lifecycleState"], "COMPLETED")

    def test_gone_after_due_without_record_is_held_not_cancelled(self):
        self.tracked()
        self.jobs()
        events = self.sync(T0 + 3700)
        self.assertEqual(self.goal()["lifecycleState"], "ACTIVE")
        self.assertIn("inconsistent", events[-1]["reason"])

    def test_run_in_progress_or_unknown_is_held(self):
        self.tracked()
        self.jobs()
        self.run_record("j1", "running", T0 + 3601, finished=False)
        self.assertEqual(self.sync(T0 + 3650)[-1]["reason"], "run in progress")
        self.assertEqual(self.goal()["lifecycleState"], "ACTIVE")
        self.run_record("j1", "unknown", T0 + 3700, finished=False)
        self.sync(T0 + 3750)
        self.assertEqual(self.goal()["lifecycleState"], "ACTIVE")

    def test_corrupt_state_file_aborts_and_is_left_untouched(self):
        self.tracked()
        for bad in (b"{broken", json.dumps({"j1": {"goal": "g.1"}}).encode()):     # garbage; old / foreign format
            (self.home / CS.STATE).write_bytes(bad)
            with self.assertRaises(CS.SyncAborted):
                self.sync(T0 + 100)
            self.assertEqual(self.state_bytes(), bad)
        self.assertEqual(len(self.api.goals), 1)

    def test_missing_state_is_rebuilt_from_goals_without_duplicates(self):
        self.tracked()
        (self.home / CS.STATE).unlink()
        events = self.sync(T0 + 20)
        self.assertEqual(events[0], {"event": "state_rebuilt", "tracked": 1})
        self.assertEqual(len(self.api.goals), 1)                       # no second goal for the same job
        self.jobs()
        self.run_record("j1", "completed", T0 + 3605)
        self.sync(T0 + 3700)
        self.assertEqual(self.goal()["lifecycleState"], "COMPLETED")   # revision-keyed moves still apply

    def test_runs_of_untracked_jobs_are_counted(self):
        self.tracked()
        self.run_record("ghost", "completed", T0 + 50)                 # created and run between two passes
        self.run_record("j1", "completed", T0 + 3605)
        self.sync(T0 + 3700)
        self.assertEqual(json.loads(self.state_bytes())["unattributed_runs_24h"], 1)


if __name__ == "__main__":
    unittest.main()
