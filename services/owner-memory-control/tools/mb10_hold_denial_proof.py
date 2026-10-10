#!/usr/bin/env python3
"""LILITH 15B2b-B1b-3e M-B10 (WRITE_HELD): the separate hold-store denial proof, phase P1B-10.

Record: docs/architecture/slice-15b2b-b1b3e-mb10-held-package.md §7.

A SEPARATE file with its own SHA-256 pin. The P1B-5 proof (`scripts/authority_custody_denial_proof.py`) and the
P1B-9b witness proof (`mb9_witness_denial_proof.py`) stay byte-for-byte unchanged and still apply after M-B10:
neither requires an empty hold store. This proof adds the HELD record itself.

Run only by the owner, as root, on `lilith-dev-01`, streamed from the merged control commit:

    sudo /usr/bin/python3 -I -B - P1B-10 < mb10_hold_denial_proof.py     (after an exact M-B10)

There is no path, principal or command argument.

Preconditions (exact, or no probe runs): the hold parent (root:root 0700) holds exactly `holds`; the hold store
(root:root 0700) holds exactly the ONE expected HELD record name, a regular root:root 0600 file with one link; the
witness service and both witness sockets are active; the signer service and socket are inactive; activation
reports `GRANT_ABSENT`. Every row is a denial: no principal other than root may read, write or traverse the hold
store or its record. There is no ALLOWED_BY_DESIGN row.

The output is deterministic (no time, pid, inode or size). The last line is
`MB10_HOLD_DENIAL_PROOF=PASS phase=P1B-10 denied=<n> allowed=0`; exit 0 only on PASS.

    denial proof != authority;  HELD = restrictive custody state only;  HELD != issuance;  signer not started
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from typing import Callable, Sequence

DEPLOYER = "sa_112096412008414111981"
APPLICATION = "lilith"
BROKER = "lilith-memory-broker"
SIGNER = "lilith-authority-dev"
WITNESS = "lilith-recovery-witness"
OUTSIDERS = (APPLICATION, DEPLOYER, BROKER)
EVERYONE = OUTSIDERS + (SIGNER, WITNESS)
FIXED_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "HOME": "/nonexistent"}
TEST = "/usr/bin/test"
RUNUSER = "/usr/sbin/runuser"
SYSTEMCTL = "/usr/bin/systemctl"
ACTIVATION_VERIFY = "/usr/local/sbin/lilith-activation-verify"
GRANT_ABSENT = "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT"

PHASES = ("P1B-10",)
HOLD_PARENT = "/var/lib/lilith-authority-custody"
HOLD_STORE = HOLD_PARENT + "/holds"
# The one INITIAL_CUSTODY record name: sha256("dev.initial-custody.test-only.dev-synthetic.actor.b1b3d.1") + ".json"
HELD_NAME = "1ee1b7d5797b9c39b941befbbe4a5917b7fe510fa48a0f487f801246f80071d6.json"
HELD = HOLD_STORE + "/" + HELD_NAME
WITNESS_UNITS = ("lilith-recovery-witness.service", "lilith-recovery-witness-owner.socket",
                 "lilith-recovery-witness-signer.socket")
SIGNER_UNITS = ("lilith-authority-dev.service", "lilith-authority-dev.socket")

# (op, path, DENIED principals): root only, for everyone else, everywhere
ROWS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("-r", HOLD_PARENT, EVERYONE),
    ("-w", HOLD_PARENT, EVERYONE),
    ("-x", HOLD_PARENT, EVERYONE),
    ("-r", HOLD_STORE, EVERYONE),
    ("-w", HOLD_STORE, EVERYONE),
    ("-x", HOLD_STORE, EVERYONE),
    ("-r", HELD, EVERYONE),
    ("-w", HELD, EVERYONE),
)
EXPECTED_DENIED = sum(len(principals) for _, _, principals in ROWS)
SCOPE_LINE = ("SCOPE: denial only; HELD is restrictive custody state only; HELD != issuance authority != signer "
              "started != Registry V1 effective != authority active")

Runner = Callable[[Sequence[str]], int]
Lstat = Callable[[str], "os.stat_result | None"]


def _run(argv: Sequence[str]) -> int:
    return subprocess.run(list(argv), env=FIXED_ENV, capture_output=True, timeout=30, check=False).returncode


def _lstat(path: str) -> "os.stat_result | None":
    try:
        return os.lstat(path)
    except FileNotFoundError:
        return None


def _listdir(path: str) -> list[str]:
    return sorted(os.listdir(path))


def _accounts() -> bool:
    import pwd

    try:
        return all(pwd.getpwnam(name).pw_uid != 0 for name in (SIGNER, WITNESS, BROKER, APPLICATION, DEPLOYER))
    except KeyError:
        return False


def _unit_state(unit: str) -> str:
    result = subprocess.run([SYSTEMCTL, "show", "--property=ActiveState", "--value", "--", unit],
                            env=FIXED_ENV, capture_output=True, text=True, timeout=30, check=False)
    return result.stdout.strip() if result.returncode == 0 else "UNREADABLE"


def _activation() -> tuple[int, str]:
    result = subprocess.run([ACTIVATION_VERIFY], env=FIXED_ENV, capture_output=True, text=True, timeout=30,
                            check=False)
    return result.returncode, result.stdout


def _exact(lstat: Lstat, path: str, kind: Callable[[int], bool], mode: int, links: int | None = None) -> bool:
    meta = lstat(path)
    return (meta is not None and kind(meta.st_mode) and (meta.st_uid, meta.st_gid) == (0, 0)
            and stat.S_IMODE(meta.st_mode) == mode and (links is None or meta.st_nlink == links))


def _state_failures(lstat: Lstat, listdir: Callable[[str], list[str]], accounts: bool) -> list[str]:
    if not accounts:
        return ["ACCOUNTS_INVALID"]
    failures = []
    if not _exact(lstat, HOLD_PARENT, stat.S_ISDIR, 0o700) or listdir(HOLD_PARENT) != ["holds"]:
        failures.append("HOLD_PARENT_INEXACT")
    if not _exact(lstat, HOLD_STORE, stat.S_ISDIR, 0o700) or listdir(HOLD_STORE) != [HELD_NAME]:
        failures.append("HOLD_STORE_INEXACT")
    elif not _exact(lstat, HELD, stat.S_ISREG, 0o600, 1):
        failures.append("HELD_RECORD_INEXACT")
    return failures


def prove(phase: str, *, run: Runner = _run, lstat: Lstat = _lstat, listdir: Callable[[str], list[str]] = _listdir,
          accounts: Callable[[], bool] = _accounts, unit_state: Callable[[str], str] = _unit_state,
          activation: Callable[[], tuple[int, str]] = _activation, euid: Callable[[], int] = lambda: os.geteuid(),
          say: Callable[[str], None] = print) -> bool:
    if phase not in PHASES:
        say(f"MB10_HOLD_DENIAL_PROOF=FAIL phase={phase} reason=USAGE")
        return False
    if euid() != 0:
        say(f"MB10_HOLD_DENIAL_PROOF=FAIL phase={phase} reason=NOT_ROOT")
        return False
    refusals = [f"FAIL: STATE_UNEXPECTED {reason}" for reason in _state_failures(lstat, listdir, accounts())]
    if not refusals:
        say(f"STATE: {HOLD_PARENT} directory root:root 0700 entries=holds")
        say(f"STATE: {HOLD_STORE} directory root:root 0700 entries={HELD_NAME}")
        say(f"STATE: {HELD} regular root:root 0600 links=1")
    for unit in WITNESS_UNITS:
        if unit_state(unit) == "active":
            say(f"UNIT: {unit} ActiveState=active")
        else:
            refusals.append(f"FAIL: UNIT_NOT_ACTIVE {unit}")
    for unit in SIGNER_UNITS:
        if unit_state(unit) == "inactive":
            say(f"UNIT: {unit} ActiveState=inactive")
        else:
            refusals.append(f"FAIL: UNIT_NOT_INACTIVE {unit}")
    rc, out = activation()
    lines = out.splitlines()
    if rc == 1 and len(lines) == 1 and lines[0].startswith(GRANT_ABSENT + " "):
        say(GRANT_ABSENT)
    else:
        refusals.append("FAIL: ACTIVATION_NOT_GRANT_ABSENT")
    if refusals:
        for line in refusals:
            say(line)
        say(f"MB10_HOLD_DENIAL_PROOF=FAIL phase={phase} reason=PRECONDITION probes=0")
        return False
    denied = allowed = failed = 0
    for op, path, principals in ROWS:
        for principal in principals:
            code = run([RUNUSER, "-u", principal, "--", TEST, op, path])
            if code == 1:
                say(f"DENIED: {principal} test {op} {path}")
                denied += 1
            elif code == 0:
                say(f"FAIL: ALLOWED(unexpected) {principal} test {op} {path}")
                allowed += 1
            else:
                say(f"FAIL: PROBE_INCONCLUSIVE rc={code} {principal} test {op} {path}")
                failed += 1
    say(SCOPE_LINE)
    passed = denied == EXPECTED_DENIED and allowed == 0 and failed == 0
    say(f"MB10_HOLD_DENIAL_PROOF={'PASS' if passed else 'FAIL'} phase={phase} denied={denied} allowed={allowed}"
        + ("" if passed else f" inconclusive={failed}"))
    return passed


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("MB10_HOLD_DENIAL_PROOF=FAIL phase=- reason=USAGE")
        return 2
    return 0 if prove(argv[0]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
