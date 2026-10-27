"""F8 synthetic console smoke test (gates G-7/G-8). Run as root on lilith-dev-01:

    /opt/hermes-gateway-dev/current/venv/bin/python -I -B /opt/hermes-gateway-dev/current/bin/smoke_console.py [--phase A|B] [--core-api]

Synthetic inputs only (prefixed F8-SYNTHETIC). Reads the DEV console token from HERMES_HOME/.env and never prints it.
Phase A (no provider credential): the model turn must fail closed with a reply (no crash, no egress).
Phase B (provider configured, separately authorized): the model turn must complete. Exit 0 = every check passed.
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
CORE = "http://127.0.0.1:8765/os/conversation"
EVIDENCE = "http://127.0.0.1:8765/os/conversation/evidence"
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


def gateway_pid() -> str:
    return subprocess.run(["systemctl", "show", "-p", "MainPID", "--value", "hermes-gateway-dev"],
                          capture_output=True, text=True).stdout.strip()


def main(argv: list[str]) -> int:
    phase = argv[argv.index("--phase") + 1] if "--phase" in argv else "A"
    tok = token()
    cfg_hash = hashlib.sha256((HH / "config.yaml").read_bytes()).hexdigest()
    pid0 = gateway_pid()

    s, b = call(CONSOLE + "health", None, {})
    check("S1 health", s == 200 and b.get("status") == "ok", str(s))
    check("S2a no token -> 401", post("F8-SYNTHETIC ping", None)[0] == 401)
    check("S2b wrong token -> 401", post("F8-SYNTHETIC ping", "f" * 64)[0] == 401)
    big = json.dumps({"message": "x" * (70 * 1024)}).encode()
    s, _ = call(CONSOLE, big, {"Content-Type": "application/json", "X-LILITH-OS-Token": tok})
    check("S3 70 KiB body -> 413", s == 413, str(s))
    s, _ = call(CONSOLE, b"{not json", {"Content-Type": "application/json", "X-LILITH-OS-Token": tok, "Content-Length": "9"})
    check("S4 invalid JSON -> 400", s == 400, str(s))

    t0 = time.time()
    s, b = post("F8-SYNTHETIC hello, this is an infrastructure smoke test. Reply with one short sentence.", tok)
    took = f"{time.time() - t0:.1f}s state={b.get('state')} reply={(b.get('reply') or '')[:160]!r}"
    if phase == "A":
        # Observed in the F8 dry run: the gateway answers "Provider authentication failed ..." (adapter state
        # "completed", because a reply was delivered) without any network attempt.
        check("S5 model turn fails closed without provider (reply, no crash)", s == 200
              and "provider authentication failed" in (b.get("reply") or "").lower(), took)
    else:
        check("S5 model turn completes", s == 200 and b.get("state") == "completed" and bool(b.get("reply")), took)

    for cmd in ("/update", "/tools enable terminal", "/skills install demo", "/model --global x", "/cron list",
                "/reload", "/restart", "/yolo", "/sethome"):
        s, b = post(cmd, tok, session="f8-smoke-cmd")
        reply = (b.get("reply") or "").lower()
        # Either the gate refuses it ("admin-only") or the gateway has no such command ("unknown command").
        check(f"S6 slash not executed: {cmd}", s == 200 and ("admin-only" in reply or "unknown command" in reply),
              reply[:80])
    check("S6z config.yaml unchanged", hashlib.sha256((HH / "config.yaml").read_bytes()).hexdigest() == cfg_hash)

    ss = subprocess.run(["ss", "-Hltnup"], capture_output=True, text=True).stdout.splitlines()
    mine = [l for l in ss if f"pid={pid0}," in l]
    check("S7 gateway listens on 127.0.0.1:9901 only", len(mine) == 1 and "127.0.0.1:9901" in mine[0], "; ".join(mine))
    est = subprocess.run(["ss", "-Htnp", "state", "established"], capture_output=True, text=True).stdout.splitlines()
    remote = [l for l in est if f"pid={pid0}," in l and "127.0.0.1" not in l.split()[3]]
    check("S8 no non-loopback connections from gateway", phase == "B" or not remote, "; ".join(remote))
    check("S9 gateway still the same process", gateway_pid() == pid0, pid0)

    if "--core-api" in argv:
        s, b = call(CORE, json.dumps({"message": "F8-SYNTHETIC relay check", "session": "f8-smoke-core"}).encode(),
                    {"Content-Type": "application/json"})
        check("S10 Core API relay reaches the console", s == 200 and "reply" in b, f"{s} state={b.get('state')}")
        s, b = call(EVIDENCE, json.dumps({"action": "open"}).encode(), {"Content-Type": "application/json"})
        check("S11 owner capture inactive (403)", s == 403, f"{s} {b.get('detail')}")

    bad = [r for r in results if not r[1]]
    print(f"F8_SMOKE_{'PASS' if not bad else 'FAIL'} phase={phase} {len(results) - len(bad)}/{len(results)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
