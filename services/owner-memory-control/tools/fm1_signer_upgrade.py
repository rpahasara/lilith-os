#!/usr/bin/env python3
"""First Memory FM-1: the release contract `UPGRADE_FM1_FIRST_MEMORY_SIGNER_DEV_SYNTHETIC` (pure; SOURCE ONLY).

Record: docs/architecture/first-memory-fm1-release-transition.md. Nothing here is authorized to run on a host; every
mutating form of `fm1_release_stages` / `fm1_operator` needs its own owner go.

The installed release is the E-23 NEW release (57bff671, E-23 E8, owner-accepted). The FM-1 release is the PR #258
merge (e2324a5, archive layout v3, `install_authority_dev_v3`). Its payload differs from the installed one in exactly
the authority-signer members below; every recovery-witness member, unit, tmpfiles line, CLI, lock and wheel is
byte-identical (`recoveryWitnessReleaseDigest` c911b733 in both attestations):

    changed  lilith_authority_dev/{core,credential,ledger,profile,protocol,server}.py   RR-39 issuance + DEV wiring
    changed  lilith_authority_host/{inputs,paths}.py                                   owner registration reader
    changed  lilith_authority_root/{cli,clients}.py                                    First Memory root bridge
    added    lilith_authority_dev/issuance.py                                           the governed issuance path
    added    lilith_owner_memory/verifier.py                                            the owner-proof verifier

The witness payload is unchanged, but the witness unit runs from the shared `current` selector with
`Restart=on-failure`: a witness left running from OLD across the selector change would come back from NEW on any
failure, a version switch no owner approved. The transition therefore stops BOTH units before the select and starts
the unchanged witness again from NEW under its own owner go (one K-WIT and one K-PAN load), exactly the E-22 order.

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

import e23_privacy_anchor_upgrade as E23  # noqa: E402

MODE = "UPGRADE_FM1_FIRST_MEMORY_SIGNER_DEV_SYNTHETIC"

# ------------------------------------------------------------------ releases ---
OLD_RELEASE = E23.NEW_RELEASE                                    # 57bff671 (E-23 E8)
OLD_MANIFEST_SHA256 = E23.NEW_MANIFEST_SHA256
# The independently attested build of the PR #258 merge (A = B on Windows and WSL, attestation REPRODUCED).
NEW_RELEASE = "e2324a5f89200aa5f374c4a43a13cb76b36376f9"
NEW_MANIFEST_SHA256 = "a2f32664133bf3aff48f621e475f4b8455c3cff51ddb029df53c45ab191db859"
# Build provenance (a record only; the archive is verified by its builder stamp and NEW_MANIFEST_SHA256).
NEW_RELEASE_ATTESTATION = {
    "archiveSha256": "6924ed9f9b2f5339d2b5c992ae472949b2bc7472bcb8f9d45eb6380a4f9714e9",
    "archiveByteSize": 5384365,
    "builderStampSha256": "974b848b48716e8e0056aa76121c59b304e187f249028673b4dbb942e210f3a1",
    "attestationDigest": "c07701d09712cb823c8c14ff1671899cec08657664aa4ca3701d0e28e7f7fafb",
    "buildRecipeSha256": "ecfddc6ab91f9e5c5c1da4b99bfe65d42f7e80299762c698a1c905c09baaded2",
    "authorityReleaseDigest": "325b378f0cdf4c9f314c5e455c3832179736ced1716537093eba6ff33bc6ba1d",
    "recoveryWitnessReleaseDigest": "c911b7334d97dfe3b9246832d5301a830771e3f41c3b2d6d86867519de16c2be",
    "identitySha256": "decd8c9d174034c94de6386d04bd7239f6969bef12131b30743ee1a3981f3917",
    "evidenceManifestSha256": "e7c7312005a0fc730e82f98422557684f193de0407f248e97646ec694fb88f03",
}

# ------------------------------------------------------------------ the delta ---
PAYLOAD_DELTA = {
    "lilith_authority_dev/core.py": (
        "a25b371b6017688000c81740a49887517bb0004d18866613cfedb623dd193c05",
        "c72c1a8c8483ab78e59940d8ff05a3553120d9149dee368f3b8c7a7b02e84542"),
    "lilith_authority_dev/credential.py": (
        "aea8912f84afbc3d762b35638f19e4e9e6fe0cef22b90f5b51bccd4d9e3784da",
        "347b72a401b415b593bc42f10436d2c275f7512bbd4829a254cd022196e0c4ae"),
    "lilith_authority_dev/ledger.py": (
        "2853f2d73f8db1173207fd034d9d40cc317472bf429e85b1638e45c16d542f1a",
        "1bac9b621203b3219466eaf795c22ff81ccded9d82fc731483567f6bdff9dca3"),
    "lilith_authority_dev/profile.py": (
        "cf291af50ff5738ff7fdc3acc50eaf95dfb4c3c7128589b8f1927fb32652710a",
        "40f7301d149b569a40fefcf8d840c0c11e66bb2948dbc68a855c4bb025a578ed"),
    "lilith_authority_dev/protocol.py": (
        "4cd1154b4d36b4ff29083e597b77a50ecfd653bc1cc4519fb7dcc6b09353a25a",
        "e5ac085e360c4e5fce5e3d44f7caa27fb621ca684a69ad4f08c79c4e4a0ba99d"),
    "lilith_authority_dev/server.py": (
        "c6c2fdeb173125d488d8b9366dd05ffa882f2f5107125cca48da50f6eadc2353",
        "11ad88aea9a530cbcfafa2eb01fc5df10d825cfa72a350c11dd3f916cee76be1"),
    "lilith_authority_host/inputs.py": (
        "775d521a197372f252cd718877f74e7902b8e9f7fee79bdd843115131a0ea299",
        "cd54bbe4df37550c740eb223479fef5eb4fa672074d992c7ab73d8b31544e038"),
    "lilith_authority_host/paths.py": (
        "d95171b91c126da983a3ec2cc864b1875dd333b0b0d638eacf8645e93d52c55e",
        "f17ecd7322b8a57cb02315557cbe2626fdc574cc5ef3a2f90fa79786810635f9"),
    "lilith_authority_root/cli.py": (
        "7175577c0bdbf52b7ad6fd56d8e5818a144d955c386ac452b768b4e5000cf10a",
        "f65d1f48a14cf787591453afbe40d0ab62695eecc38e79b56772d427387dc544"),
    "lilith_authority_root/clients.py": (
        "f6840254b0ef4abc7150077ab58612e8652472fac9caa71e778eecde3e4c328f",
        "3c7fb74b0c61f74c91a32837aacfd5132dc8fce55c1a4a0225ff8a5594c8b54b"),
}
PAYLOAD_ADDED = {
    "lilith_authority_dev/issuance.py": "8d5e20b8674ebf57daac297d47a561dafd89254eb164eb6b0b10b4aa8ca243d8",
    "lilith_owner_memory/verifier.py": "4e119272430d529a64df0666b0dea4f70c413731d990f905f2dbb8784625789c",
}


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
