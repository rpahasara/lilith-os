"""Run the recovery-witness suite (services/recovery-witness/tests) from the
authority-dev suite, which CI already discovers. The witness is its own
service tree; its tests stay there, and this loader only adds them."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

WITNESS_TESTS = Path(__file__).resolve().parents[2] / "recovery-witness" / "tests"


def load_tests(loader: unittest.TestLoader, standard_tests: unittest.TestSuite, pattern: str | None):
    if str(WITNESS_TESTS) not in sys.path:
        sys.path.insert(0, str(WITNESS_TESTS))
    import test_recovery_witness

    standard_tests.addTests(loader.loadTestsFromModule(test_recovery_witness))
    return standard_tests


if __name__ == "__main__":
    unittest.main()
