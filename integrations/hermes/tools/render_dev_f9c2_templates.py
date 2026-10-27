#!/usr/bin/env python3
"""Render the four token-bearing DEV f9c2 release files from their Git templates.

The deployed f9c2 release embeds a localhost-only provider-gate client token in four files. Git holds them with the
placeholder __LILITH_GATE_CLIENT_TOKEN__; the value lives only in owner custody (the DEV host and the encrypted
recovery archive). This tool injects it from a file and proves byte-equality with the release manifest.

    python integrations/hermes/tools/render_dev_f9c2_templates.py --token-file /secure/gate-client-token --out DIR

The token is read from the file (one line), never from the command line, and is never printed.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

RELEASE = Path(__file__).resolve().parents[1] / "release" / "dev-f9c2"
PLACEHOLDER = b"__LILITH_GATE_CLIENT_TOKEN__"
TEMPLATES = {
    "home/config.yaml": "templates/home/config.yaml.tmpl",
    "profiles/operate/config.yaml": "templates/profiles/operate/config.yaml.tmpl",
    "gate/gate.json": "templates/gate/gate.json.tmpl",
    "bin/verify_release.py": "templates/bin/verify_release.py.tmpl",
}


def manifest() -> dict[str, str]:
    entries = {}
    for line in (RELEASE / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        digest, path = line.split("  ", 1)
        entries[path.removeprefix("./")] = digest
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    token = args.token_file.read_bytes().strip()
    if not token or PLACEHOLDER in token or b"\n" in token:
        print("TOKEN_FILE_INVALID", file=sys.stderr)
        return 2

    expected = manifest()
    failed = 0
    for release_path, template in TEMPLATES.items():
        rendered = (RELEASE / template).read_bytes().replace(PLACEHOLDER, token)
        target = args.out / release_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(rendered)
        ok = hashlib.sha256(rendered).hexdigest() == expected[release_path]
        failed += not ok
        print(f"{'OK' if ok else 'MISMATCH'} {release_path}")
    print(f"DEV_F9C2_TEMPLATES={'PASS' if not failed else 'FAIL'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
