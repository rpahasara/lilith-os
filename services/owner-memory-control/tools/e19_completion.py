#!/usr/bin/env python3
"""15B2b-B1b-3e E-19 completion record: the post-U5 release bindings and the deployment-freeze gate.

Record: docs/architecture/slice-15b2b-b1b3e-e19-completion-record.md. Owner workstation, stdlib only; reads local
files, writes nothing, contacts nothing.

`e19_completion_record.json` (pinned below) binds the trusted U0 baseline, the five consumed transition steps
(U0 -> U5), the NEW release, POST9A-R, the owner's replacement acceptance, the final U5 observation and the final
`host U5` PASS. Its status is `TRANSITION_COMPLETE_U5_OWNER_COMPLETION_NOT_ACCEPTED`: E-19 is NOT owner-complete and
the deployment freeze is ACTIVE.

The freeze lifts only through `freeze_lift_admissible`, which requires BOTH:

1. the first post-transition deploy's DR-5 comparison (`e19_dr5_target.compare`) = EQUAL to
   `WITNESS_RUNNING_HELD_E19`, from a verified post-U5 `host U5` read and a named deploy run; and
2. the owner's verbatim completion statement (rendered here from exactly that comparison) and its local record.

Missing, partial, DRIFT, wrong-target, wrong-phase or unaccepted evidence never lifts it.

    | Form | Effect |
    | --- | --- |
    | `record` | the pinned completion record, validated |
    | `render <dr5-comparison.json> <deploy-run-id>` | the canonical completion statement for that comparison |
    | `gate <dr5-comparison.json> <deploy-run-id> <acceptance.json>` | the freeze-lift judgement (never a write) |
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import e19_dr5_target as D  # noqa: E402  (record pin, accepted replacement, E-19 DR-5 targets)
import e19_p1b10_upgrade as E  # noqa: E402

RECORD_TYPE = "LILITH_E19_COMPLETION_RECORD"
STATUS = "TRANSITION_COMPLETE_U5_OWNER_COMPLETION_NOT_ACCEPTED"
FREEZE = "ACTIVE"
COMPLETION_ACCEPTANCE_TYPE = "LILITH_E19_OWNER_COMPLETION_ACCEPTANCE"
_RUN_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
STEP_ORDER = ("STAGE", "STOP", "SELECT", "START", "RETIRE")

# ------------------------------------------------------------- post-U5 release bindings ---
# Every tool that names the retired release, classified after U5 (record §3). A test fails on any unclassified one.
# CURRENT bindings now pin NEW; the entries below keep the OLD SHA only as history or provenance.
REPINNED_TO_NEW = {
    "services/owner-memory-control/tools/mb11_signer_verifier.py": "RELEASE_SHA / RELEASE_CWD (W11 signer cwd)",
    "services/owner-memory-control/tools/mb11_restart_boundary_install.py":
        "RELEASE_SHA (P1B-10R plan); signer fragments byte-identical in OLD and NEW",
    "services/owner-memory-control/tools/mb12_pr3_material.py": "DEV_EXPECTED releaseSha / releaseManifestSha256",
    "services/owner-memory-control/tools/mb12_readiness_inputs.py": "DEV_PINS releaseSha / attestedManifestSha256",
}
OLD_RELEASE_MENTIONS = {
    "services/owner-memory-control/tools/mb6_operator.py":
        "HISTORICAL: completed M-B6 ceremony, byte-identical; its readiness pins describe the retired release",
    "services/owner-memory-control/tools/mb9_operator.py":
        "HISTORICAL: completed M-B9 ceremony; its single-release readiness path is superseded by `e19_operator host U5`",
    "services/owner-memory-control/tools/mb11_restart_boundary_install.py": "PROVENANCE: fragment source comment",
    "services/owner-memory-control/tools/mb12_os_denial_proof.py":
        "PROVENANCE: fragment text; the fragment bytes are identical in OLD and NEW",
    "services/owner-memory-control/tools/mb12_readiness_inputs.py":
        "HISTORICAL: E19_DEFECTIVE_RELEASES names the retired release carrying the E-19 judge defect",
    "services/owner-memory-control/tools/mb4_mb5_operator.py": "HISTORICAL: completed M-B4/M-B5 ceremony",
    "services/owner-memory-control/tools/mb6_ledger_verifier.py": "HISTORICAL: completed M-B6 verifier",
    "services/owner-memory-control/tools/mb7_mb8_operator.py": "HISTORICAL: completed Package A ceremony",
    "services/owner-memory-control/tools/e19_p1b10_upgrade.py": "CONTRACT: OLD_RELEASE of the completed transition",
}
# The routine post-U5 preservation path (replaces the M-B10 host POST + W10_1 DR-5 comparison, which read OLD).
ROUTINE_HOST_READ = "services/owner-memory-control/tools/e19_operator.py host <main> <workdir> U5_OLD_RETIRED_REPLACEMENT_ACCEPTED"
ROUTINE_DR5 = "services/owner-memory-control/tools/e19_dr5_target.py compare <host-u5-dir> <deploy-log>"


class CompletionError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _need(condition: bool, reason: str) -> None:
    if not condition:
        raise CompletionError(reason)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def load_record() -> dict:
    """The pinned completion record, validated against the merged contract (never against host values)."""
    raw = D.COMPLETION_RECORD.read_bytes()
    _need(_sha(raw) == D.COMPLETION_RECORD_SHA256, "COMPLETION_RECORD_PIN_MISMATCH")
    record = json.loads(raw)
    _need(record.get("recordType") == RECORD_TYPE and record.get("schemaVersion") == 1 and record.get("mode") == E.MODE,
          "RECORD_TYPE")
    _need(record.get("status") == STATUS and record.get("ownerCompletionAcceptance") is None
          and record.get("deploymentFreeze") == FREEZE, "RECORD_STATUS")
    _need(record["oldRelease"] == {"releaseSha": E.OLD_RELEASE, "manifestSha256": E.OLD_MANIFEST_SHA256,
                                   "state": "RETIRED"}, "RECORD_OLD_RELEASE")
    new = record["newRelease"]
    _need((new["releaseSha"], new["manifestSha256"], new["state"])
          == (E.NEW_RELEASE, E.NEW_MANIFEST_SHA256, "SOLE_INSTALLED_SELECTED")
          and new["archiveSha256"] == E.NEW_RELEASE_ATTESTATION["archiveSha256"]
          and new["attestationDigest"] == E.NEW_RELEASE_ATTESTATION["attestationDigest"], "RECORD_NEW_RELEASE")
    _need([s["step"] for s in record["transitionSteps"]] == list(STEP_ORDER)
          and all(s["result"] == f"E19_{s['step']}_REACHED_{s['postPhase']}" for s in record["transitionSteps"])
          and [s["postPhase"] for s in record["transitionSteps"]] == [E.U1, E.U2, E.U3, E.U4, E.U5]
          and [s["prePhase"] for s in record["transitionSteps"]] == [E.U0, E.U1, E.U2, E.U3, E.U4], "RECORD_STEPS")
    u0 = record["u0Baseline"]
    _need(u0["phase"] == E.U0 and u0["endingIncarnation"] == list(E.ENDING_INCARNATION)
          and all(re.fullmatch(r"[0-9a-f]{64}", u0[k]) for k in ("acceptanceSha256", "statementSha256",
                                                                   "observationSha256"))
          and E._cursor(u0["journalCursor"]) is not None, "RECORD_U0")
    _need(record["post9aR"]["result"] == "POST9A_R_VERIFIED" and record["post9aR"]["denials"] == E.POST9A_R_DENIALS
          and record["replacementAcceptance"]["subjectSha256"] == record["post9aR"]["evidenceSha256"], "RECORD_POST9A_R")
    witness = record["witness"]
    _need(witness["acceptedReplacement"] == [record["replacementAcceptance"]["invocationId"],
                                             record["replacementAcceptance"]["mainPid"]]
          and witness["invocationIdsAfterU0Cursor"] == [E.ENDING_INCARNATION[0], witness["acceptedReplacement"][0]]
          and witness["kWitLoadsAfterU0Cursor"] == 1, "RECORD_WITNESS")
    _need(record["finalU5"]["phase"] == E.U5
          and record["finalU5"]["observationSha256"] == record["transitionSteps"][-1]["postObservationSha256"],
          "RECORD_FINAL_U5")
    host = record["finalHostU5"]
    _need(host["result"] == D.HOST_U5_PASS and host["selectedRelease"] == E.NEW_RELEASE
          and host["e19State"] == "E19_OLD_RETIRED", "RECORD_HOST_U5")
    first = record["firstPostTransitionDeploy"]
    _need(first == {"dr5Target": D.RUNNING_HELD_E19, "targetStatus": "DERIVED_PINNED_NOT_ACCEPTED",
                    "deployRunId": None, "dr5Comparison": None}, "RECORD_FIRST_DEPLOY")
    return record


# ------------------------------------------------------------------ the freeze gate ---
COMPLETION_LINES = (
    "I accept E-19 completion for UPGRADE_FROM_P1B10_DEV_SYNTHETIC (DEV_SYNTHETIC).",
    "Completion record SHA-256: {record}. Release {new} (manifest {manifest}) is the sole installed release; "
    "{old} is retired.",
    "Accepted replacement witness: InvocationID {invocation}, MainPID {mainpid}.",
    "First post-transition deploy run {run}: DR-5 {target} EQUAL (comparison SHA-256 {comparison}).",
    "The E-19 deployment freeze ends with this acceptance. This acceptance authorizes nothing further: not package "
    "READY, not M-B11, not the signer, not the Registry, not authority.",
)


def _comparison_ok(comparison: Any) -> None:
    _need(isinstance(comparison, Mapping) and comparison.get("resultType") == "LILITH_E19_DR5_PHASE_COMPARISON",
          "DR5_COMPARISON_MISSING")
    _need(comparison.get("result") == "EQUAL" and comparison.get("unequal") == [] and comparison.get("allowed") == 0
          and comparison.get("oldReleaseLines") == 0, "DR5_NOT_EQUAL")
    _need(comparison.get("target") == D.RUNNING_HELD_E19 and comparison.get("phase") == "W10_1_HELD_EXACT",
          "DR5_WRONG_TARGET_OR_PHASE")
    target = E.NEW_DR5_TARGETS[D.RUNNING_HELD_E19]
    observed = comparison.get("observed") or {}
    _need(all(observed.get(name) == {"lines": target[name][0], "sha256": target[name][1]} for name in D.SETS),
          "DR5_OBSERVED_NOT_THE_PINNED_TARGET")
    bound = comparison.get("hostEvidence") or {}
    _need(all(isinstance(bound.get(k), str) and re.fullmatch(r"[0-9a-f]{64}", bound[k])
              for k in ("hostResultSha256", "w10OutputSha256")), "DR5_HOST_EVIDENCE_MISSING")


def render_completion_statement(comparison: Any, deploy_run_id: Any) -> bytes:
    """The canonical owner completion statement, from a verified EQUAL comparison only."""
    record = load_record()
    _comparison_ok(comparison)
    _need(isinstance(deploy_run_id, str) and _RUN_ID.fullmatch(deploy_run_id) is not None, "DEPLOY_RUN_ID")
    values = {"record": D.COMPLETION_RECORD_SHA256, "new": E.NEW_RELEASE, "manifest": E.NEW_MANIFEST_SHA256,
              "old": E.OLD_RELEASE, "invocation": record["witness"]["acceptedReplacement"][0],
              "mainpid": record["witness"]["acceptedReplacement"][1], "run": deploy_run_id,
              "target": D.RUNNING_HELD_E19, "comparison": _sha(_canonical(comparison))}
    return ("\n".join(line.format(**values) for line in COMPLETION_LINES) + "\n").encode("ascii")


def freeze_lift_admissible(comparison: Any, deploy_run_id: Any, acceptance: Any) -> tuple[bool, str]:
    """True only for an EQUAL first-deploy comparison AND the owner's verbatim completion statement with its record.
    It judges; it writes and lifts nothing."""
    try:
        load_record()
        _comparison_ok(comparison)
        statement = render_completion_statement(comparison, deploy_run_id)
        _need(isinstance(acceptance, Mapping) and set(acceptance) == {"statement", "record"},
              "COMPLETION_ACCEPTANCE_MISSING")
        raw = acceptance["statement"].encode("ascii") if isinstance(acceptance["statement"], str) else None
        _need(raw == statement, "COMPLETION_STATEMENT_NOT_CANONICAL")
        expected = {"recordType": COMPLETION_ACCEPTANCE_TYPE, "schemaVersion": 1, "mode": E.MODE,
                    "completionRecordSha256": D.COMPLETION_RECORD_SHA256, "deployRunId": deploy_run_id,
                    "dr5ComparisonSha256": _sha(_canonical(comparison)), "statementSha256": _sha(statement)}
        _need(isinstance(acceptance["record"], Mapping) and _canonical(acceptance["record"]) == _canonical(expected),
              "COMPLETION_ACCEPTANCE_RECORD_MISMATCH")
    except (CompletionError, D.TargetError, KeyError, TypeError, ValueError, UnicodeEncodeError) as exc:
        return False, "FREEZE_ACTIVE:" + str(getattr(exc, "reason", None) or type(exc).__name__)
    return True, "FREEZE_LIFT_ADMISSIBLE"


def _read_json(path: str) -> Any:
    raw = Path(path).read_bytes()
    _need(len(raw) <= 1024 * 1024, "INPUT_TOO_LARGE")
    return json.loads(raw)


def main(argv: list[str]) -> int:
    try:
        if argv == ["record"]:
            sys.stdout.write(json.dumps(load_record(), sort_keys=True, indent=1) + "\n")
            return 0
        if len(argv) == 3 and argv[0] == "render":
            sys.stdout.buffer.write(render_completion_statement(_read_json(argv[1]), argv[2]))
            return 0
        if len(argv) == 4 and argv[0] == "gate":
            ok, reason = freeze_lift_admissible(_read_json(argv[1]), argv[2], _read_json(argv[3]))
            sys.stdout.write(json.dumps({"admissible": ok, "reason": reason, "authorizes": "NOTHING"}) + "\n")
            return 0 if ok else 1
        print("e19_completion: REFUSED USAGE", file=sys.stderr)
        return 2
    except (CompletionError, D.TargetError, OSError, ValueError) as exc:
        print(f"e19_completion: REFUSED {getattr(exc, 'reason', exc)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
