#!/usr/bin/env python3
"""Reproducible-build comparison and non-authority build attestation (B1b-3e PR-1A).

Record: docs/architecture/slice-15b2b-b1b3e-pr1a-build-attestation.md.
It runs on the owner workstation only, contacts nothing, and writes only the
named output file.

    inspect --sha <40-hex> --source-root <clean checkout> --archive <tar.gz> \\
            --stamp <builder attestation json> --out <inspection.json>
    attest  --a <inspection A> --b <inspection B> --out <attestation.json>
    check   --attestation <attestation.json> --sha <40-hex> --archive <tar.gz> \\
            --stamp <builder attestation json>

`inspect` verifies the archive with the installer's own `verify_archive`.
It then records the complete identity of one build:

- archive bytes and the gzip header;
- every tar member header;
- every payload file with its install mode;
- the three runtime digests;
- unit and CLI digests with their host targets;
- the pinned dependency inventory;
- the build recipe.

`attest` refuses unless two inspections are identical in every identity
field. Only `environment` (human provenance) may differ. It then writes the
canonical attestation, whose digest is

    SHA-256("LILITH_PR1A_BUILD_ATTESTATION_V1\\0" || canonical JSON)

`check` re-inspects an archive and requires it to be the attested artifact.

The attestation is build provenance only. It is not authority, not K-ROOT,
not owner acceptance, and it authorizes no installation.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import platform
import subprocess
import sys
import tarfile
import zlib
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for path in (HERE, ROOT / "services/authority-dev"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import install_authority_dev as I  # noqa: E402
import release_file_set as RFS  # noqa: E402

INSPECTION_TYPE = "LILITH_AUTHORITY_DEV_BUILD_INSPECTION"
ATTESTATION_TYPE = "LILITH_AUTHORITY_DEV_PR1A_BUILD_ATTESTATION"
DOMAIN_SEPARATOR = b"LILITH_PR1A_BUILD_ATTESTATION_V1\x00"
# The build recipe: every file whose bytes decide the archive bytes besides the payload itself.
RECIPE_FILES = (
    "services/authority-dev/ceremony/build_authority_dev_release.py",
    "services/authority-dev/ceremony/install_authority_dev.py",
    "services/authority-dev/release_file_set.py",
    "services/recovery-witness/witness_release_file_set.py",
)
NONCLAIMS = ("NOT_AUTHORITY", "NOT_K_ROOT", "NOT_OWNER_ACCEPTANCE", "NOT_INSTALL_AUTHORIZATION",
             "NOT_LIVE_EVIDENCE", "VENV_BUILT_ON_HOST_NOT_ATTESTED_AS_BYTES")


class AttestError(RuntimeError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    """Compact sorted ASCII JSON (JCS for this string/int/bool/list/object data)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def attestation_digest(document: dict) -> str:
    return sha256(DOMAIN_SEPARATOR + canonical(document))


def recipe(source_root: Path) -> dict:
    files = {}
    for relative in RECIPE_FILES:
        path = Path(source_root, *relative.split("/"))
        if path.is_symlink() or not path.is_file():
            raise AttestError("RECIPE_FILE_MISSING:" + relative)
        files[relative] = sha256(path.read_bytes())
    return {"files": files, "sha256": sha256(canonical(files))}


def _members(raw: bytes) -> list[dict]:
    members = []
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        for item in tar:
            if item.name.startswith("/") or ".." in item.name.split("/"):
                raise AttestError("UNSAFE_MEMBER_PATH:" + item.name)
            members.append({"name": item.name, "type": item.type.decode("ascii", "replace"), "mode": format(item.mode, "04o"),
                            "uid": item.uid, "gid": item.gid, "uname": item.uname, "gname": item.gname,
                            "mtime": int(item.mtime), "size": item.size, "linkname": item.linkname,
                            "paxHeaders": dict(sorted(item.pax_headers.items()))})
    return members


def _gzip_header(raw: bytes) -> dict:
    if len(raw) < 10 or raw[:2] != b"\x1f\x8b":
        raise AttestError("NOT_GZIP")
    return {"method": raw[2], "flags": raw[3], "mtime": int.from_bytes(raw[4:8], "little"), "xfl": raw[8],
            "os": raw[9]}


def inspect_build(archive: Path, stamp: Path, sha: str, source_root: Path) -> dict:
    """The complete identity of one build (plus provenance that is not identity)."""
    raw = Path(archive).read_bytes()
    stamp_bytes = Path(stamp).read_bytes()
    try:
        manifest, payloads = I.verify_archive(Path(archive), Path(stamp), sha)
    except I.InstallError as exc:
        raise AttestError("ARCHIVE_REFUSED:" + exc.reason) from exc
    members = _members(raw)
    names = [member["name"] for member in members]
    if names != sorted(names) or set(names) != I.EXPECTED_PATHS | {I.MANIFEST}:
        raise AttestError("MEMBER_SET_OR_ORDER")
    files = {path: sha256(data) for path, data in sorted(payloads.items())}
    install_modes = {path: ("0755" if path in I.CLI_TARGETS else "0644") for path in files}
    executables = sorted(path for path, mode in install_modes.items() if mode == "0755")
    if executables != sorted(I.CLI_TARGETS):
        raise AttestError("EXECUTABLE_SET")
    host_targets = {**I.UNIT_TARGETS, **I.WITNESS_UNIT_TARGETS, **I.CLI_TARGETS}
    wheels = {path.split("/", 1)[1]: files[path] for path in files if path.startswith("wheels/")}
    dependency = {"requirementsLockSha256": files["requirements.lock"], "wheels": wheels}
    identity = {
        "sourceCommit": sha,
        "releaseRole": I.ROLE,
        "buildRecipe": recipe(source_root),
        "archive": {"sha256": sha256(raw), "byteSize": len(raw), "gzipHeader": _gzip_header(raw),
                    "uncompressedTarSha256": sha256(gzip.decompress(raw))},
        "builderStamp": {"sha256": sha256(stamp_bytes), "document": json.loads(stamp_bytes)},
        "manifest": {"sha256": sha256(I.canonical(manifest)), "fileCount": len(manifest["files"]),
                     "header": {k: v for k, v in manifest.items() if k != "files"}},
        "tarMembers": members,
        "payload": {path: {"sha256": files[path], "size": len(payloads[path]), "installMode": install_modes[path]}
                    for path in files},
        "runtimeDigests": {"authority": RFS.files_digest(files, RFS.AUTHORITY_RUNTIME_PREFIXES),
                           "witness": RFS.files_digest(files, RFS.WITNESS_RUNTIME_PREFIXES),
                           "rootTooling": RFS.files_digest(files, RFS.ROOT_TOOLING_PREFIXES)},
        "unitDigests": {path: files[path] for path in files if path.startswith("assets/")},
        "cliDigests": {path: files[path] for path in files if path.startswith("cli/")},
        "hostTargets": {target: {"member": member, "sha256": files[member],
                                 "installMode": install_modes[member]}
                        for member, target in sorted(host_targets.items())},
        "dependencyInventory": {**dependency, "sha256": sha256(canonical(dependency))},
    }
    environment = {"python": platform.python_version(), "implementation": platform.python_implementation(),
                   "platform": platform.platform(), "zlibVersion": zlib.ZLIB_VERSION,
                   "zlibRuntimeVersion": getattr(zlib, "ZLIB_RUNTIME_VERSION", None)}
    return {"inspectionType": INSPECTION_TYPE, "schemaVersion": 1, "identity": identity,
            "identitySha256": sha256(canonical(identity)), "environment": environment}


def differences(left: Any, right: Any, path: str = "") -> list[str]:
    """Every identity path whose value differs (deep, exact)."""
    if isinstance(left, dict) and isinstance(right, dict):
        found = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                found.append(f"{path}/{key}:{'MISSING_IN_A' if key not in left else 'MISSING_IN_B'}")
            else:
                found.extend(differences(left[key], right[key], f"{path}/{key}"))
        return found
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        return [d for index, (a, b) in enumerate(zip(left, right)) for d in differences(a, b, f"{path}[{index}]")]
    return [] if left == right else [path or "/"]


def _require_inspection(value: Any) -> dict:
    if not isinstance(value, dict) or value.get("inspectionType") != INSPECTION_TYPE or value.get("schemaVersion") != 1 \
            or value.get("identitySha256") != sha256(canonical(value.get("identity"))):
        raise AttestError("INSPECTION_MALFORMED")
    return value


def build_attestation(a: dict, b: dict) -> dict:
    a, b = _require_inspection(a), _require_inspection(b)
    diff = differences(a["identity"], b["identity"])
    if diff:
        raise AttestError("NOT_REPRODUCED:" + ",".join(diff[:50]))
    identity = a["identity"]
    return {
        "attestationType": ATTESTATION_TYPE, "schemaVersion": 1,
        "artifactRole": "lilith-authority-dev-pr1a-install-candidate",
        "sourceCommit": identity["sourceCommit"], "releaseRole": identity["releaseRole"],
        "buildRecipeSha256": identity["buildRecipe"]["sha256"], "buildRecipeFiles": identity["buildRecipe"]["files"],
        "archiveSha256": identity["archive"]["sha256"], "archiveByteSize": identity["archive"]["byteSize"],
        "uncompressedTarSha256": identity["archive"]["uncompressedTarSha256"],
        "builderStampSha256": identity["builderStamp"]["sha256"],
        "manifestSha256": identity["manifest"]["sha256"], "payloadFileCount": len(identity["payload"]),
        "authorityReleaseDigest": identity["runtimeDigests"]["authority"],
        "rootToolingDigest": identity["runtimeDigests"]["rootTooling"],
        "recoveryWitnessReleaseDigest": identity["runtimeDigests"]["witness"],
        "unitDigests": identity["unitDigests"], "cliDigests": identity["cliDigests"],
        "hostTargets": identity["hostTargets"],
        "dependencyInventorySha256": identity["dependencyInventory"]["sha256"],
        "dependencyInventory": {k: v for k, v in identity["dependencyInventory"].items() if k != "sha256"},
        "payloadSha256": sha256(canonical({p: v["sha256"] for p, v in identity["payload"].items()})),
        "reproducibility": {"result": "REPRODUCED", "independentBuilds": 2,
                            "buildAIdentitySha256": a["identitySha256"], "buildBIdentitySha256": b["identitySha256"],
                            "buildAArchiveSha256": a["identity"]["archive"]["sha256"],
                            "buildBArchiveSha256": b["identity"]["archive"]["sha256"]},
        "nonclaims": list(NONCLAIMS),
    }


def check_candidate(attestation: dict, inspection: dict) -> list[str]:
    """Pass-2 pre-stage check: this archive is exactly the attested candidate."""
    identity = _require_inspection(inspection)["identity"]
    failures = []
    for key, observed in (("sourceCommit", identity["sourceCommit"]), ("archiveSha256", identity["archive"]["sha256"]),
                          ("builderStampSha256", identity["builderStamp"]["sha256"]),
                          ("manifestSha256", identity["manifest"]["sha256"]),
                          ("authorityReleaseDigest", identity["runtimeDigests"]["authority"]),
                          ("rootToolingDigest", identity["runtimeDigests"]["rootTooling"]),
                          ("recoveryWitnessReleaseDigest", identity["runtimeDigests"]["witness"]),
                          ("unitDigests", identity["unitDigests"]), ("cliDigests", identity["cliDigests"]),
                          ("hostTargets", identity["hostTargets"]),
                          ("dependencyInventorySha256", identity["dependencyInventory"]["sha256"])):
        if attestation.get(key) != observed:
            failures.append("CANDIDATE_MISMATCH:" + key)
    return failures


def _git_exact_clean(root: Path, sha: str) -> None:
    head = subprocess.run(("git", "-C", str(root), "rev-parse", "HEAD"), text=True, capture_output=True,
                          check=True).stdout.strip()
    dirty = subprocess.run(("git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"), text=True,
                           capture_output=True, check=True).stdout.strip()
    if head != sha or dirty:
        raise AttestError("SOURCE_NOT_EXACT_CLEAN_SHA")


def _write_new(path: Path, data: bytes) -> None:
    if path.exists():
        raise AttestError("OUTPUT_EXISTS")
    path.write_bytes(data)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("inspect")
    one.add_argument("--sha", required=True)
    one.add_argument("--source-root", type=Path, required=True)
    one.add_argument("--archive", type=Path, required=True)
    one.add_argument("--stamp", type=Path, required=True)
    one.add_argument("--out", type=Path, required=True)
    two = sub.add_parser("attest")
    two.add_argument("--a", type=Path, required=True)
    two.add_argument("--b", type=Path, required=True)
    two.add_argument("--out", type=Path, required=True)
    three = sub.add_parser("check")
    three.add_argument("--attestation", type=Path, required=True)
    three.add_argument("--sha", required=True)
    three.add_argument("--source-root", type=Path, required=True)
    three.add_argument("--archive", type=Path, required=True)
    three.add_argument("--stamp", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            _git_exact_clean(args.source_root, args.sha)
            value = inspect_build(args.archive, args.stamp, args.sha, args.source_root)
            _write_new(args.out, json.dumps(value, sort_keys=True, indent=1).encode("ascii") + b"\n")
            print(f"BUILD_INSPECTION identitySha256={value['identitySha256']} "
                  f"archiveSha256={value['identity']['archive']['sha256']}")
        elif args.command == "attest":
            document = build_attestation(json.loads(args.a.read_bytes()), json.loads(args.b.read_bytes()))
            _write_new(args.out, canonical(document) + b"\n")
            print(f"PR1A_BUILD_ATTESTATION=REPRODUCED attestationDigest={attestation_digest(document)} "
                  f"archiveSha256={document['archiveSha256']}")
        else:
            document = json.loads(args.attestation.read_bytes())
            if args.attestation.read_bytes() != canonical(document) + b"\n":
                raise AttestError("ATTESTATION_NOT_CANONICAL")
            _git_exact_clean(args.source_root, args.sha)
            failures = check_candidate(document, inspect_build(args.archive, args.stamp, args.sha, args.source_root))
            print(json.dumps({"attestationDigest": attestation_digest(document), "failures": failures,
                              "result": "PASS" if not failures else "FAIL"}, sort_keys=True))
            return 0 if not failures else 1
    except AttestError as exc:
        print(f"attest_authority_dev_build: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
