#!/usr/bin/env python3
"""OWNER_PROD P3: the release stages and F-phase status of `UPGRADE_OWNER_PROD_PROFILE_DEV_SYNTHETIC` (DEV only).

Record: docs/architecture/canonical-memory-p3-dev-transition.md. SOURCE ONLY: no form below is authorized by the
repository; every mutating form needs its own owner go (`owner_prod_operator`).

It is the accepted FM-2 stage tool (`fm2_release_stages.py`, unchanged) moved to the P3 contract
(`owner_prod_signer_upgrade`); `tests/owner_prod_transform.py` is the complete difference. Host reads, the signer
rule, the installer allowance, the V1 installer, the K-PAN / witness-unit / anchor STOPs and the order are FM-2's:

1. the payload delta is the contract's 18 changed members (archive layout v3 = FM-2's, no added member);
2. the ending incarnations are the FM-2 owner-accepted signer and witness;
3. there is NO witness-units step and the Privacy anchor directory is reported, never written (as FM-2).

Both units stop before the select (a unit running from OLD after the select is a STOP); the witness, two of whose
members change, starts again from NEW, then the signer. The DEV host has no `deployment.json`, so both keep
DEV_SYNTHETIC; this tool never reads or writes PROD authority, keys or paths.

    F0_OLD_EXACT            {OLD}       current -> OLD   signer OLD   witness OLD
    F1_NEW_STAGED           {OLD, NEW}  current -> OLD   signer OLD   witness OLD
    F2_SIGNER_STOPPED       {OLD, NEW}  current -> OLD   -            witness OLD
    F3_WITNESS_STOPPED      {OLD, NEW}  current -> OLD   -            -
    F4_NEW_SELECTED         {OLD, NEW}  current -> NEW   -            -
    F5_WITNESS_RUNNING      {OLD, NEW}  current -> NEW   -            witness NEW
    F6_SIGNER_RUNNING       {OLD, NEW}  current -> NEW   signer NEW   witness NEW
    F7_OLD_RETIRED          {NEW}       current -> NEW   signer NEW   witness NEW

Forms (root on DEV):

    p3-status <OLD> <NEW>                                            read-only; layout, units, credentials, F-phase
    p3-stage <OLD> <NEW> <manifest-sha256> <archive> <attestation>   F0 -> F1
    p3-select <OLD> <NEW>                                            F3 -> F4
    p3-retire-old <OLD> <NEW> <signer-invocation> <witness-invocation>  F6 -> F7

Each mutating form refuses unless its exact pre-phase holds, never overwrites a release, and never retries, repairs,
rolls back, starts or stops a unit, reloads systemd, generates, reads or moves a credential, or touches custody, HELD,
the ledger, the witness state or the anchor chain. Credentials are judged by metadata only (lstat).

    status != classification != permission;  a running replacement != an accepted replacement (owner statement)
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

import e19_release_stages as S19  # noqa: E402  (reused host reads; the accepted E-19 tool, unchanged)
import e22_release_stages as S22  # noqa: E402  (reused signer rule and installer allowance; unchanged)
import e23_privacy_anchor_upgrade as E23  # noqa: E402  (the E-23 contract: K-PAN and anchor names)
import e23_release_stages as S23  # noqa: E402  (reused host reads; the accepted E-23 tool, unchanged)
import owner_prod_signer_upgrade as P3  # noqa: E402  (this transition's contract)
import install_authority_dev as I  # noqa: E402  (the accepted installer V1, byte-unchanged)

MODE = P3.MODE
OLD_RELEASE = P3.OLD_RELEASE
INSTALLED_STAGE = S19.INSTALLED_STAGE
SIGNER_SERVICE, SIGNER_SOCKET = I.AUTHORITY_UNITS
WITNESS_SERVICE, OWNER_SOCKET, WITNESS_SIGNER_SOCKET = I.WITNESS_UNITS
# The incarnations this transition ends: the FM-2 owner-accepted replacements (record
# personal-memory-fm2-dev-activation §7).
ENDING_SIGNER_INCARNATION = ("c32457250aff4155bce1f54f1648945f", "309023")
ENDING_WITNESS_INCARNATION = ("1089ad88e0eb4c55b167a48cdb898aa1", "308690")
KWIT_BLOB, KPAN_BLOB, CREDENTIAL_DIR = S23.KWIT_BLOB, S23.KPAN_BLOB, S23.CREDENTIAL_DIR
ANCHOR_DIR, ANCHOR_NAMES = S23.ANCHOR_DIR, S23.ANCHOR_NAMES
WITNESS_RUNTIME_CREDENTIALS, SIGNER_RUNTIME_CREDENTIALS = S23.WITNESS_RUNTIME_CREDENTIALS, S23.SIGNER_RUNTIME_CREDENTIALS
WITNESS_CREDENTIALS = S23.WITNESS_CREDENTIALS_NEW               # K-WIT + K-PAN, as the installed witness unit loads
FOREIGN_UNITS = S23.FOREIGN_UNITS

OLD_ONLY, STAGED, SELECTED, RETIRED, INCONSISTENT = (
    "P3_OLD_ONLY", "P3_NEW_STAGED", "P3_NEW_SELECTED", "P3_OLD_RETIRED", "P3_INCONSISTENT")
TWO_RELEASE_STATES = (STAGED, SELECTED)
F0, F1, F2, F3, F4, F5, F6, F7 = (
    "F0_OLD_EXACT", "F1_NEW_STAGED", "F2_SIGNER_STOPPED", "F3_WITNESS_STOPPED", "F4_NEW_SELECTED",
    "F5_WITNESS_RUNNING", "F6_SIGNER_RUNNING", "F7_OLD_RETIRED")
PHASES = (F0, F1, F2, F3, F4, F5, F6, F7)
# phase -> (installed releases, selector, signer running from, witness running from); None = stopped.
PHASE_STATE = {
    F0: (("OLD",), "OLD", "OLD", "OLD"),
    F1: (("OLD", "NEW"), "OLD", "OLD", "OLD"),
    F2: (("OLD", "NEW"), "OLD", None, "OLD"),
    F3: (("OLD", "NEW"), "OLD", None, None),
    F4: (("OLD", "NEW"), "NEW", None, None),
    F5: (("OLD", "NEW"), "NEW", None, "NEW"),
    F6: (("OLD", "NEW"), "NEW", "NEW", "NEW"),
    F7: (("NEW",), "NEW", "NEW", "NEW"),
}
STOP_UNKNOWN = "FS_UNKNOWN"
STOP_ACROSS_SELECT = "FS_UNIT_RUNNING_FROM_OLD_AFTER_SELECT"
STOP_RETIRED_TREE = "FS_UNIT_ON_RETIRED_RELEASE"
STOP_TRANSITIONAL = "FS_UNIT_TRANSITIONAL"
STOP_RESTARTED = "FS_ENDING_INCARNATION_CHANGED"
STOP_INCONSISTENT = "FS_LAYOUT_INCONSISTENT"
STOP_UNITS = "FS_WITNESS_UNITS_NOT_INSTALLED_EXACT"       # not the E-23 NEW bytes, reload pending, or anchor dir wrong
STOP_KPAN = "FS_KPAN_CREDENTIAL_NOT_EXACT"
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")

Status = Callable[..., dict]


def _need(condition: bool, reason: str) -> None:
    if not condition:
        raise I.InstallError(reason)


def _releases(old: str, new: str) -> None:
    _need(old == OLD_RELEASE, "P3_OLD_RELEASE_NOT_THE_INSTALLED_RELEASE")
    _need(isinstance(new, str) and I.SHA40.fullmatch(new) is not None and new != old, "P3_NEW_RELEASE_INVALID")
    _need(new == P3.NEW_RELEASE, "P3_NEW_RELEASE_NOT_THE_PINNED_RELEASE")


@contextlib.contextmanager
def layout_v3() -> Iterator[None]:
    """Archive layout v3 (`install_authority_dev_v3._layout_v3`): V1 with the E-23 and the FM-1 added members, bound
    for the call. Not imported: V2 / V3 put their own directory on sys.path, which under the BOOT bundle would be the
    remote working directory (a test proves the bindings agree)."""
    saved = I.EXPECTED_PATHS
    I.EXPECTED_PATHS = saved | frozenset(E23.PAYLOAD_ADDED) | frozenset(P3.LAYOUT_ADDED)
    try:
        yield
    finally:
        I.EXPECTED_PATHS = saved


# ------------------------------------------------------------------ host reads ---

def anchor_facts(system: I.System) -> dict[str, Any]:
    """The Privacy anchor directory: its names (a subset of the anchor service's) and the SHA-256 of each chain file
    (public signed anchors). The operator requires these unchanged from the preflight; this tool never writes them."""
    names = S23._names(system, ANCHOR_DIR)
    chain = S23._names(system, f"{ANCHOR_DIR}/chain") if names and "chain" in names else []
    digests = None if chain is None else {
        name: hashlib.sha256(system.path(f"{ANCHOR_DIR}/chain/{name}").read_bytes()).hexdigest() for name in chain}
    return {"names": names, "chain": digests, "exact": names is not None and set(names) <= ANCHOR_NAMES
            and digests is not None}


def delta_failures(old_files: dict[str, str] | None, new_files: dict[str, str] | None) -> list[str]:
    """NEW = OLD moved by exactly the contract delta (`new_payload_pins`): 18 changed, none added or removed."""
    if old_files is None or new_files is None:
        return ["P3_DELTA_UNOBSERVABLE"]
    try:
        expected = P3.new_payload_pins(old_files)
    except P3.Refused as exc:
        return ["P3_DELTA_OLD:" + str(exc)]
    if expected != new_files:
        return ["P3_DELTA_NOT_EXACT:" + ",".join(sorted(p for p in set(expected) | set(new_files)
                                                         if expected.get(p) != new_files.get(p))[:6])]
    return []


def _allowed_installer_failures(state: str, signer: str, kpan: str, credentials: list[str] | None) -> set[str]:
    allowed = {"RELEASE_SET"} if state in TWO_RELEASE_STATES else set()
    if signer == "RUNNING":
        allowed |= S22.SIGNER_RUNNING_INSTALLER_FAILURES
    if kpan == "PRESENT_EXACT" and credentials == S23.CREDENTIAL_NAMES_WITH_KPAN:
        allowed.add("LISTING:" + CREDENTIAL_DIR)                  # the installer predates K-PAN: exactly this one name
    return allowed


def p3_status(system: I.System, old: str, new: str, *, status: Status = I.status) -> dict[str, Any]:
    """Read-only. The closed release-layout state, both units, the witness host files, the K-PAN / K-WIT credential
    metadata, the anchor directory, the foreign units, the processes using OLD, and the F-phase."""
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
    trees = {sha: I.release_tree_failures(system, sha) for sha in shas if I.SHA40.fullmatch(sha)}   # own manifest
    failures += [f"TREE:{sha}:" + ",".join(found[:6]) for sha, found in sorted(trees.items()) if found]
    if state in TWO_RELEASE_STATES:
        failures += delta_failures(S19.manifest_files(system, old), S19.manifest_files(system, new))
    new_manifest = I._file_sha(system, f"{I.RELEASES}/{new}/{I.MANIFEST}") if new in shas else None
    if new in shas and new_manifest != P3.NEW_MANIFEST_SHA256:
        failures.append("P3_NEW_MANIFEST_NOT_THE_PIN")
    units = S19.unit_facts(system)
    reload_pending = S23._unit_show(system, WITNESS_SERVICE, ("NeedDaemonReload",))["NeedDaemonReload"]
    signer, witness = S22.signer_state(units), S19.witness_state(units)
    host_units = S23.witness_units_state(system, reload_pending)            # "NEW" = the installed E-23 NEW bytes
    kpan, credentials = S23.kpan_state(system), S23._names(system, CREDENTIAL_DIR)
    installer = None
    if state != INCONSISTENT:
        selected = target.split("/", 1)[1]
        report = status(system, INSTALLED_STAGE, selected)
        allowed = _allowed_installer_failures(state, signer, kpan, credentials)
        installer = {"stage": INSTALLED_STAGE, "releaseSha": selected, "result": report["result"],
                     "failures": list(report["failures"])}
        failures += ["INSTALLER:" + failure for failure in report["failures"] if failure not in allowed]
    report = {"schemaVersion": 1, "mode": MODE, "oldRelease": old, "newRelease": new, "state": state,
              "releaseEntries": entries, "currentTarget": target, "newManifestSha256": new_manifest,
              "installerStatus": installer, "signer": signer, "witness": witness, "units": units,
              "signerCwd": S19.process_cwd(system, units[SIGNER_SERVICE]["MainPID"]) if signer == "RUNNING" else None,
              "witnessCwd": S19.process_cwd(system, units[WITNESS_SERVICE]["MainPID"]) if witness == "RUNNING" else None,
              "witnessUnits": host_units, "witnessReloadPending": reload_pending,
              "kPan": kpan, "kPanMeta": S23.path_meta(system, KPAN_BLOB), "kWitMeta": S23.path_meta(system, KWIT_BLOB),
              "credentialNames": credentials, "anchor": anchor_facts(system),
              "witnessCredentials": S23._names(system, WITNESS_RUNTIME_CREDENTIALS) if witness == "RUNNING" else None,
              "signerCredentials": S23._names(system, SIGNER_RUNTIME_CREDENTIALS) if signer == "RUNNING" else None,
              "oldReleaseUsers": S23.release_users(system, old) if old in shas else [],
              "foreignUnits": S23.foreign_units(system),
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
    ending = ENDING_SIGNER_INCARNATION if kind == "signer" else ENDING_WITNESS_INCARNATION
    if (service["InvocationID"], service["MainPID"]) == ending and service["NRestarts"] == "0":
        identity = "ending"
    elif service["InvocationID"] != ending[0] and service["NRestarts"] == "0":
        identity = "replacement"
    else:
        identity = None
    return state, release, identity


def phase(report: Mapping[str, Any]) -> str:
    """The F-phase of one status report (`PHASE_STATE`), or a STOP. Never a permission."""
    if report["state"] == INCONSISTENT:
        return STOP_INCONSISTENT
    if report["kPan"] != "PRESENT_EXACT":                      # the installed witness unit loads K-PAN in every phase
        return STOP_KPAN
    if report["witnessUnits"] != "NEW" or not report["anchor"]["exact"]:
        return STOP_UNITS
    if report["failures"]:
        return STOP_INCONSISTENT
    units = {kind: _unit(report, kind) for kind in ("signer", "witness")}
    if any(state == "TRANSITIONAL" for state, _r, _i in units.values()):
        return STOP_TRANSITIONAL
    old = report["oldRelease"]
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
    return next((name for name, want in PHASE_STATE.items()
                 if (releases, selector, shape["signer"], shape["witness"]) == want), STOP_UNKNOWN)


def _require(report: Mapping[str, Any], expected_phase: str) -> None:
    _need(report["result"] == "PASS" and report["phase"] == expected_phase,
          f"P3_PRE_PHASE:{report['phase']}:" + ",".join(report["failures"]))


def _post(system: I.System, old: str, new: str, expected_phase: str, mutation: str, status: Status) -> dict[str, Any]:
    report = p3_status(system, old, new, status=status)
    report["mutation"] = mutation
    if report["phase"] != expected_phase:
        report["result"] = "FAIL"
        report["failures"].append("P3_POST_PHASE:" + report["phase"])
    return report


# ------------------------------------------------------------------- mutations ---

def stage_p3_stage(system: I.System, old: str, new: str, manifest_sha256: str, archive: Path, attestation: Path,
                    *, status: Status = I.status) -> dict[str, Any]:
    """STAGE (F0 -> F1): `releases/<NEW>` beside OLD from the verified, attested archive whose manifest is the pinned
    one and whose payload is OLD moved by exactly the contract delta. The body is the E-23 stage."""
    I.require_dev_root(system)
    _need(isinstance(manifest_sha256, str) and _HEX64.fullmatch(manifest_sha256) is not None
          and manifest_sha256 == P3.NEW_MANIFEST_SHA256, "P3_MANIFEST_PIN_INVALID")
    _require(p3_status(system, old, new, status=status), F0)
    with layout_v3():
        manifest, payloads = I.verify_archive(archive, attestation, new)
    _need(I.digest(I.canonical(manifest)) == manifest_sha256, "P3_MANIFEST_NOT_THE_PINNED_MANIFEST")
    delta = delta_failures(S19.manifest_files(system, old), {item["path"]: item["sha256"] for item in manifest["files"]})
    _need(not delta, "P3_PAYLOAD_DELTA:" + ",".join(delta))
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
                 "lilith_authority_dev.issuance, lilith_recovery_witness.server, "
                 "lilith_recovery_witness.privacy_anchor, lilith_authority_root.cli",
                 str(staging), cwd=staging)
    staging.rename(system.path(f"{I.RELEASES}/{new}"))
    I._fsync_directory(system, I.RELEASES)
    return _post(system, old, new, F1, "STAGED", status)


def stage_p3_select(system: I.System, old: str, new: str, *, status: Status = I.status) -> dict[str, Any]:
    """SELECT (F3 -> F4): `current -> releases/<NEW>` by symlink(tmp) + rename, ONLY while the signer AND the witness
    (service and sockets) are stopped, so neither ending incarnation runs (or restarts) across the selector change."""
    I.require_dev_root(system)
    _require(p3_status(system, old, new, status=status), F3)
    tmp = system.path(S19.SELECTOR_TMP)
    os.symlink(f"releases/{new}", tmp)
    if system.chown:
        os.lchown(tmp, 0, 0)
    os.rename(tmp, system.path(I.CURRENT))
    I._fsync_directory(system, I.OPT)
    return _post(system, old, new, F4, "SELECTED", status)


def stage_p3_retire_old(system: I.System, old: str, new: str, signer_invocation: str, witness_invocation: str, *,
                         status: Status = I.status) -> dict[str, Any]:
    """RETIRE (F6 -> F7): remove `releases/<OLD>` only while BOTH replacement incarnations the owner accepted (named in
    the go) run from `releases/<NEW>`, NRestarts 0, and no process at all still uses OLD."""
    I.require_dev_root(system)
    for invocation, ending in ((signer_invocation, ENDING_SIGNER_INCARNATION),
                               (witness_invocation, ENDING_WITNESS_INCARNATION)):
        _need(isinstance(invocation, str) and _HEX32.fullmatch(invocation) is not None and invocation != ending[0],
              "P3_REPLACEMENT_INVOCATION_INVALID")
    before = p3_status(system, old, new, status=status)
    _require(before, F6)
    _need(before["units"][SIGNER_SERVICE]["InvocationID"] == signer_invocation
          and before["units"][WITNESS_SERVICE]["InvocationID"] == witness_invocation,
          "P3_ACCEPTED_REPLACEMENTS_NOT_RUNNING")
    users = S23.release_users(system, old)
    _need(not users, "P3_OLD_RELEASE_IN_USE:" + ",".join(users))
    doomed = system.path(f"{I.RELEASES}/{old}")
    _need(not doomed.is_symlink() and doomed.is_dir(), "RETIRE_TARGET_UNSAFE")
    shutil.rmtree(doomed)
    I._fsync_directory(system, I.RELEASES)
    return _post(system, old, new, F7, "RETIRED", status)


def main(argv: list[str], system: I.System | None = None) -> int:
    system = system or I.System()
    try:
        form, rest = (argv[0], argv[1:]) if argv else ("", [])
        if form == "p3-status" and len(rest) == 2:
            I.require_dev_root(system)
            report = p3_status(system, rest[0], rest[1])
        elif form == "p3-stage" and len(rest) == 5:
            report = stage_p3_stage(system, rest[0], rest[1], rest[2], Path(rest[3]), Path(rest[4]))
        elif form == "p3-select" and len(rest) == 2:
            report = stage_p3_select(system, rest[0], rest[1])
        elif form == "p3-retire-old" and len(rest) == 4:
            report = stage_p3_retire_old(system, rest[0], rest[1], rest[2], rest[3])
        else:
            raise I.InstallError("USAGE")
    except I.InstallError as exc:
        print(f"owner_prod_release_stages: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
