#!/usr/bin/env python3
"""Build a deterministic exact-SHA Core API bundle from an allowlist."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
FIXED_FILES = (
    "services/core-api/app.py",
    "services/core-api/requirements.txt",
    "services/core-api/tests/test_goal_executive.py",
    "services/core-api/tests/test_canonical_runtime.py",
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sources(root: Path) -> tuple[tuple[str, Path], ...]:
    values = []
    for relative in FIXED_FILES:
        source = root / relative
        if not source.is_file() or source.is_symlink():
            raise RuntimeError(f"required bundle source is unavailable: {relative}")
        archive_name = relative.removeprefix("services/core-api/")
        values.append((archive_name, source))
    package = root / "services" / "core-api" / "lilith_memory"
    if not package.is_dir() or package.is_symlink():
        raise RuntimeError("canonical runtime package is unavailable")
    modules = sorted(package.glob("*.py"), key=lambda value: value.name)
    if not modules or any(value.is_symlink() for value in modules):
        raise RuntimeError("canonical runtime modules are unavailable")
    values.extend((f"lilith_memory/{value.name}", value) for value in modules)
    return tuple(sorted(values))


def build(source_root: Path, archive: Path, attestation: Path, candidate_sha: str) -> dict:
    if not SHA_RE.fullmatch(candidate_sha):
        raise ValueError("candidate SHA must be 40 lowercase hexadecimal characters")
    root = Path(source_root).resolve()
    archive_path = Path(archive).resolve()
    attestation_path = Path(attestation).resolve()
    if archive_path == attestation_path:
        raise ValueError("archive and attestation paths must differ")
    files = []
    payloads = {}
    for name, source in _sources(root):
        data = source.read_bytes()
        payloads[name] = data
        files.append(
            {"path": name, "sha256": _sha256_bytes(data), "byteSize": len(data)}
        )
    manifest = {
        "schemaVersion": 1,
        "bundleRole": "lilith-core-api-dev",
        "candidateSha": candidate_sha,
        "files": files,
    }
    manifest_bytes = (
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    payloads["deployment-manifest.json"] = manifest_bytes
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with archive_path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for name in sorted(payloads):
                    data = payloads[name]
                    info = tarfile.TarInfo(name=name)
                    info.size = len(data)
                    info.mode = 0o644
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    tar.addfile(info, io.BytesIO(data))
    attested = {
        **manifest,
        "archiveSha256": _sha256_file(archive_path),
        "archiveByteSize": archive_path.stat().st_size,
    }
    attestation_path.parent.mkdir(parents=True, exist_ok=True)
    attestation_path.write_text(
        json.dumps(attested, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return attested


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--attestation", required=True, type=Path)
    parser.add_argument("--candidate-sha", required=True)
    args = parser.parse_args()
    result = build(
        args.source_root, args.archive, args.attestation, args.candidate_sha
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
