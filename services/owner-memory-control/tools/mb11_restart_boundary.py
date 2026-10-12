"""LILITH 15B2b-B1b-3e M-B11 PR-A1: the CANDIDATE signer restart / socket-reactivation boundary (OD-M11-11, O2-D).

Control tooling (services/owner-memory-control/tools; outside the release-controlled services/authority-dev
tree), stdlib only. NOT release payload, NOT installed, NOT accepted. It holds:

- the two candidate drop-ins (`mb11_restart_boundary_dropins/`) and their pins;
- `check_effective`: the exact judgement of one unit's effective configuration (its `systemctl show` properties, its
  `DropInPaths` and the bytes of each drop-in). Any drop-in other than the pinned candidate and the host's recorded
  pre-existing set is a refusal; a missing, renamed, re-ordered or re-worded candidate is a refusal;
- `derive_probe_units`: synthetic probe units derived from the REAL release unit files, keeping every lifecycle,
  credential and socket directive verbatim and renaming only what must differ on a disposable runner.

    candidate drop-in != accepted configuration;  probe PASS on a runner != live proof on DEV
    effective property observed != drop-in provenance;  both are required
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, Mapping, Sequence

HERE = Path(__file__).resolve().parent
DROPIN_ROOT = HERE / "mb11_restart_boundary_dropins"
SERVICE_UNIT = "lilith-authority-dev.service"
SOCKET_UNIT = "lilith-authority-dev.socket"
UNIT_DIR = "/etc/systemd/system"

# Candidate drop-ins: unit -> (file name, SHA-256 of the exact bytes).
DROPINS = {
    SERVICE_UNIT: ("10-no-implicit-restart.conf", "e3faf9efa91f0238ee6110a33cf6c9f024aca1029fe05bd26fba4c21679c6b92"),
    SOCKET_UNIT: ("10-no-reactivation.conf", "85589f80764311f7e1152cf0e9ea51208662bce25806ceb524777961f579b9b9"),
}
# The effective properties each candidate must produce (`systemctl show -p ...` values).
EXPECTED_PROPERTIES = {
    SERVICE_UNIT: {"Restart": "no"},
    SOCKET_UNIT: {"StopWhenUnneeded": "yes", "RefuseManualStart": "yes"},
}
SHOW_PROPERTIES = {
    SERVICE_UNIT: ("Restart", "DropInPaths", "UnitFileState", "LoadState", "NeedDaemonReload"),
    SOCKET_UNIT: ("StopWhenUnneeded", "RefuseManualStart", "DropInPaths", "UnitFileState", "LoadState",
                  "NeedDaemonReload"),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def candidate_bytes(unit: str) -> bytes:
    name, pin = DROPINS[unit]
    data = (DROPIN_ROOT / f"{unit}.d" / name).read_bytes()
    if sha256(data) != pin:
        raise ValueError("CANDIDATE_DROPIN_PIN_MISMATCH:" + unit)
    return data


def parse_unit(text: str) -> list[tuple[str, str, str]]:
    """(section, key, value) in file order. Comments and blank lines are skipped; repeated keys are kept."""
    out: list[tuple[str, str, str]] = []
    section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if "=" not in line:
            raise ValueError("UNIT_LINE_NOT_KEY_VALUE:" + line)
        key, value = line.split("=", 1)
        out.append((section, key.strip(), value.strip()))
    return out


def check_effective(unit: str, show: Mapping[str, str], dropin_bytes: Mapping[str, bytes], *,
                    probe_unit: str | None = None, unit_dir: str = UNIT_DIR,
                    preexisting: Sequence[str] = ()) -> list[str]:
    """Refusal reasons for one unit's effective configuration; `[]` only for exactly the candidate.

    `probe_unit` is the name the candidate is installed under (the real name by default); `preexisting` is the
    host's own drop-in set recorded BEFORE the candidate was installed (e.g. distribution type-level drop-ins). It may
    never contain a path under the unit's own `.d` directory."""
    name, pin = DROPINS[unit]
    installed = probe_unit or unit
    own_dir = f"{unit_dir}/{installed}.d/"
    expected_path = own_dir + name
    reasons: list[str] = []
    if any(path.startswith(own_dir) for path in preexisting):
        reasons.append("PREEXISTING_SET_CONTAINS_UNIT_DROPIN")
    observed = (show.get("DropInPaths") or "").split()
    if sorted(observed) != sorted([*preexisting, expected_path]) or len(set(observed)) != len(observed):
        reasons.append("DROPIN_SET_NOT_EXACT")
    data = dropin_bytes.get(expected_path)
    if data is None:
        reasons.append("CANDIDATE_DROPIN_UNREAD")
    elif sha256(data) != pin:
        reasons.append("CANDIDATE_DROPIN_BYTES_NOT_PINNED")
    for path in dropin_bytes:
        if path != expected_path and path not in preexisting:
            reasons.append("FOREIGN_DROPIN_READ:" + path)
    for key, value in EXPECTED_PROPERTIES[unit].items():
        if show.get(key) != value:
            reasons.append(f"EFFECTIVE_{key.upper()}_NOT_{value.upper()}")
    if show.get("UnitFileState") not in ("static", ""):
        reasons.append("UNIT_ENABLEABLE_OR_ENABLED")
    if (show.get("LoadState"), show.get("NeedDaemonReload")) != ("loaded", "no"):
        reasons.append("UNIT_NOT_LOADED_CURRENT")
    return reasons


# ------------------------------------------------------------------ probe units ---
# Directives kept VERBATIM from the release units: everything that decides when the service runs, restarts, how its
# credential is delivered, and how the socket triggers it. Path-bearing sandbox directives that name LILITH paths
# absent on a runner are dropped (they do not influence activation); names and paths that must differ are rewritten.
SERVICE_VERBATIM = ("Requires", "After", "StartLimitIntervalSec", "StartLimitBurst", "Type", "StateDirectoryMode",
                    "UMask", "NoNewPrivileges", "PrivateTmp", "PrivateDevices", "ProtectSystem", "ProtectHome",
                    "ProtectKernelTunables", "ProtectKernelModules", "ProtectControlGroups", "RestrictNamespaces",
                    "LockPersonality", "CapabilityBoundingSet", "AmbientCapabilities", "RestrictAddressFamilies",
                    "IPAddressDeny", "Restart", "RestartSec", "TimeoutStartSec", "TimeoutStopSec")
SERVICE_REWRITTEN = ("Description", "User", "Group", "WorkingDirectory", "ExecStart", "LoadCredentialEncrypted",
                     "StateDirectory")
SERVICE_DROPPED = ("Environment", "ReadOnlyPaths", "ReadWritePaths", "InaccessiblePaths")
SOCKET_VERBATIM = ("Requires", "After", "Accept", "SocketUser", "SocketGroup", "SocketMode", "DirectoryMode",
                   "FlushPending", "RemoveOnStop", "Backlog", "TriggerLimitIntervalSec", "TriggerLimitBurst")
SOCKET_REWRITTEN = ("Description", "AssertPathIsDirectory", "ListenStream", "Service")
CREDENTIAL_NAME = "owner-actor-signing-key"


def probe_paths(name: str) -> dict[str, str]:
    return {"runtime": f"/run/{name}", "socket": f"/run/{name}/owner.sock", "state": name,
            "credential": f"/etc/{name}/credential.cred", "child": f"/usr/local/libexec/{name}/child.py",
            "control": f"/etc/{name}/mode"}


def derive_probe_units(service_text: str, socket_text: str, name: str, user: str) -> tuple[str, str, dict]:
    """Probe unit texts for `<name>.service` / `<name>.socket` and a report of what was kept, rewritten, dropped."""
    paths = probe_paths(name)
    rewrite = {
        "Description": f"LILITH M-B11 PR-A1 synthetic restart-boundary probe ({name}; never a LILITH unit)",
        "User": user, "Group": user, "WorkingDirectory": "/",
        "ExecStart": f"/usr/bin/python3 -I -B {paths['child']}",
        "LoadCredentialEncrypted": f"{CREDENTIAL_NAME}:{paths['credential']}",
        "StateDirectory": paths["state"],
    }
    socket_rewrite = {
        "Description": f"LILITH M-B11 PR-A1 synthetic restart-boundary probe socket ({name})",
        "AssertPathIsDirectory": paths["runtime"], "ListenStream": paths["socket"], "Service": f"{name}.service",
    }
    report: dict[str, list] = {"serviceVerbatim": [], "serviceRewritten": [], "serviceDropped": [],
                               "socketVerbatim": [], "socketRewritten": []}

    def build(text: str, verbatim: Iterable[str], rewritten: Mapping[str, str], dropped: Iterable[str], kind: str,
              translate: Mapping[str, str]) -> str:
        lines, section = [], None
        for sec, key, value in parse_unit(text):
            if sec != section:
                lines.append(("" if section is None else "\n") + f"[{sec}]")
                section = sec
            if key in verbatim:
                new = value
                for old, replacement in translate.items():
                    new = new.replace(old, replacement)
                lines.append(f"{key}={new}")
                report[kind + "Verbatim"].append([key, value, new])
            elif key in rewritten:
                lines.append(f"{key}={rewritten[key]}")
                report[kind + "Rewritten"].append([key, value, rewritten[key]])
            elif key in dropped:
                report[kind + "Dropped"].append([key, value])
            else:
                raise ValueError(f"UNCLASSIFIED_DIRECTIVE:{kind}:{key}")
        return "\n".join(lines) + "\n"

    translate = {SOCKET_UNIT: f"{name}.socket", SERVICE_UNIT: f"{name}.service"}
    service = build(service_text, SERVICE_VERBATIM, rewrite, SERVICE_DROPPED, "service", translate)
    socket = build(socket_text, SOCKET_VERBATIM, socket_rewrite, (), "socket", translate)
    return service, socket, report
