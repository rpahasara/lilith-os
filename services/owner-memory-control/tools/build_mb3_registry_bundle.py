#!/usr/bin/env python3
"""Build the deterministic public-only S25 Termux bundle for M-B3 / SIGN_REGISTRY_V1 (laptop, offline).

Record: docs/architecture/slice-15b2b-b1b3e-mb3-registry-ceremony-package.md §3.

    python build_mb3_registry_bundle.py --repo <clean checkout> --commit <40-hex merged SHA>
        --vendor-dir <verified vendor/ with fido2 and rfc8785> --out <tar>

The bundle holds exactly:

- the reviewed M-B1 import closure of `lilith_authority_owner_dev.py` (whose
  unchanged `registry-v1` form makes the one K-ROOT signature) and
  `burned_identities.py`;
- `tools/mb3_registry_ceremony.py`, the public-only PREPARE / verification logic;
- the pure-Python `vendor/` set;
- `SOURCE_COMMIT` and `SHA256SUMS`.

Sources come from `git show <commit>:<path>`, never the working tree. The
phone script `mb3_phone_ceremony.py` is NOT a member: it is transferred beside
the bundle and pinned separately. The bundle's own SHA-256 is printed and is
never written inside it; the owner go binds it from outside.

It holds no key, no passphrase, no K-WIT credential, no public input (those
come from the fresh sequence), and no authority material. Format: the reviewed
B-4 / M-B1 one (sorted names, mtime 0, owner 0:0, modes 0644 / 0755).
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

_MB1 = Path(__file__).resolve().with_name("build_mb1_kroot_bundle.py")
_spec = importlib.util.spec_from_file_location("_mb1_bundle", _MB1)
MB1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(MB1)
B4 = MB1.B4

LIBRARY = "services/owner-memory-control/tools/mb3_registry_ceremony.py"
PHONE_SCRIPT = "services/owner-memory-control/tools/mb3_phone_ceremony.py"
CLOSURE = tuple(MB1.CLOSURE) + (LIBRARY,)
BuildError = B4.BuildError
VENDOR_TOPS = B4.VENDOR_TOPS
FORBIDDEN_NAME_PARTS = MB1.FORBIDDEN_NAME_PARTS + ("kact-publication", "kwit-publication", "mb3-inputs")


def _refuse_forbidden(name: str) -> None:
    if any(part in name.lower() for part in FORBIDDEN_NAME_PARTS):
        raise BuildError("FORBIDDEN_MEMBER_NAME:" + name)


def bundle_members(repo: Path, commit: str, vendor_dir: Path) -> dict[str, bytes]:
    if PHONE_SCRIPT in CLOSURE:
        raise BuildError("PHONE_SCRIPT_IN_BUNDLE")
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
    top = f"lilith-mb3-registry-{commit[:7]}"
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
    script = B4._git_show(repo, commit, PHONE_SCRIPT)
    return {"bundle": out.name, "top": top, "files": str(len(members)),
            "tarSha256": hashlib.sha256(raw).hexdigest(),
            "sha256sumsSha256": hashlib.sha256(members["SHA256SUMS"]).hexdigest(), "sourceCommit": commit,
            "phoneScript": PHONE_SCRIPT, "phoneScriptSha256": hashlib.sha256(script).hexdigest()}


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
