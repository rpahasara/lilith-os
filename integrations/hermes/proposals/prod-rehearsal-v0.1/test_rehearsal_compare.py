"""Dry run of the rehearsal's comparison on a synthetic PROD-shaped tree, with the real Core API on main. TEST_ONLY; throwaway files; no network.

    python -B integrations/hermes/proposals/prod-rehearsal-v0.1/test_rehearsal_compare.py
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "services" / "core-api"))
sys.path.insert(0, str(REPO / "services" / "core-api" / "tests"))

import rehearsal_compare as R  # noqa: E402
import app  # noqa: E402

try:
    from fastapi.testclient import TestClient
    import test_populated_reads as P
except Exception:
    TestClient = None

CANARY = "TEST_ONLY_REHEARSAL_CANARY"


class Tree(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="rehearsal-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.tree = self.root / "copy"
        (self.tree / "memories").mkdir(parents=True)
        (self.tree / "lilith-os/data").mkdir(parents=True)
        (self.tree / "SOUL.md").write_text("TEST_ONLY persona", encoding="utf-8")
        (self.tree / "memories/USER.md").write_text("TEST_ONLY profile", encoding="utf-8")
        for name in R.DATABASES:
            c = sqlite3.connect(self.tree / name)
            c.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, body TEXT)")
            c.execute("INSERT INTO t (body) VALUES (?)", (CANARY,))
            c.commit(); c.close()

    def base(self):
        return R.baseline(self.tree)

    def test_an_untouched_copy_is_equal(self):
        self.assertEqual(R.compare(self.base(), self.base()), [])

    def test_the_baseline_holds_no_content(self):
        self.assertNotIn(CANARY, json.dumps(self.base()))
        self.assertNotIn("persona", json.dumps(self.base()))

    def test_reading_does_not_change_the_copy(self):
        before = {p: p.read_bytes() for p in self.tree.rglob("*") if p.is_file()}
        self.base()
        self.assertEqual({p: p.read_bytes() for p in self.tree.rglob("*") if p.is_file()}, before)

    def test_a_changed_persona_is_caught(self):
        a = self.base()
        (self.tree / "SOUL.md").write_text("changed", encoding="utf-8")
        self.assertEqual(R.compare(a, self.base()), ["identity:SOUL.md"])

    def test_one_changed_row_is_caught(self):
        a = self.base()
        c = sqlite3.connect(self.tree / "lilith-os/data/lilith.db")
        c.execute("UPDATE t SET body='x'")
        c.commit(); c.close()
        self.assertEqual(R.compare(a, self.base()), ["table:lilith-os/data/lilith.db:t"])

    def test_an_added_table_is_caught(self):
        a = self.base()
        c = sqlite3.connect(self.tree / "state.db")
        c.execute("CREATE TABLE extra (id INTEGER)")
        c.commit(); c.close()
        self.assertEqual(R.compare(a, self.base()), ["schema:state.db", "table_added:state.db:extra"])

    def test_a_replaced_empty_database_is_caught(self):
        a = self.base()
        (self.tree / "lilith-os/data/lilith.db").unlink()
        c = sqlite3.connect(self.tree / "lilith-os/data/lilith.db")
        c.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, body TEXT)")
        c.commit(); c.close()
        self.assertIn("table:lilith-os/data/lilith.db:t", R.compare(a, self.base()))

    def test_a_missing_file_is_caught(self):
        a = self.base()
        (self.tree / "memories/USER.md").unlink()
        self.assertIn("missing:memories/USER.md", R.compare(a, self.base()))

    def test_credentials_are_found_by_name(self):
        for name in (".env", "groq.env", "auth.json", "lilith-os/data/actor_authority.key", "google_token.json", "bundle.tar.gz.enc"):
            (self.tree / name).write_text("x", encoding="utf-8")
        self.assertEqual(len(R.credentials(self.tree)), 6)

    def test_a_clean_tree_has_no_credential_names(self):
        self.assertEqual(R.credentials(self.tree), [])


@unittest.skipIf(TestClient is None, "httpx not installed")
class CoreApiDryRun(unittest.TestCase):
    """R6 and R7 in miniature: the target code over a store of PROD's shape, every read, then a row-level comparison."""

    def test_the_target_core_api_changes_no_row_or_schema_on_a_prod_shaped_store(self):
        root = Path(tempfile.mkdtemp(prefix="rehearsal-api-"))
        self.addCleanup(shutil.rmtree, root, True)
        tree = root / "copy"
        (tree / "lilith-os/data").mkdir(parents=True)
        db = tree / "lilith-os/data/lilith.db"
        env = {"LILITH_OS_READ_AUTH": "open-acknowledged", "LILITH_OS_WRITE_AUTH": "open-acknowledged"}
        with mock.patch.dict(os.environ, env):
            app.DB = db
            app._goal_schema_ready = False
            app._world_schema_ready = False
            P.populate(db)
            sqlite3.connect(db).close()
            before = R.database(db)
            os.environ["LILITH_OS_FOCUS_READ_ONLY"] = "1"
            client = TestClient(app.app, raise_server_exceptions=False)
            for _, path in P.routes("GET"):
                client.get(P.fill(path))
            os.environ.pop("LILITH_OS_FOCUS_READ_ONLY", None)
        after = R.database(db)
        self.assertEqual(R.compare({"identity": {}, "missing": [], "databases": {"x": before}}, {"identity": {}, "missing": [], "databases": {"x": after}}), [])
        self.assertEqual((before["tables"]["goal"]["rows"], before["tables"]["tasks"]["rows"], before["tables"]["drafts"]["rows"]), (3, 7, 10))


if __name__ == "__main__":
    unittest.main()
