#!/usr/bin/env python3
"""Check that every DEV f9c2 release file held in Git equals the deployed release manifest.

Offline and dependency-free. Templates are checked for their placeholder instead (see render_dev_f9c2_templates.py);
files kept elsewhere in the repository are checked at their canonical path.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

HERMES = Path(__file__).resolve().parents[1]
REPO = HERMES.parents[1]
RELEASE = HERMES / "release" / "dev-f9c2"

# Release members that are tracked once, elsewhere in the repository.
CANONICAL_ELSEWHERE = {
    "dr5/deployer_authority_boundary_proof.sh": REPO / "scripts" / "deployer_authority_boundary_proof.sh",
}
TEMPLATED = {
    "home/config.yaml", "profiles/operate/config.yaml", "gate/gate.json", "bin/verify_release.py",
}
# Not LILITH source: upstream Hermes (rebuilt from the pin + patches), the bundled interpreter, wheels and build
# backend (rebuilt from requirements.locked.txt), and the Router V2 HERMES_HOME tree (integrations/hermes/home).
EXTERNAL_PREFIXES = ("src/", "python/", "wheelhouse/", "uv/", "buildbackend/", "home/")
NOT_A_MEMBER = {"MANIFEST.sha256"}


def manifest() -> dict[str, str]:
    entries = {}
    for line in (RELEASE / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        digest, path = line.split("  ", 1)
        entries[path.removeprefix("./")] = digest
    return entries


def verify() -> list[str]:
    problems = []
    expected = manifest()
    for path, digest in sorted(expected.items()):
        if path.startswith(EXTERNAL_PREFIXES) and path != "home/config.yaml":
            continue
        if path in TEMPLATED:
            continue
        local = CANONICAL_ELSEWHERE.get(path, RELEASE / path)
        if not local.is_file():
            problems.append(f"MISSING {path}")
        elif hashlib.sha256(local.read_bytes()).hexdigest() != digest:
            problems.append(f"MISMATCH {path}")
    for template in TEMPLATED:
        text = (RELEASE / "templates" / (template + ".tmpl")).read_bytes()
        if b"__LILITH_GATE_CLIENT_TOKEN__" not in text:
            problems.append(f"TEMPLATE_WITHOUT_PLACEHOLDER {template}")
    for local in sorted(RELEASE.rglob("*")):
        rel = local.relative_to(RELEASE).as_posix()
        if local.is_file() and not rel.startswith(("templates/", "README")) and rel not in NOT_A_MEMBER \
                and "__pycache__" not in local.parts and rel not in expected:
            problems.append(f"NOT_IN_RELEASE {rel}")
    return problems


def main() -> int:
    problems = verify()
    for problem in problems:
        print(problem)
    print(f"DEV_F9C2_SOURCE={'PASS' if not problems else 'FAIL'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
