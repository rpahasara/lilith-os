"""15B2b-B1b-3e M-B4/M-B5: the preparation-sequence-1 E-21 incident record and the operator pin cascade (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-mb4-mb5-prep-seq1-operator-loader-incident.md.

Pins that the record names the superseded and the current operator SHA-256,
that the current one is the file's and the package §1 table's, that the
superseded pin appears nowhere as current, that every other pin is unchanged,
that the sequence is historical and non-reusable, and the authority boundary.
Stdlib only.
"""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARCH = ROOT / "docs/architecture"
RECORD = ARCH / "slice-15b2b-b1b3e-mb4-mb5-prep-seq1-operator-loader-incident.md"
PACKAGE = ARCH / "slice-15b2b-b1b3e-mb4-mb5-ceremony-package.md"
LEDGER = ARCH / "current-architecture-acceptance-ledger-v0.1.md"
TOOLS = ROOT / "services/owner-memory-control/tools"
for _p in (TOOLS, Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import mb4_mb5_operator as O  # noqa: E402
import post_reboot_repin as RP  # noqa: E402

SUPERSEDED = "2d9835edb18361df231c58d914c8859240438c7ed7dd39de547bee4756acfbbf"
CONTROL = "ffa9575f13e60ae8f87dfb0c7b9afc9e5d4f566d"
# The package §1 pins as merged at the sequence-1 control; none of these files changed.
UNCHANGED = {
    "services/owner-memory-control/tools/mb4_mb5_installable_inputs.py":
        "dbe94a2d3a38fa838d4fd7eeb9016274c85c684221ddb770e8e993cc15b18d61",
    "services/owner-memory-control/tools/mb3_registry_ceremony.py":
        "c77b651ca2ae9d5f6c5526f958469a01c0d42e6ebdf189fc206ac2132af61320",
    "services/owner-memory-control/tools/verify_mb3_registry.py":
        "e710cfa623d494e243ab4a1fbaefe28e8d079e58398368f9dcabd645e06b5507",
    "services/authority-dev/ceremony/install_authority_dev.py":
        "fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487",
    "services/owner-memory-control/tools/mb4_mb5_trust_install_verifier.py":
        "78f57c01811e20a03ebb06bc114847bad440c7435e85ceb0249a488c659b2361",
    "services/owner-memory-control/tools/mb4_mb5_remove_before_mb6.py":
        "db0629a6a5f39ca65e23010aeeccc565978b7d8990f38d6b8bb6c361046ee104",
    "services/authority-dev/ceremony/observe_authority_dev_host.py":
        "a2f21b45e57a153f099c79a734ab05a575ac5c50f7cbc0527e562e94dd6908bf",
    "scripts/verify_broker_dev_current_incarnation.py":
        "2e68160971a3b0dd05ffcb6cdc464fc612afb2b522a57fb534b25c6af83c10ba",
    "scripts/authority_custody_denial_proof.py":
        "f4e39c81c24a01be5702f6a65a581fcd08f97e1c5ad4a07326883b605fef1455",
    "services/owner-memory-control/lilith_owner_memory/owner_freshness_tool.py":
        "fd7abe2aa5e5efae41b87553efe8fe8058b437748accf866c2fa5ee71c8a7c27",
    "scripts/deployer_authority_boundary_proof.sh":
        "9b569f9bee8f07f0bf13ec1d20e2607d9e01c601a2e94a2988320e5bc4160f43",
}
REPRESENTATION = {
    "registry-root.json": "bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687",
    "witness-anchor.json": "be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a",
    "authority-registry.v1.json": "46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PrepSequence1IncidentTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = self.text.split("## 8. State", 1)[1]
        self.operator = sha(TOOLS / "mb4_mb5_operator.py")

    def test_operator_pin_cascade(self):
        self.assertNotEqual(self.operator, SUPERSEDED)
        cascade = self.text.split("## 5. Pin cascade", 1)[1].split("## 6.", 1)[0]
        row = next(line for line in cascade.splitlines() if line.startswith("| `mb4_mb5_operator.py` |"))
        self.assertEqual(row, f"| `mb4_mb5_operator.py` | `{SUPERSEDED}` | `{self.operator}` |")
        self.assertIn(f"pre-merge) | SHA-256 `{self.operator}` |", self.text)
        package = PACKAGE.read_text(encoding="utf-8")
        table = package.split("## 1. Control and pinned tools", 1)[1].split("**Hash-gated streaming.**", 1)[0]
        operator_row = next(line for line in table.splitlines()
                            if line.startswith("| `services/owner-memory-control/tools/mb4_mb5_operator.py`"))
        self.assertIn(self.operator, operator_row)
        self.assertNotIn(SUPERSEDED, table)
        self.assertIn("**superseded and must not be used**", package.split("## 17. State", 1)[1])

    def test_every_other_pin_unchanged(self):
        for path, pin in UNCHANGED.items():
            self.assertEqual(sha(ROOT / path), RP.tree_pin(path, pin), path)
        for path, pin in O.TOOL_PINS.items():
            self.assertEqual(UNCHANGED[path], pin, path)
        self.assertEqual(dict(O.DERIVED), REPRESENTATION)
        for pin in REPRESENTATION.values():
            self.assertIn(f"`{pin}` | unchanged |", self.text)

    def test_sequence_is_historical_and_nothing_happened_downstream(self):
        self.assertIn(CONTROL, self.text)
        self.assertIn("**All evidence of sequence 1 is HISTORICAL / NON-REUSABLE**", self.text)
        for line in ("MB4_MB5_PREPARATION_SEQUENCE_1 = ENDED / STOPPED_AT_E21 / TOOL_DEFECT (HISTORICAL; NON-REUSABLE)",
                     "DEPLOYMENT_FREEZE_PREVIOUS_SEQUENCE = RELEASED (OWNER DECISION; AUTHORIZES NO DEPLOYMENT)",
                     "NO DERIVATION OUTPUT; NO STAGING; NO GO CONSUMED; NO BURN",
                     "MB4_MB5_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_GO (ACCEPTED; UNCHANGED)"):
            self.assertIn(line, self.state)

    def test_authority_boundary(self):
        for line in ("PREPARATION SEQUENCE = NOT AUTHORIZED", "TRANSFER = NOT AUTHORIZED", "M-B4 = NOT AUTHORIZED",
                     "M-B5 = NOT AUTHORIZED", "INSTALL_TRUST_AND_REGISTRY = NOT AUTHORIZED", "TRUST_INSTALLED = NO",
                     "REGISTRY_INSTALLED = NO", "REGISTRY_EFFECTIVE = NO", "AUTHORITY_ACTIVE = NO",
                     "GENESIS = NOT AUTHORIZED", "RECORD_1 = NOT AUTHORIZED", "FIRST_MEMORY = NOT AUTHORIZED",
                     "PROD = NOT AUTHORIZED", "FRESHNESS=UNKNOWN"):
            self.assertIn(line, self.state)
        for claim in ("M-B4 = AUTHORIZED", "M-B5 = AUTHORIZED", "TRUST_INSTALLED = YES", "FRESHNESS=CURRENT"):
            self.assertNotIn(claim, self.state)

    def test_ledger_and_index(self):
        ledger = LEDGER.read_text(encoding="utf-8")
        self.assertIn("### 13.1ac Current-state reconciliation (M-B4/M-B5 preparation sequence 1 stopped at E-21", ledger)
        auth02 = next(line for line in ledger.splitlines() if line.startswith("| AUTH-02 |"))
        self.assertIn("FRESHNESS=UNKNOWN (§13.1ac)", auth02)        # later passes append after it (§13.1ad …)
        self.assertTrue(auth02.endswith("| UNASSIGNED |"))
        readme = (ARCH / "README.md").read_text(encoding="utf-8")
        self.assertIn("(slice-15b2b-b1b3e-mb4-mb5-prep-seq1-operator-loader-incident.md)", readme)


if __name__ == "__main__":
    unittest.main()
