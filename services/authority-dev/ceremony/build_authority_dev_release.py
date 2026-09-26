#!/usr/bin/env python3
"""Build the deterministic `lilith-authority-dev` release archive (B1b-3d L1b).

Run by the owner on the owner workstation, from a clean checkout of the exact
protected-main commit being installed, with a wheelhouse holding exactly the
pinned wheels. It executes no code from the candidate, contacts nothing, and
writes only the two named output files. It never includes key, credential,
blob, registry, or TEST fixture material.

    python services/authority-dev/ceremony/build_authority_dev_release.py \\
        --candidate-sha <40-hex> --wheelhouse <dir> \\
        --archive <out.tar.gz> --attestation <out.json>

The archive is inert until the owner-authorized L1b.1 installer stage.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for path in (HERE, ROOT / "services/authority-dev"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import install_authority_dev as I  # noqa: E402
import release_file_set as RFS  # noqa: E402

KEYGEN_SOURCE = "services/authority-dev/ceremony/lilith_authority_keygen_dev.py"


def require_exact_clean(root: Path, sha: str) -> None:
    if not I.SHA40.fullmatch(sha):
        raise I.InstallError("INVALID_CANDIDATE_SHA")
    head = subprocess.run(("git", "-C", str(root), "rev-parse", "HEAD"), text=True, capture_output=True,
                          check=True).stdout.strip()
    dirty = subprocess.run(("git", "-C", str(root), "status", "--porcelain", "--untracked-files=all", "--",
                            "services", "scripts"), text=True, capture_output=True, check=True).stdout.strip()
    if head != sha or dirty:
        raise I.InstallError("CANDIDATE_NOT_EXACT_CLEAN_SHA")


def build_payloads(root: Path, wheelhouse: Path) -> dict[str, bytes]:
    root, wheelhouse = Path(root).resolve(), Path(wheelhouse).resolve()
    payloads = dict(RFS.runtime_payloads(root))
    cli = root / KEYGEN_SOURCE
    if cli.is_symlink() or not cli.is_file():
        raise I.InstallError("KEYGEN_SOURCE_MISSING")
    payloads[I.CLI_PATH] = cli.read_bytes()
    if not wheelhouse.is_dir() or {p.name for p in wheelhouse.iterdir()} != set(I.WHEEL_HASHES):
        raise I.InstallError("WHEEL_SET_MISMATCH")
    for name in I.WHEEL_HASHES:
        path = wheelhouse / name
        if path.is_symlink():
            raise I.InstallError("WHEEL_SYMLINK")
        payloads["wheels/" + name] = path.read_bytes()
    payloads["requirements.lock"] = I.LOCK
    I.check_payloads(payloads)
    return payloads


def build(root: Path, wheelhouse: Path, sha: str, archive: Path, attestation: Path) -> dict:
    require_exact_clean(root, sha)
    payloads = build_payloads(root, wheelhouse)
    manifest = I.manifest_for(sha, payloads)
    raw = I.write_archive(payloads, manifest)
    archive, attestation = Path(archive), Path(attestation)
    if archive.exists() or attestation.exists() or archive.resolve() == attestation.resolve():
        raise I.InstallError("OUTPUT_COLLISION")
    stamp = {"schemaVersion": 1, "artifactRole": I.ROLE, "candidateSha": sha, "archiveByteSize": len(raw),
             "archiveSha256": I.digest(raw), "manifestSha256": I.digest(I.canonical(manifest))}
    archive.write_bytes(raw)
    attestation.write_bytes(I.canonical(stamp))
    I.verify_archive(archive, attestation, sha)  # round trip with the installer's own verifier
    return stamp


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--attestation", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(ROOT, args.wheelhouse, args.candidate_sha, args.archive, args.attestation),
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
