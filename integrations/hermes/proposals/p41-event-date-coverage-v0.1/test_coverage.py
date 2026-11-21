"""Offline tests for coverage.py. TEST_ONLY synthetic texts. python -m unittest discover -s <this dir> -p "test_*.py"."""
import contextlib
import datetime as dt
import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

spec = importlib.util.spec_from_file_location("coverage_p41", Path(__file__).with_name("coverage.py"))
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
COL = ZoneInfo("Asia/Colombo")
DAY = dt.date(2026, 11, 12)


class ClassifyTests(unittest.TestCase):
    def test_classes(self):
        cases = {
            "On 2026-11-09, TEST_ONLY passed the mock exam.": "event_dated",
            "TEST_ONLY started the new job on 3 November 2026.": "event_dated",
            "TEST_ONLY moved to Kandy on November 1, 2026.": "event_dated",
            "Told LILITH on 2026-11-12: TEST_ONLY has a sister.": "told_on",
            "Told LILITH on 2026-11-12: TEST_ONLY got the offer recently.": "told_on",
            "TEST_ONLY passed the exam yesterday.": "relative",
            "TEST_ONLY moved flats the other day.": "relative",
            "TEST_ONLY plays the violin.": "undated",
            "Preference (casual): keep replies short.": "preference",
            "Boundary (global): never mention TEST_ONLY.": "preference",
        }
        for text, want in cases.items():
            with self.subTest(text=text):
                self.assertEqual(C.classify(text, DAY)[0], want)

    def test_flags(self):
        self.assertEqual(C.classify("On 2026-11-12, TEST_ONLY submitted it.", DAY), ("event_dated", {"event_date_equals_review_day"}))
        self.assertEqual(C.classify("Told LILITH on 2026-11-12: TEST_ONLY passed on 2026-11-10.", DAY),
                         ("event_dated", {"also_told_on"}))
        self.assertEqual(C.classify("Told LILITH on 2026-11-12: TEST_ONLY moved last week.", DAY),
                         ("told_on", {"relative_kept_with_told_on"}))

    def test_told_on_date_is_never_an_event_date(self):
        cls, flags = C.classify("Told LILITH on 2026-11-12: TEST_ONLY likes tea.", DAY)
        self.assertEqual((cls, flags), ("told_on", set()))


class PhrasingTests(unittest.TestCase):
    """Phrasings the review model is likely to write (2026-11-11 probe; the first version missed most of these)."""

    def test_realistic_phrasings(self):
        cases = {
            "On 3 November, TEST_ONLY passed.": ("event_dated", set()),               # the guidance's own example
            "On 3rd November 2026, TEST_ONLY passed.": ("event_dated", set()),
            "On Nov 3, TEST_ONLY passed.": ("event_dated", set()),
            "On 9 Nov 2026, TEST_ONLY moved.": ("event_dated", set()),
            "On Monday, 9 November, TEST_ONLY passed.": ("event_dated", set()),
            "TEST_ONLY moved two weeks ago.": ("relative", set()),
            "TEST_ONLY started a few days ago.": ("relative", set()),
            "TEST_ONLY visited Kandy this past weekend.": ("relative", set()),
            "TEST_ONLY passed on Monday.": ("relative", set()),
            "Told Lilith on 12 November: TEST_ONLY has a sister.": ("told_on", set()),
            "In 2024 TEST_ONLY lived in Leeds.": ("event_dated", {"partial_date"}),
            "On 12 Nov, TEST_ONLY submitted it.": ("event_dated", {"event_date_equals_review_day"}),
            "TEST_ONLY may visit soon.": ("undated", set()),
        }
        for text, want in cases.items():
            with self.subTest(text=text):
                self.assertEqual(C.classify(text, DAY), want)

    def test_year_less_dates_never_land_in_the_future(self):
        self.assertEqual(C._iso("20 December", DAY), dt.date(2025, 12, 20))
        self.assertEqual(C._iso("3rd Nov", DAY), dt.date(2026, 11, 3))


class MeasureTests(unittest.TestCase):
    EVENTS = [
        {"kind": "PROPOSED", "proposal_id": "p1", "text": "On 2026-11-11, TEST_ONLY passed.", "at": "2026-11-12T16:31:00+00:00"},
        {"kind": "PROPOSED", "proposal_id": "p1", "text": "Told LILITH on 2026-11-12: TEST_ONLY has a dog.", "at": "2026-11-12T16:31:00+00:00"},
        {"kind": "PROPOSED", "proposal_id": "p2", "text": "Preference (global): short replies.", "at": "2026-11-12T16:32:00Z"},
        {"kind": "PROPOSED", "proposal_id": "p3", "text": "TEST_ONLY moved yesterday.", "at": "2026-11-12T16:33:00+00:00"},
        {"kind": "PROPOSED", "proposal_id": "old", "text": "TEST_ONLY before the cutoff.", "at": "2026-11-01T16:30:00+00:00"},
        {"kind": "APPROVED", "proposal_id": "p1", "text": "On 2026-11-11, TEST_ONLY passed.", "at": "2026-11-13T05:00:00+00:00"},
    ]

    def test_counts_only_and_cutoff(self):
        out = C.measure(self.EVENTS, dt.datetime(2026, 11, 12, tzinfo=dt.timezone.utc), COL)
        self.assertEqual(out["proposals"], 3)
        self.assertEqual(out["items"], 4)
        self.assertEqual(out["counts"], {"event_dated": 1, "preference": 1, "relative": 1, "told_on": 1})
        self.assertEqual(out["fact_items_with_any_date"], "2/3")
        self.assertEqual(out["TEXT_PRINTED"], 0)
        blob = json.dumps(out)
        for e in self.EVENTS:
            self.assertNotIn(e["text"], blob)
            self.assertNotIn("TEST_ONLY", blob)

    def test_removals_are_counted_apart(self):
        ev = self.EVENTS[:1] + [{"kind": "PROPOSED", "proposal_id": "p9", "text": "TEST_ONLY old fact.", "at": "2026-11-12T16:31:00Z",
                                 "detail": "remove"}]
        out = C.measure(ev, dt.datetime(2026, 11, 12, tzinfo=dt.timezone.utc), COL)
        self.assertEqual((out["items"], out["counts"].get("removals")), (1, 1))

    def test_review_day_is_the_colombo_day(self):
        # 2026-11-12T18:40Z is 13 Nov in Colombo: an event dated 13 Nov is flagged, 12 Nov is not
        ev = [{"kind": "PROPOSED", "proposal_id": "x", "text": "On 2026-11-13, TEST_ONLY a.", "at": "2026-11-12T18:40:00+00:00"},
              {"kind": "PROPOSED", "proposal_id": "y", "text": "On 2026-11-12, TEST_ONLY b.", "at": "2026-11-12T18:40:00+00:00"}]
        out = C.measure(ev, dt.datetime(2026, 11, 12, tzinfo=dt.timezone.utc), COL)
        self.assertEqual(out["flags"], {"event_date_equals_review_day": 1})

    def test_main_prints_one_json_line_without_text(self):
        class R:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps({"events": MeasureTests.EVENTS}).encode()
        buf = io.StringIO()
        with mock.patch.object(C.urllib.request, "urlopen", return_value=R()), contextlib.redirect_stdout(buf):
            C.main(["--since", "2026-11-12T00:00:00+00:00"])
        out = buf.getvalue().strip().splitlines()
        self.assertEqual(len(out), 1)
        self.assertNotIn("TEST_ONLY", out[0])
        self.assertEqual(json.loads(out[0])["items"], 4)


if __name__ == "__main__":
    unittest.main()
