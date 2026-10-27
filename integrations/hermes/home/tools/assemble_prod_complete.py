#!/usr/bin/env python3
"""Assemble the complete deployed PROD (lilith-01) lilith_router tree and verify every byte. Offline only.

Sources: MODULES.json["prod-lilith-01"] (modules shared with or tracked elsewhere in the repository) plus
variants/prod-lilith-01/PROD-RECOVERY.json (Working Memory, Router V2 tests, and the router.yaml template recovered
from lilith-01 on 2026-10-27).

    python integrations/hermes/home/tools/assemble_prod_complete.py --out /tmp/prod-home \
        [--channel-id-file /secure/path/discord-channel-id]

router.yaml is written only when the private Discord channel id is supplied from a file; it is never printed.
Assembling the tree does not install, import or run anything.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HOME = Path(__file__).resolve().parents[1]
REPO = HOME.parents[2]
RECOVERY = HOME / "variants" / "prod-lilith-01" / "PROD-RECOVERY.json"


def sources() -> dict[str, dict]:
    modules = json.loads((HOME / "MODULES.json").read_text(encoding="utf-8"))["prod-lilith-01"]
    recovered = json.loads(RECOVERY.read_text(encoding="utf-8"))["files"]
    merged = {rel: entry for rel, entry in modules.items() if rel != "router.yaml"}  # PROD keeps it in lilith_router/
    merged.update(recovered)
    return merged


def assemble(out: Path | None, channel_id: bytes | None = None) -> tuple[list[str], list[str]]:
    problems, pending = [], []
    for rel, entry in sorted(sources().items()):
        if entry.get("template"):
            template = (REPO / entry["template"]).read_bytes()
            if hashlib.sha256(template).hexdigest() != entry["template_sha256"]:
                problems.append(f"TEMPLATE_MISMATCH {rel}")
                continue
            if channel_id is None:
                pending.append(f"PRIVATE_VALUE_REQUIRED {rel}")
                continue
            data = template.replace(b"__LILITH_DISCORD_CHANNEL_ID__", channel_id)
        elif entry.get("source"):
            data = (REPO / entry["source"]).read_bytes()
        else:
            problems.append(f"NO_SOURCE {rel}")
            continue
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            problems.append(f"MISMATCH {rel}")
            continue
        if out is not None:
            target = out / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    return problems, pending


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--channel-id-file", type=Path)
    args = parser.parse_args()
    channel = args.channel_id_file.read_bytes().strip() if args.channel_id_file else None
    problems, pending = assemble(None, channel)
    for line in problems + pending:
        print(line)
    if problems:
        print("PROD_HOME_COMPLETE=FAIL")
        return 1
    if args.out is not None:
        assemble(args.out, channel)
    print("PROD_HOME_COMPLETE=" + ("PASS" if not pending else "PASS_EXCEPT_PRIVATE_CONFIG"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
