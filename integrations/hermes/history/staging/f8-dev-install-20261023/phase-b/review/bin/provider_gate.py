"""F8r3 DEV provider gate: the ONLY holder of the Groq API key and the ONLY F8 process with internet egress.

The Hermes gateway (loopback-only sandbox, no DNS) calls  http://127.0.0.1:9911/openai/v1/chat/completions  with a
non-secret placeholder key. This gate:
  * accepts exactly POST /openai/v1/chat/completions on 127.0.0.1 (CONNECT, other paths and methods are refused);
  * enforces the request policy: allowlisted model, no tools / functions / response formats, n=1, output-token cap,
    default reasoning_effort, body size;
  * enforces a persistent request budget (acceptance) + per-UTC-day request and output-token ceilings, BEFORE any
    upstream call, and never retries;
  * injects the key (systemd LoadCredential, readable only by this service's dynamic user) and forwards over TLS to
    the single upstream host, verifying its certificate; the resolved address must be a global unicast address;
  * streams the response back, logs one metadata line per request (never content, never the key).
Usage:  provider_gate.py /etc/hermes-provider-gate-dev/gate.json
Stdlib only.
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
PASS_HEADERS = {"content-type", "retry-after", "x-ratelimit-limit-requests", "x-ratelimit-remaining-requests",
                "x-ratelimit-limit-tokens", "x-ratelimit-remaining-tokens", "x-request-id"}
_LOCK = threading.Lock()


def log(**fields) -> None:
    fields["ts"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
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


class State:
    """Persistent counters in $STATE_DIRECTORY/state.json (0600)."""

    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.path = Path(os.environ.get("STATE_DIRECTORY", "/var/lib/hermes-provider-gate-dev")) / "state.json"

    def _load(self) -> dict:
        try:
            st = json.loads(self.path.read_text())
        except (OSError, ValueError):
            st = {}
        today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        st.setdefault("budget_used", 0)
        if st.get("day") != today:
            st.update(day=today, day_requests=0, day_output_tokens=0)
        return st

    def _save(self, st: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(st, sort_keys=True))
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)

    def reserve(self) -> tuple[bool, str, dict]:
        """Count the request BEFORE any upstream contact (conservative: attempts, not successes)."""
        with _LOCK:
            st = self._load()
            if st["budget_used"] >= int(self.cfg["budget_requests"]):
                return False, "BUDGET_EXHAUSTED", st
            if st["day_requests"] >= int(self.cfg["daily_requests"]):
                return False, "DAILY_REQUESTS_EXHAUSTED", st
            if st["day_output_tokens"] >= int(self.cfg["daily_output_tokens"]):
                return False, "DAILY_TOKENS_EXHAUSTED", st
            st["budget_used"] += 1
            st["day_requests"] += 1
            self._save(st)
            return True, "", st

    def add_tokens(self, n: int) -> None:
        with _LOCK:
            st = self._load()
            st["day_output_tokens"] += max(0, int(n))
            self._save(st)

    def snapshot(self) -> dict:
        with _LOCK:
            return self._load()


def global_address(host: str, port: int) -> str:
    for family, _, _, _, addr in socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM):
        ip = ipaddress.ip_address(addr[0])
        if ip.is_global and not ip.is_multicast and ip not in ipaddress.ip_network("100.64.0.0/10"):
            return addr[0]
    raise OSError("UPSTREAM_ADDRESS_NOT_GLOBAL")


def sanitize(body: dict, cfg: dict) -> tuple[dict, list]:
    if not isinstance(body, dict) or not isinstance(body.get("messages"), list) or not body["messages"]:
        raise ValueError("BODY_INVALID")
    if body.get("model") not in cfg["allowed_models"]:
        raise ValueError("MODEL_NOT_ALLOWED")
    for f in FORBIDDEN_FIELDS:
        if f in body and body[f] not in (None, [], {}, False):
            raise ValueError(f"FORBIDDEN_FIELD_{f}")
    if body.get("n", 1) != 1:
        raise ValueError("N_NOT_1")
    dropped = sorted(k for k in body if k not in PASS_FIELDS)
    out = {k: v for k, v in body.items() if k in PASS_FIELDS}
    cap = int(cfg["max_output_tokens"])
    asked = out.pop("max_tokens", None) or out.pop("max_completion_tokens", None) or cap
    out.pop("max_completion_tokens", None)
    try:
        asked = int(asked)
    except (TypeError, ValueError):
        asked = cap
    out["max_completion_tokens"] = max(1, min(asked, cap))
    out.setdefault("reasoning_effort", cfg["default_reasoning_effort"])
    out.pop("n", None)
    return out, dropped


def usage_tokens(raw: bytes) -> tuple[int, int]:
    """Best effort: (prompt, completion) from a JSON body or the last SSE usage block."""
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
        self.state = State(cfg)
        self.ctx = ssl.create_default_context()  # system trust store; hostname verification on
        super().__init__((cfg["listen_host"], int(cfg["listen_port"])), Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "f8-gate"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args) -> None:  # metadata logging is done by log()
        pass

    def _refuse(self, code: int, reason: str, **extra) -> None:
        body = json.dumps({"error": {"message": f"F8_GATE_{reason}", "type": "gate_refusal"}}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        log(decision="REFUSED", reason=reason, method=self.command, path=self.path, status=code, **extra)

    def do_CONNECT(self) -> None:
        self._refuse(405, "CONNECT_NOT_ALLOWED")

    def do_GET(self) -> None:
        if self.path == "/healthz":
            st = self.server.state.snapshot()
            cfg = self.server.cfg
            body = json.dumps({"ok": True, "key_loaded": bool(load_key()),
                               "budget_used": st["budget_used"], "budget_requests": int(cfg["budget_requests"]),
                               "day_requests": st["day_requests"], "day_output_tokens": st["day_output_tokens"]}).encode()
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
        if self.path != cfg["local_path"]:
            return self._refuse(404, "PATH_NOT_ALLOWED")
        if (self.headers.get("Authorization") or "") != "Bearer " + cfg["client_token"]:
            return self._refuse(401, "CLIENT_TOKEN_INVALID")
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length <= 0 or length > int(cfg["max_request_bytes"]):
            return self._refuse(413, "REQUEST_SIZE", bytes=length)
        try:
            body, dropped = sanitize(json.loads(self.rfile.read(length)), cfg)
        except (ValueError, json.JSONDecodeError) as exc:
            return self._refuse(400, str(exc) if str(exc).isupper() or str(exc).startswith("FORBIDDEN") else "BODY_INVALID")
        key = load_key()
        if not key:
            return self._refuse(503, "KEY_NOT_PROVISIONED")
        ok, why, st = self.server.state.reserve()
        if not ok:
            return self._refuse(429, why, budget_used=st["budget_used"])
        payload = json.dumps(body).encode()
        status, sent, prompt_t, completion_t, ip = 0, 0, 0, 0, ""
        try:
            ip = global_address(cfg["upstream_host"], int(cfg["upstream_port"]))
            conn = http.client.HTTPSConnection(cfg["upstream_host"], int(cfg["upstream_port"]),
                                               timeout=int(cfg["timeout_seconds"]), context=self.server.ctx)
            raw = socket.create_connection((ip, int(cfg["upstream_port"])), timeout=int(cfg["timeout_seconds"]))
            conn.sock = self.server.ctx.wrap_socket(raw, server_hostname=cfg["upstream_host"])
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
            self.send_header("Connection", "close")
            self.end_headers()
            tail, limit = b"", int(cfg["max_response_bytes"])
            while True:
                chunk = resp.read1(65536) if hasattr(resp, "read1") else resp.read(65536)
                if not chunk:
                    break
                sent += len(chunk)
                if sent > limit:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
                tail = (tail + chunk)[-65536:]
            prompt_t, completion_t = usage_tokens(tail)
            self.server.state.add_tokens(completion_t)
            conn.close()
        except Exception as exc:  # no retry, ever
            if not status:
                return self._refuse(502, "UPSTREAM_" + type(exc).__name__, upstream_ip=ip)
            status = status or 502
        finally:
            self.close_connection = True
        log(decision="FORWARDED", status=status, model=body.get("model"), stream=bool(body.get("stream")),
            max_completion_tokens=body["max_completion_tokens"], reasoning_effort=body.get("reasoning_effort"),
            dropped_fields=dropped, upstream_ip=ip, bytes_out=len(payload), bytes_in=sent,
            prompt_tokens=prompt_t, completion_tokens=completion_t, budget_used=st["budget_used"],
            budget_requests=int(cfg["budget_requests"]), ms=int((time.time() - started) * 1000))


def main(argv: list[str]) -> int:
    cfg = load_config(argv[1])
    srv = Gate(cfg)
    st = srv.state.snapshot()
    log(decision="START", listen=f'{cfg["listen_host"]}:{cfg["listen_port"]}', upstream=cfg["upstream_host"],
        models=cfg["allowed_models"], key_loaded=bool(load_key()), budget_used=st["budget_used"],
        budget_requests=int(cfg["budget_requests"]), max_output_tokens=int(cfg["max_output_tokens"]))
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
