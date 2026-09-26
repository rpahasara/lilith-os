#!/usr/bin/env python3
"""Exact source and runtime file-set contract for `lilith-authority-dev` (B1b-3d L1).

This is packaging policy, not an installer. It reads the repository tree
only, writes nothing, and contacts nothing. It fails closed on:

- any source file under `services/authority-dev/` that is not listed here;
- any symlink;
- a change to a governed shared contract module (pinned SHA-256);
- a private-key, TEST-seed, TEST-signer, or key-generation marker in any
  runtime payload file.

The runtime payload is what a later owner-installed release tree under
`/opt/lilith-authority-dev/releases/<sha>` may contain. Tests, this file, the
README, and every TEST fixture are never runtime payload. Wheels and the
installer are later slices; they are not defined here.

    source-controlled artifact != installed service
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

SERVICE = "services/authority-dev"
RUNTIME_PACKAGE = SERVICE + "/lilith_authority_dev"
RUNTIME_MODULES = frozenset({
    "__init__.py", "profile.py", "credential.py", "evidence_minter.py", "protocol.py", "core.py", "server.py",
})
DEPLOY_ASSETS = frozenset({
    "lilith-authority-dev.service", "lilith-authority-dev.socket", "lilith-authority-dev.tmpfiles.conf",
})
TEST_FILES = frozenset({"test_authority_dev_foundation.py"})
SOURCE_FILES = frozenset(
    {f"{RUNTIME_PACKAGE}/{name}" for name in RUNTIME_MODULES}
    | {f"{SERVICE}/deploy/{name}" for name in DEPLOY_ASSETS}
    | {f"{SERVICE}/tests/{name}" for name in TEST_FILES}
    | {f"{SERVICE}/README.md", f"{SERVICE}/release_file_set.py"}
)

# Accepted contracts the runtime imports. Pinned: any change to them needs a
# deliberate re-review of the signer boundary and an update here.
SHARED_HASHES = {
    "services/core-api/lilith_memory/__init__.py":
        "2bbebd95846f1073a0b4e2ec3a2aa24378c56be4ecbb5470e5c1f1d359037e21",
    "services/core-api/lilith_memory/canonical_contracts.py":
        "f93d26d8a7e01d78d25f1f1d9540577cf2a55dfd4d52c4b64c87bef93ad887e0",
    "services/core-api/lilith_memory/owner_proof.py":
        "3a3eb7147d1e276ac261457a2340e045a0c43f6bc63eeb1a78bfc9864f80ac08",
    "services/owner-memory-control/lilith_owner_memory/__init__.py":
        "d1f1bf65a24315005ca4b597971dec6efa0212d4ab5836832e2a5a80fb9e62b4",
    "services/owner-memory-control/lilith_owner_memory/contracts.py":
        "ff5075f1131f84348bdbc5d3fbd3410e53c7da39e265476a0b57ace6ff8ef5c7",
    "services/owner-memory-control/lilith_owner_memory/authority_contracts.py":
        "fabd8fd24f45febe83f8fd67c3fc39f277278e9145df9c55d5e03e5e8598e74f",
}

RUNTIME_SOURCE_MAP = {
    **{f"{RUNTIME_PACKAGE}/{name}": f"lilith_authority_dev/{name}" for name in RUNTIME_MODULES},
    **{path: path.split("/", 2)[2] for path in SHARED_HASHES},
    **{f"{SERVICE}/deploy/{name}": f"assets/{name}" for name in DEPLOY_ASSETS},
}

# Byte markers that must never appear in a runtime payload file.
FORBIDDEN_RUNTIME_MARKERS = (
    b"-----" + b"BEGIN",  # split so this file never matches a secret scan itself
    b"PRIVATE" + b" KEY-----",
    b"OPENSSH" + b" PRIVATE",
    b"TEST_ONLY ",
    b"from_private_bytes",
    b"Ed25519PrivateKey.generate",
    b".generate()",
    b"lilith_authority_signer",
    b"synthetic_authority",
    b"synthetic_broker",
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
    """The exact tracked-shape file set under services/authority-dev."""
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
        raise FileSetError("AUTHORITY_DEV_FILE_SET_MISMATCH")


def runtime_payloads(root: Path) -> dict[str, bytes]:
    root = Path(root).resolve()
    check_source_tree(root)
    payloads = {target: _read(root, source) for source, target in RUNTIME_SOURCE_MAP.items()}
    for source, expected in SHARED_HASHES.items():
        if _digest(payloads[RUNTIME_SOURCE_MAP[source]]) != expected:
            raise FileSetError("GOVERNED_SHARED_MODULE_CHANGED")
    for data in payloads.values():
        for marker in FORBIDDEN_RUNTIME_MARKERS:
            if marker in data:
                raise FileSetError("FORBIDDEN_RUNTIME_MARKER")
    return payloads


def runtime_manifest(root: Path) -> dict:
    payloads = runtime_payloads(root)
    return {
        "role": "lilith-authority-dev-synthetic-owner-actor-signer-source-v1",
        "status": "SOURCE_FOUNDATION_NOT_INSTALLED",
        "files": {name: _digest(data) for name, data in sorted(payloads.items())},
    }


if __name__ == "__main__":
    json.dump(runtime_manifest(Path(__file__).resolve().parents[2]), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
