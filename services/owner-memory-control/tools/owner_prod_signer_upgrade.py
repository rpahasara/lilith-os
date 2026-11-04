#!/usr/bin/env python3
"""OWNER_PROD P3: the DEV release contract `UPGRADE_OWNER_PROD_PROFILE_DEV_SYNTHETIC` (pure; SOURCE ONLY; PREPARED).

Record: docs/architecture/canonical-memory-p3-release-preparation.md. Nothing here is authorized to run on a host.

OLD is the installed FM-2 release (d82f7da, archive 9588c85b). NEW is the attested build of the collapsed OWNER_PROD
stack's merge into main (rpahasara/lilith-os#312, merge 88a1168): built A = B on Windows and WSL, attestation
REPRODUCED, exactly as FM-2 pinned its NEW after #264. Its payload differs from OLD in exactly these 18 members and the
release manifest, byte-identical to the rehearsal build of the P3 source (706873c, archive f22bf71b, manifest b136366b). None is added or removed; units, tmpfiles,
CLIs, lock and wheels are byte-identical, so archive layout v3 and `install_authority_dev_v3` apply unchanged.

Two of the members are recovery-witness code (`credential.py`, `server.py`), so the transition stops BOTH units before
the select and starts the witness from NEW (one K-WIT and one K-PAN load), then the signer (one K-ACT load), the FM-1 /
FM-2 order. The DEV host keeps DEV_SYNTHETIC: it has no `deployment.json`, and every DEV value is byte-identical
(test_owner_prod_profile, the DEV-values comparison).

    contract != authorization;  a staged release != a selected release != an accepted incarnation
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Mapping, Optional

HERE = Path(__file__).resolve().parent
if not str(globals().get("__file__", "")).startswith("<mb6-bundle:") and str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import fm2_signer_upgrade as FM2  # noqa: E402

MODE = "UPGRADE_OWNER_PROD_PROFILE_DEV_SYNTHETIC"

# ------------------------------------------------------------------ releases ---
OLD_RELEASE = FM2.NEW_RELEASE                                    # d82f7da (FM-2 F7)
OLD_MANIFEST_SHA256 = FM2.NEW_MANIFEST_SHA256
OLD_ARCHIVE_SHA256 = FM2.NEW_RELEASE_ATTESTATION["archiveSha256"]
# The independently attested build of the #312 merge (A = B on Windows and WSL, attestation REPRODUCED).
NEW_RELEASE: Optional[str] = "88a1168bd41797109772ffce7df7352c1ae40e4c"
NEW_MANIFEST_SHA256: Optional[str] = "072001af671feca6564906d3d685f89bfc608f9d595aed58bae0f72a25777684"
# Build provenance (a record only; the archive is verified by its builder stamp and NEW_MANIFEST_SHA256).
NEW_RELEASE_ATTESTATION = {
    "archiveSha256": "53ae457b8b907e12282ed468da0387620b7a376a46ab1c450709b67540b43c07",
    "archiveByteSize": 5391582,
    "builderStampSha256": "05346fc48dc473f477168fcb43661cc45f66adb64cf068cd6e2a98eec83111af",
    "attestationDigest": "b2f08910794cdd585c15b53c3568136a8ee0a67e7791ebf484609e1e08204f90",
    "buildRecipeSha256": "baa80670562d019a5aaed943604397754368e4cee040dbac75434774a12b3aa0",
    "authorityReleaseDigest": "4067cd5da8380fa8278c6942b08fdc66b021ab818d32de463010ccdef3c0de12",
    "recoveryWitnessReleaseDigest": "ccc9c5bfed6e2fcba0b584d364deb578232d4429bfbb8657eb4049ac3ec6c790",
    "identitySha256": "1dafd1c9bb2045443f7579d28d496bf7dbe8a5015ff6c30a70c83a040248553a",
    "evidenceManifestSha256": "ef5ee745abea9a65c3f1ecd72b06ea0ebd95132f1bc8b274d8b355d72697aabc",
}
# The rehearsal build of the P3 source: evidence that the delta below is exact, never an installable NEW.
REHEARSAL = {
    "candidateSha": "706873c48edfe9efc0d3363aaa8ea910772e18d9",
    "archiveSha256": "f22bf71b437a2c99cefb8c08d1502a5f8f826de06ed1fb295a8e19e01f837622",
    "archiveByteSize": 5391581,
    "manifestSha256": "b136366bfd1615fa90177e91d9c6e9ea5f0f9fab3eae167237fba9b04569fa6b",
    "builderStampSha256": "33a21570b70160b0cbdb7c40a1ebf43a21533f0ce2218eef67a57a6de0790be8",
    "identitySha256": "6f5d1c044534b2df8cd3e9ffaff8992c0ec630a68eae1488b6d89b115c5f0c5c",
}

# ------------------------------------------------------------------ the delta ---
PAYLOAD_DELTA = {
    "lilith_authority_dev/core.py": (
        "c72c1a8c8483ab78e59940d8ff05a3553120d9149dee368f3b8c7a7b02e84542",
        "d71a66ceaea8f76ec4700afd7f480eb80bb8ac3f1e77b9a63a1ebb95848847e0"),
    "lilith_authority_dev/evidence_minter.py": (
        "da3228a04c6a54bd679e94224d4c42d998faf64cbe4bbf2df5247daa9b9390c3",
        "a61140a8529445ecb766b6695dc31e6c8c2bef13edd037745449d5663510d742"),
    "lilith_authority_dev/ledger.py": (
        "1bac9b621203b3219466eaf795c22ff81ccded9d82fc731483567f6bdff9dca3",
        "e87f9c2034dfbed8c7bcc62e1df3392ab055ebc7ed1a2a7f0b5ce585ebdeb4ef"),
    "lilith_authority_dev/profile.py": (
        "40f7301d149b569a40fefcf8d840c0c11e66bb2948dbc68a855c4bb025a578ed",
        "1e5ff394b1577391f241fe0aca0c7447ad36b82dd8d9b9d10bcfd7648c408f2e"),
    "lilith_authority_dev/recovery.py": (
        "8fa923934ad7977eef1a5764929b3b24688f9feec3540fe1f6cba986c669a565",
        "af0ffad0fb208c81651fe2a4e34e38e0fd713a19dceec9ec595631f0904ac658"),
    "lilith_authority_dev/server.py": (
        "11ad88aea9a530cbcfafa2eb01fc5df10d825cfa72a350c11dd3f916cee76be1",
        "23e4c651a540c794540a3b02fb1571915a884a76f1424a228556696b08550e1e"),
    "lilith_authority_host/inputs.py": (
        "cd54bbe4df37550c740eb223479fef5eb4fa672074d992c7ab73d8b31544e038",
        "7396e4783f860022752d08e7a079c9ca7a12b8e7e859275693d70da7fac08776"),
    "lilith_authority_host/paths.py": (
        "f17ecd7322b8a57cb02315557cbe2626fdc574cc5ef3a2f90fa79786810635f9",
        "6ddae81790f15a28951414ff6d9314916a6035bb35e0cbceed89aa3c7b71f636"),
    "lilith_authority_root/cli.py": (
        "46f2156515b544770a264d538b183ba5f9d7fe869fb220623a565ffb62e56d07",
        "33db13e60562af6ff59651bf83f916d5335968ca33dfe81015e073b63d9af94c"),
    "lilith_owner_memory/authority_contracts.py": (
        "fabd8fd24f45febe83f8fd67c3fc39f277278e9145df9c55d5e03e5e8598e74f",
        "2f7dde524e4944182a7adb351ab865336162549673f3944c8cb9a75add42bd02"),
    "lilith_owner_memory/authority_verifier.py": (
        "3c808267e56e9abc1ea1e848881cefd20a56fde51d9e803ac90f7f0c7517e83a",
        "093b77d6192c46ec07aaad5d8bd2321f3fdcdd56ebf716df40dff18286e94052"),
    "lilith_owner_memory/pr1_bootstrap.py": (
        "9a09a4726bb473067e84e7664dca49d51b90ced1e012564526bae07656d3d5fd",
        "ed21bbf9f97623633f8e8c8f52869ebe75f937f4fecd788f29e0eeb858ad8e48"),
    "lilith_owner_memory/recovery_contracts.py": (
        "f4a14cff094d167a2a7925622031352955291c18244545e95c0003fb9231b95e",
        "6bfd45d3943ed046dbce64039f1b889b93363e8b9d2e6c8e28cec5d422612e51"),
    "lilith_owner_memory/rotation_contracts.py": (
        "8f9df8dcd3e8a1b0cd8f03169bf7a51d4b6726cbb708cadfb3025586211996b0",
        "181acda2fd4c68aca7051669a04da43b07d72984e724e906481dfda7280fe70d"),
    "lilith_owner_memory/successor_custody.py": (
        "29e99a7b179d58dd4f8e9cd576ed544f207145f25f89c92e97ca0e6efa65cb72",
        "8b1da78c000f16ec843683329b59d25b99b1d10dce6527e1815b84952c6cb6e9"),
    "lilith_owner_memory/verifier.py": (
        "4e119272430d529a64df0666b0dea4f70c413731d990f905f2dbb8784625789c",
        "6f214b8ff5d3b87f2ba2f0159df3dce03e4cbc092b38249265ac5f50908e2cbd"),
    "lilith_recovery_witness/credential.py": (
        "68da7a17a46b41e468226cb73369ebd1ae3709150223674a2ddcc1b153f070a7",
        "a37a52f2796564369fe9d33d9bdef8d46542439b708597a5ff780a40a3c6804a"),
    "lilith_recovery_witness/server.py": (
        "6bb19ffb1b5a62555161ca6bb29b0dfc90b955dd2fe1fd2121840ae4c0d4f6f2",
        "47c79be7ec44353b371f11fd9107610133f0f6f199a526044d7eb6e463378e5a"),
}
PAYLOAD_ADDED: dict[str, str] = {}
LAYOUT_ADDED = dict(FM2.LAYOUT_ADDED)                          # layout v3 unchanged
WITNESS_MEMBERS = frozenset(m for m in PAYLOAD_DELTA if m.startswith("lilith_recovery_witness/"))


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
    """The expected NEW payload map from the COMPLETE installed payload map: exactly `PAYLOAD_DELTA` moves."""
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


def ready_to_transition() -> bool:
    """True only once NEW is pinned from the attested merge build: no stage or operator may run before that."""
    return isinstance(NEW_RELEASE, str) and isinstance(NEW_MANIFEST_SHA256, str)
