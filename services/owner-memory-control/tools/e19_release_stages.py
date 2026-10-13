#!/usr/bin/env python3
"""15B2b-B1b-3e E-19: the release stages of `UPGRADE_FROM_P1B10_DEV_SYNTHETIC` (STAGE, SELECT, RETIRE-OLD) on DEV.

Record: docs/architecture/slice-15b2b-b1b3e-e19-transition-implementation.md (E19-D1 … E19-D5 owner-ACCEPTED).
SOURCE ONLY: every mutating form needs its own owner go through `e19_operator.py`; nothing here is authorized by the
repository.

It runs as root on DEV in ONE pinned in-memory mb6 BOOT bundle together with the merged contract
`e19_p1b10_upgrade.py` (the OLD release, the payload delta and the ending incarnation come from it) and the
byte-unchanged installer
`services/authority-dev/ceremony/install_authority_dev.py` (`fe10d9a3…`, pinned and streamed by the completed M-B6,
M-B9 and M-B10 operators, so it is never edited). It reuses the installer's archive verification, release-tree check,
write helpers and `status`, and changes none of them. The installer's own `UPGRADE_EXISTING_DEV_SYNTHETIC` mode keeps
refusing a custody host (`_require_upgrade`); this is a separate, explicit mode:

    E19_OLD_ONLY      {OLD}       current -> OLD     (U0)
    E19_NEW_STAGED    {OLD, NEW}  current -> OLD     (U1, U2)
    E19_NEW_SELECTED  {OLD, NEW}  current -> NEW     (U3, U4)
    E19_OLD_RETIRED   {NEW}       current -> NEW     (U5)

Every state is judged from the release set, the selector, both trees, the payload delta (exactly
`lilith_owner_memory/pr1_acceptance.py`, the contract's `PAYLOAD_DELTA`, record §3.2) and the unchanged installer
`status --expect P1B-10` of the SELECTED release, whose only admissible failure while two releases are installed is
`RELEASE_SET`. Units and CLIs are byte-identical in both releases, so there is no unit, daemon-reload or CLI stage.

Forms (root on DEV):

    e19-status <OLD> <NEW>                                           read-only
    e19-stage <OLD> <NEW> <manifest-sha256> <archive> <attestation>  E19_OLD_ONLY -> E19_NEW_STAGED
    e19-select <OLD> <NEW>                                           E19_NEW_STAGED -> E19_NEW_SELECTED (witness STOPPED)
    e19-retire-old <OLD> <NEW> <replacement-invocation-id>           E19_NEW_SELECTED -> E19_OLD_RETIRED

Each mutating form refuses unless its exact pre-state holds, never overwrites (staging `mkdir`, `O_EXCL` files,
`symlink` + `rename` selector), and never retries, repairs, rolls back, reloads, starts or stops a unit, loads a
credential or touches custody, HELD, the ledger or the witness state. RETIRE removes only `releases/<OLD>`, and only
while the replacement incarnation named by the owner's go runs from `releases/<NEW>`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

import e19_p1b10_upgrade as E  # noqa: E402  (BOOT bundle member; the merged contract)
import install_authority_dev as I  # noqa: E402  (BOOT bundle member; on a workstation: services/authority-dev/ceremony)

MODE = E.MODE
OLD_RELEASE = E.OLD_RELEASE
(DELTA_MEMBER, (DELTA_OLD_SHA256, DELTA_NEW_SHA256)), = E.PAYLOAD_DELTA.items()
ENDING_INVOCATION = E.ENDING_INCARNATION[0]
INSTALLED_STAGE = "P1B-10"
WITNESS_SERVICE, OWNER_SOCKET, SIGNER_SOCKET = I.WITNESS_UNITS
UNIT_PROPERTIES = ("ActiveState", "SubState", "MainPID", "InvocationID", "NRestarts")
SELECTOR_TMP = I.OPT + "/.current.tmp"

OLD_ONLY = "E19_OLD_ONLY"
STAGED = "E19_NEW_STAGED"
SELECTED = "E19_NEW_SELECTED"
RETIRED = "E19_OLD_RETIRED"
INCONSISTENT = "E19_INCONSISTENT"
STATES = (OLD_ONLY, STAGED, SELECTED, RETIRED, INCONSISTENT)
TWO_RELEASE_STATES = (STAGED, SELECTED)
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")

Status = Callable[..., dict]


def _need(condition: bool, reason: str) -> None:
    if not condition:
        raise I.InstallError(reason)


def _releases(old: str, new: str) -> None:
    _need(old == OLD_RELEASE, "E19_OLD_RELEASE_NOT_THE_INSTALLED_RELEASE")
    _need(I.SHA40.fullmatch(new) is not None and new != old, "E19_NEW_RELEASE_INVALID")


# ------------------------------------------------------------------ host reads ---

def unit_facts(system: I.System) -> dict[str, dict[str, str | None]]:
    """`systemctl show` of the three witness units and the two signer units (one call per unit, read-only)."""
    out = {}
    for unit in I.WITNESS_UNITS + I.AUTHORITY_UNITS:
        result = system.run(["/usr/bin/systemctl", "show", "--property=" + ",".join(UNIT_PROPERTIES), "--", unit])
        values = dict(line.split("=", 1) for line in (result.stdout or "").splitlines() if "=" in line)
        out[unit] = {key: values.get(key) for key in UNIT_PROPERTIES}
    return out


def witness_state(units: dict[str, dict[str, str | None]]) -> str:
    """RUNNING, STOPPED or TRANSITIONAL (both sockets must match the service: e19_p1b10_upgrade._service_state)."""
    service = units[WITNESS_SERVICE]
    sockets = (units[OWNER_SOCKET]["ActiveState"], units[SIGNER_SOCKET]["ActiveState"])
    if (service["ActiveState"], service["SubState"]) == ("active", "running") \
            and service["MainPID"] not in (None, "", "0") and sockets == ("active", "active"):
        return "RUNNING"
    if (service["ActiveState"], service["SubState"], service["MainPID"]) == ("inactive", "dead", "0") \
            and sockets == ("inactive", "inactive"):
        return "STOPPED"
    return "TRANSITIONAL"


def process_cwd(system: I.System, pid: str | None) -> str | None:
    if not isinstance(pid, str) or not pid.isdigit() or pid in ("0", "1"):
        return None
    try:
        return os.readlink(system.path(f"/proc/{pid}/cwd"))
    except OSError:
        return None


def manifest_files(system: I.System, sha: str) -> dict[str, str] | None:
    path = system.path(f"{I.RELEASES}/{sha}/{I.MANIFEST}")
    try:
        if path.is_symlink() or not path.is_file():
            return None
        return {item["path"]: item["sha256"] for item in json.loads(path.read_bytes())["files"]}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def delta_failures(old_files: dict[str, str] | None, new_files: dict[str, str] | None) -> list[str]:
    """Record §3.2: the NEW payload differs from OLD in exactly `pr1_acceptance.py`, with exactly the pinned bytes."""
    if old_files is None or new_files is None:
        return ["E19_DELTA_UNOBSERVABLE"]
    if set(old_files) != set(new_files):
        return ["E19_DELTA_FILE_SET"]
    changed = sorted(path for path in new_files if new_files[path] != old_files[path])
    if changed != [DELTA_MEMBER] or (old_files[DELTA_MEMBER], new_files[DELTA_MEMBER]) != (DELTA_OLD_SHA256,
                                                                                            DELTA_NEW_SHA256):
        return ["E19_DELTA_NOT_EXACTLY_PR1_ACCEPTANCE:" + ",".join(changed)]
    return []


def e19_status(system: I.System, old: str, new: str, *, status: Status = I.status) -> dict[str, Any]:
    """Read-only. The closed state of the release layout, judged exactly; anything else is E19_INCONSISTENT."""
    _releases(old, new)
    failures: list[str] = []
    entries = I._release_entries(system)
    shas = [entry for entry in entries if not entry.startswith(".")]
    if len(shas) != len(entries):
        failures.append("STAGING_RESIDUE:" + ",".join(entry for entry in entries if entry.startswith(".")))
    if os.path.lexists(system.path(SELECTOR_TMP)):
        failures.append("SELECTOR_RESIDUE")
    current = system.path(I.CURRENT)
    target = os.readlink(current) if current.is_symlink() else None
    both = tuple(sorted((old, new)))
    state = {((old,), f"releases/{old}"): OLD_ONLY, (both, f"releases/{old}"): STAGED,
             (both, f"releases/{new}"): SELECTED, ((new,), f"releases/{new}"): RETIRED}.get(
        (tuple(sorted(shas)), target), INCONSISTENT)
    trees = {sha: I.release_tree_failures(system, sha) for sha in shas if I.SHA40.fullmatch(sha)}
    failures += [f"TREE:{sha}:" + ",".join(found[:6]) for sha, found in sorted(trees.items()) if found]
    if state in TWO_RELEASE_STATES:
        failures += delta_failures(manifest_files(system, old), manifest_files(system, new))
    if state == RETIRED and (manifest_files(system, new) or {}).get(DELTA_MEMBER) != DELTA_NEW_SHA256:
        failures.append("E19_NEW_RELEASE_NOT_THE_E19_PAYLOAD")
    installer = None
    if state != INCONSISTENT:
        selected = target.split("/", 1)[1]
        report = status(system, INSTALLED_STAGE, selected)
        allowed = {"RELEASE_SET"} if state in TWO_RELEASE_STATES else set()
        installer = {"stage": INSTALLED_STAGE, "releaseSha": selected, "result": report["result"],
                     "failures": list(report["failures"])}
        failures += ["INSTALLER:" + failure for failure in report["failures"] if failure not in allowed]
    units = unit_facts(system)
    witness = witness_state(units)
    return {"schemaVersion": 1, "mode": MODE, "oldRelease": old, "newRelease": new, "state": state,
            "releaseEntries": entries, "currentTarget": target, "installerStatus": installer,
            "witness": witness, "units": units,
            "witnessCwd": process_cwd(system, units[WITNESS_SERVICE]["MainPID"]) if witness == "RUNNING" else None,
            "failures": failures, "result": "PASS" if state != INCONSISTENT and not failures else "FAIL"}


def _require_state(report: dict[str, Any], expected: str) -> None:
    _need(report["state"] == expected and report["result"] == "PASS",
          f"E19_PRE_STATE:{report['state']}:" + ",".join(report["failures"]))


def _post(system: I.System, old: str, new: str, expected: str, mutation: str, status: Status) -> dict[str, Any]:
    report = e19_status(system, old, new, status=status)
    report["mutation"] = mutation
    if report["state"] != expected:
        report["result"] = "FAIL"
        report["failures"].append("E19_POST_STATE:" + report["state"])
    return report


# ------------------------------------------------------------------- mutations ---

def stage_e19_stage(system: I.System, old: str, new: str, manifest_sha256: str, archive: Path, attestation: Path,
                    *, status: Status = I.status) -> dict[str, Any]:
    """STAGE (E19-GO-STAGE): `releases/<NEW>` beside OLD from the verified, attested archive whose manifest is the
    pinned one. `current` and the witness are untouched (U0 -> U1)."""
    I.require_dev_root(system)
    _need(isinstance(manifest_sha256, str) and _HEX64.fullmatch(manifest_sha256) is not None, "E19_MANIFEST_PIN_INVALID")
    _require_state(e19_status(system, old, new, status=status), OLD_ONLY)
    manifest, payloads = I.verify_archive(archive, attestation, new)
    _need(I.digest(I.canonical(manifest)) == manifest_sha256, "E19_MANIFEST_NOT_THE_PINNED_MANIFEST")
    delta = delta_failures(manifest_files(system, old), {item["path"]: item["sha256"] for item in manifest["files"]})
    _need(not delta, "E19_PAYLOAD_DELTA:" + ",".join(delta))
    staging = system.path(f"{I.RELEASES}/.{new}.staging")
    _need(not os.path.lexists(staging), "RELEASE_STAGING_COLLISION")
    staging.mkdir(mode=0o700)
    for relative, data in sorted({**payloads, I.MANIFEST: I.canonical(manifest)}.items()):
        target = staging.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        I._write_new(system, target, data, 0o755 if relative in I.CLI_TARGETS else 0o644)
    system.fixed("/usr/bin/python3", "-m", "venv", str(staging / "venv"))
    system.fixed(str(staging / "venv/bin/python"), "-m", "pip", "install", "--no-index", "--no-input",
                 "--disable-pip-version-check", "--require-hashes", "--find-links", str(staging / "wheels"),
                 "-r", str(staging / "requirements.lock"))
    I._normalize_tree(system, staging)
    system.fixed("/usr/sbin/runuser", "-u", I.SERVICE_USER, "--", str(staging / "venv/bin/python"), "-I", "-B", "-c",
                 "import sys; sys.path.insert(0, sys.argv[1]); import lilith_authority_dev.server, "
                 "lilith_recovery_witness.server, lilith_authority_root.cli", str(staging), cwd=staging)
    staging.rename(system.path(f"{I.RELEASES}/{new}"))
    I._fsync_directory(system, I.RELEASES)
    return _post(system, old, new, STAGED, "STAGED", status)


def stage_e19_select(system: I.System, old: str, new: str, *, status: Status = I.status) -> dict[str, Any]:
    """SELECT (E19-GO-SELECT): `current -> releases/<NEW>` by symlink(tmp) + rename, ONLY while the witness service and
    both sockets are stopped, so the ending incarnation never runs across the selector change (U2 -> U3)."""
    I.require_dev_root(system)
    before = e19_status(system, old, new, status=status)
    _require_state(before, STAGED)
    _need(before["witness"] == "STOPPED", "E19_WITNESS_NOT_STOPPED:" + before["witness"])
    tmp = system.path(SELECTOR_TMP)
    os.symlink(f"releases/{new}", tmp)
    if system.chown:
        os.lchown(tmp, 0, 0)
    os.rename(tmp, system.path(I.CURRENT))
    I._fsync_directory(system, I.OPT)
    return _post(system, old, new, SELECTED, "SELECTED", status)


def stage_e19_retire_old(system: I.System, old: str, new: str, invocation: str, *,
                         status: Status = I.status) -> dict[str, Any]:
    """RETIRE (E19-GO-RETIRE): remove `releases/<OLD>` only while the replacement incarnation the owner accepted
    (POST9A-R and the local acceptance, checked by the operator) runs from `releases/<NEW>` (U4 -> U5). The POST is
    the unchanged installer `status --expect P1B-10 <NEW>`, single release restored."""
    I.require_dev_root(system)
    _need(isinstance(invocation, str) and _HEX32.fullmatch(invocation) is not None
          and invocation != ENDING_INVOCATION, "E19_REPLACEMENT_INVOCATION_INVALID")
    before = e19_status(system, old, new, status=status)
    _require_state(before, SELECTED)
    service = before["units"][WITNESS_SERVICE]
    _need(before["witness"] == "RUNNING" and service["InvocationID"] == invocation and service["NRestarts"] == "0",
          "E19_ACCEPTED_REPLACEMENT_NOT_RUNNING")
    _need(before["witnessCwd"] == f"{I.RELEASES}/{new}", "E19_REPLACEMENT_NOT_ON_NEW")
    doomed = system.path(f"{I.RELEASES}/{old}")
    _need(not doomed.is_symlink() and doomed.is_dir(), "RETIRE_TARGET_UNSAFE")
    shutil.rmtree(doomed)
    I._fsync_directory(system, I.RELEASES)
    return _post(system, old, new, RETIRED, "RETIRED", status)


def main(argv: list[str], system: I.System | None = None) -> int:
    system = system or I.System()
    try:
        form, rest = (argv[0], argv[1:]) if argv else ("", [])
        if form == "e19-status" and len(rest) == 2:
            I.require_dev_root(system)
            report = e19_status(system, rest[0], rest[1])
        elif form == "e19-stage" and len(rest) == 5:
            report = stage_e19_stage(system, rest[0], rest[1], rest[2], Path(rest[3]), Path(rest[4]))
        elif form == "e19-select" and len(rest) == 2:
            report = stage_e19_select(system, rest[0], rest[1])
        elif form == "e19-retire-old" and len(rest) == 3:
            report = stage_e19_retire_old(system, rest[0], rest[1], rest[2])
        else:
            raise I.InstallError("USAGE")
    except I.InstallError as exc:
        print(f"e19_release_stages: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
