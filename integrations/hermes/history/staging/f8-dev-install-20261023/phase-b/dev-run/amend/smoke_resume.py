"""F8r4 amended G-7 continuation (owner-requested, 2026-10-23). Run as root on lilith-dev-01 (or the WSL mirror):

    /opt/hermes-gateway-dev/current/venv/bin/python -I -B smoke_resume.py --prior-request-id <rid> [--expect-marker T]

Runs the THREE G-7 model turns that the interrupted smoke did not reach (turn 2 on f8b-s1, turn 3 on f8b-s2, turn 4
via the Core API relay on f8b-core) plus every non-spending smoke check, with the reviewed smoke_console.py imported
READ-ONLY from the installed release (same functions, prompts, thresholds, error notices). Nothing is changed in the
package. Every log window is POSITION-BASED from this run's own start (the defect that stopped the first attempt).

Cross-run checks (C*) tie the continuation to request #1 (already spent, recorded in the gate ledger):
  C1 ledger before this run = exactly one reservation, the prior request id, and nothing else;
  C2 the prior turn's Router V2 decision is the only earlier line and belongs to f8b-s1;
  C3 turn 2 (f8b-s1) carries turn 1's history: its prompt_tokens exceed request #1's;
  C4 after this run: 4 reservations in total, 4 FORWARDED, 4 shadow decisions (f8b-s1 2, f8b-s2 1, f8b-core 1).
Exit 0 = every check passed.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, "/opt/hermes-gateway-dev/current/bin")
import smoke_console as s  # noqa: E402  (reviewed, installed, root-owned read-only)

LEDGER = Path("/var/lib/private/hermes-provider-gate-dev/ledger.log")
check, call, post, results = s.check, s.call, s.post, s.results


def ledger_r() -> list[str]:
    return [l.split(" ")[2] for l in LEDGER.read_text(encoding="ascii").splitlines() if l.startswith("R ")]


def main(argv: list[str]) -> int:
    prior = argv[argv.index("--prior-request-id") + 1]
    marker = argv[argv.index("--expect-marker") + 1] if "--expect-marker" in argv else None
    since = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 2))
    check("S0 gateway ready (startup restore drained)", s.wait_ready())
    tok = s.token()
    cfg_hash = hashlib.sha256((s.HH / "config.yaml").read_bytes()).hexdigest()
    pid0 = s.gateway_pid()
    st, g0 = call(s.GATE, None, {})
    check("G0 provider gate up, key loaded", st == 200 and g0.get("key_loaded") is True,
          f"budget {g0.get('budget_used')}/{g0.get('budget_requests')}")
    r0 = ledger_r()
    check("C1 ledger before this run = exactly the prior request", r0 == [prior] and g0.get("budget_used") == 1,
          f"R={r0} used={g0.get('budget_used')}")
    d_all0 = s.decisions()
    check("C2 one earlier Router V2 shadow decision, f8b-s1, live False",
          len(d_all0) == 1 and str(d_all0[0].get("chat_id")) == "f8b-s1" and d_all0[0].get("live") is False,
          ";".join(f"{d.get('chat_id')}/{d.get('mode')}" for d in d_all0))
    prior_fw = [l for l in s.gate_lines() if l.get("decision") == "FORWARDED" and l.get("request_id") == prior]
    prior_prompt = int(prior_fw[0].get("prompt_tokens") or 0) if len(prior_fw) == 1 else -1
    d0 = len(d_all0)
    n0 = len(s.gate_lines())

    st, b = call(s.CONSOLE + "health", None, {})
    check("S1 health", st == 200 and b.get("status") == "ok", str(st))
    check("S2a no token -> 401", post("F8-SYNTHETIC ping", None)[0] == 401)
    check("S2b wrong token -> 401", post("F8-SYNTHETIC ping", "f" * 64)[0] == 401)
    big = json.dumps({"message": "x" * (70 * 1024)}).encode()
    st, _ = call(s.CONSOLE, big, {"Content-Type": "application/json", "X-LILITH-OS-Token": tok})
    check("S3 70 KiB body -> 413", st == 413, str(st))
    st, _ = call(s.CONSOLE, b"{not json", {"Content-Type": "application/json", "X-LILITH-OS-Token": tok, "Content-Length": "9"})
    check("S4 invalid JSON -> 400", st == 400, str(st))

    # The two direct turns the interrupted smoke never reached (identical text and sessions to smoke_console.py).
    turns = [(2, "f8b-s1", "F8-SYNTHETIC turn 2: what was the number of my previous turn? One sentence."),
             (3, "f8b-s2", "F8-SYNTHETIC turn 3: explain in one sentence why tests use synthetic text.")]
    sessions = []
    for i, sess, text in turns:
        st, b = post(text, tok, session=sess)
        ok, detail = s.model_reply_ok(st, b, marker)
        check(f"S5.{i} model turn completes with a model reply ({sess})", ok, detail)
        sessions.append(sess)

    for cmd in ("/update", "/tools enable terminal", "/skills install demo", "/model --global x", "/cron list",
                "/reload", "/restart", "/yolo", "/sethome"):
        st, b = post(cmd, tok, session="f8b-cmd")
        reply = (b.get("reply") or "").lower()
        check(f"S6 slash not executed: {cmd}", st == 200 and ("admin-only" in reply or "unknown command" in reply),
              reply[:60])
    check("S6z config.yaml unchanged", hashlib.sha256((s.HH / "config.yaml").read_bytes()).hexdigest() == cfg_hash)

    st, b = call(s.CORE, json.dumps({"message": "F8-SYNTHETIC turn 4 via the Core API relay: one sentence.",
                                     "session": "f8b-core"}).encode(), {"Content-Type": "application/json"})
    ok, detail = s.model_reply_ok(st, b, marker)
    check("S10 Core API relay -> model reply", ok, detail)
    sessions.append("f8b-core")
    st, b = call(s.EVIDENCE, json.dumps({"action": "open"}).encode(), {"Content-Type": "application/json"})
    check("S11 owner capture inactive (403)", st == 403, f"{st} {b.get('detail')}")

    rmode = next((l.split(":", 1)[1].strip() for l in (s.HH / "lilith_router" / "router.yaml").read_text().splitlines()
                  if l.startswith("mode:")), "")
    check("R0 Router V2 configured mode = shadow", rmode == "shadow", rmode)
    new = s.decisions()[d0:]
    for sess in sorted(set(sessions)):
        want = sessions.count(sess)
        got = [d for d in new if str(d.get("chat_id")) == sess]
        ok = len(got) == want and all(d.get("live") is False and d.get("platform") == "lilith_os"
                                      and d.get("mode") and "confidence" in d for d in got)
        check(f"R1 Router V2 shadow decision per turn ({sess})", ok,
              f"{len(got)}/{want} " + ";".join(f"{d.get('mode')}/{d.get('reason')}" for d in got)[:120])

    time.sleep(1)
    st, g1 = call(s.GATE, None, {})
    used = int(g1.get("budget_used", -1)) - int(g0.get("budget_used", 0))
    check("B1 gate budget used == model turns", used == len(sessions), f"{used} for {len(sessions)} turns")
    new_gate = s.gate_lines()[n0:]
    fw = [l for l in new_gate if l.get("decision") == "FORWARDED"]
    check("B2 gate forwarded == model turns, all 200, capped <= 1024, model pinned",
          len(fw) == len(sessions) and all(l.get("status") == 200 and int(l.get("max_completion_tokens", 0)) <= 1024
                                           and l.get("model") == "openai/gpt-oss-120b" for l in fw),
          f"{len(fw)} forwarded; tokens={[l.get('completion_tokens') for l in fw]}")
    refused = [l for l in new_gate if l.get("decision") == "REFUSED"]
    bad_ref = [l for l in refused if l.get("method") != "GET"]
    check("B3 no refused POSTs; GET probes answered locally only", not bad_ref,
          f"local GET probes={len(refused) - len(bad_ref)}; " + ";".join(f"{l.get('reason')}:{l.get('path')}" for l in bad_ref)[:100])
    t2 = int(fw[0].get("prompt_tokens") or 0) if fw else 0
    check("C3 turn 2 carries turn 1's history (prompt_tokens #2 > #1)", prior_prompt > 0 and t2 > prior_prompt,
          f"#1={prior_prompt} #2={t2}")
    r1 = ledger_r()
    d_all = s.decisions()
    per = {k: sum(1 for d in d_all if str(d.get("chat_id")) == k) for k in ("f8b-s1", "f8b-s2", "f8b-core")}
    all_fw = [l for l in s.gate_lines() if l.get("decision") == "FORWARDED"]
    check("C4 totals: 4 reservations (first = prior), 4 FORWARDED, decisions s1=2 s2=1 core=1, all live False",
          len(r1) == 4 and r1[0] == prior and len(all_fw) == 4 and per == {"f8b-s1": 2, "f8b-s2": 1, "f8b-core": 1}
          and len(d_all) == 4 and all(d.get("live") is False for d in d_all),
          f"R={len(r1)} fw={len(all_fw)} per={per}")

    key = s.KEYFILE.read_text().strip() if s.KEYFILE.exists() else ""
    check("K0 key provisioned (root-only file)", len(key) >= 20 and oct(s.KEYFILE.stat().st_mode & 0o777) == "0o600")
    pid = s.gateway_pid()
    env = Path(f"/proc/{pid}/environ").read_bytes() if pid and pid != "0" else b""
    hits = []
    if key:
        kb = key.encode()
        if kb in env:
            hits.append("gateway environ")
        if kb in Path(f"/proc/{pid}/cmdline").read_bytes():
            hits.append("gateway cmdline")
        grep = subprocess.run(["grep", "-rlF", "--", key, str(s.HH)], capture_output=True, text=True).stdout.strip()
        if grep:
            hits.append("HERMES_HOME:" + grep.replace("\n", ","))
        for args in (["journalctl", "--namespace=hermes-gateway-dev", "-o", "cat", "--no-pager"],
                     ["journalctl", "-o", "cat", "--no-pager", "--since", since]):
            if key in s.run(*args):
                hits.append("journal " + args[1])
    check("K1 key absent from gateway env/cmdline, HERMES_HOME, logs, journals", key != "" and not hits, ",".join(hits))
    r = subprocess.run(["runuser", "-u", "lilith", "--", "test", "-r", str(s.KEYFILE)])
    r2 = subprocess.run(["runuser", "-u", "lilith", "--", "ls", "/run/credentials/hermes-provider-gate-dev.service"],
                        capture_output=True)
    check("K2 uid lilith (gateway, Core API) cannot read the key file or the gate's credential", r.returncode != 0
          and r2.returncode != 0)

    ss = s.run("ss", "-Hltnup").splitlines()
    mine = [l for l in ss if f"pid={pid0}," in l]
    check("S7 gateway listens on 127.0.0.1:9901 only", len(mine) == 1 and "127.0.0.1:9901" in mine[0], "; ".join(mine))
    est = s.run("ss", "-Htnp", "state", "established").splitlines()
    remote = [l for l in est if f"pid={pid0}," in l and not l.split()[3].startswith("127.0.0.1:")]
    check("S8 gateway has no non-loopback connections (provider only via the gate)", not remote, "; ".join(remote))
    check("S9 gateway still the same process (this run)", s.gateway_pid() == pid0, pid0)

    bad = [x for x in results if not x[1]]
    print(f"F8_RESUME_{'PASS' if not bad else 'FAIL'} turns={len(sessions)} {len(results) - len(bad)}/{len(results)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
