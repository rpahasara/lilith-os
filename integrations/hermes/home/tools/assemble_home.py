#!/usr/bin/env python3
"""Assemble the Router V2 + plugin code tree of HERMES_HOME for one environment and verify every byte.

Offline only. Each file comes from the single repository path that owns it (see MODULES.json): lane modules that are
already tracked under docs/architecture/slice-* or services/core-api are not duplicated here.

    python integrations/hermes/home/tools/assemble_home.py --variant dev-f9c2 --out /tmp/hermes-home
    python integrations/hermes/home/tools/assemble_home.py --variant prod-lilith-01 --out /tmp/prod-home --allow-gaps

PROD has files that exist only on the PROD host. Without --allow-gaps the tool stops on them; with it, it assembles
everything else and reports each gap. A partial PROD tree is not a runnable PROD runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HOME = Path(__file__).resolve().parents[1]
REPO = HOME.parents[2]
GAP = "VM_ONLY_SOURCE_PENDING_SEPARATE_EXPORT"


def load(variant: str) -> dict[str, dict]:
    return json.loads((HOME / "MODULES.json").read_text(encoding="utf-8"))[variant]


def assemble(variant: str, out: Path | None) -> tuple[list[str], list[str]]:
    problems, gaps = [], []
    for rel, entry in sorted(load(variant).items()):
        if entry["source"] is None:
            gaps.append(f"{entry.get('status', GAP)} {rel} {entry['sha256']}")
            continue
        data = (REPO / entry["source"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            problems.append(f"MISMATCH {rel} <- {entry['source']}")
            continue
        if out is not None:
            target = out / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    return problems, gaps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--variant", choices=("prod-lilith-01", "dev-f9c2"), required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--allow-gaps", action="store_true")
    args = parser.parse_args()

    problems, gaps = assemble(args.variant, None)
    for line in problems + gaps:
        print(line)
    if problems or (gaps and not args.allow_gaps):
        print(f"HERMES_HOME_{args.variant.upper().replace('-', '_')}=FAIL")
        return 1
    if args.out is not None:
        assemble(args.variant, args.out)
    status = "PARTIAL" if gaps else "PASS"
    print(f"HERMES_HOME_{args.variant.upper().replace('-', '_')}={status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
