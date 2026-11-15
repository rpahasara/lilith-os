"""Natural reminder / follow-up routing (2026-11-15).

The assessment found 8 of 10 everyday reminder phrasings stayed on the lean (tool-less) path, where any "I'll ping you"
is a promise nothing backs. They now leave the fast path for the full agent, which has Hermes' scheduler, and the
agent's turn hint carries the scheduler rules (ask when unclear, confirm before saying it's set, this chat only).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_owner_memory import ROOT  # noqa: E402

sys.path.insert(0, str(ROOT / "deploy/prod"))
from lilith_router import social_lean as sl  # noqa: E402
from lilith_router import turn_context as tc  # noqa: E402

REMINDERS = [
    "Remind me at 6 to call mum",
    "set a timer for 20 minutes",
    "ping me tomorrow morning about the CKA",
    "check in on me later tonight",
    "follow up with me on this tomorrow",
    "nudge me in an hour to stretch",
    "let me know at 9 if it's raining",
    "tell me again tomorrow",
    "text me when it's time",
    "wake me up at 7",
]
AMBIGUOUS = ["ping me later", "remind me sometime", "nudge me about the CKA", "check in on me", "follow up with me"]
ORDINARY = [
    "she pinged me yesterday",
    "I'll follow up with my manager tomorrow",
    "let me know what you think",
    "tell me a joke",
    "how was your day?",
    "he keeps texting me",
    "text me memes lol",
    "I'll go to the gym later",
    "tell me about your day",
    "my sister checked in on me yesterday",
]


class ReminderRoutingTests(unittest.TestCase):
    def test_every_reminder_phrasing_leaves_the_fast_path_and_marks_the_turn(self):
        for m in REMINDERS:
            self.assertIn(sl.skip_reason(m), ("action_intent", "reminder_request"), m)
            self.assertTrue(sl.reminder_request(m), m)

    def test_the_eight_natural_phrasings_are_traced_as_reminder_requests(self):
        for m in REMINDERS[2:]:
            self.assertEqual(sl.skip_reason(m), "reminder_request", m)

    def test_ambiguous_requests_reach_the_agent_with_the_ask_first_rule(self):
        for m in AMBIGUOUS:
            self.assertNotEqual(sl.skip_reason(m), "", m)
            self.assertTrue(sl.reminder_request(m), m)
        self.assertIn("If the time or what to remind them about is unclear, ask first; never pick a time for them",
                      tc.REMINDER_NOTE)

    def test_ordinary_conversation_stays_lean_and_gets_no_note(self):
        for m in ORDINARY:
            self.assertEqual(sl.skip_reason(m), "", m)
            self.assertFalse(sl.reminder_request(m), m)

    def test_mentions_of_reminders_or_alarms_get_no_scheduler_note(self):
        for m in ("my alarm woke me up at 7 lol", "the reminder app is buggy", "I set my own alarm already"):
            self.assertFalse(sl.reminder_request(m), m)

    def test_note_is_honest_about_capability(self):
        note = tc.REMINDER_NOTE
        self.assertIn("only your scheduler (the cronjob tool) can do that, and it delivers here, in this chat", note)
        self.assertIn("Say it's set only after the scheduler confirms it; if it fails, say so", note)
        self.assertIn("Don't offer texts, calls, alarms or anything outside this chat", note)

    def test_note_rides_on_the_owner_agent_hint_only(self):
        owner = tc.TurnContext(owner=True, reminder=True)
        self.assertIn(tc.REMINDER_NOTE, tc.agent_hint(owner))
        self.assertNotIn(tc.REMINDER_NOTE, tc.lean_suffix(owner))                  # never on the lean path
        self.assertIsNone(tc.agent_hint(tc.TurnContext(owner=False, reminder=True)))
        self.assertNotIn(tc.REMINDER_NOTE, tc.agent_hint(tc.TurnContext(owner=True, reminder=False)) or "")

    def test_gateway_sets_the_flag_every_routed_turn(self):
        src = (ROOT / "deploy/prod/lilith_router/gateway_integration.py").read_text(encoding="utf-8")
        body = src[src.index("def _route_turn_impl("):]
        self.assertIn("tctx.reminder = _social_lean.reminder_request(message)", body)


if __name__ == "__main__":
    unittest.main()
