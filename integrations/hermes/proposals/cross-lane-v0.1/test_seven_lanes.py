"""The seven-lane suite: all seven lanes in shadow on one assembled home, on the real gateway, adapter and Core API. TEST_ONLY; no network.

    python -B integrations/hermes/proposals/cross-lane-v0.1/test_seven_lanes.py

This is integrated SOURCE, not an integrated HOST: seven lanes are not installed together anywhere. Bytes: the e1 release router, the dev-ethics-hardening adapter and
ethics.py, and the counts-only planning.py and motivation.py, each checked against the e1 verifier's pins. COVERAGE-MATRIX.md says what ran, what is simulated and what is planned.
"""

from __future__ import annotations

import gc
import hashlib
import importlib
import json
import re
import shutil
import socket
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REL = REPO / "integrations" / "hermes" / "release"
O = REPO / "integrations" / "hermes" / "overlays"
sys.path.insert(0, str(REL / "dev-f9c2-cog1-wm1-g1-r1-w1" / "tests"))
sys.path.insert(0, str(REL / "dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1" / "tests"))

import test_w1_workspace as W  # noqa: E402
import test_p1_release as PR  # noqa: E402

C = W.C
CANARY = "TEST_ONLY_CROSS_LANE_CANARY_7X"
GATE_PORT = 9911
E1 = REL / "dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1"
FIVE = lambda world: ["/os/goals?limit=200", "/os/goals/focus", "/os/drafts?limit=200", "/os/tasks?limit=200", world]
W14 = "/os/world?entity_type=career.application&entity_id=14"
SEVEN = ("cognitive", "goal", "reasoning", "workspace", "motivation", "planning", "ethics")

# message, then the records in order on an EMPTY store, then the reads. Each row is measured, reviewed, then pinned.
OWNERSHIP = (
    # one lane owns
    ("what do you know about application 14?", ["cognitive", "routing"], 0),
    ("which goal has priority?", ["goal", "routing"], 0),
    ("what are my options for application 14?", ["motivation", "workspace", "reasoning", "cognitive", "routing"], 5),
    ("what information is missing to resolve this?", ["motivation", "workspace", "reasoning", "routing"], 5),
    ("plan how to follow up on application 14 but do not do it", ["planning", "routing"], 6),
    ("is it okay to lie on my cover letter?", ["ethics", "routing"], 5),
    ("is it ok to send my salary to the recruiter without asking me?", ["ethics", "cognitive", "routing"], 6),
    ("is it ok to say I managed a team when I didn't?", ["ethics", "routing"], 5),
    # false matches: no lane, no read
    ("hey how are you", ["routing"], 0),
    ("make a plan for dinner", ["routing"], 0),
    ("plan a trip to Lisbon", ["routing"], 0),
    ("is it ok to wear jeans?", ["routing"], 0),
    ("is it fair that my team lost?", ["routing"], 0),
    ("what are the risks of eating sushi?", ["routing"], 0),
    ("what are my options on Netflix tonight?", ["routing"], 0),
    ('the book is called "is it ethical to lie on your resume"', ["routing"], 0),
    ("translate 'plan the job search' into French", ["routing"], 0),
    ("I would never lie on my cv", ["routing"], 0),
    ("how can I tell if a recruiter is lying?", ["cognitive", "routing"], 0),   # not Ethics: it asks about someone else
    # two lanes could claim it
    ("what are the risks of accepting this offer?", ["motivation", "workspace", "reasoning", "routing"], 5),
    ("what are the ethical risks of contacting the recruiter?", ["ethics", "cognitive", "routing"], 6),
    ("is it ethical to plan a follow up on application 14?", ["ethics", "cognitive", "routing"], 5),
    ("is it fair to reject this offer after accepting it?", ["ethics", "routing"], 5),
    # two intents in one message
    ("what are my options for application 14, and which goal has priority?", ["cognitive", "goal", "routing"], 0),   # Reasoning yields; the options go unanswered
    ("plan how to follow up on application 14 and tell me which goal has priority", ["goal", "routing"], 0),
    ("draft a follow up for application 14 and is it ok to lie in it?", ["ethics", "cognitive", "routing"], 5),
    ("what is pending, and what are my options for application 14?", ["cognitive", "routing"], 0),   # same
)
FORBIDDEN = ("goal_ref", "subject_target", "plan_snapshot_id", "relatedGoalIds", "resolutionConditions", "selected_primary_id", "private_app_id", "ethicalSnapshotId", "normalizedIntent", "userIntent")


def setUpModule():
    W.setUpModule()
    router = (E1 / "home/router.yaml").read_text(encoding="utf-8").replace("/home/lilith/.hermes-dev/logs/lilith-router-decisions.log", C.LOG.as_posix())
    (C.HOME / "lilith_router" / "router.yaml").write_text(router, encoding="utf-8")
    for source, name in (("dev-motivation-private-trace/lilith_router/motivation.py", "motivation.py"), ("dev-planning-hardening/lilith_router/planning.py", "planning.py"),
                         ("dev-ethics-hardening/lilith_router/world_context.py", "world_context.py"), ("dev-ethics-hardening/lilith_router/ethics.py", "ethics.py")):
        shutil.copy2(O / source, C.HOME / "lilith_router" / name)
    importlib.reload(C.STATE["wc"])


def tearDownModule():
    gc.collect()
    C.tearDownModule()


class Lanes(W.Base):
    def setUp(self):
        super().setUp()
        self.wc._READ_MEMO.clear()
        self.attempts = []
        real = socket.socket.connect

        def guarded(sock, address):
            # The in-process test client's own loopback pipe is allowed. The provider gate and anything off the host are refused and counted.
            if not isinstance(address, tuple) or address[0] not in ("127.0.0.1", "::1") or address[1] == GATE_PORT:
                self.attempts.append(repr(address))
                raise OSError("TEST_ONLY network blocked")
            return real(sock, address)
        patcher = mock.patch.object(socket.socket, "connect", guarded)
        patcher.start()
        self.addCleanup(patcher.stop)

    def turn(self, message, session):
        self.wc._READ_MEMO.clear()
        self.bridge.calls.clear()
        result = self.route(message, session)
        records = self.new_log()
        self.log0 += len(records)
        return result, records, [p for p, _ in self.bridge.calls]

    def populate(self, db):
        core = C.STATE["core"]
        conn = core._goals_db()
        core._create_goal_impl(conn, {"type": "test_only.synthetic", "title": f"{CANARY} goal", "source": "SYSTEM_MAINTENANCE", "owner": "user", "priority": "HIGH", "goalId": "g.test-only-x"})
        core._create_goal_impl(conn, {"type": "test_only.synthetic", "title": f"{CANARY} other", "source": "SYSTEM_MAINTENANCE", "owner": "user", "priority": "NORMAL", "goalId": "g.test-only-y"})
        conn.close()
        conn = sqlite3.connect(db)
        conn.execute("UPDATE goal SET lifecycle_state='BLOCKED', blocked_reason=?, blocked_by_json=? WHERE goal_id='g.test-only-y'", (f"{CANARY} reason", json.dumps(["t.test-only-x"])))
        conn.execute("INSERT INTO drafts (draft_id, schema_version, kind, status, target_type, target_id, subject, body, content_hash, idempotency_key, created_at, updated_at) "
                     "VALUES ('d.test-only-x', 1, 'followup', 'created', 'career.application', '14', ?, ?, 'h', 'k', 1, 1)", (f"{CANARY} subject", f"{CANARY} body"))
        conn.execute("INSERT INTO tasks (task_id, schema_version, revision, source, kind, status, title, created_at, updated_at, record_json) VALUES ('t.test-only-x', 1, 1, 'system', 'test_only', 'queued', ?, 1, 1, ?)",
                     (f"{CANARY} task", json.dumps({"taskId": "t.test-only-x", "title": f"{CANARY} task", "status": "queued"})))
        conn.execute("INSERT INTO world_belief (key, entity_type, entity_id, predicate, value_json, lifecycle_state, epistemic_state, confidence, confidence_tier, confidence_basis, created_at, updated_at, revision) "
                     "VALUES ('b.test-only-x', 'career.application', '14', 'status', ?, 'ACTIVE', 'OBSERVED', 0.5, 'low', 'b', 'n', 'n', 1)", (json.dumps(f"{CANARY} belief"),))
        conn.commit(); conn.close()

    def assert_private(self, records, label):
        raw = json.dumps(records)
        for secret in (CANARY, "TEST_ONLY", "g.test-only", "d.test-only", "t.test-only", "b.test-only"):
            self.assertNotIn(secret, raw, label)
        for key in FORBIDDEN:
            self.assertNotIn(f'"{key}"', raw, label)
        self.assertNotRegex(raw, r"wc\.[0-9a-f]{16}", label)
        self.assertNotRegex(raw, r'"app_id": "', label)


class Ownership(Lanes):
    def test_every_message_class_on_an_empty_store(self):
        W.bootstrap_drafts("x-own")
        for i, (message, lanes, reads) in enumerate(OWNERSHIP):
            with self.subTest(message=message):
                result, records, calls = self.turn("TEST_ONLY " + message, f"x-own-{i}")
                self.assertIsNone(result)
                self.assertEqual([r.get("lane", "routing") for r in records], lanes)
                self.assertEqual(len(calls), reads)

    def test_no_lane_is_left_out_of_the_table(self):
        seen = {lane for _, lanes, _ in OWNERSHIP for lane in lanes}
        self.assertLessEqual(set(SEVEN), seen)


class Stores(Lanes):
    def test_records_stay_private_on_both_stores(self):
        for name, populate in (("x-e", False), ("x-p", True)):
            db = W.bootstrap_drafts(name)
            if populate:
                self.populate(db)
            for i, (message, _, _) in enumerate(OWNERSHIP):
                self.assert_private(self.turn("TEST_ONLY " + message, f"{name}-{i}")[1], message)

    def test_an_empty_store_never_changes(self):
        db = W.bootstrap_drafts("x-w")
        before = C.rows(db), C.schema(db)
        for i, (message, _, _) in enumerate(OWNERSHIP):
            self.turn("TEST_ONLY " + message, f"x-w-{i}")
        self.assertEqual((C.rows(db), C.schema(db)), before)
        self.assertEqual(self.wc.status()["writes_refused"], 0)

    def test_a_populated_store_changes_only_by_the_known_focus_trace(self):
        # The one write left: a focus read records a trace when a goal exists. Blocker A2/PROD-5. Everything else must stay byte-identical.
        db = W.bootstrap_drafts("x-t")
        self.populate(db)
        tables = ("goal", "drafts", "tasks", "world_belief")
        def snapshot():
            conn = sqlite3.connect(db)
            try:
                return {t: conn.execute(f'SELECT * FROM "{t}" ORDER BY 1').fetchall() for t in tables}
            finally:
                conn.close()
        before, schema, traces = snapshot(), C.schema(db), C.rows(db)["goal_trace"][0]
        focus_reads = 0
        for i, (message, _, _) in enumerate(OWNERSHIP):
            focus_reads += self.turn("TEST_ONLY " + message, f"x-t-{i}")[2].count("/os/goals/focus")
        self.assertEqual(snapshot(), before)
        self.assertEqual(C.schema(db), schema)
        self.assertGreater(C.rows(db)["goal_trace"][0], traces)
        self.assertLessEqual(C.rows(db)["goal_trace"][0], traces + focus_reads)

    def test_populated_stores_reach_the_lanes(self):
        db = W.bootstrap_drafts("x-q")
        self.populate(db)
        _, records, _ = self.turn("TEST_ONLY what are my options for application 14?", "x-q")
        by_lane = {r.get("lane"): r for r in records}
        self.assertGreater(by_lane["workspace"]["trace"]["candidate_count"], 0)
        self.assertNotEqual(by_lane["motivation"]["trace"]["highest_intensity_class"], "SATISFIED")
        plan = next(r for r in self.turn("TEST_ONLY plan the steps for the job search", "x-q2")[1] if r.get("lane") == "planning")
        self.assertTrue(plan["trace"]["goal_ref_present"])


class Budgets(Lanes):
    def test_no_turn_reaches_the_network_or_loads_a_model_path(self):
        W.bootstrap_drafts("x-n")
        for i, (message, _, _) in enumerate(OWNERSHIP):
            self.turn("TEST_ONLY " + message, f"x-n-{i}")
        self.assertEqual(self.attempts, [])
        self.assertNotIn("lilith_router.reasoning", sys.modules)

    def test_no_turn_exceeds_six_reads_or_repeats_a_route(self):
        db = W.bootstrap_drafts("x-b")
        self.populate(db)
        for i, (message, _, _) in enumerate(OWNERSHIP):
            _, _, calls = self.turn("TEST_ONLY " + message, f"x-b-{i}")
            self.assertLessEqual(len(calls), 6, message)
            self.assertEqual(len(calls), len(set(calls)), message)

    def test_a_gated_lane_keeps_ethics_advisory_and_deterministic(self):
        W.bootstrap_drafts("x-a")
        for i, message in enumerate(("is it okay to lie on my cover letter?", "is it ethical to contact the recruiter's manager?")):
            trace = next(r for r in self.turn("TEST_ONLY " + message, f"x-a-{i}")[1] if r.get("lane") == "ethics")["trace"]
            self.assertEqual((trace["candidate_source"], trace["authoritative_policy_evaluation"]), ("deterministic", False))


class ExactReads(Lanes):
    """The window's turns: the routes themselves, in order, not only how many."""
    TURNS = (("what are my options for application 14?", FIVE(W14)), ("what information is missing to resolve this?", FIVE("/os/world")), ("which goal has priority?", []), ("hey how are you", []),
             ("plan how to follow up on application 14 but do not do it", FIVE(W14) + ["/os/drafts?target_id=14"]), ("make a plan for dinner", []), ("is it okay to lie on my cover letter?", FIVE("/os/world")), ("is it ok to wear jeans?", []),
             ("what are the risks of accepting this offer?", FIVE("/os/world")), ("should we share my private legal records with the recruiter?", FIVE("/os/world") + ["/os/world?entity_type=career.application"]))

    def test_each_turn_reads_exactly_these_routes(self):
        W.bootstrap_drafts("x-r")
        for i, (message, routes) in enumerate(self.TURNS):
            with self.subTest(message=message):
                self.assertEqual(self.turn("TEST_ONLY " + message, f"x-r-{i}")[2], routes)

    def test_every_read_succeeds(self):
        W.bootstrap_drafts("x-g")
        for i, (message, _) in enumerate(self.TURNS):
            self.turn("TEST_ONLY " + message, f"x-g-{i}")
            self.assertFalse([c for c in self.bridge.calls if c[1] != 200], message)


class Identity(Lanes):
    def test_no_value_links_two_sessions(self):
        """The same message in two sessions: nothing in a record may repeat that could follow a person across them. Fixed labels and counts may."""
        W.bootstrap_drafts("x-i")
        for i, (message, _, _) in enumerate(OWNERSHIP):
            first = self.turn("TEST_ONLY " + message, f"x-i-a{i}")[1]
            second = self.turn("TEST_ONLY " + message, f"x-i-b{i}")[1]
            pattern = re.compile(r"\b[0-9a-f]{12,}\b|\b(?:g|d|t|ps|wc|turn)[.:][0-9a-z-]{6,}")
            self.assertFalse(set(pattern.findall(json.dumps(first))) & set(pattern.findall(json.dumps(second))), message)

    def test_a_populated_store_adds_no_identifier(self):
        db = W.bootstrap_drafts("x-j")
        self.populate(db)
        for i, (message, _, _) in enumerate(OWNERSHIP):
            for record in self.turn("TEST_ONLY " + message, f"x-j-{i}")[1]:
                self.assertIsNone((record.get("intent") or {}).get("app_id"), message)


class ReleaseBytes(unittest.TestCase):
    """This suite must test what e1 would install, not a copy that drifted."""

    def pin(self, name):
        text = (E1 / "templates/bin/verify_release.py.tmpl").read_bytes().decode("utf-8")
        return re.search(name + r' = "([0-9a-f]{64})"', text).group(1)

    def digest(self, path):
        return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

    def test_the_lanes_under_test_are_the_pinned_bytes(self):
        home = C.HOME / "lilith_router"
        for name, member in (("WORLD_CONTEXT_ADAPTER_SHA256", "world_context.py"), ("ETHICS_SHA256", "ethics.py"), ("PLANNING_SHA256", "planning.py")):
            self.assertEqual(self.digest(home / member), self.pin(name), member)

    def test_the_router_under_test_is_the_release_router(self):
        got = (C.HOME / "lilith_router/router.yaml").read_bytes().replace(b"\r\n", b"\n").decode("utf-8").replace(C.LOG.as_posix(), "/home/lilith/.hermes-dev/logs/lilith-router-decisions.log")
        self.assertEqual(got, (E1 / "home/router.yaml").read_bytes().replace(b"\r\n", b"\n").decode("utf-8"))


class Failures(Lanes):
    def test_a_core_api_outage_fails_open_on_every_message(self):
        W.bootstrap_drafts("x-o")

        class Down:
            def open(self, req, timeout=None):
                raise OSError("TEST_ONLY down")
        self.wc._OPENER = Down()
        for i, (message, _, _) in enumerate(OWNERSHIP):
            self.assertIsNone(self.route("TEST_ONLY " + message, f"x-o-{i}"), message)
        self.assertEqual(self.wc._READ_MEMO, {})

    def test_a_lane_that_raises_does_not_stop_the_turn(self):
        W.bootstrap_drafts("x-r")
        for name, message in (("build_planning_input", "plan how to follow up on application 14"), ("build_ethical_input", "is it okay to lie on my cover letter?"),
                              ("build_attention_candidates", "what are my options for application 14?"), ("build_motivation_snapshot", "what are my options for application 14?")):
            with self.subTest(entry=name), mock.patch.object(self.wc, name, side_effect=RuntimeError("TEST_ONLY")):
                self.assertIsNone(self.route("TEST_ONLY " + message, f"x-r-{name}"))

    def test_a_corrupt_core_api_reply_fails_open(self):
        W.bootstrap_drafts("x-c")

        class Bad:
            def open(self, req, timeout=None):
                class Reply:
                    status = 200
                    def read(self, *a):
                        return b"{not json"
                    def __enter__(self):
                        return self
                    def __exit__(self, *a):
                        return False
                return Reply()
        self.wc._OPENER = Bad()
        self.assertIsNone(self.route("TEST_ONLY what are my options for application 14?", "x-c"))
        self.assertEqual(self.wc._READ_MEMO, {})


class Startup(PR.VerifierBehaviourTest):
    """The merged p1 verifier, run again here. It must refuse Ethics, because no installed release has seven lanes."""


del PR.VerifierBehaviourTest  # only the subclass above should run


if __name__ == "__main__":
    unittest.main()
