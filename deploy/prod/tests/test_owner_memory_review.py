"""The nightly review's context script: only the owner's console + private Telegram DM, fast Groq turns included."""
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("omr", ROOT / "deploy/prod/hermes_scripts/owner_memory_review.py")
OMR = importlib.util.module_from_spec(spec)
spec.loader.exec_module(OMR)
OWNER = "1111794198"
NOW = 1_800_000_000.0


class ReviewContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / "lilith_router").mkdir()
        (self.home / "lilith_router" / "canonical_memory.json").write_text(
            json.dumps({"schemaVersion": 1, "enabled": True, "ownerTelegramUserIds": [OWNER]}), encoding="ascii")
        (self.home / "memories").mkdir()
        (self.home / "memories" / "USER.md").write_text("Prefers tea.", encoding="utf-8")
        con = sqlite3.connect(self.home / "state.db")
        con.executescript("""
            CREATE TABLE sessions (id TEXT, source TEXT, user_id TEXT, chat_id TEXT, chat_type TEXT);
            CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT,
                                   timestamp REAL, active INTEGER);""")
        con.executemany("INSERT INTO sessions VALUES (?,?,?,?,?)", [
            ("dm", "telegram", OWNER, OWNER, "dm"), ("grp", "telegram", OWNER, "-1001", "group"),
            ("other", "telegram", "42", "42", "dm"), ("disc", "discord", OWNER, "55", "group"),
            ("con", "lilith_os", "", "", ""), ("cli", "cli", "", "", "")])
        rows = [("dm", "user", "I started learning the violin this week", NOW - 3600, 1),
                ("dm", "assistant", "That's lovely! (fast groq reply)", NOW - 3590, 1),
                ("dm", "user", "I started learning the violin this week", NOW - 3500, 1),      # compaction duplicate
                ("dm", "user", "old message", NOW - 40 * 3600, 1),
                ("dm", "user", "inactive row", NOW - 100, 0),
                ("dm", "tool", "tool output", NOW - 3580, 1),
                ("grp", "user", "GROUP-SECRET", NOW - 100, 1), ("other", "user", "OTHER-USER", NOW - 100, 1),
                ("disc", "user", "DISCORD-TEXT", NOW - 100, 1), ("cli", "user", "BRIEF-TEXT", NOW - 100, 1),
                ("con", "user", "console: my sister's name is Asha", NOW - 200, 1)]
        con.executemany("INSERT INTO messages (session_id, role, content, timestamp, active) VALUES (?,?,?,?,?)", rows)
        con.commit()
        con.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_owner_chats_in_window_including_fast_turns(self):
        out = OMR.main(self.home, now=NOW)
        self.assertIn("OWNER: I started learning the violin this week", out)
        self.assertEqual(out.count("violin"), 1)                                   # deduplicated
        self.assertIn("LILITH: That's lovely! (fast groq reply)", out)
        self.assertIn("console: my sister's name is Asha", out)
        for absent in ("old message", "inactive row", "tool output", "GROUP-SECRET", "OTHER-USER", "DISCORD-TEXT",
                       "BRIEF-TEXT"):
            self.assertNotIn(absent, out, absent)
        self.assertIn("Prefers tea.", out)                                         # dedupe against memory
        self.assertIn("relationship-origin", out)                                  # canonical: never propose

    def test_pending_proposals_are_listed(self):
        (self.home / "pending" / "memory").mkdir(parents=True)
        (self.home / "pending" / "memory" / "abc123.json").write_text(
            json.dumps({"id": "abc123", "summary": "add to user profile: plays violin"}), encoding="utf-8")
        self.assertIn("- abc123: add to user profile: plays violin", OMR.main(self.home, now=NOW))

    def test_nothing_new_is_silent(self):
        self.assertEqual(OMR.main(self.home, now=NOW + 30 * 3600), "NO_NEW_OWNER_CONVERSATION")

    def test_without_owner_settings_only_the_console_counts(self):
        (self.home / "lilith_router" / "canonical_memory.json").unlink()
        out = OMR.main(self.home, now=NOW)
        self.assertIn("Asha", out)
        self.assertNotIn("violin", out)


if __name__ == "__main__":
    unittest.main()
