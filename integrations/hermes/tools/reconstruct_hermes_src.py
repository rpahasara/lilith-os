#!/usr/bin/env python3
"""Rebuild LILITH's patched Hermes files from the pinned upstream commit and a reviewed patch set.

Offline only: reads a local clone of NousResearch/hermes-agent, never fetches, never installs, never runs Hermes.

    python integrations/hermes/tools/reconstruct_hermes_src.py \
        --upstream /path/to/hermes-agent --variant dev-f9c2 --out /tmp/hermes-dev-src [--full]

Without --full only the patched files are written (enough to verify provenance). With --full the whole upstream tree
at the pin is exported first, so --out is a complete source tree for the variant.
Exit 0 only when every patched file matches the recorded SHA-256 for the variant.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_COMMIT = "f293e7206b4ddd66042329442c6afebc19a8808d"
VARIANTS = ("prod-lilith-01", "dev-f9c2")


def git(upstream: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-c", "safe.directory=*", "-C", str(upstream), *args],
        check=True, capture_output=True,
    ).stdout


def expected_hashes(variant: str) -> dict[str, str]:
    lines = (ROOT / "patches" / f"{variant}.sha256").read_text(encoding="utf-8").splitlines()
    return {path: digest for digest, path in (line.split("  ", 1) for line in lines if line.strip())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--variant", choices=VARIANTS, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()

    head = git(args.upstream, "rev-parse", "HEAD").decode().strip()
    if head != UPSTREAM_COMMIT:
        print(f"UPSTREAM_PIN_MISMATCH head={head} expected={UPSTREAM_COMMIT}", file=sys.stderr)
        return 2
    if args.out.exists() and any(args.out.iterdir()):
        print(f"OUT_NOT_EMPTY {args.out}", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)

    expected = expected_hashes(args.variant)
    if args.full:
        archive = git(args.upstream, "archive", "--format=tar", UPSTREAM_COMMIT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(args.out, filter="data")
    else:
        for path in expected:
            target = args.out / path
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                target.write_bytes(git(args.upstream, "show", f"{UPSTREAM_COMMIT}:{path}"))
            except subprocess.CalledProcessError:
                pass  # a file the patch creates

    patch = ROOT / "patches" / f"{args.variant}.patch"
    subprocess.run(["git", "apply", "--whitespace=nowarn", str(patch)], cwd=args.out, check=True)

    failed = 0
    for path, digest in sorted(expected.items()):
        actual = hashlib.sha256((args.out / path).read_bytes()).hexdigest()
        status = "OK" if actual == digest else "MISMATCH"
        failed += status != "OK"
        print(f"{status} {digest[:12]} {path}")
    print(f"HERMES_SRC_{args.variant.upper().replace('-', '_')}={'PASS' if not failed else 'FAIL'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
