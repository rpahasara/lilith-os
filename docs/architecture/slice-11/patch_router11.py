#!/usr/bin/env python3
"""Slice 11 additive router-lane patch (Motivation / Homeostasis V1).
Anchored, backed up, idempotent-guarded. Run as the `lilith` owner.
Aborts (no write) if any anchor is not unique or a file already has Slice 11.

Paths default to the VM router dir; override with env LILITH_RT (dry runs).
New sources read from LILITH_NEW (default /tmp):
  $LILITH_NEW/motivation.py                  -> lilith_router/motivation.py (NEW)
  $LILITH_NEW/test_motivation.py             -> lilith_router/tests/test_motivation.py (NEW)
  $LILITH_NEW/world_context_slice11_block.py -> appended to world_context.py
"""
import ast
import datetime
import io
import os
import shutil
import sys

RT = os.environ.get("LILITH_RT", "/home/lilith/.hermes/lilith_router")
NEW = os.environ.get("LILITH_NEW", "/tmp")
TS = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
CONFIG = RT + "/config.py"
GATEWAY = RT + "/gateway_integration.py"
WORLDCTX = RT + "/world_context.py"
WORKSPACE = RT + "/workspace.py"
YAML = RT + "/router.yaml"
MOT_SRC = NEW + "/motivation.py"
TEST_SRC = NEW + "/test_motivation.py"
BLOCK_SRC = NEW + "/world_context_slice11_block.py"


def read(p):
    with io.open(p, "r", encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)


def replace_once(text, old, new, path):
    n = text.count(old)
    if n != 1:
        sys.exit("ABORT: anchor count %d (want 1) in %s: %r" % (n, path, old[:60]))
    return text.replace(old, new, 1)


# ---- guard: refuse to double-apply ----
for p in (CONFIG, GATEWAY, WORLDCTX, WORKSPACE):
    body = read(p)
    if "Slice 11" in body or "motivation_is_active" in body \
            or "build_motivation_snapshot" in body or "MOTIVATION_PRESSURE" in body:
        sys.exit("ABORT: %s already contains Slice 11 additions" % p)

# ---- config.py ----
cfg = read(CONFIG)
cfg = replace_once(
    cfg,
    '    workspace_enabled: bool = False\n'
    '    workspace_mode: str = "shadow"\n'
    '    workspace_capacity: int = 4\n',
    '    workspace_enabled: bool = False\n'
    '    workspace_mode: str = "shadow"\n'
    '    workspace_capacity: int = 4\n'
    '\n'
    '    # -- Slice 11: Motivation / Homeostasis lane (additive; reuses\n'
    '    # cognitive_channels). motivation_enabled + motivation_mode:shadow\n'
    '    # (build+log snapshot only) -> live (eligible MOTIVATION_DRIVE candidates\n'
    '    # merge into the Workspace pool + bounded motivationSummary on the\n'
    '    # ReasoningInput). Ordinal only; no numeric tuning. Read per-turn.\n'
    '    motivation_enabled: bool = False\n'
    '    motivation_mode: str = "shadow"\n',
    CONFIG)
cfg = replace_once(
    cfg,
    '    def workspace_is_live(self, platform: str, chat_id: str) -> bool:\n'
    '        """The workspace snapshot may bound the ReasoningInput (else shadow: log only)."""\n'
    '        return self.workspace_is_active(platform, chat_id) and self.workspace_mode == "live"\n',
    '    def workspace_is_live(self, platform: str, chat_id: str) -> bool:\n'
    '        """The workspace snapshot may bound the ReasoningInput (else shadow: log only)."""\n'
    '        return self.workspace_is_active(platform, chat_id) and self.workspace_mode == "live"\n'
    '\n'
    '    def motivation_is_active(self, platform: str, chat_id: str) -> bool:\n'
    '        """The motivation/homeostasis lane is engaged for this channel (shadow or live)."""\n'
    '        return bool(self.motivation_enabled) and self._cognitive_channel_match(platform, str(chat_id))\n'
    '\n'
    '    def motivation_is_live(self, platform: str, chat_id: str) -> bool:\n'
    '        """Eligible drive candidates may merge into the Workspace pool (else shadow: log only)."""\n'
    '        return self.motivation_is_active(platform, chat_id) and self.motivation_mode == "live"\n',
    CONFIG)
cfg = replace_once(
    cfg,
    '        try:\n'
    '            cfg.workspace_capacity = int(raw.get("workspace_capacity", cfg.workspace_capacity))\n'
    '        except (TypeError, ValueError):\n'
    '            pass\n',
    '        try:\n'
    '            cfg.workspace_capacity = int(raw.get("workspace_capacity", cfg.workspace_capacity))\n'
    '        except (TypeError, ValueError):\n'
    '            pass\n'
    '        cfg.motivation_enabled = bool(raw.get("motivation_enabled", cfg.motivation_enabled))\n'
    '        cfg.motivation_mode = str(raw.get("motivation_mode", cfg.motivation_mode)).strip().lower() or "shadow"\n',
    CONFIG)
ast.parse(cfg)

# ---- gateway_integration.py ----
gw = read(GATEWAY)
LOG_MOT = (
    'def _log_motivation(cfg, platform, chat_id, snapshot, mode, message, trace) -> None:\n'
    '    """Append one JSON line describing a motivation-lane decision (safe, non-CoT)."""\n'
    '    try:\n'
    '        path = cfg.resolved_log_path()\n'
    '        path.parent.mkdir(parents=True, exist_ok=True)\n'
    '        record = {\n'
    '            "ts": round(time.time(), 3),\n'
    '            "platform": platform,\n'
    '            "chat_id": str(chat_id or ""),\n'
    '            "lane": "motivation",\n'
    '            "motivation_mode": mode,\n'
    '            "trace": trace,\n'
    '            "preview": " ".join(((message or "")[:60]).splitlines()),\n'
    '        }\n'
    '        with path.open("a", encoding="utf-8") as fh:\n'
    '            fh.write(json.dumps(record, ensure_ascii=False) + "\\n")\n'
    '    except Exception:\n'
    '        logger.debug("lilith_router: motivation log write failed", exc_info=True)\n'
    '\n'
    '\n'
)
gw = replace_once(gw, "def _evict(runner, session_key) -> None:",
                  LOG_MOT + "def _evict(runner, session_key) -> None:", GATEWAY)
gw = replace_once(
    gw,
    "            _ws_snapshot = None\n"
    "            if cfg.workspace_is_active(platform, str(chat_id)):\n",
    "            _ws_snapshot = None\n"
    "            _mot_snapshot = None\n"
    "            if cfg.workspace_is_active(platform, str(chat_id)):\n",
    GATEWAY)
gw = replace_once(
    gw,
    "                    _ws_cands = _world_context.build_attention_candidates(\n"
    "                        message, session_key, rintent, channel=platform)\n"
    "                    _ws_snapshot = _workspace.build_workspace_snapshot(\n",
    "                    _ws_cands = _world_context.build_attention_candidates(\n"
    "                        message, session_key, rintent, channel=platform)\n"
    "                    # -- Slice 11 Motivation / Homeostasis: bounded ordinal drives --\n"
    "                    # Build+log an ephemeral MotivationSnapshot scoped to this pool\n"
    "                    # + user-referenced target + Executive focus. In motivation-live\n"
    "                    # mode, eligible (dedup-safe) MOTIVATION_DRIVE candidates merge\n"
    "                    # into the pool BEFORE arbitration. Fully fail-open; NO writes.\n"
    "                    if cfg.motivation_is_active(platform, str(chat_id)):\n"
    "                        try:\n"
    "                            _mot_snapshot = _world_context.build_motivation_snapshot(\n"
    "                                message, session_key, rintent, _ws_cands, channel=platform)\n"
    "                            _log_motivation(\n"
    "                                cfg, platform, chat_id, _mot_snapshot,\n"
    "                                \"live\" if cfg.motivation_is_live(platform, str(chat_id)) else \"shadow\",\n"
    "                                message, _world_context.motivation_trace(_mot_snapshot))\n"
    "                            if cfg.motivation_is_live(platform, str(chat_id)):\n"
    "                                _ws_cands = list(_ws_cands) + _world_context.motivation_candidates(_mot_snapshot)\n"
    "                        except Exception:\n"
    "                            _mot_snapshot = None\n"
    "                            logger.debug(\"lilith_router: motivation lane failed (fail-open)\", exc_info=True)\n"
    "                    _ws_snapshot = _workspace.build_workspace_snapshot(\n",
    GATEWAY)
gw = replace_once(
    gw,
    "                    ri = _world_context.select_reasoning_input(\n"
    "                        message, session_key, rintent,\n"
    "                        _ws_snapshot if _ws_live else None, channel=platform)\n",
    "                    ri = _world_context.select_reasoning_input_m(\n"
    "                        message, session_key, rintent,\n"
    "                        _ws_snapshot if _ws_live else None,\n"
    "                        _mot_snapshot if _ws_live else None, channel=platform)\n",
    GATEWAY)
ast.parse(gw)

# ---- workspace.py (5 additive edits) ----
ws = read(WORKSPACE)
ws = replace_once(
    ws,
    '    "RECENT_UNRESOLVED",        # 10\n'
    '    "BACKGROUND_MAINT",         # 11 connector/health; synthetic/test-only in V1\n',
    '    "RECENT_UNRESOLVED",        # 10\n'
    '    "MOTIVATION_PRESSURE",      # 11 Slice 11: functional drive pressure (low tier)\n'
    '    "BACKGROUND_MAINT",         # 12 connector/health; synthetic/test-only in V1\n',
    WORKSPACE)
ws = replace_once(
    ws,
    "_LOWEST_RANK = len(SALIENCE_CLASSES)  # unknown/missing class => lowest priority\n",
    "_LOWEST_RANK = len(SALIENCE_CLASSES)  # unknown/missing class => lowest priority\n"
    '_MOT_INTENSITY_ORDER = {"MILD": 1, "SIGNIFICANT": 2, "CRITICAL": 3}\n',
    WORKSPACE)
ws = replace_once(
    ws,
    '    if c.get("taskFailure"):\n'
    '        return "TASK_FAILURE"\n',
    '    if c.get("taskFailure"):\n'
    '        return "TASK_FAILURE"\n'
    '    if c.get("motivationDrive"):\n'
    '        return "MOTIVATION_PRESSURE"\n',
    WORKSPACE)
ws = replace_once(
    ws,
    '        "recentlyChanged": bool(raw.get("recentlyChanged", False)),\n',
    '        "recentlyChanged": bool(raw.get("recentlyChanged", False)),\n'
    '        "motivationDrive": bool(raw.get("motivationDrive", False)),\n'
    '        "motivationIntensity": raw.get("motivationIntensity"),\n',
    WORKSPACE)
ws = replace_once(
    ws,
    '    rank = _CLASS_RANK.get(c.get("salienceClass"), _LOWEST_RANK)\n'
    '    rec = c.get("recency")\n'
    '    rec = rec if isinstance(rec, (int, float)) else 0.0\n'
    '    # ascending rank; then higher recency first (negate); then stable sourceRef.\n'
    '    return (rank, -rec, str(c.get("sourceRef") or ""))\n',
    '    rank = _CLASS_RANK.get(c.get("salienceClass"), _LOWEST_RANK)\n'
    '    intens = _MOT_INTENSITY_ORDER.get(c.get("motivationIntensity"), 0)\n'
    '    rec = c.get("recency")\n'
    '    rec = rec if isinstance(rec, (int, float)) else 0.0\n'
    '    # ascending rank; higher motivation intensity first; then recency; then ref.\n'
    '    return (rank, -intens, -rec, str(c.get("sourceRef") or ""))\n',
    WORKSPACE)
ast.parse(ws)

# ---- world_context.py append ----
wc = read(WORLDCTX) + read(BLOCK_SRC)
ast.parse(wc)

# ---- router.yaml append ----
y = read(YAML) + (
    "\n"
    "# -- Slice 11: Motivation / Homeostasis lane (reuses cognitive_channels) --\n"
    "# motivation_enabled + motivation_mode: shadow (build+log snapshot only) ->\n"
    "# live (eligible MOTIVATION_DRIVE candidates merge into the Workspace pool +\n"
    "# bounded motivationSummary on the ReasoningInput). Read per-turn (no restart).\n"
    "motivation_enabled: true\n"
    "motivation_mode: shadow\n"
)

# ---- new files (syntax gate) ----
mot_src = read(MOT_SRC)
ast.parse(mot_src)
test_src = read(TEST_SRC)
ast.parse(test_src)

# ---- commit: backups then writes ----
DRY = os.environ.get("LILITH_DRY") == "1"
if DRY:
    outd = RT + "/_patched"
    os.makedirs(outd, exist_ok=True)
    write(outd + "/config.py", cfg)
    write(outd + "/gateway_integration.py", gw)
    write(outd + "/workspace.py", ws)
    write(outd + "/world_context.py", wc)
    write(outd + "/router.yaml", y)
    write(outd + "/motivation.py", mot_src)
    write(outd + "/test_motivation.py", test_src)
    print("DRY OK (Slice 11): wrote patched copies to " + outd)
else:
    for p in (CONFIG, GATEWAY, WORLDCTX, WORKSPACE, YAML):
        shutil.copy2(p, p + ".bak." + TS)
    write(CONFIG, cfg)
    write(GATEWAY, gw)
    write(WORLDCTX, wc)
    write(WORKSPACE, ws)
    write(YAML, y)
    write(RT + "/motivation.py", mot_src)
    shutil.copy2(TEST_SRC, RT + "/tests/test_motivation.py")
    print("ROUTER PATCH OK (Slice 11); backups .bak." + TS)
