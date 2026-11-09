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

    def test_render_uses_only_recorded_dates_and_safe_wording(self):
        note = self.tl.render(RECORDS)
        lines = note.splitlines()[1:]
        self.assertEqual(lines, ["- stored 2026-09-02: Works at Acme.",
                                 "- replaced 2026-10-20 (an earlier stored belief, not necessarily ever true): Lives in Leeds.",
                                 "- stored 2026-10-20: Lives in Manchester.",
                                 "- stored (undated): Name is Sam."])
        header = note.splitlines()[0]
        self.assertIn("never when anything happened", header)
        self.assertIn("never a reason to say which real event came first", header)
        self.assertIn("may have been mistaken, fictional or corrected", header)
        for unsafe in ("learned", "was true before", "no longer current"):
            self.assertNotIn(unsafe, note)
        self.assertIsNone(self.tl.render([]))
        big = [rec("x" * 230, "2026-09-%02dT00:00:00Z" % (i % 28 + 1)) for i in range(40)]
        self.assertLessEqual(len(self.tl.render(big)), self.tl.MAX_CHARS + 1)

    def test_agent_path_wording_searches_before_unknown(self):
        agent = self.tl.render(RECORDS, can_search=True)
        lean = self.tl.render(RECORDS)
        self.assertIn("check your past conversations with them first", agent)
        self.assertIn("prefer what they said at the time over any stored date", agent)
        self.assertNotIn("check your past conversations", lean)
        for note in (agent, lean):                                    # the semantics stay in both
            self.assertIn("never when anything happened", note)
            self.assertIn("may have been mistaken, fictional or corrected", note)
        self.assertEqual(agent.splitlines()[1:], lean.splitlines()[1:])
        ctx = self.turn("live", "when did I move to Manchester?")
        self.assertIn("check your past conversations", self.gi._tc.agent_hint(ctx))

    # -- integrated #406 + #407: one render produces the agent's note and its audit ids --------------------------

    def test_logged_ids_are_exactly_the_agent_notes_lines(self):
        recs = [rec("Lives in Leeds.", "2026-08-15T10:00:00Z", "SUPERSEDED", "2026-10-20T18:00:00+00:00"),
                rec("Works at Acme.", "2026-09-02T17:00:00Z"), rec("Lives in Manchester.", "2026-10-20T18:00:00Z")]
        for i, r in enumerate(recs):
            r["entry_id"] = "om_%d" % i
        self.gi._OWNER_MEMORY = self.tl.OwnerMemorySource(fetch=lambda: recs)
        ctx = self.turn("live", "when did I move to Manchester?")
        hint = self.gi._tc.agent_hint(ctx)
        self.assertIn(ctx.timeline_note, hint)                              # the stored note itself, not a re-render
        self.assertEqual(ctx.timeline_note, self.tl.render(recs, can_search=True))
        logged = self.records()[-1]
        self.assertEqual(logged["included_ids"], ["om_1", "om_0", "om_2"])  # rendered order: stored date
        self.assertEqual(list(ctx.timeline_ids), logged["included_ids"])
        self.assertEqual(len(ctx.timeline_note.splitlines()) - 1, logged["included"])

    def test_truncation_boundary_uses_the_agent_header(self):
        line_len = len("- stored 2026-09-01: ") + 230 + 1
        n_lean = (self.tl.MAX_CHARS - len(self.tl.HEADER)) // line_len
        n_agent = (self.tl.MAX_CHARS - len(self.tl.AGENT_HEADER)) // line_len
        self.assertLess(n_agent, n_lean)                                    # the boundary really differs
        recs = [rec("x" * 230, "2026-09-%02dT00:00:00Z" % (i + 1)) for i in range(12)]
        for i, r in enumerate(recs):
            r["entry_id"] = "om_t%02d" % i
        self.gi._OWNER_MEMORY = self.tl.OwnerMemorySource(fetch=lambda: recs)
        ctx = self.turn("live", "when did I start?")
        logged = self.records()[-1]
        self.assertEqual(logged["included"], n_agent)
        self.assertEqual(len(ctx.timeline_ids), n_agent)
        self.assertEqual(len(ctx.timeline_note.splitlines()) - 1, n_agent)
        self.assertLessEqual(len(ctx.timeline_note), self.tl.MAX_CHARS + 1)
        lean_note, lean_ids = self.tl.render_with_ids(recs)
        self.assertEqual(len(lean_ids), n_lean)                             # a lean render would NOT match the log

    def test_missing_ids_are_counted_not_invented(self):
        recs = [rec("A.", "2026-09-01T00:00:00Z"), rec("B.", "2026-09-02T00:00:00Z")]
        recs[0]["entry_id"] = None
        recs[1]["entry_id"] = "om_b"
        self.gi._OWNER_MEMORY = self.tl.OwnerMemorySource(fetch=lambda: recs)
        ctx = self.turn("live", "when did I start?")
        logged = self.records()[-1]
        self.assertEqual((logged["included"], logged["included_ids"], logged["missing_ids"]), (2, ["om_b"], 1))
        self.assertEqual(ctx.timeline_ids, (None, "om_b"))

    def test_shadow_logs_ids_but_injects_nothing(self):
        ctx = self.turn("shadow", "when did I move?")
        self.assertIsNone(ctx.timeline_note)
        self.assertEqual(ctx.timeline_ids, ())
        self.assertIsNone(self.gi._tc.agent_hint(ctx))
        rec_ = self.records()[-1]
        self.assertEqual((rec_["applied"], rec_["included"]), (False, 4))

    def test_owner_memory_is_only_read(self):
        seen = []

        class Resp:
            def read(self): return json.dumps({"entries": RECORDS}).encode()
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def urlopen(req, timeout=None):
            seen.append(req)
            return Resp()
        src = self.tl.OwnerMemorySource(api="http://127.0.0.1:8765")
        with mock.patch.object(self.tl.urllib.request, "urlopen", side_effect=urlopen):
            self.assertEqual(len(src.current()), 4)
        self.assertEqual(seen, ["http://127.0.0.1:8765/os/owner-memory?include_superseded=1"])   # a plain GET, no body
        text = (ROOT / "deploy/prod/lilith_router/timeline.py").read_text(encoding="utf-8")
        for verb in ("POST", "PUT", "PATCH", "DELETE", "method="):
            self.assertNotIn(verb, text)

    def test_temporal_cue_is_narrow(self):
        for m in ("when did I start at Acme?", "what came first, starting at Acme or my failed CKA attempt?",
                  "how long ago did I pass the CKA?", "where was I living when I started at Acme?",
                  "have I ever lived anywhere other than where I live now?", "did I ever tell you about my sister?",
                  "do I still work at Acme?", "when did you first learn about my job?",
                  "what did I use to do before this job?", "how many days since I passed?",
                  "where did I work before I moved?"):
            self.assertTrue(self.tl.temporal(m), m)
        for m in ("when I get home I will message you", "I'll call you after dinner",
                  "before we start, can you explain kubernetes?", "have you ever seen Dune?", "is it still raining there?",
                  "when is the deadline for the form?", "how long does a CKA exam take?",
                  "what came out first, the book or the film?", "which was first, the chicken or the egg?",
                  "since you asked, I am fine", "I moved the meeting to friday", "which city do I live in?",
                  "after this, remind me to drink water", "ever had pineapple pizza?",
                  "I started at Acme when I moved"):                       # a statement, not a question
            self.assertFalse(self.tl.temporal(m), m)

    def test_came_first_only_about_the_owners_history(self):
        for m in ("what came first, starting at Acme or my failed CKA attempt?", "my move or my new job, which came first?",
                  "which happened first: I told you my real name or asked for the three-section reviews?",
                  "which came first for us, the reminder or the review?",
                  "what came first, my sister visiting or the interview?"):
            self.assertTrue(self.tl.temporal(m), m)
        for m in ("which came first, the chicken or the egg?", "what happened first in WW2?",
                  "which came first, Unix or Linux?", "what came first, the book or the film?",
                  "which happened first, the moon landing or Woodstock?", "which came first in the race?"):
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
        self.assertIn("replaced 2026-10-20 (an earlier stored belief, not necessarily ever true): Lives in Leeds.", tc.agent_hint(ctx))
        self.assertEqual(tc.lean_suffix(ctx), "")
        rec_ = self.records()[-1]
        self.assertEqual((rec_["lane"], rec_["entries"], rec_["superseded"], rec_["applied"]), ("timeline", 4, 1, True))
        self.assertNotIn("Leeds", json.dumps(rec_))
        self.assertEqual(rec_["included_ids"], ["om_x"] * 4)                       # ids only, in rendered order
        note, ids = self.tl.render_with_ids(RECORDS)
        self.assertEqual(note, self.tl.render(RECORDS))
        self.assertEqual(len(ids), len(note.splitlines()) - 1)
        shadow = self.turn("shadow", "when did I move?")
        self.assertIsNone(tc.agent_hint(shadow))
        self.assertFalse(self.records()[-1]["applied"])
        text = (ROOT / "deploy/prod/lilith_router/gateway_integration.py").read_text(encoding="utf-8")
        self.assertIn('if not why and tctx.timeline:\n                why = "timeline"', text)

    def test_not_on_non_owner_focused_non_temporal_or_off(self):
        self.assertTrue(self.turn("live", "When did I start learning Kubernetes?", focused=True).timeline)   # technical ok
        self.log.unlink()
        for kw, msg, mode in (({"owner": False}, "when did I move?", "live"),
                              ({}, "which city do I live in?", "live"), ({}, "when did I move?", "off"),
                              ({"focused": True}, "how do I restart a kubernetes pod?", "live")):
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
