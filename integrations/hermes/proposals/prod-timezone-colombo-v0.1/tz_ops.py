"""PROD Hermes timezone operations for the Asia/Colombo migration (proposal; run only inside an authorized window).

Run as the `lilith` user with PROD's own interpreter, so Hermes' cron API is the one PROD runs. tz_window.sh installs
this file root-owned and read-only in a fresh /run directory and runs:
    HERMES_HOME=/home/lilith/.hermes /home/lilith/.hermes/hermes-agent/venv/bin/python -I <dir>/tz_ops.py <command>
This process never writes any file except jobs.json through Hermes' own update_job (jobs-apply / jobs-revert); every
other output goes to stdout for root to handle.

Read-only: config-check, config-render (new config on stdout), config-validate (candidate config on stdin), jobs-inspect,
jobs-plan, jobs-evidence SINCE OFFSET, datecheck.
Writing (gateway STOPPED, inside the window): jobs-apply, jobs-revert.
Never prints job prompts, reminder text, chat ids or message content.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

ZONE = "Asia/Colombo"
REVIEW_ID = "e161234245f3"
REVIEW_OLD, REVIEW_NEW = "30 16 * * *", "0 22 * * *"
EXPECTED_JOBS = {                     # id -> (name, kind, expr): the recurring jobs present on 2026-11-10
    "e161234245f3": ("lilith-nightly-memory-review", "cron", "30 16 * * *"),
    "f56407e4cef8": ("lilith-memory-proposal-snapshot", "cron", "*/10 * * * *"),
    "5365cfb456d4": ("lilith-commitment-sync", "cron", "* * * * *"),
}
UTC = dt.timezone.utc
HOME = Path(os.environ.get("HERMES_HOME", "/home/lilith/.hermes"))
SRC = HOME / "hermes-agent"


def die(msg: str) -> None:
    print(f"TZ_OPS_FAIL {msg}")
    sys.exit(1)


# -- config.yaml -----------------------------------------------------------------------------------------------------
def _yaml():
    import yaml
    return yaml


def config_timezone(text: str):
    data = _yaml().safe_load(text) or {}
    if not isinstance(data, dict):
        die("config.yaml is not a mapping")
    return data, data.get("timezone")


def config_with_zone(text: str) -> str:
    """The same file with one top-level `timezone: Asia/Colombo` line appended; every other key provably unchanged."""
    before, tz = config_timezone(text)
    if tz is not None:
        die(f"config.yaml already has a timezone key ({tz!r}); refusing to change it")
    new = text + ("" if text.endswith("\n") else "\n") + f"timezone: {ZONE}\n"
    after, tz2 = config_timezone(new)
    if tz2 != ZONE or {k: v for k, v in after.items() if k != "timezone"} != before:
        die("appending the timezone line changed another key")
    return new


# -- cron jobs -------------------------------------------------------------------------------------------------------
def _jobs_api():
    sys.path.insert(0, str(SRC))
    import hermes_time
    hermes_time.reset_cache()
    import cron.jobs as J
    return hermes_time, J


def _summary(job: dict) -> dict:
    s = job.get("schedule") or {}
    return {"id": job.get("id"), "name": job.get("name"), "enabled": job.get("enabled"), "state": job.get("state"),
            "kind": s.get("kind"), "expr": s.get("expr"), "run_at": s.get("run_at"), "display": job.get("schedule_display"),
            "next_run_at": job.get("next_run_at"), "last_run_at": job.get("last_run_at"), "last_status": job.get("last_status")}


def _aware(v) -> bool:
    return v is None or dt.datetime.fromisoformat(str(v)).tzinfo is not None


def jobs_check(jobs: list) -> None:
    """The window applies only to the inventoried job set: the three recurring jobs, nothing else enabled, all aware."""
    by_id = {j.get("id"): j for j in jobs}
    for jid, (name, kind, expr) in EXPECTED_JOBS.items():
        j = by_id.get(jid)
        if j is None or j.get("name") != name or (j.get("schedule") or {}).get("kind") != kind:
            die(f"job {jid} missing or changed")
        if jid != REVIEW_ID and (j.get("schedule") or {}).get("expr") != expr:
            die(f"job {jid} schedule changed")
        if not j.get("enabled"):
            die(f"job {jid} not enabled")
    for j in jobs:
        if j.get("id") not in EXPECTED_JOBS and j.get("enabled"):
            die(f"an unexpected enabled job exists ({j.get('id')}, kind {(j.get('schedule') or {}).get('kind')}): re-plan")
        s = j.get("schedule") or {}
        if not (_aware(j.get("next_run_at")) and _aware(s.get("run_at")) and _aware(j.get("last_run_at"))):
            die(f"job {j.get('id')} has a timezone-less timestamp: re-plan")


def next_review_utc(now: dt.datetime) -> dt.datetime:
    """The next 16:30 UTC strictly after now (the review's instant, before and after the change)."""
    t = now.astimezone(UTC).replace(hour=16, minute=30, second=0, microsecond=0)
    return t if t > now else t + dt.timedelta(days=1)


def main(argv: list[str]) -> None:
    cmd = argv[0] if argv else ""
    if cmd == "config-check":
        _, tz = config_timezone((HOME / "config.yaml").read_text(encoding="utf-8"))
        print(json.dumps({"timezone": tz}))
    elif cmd == "config-render":                 # the new config.yaml on stdout; root writes it
        sys.stdout.write(config_with_zone((HOME / "config.yaml").read_text(encoding="utf-8")))
    elif cmd == "config-validate":               # stdin = candidate; it must be the live config plus exactly the zone
        live, tz = config_timezone((HOME / "config.yaml").read_text(encoding="utf-8"))
        cand, ctz = config_timezone(sys.stdin.read())
        if tz is not None or ctz != ZONE or {k: v for k, v in cand.items() if k != "timezone"} != live:
            die("candidate config is not the live config plus timezone: Asia/Colombo")
        print("CONFIG_VALID")
    elif cmd == "jobs-evidence":                 # the LIVE scheduler wrote times in the expected zone since SINCE
        since = dt.datetime.fromisoformat(argv[1])
        offset = dt.timedelta(hours=5, minutes=30) if argv[2] == "colombo" else dt.timedelta(0)
        _, J = _jobs_api()
        j = {x["id"]: x for x in J.load_jobs()}["5365cfb456d4"]
        last = dt.datetime.fromisoformat(j["last_run_at"]) if j.get("last_run_at") else None
        nxt = dt.datetime.fromisoformat(j["next_run_at"]) if j.get("next_run_at") else None
        ok = bool(last and nxt and last >= since and nxt.utcoffset() == offset and j.get("last_status") == "ok")
        print(json.dumps({"sync_last_run_at": j.get("last_run_at"), "sync_next_run_at": j.get("next_run_at"),
                          "since": since.isoformat(), "want_offset": str(offset), "ok": ok}))
        sys.exit(0 if ok else 1)
    elif cmd == "jobs-inspect":
        _, J = _jobs_api()
        jobs = J.load_jobs()
        jobs_check(jobs)
        print(json.dumps([_summary(j) for j in jobs], indent=1))
    elif cmd == "jobs-plan":                     # read-only: what the review becomes, computed in memory under the zone
        os.environ["HERMES_TIMEZONE"] = ZONE
        ht, J = _jobs_api()
        if getattr(ht.get_timezone(), "key", None) != ZONE:
            die("zone did not resolve")
        sched = J.parse_schedule(REVIEW_NEW)
        nxt = dt.datetime.fromisoformat(J.compute_next_run(sched))
        want = next_review_utc(dt.datetime.now(UTC))
        print(json.dumps({"schedule": sched, "next_run_at": nxt.isoformat(), "next_run_utc": nxt.astimezone(UTC).isoformat(),
                          "expected_utc": want.isoformat(), "same_instant": nxt.astimezone(UTC) == want}))
        if nxt.astimezone(UTC) != want:
            die("planned review instant is not 16:30 UTC")
    elif cmd in ("jobs-apply", "jobs-revert"):
        apply = cmd == "jobs-apply"
        if apply and os.environ.get("HERMES_TIMEZONE") != ZONE:
            die("jobs-apply needs HERMES_TIMEZONE=Asia/Colombo (the zone the gateway will run with)")
        if not apply and os.environ.get("HERMES_TIMEZONE"):
            die("jobs-revert needs HERMES_TIMEZONE unset (UTC, as before)")
        _, tz = config_timezone((HOME / "config.yaml").read_text(encoding="utf-8"))
        if tz != (ZONE if apply else None):
            die(f"config.yaml timezone is {tz!r}; apply the config change first" if apply else "config.yaml still has a timezone")
        ht, J = _jobs_api()
        before = {j["id"]: j for j in J.load_jobs()}
        jobs_check(list(before.values()))
        expr = (before[REVIEW_ID].get("schedule") or {}).get("expr")
        target = REVIEW_NEW if apply else REVIEW_OLD
        if expr == target:
            print(f"JOBS_{'APPLY' if apply else 'REVERT'}_NOOP review already {target!r}")
        else:
            J.update_job(REVIEW_ID, {"schedule": target})
        after = {j["id"]: j for j in J.load_jobs()}
        review = after[REVIEW_ID]
        nxt = dt.datetime.fromisoformat(review["next_run_at"])
        want = next_review_utc(dt.datetime.now(UTC))
        offset = dt.timedelta(hours=5, minutes=30) if apply else dt.timedelta(0)
        if (review["schedule"].get("expr") != target or nxt.utcoffset() != offset or nxt.astimezone(UTC) != want):
            die(f"review after change: {review['schedule']} {review['next_run_at']} (want {want.isoformat()})")
        for jid, j in before.items():                # nothing else changed
            if jid != REVIEW_ID and after.get(jid) != j:
                die(f"job {jid} changed unexpectedly")
        changed = sorted(k for k in set(before[REVIEW_ID]) | set(review) if before[REVIEW_ID].get(k) != review.get(k))
        print(json.dumps({"review": _summary(review), "next_run_utc": nxt.astimezone(UTC).isoformat(), "changed_fields": changed}))
        print("JOBS_APPLY_OK" if apply else "JOBS_REVERT_OK")
    elif cmd == "datecheck":                         # read-only: the zone and the agent's date line under the live config
        os.environ.pop("HERMES_TIMEZONE", None)
        import inspect
        import textwrap
        ht, _ = _jobs_api()
        import agent.system_prompt as SP
        src = inspect.getsource(SP)
        a = src.index("    from hermes_time import get_timezone as _hermes_tz, now as _hermes_now")
        b = src.index("    # Bot Chat sessions", a)
        ns: dict = {}
        exec(textwrap.dedent(src[a:b]), ns)
        print(json.dumps({"zone": getattr(ht.get_timezone(), "key", None), "now": ht.now().isoformat(),
                          "date_line": ns["timestamp_line"]}))
    else:
        die("usage: config-check | config-render | config-validate | jobs-inspect | jobs-plan | jobs-evidence SINCE "
            "colombo|utc | jobs-apply | jobs-revert | datecheck")


if __name__ == "__main__":
    main(sys.argv[1:])
