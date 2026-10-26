#!/usr/bin/env python3
"""Personal memory FM-2: the release contract `UPGRADE_FM2_RELATIONSHIP_ORIGIN_SIGNER_DEV_SYNTHETIC` (pure; SOURCE ONLY).

Record: docs/architecture/personal-memory-fm2-dev-activation.md. Nothing here is authorized to run on a host; every
mutating form of `fm2_release_stages` / `fm2_operator` needs its own owner go.

The installed release is the FM-1 NEW release (e2324a5, FM-1 F7, owner-accepted). The FM-2 release is the PR #264
merge (d82f7da, archive layout v3, `install_authority_dev_v3`, no added member). Its payload differs from the installed
one in exactly the two authority-signer members below; every recovery-witness member, unit, tmpfiles line, CLI, lock
and wheel is byte-identical (`recoveryWitnessReleaseDigest` c911b733 in both attestations):

    changed  lilith_authority_dev/protocol.py      the relationship-origin signer purpose (`SIGNER_PURPOSES`)
    changed  lilith_authority_root/cli.py          the read-only `first-memory-context` root form

The witness payload is unchanged, but the witness unit runs from the shared `current` selector with
`Restart=on-failure`, so the transition stops BOTH units before the select and starts the unchanged witness again from
NEW under its own owner go (one K-WIT and one K-PAN load), exactly the FM-1 order.

    contract != authorization;  a staged release != a selected release != an accepted incarnation
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Mapping

HERE = Path(__file__).resolve().parent
if not str(globals().get("__file__", "")).startswith("<mb6-bundle:") and str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import fm1_signer_upgrade as FM1  # noqa: E402

MODE = "UPGRADE_FM2_RELATIONSHIP_ORIGIN_SIGNER_DEV_SYNTHETIC"

# ------------------------------------------------------------------ releases ---
OLD_RELEASE = FM1.NEW_RELEASE                                    # e2324a5 (FM-1 F7)
OLD_MANIFEST_SHA256 = FM1.NEW_MANIFEST_SHA256
# The independently attested build of the PR #264 merge (A = B on Windows and WSL, attestation REPRODUCED).
NEW_RELEASE = "d82f7dac669f37c494beebf9bbb99dffdb6c23f5"
NEW_MANIFEST_SHA256 = "81a047657698c1903d1fd5cc30e725fdbbf3ea84ccf5b587f597ecba1be22d56"
# Build provenance (a record only; the archive is verified by its builder stamp and NEW_MANIFEST_SHA256).
NEW_RELEASE_ATTESTATION = {
    "archiveSha256": "9588c85b2ed424da8c10dcac17d49202b2436304fac830faeda7a172895889f4",
    "archiveByteSize": 5387827,
    "builderStampSha256": "c7fe0bb339776ea3e05c155516fd18abc1b352f71b15365c264a6d27f4543853",
    "attestationDigest": "c5bf54b628fb454b802fe81a6c6f93a4f6ad3fe15f2c63a4bd975940ff38f5c5",
    "buildRecipeSha256": "1e61c2bad664c34cfded59d7d5b6400ab6da659716fd7890836891e200e74b7b",
    "authorityReleaseDigest": "76568cee2c878aba0e5ee5743f28e049e90d726d9acd49d497b25588a0c54b56",
    "recoveryWitnessReleaseDigest": "c911b7334d97dfe3b9246832d5301a830771e3f41c3b2d6d86867519de16c2be",
    "identitySha256": "eea6e0b593887e154e1a3e099e41c0589249d410b5ee7cadff36c68068de622f",
    "evidenceManifestSha256": "fcf23a7721e9312281aa46f8cfe5060db8d6913bc6ddcd93f127d2de2289d4fa",
}

# ------------------------------------------------------------------ the delta ---
PAYLOAD_DELTA = {
    "lilith_authority_dev/protocol.py": (
        "e5ac085e360c4e5fce5e3d44f7caa27fb621ca684a69ad4f08c79c4e4a0ba99d",
        "8a082a125e0d9d2a2b3f79e6629f68463799f6530ba93e9e83461b7d210ff829"),
    "lilith_authority_root/cli.py": (
        "f65d1f48a14cf787591453afbe40d0ab62695eecc38e79b56772d427387dc544",
        "46f2156515b544770a264d538b183ba5f9d7fe869fb220623a565ffb62e56d07"),
}
PAYLOAD_ADDED: dict[str, str] = {}
# Archive layout v3 is the FM-1 layout: FM-2 adds no member, so the layout binding keeps FM-1's two additions.
LAYOUT_ADDED = dict(FM1.PAYLOAD_ADDED)


class Refused(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        super().__init__(reason if detail is None else f"{reason}:{detail}")
        self.reason = reason


def _need(condition: bool, reason: str, detail: str | None = None) -> None:
    if not condition:
        raise Refused(reason, detail)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def new_payload_pins(installed: Mapping[str, str]) -> dict[str, str]:
    """The expected NEW payload map from the COMPLETE installed payload map: exactly `PAYLOAD_DELTA` moves and exactly
    `PAYLOAD_ADDED` appears. Any other difference is refused."""
    pins = dict(installed)
    for member, (before, after) in PAYLOAD_DELTA.items():
        _need(pins.get(member) == before, "INSTALLED_MEMBER_PIN_UNEXPECTED", member)
        pins[member] = after
    for member, after in PAYLOAD_ADDED.items():
        _need(member not in pins, "ADDED_MEMBER_ALREADY_INSTALLED", member)
        pins[member] = after
    return pins


def check_payload(payloads: Mapping[str, bytes], installed: Mapping[str, str]) -> None:
    """A candidate NEW payload (member -> bytes) is admissible only if it is the installed payload moved by the delta."""
    expected = new_payload_pins(installed)
    extra = sorted(set(payloads) - set(expected))
    _need(not extra, "PAYLOAD_MEMBER_UNEXPECTED", ",".join(extra))
    for member, pin in sorted(expected.items()):
        _need(member in payloads, "PAYLOAD_MEMBER_MISSING", member)
        _need(_sha(payloads[member]) == pin, "PAYLOAD_DELTA_NOT_EXACT", member)
