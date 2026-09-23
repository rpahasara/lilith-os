#!/usr/bin/env python3
"""Trusted-main, exact-SHA, offline B1b-2a DEV release policy.

No code or installer from a candidate checkout is executed by this builder.
The archive is inert until a separately authorized B1b-2b installer run.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import subprocess
import tarfile
from pathlib import Path


ROLE = "lilith-memory-broker-synthetic-dev-release-v1"
DEV_HOST = "lilith-dev-01"
DEV_MACHINE_ID = "ae929170e6fa4c8ab9cc7b9547238d9d"
OWNER_SCHEMA_FINGERPRINT = "8074e95c1a1b1de6081cc686efc10159793f7c4768f362b64e9e6a34705eb314"
EVIDENCE_SCHEMA_FINGERPRINT = "c18c904a9f2b4f1c48fa3aeafb3f587a33f59f35219c872f7c33d972d996e718"
FIXTURE_FINGERPRINT = "bc6938f276c7792c873081c8047b2172e36ca2cf936b1e6ce50fd33d731855fc"
CREDENTIAL_FINGERPRINT = "d030138a32a4470f7f7945e35cf67cbd9532639d8ab03075aff7c53285785e69"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
MAX_FILE = 8 * 1024 * 1024
MAX_ARCHIVE = 20 * 1024 * 1024

BROKER_MODULES = frozenset({
    "__init__.py", "request.py", "protocol.py", "state.py", "dev_config.py",
    "dev_state.py", "synthetic_evidence.py", "dev_core.py",
    "server.py",
})
EXPECTED_BROKER_MODULES = BROKER_MODULES | {"core.py"}  # B1b-1 test-only; excluded from release.
SHARED_MODULES = frozenset({"__init__.py", "canonical_contracts.py", "owner_proof.py"})
SHARED_HASHES = {
    "services/core-api/lilith_memory/__init__.py": "2bbebd95846f1073a0b4e2ec3a2aa24378c56be4ecbb5470e5c1f1d359037e21",
    "services/core-api/lilith_memory/canonical_contracts.py": "f93d26d8a7e01d78d25f1f1d9540577cf2a55dfd4d52c4b64c87bef93ad887e0",
    "services/core-api/lilith_memory/owner_proof.py": "3a3eb7147d1e276ac261457a2340e045a0c43f6bc63eeb1a78bfc9864f80ac08",
}
SOURCE_MAP = {
    **{f"services/memory-broker/lilith_memory_broker/{name}": f"lilith_memory_broker/{name}" for name in BROKER_MODULES},
    **{f"services/core-api/lilith_memory/{name}": f"lilith_memory/{name}" for name in SHARED_MODULES},
}
ASSET_HASHES = {
    "services/memory-broker/deploy/lilith-memory-broker.service": "6a9dca54b9051cc7788587a0f37601f67e16fc07de043cbc5d64e7123ed35689",
    "services/memory-broker/deploy/lilith-memory-broker.socket": "d9f21223b837fd4be98d3c67eb95625b00c8a0ee6922d06eb79605edb382e793",
    "services/memory-broker/deploy/lilith-memory-broker.tmpfiles.conf": "e6139f16b001a3c36e9ff3db733f19a3a7ce06b1d0fbc923591bc17b2d4df86e",
    "services/memory-broker/deploy/dev-config.schema.json": "95ac57fe2a9ca474fea901c77e223653b2179c66dd3f93f6dcfe445da4d90861",
    "services/memory-broker/deploy/public-synthetic-credential.json": "a7ac8bdd58ec7338bc46a142edcf9062c007b1b602f5021e52150c7369b206db",
}
WHEEL_HASHES = {
    "cffi-2.1.1-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl": "c1453022f490d2459a11819d83ad1d586e9ff65a12ac3e705ffebd46d3685dcf",
    "cryptography-50.0.1-cp311-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl": "ff838d62ec1bfce4f9ba7fa16f4a7b554cd8d0c299e6be37502161a660c84eef",
    "fido2-2.2.1-py3-none-any.whl": "ed397da981b9ab133da6ead7309e41f924b566b749956129efe286fae097749f",
    "pycparser-3.0-py3-none-any.whl": "b727414169a36b7d524c1c3e31839a521725078d7b2ff038656844266160a992",
    "rfc8785-0.1.4-py3-none-any.whl": "520d690b448ecf0703691c76e1a34a24ddcd4fc5bc41d589cb7c58ec651bcd48",
}
LOCK = "".join(
    f"{package}=={version} --hash=sha256:{WHEEL_HASHES[wheel]}\n"
    for package, version, wheel in (
        ("cffi", "2.1.1", "cffi-2.1.1-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl"),
        ("cryptography", "50.0.1", "cryptography-50.0.1-cp311-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl"),
        ("fido2", "2.2.1", "fido2-2.2.1-py3-none-any.whl"),
        ("pycparser", "3.0", "pycparser-3.0-py3-none-any.whl"),
        ("rfc8785", "0.1.4", "rfc8785-0.1.4-py3-none-any.whl"),
    )
).encode()
EXPECTED_PATHS = frozenset(SOURCE_MAP.values()) | {"assets/" + Path(p).name for p in ASSET_HASHES} | {"wheels/" + name for name in WHEEL_HASHES} | {"requirements.lock"}


class ReleaseError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _safe_file(root: Path, relative: str) -> bytes:
    path = root
    for part in relative.split("/"):
        if part in ("", ".", ".."):
            raise ReleaseError("INVALID_PATH")
        path = path / part
        if path.is_symlink():
            raise ReleaseError("SYMLINK_IN_SOURCE")
    if not path.is_file() or path.stat().st_size > MAX_FILE:
        raise ReleaseError("SOURCE_FILE_MISSING_OR_OVERSIZED")
    return path.read_bytes()


def _candidate(root: Path, sha: str) -> None:
    if not SHA40.fullmatch(sha):
        raise ReleaseError("INVALID_CANDIDATE_SHA")
    head = subprocess.run(("git", "-C", str(root), "rev-parse", "HEAD"), text=True, capture_output=True, check=True).stdout.strip()
    status = subprocess.run(("git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"), text=True, capture_output=True, check=True).stdout.strip()
    if head != sha or status:
        raise ReleaseError("CANDIDATE_NOT_EXACT_CLEAN_SHA")


def build_payloads(root: Path, wheelhouse: Path, sha: str) -> dict[str, bytes]:
    """Reject unknown operational modules and all candidate-chosen units/wheels."""
    root = Path(root).resolve()
    _candidate(root, sha)
    module_dir = root / "services/memory-broker/lilith_memory_broker"
    if {p.name for p in module_dir.iterdir() if p.is_file()} != EXPECTED_BROKER_MODULES or any(p.is_symlink() for p in module_dir.iterdir()):
        raise ReleaseError("BROKER_MODULE_SET_CHANGED")
    payloads = {target: _safe_file(root, source) for source, target in SOURCE_MAP.items()}
    for source, expected in SHARED_HASHES.items():
        if digest(payloads[SOURCE_MAP[source]]) != expected:
            raise ReleaseError("GOVERNED_SHARED_MODULE_CHANGED")
    for source, expected in ASSET_HASHES.items():
        data = _safe_file(root, source)
        if digest(data) != expected:
            raise ReleaseError("TRUSTED_ASSET_CHANGED")
        payloads["assets/" + Path(source).name] = data
    wheelhouse = Path(wheelhouse).resolve()
    if not wheelhouse.is_dir() or {p.name for p in wheelhouse.iterdir()} != set(WHEEL_HASHES):
        raise ReleaseError("WHEEL_SET_MISMATCH")
    for name, expected in WHEEL_HASHES.items():
        data = _safe_file(wheelhouse, name)
        if digest(data) != expected:
            raise ReleaseError("WHEEL_HASH_MISMATCH")
        payloads["wheels/" + name] = data
    payloads["requirements.lock"] = LOCK
    if set(payloads) != EXPECTED_PATHS:
        raise ReleaseError("RELEASE_FILE_SET_MISMATCH")
    return payloads


def build(root: Path, wheelhouse: Path, sha: str, archive: Path, attestation: Path) -> dict:
    payloads = build_payloads(root, wheelhouse, sha)
    manifest = {
        "schemaVersion": 1, "artifactRole": ROLE, "candidateSha": sha,
        "deploymentEnvironment": "dev", "expectedHost": DEV_HOST,
        "expectedMachineId": DEV_MACHINE_ID,
        "ownerSchemaFingerprint": OWNER_SCHEMA_FINGERPRINT,
        "evidenceSchemaFingerprint": EVIDENCE_SCHEMA_FINGERPRINT,
        "fixtureFingerprint": FIXTURE_FINGERPRINT,
        "credentialFingerprint": CREDENTIAL_FINGERPRINT,
        "files": [{"path": path, "byteSize": len(data), "sha256": digest(data)} for path, data in sorted(payloads.items())],
    }
    payloads["release-manifest.json"] = canonical(manifest)
    archive = Path(archive)
    attestation = Path(attestation)
    if archive.resolve() == attestation.resolve() or archive.exists() or attestation.exists():
        raise ReleaseError("OUTPUT_COLLISION")
    archive.parent.mkdir(parents=True, exist_ok=True)
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for path, data in sorted(payloads.items()):
                    member = tarfile.TarInfo(path)
                    member.size = len(data)
                    member.mode = 0o600
                    member.mtime = 0
                    tar.addfile(member, io.BytesIO(data))
    if archive.stat().st_size > MAX_ARCHIVE:
        raise ReleaseError("ARCHIVE_OVERSIZED")
    result = {"schemaVersion": 1, "artifactRole": ROLE, "candidateSha": sha,
              "archiveByteSize": archive.stat().st_size, "archiveSha256": digest(archive.read_bytes()),
              "manifestSha256": digest(payloads["release-manifest.json"])}
    attestation.write_bytes(canonical(result))
    return result


def verify_archive(archive: Path, attestation: Path, expected_sha: str) -> tuple[dict, dict[str, bytes]]:
    if not SHA40.fullmatch(expected_sha):
        raise ReleaseError("INVALID_CANDIDATE_SHA")
    archive = Path(archive)
    if not archive.is_file() or archive.stat().st_size > MAX_ARCHIVE:
        raise ReleaseError("ARCHIVE_MISSING_OR_OVERSIZED")
    stamp = json.loads(Path(attestation).read_bytes())
    if not isinstance(stamp, dict) or set(stamp) != {"schemaVersion", "artifactRole", "candidateSha", "archiveByteSize", "archiveSha256", "manifestSha256"}:
        raise ReleaseError("INVALID_ATTESTATION")
    if stamp["schemaVersion"] != 1 or stamp["artifactRole"] != ROLE or stamp["candidateSha"] != expected_sha or stamp["archiveByteSize"] != archive.stat().st_size or stamp["archiveSha256"] != digest(archive.read_bytes()):
        raise ReleaseError("ATTESTATION_MISMATCH")
    payloads: dict[str, bytes] = {}
    with tarfile.open(archive, "r:gz") as tar:
        for item in tar:
            if item.name in payloads or item.name not in EXPECTED_PATHS | {"release-manifest.json"} or not item.isfile() or item.issym() or item.islnk() or item.size > MAX_FILE:
                raise ReleaseError("UNSAFE_ARCHIVE_MEMBER")
            stream = tar.extractfile(item)
            if stream is None:
                raise ReleaseError("UNREADABLE_ARCHIVE_MEMBER")
            data = stream.read(MAX_FILE + 1)
            if len(data) != item.size:
                raise ReleaseError("ARCHIVE_MEMBER_SIZE_MISMATCH")
            payloads[item.name] = data
    if set(payloads) != EXPECTED_PATHS | {"release-manifest.json"}:
        raise ReleaseError("ARCHIVE_FILE_SET_MISMATCH")
    manifest_bytes = payloads.pop("release-manifest.json")
    if digest(manifest_bytes) != stamp["manifestSha256"]:
        raise ReleaseError("MANIFEST_HASH_MISMATCH")
    manifest = json.loads(manifest_bytes)
    expected_manifest = {
        "schemaVersion": 1, "artifactRole": ROLE, "candidateSha": expected_sha,
        "deploymentEnvironment": "dev", "expectedHost": DEV_HOST,
        "expectedMachineId": DEV_MACHINE_ID,
        "ownerSchemaFingerprint": OWNER_SCHEMA_FINGERPRINT,
        "evidenceSchemaFingerprint": EVIDENCE_SCHEMA_FINGERPRINT,
        "fixtureFingerprint": FIXTURE_FINGERPRINT,
        "credentialFingerprint": CREDENTIAL_FINGERPRINT,
        "files": [{"path": path, "byteSize": len(data), "sha256": digest(data)} for path, data in sorted(payloads.items())],
    }
    if manifest != expected_manifest or manifest_bytes != canonical(manifest):
        raise ReleaseError("MANIFEST_CONTENT_MISMATCH")
    for name, expected in WHEEL_HASHES.items():
        if digest(payloads["wheels/" + name]) != expected:
            raise ReleaseError("WHEEL_HASH_MISMATCH")
    for source, expected in ASSET_HASHES.items():
        if digest(payloads["assets/" + Path(source).name]) != expected:
            raise ReleaseError("TRUSTED_ASSET_CHANGED")
    for source, expected in SHARED_HASHES.items():
        if digest(payloads[SOURCE_MAP[source]]) != expected:
            raise ReleaseError("GOVERNED_SHARED_MODULE_CHANGED")
    if payloads["requirements.lock"] != LOCK:
        raise ReleaseError("DEPENDENCY_LOCK_MISMATCH")
    return manifest, payloads


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("build", "verify"))
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--attestation", type=Path, required=True)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--wheelhouse", type=Path)
    args = parser.parse_args()
    if args.operation == "build":
        if args.source_root is None or args.wheelhouse is None:
            parser.error("build requires source-root and wheelhouse")
        print(json.dumps(build(args.source_root, args.wheelhouse, args.candidate_sha, args.archive, args.attestation), sort_keys=True))
    else:
        manifest, _ = verify_archive(args.archive, args.attestation, args.candidate_sha)
        print(json.dumps({"candidateSha": manifest["candidateSha"], "fileCount": len(manifest["files"]), "status": "VERIFIED"}, sort_keys=True))


if __name__ == "__main__":
    main()
