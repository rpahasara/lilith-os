"""P-2 (2026-11-08): approved social preferences and correction learning, on existing owner memory (synthetic text).

Preferences are ordinary owner-approved memories with a type/scope tag; the router applies at most three whose scope
fits the turn, on owner turns only, in live mode only (shadow logs the selection without text). Explicit durable
corrections route to the tool-capable agent with a hint to PROPOSE (never claim to save) a memory.
"""
import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_owner_memory import OWNER, ROOT, load_router, src  # noqa: E402

sys.path.insert(0, str(ROOT / "deploy/prod"))
from lilith_router import social_preferences as SP  # noqa: E402

ENTRIES = [
    {"entry_id": "om_1", "text": "Preference (technical): For technical discussions, prioritize accuracy over jokes.",
     "lifecycle_state": "CURRENT"},
    {"entry_id": "om_2", "text": "Preference (casual): Playful, cheeky conversation is welcome.", "lifecycle_state": "CURRENT"},
    {"entry_id": "om_3", "text": "Boundary: Don't call me 'champ'.", "lifecycle_state": "CURRENT"},
    {"entry_id": "om_4", "text": "Boundary (topic: test scenarios): Never treat fictional test scenarios as real incidents.",
     "lifecycle_state": "CURRENT"},
    {"entry_id": "om_5", "text": "Preference: old wording, superseded.", "lifecycle_state": "SUPERSEDED"},
    {"entry_id": "om_6", "text": "Prefers tea over coffee.", "lifecycle_state": "CURRENT"},          # not a preference tag
]


class ParseAndSelectTests(unittest.TestCase):
    def test_tags_and_scopes(self):
        self.assertEqual(SP.parse("Boundary (casual): no pet names", "x"), SP.SocialPreferenceV1("boundary", "casual", "no pet names", "x"))
        self.assertEqual(SP.parse("preference - be brief").scope, "global")
        self.assertEqual(SP.parse("Preference (Topic: Job Interviews): keep it encouraging").scope, "topic:job interviews")
        for text in ("Prefers tea.", "Preference (weird): x", "Boundary:", "my preference: x", None, 3):
            self.assertIsNone(SP.parse(text), text)

    def test_selection_is_scoped_bounded_and_boundaries_first(self):
        prefs = [SP.parse(e["text"], e["entry_id"]) for e in ENTRIES if SP.parse(e["text"])]
        tech = SP.select(prefs, focused=True, message="how do I fix a merge conflict?")
        self.assertEqual([p.entry_id for p in tech], ["om_3", "om_1", "om_5"])         # boundary, specific, global
        self.assertNotIn("om_2", [p.entry_id for p in tech])                          # casual never on technical
        casual = SP.select(prefs, focused=False, message="good morning!")
        self.assertIn("om_2", [p.entry_id for p in casual])
        self.assertNotIn("om_1", [p.entry_id for p in casual])                        # technical never on casual
        self.assertNotIn("om_4", [p.entry_id for p in casual])                        # topic not mentioned
        topic = SP.select(prefs, focused=False, message="remember the test scenario from yesterday?")
        self.assertEqual([p.entry_id for p in topic][:2], ["om_4", "om_3"])          # boundaries first, topic before global
        self.assertLessEqual(len(SP.select(prefs * 3, focused=False, message="test scenarios")), SP.MAX_SELECTED)

    def test_render(self):
        self.assertIsNone(SP.render([]))
        note = SP.render([SP.parse("Boundary: Don't call me 'champ'.")])
        self.assertTrue(note.startswith(SP.NOTE_HEADER))
        self.assertIn("- Boundary: Don't call me 'champ'.", note)


class SourceTests(unittest.TestCase):
    def test_cache_supersession_and_fail_open(self):
        clock = [0.0]
        calls = []

        def fetch():
            calls.append(1)
            return ENTRIES
        src_ = SP.ApprovedPreferenceSource(fetch=fetch, clock=lambda: clock[0])
        ids = [p.entry_id for p in src_.current()]
        self.assertEqual(ids, ["om_1", "om_2", "om_3", "om_4"])                         # superseded and untagged out
        src_.current()
        self.assertEqual(len(calls), 1)                                                  # cached
        clock[0] = SP.CACHE_SECONDS + 1
        src_.current()
        self.assertEqual(len(calls), 2)                                                  # refreshed: a change applies
        broken = SP.ApprovedPreferenceSource(fetch=lambda: (_ for _ in ()).throw(OSError("down")))
        self.assertEqual(broken.current(), ())                                           # fail-open: nothing applied


class CorrectionCueTests(unittest.TestCase):
    def test_explicit_durable_corrections(self):
        for msg in ("Don't call me champ.", "stop calling me that", "I already told you I hate that",
                    "That's not what I meant", "that was only a test scenario, not a real event",
                    "please stop bringing up the outage", "it was just a test", "never say that again",
                    "I've told you this before"):
            with self.subTest(msg=msg):
                self.assertTrue(SP.durable_correction(msg))

    def test_ordinary_messages_are_not_corrections(self):
        for msg in ("don't worry about it", "I stopped by the shop", "that's what I meant", "I don't know",
                    "can you help me test this?", "never mind lol", "good morning"):
            with self.subTest(msg=msg):
                self.assertFalse(SP.durable_correction(msg))


class RouterIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.gi = load_router()
        self.log = Path(tempfile.mkdtemp()) / "decisions.log"
        self.gi._PREFERENCES = self.gi._social_prefs.ApprovedPreferenceSource(fetch=lambda: ENTRIES)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.log.parent, ignore_errors=True)

    def cfg(self, mode):
        return self.gi._config.RouterConfig(enabled=True, log_path=str(self.log), social_preferences_mode=mode)

    def apply(self, mode, message, owner=True, mode_of_turn="social", tech=0):
        gi = self.gi
        gi._pref_note.set(None)
        gi._correction_hint.set(None)
        gi._canonical_memory.set_owner_turn(owner, "telegram_owner_dm" if owner else "public")
        gi._turn_id.set("t" * 16)
        decision = types.SimpleNamespace(mode=mode_of_turn, signals={"tech": tech})
        gi._apply_social_preferences(self.cfg(mode), decision, message)
        return gi._pref_note.get(), gi._correction_hint.get()

    def records(self):
        return [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() else []

    def test_live_owner_turn_gets_scoped_preferences_and_logs_no_text(self):
        note, hint = self.apply("live", "good morning!")
        self.assertIn("Playful, cheeky conversation is welcome.", note)
        self.assertIn("Don't call me 'champ'.", note)
        self.assertNotIn("accuracy over jokes", note)
        self.assertIsNone(hint)
        rec = self.records()[-1]
        self.assertEqual((rec["lane"], rec["mode"], rec["turn_id"]), ("social_preferences", "live", "t" * 16))
        self.assertNotIn("champ", json.dumps(rec))                                       # ids, kinds, scopes only
        tech_note, _ = self.apply("live", "how do I rebase this branch?", mode_of_turn="technical")
        self.assertIn("accuracy over jokes", tech_note)
        self.assertNotIn("cheeky", tech_note)

    def test_shadow_logs_but_applies_nothing_and_off_does_nothing(self):
        self.assertEqual(self.apply("shadow", "good morning!"), (None, None))
        self.assertEqual(self.records()[-1]["mode"], "shadow")
        self.assertTrue(self.records()[-1]["selected"])
        before = len(self.records())
        self.assertEqual(self.apply("off", "good morning!"), (None, None))
        self.assertEqual(len(self.records()), before)

    def test_non_owner_turns_never_get_owner_preferences(self):
        self.assertEqual(self.apply("live", "good morning!", owner=False), (None, None))
        self.assertEqual(self.records(), [])

    def test_durable_correction_gets_the_proposal_hint(self):
        _note, hint = self.apply("live", "Don't call me champ, I already told you.")
        self.assertEqual(hint, self.gi._social_prefs.CORRECTION_HINT)
        self.assertIn("never say it is already saved", hint)
        self.assertTrue(self.records()[-1]["durable_correction"])

    def test_hint_composition_on_the_agent_path(self):
        gi = self.gi
        self.apply("live", "Don't call me champ.")
        gi._social_note.set("[tone]")
        out = gi._with_social_note({"owner_memory": True})
        self.assertEqual(out["turn_hint"].split("\n\n")[0], gi._social_prefs.CORRECTION_HINT)
        self.assertIn("[tone]", out["turn_hint"])
        self.assertIn("Don't call me 'champ'.", out["turn_hint"])
        out = gi._with_social_note({"self_status_hint": "[status]"})                    # status replaces the tone
        self.assertTrue(out["turn_hint"].startswith("[status]"))
        self.assertNotIn("[tone]", out["turn_hint"])
        self.assertNotIn("turn_hint", gi._with_social_note({"final_response": "hi"}))
        gi._social_note.set(None)

    def test_router_yaml_starts_in_shadow(self):
        cfg = self.gi._config
        with mock.patch.object(cfg, "CONFIG_PATH", ROOT / "deploy/prod/lilith_router/router.yaml"):
            self.assertEqual(cfg.load().social_preferences_mode, "shadow")

    def test_lean_path_skips_durable_corrections_and_carries_the_note(self):
        text = (ROOT / "deploy/prod/lilith_router/gateway_integration.py").read_text(encoding="utf-8")
        self.assertIn('if not why and _correction_hint.get():\n                why = "durable_correction"', text)
        self.assertIn('+ ("\\n\\n" + _pref_note.get() if _pref_note.get() else ""))', text)


if __name__ == "__main__":
    unittest.main()
