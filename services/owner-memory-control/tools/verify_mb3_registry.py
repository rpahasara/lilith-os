#!/usr/bin/env python3
"""Laptop-side independent M-B3 verification of the public S25 export (offline, public bytes only).

Record: docs/architecture/slice-15b2b-b1b3e-mb3-registry-ceremony-package.md §9.

    python verify_mb3_registry.py --export <lilith-mb3-export.tar> --control-sha <40hex> \\
        --bundle-sha256 <64hex> --manifest-sha256 <64hex> --kact-publication-sha256 <64hex> \\
        [--real-registry-burns <register.json>]

Every pin comes from the owner go, never from the export. It reads the tar
without extracting it, checks the exact public allowlist, re-runs the accepted
verification, and rebuilds the signing bytes with this checkout's owner tool.
A pass is technical evidence for REGISTRY_SIGNED. It is not owner acceptance
and authorizes nothing (no install, no M-B4/M-B5).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for _path in (ROOT / "services/core-api", ROOT / "services/owner-memory-control"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


L = _load("mb3_registry_ceremony", Path(__file__).resolve().with_name("mb3_registry_ceremony.py"))
PHONE = _load("mb3_phone_ceremony", Path(__file__).resolve().with_name("mb3_phone_ceremony.py"))
SUCCESS_EXPORT = PHONE.SUCCESS_EXPORT  # the phone script's exact success allowlist


def verify_export(export: Path, *, control_sha: str, bundle_sha256: str, manifest_sha256: str,
                  kact_publication_sha256: str, real_registry_burns=(), accepted=None) -> tuple[bool, list[str], str]:
    accepted = accepted or L.ACCEPTED
    lines: list[str] = []
    with tarfile.open(export, "r:") as tar:
        members = {m.name: m for m in tar.getmembers()}
        if sorted(members) != list(SUCCESS_EXPORT) or not all(m.isfile() for m in members.values()):
            return False, lines, "EXPORT_NOT_EXACT_ALLOWLIST"
        data = {name: tar.extractfile(m).read() for name, m in members.items()}
    lines.append("EXPORT_EXACT_PUBLIC_ALLOWLIST")
    manifest_raw = data["lilith-mb3/mb3-inputs.json"]
    if hashlib.sha256(manifest_raw).hexdigest() != manifest_sha256:
        return False, lines, "MANIFEST_SHA256_NOT_GO"
    manifest = json.loads(manifest_raw)
    if (manifest.get("controlSha"), manifest.get("bundleSha256"), manifest.get("kactPublicationSha256")) != (
            control_sha, bundle_sha256, kact_publication_sha256):
        return False, lines, "MANIFEST_NOT_GO_PINS"
    lines.append("MANIFEST_EQUALS_GO_PINS")
    registry_raw = data["lilith-mb3-registry-public/authority-registry.v1.json"]
    owner_tool = _load("mb3_laptop_owner_tool", ROOT / L.OWNER_TOOL)
    result = L.verify_signed_registry(
        registry_raw=registry_raw, manifest_raw=manifest_raw,
        root_anchor_raw=data["lilith-mb3/inputs/root-anchor.json"],
        kact_raw=data["lilith-mb3/inputs/kact-publication.json"],
        kwit_raw=data["lilith-mb3/inputs/kwit-publication.json"], accepted=accepted,
        real_registry_burns=real_registry_burns, registry_v1=owner_tool.registry_v1)
    lines += list(result.tokens)
    if not result.verified:
        return False, lines, str(result.reason)
    digest_file = data["lilith-mb3-registry-public/authority-registry.v1.digest"].decode("ascii")
    if digest_file != result.registry_digest + "\n":
        return False, lines, "S25_DIGEST_FILE_DIFFERS"
    if data["lilith-mb3/registry-signing-bytes.bin"] != L.A.registry_signing_bytes(
            {k: v for k, v in json.loads(registry_raw).items() if k != "signature"}):
        return False, lines, "SIGNING_BYTES_FILE_DIFFERS"
    lines.append("S25_DIGEST_FILE_EQUAL")
    return True, lines, result.registry_digest


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", required=True, type=Path)
    parser.add_argument("--control-sha", required=True)
    parser.add_argument("--bundle-sha256", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--kact-publication-sha256", required=True)
    parser.add_argument("--real-registry-burns", type=Path)
    args = parser.parse_args(argv)
    burns = json.loads(args.real_registry_burns.read_bytes()) if args.real_registry_burns else []
    try:
        ok, lines, detail = verify_export(args.export, control_sha=args.control_sha, bundle_sha256=args.bundle_sha256,
                                          manifest_sha256=args.manifest_sha256,
                                          kact_publication_sha256=args.kact_publication_sha256,
                                          real_registry_burns=burns)
    except (OSError, tarfile.TarError, ValueError, KeyError, L.Mb3Refusal) as exc:
        print(f"MB3_LAPTOP_VERIFY_REFUSED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    for line in lines:
        print(line)
    if not ok:
        print(f"MB3_LAPTOP_VERIFY_FAILED {detail}")
        return 1
    print(f"MB3_LAPTOP_VERIFIED registryDigest={detail}")
    print("TECHNICAL EVIDENCE ONLY: not owner acceptance; nothing installed; M-B4/M-B5 NOT AUTHORIZED.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
