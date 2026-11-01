"""live_compare.py on real SQLite files in WAL mode, with a live writer open. TEST_ONLY; stdlib. python -B test_live_compare.py"""
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import live_compare as L

DBS = ("state.db", "lilith-os/data/lilith.db", "lilith-os/data/cognitive_memory.db", "lilith-os/data/privacy_governance.db")


class Live(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.tree = Path(self.t.name)
        (self.tree / "memories").mkdir()
        (self.tree / "lilith-os/data").mkdir(parents=True)
        (self.tree / "SOUL.md").write_text("TEST_ONLY")
        (self.tree / "memories/USER.md").write_text("TEST_ONLY")
        self.con = []
        for d in DBS:
            c = sqlite3.connect(self.tree / d, isolation_level=None)
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("CREATE TABLE t (a)")
            c.execute("INSERT INTO t VALUES (1)")
            self.con.append(c)
            self.addCleanup(c.close)

    def base(self):
        return json.loads(json.dumps(L.R.baseline(self.tree)))

    def test_sees_rows_still_in_the_wal(self):
        a = self.base()
        self.con[1].execute("INSERT INTO t VALUES (2)")
        b = self.base()
        self.assertEqual(b["databases"][DBS[1]]["tables"]["t"]["rows"], 2)
        self.assertNotEqual(a["databases"][DBS[1]]["tables"]["t"]["digest"], b["databases"][DBS[1]]["tables"]["t"]["digest"])

    def test_writes_nothing_to_the_database(self):
        before = (self.tree / DBS[0]).read_bytes()
        self.base()
        self.assertEqual((self.tree / DBS[0]).read_bytes(), before)

    def test_equal_is_clean(self):
        a = self.base()
        self.assertEqual(L.judge(a, self.base(), []), ([], []))

    def test_an_unmoved_table_that_changes_is_unexpected(self):
        a = self.base()
        self.con[1].execute("DELETE FROM t")
        self.assertEqual(L.judge(a, self.base(), [])[0], [f"table:{DBS[1]}:t"])

    def test_a_table_that_moved_on_its_own_may_grow(self):
        a = self.base()
        self.con[0].execute("INSERT INTO t VALUES (2)")
        b = self.base()
        self.con[0].execute("INSERT INTO t VALUES (3)")
        self.assertEqual(L.judge(a, self.base(), [(a, b)]), ([], [f"table:{DBS[0]}:t"]))

    def test_a_moving_table_that_loses_rows_is_unexpected(self):
        a = self.base()
        self.con[0].execute("INSERT INTO t VALUES (2)")
        b = self.base()
        self.con[0].execute("DELETE FROM t")
        self.assertEqual(L.judge(b, self.base(), [(a, b)])[0], [f"rows_fell:table:{DBS[0]}:t"])

    def test_identity_is_never_allowed_to_move(self):
        a = self.base()
        (self.tree / "SOUL.md").write_text("changed")
        b = self.base()
        self.assertEqual(L.judge(a, b, [(a, b)])[0], ["identity:SOUL.md"])

    def test_schema_change_is_never_allowed_to_move(self):
        a = self.base()
        self.con[2].execute("CREATE TABLE u (a)")
        b = self.base()
        self.assertTrue(all(x.startswith(("schema:", "table_added:")) or x.startswith("rows") for x in L.judge(a, b, [])[0]))
        self.assertIn(f"schema:{DBS[2]}", L.judge(a, b, [(a, b)])[0])

    def test_command_line_exit_codes(self):
        a = self.tree / "a.json"
        a.write_text(json.dumps(self.base()))
        ok = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "live_compare.py"), "judge", str(a), str(a)], capture_output=True, text=True)
        self.assertEqual((ok.returncode, ok.stdout.split()[0]), (0, "JUDGE_EQUAL"))
        self.con[1].execute("DELETE FROM t")
        b = self.tree / "b.json"
        b.write_text(json.dumps(self.base()))
        no = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "live_compare.py"), "judge", str(a), str(b)], capture_output=True, text=True)
        self.assertEqual((no.returncode, no.stdout.split()[0]), (1, "UNEXPECTED"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
