"""PROD canonical-memory router seam (PREPARED; offline; synthetic ids and data only)."""

import hashlib
import importlib
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

O = Path(__file__).resolve().parents[1]
ROOT = O.parents[3]
OWNER = "100200300"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_package():
    tmp = Path(tempfile.mkdtemp())
    pkg = tmp / "lilith_router"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    for name in ("canonical_memory.py", "lilith_memory_context.py"):
        shutil.copy(O / name, pkg / name)
    sys.path.insert(0, str(tmp))
    for mod in [m for m in sys.modules if m == "lilith_router" or m.startswith("lilith_router.")]:
        del sys.modules[mod]
    cm = importlib.import_module("lilith_router.canonical_memory")
    return tmp, cm


def src(**kw):
    return types.SimpleNamespace(**{"user_id": None, "chat_id": None, "chat_type": "dm", **kw})


PERSONAL = {"kind": "relationship-origin", "value": "TEST_ONLY origin.", "epistemicBasis": "USER_ASSERTED",
            "sensitivity": "OWNER_PERSONAL", "admissionId": "madm.t", "revisionId": "mrev.t"}
PROJECT = {"kind": "codename", "value": "SYNTH-ORCHID", "epistemicBasis": "USER_ASSERTED",
           "sensitivity": "PROJECT_FACT", "admissionId": "madm.c", "revisionId": "mrev.c"}


def service(granted_channels=("lilith_os", "telegram_owner_dm")):
    """Stand-in for the root service: personal memory only for a granted owner channel."""
    calls = []

    def request(_socket, *, channel, session, timeout):
        calls.append(channel)
        owner = channel in granted_channels
        mem = [PROJECT] + ([PERSONAL] if owner else [])
        return {"status": "CONTEXT", "schema": "LilithCanonicalMemoryContextV1", "reason": None, "memories": mem,
                "ownerChannel": owner}
    return request, calls


class SeamTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.cm = load_package()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(sys.path.remove, str(self.tmp))
        self.cm._built_with.clear()
        self.settings = {"schemaVersion": 1, "enabled": True, "ownerTelegramUserIds": [OWNER]}

    def test_channel_isolation(self):
        ch = self.cm.owner_channel
        self.assertEqual(ch("lilith_os", src(), []), "lilith_os")
        self.assertEqual(ch("telegram", src(user_id=OWNER, chat_id=OWNER, chat_type="private"), [OWNER]),
                         "telegram_owner_dm")
        self.assertEqual(ch("telegram", src(user_id=OWNER, chat_id=OWNER, chat_type="dm"), [OWNER]), "telegram_owner_dm")
        for platform, s in (("telegram", src(user_id=OWNER, chat_id="-100500", chat_type="group")),   # owner in a group
                            ("telegram", src(user_id=OWNER, chat_id="-100500", chat_type="dm")),      # chat != user
                            ("telegram", src(user_id="999", chat_id="999", chat_type="private")),     # someone else
                            ("telegram", src(user_id=OWNER, chat_id=OWNER, chat_type="channel")),
                            ("discord", src(user_id=OWNER, chat_id=OWNER, chat_type="dm")),           # Discord, even a DM
                            ("slack", src())):
            with self.subTest(platform=platform, source=vars(s)):
                self.assertEqual(ch(platform, s, [OWNER]), "public")
        self.assertEqual(ch("telegram", src(user_id=OWNER, chat_id=OWNER, chat_type="private"), []), "public")

    def test_personal_memory_reaches_only_owner_channels(self):
        request, calls = service()
        owner_dm = self.cm.turn_note(self.settings, "telegram", src(user_id=OWNER, chat_id=OWNER, chat_type="private"),
                                     "agent:main:telegram:dm:" + OWNER, request=request)
        self.assertIn("TEST_ONLY origin.", owner_dm)
        discord = self.cm.turn_note(self.settings, "discord", src(user_id=OWNER, chat_id="55", chat_type="group"),
                                    "agent:main:discord:group:55", request=request)
        self.assertNotIn("TEST_ONLY origin.", discord)
        self.assertIn("SYNTH-ORCHID", discord)
        self.assertEqual(calls, ["telegram_owner_dm", "public"])

        def lying(_s, *, channel, session, timeout):      # even a service bug saying ownerChannel on public
            return {**request(_s, channel="lilith_os", session=session, timeout=timeout)}
        self.assertNotIn("TEST_ONLY origin.", self.cm.turn_note(self.settings, "discord", src(), "d:1", request=lying))

    def test_off_unavailable_or_broken_means_no_note(self):
        request, calls = service()
        self.assertIsNone(self.cm.turn_note(None, "lilith_os", src(), "s", request=request))
        self.assertEqual(calls, [])                                          # off: the service is not even asked

        def down(*_a, **_k):
            raise OSError("no socket")
        self.assertIsNone(self.cm.turn_note(self.settings, "lilith_os", src(), "s", request=down))
        unavailable = lambda *_a, **_k: {"status": "UNAVAILABLE", "schema": "LilithCanonicalMemoryContextV1",  # noqa: E731
                                         "reason": "PRIVACY_FRESHNESS_NOT_READY:BOOT", "memories": []}
        self.assertIsNone(self.cm.turn_note(self.settings, "lilith_os", src(), "s", request=unavailable))
        self.assertIsNone(self.cm.current_note())

    @unittest.skipUnless(os.name == "posix", "owner and mode checks are POSIX")
    def test_settings_file(self):
        home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home, True)
        (home / "lilith_router").mkdir()
        f = home / "lilith_router" / "canonical_memory.json"
        uid = os.getuid() if hasattr(os, "getuid") else 0
        self.assertIsNone(self.cm.load_settings(home, owner_uid=uid))        # absent: off
        f.write_text(json.dumps(self.settings))
        if hasattr(os, "chmod"):
            os.chmod(f, 0o644)
        self.assertEqual(self.cm.load_settings(home, owner_uid=uid), self.settings)
        for bad in ({**self.settings, "enabled": False}, {**self.settings, "ownerTelegramUserIds": ["@name"]},
                    {**self.settings, "extra": 1}, {**self.settings, "schemaVersion": 2}):
            with self.subTest(bad=bad):
                f.write_text(json.dumps(bad))
                self.assertIsNone(self.cm.load_settings(home, owner_uid=uid))
        if os.name == "posix":
            f.write_text(json.dumps(self.settings))
            os.chmod(f, 0o666)
            self.assertIsNone(self.cm.load_settings(home, owner_uid=uid))    # writable by others
            os.chmod(f, 0o644)
            self.assertIsNone(self.cm.load_settings(home, owner_uid=uid + 1))  # not root's

    def test_merge_on_every_route_and_rebuild_once_when_the_note_changes(self):
        m = self.cm.merge
        agent = object()
        # first turn, no cached agent: the main agent is built with the note; no needless rebuild
        out = m(None, note="NOTE-A", combined_ephemeral="SOUL-EXTRA", session_key="s", cached_agent=None)
        self.assertEqual(out, {"combined_ephemeral": "SOUL-EXTRA\n\nNOTE-A"})
        # next turn, same note, cached agent: reuse it
        self.assertNotIn("force_rebuild", m(None, note="NOTE-A", combined_ephemeral="", session_key="s",
                                            cached_agent=agent))
        # a lane's own ephemeral keeps the lane and gains the note; its own rebuild flag survives
        lane = m({"combined_ephemeral": "GROUNDED", "force_rebuild": True, "mode": "social"}, note="NOTE-A",
                 combined_ephemeral="", session_key="s", cached_agent=agent)
        self.assertEqual((lane["combined_ephemeral"], lane["force_rebuild"], lane["mode"]),
                         ("GROUNDED\n\nNOTE-A", True, "social"))
        # FORGET / expired grant: the note disappears -> rebuilt once without it, then quiet again
        gone = m(None, note=None, combined_ephemeral="SOUL-EXTRA", session_key="s", cached_agent=agent)
        self.assertEqual(gone, {"combined_ephemeral": "SOUL-EXTRA", "force_rebuild": True})
        self.assertIsNone(m(None, note=None, combined_ephemeral="X", session_key="s", cached_agent=agent))
        # a changed note also rebuilds
        m(None, note="NOTE-A", combined_ephemeral="", session_key="t", cached_agent=None)
        self.assertTrue(m(None, note="NOTE-B", combined_ephemeral="", session_key="t", cached_agent=agent)["force_rebuild"])
        # ready replies (Reasoning/Planning/Ethics, lean) are left alone
        ready = {"final_response": "done", "mode": "reasoning"}
        self.assertIs(m(ready, note="NOTE-A", combined_ephemeral="", session_key="s", cached_agent=agent), ready)
        # feature off from the start: byte-for-byte the router's own result
        self.assertIsNone(m(None, note=None, combined_ephemeral="X", session_key="u", cached_agent=agent))


class PatchTests(unittest.TestCase):
    def test_the_router_patch_is_small_and_on_the_deployed_prod_file(self):
        self.assertTrue(sha(O / "base/gateway_integration.py").startswith("99fe90649e316ef9"))
        patch = (O / "gateway_integration.patch").read_text(encoding="utf-8")
        self.assertEqual(patch.count("\n@@ "), 4)   # import, wrapper (2), lean
        new = (O / "gateway_integration.py").read_text(encoding="utf-8")
        self.assertIn("from . import canonical_memory as _canonical_memory", new)
        self.assertIn("_canonical_memory.current_note()", new)
        compile(new, "gateway_integration.py", "exec")
        for name in ("canonical_memory.py", "lilith_memory_context.py"):
            compile((O / name).read_text(encoding="utf-8"), name, "exec")

    def test_one_copy_of_the_renderer(self):
        self.assertEqual((O / "lilith_memory_context.py").read_bytes(),
                         (ROOT / "services/owner-memory-control/lilith_owner_memory/hermes_memory_context.py").read_bytes())

    def test_the_module_writes_nothing(self):
        source = (O / "canonical_memory.py").read_text(encoding="utf-8")
        for forbidden in ("open(", "write", "sqlite3", "subprocess", "os.remove", "unlink"):
            self.assertFalse(forbidden in source.replace("read_text", ""), forbidden)


if __name__ == "__main__":
    unittest.main()
