"""Relationship-origin FORGET intent through the REAL (patched) root executor: hold, gateway stop, identity-bound
release (TEST_ONLY, synthetic). Uses the F9-C executor matrix fixtures unchanged (fake systemd/journald host, the
executor in a fresh interpreter against the pinned Core API copy). Run as root with the same environment as the matrix.
"""

from __future__ import annotations

import os
import stat
import unittest

from test_f9c_executor_matrix import ExecutorCase, HostGateway  # noqa: E402  (sets up the import paths)

from lilith_memory import canonical_store  # noqa: E402
from lilith_memory import memory_action_v2 as MA  # noqa: E402
from lilith_memory import privacy_forget_intent as I  # noqa: E402
from lilith_memory import privacy_forget_runner as R  # noqa: E402
from test_relationship_origin_forget import OriginForgetCase  # noqa: E402

RO = MA.RELATIONSHIP_ORIGIN_IDENTITY


class OriginHoldTests(ExecutorCase):
    HELD_GID = 4243
    migrate_ro = OriginForgetCase.migrate_ro
    enable_ro = OriginForgetCase.enable_ro
    ro_store = OriginForgetCase.ro_store
    ro_proposal = OriginForgetCase.ro_proposal
    origin_evidence = OriginForgetCase.origin_evidence
    origin_rows = OriginForgetCase.origin_rows

    def setUp(self) -> None:
        super().setUp()
        self.write_config(receiptGid=self.HELD_GID)
        self.migrate_ro(tag="v2-to-v3")
        self.enable_ro()
        _action, ref = self.ro_proposal()
        self.assertEqual(self.ro_store().apply(ref.proposal_ref_id).outcome, canonical_store.ACCEPTED)
        self.intents = I.ForgetIntentStore(self.intent_dir, holder_uid=0, profile=R.RELATIONSHIP_ORIGIN_FORGET)
        self.intent = self.intent_dir / "relationship-origin.intent"

    def held(self):
        st = os.lstat(self.intent)
        return (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) == (0, self.HELD_GID, 0o640)

    def hold_tick(self, seconds):
        self.assertIsNone(self.privacy.in_flight_authorization(RO))        # nothing authorized before the hold
        self.assertEqual(self.run_executor("hold"), 0, self.run_log[-1])
        self.ticks += seconds

    def origin_hold_first(self):
        runner = R.FirstInteractionForgetRunner(self.privacy, self.owners_real(), deployment_environment="DEV_SYNTHETIC",
                                                durability_barrier=lambda: None, profile=R.RELATIONSHIP_ORIGIN_FORGET)
        return I.HoldFirstForgetRunner(runner, self.intents, HostGateway(self), hold_timeout_seconds=10,
                                       sleep=self.hold_tick, monotonic=lambda: self.ticks)

    def test_origin_intent_is_held_erased_canonically_and_released_by_identity(self):
        evidence = self.origin_evidence()
        result = self.origin_hold_first().forget(
            actor_ref_id=self.actor.ACTOR.actor_ref_id, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            intent_ref_id="intent.origin.exec", confirmation_event_ref="confirm.origin.exec")
        self.assertEqual(result.status, R.COMPLETE, (result, self.run_log))
        self.assertEqual(result.completed_owners, ("L04", "L18_V2"))
        self.assertTrue(self.held())
        self.assertFalse(self.host()["gatewayActive"])
        self.assertEqual(self.origin_rows(), 0)
        self.assert_untouched()                       # no Hermes floor for this scope: the Hermes store is untouched
        self.assertEqual(self.run_executor("reconcile"), 0)
        self.assertFalse(self.intent.exists())
        self.assertTrue(any("INTENT_RELEASED" in log for log in self.run_log))

    def test_a_mislabelled_or_unknown_intent_is_never_held_or_released(self):
        self.intent.write_text('{"v":1,"identity":"FIRST_INTERACTION","intentRefId":"i.1","actorRefId":"a.1",'
                               '"recordedAt":"2026-10-26T00:00:00Z"}')
        other = self.intent_dir / "other.intent"
        other.write_text("{}")
        self.assertEqual(self.run_executor("hold"), 0)
        self.assertIn("INTENT_REJECTED", self.run_log[-1])
        self.assertFalse(self.held())
        self.assertFalse(self.host()["gatewayActive"])                     # the hold still stops the gateway
        self.assertEqual(self.run_executor("reconcile"), 0)
        self.assertTrue(self.intent.exists() and other.exists())           # still blocking
        self.assertEqual(self.run_executor("cancel-confirmed"), 0)         # owner-approved cancel: known names only
        self.assertFalse(self.intent.exists())
        self.assertTrue(other.exists())

    def test_an_origin_forget_in_flight_cannot_be_cancelled(self):
        runner = R.FirstInteractionForgetRunner(self.privacy, self.owners_real(), deployment_environment="DEV_SYNTHETIC",
                                                durability_barrier=lambda: "CHECKPOINT_PENDING",
                                                profile=R.RELATIONSHIP_ORIGIN_FORGET)
        hf = I.HoldFirstForgetRunner(runner, self.intents, HostGateway(self), hold_timeout_seconds=10,
                                     sleep=self.hold_tick, monotonic=lambda: self.ticks)
        evidence = self.origin_evidence()
        result = hf.forget(actor_ref_id=self.actor.ACTOR.actor_ref_id,
                           actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                           intent_ref_id="intent.origin.stall", confirmation_event_ref="confirm.origin.stall")
        self.assertEqual(result.status, R.INCOMPLETE_HOLD_ACTIVE)
        self.assertEqual(self.run_executor("cancel-confirmed"), 2)
        self.assertIn("CANCEL_REFUSED_FORGET_IN_FLIGHT", self.run_log[-1])
        self.assertEqual(self.run_executor("reconcile"), 0)
        self.assertTrue(self.intent.exists())
        self.assertGreater(self.origin_rows(), 0)                          # durable-before-erase: nothing erased


if __name__ == "__main__":
    unittest.main()
