"""The nightly review's context script: only the owner's console + private Telegram DM, fast Groq turns included."""
import importlib.util
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
os.environ["LILITH_OS_API_URL"] = "http://127.0.0.1:9"     # never reach a real Core API (a local tunnel may be PROD)

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

    def stage(self, pid, payload, summary="s"):
        d = self.home / "pending" / "memory"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{pid}.json").write_text(json.dumps({"id": pid, "summary": summary, "payload": payload}), encoding="utf-8")

    def test_rejected_proposals_are_never_proposed_again(self):
        self.stage("rej1", {"action": "add", "target": "user", "content": "User plays the violin."})
        self.stage("ok1", {"action": "add", "target": "user", "content": "User likes green tea."})
        self.stage("bat1", {"action": "batch", "target": "user", "operations": [
            {"action": "replace", "old_text": "x", "content": "User lives in Colombo."},
            {"action": "add", "content": "User calls Sundays Quiet Days."}]})
        self.assertEqual(OMR.snapshot(self.home), 3)
        self.assertEqual(OMR.snapshot(self.home), 0)                                   # recorded once
        for pid in ("rej1", "ok1", "bat1"):                                            # all decided
            (self.home / "pending" / "memory" / f"{pid}.json").unlink()
        (self.home / "memories" / "USER.md").write_text("Prefers tea.\n§\nUser likes  green tea.", encoding="utf-8")
        out = OMR.main(self.home, now=NOW)
        block = out.split("=== REJECTED BY THE OWNER (never propose these again) ===")[1].split("===")[0]
        self.assertIn("- User plays the violin.", block)                              # rejected
        self.assertIn("- User lives in Colombo.", block)                              # rejected batch op
        self.assertIn("- User calls Sundays Quiet Days.", block)
        self.assertNotIn("green tea", block)                                           # approved: in memory

    def test_still_pending_is_not_rejected(self):
        self.stage("p1", {"action": "add", "target": "memory", "content": "Weekly planning on Mondays."})
        out = OMR.main(self.home, now=NOW)
        block = out.split("=== REJECTED BY THE OWNER (never propose these again) ===")[1].split("===")[0]
        self.assertIn("(none)", block)
        self.assertIn("- p1:", out)

    def test_snapshot_job_wrapper(self):
        import os
        import runpy
        self.stage("w1", {"action": "add", "target": "user", "content": "User owns a bike."})
        old = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = str(self.home)
        try:
            runpy.run_path(str(ROOT / "deploy/prod/hermes_scripts/owner_memory_snapshot.py"))
        finally:
            os.environ.pop("HERMES_HOME") if old is None else os.environ.__setitem__("HERMES_HOME", old)
        self.assertIn('"w1"', (self.home / "memory-review" / "seen.jsonl").read_text(encoding="utf-8"))

    def test_nothing_new_is_silent(self):
        self.assertEqual(OMR.main(self.home, now=NOW + 30 * 3600), "NO_NEW_OWNER_CONVERSATION")

    def test_without_owner_settings_only_the_console_counts(self):
        (self.home / "lilith_router" / "canonical_memory.json").unlink()
        out = OMR.main(self.home, now=NOW)
        self.assertIn("Asha", out)
        self.assertNotIn("violin", out)


DU, DC = "200000000000000001", "300000000000000001"          # synthetic verified Discord user / DM channel


class DiscordOwnerDmTests(ReviewContextTests):
    """Owner request 2026-11-08: the verified Discord owner DM joins the review; nothing else from Discord does."""

    def setUp(self):
        super().setUp()
        (self.home / "lilith_router" / "canonical_memory.json").write_text(json.dumps(
            {"schemaVersion": 1, "enabled": True, "ownerTelegramUserIds": [OWNER],
             "ownerDiscordDms": [{"userId": DU, "chatId": DC}]}), encoding="ascii")
        con = sqlite3.connect(self.home / "state.db")
        con.executemany("INSERT INTO sessions VALUES (?,?,?,?,?)", [
            ("ddm", "discord", DU, DC, "dm"),                           # the verified owner DM
            ("dsrv", "discord", DU, "400000000000000001", "group"),     # same user, server channel
            ("dthr", "discord", DU, DC, "thread"),                      # same ids, not a DM
            ("dodm", "discord", DU, "300000000000000009", "dm"),        # same user, another (unverified) DM
            ("dusr", "discord", "200000000000000009", DC, "dm"),        # another user
        ])
        con.executemany("INSERT INTO messages (session_id, role, content, timestamp, active) VALUES (?,?,?,?,?)", [
            ("ddm", "user", "DISCORD-OWNER: I prefer short answers in the morning", NOW - 300, 1),
            ("ddm", "user", "I started learning the violin this week", NOW - 250, 1),   # same fact, other channel
            ("dsrv", "user", "SERVER-TEXT", NOW - 100, 1), ("dthr", "user", "THREAD-TEXT", NOW - 100, 1),
            ("dodm", "user", "UNVERIFIED-DM", NOW - 100, 1), ("dusr", "user", "OTHER-DISCORD-USER", NOW - 100, 1)])
        con.commit()
        con.close()

    def test_verified_dm_only_and_one_copy_across_channels(self):
        out = OMR.main(self.home, now=NOW)
        self.assertIn("DISCORD-OWNER: I prefer short answers in the morning", out)
        self.assertEqual(out.count("violin"), 1)                  # the same line from Telegram and Discord: once
        for absent in ("SERVER-TEXT", "THREAD-TEXT", "UNVERIFIED-DM", "OTHER-DISCORD-USER", "DISCORD-TEXT",
                       "GROUP-SECRET", "OTHER-USER"):
            self.assertNotIn(absent, out, absent)
        self.assertIn("verified Discord DM", out)

    def test_malformed_or_missing_pairs_fail_closed(self):
        for pairs in ([{"userId": DU}], "x", [{"userId": "abc", "chatId": DC}]):
            with self.subTest(pairs=pairs):
                (self.home / "lilith_router" / "canonical_memory.json").write_text(json.dumps(
                    {"schemaVersion": 1, "enabled": True, "ownerTelegramUserIds": [OWNER], "ownerDiscordDms": pairs}),
                    encoding="ascii")
                self.assertNotIn("DISCORD-OWNER", OMR.main(self.home, now=NOW))


if __name__ == "__main__":
    unittest.main()
