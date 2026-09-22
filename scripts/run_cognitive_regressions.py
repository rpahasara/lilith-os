#!/usr/bin/env python3
"""Run the deterministic Slice 8-15 architecture regression records."""

from __future__ import annotations

import re
import subprocess
import sys
import os
import shutil
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS = (
    "docs/architecture/slice-8/test_goal_context.py",
    "docs/architecture/slice-9/test_reasoning.py",
    "docs/architecture/slice-10/test_workspace.py",
    "docs/architecture/slice-11/test_motivation.py",
    "docs/architecture/slice-12/test_planning.py",
    "docs/architecture/slice-13/test_ethics.py",
    "docs/architecture/slice-14/test_social_presence.py",
    "docs/architecture/slice-15a/test_learning_consolidation.py",
    "docs/architecture/slice-15b1/test_canonical_ltm.py",
    "docs/architecture/slice-15b2a/test_slice15b2a.py",
)

WORLD_BLOCKS = (
    "docs/architecture/slice-8/world_context.goal-block.py",
    "docs/architecture/slice-9/world_context.reasoning-block.py",
    "docs/architecture/slice-10/world_context.slice10-block.py",
    "docs/architecture/slice-11/world_context.slice11-block.py",
    "docs/architecture/slice-12/world_context.slice12-block.py",
    "docs/architecture/slice-13/world_context_slice13_block.py",
)

WORLD_HEADER = """\
import re, json, uuid, sqlite3, os, hashlib, time, logging
from datetime import datetime, timezone, timedelta
DB = ':memory:'
TOPK = 8
logger = logging.getLogger('cognitive-regression-stage')
_APP_ID_RE = re.compile(r'\\b(?:application|app)\\s*#?\\s*(\\d+)\\b', re.I)
def db():
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    return connection
def _corr(prefix): return prefix + '.test'
def _iso_now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def _summarize_value(value): return str(value)[:256]
def fetch_world(entity_type=None, entity_id=None): return {'beliefs': []}
def _get_json(path, timeout=None): return None
def _post_draft(*args, **kwargs): return None
def _post_goal_json(*args, **kwargs): return None
def detect_intent(message):
    value = (message or '').lower()
    return {
        'draft': ('draft' in value and ('follow-up' in value or 'follow up' in value)),
        'pending': ('pending' in value),
        'any': False,
    }
"""


def _staged_environment(stage: Path) -> dict[str, str]:
    world = WORLD_HEADER + "\n".join(
        (ROOT / relative).read_text(encoding="utf-8") for relative in WORLD_BLOCKS
    )
    (stage / "world_context.py").write_text(world, encoding="utf-8")
    workspace = (ROOT / "docs/architecture/slice-10/workspace.py").read_text(
        encoding="utf-8"
    )
    replacements = (
        (
            '    "RECENT_UNRESOLVED",        # 10\n'
            '    "BACKGROUND_MAINT",         # 11 connector/health; synthetic/test-only in V1\n',
            '    "RECENT_UNRESOLVED",        # 10\n'
            '    "MOTIVATION_PRESSURE",      # 11 Slice 11: functional drive pressure (low tier)\n'
            '    "BACKGROUND_MAINT",         # 12 connector/health; synthetic/test-only in V1\n',
        ),
        (
            "_LOWEST_RANK = len(SALIENCE_CLASSES)  # unknown/missing class => lowest priority\n",
            "_LOWEST_RANK = len(SALIENCE_CLASSES)  # unknown/missing class => lowest priority\n"
            '_MOT_INTENSITY_ORDER = {"MILD": 1, "SIGNIFICANT": 2, "CRITICAL": 3}\n',
        ),
        (
            '    if c.get("taskFailure"):\n        return "TASK_FAILURE"\n',
            '    if c.get("taskFailure"):\n        return "TASK_FAILURE"\n'
            '    if c.get("motivationDrive"):\n        return "MOTIVATION_PRESSURE"\n',
        ),
        (
            '        "recentlyChanged": bool(raw.get("recentlyChanged", False)),\n',
            '        "recentlyChanged": bool(raw.get("recentlyChanged", False)),\n'
            '        "motivationDrive": bool(raw.get("motivationDrive", False)),\n'
            '        "motivationIntensity": raw.get("motivationIntensity"),\n',
        ),
        (
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
        ),
    )
    for old, new in replacements:
        if workspace.count(old) != 1:
            raise RuntimeError("Slice 11 workspace regression anchor changed")
        workspace = workspace.replace(old, new, 1)
    (stage / "workspace.py").write_text(workspace, encoding="utf-8")
    for relative in (
        "docs/architecture/slice-9/reasoning.py",
        "docs/architecture/slice-11/motivation.py",
        "docs/architecture/slice-12/planning.py",
        "docs/architecture/slice-12/planning_capabilities.py",
        "docs/architecture/slice-13/ethics.py",
        "docs/architecture/slice-13/ethics_principles.py",
    ):
        shutil.copy2(ROOT / relative, stage / Path(relative).name)
    package = stage / "lilith_router"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    shutil.copy2(
        ROOT / "docs/architecture/slice-14/social_cognition.py",
        package / "social_cognition.py",
    )
    shutil.copy2(
        ROOT / "docs/architecture/slice-14/presence_contract.py",
        package / "presence_contract.py",
    )
    (package / "config.py").write_text(
        "class RouterConfig:\n"
        "    def __init__(self):\n"
        "        self.memory_consolidation_enabled=False\n"
        "        self.memory_consolidation_mode='shadow'\n"
        "        self.canonical_ltm_enabled=False\n"
        "        self.canonical_ltm_config_valid=False\n"
        "    def memory_consolidation_is_active(self):\n"
        "        return self.memory_consolidation_enabled is True and self.memory_consolidation_mode == 'shadow'\n"
        "    def canonical_ltm_is_enabled(self):\n"
        "        return self.canonical_ltm_config_valid is True and self.canonical_ltm_enabled is True\n",
        encoding="utf-8",
    )
    (package / "gateway_integration.py").write_text("", encoding="utf-8")
    (stage / "run_slice14_portable.py").write_text(
        "import importlib.util, sys, unittest\n"
        "spec=importlib.util.spec_from_file_location('slice14_tests', sys.argv[1])\n"
        "module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)\n"
        "loader=unittest.TestLoader(); suite=unittest.TestSuite()\n"
        "for name in ('TestSocialTurnEvidence','TestParticipantsAndAudience','TestCuesAndPresence','TestClosedSchemas','TestFingerprintAndTrace'):\n"
        "    suite.addTests(loader.loadTestsFromTestCase(getattr(module,name)))\n"
        "for name in ('test_new_modules_import_no_world_memory_tools_connectors_or_db','test_no_personality_or_interaction_style_runtime_owner','test_outputs_have_no_prompt_or_final_response'):\n"
        "    suite.addTest(module.TestAuthorityAndSideEffects(name))\n"
        "result=unittest.TextTestRunner(verbosity=2).run(suite)\n"
        "raise SystemExit(0 if result.wasSuccessful() else 1)\n",
        encoding="utf-8",
    )
    roots = [
        stage,
        *(ROOT / "docs" / "architecture" / f"slice-{number}" for number in range(9, 14)),
        ROOT / "docs" / "architecture" / "slice-15b2a",
        ROOT / "docs" / "architecture" / "slice-15b1",
        ROOT / "docs" / "architecture" / "slice-15a",
        ROOT / "services" / "core-api",
    ]
    environment = os.environ.copy()
    previous = environment.get("PYTHONPATH")
    python_path = [str(value) for value in roots]
    if previous:
        python_path.append(previous)
    environment["PYTHONPATH"] = os.pathsep.join(python_path)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def main() -> int:
    total = 0
    with tempfile.TemporaryDirectory(prefix="lilith-cognitive-regressions-") as value:
        environment = _staged_environment(Path(value))
        staged_tests = Path(value) / "tests"
        staged_tests.mkdir()
        staged_b1 = Path(value) / "slice-15b1-runtime"
        staged_b1.mkdir()
        for module in (ROOT / "services/core-api/lilith_memory").glob("*.py"):
            shutil.copy2(module, staged_b1 / module.name)
        for relative in TESTS:
            path = ROOT / relative
            if not path.is_file():
                raise SystemExit(f"missing regression record: {relative}")
            run_path = path
            if any(f"slice-{number}" in relative for number in range(8, 14)):
                run_path = staged_tests / path.name
                shutil.copy2(path, run_path)
            elif "slice-15b1/" in relative.replace("\\", "/"):
                run_path = staged_b1 / path.name
                shutil.copy2(path, run_path)
            command = [sys.executable, str(run_path)]
            if "slice-14/" in relative.replace("\\", "/"):
                command = [
                    sys.executable,
                    str(Path(value) / "run_slice14_portable.py"),
                    str(path),
                ]
            result = subprocess.run(
                command,
                cwd=str(ROOT),
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            print(f"===== {relative} =====")
            print(result.stdout, end="")
            matches = re.findall(r"Ran (\d+) tests?", result.stdout)
            if result.returncode or not matches:
                return result.returncode or 1
            total += int(matches[-1])
    print(f"SLICE 8-15 REGRESSION TOTAL: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
