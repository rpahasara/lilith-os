#!/usr/bin/env python3
"""Slice 9 — minimal additive fail-open reasoning short-circuit in gateway/run.py.
Run as the `lilith` owner. Aborts (no write) if anchors are off or already applied."""
import ast
import datetime
import io
import shutil
import sys

RUN = "/home/lilith/.hermes/hermes-agent/gateway/run.py"
TS = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def read(p):
    with io.open(p, "r", encoding="utf-8") as f:
        return f.read()


src = read(RUN)
if "Slice 9: reasoning short-circuit" in src or "_reasoning_fr" in src:
    sys.exit("ABORT: run.py already contains the Slice 9 hook")

# Anchor 1: capture the reasoning final_response right after the existing router
# override block (unconditional; _lr_res is defined by then, may be None).
A1 = (
    "            if _lr_res.get(\"force_rebuild\") and agent is not None:\n"
    "                agent = None\n"
    "        # ── end LILITH router ──\n"
)
if src.count(A1) != 1:
    sys.exit("ABORT: anchor 1 (router override block) not found exactly once")
INS1 = (
    "            if _lr_res.get(\"force_rebuild\") and agent is not None:\n"
    "                agent = None\n"
    "        # Slice 9: a reasoning result carries a ready final_response; capture it\n"
    "        # (None on every normal turn) so the run below can short-circuit.\n"
    "        _reasoning_fr = _lr_res.get(\"final_response\") if isinstance(_lr_res, dict) else None\n"
    "        # ── end LILITH router ──\n"
)
src = src.replace(A1, INS1, 1)

# Anchor 2: short-circuit the tool-exposed agent run with the reasoning answer,
# still flowing through the existing enforce_reply path. Fail-open (None -> normal).
A2 = "            result = agent.run_conversation(_api_run_message, **_conversation_kwargs)\n"
if src.count(A2) != 1:
    sys.exit("ABORT: anchor 2 (run_conversation call) not found exactly once")
INS2 = (
    "            if _reasoning_fr is not None:\n"
    "                # ── Slice 9: reasoning short-circuit (bounded tool-less answer) ──\n"
    "                # Use the reasoning answer as the turn result instead of running\n"
    "                # the tool-exposed agent. It still passes through enforce_reply\n"
    "                # below exactly as a normal final_response. Supply messages so the\n"
    "                # turn persists like a normal turn (fail-safe to []).\n"
    "                try:\n"
    "                    _rmsgs = list(agent_history) + [\n"
    "                        {\"role\": \"user\", \"content\": _api_run_message},\n"
    "                        {\"role\": \"assistant\", \"content\": _reasoning_fr},\n"
    "                    ]\n"
    "                except Exception:\n"
    "                    _rmsgs = []\n"
    "                result = {\"final_response\": _reasoning_fr, \"completed\": True,\n"
    "                          \"messages\": _rmsgs, \"api_calls\": 0}\n"
    "            else:\n"
    "                result = agent.run_conversation(_api_run_message, **_conversation_kwargs)\n"
)
src = src.replace(A2, INS2, 1)

ast.parse(src)
shutil.copy2(RUN, RUN + ".bak." + TS)
with io.open(RUN, "w", encoding="utf-8") as f:
    f.write(src)
print("RUN.PY PATCH OK; backup .bak." + TS)
