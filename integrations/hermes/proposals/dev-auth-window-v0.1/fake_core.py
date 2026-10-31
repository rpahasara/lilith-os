"""Stand-in for Core API and the provider gate in the script simulation, because this sandbox has no Linux FastAPI. test_auth_stages.py proves the same decisions on the real app. TEST_ONLY; stdlib."""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATE = os.environ["S"]
NEW = "_trusted_local_caller" in open("app.py", encoding="utf-8", errors="replace").read()
LOCAL = ("127.0.0.1", "::1")


def read_decision(path, cred, trust_local=True):
    if not NEW or path == "/health":
        return None
    mode = os.environ.get("LILITH_OS_READ_AUTH", "")
    if mode == "open-acknowledged":
        return None
    if mode != "enforced" or len(os.environ.get("LILITH_OS_READ_TOKEN", "")) < 32:
        return 503
    return None if cred == os.environ["LILITH_OS_READ_TOKEN"] else 401


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, code, body=b"{}"):
        print(f'INFO:     {self.client_address[0]}:1 - "{self.command} {self.path} HTTP/1.1" {code} X', flush=True)
        self.send_response(code)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def local(self):
        return os.environ.get("LILITH_OS_TRUST_LOOPBACK") == "1" and self.client_address[0] in LOCAL

    def do_GET(self):
        path = self.path.split("?")[0]
        code = None if self.local() and path != "/health" and os.environ.get("LILITH_OS_READ_AUTH", "") in ("enforced", "open-acknowledged") else read_decision(path, self.headers.get("x-lilith-os-read"))
        self.reply(code or 200)

    def do_POST(self):
        length = int(self.headers.get("content-length") or 0)
        self.rfile.read(length)
        path = self.path.split("?")[0]
        if not NEW:
            return self.reply(422)
        if path == "/os/conversation":
            return self.reply(read_decision(path, self.headers.get("x-lilith-os-read"), False) or 200)
        mode = os.environ.get("LILITH_OS_WRITE_AUTH", "")
        if mode == "open-acknowledged" or (mode == "enforced" and (self.local() or self.headers.get("x-lilith-os-write") == os.environ.get("LILITH_OS_WRITE_TOKEN"))):
            return self.reply(422)
        self.reply(401 if mode == "enforced" else 503)


class Gate(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        used, limit = open(os.path.join(STATE, "budget")).read().split()
        body = json.dumps({"key_loaded": True, "state": "OK", "budget_used": int(used), "budget_requests": int(limit), "available": int(used) < int(limit)}).encode()
        self.send_response(200)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


ThreadingHTTPServer.allow_reuse_address = True
threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", 19911), Gate).serve_forever, daemon=True).start()
ThreadingHTTPServer(("0.0.0.0", 8765), H).serve_forever()
