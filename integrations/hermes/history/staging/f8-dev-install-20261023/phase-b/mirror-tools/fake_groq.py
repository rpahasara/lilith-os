"""SYNTHETIC Groq stand-in for the F8r3 WSL mirror ONLY (never on DEV). HTTPS on <ip>:443 with a test-CA-signed
certificate for api.groq.com. Validates the injected bearer key, records every request (body + whether auth matched;
never the key) and answers like Groq chat completions for openai/gpt-oss-120b (non-stream JSON or SSE stream), with a
`reasoning` field. Modes (file <dir>/mode): ok | fail500 | slow.
Usage: fake_groq.py <ip> <cert> <key> <expected-api-key-file> <dir>
"""
import json
import ssl
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

IP, CERT, KEY, APIKEY_FILE, DIR = sys.argv[1:6]
DIR = Path(DIR)
COUNT = [0]


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n)
        expected = Path(APIKEY_FILE).read_text().strip()
        auth_ok = self.headers.get("Authorization") == f"Bearer {expected}"
        try:
            body = json.loads(raw)
        except ValueError:
            body = {"_unparsable": True}
        COUNT[0] += 1
        mode = (DIR / "mode").read_text().strip() if (DIR / "mode").exists() else "ok"
        rec = {"n": COUNT[0], "path": self.path, "auth_ok": auth_ok, "mode": mode, "ua": self.headers.get("User-Agent"),
               "fields": sorted(body), "model": body.get("model"), "stream": body.get("stream"),
               "max_completion_tokens": body.get("max_completion_tokens"), "max_tokens": body.get("max_tokens"),
               "reasoning_effort": body.get("reasoning_effort"), "tools": body.get("tools"),
               "n_messages": len(body.get("messages") or [])}
        with open(DIR / "requests.jsonl", "a") as fh:
            fh.write(json.dumps(rec) + "\n")
        if self.path != "/openai/v1/chat/completions" or not auth_ok:
            return self._json(401, {"error": {"message": "Invalid API Key", "type": "invalid_request_error"}})
        if mode == "fail500":
            return self._json(500, {"error": {"message": "synthetic upstream failure"}})
        text = f"F8R3-SYNTHETIC-PROVIDER-REPLY #{COUNT[0]}: hello from the synthetic Groq stand-in."
        usage = {"prompt_tokens": 40 + 3 * rec["n_messages"], "completion_tokens": 18, "total_tokens": 58 + 3 * rec["n_messages"]}
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            base = {"id": f"chatcmpl-f8r3-{COUNT[0]}", "object": "chat.completion.chunk", "created": int(time.time()),
                    "model": body.get("model")}
            chunks = [{"choices": [{"index": 0, "delta": {"role": "assistant", "reasoning": "synthetic reasoning."}}]},
                      {"choices": [{"index": 0, "delta": {"content": text}}]},
                      {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "x_groq": {"usage": usage}, "usage": usage}]
            for c in chunks:
                self.wfile.write(b"data: " + json.dumps({**base, **c}).encode() + b"\n\n")
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
            return
        self._json(200, {"id": f"chatcmpl-f8r3-{COUNT[0]}", "object": "chat.completion", "created": int(time.time()),
                         "model": body.get("model"),
                         "choices": [{"index": 0, "finish_reason": "stop",
                                      "message": {"role": "assistant", "content": text, "reasoning": "synthetic reasoning."}}],
                         "usage": usage})

    def do_GET(self):
        COUNT[0] += 1
        with open(DIR / "requests.jsonl", "a") as fh:
            fh.write(json.dumps({"n": COUNT[0], "path": self.path, "method": "GET"}) + "\n")
        self._json(404, {"error": "not found"})

    def _json(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(b)


srv = ThreadingHTTPServer((IP, 443), H)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(CERT, KEY)
srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
print(f"fake groq on {IP}:443", flush=True)
srv.serve_forever()
