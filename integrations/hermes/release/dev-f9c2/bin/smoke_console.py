"""F8 synthetic console smoke test (gate G-7). Run as root on lilith-dev-01:

    /opt/hermes-gateway-dev/current/venv/bin/python -I -B /opt/hermes-gateway-dev/current/bin/smoke_console.py \
        --phase B [--core-api] [--expect-marker TEXT]

Synthetic inputs only (prefixed F8-SYNTHETIC). Never prints the console token or the provider key.
Phase B (F8r3, provider through the local gate): exactly 4 model turns (3 direct, 1 via the Core API relay), each must
  * complete with a real model reply (not a gateway/provider error notice);
  * produce a Router V2 SHADOW decision line for its session (B-7: plain Hermes replies are not proof);
  * consume exactly one gate request (B-3), capped at <= 1024 output tokens, forwarded with status 200;
and the provider key must not appear anywhere the gateway (uid lilith) can reach. Exit 0 = every check passed.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HH = Path("/home/lilith/.hermes-dev")
CONSOLE = "http://127.0.0.1:9901/"
GATE = "http://127.0.0.1:9911/healthz"
CORE = "http://127.0.0.1:8765/os/conversation"
EVIDENCE = "http://127.0.0.1:8765/os/conversation/evidence"
DECISIONS = HH / "logs" / "lilith-router-decisions.log"
KEYFILE = Path("/etc/hermes-provider-gate-dev/credentials/groq-api-key")
# Gateway/provider failure notices start with "⚠️"; gate refusals carry "F8_GATE_" (specific, so a model reply that
# merely mentions an error is not misread as a failure).
ERROR_NOTICES = ("provider authentication failed", "f8_gate_", "⚠️", "completed the turn without a text reply",
                 "lilith is starting")
results: list[tuple[str, bool, str]] = []


def token() -> str:
    for line in (HH / ".env").read_text().splitlines():
        if line.startswith("LILITH_OS_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("no token")


def call(url: str, body: bytes | None, headers: dict, timeout: float = 200) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def post(msg: str, tok: str | None, session: str = "f8-smoke") -> tuple[int, dict]:
    h = {"Content-Type": "application/json"}
    if tok is not None:
        h["X-LILITH-OS-Token"] = tok
    return call(CONSOLE, json.dumps({"message": msg, "session": session}).encode(), h)


def run(*cmd: str) -> str:
    return subprocess.run(list(cmd), capture_output=True, text=True).stdout


def gateway_pid() -> str:
    return run("systemctl", "show", "-p", "MainPID", "--value", "hermes-gateway-dev").strip()


def wait_ready(timeout: float = 90) -> bool:
    """Readiness = Hermes' own log line written after its startup-restore queue drains (F8r2 finding)."""
    log = HH / "logs" / "gateway.log"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            lines = log.read_text(errors="replace").splitlines()
        except OSError:
            lines = []
        starts = [i for i, l in enumerate(lines) if "Starting Hermes Gateway" in l]
        if starts and any("Press Ctrl+C to stop" in l for l in lines[starts[-1]:]):
            return True
        time.sleep(1)
    return False


def decisions() -> list[dict]:
    out = []
    try:
        for line in DECISIONS.read_text(errors="replace").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    except OSError:
        pass
    return out


def gate_lines() -> list[dict]:
    text = run("journalctl", "--namespace=hermes-gateway-dev", "-u", "hermes-provider-gate-dev", "-o", "cat",
               "--no-pager")
    return [json.loads(l[len("F8_GATE "):]) for l in text.splitlines() if l.startswith("F8_GATE {")]


def model_reply_ok(s: int, b: dict, marker: str | None) -> tuple[bool, str]:
    reply = b.get("reply") or ""
    low = reply.lower()
    ok = s == 200 and b.get("state") == "completed" and len(reply.strip()) > 0 \
        and not any(n in low for n in ERROR_NOTICES) and (marker is None or marker in reply)
    return ok, f"{s} state={b.get('state')} len={len(reply)} head={reply[:60]!r}"


def main(argv: list[str]) -> int:
    phase = argv[argv.index("--phase") + 1] if "--phase" in argv else "B"
    marker = argv[argv.index("--expect-marker") + 1] if "--expect-marker" in argv else None
    assert phase == "B", "F8r3 smoke is Phase B only"
    since = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 2))
    check("S0 gateway ready (startup restore drained)", wait_ready())
    tok = token()
    cfg_hash = hashlib.sha256((HH / "config.yaml").read_bytes()).hexdigest()
    pid0 = gateway_pid()
    s, g0 = call(GATE, None, {})
    check("G0 provider gate up, key loaded", s == 200 and g0.get("key_loaded") is True,
          f"budget {g0.get('budget_used')}/{g0.get('budget_requests')}")
    d0 = len(decisions())
    n0 = len(gate_lines())  # position-based: only gate lines written during this smoke run count

    s, b = call(CONSOLE + "health", None, {})
    check("S1 health", s == 200 and b.get("status") == "ok", str(s))
    check("S2a no token -> 401", post("F8-SYNTHETIC ping", None)[0] == 401)
    check("S2b wrong token -> 401", post("F8-SYNTHETIC ping", "f" * 64)[0] == 401)
    big = json.dumps({"message": "x" * (70 * 1024)}).encode()
    s, _ = call(CONSOLE, big, {"Content-Type": "application/json", "X-LILITH-OS-Token": tok})
    check("S3 70 KiB body -> 413", s == 413, str(s))
    s, _ = call(CONSOLE, b"{not json", {"Content-Type": "application/json", "X-LILITH-OS-Token": tok, "Content-Length": "9"})
    check("S4 invalid JSON -> 400", s == 400, str(s))

    turns = [("f8b-s1", "F8-SYNTHETIC turn 1: reply with one short friendly sentence."),
             ("f8b-s1", "F8-SYNTHETIC turn 2: what was the number of my previous turn? One sentence."),
             ("f8b-s2", "F8-SYNTHETIC turn 3: explain in one sentence why tests use synthetic text.")]
    sessions = []
    for i, (sess, text) in enumerate(turns, 1):
        s, b = post(text, tok, session=sess)
        ok, detail = model_reply_ok(s, b, marker)
        check(f"S5.{i} model turn completes with a model reply ({sess})", ok, detail)
        sessions.append(sess)

    for cmd in ("/update", "/tools enable terminal", "/skills install demo", "/model --global x", "/cron list",
                "/reload", "/restart", "/yolo", "/sethome"):
        s, b = post(cmd, tok, session="f8b-cmd")
        reply = (b.get("reply") or "").lower()
        check(f"S6 slash not executed: {cmd}", s == 200 and ("admin-only" in reply or "unknown command" in reply),
              reply[:60])
    check("S6z config.yaml unchanged", hashlib.sha256((HH / "config.yaml").read_bytes()).hexdigest() == cfg_hash)

    if "--core-api" in argv:
        s, b = call(CORE, json.dumps({"message": "F8-SYNTHETIC turn 4 via the Core API relay: one sentence.",
                                      "session": "f8b-core"}).encode(), {"Content-Type": "application/json"})
        ok, detail = model_reply_ok(s, b, marker)
        check("S10 Core API relay -> model reply", ok, detail)
        sessions.append("f8b-core")
        s, b = call(EVIDENCE, json.dumps({"action": "open"}).encode(), {"Content-Type": "application/json"})
        check("S11 owner capture inactive (403)", s == 403, f"{s} {b.get('detail')}")

    # B-7: independent Router V2 shadow evidence, one decision per model turn, none for slash commands' budget.
    rmode = next((l.split(":", 1)[1].strip() for l in (HH / "lilith_router" / "router.yaml").read_text().splitlines()
                  if l.startswith("mode:")), "")
    check("R0 Router V2 configured mode = shadow", rmode == "shadow", rmode)
    new = decisions()[d0:]
    for sess in sorted(set(sessions)):
        want = sessions.count(sess)
        got = [d for d in new if str(d.get("chat_id")) == sess]
        # Each decision line: the router's classification (`mode`: social/work/...), `live` False (shadow: the
        # router.yaml mode is shadow, so it never overrides), platform lilith_os, chat_id = this session.
        ok = len(got) == want and all(d.get("live") is False and d.get("platform") == "lilith_os"
                                      and d.get("mode") and "confidence" in d for d in got)
        check(f"R1 Router V2 shadow decision per turn ({sess})", ok,
              f"{len(got)}/{want} " + ";".join(f"{d.get('mode')}/{d.get('reason')}" for d in got)[:120])

    # B-3: exactly one gate request per model turn, all forwarded, capped, no slash-command spend.
    time.sleep(1)
    s, g1 = call(GATE, None, {})
    used = int(g1.get("budget_used", -1)) - int(g0.get("budget_used", 0))
    check("B1 gate budget used == model turns", used == len(sessions), f"{used} for {len(sessions)} turns")
    new_gate = gate_lines()[n0:]
    fw = [l for l in new_gate if l.get("decision") == "FORWARDED"]
    check("B2 gate forwarded == model turns, all 200, capped <= 1024, model pinned",
          len(fw) == len(sessions) and all(l.get("status") == 200 and int(l.get("max_completion_tokens", 0)) <= 1024
                                           and l.get("model") == "openai/gpt-oss-120b" for l in fw),
          f"{len(fw)} forwarded; tokens={[l.get('completion_tokens') for l in fw]}")
    # Hermes probes local-server capability paths (GET /props, /version, /models); the gate answers 404 locally and
    # never forwards them. Any refused POST (policy, budget, key) during the turns is a failure.
    refused = [l for l in new_gate if l.get("decision") == "REFUSED"]
    bad_ref = [l for l in refused if l.get("method") != "GET"]
    check("B3 no refused POSTs; GET probes answered locally only", not bad_ref,
          f"local GET probes={len(refused) - len(bad_ref)}; " + ";".join(f"{l.get('reason')}:{l.get('path')}" for l in bad_ref)[:100])

    # Key isolation: the key exists only for the gate; never in the gateway's reach.
    key = KEYFILE.read_text().strip() if KEYFILE.exists() else ""
    check("K0 key provisioned (root-only file)", len(key) >= 20 and oct(KEYFILE.stat().st_mode & 0o777) == "0o600")
    pid = gateway_pid()
    env = Path(f"/proc/{pid}/environ").read_bytes() if pid and pid != "0" else b""
    hits = []
    if key:
        kb = key.encode()
        if kb in env:
            hits.append("gateway environ")
        if kb in Path(f"/proc/{pid}/cmdline").read_bytes():
            hits.append("gateway cmdline")
        grep = subprocess.run(["grep", "-rlF", "--", key, str(HH)], capture_output=True, text=True).stdout.strip()
        if grep:
            hits.append("HERMES_HOME:" + grep.replace("\n", ","))
        for args in (["journalctl", "--namespace=hermes-gateway-dev", "-o", "cat", "--no-pager"],
                     ["journalctl", "-o", "cat", "--no-pager", "--since", since]):
            if key in run(*args):
                hits.append("journal " + args[1])
    check("K1 key absent from gateway env/cmdline, HERMES_HOME, logs, journals", key != "" and not hits, ",".join(hits))
    r = subprocess.run(["runuser", "-u", "lilith", "--", "test", "-r", str(KEYFILE)])
    r2 = subprocess.run(["runuser", "-u", "lilith", "--", "ls", "/run/credentials/hermes-provider-gate-dev.service"],
                        capture_output=True)
    check("K2 uid lilith (gateway, Core API) cannot read the key file or the gate's credential", r.returncode != 0
          and r2.returncode != 0)

    ss = run("ss", "-Hltnup").splitlines()
    mine = [l for l in ss if f"pid={pid0}," in l]
    check("S7 gateway listens on 127.0.0.1:9901 only", len(mine) == 1 and "127.0.0.1:9901" in mine[0], "; ".join(mine))
    est = run("ss", "-Htnp", "state", "established").splitlines()
    remote = [l for l in est if f"pid={pid0}," in l and not l.split()[3].startswith("127.0.0.1:")]
    check("S8 gateway has no non-loopback connections (provider only via the gate)", not remote, "; ".join(remote))
    check("S9 gateway still the same process", gateway_pid() == pid0, pid0)

    bad = [x for x in results if not x[1]]
    print(f"F8_SMOKE_{'PASS' if not bad else 'FAIL'} phase=B turns={len(sessions)} {len(results) - len(bad)}/{len(results)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
