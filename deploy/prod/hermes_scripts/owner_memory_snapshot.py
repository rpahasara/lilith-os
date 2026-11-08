#!/usr/bin/env python3
"""Silent no-agent Hermes cron job (every 10 min): record pending memory proposals (so rejections can be recognised),
then mirror owner-approved memories into LILITH OS's World Model (owner_memory_sync)."""
import runpy
from pathlib import Path

here = Path(__file__).resolve().parent
runpy.run_path(str(here / "owner_memory_review.py"))["snapshot"]()
sync = runpy.run_path(str(here / "owner_memory_sync.py"))["sync"]
try:
    sync()
except Exception as exc:
    print("owner_memory_sync FAILED: %s" % exc)
