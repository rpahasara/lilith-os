"""Trusted, fail-closed classifier for the existing DEV deployment check.

Run this file from the exact CI-validated protected-main candidate, never a PR checkout.
The candidate has no mode input. The complete effective merge-base diff is
classified; any missing, malformed, or unfamiliar data fails closed.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

DEPLOY_REQUIRED = "DEPLOY_REQUIRED"
CONTROL_ONLY_NO_DEPLOY = "CONTROL_ONLY_NO_DEPLOY"
BROKER_CANDIDATE_VALIDATE_ONLY = "BROKER_CANDIDATE_VALIDATE_ONLY"

# Exact non-application control and separately installed snapshot-tool surface.
# This is a DEV application deployment decision, not a source-review exemption.
# No directory globs are accepted.
CONTROL_ONLY_PATHS = frozenset(
    {
        ".github/workflows/ci.yml",
        ".github/workflows/deploy-dev.yml",
        ".github/workflows/memory-broker-dev-stage2-runtime.yml",
        "scripts/classify_dev_deployment.py",
        "scripts/memory_broker_os_installer.py",
        "scripts/memory_broker_stage2_control.py",
        "scripts/memory_broker_stage3_transition.py",
        "scripts/memory_broker_stage3_liveness.py",
        "scripts/memory_broker_stage3_guard_worker.py",
        "scripts/memory_broker_stage3_adapters.py",
        "scripts/memory_broker_stage3_final.py",
        "scripts/test_classify_dev_deployment.py",
        "scripts/test_memory_broker_os_controls.py",
        "scripts/test_memory_broker_stage2_control.py",
        "scripts/test_memory_broker_stage3_transition.py",
        "scripts/test_memory_broker_stage3_liveness.py",
        "scripts/test_memory_broker_stage3_guard_linux.py",
        "scripts/test_memory_broker_stage3_adapters.py",
        "scripts/test_memory_broker_stage3_final.py",
        "scripts/test_pr_ci_dev_separation.py",
        "scripts/test_broker_only_dev_workflow.py",
        "scripts/verify_broker_dev_lifecycle.py",
        "scripts/test_broker_dev_lifecycle.py",
        "scripts/test_trusted_broker_snapshot_linux.py",
        "scripts/test_broker_candidate_dev_snapshot.py",
        "scripts/trusted_broker_snapshot_installer.py",
        "scripts/broker_candidate_dev_snapshot.py",
        "scripts/test_trusted_broker_snapshot.py",
        "docs/architecture/slice15b2b-trusted-snapshot-install-acceptance-contract.md",
        "docs/architecture/slice-15b2b-b1b2b-stage2-runtime-control.md",
        "docs/architecture/slice15b2b-stage3-a2-reversible-transition.md",
        "docs/architecture/slice15b2b-stage3-a2-control-adapters.md",
        "docs/architecture/slice15b2b-stage3-a2-final-controller.md",
    }
)

# The installer is admitted only at the exact reviewed Stage-II revision.
# Any later change to it takes full deployment.
PINNED_CANDIDATE_BLOBS = {
    "scripts/memory_broker_os_installer.py": "353ad6b75fcae5faa53929f5a591f7a75841bcbc",
}

# Exact broker-owned source/test surface. No shared Core API module, installer,
# release builder, deployment control, unit, or broad directory glob qualifies.
# A future A2 PR may use the one architecture record named here.
BROKER_CANDIDATE_PATHS = frozenset({
    "services/memory-broker/lilith_memory_broker/__init__.py",
    "services/memory-broker/lilith_memory_broker/request.py",
    "services/memory-broker/lilith_memory_broker/protocol.py",
    "services/memory-broker/lilith_memory_broker/state.py",
    "services/memory-broker/lilith_memory_broker/dev_config.py",
    "services/memory-broker/lilith_memory_broker/dev_state.py",
    "services/memory-broker/lilith_memory_broker/synthetic_evidence.py",
    "services/memory-broker/lilith_memory_broker/dev_core.py",
    "services/memory-broker/lilith_memory_broker/server.py",
    "services/memory-broker/tests/test_broker_foundation.py",
    "services/memory-broker/tests/test_dev_synthetic.py",
    "services/memory-broker/tests/test_server_adapter.py",
    "services/memory-broker/tests/test_deploy_assets.py",
    "services/memory-broker/tests/owner_request_golden.json",
    "docs/architecture/slice15b2b-stage3-a2-fault-seam.md",
})
SHA = re.compile(r"[0-9a-f]{40}\Z")
RAW_HEADER = re.compile(
    rb":(?P<old_mode>[0-7]{6}) (?P<new_mode>[0-7]{6}) "
    rb"(?P<old_oid>[0-9a-f]{40}) (?P<new_oid>[0-9a-f]{40}) "
    rb"(?P<status>[AMD])\Z"
)


def parse_raw_diff(data: bytes) -> list[tuple[str, str, str, str]]:
    """Return (path, status, old mode, new mode); reject noncanonical diffs."""
    if not data or not data.endswith(b"\0"):
        raise ValueError("empty or unterminated diff")
    fields = data[:-1].split(b"\0")
    if len(fields) % 2:
        raise ValueError("malformed raw diff")
    entries = []
    seen = set()
    for header, raw_path in zip(fields[::2], fields[1::2]):
        match = RAW_HEADER.fullmatch(header)
        if match is None or not raw_path:
            raise ValueError("unsupported diff entry")
        path = raw_path.decode("utf-8", errors="strict")
        if path in seen or path.startswith("/") or "\\" in path or "\0" in path:
            raise ValueError("duplicate or unsafe path")
        if any(part in ("", ".", "..") for part in path.split("/")):
            raise ValueError("noncanonical path")
        seen.add(path)
        entries.append(
            (
                path,
                match["status"].decode("ascii"),
                match["old_mode"].decode("ascii"),
                match["new_mode"].decode("ascii"),
            )
        )
    return entries


def classify_entries(
    entries: list[tuple[str, str, str, str]], candidate_blobs: dict[str, str],
) -> str:
    if not entries:
        return DEPLOY_REQUIRED
    mode = None
    for path, status, old_mode, new_mode in entries:
        if status not in ("A", "M", "D"):
            return DEPLOY_REQUIRED
        if old_mode not in ("000000", "100644", "100755"):
            return DEPLOY_REQUIRED
        if new_mode not in ("000000", "100644", "100755"):
            return DEPLOY_REQUIRED
        if new_mode == "000000" or status == "D":
            return DEPLOY_REQUIRED
        if path in CONTROL_ONLY_PATHS:
            if path in PINNED_CANDIDATE_BLOBS and candidate_blobs.get(path) != PINNED_CANDIDATE_BLOBS[path]:
                return DEPLOY_REQUIRED
            current = CONTROL_ONLY_NO_DEPLOY
        elif path in BROKER_CANDIDATE_PATHS:
            current = BROKER_CANDIDATE_VALIDATE_ONLY
        else:
            return DEPLOY_REQUIRED
        if mode is not None and current != mode:
            return DEPLOY_REQUIRED
        mode = current
    return mode or DEPLOY_REQUIRED


def git(root: Path, *args: str) -> bytes:
    output = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout
    return output if args[0] == "diff" else output.strip()


def classify_repository(candidate_root: Path, base_sha: str, candidate_sha: str) -> tuple[str, list[str]]:
    if not SHA.fullmatch(base_sha) or not SHA.fullmatch(candidate_sha):
        raise ValueError("expected full commit SHAs")
    if git(candidate_root, "rev-parse", "HEAD").decode() != candidate_sha:
        raise ValueError("candidate checkout SHA mismatch")
    if git(candidate_root, "rev-parse", f"{base_sha}^{{commit}}").decode() != base_sha:
        raise ValueError("base SHA not present")
    raw = git(
        candidate_root, "diff", "--raw", "--abbrev=40", "-z", "--no-renames", "--no-ext-diff",
        f"{base_sha}...{candidate_sha}",
    )
    entries = parse_raw_diff(raw)
    blobs = {}
    for path, _, _, _ in entries:
        if path in PINNED_CANDIDATE_BLOBS:
            blobs[path] = git(candidate_root, "rev-parse", f"{candidate_sha}:{path}").decode()
    mode = classify_entries(entries, blobs)
    return mode, [path for path, _, _, _ in entries]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        mode, paths = classify_repository(args.candidate_root, args.base_sha, args.candidate_sha)
    except (OSError, subprocess.CalledProcessError, UnicodeError, ValueError) as exc:
        print(f"Classification uncertainty: {exc}; forcing {DEPLOY_REQUIRED}", file=sys.stderr)
        mode, paths = DEPLOY_REQUIRED, []
    with args.github_output.open("a", encoding="utf-8") as output:
        output.write(f"mode={mode}\nbase_sha={args.base_sha}\ncandidate_sha={args.candidate_sha}\n")
    print(f"MODE={mode} BASE_SHA={args.base_sha} CANDIDATE_SHA={args.candidate_sha}")
    print("COMPLETE_EFFECTIVE_DIFF=" + repr(paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
