#!/usr/bin/env python3
"""P-1 T-4: focused OFFLINE replay of LILITH's reply builders for A/B variants. Runs on the LILITH host as `lilith`.

Generalizes the operator tools sc_eval.py (lean Groq reply) and t4_synth.py (full agent, no tools). It writes nothing
to LILITH: no session DB, no memory, no tools, no Hermes session. Output is raw JSON (replies, tokens, latency) for
blind.py.

Spec (JSON file; synthetic scenarios only):
    {"mode": "lean" | "agent",
     "samples": 2, "gap_s": 30, "budget_tokens": 50000,
     "variants": {"A": {}, "B": {"system_suffix": "...", "message_prefix": "...", "tone_note": "deployed"}},
     "scenarios": [{"id": "s1", "history": [["user", "..."], ["assistant", "..."]], "message": "..."}]}

Variant keys (all optional; an empty variant is the baseline):
    system_suffix   text appended to the lean policy / the agent's ephemeral system prompt
    message_prefix  text prefixed to the current message (API-only turn-hint style)
    tone_note       "deployed": the router's own owner tone note for this turn (lean mode)

Budget: stops sampling when this run's tokens reach budget_tokens, or when the provider reports fewer than 7000
remaining tokens per minute (then waits for the reset). Errors are recorded, never retried blindly.

    sudo -u lilith env HERMES_HOME=~lilith/.hermes ~lilith/.hermes/hermes-agent/venv/bin/python replay.py spec.json > raw.json
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

HOME = Path("/home/lilith/.hermes")


def _dur(s: str) -> float:
    m = re.match(r"(?:(\d+)m)?([\d.]+)s", s or "")
    return (int(m.group(1) or 0) * 60 + float(m.group(2))) if m else 10.0


def lean_runner(spec):
    sys.path.insert(0, str(HOME))
    sys.path.insert(0, str(HOME / "hermes-agent"))
    from lilith_router import classifier as cl, config as cfgmod, policy as pol, social_cognition as sc
    from lilith_router import social_lean as sl
    from gateway.run import _resolve_runtime_agent_kwargs_for_provider as res
    from openai import OpenAI
    cfg = cfgmod.load()
    try:
        from providers import get_provider_profile
        get_provider_profile(cfg.groq_provider)
    except Exception:
        pass
    rt = res(cfg.groq_provider)
    client = OpenAI(base_url=rt["base_url"], api_key=rt["api_key"], timeout=60, max_retries=0)
    core = sl.soul_core(HOME / "SOUL.md")

    def run(scn, variant):
        hist = [{"role": r, "content": c} for r, c in scn.get("history", [])]
        users = [c for r, c in scn.get("history", []) if r == "user"]
        policy = pol.SOCIAL_POLICY
        if variant.get("tone_note") == "deployed":
            d = cl.classify(scn["message"], users, "social" if users else None)
            snap = sc.build_social_context(sc.build_social_input(scn["message"], "eval.replay", "telegram"))
            note = sc.tone_note(snap, focused=d.mode != "social" or bool((d.signals or {}).get("tech")),
                                context=sc.tone_context(scn["message"], users))
            policy += ("\n\n" + note) if note else ""
        if variant.get("system_suffix"):
            policy += "\n\n" + variant["system_suffix"]
        msg = (variant.get("message_prefix", "") + "\n\n" + scn["message"]) if variant.get("message_prefix") \
            else scn["message"]
        msgs = sl.build_messages(core, policy, "", hist, msg)
        t0 = time.monotonic()
        raw = client.chat.completions.with_raw_response.create(
            model=cfg.groq_model, messages=msgs, max_tokens=cfg.social_lean_max_output_tokens, temperature=0.7,
            extra_body={"reasoning_effort": "none"})
        resp, h = raw.parse(), raw.headers
        ms = int((time.monotonic() - t0) * 1000)          # the call itself; the back-off below is not latency
        text = sl._THINK_RE.sub("", resp.choices[0].message.content or "").strip()
        rem = int(h.get("x-ratelimit-remaining-tokens", "99999") or 99999)
        if rem < 7000:
            time.sleep(min(65, _dur(h.get("x-ratelimit-reset-tokens")) + 1))
        return text, int(getattr(resp.usage, "total_tokens", 0) or 0), ms
    return run


def agent_runner(spec):
    sys.path.insert(0, str(HOME / "hermes-agent"))
    import logging
    logging.disable(logging.WARNING)
    from run_agent import AIAgent
    from gateway.run import _resolve_runtime_agent_kwargs_for_provider as res
    rt = res(spec.get("agent_provider", "openai-codex"))
    model = spec.get("agent_model", "gpt-5.6-sol")

    def run(scn, variant):
        a = AIAgent(model=model, **{k: rt[k] for k in ("provider", "base_url", "api_key", "api_mode") if k in rt},
                    quiet_mode=True, verbose_logging=False, enabled_toolsets=[], skip_context_files=True,
                    load_soul_identity=True, ephemeral_system_prompt=variant.get("system_suffix") or None,
                    max_iterations=2)
        msg = (variant.get("message_prefix", "") + "\n\n" + scn["message"]) if variant.get("message_prefix") \
            else scn["message"]
        t0 = time.monotonic()
        r = a.run_conversation(msg, conversation_history=[{"role": x, "content": y} for x, y in scn.get("history", [])])
        toks = int(getattr(a, "session_prompt_tokens", 0) or 0) + int(getattr(a, "session_completion_tokens", 0) or 0)
        return (r.get("final_response") or "").strip(), toks, int((time.monotonic() - t0) * 1000)
    return run


def replay(spec: dict, run) -> list:
    budget, used, out = int(spec.get("budget_tokens", 50000)), 0, []
    for scn in spec["scenarios"]:
        rec = {"id": scn["id"], "replies": {}, "tokens": {}, "latency_ms": {}}
        for name, variant in spec["variants"].items():
            for k in ("replies", "tokens", "latency_ms"):
                rec[k][name] = []
            for _ in range(int(spec.get("samples", 2))):
                if used >= budget:
                    rec["replies"][name].append(None)
                    continue
                try:
                    text, toks, ms = run(scn, variant)
                except Exception as exc:
                    text, toks, ms = "<<ERROR %s %s>>" % (type(exc).__name__, getattr(exc, "status_code", "")), 0, 0
                used += toks
                rec["replies"][name].append(text)
                rec["tokens"][name].append(toks)
                rec["latency_ms"][name].append(ms)
                time.sleep(float(spec.get("gap_s", 0)))
        out.append(rec)
    return out


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    spec = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    run = lean_runner(spec) if spec.get("mode", "lean") == "lean" else agent_runner(spec)
    json.dump(replay(spec, run), sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
