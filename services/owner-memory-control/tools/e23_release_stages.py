#!/usr/bin/env python3
"""Track B E-23: the release stages and E-phase status of `UPGRADE_E23_PRIVACY_ANCHOR_DEV_SYNTHETIC` (SOURCE ONLY).

Record: docs/architecture/trackb-e23-transition.md. No form below is authorized by the repository; every mutating form
needs its own owner go (`e23_operator`).

It is the accepted E-22 stage tool (`e22_release_stages.py`, unchanged) moved to the merged, pinned E-23 contract
(`e23_privacy_anchor_upgrade`): the host reads are E-19's (`e19_release_stages`), the signer rule is E-22's
(`e22_release_stages.signer_state`), the installer is the byte-unchanged V1. It differs from E-22 in three ways:

1. the payload delta is the contract's 4 changed + 2 added members (archive layout v2, bound here for the call);
2. the witness UNIT and TMPFILES files change, so one extra stage (`e23-witness-units`, E4 -> E5) replaces exactly
   those two host files with NEW's, reloads systemd and creates the separate Privacy anchor directory, while signer
   and witness are stopped, and ONLY when the encrypted K-PAN credential already exists (`LoadCredentialEncrypted=`
   would fail every witness start otherwise);
3. retirement also refuses while ANY process still uses `releases/<OLD>` (cwd, executable or a mapped file).

    E0_OLD_EXACT            {OLD}       current -> OLD   signer OLD   witness OLD   units OLD
    E1_NEW_STAGED           {OLD, NEW}  current -> OLD   signer OLD   witness OLD   units OLD
    E2_SIGNER_STOPPED       {OLD, NEW}  current -> OLD   -            witness OLD   units OLD
    E3_WITNESS_STOPPED      {OLD, NEW}  current -> OLD   -            -             units OLD
    E4_NEW_SELECTED         {OLD, NEW}  current -> NEW   -            -             units OLD
    E5_WITNESS_UNITS_NEW    {OLD, NEW}  current -> NEW   -            -             units NEW (K-PAN present)
    E6_WITNESS_RUNNING      {OLD, NEW}  current -> NEW   -            witness NEW   units NEW
    E7_SIGNER_RUNNING       {OLD, NEW}  current -> NEW   signer NEW   witness NEW   units NEW
    E8_OLD_RETIRED          {NEW}       current -> NEW   signer NEW   witness NEW   units NEW

Forms (root on DEV):

    e23-status <OLD> <NEW>                                            read-only; layout, units, K-PAN facts, E-phase
    e23-stage <OLD> <NEW> <manifest-sha256> <archive> <attestation>   E0 -> E1
    e23-select <OLD> <NEW>                                            E3 -> E4
    e23-witness-units <OLD> <NEW>                                     E4 -> E5 (the only form that reloads systemd)
    e23-retire-old <OLD> <NEW> <signer-invocation> <witness-invocation>  E7 -> E8

Each mutating form refuses unless its exact pre-phase holds, never overwrites a release, and never retries, repairs,
rolls back, starts or stops a unit, generates, reads or moves a credential, or touches custody, HELD, the ledger, the
witness state or the anchor chain. Credentials are judged by metadata only (lstat; their bytes are never opened).

    status != classification != permission;  a running replacement != an accepted replacement (owner statement)
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

import e19_release_stages as S19  # noqa: E402  (reused host reads; the accepted E-19 tool, unchanged)
import e22_release_stages as S22  # noqa: E402  (reused signer rule and installer allowance; unchanged)
import e23_privacy_anchor_upgrade as E23  # noqa: E402  (the merged, pinned contract)
import install_authority_dev as I  # noqa: E402  (the accepted installer V1, byte-unchanged)

MODE = E23.MODE
OLD_RELEASE = E23.OLD_RELEASE
INSTALLED_STAGE = S19.INSTALLED_STAGE
SIGNER_SERVICE, SIGNER_SOCKET = I.AUTHORITY_UNITS
WITNESS_SERVICE, OWNER_SOCKET, WITNESS_SIGNER_SOCKET = I.WITNESS_UNITS
# The incarnations this transition ends: the E-22 owner-accepted replacements (record e22-completion §6).
ENDING_SIGNER_INCARNATION = ("efbc078492634b0280565d8990dab3d3", "128648")
ENDING_WITNESS_INCARNATION = ("8cbfbed20c954c478425c7233084ce17", "127192")
# The two host files E-23 replaces (installer targets of the contract's changed assets), old and new bytes pinned.
WITNESS_HOST_FILES = {member: I.WITNESS_UNIT_TARGETS[member] for member in sorted(E23.PAYLOAD_DELTA)
                      if member.startswith("assets/")}
KWIT_BLOB = I.WITNESS_BLOB
KPAN_BLOB = E23.KPAN_CREDENTIAL_BLOB
CREDENTIAL_DIR = I.WITNESS_CREDENTIAL_ROOT
CREDENTIAL_NAMES_WITH_KPAN = sorted((Path(KWIT_BLOB).name, Path(KPAN_BLOB).name))
ANCHOR_DIR = E23.ANCHOR_STATE_DIR
ANCHOR_NAMES = frozenset({"anchor.lock", "chain", "staging"})          # privacy_anchor.LOCK / CHAIN / staging
WITNESS_RUNTIME_CREDENTIALS = I.WITNESS_CREDENTIALS_RUNTIME
WITNESS_CREDENTIALS_OLD = ["recovery-witness-signing-key"]
WITNESS_CREDENTIALS_NEW = sorted(WITNESS_CREDENTIALS_OLD + [E23.KPAN_CREDENTIAL_NAME])
SIGNER_RUNTIME_CREDENTIALS = "/run/credentials/" + SIGNER_SERVICE
# Units outside the transition whose incarnations must not change (Core API, Hermes, provider gate, broker).
FOREIGN_UNITS = ("lilith-os-api-dev.service", "hermes-gateway-dev.service", "hermes-provider-gate-dev.service",
                 "lilith-memory-broker.service", "lilith-memory-broker.socket")
TMPFILES = WITNESS_HOST_FILES["assets/lilith-recovery-witness.tmpfiles.conf"]
DAEMON_RELOAD = ("/usr/bin/systemctl", "daemon-reload")
TMPFILES_CREATE = ("/usr/bin/systemd-tmpfiles", "--create", TMPFILES)

OLD_ONLY, STAGED, SELECTED, RETIRED, INCONSISTENT = (
    "E23_OLD_ONLY", "E23_NEW_STAGED", "E23_NEW_SELECTED", "E23_OLD_RETIRED", "E23_INCONSISTENT")
TWO_RELEASE_STATES = (STAGED, SELECTED)
E0, E1, E2, E3, E4, E5, E6, E7, E8 = (
    "E0_OLD_EXACT", "E1_NEW_STAGED", "E2_SIGNER_STOPPED", "E3_WITNESS_STOPPED", "E4_NEW_SELECTED",
    "E5_WITNESS_UNITS_NEW", "E6_WITNESS_RUNNING", "E7_SIGNER_RUNNING", "E8_OLD_RETIRED")
PHASES = (E0, E1, E2, E3, E4, E5, E6, E7, E8)
# phase -> (installed releases, selector, signer running from, witness running from, witness host files); None = stopped.
PHASE_STATE = {
    E0: (("OLD",), "OLD", "OLD", "OLD", "OLD"),
    E1: (("OLD", "NEW"), "OLD", "OLD", "OLD", "OLD"),
    E2: (("OLD", "NEW"), "OLD", None, "OLD", "OLD"),
    E3: (("OLD", "NEW"), "OLD", None, None, "OLD"),
    E4: (("OLD", "NEW"), "NEW", None, None, "OLD"),
    E5: (("OLD", "NEW"), "NEW", None, None, "NEW"),
    E6: (("OLD", "NEW"), "NEW", None, "NEW", "NEW"),
    E7: (("OLD", "NEW"), "NEW", "NEW", "NEW", "NEW"),
    E8: (("NEW",), "NEW", "NEW", "NEW", "NEW"),
}
STOP_UNKNOWN = "ES_UNKNOWN"
STOP_ACROSS_SELECT = "ES_UNIT_RUNNING_FROM_OLD_AFTER_SELECT"
STOP_RETIRED_TREE = "ES_UNIT_ON_RETIRED_RELEASE"
STOP_TRANSITIONAL = "ES_UNIT_TRANSITIONAL"
STOP_RESTARTED = "ES_ENDING_INCARNATION_CHANGED"
STOP_INCONSISTENT = "ES_LAYOUT_INCONSISTENT"
STOP_UNITS = "ES_WITNESS_UNITS_NOT_EXACT"                   # MIXED bytes, reload pending, or anchor dir not exact
STOP_KPAN = "ES_KPAN_CREDENTIAL_NOT_EXACT"
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")

Status = Callable[..., dict]


def _need(condition: bool, reason: str) -> None:
    if not condition:
        raise I.InstallError(reason)


def _releases(old: str, new: str) -> None:
    _need(old == OLD_RELEASE, "E23_OLD_RELEASE_NOT_THE_INSTALLED_RELEASE")
    _need(isinstance(new, str) and I.SHA40.fullmatch(new) is not None and new != old, "E23_NEW_RELEASE_INVALID")
    _need(new == E23.NEW_RELEASE, "E23_NEW_RELEASE_NOT_THE_PINNED_RELEASE")


@contextlib.contextmanager
def layout_v2() -> Iterator[None]:
    """Archive layout v2 (`install_authority_dev_v2._layout_v2`): V1 with exactly the contract's two added members,
    bound for the call. Not imported: V2 puts its own directory on sys.path, which under the BOOT bundle would be the
    remote working directory (a test proves the two bindings agree)."""
    saved = I.EXPECTED_PATHS
    I.EXPECTED_PATHS = saved | frozenset(E23.PAYLOAD_ADDED)
    try:
        yield
    finally:
        I.EXPECTED_PATHS = saved


# ------------------------------------------------------------------ host reads ---

def path_meta(system: I.System, absolute: str) -> dict | None:
    """lstat facts only (never opens the file): kind, owner, mode, size, inode, mtime."""
    try:
        meta = os.lstat(system.path(absolute))
    except FileNotFoundError:
        return None
    kind = ("symlink" if stat.S_ISLNK(meta.st_mode) else "dir" if stat.S_ISDIR(meta.st_mode)
            else "file" if stat.S_ISREG(meta.st_mode) else "other")
    return {"kind": kind, "uid": meta.st_uid, "gid": meta.st_gid, "mode": format(stat.S_IMODE(meta.st_mode), "04o"),
            "size": meta.st_size, "ino": meta.st_ino, "mtimeNs": meta.st_mtime_ns}


def _names(system: I.System, absolute: str) -> list[str] | None:
    path = system.path(absolute)
    if path.is_symlink() or not path.is_dir():
        return None
    return sorted(entry.name for entry in path.iterdir())


def kpan_state(system: I.System) -> str:
    """ABSENT, PRESENT_EXACT (root:root 0600 regular, non-empty) or PRESENT_UNSAFE. Metadata only."""
    meta = path_meta(system, KPAN_BLOB)
    if meta is None:
        return "ABSENT"
    exact = (meta["kind"], meta["uid"], meta["gid"], meta["mode"]) == ("file", system.owner_uid, system.owner_gid,
                                                                       "0600") and meta["size"] > 0
    return "PRESENT_EXACT" if exact else "PRESENT_UNSAFE"


def witness_units_state(system: I.System, reload_pending: str | None) -> str:
    """OLD / NEW (both host files at the contract's old / new bytes, no reload pending, the anchor directory absent /
    exact) or MIXED. Unit files are not secrets: their bytes are hashed."""
    shas = [I._file_sha(system, target) for target in WITNESS_HOST_FILES.values()]
    old = [E23.PAYLOAD_DELTA[member][0] for member in WITNESS_HOST_FILES]
    new = [E23.PAYLOAD_DELTA[member][1] for member in WITNESS_HOST_FILES]
    if reload_pending != "no":
        return "MIXED"
    anchor, state = path_meta(system, ANCHOR_DIR), path_meta(system, I.WITNESS_STATE)
    if shas == old:
        return "OLD" if anchor is None else "MIXED"
    if shas == new and anchor is not None and state is not None \
            and (anchor["kind"], anchor["uid"], anchor["gid"], anchor["mode"]) == ("dir", state["uid"], state["gid"],
                                                                                   "0700"):
        return "NEW"
    return "MIXED"


def anchor_facts(system: I.System) -> dict[str, Any]:
    """The separate Privacy anchor directory: its names (subset of the anchor service's) and the chain versions
    (E-23 writes none: genesis is B6)."""
    names = _names(system, ANCHOR_DIR)
    chain = _names(system, f"{ANCHOR_DIR}/chain") if names and "chain" in names else []
    return {"names": names, "chainVersions": None if chain is None else len(chain),
            "exact": names is None or (set(names) <= ANCHOR_NAMES and chain == [])}


def _unit_show(system: I.System, unit: str, properties: tuple[str, ...]) -> dict[str, str | None]:
    result = system.run(["/usr/bin/systemctl", "show", "--property=" + ",".join(properties), "--", unit])
    values = dict(line.split("=", 1) for line in (result.stdout or "").splitlines() if "=" in line)
    return {key: values.get(key) for key in properties}


def foreign_units(system: I.System) -> dict[str, dict[str, str | None]]:
    return {unit: _unit_show(system, unit, S19.UNIT_PROPERTIES) for unit in FOREIGN_UNITS}


def release_users(system: I.System, release: str) -> list[str]:
    """Every process whose cwd, executable or a mapped file is inside `releases/<release>` (read-only /proc scan)."""
    top = f"{I.RELEASES}/{release}"
    users = []
    proc = system.path("/proc")
    for entry in sorted(proc.iterdir()) if proc.is_dir() else []:
        if not entry.name.isdigit():
            continue
        found = False
        for link in ("cwd", "exe"):
            try:
                target = os.readlink(entry / link)
            except OSError:
                continue
            found = found or target == top or target.startswith(top + "/")
        try:
            found = found or any(top + "/" in line or line.rstrip().endswith(top)
                                 for line in (entry / "maps").read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            pass
        if found:
            users.append(entry.name)
    return users


def delta_failures(old_files: dict[str, str] | None, new_files: dict[str, str] | None) -> list[str]:
    """NEW = OLD moved by exactly the contract delta (`new_payload_pins`): 4 changed, 2 added, none removed."""
    if old_files is None or new_files is None:
        return ["E23_DELTA_UNOBSERVABLE"]
    try:
        expected = E23.new_payload_pins(old_files)
    except E23.Refused as exc:
        return ["E23_DELTA_OLD:" + str(exc)]
    if expected != new_files:
        return ["E23_DELTA_NOT_EXACT:" + ",".join(sorted(p for p in set(expected) | set(new_files)
                                                         if expected.get(p) != new_files.get(p))[:6])]
    return []


def _allowed_installer_failures(state: str, signer: str, kpan: str, credentials: list[str] | None,
                                units: str, selector_new: bool) -> set[str]:
    allowed = {"RELEASE_SET"} if state in TWO_RELEASE_STATES else set()
    if signer == "RUNNING":
        allowed |= S22.SIGNER_RUNNING_INSTALLER_FAILURES
    if kpan == "PRESENT_EXACT" and credentials == CREDENTIAL_NAMES_WITH_KPAN:
        allowed.add("LISTING:" + CREDENTIAL_DIR)                  # the installer predates K-PAN: exactly this one name
    if selector_new and units == "OLD":
        allowed |= {"UNIT_BYTES:" + target for target in WITNESS_HOST_FILES.values()}     # E4 only: NEW selected
    return allowed


def e23_status(system: I.System, old: str, new: str, *, status: Status = I.status) -> dict[str, Any]:
    """Read-only. The closed release-layout state, both units, the witness host files, the K-PAN / K-WIT credential
    metadata, the anchor directory, the foreign units, and the E-phase."""
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
    if new in shas and new_manifest != E23.NEW_MANIFEST_SHA256:
        failures.append("E23_NEW_MANIFEST_NOT_THE_PIN")
    units = S19.unit_facts(system)
    reload_pending = _unit_show(system, WITNESS_SERVICE, ("NeedDaemonReload",))["NeedDaemonReload"]
    signer, witness = S22.signer_state(units), S19.witness_state(units)
    host_units = witness_units_state(system, reload_pending)
    kpan, credentials = kpan_state(system), _names(system, CREDENTIAL_DIR)
    installer = None
    if state != INCONSISTENT:
        selected = target.split("/", 1)[1]
        report = status(system, INSTALLED_STAGE, selected)
        allowed = _allowed_installer_failures(state, signer, kpan, credentials, host_units, selected == new)
        installer = {"stage": INSTALLED_STAGE, "releaseSha": selected, "result": report["result"],
                     "failures": list(report["failures"])}
        failures += ["INSTALLER:" + failure for failure in report["failures"] if failure not in allowed]
    report = {"schemaVersion": 1, "mode": MODE, "oldRelease": old, "newRelease": new, "state": state,
              "releaseEntries": entries, "currentTarget": target, "newManifestSha256": new_manifest,
              "installerStatus": installer, "signer": signer, "witness": witness, "units": units,
              "signerCwd": S19.process_cwd(system, units[SIGNER_SERVICE]["MainPID"]) if signer == "RUNNING" else None,
              "witnessCwd": S19.process_cwd(system, units[WITNESS_SERVICE]["MainPID"]) if witness == "RUNNING" else None,
              "witnessUnits": host_units, "witnessReloadPending": reload_pending,
              "kPan": kpan, "kPanMeta": path_meta(system, KPAN_BLOB), "kWitMeta": path_meta(system, KWIT_BLOB),
              "credentialNames": credentials, "anchor": anchor_facts(system),
              "witnessCredentials": _names(system, WITNESS_RUNTIME_CREDENTIALS) if witness == "RUNNING" else None,
              "signerCredentials": _names(system, SIGNER_RUNTIME_CREDENTIALS) if signer == "RUNNING" else None,
              "foreignUnits": foreign_units(system),
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
    """The E-phase of one status report (`PHASE_STATE`), or a STOP. Never a permission."""
    if report["state"] == INCONSISTENT:
        return STOP_INCONSISTENT
    if report["kPan"] == "PRESENT_UNSAFE":                     # the specific STOPs first (all are STOPs)
        return STOP_KPAN
    if report["witnessUnits"] not in ("OLD", "NEW") or not report["anchor"]["exact"]:
        return STOP_UNITS
    if report["failures"]:
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
    found = next((name for name, want in PHASE_STATE.items()
                  if (releases, selector, shape["signer"], shape["witness"], report["witnessUnits"]) == want),
                 STOP_UNKNOWN)
    # Witness host files at NEW name the K-PAN credential: from E5 on it must exist, exact.
    if found in PHASES[PHASES.index(E5):] and report["kPan"] != "PRESENT_EXACT":
        return STOP_KPAN
    return found


def _require(report: Mapping[str, Any], expected_phase: str) -> None:
    _need(report["result"] == "PASS" and report["phase"] == expected_phase,
          f"E23_PRE_PHASE:{report['phase']}:" + ",".join(report["failures"]))


def _post(system: I.System, old: str, new: str, expected_phase: str, mutation: str, status: Status) -> dict[str, Any]:
    report = e23_status(system, old, new, status=status)
    report["mutation"] = mutation
    if report["phase"] != expected_phase:
        report["result"] = "FAIL"
        report["failures"].append("E23_POST_PHASE:" + report["phase"])
    return report


# ------------------------------------------------------------------- mutations ---

def stage_e23_stage(system: I.System, old: str, new: str, manifest_sha256: str, archive: Path, attestation: Path,
                    *, status: Status = I.status) -> dict[str, Any]:
    """STAGE (E0 -> E1): `releases/<NEW>` beside OLD from the verified, attested archive whose manifest is the pinned
    one and whose payload is OLD moved by exactly the contract delta. The body is the E-22 stage."""
    I.require_dev_root(system)
    _need(isinstance(manifest_sha256, str) and _HEX64.fullmatch(manifest_sha256) is not None
          and manifest_sha256 == E23.NEW_MANIFEST_SHA256, "E23_MANIFEST_PIN_INVALID")
    _require(e23_status(system, old, new, status=status), E0)
    with layout_v2():
        manifest, payloads = I.verify_archive(archive, attestation, new)
    _need(I.digest(I.canonical(manifest)) == manifest_sha256, "E23_MANIFEST_NOT_THE_PINNED_MANIFEST")
    delta = delta_failures(S19.manifest_files(system, old), {item["path"]: item["sha256"] for item in manifest["files"]})
    _need(not delta, "E23_PAYLOAD_DELTA:" + ",".join(delta))
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
                 "lilith_recovery_witness.server, lilith_recovery_witness.privacy_anchor, lilith_authority_root.cli",
                 str(staging), cwd=staging)
    staging.rename(system.path(f"{I.RELEASES}/{new}"))
    I._fsync_directory(system, I.RELEASES)
    return _post(system, old, new, E1, "STAGED", status)


def stage_e23_select(system: I.System, old: str, new: str, *, status: Status = I.status) -> dict[str, Any]:
    """SELECT (E3 -> E4): `current -> releases/<NEW>` by symlink(tmp) + rename, ONLY while the signer AND the witness
    (service and sockets) are stopped, so neither ending incarnation runs across the selector change."""
    I.require_dev_root(system)
    _require(e23_status(system, old, new, status=status), E3)
    tmp = system.path(S19.SELECTOR_TMP)
    os.symlink(f"releases/{new}", tmp)
    if system.chown:
        os.lchown(tmp, 0, 0)
    os.rename(tmp, system.path(I.CURRENT))
    I._fsync_directory(system, I.OPT)
    return _post(system, old, new, E4, "SELECTED", status)


def stage_e23_witness_units(system: I.System, old: str, new: str, *, status: Status = I.status) -> dict[str, Any]:
    """WITNESS_UNITS (E4 -> E5): with NEW selected and both units stopped, and ONLY when the encrypted K-PAN credential
    already exists exact: replace the witness unit and tmpfiles host files with NEW's (tmp + rename each), reload
    systemd, and create the anchor directory from the new tmpfiles line. No unit is started, stopped or enabled."""
    I.require_dev_root(system)
    before = e23_status(system, old, new, status=status)
    _require(before, E4)
    _need(before["kPan"] == "PRESENT_EXACT", "E23_KPAN_CREDENTIAL_REQUIRED_BEFORE_WITNESS_UNITS")
    _need((before["kWitMeta"] or {}).get("kind") == "file", "E23_KWIT_CREDENTIAL_MISSING")
    for member, target in WITNESS_HOST_FILES.items():
        data = system.path(f"{I.RELEASES}/{new}/{member}").read_bytes()
        _need(I.digest(data) == E23.PAYLOAD_DELTA[member][1], "E23_NEW_UNIT_BYTES_NOT_THE_PIN:" + member)
        I._replace_file(system, target, data, 0o644)
    system.fixed(*DAEMON_RELOAD)
    system.fixed(*TMPFILES_CREATE)
    return _post(system, old, new, E5, "WITNESS_UNITS_REPLACED_RELOADED", status)


def stage_e23_retire_old(system: I.System, old: str, new: str, signer_invocation: str, witness_invocation: str, *,
                         status: Status = I.status) -> dict[str, Any]:
    """RETIRE (E7 -> E8): remove `releases/<OLD>` only while BOTH replacement incarnations the owner accepted (named in
    the go) run from `releases/<NEW>`, NRestarts 0, and no process at all still uses OLD."""
    I.require_dev_root(system)
    for invocation, ending in ((signer_invocation, ENDING_SIGNER_INCARNATION),
                               (witness_invocation, ENDING_WITNESS_INCARNATION)):
        _need(isinstance(invocation, str) and _HEX32.fullmatch(invocation) is not None and invocation != ending[0],
              "E23_REPLACEMENT_INVOCATION_INVALID")
    before = e23_status(system, old, new, status=status)
    _require(before, E7)
    _need(before["units"][SIGNER_SERVICE]["InvocationID"] == signer_invocation
          and before["units"][WITNESS_SERVICE]["InvocationID"] == witness_invocation,
          "E23_ACCEPTED_REPLACEMENTS_NOT_RUNNING")
    users = release_users(system, old)
    _need(not users, "E23_OLD_RELEASE_IN_USE:" + ",".join(users))
    doomed = system.path(f"{I.RELEASES}/{old}")
    _need(not doomed.is_symlink() and doomed.is_dir(), "RETIRE_TARGET_UNSAFE")
    shutil.rmtree(doomed)
    I._fsync_directory(system, I.RELEASES)
    return _post(system, old, new, E8, "RETIRED", status)


def main(argv: list[str], system: I.System | None = None) -> int:
    system = system or I.System()
    try:
        form, rest = (argv[0], argv[1:]) if argv else ("", [])
        if form == "e23-status" and len(rest) == 2:
            I.require_dev_root(system)
            report = e23_status(system, rest[0], rest[1])
        elif form == "e23-stage" and len(rest) == 5:
            report = stage_e23_stage(system, rest[0], rest[1], rest[2], Path(rest[3]), Path(rest[4]))
        elif form == "e23-select" and len(rest) == 2:
            report = stage_e23_select(system, rest[0], rest[1])
        elif form == "e23-witness-units" and len(rest) == 2:
            report = stage_e23_witness_units(system, rest[0], rest[1])
        elif form == "e23-retire-old" and len(rest) == 4:
            report = stage_e23_retire_old(system, rest[0], rest[1], rest[2], rest[3])
        else:
            raise I.InstallError("USAGE")
    except I.InstallError as exc:
        print(f"e23_release_stages: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
