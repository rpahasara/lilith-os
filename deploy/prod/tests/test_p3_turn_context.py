"""P-3 batch 1: the shared TurnContext and typed StyleDirective reproduce the pre-P-3 prompt text byte for byte,
stay owner-only, reset every turn and trace metadata only."""
import itertools
import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_p2_social_preferences import ENTRIES, load_router  # noqa: E402


class TurnContextRenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.gi = load_router()
        self.tc = self.gi._tc
        from lilith_router import social_cognition as sc, social_preferences as sp
        self.sc, self.sp = sc, sp
        self.prefs = [p for p in (sp.parse(e["text"], e["entry_id"]) for e in ENTRIES) if p]

    def tearDown(self):
        self.tc.begin()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # the pre-P-3 composition, kept here as the reference
    def old_tone(self, keys):
        return (self.sc.TONE_HEADER + "\n" + "\n".join("- " + self.sc.TONE_LINES[k] for k in keys)) if keys else None

    def old_agent_hint(self, correction, keys, prefs, status):
        parts = [status] if status else [self.sp.CORRECTION_HINT if correction else None, self.old_tone(keys)]
        parts.append(self.sp.render(prefs) if prefs else None)
        return "\n\n".join(p for p in parts if p) or None

    def old_lean_suffix(self, keys, prefs):
        tone, note = self.old_tone(keys), (self.sp.render(prefs) if prefs else None)
        return ("\n\n" + tone if tone else "") + ("\n\n" + note if note else "")

    def ctx(self, keys, prefs, correction, owner=True, live=True):
        c = self.tc.begin("telegram_owner_dm" if owner else "public", owner)
        c.style = self.tc.directive(keys, focused=False, preference_refs=[p.entry_id for p in prefs])
        c.preferences, c.preferences_live, c.correction = tuple(prefs), live, correction
        return c

    def test_byte_identical_to_the_previous_composition(self):
        key_sets = [(), ("playful",), ("correction", "support"), ("mixed", "humor"), ("formal",), ("difficulty",)]
        pref_sets = [[], self.prefs[:1], self.prefs[:3]]
        n = 0
        for keys, prefs, corr, status in itertools.product(key_sets, pref_sets, (False, True), (None, "[status]")):
            c = self.ctx(keys, prefs, corr)
            self.assertEqual(self.tc.agent_hint(c, status), self.old_agent_hint(corr, keys, prefs, status))
            self.assertEqual(self.tc.lean_suffix(c), self.old_lean_suffix(keys, prefs))
            n += 1
        self.assertEqual(n, 72)

    def test_shadow_preferences_are_traced_not_rendered(self):
        c = self.ctx(("playful",), self.prefs[:2], False, live=False)
        self.assertNotIn(self.prefs[0].text, self.tc.agent_hint(c))
        s = c.summary()
        self.assertEqual(s["pref_refs"], [p.entry_id for p in self.prefs[:2]])
        self.assertFalse(s["pref_applied"])

    def test_non_owner_renders_nothing(self):
        c = self.ctx(("playful",), self.prefs, True, owner=False)
        self.assertIsNone(self.tc.agent_hint(c, "[status]"))
        self.assertEqual(self.tc.lean_suffix(c), "")

    def test_confidence_and_register(self):
        d = self.tc.directive
        self.assertEqual(d((), focused=True).confidence, "low")
        self.assertEqual(d(("playful",), focused=False).confidence, "medium")
        self.assertEqual(d(("playful", "humor"), focused=False).confidence, "high")
        self.assertEqual(d(("formal",), focused=True).register, "formal")
        self.assertEqual(d((), focused=True).focus, "task")
        # low confidence renders no tone line, even if lines were forced in
        c = self.tc.begin("lilith_os", True)
        c.style = self.tc.dataclasses_replace(d(("playful",), focused=False), confidence="low")
        self.assertIsNone(self.tc.tone_text(c))

    def test_summary_is_metadata_only(self):
        c = self.ctx(("playful", "correction"), self.prefs, True)
        blob = json.dumps(c.summary())
        for p in self.prefs:
            self.assertNotIn(p.text, blob)
        for line in self.sc.TONE_LINES.values():
            self.assertNotIn(line, blob)
        self.assertIn('"style_lines": ["playful", "correction"]', blob)


class TurnContextLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.gi = load_router()
        self.log = Path(tempfile.mkdtemp()) / "decisions.log"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.log.parent, ignore_errors=True)

    def test_route_turn_starts_a_fresh_context(self):
        gi = self.gi
        c = gi._tc.begin("telegram_owner_dm", True)
        c.correction = True
        gi._route_turn_impl = lambda **kw: None
        gi.route_turn(runner=None, ctx=types.SimpleNamespace(source=None), model=None, runtime_kwargs={},
                      turn_route=None, combined_ephemeral="")
        now = gi._tc.current()
        self.assertIsNot(now, c)
        self.assertFalse(now.correction)
        self.assertFalse(now.owner)

    def test_turn_end_record_carries_the_summary(self):
        gi = self.gi
        cfg = gi._config.RouterConfig(enabled=True, log_path=str(self.log))
        gi._config.load = lambda: cfg
        gi._turn_id.set("t" * 16)
        c = gi._tc.begin("telegram_owner_dm", True)
        c.style = gi._tc.directive(("playful",), focused=False)
        gi.log_turn_end(types.SimpleNamespace(source=None, session_key="k"), result={})
        rec = json.loads(self.log.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual((rec["lane"], rec["style_lines"], rec["style_confidence"]), ("turn", ["playful"], "medium"))


if __name__ == "__main__":
    unittest.main()
