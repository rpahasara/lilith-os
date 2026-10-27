"""Route synthetic TEST_ONLY messages through one assembled HERMES_HOME tree in a fresh process. Offline only.

    python _route_probe.py <hermes_home> <scenario.json>

The scenario holds the router.yaml content and the messages. Sockets are blocked for the whole process. Prints
one JSON document: each route_turn result, the decision log with its random and time fields removed, the
world_context identity, and every socket connection that was attempted.
"""

from __future__ import annotations

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

os.environ["HERMES_HOME"] = str(home)
os.environ["HOME"] = os.environ["USERPROFILE"] = str(home.parent)
(home / "lilith_router" / "router.yaml").write_text(scenario["router_yaml"], encoding="utf-8")
sys.path.insert(0, str(home))

from lilith_router import config as rconfig, gateway_integration as gi, world_context as wc  # noqa: E402

cfg = rconfig.load()

results = []
for i, message in enumerate(scenario["messages"]):
    ctx = SimpleNamespace(source=SimpleNamespace(platform=SimpleNamespace(value="lilith_os"), chat_id=f"probe-{i}"),
                          session_key=f"agent:lilith_os:probe-{i}", message=message)
    results.append(gi.route_turn(runner=SimpleNamespace(), ctx=ctx, model="dev-model", runtime_kwargs={},
                                 turn_route={"model": "dev-model"}, combined_ephemeral="TEST_ONLY base",
                                 cached_agent=None))
log = Path(scenario["log_path"])
records = []
for line in (log.read_text(encoding="utf-8").splitlines() if log.exists() else []):
    record = json.loads(line)
    record.pop("ts", None)
    record.pop("event_id", None)
    records.append(record)
identity = {"stub": getattr(wc, "DEV_IMPORT_STUB", None), "unified": getattr(wc, "DEV_UNIFIED_COGNITION", False),
            "router_enabled": cfg.enabled, "router_mode": cfg.mode}
if hasattr(wc, "status"):
    identity["status"] = wc.status()
print(json.dumps({"results": results, "log": records, "identity": identity, "socket_attempts": attempts}))
