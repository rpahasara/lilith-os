"""Owner decision 2026-11-06 (Option B): Hermes' personal memory (USER.md / MEMORY.md) reaches owner channels only.

Runs against the real deploy sources: the router mirror (deploy/prod/lilith_router) and the patched Hermes
gateway/run.py (deploy/prod/hermes_gateway). Both paths are covered: the lean social reply and the full agent.
"""
import importlib
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MIRROR = ROOT / "deploy/prod/lilith_router"
RUN_PY = ROOT / "deploy/prod/hermes_gateway/run.py"
OWNER = "1111794198"
SETTINGS = {"schemaVersion": 1, "enabled": True, "ownerTelegramUserIds": [OWNER]}
SECRET = "OWNER-ONLY-SECRET-FACT-7f3a"


def src(**kw):
    base = {"user_id": "", "chat_id": "", "chat_type": "dm", "platform": None}
    base.update(kw)
    return types.SimpleNamespace(**base)


def load_router():
    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(MIRROR, tmp / "lilith_router_t", ignore=shutil.ignore_patterns(".gitattributes"))
    sys.path.insert(0, str(tmp))
    for name in list(sys.modules):
        if name.startswith("lilith_router_t"):
            del sys.modules[name]
    gi = importlib.import_module("lilith_router_t.gateway_integration")
    return tmp, gi


class OwnerRuleTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.gi = load_router()
        self.cm = self.gi._canonical_memory

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_only_the_console_and_the_owner_dm_are_owner_turns(self):
        own = self.cm.is_owner_turn
        self.assertTrue(own(SETTINGS, "lilith_os", src()))
        self.assertTrue(own(SETTINGS, "telegram", src(user_id=OWNER, chat_id=OWNER, chat_type="dm")))
        for platform, s in [("telegram", src(user_id=OWNER, chat_id="-1001", chat_type="group")),
                            ("telegram", src(user_id=OWNER, chat_id="-1001", chat_type="supergroup")),
                            ("telegram", src(user_id="42", chat_id="42", chat_type="dm")),
                            ("discord", src(user_id=OWNER, chat_id="55", chat_type="group")),
                            ("discord", src(user_id=OWNER, chat_id=OWNER, chat_type="dm")),
                            ("whatsapp", src(user_id=OWNER, chat_id=OWNER, chat_type="dm"))]:
            with self.subTest(platform=platform, source=vars(s)):
                self.assertFalse(own(SETTINGS, platform, s))
        self.assertFalse(own(None, "telegram", src(user_id=OWNER, chat_id=OWNER, chat_type="dm")))  # no settings

    def route(self, platform, source, impl=None, settings=SETTINGS):
        gi = self.gi
        gi._route_turn_impl = impl or (lambda **kw: None)
        gi._canonical_memory.load_settings = lambda home, **kw: settings
        gi._canonical_memory.turn_note = lambda *a, **kw: None
        gi._platform_name = lambda s: platform
        ctx = types.SimpleNamespace(source=source, session_key=f"agent:main:{platform}:x")
        return gi.route_turn(runner=None, ctx=ctx, model="m", runtime_kwargs={}, turn_route={}, combined_ephemeral="")

    def test_route_turn_always_says_whether_memory_may_load(self):
        r = self.route("telegram", src(user_id=OWNER, chat_id=OWNER, chat_type="dm"))
        self.assertEqual(r, {"owner_memory": True})
        self.assertIs(self.route("lilith_os", src())["owner_memory"], True)
        self.assertIs(self.route("discord", src(user_id=OWNER, chat_id="55", chat_type="group"))["owner_memory"], False)
        self.assertIs(self.route("telegram", src(user_id=OWNER, chat_id="-1", chat_type="group"))["owner_memory"], False)
        kept = self.route("telegram", src(user_id=OWNER, chat_id=OWNER, chat_type="dm"),
                          impl=lambda **kw: {"final_response": "hi", "mode": "social"})
        self.assertEqual((kept["final_response"], kept["owner_memory"]), ("hi", True))   # route result kept

    def test_failures_mean_no_personal_memory(self):
        def boom(**kw):
            raise RuntimeError("x")
        self.assertIs(self.route("lilith_os", src(), impl=boom)["owner_memory"], True)    # impl failure: rule still holds
        self.gi._canonical_memory.load_settings = None                                   # settings path broken
        ctx = types.SimpleNamespace(source=src(), session_key="k")
        r = self.gi.route_turn(runner=None, ctx=ctx, model="m", runtime_kwargs={}, turn_route={}, combined_ephemeral="")
        self.assertIs(r["owner_memory"], False)
        self.assertIs(self.cm.owner_turn(), False)
        no_source = self.gi.route_turn(runner=None, ctx=types.SimpleNamespace(source=None), model="m",
                                       runtime_kwargs={}, turn_route={}, combined_ephemeral="")
        self.assertIs(no_source["owner_memory"], False)


class LeanPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.gi = load_router()
        self.lean = self.gi._social_lean
        home = self.tmp / "home"
        (home / "memories").mkdir(parents=True)
        (home / "memories" / "USER.md").write_text(SECRET + " likes tea", encoding="utf-8")
        (home / "memories" / "MEMORY.md").write_text(SECRET + " durable", encoding="utf-8")
        self.home = home

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_profile_only_with_include_profile(self):
        with_prof = self.lean.build_messages("CORE", "POLICY", self.lean.profile(self.home), [], "hey")
        self.assertIn(SECRET, with_prof[0]["content"])
        text = (MIRROR / "social_lean.py").read_text(encoding="utf-8")
        self.assertIn('profile(home) if include_profile is True else ""', text)
        self.assertIn("include_profile: bool = False", text)                          # default: no profile

    def test_reply_sends_no_profile_unless_owner(self):
        captured = []

        class Client:
            class chat:
                class completions:
                    @staticmethod
                    def create(**kw):
                        captured.append(kw["messages"])
                        return types.SimpleNamespace(choices=[types.SimpleNamespace(
                            message=types.SimpleNamespace(content="ok"))], usage=None)
        self.lean.soul_core = lambda path: "SOUL CORE"
        cfg = types.SimpleNamespace(social_lean_history_turns=0, social_lean_max_output_tokens=50,
                                    social_lean_tpm_budget=10 ** 9, social_lean_tpd_budget=10 ** 9,
                                    social_lean_timeout_s=5, groq_model="m")
        kw = dict(runner=None, cfg=cfg, home=self.home, session_key="s", message="hey", policy="P",
                  runtime={"api_key": "k", "base_url": "u"}, client_factory=lambda rt, t: Client)
        self.lean.reply(**kw)
        self.lean.reply(**kw, include_profile=True)
        self.assertNotIn(SECRET, captured[0][0]["content"])
        self.assertIn(SECRET, captured[1][0]["content"])

    def test_router_passes_the_owner_flag_to_the_lean_reply(self):
        text = (MIRROR / "gateway_integration.py").read_text(encoding="utf-8")
        self.assertIn("include_profile=_canonical_memory.owner_turn()", text)
        self.assertEqual(text.count("_social_lean.reply("), 1)


class FullAgentPathTests(unittest.TestCase):
    """The hook in gateway/run.py, executed exactly as written against fake agents."""

    def hook(self):
        text = RUN_PY.read_text(encoding="utf-8")
        start = text.index("        # ── LILITH owner-only Hermes memory")
        end = text.index("        # ── end LILITH owner-only memory ──")
        self.assertLess(start, text.index("        # Per-message state — callbacks and reasoning config change every"))
        self.assertGreater(start, text.index("            agent = ctx.AIAgent("))           # after the agent exists
        return "\n".join(l[8:] for l in text[start:end].splitlines())

    def run_hook(self, lr_res):
        names = ("clarify", "delegate_task", "execute_code", "memory", "patch", "process", "read_file", "search_files", "session_search", "skill_manage", "skill_view", "skills_list", "terminal", "text_to_speech", "todo", "vision_analyze", "web_extract", "web_search", "write_file")                                     # PROD Discord/Telegram tools, 2026-11-06
        tools = [{"function": {"name": n}} for n in names]
        agent = types.SimpleNamespace(_memory_store=object(), _memory_enabled=True, _user_profile_enabled=True,
                                      tools=tools, valid_tool_names=set(names),
                                      _get_session_db_for_recall=lambda: "STATE_DB")
        exec(compile(self.hook(), "hook", "exec"), {}, {"agent": agent, "_lr_res": lr_res})
        return agent

    def test_owner_turn_keeps_memory(self):
        a = self.run_hook({"owner_memory": True, "turn_route": {}})
        self.assertIsNotNone(a._memory_store)
        self.assertTrue(a._memory_enabled and a._user_profile_enabled)
        self.assertEqual(a._get_session_db_for_recall(), "STATE_DB")                       # owner keeps recall
        self.assertEqual(a.valid_tool_names, set(("clarify", "delegate_task", "execute_code", "memory", "patch", "process", "read_file", "search_files", "session_search", "skill_manage", "skill_view", "skills_list", "terminal", "text_to_speech", "todo", "vision_analyze", "web_extract", "web_search", "write_file")))                     # owner keeps every tool

    def test_everything_else_drops_memory(self):
        for lr in ({"owner_memory": False}, {}, None, {"owner_memory": "yes"}, {"owner_memory": 1}, "x"):
            with self.subTest(lr=lr):
                a = self.run_hook(lr)
                self.assertIsNone(a._memory_store)
                self.assertFalse(a._memory_enabled or a._user_profile_enabled)
                self.assertIsNone(a._get_session_db_for_recall())                         # no cross-chat search
                safe = {"clarify", "text_to_speech", "todo", "vision_analyze", "web_extract", "web_search"}
                self.assertEqual(a.valid_tool_names, safe)                                 # conversation tools only
                self.assertEqual({t["function"]["name"] for t in a.tools}, safe)
                for local in ("read_file", "search_files", "terminal", "execute_code", "process", "patch",
                              "write_file", "delegate_task", "skill_view", "skills_list", "skill_manage"):
                    self.assertNotIn(local, a.valid_tool_names)                            # nothing reads this host

    def test_hook_is_present_once(self):
        self.assertEqual(RUN_PY.read_text(encoding="utf-8").count("LILITH owner-only Hermes memory"), 1)


if __name__ == "__main__":
    unittest.main()
