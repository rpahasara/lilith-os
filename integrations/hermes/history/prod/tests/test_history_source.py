"""Offline checks for the preserved PROD history trees. Nothing is imported or executed from them.

    python -m unittest discover -s integrations/hermes/history/prod/tests -p "test_*.py"
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
PRIVATE_ID = re.compile(r"(?<![0-9])[0-9]{17,20}(?![0-9])")


class HistorySourceTest(unittest.TestCase):
    def test_python_history_parses(self) -> None:
        for path in ("lilith_router", "hermes-home/lilith-os/api", "home-lilith"):
            for file in sorted((HERE / path).rglob("*")):
                if file.is_file() and (file.suffix == ".py" or ".py." in file.name):
                    with self.subTest(file=file.relative_to(HERE).as_posix()):
                        ast.parse(file.read_text(encoding="utf-8"))

    def test_router_configs_and_notes_carry_no_channel_id(self) -> None:
        files = list((HERE / "lilith_router").rglob("router.yaml*")) + [HERE / "lilith_router" / "CURRENT_STATE.md"]
        self.assertGreaterEqual(len(files), 20)
        for file in files:
            with self.subTest(file=file.name):
                self.assertIsNone(PRIVATE_ID.search(file.read_text(encoding="utf-8")))

    def test_hand_patched_api_is_preserved(self) -> None:
        api = HERE / "hermes-home" / "lilith-os" / "api" / "app.py.bak.gitdeploy.20260913T153019Z"
        self.assertEqual(api.stat().st_size, 122756)


if __name__ == "__main__":
    unittest.main()
