#!/usr/bin/env python3
"""Slice 10 additive router-lane patch (Global Workspace / Attention V1).
Anchored, backed up, idempotent-guarded. Run as the `lilith` owner.
Aborts (no write) if any anchor is not unique or a file already has Slice 10.

Reads new sources from /tmp:
  /tmp/workspace.py                      -> lilith_router/workspace.py (NEW)
  /tmp/test_workspace.py                 -> lilith_router/tests/test_workspace.py (NEW)
  /tmp/world_context_slice10_block.py    -> appended to world_context.py
"""
import ast
import datetime
import io
import shutil
import sys

RT = "/home/lilith/.hermes/lilith_router"
TS = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
CONFIG = RT + "/config.py"
GATEWAY = RT + "/gateway_integration.py"
WORLDCTX = RT + "/world_context.py"
YAML = RT + "/router.yaml"
WORKSPACE_SRC = "/tmp/workspace.py"
TEST_SRC = "/tmp/test_workspace.py"
BLOCK_SRC = "/tmp/world_context_slice10_block.py"


def read(p):
    with io.open(p, "r", encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(s)


def ins_after(text, anchor, insert, path):
    n = text.count(anchor)
    if n != 1:
        sys.exit("ABORT: anchor count %d (want 1) in %s: %r" % (n, path, anchor[:60]))
    return text.replace(anchor, anchor + insert, 1)


def replace_once(text, old, new, path):
    n = text.count(old)
    if n != 1:
        sys.exit("ABORT: replace anchor count %d (want 1) in %s: %r" % (n, path, old[:60]))
    return text.replace(old, new, 1)


# ---- guard: refuse to double-apply ----
for p in (CONFIG, GATEWAY, WORLDCTX):
    body = read(p)
    if "Slice 10" in body or "workspace_is_active" in body or "build_attention_candidates" in body:
        sys.exit("ABORT: %s already contains Slice 10 additions" % p)

# ---- config.py ----
cfg = read(CONFIG)
cfg = ins_after(
    cfg,
    "    reasoning_enabled: bool = False\n    reasoning_mode: str = \"shadow\"\n",
    "\n"
    "    # -- Slice 10: Global Workspace / Attention lane (additive; reuses\n"
    "    # cognitive_channels). workspace_enabled + workspace_mode:shadow (build+log\n"
    "    # snapshot only) -> live (snapshot bounds the Slice 9 ReasoningInput).\n"
    "    # workspace_capacity = secondary capacity, hard-bounded [0,8] downstream.\n"
    "    workspace_enabled: bool = False\n"
    "    workspace_mode: str = \"shadow\"\n"
    "    workspace_capacity: int = 4\n",
    CONFIG,
)
cfg = ins_after(
    cfg,
    "        return self.reasoning_is_active(platform, chat_id) and self.reasoning_mode == \"live\"\n",
    "\n"
    "    def workspace_is_active(self, platform: str, chat_id: str) -> bool:\n"
    "        \"\"\"The workspace/attention lane is engaged for this channel (shadow or live).\"\"\"\n"
    "        return bool(self.workspace_enabled) and self._cognitive_channel_match(platform, str(chat_id))\n"
    "\n"
    "    def workspace_is_live(self, platform: str, chat_id: str) -> bool:\n"
    "        \"\"\"The workspace snapshot may bound the ReasoningInput (else shadow: log only).\"\"\"\n"
    "        return self.workspace_is_active(platform, chat_id) and self.workspace_mode == \"live\"\n",
    CONFIG,
)
cfg = ins_after(
    cfg,
    "        cfg.reasoning_mode = str(raw.get(\"reasoning_mode\", cfg.reasoning_mode)).strip().lower() or \"shadow\"\n",
    "        cfg.workspace_enabled = bool(raw.get(\"workspace_enabled\", cfg.workspace_enabled))\n"
    "        cfg.workspace_mode = str(raw.get(\"workspace_mode\", cfg.workspace_mode)).strip().lower() or \"shadow\"\n"
    "        try:\n"
    "            cfg.workspace_capacity = int(raw.get(\"workspace_capacity\", cfg.workspace_capacity))\n"
    "        except (TypeError, ValueError):\n"
    "            pass\n",
    CONFIG,
)
ast.parse(cfg)

# ---- gateway_integration.py ----
gw = read(GATEWAY)
LOG_WS = (
    "def _log_workspace(cfg, platform, chat_id, snapshot, mode, message, trace) -> None:\n"
    "    \"\"\"Append one JSON line describing a workspace-lane decision (safe, non-CoT).\"\"\"\n"
    "    try:\n"
    "        path = cfg.resolved_log_path()\n"
    "        path.parent.mkdir(parents=True, exist_ok=True)\n"
    "        record = {\n"
    "            \"ts\": round(time.time(), 3),\n"
    "            \"platform\": platform,\n"
    "            \"chat_id\": str(chat_id or \"\"),\n"
    "            \"lane\": \"workspace\",\n"
    "            \"workspace_mode\": mode,\n"
    "            \"trace\": trace,\n"
    "            \"preview\": (message or \"\")[:60].replace(\"\\n\", \" \"),\n"
    "        }\n"
    "        with path.open(\"a\", encoding=\"utf-8\") as fh:\n"
    "            fh.write(json.dumps(record, ensure_ascii=False) + \"\\n\")\n"
    "    except Exception:\n"
    "        logger.debug(\"lilith_router: workspace log write failed\", exc_info=True)\n"
    "\n"
    "\n"
)
gw = replace_once(gw, "def _evict(runner, session_key) -> None:",
                  LOG_WS + "def _evict(runner, session_key) -> None:", GATEWAY)

OLD_LANE = (
    "            reasoning_live = cfg.reasoning_is_live(platform, str(chat_id))\n"
    "            try:\n"
    "                if reasoning_live:\n"
    "                    ri = _world_context.build_reasoning_input(\n"
    "                        message, session_key, rintent, channel=platform)\n"
)
NEW_LANE = (
    "            reasoning_live = cfg.reasoning_is_live(platform, str(chat_id))\n"
    "            # -- Slice 10 Global Workspace: bounded attention selection --\n"
    "            # Build an ephemeral WorkspaceSnapshot from durable source refs and\n"
    "            # log it (shadow or live). In workspace-live mode a successful\n"
    "            # snapshot is the REAL selection boundary for the Slice 9\n"
    "            # ReasoningInput (bounded support expansion around the SELECTED refs\n"
    "            # only); shadow / failure / no-primary falls back to the exact\n"
    "            # existing builder. Fully fail-open; performs NO writes.\n"
    "            _ws_snapshot = None\n"
    "            if cfg.workspace_is_active(platform, str(chat_id)):\n"
    "                try:\n"
    "                    from . import workspace as _workspace\n"
    "                    _ws_cands = _world_context.build_attention_candidates(\n"
    "                        message, session_key, rintent, channel=platform)\n"
    "                    _ws_snapshot = _workspace.build_workspace_snapshot(\n"
    "                        _ws_cands, capacity=cfg.workspace_capacity, channel=platform)\n"
    "                    _log_workspace(\n"
    "                        cfg, platform, chat_id, _ws_snapshot,\n"
    "                        \"live\" if cfg.workspace_is_live(platform, str(chat_id)) else \"shadow\",\n"
    "                        message, _workspace.build_trace(_ws_snapshot))\n"
    "                except Exception:\n"
    "                    _ws_snapshot = None\n"
    "                    logger.debug(\"lilith_router: workspace lane failed (fail-open)\", exc_info=True)\n"
    "            _ws_live = _ws_snapshot is not None and cfg.workspace_is_live(platform, str(chat_id))\n"
    "            try:\n"
    "                if reasoning_live:\n"
    "                    ri = _world_context.select_reasoning_input(\n"
    "                        message, session_key, rintent,\n"
    "                        _ws_snapshot if _ws_live else None, channel=platform)\n"
)
gw = replace_once(gw, OLD_LANE, NEW_LANE, GATEWAY)
ast.parse(gw)

# ---- world_context.py append ----
wc = read(WORLDCTX) + read(BLOCK_SRC)
ast.parse(wc)

# ---- router.yaml append ----
y = read(YAML) + (
    "\n"
    "# -- Slice 10: Global Workspace / Attention lane (reuses cognitive_channels) --\n"
    "# workspace_enabled + workspace_mode: shadow (build+log snapshot only) -> live\n"
    "# (snapshot bounds the Slice 9 ReasoningInput). workspace_capacity = secondary\n"
    "# capacity (hard-bounded [0,8]). Read per-turn (no gateway restart to flip).\n"
    "workspace_enabled: true\n"
    "workspace_mode: shadow\n"
    "workspace_capacity: 4\n"
)

# ---- new files (syntax gate) ----
workspace_src = read(WORKSPACE_SRC)
ast.parse(workspace_src)
test_src = read(TEST_SRC)
ast.parse(test_src)

# ---- commit: backups then writes ----
for p in (CONFIG, GATEWAY, WORLDCTX, YAML):
    shutil.copy2(p, p + ".bak." + TS)
write(CONFIG, cfg)
write(GATEWAY, gw)
write(WORLDCTX, wc)
write(YAML, y)
write(RT + "/workspace.py", workspace_src)
shutil.copy2(TEST_SRC, RT + "/tests/test_workspace.py")
print("ROUTER PATCH OK (Slice 10); backups .bak." + TS)
