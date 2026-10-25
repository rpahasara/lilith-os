#!/usr/bin/env python3
"""Track B B4: the versioned installer successor for E-23 release archives (owner decision, 2026-10-25).

`install_authority_dev.py` (`fe10d9a3…`) stays byte-identical: the closed M-B4 … M-B10 ceremonies, their owner-approved
go texts and every operator in the pin chain bind its exact bytes. This successor changes exactly one thing, the
release archive layout: an E-23 archive carries two more runtime members,

    lilith_recovery_witness/privacy_anchor.py       (the witness-held K-PAN Privacy anchor)
    lilith_memory/privacy_anchor_contracts.py       (the pure contract it imports; SHARED_HASHES addition)

Everything else IS the accepted installer: every other name is delegated to it (module `__getattr__`), and the two
layout-dependent functions (`check_payloads`, `verify_archive`) run the V1 code itself with the V2 layout set bound
for the duration of the call (single-threaded CLI tools only). No installer logic is duplicated.

Used by the release builder, the build attestation tool and the (later, separately authorized) E-23 stage tooling.
An installed release is judged against its own manifest by V1 (`release_tree_failures`), so OLD (129f2be) stays valid
while E-23 is staged.

    archive layout v2 != installed release != authorization
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from typing import Iterator

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import install_authority_dev as V1  # noqa: E402  (the accepted installer; byte-identical)

LAYOUT_VERSION = 2
ADDED_RUNTIME_PATHS = frozenset({"lilith_recovery_witness/privacy_anchor.py", "lilith_memory/privacy_anchor_contracts.py"})
RUNTIME_PATHS = V1.RUNTIME_PATHS | ADDED_RUNTIME_PATHS
EXPECTED_PATHS = V1.EXPECTED_PATHS | ADDED_RUNTIME_PATHS


def __getattr__(name: str):
    return getattr(V1, name)


@contextlib.contextmanager
def _layout_v2() -> Iterator[None]:
    saved = V1.EXPECTED_PATHS
    V1.EXPECTED_PATHS = saved | ADDED_RUNTIME_PATHS
    try:
        yield
    finally:
        V1.EXPECTED_PATHS = saved


def check_payloads(payloads: dict[str, bytes]) -> None:
    with _layout_v2():
        V1.check_payloads(payloads)


def verify_archive(archive: Path, attestation: Path, expected_sha: str) -> tuple[dict, dict[str, bytes]]:
    with _layout_v2():
        return V1.verify_archive(archive, attestation, expected_sha)
