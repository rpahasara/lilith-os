"""A1-A7 evidence use after a deterministic refusal inside the L04 transaction (owner-approved, local only).

Before: a deterministic refusal raised inside L04 apply (a Reject from the in-transaction link check, or L04's own
pre-commit CanonicalStoreError, e.g. a Privacy hold appearing just before commit) rolled L04 back but left the
evidence use RESERVED: "admission may be in flight", although nothing was committed, and `reconcile` cannot resolve it.

After: for exactly those two exception types, the adapter re-reads L04 (read-only, the exact proposal) and moves the
use RESERVED -> ABANDONED (the ledger's existing transition) only when no accepted admission exists. Ambiguity keeps
RESERVED: an unreadable view, an accepted admission, or any other exception (the accepted A1-A7 crash semantics).
Both states stay terminal for reuse; nothing becomes reusable. Synthetic temporary databases only.
"""

from __future__ import annotations

import unittest
from unittest import mock

import synthetic_b1b3b as T
from lilith_authority_signer import synthetic_evidence_ledger as EL
from lilith_memory import canonical_store
from lilith_owner_memory import admission_v2 as V2
from lilith_owner_memory import l04_v2_adapter as AD


class Crash(RuntimeError):
    """Models a process crash inside the transaction, exactly as the accepted A1-A7 tests do."""


class LateHold(T.PrivacyState):
    """No hold for the adapter's check, L04 prevalidation and L04's pre-write check; a hold appears just before the
    commit (a race with a concurrent Privacy FORGET)."""

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def is_held(self, *identity):
        self.calls += 1
        return self.calls >= 4


def raise_at_commit(exc):
    def hook(stage):
        if stage == "before_commit":
            raise exc
    return hook


class ReservedAbandonCase(unittest.TestCase):
    durable = True

    def setUp(self):
        self.flow = T.Flow(durable=self.durable)
        self.addCleanup(self.flow.l04.close)
        self.action, self.proposal, self.proof, self.evidence = self.flow.create("SYNTH-RESERVED", "a17.reserved")
        self.before = self.flow.l04.counts()

    def admit_with(self, **store_overrides):
        self.flow.adapter = self.flow.make_adapter(store_overrides=store_overrides)
        return self.flow.adapter.admit(self.flow.request(self.proposal, self.proof, self.evidence))

    def state(self):
        return self.flow.ledger.lookup(self.evidence["evidenceId"])["state"]

    def assert_nothing_committed(self):
        self.assertEqual(self.flow.l04.counts(), self.before)
        self.assertIsNone(AD.read_l04_admission_view(self.flow.l04.db, self.proposal, self.action))
        self.assertIsNone(self.flow.links.get(self.proposal))

    def assert_terminal_for_reuse(self, expected_detail):
        retry = self.flow.adapter.admit(self.flow.request(self.proposal, self.proof, self.evidence))
        self.assertEqual((retry.status, retry.reason, retry.detail),
                         (V2.NOT_ACCEPTED, "EVIDENCE_ALREADY_CONSUMED", expected_detail))
        self.assert_nothing_committed()


class DeterministicRefusalTests(ReservedAbandonCase):
    def test_a_reject_inside_the_transaction_abandons(self):
        result = self.admit_with(fault_hook=raise_at_commit(AD.Reject("ADMISSION_BINDING_MISMATCH")))
        self.assertEqual((result.status, result.reason), (V2.NOT_ACCEPTED, "ADMISSION_BINDING_MISMATCH"))
        self.assert_nothing_committed()
        self.assertEqual(self.state(), EL.ABANDONED)
        self.assert_terminal_for_reuse("EVIDENCE_ALREADY_ABANDONED")

    def test_a_pre_commit_privacy_hold_abandons_and_still_raises(self):
        hold = LateHold()
        with self.assertRaisesRegex(canonical_store.CanonicalStoreError, "PRIVACY_HOLD_ACTIVE"):
            self.admit_with(privacy_hold_resolver=hold)          # unchanged: the L04 exception still propagates
        self.assert_nothing_committed()
        self.assertEqual(self.state(), EL.ABANDONED)

    def test_the_existing_pre_write_refusal_path_is_unchanged(self):
        result = self.admit_with(capability_provider=lambda capability: False)
        self.assertEqual((result.status, result.reason, result.detail),
                         (V2.NOT_ACCEPTED, "L04_NOT_ADMITTED", "REJECTED:CAPABILITY_INACTIVE"))
        self.assertEqual(self.state(), EL.ABANDONED)

    def test_reconcile_still_refuses_an_uncommitted_proposal(self):
        self.admit_with(fault_hook=raise_at_commit(AD.Reject("ADMISSION_BINDING_MISMATCH")))
        reconciled = self.flow.adapter.reconcile(self.proposal)
        self.assertEqual((reconciled.status, reconciled.reason), (V2.NOT_ACCEPTED, "ADMISSION_LINK_MISSING"))
        self.assertEqual(self.state(), EL.ABANDONED)


class AmbiguityKeepsReservedTests(ReservedAbandonCase):
    """Negative controls: anything short of a confirmed absence of an accepted admission keeps RESERVED."""

    def test_any_other_exception_keeps_the_accepted_crash_semantics(self):
        with self.assertRaises(Crash):
            self.admit_with(fault_hook=raise_at_commit(Crash("before_commit")))
        self.assert_nothing_committed()
        self.assertEqual(self.state(), EL.RESERVED)
        self.assert_terminal_for_reuse("EVIDENCE_ALREADY_RESERVED")

    def test_an_unreadable_l04_view_keeps_reserved(self):
        with mock.patch.object(AD, "read_l04_admission_view", side_effect=OSError("L04 unavailable")):
            result = self.admit_with(fault_hook=raise_at_commit(AD.Reject("ADMISSION_BINDING_MISMATCH")))
        self.assertEqual(result.reason, "ADMISSION_BINDING_MISMATCH")
        self.assertEqual(self.state(), EL.RESERVED)

    def test_a_view_showing_an_accepted_admission_keeps_reserved(self):
        accepted = {"admissionOutcome": canonical_store.ACCEPTED}
        with mock.patch.object(AD, "read_l04_admission_view", return_value=accepted):
            self.admit_with(fault_hook=raise_at_commit(AD.Reject("ADMISSION_BINDING_MISMATCH")))
        self.assertEqual(self.state(), EL.RESERVED)

    def test_the_check_reads_the_exact_proposal(self):
        with mock.patch.object(AD, "read_l04_admission_view", wraps=AD.read_l04_admission_view) as view:
            self.admit_with(fault_hook=raise_at_commit(AD.Reject("ADMISSION_BINDING_MISMATCH")))
        self.assertEqual([c.args[1] for c in view.call_args_list], [self.proposal])
        self.assertEqual(view.call_args.args[2], self.action)


class InMemoryLinkStoreTests(DeterministicRefusalTests):
    """The same behaviour with the non-durable link store (no in-transaction callback)."""

    durable = False


if __name__ == "__main__":
    unittest.main()
