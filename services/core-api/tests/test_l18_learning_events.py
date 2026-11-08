"""L18 learning events for owner memories: written with every World Model owner-memory change, plus runtime
PROPOSED / REJECTED events. TEST_ONLY; throwaway DB; handlers called directly."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
from fastapi import HTTPException  # noqa: E402

TOKEN = "TEST_ONLY" + "z" * 32
IMPORT = {"kind": "HERMES_PREEXISTING_IMPORT"}


def approved(pid):
    return {"kind": "OWNER_APPROVED_PROPOSAL", "proposal_id": pid, "approved_at": "2026-11-06T20:40:07Z",
            "channel": "telegram_owner_dm"}


class L18EventsTest(unittest.TestCase):
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

    def mem(self, body):
        return app.post_owner_memory(body, x_lilith_os_write=TOKEN)

    def ev(self, body, cred=TOKEN):
        return app.post_learning_events(body, x_lilith_os_write=cred)

    def events(self, kind=None):
        return [(e["kind"], e["proposal_id"], e["text"] or e["entry_id"]) for e in app.get_learning_events(kind=kind)["events"]]

    def test_every_owner_memory_change_is_a_learning_event(self):
        old = self.mem({"store": "user", "text": "User likes rain.", "provenance": IMPORT})["entry_id"]
        new = self.mem({"store": "user", "text": "User likes sunny days.", "provenance": approved("p1"),
                        "supersedes": [old]})["entry_id"]
        self.mem({"action": "retract", "store": "user", "entry_id": new, "provenance": approved("p2")})
        self.assertEqual(self.events(), [("IMPORTED", None, "User likes rain."),
                                         ("APPROVED", "p1", "User likes sunny days."),
                                         ("SUPERSEDED", "p1", old),
                                         ("RETRACTED", "p2", new)])
        e = app.get_learning_events(kind="APPROVED")["events"][0]
        self.assertEqual((e["at"], e["source"], e["entry_id"]), ("2026-11-06T20:40:07Z", "telegram_owner_dm", new))

    def test_replays_create_no_duplicate_events(self):
        body = {"store": "user", "text": "User owns a bike.", "provenance": approved("p3")}
        self.mem(body)
        self.mem(body)
        self.ev({"kind": "PROPOSED", "proposal_id": "p3", "items": [{"store": "user", "action": "add", "text": "User owns a bike."}]})
        self.ev({"kind": "PROPOSED", "proposal_id": "p3", "items": [{"store": "user", "action": "add", "text": "User owns a bike."}]})
        self.assertEqual(sorted(k for k, _, _ in self.events()), ["APPROVED", "PROPOSED"])

    def test_runtime_events_proposed_and_rejected(self):
        self.ev({"kind": "PROPOSED", "proposal_id": "r1", "source": "hermes", "items": [
            {"store": "user", "action": "add", "text": "User calls Sundays Quiet Days."},
            {"store": "memory", "action": "add", "text": "Weekly planning on Mondays."}]})
        self.ev({"kind": "REJECTED", "proposal_id": "r1", "items": [
            {"store": "user", "action": "add", "text": "User calls Sundays Quiet Days."}]})
        self.assertEqual(self.events("REJECTED"), [("REJECTED", "r1", "User calls Sundays Quiet Days.")])
        self.assertEqual(len(self.events("PROPOSED")), 2)
        self.assertEqual(app.get_owner_memory()["count"], 0)                    # a rejection never becomes a belief

    def test_runtime_cannot_claim_approval_and_needs_the_credential(self):
        with self.assertRaises(HTTPException) as caught:
            self.ev({"kind": "PROPOSED", "proposal_id": "x", "items": [{"store": "user", "action": "add", "text": "t"}]},
                    cred="wrong")
        self.assertEqual(caught.exception.status_code, 401)
        bad = [{"kind": "APPROVED", "proposal_id": "x", "items": [{"store": "user", "action": "add", "text": "t"}]},
               {"kind": "PROPOSED", "items": [{"store": "user", "action": "add", "text": "t"}]},
               {"kind": "PROPOSED", "proposal_id": "x", "items": []},
               {"kind": "PROPOSED", "proposal_id": "x", "items": [{"store": "soul", "action": "add", "text": "t"}]},
               {"kind": "PROPOSED", "proposal_id": "x", "items": [{"store": "user", "action": "drop", "text": "t"}]},
               {"kind": "PROPOSED", "proposal_id": "x", "items": [{"store": "user", "action": "add", "text": ""}]}]
        for body in bad:
            with self.subTest(body=body):
                with self.assertRaises(HTTPException):
                    self.ev(body)
        self.assertEqual(self.events(), [])


if __name__ == "__main__":
    unittest.main()
