"""P-4 P4-4: scheduler jobs from owner channels become typed goals; outcomes come only from the scheduler's own run
records; one-time jobs deleted after their run are not mistaken for cancellations; non-owner and system jobs never
count. Uses an in-memory fake of the Goals API that applies the Core API's FSM."""
import importlib.util
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

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
        if path == "/os/goals":
            gid = "g.%d" % (len(self.goals) + 1)
            self.goals[gid] = dict(body, goalId=gid, lifecycleState="PENDING", trace=[])
            return {"goal": self.goals[gid]}
        gid = path.split("/")[3]
        g = self.goals[gid]
        allowed, target = ACTIONS[body["action"]]
        if g["lifecycleState"] not in allowed:
            raise CS.urllib.error.HTTPError(path, 409, "invalid_transition", None, None)
        g["lifecycleState"] = target
        g["trace"].append(body["reason"])
        return {"goal": g}


def iso(ts):
    return CS._iso(ts)


class CommitmentSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / "lilith_router").mkdir()
        (self.home / "lilith_router" / "canonical_memory.json").write_text(json.dumps(
            {"schemaVersion": 1, "enabled": True, "ownerTelegramUserIds": [OWNER],
             "ownerDiscordDms": [{"userId": "77", "chatId": "88"}]}), encoding="ascii")
        (self.home / "cron").mkdir()
        con = sqlite3.connect(self.home / "cron" / "executions.db")
        con.execute("CREATE TABLE executions (id TEXT PRIMARY KEY, job_id TEXT NOT NULL, source TEXT NOT NULL, "
                    "process_id TEXT NOT NULL, pid INTEGER NOT NULL, process_started_at INTEGER, status TEXT NOT NULL, "
                    "claimed_at TEXT NOT NULL, started_at TEXT, finished_at TEXT, error TEXT)")
        con.commit()
        con.close()
        self.api = FakeGoals()

    def tearDown(self):
        self.tmp.cleanup()

    def jobs(self, *jobs):
        (self.home / "cron" / "jobs.json").write_text(json.dumps({"jobs": list(jobs)}), encoding="utf-8")

    def run_record(self, job_id, status, finished):
        con = sqlite3.connect(self.home / "cron" / "executions.db")
        con.execute("INSERT INTO executions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (job_id + status + str(finished), job_id, "tick", "p", 1, 0, status, iso(finished - 5),
                     iso(finished - 5), iso(finished), None))
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

    def test_honoured_one_time_reminder_after_auto_delete(self):
        self.jobs(self.job("j1"))
        ch = self.sync(T0 + 10)
        self.assertEqual(ch[0]["event"], "created")
        g = self.goal()
        self.assertEqual((g["type"], g["lifecycleState"], g["source"]), ("commitment.once", "ACTIVE", "SCHEDULED"))
        self.assertEqual(g["target"], {"type": "hermes.cron", "id": "j1"})
        self.assertEqual(g["deadline"], iso(T0 + 3600))
        self.assertEqual(g["sourceChannel"], "telegram_owner_dm")
        self.jobs()                                                   # Hermes deletes a one-time job after its run
        self.run_record("j1", "completed", T0 + 3605)
        self.sync(T0 + 3700)
        self.assertEqual(g["lifecycleState"], "COMPLETED")
        self.assertIn("honoured", g["trace"][-1])
        self.assertNotIn("PRIVATE-PROMPT", json.dumps(self.api.calls))

    def test_missed_then_resolved_and_failed_runs(self):
        self.jobs(self.job("j1"))
        self.sync(T0 + 10)
        self.sync(T0 + 3600 + CS.GRACE_S + 60)                         # due, never run: missed
        self.assertEqual(self.goal()["lifecycleState"], "BLOCKED")
        self.assertIn("missed", self.goal()["trace"][-1])
        self.run_record("j1", "completed", T0 + 3600 + CS.GRACE_S + 120)
        self.jobs()
        self.sync(T0 + 3600 + CS.GRACE_S + 200)
        self.assertEqual(self.goal()["lifecycleState"], "COMPLETED")
        self.jobs(self.job("j2"))
        self.sync(T0 + 20)
        self.run_record("j2", "failed", T0 + 3601)
        self.sync(T0 + 3650)
        self.assertEqual(self.goal(2)["lifecycleState"], "FAILED")

    def test_cancel_only_when_gone_without_a_run(self):
        self.jobs(self.job("j1"))
        self.sync(T0 + 10)
        self.jobs()
        self.sync(T0 + 100)
        self.assertEqual(self.goal()["lifecycleState"], "CANCELLED")
        self.assertIn("removed before it ran", self.goal()["trace"][-1])

    def test_pause_resume_and_routine(self):
        self.jobs(self.job("j1", kind="cron", state="paused", enabled=False))
        self.sync(T0 + 10)
        g = self.goal()
        self.assertEqual((g["type"], g["lifecycleState"]), ("commitment.routine", "SUSPENDED"))
        self.assertNotIn("deadline", g)
        self.jobs(self.job("j1", kind="cron"))
        self.sync(T0 + 20)
        self.assertEqual(g["lifecycleState"], "ACTIVE")
        self.run_record("j1", "completed", T0 + 3605)                   # a routine run never completes the routine
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
        made = sorted(g["target"]["id"] for g in self.api.goals.values())
        self.assertEqual(made, ["con", "disc"])

    def test_idempotent_and_state_survives(self):
        self.jobs(self.job("j1"))
        self.sync(T0 + 10)
        n = len(self.api.calls)
        self.assertEqual(self.sync(T0 + 20), [])
        self.assertEqual(len(self.api.calls), n)
        state = json.loads((self.home / CS.STATE).read_text(encoding="utf-8"))
        self.assertEqual(state["j1"]["status"], "ACTIVE")

    def test_refused_transition_does_not_stop_the_pass(self):
        self.jobs(self.job("j1"), self.job("j2"))
        self.sync(T0 + 10)
        self.goal(1)["lifecycleState"] = "COMPLETED"                   # changed elsewhere (e.g. by the owner)
        self.jobs()
        self.run_record("j2", "completed", T0 + 3605)
        ch = self.sync(T0 + 3700)
        events = {c["job"]: c["event"] for c in ch}
        self.assertEqual(events["j1"], "transition_refused")
        self.assertEqual(self.goal(2)["lifecycleState"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
