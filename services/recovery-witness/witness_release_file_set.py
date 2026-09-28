#!/usr/bin/env python3
"""Exact source and runtime file-set contract for `lilith-recovery-witness` (B1b-3e PR-1S).

Packaging policy only: it reads the repository tree, writes nothing, and
contacts nothing. The recovery witness is its own service identity, state
owner, private key, unit set, and failure domain. Its runtime payload ships
INSIDE the one reviewed authority-dev release archive (preflight §34:
"one reviewed release, two units, RR-25 unchanged") under
`lilith_recovery_witness/` and `assets/lilith-recovery-witness*`, and it has
its OWN manifest identity here (`runtimeSha256`), so the witness payload is
reviewable and verifiable on the host separately from the signer's.

One Git slice != one runtime service identity.

It fails closed on any unlisted file under `services/recovery-witness/`, any
symlink, and any private-key, TEST-seed, TEST-signer, or key-generation
marker in a runtime payload file.

    source-controlled artifact != installed service
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

SERVICE = "services/recovery-witness"
RUNTIME_PACKAGE = SERVICE + "/lilith_recovery_witness"
RUNTIME_MODULES = frozenset({"__init__.py", "profile.py", "credential.py", "storage.py", "writer.py", "protocol.py",
                             "core.py", "server.py"})
DEPLOY_ASSETS = frozenset({"lilith-recovery-witness.service", "lilith-recovery-witness-owner.socket",
                           "lilith-recovery-witness-signer.socket", "lilith-recovery-witness.tmpfiles.conf"})
TEST_FILES = frozenset({"test_recovery_witness.py", "test_recovery_witness_units.py", "witness_fixtures.py"})
SOURCE_FILES = frozenset(
    {f"{RUNTIME_PACKAGE}/{name}" for name in RUNTIME_MODULES}
    | {f"{SERVICE}/deploy/{name}" for name in DEPLOY_ASSETS}
    | {f"{SERVICE}/tests/{name}" for name in TEST_FILES}
    | {f"{SERVICE}/README.md", f"{SERVICE}/witness_release_file_set.py"}
)
RUNTIME_SOURCE_MAP = {
    **{f"{RUNTIME_PACKAGE}/{name}": f"lilith_recovery_witness/{name}" for name in RUNTIME_MODULES},
    **{f"{SERVICE}/deploy/{name}": f"assets/{name}" for name in DEPLOY_ASSETS},
}
FORBIDDEN_RUNTIME_MARKERS = (
    b"-----" + b"BEGIN",
    b"PRIVATE" + b" KEY-----",
    b"OPENSSH" + b" PRIVATE",
    b"TEST_ONLY ",
    b"from_private_bytes",
    b"Ed25519PrivateKey.generate",
    b".generate()",
    b"lilith_authority_signer",
    b"synthetic_",
    b"SEEDS",
)
MAX_FILE = 1024 * 1024


class FileSetError(RuntimeError):
    pass


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(root: Path, relative: str) -> bytes:
    path = root
    for part in relative.split("/"):
        if part in ("", ".", ".."):
            raise FileSetError("INVALID_PATH")
        path = path / part
        if path.is_symlink():
            raise FileSetError("SYMLINK_IN_SOURCE")
    if not path.is_file() or path.stat().st_size > MAX_FILE:
        raise FileSetError("SOURCE_FILE_MISSING_OR_OVERSIZED")
    return path.read_bytes()


def source_files(root: Path) -> frozenset[str]:
    base = Path(root) / SERVICE
    found = set()
    for path in base.rglob("*"):
        if "__pycache__" in path.parts:
            continue
        if path.is_symlink():
            raise FileSetError("SYMLINK_IN_SOURCE")
        if path.is_file():
            found.add(path.relative_to(root).as_posix())
    return frozenset(found)


def check_source_tree(root: Path) -> None:
    if source_files(root) != SOURCE_FILES:
        raise FileSetError("RECOVERY_WITNESS_FILE_SET_MISMATCH")


def runtime_payloads(root: Path) -> dict[str, bytes]:
    root = Path(root).resolve()
    check_source_tree(root)
    payloads = {target: _read(root, source) for source, target in RUNTIME_SOURCE_MAP.items()}
    for data in payloads.values():
        for marker in FORBIDDEN_RUNTIME_MARKERS:
            if marker in data:
                raise FileSetError("FORBIDDEN_RUNTIME_MARKER")
    return payloads


def files_digest(files: dict[str, str]) -> str:
    """SHA-256 of JCS `{path: sha256}` (flat ASCII map: sorted, compact)."""
    return _digest(json.dumps(dict(sorted(files.items())), sort_keys=True, separators=(",", ":")).encode("ascii"))


def runtime_manifest(root: Path) -> dict:
    files = {name: _digest(data) for name, data in sorted(runtime_payloads(root).items())}
    return {"role": "lilith-recovery-witness-dev-synthetic-source-v1", "status": "SOURCE_PREPARED_NOT_INSTALLED",
            "files": files, "runtimeSha256": files_digest(files)}


if __name__ == "__main__":
    json.dump(runtime_manifest(Path(__file__).resolve().parents[2]), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
