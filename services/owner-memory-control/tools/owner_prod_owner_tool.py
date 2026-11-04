#!/usr/bin/env python3
"""OWNER_PROD owner-workstation tool (P3): K-ROOT, registry v1, witness anchor and off-host reproduction for `prod`.

    python owner_prod_owner_tool.py root-keygen <key-out>
    python owner_prod_owner_tool.py registry-v1 <key> <kact-publication> <epochRandom> <policyVersion> <issuedAt>
    python owner_prod_owner_tool.py witness-anchor <kwit-publication>
    python owner_prod_owner_tool.py reproduce <registry> <registry-root> <witness-anchor> <updatedAt>

The production twin of `services/authority-dev/ceremony/lilith_authority_owner_dev.py`, which stays byte-identical.
This tool loads its OWN instance of that module and sets exactly two identity constants on that instance:
`ENVIRONMENT = "prod"` and `ROOT_KEY_ID = "prod.registry-root.owner-prod.1"`. Every builder, check and output is
otherwise the DEV tool's own code. It adds one check, which the DEV tool cannot need: the witness anchor's environment
must be `prod`. A DEV K-ACT publication is refused by the DEV tool's own scope check (PUBLICATION_SCOPE).

Run by the owner on the owner workstation only, from a clean checkout of the reviewed commit. It contacts nothing.
K-ROOT for PROD is a NEW key, never the DEV K-ROOT (owner decision D-1); where it is generated and held is an owner
decision recorded in the PROD ceremony checklist.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEV_TOOL = ROOT / "services/authority-dev/ceremony/lilith_authority_owner_dev.py"
ENVIRONMENT = "prod"
ROOT_KEY_ID = "prod.registry-root.owner-prod.1"
POLICY_VERSION = "policy.owner-prod.v1"


def _instance() -> Any:
    spec = importlib.util.spec_from_file_location("lilith_authority_owner_prod_instance", DEV_TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module          # dataclasses resolve their module by name
    spec.loader.exec_module(module)
    module.ENVIRONMENT, module.ROOT_KEY_ID = ENVIRONMENT, ROOT_KEY_ID
    return module


T = _instance()
OwnerToolError = T.OwnerToolError
root_keygen = T.root_keygen
registry_v1 = T.registry_v1
reproduce = T.reproduce
_root_key = T._root_key


def witness_anchor(publication: dict[str, Any]) -> dict[str, Any]:
    document = T.witness_anchor(publication)
    if document.get("environment") != ENVIRONMENT:
        raise OwnerToolError("PUBLICATION_SCOPE")          # a DEV K-WIT never anchors PROD
    return document


def main(argv: list[str], *, passphrase: Callable[[], bytes] | None = None) -> int:
    if argv[:1] == ["witness-anchor"] and len(argv) == 2:
        try:
            result = witness_anchor(T._load(argv[1]))
        except (OwnerToolError, ValueError, KeyError, TypeError, OSError) as exc:
            print(f"owner_prod_owner_tool: REFUSED {exc}", file=sys.stderr)
            return 2
        sys.stdout.write(T._jcs(result) + "\n")
        return 0
    if argv[:1] not in (["root-keygen"], ["registry-v1"], ["reproduce"]):
        print("owner_prod_owner_tool: REFUSED USAGE", file=sys.stderr)
        return 2
    return T.main(argv, passphrase=passphrase)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
