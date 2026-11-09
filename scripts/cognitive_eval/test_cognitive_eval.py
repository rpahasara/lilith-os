"""P-1 T-3/T-4/T-5 tools: summarizer never prints text; blinding is deterministic and keyless; scoring is honest."""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blind  # noqa: E402
import replay  # noqa: E402
import trace_summary as ts  # noqa: E402

SECRET = "this is private message text"
NOW = 1_800_000_000.0


def log_lines():
    recs = [
        {"ts": NOW - 10, "turn_id": "a" * 16, "mode": "social", "signals": {}, "live": True},
        {"ts": NOW - 10, "turn_id": "a" * 16, "lane": "social_route", "route": "groq_lean"},
        {"ts": NOW - 10, "turn_id": "a" * 16, "lane": "social_cognition_live", "tone_note_keys": ["playful"]},
        {"ts": NOW - 9, "turn_id": "a" * 16, "lane": "turn", "answered_by": "lean", "provider": "groq",
         "model": "qwen/qwen3.8-27b", "tokens_in": 2400, "tokens_out": 100, "duration_ms": 900, "owner": True},
        {"ts": NOW - 5, "turn_id": "b" * 16, "lane": "turn", "answered_by": "agent", "provider": "openai-codex",
         "model": "gpt-5.6-sol", "tokens_in": 9000, "tokens_out": 300, "duration_ms": 6000,
         "fallback_activated": False, "guard_changed": True},
        {"ts": NOW - 86400 * 30, "mode": "social", "preview": SECRET},             # legacy, outside the window
        {"timestamp": "2026-11-08T00:00:00Z", "lane": SECRET},                    # hostile free text as a label
        "not json",
    ]
    return [json.dumps(r) if isinstance(r, dict) else r for r in recs]


class SummaryTests(unittest.TestCase):
    def test_aggregates(self):
        out = ts.summarize(log_lines(), since=NOW - 3600)
        self.assertEqual(out["turn_records"], 2)
        self.assertEqual(out["answered_by"], {"lean": 1, "agent": 1})
        self.assertEqual(out["routes"], {"groq_lean": 1})
        self.assertEqual(out["tone_keys"], {"playful": 1})
        self.assertEqual(out["tokens"]["agent"]["in"], 9000)
        self.assertEqual(out["latency_ms"]["lean"]["p50"], 900)
        self.assertEqual(out["rates"]["guard_changed"], 0.5)
        self.assertEqual(out["lane_records_per_turn"], {"1": 1, "4": 1})

    def test_never_prints_free_text(self):
        everything = json.dumps(ts.summarize(log_lines(), since=None))
        self.assertNotIn(SECRET, everything)
        self.assertIn('"legacy_preview_records": 1', everything)
        self.assertIn("<other>", everything)


SCN = {"s1": {"id": "s1", "history": [["user", "hi"]], "message": "how are you"},
       "s2": {"id": "s2", "history": [], "message": "rough day"}}
RAW = [{"id": "s1", "replies": {"A": ["a1", "a2"], "B": ["b1", "b2"]}},
       {"id": "s2", "replies": {"A": ["a3", None], "B": ["b3", "b4"]}}]


class BlindTests(unittest.TestCase):
    def test_deterministic_and_keyless(self):
        md1, key1, tpl = blind.make(RAW, SCN, "x")
        md2, key2, _ = blind.make(RAW, SCN, "x")
        self.assertEqual((md1, key1), (md2, key2))
        self.assertEqual(len(key1), 7)                          # the None reply is not shown
        self.assertEqual(set(tpl), set(key1))
        self.assertNotIn('"A"', md1)
        self.assertNotIn("[A]", md1)
        self.assertNotEqual(blind.make(RAW, SCN, "y")[1], key1)

    def test_score_with_ties_and_skips(self):
        key = {"s1#1": "A", "s1#2": "B", "s2#1": "A", "s2#2": "B", "s2#3": "B"}
        verdicts = {"s1#1": 4, "s1#2": 2, "s2#1": 3, "s2#2": 3, "s2#3": None}
        out = blind.score(key, verdicts)
        self.assertEqual(out["scenario_wins"], {"A": 1})
        self.assertEqual((out["scenario_ties"], out["scenarios_compared"], out["skipped"]), (1, 2, 1))
        self.assertEqual(out["ratings"]["A"], {"n": 2, "mean": 3.5})


class ReplayLoopTests(unittest.TestCase):
    def test_budget_stops_sampling_and_errors_are_recorded(self):
        calls = []

        def run(scn, variant):
            calls.append(scn["id"])
            if variant.get("boom"):
                raise RuntimeError("x")
            return "reply", 400, 10
        spec = {"samples": 2, "budget_tokens": 1000, "scenarios": list(SCN.values()),
                "variants": {"A": {}, "B": {"boom": True}}}
        out = replay.replay(spec, run)
        self.assertEqual(out[0]["replies"]["A"], ["reply", "reply"])
        self.assertTrue(out[0]["replies"]["B"][0].startswith("<<ERROR RuntimeError"))
        self.assertEqual(out[1]["replies"]["A"], ["reply", None])   # budget (1000) reached after 3 × 400
        self.assertEqual(len(calls), 5)

    def test_shipped_scenarios_are_synthetic_and_well_formed(self):
        spec = json.loads((Path(__file__).parent / "scenarios" / "social_tone_v1.json").read_text(encoding="utf-8"))
        self.assertEqual(len(spec["scenarios"]), 14)
        for s in spec["scenarios"]:
            self.assertEqual(set(s), {"id", "history", "message"})
        self.assertLessEqual(spec["budget_tokens"], 50000)


class P2EvalTests(unittest.TestCase):
    """P-2 E-2/E-6: the arms reuse the deployed social_preferences module; metrics never print reply text."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "deploy/prod"))
        from lilith_router import social_preferences
        cls.sp = social_preferences
        import metrics
        cls.metrics = metrics

    def test_preference_arms(self):
        prof = ["Works nights.", "Preference (technical): no emoji.", "Boundary: Don't call me 'champ'."]
        scn = {"message": "how do I rebase?"}
        self.assertEqual(replay.preference_parts(scn, {}, self.sp, True), ("", None))
        p, note = replay.preference_parts(scn, {"profile": prof}, self.sp, True)
        self.assertTrue(p.startswith("[About them]\nWorks nights.") and note is None)
        _, note = replay.preference_parts(scn, {"profile": prof, "preferences": "router"}, self.sp, True)
        self.assertIn("- Preference: no emoji.", note)
        _, note = replay.preference_parts(scn, {"profile": prof, "preferences": "router"}, self.sp, False)
        self.assertNotIn("no emoji", note)                                     # technical scope, casual turn
        _, note = replay.preference_parts({"message": "don't call me that"}, {"profile": prof, "preferences": "router"},
                                          self.sp, False)
        self.assertTrue(note.startswith(self.sp.CORRECTION_HINT))

    def test_metrics(self):
        spec = {"scenarios": [{"id": "s1", "kind": "applies", "emoji": "none", "forbid": ["\\bchamp"]},
                              {"id": "s2", "kind": "unrelated", "emoji": "some", "expect": ["probe"]}]}
        raw = [{"id": "s1", "replies": {"A": ["hey champ 🎉", SECRET], "C": ["hello"]},
                "tokens": {"A": [10, 20], "C": [30]}, "latency_ms": {"A": [5, 7], "C": [9]}},
               {"id": "s2", "replies": {"A": ["a probe 🙂"], "C": ["<<ERROR X >>"]}}]
        out = self.metrics.measure(raw, spec)
        self.assertEqual(out["arms"]["A"], {"applies:emoji_ok": "1/2", "applies:forbid_hit": "1/2",
                                            "unrelated:emoji_ok": "1/1", "unrelated:expect_hit": "1/1"})
        self.assertEqual(out["errors"], {"C": 1})
        self.assertEqual(out["cost"]["A"], {"mean_tokens": 15, "mean_latency_ms": 6, "n": 2})
        self.assertNotIn(SECRET, json.dumps(out))

    def test_shipped_p2_specs_are_synthetic_and_in_budget(self):
        for name in ("p2_e2_preferences_v1.json", "p2_e6_corrections_v1.json"):
            text = (Path(__file__).parent / "scenarios" / name).read_text(encoding="utf-8")
            self.assertFalse(any(ord(c) < 32 and c != "\n" for c in text), name)   # e.g. a shell-mangled \b
            spec = json.loads(text)
            for s in spec["scenarios"]:
                for p in s.get("forbid", []) + s.get("expect", []):
                    re.compile(p)
            self.assertEqual(set(spec["variants"]), {"A", "B", "C"})
            self.assertEqual(spec["variants"]["C"].get("preferences"), "router")
            self.assertLessEqual(spec["budget_tokens"], 50000)
            self.assertEqual(len(spec["scenarios"]), 8)
            for s in spec["scenarios"]:
                self.assertIn(s.get("kind"), ("applies", "unrelated", "explicit"))


class P3EvalTests(unittest.TestCase):
    """P-3 E-5: the meta arm reuses the deployed metacognition module; the spec's gate fires on gap scenarios only."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "deploy/prod"))

    def test_meta_arm_fires_on_gap_scenarios_only(self):
        spec = json.loads((Path(__file__).parent / "scenarios/p3_e5_recall_gap_v1.json").read_text(encoding="utf-8"))
        for s in spec["scenarios"]:
            for pat in s.get("expect", []) + s.get("forbid", []):
                re.compile(pat)
                self.assertFalse(re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", pat), s["id"])
            prof, _ = replay.preference_parts(s, spec["variants"]["B"], None, False)
            self.assertIsNone(replay.meta_note(s, spec["variants"]["A"], prof))
            fired = replay.meta_note(s, spec["variants"]["B"], prof) is not None
            self.assertEqual(fired, s["kind"] == "applies", s["id"])

    def test_spec_patterns_accept_typographic_apostrophes(self):
        for name in ("p3_e5_recall_gap_v1.json", "p3_e4_appraisal_v1.json"):
            spec = json.loads((Path(__file__).parent / "scenarios" / name).read_text(encoding="utf-8"))
            for s in spec["scenarios"]:
                for pat in s.get("expect", []) + s.get("forbid", []):
                    if "'" in pat:
                        self.assertIn("\u2019", pat, (name, s["id"]))      # the model writes ’ (N-47)

    def test_appraisal_arm_reuses_the_deployed_mapping(self):
        from lilith_router import classifier as cl
        spec = json.loads((Path(__file__).parent / "scenarios/p3_e4_appraisal_v1.json").read_text(encoding="utf-8"))
        changed = 0
        for s in spec["scenarios"]:
            for pat in s.get("expect", []) + s.get("forbid", []):
                re.compile(pat)
                self.assertFalse(re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", pat), s["id"])
            f = replay._focused(cl, s)
            a, b = replay.style_parts(s, spec["variants"]["A"], f), replay.style_parts(s, spec["variants"]["B"], f)
            self.assertIsNone(a[1])                                       # the baseline arm never gets a goal line
            changed += int(a != b)
        self.assertGreaterEqual(changed, 6)


class ApprovalFatigueTests(unittest.TestCase):
    """P-4 P4-2: proposals grouped by id across L18 kinds and pending files; counts only."""

    def test_outcomes_rates_and_gate(self):
        import approval_fatigue as af
        now = 1_800_000_000.0
        day = 86400
        ev = [
            {"kind": "PROPOSED", "proposal_id": "p1", "at": now - 3 * day, "source": "hermes", "text": "SECRET-1"},
            {"kind": "APPROVED", "proposal_id": "p1", "at": now - 2 * day},
            {"kind": "APPROVED", "proposal_id": "p1", "at": now - 2 * day},          # second item, same proposal
            {"kind": "APPROVED", "proposal_id": "p2", "at": "2027-01-15T08:00:00Z"},  # fast approval: no PROPOSED
            {"kind": "PROPOSED", "proposal_id": "p3", "at": now - 4 * day, "source": "hermes"},
            {"kind": "REJECTED", "proposal_id": "p3", "at": now - 4 * day},
            {"kind": "PROPOSED", "proposal_id": "p4", "at": now - 20 * day, "source": "some free text"},  # gone
            {"kind": "PROPOSED", "proposal_id": "p5", "at": now - 10 * day, "source": "hermes"},  # pending > 7 d
            {"kind": "PROPOSED", "proposal_id": "p6", "at": now - 1 * day, "source": "hermes"},   # pending, young
            {"kind": "IMPORTED", "proposal_id": None, "at": now},
            {"kind": "SUPERSEDED", "proposal_id": "p1", "at": now}]
        props = af.classify(ev, [("p5", None), ("p6", now - day)], now)
        got = {k: v["outcome"] for k, v in props.items()}
        self.assertEqual(got, {"p1": "approved", "p2": "approved", "p3": "rejected", "p4": "ignored",
                               "p5": "ignored", "p6": "pending"})
        self.assertEqual(props["p4"]["source"], "other")                       # free text never passes through
        s = af.summarize(props, now)
        self.assertEqual(s["total"]["fatigue_rate"], 0.6)                       # (1 rejected + 2 ignored) / 5
        self.assertEqual(s["gate"], "TIGHTEN")
        self.assertNotIn("SECRET", json.dumps(s))
        self.assertEqual(af.summarize({}, now)["total"]["fatigue_rate"], None)


class CommitmentOutcomesTests(unittest.TestCase):
    """P-4 P4-5a: E-7 counts from commitment goals, their traces, the sync state and the promise flags."""

    def test_outcomes_rate_gate_and_no_text(self):
        import commitment_outcomes as co
        now = 1_800_000_000.0
        iso = lambda ts: __import__("datetime").datetime.fromtimestamp(ts, __import__("datetime").timezone.utc).isoformat()
        g = lambda gid, st, typ="commitment.once", job=None: {
            "goalId": gid, "type": typ, "lifecycleState": st, "createdAt": iso(now - 3600),
            "title": "SECRET TITLE", "target": {"type": "hermes.cron", "id": job or gid}}
        goals = [g("a", "COMPLETED"), g("b", "COMPLETED"), g("c", "FAILED"), g("d", "BLOCKED"), g("e", "CANCELLED"),
                 g("f", "ACTIVE"), g("r", "ACTIVE", "commitment.routine")]
        traces = {"a": [("PENDING", "goal_created"), ("ACTIVE", "accepted"),
                        ("COMPLETED", "the scheduled run completed at X; the scheduler recorded no delivery error")],
                  "b": [("ACTIVE", "x"), ("BLOCKED", "missed"), ("ACTIVE", "y"),
                        ("COMPLETED", "the scheduled run completed at X; delivery to the chat not verified")]}
        state = {"v": 2, "jobs": {"a": {}, "d": {"held": "run in progress"}}, "unattributed_runs_24h": 1}
        promises = [{"promise": True, "scheduled": True, "unbacked_promise": False},
                    {"promise": True, "scheduled": False, "unbacked_promise": True}, {"unbacked_promise": False}]
        s = co.summarize(goals, traces, state, promises, now)
        self.assertEqual({k: s["one_time"][k] for k in ("kept_on_time", "kept_late", "failed", "missed_open",
                                                       "cancelled", "open", "total")},
                         {"kept_on_time": 1, "kept_late": 1, "failed": 1, "missed_open": 1, "cancelled": 1, "open": 1,
                          "total": 6})
        self.assertEqual(s["e7_rate"], 0.5)                                 # 2 kept / (2 + 1 failed + 1 missed)
        self.assertEqual(s["e7_gate"], "BELOW_BAR")
        self.assertEqual(s["delivery_evidence_on_kept"], {"no_error_recorded": 1, "not_verified": 1})
        self.assertEqual(s["routine"], {"ACTIVE": 1, "total": 1})
        self.assertEqual((s["sync"]["held"], s["sync"]["unattributed_runs_24h"]), (1, 1))
        self.assertEqual((s["promises"]["unbacked_promise"], s["promises"]["turns_checked"]), (1, 3))
        self.assertNotIn("SECRET", json.dumps(s))
        dup = co.summarize(goals[:1] + [g("z", "COMPLETED", job="a")], {}, None, [], now)
        self.assertEqual((dup["duplicate_goals_per_job"], dup["e7_gate"]), (1, "BELOW_BAR"))
        self.assertIsNone(co.summarize([], {}, None, [], now)["e7_rate"])


if __name__ == "__main__":
    unittest.main()
