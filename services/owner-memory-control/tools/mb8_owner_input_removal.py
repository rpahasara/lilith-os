#!/usr/bin/env python3
"""15B2b-B1b-3e Package A (M-B8): bounded removal of the two on-host owner-input copies, BEFORE M-B9a only (DEV).

Record: docs/architecture/slice-15b2b-b1b3e-mb7-mb8-genesis-prep-package.md §6.

The accepted PR-1 mutation ledger (preflight §27, M-B8 row) allows "remove
the copy (before M-B9b)". The installer writes the two copies write-once
(`O_EXCL`) and in order (the genesis-pin copy, then the register copy), so an
interrupted M-B8 can leave a partial state (W8-1, W8-2, W8-3) that blocks
every re-run: `install-owner-inputs` requires `status --expect P1B-6`, whose
owner-input listing must be empty. This tool is the one reviewed way to
remove those copies. It is not a reset and not a rollback mechanism:

- it touches exactly two fixed paths and nothing else:
  `/etc/lilith-authority-dev/owner/authorization-register.json` and
  `/etc/lilith-authority-dev/owner/genesis-pin.json`;
- it is narrower than the ledger row: it refuses unless the host is
  post-M-B6 and pre-M-B9a (the ledger exists; no witness state, no running
  signer or witness, no hold record);
- it refuses on any other entry in the owner-input directory, a symlink, a
  non-regular file, a hard-linked file, or a file not owned by root;
- `remove` acts only on the exact state the owner reviewed: it takes the
  `planDigest` printed by the read-only `plan` form and refuses if anything
  changed since;
- it removes files only (the register copy first, then the pin copy: the
  reverse of the install order); never the directory, a ledger, trust,
  registry, credential, unit, or any other path;
- it judges no content (the W8 verifier does) and never decrypts, signs,
  starts, stops, reloads or enables anything.

Running it needs a separate explicit owner authorization naming the plan
digest and the W8 phase. It never touches the owner's off-host pin copies
P-A and P-B, which are owner records: removing an on-host copy is not a new
pin and never re-opens the candidate. A consumed M-B8 go stays consumed; a
new attempt needs a new owner go and a fresh re-proof.

    removal != reset;  plan digest != authorization;  on-host copy != owner pin

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
OWNER_INPUT_DIR = "/etc/lilith-authority-dev/owner"
PIN_COPY = OWNER_INPUT_DIR + "/genesis-pin.json"
REGISTER_COPY = OWNER_INPUT_DIR + "/authorization-register.json"
REMOVAL_ORDER = (REGISTER_COPY, PIN_COPY)                      # reverse of the install order
LEDGER = "/var/lib/lilith-authority-dev/authority_ledger.db"
HOLD_STORE = "/var/lib/lilith-authority-custody/holds"
LATER_STATE = (
    "/var/lib/lilith-recovery-witness",
    "/run/credentials/lilith-recovery-witness.service",
    "/run/credentials/lilith-authority-dev.service",
    "/run/lilith-authority-dev/owner.sock",
    "/run/lilith-recovery-witness/owner.sock",
    "/run/lilith-recovery-witness/signer.sock",
)
MAX_FILE = 64 * 1024
PLAN_TYPE = "LILITH_MB8_OWNER_INPUT_REMOVAL_PLAN"
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
    euid: Callable[[], int] = os.geteuid if hasattr(os, "geteuid") else (lambda: 0)
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


def _file(host: Host, absolute: str) -> dict[str, Any] | None:
    path = host.path(absolute)
    try:
        meta = os.lstat(path)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid != host.owner_uid or meta.st_size > MAX_FILE \
            or meta.st_nlink != 1:
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
    if not os.path.lexists(host.path(LEDGER)):
        raise Refused("NOT_POST_LEDGER")
    for path in LATER_STATE:
        if os.path.lexists(host.path(path)):
            raise Refused("LATER_STATE_PRESENT:" + path)
    try:
        holds = os.listdir(host.path(HOLD_STORE))
    except OSError as exc:
        raise Refused("HOLD_STORE_UNREADABLE") from exc
    if holds:
        raise Refused("LATER_STATE_PRESENT:" + HOLD_STORE)
    try:
        meta = os.lstat(host.path(OWNER_INPUT_DIR))
    except FileNotFoundError as exc:
        raise Refused("DIRECTORY_MISSING:" + OWNER_INPUT_DIR) from exc
    if not stat.S_ISDIR(meta.st_mode) or (meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode)) \
            != (host.owner_uid, host.owner_gid, 0o755):
        raise Refused("DIRECTORY_UNEXPECTED:" + OWNER_INPUT_DIR)
    if not set(os.listdir(host.path(OWNER_INPUT_DIR))) <= {Path(p).name for p in REMOVAL_ORDER}:
        raise Refused("OWNER_INPUT_DIRECTORY_UNEXPECTED")
    files = {path: _file(host, path) for path in REMOVAL_ORDER}
    body = {"planType": PLAN_TYPE, "schemaVersion": 1, "files": files,
            "remove": [path for path in REMOVAL_ORDER if files[path] is not None]}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()
    return dict(body, planDigest=digest, authorityGranted=False,
                note="plan only; removal needs a separate explicit owner authorization naming this digest")


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
        _fsync_directory(host, OWNER_INPUT_DIR)
        removed.append(path)
    after = plan(host)
    if after["remove"]:
        raise Refused("REMOVAL_INCOMPLETE")
    return {"removed": removed, "planDigest": plan_digest, "after": after["files"], "result": "PRE_MB8_RESTORED",
            "authorityGranted": False,
            "note": "re-run `install_authority_dev.py status --expect P1B-6 <RELEASE_SHA>` and the W8 verifier "
                    "(expect W8_0_NO_OWNER_INPUTS) before anything else"}


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
        print(f"mb8_owner_input_removal: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
