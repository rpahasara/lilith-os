#!/usr/bin/env python3
"""Slice 13 additive router-lane patch (Ethical Deliberation V1).
Anchored, backed up, idempotent-guarded. Run as the ``lilith`` owner.
Aborts (no write) if any anchor is not unique or a file already has Slice 13.

Reuses the existing Slice-9 run.py final_response short-circuit — NO run.py patch,
NO app.py/DB change. Advisory-only: no ALLOW/DENY, no writes, no tools, no
execution, no Policy impersonation.

New sources read from LILITH_NEW (default /tmp):
  $LILITH_NEW/ethics.py                       -> lilith_router/ethics.py (NEW)
  $LILITH_NEW/ethics_principles.py            -> lilith_router/ethics_principles.py (NEW)
  $LILITH_NEW/test_ethics.py                  -> lilith_router/tests/test_ethics.py (NEW)
  $LILITH_NEW/world_context_slice13_block.py  -> appended to world_context.py

Dry run:  LILITH_DRY=1 python3 patch_router13.py   (writes patched copies to RT/_patched)
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
ETHICS_SRC = NEW + "/ethics.py"
PRINC_SRC = NEW + "/ethics_principles.py"
TEST_SRC = NEW + "/test_ethics.py"
BLOCK_SRC = NEW + "/world_context_slice13_block.py"


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
    if "Slice 13" in body or "ethics_is_active" in body \
            or "detect_ethics_intent" in body or "ethics_enabled" in body:
        sys.exit("ABORT: %s already contains Slice 13 additions" % p)

# ---- config.py ----
cfg = read(CONFIG)
cfg = replace_once(
    cfg,
    '    planning_max_steps: int = 6\n'
    '\n'
    '    def channel_is_live(self, platform: str, chat_id: str) -> bool:\n',
    '    planning_max_steps: int = 6\n'
    '\n'
    '    # -- Slice 13: Ethical Deliberation lane (additive; reuses cognitive_channels).\n'
    '    # ethics_enabled + ethics_mode:shadow (build+validate+log an advisory result\n'
    '    # only, NO user-facing answer) -> live (a grounded advisory answer becomes the\n'
    '    # turn final_response). ADVISORY ONLY: no ALLOW/DENY, no execution, no approval/\n'
    '    # verification, no goal/plan/belief/draft mutation, no Policy impersonation.\n'
    '    # ethics_max_concerns/tensions hard-clamped downstream. Read per-turn.\n'
    '    ethics_enabled: bool = False\n'
    '    ethics_mode: str = "shadow"\n'
    '    ethics_max_concerns: int = 4\n'
    '    ethics_max_tensions: int = 3\n'
    '\n'
    '    def channel_is_live(self, platform: str, chat_id: str) -> bool:\n',
    CONFIG)
cfg = replace_once(
    cfg,
    '        return self.planning_is_active(platform, chat_id) and self.planning_mode == "live"\n'
    '\n'
    '    def resolved_log_path(self) -> Path:\n',
    '        return self.planning_is_active(platform, chat_id) and self.planning_mode == "live"\n'
    '\n'
    '    def ethics_is_active(self, platform: str, chat_id: str) -> bool:\n'
    '        """The ethical-deliberation lane is engaged for this channel (shadow or live)."""\n'
    '        return bool(self.ethics_enabled) and self._cognitive_channel_match(platform, str(chat_id))\n'
    '\n'
    '    def ethics_is_live(self, platform: str, chat_id: str) -> bool:\n'
    '        """A grounded advisory result answer may become the turn final_response\n'
    '        (else shadow: build+validate+log only). ADVISORY ONLY; never authorises."""\n'
    '        return self.ethics_is_active(platform, chat_id) and self.ethics_mode == "live"\n'
    '\n'
    '    def resolved_log_path(self) -> Path:\n',
    CONFIG)
cfg = replace_once(
    cfg,
    '            pass\n'
    '        return cfg\n',
    '            pass\n'
    '        cfg.ethics_enabled = bool(raw.get("ethics_enabled", cfg.ethics_enabled))\n'
    '        cfg.ethics_mode = str(raw.get("ethics_mode", cfg.ethics_mode)).strip().lower() or "shadow"\n'
    '        try:\n'
    '            cfg.ethics_max_concerns = int(raw.get("ethics_max_concerns", cfg.ethics_max_concerns))\n'
    '        except (TypeError, ValueError):\n'
    '            pass\n'
    '        try:\n'
    '            cfg.ethics_max_tensions = int(raw.get("ethics_max_tensions", cfg.ethics_max_tensions))\n'
    '        except (TypeError, ValueError):\n'
    '            pass\n'
    '        return cfg\n',
    CONFIG)
ast.parse(cfg)

# ---- gateway_integration.py ----
gw = read(GATEWAY)
LOG_ETHICS = (
    'def _log_ethics(cfg, platform, chat_id, eintent, mode, message, trace) -> None:\n'
    '    """Append one JSON line describing an ethics-lane decision (safe, non-CoT)."""\n'
    '    try:\n'
    '        path = cfg.resolved_log_path()\n'
    '        path.parent.mkdir(parents=True, exist_ok=True)\n'
    '        record = {\n'
    '            "ts": round(time.time(), 3),\n'
    '            "platform": platform,\n'
    '            "chat_id": str(chat_id or ""),\n'
    '            "lane": "ethics",\n'
    '            "ethics_mode": mode,\n'
    '            "intent": {"trigger": (eintent or {}).get("trigger"),\n'
    '                       "app_id": (eintent or {}).get("app_id")},\n'
    '            "trace": trace,\n'
    '            "preview": " ".join(((message or "")[:60]).splitlines()),\n'
    '        }\n'
    '        with path.open("a", encoding="utf-8") as fh:\n'
    '            fh.write(json.dumps(record, ensure_ascii=False) + "\\n")\n'
    '    except Exception:\n'
    '        logger.debug("lilith_router: ethics log write failed", exc_info=True)\n'
    '\n'
    '\n'
)
gw = replace_once(gw, "def _evict(runner, session_key) -> None:",
                  LOG_ETHICS + "def _evict(runner, session_key) -> None:", GATEWAY)

LANE = (
    '    # -- Slice 13 ethics lane (additive; EXPLICIT ethical questions only; ADVISORY-ONLY) --\n'
    '    # Runs after the planning lane and before the reasoning lane, but\n'
    '    # detect_ethics_intent YIELDS to explicit action (7.2 draft / 8 goal_create),\n'
    '    # goal-state queries, pending, AND planning, so those accepted paths stay\n'
    '    # authoritative. Builds a BOUNDED EthicalInput (with ephemeral TURN evidence)\n'
    '    # for ONE USER_INTENT subject, runs the deterministic advisory deliberator\n'
    '    # (the bounded no-tool LLM candidate path is built + unit-tested but NOT wired\n'
    '    # live), and -- in live mode -- returns the advisory answer as the turn\'s\n'
    '    # final_response (reuses the Slice-9 run.py short-circuit). Ethics NEVER returns\n'
    '    # ALLOW/DENY, never acts/approves/verifies, never mutates goals/plans/beliefs/\n'
    '    # drafts, never impersonates Policy. Fully fail-open.\n'
    '    if cfg.ethics_is_active(platform, str(chat_id)):\n'
    '        try:\n'
    '            eintent = _world_context.detect_ethics_intent(message)\n'
    '        except Exception:\n'
    '            eintent = None\n'
    '        if eintent and eintent.get("any"):\n'
    '            ethics_live = cfg.ethics_is_live(platform, str(chat_id))\n'
    '            _e_ws = None\n'
    '            if cfg.workspace_is_active(platform, str(chat_id)):\n'
    '                try:\n'
    '                    from . import workspace as _workspace\n'
    '                    _e_cands = _world_context.build_attention_candidates(\n'
    '                        message, session_key, eintent, channel=platform)\n'
    '                    _e_ws = _workspace.build_workspace_snapshot(\n'
    '                        _e_cands, capacity=cfg.workspace_capacity, channel=platform)\n'
    '                except Exception:\n'
    '                    _e_ws = None\n'
    '                    logger.debug("lilith_router: ethics attention build failed (fail-open)", exc_info=True)\n'
    '            _e_ws_live = _e_ws is not None and cfg.workspace_is_live(platform, str(chat_id))\n'
    '            try:\n'
    '                ein = _world_context.build_ethical_input(\n'
    '                    message, session_key, eintent,\n'
    '                    _e_ws if _e_ws_live else None, channel=platform)\n'
    '                from . import ethics as _ethics\n'
    '                e_result, e_trace = _ethics.run_ethics(\n'
    '                    ein, max_concerns=cfg.ethics_max_concerns,\n'
    '                    max_tensions=cfg.ethics_max_tensions)\n'
    '                _log_ethics(cfg, platform, chat_id, eintent,\n'
    '                            "live" if ethics_live else "shadow", message, e_trace)\n'
    '                if ethics_live and e_result and e_result.get("answer"):\n'
    '                    # Record WORK so the social guard leaves this grounded advisory\n'
    '                    # answer untouched; it flows through enforce_reply as normal.\n'
    '                    STATE.record(session_key, message, WORK)\n'
    '                    return {"final_response": e_result["answer"], "mode": "ethics"}\n'
    '                # shadow -> fall through to existing lanes\n'
    '            except Exception:\n'
    '                logger.debug("lilith_router: ethics lane failed (fail-open)", exc_info=True)\n'
    '    # -- end ethics lane --\n'
)
gw = replace_once(
    gw,
    "    # -- end planning lane --\n"
    "    if cfg.reasoning_is_active(platform, str(chat_id)):\n"
    "        try:\n"
    "            rintent = _world_context.detect_reasoning_intent(message)\n",
    "    # -- end planning lane --\n"
    + LANE +
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
    "# -- Slice 13: Ethical Deliberation lane (reuses cognitive_channels) --\n"
    "# ethics_enabled + ethics_mode: shadow (build+validate+log an advisory result\n"
    "# only) -> live (a grounded advisory answer becomes the turn final_response).\n"
    "# ADVISORY ONLY; no ALLOW/DENY, no writes/tools/execution, no Policy impersonation.\n"
    "ethics_enabled: true\n"
    "ethics_mode: shadow\n"
    "ethics_max_concerns: 4\n"
    "ethics_max_tensions: 3\n"
)

# ---- new files (syntax gate) ----
ethics_src = read(ETHICS_SRC)
ast.parse(ethics_src)
princ_src = read(PRINC_SRC)
ast.parse(princ_src)
test_src = read(TEST_SRC)
ast.parse(test_src)

# ---- commit: backups then writes ----
DRY = os.environ.get("LILITH_DRY") == "1"
if DRY:
    outd = RT + "/_patched13"
    os.makedirs(outd, exist_ok=True)
    write(outd + "/config.py", cfg)
    write(outd + "/gateway_integration.py", gw)
    write(outd + "/world_context.py", wc)
    write(outd + "/router.yaml", y)
    write(outd + "/ethics.py", ethics_src)
    write(outd + "/ethics_principles.py", princ_src)
    write(outd + "/test_ethics.py", test_src)
    print("DRY OK (Slice 13): wrote patched copies to " + outd)
else:
    for p in (CONFIG, GATEWAY, WORLDCTX, YAML):
        shutil.copy2(p, p + ".bak." + TS)
    write(CONFIG, cfg)
    write(GATEWAY, gw)
    write(WORLDCTX, wc)
    write(YAML, y)
    write(RT + "/ethics.py", ethics_src)
    write(RT + "/ethics_principles.py", princ_src)
    shutil.copy2(TEST_SRC, RT + "/tests/test_ethics.py")
    print("ROUTER PATCH OK (Slice 13); backups .bak." + TS)
