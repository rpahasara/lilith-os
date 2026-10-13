#!/usr/bin/env python3
"""15B2b-B1b-3e M-B11 PR-A2: control-side install and read-only status of the O2-D signer restart boundary
(provisional stage `P1B-10R`, OD-M11-11). DESIGN / SOURCE ONLY: running any form live needs a separate owner
authorization; OD-M11-11 and the E-6 / RR-33 amendment are PROPOSED, not accepted.

Record: docs/architecture/slice-15b2b-b1b3e-mb11-restart-boundary-p1b10r.md.

Control tooling under services/owner-memory-control/tools, never release payload: the accepted release `aee323e`
and its unit fragments are not changed. The two candidate drop-ins are the exact PR-A1 bytes
(`mb11_restart_boundary.DROPINS`, proven on a disposable runner by `scripts/probe_signer_restart_boundary.py`).

Four transitions, never merged into one:

1. `install <plan-digest>` (root, one go): writes the two drop-ins, `O_EXCL`, from an exact `P10R_0` pre-state bound
   to the owner-reviewed plan digest. It writes nothing else and never overwrites, repairs or rolls back;
2. `systemctl daemon-reload`: the owner's SEPARATE command. This tool never reloads;
3. `expect P10R_2_EFFECTIVE_EXACT`: the read-only verification of the effective configuration;
4. signer startup (M-B11): a separate owner authorization entirely. This tool never starts, stops or enables a unit.

Forms (root on DEV, release interpreter):

    ... observe                  one read-only observation and its phase
    ... plan                     the plan digest of an exact P10R_0 pre-state (read-only)
    ... install <plan-digest>    the one install write, then a read-back (expected P10R_1)
    ... expect <PHASE>           exit 0 only if the host is exactly <PHASE>

    drop-ins installed != reloaded != effective != startup authorized != authority
    effective restart boundary = release fragments (unchanged) + the pinned owner-controlled overlay (PROPOSED)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mb11_restart_boundary as B  # noqa: E402

TOOL_TYPE = "LILITH_MB11_RESTART_BOUNDARY_STAGE"
STAGE = "P1B-10R"
UNIT_DIR = "/etc/systemd/system"
UNITS = (B.SERVICE_UNIT, B.SOCKET_UNIT)
RELEASE_SHA = "aee323e94412accbe321bc84eae78c5b8cf95afc"
# The accepted release fragments, byte-exact (`git show aee323e:services/authority-dev/deploy/<unit>`).
FRAGMENTS = {B.SERVICE_UNIT: "11b6d00f04d998caa156875fb587dd642cb7d78dd9b6d1866616cc0b9bc1b254",
             B.SOCKET_UNIT: "bff5e9275ad1478dd068855465d65542ceb338e5e9236e43d1bd43d7c50c194f"}
FRAGMENT_MODE = 0o644
DIR_MODE = 0o755
FILE_MODE = 0o644
MAX_FILE = 64 * 1024
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
# The release defaults the loaded units show before the overlay is effective.
RELEASE_DEFAULTS = {B.SERVICE_UNIT: {"Restart": "on-failure"},
                    B.SOCKET_UNIT: {"StopWhenUnneeded": "no", "RefuseManualStart": "no"}}
UNIT_PROPERTIES = ("Id", "LoadState", "ActiveState", "SubState", "UnitFileState", "NeedDaemonReload", "FragmentPath",
                   "DropInPaths", "Restart", "StopWhenUnneeded", "RefuseManualStart", "InvocationID", "MainPID")
# Every other place systemd would read a fragment or drop-in for these names from: any of them present is foreign.
SHADOW_BASES = ("/etc/systemd/system.control", "/run/systemd/system.control", "/run/systemd/transient",
                "/run/systemd/generator.early", "/etc/systemd/system.attached", "/run/systemd/system",
                "/run/systemd/system.attached", "/run/systemd/generator", "/usr/local/lib/systemd/system",
                "/usr/lib/systemd/system", "/run/systemd/generator.late")
ACTIVATION_VERIFY = "/usr/local/sbin/lilith-activation-verify"
# The COMPLETE dark line, compared by exact equality (never prefix / substring): `lilith-activation-verify` (B1c,
# `scripts/dev_deployer/lilith_activation_verify.py`) prints one line, exit 1, ending in an `advisoryConfigEnabled`
# field. The original tool (`b67f9ecf…`) omitted that field and so refused the real host line: P1B-10R read-only
# preflight 2026-10-12 `REFUSED NOT_P10R_0:P10R_AUTHORITY_NOT_DARK` (no plan, no digest; that HALT stays recorded).
# The value below is the line observed byte-identically in every preserved root custody read (host/06-POST, 07-POST).
ACTIVATION_DARK = "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=false"
ACTIVATION_DARK_EXIT = 1
SYSTEMCTL = "/usr/bin/systemctl"
FIXED_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "HOME": "/nonexistent"}

P10R_0 = "P10R_0_PRE_INSTALL_EXACT"                  # release fragments only; no overlay anywhere; units inactive
P10R_1 = "P10R_1_INSTALLED_RELOAD_PENDING"           # overlay files exact; systemd still runs the release defaults
P10R_2 = "P10R_2_EFFECTIVE_EXACT"                    # overlay effective exactly; units inactive, static, loaded
P10R_PARTIAL = "P10R_PARTIAL_INSTALL"                # a strict prefix of the install's own writes, nothing else
P10R_FOREIGN = "P10R_FOREIGN_OR_ALTERED"             # anything the install cannot produce, or altered bytes / metadata
P10R_UNIT = "P10R_UNIT_NOT_EXACT"                    # fragments, load, enablement or reload state not the accepted one
P10R_ACTIVE = "P10R_SIGNER_NOT_INACTIVE"             # a signer unit is not inactive: outside this stage (W11 judges)
P10R_DARK = "P10R_AUTHORITY_NOT_DARK"                # activation is not GRANT_ABSENT
UNCLASSIFIED = "UNCLASSIFIED_STOP"
PHASES = (P10R_0, P10R_1, P10R_2, P10R_PARTIAL, P10R_FOREIGN, P10R_UNIT, P10R_ACTIVE, P10R_DARK, UNCLASSIFIED)
ROUTES = {
    P10R_0: "PROCEED_BY_PLAN_AND_GO: the one install may run only under an owner go naming this plan digest",
    P10R_1: "OWNER_DAEMON_RELOAD: the owner's separate daemon-reload, then `expect P10R_2_EFFECTIVE_EXACT`",
    P10R_2: "EFFECTIVE: verified; signer startup is a separate M-B11 authorization",
    P10R_PARTIAL: "STOP_OWNER_ADJUDICATION: an interrupted install; never completed, repaired or removed by a tool",
    P10R_FOREIGN: "HALT_PENDING_OWNER_ADJUDICATION: no tool acts",
    P10R_UNIT: "STOP_REVALIDATE: the accepted unit state is not present",
    P10R_ACTIVE: "STOP: a signer unit is active; outside P1B-10R",
    P10R_DARK: "HALT_PENDING_OWNER_ADJUDICATION: activation is not dark",
    UNCLASSIFIED: "STOP: UNKNOWN is never success",
}


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _host(root: Path, absolute: str) -> Path:
    return root / absolute.lstrip("/")


def candidate_path(unit: str) -> str:
    return f"{UNIT_DIR}/{unit}.d/{B.DROPINS[unit][0]}"


# ------------------------------------------------------------------ observation ---

def _lstat(path: Path) -> dict | None:
    try:
        meta = os.lstat(path)
    except FileNotFoundError:
        return None
    kind = ("dir" if stat.S_ISDIR(meta.st_mode) else "file" if stat.S_ISREG(meta.st_mode)
            else "symlink" if stat.S_ISLNK(meta.st_mode) else "other")
    return {"kind": kind, "uid": meta.st_uid, "gid": meta.st_gid, "mode": stat.S_IMODE(meta.st_mode),
            "links": meta.st_nlink}


def _read(path: Path) -> bytes | None:
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    except OSError:
        return None
    try:
        return os.read(fd, MAX_FILE + 1)
    finally:
        os.close(fd)


def _units(names: Sequence[str]) -> dict[str, dict[str, str]]:
    result = subprocess.run([SYSTEMCTL, "show", "-p", ",".join(UNIT_PROPERTIES), "--no-pager", "--", *names],
                            env=FIXED_ENV, capture_output=True, text=True, timeout=30, check=False)
    if result.returncode != 0:
        raise Refused("UNITS_UNREADABLE")
    out = {}
    for block in result.stdout.strip().split("\n\n"):
        facts = dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
        if facts.get("Id") in names:
            out[facts["Id"]] = facts
    if set(out) != set(names):
        raise Refused("UNITS_INCOMPLETE")
    return out


def _activation() -> str | None:
    result = subprocess.run([ACTIVATION_VERIFY], env=FIXED_ENV, capture_output=True, timeout=30, check=False)
    return activation_line(result.returncode, result.stdout)


def activation_line(returncode: int, stdout: bytes) -> str | None:
    """The verifier's line, only when it printed exactly one ASCII line + LF with the NOT_ACCEPTED exit code. Any
    other output (exit code, extra or missing lines, CR, non-ASCII) becomes an UNEXPECTED marker that can never equal
    `ACTIVATION_DARK`; no output at all is None (UNCLASSIFIED)."""
    if not stdout:
        return None
    try:
        text = stdout.decode("ascii")
    except UnicodeDecodeError:
        text = None
    if returncode == ACTIVATION_DARK_EXIT and text is not None and text.endswith("\n") and text.count("\n") == 1 \
            and "\r" not in text:
        return text[:-1]
    return f"UNEXPECTED_ACTIVATION_OUTPUT rc={returncode} stdout={stdout!r}"


def activation_dark(line: Any) -> bool:
    """Exact equality with the complete known-safe line: no prefix, substring or field-wise acceptance."""
    return isinstance(line, str) and line == ACTIVATION_DARK


def observe(root: Path | str = Path("/"), *, units: Callable[[Sequence[str]], dict] | None = None,
            activation: Callable[[], str | None] | None = _activation,
            owner: tuple[int, int] = (0, 0)) -> dict[str, Any]:
    """Read-only facts: fragments, the overlay directories (entries, metadata, bytes), shadow paths, unit
    properties and, unless `activation=None`, the activation line. It never writes, reloads or connects.
    `owner` is the expected owner of every file and directory (root; a TEST seam for synthetic roots)."""
    root = Path(root)
    fragments, overlay, shadows = {}, {}, {}
    for unit in UNITS:
        path = _host(root, f"{UNIT_DIR}/{unit}")
        data = _read(path)
        fragments[unit] = {"meta": _lstat(path), "sha256": None if data is None else B.sha256(data)}
        directory = _host(root, f"{UNIT_DIR}/{unit}.d")
        meta = _lstat(directory)
        entries: dict[str, Any] = {}
        if meta is not None and meta["kind"] == "dir":
            try:
                for name in sorted(os.listdir(directory)):
                    data = _read(directory / name)
                    entries[name] = {"meta": _lstat(directory / name),
                                     "sha256": None if data is None else B.sha256(data),
                                     "bytes": None if data is None or len(data) > MAX_FILE else data.decode("latin-1")}
            except OSError:
                entries = {"<unreadable>": None}
        overlay[unit] = {"directory": meta, "entries": entries}
        for base in SHADOW_BASES:
            for suffix in ("", ".d"):
                if _lstat(_host(root, f"{base}/{unit}{suffix}")) is not None:
                    shadows[f"{base}/{unit}{suffix}"] = True
    try:
        facts = (units or _units)(UNITS)
        unit_facts = {name: {key: str(facts[name].get(key, "")) for key in UNIT_PROPERTIES} for name in UNITS}
    except (Refused, KeyError, OSError, subprocess.SubprocessError):
        unit_facts = None
    line = None
    if activation is not None:
        try:
            line = activation()
        except (OSError, subprocess.SubprocessError):
            line = None
    return {"fragments": fragments, "overlay": overlay, "shadows": sorted(shadows), "units": unit_facts,
            "activation": line, "activationChecked": activation is not None, "owner": list(owner)}


# --------------------------------------------------------------------- judgement ---

def _overlay_class(overlay: Mapping[str, Any], owner: Sequence[int] = (0, 0)) -> tuple[str, list[str]]:
    """EMPTY, EXACT, PARTIAL (a strict prefix of the install's own write order) or FOREIGN."""
    reasons: list[str] = []
    progress = []                    # per unit in install order: 0 nothing, 1 directory, 2 directory + exact file
    for unit in UNITS:
        name, pin = B.DROPINS[unit]
        state = overlay.get(unit) or {}
        directory, entries = state.get("directory"), state.get("entries") or {}
        if directory is None:
            progress.append(0)
            continue
        if (directory.get("kind"), directory.get("uid"), directory.get("gid"), directory.get("mode")) \
                != ("dir", owner[0], owner[1], DIR_MODE):
            reasons.append("OVERLAY_DIRECTORY_METADATA_NOT_EXACT:" + unit)
        if not entries:
            progress.append(1)
            continue
        if set(entries) != {name}:
            reasons.append("OVERLAY_ENTRIES_NOT_EXACTLY_THE_CANDIDATE:" + unit)
            progress.append(2)
            continue
        entry = entries[name] or {}
        meta = entry.get("meta") or {}
        if (meta.get("kind"), meta.get("uid"), meta.get("gid"), meta.get("mode"), meta.get("links")) \
                != ("file", owner[0], owner[1], FILE_MODE, 1):
            reasons.append("OVERLAY_FILE_METADATA_NOT_EXACT:" + unit)
        elif entry.get("sha256") == EMPTY_SHA256:
            progress.append(1)                       # created `O_EXCL`, not yet written: the install's own window
            continue
        if entry.get("sha256") != pin:
            reasons.append("OVERLAY_FILE_BYTES_NOT_PINNED:" + unit)
        progress.append(2)
    if reasons:
        return "FOREIGN", reasons
    if progress == [0, 0]:
        return "EMPTY", []
    if progress == [2, 2]:
        return "EXACT", []
    if progress in ([1, 0], [2, 0], [2, 1]):
        return "PARTIAL", ["OVERLAY_PARTIAL:" + ",".join(map(str, progress))]
    return "FOREIGN", ["OVERLAY_NOT_A_PREFIX_OF_THE_INSTALL:" + ",".join(map(str, progress))]


def boundary_reasons(obs: Mapping[str, Any]) -> list[str]:
    """Why the effective restart boundary is NOT exactly in force, regardless of whether the signer runs (W11 uses
    this). `[]` only for exact fragments, the exact overlay, and exactly the candidate's effective properties."""
    reasons = _fragment_reasons(obs)
    klass, overlay = _overlay_class(obs.get("overlay") or {}, obs.get("owner") or (0, 0))
    if klass != "EXACT":
        reasons += overlay or ["OVERLAY_" + klass]
    if obs.get("shadows"):
        reasons.append("SHADOW_FRAGMENT_OR_DROPIN_PRESENT")
    units = obs.get("units")
    if units is None:
        return reasons + ["UNITS_UNREADABLE"]
    for unit in UNITS:
        facts = units[unit]
        data = {}
        entry = ((obs.get("overlay") or {}).get(unit) or {}).get("entries", {}).get(B.DROPINS[unit][0]) or {}
        if entry.get("bytes") is not None:
            data[candidate_path(unit)] = entry["bytes"].encode("latin-1")
        reasons += [f"{unit}:{r}" for r in B.check_effective(unit, facts, data)]
        if facts.get("FragmentPath") != f"{UNIT_DIR}/{unit}":
            reasons.append("FRAGMENT_PATH_NOT_ETC:" + unit)
    return reasons


def _fragment_reasons(obs: Mapping[str, Any]) -> list[str]:
    reasons = []
    for unit in UNITS:
        fragment = (obs.get("fragments") or {}).get(unit) or {}
        meta = fragment.get("meta") or {}
        owner = obs.get("owner") or (0, 0)
        if (meta.get("kind"), meta.get("uid"), meta.get("gid"), meta.get("mode")) != ("file", owner[0], owner[1], FRAGMENT_MODE) \
                or fragment.get("sha256") != FRAGMENTS[unit]:
            reasons.append("RELEASE_FRAGMENT_NOT_EXACT:" + unit)
    return reasons


def classify(obs: Mapping[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    units = obs.get("units")
    klass, overlay_reasons = _overlay_class(obs.get("overlay") or {}, obs.get("owner") or (0, 0))
    reasons += overlay_reasons
    if klass == "FOREIGN" or obs.get("shadows"):
        return _result(P10R_FOREIGN, reasons + (["SHADOW_FRAGMENT_OR_DROPIN_PRESENT"] if obs.get("shadows") else []),
                       klass)
    if obs.get("activationChecked") and not activation_dark(obs.get("activation")):
        return _result(P10R_DARK if obs.get("activation") else UNCLASSIFIED,
                       reasons + ["ACTIVATION:" + str(obs.get("activation"))], klass)
    if units is None:
        return _result(UNCLASSIFIED, reasons + ["UNITS_UNREADABLE"], klass)
    if any(units[u].get("ActiveState") != "inactive" or units[u].get("InvocationID") for u in UNITS):
        return _result(P10R_ACTIVE, reasons + ["SIGNER_UNIT_NOT_INACTIVE"], klass)
    fragment = _fragment_reasons(obs)
    common = [f"{u}:{k}" for u in UNITS for k, v in (("LoadState", "loaded"),) if units[u].get(k) != v]
    common += [f"{u}:UnitFileState" for u in UNITS if units[u].get("UnitFileState") not in ("static", "")]
    common += [f"{u}:FragmentPath" for u in UNITS if units[u].get("FragmentPath") != f"{UNIT_DIR}/{u}"]
    if fragment or common:
        return _result(P10R_UNIT, reasons + fragment + common, klass)
    reload = [units[u].get("NeedDaemonReload") for u in UNITS]
    if klass == "PARTIAL":
        return _result(P10R_PARTIAL, reasons, klass)
    if klass == "EMPTY":
        defaults = [f"{u}:{k}" for u in UNITS for k, v in RELEASE_DEFAULTS[u].items() if units[u].get(k) != v]
        defaults += [f"{u}:DropInPaths" for u in UNITS if units[u].get("DropInPaths")]
        if reload != ["no", "no"] or defaults:
            return _result(P10R_UNIT, reasons + defaults + ["RELOAD_STATE:" + ",".join(reload)], klass)
        return _result(P10R_0, reasons, klass)
    # EXACT overlay. Real systemd 255 keeps `NeedDaemonReload=no` when only drop-ins are added (E-19 PR #190 disposable
    # systemd probe), so "installed, not yet reloaded" is proven by what systemd LOADED, not by that flag: no unit
    # reports a drop-in and every unit still has the release defaults. The flag may then read `yes` or `no`. A unit
    # that already reports its drop-in while the other does not is never P10R_1.
    in_effect = [bool(units[u].get("DropInPaths")) for u in UNITS]
    if not any(in_effect):
        defaults = [f"{u}:{k}" for u in UNITS for k, v in RELEASE_DEFAULTS[u].items() if units[u].get(k) != v]
        if defaults or any(r not in ("yes", "no") for r in reload):
            return _result(UNCLASSIFIED, reasons + defaults + ["RELOAD_STATE:" + ",".join(reload)], klass)
        return _result(P10R_1, reasons, klass)
    if not all(in_effect):
        return _result(P10R_UNIT, reasons + [f"{u}:DropInPaths" for u, on in zip(UNITS, in_effect) if not on], klass)
    effective = boundary_reasons(obs)
    if reload != ["no", "no"] or effective:
        return _result(P10R_UNIT, reasons + effective + ["RELOAD_STATE:" + ",".join(reload)], klass)
    return _result(P10R_2, reasons, klass)


def _result(phase: str, reasons: list[str], overlay: str) -> dict[str, Any]:
    return {"toolType": TOOL_TYPE, "schemaVersion": 1, "stage": STAGE, "phase": phase, "route": ROUTES[phase],
            "overlay": overlay, "reasons": reasons, "startupAuthorized": False, "reloadPerformedByTool": False,
            "authorityGranted": False, "registryEffective": False, "authorityActive": False,
            "issuanceAuthority": "NONE", "accepted": False}


def plan_digest(obs: Mapping[str, Any]) -> str:
    """The digest an owner go names: the exact P10R_0 facts and the candidate pins (volatile values excluded)."""
    units = {u: {k: v for k, v in (obs.get("units") or {}).get(u, {}).items() if k not in ("InvocationID", "MainPID")}
             for u in UNITS}
    body = {"stage": STAGE, "release": RELEASE_SHA, "fragments": obs.get("fragments"), "units": units,
            "shadows": obs.get("shadows"), "activation": obs.get("activation"),
            "candidates": {u: list(B.DROPINS[u]) for u in UNITS}}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------ install ---

def install(digest: str, *, root: Path | str = Path("/"), units: Callable[[Sequence[str]], dict] | None = None,
            activation: Callable[[], str | None] | None = _activation, chown: bool = True,
            owner: tuple[int, int] = (0, 0)) -> dict[str, Any]:
    """The ONE write of P1B-10R. Refuses unless a fresh observation is exactly P10R_0 and its plan digest equals
    `digest`. Each directory is created with `mkdir` (never existing) and each file with `O_EXCL`; nothing is ever
    overwritten, repaired or removed. No daemon-reload. `chown=False` is a TEST seam for synthetic roots."""
    root = Path(root)
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise Refused("PLAN_DIGEST_INVALID")
    before = observe(root, units=units, activation=activation, owner=owner)
    phase = classify(before)["phase"]
    if phase != P10R_0:
        raise Refused("NOT_P10R_0:" + phase)
    if plan_digest(before) != digest:
        raise Refused("PLAN_DIGEST_MISMATCH")
    for unit in UNITS:
        directory = _host(root, f"{UNIT_DIR}/{unit}.d")
        os.mkdir(directory, DIR_MODE)
        os.chmod(directory, DIR_MODE)
        if chown:
            os.chown(directory, *owner)
        path = directory / B.DROPINS[unit][0]
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
                     | getattr(os, "O_CLOEXEC", 0), FILE_MODE)
        try:
            os.write(fd, B.candidate_bytes(unit))
            if hasattr(os, "fchmod"):
                os.fchmod(fd, FILE_MODE)
            if chown:
                os.fchown(fd, *owner)
            os.fsync(fd)
        finally:
            os.close(fd)
        _fsync_dir(directory)
    _fsync_dir(_host(root, UNIT_DIR))
    after = classify(observe(root, units=units, activation=activation, owner=owner))
    return {"result": "P1B10R_INSTALLED" if after["phase"] == P10R_1 else "P1B10R_INSTALLED_READBACK_NOT_P10R_1",
            "planDigest": digest, "readBack": after, "reloadPerformedByTool": False, "startupAuthorized": False,
            "next": "the owner's separate `systemctl daemon-reload`, then `expect P10R_2_EFFECTIVE_EXACT`"}


def _fsync_dir(path: Path) -> None:
    if os.name != "posix":
        return
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


# ------------------------------------------------------- what other observations see ---
# The overlay is NOT invisible: the PR-1A host observer reports it. After install + reload exactly these observer
# facts change (record §6). Between install and reload the W9 / W10 unit checks see `NeedDaemonReload=yes` only on
# a systemd that flags added drop-ins; systemd 255 leaves it `no` (record §10a), so only `expect` proves the reload.

def expected_observer_changes() -> dict[str, Any]:
    return {
        "units.show.DropInPaths": {u: candidate_path(u) for u in UNITS},
        "units.enablementOrDropInEntries.added": sorted(candidate_path(u).lstrip("/") for u in UNITS),
        "namespaceInventory./etc/systemd/system.added": sorted(f"{u}.d" for u in UNITS),
    }


def observer_delta_reasons(pre: Mapping[str, Any], post: Mapping[str, Any]) -> list[str]:
    """Unexpected differences between two host observer `facts` documents (pre-install P10R_0, post-reload P10R_2).
    Clock values are ignored; every other change outside `expected_observer_changes` is a reason."""
    reasons: list[str] = []
    expected = expected_observer_changes()
    sections = set(pre) | set(post)
    for section in sorted(sections):
        a, b = pre.get(section), post.get(section)
        if section == "host":
            a = {k: v for k, v in (a or {}).items() if k not in ("uptimeSeconds", "utcNow")}
            b = {k: v for k, v in (b or {}).items() if k not in ("uptimeSeconds", "utcNow")}
        elif section == "units":
            a, b = json.loads(json.dumps(a)), json.loads(json.dumps(b))
            for unit in UNITS:
                if ((a or {}).get("show", {}).get(unit) or {}).get("DropInPaths") != "":
                    reasons.append("PRE_DROPINPATHS_NOT_EMPTY:" + unit)
                if ((b or {}).get("show", {}).get(unit) or {}).get("DropInPaths") != expected["units.show.DropInPaths"][unit]:
                    reasons.append("POST_DROPINPATHS_NOT_EXACT:" + unit)
                for doc in (a, b):
                    (doc or {}).get("show", {}).get(unit, {}).pop("DropInPaths", None)
            pre_entries, post_entries = (a or {}).pop("enablementOrDropInEntries", []), \
                (b or {}).pop("enablementOrDropInEntries", [])
            if sorted(post_entries) != sorted(pre_entries + expected["units.enablementOrDropInEntries.added"]):
                reasons.append("DROPIN_ENTRIES_NOT_EXACTLY_THE_CANDIDATES")
        elif section == "namespaceInventory":
            a, b = dict(a or {}), dict(b or {})
            pre_names, post_names = a.pop(UNIT_DIR, []), b.pop(UNIT_DIR, [])
            if sorted(post_names) != sorted(pre_names + expected["namespaceInventory./etc/systemd/system.added"]):
                reasons.append("UNIT_DIR_INVENTORY_NOT_EXACTLY_THE_CANDIDATE_DIRECTORIES")
        if a != b:
            reasons.append("OBSERVER_SECTION_CHANGED:" + section)
    return reasons


def prove_dr5_unaffected(script: bytes) -> dict[str, Any]:
    """The overlay adds no routine-deployer DR-5 line: no list of the pinned script names a path at or beneath an
    overlay directory, and the unit directory is a write-denied parent (so DR-5 targets W10 / W11 are unchanged)."""
    import mb10_dr5_target as T10

    lists = T10.script_lists(script)
    for name, items in lists.items():
        for path in T10._paths(name, items):
            if any(path == f"{UNIT_DIR}/{u}.d" or path.startswith(f"{UNIT_DIR}/{u}.d/") for u in UNITS):
                raise Refused("DR5_OBSERVES_THE_OVERLAY:" + name)
    if UNIT_DIR not in lists["AB_PARENTS"]:
        raise Refused("UNIT_DIR_NOT_A_DENIED_PARENT")
    return {"dr5Delta": "EMPTY_PROVEN_FROM_PINNED_SCRIPT", "unitDirWriteDeniedParent": True}


# --------------------------------------------------------------------------- entry ---

def main(argv: list[str]) -> int:
    try:
        import mb6_ledger_verifier as V6

        if not argv or argv[0] not in ("observe", "plan", "install", "expect"):
            raise Refused("USAGE")
        V6.require_dev_root()
        if argv == ["observe"]:
            obs = observe()
            out = {"observation": obs, "classification": classify(obs)}
        elif argv == ["plan"]:
            obs = observe()
            klass = classify(obs)
            if klass["phase"] != P10R_0:
                raise Refused("NOT_P10R_0:" + klass["phase"])
            out = {"planDigest": plan_digest(obs), "classification": klass}
        elif len(argv) == 2 and argv[0] == "install":
            out = install(argv[1])
        elif len(argv) == 2 and argv[0] == "expect" and argv[1] in PHASES:
            out = classify(observe())
            sys.stdout.write(json.dumps(out, sort_keys=True, indent=2) + "\n")
            return 0 if out["phase"] == argv[1] else 1
        else:
            raise Refused("USAGE")
    except Refused as exc:
        print(f"mb11_restart_boundary_install: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(out, sort_keys=True, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
