#!/usr/bin/python3 -IB
"""LILITH 15B2b-B1b-3e M-B6: the separate P1B-6 ledger denial proof (owner decision R-3).

Record: docs/architecture/slice-15b2b-b1b3e-mb6-ledger-remediation.md §13.
A SEPARATE file with its own SHA-256 pin. The P1B-5 proof
(`scripts/authority_custody_denial_proof.py`) and every M-B4/M-B5 pin are
unchanged; the M-B6 owner-acceptance evidence runs both proofs.

Run only by the owner, as root, on `lilith-dev-01`, streamed from the merged
control, in a separately authorized M-B6 evidence step AFTER a verified
`LEDGER_COMMITTED_EXACT`:

    sudo /usr/bin/python3 -I -B - P1B-6 < mb6_ledger_denial_proof.py

`P1B-6` is the only phase; there is no path, principal or command argument.

1. Root `lstat` refuses any state other than the reviewed successful one:
   `/var/lib/lilith-authority-dev` a real directory, signer `uid:gid`,
   `0700`, holding exactly `authority_ledger.db`; the ledger a regular file,
   signer `uid:gid`, `0600`, one link. A `-wal`, `-shm`, `-journal`, extra
   entry, symlink or other mode is a refusal, never a probe.
2. `lilith-authority-dev.service` and `lilith-recovery-witness.service` must
   be `inactive`: the proof implies no signer or witness activation.
3. `/usr/local/sbin/lilith-activation-verify` must report
   `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` (exit 1).
4. Only then the FIXED rows: `runuser -u <principal> -- /usr/bin/test <op>
   <path>` (access(2) as that principal; creates, reads, or writes nothing).
   Exit 1 = DENIED. Exit 0 = ALLOWED, which is never acceptable. Any other
   exit = inconclusive = FAIL.

The output is deterministic (no time, pid, inode or size), so the owner can
pin the SHA-256 of the complete transcript. The last line is
`MB6_LEDGER_DENIAL_PROOF=PASS phase=P1B-6 denied=20 allowed=0` or
`MB6_LEDGER_DENIAL_PROOF=FAIL phase=P1B-6 ...`; exit 0 only on PASS.

    denial proof != authority;  ledger provisioned != Registry V1 effective
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

PHASE = "P1B-6"
AUTHORITY_STATE = "/var/lib/lilith-authority-dev"
LEDGER_NAME = "authority_ledger.db"
LEDGER = AUTHORITY_STATE + "/" + LEDGER_NAME
UNITS = ("lilith-authority-dev.service", "lilith-recovery-witness.service")
GRANT_ABSENT = "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT"

# Every principal except the signer, which owns the state by design and is never probed.
PRINCIPALS = (APPLICATION, DEPLOYER, BROKER, WITNESS)
# (op, path): the M-B6 state directory and the ledger that exist after a successful M-B6.
ROWS: tuple[tuple[str, str], ...] = (
    ("-r", AUTHORITY_STATE),
    ("-x", AUTHORITY_STATE),
    ("-w", AUTHORITY_STATE),
    ("-r", LEDGER),
    ("-w", LEDGER),
)
EXPECTED_DENIED = len(ROWS) * len(PRINCIPALS)
SCOPE_LINE = ("SCOPE: denial only; ledger provisioned != Registry V1 effective != authority active; "
              "signer and witness not started")

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


def _signer_ids() -> tuple[int, int] | None:
    import pwd

    try:
        entry = pwd.getpwnam(SIGNER)
    except KeyError:
        return None
    return entry.pw_uid, entry.pw_gid


def _unit_state(unit: str) -> str:
    result = subprocess.run([SYSTEMCTL, "show", "--property=ActiveState", "--value", "--", unit],
                            env=FIXED_ENV, capture_output=True, text=True, timeout=30, check=False)
    return result.stdout.strip() if result.returncode == 0 else "UNREADABLE"


def _activation() -> tuple[int, str]:
    result = subprocess.run([ACTIVATION_VERIFY], env=FIXED_ENV, capture_output=True, text=True, timeout=30,
                            check=False)
    return result.returncode, result.stdout


def _state_failures(lstat: Lstat, listdir: Callable[[str], list[str]], ids: tuple[int, int] | None) -> list[str]:
    if ids is None or 0 in ids:
        return ["SIGNER_ACCOUNT_INVALID"]
    directory = lstat(AUTHORITY_STATE)
    if directory is None:
        return ["STATE_DIRECTORY_ABSENT"]
    if not stat.S_ISDIR(directory.st_mode):
        return ["STATE_DIRECTORY_NOT_A_REAL_DIRECTORY"]
    failures = []
    if (directory.st_uid, directory.st_gid) != ids:
        failures.append("STATE_DIRECTORY_OWNER_INEXACT")
    if stat.S_IMODE(directory.st_mode) != 0o700:
        failures.append("STATE_DIRECTORY_MODE_INEXACT")
    entries = listdir(AUTHORITY_STATE)
    if entries != [LEDGER_NAME]:
        failures.append("STATE_DIRECTORY_ENTRIES_INEXACT:" + ",".join(entries))
    ledger = lstat(LEDGER)
    if ledger is None:
        return failures + ["LEDGER_ABSENT"]
    if not stat.S_ISREG(ledger.st_mode):
        return failures + ["LEDGER_NOT_A_REGULAR_FILE"]
    if (ledger.st_uid, ledger.st_gid) != ids:
        failures.append("LEDGER_OWNER_INEXACT")
    if stat.S_IMODE(ledger.st_mode) != 0o600:
        failures.append("LEDGER_MODE_INEXACT")
    if ledger.st_nlink != 1:
        failures.append("LEDGER_LINK_COUNT_INEXACT")
    return failures


def prove(phase: str, *, run: Runner = _run, lstat: Lstat = _lstat, listdir: Callable[[str], list[str]] = _listdir,
          signer_ids: Callable[[], tuple[int, int] | None] = _signer_ids,
          unit_state: Callable[[str], str] = _unit_state, activation: Callable[[], tuple[int, str]] = _activation,
          euid: Callable[[], int] = lambda: os.geteuid(), say: Callable[[str], None] = print) -> bool:
    if phase != PHASE:
        say(f"MB6_LEDGER_DENIAL_PROOF=FAIL phase={phase} reason=USAGE")
        return False
    if euid() != 0:
        say(f"MB6_LEDGER_DENIAL_PROOF=FAIL phase={phase} reason=NOT_ROOT")
        return False
    refusals = [f"FAIL: STATE_UNEXPECTED {reason}" for reason in _state_failures(lstat, listdir, signer_ids())]
    if not refusals:
        say(f"STATE: {AUTHORITY_STATE} directory {SIGNER}:{SIGNER} 0700 entries={LEDGER_NAME}")
        say(f"STATE: {LEDGER} regular {SIGNER}:{SIGNER} 0600 links=1")
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
        say(f"MB6_LEDGER_DENIAL_PROOF=FAIL phase={phase} reason=PRECONDITION probes=0")
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
    say(f"MB6_LEDGER_DENIAL_PROOF={'PASS' if passed else 'FAIL'} phase={phase} denied={denied} allowed={allowed}"
        + ("" if passed else f" inconclusive={failed}"))
    return passed


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("MB6_LEDGER_DENIAL_PROOF=FAIL phase=- reason=USAGE")
        return 2
    return 0 if prove(argv[0]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
