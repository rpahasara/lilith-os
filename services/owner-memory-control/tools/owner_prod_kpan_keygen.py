#!/usr/bin/python3 -IB
"""OWNER_PROD K-PAN (Privacy anchor signing key) ceremony (P3). SOURCE ONLY; never installed.

    python3 -I -B owner_prod_kpan_keygen.py keygen

The production twin of `trackb_kpan_keygen.py`, which stays byte-identical. This tool loads its OWN instance of that
module and sets, on that instance only, the OWNER_PROD identity (`kpan.owner-prod.01`, Privacy environment
`OWNER_PROD`) and the PROD host identity (`lilith-01`, a machine ID hashing to `PROD_MACHINE_ID_SHA256`). The DEV tool's own preflight, generation,
systemd-creds encryption, exclusive write and K-WIT-unchanged proof then run unchanged. Before them it refuses unless
`PROD_MACHINE_ID_SHA256` is pinned (it is None in source until a reviewed commit pins the digest from a read-only PROD observation),
the machine is not the DEV machine, and the root-installed `deployment.json` names OWNER_PROD.
"""

from __future__ import annotations

import hashlib
import re
import importlib.util
import os
import socket
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEV_TOOL = HERE / "trackb_kpan_keygen.py"
ENVIRONMENT = "OWNER_PROD"
KEY_ID = "kpan.owner-prod.01"
HOSTNAME = "lilith-01"
PROD_MACHINE_ID_SHA256: str | None = None   # NOT PINNED: must equal owner_prod_keygen.PROD_MACHINE_ID_SHA256 (a test checks)
DEPLOYMENT_PATH = "/etc/lilith-authority-dev/deployment.json"
DEPLOYMENT = b'{"environment":"prod","profile":"OWNER_PROD","schemaVersion":1}'


def instance(machine_pin: str | None = None, machine_digest: str | None = None):
    spec = importlib.util.spec_from_file_location("trackb_kpan_keygen_prod_instance", DEV_TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module          # dataclasses resolve their module by name
    spec.loader.exec_module(module)
    dev_machine_id, dev_preflight = module.DEV_MACHINE_ID, module.preflight
    if machine_digest is not None:
        pin = machine_digest
    elif machine_pin is not None:                                         # TEST seam: hashed as the host file is
        pin = hashlib.sha256((machine_pin + "\n").encode("ascii")).hexdigest()
    else:
        pin = PROD_MACHINE_ID_SHA256

    def preflight(host, *, euid, isolated, hostname):
        if pin is None:
            raise module.Refused("PROD_MACHINE_ID_NOT_PINNED")
        try:
            raw = host.path("/etc/machine-id").read_bytes()
        except OSError as exc:
            raise module.Refused("NOT_PROD_HOST") from exc
        if not re.fullmatch(rb"[0-9a-f]{32}\n", raw) or hashlib.sha256(raw).hexdigest() != pin \
                or raw.decode("ascii").strip() == dev_machine_id:
            raise module.Refused("NOT_PROD_HOST")
        # the DEV tool's own host check then compares with exactly the ID this PROD host proved by its digest
        module.DEV_MACHINE_ID = raw.decode("ascii").strip()
        path = host.path(DEPLOYMENT_PATH)
        if not os.path.lexists(path):
            raise module.Refused("DEPLOYMENT_NOT_OWNER_PROD")
        module._root_owned(host, path, kind="file", mode=0o644, missing="DEPLOYMENT_INVALID", bad="DEPLOYMENT_INVALID")
        if path.read_bytes().rstrip(b"\n") != DEPLOYMENT:
            raise module.Refused("DEPLOYMENT_INVALID")
        return dev_preflight(host, euid=euid, isolated=isolated, hostname=hostname)

    module.ENVIRONMENT, module.KEY_ID = ENVIRONMENT, KEY_ID
    module.DEV_MACHINE_ID, module.DEV_HOSTNAME = None, HOSTNAME     # set per preflight from the digest-proven host
    module.preflight = preflight
    return module


def main(argv: list[str]) -> int:
    module = instance()
    if argv != ["keygen"]:
        print("REFUSED USAGE_ONLY_KEYGEN")
        return module.EXIT_REFUSED
    module._no_core_dumps()
    try:
        result = module.keygen(module.Host(), euid=os.geteuid(), isolated=bool(sys.flags.isolated),
                               hostname=socket.gethostname())
    except module.Refused as exc:
        print("REFUSED " + exc.reason)
        return module.EXIT_REFUSED
    except module.Failed as exc:
        print("FAILED " + exc.reason)
        return module.EXIT_FAILED
    sys.stdout.buffer.write(module.canonical(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
