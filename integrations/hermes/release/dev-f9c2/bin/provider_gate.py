"""F8r4 DEV provider gate: the ONLY holder of the Groq API key and the ONLY F8 process with internet egress.

The Hermes gateway (loopback-only sandbox, no DNS) calls  http://127.0.0.1:9911/openai/v1/chat/completions  with a
non-secret client token. For every request, in this order, the gate:
  1. accepts exactly  POST /openai/v1/chat/completions  (origin-form only; CONNECT, absolute-form, other paths and
     methods are refused; the Host header is ignored);
  2. enforces the request policy on the WHOLE body, streaming or not: allowlisted model; no tools / functions /
     response formats / documents; only system|user|assistant messages without tool calls; n=1;
     max_completion_tokens = min(asked, cap); default reasoning_effort; body-size cap;
  3. requires a provisioned key and a non-exhausted budget (read-only check);
  4. resolves the single upstream host and requires a GLOBAL unicast IPv4 address (no loopback / private / CGNAT /
     link-local / metadata / reserved): DNS rebinding cannot redirect it;
  5. opens TCP + TLS to that address with the system trust store and hostname verification (the certificate must be
     valid for the upstream host): a rebound or spoofed address fails here;
  6. ONLY THEN reserves one request in the append-only, fsync'd ledger (the persistent budget). Failures in steps
     1-5 send nothing to the provider and spend nothing; every failure after step 6 is ambiguous and stays spent
     (never refunded, never retried, so never double-spent);
  7. sends the request with the injected key, streams the reply back (no redirect is ever followed), records the
     reported output tokens and the provider's rate-limit headers; one metadata log line, never content or the key.
Usage:  provider_gate.py /etc/hermes-provider-gate-dev/gate.json        Stdlib only.
"""
from __future__ import annotations

import datetime
import http.client
import ipaddress
import json
import os
import socket
import ssl
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CONFIG_KEYS = {
    "listen_host", "listen_port", "upstream_host", "upstream_port", "local_path", "upstream_path", "allowed_models",
    "max_output_tokens", "default_reasoning_effort", "max_request_bytes", "max_response_bytes", "budget_requests",
    "daily_requests", "daily_output_tokens", "timeout_seconds", "client_token",
}
PASS_FIELDS = {
    "model", "messages", "max_tokens", "max_completion_tokens", "temperature", "top_p", "stream", "stream_options",
    "reasoning_effort", "include_reasoning", "stop", "seed", "user", "frequency_penalty", "presence_penalty", "n",
}
FORBIDDEN_FIELDS = {"tools", "tool_choice", "functions", "function_call", "parallel_tool_calls", "response_format",
                    "search_settings", "documents", "compound_custom", "logprobs", "top_logprobs"}
MESSAGE_ROLES = {"system", "user", "assistant"}
MESSAGE_FORBIDDEN = {"tool_calls", "function_call", "tool_call_id"}
PASS_HEADERS = {"content-type", "retry-after", "x-ratelimit-limit-requests", "x-ratelimit-remaining-requests",
                "x-ratelimit-limit-tokens", "x-ratelimit-remaining-tokens", "x-request-id"}
NON_GLOBAL_EXTRA = [ipaddress.ip_network("100.64.0.0/10")]
_LOCK = threading.Lock()


def now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def log(**fields) -> None:
    fields["ts"] = now().isoformat(timespec="seconds")
    print("F8_GATE " + json.dumps(fields, sort_keys=True), flush=True)


def load_config(path: str) -> dict:
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    if set(cfg) != CONFIG_KEYS:
        raise SystemExit(f"gate config keys mismatch: {sorted(set(cfg) ^ CONFIG_KEYS)}")
    if cfg["listen_host"] != "127.0.0.1":
        raise SystemExit("gate must listen on 127.0.0.1 only")
    if not (0 < int(cfg["max_output_tokens"]) <= 4096) or int(cfg["budget_requests"]) < 0:
        raise SystemExit("gate limits out of range")
    return cfg


def load_key() -> str:
    cred = os.environ.get("CREDENTIALS_DIRECTORY")
    if not cred:
        return ""
    try:
        key = (Path(cred) / "groq-api-key").read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return key if len(key) >= 20 and "\n" not in key and " " not in key else ""


class Ledger:
    """Persistent budget = an append-only ledger in $STATE_DIRECTORY/ledger.log (0600), fsync'd on every append.

    Lines:  R <utc-iso> <request-id>      one reserved (= possibly sent) provider request
            T <utc-iso> <n>               output tokens reported for a request
            RESET <utc-iso> <note>        owner-approved budget reset (gate_budget.sh); counts start again after it
    Budget used = R lines after the last RESET. Day counters = R / T lines of the current UTC date after it.
    Fail-closed: an unreadable or malformed ledger refuses every request (it is never read as "zero spent").
    A crash can lose at most the in-flight request's token line, never a reservation (fsync before sending).
    """

    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.dir = Path(os.environ.get("STATE_DIRECTORY", "/var/lib/hermes-provider-gate-dev"))
        self.path = self.dir / "ledger.log"
        if not self.path.exists():
            self._append(f"RESET {now().isoformat(timespec='seconds')} initial-ledger")

    def _append(self, line: str) -> None:
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, (line + "\n").encode())
            os.fsync(fd)
        finally:
            os.close(fd)
        dfd = os.open(self.dir, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)

    def counters(self) -> dict:
        today = now().date().isoformat()
        used = day_req = day_tok = 0
        lines = self.path.read_text(encoding="ascii").splitlines()  # raises -> fail closed
        for line in lines:
            parts = line.split(" ")
            if len(parts) < 3 or parts[0] not in ("R", "T", "RESET"):
                raise ValueError("LEDGER_MALFORMED")
            kind, ts = parts[0], parts[1]
            if kind == "RESET":  # an owner-approved reset restarts every counter (budget and day)
                used = day_req = day_tok = 0
            elif kind == "R":
                used += 1
                day_req += ts.startswith(today)
            else:
                day_tok += int(parts[2]) if ts.startswith(today) else 0
        return {"budget_used": used, "day_requests": day_req, "day_output_tokens": day_tok}

    def check(self) -> tuple[bool, str, dict]:
        with _LOCK:
            try:
                c = self.counters()
            except (OSError, ValueError, UnicodeDecodeError):
                return False, "LEDGER_UNREADABLE", {"budget_used": -1}
            if c["budget_used"] >= int(self.cfg["budget_requests"]):
                return False, "BUDGET_EXHAUSTED", c
            if c["day_requests"] >= int(self.cfg["daily_requests"]):
                return False, "DAILY_REQUESTS_EXHAUSTED", c
            if c["day_output_tokens"] >= int(self.cfg["daily_output_tokens"]):
                return False, "DAILY_TOKENS_EXHAUSTED", c
            return True, "", c

    def reserve(self, rid: str) -> tuple[bool, str, dict]:
        with _LOCK:
            try:
                c = self.counters()
            except (OSError, ValueError, UnicodeDecodeError):
                return False, "LEDGER_UNREADABLE", {"budget_used": -1}
            if c["budget_used"] >= int(self.cfg["budget_requests"]) or c["day_requests"] >= int(self.cfg["daily_requests"]):
                return False, "BUDGET_EXHAUSTED", c
            self._append(f"R {now().isoformat(timespec='seconds')} {rid}")
            c["budget_used"] += 1
            c["day_requests"] += 1
            return True, "", c

    def tokens(self, n: int) -> None:
        with _LOCK:
            self._append(f"T {now().isoformat(timespec='seconds')} {max(0, int(n))}")


def global_address(host: str, port: int) -> str:
    for _, _, _, _, addr in socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM):
        ip = ipaddress.ip_address(addr[0])
        if ip.is_global and not ip.is_multicast and not any(ip in n for n in NON_GLOBAL_EXTRA):
            return addr[0]
    raise OSError("UPSTREAM_ADDRESS_NOT_GLOBAL")


def sanitize(body, cfg: dict) -> tuple[dict, list]:
    if not isinstance(body, dict) or not isinstance(body.get("messages"), list) or not body["messages"]:
        raise ValueError("BODY_INVALID")
    if body.get("model") not in cfg["allowed_models"]:
        raise ValueError("MODEL_NOT_ALLOWED")
    for f in FORBIDDEN_FIELDS:
        if f in body and body[f] not in (None, [], {}, False):
            raise ValueError(f"FORBIDDEN_FIELD_{f}")
    for m in body["messages"]:
        if not isinstance(m, dict) or m.get("role") not in MESSAGE_ROLES or MESSAGE_FORBIDDEN & set(m):
            raise ValueError("MESSAGE_NOT_ALLOWED")
    if body.get("n", 1) != 1:
        raise ValueError("N_NOT_1")
    if not isinstance(body.get("stream", False), bool):
        raise ValueError("BODY_INVALID")
    dropped = sorted(k for k in body if k not in PASS_FIELDS)
    out = {k: v for k, v in body.items() if k in PASS_FIELDS}
    cap = int(cfg["max_output_tokens"])
    asked = out.pop("max_tokens", None)
    asked2 = out.pop("max_completion_tokens", None)
    asked = asked if asked is not None else asked2
    try:
        asked = int(asked) if asked is not None else cap
    except (TypeError, ValueError):
        asked = cap
    out["max_completion_tokens"] = max(1, min(asked, cap))
    out.setdefault("reasoning_effort", cfg["default_reasoning_effort"])
    out.pop("n", None)
    return out, dropped


def usage_tokens(raw: bytes) -> tuple[int, int]:
    text = raw.decode("utf-8", "replace")
    candidates = [text] if text.lstrip().startswith("{") else [
        line[5:].strip() for line in text.splitlines() if line.startswith("data:") and "usage" in line]
    for c in reversed(candidates):
        try:
            d = json.loads(c)
        except ValueError:
            continue
        u = d.get("usage") or (d.get("x_groq") or {}).get("usage") or {}
        if u:
            return int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))
    return 0, 0


class Gate(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.ledger = Ledger(cfg)
        self.ctx = ssl.create_default_context()  # system trust store; check_hostname + CERT_REQUIRED
        super().__init__((cfg["listen_host"], int(cfg["listen_port"])), Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "f8-gate"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args) -> None:
        pass

    def _refuse(self, code: int, reason: str, **extra) -> None:
        body = json.dumps({"error": {"message": f"F8_GATE_{reason}", "type": "gate_refusal"}}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True
        log(decision="REFUSED", reason=reason, method=self.command, path=self.path[:80], status=code, **extra)

    def do_CONNECT(self) -> None:
        self._refuse(405, "CONNECT_NOT_ALLOWED")

    def do_GET(self) -> None:
        if self.path == "/healthz":
            ok, why, c = self.server.ledger.check()
            body = json.dumps({"ok": True, "key_loaded": bool(load_key()), "budget_requests":
                               int(self.server.cfg["budget_requests"]), "available": ok, "state": why or "OK", **c}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._refuse(404, "PATH_NOT_ALLOWED")

    do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = lambda self: self._refuse(405, "METHOD_NOT_ALLOWED")

    def do_POST(self) -> None:
        cfg, started = self.server.cfg, time.time()
        if self.path != cfg["local_path"]:  # origin-form only: absolute-form "http://host/..." never matches
            return self._refuse(404, "PATH_NOT_ALLOWED")
        if (self.headers.get("Authorization") or "") != "Bearer " + cfg["client_token"]:
            return self._refuse(401, "CLIENT_TOKEN_INVALID")
        if self.headers.get("Transfer-Encoding"):
            return self._refuse(411, "CHUNKED_REQUEST_NOT_ALLOWED")
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length <= 0 or length > int(cfg["max_request_bytes"]):
            return self._refuse(413, "REQUEST_SIZE", bytes=length)
        try:
            body, dropped = sanitize(json.loads(self.rfile.read(length)), cfg)
        except ValueError as exc:  # json.JSONDecodeError is a ValueError
            reason = str(exc) if str(exc).split("_")[0] in ("BODY", "MODEL", "FORBIDDEN", "MESSAGE", "N") else "BODY_INVALID"
            return self._refuse(400, reason)
        key = load_key()
        if not key:
            return self._refuse(503, "KEY_NOT_PROVISIONED")
        ok, why, c = self.server.ledger.check()
        if not ok:
            return self._refuse(429 if "EXHAUSTED" in why else 503, why, budget_used=c.get("budget_used"))
        port = int(cfg["upstream_port"])
        try:
            ip = global_address(cfg["upstream_host"], port)
            raw = socket.create_connection((ip, port), timeout=int(cfg["timeout_seconds"]))
            tls = self.server.ctx.wrap_socket(raw, server_hostname=cfg["upstream_host"])
        except (OSError, ssl.SSLError) as exc:
            reason = str(exc) if str(exc) == "UPSTREAM_ADDRESS_NOT_GLOBAL" else "UPSTREAM_CONNECT_" + type(exc).__name__
            return self._refuse(502, reason, spent=False)
        rid = os.urandom(6).hex()
        ok, why, c = self.server.ledger.reserve(rid)
        if not ok:
            tls.close()
            return self._refuse(429 if "EXHAUSTED" in why else 503, why, budget_used=c.get("budget_used"))
        payload = json.dumps(body).encode()
        status, sent, prompt_t, completion_t, rl = 0, 0, 0, 0, {}
        try:
            conn = http.client.HTTPSConnection(cfg["upstream_host"], port, timeout=int(cfg["timeout_seconds"]),
                                               context=self.server.ctx)
            conn.sock = tls
            conn.request("POST", cfg["upstream_path"], body=payload, headers={
                "Authorization": "Bearer " + key, "Content-Type": "application/json",
                "Accept": "text/event-stream" if body.get("stream") else "application/json",
                "User-Agent": "lilith-f8-gate/1"})
            resp = conn.getresponse()
            status = resp.status
            self.send_response(status)
            for h, v in resp.getheaders():
                if h.lower() in PASS_HEADERS:
                    self.send_header(h, v)
                if h.lower().startswith("x-ratelimit-"):
                    rl[h.lower()[len("x-ratelimit-"):]] = v
            self.send_header("Connection", "close")
            self.end_headers()
            tail, limit = b"", int(cfg["max_response_bytes"])
            while True:
                chunk = resp.read1(65536)
                if not chunk:
                    break
                sent += len(chunk)
                if sent > limit:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
                tail = (tail + chunk)[-65536:]
            prompt_t, completion_t = usage_tokens(tail)
            conn.close()
        except Exception as exc:  # after the reservation: spent, never retried
            if not status:
                self.server.ledger.tokens(0)
                return self._refuse(502, "UPSTREAM_" + type(exc).__name__, spent=True, request_id=rid)
        finally:
            self.close_connection = True
        self.server.ledger.tokens(completion_t)
        anomaly = completion_t > int(body["max_completion_tokens"])
        log(decision="FORWARDED", request_id=rid, status=status, model=body.get("model"), stream=bool(body.get("stream")),
            max_completion_tokens=body["max_completion_tokens"], reasoning_effort=body.get("reasoning_effort"),
            dropped_fields=dropped, upstream_ip=ip, bytes_out=len(payload), bytes_in=sent, prompt_tokens=prompt_t,
            completion_tokens=completion_t, token_cap_anomaly=anomaly, ratelimit=rl, budget_used=c["budget_used"],
            budget_requests=int(cfg["budget_requests"]), ms=int((time.time() - started) * 1000))


def main(argv: list[str]) -> int:
    cfg = load_config(argv[1])
    srv = Gate(cfg)
    ok, why, c = srv.ledger.check()
    log(decision="START", listen=f'{cfg["listen_host"]}:{cfg["listen_port"]}', upstream=cfg["upstream_host"],
        models=cfg["allowed_models"], key_loaded=bool(load_key()), state=why or "OK",
        budget_used=c.get("budget_used"), budget_requests=int(cfg["budget_requests"]),
        max_output_tokens=int(cfg["max_output_tokens"]))
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
