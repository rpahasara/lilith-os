"""E-T4 and D1 (2026-11-08).

E-T4: "what am I working toward right now?" took the right route and read the goals, but the model let a casual
weekend plan from the previous turn outweigh the durable goals. The instruction now also rides on the current
message (API-only turn hint), owner turns only; the goal read is owner-only too.

D1: when the social guard replaced a reply, the stored transcript kept the rejected one (and its provider replay
items). The stored row now says what the user saw.
"""
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_owner_memory import ROOT, RUN_PY  # noqa: E402

sys.path.insert(0, str(ROOT / "deploy/prod"))
from lilith_router import config as cfgmod  # noqa: E402
from lilith_router import gateway_integration as gi  # noqa: E402


class SelfStatusTests(unittest.TestCase):
    def route(self, owner):
        cfg = mock.Mock(spec=cfgmod.RouterConfig)
        cfg.goals_is_live.return_value = True
        grounding = mock.Mock(return_value=("- GOAL 1: pass the CKA\nother line", None))
        with mock.patch.object(gi._canonical_memory, "owner_turn", return_value=owner), \
                mock.patch.object(gi, "_note_social_route"), \
                mock.patch.object(gi._world_context, "build_goal_grounding", grounding):
            out = gi._self_status_route(None, cfg, "telegram", "1", "telegram:1", {"model": "m"}, "base", None,
                                        "social")
        return out, grounding

    def test_owner_gets_goals_and_the_hint(self):
        out, grounding = self.route(True)
        grounding.assert_called_once()
        self.assertEqual(grounding.call_args.kwargs["do_write"], False)
        self.assertIn("- GOAL 1: pass the CKA", out["combined_ephemeral"])
        self.assertNotIn("other line", out["combined_ephemeral"])
        self.assertEqual(out["self_status_hint"], gi.SELF_STATUS_HINT)

    def test_non_owner_gets_neither_the_owner_goals_nor_the_hint(self):
        out, grounding = self.route(False)
        grounding.assert_not_called()
        self.assertIn(gi.SELF_STATUS_NOTE, out["combined_ephemeral"])
        self.assertNotIn("self_status_hint", out)

    def test_hint_becomes_the_turn_hint_and_replaces_a_tone_note(self):
        ctx = gi._tc.begin("telegram_owner_dm", True)
        ctx.style = gi._tc.directive(("playful",), focused=False)
        tone = gi._tc.tone_text(ctx)
        with mock.patch.object(gi._canonical_memory, "owner_turn", return_value=True):
            out = gi._with_social_note({"self_status_hint": gi.SELF_STATUS_HINT})
            self.assertEqual(out, {"turn_hint": gi.SELF_STATUS_HINT})
            self.assertEqual(gi._with_social_note({})["turn_hint"], tone)               # other turns unchanged
        with mock.patch.object(gi._canonical_memory, "owner_turn", return_value=False):
            self.assertEqual(gi._with_social_note({"self_status_hint": gi.SELF_STATUS_HINT}), {})
        gi._tc.begin()

    def test_hint_wording_targets_the_observed_failure(self):
        h = gi.SELF_STATUS_HINT
        for phrase in ("ongoing goals", "not today's or this weekend's plans", "Lead with those", "second person"):
            self.assertIn(phrase, h)

    def test_pattern_still_matches_the_test_question_only(self):
        self.assertTrue(gi._SELF_STATUS_RE.search("what am I working toward right now?"))
        self.assertFalse(gi._SELF_STATUS_RE.search("my only goal this weekend is relaxing"))
        self.assertFalse(gi._SELF_STATUS_RE.search("what's my plan for dinner?"))


class FakeDB:
    COLS = ["id", "session_id", "role", "content", "tool_calls", "active", "api_content", "codex_message_items",
            "codex_reasoning_items", "reasoning", "reasoning_content", "reasoning_details", "finish_reason"]

    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, "
                          "tool_calls TEXT, active INTEGER, api_content TEXT, codex_message_items TEXT, "
                          "codex_reasoning_items TEXT, reasoning TEXT, reasoning_content TEXT, "
                          "reasoning_details TEXT, finish_reason TEXT)")

    def add(self, sid, role, content, tool_calls=None, active=1):
        self.conn.execute("INSERT INTO messages (session_id, role, content, tool_calls, active, api_content, "
                          "codex_message_items, codex_reasoning_items, reasoning, reasoning_content, "
                          "reasoning_details, finish_reason) VALUES (?,?,?,?,?,'a','[m]','[r]','x','y','[d]','stop')",
                          (sid, role, content, tool_calls, active))

    def _execute_write(self, fn):
        out = fn(self.conn)
        self.conn.commit()
        return out

    def _message_column_names(self, conn):
        return list(self.COLS)

    def rows(self, sid):
        return self.conn.execute("SELECT role, content, codex_message_items, api_content, reasoning_content, "
                                 "finish_reason FROM messages WHERE session_id = ? ORDER BY id", (sid,)).fetchall()


class DeliveredReplyTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        self.db.add("s1", "user", "hey you")
        self.db.add("s1", "assistant", "As an AI, I don't have feelings, but hi!")
        self.db.add("s2", "assistant", "As an AI, I don't have feelings, but hi!")

    def test_rewritten_reply_replaces_the_stored_one_and_its_replay_items(self):
        wrapper = mock.Mock(_db=self.db)   # run.py passes the SessionStore wrapper
        self.assertTrue(gi.record_delivered_reply(wrapper, "s1", "As an AI, I don't have feelings, but hi!",
                                                  "hey yourself 😌"))
        self.assertEqual(self.db.rows("s1")[-1], ("assistant", "hey yourself 😌", None, None, None, "stop"))
        self.assertEqual(self.db.rows("s2")[0][1], "As an AI, I don't have feelings, but hi!")   # other session

    def test_reasoning_wrapper_difference_still_matches(self):
        self.db.add("s3", "assistant", "<think>plan</think>hello there")
        self.assertTrue(gi.record_delivered_reply(self.db, "s3", "hello there", "hi love"))
        self.assertEqual(self.db.rows("s3")[-1][1], "hi love")

    def test_never_touches_a_different_or_tool_call_row(self):
        self.assertFalse(gi.record_delivered_reply(self.db, "s1", "some other reply", "x"))
        self.db.add("s4", "assistant", "calling a tool", tool_calls='[{"id": 1}]')
        self.assertFalse(gi.record_delivered_reply(self.db, "s4", "calling a tool", "x"))
        self.assertEqual(self.db.rows("s1")[-1][1], "As an AI, I don't have feelings, but hi!")

    def test_no_change_and_bad_input_are_noops(self):
        same = "As an AI, I don't have feelings, but hi!"
        self.assertFalse(gi.record_delivered_reply(self.db, "s1", same, same))
        self.assertFalse(gi.record_delivered_reply(self.db, "s1", same, "   "))
        self.assertFalse(gi.record_delivered_reply(self.db, "", same, "x"))
        self.assertFalse(gi.record_delivered_reply(None, "s1", same, "x"))
        self.assertFalse(gi.record_delivered_reply(self.db, "s1", None, "x"))
        broken = mock.Mock(_db=mock.Mock(_execute_write=mock.Mock(side_effect=RuntimeError)))
        self.assertFalse(gi.record_delivered_reply(broken, "s1", same, "x"))

    def test_run_py_records_only_after_a_guard_change(self):
        text = RUN_PY.read_text(encoding="utf-8")
        i = text.index("_lrg_original = final_response")
        j = text.index("final_response = _lilith_router.enforce_reply(final_response, ctx)")
        k = text.index("_lilith_router.record_delivered_reply(")
        self.assertLess(i, j)
        self.assertLess(j, k)
        self.assertIn("_lrg_changed = final_response is not _lrg_original and final_response != _lrg_original", text)
        self.assertLess(text.index("if _lrg_changed:"), k)


if __name__ == "__main__":
    unittest.main()
