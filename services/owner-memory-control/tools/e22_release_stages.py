#!/usr/bin/env python3
"""15B2b-B1b-3e M-B12: the release stages and V-phase status of `UPGRADE_E22_JUDGE_DEV_SYNTHETIC` (SOURCE ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-e22-judge-transition.md. No form below is authorized by the repository;
every mutating form needs its own owner go (the laptop operator, a later slice).

It follows the accepted E-19 stage tool (`e19_release_stages.py`, unchanged) and reuses its host reads (`unit_facts`,
`witness_state`, `process_cwd`, `manifest_files`, the selector temp path) and the byte-unchanged installer
`install_authority_dev.py` (archive verification, release-tree check, write helpers, `status`). It differs from E-19
in one way only: the signer is RUNNING and imports the judge from `current`, so SELECT needs the signer stopped too,
and RETIRE needs both accepted replacement incarnations running from NEW (contract `e22_judge_upgrade`, V0 … V7):

    E22_OLD_ONLY      {OLD}       current -> OLD     (V0)
    E22_NEW_STAGED    {OLD, NEW}  current -> OLD     (V1, V2, V3)
    E22_NEW_SELECTED  {OLD, NEW}  current -> NEW     (V4, V5, V6)
    E22_OLD_RETIRED   {NEW}       current -> NEW     (V7)

Forms (root on DEV):

    e22-status <OLD> <NEW>                                            read-only; the layout state and the V-phase
    e22-stage <OLD> <NEW> <manifest-sha256> <archive> <attestation>   E22_OLD_ONLY -> E22_NEW_STAGED       (V0 -> V1)
    e22-select <OLD> <NEW>                                            E22_NEW_STAGED -> E22_NEW_SELECTED   (V3 -> V4)
    e22-retire-old <OLD> <NEW> <signer-invocation> <witness-invocation>  E22_NEW_SELECTED -> E22_OLD_RETIRED (V6 -> V7)

Each mutating form refuses unless its exact pre-state holds, never overwrites, and never retries, repairs, rolls back,
reloads, starts or stops a unit, loads a credential or touches custody, HELD, the ledger or the witness state. The
signer and witness stop / start commands are the contract's reviewed commands, issued by the operator, never here.

    status != classification != permission;  a running replacement != an accepted replacement (owner statement)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

import e19_release_stages as S19  # noqa: E402  (reused host reads; the accepted E-19 tool, unchanged)
import e22_judge_upgrade as J  # noqa: E402  (the one-member contract)
import install_authority_dev as I  # noqa: E402

MODE = J.MODE
OLD_RELEASE = J.OLD_RELEASE
(DELTA_MEMBER, (DELTA_OLD_SHA256, DELTA_NEW_SHA256)), = J.PAYLOAD_DELTA.items()
INSTALLED_STAGE = S19.INSTALLED_STAGE
SIGNER_SERVICE, SIGNER_SOCKET = I.AUTHORITY_UNITS
WITNESS_SERVICE = I.WITNESS_UNITS[0]

OLD_ONLY = "E22_OLD_ONLY"
STAGED = "E22_NEW_STAGED"
SELECTED = "E22_NEW_SELECTED"
RETIRED = "E22_OLD_RETIRED"
INCONSISTENT = "E22_INCONSISTENT"
TWO_RELEASE_STATES = (STAGED, SELECTED)
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
# Phase classification outcomes other than V0 … V7 (STOP: owner adjudication; never repaired here).
STOP_UNKNOWN = "VS_UNKNOWN"
STOP_ACROSS_SELECT = "VS_UNIT_RUNNING_FROM_OLD_AFTER_SELECT"
STOP_RETIRED_TREE = "VS_UNIT_ON_RETIRED_RELEASE"
STOP_TRANSITIONAL = "VS_UNIT_TRANSITIONAL"
STOP_RESTARTED = "VS_ENDING_INCARNATION_CHANGED"
STOP_INCONSISTENT = "VS_LAYOUT_INCONSISTENT"
# The installer `status --expect P1B-10` predates the signer start (M-B11): it reports the running signer's own facts
# as failures. Exactly these, and only while the signer is RUNNING, are the accepted state (V0, V1, V6, V7; the
# signer itself is judged by W11). Any other installer failure stays a STOP.
SIGNER_RUNNING_INSTALLER_FAILURES = frozenset({"UNEXPECTED_PRESENT:/run/credentials/" + SIGNER_SERVICE,
                                               "UNIT_ACTIVE:" + SIGNER_SERVICE, "UNIT_ACTIVE:" + SIGNER_SOCKET})

Status = Callable[..., dict]


def _need(condition: bool, reason: str) -> None:
    if not condition:
        raise I.InstallError(reason)


def _releases(old: str, new: str) -> None:
    _need(old == OLD_RELEASE, "E22_OLD_RELEASE_NOT_THE_INSTALLED_RELEASE")
    _need(I.SHA40.fullmatch(new) is not None and new != old, "E22_NEW_RELEASE_INVALID")
    _need(J.NEW_RELEASE is None or new == J.NEW_RELEASE, "E22_NEW_RELEASE_NOT_THE_PINNED_RELEASE")


def signer_state(units: Mapping[str, Mapping[str, str | None]]) -> str:
    """RUNNING, STOPPED or TRANSITIONAL for the signer service and its socket (the witness rule of E-19)."""
    service, socket = units[SIGNER_SERVICE], units[SIGNER_SOCKET]["ActiveState"]
    if (service["ActiveState"], service["SubState"]) == ("active", "running") \
            and service["MainPID"] not in (None, "", "0") and socket == "active":
        return "RUNNING"
    if (service["ActiveState"], service["SubState"], service["MainPID"]) == ("inactive", "dead", "0") \
            and socket == "inactive":
        return "STOPPED"
    return "TRANSITIONAL"


def delta_failures(old_files: dict[str, str] | None, new_files: dict[str, str] | None) -> list[str]:
    """The NEW payload differs from OLD in exactly the judge, with exactly the pinned bytes (contract PAYLOAD_DELTA)."""
    if old_files is None or new_files is None:
        return ["E22_DELTA_UNOBSERVABLE"]
    if set(old_files) != set(new_files):
        return ["E22_DELTA_FILE_SET"]
    changed = sorted(path for path in new_files if new_files[path] != old_files[path])
    if changed != [DELTA_MEMBER] or (old_files[DELTA_MEMBER], new_files[DELTA_MEMBER]) != (DELTA_OLD_SHA256,
                                                                                            DELTA_NEW_SHA256):
        return ["E22_DELTA_NOT_EXACTLY_THE_JUDGE:" + ",".join(changed)]
    return []


def e22_status(system: I.System, old: str, new: str, *, status: Status = I.status) -> dict[str, Any]:
    """Read-only. The closed release-layout state, both units and their working trees, and the V-phase."""
    _releases(old, new)
    failures: list[str] = []
    entries = I._release_entries(system)
    shas = [entry for entry in entries if not entry.startswith(".")]
    if len(shas) != len(entries):
        failures.append("STAGING_RESIDUE:" + ",".join(entry for entry in entries if entry.startswith(".")))
    if os.path.lexists(system.path(S19.SELECTOR_TMP)):
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
        failures += delta_failures(S19.manifest_files(system, old), S19.manifest_files(system, new))
    if state == RETIRED and (S19.manifest_files(system, new) or {}).get(DELTA_MEMBER) != DELTA_NEW_SHA256:
        failures.append("E22_NEW_RELEASE_NOT_THE_JUDGE_PAYLOAD")
    units = S19.unit_facts(system)
    signer, witness = signer_state(units), S19.witness_state(units)
    installer = None
    if state != INCONSISTENT:
        selected = target.split("/", 1)[1]
        report = status(system, INSTALLED_STAGE, selected)
        allowed = {"RELEASE_SET"} if state in TWO_RELEASE_STATES else set()
        if signer == "RUNNING":
            allowed |= SIGNER_RUNNING_INSTALLER_FAILURES
        installer = {"stage": INSTALLED_STAGE, "releaseSha": selected, "result": report["result"],
                     "failures": list(report["failures"])}
        failures += ["INSTALLER:" + failure for failure in report["failures"] if failure not in allowed]
    report = {"schemaVersion": 1, "mode": MODE, "oldRelease": old, "newRelease": new, "state": state,
              "releaseEntries": entries, "currentTarget": target, "installerStatus": installer,
              "signer": signer, "witness": witness, "units": units,
              "signerCwd": S19.process_cwd(system, units[SIGNER_SERVICE]["MainPID"]) if signer == "RUNNING" else None,
              "witnessCwd": S19.process_cwd(system, units[WITNESS_SERVICE]["MainPID"]) if witness == "RUNNING" else None,
              "failures": failures, "result": "PASS" if state != INCONSISTENT and not failures else "FAIL"}
    report["phase"] = phase(report)
    return report


def _unit(report: Mapping[str, Any], kind: str) -> tuple[str, str | None, str | None]:
    """(state, release the unit runs from, `ending` | `replacement` | None) for `signer` or `witness`."""
    state = report[kind]
    if state != "RUNNING":
        return state, None, None
    cwd = report[f"{kind}Cwd"] or ""
    release = next((r for r in (report["oldRelease"], report["newRelease"]) if cwd == f"{I.RELEASES}/{r}"), None)
    service = report["units"][SIGNER_SERVICE if kind == "signer" else WITNESS_SERVICE]
    ending = J.ENDING_SIGNER_INCARNATION if kind == "signer" else J.ENDING_WITNESS_INCARNATION
    if (service["InvocationID"], service["MainPID"]) == ending and service["NRestarts"] == "0":
        identity = "ending"
    elif service["InvocationID"] != ending[0] and service["NRestarts"] == "0":
        identity = "replacement"
    else:
        identity = None
    return state, release, identity


def phase(report: Mapping[str, Any]) -> str:
    """The V-phase of one status report (contract `PHASE_STATE`), or a STOP. Never a permission."""
    if report["state"] == INCONSISTENT or report["failures"]:
        return STOP_INCONSISTENT
    units = {kind: _unit(report, kind) for kind in ("signer", "witness")}
    if any(state == "TRANSITIONAL" for state, _r, _i in units.values()):
        return STOP_TRANSITIONAL
    old, new = report["oldRelease"], report["newRelease"]
    for state, release, identity in units.values():
        if state != "RUNNING":
            continue
        if release is None:
            return STOP_RETIRED_TREE
        if report["state"] in (SELECTED, RETIRED) and release == old:
            return STOP_ACROSS_SELECT
        if identity is None or (release == old) != (identity == "ending"):
            return STOP_RESTARTED
    shape = {kind: (None if state == "STOPPED" else ("OLD" if release == old else "NEW"))
             for kind, (state, release, _i) in units.items()}
    selector = "OLD" if report["state"] in (OLD_ONLY, STAGED) else "NEW"
    releases = ("OLD",) if report["state"] == OLD_ONLY else ("NEW",) if report["state"] == RETIRED else ("OLD", "NEW")
    for name, (want_releases, want_selector, want_signer, want_witness) in J.PHASE_STATE.items():
        if (releases, selector, shape["signer"], shape["witness"]) == (want_releases, want_selector, want_signer,
                                                                        want_witness):
            return name
    return STOP_UNKNOWN


def _require(report: Mapping[str, Any], expected_phase: str) -> None:
    _need(report["result"] == "PASS" and report["phase"] == expected_phase,
          f"E22_PRE_PHASE:{report['phase']}:" + ",".join(report["failures"]))


def _post(system: I.System, old: str, new: str, expected_state: str, mutation: str, status: Status) -> dict[str, Any]:
    report = e22_status(system, old, new, status=status)
    report["mutation"] = mutation
    if report["state"] != expected_state:
        report["result"] = "FAIL"
        report["failures"].append("E22_POST_STATE:" + report["state"])
    return report


# ------------------------------------------------------------------- mutations ---

def stage_e22_stage(system: I.System, old: str, new: str, manifest_sha256: str, archive: Path, attestation: Path,
                    *, status: Status = I.status) -> dict[str, Any]:
    """STAGE (V0 -> V1): `releases/<NEW>` beside OLD from the verified, attested archive whose manifest is the pinned
    one and whose payload differs from OLD in exactly the judge. `current`, the signer and the witness are untouched.
    The body is the E-19 stage (installer archive verification, O_EXCL writes, offline venv, import check)."""
    I.require_dev_root(system)
    _need(isinstance(manifest_sha256, str) and _HEX64.fullmatch(manifest_sha256) is not None
          and (J.NEW_MANIFEST_SHA256 is None or manifest_sha256 == J.NEW_MANIFEST_SHA256), "E22_MANIFEST_PIN_INVALID")
    _require(e22_status(system, old, new, status=status), J.V0)
    manifest, payloads = I.verify_archive(archive, attestation, new)
    _need(I.digest(I.canonical(manifest)) == manifest_sha256, "E22_MANIFEST_NOT_THE_PINNED_MANIFEST")
    delta = delta_failures(S19.manifest_files(system, old), {item["path"]: item["sha256"] for item in manifest["files"]})
    _need(not delta, "E22_PAYLOAD_DELTA:" + ",".join(delta))
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


def stage_e22_select(system: I.System, old: str, new: str, *, status: Status = I.status) -> dict[str, Any]:
    """SELECT (V3 -> V4): `current -> releases/<NEW>` by symlink(tmp) + rename, ONLY while the signer AND the witness
    (service and sockets) are stopped, so neither ending incarnation runs across the selector change."""
    I.require_dev_root(system)
    before = e22_status(system, old, new, status=status)
    _require(before, J.V3)
    tmp = system.path(S19.SELECTOR_TMP)
    os.symlink(f"releases/{new}", tmp)
    if system.chown:
        os.lchown(tmp, 0, 0)
    os.rename(tmp, system.path(I.CURRENT))
    I._fsync_directory(system, I.OPT)
    return _post(system, old, new, SELECTED, "SELECTED", status)


def stage_e22_retire_old(system: I.System, old: str, new: str, signer_invocation: str, witness_invocation: str, *,
                         status: Status = I.status) -> dict[str, Any]:
    """RETIRE (V6 -> V7): remove `releases/<OLD>` only while BOTH replacement incarnations the owner accepted (named in
    the go) run from `releases/<NEW>`, NRestarts 0."""
    I.require_dev_root(system)
    for invocation, ending in ((signer_invocation, J.ENDING_SIGNER_INCARNATION),
                               (witness_invocation, J.ENDING_WITNESS_INCARNATION)):
        _need(isinstance(invocation, str) and _HEX32.fullmatch(invocation) is not None and invocation != ending[0],
              "E22_REPLACEMENT_INVOCATION_INVALID")
    before = e22_status(system, old, new, status=status)
    _require(before, J.V6)
    _need(before["units"][SIGNER_SERVICE]["InvocationID"] == signer_invocation
          and before["units"][WITNESS_SERVICE]["InvocationID"] == witness_invocation,
          "E22_ACCEPTED_REPLACEMENTS_NOT_RUNNING")
    doomed = system.path(f"{I.RELEASES}/{old}")
    _need(not doomed.is_symlink() and doomed.is_dir(), "RETIRE_TARGET_UNSAFE")
    shutil.rmtree(doomed)
    I._fsync_directory(system, I.RELEASES)
    return _post(system, old, new, RETIRED, "RETIRED", status)


def main(argv: list[str], system: I.System | None = None) -> int:
    system = system or I.System()
    try:
        form, rest = (argv[0], argv[1:]) if argv else ("", [])
        if form == "e22-status" and len(rest) == 2:
            I.require_dev_root(system)
            report = e22_status(system, rest[0], rest[1])
        elif form == "e22-stage" and len(rest) == 5:
            report = stage_e22_stage(system, rest[0], rest[1], rest[2], Path(rest[3]), Path(rest[4]))
        elif form == "e22-select" and len(rest) == 2:
            report = stage_e22_select(system, rest[0], rest[1])
        elif form == "e22-retire-old" and len(rest) == 4:
            report = stage_e22_retire_old(system, rest[0], rest[1], rest[2], rest[3])
        else:
            raise I.InstallError("USAGE")
    except I.InstallError as exc:
        print(f"e22_release_stages: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
