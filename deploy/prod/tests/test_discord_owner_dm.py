"""Private Discord owner DM (2026-11-08): an additional verified owner channel for the SAME LILITH identity.

Owner only when the (Discord user id, DM channel id) pair is one the owner verified through the Telegram owner DM and
the operator installed in the root-owned canonical_memory.json. Server channels, threads, groups, bots and other users
stay non-owner. Synthetic ids only.
"""
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_owner_memory import ROOT, load_router, src  # noqa: E402

TG = "100000001"
DU, DC = "200000000000000001", "300000000000000001"          # synthetic Discord user / DM channel ids
VERIFIED = {"schemaVersion": 1, "enabled": True, "ownerTelegramUserIds": [TG],
            "ownerDiscordDms": [{"userId": DU, "chatId": DC}]}
UNVERIFIED = {"schemaVersion": 1, "enabled": True, "ownerTelegramUserIds": [TG]}


def dm(**kw):
    base = dict(user_id=DU, chat_id=DC, chat_type="dm", guild_id=None, thread_id=None, is_bot=False, user_name="me")
    base.update(kw)
    return src(**base)


class OwnerRuleTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.gi = load_router()
        self.cm = self.gi._canonical_memory

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_only_the_verified_dm_pair_is_an_owner_channel(self):
        self.assertEqual(self.cm.channel_for(VERIFIED, "discord", dm()), "discord_owner_dm")
        for label, s in [("server channel", dm(chat_type="group", chat_id="400000000000000001", guild_id="5")),
                         ("same user in a guild", dm(chat_type="group", guild_id="5")),
                         ("thread", dm(chat_type="thread", thread_id="6")),
                         ("other DM channel", dm(chat_id="300000000000000002")),
                         ("other user, same channel id", dm(user_id="200000000000000002")),
                         ("bot", dm(is_bot=True)),
                         ("guild set on a dm", dm(guild_id="5"))]:
            with self.subTest(label):
                self.assertEqual(self.cm.channel_for(VERIFIED, "discord", s), "public")
        self.assertEqual(self.cm.channel_for(UNVERIFIED, "discord", dm()), "public")       # not yet verified
        self.assertEqual(self.cm.channel_for(None, "discord", dm()), "public")             # feature off

    def test_telegram_and_console_rules_unchanged(self):
        self.assertEqual(self.cm.channel_for(VERIFIED, "telegram", src(user_id=TG, chat_id=TG, chat_type="dm")),
                         "telegram_owner_dm")
        self.assertEqual(self.cm.channel_for(VERIFIED, "lilith_os", src()), "lilith_os")
        self.assertEqual(self.cm.channel_for(VERIFIED, "telegram", src(user_id=DU, chat_id=DU, chat_type="dm")),
                         "public")                                    # a Discord id never counts on Telegram

    def test_settings_accept_the_optional_pairs_and_reject_malformed(self):
        home = self.tmp / "home"
        (home / "lilith_router").mkdir(parents=True)
        path = home / "lilith_router" / "canonical_memory.json"
        uid = os.lstat(home).st_uid

        def load(value):
            path.write_text(json.dumps(value), encoding="ascii")
            with mock.patch.object(self.cm.os, "lstat", lambda p: types.SimpleNamespace(
                    st_mode=0o100644, st_uid=uid, st_size=len(json.dumps(value)))):
                return self.cm.load_settings(home, owner_uid=uid)

        self.assertEqual(load(VERIFIED), VERIFIED)
        self.assertEqual(load(UNVERIFIED), UNVERIFIED)
        for bad in ([{"userId": DU}], [{"userId": "12", "chatId": DC}], [{"userId": DU, "chatId": DC, "x": "1"}],
                    [{"userId": DU, "chatId": DC}] * 4, "x"):
            with self.subTest(bad=bad):
                self.assertIsNone(load(dict(UNVERIFIED, ownerDiscordDms=bad)))
        self.assertIsNone(load(dict(VERIFIED, extra=1)))

    def route(self, source, settings=VERIFIED, message="hi"):
        gi = self.gi
        gi._route_turn_impl = lambda **kw: None
        gi._canonical_memory.load_settings = lambda home, **kw: settings
        gi._canonical_memory.turn_note = lambda *a, **kw: None
        gi._platform_name = lambda s: "discord"
        ctx = types.SimpleNamespace(source=source, session_key="agent:main:discord:x", message=message)
        return gi.route_turn(runner=None, ctx=ctx, model="m", runtime_kwargs={}, turn_route={}, combined_ephemeral="")

    def test_owner_dm_gets_the_same_owner_path_and_server_channels_do_not(self):
        self.assertIs(self.route(dm())["owner_memory"], True)
        self.assertEqual(self.cm.current_channel(), "discord_owner_dm")
        self.assertIs(self.route(dm(chat_type="group", guild_id="5"))["owner_memory"], False)
        self.assertEqual(self.cm.current_channel(), "public")

    def test_owner_label_joins_live_and_cognitive_lists_only_for_the_verified_dm(self):
        cfg = self.gi._config.RouterConfig(enabled=True, mode="live", live_channels=["telegram", "discord_owner_dm"],
                                           cognitive_channels=["lilith_os", "telegram", "discord_owner_dm"],
                                           cognitive_enabled=True)
        self.route(dm())
        self.assertTrue(cfg.channel_is_live("discord", DC))
        self.assertTrue(cfg.cognitive_is_active("discord", DC))
        self.route(dm(chat_type="group", guild_id="5", chat_id="400000000000000001"))
        self.assertFalse(cfg.channel_is_live("discord", "400000000000000001"))
        self.assertFalse(cfg.cognitive_is_active("discord", "400000000000000001"))

    def test_deployed_router_yaml_names_the_label_and_no_dm_id(self):
        text = (ROOT / "deploy/prod/lilith_router/router.yaml").read_text(encoding="utf-8")
        self.assertIn('"discord_owner_dm"]', text)
        cfg = self.gi._config
        with mock.patch.object(cfg, "CONFIG_PATH", ROOT / "deploy/prod/lilith_router/router.yaml"):
            c = cfg.load()
        self.assertIn("discord_owner_dm", c.live_channels)
        self.assertIn("discord_owner_dm", c.cognitive_channels)


class LinkChallengeTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.gi = load_router()
        self.link = self.gi._owner_link
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.sent = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def send(self, chat, text):
        self.sent.append((chat, text))
        return True

    def h(self, message, source=None, now=1000.0, settings=UNVERIFIED, platform="discord"):
        return self.link.handle(settings, platform, source or dm(), message, home=self.home, send=self.send, now=now)

    def code(self):
        return self.sent[-1][1].split("\n")[4].strip()

    def test_full_challenge_records_the_verified_pair_and_tells_telegram(self):
        self.assertIn("one-time code", self.h("link owner"))
        chat, text = self.sent[-1]
        self.assertEqual(chat, TG)
        self.assertIn(DU, text)
        self.assertIn(DC, text)
        self.assertIn("Verified", self.h(self.code()))
        rec = json.loads((self.home / "owner-link" / "verified.json").read_text(encoding="utf-8"))
        self.assertEqual((rec["userId"], rec["chatId"], rec["via"]), (DU, DC, "telegram_owner_dm"))
        self.assertNotIn("codeHash", json.loads((self.home / "owner-link" / "pending.json").read_text()))
        self.assertIn("verified", self.sent[-1][1])

    def test_code_is_not_stored_in_clear(self):
        self.h("link owner")
        raw = (self.home / "owner-link" / "pending.json").read_text(encoding="utf-8")
        self.assertNotIn(self.code().replace("-", ""), raw)

    def test_wrong_code_expiry_and_attempt_limit(self):
        self.h("link owner")
        self.assertEqual(self.h("AAAA-AAAA"), "That code doesn't match.")
        for _ in range(3):
            self.h("AAAA-AAAA")
        self.assertIn("Too many wrong codes", self.h("AAAA-AAAA"))
        self.assertIsNone(self.h(self.code()))                  # challenge gone: an ordinary message now
        self.h("link owner", now=2000.0)
        self.assertIn("expired", self.h(self.code(), now=2000.0 + 601))
        self.assertFalse((self.home / "owner-link" / "verified.json").exists())

    def test_rate_limit(self):
        for i in range(3):
            self.h("link owner", now=1000.0 + i)
        self.assertIn("Too many link requests", self.h("link owner", now=1010.0))
        self.assertEqual(len(self.sent), 3)

    def test_code_from_another_dm_or_server_never_verifies(self):
        self.h("link owner")
        code = self.code()
        self.assertIsNone(self.h(code, source=dm(user_id="200000000000000009", chat_id="300000000000000009")))
        self.assertIsNone(self.h(code, source=dm(chat_type="group", guild_id="5")))
        self.assertIsNone(self.h("link owner", source=dm(chat_type="group", guild_id="5")))
        self.assertIsNone(self.h("link owner", platform="telegram"))
        self.assertFalse((self.home / "owner-link" / "verified.json").exists())

    def test_ordinary_messages_and_missing_settings_pass_through(self):
        self.assertIsNone(self.h("hey, how are you?"))
        self.assertIsNone(self.h("link owner", settings=None))
        self.assertEqual(self.sent, [])

    def test_telegram_failure_means_no_challenge(self):
        self.send = lambda chat, text: False
        self.assertIn("couldn't reach", self.h("link owner"))
        self.assertNotIn("codeHash", json.loads((self.home / "owner-link" / "pending.json").read_text()))

    def test_route_turn_returns_a_ready_non_owner_reply_and_never_on_owner_channels(self):
        gi = self.gi
        gi._owner_link.telegram_sender = lambda home: self.send
        gi._config._hermes_home = lambda: self.home
        gi._route_turn_impl = lambda **kw: None
        gi._canonical_memory.load_settings = lambda home, **kw: UNVERIFIED
        gi._canonical_memory.turn_note = lambda *a, **kw: None
        gi._platform_name = lambda s: "discord"
        ctx = types.SimpleNamespace(source=dm(), session_key="k", message="link owner")
        r = gi.route_turn(runner=None, ctx=ctx, model="m", runtime_kwargs={}, turn_route={}, combined_ephemeral="")
        self.assertIn("one-time code", r["final_response"])
        self.assertIs(r["owner_memory"], False)
        gi._canonical_memory.load_settings = lambda home, **kw: VERIFIED          # already an owner channel
        r = gi.route_turn(runner=None, ctx=ctx, model="m", runtime_kwargs={}, turn_route={}, combined_ephemeral="")
        self.assertNotIn("final_response", r)
        self.assertIs(r["owner_memory"], True)


if __name__ == "__main__":
    unittest.main()
