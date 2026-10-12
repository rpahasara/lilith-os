#!/usr/bin/env python3
"""15B2b-B1b-3e E-19: install and read-only verification of the WITNESS restart boundary (DEV, design only).

Record: docs/architecture/slice-15b2b-b1b3e-e19-witness-restart-boundary.md. Contract (merged, unchanged):
`e19_p1b10_upgrade.py` §4.4 (`RESTART_BOUNDARY`, the three candidate drop-ins in `e19_witness_restart_dropins/`).
The pattern is the reviewed P1B-10R signer tool (`mb11_restart_boundary_install.py`); it is not changed.

DESIGN / SOURCE ONLY. Running any form live needs a separate owner authorization (E19-D3, PROPOSED). Unlike the
signer, the witness RUNS during this stage: the accepted incarnation 8af12bd6…/1580 must be the same, with no new
invocation (K-WIT load) after the plan's journal cursor, in every phase. Four transitions, never merged into one:

1. `install <plan-digest> <plan-cursor>` (root, one go): from an exact WRB_0 pre-state bound to the owner-reviewed plan
   digest, creates the three drop-in directories (`mkdir`, never existing) and files (`O_EXCL`). It never
   overwrites, repairs, removes or rolls back, and never reloads, starts, stops or restarts a unit;
2. `systemctl daemon-reload`: the owner's SEPARATE command under its own authorization. This tool never reloads;
3. `expect WRB_2_EFFECTIVE_EXACT <plan-cursor>`: the read-only verification;
4. the E-19 U0 baseline: a separate owner acceptance entirely.

Forms (root on DEV, interpreter `-I -B`):

    ... observe                                  one read-only observation and its phase
    ... plan                                     the plan digest and journal cursor of an exact WRB_0 (read-only)
    ... install <plan-digest> <plan-cursor>      the one install write, then a read-back (expected WRB_1)
    ... expect <PHASE> <plan-cursor>             exit 0 only if the host is exactly <PHASE>

    installed != reloaded != effective != U0 accepted;  no restart, no K-WIT load, no reload by this tool
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

sys.dont_write_bytecode = True          # read-only Python before any tool import (as the E-19 observer, F1)

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import e19_maintenance_observer as O  # noqa: E402  (journal reads, units reader; merged, unchanged)
import e19_p1b10_upgrade as E  # noqa: E402  (the merged contract: units, pins, RESTART_BOUNDARY)
import mb11_restart_boundary as B  # noqa: E402  (parse_unit only)
import mb11_restart_boundary_install as RBI  # noqa: E402  (SHADOW_BASES, activation line; unchanged)

TOOL_TYPE = "LILITH_E19_WITNESS_RESTART_BOUNDARY_STAGE"
STAGE = "E19-WRB"
UNIT_DIR = E.UNIT_DIR
UNITS = (E.WITNESS_SERVICE, E.OWNER_SOCKET, E.SIGNER_SOCKET)          # install order
DROPINS = {unit: (Path(path).name, E.WITNESS_DROPINS[path])
           for unit, path in ((E.WITNESS_SERVICE, E.SERVICE_DROPIN), (E.OWNER_SOCKET, E.SOCKET_DROPINS[E.OWNER_SOCKET]),
                              (E.SIGNER_SOCKET, E.SOCKET_DROPINS[E.SIGNER_SOCKET]))}
# The accepted release fragments (`E.OLD_RELEASE` assets, byte-identical in the repository; a test re-derives them).
FRAGMENTS = {
    E.WITNESS_SERVICE: "9f78130c06491d184aff7066de99f804bf3816e171c63d6f70b734b1c6e85d7d",
    E.OWNER_SOCKET: "d260917fb31e9c76341fba131bafdc2802b80c0cf2fdcffb8cecc6e176440beb",
    E.SIGNER_SOCKET: "ad345d18747c30a7c2a93cb18d5be310dc091f5efe07fc6e1606efbc099bb9c7",
}
FRAGMENT_MODE = 0o644
DIR_MODE = 0o755
FILE_MODE = 0o644
MAX_FILE = 64 * 1024
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
# What systemd reports before the overlay is effective (the release fragments' own values).
RELEASE_DEFAULTS = {E.WITNESS_SERVICE: {"Restart": "on-failure"},
                    E.OWNER_SOCKET: {"StopWhenUnneeded": "no", "RefuseManualStart": "no"},
                    E.SIGNER_SOCKET: {"StopWhenUnneeded": "no", "RefuseManualStart": "no"}}
UNIT_PROPERTIES = ("Id", "LoadState", "ActiveState", "SubState", "UnitFileState", "NeedDaemonReload", "FragmentPath",
                   "DropInPaths", "Restart", "StopWhenUnneeded", "RefuseManualStart", "InvocationID", "MainPID",
                   "NRestarts")
SHADOW_BASES = RBI.SHADOW_BASES
ACCEPTED_INCARNATION = E.ENDING_INCARNATION                     # 8af12bd6… / 1580, running, NRestarts 0

WRB_0 = "WRB_0_PRE_INSTALL_EXACT"                # release fragments only; no overlay anywhere; witness exact
WRB_1 = "WRB_1_INSTALLED_RELOAD_PENDING"         # overlay files exact; systemd still has the release defaults
WRB_2 = "WRB_2_EFFECTIVE_EXACT"                  # overlay effective exactly (= the merged RESTART_BOUNDARY)
WRB_PARTIAL = "WRB_PARTIAL_INSTALL"              # a strict prefix of the install's own writes, nothing else
WRB_FOREIGN = "WRB_FOREIGN_OR_ALTERED"           # anything the install cannot produce, altered bytes, or a shadow
WRB_UNIT = "WRB_UNIT_NOT_EXACT"                  # fragments, load, enablement, reload or effective state not accepted
WRB_WITNESS = "WRB_WITNESS_NOT_THE_ACCEPTED_INCARNATION"   # stopped, restarted, another identity, or a new load
WRB_DARK = "WRB_AUTHORITY_NOT_DARK"              # activation is not GRANT_ABSENT
UNCLASSIFIED = "UNCLASSIFIED_STOP"               # unknown evidence (units, journal, cursor retention, activation)
PHASES = (WRB_0, WRB_1, WRB_2, WRB_PARTIAL, WRB_FOREIGN, WRB_UNIT, WRB_WITNESS, WRB_DARK, UNCLASSIFIED)
ROUTES = {
    WRB_0: "PROCEED_BY_PLAN_AND_GO: the one install may run only under an owner go naming this plan digest and cursor",
    WRB_1: "OWNER_DAEMON_RELOAD: the owner's separate daemon-reload (own authorization), then `expect WRB_2`",
    WRB_2: "EFFECTIVE: verified; the E-19 U0 baseline is a separate owner acceptance",
    WRB_PARTIAL: "STOP_OWNER_ADJUDICATION: an interrupted install; never completed, repaired or removed by a tool",
    WRB_FOREIGN: "HALT_PENDING_OWNER_ADJUDICATION: no tool acts",
    WRB_UNIT: "STOP_REVALIDATE: the accepted unit state is not present",
    WRB_WITNESS: "HALT_PENDING_OWNER_ADJUDICATION: the witness incarnation changed or loaded K-WIT again",
    WRB_DARK: "HALT_PENDING_OWNER_ADJUDICATION: activation is not dark",
    UNCLASSIFIED: "STOP: UNKNOWN is never success",
}
_CURSOR = re.compile(r"\S{1,512}\Z")

Refused = E.Refused


def _host(root: Path, absolute: str) -> Path:
    return root / absolute.lstrip("/")


def candidate_path(unit: str) -> str:
    return f"{UNIT_DIR}/{unit}.d/{DROPINS[unit][0]}"


def candidate_bytes(unit: str) -> bytes:
    """The merged candidate bytes, refused unless they still hash to the merged pin."""
    name, pin = DROPINS[unit]
    data = (E.DROPIN_SOURCE / f"{unit}.d" / name).read_bytes()
    if hashlib.sha256(data).hexdigest() != pin:
        raise Refused("CANDIDATE_NOT_PINNED", unit)
    return data


# ------------------------------------------------------------------ observation ---

_lstat = RBI._lstat


def _read(path: Path) -> bytes | None:
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    except OSError:
        return None
    try:
        return os.read(fd, MAX_FILE + 1)
    finally:
        os.close(fd)


def _units(names: Sequence[str]) -> dict[str, dict[str, str]] | None:
    import subprocess

    result = subprocess.run([O.SYSTEMCTL, "show", "-p", ",".join(UNIT_PROPERTIES), "--no-pager", "--", *names],
                            env=O.FIXED_ENV, capture_output=True, text=True, timeout=30, check=False)
    if result.returncode != 0:
        return None
    out = {}
    for block in result.stdout.strip().split("\n\n"):
        facts = dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
        if facts.get("Id") in names:
            out[facts["Id"]] = facts
    return out if set(out) == set(names) else None


def observe(root: Path | str = Path("/"), *, after_cursor: str | None = None, units: Callable | None = None,
            activation: Callable | None = RBI._activation, journal_tail: Callable | None = None,
            invocations: Callable | None = None, cursor_retained: Callable | None = None,
            owner: tuple[int, int] = (0, 0)) -> dict[str, Any]:
    """Read-only facts: fragments, the overlay directories (entries, metadata, bytes), shadow paths, unit properties,
    the activation line, and the journal: the current cursor, whether `after_cursor` (the plan's) is still retained,
    and the witness invocations after it. It never writes, reloads, starts or connects to a socket."""
    root = Path(root)
    fragments, overlay, shadows = {}, {}, []
    for unit in UNITS:
        path = _host(root, f"{UNIT_DIR}/{unit}")
        data = _read(path)
        fragments[unit] = {"meta": _lstat(path), "sha256": None if data is None else hashlib.sha256(data).hexdigest()}
        directory = _host(root, f"{UNIT_DIR}/{unit}.d")
        meta = _lstat(directory)
        entries: dict[str, Any] = {}
        if meta is not None and meta["kind"] == "dir":
            try:
                for name in sorted(os.listdir(directory)):
                    data = _read(directory / name)
                    entries[name] = {"meta": _lstat(directory / name),
                                     "sha256": None if data is None else hashlib.sha256(data).hexdigest(),
                                     "bytes": None if data is None or len(data) > MAX_FILE else data.decode("latin-1")}
            except OSError:
                entries = {"<unreadable>": None}
        overlay[unit] = {"directory": meta, "entries": entries}
        shadows += [f"{base}/{unit}{suffix}" for base in SHADOW_BASES for suffix in ("", ".d")
                    if _lstat(_host(root, f"{base}/{unit}{suffix}")) is not None]
    unit_facts = O._safe(lambda: (units or _units)(UNITS))
    if unit_facts is not None:
        unit_facts = {name: {key: str(unit_facts[name].get(key, "")) for key in UNIT_PROPERTIES} for name in UNITS}
    line = O._safe(activation) if activation is not None else None
    cursor = O._safe(journal_tail or O._journal_tail)
    anchor = after_cursor if after_cursor is not None else cursor
    retained = O._safe(lambda: (cursor_retained or O._cursor_retained)(anchor)) if anchor is not None else None
    loads = (O._safe(lambda: (invocations or O._invocations)(E.WITNESS_SERVICE, anchor)) if retained is True
             else None)
    return {"fragments": fragments, "overlay": overlay, "shadows": sorted(shadows), "units": unit_facts,
            "activation": line, "activationChecked": activation is not None, "owner": list(owner),
            "journal": {"cursor": cursor, "afterCursor": anchor, "retained": retained, "witnessLoads": loads}}


# --------------------------------------------------------------------- judgement ---

def _overlay_class(overlay: Mapping[str, Any], owner: Sequence[int] = (0, 0)) -> tuple[str, list[str]]:
    """EMPTY, EXACT, PARTIAL (a strict prefix of the install's own write order) or FOREIGN."""
    reasons: list[str] = []
    progress = []                    # per unit in install order: 0 nothing, 1 directory (+ empty O_EXCL file), 2 exact
    for unit in UNITS:
        name, pin = DROPINS[unit]
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
            progress.append(1)                       # created O_EXCL, not yet written: the install's own window
            continue
        if entry.get("sha256") != pin:
            reasons.append("OVERLAY_FILE_BYTES_NOT_PINNED:" + unit)
        progress.append(2)
    if reasons:
        return "FOREIGN", reasons
    if progress == [0, 0, 0]:
        return "EMPTY", []
    if progress == [2, 2, 2]:
        return "EXACT", []
    if progress in ([1, 0, 0], [2, 0, 0], [2, 1, 0], [2, 2, 0], [2, 2, 1]):
        return "PARTIAL", ["OVERLAY_PARTIAL:" + ",".join(map(str, progress))]
    return "FOREIGN", ["OVERLAY_NOT_A_PREFIX_OF_THE_INSTALL:" + ",".join(map(str, progress))]


def _fragment_reasons(obs: Mapping[str, Any]) -> list[str]:
    owner = obs.get("owner") or (0, 0)
    reasons = []
    for unit in UNITS:
        fragment = (obs.get("fragments") or {}).get(unit) or {}
        meta = fragment.get("meta") or {}
        if (meta.get("kind"), meta.get("uid"), meta.get("gid"), meta.get("mode")) \
                != ("file", owner[0], owner[1], FRAGMENT_MODE) or fragment.get("sha256") != FRAGMENTS[unit]:
            reasons.append("RELEASE_FRAGMENT_NOT_EXACT:" + unit)
    return reasons


def _witness_reasons(units: Mapping[str, Mapping[str, str]], journal: Mapping[str, Any]) -> list[str]:
    service = units[E.WITNESS_SERVICE]
    reasons = []
    if (service.get("ActiveState"), service.get("SubState")) != ("active", "running"):
        reasons.append("WITNESS_NOT_RUNNING")
    if (service.get("InvocationID"), service.get("MainPID")) != ACCEPTED_INCARNATION:
        reasons.append("WITNESS_NOT_THE_ACCEPTED_INCARNATION")
    if service.get("NRestarts") != "0":
        reasons.append("WITNESS_RESTARTED")
    if any(units[s].get("ActiveState") != "active" for s in (E.OWNER_SOCKET, E.SIGNER_SOCKET)):
        reasons.append("WITNESS_SOCKETS_NOT_ACTIVE")
    if journal.get("witnessLoads") != []:
        reasons.append("WITNESS_LOADED_AFTER_THE_PLAN_CURSOR")
    return reasons


def effective_reasons(obs: Mapping[str, Any]) -> list[str]:
    """Why the effective configuration is not exactly the merged `RESTART_BOUNDARY` (installed bytes + properties)."""
    units = obs.get("units") or {}
    reasons = []
    for unit, expected in E.RESTART_BOUNDARY["units"].items():
        reasons += [f"{unit}:{key}" for key, value in expected.items() if (units.get(unit) or {}).get(key) != value]
    for unit in UNITS:
        entry = (((obs.get("overlay") or {}).get(unit) or {}).get("entries") or {}).get(DROPINS[unit][0]) or {}
        if entry.get("sha256") != DROPINS[unit][1]:
            reasons.append(f"DROPIN_BYTES:{unit}")
    return reasons


def classify(obs: Mapping[str, Any]) -> dict[str, Any]:
    """HALT / STOP facts first, then UNKNOWN, then the exact phases."""
    reasons: list[str] = []
    units = obs.get("units")
    journal = obs.get("journal") or {}
    klass, overlay_reasons = _overlay_class(obs.get("overlay") or {}, obs.get("owner") or (0, 0))
    reasons += overlay_reasons
    if klass == "FOREIGN" or obs.get("shadows"):
        return _result(WRB_FOREIGN, reasons + [f"SHADOW:{p}" for p in obs.get("shadows") or []], klass)
    if obs.get("activationChecked") and not RBI.activation_dark(obs.get("activation")):
        return _result(WRB_DARK if obs.get("activation") else UNCLASSIFIED,
                       reasons + ["ACTIVATION:" + str(obs.get("activation"))], klass)
    if units is None:
        return _result(UNCLASSIFIED, reasons + ["UNITS_UNREADABLE"], klass)
    if journal.get("retained") is not True or journal.get("witnessLoads") is None:
        return _result(UNCLASSIFIED, reasons + ["JOURNAL_NOT_PROVEN:" + str(journal.get("retained"))], klass)
    witness = _witness_reasons(units, journal)
    if witness:
        return _result(WRB_WITNESS, reasons + witness, klass)
    fragment = _fragment_reasons(obs)
    common = [f"{u}:LoadState" for u in UNITS if units[u].get("LoadState") != "loaded"]
    common += [f"{u}:UnitFileState" for u in UNITS if units[u].get("UnitFileState") not in ("static", "")]
    common += [f"{u}:FragmentPath" for u in UNITS if units[u].get("FragmentPath") != f"{UNIT_DIR}/{u}"]
    if fragment or common:
        return _result(WRB_UNIT, reasons + fragment + common, klass)
    if klass == "PARTIAL":
        return _result(WRB_PARTIAL, reasons, klass)
    reload = [units[u].get("NeedDaemonReload") for u in UNITS]
    defaults = [f"{u}:{k}" for u in UNITS for k, v in RELEASE_DEFAULTS[u].items() if units[u].get(k) != v]
    defaults += [f"{u}:DropInPaths" for u in UNITS if units[u].get("DropInPaths")]
    if klass == "EMPTY":
        if reload != ["no", "no", "no"] or defaults:
            return _result(WRB_UNIT, reasons + defaults + ["RELOAD_STATE:" + ",".join(reload)], klass)
        return _result(WRB_0, reasons, klass)
    # EXACT overlay
    if reload == ["yes", "yes", "yes"]:
        if defaults:
            return _result(UNCLASSIFIED, reasons + defaults, klass)       # reload pending yet partly effective
        return _result(WRB_1, reasons, klass)
    effective = effective_reasons(obs)
    if reload != ["no", "no", "no"] or effective:
        return _result(WRB_UNIT, reasons + effective + ["RELOAD_STATE:" + ",".join(reload)], klass)
    return _result(WRB_2, reasons, klass)


def _result(phase: str, reasons: list[str], overlay: str) -> dict[str, Any]:
    return {"toolType": TOOL_TYPE, "schemaVersion": 1, "stage": STAGE, "phase": phase, "route": ROUTES[phase],
            "overlay": overlay, "reasons": reasons, "reloadPerformedByTool": False, "witnessRestartedByTool": False,
            "u0Accepted": False, "authorityGranted": False, "accepted": False}


def plan_digest(obs: Mapping[str, Any]) -> str:
    """The digest an owner go names: the exact WRB_0 facts (including the witness identity, which must not change),
    the shadows, the activation line and the candidate pins. The journal cursor is returned beside it, not in it."""
    units = {u: {k: v for k, v in (obs.get("units") or {}).get(u, {}).items()} for u in UNITS}
    body = {"stage": STAGE, "release": E.OLD_RELEASE, "fragments": obs.get("fragments"), "units": units,
            "shadows": obs.get("shadows"), "activation": obs.get("activation"),
            "candidates": {u: list(DROPINS[u]) for u in UNITS}}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def plan(**observe_kw: Any) -> dict[str, Any]:
    """Read-only: the plan digest and the journal cursor of an exact WRB_0 (the cursor binds every later load count)."""
    obs = observe(**observe_kw)
    klass = classify(obs)
    if klass["phase"] != WRB_0:
        raise Refused("NOT_WRB_0", klass["phase"])
    return {"planDigest": plan_digest(obs), "planCursor": obs["journal"]["afterCursor"], "classification": klass}


# ------------------------------------------------------------------------ install ---

def install(digest: str, plan_cursor: str, *, root: Path | str = Path("/"), chown: bool = True,
            owner: tuple[int, int] = (0, 0), **observe_kw: Any) -> dict[str, Any]:
    """The ONE write. Refuses unless a fresh observation, counted after the plan's cursor, is exactly WRB_0 and its
    plan digest equals `digest`. Directories by `mkdir` (never existing), files by `O_EXCL`; nothing is overwritten,
    repaired or removed; no daemon-reload, start, stop or restart. `chown=False` is a TEST seam."""
    root = Path(root)
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise Refused("PLAN_DIGEST_INVALID")
    if not isinstance(plan_cursor, str) or _CURSOR.fullmatch(plan_cursor) is None:
        raise Refused("PLAN_CURSOR_INVALID")
    payloads = {unit: candidate_bytes(unit) for unit in UNITS}
    before = observe(root, after_cursor=plan_cursor, owner=owner, **observe_kw)
    phase = classify(before)["phase"]
    if phase != WRB_0:
        raise Refused("NOT_WRB_0", phase)
    if plan_digest(before) != digest:
        raise Refused("PLAN_DIGEST_MISMATCH")
    for unit in UNITS:
        directory = _host(root, f"{UNIT_DIR}/{unit}.d")
        os.mkdir(directory, DIR_MODE)
        os.chmod(directory, DIR_MODE)
        if chown:
            os.chown(directory, *owner)
        fd = os.open(directory / DROPINS[unit][0], os.O_WRONLY | os.O_CREAT | os.O_EXCL
                     | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0), FILE_MODE)
        try:
            os.write(fd, payloads[unit])
            if hasattr(os, "fchmod"):
                os.fchmod(fd, FILE_MODE)
            if chown:
                os.fchown(fd, *owner)
            os.fsync(fd)
        finally:
            os.close(fd)
        _fsync_dir(directory)
    _fsync_dir(_host(root, UNIT_DIR))
    after = classify(observe(root, after_cursor=plan_cursor, owner=owner, **observe_kw))
    return {"result": "WRB_INSTALLED" if after["phase"] == WRB_1 else "WRB_INSTALLED_READBACK_NOT_WRB_1",
            "planDigest": digest, "planCursor": plan_cursor, "readBack": after, "reloadPerformedByTool": False,
            "witnessRestartedByTool": False,
            "next": "the owner's separate `systemctl daemon-reload` (own authorization), then `expect WRB_2`"}


def _fsync_dir(path: Path) -> None:
    if os.name != "posix":
        return
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


# ------------------------------------------------------- what other observations see ---
# The overlay is NOT invisible (as for P1B-10R): the PR-1A host observer reports `DropInPaths`, the drop-in entries
# and the unit-directory inventory, so every later host POST observer output differs by exactly these facts. The W9
# verifier and installer `status` also see `NeedDaemonReload=yes` between install and the owner's reload (WRB_1).

def expected_observer_changes() -> dict[str, Any]:
    return {
        "units.show.DropInPaths": {u: candidate_path(u) for u in UNITS},
        "units.enablementOrDropInEntries.added": sorted(candidate_path(u).lstrip("/") for u in UNITS),
        "namespaceInventory./etc/systemd/system.added": sorted(f"{u}.d" for u in UNITS),
    }


def observer_delta_reasons(pre: Mapping[str, Any], post: Mapping[str, Any]) -> list[str]:
    """Unexpected differences between two host observer `facts` documents (pre-install WRB_0, post-reload WRB_2).
    Clock values are ignored; every other change outside `expected_observer_changes` is a reason, including any
    change of the witness incarnation (InvocationID / MainPID / NRestarts are compared like every other fact)."""
    reasons: list[str] = []
    expected = expected_observer_changes()
    for section in sorted(set(pre) | set(post)):
        a, b = pre.get(section), post.get(section)
        if section == "host":
            a = {k: v for k, v in (a or {}).items() if k not in ("uptimeSeconds", "utcNow")}
            b = {k: v for k, v in (b or {}).items() if k not in ("uptimeSeconds", "utcNow")}
        elif section == "units":
            a, b = json.loads(json.dumps(a)), json.loads(json.dumps(b))
            for unit in UNITS:
                if ((a or {}).get("show", {}).get(unit) or {}).get("DropInPaths") != "":
                    reasons.append("PRE_DROPINPATHS_NOT_EMPTY:" + unit)
                if ((b or {}).get("show", {}).get(unit) or {}).get("DropInPaths") \
                        != expected["units.show.DropInPaths"][unit]:
                    reasons.append("POST_DROPINPATHS_NOT_EXACT:" + unit)
                for doc in (a, b):
                    (doc or {}).get("show", {}).get(unit, {}).pop("DropInPaths", None)
            pre_entries = (a or {}).pop("enablementOrDropInEntries", [])
            post_entries = (b or {}).pop("enablementOrDropInEntries", [])
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


# ----------------------------------------------------------------- DR-5 (synthetic) ---

# systemctl verbs that would print unit configuration or state (and so could change with the overlay).
READ_VERBS = frozenset({"show", "cat", "status", "list-dependencies", "list-units", "list-unit-files", "is-active",
                        "is-enabled", "is-failed", "get-default", "help"})


def prove_dr5_unaffected(script: bytes) -> dict[str, Any]:
    """The overlay adds no routine-deployer DR-5 line: no list of the pinned DR-5 script names a path at or beneath a
    witness overlay directory, the unit directory is a write-denied parent, and the script reads no unit property
    (its only `systemctl` uses are sudo-denial probes). So the W10_1 targets are unchanged by this stage."""
    import mb10_dr5_target as T10

    lists = T10.script_lists(script)
    for name, items in lists.items():
        for path in T10._paths(name, items):
            if any(path == f"{UNIT_DIR}/{u}.d" or path.startswith(f"{UNIT_DIR}/{u}.d/") for u in UNITS):
                raise Refused("DR5_OBSERVES_THE_OVERLAY", name)
    if UNIT_DIR not in lists["AB_PARENTS"]:
        raise Refused("UNIT_DIR_NOT_A_DENIED_PARENT")
    text = script.decode("utf-8")
    verbs = re.findall(r'^readonly AB_UNIT_VERBS="([^"]*)"$', text, flags=re.MULTILINE)
    if len(verbs) != 1 or set(verbs[0].split()) & READ_VERBS or not verbs[0].split():
        raise Refused("DR5_READS_UNIT_PROPERTIES")
    if any("systemctl" in line and "AB_SYSTEMCTL" not in line for line in text.splitlines()
           if not line.lstrip().startswith("#")):
        raise Refused("DR5_UNPINNED_SYSTEMCTL_USE")
    return {"dr5Delta": "EMPTY_PROVEN_FROM_PINNED_SCRIPT", "unitDirWriteDeniedParent": True,
            "unitPropertiesRead": False}


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
            out = plan()
        elif len(argv) == 3 and argv[0] == "install":
            out = install(argv[1], argv[2])
        elif len(argv) == 3 and argv[0] == "expect" and argv[1] in PHASES:
            out = classify(observe(after_cursor=argv[2]))
            sys.stdout.write(json.dumps(out, sort_keys=True, indent=2) + "\n")
            return 0 if out["phase"] == argv[1] else 1
        else:
            raise Refused("USAGE")
    except Refused as exc:
        print(f"e19_witness_restart_boundary_install: REFUSED {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(out, sort_keys=True, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
