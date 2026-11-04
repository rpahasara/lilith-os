"""cm1 overlay integrity (offline): the adapter is exactly the installed e1 adapter plus the reviewed hunk, the context
module is the one canonical copy, and the DEV window pins exactly these bytes."""

import hashlib
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
O = ROOT / "integrations/hermes/overlays/dev-canonical-memory-context"
BASE = ROOT / "integrations/hermes/home/variants/dev-f9c2/plugins/lilith_os/adapter.py"
OMC = ROOT / "services/owner-memory-control"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class OverlayTests(unittest.TestCase):
    def test_the_adapter_is_the_e1_adapter_plus_one_reviewed_hunk(self):
        self.assertEqual(sha(BASE), "8c3b00552d83adb4e7d6c0af5a9aa081cb60d92879dc14db3baf71537ca32a4a")
        base, new = BASE.read_text(encoding="utf-8").splitlines(), (O / "adapter.py").read_text(encoding="utf-8").splitlines()
        added = [line for line in new if line not in base]
        removed = [line for line in base if line not in new]
        self.assertEqual(removed, [])
        self.assertIn("from .lilith_memory_context import DEFAULT_SOCKET, note_for_turn", added)
        self.assertIn("            event.channel_prompt = note_for_turn(", added)
        self.assertLessEqual(len(added), 12)
        compile((O / "adapter.py").read_text(encoding="utf-8"), "adapter.py", "exec")

    def test_one_copy_of_the_context_module(self):
        self.assertEqual((O / "lilith_memory_context.py").read_bytes(),
                         (OMC / "lilith_owner_memory/hermes_memory_context.py").read_bytes())

    def test_the_window_pins_these_bytes(self):
        window = (O / "cm1_window.sh").read_text(encoding="utf-8")
        pins = dict(re.findall(r"^  \[([^\]]+)\]=([0-9a-f]{64})$", window, re.M))
        expected = {"adapter.cm1.py": O / "adapter.py", "adapter.e1.py": BASE,
                    "lilith_memory_context.py": O / "lilith_memory_context.py",
                    "canonical_context_service.py": OMC / "tools/hermes_context/canonical_context_service.py",
                    "lilith-first-memory-context.socket": OMC / "tools/hermes_context/lilith-first-memory-context.socket",
                    "lilith-first-memory-context@.service": OMC / "tools/hermes_context/lilith-first-memory-context@.service"}
        self.assertEqual(set(pins), set(expected))
        for name, path in expected.items():
            self.assertEqual(pins[name], sha(path), name)
        for line in (O / "SHA256SUMS").read_text(encoding="ascii").splitlines():
            digest, name = line.split("  ", 1)
            self.assertEqual(sha(O / name), digest, name)

    def test_the_window_raises_the_gate_by_exactly_two_and_restores_it_byte_for_byte(self):
        window = (O / "cm1_window.sh").read_text(encoding="utf-8")
        self.assertIn("NEWLIMIT=$((USED + 2))", window)
        self.assertIn("cp -p ${W}/gate.json.pre ${GJ}", window)
        self.assertNotIn("gate_budget.sh reset", window)          # never a ledger RESET


if __name__ == "__main__":
    unittest.main()
