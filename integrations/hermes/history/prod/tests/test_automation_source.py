"""Offline checks for the preserved PROD automations and units. Nothing is imported, executed or scheduled.

    python -m unittest discover -s integrations/hermes/history/prod/tests -p "test_*.py"
"""

from __future__ import annotations

import ast
import configparser
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
AUTOMATION = HERE / "hermes-home" / "automation" / "productivity"
UNITS = HERE / "systemd"


class AutomationSourceTest(unittest.TestCase):
    def test_scripts_parse_and_config_is_valid_json(self) -> None:
        scripts = [p for p in AUTOMATION.iterdir() if p.is_file() and (p.suffix == ".py" or ".py." in p.name)]
        self.assertEqual(len(scripts), 13)
        for script in scripts:
            with self.subTest(script=script.name):
                ast.parse(script.read_text(encoding="utf-8"))
        json.loads((AUTOMATION / "config.json").read_text(encoding="utf-8"))

    def test_no_runtime_data_was_preserved(self) -> None:
        for name in ("logs", "state", "followups"):
            self.assertFalse((AUTOMATION / name).exists(), name)

    def test_units_parse_and_point_at_preserved_scripts(self) -> None:
        units = sorted(UNITS.glob("*.*"))
        self.assertEqual(len(units), 12)
        for unit in units:
            parser = configparser.ConfigParser(strict=False, interpolation=None)
            parser.optionxform = str
            parser.read_string(unit.read_text(encoding="utf-8"))
            with self.subTest(unit=unit.name):
                if unit.suffix == ".timer":
                    self.assertIn("Timer", parser)
                else:
                    self.assertIn("ExecStart", parser["Service"])


if __name__ == "__main__":
    unittest.main()
