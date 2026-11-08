"""P-1 T-3/T-4/T-5 tools: summarizer never prints text; blinding is deterministic and keyless; scoring is honest."""
import json
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


if __name__ == "__main__":
    unittest.main()
