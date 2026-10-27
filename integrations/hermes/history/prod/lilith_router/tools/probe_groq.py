"""Standalone Groq provider probe — validates key + endpoint + model.

Run:  python -m lilith_router.tools.probe_groq
Loads GROQ_API_KEY from env or ~/.hermes/groq.env, makes ONE tiny chat call,
and reports PASS/FAIL. The API key is NEVER printed. Exit code: 0 = pass.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

MODEL = os.environ.get("GROQ_PROBE_MODEL", "qwen/qwen3.8-27b")


def _load_key() -> str | None:
    key = os.environ.get("GROQ_API_KEY")
    if key:
        return key
    home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    env_path = Path(home) / "groq.env"
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "GROQ_API_KEY":
                return v.strip().strip('"').strip("'")
    except FileNotFoundError:
        return None
    except Exception:
        return None
    return None


def main() -> int:
    key = _load_key()
    if not key:
        print("[FAIL] GROQ_API_KEY not found in env or ~/.hermes/groq.env")
        return 2
    print(f"[info] key loaded (len={len(key)}, masked) ; model={MODEL}")

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "Reply with exactly the word: pong"},
            {"role": "user", "content": "ping"},
        ],
        "temperature": 0,
        "max_tokens": 8,
    }
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "lilith-router-probe/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        print(f"[FAIL] Groq HTTP {e.code}: {body}")
        return 1
    except Exception as e:
        print(f"[FAIL] Groq request error: {type(e).__name__}: {e}")
        return 1

    choices = data.get("choices") or []
    if not choices:
        print(f"[FAIL] Groq returned no choices: {json.dumps(data)[:200]}")
        return 1
    content = (choices[0].get("message") or {}).get("content", "")
    print(f"[PASS] Groq responded: {content.strip()[:60]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
