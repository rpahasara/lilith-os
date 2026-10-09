"""The 2026-10-09 post-reboot re-pin, as seen by the tests of completed ceremonies.

The broker preservation verifier was re-pinned to the owner-accepted post-reboot broker baseline
(docs/architecture/slice-15b2b-b1b3e-post-reboot-witness-broker-repin.md). The completed M-B4/M-B5, M-B6 and
Package A operators stay byte-unchanged and keep their historical pin of it, so against the current tree they
refuse with TOOL_PIN_MISMATCH. Their tests check that historical pin exactly and exercise their logic with the
current verifier bytes. Only `mb9_operator` (and through it `pkgc_operator`) pins the current verifier.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
BROKER = "scripts/verify_broker_dev_current_incarnation.py"
# Bound by the completed M-B4/M-B5, M-B6 and Package A operators (the Package B record §16 value).
HISTORICAL_BROKER_PIN = "2e68160971a3b0dd05ffcb6cdc464fc612afb2b522a57fb534b25c6af83c10ba"
# The re-pinned verifier: `mb9_operator.TOOL_PINS[BROKER]`.
CURRENT_BROKER_PIN = "b90ed6efa203f7aade5519120e1658b866aa9f0d4f559e6ac39fcc51573ebfcf"
# `mb9_operator.py` as accepted with Package B (record §16 / completion record), and after this re-pin.
HISTORICAL_MB9_OPERATOR_PIN = "066fc8213b40c392e3e2bfd609da4a7f2a4e0b6f05da011daee9add3caf13973"
CURRENT_MB9_OPERATOR_PIN = "2312e26a9cc8c2076539ae8bdde98cc5d79c2bbeb5138d66d07863ec3303c928"


def tree_pin(path: str, pin: str) -> str:
    """The SHA-256 the current tree must have for a completed ceremony's pin: the pin itself, except the
    historical broker verifier pin, whose file is now exactly the re-pinned one."""
    return CURRENT_BROKER_PIN if (path, pin) == (BROKER, HISTORICAL_BROKER_PIN) else pin


def record_pin(path: str, pin: str) -> str:
    """The value a completed record states for a current pin: the pin itself, except the re-pinned broker
    verifier, which the record states with its historical value."""
    return HISTORICAL_BROKER_PIN if (path, pin) == (BROKER, CURRENT_BROKER_PIN) else pin


def current_tree(module) -> "mock._patch_dict":
    """Exercise a completed ceremony operator against the current tree (test-only; the file is unchanged)."""
    assert module.TOOL_PINS[BROKER] == HISTORICAL_BROKER_PIN
    assert hashlib.sha256((ROOT / BROKER).read_bytes()).hexdigest() == CURRENT_BROKER_PIN
    return mock.patch.dict(module.TOOL_PINS, {BROKER: CURRENT_BROKER_PIN})
