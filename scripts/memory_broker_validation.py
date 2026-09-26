#!/usr/bin/env python3
"""Trusted, closed B1b-1/B1b-2a validation artifact and transient runner.

This script belongs to default-branch controls, never to the candidate bundle.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


SHA = re.compile(r"[0-9a-f]{40}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
ROLE = "lilith-memory-broker-validation-v1"
BROKER_ROOT = "services/memory-broker"
BROKER_FILES = frozenset({
    f"{BROKER_ROOT}/README.md",
    f"{BROKER_ROOT}/lilith_memory_broker/__init__.py",
    f"{BROKER_ROOT}/lilith_memory_broker/request.py",
    f"{BROKER_ROOT}/lilith_memory_broker/protocol.py",
    f"{BROKER_ROOT}/lilith_memory_broker/state.py",
    f"{BROKER_ROOT}/lilith_memory_broker/core.py",
    f"{BROKER_ROOT}/tests/test_broker_foundation.py",
    f"{BROKER_ROOT}/tests/owner_request_golden.json",
})
SHARED_FILES = frozenset({
    "services/core-api/requirements.txt",
    "services/core-api/lilith_memory/__init__.py",
    "services/core-api/lilith_memory/canonical_contracts.py",
    "services/core-api/lilith_memory/canonical_authority.py",
    "services/core-api/lilith_memory/owner_proof.py",
    "services/core-api/tests/test_owner_proof.py",
    "services/core-api/tests/owner_proof_golden.jsonl",
})
FILES = BROKER_FILES | SHARED_FILES
B1B2A_EXTRA = frozenset({
    "services/memory-broker/lilith_memory_broker/dev_config.py",
    "services/memory-broker/lilith_memory_broker/dev_state.py",
    "services/memory-broker/lilith_memory_broker/synthetic_evidence.py",
    "services/memory-broker/lilith_memory_broker/dev_core.py",
    "services/memory-broker/lilith_memory_broker/server.py",
    "services/memory-broker/tests/test_dev_synthetic.py",
    "services/memory-broker/tests/test_server_adapter.py",
    "services/memory-broker/tests/test_deploy_assets.py",
    "services/memory-broker/deploy/lilith-memory-broker.service",
    "services/memory-broker/deploy/lilith-memory-broker.socket",
    "services/memory-broker/deploy/lilith-memory-broker.tmpfiles.conf",
    "services/memory-broker/deploy/dev-config.schema.json",
    "services/memory-broker/deploy/public-synthetic-credential.json",
})
B1B2A_BROKER_FILES = BROKER_FILES | B1B2A_EXTRA
B1B2A_FILES = B1B2A_BROKER_FILES | SHARED_FILES
# Source-controlled host install material kept beside the broker units. It is
# recognized exactly in the tree but never packaged into the validation
# artifact (or the OS release, which pins its own assets). Only the owner
# runbook in docs/architecture/slice15b2b-b1b3d-current-runtime-baseline.md
# installs it; its content hash is pinned by scripts/test_needrestart_lilith_override.py.
SOURCE_ONLY_BROKER_FILES = frozenset({
    "services/memory-broker/deploy/needrestart-lilith-authority-sensitive.conf",
})
ACCEPTED_BROKER_TREES = (
    BROKER_FILES,
    B1B2A_BROKER_FILES,
    B1B2A_BROKER_FILES | SOURCE_ONLY_BROKER_FILES,
)
ALLOWED_FILES = FILES | B1B2A_FILES | SOURCE_ONLY_BROKER_FILES
MANIFEST_NAME = "broker-validation-manifest.json"
MAX_FILE = 1024 * 1024
MAX_ARCHIVE = 8 * 1024 * 1024


class ValidationError(RuntimeError):
    pass


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _path(root: Path, name: str) -> Path:
    # Names originate in this trusted policy, but still guard each component.
    if name not in ALLOWED_FILES or name.startswith("/") or ".." in name.split("/"):
        raise ValidationError("UNTRUSTED_COMPONENT_PATH")
    path = root
    for part in name.split("/"):
        path = path / part
        if path.is_symlink():
            raise ValidationError("SYMLINK_IN_COMPONENT")
    if not path.is_file():
        raise ValidationError(f"REQUIRED_FILE_MISSING:{name}")
    return path


def component_present(root: Path) -> bool:
    path = root / BROKER_ROOT
    if path.is_symlink():
        raise ValidationError("SYMLINK_IN_COMPONENT")
    if path.exists() and not path.is_dir():
        raise ValidationError("INVALID_COMPONENT_ROOT")
    return path.is_dir()


def component_files(root: Path) -> dict[str, bytes] | None:
    root = Path(root)
    if not component_present(root):
        return None
    actual = set()
    for path in (root / BROKER_ROOT).rglob("*"):
        if path.is_symlink():
            raise ValidationError("SYMLINK_IN_COMPONENT")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
        elif not path.is_dir():
            raise ValidationError("UNEXPECTED_COMPONENT_ENTRY")
    if actual not in ACCEPTED_BROKER_TREES:
        raise ValidationError(f"BROKER_FILE_SET_MISMATCH actual={sorted(actual)}")
    for name in sorted(actual & SOURCE_ONLY_BROKER_FILES):
        data = _path(root, name).read_bytes()
        if len(data) > MAX_FILE:
            raise ValidationError(f"COMPONENT_FILE_OVERSIZED:{name}")
        if b"PRIVATE KEY-----" in data:
            raise ValidationError("PRIVATE_MATERIAL_IN_BROKER")
    selected = FILES if actual == BROKER_FILES else B1B2A_FILES
    values = {}
    for name in sorted(selected):
        data = _path(root, name).read_bytes()
        if len(data) > MAX_FILE:
            raise ValidationError(f"COMPONENT_FILE_OVERSIZED:{name}")
        if name in (BROKER_FILES | B1B2A_BROKER_FILES) and (b"-----BEGIN PRIVATE KEY-----" in data or b"-----BEGIN EC PRIVATE KEY-----" in data):
            raise ValidationError("PRIVATE_MATERIAL_IN_BROKER")
        values[name] = data
    return values


def assert_candidate_sha(root: Path, expected: str) -> None:
    if not SHA.fullmatch(expected):
        raise ValidationError("INVALID_CANDIDATE_SHA")
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    )
    if result.stdout.strip() != expected:
        raise ValidationError("CANDIDATE_SHA_MISMATCH")
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
        check=True, capture_output=True, text=True,
    )
    if status.stdout.strip():
        raise ValidationError("CANDIDATE_WORKTREE_NOT_CLEAN")


def build(root: Path, archive: Path, attestation: Path, candidate_sha: str) -> dict | None:
    root = Path(root).resolve()
    assert_candidate_sha(root, candidate_sha)
    payloads = component_files(root)
    if payloads is None:
        return None
    manifest = {
        "schemaVersion": 1,
        "componentVersion": "B1b-1" if set(payloads) == FILES else "B1b-2a",
        "artifactRole": ROLE,
        "candidateSha": candidate_sha,
        "files": [
            {"path": name, "byteSize": len(payloads[name]), "sha256": _digest(payloads[name])}
            for name in sorted(payloads)
        ],
    }
    archive = Path(archive)
    attestation = Path(attestation)
    if archive.resolve() == attestation.resolve():
        raise ValidationError("OUTPUT_PATH_ALIAS")
    payloads[MANIFEST_NAME] = _canonical(manifest)
    archive.parent.mkdir(parents=True, exist_ok=True)
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for name, data in sorted(payloads.items()):
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    info.mode = 0o600
                    info.mtime = 0
                    tar.addfile(info, io.BytesIO(data))
    if archive.stat().st_size > MAX_ARCHIVE:
        archive.unlink()
        raise ValidationError("ARTIFACT_OVERSIZED")
    result = {**manifest, "archiveByteSize": archive.stat().st_size, "archiveSha256": _digest(archive.read_bytes())}
    attestation.parent.mkdir(parents=True, exist_ok=True)
    attestation.write_bytes(_canonical(result))
    return result


def verify_extract(archive: Path, attestation: Path, destination: Path, candidate_sha: str) -> dict:
    if not SHA.fullmatch(candidate_sha):
        raise ValidationError("INVALID_CANDIDATE_SHA")
    archive = Path(archive)
    if not archive.is_file() or archive.stat().st_size > MAX_ARCHIVE:
        raise ValidationError("ARTIFACT_MISSING_OR_OVERSIZED")
    value = json.loads(Path(attestation).read_bytes())
    if not isinstance(value, dict) or set(value) != {"schemaVersion", "componentVersion", "artifactRole", "candidateSha", "files", "archiveByteSize", "archiveSha256"}:
        raise ValidationError("INVALID_ATTESTATION_SCHEMA")
    if (value["schemaVersion"], value["artifactRole"], value["candidateSha"]) != (1, ROLE, candidate_sha) or value["componentVersion"] not in ("B1b-1", "B1b-2a"):
        raise ValidationError("ATTESTATION_IDENTITY_MISMATCH")
    selected = FILES if value["componentVersion"] == "B1b-1" else B1B2A_FILES
    if value["archiveByteSize"] != archive.stat().st_size or value["archiveSha256"] != _digest(archive.read_bytes()):
        raise ValidationError("ARTIFACT_DIGEST_MISMATCH")
    items = value["files"]
    if not isinstance(items, list) or len(items) != len(selected):
        raise ValidationError("ATTESTED_FILE_SET_MISMATCH")
    indexed = {}
    for item in items:
        if not isinstance(item, dict) or set(item) != {"path", "byteSize", "sha256"}:
            raise ValidationError("INVALID_FILE_ATTESTATION")
        name = item["path"]
        if name not in selected or name in indexed or type(item["byteSize"]) is not int or not 0 <= item["byteSize"] <= MAX_FILE or not isinstance(item["sha256"], str) or not HEX.fullmatch(item["sha256"]):
            raise ValidationError("UNSAFE_ATTESTED_FILE")
        indexed[name] = item
    if set(indexed) != selected:
        raise ValidationError("ATTESTED_FILE_SET_MISMATCH")
    destination = Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise ValidationError("DESTINATION_NOT_EMPTY")
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {key: value[key] for key in ("schemaVersion", "componentVersion", "artifactRole", "candidateSha", "files")}
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)) or set(names) != selected | {MANIFEST_NAME}:
            raise ValidationError("ARCHIVE_MEMBER_SET_MISMATCH")
        for member in members:
            if not member.isfile() or member.issym() or member.islnk() or member.size > MAX_FILE or member.name.startswith("/") or ".." in member.name.split("/"):
                raise ValidationError("UNSAFE_ARCHIVE_MEMBER")
            stream = tar.extractfile(member)
            if stream is None:
                raise ValidationError("UNREADABLE_ARCHIVE_MEMBER")
            data = stream.read(MAX_FILE + 1)
            if len(data) != member.size:
                raise ValidationError("ARCHIVE_MEMBER_SIZE_MISMATCH")
            if member.name == MANIFEST_NAME:
                if data != _canonical(manifest):
                    raise ValidationError("EMBEDDED_MANIFEST_MISMATCH")
            elif len(data) != indexed[member.name]["byteSize"] or _digest(data) != indexed[member.name]["sha256"]:
                raise ValidationError("FILE_DIGEST_MISMATCH")
            output = destination.joinpath(*member.name.split("/"))
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
    return value


def _run(argv: list[str], root: Path, env: dict[str, str]) -> None:
    subprocess.run(argv, cwd=root, env=env, check=True)


def execute(root: Path, python: str = sys.executable) -> None:
    """Compile/import and run exact broker plus B1a tests; failures propagate."""
    env = os.environ.copy()
    env["LILITH_ENV"] = "test"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    root = Path(root)
    selected = set(component_files(root) or ())
    sources = [str(root / name) for name in sorted(selected) if name.endswith(".py")]
    _run([python, "-B", "-c", "import pathlib,sys; [compile(pathlib.Path(p).read_bytes(), p, 'exec') for p in sys.argv[1:]]", *sources], root, env)
    imports = "import sys; sys.path[:0]=['services/core-api','services/memory-broker']; import lilith_memory_broker.core, lilith_memory_broker.protocol, lilith_memory_broker.request, lilith_memory_broker.state"
    _run([python, "-B", "-c", imports], root, env)
    test_code = (
        "import sys,unittest; "
        "suite=unittest.defaultTestLoader.discover(sys.argv[1],pattern=sys.argv[2]); "
        "count=suite.countTestCases(); "
        "print('TRUSTED_TEST_COUNT='+str(count),flush=True); "
        "sys.exit(1) if count<int(sys.argv[3]) else None; "
        "result=unittest.TextTestRunner(verbosity=2).run(suite); "
        "sys.exit(0 if result.wasSuccessful() else 1)"
    )
    _run([python, "-B", "-c", test_code, f"{BROKER_ROOT}/tests", "test_*.py", "14" if selected == FILES else "35"], root, env)
    _run([python, "-B", "-c", test_code, "services/core-api/tests", "test_owner_proof.py", "22"], root, env)


def run_transient(archive: Path, attestation: Path, candidate_sha: str, python: str = sys.executable) -> dict:
    with tempfile.TemporaryDirectory(prefix="lilith-memory-broker-validation-") as temporary:
        root = Path(temporary)
        value = verify_extract(archive, attestation, root, candidate_sha)
        execute(root, python)
        result = {"status": "VALIDATED", "candidateSha": candidate_sha, "archiveSha256": value["archiveSha256"], "fileCount": len(value["files"])}
    if root.exists():
        raise ValidationError("TRANSIENT_CLEANUP_FAILED")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("detect", "ci", "build", "verify-run"))
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--attestation", type=Path)
    parser.add_argument("--candidate-sha")
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()
    if args.mode == "detect":
        print("PRESENT" if component_present(args.source_root) else "NOT_APPLICABLE")
    elif args.mode == "ci":
        payloads = component_files(args.source_root)
        if payloads is None:
            print("NOT_APPLICABLE")
        else:
            execute(args.source_root, args.python)
            print("BROKER_CI_VALIDATED")
    elif args.mode == "build":
        result = build(args.source_root, args.archive, args.attestation, args.candidate_sha)
        print(json.dumps(result if result is not None else {"status": "NOT_APPLICABLE"}, sort_keys=True))
    else:
        print(json.dumps(run_transient(args.archive, args.attestation, args.candidate_sha, args.python), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
