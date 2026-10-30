"""Measured effects behind PLAN.md: Global Workspace on the real gateway, adapter and Core API. TEST_ONLY; no network.

    python -m unittest discover -s integrations/hermes/proposals/workspace-integration-v0.1 -p "test_*.py"

Reuses the g2 Core API test harness. The router here is a test-only copy (g1 + the flags under test); no release has it.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
G2_TESTS = REPO / "integrations" / "hermes" / "release" / "dev-f9c2-cog1-wm1-g2" / "tests"
sys.path.insert(0, str(G2_TESTS))

import test_g2_core_api_compat as C  # noqa: E402

G1_ROUTER = REPO / "integrations" / "hermes" / "release" / "dev-f9c2-cog1-wm1-g1" / "home" / "router.yaml"
ANALYTIC = "TEST_ONLY what are my options for application 14?"
SOCIAL = "TEST_ONLY hey how are you"
GOAL_Q = "TEST_ONLY which goal has priority?"


def setUpModule():
    C.setUpModule()


def tearDownModule():
    C.tearDownModule()


def router(**flags):
    text = G1_ROUTER.read_text(encoding="utf-8").replace(
        "/home/lilith/.hermes-dev/logs/lilith-router-decisions.log", C.LOG.as_posix())
    for key, value in flags.items():
        text = re.sub(rf"^{key}: .*$", f"{key}: {value}", text, flags=re.M) if re.search(rf"^{key}: ", text, re.M) else text + f"{key}: {value}\n"
    (C.HOME / "lilith_router" / "router.yaml").write_text(text, encoding="utf-8")


class WorkspaceEffects(C.GoalsLiveOnTheRealCoreApiTest):
    """Inherits only the harness; the parent's own tests are not re-run here."""

    def run_turn(self, message, chat, **flags):
        router(**flags)
        db = C.use_db(chat, goal_schema=True)
        before = {r[1] for r in C.schema(db)}
        result = self.route(message, chat)
        return result, [p for p, _ in self.bridge.calls], {r[1] for r in C.schema(db)} - before, self.new_log(), db

    def test_workspace_alone_never_runs_it_needs_a_host_lane(self):
        result, calls, new, log, _ = self.run_turn(ANALYTIC, "ws-alone", workspace_enabled="true", workspace_mode="shadow")
        self.assertEqual((calls, new), ([], set()))
        self.assertFalse([r for r in log if r.get("lane") == "workspace"])
        self.assertIsNone(result)

    def test_reasoning_shadow_alone_is_write_free(self):
        _, calls, new, log, _ = self.run_turn(ANALYTIC, "r-alone", reasoning_enabled="true", reasoning_mode="shadow")
        self.assertEqual((calls, new), ([], set()))
        self.assertEqual([r["lane"] for r in log if "lane" in r], ["reasoning", "cognitive"])   # World Model shadow also matches

    def test_workspace_shadow_reads_every_source_and_creates_the_drafts_table(self):
        result, calls, new, log, _ = self.run_turn(
            ANALYTIC, "ws-on", reasoning_enabled="true", reasoning_mode="shadow",
            workspace_enabled="true", workspace_mode="shadow")
        print("\nWORKSPACE_SHADOW_READS", calls, "NEW_OBJECTS", sorted(new))
        self.assertIsNone(result)                                # the reply path is unchanged in shadow
        self.assertLessEqual({"/os/goals?limit=200", "/os/goals/focus", "/os/drafts?limit=200", "/os/tasks?limit=200"}, set(calls))
        self.assertIn("drafts", new)                             # a GET creates a table on the DEV schema
        self.assertEqual({r["lane"] for r in log if "lane" in r}, {"reasoning", "workspace", "cognitive"})

    def test_workspace_trace_holds_no_message_text(self):
        _, _, _, log, _ = self.run_turn(
            ANALYTIC, "ws-log", reasoning_enabled="true", reasoning_mode="shadow",
            workspace_enabled="true", workspace_mode="shadow")
        raw = C.json.dumps([r for r in log if r.get("lane") == "workspace"])
        self.assertNotIn("TEST_ONLY", raw)
        self.assertNotIn("options", raw)

    def test_a_social_turn_and_a_goal_turn_do_not_run_the_workspace(self):
        for message, chat in ((SOCIAL, "ws-social"), (GOAL_Q, "ws-goal")):
            _, calls, new, log, _ = self.run_turn(
                message, chat, reasoning_enabled="true", reasoning_mode="shadow",
                workspace_enabled="true", workspace_mode="shadow")
            self.assertEqual((calls, new), ([], set()))
            self.assertFalse([r for r in log if r.get("lane") == "workspace"])


for name in [n for n in dir(C.GoalsLiveOnTheRealCoreApiTest) if n.startswith("test_")]:
    if name not in WorkspaceEffects.__dict__:
        setattr(WorkspaceEffects, name, None)
del C.GoalsLiveOnTheRealCoreApiTest   # not collected from this module

if __name__ == "__main__":
    unittest.main()
