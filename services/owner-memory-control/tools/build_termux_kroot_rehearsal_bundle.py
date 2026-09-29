#!/usr/bin/env python3
"""Build the deterministic Termux bundle for the B-4 K-ROOT capability rehearsal (laptop, offline).

Record: docs/architecture/slice-15b2b-b1b3e-b4-termux-kroot-rehearsal.md.

    python build_termux_kroot_rehearsal_bundle.py --repo <clean checkout> --commit <40-hex merged SHA>
        --vendor-dir <verified vendor/ with fido2 and rfc8785> --out <tar>

The bundle holds exactly:

- the import closure of the owner tool (`CLOSURE`), taken from `git show
  <commit>:<path>` rather than from the working tree;
- the rehearsal script;
- the pure-Python `vendor/` set;
- `SOURCE_COMMIT`;
- `SHA256SUMS`.

`cryptography` is native and must already be installed in Termux (the P3-3B
G0 gate). The tar is deterministic: sorted names, mtime 0, owner 0:0, and
modes 0644 / 0755. It holds no key, no passphrase, and no real authority
material. Building it contacts nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import subprocess
import sys
import tarfile
from pathlib import Path

REHEARSAL = "services/owner-memory-control/tools/termux_kroot_rehearsal.py"
# The import closure of lilith_authority_owner_dev.py + lilith_authority_keygen_dev.py (pinned by a test).
CLOSURE = (
    "services/authority-dev/ceremony/lilith_authority_keygen_dev.py",
    "services/authority-dev/ceremony/lilith_authority_owner_dev.py",
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
)
VENDOR_TOPS = ("fido2", "fido2-2.2.1.dist-info", "rfc8785", "rfc8785-0.1.4.dist-info")
SHA40 = re.compile(r"[0-9a-f]{40}\Z")


class BuildError(Exception):
    pass


def _git_show(repo: Path, commit: str, path: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), "show", f"{commit}:{path}"], check=True,
                          capture_output=True).stdout


def bundle_members(repo: Path, commit: str, vendor_dir: Path) -> dict[str, bytes]:
    """Relative path -> bytes, before SHA256SUMS."""
    if not SHA40.fullmatch(commit):
        raise BuildError("COMMIT_NOT_40_HEX")
    if sorted(p.name for p in vendor_dir.iterdir()) != sorted(VENDOR_TOPS):
        raise BuildError("VENDOR_SET_MISMATCH")
    try:
        members = {path: _git_show(repo, commit, path) for path in (*CLOSURE, REHEARSAL)}
    except subprocess.CalledProcessError as exc:
        raise BuildError("SOURCE_NOT_AT_COMMIT") from exc
    for file in sorted(vendor_dir.rglob("*")):
        if file.is_symlink():
            raise BuildError("VENDOR_SYMLINK")
        if file.is_file() and "__pycache__" not in file.parts and not file.name.endswith(".pyc"):
            members["vendor/" + file.relative_to(vendor_dir).as_posix()] = file.read_bytes()
    members["SOURCE_COMMIT"] = (commit + "\n").encode("ascii")
    return members


def sha256sums(members: dict[str, bytes]) -> bytes:
    return "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(members.items())).encode()


def build(repo: Path, commit: str, vendor_dir: Path, out: Path) -> dict[str, str]:
    members = bundle_members(repo, commit, vendor_dir)
    members["SHA256SUMS"] = sha256sums(members)
    top = f"lilith-b4-kroot-rehearsal-{commit[:7]}"
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
