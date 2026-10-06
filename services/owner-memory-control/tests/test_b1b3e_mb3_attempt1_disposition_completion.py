"""15B2b-B1b-3e M-B3: the attempt-1 phone incident disposition completion record (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-mb3-attempt1-disposition-completion.md.

Pins the PASS result, the archive and its 64-hex manifest digest, the
disposition script digest (equal to the reviewed block in the incident record),
the verbatim owner authorization, K-ROOT custody preservation, unchanged
attempt-1 history, and that nothing later is authorized.
"""

from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARCH = ROOT / "docs/architecture"
RECORD = ARCH / "slice-15b2b-b1b3e-mb3-attempt1-disposition-completion.md"
INCIDENT = ARCH / "slice-15b2b-b1b3e-mb3-sign-attempt1-incident.md"
CONTROL = "cb07608b3bcc8b8b04834a174383bc28461994f8"
ARCHIVE_SHA = "94483e8b95adecea163dad9d0622877f21328f9d580ebee68201bf36c955181d"
SCRIPT_SHA = "73f7135549322bd939fd7f3c743e564715e708402388d61d51a86e46c30154e1"
CANDIDATE = "b7e24530a21757a5bef996ec9adb13ed5932ab04edb1943321f529e3206c0e53"
UNAUTHORIZED = ("REPLACEMENT M-B3 PREPARATION SEQUENCE = NOT AUTHORIZED", "PREPARE = NOT AUTHORIZED",
                "SIGN_REGISTRY_V1 = NOT AUTHORIZED", "REGISTRY_SIGNED = NOT REACHED", "M-B4/M-B5 = NOT AUTHORIZED",
                "REGISTRY EFFECTIVENESS = NOT AUTHORIZED", "GENESIS = NOT AUTHORIZED", "RECORD 1 = NOT AUTHORIZED",
                "FIRST MEMORY = NOT AUTHORIZED", "PROD = NOT AUTHORIZED", "FRESHNESS=UNKNOWN")


def flat(text: str) -> str:
    return " ".join(re.sub(r"^\s*>", " ", text, flags=re.MULTILINE).split())


def reviewed_block() -> bytes:
    parts = [p.split("\n```", 1)[0] + "\n" for p in INCIDENT.read_text(encoding="utf-8").split("```bash\n")[1:]]
    found = [p for p in parts if p.startswith("# ===== M-B3 attempt-1 incident disposition")]
    assert len(found) == 1
    return found[0].encode("utf-8")


class CompletionRecordTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = self.text.split("## 7. State", 1)[1]

    def test_result_and_archive(self):
        for line in ("PHONE_INCIDENT_DISPOSITION = PASS", "ATTEMPT1_ARCHIVE = ~/lilith-mb3-incident-attempt1",
                     f"ARCHIVE_MANIFEST_SHA256 = {ARCHIVE_SHA}", "ACTIVE_MB3_STATE = ABSENT",
                     "ATTEMPT1_DOWNLOAD_FILES = ARCHIVED", "KROOT_CUSTODY_PRESERVED = YES",
                     "NOTHING DELETED; ARCHIVE BY RENAME / MOVE", "REPLACEMENT_FILES_TRANSFERRED = NO"):
            self.assertIn(line, self.state)
        self.assertRegex(ARCHIVE_SHA, r"^[0-9a-f]{64}$")
        self.assertIn(CONTROL, self.text)

    def test_script_is_the_reviewed_block(self):
        self.assertEqual(hashlib.sha256(reviewed_block()).hexdigest(), SCRIPT_SHA)
        self.assertIn(f"DISPOSITION_SCRIPT {SCRIPT_SHA} (REVIEWED BLOCK AT cb07608, UNCHANGED)", self.state)

    def test_verbatim_authorization(self):
        verbatim = flat(self.text.split("## 2. Owner authorization (verbatim)", 1)[1].split("## 3.", 1)[0])
        self.assertTrue(verbatim.startswith("I authorize one owner-attended S25 M-B3 attempt-1 incident disposition "
                                            "operation, and nothing beyond it."))
        self.assertIn("This authorization does not permit opening, reading, decrypting, moving, copying, renaming or "
                      "modifying k-root.der or any K-ROOT private material.", verbatim)
        self.assertTrue(verbatim.endswith("FRESHNESS=UNKNOWN remains unchanged."))

    def test_precheck_and_transcription_correction_are_recorded(self):
        self.assertIn("**The reviewed script was not changed.**", self.text)
        self.assertIn("The owner's first transcription had 65 hexadecimal characters", self.text)

    def test_history_unchanged_and_nothing_authorized(self):
        self.assertIn("M-B3 SIGN ATTEMPT 1 = CLOSED / INCIDENT / A_NO_SIGNATURE", self.state)
        self.assertIn("ATTEMPT-1 CANDIDATE = HISTORICAL_ABANDONED_UNSIGNED_CANDIDATE; NOT BURNED; NOT REUSABLE", self.state)
        self.assertIn(CANDIDATE, self.text)
        for line in UNAUTHORIZED:
            self.assertIn(line, self.state)
        for claim in ("PREPARATION SEQUENCE = AUTHORIZED", "PREPARE = AUTHORIZED", "SIGN_REGISTRY_V1 = AUTHORIZED",
                      "REGISTRY_SIGNED = REACHED", "FRESHNESS=CURRENT", "REPLACEMENT_FILES_TRANSFERRED = YES"):
            self.assertNotIn(claim, self.state)

    def test_pointers(self):
        for name in ("slice-15b2b-b1b3e-mb3-sign-attempt1-incident.md",
                     "slice-15b2b-b1b3e-mb3-replacement-final-package-pins.md", "README.md"):
            self.assertIn("(slice-15b2b-b1b3e-mb3-attempt1-disposition-completion.md)",
                          (ARCH / name).read_text(encoding="utf-8"), name)


if __name__ == "__main__":
    unittest.main()
