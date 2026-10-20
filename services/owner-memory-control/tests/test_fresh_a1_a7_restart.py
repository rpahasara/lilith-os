"""Fresh A1-A7 crash/replay rehearsal using reconstructed in-process components (TEST-ONLY, local).

Design inputs: custody-isolation design "Relationship to Stage III A2" (A1-A7 under broker-signed evidence), the L04 V2
adapter design "Stage III implications" (S1-S6), and the B1b-3d note that A6/A7 crash testing belongs to the fresh
rehearsal. This is NOT a retry of the legacy Stage III A2.

The existing B1b-3b crash tests (`test_b1b3b_hardening.PostCommitCrashTests`) crash inside one process with in-memory
components. Here a simulated crash is followed by fresh components over the same files, in the same OS process.
This tests persisted-state reconstruction, not termination/restart of the OS process or power-loss durability. The flow runs in durable mode (owner decision "Link in L04 txn"): the admission link and its archived chain are
written inside the L04 commit transaction, and the authority-side evidence-use ledger is a separate authority-side file.
Replay uses exactly the bytes a client could still hold (the signed evidence and the old challenge record).

- RestartSafetyTests: no duplicate memory commit at any crash point across restarts and replays; a challenge prepared
  or consumed before a restart cannot be continued after it; issued evidence is never reissued.
- DurabilityContractTests: A3/A4 reserved evidence stays single-use across a restart; the A6 pre-commit boundary leaves
  neither admission nor link; A7 recovers ACCEPTED_MEMORY after a durable commit and a restart (reconciliation).

Real issuance stays unwired: only the TEST-environment synthetic broker signs. No DEV, no real key, no real memory.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
import unittest
from unittest import mock

import synthetic_b1b3b as T
from lilith_authority_signer import synthetic_broker as B
from lilith_authority_signer import synthetic_evidence_ledger as EL
from lilith_owner_memory import admission_v2 as V2
from lilith_owner_memory import l04_v2_adapter as AD

POINTS = (None,) + AD.FAULT_POINTS            # None = a complete, fully confirmed admission
COMMITTED = (None, "after_l04_commit", "after_link", "after_confirm")
UNCONFIRMED = ("after_l04_commit", "after_link")   # L04 + link committed, authority confirmation lost (A7)


class Crash(RuntimeError):
    pass


def crash_at(point):
    def hook(stage):
        if stage == point:
            raise Crash(point)
    return hook


class RestartCase(unittest.TestCase):
    def setUp(self) -> None:
        self.fresh()

    def fresh(self) -> None:
        self.flow = T.Flow(durable=True)
        self.addCleanup(self.flow.l04.close)

    def restart(self) -> T.Flow:
        """Rebuild broker and adapter objects in-process; the L04 and journal files survive."""
        return T.Flow(self.flow.l04, durable=True)

    def admit_then_crash(self, point, value="SYNTH-RESTART", nonce="fresh.a17", adapter=None):
        action, proposal, proof, evidence = self.flow.create(value, nonce)
        record = dict(self.flow.broker.ledger_record(proof.challenge["challengeId"]))
        adapter = adapter or (self.flow.make_adapter(fault_hook=crash_at(point)) if point else self.flow.adapter)
        if point is None:
            self.assertEqual(adapter.admit(self.flow.request(proposal, proof, evidence)).status, AD.L04_ADMITTED)
        else:
            with self.assertRaises(Crash):
                adapter.admit(self.flow.request(proposal, proof, evidence))
        return proposal, proof, evidence, record

    def replay(self, flow: T.Flow, proposal, proof, evidence, record):
        return flow.adapter.admit(flow.request(proposal, proof, evidence, challenge_record=record))

    def use_state(self, evidence):
        use = self.restart().ledger.lookup(evidence["evidenceId"])
        return None if use is None else use["state"]


class RestartSafetyTests(RestartCase):
    def test_no_crash_point_and_no_replay_produces_a_second_memory_commit(self):
        for point in POINTS:
            with self.subTest(point=point):
                self.fresh()
                proposal, proof, evidence, record = self.admit_then_crash(point)
                durable = self.flow.l04.counts()
                self.assertLessEqual(durable["memory_item"], 1)
                self.assertEqual(self.restart().l04.counts(), durable)              # the durable truth survives
                for _ in range(3):                                                 # replays across fresh restarts
                    result = self.replay(self.restart(), proposal, proof, evidence, record)
                    self.assertEqual((result.status, result.reason), (V2.NOT_ACCEPTED, "EVIDENCE_ALREADY_CONSUMED"))
                    self.assertEqual(self.flow.l04.counts(), durable)

    def test_a_committed_proposal_is_never_readmitted_after_restart(self):
        for point in COMMITTED:                                                    # L04 committed (A6 / A7)
            with self.subTest(point=point):
                self.fresh()
                proposal, proof, evidence, record = self.admit_then_crash(point)
                result = self.replay(self.restart(), proposal, proof, evidence, record)
                self.assertEqual((result.status, result.reason), (V2.NOT_ACCEPTED, "EVIDENCE_ALREADY_CONSUMED"))
                self.assertEqual(self.flow.l04.counts()["memory_item"], 1)

    def test_every_committed_admission_has_its_link_and_no_uncommitted_one_does(self):
        for point in POINTS:
            with self.subTest(point=point):
                self.fresh()
                proposal, *_ = self.admit_then_crash(point)
                linked = self.restart().links.get(proposal) is not None
                self.assertEqual(linked, self.flow.l04.counts()["memory_admission"] == 1)
                self.assertEqual(linked, point in COMMITTED)

    def test_a1_a_prepared_challenge_cannot_be_continued_after_restart(self):
        action, _ = self.flow.l04.action("SYNTH-A1")
        proof = T.owner_proof(action, "och.fresh.a1")
        self.assertEqual(self.flow.broker.prepare_challenge(proof.challenge_json).status, B.PREPARED)
        before = self.flow.l04.counts()
        consumed = self.restart().broker.consume_owner_proof(
            proof.challenge["challengeId"], action=proof.action, assertion=proof.assertion,
            owner_credential=proof.credential)
        self.assertEqual((consumed.status, consumed.reason), (B.REFUSED, "CHALLENGE_UNKNOWN"))
        self.assertEqual(self.flow.l04.counts(), before)

    def test_a2_a_consumed_challenge_cannot_be_signed_after_restart(self):
        action, _ = self.flow.l04.action("SYNTH-A2")
        proof = T.owner_proof(action, "och.fresh.a2")
        self.assertEqual(self.flow.broker.prepare_challenge(proof.challenge_json).status, B.PREPARED)
        self.flow.clock.value = T.CHALLENGE_ISSUED + T.timedelta(seconds=20)
        self.assertEqual(self.flow.broker.consume_owner_proof(
            proof.challenge["challengeId"], action=proof.action, assertion=proof.assertion,
            owner_credential=proof.credential).status, B.CONSUMED)
        before = self.flow.l04.counts()
        issued = self.restart().broker.issue_owner_evidence(B.OwnerEvidenceRequestV1(
            proof.challenge["challengeId"], proof.action, proof.assertion, proof.credential))
        self.assertEqual(issued.status, B.REFUSED)                               # the owner proof is burned
        self.assertEqual(self.flow.l04.counts(), before)

    def test_a5_issued_evidence_lost_in_transit_is_never_reissued(self):
        action, _ = self.flow.l04.action("SYNTH-A5")
        proof = T.owner_proof(action, "och.fresh.a5")
        self.flow.signed(proof)                                                   # the response is then "lost"
        request = B.OwnerEvidenceRequestV1(proof.challenge["challengeId"], proof.action, proof.assertion,
                                           proof.credential)
        self.assertEqual(self.flow.broker.issue_owner_evidence(request).status, B.REFUSED)    # same process
        self.assertEqual(self.restart().broker.issue_owner_evidence(request).status, B.REFUSED)  # after restart
        self.assertEqual(self.flow.l04.counts()["memory_item"], 0)


class DurabilityContractTests(RestartCase):
    """Required for First Memory; provided by the durable TEST link store and evidence-use ledger."""

    def test_a7_a_fully_confirmed_admission_stays_accepted_after_restart(self):
        for point in (None, "after_confirm"):
            with self.subTest(point=point):
                self.fresh()
                self.admit_then_crash(point)
                self.assertEqual(self.flow.read().status, V2.ACCEPTED_MEMORY)
                self.assertEqual(self.restart().read().status, V2.ACCEPTED_MEMORY)

    def test_a3_a4_reserved_evidence_stays_single_use_after_restart(self):
        proposal, proof, evidence, record = self.admit_then_crash("before_apply")
        result = self.replay(self.restart(), proposal, proof, evidence, record)
        self.assertEqual((result.status, result.reason, result.detail),
                         (V2.NOT_ACCEPTED, "EVIDENCE_ALREADY_CONSUMED", "EVIDENCE_ALREADY_RESERVED"))
        self.assertEqual(self.flow.l04.counts()["memory_item"], 0)
        self.assertEqual(self.use_state(evidence), EL.RESERVED)                   # fail-closed; owner re-authorizes

    def test_a6_a_crash_before_the_l04_commit_leaves_neither_admission_nor_link(self):
        for stage in ("after_revision", "before_commit"):                         # inside the L04 transaction
            with self.subTest(stage=stage):
                self.fresh()
                adapter = self.flow.make_adapter(store_overrides={"fault_hook": crash_at(stage)})
                before = self.flow.l04.counts()
                proposal, proof, evidence, record = self.admit_then_crash(stage, adapter=adapter)
                self.assertEqual(self.flow.l04.counts(), before)
                after = self.restart()
                self.assertIsNone(after.links.get(proposal))
                self.assertEqual(self.use_state(evidence), EL.RESERVED)
                self.assertNotEqual(after.read().status, V2.ACCEPTED_MEMORY)
                self.assertEqual(after.adapter.reconcile(proposal).reason, "ADMISSION_LINK_MISSING")
                result = self.replay(self.restart(), proposal, proof, evidence, record)
                self.assertEqual((result.status, result.reason), (V2.NOT_ACCEPTED, "EVIDENCE_ALREADY_CONSUMED"))
                self.assertEqual(self.flow.l04.counts(), before)

    def test_a6_a_failed_link_write_rolls_back_the_whole_admission(self):
        before = self.flow.l04.counts()
        with mock.patch.object(AD.L04AdmissionLinkStoreV1, "write_in_transaction", side_effect=Crash("link")):
            proposal, proof, evidence, record = self.admit_then_crash("link")
        self.assertEqual(self.flow.l04.counts(), before)                         # no admission without its link
        self.assertIsNone(self.restart().links.get(proposal))
        self.assertEqual(self.use_state(evidence), EL.RESERVED)

    def test_a7_lost_confirmation_is_reconciled_to_accepted_memory_after_restart(self):
        for point in UNCONFIRMED:
            with self.subTest(point=point):
                self.fresh()
                proposal, proof, evidence, record = self.admit_then_crash(point)
                committed = self.flow.l04.counts()
                after = self.restart()
                self.assertEqual(self.use_state(evidence), EL.RESERVED)
                self.assertNotEqual(after.read().status, V2.ACCEPTED_MEMORY)      # not accepted until confirmed
                self.assertEqual(after.adapter.reconcile(proposal).status, AD.RECONCILED)
                self.assertEqual(self.use_state(evidence), EL.CONSUMED)
                self.assertEqual(self.restart().read().status, V2.ACCEPTED_MEMORY)
                self.assertEqual(self.restart().adapter.reconcile(proposal).status, AD.RECONCILED)  # idempotent
                result = self.replay(self.restart(), proposal, proof, evidence, record)
                self.assertEqual((result.status, result.reason), (V2.NOT_ACCEPTED, "EVIDENCE_ALREADY_CONSUMED"))
                self.assertEqual(self.flow.l04.counts(), committed)               # reconciliation never re-applies

    def test_a7_corrupted_archived_challenge_cannot_confirm_reserved_evidence(self):
        proposal, _proof, evidence, _record = self.admit_then_crash("after_l04_commit")
        with contextlib.closing(sqlite3.connect(str(self.flow.l04.db))) as conn, conn:
            chain_json, = conn.execute(
                "SELECT chain_json FROM memory_admission_authority_link WHERE proposal_ref_id=?", (proposal,)
            ).fetchone()
            chain = json.loads(chain_json)
            chain.pop("challengeRecord")
            conn.execute("UPDATE memory_admission_authority_link SET chain_json=? WHERE proposal_ref_id=?",
                         (json.dumps(chain, sort_keys=True), proposal))
        after = self.restart()
        result = after.adapter.reconcile(proposal)
        self.assertEqual((result.status, result.reason), (V2.NOT_ACCEPTED, "OWNER_PROOF_REJECTED"))
        self.assertEqual(self.use_state(evidence), EL.RESERVED)
        self.assertNotEqual(after.read().status, V2.ACCEPTED_MEMORY)

    def test_authority_journal_conflict_does_not_confirm_in_memory(self):
        journal = T.EvidenceUseJournal(self.flow.l04.root / "conflict-journal.db")
        ledger = EL.SyntheticEvidenceUseLedgerV1(journal)
        digest = "a" * 64
        result = ledger.reserve(evidence_id="evid.conflict", evidence_digest=digest,
                                challenge_id="challenge.conflict", proposal_ref_id="proposal.conflict",
                                action_digest="b" * 64)
        self.assertEqual(result.status, EL.RESERVE_OK)
        # Simulate a conflicting on-disk record while the ledger stays in memory.
        with contextlib.closing(sqlite3.connect(journal.path)) as conn, conn:
            conn.execute("UPDATE evidence_use_v1 SET evidence_digest=? WHERE evidence_id=?",
                         ("c" * 64, "evid.conflict"))
        with self.assertRaisesRegex(RuntimeError, "journal write conflict"):
            ledger.confirm(evidence_id="evid.conflict", proposal_ref_id="proposal.conflict",
                           admission_id="admission.conflict", revision_id="revision.conflict")
        self.assertEqual(ledger.lookup("evid.conflict")["state"], EL.RESERVED)
        self.assertEqual(EL.SyntheticEvidenceUseLedgerV1(journal).lookup("evid.conflict")["state"], EL.RESERVED)

    def test_reconcile_refuses_without_a_durable_link_store(self):
        flow = T.Flow()
        self.addCleanup(flow.l04.close)
        result = flow.adapter.reconcile("anything")
        self.assertEqual((result.reason, result.detail), ("ADMISSION_LINK_MISSING", "LINK_STORE_NOT_DURABLE"))


if __name__ == "__main__":
    unittest.main()
