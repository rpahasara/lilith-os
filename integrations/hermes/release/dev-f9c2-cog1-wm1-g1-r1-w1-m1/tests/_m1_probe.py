"""Route synthetic TEST_ONLY messages through one assembled cog1 HERMES_HOME in a fresh process. Offline only.

    python _g1_probe.py <hermes_home> <scenario.json>

Sockets are blocked for the whole process. Prints one JSON document: each route_turn result, the decision log with
its random and time fields removed, the adapter's read/write counters, the lilith_router modules that were imported,
every file under HERMES_HOME that was created or changed (apart from the decision log), and any socket attempt.
"""

from __future__ import annotations

import hashlib
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

cfg = rconfig.load()
results = []
for i, message in enumerate(scenario["messages"]):
    ctx = SimpleNamespace(source=SimpleNamespace(platform=SimpleNamespace(value=scenario.get("platform", "lilith_os")),
                                                 chat_id=f"probe-{i}"),
                          session_key=f"agent:lilith_os:probe-{i}", message=message)
    results.append(gi.route_turn(runner=SimpleNamespace(), ctx=ctx, model="dev-model", runtime_kwargs={},
                                 turn_route={"model": "dev-model"}, combined_ephemeral="TEST_ONLY base",
                                 cached_agent=None))
records = []
for line in (log.read_text(encoding="utf-8").splitlines() if log.exists() else []):
    record = json.loads(line)
    record.pop("ts", None)
    record.pop("event_id", None)
    records.append(record)
after = tree()
changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
print(json.dumps({
    "results": results, "log": records, "socket_attempts": attempts,
    "config": {"enabled": cfg.enabled, "mode": cfg.mode, "cognitive_enabled": cfg.cognitive_enabled,
               "cognitive_mode": cfg.cognitive_mode, "cognitive_channels": cfg.cognitive_channels,
               "goals_enabled": cfg.goals_enabled, "goals_mode": cfg.goals_mode,
               "reasoning_enabled": cfg.reasoning_enabled, "reasoning_mode": cfg.reasoning_mode,
               "workspace_enabled": cfg.workspace_enabled, "workspace_mode": cfg.workspace_mode,
               "motivation_enabled": cfg.motivation_enabled, "motivation_mode": cfg.motivation_mode},
    "adapter": wc.status(),
    "modules": sorted(m for m in sys.modules if m.startswith("lilith_router")),
    "changed_files": changed,
}))
