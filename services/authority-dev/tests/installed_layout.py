"""Track B B4 test helper: the INSTALLED (E-22 NEW, 129f2be) release payload for fixtures that stage through the
byte-identical V1 installer.

Until Track B, the repository payload WAS the installed payload, so fixtures built "the release" from the tree. The
tree now carries the proposed E-23 payload (archive layout v2, `install_authority_dev_v2`), which V1 rightly refuses.
Fixtures that model the installed host or the historical E-19 / E-22 transitions therefore build the installed
layout: every runtime member at its 129f2be bytes (`git show`), and the two E-23 additions absent. CLIs, the lock and
the wheels are unchanged by E-23 and are taken from the build as before. CI checks out full history.

RR-39 moved the tree on to archive layout v3 (`install_authority_dev_v3`, two more runtime members). `_build_v2` is
therefore the E-23 NEW (57bff671) payload itself, every runtime member at its 57bff671 bytes and the v3 additions
absent, and the installed layout drops both successors' additions.
"""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OLD_RELEASE = "129f2bed617334be61dcac5204cd409946a7a566"
E23_RELEASE = "57bff671fbfe5df4e59248d5d69338dc0ba05846"         # the installed E-23 NEW release (archive layout v2)


@lru_cache(maxsize=None)
def old_source_bytes(source: str, release: str = OLD_RELEASE) -> bytes:
    return subprocess.run(["git", "show", f"{release}:{source}"], cwd=ROOT, capture_output=True,
                          check=True).stdout


def installed_layout(payloads: dict[str, bytes]) -> dict[str, bytes]:
    import install_authority_dev_v2 as I2
    import install_authority_dev_v3 as I3
    import release_file_set as RFS

    source_of = {target: source for source, target in RFS.RUNTIME_SOURCE_MAP.items()}
    out = {}
    for member, data in payloads.items():
        if member in I2.ADDED_RUNTIME_PATHS | I3.ADDED_RUNTIME_PATHS:
            continue
        source = source_of.get(member)
        out[member] = old_source_bytes(source) if source is not None else data
    return out


def installed_build_payloads(root: Path, wheelhouse: Path) -> dict[str, bytes]:
    """`build_authority_dev_release.build_payloads`, in the installed (V1) layout and bytes."""
    import install_authority_dev as I
    import install_authority_dev_v2 as I2

    payloads = installed_layout(_build_v2(root, wheelhouse))
    I.check_payloads(payloads)                          # the installed layout is a valid V1 release
    assert set(payloads) == I2.EXPECTED_PATHS - I2.ADDED_RUNTIME_PATHS
    return payloads


def _build_v2(root: Path, wheelhouse: Path) -> dict[str, bytes]:
    """The E-23 NEW payload (archive layout v2): the build with every runtime member at its 57bff671 bytes."""
    import build_authority_dev_release as B
    import install_authority_dev_v2 as I2
    import install_authority_dev_v3 as I3
    import release_file_set as RFS

    source_of = {target: source for source, target in RFS.RUNTIME_SOURCE_MAP.items()}
    payloads = {}
    for member, data in B.build_payloads(root, wheelhouse).items():
        if member in I3.ADDED_RUNTIME_PATHS:
            continue
        source = source_of.get(member)
        payloads[member] = old_source_bytes(source, E23_RELEASE) if source is not None else data
    I2.check_payloads(payloads)                         # a valid archive layout v2 release
    return payloads


FM1_RELEASE = "e2324a5f89200aa5f374c4a43a13cb76b36376f9"         # the installed FM-1 NEW release (archive layout v3)


def build_fm1(root: Path, wheelhouse: Path) -> dict[str, bytes]:
    """The FM-1 NEW payload (archive layout v3): the build with every runtime member at its e2324a5 bytes. The tree
    has moved on (relationship origin changes `lilith_authority_dev/protocol.py`), as it moved past 57bff671."""
    import build_authority_dev_release as B
    import release_file_set as RFS

    source_of = {target: source for source, target in RFS.RUNTIME_SOURCE_MAP.items()}
    return {member: old_source_bytes(source_of[member], FM1_RELEASE) if member in source_of else data
            for member, data in B.build_payloads(root, wheelhouse).items()}
