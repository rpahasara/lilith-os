#!/usr/bin/env python3
"""P-4 P4-4: mirror LILITH's real scheduled commitments into the Goals store (LILITH OS stays authoritative).

The full agent already has Hermes' scheduler (the `cronjob` tool): when the owner asks "remind me at 6 to call mum" or
"check the release notes tomorrow and tell me", the agent creates a job that Hermes' scheduler fires and delivers back
to the same chat. This silent no-agent cron script makes each such job a typed goal:

    commitment.once      a one-time reminder or follow-up        PENDING -> ACTIVE -> COMPLETED | FAILED | CANCELLED
    commitment.routine   a recurring one ("every Monday ...")   ACTIVE until removed (CANCELLED)

Evidence only, never inferred:
- accepted by the scheduler (job present, `next_run_at` set)              -> goal created and activated;
- the scheduler's run record (cron/executions.db) says completed          -> COMPLETED. This means the scheduled run
  finished; it does NOT prove the message reached the owner (Hermes deletes a one-time job after its run, and with it
  any delivery error). The reason says so; a delivery error seen on a still-present job is reported as FAILED;
- it says failed                                                           -> FAILED;
- due more than GRACE ago, job still present and not run                   -> BLOCKED ("missed"); a later run resolves it;
- paused / resumed                                                         -> SUSPENDED / ACTIVE;
- the job disappeared BEFORE its due time and the scheduler has no record of any run -> CANCELLED.

Fail-safe (owner review 2026-11-09): nothing is ever concluded from missing evidence.
- jobs.json missing, unreadable or malformed -> the whole pass stops; nothing is written (an empty scheduler is only
  ever a jobs.json that parses);
- executions.db unreadable, a run still in progress, or inconsistent evidence (gone after its due time with no run
  record) -> that commitment is HELD unchanged and reported;
- sync.json unreadable or malformed -> the pass stops and the file is left untouched; sync.json missing -> the mapping
  is rebuilt from the Goals API (the authoritative record) before anything new is created.

Coverage limit: this polls. A one-time job created and executed between two passes never appears in jobs.json and
cannot be attributed to a channel, so it is not tracked. Run it every minute; each pass reports how many scheduler runs
in the last 24 h belong to no tracked or present job (`unattributed_runs_24h`), so the gap is visible, never hidden.

Only jobs created from an owner channel (console, owner Telegram DM, verified Discord DM; the router's owner rule)
are commitments. System jobs (scripts / no-agent) are skipped. Nothing is sent, scheduled or deleted here; the only
writes are the Goals API (loopback; controlled create / transition with a reason in the goal trace) and this script's
own state file. Prints nothing on success; one JSON line per event with --verbose (ids and states, never job text).

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
STATE_VERSION = 2
GRACE_S = 30 * 60
TITLE_MAX = 160
TERMINAL = ("COMPLETED", "FAILED", "CANCELLED")

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from owner_memory_review import owner_discord_dms, owner_ids   # the same owner rule as the nightly review
except Exception:                                                  # pragma: no cover - fail closed
    def owner_ids(home):
        return set()

    def owner_discord_dms(home):
        return set()


class SyncAborted(Exception):
    """A precondition failed; the pass stops and writes nothing."""


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
    """The scheduler's jobs by id. Raises SyncAborted unless jobs.json exists and parses into a job list."""
    try:
        d = json.loads((home / "cron" / "jobs.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SyncAborted("jobs_unreadable:%s" % type(exc).__name__)
    jobs = d.get("jobs") if isinstance(d, dict) else d
    if isinstance(jobs, dict):
        jobs = list(jobs.values())
    if not isinstance(jobs, list):
        raise SyncAborted("jobs_malformed")
    return {str(j["id"]): j for j in jobs if isinstance(j, dict) and j.get("id")}


def load_runs(home: Path):
    """All scheduler run records: {job_id: [(status, finished_ts, claimed_ts)]} oldest first, or None when the
    executions database cannot be read (evidence unavailable)."""
    path = home / "cron" / "executions.db"
    if not path.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        try:
            rows = con.execute("SELECT job_id, status, finished_at, claimed_at FROM executions "
                               "ORDER BY coalesce(finished_at, claimed_at)").fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return None
    out = {}
    for jid, status, finished, claimed in rows:
        out.setdefault(str(jid), []).append((str(status), _ts(finished), _ts(claimed)))
    return out


def owner_origin(job: dict, telegram_ids: set, discord_dms: set):
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

HOLD = "HOLD"


def desired(entry: dict, job, job_runs, now: float):
    """(target lifecycle | HOLD, reason). Pure; evidence only. `job_runs` None = execution evidence unavailable."""
    created = entry.get("created_ts") or 0
    due = entry.get("due_ts")
    if entry.get("once"):
        if job_runs is not None:
            mine = [r for r in job_runs if (r[2] or r[1] or 0) >= created - 60]
            finished = [r for r in mine if r[0] in ("completed", "failed")]
            if finished:
                status, fin, _ = finished[-1]
                if status == "failed":
                    return "FAILED", "the scheduler run failed at %s" % (_iso(fin) or "unknown")
                if job is not None and job.get("last_delivery_error"):
                    return "FAILED", "run completed at %s but delivery failed" % (_iso(fin) or "unknown")
                return "COMPLETED", ("the scheduled run completed at %s; delivery to the chat not verified"
                                     % (_iso(fin) or "unknown"))
            if any(r[0] in ("claimed", "running") for r in mine):
                return (HOLD, "run in progress") if job is None else ("ACTIVE", "run in progress")
            if any(r[0] == "unknown" for r in mine):
                return HOLD, "run outcome unknown in the scheduler record"
        if job is not None:
            if job.get("state") == "paused" or job.get("enabled") is False:
                return "SUSPENDED", "paused"
            if due and now - due > GRACE_S:
                return "BLOCKED", "missed: due %s and not run by the scheduler" % _iso(due)
            return "ACTIVE", "accepted by the scheduler"
        if job_runs is None:
            return HOLD, "job gone and execution evidence unavailable"
        if due and now < due:
            return "CANCELLED", "removed before it was due (no run recorded)"
        return HOLD, "job gone after its due time with no run record (inconsistent evidence)"
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


def transition(goal_id: str, action: str, reason: str, job_id: str, revision) -> dict:
    # keyed by the goal's current revision: unique per move, and stable across a state rebuild (a reused
    # operationId would be taken by the Core API as a replay of an earlier move)
    out = _api("POST", "/os/goals/%s/transition" % goal_id,
               {"action": action, "reason": reason, "correlationId": "commit-" + job_id,
                "operationId": "commit-%s-%s-r%s" % (job_id, action, revision)})
    return out.get("goal", out)


def _read_state(home: Path):
    """(state, existed). Raises SyncAborted for an unreadable or malformed file, which is left untouched."""
    path = home / STATE
    if not path.exists():
        return {"v": STATE_VERSION, "jobs": {}}, False
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SyncAborted("state_unreadable:%s" % type(exc).__name__)
    if not (isinstance(state, dict) and state.get("v") == STATE_VERSION and isinstance(state.get("jobs"), dict)):
        raise SyncAborted("state_malformed")
    return state, True


def rebuild_state() -> dict:
    """The job -> goal mapping from the authoritative Goals store (used when sync.json is missing)."""
    jobs = {}
    for gtype in ("commitment.once", "commitment.routine"):
        for g in _api("GET", "/os/goals?type=%s&limit=200" % gtype).get("goals", []):
            tgt = g.get("target") or {}
            if tgt.get("type") != "hermes.cron" or not tgt.get("id"):
                continue
            jobs[str(tgt["id"])] = {"goal": g["goalId"], "once": gtype == "commitment.once",
                                    "created_ts": _ts(g.get("createdAt")), "due_ts": _ts(g.get("deadline")),
                                    "status": g.get("lifecycleState"), "rev": g.get("revision")}
    return {"v": STATE_VERSION, "jobs": jobs}


def _write_state(home: Path, state: dict) -> None:
    path = home / STATE
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def sync(home: Path = HOME, now=None, api=None) -> list:
    """One pass. Returns event records (ids, types, states; no job text). `api` overrides the HTTP layer in tests.
    Raises SyncAborted (nothing written) when the scheduler's job list or the state file cannot be trusted."""
    global _api
    if api is not None:
        _api = api
    now = dt.datetime.now(dt.timezone.utc).timestamp() if now is None else now
    state, existed = _read_state(home)                      # before anything else: never overwrite a bad file
    jobs = load_jobs(home)
    all_runs = load_runs(home)
    events = []
    if not existed:
        state = rebuild_state()
        events.append({"event": "state_rebuilt", "tracked": len(state["jobs"])})
    tracked = state["jobs"]
    tg, dc = owner_ids(home), owner_discord_dms(home)
    for jid, job in jobs.items():                          # new commitments the scheduler has accepted
        if jid in tracked or not is_agent_job(job) or not job.get("next_run_at"):
            continue
        channel = owner_origin(job, tg, dc)
        if channel is None:
            continue
        once = one_shot(job)
        try:
            goal = create_goal(job, channel, once)
        except (urllib.error.HTTPError, KeyError, ValueError) as exc:
            events.append({"job": jid, "event": "create_refused", "error": type(exc).__name__})
            continue
        tracked[jid] = {"goal": goal["goalId"], "once": once, "created_ts": _ts(job.get("created_at")) or now,
                        "due_ts": _ts(job.get("next_run_at")) if once else None,
                        "status": goal.get("lifecycleState"), "rev": goal.get("revision")}
        events.append({"job": jid, "goal": goal["goalId"], "event": "created", "type": "once" if once else "routine"})
    for jid, entry in tracked.items():
        if entry.get("status") in TERMINAL:
            continue
        job_runs = None if all_runs is None else all_runs.get(jid, [])
        target, reason = desired(entry, jobs.get(jid), job_runs, now)
        if target == HOLD:
            if entry.get("held") != reason:
                entry["held"] = reason
                events.append({"job": jid, "goal": entry["goal"], "event": "held", "reason": reason})
            continue
        entry.pop("held", None)
        if target == entry.get("status"):
            continue
        try:
            for action in PATH.get((entry.get("status"), target), []):
                goal = transition(entry["goal"], action, reason, jid, entry.get("rev"))
                entry["status"] = goal.get("lifecycleState", entry["status"])
                entry["rev"] = goal.get("revision", entry.get("rev"))
        except (urllib.error.HTTPError, KeyError, ValueError) as exc:
            events.append({"job": jid, "goal": entry["goal"], "event": "transition_refused",
                           "error": type(exc).__name__})
            continue
        events.append({"job": jid, "goal": entry["goal"], "event": target.lower()})
    if all_runs is not None:                               # the polling gap, made visible
        known = set(tracked) | set(jobs)
        recent = {j for j, rs in all_runs.items() if j not in known
                  and any((r[1] or r[2] or 0) >= now - 86400 for r in rs)}
        state["unattributed_runs_24h"] = len(recent)
    _write_state(home, state)
    return events


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        events = sync()
    except SyncAborted as exc:
        print("commitment_sync ABORTED (nothing written): %s" % exc)
        return 2
    except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
        print("commitment_sync FAILED: %s" % type(exc).__name__)
        return 1
    if "--verbose" in argv:
        for e in events:
            print(json.dumps(e, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
