#!/usr/bin/env python3
"""Slice 12 additive router-lane patch (Planning / Replanning V1).
Anchored, backed up, idempotent-guarded. Run as the ``lilith`` owner.
Aborts (no write) if any anchor is not unique or a file already has Slice 12.

Reuses the existing Slice-9 run.py final_response short-circuit — NO run.py patch,
NO app.py/DB change. Proposal-only: no writes, no tools, no execution.

New sources read from LILITH_NEW (default /tmp):
  $LILITH_NEW/planning.py                     -> lilith_router/planning.py (NEW)
  $LILITH_NEW/planning_capabilities.py        -> lilith_router/planning_capabilities.py (NEW)
  $LILITH_NEW/test_planning.py                -> lilith_router/tests/test_planning.py (NEW)
  $LILITH_NEW/world_context_slice12_block.py  -> appended to world_context.py

Dry run:  LILITH_DRY=1 python3 patch_router12.py   (writes patched copies to RT/_patched)
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
YAML = RT + "/router.yaml"
PLAN_SRC = NEW + "/planning.py"
CAPS_SRC = NEW + "/planning_capabilities.py"
TEST_SRC = NEW + "/test_planning.py"
BLOCK_SRC = NEW + "/world_context_slice12_block.py"


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
for p in (CONFIG, GATEWAY, WORLDCTX):
    body = read(p)
    if "Slice 12" in body or "planning_is_active" in body \
            or "detect_planning_intent" in body or "planning_enabled" in body:
        sys.exit("ABORT: %s already contains Slice 12 additions" % p)

# ---- config.py ----
cfg = read(CONFIG)
cfg = replace_once(
    cfg,
    '    motivation_enabled: bool = False\n'
    '    motivation_mode: str = "shadow"\n'
    '\n'
    '    def channel_is_live(self, platform: str, chat_id: str) -> bool:\n',
    '    motivation_enabled: bool = False\n'
    '    motivation_mode: str = "shadow"\n'
    '\n'
    '    # -- Slice 12: Planning / Replanning lane (additive; reuses cognitive_channels).\n'
    '    # planning_enabled + planning_mode:shadow (build+validate+log a plan snapshot\n'
    '    # only, NO user-facing answer) -> live (a PLAN_PROPOSED / USER_DECISION_REQUIRED\n'
    '    # snapshot\'s natural answer becomes the turn\'s final_response). Proposal-only:\n'
    '    # no task/draft/goal/belief writes, no tools, no execution. planning_max_steps\n'
    '    # bounds the plan, hard-clamped [1,8] downstream. Read per-turn.\n'
    '    planning_enabled: bool = False\n'
    '    planning_mode: str = "shadow"\n'
    '    planning_max_steps: int = 6\n'
    '\n'
    '    def channel_is_live(self, platform: str, chat_id: str) -> bool:\n',
    CONFIG)
cfg = replace_once(
    cfg,
    '    def motivation_is_live(self, platform: str, chat_id: str) -> bool:\n'
    '        """Eligible drive candidates may merge into the Workspace pool (else shadow: log only)."""\n'
    '        return self.motivation_is_active(platform, chat_id) and self.motivation_mode == "live"\n'
    '\n'
    '    def resolved_log_path(self) -> Path:\n',
    '    def motivation_is_live(self, platform: str, chat_id: str) -> bool:\n'
    '        """Eligible drive candidates may merge into the Workspace pool (else shadow: log only)."""\n'
    '        return self.motivation_is_active(platform, chat_id) and self.motivation_mode == "live"\n'
    '\n'
    '    def planning_is_active(self, platform: str, chat_id: str) -> bool:\n'
    '        """The planning lane is engaged for this channel (shadow or live)."""\n'
    '        return bool(self.planning_enabled) and self._cognitive_channel_match(platform, str(chat_id))\n'
    '\n'
    '    def planning_is_live(self, platform: str, chat_id: str) -> bool:\n'
    '        """A proposed plan snapshot\'s answer may become the turn\'s final_response\n'
    '        (else shadow: build+validate+log only, no user-facing answer)."""\n'
    '        return self.planning_is_active(platform, chat_id) and self.planning_mode == "live"\n'
    '\n'
    '    def resolved_log_path(self) -> Path:\n',
    CONFIG)
cfg = replace_once(
    cfg,
    '        cfg.motivation_enabled = bool(raw.get("motivation_enabled", cfg.motivation_enabled))\n'
    '        cfg.motivation_mode = str(raw.get("motivation_mode", cfg.motivation_mode)).strip().lower() or "shadow"\n'
    '        return cfg\n',
    '        cfg.motivation_enabled = bool(raw.get("motivation_enabled", cfg.motivation_enabled))\n'
    '        cfg.motivation_mode = str(raw.get("motivation_mode", cfg.motivation_mode)).strip().lower() or "shadow"\n'
    '        cfg.planning_enabled = bool(raw.get("planning_enabled", cfg.planning_enabled))\n'
    '        cfg.planning_mode = str(raw.get("planning_mode", cfg.planning_mode)).strip().lower() or "shadow"\n'
    '        try:\n'
    '            cfg.planning_max_steps = int(raw.get("planning_max_steps", cfg.planning_max_steps))\n'
    '        except (TypeError, ValueError):\n'
    '            pass\n'
    '        return cfg\n',
    CONFIG)
ast.parse(cfg)

# ---- gateway_integration.py ----
gw = read(GATEWAY)
LOG_PLAN = (
    'def _log_planning(cfg, platform, chat_id, pintent, mode, message, trace) -> None:\n'
    '    """Append one JSON line describing a planning-lane decision (safe, non-CoT)."""\n'
    '    try:\n'
    '        path = cfg.resolved_log_path()\n'
    '        path.parent.mkdir(parents=True, exist_ok=True)\n'
    '        record = {\n'
    '            "ts": round(time.time(), 3),\n'
    '            "platform": platform,\n'
    '            "chat_id": str(chat_id or ""),\n'
    '            "lane": "planning",\n'
    '            "planning_mode": mode,\n'
    '            "intent": {"subtype": (pintent or {}).get("subtype"),\n'
    '                       "app_id": (pintent or {}).get("app_id")},\n'
    '            "trace": trace,\n'
    '            "preview": " ".join(((message or "")[:60]).splitlines()),\n'
    '        }\n'
    '        with path.open("a", encoding="utf-8") as fh:\n'
    '            fh.write(json.dumps(record, ensure_ascii=False) + "\\n")\n'
    '    except Exception:\n'
    '        logger.debug("lilith_router: planning log write failed", exc_info=True)\n'
    '\n'
    '\n'
)
gw = replace_once(gw, "def _evict(runner, session_key) -> None:",
                  LOG_PLAN + "def _evict(runner, session_key) -> None:", GATEWAY)

LANE = (
    '    # -- Slice 12 planning lane (additive; EXPLICIT plan framings only; PROPOSAL-ONLY) --\n'
    '    # Runs before the reasoning lane, but detect_planning_intent YIELDS to explicit\n'
    '    # action (7.2 draft / 8 goal_create), goal-state queries, and pending, so those\n'
    '    # accepted paths stay authoritative. Builds a BOUNDED PlanningInput for ONE\n'
    '    # subject, runs the deterministic planner (template fast-path; the bounded\n'
    '    # no-tool LLM candidate path is implemented + unit-tested but NOT wired into\n'
    '    # this live call in V1), validates, and — in live mode — returns a\n'
    '    # PLAN_PROPOSED / USER_DECISION_REQUIRED answer as the turn\'s final_response\n'
    '    # (reuses the Slice-9 run.py short-circuit). NO writes, NO execution, NO tools,\n'
    '    # NO approval/verification claim. Fully fail-open: any failure or non-proposal\n'
    '    # outcome -> fall through to the existing lanes unchanged.\n'
    '    if cfg.planning_is_active(platform, str(chat_id)):\n'
    '        try:\n'
    '            pintent = _world_context.detect_planning_intent(message)\n'
    '        except Exception:\n'
    '            pintent = None\n'
    '        if pintent and pintent.get("any"):\n'
    '            planning_live = cfg.planning_is_live(platform, str(chat_id))\n'
    '            _p_ws = None\n'
    '            _p_mot = None\n'
    '            if cfg.workspace_is_active(platform, str(chat_id)):\n'
    '                try:\n'
    '                    from . import workspace as _workspace\n'
    '                    _p_cands = _world_context.build_attention_candidates(\n'
    '                        message, session_key, pintent, channel=platform)\n'
    '                    if cfg.motivation_is_active(platform, str(chat_id)):\n'
    '                        try:\n'
    '                            _p_mot = _world_context.build_motivation_snapshot(\n'
    '                                message, session_key, pintent, _p_cands, channel=platform)\n'
    '                            if cfg.motivation_is_live(platform, str(chat_id)):\n'
    '                                _p_cands = list(_p_cands) + _world_context.motivation_candidates(_p_mot)\n'
    '                        except Exception:\n'
    '                            _p_mot = None\n'
    '                    _p_ws = _workspace.build_workspace_snapshot(\n'
    '                        _p_cands, capacity=cfg.workspace_capacity, channel=platform)\n'
    '                except Exception:\n'
    '                    _p_ws = None\n'
    '                    logger.debug("lilith_router: planning attention build failed (fail-open)", exc_info=True)\n'
    '            _p_ws_live = _p_ws is not None and cfg.workspace_is_live(platform, str(chat_id))\n'
    '            try:\n'
    '                pin = _world_context.build_planning_input(\n'
    '                    message, session_key, pintent,\n'
    '                    _p_ws if _p_ws_live else None,\n'
    '                    _p_mot if _p_ws_live else None, channel=platform)\n'
    '                from . import planning as _planning\n'
    '                p_result, p_trace = _planning.run_planning(pin, max_steps=cfg.planning_max_steps)\n'
    '                _log_planning(cfg, platform, chat_id, pintent,\n'
    '                              "live" if planning_live else "shadow", message, p_trace)\n'
    '                if (planning_live and p_result and p_result.get("answer")\n'
    '                        and p_result.get("outcome") in ("PLAN_PROPOSED", "USER_DECISION_REQUIRED")):\n'
    '                    # Record WORK so the social guard leaves this grounded planning\n'
    '                    # answer untouched; it flows through enforce_reply as normal.\n'
    '                    STATE.record(session_key, message, WORK)\n'
    '                    return {"final_response": p_result["answer"], "mode": "planning"}\n'
    '                # shadow, or no viable proposal -> fall through to existing lanes\n'
    '            except Exception:\n'
    '                logger.debug("lilith_router: planning lane failed (fail-open)", exc_info=True)\n'
    '    # -- end planning lane --\n'
)
gw = replace_once(
    gw,
    "    if cfg.reasoning_is_active(platform, str(chat_id)):\n"
    "        try:\n"
    "            rintent = _world_context.detect_reasoning_intent(message)\n",
    LANE +
    "    if cfg.reasoning_is_active(platform, str(chat_id)):\n"
    "        try:\n"
    "            rintent = _world_context.detect_reasoning_intent(message)\n",
    GATEWAY)
ast.parse(gw)

# ---- world_context.py append ----
wc = read(WORLDCTX) + read(BLOCK_SRC)
ast.parse(wc)

# ---- router.yaml append ----
y = read(YAML) + (
    "\n"
    "# -- Slice 12: Planning / Replanning lane (reuses cognitive_channels) --\n"
    "# planning_enabled + planning_mode: shadow (build+validate+log a plan snapshot\n"
    "# only) -> live (PLAN_PROPOSED / USER_DECISION_REQUIRED answer becomes the turn\n"
    "# final_response). Proposal-only; no writes/tools/execution. Read per-turn.\n"
    "planning_enabled: true\n"
    "planning_mode: shadow\n"
    "planning_max_steps: 6\n"
)

# ---- new files (syntax gate) ----
plan_src = read(PLAN_SRC)
ast.parse(plan_src)
caps_src = read(CAPS_SRC)
ast.parse(caps_src)
test_src = read(TEST_SRC)
ast.parse(test_src)

# ---- commit: backups then writes ----
DRY = os.environ.get("LILITH_DRY") == "1"
if DRY:
    outd = RT + "/_patched"
    os.makedirs(outd, exist_ok=True)
    write(outd + "/config.py", cfg)
    write(outd + "/gateway_integration.py", gw)
    write(outd + "/world_context.py", wc)
    write(outd + "/router.yaml", y)
    write(outd + "/planning.py", plan_src)
    write(outd + "/planning_capabilities.py", caps_src)
    write(outd + "/test_planning.py", test_src)
    print("DRY OK (Slice 12): wrote patched copies to " + outd)
else:
    for p in (CONFIG, GATEWAY, WORLDCTX, YAML):
        shutil.copy2(p, p + ".bak." + TS)
    write(CONFIG, cfg)
    write(GATEWAY, gw)
    write(WORLDCTX, wc)
    write(YAML, y)
    write(RT + "/planning.py", plan_src)
    write(RT + "/planning_capabilities.py", caps_src)
    shutil.copy2(TEST_SRC, RT + "/tests/test_planning.py")
    print("ROUTER PATCH OK (Slice 12); backups .bak." + TS)
