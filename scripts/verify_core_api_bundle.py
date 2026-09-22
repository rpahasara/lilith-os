#!/usr/bin/env python3
"""Verify and safely extract a deterministic Core API deployment bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tarfile
from pathlib import Path, PurePosixPath


SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_and_extract(
    archive: Path,
    attestation: Path,
    destination: Path,
    expected_sha: str,
) -> dict:
    if not SHA_RE.fullmatch(expected_sha):
        raise ValueError("expected SHA is invalid")
    archive_path = Path(archive).resolve()
    attestation_path = Path(attestation).resolve()
    target = Path(destination).resolve()
    if not archive_path.is_file() or not attestation_path.is_file():
        raise RuntimeError("bundle inputs are unavailable")
    if target.exists() and any(target.iterdir()):
        raise RuntimeError("bundle destination must be empty")
    target.mkdir(parents=True, exist_ok=True)
    attested = json.loads(attestation_path.read_text(encoding="utf-8"))
    expected_keys = {
        "schemaVersion",
        "bundleRole",
        "candidateSha",
        "files",
        "archiveSha256",
        "archiveByteSize",
    }
    if (
        not isinstance(attested, dict)
        or set(attested) != expected_keys
        or attested.get("schemaVersion") != 1
        or attested.get("bundleRole") != "lilith-core-api-dev"
        or attested.get("candidateSha") != expected_sha
        or attested.get("archiveSha256") != _file_sha256(archive_path)
        or attested.get("archiveByteSize") != archive_path.stat().st_size
        or not isinstance(attested.get("files"), list)
    ):
        raise RuntimeError("bundle attestation is invalid")
    expected_files = {}
    for item in attested["files"]:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "byteSize"}:
            raise RuntimeError("bundle file attestation is malformed")
        name = item["path"]
        normalized = PurePosixPath(name)
        if (
            not isinstance(name, str)
            or normalized.is_absolute()
            or ".." in normalized.parts
            or name in expected_files
            or not isinstance(item["byteSize"], int)
            or item["byteSize"] < 0
        ):
            raise RuntimeError("bundle file path is unsafe")
        expected_files[name] = item
    expected_members = set(expected_files) | {"deployment-manifest.json"}
    with tarfile.open(archive_path, mode="r:gz") as tar:
        members = tar.getmembers()
        names = {member.name for member in members}
        if names != expected_members or len(names) != len(members):
            raise RuntimeError("bundle member set differs from attestation")
        for member in members:
            normalized = PurePosixPath(member.name)
            if (
                not member.isfile()
                or normalized.is_absolute()
                or ".." in normalized.parts
                or member.issym()
                or member.islnk()
            ):
                raise RuntimeError("bundle contains an unsafe member")
            extracted = tar.extractfile(member)
            if extracted is None:
                raise RuntimeError("bundle member cannot be read")
            data = extracted.read()
            if member.name == "deployment-manifest.json":
                inner = json.loads(data.decode("utf-8"))
                expected_inner = {
                    key: value
                    for key, value in attested.items()
                    if key not in {"archiveSha256", "archiveByteSize"}
                }
                if inner != expected_inner:
                    raise RuntimeError("embedded deployment manifest differs")
            else:
                item = expected_files[member.name]
                if len(data) != item["byteSize"] or _sha256(data) != item["sha256"]:
                    raise RuntimeError("bundle member digest differs")
            output = target.joinpath(*normalized.parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
            os.chmod(output, 0o644)
    (target / ".bundle-sha256").write_text(
        str(attested["archiveSha256"]) + "\n", encoding="ascii"
    )
    return attested


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--attestation", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    result = verify_and_extract(
        args.archive, args.attestation, args.destination, args.expected_sha
    )
    print(
        json.dumps(
            {
                "candidateSha": result["candidateSha"],
                "archiveSha256": result["archiveSha256"],
                "fileCount": len(result["files"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
