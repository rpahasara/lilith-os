#!/usr/bin/env python3
"""15B2b-B1b-3e E-19: the PROPOSED `UPGRADE_FROM_P1B10_DEV_SYNTHETIC` release-maintenance contract (SYNTHETIC ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-e19-release-maintenance.md.
DESIGN / SOURCE ONLY. E19-D1 … E19-D5 are PROPOSED. Nothing here replaces a release, stops or starts a witness,
loads K-WIT, rebinds custody, changes HELD or the ledger, starts the signer, loads K-ACT or activates authority.

Owner workstation, stdlib only. It reads local files, writes nothing and contacts nothing. There is no host
observer for this contract yet: `classify` judges a recorded observation document (the closed schema below), and the
synthetic tests build those documents. A live observer, the installer stages and the restart path are later slices.

The transition replaces release `aee323e` (the defective E-19 judge) by a NEW release whose payload differs from it
in exactly `lilith_owner_memory/pr1_acceptance.py` (and the manifest). Units and CLIs are byte-identical, so there is
no unit, daemon-reload or CLI step. Because `current` is the witness's WorkingDirectory and ExecStart path, and the
witness imports `pr1_acceptance`, the running witness must NEVER run across a selector change or from a retired tree:

    U0 P1B10 exact            1 release (OLD), current -> OLD, accepted witness incarnation running from OLD
    U1 NEW staged             2 releases, current -> OLD, the SAME incarnation running from OLD   (staging exception)
    U2 witness stopped        2 releases, current -> OLD, service and both sockets inactive        (staging exception)
    U3 NEW selected           2 releases, current -> NEW, witness stopped                          (staging exception)
    U4 replacement running    2 releases, current -> NEW, ONE new incarnation (one K-WIT load) from NEW
    U5 OLD retired            1 release (NEW), the ACCEPTED replacement incarnation running from NEW

    restart != preservation of the original InvocationID;  one start go != one K-WIT load (counted, never inferred)
    technical phase != owner acceptance;  classification != permission;  STOP != repair;  no rollback

Forms:

    ... classify <observation.json> [<baseline.json>]   the pure judgement of a recorded observation
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

MODE = "UPGRADE_FROM_P1B10_DEV_SYNTHETIC"
OBSERVATION_TYPE = "LILITH_E19_P1B10_UPGRADE_OBSERVATION"
STATUS = "PROPOSED_NOT_ACCEPTED"
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
MAX_OBSERVATION = 256 * 1024

# ------------------------------------------------------------------ releases ---
OPT = "/opt/lilith-authority-dev"
OLD_RELEASE = "aee323e94412accbe321bc84eae78c5b8cf95afc"                                       # PR-1A (RR-33)
OLD_MANIFEST_SHA256 = "1d578ca707a95134dab218c826408b4380e7af0b5839160f47ede37232b94e8f"
# The NEW release does not exist. Only a merged owner record (after a build attestation) may set these.
NEW_RELEASE: str | None = None
NEW_MANIFEST_SHA256: str | None = None

# ------------------------------------------------------- the E-19 source delta ---
PR1_ACCEPTANCE_MEMBER = "lilith_owner_memory/pr1_acceptance.py"
PR1_ACCEPTANCE_SOURCE = "services/owner-memory-control/lilith_owner_memory/pr1_acceptance.py"
PR1_ACCEPTANCE_OLD_SHA256 = "e0928854e1fcf4107458939ba9ebf1903cf7a4d0ab6808f7e89108db1444bbff"   # aee323e
PR1_ACCEPTANCE_E19_SHA256 = "0d2e6ccabf916425a1dfa7dc587bfcb3d7a232eb6c52c5cd938d573199715cff"
ACTIVATION_LINE_OLD = "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT"
ACTIVATION_LINE_E19 = "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=false"
# The exact edits (aee323e bytes -> E-19 bytes). `reverse_e19` proves the diff is these edits and nothing else.
E19_EDITS = (
    (b'ACTIVATION_DARK_LINE = "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT"\n',
     b'# E-19: the COMPLETE line the B1c activation verifier prints while the grant is absent\n'
     b'# (`scripts/dev_deployer/lilith_activation_verify.py`, NOT_ACCEPTED branch), byte-identical in every\n'
     b'# preserved DEV host POST. Exact equality only: no prefix, trim, case or field-order tolerance.\n'
     b'ACTIVATION_DARK_LINE = "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=false"\n'
     b'\n'
     b'\n'
     b'def _activation_evidence(value: Any) -> str | None:\n'
     b'    """The observed line as package evidence: a UTF-8-encodable `str`, else None (never a canonicalization'
     b' crash)."""\n'
     b'    if type(value) is not str:\n'
     b'        return None\n'
     b'    try:\n'
     b'        value.encode("utf-8")\n'
     b'    except UnicodeEncodeError:\n'
     b'        return None\n'
     b'    return value\n'),
    (b'           and activation.line == ACTIVATION_DARK_LINE and activation.b1c_unchanged is True\n',
     b'           and type(activation.line) is str and activation.line == ACTIVATION_DARK_LINE\n'
     b'           and activation.b1c_unchanged is True\n'),
    (b'    evidence["activation"] = None if not isinstance(activation, ActivationObservationV1) else {\n'
     b'        "line": activation.line, "b1cUnchanged": activation.b1c_unchanged}\n',
     b'    # A malformed value FAILs above and is evidenced as null: it never reaches (or crashes) the package digest.\n'
     b'    evidence["activation"] = None if not isinstance(activation, ActivationObservationV1) else {\n'
     b'        "line": _activation_evidence(activation.line),\n'
     b'        "b1cUnchanged": activation.b1c_unchanged if type(activation.b1c_unchanged) is bool else None}\n'),
)
# The only release payload member that differs from aee323e (the manifest aside). Record §3.2.
PAYLOAD_DELTA = {PR1_ACCEPTANCE_MEMBER: (PR1_ACCEPTANCE_OLD_SHA256, PR1_ACCEPTANCE_E19_SHA256)}


class Refused(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        super().__init__(reason if detail is None else f"{reason}:{detail}")
        self.reason = reason
        self.detail = detail


def _need(condition: bool, reason: str, detail: str | None = None) -> None:
    if not condition:
        raise Refused(reason, detail)


def _sha(data: bytes) -> str:
    return hashlib.sha256(bytes(data)).hexdigest()


def reverse_e19(data: bytes) -> bytes:
    """The aee323e bytes of `pr1_acceptance.py`, from the E-19 bytes, by undoing exactly `E19_EDITS`."""
    _need(_sha(data) == PR1_ACCEPTANCE_E19_SHA256, "E19_SOURCE_NOT_PINNED")
    for old, new in E19_EDITS:
        _need(data.count(new) == 1, "E19_EDIT_NOT_UNIQUE")
        data = data.replace(new, old)
    _need(_sha(data) == PR1_ACCEPTANCE_OLD_SHA256, "E19_REVERSAL_NOT_AEE323E")
    return data


def new_release_module_pins(old_pins: Mapping[str, str]) -> dict[str, str]:
    """The expected NEW release module map, from the accepted aee323e module pins: exactly `PAYLOAD_DELTA` moves."""
    pins = dict(old_pins)
    for member, (before, after) in PAYLOAD_DELTA.items():
        if member in pins:
            _need(pins[member] == before, "OLD_MODULE_PIN_UNEXPECTED", member)
            pins[member] = after
    return pins


# ----------------------------------------------------------------- the FROM state ---
# Facts that must stay byte-identical through every phase (accepted repository records; never host values).
PRESERVED_PINS = {
    "kActCurrentBlobSha256": "6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3",      # B-5 / §24
    "kActPublicationFileSha256": "d76479762007afef828f3901591647dc4a2fb2205f4afac527b66d2cc9c6b032",
    "kWitBlobSha256": "f87593701ee5e9272363a473a115b87cc06179df3c0b233af4aa62bb5b9b97be",             # M-B2
    "registryRootAnchorSha256": "bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687",   # M-B4
    "witnessAnchorSha256": "be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a",
    "registrySha256": "46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e",              # M-B5
    "ledgerHead": "19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630",                  # M-B6
    "witnessGenesis": "ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4",              # M-B9b
    "witnessChain1Sha256": "252c32204bebf3fa1ca0981d8791115e2abb6cd8ddb0925285c64213317cfb99",
    "witnessJsonSha256": "252c32204bebf3fa1ca0981d8791115e2abb6cd8ddb0925285c64213317cfb99",
    "holdListing": ["1ee1b7d5797b9c39b941befbbe4a5917b7fe510fa48a0f487f801246f80071d6.json"],           # M-B10
    "heldSha256": "c713ea1d2e0b016e59eb55ddc1a125561495ed4cc0a2c24764f36c8355d0216d",
    "brokerInvocationId": "ed35e343bc9f4ec687f753ed7b3a53b2",                                         # re-pin
    "brokerMainPid": "3411",
    "brokerBaselineSha256": "ff3a432d9d8e5c23718be41898be9568dd8914f0e2e28bb4c27f8e0bccaa3ef1",
    "brokerPreservation": "PASS",
    "activationLine": ACTIVATION_LINE_E19,                     # the host line; unchanged by any release change
}
# Host facts recorded at U0 and required byte-identical afterwards (no repository pin exists for them).
PRESERVED_HOST_FACTS = ("kActCurrentBlobIdentity", "kWitBlobIdentity", "hostKeyIdentity", "credstoreListing",
                        "custodyListing", "witnessCredentialListing", "ledgerBytesSha256", "ownerInputsSha256",
                        "signerUnitFilesSha256", "witnessUnitFilesSha256", "installedClisSha256")
PRESERVED_FIELDS = frozenset(PRESERVED_PINS) | frozenset(PRESERVED_HOST_FACTS)
BOOT_ID = "cb0d71da-32a7-402b-b85e-5748da012bff"

# The witness incarnation that ENDS (post-reboot re-pin, owner-accepted 2026-10-09). The Package B B3 incarnation
# 5136ea7af2544450b9370fa412786c98 / 143946 ended at the 2026-10-09 M-R1 reboot and is historical: never expected.
ENDING_INCARNATION = ("8af12bd64d024d0eba56bbcedbc534a6", "1580")
HISTORICAL_INCARNATIONS = (("5136ea7af2544450b9370fa412786c98", "143946"),)
KWIT_PUBLIC_KEY_SHA256 = "5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf"
# Replacement incarnations accepted by a merged owner record (InvocationID -> MainPID). EMPTY.
ACCEPTED_REPLACEMENT_INCARNATIONS: Mapping[str, str] = {}

# ------------------------------------------------------------ observation schema ---
FIELDS = frozenset({"observationType", "schemaVersion", "mode", "oldRelease", "newRelease", "bootId",
                    "optEntries", "releaseEntries", "currentTarget", "treeVerified", "witness", "signer",
                    "preserved"})
WITNESS_FIELDS = frozenset({"service", "ownerSocket", "signerSocket", "cwd", "invocationsSinceBaseline",
                            "health", "kWitPublicKeySha256"})
SERVICE_FIELDS = frozenset({"ActiveState", "SubState", "MainPID", "InvocationID", "NRestarts", "Result"})
SIGNER_FIELDS = frozenset({"ActiveState", "SubState", "MainPID", "InvocationID", "NRestarts", "UnitFileState",
                           "DropInPaths", "invocationsEver"})
SIGNER_DARK = {"ActiveState": "inactive", "SubState": "dead", "MainPID": "0", "InvocationID": "", "NRestarts": "0",
               "UnitFileState": "static", "DropInPaths": "", "invocationsEver": []}
OPT_EXACT = ["current", "releases"]
SELECTOR_RESIDUE = ".current.tmp"

# ---------------------------------------------------------------------- phases ---
U0 = "U0_P1B10_EXACT"
U1 = "U1_NEW_STAGED_WITNESS_ON_OLD"
U2 = "U2_WITNESS_STOPPED_OLD_SELECTED"
U3 = "U3_NEW_SELECTED_WITNESS_STOPPED"
U4 = "U4_REPLACEMENT_RUNNING_ON_NEW"
U5 = "U5_OLD_RETIRED_REPLACEMENT_ACCEPTED"
EXACT_PHASES = (U0, U1, U2, U3, U4, U5)
TWO_RELEASE_PHASES = (U1, U2, U3, U4)        # the ONLY scope of the temporary staging exception
# HALT: a preserved custody fact or the signer is not exact. Never continued by this contract.
HALT_PRESERVED = "UH_PRESERVED_FACT_CHANGED"
HALT_SIGNER = "UH_SIGNER_NOT_DARK"
# STOP: owner adjudication; never repaired, retried or rolled back here.
UNKNOWN = "US_UNKNOWN"
STOP_BOOT = "US_BOOT_CHANGED"
STOP_STAGING = "US_STAGING_RESIDUE"
STOP_SELECTOR = "US_SELECTOR_RESIDUE"
STOP_RELEASE_SET = "US_RELEASE_SET_FOREIGN"
STOP_NEW_TREE = "US_NEW_TREE_INVALID"
STOP_OLD_TREE = "US_OLD_TREE_CHANGED"
STOP_RETIRE_PARTIAL = "US_RETIRE_PARTIAL"
STOP_MIXED = "US_WITNESS_RUNNING_ACROSS_SELECT"
STOP_DELETED = "US_WITNESS_ON_RETIRED_RELEASE"
STOP_WITNESS_TRANSITIONAL = "US_WITNESS_TRANSITIONAL"
STOP_ORIGINAL_RESTARTED = "US_ENDING_INCARNATION_CHANGED"
STOP_LOADS = "US_KWIT_LOADS_NOT_EXACTLY_ONE"
STOP_START_FAILED = "US_REPLACEMENT_START_FAILED"
STOP_RESTARTED_ON_OLD = "US_REPLACEMENT_ON_OLD_RELEASE"
STOP_OUT_OF_ORDER = "US_OUT_OF_ORDER"
STOP_RETIRED_EARLY = "US_RETIRED_BEFORE_INCARNATION_ACCEPTED"
STOP_UNHEALTHY = "US_REPLACEMENT_NOT_CONSISTENT"
HALT_PHASES = (HALT_PRESERVED, HALT_SIGNER)
STOP_PHASES = (UNKNOWN, STOP_BOOT, STOP_STAGING, STOP_SELECTOR, STOP_RELEASE_SET, STOP_NEW_TREE, STOP_OLD_TREE,
               STOP_RETIRE_PARTIAL, STOP_MIXED, STOP_DELETED, STOP_WITNESS_TRANSITIONAL, STOP_ORIGINAL_RESTARTED,
               STOP_LOADS, STOP_START_FAILED, STOP_RESTARTED_ON_OLD, STOP_OUT_OF_ORDER, STOP_RETIRED_EARLY,
               STOP_UNHEALTHY)

# Exact phase -> the next proposed step and the separate owner act it would need. Routing authorizes NOTHING.
ROUTES = {
    U0: ("STAGE_NEW_RELEASE", "E19-GO-STAGE (installer stage for this mode: NOT IMPLEMENTED)"),
    U1: ("STOP_WITNESS_SERVICE_AND_SOCKETS", "E19-GO-STOP: ends incarnation 8af12bd6…/1580 (separate authorization)"),
    U2: ("SELECT_NEW_RELEASE", "E19-GO-SELECT (atomic symlink + rename; witness stays stopped)"),
    U3: ("START_REPLACEMENT_WITNESS", "E19-GO-START: one start of both sockets and the service; one K-WIT load"),
    U4: ("POST9A_R_THEN_OWNER_ACCEPTANCE_THEN_RETIRE_OLD",
         "owner acceptance of the replacement incarnation (merged record), then E19-GO-RETIRE"),
    U5: ("FINAL_POST_AND_FIRST_DEPLOY_DR5_THEN_OWNER_COMPLETION", "E19 completion acceptance (not package READY)"),
}
# Every non-exact class -> its safe STOP and recovery rule. No automatic rollback, cleanup, restart or K-WIT reload.
RECOVERY = {
    HALT_PRESERVED: "HALT. A custody, HELD, ledger, genesis, trust or broker fact moved. Freeze; owner forensics.",
    HALT_SIGNER: "HALT. The signer is not dark (a K-ACT load or activity). Freeze; owner forensics (M-B11 rules).",
    UNKNOWN: "STOP. Re-observe read-only; an unobservable fact is never success.",
    STOP_BOOT: "STOP. A reboot ended the incarnation and the sockets; re-baseline under owner adjudication.",
    STOP_STAGING: "STOP. Interrupted stage: witness and current untouched; residue removal is one separate owner act.",
    STOP_SELECTOR: "STOP. Interrupted select: current is still one exact target (rename is atomic); witness stays "
                   "stopped; residue removal is one separate owner act.",
    STOP_RELEASE_SET: "STOP. A release set this contract cannot produce; owner forensics.",
    STOP_NEW_TREE: "STOP. The NEW tree does not verify; it is never selected or started; owner adjudication.",
    STOP_OLD_TREE: "STOP. The OLD tree changed before retirement; owner forensics.",
    STOP_RETIRE_PARTIAL: "STOP. Interrupted retire: the replacement runs from NEW only; completing the removal is "
                         "one separate owner act.",
    STOP_MIXED: "STOP. The ending incarnation runs while current -> NEW (lazy imports could load NEW bytes). Never "
                "an endpoint; the only exit is the separately authorized stop.",
    STOP_DELETED: "STOP. A witness runs from a retired tree. Never an endpoint; owner adjudication.",
    STOP_WITNESS_TRANSITIONAL: "STOP. Activating, deactivating, failed, auto-restart or sockets not matching the "
                               "service. Never retried automatically.",
    STOP_ORIGINAL_RESTARTED: "STOP. The ending incarnation restarted or changed identity outside this contract.",
    STOP_LOADS: "STOP. The journal shows a number of witness invocations (K-WIT loads) other than exactly one.",
    STOP_START_FAILED: "STOP. A start attempt loaded K-WIT and the witness is not running. No retry without a new "
                       "owner go; every attempt is a counted load.",
    STOP_RESTARTED_ON_OLD: "STOP. A replacement incarnation runs from OLD. Not this contract; owner adjudication.",
    STOP_OUT_OF_ORDER: "STOP. A step ran out of the U0..U5 order; owner adjudication (no reverse path exists).",
    STOP_RETIRED_EARLY: "STOP. OLD retired before the replacement incarnation was accepted by a merged record.",
    STOP_UNHEALTHY: "STOP. The replacement does not report CONSISTENT health with the custodied K-WIT.",
}
assert set(RECOVERY) == set(HALT_PHASES) | set(STOP_PHASES) and set(ROUTES) == set(EXACT_PHASES)


def _exact(value: Any, fields: frozenset[str], name: str) -> Mapping[str, Any]:
    _need(isinstance(value, Mapping) and set(value) == fields, "OBSERVATION_FIELDS", name)
    return value


def parse_observation(document: Any, *, new_release: str) -> Mapping[str, Any]:
    """The closed schema. `None` is the only spelling of an unobserved value (-> UNKNOWN), never a default."""
    doc = _exact(document, FIELDS, "observation")
    _need(doc["observationType"] == OBSERVATION_TYPE and doc["schemaVersion"] == 1 and doc["mode"] == MODE,
          "OBSERVATION_TYPE")
    _need(doc["oldRelease"] == OLD_RELEASE and doc["newRelease"] == new_release, "OBSERVATION_RELEASES")
    witness = _exact(doc["witness"], WITNESS_FIELDS, "witness")
    for name in ("service", "ownerSocket", "signerSocket"):
        if witness[name] is not None:
            _exact(witness[name], SERVICE_FIELDS if name == "service" else frozenset({"ActiveState"}), name)
    if doc["signer"] is not None:
        _exact(doc["signer"], SIGNER_FIELDS, "signer")
    if doc["preserved"] is not None:
        _exact(doc["preserved"], PRESERVED_FIELDS, "preserved")
    for name in ("optEntries", "releaseEntries"):
        _need(doc[name] is None or (isinstance(doc[name], list) and all(isinstance(x, str) for x in doc[name])),
              "OBSERVATION_FIELDS", name)
    _need(doc["treeVerified"] is None or (isinstance(doc["treeVerified"], Mapping) and all(
        _SHA40.fullmatch(k) and (v is None or type(v) is bool) for k, v in doc["treeVerified"].items())),
        "OBSERVATION_FIELDS", "treeVerified")
    return doc


def _unknowns(doc: Mapping[str, Any]) -> list[str]:
    out = [name for name in ("bootId", "optEntries", "releaseEntries", "treeVerified", "signer", "preserved")
           if doc[name] is None]
    witness = doc["witness"]
    out += [f"witness.{name}" for name in ("service", "ownerSocket", "signerSocket", "invocationsSinceBaseline")
            if witness[name] is None]
    if doc["treeVerified"] is not None:
        out += [f"treeVerified.{sha}" for sha, value in sorted(doc["treeVerified"].items()) if value is None]
    return out


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _service_state(witness: Mapping[str, Any]) -> str:
    """RUNNING, STOPPED or TRANSITIONAL. Both sockets must match the service (a listening socket while the service
    is stopped would start it, and load K-WIT, on the next connection)."""
    service, owner, signer = witness["service"], witness["ownerSocket"], witness["signerSocket"]
    sockets = (owner["ActiveState"], signer["ActiveState"])
    if (service["ActiveState"], service["SubState"]) == ("active", "running") and service["MainPID"] not in ("", "0") \
            and service["NRestarts"] == "0" and sockets == ("active", "active"):
        return "RUNNING"
    if (service["ActiveState"], service["SubState"], service["MainPID"]) == ("inactive", "dead", "0") \
            and service["Result"] == "success" and sockets == ("inactive", "inactive"):
        return "STOPPED"
    return "TRANSITIONAL"


def classify(document: Any, baseline: Any = None, *, new_release: str | None = NEW_RELEASE,
             accepted_replacements: Mapping[str, str] = ACCEPTED_REPLACEMENT_INCARNATIONS) -> dict[str, Any]:
    """One judgement. Precedence: HALT, then UNKNOWN, then STOP classes, then the exact phases."""
    _need(isinstance(new_release, str) and _SHA40.fullmatch(new_release) is not None and new_release != OLD_RELEASE,
          "NEW_RELEASE_NOT_ESTABLISHED")
    doc = parse_observation(document, new_release=new_release)
    base = None if baseline is None else parse_observation(baseline, new_release=new_release)
    reasons: list[str] = []

    def result(phase: str, *more: str) -> dict[str, Any]:
        exact = phase in EXACT_PHASES
        return {"mode": MODE, "status": STATUS, "phase": phase, "reasons": reasons + list(more),
                "twoReleaseException": phase in TWO_RELEASE_PHASES,
                "next": ROUTES[phase][0] if exact else "STOP", "ownerAct": ROUTES[phase][1] if exact else None,
                "recovery": None if exact else RECOVERY[phase], "packageReadyAdmissible": False,
                "authorizes": "NOTHING"}

    # ---- HALT (proven facts first, even when other parts are unknown)
    preserved = doc["preserved"]
    if preserved is not None:
        moved = sorted(name for name, pin in PRESERVED_PINS.items() if preserved[name] != pin)
        if base is not None:
            _need(base["preserved"] is not None, "BASELINE_INCOMPLETE")
            moved += sorted(name for name in PRESERVED_HOST_FACTS
                            if _canonical(preserved[name]) != _canonical(base["preserved"][name]))
        if moved:
            return result(HALT_PRESERVED, *("PRESERVED:" + name for name in moved))
    if doc["signer"] is not None and any(doc["signer"][k] != v for k, v in SIGNER_DARK.items()):
        return result(HALT_SIGNER)

    # ---- UNKNOWN
    missing = _unknowns(doc)
    if missing:
        return result(UNKNOWN, *("UNOBSERVED:" + name for name in missing))
    if doc["bootId"] != BOOT_ID:
        return result(STOP_BOOT)

    # ---- the release set and the selector
    old, new = OLD_RELEASE, new_release
    entries = doc["releaseEntries"]
    if f".{new}.staging" in entries:
        return result(STOP_STAGING)
    shas = frozenset(entries)
    if len(entries) != len(shas) or any(not _SHA40.fullmatch(e) for e in entries) \
            or shas not in (frozenset({old}), frozenset({old, new}), frozenset({new})):
        return result(STOP_RELEASE_SET, "ENTRIES:" + ",".join(sorted(entries)))
    if SELECTOR_RESIDUE in doc["optEntries"]:
        return result(STOP_SELECTOR)
    target = doc["currentTarget"]
    if sorted(doc["optEntries"]) != OPT_EXACT or target not in (f"releases/{old}", f"releases/{new}") \
            or target.split("/", 1)[1] not in shas:
        return result(STOP_RELEASE_SET, f"SELECTOR:{target}")
    _need(set(doc["treeVerified"]) == shas, "OBSERVATION_FIELDS", "treeVerified")
    if new in shas and not doc["treeVerified"][new]:
        return result(STOP_NEW_TREE)

    # ---- the witness
    witness = doc["witness"]
    service = witness["service"]
    state = _service_state(witness)
    loads = witness["invocationsSinceBaseline"]
    _need(isinstance(loads, list) and all(isinstance(x, str) and _HEX32.fullmatch(x) for x in loads),
          "OBSERVATION_FIELDS", "invocationsSinceBaseline")
    cwd = witness["cwd"]
    if state == "RUNNING" and cwd not in tuple(f"{OPT}/releases/{sha}" for sha in shas):
        return result(STOP_DELETED, f"CWD:{cwd}")
    if old in shas and not doc["treeVerified"][old]:
        running_new = state == "RUNNING" and cwd == f"{OPT}/releases/{new}" and target == f"releases/{new}"
        return result(STOP_RETIRE_PARTIAL if running_new and service["InvocationID"] in accepted_replacements
                      else STOP_OLD_TREE)
    if state == "TRANSITIONAL":
        return result(STOP_WITNESS_TRANSITIONAL, f"SERVICE:{service['ActiveState']}/{service['SubState']}")
    if base is None:
        _need(shas == frozenset({old}) and state == "RUNNING" and loads == [], "BASELINE_REQUIRED")

    identity = (service["InvocationID"], service["MainPID"])
    if state == "RUNNING" and service["InvocationID"] == ENDING_INCARNATION[0]:
        if identity != ENDING_INCARNATION or loads:
            return result(STOP_ORIGINAL_RESTARTED)
        if target == f"releases/{new}":
            return result(STOP_MIXED)
        if cwd != f"{OPT}/releases/{old}":
            return result(STOP_ORIGINAL_RESTARTED, f"CWD:{cwd}")
        if witness["health"] != "CONSISTENT" or witness["kWitPublicKeySha256"] != KWIT_PUBLIC_KEY_SHA256:
            return result(STOP_ORIGINAL_RESTARTED, "HEALTH")
        return result(U0 if shas == frozenset({old}) else U1)
    if state == "STOPPED":
        if loads:
            return result(STOP_START_FAILED, f"LOADS:{len(loads)}")
        if shas != frozenset({old, new}):
            return result(STOP_OUT_OF_ORDER, "STOPPED_WITHOUT_TWO_RELEASES")
        return result(U2 if target == f"releases/{old}" else U3)
    # RUNNING, another incarnation: the replacement (or not this contract)
    if identity in HISTORICAL_INCARNATIONS:
        return result(STOP_ORIGINAL_RESTARTED, "HISTORICAL_INCARNATION")
    if loads != [service["InvocationID"]]:
        return result(STOP_LOADS, f"LOADS:{len(loads)}")
    if cwd != f"{OPT}/releases/{new}" or target != f"releases/{new}":
        return result(STOP_RESTARTED_ON_OLD, f"CWD:{cwd}")
    if witness["health"] != "CONSISTENT" or witness["kWitPublicKeySha256"] != KWIT_PUBLIC_KEY_SHA256:
        return result(STOP_UNHEALTHY)
    if shas == frozenset({old, new}):
        return result(U4)
    if accepted_replacements.get(service["InvocationID"]) != service["MainPID"]:
        return result(STOP_RETIRED_EARLY)
    return result(U5)


def package_ready_admissible(verdict: Mapping[str, Any], *, release_sha: str,
                             new_release: str | None = NEW_RELEASE) -> tuple[bool, str]:
    """The M-B12 package READY gate across this transition. READY is never admissible while two releases are
    installed (the judge's own E-01 also refuses: `release_entries == [release_sha]`), never on aee323e (its
    E-19 cannot pass on the real host line), and never on a HALT / STOP / UNKNOWN."""
    phase = verdict.get("phase")
    if phase in TWO_RELEASE_PHASES:
        return False, "TWO_RELEASE_INTERMEDIATE"
    if phase not in EXACT_PHASES:
        return False, "NOT_EXACT"
    if phase == U0 or release_sha == OLD_RELEASE:
        return False, "INSTALLED_RELEASE_E19_DEFECT"
    if new_release is None or release_sha != new_release:
        return False, "RELEASE_NOT_THE_ACCEPTED_NEW_RELEASE"
    return True, "U5_SINGLE_NEW_RELEASE"


# ------------------------------------------------------------- DR-5 release delta ---
# The routine DR-5 script (`scripts/deployer_authority_boundary_proof.sh`) prints the release directory twice: once
# for the `releases/` listing and once for the `current` target. No other line names a release. Record §6.
DR5_RELEASE_LINE = "DENIED: test -w /opt/lilith-authority-dev/releases/{sha}"
DR5_RELEASE_LINE_COUNTS = {"result-set": 2, "dr5-block": 2, "predeploy-block": 0}
# The replaced post-upgrade targets (derived later from the accepted W10_1 texts; PROPOSED; no pins exist).
NEW_DR5_TARGETS: Mapping[str, Any] = {"WITNESS_RUNNING_HELD_E19": None,
                                       "WITNESS_STATE_PRESENT_SERVICE_STOPPED_HELD_E19": None}


def derive_release_swap(texts: Mapping[str, list[str]], *, old: str, new: str) -> dict[str, list[str]]:
    """The single-release DR-5 texts for NEW from the accepted single-release texts for OLD: exactly the release
    lines move, in place; every other line keeps its text and order. Intermediate phases have NO target."""
    _need(_SHA40.fullmatch(old) is not None and _SHA40.fullmatch(new) is not None and old != new, "RELEASE_SHA")
    _need(set(texts) == set(DR5_RELEASE_LINE_COUNTS), "DR5_SETS")
    before, after = DR5_RELEASE_LINE.format(sha=old), DR5_RELEASE_LINE.format(sha=new)
    out = {}
    for name, lines in texts.items():
        _need(lines.count(before) == DR5_RELEASE_LINE_COUNTS[name], "DR5_RELEASE_LINE_COUNT", name)
        _need(not any(new in line for line in lines), "DR5_NEW_RELEASE_ALREADY_PRESENT", name)
        _need(all(line == before or old not in line for line in lines), "DR5_OTHER_LINE_NAMES_RELEASE", name)
        out[name] = [after if line == before else line for line in lines]
    return out


# ------------------------------------------------------------ pin replacement map ---
# Files with a CURRENT aee323e binding that the upgrade invalidates (re-pinned only after NEW exists; record §7).
CURRENT_RELEASE_BINDINGS = {
    "services/owner-memory-control/tools/mb6_operator.py":
        "RELEASE_SHA + RELEASE_MODULES/PROVISION_MODULES, reused by mb9_operator.readiness_ok (the mb10 host POST)",
    "services/owner-memory-control/tools/mb9_operator.py": "RELEASE_SHA (= mb6) in status --expect and readiness",
    "services/owner-memory-control/tools/mb11_signer_verifier.py": "RELEASE_SHA / RELEASE_CWD",
    "services/owner-memory-control/tools/mb11_restart_boundary_install.py": "RELEASE_SHA (fragment bytes unchanged)",
    "services/owner-memory-control/tools/mb12_os_denial_proof.py": "fragment provenance text only (bytes unchanged)",
    "services/owner-memory-control/tools/mb12_pr3_material.py": "releaseSha / releaseManifestSha256",
    "services/owner-memory-control/tools/mb12_readiness_inputs.py": "DEV_PINS releaseSha / attestedManifestSha256",
}
# Completed, owner-accepted ceremonies: never re-run, byte-unchanged; they refuse NEW by their own pins.
HISTORICAL_RELEASE_BINDINGS = frozenset({
    "services/owner-memory-control/tools/mb4_mb5_operator.py",
    "services/owner-memory-control/tools/mb6_ledger_verifier.py",
    "services/owner-memory-control/tools/mb7_mb8_operator.py",
})


def _read_json(path: str) -> Any:
    raw = Path(path).read_bytes()
    _need(len(raw) <= MAX_OBSERVATION, "OBSERVATION_TOO_LARGE")
    return json.loads(raw)


def main(argv: list[str]) -> int:
    try:
        if len(argv) in (2, 3) and argv[0] == "classify":
            verdict = classify(_read_json(argv[1]), None if len(argv) == 2 else _read_json(argv[2]))
            sys.stdout.write(json.dumps(verdict, sort_keys=True) + "\n")
            return 0 if verdict["phase"] in EXACT_PHASES else 2
        sys.stderr.write("usage: e19_p1b10_upgrade.py classify <observation.json> [<baseline.json>]\n")
        return 64
    except (Refused, OSError, ValueError) as exc:
        sys.stderr.write(f"e19_p1b10_upgrade: REFUSED {exc}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
