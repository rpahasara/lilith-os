#!/usr/bin/env python3
"""Fixed, read-only inspection of the consumed Stage-III A2 DEV dispatch.

Stream this protected-main source to ``python3 -I -B -``. It never imports or
executes installed control code and never invokes the snapshot observer (that
observer starts a transient systemd unit). Output is deliberately redacted.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

RUN_ID = "36145190507"
VAULT = Path("/var/lib/.lilith-memory-broker-stage3-a2")
SERVICE = "lilith-stage3-a2-final.service"
UNITS = (SERVICE, "lilith-stage3-a2-guard.service",
         "lilith-memory-broker.service", "lilith-memory-broker.socket")
PROPERTIES = ("LoadState", "ActiveState", "SubState", "Result", "ExecMainCode",
              "ExecMainStatus", "MainPID", "InvocationID", "NRestarts",
              "FragmentPath", "DropInPaths", "UnitFileState")
MARKERS = {
    "dispatchAttempt": Path("/var/lib/.lilith-memory-broker-stage3-a2-dispatch-attempt.json"),
    "finalAttempt": Path("/var/lib/.lilith-memory-broker-stage3-a2-final-attempt.json"),
    "authorization": Path("/etc/lilith-memory-broker/b1b2b-stage3-a2-authorization.json"),
    "authorizationUsed": Path("/etc/lilith-memory-broker/b1b2b-stage3-a2-authorization.used.json"),
    "arm": Path("/run/lilith-memory-stage3/a2-arm.json"),
}
EVIDENCE = ("accepted-dev.json", "fork-provenance.json", "guard.claim.json",
            "a2-arm-written.json", "a2-barrier.json", "a2-kill-attempt.json",
            "a2-kill-observed.json", "completed-evidence.json", "final-report.json")
PHASES = ("INTENT", "QUIESCED", "ACCEPTED_VAULTED", "FORK_READY",
          "BINDINGS_SWITCHED", "LIVENESS_BOUND", "CANDIDATE_ACTIVE",
          "EVIDENCE_SEALED", "RESTORE_QUIESCED", "EXPERIMENT_PRESERVED",
          "ACCEPTED_REBOUND", "RESTORED", "FAILED_INERT")
ACCEPTED = "817a83e44cec8965479fd97fc30b7a0b3ae49ab2"
CANDIDATE = "4a04f2d09a2b32aecedfe777090fd2e1a27ec909"
MANIFESTS = {
    "accepted": (ACCEPTED, "7a46ac83001411a29b1bc4be7e0f91f09c5879967386c452b2620e23d16e4614"),
    "candidate": (CANDIDATE, "784c60d39edbd67b86d670bf568c0d28a1a6eef202c5d19254ec0f6dc74da313"),
}
CONTROL_MANIFEST = Path("/opt/lilith-stage3-a2-final-v1/manifest.json")
CONTROL_SHA = "c9b8ea012ef82d9820f944d68f5eeae140b3249f7817dc4efd01e768b607eaa3"
MAX_FILE = 2 * 1024 * 1024
MAX_JOURNAL = 512 * 1024


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_fixed(path: Path, *, max_size: int = MAX_FILE,
               root_private: bool = False) -> bytes | None:
    """Read a fixed regular file without following its final symlink."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > max_size:
        raise ValueError("EVIDENCE_CUSTODY_OR_SIZE")
    if root_private and (info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600):
        raise ValueError("EVIDENCE_CUSTODY_OR_SIZE")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        if ((opened.st_dev, opened.st_ino, opened.st_size) !=
                (info.st_dev, info.st_ino, info.st_size)):
            raise ValueError("EVIDENCE_CHANGED_DURING_READ")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(max_size + 1)
        if len(raw) != info.st_size:
            raise ValueError("EVIDENCE_CHANGED_DURING_READ")
        return raw
    finally:
        os.close(fd)


def file_summary(path: Path) -> dict:
    try:
        raw = read_fixed(path)
        return {"present": raw is not None, **({"sha256": digest(raw), "bytes": len(raw)}
                                             if raw is not None else {})}
    except (OSError, ValueError):
        return {"present": True, "inspection": "UNAVAILABLE_OR_UNTRUSTED"}


def fixed_command(argv: list[str], *, max_bytes: int = 65536) -> bytes:
    result = subprocess.run(argv, capture_output=True, check=False, timeout=15)
    if result.returncode or len(result.stdout) > max_bytes:
        raise ValueError("READ_ONLY_COMMAND_UNAVAILABLE")
    return result.stdout


def unit_state(unit: str) -> dict:
    try:
        raw = fixed_command(["/usr/bin/systemctl", "show", unit,
                             "--property=" + ",".join(PROPERTIES), "--no-pager"])
        fields = dict(line.split("=", 1) for line in raw.decode("utf-8").splitlines()
                      if "=" in line)
        if set(fields) != set(PROPERTIES):
            raise ValueError("SYSTEMD_FIELDS_INCOMPLETE")
        return fields
    except (OSError, UnicodeError, ValueError, subprocess.TimeoutExpired):
        return {"inspection": "UNAVAILABLE"}


def phase_journal() -> dict:
    try:
        info = VAULT.lstat()
    except FileNotFoundError:
        return {"present": False, "terminalPhase": "UNKNOWN"}
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
        return {"present": True, "inspection": "UNTRUSTED_CUSTODY", "terminalPhase": "UNKNOWN"}
    try:
        names = sorted(item.name for item in VAULT.iterdir()
                       if re.fullmatch(r"\d{3}-[A-Z_]+\.json", item.name))
        if not names or len(names) > len(PHASES) + 1:
            raise ValueError("JOURNAL_SEQUENCE")
        previous = None
        sequence = []
        next_phases = {
            None: ("INTENT",), "INTENT": ("QUIESCED", "FAILED_INERT"),
            "QUIESCED": ("ACCEPTED_VAULTED", "FAILED_INERT"),
            "ACCEPTED_VAULTED": ("FORK_READY", "FAILED_INERT"),
            "FORK_READY": ("BINDINGS_SWITCHED", "FAILED_INERT"),
            "BINDINGS_SWITCHED": ("LIVENESS_BOUND", "FAILED_INERT"),
            "LIVENESS_BOUND": ("CANDIDATE_ACTIVE", "FAILED_INERT"),
            "CANDIDATE_ACTIVE": ("EVIDENCE_SEALED", "FAILED_INERT"),
            "EVIDENCE_SEALED": ("RESTORE_QUIESCED", "FAILED_INERT"),
            "RESTORE_QUIESCED": ("EXPERIMENT_PRESERVED", "FAILED_INERT"),
            "EXPERIMENT_PRESERVED": ("ACCEPTED_REBOUND", "FAILED_INERT"),
            "ACCEPTED_REBOUND": ("RESTORED", "FAILED_INERT"),
            "RESTORED": (), "FAILED_INERT": (),
        }
        last_phase = None
        historical_snapshot = None
        for index, name in enumerate(names):
            phase = name.split("-", 1)[1][:-5]
            if (not name.startswith(f"{index:03d}-") or phase not in PHASES
                    or phase not in next_phases[last_phase]):
                raise ValueError("JOURNAL_SEQUENCE")
            raw = read_fixed(VAULT / name, root_private=True)
            if raw is None or len(raw) > 262144:
                raise ValueError("JOURNAL_FILE")
            value = json.loads(raw)
            canonical = (json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False) + "\n").encode()
            if (raw != canonical or value.get("schema") != "Stage3A2TransitionJournalV1"
                    or value.get("phase") != phase or value.get("previousSha256") != previous
                    or not isinstance(value.get("record"), dict)):
                raise ValueError("JOURNAL_CHAIN")
            previous = digest(raw)
            sequence.append(phase)
            last_phase = phase
            if phase == "INTENT":
                candidate = value["record"].get("acceptedSnapshotSha256")
                if isinstance(candidate, str) and re.fullmatch(r"[0-9a-f]{64}", candidate):
                    historical_snapshot = candidate
        return {"present": True, "verifiedHashChain": True, "phases": sequence,
                "terminalPhase": sequence[-1], "lastRecordSha256": previous,
                "historicalAcceptedSnapshotSha256": historical_snapshot}
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
        return {"present": True, "inspection": "UNAVAILABLE_OR_INVALID",
                "terminalPhase": "UNKNOWN"}


def journal_metadata(invocation_id: str) -> dict:
    try:
        raw = fixed_command(["/usr/bin/journalctl", "--no-pager", "--output=json",
                             "--unit=" + SERVICE, "--boot", "-n", "256"],
                            max_bytes=MAX_JOURNAL)
        entries = []
        for line in raw.splitlines():
            item = json.loads(line)
            if item.get("_SYSTEMD_UNIT") != SERVICE:
                continue
            identity = item.get("_SYSTEMD_INVOCATION_ID", "")
            if invocation_id and identity != invocation_id:
                continue
            message = item.get("MESSAGE", "")
            if not isinstance(message, str):
                message = ""
            entries.append({"invocationId": identity,
                            "realtimeUsec": item.get("__REALTIME_TIMESTAMP"),
                            "errorCodes": sorted(set(re.findall(
                                r"\bSTAGE3_[A-Z0-9_]{3,100}\b", message))),
                            "messageSha256": digest(message.encode())})
        return {"entryCount": len(entries), "entries": entries}
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError,
            subprocess.TimeoutExpired):
        return {"inspection": "UNAVAILABLE_OR_TRUNCATED"}


def selector() -> dict:
    path = Path("/opt/lilith-memory-broker/current")
    try:
        target = os.readlink(path)
        return {"target": target if target in (f"releases/{ACCEPTED}",
                                                f"releases/{CANDIDATE}") else "UNRECOGNIZED"}
    except OSError:
        return {"target": "UNAVAILABLE"}


def inspect() -> dict:
    if os.geteuid() != 0 or os.getegid() != 0:
        raise ValueError("ROOT_REQUIRED_FOR_READ_ONLY_EVIDENCE")
    units = {name: unit_state(name) for name in UNITS}
    final = units[SERVICE]
    return {
        "schema": "Stage3A2ConsumedDispatchForensicsV1", "targetRunId": RUN_ID,
        "operation": "READ_ONLY_INSPECTION", "units": units,
        "serviceJournal": journal_metadata(final.get("InvocationID", "")),
        "phaseJournal": phase_journal(),
        "markers": {name: file_summary(path) for name, path in MARKERS.items()},
        "evidence": {name: file_summary(VAULT / name) for name in EVIDENCE},
        "selector": selector(),
        "releaseManifests": {name: {**file_summary(Path("/opt/lilith-memory-broker/releases") /
                                                   release / "release-manifest.json"),
                                     "expectedSha256": expected}
                             for name, (release, expected) in MANIFESTS.items()},
        "controlManifest": {**file_summary(CONTROL_MANIFEST),
                            "expectedSha256": CONTROL_SHA},
        "acceptedStateObserver": "NOT_RUN_STARTS_TRANSIENT_SYSTEMD_UNIT",
        "conclusion": "INSPECTION_ONLY_NO_REPAIR_OR_RETRY",
    }


if __name__ == "__main__":
    if sys.argv != ["-"]:
        raise SystemExit("FIXED_STDIN_ENTRYPOINT_ONLY")
    try:
        print(json.dumps(inspect(), sort_keys=True, separators=(",", ":")))
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from None
