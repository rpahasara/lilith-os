"""FM-02 First Interaction family (versioned memory_action_v2 design): synthetic end-to-end over the V2 chain.

Synthetic only: a temporary L04 migrated to schema v2, the labelled TEST_ONLY FM-02 fixture, the synthetic owner
WebAuthn proof, the TEST_ONLY test-harness signer (lilith_authority_signer.synthetic_broker) and the synthetic
Identity V1 profile. No real conversation, identity, charter acceptance or memory exists or is created.

Two configurations, each asserting a definite outcome (nothing is skipped), selected by ADMISSION_V2_FAMILY_BASIS:
- `admission_v2` WITHOUT the separately reviewable family-basis change: its pinned USER_ASSERTED basis refuses every
  First Interaction admission through the genuine adapter (ADMISSION_BINDING_MISMATCH), with no L04 row written;
  Identity V1 therefore cannot bind.
- `admission_v2` WITH the owner-ratified family-basis change (it exposes EPISTEMIC_BASIS_BY_PURPOSE; the integrated
  tree): the chain reaches L04_ADMITTED, V2 ACCEPTED_MEMORY with RECORDED_INTERACTION, an accepted exact read and
  Identity V1 IDENTITY_BOUND.
Test-harness success is NOT released-signer compatibility: ReleasedSignerTests shows the installed signer's request
parser (authority-dev protocol over the unchanged canonical_contracts) refusing the new purpose.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import unittest
from pathlib import Path

import synthetic_b1b3b as T  # puts the core-api package on sys.path
import synthetic_first_memory as SF
import synthetic_fm02_l04 as FX
import synthetic_identity as SI
from lilith_memory import canonical_contracts as C
from lilith_memory import canonical_store
from lilith_memory import first_interaction_v1 as FI
from lilith_memory import learning_v2
from lilith_memory import memory_action_v2 as MA
from lilith_memory import memory_v2
from lilith_owner_memory import admission_v2 as V2
from lilith_owner_memory import first_memory_profile as FM
from lilith_owner_memory import identity_profile as IP
from lilith_owner_memory import l04_v2_adapter as AD

REPO = Path(__file__).resolve().parents[3]
# True only with the separately proposed admission_v2 basis change applied (owner ratification required).
ADMISSION_V2_FAMILY_BASIS = getattr(V2, "EPISTEMIC_BASIS_BY_PURPOSE", None) is not None


class FlowCase(unittest.TestCase):
    durable = True

    def setUp(self):
        self.flow = FX.FirstInteractionFlow(durable=self.durable)
        self.addCleanup(self.flow.l04.close)

    def bind(self, admitted_value, v2_inputs, context=None):
        return IP.verify_identity_bound_memory_v1(admitted_value=admitted_value,
                                                  identity_context=context or SI.context(), **v2_inputs)

    def stored(self) -> dict | None:
        return self.flow.l04.store().get_active(*MA.FIRST_INTERACTION_IDENTITY)

    def store_episode(self, value=None, nonce="fm02.create"):
        """The genuine adapter admission. Unchanged admission_v2: asserts its refusal (nothing written; the evidence use
        ABANDONED, per the merged #241 correction for a deterministic in-transaction refusal), then stores the episode
        by a direct L04 apply (not V2 acceptance) for L04-only tests."""
        action, proposal, proof, evidence = self.flow.create_fi(value, nonce)
        before = self.flow.l04.counts()
        result = self.flow.adapter.admit(self.flow.request(proposal, proof, evidence))
        if ADMISSION_V2_FAMILY_BASIS:
            self.assertEqual(result.status, AD.L04_ADMITTED, result)
        else:
            self.assertEqual((result.status, result.reason), (V2.NOT_ACCEPTED, "ADMISSION_BINDING_MISMATCH"))
            self.assertEqual(self.flow.l04.counts(), before)
            self.assertEqual(self.flow.ledger.lookup(evidence["evidenceId"])["state"], "ABANDONED")
            self.assertEqual(self.flow.l04.store().apply(proposal).outcome, canonical_store.ACCEPTED)
        return action, proposal, proof, evidence, result


class EndToEndTests(FlowCase):
    def test_synthetic_admission_and_identity_binding(self):
        # 1-3. Eligible candidate over the exact normalized value (identityBinding inside it), evidence-checked.
        value = SF.value()
        canonical, payload = learning_v2.normalize_for_purpose(FX.FI_PURPOSE, value)
        self.assertEqual(json.loads(canonical)[IP.BINDING_FIELD], SI.profile().binding())
        self.assertEqual(FI.verify_episode_evidence(canonical, SF.transcript_bytes())["payloadDigest"], payload)
        self.assertIs(FM.normalize_first_interaction_episode, FI.normalize_first_interaction_episode)
        # 4. Owner proof -> test-harness-signed OwnerEvidenceV2 over the exact action and payload.
        action, proposal, proof, evidence = self.flow.create_fi(value)
        self.assertIsInstance(action, MA.FirstInteractionActionV1)
        self.assertEqual(self.flow.l04.last["candidate"].candidate_id.split(".")[1], "fi")
        self.assertEqual((evidence["payloadDigest"], evidence["actionDigest"]), (payload, action.action_digest))
        # 5. L04 CREATE through the genuine adapter.
        before = self.flow.l04.counts()
        admitted = self.flow.adapter.admit(self.flow.request(proposal, proof, evidence))
        v2_inputs = self.flow.acceptance_kwargs(proof, evidence, proposal)
        if not ADMISSION_V2_FAMILY_BASIS:
            self.assertEqual((admitted.status, admitted.reason), (V2.NOT_ACCEPTED, "ADMISSION_BINDING_MISMATCH"))
            self.assertEqual(self.flow.l04.counts(), before)                     # fail closed: nothing written
            self.assertIsNone(self.stored())
            self.assertEqual(self.flow.read_fi().reason, "NOT_READABLE")
            bound = self.bind(canonical, v2_inputs)
            self.assertEqual((bound.status, bound.reason), (IP.IDENTITY_NOT_BOUND, "ACCEPTED_MEMORY_REQUIRED"))
            return
        self.assertEqual(admitted.status, AD.L04_ADMITTED, admitted)
        self.assertIs(admitted.facts["memoryAcceptance"], False)
        # 6. The V2 verifier: ACCEPTED_MEMORY with the family's L04-fixed basis.
        accepted = V2.verify_accepted_memory_v2(**v2_inputs)
        self.assertEqual(accepted.status, V2.ACCEPTED_MEMORY, accepted)
        self.assertEqual(accepted.facts["epistemicBasis"], MA.RECORDED_INTERACTION)
        self.assertIs(accepted.facts["truthClaim"], False)
        # 8. A subsequent authorized exact read through the accepted-memory facade.
        read = self.flow.read_fi()
        self.assertEqual(read.status, V2.ACCEPTED_MEMORY, read)
        self.assertEqual(read.row["normalized_value_json"], canonical)
        # 7. Identity V1 over the actually admitted value.
        bound = self.bind(read.row["normalized_value_json"], v2_inputs)
        self.assertEqual(bound.status, IP.IDENTITY_BOUND, bound)
        self.assertEqual(bound.facts["lilithIdentityId"], SI.SYNTHETIC_IDENTITY_ID)
        self.assertIs(bound.facts["authorizesAdmission"], False)

    def test_nothing_real_was_created(self):
        self.store_episode()
        self.assertEqual(SI.SYNTHETIC_IDENTITY_ID,
                         "lid1." + hashlib.sha256(b"TEST_ONLY synthetic lilith identity 1").hexdigest()[:32])
        self.assertIn(b"TEST_ONLY", SI.SYNTHETIC_CHARTER_BYTES)
        self.assertEqual(SI.profile().environment, "test")
        self.assertTrue(all(q["text"].startswith("TEST_ONLY") for q in SF.value()["quotations"]))
        self.assertTrue(str(self.flow.l04.db).startswith(str(self.flow.l04.root)))


class ReleasedSignerTests(unittest.TestCase):
    """The installed signer validates actions with the unchanged canonical_contracts: it refuses the new purpose
    until a reviewed signer release adopts memory_action_v2. Codename requests still pass action parsing."""

    def parse(self, action_fields):
        sys.path.insert(0, str(REPO / "services" / "authority-dev"))
        try:
            from lilith_authority_dev import protocol as P
        finally:
            sys.path.pop(0)
        payload = {name: None for name in P._PAYLOAD_FIELDS[P.ISSUE_OWNER_EVIDENCE]}
        payload.update(challengeId="och.fm02.released", action=action_fields)
        try:
            P.parse_issue_request(payload)
        except P.ProtocolError as exc:
            return str(exc)
        return None

    def test_released_signer_refuses_the_first_interaction_purpose(self):
        harness = FX.FirstInteractionHarness(migrate=False)
        self.addCleanup(harness.close)
        fi_action, _ = harness.fi_action()
        codename_action, _ = harness.action("SYNTH-ALPHA")
        self.assertEqual(self.parse(fi_action.semantic_dict()), "INVALID_ACTION")
        self.assertNotEqual(self.parse(codename_action.semantic_dict()), "INVALID_ACTION")   # fails later instead


class NegativeTests(FlowCase):
    def test_wrong_identity_charter_or_environment(self):
        _a, proposal, proof, evidence, _r = self.store_episode()
        value = self.stored()["normalized_value_json"]
        cases = (
            (SI.context(trusted_profile=SI.profile(lilith_identity_id="lid1." + "0" * 31 + "1")),
             "IDENTITY_BINDING_MISMATCH"),
            (SI.context(trusted_profile=SI.profile(charter_digest="f" * 64)), "CHARTER_MISMATCH"),
            (SI.context(environment="dev"), "IDENTITY_ENVIRONMENT_MISMATCH"),
        )
        v2_inputs = self.flow.acceptance_kwargs(proof, evidence, proposal)
        for context, reason in cases:
            with self.subTest(reason=reason):
                if ADMISSION_V2_FAMILY_BASIS:
                    self.assertEqual(self.bind(value, v2_inputs, context).reason, reason)
                else:                                     # COMPARISON ONLY: no genuine acceptance exists here
                    with self.assertRaises(IP._Reject) as raised:
                        IP._compare_binding(json.loads(value)[IP.BINDING_FIELD], context)
                    self.assertEqual(raised.exception.reason, reason)

    def test_changed_transcript_or_quotation(self):
        self.store_episode()
        value = self.stored()["normalized_value_json"]
        with self.assertRaisesRegex(FI.FirstMemoryContractViolation, "TRANSCRIPT_DIGEST_MISMATCH"):
            FI.verify_episode_evidence(value, SF.transcript_bytes().replace(b"moring", b"morning"))
        # Transcript fidelity is enforced before owner authorization (FM-05/06), not inside L04 apply.
        corrected = SF.OPENING_LILITH.replace("moring", "morning")
        quotes = [SF.quotation(FM.OPENING, 0), SF.quotation(FM.OPENING, 1, end=len(corrected), text=corrected),
                  SF.quotation(FM.CLOSING, 4)]
        with self.assertRaisesRegex(FI.FirstMemoryContractViolation, "QUOTATION_NOT_VERBATIM"):
            FI.verify_episode_evidence(SF.canonical(quotations=quotes), SF.transcript_bytes())

    def test_payload_modified_after_authorization(self):
        action, _encoded = self.flow.l04.fi_action()
        proof = T.owner_proof(action, "och.fm02.signed")
        evidence = self.flow.signed(proof)
        other, other_encoded = self.flow.l04.fi_action(SF.value(quotations=[SF.quotation(FM.OPENING, 0),
                                                                            SF.quotation(FM.CLOSING, 3)]))
        swapped = self.flow.l04.proposal(other, other_encoded, nonce="fm02.swapped")
        before = self.flow.l04.counts()
        result = self.flow.adapter.admit(self.flow.request(swapped, proof, evidence))
        self.assertEqual((result.status, result.reason, result.detail),
                         (V2.NOT_ACCEPTED, "OWNER_PROOF_REJECTED", "PAYLOAD_DIGEST_MISMATCH"))
        self.assertEqual(self.flow.l04.counts(), before)
        # A stored value rewritten after admission no longer re-normalizes to its digest (adapter re-check).
        _a, proposal, _p, _e, _r = self.store_episode(nonce="fm02.tamper")
        tampered = self.stored()["normalized_value_json"].replace("moring", "morning")
        conn = self.flow.l04.raw()
        try:
            trigger = conn.execute("SELECT sql FROM sqlite_master WHERE name='memory_revision_no_update'").fetchone()[0]
            conn.execute("DROP TRIGGER memory_revision_no_update")
            conn.execute("UPDATE memory_revision SET normalized_value_json=?", (tampered,))
            conn.execute(trigger)
            conn.commit()
        finally:
            conn.close()
        view = AD.read_l04_admission_view(self.flow.l04.db, proposal, AD.resolve_v2_action(self.flow.l04.store(),
                                                                                        proposal))
        self.assertIsNone(view["payloadDigest"])
        self.assertEqual(self.flow.read_fi().status, V2.NOT_ACCEPTED)

    def test_wrong_purpose_or_capability(self):
        with self.assertRaises(C.ContractError):
            self.flow.l04.fi_action(purpose=C.LONG_TERM_PERSONAL_PROJECT_RECALL)
        action, _encoded = self.flow.l04.fi_action()
        ev = self.flow.l04.actor.issue(action=action, request_digest=T.digest("request:cap"), nonce="cap")
        with self.assertRaises(Exception):
            self.flow.l04.policy.decide(action=action, actor_evidence_ref_id=ev.actor_evidence_ref_id,
                                        capability=C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE)
        flow = FX.FirstInteractionFlow()
        self.addCleanup(flow.l04.close)
        _a, proposal, proof, evidence = flow.create_fi(nonce="fm02.inactive")
        adapter = flow.make_adapter(store_overrides={"capability_provider": lambda c: c == T.L04_CAPABILITY})
        before = flow.l04.counts()["memory_item"]
        result = adapter.admit(flow.request(proposal, proof, evidence))
        self.assertEqual((result.status, result.reason, result.detail),
                         (V2.NOT_ACCEPTED, "L04_NOT_ADMITTED", "REJECTED:CAPABILITY_INACTIVE"))
        self.assertEqual(flow.l04.counts()["memory_item"], before)
        bad = T.owner_proof(action, "och.fm02.purpose", purpose=C.LONG_TERM_PERSONAL_PROJECT_RECALL)
        self.assertEqual(self.flow.broker.prepare_challenge(bad.challenge_json).status, "PREPARED")
        consumed = self.flow.broker.consume_owner_proof(bad.challenge["challengeId"], action=action,
                                                        assertion=bad.assertion, owner_credential=bad.credential)
        self.assertEqual((consumed.status, consumed.reason, consumed.detail),
                         ("REFUSED", "OWNER_PROOF_REJECTED", "MEMORY_IDENTITY_MISMATCH"))

    def test_supersede_and_restore_are_refused(self):
        for operation, fields in ((C.SUPERSEDE, {"expected_active_revision_id": "mrev.x"}),
                                  (C.RESTORE, {"expected_active_revision_id": "mrev.x", "restore_revision_id": "mrev.y",
                                               "value_schema": None})):
            with self.subTest(operation=operation), self.assertRaises(C.ContractError):
                self.flow.l04.fi_action(operation=operation, **fields)[0].validate()

    def test_unauthorized_read_and_missing_owner_authentication(self):
        self.store_episode()
        with self.assertRaisesRegex(PermissionError, "ACTOR_UNRESOLVED"):
            self.flow.read_fi(actor=None)
        stranger = C.ActorRefV1(1, "actor.someone-else.v1", C.LOCAL_OWNER_ACTOR_ID, C.LOCAL_OWNER_AUTHORITY_V1,
                                C.OWNER_CONTROLLED_HOME_CONTEXT)
        with self.assertRaisesRegex(PermissionError, "ACTOR_UNRESOLVED"):
            self.flow.read_fi(actor=stranger)
        unreadable = memory_v2.CanonicalTupleRegistry((self.flow.l04.registry_policy, memory_v2.MemoryTuplePolicyV1(
            FX.FI_CLASS, FX.FI_NAMESPACE, FX.FI_KEY, MA.FIRST_INTERACTION_VALUE_SCHEMA, FX.FI_CAPABILITY,
            read_allowed=False, write_allowed=True)))
        facade = memory_v2.CanonicalMemoryReadFacade(
            self.flow.l04.store(), registry=unreadable, consent_store=self.flow.l04.consent,
            privacy_hold_resolver=self.flow.l04.privacy, actor_resolver=lambda a: a == self.flow.l04.actor.ACTOR)
        with self.assertRaisesRegex(PermissionError, "UNKNOWN_MEMORY_TUPLE"):
            facade.read_exact(actor=self.flow.l04.actor.ACTOR, memory_class=FX.FI_CLASS,
                              subject_namespace=FX.FI_NAMESPACE, subject_key=FX.FI_KEY)

    def test_duplicate_create_and_idempotent_replay(self):
        _a, proposal, proof, evidence, _r = self.store_episode()
        first_value = self.stored()["normalized_value_json"]
        before = self.flow.l04.counts()
        self.assertEqual(self.flow.l04.store().apply(proposal).outcome, canonical_store.ALREADY_APPLIED)
        replay = self.flow.adapter.admit(self.flow.request(proposal, proof, evidence))
        self.assertEqual(replay.status, V2.NOT_ACCEPTED)            # evidence already reserved/consumed
        self.assertEqual(self.flow.l04.counts(), before)
        second = SF.value(quotations=[SF.quotation(FM.OPENING, 0), SF.quotation(FM.CLOSING, 3)])
        action2, encoded2 = self.flow.l04.fi_action(second)
        duplicate = self.flow.l04.store().apply(self.flow.l04.proposal(action2, encoded2, nonce="fm02.second"))
        self.assertEqual((duplicate.outcome, duplicate.failure_code),
                         (canonical_store.PRECONDITION_FAILED, "MEMORY_ALREADY_EXISTS"))
        self.assertEqual(self.stored()["normalized_value_json"], first_value)        # the first stays first

    def test_v2_admission_gate_foundation_does_not_dispatch_the_family(self):
        _a, proposal, _p, _e = self.flow.create_fi(nonce="fm02.gate")
        l04 = self.flow.l04
        gate = memory_v2.L04V2AdmissionGate(
            l04.learning, enabled_provider=lambda: True,
            family_registry=memory_v2.ProposalFamilyRegistry((learning_v2.FIRST_INTERACTION_PROPOSAL_FAMILY,)),
            memory_registry=l04.tuple_registry, actor_authority=l04.actor, policy_store=l04.policy,
            consent_store=l04.consent, rollback_authority=l04.rollback, privacy_hold_resolver=l04.privacy)
        self.assertEqual(gate.evaluate(proposal).failure_code, "V1_DISPATCH_UNCHANGED")


class PrivacyTests(FlowCase):
    def setUp(self):
        harness = FX.FirstInteractionHarness()
        self.privacy = harness.privacy_store()
        harness.privacy = self.privacy
        harness.learning.privacy_hold_resolver = self.privacy
        self.flow = FX.FirstInteractionFlow(harness)
        self.addCleanup(harness.close)

    def forget(self):
        l04 = self.flow.l04
        active = self.stored()
        action = MA.action_from_fields(
            schema_version=1, actor_ref_id=l04.actor.ACTOR.actor_ref_id, operation=C.FORGET, memory_class=FX.FI_CLASS,
            subject_namespace=FX.FI_NAMESPACE, subject_key=FX.FI_KEY, value_schema=None, payload_digest="0" * 64,
            expected_active_revision_id=None, restore_revision_id=None, purpose=FX.FI_PURPOSE)
        ev = l04.actor.issue(action=action, request_digest=T.digest("request:forget"), nonce="forget")
        _request, auth, _suppression = self.privacy.begin_forget(
            action=action, actor_evidence_ref_id=ev.actor_evidence_ref_id, intent_ref_id="intent.forget",
            memory_item_id=None if active is None else active["memory_item_id"],
            resource_owners=("L04", "L18_V2"), confirmation_event_ref="confirm.forget")
        l04_result = memory_v2.L04PrivacyErasureOwner(l04.db, self.privacy).erase_authorized(
            auth.authorization_ref_id, auth.execution_nonce)
        l18_result = memory_v2.L18V2PrivacyErasureOwner(l04.db, self.privacy).erase_authorized(
            auth.authorization_ref_id, auth.execution_nonce)
        return l04_result, l18_result, self.privacy.complete(auth.authorization_ref_id, auth.execution_nonce)

    def assert_erased(self):
        conn = sqlite3.connect(self.flow.l04.db)
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            for table in ("memory_item", "memory_revision", "memory_admission",
                          *sorted(learning_v2.FIRST_INTERACTION_TABLES)):
                with self.subTest(table=table):
                    self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM learning_proposal_ref WHERE proposal_family=?",
                                          (learning_v2.FIRST_INTERACTION_PROPOSAL_FAMILY,)).fetchone()[0], 0)
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            conn.close()
        raw = self.flow.l04.db.read_bytes()
        for snippet in (b"moring", b"good night", b"TEST_ONLY hi LILITH"):
            self.assertNotIn(snippet, raw)

    def test_forget_erases_the_episode_and_blocks_a_replacement_first_memory(self):
        self.store_episode(nonce="fm02.forget")
        _l04, _l18, receipt = self.forget()
        self.assertEqual(receipt.verification_status, "COMPLETE")
        self.assert_erased()
        # The monotonic Privacy restore-suppression selector blocks a replacement "first memory" (no new tombstone).
        self.assertTrue(self.privacy.is_held(*MA.FIRST_INTERACTION_IDENTITY))
        second = SF.value(quotations=[SF.quotation(FM.OPENING, 0), SF.quotation(FM.CLOSING, 3)])
        action, encoded = self.flow.l04.fi_action(second)
        with self.assertRaises(AssertionError):                    # the harness requires REAL_ELIGIBLE
            self.flow.l04.proposal(action, encoded, nonce="fm02.replacement")
        conn = sqlite3.connect(self.flow.l04.db)
        try:
            assessed = conn.execute("SELECT outcome,reason_code FROM learning_fi_assessment_v1").fetchall()
        finally:
            conn.close()
        self.assertEqual(assessed, [("REJECTED", "PRIVACY_HOLD_ACTIVE")])
        with self.assertRaisesRegex(AD.Reject, "PRIVACY_HOLD_ACTIVE"):
            self.flow.adapter._privacy_clear(action)
        self.assertIsNone(self.stored())

    def test_forget_with_a_rejected_duplicate_completes(self):
        """The merged #240 correction, extended to the First Interaction family."""
        self.store_episode(nonce="fm02.first")
        second = SF.value(quotations=[SF.quotation(FM.OPENING, 0), SF.quotation(FM.CLOSING, 3)])
        action2, encoded2 = self.flow.l04.fi_action(second)
        duplicate = self.flow.l04.store().apply(self.flow.l04.proposal(action2, encoded2, nonce="fm02.duplicate"))
        self.assertEqual((duplicate.outcome, duplicate.failure_code),
                         (canonical_store.PRECONDITION_FAILED, "MEMORY_ALREADY_EXISTS"))
        l04, l18, receipt = self.forget()
        self.assertEqual((l04["status"], l18["status"], receipt.verification_status),
                         ("COMPLETE", "COMPLETE", "COMPLETE"))
        self.assert_erased()


class CodenameTests(FlowCase):
    def test_codename_family_is_unchanged_on_the_migrated_database(self):
        action, proposal, proof, evidence = self.flow.create("SYNTH-ALPHA", "codename.v2db")
        self.assertIs(type(action), C.FrozenMemoryActionV1)
        result = self.flow.adapter.admit(self.flow.request(proposal, proof, evidence))
        self.assertEqual(result.status, AD.L04_ADMITTED)
        accepted = V2.verify_accepted_memory_v2(**self.flow.acceptance_kwargs(proof, evidence, proposal))
        self.assertEqual((accepted.status, accepted.facts["epistemicBasis"]), (V2.ACCEPTED_MEMORY, "USER_ASSERTED"))
        self.assertEqual(self.flow.read().status, V2.ACCEPTED_MEMORY)


if __name__ == "__main__":
    unittest.main()
