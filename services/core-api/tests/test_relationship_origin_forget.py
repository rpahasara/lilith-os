"""Relationship-origin FORGET through the governed runner and the durable hold-first intent (TEST_ONLY, synthetic).

The F9-C runner fixtures unchanged (real L04, L18_V2 and Privacy; the mock Hermes executor of the runner tests): the
database carries the admitted First Interaction episode and the codename memory, is moved to owner-ledger schema v3,
and then holds one admitted relationship-origin statement. The origin FORGET must be identity-specific, never enlist
the Hermes owner where the Privacy floor does not provision it, refuse every ambiguous or insufficient authority before
anything is held, stay durable-before-erase, and leave the First Interaction FORGET exactly as it was.
"""

from __future__ import annotations

import os
import unittest

from test_privacy_forget_intent import HOLDER, FakeGateway
from test_privacy_forget_runner import DURABLE_FOR_TEST, FI, HERMES, CountingOwner, RunnerCase
from test_relationship_origin_l04 import STATEMENT, OriginCase

from lilith_memory import canonical_store
from lilith_memory import memory_action_v2 as MA
from lilith_memory import privacy_forget_intent as I
from lilith_memory import privacy_forget_runner as R

RO = MA.RELATIONSHIP_ORIGIN_IDENTITY


class OriginForgetCase(RunnerCase):
    migrate_ro = OriginCase.migrate_ro
    enable_ro = OriginCase.enable_ro
    ro_store = OriginCase.ro_store
    ro_proposal = OriginCase.ro_proposal

    def setUp(self) -> None:
        super().setUp()                                     # codename + First Interaction episode, Privacy v2 + floor
        self.migrate_ro(tag="v2-to-v3")
        self.enable_ro()
        _action, ref = self.ro_proposal()
        self.assertEqual(self.ro_store().apply(ref.proposal_ref_id).outcome, canonical_store.ACCEPTED)

    def origin_runner(self, owners=None, barrier=DURABLE_FOR_TEST):
        return R.FirstInteractionForgetRunner(self.privacy, owners or self.owners(),
                                              deployment_environment="DEV_SYNTHETIC", durability_barrier=barrier,
                                              profile=R.RELATIONSHIP_ORIGIN_FORGET)

    def origin_evidence(self):
        self._n += 1
        action = R.forget_action(R.RELATIONSHIP_ORIGIN_FORGET, self.actor.ACTOR.actor_ref_id)
        return self.actor.issue(action=action, request_digest=f"{self._n:064x}", nonce=f"forget.origin.{self._n}")

    def forget_origin(self, runner=None, evidence=None):
        evidence = evidence or self.origin_evidence()
        return (runner or self.origin_runner()).forget(
            actor_ref_id=self.actor.ACTOR.actor_ref_id, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            intent_ref_id=f"intent.origin.{self._n}", confirmation_event_ref=f"confirm.origin.{self._n}")

    def origin_rows(self) -> int:
        tables = ("learning_ro_intent_v1", "learning_ro_candidate_v1", "learning_ro_proposal_v1")
        return sum(self.count(f"SELECT COUNT(*) FROM {t}") for t in tables) + self.count(
            "SELECT COUNT(*) FROM memory_item WHERE memory_class=?", RO[0])


class OriginForgetTests(OriginForgetCase):
    def test_the_profiles_are_closed_and_distinct(self):
        self.assertEqual(R.PROFILES, (R.FIRST_INTERACTION_FORGET, R.RELATIONSHIP_ORIGIN_FORGET))
        self.assertEqual((R.FIRST_INTERACTION_FORGET.identity, R.FIRST_INTERACTION_FORGET.family_owners,
                          R.FIRST_INTERACTION_FORGET.allowed_floors), (FI, R.FAMILY_OWNERS, (R.REQUIRED_FLOOR,)))
        self.assertEqual((R.RELATIONSHIP_ORIGIN_FORGET.identity, R.RELATIONSHIP_ORIGIN_FORGET.family_owners,
                          R.RELATIONSHIP_ORIGIN_FORGET.allowed_floors),
                         (RO, ("L04", "L18_V2"), (frozenset(), frozenset({HERMES}))))
        self.assertEqual(I.INTENT_NAMES, {"FIRST_INTERACTION": "first-interaction.intent",
                                          "RELATIONSHIP_ORIGIN": "relationship-origin.intent"})
        forged = R.ForgetProfileV1("RELATIONSHIP_ORIGIN", FI, MA.OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION,
                                   ("L04", "L18_V2"), (frozenset(),))
        with self.assertRaises(R.ForgetRunnerError) as caught:              # never a caller-built identity
            self.origin_runner().__class__(self.privacy, self.owners(), deployment_environment="DEV_SYNTHETIC",
                                           durability_barrier=DURABLE_FOR_TEST, profile=forged)
        self.assertEqual(caught.exception.code, "FORGET_PROFILE_UNKNOWN")

    def test_origin_forget_erases_only_the_origin_and_keeps_codename_and_first_interaction(self):
        fi_before = self.fi_rows()
        self.assertGreater(self.origin_rows(), 0)
        result = self.forget_origin()
        self.assertEqual(result.status, R.COMPLETE, result)
        self.assertEqual(result.completed_owners, ("L04", "L18_V2"))         # no Hermes floor for this scope
        self.assertEqual(self.origin_rows(), 0)
        self.assertNotIn(STATEMENT.encode("ascii"), self.db.read_bytes())
        self.assertEqual(self.fi_rows(), fi_before)                          # the First Interaction rows untouched
        self.assertIn(b"SYNTH-ALPHA", self.db.read_bytes())                  # the codename memory untouched
        self.assertTrue(self.privacy.is_held(*RO))                           # suppressed for good
        self.assertFalse(self.privacy.is_held(*FI))
        self.assertEqual(self.executor.requests, [])                         # Hermes not enlisted unprovisioned
        self.assertEqual(self.origin_runner().resume().status, R.ALREADY_COMPLETE)
        self.assertEqual(self.runner().resume().status, R.NOT_STARTED)      # the FI runner never sees RO

    def test_the_first_interaction_forget_is_unchanged_and_both_suppressions_hold(self):
        self.assertEqual(self.forget().status, R.COMPLETE)                  # FI first (the historical F9c2 shape)
        self.assert_fi_erased()
        self.assertEqual(self.forget_origin().status, R.COMPLETE)
        self.assertTrue(self.privacy.is_held(*FI) and self.privacy.is_held(*RO))
        self.assertEqual(self.prows("SELECT COUNT(*) FROM privacy_completion_receipt"), [(2,)])

    def test_insufficient_or_ambiguous_authority_holds_nothing(self):
        owners = self.owners()
        del owners["L18_V2"]
        with self.assertRaises(R.ForgetRunnerError) as caught:              # every owner adapter before any hold
            self.forget_origin(self.origin_runner(owners))
        self.assertEqual(caught.exception.code, "OWNER_ADAPTER_MISSING")
        fi_evidence = self.evidence()                                       # evidence for the OTHER identity
        with self.assertRaises(Exception):
            self.forget_origin(evidence=fi_evidence)
        with self.assertRaises(Exception):                                  # forged reference
            self.forget_origin(evidence=type("E", (), {"actor_evidence_ref_id": "aev.forged"})())
        self.assertEqual(self.prows("SELECT COUNT(*) FROM privacy_hold"), [(0,)])
        self.assertEqual(self.prows("SELECT COUNT(*) FROM privacy_erasure_authorization"), [(0,)])
        self.assertFalse(self.privacy.is_held(*RO))
        self.assertGreater(self.origin_rows(), 0)

    def test_durable_before_erase_and_replay(self):
        result = self.forget_origin(self.origin_runner(barrier=lambda: "CHECKPOINT_PENDING"))
        self.assertEqual((result.status, result.failure_code), (R.INCOMPLETE_HOLD_ACTIVE, "CHECKPOINT_PENDING"))
        self.assertGreater(self.origin_rows(), 0)                            # nothing erased before durability
        self.assertTrue(self.privacy.is_held(*RO))                           # but the hold is already ACTIVE
        self.assertIsNotNone(self.privacy.in_flight_authorization(RO))
        owners = {n: CountingOwner(o) for n, o in self.owners().items()}
        self.assertEqual(self.origin_runner(owners).resume().status, R.COMPLETE)
        self.assertEqual(self.origin_rows(), 0)
        before = self.privacy_db.read_bytes()
        self.assertEqual(self.origin_runner(owners).resume().status, R.ALREADY_COMPLETE)
        self.assertEqual([o.calls for o in owners.values()], [1, 1, 0])     # L04, L18_V2; Hermes unprovisioned
        self.assertEqual(self.privacy_db.read_bytes(), before)
        with self.assertRaises(Exception):                                  # no second FORGET of the same identity
            self.forget_origin()


@unittest.skipUnless(hasattr(os, "geteuid") and os.geteuid() == 0, "ownership changes need root")
class OriginIntentTests(OriginForgetCase):
    def setUp(self) -> None:
        super().setUp()
        self.intent_dir = self.root / "intent"
        self.intent_dir.mkdir()
        os.chmod(self.intent_dir, 0o1770)
        self.fi_intents = I.ForgetIntentStore(self.intent_dir, holder_uid=HOLDER)
        self.ro_intents = I.ForgetIntentStore(self.intent_dir, holder_uid=HOLDER,
                                              profile=R.RELATIONSHIP_ORIGIN_FORGET)

    def hold_first(self, intents, runner):
        return I.HoldFirstForgetRunner(runner, intents, FakeGateway(), hold_timeout_seconds=1.0, poll_seconds=0.5,
                                       sleep=lambda s: os.chown(intents.path, HOLDER, -1), monotonic=lambda: 0.0)

    def test_hold_first_origin_forget_with_its_own_labelled_intent(self):
        evidence = self.origin_evidence()
        result = self.hold_first(self.ro_intents, self.origin_runner()).forget(
            actor_ref_id=self.actor.ACTOR.actor_ref_id, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            intent_ref_id="intent.origin.held", confirmation_event_ref="confirm.origin.held")
        self.assertEqual(result.status, R.COMPLETE, result)
        self.assertEqual(self.ro_intents.path.name, "relationship-origin.intent")
        self.assertEqual(self.ro_intents.read()["identity"], "RELATIONSHIP_ORIGIN")
        self.assertEqual(self.origin_rows(), 0)

    def test_identities_never_share_an_intent_or_a_hold(self):
        with self.assertRaises(I.ForgetIntentError) as caught:              # runner and intent must agree
            I.HoldFirstForgetRunner(self.runner(), self.ro_intents, FakeGateway())
        self.assertEqual(caught.exception.code, "FORGET_PROFILE_MISMATCH")
        self.ro_intents.record(intent_ref_id="intent.origin.1", actor_ref_id=self.actor.ACTOR.actor_ref_id)
        with self.assertRaises(I.ForgetIntentError) as caught:              # one FORGET at a time
            self.fi_intents.record(intent_ref_id="intent.fi.1", actor_ref_id=self.actor.ACTOR.actor_ref_id)
        self.assertEqual(caught.exception.code, "FORGET_INTENT_PENDING_OTHER_IDENTITY")
        os.link(self.ro_intents.path, self.intent_dir / "first-interaction.intent")   # a mislabelled FI intent
        with self.assertRaises(I.ForgetIntentError) as caught:
            self.fi_intents.read()
        self.assertEqual(caught.exception.code, "FORGET_INTENT_MALFORMED")
        self.assertEqual(self.prows("SELECT COUNT(*) FROM privacy_hold"), [(0,)])

    def test_a_hold_that_is_not_established_erases_nothing(self):
        runner = I.HoldFirstForgetRunner(self.origin_runner(), self.ro_intents, FakeGateway(stopped=False),
                                         hold_timeout_seconds=1.0, poll_seconds=0.5, sleep=lambda s: None,
                                         monotonic=iter([0.0, 2.0]).__next__)
        evidence = self.origin_evidence()
        result = runner.forget(actor_ref_id=self.actor.ACTOR.actor_ref_id,
                               actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                               intent_ref_id="intent.origin.nohold", confirmation_event_ref="confirm.origin.nohold")
        self.assertEqual((result.status, result.failure_code), (I.INTENT_RECORDED_HOLD_PENDING, "HOLD_NOT_ESTABLISHED"))
        self.assertEqual(self.prows("SELECT COUNT(*) FROM privacy_hold"), [(0,)])
        self.assertGreater(self.origin_rows(), 0)


if __name__ == "__main__":
    unittest.main()
