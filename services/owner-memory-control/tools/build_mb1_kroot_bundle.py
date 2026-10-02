#!/usr/bin/env python3
"""Build the deterministic S25 Termux bundle for the real M-B1 K-ROOT ceremony (laptop, offline).

Record: docs/architecture/slice-15b2b-b1b3e-mb1-kroot-ceremony-package.md.

    python build_mb1_kroot_bundle.py --repo <clean checkout> --commit <40-hex merged SHA>
        --vendor-dir <verified vendor/ with fido2 and rfc8785> --out <tar>

The bundle holds exactly:

- the import closure of the owner tool's `root-keygen` (`CLOSURE`), taken from
  `git show <commit>:<path>` rather than from the working tree;
- `burned_identities.py`, for the phone-side burned-identity refusal;
- the pure-Python `vendor/` set;
- `SOURCE_COMMIT` and `SHA256SUMS`.

It holds no rehearsal script, no key, no passphrase, and no authority
material. Only `root-keygen` is ever run from it; the operator script never
invokes `registry-v1`, `witness-anchor`, `reproduce`, or `package-digest`.
The tar format is the reviewed B-4 one (sorted names, mtime 0, owner 0:0,
modes 0644 / 0755). Building it contacts nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import subprocess
import sys
import tarfile
from pathlib import Path

_B4 = Path(__file__).resolve().with_name("build_termux_kroot_rehearsal_bundle.py")
_spec = importlib.util.spec_from_file_location("_b4_bundle", _B4)
B4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B4)                         # the reviewed B-4 primitives: vendor check, sums, format

OWNER_TOOL = "services/authority-dev/ceremony/lilith_authority_owner_dev.py"
BURNED = "services/owner-memory-control/lilith_owner_memory/burned_identities.py"
# The import closure of lilith_authority_owner_dev.py (pinned by a test), plus burned_identities.py.
CLOSURE = (
    OWNER_TOOL,
    "services/core-api/lilith_memory/__init__.py",
    "services/core-api/lilith_memory/canonical_contracts.py",
    "services/core-api/lilith_memory/owner_proof.py",
    "services/owner-memory-control/lilith_owner_memory/__init__.py",
    "services/owner-memory-control/lilith_owner_memory/authority_contracts.py",
    "services/owner-memory-control/lilith_owner_memory/authority_ledger_journal.py",
    "services/owner-memory-control/lilith_owner_memory/authority_verifier.py",
    "services/owner-memory-control/lilith_owner_memory/contracts.py",
    "services/owner-memory-control/lilith_owner_memory/pr1_acceptance.py",
    "services/owner-memory-control/lilith_owner_memory/pr1_bootstrap.py",
    "services/owner-memory-control/lilith_owner_memory/recovery_contracts.py",
    "services/owner-memory-control/lilith_owner_memory/rotation_contracts.py",
    "services/owner-memory-control/lilith_owner_memory/successor_custody.py",
    "services/owner-memory-control/lilith_owner_memory/successor_readiness.py",
    "services/owner-memory-control/lilith_owner_memory/witness_readiness.py",
    BURNED,
)
BuildError = B4.BuildError
VENDOR_TOPS = B4.VENDOR_TOPS


FORBIDDEN_NAME_PARTS = ("k-root", ".der", ".pem", ".cred", "secret", "passphrase")


def _refuse_forbidden(name: str) -> None:
    if any(part in name.lower() for part in FORBIDDEN_NAME_PARTS):
        raise BuildError("FORBIDDEN_MEMBER_NAME:" + name)


def bundle_members(repo: Path, commit: str, vendor_dir: Path) -> dict[str, bytes]:
    """Relative path -> bytes, before SHA256SUMS."""
    for name in CLOSURE:
        _refuse_forbidden(name)
    if not B4.SHA40.fullmatch(commit):
        raise BuildError("COMMIT_NOT_40_HEX")
    if sorted(p.name for p in vendor_dir.iterdir()) != sorted(VENDOR_TOPS):
        raise BuildError("VENDOR_SET_MISMATCH")
    try:
        members = {path: B4._git_show(repo, commit, path) for path in CLOSURE}
    except subprocess.CalledProcessError as exc:
        raise BuildError("SOURCE_NOT_AT_COMMIT") from exc
    for file in sorted(vendor_dir.rglob("*")):
        if file.is_symlink():
            raise BuildError("VENDOR_SYMLINK")
        if file.is_file() and "__pycache__" not in file.parts and not file.name.endswith(".pyc"):
            members["vendor/" + file.relative_to(vendor_dir).as_posix()] = file.read_bytes()
    for name in members:
        _refuse_forbidden(name)
    members["SOURCE_COMMIT"] = (commit + "\n").encode("ascii")
    return members


def build(repo: Path, commit: str, vendor_dir: Path, out: Path) -> dict[str, str]:
    members = bundle_members(repo, commit, vendor_dir)
    members["SHA256SUMS"] = B4.sha256sums(members)
    top = f"lilith-mb1-kroot-{commit[:7]}"
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        directories = {top}
        for name in members:
            parts = name.split("/")
            directories.update(f"{top}/{'/'.join(parts[:i])}" for i in range(1, len(parts)))
        for name in sorted(directories):
            info = tarfile.TarInfo(name)
            info.type, info.mode, info.mtime, info.uid, info.gid = tarfile.DIRTYPE, 0o755, 0, 0, 0
            info.uname = info.gname = ""
            tar.addfile(info)
        for name in sorted(members):
            data = members[name]
            info = tarfile.TarInfo(f"{top}/{name}")
            info.size, info.mode, info.mtime, info.uid, info.gid = len(data), 0o644, 0, 0, 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(data))
    raw = buffer.getvalue()
    out.write_bytes(raw)
    return {"bundle": out.name, "top": top, "files": str(len(members)),
            "tarSha256": hashlib.sha256(raw).hexdigest(),
            "sha256sumsSha256": hashlib.sha256(members["SHA256SUMS"]).hexdigest(), "sourceCommit": commit}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--vendor-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.out.exists():
        print("build refused: output exists", file=sys.stderr)
        return 2
    try:
        result = build(args.repo, args.commit, args.vendor_dir, args.out)
    except (BuildError, subprocess.CalledProcessError, OSError) as exc:
        print(f"build refused: {exc}", file=sys.stderr)
        return 2
    for key, value in result.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
