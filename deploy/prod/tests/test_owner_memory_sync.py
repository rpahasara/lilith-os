"""Hermes -> LILITH OS World Model sync, end to end against the real Core API handler (throwaway DB). TEST_ONLY."""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services/core-api"))
import app  # noqa: E402

spec = importlib.util.spec_from_file_location("oms", ROOT / "deploy/prod/hermes_scripts/owner_memory_sync.py")
OMS = importlib.util.module_from_spec(spec)
spec.loader.exec_module(OMS)

OLD_SARA = "User prefers to be called Sara; he is a boy and uses he/him language."
NAME = OMS.BOOTSTRAP[1]["text"]
PREF = OMS.BOOTSTRAP[2]["text"]
PRE = ["Style: casual, concise.", "Autonomy: draft first.", "DevOps/Cloud Engineer.",
       "User enjoys PlayStation.", "User's Google Calendar timezone is Asia/Colombo."]


class FakeStore:
    """Hermes MemoryStore stand-in: add / remove whole entries in USER.md / MEMORY.md."""

    def __init__(self, home):
        self.home = home

    def _path(self, target):
        return self.home / "memories" / ("USER.md" if target == "user" else "MEMORY.md")

    def _read(self, target):
        try:
            return [e for e in self._path(target).read_text(encoding="utf-8").split("\n§\n") if e]
        except OSError:
            return []

    def add(self, target, content):
        items = self._read(target) + [content]
        self._path(target).parent.mkdir(parents=True, exist_ok=True)
        self._path(target).write_text("\n§\n".join(items), encoding="utf-8")
        return {"success": True}

    def remove(self, target, old_text):
        items = [e for e in self._read(target) if e != old_text]
        self._path(target).write_text("\n§\n".join(items), encoding="utf-8")
        return {"success": True}


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        fd, db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(db) and os.unlink(db))
        app.DB = Path(db)
        app._world_schema_ready = False
        patch = mock.patch.dict(os.environ, {"LILITH_OS_WRITE_AUTH": "open-acknowledged"})
        patch.start()
        self.addCleanup(patch.stop)
        self.home = self.tmp / "hermes"
        (self.home / "memories").mkdir(parents=True)
        (self.home / "pending" / "memory").mkdir(parents=True)
        self.write_user(PRE[:3] + [NAME] + PRE[3:] + [PREF])

    def write_user(self, items):
        (self.home / "memories" / "USER.md").write_text("\n§\n".join(items), encoding="utf-8")

    def poster(self, body):
        return app.post_owner_memory(body, x_lilith_os_write=None)

    def seen(self, *records):
        path = self.home / "memory-review" / "seen.jsonl"
        path.parent.mkdir(exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    def sync(self):
        return OMS.sync(self.home, poster=self.poster, now=1_800_000_000, getter=self.getter, repairer=FakeStore)

    def getter(self, include_superseded=True):
        return app.get_owner_memory(include_superseded=1 if include_superseded else 0)["entries"]

    def user_entries(self):
        return [e for e in (self.home / "memories" / "USER.md").read_text(encoding="utf-8").split("\n§\n") if e]

    def export(self, include_superseded=0):
        return {e["text"]: e for e in app.get_owner_memory(include_superseded=include_superseded)["entries"]}

    def test_bootstrap_labels_honestly_and_is_idempotent(self):
        self.sync()
        cur = self.export()
        self.assertEqual(set(cur), set(PRE) | {NAME, PREF})                         # the 7 current entries
        self.assertEqual(cur[NAME]["provenance"][0]["proposal_id"], "6e64c725")
        self.assertEqual(cur[PREF]["provenance"][0]["proposal_id"], "32b0ef1e")
        for text in PRE:
            p = cur[text]["provenance"][0]
            self.assertEqual((p["kind"], p["proposal_id"], p["approved_at"]), ("HERMES_PREEXISTING_IMPORT", None, None))
        hist = self.export(include_superseded=1)
        self.assertEqual(hist[OLD_SARA]["lifecycle_state"], "SUPERSEDED")         # history kept
        report = self.sync()
        self.assertEqual(report["created"], 0)                                     # no duplicates
        self.assertEqual(len(self.export()), 7)

    def test_only_approved_proposals_sync_afterwards(self):
        self.sync()
        self.seen({"id": "p9", "contents": ["User owns a bike."],
                   "ops": [{"action": "add", "target": "user", "content": "User owns a bike."}]},
                  {"id": "p10", "contents": ["User hates rain."],                                   # rejected
                   "ops": [{"action": "add", "target": "user", "content": "User hates rain."}]},
                  {"id": "p11", "contents": ["User plays chess."],                                  # still pending
                   "ops": [{"action": "add", "target": "user", "content": "User plays chess."}]})
        (self.home / "pending" / "memory" / "p11.json").write_text("{}", encoding="utf-8")
        self.write_user(PRE + [NAME, PREF, "User owns a bike.", "User plays chess.", "Hand-written entry."])
        report = self.sync()
        cur = self.export()
        self.assertEqual(cur["User owns a bike."]["provenance"][0]["proposal_id"], "p9")
        self.assertNotIn("User hates rain.", cur)                                  # rejected never synced
        self.assertNotIn("User plays chess.", cur)                                 # pending never synced
        self.assertNotIn("Hand-written entry.", cur)                               # unattributed never synced
        self.assertEqual(report["skipped_unattributed"], 2)

    def test_replace_supersedes_remove_retracts_missing_is_kept(self):
        self.sync()
        self.seen({"id": "p9", "ops": [{"action": "add", "target": "user", "content": "User owns a bike."}]})
        self.write_user(PRE + [NAME, PREF, "User owns a bike."])
        self.sync()
        self.seen({"id": "p12", "ops": [{"action": "replace", "target": "user", "old_text": "User owns a bike.",
                                        "content": "User owns two bikes."}]},
                  {"id": "p13", "ops": [{"action": "remove", "target": "user", "old_text": PRE[3]}]})
        self.write_user(PRE[:3] + PRE[4:] + [PREF, "User owns two bikes."])        # NAME vanished with no proposal
        report = self.sync()
        cur, hist = self.export(), self.export(include_superseded=1)
        self.assertIn("User owns two bikes.", cur)
        self.assertEqual(hist["User owns a bike."]["lifecycle_state"], "SUPERSEDED")
        self.assertEqual(hist[PRE[3]]["lifecycle_state"], "SUPERSEDED")             # owner-approved removal
        self.assertEqual(report["retracted"], 1)
        self.assertEqual(cur[NAME]["lifecycle_state"], "ACTIVE")                   # missing file entry: never retracted
        self.assertEqual(report["repaired_added"], 1)                              # ...and the projection is restored
        self.assertIn(NAME, self.user_entries())
        self.assertEqual(report["missing_in_hermes"], 0)

    def test_knowledge_is_recoverable_without_hermes_files(self):
        self.sync()
        shutil.rmtree(self.home / "memories")                                      # Hermes gone
        cur = self.export()
        self.assertIn(NAME, cur)
        self.assertIn(PREF, cur)
        self.assertEqual(len(cur), 7)
        report = self.sync()                                                       # a fresh runtime: rebuilt from LILITH OS
        self.assertEqual(report["repaired_added"], 7)
        self.assertEqual(sorted(self.user_entries()), sorted(cur))
        self.assertNotIn(OLD_SARA, self.user_entries())                            # history is not projected
        self.assertEqual(self.sync()["repaired_added"], 0)                         # restart: nothing twice


if __name__ == "__main__":
    unittest.main()
