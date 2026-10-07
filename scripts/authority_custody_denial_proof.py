#!/usr/bin/python3 -IB
"""LILITH 15B2b-B1b-3e PR-1S (S-15): fixed root denial proof for the PR-1 custody paths.

Run only by the owner, as root, on `lilith-dev-01`, streamed from the reviewed
CONTROL_SHA, inside a separately authorized PR-1A (P1A-10) or PR-1B (P1B-12)
evidence step. B1b-3e M-B4/M-B5 adds the closed phase `P1B-5`: after M-B5, the
three public install files (the two trust anchors and Registry V1) must be
unwritable by every outsider, the signer and the witness
(docs/architecture/slice-15b2b-b1b3e-mb4-mb5-ceremony-package.md). Control tooling only: never release payload, never run by the
routine deployer or GitHub Actions.

    sudo /usr/bin/python3 -I -B - <phase> < authority_custody_denial_proof.py

`<phase>` is one of the closed values below; there is no path, principal, or
command argument. Every probe is a FIXED row: `runuser -u <principal> --
/usr/bin/test <op> <path>` (access(2) as that principal; creates, reads, or
writes nothing), plus, from P1B-12, the signer mount-namespace probe
(`nsenter --target <MainPID> --mount --setuid/--setgid <signer>` then the
same `test`): the path must be inaccessible INSIDE the signer's namespace.

    DENIED requires the path to exist (checked by root `lstat` first).
    PATH_ABSENT != ACCESS_DENIED: a required path that is absent is a FAIL.

The last line is `AUTHORITY_CUSTODY_DENIAL_PROOF=PASS phase=<phase>` or
`...=FAIL phase=<phase>`; the exit status is 0 only on PASS. The owner binds
the SHA-256 of the complete transcript into the PR-1 package (E-7, E-9).

    denial proof != authority
"""

from __future__ import annotations

import os
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
NSENTER = "/usr/bin/nsenter"
SYSTEMCTL = "/usr/bin/systemctl"

PHASES = ("P1A-10", "P1B-5", "P1B-12")

CURRENT = "/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred"
CREDSTORE = "/etc/credstore.encrypted"
CUSTODY_ROOT = "/etc/lilith-authority-custody"
HOLD_PARENT = "/var/lib/lilith-authority-custody"
HOLD_STORE = HOLD_PARENT + "/holds"
WITNESS_CREDENTIAL_PARENT = "/etc/lilith-recovery-witness"
WITNESS_BLOB = WITNESS_CREDENTIAL_PARENT + "/credentials/lilith-recovery-witness.witness.cred"
AUTHORITY_CONFIG = "/etc/lilith-authority-dev"
REGISTRY_ROOT_ANCHOR = AUTHORITY_CONFIG + "/trust/registry-root.json"
WITNESS_ANCHOR = AUTHORITY_CONFIG + "/trust/witness-anchor.json"
REGISTRY_V1 = AUTHORITY_CONFIG + "/registry/authority-registry.v1.json"
AUTHORITY_STATE = "/var/lib/lilith-authority-dev"
LEDGER = AUTHORITY_STATE + "/authority_ledger.db"
WITNESS_STATE = "/var/lib/lilith-recovery-witness"
WITNESS_POINTER = WITNESS_STATE + "/witness.json"
WITNESS_OWNER_SOCKET = "/run/lilith-recovery-witness/owner.sock"
WITNESS_RUNTIME = "/run/lilith-recovery-witness"
AUTHORITY_RUNTIME = "/run/lilith-authority-dev"
SIGNER_CREDENTIALS = "/run/credentials/lilith-authority-dev.service"
WITNESS_CREDENTIALS = "/run/credentials/lilith-recovery-witness.service"
BROKER_STATE = "/var/lib/lilith-memory-broker"

OUTSIDERS = (APPLICATION, DEPLOYER, BROKER)
# (first phase, principals, op, path). Rows are the B1b-3d §17 N1-N9 / D1-D9,
# B1-B4, and broker probes, extended to the PR-1 custody, witness, and hold
# paths (preflight §8, §9, §19 E-7 .. E-9).
ROWS: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    ("P1A-10", OUTSIDERS + (WITNESS,), "-r", CREDSTORE),
    ("P1A-10", OUTSIDERS + (WITNESS,), "-x", CREDSTORE),
    ("P1A-10", OUTSIDERS, "-w", CREDSTORE),
    ("P1A-10", OUTSIDERS + (SIGNER, WITNESS), "-r", CUSTODY_ROOT),
    ("P1A-10", OUTSIDERS + (SIGNER, WITNESS), "-w", CUSTODY_ROOT),
    ("P1A-10", OUTSIDERS + (SIGNER, WITNESS), "-x", CUSTODY_ROOT),
    ("P1A-10", OUTSIDERS + (SIGNER, WITNESS), "-r", HOLD_PARENT),
    ("P1A-10", OUTSIDERS + (SIGNER, WITNESS), "-w", HOLD_PARENT),
    ("P1A-10", OUTSIDERS + (SIGNER, WITNESS), "-x", HOLD_PARENT),
    ("P1A-10", OUTSIDERS + (SIGNER, WITNESS), "-r", WITNESS_CREDENTIAL_PARENT),
    ("P1A-10", OUTSIDERS + (SIGNER, WITNESS), "-w", WITNESS_CREDENTIAL_PARENT),
    ("P1A-10", OUTSIDERS + (SIGNER, WITNESS), "-x", WITNESS_CREDENTIAL_PARENT),
    ("P1A-10", OUTSIDERS + (SIGNER, WITNESS), "-w", AUTHORITY_CONFIG),
    ("P1A-10", OUTSIDERS + (SIGNER, WITNESS), "-w", AUTHORITY_CONFIG + "/trust"),
    ("P1A-10", OUTSIDERS + (SIGNER, WITNESS), "-w", AUTHORITY_CONFIG + "/registry"),
    ("P1A-10", OUTSIDERS + (SIGNER, WITNESS), "-w", AUTHORITY_CONFIG + "/owner"),
    ("P1A-10", (SIGNER,), "-r", BROKER_STATE),
    ("P1B-5", OUTSIDERS + (SIGNER, WITNESS), "-w", REGISTRY_ROOT_ANCHOR),
    ("P1B-5", OUTSIDERS + (SIGNER, WITNESS), "-w", WITNESS_ANCHOR),
    ("P1B-5", OUTSIDERS + (SIGNER, WITNESS), "-w", REGISTRY_V1),
    ("P1B-12", OUTSIDERS + (WITNESS,), "-r", AUTHORITY_STATE),
    ("P1B-12", OUTSIDERS + (WITNESS,), "-x", AUTHORITY_STATE),
    ("P1B-12", OUTSIDERS + (WITNESS,), "-w", AUTHORITY_STATE),
    ("P1B-12", OUTSIDERS + (SIGNER,), "-w", WITNESS_STATE),
    ("P1B-12", OUTSIDERS, "-r", WITNESS_STATE),
    ("P1B-12", OUTSIDERS, "-x", WITNESS_STATE),
    ("P1B-12", (SIGNER,), "-w", WITNESS_POINTER),
    ("P1B-12", OUTSIDERS + (SIGNER,), "-w", WITNESS_OWNER_SOCKET),
    ("P1B-12", OUTSIDERS, "-x", WITNESS_RUNTIME),
    ("P1B-12", OUTSIDERS + (WITNESS,), "-x", AUTHORITY_RUNTIME),
    ("P1B-12", OUTSIDERS + (WITNESS,), "-r", SIGNER_CREDENTIALS),
    ("P1B-12", OUTSIDERS + (SIGNER,), "-r", WITNESS_CREDENTIALS),
)
# The signer's own mount namespace (E-7): unit InaccessiblePaths, observed at runtime.
NAMESPACE_ROWS = (("-r", CREDSTORE), ("-x", CREDSTORE), ("-r", CUSTODY_ROOT), ("-x", CUSTODY_ROOT),
                  ("-r", HOLD_PARENT), ("-x", HOLD_PARENT), ("-r", WITNESS_CREDENTIAL_PARENT),
                  ("-x", WITNESS_CREDENTIAL_PARENT), ("-r", BROKER_STATE))

Runner = Callable[[Sequence[str]], int]
Exists = Callable[[str], bool]


def _run(argv: Sequence[str]) -> int:
    return subprocess.run(list(argv), env=FIXED_ENV, capture_output=True, timeout=30, check=False).returncode


def _exists(path: str) -> bool:
    return os.path.lexists(path)


def _signer_pid() -> str:
    result = subprocess.run([SYSTEMCTL, "show", "--property=MainPID", "--value", "--", "lilith-authority-dev.service"],
                            env=FIXED_ENV, capture_output=True, text=True, timeout=30, check=False)
    return result.stdout.strip()


def _signer_ids() -> tuple[int, int] | None:
    import pwd

    try:
        entry = pwd.getpwnam(SIGNER)
    except KeyError:
        return None
    return entry.pw_uid, entry.pw_gid


def prove(phase: str, *, run: Runner = _run, exists: Exists = _exists, euid: Callable[[], int] = os.geteuid,
          signer_pid: Callable[[], str] = _signer_pid, signer_ids: Callable[[], tuple[int, int] | None] = _signer_ids,
          say: Callable[[str], None] = print) -> bool:
    if phase not in PHASES:
        say(f"AUTHORITY_CUSTODY_DENIAL_PROOF=FAIL phase={phase} reason=USAGE")
        return False
    if euid() != 0:
        say(f"AUTHORITY_CUSTODY_DENIAL_PROOF=FAIL phase={phase} reason=NOT_ROOT")
        return False
    failed = False
    active = PHASES.index(phase)
    for first, principals, op, path in ROWS:
        if PHASES.index(first) > active:
            say(f"DEFERRED_UNTIL_PHASE: {first} {op} {path}")
            continue
        if not exists(path):
            say(f"FAIL: DENIAL_VACUOUS_PATH_ABSENT {op} {path}")
            failed = True
            continue
        for principal in principals:
            rc = run([RUNUSER, "-u", principal, "--", TEST, op, path])
            if rc == 0:
                say(f"FAIL: ALLOWED(unexpected) {principal} test {op} {path}")
                failed = True
            elif rc == 1:
                say(f"DENIED: {principal} test {op} {path}")
            else:
                say(f"FAIL: PROBE_INCONCLUSIVE rc={rc} {principal} test {op} {path}")
                failed = True
    if phase == "P1B-12":
        pid, ids = signer_pid(), signer_ids()
        if not pid.isdigit() or pid in ("0", "1") or ids is None or 0 in ids:
            say("FAIL: SIGNER_NOT_RUNNING (the namespace probe needs the running signer and its account)")
            failed = True
        else:
            for op, path in NAMESPACE_ROWS:
                if not exists(path):
                    say(f"FAIL: DENIAL_VACUOUS_PATH_ABSENT namespace {op} {path}")
                    failed = True
                    continue
                rc = run([NSENTER, "--target", pid, "--mount", f"--setuid={ids[0]}", f"--setgid={ids[1]}", "--",
                          TEST, op, path])
                if rc == 0:
                    say(f"FAIL: ALLOWED(unexpected) signer-namespace test {op} {path}")
                    failed = True
                elif rc == 1:
                    say(f"DENIED: signer-namespace test {op} {path}")
                else:
                    say(f"FAIL: PROBE_INCONCLUSIVE rc={rc} signer-namespace test {op} {path}")
                    failed = True
    say(f"AUTHORITY_CUSTODY_DENIAL_PROOF={'FAIL' if failed else 'PASS'} phase={phase}")
    return not failed


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("AUTHORITY_CUSTODY_DENIAL_PROOF=FAIL phase=- reason=USAGE")
        return 2
    return 0 if prove(argv[0]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
