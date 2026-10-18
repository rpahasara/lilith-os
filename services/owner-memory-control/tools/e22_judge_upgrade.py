#!/usr/bin/env python3
"""15B2b-B1b-3e M-B12: the PROPOSED `UPGRADE_E22_JUDGE_DEV_SYNTHETIC` one-member release contract (SOURCE ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-e22-judge-transition.md.
DESIGN / SOURCE ONLY. Nothing here builds, stages, selects or retires a release, stops or starts a unit, loads K-ACT
or K-WIT, changes custody, HELD or the ledger, or activates authority. Owner workstation, stdlib only; it reads local
files, writes nothing and contacts nothing.

It reuses the accepted E-19 contract (`e19_p1b10_upgrade`): the installed release is the E-19 NEW release `ba943e1`, and
the transition replaces it by a NEW release whose payload differs from it in exactly
`lilith_owner_memory/pr1_acceptance.py` (the OD-M12-10 judge), with units and CLIs byte-identical. Unlike E-19 the
signer is RUNNING (M-B11), and both the signer (`lilith_authority_dev.recovery`) and the witness
(`lilith_recovery_witness.core`) import that module and run from `current`. Neither may run across a selector change
or from a retired tree, so both stop before the select and start again from NEW:

    V0 W11 exact              1 release (OLD), current -> OLD, signer + witness running from OLD (accepted W11 / POST11)
    V1 NEW staged             2 releases, current -> OLD, the same two incarnations                (staging exception)
    V2 signer stopped         2 releases, current -> OLD, signer service + socket inactive; witness running
    V3 witness stopped        2 releases, current -> OLD, signer and witness (service + both sockets) inactive
    V4 NEW selected           2 releases, current -> NEW, signer and witness stopped
    V5 witness running        2 releases, current -> NEW, ONE new witness incarnation (one K-WIT load) from NEW
    V6 signer running         2 releases, current -> NEW, ONE new signer incarnation (one K-ACT load, the second) from NEW
    V7 OLD retired            1 release (NEW), both accepted replacement incarnations running from NEW

OD-M12-11 (owner-accepted 2026-10-18, record §2) binds the two load events (V5, V6): each records its own window and
retains its transcript; the post-transition `journal` and `attribute` reads follow the last of them, in the same boot,
and must show exactly the historical 12 attributed matches (the OD-M12-10 admission). The loads never inherit the
OD-M12-10 risk acceptance.

    restart != preservation;  one start go != one credential load (counted, never inferred)
    technical phase != owner acceptance;  NEW is unpinned until a merged owner record names the attested build
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Mapping

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import e19_p1b10_upgrade as E19  # noqa: E402

MODE = "UPGRADE_E22_JUDGE_DEV_SYNTHETIC"
STATUS = "PROPOSED_NOT_ACCEPTED"

# ------------------------------------------------------------------ releases ---
# The installed release is the E-19 NEW release (E-19 U5, owner-accepted). NEW stays None until a merged owner record
# pins an independently attested build of the merged source (the E-19 `new-release-pin` pattern).
OLD_RELEASE = E19.NEW_RELEASE
OLD_MANIFEST_SHA256 = E19.NEW_MANIFEST_SHA256
NEW_RELEASE: str | None = None
NEW_MANIFEST_SHA256: str | None = None

# ------------------------------------------------------------- the one-member delta ---
PR1_ACCEPTANCE_MEMBER = E19.PR1_ACCEPTANCE_MEMBER
PR1_ACCEPTANCE_SOURCE = E19.PR1_ACCEPTANCE_SOURCE
PR1_ACCEPTANCE_OLD_SHA256 = E19.PR1_ACCEPTANCE_E19_SHA256                                       # ba943e1 (E-19)
PR1_ACCEPTANCE_NEW_SHA256 = "d3df4cfca975b31cbe526805d6573e7d4760ef376ad02f3cb8e0ac7cece4049b"  # OD-M12-10 judge
PAYLOAD_DELTA = {PR1_ACCEPTANCE_MEMBER: (PR1_ACCEPTANCE_OLD_SHA256, PR1_ACCEPTANCE_NEW_SHA256)}
# The exact edits (E-19 bytes -> OD-M12-10 bytes), each anchored on unique preceding context. `reverse_e22` proves the
# repository judge is these edits over the installed bytes and nothing else.
E22_EDITS = (
    (
        b'REQUIRED_DEPLOYER_MATURITY = "maturity=P1A-9"\n'
        b'\n',
        b'REQUIRED_DEPLOYER_MATURITY = "maturity=P1A-9"\n'
        b'\n'
        b'# E-22 owner risk adjudication (OD-M12-10; docs/architecture/slice-15b2b-b1b3e-mb12-prb2-proof-producers.md \xc2\xa717).\n'
        b'# The ONE E-22 outcome other than PASS that the package can carry: a genuine SECRET_HYGIENE FAIL whose `detail`\n'
        b'# names an owner adjudication pinned here by a reviewed, merged owner record, for the DEV_SYNTHETIC K-ACT only.\n'
        b'# The control side admits that detail only for the exact historical failure set (mb12_readiness_inputs). It is\n'
        b'# never PASS and never a clean scan; every other check stays PASS-only.\n'
        b'OWNER_RISK_ADJUDICATED = "OWNER_RISK_ADJUDICATED"\n'
        b'E22_ADJUDICATION_DETAIL_PREFIX = "OWNER_RISK_ADJUDICATION="\n'
        b'E22_ADJUDICATION_KEY_ID = "test-only.dev-synthetic.actor.b1b3d.1"\n'
        b'E22_ADJUDICATION_ENVIRONMENT = SC.ENVIRONMENT          # "dev": the DEV_SYNTHETIC deployment only\n'
        b'E22_ADJUDICATED_FAILURES = (\n'
        b'    "FAIL: JOURNAL_SCAN_NOT_PASS",\n'
        b'    "FAIL: JOURNAL_MARKER class=PEM_PRIVATE_KEY count=12",\n'
        b'    "FAIL: CEREMONY_TRANSCRIPT_NOT_RETAINED B1B3D-L2b",\n'
        b'    "FAIL: CEREMONY_WINDOW_NOT_RECORDED B1B3D-L2b",\n'
        b')\n'
        b'# adjudication SHA-256 -> the owner decision record SHA-256 that accepted it.\n'
        b'ACCEPTED_E22_ADJUDICATIONS: Mapping[str, str] = {\n'
        b'    "9528f7338b0a832bb821884654b1b8e2a8c86c1b65f4bf17ea2be2a48cbe9989":\n'
        b'        "56e71df1b7bf5c599c7d3f09edd5b12a37cf642c63d715b2f823f2ff92242c5a",\n'
        b'}\n'
        b'E22_ADJUDICATION_NONCLAIM = (\n'
        b'    "E-22 SECRET_HYGIENE: OWNER_RISK_ADJUDICATED (OD-M12-10), NOT a clean scan: JOURNAL_SECRET_SCAN=FAIL stands "\n'
        b'    "(12 PEM_PRIVATE_KEY markers, purpose UNKNOWN x3); the B1b-3d L2b transcript was not retained and its window "\n'
        b'    "not recorded; exposure of the DEV_SYNTHETIC K-ACT during or around L2b is not excluded; no other key, "\n'
        b'    "ceremony, environment or PROD")\n'
        b'\n'),
    (
        b'            return f"PROOF_SCOPE_MISMATCH:{name}"\n'
        b'    return None\n'
        b'\n'
        b'\n',
        b'            return f"PROOF_SCOPE_MISMATCH:{name}"\n'
        b'    return None\n'
        b'\n'
        b'\n'
        b'def _secret_hygiene_outcome(inputs: Pr1AcceptanceInputsV1) -> WR.CheckOutcomeV1:\n'
        b'    """E-22: PASS; or OWNER_RISK_ADJUDICATED for a genuine FAIL naming a pinned adjudication, DEV_SYNTHETIC only."""\n'
        b'    proofs = inputs.proofs if isinstance(inputs.proofs, Mapping) else {}\n'
        b'    proof = proofs.get("SECRET_HYGIENE")\n'
        b'    detail = proof.detail if isinstance(proof, ExternalProofV1) else None\n'
        b'    if detail is None:\n'
        b'        reason = _proof_reason(proofs, "SECRET_HYGIENE")\n'
        b'        return WR.CheckOutcomeV1(PASS) if reason is None else WR.CheckOutcomeV1(FAIL, reason)\n'
        b'    reason = _proof_reason(proofs, "SECRET_HYGIENE")\n'
        b'    adjudication = detail[len(E22_ADJUDICATION_DETAIL_PREFIX):] if type(detail) is str else ""\n'
        b'    if reason not in (None, "PROOF_NOT_PASS:SECRET_HYGIENE"):\n'
        b'        return WR.CheckOutcomeV1(FAIL, reason)\n'
        b'    if type(detail) is not str or not detail.startswith(E22_ADJUDICATION_DETAIL_PREFIX) \\\n'
        b'            or _HEX64.fullmatch(adjudication) is None:\n'
        b'        return WR.CheckOutcomeV1(FAIL, "E22_ADJUDICATION_MALFORMED")\n'
        b'    if proof.result != FAIL:\n'
        b'        return WR.CheckOutcomeV1(FAIL, "E22_ADJUDICATION_NOT_FOR_FAIL")\n'
        b'    if inputs.environment != E22_ADJUDICATION_ENVIRONMENT or not SC.is_dev_synthetic(inputs.profile) \\\n'
        b'            or inputs.profile.environment != E22_ADJUDICATION_ENVIRONMENT \\\n'
        b'            or inputs.profile.initial_key_id != E22_ADJUDICATION_KEY_ID:\n'
        b'        return WR.CheckOutcomeV1(FAIL, "E22_ADJUDICATION_OUT_OF_SCOPE")\n'
        b'    if adjudication not in ACCEPTED_E22_ADJUDICATIONS:\n'
        b'        return WR.CheckOutcomeV1(FAIL, "E22_ADJUDICATION_NOT_ACCEPTED")\n'
        b'    return WR.CheckOutcomeV1(OWNER_RISK_ADJUDICATED, adjudication)\n'
        b'\n'
        b'\n'),
    (
        b'    record("E09_BROKER_DENIAL_PRESERVATION", _proof_reason(inputs.proofs, "BROKER_DENIAL", "BROKER_PRESERVATION"))\n'
        b'    record("E22_SECRET_HYGIENE", _proof_reason(inputs.proofs, "SECRET_HYGIENE"))\n',
        b'    record("E09_BROKER_DENIAL_PRESERVATION", _proof_reason(inputs.proofs, "BROKER_DENIAL", "BROKER_PRESERVATION"))\n'
        b'    checks["E22_SECRET_HYGIENE"] = e22 = _secret_hygiene_outcome(inputs)\n'
        b'    if e22.status == OWNER_RISK_ADJUDICATED:\n'
        b'        evidence["secretHygieneAdjudication"] = {\n'
        b'            "status": OWNER_RISK_ADJUDICATED, "decision": "OD-M12-10", "adjudicationSha256": e22.reason,\n'
        b'            "ownerRecordSha256": ACCEPTED_E22_ADJUDICATIONS[e22.reason], "keyId": E22_ADJUDICATION_KEY_ID,\n'
        b'            "transcriptSha256": inputs.proofs["SECRET_HYGIENE"].transcript_sha256,\n'
        b'            "failures": list(E22_ADJUDICATED_FAILURES), "nonclaim": E22_ADJUDICATION_NONCLAIM}\n'),
    (
        b'    ordered = {name: checks[name] for name in PACKAGE_CHECKS}\n'
        b'    reasons = tuple(f"{name}:{outcome.reason}" for name, outcome in ordered.items() if outcome.status != PASS)\n',
        b'    ordered = {name: checks[name] for name in PACKAGE_CHECKS}\n'
        b'    # OWNER_RISK_ADJUDICATED satisfies E-22 only (OD-M12-10); it is kept distinct in the package, never shown as PASS.\n'
        b'    adjudicated = ordered["E22_SECRET_HYGIENE"].status == OWNER_RISK_ADJUDICATED\n'
        b'    reasons = tuple(f"{name}:{outcome.reason}" for name, outcome in ordered.items()\n'
        b'                    if outcome.status != PASS and not (adjudicated and name == "E22_SECRET_HYGIENE"))\n'),
    (
        b'        "evidence": _jsonable(evidence),\n'
        b'        "nonclaims": list(PR1_NONCLAIMS),\n',
        b'        "evidence": _jsonable(evidence),\n'
        b'        "nonclaims": list(PR1_NONCLAIMS) + ([E22_ADJUDICATION_NONCLAIM] if adjudicated else []),\n'),
)


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


def reverse_e22(data: bytes) -> bytes:
    """The installed (E-19) bytes of `pr1_acceptance.py`, from the OD-M12-10 bytes, by undoing exactly `E22_EDITS`."""
    _need(_sha(data) == PR1_ACCEPTANCE_NEW_SHA256, "E22_SOURCE_NOT_PINNED")
    for old, new in E22_EDITS:
        _need(data.count(new) == 1, "E22_EDIT_NOT_UNIQUE")
        data = data.replace(new, old)
    _need(_sha(data) == PR1_ACCEPTANCE_OLD_SHA256, "E22_REVERSAL_NOT_E19")
    return data


def new_release_module_pins(installed_pins: Mapping[str, str]) -> dict[str, str]:
    """The expected NEW module map from the installed (E-19 NEW) module pins: exactly `PAYLOAD_DELTA` moves."""
    pins = dict(installed_pins)
    for member, (before, after) in PAYLOAD_DELTA.items():
        _need(pins.get(member) == before, "INSTALLED_MODULE_PIN_UNEXPECTED", member)
        pins[member] = after
    return pins


def check_payload(payloads: Mapping[str, bytes], installed_pins: Mapping[str, str]) -> None:
    """A candidate NEW payload (member -> bytes) is admissible only if it differs from the installed module map in
    exactly the one member, with exactly the pinned bytes, and adds or drops no pinned member."""
    expected = new_release_module_pins(installed_pins)
    for member, pin in sorted(expected.items()):
        _need(member in payloads, "PAYLOAD_MEMBER_MISSING", member)
        _need(_sha(payloads[member]) == pin, "PAYLOAD_DELTA_NOT_EXACT", member)


# ------------------------------------------------------------------ the phases ---
V0, V1, V2, V3, V4, V5, V6, V7 = ("V0_W11_EXACT", "V1_NEW_STAGED", "V2_SIGNER_STOPPED", "V3_WITNESS_STOPPED",
                                  "V4_NEW_SELECTED", "V5_WITNESS_RUNNING", "V6_SIGNER_RUNNING", "V7_OLD_RETIRED")
PHASES = (V0, V1, V2, V3, V4, V5, V6, V7)
# phase -> (installed releases, selector, signer running from, witness running from); None = stopped.
PHASE_STATE = {
    V0: (("OLD",), "OLD", "OLD", "OLD"),
    V1: (("OLD", "NEW"), "OLD", "OLD", "OLD"),
    V2: (("OLD", "NEW"), "OLD", None, "OLD"),
    V3: (("OLD", "NEW"), "OLD", None, None),
    V4: (("OLD", "NEW"), "NEW", None, None),
    V5: (("OLD", "NEW"), "NEW", None, "NEW"),
    V6: (("OLD", "NEW"), "NEW", "NEW", "NEW"),
    V7: (("NEW",), "NEW", "NEW", "NEW"),
}
SIGNER_STOP_COMMAND = "/usr/bin/systemctl stop lilith-authority-dev.service lilith-authority-dev.socket"
WITNESS_STOP_COMMAND = E19.STOP_COMMAND
WITNESS_START_COMMAND = E19.START_COMMAND
# OD-M12-11: the credential loads of this transition, each its own private-material event (never OD-M12-10's).
LOAD_EVENTS = {V5: ("K-WIT", 1), V6: ("K-ACT", 1)}
KACT_LOAD_COUNT_AFTER = 2
OD_M12_11_RULE = (
    "each transition-time load (V5 K-WIT, V6 K-ACT) records its own window (operator markers) and retains its "
    "transcript; the post-transition journal and attribute reads follow the last load, in the same boot as its window, "
    "and must show exactly the historical 12 attributed matches (the OD-M12-10 admission); no new marker; the loads "
    "do not join the E-22 CEREMONIES table and never inherit the OD-M12-10 risk acceptance")


def check_phase_order(observed: list[str]) -> None:
    """The phases a transition passed through, in order: a prefix of `PHASES`, no skip and no repeat."""
    _need(list(observed) == list(PHASES[:len(observed)]), "PHASE_OUT_OF_ORDER", ",".join(observed))
