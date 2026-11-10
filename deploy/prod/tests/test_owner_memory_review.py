"""The nightly review's context script: only the owner's console + private Telegram DM, fast Groq turns included."""
import importlib.util
import json
import os
import sqlite3
import tempfile
import unittest
import unittest.mock
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


class ConsolidationContextTests(unittest.TestCase):
    """P-4 P4-1: moments from the router trace (flags only), verified goal outcomes, and proposal guidance."""
    setUp = ReviewContextTests.setUp
    tearDown = ReviewContextTests.tearDown

    def write_log(self, records):
        (self.home / "lilith_router" / "decisions.log").write_text(
            "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")

    def test_owner_lines_are_tagged_from_trace_flags_only(self):
        self.write_log([
            {"ts": NOW - 3598, "lane": "appraisal", "signals": ["progress", "goal"], "goal_refs": ["g1"],
             "note": "TRACE-TEXT-NEVER"},
            {"ts": NOW - 195, "lane": "social_preferences", "durable_correction": True},
            {"ts": NOW - 40 * 3600, "lane": "appraisal", "signals": ["setback"]},            # outside the window
            {"ts": NOW - 50, "lane": "metacognition", "recall_gap": False},
            "not json"])
        out = OMR.main(self.home, now=NOW)
        self.assertIn("OWNER: I started learning the violin this week [moment: they reported progress or an "
                      "achievement; touches a goal they track]", out)
        self.assertIn("console: my sister's name is Asha [moment: a correction about how LILITH should behave]", out)
        self.assertNotIn("setback", out.split("=== OWNER CONVERSATION")[1])
        self.assertNotIn("TRACE-TEXT-NEVER", out)
        self.assertNotIn("nothing remembered", out)                                    # recall_gap False: no tag

    def test_moments_link_only_to_a_recent_owner_line(self):
        self.write_log([{"ts": NOW - 3600 + 400, "lane": "appraisal", "signals": ["setback"]}])  # 400 s after: too late
        self.assertNotIn("[moment:", OMR.main(self.home, now=NOW).split("=== OWNER CONVERSATION")[1])

    def test_guidance_and_goal_outcomes(self):
        goals = {"goals": [
            {"goalId": "g1", "title": "Follow up on application 12 - Data Engineer at Acme", "lifecycleState": "COMPLETED",
             "completedAt": "2026-11-09T10:00:00Z"},
            {"goalId": "g2", "title": "Pass the CKA exam", "lifecycleState": "ACTIVE", "updatedAt": NOW},
            {"goalId": "g3", "title": "Old goal", "lifecycleState": "FAILED", "failedAt": NOW - 90 * 3600}]}

        class Resp:
            def __init__(self, body): self.body = body
            def read(self): return json.dumps(self.body).encode()
            def __enter__(self): return self
            def __exit__(self, *a): return False

        now = 1_762_700_000.0                                                              # 2025-11-09T14:53Z
        goals["goals"][0]["completedAt"] = now - 3600
        goals["goals"][2]["failedAt"] = now - 90 * 3600                                  # outside the 26 h window
        with unittest.mock.patch.object(OMR.urllib.request, "urlopen", return_value=Resp(goals)):
            lines = OMR.goal_outcomes(now - OMR.REVIEW_HOURS * 3600)
        self.assertEqual(len(lines), 1)
        self.assertIn("their application for Data Engineer at Acme: marked completed in their tracked goals on",
                      lines[0])
        self.assertIn("not necessarily when it happened", lines[0])                 # marked time != event time
        self.assertNotIn("12", lines[0].split(":")[0])
        self.assertNotIn("g1", lines[0])
        out = OMR.main(self.home, now=NOW)
        self.assertIn("=== HOW TO PROPOSE ===", out)
        self.assertIn('"Preference (scope): ..."', out)
        self.assertIn("never store the scenario itself as true", out)
        self.assertIn("=== THEIR TRACKED GOAL OUTCOMES", out)

    def test_goal_api_down_and_log_missing_fail_open(self):
        out = OMR.main(self.home, now=NOW)                                               # API is 127.0.0.1:9
        self.assertIn("(none)", out.split("=== THEIR TRACKED GOAL OUTCOMES")[1])
        self.assertNotIn("[moment:", out.split("=== OWNER CONVERSATION")[1])


class CommitmentSectionTests(unittest.TestCase):
    """P-4 P4-5b: LILITH's own commitments are a separate section; kept ones are only counted and never memories;
    missed / failed ones are her unresolved responsibilities with scheduler evidence; no delivery claims."""
    setUp = ReviewContextTests.setUp
    tearDown = ReviewContextTests.tearDown

    def fake_goals(self, life, once):
        class Resp:
            def __init__(self, body): self.body = body
            def read(self): return json.dumps({"goals": self.body}).encode()
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def urlopen(url, timeout=5):
            return Resp(once if "type=commitment.once" in url else life + once)
        return unittest.mock.patch.object(OMR.urllib.request, "urlopen", side_effect=urlopen)

    def iso(self, ts):
        return OMR._dt.datetime.fromtimestamp(ts, OMR._dt.timezone.utc).isoformat()

    def test_separate_section_kept_counted_unresolved_listed(self):
        life = [{"goalId": "g1", "type": "career.followup", "title": "Pass the CKA exam", "lifecycleState": "COMPLETED",
                 "completedAt": self.iso(NOW - 3600)}]
        once = [
            {"goalId": "c1", "type": "commitment.once", "title": "Water reminder", "lifecycleState": "COMPLETED",
             "completedAt": self.iso(NOW - 600), "deadline": "2027-01-15T07:08:18Z"},
            {"goalId": "c2", "type": "commitment.once", "title": "Call the bank", "lifecycleState": "BLOCKED",
             "deadline": "2027-01-15T09:00:00Z", "blockedReason": "missed: due 2027-01-15T09:00:00Z and not run"},
            {"goalId": "c3", "type": "commitment.once", "title": "Check release notes", "lifecycleState": "FAILED",
             "failedAt": self.iso(NOW - 2 * 86400), "deadline": "2027-01-13T09:00:00Z"},
            {"goalId": "c4", "type": "commitment.once", "title": "Old failure", "lifecycleState": "FAILED",
             "failedAt": self.iso(NOW - 30 * 86400)},
            {"goalId": "c5", "type": "commitment.once", "title": "Later", "lifecycleState": "ACTIVE"}]
        with self.fake_goals(life, once):
            out = OMR.main(self.home, now=NOW)
        life_part = out.split("=== THEIR TRACKED GOAL OUTCOMES")[1].split("===")[1]
        mine = out.split("=== LILITH'S OWN COMMITMENTS")[1].split("=== OWNER CONVERSATION")[0]
        self.assertIn("Pass the CKA exam", life_part)
        self.assertNotIn("Water reminder", out)                         # kept: counted, never listed or proposed
        self.assertIn("1 reminder(s) ran as scheduled", mine)
        self.assertIn('UNRESOLVED: "Call the bank" was due 2027-01-15T09:00:00Z', mine)
        self.assertIn("missed: due", mine)
        self.assertIn('UNRESOLVED: "Check release notes"', mine)
        self.assertNotIn("Old failure", mine)
        self.assertNotIn("Later", mine)
        for claim in ("was delivered", "they received", "reached them as planned."):
            self.assertNotIn(claim, mine)
        self.assertIn("never propose them as memories", out)

    def test_commitment_records_unavailable_says_so(self):
        out = OMR.main(self.home, now=NOW)                               # API is 127.0.0.1:9
        mine = out.split("=== LILITH'S OWN COMMITMENTS")[1].split("=== OWNER CONVERSATION")[0]
        self.assertIn("commitment records unavailable", mine)


def utc(text):
    """Epoch seconds for an ISO UTC time ('2026-11-09T18:20')."""
    return OMR._dt.datetime.fromisoformat(text).replace(tzinfo=OMR._dt.timezone.utc).timestamp()


REVIEW_AT = utc("2026-11-10T16:30")                    # the nightly run (Tuesday); never a said-on or event date


class ConversationDateTests(unittest.TestCase):
    """P4-1 conversation dates: each owner-local day is marked with when its lines were said; the guidance keeps the
    event date, the told date, unknown dates and never-event dates (run, approval, replacement) apart."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / "lilith_router").mkdir()
        (self.home / "lilith_router" / "canonical_memory.json").write_text(
            json.dumps({"schemaVersion": 1, "enabled": True, "ownerTelegramUserIds": [OWNER]}), encoding="ascii")
        self.env = unittest.mock.patch.dict(os.environ, {"HERMES_TIMEZONE": ""})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def db(self, rows, extra_sessions=()):
        con = sqlite3.connect(self.home / "state.db")
        con.executescript("""
            CREATE TABLE sessions (id TEXT, source TEXT, user_id TEXT, chat_id TEXT, chat_type TEXT);
            CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT,
                                   timestamp REAL, active INTEGER);""")
        con.executemany("INSERT INTO sessions VALUES (?,?,?,?,?)",
                        [("dm", "telegram", OWNER, OWNER, "dm"), *extra_sessions])
        con.executemany("INSERT INTO messages (session_id, role, content, timestamp, active) VALUES (?,?,?,?,1)",
                        [(r[0], r[1], r[2], r[3]) if len(r) == 4 else ("dm", *r) for r in rows])
        con.commit()
        con.close()

    def convo(self, tz=None):
        if tz:
            (self.home / "config.yaml").write_text(f"model: x\ntimezone: {tz}  # owner\n", encoding="utf-8")
        out = OMR.main(self.home, now=REVIEW_AT)
        return out.split("=== OWNER CONVERSATION")[1].splitlines()[1:]

    def day_of(self, lines, needle):
        """The said-on marker a line sits under."""
        marker = None
        for line in lines:
            if line.startswith("--- said on "):
                marker = line
            elif needle in line:
                return marker
        raise AssertionError(needle)

    def test_conversation_crossing_local_midnight(self):
        self.db([("user", "heading to bed soon", utc("2026-11-09T18:20")),        # 23:50 Monday in Colombo
                 ("assistant", "sleep well", utc("2026-11-09T18:21")),
                 ("user", "actually still up, I finished the Helm chart", utc("2026-11-09T18:40"))])  # 00:10 Tue
        lines = self.convo("Asia/Colombo")
        self.assertEqual(self.day_of(lines, "heading to bed"), "--- said on 2026-11-09 (Monday), Asia/Colombo ---")
        self.assertEqual(self.day_of(lines, "sleep well"), "--- said on 2026-11-09 (Monday), Asia/Colombo ---")
        self.assertEqual(self.day_of(lines, "Helm chart"), "--- said on 2026-11-10 (Tuesday), Asia/Colombo ---")
        self.assertEqual([l for l in lines if l.startswith("---")][-1], "--- said on 2026-11-10 (Tuesday), "
                                                                          "Asia/Colombo ---")

    def test_multiple_dates_in_one_review_each_marked_once_in_order(self):
        self.db([("user", "first day line", utc("2026-11-09T17:00")), ("user", "first day again", utc("2026-11-09T17:05")),
                 ("user", "second day line", utc("2026-11-10T09:00")), ("assistant", "reply", utc("2026-11-10T09:01"))])
        lines = self.convo()
        markers = [l for l in lines if l.startswith("--- said on ")]
        self.assertEqual(markers, ["--- said on 2026-11-09 (Monday), UTC ---", "--- said on 2026-11-10 (Tuesday), UTC ---"])
        self.assertEqual(lines[0], markers[0])                                   # no undated line before a marker
        self.assertLess(lines.index(markers[0]), lines.index("OWNER: first day again"))
        self.assertLess(lines.index("OWNER: first day again"), lines.index(markers[1]))

    def test_truncated_window_keeps_the_date_of_the_kept_lines(self):
        self.db([("user", "x" * 600 + " %d" % i, utc("2026-11-09T17:00") + i) for i in range(30)])
        with unittest.mock.patch.object(OMR, "TOTAL", 2000):
            lines = self.convo()
        self.assertEqual(lines[0], "--- said on 2026-11-09 (Monday), UTC ---")
        self.assertNotIn(" 0", lines[1][-3:])                                    # the oldest lines were the ones cut

    def test_relative_date_is_tied_to_the_line_it_was_said_on_not_the_run(self):
        self.db([("user", "I passed the CKA yesterday", utc("2026-11-09T18:20"))])  # Monday 23:50 Colombo
        lines = self.convo("Asia/Colombo")
        self.assertEqual(self.day_of(lines, "passed the CKA yesterday"),
                         "--- said on 2026-11-09 (Monday), Asia/Colombo ---")   # yesterday = Sunday 8 Nov
        utc_lines = self.convo("UTC")
        self.assertEqual(self.day_of(utc_lines, "passed the CKA yesterday"), "--- said on 2026-11-09 (Monday), UTC ---")
        g = OMR.GUIDANCE
        self.assertIn("Resolve today / yesterday / last <weekday> against the said-on date of THAT line", g)
        self.assertIn("never against today's date", g)
        self.assertNotIn("2026-11-10", "\n".join(lines))                         # run day: no line was said then

    def test_timezone_boundary_changes_the_said_on_day(self):
        self.db([("user", "boundary line", utc("2026-11-09T18:40"))])            # 18:40 UTC = 00:10 Tue Colombo
        self.assertEqual(self.day_of(self.convo("UTC"), "boundary"), "--- said on 2026-11-09 (Monday), UTC ---")
        self.assertEqual(self.day_of(self.convo("Asia/Colombo"), "boundary"),
                         "--- said on 2026-11-10 (Tuesday), Asia/Colombo ---")
        with unittest.mock.patch.dict(os.environ, {"HERMES_TIMEZONE": "America/Los_Angeles"}):  # env wins
            self.assertEqual(self.day_of(self.convo("Asia/Colombo"), "boundary"),
                             "--- said on 2026-11-09 (Monday), America/Los_Angeles ---")

    def test_timezone_setting_fails_safe_to_named_utc(self):
        for cfg in ("timezone: Not/AZone\n", "agent:\n  timezone: Asia/Colombo\n", "timezone:\n", None):
            if cfg is None:
                (self.home / "config.yaml").unlink(missing_ok=True)
            else:
                (self.home / "config.yaml").write_text(cfg, encoding="utf-8")
            self.assertEqual(OMR.review_timezone(self.home)[1], "UTC", cfg)
        (self.home / "config.yaml").write_text('timezone: "Asia/Colombo"\n', encoding="utf-8")
        self.assertEqual(OMR.review_timezone(self.home)[1], "Asia/Colombo")

    def test_ambiguous_and_undated_events_are_never_given_a_day(self):
        self.db([("user", "I got the offer the other day", utc("2026-11-10T09:00")),
                 ("user", "I moved to Manchester", utc("2026-11-10T09:05"))])
        out = OMR.main(self.home, now=REVIEW_AT)
        g = OMR.GUIDANCE
        self.assertIn('write "On <date>, ..." ONLY when they said when it happened', g)
        self.assertIn('write "Told LILITH on\n    <said-on date>: ..." That is when they said it, not when it happened', g)
        for vague in ('"recently"', '"the other day"', '"last week"', '"a while ago"'):
            self.assertIn(vague, g)
        self.assertIn("Never\n    invent or guess a day.", g)
        self.assertNotIn("On 2026-11-09 he passed", out)                         # the old example invited the run date
        self.assertIn("I moved to Manchester", out)

    def test_never_an_event_date_run_approval_replacement_or_goal_marked(self):
        g = OMR.GUIDANCE
        self.assertIn('the date this review runs (the "Conversation started" date), and any stored, approval,\n'
                      "    replacement or goal-marked date", g)

    def test_repeated_line_on_another_day_stays_on_its_first_day_and_is_noted(self):
        self.db([("user", "I passed yesterday", utc("2026-11-09T17:00")),
                 ("user", "I passed yesterday", utc("2026-11-09T17:01")),          # same-day re-insert: silent
                 ("user", "I passed yesterday", utc("2026-11-10T09:00")),          # next day: noted, not moved
                 ("assistant", "congrats", utc("2026-11-09T17:02")), ("assistant", "congrats", utc("2026-11-10T09:01"))])
        lines = self.convo()
        owner = [l for l in lines if l.startswith("OWNER: ")]
        self.assertEqual(owner, ["OWNER: I passed yesterday [also said on 2026-11-10]"])
        self.assertEqual(self.day_of(lines, "I passed yesterday"), "--- said on 2026-11-09 (Monday), UTC ---")
        self.assertEqual([l for l in lines if l.startswith("--- said on ")], ["--- said on 2026-11-09 (Monday), UTC ---"])
        self.assertIn("relative word sits on a line marked [also said on ...]", OMR.GUIDANCE)

    def test_plans_corrections_history_and_fiction_keep_their_meaning(self):
        g = OMR.GUIDANCE
        self.assertIn('a plan or intention stays a plan ("plans to ..."), never done', g)
        self.assertIn("a correction\n  replaces the entry it corrects", g)
        self.assertIn('a past fact stays past ("used to ...")', g)
        self.assertIn("a wish, guess or hypothetical stays one", g)
        self.assertIn("A fictional, hypothetical or test scenario is never a real fact about them", g)
        self.assertIn("never store the scenario itself as true", g)

    def test_other_chats_add_no_dates_and_nothing_is_written(self):
        self.db([("user", "owner line", utc("2026-11-10T09:00")),
                 ("grp", "user", "GROUP LINE", utc("2026-11-09T12:00")), ("x", "user", "OTHER LINE", utc("2026-11-09T12:00"))],
                extra_sessions=[("grp", "telegram", OWNER, "-1001", "group"), ("x", "telegram", "42", "42", "dm")])
        before = sorted(str(p) for p in self.home.rglob("*"))
        lines = self.convo()
        self.assertEqual([l for l in lines if l.startswith("--- said on ")], ["--- said on 2026-11-10 (Tuesday), UTC ---"])
        self.assertNotIn("GROUP LINE", "\n".join(lines))
        self.assertNotIn("OTHER LINE", "\n".join(lines))
        after = sorted(str(p) for p in self.home.rglob("*") if "memory-review" not in str(p))
        self.assertEqual(before, after)                                          # read-only (beyond SEEN snapshot)

    def test_only_assistant_lines_is_still_silent(self):
        self.db([("assistant", "hello?", utc("2026-11-10T09:00"))])
        self.assertEqual(OMR.main(self.home, now=REVIEW_AT), "NO_NEW_OWNER_CONVERSATION")


if __name__ == "__main__":
    unittest.main()
