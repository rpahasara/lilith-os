#!/usr/bin/env python3
"""P-4 P4-4: mirror LILITH's real scheduled commitments into the Goals store (LILITH OS stays authoritative).

The full agent already has Hermes' scheduler (the `cronjob` tool): when the owner asks "remind me at 6 to call mum" or
"check the release notes tomorrow and tell me", the agent creates a job that Hermes' scheduler fires and delivers back
to the same chat. Until now that commitment lived only in Hermes' jobs.json, invisible to LILITH OS's Goals, the
Executive focus and the nightly review, and nothing noticed when one was missed.

This silent no-agent cron script (same pattern as owner_memory_snapshot.py) makes each such job a typed goal:

    commitment.once      a one-time reminder or follow-up        PENDING -> ACTIVE -> COMPLETED | FAILED | CANCELLED
    commitment.routine   a recurring one ("every Monday ...")   ACTIVE until removed (CANCELLED)

Evidence only, never inferred:
- created and accepted by the scheduler (job present, `next_run_at` set)  -> goal created and activated;
- the scheduler's own run record (cron/executions.db) says completed      -> COMPLETED ("honoured");
- it says failed                                                           -> FAILED;
- due more than GRACE ago, still not run                                   -> BLOCKED ("missed"); a later run resolves it;
- paused / resumed by the owner                                            -> SUSPENDED / ACTIVE;
- the job is gone and the scheduler never ran it                           -> CANCELLED ("removed before it ran").
Hermes deletes a one-time job right after its run, so "gone" alone never means cancelled: the run record decides.

Only jobs created from an owner channel (console, owner Telegram DM, verified Discord DM; the router's owner rule)
are commitments. System jobs (scripts / no-agent) are skipped. Nothing is sent, scheduled or deleted here; the only
writes are the Goals API (loopback, controlled create / transition with a reason in the goal trace) and this script's
own state file. Prints nothing on success; one line per change with --verbose (ids and states, never job text).

Rollback: disable this cron job; the goals stay as an accurate history and can be cancelled through the Goals API.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

HOME = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
API = os.environ.get("LILITH_OS_API_URL", "http://127.0.0.1:8765")
STATE = "commitments/sync.json"
GRACE_S = 30 * 60
TITLE_MAX = 160

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from owner_memory_review import owner_discord_dms, owner_ids   # the same owner rule as the nightly review
except Exception:                                                  # pragma: no cover - fail closed
    def owner_ids(home):
        return set()

    def owner_discord_dms(home):
        return set()


def _ts(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    try:
        d = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)).timestamp()
    except ValueError:
        return None


def _iso(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if ts else None


# ---------------------------------------------------------------------------------------------- reading ---

def load_jobs(home: Path) -> dict:
    try:
        d = json.loads((home / "cron" / "jobs.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    jobs = d.get("jobs", []) if isinstance(d, dict) else d
    if isinstance(jobs, dict):
        jobs = list(jobs.values())
    return {str(j["id"]): j for j in jobs if isinstance(j, dict) and j.get("id")}


def runs(home: Path, job_id: str) -> list:
    """The scheduler's own run records for a job: [(status, finished_ts)], oldest first. Read-only."""
    try:
        con = sqlite3.connect(f"file:{home / 'cron' / 'executions.db'}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return []
    try:
        rows = con.execute("SELECT status, finished_at FROM executions WHERE job_id=? AND status IN "
                           "('completed', 'failed') ORDER BY coalesce(finished_at, claimed_at)", (job_id,)).fetchall()
    except sqlite3.Error:
        rows = []
    finally:
        con.close()
    return [(s, _ts(f)) for s, f in rows]


def owner_origin(job: dict, telegram_ids: set, discord_dms: set) -> str | None:
    """The owner channel a job was created from, or None (not a commitment)."""
    o = job.get("origin") or {}
    platform, chat = str(o.get("platform") or ""), str(o.get("chat_id") or "")
    if platform == "lilith_os":
        return "lilith_os"
    if platform == "telegram" and chat and chat in telegram_ids:
        return "telegram_owner_dm"
    if platform == "discord" and chat and chat in {c for _, c in discord_dms}:
        return "discord_owner_dm"
    return None


def is_agent_job(job: dict) -> bool:
    return not (job.get("script") or job.get("no_agent") or job.get("monitor_script"))


def one_shot(job: dict) -> bool:
    sched = job.get("schedule") or {}
    times = (job.get("repeat") or {}).get("times")
    return sched.get("kind") == "once" or times == 1


# -------------------------------------------------------------------------------------- the decision ---

def desired(entry: dict, job: dict | None, job_runs: list, now: float) -> tuple[str, str] | None:
    """(target lifecycle, reason) for a tracked commitment, or None to leave it. Pure; evidence only."""
    created = entry.get("created_ts") or 0
    after = [(s, f) for s, f in job_runs if f is None or f >= created - 60]
    if entry.get("once"):
        if after:
            status, finished = after[-1]
            if status == "completed":
                return "COMPLETED", "honoured: the scheduler completed the run at %s" % (_iso(finished) or "unknown")
            return "FAILED", "the scheduler run failed at %s" % (_iso(finished) or "unknown")
        if job is None:
            return "CANCELLED", "removed before it ran"
        if job.get("state") == "paused" or job.get("enabled") is False:
            return "SUSPENDED", "paused"
        due = entry.get("due_ts")
        if due and now - due > GRACE_S:
            return "BLOCKED", "missed: due %s and not run by the scheduler" % _iso(due)
        return "ACTIVE", "accepted by the scheduler"
    if job is None:
        return "CANCELLED", "routine removed"
    if job.get("state") == "paused" or job.get("enabled") is False:
        return "SUSPENDED", "paused"
    return "ACTIVE", "routine scheduled"


# Goal FSM moves (Core API _GOAL_ACTIONS) from a current lifecycle to a target one.
PATH = {
    ("PENDING", "ACTIVE"): ["activate"], ("PENDING", "COMPLETED"): ["activate", "complete"],
    ("PENDING", "FAILED"): ["activate", "fail"], ("PENDING", "BLOCKED"): ["block"],
    ("PENDING", "SUSPENDED"): ["activate", "suspend"], ("PENDING", "CANCELLED"): ["cancel"],
    ("ACTIVE", "COMPLETED"): ["complete"], ("ACTIVE", "FAILED"): ["fail"], ("ACTIVE", "BLOCKED"): ["block"],
    ("ACTIVE", "SUSPENDED"): ["suspend"], ("ACTIVE", "CANCELLED"): ["cancel"],
    ("BLOCKED", "ACTIVE"): ["unblock"], ("BLOCKED", "COMPLETED"): ["unblock", "complete"],
    ("BLOCKED", "FAILED"): ["fail"], ("BLOCKED", "CANCELLED"): ["cancel"],
    ("SUSPENDED", "ACTIVE"): ["resume"], ("SUSPENDED", "COMPLETED"): ["resume", "complete"],
    ("SUSPENDED", "FAILED"): ["resume", "fail"], ("SUSPENDED", "BLOCKED"): ["resume", "block"],
    ("SUSPENDED", "CANCELLED"): ["cancel"],
}


# ------------------------------------------------------------------------------------------- writing ---

def _api(method: str, path: str, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def create_goal(job: dict, channel: str, once: bool) -> dict:
    name = " ".join(str(job.get("name") or "").split())[:TITLE_MAX] or "Scheduled follow-up"
    body = {"type": "commitment.once" if once else "commitment.routine", "title": name, "source": "SCHEDULED",
            "owner": "user", "priority": "NORMAL", "target": {"type": "hermes.cron", "id": str(job["id"])},
            "sourceChannel": channel, "createdVia": "commitment_sync",
            "operationId": "commit-create-" + str(job["id"]),
            "correlationId": "commit-" + str(job["id"])}
    due = _ts(job.get("next_run_at"))
    if once and due:
        body["deadline"] = _iso(due)                       # only the scheduler's own fire time; never invented
    out = _api("POST", "/os/goals", body)
    return out.get("goal", out)


def transition(goal_id: str, action: str, reason: str, job_id: str, step: int) -> dict:
    out = _api("POST", "/os/goals/%s/transition" % goal_id,
               {"action": action, "reason": reason, "correlationId": "commit-" + job_id,
                "operationId": "commit-%s-%s-%d" % (job_id, action, step)})
    return out.get("goal", out)


def _read_state(home: Path) -> dict:
    try:
        return json.loads((home / STATE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_state(home: Path, state: dict) -> None:
    path = home / STATE
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def sync(home: Path = HOME, now: float | None = None, api=None) -> list:
    """One pass. Returns change records (ids, types, states; no job text). `api` overrides the HTTP layer in tests."""
    global _api
    if api is not None:
        _api = api
    now = dt.datetime.now(dt.timezone.utc).timestamp() if now is None else now
    state, changes = _read_state(home), []
    jobs = load_jobs(home)
    tg, dc = owner_ids(home), owner_discord_dms(home)
    for jid, job in jobs.items():                          # new commitments the scheduler has accepted
        if jid in state or not is_agent_job(job) or not job.get("next_run_at"):
            continue
        channel = owner_origin(job, tg, dc)
        if channel is None:
            continue
        once = one_shot(job)
        try:
            goal = create_goal(job, channel, once)
        except (urllib.error.HTTPError, KeyError, ValueError) as exc:
            changes.append({"job": jid, "event": "create_refused", "error": type(exc).__name__})
            continue
        state[jid] = {"goal": goal["goalId"], "once": once, "created_ts": _ts(job.get("created_at")) or now,
                      "due_ts": _ts(job.get("next_run_at")) if once else None, "status": goal.get("lifecycleState"),
                      "step": 0}
        changes.append({"job": jid, "goal": goal["goalId"], "event": "created", "type": "once" if once else "routine"})
    for jid, entry in state.items():
        if entry.get("status") in ("COMPLETED", "FAILED", "CANCELLED"):
            continue
        target = desired(entry, jobs.get(jid), runs(home, jid), now)
        if target is None or target[0] == entry.get("status"):
            continue
        try:
            for action in PATH.get((entry.get("status"), target[0]), []):
                entry["step"] = int(entry.get("step") or 0) + 1
                goal = transition(entry["goal"], action, target[1], jid, entry["step"])
                entry["status"] = goal.get("lifecycleState", entry["status"])
        except (urllib.error.HTTPError, KeyError, ValueError) as exc:
            changes.append({"job": jid, "goal": entry["goal"], "event": "transition_refused",
                            "error": type(exc).__name__})
            continue
        changes.append({"job": jid, "goal": entry["goal"], "event": target[0].lower()})
    _write_state(home, state)
    return changes


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        changes = sync()
    except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
        print("commitment_sync FAILED: %s" % type(exc).__name__)
        return 1
    if "--verbose" in argv:
        for c in changes:
            print(json.dumps(c, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
