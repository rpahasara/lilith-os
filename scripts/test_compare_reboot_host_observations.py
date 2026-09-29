"""Offline regressions for the pre-PR-1B reboot PRE/POST observation comparison."""

from __future__ import annotations

import ast
import copy
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import compare_reboot_host_observations as C

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "scripts/compare_reboot_host_observations.py").read_text(encoding="utf-8")
PRE_BOOT = "24d1771d-e1b5-4e5f-816d-da08ad8b367a"
POST_BOOT = "5b0e7c1a-9d2f-4e61-8a3b-0c4d5e6f7a8b"
OLD_KERNEL = "6.17.0-1022-gcp"
NEW_KERNEL = "7.0.0-1011-gcp"
SIGNER_GID = 985


def stat(kind="dir", uid=0, gid=0, mode="0755", inode=100, device=2049):
    return {"kind": kind, "uid": uid, "gid": gid, "mode": mode, "device": device, "inode": inode, "size": 4096,
            "nlink": 2, "mtimeNs": 1790000000000000000, "ctimeNs": 1790000000000000000}


def unit(active="inactive", invocation="", pid="0"):
    return {"Id": "x", "LoadState": "loaded", "ActiveState": active, "SubState": "dead" if active == "inactive"
            else "running", "UnitFileState": "static", "NeedDaemonReload": "no", "NRestarts": "0", "MainPID": pid,
            "InvocationID": invocation, "ExecMainStartTimestamp": "", "InactiveExitTimestamp": "",
            "ActiveEnterTimestamp": "", "FragmentPath": "/etc/systemd/system/x", "DropInPaths": ""}


def pre_facts() -> dict:
    """The accepted P1A-9 shape, before the reboot (values are illustrative)."""
    units = {name: unit() for name in ("lilith-authority-dev.service", "lilith-authority-dev.socket",
                                       "lilith-recovery-witness.service", "lilith-recovery-witness-owner.socket",
                                       "lilith-recovery-witness-signer.socket")}
    units["lilith-memory-broker.service"] = dict(unit("active", "42af2691b8d24ee5a92a286197c5444c", "132976"),
                                                 ExecMainStartTimestamp="Sat 2026-09-26 06:34:09 UTC",
                                                 UnitFileState="static")
    pr1 = {path: None for path in (
        "/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred",
        "/var/lib/lilith-authority-dev", "/var/lib/lilith-recovery-witness", "/run/lilith-authority-dev",
        "/run/lilith-recovery-witness", "/run/credentials/lilith-authority-dev.service",
        "/run/credentials/lilith-recovery-witness.service")}
    pr1.update({"/etc/lilith-authority-custody": stat(mode="0700", inode=11),
                "/etc/lilith-authority-dev": stat(inode=12)})
    return {
        "host": {"hostname": "lilith-dev-01", "machineId": "ae929170e6fa4c8ab9cc7b9547238d9d", "bootId": PRE_BOOT,
                 "kernel": OLD_KERNEL, "osPrettyName": "Ubuntu 24.04.4 LTS", "swaps": [], "rebootRequired": True,
                 "localtime": stat("symlink", inode=3), "uptimeSeconds": "1400000.00",
                 "utcNow": "2026-09-30T01:00:00Z"},
        "releases": {"releaseEntries": ["aee323e94412accbe321bc84eae78c5b8cf95afc"], "trees": {"x": {"treeSha256": "a"}}},
        "hostFiles": {"/usr/local/sbin/lilith-activation-verify": dict(stat("file", mode="0755", inode=7),
                                                                       sha256="44046cae")},
        "units": {"show": units, "enablementOrDropInEntries": []},
        "accounts": {"lilith-authority-dev": {"uid": 995, "gid": SIGNER_GID},
                     "lilith-recovery-witness": {"uid": 994, "gid": 984}},
        "currentBlob": dict(stat("file", mode="0600", inode=1738), sha256="6a61c350"),
        "hostKey": stat("file", mode="0400", inode=5768),
        "listings": {"/etc/credstore.encrypted": {"lilith-authority-dev.owner-actor.cred": "file"},
                     "/run/credentials": {}, "/etc/lilith-authority-custody/prepared": {}},
        "pr1Objects": pr1,
        "filesystems": {"/etc": {"nearestExisting": "/etc", "device": 2049, "mount": {"mountPoint": "/"}}},
        "namespaceInventory": {"/etc": ["lilith-authority-custody", "lilith-authority-dev"],
                               "/run": ["lilith-memory", "lilith-os-api-dev"], "/opt": ["lilith-authority-dev"]},
    }


def post_facts(pre: dict | None = None) -> dict:
    """The same host after one reboot, with every expected reboot effect."""
    facts = copy.deepcopy(pre or pre_facts())
    facts["host"].update(bootId=POST_BOOT, kernel=NEW_KERNEL, rebootRequired=False, uptimeSeconds="120.00",
                         utcNow="2026-09-30T01:10:00Z")
    facts["units"]["show"]["lilith-memory-broker.service"].update(ActiveState="inactive", SubState="dead",
                                                                  MainPID="0", InvocationID="",
                                                                  ExecMainStartTimestamp="")
    facts["pr1Objects"]["/run/lilith-authority-dev"] = stat(mode="0700", inode=900, device=25)
    facts["pr1Objects"]["/run/lilith-recovery-witness"] = stat(gid=SIGNER_GID, mode="0710", inode=901, device=25)
    facts["namespaceInventory"]["/run"] = ["lilith-authority-dev", "lilith-memory", "lilith-recovery-witness"]
    return facts


def report(facts: dict) -> dict:
    stable = C.stable_facts(facts)
    return {"schema": C.OBSERVER_SCHEMA, "schemaVersion": 1, "operation": "READ_ONLY_OBSERVATION",
            "judgment": "NOT_PERFORMED", "facts": facts,
            "sectionSha256": {name: C._digest(value) for name, value in sorted(stable.items())},
            "stableSha256": C._digest(stable)}


def transcript(facts: dict) -> str:
    value = report(facts)
    return (json.dumps(value, sort_keys=True, indent=1) + "\n"
            + f"PR1A_HOST_OBSERVATION=COMPLETE stableSha256={value['stableSha256']}\n")


def run(pre: dict, post: dict, kernel: str = NEW_KERNEL, accepted: str | None = None) -> dict:
    return C.compare(C.parse_transcript(transcript(pre)), C.parse_transcript(transcript(post)),
                     expected_kernel=kernel, accepted_pre_stable=accepted)


class ExpectedRebootTests(unittest.TestCase):
    def test_expected_reboot_passes_and_records_or6(self):
        result = run(pre_facts(), post_facts())
        self.assertEqual(result["REBOOT_OBSERVATION_COMPARISON"], "PASS", result["unexpected"])
        self.assertEqual(result["unexpected"], [])
        for item in ("BOOT_ID_CHANGED", "KERNEL_CHANGED_TO_EXPECTED", "REBOOT_REQUIRED_CLEARED",
                     "OR6_TMPFILES_RUNTIME_DIR_CREATED:/run/lilith-authority-dev",
                     "OR6_TMPFILES_RUNTIME_DIR_CREATED:/run/lilith-recovery-witness",
                     "RUN_ENTRY_ADDED:lilith-authority-dev", "RUN_ENTRY_ADDED:lilith-recovery-witness",
                     "RUN_ENTRY_NOT_RECREATED:lilith-os-api-dev",
                     "BROKER_PROCESS_LIFETIME_CHANGED:InvocationID"):
            self.assertIn(item, result["expected"])
        self.assertEqual(result["or6"]["/run/lilith-recovery-witness"]["post"], "PRESENT_EXACT_TMPFILES_SPEC")
        self.assertEqual(result["or6"]["/run/lilith-authority-dev"]["pre"], "ABSENT")
        self.assertEqual(result["or6"]["/run/lilith-authority-dev"]["postMeta"]["device"], 25)
        self.assertEqual(set(result["unchangedSections"]), set(C.IDENTICAL_SECTIONS))
        self.assertIn("RUNTIME_DIRECTORY_IS_NOT_WITNESS_STATE", result["nonclaims"])
        self.assertNotIn("PASS", json.dumps(result["nonclaims"]))

    def test_broker_started_after_reboot_is_still_only_a_lifetime_delta(self):
        post = post_facts()
        post["units"]["show"]["lilith-memory-broker.service"].update(
            ActiveState="active", SubState="running", MainPID="1234", InvocationID="0" * 32,
            ExecMainStartTimestamp="Wed 2026-09-30 01:05:00 UTC")
        self.assertEqual(run(pre_facts(), post)["unexpected"], [])

    def test_runtime_dirs_already_present_before_the_reboot(self):
        pre = pre_facts()
        pre["pr1Objects"]["/run/lilith-authority-dev"] = stat(mode="0700", inode=50, device=25)
        pre["namespaceInventory"]["/run"].append("lilith-authority-dev")
        result = run(pre, post_facts(pre))
        self.assertEqual(result["unexpected"], [])
        self.assertEqual(result["or6"]["/run/lilith-authority-dev"]["pre"], "PRESENT_EXACT_TMPFILES_SPEC")

    def test_accepted_pre_digest_is_checked_when_given(self):
        pre = pre_facts()
        accepted = report(pre)["stableSha256"]
        self.assertTrue(run(pre, post_facts(), accepted=accepted)["preMatchesAccepted"])
        result = run(pre, post_facts(), accepted="0" * 64)
        self.assertIn("PRE_NOT_ACCEPTED_BASELINE", result["unexpected"])


class SuspiciousChangeTests(unittest.TestCase):
    def assertUnexpected(self, mutate, code, *, kernel=NEW_KERNEL):
        post = post_facts()
        mutate(post)
        result = run(pre_facts(), post, kernel)
        self.assertEqual(result["REBOOT_OBSERVATION_COMPARISON"], "FAIL", code)
        self.assertIn(code, result["unexpected"])

    def test_authority_material_and_custody_changes_are_unexpected(self):
        cases = {
            "SECTION_CHANGED:currentBlob": lambda f: f["currentBlob"].update(sha256="0" * 64),
            "SECTION_CHANGED:hostKey": lambda f: f["hostKey"].update(ctimeNs=1),
            "SECTION_CHANGED:releases": lambda f: f["releases"]["releaseEntries"].append("b" * 40),
            "SECTION_CHANGED:hostFiles": lambda f: f["hostFiles"]["/usr/local/sbin/lilith-activation-verify"]
            .update(sha256="0"),
            "SECTION_CHANGED:accounts": lambda f: f["accounts"]["lilith-recovery-witness"].update(uid=0),
            "SECTION_CHANGED:listings": lambda f: f["listings"]["/etc/lilith-authority-custody/prepared"]
            .update({"x": "file"}),
            "SECTION_CHANGED:filesystems": lambda f: f["filesystems"]["/etc"].update(device=2050),
            "PR1_OBJECT_CHANGED:/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred":
                lambda f: f["pr1Objects"].update({"/etc/lilith-recovery-witness/credentials/"
                                                  "lilith-recovery-witness.witness.cred": stat("file", mode="0600")}),
            "PR1_OBJECT_CHANGED:/var/lib/lilith-recovery-witness":
                lambda f: f["pr1Objects"].update({"/var/lib/lilith-recovery-witness": stat(mode="2750")}),
            "PR1_OBJECT_CHANGED:/var/lib/lilith-authority-dev":
                lambda f: f["pr1Objects"].update({"/var/lib/lilith-authority-dev": stat(mode="0700")}),
            "PR1_OBJECT_CHANGED:/run/credentials/lilith-authority-dev.service":
                lambda f: f["pr1Objects"].update({"/run/credentials/lilith-authority-dev.service": stat(mode="0700")}),
            "PR1_OBJECT_CHANGED:/etc/lilith-authority-custody":
                lambda f: f["pr1Objects"]["/etc/lilith-authority-custody"].update(inode=99),
            "NAMESPACE_CHANGED:/etc": lambda f: f["namespaceInventory"]["/etc"].append("lilith-authority-hold"),
        }
        for code, mutate in cases.items():
            with self.subTest(code):
                self.assertUnexpected(mutate, code)

    def test_authority_or_witness_units_must_not_change(self):
        for name in ("lilith-authority-dev.service", "lilith-recovery-witness-owner.socket"):
            with self.subTest(name):
                self.assertUnexpected(lambda f: f["units"]["show"][name].update(
                    ActiveState="active", InvocationID="1" * 32), f"UNIT_PROPERTY_CHANGED:{name}:ActiveState")
                self.assertUnexpected(lambda f: f["units"]["show"][name].update(UnitFileState="enabled"),
                                      f"UNIT_PROPERTY_CHANGED:{name}:UnitFileState")
        self.assertUnexpected(lambda f: f["units"].update(enablementOrDropInEntries=[
            "etc/systemd/system/sockets.target.wants/lilith-authority-dev.socket"]), "ENABLEMENT_OR_DROPIN_CHANGED")
        self.assertUnexpected(lambda f: f["units"]["show"]["lilith-memory-broker.service"].update(
            FragmentPath="/run/systemd/transient/x"), "UNIT_PROPERTY_CHANGED:lilith-memory-broker.service:FragmentPath")
        self.assertUnexpected(lambda f: f["units"]["show"]["lilith-memory-broker.service"].update(
            InvocationID="42af2691b8d24ee5a92a286197c5444c"), "BROKER_INVOCATION_SURVIVED_REBOOT")

    def test_or6_runtime_directories(self):
        self.assertUnexpected(lambda f: f["pr1Objects"]["/run/lilith-authority-dev"].update(mode="0755"),
                              "OR6_RUNTIME_DIR_WRONG_SPEC:/run/lilith-authority-dev")
        self.assertUnexpected(lambda f: f["pr1Objects"]["/run/lilith-recovery-witness"].update(gid=984),
                              "OR6_RUNTIME_DIR_WRONG_SPEC:/run/lilith-recovery-witness")
        self.assertUnexpected(lambda f: f["pr1Objects"]["/run/lilith-recovery-witness"].update(kind="symlink"),
                              "OR6_RUNTIME_DIR_WRONG_SPEC:/run/lilith-recovery-witness")
        self.assertUnexpected(lambda f: f["pr1Objects"].update({"/run/lilith-authority-dev": None}),
                              "OR6_TMPFILES_RUNTIME_DIR_NOT_CREATED:/run/lilith-authority-dev")

    def test_run_namespace(self):
        self.assertUnexpected(lambda f: f["namespaceInventory"]["/run"].append("lilith-authority-dev-staging"),
                              "RUN_ENTRY_ADDED:lilith-authority-dev-staging")
        self.assertUnexpected(lambda f: f["namespaceInventory"]["/run"].remove("lilith-memory"),
                              "RUN_ENTRY_NOT_RECREATED:lilith-memory")

    def test_host_and_reboot_facts(self):
        self.assertUnexpected(lambda f: f["host"].update(bootId=PRE_BOOT), "REBOOT_NOT_OBSERVED")
        self.assertUnexpected(lambda f: f["host"].update(bootId="not-a-boot"), "BOOT_ID_INVALID")
        self.assertUnexpected(lambda f: f["host"].update(kernel=OLD_KERNEL), "KERNEL_NOT_EXPECTED")
        self.assertUnexpected(lambda f: None, "KERNEL_NOT_EXPECTED", kernel="7.0.0-9999-gcp")
        self.assertUnexpected(lambda f: f["host"].update(rebootRequired=True), "POST_REBOOT_REQUIRED_STILL_PRESENT")
        self.assertUnexpected(lambda f: f["host"].update(machineId="0" * 32), "HOST_CHANGED:machineId")
        self.assertUnexpected(lambda f: f["host"].update(swaps=["/swapfile file 1 0 -2"]), "HOST_CHANGED:swaps")
        self.assertUnexpected(lambda f: f["host"].update(utcNow="2026-09-29T00:00:00Z"), "POST_NOT_AFTER_PRE")
        pre = pre_facts()
        pre["host"]["rebootRequired"] = False
        self.assertIn("PRE_REBOOT_REQUIRED_NOT_PRESENT", run(pre, post_facts(pre))["unexpected"])


class TranscriptTests(unittest.TestCase):
    def test_digest_is_recomputed_never_trusted(self):
        text = transcript(pre_facts())
        tampered = text.replace('"6a61c350"', '"00000000"')
        with self.assertRaises(C.CompareError) as caught:
            C.parse_transcript(tampered)
        self.assertEqual(caught.exception.reason, "STABLE_DIGEST_MISMATCH")
        value = report(pre_facts())
        value["sectionSha256"]["host"] = "0" * 64
        with self.assertRaises(C.CompareError) as caught:
            C.parse_transcript(json.dumps(value) + f"\nPR1A_HOST_OBSERVATION=COMPLETE stableSha256="
                                                   f"{value['stableSha256']}\n")
        self.assertEqual(caught.exception.reason, "SECTION_DIGEST_MISMATCH")

    def test_volatile_facts_do_not_change_the_digest(self):
        facts = pre_facts()
        other = copy.deepcopy(facts)
        other["host"].update(uptimeSeconds="1", utcNow="2030-01-01T00:00:00Z")
        self.assertEqual(report(facts)["stableSha256"], report(other)["stableSha256"])

    def test_incomplete_or_foreign_transcripts_are_refused(self):
        good = transcript(pre_facts())
        value = report(pre_facts())
        for text, reason in ((good.rsplit("\n", 2)[0] + "\n", "TRANSCRIPT_NOT_COMPLETE"),
                             ("{{\n" + good.split("\n", 1)[1], "TRANSCRIPT_JSON_MALFORMED"),
                             (good.replace(C.OBSERVER_SCHEMA, "OTHER"), "OBSERVER_SCHEMA_MISMATCH")):
            with self.subTest(reason):
                with self.assertRaises(C.CompareError) as caught:
                    C.parse_transcript(text)
                self.assertEqual(caught.exception.reason, reason)
        del value["facts"]["namespaceInventory"]
        with self.assertRaises(C.CompareError) as caught:
            C.parse_transcript(json.dumps(value) + "\nPR1A_HOST_OBSERVATION=COMPLETE stableSha256=" + "0" * 64)
        self.assertEqual(caught.exception.reason, "OBSERVER_SECTIONS_MISMATCH")

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            pre, post, bad = (Path(directory) / name for name in ("pre", "post", "bad"))
            pre.write_text(transcript(pre_facts()), encoding="utf-8")
            post.write_text(transcript(post_facts()), encoding="utf-8")
            broken = post_facts()
            broken["currentBlob"]["sha256"] = "0" * 64
            bad.write_text(transcript(broken), encoding="utf-8")
            with open(os.devnull, "w", encoding="utf-8") as sink:
                saved = sys.stdout, sys.stderr
                sys.stdout = sys.stderr = sink
                try:
                    codes = (C.main([str(pre), str(post), NEW_KERNEL]),
                             C.main([str(pre), str(bad), NEW_KERNEL]),
                             C.main([str(pre), str(post)]),
                             C.main([str(pre), str(post), NEW_KERNEL, "short"]),
                             C.main([str(pre), str(post), "7.0; rm -rf /"]))
                finally:
                    sys.stdout, sys.stderr = saved
        self.assertEqual(codes, (0, 2, 1, 1, 1))


LOCK_OK = "/run/lilith-dev-deploy.lock|regular empty file|0|0|600|0|1"


def before_deploy() -> dict:
    """Post-M-R2: the rebooted host with the broker started once."""
    facts = post_facts()
    facts["units"]["show"]["lilith-memory-broker.service"].update(
        ActiveState="active", SubState="running", MainPID="1234", InvocationID="0" * 32,
        ExecMainStartTimestamp="Wed 2026-09-30 01:05:00 UTC")
    return facts


def after_deploy(before: dict | None = None) -> dict:
    """The same boot after one routine DEV deployment: only the deploy lock is new."""
    facts = copy.deepcopy(before or before_deploy())
    facts["host"].update(uptimeSeconds="900.00", utcNow="2026-09-30T01:30:00Z")
    facts["namespaceInventory"]["/run"] = sorted(facts["namespaceInventory"]["/run"] + ["lilith-dev-deploy.lock"])
    return facts


def routine(before: dict, after: dict, lock: str | None = LOCK_OK) -> dict:
    return C.compare_routine_deploy(C.parse_transcript(transcript(before)), C.parse_transcript(transcript(after)),
                                    lock_stat=None if lock is None else C.parse_lock_stat(lock))


class RoutineDeployTests(unittest.TestCase):
    """§10: post-M-R2 -> post-routine-deploy. Only the reviewed deploy lock may appear."""

    def assertRoutineFails(self, mutate, code, lock=LOCK_OK):
        after = after_deploy()
        mutate(after)
        result = routine(before_deploy(), after, lock)
        self.assertEqual(result["ROUTINE_DEPLOY_OBSERVATION_COMPARISON"], "FAIL", code)
        self.assertIn(code, result["unexpected"])

    def test_exact_reviewed_deploy_lock_creation_is_accepted(self):
        result = routine(before_deploy(), after_deploy())
        self.assertEqual(result["ROUTINE_DEPLOY_OBSERVATION_COMPARISON"], "PASS", result["unexpected"])
        self.assertEqual(result["expected"], ["DEPLOY_LOCK_CREATED"])
        self.assertIs(result["rawDigestEqual"], False)  # the raw digest legitimately differs
        self.assertEqual(result["deployLock"], C.DEPLOY_LOCK_SPEC)
        self.assertIn("DEPLOY_LOCK_IS_NOT_AUTHORITY", result["nonclaims"])

    def test_lock_already_present_and_unchanged_needs_no_facts(self):
        before = after_deploy()
        after = copy.deepcopy(before)
        after["host"]["utcNow"] = "2026-09-30T02:00:00Z"
        result = routine(before, after, None)
        self.assertEqual(result["ROUTINE_DEPLOY_OBSERVATION_COMPARISON"], "PASS", result["unexpected"])
        self.assertIs(result["rawDigestEqual"], True)
        self.assertEqual(routine(before, after)["unexpected"], [])  # facts still checked when given

    def test_lock_creation_without_its_stat_facts_fails_closed(self):
        result = routine(before_deploy(), after_deploy(), None)
        self.assertEqual(result["unexpected"], ["DEPLOY_LOCK_FACTS_MISSING"])

    def test_wrong_owner_mode_path_type_size_or_links_is_rejected(self):
        cases = {
            "uid": "/run/lilith-dev-deploy.lock|regular empty file|1001|0|600|0|1",
            "gid": "/run/lilith-dev-deploy.lock|regular empty file|0|988|600|0|1",
            "mode": "/run/lilith-dev-deploy.lock|regular empty file|0|0|644|0|1",
            "path": "/run/lilith-dev-deploy.lock.new|regular empty file|0|0|600|0|1",
            "type": "/run/lilith-dev-deploy.lock|symbolic link|0|0|777|0|1",
            "links": "/run/lilith-dev-deploy.lock|regular empty file|0|0|600|0|2",
        }
        for field, line in cases.items():
            with self.subTest(field):
                result = routine(before_deploy(), after_deploy(), line)
                self.assertIn("DEPLOY_LOCK_WRONG_SPEC:" + field, result["unexpected"])
                self.assertEqual(result["ROUTINE_DEPLOY_OBSERVATION_COMPARISON"], "FAIL")
        for line in ("/run/lilith-dev-deploy.lock|directory|0|0|700|40|2",
                     "/run/lilith-dev-deploy.lock|regular file|0|0|600|12|1"):
            with self.subTest(line):
                self.assertIn("DEPLOY_LOCK_WRONG_SPEC:type", routine(before_deploy(), after_deploy(), line)["unexpected"])
        self.assertIn("DEPLOY_LOCK_WRONG_SPEC:size",
                      routine(before_deploy(), after_deploy(),
                              "/run/lilith-dev-deploy.lock|regular empty file|0|0|600|12|1")["unexpected"])

    def test_malformed_lock_stat_is_refused(self):
        for text in ("", LOCK_OK + "\n" + LOCK_OK, "/run/lilith-dev-deploy.lock|regular empty file|0|0|600|0",
                     "stat: cannot statx '/run/lilith-dev-deploy.lock': No such file or directory",
                     "/run/x|y|0|0|600|0|1|extra"):
            with self.subTest(text):
                with self.assertRaises(C.CompareError) as caught:
                    C.parse_lock_stat(text)
                self.assertEqual(caught.exception.reason, "LOCK_STAT_MALFORMED")

    def test_lock_facts_without_a_lock_entry_fail(self):
        before = before_deploy()
        after = copy.deepcopy(before)
        after["host"]["utcNow"] = "2026-09-30T02:00:00Z"
        self.assertIn("DEPLOY_LOCK_FACTS_WITHOUT_ENTRY", routine(before, after)["unexpected"])

    def test_unexpected_additional_run_changes_are_rejected(self):
        run = lambda f: f["namespaceInventory"]["/run"]  # noqa: E731
        cases = {
            "NAMESPACE_ENTRY_ADDED:/run:lilith-dev-deploy.lock2": lambda f: run(f).append("lilith-dev-deploy.lock2"),
            "NAMESPACE_ENTRY_ADDED:/run:lilith-authority-dev.lock": lambda f: run(f).append("lilith-authority-dev.lock"),
            "NAMESPACE_ENTRY_REMOVED:/run:lilith-memory": lambda f: run(f).remove("lilith-memory"),
            "NAMESPACE_ENTRY_REMOVED:/run:lilith-recovery-witness": lambda f: run(f).remove("lilith-recovery-witness"),
            "NAMESPACE_ENTRY_ADDED:/etc:lilith-dev-deploy.lock": lambda f: f["namespaceInventory"]["/etc"].append(
                "lilith-dev-deploy.lock"),
            "NAMESPACE_ENTRY_ADDED:/opt:lilith-extra": lambda f: f["namespaceInventory"]["/opt"].append("lilith-extra"),
        }
        for code, mutate in cases.items():
            with self.subTest(code):
                self.assertRoutineFails(mutate, code)

    def test_persistent_state_drift_still_fails(self):
        cases = {
            "SECTION_CHANGED:currentBlob": lambda f: f["currentBlob"].update(ctimeNs=1),
            "SECTION_CHANGED:hostKey": lambda f: f["hostKey"].update(inode=1),
            "SECTION_CHANGED:releases": lambda f: f["releases"]["releaseEntries"].append("c" * 40),
            "SECTION_CHANGED:hostFiles": lambda f: f["hostFiles"]["/usr/local/sbin/lilith-activation-verify"]
            .update(sha256="1"),
            "SECTION_CHANGED:accounts": lambda f: f["accounts"]["lilith-authority-dev"].update(gid=0),
            "SECTION_CHANGED:listings": lambda f: f["listings"]["/etc/lilith-authority-custody/prepared"]
            .update({"k": "file"}),
            "SECTION_CHANGED:filesystems": lambda f: f["filesystems"]["/etc"].update(device=1),
            "PR1_OBJECT_CHANGED:/var/lib/lilith-recovery-witness":
                lambda f: f["pr1Objects"].update({"/var/lib/lilith-recovery-witness": stat(mode="2750")}),
            "PR1_OBJECT_CHANGED:/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred":
                lambda f: f["pr1Objects"].update({"/etc/lilith-recovery-witness/credentials/"
                                                  "lilith-recovery-witness.witness.cred": stat("file", mode="0600")}),
            "PR1_OBJECT_CHANGED:/etc/lilith-authority-custody":
                lambda f: f["pr1Objects"]["/etc/lilith-authority-custody"].update(mode="0755"),
        }
        for code, mutate in cases.items():
            with self.subTest(code):
                self.assertRoutineFails(mutate, code)

    def test_authority_witness_runtime_and_service_drift_still_fails(self):
        cases = {
            "PR1_OBJECT_CHANGED:/run/lilith-authority-dev":
                lambda f: f["pr1Objects"]["/run/lilith-authority-dev"].update(inode=999),
            "PR1_OBJECT_CHANGED:/run/lilith-recovery-witness":
                lambda f: f["pr1Objects"].update({"/run/lilith-recovery-witness": None}),
            "PR1_OBJECT_CHANGED:/run/credentials/lilith-authority-dev.service":
                lambda f: f["pr1Objects"].update({"/run/credentials/lilith-authority-dev.service": stat(mode="0700")}),
            "UNIT_PROPERTY_CHANGED:lilith-authority-dev.service:ActiveState":
                lambda f: f["units"]["show"]["lilith-authority-dev.service"].update(ActiveState="active"),
            "UNIT_PROPERTY_CHANGED:lilith-recovery-witness-signer.socket:UnitFileState":
                lambda f: f["units"]["show"]["lilith-recovery-witness-signer.socket"].update(UnitFileState="enabled"),
            "UNIT_PROPERTY_CHANGED:lilith-memory-broker.service:InvocationID":
                lambda f: f["units"]["show"]["lilith-memory-broker.service"].update(InvocationID="f" * 32),
            "UNIT_PROPERTY_CHANGED:lilith-memory-broker.service:NRestarts":
                lambda f: f["units"]["show"]["lilith-memory-broker.service"].update(NRestarts="1"),
            "ENABLEMENT_OR_DROPIN_CHANGED": lambda f: f["units"].update(enablementOrDropInEntries=["x"]),
            "HOST_CHANGED:bootId": lambda f: f["host"].update(bootId=PRE_BOOT),
            "HOST_CHANGED:kernel": lambda f: f["host"].update(kernel=OLD_KERNEL),
            "HOST_CHANGED:rebootRequired": lambda f: f["host"].update(rebootRequired=True),
            "AFTER_NOT_LATER": lambda f: f["host"].update(utcNow="2026-09-30T01:00:00Z"),
        }
        for code, mutate in cases.items():
            with self.subTest(code):
                self.assertRoutineFails(mutate, code)

    def test_reboot_mode_is_unchanged_by_the_lock_rule(self):
        # The reboot comparison never accepts a new lock: after a boot /run starts without it.
        post = post_facts()
        post["namespaceInventory"]["/run"].append("lilith-dev-deploy.lock")
        self.assertIn("RUN_ENTRY_ADDED:lilith-dev-deploy.lock", run(pre_facts(), post)["unexpected"])

    def test_routine_deploy_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            (d / "before").write_text(transcript(before_deploy()), encoding="utf-8")
            (d / "after").write_text(transcript(after_deploy()), encoding="utf-8")
            (d / "lock").write_text(LOCK_OK + "\n", encoding="utf-8")
            (d / "badlock").write_text(LOCK_OK.replace("|600|", "|666|") + "\n", encoding="utf-8")
            with open(os.devnull, "w", encoding="utf-8") as sink:
                saved = sys.stdout, sys.stderr
                sys.stdout = sys.stderr = sink
                try:
                    codes = (C.main(["routine-deploy", str(d / "before"), str(d / "after"), str(d / "lock")]),
                             C.main(["routine-deploy", str(d / "before"), str(d / "after")]),
                             C.main(["routine-deploy", str(d / "before"), str(d / "after"), str(d / "badlock")]),
                             C.main(["routine-deploy", str(d / "before")]),
                             C.main(["routine-deploy", str(d / "before"), str(d / "after"), str(d / "missing")]))
                finally:
                    sys.stdout, sys.stderr = saved
        self.assertEqual(codes, (0, 2, 2, 1, 1))


class ContractTests(unittest.TestCase):
    def test_offline_only(self):
        tree = ast.parse(SOURCE)
        imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
                    for alias in node.names}
        imported |= {node.module.split(".")[0] for node in ast.walk(tree)
                     if isinstance(node, ast.ImportFrom) and node.module}
        self.assertLessEqual(imported, {"__future__", "hashlib", "json", "re", "sys", "pathlib"})
        for token in ("subprocess", "socket", "urllib", "os.system", "gcloud", "write_text", "write_bytes",
                      "unlink", "open("):
            self.assertNotIn(token, SOURCE.split('"""', 2)[2], token)

    def test_deploy_lock_spec_matches_the_pinned_deploy_helper(self):
        helper = (ROOT / "scripts/dev_deployer/lilith-dev-deploy").read_text(encoding="utf-8")
        self.assertIn('readonly LOCK_PATH="/run/lilith-dev-deploy.lock"', helper)
        self.assertIn("\numask 077\n", helper)
        self.assertIn('exec 9>"${LOCK_PATH}"', helper)
        # The lock is only ever created (never removed, chmod-ed or chown-ed): its one use is the exec.
        self.assertEqual(helper.count("${LOCK_PATH}"), 1)
        self.assertEqual(helper.count("/run/"), 1)
        self.assertEqual(helper.count("lilith-dev-deploy.lock"), 1)
        import hashlib
        from scripts import verify_broker_dev_current_incarnation as broker
        self.assertEqual(hashlib.sha256((ROOT / "scripts/dev_deployer/lilith-dev-deploy").read_bytes()).hexdigest(),
                         broker.DEPLOY_HELPER_SHA)
        self.assertEqual(C.DEPLOY_LOCK, "/run/" + C.DEPLOY_LOCK_NAME)
        self.assertEqual(C.DEPLOY_LOCK_SPEC, {"path": C.DEPLOY_LOCK, "type": "regular empty file", "uid": "0",
                                              "gid": "0", "mode": "600", "size": "0", "links": "1"})
        record = (ROOT / "docs/architecture/slice-15b2b-b1b3e-pre-pr1b-reboot-rebaseline.md").read_text(encoding="utf-8")
        self.assertIn(C.LOCK_STAT_FORMAT, record)
        self.assertIn("routine-deploy", record)

    def test_tmpfiles_specs_match_the_installed_assets(self):
        authority = (ROOT / "services/authority-dev/deploy/lilith-authority-dev.tmpfiles.conf").read_text()
        witness = (ROOT / "services/recovery-witness/deploy/lilith-recovery-witness.tmpfiles.conf").read_text()
        self.assertEqual(authority, "d /run/lilith-authority-dev 0700 root root -\n")
        self.assertEqual(witness, "d /run/lilith-recovery-witness 0710 root lilith-authority-dev -\n")
        self.assertEqual(C.TMPFILES_RUNTIME_DIRS["/run/lilith-authority-dev"], ("dir", 0, 0, "0700"))
        self.assertEqual(C.TMPFILES_RUNTIME_DIRS["/run/lilith-recovery-witness"], ("dir", 0, None, "0710"))
        self.assertEqual(C.SIGNER_ACCOUNT, "lilith-authority-dev")
        broker = (ROOT / "services/memory-broker/deploy/lilith-memory-broker.tmpfiles.conf").read_text()
        self.assertIn("d /run/lilith-memory ", broker)

    @unittest.skipUnless(os.name == "posix", "the observer imports pwd/grp")
    def test_digest_and_sections_match_the_real_observer(self):
        sys.path.insert(0, str(ROOT / "services/authority-dev/ceremony"))
        try:
            observer = importlib.import_module("observe_authority_dev_host")
        finally:
            sys.path.pop(0)
        facts = pre_facts()
        self.assertEqual(observer.report(copy.deepcopy(facts)), report(facts))
        self.assertEqual(observer.VOLATILE, C.VOLATILE)
        self.assertEqual(observer.SCHEMA, C.OBSERVER_SCHEMA)
        for path in C.TMPFILES_RUNTIME_DIRS:
            self.assertIn(path, observer.PR1_OBJECTS)
        self.assertIn(C.BROKER_UNIT, observer.UNITS)
        self.assertLessEqual(C.BROKER_PROCESS_LIFETIME, set(observer.UNIT_PROPERTIES.split(",")))


if __name__ == "__main__":
    unittest.main()
