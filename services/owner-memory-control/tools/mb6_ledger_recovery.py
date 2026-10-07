#!/usr/bin/env python3
"""15B2b-B1b-3e M-B6: bounded PRE-M-B9b ledger recovery, plan-digest bound (DEV).

Record: docs/architecture/slice-15b2b-b1b3e-mb6-ledger-remediation.md §6.

Accepted governance allows removal of the M-B6 ledger before M-B9b
(preflight §29, F-5; sequencing C-7). This tool is the one reviewed way to
act on an interrupted M-B6. It is NOT a ledger reset and NOT a retry of
M-B6: it never runs `provision`, never writes a ledger byte, and leaves the
host either where a NEW owner go may start again or in the reviewed
success state.

| Classified host phase (`mb6_ledger_verifier`) | Action | Result |
| --- | --- | --- |
| `W6_1_STATE_DIRECTORY_INEXACT` (empty, root-owned) | `REMOVE_EMPTY_STATE_DIRECTORY`: `rmdir` the state directory, fsync `/var/lib` | `W6_0_NO_MB6_MUTATION` |
| `W6_3_LEDGER_INCOMPLETE` (nothing committed) | `REMOVE_UNCOMMITTED_LEDGER_FILES`: unlink the present `authority_ledger.db` / `-wal` / `-shm`, fsync the state directory | `W6_2_STATE_DIRECTORY_EXACT_EMPTY` |
| `LEDGER_COMMITTED_EXACT`, clean (no sidecar) | `ADOPT_COMMITTED_LEDGER`: fsync the ledger file and the state directory; no byte is written | `LEDGER_COMMITTED_EXACT` (unchanged) |
| `LEDGER_COMMITTED_EXACT` with a `-wal` / `-shm` sidecar | none: `OWNER_ADJUDICATION_REQUIRED` | — |
| `W6_0`, `W6_2` | none: `NOTHING_TO_RECOVER` | — |
| anything else | refused | — |

A valid committed deterministic ledger is never deleted. `plan` is
read-only and prints the plan and its `planDigest`; `recover` re-derives
the plan, refuses unless the digest is identical (`PLAN_CHANGED`), acts,
and re-classifies. Every form requires root on `lilith-dev-01` and refuses
whenever any M-B8-or-later state exists (witness state, owner pin or
register copy, a HELD record, a running signer or witness): the verifier
classifies such a host `OUT_OF_SCOPE_LATER_STATE`, so this tool can never
run after M-B9b. It touches only `/var/lib/lilith-authority-dev` and the
three ledger artifact names in it. It never changes trust, registry,
owner-freshness, witness, hold or credential state, never decrypts, signs,
starts, stops, reloads or enables anything, and reopens no burn or point of
no return.

Streamed by the M-B6 operator as one hash-gated bundle with the W5 and M-B6
verifiers. Running it needs a separate explicit owner authorization naming
the plan digest.

    recovery != reset != retry;  plan digest != authorization
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import mb6_ledger_verifier as V

PLAN_TYPE = "LILITH_MB6_LEDGER_RECOVERY_PLAN"
REMOVE_DIRECTORY = "REMOVE_EMPTY_STATE_DIRECTORY"
REMOVE_FILES = "REMOVE_UNCOMMITTED_LEDGER_FILES"
ADOPT = "ADOPT_COMMITTED_LEDGER"
NOTHING = "NOTHING_TO_RECOVER"
ADJUDICATE = "OWNER_ADJUDICATION_REQUIRED"
MUTATING = (REMOVE_DIRECTORY, REMOVE_FILES, ADOPT)
AFTER = {REMOVE_DIRECTORY: V.W6_0, REMOVE_FILES: V.W6_2, ADOPT: V.COMMITTED}
ORDER = (V.WAL_NAME, V.SHM_NAME, V.LEDGER_NAME)         # sidecars first, then the database


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class Host:
    """`root`, the ids, `euid`, `hostname` and the pins are TEST seams."""

    root: Path = Path("/")
    owner_uid: int = 0
    owner_gid: int = 0
    signer: tuple[int, int] | None = None
    euid: Callable[[], int] = field(default=lambda: os.geteuid())
    hostname: Callable[[], str] = field(default=lambda: os.uname().nodename)
    trust_pins: Any = None
    pins: V.LedgerPinsV1 = V.ACCEPTED_PINS

    def path(self, absolute: str) -> Path:
        return Path(self.root) / absolute.lstrip("/")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _require(host: Host) -> None:
    try:
        V.require_dev_root(euid=host.euid, root=Path(host.root), hostname=host.hostname)
    except V.Refused as exc:
        raise Refused(exc.reason) from exc


def _target_facts(host: Host, names: list[str]) -> list[dict[str, Any]]:
    out = []
    for name in names:
        path = host.path(V.STATE_DIR) / name
        meta = os.lstat(path)
        out.append({"name": name, "inode": meta.st_ino, "device": meta.st_dev, "size": meta.st_size,
                    "mtimeNs": meta.st_mtime_ns, "ctimeNs": meta.st_ctime_ns,
                    "sha256": hashlib.sha256(V._read(path)).hexdigest()})
    return out


def plan(host: Host, expected_head: str) -> dict[str, Any]:
    """Read-only. The plan for the exact classified host state, and its digest."""
    _require(host)
    try:
        report = V.evaluate(expected_head, root=host.root, owner_uid=host.owner_uid, owner_gid=host.owner_gid,
                            signer=host.signer, pins=host.pins, trust_pins=host.trust_pins)
    except V.Refused as exc:
        raise Refused(exc.reason) from exc
    phase = report["phase"]
    if phase in (V.LATER_STATE, V.UNCLASSIFIED):
        raise Refused("NOT_RECOVERABLE:" + phase)
    if not report["checks"]["laterStateAbsent"] or report["witnessGenesisPresent"] \
            or report["ownerRegisterCopyPresent"] or report["genesisPinCopyPresent"]:
        raise Refused("NOT_PRE_MB9B")                      # defence in depth; the verifier already refuses
    targets: list[str] = []
    if phase == V.W6_1:
        action = REMOVE_DIRECTORY
    elif phase == V.W6_3:
        action = REMOVE_FILES
        targets = [name for name in ORDER if name in (report["entries"] or [])]
    elif phase == V.COMMITTED:
        action = ADOPT if report["ledgerClean"] else ADJUDICATE
        targets = [V.LEDGER_NAME] if action == ADOPT else []
    else:
        action = NOTHING
    directory = os.lstat(host.path(V.STATE_DIR)) if phase != V.W6_0 else None
    body = {
        "planType": PLAN_TYPE, "schemaVersion": 1, "environment": V.ENVIRONMENT, "phase": phase, "action": action,
        "expectedLedgerHead": expected_head, "stateDirectory": None if directory is None else {
            "inode": directory.st_ino, "device": directory.st_dev, "uid": directory.st_uid, "gid": directory.st_gid,
            "mode": format(directory.st_mode & 0o7777, "04o")},
        "targets": _target_facts(host, targets), "expectedAfter": AFTER.get(action),
        "observationSha256": hashlib.sha256(_canonical(report)).hexdigest(),
    }
    return dict(body, planDigest=hashlib.sha256(_canonical(body)).hexdigest(), mutating=action in MUTATING,
                authorityGranted=False)


def _fsync(path: Path, directory: bool) -> None:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    if directory:
        flags |= getattr(os, "O_DIRECTORY", 0)
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def recover(host: Host, expected_head: str, plan_digest: str) -> dict[str, Any]:
    """Act on exactly the reviewed plan; then re-classify. Never re-plans, never retries."""
    current = plan(host, expected_head)
    if current["planDigest"] != plan_digest:
        raise Refused("PLAN_CHANGED")
    action = current["action"]
    if action not in MUTATING:
        raise Refused(action)
    state = host.path(V.STATE_DIR)
    if action == REMOVE_DIRECTORY:
        os.rmdir(state)                                    # refuses by itself unless empty
        _fsync(state.parent, True)
    elif action == REMOVE_FILES:
        for target in current["targets"]:
            os.unlink(state / target["name"])
        _fsync(state, True)
    else:
        _fsync(state / V.LEDGER_NAME, False)              # durability only: no byte changes
        _fsync(state, True)
    after = V.evaluate(expected_head, root=host.root, owner_uid=host.owner_uid, owner_gid=host.owner_gid,
                       signer=host.signer, pins=host.pins, trust_pins=host.trust_pins)
    ok = after["phase"] == current["expectedAfter"]
    return {"action": action, "planDigest": plan_digest, "phaseBefore": current["phase"], "phaseAfter": after["phase"],
            "result": "MB6_RECOVERY_" + ("DONE" if ok else "STOP_UNEXPECTED_AFTER_STATE"),
            "next": "a new M-B6 attempt needs a new owner go and a fresh re-proof" if action != ADOPT
            else "M-B6 POST, then owner acceptance", "authorityGranted": False}


def main(argv: list[str], host: Host | None = None) -> int:
    host = host or Host()
    try:
        if len(argv) == 2 and argv[0] == "plan":
            result = plan(host, argv[1])
        elif len(argv) == 3 and argv[0] == "recover" and len(argv[2]) == 64 \
                and all(c in "0123456789abcdef" for c in argv[2]):
            result = recover(host, argv[1], argv[2])
        else:
            raise Refused("USAGE")
    except Refused as exc:
        print(f"mb6_ledger_recovery: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    except V.Refused as exc:
        print(f"mb6_ledger_recovery: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return 0 if not result.get("result", "").endswith("UNEXPECTED_AFTER_STATE") else 1


if __name__ == "__main__":
    if V.RELEASE_TREE not in sys.path:
        sys.path.insert(0, V.RELEASE_TREE)
    sys.exit(main(sys.argv[1:]))
