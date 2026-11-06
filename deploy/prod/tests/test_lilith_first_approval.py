"""/memory approve writes LILITH OS first (patched hermes_cli/write_approval_commands.py), end to end against the real
Core API handler on a throwaway database. Hermes' own pending store and MemoryStore are small stand-ins. TEST_ONLY."""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services/core-api"))
import app  # noqa: E402
from fastapi import HTTPException  # noqa: E402

PENDING = {}
APPLIED = []
APPLY_OK = {"value": True}


def _install_stubs():
    wa = types.ModuleType("tools.write_approval")
    wa.MEMORY, wa.SKILLS = "memory", "skills"
    wa.list_pending = lambda sub: list(PENDING.values())
    wa.get_pending = lambda sub, pid: PENDING.get(pid)
    wa.discard_pending = lambda sub, pid: PENDING.pop(pid, None) is not None
    wa.write_approval_enabled = lambda sub: True
    mt = types.ModuleType("tools.memory_tool")

    def apply_memory_pending(payload, store):
        if not APPLY_OK["value"]:
            return {"success": False, "error": "disk full"}
        APPLIED.append(payload)
        return {"success": True}
    mt.apply_memory_pending = apply_memory_pending
    tools = types.ModuleType("tools")
    tools.write_approval, tools.memory_tool = wa, mt
    sys.modules.update({"tools": tools, "tools.write_approval": wa, "tools.memory_tool": mt})


_install_stubs()
spec = importlib.util.spec_from_file_location("wac", ROOT / "deploy/prod/hermes_cli/write_approval_commands.py")
WAC = importlib.util.module_from_spec(spec)
spec.loader.exec_module(WAC)
spec2 = importlib.util.spec_from_file_location("omr", ROOT / "deploy/prod/hermes_scripts/owner_memory_review.py")
OMR = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(OMR)


class LilithFirstApprovalTest(unittest.TestCase):
    def setUp(self):
        PENDING.clear()
        APPLIED.clear()
        APPLY_OK["value"] = True
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        fd, db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(db) and os.unlink(db))
        app.DB = Path(db)
        app._world_schema_ready = False
        env = mock.patch.dict(os.environ, {"LILITH_OS_WRITE_AUTH": "open-acknowledged", "HERMES_HOME": str(self.tmp)})
        env.start()
        self.addCleanup(env.stop)
        (self.tmp / "memories").mkdir()
        (self.tmp / "memories" / "USER.md").write_text("User enjoys PlayStation.\n§\nHand-written: likes rain.",
                                                       encoding="utf-8")
        self.down = False
        post = mock.patch.object(WAC, "_lilith_post", self.post)
        post.start()
        self.addCleanup(post.stop)

    def post(self, body):                        # the real handler, with the HTTP layer's error mapping
        if self.down:
            raise WAC._LilithNotSaved("LILITH OS unreachable (URLError)")
        try:
            return app.post_owner_memory(body, x_lilith_os_write=None)
        except HTTPException as exc:
            raise WAC._LilithNotSaved("LILITH OS refused (%s)" % exc.status_code) from exc

    def stage(self, pid, payload):
        PENDING[pid] = {"id": pid, "summary": "s", "payload": payload}

    def approve(self, pid):
        return WAC._approve("memory", [pid], memory_store=object())

    def export(self, sup=0):
        return {e["text"]: e for e in app.get_owner_memory(include_superseded=sup)["entries"]}

    def test_ids_match_the_core_api(self):
        for store, text in (("user", "User owns a bike."), ("memory", "  Weekly  planning\non Mondays ")):
            self.assertEqual(WAC.lilith_memory_id(store, text), app.owner_memory_id(store, text))

    def test_approve_writes_lilith_os_first_then_hermes(self):
        self.stage("p1", {"action": "add", "target": "user", "content": "User owns a bike."})
        out = self.approve("p1")
        self.assertIn("Approved 1 memory write(s).", out)
        e = self.export()["User owns a bike."]
        self.assertEqual((e["provenance"][0]["kind"], e["provenance"][0]["proposal_id"]), ("OWNER_APPROVED_PROPOSAL", "p1"))
        self.assertTrue(e["provenance"][0]["approved_at"])
        self.assertEqual(len(APPLIED), 1)                                           # Hermes projection applied
        self.assertNotIn("p1", PENDING)

    def test_lilith_down_keeps_it_pending_and_says_so(self):
        self.down = True
        self.stage("p2", {"action": "add", "target": "user", "content": "User owns a bike."})
        out = self.approve("p2")
        self.assertIn("Approved 0 memory write(s).", out)
        self.assertIn("not saved", out)
        self.assertIn("still pending", out)
        self.assertIn("p2", PENDING)                                                # safe to retry
        self.assertEqual(APPLIED, [])                                               # Hermes not touched
        self.down = False
        self.assertIn("Approved 1 memory write(s).", self.approve("p2"))           # retry succeeds
        self.assertEqual(len(self.export()), 1)

    def test_retry_after_partial_failure_is_idempotent(self):
        self.stage("p3", {"action": "add", "target": "user", "content": "User owns a bike."})
        WAC.lilith_record_approval(PENDING["p3"], post=self.post)                   # recorded, then e.g. a crash
        self.approve("p3")                                                           # the owner approves again
        e = self.export()["User owns a bike."]
        self.assertEqual(len(e["provenance"]), 1)                                   # one memory, one evidence row

    def test_hermes_failure_after_lilith_success_is_not_lost(self):
        APPLY_OK["value"] = False
        self.stage("p4", {"action": "add", "target": "user", "content": "User owns a bike."})
        out = self.approve("p4")
        self.assertIn("saved in LILITH OS; the Hermes copy will be repaired", out)
        self.assertIn("User owns a bike.", self.export())
        self.assertNotIn("p4", PENDING)

    def test_replace_supersedes_even_an_unrecorded_hand_written_entry(self):
        self.stage("p5", {"action": "replace", "target": "user", "old_text": "likes rain",
                          "content": "User likes sunny days."})
        self.assertIn("Approved 1", self.approve("p5"))
        hist = self.export(sup=1)
        self.assertEqual(hist["Hand-written: likes rain."]["lifecycle_state"], "SUPERSEDED")
        self.assertEqual(hist["Hand-written: likes rain."]["provenance"][0]["kind"], "HERMES_PREEXISTING_IMPORT")
        self.assertEqual(hist["User likes sunny days."]["lifecycle_state"], "ACTIVE")

    def test_remove_retracts_and_ambiguous_target_is_refused(self):
        self.stage("p6", {"action": "add", "target": "user", "content": "User enjoys PlayStation."})
        self.approve("p6")
        self.stage("p7", {"action": "remove", "target": "user", "old_text": "PlayStation"})
        self.assertIn("Approved 1", self.approve("p7"))
        self.assertNotIn("User enjoys PlayStation.", self.export())
        self.stage("p8", {"action": "remove", "target": "user", "old_text": "e"})   # matches several entries
        out = self.approve("p8")
        self.assertIn("ambiguous", out)
        self.assertIn("p8", PENDING)

    def test_batch_is_recorded_operation_by_operation(self):
        self.stage("p9", {"action": "batch", "target": "user", "operations": [
            {"action": "add", "content": "User owns a bike."},
            {"action": "add", "target": "memory", "content": "Weekly planning on Mondays."}]})
        self.approve("p9")
        cur = self.export()
        self.assertEqual((cur["User owns a bike."]["store"], cur["Weekly planning on Mondays."]["store"]), ("user", "memory"))

    def test_reject_is_logged_and_never_proposed_again(self):
        self.stage("r1", {"action": "add", "target": "user", "content": "User calls Sundays Quiet Days."})
        out = WAC._reject("memory", ["r1"])
        self.assertIn("Rejected", out)
        self.assertEqual(self.export(), {})                                         # nothing recorded
        self.assertIn("- User calls Sundays Quiet Days.", OMR.rejected(self.tmp))  # immediately, no snapshot needed


if __name__ == "__main__":
    unittest.main()
