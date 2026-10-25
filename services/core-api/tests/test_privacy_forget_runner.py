"""F9-C Slice 3: the governed First Interaction FORGET runner over the real L04 and L18_V2 owners and the Slice 2
Hermes owner, whose executor is a MOCK (durable JSON receipts in a temporary directory; no privileged operation).

Actor evidence is issued by the existing synthetic test actor authority (the explicitly authorized fixture); the
runner itself never issues evidence. Every failure must leave Privacy incomplete with the hold ACTIVE, and a retry
through resume() must be safe and idempotent.
"""

from __future__ import annotations

import inspect
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_canonical_runtime import TEST_CLASS, digest, stamp_text  # noqa: F401  (puts the Core API on sys.path)
from test_first_interaction_l04 import FirstInteractionCase, fi_value
from test_hermes_erasure_owner import FakeClock, SyntheticExecutor
from test_privacy_hermes_owner_v2 import SECRET, HermesOwnerCase

from lilith_memory import canonical_store
from lilith_memory import hermes_erasure_owner as H
from lilith_memory import learning_v2
from lilith_memory import memory_action_v2 as MA
from lilith_memory import memory_v2
from lilith_memory import privacy_forget_runner as R
from lilith_memory import privacy_governance as privacy
from lilith_memory import privacy_schema_v2 as V2
from lilith_memory import slice15b2a_migration

HERMES = privacy.HERMES_DEV_CONVERSATION
FI = MA.FIRST_INTERACTION_IDENTITY
FAREWELL = b"TEST_ONLY F9C3 farewell"


class ResolvingExecutor(SyntheticExecutor):
    """Mock executor that, like the real one, resolves the authorization itself from the request it receives."""

    def __init__(self, root: Path, store, **kw):
        super().__init__(root, **kw)
        self.store = store

    def build(self, request, status="COMPLETE"):
        self.authorization = self.store.resolve_erasure_authorization(
            request["authorizationRefId"], owner=HERMES, execution_nonce=request["executionNonce"])
        if self.authorization is None:
            raise PermissionError("TEST_ONLY executor: authorization did not resolve")
        return super().build(request, status)


class CountingOwner:
    """Wraps a real owner; can fail its first calls (raising, recording nothing) or lie about COMPLETE."""

    def __init__(self, owner, *, fail_times: int = 0, exc=RuntimeError, lie: bool = False):
        self.inner, self.OWNER = owner, owner.OWNER
        self.fail_times, self.exc, self.lie, self.calls = fail_times, exc, lie, 0

    def erase_authorized(self, ref, nonce):
        self.calls += 1
        if self.lie:
            return {"owner": self.OWNER, "status": "COMPLETE"}
        if self.calls <= self.fail_times:
            raise self.exc("TEST_ONLY injected owner failure")
        return self.inner.erase_authorized(ref, nonce)


class RunnerCase(FirstInteractionCase):
    def setUp(self) -> None:
        super().setUp()
        self.create()                                                     # codename "SYNTH-ALPHA" must survive
        self.migrate_fi()
        self.enable_fi()
        _action, ref = self.fi_proposal(fi_value(closing=FAREWELL.decode()))
        self.assertEqual(self.fi_store().apply(ref.proposal_ref_id).outcome, canonical_store.ACCEPTED)
        self.privacy_db = self.root / "privacy.test.db"
        slice15b2a_migration.migrate_privacy(self.privacy_db, applied_at=stamp_text(3))
        V2.upgrade_privacy_v1_to_v2(self.privacy_db, applied_at=stamp_text(4))
        V2.provision_hermes_owner_floor(self.privacy_db, deployment_environment=V2.DEV_SYNTHETIC,
                                        applied_at=stamp_text(5))
        self.privacy = privacy.PrivacyGovernanceStore(self.privacy_db, SECRET, self.actor, now_fn=lambda: self.now)
        self.clock = FakeClock()
        self.executor = self.mock_executor()
        self._n = 0

    # --- fixtures -------------------------------------------------------------------------------------------------
    def mock_executor(self, **kw):
        return ResolvingExecutor(self.root / "executor", self.privacy, **kw)

    def hermes(self, executor="default", store=None):
        return H.HermesConversationErasureOwner(
            store or self.privacy, self.executor if executor == "default" else executor,
            deployment_environment="DEV_SYNTHETIC", timeout_seconds=10.0, poll_seconds=1.0,
            sleep=self.clock.sleep, monotonic=self.clock.monotonic)

    def owners(self, store=None, **wrap):
        store = store or self.privacy
        real = {"L04": memory_v2.L04PrivacyErasureOwner(self.db, store),
                "L18_V2": memory_v2.L18V2PrivacyErasureOwner(self.db, store),
                HERMES: self.hermes(store=store)}
        real.update(wrap)
        return real

    def runner(self, owners=None, store=None):
        return R.FirstInteractionForgetRunner(store or self.privacy, owners or self.owners(store),
                                              deployment_environment="DEV_SYNTHETIC")

    def evidence(self, action=None):
        """The authorized synthetic fixture: the test actor authority issues evidence for the canonical action."""
        self._n += 1
        action = action or R.first_interaction_forget_action(self.actor.ACTOR.actor_ref_id)
        return self.actor.issue(action=action, request_digest=digest(f"forget-runner:{self._n}"),
                                nonce=f"forget.runner.{self._n}")

    def forget(self, runner=None, evidence=None, actor_ref_id=None):
        evidence = evidence or self.evidence()
        return (runner or self.runner()).forget(
            actor_ref_id=actor_ref_id or self.actor.ACTOR.actor_ref_id,
            actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            intent_ref_id=f"intent.runner.{self._n}", confirmation_event_ref=f"confirm.runner.{self._n}")

    # --- observations ---------------------------------------------------------------------------------------------
    def prows(self, sql, *params):
        conn = sqlite3.connect(self.privacy_db)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def count(self, sql, *params):
        conn = sqlite3.connect(self.db)
        try:
            return int(conn.execute(sql, params).fetchone()[0])
        finally:
            conn.close()

    def fi_rows(self):
        counts = {t: self.count(f"SELECT COUNT(*) FROM {t}") for t in sorted(learning_v2.FIRST_INTERACTION_TABLES)}
        counts["memory_item"] = self.count("SELECT COUNT(*) FROM memory_item WHERE memory_class=? AND "
                                           "subject_namespace=? AND subject_key=?", *FI)
        return counts

    def assert_fi_erased(self):
        self.assertEqual(set(self.fi_rows().values()), {0})
        self.assertNotIn(FAREWELL, self.db.read_bytes())
        self.assertEqual(self.count("SELECT COUNT(*) FROM memory_item WHERE memory_class=?", TEST_CLASS), 1)
        self.assertIn(b"SYNTH-ALPHA", self.db.read_bytes())

    def assert_incomplete(self, result, code=None):
        self.assertEqual(result.status, R.INCOMPLETE_HOLD_ACTIVE)
        if code is not None:
            self.assertEqual(result.failure_code, code)
        self.assertEqual(self.prows("SELECT state FROM privacy_hold"), [("ACTIVE",)])
        self.assertEqual(self.prows("SELECT COUNT(*) FROM privacy_completion_receipt"), [(0,)])
        self.assertIsNotNone(self.privacy.in_flight_authorization(FI))
        self.assertTrue(self.privacy.is_held(*FI))

    def assert_nothing_started(self):
        self.assertEqual(self.prows("SELECT COUNT(*) FROM privacy_hold"), [(0,)])
        self.assertEqual(self.prows("SELECT COUNT(*) FROM privacy_erasure_authorization"), [(0,)])
        self.assertEqual(self.prows("SELECT COUNT(*) FROM privacy_restore_suppression_manifest"), [(0,)])
        self.assertEqual(self.fi_rows()["memory_item"], 1)

    def evidence_unconsumed(self, evidence):
        """Prove the evidence was not consumed: a correct run can still use it."""
        self.assertEqual(self.forget(evidence=evidence).status, R.COMPLETE)


class ContractTests(RunnerCase):
    def test_runner_is_dev_synthetic_only(self):
        for environment in ("PROD", "DEV", "LIVE", "", "dev_synthetic"):
            with self.subTest(environment=environment), self.assertRaises(R.ForgetRunnerError) as caught:
                R.FirstInteractionForgetRunner(self.privacy, self.owners(), deployment_environment=environment)
            self.assertEqual(caught.exception.code, "INTERIM_V1_PATH_DEV_SYNTHETIC_ONLY")

    def test_owner_adapters_must_match_their_names(self):
        bad = self.owners()
        bad["L04"] = bad["L18_V2"]
        for owners in (bad, {**self.owners(), "UNKNOWN": self.hermes()}):
            with self.assertRaises(R.ForgetRunnerError) as caught:
                R.FirstInteractionForgetRunner(self.privacy, owners, deployment_environment="DEV_SYNTHETIC")
            self.assertEqual(caught.exception.code, "OWNER_ADAPTER_INVALID")

    def test_no_identity_session_or_owner_input_and_no_evidence_minting(self):
        params = set(inspect.signature(R.FirstInteractionForgetRunner.forget).parameters)
        self.assertEqual(params, {"self", "actor_ref_id", "actor_evidence_ref_id", "intent_ref_id",
                                  "confirmation_event_ref"})
        self.assertEqual(set(inspect.signature(R.FirstInteractionForgetRunner.resume).parameters), {"self"})
        source = inspect.getsource(R).split('"""', 2)[2]                 # code only, not the module docstring
        for forbidden in (".issue(", "resolve_and_consume", "record_owner_result", "session", "subprocess",
                          "systemctl", "os.remove", "unlink"):
            self.assertNotIn(forbidden, source)
        action = R.first_interaction_forget_action("actor.x")
        self.assertEqual((action.operation, action.identity if hasattr(action, "identity") else
                          (action.memory_class, action.subject_namespace, action.subject_key), action.purpose),
                         ("FORGET", FI, MA.OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION))


class HappyPathTests(RunnerCase):
    def test_forget_runs_every_owner_in_order_and_completes(self):
        calls = []
        owners = {n: CountingOwner(o) for n, o in self.owners().items()}
        for name, wrapped in owners.items():
            inner = wrapped.erase_authorized
            wrapped.erase_authorized = lambda ref, nonce, inner=inner, name=name: (calls.append(name),
                                                                                   inner(ref, nonce))[1]
        result = self.forget(self.runner(owners))
        self.assertEqual(result.status, R.COMPLETE, result)
        self.assertEqual((calls, result.completed_owners), (["L04", "L18_V2", HERMES], ("L04", "L18_V2", HERMES)))
        self.assert_fi_erased()
        self.assertEqual(self.executor.requests, [{"v": 1, "owner": HERMES,
                                                   "authorizationRefId": result.authorization_ref_id,
                                                   "executionNonce": self.executor.requests[0]["executionNonce"]}])
        self.assertEqual(self.prows("SELECT resource_owner FROM privacy_completion_owner_result ORDER BY 1"),
                         [(HERMES,), ("L04",), ("L18_V2",)])
        for table in ("privacy_hold", "privacy_erasure_authorization", "privacy_erasure_execution",
                      "privacy_forget_request"):
            self.assertEqual(self.prows(f"SELECT COUNT(*) FROM {table}"), [(0,)], table)
        self.assertIsNone(self.privacy.in_flight_authorization(FI))
        self.assertTrue(self.privacy.is_held(*FI))                       # restore suppression is permanent

    def test_replay_after_completion_writes_nothing_and_calls_no_owner(self):
        evidence = self.evidence()
        self.assertEqual(self.forget(evidence=evidence).status, R.COMPLETE)
        before = self.privacy_db.read_bytes()
        owners = {n: CountingOwner(o) for n, o in self.owners().items()}
        self.assertEqual(self.runner(owners).resume().status, R.ALREADY_COMPLETE)
        self.assertEqual([o.calls for o in owners.values()], [0, 0, 0])
        self.assertEqual(self.privacy_db.read_bytes(), before)
        with self.assertRaises(Exception):                                # the same evidence cannot start another
            self.forget(evidence=evidence)
        self.assertEqual(self.prows("SELECT COUNT(*) FROM privacy_hold"), [(0,)])

    def test_resume_with_nothing_started(self):
        self.assertEqual(self.runner().resume().status, R.NOT_STARTED)
        self.assert_nothing_started()


class AuthorizationTests(RunnerCase):
    def refused(self, exc_type, **kw):
        with self.assertRaises(exc_type):
            self.forget(**kw)
        self.assert_nothing_started()

    def test_evidence_for_another_action_is_refused(self):
        other = MA.action_from_fields(**{**R.first_interaction_forget_action(self.actor.ACTOR.actor_ref_id).__dict__,
                                         "payload_digest": "1" * 64})
        self.refused(Exception, evidence=self.evidence(other))

    def test_forged_evidence_reference_is_refused(self):
        forged = mock.Mock(actor_evidence_ref_id="actor-evidence." + "0" * 32)
        self.refused(Exception, evidence=forged)

    def test_wrong_actor_is_refused(self):
        self.refused(Exception, actor_ref_id="actor.someone-else")

    def test_unprovisioned_floor_refuses_before_consuming_evidence(self):
        self.assertTrue(V2.retire_hermes_owner_floor(self.privacy_db))
        evidence = self.evidence()
        with self.assertRaises(R.ForgetRunnerError) as caught:
            self.forget(evidence=evidence)
        self.assertEqual(caught.exception.code, "REQUIRED_OWNER_FLOOR_UNPROVISIONED")
        self.assert_nothing_started()
        V2.provision_hermes_owner_floor(self.privacy_db, deployment_environment=V2.DEV_SYNTHETIC)
        self.evidence_unconsumed(evidence)

    def test_v1_privacy_database_is_refused(self):
        v1 = self.root / "privacy.v1.db"
        slice15b2a_migration.migrate_privacy(v1, applied_at=stamp_text(3))
        store = privacy.PrivacyGovernanceStore(v1, SECRET, self.actor, now_fn=lambda: self.now)
        with self.assertRaises(R.ForgetRunnerError) as caught:
            self.forget(self.runner(self.owners(store), store))
        self.assertEqual(caught.exception.code, "REQUIRED_OWNER_FLOOR_UNPROVISIONED")

    def test_missing_hermes_adapter_refuses_before_consuming_evidence(self):
        owners = self.owners()
        del owners[HERMES]
        evidence = self.evidence()
        with self.assertRaises(R.ForgetRunnerError) as caught:
            self.forget(self.runner(owners), evidence=evidence)
        self.assertEqual(caught.exception.code, "OWNER_ADAPTER_MISSING")
        self.assert_nothing_started()
        self.evidence_unconsumed(evidence)

    def test_tampered_authorization_is_refused_by_runner_and_owners(self):
        result = self.forget(self.runner(self.owners(**{HERMES: self.hermes(None)})))
        self.assert_incomplete(result, "EXECUTOR_UNAVAILABLE")
        conn = sqlite3.connect(self.privacy_db)                       # a raw-file attacker bypassing the trigger
        try:
            name, sql = conn.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND "
                                     "tbl_name='privacy_erasure_authorization' AND sql LIKE '%BEFORE UPDATE%'"
                                     ).fetchone()
            conn.execute(f'DROP TRIGGER "{name}"')
            conn.execute("UPDATE privacy_erasure_authorization SET authorization_fingerprint=?", ("0" * 64,))
            conn.execute(sql)
            conn.commit()
        finally:
            conn.close()
        self.assert_incomplete(self.runner().resume(), "PRIVACY_ERASURE_NOT_AUTHORIZED")
        self.assertEqual(self.executor.requests, [])

    def test_a_store_with_another_secret_cannot_drive_it(self):
        self.assert_incomplete(self.forget(self.runner(self.owners(**{HERMES: self.hermes(None)}))))
        other = privacy.PrivacyGovernanceStore(self.privacy_db, b"TEST_ONLY a different 32+ byte secret!!",
                                               self.actor)
        self.assert_incomplete(self.runner(self.owners(other), other).resume(), "PRIVACY_ERASURE_NOT_AUTHORIZED")

    def test_forget_while_in_flight_is_refused_before_consuming_evidence(self):
        self.assert_incomplete(self.forget(self.runner(self.owners(**{HERMES: self.hermes(None)}))))
        evidence = self.evidence()
        with self.assertRaises(R.ForgetRunnerError) as caught:
            self.forget(evidence=evidence)
        self.assertEqual(caught.exception.code, "FORGET_IN_FLIGHT")
        self.assertEqual(self.runner().resume().status, R.COMPLETE)
        self.assert_fi_erased()


class OmissionAndDowngradeTests(RunnerCase):
    def test_a_runner_that_omits_hermes_is_refused_by_privacy(self):
        class Omitting(R.FirstInteractionForgetRunner):
            def _policy_owners(self):
                return R.FAMILY_OWNERS

        evidence = self.evidence()
        with self.assertRaisesRegex(privacy.PrivacyError, "required erasure resource owner is missing"):
            self.forget(Omitting(self.privacy, self.owners(), deployment_environment="DEV_SYNTHETIC"),
                        evidence=evidence)
        self.assert_nothing_started()
        self.evidence_unconsumed(evidence)

    def test_old_privacy_code_cannot_forget_without_hermes_and_the_runner_still_can(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        old_module, old = HermesOwnerCase.frozen_store(self, Path(tmp.name))
        action = R.first_interaction_forget_action(self.actor.ACTOR.actor_ref_id)
        with self.assertRaises((old_module.PrivacyError, sqlite3.DatabaseError)):
            old.begin_forget(action=action, actor_evidence_ref_id=self.evidence().actor_evidence_ref_id,
                             intent_ref_id="intent.old", memory_item_id=None, resource_owners=("L04", "L18_V2"),
                             confirmation_event_ref="confirm.old")
        self.assert_nothing_started()
        self.assertEqual(self.forget().status, R.COMPLETE)
        self.assert_fi_erased()

    def test_an_authorization_the_runner_did_not_shape_is_not_executed(self):
        """Another caller's FI authorization with an extra owner: the runner refuses it before any owner erases."""
        self.privacy.begin_forget(action=R.first_interaction_forget_action(self.actor.ACTOR.actor_ref_id),
                                  actor_evidence_ref_id=self.evidence().actor_evidence_ref_id,
                                  intent_ref_id="intent.other", memory_item_id=None,
                                  resource_owners=("L04", "L18_V2", HERMES, "PENDING"),
                                  confirmation_event_ref="confirm.other")
        owners = {n: CountingOwner(o) for n, o in self.owners().items()}
        self.assert_incomplete(self.runner(owners).resume(), "AUTHORIZATION_OWNER_SET_MISMATCH")
        self.assertEqual([o.calls for o in owners.values()], [0, 0, 0])
        self.assertEqual(self.fi_rows()["memory_item"], 1)

    def test_floor_retired_mid_flight_keeps_the_hold_until_reprovisioned(self):
        self.assert_incomplete(self.forget(self.runner(self.owners(**{HERMES: self.hermes(None)}))))
        self.assertTrue(V2.retire_hermes_owner_floor(self.privacy_db))
        self.assert_incomplete(self.runner().resume(), "REQUIRED_OWNER_FLOOR_UNPROVISIONED")
        V2.provision_hermes_owner_floor(self.privacy_db, deployment_environment=V2.DEV_SYNTHETIC)
        self.assertEqual(self.runner().resume().status, R.COMPLETE)
        self.assert_fi_erased()


class PartialExecutionTests(RunnerCase):
    def test_hermes_executor_failures_keep_the_hold(self):
        cases = {
            "EXECUTOR_UNAVAILABLE": self.hermes(None),
            "EXECUTOR_TIMEOUT": self.hermes(self.mock_executor(mode="crash")),
        }
        for code, owner in cases.items():
            with self.subTest(code=code):
                runner = self.runner(self.owners(**{HERMES: owner}))
                result = runner.resume() if self.privacy.in_flight_authorization(FI) else self.forget(runner)
                self.assert_incomplete(result, code)
                self.assertEqual((result.completed_owners, result.pending_owners, result.failed_owner),
                                 (("L04", "L18_V2"), (HERMES,), HERMES))
                self.assertIsNone(self.privacy.owner_result(result.authorization_ref_id,
                                                            self.privacy.in_flight_authorization(FI)[1], HERMES))
        self.assertEqual(self.runner().resume().status, R.COMPLETE)
        self.assert_fi_erased()

    def test_rejected_and_incomplete_receipts_never_complete(self):
        for code, executor in (("EXECUTOR_REJECTED", self.mock_executor(mode="rejected")),
                               ("RECEIPT_INCOMPLETE", self.mock_executor(
                                   mutate=lambda r: r["checks"].__setitem__("sessions_zero", False)))):
            with self.subTest(code=code):
                runner = self.runner(self.owners(**{HERMES: self.hermes(executor)}))
                result = runner.resume() if self.privacy.in_flight_authorization(FI) else self.forget(runner)
                self.assert_incomplete(result, code)
                self.assert_incomplete(runner.resume(), code)        # the same durable receipt never turns COMPLETE
                (self.root / "executor" / f"{result.authorization_ref_id}.receipt.json").unlink()
        self.assertEqual(self.runner().resume().status, R.COMPLETE)

    def test_an_owner_crash_mid_run_resumes_without_rerunning_completed_owners(self):
        l04 = CountingOwner(self.owners()["L04"])
        l18 = CountingOwner(self.owners()["L18_V2"], fail_times=1)
        hermes = CountingOwner(self.hermes())
        runner = self.runner({"L04": l04, "L18_V2": l18, HERMES: hermes})
        result = self.forget(runner)
        self.assert_incomplete(result, "RuntimeError")
        self.assertEqual((result.completed_owners, result.pending_owners, result.failed_owner),
                         (("L04",), ("L18_V2", HERMES), "L18_V2"))
        self.assertEqual((l04.calls, l18.calls, hermes.calls, self.executor.requests), (1, 1, 0, []))
        self.assertEqual(runner.resume().status, R.COMPLETE)
        self.assertEqual((l04.calls, l18.calls, hermes.calls), (1, 2, 1))
        self.assert_fi_erased()

    def test_process_crash_inside_the_executor_then_a_new_runner_resumes(self):
        class Killed(ResolvingExecutor):
            def read_receipt(self, ref):
                raise KeyboardInterrupt                                  # stands in for the process dying

        with self.assertRaises(KeyboardInterrupt):
            self.forget(self.runner(self.owners(**{HERMES: self.hermes(Killed(self.root / "executor",
                                                                                self.privacy))})))
        self.assertTrue(self.privacy.is_held(*FI))
        self.assertEqual(self.prows("SELECT COUNT(*) FROM privacy_completion_receipt"), [(0,)])
        fresh = privacy.PrivacyGovernanceStore(self.privacy_db, SECRET, self.actor, now_fn=lambda: self.now)
        self.assertEqual(self.runner(self.owners(fresh), fresh).resume().status, R.COMPLETE)
        self.assert_fi_erased()

    def test_an_owner_claiming_complete_without_a_privacy_record_is_not_trusted(self):
        result = self.forget(self.runner(self.owners(**{HERMES: CountingOwner(self.hermes(), lie=True)})))
        self.assert_incomplete(result, "OWNER_RESULT_UNVERIFIED")
        self.assertEqual(self.executor.requests, [])

    def test_a_terminal_failed_result_stops_the_run(self):
        self.assert_incomplete(self.forget(self.runner(self.owners(**{HERMES: self.hermes(None)}))))
        ref, nonce = self.privacy.in_flight_authorization(FI)
        self.privacy.record_owner_result(ref, nonce, {"owner": HERMES, "status": "FAILED"})
        result = self.runner().resume()
        self.assert_incomplete(result, "OWNER_RESULT_TERMINAL")
        self.assertEqual(self.executor.requests, [])

    def test_privacy_completion_failure_keeps_the_hold_and_retries(self):
        runner = self.runner()
        with mock.patch.object(self.privacy, "complete", side_effect=sqlite3.OperationalError("TEST_ONLY busy")):
            self.assert_incomplete(self.forget(runner), "PRIVACY_COMPLETION_FAILED:OperationalError")
        self.assertEqual(runner.resume().status, R.COMPLETE)
        self.assertEqual(len(self.executor.requests), 1)                  # Hermes was not erased twice
        self.assert_fi_erased()

    def test_failure_after_the_completion_commit_reports_already_complete(self):
        real = self.privacy.complete

        def commit_then_fail(ref, nonce):
            real(ref, nonce)
            raise sqlite3.OperationalError("TEST_ONLY checkpoint failed after commit")

        with mock.patch.object(self.privacy, "complete", side_effect=commit_then_fail):
            self.assertEqual(self.forget().status, R.ALREADY_COMPLETE)
        self.assert_fi_erased()


class RestoreSuppressionTests(RunnerCase):
    def test_a_restored_pre_forget_copy_is_suppressed_before_serving(self):
        backup_copy = self.root / "cognitive.pre-forget.copy.db"
        shutil.copyfile(self.db, backup_copy)
        self.assertEqual(self.forget().status, R.COMPLETE)
        self.assert_fi_erased()
        shutil.copyfile(backup_copy, self.db)                              # a restore of the old copy
        self.assertEqual(self.fi_rows()["memory_item"], 1)
        verification = privacy.RestoreSuppressionVerifier(
            self.privacy, memory_v2.L04PrivacyErasureOwner(self.db, self.privacy),
            memory_v2.L18V2PrivacyErasureOwner(self.db, self.privacy)).verify_and_apply()
        self.assertEqual((verification.ready_to_serve, verification.suppressed_identities,
                          verification.failure_code), (True, 1, None))
        self.assertEqual(self.fi_rows()["memory_item"], 0)
        self.assertEqual(self.count("SELECT COUNT(*) FROM memory_item WHERE memory_class=?", TEST_CLASS), 1)
        self.assertTrue(self.privacy.is_held(*FI))

    def test_restored_l18_first_interaction_rows_are_suppressed_before_ready(self):
        """Formerly the recorded KNOWN GAP (b9eb32c): the verifier covered only L04, so a restored pre-FORGET copy kept
        its First Interaction L18 rows (plaintext included) while reporting ready_to_serve. Permanent regression."""
        backup_copy = self.root / "cognitive.pre-forget.copy.db"
        shutil.copyfile(self.db, backup_copy)
        self.assertEqual(self.forget().status, R.COMPLETE)
        shutil.copyfile(backup_copy, self.db)
        verification = privacy.RestoreSuppressionVerifier(
            self.privacy, memory_v2.L04PrivacyErasureOwner(self.db, self.privacy),
            memory_v2.L18V2PrivacyErasureOwner(self.db, self.privacy)).verify_and_apply()
        self.assertTrue(verification.ready_to_serve)
        self.assertEqual(set(self.fi_rows().values()), {0})
        self.assertNotIn(FAREWELL, self.db.read_bytes())

    def test_suppression_survives_and_a_second_forget_still_requires_hermes(self):
        self.assertEqual(self.forget().status, R.COMPLETE)
        self.assertTrue(self.privacy.suppression_matches(FI))
        with self.assertRaisesRegex(privacy.PrivacyError, "required erasure resource owner is missing"):
            self.privacy.begin_forget(action=R.first_interaction_forget_action(self.actor.ACTOR.actor_ref_id),
                                      actor_evidence_ref_id=self.evidence().actor_evidence_ref_id,
                                      intent_ref_id="intent.again", memory_item_id=None,
                                      resource_owners=("L04", "L18_V2"), confirmation_event_ref="confirm.again")


class PrivacyReadHelperTests(RunnerCase):
    def test_helpers_are_read_only_and_exact(self):
        self.assertEqual(self.privacy.required_owners(*FI[:2]), frozenset({HERMES}))
        self.assertEqual(self.privacy.required_owners(TEST_CLASS, "lilith.test.codename"), frozenset())
        self.assertIsNone(self.privacy.in_flight_authorization(FI))
        self.assert_incomplete(self.forget(self.runner(self.owners(**{HERMES: self.hermes(None)}))))
        before = self.privacy_db.read_bytes()
        ref, nonce = self.privacy.in_flight_authorization(FI)
        self.assertIsNone(self.privacy.in_flight_authorization((FI[0], FI[1], "another-key")))
        self.assertEqual(self.privacy_db.read_bytes(), before)
        self.assertEqual(self.prows("SELECT authorization_ref_id,execution_nonce FROM privacy_erasure_authorization"),
                         [(ref, nonce)])


if __name__ == "__main__":
    unittest.main()
