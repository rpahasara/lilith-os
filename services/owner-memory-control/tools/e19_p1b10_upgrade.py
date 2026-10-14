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

Every phase requires the effective witness restart boundary (`Restart=no`; sockets `StopWhenUnneeded` /
`RefuseManualStart`) and counts witness invocations (K-WIT loads) after the owner-accepted U0 journal cursor.

    restart != preservation of the original InvocationID;  one start go != one K-WIT load (counted, never inferred)
    technical phase != owner acceptance;  classification != permission;  STOP != repair;  no rollback

Forms:

    ... classify <observation.json> [<u0-acceptance.json> [<replacement-acceptance.json>]]
        the pure judgement of a recorded observation, against the owner-accepted U0 baseline bundle (R1) and, for
        U5, the verified local replacement-incarnation acceptance bundle (R2)
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
# The NEW release: the owner-authorized pin of the independently attested build (record
# slice-15b2b-b1b3e-e19-new-release-pin.md). NEW_RELEASE is the SOURCE commit the archive was built from (the PR #193
# merge), never the commit that carries this pin. It is a proposed target only: the INSTALLED release stays OLD
# until the owner-authorized U2 -> U3 select, and every current read path keeps its OLD pins.
NEW_RELEASE: str | None = "ba943e1a188d98f4108c9eec7149c0cf1a8f68bb"
NEW_MANIFEST_SHA256: str | None = "b8393015e505495a81629411a4ecd33c0c372c7b16d2761094eb4e018bc300a2"
# Provenance of that pin (two independent builds, Windows + WSL, byte-identical; `attest_authority_dev_build.py`).
# Record only: staging verifies the archive against its builder stamp and NEW_MANIFEST_SHA256.
NEW_RELEASE_ATTESTATION = {
    "archiveSha256": "a4ad24e8c261c6e5858c559f4102ac8d6cc6923cfc19a9a7ffe5720408ae3faf",
    "archiveByteSize": 5355042,
    "builderStampSha256": "cc1695184453c99bd0d0ffd3c18fca8eaf2b979e9f33a4c2a6fbd1b236837211",
    "attestationDigest": "d6f7f709d3b40dc42d6fb9c936137bb6c6871c36917c9d27f8f2faa634ff51d2",
    "buildRecipeSha256": "aa1c5200db931553271897f18a53306bd7c5ab6726d3b484b74d0b1e134ce092",
    "authorityReleaseDigest": "5a7c990318e74fd3c8a5e39259a9382cbc7f3971ce38efad0fdc425c61a45f58",
    "evidenceManifestSha256": "b502b8dab36fa72349c5f386e02522b1a9b0325a4072c6a4189265979a7c21a7",
}

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
     b'    # A malformed value FAILs above and is evidenced as null: it never reaches (or crashes)'
     b' the package digest.\n'
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
# Host facts recorded in the owner-accepted U0 baseline and required byte-identical afterwards.
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
KWIT_KEY_ID = "test-only.witness.dev-synthetic.b1b3d.1"
HEALTH_EXACT = {"classification": "CONSISTENT", "publicKeySha256": KWIT_PUBLIC_KEY_SHA256, "witnessKeyId": KWIT_KEY_ID}

# ------------------------------------------------------ witness restart boundary (R4) ---
# The unit files have `Restart=on-failure` (RestartSec=5s, StartLimitBurst=3 / 60 s) and two `Accept=no` sockets
# with `Service=lilith-recovery-witness.service`: a crash of a running witness, or any connection to a listening
# socket of a stopped one, would exec it again and load K-WIT without a go. The P1B-10R pattern closes both: the
# service never restarts by itself, and a socket stops when no started witness needs it and refuses a manual start
# (so it can never be left listening alone). PREREQUISITE of the maintenance transition, effective already at U0
# (the ending incarnation may crash too). Candidate files only: NOT accepted, NOT installed (E19-D3).
WITNESS_SERVICE = "lilith-recovery-witness.service"
OWNER_SOCKET = "lilith-recovery-witness-owner.socket"
SIGNER_SOCKET = "lilith-recovery-witness-signer.socket"
WITNESS_UNITS = (WITNESS_SERVICE, OWNER_SOCKET, SIGNER_SOCKET)
UNIT_DIR = "/etc/systemd/system"
DROPIN_SOURCE = Path(__file__).resolve().parent / "e19_witness_restart_dropins"
SERVICE_DROPIN = f"{UNIT_DIR}/{WITNESS_SERVICE}.d/10-no-implicit-restart.conf"
SOCKET_DROPINS = {unit: f"{UNIT_DIR}/{unit}.d/10-no-reactivation.conf" for unit in (OWNER_SOCKET, SIGNER_SOCKET)}
WITNESS_DROPINS = {  # installed path -> reviewed candidate bytes SHA-256 (tests: = the files in DROPIN_SOURCE)
    SERVICE_DROPIN: "661a486dd05a95e0180e245e5e247d3da867c2f75b682e6a2daeb162ee70f3bb",
    SOCKET_DROPINS[OWNER_SOCKET]: "adef54692069b298387ea870d9b765aaa7601c51b94c9176bda7b9689c98fdf2",
    SOCKET_DROPINS[SIGNER_SOCKET]: "adef54692069b298387ea870d9b765aaa7601c51b94c9176bda7b9689c98fdf2",
}
# The EFFECTIVE configuration (`systemctl show`) plus the installed drop-in bytes, required exactly in every phase.
RESTART_BOUNDARY = {
    "units": {
        WITNESS_SERVICE: {"Restart": "no", "DropInPaths": SERVICE_DROPIN, "NeedDaemonReload": "no"},
        **{unit: {"StopWhenUnneeded": "yes", "RefuseManualStart": "yes", "DropInPaths": path,
                  "NeedDaemonReload": "no"} for unit, path in SOCKET_DROPINS.items()},
    },
    "dropIns": dict(WITNESS_DROPINS),
}
# The only reviewed commands. Stop: the service and both sockets in ONE transaction. Start: the service only; its
# `Requires=` pulls both sockets (a manual socket start is refused by the boundary).
STOP_COMMAND = f"/usr/bin/systemctl stop {WITNESS_SERVICE} {OWNER_SOCKET} {SIGNER_SOCKET}"
START_COMMAND = f"/usr/bin/systemctl start {WITNESS_SERVICE}"

# ------------------------------------------------------------ observation schema ---
FIELDS = frozenset({"observationType", "schemaVersion", "mode", "oldRelease", "newRelease", "bootId",
                    "journalCursor", "optEntries", "releaseEntries", "currentTarget", "treeVerified", "witness",
                    "signer", "preserved"})
WITNESS_FIELDS = frozenset({"service", "ownerSocket", "signerSocket", "cwd", "invocations", "health",
                            "restartBoundary"})
SERVICE_FIELDS = frozenset({"ActiveState", "SubState", "MainPID", "InvocationID", "NRestarts", "Result"})
SOCKET_FIELDS = frozenset({"ActiveState"})
INVOCATION_FIELDS = frozenset({"afterCursor", "ids"})
HEALTH_FIELDS = frozenset(HEALTH_EXACT)
SIGNER_FIELDS = frozenset({"ActiveState", "SubState", "MainPID", "InvocationID", "NRestarts", "UnitFileState",
                           "DropInPaths", "invocationsEver"})
SIGNER_DARK = {"ActiveState": "inactive", "SubState": "dead", "MainPID": "0", "InvocationID": "", "NRestarts": "0",
               "UnitFileState": "static", "DropInPaths": "", "invocationsEver": []}
OPT_EXACT = ["current", "releases"]
SELECTOR_RESIDUE = ".current.tmp"
# A systemd journal cursor. `b=` is the boot id; invocations are counted strictly after the baseline cursor.
_CURSOR = re.compile(r"s=([0-9a-f]{32});i=([0-9a-f]{1,16});b=([0-9a-f]{32});m=[0-9a-f]{1,16};t=[0-9a-f]{1,16};"
                     r"x=[0-9a-f]{1,16}\Z")

# ---------------------------------------------------------------------- phases ---
U0 = "U0_P1B10_EXACT"
U1 = "U1_NEW_STAGED_WITNESS_ON_OLD"
U2 = "U2_WITNESS_STOPPED_OLD_SELECTED"
U3 = "U3_NEW_SELECTED_WITNESS_STOPPED"
U4 = "U4_REPLACEMENT_RUNNING_ON_NEW"
U5 = "U5_OLD_RETIRED_REPLACEMENT_ACCEPTED"
EXACT_PHASES = (U0, U1, U2, U3, U4, U5)
TWO_RELEASE_PHASES = (U1, U2, U3, U4)        # the ONLY scope of the temporary staging exception
# While the witness is not proven RUNNING (same InvocationID before and after), nothing may contact a witness socket:
# the owner CLI `health` / `read` are never run (the `mb9_operator.health` WITNESS_NOT_RUNNING_NO_SOCKET_CONTACT rule).
NO_SOCKET_CONTACT_PHASES = (U2, U3)
# HALT: a PROVEN (observed, non-null) preserved custody fact or signer fact is not exact. Never continued here.
HALT_PRESERVED = "UH_PRESERVED_FACT_CHANGED"
HALT_SIGNER = "UH_SIGNER_NOT_DARK"
# STOP: owner adjudication; never repaired, retried or rolled back here.
UNKNOWN = "US_UNKNOWN"
STOP_BOOT = "US_BOOT_CHANGED"
STOP_JOURNAL = "US_INVOCATIONS_NOT_BOUND_TO_BASELINE"
STOP_BOUNDARY = "US_RESTART_BOUNDARY_NOT_EFFECTIVE"
STOP_STAGING = "US_STAGING_RESIDUE"
STOP_SELECTOR = "US_SELECTOR_RESIDUE"
STOP_RELEASE_SET = "US_RELEASE_SET_FOREIGN"
STOP_NEW_TREE = "US_NEW_TREE_INVALID"
STOP_OLD_TREE = "US_OLD_TREE_CHANGED"
STOP_RETIRE_PARTIAL = "US_RETIRE_PARTIAL"
STOP_MIXED = "US_WITNESS_RUNNING_ACROSS_SELECT"
STOP_DELETED = "US_WITNESS_ON_RETIRED_RELEASE"
STOP_WITNESS_TRANSITIONAL = "US_WITNESS_TRANSITIONAL"
STOP_SOCKET_CONTACT = "US_SOCKET_CONTACT_WHILE_STOPPED"
STOP_ORIGINAL_RESTARTED = "US_ENDING_INCARNATION_CHANGED"
STOP_LOADS = "US_KWIT_LOADS_NOT_EXACTLY_ONE"
STOP_START_FAILED = "US_REPLACEMENT_START_FAILED"
STOP_RESTARTED_ON_OLD = "US_REPLACEMENT_ON_OLD_RELEASE"
STOP_OUT_OF_ORDER = "US_OUT_OF_ORDER"
STOP_RETIRED_EARLY = "US_RETIRED_BEFORE_INCARNATION_ACCEPTED"
STOP_UNHEALTHY = "US_REPLACEMENT_NOT_CONSISTENT"
HALT_PHASES = (HALT_PRESERVED, HALT_SIGNER)
STOP_PHASES = (UNKNOWN, STOP_BOOT, STOP_JOURNAL, STOP_BOUNDARY, STOP_STAGING, STOP_SELECTOR, STOP_RELEASE_SET,
               STOP_NEW_TREE, STOP_OLD_TREE, STOP_RETIRE_PARTIAL, STOP_MIXED, STOP_DELETED,
               STOP_WITNESS_TRANSITIONAL, STOP_SOCKET_CONTACT, STOP_ORIGINAL_RESTARTED, STOP_LOADS, STOP_START_FAILED,
               STOP_RESTARTED_ON_OLD, STOP_OUT_OF_ORDER, STOP_RETIRED_EARLY, STOP_UNHEALTHY)

# Exact phase -> (the next proposed step, the separate owner act it needs). Routing authorizes NOTHING.
ROUTES = {
    U0: ("STAGE_NEW_RELEASE", "E19-GO-STAGE after the owner-accepted U0 baseline (installer stage NOT IMPLEMENTED)"),
    U1: ("STOP_WITNESS_SERVICE_AND_SOCKETS", "E19-GO-STOP: STOP_COMMAND, one transaction; ends incarnation "
                                             "8af12bd6…/1580 (separate authorization)"),
    U2: ("SELECT_NEW_RELEASE", "E19-GO-SELECT (atomic symlink + rename; witness stays stopped; no socket contact)"),
    U3: ("START_REPLACEMENT_WITNESS", "E19-GO-START: START_COMMAND once; exactly one K-WIT load (no socket contact "
                                      "before it)"),
    U4: ("POST9A_R_THEN_LOCAL_REPLACEMENT_ACCEPTANCE_THEN_RETIRE_OLD",
         "POST9A-R, then the owner's local digest-bound replacement acceptance, then E19-GO-RETIRE"),
    U5: ("FINAL_POST_AND_FIRST_DEPLOY_DR5_THEN_OWNER_COMPLETION",
         "E19 completion acceptance; the repository pin of the replacement belongs in that completion record"),
}
# Every non-exact class -> its safe STOP and recovery rule. No automatic rollback, cleanup, restart or K-WIT reload.
RECOVERY = {
    HALT_PRESERVED: "HALT. A custody, HELD, ledger, genesis, trust or broker fact moved. Freeze; owner forensics.",
    HALT_SIGNER: "HALT. The signer is not dark (a K-ACT load or activity). Freeze; owner forensics (M-B11 rules).",
    UNKNOWN: "STOP. Re-observe read-only; an unobserved fact is never success and never a proven change.",
    STOP_BOOT: "STOP. A reboot ended the incarnation and the sockets; re-baseline under owner adjudication.",
    STOP_JOURNAL: "STOP. The invocation count is not bound to the accepted U0 journal cursor; re-observe read-only.",
    STOP_BOUNDARY: "STOP. The witness restart boundary is not exactly effective; no stop, select or start may run. "
                   "Installing or repairing it is a separate owner-authorized step.",
    STOP_STAGING: "STOP. Interrupted stage: witness and current untouched; residue removal is one separate owner act.",
    STOP_SELECTOR: "STOP. Interrupted select: current is still one exact target (rename is atomic); witness stays "
                   "stopped; residue removal is one separate owner act.",
    STOP_RELEASE_SET: "STOP. A release set or selector this contract cannot produce; owner forensics.",
    STOP_NEW_TREE: "STOP. The NEW tree does not verify; it is never selected or started; owner adjudication.",
    STOP_OLD_TREE: "STOP. The OLD tree changed before an accepted retirement; owner forensics.",
    STOP_RETIRE_PARTIAL: "STOP. Interrupted retire: the accepted replacement runs from NEW only; completing the "
                         "removal is one separate owner act.",
    STOP_MIXED: "STOP. The ending incarnation runs while current -> NEW (lazy imports could load NEW bytes). Never "
                "an endpoint; the only exit is the separately authorized STOP_COMMAND.",
    STOP_DELETED: "STOP. A witness runs from a retired tree. Never an endpoint; owner adjudication.",
    STOP_WITNESS_TRANSITIONAL: "STOP. Activating, deactivating, failed, restarted, or sockets not matching the "
                               "service. No socket contact, no retry; owner adjudication.",
    STOP_SOCKET_CONTACT: "STOP. A witness socket was contacted (health / read) while the witness was not running; "
                         "the contact may have started it. Owner forensics over the journal.",
    STOP_ORIGINAL_RESTARTED: "STOP. The ending incarnation restarted or changed identity outside this contract.",
    STOP_LOADS: "STOP. The journal shows a number of witness invocations (K-WIT loads) other than exactly one.",
    STOP_START_FAILED: "STOP. A start attempt loaded K-WIT and the witness is not running. No retry without a new "
                       "owner go; every attempt is a counted load.",
    STOP_RESTARTED_ON_OLD: "STOP. A replacement incarnation runs from OLD. Not this contract; owner adjudication.",
    STOP_OUT_OF_ORDER: "STOP. A step ran out of the U0..U5 order; owner adjudication (no reverse path exists).",
    STOP_RETIRED_EARLY: "STOP. OLD retired before the replacement incarnation's verified local acceptance.",
    STOP_UNHEALTHY: "STOP. The replacement does not report CONSISTENT health with the custodied K-WIT.",
}
assert set(RECOVERY) == set(HALT_PHASES) | set(STOP_PHASES) and set(ROUTES) == set(EXACT_PHASES)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def document_sha256(document: Any) -> str:
    """The digest an acceptance binds: SHA-256 of the canonical JSON of the document."""
    return _sha(_canonical(document))


def _exact(value: Any, fields: frozenset[str], name: str) -> Mapping[str, Any]:
    _need(isinstance(value, Mapping) and set(value) == fields, "OBSERVATION_FIELDS", name)
    return value


def _maybe(value: Any, fields: frozenset[str], name: str) -> None:
    """A container may be null (unobserved); when present its field set is closed."""
    if value is not None:
        _exact(value, fields, name)


def parse_observation(document: Any, *, new_release: str) -> Mapping[str, Any]:
    """The closed schema. `None` is the only spelling of an unobserved value (-> UNKNOWN), never a default."""
    doc = _exact(document, FIELDS, "observation")
    _need(doc["observationType"] == OBSERVATION_TYPE and doc["schemaVersion"] == 1 and doc["mode"] == MODE,
          "OBSERVATION_TYPE")
    _need(doc["oldRelease"] == OLD_RELEASE and doc["newRelease"] == new_release, "OBSERVATION_RELEASES")
    witness = _exact(doc["witness"], WITNESS_FIELDS, "witness")
    _maybe(witness["service"], SERVICE_FIELDS, "service")
    _maybe(witness["ownerSocket"], SOCKET_FIELDS, "ownerSocket")
    _maybe(witness["signerSocket"], SOCKET_FIELDS, "signerSocket")
    _maybe(witness["invocations"], INVOCATION_FIELDS, "invocations")
    _maybe(witness["health"], HEALTH_FIELDS, "health")
    _maybe(witness["restartBoundary"], frozenset(RESTART_BOUNDARY), "restartBoundary")
    if witness["invocations"] is not None and witness["invocations"]["ids"] is not None:
        ids = witness["invocations"]["ids"]
        _need(isinstance(ids, list) and all(isinstance(x, str) and _HEX32.fullmatch(x) for x in ids),
              "OBSERVATION_FIELDS", "invocations.ids")
    _maybe(doc["signer"], SIGNER_FIELDS, "signer")
    _maybe(doc["preserved"], PRESERVED_FIELDS, "preserved")
    for name in ("optEntries", "releaseEntries"):
        _need(doc[name] is None or (isinstance(doc[name], list) and all(isinstance(x, str) for x in doc[name])),
              "OBSERVATION_FIELDS", name)
    _need(doc["treeVerified"] is None or (isinstance(doc["treeVerified"], Mapping) and all(
        _SHA40.fullmatch(k) and (v is None or type(v) is bool) for k, v in doc["treeVerified"].items())),
        "OBSERVATION_FIELDS", "treeVerified")
    return doc


def _nulls(value: Any, path: str) -> list[str]:
    if value is None:
        return [path]
    if isinstance(value, Mapping):
        return [p for key in sorted(value) for p in _nulls(value[key], f"{path}.{key}" if path else key)]
    if isinstance(value, list):
        return [p for i, item in enumerate(value) for p in _nulls(item, f"{path}[{i}]")]
    return []


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


def _cursor(value: str) -> tuple[str, int, str] | None:
    match = _CURSOR.fullmatch(value) if isinstance(value, str) else None
    return None if match is None else (match.group(1), int(match.group(2), 16), match.group(3))


def _verdict(phase: str, reasons: list[str]) -> dict[str, Any]:
    exact = phase in EXACT_PHASES
    return {"mode": MODE, "status": STATUS, "phase": phase, "reasons": list(reasons),
            "twoReleaseException": phase in TWO_RELEASE_PHASES,
            "next": ROUTES[phase][0] if exact else "STOP", "ownerAct": ROUTES[phase][1] if exact else None,
            "recovery": None if exact else RECOVERY[phase], "packageReadyAdmissible": False,
            "authorizes": "NOTHING"}


def _judge(doc: Mapping[str, Any], base: Mapping[str, Any] | None, accepted: tuple[str, str] | None,
           new_release: str) -> dict[str, Any]:
    """The judgement of a PARSED observation against an already VERIFIED baseline (or none: the U0 candidate) and an
    already VERIFIED replacement acceptance identity. Internal: callers go through `classify`."""
    reasons: list[str] = []

    def result(phase: str, *more: str) -> dict[str, Any]:
        return _verdict(phase, reasons + list(more))

    # ---- HALT on PROVEN facts only (an unobserved value is UNKNOWN, never a change)
    preserved = doc["preserved"]
    if preserved is not None:
        moved = sorted(name for name, pin in PRESERVED_PINS.items()
                       if preserved[name] is not None and not _nulls(preserved[name], "")
                       and preserved[name] != pin)
        if base is not None:
            moved += sorted(name for name in PRESERVED_HOST_FACTS
                            if preserved[name] is not None and not _nulls(preserved[name], "")
                            and _canonical(preserved[name]) != _canonical(base["preserved"][name]))
        if moved:
            return result(HALT_PRESERVED, *("PRESERVED:" + name for name in moved))
    signer = doc["signer"]
    if signer is not None and any(signer[k] is not None and not _nulls(signer[k], "") and signer[k] != v
                                  for k, v in SIGNER_DARK.items()):
        return result(HALT_SIGNER)

    # ---- UNKNOWN: every null, except the two slots a witness that is not running has no value for
    witness = doc["witness"]
    parts = (witness["service"], witness["ownerSocket"], witness["signerSocket"])
    state = _service_state(witness) if all(p is not None and not _nulls(p, "") for p in parts) else None
    missing = _nulls(doc, "")
    if state in ("STOPPED", "TRANSITIONAL"):
        missing = [p for p in missing if p not in ("witness.cwd", "witness.health")]
    if missing:
        return result(UNKNOWN, *("UNOBSERVED:" + p for p in missing))
    if doc["bootId"] != BOOT_ID:
        return result(STOP_BOOT)

    # ---- the journal: invocations counted strictly after the accepted U0 cursor, on this boot
    cursor, invocations = _cursor(doc["journalCursor"]), witness["invocations"]
    anchor = doc["journalCursor"] if base is None else base["journalCursor"]
    anchored = _cursor(anchor)
    if cursor is None or anchored is None or cursor[2] != BOOT_ID.replace("-", "") \
            or invocations["afterCursor"] != anchor or cursor[0] != anchored[0] or cursor[1] < anchored[1]:
        return result(STOP_JOURNAL)
    # A K-WIT load is a DISTINCT, NEWLY STARTED invocation. `journalctl -u … --after-cursor` also returns the running
    # ending incarnation's own log lines and its stop entries, all with its InvocationID (real systemd 255, PR #190
    # probe): they are never a load, and repeated entries of one invocation are one id (the observer deduplicates; a
    # document that repeats an id is malformed).
    ids = invocations["ids"]
    _need(len(ids) == len(set(ids)), "OBSERVATION_FIELDS", "invocations.ids")
    loads = [i for i in ids if i != ENDING_INCARNATION[0]]

    # ---- the restart boundary: a prerequisite in every phase
    if _canonical(witness["restartBoundary"]) != _canonical(RESTART_BOUNDARY):
        return result(STOP_BOUNDARY)

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
    if sorted(doc["optEntries"]) != OPT_EXACT or not isinstance(target, str) \
            or target not in (f"releases/{old}", f"releases/{new}") or target.split("/", 1)[1] not in shas:
        return result(STOP_RELEASE_SET, f"SELECTOR:{target}")
    _need(set(doc["treeVerified"]) == shas, "OBSERVATION_FIELDS", "treeVerified")
    if new in shas and not doc["treeVerified"][new]:
        return result(STOP_NEW_TREE)

    # ---- the witness
    service = witness["service"]
    cwd = witness["cwd"]
    if state == "STOPPED" and witness["health"] is not None:
        return result(STOP_SOCKET_CONTACT)
    if state == "RUNNING" and cwd not in tuple(f"{OPT}/releases/{sha}" for sha in shas):
        return result(STOP_DELETED, f"CWD:{cwd}")
    if old in shas and not doc["treeVerified"][old]:
        running_new = state == "RUNNING" and cwd == f"{OPT}/releases/{new}" and target == f"releases/{new}"
        accepted_here = accepted is not None and (service["InvocationID"], service["MainPID"]) == accepted
        return result(STOP_RETIRE_PARTIAL if running_new and accepted_here else STOP_OLD_TREE)
    if state == "TRANSITIONAL":
        return result(STOP_WITNESS_TRANSITIONAL, f"SERVICE:{service['ActiveState']}/{service['SubState']}")
    if base is None:
        _need(shas == frozenset({old}) and state == "RUNNING" and loads == [], "BASELINE_REQUIRED")

    identity = (service["InvocationID"], service["MainPID"])
    healthy = dict(witness["health"] or {}) == HEALTH_EXACT
    if state == "RUNNING" and service["InvocationID"] == ENDING_INCARNATION[0]:
        if identity != ENDING_INCARNATION or loads:
            return result(STOP_ORIGINAL_RESTARTED)
        if target == f"releases/{new}":
            return result(STOP_MIXED)
        if cwd != f"{OPT}/releases/{old}":
            return result(STOP_ORIGINAL_RESTARTED, f"CWD:{cwd}")
        if not healthy:
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
    if not healthy:
        return result(STOP_UNHEALTHY)
    if shas == frozenset({old, new}):
        return result(U4)
    if accepted != identity:
        return result(STOP_RETIRED_EARLY)
    return result(U5)


# ----------------------------------------------------- local owner acceptances (R1, R2) ---
# The B3 / D3 pattern: the tool renders the ONE canonical statement (LF, ASCII) from evidence it verifies itself;
# the owner issues it verbatim; the local record binds the subject digest and the statement digest. Every use
# re-verifies subject, statement and record: a caller-made record, a reworded statement or a substituted subject
# is refused. Nothing here is a repository pin: the replacement is pinned only by the post-U5 completion record.
U0_RECORD_TYPE = "LILITH_E19_U0_BASELINE_ACCEPTANCE"
REPLACEMENT_RECORD_TYPE = "LILITH_E19_REPLACEMENT_INCARNATION_ACCEPTANCE"
RECORD_FIELDS = frozenset({"recordType", "schemaVersion", "mode", "newRelease", "subjectSha256", "statementSha256",
                           "invocationId", "mainPid", "journalCursor"})
BUNDLE_FIELDS = {U0_RECORD_TYPE: frozenset({"observation", "statement", "record"}),
                 REPLACEMENT_RECORD_TYPE: frozenset({"evidence", "statement", "record"})}
U0_LINES = (
    "I accept this exact U0 baseline for UPGRADE_FROM_P1B10_DEV_SYNTHETIC (E-19 release maintenance, DEV_SYNTHETIC).",
    "U0 observation SHA-256: {subject}.",
    "Installed release {old}, current releases/{old}; proposed NEW release {new}.",
    "Ending witness incarnation: InvocationID {invocation}, MainPID {mainpid}, NRestarts 0.",
    "Journal cursor (invocations are counted after it): {cursor}.",
    "Witness restart boundary effective: {boundary}.",
    "This acceptance authorizes nothing further: not staging, not the witness stop, not a K-WIT load, not a release "
    "switch or retirement, not the signer, not authority.",
)
REPLACEMENT_LINES = (
    "I accept the replacement witness incarnation for UPGRADE_FROM_P1B10_DEV_SYNTHETIC (POST9A-R, DEV_SYNTHETIC).",
    "POST9A-R evidence SHA-256: {subject}. U0 baseline statement SHA-256: {baseline}.",
    "Replacement: InvocationID {invocation}, MainPID {mainpid}, NRestarts 0, from releases/{new}; exactly one "
    "K-WIT load after journal cursor {cursor}.",
    "W10 {w10} (verifier output {w10out}); health CONSISTENT, K-WIT " + KWIT_PUBLIC_KEY_SHA256 + ".",
    "The ending incarnation " + ENDING_INCARNATION[0] + " / " + ENDING_INCARNATION[1] + " is historical.",
    "This acceptance authorizes nothing further: not the retirement of releases/{old} (a separate go), not package "
    "READY, not the signer, not authority.",
)


def _statement(lines: tuple[str, ...], **values: str) -> bytes:
    return ("\n".join(line.format(**values) for line in lines) + "\n").encode("ascii")


def _statement_bytes(value: Any) -> bytes:
    if isinstance(value, str):
        _need(value.isascii(), "STATEMENT_NOT_CANONICAL")
        value = value.encode("ascii")
    _need(isinstance(value, bytes), "STATEMENT_NOT_CANONICAL")
    return value


def render_u0_statement(observation: Any, *, new_release: str | None = NEW_RELEASE) -> bytes:
    """The canonical U0 acceptance statement. Refused unless the observation, judged ALONE, is exactly U0."""
    _need(isinstance(new_release, str) and _SHA40.fullmatch(new_release) is not None and new_release != OLD_RELEASE,
          "NEW_RELEASE_NOT_ESTABLISHED")
    doc = parse_observation(observation, new_release=new_release)
    try:
        verdict = _judge(doc, None, None, new_release)
    except Refused as exc:
        raise Refused("BASELINE_NOT_U0", exc.reason) from exc
    _need(verdict["phase"] == U0, "BASELINE_NOT_U0", verdict["phase"])
    return _statement(U0_LINES, subject=document_sha256(doc), old=OLD_RELEASE, new=new_release,
                      invocation=ENDING_INCARNATION[0], mainpid=ENDING_INCARNATION[1], cursor=doc["journalCursor"],
                      boundary=document_sha256(RESTART_BOUNDARY))


def acceptance_record(record_type: str, subject: Any, statement: bytes, *, new_release: str,
                      invocation: tuple[str, str], cursor: str) -> dict[str, Any]:
    """The local record the operator writes after the owner issues the statement verbatim (pure)."""
    return {"recordType": record_type, "schemaVersion": 1, "mode": MODE, "newRelease": new_release,
            "subjectSha256": document_sha256(subject), "statementSha256": _sha(statement),
            "invocationId": invocation[0], "mainPid": invocation[1], "journalCursor": cursor}


def _verify_bundle(bundle: Any, record_type: str, subject_key: str, expected_statement: bytes,
                   expected_record: Mapping[str, Any]) -> None:
    item = bundle if isinstance(bundle, Mapping) else None
    _need(item is not None and set(item) == BUNDLE_FIELDS[record_type], "ACCEPTANCE_FIELDS", record_type)
    _need(_statement_bytes(item["statement"]) == expected_statement, "STATEMENT_NOT_CANONICAL", record_type)
    record = item["record"]
    _need(isinstance(record, Mapping) and set(record) == RECORD_FIELDS, "ACCEPTANCE_RECORD_FIELDS", record_type)
    _need(_canonical(record) == _canonical(expected_record), "ACCEPTANCE_RECORD_MISMATCH", record_type)


def trusted_baseline(acceptance: Any, *, new_release: str | None = NEW_RELEASE) -> Mapping[str, Any]:
    """R1. The owner-accepted U0 baseline, re-verified on every use: the observation judged ALONE is exact U0 (a
    substituted U3 or any other observation is refused even when later preserved facts match it), the statement is
    byte-exactly the canonical U0 statement for it, and the record binds both digests."""
    _need(isinstance(acceptance, Mapping) and set(acceptance) == BUNDLE_FIELDS[U0_RECORD_TYPE],
          "ACCEPTANCE_FIELDS", U0_RECORD_TYPE)
    statement = render_u0_statement(acceptance["observation"], new_release=new_release)
    doc = parse_observation(acceptance["observation"], new_release=new_release)
    _verify_bundle(acceptance, U0_RECORD_TYPE, "observation", statement, acceptance_record(
        U0_RECORD_TYPE, doc, statement, new_release=new_release, invocation=ENDING_INCARNATION,
        cursor=doc["journalCursor"]))
    return doc


# --------------------------------------------------------------------- POST9A-R (R3) ---
# POST9A-R is the REPLACEMENT-WITNESS acceptance evidence at U4, judged under the exact U4 TWO-release contract.
# It is NOT PR-1 package readiness: installer `status --expect P1B-10` (RELEASE_SET), judge E-01 and package READY
# cannot pass while two releases are installed and are deliberately not required. Package READY stays U5-only.
POST9A_R_TYPE = "LILITH_E19_POST9A_R_EVIDENCE"
POST9A_R_FIELDS = frozenset({"evidenceType", "schemaVersion", "mode", "baselineSubjectSha256", "observation",
                             "w9PhaseDirect", "w9PhaseSeamed", "w10Phase", "w10OutputSha256", "healthCapture",
                             "denials"})
HEALTH_CAPTURE_FIELDS = frozenset({"before", "after", "health"})
IDENTITY_FIELDS = frozenset({"InvocationID", "MainPID"})
POST9A_R_PHASES = {"w9PhaseDirect": "W9_LATER_STATE", "w9PhaseSeamed": "W9_5_GENESIS_COMMITTED_EXACT",
                   "w10Phase": "W10_1_HELD_EXACT"}
# The reviewed read-only denial proofs (POST10 precedent): witness custody, hold store, signer custody.
POST9A_R_DENIALS = {"P1B-9b": "PASS", "P1B-10": "PASS", "P1B-5": "PASS"}
POST9A_R_NOT_REQUIRED = ("INSTALLER_STATUS_P1B10_RELEASE_SET", "E01_INSTALLED_RELEASE", "PR1_PACKAGE_READY")


def post9a_r(evidence: Any, baseline: Any, *, new_release: str | None = NEW_RELEASE) -> dict[str, Any]:
    """R3. VERIFIED only when: the observation is exactly U4 under the owner-accepted baseline (two releases
    {OLD, NEW}, current -> NEW, the replacement running from NEW, exactly one invocation after the U0 cursor,
    NRestarts 0, the restart boundary effective, every preserved fact exact); W9 direct = W9_LATER_STATE and seamed =
    W9_5 (the W9 code reads HELD as a later state, as at M-B10), W10 = W10_1_HELD_EXACT; the health capture is
    CONSISTENT with the custodied K-WIT and bound to the same InvocationID / MainPID before and after it; and the
    three denial proofs PASS."""
    base = trusted_baseline(baseline, new_release=new_release)
    item = _exact(evidence, POST9A_R_FIELDS, "post9aR")
    _need(item["evidenceType"] == POST9A_R_TYPE and item["schemaVersion"] == 1 and item["mode"] == MODE,
          "POST9A_R_TYPE")
    doc = parse_observation(item["observation"], new_release=new_release)
    reasons = []
    if item["baselineSubjectSha256"] != document_sha256(base):
        reasons.append("BASELINE_NOT_BOUND")
    phase = _judge(doc, base, None, new_release)["phase"]
    if phase != U4:
        reasons.append("OBSERVATION_NOT_U4:" + phase)
    reasons += [f"{name}:{item[name]}" for name, expected in POST9A_R_PHASES.items() if item[name] != expected]
    if not (isinstance(item["w10OutputSha256"], str) and _HEX64.fullmatch(item["w10OutputSha256"])):
        reasons.append("W10_OUTPUT_DIGEST")
    capture = item["healthCapture"]
    service = doc["witness"]["service"] or {}
    identity = {"InvocationID": service.get("InvocationID"), "MainPID": service.get("MainPID")}
    if not (isinstance(capture, Mapping) and set(capture) == HEALTH_CAPTURE_FIELDS
            and capture["before"] == identity and capture["after"] == identity
            and capture["health"] == HEALTH_EXACT and doc["witness"]["health"] == HEALTH_EXACT):
        reasons.append("HEALTH_NOT_BOUND_OR_NOT_CONSISTENT")
    if item["denials"] != POST9A_R_DENIALS:
        reasons.append("DENIAL_PROOFS")
    return {"result": "POST9A_R_NOT_VERIFIED" if reasons else "POST9A_R_VERIFIED", "reasons": reasons,
            "invocationId": identity["InvocationID"], "mainPid": identity["MainPID"],
            "evidenceSha256": document_sha256(item), "notRequired": list(POST9A_R_NOT_REQUIRED),
            "authorizes": "NOTHING"}


def render_replacement_statement(evidence: Any, baseline: Any, *, new_release: str | None = NEW_RELEASE) -> bytes:
    """The canonical replacement acceptance statement. Refused unless POST9A-R is VERIFIED."""
    report = post9a_r(evidence, baseline, new_release=new_release)
    _need(report["result"] == "POST9A_R_VERIFIED", "POST9A_R_NOT_VERIFIED", ",".join(report["reasons"]))
    base = trusted_baseline(baseline, new_release=new_release)
    return _statement(REPLACEMENT_LINES, subject=report["evidenceSha256"],
                      baseline=_sha(_statement_bytes(baseline["statement"])), invocation=report["invocationId"],
                      mainpid=report["mainPid"], new=new_release, old=OLD_RELEASE, cursor=base["journalCursor"],
                      w10=evidence["w10Phase"], w10out=evidence["w10OutputSha256"])


def trusted_replacement(acceptance: Any, baseline: Any, *, new_release: str | None = NEW_RELEASE) -> tuple[str, str]:
    """R2. The replacement identity, only from a verified local acceptance: POST9A-R VERIFIED over the evidence,
    the statement byte-exactly canonical for it, and the record binding both digests and the identity."""
    _need(isinstance(acceptance, Mapping) and set(acceptance) == BUNDLE_FIELDS[REPLACEMENT_RECORD_TYPE],
          "ACCEPTANCE_FIELDS", REPLACEMENT_RECORD_TYPE)
    statement = render_replacement_statement(acceptance["evidence"], baseline, new_release=new_release)
    report = post9a_r(acceptance["evidence"], baseline, new_release=new_release)
    base = trusted_baseline(baseline, new_release=new_release)
    _verify_bundle(acceptance, REPLACEMENT_RECORD_TYPE, "evidence", statement, acceptance_record(
        REPLACEMENT_RECORD_TYPE, acceptance["evidence"], statement, new_release=new_release,
        invocation=(report["invocationId"], report["mainPid"]), cursor=base["journalCursor"]))
    return report["invocationId"], report["mainPid"]


def classify(document: Any, baseline: Any = None, replacement: Any = None, *,
             new_release: str | None = NEW_RELEASE) -> dict[str, Any]:
    """One judgement. `baseline` is the owner-accepted U0 bundle (R1); without it only the U0 candidate can be
    judged. `replacement` is the verified local replacement acceptance (R2), required for U5. Precedence: HALT on
    proven facts, then UNKNOWN, then STOP classes, then the exact phases."""
    _need(isinstance(new_release, str) and _SHA40.fullmatch(new_release) is not None and new_release != OLD_RELEASE,
          "NEW_RELEASE_NOT_ESTABLISHED")
    doc = parse_observation(document, new_release=new_release)
    base = None if baseline is None else trusted_baseline(baseline, new_release=new_release)
    _need(replacement is None or base is not None, "BASELINE_REQUIRED")
    accepted = None if replacement is None else trusted_replacement(replacement, baseline, new_release=new_release)
    return _judge(doc, base, accepted, new_release)


def package_ready_admissible(document: Any, baseline: Any = None, replacement: Any = None, *, release_sha: str,
                             new_release: str | None = NEW_RELEASE) -> tuple[bool, str]:
    """The M-B12 package READY gate across this transition. It classifies the observation ITSELF (never a caller's
    verdict). READY is never admissible while two releases are installed (the judge's own E-01 also refuses:
    `release_entries == [release_sha]`), never on aee323e (its E-19 cannot pass on the real host line), and never on
    a HALT / STOP / UNKNOWN or before the replacement's verified acceptance (U5)."""
    try:
        phase = classify(document, baseline, replacement, new_release=new_release)["phase"]
    except Refused as exc:
        return False, "REFUSED:" + exc.reason
    if phase in TWO_RELEASE_PHASES:
        return False, "TWO_RELEASE_INTERMEDIATE"
    if phase not in EXACT_PHASES:
        return False, "NOT_EXACT:" + phase
    if phase == U0 or release_sha == OLD_RELEASE:
        return False, "INSTALLED_RELEASE_E19_DEFECT"
    if release_sha != new_release:
        return False, "RELEASE_NOT_THE_NEW_RELEASE"
    return True, "U5_SINGLE_NEW_RELEASE"


# ------------------------------------------------------------- DR-5 release delta ---
# The routine DR-5 script (`scripts/deployer_authority_boundary_proof.sh`) prints the release directory twice: once
# for the `releases/` listing and once for the `current` target. No other line names a release. Record §6.
DR5_RELEASE_LINE = "DENIED: test -w /opt/lilith-authority-dev/releases/{sha}"
DR5_RELEASE_LINE_COUNTS = {"result-set": 2, "dr5-block": 2, "predeploy-block": 0}
# The replaced post-upgrade targets: `derive_release_swap(<OLD>, <NEW_RELEASE>)` over the accepted W10_1 texts
# (`mb10_dr5_target.derive`, which itself re-checks the W10 pins), as (lines, SHA-256) per set. Tests re-derive them.
# DERIVED and PINNED, NOT ACCEPTED and NOT EFFECTIVE: they apply only after U5 (the first post-U5 deploy), and only
# the owner accepts them. Until then the routine deploy compares against the unchanged aee323e W10_1 targets.
NEW_DR5_TARGETS_STATUS = "DERIVED_PINNED_NOT_ACCEPTED"
NEW_DR5_SOURCES = {"WITNESS_RUNNING_HELD_E19": "WITNESS_RUNNING_HELD",
                   "WITNESS_STATE_PRESENT_SERVICE_STOPPED_HELD_E19": "WITNESS_STATE_PRESENT_SERVICE_STOPPED_HELD"}
NEW_DR5_TARGETS: Mapping[str, Any] = {
    "WITNESS_RUNNING_HELD_E19": {
        "result-set": (192, "91c91ec7d5001d8c13f8438cb3d653ea3ee9b6bc1e41087ec154fec834def13d"),
        "dr5-block": (153, "0692dc6df9dfbba2e6d81d985d56090025c11d2756a6397966346bb5f9e5fd16"),
        "predeploy-block": (29, "f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae"),
    },
    "WITNESS_STATE_PRESENT_SERVICE_STOPPED_HELD_E19": {
        "result-set": (190, "a3d07a4342296dfdf424bc2f6f74e9add141e373d2822420ff15768abb74dc9e"),
        "dr5-block": (151, "8d25c6766b61b23517db870d5ddb5887af0e3b8fefe9b2011ced3de09ce2452f"),
        "predeploy-block": (29, "f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae"),
    },
}


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
# Files with a CURRENT aee323e binding that the upgrade invalidates (record §7). They describe the INSTALLED
# release, so they stay on aee323e while it is installed (pinning NEW here before the select would make the live
# host read as NEW); they are re-pinned with the post-U5 completion record.
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
        if len(argv) in (2, 3, 4) and argv[0] == "classify":
            docs = [_read_json(path) for path in argv[1:]] + [None] * (4 - len(argv))
            verdict = classify(docs[0], docs[1], docs[2])
            sys.stdout.write(json.dumps(verdict, sort_keys=True) + "\n")
            return 0 if verdict["phase"] in EXACT_PHASES else 2
        sys.stderr.write("usage: e19_p1b10_upgrade.py classify <observation.json> [<u0-acceptance.json> "
                         "[<replacement-acceptance.json>]]\n")
        return 64
    except (Refused, OSError, ValueError) as exc:
        sys.stderr.write(f"e19_p1b10_upgrade: REFUSED {exc}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
