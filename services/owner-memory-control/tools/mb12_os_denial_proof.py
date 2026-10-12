#!/usr/bin/python3 -IB
"""15B2b-B1b-3e M-B12 PR-B2: the OS_DENIAL proof producer (E-7, unit-property half). Root, read-only, DEV.

Record: docs/architecture/slice-15b2b-b1b3e-mb12-prb2-proof-producers.md.
DESIGN / SOURCE ONLY. Running it live needs a separate owner authorization.

Preflight §19 E-7 is "authority service denial of PREPARED/RETIRED: unit property + mount-namespace probe"; §8 defines
the two halves: "config level: the installed unit bytes equal the NEW release asset and `systemctl show -p
InaccessiblePaths` lists `/etc/lilith-authority-custody`. Runtime level (PR-1B, signer running): a probe inside the
signer's mount namespace". The runtime half is `SIGNER_DENIAL` (`scripts/authority_custody_denial_proof.py P1B-12`,
the 9 namespace rows). This tool is the config half, `OS_DENIAL` (the OD-M11-14 mapping, PROPOSED). It needs no
running signer, starts nothing, connects to no socket and reads no credential:

- `systemctl show` of exactly the fixed properties of `lilith-authority-dev.service` (never start, never reload);
- the installed fragment bytes and the selected release asset bytes, both = the accepted `aee323e` fragment;
- `DropInPaths` empty, or exactly the pinned P1B-10R service overlay (OD-M11-11) with its pinned bytes;
- the effective `InaccessiblePaths` exactly the release value (both custody slots' parent and the credstore included);
- `User=lilith-authority-dev`, `LoadState=loaded`, `NeedDaemonReload=no`.

    sudo /usr/bin/python3 -I -B - UNIT < mb12_os_denial_proof.py

The last line is `OS_DENIAL_PROOF=PASS unit=lilith-authority-dev.service` (exit 0) or `OS_DENIAL_PROOF=FAIL …`
(exit 1); usage is exit 2. A PASS transcript is exactly `expected_pass(...)`: the builder
(`mb12_readiness_inputs`) rebuilds it byte for byte.

    unit property != runtime denial;  OS_DENIAL PASS != SIGNER_DENIAL;  denial proof != authority
"""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import sys
from typing import Callable, Sequence

PHASE = "UNIT"
UNIT = "lilith-authority-dev.service"
FRAGMENT = "/etc/systemd/system/lilith-authority-dev.service"
RELEASE_ASSET = "/opt/lilith-authority-dev/current/assets/lilith-authority-dev.service"
FRAGMENT_SHA256 = "11b6d00f04d998caa156875fb587dd642cb7d78dd9b6d1866616cc0b9bc1b254"   # aee323e, P1B-10R §1
P1B10R_DROPIN = "/etc/systemd/system/lilith-authority-dev.service.d/10-no-implicit-restart.conf"
P1B10R_DROPIN_SHA256 = "e3faf9efa91f0238ee6110a33cf6c9f024aca1029fe05bd26fba4c21679c6b92"
USER = "lilith-authority-dev"
# The release unit's InaccessiblePaths, in order (`services/authority-dev/deploy/lilith-authority-dev.service`).
INACCESSIBLE = ("/etc/credstore.encrypted", "/etc/lilith-authority-custody", "/var/lib/lilith-authority-custody",
                "/etc/lilith-recovery-witness", "/etc/lilith-memory-broker", "/var/lib/lilith-memory-broker",
                "/etc/lilith-os-dev")
REQUIRED_DENIED = ("/etc/lilith-authority-custody", "/etc/credstore.encrypted")   # PREPARED / RETIRED; CURRENT
PROPERTIES = ("Id", "LoadState", "NeedDaemonReload", "FragmentPath", "DropInPaths", "User", "InaccessiblePaths")
SYSTEMCTL = "/usr/bin/systemctl"
FIXED_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "HOME": "/nonexistent"}
MAX_UNIT_BYTES = 64 * 1024
DROPINS_NONE = "NONE"
DROPINS_P1B10R = "P1B-10R"

Runner = Callable[[Sequence[str]], tuple[int, str]]
Reader = Callable[[str], "bytes | None"]


def final_line(passed: bool, reason: str | None = None) -> str:
    return f"OS_DENIAL_PROOF={'PASS' if passed else 'FAIL'} unit={UNIT}" + (f" reason={reason}" if reason else "")


def expected_pass(dropins: str) -> bytes:
    """The complete PASS transcript for one of the two admitted overlay states."""
    if dropins not in (DROPINS_NONE, DROPINS_P1B10R):
        raise ValueError("dropins")
    lines = [f"UNIT: {UNIT} LoadState=loaded NeedDaemonReload=no User={USER}",
             f"FRAGMENT: {FRAGMENT} sha256={FRAGMENT_SHA256} releaseAsset=EQUAL",
             "DROPINS: NONE" if dropins == DROPINS_NONE else
             f"DROPINS: P1B-10R {P1B10R_DROPIN} sha256={P1B10R_DROPIN_SHA256}"]
    lines += [f"INACCESSIBLE: {path}" for path in INACCESSIBLE]
    lines.append(final_line(True))
    return ("\n".join(lines) + "\n").encode("ascii")


def _run(argv: Sequence[str]) -> tuple[int, str]:
    result = subprocess.run(list(argv), env=FIXED_ENV, capture_output=True, text=True, timeout=30, check=False)
    return result.returncode, result.stdout


def _read(path: str) -> bytes | None:
    """Bytes of one root-owned regular file, never through a symlink, bounded; None if not exactly that."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        return None
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_uid != 0 or meta.st_size > MAX_UNIT_BYTES \
                or meta.st_mode & 0o022:
            return None
        return os.read(fd, MAX_UNIT_BYTES + 1)
    finally:
        os.close(fd)


def parse_show(text: str) -> dict[str, str] | None:
    """`systemctl show -p …` output as {key: value} with exactly PROPERTIES, or None."""
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            return None
        key, value = line.split("=", 1)
        if key in values:
            return None
        values[key] = value
    return values if set(values) == set(PROPERTIES) else None


def prove(phase: str, *, run: Runner = _run, read: Reader = _read, euid: Callable[[], int] = os.geteuid,
          say: Callable[[str], None] = print) -> bool:
    if phase != PHASE:
        say(final_line(False, "USAGE"))
        return False
    if euid() != 0:
        say(final_line(False, "NOT_ROOT"))
        return False
    failures: list[str] = []
    rc, text = run([SYSTEMCTL, "show", "--no-pager", "-p", ",".join(PROPERTIES), "--", UNIT])
    show = parse_show(text) if rc == 0 else None
    if show is None:
        say("FAIL: UNIT_PROPERTIES_UNOBSERVED")
        say(final_line(False))
        return False
    unit_ok = (show["Id"] == UNIT and show["LoadState"] == "loaded" and show["NeedDaemonReload"] == "no"
               and show["User"] == USER and show["FragmentPath"] == FRAGMENT)
    if unit_ok:
        say(f"UNIT: {UNIT} LoadState=loaded NeedDaemonReload=no User={USER}")
    else:
        failures.append("FAIL: UNIT_NOT_EXACT")
    fragment, asset = read(FRAGMENT), read(RELEASE_ASSET)
    digest = None if fragment is None else hashlib.sha256(fragment).hexdigest()
    if digest == FRAGMENT_SHA256 and asset == fragment:
        say(f"FRAGMENT: {FRAGMENT} sha256={FRAGMENT_SHA256} releaseAsset=EQUAL")
    else:
        failures.append("FAIL: FRAGMENT_NOT_RELEASE_ASSET" if fragment is not None else "FAIL: FRAGMENT_UNOBSERVED")
    dropins = show["DropInPaths"]
    if dropins == "":
        say("DROPINS: NONE")
    elif dropins == P1B10R_DROPIN and (lambda b: b is not None and hashlib.sha256(b).hexdigest()
                                       == P1B10R_DROPIN_SHA256)(read(P1B10R_DROPIN)):
        say(f"DROPINS: P1B-10R {P1B10R_DROPIN} sha256={P1B10R_DROPIN_SHA256}")
    else:
        failures.append("FAIL: DROPINS_NOT_ADMITTED")
    effective = tuple(show["InaccessiblePaths"].split(" ")) if show["InaccessiblePaths"] else ()
    if effective == INACCESSIBLE and all(path in effective for path in REQUIRED_DENIED):
        for path in INACCESSIBLE:
            say(f"INACCESSIBLE: {path}")
    else:
        failures.append("FAIL: INACCESSIBLE_PATHS_NOT_EXACT")
    for line in failures:
        say(line)
    say(final_line(not failures))
    return not failures


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(final_line(False, "USAGE"))
        return 2
    return 0 if prove(argv[0]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
