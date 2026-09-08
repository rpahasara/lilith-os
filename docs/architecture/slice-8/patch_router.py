#!/usr/bin/env python3
"""Slice 8 additive router-lane patch. Idempotent-guarded, anchored, backed up.
Run as the `lilith` owner. Aborts (no write) if any anchor is not found exactly
once, or if a file already contains the Slice 8 marker."""
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
GOALBLOCK = "/tmp/world_context_goal_block.py"


def read(p):
    with io.open(p, "r", encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(s)


def backup(p):
    shutil.copy2(p, p + ".bak." + TS)


def insert_after(text, anchor, insert, path):
    n = text.count(anchor)
    if n != 1:
        sys.exit("ABORT: anchor count %d (expected 1) in %s:\n%r" % (n, path, anchor[:60]))
    return text.replace(anchor, anchor + insert, 1)


# ---- guard: refuse to double-apply ----
for p in (CONFIG, GATEWAY, WORLDCTX):
    if "Slice 8" in read(p) or "goals_is_active" in read(p) or "detect_goal_intent" in read(p):
        sys.exit("ABORT: %s already contains Slice 8 additions" % p)

# ---- config.py ----
cfg = read(CONFIG)
cfg = insert_after(
    cfg,
    "    cognitive_draft_dedup: bool = True\n",
    "\n"
    "    # -- Slice 8: Goal / Executive lane (additive; reuses cognitive_channels).\n"
    "    # Independent rollout: goals_enabled + goals_mode:shadow (detect+log) ->\n"
    "    # goals_mode:live (inject durable Goal/Executive grounding; create only on\n"
    "    # an explicit 'track as a goal'). Channel scope reuses cognitive_channels.\n"
    "    goals_enabled: bool = False\n"
    "    goals_mode: str = \"shadow\"\n",
    CONFIG,
)
cfg = insert_after(
    cfg,
    "        return self.cognitive_is_active(platform, chat_id) and self.cognitive_mode == \"live\"\n",
    "\n"
    "    def goals_is_active(self, platform: str, chat_id: str) -> bool:\n"
    "        \"\"\"The goal/executive lane is engaged for this channel (shadow or live).\"\"\"\n"
    "        return bool(self.goals_enabled) and self._cognitive_channel_match(platform, str(chat_id))\n"
    "\n"
    "    def goals_is_live(self, platform: str, chat_id: str) -> bool:\n"
    "        \"\"\"The goal lane may inject Goal/Executive grounding / create goals.\"\"\"\n"
    "        return self.goals_is_active(platform, chat_id) and self.goals_mode == \"live\"\n",
    CONFIG,
)
cfg = insert_after(
    cfg,
    "        cfg.cognitive_draft_dedup = bool(raw.get(\"cognitive_draft_dedup\", cfg.cognitive_draft_dedup))\n",
    "        cfg.goals_enabled = bool(raw.get(\"goals_enabled\", cfg.goals_enabled))\n"
    "        cfg.goals_mode = str(raw.get(\"goals_mode\", cfg.goals_mode)).strip().lower() or \"shadow\"\n",
    CONFIG,
)
ast.parse(cfg)

# ---- gateway_integration.py ----
gw = read(GATEWAY)
LOG_GOAL = (
    "def _log_goal(cfg, platform, chat_id, gintent, goal_mode, message) -> None:\n"
    "    \"\"\"Append one JSON line describing a goal-lane decision. Never raises.\"\"\"\n"
    "    try:\n"
    "        path = cfg.resolved_log_path()\n"
    "        path.parent.mkdir(parents=True, exist_ok=True)\n"
    "        record = {\n"
    "            \"ts\": round(time.time(), 3),\n"
    "            \"platform\": platform,\n"
    "            \"chat_id\": str(chat_id or \"\"),\n"
    "            \"lane\": \"goal\",\n"
    "            \"goal_mode\": goal_mode,\n"
    "            \"intent\": {k: gintent.get(k) for k in (\"goal_query\", \"goal_create\", \"app_id\", \"subtype\")},\n"
    "            \"preview\": (message or \"\")[:60].replace(\"\\n\", \" \"),\n"
    "        }\n"
    "        with path.open(\"a\", encoding=\"utf-8\") as fh:\n"
    "            fh.write(json.dumps(record, ensure_ascii=False) + \"\\n\")\n"
    "    except Exception:\n"
    "        logger.debug(\"lilith_router: goal log write failed\", exc_info=True)\n"
    "\n"
    "\n"
)
gw = insert_after(gw, "def _evict(runner, session_key) -> None:", "", GATEWAY)  # anchor check only
# put _log_goal immediately before _evict
gw = gw.replace("def _evict(runner, session_key) -> None:",
                LOG_GOAL + "def _evict(runner, session_key) -> None:", 1)

GOAL_LANE = (
    "\n"
    "    # -- Slice 8 goal / executive lane (additive; goal-state + tracking turns) --\n"
    "    # Runs after the cognitive lane and before the social/technical decision, so a\n"
    "    # goal-state question ('what are you trying to do', 'what is blocked', 'which\n"
    "    # goal has priority') is grounded on the WORK brain from durable Goal state,\n"
    "    # and an explicit 'track as a goal' creates a durable goal (server-side dedup).\n"
    "    # Governs ONLY these turns; fully fail-open.\n"
    "    if cfg.goals_is_active(platform, str(chat_id)):\n"
    "        try:\n"
    "            gintent = _world_context.detect_goal_intent(message)\n"
    "        except Exception:\n"
    "            gintent = None\n"
    "        if gintent and gintent.get(\"any\"):\n"
    "            goals_live = cfg.goals_is_live(platform, str(chat_id))\n"
    "            _log_goal(cfg, platform, chat_id, gintent, \"live\" if goals_live else \"shadow\", message)\n"
    "            if goals_live:\n"
    "                STATE.record(session_key, message, WORK)\n"
    "                try:\n"
    "                    suffix, _gaction = _world_context.build_goal_grounding(\n"
    "                        message=message, session_key=session_key, gintent=gintent,\n"
    "                        do_write=True,\n"
    "                    )\n"
    "                except Exception:\n"
    "                    suffix = None\n"
    "                    logger.debug(\"lilith_router: build_goal_grounding failed\", exc_info=True)\n"
    "                if suffix:\n"
    "                    base = (combined_ephemeral or \"\").strip()\n"
    "                    grounded = (base + \"\\n\\n\" + suffix) if base else suffix\n"
    "                    if getattr(cached_agent, \"model\", None) == cfg.groq_model:\n"
    "                        _evict(runner, session_key)\n"
    "                    return {\n"
    "                        \"turn_route\": turn_route,\n"
    "                        \"combined_ephemeral\": grounded,\n"
    "                        \"force_rebuild\": True,\n"
    "                        \"mode\": \"goal\",\n"
    "                    }\n"
    "                # Grounding unavailable -> fall through to normal routing below.\n"
    "            # Shadow mode -> observed + logged only; fall through unchanged.\n"
    "    # -- end goal lane --\n"
)
gw = insert_after(gw, "    # \u2500\u2500 end cognitive lane \u2500\u2500\n", GOAL_LANE, GATEWAY)
ast.parse(gw)

# ---- world_context.py append ----
wc = read(WORLDCTX)
goalblock = read(GOALBLOCK)
wc2 = wc + goalblock
ast.parse(wc2)

# ---- router.yaml append ----
y = read(YAML)
YBLOCK = (
    "\n"
    "# -- Slice 8: Goal / Executive lane (independent rollout; reuses cognitive_channels) --\n"
    "# goals_enabled + goals_mode: shadow (detect+log) -> live (inject grounding +\n"
    "# create on explicit 'track as a goal'). Read per-turn (no gateway restart to flip).\n"
    "goals_enabled: true\n"
    "goals_mode: shadow\n"
)
y2 = y + YBLOCK

# ---- commit: backups then writes ----
for p in (CONFIG, GATEWAY, WORLDCTX, YAML):
    backup(p)
write(CONFIG, cfg)
write(GATEWAY, gw)
write(WORLDCTX, wc2)
write(YAML, y2)
print("PATCH OK; backups .bak." + TS)
