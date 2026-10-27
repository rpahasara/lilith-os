"""Mirror-only: make the SYNTHETIC Groq stand-in record the STRUCTURE of every chat request it receives: for each
message, its role, text length and sha256 prefix (never the text itself), so the rehearsal can prove which prior user
and assistant messages Hermes actually assembled into turn 2's request, and in what order. Idempotent."""
import sys
from pathlib import Path
p = Path(sys.argv[1]); src = p.read_text()
if '"msgs":' in src:
    print("already patched (msgs)"); raise SystemExit(0)
Path(str(p) + ".pre-msgs").write_text(src)
a = '               "n_messages": len(body.get("messages") or [])}'
assert a in src
src = src.replace(a, '               "n_messages": len(body.get("messages") or []),\n'
                     '               "msgs": [{"role": m.get("role"), "len": len(_t(m.get("content"))),\n'
                     '                         "sha": hashlib.sha256(_t(m.get("content")).encode()).hexdigest()[:16]}\n'
                     '                        for m in (body.get("messages") or []) if isinstance(m, dict)]}', 1)
helper = ('import hashlib\n\n\ndef _t(c):\n'
          '    if isinstance(c, list):\n'
          '        return " ".join(str(x.get("text", "")) if isinstance(x, dict) else str(x) for x in c)\n'
          '    return "" if c is None else str(c)\n\n\nclass H(BaseHTTPRequestHandler):')
src = src.replace("class H(BaseHTTPRequestHandler):", helper, 1)
p.write_text(src); print("patched (msgs)")
