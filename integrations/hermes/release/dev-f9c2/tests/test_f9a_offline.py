"""F9-A offline regression tests (D-1 option B, D-2). TEST_ONLY: synthetic text, no model calls, no network.

Same layout as the F7 suite (BUILD/hermes-agent -> release src, BUILD/hermes-home-dev -> home copy). The DEV config is
passed explicitly because the F7 home template carries the F7 test config:
    F9A_DEV_CONFIG=<package>/home/config.yaml  <venv>/bin/python -B tests/test_f9a_offline.py
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

BUILD = Path(__file__).resolve().parents[1]
HERMES_SRC = BUILD / "hermes-agent"
HOME = BUILD / "hermes-home-dev"
DEV_CONFIG = Path(os.environ["F9A_DEV_CONFIG"])
_TMP = tempfile.TemporaryDirectory(prefix="f9a-")
os.environ["HERMES_HOME"] = str(Path(_TMP.name) / "hh")
os.environ["HOME"] = _TMP.name
sys.path.insert(0, str(HERMES_SRC))
sys.path.insert(0, str(HOME))

CANARY = "F9A-CANARY-7Q2X synthetic line one\nsecond line of the synthetic canary"
PERSONALITY_SHA = "520cf5dbcda99247e39fecf520eac897d270e28dd26908a5c1686131a0d5f6b0"   # F8r4, must be unchanged


class RouterLogTests(unittest.TestCase):
    """D-2: every Router decision writer logs non-content metadata only."""

    @classmethod
    def setUpClass(cls):
        from lilith_router import gateway_integration as gi
        cls.gi = gi

    def setUp(self):
        self.log = Path(_TMP.name) / f"decisions-{self._testMethodName}.log"
        self.cfg = SimpleNamespace(resolved_log_path=lambda: self.log)

    def write_all(self, message):
        gi, cfg = self.gi, self.cfg
        dec = SimpleNamespace(mode="social", confidence=0.5, reason="conversational default", signals={"question": 1})
        gi._log_decision(cfg, "lilith_os", "f9a-s1", dec, False, message)
        gi._log_cognitive(cfg, "lilith_os", "f9a-s1", {"belief": True}, "shadow", message)
        gi._log_goal(cfg, "lilith_os", "f9a-s1", {"goal_query": True}, "shadow", message)
        gi._log_reasoning(cfg, "lilith_os", "f9a-s1", {"mode": "x"}, "shadow", message, {"steps": 0})
        gi._log_workspace(cfg, "lilith_os", "f9a-s1", None, "shadow", message, {"items": 0})
        gi._log_motivation(cfg, "lilith_os", "f9a-s1", None, "shadow", message, {"drives": 0})
        gi._log_planning(cfg, "lilith_os", "f9a-s1", {"subtype": "x"}, "shadow", message, {"plan": 0})
        gi._log_ethics(cfg, "lilith_os", "f9a-s1", {"trigger": "x"}, "shadow", message, {"principles": 0})
        return self.log.read_text(encoding="utf-8")

    def test_all_eight_writers_log_no_message_text(self):
        raw = self.write_all(CANARY)
        recs = [json.loads(l) for l in raw.splitlines()]
        self.assertEqual(len(recs), 8)
        self.assertNotIn("CANARY", raw)
        self.assertNotIn("synthetic", raw)
        for r in recs:
            self.assertNotIn("preview", r)
            self.assertEqual((r["msg_chars"], r["msg_lines"]), (len(CANARY), 2))
            self.assertRegex(r["event_id"], r"^[0-9a-f]{32}$")

    def test_event_ids_are_random_not_content_derived(self):
        self.write_all(CANARY)
        raw = self.write_all(CANARY)                                                # 16 records, same text twice
        ids = [json.loads(l)["event_id"] for l in raw.splitlines()]
        self.assertEqual(len(ids), 16)
        self.assertEqual(len(ids), len(set(ids)))                                   # same text, different ids
        digests = {h(CANARY.encode()).hexdigest() for h in (hashlib.md5, hashlib.sha1, hashlib.sha256)}
        self.assertFalse(any(d.startswith(i) or i in d for i in ids for d in digests))

    def test_empty_and_none_message(self):
        for m in ("", None):
            self.log.unlink(missing_ok=True)
            r = json.loads(self.write_all(m).splitlines()[0])
            self.assertEqual((r["msg_chars"], r["msg_lines"]), (0, 0))

    def test_source_has_no_preview_key_and_no_text_hashing(self):
        src = Path(self.gi.__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)
        keys = {k.value for n in ast.walk(tree) if isinstance(n, ast.Dict) for k in n.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        self.assertNotIn("preview", keys)
        self.assertNotIn("hashlib", src)


class OnboardingTests(unittest.TestCase):
    """D-1 option B: config off + no first-contact sidecar note for lilith_os."""

    def test_dev_config_disables_profile_build(self):
        import yaml
        from agent.onboarding import profile_build_mode
        cfg = yaml.safe_load(DEV_CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(cfg["onboarding"]["profile_build"], "off")                 # a string, not YAML false
        self.assertEqual(profile_build_mode(cfg), "off")
        self.assertEqual((cfg["memory"]["memory_enabled"], cfg["memory"]["user_profile_enabled"]), (False, False))

    def test_unquoted_yaml_off_would_not_disable(self):
        import yaml
        from agent.onboarding import profile_build_mode
        self.assertEqual(profile_build_mode(yaml.safe_load("onboarding:\n  profile_build: off\n")), "ask")

    def test_run_py_skips_first_contact_note_for_lilith_os(self):
        src = (HERMES_SRC / "gateway" / "run.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        guards = [n for n in ast.walk(tree) if isinstance(n, ast.If)
                  and "has_any_sessions" in ast.unparse(n.test)]
        self.assertEqual(len(guards), 1)
        cond = ast.unparse(guards[0].test)
        self.assertIn("'lilith_os'", cond)
        self.assertLess(cond.index("lilith_os"), cond.index("has_any_sessions"))   # evaluated first: no re-arm
        body = ast.unparse(guards[0])
        self.assertIn("profile_build_directive", body)                             # both notes only inside the guard
        self.assertIn("_intro_note", body)
        outside = src.replace(ast.get_source_segment(src, guards[0]), "")
        self.assertNotIn("profile_build_directive()", outside)
        self.assertNotRegex(outside, r"_intro_note\s*=")

    def test_profile_directive_text_unchanged_upstream(self):
        from agent.onboarding import profile_build_directive
        self.assertIn("build a short profile", profile_build_directive())          # upstream module untouched


class PersonaPreservationTests(unittest.TestCase):
    """Owner preference: SOUL.md and LILITH's personality design are not modified by F9-A."""

    def test_personality_module_unchanged(self):
        data = (HERMES_SRC / "hermes_cli" / "personality.py").read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), PERSONALITY_SHA)

    def test_no_soul_file_shipped(self):
        self.assertFalse(any(p.name.startswith("SOUL") for p in HOME.rglob("*")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
