"""P-4 E-8 follow-up: the dated approved-memory timeline. Rendered only from the World Model's records (learned =
approval date; superseded = no longer current); nothing invented; owner temporal turns only; full agent only."""
import json
import shutil
import sys
import tempfile
import types
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

    def test_selective_escalation_record_vs_event_level(self):
        for m in ("How was my nickname stored before I corrected it?", "How was my city stored before I corrected it?",
                  "how was my name stored before I corrected it?"):
            self.assertTrue(self.tl.temporal(m), m)
            self.assertFalse(self.tl.needs_conversation(m), m)
        for m in ("When did I start at Acme?", "Which came first: me starting Kubernetes or starting at Acme?",
                  "How long ago did I pass the CKA?", "Where was I living when I failed my first CKA attempt?",
                  "When did I tell you I'd moved to Manchester?", "When did I start learning to cook?"):
            self.assertTrue(self.tl.needs_conversation(m), m)
        self.assertFalse(self.tl.needs_conversation("which city do I live in?"))

    def test_record_level_stays_fast_with_the_plain_header(self):
        tc = self.gi._tc
        ctx = self.turn("live", "How was my name stored before I corrected it?")
        self.assertFalse(ctx.timeline_escalate)
        self.assertIn("replaced 2026-10-20", tc.lean_suffix(ctx))            # the fast path gets the record timeline
        self.assertNotIn("check your past conversations", tc.lean_suffix(ctx))
        self.assertFalse(self.records()[-1]["escalate"])
        ev = self.turn("live", "when did I move to Manchester?")
        self.assertTrue(ev.timeline_escalate)
        self.assertEqual(tc.lean_suffix(ev), "")                              # event-level never on the fast path
        self.assertIn("check your past conversations", tc.agent_hint(ev))
        text = (ROOT / "deploy/prod/lilith_router/gateway_integration.py").read_text(encoding="utf-8")
        self.assertIn('if not why and tctx.timeline and tctx.timeline_escalate:\n        why = "timeline"', text)

    def test_mixed_record_and_event_questions_escalate(self):
        # owner review of #410: a record term never keeps an event-chronology question on the fast path
        for m in ("What did you have stored about my city before I corrected it, and when did I actually move?",
                  "How was my job stored before I corrected it, and how long ago did I start there?",
                  "Which came first: me starting Kubernetes or the date you saved it?",
                  "Where was I living when I failed the CKA, according to what you saved?",
                  "How many days since I passed the CKA, going by what's on file?",
                  "When did I tell you about Acme, and how was it stored?",
                  "Did I ever live in Leeds, or was that just what you had stored?",
                  "What was my nickname stored as back then, before I corrected it?",
                  "how was my city stored before I moved?"):
            self.assertTrue(self.tl.temporal(m), m)
            self.assertTrue(self.tl.needs_conversation(m), m)
        # record-only questions (what is or was stored, and when it was stored) stay on the fast path
        for m in ("How was my nickname stored before I corrected it?", "How was my city stored before I corrected it?",
                  "When was my city stored?", "what was my job saved as before I corrected it?",
                  "how was my name kept in your memory before I corrected it?"):
            self.assertTrue(self.tl.temporal(m), m)
            self.assertFalse(self.tl.needs_conversation(m), m)

    def test_every_gate_to_the_agent_gets_search_compatible_wording(self):
        gi, tc = self.gi, self.gi._tc
        q = "How was my name stored before I corrected it?"                   # record-level
        searching = "check your past conversations with them first"
        suppressing = "If the dates you need aren't written in an entry, say you don't know."
        self.assertIn(suppressing, self.tl.HEADER)
        cases = {"durable_correction": lambda c: setattr(c, "correction", True),
                 "recall_gap": lambda c: c.meta.update({"applied": True, "control": "escalate"}),
                 "responsibility": lambda c: setattr(c, "responsibility", ({"title": "water", "state": "BLOCKED"},)),
                 "action_intent": None}
        for why, arm in cases.items():
            ctx = self.turn("live", q)
            self.assertFalse(ctx.timeline_escalate)
            if arm:
                arm(ctx)
                self.assertEqual(gi._lean_skip_reason(q, ctx), why)
            else:                                                               # skip_reason's own gate
                self.assertEqual(gi._lean_skip_reason("remind me tomorrow: how was my name stored before?", ctx),
                                 "action_intent")
            hint = tc.agent_hint(ctx)
            self.assertIn(searching, hint, why)
            self.assertNotIn(suppressing, hint, why)
            self.assertIn(self.tl.HEADER.split(" If the dates")[0], hint)         # stored != event semantics kept
        ctx = self.turn("live", q)
        self.assertEqual(gi._lean_skip_reason(q, ctx), "")                       # alone it stays fast
        self.assertNotIn(searching, tc.lean_suffix(ctx))
        ev = self.turn("live", "when did I move to Manchester?")
        self.assertEqual(gi._lean_skip_reason("when did I move to Manchester?", ev), "timeline")
        ev.correction = True                                                    # an earlier gate names the reason
        self.assertEqual(gi._lean_skip_reason("when did I move to Manchester?", ev), "durable_correction")

    def test_record_level_logs_both_notes_ids_and_the_delivered_one(self):
        recs = [rec("x" * 230, "2026-09-%02dT00:00:00Z" % (i + 1)) for i in range(12)]
        for i, r in enumerate(recs):
            r["entry_id"] = "om_t%02d" % i
        self.gi._OWNER_MEMORY = self.tl.OwnerMemorySource(fetch=lambda: recs)
        ctx = self.turn("live", "How was my name stored before I corrected it?")
        logged = self.records()[-1]
        agent_note, agent_ids = self.tl.render_with_ids(recs, can_search=True)
        lean_note, lean_ids = self.tl.render_with_ids(recs)
        self.assertNotEqual(len(agent_ids), len(lean_ids))                     # the truncation boundaries differ
        self.assertEqual((ctx.timeline_note, ctx.timeline_lean_note), (agent_note, lean_note))
        self.assertEqual((logged["included_ids"], logged["lean_included_ids"]), (agent_ids, lean_ids))
        self.assertIsNone(ctx.summary().get("timeline_delivered"))             # nothing delivered yet
        out = self.gi._with_social_note({"combined_ephemeral": "x"})            # e.g. the lean call failed
        self.assertIn(agent_note, out["turn_hint"])
        self.assertEqual((ctx.summary()["timeline_delivered"], ctx.summary()["timeline_delivered_ids"]),
                         ("agent", agent_ids))
        ready = self.turn("live", "How was my name stored before I corrected it?")
        self.gi._with_social_note({"final_response": "ready"})                 # a ready reply carries no note
        self.assertIsNone(ready.summary().get("timeline_delivered"))
        ev = self.turn("live", "when did I start?")
        self.assertNotIn("lean_included_ids", self.records()[-1])              # event-level: no fast-path note
        self.assertIsNone(ev.timeline_lean_note)

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
        self.assertIn('if not why and tctx.timeline and tctx.timeline_escalate:\n        why = "timeline"', text)

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


class LocalDateTests(unittest.TestCase):
    """2026-11-10: PROD Hermes runs in Asia/Colombo. A "stored" date is the owner's calendar day in Hermes' zone, not
    the UTC day: three PROD approvals at 18:32-20:40Z on 6 Nov were 7 Nov in Colombo."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("tl_local", Path(__file__).resolve().parents[1] / "lilith_router" / "timeline.py")
        self.tl = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.tl)
        self.recs = [dict(rec("TEST_ONLY a.", "2026-11-06T18:32:00+00:00"), entry_id="om_a"),
                     dict(rec("TEST_ONLY b.", "2026-11-06T20:40:00Z"), entry_id="om_b"),
                     dict(rec("TEST_ONLY c.", "2026-11-08T12:48:00+00:00"), entry_id="om_c"),
                     dict(rec("TEST_ONLY old.", "2026-11-01T10:00:00Z", "SUPERSEDED", "2026-11-06T19:37:00+00:00"), entry_id="om_d")]

    def render(self, zone):
        env = {"HERMES_TIMEZONE": zone} if zone else {}
        with mock.patch.dict("os.environ", env, clear=False):
            if not zone:
                import os
                os.environ.pop("HERMES_TIMEZONE", None)
            return self.tl.render_with_ids(self.recs)

    def test_colombo_days(self):
        note, ids = self.render("Asia/Colombo")
        self.assertIn("(dates are calendar days in Asia/Colombo)", note.splitlines()[0])
        self.assertEqual(note.splitlines()[1:], [
            "- stored 2026-11-07: TEST_ONLY a.", "- stored 2026-11-07: TEST_ONLY b.",
            "- replaced 2026-11-07 (an earlier stored belief, not necessarily ever true): TEST_ONLY old.",
            "- stored 2026-11-08: TEST_ONLY c."])                         # same-day entries keep their stored order
        self.assertEqual(ids, ["om_a", "om_b", "om_d", "om_c"])

    def test_utc_when_no_zone_is_configured(self):
        note, ids = self.render(None)
        self.assertIn("(dates are calendar days in UTC)", note.splitlines()[0])
        self.assertEqual([l.split(":")[0] for l in note.splitlines()[1:]],
                         ["- stored 2026-11-06", "- stored 2026-11-06",
                          "- replaced 2026-11-06 (an earlier stored belief, not necessarily ever true)", "- stored 2026-11-08"])

    def test_unknown_zone_falls_back_to_named_utc(self):
        note, _ = self.render("Not/AZone")
        self.assertIn("(dates are calendar days in UTC)", note)

    def test_naive_timestamps_are_utc(self):
        self.assertEqual(self.tl._day("2026-11-06T19:00:00", self.tl.zone()[0]), "2026-11-06")
        from zoneinfo import ZoneInfo
        self.assertEqual(self.tl._day("2026-11-06T19:00:00", ZoneInfo("Asia/Colombo")), "2026-11-07")
        self.assertIsNone(self.tl._day("not a date"))

    def test_size_pressure_drops_the_oldest_not_the_newest(self):
        import os
        os.environ.pop("HERMES_TIMEZONE", None)
        recs = [dict(rec("x" * 240, "2026-10-%02dT10:00:00Z" % (i + 1)), entry_id="om_%02d" % (i + 1)) for i in range(20)]
        recs.append(dict(rec("TEST_ONLY imported, undated."), entry_id="om_imp"))
        for can_search in (False, True):
            with self.subTest(can_search=can_search):
                note, ids = self.tl.render_with_ids(recs, can_search=can_search)
                body = note.splitlines()[1:]
                self.assertLessEqual(len(note), self.tl.MAX_CHARS)
                self.assertEqual(len(ids), len(body))                          # audit ids = exactly the lines
                self.assertEqual(ids[-1], "om_imp")                             # undated stays last
                dated = ids[:-1]
                self.assertEqual(dated, sorted(dated))                          # chronological order kept
                self.assertEqual(dated[-1], "om_20")                            # the newest survives
                self.assertNotIn("om_01", ids)                                  # the oldest dropped first
                self.assertLessEqual(len(ids), self.tl.MAX_ENTRIES)

    def test_stored_is_still_never_an_event_date(self):
        note, _ = self.render("Asia/Colombo")
        self.assertIn('A "stored" date is when the memory', note)


class RoutedTurnTests(unittest.TestCase):
    """The real route: lean success, lean failure (fallback to the agent), event-level escalation, shadow."""

    def setUp(self):
        from test_owner_memory import OWNER, SETTINGS, src
        from test_social_tone_live import FakeCfg
        self.tmp, self.gi = load_router()
        self.log = Path(self.tmp) / "decisions.log"
        self.owner, self.settings, self.src = OWNER, SETTINGS, src
        recs = [dict(r, entry_id="om_%d" % i) for i, r in enumerate(RECORDS)]
        self.ids = ["om_2", "om_1", "om_3", "om_0"]                             # rendered (stored-date) order
        self.gi._OWNER_MEMORY = self.gi._timeline.OwnerMemorySource(fetch=lambda: recs)

        class Cfg(FakeCfg):
            timeline_mode = "live"
        self.Cfg = Cfg

    def tearDown(self):
        self.gi._tc.begin()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def route(self, message, lean_text="hey", mode="live"):
        gi, seen = self.gi, {}
        self.Cfg.timeline_mode = mode
        gi._config.load = lambda: self.Cfg(self.log, live=True)
        gi._canonical_memory.load_settings = lambda home, **kw: self.settings
        gi._canonical_memory.turn_note = lambda *a, **kw: None
        gi._platform_name = lambda s: "telegram"
        gi._groq_runtime = lambda runner, cfg: ({"api_key": "k"}, "")

        def reply(**kw):
            seen.update(kw)
            return (lean_text, "") if lean_text else (None, "lean_error")
        gi._social_lean.reply = reply
        ctx = types.SimpleNamespace(source=self.src(user_id=self.owner, chat_id=self.owner, chat_type="dm"),
                                    message=message, session_key="k:" + message[:12])
        out = gi.route_turn(runner=None, ctx=ctx, model="m", runtime_kwargs={}, turn_route={}, combined_ephemeral="")
        return out, seen, gi._tc.current()

    def test_record_level_lean_success_gets_the_plain_note(self):
        out, seen, ctx = self.route("hehe how was my name stored before I corrected it?")
        if "final_response" not in out:
            self.skipTest("classifier sent this message off the social path")
        self.assertIn(self.gi._timeline.HEADER, seen["policy"])
        self.assertNotIn("check your past conversations", seen["policy"])
        s = ctx.summary()
        self.assertEqual((s["timeline_delivered"], s["timeline_delivered_ids"]), ("lean", self.ids))

    def test_record_level_lean_failure_falls_back_with_search_wording(self):
        out, seen, ctx = self.route("hehe how was my name stored before I corrected it?", lean_text=None)
        self.assertNotIn("final_response", out)
        self.assertIn(self.gi._timeline.AGENT_HEADER, out["turn_hint"])
        self.assertNotIn(self.gi._timeline.HEADER, out["turn_hint"])
        self.assertEqual(ctx.summary()["timeline_delivered"], "agent")
        self.assertEqual(ctx.summary()["timeline_delivered_ids"], self.ids)

    def test_event_level_never_takes_the_lean_call(self):
        out, seen, ctx = self.route("hehe when did I move to Manchester?")
        self.assertEqual(seen, {})                                              # lean reply never called
        self.assertIn(self.gi._timeline.AGENT_HEADER, out["turn_hint"])
        self.assertEqual(ctx.summary()["timeline_delivered"], "agent")

    def test_shadow_routes_exactly_as_before(self):
        out, seen, ctx = self.route("hehe when did I move to Manchester?", mode="shadow")
        self.assertNotIn("timeline", json.dumps(out.get("turn_hint") or ""))
        self.assertNotIn("check your past conversations", json.dumps(out))
        self.assertIsNone(ctx.summary().get("timeline_delivered"))
        rec_ = [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines() if '"timeline"' in l][-1]
        self.assertEqual((rec_["mode"], rec_["applied"], rec_["escalate"]), ("shadow", False, True))


if __name__ == "__main__":
    unittest.main()
