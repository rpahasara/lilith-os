"""Offline tests for tz_ops.py's pure parts. TEST_ONLY. python -m unittest discover -s <this dir> -p "test_*.py"."""
import contextlib
import datetime as dt
import importlib.util
import io
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("tz_ops", Path(__file__).with_name("tz_ops.py"))
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)
UTC = dt.timezone.utc
CONFIG = """model:
  default: x
compression:
  enabled: true
platform_toolsets:
  telegram: [a, b]
_config_version: 7
"""


def job(jid, name, kind="cron", expr=None, enabled=True, next_run="2026-11-10T16:30:00+00:00", run_at=None, last=None):
    return {"id": jid, "name": name, "enabled": enabled, "schedule": {"kind": kind, "expr": expr, "run_at": run_at},
            "next_run_at": next_run, "last_run_at": last}


def prod_jobs():
    return [job(j, n, k, e) for j, (n, k, e) in T.EXPECTED_JOBS.items()] + [
        job("7e481025f885", "Drink water reminder", "once", enabled=False, next_run=None,
            run_at="2026-11-09T07:08:18.415035+00:00", last="2026-11-09T07:08:55.407185+00:00")]


def refuses(fn, *a):
    with contextlib.redirect_stdout(io.StringIO()) as out, unittest.TestCase().assertRaises(SystemExit):
        fn(*a)
    return out.getvalue()


class ConfigTests(unittest.TestCase):
    def test_appends_one_top_level_line_and_changes_nothing_else(self):
        new = T.config_with_zone(CONFIG)
        self.assertEqual(new, CONFIG + "timezone: Asia/Colombo\n")
        before, _ = T.config_timezone(CONFIG)
        after, tz = T.config_timezone(new)
        self.assertEqual(tz, "Asia/Colombo")
        self.assertEqual({k: v for k, v in after.items() if k != "timezone"}, before)

    def test_file_without_trailing_newline(self):
        self.assertEqual(T.config_with_zone(CONFIG.rstrip("\n")), CONFIG + "timezone: Asia/Colombo\n")

    def test_refuses_an_existing_timezone(self):
        self.assertIn("already has a timezone", refuses(T.config_with_zone, CONFIG + "timezone: UTC\n"))

    def test_refuses_when_the_tail_is_inside_a_block(self):
        # a trailing block scalar would swallow the appended line: the deep compare catches it
        self.assertIn("changed another key", refuses(T.config_with_zone, "note: |\n  free text"))


class JobSetTests(unittest.TestCase):
    def test_prod_inventory_passes(self):
        T.jobs_check(prod_jobs())

    def test_review_schedule_may_be_either_value(self):
        jobs = prod_jobs(); jobs[0]["schedule"]["expr"] = T.REVIEW_NEW
        T.jobs_check(jobs)

    def test_refusals(self):
        cases = {
            "missing": lambda js: js.pop(1),
            "extra enabled reminder": lambda js: js.append(job("abc", "TEST_ONLY", "once", next_run="2026-11-12T20:00:00+00:00")),
            "naive next run": lambda js: js[2].update(next_run_at="2026-11-10T16:31:00"),
            "naive one-shot": lambda js: js[3]["schedule"].update(run_at="2026-11-09T07:08:18"),
            "changed expr": lambda js: js[1]["schedule"].update(expr="*/5 * * * *"),
            "disabled": lambda js: js[2].update(enabled=False),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                js = prod_jobs(); mutate(js)
                refuses(T.jobs_check, js)


class InstantTests(unittest.TestCase):
    def test_next_review_is_always_16_30_utc(self):
        for now, want in (("2026-11-10T05:00:00", "2026-11-10T16:30:00"), ("2026-11-10T16:30:00", "2026-11-11T16:30:00"),
                          ("2026-11-10T16:29:59", "2026-11-10T16:30:00"), ("2026-11-10T23:59:00", "2026-11-11T16:30:00")):
            got = T.next_review_utc(dt.datetime.fromisoformat(now).replace(tzinfo=UTC))
            self.assertEqual(got, dt.datetime.fromisoformat(want).replace(tzinfo=UTC), now)

    def test_22_00_colombo_is_16_30_utc_all_year(self):
        from zoneinfo import ZoneInfo
        for month in range(1, 13):                       # Sri Lanka has no DST: +05:30 every day
            t = dt.datetime(2026, month, 15, 22, 0, tzinfo=ZoneInfo("Asia/Colombo"))
            self.assertEqual((t.astimezone(UTC).hour, t.astimezone(UTC).minute), (16, 30))

    def test_ten_minute_and_minute_grids_coincide(self):
        # +05:30 is a whole number of 10-minute steps, so */10 and * * * * * fire at the same UTC instants
        self.assertEqual((5 * 60 + 30) % 10, 0)


if __name__ == "__main__":
    unittest.main()
