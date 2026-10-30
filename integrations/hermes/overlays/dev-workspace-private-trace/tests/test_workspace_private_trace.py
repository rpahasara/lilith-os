"""Counts-only Workspace trace (NOT IN ANY RELEASE). TEST_ONLY; no network.

    python -m unittest discover -s integrations/hermes/overlays/dev-workspace-private-trace/tests -p "test_*.py"
"""

from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[3]
BASE = REPO / "integrations/hermes/home/lilith_router/workspace.py"
CAND = HERE / "lilith_router" / "workspace.py"
FORGET = REPO / "integrations/hermes/release/dev-f9c2/bin/hermes_forget_executor.py"
RETENTION = REPO / "integrations/hermes/release/dev-f9c2/systemd/hermes-gateway-dev-retention.service"
ROUTER = REPO / "integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1/home/router.yaml"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CANDS = [{"sourceType": "GOAL", "sourceRef": "goal:g.secret-meaning", "category": "goal", "summary": "TEST_ONLY canary title", "isFocusGoal": True},
         {"sourceType": "TASK", "sourceRef": "task:t1", "category": "task", "summary": "TEST_ONLY canary task"}]


class PrivateTrace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, cls.cand = load(BASE, "ws_base"), load(CAND, "ws_cand")

    def trace(self, module):
        return module.build_trace(module.build_workspace_snapshot([dict(c) for c in CANDS], channel="lilith_os"))

    def test_the_deployed_trace_has_a_stable_id_and_the_candidate_has_none(self):
        self.assertEqual(self.trace(self.base)["candidate_count"], self.trace(self.cand)["candidate_count"])
        raw = json.dumps(self.trace(self.cand))
        self.assertIsNone(re.search(r"wc\.[0-9a-f]{16}", raw))
        self.assertNotIn("_ids", raw)
        self.assertNotIn("selected_primary_id", raw)
        self.assertNotIn("g.secret-meaning", raw)
        self.assertNotIn("TEST_ONLY", raw)

    def test_two_turns_cannot_be_linked_through_the_trace(self):
        a, b = self.trace(self.cand), self.trace(self.cand)
        for t in (a, b):
            t.pop("timestamp"); t.pop("duration_ms")
        self.assertNotEqual(a.pop("correlation_id"), b.pop("correlation_id"))
        self.assertEqual(a, b)

    def test_counts_are_kept(self):
        t = self.trace(self.cand)
        self.assertEqual(t["candidate_count"], 2)
        self.assertEqual(t["selected_secondary_count"] + t["suppressed_count"], 1)
        self.assertEqual(sum(t["source_type_counts"].values()) + t["suppressed_count"], 2)

    def test_only_the_trace_function_changed(self):
        base, cand = (p.read_text(encoding="utf-8").splitlines() for p in (BASE, CAND))
        self.assertEqual(sorted(set(base) - set(cand)), sorted(l for l in base if "candidateId" in l and ("selected_" in l or "suppressed_ids" in l)))
        self.assertEqual(len(set(cand) - set(base)), 2)

    def test_nothing_else_reads_the_removed_keys(self):
        lilith = REPO / "integrations/hermes/home"
        for key in ("selected_primary_id", "selected_secondary_ids", "suppressed_ids"):
            users = [p for p in lilith.rglob("*.py") if key in p.read_text(encoding="utf-8", errors="replace") and p != BASE]
            self.assertEqual(users, [], key)

    def test_retention_and_forget_cover_the_decision_log(self):
        self.assertRegex(FORGET.read_text(encoding="utf-8"), r'PURGE_DIRS = \("logs"')
        self.assertRegex(RETENTION.read_text(encoding="utf-8"), r"find /home/lilith/\.hermes-dev/logs .*-mtime \+7")
        self.assertIn(".hermes-dev/logs/lilith-router-decisions.log", ROUTER.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
