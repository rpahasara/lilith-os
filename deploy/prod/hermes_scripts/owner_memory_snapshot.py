#!/usr/bin/env python3
"""Silent no-agent Hermes cron job (every 10 min): record pending memory proposals so rejections can be recognised."""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).with_name("owner_memory_review.py")))["snapshot"]()
