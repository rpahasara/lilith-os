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
    profile         P-2: a list of SYNTHETIC memory entries, given as the owner profile (USER.md shape; lean: the
                    profile block, agent: the ephemeral system prompt). A scenario's own "profile" is added to it
    preferences     "router": also the P-2 router note, selected from the profile entries by the deployed
                    social_preferences module exactly as a live owner turn would (plus the correction hint)
    appraisal       P-3: "router": the deployed appraisal module over the message and the SYNTHETIC "goals" (variant
                    plus scenario), applied to the deployed tone note lines and adding the goal line (needs
                    tone_note "deployed"; the agent arm then also carries the tone note as its turn hint)
    timeline        P-4: "router": the deployed timeline note rendered from the spec's SYNTHETIC "timeline_records", only
                    when the deployed trigger (timeline.temporal) fires for the message - as a live owner turn would
    timeline_header P-4: candidate header text for the timeline note (offline comparison of wordings)
    retrieval       P-4 (agent mode): "synthetic": the agent gets Hermes' own session_search tool over a throwaway
                    state.db built from the spec's SYNTHETIC "synthetic_conversations" (real owner transcripts are never
                    reachable: SessionDB is pinned to the synthetic file for the whole process)
    meta            P-3: "ask" | "escalate": the L16 recall-gap control, decided by the deployed metacognition module
                    with the synthetic profile as grounding, exactly as a live owner turn would (note only if it fires)

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


def preference_parts(scn: dict, variant: dict, sp, focused: bool):
    """P-2 arms: (synthetic profile text, router preference note or None). `sp` is lilith_router.social_preferences."""
    entries = list(variant.get("profile") or []) + list(scn.get("profile") or [])
    prof = ("[About them]\n" + "\n§\n".join(entries)) if entries else ""
    note = None
    if variant.get("preferences") == "router":
        prefs = [p for p in (sp.parse(t, "e%d" % i) for i, t in enumerate(entries)) if p]
        parts = [sp.CORRECTION_HINT if sp.durable_correction(scn["message"]) else None,
                 sp.render(sp.select(prefs, focused=focused, message=scn["message"]))]
        note = "\n\n".join(p for p in parts if p) or None
    return prof, note


def style_parts(scn: dict, variant: dict, focused: bool):
    """(tone note, goal line) exactly as the router renders them for this scenario: the deployed Social Cognition
    lines, then (appraisal arm) the deployed appraisal mapping and goal line. (None, None) without tone_note."""
    if variant.get("tone_note") != "deployed":
        return None, None
    from lilith_router import social_cognition as sc
    users = [c for r, c in scn.get("history", []) if r == "user"]
    snap = sc.build_social_context(sc.build_social_input(scn["message"], "eval.replay", "telegram"))
    keys = sc.tone_note_keys(snap, focused=focused, context=sc.tone_context(scn["message"], users))
    goal = None
    if variant.get("appraisal") == "router":
        from lilith_router import appraisal as ap
        goals = list(variant.get("goals") or []) + list(scn.get("goals") or [])
        sigs = ap.appraise(scn["message"], goals)
        keys = list(ap.adjust_lines(keys, sigs, focused=focused))
        refs = {s.ref for s in sigs if s.kind == "goal"}
        goal = ap.goal_note([g for g in goals if str(g.get("goalId") or "") in refs])
    tone = (sc.TONE_HEADER + "\n" + "\n".join("- " + sc.TONE_LINES[k] for k in keys)) if keys else None
    return tone, goal


def timeline_note(scn: dict, variant: dict, spec: dict):
    """P-4 arm: the router's timeline note for this scenario (deployed module, synthetic records), or None."""
    if variant.get("timeline") != "router":
        return None
    from lilith_router import timeline as tl
    if not tl.temporal(scn["message"]):
        return None
    header = variant.get("timeline_header")          # candidate wording, evaluated without touching the deployed one
    saved = tl.HEADER
    try:
        if header:
            tl.HEADER = header
        return tl.render(spec.get("timeline_records") or [])
    finally:
        tl.HEADER = saved


def synthetic_session_store(spec: dict) -> Path:
    """A throwaway Hermes state.db with the spec's synthetic conversations (Hermes' own schema), timestamps set to
    the scenario's dates; then every SessionDB in this process is pinned to it."""
    import sqlite3
    import tempfile
    import hermes_state
    path = Path(tempfile.mkdtemp(prefix="syn-sessions-")) / "state.db"
    db = hermes_state.SessionDB(db_path=path)
    for s in spec.get("synthetic_conversations") or []:
        db.create_session(s["id"], s.get("source", "telegram"))
        for role, content, _ts in s["messages"]:
            db.append_message(s["id"], role, content)
    close = getattr(db, "close", None)
    if callable(close):
        close()
    con = sqlite3.connect(path)
    for s in spec.get("synthetic_conversations") or []:
        ids = [r[0] for r in con.execute("SELECT id FROM messages WHERE session_id=? ORDER BY id", (s["id"],))]
        stamps = [_epoch(ts) for _, _, ts in s["messages"]]
        for mid, ts in zip(ids, stamps):
            con.execute("UPDATE messages SET timestamp=? WHERE id=?", (ts, mid))
        cols = {r[1] for r in con.execute("PRAGMA table_info(sessions)")}
        if "started_at" in cols and stamps:
            con.execute("UPDATE sessions SET started_at=? WHERE id=?", (stamps[0], s["id"]))
        if "ended_at" in cols and stamps:
            con.execute("UPDATE sessions SET ended_at=? WHERE id=?", (stamps[-1], s["id"]))
    con.commit()
    con.close()
    original = hermes_state.SessionDB

    class _Synthetic(original):
        def __init__(self, db_path=None, read_only=False, *a, **k):
            super().__init__(db_path=path, read_only=read_only, *a, **k)
    hermes_state.SessionDB = _Synthetic
    return path


def _epoch(value) -> float:
    import datetime as _dt
    return _dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()


def _tool_calls(messages) -> int:
    return sum(len(m.get("tool_calls") or []) for m in messages or [] if isinstance(m, dict) and m.get("role") == "assistant")


def meta_note(scn: dict, variant: dict, prof: str):
    """P-3 arm: the router's L16 note for this scenario, or None (no control, or the gate did not fire)."""
    control = variant.get("meta")
    if control not in ("ask", "escalate"):
        return None
    from lilith_router import metacognition as mc
    sig = mc.recall_gap(scn["message"], prof)
    return mc.note_for(control) if sig and sig["fired"] else None


def _focused(cl, scn) -> bool:
    users = [c for r, c in scn.get("history", []) if r == "user"]
    d = cl.classify(scn["message"], users, "social" if users else None)
    return d.mode != "social" or bool((d.signals or {}).get("tech"))


def lean_runner(spec):
    sys.path.insert(0, str(HOME))
    sys.path.insert(0, str(HOME / "hermes-agent"))
    from lilith_router import classifier as cl, config as cfgmod, policy as pol, social_cognition as sc
    from lilith_router import social_lean as sl, social_preferences as sp
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
        tone, goal = style_parts(scn, variant, _focused(cl, scn))
        policy += ("\n\n" + tone) if tone else ""
        prof, pref_note = preference_parts(scn, variant, sp, _focused(cl, scn))
        if pref_note:
            policy += "\n\n" + pref_note                  # the router appends the P-2 note to the lean policy
        mnote = meta_note(scn, variant, prof)
        if mnote:
            policy += "\n\n" + mnote                      # then the P-3 L16 note (turn_context.lean_suffix order)
        if goal:
            policy += "\n\n" + goal                       # then the P-3 appraisal goal line
        tnote = timeline_note(scn, variant, spec)
        if tnote:
            policy += "\n\n" + tnote                      # P-4 arm D: the timeline on the lean path (experiment)
        if variant.get("system_suffix"):
            policy += "\n\n" + variant["system_suffix"]
        msg = (variant.get("message_prefix", "") + "\n\n" + scn["message"]) if variant.get("message_prefix") \
            else scn["message"]
        msgs = sl.build_messages(core, policy, prof, hist, msg)
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
    sys.path.insert(0, str(HOME))
    sys.path.insert(0, str(HOME / "hermes-agent"))
    import inspect
    import logging
    logging.disable(logging.WARNING)
    from lilith_router import classifier as cl, social_preferences as sp
    from run_agent import AIAgent
    # synthetic profile only: keep the owner's stored memory out of the eval prompt when the agent supports it
    params = inspect.signature(AIAgent.__init__).parameters
    extra = {k: True for k in ("skip_memory",) if k in params}
    from gateway.run import _resolve_runtime_agent_kwargs_for_provider as res
    rt = res(spec.get("agent_provider", "openai-codex"))
    model = spec.get("agent_model", "gpt-5.6-sol")
    store = None
    if any(v.get("retrieval") == "synthetic" for v in spec["variants"].values()):
        store = synthetic_session_store(spec)

    def run(scn, variant):
        prof, pref_note = preference_parts(scn, variant, sp, _focused(cl, scn))
        system = "\n\n".join(p for p in (prof, variant.get("system_suffix")) if p) or None
        retrieval = variant.get("retrieval") == "synthetic" and store is not None
        a = AIAgent(model=model, **{k: rt[k] for k in ("provider", "base_url", "api_key", "api_mode") if k in rt},
                    quiet_mode=True, verbose_logging=False,
                    enabled_toolsets=["session_search"] if retrieval else [], skip_context_files=True,
                    load_soul_identity=True, ephemeral_system_prompt=system,
                    max_iterations=6 if retrieval else 2, **extra)
        tone, goal = style_parts(scn, variant, _focused(cl, scn))
        prefix = "\n\n".join(p for p in (variant.get("message_prefix"), tone, pref_note, meta_note(scn, variant, prof),
                                          goal, timeline_note(scn, variant, spec)) if p)  # the router's turn hint
        msg = (prefix + "\n\n" + scn["message"]) if prefix else scn["message"]
        t0 = time.monotonic()
        r = a.run_conversation(msg, conversation_history=[{"role": x, "content": y} for x, y in scn.get("history", [])])
        toks = int(getattr(a, "session_prompt_tokens", 0) or 0) + int(getattr(a, "session_completion_tokens", 0) or 0)
        n_hist = len(scn.get("history", [])) + 1
        calls = _tool_calls((r.get("messages") or [])[n_hist:])
        return (r.get("final_response") or "").strip(), toks, int((time.monotonic() - t0) * 1000), calls
    return run


def replay(spec: dict, run) -> list:
    budget, used, out = int(spec.get("budget_tokens", 50000)), 0, []
    for scn in spec["scenarios"]:
        rec = {"id": scn["id"], "replies": {}, "tokens": {}, "latency_ms": {}}
        for name, variant in spec["variants"].items():
            for k in ("replies", "tokens", "latency_ms", "tool_calls"):
                rec.setdefault(k, {})[name] = []
            for _ in range(int(spec.get("samples", 2))):
                if used >= budget:
                    rec["replies"][name].append(None)
                    continue
                try:
                    res = run(scn, variant)
                    text, toks, ms = res[:3]
                    rec["tool_calls"][name].append(res[3] if len(res) > 3 else 0)
                except Exception as exc:
                    text, toks, ms = "<<ERROR %s %s>>" % (type(exc).__name__, getattr(exc, "status_code", "")), 0, 0
                    rec["tool_calls"][name].append(0)
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
