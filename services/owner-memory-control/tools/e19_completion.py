#!/usr/bin/env python3
"""15B2b-B1b-3e E-19 completion record: the post-U5 release bindings and the deployment-freeze gate.

Record: docs/architecture/slice-15b2b-b1b3e-e19-completion-record.md. Owner workstation, stdlib only; reads local
files, writes nothing, contacts nothing.

`e19_completion_record.json` (pinned below) binds the trusted U0 baseline, the five consumed transition steps
(U0 -> U5), the NEW release, POST9A-R, the owner's replacement acceptance, the final U5 observation and the final
`host U5` PASS. Its status is `TRANSITION_COMPLETE_U5_OWNER_COMPLETION_NOT_ACCEPTED`: E-19 is NOT owner-complete and
the deployment freeze is ACTIVE.

The freeze lifts only through `freeze_lift_admissible(host_u5_dir, deploy_run_id, acceptance)`. It trusts no
caller-supplied verdict, metadata, timestamp or log; it re-establishes everything itself:

1. provenance from the read-only GitHub Actions REST API (the owner's authenticated `gh`): PR #195 is MERGED into
   main; the run is `Deploy LILITH Core API to DEV` (`.github/workflows/deploy-dev.yml`, event `workflow_run`; never
   the PR-only "LILITH DEV deployment" CI stub), completed with conclusion success, on main at exactly the merge
   commit, and the FIRST such run created after the merge; its log is fetched from GitHub here and hashed;
2. a canonical `e19_operator host U5` directory whose own DEV-clock identity read (`identity.out`, rc 0, the DEV
   host, machine-id and boot) was acquired strictly AFTER that run completed;
3. `e19_dr5_target.compare(host dir, fetched log)`, recomputed here: EQUAL to `WITNESS_RUNNING_HELD_E19` with the
   accepted replacement and the NEW release;
4. the owner's verbatim completion statement, rendered from that evidence, and its local record binding the
   evidence digest.

Before the sanctioned deploy exists (PR not merged, no qualifying run) the gate is NOT admissible. Missing,
uncertain, stale, pre-deploy, wrong-run, wrong-workflow, wrong-commit, DRIFT or unaccepted evidence never lifts it.

    | Form | Effect |
    | --- | --- |
    | `record` | the pinned completion record, validated |
    | `render <host-u5-dir> <deploy-run-id>` | the canonical completion statement (provenance fetched read-only) |
    | `gate <host-u5-dir> <deploy-run-id> <acceptance.json>` | the freeze-lift judgement (never a write) |
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
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
# The exact post-U5 SHA-256 of the two re-pinned M-B11 tools (file -> digest). The M-B11 record-pin tests accept these
# and only these as the alternative to their own records; no other tool and no other field is admitted.
MB11_REPINNED_SHA256 = {
    "services/owner-memory-control/tools/mb11_signer_verifier.py":
        "e21fd26fd68bcdea3d645a12ff53b647ef3aa8f62824e9c89712b8fcb85d4e1d",
    "services/owner-memory-control/tools/mb11_restart_boundary_install.py":
        "428d93b4b36bdb8d7783e2c1f22d3961fd5cf3623ce0ee0d419ab3b81c53c8af",
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
COMPLETION_PR = 195
REPOSITORY = "rpahasara/lilith-os"
DEPLOY_WORKFLOW_NAME = "Deploy LILITH Core API to DEV"
DEPLOY_WORKFLOW_PATH = ".github/workflows/deploy-dev.yml"
DEV_HOSTNAME, DEV_MACHINE_ID = "lilith-dev-01", "ae929170e6fa4c8ab9cc7b9547238d9d"
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
COMPLETION_LINES = (
    "I accept E-19 completion for UPGRADE_FROM_P1B10_DEV_SYNTHETIC (DEV_SYNTHETIC).",
    "Completion record SHA-256: {record}. Release {new} (manifest {manifest}) is the sole installed release; "
    "{old} is retired.",
    "Accepted replacement witness: InvocationID {invocation}, MainPID {mainpid}.",
    "PR #{pr} merged as {merge}; first post-transition deploy run {run} ({workflow}) succeeded, completed {completed}; "
    "run log SHA-256 {log}.",
    "Host U5 read at {acquired} (HOST_RESULT SHA-256 {host}); DR-5 {target} EQUAL (comparison SHA-256 {comparison}).",
    "Evidence SHA-256: {evidence}.",
    "The E-19 deployment freeze ends with this acceptance. This acceptance authorizes nothing further: not package "
    "READY, not M-B11, not the signer, not the Registry, not authority.",
)


class GitHubSource:
    """The read-only provenance source: the owner's authenticated `gh` CLI against the GitHub REST API. Every fact
    the gate relies on is fetched here, never taken from the caller. Tests substitute a synthetic source."""

    def __init__(self, repository: str = REPOSITORY):
        self.repository = repository

    def _gh(self, *args: str) -> bytes:
        try:
            result = subprocess.run(("gh", *args), capture_output=True, timeout=300, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise CompletionError("GITHUB_UNAVAILABLE") from exc
        _need(result.returncode == 0 and bool(result.stdout), "GITHUB_UNAVAILABLE")
        return result.stdout

    def _api(self, path: str) -> Any:
        try:
            return json.loads(self._gh("api", path))
        except ValueError as exc:
            raise CompletionError("GITHUB_RESPONSE_UNPARSEABLE") from exc

    def pull(self, number: int) -> Any:
        return self._api(f"repos/{self.repository}/pulls/{number}")

    def run(self, run_id: str) -> Any:
        return self._api(f"repos/{self.repository}/actions/runs/{run_id}")

    def deploy_runs(self) -> Any:
        return self._api(f"repos/{self.repository}/actions/workflows/deploy-dev.yml/runs?branch=main"
                         "&event=workflow_run&per_page=100")

    def log(self, run_id: str) -> bytes:
        return self._gh("run", "view", run_id, "-R", self.repository, "--log")


def deploy_provenance(run_id: Any, github: Any) -> tuple[dict, bytes]:
    """The first post-transition deploy, established from GitHub only; refused (never substituted) otherwise."""
    _need(isinstance(run_id, str) and _RUN_ID.fullmatch(run_id) is not None, "DEPLOY_RUN_ID")
    _need(getattr(github, "repository", None) == REPOSITORY, "PROVENANCE_SOURCE_REPOSITORY")
    pr = github.pull(COMPLETION_PR)
    _need(isinstance(pr, Mapping) and pr.get("number") == COMPLETION_PR and pr.get("merged") is True,
          "PR_NOT_MERGED")
    merge, merged_at = pr.get("merge_commit_sha"), pr.get("merged_at")
    _need(isinstance(merge, str) and _SHA40.fullmatch(merge) is not None and isinstance(merged_at, str)
          and _INSTANT.fullmatch(merged_at) is not None and (pr.get("base") or {}).get("ref") == "main",
          "PR_MERGE_UNVERIFIED")
    run = github.run(run_id)
    _need(isinstance(run, Mapping) and str(run.get("id")) == run_id, "RUN_NOT_FOUND")
    _need(run.get("name") == DEPLOY_WORKFLOW_NAME and run.get("path") == DEPLOY_WORKFLOW_PATH, "RUN_WRONG_WORKFLOW")
    _need((run.get("repository") or {}).get("full_name") == REPOSITORY, "RUN_WRONG_REPOSITORY")
    _need(run.get("event") == "workflow_run" and run.get("head_branch") == "main", "RUN_WRONG_TRIGGER")
    _need(run.get("status") == "completed" and run.get("conclusion") == "success", "RUN_NOT_SUCCESSFUL")
    _need(run.get("head_sha") == merge, "RUN_NOT_THE_MERGE_COMMIT")
    created, completed = run.get("created_at"), run.get("updated_at")
    _need(all(isinstance(v, str) and _INSTANT.fullmatch(v) for v in (created, completed))
          and merged_at <= created <= completed, "RUN_TIMES")
    listing = github.deploy_runs()
    runs = listing.get("workflow_runs") if isinstance(listing, Mapping) else None
    _need(isinstance(runs, list), "RUN_LISTING_UNAVAILABLE")
    after = sorted((r for r in runs if isinstance(r, Mapping) and r.get("event") == "workflow_run"
                    and isinstance(r.get("created_at"), str) and r["created_at"] >= merged_at),
                   key=lambda r: (r["created_at"], str(r.get("id"))))
    _need(bool(after) and str(after[0].get("id")) == run_id, "RUN_NOT_THE_FIRST_AFTER_MERGE")
    log = github.log(run_id)
    _need(isinstance(log, bytes) and bool(log), "RUN_LOG_UNAVAILABLE")
    return {"pr": COMPLETION_PR, "mergeCommit": merge, "mergedAt": merged_at, "runId": run_id,
            "workflow": DEPLOY_WORKFLOW_PATH, "runCreatedAt": created, "runCompletedAt": completed,
            "logSha256": _sha(log)}, log


def host_binding(host_dir: Path, completed_at: str) -> dict:
    """The canonical `host U5` directory; its DEV-clock acquisition instant strictly after the deploy completed."""
    host_dir = Path(host_dir)
    identity, rc = host_dir / "identity.out", host_dir / "identity.rc"
    _need(identity.is_file() and not identity.is_symlink() and rc.is_file() and rc.read_text().strip() == "0",
          "HOST_IDENTITY_MISSING")
    lines = identity.read_bytes().decode("utf-8", "replace").splitlines()
    _need(len(lines) >= 4 and _INSTANT.fullmatch(lines[0]) is not None, "HOST_IDENTITY_MALFORMED")
    _need((lines[1], lines[2], lines[3]) == (DEV_HOSTNAME, DEV_MACHINE_ID, E.BOOT_ID), "HOST_NOT_DEV_THIS_BOOT")
    _need(lines[0] > completed_at, "HOST_READ_NOT_AFTER_DEPLOY")
    return {"acquiredAt": lines[0], "identitySha256": _sha(identity.read_bytes()),
            "hostResultSha256": _sha((host_dir / "HOST_RESULT.json").read_bytes()),
            "w10OutputSha256": _sha((host_dir / "w10verifier.out").read_bytes())}


def completion_evidence(host_dir: Path, run_id: Any, github: Any = None) -> dict:
    """Everything the owner's completion statement binds, recomputed from trusted sources only."""
    load_record()
    github = github if github is not None else GitHubSource()
    provenance, log = deploy_provenance(run_id, github)
    host = host_binding(Path(host_dir), provenance["runCompletedAt"])
    comparison = D.compare(Path(host_dir), log.decode("utf-8", "replace"))          # recomputed, never supplied
    _need(comparison.get("result") == "EQUAL" and comparison.get("target") == D.RUNNING_HELD_E19
          and comparison.get("phase") == "W10_1_HELD_EXACT", "DR5_NOT_EQUAL_RUNNING_HELD_E19")
    _need(comparison["hostEvidence"] == {"hostResultSha256": host["hostResultSha256"],
                                         "w10OutputSha256": host["w10OutputSha256"]}, "HOST_EVIDENCE_CHANGED")
    return {"completionRecordSha256": D.COMPLETION_RECORD_SHA256, "provenance": provenance, "host": host,
            "comparison": comparison, "comparisonSha256": _sha(_canonical(comparison))}


def _statement(evidence: Mapping[str, Any]) -> bytes:
    record = load_record()
    p, h = evidence["provenance"], evidence["host"]
    values = {"record": D.COMPLETION_RECORD_SHA256, "new": E.NEW_RELEASE, "manifest": E.NEW_MANIFEST_SHA256,
              "old": E.OLD_RELEASE, "invocation": record["witness"]["acceptedReplacement"][0],
              "mainpid": record["witness"]["acceptedReplacement"][1], "pr": p["pr"], "merge": p["mergeCommit"],
              "run": p["runId"], "workflow": p["workflow"], "completed": p["runCompletedAt"], "log": p["logSha256"],
              "acquired": h["acquiredAt"], "host": h["hostResultSha256"], "target": D.RUNNING_HELD_E19,
              "comparison": evidence["comparisonSha256"], "evidence": _sha(_canonical(evidence))}
    return ("\n".join(line.format(**values) for line in COMPLETION_LINES) + "\n").encode("ascii")


def render_completion_statement(host_dir: Any, run_id: Any, github: Any = None) -> bytes:
    """The canonical owner completion statement, from recomputed evidence only."""
    return _statement(completion_evidence(Path(host_dir), run_id, github))


def acceptance_record(evidence: Mapping[str, Any], statement: bytes) -> dict:
    return {"recordType": COMPLETION_ACCEPTANCE_TYPE, "schemaVersion": 1, "mode": E.MODE,
            "completionRecordSha256": D.COMPLETION_RECORD_SHA256, "deployRunId": evidence["provenance"]["runId"],
            "mergeCommit": evidence["provenance"]["mergeCommit"], "evidenceSha256": _sha(_canonical(evidence)),
            "statementSha256": _sha(statement)}


def freeze_lift_admissible(host_dir: Any, run_id: Any, acceptance: Any, github: Any = None) -> tuple[bool, str]:
    """True only when the recomputed first-deploy evidence is EQUAL AND the owner's verbatim statement over exactly
    that evidence, with its record, is supplied. It judges; it writes and lifts nothing."""
    try:
        evidence = completion_evidence(Path(host_dir), run_id, github)
        statement = _statement(evidence)
        _need(isinstance(acceptance, Mapping) and set(acceptance) == {"statement", "record"},
              "COMPLETION_ACCEPTANCE_MISSING")
        raw = acceptance["statement"].encode("ascii") if isinstance(acceptance["statement"], str) else None
        _need(raw == statement, "COMPLETION_STATEMENT_NOT_CANONICAL")
        _need(isinstance(acceptance["record"], Mapping)
              and _canonical(acceptance["record"]) == _canonical(acceptance_record(evidence, statement)),
              "COMPLETION_ACCEPTANCE_RECORD_MISMATCH")
    except (CompletionError, D.TargetError, KeyError, TypeError, ValueError, OSError, UnicodeEncodeError) as exc:
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
            sys.stdout.buffer.write(render_completion_statement(Path(argv[1]), argv[2]))
            return 0
        if len(argv) == 4 and argv[0] == "gate":
            ok, reason = freeze_lift_admissible(Path(argv[1]), argv[2], _read_json(argv[3]))
            sys.stdout.write(json.dumps({"admissible": ok, "reason": reason, "authorizes": "NOTHING"}) + "\n")
            return 0 if ok else 1
        print("e19_completion: REFUSED USAGE", file=sys.stderr)
        return 2
    except (CompletionError, D.TargetError, OSError, ValueError) as exc:
        print(f"e19_completion: REFUSED {getattr(exc, 'reason', exc)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
