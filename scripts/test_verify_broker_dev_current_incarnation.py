"""Fixture regressions for the read-only DR-1 current-incarnation baseline."""

from __future__ import annotations

import ast
import copy
import json
import unittest
from pathlib import Path

from scripts import memory_broker_stage3_forensics as forensics
from scripts import verify_broker_dev_current_incarnation as gate
from scripts import verify_broker_dev_lifecycle as lifecycle

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "scripts/verify_broker_dev_current_incarnation.py").read_text(encoding="utf-8")
CURRENT_INVOCATION = "42af2691b8d24ee5a92a286197c5444c"
BOOT_ID = "24d1771d-e1b5-4e5f-816d-da08ad8b367a"
EXPAT = "/usr/lib/x86_64-linux-gnu/libexpat.so.1.9.1"


def contract_files(contract: dict) -> dict:
    return {path: {"present": True, "sha256": sha, "uid": uid, "gid": gid, "mode": mode}
            for path, (sha, uid, gid, mode) in contract.items()}


def observation() -> dict:
    """Facts as read on DEV by the DR-1 forensics, 2026-09-26 (UTC)."""
    service = {**gate.SERVICE_EXPECTED, **gate.SANDBOX_EXPECTED, "MainPID": "132976",
               "InvocationID": CURRENT_INVOCATION,
               "ExecMainStartTimestamp": "Sat 2026-09-26 06:34:09 UTC"}
    return {
        "host": {"hostname": gate.DEV_INSTANCE, "fqdn": gate.DEV_HOSTNAME,
                 "machineId": gate.DEV_MACHINE_ID, "instanceName": gate.DEV_INSTANCE,
                 "instanceId": gate.DEV_INSTANCE_ID, "bootId": BOOT_ID},
        "units": {
            gate.SERVICE: service,
            gate.SOCKET: {**gate.SOCKET_EXPECTED, "InvocationID": "1434eda774ed4d8296bc4e266191bc67"},
            gate.CONTROLLER: dict(gate.CONTROLLER_EXPECTED),
        },
        "release": {"target": f"releases/{gate.RELEASE_SHA}", "linkOwner": [0, 0],
                    "manifestSha256": gate.MANIFEST_SHA, "payloadCount": 23, "payloadMismatches": []},
        "files": {**contract_files(gate.UNIT_FILES), **contract_files(gate.CONFIG_FILES),
                  **contract_files(gate.STATE_FILES)},
        "directories": {path: {"present": True, "uid": u, "gid": g, "mode": m}
                        for path, (u, g, m) in gate.DIRECTORIES.items()},
        "accounts": {"broker": {"uid": 999, "gid": 987, "home": "/nonexistent",
                                "shell": "/usr/sbin/nologin", "groups": [987]},
                     "ipc": {"gid": 988, "members": ["lilith-memory-relay"]}},
        "process": {
            "pid": 132976,
            "status": {"uid": [999] * 4, "gid": [987] * 4, "groups": [987], "ppid": 1,
                       "noNewPrivs": "1", "seccomp": "2",
                       "capabilities": {name: "0000000000000000"
                                        for name in ("CapPrm", "CapEff", "CapBnd", "CapAmb")}},
            "cmdline": gate.BROKER_CMDLINE, "exe": "/usr/bin/python3.12",
            "cwd": str(gate.ROOT / "releases" / gate.RELEASE_SHA),
            "startTicks": 108370000, "startTime": "2026-09-26T06:34:09Z",
        },
        "libraries": {
            "/usr/bin/python3.12": {"inode": 1001, "diskInode": 1001, "deleted": False, "sha256": "a" * 64},
            EXPAT: {"inode": 2002, "diskInode": 2002, "deleted": False, "sha256": "b" * 64},
        },
        "brokerProcesses": [132976],
        "runtimeDirectory": {"present": True, "uid": 0, "gid": 988, "mode": 0o710},
        "ownerSocket": {"present": True, "type": "socket", "uid": 999, "gid": 988,
                        "mode": 0o660, "listening": True},
        "stage3": {"vault": {"present": True, "uid": 0, "gid": 0, "mode": 0o700},
                   "journal": dict(gate.STAGE3_JOURNAL), "phases": ["INTENT"],
                   "present": dict(gate.STAGE3_PRESENT),
                   "absent": {path: True for path in gate.STAGE3_ABSENT}},
        "deployer": {"sudoers": {"present": True, "exactText": True, "uid": 0, "gid": 0, "mode": 0o440},
                     "helperSha256": gate.DEPLOY_HELPER_SHA},
        "custodyPaths": {path: {"present": False} for path in gate.CUSTODY_PATHS},
        "ubuntu": {"present": True, "groups": ["adm", "cdrom", "dip", "lxd", "sudo", "ubuntu"],
                   "rootEquivalentGroups": ["lxd", "sudo"], "passwordLocked": True,
                   "authorizedKeysBytes": 0},
        "needrestart": {"installed": True, "restartMode": "DEFAULT",
                        "serviceSpecificExclusion": {name: False for name in gate.AUTHORITY_SENSITIVE_SERVICES}},
    }


def walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


class BaselineResultTests(unittest.TestCase):
    def test_observed_dev_facts_produce_a_separate_pass_candidate(self) -> None:
        result = gate.evaluate(observation())
        self.assertEqual(result["CURRENT_RUNTIME_BASELINE"], "PASS", result["failures"])
        for key in ("releaseEquivalent", "configEquivalent", "stateEquivalent",
                    "identityBoundaryEquivalent", "socketBoundaryEquivalent", "stageIIIUntouched",
                    "deployerPolicyTextEquivalent", "incarnationHealthy"):
            self.assertIs(result[key], True, key)
        self.assertIs(result["processContinuity"], False)
        self.assertEqual(result["runtimeIncarnation"], CURRENT_INVOCATION)
        self.assertEqual(result["bootId"], BOOT_ID)
        self.assertEqual(result["startTime"], "2026-09-26T06:34:09Z")
        self.assertEqual(result["runtimeBehavioralEquivalence"], "NOT_PROVEN_BY_OBSERVATION")
        self.assertEqual(result["ownerAcceptance"], "PENDING_SEPARATE_EXPLICIT_OWNER_DECISION")
        self.assertRegex(result["baselineCandidateSha256"], r"^[0-9a-f]{64}$")
        libraries = [item["path"] for item in result["baselineCandidate"]["sharedLibraries"]]
        self.assertIn(EXPAT, libraries)

    def test_never_claims_stage_ii_acceptance(self) -> None:
        for obs in (observation(), {}):
            result = gate.evaluate(obs)
            text = json.dumps(result)
            self.assertNotIn("STAGE_II_ACCEPTED", text)
            self.assertNotIn("stageIIAccepted", set(walk_keys(result)))
            self.assertTrue(result["stageIIAcceptance"].startswith("HISTORICAL_RECORD_UNCHANGED"))

    def test_process_continuity_is_reported_not_required(self) -> None:
        obs = observation()
        obs["units"][gate.SERVICE]["InvocationID"] = gate.ACCEPTED_SERVICE_INVOCATION
        obs["units"][gate.SERVICE]["MainPID"] = str(gate.ACCEPTED_BROKER_PID)
        obs["process"].update(pid=gate.ACCEPTED_BROKER_PID, startTicks=gate.ACCEPTED_BROKER_START_TICKS)
        obs["brokerProcesses"] = [gate.ACCEPTED_BROKER_PID]
        result = gate.evaluate(obs)
        self.assertIs(result["processContinuity"], True)
        self.assertEqual(result["CURRENT_RUNTIME_BASELINE"], "PASS")
        self.assertNotIn("STAGE_II_ACCEPTED", json.dumps(result))

    def test_empty_observation_fails_closed(self) -> None:
        result = gate.evaluate({})
        self.assertEqual(result["CURRENT_RUNTIME_BASELINE"], "FAIL")
        self.assertIsNone(result["baselineCandidateSha256"])
        self.assertIn("HOST_MISMATCH", result["failures"])


class DriftDetectionTests(unittest.TestCase):
    def assertFails(self, mutate, code: str) -> None:
        obs = observation()
        mutate(obs)
        result = gate.evaluate(obs)
        self.assertEqual(result["CURRENT_RUNTIME_BASELINE"], "FAIL")
        self.assertIn(code, result["failures"])
        self.assertIsNone(result["baselineCandidateSha256"])

    def test_prod_host_is_rejected(self) -> None:
        def prod(o):
            o["host"].update(hostname="lilith-01", instanceName="lilith-01",
                             fqdn=f"lilith-01.{gate.ZONE}.c.{gate.PROJECT}.internal")
        self.assertFails(prod, "HOST_MISMATCH")

    def test_release_drift(self) -> None:
        cand = "4a04f2d09a2b32aecedfe777090fd2e1a27ec909"
        self.assertFails(lambda o: o["release"].update(target=f"releases/{cand}"), "RELEASE_SELECTOR_CHANGED")
        self.assertFails(lambda o: o["release"].update(manifestSha256="0" * 64), "RELEASE_MANIFEST_CHANGED")
        self.assertFails(lambda o: o["release"].update(payloadMismatches=["x.py"]), "RELEASE_PAYLOAD_CHANGED")
        self.assertFails(lambda o: o["process"].update(cwd=f"/opt/lilith-memory-broker/releases/{cand}"),
                         "PROCESS_NOT_ON_SELECTED_RELEASE")

    def test_file_config_and_state_drift(self) -> None:
        unit = "/etc/systemd/system/lilith-memory-broker.service"
        self.assertFails(lambda o: o["files"][unit].update(sha256="0" * 64), "UNIT_FILE_CHANGED")
        self.assertFails(lambda o: o["files"][str(gate.CONFIG / "dev.json")].update(mode=0o644),
                         "BROKER_CONFIG_CHANGED")
        self.assertFails(lambda o: o["files"][str(gate.OWNER_DB)].update(sha256="0" * 64),
                         "BROKER_STATE_CHANGED")
        self.assertFails(lambda o: o["directories"][str(gate.CONFIG)].update(mode=0o777),
                         "DIRECTORY_CUSTODY_CHANGED")

    def test_identity_and_sandbox_drift(self) -> None:
        self.assertFails(lambda o: o["accounts"]["broker"].update(groups=[987, 27]), "BROKER_ACCOUNT_CHANGED")
        self.assertFails(lambda o: o["process"]["status"].update(uid=[0] * 4), "BROKER_PROCESS_IDENTITY_CHANGED")
        self.assertFails(lambda o: o["process"]["status"]["capabilities"].update(CapBnd="000001ffffffffff"),
                         "BROKER_PROCESS_PRIVILEGE_CHANGED")
        self.assertFails(lambda o: o["units"][gate.SERVICE].update(ProtectSystem="full"), "BROKER_SANDBOX_CHANGED")
        self.assertFails(lambda o: o["units"][gate.SERVICE].update(DropInPaths="/run/x.conf"),
                         "BROKER_SERVICE_STATE_UNEXPECTED")

    def test_socket_boundary_drift(self) -> None:
        self.assertFails(lambda o: o["units"][gate.SOCKET].update(SocketMode="0666"), "SOCKET_UNIT_CHANGED")
        self.assertFails(lambda o: o["ownerSocket"].update(gid=0), "OWNER_SOCKET_CHANGED")
        self.assertFails(lambda o: o["ownerSocket"].update(listening=False), "OWNER_SOCKET_CHANGED")
        self.assertFails(lambda o: o["runtimeDirectory"].update(mode=0o755), "RUNTIME_DIRECTORY_CHANGED")

    def test_stage_iii_drift(self) -> None:
        def quiesced(o):
            o["stage3"]["journal"]["001-QUIESCED.json"] = "c" * 64
            o["stage3"]["phases"].append("QUIESCED")
        self.assertFails(quiesced, "STAGE3_JOURNAL_CHANGED")
        self.assertFails(lambda o: o["stage3"]["absent"].update({gate.STAGE3_ABSENT[0]: False}),
                         "STAGE3_ARM_GUARD_OR_CONSUMPTION_PRESENT")
        self.assertFails(lambda o: o["stage3"]["absent"].update({"/run/lilith-memory-stage3/a2-arm.json": False}),
                         "STAGE3_ARM_GUARD_OR_CONSUMPTION_PRESENT")
        auth = str(gate.CONFIG / "b1b2b-stage3-a2-authorization.json")
        self.assertFails(lambda o: o["stage3"]["present"].update({auth: None}), "STAGE3_ARTIFACT_CHANGED")
        self.assertFails(lambda o: o["units"][gate.CONTROLLER].update(ActiveState="active"),
                         "STAGE3_CONTROLLER_CHANGED")

    def test_deployer_policy_drift(self) -> None:
        self.assertFails(lambda o: o["deployer"]["sudoers"].update(exactText=False), "DEPLOYER_POLICY_CHANGED")
        self.assertFails(lambda o: o["deployer"].update(helperSha256="0" * 64), "DEPLOYER_POLICY_CHANGED")

    def test_runtime_incarnation_drift(self) -> None:
        self.assertFails(lambda o: o["units"][gate.SERVICE].update(NRestarts="1"), "BROKER_SERVICE_STATE_UNEXPECTED")
        self.assertFails(lambda o: o["units"][gate.SERVICE].update(InvocationID=""), "INVOCATION_ID_INVALID")
        self.assertFails(lambda o: o.update(brokerProcesses=[132976, 140000]), "BROKER_PROCESS_AMBIGUOUS")
        self.assertFails(lambda o: o["libraries"][EXPAT].update(deleted=True, sha256=None),
                         "RUNTIME_SUBSTRATE_STALE_OR_UNREADABLE")
        self.assertFails(lambda o: o["libraries"][EXPAT].update(diskInode=9999),
                         "RUNTIME_SUBSTRATE_STALE_OR_UNREADABLE")


class NoFalseDenialTests(unittest.TestCase):
    def test_missing_custody_paths_are_not_yet_present_never_denied(self) -> None:
        result = gate.evaluate(observation())
        self.assertEqual(set(result["custodyPaths"].values()), {"NOT_YET_PRESENT"})
        self.assertNotIn("DENIED", json.dumps(result))
        self.assertEqual(result["informational"]["sudoAsBrokerDenial"], "NOT_TESTED_DR5_OPEN")
        self.assertEqual(result["informational"]["deployerBoundary"], "POLICY_TEXT_ONLY_NOT_A_DENIAL_PROOF")

    def test_present_custody_path_before_b1b3d_fails(self) -> None:
        obs = observation()
        obs["custodyPaths"]["/etc/lilith-authority-dev"] = {"present": True, "uid": 0, "gid": 0, "mode": 0o755}
        result = gate.evaluate(obs)
        self.assertIn("CUSTODY_PATH_PRESENT_BEFORE_B1B3D", result["failures"])
        self.assertEqual(result["custodyPaths"]["/etc/lilith-authority-dev"], "PRESENT")

    def test_unobserved_custody_path_is_not_treated_as_absent(self) -> None:
        obs = observation()
        del obs["custodyPaths"]["/var/lib/lilith-recovery-witness"]
        self.assertIn("CUSTODY_PATH_PRESENT_BEFORE_B1B3D", gate.evaluate(obs)["failures"])


L1B1_CUSTODY = {  # legitimate B1b-3d state at L1b.1 as seen by this observer
    "/opt/lilith-authority-dev": {"present": True, "uid": 0, "gid": 0, "mode": 0o755},
}
LEGACY_EMPTY_FAILURE_ORDER = [  # `baseline` failure order on an empty observation, as on origin/main 9ac7de2
    "HOST_MISMATCH", "RELEASE_SELECTOR_CHANGED", "RELEASE_MANIFEST_CHANGED", "RELEASE_PAYLOAD_CHANGED",
    "PROCESS_NOT_ON_SELECTED_RELEASE", "UNIT_FILE_CHANGED", "BROKER_CONFIG_CHANGED", "DIRECTORY_CUSTODY_CHANGED",
    "BROKER_STATE_CHANGED", "BROKER_ACCOUNT_CHANGED", "IPC_GROUP_CHANGED", "BROKER_PROCESS_IDENTITY_CHANGED",
    "BROKER_PROCESS_PRIVILEGE_CHANGED", "BROKER_SANDBOX_CHANGED", "SOCKET_UNIT_CHANGED", "RUNTIME_DIRECTORY_CHANGED",
    "OWNER_SOCKET_CHANGED", "STAGE3_JOURNAL_CHANGED", "STAGE3_ARTIFACT_CHANGED",
    "STAGE3_ARM_GUARD_OR_CONSUMPTION_PRESENT", "STAGE3_CONTROLLER_CHANGED", "DEPLOYER_POLICY_CHANGED",
    "CUSTODY_PATH_PRESENT_BEFORE_B1B3D", "RUNTIME_SUBSTRATE_STALE_OR_UNREADABLE",
    "BROKER_SERVICE_STATE_UNEXPECTED", "INVOCATION_ID_INVALID", "BROKER_PROCESS_AMBIGUOUS",
]


def with_l1b1_custody(obs: dict) -> dict:
    obs["custodyPaths"].update(copy.deepcopy(L1B1_CUSTODY))
    return obs


IDENTITY_KEYS = ("bootId", "pid", "startTicks", "nRestarts", "releaseSha", "manifestSha256", "sharedLibrariesSha256")


def identity_of(obs: dict) -> dict:
    candidate = gate.evaluate(copy.deepcopy(obs))["baselineCandidate"]
    return {key: candidate[key] for key in IDENTITY_KEYS}


def preserve(obs: dict) -> dict:
    """Evaluate `preservation` with the pre-reboot fixture's own accepted pins,
    including its (pre-reboot, failed) Stage III controller contract."""
    accepted = gate.evaluate(observation())["baselineCandidateSha256"]
    return gate.evaluate_preservation(obs, accepted_incarnation=CURRENT_INVOCATION,
                                      accepted_candidate_sha256=accepted,
                                      accepted_identity=identity_of(observation()),
                                      controller_expected=gate.CONTROLLER_EXPECTED)


class LegacyBaselineUnchangedTests(unittest.TestCase):
    """N-45: `baseline` keeps its historical pre-custody semantics exactly."""

    def test_baseline_still_rejects_legitimate_custody_presence(self) -> None:
        result = gate.evaluate(with_l1b1_custody(observation()))
        self.assertEqual(result["CURRENT_RUNTIME_BASELINE"], "FAIL")
        self.assertEqual(result["failures"], ["CUSTODY_PATH_PRESENT_BEFORE_B1B3D"])
        self.assertIsNone(result["baselineCandidateSha256"])
        self.assertEqual(result["operation"], "READ_ONLY_OBSERVATION")

    def test_baseline_failure_order_is_unchanged(self) -> None:
        self.assertEqual(gate.evaluate({})["failures"], LEGACY_EMPTY_FAILURE_ORDER)

    def test_only_three_fixed_operations_and_no_bypass(self) -> None:
        self.assertEqual(set(gate.OPERATIONS), {"baseline", "preservation", "rebaseline"})
        for argv in ([], ["baseline", "--ignore-failure"], ["preservation", "--allow-path", "/opt"],
                     ["preservation", "--force"], ["--ignore-failure"], ["bypass"], ["PRESERVATION"],
                     ["rebaseline", "--boot-id", BOOT_ID], ["rebaseline", "--accept"], ["REBASELINE"]):
            with self.assertRaises(gate.BaselineError):
                gate.main(argv)
        tree = ast.parse(SOURCE)
        for node in ast.walk(tree):  # scan code only, not the docstrings that explain the rule
            body = getattr(node, "body", None)
            if (isinstance(body, list) and body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str)):
                body[0] = ast.Pass()
        code = ast.unparse(tree)
        for token in ("ignore", "allow_path", "allow-path", "bypass", "skip", "--force", "argparse"):
            self.assertNotIn(token, code.lower(), token)
        self.assertNotIn("os.environ", code)  # no environment-driven switch either


class PreservationTests(unittest.TestCase):
    def test_accepts_legitimate_l1b1_custody_when_broker_is_unchanged(self) -> None:
        result = preserve(with_l1b1_custody(observation()))
        self.assertEqual(result["BROKER_PRESERVATION"], "PASS", result["failures"])
        self.assertTrue(result["baselineCandidateMatchesAccepted"])
        self.assertEqual(result["runtimeIncarnation"], CURRENT_INVOCATION)
        self.assertEqual(result["operation"], "READ_ONLY_BROKER_PRESERVATION")
        for key in ("releaseEquivalent", "configEquivalent", "stateEquivalent", "identityBoundaryEquivalent",
                    "socketBoundaryEquivalent", "stageIIIUntouched", "deployerPolicyTextEquivalent",
                    "incarnationHealthy"):
            self.assertIs(result[key], True, key)

    def test_candidate_is_always_produced_and_hashed(self) -> None:
        for obs in (with_l1b1_custody(observation()), {}):
            result = preserve(obs)
            self.assertRegex(result["baselineCandidateSha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(result["baselineCandidateSha256"], gate.canonical_sha256(result["baselineCandidate"]))
        # With custody present the candidate is the same one `baseline` accepted before custody existed.
        self.assertEqual(preserve(with_l1b1_custody(observation()))["baselineCandidate"],
                         gate.evaluate(observation())["baselineCandidate"])

    def assertBrokerDrift(self, mutate, code: str) -> None:
        obs = with_l1b1_custody(observation())
        mutate(obs)
        result = preserve(obs)
        self.assertEqual(result["BROKER_PRESERVATION"], "FAIL", code)
        self.assertIn(code, result["failures"])

    def test_every_broker_drift_class_still_fails(self) -> None:
        cases = {
            "RELEASE_SELECTOR_CHANGED": lambda o: o["release"].update(target="releases/" + "0" * 40),
            "RELEASE_MANIFEST_CHANGED": lambda o: o["release"].update(manifestSha256="0" * 64),
            "RELEASE_PAYLOAD_CHANGED": lambda o: o["release"].update(payloadMismatches=["x.py"]),
            "UNIT_FILE_CHANGED": lambda o: o["files"][next(iter(gate.UNIT_FILES))].update(sha256="0" * 64),
            "BROKER_CONFIG_CHANGED": lambda o: o["files"][next(iter(gate.CONFIG_FILES))].update(mode=0o644),
            "BROKER_STATE_CHANGED": lambda o: o["files"][next(iter(gate.STATE_FILES))].update(sha256="0" * 64),
            "DIRECTORY_CUSTODY_CHANGED": lambda o: o["directories"][str(gate.STATE)].update(mode=0o755),
            "BROKER_ACCOUNT_CHANGED": lambda o: o["accounts"]["broker"].update(shell="/bin/bash"),
            "BROKER_PROCESS_IDENTITY_CHANGED": lambda o: o["process"]["status"].update(uid=[0] * 4),
            "BROKER_SANDBOX_CHANGED": lambda o: o["units"][gate.SERVICE].update(ProtectSystem="no"),
            "SOCKET_UNIT_CHANGED": lambda o: o["units"][gate.SOCKET].update(SocketMode="0666"),
            "OWNER_SOCKET_CHANGED": lambda o: o["ownerSocket"].update(mode=0o666),
            "STAGE3_ARM_GUARD_OR_CONSUMPTION_PRESENT": lambda o: o["stage3"]["absent"].update(
                {gate.STAGE3_ABSENT[0]: False}),
            "STAGE3_JOURNAL_CHANGED": lambda o: o["stage3"].update(phases=["INTENT", "ARM"]),
            "DEPLOYER_POLICY_CHANGED": lambda o: o["deployer"].update(helperSha256="0" * 64),
            "BROKER_SERVICE_STATE_UNEXPECTED": lambda o: o["units"][gate.SERVICE].update(NRestarts="1"),
            "HOST_MISMATCH": lambda o: o["host"].update(instanceName="lilith-01"),
        }
        for code, mutate in cases.items():
            with self.subTest(code=code):
                self.assertBrokerDrift(mutate, code)

    def test_process_and_incarnation_continuity_are_pinned(self) -> None:
        def restart(o):  # same healthy shape, new process identity
            o["units"][gate.SERVICE].update(InvocationID="f" * 32, MainPID="140000")
            o["process"].update(pid=140000, startTicks=999)
            o["brokerProcesses"] = [140000]
        self.assertBrokerDrift(restart, "RUNTIME_INCARNATION_NOT_ACCEPTED_BASELINE")
        self.assertBrokerDrift(restart, "BASELINE_CANDIDATE_CHANGED")
        for mutate in (lambda o: o["process"].update(startTicks=1),
                       lambda o: o["host"].update(bootId="00000000-0000-0000-0000-000000000000"),
                       lambda o: o["libraries"][EXPAT].update(sha256="c" * 64)):
            self.assertBrokerDrift(mutate, "BASELINE_CANDIDATE_CHANGED")
        # `baseline` alone would accept that restart as a *new* candidate; `preservation` never does.
        obs = observation()
        restart(obs)
        self.assertEqual(gate.evaluate(obs)["CURRENT_RUNTIME_BASELINE"], "PASS")

    def test_custody_presence_is_reported_never_judged_or_matured(self) -> None:
        clean = preserve(observation())
        custody = preserve(with_l1b1_custody(observation()))
        odd = observation()
        odd["custodyPaths"]["/etc/lilith-authority-dev"] = {"present": True, "uid": 1001, "gid": 1002, "mode": 0o777}
        unexpected = preserve(odd)
        for result in (clean, custody, unexpected):
            self.assertEqual(result["BROKER_PRESERVATION"], "PASS")
            self.assertEqual(result["authorityCustody"]["brokerVerifierAssessment"], "NOT_ASSESSED_BY_BROKER_VERIFIER")
            self.assertEqual(result["authorityCustody"]["exactAuthorityState"],
                             "install_authority_dev.py status --expect <stage> <RELEASE_SHA>")
            self.assertEqual(result["authorityCustodyJudgment"], "NOT_PERFORMED")
            self.assertEqual(result["authorityMaturity"], "NOT_ESTABLISHED_BY_PRESERVATION")
            keys = [key for key in walk_keys(result) if "maturity" in key.lower() or key.lower() == "stage"]
            self.assertEqual(keys, ["authorityMaturity"])  # the only maturity field, and it disclaims one
            self.assertNotIn("L1b", json.dumps(result))
        # Unexpected authority state is visible verbatim, so the separately required
        # installer status (not this verifier) can refuse it.
        self.assertEqual(unexpected["authorityCustody"]["observedPaths"]["/etc/lilith-authority-dev"],
                         {"present": True, "uid": 1001, "gid": 1002, "mode": 0o777})
        self.assertEqual(clean["baselineCandidateSha256"], custody["baselineCandidateSha256"])

    def test_preservation_pass_cannot_be_read_as_authority_maturity(self) -> None:
        for obs in (observation(), with_l1b1_custody(observation()), {}):
            result = preserve(obs)
            self.assertEqual(result["authorityCustodyJudgment"], "NOT_PERFORMED")
            self.assertEqual(result["authorityMaturity"], "NOT_ESTABLISHED_BY_PRESERVATION")
            self.assertNotIn("AUTHORITY_BOUNDARY_PROOF", json.dumps(result))
            self.assertFalse(any(value in json.dumps(result) for value in ('"L1a"', '"L1b.1"', '"PRE_L1A"')))
        # The two scope fields are constants, independent of the verdict.
        self.assertEqual(preserve(observation())["authorityMaturity"], preserve({})["authorityMaturity"])
        self.assertIn('"authorityCustodyJudgment": "NOT_PERFORMED"', SOURCE)
        # `baseline` output is unchanged and carries no such fields.
        self.assertNotIn("authorityMaturity", gate.evaluate(observation()))

    def test_real_pins_match_the_accepted_runtime_baseline_record(self) -> None:
        record = REPIN_RECORD.read_text(encoding="utf-8")
        acceptance = record.split("**Broker baseline**", 1)[1].split("## 3.", 1)[0]
        for value in (gate.ACCEPTED_CURRENT_INCARNATION, gate.ACCEPTED_CURRENT_BASELINE_SHA256,
                      gate.ACCEPTED_CURRENT_BOOT_ID, *map(str, gate.ACCEPTED_CURRENT_IDENTITY.values())):
            self.assertIn(value, acceptance)
        # Every retired baseline stays documented in its own record, never accepted.
        self.assertEqual([r["runtimeIncarnation"] for r in gate.RETIRED_BROKER_BASELINES],
                         [CURRENT_INVOCATION, OLDER_ACCEPTED_INVOCATION, PREVIOUS_ACCEPTED_INVOCATION])
        for retired in gate.RETIRED_BROKER_BASELINES:
            old = (ROOT / retired["record"]).read_text(encoding="utf-8")
            for value in (retired["runtimeIncarnation"], retired["baselineCandidateSha256"], retired["bootId"]):
                self.assertIn(value, old)
        # The fixture is not the live host, so the real pin rejects it: no silent acceptance.
        self.assertIn("BASELINE_CANDIDATE_CHANGED",
                      gate.evaluate_preservation(with_l1b1_custody(observation()))["failures"])


NEW_BOOT_ID = "5b0e7c1a-9d2f-4e61-8a3b-0c4d5e6f7a8b"
NEW_INVOCATION = "0123456789abcdef0123456789abcdef"


def rebooted(obs: dict) -> dict:
    """The same healthy broker after one reboot and the owner's separate start:
    new boot, process, invocation, and freshly mapped libraries; the Stage III
    controller no longer holds its failed result."""
    obs["host"]["bootId"] = NEW_BOOT_ID
    obs["units"][gate.SERVICE].update(InvocationID=NEW_INVOCATION, MainPID="1234",
                                      ExecMainStartTimestamp="Wed 2026-09-30 01:02:03 UTC")
    obs["units"][gate.CONTROLLER] = dict(gate.CONTROLLER_POST_REBOOT_EXPECTED)
    obs["process"].update(pid=1234, startTicks=4321, startTime="2026-09-30T01:02:03Z")
    obs["brokerProcesses"] = [1234]
    obs["libraries"][EXPAT].update(inode=3003, diskInode=3003, sha256="d" * 64)
    return obs


def rebase(obs: dict) -> dict:
    """Evaluate `rebaseline` against the fixture's own accepted pins."""
    accepted = gate.evaluate(observation())["baselineCandidateSha256"]
    return gate.evaluate_rebaseline(obs, superseded_incarnation=CURRENT_INVOCATION, superseded_boot_id=BOOT_ID,
                                    superseded_candidate_sha256=accepted)


class RebaselineTests(unittest.TestCase):
    """Pre-PR-1B reboot ceremony: a fresh candidate after one reboot."""

    def test_post_reboot_broker_with_p1a9_custody_passes_as_a_new_candidate(self) -> None:
        result = rebase(rebooted(with_l1b1_custody(observation())))
        self.assertEqual(result["BROKER_REBASELINE"], "PASS", result["failures"])
        self.assertEqual(result["operation"], "READ_ONLY_POST_REBOOT_REBASELINE")
        self.assertEqual((result["runtimeIncarnation"], result["bootId"]), (NEW_INVOCATION, NEW_BOOT_ID))
        self.assertEqual(result["baselineCandidateSha256"], gate.canonical_sha256(result["baselineCandidate"]))
        self.assertEqual(result["baselineCandidate"]["pid"], 1234)
        self.assertEqual(result["baselineCandidate"]["startTicks"], 4321)
        self.assertIs(result["continuityWithAcceptedBaseline"], False)
        self.assertEqual(result["ownerAcceptance"], "PENDING_SEPARATE_EXPLICIT_OWNER_DECISION")
        self.assertEqual(result["authorityCustodyJudgment"], "NOT_PERFORMED")
        self.assertEqual(result["authorityMaturity"], "NOT_ESTABLISHED_BY_REBASELINE")
        self.assertNotIn("STAGE_II_ACCEPTED", json.dumps(result))
        for key in ("releaseEquivalent", "configEquivalent", "stateEquivalent", "identityBoundaryEquivalent",
                    "socketBoundaryEquivalent", "stageIIIUntouched", "deployerPolicyTextEquivalent",
                    "incarnationHealthy"):
            self.assertIs(result[key], True, key)

    def test_the_same_post_reboot_host_fails_the_other_two_operations(self) -> None:
        obs = rebooted(with_l1b1_custody(observation()))
        self.assertIn("RUNTIME_INCARNATION_NOT_ACCEPTED_BASELINE", preserve(obs)["failures"])
        self.assertIn("STAGE3_CONTROLLER_CHANGED", preserve(obs)["failures"])
        self.assertIn("CUSTODY_PATH_PRESENT_BEFORE_B1B3D", gate.evaluate(obs)["failures"])

    def test_pre_reboot_host_is_not_a_rebaseline(self) -> None:
        result = rebase(with_l1b1_custody(observation()))
        self.assertEqual(result["BROKER_REBASELINE"], "FAIL")
        for code in ("REBOOT_NOT_OBSERVED", "RUNTIME_INCARNATION_NOT_REPLACED", "BASELINE_CANDIDATE_NOT_REPLACED",
                     "STAGE3_CONTROLLER_CHANGED"):
            self.assertIn(code, result["failures"])
        self.assertIsNone(result["baselineCandidateSha256"])  # no digest to accept from a failing run

    def test_a_restart_without_a_reboot_is_not_a_rebaseline(self) -> None:
        obs = rebooted(with_l1b1_custody(observation()))
        obs["host"]["bootId"] = BOOT_ID
        self.assertEqual(rebase(obs)["failures"], ["REBOOT_NOT_OBSERVED"])

    def test_controller_must_be_loaded_and_never_started_in_the_new_boot(self) -> None:
        cases = {
            "still failed": dict(gate.CONTROLLER_EXPECTED, LoadState="loaded", InvocationID=""),
            "ran this boot": dict(gate.CONTROLLER_POST_REBOOT_EXPECTED, InvocationID="e" * 32),
            "active": dict(gate.CONTROLLER_POST_REBOOT_EXPECTED, ActiveState="active", SubState="running"),
            "unit file gone": dict(gate.CONTROLLER_POST_REBOOT_EXPECTED, LoadState="not-found"),
            "restarting": dict(gate.CONTROLLER_POST_REBOOT_EXPECTED, Restart="on-failure"),
            "unobserved": {},
        }
        for name, state in cases.items():
            with self.subTest(name):
                obs = rebooted(with_l1b1_custody(observation()))
                obs["units"][gate.CONTROLLER] = state
                result = rebase(obs)
                self.assertEqual(result["failures"], ["STAGE3_CONTROLLER_CHANGED"])
                self.assertIsNone(result["baselineCandidateSha256"])

    def test_every_broker_drift_class_still_fails_after_reboot(self) -> None:
        cases = {
            "RELEASE_MANIFEST_CHANGED": lambda o: o["release"].update(manifestSha256="0" * 64),
            "UNIT_FILE_CHANGED": lambda o: o["files"][next(iter(gate.UNIT_FILES))].update(sha256="0" * 64),
            "BROKER_STATE_CHANGED": lambda o: o["files"][next(iter(gate.STATE_FILES))].update(sha256="0" * 64),
            "BROKER_SANDBOX_CHANGED": lambda o: o["units"][gate.SERVICE].update(ProtectSystem="no"),
            "SOCKET_UNIT_CHANGED": lambda o: o["units"][gate.SOCKET].update(UnitFileState="enabled"),
            "RUNTIME_DIRECTORY_CHANGED": lambda o: o["runtimeDirectory"].update(mode=0o755),
            "OWNER_SOCKET_CHANGED": lambda o: o["ownerSocket"].update(listening=False),
            "STAGE3_ARM_GUARD_OR_CONSUMPTION_PRESENT": lambda o: o["stage3"]["absent"].update(
                {gate.STAGE3_ABSENT[1]: False}),
            "DEPLOYER_POLICY_CHANGED": lambda o: o["deployer"]["sudoers"].update(exactText=False),
            "RUNTIME_SUBSTRATE_STALE_OR_UNREADABLE": lambda o: o["libraries"][EXPAT].update(deleted=True),
            "BROKER_SERVICE_STATE_UNEXPECTED": lambda o: o["units"][gate.SERVICE].update(ActiveState="inactive"),
            "BROKER_PROCESS_AMBIGUOUS": lambda o: o.update(brokerProcesses=[1234, 1235]),
            "HOST_MISMATCH": lambda o: o["host"].update(machineId="0" * 32),
        }
        for code, mutate in cases.items():
            with self.subTest(code=code):
                obs = rebooted(with_l1b1_custody(observation()))
                mutate(obs)
                result = rebase(obs)
                self.assertEqual(result["BROKER_REBASELINE"], "FAIL")
                self.assertIn(code, result["failures"])

    def test_broker_left_down_after_reboot_fails_closed(self) -> None:
        obs = rebooted(with_l1b1_custody(observation()))
        obs["units"][gate.SERVICE].update(ActiveState="inactive", SubState="dead", MainPID="0", InvocationID="")
        obs["units"][gate.SOCKET].update(ActiveState="inactive")
        obs.update(process={}, libraries={}, brokerProcesses=[], ownerSocket={"present": False})
        result = rebase(obs)
        self.assertEqual(result["BROKER_REBASELINE"], "FAIL")
        for code in ("SOCKET_UNIT_CHANGED", "OWNER_SOCKET_CHANGED", "BROKER_SERVICE_STATE_UNEXPECTED",
                     "INVOCATION_ID_INVALID", "BROKER_PROCESS_AMBIGUOUS", "RUNTIME_SUBSTRATE_STALE_OR_UNREADABLE"):
            self.assertIn(code, result["failures"])

    def test_real_supersession_pins_are_the_accepted_baseline(self) -> None:
        # After the re-pin, `rebaseline` supersedes the currently accepted (post-reboot) baseline.
        self.assertEqual(gate.ACCEPTED_CURRENT_BOOT_ID, ACCEPTED_BOOT)
        self.assertNotEqual(gate.ACCEPTED_CURRENT_BOOT_ID, gate.ACCEPTED_BROKER_BOOT_ID)
        result = gate.evaluate_rebaseline(rebooted(with_l1b1_custody(observation())))
        self.assertEqual(result["supersedes"], {"runtimeIncarnation": gate.ACCEPTED_CURRENT_INCARNATION,
                                                "bootId": gate.ACCEPTED_CURRENT_BOOT_ID,
                                                "baselineCandidateSha256": gate.ACCEPTED_CURRENT_BASELINE_SHA256})
        self.assertEqual(result["BROKER_REBASELINE"], "PASS", result["failures"])
        # `rebaseline` itself never re-pins; the pins are reviewed constants.
        self.assertEqual(gate.ACCEPTED_CURRENT_INCARNATION, ACCEPTED_INVOCATION)

    def test_controller_collection_reads_both_contracts(self) -> None:
        for key in (*gate.CONTROLLER_EXPECTED, *gate.CONTROLLER_POST_REBOOT_EXPECTED):
            self.assertIn(key, gate.CONTROLLER_PROPERTIES)
        self.assertEqual(len(gate.CONTROLLER_PROPERTIES), len(set(gate.CONTROLLER_PROPERTIES)))


FENCE = "`" * 3
REPIN_RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-post-reboot-witness-broker-repin.md"
# The owner-accepted post-reboot baseline of 2026-10-09 (M-R1 reboot, one M-R2 start).
ACCEPTED_BOOT = "cb0d71da-32a7-402b-b85e-5748da012bff"
ACCEPTED_INVOCATION = "ed35e343bc9f4ec687f753ed7b3a53b2"
ACCEPTED_CANDIDATE = "ff3a432d9d8e5c23718be41898be9568dd8914f0e2e28bb4c27f8e0bccaa3ef1"
# The 2026-10-02 post-restart baseline, retired by the 2026-10-09 M-R1 reboot.
PREVIOUS_ACCEPTED_BOOT = "eea461c3-60f0-4b10-8ee9-556dcef19711"
PREVIOUS_ACCEPTED_INVOCATION = "c4b9cb38d7a041dc91db0d8ada7e8d04"
PREVIOUS_ACCEPTED_CANDIDATE = "a30bd7d6e26a75e4eba863c08622aebbbaf72928bc9dc7737fc1f7aa6473069d"
# The 2026-09-29 post-reboot baseline, retired by the 2026-10-02 broker restart.
OLDER_ACCEPTED_INVOCATION = "84798e5b74494e1ea362ce90f1cf04ad"
OLDER_ACCEPTED_CANDIDATE = "5000374513f38144c90bd75aefdabb4d000f644e024107bf275da9f80af7dbe2"


def accepted_obs() -> dict:
    """The accepted post-reboot shape: custody present, broker started once, controller never run."""
    return rebooted(with_l1b1_custody(observation()))


def preserve_accepted(obs: dict) -> dict:
    """`preservation` with the fixture's post-reboot pins and the real default controller contract."""
    pinned = accepted_obs()
    return gate.evaluate_preservation(obs, accepted_incarnation=NEW_INVOCATION,
                                      accepted_candidate_sha256=gate.canonical_sha256(gate.evaluate(pinned)["baselineCandidate"]),
                                      accepted_identity=identity_of(pinned))


class RepinTests(unittest.TestCase):
    """Pre-PR-1B re-pin: `preservation` pins the owner-accepted post-reboot baseline."""

    def test_real_pins_are_exactly_the_accepted_baseline(self) -> None:
        self.assertEqual(gate.ACCEPTED_CURRENT_INCARNATION, ACCEPTED_INVOCATION)
        self.assertEqual(gate.ACCEPTED_CURRENT_BASELINE_SHA256, ACCEPTED_CANDIDATE)
        self.assertEqual(gate.ACCEPTED_CURRENT_BOOT_ID, ACCEPTED_BOOT)
        self.assertEqual(gate.ACCEPTED_CURRENT_IDENTITY, {
            "bootId": ACCEPTED_BOOT, "pid": 3411, "startTicks": 125335, "nRestarts": "0",
            "releaseSha": "817a83e44cec8965479fd97fc30b7a0b3ae49ab2",
            "manifestSha256": "7a46ac83001411a29b1bc4be7e0f91f09c5879967386c452b2620e23d16e4614",
            "sharedLibrariesSha256": "818994544397da37d5a97e3799afff314608a7aa00cad50c968a90b86f41ce60"})
        self.assertEqual(gate.ACCEPTED_CURRENT_IDENTITY["releaseSha"], gate.RELEASE_SHA)
        self.assertEqual(gate.ACCEPTED_CURRENT_IDENTITY["manifestSha256"], gate.MANIFEST_SHA)
        self.assertEqual(set(gate.ACCEPTED_CURRENT_IDENTITY), set(IDENTITY_KEYS))
        self.assertIs(gate.ACCEPTED_CURRENT_CONTROLLER_EXPECTED, gate.CONTROLLER_POST_REBOOT_EXPECTED)
        retired = gate.RETIRED_BROKER_BASELINES
        self.assertEqual([r["runtimeIncarnation"] for r in retired],
                         [CURRENT_INVOCATION, OLDER_ACCEPTED_INVOCATION, PREVIOUS_ACCEPTED_INVOCATION])
        self.assertEqual(retired[0]["baselineCandidateSha256"],
                         "3549585487ad46ead96a0cb1af30a15be0c4ac17575663816e8e11dc80a7eee5")
        self.assertEqual(retired[0]["bootId"], BOOT_ID)
        # The 2026-10-02 same-boot restart retired the 2026-09-29 baseline but kept its boot.
        self.assertEqual(retired[1]["baselineCandidateSha256"], OLDER_ACCEPTED_CANDIDATE)
        self.assertEqual(retired[1]["bootId"], PREVIOUS_ACCEPTED_BOOT)
        # The 2026-10-09 reboot retires the post-restart baseline and its boot.
        self.assertEqual((retired[2]["baselineCandidateSha256"], retired[2]["bootId"]),
                         (PREVIOUS_ACCEPTED_CANDIDATE, PREVIOUS_ACCEPTED_BOOT))
        self.assertEqual(retired[2]["record"], "docs/architecture/slice-15b2b-b1b3e-broker-restart-recovery.md")
        for old in retired:
            self.assertNotEqual(gate.ACCEPTED_CURRENT_BASELINE_SHA256, old["baselineCandidateSha256"])
        self.assertNotEqual(gate.ACCEPTED_CURRENT_BOOT_ID, PREVIOUS_ACCEPTED_BOOT)
        self.assertNotIn(gate.ACCEPTED_CURRENT_INCARNATION, [r["runtimeIncarnation"] for r in retired])

    def test_the_accepted_candidate_preimage_is_exact(self) -> None:
        # Appendix A of the re-pin record is the accepted `rebaseline` candidate, byte for byte.
        text = REPIN_RECORD.read_text(encoding="utf-8").split("## Appendix A.", 1)[1]
        candidate = json.loads(text.split(FENCE + "json\n", 1)[1].split("\n" + FENCE, 1)[0])
        self.assertEqual(gate.canonical_sha256(candidate), gate.ACCEPTED_CURRENT_BASELINE_SHA256)
        self.assertEqual(candidate["runtimeIncarnation"], gate.ACCEPTED_CURRENT_INCARNATION)
        self.assertEqual({key: candidate[key] for key in IDENTITY_KEYS}, gate.ACCEPTED_CURRENT_IDENTITY)
        self.assertEqual(candidate["startTime"], "2026-10-09T09:52:33Z")
        self.assertFalse(any(lib["deleted"] for lib in candidate["sharedLibraries"]))

    def test_the_historical_post_restart_baseline_is_not_current(self) -> None:
        obs = accepted_obs()
        obs["host"]["bootId"] = PREVIOUS_ACCEPTED_BOOT
        obs["units"][gate.SERVICE]["InvocationID"] = PREVIOUS_ACCEPTED_INVOCATION
        result = gate.evaluate_preservation(obs)
        self.assertEqual(result["BROKER_PRESERVATION"], "FAIL")
        for code in ("RUNTIME_INCARNATION_NOT_ACCEPTED_BASELINE", "ACCEPTED_IDENTITY_CHANGED:bootId",
                     "BASELINE_CANDIDATE_CHANGED"):
            self.assertIn(code, result["failures"])
        self.assertEqual(result["acceptedRuntimeIncarnation"], ACCEPTED_INVOCATION)
        self.assertEqual(result["acceptedBaselineCandidateSha256"], ACCEPTED_CANDIDATE)

    def test_preservation_accepts_the_exact_accepted_baseline(self) -> None:
        result = preserve_accepted(accepted_obs())
        self.assertEqual(result["BROKER_PRESERVATION"], "PASS", result["failures"])
        self.assertIs(result["acceptedIdentityMatches"], True)
        self.assertIs(result["baselineCandidateMatchesAccepted"], True)
        self.assertEqual(result["runtimeIncarnation"], NEW_INVOCATION)

    def assertRejected(self, mutate, *codes) -> None:
        obs = accepted_obs()
        mutate(obs)
        result = preserve_accepted(obs)
        self.assertEqual(result["BROKER_PRESERVATION"], "FAIL", codes)
        for code in codes:
            self.assertIn(code, result["failures"])

    def test_preservation_rejects_the_retired_pre_reboot_baseline(self) -> None:
        result = preserve_accepted(with_l1b1_custody(observation()))  # the old incarnation, as last accepted
        self.assertEqual(result["BROKER_PRESERVATION"], "FAIL")
        for code in ("RUNTIME_INCARNATION_NOT_ACCEPTED_BASELINE", "BASELINE_CANDIDATE_CHANGED",
                     "ACCEPTED_IDENTITY_CHANGED:bootId", "ACCEPTED_IDENTITY_CHANGED:pid",
                     "ACCEPTED_IDENTITY_CHANGED:startTicks", "STAGE3_CONTROLLER_CHANGED"):
            self.assertIn(code, result["failures"])

    def test_preservation_rejects_the_old_incarnation_alone(self) -> None:
        self.assertRejected(lambda o: o["units"][gate.SERVICE].update(InvocationID=CURRENT_INVOCATION),
                            "RUNTIME_INCARNATION_NOT_ACCEPTED_BASELINE")

    def test_preservation_rejects_old_pid_and_start_ticks(self) -> None:
        def old_process(o):
            o["units"][gate.SERVICE].update(MainPID="132976")
            o["process"].update(pid=132976)
            o["brokerProcesses"] = [132976]
        self.assertRejected(old_process, "ACCEPTED_IDENTITY_CHANGED:pid", "BASELINE_CANDIDATE_CHANGED")
        self.assertRejected(lambda o: o["process"].update(startTicks=108213277),
                            "ACCEPTED_IDENTITY_CHANGED:startTicks", "BASELINE_CANDIDATE_CHANGED")

    def test_preservation_rejects_a_candidate_mismatch(self) -> None:
        self.assertRejected(lambda o: o["libraries"][EXPAT].update(sha256="e" * 64),
                            "ACCEPTED_IDENTITY_CHANGED:sharedLibrariesSha256", "BASELINE_CANDIDATE_CHANGED")
        self.assertRejected(lambda o: o["process"].update(startTime="2026-09-30T00:00:00Z"),
                            "BASELINE_CANDIDATE_CHANGED")
        obs = accepted_obs()
        pinned = accepted_obs()
        result = gate.evaluate_preservation(obs, accepted_incarnation=NEW_INVOCATION,
                                            accepted_candidate_sha256="0" * 64, accepted_identity=identity_of(pinned))
        self.assertEqual(result["failures"], ["BASELINE_CANDIDATE_CHANGED"])

    def test_preservation_rejects_restarts(self) -> None:
        self.assertRejected(lambda o: o["units"][gate.SERVICE].update(NRestarts="1"),
                            "BROKER_SERVICE_STATE_UNEXPECTED", "ACCEPTED_IDENTITY_CHANGED:nRestarts",
                            "BASELINE_CANDIDATE_CHANGED")

    def test_preservation_rejects_a_boot_mismatch(self) -> None:
        self.assertRejected(lambda o: o["host"].update(bootId=BOOT_ID),
                            "ACCEPTED_IDENTITY_CHANGED:bootId", "BASELINE_CANDIDATE_CHANGED")
        self.assertRejected(lambda o: o["host"].update(bootId="11111111-2222-3333-4444-555555555555"),
                            "ACCEPTED_IDENTITY_CHANGED:bootId", "BASELINE_CANDIDATE_CHANGED")

    def test_preservation_pins_the_accepted_boots_controller_state(self) -> None:
        self.assertRejected(lambda o: o["units"].update({gate.CONTROLLER: dict(gate.CONTROLLER_EXPECTED)}),
                            "STAGE3_CONTROLLER_CHANGED")
        self.assertRejected(lambda o: o["units"][gate.CONTROLLER].update(InvocationID="e" * 32),
                            "STAGE3_CONTROLLER_CHANGED")

    def test_every_broker_drift_class_still_fails(self) -> None:
        for code, mutate in {
            "RELEASE_MANIFEST_CHANGED": lambda o: o["release"].update(manifestSha256="0" * 64),
            "BROKER_STATE_CHANGED": lambda o: o["files"][next(iter(gate.STATE_FILES))].update(sha256="0" * 64),
            "SOCKET_UNIT_CHANGED": lambda o: o["units"][gate.SOCKET].update(UnitFileState="enabled"),
            "STAGE3_ARM_GUARD_OR_CONSUMPTION_PRESENT": lambda o: o["stage3"]["absent"].update(
                {gate.STAGE3_ABSENT[0]: False}),
            "DEPLOYER_POLICY_CHANGED": lambda o: o["deployer"].update(helperSha256="0" * 64),
        }.items():
            with self.subTest(code):
                self.assertRejected(mutate, code)

    def test_rebaseline_is_unchanged_and_never_accepts_the_accepted_baseline(self) -> None:
        # Same code path, same fixture results as before the re-pin (RebaselineTests use explicit pins).
        self.assertEqual(rebase(accepted_obs())["BROKER_REBASELINE"], "PASS")
        # Against the real pins, the accepted baseline itself is not a *new* candidate.
        obs = accepted_obs()
        obs["host"]["bootId"] = ACCEPTED_BOOT
        obs["units"][gate.SERVICE]["InvocationID"] = ACCEPTED_INVOCATION
        result = gate.evaluate_rebaseline(obs)
        self.assertIn("REBOOT_NOT_OBSERVED", result["failures"])
        self.assertIn("RUNTIME_INCARNATION_NOT_REPLACED", result["failures"])
        self.assertIsNone(result["baselineCandidateSha256"])
        # `baseline` keeps its historical pre-custody semantics.
        self.assertIn("CUSTODY_PATH_PRESENT_BEFORE_B1B3D", gate.evaluate(accepted_obs())["failures"])

    def test_preservation_pass_implies_no_authority_or_custody_acceptance(self) -> None:
        result = preserve_accepted(accepted_obs())
        self.assertEqual(result["BROKER_PRESERVATION"], "PASS")
        self.assertEqual(result["authorityCustodyJudgment"], "NOT_PERFORMED")
        self.assertEqual(result["authorityMaturity"], "NOT_ESTABLISHED_BY_PRESERVATION")
        self.assertEqual(result["authorityCustody"]["brokerVerifierAssessment"], "NOT_ASSESSED_BY_BROKER_VERIFIER")
        text = json.dumps(result)
        for token in ("PR-1B", "PR1B", "AUTHORIZED", "K_WIT", "K-WIT", "INITIAL_CUSTODY", "FRESHNESS",
                      "AUTHORITY_BOUNDARY_PROOF", "P1A-9"):
            self.assertNotIn(token, text)
        keys = [key for key in walk_keys(result) if "maturity" in key.lower() or key.lower() == "stage"]
        self.assertEqual(keys, ["authorityMaturity"])


class ParserTests(unittest.TestCase):
    def test_maps_skip_anonymous_and_flag_deleted(self) -> None:
        text = "\n".join((
            "5600-5700 r--p 00000000 08:01 1001 /usr/bin/python3.12",
            "5700-5800 r-xp 00001000 08:01 1001 /usr/bin/python3.12",
            "7f00-7f01 r--p 00000000 08:01 2002 /usr/lib/x86_64-linux-gnu/libexpat.so.1.9.1 (deleted)",
            "7f01-7f02 rw-p 00000000 00:00 0 ",
            "7f02-7f03 rw-s 00000000 00:05 77 /dev/zero (deleted)",
            "7ffd-7ffe rw-p 00000000 00:00 0 [stack]",
        ))
        self.assertEqual(gate.parse_maps(text), {
            "/usr/bin/python3.12": {"inode": 1001, "deleted": False},
            EXPAT: {"inode": 2002, "deleted": True},
        })

    def test_start_ticks_survive_hostile_comm(self) -> None:
        stat = "132976 (py) (x) S 1 " + " ".join(str(i) for i in range(2, 30))
        fields = stat[stat.rfind(") ") + 2:].split()
        self.assertEqual(gate.parse_start_ticks(stat), int(fields[19]))

    def test_start_time(self) -> None:
        self.assertEqual(gate.start_time_utc(250, 1_000_000_000, 100), "2001-09-09T01:46:42Z")

    def test_status(self) -> None:
        parsed = gate.parse_status("PPid:\t1\nUid:\t999\t999\t999\t999\nGid:\t987\t987\t987\t987\n"
                                   "Groups:\t987 \nNoNewPrivs:\t1\nSeccomp:\t2\nCapEff:\t0000000000000000\n")
        self.assertEqual((parsed["uid"], parsed["groups"], parsed["ppid"], parsed["noNewPrivs"]),
                         ([999] * 4, [987], 1, "1"))

    def test_needrestart_default_and_override(self) -> None:
        default = gate.parse_needrestart(["#$nrconf{restart} = 'i';\n"])
        self.assertEqual(default["restartMode"], "DEFAULT")
        self.assertFalse(any(default["serviceSpecificExclusion"].values()))
        override = gate.parse_needrestart([
            "$nrconf{restart} = 'l';\n",
            "$nrconf{override_rc}{qr(^lilith-memory-broker\\.service$)} = 0;\n",
        ])
        self.assertEqual(override["restartMode"], "l")
        self.assertTrue(override["serviceSpecificExclusion"]["lilith-memory-broker"])
        self.assertFalse(override["serviceSpecificExclusion"]["lilith-authority-dev"])


class ReadOnlyContractTests(unittest.TestCase):
    def test_only_systemctl_show_is_permitted(self) -> None:
        good = ["/usr/bin/systemctl", "show", "lilith-memory-broker.service", "--property=MainPID", "--no-pager"]
        self.assertEqual(gate.readonly_argv(good), good)
        for verb in ("restart", "stop", "start", "reload", "daemon-reload", "kill", "reset-failed"):
            with self.assertRaises(gate.BaselineError):
                gate.readonly_argv(["/usr/bin/systemctl", verb, "lilith-memory-broker.service",
                                    "--property=MainPID", "--no-pager"])
        for argv in (good + ["--runtime"], ["/usr/bin/sudo"] + good[1:],
                     good[:2] + ["x; rm -rf /"] + good[3:]):
            with self.assertRaises(gate.BaselineError):
                gate.readonly_argv(argv)

    def test_source_has_no_mutation_primitives(self) -> None:
        tree = ast.parse(SOURCE)
        forbidden = {"remove", "unlink", "rmdir", "chmod", "chown", "mkdir", "makedirs", "rename",
                     "symlink", "write_text", "write_bytes", "touch", "kill", "system",
                     "Popen", "check_output", "connect"}
        attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        self.assertFalse(attributes & forbidden, attributes & forbidden)
        self.assertNotIn("os.replace", SOURCE)
        self.assertNotIn("shutil", SOURCE)
        imports = {alias.name for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
                   for alias in node.names}
        self.assertNotIn("sqlite3", imports)
        runs = [node for node in ast.walk(tree) if isinstance(node, ast.Attribute) and node.attr == "run"]
        self.assertEqual(len(runs), 1)
        opens = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and node.func.attr == "open"
                 and getattr(node.func.value, "id", None) == "os"]
        self.assertTrue(all("O_RDONLY" in ast.unparse(node) for node in opens))
        self.assertNotIn("sudo -u", SOURCE.replace("never runs ``sudo -u``", ""))

    def test_wrong_host_refused_before_other_reads(self) -> None:
        collect = next(node for node in ast.parse(SOURCE).body
                       if isinstance(node, ast.FunctionDef) and node.name == "collect")
        first = collect.body[1]  # after the docstring
        self.assertIn("_host()", ast.unparse(first))
        self.assertIn('require(socket.gethostname() == DEV_INSTANCE, "WRONG_HOST_REFUSED")', SOURCE)


class PinnedConstantDriftTests(unittest.TestCase):
    """Pins must stay identical to the accepted lifecycle and forensic sources."""

    def test_artifact_contract_matches_accepted_lifecycle(self) -> None:
        for path, value in {**gate.UNIT_FILES, **gate.CONFIG_FILES, **gate.STATE_FILES}.items():
            self.assertEqual(lifecycle.ACCEPTED_FILES[path], value, path)
        self.assertEqual((gate.RELEASE_SHA, gate.MANIFEST_SHA), (lifecycle.RELEASE_SHA, lifecycle.MANIFEST_SHA))
        self.assertEqual((gate.DEV_HOSTNAME, gate.DEV_MACHINE_ID, gate.DEV_INSTANCE_ID),
                         (lifecycle.DEV_HOSTNAME, lifecycle.DEV_MACHINE_ID, lifecycle.DEV_INSTANCE_ID))
        excluded = set(lifecycle.ACCEPTED_FILES) - set(gate.UNIT_FILES) - set(gate.CONFIG_FILES) - set(gate.STATE_FILES)
        self.assertEqual(excluded, {str(lifecycle.API_ROOT / "current/app.py"),
                                    "/etc/systemd/system/lilith-os-api-dev.service"})

    def test_accepted_process_identity_is_reference_only(self) -> None:
        self.assertEqual((gate.ACCEPTED_SERVICE_INVOCATION, gate.ACCEPTED_BROKER_START_TICKS,
                          gate.ACCEPTED_BROKER_BOOT_ID),
                         (lifecycle.ACCEPTED_SERVICE_INVOCATION, lifecycle.ACCEPTED_BROKER_START_TICKS,
                          lifecycle.ACCEPTED_BROKER_BOOT_ID))
        self.assertNotIn("ACCEPTED_SERVICE_INVOCATION", ast.unparse(
            next(node for node in ast.parse(SOURCE).body
                 if isinstance(node, ast.FunctionDef) and node.name == "collect")))

    def test_stage3_paths_match_forensics(self) -> None:
        self.assertEqual(gate.STAGE3_VAULT, forensics.VAULT)
        self.assertEqual(gate.CONTROLLER, forensics.SERVICE)
        posix = lambda value: str(value).replace("\\", "/")  # noqa: E731 - Windows runners
        markers = {posix(path) for path in forensics.MARKERS.values()}
        ours = {posix(path) for path in (*gate.STAGE3_PRESENT, *gate.STAGE3_ABSENT[:2])}
        self.assertTrue(ours <= markers, ours - markers)
        self.assertEqual(gate.RELEASE_SHA, forensics.ACCEPTED)

    def test_sudoers_text_is_the_rendered_b1c_template(self) -> None:
        template = (ROOT / "scripts/dev_deployer/sudoers-lilith-dev-deployer.in").read_text(encoding="utf-8")
        rendered = template.replace("@DEPLOYER@", gate.DEPLOYER)
        self.assertEqual(gate.DEPLOYER_SUDOERS_TEXT, rendered)
        self.assertEqual(len(rendered.encode()), 294)  # live size observed 2026-09-26

    def test_custody_paths_are_named_in_b1b3d_design(self) -> None:
        design = (ROOT / "docs/architecture/slice-15b2b-b1b3d-dev-synthetic-custody-design.md").read_text(encoding="utf-8")
        # B1b-3e PR-1S adds the PR-1 paths; each is named in its runtime-wiring record instead.
        pr1 = (ROOT / "docs/architecture/slice-15b2b-b1b3e-pr1s-runtime-wiring.md").read_text(encoding="utf-8")
        for path in gate.CUSTODY_PATHS:
            self.assertTrue(Path(path).name in design or path in pr1, path)


if __name__ == "__main__":
    unittest.main()
