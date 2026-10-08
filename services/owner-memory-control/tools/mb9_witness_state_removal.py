#!/usr/bin/env python3
"""15B2b-B1b-3e Package B (M-B9a): bounded PRE-COMMIT removal of the witness state, before any lineage (DEV).

Record: docs/architecture/slice-15b2b-b1b3e-mb9-witness-genesis-package.md §6.3 (owner decision OD-B5).

The accepted PR-1 mutation ledger (preflight §27, M-B9a row) allows "stop; remove the empty state dir". M-B9a
can leave the witness state in a few pre-lineage shapes (W9-1P, W9-1, W9-2S, W9-3). This tool is the one
reviewed way to return such a host to `W9_0_PRE_WITNESS`. It is not a reset, not a rollback of a lineage and not
a retry helper:

- it acts only on `/var/lib/lilith-recovery-witness` and the only things that may be inside it before a
  commit: an empty `witness.lock`, an EMPTY `chain/` and an EMPTY `authorizations/`;
- it refuses on ANY lineage-bearing residue: a `chain/` entry (e.g. `1.json`, even partial), `witness.json`,
  the pointer scratch `.witness.json.tmp`, any retained authorization, or any other entry;
- it refuses unless the witness and signer units are inactive (it never stops anything), the runtime
  credentials and sockets are absent, the ledger and both owner-input copies exist (post-M-B8) and the hold
  store is empty;
- it refuses on a symlink, a non-regular file, a hard-linked file, an unexpected owner, a non-empty lock, or
  any unreadable fact (ambiguity is a refusal);
- `remove` acts only on the exact state the owner reviewed: it takes the `planDigest` printed by the read-only
  `plan` form and refuses `PLAN_CHANGED` on any difference; it removes in the reverse of creation order and
  fsyncs `/var/lib`;
- it never touches the K-WIT blob, a credential, a unit, the ledger, the owner inputs, trust, the registry,
  P-A / P-B, the replicas or any other path.

A committed witness genesis is never removable: after the `chain/` fsync commit point the lineage is forward
only (RR-40). Running it needs a separate explicit owner authorization naming the plan digest and the W9 phase.
A consumed M-B9a or M-B9b go stays consumed; a new attempt needs a new owner go and a fresh re-proof.

    removal != reset;  plan digest != authorization;  pre-commit removal != lineage rollback

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
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

DEV_HOSTNAME = "lilith-dev-01"
DEV_MACHINE_ID = "ae929170e6fa4c8ab9cc7b9547238d9d"
WITNESS_USER = "lilith-recovery-witness"
SIGNER_GROUP = "lilith-authority-dev"
WITNESS_STATE = "/var/lib/lilith-recovery-witness"
LOCK = WITNESS_STATE + "/witness.lock"
CHAIN = WITNESS_STATE + "/chain"
AUTHORIZATIONS = WITNESS_STATE + "/authorizations"
REMOVABLE_ENTRIES = {"witness.lock": "file", "chain": "dir", "authorizations": "dir"}
LEDGER = "/var/lib/lilith-authority-dev/authority_ledger.db"
OWNER_COPIES = ("/etc/lilith-authority-dev/owner/genesis-pin.json",
                "/etc/lilith-authority-dev/owner/authorization-register.json")
HOLD_STORE = "/var/lib/lilith-authority-custody/holds"
MUST_BE_ABSENT = (
    "/run/credentials/lilith-recovery-witness.service",
    "/run/credentials/lilith-authority-dev.service",
    "/run/lilith-recovery-witness/owner.sock",
    "/run/lilith-recovery-witness/signer.sock",
    "/run/lilith-authority-dev/owner.sock",
)
UNITS = ("lilith-recovery-witness.service", "lilith-recovery-witness-owner.socket",
         "lilith-recovery-witness-signer.socket", "lilith-authority-dev.service", "lilith-authority-dev.socket")
SYSTEMCTL = "/usr/bin/systemctl"
FIXED_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "HOME": "/nonexistent"}
PLAN_TYPE = "LILITH_MB9_WITNESS_STATE_REMOVAL_PLAN"
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _unit_states(units: Sequence[str]) -> dict[str, str]:
    states = {}
    for unit in units:
        result = subprocess.run([SYSTEMCTL, "show", "--property=ActiveState", "--value", "--", unit],
                                env=FIXED_ENV, capture_output=True, text=True, timeout=30, check=False)
        states[unit] = result.stdout.strip() if result.returncode == 0 else "UNREADABLE"
    return states


def _ids() -> tuple[int, int]:
    import grp
    import pwd

    return pwd.getpwnam(WITNESS_USER).pw_uid, grp.getgrnam(SIGNER_GROUP).gr_gid


@dataclass
class Host:
    """The real host by default. `root`, `ids`, `units`, `euid` and `hostname` are TEST seams."""

    root: Path = field(default_factory=lambda: Path("/"))
    ids: Callable[[], tuple[int, int]] = _ids
    units: Callable[[Sequence[str]], dict[str, str]] = _unit_states
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


def _lstat(host: Host, absolute: str) -> os.stat_result | None:
    try:
        return os.lstat(host.path(absolute))
    except FileNotFoundError:
        return None


def _facts(meta: os.stat_result) -> dict[str, Any]:
    return {"uid": meta.st_uid, "gid": meta.st_gid, "mode": format(stat.S_IMODE(meta.st_mode), "04o"),
            "size": meta.st_size, "links": meta.st_nlink, "inode": meta.st_ino}


def plan(host: Host) -> dict[str, Any]:
    """Read-only: the exact removal plan and its digest. Refuses outside the bounded pre-commit case."""
    if _lstat(host, LEDGER) is None or any(_lstat(host, path) is None for path in OWNER_COPIES):
        raise Refused("NOT_POST_MB8")
    for path in MUST_BE_ABSENT:
        if _lstat(host, path) is not None:
            raise Refused("RUNTIME_PRESENT:" + path)
    try:
        if os.listdir(host.path(HOLD_STORE)):
            raise Refused("LATER_STATE_PRESENT:" + HOLD_STORE)
    except OSError as exc:
        raise Refused("HOLD_STORE_UNREADABLE") from exc
    states = host.units(UNITS)
    for unit in UNITS:
        if states.get(unit) != "inactive":
            raise Refused("UNIT_NOT_INACTIVE:" + unit)
    try:
        witness_uid, signer_gid = host.ids()
    except KeyError as exc:
        raise Refused("ACCOUNTS_INVALID") from exc
    state = _lstat(host, WITNESS_STATE)
    if state is None:
        body = {"planType": PLAN_TYPE, "schemaVersion": 1, "state": None, "entries": {}, "remove": []}
    else:
        if not stat.S_ISDIR(state.st_mode):
            raise Refused("STATE_NOT_A_REAL_DIRECTORY")
        if (state.st_uid, state.st_gid) not in ((0, 0), (witness_uid, signer_gid)) \
                or stat.S_IMODE(state.st_mode) not in (0o2750, 0o750, 0o700):
            raise Refused("STATE_UNEXPECTED")
        entries: dict[str, Any] = {}
        for name in sorted(os.listdir(host.path(WITNESS_STATE))):
            kind = REMOVABLE_ENTRIES.get(name)
            if kind is None:
                # witness.json, .witness.json.tmp or anything else: possible lineage or foreign content
                raise Refused("LINEAGE_OR_FOREIGN_ENTRY:" + name)
            absolute = f"{WITNESS_STATE}/{name}"
            meta = _lstat(host, absolute)
            if meta is None:
                raise Refused("STATE_CHANGED_DURING_PLAN")
            if kind == "file":
                if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1 or meta.st_size != 0 \
                        or (meta.st_uid, meta.st_gid) != (witness_uid, signer_gid):
                    raise Refused("LOCK_UNEXPECTED")
            else:
                if not stat.S_ISDIR(meta.st_mode) or (meta.st_uid, meta.st_gid) != (witness_uid, signer_gid):
                    raise Refused("DIRECTORY_UNEXPECTED:" + name)
                if os.listdir(host.path(absolute)):
                    raise Refused("LINEAGE_OR_FOREIGN_ENTRY:" + name + "/")
            entries[name] = dict(_facts(meta), kind=kind)
        # reverse of creation: the two BOOTSTRAP directories, the lock, then the state directory itself
        order = [path for path in (CHAIN, AUTHORIZATIONS, LOCK) if path.rsplit("/", 1)[1] in entries]
        body = {"planType": PLAN_TYPE, "schemaVersion": 1, "state": _facts(state), "entries": entries,
                "remove": order + [WITNESS_STATE]}
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
    for absolute in current["remove"]:
        if absolute == LOCK:
            os.unlink(host.path(absolute))          # never follows a symlink; the plan proved an empty regular file
            _fsync_directory(host, WITNESS_STATE)
        else:
            os.rmdir(host.path(absolute))           # refuses a non-empty directory by itself
            _fsync_directory(host, "/var/lib" if absolute == WITNESS_STATE else WITNESS_STATE)
        removed.append(absolute)
    after = plan(host)
    if after["remove"]:
        raise Refused("REMOVAL_INCOMPLETE")
    return {"removed": removed, "planDigest": plan_digest, "result": "PRE_MB9A_RESTORED", "authorityGranted": False,
            "note": "re-run `install_authority_dev.py status --expect P1B-8 <RELEASE_SHA>` and the W9 verifier "
                    "(expect W9_0_PRE_WITNESS) before anything else"}


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
        print(f"mb9_witness_state_removal: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
