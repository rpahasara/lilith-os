#!/usr/bin/env python3
"""Assemble the candidate DEV HERMES_HOME code tree with unified cognition and verify every byte. Offline only.

The tree is the f9c2 DEV tree from MODULES.json["dev-f9c2"] with the changes listed in OVERLAY.json:
``lilith_router/world_context.py`` becomes the governed adapter, and ``lilith_router/_prod_world_context.py`` is the
recovered PROD Working Memory, byte-exact. The DEV router.yaml (shadow, every lane off), the hardened gateway and
the hardened lilith_os adapter are unchanged.

    python integrations/hermes/overlays/dev-unified-cognition/tools/assemble_dev_cognition.py --out /tmp/hermes-home

Assembling the tree does not install, import or run anything, and nothing here deploys it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

OVERLAY = Path(__file__).resolve().parents[1]
REPO = OVERLAY.parents[3]
sys.path.insert(0, str(REPO / "integrations" / "hermes" / "home" / "tools"))

import assemble_home  # noqa: E402


def load() -> dict:
    return json.loads((OVERLAY / "OVERLAY.json").read_text(encoding="utf-8"))


def files() -> dict[str, dict]:
    manifest = load()
    base = assemble_home.load(manifest["base_variant"])
    merged = {rel: {"sha256": e["sha256"], "source": e["source"]} for rel, e in base.items()}
    for rel, entry in manifest["files"].items():
        replaces = entry.get("replaces")
        if replaces is not None and merged.get(rel, {}).get("sha256") != replaces:
            raise ValueError(f"BASE_MISMATCH {rel}")
        if replaces is None and rel in merged:
            raise ValueError(f"UNEXPECTED_BASE_FILE {rel}")
        merged[rel] = {"sha256": entry["sha256"], "source": entry["source"]}
    return merged


def assemble(out: Path | None) -> list[str]:
    problems = []
    for rel, entry in sorted(files().items()):
        data = (REPO / entry["source"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            problems.append(f"MISMATCH {rel} <- {entry['source']}")
            continue
        if out is not None:
            target = out / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        problems = assemble(None)
    except ValueError as exc:
        problems = [str(exc)]
    for line in problems:
        print(line)
    if problems:
        print("DEV_UNIFIED_COGNITION_TREE=FAIL")
        return 1
    if args.out is not None:
        assemble(args.out)
    print("DEV_UNIFIED_COGNITION_TREE=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
