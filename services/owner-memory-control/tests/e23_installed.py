"""Track B B4 test helper: the INSTALLED (E-22 NEW, 129f2be) release payload, reconstructed from Git history.

Tests that compare the repository against the installed release (the M-B6 module pins, the E-19 restart-boundary unit
fragment, the E-19/E-22 delta guards) use these bytes for the E-23 members, because the repository now carries the
proposed E-23 payload while the host still runs OLD. CI checks out the full history (`fetch-depth: 0`).

RR-39 (archive layout v3) moved the repository on again: its four changed signer members are reverted the same way
(E-23 left them untouched, so their 129f2be bytes are also the 57bff671 bytes) and its two added members are removed.
"""

from __future__ import annotations

import subprocess
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _path in (ROOT / "services/core-api", ROOT / "services/owner-memory-control", ROOT / "services/owner-memory-control/tools",
              ROOT / "services/authority-dev", ROOT / "services/authority-dev/ceremony"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import e23_privacy_anchor_upgrade as E23  # noqa: E402
import install_authority_dev_v3 as V3  # noqa: E402
import release_file_set as RFS  # noqa: E402

SOURCE_OF = {target: source for source, target in RFS.RUNTIME_SOURCE_MAP.items()}
# The post-E-23 source change to the signer runtime, RR-39 then First Memory (pinned exactly by authority-dev
# `test_rr39_layout_v3`).
RR39_CHANGED = frozenset({"lilith_authority_dev/core.py", "lilith_authority_dev/credential.py",
                          "lilith_authority_dev/ledger.py", "lilith_authority_dev/protocol.py",
                          # First Memory: the DEV runtime wiring and the evidence-use transport.
                          "lilith_authority_dev/profile.py", "lilith_authority_dev/server.py",
                          "lilith_authority_host/inputs.py", "lilith_authority_host/paths.py",
                          "lilith_authority_root/clients.py",
                          # First Memory privilege fix: the root bridge (`first-memory` form).
                          "lilith_authority_root/cli.py"})
# OWNER_PROD (P2, 2026-11): the production profile beside DEV_SYNTHETIC. Installed DEV (d82f7da) still runs these
# members' earlier bytes; the P3 transition installs them (the witness restarts from NEW, as FM-1 did).
OWNER_PROD_CHANGED = frozenset({"lilith_authority_dev/evidence_minter.py", "lilith_authority_dev/recovery.py",
                                "lilith_owner_memory/authority_contracts.py", "lilith_owner_memory/authority_verifier.py",
                                "lilith_owner_memory/pr1_bootstrap.py", "lilith_owner_memory/recovery_contracts.py",
                                "lilith_owner_memory/rotation_contracts.py", "lilith_owner_memory/successor_custody.py",
                                "lilith_owner_memory/verifier.py", "lilith_recovery_witness/credential.py",
                                "lilith_recovery_witness/server.py"})
# Every signer-payload member P2 moved past the installed FM-2 release (d82f7da): the RR-39/First Memory members it
# touched again plus OWNER_PROD_CHANGED. `P2_BASE` is the last main commit before P2 (75ca0db, #306), whose payload
# equals d82f7da's.
P2_BASE = "75ca0db084ef43f39462e3fe77b2f3fce8f5a0e2"
OWNER_PROD_TREE_DELTA = OWNER_PROD_CHANGED | frozenset({
    "lilith_authority_dev/core.py", "lilith_authority_dev/ledger.py", "lilith_authority_dev/profile.py",
    "lilith_authority_dev/server.py", "lilith_authority_host/inputs.py", "lilith_authority_host/paths.py",
    "lilith_authority_root/cli.py"})
OWNER_PROD_SOURCES = frozenset(SOURCE_OF[m] for m in OWNER_PROD_TREE_DELTA)
# Only members the E-23 era release carries (RR-39's layout-v3 additions, e.g. the shared verifier, are not).
OWNER_PROD_INSTALLED = OWNER_PROD_CHANGED - V3.ADDED_RUNTIME_PATHS
# Every repository member whose installed bytes differ, and every member the installed release does not carry.
INSTALLED_DELTA = frozenset(E23.PAYLOAD_DELTA) | RR39_CHANGED | OWNER_PROD_INSTALLED
NOT_INSTALLED = frozenset(E23.PAYLOAD_ADDED) | V3.ADDED_RUNTIME_PATHS


@lru_cache(maxsize=None)
def old_bytes(member: str) -> bytes:
    """The installed bytes of one changed E-23 or RR-39 member (`git show <OLD_RELEASE>:<source>`)."""
    if member not in INSTALLED_DELTA:
        raise KeyError(member)
    out = subprocess.run(["git", "show", f"{E23.OLD_RELEASE}:{SOURCE_OF[member]}"], cwd=ROOT, capture_output=True,
                         check=True)
    return out.stdout


@lru_cache(maxsize=None)
def e23_new_bytes(member: str) -> bytes:
    """The E-23 NEW (57bff671) bytes of one member (`git show <NEW_RELEASE>:<source>`)."""
    out = subprocess.run(["git", "show", f"{E23.NEW_RELEASE}:{SOURCE_OF[member]}"], cwd=ROOT, capture_output=True,
                         check=True)
    return out.stdout


def e23_new_payloads(root: Path = ROOT) -> dict[str, bytes]:
    """The E-23 NEW payload (archive layout v2): the repository payload with the RR-39 change reverted."""
    payloads = dict(RFS.runtime_payloads(root))
    for member in V3.ADDED_RUNTIME_PATHS:
        payloads.pop(member)
    for member in RR39_CHANGED:
        payloads[member] = old_bytes(member)
    for member in OWNER_PROD_INSTALLED:          # P2 moved them on from their E-23 NEW bytes
        payloads[member] = e23_new_bytes(member)
    return payloads


def installed_payloads(root: Path = ROOT) -> dict[str, bytes]:
    """The repository payload with every E-23 / RR-39 member at its installed bytes and the added members removed."""
    payloads = dict(RFS.runtime_payloads(root))
    for member in NOT_INSTALLED:
        payloads.pop(member)
    for member in INSTALLED_DELTA:
        payloads[member] = old_bytes(member)
    return payloads


def installed_source_bytes(source: str) -> bytes:
    """Installed bytes for a repository source path: OLD for an E-23 / RR-39 member, the repository bytes otherwise."""
    target = RFS.RUNTIME_SOURCE_MAP.get(source)
    if target in INSTALLED_DELTA:
        return old_bytes(target)
    return (ROOT / source).read_bytes()
