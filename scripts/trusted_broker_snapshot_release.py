#!/usr/bin/env python3
"""Deterministic, fixed-payload DEV snapshot control release (not an installer)."""

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


ROLE = "TrustedBrokerSnapshotReleaseV1"
PROFILE = "POST_STAGE_II_ACCEPTED_V1"
OPERATION = "SNAPSHOT_ACCEPTED_STAGE2"
OUTPUT_SCHEMA = "BrokerCandidateDevSnapshotV1"
SOURCE_MAP = {
    "scripts/trusted_broker_snapshot.py": "bin/lilith-broker-dev-snapshot",
    "scripts/trusted_broker_snapshot_invocation.py": "bin/lilith-broker-dev-invocation",
    "scripts/verify_broker_dev_lifecycle.py": "lib/verify_broker_dev_lifecycle.py",
}
RUNTIME = {
    "pythonExecutable": "/usr/bin/python3",
    "pythonVersion": "3.12.3",
    "pythonSha256": "e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f",
    "sqliteVersion": "3.45.1",
    "sqliteModuleSha256": "f7cc982617b68e147540ef352d38310fe4d25c2c9c2542b67d0590c871df09a8",
    "sqliteExtensionSha256": "ecf54958b24c533f5c8dc67ca82cdce236aeb322864140bfe93eb8a69b729f4d",
    "pythonPackage": "python3.12-minimal=3.12.3-1ubuntu0.17",
    "sqlitePackage": "libsqlite3-0=3.45.1-1ubuntu2.8",
}
MAX_PAYLOAD = 512 * 1024
MAX_ARCHIVE = 2 * 1024 * 1024
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")


class ReleaseError(RuntimeError):
    pass


def canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _committed_file(root: Path, commit: str, path: str) -> bytes:
    if not SHA40.fullmatch(commit):
        raise ReleaseError("SOURCE_COMMIT_FORMAT")
    source = root / path
    parent = root
    for part in Path(path).parts[:-1]:
        parent = parent / part
        if parent.is_symlink() or not parent.is_dir():
            raise ReleaseError("SOURCE_PARENT_CUSTODY")
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_PAYLOAD:
        raise ReleaseError("SOURCE_FILE_CUSTODY")
    data = source.read_bytes()
    committed = subprocess.run(
        ("git", "-C", str(root), "show", f"{commit}:{path}"),
        check=True, capture_output=True,
    ).stdout
    if data != committed:
        raise ReleaseError("SOURCE_FILE_NOT_EXACT_COMMIT")
    return data


def make_manifest(payloads: dict[str, bytes]) -> dict:
    if set(payloads) != set(SOURCE_MAP.values()):
        raise ReleaseError("PAYLOAD_SET")
    if any(not data or len(data) > MAX_PAYLOAD for data in payloads.values()):
        raise ReleaseError("PAYLOAD_SIZE")
    return {
        "schema": ROLE,
        "operation": OPERATION,
        "lifecycleProfile": PROFILE,
        "outputSchema": OUTPUT_SCHEMA,
        "runtime": RUNTIME,
        "payloads": [
            {"path": path, "size": len(payloads[path]), "sha256": digest(payloads[path])}
            for path in sorted(payloads)
        ],
    }


def build(source_root: Path, source_commit: str, archive: Path, attestation: Path) -> dict:
    source_root = source_root.resolve()
    payloads = {target: _committed_file(source_root, source_commit, source)
                for source, target in SOURCE_MAP.items()}
    manifest_bytes = canonical(make_manifest(payloads))
    release_id = digest(manifest_bytes)
    members = {**payloads, "release-manifest.json": manifest_bytes}
    if archive.exists() or attestation.exists() or archive.resolve() == attestation.resolve():
        raise ReleaseError("OUTPUT_COLLISION")
    archive.parent.mkdir(parents=True, exist_ok=True)
    attestation.parent.mkdir(parents=True, exist_ok=True)
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w", format=tarfile.USTAR_FORMAT) as tar:
                for path, data in sorted(members.items()):
                    member = tarfile.TarInfo(path)
                    member.size = len(data)
                    member.mode = 0o755 if path.startswith("bin/") else 0o644
                    member.uid = member.gid = member.mtime = 0
                    member.uname = member.gname = ""
                    tar.addfile(member, io.BytesIO(data))
    if archive.stat().st_size > MAX_ARCHIVE:
        raise ReleaseError("ARCHIVE_SIZE")
    result = {
        "schema": ROLE,
        "sourceCommit": source_commit,
        "releaseId": release_id,
        "manifestSha256": release_id,
        "archiveSha256": digest(archive.read_bytes()),
        "archiveSize": archive.stat().st_size,
        "payloads": make_manifest(payloads)["payloads"],
        "runtime": RUNTIME,
    }
    attestation.write_bytes(canonical(result))
    return result


def verify(archive: Path, attestation: Path) -> tuple[dict, dict[str, bytes]]:
    if archive.is_symlink() or attestation.is_symlink() or not archive.is_file() or not attestation.is_file():
        raise ReleaseError("ARTIFACT_FILE")
    raw = archive.read_bytes()
    if not raw or len(raw) > MAX_ARCHIVE:
        raise ReleaseError("ARCHIVE_SIZE")
    evidence_bytes = attestation.read_bytes()
    evidence = json.loads(evidence_bytes)
    if (canonical(evidence) != evidence_bytes or set(evidence) != {
            "schema", "sourceCommit", "releaseId", "manifestSha256", "archiveSha256",
            "archiveSize", "payloads", "runtime",
        } or evidence.get("schema") != ROLE or
            not SHA40.fullmatch(evidence.get("sourceCommit", ""))):
        raise ReleaseError("ATTESTATION_SCHEMA")
    if evidence.get("archiveSha256") != digest(raw) or evidence.get("archiveSize") != len(raw):
        raise ReleaseError("ARCHIVE_HASH")
    members = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        for member in tar:
            if (not member.isfile() or member.name in members or
                    member.name not in set(SOURCE_MAP.values()) | {"release-manifest.json"} or
                    member.uid != 0 or member.gid != 0 or member.mtime != 0 or
                    member.mode != (0o755 if member.name.startswith("bin/") else 0o644) or
                    member.size > MAX_PAYLOAD):
                raise ReleaseError("ARCHIVE_MEMBER")
            source = tar.extractfile(member)
            if source is None:
                raise ReleaseError("ARCHIVE_MEMBER")
            members[member.name] = source.read(MAX_PAYLOAD + 1)
    if set(members) != set(SOURCE_MAP.values()) | {"release-manifest.json"}:
        raise ReleaseError("ARCHIVE_MEMBER_SET")
    manifest_bytes = members.pop("release-manifest.json")
    manifest = json.loads(manifest_bytes)
    release_id = digest(manifest_bytes)
    if (canonical(manifest) != manifest_bytes or manifest != make_manifest(members) or
            evidence.get("releaseId") != release_id or evidence.get("manifestSha256") != release_id or
            evidence.get("payloads") != manifest["payloads"] or evidence.get("runtime") != RUNTIME):
        raise ReleaseError("MANIFEST_MISMATCH")
    return evidence, members


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "verify"))
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--attestation", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "build":
        if args.source_root is None or args.source_commit is None:
            raise ReleaseError("SOURCE_REQUIRED")
        result = build(args.source_root, args.source_commit, args.archive, args.attestation)
    else:
        if args.source_root is not None or args.source_commit is not None:
            raise ReleaseError("VERIFY_SOURCE_ARGUMENT")
        result, _ = verify(args.archive, args.attestation)
    print(canonical(result).decode(), end="")


if __name__ == "__main__":
    main()
