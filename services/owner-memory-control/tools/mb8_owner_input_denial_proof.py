#!/usr/bin/env python3
"""LILITH 15B2b-B1b-3e Package A (M-B8): the separate P1B-8 owner-input denial proof.

A SEPARATE file with its own SHA-256 pin, like the P1B-6 ledger proof. The
P1B-5 proof (`scripts/authority_custody_denial_proof.py`) and the P1B-6 proof
(`mb6_ledger_denial_proof.py`) stay byte-for-byte unchanged, and both still
apply after M-B8 (neither lists the owner-input directory).

Run only by the owner, as root, on `lilith-dev-01`, streamed from the merged
control commit, after a verified `OWNER_INPUTS_INSTALLED_EXACT`:

    sudo /usr/bin/python3 -I -B - P1B-8 < mb8_owner_input_denial_proof.py

`P1B-8` is the only phase; there is no path, principal or command argument.

The two on-host copies are public (`0644`: every principal may read them,
and the witness must). What must be denied is replacing them: no non-root
principal (application, deployer, broker, signer, witness) may write either
file. The parent directories' write denials are already P1B-5 / P1A-10 rows.

Preconditions (exact, or no probe runs): the owner-input directory is
`root:root 0755` and lists exactly the two copies; each copy is a regular
`root:root 0644` file with one link; the signer and witness units are
inactive; activation reports `GRANT_ABSENT`.

The output is deterministic (no time, pid, inode or size). Expected PASS
transcript: 18 lines (3 `STATE:` + 2 `UNIT:` + 1 `GRANT_ABSENT` + 10
`DENIED:` + 1 `SCOPE:`, then the PASS line):
`MB8_OWNER_INPUT_DENIAL_PROOF=PASS phase=P1B-8 denied=10 allowed=0`; exit 0
only on PASS.

    denial proof != authority;  owner inputs installed != genesis != Registry V1 effective
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
FIXED_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "HOME": "/nonexistent"}
TEST = "/usr/bin/test"
RUNUSER = "/usr/sbin/runuser"
SYSTEMCTL = "/usr/bin/systemctl"
ACTIVATION_VERIFY = "/usr/local/sbin/lilith-activation-verify"

PHASE = "P1B-8"
OWNER_INPUT_DIR = "/etc/lilith-authority-dev/owner"
PIN_NAME = "genesis-pin.json"
REGISTER_NAME = "authorization-register.json"
COPIES = (OWNER_INPUT_DIR + "/" + PIN_NAME, OWNER_INPUT_DIR + "/" + REGISTER_NAME)
UNITS = ("lilith-authority-dev.service", "lilith-recovery-witness.service")
GRANT_ABSENT = "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT"

PRINCIPALS = (APPLICATION, DEPLOYER, BROKER, SIGNER, WITNESS)
ROWS: tuple[tuple[str, str], ...] = tuple(("-w", path) for path in COPIES)
EXPECTED_DENIED = len(ROWS) * len(PRINCIPALS)
SCOPE_LINE = ("SCOPE: write denial only; owner inputs installed != witness genesis != Registry V1 effective "
              "!= authority active; signer and witness not started")

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


def _unit_state(unit: str) -> str:
    result = subprocess.run([SYSTEMCTL, "show", "--property=ActiveState", "--value", "--", unit],
                            env=FIXED_ENV, capture_output=True, text=True, timeout=30, check=False)
    return result.stdout.strip() if result.returncode == 0 else "UNREADABLE"


def _activation() -> tuple[int, str]:
    result = subprocess.run([ACTIVATION_VERIFY], env=FIXED_ENV, capture_output=True, text=True, timeout=30,
                            check=False)
    return result.returncode, result.stdout


def _state_failures(lstat: Lstat, listdir: Callable[[str], list[str]]) -> list[str]:
    directory = lstat(OWNER_INPUT_DIR)
    if directory is None or not stat.S_ISDIR(directory.st_mode):
        return ["OWNER_INPUT_DIRECTORY_ABSENT_OR_NOT_A_DIRECTORY"]
    failures = []
    if (directory.st_uid, directory.st_gid, stat.S_IMODE(directory.st_mode)) != (0, 0, 0o755):
        failures.append("OWNER_INPUT_DIRECTORY_INEXACT")
    entries = listdir(OWNER_INPUT_DIR)
    if entries != sorted((PIN_NAME, REGISTER_NAME)):
        failures.append("OWNER_INPUT_ENTRIES_INEXACT:" + ",".join(entries))
    for path in COPIES:
        meta = lstat(path)
        if meta is None:
            failures.append("COPY_ABSENT:" + path)
        elif not stat.S_ISREG(meta.st_mode):
            failures.append("COPY_NOT_A_REGULAR_FILE:" + path)
        elif (meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode), meta.st_nlink) != (0, 0, 0o644, 1):
            failures.append("COPY_METADATA_INEXACT:" + path)
    return failures


def prove(phase: str, *, run: Runner = _run, lstat: Lstat = _lstat, listdir: Callable[[str], list[str]] = _listdir,
          unit_state: Callable[[str], str] = _unit_state, activation: Callable[[], tuple[int, str]] = _activation,
          euid: Callable[[], int] = lambda: os.geteuid(), say: Callable[[str], None] = print) -> bool:
    if phase != PHASE:
        say(f"MB8_OWNER_INPUT_DENIAL_PROOF=FAIL phase={phase} reason=USAGE")
        return False
    if euid() != 0:
        say(f"MB8_OWNER_INPUT_DENIAL_PROOF=FAIL phase={phase} reason=NOT_ROOT")
        return False
    refusals = [f"FAIL: STATE_UNEXPECTED {reason}" for reason in _state_failures(lstat, listdir)]
    if not refusals:
        say(f"STATE: {OWNER_INPUT_DIR} directory root:root 0755 entries={REGISTER_NAME},{PIN_NAME}")
        for path in COPIES:
            say(f"STATE: {path} regular root:root 0644 links=1")
    for unit in UNITS:
        active = unit_state(unit)
        if active == "inactive":
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
        say(f"MB8_OWNER_INPUT_DENIAL_PROOF=FAIL phase={phase} reason=PRECONDITION probes=0")
        return False
    denied = allowed = failed = 0
    for op, path in ROWS:
        for principal in PRINCIPALS:
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
    say(f"MB8_OWNER_INPUT_DENIAL_PROOF={'PASS' if passed else 'FAIL'} phase={phase} denied={denied} allowed={allowed}"
        + ("" if passed else f" inconclusive={failed}"))
    return passed


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("MB8_OWNER_INPUT_DENIAL_PROOF=FAIL phase=- reason=USAGE")
        return 2
    return 0 if prove(argv[0]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
