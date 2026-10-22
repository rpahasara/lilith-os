"""FM-02 First Interaction family integrated on main with the #240 FORGET and #241 RESERVED-evidence corrections.

Synthetic temporary databases and evidence only. The single-component behaviour is tested elsewhere
(test_fm02_l04_first_interaction, test_admission_v2_family_basis, test_privacy_forget_lineage,
test_a17_reserved_abandon); this file covers their interaction for the new family plus the governed release pins.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest import mock

import synthetic_b1b3b as T  # puts the core-api package on sys.path
import synthetic_first_memory as SF
import synthetic_fm02_l04 as FX
from lilith_authority_signer import synthetic_evidence_ledger as EL
from lilith_memory import canonical_contracts as C
from lilith_memory import canonical_store
from lilith_memory import learning_v2
from lilith_memory import memory_action_v2 as MA
from lilith_memory import memory_v2
from lilith_owner_memory import admission_v2 as V2
from lilith_owner_memory import first_memory_profile as FM
from lilith_owner_memory import l04_v2_adapter as AD

REPO = Path(__file__).resolve().parents[3]
GOVERNED_CANONICAL_CONTRACTS_SHA256 = "f93d26d8a7e01d78d25f1f1d9540577cf2a55dfd4d52c4b64c87bef93ad887e0"


class Crash(RuntimeError):
    """A process crash inside the transaction, modelled exactly as the accepted A1-A7 tests do."""


class LateHold(T.PrivacyState):
    """No hold for the adapter's check, L04 prevalidation and L04's pre-write check; one appears just before commit."""

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


class IntegrationCase(unittest.TestCase):
    """A schema-v2 L04 with the real Privacy Governance store as its hold resolver."""

    def setUp(self):
        harness = FX.FirstInteractionHarness()
        self.privacy = harness.privacy_store()
        harness.privacy = self.privacy
        harness.learning.privacy_hold_resolver = self.privacy
        self.flow = FX.FirstInteractionFlow(harness)
        self.addCleanup(harness.close)
        self.proofs = {}

    def fi_attempt(self, *, nonce="int.fi", value=None, **store_overrides):
        """A genuine owner proof and signed evidence for one First Interaction proposal; the adapter is rebuilt with
        the given L04 store overrides."""
        _action, proposal, proof, evidence = self.flow.create_fi(value, nonce)
        self.proofs[proposal] = proof
        self.flow.adapter = self.flow.make_adapter(store_overrides=store_overrides)
        return proposal, evidence

    def admit(self, proposal, evidence):
        return self.flow.adapter.admit(self.flow.request(proposal, self.proofs[proposal], evidence))

    def use_state(self, evidence):
        return self.flow.ledger.lookup(evidence["evidenceId"])["state"]

    def forget(self):
        l04 = self.flow.l04
        active = l04.store().get_active(*MA.FIRST_INTERACTION_IDENTITY)
        action = MA.action_from_fields(
            schema_version=1, actor_ref_id=l04.actor.ACTOR.actor_ref_id, operation=C.FORGET,
            memory_class=FX.FI_CLASS, subject_namespace=FX.FI_NAMESPACE, subject_key=FX.FI_KEY, value_schema=None,
            payload_digest="0" * 64, expected_active_revision_id=None, restore_revision_id=None, purpose=FX.FI_PURPOSE)
        ev = l04.actor.issue(action=action, request_digest=T.digest("request:int.forget"), nonce="int.forget")
        _request, auth, _suppression = self.privacy.begin_forget(
            action=action, actor_evidence_ref_id=ev.actor_evidence_ref_id, intent_ref_id="intent.int.forget",
            memory_item_id=None if active is None else active["memory_item_id"],
            resource_owners=("L04", "L18_V2"), confirmation_event_ref="confirm.int.forget")
        l04_result = memory_v2.L04PrivacyErasureOwner(l04.db, self.privacy).erase_authorized(
            auth.authorization_ref_id, auth.execution_nonce)
        l18_result = memory_v2.L18V2PrivacyErasureOwner(l04.db, self.privacy).erase_authorized(
            auth.authorization_ref_id, auth.execution_nonce)
        return l04_result, l18_result, self.privacy.complete(auth.authorization_ref_id, auth.execution_nonce)

    def assert_family_erased(self):
        conn = sqlite3.connect(self.flow.l04.db)
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                      for t in ("memory_item", "memory_admission", *sorted(learning_v2.FIRST_INTERACTION_TABLES))}
            refs = conn.execute("SELECT COUNT(*) FROM learning_proposal_ref WHERE proposal_family=?",
                                (learning_v2.FIRST_INTERACTION_PROPOSAL_FAMILY,)).fetchone()[0]
            fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        finally:
            conn.close()
        self.assertEqual(set(counts.values()), {0}, counts)
        self.assertEqual((refs, fk), (0, []))
        raw = self.flow.l04.db.read_bytes()
        for snippet in (b"moring", b"good night", b"TEST_ONLY hi LILITH"):
            self.assertNotIn(snippet, raw)
        self.assertTrue(self.privacy.is_held(*MA.FIRST_INTERACTION_IDENTITY))       # restore suppression


class PrivacyIntegrationTests(IntegrationCase):
    def test_rejected_first_interaction_admission_then_forget(self):
        """#240 for the new family: a REJECTED admission row (no memory item) no longer blocks erasure."""
        proposal, evidence = self.fi_attempt(capability_provider=lambda c: c == T.L04_CAPABILITY)
        result = self.admit(proposal, evidence)
        self.assertEqual((result.status, result.detail), (V2.NOT_ACCEPTED, "REJECTED:CAPABILITY_INACTIVE"))
        self.assertEqual(self.use_state(evidence), EL.ABANDONED)
        self.assertIsNone(self.flow.l04.store().get_active(*MA.FIRST_INTERACTION_IDENTITY))
        l04, l18, receipt = self.forget()
        self.assertEqual((l04["status"], l04["deleted"], l18["status"], receipt.verification_status),
                         ("COMPLETE", 0, "COMPLETE", "COMPLETE"))
        self.assert_family_erased()

    def test_accepted_first_interaction_then_forget_and_restore_suppression(self):
        proposal, evidence = self.fi_attempt()
        self.assertEqual(self.admit(proposal, evidence).status, AD.L04_ADMITTED)
        self.assertEqual(self.use_state(evidence), EL.CONSUMED)
        self.assertEqual(self.flow.read_fi().status, V2.ACCEPTED_MEMORY)
        _l04, _l18, receipt = self.forget()
        self.assertEqual(receipt.verification_status, "COMPLETE")
        self.assert_family_erased()
        replacement, _encoded = self.flow.l04.fi_action(SF.value(quotations=[SF.quotation(FM.OPENING, 0),
                                                                              SF.quotation(FM.CLOSING, 3)]))
        with self.assertRaisesRegex(AD.Reject, "PRIVACY_HOLD_ACTIVE"):
            self.flow.adapter._privacy_clear(replacement)                      # no replacement "first memory"


class ReservedEvidenceIntegrationTests(IntegrationCase):
    """#241 for the new family: deterministic refusal -> ABANDONED only on proven non-admission."""

    def test_deterministic_refusal_in_the_transaction_abandons(self):
        proposal, evidence = self.fi_attempt(
            nonce="int.reject", fault_hook=raise_at_commit(AD.Reject("ADMISSION_BINDING_MISMATCH")))
        before = self.flow.l04.counts()
        result = self.admit(proposal, evidence)
        self.assertEqual((result.status, result.reason), (V2.NOT_ACCEPTED, "ADMISSION_BINDING_MISMATCH"))
        self.assertEqual(self.flow.l04.counts(), before)
        self.assertEqual(self.use_state(evidence), EL.ABANDONED)

    def test_a_pre_commit_hold_abandons(self):
        proposal, evidence = self.fi_attempt(nonce="int.hold", privacy_hold_resolver=LateHold())
        with self.assertRaisesRegex(canonical_store.CanonicalStoreError, "PRIVACY_HOLD_ACTIVE"):
            self.admit(proposal, evidence)
        self.assertEqual(self.use_state(evidence), EL.ABANDONED)
        self.assertIsNone(self.flow.l04.store().get_active(*MA.FIRST_INTERACTION_IDENTITY))

    def test_a_crash_keeps_reserved(self):
        proposal, evidence = self.fi_attempt(nonce="int.crash", fault_hook=raise_at_commit(Crash("before_commit")))
        with self.assertRaises(Crash):
            self.admit(proposal, evidence)
        self.assertEqual(self.use_state(evidence), EL.RESERVED)
        reconciled = self.flow.adapter.reconcile(proposal)
        self.assertEqual((reconciled.status, reconciled.reason), (V2.NOT_ACCEPTED, "ADMISSION_LINK_MISSING"))
        self.assertEqual(self.use_state(evidence), EL.RESERVED)

    def test_an_unreadable_view_keeps_reserved(self):
        proposal, evidence = self.fi_attempt(
            nonce="int.unreadable", fault_hook=raise_at_commit(AD.Reject("ADMISSION_BINDING_MISMATCH")))
        with mock.patch.object(AD, "read_l04_admission_view", side_effect=OSError("L04 unavailable")):
            self.admit(proposal, evidence)
        self.assertEqual(self.use_state(evidence), EL.RESERVED)


class GovernedPinTests(unittest.TestCase):
    """Every governed shared module of the signer and broker releases still matches its pin."""

    @staticmethod
    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(Path(path).parent))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
        return module

    def test_signer_and_broker_governed_pins_validate(self):
        canonical = (REPO / "services/core-api/lilith_memory/canonical_contracts.py").read_bytes()
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), GOVERNED_CANONICAL_CONTRACTS_SHA256)
        for label, path in (("signer", REPO / "services/authority-dev/release_file_set.py"),
                            ("broker", REPO / "scripts/memory_broker_os_release.py")):
            module = self.load(f"fm02_pin_{label}", path)
            mismatched = [p for p, h in module.SHARED_HASHES.items()
                          if hashlib.sha256((REPO / p).read_bytes()).hexdigest() != h]
            with self.subTest(release=label):
                self.assertEqual(mismatched, [])
                self.assertNotIn("services/core-api/lilith_memory/memory_action_v2.py", module.SHARED_HASHES)


if __name__ == "__main__":
    unittest.main()
