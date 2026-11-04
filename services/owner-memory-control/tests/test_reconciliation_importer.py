"""Reconciliation importer: proposals only, inputs untouched (TEST_ONLY synthetic profile; no host, no runtime)."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent / "tools" / "reconciliation_importer.py"
_spec = importlib.util.spec_from_file_location("reconciliation_importer", TOOL)
RI = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RI)

S = "§"
USER_MD = (
    "Style: TEST_ONLY casual and concise; answer first.\r\n" + S + "\r\n"
    "Autonomy: ask before destructive or production actions; proactively verify reversible local work.\r\n" + S + "\r\n"
    "TEST_ONLY user is a landscape architect with ~5 years of experience; former teacher.\r\n" + S + "\r\n"
    "TEST_ONLY user prefers to be called Robin and uses they/them.\r\n" + S + "\r\n"
    "TEST_ONLY user enjoys tabletop games.\r\n" + S + "\r\n"
    "TEST_ONLY user enjoys tabletop games.\r\n" + S + "\r\n"
    "TEST_ONLY user prefers to be called Sam.\r\n"
)
NOTE = "# TEST_ONLY project note\n\nThe homelab project is currently being rebuilt.\n\n\nSecond paragraph about the repo.\n"


class ImporterTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.mem = self.base / "memories"
        for d in RI.NOTE_DIRS:
            (self.mem / d).mkdir(parents=True)
            (self.mem / d / "README.md").write_bytes(b"")
        (self.mem / "USER.md").write_bytes(USER_MD.encode("utf-8"))
        (self.mem / "MEMORY.md").write_bytes(b"")
        (self.mem / "USER.md.lock").write_bytes(b"")
        (self.mem / "projects" / "homelab.md").write_bytes(NOTE.encode("utf-8"))
        self.out = self.base / "out"

    def snapshot(self):
        return {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in sorted(self.mem.rglob("*")) if p.is_file()}

    def run_propose(self, **kw):
        before = self.snapshot()
        result = RI.propose(self.mem, self.out, **kw)
        self.assertEqual(self.snapshot(), before)                      # not one input byte or mtime changed
        return result

    def by_text(self, result, needle):
        return [p for p in result["proposals"] if needle in p["text"]]

    def test_every_entry_becomes_one_pending_verbatim_proposal_with_provenance(self):
        result = self.run_propose()
        self.assertEqual(result["schema"], RI.SCHEMA)
        self.assertEqual(sorted(os.listdir(self.out)), ["REVIEW.md", "proposals.json"])
        user = [p for p in result["proposals"] if p["source"]["path"] == "USER.md"]
        self.assertEqual(len(user), 7)
        self.assertEqual(user[3]["text"], "TEST_ONLY user prefers to be called Robin and uses they/them.")
        self.assertEqual(user[3]["source"]["lines"], [7, 7])
        notes = [p for p in result["proposals"] if p["source"]["path"] == "projects/homelab.md"]
        self.assertEqual(len(notes), 3)
        for p in result["proposals"]:
            self.assertEqual((p["decision"], p["epistemicBasis"], p["sensitivity"]),
                             ("PENDING_OWNER_REVIEW", "HERMES_MEMORY_NOTE_UNVERIFIED", "OWNER_PERSONAL"))
            self.assertEqual(p["allowedDecisions"], list(RI.DECISIONS))
            self.assertIsNone(p["proposedTarget"]["family"])            # never a guessed family
        sources = {s["path"]: s for s in result["sources"]}
        self.assertTrue(sources["MEMORY.md"]["empty"] and sources["decisions/README.md"]["empty"])
        self.assertEqual(result["ignored"], ["USER.md.lock"])
        on_disk = json.loads((self.out / "proposals.json").read_text(encoding="utf-8"))
        self.assertEqual(on_disk, result)

    def test_review_flags(self):
        result = self.run_propose()
        rule = self.by_text(result, "Autonomy:")[0]
        self.assertEqual((rule["category"], rule["proposedTarget"]["status"]), ("OPERATING_RULE", "NOT_A_MEMORY_FACT"))
        career = self.by_text(result, "landscape architect")[0]
        self.assertEqual(career["category"], "CAREER")
        self.assertIn("TIME_SENSITIVE", career["flags"])                # "~5 years" ages
        self.assertIn("TIME_SENSITIVE", self.by_text(result, "currently being rebuilt")[0]["flags"])
        first, second = self.by_text(result, "enjoys tabletop games")
        self.assertNotIn("DUPLICATE_OF:" + first["proposalId"], first["flags"])
        self.assertIn("DUPLICATE_OF:" + first["proposalId"], second["flags"])
        robin, sam = self.by_text(result, "Robin")[0], self.by_text(result, "called Sam")[0]
        self.assertEqual((robin["keys"]["preferred_name"], sam["keys"]["preferred_name"]), ("robin", "sam"))
        self.assertIn("CONFLICTS_ON:preferred_name:" + sam["proposalId"], robin["flags"])
        self.assertIn("CONFLICTS_ON:preferred_name:" + robin["proposalId"], sam["flags"])
        self.assertEqual(robin["category"], "IDENTITY")
        self.assertEqual(result["counts"]["flagged"]["CONFLICTS_ON"], 2)

    def test_already_canonical_values_are_marked_not_reproposed(self):
        canonical = {"schema": "LilithCanonicalMemoryContextV1", "status": "CONTEXT", "reason": None,
                     "memories": [{"kind": "codename", "value": "TEST_ONLY user enjoys tabletop games."}]}
        result = self.run_propose(canonical=canonical)
        for p in self.by_text(result, "tabletop"):
            self.assertIn("ALREADY_CANONICAL:codename", p["flags"])
        unavailable = {**canonical, "status": "UNAVAILABLE"}
        self.out = self.base / "out2"
        self.assertFalse(any(f.startswith("ALREADY") for p in self.run_propose(canonical=unavailable)["proposals"]
                             for f in p["flags"]))

    def test_the_proposal_ids_are_stable(self):
        a = self.run_propose()
        self.out = self.base / "again"
        self.assertEqual([p["proposalId"] for p in a["proposals"]],
                         [p["proposalId"] for p in self.run_propose()["proposals"]])

    def test_refusals_and_no_overwrite(self):
        with self.assertRaises(RI.ImportRefused) as ctx:
            RI.propose(self.mem, self.mem / "out")
        self.assertEqual(ctx.exception.code, "OUTPUT_OVERLAPS_INPUT")
        with self.assertRaises(RI.ImportRefused):
            RI.propose(self.mem, self.mem)
        self.run_propose()
        sheet = (self.out / "REVIEW.md").read_bytes()
        with self.assertRaises(RI.ImportRefused) as ctx:
            RI.propose(self.mem, self.out)
        self.assertEqual(ctx.exception.code, "OUTPUT_EXISTS")
        self.assertEqual((self.out / "REVIEW.md").read_bytes(), sheet)   # an earlier review is never overwritten
        empty = self.base / "empty"
        empty.mkdir()
        with self.assertRaises(RI.ImportRefused):
            RI.build(empty)
        (self.mem / "USER.md").write_bytes(b"\xff\xfe bad")
        with self.assertRaises(RI.ImportRefused) as ctx:
            RI.build(self.mem)
        self.assertEqual(ctx.exception.code, "NOT_UTF8:USER.md")

    def test_verify_and_cli(self):
        self.assertEqual(RI.main(["propose", str(self.mem), str(self.out)]), 0)
        self.assertEqual(RI.main(["verify", str(self.mem), str(self.out)]), 0)
        (self.mem / "USER.md").write_bytes(USER_MD.encode("utf-8") + b"x")
        self.assertEqual(RI.verify(self.mem, self.out)["inputsUnchanged"], False)
        self.assertEqual(RI.main(["verify", str(self.mem), str(self.out)]), 1)
        self.assertEqual(RI.main(["admit", str(self.mem), str(self.out)]), 2)

    def test_the_tool_cannot_reach_the_runtime(self):
        source = TOOL.read_text(encoding="utf-8")
        for forbidden in ("import sqlite3", "import socket", "lilith_memory", "lilith_owner_memory", "subprocess",
                          "urllib", "requests", "os.remove", "unlink", "rmtree", '"r+', '"a"'):
            self.assertFalse(forbidden in source, forbidden)


if __name__ == "__main__":
    unittest.main()
