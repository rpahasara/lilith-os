#!/usr/bin/env python3
"""15B2b-B1b-3e Package C (record 1 on Replica A and B + acceptance envelope 1 on copies A and B): the reviewed
owner-laptop binding and sequencing operator.

Record: docs/architecture/slice-15b2b-b1b3e-pkgc-record1-envelope-package.md.
DESIGN / SOURCE ONLY: no form below is authorized by this repository. Each live use needs its own explicit owner
act (C1, C2, C3, C4A, C4B, C5; record §6); the four owner-record acts (C2, C3, C4A, C4B) each need a separate go.

Why it exists (record §3, §5). The canonical `owner_freshness_tool` is unchanged and remains the ONLY writer of
owner records and envelopes. It needs, on one machine, (a) a trust-input document and a chain-export array in its
own format, and (b) both copies (target and peer). Package C has neither: the host exports `chain/1.json` bytes and
the owner holds the accepted installables; Replica A is on the laptop and Replica B on the S25. This operator adds
only the deterministic glue:

| Form | Effect |
| --- | --- |
| `pins <repo>` | local, read-only: clean checkout; control = `HEAD`; every pinned tool exact |
| `open <repo> <workdir> <statement> <facts.json>` | local: the owner's verbatim C1 in a NEW work directory; a fresh sequence id |
| `acquire <repo> <workdir> <mb9-workdir>` | ONE fresh read of the presented DEV world through the pinned read-only `mb9_operator.py` forms `host … POST9B` and `chain-export`, with a per-read acquisition receipt (record §3.1) |
| `bind <workdir> <installables-dir> <pin-dir> <export> <replica-a> <pr2-sha256> <p33-sha256>` | local, read-only over owner-held inputs and ONE verified acquisition: writes the NEW `<workdir>/binding/` |
| `gate <workdir> <stage> <export> <facts.json>` | local: the continuity gate before C2 / C3 / C4A / C4B / C5 over a NEW, never-consumed acquisition |
| `peer-view <workdir> <kind> [<source>]` | local: one read-only, provenance-bound, NON-CUSTODY peer view at `<workdir>/views/<kind>` (record §5) |
| `transfer <workdir> <replica-a\\|store-a> <paths.json> <out>` / `s25-bundle <repo> <workdir> <vendor> <out>` | deterministic transfer tars (record §8.2) |
| `s25-expect` / `s25-check <workdir> <stage> <paths.json> [<transcription>]` | the exact S25 result lines and their comparison (`OWNER_SCREEN_TRANSCRIPTION`) |
| `c4b-eligibility <workdir> <paths.json>` | local: the fresh read proving exactly `ACCEPTANCE_PARTIAL`, copy A exact, copy B absent |
| `arm <workdir> <C2\\|C3\\|C4A\\|C4B> <go> <paths.json>` | local: the go against its template and the last exact gate; the one-attempt marker; **writes no owner record** |
| `record <workdir> <C5\\|STOP> <statement> <paths.json>` | local: the owner's verbatim Package C acceptance or pre-C2 stop |

    binding != record 1;  record 1 on A != freshness CURRENT;  CURRENT != acceptance evidence
    a fresh acquisition is a receipt-bound read, never "a new directory"; a peer view is never custody
    envelope complete != HELD != signer != Registry V1 effective != authority active != First Memory

It never writes a replica, an acceptance store, HELD, a ledger or witness object. Its only DEV contact is
`acquire`, which runs the two pinned read-only `mb9_operator.py` forms named above and nothing else. It never
contacts the S25, holds or loads a key, and has no HELD, signer, activation, ledger, head-advance, epoch-advance or
First Memory form.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _path in (ROOT / "services/core-api", ROOT / "services/owner-memory-control"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from lilith_owner_memory import owner_acceptance as OA  # noqa: E402
from lilith_owner_memory import owner_freshness as OF  # noqa: E402
from lilith_owner_memory import owner_freshness_tool as T  # noqa: E402
from lilith_owner_memory import witness_readiness as WR  # noqa: E402

RESULT_TYPE = "LILITH_PKGC_OPERATOR"
CONTINUITY = ("PACKAGE_C_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_"
              "FOUR_OWNER_RECORD_BOUNDARIES")
OPERATOR = "services/owner-memory-control/tools/pkgc_operator.py"
FRESHNESS_TOOL = "services/owner-memory-control/lilith_owner_memory/owner_freshness_tool.py"
MB9_OPERATOR = "services/owner-memory-control/tools/mb9_operator.py"
W9_VERIFIER = "services/owner-memory-control/tools/mb9_witness_verifier.py"
OWNER_VERIFY = "services/owner-memory-control/tools/mb9_owner_genesis_verify.py"
# The canonical owner-record tool and the pinned Package B read-only tools Package C relies on. Unchanged here.
TOOL_PINS = {
    FRESHNESS_TOOL: "fd7abe2aa5e5efae41b87553efe8fe8058b437748accf866c2fa5ee71c8a7c27",
    MB9_OPERATOR: "066fc8213b40c392e3e2bfd609da4a7f2a4e0b6f05da011daee9add3caf13973",
    W9_VERIFIER: "e4aca11dcc925e8ebdb280c2d4a7da1cf4f9a8fcc4e2abb080e22d6917080e78",
    OWNER_VERIFY: "30b66fd2be9f29e820041840a75dc87f7623eff44551c025a0141790e7c89a5a",
}

_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
W9_5 = "W9_5_GENESIS_COMMITTED_EXACT"
STAGES = ("C2", "C3", "C4A", "C4B", "C5")
ARMABLE = ("C2", "C3", "C4A", "C4B")
# The accepted P3-5 bootstrap step each owner-record act performs (step 10, 11, 11a, 11b).
BOOTSTRAP_STEP = {"C2": "APPEND_RECORD_1_REPLICA_A", "C3": "APPEND_RECORD_1_REPLICA_B",
                  "C4A": "APPEND_ENVELOPE_1_COPY_A", "C4B": "APPEND_ENVELOPE_1_COPY_B"}


class Stop(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _need(condition: bool, reason: str) -> None:
    if not condition:
        raise Stop(reason)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(bytes(data)).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------- pins ---

@dataclass(frozen=True)
class PackageCPinsV1:
    """The owner-accepted identities Package C binds (Package A / B completion records). TEST seam: `pins=`."""
    environment: str
    authority_profile: str
    registry_sha256: str
    root_anchor_sha256: str
    witness_anchor_sha256: str
    genesis_digest: str
    chain_1_sha256: str
    pin_sha256: str
    register_sha256: str
    pin_record_sha256: str
    replica_a_id: str
    replica_b_id: str
    replica_b_manifest_sha256: str
    witness_invocation_id: str
    witness_main_pid: str


ACCEPTED_PINS = PackageCPinsV1(
    environment="dev", authority_profile="DEV_SYNTHETIC",
    registry_sha256="46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e",
    root_anchor_sha256="bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687",
    witness_anchor_sha256="be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a",
    genesis_digest="ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4",
    chain_1_sha256="252c32204bebf3fa1ca0981d8791115e2abb6cd8ddb0925285c64213317cfb99",
    pin_sha256="357477369ab53790245b42cbecbe2a630110477bede5b599696699e4f5c3a590",
    register_sha256="8d5ab87564d0e531b7d1467c18b6d106f2a468d5d155ce9f2acb64758df85575",
    pin_record_sha256="009a0596ca1d7f2f8d941c949c0671f2091b83668aa9315486dbc7f2a0f1e0ae",
    replica_a_id="owner-primary-dev-synthetic-01",
    replica_b_id="owner-offline-dev-synthetic-01",
    replica_b_manifest_sha256="c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4",
    witness_invocation_id="5136ea7af2544450b9370fa412786c98",
    witness_main_pid="143946",
)

INSTALLABLES = {"registry": "authority-registry.v1.json", "root": "registry-root.json",
                "anchor": "witness-anchor.json"}
PIN_FILES = ("genesis-pin.json", "authorization-register.json", "pin-record.json")
CHAIN_FILES = ("chain-1.json", "witness.json", "w9verifier.out", "w9verifier.err", "w9verifier.rc")
HOST_FILES = ("identity.out", "identity.rc", "w9verifier.out", "w9verifier.err", "w9verifier.rc")
BINDING_DIR = "binding"
TRUST_FILE, CHAIN_FILE, PIN_FILE, BINDING_FILE = ("trust-inputs.json", "chain-export.json", "genesis-pin.json",
                                                  "BINDING.json")
EXPORTS_DIR = "exports"          # one NEW directory per acquisition: exports/<NN>-<acquisitionId>/
ACQUISITIONS_DIR = "acquisitions"
RECEIPT_FILE = "ACQUISITION.json"
ATTEMPT_DIR = "attempt"
GATES_DIR = "gates"
VIEWS_DIR = "views"
C1_FILE = "C1_OPENING.json"
C4B_ELIGIBILITY_FILE = "C4B_ELIGIBILITY.json"


# ------------------------------------------------------------ owner texts ---
# Record §6. `{...}` placeholders are bound at runtime from files; tool pins are static. No text implies the next.

FREEZE_LINE = ("From this successful opening through C5, no intentional merge, deploy, reboot or witness restart is "
               "permitted. An unexpected external drift does not advance the sequence: it enters the reviewed "
               "revalidation path, and continuing requires the relevant fresh gate.")
C1_LINES = (
    "I authorize opening the Package C (record 1 + acceptance envelope 1) live sequence now, for this current "
    "DEV_SYNTHETIC sequence only.",
    "Continuity: " + CONTINUITY + ".",
    FREEZE_LINE,
    "Control commit: {control}.",
    "Operator: " + OPERATOR + " SHA-256 {operator}.",
    "Owner freshness tool: " + FRESHNESS_TOOL + " SHA-256 {freshness_tool}.",
    "Committed witness genesis digest: {genesis}. chain/1.json SHA-256: {chain1}.",
    "This authorizes opening the sequence, read-only evidence (including receipt-bound acquisitions through the "
    "pinned read-only mb9_operator.py forms host POST9B and chain-export), the S25 read-only gate and the transfer "
    "of the reviewed bundle only. It does not authorize any owner-record write, record 1, either acceptance "
    "envelope copy, HELD, the signer, authority activation, First Memory or PROD.",
)
C2_LINES = (
    "I authorize APPEND_RECORD_1_REPLICA_A now for exactly one attempt within this current Package C sequence.",
    "Continuity: " + CONTINUITY + ".",
    "Control commit: {control}. Binding SHA-256: {binding}. Gate C2 SHA-256: {gate}.",
    "Target: Replica A {replica_a}. Peer: the non-custody, provenance-bound empty Replica B view (SHA-256 {view}).",
    "Record 1 candidate digest: {record}. Review package digest: {package}.",
    "Committed witness genesis digest: {genesis} (= the owner pin).",
    "I have reviewed the candidate and repeat its digest by hand to owner_freshness_tool append.",
    "I understand that this is an owner-record write: record 1 on Replica A is never overwritten or removed, and "
    "freshness remains FRESHNESS_UNKNOWN until Replica B holds the identical record.",
    "This go does not authorize record 1 on Replica B, either acceptance envelope copy, HELD, the signer, authority "
    "activation, First Memory or PROD.",
    "Any REFUSED, FAILED, traceback, pending file or other STOP after the attempt marker consumes this go. There is "
    "no automatic retry.",
)
C3_LINES = (
    "I authorize APPEND_RECORD_1_REPLICA_B on the S25 now for exactly one attempt within this current Package C "
    "sequence.",
    "Continuity: " + CONTINUITY + ".",
    "Control commit: {control}. Binding SHA-256: {binding}. Gate C3 SHA-256: {gate}.",
    "Target: Replica B {replica_b}, run by me locally in Termux, with no SSH and no ADB. Peer: the non-custody "
    "Replica A view (SHA-256 {view}).",
    "S25 bundle SHA-256: {bundle}. Record 1 digest: {record} (the same record as Replica A).",
    "I understand that this is an owner-record write and that AUTHENTIC + CURRENT becomes possible only when "
    "Replica B holds exactly this record.",
    "This go does not authorize either acceptance envelope copy, HELD, the signer, authority activation, First "
    "Memory or PROD.",
    "Any REFUSED, FAILED, traceback, pending file or other STOP after the attempt marker consumes this go. There is "
    "no automatic retry.",
)
ENVELOPE_SCOPE_LINE = ("I understand that the envelope is owner-acceptance evidence only: it does not make freshness "
                       "current, does not make Registry V1 effective, does not start the signer, does not write HELD "
                       "and grants no authority.")
C4A_LINES = (
    "I authorize APPEND_ENVELOPE_1_COPY_A now for exactly one attempt within this current Package C sequence: "
    "initialization of acceptance store A, then the one envelope append to store A on the laptop.",
    "Continuity: " + CONTINUITY + ".",
    "Control commit: {control}. Binding SHA-256: {binding}. Gate C4A SHA-256: {gate}.",
    "Freshness: AUTHENTIC + CURRENT for record 1 {record}, observed in this sequence.",
    "Target: acceptance store A {store_a}. Peer: the non-custody, provenance-bound empty store B view (SHA-256 "
    "{view}).",
    "Envelope digest: {envelope}. Review package digest: {package}.",
    ENVELOPE_SCOPE_LINE,
    "This go does not authorize APPEND_ENVELOPE_1_COPY_B, HELD, the signer, authority activation, First Memory or "
    "PROD.",
    "Any REFUSED, FAILED, traceback, pending file or other STOP after the attempt marker consumes this go. There is "
    "no automatic retry.",
)
C4B_LINES = (
    "I authorize APPEND_ENVELOPE_1_COPY_B on the S25 now for exactly one attempt within this current Package C "
    "sequence: initialization of acceptance store B, then the one envelope append to store B, run by me locally in "
    "Termux, with no SSH and no ADB.",
    "Continuity: " + CONTINUITY + ".",
    "Control commit: {control}. Binding SHA-256: {binding}. Gate C4B SHA-256: {gate}.",
    "C4B eligibility SHA-256: {eligibility}: a fresh read proved exactly ACCEPTANCE_PARTIAL, with copy A exact and "
    "copy B absent.",
    "Envelope digest: {envelope} (the same envelope as copy A). Record 1 digest: {record}.",
    "S25 bundle SHA-256: {bundle}. Peer: the non-custody store A view (SHA-256 {store_view}).",
    ENVELOPE_SCOPE_LINE,
    "This go does not authorize HELD, the signer, authority activation, First Memory or PROD.",
    "Any REFUSED, FAILED, traceback, pending file or other STOP after the attempt marker consumes this go. There is "
    "no automatic retry.",
)
C5_LINES = (
    "I accept Package C for this sequence: record 1 on Replica A and Replica B and acceptance envelope 1 on copies A "
    "and B are COMPLETED.",
    "Record 1 digest: {record}. Envelope digest: {envelope}. Binding SHA-256: {binding}.",
    "Freshness: AUTHENTIC + CURRENT. Acceptance: ACCEPTANCE_COMPLETE.",
    "REGISTRY_EFFECTIVE remains NO. AUTHORITY_ACTIVE remains NO. authorityGranted remains false. The signer remains "
    "inactive.",
    "This acceptance authorizes nothing further: not HELD, the signer, authority activation, First Memory or PROD. "
    "The Package C freeze ends now.",
)
STOP_LINES = (
    "I stop this Package C sequence now, before any owner-record write, for this current DEV_SYNTHETIC sequence "
    "only.",
    "Control commit: {control}. C1 record SHA-256: {c1}.",
    "No C2 attempt marker exists and no owner record was written by this sequence.",
    "This sequence is STOPPED / HISTORICAL / NON-REUSABLE. Its freeze is released; the release authorizes nothing.",
)
TEMPLATES = {"C1": C1_LINES, "C2": C2_LINES, "C3": C3_LINES, "C4A": C4A_LINES, "C4B": C4B_LINES, "C5": C5_LINES,
             "STOP": STOP_LINES}


def check_text(text: str, lines: Sequence[str], **values: str) -> None:
    """Every canonical line, with its bound values, appears verbatim (whitespace-normalized)."""
    flat = " ".join(text.replace(">", " ").split())
    for line in lines:
        _need(" ".join(line.format(**values).split()) in flat, "GO_LINE_MISSING")


# ----------------------------------------------------------- state machine ---
# Record §2. Pure; forward only. C1 -> C2 -> C3 -> C4A -> C4B -> C5.

PC0 = "PC0_NOT_OPENED"
PC1 = "PC1_OPENED_READ_ONLY"
PC1B = "PC1_BOUND_KNOWN_EMPTY"
PC2A = "PC2_ARMED"
PC2 = "PC2_RECORD1_A_PARTIAL"            # P3-5 step 10 -> OWNER_RECORD_PARTIAL; FRESHNESS_UNKNOWN by design
PC3A = "PC3_ARMED"
PC3 = "PC3_RECORD1_CURRENT"              # P3-5 step 11 -> OWNER_FRESHNESS_CURRENT; acceptance NOT_PRESENT
PC4AA = "PC4A_ARMED"
PC4AP = "PC4A_ENVELOPE_A_PARTIAL"        # P3-5 step 11a -> OWNER_ACCEPTANCE_EVIDENCE_PARTIAL
PC4BA = "PC4B_ARMED"
PC4B = "PC4B_ENVELOPE_COMPLETE"          # P3-5 step 11b -> OWNER_ACCEPTANCE_EVIDENCED
PC5 = "PC5_PACKAGE_C_ACCEPTED"
STOPPED = "PC_STOPPED_BEFORE_OWNER_RECORD"
HALT = "PC_HALT_MANUAL_RECOVERY"

BOOTSTRAP_STATE = {PC2: "OWNER_RECORD_PARTIAL", PC3: "OWNER_FRESHNESS_CURRENT",
                   PC4AP: "OWNER_ACCEPTANCE_EVIDENCE_PARTIAL", PC4B: "OWNER_ACCEPTANCE_EVIDENCED",
                   PC5: "OWNER_ACCEPTANCE_EVIDENCED"}
# Owner-record points of no return (record §4). An armed state counts: once the marker exists, whether the write
# happened is decided only by reading the copies.
PONR_STATES = frozenset({PC2A, PC2, PC3A, PC3, PC4AA, PC4AP, PC4BA, PC4B, PC5})
# The states a NEW sequence may resume at (record §7.3), each re-proven fresh at its opening.
RESUMABLE = {"EMPTY": PC1B, "A_ONLY": PC2, "AB_NO_ENVELOPE": PC3, "ENVELOPE_A_ONLY": PC4AP}
GATE_SOURCE = {"C2": PC1B, "C3": PC2, "C4A": PC3, "C4B": PC4AP, "C5": PC4B}
ARM = {"C2": (PC1B, PC2A), "C3": (PC2, PC3A), "C4A": (PC3, PC4AA), "C4B": (PC4AP, PC4BA)}

# Invalidators (record §7.2). REVALIDATE: nothing owner-held changed; the next act needs a fresh gate (and, after a
# consumed marker, a new go). HALT: owner-record or lineage inconsistency; manual recovery, never auto-repaired.
REVALIDATE_EVENTS = frozenset({
    "DEPLOY_OCCURRED", "WORKFLOW_QUEUE_NOT_EMPTY", "WITNESS_INCARNATION_CHANGED", "WITNESS_RESTARTED",
    "BOOT_ID_CHANGED", "REBOOT_REQUIRED_PRESENT", "CONTROL_CHANGED", "TOOL_PIN_CHANGED", "S25_BUNDLE_MISMATCH",
    "W9_PHASE_NOT_EXACT", "EVIDENCE_UNKNOWN", "TRANSCRIPTION_MISMATCH", "ACQUISITION_NOT_FRESH",
})
HALT_EVENTS = frozenset({
    "GENESIS_MISMATCH", "CHAIN_ADVANCED", "CHAIN_BYTES_CHANGED", "OWNER_RECORD_INCONSISTENT", "REPLICA_PENDING_WRITE",
    "ACCEPTANCE_PENDING_WRITE", "ACCEPTANCE_CONFLICTING", "PIN_BYTES_CHANGED", "HOLD_STORE_NOT_EMPTY",
    "SIGNER_ACTIVE", "AUTHORITY_GRANTED", "REGISTRY_EFFECTIVE",
})

# The only facts Package C may ever report about the authority boundary (record §11).
AUTHORITY_BOUNDARY = {"REGISTRY_EFFECTIVE": "NO", "AUTHORITY_ACTIVE": "NO", "authorityGranted": False,
                      "signer": "INACTIVE", "HELD": "NOT AUTHORIZED", "FIRST_MEMORY": "NOT AUTHORIZED",
                      "PROD": "NOT AUTHORIZED"}


@dataclass(frozen=True)
class EventResultV1:
    status: str
    state: str
    reason: str | None = None

    @property
    def advanced(self) -> bool:
        return self.status == "ADVANCED"


def _freshness_current(value: Any) -> bool:
    return isinstance(value, OF.FreshnessResultV1) and value.current


def _acceptance_is(value: Any, state: str) -> bool:
    return isinstance(value, OA.AcceptanceResultV1) and value.state == state


@dataclass
class PackageCSequenceV1:
    """One Package C sequence. Every transition takes literal evidence; freshness and acceptance only as the real
    `FreshnessResultV1` / `AcceptanceResultV1`, never a boolean."""

    state: str = PC0
    revalidate: bool = True                  # a fresh gate is required before the next arm
    c4b_eligible: bool = False               # set only by a fresh eligibility read AFTER the C4B gate
    history: list[str] = field(default_factory=list)

    def _ok(self, state: str, event: str) -> EventResultV1:
        self.state = state
        self.history.append(event)
        return EventResultV1("ADVANCED", state)

    def _no(self, reason: str) -> EventResultV1:
        return EventResultV1("REFUSED", self.state, reason)

    def open(self, *, c1_exact: bool) -> EventResultV1:
        if self.state != PC0:
            return self._no("TRANSITION_OUT_OF_ORDER")
        return self._ok(PC1, "C1") if c1_exact is True else self._no("C1_NOT_EXACT")

    def bind(self, *, binding_exact: bool, s25_c1_exact: bool, register_entry: str) -> EventResultV1:
        """The fresh binding plus the S25 read-only gate. The observed owner-register entry decides where the
        sequence starts: KNOWN_EMPTY, or a canonical recoverable state of an earlier sequence (record §7.3)."""
        if self.state != PC1:
            return self._no("TRANSITION_OUT_OF_ORDER")
        if binding_exact is not True or s25_c1_exact is not True:
            return self._no("BINDING_NOT_EXACT")
        if register_entry not in RESUMABLE:
            return self.invalidate("OWNER_RECORD_INCONSISTENT")
        self.revalidate = True
        return self._ok(RESUMABLE[register_entry], "BIND:" + register_entry)

    def gate(self, stage: str, *, continuity_exact: bool) -> EventResultV1:
        if self.state in (HALT, STOPPED, PC5):
            return self._no("SEQUENCE_ENDED")
        if stage not in GATE_SOURCE or self.state != GATE_SOURCE[stage]:
            return self._no("GATE_OUT_OF_ORDER")
        self.c4b_eligible = False                  # eligibility must be read after this gate
        if continuity_exact is not True:
            self.revalidate = True
            return self._no("CONTINUITY_NOT_EXACT")
        self.revalidate = False
        self.history.append("GATE:" + stage)
        return EventResultV1("ADVANCED", self.state, "GATE_PASS")

    def c4b_eligibility(self, *, freshness: Any, acceptance: Any, copy_a_exact: bool, copy_b_absent: bool
                        ) -> EventResultV1:
        """C4B is eligible only after a fresh read (after the C4B gate) proves exactly ACCEPTANCE_PARTIAL, copy A
        exact and copy B absent. Copy B already present is HALT: never a second write."""
        if self.state != PC4AP:
            return self._no("TRANSITION_OUT_OF_ORDER")
        if self.revalidate:
            return self._no("FRESH_GATE_REQUIRED")
        if copy_b_absent is not True:
            return self.invalidate("ACCEPTANCE_CONFLICTING")
        if not _freshness_current(freshness) or not _acceptance_is(acceptance, OA.ACCEPTANCE_PARTIAL) \
                or copy_a_exact is not True:
            return self.invalidate("ACCEPTANCE_CONFLICTING")
        self.c4b_eligible = True
        self.history.append("C4B_ELIGIBLE")
        return EventResultV1("ADVANCED", self.state, "C4B_ELIGIBLE")

    def arm(self, stage: str, *, go_exact: bool, freshness: Any = None) -> EventResultV1:
        source, target = ARM.get(stage, (None, None))
        if source is None or self.state != source:
            return self._no("TRANSITION_OUT_OF_ORDER")
        if self.revalidate:
            return self._no("FRESH_GATE_REQUIRED")
        if stage == "C4B" and not self.c4b_eligible:
            return self._no("C4B_NOT_ELIGIBLE")
        if go_exact is not True:
            return self._no("GO_NOT_EXACT")
        if stage in ("C4A", "C4B") and not _freshness_current(freshness):
            return self._no("FRESHNESS_NOT_CURRENT")
        self.revalidate, self.c4b_eligible = True, False      # one gate, one go, one attempt
        return self._ok(target, "ARM:" + stage)

    def observe_record_a(self, *, replica_a_exact_record1: bool, replica_b_empty: bool, freshness: Any
                         ) -> EventResultV1:
        if self.state != PC2A:
            return self._no("TRANSITION_OUT_OF_ORDER")
        if replica_a_exact_record1 is not True or replica_b_empty is not True:
            return self.invalidate("OWNER_RECORD_INCONSISTENT")
        if not isinstance(freshness, OF.FreshnessResultV1) or freshness.freshness != OF.FRESHNESS_UNKNOWN:
            return self.invalidate("OWNER_RECORD_INCONSISTENT")    # CURRENT after A alone is impossible: STOP
        return self._ok(PC2, "RECORD1_A")

    def observe_record_b(self, *, transcription_exact: bool, replicas_identical: bool, freshness: Any
                         ) -> EventResultV1:
        if self.state != PC3A:
            return self._no("TRANSITION_OUT_OF_ORDER")
        if transcription_exact is not True:
            return self.invalidate("TRANSCRIPTION_MISMATCH")
        if replicas_identical is not True or not _freshness_current(freshness):
            return self.invalidate("OWNER_RECORD_INCONSISTENT")
        return self._ok(PC3, "RECORD1_B")

    def observe_envelope_a(self, *, freshness: Any, acceptance: Any) -> EventResultV1:
        if self.state != PC4AA:
            return self._no("TRANSITION_OUT_OF_ORDER")
        if not _freshness_current(freshness):
            return self.invalidate("OWNER_RECORD_INCONSISTENT")
        if not _acceptance_is(acceptance, OA.ACCEPTANCE_PARTIAL):
            return self.invalidate("ACCEPTANCE_CONFLICTING")
        return self._ok(PC4AP, "ENVELOPE_A")

    def observe_envelope_b(self, *, transcription_exact: bool, freshness: Any, acceptance: Any) -> EventResultV1:
        if self.state != PC4BA:
            return self._no("TRANSITION_OUT_OF_ORDER")
        if transcription_exact is not True:
            return self.invalidate("TRANSCRIPTION_MISMATCH")
        if not _freshness_current(freshness) or not _acceptance_is(acceptance, OA.ACCEPTANCE_COMPLETE):
            return self.invalidate("ACCEPTANCE_CONFLICTING")
        return self._ok(PC4B, "ENVELOPE_B")

    def accept(self, *, c5_exact: bool, freshness: Any, acceptance: Any) -> EventResultV1:
        if self.state != PC4B:
            return self._no("TRANSITION_OUT_OF_ORDER")
        if self.revalidate:
            return self._no("FRESH_GATE_REQUIRED")
        if c5_exact is not True or not _freshness_current(freshness) \
                or not _acceptance_is(acceptance, OA.ACCEPTANCE_COMPLETE):
            return self._no("C5_PRECONDITION_NOT_MET")
        return self._ok(PC5, "C5")

    def stop(self) -> EventResultV1:
        """The owner pre-C2 stop: only before any owner-record point of no return."""
        if self.state not in (PC1, PC1B) or any(h.startswith("ARM:") for h in self.history):
            return self._no("STOP_REFUSED_ATTEMPT_MARKER_PRESENT")
        return self._ok(STOPPED, "STOP")

    def invalidate(self, event: str) -> EventResultV1:
        """External drift never advances the sequence. HALT events end it; everything else (including any event
        not known to be harmless: UNKNOWN => revalidate) keeps the state and requires a fresh gate."""
        self.c4b_eligible = False
        if event in HALT_EVENTS:
            self.history.append("HALT:" + event)
            self.state = HALT
            return EventResultV1("HALTED", HALT, event)
        self.revalidate = True
        self.history.append("REVALIDATE:" + event)
        return EventResultV1("REVALIDATE", self.state, event if event in REVALIDATE_EVENTS else "EVIDENCE_UNKNOWN")

    def reset(self) -> EventResultV1:
        if self.state in PONR_STATES or self.state == HALT:
            return self._no("OWNER_RECORD_PONR_PASSED")
        self.state, self.history, self.revalidate, self.c4b_eligible = PC0, [], True, False
        return EventResultV1("ADVANCED", PC0, "RESET_BEFORE_OWNER_RECORD")

    @staticmethod
    def authority_boundary() -> dict[str, Any]:
        return dict(AUTHORITY_BOUNDARY)

    @staticmethod
    def next_after_completion() -> str:
        return "NONE: HELD, the signer, activation, First Memory and PROD each need their own later authorization"


# ---------------------------------------------------------------- helpers ---

def _read(path: Path, reason: str) -> bytes:
    path = Path(path)
    _need(path.is_file() and not path.is_symlink(), reason + ":" + path.name)
    data = path.read_bytes()
    _need(len(data) <= T.MAX_INPUT_BYTES, reason + ":" + path.name)
    return data


def _json(data: bytes, reason: str) -> Any:
    try:
        return WR._json(data)
    except Exception as exc:  # noqa: BLE001 - any parse failure is a STOP
        raise Stop(reason) from exc


def _canonical_list(values: list[Any]) -> bytes:
    """RFC 8785 for the chain-export array (the same pinned `rfc8785` the tool's JCS uses, applied to a list)."""
    import rfc8785
    return rfc8785.dumps(list(values))


def _create(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0),
                 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def _new_dir(path: Path) -> Path:
    path = Path(path)
    _need(not os.path.lexists(path), "DIRECTORY_EXISTS:" + path.name)
    path.mkdir(mode=0o700)
    return path


def _document(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, indent=1).encode("utf-8") + b"\n"


def _exact_listing(directory: Path, names: Sequence[str], reason: str) -> None:
    _need(directory.is_dir() and not directory.is_symlink(), reason)
    _need(sorted(p.name for p in directory.iterdir()) == sorted(names), reason)


def _opening(workdir: Path) -> dict[str, Any]:
    return _json(_read(Path(workdir) / C1_FILE, "SEQUENCE_NOT_OPENED"), "C1_INVALID")


def _is_custody_root(path: Path) -> bool:
    """A canonical replica root (REPLICA.json + records/) or acceptance-store root (ACCEPTANCE.json + envelopes/)."""
    return (os.path.lexists(path / T.MANIFEST) and os.path.isdir(path / T.RECORDS)) or \
        (os.path.lexists(path / T.ACCEPTANCE_MANIFEST) and os.path.isdir(path / T.ENVELOPES))


def _under_custody_root(path: Path) -> bool:
    path = Path(os.path.abspath(path))
    return any(_is_custody_root(p) for p in (path, *path.parents))


def _disjoint(workdir: Path, canonical: Path, reason: str) -> None:
    """A canonical copy is never inside the work directory, and the work directory never inside a canonical copy."""
    a, b = Path(os.path.abspath(workdir)), Path(os.path.abspath(canonical))
    _need(a != b and a not in b.parents and b not in a.parents, reason)


# ------------------------------------------------------------ acquisition ---
# Record §3.1. A fresh acquisition is ONE read of the presented DEV world performed by `acquire` in THIS sequence:
# a STARTED log entry, the pinned read-only mb9_operator forms, a receipt binding sequence, time, control, pins,
# phase, incarnation, boot, genesis and every artifact hash, and a COMPLETED log entry binding the receipt hash.
# Identical artifact bytes are expected (the genesis is immutable); freshness is the receipt, never the directory.

Runner = Callable[[Sequence[str]], "tuple[int, bytes]"]


def _mb9_runner(args: Sequence[str]) -> tuple[int, bytes]:
    path = ROOT / MB9_OPERATOR
    _need(sha256_hex(path.read_bytes()) == TOOL_PINS[MB9_OPERATOR], "TOOL_PIN_MISMATCH:" + MB9_OPERATOR)
    result = subprocess.run([sys.executable, str(path), *args], capture_output=True, timeout=3600)
    return result.returncode, result.stdout


def _artifacts(directory: Path) -> dict[str, str]:
    out = {}
    for file in directory.rglob("*"):
        _need(not file.is_symlink(), "ACQUISITION_SYMLINK")
        if file.is_file() and file.name != RECEIPT_FILE:
            out[file.relative_to(directory).as_posix()] = sha256_hex(file.read_bytes())
    return dict(sorted(out.items()))


def _acquired_facts(export: Path) -> dict[str, Any]:
    """Re-derived from the artifact bytes on every use; the receipt's copy must equal it."""
    chain, host = export / "chain", export / "host"
    _need(chain.is_dir() and host.is_dir() and not chain.is_symlink() and not host.is_symlink(),
          "ACQUISITION_INCOMPLETE")
    _need(set(CHAIN_FILES) <= {p.name for p in chain.iterdir()} and set(HOST_FILES) <= {p.name for p in host.iterdir()},
          "ACQUISITION_INCOMPLETE")
    report = _json(_read(chain / "w9verifier.out", "ACQUISITION_INCOMPLETE"), "W9_REPORT_INVALID")
    host_report = _json(_read(host / "w9verifier.out", "ACQUISITION_INCOMPLETE"), "W9_REPORT_INVALID")
    _need(isinstance(report, dict) and isinstance(host_report, dict), "W9_REPORT_INVALID")
    identity = _read(host / "identity.out", "ACQUISITION_INCOMPLETE").decode("utf-8", "replace").splitlines()
    committed = report.get("committedGenesis") if isinstance(report.get("committedGenesis"), dict) else {}
    return {"phase": report.get("phase"), "hostPhase": host_report.get("phase"),
            "witnessInvocationId": report.get("witnessInvocationId"), "witnessMainPid": report.get("witnessMainPid"),
            "witnessNRestarts": report.get("witnessNRestarts"), "committedDigest": committed.get("digest"),
            "chain1Sha256": sha256_hex(_read(chain / "chain-1.json", "ACQUISITION_INCOMPLETE")),
            "devDate": identity[0] if len(identity) > 0 else None,
            "bootId": identity[3] if len(identity) > 3 else None,
            "rebootRequired": identity[5].removeprefix("REBOOT_REQUIRED=") if len(identity) > 5
            and identity[5].startswith("REBOOT_REQUIRED=") else None}


def acquire(repo: Path, workdir: Path, mb9_workdir: Path, *, runner: Runner | None = None,
            now: Callable[[], str] | None = None, pinned: Mapping[str, str] | None = None) -> dict[str, Any]:
    """ONE fresh read. Only the two pinned read-only mb9_operator forms run; nothing else reaches DEV."""
    workdir = Path(workdir)
    opening = _opening(workdir)
    pinned = dict(pinned) if pinned is not None else check_pins(Path(repo))
    _need(pinned["control"] == opening["control"], "CONTROL_CHANGED")
    runner, now = runner or _mb9_runner, now or _utc_now
    log = workdir / ACQUISITIONS_DIR
    log.mkdir(mode=0o700, exist_ok=True)
    index = len([p for p in log.iterdir() if p.name.endswith(".started.json")]) + 1
    acquisition_id = os.urandom(16).hex()
    name = f"{index:02d}-{acquisition_id}"
    started = now()
    _create(log / f"{name}.started.json", _document({"sequenceId": opening["sequenceId"],
                                                     "acquisitionId": acquisition_id, "index": index,
                                                     "startedAt": started}))
    export = _new_dir(workdir / EXPORTS_DIR / name)
    commands = {"host": ["host", str(repo), str(mb9_workdir), str(export / "host"), "POST9B"],
                "chain": ["chain-export", str(repo), str(mb9_workdir), str(export / "chain")]}
    results = {}
    for key, argv in commands.items():
        code, stdout = runner(argv)
        try:
            parsed = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            parsed = {}
        results[key] = {"form": argv[0], "args": argv[1:], "exitCode": code, "stdoutSha256": sha256_hex(stdout),
                        "result": parsed.get("result") if isinstance(parsed, dict) else None}
    completed = now()
    receipt = {"receiptType": "LILITH_PKGC_ACQUISITION_RECEIPT", "schemaVersion": 1,
               "sequenceId": opening["sequenceId"], "acquisitionId": acquisition_id, "index": index,
               "startedAt": started, "completedAt": completed, "control": pinned["control"],
               "operatorSha256": pinned["operator"], "toolPins": dict(TOOL_PINS), "commands": results,
               "facts": _acquired_facts(export), "artifacts": _artifacts(export)}
    raw = _document(receipt)
    _create(export / RECEIPT_FILE, raw)
    _create(log / f"{name}.completed.json", _document({"sequenceId": opening["sequenceId"],
                                                       "acquisitionId": acquisition_id, "completedAt": completed,
                                                       "receiptSha256": sha256_hex(raw)}))
    return {"result": "PKGC_ACQUIRED", "acquisition": name, "receiptSha256": sha256_hex(raw),
            "facts": receipt["facts"]}


def verify_acquisition(workdir: Path, export: Path) -> dict[str, Any]:
    """The freshness rule (record §3.1). Every clause must hold; an old export copied into a new directory has no
    receipt registered in this sequence's acquisition log and is refused (ACQUISITION_NOT_FRESH)."""
    workdir, export = Path(workdir), Path(export)
    opening = _opening(workdir)
    _need(export.parent.resolve() == (workdir / EXPORTS_DIR).resolve(), "EXPORT_NOT_IN_SEQUENCE")
    match = re.fullmatch(r"(\d{2})-([0-9a-f]{32})", export.name)
    _need(match is not None and (export / RECEIPT_FILE).is_file(), "ACQUISITION_NOT_FRESH:NO_RECEIPT")
    raw = _read(export / RECEIPT_FILE, "ACQUISITION_NOT_FRESH")
    receipt = _json(raw, "ACQUISITION_NOT_FRESH:RECEIPT_INVALID")
    log = workdir / ACQUISITIONS_DIR
    started = log / f"{export.name}.started.json"
    completed = log / f"{export.name}.completed.json"
    _need(started.is_file() and completed.is_file(), "ACQUISITION_NOT_FRESH:NOT_IN_SEQUENCE_LOG")
    started_doc = _json(started.read_bytes(), "ACQUISITION_NOT_FRESH")
    completed_doc = _json(completed.read_bytes(), "ACQUISITION_NOT_FRESH")
    previous = [_json(p.read_bytes(), "ACQUISITION_NOT_FRESH")["startedAt"]
                for p in sorted(log.glob("*.started.json")) if p.name < started.name]
    checks = {
        "sequenceBound": receipt.get("sequenceId") == opening["sequenceId"] == started_doc.get("sequenceId")
        == completed_doc.get("sequenceId"),
        "acquisitionBound": receipt.get("acquisitionId") == match.group(2) == started_doc.get("acquisitionId")
        and receipt.get("index") == int(match.group(1)) == started_doc.get("index"),
        "receiptLogged": completed_doc.get("receiptSha256") == sha256_hex(raw),
        "timestamps": all(isinstance(receipt.get(k), str) and _INSTANT.fullmatch(receipt[k])
                          for k in ("startedAt", "completedAt"))
        and receipt.get("startedAt") == started_doc.get("startedAt")
        and opening["openedAt"] <= receipt["startedAt"] <= receipt["completedAt"]
        and all(p <= receipt["startedAt"] for p in previous),
        "controlBound": receipt.get("control") == opening["control"],
        "toolPinsBound": receipt.get("toolPins") == TOOL_PINS,
        "commandsExact": isinstance(receipt.get("commands"), dict)
        and receipt["commands"].get("host", {}).get("form") == "host"
        and receipt["commands"]["host"].get("args", [None] * 4)[3] == "POST9B"
        and receipt["commands"]["host"].get("exitCode") == 0
        and receipt["commands"]["host"].get("result") == "MB9_HOST_POST9B_PASS"
        and receipt["commands"].get("chain", {}).get("form") == "chain-export"
        and receipt["commands"]["chain"].get("exitCode") == 0
        and receipt["commands"]["chain"].get("result") == "MB9_CHAIN_EXPORTED",
        "artifactsExact": receipt.get("artifacts") == _artifacts(export),
    }
    facts = _acquired_facts(export)
    checks["factsExact"] = receipt.get("facts") == facts
    exact = all(checks.values())
    _need(exact, "ACQUISITION_NOT_FRESH:" + ",".join(k for k, v in checks.items() if not v))
    return {"receiptSha256": sha256_hex(raw), "receipt": receipt, "facts": facts, "acquisition": export.name}


def check_export(workdir: Path, export: Path, pins: PackageCPinsV1) -> dict[str, Any]:
    """A verified fresh acquisition whose W9 / host facts are exactly the accepted committed-genesis world."""
    acquired = verify_acquisition(workdir, export)
    chain = Path(export) / "chain"
    _need(_read(chain / "w9verifier.rc", "ACQUISITION_INCOMPLETE").strip() == b"0", "W9_VERIFIER_FAILED")
    _need(_read(chain / "w9verifier.err", "ACQUISITION_INCOMPLETE") == b"", "W9_VERIFIER_STDERR")
    report = _json(_read(chain / "w9verifier.out", "ACQUISITION_INCOMPLETE"), "W9_REPORT_INVALID")
    genesis = _read(chain / "chain-1.json", "ACQUISITION_INCOMPLETE")
    pointer = _read(chain / "witness.json", "ACQUISITION_INCOMPLETE")
    evidence = report.get("evidence9b") if isinstance(report.get("evidence9b"), dict) else {}
    facts = acquired["facts"]
    checks = {
        "w9PhaseExact": facts["phase"] == W9_5 and facts["hostPhase"] == W9_5,
        "w9NoFailures": report.get("failures") == [],
        "evidence9bAllTrue": bool(evidence) and all(v is True for v in evidence.values()),
        "committedDigestIsAccepted": facts["committedDigest"] == pins.genesis_digest,
        "chain1BytesAccepted": facts["chain1Sha256"] == pins.chain_1_sha256,
        "pointerEqualsGenesis": pointer == genesis,
        "incarnationAccepted": (str(facts["witnessInvocationId"]), str(facts["witnessMainPid"]))
        == (pins.witness_invocation_id, pins.witness_main_pid),
        "noRestart": str(facts["witnessNRestarts"]) == "0",
        "bootIdKnown": isinstance(facts["bootId"], str) and bool(facts["bootId"]),
        "rebootRequiredAbsent": facts["rebootRequired"] == "absent",
        "holdStoreEmpty": report.get("holdStoreListing") == [],
        "signerNoLaterState": isinstance(report.get("signerLaterState"), dict)
        and not any(report["signerLaterState"].values()),
        "registryNotEffective": report.get("registryEffective") is False,
        "authorityNotActive": report.get("authorityActive") is False and report.get("authorityGranted") is False,
    }
    return {"checks": checks, "exact": all(checks.values()), "genesisBytes": genesis, "facts": facts,
            "receiptSha256": acquired["receiptSha256"], "receipt": acquired["receipt"],
            "acquisition": acquired["acquisition"]}


def _consumed(workdir: Path) -> set[str]:
    used = set()
    binding = Path(workdir) / BINDING_DIR / BINDING_FILE
    if binding.is_file():
        used.add(_json(binding.read_bytes(), "BINDING_INVALID")["inputs"]["acquisition"])
    gates = Path(workdir) / GATES_DIR
    if gates.is_dir():
        used |= {_json(p.read_bytes(), "GATE_INVALID")["acquisition"] for p in gates.iterdir()}
    return used


# ------------------------------------------------------------------ binding ---

def bind(workdir: Path, installables: Path, pin_dir: Path, export: Path, replica_a: Path, pr2_sha256: str,
         p33_sha256: str, *, pins: PackageCPinsV1 = ACCEPTED_PINS) -> dict[str, Any]:
    """The canonical chain-export binding (record §3). Read-only over its inputs; writes only the NEW binding dir."""
    workdir = Path(workdir)
    _need((workdir / C1_FILE).is_file(), "SEQUENCE_NOT_OPENED")
    _need(not os.path.lexists(workdir / BINDING_DIR), "BINDING_EXISTS")
    _need(all(isinstance(v, str) and _HEX64.fullmatch(v) for v in (pr2_sha256, p33_sha256)),
          "OWNER_EVIDENCE_DIGEST_INVALID")
    _disjoint(workdir, Path(replica_a), "CANONICAL_COPY_INSIDE_WORKDIR")
    # 1. owner-held installables: exactly the accepted bytes
    _exact_listing(Path(installables), list(INSTALLABLES.values()), "INSTALLABLES_INEXACT")
    raw = {key: _read(Path(installables) / name, "INSTALLABLE_ABSENT") for key, name in INSTALLABLES.items()}
    _need(sha256_hex(raw["registry"]) == pins.registry_sha256, "REGISTRY_NOT_ACCEPTED")
    _need(sha256_hex(raw["root"]) == pins.root_anchor_sha256, "ROOT_ANCHOR_NOT_ACCEPTED")
    _need(sha256_hex(raw["anchor"]) == pins.witness_anchor_sha256, "WITNESS_ANCHOR_NOT_ACCEPTED")
    # 2. the owner pin record P-A: exactly the three accepted files
    _exact_listing(Path(pin_dir), PIN_FILES, "PIN_DIRECTORY_INEXACT")
    pin_raw = {name: _read(Path(pin_dir) / name, "PIN_ABSENT") for name in PIN_FILES}
    _need((sha256_hex(pin_raw[PIN_FILES[0]]), sha256_hex(pin_raw[PIN_FILES[1]]), sha256_hex(pin_raw[PIN_FILES[2]]))
          == (pins.pin_sha256, pins.register_sha256, pins.pin_record_sha256), "PIN_BYTES_NOT_ACCEPTED")
    pin = WR.OwnerGenesisPinV1.from_dict(_json(pin_raw[PIN_FILES[0]], "PIN_INVALID"))
    _need((pin.environment, pin.genesis_witness_digest) == (pins.environment, pins.genesis_digest), "PIN_NOT_ACCEPTED")
    # 3. one fresh, receipt-bound acquisition of the presented world, never consumed before
    _need(Path(export).name not in _consumed(workdir), "EXPORT_REUSED")
    exported = check_export(workdir, export, pins)
    _need(exported["exact"], "EXPORT_NOT_EXACT:" + ",".join(k for k, v in exported["checks"].items() if not v))
    # 4. canonical tool inputs, deterministic from the bytes above
    trust_bytes = OF.record_bytes({"trustType": T.TRUST_TYPE, "schemaVersion": 1, "environment": pins.environment,
                                   "witnessAnchor": _json(raw["anchor"], "ANCHOR_INVALID"),
                                   "registryRoot": _json(raw["root"], "ROOT_INVALID"),
                                   "registries": [_json(raw["registry"], "REGISTRY_INVALID")]})
    chain_bytes = _canonical_list([_json(exported["genesisBytes"], "GENESIS_INVALID")])
    out = _new_dir(workdir / BINDING_DIR)
    _create(out / TRUST_FILE, trust_bytes)
    _create(out / CHAIN_FILE, chain_bytes)
    _create(out / PIN_FILE, pin_raw[PIN_FILES[0]])
    # 5. the canonical tool's own view: authentic, genesis only, = pin
    trust = T.load_trust(out / TRUST_FILE)
    inspected = T.inspect_chain(trust, out / CHAIN_FILE, pins.environment)
    replica = T.load_replica(Path(replica_a))
    _need(replica.replica_id == pins.replica_a_id, "REPLICA_A_ID_MISMATCH")
    tool_checks = {
        "authentic": inspected.get("authenticity") == OF.AUTHENTIC,
        "genesisOnly": inspected.get("entries") == 1,
        "genesisEqualsPin": inspected.get("genesisWitnessDigest") == pins.genesis_digest,
        "headIsGenesis": inspected.get("headWitnessDigest") == pins.genesis_digest,
        "noConsumedAuthorization": inspected.get("consumedAuthorizationIds") == [],
    }
    _need(all(tool_checks.values()), "TOOL_VIEW_NOT_EXACT:" + ",".join(k for k, v in tool_checks.items() if not v))
    binding = {
        "resultType": RESULT_TYPE, "kind": "PACKAGE_C_BINDING", "schemaVersion": 1,
        "sequenceId": _opening(workdir)["sequenceId"],
        "environment": pins.environment, "authorityProfile": pins.authority_profile,
        "inputs": {"registrySha256": pins.registry_sha256, "rootAnchorSha256": pins.root_anchor_sha256,
                   "witnessAnchorSha256": pins.witness_anchor_sha256, "pinSha256": pins.pin_sha256,
                   "registerSha256": pins.register_sha256, "pinRecordSha256": pins.pin_record_sha256,
                   "chain1Sha256": pins.chain_1_sha256, "acquisition": exported["acquisition"],
                   "acquisitionReceiptSha256": exported["receiptSha256"]},
        "outputs": {TRUST_FILE: sha256_hex(trust_bytes), CHAIN_FILE: sha256_hex(chain_bytes),
                    PIN_FILE: pins.pin_sha256},
        "genesisDigest": pins.genesis_digest, "snapshot": exported["facts"],
        "replicaA": {"replicaId": replica.replica_id, "records": list(replica.digests),
                     "manifestSha256": sha256_hex((Path(replica_a) / T.MANIFEST).read_bytes())},
        "replicaB": {"replicaId": pins.replica_b_id, "manifestSha256": pins.replica_b_manifest_sha256},
        "attachedEvidence": {"PR2_REVALIDATION": pr2_sha256, "P3_3_INDEPENDENCE": p33_sha256},
        "toolView": tool_checks, "freshness": "UNKNOWN", "record1": "NOT CREATED BY BINDING",
        "authorityBoundary": dict(AUTHORITY_BOUNDARY),
    }
    _create(out / BINDING_FILE, OF.record_bytes(binding))
    return {"result": "PKGC_BINDING_EXACT", "bindingSha256": sha256_hex((out / BINDING_FILE).read_bytes()),
            "outputs": binding["outputs"], "note": "binding != record 1; nothing was written to any replica"}


def load_binding(workdir: Path) -> tuple[dict[str, Any], str]:
    directory = Path(workdir) / BINDING_DIR
    _exact_listing(directory, (TRUST_FILE, CHAIN_FILE, PIN_FILE, BINDING_FILE), "BINDING_INEXACT")
    raw = _read(directory / BINDING_FILE, "BINDING_ABSENT")
    binding = _json(raw, "BINDING_INVALID")
    for name, digest in binding["outputs"].items():
        _need(sha256_hex(_read(directory / name, "BINDING_INEXACT")) == digest, "BINDING_OUTPUT_CHANGED:" + name)
    return binding, sha256_hex(raw)


# --------------------------------------------------------------- continuity ---
# Record §7.1: exactly what must stay unchanged from the binding through C5. Control, pins, phase, incarnation,
# boot and genesis come from the verified acquisition receipt; deploy, queue and bundle from the owner's read-only
# facts file.

CONTINUITY_FACTS = ("lastDeployRunId", "workflowQueueEmpty", "s25BundleSha256")
OPENING_FACTS = ("control", "lastDeployRunId")


def continuity(binding: Mapping[str, Any], exported: Mapping[str, Any], facts: Mapping[str, Any],
               opening: Mapping[str, Any], bundle_sha256: str | None) -> dict[str, Any]:
    """A missing fact is UNKNOWN, and UNKNOWN is never equality (=> REVALIDATE)."""
    events = []
    snapshot, acquired, checks = binding["snapshot"], exported["facts"], exported["checks"]
    if not checks["committedDigestIsAccepted"]:
        events.append("GENESIS_MISMATCH")
    if not checks["chain1BytesAccepted"] or not checks["pointerEqualsGenesis"]:
        events.append("CHAIN_BYTES_CHANGED")
    if not checks["w9PhaseExact"]:
        events.append("CHAIN_ADVANCED" if "W9_LATER_STATE" in (acquired["phase"], acquired["hostPhase"])
                      else "W9_PHASE_NOT_EXACT")
    if (acquired["witnessInvocationId"], acquired["witnessMainPid"]) != \
            (snapshot["witnessInvocationId"], snapshot["witnessMainPid"]):
        events.append("WITNESS_INCARNATION_CHANGED")
    if acquired["witnessNRestarts"] != snapshot["witnessNRestarts"]:
        events.append("WITNESS_RESTARTED")
    if not acquired["bootId"]:
        events.append("EVIDENCE_UNKNOWN")
    elif acquired["bootId"] != snapshot["bootId"]:
        events.append("BOOT_ID_CHANGED")
    if acquired["rebootRequired"] != "absent":
        events.append("REBOOT_REQUIRED_PRESENT" if acquired["rebootRequired"] == "present" else "EVIDENCE_UNKNOWN")
    if exported["receipt"]["control"] != opening["control"]:
        events.append("CONTROL_CHANGED")
    for name, event in (("holdStoreEmpty", "HOLD_STORE_NOT_EMPTY"), ("signerNoLaterState", "SIGNER_ACTIVE"),
                        ("authorityNotActive", "AUTHORITY_GRANTED"), ("registryNotEffective", "REGISTRY_EFFECTIVE")):
        if not checks[name]:
            events.append(event)
    for name, expected, event in (("lastDeployRunId", opening["facts"].get("lastDeployRunId"), "DEPLOY_OCCURRED"),
                                  ("s25BundleSha256", bundle_sha256, "S25_BUNDLE_MISMATCH")):
        if facts.get(name) is None or expected is None:
            events.append("EVIDENCE_UNKNOWN")
        elif facts[name] != expected:
            events.append(event)
    if facts.get("workflowQueueEmpty") is not True:
        events.append("WORKFLOW_QUEUE_NOT_EMPTY" if facts.get("workflowQueueEmpty") is False else "EVIDENCE_UNKNOWN")
    if set(facts) - set(CONTINUITY_FACTS):
        events.append("EVIDENCE_UNKNOWN")
    events = sorted(set(events))
    halt = [e for e in events if e in HALT_EVENTS]
    return {"exact": not events, "events": events, "route": "HALT" if halt else ("REVALIDATE" if events else "CONTINUE")}


def gate(workdir: Path, stage: str, export: Path, facts_path: Path, *,
         pins: PackageCPinsV1 = ACCEPTED_PINS) -> dict[str, Any]:
    workdir = Path(workdir)
    _need(stage in STAGES, "STAGE_INVALID")
    binding, binding_sha = load_binding(workdir)
    opening = _opening(workdir)
    _need(Path(export).name not in _consumed(workdir), "EXPORT_REUSED")
    gates = workdir / GATES_DIR
    gates.mkdir(mode=0o700, exist_ok=True)
    try:
        exported = check_export(workdir, export, pins)
    except Stop as stop:
        if not stop.reason.startswith("ACQUISITION_NOT_FRESH"):
            raise
        result = {"exact": False, "events": ["ACQUISITION_NOT_FRESH"], "route": "REVALIDATE"}
        exported = {"acquisition": Path(export).name, "receiptSha256": None}
    else:
        facts = _json(_read(Path(facts_path), "FACTS_ABSENT"), "FACTS_INVALID")
        _need(isinstance(facts, dict), "FACTS_INVALID")
        result = continuity(binding, exported, facts, opening, bundle_record(workdir).get("tarSha256"))
    record = {"stage": stage, "bindingSha256": binding_sha, "acquisition": exported["acquisition"],
              "acquisitionReceiptSha256": exported["receiptSha256"], **result}
    index = len(list(gates.iterdir())) + 1
    path = gates / f"{index:02d}-{stage}.json"
    _create(path, _document(record))
    return {"stage": stage, "result": "PKGC_GATE_PASS" if result["exact"] else "PKGC_GATE_" + result["route"],
            "events": result["events"], "gateSha256": sha256_hex(path.read_bytes())}


def last_gate(workdir: Path, stage: str) -> tuple[dict[str, Any], str]:
    gates = sorted((Path(workdir) / GATES_DIR).iterdir()) if (Path(workdir) / GATES_DIR).is_dir() else []
    _need(gates, "FRESH_GATE_REQUIRED")
    raw = gates[-1].read_bytes()
    record = _json(raw, "GATE_INVALID")
    _need(record["stage"] == stage and record["exact"] is True, "FRESH_GATE_REQUIRED")
    return record, sha256_hex(raw)


def _marker(workdir: Path, stage: str) -> dict[str, Any]:
    return _json(_read(Path(workdir) / ATTEMPT_DIR / f"{stage}.json", "ATTEMPT_ABSENT:" + stage), "ATTEMPT_INVALID")


# --------------------------------------------------------------- peer views ---
# Record §5. A peer view is a NON-CUSTODY, read-only comparison input to the canonical tool's peer / second replica /
# second store argument, so the tool can run where only one real copy is present. Invariants (each tested):
#   - it lives only at <workdir>/views/<kind>; the work directory is disjoint from every canonical replica and store
#     root, so a view is never at or under a canonical root;
#   - nothing discovers it: the operator takes canonical copies only from explicit paths, refuses any canonical path
#     inside the work directory, and never enumerates directories for replicas or stores;
#   - its files are made read-only, and the canonical tool writes only its target;
#   - it is bound by a provenance record (beside it, not inside) to the actual opposite-side canonical owner record:
#     the S25 transcription that proves the real copy, and the canonical source bytes it was built from;
#   - freshness and acceptance computed through the operator count a view ONLY when its provenance verifies;
#     otherwise the result is FRESHNESS_UNKNOWN / ACCEPTANCE_UNKNOWN (PEER_VIEW_NOT_PROVEN). A view never makes
#     anything current by existing.

PEER_KINDS = ("replica-b-0", "replica-b-1", "store-b-0", "store-b-1")
# kind -> the S25 transcription stage that proves the real opposite-side copy
VIEW_EVIDENCE = {"replica-b-0": "C1", "replica-b-1": "C3", "store-b-0": "C3", "store-b-1": "C4B"}


def replica_b_manifest(pins: PackageCPinsV1 = ACCEPTED_PINS) -> bytes:
    return OF.record_bytes(T._manifest(pins.replica_b_id, pins.environment, pins.authority_profile))


def store_manifest(copy_id: str, pins: PackageCPinsV1 = ACCEPTED_PINS) -> bytes:
    return OF.record_bytes({"storeType": T.ACCEPTANCE_STORE_TYPE, "schemaVersion": 1, "custodyCopyId": copy_id,
                            "environment": pins.environment, "authorityProfile": pins.authority_profile})


def tree_digest(path: Path) -> str:
    """SHA-256 over the sorted (relative path, file SHA-256) lines: one value for a whole view or copy."""
    path = Path(path)
    lines = []
    for file in path.rglob("*"):
        _need(not file.is_symlink(), "VIEW_SYMLINK")
        if file.is_file():
            lines.append(f"{file.relative_to(path).as_posix()}={sha256_hex(file.read_bytes())}\n")
    return sha256_hex("".join(sorted(lines)).encode())


def _s25_exact(workdir: Path, stage: str) -> str:
    path = Path(workdir) / "s25" / f"{stage}.json"
    raw = _read(path, "S25_TRANSCRIPTION_ABSENT:" + stage)
    _need(_json(raw, "S25_TRANSCRIPTION_INVALID")["exact"] is True, "S25_TRANSCRIPTION_NOT_EXACT:" + stage)
    return sha256_hex(raw)


def _make_read_only(path: Path) -> None:
    for item in sorted(path.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        os.chmod(item, 0o500 if item.is_dir() else 0o400)
    os.chmod(path, 0o500)


def peer_view(workdir: Path, kind: str, source: Path | None = None, *,
              pins: PackageCPinsV1 = ACCEPTED_PINS) -> dict[str, Any]:
    _need(kind in PEER_KINDS, "VIEW_KIND_INVALID")
    workdir = Path(workdir)
    load_binding(workdir)
    _need(not _under_custody_root(workdir), "WORKDIR_UNDER_CUSTODY_ROOT")
    views = workdir / VIEWS_DIR
    views.mkdir(mode=0o700, exist_ok=True)
    out = views / kind
    _need(not os.path.lexists(out) and not os.path.lexists(views / f"{kind}.provenance.json"), "VIEW_EXISTS")
    evidence = {"s25Stage": VIEW_EVIDENCE[kind], "s25RecordSha256": _s25_exact(workdir, VIEW_EVIDENCE[kind])}
    provenance: dict[str, Any] = {"kind": kind, "custody": "NON_CUSTODY_PEER_VIEW", "readOnly": True}
    if kind.startswith("replica-b"):
        manifest = replica_b_manifest(pins)
        _need(sha256_hex(manifest) == pins.replica_b_manifest_sha256, "REPLICA_B_MANIFEST_NOT_ACCEPTED")
        records: list[tuple[str, bytes]] = []
        if kind == "replica-b-1":
            _disjoint(workdir, Path(source), "CANONICAL_COPY_INSIDE_WORKDIR")
            digest = _record_1(Path(source), pins)
            _need(digest == _marker(workdir, "C2")["values"]["record"], "SOURCE_NOT_THE_C2_RECORD")
            replica = T.load_replica(Path(source))
            records.append((f"000001-{digest}.json", OF.record_bytes(replica.records[0])))
            provenance |= {"recordDigest": digest, "sourceTreeSha256": tree_digest(Path(source))}
        out.mkdir(mode=0o700)
        _create(out / T.MANIFEST, manifest)
        (out / T.RECORDS).mkdir(mode=0o700)
        for name, data in records:
            _create(out / T.RECORDS / name, data)
        _need(T.load_replica(out).replica_id == pins.replica_b_id, "VIEW_INVALID")
        provenance |= {"standsFor": "REPLICA_B", "replicaId": pins.replica_b_id,
                       "manifestSha256": pins.replica_b_manifest_sha256, "records": [n for n, _ in records]}
    else:
        bundles: list[tuple[str, bytes]] = []
        if kind == "store-b-1":
            _disjoint(workdir, Path(source), "CANONICAL_COPY_INSIDE_WORKDIR")
            store = T.load_acceptance_store(Path(source))
            _need(store.custody_copy_id == pins.replica_a_id and len(store.bundles) == 1, "SOURCE_NOT_ENVELOPE_1_ONLY")
            _need(store.digests[0] == _marker(workdir, "C4A")["values"]["envelope"], "SOURCE_NOT_THE_C4A_ENVELOPE")
            bundles.append((f"000001-{store.digests[0]}.json", OF.record_bytes(store.bundles[0])))
            provenance |= {"envelopeDigest": store.digests[0], "sourceTreeSha256": tree_digest(Path(source))}
        out.mkdir(mode=0o700)
        _create(out / T.ACCEPTANCE_MANIFEST, store_manifest(pins.replica_b_id, pins))
        (out / T.ENVELOPES).mkdir(mode=0o700)
        for name, data in bundles:
            _create(out / T.ENVELOPES / name, data)
        _need(T.load_acceptance_store(out).custody_copy_id == pins.replica_b_id, "VIEW_INVALID")
        provenance |= {"standsFor": "ACCEPTANCE_STORE_B", "custodyCopyId": pins.replica_b_id,
                       "envelopes": [n for n, _ in bundles]}
    provenance |= {"treeSha256": tree_digest(out), "evidence": evidence}
    _make_read_only(out)
    _create(views / f"{kind}.provenance.json", _document(provenance))
    return {"kind": kind, "viewSha256": provenance["treeSha256"], "result": "PKGC_PEER_VIEW_WRITTEN",
            "note": "a NON-CUSTODY read-only comparison input, never a replica or store of custody"}


def load_view(workdir: Path, kind: str) -> Path:
    """The view path, only if its provenance still verifies (tree and evidence unchanged)."""
    workdir = Path(workdir)
    out, record = workdir / VIEWS_DIR / kind, workdir / VIEWS_DIR / f"{kind}.provenance.json"
    _need(kind in PEER_KINDS and out.is_dir() and record.is_file(), "PEER_VIEW_NOT_PROVEN")
    provenance = _json(record.read_bytes(), "PEER_VIEW_NOT_PROVEN")
    _need(provenance.get("custody") == "NON_CUSTODY_PEER_VIEW" and provenance.get("treeSha256") == tree_digest(out),
          "PEER_VIEW_NOT_PROVEN")
    try:
        _need(_s25_exact(workdir, VIEW_EVIDENCE[kind]) == provenance["evidence"]["s25RecordSha256"],
              "PEER_VIEW_NOT_PROVEN")
    except Stop as exc:
        raise Stop("PEER_VIEW_NOT_PROVEN") from exc
    return out


def laptop_freshness(workdir: Path, replica_a: Path, view_kind: str) -> OF.FreshnessResultV1:
    """Freshness on the laptop: Replica A plus a PROVEN Replica B view. An unproven view is never counted."""
    workdir = Path(workdir)
    _disjoint(workdir, Path(replica_a), "CANONICAL_COPY_INSIDE_WORKDIR")
    chain = T.verify_chain(T.load_trust(workdir / BINDING_DIR / TRUST_FILE), workdir / BINDING_DIR / CHAIN_FILE,
                           _binding_env(workdir))
    try:
        view = load_view(workdir, view_kind)
    except Stop:
        return OF.FreshnessResultV1(OF.AUTHENTIC if chain.verified else OF.NOT_AUTHENTIC, OF.FRESHNESS_UNKNOWN,
                                    "PEER_VIEW_NOT_PROVEN")
    register, _ = T.load_register([Path(replica_a), view])
    binding, _ = load_binding(workdir)
    return OF.classify_presented_world(register=register, chain=chain, environment=binding["environment"],
                                       authority_profile=binding["authorityProfile"])


def laptop_acceptance(workdir: Path, replica_a: Path, store_a: Path, replica_view: str, store_view: str
                      ) -> OA.AcceptanceResultV1:
    workdir = Path(workdir)
    for canonical in (replica_a, store_a):
        _disjoint(workdir, Path(canonical), "CANONICAL_COPY_INSIDE_WORKDIR")
    try:
        rv, sv = load_view(workdir, replica_view), load_view(workdir, store_view)
    except Stop:
        return OA.AcceptanceResultV1(OA.ACCEPTANCE_UNKNOWN, "PEER_VIEW_NOT_PROVEN")
    result = T.classify_acceptance_state([Path(replica_a), rv], [Path(store_a), sv],
                                         Path(workdir) / BINDING_DIR / PIN_FILE)
    return OA.AcceptanceResultV1(result["state"], result.get("reason"), result.get("detail"),
                                 result.get("evidencedRecordVersion") or 0)


def _binding_env(workdir: Path) -> str:
    return load_binding(workdir)[0]["environment"]


# -------------------------------------------------------- S25 transcription ---
# Record §8.4. The S25 prints these lines (`pkgc_s25_phone.sh`); the owner reads them off the screen. Evidence class:
# OWNER_SCREEN_TRANSCRIPTION (not machine-captured).

S25_STAGES = ("C1", "C3", "C4B_PRE", "C4B")


def s25_expect(stage: str, *, record_digest: str | None = None, envelope_digest: str | None = None,
               bundle_sha256: str | None = None, a_view: str | None = None, store_view: str | None = None,
               pins: PackageCPinsV1 = ACCEPTED_PINS) -> list[str]:
    _need(stage in S25_STAGES, "STAGE_INVALID")
    _need(isinstance(bundle_sha256, str) and _HEX64.fullmatch(bundle_sha256) is not None, "BUNDLE_UNKNOWN")
    common = [f"PKGC_S25_STAGE={stage}", f"BUNDLE_SHA256={bundle_sha256}", "BUNDLE_VERIFIED",
              "CRYPTOGRAPHY_ED25519_SELFTEST=PASS", f"PB_PIN_SHA256={pins.pin_sha256}",
              f"PB_REGISTER_SHA256={pins.register_sha256}", f"PB_PIN_RECORD_SHA256={pins.pin_record_sha256}",
              "CHAIN_AUTHENTICITY=AUTHENTIC", "CHAIN_ENTRIES=1", f"CHAIN_GENESIS={pins.genesis_digest}",
              f"REPLICA_B_MANIFEST_SHA256={pins.replica_b_manifest_sha256}"]
    if stage == "C1":
        return common + ["REPLICA_B_RECORDS=0", "REPLICA_B_HEAD=null", "ACCEPTANCE_STORE_B=ABSENT"]
    _need(isinstance(record_digest, str) and _HEX64.fullmatch(record_digest) is not None, "RECORD_UNKNOWN")
    _need(isinstance(a_view, str) and _HEX64.fullmatch(a_view) is not None, "A_VIEW_UNKNOWN")
    common.append(f"A_VIEW_TREE_SHA256={a_view}")
    if stage == "C3":
        return common + ["APPEND=RECORD_APPENDED", "REPLICATION=REPLICAS_IDENTICAL", f"RECORD_DIGEST={record_digest}",
                         "REPLICA_B_RECORDS=1", f"REPLICA_B_HEAD={record_digest}",
                         f"REPLICA_B_FILE=000001-{record_digest}.json", "COMPARE=OWNER_REGISTER_VERIFIED",
                         "FRESHNESS=AUTHENTIC:CURRENT", "ACCEPTANCE_STORE_B=ABSENT"]
    if stage == "C4B_PRE":
        return common + ["REPLICA_B_RECORDS=1", f"REPLICA_B_HEAD={record_digest}", "FRESHNESS=AUTHENTIC:CURRENT",
                         "ACCEPTANCE_STORE_B=ABSENT"]
    _need(isinstance(envelope_digest, str) and _HEX64.fullmatch(envelope_digest) is not None, "ENVELOPE_UNKNOWN")
    _need(isinstance(store_view, str) and _HEX64.fullmatch(store_view) is not None, "STORE_VIEW_UNKNOWN")
    return common + [f"A_STORE_VIEW_TREE_SHA256={store_view}", "REPLICA_B_RECORDS=1",
                     f"REPLICA_B_HEAD={record_digest}", "FRESHNESS=AUTHENTIC:CURRENT",
                     "STORE_B=ACCEPTANCE_STORE_INITIALIZED",
                     f"STORE_B_MANIFEST_SHA256={sha256_hex(store_manifest(pins.replica_b_id, pins))}",
                     "APPEND_ENVELOPE=ENVELOPE_APPENDED", "REPLICATION=COPIES_IDENTICAL",
                     f"ENVELOPE_DIGEST={envelope_digest}", "ACCEPTANCE=ACCEPTANCE_COMPLETE"]


def result_block_sha256(lines: Sequence[str]) -> str:
    """The phone prints this over its result lines (each + LF): a transcription error check, not an authenticator."""
    return sha256_hex("".join(line + "\n" for line in lines).encode("utf-8"))


def s25_check(expected: Sequence[str], transcription: str) -> dict[str, Any]:
    """Exact, ordered equality with the expectation, then the phone's block hash over exactly those lines."""
    lines = [line.strip() for line in transcription.splitlines() if line.strip()]
    block = lines[:-1] if lines and lines[-1].startswith("RESULT_BLOCK_SHA256=") else lines
    missing = [line for line in expected if line not in block]
    extra = [line for line in block if line not in expected]
    hashed = bool(lines) and lines[-1] == "RESULT_BLOCK_SHA256=" + result_block_sha256(expected)
    exact = block == list(expected) and hashed
    return {"exact": exact, "missing": missing, "unexpected": extra, "evidenceClass": "OWNER_SCREEN_TRANSCRIPTION",
            "result": "PKGC_S25_TRANSCRIPTION_EXACT" if exact else "PKGC_S25_TRANSCRIPTION_MISMATCH"}


def s25_expected(workdir: Path, stage: str, paths: Mapping[str, str], *,
                 pins: PackageCPinsV1 = ACCEPTED_PINS) -> list[str]:
    """The expectation from the work directory: the bundle record, Replica A's record 1, store A's envelope."""
    values: dict[str, Any] = {"bundle_sha256": bundle_record(workdir).get("tarSha256")}
    if stage in ("C3", "C4B_PRE", "C4B"):
        values["record_digest"] = _record_1(Path(paths["replicaA"]), pins)
        values["a_view"] = tree_digest(Path(paths["replicaA"]))
    if stage == "C4B":
        store = T.load_acceptance_store(Path(paths["storeA"]))
        _need(len(store.bundles) == 1, "STORE_A_NOT_ENVELOPE_1_ONLY")
        values["envelope_digest"] = store.digests[0]
        values["store_view"] = tree_digest(Path(paths["storeA"]))
    return s25_expect(stage, pins=pins, **values)


def s25_record(workdir: Path, stage: str, paths: Mapping[str, str], transcription: bytes, *,
               pins: PackageCPinsV1 = ACCEPTED_PINS) -> dict[str, Any]:
    """Compare one owner transcription and record it create-only (one per stage; a mismatch is recorded too). The
    C4B_PRE read is bound to the C4B gate it follows."""
    result = s25_check(s25_expected(workdir, stage, paths, pins=pins), transcription.decode("utf-8"))
    after_gate = last_gate(workdir, "C4B")[1] if stage == "C4B_PRE" else None
    directory = Path(workdir) / "s25"
    directory.mkdir(mode=0o700, exist_ok=True)
    try:
        _create(directory / f"{stage}.json", _document({**result, "stage": stage, "afterGateSha256": after_gate,
                                                        "transcriptionSha256": sha256_hex(transcription)}))
    except FileExistsError as exc:
        raise Stop("TRANSCRIPTION_ALREADY_RECORDED:" + stage) from exc
    return result


# --------------------------------------------------------------- S25 bundle ---
# Record §8.2. Exactly the reviewed import closure of the canonical tool at the control, the pure-Python vendor
# set, the bound canonical inputs and the phone script. `cryptography` is native: it must already be installed in
# Termux (gate G0). Deterministic: sorted names, mtime 0, owner 0:0.

S25_CLOSURE = (
    "services/core-api/lilith_memory/__init__.py",
    "services/core-api/lilith_memory/canonical_contracts.py",
    "services/core-api/lilith_memory/owner_proof.py",
    "services/owner-memory-control/lilith_owner_memory/__init__.py",
    "services/owner-memory-control/lilith_owner_memory/authority_contracts.py",
    "services/owner-memory-control/lilith_owner_memory/authority_verifier.py",
    "services/owner-memory-control/lilith_owner_memory/burned_identities.py",
    "services/owner-memory-control/lilith_owner_memory/contracts.py",
    "services/owner-memory-control/lilith_owner_memory/create_only_publish.py",
    "services/owner-memory-control/lilith_owner_memory/owner_acceptance.py",
    "services/owner-memory-control/lilith_owner_memory/owner_freshness.py",
    "services/owner-memory-control/lilith_owner_memory/owner_freshness_tool.py",
    "services/owner-memory-control/lilith_owner_memory/recovery_contracts.py",
    "services/owner-memory-control/lilith_owner_memory/rotation_contracts.py",
    "services/owner-memory-control/lilith_owner_memory/witness_readiness.py",
)
PHONE_SCRIPT = "services/owner-memory-control/tools/pkgc_s25_phone.sh"
VENDOR_TOPS = ("fido2", "fido2-2.2.1.dist-info", "rfc8785", "rfc8785-0.1.4.dist-info")
BUNDLE_FILE = "S25_BUNDLE.json"


def bundle_record(workdir: Path) -> dict[str, Any]:
    path = Path(workdir) / BUNDLE_FILE
    return _json(_read(path, "S25_BUNDLE_UNKNOWN"), "S25_BUNDLE_INVALID") if path.exists() else {}


def s25_bundle_members(repo: Path, commit: str, vendor_dir: Path, binding_dir: Path) -> dict[str, bytes]:
    _need(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "COMMIT_NOT_40_HEX")
    _need(sorted(p.name for p in Path(vendor_dir).iterdir()) == sorted(VENDOR_TOPS), "VENDOR_SET_MISMATCH")

    def show(path: str) -> bytes:
        return subprocess.run(["git", "-C", str(repo), "show", f"{commit}:{path}"], check=True,
                              capture_output=True).stdout

    members = {"src/" + path.removeprefix("services/"): show(path) for path in S25_CLOSURE}
    _need(sha256_hex(show(FRESHNESS_TOOL)) == TOOL_PINS[FRESHNESS_TOOL], "TOOL_PIN_MISMATCH:" + FRESHNESS_TOOL)
    members["pkgc_s25_phone.sh"] = show(PHONE_SCRIPT)
    for file in sorted(Path(vendor_dir).rglob("*")):
        _need(not file.is_symlink(), "VENDOR_SYMLINK")
        if file.is_file() and "__pycache__" not in file.parts and not file.name.endswith(".pyc"):
            members["vendor/" + file.relative_to(vendor_dir).as_posix()] = file.read_bytes()
    for name in (TRUST_FILE, CHAIN_FILE, PIN_FILE, BINDING_FILE):
        members["binding/" + name] = _read(Path(binding_dir) / name, "BINDING_INEXACT")
    members["SOURCE_COMMIT"] = (commit + "\n").encode("ascii")
    return members


def bundle_tar(members: Mapping[str, bytes], top: str) -> bytes:
    import io
    import tarfile
    members = dict(members)
    members["SHA256SUMS"] = "".join(f"{sha256_hex(data)}  {name}\n"
                                    for name, data in sorted(members.items())).encode("ascii")
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        directories = {top}
        for name in members:
            parts = name.split("/")
            directories.update(f"{top}/{'/'.join(parts[:i])}" for i in range(1, len(parts)))
        for name in sorted(directories):
            info = tarfile.TarInfo(name)
            info.type, info.mode, info.mtime, info.uid, info.gid = tarfile.DIRTYPE, 0o755, 0, 0, 0
            info.uname = info.gname = ""
            tar.addfile(info)
        for name in sorted(members):
            info = tarfile.TarInfo(f"{top}/{name}")
            info.size, info.mode, info.mtime, info.uid, info.gid = len(members[name]), 0o644, 0, 0, 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(members[name]))
    return buffer.getvalue()


TRANSFERS = ("replica-a", "store-a")


def build_transfer(workdir: Path, kind: str, paths: Mapping[str, str], out: Path, *,
                   pins: PackageCPinsV1 = ACCEPTED_PINS) -> dict[str, Any]:
    """T2 / T3 (record §8.2): a deterministic tar of exactly the NON-CUSTODY view the S25 needs: a byte copy of
    Replica A after C2 (`replica-a`), or of store A after C4A plus the review package (`store-a`)."""
    _need(kind in TRANSFERS, "TRANSFER_KIND_INVALID")
    workdir = Path(workdir)
    load_binding(workdir)
    directory = workdir / "transfers"
    directory.mkdir(mode=0o700, exist_ok=True)
    _need(not (directory / f"{kind}.json").exists() and not os.path.lexists(out), "TRANSFER_EXISTS")
    if kind == "replica-a":
        source = Path(paths["replicaA"])
        _disjoint(workdir, source, "CANONICAL_COPY_INSIDE_WORKDIR")
        digest = _record_1(source, pins)
        _need(digest == _marker(workdir, "C2")["values"]["record"], "SOURCE_NOT_THE_C2_RECORD")
        members = {f"replica-a/{p.relative_to(source).as_posix()}": p.read_bytes()
                   for p in sorted(source.rglob("*")) if p.is_file()}
        bound = {"recordDigest": digest}
    else:
        source = Path(paths["storeA"])
        _disjoint(workdir, source, "CANONICAL_COPY_INSIDE_WORKDIR")
        store = T.load_acceptance_store(source)
        _need(store.custody_copy_id == pins.replica_a_id and len(store.bundles) == 1, "STORE_A_NOT_ENVELOPE_1_ONLY")
        _need(store.digests[0] == _marker(workdir, "C4A")["values"]["envelope"], "SOURCE_NOT_THE_C4A_ENVELOPE")
        members = {f"store-a/{p.relative_to(source).as_posix()}": p.read_bytes()
                   for p in sorted(source.rglob("*")) if p.is_file()}
        package = _read(Path(paths["package"]), "PACKAGE_ABSENT")
        _need(OA.review_package_digest(_json(package, "PACKAGE_INVALID"))
              == store.bundles[0]["envelope"]["ownerReviewPackageDigest"], "PACKAGE_NOT_BOUND")
        members["package.json"] = package
        bound = {"envelopeDigest": store.digests[0]}
    raw = bundle_tar(members, f"lilith-pkgc-{kind}")
    _create(Path(out), raw)
    record = {"kind": kind, "custody": "NON_CUSTODY_PEER_VIEW", "tarSha256": sha256_hex(raw),
              "treeSha256": tree_digest(source), **bound}
    _create(directory / f"{kind}.json", _document(record))
    return {"result": "PKGC_TRANSFER_BUILT", **record}


def build_s25_bundle(repo: Path, workdir: Path, vendor_dir: Path, out: Path) -> dict[str, Any]:
    workdir = Path(workdir)
    opening = _opening(workdir)
    load_binding(workdir)
    _need(not (workdir / BUNDLE_FILE).exists() and not os.path.lexists(out), "S25_BUNDLE_EXISTS")
    commit = opening["control"]
    members = s25_bundle_members(repo, commit, vendor_dir, workdir / BINDING_DIR)
    raw = bundle_tar(members, f"lilith-pkgc-{commit[:7]}")
    _create(Path(out), raw)
    record = {"tarSha256": sha256_hex(raw), "top": f"lilith-pkgc-{commit[:7]}", "sourceCommit": commit,
              "files": len(members) + 1}
    _create(workdir / BUNDLE_FILE, _document(record))
    return {"result": "PKGC_S25_BUNDLE_BUILT", **record}


# --------------------------------------------------------------- owner acts ---

def open_sequence(workdir: Path, statement: str, *, control: str, operator: str, freshness_tool: str,
                  facts: Mapping[str, Any], pins: PackageCPinsV1 = ACCEPTED_PINS,
                  now: Callable[[], str] | None = None) -> dict[str, Any]:
    check_text(statement, C1_LINES, control=control, operator=operator, freshness_tool=freshness_tool,
               genesis=pins.genesis_digest, chain1=pins.chain_1_sha256)
    _need(set(facts) == set(OPENING_FACTS) and facts.get("control") == control, "OPENING_FACTS_INEXACT")
    _need(not _under_custody_root(Path(workdir).parent), "WORKDIR_UNDER_CUSTODY_ROOT")
    workdir = _new_dir(Path(workdir))
    (workdir / EXPORTS_DIR).mkdir(mode=0o700)
    record = {"act": "C1", "sequenceId": os.urandom(16).hex(), "openedAt": (now or _utc_now)(),
              "statementSha256": sha256_hex(statement.encode("utf-8")), "statement": statement,
              "control": control, "operator": operator, "freshnessTool": freshness_tool, "facts": dict(facts)}
    _create(workdir / C1_FILE, _document(record))
    return {"result": "PKGC_SEQUENCE_OPENED_READ_ONLY", "sequenceId": record["sequenceId"],
            "c1Sha256": sha256_hex((workdir / C1_FILE).read_bytes())}


def _record_1(replica_a: Path, pins: PackageCPinsV1) -> str:
    replica = T.load_replica(Path(replica_a))
    _need(replica.replica_id == pins.replica_a_id and len(replica.records) == 1, "REPLICA_A_NOT_RECORD_1_ONLY")
    record = replica.records[0]
    _need(record["recordVersion"] == 1 and record["genesisWitnessDigest"] == pins.genesis_digest
          and record["witnessDigest"] == pins.genesis_digest and record["decision"] == OF.ACCEPT_CURRENT,
          "RECORD_1_NOT_BOUND_TO_GENESIS")
    return replica.digests[0]


def _package(path: Path, record_digest: str, binding: Mapping[str, Any]) -> str:
    package = _json(_read(Path(path), "PACKAGE_ABSENT"), "PACKAGE_INVALID")
    _need(isinstance(package, dict) and package.get("packageKind") == OA.RECORD_1
          and package.get("candidateRecordDigest") == record_digest
          and package.get("attachedEvidence") == binding["attachedEvidence"], "PACKAGE_NOT_BOUND")
    return OA.review_package_digest(package)


def _transfer(workdir: Path, kind: str, source: Path) -> str:
    record = _json(_read(Path(workdir) / "transfers" / f"{kind}.json", "TRANSFER_ABSENT:" + kind), "TRANSFER_INVALID")
    _need(record["treeSha256"] == tree_digest(source), "TRANSFER_NOT_THE_CURRENT_COPY:" + kind)
    return record["treeSha256"]


def c4b_eligibility(workdir: Path, paths: Mapping[str, str], *, pins: PackageCPinsV1 = ACCEPTED_PINS
                    ) -> dict[str, Any]:
    """The fresh read C4B needs (record §2): after the last exact C4B gate, (1) the S25 C4B_PRE transcription read
    after that gate proves copy B absent and Replica B = record 1 CURRENT; (2) store A is exactly envelope 1 of
    the C4A go; (3) the laptop classifies exactly ACCEPTANCE_PARTIAL and CURRENT through PROVEN views."""
    workdir = Path(workdir)
    _need(not (workdir / C4B_ELIGIBILITY_FILE).exists(), "C4B_ELIGIBILITY_EXISTS")
    _, gate_sha = last_gate(workdir, "C4B")
    pre = _json(_read(workdir / "s25" / "C4B_PRE.json", "S25_TRANSCRIPTION_ABSENT:C4B_PRE"), "S25_INVALID")
    replica_a, store_a = Path(paths["replicaA"]), Path(paths["storeA"])
    store = T.load_acceptance_store(store_a)
    envelope = _marker(workdir, "C4A")["values"]["envelope"]
    freshness = laptop_freshness(workdir, replica_a, "replica-b-1")
    acceptance = laptop_acceptance(workdir, replica_a, store_a, "replica-b-1", "store-b-0")
    checks = {
        "c4bPreAfterThisGate": pre.get("afterGateSha256") == gate_sha,
        "copyBAbsent": pre.get("exact") is True,
        "copyAExact": store.custody_copy_id == pins.replica_a_id and store.digests == (envelope,),
        "acceptancePartial": acceptance.state == OA.ACCEPTANCE_PARTIAL,
        "freshnessCurrent": freshness.current,
    }
    _need(all(checks.values()), "C4B_NOT_ELIGIBLE:" + ",".join(k for k, v in checks.items() if not v))
    record = {"gateSha256": gate_sha, "envelopeDigest": envelope, "storeATreeSha256": tree_digest(store_a),
              "acceptance": acceptance.state, "freshness": f"{freshness.authenticity}:{freshness.freshness}",
              "checks": checks}
    _create(workdir / C4B_ELIGIBILITY_FILE, _document(record))
    return {"result": "PKGC_C4B_ELIGIBLE", "eligibilitySha256": sha256_hex((workdir / C4B_ELIGIBILITY_FILE)
                                                                           .read_bytes()), **record}


def derive_values(workdir: Path, stage: str, paths: Mapping[str, str], *,
                  pins: PackageCPinsV1 = ACCEPTED_PINS) -> dict[str, str]:
    """Every value a go or acceptance text binds, computed from the files themselves: never typed in."""
    workdir = Path(workdir)
    binding, _ = load_binding(workdir)
    opening = _opening(workdir)
    values = {"control": opening["control"], "genesis": pins.genesis_digest}
    if stage == "C2":
        record, digest = T.load_candidate(Path(paths["candidate"]))
        _need(record["recordVersion"] == 1 and record["genesisWitnessDigest"] == pins.genesis_digest
              and record["previousRecordDigest"] is None and record["decision"] == OF.ACCEPT_CURRENT,
              "CANDIDATE_NOT_RECORD_1")
        _disjoint(workdir, Path(paths["replicaA"]), "CANONICAL_COPY_INSIDE_WORKDIR")
        view = load_view(workdir, "replica-b-0")
        values |= {"record": digest, "package": _package(Path(paths["package"]), digest, binding),
                   "view": tree_digest(view), "replica_a": str(paths["replicaA"])}
    elif stage == "C3":
        digest = _record_1(Path(paths["replicaA"]), pins)
        _need(digest == _marker(workdir, "C2")["values"]["record"], "RECORD_NOT_THE_C2_RECORD")
        values |= {"record": digest, "view": _transfer(workdir, "replica-a", Path(paths["replicaA"])),
                   "replica_b": paths["replicaBPath"], "bundle": bundle_record(workdir)["tarSha256"]}
    elif stage == "C4A":
        digest = _record_1(Path(paths["replicaA"]), pins)
        candidate = _json(_read(Path(paths["envelopeCandidate"]), "ENVELOPE_CANDIDATE_ABSENT"), "ENVELOPE_INVALID")
        envelope = candidate.get("envelope") if isinstance(candidate, dict) else None
        package = _package(Path(paths["package"]), digest, binding)
        _need(isinstance(envelope, dict) and envelope.get("freshnessRecordDigest") == digest
              and envelope.get("freshnessRecordVersion") == 1
              and envelope.get("previousAcceptanceEnvelopeDigest") is None
              and envelope.get("ownerReviewPackageDigest") == package
              and candidate.get("envelopeDigest") == OA.envelope_digest(envelope), "ENVELOPE_NOT_BOUND")
        _disjoint(workdir, Path(paths["storeAPath"]), "CANONICAL_COPY_INSIDE_WORKDIR")
        _need(not os.path.lexists(paths["storeAPath"]), "STORE_A_EXISTS")
        values |= {"record": digest, "envelope": candidate["envelopeDigest"], "package": package,
                   "store_a": str(paths["storeAPath"]), "view": tree_digest(load_view(workdir, "store-b-0"))}
    elif stage == "C4B":
        digest = _record_1(Path(paths["replicaA"]), pins)
        raw = _read(workdir / C4B_ELIGIBILITY_FILE, "C4B_NOT_ELIGIBLE")
        eligibility = _json(raw, "C4B_NOT_ELIGIBLE")
        _need(eligibility["gateSha256"] == last_gate(workdir, "C4B")[1], "C4B_ELIGIBILITY_NOT_FOR_THIS_GATE")
        store_view = _transfer(workdir, "store-a", Path(paths["storeA"]))
        _need(store_view == eligibility["storeATreeSha256"], "STORE_A_CHANGED_SINCE_ELIGIBILITY")
        values |= {"record": digest, "envelope": eligibility["envelopeDigest"], "eligibility": sha256_hex(raw),
                   "store_view": store_view, "bundle": bundle_record(workdir)["tarSha256"]}
    elif stage == "C5":
        digest = _record_1(Path(paths["replicaA"]), pins)
        store = T.load_acceptance_store(Path(paths["storeA"]))
        _need(store.custody_copy_id == pins.replica_a_id and len(store.bundles) == 1
              and store.bundles[0]["envelope"]["freshnessRecordDigest"] == digest, "STORE_A_NOT_ENVELOPE_1_ONLY")
        values |= {"record": digest, "envelope": store.digests[0]}
    else:
        raise Stop("STAGE_INVALID")
    return values


def arm(workdir: Path, stage: str, go_text: str, paths: Mapping[str, str], *,
        pins: PackageCPinsV1 = ACCEPTED_PINS) -> dict[str, Any]:
    """Check one go against its template (values derived from the files) and the last exact gate, then write its
    one-attempt marker. The commands the owner then runs are the canonical tool's; this writes no owner record."""
    _need(stage in ARMABLE, "STAGE_INVALID")
    workdir = Path(workdir)
    _need(not (workdir / "STOP.json").exists(), "SEQUENCE_STOPPED")
    previous = ARMABLE[:ARMABLE.index(stage)]
    _need(all((workdir / ATTEMPT_DIR / f"{s}.json").is_file() for s in previous), "TRANSITION_OUT_OF_ORDER")
    _, binding_sha = load_binding(workdir)
    gate_record, gate_sha = last_gate(workdir, stage)
    _need(gate_record["bindingSha256"] == binding_sha, "GATE_NOT_FOR_THIS_BINDING")
    values = derive_values(workdir, stage, paths, pins=pins)
    check_text(go_text, TEMPLATES[stage], binding=binding_sha, gate=gate_sha, **values)
    directory = workdir / ATTEMPT_DIR
    directory.mkdir(mode=0o700, exist_ok=True)
    marker = directory / f"{stage}.json"
    try:
        _create(marker, _document({"attempt": stage, "bootstrapStep": BOOTSTRAP_STEP[stage],
                                   "goSha256": sha256_hex(go_text.encode("utf-8")), "gateSha256": gate_sha,
                                   "bindingSha256": binding_sha, "values": values}))
    except FileExistsError as exc:
        raise Stop("ATTEMPT_ALREADY_CONSUMED:" + stage) from exc
    return {"result": "PKGC_ARMED", "stage": stage, "bootstrapStep": BOOTSTRAP_STEP[stage], "marker": marker.name,
            "values": values,
            "note": "the marker consumes this go; run the canonical commands exactly once; no automatic retry"}


def record_act(workdir: Path, act: str, statement: str, paths: Mapping[str, str], *,
               pins: PackageCPinsV1 = ACCEPTED_PINS) -> dict[str, Any]:
    _need(act in ("C5", "STOP"), "ACT_INVALID")
    workdir = Path(workdir)
    if act == "STOP":
        _need(not (workdir / ATTEMPT_DIR).exists(), "STOP_REFUSED_ATTEMPT_MARKER_PRESENT")
        values = {"control": _opening(workdir)["control"], "c1": sha256_hex((workdir / C1_FILE).read_bytes())}
    else:
        _need(all((workdir / ATTEMPT_DIR / f"{s}.json").is_file() for s in ARMABLE), "C5_BEFORE_C2_C3_C4A_C4B")
        last_gate(workdir, "C5")
        values = derive_values(workdir, "C5", paths, pins=pins) | {"binding": load_binding(workdir)[1]}
    check_text(statement, TEMPLATES[act], **values)
    target = workdir / ("C5_ACCEPTANCE.json" if act == "C5" else "STOP.json")
    try:
        _create(target, _document({"act": act, "statementSha256": sha256_hex(statement.encode("utf-8")),
                                   "statement": statement}))
    except FileExistsError as exc:
        raise Stop("ACT_ALREADY_RECORDED:" + act) from exc
    return {"result": "PKGC_PACKAGE_C_ACCEPTED" if act == "C5" else "PKGC_SEQUENCE_STOPPED",
            "authorityBoundary": dict(AUTHORITY_BOUNDARY)}


def check_pins(repo: Path) -> dict[str, str]:
    """Local, read-only: a clean checkout whose HEAD is the control, every pinned tool exact at HEAD, and this
    operator equal to its HEAD bytes."""
    def git(*args: str) -> bytes:
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout

    _need(git("status", "--porcelain", "--untracked-files=no") == b"", "CHECKOUT_NOT_CLEAN")
    control = git("rev-parse", "HEAD").decode().strip()
    for path, pin in TOOL_PINS.items():
        _need(sha256_hex(git("show", f"HEAD:{path}")) == pin, "TOOL_PIN_MISMATCH:" + path)
    operator = sha256_hex(git("show", f"HEAD:{OPERATOR}"))
    _need(operator == sha256_hex(Path(__file__).read_bytes()), "OPERATOR_NOT_AT_CONTROL")
    return {"control": control, "operator": operator, "freshnessTool": TOOL_PINS[FRESHNESS_TOOL],
            "result": "PKGC_TOOL_PINS_EXACT"}


# ---------------------------------------------------------------------- CLI ---

def main(argv: Sequence[str]) -> int:
    argv = list(argv)
    try:
        if len(argv) == 2 and argv[0] == "pins":
            result = check_pins(Path(argv[1]))
        elif len(argv) == 5 and argv[0] == "open":
            pinned = check_pins(Path(argv[1]))
            facts = _json(_read(Path(argv[4]), "FACTS_ABSENT"), "FACTS_INVALID")
            result = open_sequence(Path(argv[2]), _read(Path(argv[3]), "STATEMENT_ABSENT").decode("utf-8"),
                                   control=pinned["control"], operator=pinned["operator"],
                                   freshness_tool=pinned["freshnessTool"], facts=facts)
        elif len(argv) == 4 and argv[0] == "acquire":
            result = acquire(Path(argv[1]), Path(argv[2]), Path(argv[3]))
        elif len(argv) == 5 and argv[0] in ("arm", "record"):
            text = _read(Path(argv[3]), "STATEMENT_ABSENT").decode("utf-8")
            paths = _json(_read(Path(argv[4]), "PATHS_ABSENT"), "PATHS_INVALID")
            act = arm if argv[0] == "arm" else record_act
            result = act(Path(argv[1]), argv[2], text, paths)
        elif len(argv) == 8 and argv[0] == "bind":
            result = bind(*(Path(a) for a in argv[1:6]), argv[6], argv[7])
        elif len(argv) == 5 and argv[0] == "gate":
            result = gate(Path(argv[1]), argv[2], Path(argv[3]), Path(argv[4]))
        elif len(argv) in (3, 4) and argv[0] == "peer-view":
            result = peer_view(Path(argv[1]), argv[2], Path(argv[3]) if len(argv) == 4 else None)
        elif len(argv) == 3 and argv[0] == "c4b-eligibility":
            result = c4b_eligibility(Path(argv[1]), _json(_read(Path(argv[2]), "PATHS_ABSENT"), "PATHS_INVALID"))
        elif len(argv) == 4 and argv[0] == "s25-expect":
            paths = _json(_read(Path(argv[3]), "PATHS_ABSENT"), "PATHS_INVALID")
            result = {"lines": s25_expected(Path(argv[1]), argv[2], paths)}
        elif len(argv) == 5 and argv[0] == "s25-check":
            paths = _json(_read(Path(argv[3]), "PATHS_ABSENT"), "PATHS_INVALID")
            result = s25_record(Path(argv[1]), argv[2], paths, _read(Path(argv[4]), "TRANSCRIPTION_ABSENT"))
        elif len(argv) == 5 and argv[0] == "transfer":
            paths = _json(_read(Path(argv[3]), "PATHS_ABSENT"), "PATHS_INVALID")
            result = build_transfer(Path(argv[1]), argv[2], paths, Path(argv[4]))
        elif len(argv) == 5 and argv[0] == "s25-bundle":
            result = build_s25_bundle(Path(argv[1]), Path(argv[2]), Path(argv[3]), Path(argv[4]))
        else:
            raise Stop("USAGE")
    except Stop as exc:
        print(f"pkgc_operator: STOP {exc.reason}", file=sys.stderr)
        return 2
    except T.ToolRefusal as exc:
        print(f"pkgc_operator: STOP {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(result, sort_keys=True, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
