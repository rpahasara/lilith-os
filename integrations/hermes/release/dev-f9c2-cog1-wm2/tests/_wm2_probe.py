"""Route synthetic TEST_ONLY messages through one assembled cog1 HERMES_HOME in a fresh process. Offline only.

    python _wm2_probe.py <hermes_home> <scenario.json>

As tests/_wm1_probe.py in dev-f9c2-cog1-wm1, plus a fake Core API: the adapter's opener is replaced by a stand-in that
answers from the scenario's fixtures (or fails, for "unavailable") and records every request. Sockets stay blocked
for the whole process. Also prints each route_turn result in full (including the grounded ephemeral prompt).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

home = Path(sys.argv[1])
scenario = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
attempts = []


def _blocked(*args, **kwargs):
    attempts.append(repr(args[:2]))
    raise OSError("TEST_ONLY network blocked")


socket.socket.connect = _blocked
socket.socket.connect_ex = _blocked
socket.create_connection = _blocked
sys.dont_write_bytecode = True


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes):
        super().__init__(body)
        self.code, self.headers = 200, {"content-type": "application/json"}

    def getcode(self):
        return self.code

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class FakeCoreApi:
    """Answers GETs from the fixtures by path (query ignored); records method, path+query and body of every call."""

    def __init__(self, fixtures, unavailable):
        self.fixtures, self.unavailable, self.calls = fixtures, unavailable, []

    def open(self, req, timeout=None):
        url = req.full_url.split("127.0.0.1:8765", 1)[1]
        self.calls.append({"method": req.get_method(), "url": url, "data": req.data is not None})
        if self.unavailable:
            raise OSError("TEST_ONLY Core API unavailable")
        return FakeResponse(json.dumps(self.fixtures.get(url.split("?", 1)[0])).encode("utf-8"))


def tree() -> dict:
    return {p.relative_to(home).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in home.rglob("*") if p.is_file() and "__pycache__" not in p.parts}


os.environ["HERMES_HOME"] = str(home)
os.environ["HOME"] = os.environ["USERPROFILE"] = str(home.parent)
(home / "lilith_router" / "router.yaml").write_text(scenario["router_yaml"], encoding="utf-8")
log = Path(scenario["log_path"])
before = tree()
sys.path.insert(0, str(home))

from lilith_router import config as rconfig, gateway_integration as gi, world_context as wc  # noqa: E402

core = FakeCoreApi(scenario.get("fixtures") or {}, scenario.get("unavailable", False))
wc._OPENER = core
cfg = rconfig.load()
results, calls_per_turn = [], []
for i, message in enumerate(scenario["messages"]):
    ctx = SimpleNamespace(source=SimpleNamespace(platform=SimpleNamespace(value=scenario.get("platform", "lilith_os")),
                                                 chat_id=f"probe-{i}"),
                          session_key=f"agent:lilith_os:probe-{i}", message=message)
    n = len(core.calls)
    results.append(gi.route_turn(runner=SimpleNamespace(), ctx=ctx, model="dev-model", runtime_kwargs={},
                                 turn_route={"model": "dev-model"}, combined_ephemeral="TEST_ONLY base",
                                 cached_agent=None))
    calls_per_turn.append(core.calls[n:])
records = []
for line in (log.read_text(encoding="utf-8").splitlines() if log.exists() else []):
    record = json.loads(line)
    record.pop("ts", None)
    record.pop("event_id", None)
    records.append(record)
after = tree()
changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
print(json.dumps({
    "results": results, "calls": calls_per_turn, "log": records, "socket_attempts": attempts,
    "config": {"enabled": cfg.enabled, "mode": cfg.mode, "cognitive_enabled": cfg.cognitive_enabled,
               "cognitive_mode": cfg.cognitive_mode, "cognitive_channels": cfg.cognitive_channels},
    "adapter": wc.status(),
    "modules": sorted(m for m in sys.modules if m.startswith("lilith_router")),
    "changed_files": changed,
}))
