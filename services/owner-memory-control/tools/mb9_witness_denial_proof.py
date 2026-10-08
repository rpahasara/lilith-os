#!/usr/bin/env python3
"""LILITH 15B2b-B1b-3e Package B (M-B9a / M-B9b): the separate witness denial proof, phases P1B-9a and P1B-9b.

Record: docs/architecture/slice-15b2b-b1b3e-mb9-witness-genesis-package.md §11.

A SEPARATE file with its own SHA-256 pin. The P1B-5 proof (`scripts/authority_custody_denial_proof.py`), the
P1B-6 proof (`mb6_ledger_denial_proof.py`) and the P1B-8 proof (`mb8_owner_input_denial_proof.py`) stay
byte-for-byte unchanged. P1B-5 still applies while the witness runs (its witness rows are deferred to P1B-12 and
it has no unit precondition). P1B-6 and P1B-8 do NOT: both require `lilith-recovery-witness.service` inactive,
so once M-B9a starts the witness they are simply out of their valid phase (not drift, not failure). This proof
re-covers their ledger and owner-input rows with the witness active.

Run only by the owner, as root, on `lilith-dev-01`, streamed from the merged control commit:

    sudo /usr/bin/python3 -I -B - P1B-9a < mb9_witness_denial_proof.py     (after an exact M-B9a)
    sudo /usr/bin/python3 -I -B - P1B-9b < mb9_witness_denial_proof.py     (after an exact M-B9b)

There is no path, principal or command argument.

Each row names the principals that must be DENIED and, explicitly, the principals whose access is
ALLOWED_BY_DESIGN (owner decision OD-B9: the signer reads and traverses the setgid witness state, and reaches its
own socket). A by-design row that is denied, a denial row that is allowed, and any inconclusive probe all FAIL.
Not probed, by design: the witness on its own state (it is the only writer), on its signer socket (it is the
listener and serves the inherited descriptor) and on its own runtime credential (it is the consumer).

Preconditions (exact, or no probe runs): the witness state (2750 `lilith-recovery-witness:lilith-authority-dev`)
holds exactly the phase's entries; the ledger and the owner-input copies are exactly the accepted M-B6 / M-B8
state; the runtime directory, the two sockets and the runtime credential exist with the unit-file metadata;
the witness service and both witness sockets are active; the signer service and socket are inactive;
activation reports `GRANT_ABSENT`.

The output is deterministic (no time, pid, inode or size). The last line is
`MB9_WITNESS_DENIAL_PROOF=PASS phase=<phase> denied=<n> allowed_by_design=<m> allowed=0`; exit 0 only on PASS.

    denial proof != authority;  witness started != genesis committed != record 1 != Registry V1 effective
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

PHASES = ("P1B-9a", "P1B-9b")
WITNESS_STATE = "/var/lib/lilith-recovery-witness"
LOCK = WITNESS_STATE + "/witness.lock"
CHAIN = WITNESS_STATE + "/chain"
GENESIS = CHAIN + "/1.json"
POINTER = WITNESS_STATE + "/witness.json"
AUTHORIZATIONS = WITNESS_STATE + "/authorizations"
RUNTIME = "/run/lilith-recovery-witness"
OWNER_SOCKET = RUNTIME + "/owner.sock"
SIGNER_SOCKET = RUNTIME + "/signer.sock"
CREDENTIALS = "/run/credentials/lilith-recovery-witness.service"
AUTHORITY_STATE = "/var/lib/lilith-authority-dev"
LEDGER_NAME = "authority_ledger.db"
LEDGER = AUTHORITY_STATE + "/" + LEDGER_NAME
OWNER_INPUT_DIR = "/etc/lilith-authority-dev/owner"
PIN_COPY = OWNER_INPUT_DIR + "/genesis-pin.json"
REGISTER_COPY = OWNER_INPUT_DIR + "/authorization-register.json"
ROOT_ANCHOR = "/etc/lilith-authority-dev/trust/registry-root.json"
WITNESS_ANCHOR = "/etc/lilith-authority-dev/trust/witness-anchor.json"
REGISTRY_V1 = "/etc/lilith-authority-dev/registry/authority-registry.v1.json"
KWIT_BLOB = "/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred"
WITNESS_UNITS = ("lilith-recovery-witness.service", "lilith-recovery-witness-owner.socket",
                 "lilith-recovery-witness-signer.socket")
SIGNER_UNITS = ("lilith-authority-dev.service", "lilith-authority-dev.socket")
STATE_ENTRIES = {"P1B-9a": ["witness.lock"], "P1B-9b": ["authorizations", "chain", "witness.json", "witness.lock"]}
SUBDIRECTORY_MODES = (0o2750, 0o750)

# (first phase, op, path, DENIED principals, ALLOWED_BY_DESIGN principals)
ROWS: tuple[tuple[str, str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    # the witness state: no non-witness write; outsiders never read or traverse; the signer reads by design
    ("P1B-9a", "-w", WITNESS_STATE, OUTSIDERS + (SIGNER,), ()),
    ("P1B-9a", "-r", WITNESS_STATE, OUTSIDERS, (SIGNER,)),
    ("P1B-9a", "-x", WITNESS_STATE, OUTSIDERS, (SIGNER,)),
    ("P1B-9a", "-w", LOCK, OUTSIDERS + (SIGNER,), ()),
    ("P1B-9a", "-r", LOCK, OUTSIDERS, (SIGNER,)),
    # the lineage objects (exist after M-B9b only)
    ("P1B-9b", "-w", CHAIN, OUTSIDERS + (SIGNER,), ()),
    ("P1B-9b", "-r", CHAIN, OUTSIDERS, (SIGNER,)),
    ("P1B-9b", "-x", CHAIN, OUTSIDERS, (SIGNER,)),
    ("P1B-9b", "-w", GENESIS, OUTSIDERS + (SIGNER,), ()),
    ("P1B-9b", "-r", GENESIS, OUTSIDERS, (SIGNER,)),
    ("P1B-9b", "-w", POINTER, OUTSIDERS + (SIGNER,), ()),
    ("P1B-9b", "-r", POINTER, OUTSIDERS, (SIGNER,)),
    ("P1B-9b", "-w", AUTHORIZATIONS, OUTSIDERS + (SIGNER,), ()),
    ("P1B-9b", "-r", AUTHORIZATIONS, OUTSIDERS, (SIGNER,)),
    ("P1B-9b", "-x", AUTHORIZATIONS, OUTSIDERS, (SIGNER,)),
    # runtime: the owner socket is root only; the signer socket is the signer's; the credential is the witness's
    ("P1B-9a", "-x", RUNTIME, OUTSIDERS, (SIGNER,)),
    ("P1B-9a", "-w", OWNER_SOCKET, EVERYONE, ()),
    ("P1B-9a", "-w", SIGNER_SOCKET, OUTSIDERS, (SIGNER,)),
    ("P1B-9a", "-r", CREDENTIALS, OUTSIDERS + (SIGNER,), ()),
    ("P1B-9a", "-x", CREDENTIALS, OUTSIDERS + (SIGNER,), ()),
    # the ledger (P1B-6 rows, re-covered with the witness active; the signer owns it and is not probed)
    ("P1B-9a", "-r", AUTHORITY_STATE, OUTSIDERS + (WITNESS,), ()),
    ("P1B-9a", "-x", AUTHORITY_STATE, OUTSIDERS + (WITNESS,), ()),
    ("P1B-9a", "-w", AUTHORITY_STATE, OUTSIDERS + (WITNESS,), ()),
    ("P1B-9a", "-r", LEDGER, OUTSIDERS + (WITNESS,), ()),
    ("P1B-9a", "-w", LEDGER, OUTSIDERS + (WITNESS,), ()),
    # the owner inputs (P1B-8 rows, re-covered): public, never replaceable
    ("P1B-9a", "-w", PIN_COPY, EVERYONE, ()),
    ("P1B-9a", "-w", REGISTER_COPY, EVERYONE, ()),
    # trust anchors and Registry V1: never writable by any service principal (the witness included)
    ("P1B-9a", "-w", ROOT_ANCHOR, EVERYONE, ()),
    ("P1B-9a", "-w", WITNESS_ANCHOR, EVERYONE, ()),
    ("P1B-9a", "-w", REGISTRY_V1, EVERYONE, ()),
    # the encrypted K-WIT blob: root only (systemd loads it as root through LoadCredentialEncrypted=)
    ("P1B-9a", "-r", KWIT_BLOB, EVERYONE, ()),
    ("P1B-9a", "-w", KWIT_BLOB, EVERYONE, ()),
)


def rows_for(phase: str) -> list[tuple[str, str, tuple[str, ...], tuple[str, ...]]]:
    active = PHASES.index(phase)
    return [(op, path, denied, by_design) for first, op, path, denied, by_design in ROWS
            if PHASES.index(first) <= active]


def expected_counts(phase: str) -> tuple[int, int]:
    rows = rows_for(phase)
    return sum(len(d) for _, _, d, _ in rows), sum(len(b) for _, _, _, b in rows)


SCOPE_LINE = ("SCOPE: denial and by-design access only; witness started != witness genesis committed != record 1 "
              "!= Registry V1 effective != authority active; signer not started")

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


def _ids() -> dict[str, int] | None:
    import grp
    import pwd

    try:
        return {"witness": pwd.getpwnam(WITNESS).pw_uid, "signer": pwd.getpwnam(SIGNER).pw_uid,
                "signerGid": grp.getgrnam(SIGNER).gr_gid, "witnessGid": pwd.getpwnam(WITNESS).pw_gid}
    except KeyError:
        return None


def _unit_state(unit: str) -> str:
    result = subprocess.run([SYSTEMCTL, "show", "--property=ActiveState", "--value", "--", unit],
                            env=FIXED_ENV, capture_output=True, text=True, timeout=30, check=False)
    return result.stdout.strip() if result.returncode == 0 else "UNREADABLE"


def _activation() -> tuple[int, str]:
    result = subprocess.run([ACTIVATION_VERIFY], env=FIXED_ENV, capture_output=True, text=True, timeout=30,
                            check=False)
    return result.returncode, result.stdout


def _exact(lstat: Lstat, path: str, kind: Callable[[int], bool], owner: tuple[int, int], modes: Sequence[int],
           links: int | None = None) -> bool:
    meta = lstat(path)
    return (meta is not None and kind(meta.st_mode) and (meta.st_uid, meta.st_gid) == owner
            and stat.S_IMODE(meta.st_mode) in modes and (links is None or meta.st_nlink == links))


def _state_failures(phase: str, lstat: Lstat, listdir: Callable[[str], list[str]], ids: dict[str, int] | None
                    ) -> list[str]:
    if ids is None or 0 in ids.values():
        return ["ACCOUNTS_INVALID"]
    wit = (ids["witness"], ids["signerGid"])
    signer = (ids["signer"], ids["signerGid"])
    is_dir, is_reg, is_sock = stat.S_ISDIR, stat.S_ISREG, stat.S_ISSOCK
    failures = []
    if not _exact(lstat, WITNESS_STATE, is_dir, wit, (0o2750,)):
        return ["WITNESS_STATE_INEXACT"]
    if listdir(WITNESS_STATE) != STATE_ENTRIES[phase]:
        failures.append("WITNESS_STATE_ENTRIES_INEXACT")
    files = [LOCK] + ([POINTER, GENESIS] if phase == "P1B-9b" else [])
    for path in files:
        if not _exact(lstat, path, is_reg, wit, (0o640,), 1):
            failures.append("WITNESS_FILE_INEXACT:" + path)
    if phase == "P1B-9b":
        for path, entries in ((CHAIN, ["1.json"]), (AUTHORIZATIONS, [])):
            if not _exact(lstat, path, is_dir, wit, SUBDIRECTORY_MODES) or listdir(path) != entries:
                failures.append("WITNESS_DIRECTORY_INEXACT:" + path)
    if not _exact(lstat, AUTHORITY_STATE, is_dir, signer, (0o700,)) or listdir(AUTHORITY_STATE) != [LEDGER_NAME] \
            or not _exact(lstat, LEDGER, is_reg, signer, (0o600,), 1):
        failures.append("LEDGER_STATE_INEXACT")
    if not _exact(lstat, OWNER_INPUT_DIR, is_dir, (0, 0), (0o755,)) \
            or listdir(OWNER_INPUT_DIR) != ["authorization-register.json", "genesis-pin.json"] \
            or not all(_exact(lstat, p, is_reg, (0, 0), (0o644,), 1) for p in (PIN_COPY, REGISTER_COPY)):
        failures.append("OWNER_INPUTS_INEXACT")
    # the unit-file metadata: tmpfiles `d ... 0710 root lilith-authority-dev`; SocketMode / SocketUser / SocketGroup
    if not _exact(lstat, RUNTIME, is_dir, (0, ids["signerGid"]), (0o710,)) \
            or not _exact(lstat, OWNER_SOCKET, is_sock, (0, 0), (0o600,)) \
            or not _exact(lstat, SIGNER_SOCKET, is_sock, wit, (0o660,)):
        failures.append("RUNTIME_INEXACT")
    credentials = lstat(CREDENTIALS)
    if credentials is None or not stat.S_ISDIR(credentials.st_mode):
        failures.append("RUNTIME_CREDENTIAL_ABSENT")
    return failures


def prove(phase: str, *, run: Runner = _run, lstat: Lstat = _lstat, listdir: Callable[[str], list[str]] = _listdir,
          ids: Callable[[], dict[str, int] | None] = _ids, unit_state: Callable[[str], str] = _unit_state,
          activation: Callable[[], tuple[int, str]] = _activation, euid: Callable[[], int] = lambda: os.geteuid(),
          say: Callable[[str], None] = print) -> bool:
    if phase not in PHASES:
        say(f"MB9_WITNESS_DENIAL_PROOF=FAIL phase={phase} reason=USAGE")
        return False
    if euid() != 0:
        say(f"MB9_WITNESS_DENIAL_PROOF=FAIL phase={phase} reason=NOT_ROOT")
        return False
    refusals = [f"FAIL: STATE_UNEXPECTED {reason}" for reason in _state_failures(phase, lstat, listdir, ids())]
    if not refusals:
        say(f"STATE: {WITNESS_STATE} directory {WITNESS}:{SIGNER} 2750 entries={','.join(STATE_ENTRIES[phase])}")
        if phase == "P1B-9b":
            say(f"STATE: {CHAIN} entries=1.json; {AUTHORIZATIONS} entries=")
        say(f"STATE: {AUTHORITY_STATE} entries={LEDGER_NAME}; {OWNER_INPUT_DIR} entries=authorization-register.json,"
            "genesis-pin.json")
        say(f"STATE: {RUNTIME} root:{SIGNER} 0710; owner.sock root:root 0600; signer.sock {WITNESS}:{SIGNER} 0660; "
            "runtime credential present")
    for unit in WITNESS_UNITS:
        active = unit_state(unit)
        if active == "active":
            say(f"UNIT: {unit} ActiveState=active")
        else:
            refusals.append(f"FAIL: UNIT_NOT_ACTIVE {unit}")
    for unit in SIGNER_UNITS:
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
        say(f"MB9_WITNESS_DENIAL_PROOF=FAIL phase={phase} reason=PRECONDITION probes=0")
        return False
    denied = by_design = allowed = failed = 0
    for op, path, denied_principals, design_principals in rows_for(phase):
        for principal in denied_principals:
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
        for principal in design_principals:
            code = run([RUNUSER, "-u", principal, "--", TEST, op, path])
            if code == 0:
                say(f"ALLOWED_BY_DESIGN: {principal} test {op} {path}")
                by_design += 1
            elif code == 1:
                say(f"FAIL: BY_DESIGN_ACCESS_DENIED {principal} test {op} {path}")
                failed += 1
            else:
                say(f"FAIL: PROBE_INCONCLUSIVE rc={code} {principal} test {op} {path}")
                failed += 1
    say(SCOPE_LINE)
    want_denied, want_by_design = expected_counts(phase)
    passed = denied == want_denied and by_design == want_by_design and allowed == 0 and failed == 0
    say(f"MB9_WITNESS_DENIAL_PROOF={'PASS' if passed else 'FAIL'} phase={phase} denied={denied} "
        f"allowed_by_design={by_design} allowed={allowed}" + ("" if passed else f" inconclusive={failed}"))
    return passed


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("MB9_WITNESS_DENIAL_PROOF=FAIL phase=- reason=USAGE")
        return 2
    return 0 if prove(argv[0]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
