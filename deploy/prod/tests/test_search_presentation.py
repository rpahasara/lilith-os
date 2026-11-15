"""Conversation-search presentation (2026-11-15 Timeline replay finding, presentation.py).

Both replay arms told the owner "you first told me on 19 October" for a message sent 2026-10-19 21:00 UTC, which was
20 Oct 02:30 in Asia/Colombo, and both pasted "@session:default/syn-1019" into the reply.
"""
import datetime as dt
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_owner_memory import ROOT  # noqa: E402

sys.path.insert(0, str(ROOT / "deploy/prod"))
from lilith_router import gateway_integration as gi  # noqa: E402
from lilith_router import presentation as pr  # noqa: E402
from lilith_router import timeline as tl  # noqa: E402

OCT19_UTC_2100 = dt.datetime(2026, 10, 19, 21, 0, tzinfo=dt.timezone.utc).timestamp()
Q6_REPLY = ("You first told me on **20 October 2026**, saying, “moving to Manchester tomorrow!” Then later that "
            "day you confirmed: “I live in Manchester now, update that.”\n\n"
            "That conversation is @session:default/syn-1019.")


def no_hermes_time():
    return mock.patch.dict(sys.modules, {"hermes_time": None})        # import fails: env / UTC fallback


class ZonedTimestampTests(unittest.TestCase):
    def test_oct19_utc_is_oct20_in_colombo(self):
        with no_hermes_time(), mock.patch.dict("os.environ", {"HERMES_TIMEZONE": "Asia/Colombo"}):
            self.assertEqual(pr.zoned_timestamp(OCT19_UTC_2100), "October 20, 2026 at 02:30 AM (Asia/Colombo)")
            self.assertEqual(pr.zoned_timestamp(str(OCT19_UTC_2100)), "October 20, 2026 at 02:30 AM (Asia/Colombo)")

    def test_without_a_zone_it_is_utc_and_says_so(self):
        with no_hermes_time(), mock.patch.dict("os.environ", {"HERMES_TIMEZONE": ""}):
            self.assertEqual(pr.zoned_timestamp(OCT19_UTC_2100), "October 19, 2026 at 09:00 PM (UTC)")

    def test_hermes_own_resolver_wins(self):
        from zoneinfo import ZoneInfo
        fake = types.SimpleNamespace(get_timezone=lambda: ZoneInfo("Asia/Colombo"))
        with mock.patch.dict(sys.modules, {"hermes_time": fake}), mock.patch.dict("os.environ", {"HERMES_TIMEZONE": ""}):
            self.assertTrue(pr.zoned_timestamp(OCT19_UTC_2100).startswith("October 20, 2026"))

    def test_same_contract_as_hermes(self):
        self.assertEqual(pr.zoned_timestamp(None), "unknown")
        self.assertEqual(pr.zoned_timestamp("2026-10-19T21:00:00Z"), "2026-10-19T21:00:00Z")   # non-numeric: as is
        self.assertEqual(pr.zoned_timestamp("yesterday"), "yesterday")

    def test_search_date_and_timeline_stored_date_agree(self):
        # told-on (search) and stored-on (timeline) are the same calendar day for the same instant, in one zone
        with no_hermes_time(), mock.patch.dict("os.environ", {"HERMES_TIMEZONE": "Asia/Colombo"}):
            tz, _ = tl.zone()
            self.assertEqual(tl._day("2026-10-19T21:00:00Z", tz), "2026-10-20")
            self.assertTrue(pr.zoned_timestamp(OCT19_UTC_2100).startswith("October 20, 2026"))


class InstallTests(unittest.TestCase):
    def fake_tool(self):
        mod = types.ModuleType("fake_session_search_tool")
        exec("def _format_timestamp(ts):\n    return 'host-local'\n"
             "def when(meta):\n    return _format_timestamp(meta['started_at'])\n"
             "def _shape_message(m, anchor_id=None, max_content_len=None):\n"
             "    return {'id': m.get('id'), 'role': m.get('role'), 'content': m.get('content'),"
             " 'timestamp': m.get('timestamp')}\n"
             "def scroll(rows):\n    return [_shape_message(m, anchor_id=1) for m in rows]\n", mod.__dict__)
        return mod

    def test_message_results_keep_the_raw_epoch_and_gain_a_zoned_when(self):
        mod = self.fake_tool()
        rows = [{"id": 1, "role": "user", "content": "moving to Manchester tomorrow!", "timestamp": OCT19_UTC_2100},
                {"id": 2, "role": "assistant", "content": "Big move!"}]
        with no_hermes_time(), mock.patch.dict("os.environ", {"HERMES_TIMEZONE": "Asia/Colombo"}):
            pr.install_session_search_dates(mod)
            pr.install_session_search_dates(mod)                           # wrapped once, not twice
            out = mod.scroll(rows)
        self.assertEqual(out[0]["timestamp"], OCT19_UTC_2100)              # raw UTC epoch unchanged
        self.assertEqual(out[0]["when"], "October 20, 2026 at 02:30 AM (Asia/Colombo)")
        self.assertNotIn("when", out[1])                                  # no timestamp, no invented date
        self.assertTrue(getattr(mod._shape_message, "__wrapped__", None))
        self.assertFalse(hasattr(mod._shape_message.__wrapped__, "__wrapped__"))

    def test_tool_callers_get_the_zoned_date_and_storage_is_untouched(self):
        mod = self.fake_tool()
        meta = {"started_at": OCT19_UTC_2100}
        with no_hermes_time(), mock.patch.dict("os.environ", {"HERMES_TIMEZONE": "Asia/Colombo"}):
            self.assertTrue(pr.install_session_search_dates(mod))
            self.assertEqual(mod.when(meta), "October 20, 2026 at 02:30 AM (Asia/Colombo)")
        self.assertEqual(meta["started_at"], OCT19_UTC_2100)              # the stored UTC epoch is unchanged

    def test_idempotent_and_fail_open(self):
        mod = self.fake_tool()
        pr.install_session_search_dates(mod)
        pr.install_session_search_dates(mod)
        self.assertIs(mod._format_timestamp, pr.zoned_timestamp)
        self.assertFalse(pr.install_session_search_dates(types.ModuleType("no_formatter")))
        with mock.patch.dict(sys.modules, {"tools.session_search_tool": None}):
            self.assertFalse(pr.install_session_search_dates())            # import fails: no change, no raise

    def test_route_turn_installs_it(self):
        src = (ROOT / "deploy/prod/lilith_router/gateway_integration.py").read_text(encoding="utf-8")
        body = src[src.index("def route_turn("):src.index("def _with_fallback_chain(")]
        self.assertIn("_presentation.install_session_search_dates()", body)


class SessionLinkTests(unittest.TestCase):
    def test_q6_reply_loses_the_reference_and_keeps_the_answer(self):
        out = pr.strip_session_links(Q6_REPLY)
        self.assertNotIn("@session", out)
        self.assertIn("20 October 2026", out)
        self.assertIn("I live in Manchester now", out)
        self.assertNotIn("That conversation is", out)

    def test_mid_sentence_and_backticked_references(self):
        out = pr.strip_session_links("Found it. That's `@session:work/20260722_204335_d62c16` — want me to pick it up? "
                                     "You said Leeds.")
        self.assertEqual(out, "Found it. You said Leeds.")

    def test_reply_without_references_is_returned_as_is(self):
        text = "You were living in Leeds."
        self.assertIs(pr.strip_session_links(text), text)
        self.assertIsNone(pr.strip_session_links(None))

    def test_never_an_empty_reply(self):
        self.assertEqual(pr.strip_session_links("@session:default/x"), "@session:default/x")
        self.assertEqual(pr.strip_session_links("See @session:default/x"), "See")

    def test_enforce_reply_strips_on_every_turn_even_when_the_guard_does_not_apply(self):
        ctx = types.SimpleNamespace(source=None, message="when did I tell you?")
        disabled = types.SimpleNamespace(enabled=False)
        with mock.patch.object(gi._config, "load", return_value=disabled):
            self.assertNotIn("@session", gi.enforce_reply(Q6_REPLY, ctx))
        with mock.patch.object(gi._config, "load", side_effect=RuntimeError("boom")):
            self.assertNotIn("@session", gi.enforce_reply(Q6_REPLY, ctx))      # fail-open still strips


if __name__ == "__main__":
    unittest.main()
