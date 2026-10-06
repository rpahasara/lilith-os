#!/usr/bin/env python3
"""15B2b-B1b-3e M-B4/M-B5: READ-ONLY pre-ledger content verifier for INSTALL_TRUST_AND_REGISTRY (DEV).

Record: docs/architecture/slice-15b2b-b1b3e-mb4-mb5-trust-install-remediation.md §5.

It produces, from the authoritative observed on-host content, the three
evidence items the sequencer requires for `INSTALL_TRUST_AND_REGISTRY`
(`pr1b_sequencing.STEPS`, M-B4+M-B5):

    anchorsEqualOwnerCopies   witnessAnchorNamesKWit   registryVerifiesOnHost

Each is a content result: exact bytes against the owner-derived
representation pins, parsed by the installed release's own runtime reader
(`lilith_authority_host.inputs.read_host_inputs`), and for the registry the
K-ROOT signature verified under the *installed* root anchor. It also
classifies the crash window (W0 … W5) the host is in. It is never a
shape-only check: `install_authority_dev.py status` stays the owner of the
path/mode contract.

It runs on DEV as root with the installed release interpreter and imports
only the selected release tree. Stream it like the installer:

    echo <gzip+base64> | base64 -d | gunzip | \\
        sudo /opt/lilith-authority-dev/current/venv/bin/python -I -B - observe

It takes no path argument. It uses `lstat`, directory listings and bounded
`O_NOFOLLOW` reads of the three public M-B4/M-B5 files only. It never opens
a credential, the credstore, the host credential key or the K-WIT blob; never
decrypts, signs, starts, stops, reloads or enables anything; never creates,
writes, chmods or removes a path; and contacts nothing.

    observation != installation        content verified != registry effective
    TRUST_INSTALLED candidate != owner acceptance != genesis != authority
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

VERIFIER_TYPE = "LILITH_MB4_MB5_TRUST_INSTALL_VERIFICATION"
ENVIRONMENT = "dev"
DEV_HOSTNAME = "lilith-dev-01"
DEV_MACHINE_ID = "ae929170e6fa4c8ab9cc7b9547238d9d"
RELEASE_TREE = "/opt/lilith-authority-dev/current"
MAX_DOCUMENT = 64 * 1024

TRUST_DIR = "/etc/lilith-authority-dev/trust"
REGISTRY_DIR = "/etc/lilith-authority-dev/registry"
OWNER_INPUT_DIR = "/etc/lilith-authority-dev/owner"
ROOT_ANCHOR = TRUST_DIR + "/registry-root.json"
WITNESS_ANCHOR = TRUST_DIR + "/witness-anchor.json"
REGISTRY = REGISTRY_DIR + "/authority-registry.v1.json"
TARGETS = (ROOT_ANCHOR, WITNESS_ANCHOR, REGISTRY)
# M-B6 and later state. While all are absent the host is pre-ledger.
LATER_STATE = ("/var/lib/lilith-authority-dev", "/var/lib/lilith-recovery-witness")
# The only host-input reasons a complete M-B4/M-B5 leaves (M-B8 installs these).
EXPECTED_AFTER_MB5 = frozenset({"GENESIS_PIN_COPY_MISSING", "AUTHORIZATION_REGISTER_COPY_MISSING"})

EVIDENCE = ("anchorsEqualOwnerCopies", "witnessAnchorNamesKWit", "registryVerifiesOnHost")

# Crash-window phases (remediation record §6).
W0_PRE_INSTALL = "W0_PRE_INSTALL"
W1_ROOT_ANCHOR_INCOMPLETE = "W1_ROOT_ANCHOR_INCOMPLETE"
W2_WITNESS_ANCHOR_INCOMPLETE = "W2_WITNESS_ANCHOR_INCOMPLETE"
W3_ANCHORS_INSTALLED = "W3_ANCHORS_INSTALLED_REGISTRY_ABSENT"
W4_REGISTRY_INCOMPLETE = "W4_REGISTRY_INCOMPLETE"
W5_INSTALLED_CONTENT_VERIFIED = "W5_INSTALLED_CONTENT_VERIFIED"
W5_INSTALLED_CONTENT_NOT_VERIFIED = "W5_INSTALLED_CONTENT_NOT_VERIFIED"
UNEXPECTED = "UNEXPECTED_STATE"
POST_LEDGER = "OUT_OF_SCOPE_POST_LEDGER"
PHASES = (W0_PRE_INSTALL, W1_ROOT_ANCHOR_INCOMPLETE, W2_WITNESS_ANCHOR_INCOMPLETE, W3_ANCHORS_INSTALLED,
          W4_REGISTRY_INCOMPLETE, W5_INSTALLED_CONTENT_VERIFIED, W5_INSTALLED_CONTENT_NOT_VERIFIED, UNEXPECTED,
          POST_LEDGER)


@dataclass(frozen=True)
class TrustInstallPinsV1:
    """Accepted public identities and the owner-derived representation pins."""

    root_anchor_sha256: str
    witness_anchor_sha256: str
    registry_sha256: str
    registry_digest: str
    kroot_public_key_sha256: str
    root_key_id: str
    kwit_public_key_sha256: str
    kwit_key_id: str
    kact_public_key_sha256: str
    kact_key_id: str
    epoch_random: str
    policy_version: str


# Owner decision record §2–§4; remediation record §3 (derived twice, byte-equal).
ACCEPTED_PINS = TrustInstallPinsV1(
    root_anchor_sha256="bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687",
    witness_anchor_sha256="be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a",
    registry_sha256="46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e",
    registry_digest="fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc",
    kroot_public_key_sha256="cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf",
    root_key_id="test-only.registry-root.dev-synthetic.b1b3d.1",
    kwit_public_key_sha256="5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf",
    kwit_key_id="test-only.witness.dev-synthetic.b1b3d.1",
    kact_public_key_sha256="dd13a1fb302375a4e7ec81131a72920e23e365e06a0b6dc9bb7ab124dadc01ed",
    kact_key_id="test-only.dev-synthetic.actor.b1b3d.1",
    epoch_random="11f184889f333dece054f3b91a301632",
    policy_version="policy.dev-synthetic.v1",
)


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _sha(data: bytes) -> str:
    return hashlib.sha256(bytes(data)).hexdigest()


def _host(root: Path, absolute: str) -> Path:
    return root / absolute.lstrip("/")


def _listing(root: Path, absolute: str) -> list[str] | None:
    path = _host(root, absolute)
    try:
        meta = os.lstat(path)
    except FileNotFoundError:
        return None
    if not stat.S_ISDIR(meta.st_mode):
        return ["<not-a-directory>"]
    return sorted(os.listdir(path))


def _observe_file(root: Path, absolute: str, *, owner_uid: int, owner_gid: int) -> dict[str, Any]:
    """ABSENT, or the exact facts and SHA-256 of a bounded regular file (never through a symlink)."""
    path = _host(root, absolute)
    try:
        meta = os.lstat(path)
    except FileNotFoundError:
        return {"state": "ABSENT"}
    facts: dict[str, Any] = {"state": "PRESENT", "regular": stat.S_ISREG(meta.st_mode),
                             "uid": meta.st_uid, "gid": meta.st_gid, "mode": format(stat.S_IMODE(meta.st_mode), "04o"),
                             "size": meta.st_size}
    if not facts["regular"] or meta.st_size > MAX_DOCUMENT:
        return dict(facts, sha256=None, metadataExact=False)
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    try:
        data = b""
        while chunk := os.read(fd, 65536):
            data += chunk
            if len(data) > MAX_DOCUMENT:
                return dict(facts, sha256=None, metadataExact=False)
    finally:
        os.close(fd)
    exact = (meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode)) == (owner_uid, owner_gid, 0o644)
    return dict(facts, sha256=_sha(data), metadataExact=exact)


def _release_modules():
    from lilith_authority_host import inputs as HI
    from lilith_owner_memory import authority_contracts as A
    from lilith_owner_memory import authority_verifier as AV
    from lilith_owner_memory import rotation_contracts as RC
    return HI, A, AV, RC


def evaluate(*, root: Path | str = Path("/"), owner_uid: int = 0, owner_gid: int = 0,
             pins: TrustInstallPinsV1 = ACCEPTED_PINS) -> dict[str, Any]:
    """One read-only observation and judgment. `root`, `owner_*` and `pins` are TEST seams."""
    HI, A, AV, RC = _release_modules()
    root = Path(root)
    expected = {ROOT_ANCHOR: pins.root_anchor_sha256, WITNESS_ANCHOR: pins.witness_anchor_sha256,
                REGISTRY: pins.registry_sha256}
    files = {path: _observe_file(root, path, owner_uid=owner_uid, owner_gid=owner_gid) for path in TARGETS}
    exact = {path: files[path]["state"] == "PRESENT" and files[path].get("metadataExact") is True
             and files[path].get("sha256") == expected[path] for path in TARGETS}
    present = {path: files[path]["state"] == "PRESENT" for path in TARGETS}
    listings = {directory: _listing(root, directory) for directory in (TRUST_DIR, REGISTRY_DIR, OWNER_INPUT_DIR)}
    later = {path: os.path.lexists(_host(root, path)) for path in LATER_STATE}
    failures: list[str] = []

    trust_names = {Path(ROOT_ANCHOR).name, Path(WITNESS_ANCHOR).name}
    trust_extra = listings[TRUST_DIR] is None or not set(listings[TRUST_DIR]) <= trust_names
    registry_extra = listings[REGISTRY_DIR] is None or not set(listings[REGISTRY_DIR]) <= {Path(REGISTRY).name}
    pre_ledger = not any(later.values()) and listings[OWNER_INPUT_DIR] == []
    if trust_extra:
        failures.append("TRUST_DIRECTORY_UNEXPECTED")
    if registry_extra:
        failures.append("REGISTRY_DIRECTORY_UNEXPECTED")
    if not pre_ledger:
        failures.append("NOT_PRE_LEDGER")

    host = HI.read_host_inputs(environment=ENVIRONMENT, root=root, owner_uid=owner_uid)
    reasons = set(host.reasons)

    # 1. anchorsEqualOwnerCopies: exact owner-derived bytes, accepted by the runtime reader
    anchors_equal = (exact[ROOT_ANCHOR] and exact[WITNESS_ANCHOR] and not trust_extra
                     and sorted(listings[TRUST_DIR] or []) == sorted(trust_names)
                     and host.registry_root is not None and host.witness_anchor is not None
                     and _sha(host.documents.get(ROOT_ANCHOR, b"")) == pins.root_anchor_sha256
                     and _sha(host.documents.get(WITNESS_ANCHOR, b"")) == pins.witness_anchor_sha256
                     and not reasons & {"REGISTRY_ROOT_ANCHOR_MISSING", "REGISTRY_ROOT_ANCHOR_INVALID",
                                        "WITNESS_ANCHOR_MISSING", "WITNESS_ANCHOR_INVALID",
                                        "INPUT_ENVIRONMENT_MISMATCH"})
    if not anchors_equal:
        failures.append("ANCHORS_NOT_EQUAL_OWNER_COPIES")

    # 2. witnessAnchorNamesKWit: the installed anchor is exactly K-WIT, distinct from every authority key
    root_key = host.registry_root
    witness = host.witness_anchor
    names_kwit = (witness is not None and exact[WITNESS_ANCHOR]
                  and witness.witness_key_id == pins.kwit_key_id and witness.environment == ENVIRONMENT
                  and _sha(witness.public_key) == pins.kwit_public_key_sha256
                  and witness.public_key not in HI.authority_public_keys(host))
    if not names_kwit:
        failures.append("WITNESS_ANCHOR_NOT_KWIT")

    # 3. registryVerifiesOnHost: the installed bytes, read by the runtime, verify under the installed E-21 root
    registry_ok = False
    registry_digest = None
    if (exact[REGISTRY] and anchors_equal and root_key is not None and len(host.registries) == 1
            and listings[REGISTRY_DIR] == [Path(REGISTRY).name]
            and _sha(host.documents.get(REGISTRY, b"")) == pins.registry_sha256):
        registry = host.registries[0]
        try:
            registry_digest = RC.registry_digest(registry)
            context = A.AuthorityVerificationContextV1(
                environment=ENVIRONMENT, purpose=A.NEW_ADMISSION, registry_root=root_key,
                trusted_minimum_registry_version=1,
                expected_recovery_epoch=A.RecoveryEpochV1(1, pins.epoch_random), policy_version=pins.policy_version)
            verified = AV.verify_authority_registry(context=context, registry=registry)
            keys = registry.get("keys", [])
            registry_ok = (verified.verified and registry_digest == pins.registry_digest
                           and registry.get("registryVersion") == 1 and registry.get("environment") == ENVIRONMENT
                           and _sha(root_key.public_key) == pins.kroot_public_key_sha256
                           and root_key.root_key_id == pins.root_key_id
                           and registry.get("registryRootKeyId") == pins.root_key_id
                           and len(keys) == 1 and keys[0].get("keyId") == pins.kact_key_id
                           and _sha(A._public_key(keys[0]["publicKey"])) == pins.kact_public_key_sha256
                           and (witness is None or witness.public_key != A._public_key(keys[0]["publicKey"]))
                           and reasons <= EXPECTED_AFTER_MB5)
        except Exception:  # noqa: BLE001 - any malformed installed content fails closed
            registry_ok = False
    if not registry_ok:
        failures.append("REGISTRY_NOT_VERIFIED_ON_HOST")

    evidence = {"anchorsEqualOwnerCopies": anchors_equal, "witnessAnchorNamesKWit": names_kwit,
                "registryVerifiesOnHost": registry_ok}
    phase = classify(present=present, exact=exact, trust_extra=trust_extra, registry_extra=registry_extra,
                     pre_ledger=pre_ledger, evidence=evidence)
    return {
        "verifierType": VERIFIER_TYPE, "schemaVersion": 1, "environment": ENVIRONMENT, "phase": phase,
        "evidence": evidence, "files": files, "expectedSha256": expected, "listings": listings,
        "laterStatePresent": later, "preLedger": pre_ledger, "hostInputReasons": sorted(reasons),
        "registryDigest": registry_digest, "failures": failures,
        "trustInstalledCandidate": phase == W5_INSTALLED_CONTENT_VERIFIED,
        "registryEffective": False, "authorityGranted": False,
    }


def classify(*, present: dict[str, bool], exact: dict[str, bool], trust_extra: bool, registry_extra: bool,
             pre_ledger: bool, evidence: dict[str, bool]) -> str:
    if not pre_ledger:
        return POST_LEDGER
    if trust_extra or registry_extra:
        return UNEXPECTED
    root_p, witness_p, registry_p = (present[p] for p in TARGETS)
    root_x, witness_x, registry_x = (exact[p] for p in TARGETS)
    if not (root_p or witness_p or registry_p):
        return W0_PRE_INSTALL
    if not registry_p:
        if not root_x:
            return W1_ROOT_ANCHOR_INCOMPLETE if not witness_p else UNEXPECTED
        if not witness_x:
            return W2_WITNESS_ANCHOR_INCOMPLETE
        return W3_ANCHORS_INSTALLED
    if not (root_x and witness_x):
        return UNEXPECTED          # registry without both exact anchors: never an installer order
    if not registry_x:
        return W4_REGISTRY_INCOMPLETE
    return W5_INSTALLED_CONTENT_VERIFIED if all(evidence.values()) else W5_INSTALLED_CONTENT_NOT_VERIFIED


def require_dev_root(*, euid: Callable[[], int] = os.geteuid, root: Path = Path("/"),
                     hostname: Callable[[], str] = lambda: os.uname().nodename) -> None:
    if euid() != 0:
        raise Refused("NOT_ROOT")
    try:
        machine_id = (root / "etc/machine-id").read_text(encoding="ascii").strip()
    except OSError as exc:
        raise Refused("NOT_DEV_HOST") from exc
    if machine_id != DEV_MACHINE_ID or hostname().split(".", 1)[0] != DEV_HOSTNAME:
        raise Refused("NOT_DEV_HOST")


def main(argv: list[str]) -> int:
    try:
        if argv not in (["observe"],) and not (len(argv) == 2 and argv[0] == "expect" and argv[1] in PHASES):
            raise Refused("USAGE")
        require_dev_root()
        if RELEASE_TREE not in sys.path:
            sys.path.insert(0, RELEASE_TREE)
        report = evaluate()
    except Refused as exc:
        print(f"mb4_mb5_trust_install_verifier: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(report, sort_keys=True, indent=2) + "\n")
    if argv[0] == "expect":
        return 0 if report["phase"] == argv[1] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
