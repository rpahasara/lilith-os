#!/usr/bin/env python3
"""P-4 P4-5a: E-7 reading of LILITH's commitments (read-only; counts only; never prints titles or text).

Sources (all existing):
- the Goals store: `commitment.once` / `commitment.routine` goals (GET /os/goals) and their transitions
  (goal_trace, read-only from the Core API database) - the commitment sync writes both (P4-4);
- the sync state file: runs that belong to no tracked job (`unattributed_runs_24h`) and held commitments;
- the router trace (decisions.log): the unbacked-promise shadow flags on turn-end records (P4-4b).

One-time commitments, by outcome:
    kept_on_time   COMPLETED without ever being BLOCKED (missed)
    kept_late      COMPLETED after a BLOCKED (missed) period
    failed         FAILED
    missed_open    BLOCKED now (due, not run)
    cancelled      CANCELLED
    open           PENDING / ACTIVE / SUSPENDED
Delivery evidence on kept ones (from the sync's own reasons): no_error_recorded | not_verified.
E-7 rate = kept / (kept + failed + missed_open). E-7 pass bar: >= 0.9 and no duplicate goals per scheduler job.
"Acknowledged" (a missed commitment owned in conversation) is not measured yet and is not counted as kept.

    sudo -u lilith python3 commitment_outcomes.py --db ~/.hermes/lilith-os/data/lilith.db --home ~/.hermes [--days 30]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path


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


def classify(goal: dict, trace: list) -> tuple:
    """(outcome, delivery) for one commitment.once goal. `trace` = [(new_state, reason)] in order."""
    state = goal.get("lifecycleState")
    was_blocked = any(s == "BLOCKED" for s, _ in trace)
    if state == "COMPLETED":
        reason = next((r for s, r in reversed(trace) if s == "COMPLETED"), "") or ""
        delivery = "no_error_recorded" if "no delivery error" in reason else "not_verified"
        return ("kept_late" if was_blocked else "kept_on_time"), delivery
    if state == "FAILED":
        return "failed", None
    if state == "BLOCKED":
        return "missed_open", None
    if state == "CANCELLED":
        return "cancelled", None
    return "open", None


def summarize(goals: list, traces: dict, sync_state: dict, promise_records: list, now: float, days: int = 30) -> dict:
    since = now - days * 86400
    once = [g for g in goals if g.get("type") == "commitment.once" and (_ts(g.get("createdAt")) or now) >= since]
    routine = [g for g in goals if g.get("type") == "commitment.routine"]
    outcomes, delivery = Counter(), Counter()
    by_week = defaultdict(Counter)
    for g in once:
        o, d = classify(g, traces.get(g["goalId"], []))
        outcomes[o] += 1
        if d:
            delivery[d] += 1
        iso = dt.datetime.fromtimestamp(_ts(g.get("createdAt")) or now, dt.timezone.utc).isocalendar()
        by_week["%d-W%02d" % (iso[0], iso[1])][o] += 1
    targets = Counter((g.get("target") or {}).get("id") for g in goals if (g.get("target") or {}).get("id"))
    kept = outcomes["kept_on_time"] + outcomes["kept_late"]
    due = kept + outcomes["failed"] + outcomes["missed_open"]
    rate = round(kept / due, 3) if due else None
    dupes = sum(1 for n in targets.values() if n > 1)
    flags = Counter()
    for r in promise_records:
        for k in ("promise", "scheduling_claim", "scheduled", "unbacked_promise"):
            flags[k] += int(bool(r.get(k)))
    flags["turns_checked"] = len(promise_records)
    jobs = (sync_state or {}).get("jobs", {})
    return {
        "window_days": days, "one_time": dict(outcomes, total=len(once)), "by_week": {w: dict(c) for w, c in
                                                                                       sorted(by_week.items())},
        "delivery_evidence_on_kept": dict(delivery),
        "routine": dict(Counter(g.get("lifecycleState") for g in routine), total=len(routine)),
        "e7_rate": rate, "duplicate_goals_per_job": dupes,
        "e7_gate": None if rate is None else ("PASS" if rate >= 0.9 and dupes == 0 else "BELOW_BAR"),
        "sync": {"tracked": len(jobs), "held": sum(1 for e in jobs.values() if e.get("held")),
                 "unattributed_runs_24h": (sync_state or {}).get("unattributed_runs_24h")},
        "promises": dict(flags),
        "note": "counts only; kept = scheduled run completed (receipt not verified); acknowledgement of missed "
                "commitments not yet measured",
    }


def load_goals(api: str) -> list:
    out = []
    for t in ("commitment.once", "commitment.routine"):
        with urllib.request.urlopen(api.rstrip("/") + "/os/goals?limit=200&type=" + t, timeout=10) as r:
            out += json.loads(r.read().decode("utf-8")).get("goals", [])
    return out


def load_traces(db: Path, goal_ids: list) -> dict:
    out = defaultdict(list)
    if not goal_ids:
        return out
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
    try:
        marks = ",".join("?" * len(goal_ids))
        for gid, state, reason in con.execute(
                f"SELECT goal_id, new_state, reason FROM goal_trace WHERE goal_id IN ({marks}) ORDER BY id", goal_ids):
            out[gid].append((state, reason))
    finally:
        con.close()
    return out


def load_promise_records(home: Path, since: float) -> list:
    recs = []
    for name in ("decisions.log.1", "decisions.log"):
        try:
            lines = (home / "lilith_router" / name).read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for ln in lines:
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if r.get("lane") == "turn" and "unbacked_promise" in r and float(r.get("ts") or 0) >= since:
                recs.append(r)
    return recs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default=os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes"))
    ap.add_argument("--db", required=True)
    ap.add_argument("--api", default=os.environ.get("LILITH_OS_API_URL", "http://127.0.0.1:8765"))
    ap.add_argument("--days", type=int, default=30)
    a = ap.parse_args(argv)
    now, home = time.time(), Path(a.home)
    goals = load_goals(a.api)
    try:
        state = json.loads((home / "commitments" / "sync.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = None
    print(json.dumps(summarize(goals, load_traces(Path(a.db), [g["goalId"] for g in goals]), state,
                               load_promise_records(home, now - a.days * 86400), now, a.days), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
