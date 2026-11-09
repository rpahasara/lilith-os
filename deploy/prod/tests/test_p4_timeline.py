"""P-4 E-8 follow-up: the dated approved-memory timeline. Rendered only from the World Model's records (learned =
approval date; superseded = no longer current); nothing invented; owner temporal turns only; full agent only."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_p2_social_preferences import load_router  # noqa: E402


def rec(text, approved=None, state="ACTIVE", updated=None):
    return {"text": text, "lifecycle_state": state, "updated_at": updated, "entry_id": "om_x",
            "provenance": [{"kind": "OWNER_APPROVED_PROPOSAL" if approved else "HERMES_PREEXISTING_IMPORT",
                            "approved_at": approved}]}


RECORDS = [rec("Name is Sam."), rec("Lives in Leeds.", "2026-08-15T10:00:00Z", "SUPERSEDED", "2026-10-20T18:00:00+00:00"),
           rec("Works at Acme.", "2026-09-02T17:00:00Z"), rec("Lives in Manchester.", "2026-10-20T18:00:00Z")]


class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.gi = load_router()
        self.tl = self.gi._timeline
        self.log = Path(tempfile.mkdtemp()) / "decisions.log"
        self.gi._OWNER_MEMORY = self.tl.OwnerMemorySource(fetch=lambda: RECORDS)

    def tearDown(self):
        self.gi._tc.begin()
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.log.parent, ignore_errors=True)

    def test_render_uses_only_recorded_dates(self):
        note = self.tl.render(RECORDS)
        lines = note.split("\n")[1:]
        self.assertEqual(lines, ["- learned 2026-09-02: Works at Acme.",
                                 "- no longer current since 2026-10-20: Lives in Leeds.",
                                 "- learned 2026-10-20: Lives in Manchester.",
                                 "- undated: Name is Sam."])
        self.assertIn("not necessarily when it happened", note)
        self.assertIsNone(self.tl.render([]))
        big = [rec("x" * 230, "2026-09-%02dT00:00:00Z" % (i % 28 + 1)) for i in range(40)]
        self.assertLessEqual(len(self.tl.render(big)), self.tl.MAX_CHARS + 1)

    def test_temporal_cue(self):
        for m in ("when did I start at Acme?", "what came first?", "how long ago did I pass?", "did I ever live elsewhere?",
                  "where was I living before?", "do I still work there?"):
            self.assertTrue(self.tl.temporal(m), m)
        for m in ("which city do I live in?", "good morning!", "did I pass on my first try"):
            self.assertFalse(self.tl.temporal(m), m)

    def turn(self, mode, message, owner=True, focused=False):
        gi = self.gi
        ctx = gi._tc.begin("telegram_owner_dm" if owner else "public", owner)
        ctx.focused = focused
        gi._canonical_memory.set_owner_turn(owner, "telegram_owner_dm" if owner else "public")
        gi._turn_id.set("t" * 16)
        gi._apply_timeline(gi._config.RouterConfig(enabled=True, log_path=str(self.log), timeline_mode=mode), message)
        return ctx

    def records(self):
        return [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() else []

    def test_live_agent_only_and_shadow_logs_only(self):
        tc = self.gi._tc
        ctx = self.turn("live", "when did I move to Manchester?")
        self.assertIn("no longer current since 2026-10-20: Lives in Leeds.", tc.agent_hint(ctx))
        self.assertEqual(tc.lean_suffix(ctx), "")
        rec_ = self.records()[-1]
        self.assertEqual((rec_["lane"], rec_["entries"], rec_["superseded"], rec_["applied"]), ("timeline", 4, 1, True))
        self.assertNotIn("Leeds", json.dumps(rec_))
        shadow = self.turn("shadow", "when did I move?")
        self.assertIsNone(tc.agent_hint(shadow))
        self.assertFalse(self.records()[-1]["applied"])
        text = (ROOT / "deploy/prod/lilith_router/gateway_integration.py").read_text(encoding="utf-8")
        self.assertIn('if not why and tctx.timeline:\n                why = "timeline"', text)

    def test_not_on_non_owner_focused_non_temporal_or_off(self):
        for kw, msg, mode in (({"owner": False}, "when did I move?", "live"), ({"focused": True}, "when did I move?", "live"),
                              ({}, "which city do I live in?", "live"), ({}, "when did I move?", "off")):
            self.assertEqual(self.turn(mode, msg, **kw).timeline, (), (kw, msg, mode))
        self.assertEqual(self.records(), [])

    def test_source_fail_open_and_router_yaml(self):
        self.gi._OWNER_MEMORY = self.tl.OwnerMemorySource(fetch=mock.Mock(side_effect=OSError("down")))
        self.assertEqual(self.turn("live", "when did I move?").timeline, ())
        cfg = self.gi._config
        with mock.patch.object(cfg, "CONFIG_PATH", ROOT / "deploy/prod/lilith_router/router.yaml"):
            self.assertEqual(cfg.load().timeline_mode, "shadow")


if __name__ == "__main__":
    unittest.main()
