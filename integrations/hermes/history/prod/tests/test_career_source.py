"""Offline checks for the preserved PROD career pipeline. Nothing is imported or executed from it.

    python -m unittest discover -s integrations/hermes/history/prod/tests -p "test_*.py"
"""

from __future__ import annotations

import ast
import re
import sqlite3
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[3]
CAREER = HERE / "hermes-home" / "lilith-os" / "apps" / "career"
CONSUMER = REPO / "services" / "core-api" / "app.py"


def schema_sql() -> str:
    tree = ast.parse((CAREER / "init_db.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "SCHEMA" for t in node.targets):
            return node.value.value
    raise AssertionError("SCHEMA not found")


class CareerSourceTest(unittest.TestCase):
    def test_all_ten_scripts_are_preserved_and_parse(self) -> None:
        scripts = sorted(p.name for p in CAREER.glob("*.py"))
        self.assertEqual(len(scripts), 10)
        for script in scripts:
            with self.subTest(script=script):
                ast.parse((CAREER / script).read_text(encoding="utf-8"))

    def test_schema_provides_every_column_the_core_api_consumer_reads(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.executescript(schema_sql())
        columns = {row[1] for row in conn.execute("PRAGMA table_info(career_events)")}
        consumer = CONSUMER.read_text(encoding="utf-8")
        select = re.search(r'"SELECT ([a-z_, ]+) "\s*"FROM career_events WHERE id > \?', consumer)
        self.assertIsNotNone(select, "Core API career_events consumer not found")
        read = {c.strip() for c in select.group(1).split(",")}
        self.assertTrue(read <= columns, read - columns)
        app_columns = {row[1] for row in conn.execute("PRAGMA table_info(job_applications)")}
        self.assertTrue({"id", "role_title", "stage", "last_activity", "source_account", "company_id"} <= app_columns)

    def test_owner_addresses_are_placeholders(self) -> None:
        for script in CAREER.glob("*.py"):
            text = script.read_text(encoding="utf-8")
            with self.subTest(script=script.name):
                self.assertNotRegex(text, r"[A-Za-z0-9._%+-]+@gmail\.com")


if __name__ == "__main__":
    unittest.main()
