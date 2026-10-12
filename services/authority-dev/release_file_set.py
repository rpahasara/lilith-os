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
README, and every TEST fixture are never runtime payload.

B1b-3e PR-1S (docs/architecture/slice-15b2b-b1b3e-pr1s-runtime-wiring.md):
the ONE reviewed release PR-1A installs (RR-33) carries the signer runtime
(with the durable ledger and C-4 wiring), the shared host observers
(`lilith_authority_host`), the root ceremony tooling
(`lilith_authority_root`), and the recovery-witness payload from
`services/recovery-witness/` (its own file set and manifest identity), plus
the pinned shared contracts they import. `runtime_manifest` reports one
digest per runtime owner (authority, witness, root tooling).

    source-controlled artifact != installed service
    source release prepared    != installed release
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

SERVICE = "services/authority-dev"
RUNTIME_PACKAGE = SERVICE + "/lilith_authority_dev"
RUNTIME_MODULES = frozenset({
    "__init__.py", "profile.py", "credential.py", "evidence_minter.py", "protocol.py", "core.py", "server.py",
    "ledger.py", "recovery.py", "state.py", "witness_client.py",
})
HOST_PACKAGE = SERVICE + "/lilith_authority_host"
HOST_MODULES = frozenset({"__init__.py", "paths.py", "inputs.py", "store_observer.py"})
ROOT_PACKAGE = SERVICE + "/lilith_authority_root"
ROOT_MODULES = frozenset({"__init__.py", "hold_store.py", "observers.py", "verifier.py", "genesis.py",
                          "ledger_tool.py", "clients.py", "cli.py"})
DEPLOY_ASSETS = frozenset({
    "lilith-authority-dev.service", "lilith-authority-dev.socket", "lilith-authority-dev.tmpfiles.conf",
})
TEST_FILES = frozenset({"test_authority_dev_foundation.py", "test_custody_preparation.py",
                        "test_successor_custody.py", "test_pr1s_runtime_wiring.py", "test_pr1s_installer_upgrade.py",
                        "test_pr1s_root_tooling.py", "test_recovery_witness_suite.py", "pr1s_fixtures.py",
                        "test_pr1a_build_attestation.py"})
# Owner ceremony tooling (B1b-3d L2, B1b-3e PR-1S). Never runtime payload; the
# keygen is shipped separately as the release member `cli/lilith-authority-keygen-dev`.
CEREMONY_FILES = frozenset({"lilith_authority_keygen_dev.py", "install_authority_dev.py",
                            "build_authority_dev_release.py", "lilith_authority_owner_dev.py",
                            # B1b-3e PR-1A build gate: owner-workstation attestation and the fixed host observer.
                            "attest_authority_dev_build.py", "observe_authority_dev_host.py"})
# The fixed root CLI wrappers (release members `cli/<name>`).
CLI_FILES = frozenset({"lilith-authority-ledger-dev", "lilith-authority-hold-dev", "lilith-authority-verify-dev",
                       "lilith-authority-recovery-dev", "lilith-recovery-witness-owner-dev"})
SOURCE_FILES = frozenset(
    {f"{RUNTIME_PACKAGE}/{name}" for name in RUNTIME_MODULES}
    | {f"{HOST_PACKAGE}/{name}" for name in HOST_MODULES}
    | {f"{ROOT_PACKAGE}/{name}" for name in ROOT_MODULES}
    | {f"{SERVICE}/deploy/{name}" for name in DEPLOY_ASSETS}
    | {f"{SERVICE}/tests/{name}" for name in TEST_FILES}
    | {f"{SERVICE}/ceremony/{name}" for name in CEREMONY_FILES}
    | {f"{SERVICE}/bin/{name}" for name in CLI_FILES}
    | {f"{SERVICE}/README.md", f"{SERVICE}/release_file_set.py"}
)
KEYGEN_SOURCE = f"{SERVICE}/ceremony/lilith_authority_keygen_dev.py"
CLI_SOURCES = {"cli/lilith-authority-keygen-dev": KEYGEN_SOURCE,
               **{f"cli/{name}": f"{SERVICE}/bin/{name}" for name in CLI_FILES}}


def _witness_file_set():
    """The recovery-witness tree's own contract (services/recovery-witness)."""
    path = Path(__file__).resolve().parents[1] / "recovery-witness" / "witness_release_file_set.py"
    spec = importlib.util.spec_from_file_location("lilith_recovery_witness_release_file_set", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WITNESS = _witness_file_set()

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
    # B1b-3e PR-1S: the accepted pure contracts the signer, witness, and root
    # tooling import. Unchanged accepted modules keep their merged bytes.
    "services/owner-memory-control/lilith_owner_memory/authority_verifier.py": "3c808267e56e9abc1ea1e848881cefd20a56fde51d9e803ac90f7f0c7517e83a",
    "services/owner-memory-control/lilith_owner_memory/recovery_contracts.py": "f4a14cff094d167a2a7925622031352955291c18244545e95c0003fb9231b95e",
    "services/owner-memory-control/lilith_owner_memory/rotation_contracts.py": "8f9df8dcd3e8a1b0cd8f03169bf7a51d4b6726cbb708cadfb3025586211996b0",
    "services/owner-memory-control/lilith_owner_memory/witness_readiness.py": "129d4479a7c86a6ef33acfb27da4f5cd6c6a6947b89184863a50117091fe3cbd",
    "services/owner-memory-control/lilith_owner_memory/successor_custody.py": "29e99a7b179d58dd4f8e9cd576ed544f207145f25f89c92e97ca0e6efa65cb72",
    "services/owner-memory-control/lilith_owner_memory/successor_readiness.py": "842176d06954607aed39d8988764fc253fa8bd4c41ca49fcd5e2a4532c5ecc16",
    "services/owner-memory-control/lilith_owner_memory/authority_ledger_journal.py": "f0d554c53948723c80f5cfbfd638d60855e92ddb562137370d12f9c7eeec49ce",
    "services/owner-memory-control/lilith_owner_memory/pr1_bootstrap.py": "9a09a4726bb473067e84e7664dca49d51b90ced1e012564526bae07656d3d5fd",
    "services/owner-memory-control/lilith_owner_memory/pr1_acceptance.py": "0d2e6ccabf916425a1dfa7dc587bfcb3d7a232eb6c52c5cd938d573199715cff",
}

RUNTIME_SOURCE_MAP = {
    **{f"{RUNTIME_PACKAGE}/{name}": f"lilith_authority_dev/{name}" for name in RUNTIME_MODULES},
    **{f"{HOST_PACKAGE}/{name}": f"lilith_authority_host/{name}" for name in HOST_MODULES},
    **{f"{ROOT_PACKAGE}/{name}": f"lilith_authority_root/{name}" for name in ROOT_MODULES},
    **{path: path.split("/", 2)[2] for path in SHARED_HASHES},
    **{f"{SERVICE}/deploy/{name}": f"assets/{name}" for name in DEPLOY_ASSETS},
    **WITNESS.RUNTIME_SOURCE_MAP,
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
    try:
        WITNESS.check_source_tree(root)
    except WITNESS.FileSetError as exc:
        raise FileSetError(str(exc)) from exc


def input_files() -> frozenset[str]:
    """Every repository file the release payload is built from (sources + shared)."""
    return SOURCE_FILES | frozenset(SHARED_HASHES) | WITNESS.SOURCE_FILES


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


AUTHORITY_RUNTIME_PREFIXES = ("lilith_authority_dev/", "lilith_memory/", "lilith_owner_memory/",
                              "assets/lilith-authority-dev.")
WITNESS_RUNTIME_PREFIXES = ("lilith_recovery_witness/", "assets/lilith-recovery-witness")
ROOT_TOOLING_PREFIXES = ("lilith_authority_root/", "cli/")


def files_digest(files: dict[str, str], prefixes: tuple[str, ...]) -> str:
    """SHA-256 of JCS `{path: sha256}` over members with `prefixes` (flat ASCII
    map: sorted keys, compact). Equal to `pr1_acceptance.runtime_files_digest`,
    which the root verifier recomputes from the installed manifest."""
    selected = {path: sha for path, sha in sorted(files.items()) if path.startswith(prefixes)}
    return _digest(json.dumps(selected, sort_keys=True, separators=(",", ":")).encode("ascii"))


def cli_payloads(root: Path) -> dict[str, bytes]:
    root = Path(root).resolve()
    check_source_tree(root)
    payloads = {member: _read(root, source) for member, source in CLI_SOURCES.items()}
    for member, data in payloads.items():
        if member != "cli/lilith-authority-keygen-dev" and any(m in data for m in FORBIDDEN_RUNTIME_MARKERS):
            raise FileSetError("FORBIDDEN_RUNTIME_MARKER")
    return payloads


def runtime_manifest(root: Path) -> dict:
    """The reviewed SOURCE release identity (never an installed-release claim)."""
    payloads = runtime_payloads(root)
    files = {name: _digest(data) for name, data in sorted(payloads.items())}
    members = {**files, **{name: _digest(data) for name, data in cli_payloads(root).items()}}
    return {
        "role": "lilith-authority-dev-synthetic-release-source-v2",
        "status": "SOURCE_PREPARED_NOT_INSTALLED",
        "files": files,
        "runtimeDigests": {
            "authority": files_digest(members, AUTHORITY_RUNTIME_PREFIXES),
            "witness": files_digest(members, WITNESS_RUNTIME_PREFIXES),
            "rootTooling": files_digest(members, ROOT_TOOLING_PREFIXES),
        },
        "witnessManifestSha256": WITNESS.runtime_manifest(root)["runtimeSha256"],
    }


if __name__ == "__main__":
    json.dump(runtime_manifest(Path(__file__).resolve().parents[2]), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
