#!/usr/bin/env python3
"""15B2b-B1b-3e M-B11 (START_SIGNER): READ-ONLY post-start host verifier and W11 classifier (DEV).

Record: docs/architecture/slice-15b2b-b1b3e-mb11-signer-start-design.md.
DESIGN / SOURCE ONLY. Running it live needs a separate owner authorization. Live M-B11 startup is BLOCKED until a
proven restart and socket-reactivation bound exists (record §6, OD-M11-11).

M-B11 is the first start of `lilith-authority-dev.service` (not enabled), after the accepted INITIAL_CUSTODY HELD.
systemd decrypts K-ACT (`LoadCredentialEncrypted=`) into `/run/credentials/lilith-authority-dev.service` on EVERY
service exec attempt, before the signer's Python runs. One owner go, one operator invocation and one K-ACT load are
therefore different counts; this verifier counts loads from the journal and never infers them from a go.

The accepted W10 verifier (`mb10_held_verifier.py`, pinned, UNCHANGED) classifies any signer activity as
`W10_SIGNER_OR_LATER_STATE`. This verifier does not reinterpret that. It reports the unchanged W10 judgement as
`w10PhaseDirect` and, separately, runs the SAME W10 code with only the signer side judged here
(`w10PhaseSignerJudgedSeparately`): the two signer runtime paths read as absent and the two signer units as inactive,
static and loaded. The substitution must be consulted, or the result is UNCLASSIFIED. The signer side itself is
judged here from root observations:

- unit facts (`systemctl show` only), the credentials directory (names and metadata only; never opened), the owner
  socket metadata, the process command line and identity (`/proc/<pid>`), and the journal invocation set;
- the signer HEALTH, as SUPPLIED evidence captured elsewhere and bound to the InvocationID / MainPID before and after
  the capture. HEALTH is a signer self-claim (B4). THIS VERIFIER NEVER OPENS, CONNECTS TO OR BINDS ANY SOCKET: a
  connection to the owner socket while the service is inactive would start it and load K-ACT;
- the two root readiness evaluations (HOLD_RELEASE_ELIGIBILITY and FULL_READINESS), computed by the release's own
  root verifier over the SAME captured HEALTH (`readiness_pair`), never by the signer;
- the ledger directory bytes (`observe_ledger_bytes`): the logical ledger is the W9 / M-B6 judgement (unchanged);
  byte equality and sidecar residue are judged here;
- the effective restart boundary (PR-A2, `mb11_restart_boundary_install.boundary_reasons`): the release fragments plus
  exactly the pinned owner overlay, with `Restart=no`, `StopWhenUnneeded=yes`, `RefuseManualStart=yes` in effect.
  Every exact W11 phase requires it; unobserved is UNKNOWN, inexact is `W11_UNEXPECTED_UNIT_STATE`.

    signer started != signer verified != readiness != signing permission != Registry effective != authority
    HEALTH (B4) = a claim;  B1 = B2 = B3 = B4 (+ B5, B6) = the binding;  root readiness != owner acceptance
    stopped after the first K-ACT load != W10_1 (the load is a permanent custody fact);  UNKNOWN != success

Forms (root, DEV, release interpreter; design only):

    ... observe <evidence.json>       one read-only observation and judgement
    ... classify <observation.json>   the pure judgement of a recorded observation (off-host, stdlib only)
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

VERIFIER_TYPE = "LILITH_MB11_SIGNER_VERIFICATION"
ENVIRONMENT = "dev"
SIGNER_SERVICE = "lilith-authority-dev.service"
SIGNER_SOCKET_UNIT = "lilith-authority-dev.socket"
SIGNER_UNITS = (SIGNER_SERVICE, SIGNER_SOCKET_UNIT)
SIGNER_CREDENTIALS = "/run/credentials/lilith-authority-dev.service"
SIGNER_OWNER_SOCKET = "/run/lilith-authority-dev/owner.sock"
CREDENTIAL_NAME = "owner-actor-signing-key"
LEDGER_STATE_DIR = "/var/lib/lilith-authority-dev"
LEDGER_NAME = "authority_ledger.db"
WAL_NAME = LEDGER_NAME + "-wal"
SHM_NAME = LEDGER_NAME + "-shm"
RELEASE_SHA = "ba943e1a188d98f4108c9eec7149c0cf1a8f68bb"   # E-19 U5 (completion record); was the E-19 OLD release
RELEASE_CWD = "/opt/lilith-authority-dev/releases/" + RELEASE_SHA     # WorkingDirectory=…/current, resolved
EXEC_ARGV = ("/opt/lilith-authority-dev/current/venv/bin/python", "-B", "-m", "lilith_authority_dev.server")
MAX_LEDGER = 64 * 1024 * 1024
SYSTEMCTL = "/usr/bin/systemctl"
JOURNALCTL = "/usr/bin/journalctl"
FIXED_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "HOME": "/nonexistent"}
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")

# The accepted custody bindings (repository records; never host values).
KACT_KEY_ID = "test-only.dev-synthetic.actor.b1b3d.1"
B3_PUBLIC_KEY_SHA256 = "dd13a1fb302375a4e7ec81131a72920e23e365e06a0b6dc9bb7ab124dadc01ed"   # M-B3 completion
B2_CURRENT_BLOB_SHA256 = "6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3"  # preflight B-5 / §24
KACT_PUBLICATION_FILE_SHA256 = "d76479762007afef828f3901591647dc4a2fb2205f4afac527b66d2cc9c6b032"

# OD-M11-1 (PROPOSED). H: the exact signer HEALTH (a claim). E: root HOLD_RELEASE_ELIGIBILITY READY. F: root
# FULL_READINESS NOT_READY with exactly the hold reason. G: no authority anywhere.
HEALTH_FIELDS = frozenset({"profile", "signingDomain", "foundation", "service", "credential", "publicKeySha256",
                           "signing", "readiness", "reasons"})
HEALTH_EXACT = {"profile": "DEV_SYNTHETIC", "signingDomain": "OWNER_ACTOR", "foundation": "B1B3D_L1_SOURCE_FOUNDATION",
                "service": "SERVICE_AVAILABLE", "credential": "CREDENTIAL_PRESENT_UNVERIFIED",
                "signing": "SIGNING_NOT_AVAILABLE", "readiness": "NOT_READY"}
STRUCTURAL_REASONS = ("CREDENTIAL_INVENTORY_UNOBSERVABLE_BY_SIGNER", "HOLD_STORE_UNOBSERVABLE_BY_SIGNER",
                      "ISSUANCE_UNWIRED")
EXPECTED_FULL_REASONS = ("CEREMONY_HOLD:CEREMONY_HOLD_HELD",)
FULL_HOLD_DETAIL = "INITIAL_CUSTODY_BOOTSTRAP"
CREDENTIAL_FAILURE_STATES = ("CREDENTIAL_ABSENT", "CREDENTIAL_INVALID")
# `rotation_contracts.verify_loaded_key_binding` reasons that mean the loaded key is not the custodied one.
KEY_MISMATCH_REASONS = frozenset({"HEALTH_FINGERPRINT_MISMATCH", "PUBLICATION_KEY_MISMATCH", "BLOB_HASH_MISMATCH",
                                  "INVENTORY_CURRENT_BLOB_MISMATCH", "PUBLICATION_FINGERPRINT_INVALID"})
CREDENTIAL_EXIT_STATUSES = frozenset({"3", "4", "243"})        # server.EXIT_CREDENTIAL_*; systemd 243/CREDENTIALS
DARK_FACTS = ("authorityGranted", "liveEntryAuthorized", "issuanceReady", "successorCurrent")
DARK_PACKAGE_FLAGS = ("authorityGranted", "activationGranted", "issuanceWired")
UNIT_PROPERTIES = ("Id", "LoadState", "ActiveState", "SubState", "UnitFileState", "NeedDaemonReload", "MainPID",
                   "NRestarts", "InvocationID", "Result", "ExecMainStatus", "FragmentPath", "DropInPaths", "Restart",
                   "StopWhenUnneeded", "RefuseManualStart")
# The W10 view of the signer side while it is judged here (W9 / W10 code unchanged).
MASKED_UNIT = {"LoadState": "loaded", "UnitFileState": "static", "NeedDaemonReload": "no", "ActiveState": "inactive",
               "SubState": "dead", "MainPID": "0", "NRestarts": "0", "InvocationID": "", "Result": "success"}

# ------------------------------------------------------------------ phases ---
W11_0 = "W11_0_PRE_SIGNER_EXACT"                     # W10_1 exact; boundary effective; never started; no load recorded
W11_1 = "W11_1_SIGNER_STARTED_EXACT"                 # W10_1 (signer judged here); one load; H, E, F, G exact
W11_1S = "W11_1S_STOPPED_AFTER_FIRST_LOAD"           # W10_1 (signer judged here); signer stopped after exactly one load
W11_HOLD = "W11_HOLD_NOT_EXACT"                      # any W10 hold HALT: malformed, misbound, unexpected, foreign
W11_LEDGER = "W11_LEDGER_CHANGED"                    # logical ledger not exact, WAL frames, or DB bytes changed
W11_KEY = "W11_KEY_MISMATCH"                         # the loaded key is not the custodied K-ACT (B4 != B3 or binding)
W11_CREDENTIAL = "W11_CREDENTIAL_FAILED"             # decrypt failure (243), credential absent / invalid (exit 3 / 4)
W11_DARK = "W11_AUTHORITY_NOT_DARK"                  # HEALTH READY, signing available, or any authority flag true
W11_WITNESS = "W11_WITNESS_NOT_EXACT"                # the witness side is not exact, stopped, or another incarnation
W11_RESTART = "W11_RESTARTED_OR_INCARNATION_CHANGED"  # more than one load, restarts, or HEALTH from another incarnation
W11_START = "W11_START_FAILED_OR_AMBIGUOUS"          # failed, activating, auto-restart, or signer state without a load
W11_UNIT = "W11_UNEXPECTED_UNIT_STATE"               # enabled, unloaded, reload pending, socket-only, wrong process
W11_HEALTH = "W11_UNEXPECTED_HEALTH"                 # HEALTH fields or reasons not exactly H
W11_READINESS = "W11_READINESS_NOT_EXPECTED"         # E not READY, or F not exactly the hold reason
W11_RESIDUE = "W11_LEDGER_SIDECAR_RESIDUE"           # an empty WAL / shm left by an interrupted reader
UNCLASSIFIED = "UNCLASSIFIED_STOP"
HOST_PHASES = (W11_0, W11_1, W11_1S, W11_HOLD, W11_LEDGER, W11_KEY, W11_CREDENTIAL, W11_DARK, W11_WITNESS,
               W11_RESTART, W11_START, W11_UNIT, W11_HEALTH, W11_READINESS, W11_RESIDUE, UNCLASSIFIED)
# Precedence (record §7): HALT facts first (in this order), then UNKNOWN, then the STOP classes (in this order),
# then the exact phases. A proven HALT is reported even when other parts are unknown.
HALT_PHASES = (W11_HOLD, W11_LEDGER, W11_KEY, W11_CREDENTIAL, W11_DARK)
STOP_PHASES = (W11_WITNESS, W11_RESTART, W11_START, W11_UNIT, W11_HEALTH, W11_READINESS, W11_RESIDUE)

PROCEED_BY_GATE_AND_GO = "PROCEED_BY_GATE_AND_GO_ONLY_AFTER_RESTART_BOUND_PROVEN"
SAFE_ADOPT = "SAFE_ADOPT"
FORWARD_ONLY_STOPPED = "FORWARD_ONLY_RESTART_NEEDS_NEW_GO"
STOP_REVALIDATE = "STOP_REVALIDATE"
STOP_OWNER_ADJUDICATION = "STOP_OWNER_ADJUDICATION"
HALT = "HALT_PENDING_OWNER_ADJUDICATION"
PHASE_TABLE = {
    W11_0: (PROCEED_BY_GATE_AND_GO, "the M-B11 start may run only under an exact gate and a separate one-attempt go, "
                                    "and only after the restart / socket-reactivation bound is proven (OD-M11-11)"),
    W11_1: (SAFE_ADOPT, "read-only POST11, then the owner acceptance; authorizes nothing further"),
    W11_1S: (FORWARD_ONLY_STOPPED, "K-ACT was loaded once: this is never W10_1; any restart is a new load and needs "
                                   "a new go"),
    W11_HOLD: (HALT, "RR-40: no tool acts on the hold store"),
    W11_LEDGER: (HALT, "the ledger moved or its bytes changed: no tool repairs it"),
    W11_KEY: (HALT, "custody incident: the loaded key is not the custodied K-ACT; stop the signer by the pre-authorized "
                    "safe stop only (OD-M11-4); no retry"),
    W11_CREDENTIAL: (HALT, "the credential did not load as the custodied K-ACT: the attempt is consumed; no retry"),
    W11_DARK: (HALT, "authority darkness not observed: no tool acts"),
    W11_WITNESS: (STOP_REVALIDATE, "the witness side is not the accepted one: no M-B11 evidence is valid"),
    W11_RESTART: (STOP_OWNER_ADJUDICATION, "more than one K-ACT load or another incarnation: the attempt is consumed"),
    W11_START: (STOP_OWNER_ADJUDICATION, "the start did not reach one exact running incarnation"),
    W11_UNIT: (STOP_OWNER_ADJUDICATION, "unit or process facts are not the accepted ones"),
    W11_HEALTH: (STOP_OWNER_ADJUDICATION, "HEALTH is not exactly H"),
    W11_READINESS: (STOP_OWNER_ADJUDICATION, "root readiness is not exactly E and F"),
    W11_RESIDUE: (STOP_OWNER_ADJUDICATION, "an interrupted reader left sidecars: owner adjudication, never removal"),
    UNCLASSIFIED: (STOP_OWNER_ADJUDICATION, "UNKNOWN is never absence and never success"),
}


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _host(root: Path, absolute: str) -> Path:
    return root / absolute.lstrip("/")


# --------------------------------------------------------------- the journal ---
LOADED = "LOADED"
FAILED = "FAILED"
UNKNOWN = "UNKNOWN"
_CREDENTIAL_FAILURE_MARKERS = ("Failed to set up credentials", "status=243/CREDENTIALS", "243/CREDENTIALS")


def parse_journal(lines: Sequence[str]) -> dict[str, Any]:
    """The signer service's invocations from `journalctl -o json` lines (one JSON object per line), in order.
    An invocation is LOADED once its process ran (a message from the service process, or systemd's start line),
    FAILED on a credential setup failure, else UNKNOWN. The exact live message set is a systemd-runner proof
    obligation (record §6); unknown text is never success."""
    order: list[str] = []
    seen: dict[str, dict[str, Any]] = {}
    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            return {"readable": False, "invocations": [], "reason": "JOURNAL_LINE_NOT_JSON"}
        if not isinstance(entry, dict):
            return {"readable": False, "invocations": [], "reason": "JOURNAL_LINE_NOT_OBJECT"}
        invocation = entry.get("_SYSTEMD_INVOCATION_ID") or entry.get("INVOCATION_ID")
        if not isinstance(invocation, str) or _HEX32.fullmatch(invocation) is None:
            continue
        message = entry.get("MESSAGE")
        message = message if isinstance(message, str) else ""
        record = seen.setdefault(invocation, {"id": invocation, "credentials": UNKNOWN})
        if invocation not in order:
            order.append(invocation)
        if any(marker in message for marker in _CREDENTIAL_FAILURE_MARKERS):
            record["credentials"] = FAILED
        elif record["credentials"] == UNKNOWN and (entry.get("_COMM") not in (None, "systemd")
                                                   or message.startswith("Started ")):
            record["credentials"] = LOADED
    return {"readable": True, "invocations": [seen[i] for i in order]}


def journal_invocations(cursor: str | None, *, run: Callable[..., Any] = subprocess.run) -> dict[str, Any]:
    """The invocations after `cursor` (the baseline). A cursor journald no longer has is UNKNOWN, never empty."""
    argv = [JOURNALCTL, "-u", SIGNER_SERVICE, "-o", "json", "--no-pager", "--quiet"]
    if cursor is not None:
        if not isinstance(cursor, str) or not cursor or any(c.isspace() for c in cursor):
            return {"readable": False, "invocations": [], "reason": "CURSOR_INVALID"}
        argv.append("--after-cursor=" + cursor)
    result = run(argv, env=FIXED_ENV, capture_output=True, text=True, timeout=60, check=False)
    if result.returncode != 0:
        return {"readable": False, "invocations": [], "reason": f"JOURNALCTL_EXIT_{result.returncode}"}
    return parse_journal(result.stdout.splitlines())


# ------------------------------------------------------------ signer facts ---

def _units(names: Sequence[str], *, run: Callable[..., Any] = subprocess.run) -> dict[str, dict[str, str]]:
    result = run([SYSTEMCTL, "show", "-p", ",".join(UNIT_PROPERTIES), "--no-pager", "--", *names], env=FIXED_ENV,
                 capture_output=True, text=True, timeout=30, check=False)
    if result.returncode != 0:
        raise Refused("UNITS_UNREADABLE")
    out: dict[str, dict[str, str]] = {}
    for block in result.stdout.strip().split("\n\n"):
        facts = dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
        if facts.get("Id") in names:
            out[facts["Id"]] = facts
    if set(out) != set(names):
        raise Refused("UNITS_INCOMPLETE")
    return out


def _path_facts(path: Path, *, names: bool = False) -> dict[str, Any]:
    try:
        meta = os.lstat(path)
    except FileNotFoundError:
        return {"present": False}
    kind = ("dir" if stat.S_ISDIR(meta.st_mode) else "socket" if stat.S_ISSOCK(meta.st_mode)
            else "file" if stat.S_ISREG(meta.st_mode) else "other")
    facts: dict[str, Any] = {"present": True, "kind": kind, "uid": meta.st_uid, "gid": meta.st_gid,
                             "mode": stat.S_IMODE(meta.st_mode)}
    if names and kind == "dir":
        facts["names"] = sorted(os.listdir(path))           # names only: no credential is ever opened
    return facts


def _process(root: Path, pid: str) -> dict[str, Any] | None:
    if not pid.isdigit() or pid in ("0", "1"):
        return None
    proc = _host(root, f"/proc/{pid}")
    try:
        meta = os.stat(proc)
        cwd = os.readlink(proc / "cwd")
        argv = (proc / "cmdline").read_bytes().split(b"\0")
    except OSError:
        return None
    return {"cwd": cwd, "argv": [part.decode("utf-8", "replace") for part in argv if part], "uid": meta.st_uid,
            "gid": meta.st_gid}


def observe_signer(root: Path | str = Path("/"), *, units: Callable[[Sequence[str]], dict] | None = None,
                   process: Callable[[Path, str], dict | None] | None = None) -> dict[str, Any]:
    """Root observations of the signer side. Never a socket, never a credential read."""
    root = Path(root)
    try:
        facts = (units or _units)(SIGNER_UNITS)
        unit_facts = {name: {key: str(facts[name].get(key, "")) for key in UNIT_PROPERTIES} for name in SIGNER_UNITS}
    except (Refused, KeyError, OSError, subprocess.SubprocessError):
        unit_facts = None
    pid = unit_facts[SIGNER_SERVICE]["MainPID"] if unit_facts else "0"
    return {"units": unit_facts,
            "paths": {"credentials": _path_facts(_host(root, SIGNER_CREDENTIALS), names=True),
                      "ownerSocket": _path_facts(_host(root, SIGNER_OWNER_SOCKET))},
            "process": (process or _process)(root, pid)}


# ------------------------------------------------------------- ledger bytes ---

def observe_ledger_bytes(root: Path | str = Path("/")) -> dict[str, Any]:
    """Listing (names, sizes) and the DB SHA-256 of the ledger directory, read through `O_NOFOLLOW`. Never opens the
    database: the logical ledger is the unchanged W9 / M-B6 judgement."""
    state = _host(Path(root), LEDGER_STATE_DIR)
    try:
        names = sorted(os.listdir(state))
        listing = {}
        for name in names:
            meta = os.lstat(state / name)
            listing[name] = meta.st_size if stat.S_ISREG(meta.st_mode) else -1
        fd = os.open(state / LEDGER_NAME, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
        try:
            data = os.read(fd, MAX_LEDGER + 1)
        finally:
            os.close(fd)
    except OSError as exc:
        return {"readable": False, "reason": type(exc).__name__}
    if len(data) > MAX_LEDGER:
        return {"readable": False, "reason": "LEDGER_TOO_LARGE"}
    return {"readable": True, "listing": listing, "dbSha256": hashlib.sha256(data).hexdigest()}


# ---------------------------------------------------------- root readiness ---

def _summary(result: Any) -> dict[str, Any]:
    readiness = getattr(result, "readiness", None)
    if readiness is None:
        return {"status": "INPUT_MISSING", "reasons": ["READINESS_INPUT_MISSING"], "holdDetail": None,
                "loadedKeyBinding": None, "facts": {}, "packageFlags": {}}
    hold = readiness.checks.get("CEREMONY_HOLD")
    binding = readiness.checks.get("LOADED_KEY_BINDING")
    package = getattr(result, "package", {}) or {}
    return {"status": readiness.status, "reasons": list(readiness.reasons),
            "holdDetail": None if hold is None else hold.detail,
            "loadedKeyBinding": None if binding is None else {"status": binding.status, "reason": binding.reason,
                                                              "detail": binding.detail},
            "facts": {key: readiness.facts.get(key) for key in DARK_FACTS},
            "packageFlags": {key: package.get(key) for key in DARK_PACKAGE_FLAGS},
            "packageReasons": list(getattr(result, "reasons", ()))}


def readiness_pair(owner_document: Mapping[str, Any], health: Mapping[str, Any] | None, *,
                   root: Path | str = Path("/"), owner_uid: int = 0, owner_gid: int = 0,
                   run: Callable[..., Any] | None = None) -> dict[str, Any]:
    """E and F: the release's own root verifier in both modes over the SAME captured HEALTH and one complete hold
    observation. `health=None` is the stopped signer (the binding input B4 is missing). The PR-1 package reasons are
    recorded, never judged here (M-B12 / M-B13 own them)."""
    from lilith_authority_root import observers as O
    from lilith_authority_root import verifier as RV
    from lilith_authority_root.hold_store import HoldStoreV1
    from lilith_owner_memory import successor_readiness as SR

    owner = RV.parse_verifier_inputs(owner_document)
    captured = None if health is None else dict(health)

    def supplied() -> Mapping[str, Any]:
        if captured is None:
            raise OSError("signer HEALTH not captured")
        return dict(captured)

    root = Path(root)
    hold = HoldStoreV1(environment=owner.environment, root=root, owner_uid=owner_uid, owner_gid=owner_gid).observe()
    out = {}
    for name, mode in (("eligibility", SR.HOLD_RELEASE_ELIGIBILITY), ("full", SR.FULL_READINESS)):
        result = RV.evaluate(mode, owner, root=root, owner_uid=owner_uid, owner_gid=owner_gid, health=supplied,
                             run=run or O.default_runner, hold=hold)
        out[name] = _summary(result)
    out["holdListingDigest"] = hold.listing_digest
    return out


# ------------------------------------------------------- W10 with the signer side judged here ---

@contextlib.contextmanager
def signer_side_judged_separately(root: Path) -> Iterator[list[str]]:
    """Run the UNCHANGED W9 / W10 judgement with only the signer side handed to this verifier: the two signer runtime
    paths read as absent. The units view is masked by `masked_units`. The caller requires both paths consulted."""
    import mb6_ledger_verifier as V6

    original = V6._lstat
    masked = {_host(root, SIGNER_CREDENTIALS), _host(root, SIGNER_OWNER_SOCKET)}
    consulted: list[str] = []

    def lstat(path):
        if Path(path) in masked:
            consulted.append(str(path))
            return None
        return original(path)

    V6._lstat = lstat
    try:
        yield consulted
    finally:
        V6._lstat = original


def masked_units(units: Callable[[Sequence[str]], dict], consulted: list[str]) -> Callable[[Sequence[str]], dict]:
    def view(names):
        facts = units([name for name in names if name not in SIGNER_UNITS])
        out = dict(facts)
        for name in names:
            if name in SIGNER_UNITS:
                consulted.append(name)
                out[name] = {"Id": name, **MASKED_UNIT}
        return out
    return view


def w10_signer_masked(expected_head: str, candidate_digest: str, updated_at: str, *, root: Path,
                      units: Callable[[Sequence[str]], dict] | None = None, w10: Callable[..., dict] | None = None,
                      **w10_seams: Any) -> dict[str, Any]:
    import mb10_held_verifier as V10
    import mb9_witness_verifier as V9

    w10 = w10 or V10.evaluate
    base_units = units or V9._units
    direct = w10(expected_head, candidate_digest, updated_at, root=root, units=base_units, **w10_seams)
    unit_consults: list[str] = []
    with signer_side_judged_separately(root) as path_consults:
        separate = w10(expected_head, candidate_digest, updated_at, root=root,
                       units=masked_units(base_units, unit_consults), **w10_seams)
    exact = (set(path_consults) == {str(_host(root, SIGNER_CREDENTIALS)), str(_host(root, SIGNER_OWNER_SOCKET))}
             and set(unit_consults) == set(SIGNER_UNITS))
    return {"phase": separate.get("phase"), "direct": direct.get("phase"), "maskExact": exact,
            "holdClass": separate.get("holdClass"), "committedGenesisDigest": separate.get("committedGenesisDigest"),
            "observedHeldSha256": separate.get("observedHeldSha256"),
            "witnessInvocationId": separate.get("witnessInvocationId"),
            "witnessMainPid": separate.get("witnessMainPid"), "witnessNRestarts": separate.get("witnessNRestarts"),
            "w9Failures": list(separate.get("w9Failures") or []), "failures": list(separate.get("failures") or [])}


# ---------------------------------------------------------------- classify ---
W10_1 = "W10_1_HELD_EXACT"
W10_1S = "W10_1S_HELD_EXACT_WITNESS_STOPPED"
W10_WITNESS = "W10_WITNESS_NOT_EXACT"
W10_HALTS = ("W10_HOLD_RECORD_MALFORMED", "W10_HELD_MISBOUND", "W10_HOLD_SET_UNEXPECTED", "W10_FOREIGN_OR_UNSAFE")
W10_HOLD_HALT_CLASSES = ("MALFORMED", "MISBOUND", "UNEXPECTED_SET", "UNSAFE")
W10_PHASES = ("W10_0_PRE_HELD_EXACT", W10_1, W10_1S, "W10_P_SCRATCH_RESIDUE_NOT_HELD", *W10_HALTS, W10_WITNESS,
              "W10_SIGNER_OR_LATER_STATE", "UNCLASSIFIED_STOP")


def _signer_state(units: Mapping[str, Mapping[str, str]], paths: Mapping[str, Any]) -> str:
    service, socket_unit = units[SIGNER_SERVICE], units[SIGNER_SOCKET_UNIT]
    states = (service.get("ActiveState"), service.get("SubState"), socket_unit.get("ActiveState"))
    present = paths["credentials"].get("present") or paths["ownerSocket"].get("present")
    if states == ("active", "running", "active") and socket_unit.get("SubState") in ("listening", "running"):
        return "RUNNING"
    if states[0] == "inactive" and states[2] == "inactive" and service.get("Result") == "success" and not present:
        return "STOPPED"
    if states[0] == "inactive" and states[2] == "active":
        return "SOCKET_ONLY"
    return "ABNORMAL"


def classify(observation: Mapping[str, Any]) -> dict[str, Any]:
    """The W11 phase of one observation (pure). See the record §7 for the precedence."""
    reasons: list[str] = []
    obs = observation if isinstance(observation, Mapping) else {}
    w10 = obs.get("w10") or {}
    units = obs.get("units")
    paths = obs.get("paths") or {}
    journal = obs.get("journal") or {}
    capture = obs.get("health")
    readiness = obs.get("readiness")
    ledger = obs.get("ledger") or {}
    baseline = obs.get("baseline") or {}
    first_load_recorded = obs.get("firstLoadRecorded")
    health = capture.get("health") if isinstance(capture, Mapping) else None
    invocations = journal.get("invocations") if journal.get("readable") is True else None
    halts: list[str] = []
    unknown: list[str] = []
    stops: list[str] = []

    # ---- HALT facts
    if w10.get("phase") in W10_HALTS or w10.get("holdClass") in W10_HOLD_HALT_CLASSES:
        halts.append(W11_HOLD)
        reasons.append("HOLD:" + str(w10.get("holdClass")))
    w9_failures = [str(f) for f in w10.get("w9Failures") or []]
    listing = ledger.get("listing") if ledger.get("readable") is True else None
    if any(f == "BASE_NOT_EXACT:ledgerExact" or f.startswith(("LEDGER_CONTENT:", "LEDGER_IMAGE_")) for f in w9_failures):
        halts.append(W11_LEDGER)
        reasons.append("LEDGER_LOGICAL_NOT_EXACT")
    if listing is not None:
        if listing.get(WAL_NAME, 0) not in (0,) or set(listing) - {LEDGER_NAME, WAL_NAME, SHM_NAME}:
            halts.append(W11_LEDGER)
            reasons.append("LEDGER_WAL_FRAMES_OR_FOREIGN_ENTRY")
        elif set(listing) == {LEDGER_NAME} and baseline.get("dbSha256") is not None \
                and ledger.get("dbSha256") != baseline.get("dbSha256"):
            halts.append(W11_LEDGER)
            reasons.append("LEDGER_DB_BYTES_CHANGED")
    if isinstance(health, Mapping) and health.get("credential") == HEALTH_EXACT["credential"] \
            and health.get("publicKeySha256") != B3_PUBLIC_KEY_SHA256:
        halts.append(W11_KEY)
        reasons.append("HEALTH_FINGERPRINT_NOT_B3")
    eligibility = readiness.get("eligibility") if isinstance(readiness, Mapping) else None
    binding = (eligibility or {}).get("loadedKeyBinding") or {}
    if binding.get("reason") in KEY_MISMATCH_REASONS:
        halts.append(W11_KEY)
        reasons.append("BINDING:" + str(binding.get("reason")))
    exit_status = units[SIGNER_SERVICE].get("ExecMainStatus") if units else None
    if (invocations is not None and any(i.get("credentials") == FAILED for i in invocations)) \
            or (isinstance(health, Mapping) and health.get("credential") in CREDENTIAL_FAILURE_STATES) \
            or (units and units[SIGNER_SERVICE].get("Result") == "exit-code" and exit_status in CREDENTIAL_EXIT_STATUSES):
        halts.append(W11_CREDENTIAL)
        reasons.append("CREDENTIAL_NOT_LOADED_AS_CUSTODIED")
    dark_broken = isinstance(health, Mapping) and (health.get("readiness") != "NOT_READY"
                                                   or health.get("signing") != "SIGNING_NOT_AVAILABLE")
    if isinstance(readiness, Mapping):
        for mode in ("eligibility", "full"):
            summary = readiness.get(mode) or {}
            if any((summary.get("facts") or {}).get(k) is True for k in ("authorityGranted", "liveEntryAuthorized")) \
                    or any((summary.get("packageFlags") or {}).get(k) is True for k in DARK_PACKAGE_FLAGS):
                dark_broken = True
        full_facts = (readiness.get("full") or {}).get("facts") or {}
        if full_facts.get("issuanceReady") is True or full_facts.get("successorCurrent") is True:
            dark_broken = True
    if dark_broken:
        halts.append(W11_DARK)
        reasons.append("AUTHORITY_NOT_DARK")

    # ---- UNKNOWN
    if units is None:
        unknown.append("UNITS_UNREADABLE")
    if invocations is None:
        unknown.append("JOURNAL_UNREADABLE")
    if w10.get("maskExact") is not True:
        unknown.append("W10_SIGNER_SEAM_NOT_EXACT")
    if w10.get("phase") not in W10_PHASES or w10.get("phase") == "UNCLASSIFIED_STOP":
        unknown.append("W10_UNCLASSIFIED")
    if listing is None:
        unknown.append("LEDGER_UNREADABLE")
    if not isinstance(first_load_recorded, bool):
        unknown.append("FIRST_LOAD_RECORD_UNKNOWN")
    boundary = obs.get("restartBoundary")
    if not isinstance(boundary, Mapping) or not isinstance(boundary.get("reasons"), list):
        unknown.append("RESTART_BOUNDARY_UNOBSERVED")
    for key in ("dbSha256", "witnessInvocationId", "witnessMainPid"):
        if not isinstance(baseline.get(key), str) or not baseline.get(key):
            unknown.append("BASELINE_MISSING:" + key)
    state = _signer_state(units, paths) if units is not None and paths.get("credentials") is not None \
        and paths.get("ownerSocket") is not None else None
    if state is None and units is not None:
        unknown.append("SIGNER_PATHS_UNOBSERVED")

    if halts:
        return _report(min(set(halts), key=HALT_PHASES.index), reasons + unknown, obs, state, invocations)
    if unknown:
        return _report(UNCLASSIFIED, reasons + unknown, obs, state, invocations)

    # ---- STOP classes
    loads = len(invocations)
    if w10.get("phase") != W10_1:                      # W10_1S (witness stopped), W10_0, scratch, later, not exact
        stops.append(W11_WITNESS)
        reasons.append("W10_PHASE:" + str(w10.get("phase")))
    for key in ("witnessInvocationId", "witnessMainPid"):
        if w10.get(key) != baseline.get(key):
            stops.append(W11_WITNESS)
            reasons.append("WITNESS_INCARNATION_CHANGED:" + key)
    service = units[SIGNER_SERVICE]
    if loads > 1 or service.get("NRestarts") not in ("0", ""):
        stops.append(W11_RESTART)
        reasons.append(f"LOADS={loads}:NRESTARTS={service.get('NRestarts')}")
    if state == "RUNNING":
        current = {"InvocationID": service.get("InvocationID"), "MainPID": service.get("MainPID")}
        if not isinstance(capture, Mapping) or capture.get("before") != current or capture.get("after") != current:
            stops.append(W11_RESTART)
            reasons.append("HEALTH_NOT_BOUND_TO_THIS_INCARNATION")
        elif loads == 1 and invocations[0].get("id") != service.get("InvocationID"):
            stops.append(W11_RESTART)
            reasons.append("RUNNING_INVOCATION_NOT_THE_LOADED_ONE")
    if state == "ABNORMAL" or (state == "RUNNING" and loads == 0) \
            or (state == "STOPPED" and loads == 0 and first_load_recorded) \
            or any(i.get("credentials") == UNKNOWN for i in invocations):
        stops.append(W11_START)
        reasons.append("START_NOT_ONE_EXACT_INCARNATION:" + str(state))
    unit_reasons = []
    for name in SIGNER_UNITS:
        facts = units[name]
        if facts.get("UnitFileState") not in ("static", ""):
            unit_reasons.append("ENABLEABLE_OR_ENABLED:" + name)
        if facts.get("LoadState") != "loaded" or facts.get("NeedDaemonReload") != "no":
            unit_reasons.append("NOT_LOADED_CURRENT:" + name)
    if state == "SOCKET_ONLY":
        unit_reasons.append("SOCKET_LISTENING_WITHOUT_SERVICE")      # any root connection would load K-ACT
    unit_reasons += ["RESTART_BOUNDARY_NOT_EFFECTIVE:" + str(r) for r in boundary["reasons"]]
    if state == "RUNNING":
        process = obs.get("process")
        ids = obs.get("signerIds")
        if not isinstance(process, Mapping) or process.get("cwd") != RELEASE_CWD \
                or tuple(process.get("argv") or ()) != EXEC_ARGV \
                or (ids is not None and (process.get("uid"), process.get("gid")) != tuple(ids)):
            unit_reasons.append("PROCESS_NOT_THE_RELEASE_SIGNER")
        credentials = paths["credentials"]
        if credentials.get("kind") != "dir" or credentials.get("names") != [CREDENTIAL_NAME]:
            unit_reasons.append("CREDENTIALS_DIRECTORY_NOT_EXACTLY_ONE_NAME")
        sock = paths["ownerSocket"]
        if (sock.get("kind"), sock.get("uid"), sock.get("gid"), sock.get("mode")) != ("socket", 0, 0, 0o600):
            unit_reasons.append("OWNER_SOCKET_NOT_ROOT_0600")
    if unit_reasons:
        stops.append(W11_UNIT)
        reasons.extend(unit_reasons)
    if state == "RUNNING":
        health_reasons = health_mismatches(health)
        if health_reasons:
            stops.append(W11_HEALTH)
            reasons.extend(health_reasons)
        readiness_reasons = readiness_mismatches(readiness)
        if readiness_reasons:
            stops.append(W11_READINESS)
            reasons.extend(readiness_reasons)
    if set(listing) - {LEDGER_NAME}:
        stops.append(W11_RESIDUE)
        reasons.append("LEDGER_SIDECARS:" + ",".join(sorted(set(listing) - {LEDGER_NAME})))
    if stops:
        return _report(min(set(stops), key=STOP_PHASES.index), reasons, obs, state, invocations)

    # ---- exact
    if state == "RUNNING" and loads == 1:
        return _report(W11_1, reasons, obs, state, invocations)
    if state == "STOPPED" and loads == 1:
        return _report(W11_1S, reasons, obs, state, invocations)
    if state == "STOPPED" and loads == 0 and first_load_recorded is False:
        return _report(W11_0, reasons, obs, state, invocations)
    reasons.append("NO_EXACT_PHASE")
    return _report(UNCLASSIFIED, reasons, obs, state, invocations)


def health_mismatches(health: Any) -> list[str]:
    """H, exactly (the fingerprint and the credential state are judged as HALT facts before this)."""
    if not isinstance(health, Mapping):
        return ["HEALTH_NOT_CAPTURED"]
    out = []
    if set(health) != HEALTH_FIELDS:
        out.append("HEALTH_FIELDS_NOT_EXACT")
    for key, value in HEALTH_EXACT.items():
        if health.get(key) != value:
            out.append("HEALTH_FIELD:" + key)
    if list(health.get("reasons") or []) != list(STRUCTURAL_REASONS) or not isinstance(health.get("reasons"), list):
        out.append("HEALTH_REASONS_NOT_EXACTLY_STRUCTURAL")
    return out


def readiness_mismatches(readiness: Any) -> list[str]:
    """E and F, exactly; G is judged as a HALT fact before this."""
    if not isinstance(readiness, Mapping):
        return ["READINESS_NOT_EVALUATED"]
    out = []
    eligibility, full = readiness.get("eligibility") or {}, readiness.get("full") or {}
    if eligibility.get("status") != "READY" or list(eligibility.get("reasons") or []) != []:
        out.append("E_ELIGIBILITY_NOT_READY")
    if (eligibility.get("loadedKeyBinding") or {}).get("status") != "PASS":
        out.append("E_LOADED_KEY_BINDING_NOT_PASS")
    if full.get("status") != "NOT_READY" or tuple(full.get("reasons") or ()) != EXPECTED_FULL_REASONS:
        out.append("F_FULL_NOT_EXACTLY_THE_HOLD_REASON")
    if full.get("holdDetail") != FULL_HOLD_DETAIL:
        out.append("F_HOLD_DETAIL_NOT_INITIAL_CUSTODY_BOOTSTRAP")
    return out


def _report(phase: str, reasons: list[str], obs: Mapping[str, Any], state: str | None,
            invocations: list | None) -> dict[str, Any]:
    route, note = PHASE_TABLE[phase]
    w10 = obs.get("w10") or {}
    capture = obs.get("health") if isinstance(obs.get("health"), Mapping) else {}
    health = capture.get("health") if isinstance(capture, Mapping) else None
    return {
        "verifierType": VERIFIER_TYPE, "schemaVersion": 1, "environment": ENVIRONMENT, "phase": phase,
        "routing": route, "routeNote": note, "reasons": reasons, "signerState": state,
        "kActLoadCount": None if invocations is None else len(invocations),
        "w10PhaseSignerJudgedSeparately": w10.get("phase"), "w10PhaseDirect": w10.get("direct"),
        "healthPublicKeySha256": health.get("publicKeySha256") if isinstance(health, Mapping) else None,
        "healthIsSignerClaim": True, "expectedB3": B3_PUBLIC_KEY_SHA256, "expectedB2": B2_CURRENT_BLOB_SHA256,
        "signerAvailableIsAuthority": False, "readinessIsAuthority": False, "issuanceAuthority": "NONE",
        "registryEffective": False, "authorityActive": False, "authorityGranted": False,
    }


# ---------------------------------------------------------------- evaluate ---

def evaluate(evidence: Mapping[str, Any], *, root: Path | str = Path("/"), owner_uid: int = 0, owner_gid: int = 0,
             units: Callable[[Sequence[str]], dict] | None = None, journal: Callable[[str | None], dict] | None = None,
             process: Callable[[Path, str], dict | None] | None = None, w10: Callable[..., dict] | None = None,
             readiness: Callable[..., dict] | None = None,
             restart_boundary: Callable[[Path, Callable], dict] | None = None, **w10_seams: Any) -> dict[str, Any]:
    """One read-only observation and judgement. `evidence` holds the owner-side inputs: the expected ledger head,
    candidate digest and updatedAt (as for W10), the baseline (pre-start DB SHA-256, witness incarnation, journal
    cursor), `firstLoadRecorded`, the captured HEALTH (or null), the signer ids and the verifier owner inputs. The
    remaining arguments are TEST seams."""
    root = Path(root)
    baseline = dict(evidence.get("baseline") or {})
    masked = w10_signer_masked(evidence["expectedHead"], evidence["candidateDigest"], evidence["updatedAt"],
                               root=root, units=units, w10=w10, owner_uid=owner_uid, owner_gid=owner_gid,
                               **w10_seams)
    signer = observe_signer(root, units=units, process=process)
    capture = evidence.get("healthCapture")
    health = capture.get("health") if isinstance(capture, Mapping) else None
    pair = None
    if evidence.get("ownerInputs") is not None and signer["units"] is not None:
        try:
            pair = (readiness or readiness_pair)(evidence["ownerInputs"], health, root=root, owner_uid=owner_uid,
                                                 owner_gid=owner_gid)
        except Exception as exc:  # noqa: BLE001 - an evaluation that cannot run is UNKNOWN, never success
            pair = {"error": type(exc).__name__}
    try:
        boundary = (restart_boundary or _restart_boundary)(root, units)
    except Exception as exc:  # noqa: BLE001 - an unreadable boundary is UNKNOWN, never success
        boundary = {"error": type(exc).__name__}
    observation = {
        "w10": masked, "units": signer["units"], "paths": signer["paths"], "process": signer["process"],
        "restartBoundary": boundary,
        "journal": (journal or journal_invocations)(baseline.get("journalCursor")), "health": capture,
        "readiness": pair if isinstance(pair, Mapping) and "error" not in pair else None,
        "ledger": observe_ledger_bytes(root), "baseline": baseline,
        "firstLoadRecorded": evidence.get("firstLoadRecorded"), "signerIds": evidence.get("signerIds"),
    }
    report = classify(observation)
    report["observation"] = observation
    return report


def _restart_boundary(root: Path, units: Callable[[Sequence[str]], dict] | None) -> dict[str, Any]:
    """The effective restart boundary, read-only (fragments, overlay bytes and metadata, unit properties)."""
    import mb11_restart_boundary_install as RBI

    observed = RBI.observe(root, units=units, activation=None)
    return {"reasons": RBI.boundary_reasons(observed), "shadows": observed["shadows"]}


# ------------------------------------------------------------------ entry ---

def main(argv: list[str]) -> int:
    try:
        if len(argv) == 2 and argv[0] == "classify":
            report = classify(json.loads(Path(argv[1]).read_text(encoding="utf-8")))
        elif len(argv) == 2 and argv[0] == "observe":
            import mb6_ledger_verifier as V6

            V6.require_dev_root()
            if V6.RELEASE_TREE not in sys.path:
                sys.path.insert(0, V6.RELEASE_TREE)
            report = evaluate(json.loads(Path(argv[1]).read_text(encoding="utf-8")))
        else:
            raise Refused("USAGE")
    except (Refused, ValueError, OSError) as exc:
        print(f"mb11_signer_verifier: REFUSED {getattr(exc, 'reason', type(exc).__name__)}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
