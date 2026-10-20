"""15B2b-B1b-3e M-B15 W14 (post-RELEASED, read-only): the FULL_READINESS tail, the W14 judge, the operator flow.

Record: docs/architecture/slice-15b2b-b1b3e-mb15-w14-full-readiness-package.md. TEST-ONLY: synthetic reports (with
REAL package digests), a synthetic DEV behind the operator's transport seams, and (contract layer) the REAL release
verifier in both modes on the synthetic PR-1 host before and after a REAL `release_initial`. Nothing contacts DEV.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-mb15-w14-full-readiness-package.md"
for _p in (ROOT / "services/core-api", ROOT / "services/owner-memory-control", TOOLS, ROOT / "services/authority-dev",
           ROOT / "services/authority-dev/ceremony", ROOT / "services/authority-dev/tests",
           ROOT / "services/recovery-witness"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import mb11_signer_verifier as W  # noqa: E402
import mb14_operator as MB14  # noqa: E402
import mb15_full_remote as F  # noqa: E402
import mb15_operator as OP  # noqa: E402
from lilith_owner_memory import pr1_acceptance as PA  # noqa: E402
from lilith_owner_memory import successor_custody as SC  # noqa: E402
from lilith_owner_memory import witness_readiness as WR  # noqa: E402

try:
    import cryptography  # noqa: F401
    import fido2  # noqa: F401
    import rfc8785  # noqa: F401
    HAVE_CRYPTO = True
except ImportError:  # pragma: no cover - the stdlib layer still runs
    HAVE_CRYPTO = False
POSIX = os.name == "posix"

INPUTS = {"synthetic": "owner inputs (TEST)"}
ENVELOPE = b'{"envelopeType":"SYNTHETIC"}\n'
EXP = OP.expected()
DOC = {"form": "full", "ownerInputs": INPUTS}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def done(code=0, out=b"", err=b""):
    return subprocess.CompletedProcess([], code, out, err)


# ------------------------------------------------------------------ synthetic evidence ---

def report(mode: str, **change) -> dict:
    """A `verifier.report` with a REAL package digest; `change` edits the package before it is digested."""
    checks = {name: [PA.PASS, None] for name in PA.PACKAGE_CHECKS}
    status, reasons = "READY", []
    if mode == OP.ELIGIBILITY:
        checks["E16_HOLD_STORE"] = [PA.FAIL, "CEREMONY_HOLD:HOLD_NOT_HELD"]
        checks["E17_READINESS"] = [PA.FAIL, "READINESS_NOT_READY"]
        status, reasons = "NOT_READY", list(OP.ELIGIBILITY_PACKAGE_REASONS)
    package = {"packageType": PA.PACKAGE_TYPE, "schemaVersion": PA.PACKAGE_SCHEMA_VERSION, "environment": "dev",
               "mode": mode, "scope": "PR1_INITIAL_CUSTODY", "status": status, "authorityGranted": False,
               "activationGranted": False, "issuanceWired": False, "wholeHostRollbackProtected": False,
               "checks": checks,
               "evidence": {"holdStore": {"listingDigest": EXP["released"]["listingDigest"],
                                          "records": [[EXP["ceremonyId"], "INITIAL_CUSTODY", "RELEASED"]]},
                            "witness": {"classification": "CONSISTENT", "chainLength": 1,
                                        "headDigest": EXP["genesis"], "genesisDigest": EXP["genesis"]},
                            "activation": {"line": PA.ACTIVATION_DARK_LINE, "b1cUnchanged": True}},
               "nonclaims": []}
    package.update(change.pop("package", {}))
    value = {"mode": mode, "status": package["status"], "reasons": reasons, "packageDigest": PA.package_digest(package),
             "package": package, "authorityGranted": False}
    value.update(change)
    return value


def summary(mode: str, **change) -> dict:
    full = mode == OP.FULL
    value = {"status": "READY" if full else "NOT_READY", "reasons": [] if full else ["CEREMONY_HOLD:HOLD_NOT_HELD"],
             "holdDetail": None if full else "RELEASED",
             "loadedKeyBinding": {"status": "PASS", "reason": None, "detail": None},
             "facts": {"authorityGranted": False, "liveEntryAuthorized": False, "issuanceReady": full,
                       "successorCurrent": full},
             "packageFlags": {"authorityGranted": False, "activationGranted": False, "issuanceWired": False},
             "packageReasons": []}
    value.update(change)
    return value


def health() -> dict:
    return {**W.HEALTH_EXACT, "publicKeySha256": W.B3_PUBLIC_KEY_SHA256, "reasons": list(W.STRUCTURAL_REASONS)}


def signer_units(signer=OP.SIGNER) -> dict:
    common = {"LoadState": "loaded", "UnitFileState": "static", "NeedDaemonReload": "no", "Result": "success",
              "ActiveState": "active"}
    return {W.SIGNER_SERVICE: {**common, "Id": W.SIGNER_SERVICE, "SubState": "running", "MainPID": signer[1],
                               "NRestarts": "0", "InvocationID": signer[0]},
            W.SIGNER_SOCKET_UNIT: {**common, "Id": W.SIGNER_SOCKET_UNIT, "SubState": "running", "MainPID": "0",
                                   "NRestarts": "0", "InvocationID": ""}}


def remote(**change) -> dict:
    bound = {"InvocationID": OP.SIGNER[0], "MainPID": OP.SIGNER[1]}
    value = {"remoteType": F.REMOTE_TYPE, "schemaVersion": 1, "form": "full", "evidenceSha256": F.evidence_digest(DOC),
             "authorityGranted": False,
             "healthCapture": {"attempted": True, "before": bound, "after": dict(bound), "health": health()},
             "readiness": {"holdListingDigest": EXP["released"]["listingDigest"],
                           "full": report(OP.FULL), "fullSummary": summary(OP.FULL),
                           "eligibility": report(OP.ELIGIBILITY), "eligibilitySummary": summary(OP.ELIGIBILITY)},
             "signer": {"units": signer_units(),
                        "paths": {"credentials": {"present": True, "kind": "dir", "uid": 995, "gid": 985,
                                                  "mode": 0o500, "names": [W.CREDENTIAL_NAME]},
                                  "ownerSocket": {"present": True, "kind": "socket", "uid": 0, "gid": 0,
                                                  "mode": 0o600}},
                        "process": {"cwd": OP.RELEASE_CWD, "argv": list(W.EXEC_ARGV), "uid": 995, "gid": 985}},
             "restartBoundary": {"reasons": [], "shadows": []},
             "ledger": {"readable": True, "listing": {W.LEDGER_NAME: 61440}, "dbSha256": "c" * 64}}
    value.update(change)
    return value


def released_entries(state: str = SC.RELEASED, witness: str = OP.MB14.GENESIS) -> list[tuple[str, bytes]]:
    reason = SC.INITIAL_CUSTODY_BOOTSTRAP if state == SC.HELD else SC.OWNER_RELEASE_AFTER_ELIGIBILITY
    record = SC.CeremonyHoldV1("dev", EXP["ceremonyId"], SC.INITIAL_CUSTODY, state, reason, None,
                               SC.custody_profile("dev").initial_key_id, witness).to_dict()
    return [(SC.hold_record_name(record["ceremonyId"]), SC.hold_record_bytes(record))]


def observe_out(entries: list[tuple[str, bytes]]) -> bytes:
    observation = SC.HoldStoreObservationV1(tuple(WR.StoreEntryV1(n, WR.REGULAR, d) for n, d in entries))
    snapshot = PA.hold_snapshot_document(observation, environment="dev")
    return json.dumps({"listingDigest": snapshot["listingDigest"], "snapshot": snapshot, "authorityGranted": False},
                      sort_keys=True, separators=(",", ":")).encode() + b"\n"


def read(entries=None, **change) -> dict:
    exp_doc = MB14.expected_document()
    value = {"codes": {"observe": 0, "stage": 0, "units": 0},
             "hold": MB14.judge_observe(0, observe_out(released_entries() if entries is None else entries), exp_doc),
             "stage": "ABSENT", "signer": list(OP.SIGNER), "witness": list(OP.WITNESS)}
    value.update(change)
    return value


def readiness_with(**change) -> dict:
    value = remote()["readiness"]
    value.update(change)
    return value


# ------------------------------------------------------------------------------- tests ---

class PinTests(unittest.TestCase):
    def test_new_tools_are_pinned_and_reused_tools_are_byte_unchanged(self):
        self.assertEqual(sha((TOOLS / "mb15_full_remote.py").read_bytes()), OP.TOOL_PINS[OP.REMOTE])
        self.assertEqual(sha((TOOLS / "mb14_operator.py").read_bytes()), OP.TOOL_PINS[OP.MB14.OPERATOR])
        for path, pin in OP.MB14.TOOL_PINS.items():           # every M-B14 / E-22 / W11 pin, unchanged
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)

    def test_the_tail_is_read_only(self):
        source = (TOOLS / "mb15_full_remote.py").read_text(encoding="utf-8")
        for forbidden in ("release_initial", "release-initial", "unlink(", "rmdir(", "os.remove", ".write_bytes",
                          ".write_text", "\"start\"", "\"stop\"", "daemon-reload", "open(", "subprocess"):
            self.assertNotIn(forbidden, source, forbidden)
        self.assertEqual(F.FORMS, ("full",))


class JudgeTests(unittest.TestCase):
    def judge(self, readback=None, value=None):
        return OP.judge(read() if readback is None else readback, remote() if value is None else value)

    def assert_stop(self, reason, readback=None, value=None):
        result = self.judge(readback, value)
        self.assertEqual(result["w14"], OP.W14_STOP)
        self.assertTrue(any(r == reason or r.startswith(reason + ":") for r in result["reasons"]),
                        (reason, result["reasons"]))

    def test_the_exact_released_state_is_w14_1_and_nothing_more(self):
        result = self.judge()
        self.assertEqual((result["w14"], result["reasons"]), (OP.W14_1, []))
        self.assertEqual(result["fullPackageDigest"], remote()["readiness"]["full"]["packageDigest"])
        self.assertIs(result["mb15Established"], False)
        self.assertIs(result["authorityGranted"], False)
        self.assertEqual(result["outstanding"], list(OP.OUTSTANDING))
        self.assertIn("OWNER_FRESHNESS_CURRENT_S25_REPLICA_B", result["outstanding"])
        self.assertIn("PENDING_REBOOT_WINDOW", result["outstanding"])

    def test_owner_input_checks_are_reported_as_envelope_derived_never_observed(self):
        result = self.judge()
        self.assertEqual(result["w14"], OP.W14_1)
        self.assertEqual(result["activationDarkSource"], "OWNER_ENVELOPE_ACTIVATION_LINE")
        self.assertIs(result["activationObservedLive"], False)
        self.assertEqual((result["envelopeCurrency"], result["ownerFreshness"]), ("NOT_JUDGED", "NOT_EVALUATED"))
        self.assertEqual(result["ownerInputChecks"], {name: PA.PASS for name in OP.OWNER_INPUT_CHECKS})
        self.assertEqual(result["ownerInputBoundChecks"], {name: PA.PASS for name in OP.OWNER_INPUT_BOUND_CHECKS})
        self.assertEqual(result["activationEvidence"], {"line": PA.ACTIVATION_DARK_LINE, "b1cUnchanged": True})
        self.assertIn("E19_ACTIVATION_DARK", OP.OWNER_INPUT_CHECKS)
        self.assertTrue(set(OP.OWNER_INPUT_CHECKS + OP.OWNER_INPUT_BOUND_CHECKS) <= set(PA.PACKAGE_CHECKS))
        self.assertIs(result["mb15Established"], False)                  # observation success != M-B15

    def test_an_envelope_activation_line_that_is_not_dark_stops_and_is_named(self):
        checks = copy.deepcopy(report(OP.FULL)["package"]["checks"])
        checks["E19_ACTIVATION_DARK"] = [PA.FAIL, "ACTIVATION_NOT_DARK"]
        result = self.judge(value=remote(readiness=readiness_with(full=report(OP.FULL, package={"checks": checks}))))
        self.assertEqual(result["w14"], OP.W14_STOP)
        self.assertIn("FULL_CHECKS_NOT_ALL_PASS", result["reasons"])
        self.assertEqual(result["ownerInputChecks"]["E19_ACTIVATION_DARK"], PA.FAIL)
        self.assertIs(result["activationObservedLive"], False)

    def test_issuance_ready_is_a_fact_name_not_a_darkness_failure(self):
        self.assertIs(remote()["readiness"]["fullSummary"]["facts"]["issuanceReady"], True)
        self.assertEqual(self.judge()["w14"], OP.W14_1)

    # --- RELEASED record and hold set
    def test_a_wrong_released_record_or_hash_stops(self):
        self.assert_stop("HOLD_NOT_EXACTLY_THE_RELEASED", read(released_entries(witness="e" * 64)))

    def test_a_remaining_held_record_stops(self):
        self.assert_stop("HOLD_NOT_EXACTLY_THE_RELEASED", read(released_entries(SC.HELD)))
        extra = released_entries() + [("f" * 64 + ".json", released_entries(SC.HELD)[0][1])]
        self.assert_stop("HOLD_NOT_EXACTLY_THE_RELEASED", read(extra))
        held_in_package = report(OP.FULL, package={"evidence": {
            "holdStore": {"listingDigest": EXP["released"]["listingDigest"],
                          "records": [[EXP["ceremonyId"], "INITIAL_CUSTODY", "RELEASED"],
                                      ["other", "INITIAL_CUSTODY", "HELD"]]},
            "witness": report(OP.FULL)["package"]["evidence"]["witness"]}})
        self.assert_stop("FULL_PACKAGE_HOLD_NOT_THE_RELEASED", value=remote(readiness=readiness_with(full=held_in_package)))

    def test_a_readiness_hold_listing_other_than_the_released_stops(self):
        self.assert_stop("READINESS_HOLD_LISTING_NOT_THE_RELEASED",
                         value=remote(readiness=readiness_with(holdListingDigest=EXP["held"]["listingDigest"])))

    # --- FULL_READINESS
    def test_full_not_ready_or_with_reasons_stops(self):
        not_ready = report(OP.FULL, package={"status": "NOT_READY"}, reasons=["E05_CREDENTIAL_INVENTORY:X"])
        self.assert_stop("FULL_NOT_READY", value=remote(readiness=readiness_with(full=not_ready)))
        self.assert_stop("FULL_READINESS_NOT_READY", value=remote(readiness=readiness_with(
            fullSummary=summary(OP.FULL, status="NOT_READY", reasons=["CEREMONY_HOLD:CEREMONY_HOLD_HELD"]))))
        failing = copy.deepcopy(report(OP.FULL)["package"]["checks"])
        failing["E19_ACTIVATION_DARK"] = [PA.FAIL, "ACTIVATION_NOT_DARK"]
        self.assert_stop("FULL_CHECKS_NOT_ALL_PASS",
                         value=remote(readiness=readiness_with(full=report(OP.FULL, package={"checks": failing}))))

    @staticmethod
    def adjudicated(identifier: str, **evidence_change) -> dict:
        """A FULL report whose E-22 is OWNER_RISK_ADJUDICATED, written as `pr1_acceptance` writes it."""
        checks = copy.deepcopy(report(OP.FULL)["package"]["checks"])
        checks["E22_SECRET_HYGIENE"] = [PA.OWNER_RISK_ADJUDICATED, identifier]
        evidence = copy.deepcopy(report(OP.FULL)["package"]["evidence"])
        evidence["secretHygieneAdjudication"] = {
            "status": PA.OWNER_RISK_ADJUDICATED, "decision": "OD-M12-10", "adjudicationSha256": identifier,
            "ownerRecordSha256": PA.ACCEPTED_E22_ADJUDICATIONS.get(identifier, "f" * 64),
            "keyId": PA.E22_ADJUDICATION_KEY_ID, "transcriptSha256": "e" * 64,
            "failures": list(PA.E22_ADJUDICATED_FAILURES), "nonclaim": PA.E22_ADJUDICATION_NONCLAIM,
            **evidence_change}
        return report(OP.FULL, package={"checks": checks, "evidence": evidence,
                                        "nonclaims": [PA.E22_ADJUDICATION_NONCLAIM]})

    def test_the_accepted_e22_adjudication_is_admitted_and_nothing_else(self):
        self.assertEqual(OP.ADJUDICATED_E22, PA.OWNER_RISK_ADJUDICATED)
        (accepted,) = PA.ACCEPTED_E22_ADJUDICATIONS                       # the one owner-accepted OD-M12-10 identity
        result = self.judge(value=remote(readiness=readiness_with(full=self.adjudicated(accepted))))
        self.assertEqual((result["w14"], result["reasons"]), (OP.W14_1, []))
        self.assertEqual(result["ownerInputChecks"]["E22_SECRET_HYGIENE"], PA.OWNER_RISK_ADJUDICATED)   # never PASS
        checks = copy.deepcopy(report(OP.FULL)["package"]["checks"])
        checks["E21_OFFHOST_REGISTER"] = [OP.ADJUDICATED_E22, accepted]
        self.assert_stop("FULL_CHECKS_NOT_ALL_PASS",
                         value=remote(readiness=readiness_with(full=report(OP.FULL, package={"checks": checks}))))

    def test_a_fabricated_or_unaccepted_e22_adjudication_stops(self):
        (accepted,) = PA.ACCEPTED_E22_ADJUDICATIONS
        for full in (self.adjudicated("0" * 64),                                   # well-formed, not accepted
                     self.adjudicated("JOURNAL_SECRET_SCAN"),                       # not an identity at all
                     self.adjudicated(accepted, ownerRecordSha256="f" * 64),        # wrong owner record
                     self.adjudicated(accepted, nonclaim="a clean scan"),           # nonclaim dropped
                     report(OP.FULL, package={"checks": {**self.adjudicated(accepted)["package"]["checks"]}})):
            self.assert_stop("FULL_E22_ADJUDICATION_NOT_ACCEPTED", value=remote(readiness=readiness_with(full=full)))

    def test_a_package_digest_that_does_not_reproduce_stops(self):
        tampered = report(OP.FULL)
        tampered["package"]["nonclaims"] = ["edited after digesting"]
        self.assert_stop("FULL_PACKAGE_DIGEST_NOT_REPRODUCED", value=remote(readiness=readiness_with(full=tampered)))
        self.assert_stop("FULL_PACKAGE_DIGEST_NOT_REPRODUCED",
                         value=remote(readiness=readiness_with(full=report(OP.FULL, packageDigest="0" * 64))))

    def test_a_loaded_key_binding_other_than_pass_stops(self):
        self.assert_stop("FULL_LOADED_KEY_BINDING_NOT_PASS", value=remote(readiness=readiness_with(
            fullSummary=summary(OP.FULL, loadedKeyBinding={"status": "FAIL", "reason": "HEALTH_FINGERPRINT_MISMATCH"}))))

    def test_a_moved_witness_head_stops(self):
        moved = report(OP.FULL, package={"evidence": {**report(OP.FULL)["package"]["evidence"],
                                                      "witness": {"classification": "CONSISTENT", "chainLength": 2,
                                                                  "headDigest": "a" * 64,
                                                                  "genesisDigest": EXP["genesis"]}}})
        self.assert_stop("FULL_WITNESS_HEAD_NOT_GENESIS", value=remote(readiness=readiness_with(full=moved)))

    # --- HOLD_RELEASE_ELIGIBILITY after RELEASED
    def test_eligibility_must_be_not_ready_for_exactly_the_released_hold(self):
        self.assert_stop("ELIGIBILITY_NOT_EXACTLY_THE_RELEASED_HOLD",
                         value=remote(readiness=readiness_with(eligibility=report(OP.FULL) | {"mode": OP.ELIGIBILITY})))
        other = report(OP.ELIGIBILITY, reasons=["E16_HOLD_STORE:CEREMONY_HOLD:HOLD_NOT_HELD"])
        self.assert_stop("ELIGIBILITY_NOT_EXACTLY_THE_RELEASED_HOLD", value=remote(readiness=readiness_with(eligibility=other)))
        self.assert_stop("ELIGIBILITY_READINESS_NOT_EXACTLY_HOLD_NOT_HELD", value=remote(readiness=readiness_with(
            eligibilitySummary=summary(OP.ELIGIBILITY, status="READY", reasons=[]))))

    # --- identities and incarnations
    def test_a_changed_signer_incarnation_stops(self):
        other = ("7" * 32, "99999")
        self.assert_stop("UNITS_SIGNER_NOT_THE_ACCEPTED_INCARNATION", read(signer=list(other)))
        changed = remote()
        changed["signer"]["units"] = signer_units(other)
        self.assert_stop("SIGNER_NOT_THE_ACCEPTED_INCARNATION", value=changed)
        restarted = remote()
        restarted["signer"]["units"][W.SIGNER_SERVICE]["NRestarts"] = "1"
        self.assert_stop("SIGNER_NOT_THE_ACCEPTED_INCARNATION", value=restarted)
        moved = remote()
        moved["healthCapture"]["after"] = {"InvocationID": other[0], "MainPID": other[1]}
        self.assert_stop("HEALTH_NOT_BOUND_TO_THE_ACCEPTED_INCARNATION", value=moved)

    def test_a_changed_witness_incarnation_stops(self):
        self.assert_stop("UNITS_WITNESS_NOT_THE_ACCEPTED_INCARNATION", read(witness=["9" * 32, "1"]))

    def test_another_release_process_or_credentials_or_boundary_stops(self):
        value = remote()
        value["signer"]["process"]["cwd"] = "/opt/lilith-authority-dev/releases/" + "b" * 40
        self.assert_stop("PROCESS_NOT_THE_RELEASE_SIGNER", value=value)
        value = remote()
        value["signer"]["paths"]["credentials"]["names"] = [W.CREDENTIAL_NAME, "extra"]
        self.assert_stop("CREDENTIALS_DIRECTORY_NOT_EXACTLY_ONE_NAME", value=value)
        self.assert_stop("RESTART_BOUNDARY_NOT_EFFECTIVE", value=remote(restartBoundary={"error": "OSError"}))
        self.assert_stop("LEDGER_NOT_EXACTLY_THE_DATABASE", value=remote(
            ledger={"readable": True, "listing": {W.LEDGER_NAME: 1, W.WAL_NAME: 0}, "dbSha256": "c" * 64}))

    def test_a_health_other_than_h_or_another_key_stops(self):
        value = remote()
        value["healthCapture"]["health"] = {**health(), "readiness": "READY"}
        self.assert_stop("HEALTH_FIELD", value=value)
        value = remote()
        value["healthCapture"]["health"] = {**health(), "publicKeySha256": "a" * 64}
        self.assert_stop("HEALTH_FINGERPRINT_NOT_B3", value=value)

    # --- authority
    def test_authority_unexpectedly_active_stops(self):
        granted = report(OP.FULL, package={"authorityGranted": True})
        self.assert_stop("FULL_AUTHORITY_NOT_DARK", value=remote(readiness=readiness_with(full=granted)))
        wired = report(OP.FULL, package={"issuanceWired": True})
        self.assert_stop("FULL_AUTHORITY_NOT_DARK", value=remote(readiness=readiness_with(full=wired)))
        live = summary(OP.FULL, facts={**summary(OP.FULL)["facts"], "liveEntryAuthorized": True})
        self.assert_stop("FULL_AUTHORITY_NOT_DARK", value=remote(readiness=readiness_with(fullSummary=live)))
        self.assert_stop("FULL_REMOTE_NOT_RECEIVED", value=remote(authorityGranted=True))

    def test_darkness_facts_must_be_explicitly_false(self):
        for mode, key in ((OP.FULL, "fullSummary"), (OP.ELIGIBILITY, "eligibilitySummary")):
            tag = "FULL" if mode == OP.FULL else "ELIGIBILITY"
            for fact in OP.DARK_FALSE_FACTS:
                missing = {k: v for k, v in summary(mode)["facts"].items() if k != fact}
                for facts in (missing, {**summary(mode)["facts"], fact: None}, {**summary(mode)["facts"], fact: True}):
                    self.assert_stop(f"{tag}_AUTHORITY_NOT_DARK",
                                     value=remote(readiness=readiness_with(**{key: summary(mode, facts=facts)})))
        relaxed = {**summary(OP.FULL)["facts"]}                     # readiness facts: reported, never darkness
        relaxed.pop("successorCurrent")
        relaxed["issuanceReady"] = None
        self.assertEqual(self.judge(value=remote(readiness=readiness_with(
            fullSummary=summary(OP.FULL, facts=relaxed))))["w14"], OP.W14_1)

    # --- missing / inconsistent evidence
    def test_missing_or_incomplete_evidence_is_never_success(self):
        result = OP.judge(read(), None)
        self.assertEqual(result["w14"], OP.W14_STOP)
        self.assertIn("FULL_REMOTE_NOT_RECEIVED", result["reasons"])
        self.assert_stop("READINESS_NOT_EVALUATED", value=remote(readiness=None))
        self.assert_stop("FULL_REPORT_MISSING", value=remote(readiness=readiness_with(full=None)))
        self.assert_stop("ELIGIBILITY_SUMMARY_MISSING", value=remote(readiness=readiness_with(eligibilitySummary=None)))
        self.assert_stop("SIGNER_UNOBSERVED", value=remote(signer={"units": None, "paths": {}}))
        self.assert_stop("HEALTH_NOT_CAPTURED", value=remote(healthCapture={"attempted": False, "before": None,
                                                                            "after": None, "health": None}))
        self.assert_stop("READBACK_NOT_COMPLETE", read(codes={"observe": 0, "stage": 1, "units": 0}))
        self.assert_stop("STAGING_PATH_NOT_ABSENT", read(stage="UNKNOWN"))
        self.assert_stop("HOLD_NOT_EXACTLY_THE_RELEASED", read(hold={"class": MB14.UNOBSERVABLE}))


class Dev:
    """A synthetic DEV behind the operator's transport: the hold store, the staging path, the units, the tail."""

    def __init__(self):
        self.entries = released_entries()
        self.remote = remote()
        self.calls: list[str] = []

    def invoke(self, command: str, stdin: bytes | None):
        self.calls.append(command)
        if command == MB14.OBSERVE_COMMAND:
            return done(0, observe_out(self.entries))
        if command == MB14.STAGE_COMMAND:
            return done(0, b"STAGE=absent\n")
        if command == MB14.UNITS_COMMAND:
            return done(0, (f"Id={MB14.E22.SIGNER_SERVICE}\nMainPID={OP.SIGNER[1]}\nInvocationID={OP.SIGNER[0]}\n\n"
                            f"Id={MB14.E22.WITNESS_SERVICE}\nMainPID={OP.WITNESS[1]}\n"
                            f"InvocationID={OP.WITNESS[0]}\n").encode())
        if stdin is not None and f"mb15_full_remote full {F.evidence_digest(DOC)}" in command:
            self.payload = stdin.rstrip(b"\n")
            assert f"grep -qx '{sha(self.payload)}' || exit 96" in command       # the host's payload check
            return done(0, json.dumps(self.remote).encode() + b"\n")
        raise AssertionError(command)


class FakeOperator(OP.Operator):
    def attach(self, dev: Dev) -> "FakeOperator":
        self.dev = dev
        return self

    def pins(self, repo):
        return {"control": "c" * 40, "operatorSha256": "d" * 64, "result": "MB15_TOOL_PINS_EXACT"}

    def owner_inputs(self, raw):
        assert raw == ENVELOPE
        return dict(INPUTS)

    def tool_bytes(self, repo, path):           # the REAL bundle, from this checkout's pinned bytes
        return OP.Operator.local_tool(path)

    def _invoke_once(self, command, stdin):
        return self.dev.invoke(command, stdin)


class OperatorFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "envelope.out").write_bytes(ENVELOPE)
        self.dev = Dev()
        self.op = FakeOperator().attach(self.dev)

    def observe(self):
        return self.op.observe(self.tmp / "repo", self.tmp / "w14", self.tmp / "envelope.out")

    def test_observe_is_read_only_judges_w14_and_classify_reproduces_it(self):
        result = self.observe()
        self.assertEqual((result["w14"], result["reasons"]), (OP.W14_1, []))
        self.assertEqual(self.dev.calls[:3], [MB14.OBSERVE_COMMAND, MB14.STAGE_COMMAND, MB14.UNITS_COMMAND])
        self.assertEqual(len(self.dev.calls), 4)
        self.assertEqual(result["envelopeSha256"], sha(ENVELOPE))
        self.assertEqual(result["codeIdentity"], {
            "operatorSha256": sha((TOOLS / "mb15_operator.py").read_bytes()),
            "toolPinsSha256": sha(json.dumps(OP.TOOL_PINS, sort_keys=True).encode("ascii")),
            "remoteSha256": OP.TOOL_PINS[OP.REMOTE], "bundlePayloadSha256": sha(self.dev.payload)})
        again = self.op.classify(self.tmp / "w14")                      # off-host: no invocation at all
        self.assertEqual(again["w14Sha256"], result["w14Sha256"])
        self.assertEqual(len(self.dev.calls), 4)

    def test_a_changed_transcript_or_envelope_stops_the_reproduction(self):
        self.observe()
        out = self.tmp / "w14" / "full.out"
        out.write_bytes(out.read_bytes().replace(b'"READY"', b'"NOT_READY"', 1))
        with self.assertRaises(OP.Stop) as caught:
            self.op.classify(self.tmp / "w14")
        self.assertEqual(caught.exception.code, "TRANSCRIPTS_CHANGED_OR_MISSING")

    def test_a_changed_envelope_stops_the_reproduction(self):
        self.observe()
        (self.tmp / "w14" / "envelope.out").write_bytes(b'{"envelopeType":"OTHER"}\n')
        with self.assertRaises(OP.Stop):
            self.op.classify(self.tmp / "w14")

    def test_an_old_envelope_can_be_observed_but_never_counts_as_freshness(self):
        result = self.observe()                    # any envelope the reader admits: currency is not judged here
        self.assertEqual(result["w14"], OP.W14_1)
        self.assertEqual(result["envelopeSha256"], sha(ENVELOPE))
        self.assertEqual((result["envelopeCurrency"], result["ownerFreshness"]), ("NOT_JUDGED", "NOT_EVALUATED"))
        self.assertIn("OWNER_INPUT_ENVELOPE_CURRENCY", result["outstanding"])
        self.assertIn("OWNER_FRESHNESS_CURRENT_S25_REPLICA_B", result["outstanding"])
        self.assertIs(result["mb15Established"], False)

    def stop_code(self):
        with self.assertRaises(OP.Stop) as caught:
            self.op.classify(self.tmp / "w14")
        return caught.exception.code

    def test_a_recorded_code_identity_other_than_this_code_is_rejected(self):
        self.observe()
        path = self.tmp / "w14" / OP.OBSERVATION_FILE
        observation = json.loads(path.read_bytes())
        observation["codeIdentity"]["bundlePayloadSha256"] = "0" * 64
        path.write_bytes(json.dumps(observation).encode())
        self.assertEqual(self.stop_code(), "CODE_NOT_THE_OBSERVED_CODE")
        del observation["codeIdentity"]
        path.write_bytes(json.dumps(observation).encode())
        self.assertEqual(self.stop_code(), "CODE_NOT_THE_OBSERVED_CODE")

    def test_a_classifier_running_other_code_is_rejected(self):
        self.observe()
        other = self.tmp / "mb15_operator.py"                   # a classifier that is not the observing operator
        other.write_bytes((TOOLS / "mb15_operator.py").read_bytes() + b"# changed\n")
        with mock.patch.object(OP, "__file__", str(other)):
            self.assertEqual(self.stop_code(), "CODE_NOT_THE_OBSERVED_CODE")
        changed = {OP.REMOTE: "1" * 64}                          # a different `full` tail pin
        with mock.patch.dict(OP.TOOL_PINS, changed):
            self.assertEqual(self.stop_code(), "TOOL_PIN_MISMATCH:" + OP.REMOTE)
        self.assertEqual(self.op.classify(self.tmp / "w14")["w14"], OP.W14_1)     # the observing code reproduces

    def test_a_remote_echoing_other_evidence_is_not_received(self):
        self.dev.remote = remote(evidenceSha256="0" * 64)
        result = self.observe()
        self.assertEqual(result["w14"], OP.W14_STOP)
        self.assertIn("FULL_REMOTE_NOT_RECEIVED", result["reasons"])

    def test_a_held_store_on_dev_stops(self):
        self.dev.entries = released_entries(SC.HELD)
        result = self.observe()
        self.assertEqual(result["w14"], OP.W14_STOP)
        self.assertIn("HOLD_NOT_EXACTLY_THE_RELEASED:HELD_UNCHANGED", result["reasons"])

    def test_an_existing_outdir_is_refused(self):
        (self.tmp / "w14").mkdir()
        with self.assertRaises(OP.Stop):
            self.observe()
        self.assertEqual(self.dev.calls, [])


class RecordTests(unittest.TestCase):
    def test_the_record_keeps_m_b15_open(self):
        text = RECORD.read_text(encoding="utf-8")
        for value in (OP.W14_1, "bb7576f4437fb61dd31adafe50ac56eba467c7f98b329b7149942e630f1ef003",
                      "c4cb131983b450d1e931d1121e5b125a98c2dc1625934db0ff0a5f3f661e195c", "NOT AUTHORIZED",
                      "OUTSTANDING", OP.TOOL_PINS[OP.REMOTE], OP.ACTIVATION_SOURCE, "CODE_NOT_THE_OBSERVED_CODE",
                      "activationObservedLive"):
            self.assertIn(value, text)
        for claim in ("M-B15 = COMPLETED", "FULL_READINESS = ESTABLISHED", "AUTHORITY = ACTIVE"):
            self.assertNotIn(claim, text)


# ---------------------------------------------------------- contract layer (synthetic PR-1 host) ---

if HAVE_CRYPTO and POSIX:
    import pr1s_fixtures as X
    import install_authority_dev as I
    from lilith_authority_root import verifier as RV
    from lilith_owner_memory import successor_readiness as SR


@unittest.skipUnless(HAVE_CRYPTO and POSIX, "POSIX owner/mode semantics and cryptography/rfc8785/fido2 required")
class SyntheticHostFullReadinessTests(unittest.TestCase):
    """The REAL release verifier in both modes through the tail's `both_modes`, on the synthetic PR-1 host before and
    after a REAL `release_initial`; the W14 package and summary judges over the real reports (environment `test`)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.host = X.Pr1Host(self.tmp.name).genesis_host()
        with X.stand_in_wheels() as wheels:
            payloads = X.release_payloads(wheels)
        manifest = X.install_release(self.host.root, X.RELEASE_SHA, payloads)
        self.owner = X.verifier_inputs(self.host, manifest_sha256=sha(I.canonical(manifest)),
                                       first_current=X.current_document(self.host), with_pr2=True, with_pr3=True)
        self.health = X.health_p0()

    def tearDown(self):
        self.tmp.cleanup()

    def both(self):
        return F.both_modes(self.host.root, owner_uid=X.UID, owner_gid=X.GID, run=X.fake_systemctl())(
            self.owner, self.health)

    def expected(self, readiness):
        evidence = readiness["full"]["package"]["evidence"]
        return {"environment": X.ENV, "genesis": evidence["witness"]["genesisDigest"],
                "ceremonyId": SC.initial_ceremony_id(X.ENV, SC.custody_profile(X.ENV).initial_key_id),
                "released": {"listingDigest": readiness["holdListingDigest"]}}

    def test_held_then_released_through_the_real_verifier(self):
        held = self.both()
        self.assertEqual(held["eligibility"]["status"], "READY", held["eligibility"]["reasons"])
        self.assertIn("FULL_READINESS_NOT_READY", OP.judge_summary(held["fullSummary"], OP.FULL))
        owner = RV.parse_verifier_inputs(self.owner)
        self.host.holds.release_initial(
            approved_package_digest=held["eligibility"]["packageDigest"],
            rerun=lambda hold: RV.evaluate(SR.HOLD_RELEASE_ELIGIBILITY, owner, root=self.host.root, owner_uid=X.UID,
                                           owner_gid=X.GID, health=lambda: dict(self.health), run=X.fake_systemctl(),
                                           hold=hold),
            witness_store=self.host.witness_store(), context=self.host.context())
        released = self.both()
        exp = self.expected(released)
        self.assertEqual(OP.judge_package(released["full"], OP.FULL, exp), [])
        self.assertEqual(OP.judge_package(released["eligibility"], OP.ELIGIBILITY, exp), [])
        self.assertEqual(OP.judge_summary(released["fullSummary"], OP.FULL), [])
        self.assertEqual(OP.judge_summary(released["eligibilitySummary"], OP.ELIGIBILITY), [])
        self.assertEqual(tuple(released["eligibility"]["reasons"]), OP.ELIGIBILITY_PACKAGE_REASONS)
        self.assertEqual(tuple(released["eligibilitySummary"]["reasons"]), OP.ELIGIBILITY_READINESS_REASONS)
        self.assertIs(released["fullSummary"]["facts"]["issuanceReady"], True)    # a fact name; issuance unwired
        self.assertIs(released["full"]["package"]["issuanceWired"], False)
        self.assertNotEqual(released["full"]["packageDigest"], held["eligibility"]["packageDigest"])


if __name__ == "__main__":
    unittest.main()
