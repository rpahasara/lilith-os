#!/usr/bin/env python3
"""LILITH 15B2b-B1b-3e M-B10: MB10_SCRATCH_RECOVERY, the bounded removal of ONE exactly recognized writer scratch.

Record: docs/architecture/slice-15b2b-b1b3e-mb10-held-package.md §6.2 (OD-M10-6, owner-accepted 2026-10-10).

A SEPARATE file with its own SHA-256 pin. The M-B10 operator never deletes or repairs residue: a scratch is STOP,
not success and not retryable. This tool is the only reviewed recovery, and only under its own explicit owner
recovery authorization (operator form `scratch-recover`).

`hold_store._publish` creates `/var/lib/lilith-authority-custody/.<name>.tmp` (`O_CREAT|O_EXCL|O_NOFOLLOW`, 0600),
writes the record bytes, `fchmod 0600`, fsync, then renames it into `holds/`. A crash before the rename leaves that
scratch and an empty store; every later writer refuses `HOLD_PARENT_UNEXPECTED_ENTRY`. This tool recognizes exactly
that and nothing else:

- the canonical HELD is absent and the hold store is EMPTY (no other hold-store content at all);
- the parent holds exactly `holds` and the ONE scratch name derived from the fixed INITIAL_CUSTODY ceremony;
- the scratch is a regular `root:root 0600` file with one link, at most the record length, and its bytes are a
  prefix of the exact expected HELD bytes (the writer's only content; a partial write is a prefix).

Run only by the owner, as root, on `lilith-dev-01`, streamed from the merged control commit:

    sudo /usr/bin/python3 -I -B - plan                  < mb10_scratch_recovery.py   (read-only)
    sudo /usr/bin/python3 -I -B - recover <plan-digest> < mb10_scratch_recovery.py   (removes that one file)

`recover` re-derives the plan; it removes only when the digest equals the authorized one, then fsyncs the parent
and re-observes: `MB10_SCRATCH_RECOVERED` only when the parent holds exactly `holds` and the store is empty. It
never touches the store, a record, the witness, the ledger or any unit, and it never writes HELD.

    scratch recovery != M-B10 retry;  a removed scratch never authorizes a write;  a linked successor needs its own go
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any, Callable

HOLD_PARENT = "/var/lib/lilith-authority-custody"
HOLD_STORE_NAME = "holds"
GENESIS = "ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4"
INITIAL_KEY_ID = "test-only.dev-synthetic.actor.b1b3d.1"
EXPECTED_HELD_NAME = "1ee1b7d5797b9c39b941befbbe4a5917b7fe510fa48a0f487f801246f80071d6.json"
EXPECTED_HELD_SHA256 = "c713ea1d2e0b016e59eb55ddc1a125561495ed4cc0a2c24764f36c8355d0216d"
SCRATCH_NAME = "." + EXPECTED_HELD_NAME + ".tmp"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def expected_bytes() -> bytes:
    """The exact INITIAL_CUSTODY HELD bytes (sorted compact JSON = RFC 8785 for these values), pin-checked."""
    ceremony = f"dev.initial-custody.{INITIAL_KEY_ID}"
    record = {"protocol": "LILITH_CEREMONY_HOLD", "schemaVersion": 1, "environment": "dev", "ceremonyId": ceremony,
              "transitionKind": "INITIAL_CUSTODY", "state": "HELD", "reason": "INITIAL_CUSTODY_BOOTSTRAP",
              "expectedPredecessorKeyId": None, "expectedSuccessorKeyId": INITIAL_KEY_ID,
              "observedWitnessDigest": GENESIS}
    data = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("ascii")
    if hashlib.sha256(data).hexdigest() != EXPECTED_HELD_SHA256 or \
            hashlib.sha256(ceremony.encode()).hexdigest() + ".json" != EXPECTED_HELD_NAME:
        raise Refused("EXPECTED_HELD_PIN_MISMATCH")
    return data


def plan(*, root: Path = Path("/"), owner: tuple[int, int] = (0, 0)) -> dict[str, Any]:
    """Read-only: the recovery plan and its digest, or a refusal naming the first unmet condition."""
    expected = expected_bytes()
    parent = Path(root) / HOLD_PARENT.lstrip("/")
    meta = os.lstat(parent)
    if not stat.S_ISDIR(meta.st_mode) or (meta.st_uid, meta.st_gid) != owner or stat.S_IMODE(meta.st_mode) != 0o700:
        raise Refused("HOLD_PARENT_UNSAFE")
    if sorted(os.listdir(parent)) != sorted([HOLD_STORE_NAME, SCRATCH_NAME]):
        raise Refused("PARENT_NOT_EXACTLY_HOLDS_AND_THE_SCRATCH")
    store = parent / HOLD_STORE_NAME
    smeta = os.lstat(store)
    if not stat.S_ISDIR(smeta.st_mode) or (smeta.st_uid, smeta.st_gid) != owner or stat.S_IMODE(smeta.st_mode) != 0o700:
        raise Refused("HOLD_STORE_UNSAFE")
    if os.listdir(store):
        raise Refused("HOLD_STORE_NOT_EMPTY")                    # the canonical HELD or anything else: never here
    scratch = parent / SCRATCH_NAME
    fmeta = os.lstat(scratch)
    if not stat.S_ISREG(fmeta.st_mode) or (fmeta.st_uid, fmeta.st_gid) != owner \
            or stat.S_IMODE(fmeta.st_mode) != 0o600 or fmeta.st_nlink != 1 or fmeta.st_size > len(expected):
        raise Refused("SCRATCH_METADATA_NOT_THE_WRITER_FORM")
    fd = os.open(scratch, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    try:
        if os.fstat(fd).st_ino != fmeta.st_ino:
            raise Refused("SCRATCH_CHANGED_DURING_OBSERVATION")
        data = os.read(fd, len(expected) + 1)
    finally:
        os.close(fd)
    if len(data) != fmeta.st_size or data != expected[:len(data)]:
        raise Refused("SCRATCH_BYTES_NOT_A_PREFIX_OF_THE_EXPECTED_HELD")
    body = {"planType": "LILITH_MB10_SCRATCH_RECOVERY_PLAN", "schemaVersion": 1, "scratch": SCRATCH_NAME,
            "inode": fmeta.st_ino, "size": fmeta.st_size, "sha256": hashlib.sha256(data).hexdigest(),
            "complete": data == expected, "holdStore": "EMPTY", "canonicalHeld": "ABSENT"}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()
    return dict(body, planDigest=digest)


def recover(plan_digest: str, *, root: Path = Path("/"), owner: tuple[int, int] = (0, 0),
            unlink: Callable[[str, int], None] | None = None) -> dict[str, Any]:
    if not isinstance(plan_digest, str) or _HEX64.fullmatch(plan_digest) is None:
        raise Refused("PLAN_DIGEST_INVALID")
    current = plan(root=root, owner=owner)
    if current["planDigest"] != plan_digest:
        raise Refused("PLAN_CHANGED")
    parent = Path(root) / HOLD_PARENT.lstrip("/")
    fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
    try:
        (unlink or (lambda name, dir_fd: os.unlink(name, dir_fd=dir_fd)))(SCRATCH_NAME, fd)
        os.fsync(fd)
    finally:
        os.close(fd)
    restored = sorted(os.listdir(parent)) == [HOLD_STORE_NAME] and os.listdir(parent / HOLD_STORE_NAME) == []
    return {"result": "MB10_SCRATCH_RECOVERED" if restored else "MB10_SCRATCH_RECOVERY_STOP",
            "planDigest": plan_digest, "removed": SCRATCH_NAME, "heldWritten": False, "authorityGranted": False}


def main(argv: list[str]) -> int:
    try:
        if os.geteuid() != 0:
            raise Refused("NOT_ROOT")
        if argv == ["plan"]:
            out = plan()
        elif len(argv) == 2 and argv[0] == "recover":
            out = recover(argv[1])
        else:
            raise Refused("USAGE")
    except Refused as exc:
        print(f"mb10_scratch_recovery: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"mb10_scratch_recovery: REFUSED OS_ERROR:{type(exc).__name__}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(out, sort_keys=True, indent=2) + "\n")
    return 0 if out.get("result", "MB10_SCRATCH_RECOVERED") == "MB10_SCRATCH_RECOVERED" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
