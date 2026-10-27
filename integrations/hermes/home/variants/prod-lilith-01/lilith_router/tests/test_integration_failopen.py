"""Fail-open + switch behavior tests for the gateway integration.

Run:  python -m lilith_router.tests.test_integration_failopen
Uses fakes for the gateway runner / ctx — no gateway, no network, no secrets.
Verifies the router NEVER raises into the core and only overrides when it is
safe and enabled. Exits non-zero on any failure.
"""

from __future__ import annotations

import sys

from lilith_router import gateway_integration as gi
from lilith_router import config as gi_config


# ── Fakes ────────────────────────────────────────────────────────────────
class FakePlatform:
    def __init__(self, value):
        self.value = value


class FakeSource:
    def __init__(self, platform="discord", chat_id="C1"):
        self.platform = FakePlatform(platform)
        self.chat_id = chat_id


class FakeCtx:
    def __init__(self, message, session_key="s1", platform="discord", chat_id="C1"):
        self.message = message
        self.session_key = session_key
        self.source = FakeSource(platform, chat_id)


class FakeAgent:
    def __init__(self, model):
        self.model = model


class FakeRunner:
    def __init__(self, groq_ok=True, raise_creds=False):
        self._groq_ok = groq_ok
        self._raise_creds = raise_creds
        self.evicted = []

    def _resolve_runtime_agent_kwargs_for_provider(self, provider):
        if self._raise_creds:
            raise RuntimeError("no creds")
        if not self._groq_ok:
            return {"api_key": None, "credential_pool": None}
        return {"api_key": "x", "base_url": "https://api.groq.com/openai/v1",
                "provider": "groq", "api_mode": "chat_completions"}

    def _resolve_turn_agent_config(self, message, model, runtime_kwargs):
        return {"model": model, "runtime": runtime_kwargs}

    def _evict_cached_agent(self, key):
        self.evicted.append(key)


def _cfg(enabled=True, mode="live", channels=("*",)):
    c = gi_config.RouterConfig()
    c.enabled = enabled
    c.mode = mode
    c.live_channels = list(channels)
    return c


def _patch_cfg(c):
    gi._config.load = lambda: c  # type: ignore


def run():
    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))
        print(f"[{'ok ' if cond else 'FAIL'}] {name}")

    base = dict(model="gpt-5.6-sol", runtime_kwargs={"provider": "openai-codex"},
                turn_route={"model": "gpt-5.6-sol", "runtime": {}},
                combined_ephemeral="BASE")

    # 1) Disabled -> no-op.
    _patch_cfg(_cfg(enabled=False))
    r = gi.route_turn(runner=FakeRunner(), ctx=FakeCtx("hey you 😊"), cached_agent=None, **base)
    check("disabled returns None", r is None)

    # 2) Shadow -> observe only, never switch.
    _patch_cfg(_cfg(mode="shadow"))
    r = gi.route_turn(runner=FakeRunner(), ctx=FakeCtx("you missed me huh 😏"), cached_agent=None, **base)
    check("shadow returns None", r is None)

    # 3) Live + social + creds ok -> override to groq with social ephemeral.
    _patch_cfg(_cfg())
    r = gi.route_turn(runner=FakeRunner(), ctx=FakeCtx("bro today was exhausting"), cached_agent=None, **base)
    check("social override produced", r is not None and r.get("turn_route", {}).get("model") == "qwen/qwen3.8-27b")
    check("social ephemeral appended", r is not None and "conversation mode" in r.get("combined_ephemeral", ""))
    check("social first turn no force_rebuild", r is not None and r.get("force_rebuild") is False)
    check(
        "social fallback -> gpt-5.6-sol",
        r is not None
        and r.get("fallback_model") == [{"provider": "openai-codex", "model": "gpt-5.6-sol"}],
    )

    # 4) Live + social + creds MISSING -> fail open (None).
    _patch_cfg(_cfg())
    r = gi.route_turn(runner=FakeRunner(groq_ok=False), ctx=FakeCtx("hey 🥰"), cached_agent=None, **base)
    check("social + no creds fails open", r is None)

    # 5) Live + social + creds resolver RAISES -> fail open (None, no exception).
    _patch_cfg(_cfg())
    r = gi.route_turn(runner=FakeRunner(raise_creds=True), ctx=FakeCtx("hey 🥰"), cached_agent=None, **base)
    check("creds exception fails open", r is None)

    # 6) Live + social, cached agent is non-groq -> force rebuild + evict.
    _patch_cfg(_cfg())
    runner = FakeRunner()
    r = gi.route_turn(runner=runner, ctx=FakeCtx("miss you ❤️"), cached_agent=FakeAgent("gpt-5.6-sol"), **base)
    check("social with stale native agent forces rebuild", r is not None and r.get("force_rebuild") is True)
    check("eviction called on switch to groq", "s1" in runner.evicted)

    # 7) Live + social, cached agent already groq -> reuse (None).
    _patch_cfg(_cfg())
    r = gi.route_turn(runner=FakeRunner(), ctx=FakeCtx("hey cutie 😊"), cached_agent=FakeAgent("qwen/qwen3.8-27b"), **base)
    check("social reuse of groq agent returns None", r is None)

    # 8) Live + technical, cached agent is groq -> switch back (force rebuild).
    _patch_cfg(_cfg())
    runner = FakeRunner()
    r = gi.route_turn(runner=runner, ctx=FakeCtx("why is my kubernetes pod pending?"),
                      cached_agent=FakeAgent("qwen/qwen3.8-27b"), **base)
    check("technical switch-back forces rebuild", r is not None and r.get("force_rebuild") is True)
    check("eviction called on switch back", "s1" in runner.evicted)

    # 9) Live + technical, cached native -> no-op (native path).
    _patch_cfg(_cfg())
    r = gi.route_turn(runner=FakeRunner(), ctx=FakeCtx("fix the nginx config"),
                      cached_agent=FakeAgent("gpt-5.6-sol"), **base)
    check("technical on native agent returns None", r is None)

    failed = [n for n, ok in checks if not ok]
    print()
    if failed:
        print(f"{len(failed)}/{len(checks)} FAILED: {failed}")
        return 1
    print(f"All {len(checks)} integration checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
