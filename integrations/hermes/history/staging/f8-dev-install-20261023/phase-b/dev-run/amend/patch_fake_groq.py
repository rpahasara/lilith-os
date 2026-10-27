"""Mirror-only: make the SYNTHETIC Groq stand-in send Groq-style x-ratelimit-* headers on 200 replies (real Groq does,
as DEV request #1 showed; the gate logs them and G-7d requires them). Keeps fake_groq.py.orig. Idempotent."""
import sys
from pathlib import Path
p = Path(sys.argv[1]); src = p.read_text()
if "_rl_headers" in src:
    print("already patched"); raise SystemExit(0)
Path(str(p) + ".orig").write_text(src)
helper = '''
    def _rl_headers(self):
        n = COUNT[0]
        for k, v in (("x-ratelimit-limit-requests", "10"), ("x-ratelimit-remaining-requests", str(max(0, 10 - n))),
                     ("x-ratelimit-limit-tokens", "8000"), ("x-ratelimit-remaining-tokens", "7900"),
                     ("x-ratelimit-reset-requests", "2h24m0s"), ("x-ratelimit-reset-tokens", "1s")):
            self.send_header(k, v)

    def do_GET(self):'''
src = src.replace("\n    def do_GET(self):", helper, 1)
a = '            self.send_header("Content-Type", "text/event-stream")\n            self.send_header("Connection", "close")'
assert a in src; src = src.replace(a, a + "\n            self._rl_headers()", 1)
b = '        self.send_header("Content-Length", str(len(b)))\n        self.send_header("Connection", "close")'
assert b in src; src = src.replace(b, b + "\n        if code == 200:\n            self._rl_headers()", 1)
p.write_text(src); print("patched")
