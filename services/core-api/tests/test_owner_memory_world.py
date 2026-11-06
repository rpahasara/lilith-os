"""Owner-approved memories in the World Model (LILITH OS owns them; Hermes files are not needed). TEST_ONLY.

Handlers are called directly (no httpx), on a throwaway database.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
from fastapi import HTTPException  # noqa: E402

TOKEN = "TEST_ONLY" + "y" * 32
IMPORT = {"kind": "HERMES_PREEXISTING_IMPORT", "note": "imported from Hermes USER.md"}


def approved(pid, at="2026-11-06T19:37:52Z"):
    return {"kind": "OWNER_APPROVED_PROPOSAL", "proposal_id": pid, "approved_at": at, "channel": "telegram_owner_dm"}


class OwnerMemoryWorldTest(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        app.DB = Path(path)
        app._world_schema_ready = False
        app._l18_schema_ready = False
        patch = mock.patch.dict(os.environ, {"LILITH_OS_WRITE_AUTH": "enforced", "LILITH_OS_WRITE_TOKEN": TOKEN})
        patch.start()
        self.addCleanup(patch.stop)

    def post(self, body, cred=TOKEN):
        return app.post_owner_memory(body, x_lilith_os_write=cred)

    def export(self, include_superseded=0):
        return app.get_owner_memory(include_superseded=include_superseded)

    def test_write_needs_the_write_credential(self):
        for cred in (None, "wrong"):
            with self.assertRaises(HTTPException) as caught:
                self.post({"store": "user", "text": "x", "provenance": IMPORT}, cred=cred)
            self.assertEqual(caught.exception.status_code, 401)
        self.assertEqual(self.export()["count"], 0)

    def test_import_is_idempotent_and_recoverable_without_hermes_files(self):
        r1 = self.post({"store": "user", "text": "User enjoys PlayStation.", "provenance": IMPORT})
        r2 = self.post({"store": "user", "text": "User  enjoys PlayStation. ", "provenance": IMPORT})   # same memory
        self.assertEqual(r1["entry_id"], r2["entry_id"])
        self.assertEqual((r1["action"], r2["action"]), ("created", "noop"))
        out = self.export()
        self.assertEqual(out["count"], 1)
        e = out["entries"][0]
        self.assertEqual((e["text"], e["store"], e["lifecycle_state"], e["epistemic_state"]),
                         ("User enjoys PlayStation.", "user", "ACTIVE", "USER_ASSERTED"))
        self.assertEqual(len(e["provenance"]), 1)                                   # no duplicate evidence
        self.assertEqual(e["provenance"][0]["kind"], "HERMES_PREEXISTING_IMPORT")
        self.assertIsNone(e["provenance"][0]["approved_at"])                         # no invented timestamp

    def test_owner_approved_replace_supersedes_and_keeps_history(self):
        old = self.post({"store": "user", "text": "User prefers to be called Sara.", "provenance": IMPORT})["entry_id"]
        new = self.post({"store": "user", "text": "User's real name is Ravindu; friends call him Sara.",
                         "provenance": approved("6e64c725", "2026-11-06T18:32:52Z"), "supersedes": [old]})
        self.assertEqual(new["superseded"], [old])
        current = self.export()
        self.assertEqual([e["text"] for e in current["entries"]], ["User's real name is Ravindu; friends call him Sara."])
        history = {e["entry_id"]: e for e in self.export(include_superseded=1)["entries"]}
        self.assertEqual(history[old]["lifecycle_state"], "SUPERSEDED")
        self.assertIn("owner_approved_replace", history[old]["provenance"][-1]["note"])
        self.assertEqual(history[new["entry_id"]]["provenance"][0]["proposal_id"], "6e64c725")
        again = self.post({"store": "user", "text": "User's real name is Ravindu; friends call him Sara.",
                           "provenance": approved("6e64c725", "2026-11-06T18:32:52Z"), "supersedes": [old]})
        self.assertEqual((again["action"], again["superseded"]), ("noop", []))      # idempotent replay

    def test_contradictions_are_kept_not_overwritten(self):
        a = self.post({"store": "user", "text": "User drinks coffee.", "provenance": IMPORT})["entry_id"]
        b = self.post({"store": "user", "text": "User drinks tea.", "provenance": approved("p2")})["entry_id"]
        self.assertNotEqual(a, b)
        self.assertEqual(self.export()["count"], 2)                                  # both visible, nothing silently lost

    def test_only_explicit_owner_approval_retracts_or_supersedes(self):
        a = self.post({"store": "memory", "text": "Weekly planning on Mondays.", "provenance": IMPORT})["entry_id"]
        with self.assertRaises(HTTPException):
            self.post({"action": "retract", "store": "memory", "entry_id": a, "provenance": IMPORT})
        with self.assertRaises(HTTPException):
            self.post({"store": "memory", "text": "x", "provenance": IMPORT, "supersedes": [a]})
        r = self.post({"action": "retract", "store": "memory", "entry_id": a, "provenance": approved("rm1")})
        self.assertEqual(r["action"], "retracted")
        self.assertEqual(self.export()["count"], 0)
        self.assertEqual(self.export(include_superseded=1)["entries"][0]["lifecycle_state"], "SUPERSEDED")

    def test_validation(self):
        bad = [{"store": "x", "text": "t", "provenance": IMPORT},
               {"store": "user", "text": "", "provenance": IMPORT},
               {"store": "user", "text": "t" * 2001, "provenance": IMPORT},
               {"store": "user", "text": "t", "provenance": {"kind": "MADE_UP"}},
               {"store": "user", "text": "t", "provenance": {"kind": "OWNER_APPROVED_PROPOSAL"}},       # no proposal id
               {"store": "user", "text": "t", "provenance": dict(IMPORT, proposal_id="p")},
               {"store": "user", "text": "t", "provenance": dict(IMPORT, approved_at="2026-11-06T00:00:00Z")},
               {"store": "user", "text": "t", "provenance": approved("p", "yesterday")},
               {"store": "user", "text": "t", "provenance": approved("p"), "supersedes": ["om_" + "0" * 20]}]
        for body in bad:
            with self.subTest(body=body):
                with self.assertRaises(HTTPException):
                    self.post(body)
        self.assertEqual(self.export()["count"], 0)

    def test_owner_memories_stay_out_of_the_default_world_overview(self):
        self.post({"store": "user", "text": "User enjoys PlayStation.", "provenance": IMPORT})
        overview = app.os_world()
        self.assertFalse([b for b in overview["beliefs"] if b["entity_type"] == "owner"])
        explicit = app.os_world(entity_type="owner")
        self.assertEqual(len(explicit["beliefs"]), 1)


if __name__ == "__main__":
    unittest.main()
