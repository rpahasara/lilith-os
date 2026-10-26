#!/usr/bin/env python3
"""RR-39: the versioned installer successor for release archives that carry the governed issuance path.

`install_authority_dev.py` (`fe10d9a3…`) and `install_authority_dev_v2.py` (the E-23 archive layout v2) stay
byte-identical: the closed ceremonies, the E-23 transition and their owner-approved go texts bind their exact bytes.
This successor changes exactly one thing, the release archive layout: an RR-39 archive carries two more runtime
members than E-23,

    lilith_authority_dev/issuance.py                (the governed DEV_SYNTHETIC issuance path; unwired in the runtime)
    lilith_owner_memory/verifier.py                 (the owner-proof verifier it imports; SHARED_HASHES addition)

Everything else IS the accepted installer: every other name is delegated to V2 and through it to V1 (module
`__getattr__`), and the two layout-dependent functions (`check_payloads`, `verify_archive`) run the V1 code itself
with the V3 layout set bound for the duration of the call (single-threaded CLI tools only). No installer logic is
duplicated, and no wheel is added (`fido2`, `cryptography`, `rfc8785` are already pinned).

Used by the release builder and the build attestation tool. An installed release is judged against its own manifest by
V1 (`release_tree_failures`), so the installed E-23 release (57bff671) stays valid while a successor is staged.

    archive layout v3 != installed release != authorization
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
import install_authority_dev_v2 as V2  # noqa: E402  (the E-23 archive layout v2; byte-identical)

LAYOUT_VERSION = 3
ADDED_RUNTIME_PATHS = frozenset({"lilith_authority_dev/issuance.py", "lilith_owner_memory/verifier.py"})
RUNTIME_PATHS = V2.RUNTIME_PATHS | ADDED_RUNTIME_PATHS
EXPECTED_PATHS = V2.EXPECTED_PATHS | ADDED_RUNTIME_PATHS


def __getattr__(name: str):
    return getattr(V2, name)


@contextlib.contextmanager
def _layout_v3() -> Iterator[None]:
    saved = V1.EXPECTED_PATHS
    V1.EXPECTED_PATHS = EXPECTED_PATHS
    try:
        yield
    finally:
        V1.EXPECTED_PATHS = saved


def check_payloads(payloads: dict[str, bytes]) -> None:
    with _layout_v3():
        V1.check_payloads(payloads)


def verify_archive(archive: Path, attestation: Path, expected_sha: str) -> tuple[dict, dict[str, bytes]]:
    with _layout_v3():
        return V1.verify_archive(archive, attestation, expected_sha)
