"""PROD canonical-memory router seam (PREPARED; offline; synthetic ids and data only)."""

import hashlib
import importlib
import json
import os
import shutil
import subprocess
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

    def test_non_owner_turns_get_no_canonical_memory_even_project_facts(self):
        # Regression (PROD Gate 7.2, 2026-11-06): the codename is PROJECT_FACT, not OWNER_PERSONAL, so the service
        # returns it to `public`. Owner decision: canonical memory reaches owner channels only, so a public turn
        # must not even ask the service, and must never carry a note.
        request, calls = service()
        cases = [
            ("telegram", src(user_id=OWNER, chat_id="-1001", chat_type="group"), "agent:main:telegram:group:-1001"),
            ("telegram", src(user_id=OWNER, chat_id="-1001", chat_type="supergroup"), "agent:main:telegram:group:-1001"),
            ("telegram", src(user_id="42", chat_id="42", chat_type="dm"), "agent:main:telegram:dm:42"),
            ("telegram", src(user_id=OWNER, chat_id="42", chat_type="dm"), "agent:main:telegram:dm:42"),
            ("discord", src(user_id=OWNER, chat_id=OWNER, chat_type="dm"), "agent:main:discord:dm:" + OWNER),
            ("whatsapp", src(user_id=OWNER, chat_id=OWNER, chat_type="dm"), "agent:main:whatsapp:dm:" + OWNER),
        ]
        for platform, s, key in cases:
            with self.subTest(platform=platform, source=vars(s)):
                self.assertIsNone(self.cm.turn_note(self.settings, platform, s, key, request=request))
                self.assertIsNone(self.cm.current_note())
        self.assertEqual(calls, [])
        owner = self.cm.turn_note(self.settings, "telegram", src(user_id=OWNER, chat_id=OWNER, chat_type="dm"),
                                  "agent:main:telegram:dm:" + OWNER, request=request)
        self.assertIn("SYNTH-ORCHID", owner)                 # the owner DM still gets the project memory
        self.assertEqual(calls, ["telegram_owner_dm"])

    def test_personal_memory_reaches_only_owner_channels(self):
        request, calls = service()
        owner_dm = self.cm.turn_note(self.settings, "telegram", src(user_id=OWNER, chat_id=OWNER, chat_type="private"),
                                     "agent:main:telegram:dm:" + OWNER, request=request)
        self.assertIn("TEST_ONLY origin.", owner_dm)
        discord = self.cm.turn_note(self.settings, "discord", src(user_id=OWNER, chat_id="55", chat_type="group"),
                                    "agent:main:discord:group:55", request=request)
        self.assertIsNone(discord)                        # owner-only: public gets no canonical memory at all
        self.assertEqual(calls, ["telegram_owner_dm"])    # and the service is not even asked

        def lying(_s, *, channel, session, timeout):      # even a service bug saying ownerChannel on public
            return {**request(_s, channel="lilith_os", session=session, timeout=timeout)}
        self.assertIsNone(self.cm.turn_note(self.settings, "discord", src(), "d:1", request=lying))

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
        # R3c: rebased onto the router PROD runs since the T4 wording fix (audit run 2, 2026-11-05: pin MATCH).
        self.assertEqual(sha(O / "base/gateway_integration.py"),
                         "4db8bb58da3fbdef80fb550c74709bb3ea62c605afadec56aa96b28d2568ca8b")
        patch = (O / "gateway_integration.patch").read_text(encoding="utf-8")
        self.assertEqual(patch.count("\n@@ "), 4)   # import, wrapper (2), lean
        new = (O / "gateway_integration.py").read_text(encoding="utf-8")
        self.assertIn("from . import canonical_memory as _canonical_memory", new)
        self.assertIn("_canonical_memory.current_note()", new)
        compile(new, "gateway_integration.py", "exec")
        for name in ("canonical_memory.py", "lilith_memory_context.py"):
            compile((O / name).read_text(encoding="utf-8"), name, "exec")

    def test_the_patch_applies_to_the_t4_base_and_keeps_every_route(self):
        patch_bin = shutil.which("patch")
        if patch_bin is not None:
            work = Path(tempfile.mkdtemp())
            shutil.copy(O / "base/gateway_integration.py", work / "g.py")
            with open(O / "gateway_integration.patch", "rb") as f:
                done = subprocess.run([patch_bin, "-s", "-p0", str(work / "g.py")], stdin=f, capture_output=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual((work / "g.py").read_bytes(), (O / "gateway_integration.py").read_bytes())
            shutil.rmtree(work)
        text = (O / "gateway_integration.py").read_text(encoding="utf-8")
        base = (O / "base/gateway_integration.py").read_text(encoding="utf-8")
        for kept in ("_SELF_STATUS_RE = re.compile(", "def _self_status_route(", "SELF_STATUS_NOTE = ",
                     '"native_self_status"', '"native_recall"', "_social_lean", "_world_context."):
            self.assertEqual(text.count(kept), base.count(kept), kept)         # T4 fixes and every route preserved
        self.assertGreater(base.count('"native_self_status"'), 0)

    def test_the_self_status_route_keeps_its_note_and_gains_canonical_memory_only_when_on(self):
        _tmp, cm = load_package()
        m = cm.merge
        result = {"turn_route": {"model": "gpt-5.6-sol"}, "combined_ephemeral": "BASE\n\nSELF_STATUS_NOTE TEXT",
                  "force_rebuild": True, "mode": "social"}
        self.assertIs(m(result, note=None, combined_ephemeral="BASE", session_key="ss-off", cached_agent=None), result)
        on = m(result, note="NOTE-A", combined_ephemeral="BASE", session_key="ss-on", cached_agent=None)
        self.assertTrue(on["combined_ephemeral"].startswith("BASE\n\nSELF_STATUS_NOTE TEXT"))
        self.assertIn("NOTE-A", on["combined_ephemeral"])
        self.assertTrue(on["force_rebuild"])
        self.assertEqual(on["mode"], "social")

    def test_one_copy_of_the_renderer(self):
        self.assertEqual((O / "lilith_memory_context.py").read_bytes(),
                         (ROOT / "services/owner-memory-control/lilith_owner_memory/hermes_memory_context.py").read_bytes())

    def test_the_module_writes_nothing(self):
        source = (O / "canonical_memory.py").read_text(encoding="utf-8")
        for forbidden in ("open(", "write", "sqlite3", "subprocess", "os.remove", "unlink"):
            self.assertFalse(forbidden in source.replace("read_text", ""), forbidden)


if __name__ == "__main__":
    unittest.main()
