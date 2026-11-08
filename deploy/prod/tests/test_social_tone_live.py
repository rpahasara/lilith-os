"""Social Cognition live tone note (owner-approved wording 2026-11-07).

A light, optional hint on OWNER turns only, on both the lean Groq reply and the full agent; public channels stay shadow.
Clues are weak signals, technical / work turns stay focused, and an explicit request beats a clue.
"""
import ast
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_owner_memory import OWNER, ROOT, RUN_PY, SETTINGS, load_router, src  # noqa: E402

sys.path.insert(0, str(ROOT / "deploy/prod"))
from lilith_router import social_cognition as sc  # noqa: E402

HEADER = ("[A light read of this message — a hint, not a script. Stay completely yourself; ignore it if the "
          "conversation clearly needs something else.]")


def note(message, focused=False):
    snap = sc.build_social_context(sc.build_social_input(message, "sc.t", "telegram"))
    return sc.tone_note(snap, focused=focused)


class ToneNoteWordingTests(unittest.TestCase):
    def test_exact_approved_wording(self):
        self.assertEqual(sc.TONE_HEADER, HEADER)
        self.assertEqual(sc.TONE_LINES, {
            "playful": "They sound playful or warm — play along in your own way if you feel like it.",
            "difficulty": "They mention something that's weighing on them — notice it with warmth; keep any "
                          "teasing gentle.",
            "mixed": "They're joking about something genuinely annoying — you can laugh with them and still take "
                     "the annoying part seriously.",
            "correction": "They're correcting you — take it on board plainly and fix it; no grovelling.",
            "support": "They're asking for comfort — lead with care, in your own words.",
            "humor": "They asked for humour — go for it.",
            "formal": "They want this one formal.",
        })

    def test_lines(self):
        self.assertEqual(note("hehe you are such a cutie ❤️"), HEADER + "\n- " + sc.TONE_LINES["playful"])
        self.assertEqual(note("long day at work, so tired"), HEADER + "\n- " + sc.TONE_LINES["difficulty"])
        self.assertIn(sc.TONE_LINES["correction"], note("no, that's wrong, I meant the other one"))
        self.assertIn(sc.TONE_LINES["support"], note("can you cheer me up"))
        self.assertIn(sc.TONE_LINES["humor"], note("make it funny please"))

    def test_mixed_signals_get_one_mixed_line(self):
        n = note("ugh this bug is killing me lol")
        self.assertIn(sc.TONE_LINES["mixed"], n)
        self.assertNotIn(sc.TONE_LINES["playful"], n)
        self.assertNotIn(sc.TONE_LINES["difficulty"], n)

    def test_quiet_messages_get_no_note(self):
        for msg in ("How do I configure an nginx reverse proxy?", "no worries, take your time",
                    "Run the tests again please", "What's the status of my job applications?"):
            with self.subTest(msg=msg):
                self.assertIsNone(note(msg))

    def test_technical_turns_stay_focused(self):
        self.assertIsNone(note("lol can you fix the nginx config \U0001f602", focused=True))     # emoji is not a mood
        self.assertIsNone(note("ugh this bug is killing me lol", focused=True))
        self.assertIn(sc.TONE_LINES["correction"], note("actually, use port 8080 instead lol", focused=True))

    def test_explicit_formality_beats_a_playful_clue(self):
        n = note("haha my manager wants a status email, keep it formal")
        self.assertIn(sc.TONE_LINES["formal"], n)
        self.assertNotIn(sc.TONE_LINES["playful"], n)

    def test_support_covers_difficulty(self):
        n = note("I'm so stressed, I need a hug")
        self.assertIn(sc.TONE_LINES["support"], n)
        self.assertNotIn(sc.TONE_LINES["difficulty"], n)

    def test_hint_never_names_a_feeling_as_fact(self):
        for line in [HEADER] + list(sc.TONE_LINES.values()):
            for word in ("you must", "always", "never", "is sad", "is angry", "is happy"):
                self.assertNotIn(word, line.lower())


class FakeCfg:
    """Every other lane off; Social Cognition live; the channel's live switching is `live`."""

    def __init__(self, log, live=False, mode="live"):
        self.enabled, self.recent_turns, self.groq_model = True, 4, "groq-m"
        self.social_cognition_mode, self._live, self._log = mode, live, log

    def resolved_log_path(self):
        return self._log

    def social_cognition_is_active(self, platform, chat_id):
        return self.social_cognition_mode in ("shadow", "live")

    def social_cognition_is_live(self, platform, chat_id):
        return self.social_cognition_mode == "live"

    def channel_is_live(self, platform, chat_id):
        return self._live

    def social_lean_is_on(self, platform):
        return True

    def __getattr__(self, name):
        if name.endswith(("_is_active", "_is_live", "_is_on")):
            return lambda *a, **k: False
        raise AttributeError(name)


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.gi = load_router()
        self.log = Path(self.tmp) / "decisions.log"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def route(self, platform, source, message, live=False, mode="live"):
        gi = self.gi
        gi._config.load = lambda: FakeCfg(self.log, live=live, mode=mode)
        gi._canonical_memory.load_settings = lambda home, **kw: SETTINGS
        gi._canonical_memory.turn_note = lambda *a, **kw: None
        gi._platform_name = lambda s: platform
        ctx = types.SimpleNamespace(source=source, message=message, session_key=f"k:{platform}:{message[:8]}")
        return gi.route_turn(runner=None, ctx=ctx, model="m", runtime_kwargs={}, turn_route={}, combined_ephemeral="")

    def test_full_agent_owner_turn_gets_the_hint(self):
        r = self.route("telegram", src(user_id=OWNER, chat_id=OWNER, chat_type="dm"), "hehe good morning \U0001f338")
        self.assertTrue(r["turn_hint"].startswith(HEADER))
        self.assertIn(sc.TONE_LINES["playful"], r["turn_hint"])
        self.assertNotIn("combined_ephemeral", r)                 # the cached agent's prompt is untouched
        self.assertIn('"lane": "social_cognition_live"', self.log.read_text(encoding="utf-8"))

    def test_public_channels_stay_shadow(self):
        for platform, s in [("telegram", src(user_id=OWNER, chat_id="-1001", chat_type="group")),
                            ("telegram", src(user_id="42", chat_id="42", chat_type="dm")),
                            ("discord", src(user_id=OWNER, chat_id="55", chat_type="group"))]:
            with self.subTest(platform=platform):
                self.assertNotIn("turn_hint", self.route(platform, s, "hehe good morning \U0001f338"))

    def test_shadow_mode_and_quiet_turns_add_nothing(self):
        owner = src(user_id=OWNER, chat_id=OWNER, chat_type="dm")
        self.assertNotIn("turn_hint", self.route("telegram", owner, "hehe good morning \U0001f338", mode="shadow"))
        self.assertNotIn("turn_hint", self.route("telegram", owner, "Run the tests again please"))
        self.assertNotIn("turn_hint", self.route("lilith_os", src(), "hehe hi", mode="bogus"))   # unknown mode: off

    def test_lean_groq_reply_gets_the_note_in_its_policy(self):
        gi, seen = self.gi, {}
        gi._groq_runtime = lambda runner, cfg: ({"api_key": "k"}, "")
        gi._social_lean.skip_reason = lambda message: ""

        def reply(**kw):
            seen.update(kw)
            return "hey you", ""
        gi._social_lean.reply = reply
        r = self.route("telegram", src(user_id=OWNER, chat_id=OWNER, chat_type="dm"), "hehe good morning \U0001f338",
                       live=True)
        self.assertEqual(r["final_response"], "hey you")
        self.assertNotIn("turn_hint", r)
        self.assertIn(sc.TONE_LINES["playful"], seen["policy"])
        self.assertTrue(seen["policy"].startswith(gi._policy.SOCIAL_POLICY))    # added to, never replacing

    def test_hint_does_not_leak_into_the_next_turn(self):
        self.route("telegram", src(user_id=OWNER, chat_id=OWNER, chat_type="dm"), "hehe good morning \U0001f338")
        r = self.route("discord", src(user_id=OWNER, chat_id="55", chat_type="group"), "what's up")
        self.assertNotIn("turn_hint", r)
        self.assertEqual(self.gi._tc.current().style.lines, ())
        self.assertIsNone(self.gi._tc.tone_text(self.gi._tc.current()))


class RunPyTests(unittest.TestCase):
    def helper(self):
        tree = ast.parse(RUN_PY.read_text(encoding="utf-8"))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == "_wrap_current_message_with_turn_hint")
        ns = {"Any": object}
        exec(compile(ast.Module([fn], []), "run.py", "exec"), ns)
        return ns[fn.name]

    def test_hint_is_api_only(self):
        wrap = self.helper()
        self.assertEqual(wrap("hi", "HINT"), "HINT\n\nhi")
        parts = [{"type": "image_url", "image_url": {"url": "x"}}, {"type": "text", "text": "look"}]
        self.assertEqual(wrap(parts, "HINT")[1]["text"], "HINT\n\nlook")
        self.assertEqual(parts[1]["text"], "look")                                    # input untouched
        text = RUN_PY.read_text(encoding="utf-8")
        self.assertIn("elif observed_group_context or _lr_turn_hint:\n"
                      "                _conversation_kwargs[\"persist_user_message\"] = ctx.message", text)


class ContextGateTests(unittest.TestCase):
    """2026-11-07 offline review: the playful line was nearly every misfire. Same approved wording, chosen with context."""

    def keys(self, message, recent=()):
        from lilith_router import classifier as cl
        d = cl.classify(message, list(recent), "social" if recent else None)
        snap = sc.build_social_context(sc.build_social_input(message, "sc.g", "telegram"))
        focused = d.mode != "social" or bool(d.signals["tech"])
        return sc.tone_note_keys(snap, focused=focused, context=sc.tone_context(message, list(recent)))

    def test_casual_technical_questions_stay_focused(self):
        self.assertEqual(self.keys("lol okay, how do I make git keep my uncommitted changes safe? \U0001f605",
                                   ["ugh my laptop froze right before I saved, this is killing me lol"]), [])
        self.assertEqual(self.keys("hey can you help me write a regex for emails? ty \u2764\ufe0f"), [])
        self.assertEqual(self.keys("lol why does my docker container keep exiting with code 137"), [])

    def test_a_bad_idea_gets_no_play_along_nudge(self):
        self.assertEqual(self.keys("haha I'm just gonna force push to main on friday night, what could go wrong \U0001f602"), [])

    def test_sarcasm_is_joking_about_something_annoying(self):
        self.assertEqual(self.keys("great, another rejection email. love that for me \U0001f643"), ["mixed"])

    def test_laughing_about_no_sleep_is_mixed(self):
        self.assertEqual(self.keys("lol I haven't slept in two days but I'm fine haha \U0001f602"), ["mixed"])

    def test_brushing_off_something_hard_from_the_previous_turn(self):
        hard = ["they rejected me after the final round. third time this month."]
        self.assertEqual(self.keys("haha whatever, it's fine \U0001f602 what's new with you?", hard), [])

    def test_an_earlier_hard_subject_alone_does_not_decide(self):
        msg = "haha whatever, it's fine \U0001f602 what's new with you?"
        self.assertEqual(self.keys(msg, ["had pizza for lunch"]), ["playful"])
        self.assertEqual(self.keys("hehe you're such a nerd \U0001f60f", ["ugh rough week"]), ["playful"])  # no brush-off
        self.assertEqual(self.keys("haha that was a rough week but this weekend was amazing \U0001f602",
                                   ["ugh rough week"]), ["mixed"])

    def test_playful_and_explicit_intent_still_work(self):
        self.assertEqual(self.keys("hehe you're such a nerd for noticing \U0001f60f"), ["playful"])
        self.assertEqual(self.keys("good morning \u2764\ufe0f missed you"), ["playful"])
        self.assertEqual(self.keys("haha make it funny please"), ["playful", "humor"])
        self.assertEqual(self.keys("no, it's tuesday not monday lol", ["my interview is on tuesday"]),
                         ["correction", "playful"])
        self.assertEqual(self.keys("can you cheer me up? the interview went badly"), ["support"])
        self.assertIn("formal", self.keys("haha my manager wants a status email, keep it formal"))

    def test_rejection_wording_is_narrow(self):
        self.assertEqual(self.keys("I rejected the offer haha \U0001f60f"), ["playful"])
        self.assertEqual(self.keys("lol you git \U0001f602"), ["playful"])

    def test_git_terms_route_only_real_git_talk(self):
        from lilith_router import classifier as cl
        self.assertEqual(cl.classify("how do I make git keep my uncommitted changes safe?", [], None).mode, "technical")
        for msg in ("that's legit hilarious", "lol you git", "good morning, I digit-ally miss you",
                    "haha I'm so tired today", "what's up babe"):
            with self.subTest(msg=msg):
                self.assertEqual(cl.classify(msg, [], None).signals["tech"], 0)

    def test_router_logs_the_choice_without_text(self):
        text = (ROOT / "deploy/prod/lilith_router/gateway_integration.py").read_text(encoding="utf-8")
        self.assertIn('tctx.focused = decision.mode != SOCIAL or bool((decision.signals or {}).get("tech"))', text)
        self.assertIn("tone_ctx = _sc.tone_context(message, recent)", text)


if __name__ == "__main__":
    unittest.main()
