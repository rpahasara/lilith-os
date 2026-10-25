#!/usr/bin/env python3
"""Track B B4: the PROPOSED release contract `UPGRADE_E23_PRIVACY_ANCHOR_DEV_SYNTHETIC` (pure; SOURCE ONLY).

Record: lilith-hermes-staging f9c/trackb (TRACKB-B2-RESULT.md, TRACKB-B3B4 package). Nothing here is authorized to run
on a host: there is no stage, stop, select, start or retire form (that live-ladder tooling is a separate tranche).

The installed release is the E-22 NEW release (129f2be, E-22 V7, owner-accepted). The E-23 payload differs from it in
exactly these members, all on the recovery-witness side (the authority signer imports none of them, so the signer
payload is byte-identical; its process must still move off OLD before OLD can be retired, the E-22 rule):

    changed  lilith_recovery_witness/credential.py        + PrivacyAnchorSigningKeyV1 (K-PAN), K-WIT unchanged
    changed  lilith_recovery_witness/server.py            owner-socket-only routing of the anchor protocol id
    changed  assets/lilith-recovery-witness.service       + LoadCredentialEncrypted K-PAN, + anchor state path
    changed  assets/lilith-recovery-witness.tmpfiles.conf + d /var/lib/lilith-privacy-anchor 0700 witness
    added    lilith_recovery_witness/privacy_anchor.py    the K-PAN anchor service
    added    lilith_memory/privacy_anchor_contracts.py    the pure contract (SHARED_HASHES addition)

Host pins of the installed release (the M-B6 module pins, the E-19 restart-boundary unit fragment `9f78130c`) stay on
OLD until the transition completes; tests prove the delta against `git show OLD_RELEASE:<source>`.

Live ordering constraint (for the later ladder): the K-PAN encrypted credential must exist BEFORE the new witness unit
is loaded, because `LoadCredentialEncrypted=` fails the witness start otherwise; the anchor state directory comes from
the new tmpfiles line.

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

import e22_judge_upgrade as E22  # noqa: E402

MODE = "UPGRADE_E23_PRIVACY_ANCHOR_DEV_SYNTHETIC"
STATUS = "PROPOSED_NOT_ACCEPTED"

# ------------------------------------------------------------------ releases ---
OLD_RELEASE = E22.NEW_RELEASE                                    # 129f2be (E-22 V7)
OLD_MANIFEST_SHA256 = E22.NEW_MANIFEST_SHA256
# The PROPOSED pin of the independently attested build (record trackb-e23-new-release-pin.md, NOT APPROVED until the
# owner reviews and merges it). NEW_RELEASE is the SOURCE commit the archive was built from (the PR #251 merge), never
# the commit carrying this pin.
NEW_RELEASE: str | None = "57bff671fbfe5df4e59248d5d69338dc0ba05846"
NEW_MANIFEST_SHA256: str | None = "fc29a23cbb411704f2799b418f8c7fd7fadf215489174e9ac9d370db2e78368c"
# Build provenance (a record only; the archive is verified by its builder stamp and NEW_MANIFEST_SHA256).
NEW_RELEASE_ATTESTATION = {
    "archiveSha256": "a8cadbfa75023ed19c6939b17841e56f1ad9d0b83a6f854755621e32ed174486",
    "archiveByteSize": 5367662,
    "builderStampSha256": "3972c9a7f899df0e7c1d0cad2d52d267cb2e4decefd876ea17c3f63b05fed32e",
    "attestationDigest": "3f18fd50f0269c1e72e537e996b2a38de8369b0ed4da6150ee597cd5299f4b90",
    "buildRecipeSha256": "5e687a8e06d6c937a6ac088c055d603d581000cf413fe8d2a42a4c813a580130",
    "authorityReleaseDigest": "4475c3c408571a7cba0a0f705c360ae1a6df02486a7d32c710531a8fd2ed16b7",
    "recoveryWitnessReleaseDigest": "c911b7334d97dfe3b9246832d5301a830771e3f41c3b2d6d86867519de16c2be",
    "identitySha256": "409874ff7c5e216b613f0bf649ea66443c1ec81f52b8f69277c8e0f1ef45f40e",
    "evidenceManifestSha256": "3ca5bbe1a2e24a5d24fd29fde4c297e26c7438869760ac53052206ba2d15ff68",
}

# ------------------------------------------------------------------ the delta ---
PAYLOAD_DELTA = {
    "lilith_recovery_witness/credential.py": (
        "7a394b561df072f5ec5ed933ab04deca450cfd84bf23f3fcf166b0c068916c18",
        "68da7a17a46b41e468226cb73369ebd1ae3709150223674a2ddcc1b153f070a7"),
    "lilith_recovery_witness/server.py": (
        "1d709a17ba9bd036628c4207f627be1cee305636cc078f34c2f3b94cae292c6f",
        "6bb19ffb1b5a62555161ca6bb29b0dfc90b955dd2fe1fd2121840ae4c0d4f6f2"),
    "assets/lilith-recovery-witness.service": (
        "9f78130c06491d184aff7066de99f804bf3816e171c63d6f70b734b1c6e85d7d",
        "b3e2c753c6facea0691752c4894f28ce3f2fe3738f31cf3baa75a25af1d011c1"),
    "assets/lilith-recovery-witness.tmpfiles.conf": (
        "c3491d517aa70ff960e1dba4410378efcecc134737282136aad77a5a9d200be0",
        "9fd8a2eca10fdc397899c9e80de5711f21cbe1179711c5d6b3e0bd8a1b5ed4e5"),
}
PAYLOAD_ADDED = {
    "lilith_recovery_witness/privacy_anchor.py": "9d7d7c37f7ef9b86754ed693e6c0acfd3b38c3fa2865d901f5578ee88652644d",
    "lilith_memory/privacy_anchor_contracts.py": "58e954af7988115740fee8097d8d3248f47861a7b4046fc63bf9b0f3903fd768",
}
WITNESS_UNIT = "assets/lilith-recovery-witness.service"
KPAN_CREDENTIAL_NAME = "privacy-anchor-signing-key"
KPAN_KEY_ID = "kpan.dev-synthetic.01"
KPAN_CREDENTIAL_BLOB = "/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.privacy-anchor.cred"
ANCHOR_STATE_DIR = "/var/lib/lilith-privacy-anchor"


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
