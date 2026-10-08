#!/usr/bin/env python3
"""15B2b-B1b-3e Package B (M-B9a / M-B9b): READ-ONLY witness verifier and W9 crash-window classifier (DEV).

Record: docs/architecture/slice-15b2b-b1b3e-mb9-witness-genesis-package.md §6 – §8.

M-B9a (`START_WITNESS`) is two ordered mutations: the installer stage `witness-state <RELEASE_SHA>` (P1B-9a:
`/var/lib/lilith-recovery-witness`, `lilith-recovery-witness:lilith-authority-dev 2750`), then the start of the
two witness sockets and the witness service (never enabled, never `daemon-reload`). M-B9b
(`COMMIT_WITNESS_GENESIS`) is one owner `BOOTSTRAP` of the exact pinned candidate; its commit point is the fsync of
`chain/` after `chain/1.json` was created `O_EXCL` and fsynced (`writer.py` `_commit`). This tool judges the host
before, between and after those mutations and classifies it into exactly one W9 host phase.

Every judgment is against OWNER-computed values passed as arguments (the expected ledger head, the candidate
digest, the owner-chosen `updatedAt`) and the accepted pins. The trust anchors and Registry V1 are judged by the
accepted W5 verifier, the ledger by the accepted M-B6 byte reader, the owner-input copies by the accepted W8
file classifier (all imported unchanged); the witness store by the release recovery classifier
(`witness_readiness.classify_witness_store`) over a read-only observation (`store_observer`).

It runs on DEV as root with the installed release interpreter, streamed by the Package B operator as one
hash-gated bundle with the W5, M-B6 and W8 verifiers:

    ... observe <ledger-head> <candidate-digest> <updatedAt>
    ... expect <PHASE> <ledger-head> <candidate-digest> <updatedAt>

It takes no path argument. It NEVER opens or connects to a witness or signer socket (socket activation would
start the service), never opens a credential, the credstore, the host credential key or the K-WIT blob, never
decrypts, signs, starts, stops, reloads or enables anything, and writes nothing. Unit state comes from
`systemctl show` only.

    candidate != pin != committed genesis;  W9 phase != owner acceptance;  WITNESS_STARTED != M-B9b authorization
    commit point = chain/ fsync;  after it the lineage is forward only;  committed != pin -> REBOOTSTRAP_FORBIDDEN
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import mb6_ledger_verifier as V6
import mb8_owner_input_verifier as V8

VERIFIER_TYPE = "LILITH_MB9_WITNESS_VERIFICATION"
ENVIRONMENT = "dev"
RELEASE_TREE = V6.RELEASE_TREE
WITNESS_USER = "lilith-recovery-witness"
SIGNER_GROUP = "lilith-authority-dev"
WITNESS_STATE = "/var/lib/lilith-recovery-witness"
WITNESS_RUNTIME = "/run/lilith-recovery-witness"
WITNESS_OWNER_SOCKET = WITNESS_RUNTIME + "/owner.sock"
WITNESS_SIGNER_SOCKET = WITNESS_RUNTIME + "/signer.sock"
WITNESS_CREDENTIALS = "/run/credentials/lilith-recovery-witness.service"
SIGNER_CREDENTIALS = "/run/credentials/lilith-authority-dev.service"
SIGNER_OWNER_SOCKET = "/run/lilith-authority-dev/owner.sock"
HOLD_STORE = V6.HOLD_STORE
WITNESS_SERVICE = "lilith-recovery-witness.service"
WITNESS_OWNER_UNIT = "lilith-recovery-witness-owner.socket"
WITNESS_SIGNER_UNIT = "lilith-recovery-witness-signer.socket"
WITNESS_UNITS = (WITNESS_SERVICE, WITNESS_OWNER_UNIT, WITNESS_SIGNER_UNIT)
SIGNER_UNITS = ("lilith-authority-dev.service", "lilith-authority-dev.socket")
UNIT_PROPERTIES = ("Id", "LoadState", "ActiveState", "SubState", "UnitFileState", "NeedDaemonReload", "MainPID",
                   "NRestarts", "InvocationID", "Result")
SYSTEMCTL = "/usr/bin/systemctl"
FIXED_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "HOME": "/nonexistent"}
LOCK_NAME = "witness.lock"
POINTER_NAME = "witness.json"
SCRATCH_NAME = ".witness.json.tmp"
CHAIN_DIRECTORY = "chain"
AUTHORIZATION_DIRECTORY = "authorizations"
GENESIS_ENTRY = "1.json"
STATE_KINDS = {LOCK_NAME: "file", POINTER_NAME: "file", SCRATCH_NAME: "file", CHAIN_DIRECTORY: "dir",
               AUTHORIZATION_DIRECTORY: "dir"}
STATE_DIRECTORY_MODE = 0o2750                     # the installer `witness-state` chmod (setgid: group = signer)
# A directory the witness creates (`storage.make_directory`, 0750 under UMask=0027) inside the setgid state
# directory: 2750 where the filesystem propagates setgid (Linux default), 0750 otherwise. Both are producible
# by the witness alone; anything else is foreign.
SUBDIRECTORY_MODES = (0o2750, 0o750)
FILE_MODE = 0o640                                 # `storage.FILE_MODE` under UMask=0027
MAX_FILE = 256 * 1024
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_CHAIN_NAME = re.compile(r"[1-9][0-9]{0,15}\.json\Z")

EVIDENCE_9A = ("stateDirectoryExact", "witnessRunning", "storeUninitialized", "noLineageEntry")
EVIDENCE_9B = ("genesisCommitted", "committedDigestEqualsPin", "committedEqualsCandidate", "chainIsGenesisOnly",
               "pointerEqualsGenesis", "retainedAuthorizationsEmpty")
BASE_CHECKS = ("trustRegistryExact", "ledgerExact", "ownerInputsExact", "hostInputReasonsEmpty",
               "hostCandidateEqualsOwner", "pinEqualsCandidate", "registerExact")

# ------------------------------------------------------------------ phases ---
# Host phases (what the host alone shows).
W9_0 = "W9_0_PRE_WITNESS"                           # = W8 OWNER_INPUTS_INSTALLED_EXACT; no witness state; units inactive
W9_1P = "W9_1P_STATE_DIR_PARTIAL"                   # witness-state interrupted: mkdir done, chown/chmod not
W9_1 = "W9_1_STATE_DIR_ONLY"                        # 9A-1 exact: the empty 2750 directory; units inactive
W9_2 = "W9_2_STARTED_UNINITIALIZED"                 # 9A-2 exact: sockets + service running; store UNINITIALIZED
W9_2S = "W9_2S_STOPPED_UNINITIALIZED"               # the witness ran (lock present) and is stopped; UNINITIALIZED
W9_FAILED = "W9_FAILED_START"                       # pre-lineage: a failed, partial or transitional runtime
W9_3 = "W9_3_PRECOMMIT_DIRS"                        # BOOTSTRAP created chain/ + authorizations/ (empty): UNINITIALIZED
W9_4 = "W9_4_COMMITTED_POINTER_PENDING"             # chain/1.json committed = pin; pointer missing/corrupt/scratch
W9_5 = "W9_5_GENESIS_COMMITTED_EXACT"               # M-B9b exact; witness running
W9_5S = "W9_5S_GENESIS_COMMITTED_STOPPED"           # M-B9b exact; witness stopped (e.g. after a reboot)
W9_ABNORMAL = "W9_RUNTIME_ABNORMAL_AFTER_COMMIT"    # lineage committed; failed, partial or transitional runtime
W9_TORN = "W9_TORN_GENESIS"                         # chain/1.json present but not a valid witness document
W9_MISMATCH = "W9_GENESIS_MISMATCH"                 # committed genesis != owner pin / candidate: C-12
LATER_STATE = "W9_LATER_STATE"                      # chain > genesis, retained authorization, HELD, signer
FOREIGN = "W9_FOREIGN_OR_UNSAFE"                    # content / metadata the installer and witness cannot produce
UNCLASSIFIED = "UNCLASSIFIED_STOP"
HOST_PHASES = (W9_0, W9_1P, W9_1, W9_2, W9_2S, W9_FAILED, W9_3, W9_4, W9_5, W9_5S, W9_ABNORMAL, W9_TORN,
               W9_MISMATCH, LATER_STATE, FOREIGN, UNCLASSIFIED)
LINEAGE_COMMITTED_PHASES = (W9_4, W9_5, W9_5S, W9_ABNORMAL, W9_MISMATCH)
REMOVABLE_PHASES = (W9_1P, W9_1, W9_2S, W9_3)       # the removal tool re-checks every condition itself
RESTARTABLE_PHASES = (W9_1, W9_2S, W9_3, W9_4, W9_5S)  # units inactive; never a stop of a running witness

# Routes. No route is automatic; each needs its own owner act.
SAFE_RETRY = "SAFE_RETRY"
SAFE_CONTINUE_OR_REMOVE = "SAFE_CONTINUE_OR_REMOVE"
SAFE_REMOVE_AND_RETRY = "SAFE_REMOVE_AND_RETRY"
SAFE_RESTART_OR_REMOVE = "SAFE_RESTART_OR_REMOVE"
SAFE_RESTART = "SAFE_RESTART"
SAFE_ADOPT = "SAFE_ADOPT"
STOP_OWNER_ADJUDICATION = "STOP_OWNER_ADJUDICATION"
HALT = "HALT_REBOOTSTRAP_FORBIDDEN"
ROUTES = (SAFE_RETRY, SAFE_CONTINUE_OR_REMOVE, SAFE_REMOVE_AND_RETRY, SAFE_RESTART_OR_REMOVE, SAFE_RESTART,
          SAFE_ADOPT, STOP_OWNER_ADJUDICATION, HALT)
YES, NO, UNDETERMINED = "YES", "NO", "UNDETERMINED"

# Host-phase table (record §6.1): route, reversible (lineage), owner act needed, retry / adoption / removal.
PHASE_TABLE = {
    W9_0: (SAFE_RETRY, YES, "B2 (M-B9a go)",
           "nothing of M-B9a exists; a stage consumed without mutation needs a new B2 and a fresh re-proof"),
    W9_1P: (SAFE_REMOVE_AND_RETRY, YES, "bounded removal authorization, then a new B2",
            "interrupted `witness-state`; only the plan-digest-bound removal; never a re-run over it"),
    W9_1: (SAFE_CONTINUE_OR_REMOVE, YES, "none within the same B2 after an exact 9A-1; otherwise restart or removal",
           "stage 9A-2 runs only under the same B2 after an exact 9A-1; after a consumed 9A-2: separately "
           "authorized restart, or bounded removal"),
    W9_2: (SAFE_ADOPT, YES, "B3 (WITNESS_STARTED acceptance) after POST9A",
           "read-only POST9A; reversal would need a separately reviewed stop (not implemented) and the removal"),
    W9_2S: (SAFE_RESTART_OR_REMOVE, YES, "restart or removal authorization",
            "any earlier M-B9a acceptance is stale: a separately authorized restart, then a fresh POST9A and B3"),
    W9_FAILED: (STOP_OWNER_ADJUDICATION, YES, "owner adjudication",
                "no automatic restart; diagnose first; no lineage exists"),
    W9_3: (STOP_OWNER_ADJUDICATION, YES, "owner adjudication; a new B4 and a fresh re-proof, or restart / removal",
           "BOOTSTRAP stopped before the commit point (C-11): UNINITIALIZED, no lineage; the consumed go is not "
           "retried"),
    W9_4: (STOP_OWNER_ADJUDICATION, NO, "owner adjudication; a separately authorized restart if stopped",
           "the lineage is committed; the pointer is rolled forward only by the witness's own recovery at start; "
           "never removed, recreated or retried"),
    W9_5: (SAFE_ADOPT, NO, "B5 (Package B acceptance) after POST9B and owner offline verification",
           "read-only POST9B; forward only"),
    W9_5S: (SAFE_RESTART, NO, "restart authorization, then a fresh POST9B",
            "the lineage is committed; restart only; forward only"),
    W9_ABNORMAL: (STOP_OWNER_ADJUDICATION, NO, "owner adjudication", "the lineage is committed; no automatic action"),
    W9_TORN: (STOP_OWNER_ADJUDICATION, UNDETERMINED, "owner adjudication",
              "OD-B6: no automated deletion, repair or re-bootstrap"),
    W9_MISMATCH: (HALT, NO, "a separately reviewed owner recovery / successor design",
                  "C-12 REBOOTSTRAP_FORBIDDEN: no second witness genesis, ever"),
    LATER_STATE: (STOP_OWNER_ADJUDICATION, NO, "owner adjudication", "record 1 / HELD / signer or later: outside Package B"),
    FOREIGN: (STOP_OWNER_ADJUDICATION, UNDETERMINED, "owner adjudication", "no tool acts on it"),
    UNCLASSIFIED: (STOP_OWNER_ADJUDICATION, UNDETERMINED, "owner adjudication",
                   "an inconsistent, unreadable or unreachable combination; UNKNOWN is never absence or success"),
}

# Sequence phases (host phase + the operator's markers, transcripts, POST and acceptance records).
S9_0 = "S9_0_NOT_STARTED"
S9A1_R = "S9A1_R_CONSUMED_NO_MUTATION"
S9A1_PARTIAL = "S9A1_PARTIAL"
S9A1_INCOMPLETE = "S9A1_TRANSCRIPT_INCOMPLETE"
S9A1_EXACT = "S9A1_EXACT_STAGE2_PENDING"
S9A2_R = "S9A2_R_CONSUMED_NOT_STARTED"
S9A2_PARTIAL = "S9A2_PARTIAL"
S9A2_INCOMPLETE = "S9A2_TRANSCRIPT_INCOMPLETE"
S9A_POST_PENDING = "S9A_POST_PENDING"
S9A_POST_VERIFIED = "S9A_POST_VERIFIED_ACCEPTANCE_PENDING"
S9A_ACCEPTED = "S9A_ACCEPTED"
S9A_STALE = "S9A_ACCEPTANCE_STALE_REVALIDATE"
S9A_STOPPED = "S9A_STOPPED_REVALIDATE"
S9B_R = "S9B_R_CONSUMED_NO_LINEAGE"
S9B_POINTER = "S9B_COMMITTED_POINTER_PENDING"
S9B_UNACKNOWLEDGED = "S9B_COMMITTED_UNACKNOWLEDGED"
S9B_STOPPED = "S9B_COMMITTED_STOPPED_REVALIDATE"
S9B_POST_PENDING = "S9B_POST_PENDING"
S9B_POST_VERIFIED = "S9B_POST_VERIFIED_ACCEPTANCE_PENDING"
S9B_ADOPTION_PENDING = "S9B_POST_VERIFIED_ADOPTION_PENDING"
S9_HALT = "S9_HALT_REBOOTSTRAP_FORBIDDEN"
SEQUENCE_PHASES = (S9_0, S9A1_R, S9A1_PARTIAL, S9A1_INCOMPLETE, S9A1_EXACT, S9A2_R, S9A2_PARTIAL, S9A2_INCOMPLETE,
                   S9A_POST_PENDING, S9A_POST_VERIFIED, S9A_ACCEPTED, S9A_STALE, S9A_STOPPED, S9B_R, S9B_POINTER,
                   S9B_UNACKNOWLEDGED, S9B_STOPPED, S9B_POST_PENDING, S9B_POST_VERIFIED, S9B_ADOPTION_PENDING,
                   S9_HALT, W9_TORN, LATER_STATE, FOREIGN, UNCLASSIFIED)
SEQUENCE_ROUTING = {
    S9_0: (SAFE_RETRY, "nothing consumed; B2 may be issued after the closing gate"),
    S9A1_R: (SAFE_RETRY, "stage 9A-1 consumed, nothing created: a new B2 and a fresh re-proof"),
    S9A1_PARTIAL: (SAFE_REMOVE_AND_RETRY, "bounded removal (plan digest, separate authorization), then a new B2"),
    S9A1_INCOMPLETE: (STOP_OWNER_ADJUDICATION, "the directory is exact but the transcript is not: stage 9A-2 never "
                                               "runs; owner adjudication (restart or removal)"),
    S9A1_EXACT: (SAFE_RETRY, "stage 9A-2 under the same B2 (the operator runs it in the same invocation only)"),
    S9A2_R: (SAFE_RESTART_OR_REMOVE, "stage 9A-2 consumed, nothing started: separately authorized restart or removal"),
    S9A2_PARTIAL: (STOP_OWNER_ADJUDICATION, "failed or partial start: diagnose; no automatic restart"),
    S9A2_INCOMPLETE: (SAFE_ADOPT, "running and UNINITIALIZED but the transcript is incomplete: read-only POST9A, "
                                  "then an explicit owner adoption in B3"),
    S9A_POST_PENDING: (SAFE_ADOPT, "run the read-only POST9A"),
    S9A_POST_VERIFIED: (SAFE_ADOPT, "owner acceptance B3 (WITNESS_STARTED) for this InvocationID / MainPID"),
    S9A_ACCEPTED: (SAFE_ADOPT, "closing gate, then the separate B4 lineage go; B3 is not M-B9b authorization"),
    S9A_STALE: (SAFE_ADOPT, "the running witness is not the accepted incarnation: a fresh POST9A and a new B3"),
    S9A_STOPPED: (SAFE_RESTART_OR_REMOVE, "the witness stopped: separately authorized restart, fresh POST9A, new B3"),
    S9B_R: (STOP_OWNER_ADJUDICATION, "B4 consumed; the host proves no lineage (UNINITIALIZED): a new B4 needs a "
                                     "fresh closing gate; never an automatic retry"),
    S9B_POINTER: (STOP_OWNER_ADJUDICATION, "lineage committed, pointer pending: owner adjudication; roll-forward "
                                           "only by the witness's recovery at an authorized start"),
    S9B_UNACKNOWLEDGED: (SAFE_ADOPT, "lineage committed, acknowledgement lost: read-only POST9B, then an explicit "
                                     "owner adoption decision in B5"),
    S9B_STOPPED: (SAFE_RESTART, "lineage committed, witness stopped: separately authorized restart, fresh POST9B"),
    S9B_POST_PENDING: (SAFE_ADOPT, "run the read-only POST9B and the owner offline verification"),
    S9B_POST_VERIFIED: (SAFE_ADOPT, "owner offline verification, then Package B acceptance B5"),
    S9B_ADOPTION_PENDING: (SAFE_ADOPT, "owner offline verification, then B5 with the explicit adoption sentence"),
    S9_HALT: (HALT, "C-12: STOP; no second genesis; separately reviewed owner recovery / successor design"),
    W9_TORN: (STOP_OWNER_ADJUDICATION, "torn genesis: no automated deletion, repair or re-bootstrap"),
    LATER_STATE: (STOP_OWNER_ADJUDICATION, "later state: outside Package B"),
    FOREIGN: (STOP_OWNER_ADJUDICATION, "foreign or unsafe content: no tool acts on it"),
    UNCLASSIFIED: (STOP_OWNER_ADJUDICATION, "an inconsistent or unreachable combination"),
}

# Transcript classes.
NOT_INVOKED = "NOT_INVOKED"
GUARD_STOPPED = "GUARD_STOPPED"
TRANSPORT_FAILED = "TRANSPORT_FAILED"
FAILED_UNCLASSIFIED = "FAILED_UNCLASSIFIED"
STAGE_PASS = "STAGE_PASS"
STAGE_STATUS_FAIL = "STAGE_STATUS_FAIL"
STAGE_REFUSED = "STAGE_REFUSED"
STAGE_CLASSES = (NOT_INVOKED, STAGE_PASS, STAGE_STATUS_FAIL, STAGE_REFUSED, GUARD_STOPPED, TRANSPORT_FAILED,
                 FAILED_UNCLASSIFIED)
START_OK = "START_RETURNED_OK"
START_FAILED = "START_FAILED"
START_CLASSES = (NOT_INVOKED, START_OK, START_FAILED, GUARD_STOPPED, TRANSPORT_FAILED)
BOOTSTRAP_PASS = "BOOTSTRAP_PASS"
BOOTSTRAP_REFUSED_BEFORE_WITNESS = "BOOTSTRAP_REFUSED_BEFORE_WITNESS"
BOOTSTRAP_WITNESS_REFUSED = "BOOTSTRAP_WITNESS_REFUSED"          # pre-sign refusal OR post-commit STOP: host decides
BOOTSTRAP_COMMITTED_NOT_PINNED = "BOOTSTRAP_COMMITTED_NOT_PINNED"
BOOTSTRAP_REFUSED_OTHER = "BOOTSTRAP_REFUSED_OTHER"
BOOTSTRAP_CLASSES = (NOT_INVOKED, BOOTSTRAP_PASS, BOOTSTRAP_REFUSED_BEFORE_WITNESS, BOOTSTRAP_WITNESS_REFUSED,
                     BOOTSTRAP_COMMITTED_NOT_PINNED, BOOTSTRAP_REFUSED_OTHER, GUARD_STOPPED, TRANSPORT_FAILED,
                     FAILED_UNCLASSIFIED)
# `genesis.bootstrap` refusals raised before the witness is contacted (lilith_authority_root.genesis / cli).
BEFORE_WITNESS_REASONS = frozenset({"GENESIS_INPUTS_INCOMPLETE", "GENESIS_REGISTRY_NOT_INSTALLED",
                                    "GENESIS_LEDGER_ABSENT", "GENESIS_LEDGER_INVALID", "GENESIS_CANDIDATE_REFUSED",
                                    "GENESIS_PIN_NOT_CANDIDATE", "USAGE", "VERSION_INVALID", "UPDATED_AT_INVALID",
                                    "NOT_ROOT"})


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _host(root: Path, absolute: str) -> Path:
    return root / absolute.lstrip("/")


# ------------------------------------------------------------------- units ---

def parse_units(text: str) -> dict[str, dict[str, str]]:
    """`systemctl show -p <UNIT_PROPERTIES> <units>`: blank-line separated blocks, keyed by `Id`."""
    units: dict[str, dict[str, str]] = {}
    for block in text.strip("\n").split("\n\n"):
        values = dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
        if values.get("Id"):
            units[values["Id"]] = values
    return units


def _units(names: Sequence[str]) -> dict[str, dict[str, str]]:
    result = subprocess.run([SYSTEMCTL, "show", "-p", ",".join(UNIT_PROPERTIES), "--no-pager", "--", *names],
                            env=FIXED_ENV, capture_output=True, text=True, timeout=30, check=False)
    if result.returncode != 0:
        raise Refused("UNITS_UNREADABLE")
    return parse_units(result.stdout)


def runtime_class(units: Mapping[str, Mapping[str, str]], *, credentials: bool, sockets: tuple[bool, bool]) -> str:
    """RUNNING | STOPPED | ABNORMAL from `systemctl show` and the runtime paths (never a socket connection)."""
    states = [units[name].get("ActiveState") for name in WITNESS_UNITS]
    service = units[WITNESS_SERVICE]
    if states == ["active", "active", "active"] and service.get("SubState") == "running" \
            and service.get("MainPID", "0") not in ("", "0") and credentials and sockets == (True, True):
        return "RUNNING"
    if states == ["inactive", "inactive", "inactive"] and not credentials and sockets == (False, False):
        return "STOPPED"
    return "ABNORMAL"


# ------------------------------------------------------------------- store ---

def _meta(path: Path) -> os.stat_result | None:
    try:
        return os.lstat(path)
    except FileNotFoundError:
        return None


def _entry_facts(meta: os.stat_result) -> dict[str, Any]:
    kind = ("symlink" if stat.S_ISLNK(meta.st_mode) else "dir" if stat.S_ISDIR(meta.st_mode)
            else "file" if stat.S_ISREG(meta.st_mode) else "other")
    return {"kind": kind, "uid": meta.st_uid, "gid": meta.st_gid, "mode": format(stat.S_IMODE(meta.st_mode), "04o"),
            "size": meta.st_size, "links": meta.st_nlink}


def store_metadata(root: Path, witness_ids: tuple[int, int], signer_gid: int) -> dict[str, Any]:
    """Every entry of the witness state directory (and its two subdirectories), `lstat` only, judged against
    what the installer and the witness alone can produce. Contents are judged by the release classifier."""
    state = _host(root, WITNESS_STATE)
    meta = _meta(state)
    if meta is None:
        return {"present": False}
    facts: dict[str, Any] = {"present": True, "directory": _entry_facts(meta), "entries": {}, "chain": {},
                             "authorizations": {}, "failures": []}
    failures = facts["failures"]
    if not stat.S_ISDIR(meta.st_mode):
        failures.append("STATE_NOT_A_REAL_DIRECTORY")
        return facts
    wit_uid = witness_ids[0]
    owner = (meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode))
    facts["directoryExact"] = owner == (wit_uid, signer_gid, STATE_DIRECTORY_MODE)
    # Reachable only by an interrupted `witness-state` (mkdir 0750 by root, then chown, then chmod 2750).
    facts["directoryPartialReachable"] = (not facts["directoryExact"]
                                          and (meta.st_uid, meta.st_gid) in ((0, 0), (wit_uid, signer_gid))
                                          and stat.S_IMODE(meta.st_mode) & ~0o750 == 0)
    names = sorted(os.listdir(state))
    facts["listing"] = names

    def regular(path: Path, label: str) -> None:
        item = _meta(path)
        info = _entry_facts(item)
        if info["kind"] != "file" or (item.st_uid, item.st_gid, stat.S_IMODE(item.st_mode)) \
                != (wit_uid, signer_gid, FILE_MODE) or item.st_nlink != 1 or item.st_size > MAX_FILE:
            failures.append("ENTRY_UNSAFE:" + label)
        return info

    def directory(path: Path, label: str) -> list[str]:
        item = _meta(path)
        info = _entry_facts(item)
        if info["kind"] != "dir" or (item.st_uid, item.st_gid) != (wit_uid, signer_gid) \
                or stat.S_IMODE(item.st_mode) not in SUBDIRECTORY_MODES:
            failures.append("ENTRY_UNSAFE:" + label)
            return []
        return sorted(os.listdir(path))

    for name in names:
        if name not in STATE_KINDS:
            failures.append("ENTRY_UNEXPECTED:" + name)
            continue
        path = state / name
        if STATE_KINDS[name] == "file":
            facts["entries"][name] = regular(path, name)
        else:
            facts["entries"][name] = _entry_facts(_meta(path))
            for child in directory(path, name):
                target = facts["chain" if name == CHAIN_DIRECTORY else "authorizations"]
                pattern = _CHAIN_NAME if name == CHAIN_DIRECTORY else re.compile(r"[0-9a-f]{64}\.json\Z")
                if pattern.fullmatch(child) is None:
                    failures.append(f"ENTRY_UNEXPECTED:{name}/{child}")
                    continue
                target[child] = regular(path / child, f"{name}/{child}")
    return facts


def _read_bytes(path: Path) -> bytes | None:
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    except FileNotFoundError:
        return None
    try:
        data = os.read(fd, MAX_FILE + 1)
    finally:
        os.close(fd)
    return data if len(data) <= MAX_FILE else None


# ---------------------------------------------------------------- evaluate ---

def _ids() -> tuple[tuple[int, int], int]:
    import grp
    import pwd

    entry = pwd.getpwnam(WITNESS_USER)
    return (entry.pw_uid, entry.pw_gid), grp.getgrnam(SIGNER_GROUP).gr_gid


def evaluate(expected_head: str, candidate_digest: str, updated_at: str, *, root: Path | str = Path("/"),
             owner_uid: int = 0, owner_gid: int = 0, signer: tuple[int, int] | None = None,
             witness: tuple[tuple[int, int], int] | None = None, units: Callable[[Sequence[str]], dict] | None = None,
             pins: V6.LedgerPinsV1 = V6.ACCEPTED_PINS, trust_pins: Any = None) -> dict[str, Any]:
    """One read-only observation and judgment. `root`, `owner_*`, `signer`, `witness`, `units`, `pins`,
    `trust_pins` are TEST seams."""
    for value, reason in ((expected_head, "EXPECTED_HEAD_INVALID"), (candidate_digest, "CANDIDATE_DIGEST_INVALID")):
        if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
            raise Refused(reason)
    if not isinstance(updated_at, str) or _INSTANT.fullmatch(updated_at) is None:
        raise Refused("UPDATED_AT_INVALID")
    V5, L, HI, A, J, B, R, RC, WR, canonical = V8._release_modules()
    from lilith_authority_host import store_observer as SO

    root = Path(root)
    signer = signer if signer is not None else V8._signer_ids()
    (witness_ids, signer_gid) = witness if witness is not None else _ids()
    trust_pins = trust_pins if trust_pins is not None else V5.ACCEPTED_PINS
    failures: list[str] = []

    # ---- the accepted Package A end state, re-proven (W5 + M-B6 ledger + W8 copies + in-memory candidate)
    host = HI.read_host_inputs(environment=ENVIRONMENT, root=root, owner_uid=owner_uid)
    reasons = sorted(host.reasons)
    trust = V5.evaluate(root=root, owner_uid=owner_uid, owner_gid=owner_gid, pins=trust_pins)
    trust_exact = all(trust["evidence"].get(name) is True for name in
                      ("anchorsEqualOwnerCopies", "witnessAnchorNamesKWit", "registryVerifiesOnHost"))
    ledger_exact, ledger, ledger_failures = V8._ledger(root, expected_head, pins, signer, L, J, R, A, canonical)
    failures.extend(ledger_failures)
    owner_dir = V6._facts(V6._lstat(_host(root, V8.OWNER_INPUT_DIR)))
    listing = V6._listing(root, V8.OWNER_INPUT_DIR)
    files = {V8.PIN_COPY: V8.classify_file(root, V8.PIN_COPY, V8.expected_pin_bytes(candidate_digest),
                                           owner_uid=owner_uid, owner_gid=owner_gid),
             V8.REGISTER_COPY: V8.classify_file(root, V8.REGISTER_COPY,
                                                V8.expected_register_bytes(trust_pins.registry_digest),
                                                owner_uid=owner_uid, owner_gid=owner_gid)}
    owner_inputs_exact = (owner_dir.get("kind") == "dir"
                          and (owner_dir["uid"], owner_dir["gid"], owner_dir["mode"]) == (owner_uid, owner_gid, "0755")
                          and listing == sorted(V8.OWNER_NAMES)
                          and all(info["state"] == "EXACT" for info in files.values()))
    built = None
    if trust_exact and ledger_exact:
        registry = next((r for r in host.registries if r.get("registryVersion") == 1), None)
        try:
            op = ledger["op"]
            observation = RC.AuthorityLedgerObservationV1(
                environment=ENVIRONMENT, recovery_epoch=A.RecoveryEpochV1.from_dict(op["recoveryEpoch"]),
                sequence=ledger["sequence"], head=ledger["head"], registry_view=op["registryVersion"],
                signing_key_ids=tuple(op["signingKeyIds"]))
            built = B.build_genesis_candidate(registry=registry, registry_root=host.registry_root,
                                              ledger_observation=observation, updated_at=updated_at,
                                              profile=B.witness_profile(ENVIRONMENT))
        except Exception:  # noqa: BLE001 - any refusal fails closed
            built = None
    candidate_equal = built is not None and built.built and built.digest == candidate_digest
    pin_reason = B.candidate_pin_reason(host.genesis_pin, built, environment=ENVIRONMENT) if candidate_equal \
        else "NO_CANDIDATE"
    try:
        register = WR.OwnerAuthorizationRegisterV1.from_dict(host.owner_register) if host.owner_register else None
    except Exception:  # noqa: BLE001
        register = None
    register_exact = (register is not None and not register.authorizations
                      and register.head_registries == frozenset({RC.RegistryHeadV1(1, trust_pins.registry_digest)}))
    base = {"trustRegistryExact": trust_exact, "ledgerExact": ledger_exact, "ownerInputsExact": owner_inputs_exact,
            "hostInputReasonsEmpty": reasons == [], "hostCandidateEqualsOwner": candidate_equal,
            "pinEqualsCandidate": pin_reason is None, "registerExact": register_exact}
    failures.extend("BASE_NOT_EXACT:" + name for name, ok in base.items() if not ok)

    # ---- later state outside Package B: the signer, HELD
    signer_paths = {path: V6._lstat(_host(root, path)) is not None for path in (SIGNER_CREDENTIALS, SIGNER_OWNER_SOCKET)}
    holds = V6._listing(root, HOLD_STORE)
    runtime_paths = {path: V6._lstat(_host(root, path)) is not None
                     for path in (WITNESS_CREDENTIALS, WITNESS_OWNER_SOCKET, WITNESS_SIGNER_SOCKET)}

    # ---- units (systemctl show only)
    try:
        unit_facts = (units or _units)(WITNESS_UNITS + SIGNER_UNITS)
        unit_facts = {name: {key: unit_facts[name].get(key, "") for key in UNIT_PROPERTIES} for name in
                      WITNESS_UNITS + SIGNER_UNITS}
        units_readable = True
    except (Refused, KeyError, OSError, subprocess.SubprocessError):
        unit_facts, units_readable = {}, False
        failures.append("UNITS_UNREADABLE")
    runtime = None
    if units_readable:
        runtime = runtime_class(unit_facts, credentials=runtime_paths[WITNESS_CREDENTIALS],
                                sockets=(runtime_paths[WITNESS_OWNER_SOCKET], runtime_paths[WITNESS_SIGNER_SOCKET]))
    signer_active = (not units_readable or any(unit_facts[name]["ActiveState"] != "inactive" for name in SIGNER_UNITS)
                     or any(signer_paths.values()))
    units_foreign = units_readable and any(unit_facts[name]["UnitFileState"] not in ("static", "")
                                           for name in WITNESS_UNITS + SIGNER_UNITS)
    units_unloaded = units_readable and any((unit_facts[name]["LoadState"], unit_facts[name]["NeedDaemonReload"])
                                            != ("loaded", "no") for name in WITNESS_UNITS + SIGNER_UNITS)

    # ---- the witness store: metadata (lstat), then content (the release recovery classifier)
    store = store_metadata(root, witness_ids, signer_gid)
    scan = None
    genesis_bytes = pointer_bytes = None
    if store.get("present") and not store["failures"] and base["trustRegistryExact"]:
        try:
            observation = SO.observe_witness_state(_host(root, WITNESS_STATE))
            scan = WR.classify_witness_store(observation=observation, context=host.store_context(
                authority_public_keys=HI.authority_public_keys(host)))
        except (OSError, ValueError):
            scan = None
            failures.append("STORE_UNREADABLE")
        genesis_bytes = _read_bytes(_host(root, f"{WITNESS_STATE}/{CHAIN_DIRECTORY}/{GENESIS_ENTRY}"))
        pointer_bytes = _read_bytes(_host(root, f"{WITNESS_STATE}/{POINTER_NAME}"))
    classification = scan.classification if scan is not None else None

    # ---- committed genesis exactness (only meaningful when a genesis entry exists)
    committed: dict[str, Any] = {}
    if genesis_bytes is not None and built is not None and built.built:
        try:
            document = WR.parse_document_bytes(genesis_bytes)
            unsigned = {k: v for k, v in document.items() if k != "signature"}
            committed = {"digest": RC.witness_v2_digest(document), "fieldsEqualCandidate": unsigned == dict(built.unsigned),
                         "sha256": V6._sha(genesis_bytes)}
        except Exception:  # noqa: BLE001 - malformed: the classifier reports it
            committed = {"digest": None, "fieldsEqualCandidate": False, "sha256": V6._sha(genesis_bytes)}
    pin_digest = host.genesis_pin.get("genesisWitnessDigest") if isinstance(host.genesis_pin, Mapping) else None

    # ---- the phase
    entries = store.get("listing", [])
    chain = sorted(store.get("chain", {}))
    retained = sorted(store.get("authorizations", {}))
    phase: str
    if not units_readable:
        phase = UNCLASSIFIED
    elif signer_active or holds != []:
        phase = LATER_STATE
    elif units_foreign:
        phase = FOREIGN
    elif units_unloaded or not all(base.values()):
        phase = UNCLASSIFIED
    elif not store["present"]:
        phase = W9_0 if runtime == "STOPPED" else UNCLASSIFIED
    elif store["failures"]:
        phase = FOREIGN
    elif not store["directoryExact"]:
        phase = W9_1P if (store["directoryPartialReachable"] and entries == [] and runtime == "STOPPED") else FOREIGN
    elif chain not in ([], [GENESIS_ENTRY]) or retained:
        phase = LATER_STATE
    elif classification is None:
        phase = UNCLASSIFIED
    elif classification == WR.GENESIS_MISMATCH:
        phase = W9_MISMATCH
    elif classification in (WR.CHAIN_CORRUPT, WR.TORN_TAIL):
        phase = W9_TORN
    elif classification == WR.UNINITIALIZED:
        subdirectories = bool({CHAIN_DIRECTORY, AUTHORIZATION_DIRECTORY} & set(entries))
        if runtime == "ABNORMAL":
            phase = W9_FAILED
        elif subdirectories:
            phase = W9_3
        elif entries == []:
            phase = W9_1 if runtime == "STOPPED" else UNCLASSIFIED      # a running witness always holds its lock
        elif entries == [LOCK_NAME]:
            phase = W9_2 if runtime == "RUNNING" else W9_2S
        else:
            phase = UNCLASSIFIED
    elif classification in (WR.POINTER_MISSING, WR.POINTER_CORRUPT, WR.POINTER_BEHIND_BY_ONE, WR.CONSISTENT):
        exact = (chain == [GENESIS_ENTRY] and committed.get("digest") == candidate_digest == pin_digest
                 and committed.get("fieldsEqualCandidate") is True)
        pointer_pending = classification != WR.CONSISTENT or (scan is not None and scan.discard_scratch)
        if not exact:
            phase = W9_MISMATCH
        elif pointer_pending:
            phase = W9_4
        elif pointer_bytes != genesis_bytes:
            phase = UNCLASSIFIED
        elif runtime == "RUNNING":
            phase = W9_5
        elif runtime == "STOPPED":
            phase = W9_5S
        else:
            phase = W9_ABNORMAL
    elif classification in (WR.CHAIN_MISSING, WR.ORPHAN, WR.UNEXPECTED_ENTRY, WR.SCRATCH_ORDERING_VIOLATION):
        phase = FOREIGN
    else:
        phase = UNCLASSIFIED

    service = unit_facts.get(WITNESS_SERVICE, {})
    lineage = phase in LINEAGE_COMMITTED_PHASES or (phase in (W9_TORN,) and genesis_bytes is not None)
    evidence_9a = {
        "stateDirectoryExact": bool(store.get("present")) and store.get("directoryExact") is True and not store.get(
            "failures"),
        "witnessRunning": runtime == "RUNNING",
        "storeUninitialized": classification == WR.UNINITIALIZED,
        "noLineageEntry": chain == [] and retained == [] and POINTER_NAME not in entries and SCRATCH_NAME not in entries,
    }
    evidence_9b = {
        "genesisCommitted": phase in (W9_5, W9_5S),
        "committedDigestEqualsPin": phase in (W9_5, W9_5S) and committed.get("digest") == pin_digest,
        "committedEqualsCandidate": phase in (W9_5, W9_5S) and committed.get("digest") == candidate_digest
        and committed.get("fieldsEqualCandidate") is True,
        "chainIsGenesisOnly": phase in (W9_5, W9_5S) and chain == [GENESIS_ENTRY],
        "pointerEqualsGenesis": phase in (W9_5, W9_5S) and pointer_bytes == genesis_bytes,
        "retainedAuthorizationsEmpty": phase in (W9_5, W9_5S) and retained == [],
    }
    route, reversible, owner_act, note = PHASE_TABLE[phase]
    return {
        "verifierType": VERIFIER_TYPE, "schemaVersion": 1, "environment": ENVIRONMENT, "phase": phase,
        "routing": route, "lineageReversible": reversible, "ownerAct": owner_act, "routeNote": note,
        "lineageCommitted": lineage, "evidence9a": evidence_9a, "evidence9b": evidence_9b,
        "expectedLedgerHead": expected_head, "candidateDigest": candidate_digest, "updatedAt": updated_at,
        "hostCandidateDigest": built.digest if built is not None and built.built else None,
        "genesisPinDigest": pin_digest, "committedGenesis": committed, "storeClassification": classification,
        "store": store, "runtime": runtime, "runtimePaths": runtime_paths, "units": unit_facts,
        "witnessInvocationId": service.get("InvocationID") or None, "witnessMainPid": service.get("MainPID") or None,
        "witnessNRestarts": service.get("NRestarts") or None,
        "base": base, "files": files, "ownerInputListing": listing, "hostInputReasons": reasons,
        "trust": {"phase": trust["phase"], "evidence": trust["evidence"], "registryDigest": trust["registryDigest"]},
        "signerLaterState": signer_paths, "holdStoreListing": holds, "failures": failures,
        "record1": "NOT_HOST_OBSERVABLE (owner register; absent until the separately authorized P3 ceremony)",
        "registryEffective": False, "authorityActive": False, "authorityGranted": False,
    }


# ------------------------------------------------------------- transcripts ---

def classify_stage_transcript(returncode: int | None, stdout: bytes, stderr: bytes) -> tuple[str, str | None]:
    """The one `install_authority_dev.py witness-state <RELEASE_SHA>` (stage 9A-1)."""
    if returncode is None:
        return TRANSPORT_FAILED, "NO_RETURN_CODE"
    if returncode in (96, 97):
        return GUARD_STOPPED, str(returncode)
    if returncode == 255:
        return TRANSPORT_FAILED, "SSH_255"
    try:
        report = json.loads(stdout.decode("utf-8")) if stdout.strip() else None
    except (UnicodeDecodeError, ValueError):
        report = None
    if isinstance(report, dict) and report.get("stage") == "P1B-9a":
        if returncode == 0 and report.get("result") == "PASS" and report.get("failures") == [] and stderr == b"":
            return STAGE_PASS, None
        if returncode == 1 and report.get("result") == "FAIL":
            return STAGE_STATUS_FAIL, ",".join(str(x) for x in report.get("failures", []))[:512]
        return FAILED_UNCLASSIFIED, "REPORT_NOT_EXACT"
    text = stderr.decode("utf-8", "replace").strip()
    prefix = "install_authority_dev: REFUSED "
    if returncode == 2 and not stdout.strip() and text.startswith(prefix) and "\n" not in text:
        return STAGE_REFUSED, text[len(prefix):]
    return FAILED_UNCLASSIFIED, f"EXIT_{returncode}"


def classify_start_transcript(returncode: int | None, stdout: bytes, stderr: bytes) -> tuple[str, str | None]:
    """The one `systemctl start` pair (stage 9A-2 or an authorized restart). It says only that systemd accepted
    the jobs; the host phase decides."""
    if returncode is None:
        return TRANSPORT_FAILED, "NO_RETURN_CODE"
    if returncode in (96, 97):
        return GUARD_STOPPED, str(returncode)
    if returncode == 255:
        return TRANSPORT_FAILED, "SSH_255"
    if returncode == 0 and not stdout.strip() and not stderr.strip():
        return START_OK, None
    return START_FAILED, f"EXIT_{returncode}"


def classify_bootstrap_transcript(returncode: int | None, stdout: bytes, stderr: bytes, *,
                                  candidate_digest: str) -> tuple[str, str | None]:
    """The one `lilith-recovery-witness-owner-dev bootstrap 1 <updatedAt>`. Never a lineage proof: a post-commit
    witness STOP and a pre-sign refusal print the same reason. The W9 host phase decides."""
    if returncode is None:
        return TRANSPORT_FAILED, "NO_RETURN_CODE"
    if returncode in (96, 97):
        return GUARD_STOPPED, str(returncode)
    if returncode == 255:
        return TRANSPORT_FAILED, "SSH_255"
    if returncode == 0:
        try:
            report = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return FAILED_UNCLASSIFIED, "STDOUT_NOT_JSON"
        if report == {"authorityGranted": False, "classification": "CONSISTENT", "genesisDigest": candidate_digest,
                      "pinned": True} and stderr == b"" and stdout.endswith(b"\n") and stdout.count(b"\n") == 1:
            return BOOTSTRAP_PASS, None
        return FAILED_UNCLASSIFIED, "REPORT_NOT_EXACT"
    text = stderr.decode("utf-8", "replace").strip()
    prefix = "lilith-recovery-witness-owner-dev: REFUSED "
    if returncode == 2 and not stdout.strip() and text.startswith(prefix) and "\n" not in text:
        reason = text[len(prefix):]
        if reason in BEFORE_WITNESS_REASONS:
            return BOOTSTRAP_REFUSED_BEFORE_WITNESS, reason
        if reason == "GENESIS_WITNESS_REFUSED":
            return BOOTSTRAP_WITNESS_REFUSED, reason
        if reason == "GENESIS_COMMITTED_NOT_PINNED":
            return BOOTSTRAP_COMMITTED_NOT_PINNED, reason
        return BOOTSTRAP_REFUSED_OTHER, reason
    return FAILED_UNCLASSIFIED, f"EXIT_{returncode}"


def check_health(stdout: bytes, *, expected_classification: str, kwit_public_key_sha256: str,
                 witness_key_id: str) -> dict[str, Any]:
    """The owner-socket HEALTH reply (`lilith-recovery-witness-owner-dev health`), judged against the accepted
    K-WIT identity. Read-only; obtained only after the service was observed RUNNING."""
    try:
        reply = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {"exact": False, "failures": ["HEALTH_NOT_JSON"]}
    health = reply.get("health") if isinstance(reply, dict) else None
    checks = {
        "statusOk": isinstance(reply, dict) and reply.get("status") == "OK",
        "classification": isinstance(health, dict) and health.get("classification") == expected_classification,
        "publicKeySha256": isinstance(health, dict) and health.get("publicKeySha256") == kwit_public_key_sha256,
        "witnessKeyId": isinstance(health, dict) and health.get("witnessKeyId") == witness_key_id,
        "inputsEmpty": isinstance(health, dict) and health.get("inputs") == [],
        "genericSigningNotAvailable": isinstance(health, dict) and health.get("genericSigning") == "NOT_AVAILABLE",
        "authorityNotGranted": isinstance(health, dict) and health.get("authorityGranted") is False,
        "environment": isinstance(health, dict) and health.get("environment") == ENVIRONMENT,
    }
    return {"exact": all(checks.values()), "checks": checks, "health": health,
            "failures": sorted(name for name, ok in checks.items() if not ok)}


# ---------------------------------------------------------------- sequence ---

def classify_sequence(*, host_phase: str, markers: Sequence[str], stage: str = NOT_INVOKED,
                      start: str = NOT_INVOKED, bootstrap: str = NOT_INVOKED, post9a_current: bool = False,
                      accepted9a_current: bool = False, stale9a: bool = False, post9b: bool = False) -> str:
    """The W9 sequence phase from the host phase and the operator's own records (pure). The transcript never
    proves success or absence on its own: the host phase decides, and contradictions are UNCLASSIFIED."""
    marks = set(markers)
    if host_phase not in HOST_PHASES or stage not in STAGE_CLASSES or start not in START_CLASSES \
            or bootstrap not in BOOTSTRAP_CLASSES or not marks <= {"mb9a-1", "mb9a-2", "mb9b"}:
        return UNCLASSIFIED
    if host_phase == W9_MISMATCH:
        return S9_HALT
    if host_phase in (W9_TORN, LATER_STATE, FOREIGN, UNCLASSIFIED):
        return host_phase
    if ("mb9a-2" in marks and "mb9a-1" not in marks) or ("mb9b" in marks and "mb9a-2" not in marks):
        return UNCLASSIFIED                          # markers are consumed strictly in order
    if not marks:
        return S9_0 if host_phase == W9_0 and stage == start == bootstrap == NOT_INVOKED else UNCLASSIFIED
    if "mb9b" in marks:
        if bootstrap == NOT_INVOKED:
            return UNCLASSIFIED                      # a marker is always followed by exactly one recorded invocation
        if host_phase in (W9_2, W9_3, W9_2S, W9_FAILED):
            return S9B_R if bootstrap != BOOTSTRAP_PASS else UNCLASSIFIED
        if host_phase == W9_4:
            return S9B_POINTER
        if host_phase == W9_5:
            if bootstrap == BOOTSTRAP_PASS:
                return S9B_POST_VERIFIED if post9b else S9B_POST_PENDING
            return S9B_ADOPTION_PENDING if post9b else S9B_UNACKNOWLEDGED
        if host_phase == W9_5S:
            return S9B_STOPPED
        return UNCLASSIFIED                          # W9_ABNORMAL, or a pre-witness state after a B4
    if "mb9a-2" not in marks:
        if stage == NOT_INVOKED:
            return UNCLASSIFIED
        if host_phase == W9_0:
            return S9A1_R if stage != STAGE_PASS else UNCLASSIFIED
        if host_phase == W9_1P:
            return S9A1_PARTIAL if stage != STAGE_PASS else UNCLASSIFIED
        if host_phase == W9_1:
            return S9A1_EXACT if stage == STAGE_PASS else S9A1_INCOMPLETE
        return UNCLASSIFIED
    if stage != STAGE_PASS or start == NOT_INVOKED:
        return UNCLASSIFIED                          # stage 9A-2 never runs unless stage 9A-1 was exact
    if host_phase == W9_1:
        return S9A2_R if start != START_OK else UNCLASSIFIED
    if host_phase == W9_FAILED:
        return S9A2_PARTIAL
    if host_phase == W9_2S:
        return S9A_STOPPED
    if host_phase == W9_2:
        if accepted9a_current:
            return S9A_ACCEPTED
        if post9a_current:
            return S9A_POST_VERIFIED
        if stale9a:
            return S9A_STALE
        return S9A_POST_PENDING if start == START_OK else S9A2_INCOMPLETE
    return UNCLASSIFIED                              # W9_3 / W9_4 / W9_5* without a B4 marker


# ------------------------------------------------------------------ entry ---

def main(argv: list[str]) -> int:
    try:
        if len(argv) == 4 and argv[0] == "observe":
            args = argv[1:]
        elif len(argv) == 5 and argv[0] == "expect" and argv[1] in HOST_PHASES:
            args = argv[2:]
        else:
            raise Refused("USAGE")
        V6.require_dev_root()
        if RELEASE_TREE not in sys.path:
            sys.path.insert(0, RELEASE_TREE)
        report = evaluate(*args)
    except (Refused, V6.Refused, V8.Refused) as exc:
        print(f"mb9_witness_verifier: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(report, sort_keys=True, indent=2) + "\n")
    if argv[0] == "expect":
        return 0 if report["phase"] == argv[1] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
