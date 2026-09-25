"""Source-only contracts; these tests never contact DEV or run systemctl."""

from __future__ import annotations

import copy
from contextlib import closing
import inspect
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from scripts import memory_broker_stage2_control as stage2
from scripts import memory_broker_stage3_transition as transition
from scripts import memory_broker_stage3_liveness as liveness
from scripts.test_broker_candidate_dev_snapshot import accepted_result


class Stage3TransitionContracts(unittest.TestCase):
    def test_physical_bytes_must_match_the_trusted_accepted_snapshot(self):
        accepted = accepted_result()
        snapshot = accepted["snapshot"]
        hashes = {
            "owner": {transition.OWNER_FILES[0]: snapshot["files"][
                str(stage2.OWNER_DB)]["sha256"]},
            "evidence": {transition.EVIDENCE_FILES[0]: snapshot["files"][
                str(stage2.EVIDENCE_DB)]["sha256"]},
        }
        for kind, main in (("owner", transition.OWNER_FILES[0]),
                           ("evidence", transition.EVIDENCE_FILES[0])):
            for suffix in ("-wal", "-shm"):
                hashes[kind][main + suffix] = snapshot["databases"][kind][
                    "sidecars"][suffix]["sha256"]
        config_sha = snapshot["files"][str(stage2.CONFIG / "dev.json")]["sha256"]
        transition.bind_accepted_bytes(accepted, hashes, config_sha)
        changed = copy.deepcopy(hashes)
        changed["owner"][transition.OWNER_FILES[0]] = "0" * 64
        with self.assertRaisesRegex(transition.TransitionError,
                                    "STAGE3_ACCEPTED_SNAPSHOT_BYTE_DRIFT"):
            transition.bind_accepted_bytes(accepted, changed, config_sha)

    @unittest.skipIf(os.name != "nt" and os.geteuid() != 0,
                     "positive custody fixture requires root-owned journal")
    def test_journal_is_one_shot_ordered_fsynced_and_tamper_evident(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            journal = transition.Journal(parent / "vault")
            journal.create({"stateDevice": parent.stat().st_dev, "test": "intent"})
            self.assertEqual(journal.last(), ("INTENT", {
                "stateDevice": parent.stat().st_dev, "test": "intent"}))
            journal.append("QUIESCED", {"test": "stopped"})
            self.assertEqual(journal.last()[0], "QUIESCED")
            with self.assertRaisesRegex(transition.TransitionError,
                                        "STAGE3_JOURNAL_ILLEGAL_TRANSITION"):
                journal.append("INTENT", {})
            with self.assertRaisesRegex(transition.TransitionError,
                                        "STAGE3_VAULT_COLLISION"):
                journal.create({"stateDevice": parent.stat().st_dev})
            first = parent / "vault/000-INTENT.json"
            value = json.loads(first.read_bytes())
            value["record"]["test"] = "changed"
            first.write_bytes(transition.canonical(value))
            with self.assertRaisesRegex(transition.TransitionError,
                                        "STAGE3_JOURNAL_INVALID"):
                journal.last()

    def test_accepted_tree_copy_is_separate_and_original_bytes_survive(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            source, target = parent / "accepted", parent / "restored"
            source.mkdir()
            payloads = {name: (name + ":accepted").encode()
                        for name in transition.OWNER_FILES}
            for name, raw in payloads.items():
                (source / name).write_bytes(raw)
            original_regular = transition.regular
            with patch.object(transition, "regular",
                              side_effect=lambda path, **_kw: original_regular(path)), \
                 patch.object(transition.os, "chown", create=True), \
                 patch.object(transition.os, "fchown", create=True):
                transition.copy_state_tree(source, target, transition.OWNER_FILES)
            self.assertEqual({name: (source / name).read_bytes() for name in payloads},
                             payloads)
            self.assertEqual({name: (target / name).read_bytes() for name in payloads},
                             payloads)
            with self.assertRaisesRegex(transition.TransitionError,
                                        "STAGE3_COPY_COLLISION"):
                transition.copy_state_tree(source, target, transition.OWNER_FILES)

    def test_fork_changes_only_private_release_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = transition.Paths(root=root / "opt", config=root / "etc",
                                     state=root / "state", vault=root / "vault")
            paths.vault.mkdir()
            for kind, names in (("owner", transition.OWNER_FILES),
                                ("evidence", transition.EVIDENCE_FILES)):
                folder = paths.saved(kind)
                folder.mkdir()
                db_path = folder / names[0]
                with closing(sqlite3.connect(db_path)) as db:
                    if kind == "owner":
                        for table in transition.HISTORY["owner"]:
                            db.execute(f'CREATE TABLE "{table}" (id TEXT PRIMARY KEY, value TEXT)')
                            db.execute(f'INSERT INTO "{table}" VALUES (?,?)',
                                       (table, "accepted"))
                    else:
                        db.execute("CREATE TABLE synthetic_schema_v1 "
                                   "(profile TEXT PRIMARY KEY, release_sha TEXT)")
                        db.execute("INSERT INTO synthetic_schema_v1 VALUES (?,?)",
                                   ("B1B2_SYNTHETIC_EVIDENCE_V1", stage2.RELEASE))
                        db.execute("CREATE TABLE synthetic_evidence_v1 "
                                   "(id TEXT PRIMARY KEY, value TEXT)")
                        db.execute("INSERT INTO synthetic_evidence_v1 VALUES (?,?)",
                                   ("historical", "accepted"))
                    db.commit()
                for sidecar in names[1:]:
                    (folder / sidecar).write_bytes(b"")
            original = {kind: {name: (paths.saved(kind) / name).read_bytes()
                               for name in names} for kind, names in (
                ("owner", transition.OWNER_FILES),
                ("evidence", transition.EVIDENCE_FILES))}
            original_regular = transition.regular
            with patch.object(transition, "regular",
                              side_effect=lambda path, **_kw: original_regular(path)), \
                 patch.object(transition, "tree_fingerprints",
                              return_value={"accepted": "exact"}), \
                 patch.object(transition.os, "chown", create=True), \
                 patch.object(transition.os, "fchown", create=True):
                provenance = transition.fork_state(paths, {"accepted": "exact"})
            self.assertEqual(provenance["inheritedRows"], provenance["forkRows"])
            self.assertEqual({kind: {name: (paths.saved(kind) / name).read_bytes()
                                     for name in names} for kind, names in (
                ("owner", transition.OWNER_FILES),
                ("evidence", transition.EVIDENCE_FILES))}, original)
            with closing(sqlite3.connect(paths.fork("evidence") /
                                         transition.EVIDENCE_FILES[0])) as db:
                self.assertEqual(db.execute(
                    "SELECT release_sha FROM synthetic_schema_v1").fetchall(),
                    [(stage2.STAGE3_RELEASE,)])

    @staticmethod
    def restored():
        intent = {
            "acceptedRelease": stage2.RELEASE,
            "candidateRelease": stage2.STAGE3_RELEASE,
            "acceptedSnapshotSha256": stage2.STAGE3_ACCEPTED_SNAPSHOT_SHA,
            "configSha256": "a" * 64,
            "stateHashes": {"owner": {"owner_control.db": "b" * 64},
                            "evidence": {"synthetic_evidence.db": "c" * 64}},
            "acceptedInvocationId": "old-invocation",
            "apiBaseline": {"status": "unchanged"},
            "authorizationId": "d" * 32,
        }
        observed = {
            "profile": transition.PROFILE_RESTORED,
            "acceptedRelease": stage2.RELEASE,
            "candidateRelease": stage2.STAGE3_RELEASE,
            "selector": f"releases/{stage2.RELEASE}",
            "acceptedSnapshotSha256": stage2.STAGE3_ACCEPTED_SNAPSHOT_SHA,
            "configSha256": intent["configSha256"],
            "stateHashes": intent["stateHashes"],
            "vaultAcceptedHashes": intent["stateHashes"],
            "experimentHashes": {"owner": {"owner_control.db": "e" * 64}},
            "invocationId": "new-invocation",
            "previousInvocationId": "old-invocation",
            "apiBaseline": intent["apiBaseline"],
            "authorizationId": intent["authorizationId"],
            "evidenceSha256": "f" * 64,
            "armAbsent": True,
        }
        return intent, observed

    def test_restored_profile_requires_original_bytes_and_new_incarnation(self):
        intent, observed = self.restored()
        transition.validate_restored_state(intent, observed)
        for field, value in (
            ("invocationId", "old-invocation"),
            ("stateHashes", {"owner": {"owner_control.db": "0" * 64}}),
            ("configSha256", "0" * 64),
            ("armAbsent", False),
            ("profile", "POST_STAGE_II_ACCEPTED_V1"),
            ("apiBaseline", {"status": "changed"}),
        ):
            changed = copy.deepcopy(observed)
            changed[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(
                    transition.TransitionError, "STAGE3_RESTORED_PROFILE_MISMATCH"):
                transition.validate_restored_state(intent, changed)

    def test_evidence_seal_rejects_new_evidence_and_requires_consumed_no_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = transition.Paths(root=root / "opt", config=root / "etc",
                                     state=root / "state", vault=root / "vault")
            paths.vault.mkdir()
            for kind in transition.HISTORY:
                paths.active(kind).mkdir(parents=True)
            owner_path = paths.active("owner") / transition.OWNER_FILES[0]
            evidence_path = paths.active("evidence") / transition.EVIDENCE_FILES[0]
            with closing(sqlite3.connect(owner_path)) as db:
                for table in transition.HISTORY["owner"]:
                    if table == "owner_proof_challenge_v1":
                        db.execute("CREATE TABLE owner_proof_challenge_v1 "
                                   "(challenge_id TEXT PRIMARY KEY, state TEXT, "
                                   "challenge_json BLOB)")
                    elif table == "owner_request_v1":
                        db.execute("CREATE TABLE owner_request_v1 "
                                   "(challenge_id TEXT PRIMARY KEY, request_digest TEXT, "
                                   "request_json BLOB)")
                    elif table == "synthetic_claim_v1":
                        db.execute("CREATE TABLE synthetic_claim_v1 "
                                   "(challenge_id TEXT PRIMARY KEY)")
                    else:
                        db.execute(f'CREATE TABLE "{table}" '
                                   '(id TEXT PRIMARY KEY, value TEXT)')
                        db.execute(f'INSERT INTO "{table}" VALUES (?,?)',
                                   (table, "accepted"))
                db.commit()
            with closing(sqlite3.connect(evidence_path)) as db:
                db.execute("CREATE TABLE synthetic_schema_v1 "
                           "(profile TEXT PRIMARY KEY, release_sha TEXT)")
                db.execute("INSERT INTO synthetic_schema_v1 VALUES (?,?)",
                           ("B1B2_SYNTHETIC_EVIDENCE_V1", stage2.STAGE3_RELEASE))
                db.execute("CREATE TABLE synthetic_evidence_v1 "
                           "(challenge_id TEXT PRIMARY KEY)")
                db.commit()
            inherited = transition.row_fingerprints(owner_path, evidence_path)
            challenge_id = "och." + "a" * 32
            request_digest, action_digest = "b" * 64, "c" * 64
            with closing(sqlite3.connect(owner_path)) as db:
                db.execute("INSERT INTO owner_proof_challenge_v1 VALUES (?,?,?)",
                           (challenge_id, "CONSUMED", json.dumps({
                               "requestDigest": request_digest,
                               "actionDigest": action_digest}).encode()))
                db.execute("INSERT INTO owner_request_v1 VALUES (?,?,?)",
                           (challenge_id, request_digest, json.dumps({
                               "actionDigest": action_digest}).encode()))
                db.commit()
            (paths.vault / "000-INTENT.json").write_bytes(transition.canonical({
                "record": {"authorizationId": "d" * 32}}))
            (paths.vault / "fork-provenance.json").write_bytes(
                transition.canonical({"inheritedRows": inherited}))
            used, marker, arm = (root / name for name in ("used", "marker", "arm"))
            used.write_bytes(transition.canonical({"authorizationId": "d" * 32}))
            identity = {"pid": 501, "bootId": "boot", "startTicks": 100,
                        "invocationId": "first", "releaseSha": stage2.STAGE3_RELEASE}
            evidence = {
                "schema": "Stage3A2CompletedEvidenceV1",
                "candidateRelease": stage2.STAGE3_RELEASE,
                "challengeId": challenge_id,
                "requestDigest": request_digest, "actionDigest": action_digest,
                "barrierEventSha256": "e" * 64,
                "stoppedProcessIdentity": identity,
                "killedProcessIdentity": identity.copy(),
                "restartedInvocationId": "second",
                "recoveryOutcome": "PROOF_BURNED_NO_CLAIM",
                "replayOutcome": "REJECTED_BEFORE_CLAIM",
                "stoppedWalSha256": "f" * 64,
            }
            controller = transition.TransitionController(paths)
            original_regular = transition.regular
            with patch.object(controller.journal, "last", return_value=(
                    "CANDIDATE_ACTIVE", {"invocationId": "first"})), \
                 patch.object(controller.journal, "append"), \
                 patch.object(transition, "regular",
                              side_effect=lambda path, **_kw: original_regular(path)), \
                 patch.object(stage2, "STAGE3_USED", used), \
                 patch.object(stage2, "STAGE3_MARKER", marker), \
                 patch.object(stage2, "STAGE3_ARM", arm), \
                 patch.object(stage2, "assert_unit_state"), \
                 patch.object(stage2, "show", return_value={"InvocationID": "second"}), \
                 patch.object(stage2, "stage3_verify_candidate_release"), \
                 patch.object(liveness, "verify"), \
                 patch.object(transition.os, "readlink",
                              return_value=f"releases/{stage2.STAGE3_RELEASE}"):
                with closing(sqlite3.connect(evidence_path)) as db:
                    db.execute("INSERT INTO synthetic_evidence_v1 VALUES (?)",
                               (challenge_id,))
                    db.commit()
                with self.assertRaisesRegex(transition.TransitionError,
                                            "STAGE3_EVIDENCE_HISTORY_DRIFT"):
                    controller._seal_evidence(evidence)
                with closing(sqlite3.connect(evidence_path)) as db:
                    db.execute("DELETE FROM synthetic_evidence_v1 WHERE challenge_id=?",
                               (challenge_id,))
                    db.commit()
                controller._seal_evidence(evidence)
            self.assertEqual(json.loads((paths.vault / "completed-evidence.json")
                                        .read_bytes()), evidence)

    def test_no_dispatch_entrypoint_or_implicit_authority(self):
        source = inspect.getsource(transition)
        self.assertNotIn('if __name__ == "__main__"', source)
        self.assertNotIn("stage3_issue_authorization(", source)
        self.assertNotIn("stage3_prepare_package(", source)
        self.assertNotIn("SIGSTOP", source)
        self.assertNotIn("SIGKILL", source)
        self.assertNotIn("stage3-transition", inspect.getsource(stage2.main))
        self.assertLess(source.index("self.journal.create(intent)"),
                        source.index("stopped()\n            original_units = "
                                     "liveness.prepare_inert(self.guard)"))

    def test_containment_still_stops_guard_and_units_if_gate_close_fails(self):
        journal = MagicMock()
        with patch.object(liveness, "close_gate", side_effect=OSError("synthetic")), \
             patch.object(transition.os.path, "lexists", return_value=True), \
             patch.object(stage2, "show", return_value={"ActiveState": "active"}), \
             patch.object(stage2, "run_fixed") as run, \
             patch.object(transition, "stopped") as stop, \
             self.assertRaisesRegex(transition.TransitionError,
                                    "STAGE3_CONTAINMENT_UNVERIFIED"):
            transition.contain_failure(journal, liveness.Paths(), "SYNTHETIC")
        run.assert_called_once_with("/usr/bin/systemctl", "stop", liveness.GUARD)
        stop.assert_called_once()
        journal.append.assert_not_called()


if __name__ == "__main__":
    unittest.main()
