"""The stage 1 drop-in against the real Core API rule. TEST_ONLY; no network.

    python -B -m unittest discover -s integrations/hermes/proposals/cognition-roadmap-v0.1 -p "test_*.py"

Skips if #289 is not in this checkout: it tests the two together.
"""

import configparser
import importlib.util
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.dont_write_bytecode = True


class Stage1(unittest.TestCase):
    def test_the_drop_in_is_one_setting_and_no_secret(self):
        text = (HERE / "write-auth-stage1.conf").read_text(encoding="utf-8")
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str
        parser.read_string(text)
        self.assertEqual(parser.sections(), ["Service"])
        self.assertEqual(dict(parser["Service"]), {"Environment": "LILITH_OS_WRITE_AUTH=open-acknowledged"})
        self.assertIsNone(re.search(r"TOKEN|SECRET|KEY", text.split("[Service]")[1]))

    def test_the_setting_is_one_the_core_api_accepts(self):
        source = (REPO / "services/core-api/app.py").read_text(encoding="utf-8")
        if "_write_auth_state" not in source:
            self.skipTest("#289 not in this checkout")
        tmp = tempfile.mkdtemp(prefix="auth1.")
        os.environ.update(LILITH_DB_PATH=str(Path(tmp) / "a.db"), HERMES_HOME=tmp, LILITH_HOME=tmp, LILITH_OS_WRITE_AUTH="open-acknowledged")
        spec = importlib.util.spec_from_file_location("app_auth1", REPO / "services/core-api/app.py")
        app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(app)
        self.assertEqual(app._write_auth_state(), "open-acknowledged")


if __name__ == "__main__":
    unittest.main()
