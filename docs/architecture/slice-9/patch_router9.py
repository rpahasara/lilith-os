#!/usr/bin/env python3
"""Slice 9 additive router-lane patch. Anchored, backed up, idempotent-guarded.
Run as the `lilith` owner."""
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
REASONING_SRC = "/tmp/reasoning.py"
TEST_SRC = "/tmp/test_reasoning.py"
GOALBLOCK = "/tmp/world_context_reasoning_block.py"


def read(p):
    with io.open(p, "r", encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(s)


def ins_after(text, anchor, insert, path):
    if text.count(anchor) != 1:
        sys.exit("ABORT: anchor count %d (want 1) in %s: %r" % (text.count(anchor), path, anchor[:50]))
    return text.replace(anchor, anchor + insert, 1)


for p in (CONFIG, GATEWAY, WORLDCTX):
    if "Slice 9" in read(p) or "reasoning_is_active" in read(p) or "detect_reasoning_intent" in read(p):
        sys.exit("ABORT: %s already has Slice 9 additions" % p)

# ---- config.py ----
cfg = read(CONFIG)
cfg = ins_after(cfg, "    goals_mode: str = \"shadow\"\n",
    "\n"
    "    # -- Slice 9: Reasoning lane (additive; reuses cognitive_channels). --\n"
    "    # reasoning_enabled + reasoning_mode:shadow (detect+log) -> live (bounded\n"
    "    # tool-less reasoning answer). Analytic framings only; yields to 7.2/8.\n"
    "    reasoning_enabled: bool = False\n"
    "    reasoning_mode: str = \"shadow\"\n", CONFIG)
cfg = ins_after(cfg,
    "        return self.goals_is_active(platform, chat_id) and self.goals_mode == \"live\"\n",
    "\n"
    "    def reasoning_is_active(self, platform: str, chat_id: str) -> bool:\n"
    "        \"\"\"The reasoning lane is engaged for this channel (shadow or live).\"\"\"\n"
    "        return bool(self.reasoning_enabled) and self._cognitive_channel_match(platform, str(chat_id))\n"
    "\n"
    "    def reasoning_is_live(self, platform: str, chat_id: str) -> bool:\n"
    "        \"\"\"The reasoning lane may run the bounded tool-less reasoning call.\"\"\"\n"
    "        return self.reasoning_is_active(platform, chat_id) and self.reasoning_mode == \"live\"\n",
    CONFIG)
cfg = ins_after(cfg,
    "        cfg.goals_mode = str(raw.get(\"goals_mode\", cfg.goals_mode)).strip().lower() or \"shadow\"\n",
    "        cfg.reasoning_enabled = bool(raw.get(\"reasoning_enabled\", cfg.reasoning_enabled))\n"
    "        cfg.reasoning_mode = str(raw.get(\"reasoning_mode\", cfg.reasoning_mode)).strip().lower() or \"shadow\"\n",
    CONFIG)
ast.parse(cfg)

# ---- gateway_integration.py ----
gw = read(GATEWAY)
LOG = (
    "def _log_reasoning(cfg, platform, chat_id, rintent, mode, message, trace) -> None:\n"
    "    \"\"\"Append one JSON line describing a reasoning-lane decision (safe, non-CoT).\"\"\"\n"
    "    try:\n"
    "        path = cfg.resolved_log_path()\n"
    "        path.parent.mkdir(parents=True, exist_ok=True)\n"
    "        record = {\n"
    "            \"ts\": round(time.time(), 3),\n"
    "            \"platform\": platform,\n"
    "            \"chat_id\": str(chat_id or \"\"),\n"
    "            \"lane\": \"reasoning\",\n"
    "            \"reasoning_mode\": mode,\n"
    "            \"intent\": {\"mode\": rintent.get(\"mode\"), \"subtype\": rintent.get(\"subtype\"),\n"
    "                       \"app_id\": rintent.get(\"app_id\")},\n"
    "            \"trace\": trace,\n"
    "            \"preview\": (message or \"\")[:60].replace(\"\\n\", \" \"),\n"
    "        }\n"
    "        with path.open(\"a\", encoding=\"utf-8\") as fh:\n"
    "            fh.write(json.dumps(record, ensure_ascii=False) + \"\\n\")\n"
    "    except Exception:\n"
    "        logger.debug(\"lilith_router: reasoning log write failed\", exc_info=True)\n"
    "\n"
    "\n"
)
if gw.count("def _evict(runner, session_key) -> None:") != 1:
    sys.exit("ABORT: _evict anchor not unique")
gw = gw.replace("def _evict(runner, session_key) -> None:",
                LOG + "def _evict(runner, session_key) -> None:", 1)

LANE = (
    "    # -- Slice 9 reasoning lane (additive; analytic framings only; TOOL-LESS) --\n"
    "    # Runs before the 7.2/8 lanes but detect_reasoning_intent YIELDS to their\n"
    "    # intents, so accepted paths stay authoritative. Produces a natural answer via\n"
    "    # a bounded TOOL-LESS reasoning call and returns it as the turn's\n"
    "    # final_response (run.py short-circuit), which still flows through\n"
    "    # enforce_reply. Fully fail-open: any failure -> fall through unchanged.\n"
    "    if cfg.reasoning_is_active(platform, str(chat_id)):\n"
    "        try:\n"
    "            rintent = _world_context.detect_reasoning_intent(message)\n"
    "        except Exception:\n"
    "            rintent = None\n"
    "        if rintent and rintent.get(\"any\"):\n"
    "            reasoning_live = cfg.reasoning_is_live(platform, str(chat_id))\n"
    "            try:\n"
    "                if reasoning_live:\n"
    "                    ri = _world_context.build_reasoning_input(\n"
    "                        message, session_key, rintent, channel=platform)\n"
    "                    from . import reasoning as _reasoning\n"
    "                    r_result, r_trace = _reasoning.run_reasoning(ri)\n"
    "                    _log_reasoning(cfg, platform, chat_id, rintent, \"live\", message, r_trace)\n"
    "                    if r_result and r_result.get(\"answer\"):\n"
    "                        # Record WORK so the social guard leaves this grounded\n"
    "                        # reasoning answer untouched; it still passes through\n"
    "                        # enforce_reply exactly as a normal final response.\n"
    "                        STATE.record(session_key, message, WORK)\n"
    "                        return {\"final_response\": r_result[\"answer\"], \"mode\": \"reasoning\"}\n"
    "                    # reasoning failed/invalid -> fall through to existing lanes\n"
    "                else:\n"
    "                    _log_reasoning(cfg, platform, chat_id, rintent, \"shadow\", message, None)\n"
    "            except Exception:\n"
    "                logger.debug(\"lilith_router: reasoning lane failed (fail-open)\", exc_info=True)\n"
    "    # -- end reasoning lane --\n"
)
gw = ins_after(gw, "    if cfg.cognitive_is_active(platform, str(chat_id)):\n",
               "", GATEWAY)  # anchor existence check only
# insert the reasoning lane immediately BEFORE the cognitive lane
gw = gw.replace("    if cfg.cognitive_is_active(platform, str(chat_id)):\n",
                LANE + "    if cfg.cognitive_is_active(platform, str(chat_id)):\n", 1)
ast.parse(gw)

# ---- world_context.py append ----
wc = read(WORLDCTX) + read(GOALBLOCK)
ast.parse(wc)

# ---- router.yaml append ----
y = read(YAML) + (
    "\n"
    "# -- Slice 9: Reasoning lane (independent rollout; reuses cognitive_channels) --\n"
    "# reasoning_enabled + reasoning_mode: shadow (detect+log) -> live (bounded\n"
    "# tool-less reasoning answer). Analytic framings only. Read per-turn.\n"
    "reasoning_enabled: true\n"
    "reasoning_mode: shadow\n"
)

# ---- reasoning.py new file (syntax gate) ----
reasoning_src = read(REASONING_SRC)
ast.parse(reasoning_src)

# ---- commit: backups then writes ----
for p in (CONFIG, GATEWAY, WORLDCTX, YAML):
    shutil.copy2(p, p + ".bak." + TS)
write(CONFIG, cfg)
write(GATEWAY, gw)
write(WORLDCTX, wc)
write(YAML, y)
write(RT + "/reasoning.py", reasoning_src)
shutil.copy2(TEST_SRC, RT + "/tests/test_reasoning.py")
print("ROUTER PATCH OK; backups .bak." + TS)
