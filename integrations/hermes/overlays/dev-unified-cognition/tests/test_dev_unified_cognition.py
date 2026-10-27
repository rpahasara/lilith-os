"""Offline checks for the DEV unified-cognition overlay. TEST_ONLY synthetic data; no model call; sockets blocked.

    python -m unittest discover -s integrations/hermes/overlays/dev-unified-cognition/tests -p "test_*.py"

The candidate HERMES_HOME tree is assembled into a temporary directory and imported from there. A fake opener
stands in for the Core API, so no request leaves the process.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace

OVERLAY = Path(__file__).resolve().parents[1]
REPO = OVERLAY.parents[3]
HOME_SRC = REPO / "integrations" / "hermes" / "home"
sys.path.insert(0, str(OVERLAY / "tools"))
sys.path.insert(0, str(HOME_SRC / "tools"))

import assemble_dev_cognition  # noqa: E402
import assemble_home  # noqa: E402

PROD_SHA = "46b8187e3f6f2ac72c920de9dab12fd9c2841551f6c2aa7c20fd91941e3f0104"
DEV_STUB_SHA = "5c1fbf98ead049013aa79fdfb4e74dd3dd210ab0c3386f257ce0b4e334e6a3d5"
PROBE = Path(__file__).resolve().with_name("_route_probe.py")
LANES = ("cognitive", "goals", "reasoning", "workspace", "motivation", "planning", "ethics")

MESSAGE_CANARY = "TEST_ONLY_MESSAGE_CANARY_7Q"
BELIEF_CANARY = "TEST_ONLY_BELIEF_CANARY_4K"
FORGOTTEN_CANARY = "TEST_ONLY_FORGOTTEN_CANARY_9Z"
MESSAGES = {
    "belief": f"TEST_ONLY what do you believe about application 14? {MESSAGE_CANARY}",
    "pending": f"TEST_ONLY what is pending right now? {MESSAGE_CANARY}",
    "draft": f"TEST_ONLY create a follow-up draft for application 14 {MESSAGE_CANARY}",
    "goal_query": f"TEST_ONLY which goal has priority? {MESSAGE_CANARY}",
    "goal_create": f"TEST_ONLY track application 14 as a goal {MESSAGE_CANARY}",
    "reasoning": f"TEST_ONLY what are my options for application 14? {MESSAGE_CANARY}",
    "planning": f"TEST_ONLY make a plan to follow up on application 14 but do not create anything {MESSAGE_CANARY}",
    "ethics": f"TEST_ONLY is it okay to share my salary with the recruiter? {MESSAGE_CANARY}",
    "social": f"TEST_ONLY hey how are you {MESSAGE_CANARY}",
    "technical": f"TEST_ONLY why is my kubernetes pod pending? {MESSAGE_CANARY}",
}


def _belief(eid, pred, val):
    return {"key": f"career.application:{eid}:{pred}", "entity_type": "career.application", "entity_id": str(eid),
            "predicate": pred, "value": val, "lifecycle_state": "ACTIVE", "epistemic_state": "OBSERVED",
            "confidence": {"value": 0.9, "tier": "high", "basis": "observed"},
            "provenance": [{"source_class": "LIVE_CONNECTOR", "source_id": "career-events", "freshness": "fresh"}]}


WORLD = {"beliefs": [_belief(14, "status", f"interviewing {BELIEF_CANARY}"), _belief(14, "company", "TEST_ONLY Co")],
         "meta": {"total": 2, "conflicted": 0, "stale": 0, "last_reconciled_at": "2026-10-28T00:00:00+00:00"}}
GOAL = {"goalId": "g.test.1", "title": "TEST_ONLY follow up on application 14", "lifecycleState": "ACTIVE",
        "priority": "NORMAL", "source": "USER_REQUESTED", "target": {"type": "career.application", "id": "14"},
        "updatedAt": "2026-10-28T00:00:00+00:00", "createdAt": "2026-10-27T00:00:00+00:00"}
FIXTURES = {
    "/os/world": WORLD,
    "/career/applications": {"applications": [{"id": 14, "role_title": "TEST_ONLY Engineer", "company": "TEST_ONLY Co"}]},
    "/os/tasks": {"tasks": [{"taskId": "t.test.1", "title": "TEST_ONLY review", "status": "waiting_for_approval",
                             "approvalState": "required"}]},
    "/os/drafts": {"drafts": []},
    "/os/goals": {"goals": [GOAL]},
    "/os/goals/focus": {"focus": GOAL, "arbitration": {"alternatives": []}},
    "/memory/USER.md": {"text": FORGOTTEN_CANARY},      # must never be requested
}


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, code=200, content_type="application/json"):
        super().__init__(body)
        self.code, self.headers = code, {"content-type": content_type}

    def getcode(self):
        return self.code

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class FakeOpener:
    """The Core API stand-in. Records every request; never touches a socket."""

    def __init__(self, fixtures=None, error=None, respond=None):
        self.fixtures, self.error, self.respond, self.calls = fixtures or FIXTURES, error, respond, []

    def open(self, req, timeout=None):
        self.calls.append({"method": req.get_method(), "url": req.full_url, "timeout": timeout,
                           "data": req.data})
        if self.error is not None:
            raise self.error
        if self.respond is not None:
            return self.respond(req)
        path = req.full_url.split("127.0.0.1:8765", 1)[1].split("?", 1)[0]
        return FakeResponse(json.dumps(self.fixtures.get(path)).encode("utf-8"))


def yaml_text(log_path: Path, **changes) -> str:
    import yaml
    data = yaml.safe_load((HOME_SRC / "variants" / "dev-f9c2" / "router.yaml").read_text(encoding="utf-8"))
    data["log_path"] = str(log_path)
    data.update(changes)
    return yaml.safe_dump(data)


def all_lanes(mode: str) -> dict:
    changes = {"cognitive_channels": ["lilith_os"]}
    for lane in LANES:
        changes[f"{lane}_enabled"] = True
        changes[f"{lane}_mode"] = mode
    return changes


_TMP = tempfile.TemporaryDirectory(prefix="dev-unified-cognition-")
TMP = Path(_TMP.name)
CANDIDATE = TMP / "candidate" / "hermes-home"
BASELINE = TMP / "baseline" / "hermes-home"
_SOCKET_ATTEMPTS: list = []
_SAVED_SOCKET = {}


def _blocked(*args, **kwargs):
    _SOCKET_ATTEMPTS.append(repr(args[:2]))
    raise OSError("TEST_ONLY network blocked")


def setUpModule():
    assert assemble_dev_cognition.assemble(CANDIDATE) == []
    problems, gaps = assemble_home.assemble("dev-f9c2", BASELINE)
    assert (problems, gaps) == ([], [])
    for name, target in (("connect", socket.socket), ("connect_ex", socket.socket), ("create_connection", socket)):
        _SAVED_SOCKET[name] = (target, getattr(target, name))
        setattr(target, name, _blocked)
    os.environ["HERMES_HOME"] = str(CANDIDATE)
    (CANDIDATE / "lilith_router" / "router.yaml").write_text(yaml_text(TMP / "decisions.log"), encoding="utf-8")
    sys.path.insert(0, str(CANDIDATE))


def tearDownModule():
    for name, (target, original) in _SAVED_SOCKET.items():
        setattr(target, name, original)
    for mod in [m for m in sys.modules if m == "lilith_router" or m.startswith("lilith_router.")]:
        del sys.modules[mod]
    sys.path.remove(str(CANDIDATE))
    _TMP.cleanup()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def code_files(root: Path) -> set:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts}


def probe(home: Path, messages, **changes) -> dict:
    log = home.parent / "probe-decisions.log"
    if log.exists():
        log.unlink()
    scenario = home.parent / "scenario.json"
    scenario.write_text(json.dumps({"router_yaml": yaml_text(log, **changes), "messages": list(messages),
                                    "log_path": str(log)}), encoding="utf-8")
    out = subprocess.run([sys.executable, str(PROBE), str(home), str(scenario)], check=True, cwd=home.parent,
                         capture_output=True, text=True, timeout=120)
    result = json.loads(out.stdout)
    assert (result["identity"]["router_enabled"], result["identity"]["router_mode"]) == (True, "shadow"), result
    return result


class SourceAndManifestTest(unittest.TestCase):
    def test_candidate_tree_is_byte_exact_and_keeps_dev_hardening(self):
        dev = assemble_home.load("dev-f9c2")
        self.assertEqual(sha(CANDIDATE / "lilith_router" / "_prod_world_context.py"), PROD_SHA)
        for rel in ("lilith_router/gateway_integration.py", "plugins/lilith_os/adapter.py",
                    "lilith_router/config.py", "lilith_router/reasoning.py", "lilith_router/memory_store.py"):
            with self.subTest(rel=rel):
                self.assertEqual(sha(CANDIDATE / rel), dev[rel]["sha256"])
        self.assertEqual(code_files(CANDIDATE) - {"lilith_router/router.yaml"},     # written by these tests
                         set(dev) | {"lilith_router/_prod_world_context.py"})

    def test_recovered_prod_source_and_dev_stub_are_untouched(self):
        self.assertEqual(sha(HOME_SRC / "variants" / "prod-lilith-01" / "lilith_router" / "world_context.py"), PROD_SHA)
        self.assertEqual(sha(HOME_SRC / "variants" / "dev-f9c2" / "lilith_router" / "world_context.py"), DEV_STUB_SHA)

    def test_manifest_matches_the_adapter_and_replaces_only_the_stub(self):
        manifest = assemble_dev_cognition.load()
        adapter = manifest["files"]["lilith_router/world_context.py"]
        self.assertEqual(sha(REPO / adapter["source"]), adapter["sha256"])
        self.assertEqual(adapter["replaces"], DEV_STUB_SHA)
        self.assertEqual(set(manifest["files"]), {"lilith_router/world_context.py", "lilith_router/_prod_world_context.py"})

    def test_exports_cover_every_world_context_use_in_the_dev_gateway(self):
        from lilith_router import world_context as wc
        tree = ast.parse((CANDIDATE / "lilith_router" / "gateway_integration.py").read_text(encoding="utf-8"))
        used = {n.attr for n in ast.walk(tree)
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "_world_context"}
        self.assertEqual(used, set(wc.GATEWAY_API))
        for name in wc.GATEWAY_API:
            self.assertTrue(callable(getattr(wc, name)))

    def test_prod_network_io_is_only_in_the_replaced_helpers(self):
        from lilith_router import world_context as wc
        tree = ast.parse((CANDIDATE / "lilith_router" / "_prod_world_context.py").read_text(encoding="utf-8"))
        with_io = {f.name for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)
                   and any(isinstance(n, ast.Attribute) and n.attr == "urlopen" for n in ast.walk(f))}
        self.assertEqual(with_io, {"_get_json", "_post_draft", "_post_goal_json"})
        self.assertIs(wc._LEGACY._get_json, wc._governed_get)
        self.assertIs(wc._LEGACY._post_draft, wc._refused_post_draft)
        self.assertIs(wc._LEGACY._post_goal_json, wc._refused_post_goal_json)
        self.assertTrue(wc.status()["legacy_loaded"])
        self.assertFalse(wc.status()["writes_enabled"])


class BaselineTest(unittest.TestCase):
    def test_flags_off_routing_and_log_equal_the_stub(self):
        base = probe(BASELINE, MESSAGES.values())
        cand = probe(CANDIDATE, MESSAGES.values())
        self.assertEqual(base["identity"]["stub"], True)
        self.assertEqual(cand["identity"]["unified"], True)
        self.assertTrue(cand["identity"]["status"]["legacy_loaded"])
        self.assertEqual(cand["results"], base["results"])
        self.assertEqual(cand["log"], base["log"])
        self.assertEqual(len(cand["log"]), len(MESSAGES))
        self.assertEqual((cand["socket_attempts"], base["socket_attempts"]), ([], []))
        self.assertEqual({k: cand["identity"]["status"][k] for k in ("reads", "reads_refused", "writes_refused")},
                         {"reads": 0, "reads_refused": 0, "writes_refused": 0})

    def test_lanes_on_with_the_stub_still_fail_open(self):
        base = probe(BASELINE, MESSAGES.values(), **all_lanes("live"))
        self.assertEqual(base["socket_attempts"], [])
        self.assertTrue(all(r is None for r in base["results"]))


class InProcessCase(unittest.TestCase):
    def setUp(self):
        from lilith_router import gateway_integration as gi, world_context as wc
        self.gi, self.wc = gi, wc
        self.log = TMP / f"{self.id().rsplit('.', 1)[1]}.log"
        self.opener = FakeOpener()
        self._saved_opener = wc._OPENER
        wc._OPENER = self.opener
        self.stats_before = dict(wc._STATS)
        _SOCKET_ATTEMPTS.clear()

    def tearDown(self):
        self.wc._OPENER = self._saved_opener
        (CANDIDATE / "lilith_router" / "router.yaml").write_text(yaml_text(TMP / "decisions.log"), encoding="utf-8")
        self.assertEqual(_SOCKET_ATTEMPTS, [])

    def configure(self, **changes):
        (CANDIDATE / "lilith_router" / "router.yaml").write_text(yaml_text(self.log, **changes), encoding="utf-8")

    def route(self, key, chat=None):
        chat = chat or f"{self.id().rsplit('.', 1)[1]}-{key}"
        ctx = SimpleNamespace(source=SimpleNamespace(platform=SimpleNamespace(value="lilith_os"), chat_id=chat),
                              session_key=f"agent:lilith_os:{chat}", message=MESSAGES[key])
        return self.gi.route_turn(runner=SimpleNamespace(), ctx=ctx, model="dev-model", runtime_kwargs={},
                                  turn_route={"model": "dev-model"}, combined_ephemeral="TEST_ONLY base",
                                  cached_agent=None)

    def delta(self, key):
        return self.wc._STATS[key] - self.stats_before[key]

    def assert_reads_only_allowlisted(self):
        for call in self.opener.calls:
            self.assertEqual(call["method"], "GET")
            self.assertIsNone(call["data"])
            self.assertTrue(call["url"].startswith("http://127.0.0.1:8765/"))
            self.assertTrue(self.wc._path_allowed(call["url"][len("http://127.0.0.1:8765"):]), call["url"])
            self.assertNotIn("/memory", call["url"])
            self.assertLessEqual(call["timeout"], self.wc.GET_TIMEOUT_MAX)


class ShadowTest(InProcessCase):
    def test_every_lane_in_shadow_reads_only_and_never_changes_routing(self):
        self.configure(**all_lanes("shadow"))
        for key in MESSAGES:
            with self.subTest(message=key):
                self.assertIsNone(self.route(key))
        self.assertTrue(self.opener.calls)                     # shadow is not free: it reads durable state
        self.assert_reads_only_allowlisted()
        self.assertEqual(self.delta("writes_refused"), 0)      # shadow never even attempts a write
        raw = self.log.read_text(encoding="utf-8")
        lanes = {json.loads(line).get("lane") for line in raw.splitlines()}
        self.assertTrue({"cognitive", "goal", "reasoning", "planning", "ethics"} <= lanes, lanes)
        for canary in (MESSAGE_CANARY, BELIEF_CANARY, FORGOTTEN_CANARY, "TEST_ONLY Co"):
            self.assertNotIn(canary, raw)


class LiveLaneTest(InProcessCase):
    """Live lanes against the fake Core API: the integration path works, and it never writes."""

    def test_belief_turn_is_grounded_from_the_world_model(self):
        self.configure(cognitive_enabled=True, cognitive_mode="live", cognitive_channels=["lilith_os"])
        res = self.route("belief")
        self.assertEqual(res["mode"], "cognitive")
        self.assertTrue(res["combined_ephemeral"].startswith("TEST_ONLY base\n\n"))
        self.assertIn("WORLD MODEL BELIEFS", res["combined_ephemeral"])
        self.assertIn(BELIEF_CANARY, res["combined_ephemeral"])
        self.assertNotIn(FORGOTTEN_CANARY, res["combined_ephemeral"])
        self.assert_reads_only_allowlisted()

    def test_pending_turn_reads_durable_tasks_and_drafts(self):
        self.configure(cognitive_enabled=True, cognitive_mode="live", cognitive_channels=["lilith_os"])
        res = self.route("pending")
        self.assertEqual(res["mode"], "cognitive")
        self.assertIn("DURABLE PENDING STATE", res["combined_ephemeral"])
        self.assertIn("TASK t.test.1", res["combined_ephemeral"])

    def test_draft_request_is_never_written_and_the_model_is_told_so(self):
        self.configure(cognitive_enabled=True, cognitive_mode="live", cognitive_channels=["lilith_os"])
        res = self.route("draft")
        self.assertEqual(res["mode"], "cognitive")
        self.assertIn("did not confirm it", res["combined_ephemeral"])
        self.assertNotIn("DURABLE ACTION RESULT:", res["combined_ephemeral"])
        self.assertNotIn("draft has been saved", res["combined_ephemeral"])
        self.assertEqual(self.delta("writes_refused"), 1)
        self.assertFalse([c for c in self.opener.calls if c["method"] != "GET"])

    def test_goal_turns_ground_from_goal_state_and_never_create_a_goal(self):
        self.configure(goals_enabled=True, goals_mode="live", cognitive_channels=["lilith_os"])
        query = self.route("goal_query")
        self.assertEqual(query["mode"], "goal")
        self.assertIn("GOAL g.test.1", query["combined_ephemeral"])
        self.assertIn("CURRENT FOCUS (deterministic arbitration): g.test.1", query["combined_ephemeral"])
        create = self.route("goal_create")
        self.assertEqual(create["mode"], "goal")
        self.assertIn("could not track the goal", create["combined_ephemeral"])
        self.assertEqual(self.delta("writes_refused"), 1)
        self.assertFalse([c for c in self.opener.calls if c["method"] != "GET"])

    def test_planning_proposes_only(self):
        self.configure(planning_enabled=True, planning_mode="live", workspace_enabled=True, workspace_mode="live",
                       motivation_enabled=True, motivation_mode="live", cognitive_channels=["lilith_os"])
        res = self.route("planning")
        self.assertIsNotNone(res)
        self.assertEqual(res["mode"], "planning")
        self.assertTrue(res["final_response"])
        self.assertEqual(self.delta("writes_refused"), 0)
        self.assert_reads_only_allowlisted()
        planning = [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines()
                    if json.loads(l).get("lane") == "planning"]
        self.assertEqual(planning[-1]["planning_mode"], "live")

    def test_ethics_is_advisory_and_read_only(self):
        self.configure(ethics_enabled=True, ethics_mode="live", workspace_enabled=True, workspace_mode="live",
                       cognitive_channels=["lilith_os"])
        res = self.route("ethics")
        self.assertIsNotNone(res)
        self.assertEqual(res["mode"], "ethics")
        self.assertTrue(res["final_response"])
        for verdict in ("ALLOW", "DENY"):
            self.assertNotIn(verdict, res["final_response"])
        self.assertEqual(self.delta("writes_refused"), 0)
        self.assert_reads_only_allowlisted()

    def test_reasoning_gets_bounded_durable_input_and_fails_open_without_a_model(self):
        from lilith_router import reasoning
        prompts = []
        saved = reasoning._default_model_call
        reasoning._default_model_call = lambda prompt: prompts.append(prompt) or "not json"
        try:
            self.configure(reasoning_enabled=True, reasoning_mode="live", workspace_enabled=True,
                           workspace_mode="live", motivation_enabled=True, motivation_mode="live",
                           cognitive_channels=["lilith_os"])
            res = self.route("reasoning")
        finally:
            reasoning._default_model_call = saved
        self.assertIsNone(res)                                 # unparseable model output -> falls through
        self.assertEqual(len(prompts), 1)
        self.assertIn(BELIEF_CANARY, prompts[0])               # durable World Model state reaches the input
        self.assertNotIn(FORGOTTEN_CANARY, prompts[0])
        self.assertLess(len(prompts[0]), 40000)
        self.assert_reads_only_allowlisted()
        self.assertEqual(self.delta("writes_refused"), 0)

    def test_lane_precedence_is_the_gateway_order(self):
        self.configure(**all_lanes("live"))
        from lilith_router import reasoning
        saved = reasoning._default_model_call
        reasoning._default_model_call = lambda prompt: "not json"
        try:
            modes = {key: (self.route(key) or {}).get("mode") for key in
                     ("planning", "ethics", "belief", "goal_query", "draft")}
        finally:
            reasoning._default_model_call = saved
        self.assertEqual(modes, {"planning": "planning", "ethics": "ethics", "belief": "cognitive",
                                 "goal_query": "goal", "draft": "cognitive"})
        self.assertFalse([c for c in self.opener.calls if c["method"] != "GET"])


class FailureTest(InProcessCase):
    def test_unavailable_core_api_is_reported_honestly(self):
        self.opener.error = urllib.error.URLError("TEST_ONLY refused")
        self.configure(cognitive_enabled=True, cognitive_mode="live", goals_enabled=True, goals_mode="live",
                       cognitive_channels=["lilith_os"])
        belief = self.route("belief")
        self.assertIn("WORLD MODEL: temporarily unavailable", belief["combined_ephemeral"])
        goal = self.route("goal_query")
        self.assertIn("GOAL / EXECUTIVE STATE: temporarily unavailable", goal["combined_ephemeral"])

    def test_malformed_responses_never_break_a_turn(self):
        bodies = [b"[]", b'"x"', b"null", b"{", b'{"beliefs": "nope", "goals": 7, "tasks": {"a": 1}}']
        self.configure(**all_lanes("live"))
        for body in bodies:
            with self.subTest(body=body):
                self.opener.respond = lambda req, body=body: FakeResponse(body)
                for key in ("belief", "pending", "goal_query", "planning", "ethics"):
                    self.route(key)                            # must return normally
        self.assertFalse([c for c in self.opener.calls if c["method"] != "GET"])

    def test_transport_refuses_everything_outside_the_contract(self):
        wc = self.wc
        token = wc._BUDGET.set([100])
        try:
            for path in ("/memory/USER.md", "/memory/search?q=x", "/os/world?entity_type=x", "/os/../memory",
                         "/os/conversation", "/os/drafts", "//evil.example/os/world", "/os/goals?limit=201",
                         "/os/world?entity_type=career.application&entity_id=../../memory"):
                with self.subTest(path=path):
                    self.assertIsNone(wc._governed_get(path))
            self.assertEqual(self.opener.calls, [])
            for respond in (lambda r: FakeResponse(b'{"a":1}', code=204),
                            lambda r: FakeResponse(b'{"a":1}', content_type="text/html"),
                            lambda r: FakeResponse(b" " * (wc.MAX_RESPONSE_BYTES + 1)),
                            lambda r: (_ for _ in ()).throw(TimeoutError("TEST_ONLY"))):
                self.opener.respond = respond
                self.assertIsNone(wc._governed_get("/os/goals/focus"))
        finally:
            wc._BUDGET.reset(token)
        self.assertIsNone(wc._governed_get("/os/goals/focus"))           # outside any entry point: refused
        self.assertEqual(len(self.opener.calls), 4)

    def test_read_budget_bounds_calls_per_entry(self):
        wc = self.wc
        token = wc._BUDGET.set([2])
        try:
            results = [wc._governed_get("/os/goals/focus") for _ in range(3)]
        finally:
            wc._BUDGET.reset(token)
        self.assertEqual([r is not None for r in results], [True, True, False])
        self.assertEqual(len(self.opener.calls), 2)
        wc.build_attention_candidates(MESSAGES["reasoning"], "s", wc.detect_reasoning_intent(MESSAGES["reasoning"]))
        self.assertLessEqual(len(self.opener.calls) - 2, wc.MAX_CALLS_PER_ENTRY)

    def test_opener_uses_no_proxy_and_follows_no_redirect(self):
        import urllib.request
        handlers = self._saved_opener.handlers
        # ProxyHandler({}) registers no proxy method, and its presence stops build_opener from adding the default
        # environment-proxy handler: no handler routes a request through HTTP(S)_PROXY.
        self.assertFalse([h for h in handlers if isinstance(h, urllib.request.ProxyHandler)])
        redirect = [h for h in handlers if isinstance(h, urllib.request.HTTPRedirectHandler)]
        self.assertEqual([type(h) for h in redirect], [self.wc._NoRedirect])
        self.assertIsNone(redirect[0].redirect_request(None, None, 302, "", {}, "http://evil.example/"))
        self.assertEqual(self.wc.API_BASE, "http://127.0.0.1:8765")

    def test_grounding_is_length_capped(self):
        many = {"goals": [dict(GOAL, goalId=f"g.test.{i}") for i in range(600)]}
        self.opener.fixtures = dict(FIXTURES, **{"/os/goals": many})
        suffix, _ = self.wc.build_goal_grounding(message=MESSAGES["goal_query"], session_key="s",
                                                 gintent=self.wc.detect_goal_intent(MESSAGES["goal_query"]),
                                                 do_write=True)
        self.assertEqual(len(suffix), self.wc.MAX_GROUNDING_CHARS)
        self.assertTrue(suffix.endswith(self.wc.TRUNCATION_MARK))


class DisabledLegacyTest(unittest.TestCase):
    def test_changed_prod_bytes_disable_cognition_and_route_like_the_stub(self):
        tampered = TMP / "tampered" / "hermes-home"
        shutil.copytree(CANDIDATE, tampered)
        legacy = tampered / "lilith_router" / "_prod_world_context.py"
        legacy.write_bytes(legacy.read_bytes() + b"\n# TEST_ONLY tamper\n")
        result = probe(tampered, MESSAGES.values(), **all_lanes("live"))
        self.assertEqual(result["identity"]["status"]["reason"], "legacy_digest_mismatch")
        self.assertFalse(result["identity"]["status"]["legacy_loaded"])
        self.assertTrue(all(r is None for r in result["results"]))
        self.assertEqual(result["socket_attempts"], [])
        self.assertFalse([r for r in result["log"] if r.get("lane")])     # no lane detected anything

    def test_rollback_restores_the_verified_dev_tree(self):
        rolled = TMP / "rollback" / "hermes-home"
        shutil.copytree(CANDIDATE, rolled)
        dev = assemble_home.load("dev-f9c2")
        stub = dev["lilith_router/world_context.py"]
        (rolled / "lilith_router" / "_prod_world_context.py").unlink()
        shutil.copyfile(REPO / stub["source"], rolled / "lilith_router" / "world_context.py")
        (rolled / "lilith_router" / "router.yaml").unlink()                          # written by these tests
        built = {rel: sha(rolled / rel) for rel in code_files(rolled)}
        self.assertEqual(built, {rel: e["sha256"] for rel, e in dev.items()})


if __name__ == "__main__":
    unittest.main()
