"""Track B B4 test helper: the INSTALLED (E-22 NEW, 129f2be) release payload, reconstructed from Git history.

Tests that compare the repository against the installed release (the M-B6 module pins, the E-19 restart-boundary unit
fragment, the E-19/E-22 delta guards) use these bytes for the E-23 members, because the repository now carries the
proposed E-23 payload while the host still runs OLD. CI checks out the full history (`fetch-depth: 0`).
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
import release_file_set as RFS  # noqa: E402

SOURCE_OF = {target: source for source, target in RFS.RUNTIME_SOURCE_MAP.items()}


@lru_cache(maxsize=None)
def old_bytes(member: str) -> bytes:
    """The installed bytes of one changed E-23 member (`git show <OLD_RELEASE>:<source>`)."""
    if member not in E23.PAYLOAD_DELTA:
        raise KeyError(member)
    out = subprocess.run(["git", "show", f"{E23.OLD_RELEASE}:{SOURCE_OF[member]}"], cwd=ROOT, capture_output=True,
                         check=True)
    return out.stdout


def installed_payloads(root: Path = ROOT) -> dict[str, bytes]:
    """The repository payload with every E-23 member at its installed bytes and the added members removed."""
    payloads = dict(RFS.runtime_payloads(root))
    for member in E23.PAYLOAD_ADDED:
        payloads.pop(member)
    for member in E23.PAYLOAD_DELTA:
        payloads[member] = old_bytes(member)
    return payloads


def installed_source_bytes(source: str) -> bytes:
    """Installed bytes for a repository source path: OLD for an E-23 member, the repository bytes otherwise."""
    target = RFS.RUNTIME_SOURCE_MAP.get(source)
    if target in E23.PAYLOAD_DELTA:
        return old_bytes(target)
    return (ROOT / source).read_bytes()
