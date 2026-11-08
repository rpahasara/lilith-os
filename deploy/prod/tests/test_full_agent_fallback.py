"""Full-agent provider fallback (2026-11-08).

router.yaml `full_agent_fallback` becomes Hermes' native `fallback_model` chain on every routed turn, after the social
route's own fallback, and run.py applies it to a reused (cached) agent as well. Hermes itself decides when to switch
(auth / billing / rate-limit / overload / timeout / missing model) and retries only the failed model call.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_owner_memory import ROOT, RUN_PY  # noqa: E402

sys.path.insert(0, str(ROOT / "deploy/prod"))
from lilith_router import config as cfgmod  # noqa: E402
from lilith_router import gateway_integration as gi  # noqa: E402

YAML = ROOT / "deploy/prod/lilith_router/router.yaml"
COPILOT = {"provider": "copilot", "model": "gpt-4.1"}
CODEX = {"provider": "openai-codex", "model": "gpt-5.6-sol"}


def cfg_from(text):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "router.yaml"
        p.write_text(text, encoding="utf-8")
        with mock.patch.object(cfgmod, "CONFIG_PATH", p):
            return cfgmod.load()


class ParseTests(unittest.TestCase):
    def test_deployed_config_uses_free_same_architecture_fallback(self):
        cfg = cfg_from(YAML.read_text(encoding="utf-8"))
        self.assertEqual(cfg.full_agent_fallback, [COPILOT])
        self.assertEqual((cfg.hermes_provider, cfg.hermes_model), ("openai-codex", "gpt-5.6-sol"))  # primary unchanged

    def test_malformed_entries_are_dropped_never_raise(self):
        self.assertEqual(cfgmod.parse_fallback_chain(None), [])
        self.assertEqual(cfgmod.parse_fallback_chain("copilot"), [])
        self.assertEqual(cfgmod.parse_fallback_chain([{"provider": "copilot"}, "x", {"model": "m"}, COPILOT, COPILOT]),
                         [COPILOT])
        self.assertEqual(cfgmod.parse_fallback_chain([{"provider": "a", "model": str(i)} for i in range(9)])[-1],
                         {"provider": "a", "model": "2"})
        self.assertEqual(cfgmod.parse_fallback_chain([dict(COPILOT, api_mode="bogus")]), [COPILOT])

    def test_missing_key_means_no_fallback(self):
        self.assertEqual(cfg_from("enabled: true\n").full_agent_fallback, [])


class ChainTests(unittest.TestCase):
    def run_with(self, out, chain=(COPILOT,), enabled=True):
        cfg = cfgmod.RouterConfig(enabled=enabled, full_agent_fallback=list(chain))
        with mock.patch.object(gi._config, "load", return_value=cfg):
            return gi._with_fallback_chain(dict(out))

    def test_native_turn_gets_the_chain(self):
        self.assertEqual(self.run_with({"owner_memory": True})["fallback_model"], [COPILOT])

    def test_social_route_keeps_its_own_fallback_first(self):
        out = self.run_with({"fallback_model": [CODEX], "mode": "social"})
        self.assertEqual(out["fallback_model"], [CODEX, COPILOT])
        out = self.run_with({"fallback_model": [COPILOT]})
        self.assertEqual(out["fallback_model"], [COPILOT])  # no duplicate entry

    def test_ready_reply_disabled_router_or_empty_chain_unchanged(self):
        self.assertNotIn("fallback_model", self.run_with({"final_response": "hi"}))
        self.assertNotIn("fallback_model", self.run_with({}, enabled=False))
        self.assertNotIn("fallback_model", self.run_with({}, chain=()))

    def test_config_error_leaves_turn_as_is(self):
        with mock.patch.object(gi._config, "load", side_effect=RuntimeError):
            self.assertEqual(gi._with_fallback_chain({"owner_memory": False}), {"owner_memory": False})

    def test_every_route_turn_return_carries_it(self):
        text = (ROOT / "deploy/prod/lilith_router/gateway_integration.py").read_text(encoding="utf-8")
        self.assertIn("return _with_fallback_chain(_with_owner_memory(result, False))", text)
        self.assertIn("return _with_fallback_chain(_with_social_note(_with_owner_memory(merged, owner)))", text)


class RunPyTests(unittest.TestCase):
    def test_cached_agent_gets_the_router_chain_after_the_config_refresh(self):
        text = RUN_PY.read_text(encoding="utf-8")
        refresh = text.index("self._runner._apply_fallback_chain_to_agent(\n                agent, self._runner._refresh_fallback_model(),")
        router = text.index("self._runner._apply_fallback_chain_to_agent(agent, _lilith_fallback_override)")
        build = text.index("_lilith_fallback_override\n                    if _lilith_fallback_override is not None")
        self.assertLess(refresh, router)
        self.assertLess(router, build)


if __name__ == "__main__":
    unittest.main()
