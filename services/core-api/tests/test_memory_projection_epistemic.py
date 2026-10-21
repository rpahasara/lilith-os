# -*- coding: utf-8 -*-
"""EPI-01 — the read-only /memory/* projection never asserts "fact" without evidence.

Synthetic only: an in-memory SQLite career fixture and a temporary Hermes memories
directory. Never lilith.db, never ~/.hermes. Covers both projection paths:
email-derived career activity (a candidate observation) and curated Hermes markdown
(no per-entry epistemic basis). Both are "unknown"; provenance, confidence,
timestamps and USER.md exclusion are unchanged (principle P-07, ledger EPI-01).
"""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # api/ dir
import app  # noqa: E402


def _career_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE companies (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE job_applications (id INTEGER PRIMARY KEY, company_id INTEGER, role_title TEXT, stage TEXT);
        CREATE TABLE career_activities (id INTEGER PRIMARY KEY, application_id INTEGER, activity_type TEXT,
            title TEXT, details TEXT, source TEXT, occurred_at TEXT, confidence REAL);
        INSERT INTO companies VALUES (1, 'Synthetic Co');
        INSERT INTO job_applications VALUES (10, 1, 'Synthetic Engineer', 'applied');
        INSERT INTO job_applications VALUES (11, NULL, 'Synthetic Analyst', 'discovered');
        INSERT INTO career_activities VALUES
            (100, 10, 'applied', 'Applied to Synthetic Co', 'Synthetic details', 'gmail', '2026-10-01 09:30:00', 0.82),
            (101, 11, NULL, 'Recruiter note', NULL, 'gmail', '2026-10-02 10:00:00', NULL);
    """)
    return conn


class CareerProjectionTests(unittest.TestCase):
    def setUp(self):
        self.conn = _career_conn()
        self.addCleanup(self.conn.close)
        self.records = {r["id"]: r for r in app._career_memory_records(self.conn)}

    def test_career_activity_is_unknown_never_fact(self):
        self.assertEqual(set(self.records), {"career_activity_100", "career_activity_101"})
        for record in self.records.values():
            self.assertEqual(record["kind"], "unknown")
            self.assertNotEqual(record["kind"], "fact")

    def test_career_provenance_confidence_and_timestamps_are_preserved(self):
        r = self.records["career_activity_100"]
        self.assertEqual(r["provenance"], {"kind": "career_event", "source_account": "gmail",
                                           "label": "Career activity: applied", "at": "2026-10-01T09:30:00+00:00"})
        self.assertEqual(r["confidence"], 82)
        self.assertEqual((r["created_at"], r["updated_at"]), ("2026-10-01T09:30:00+00:00",) * 2)
        self.assertEqual(self.records["career_activity_101"]["confidence"], None)  # absent stays absent
        self.assertEqual(self.records["career_activity_101"]["provenance"]["label"], "Career activity: event")

    def test_career_response_shape_is_unchanged(self):
        keys = {"id", "summary", "content", "category", "entity_type", "entities", "kind", "confidence",
                "importance", "pinned", "tags", "provenance", "created_at", "updated_at", "last_accessed", "related"}
        for record in self.records.values():
            self.assertEqual(set(record), keys)
        self.assertEqual([e["id"] for e in self.records["career_activity_100"]["entities"]],
                         ["application_10", "company_1"])


class CuratedProjectionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "projects").mkdir()
        (root / "projects" / "synthetic.md").write_text("# Synthetic project\nA note.§# Second entry\nMore.",
                                                        encoding="utf-8")
        (root / "USER.md").write_text("# Sensitive owner profile\nmust never be projected", encoding="utf-8")
        (root / "empty.md").write_text("   \n", encoding="utf-8")
        patcher = mock.patch.object(app, "MEM", root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.records = app._curated_memory_records()

    def test_curated_markdown_is_unknown_never_fact(self):
        self.assertEqual(len(self.records), 2)
        for record in self.records:
            self.assertEqual(record["kind"], "unknown")
            self.assertNotEqual(record["kind"], "fact")

    def test_curated_provenance_and_absent_confidence_are_preserved(self):
        for record in self.records:
            self.assertEqual(record["provenance"]["kind"], "curated_memory")
            self.assertEqual(record["provenance"]["source_account"], "hermes · memories")
            self.assertIn("(timestamp: file mtime)", record["provenance"]["label"])
            self.assertIsNone(record["confidence"])
            self.assertEqual(record["category"], "projects")

    def test_user_md_and_empty_files_are_excluded(self):
        text = " ".join(r["summary"] + " " + r["content"] + " " + r["provenance"]["label"] for r in self.records)
        self.assertNotIn("Sensitive owner profile", text)
        self.assertNotIn("USER.md", text)
        self.assertEqual(sorted(r["summary"] for r in self.records), ["Second entry", "Synthetic project"])


class CombinedProjectionTests(unittest.TestCase):
    def test_no_projected_record_asserts_fact(self):
        conn = _career_conn()
        self.addCleanup(conn.close)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(app, "MEM", Path(tmp)):
            (Path(tmp) / "note.md").write_text("# Note\nbody", encoding="utf-8")
            records = app._all_memory_records(conn)
        self.assertEqual(len(records), 3)
        self.assertEqual([r for r in records if r["kind"] == "fact"], [])


if __name__ == "__main__":
    unittest.main()
