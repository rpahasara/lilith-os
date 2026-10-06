#!/usr/bin/env python3
"""15B2b-B1b-3e M-B4/M-B5: bounded removal of the three public install files, BEFORE M-B6 only (DEV).

Record: docs/architecture/slice-15b2b-b1b3e-mb4-mb5-trust-install-remediation.md §6.

The accepted PR-1 mutation ledger (preflight §27) allows rollback of M-B4
("remove") and M-B5 ("remove (nothing binds it yet)") until the ledger
exists. The installer writes each file write-once (`O_EXCL`) and is not
atomic, so an interrupted M-B4/M-B5 (crash windows W1, W2, W4) can leave a
partial file that blocks every re-run. This tool is the one reviewed way to
remove those files. It is not a reset and not a rollback mechanism:

- it touches exactly three fixed paths and nothing else:
  `/etc/lilith-authority-dev/trust/registry-root.json`,
  `/etc/lilith-authority-dev/trust/witness-anchor.json`,
  `/etc/lilith-authority-dev/registry/authority-registry.v1.json`;
- it refuses unless the host is pre-ledger: `/var/lib/lilith-authority-dev`
  and `/var/lib/lilith-recovery-witness` absent and
  `/etc/lilith-authority-dev/owner` empty (M-B6 and later never happened);
- it refuses on any other entry in the trust or registry directory, on a
  symlink, a non-regular file, or a file not owned by root;
- `remove` acts only on the exact state the owner reviewed: it takes the
  `planDigest` printed by the read-only `plan` form and refuses if anything
  changed since;
- it removes files only (registry first, then the witness anchor, then the
  root anchor); never a directory, credential, unit, or any other path;
- it never decrypts, signs, starts, stops, reloads or enables anything.

Running it needs a separate explicit owner authorization. It does not
reopen anything M-B4 closed: the K-WIT burn/regenerate option stays closed,
a consumed M-B4/M-B5 go stays consumed, and a new attempt needs a new owner
authorization and a fresh re-proof.

    removal != reset;  plan digest != authorization

Stream it like the installer (stdlib only):

    echo <gzip+base64> | base64 -d | gunzip | sudo /usr/bin/python3 -I -B - plan
    echo <gzip+base64> | base64 -d | gunzip | sudo /usr/bin/python3 -I -B - remove <planDigest>
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

DEV_HOSTNAME = "lilith-dev-01"
DEV_MACHINE_ID = "ae929170e6fa4c8ab9cc7b9547238d9d"
TRUST_DIR = "/etc/lilith-authority-dev/trust"
REGISTRY_DIR = "/etc/lilith-authority-dev/registry"
OWNER_INPUT_DIR = "/etc/lilith-authority-dev/owner"
ROOT_ANCHOR = TRUST_DIR + "/registry-root.json"
WITNESS_ANCHOR = TRUST_DIR + "/witness-anchor.json"
REGISTRY = REGISTRY_DIR + "/authority-registry.v1.json"
REMOVAL_ORDER = (REGISTRY, WITNESS_ANCHOR, ROOT_ANCHOR)          # reverse of the install order
LATER_STATE = ("/var/lib/lilith-authority-dev", "/var/lib/lilith-recovery-witness")
MAX_FILE = 64 * 1024
PLAN_TYPE = "LILITH_MB4_MB5_REMOVE_BEFORE_MB6_PLAN"
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class Host:
    """The real host by default. `root`, `owner_*`, `euid` and `hostname` are TEST seams."""

    root: Path = field(default_factory=lambda: Path("/"))
    owner_uid: int = 0
    owner_gid: int = 0
    euid: Callable[[], int] = os.geteuid
    hostname: Callable[[], str] = field(default_factory=lambda: (lambda: os.uname().nodename))

    def path(self, absolute: str) -> Path:
        return self.root / absolute.lstrip("/")


def require_dev_root(host: Host) -> None:
    if host.euid() != 0:
        raise Refused("NOT_ROOT")
    try:
        machine_id = host.path("/etc/machine-id").read_text(encoding="ascii").strip()
    except OSError as exc:
        raise Refused("NOT_DEV_HOST") from exc
    if machine_id != DEV_MACHINE_ID or host.hostname().split(".", 1)[0] != DEV_HOSTNAME:
        raise Refused("NOT_DEV_HOST")


def _root_directory(host: Host, absolute: str) -> list[str]:
    try:
        meta = os.lstat(host.path(absolute))
    except FileNotFoundError as exc:
        raise Refused("DIRECTORY_MISSING:" + absolute) from exc
    if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != host.owner_uid or stat.S_IMODE(meta.st_mode) != 0o755:
        raise Refused("DIRECTORY_UNEXPECTED:" + absolute)
    return sorted(os.listdir(host.path(absolute)))


def _file(host: Host, absolute: str) -> dict[str, Any] | None:
    path = host.path(absolute)
    try:
        meta = os.lstat(path)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid != host.owner_uid or meta.st_size > MAX_FILE:
        raise Refused("FILE_UNEXPECTED:" + absolute)
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    try:
        data = os.read(fd, MAX_FILE + 1)
    finally:
        os.close(fd)
    if len(data) > MAX_FILE:
        raise Refused("FILE_UNEXPECTED:" + absolute)
    return {"sha256": hashlib.sha256(data).hexdigest(), "size": meta.st_size, "uid": meta.st_uid,
            "gid": meta.st_gid, "mode": format(stat.S_IMODE(meta.st_mode), "04o"), "inode": meta.st_ino}


def plan(host: Host) -> dict[str, Any]:
    """Read-only: the exact removal plan and its digest. Refuses outside the bounded case."""
    for path in LATER_STATE:
        if os.path.lexists(host.path(path)):
            raise Refused("NOT_PRE_LEDGER:" + path)
    if _root_directory(host, OWNER_INPUT_DIR):
        raise Refused("NOT_PRE_LEDGER:" + OWNER_INPUT_DIR)
    trust = _root_directory(host, TRUST_DIR)
    registry = _root_directory(host, REGISTRY_DIR)
    if not set(trust) <= {Path(ROOT_ANCHOR).name, Path(WITNESS_ANCHOR).name}:
        raise Refused("TRUST_DIRECTORY_UNEXPECTED")
    if not set(registry) <= {Path(REGISTRY).name}:
        raise Refused("REGISTRY_DIRECTORY_UNEXPECTED")
    files = {path: _file(host, path) for path in REMOVAL_ORDER}
    body = {"planType": PLAN_TYPE, "schemaVersion": 1, "files": files,
            "remove": [path for path in REMOVAL_ORDER if files[path] is not None]}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()
    return dict(body, planDigest=digest, authorityGranted=False,
                note="plan only; removal needs a separate explicit owner authorization")


def _fsync_directory(host: Host, absolute: str) -> None:
    fd = os.open(host.path(absolute), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def remove(host: Host, plan_digest: str) -> dict[str, Any]:
    if not _DIGEST.fullmatch(plan_digest or ""):
        raise Refused("PLAN_DIGEST_INVALID")
    current = plan(host)
    if current["planDigest"] != plan_digest:
        raise Refused("PLAN_CHANGED")
    if not current["remove"]:
        raise Refused("NOTHING_TO_REMOVE")
    removed = []
    for path in current["remove"]:
        os.unlink(host.path(path))          # unlink never follows a symlink; the plan proved a regular file
        _fsync_directory(host, str(Path(path).parent))
        removed.append(path)
    after = plan(host)
    if after["remove"]:
        raise Refused("REMOVAL_INCOMPLETE")
    return {"removed": removed, "planDigest": plan_digest, "after": after["files"], "result": "PRE_INSTALL_RESTORED",
            "authorityGranted": False,
            "note": "re-run `install_authority_dev.py status --expect P1B-2 <RELEASE_SHA>` before anything else"}


def main(argv: list[str], host: Host | None = None) -> int:
    host = host or Host()
    try:
        require_dev_root(host)
        if argv == ["plan"]:
            result = plan(host)
        elif len(argv) == 2 and argv[0] == "remove":
            result = remove(host, argv[1])
        else:
            raise Refused("USAGE")
    except Refused as exc:
        print(f"mb4_mb5_remove_before_mb6: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
