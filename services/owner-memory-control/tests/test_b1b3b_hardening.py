"""15B2b-B1b-3b pre-PR hardening (TEST-ONLY).

Covers the V1 new-write escape hatch, the accepted-memory read boundary,
authority-side evidence single use, proposal/basis binding, post-commit link
crashes, and B2a equivalence. Everything is synthetic, in-process, or in a
temporary directory.
"""

from __future__ import annotations

import copy
import pickle
import re
import sqlite3
import unittest

import synthetic_authority as SA
import synthetic_b1b3b as T
import synthetic_chain as SC
import test_accepted_memory_verifier as B2A_TESTS
from lilith_authority_signer import synthetic_evidence_ledger as EL
from lilith_memory import canonical_contracts as C
from lilith_memory import canonical_store
from lilith_memory import learning_v2
from lilith_owner_memory import accepted_read_v2 as AR
from lilith_owner_memory import admission_v2 as V2
from lilith_owner_memory import l04_v2_adapter as AD
from lilith_owner_memory import verifier as B2A


class Crash(RuntimeError):
    pass


def crash_at(point):
    def hook(stage):
        if stage == point:
            raise Crash(point)
    return hook


class HardeningCase(unittest.TestCase):
    def setUp(self) -> None:
        self.flow = T.Flow()
        self.addCleanup(self.flow.l04.close)

    def admit(self, proposal, proof, evidence, /, adapter=None, **replace):
        return (adapter or self.flow.adapter).admit(self.flow.request(proposal, proof, evidence, **replace))

    def accept(self, proof, evidence, proposal, /, **replace):
        return V2.verify_accepted_memory_v2(**self.flow.acceptance_kwargs(proof, evidence, proposal, **replace))

    def assertRejected(self, result, reason, detail=None):
        self.assertEqual((result.status, result.reason, result.detail), (V2.NOT_ACCEPTED, reason, detail), result)

    def raw_store(self):
        """An UNGUARDED store: models code that bypasses V2 admission mode."""
        return self.flow.l04.store()


# ------------------------------------------- 1. V1 new-write escape hatch ---

RUNTIME_APPLY_ALLOWLIST = {
    # Trusted DEV-only synthetic durability probe (fixed DEV helper; own probe
    # key and probe paths). Its V1 rows are never V2 accepted memory.
    "scripts/run_core_api_dev_durability_probe.py",
    # The only V2 new-admission entry point.
    "services/owner-memory-control/lilith_owner_memory/l04_v2_adapter.py",
}


class V1EscapeHatchTests(HardeningCase):
    def test_v2_mode_store_refuses_direct_v1_new_admission_with_valid_hmac_rows(self):
        l04 = self.flow.l04
        action, encoded = l04.action("SYNTH-V1-NEW")
        proposal = l04.proposal(action, encoded, nonce="v1.new")
        evidence = l04.last["actor_evidence"]
        guarded = AD.v2_admission_store(l04.store())
        # The V1 evidence is valid under historical V1 semantics...
        self.assertEqual(guarded.actor_authority.verify_historical_v1(evidence.actor_evidence_ref_id,
                                                                       action=action), evidence)
        # ...but cannot create NEW memory through a V2-mode store.
        result = guarded.apply(proposal)
        self.assertEqual((result.outcome, result.failure_code), (canonical_store.REJECTED, "ACTOR_UNRESOLVED"))
        self.assertEqual(l04.counts()["memory_item"], 0)
        self.assertRejected(self.flow.read(), "NOT_READABLE")

    def test_gate_opens_only_for_the_verified_action_during_the_adapter_apply(self):
        gate = AD.V2AdmissionActorGate(self.flow.l04.actor)
        action, _ = self.flow.l04.action("SYNTH-GATE")
        other, _ = self.flow.l04.action("SYNTH-OTHER")
        with self.assertRaises(Exception):
            gate.validate_existing("ae.x", action=action, require_consumed=True)
        with gate.admitting(other.action_digest):
            with self.assertRaises(Exception):
                gate.validate_existing("ae.x", action=action, require_consumed=True)
            with self.assertRaises(RuntimeError):
                with gate.admitting(action.action_digest):
                    pass
        with self.assertRaises(TypeError):
            AD.V2AdmissionActorGate(object())

    def test_adapter_refuses_a_store_not_in_v2_admission_mode(self):
        with self.assertRaises(TypeError):
            AD.L04V2AdmissionAdapter(self.raw_store(), owner_context=T.owner_context(),
                                     authority_context=T.authority_context(), registry_provider=lambda: None,
                                     link_store=self.flow.links, evidence_use_ledger=self.flow.ledger)
        with self.assertRaises(TypeError):  # app-held link store is not an authority ledger
            AD.L04V2AdmissionAdapter(AD.v2_admission_store(self.raw_store()), owner_context=T.owner_context(),
                                     authority_context=T.authority_context(), registry_provider=lambda: None,
                                     link_store=self.flow.links, evidence_use_ledger=self.flow.links)

    def test_unguarded_v1_row_is_storage_only_and_labelled_historical(self):
        l04 = self.flow.l04
        action, encoded = l04.action("SYNTH-V1-ONLY")
        proposal = l04.proposal(action, encoded, nonce="v1.only")
        self.assertEqual(self.raw_store().apply(proposal).outcome, canonical_store.ACCEPTED)
        self.assertIsNotNone(l04.store().get_active(T.L04_CLASS, T.L04_NAMESPACE, T.L04_KEY))  # stored
        self.assertRejected(self.flow.read(), "ADMISSION_LINK_MISSING")                          # not accepted
        historical = self.flow.reader().read_historical_v1(
            actor=l04.actor.ACTOR, memory_class=T.L04_CLASS, subject_namespace=T.L04_NAMESPACE,
            subject_key=T.L04_KEY)
        self.assertEqual((historical.read_class, historical.accepted_memory, historical.truth_claim),
                         (AR.HISTORICAL_V1_READ, False, False))
        self.assertIsNotNone(historical.row)

    def test_no_runtime_caller_reaches_v1_admission(self):
        root = SA.ROOT
        candidates = [p for p in list((root / "services").rglob("*.py")) + list((root / "scripts").glob("*.py"))
                      if ".venv" not in p.parts and "tests" not in p.parts and not p.name.startswith("test_")]
        callers = set()
        for path in candidates:
            if re.search(r"\.apply\(", path.read_text(encoding="utf-8", errors="ignore")):
                callers.add(path.relative_to(root).as_posix())
        self.assertEqual(callers, RUNTIME_APPLY_ALLOWLIST)
        app = (root / "services/core-api/app.py").read_text(encoding="utf-8")
        self.assertNotIn("lilith_memory", app)  # the PROD API never imports the canonical runtime


# ------------------------------------------ 2. accepted-memory read boundary ---

class AcceptedReadBoundaryTests(HardeningCase):
    def test_v2_admitted_and_verified_row_is_returned_as_accepted_not_truth(self):
        _, proposal, proof, evidence = self.flow.create("SYNTH-READ", "read.ok")
        self.assertEqual(self.admit(proposal, proof, evidence).status, AD.L04_ADMITTED)
        result = self.flow.read()
        self.assertEqual(result.status, V2.ACCEPTED_MEMORY, result)
        self.assertEqual((result.facts["readClass"], result.facts["truthClaim"], result.facts["epistemicBasis"]),
                         (AR.ACCEPTED_V2_READ, False, "USER_ASSERTED"))
        self.assertIn("SYNTH-READ", result.row["normalized_value_json"])

    def test_forged_db_rows_are_not_returned(self):
        l04 = self.flow.l04
        action, encoded = l04.action("SYNTH-FORGED")
        proposal = l04.proposal(action, encoded, nonce="read.forged")
        conn = l04.raw()
        try:
            conn.execute("INSERT INTO memory_item VALUES (?,?,?,?,?)",
                         ("mitem.forged", *action.identity, "2026-09-22T01:00:20Z"))
            conn.execute("INSERT INTO memory_admission VALUES (?,?,?,?,?,?)",
                         ("madm.forged", proposal, 1, "ACCEPTED", None, "2026-09-22T01:00:20Z"))
            conn.execute("INSERT INTO memory_revision VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                "mrev.forged", "mitem.forged", 1, learning_v2.VALUE_SCHEMA, encoded, action.payload_digest,
                proposal, None, None, "USER_ASSERTED", "OWNER_DIRECTED_EXACT_ACTION",
                l04.last["consent"].consent_id, None, None, "2026-09-22T01:00:20Z"))
            conn.execute("INSERT INTO memory_apply_audit VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                "mop.forged", proposal, "madm.forged", 1, C.CREATE, "mitem.forged", None, "mrev.forged",
                "mrev.forged", None, "2026-09-22T01:00:20Z"))
            conn.execute("INSERT INTO memory_active_revision VALUES (?,?,?,?)",
                         ("mitem.forged", "mrev.forged", "2026-09-22T01:00:20Z", "mop.forged"))
            conn.commit()
        finally:
            conn.close()
        self.assertIsNotNone(self.flow.l04_read_facade().read_exact(
            actor=l04.actor.ACTOR, memory_class=T.L04_CLASS, subject_namespace=T.L04_NAMESPACE,
            subject_key=T.L04_KEY))  # the unchanged L04 facade would return it
        self.assertRejected(self.flow.read(), "ADMISSION_LINK_MISSING")

    def test_l04_allows_one_revision_per_proposal_so_a_forged_revision_cannot_reuse_it(self):
        _, proposal, proof, evidence = self.flow.create("SYNTH-REAL", "read.reuse")
        admitted = self.admit(proposal, proof, evidence).facts["admission"]
        forged_value, forged_digest = learning_v2.normalize_project_codename({"codename": "SYNTH-SWAP"})
        conn = self.flow.l04.raw()
        try:
            with self.assertRaises(sqlite3.IntegrityError):  # UNIQUE(created_from_proposal_ref_id)
                conn.execute("INSERT INTO memory_revision VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    "mrev.swap", admitted["memoryItemId"], 1, learning_v2.VALUE_SCHEMA, forged_value,
                    forged_digest, proposal, None, None, "USER_ASSERTED", "OWNER_DIRECTED_EXACT_ACTION", None, None,
                    None, "2026-09-22T01:00:30Z"))
            # A forged revision under an invented proposal, made active.
            conn.execute("INSERT INTO memory_revision VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                "mrev.swap", admitted["memoryItemId"], 1, learning_v2.VALUE_SCHEMA, forged_value, forged_digest,
                "proposal-ref.forged", None, None, "USER_ASSERTED", "OWNER_DIRECTED_EXACT_ACTION",
                self.flow.l04.last["consent"].consent_id, None, None, "2026-09-22T01:00:30Z"))
            conn.execute("UPDATE memory_active_revision SET revision_id='mrev.swap' WHERE memory_item_id=?",
                         (admitted["memoryItemId"],))
            conn.commit()
        finally:
            conn.close()
        result = self.flow.read()
        self.assertEqual(result.status, V2.NOT_ACCEPTED)
        self.assertIn(result.reason, {"ADMISSION_LINK_MISSING", "NOT_READABLE"})

    def test_active_revision_must_be_the_revision_the_accepted_chain_created(self):
        _, proposal, proof, evidence = self.flow.create("SYNTH-INDEX", "read.index")
        self.admit(proposal, proof, evidence)
        self.assertEqual(self.flow.read().status, V2.ACCEPTED_MEMORY)
        # Defence in depth: a revision-to-proposal index that disagrees with
        # the accepted chain (e.g. a tampered store) is refused.
        original = AR.proposal_for_revision
        try:
            AR.proposal_for_revision = lambda _path, _revision: proposal
            reader = self.flow.reader()
            facade = reader._facade

            class Shifted:
                def read_exact(self, **kw):
                    return {**facade.read_exact(**kw), "revision_id": "mrev.other"}

            reader._facade = Shifted()
            self.assertRejected(reader.read_accepted(actor=self.flow.l04.actor.ACTOR, memory_class=T.L04_CLASS,
                                                     subject_namespace=T.L04_NAMESPACE, subject_key=T.L04_KEY),
                                "ACTIVE_REVISION_MISMATCH")
        finally:
            AR.proposal_for_revision = original

    def test_later_v1_supersede_hides_nothing_but_is_never_accepted(self):
        _, proposal, proof, evidence = self.flow.create("SYNTH-V2", "read.v2")
        admitted = self.admit(proposal, proof, evidence).facts["admission"]
        self.assertEqual(self.flow.read().status, V2.ACCEPTED_MEMORY)
        l04 = self.flow.l04
        action2, encoded2 = l04.action("SYNTH-V1-LATER", operation=C.SUPERSEDE, expected=admitted["revisionId"])
        ref2 = l04.proposal(action2, encoded2, nonce="read.v1later")
        self.assertEqual(self.raw_store().apply(ref2).outcome, canonical_store.ACCEPTED)
        self.assertRejected(self.flow.read(), "ADMISSION_LINK_MISSING")

    def test_privacy_hold_and_revoked_consent_remove_accepted_memory_from_reads(self):
        action, proposal, proof, evidence = self.flow.create("SYNTH-GONE", "read.gone")
        self.admit(proposal, proof, evidence)
        self.flow.l04.privacy.held = True
        self.assertRejected(self.flow.read(), "NOT_READABLE")
        self.flow.l04.privacy.held = False
        self.assertEqual(self.flow.read().status, V2.ACCEPTED_MEMORY)
        l04 = self.flow.l04
        revoke = l04.actor.issue(action=action, request_digest=T.digest("revoke"), nonce="read.revoke")
        l04.actor.resolve_and_consume(revoke.actor_evidence_ref_id, action=action, consumer_ref="test.revoke")
        l04.consent.revoke(l04.last["consent"].consent_id, actor_evidence_ref_id=revoke.actor_evidence_ref_id,
                           action=action)
        self.assertRejected(self.flow.read(), "NOT_READABLE")

    def test_nothing_readable_is_not_accepted(self):
        self.assertRejected(self.flow.read(), "NOT_READABLE")


# ------------------------------------------- 3. authority-side single use ---

class EvidenceSingleUseTests(HardeningCase):
    def test_first_use_succeeds_and_every_replay_is_refused(self):
        action, proposal, proof, evidence = self.flow.create("SYNTH-ONCE", "once")
        self.assertEqual(self.admit(proposal, proof, evidence).status, AD.L04_ADMITTED)
        record = self.flow.ledger.lookup(evidence["evidenceId"])
        self.assertEqual(record["state"], EL.CONSUMED)
        after = self.flow.l04.counts()
        # Exact replay, twice: deterministic.
        for _ in range(2):
            self.assertRejected(self.admit(proposal, proof, evidence), "EVIDENCE_ALREADY_CONSUMED",
                                "EVIDENCE_ALREADY_CONSUMED")
        # Replay against another admission: a SUPERSEDE of the same memory.
        action2, encoded2 = self.flow.l04.action("SYNTH-ONCE-2", operation=C.SUPERSEDE,
                                                 expected=record["revisionId"])
        other = self.flow.l04.proposal(action2, encoded2, nonce="once.other")
        self.assertRejected(self.admit(other, proof, evidence), "OWNER_PROOF_REJECTED", "OPERATION_MISMATCH")
        # Replay after the application wipes and forges its own link metadata.
        self.flow.links._by_proposal.clear()
        self.flow.links._chains.clear()
        self.assertRejected(self.admit(proposal, proof, evidence), "EVIDENCE_ALREADY_CONSUMED",
                            "EVIDENCE_ALREADY_CONSUMED")
        self.assertEqual(self.flow.l04.counts(), after)
        self.assertEqual(self.flow.ledger.lookup(evidence["evidenceId"]), record)

    def test_forged_duplicate_admission_of_the_same_evidence_is_not_accepted(self):
        action, proposal, proof, evidence = self.flow.create("SYNTH-DUP", "dup")
        self.admit(proposal, proof, evidence)
        link = self.flow.links.get(proposal)
        # A DB/link writer claims a second admission for the same evidence.
        forged_link = {**link, "admissionId": "madm.dup", "applyAuditId": "mop.dup", "revisionId": "mrev.dup"}
        forged_view = {**AD.read_l04_admission_view(self.flow.l04.db, proposal, action),
                       "admissionId": "madm.dup", "applyAuditId": "mop.dup", "revisionId": "mrev.dup"}
        self.assertRejected(self.accept(proof, evidence, proposal, link=forged_link, admission=forged_view),
                            "EVIDENCE_USE_MISMATCH")
        self.assertRejected(self.accept(proof, evidence, proposal, evidence_use=None), "EVIDENCE_USE_MISSING")
        self.assertEqual(self.accept(proof, evidence, proposal).status, V2.ACCEPTED_MEMORY)

    def test_l04_refusal_abandons_the_evidence_for_good(self):
        action, proposal, proof, evidence = self.flow.create("SYNTH-ABANDON", "abandon")
        consent = self.flow.l04.last["consent"]
        l04 = self.flow.l04
        revoke = l04.actor.issue(action=action, request_digest=T.digest("r"), nonce="abandon.revoke")
        l04.actor.resolve_and_consume(revoke.actor_evidence_ref_id, action=action, consumer_ref="test.revoke")
        l04.consent.revoke(consent.consent_id, actor_evidence_ref_id=revoke.actor_evidence_ref_id, action=action)
        self.assertRejected(self.admit(proposal, proof, evidence), "L04_NOT_ADMITTED", "REJECTED:CONSENT_REVOKED")
        self.assertEqual(self.flow.ledger.lookup(evidence["evidenceId"])["state"], EL.ABANDONED)
        self.assertRejected(self.admit(proposal, proof, evidence), "EVIDENCE_ALREADY_CONSUMED",
                            "EVIDENCE_ALREADY_ABANDONED")

    def test_ledger_is_authority_side_and_cannot_be_reset_or_copied(self):
        ledger = self.flow.ledger
        for operation in (pickle.dumps, copy.copy, copy.deepcopy):
            with self.assertRaises(TypeError):
                operation(ledger)
        public = {name for name in dir(ledger) if not name.startswith("_")}
        self.assertEqual(public, {"reserve", "confirm", "abandon", "lookup"})
        ok = dict(evidence_id="aev.x", evidence_digest="a" * 64, challenge_id="och.x", proposal_ref_id="p.x",
                  action_digest="b" * 64)
        self.assertEqual(ledger.reserve(**ok).status, EL.RESERVE_OK)
        self.assertEqual(ledger.reserve(**{**ok, "evidence_id": "aev.y"}).reason, "EVIDENCE_DIGEST_ALREADY_USED")
        self.assertEqual(ledger.reserve(**{**ok, "evidence_digest": "nothex"}).reason, "RESERVATION_MALFORMED")
        self.assertEqual(ledger.confirm(evidence_id="aev.x", proposal_ref_id="p.other", admission_id="a",
                                        revision_id="r").reason, "CONFIRMATION_REFUSED")
        view = ledger.lookup("aev.x")
        view["state"] = EL.CONSUMED  # a caller's copy cannot change the ledger
        self.assertEqual(ledger.lookup("aev.x")["state"], EL.RESERVED)
        self.assertEqual(ledger.abandon(evidence_id="aev.x", proposal_ref_id="p.x").status, EL.ABANDONED)
        self.assertEqual(ledger.abandon(evidence_id="aev.x", proposal_ref_id="p.x").reason, "ABANDON_REFUSED")

    def test_signer_and_ledger_are_separate_and_neither_is_the_verifier(self):
        self.assertFalse(any(isinstance(v, EL.SyntheticEvidenceUseLedgerV1)
                             for v in vars(self.flow.broker).values()))
        for name in ("sign", "issue_owner_evidence"):
            self.assertFalse(hasattr(self.flow.ledger, name))
            self.assertFalse(hasattr(self.flow.adapter, name))
            self.assertFalse(hasattr(self.flow.reader(), name))


# ------------------------------------- 4. proposalRefId / basis binding ---

class BindingGraphTests(HardeningCase):
    def test_action_digest_commits_every_semantic_action_field(self):
        action, _ = self.flow.l04.action("SYNTH-BIND")
        base = action.action_digest
        variants = {
            "actor_ref_id": "actor.other", "memory_class": "OTHER_CLASS", "subject_namespace": "project.other",
            "subject_key": "other", "value_schema": "OtherSchemaV1", "payload_digest": "f" * 64,
            "purpose": C.LONG_TERM_PERSONAL_PROJECT_RECALL,
        }
        for field, value in variants.items():
            if getattr(action, field) == value:
                continue
            with self.subTest(field=field):
                changed = C.FrozenMemoryActionV1(**{**action.__dict__, field: value})
                self.assertNotEqual(changed.action_digest, base)
        # The owner challenge commits the action digest; the evidence commits the challenge digest.
        proof = T.owner_proof(action, "och.bind")
        self.assertEqual(proof.challenge["actionDigest"], base)
        evidence = self.flow.signed(proof)
        self.assertEqual((evidence["actionDigest"], evidence["challengeDigest"]),
                         (base, proof.challenge.challenge_digest()))

    def test_proposal_substitution_cannot_change_the_admitted_operation(self):
        l04 = self.flow.l04
        action, proposal, proof, evidence = self.flow.create("SYNTH-SUBST", "subst")
        other_action, other_encoded = l04.action("SYNTH-SUBST-OTHER")
        other = l04.proposal(other_action, other_encoded, nonce="subst.other")
        self.assertRejected(self.admit(other, proof, evidence), "OWNER_PROOF_REJECTED", "PAYLOAD_DIGEST_MISMATCH")
        self.assertEqual(l04.counts()["memory_admission"], 0)
        self.assertEqual(self.admit(proposal, proof, evidence).status, AD.L04_ADMITTED)
        # One L04 candidate (hence one proposal) per action digest: a second
        # proposal with the IDENTICAL action cannot even be created.
        with self.assertRaises(sqlite3.IntegrityError):
            l04.proposal(action, learning_v2.normalize_project_codename({"codename": "SYNTH-SUBST"})[0],
                         nonce="subst.twin")
        # The authority-side ledger binds the evidence to the proposal it first admitted.
        self.assertEqual(self.flow.ledger.lookup(evidence["evidenceId"])["proposalRefId"], proposal)

    def test_epistemic_basis_is_fixed_by_l04_not_selectable_by_proposal(self):
        conn = sqlite3.connect(self.flow.l04.db)
        try:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(learning_proposal_v2)")}
        finally:
            conn.close()
        self.assertFalse({c for c in columns if "basis" in c or "epistemic" in c})
        import inspect
        source = inspect.getsource(canonical_store.CanonicalMemoryStoreV2.apply)
        self.assertIn('"USER_ASSERTED"', source)
        self.assertIn('"OWNER_DIRECTED_EXACT_ACTION"', source)
        self.assertEqual((V2.L04_V2_EPISTEMIC_BASIS, V2.L04_V2_ADMISSION_BASIS),
                         ("USER_ASSERTED", "OWNER_DIRECTED_EXACT_ACTION"))


# ------------------------------------------- 5. post-commit link crashes ---

class PostCommitCrashTests(HardeningCase):
    def setUp(self) -> None:
        super().setUp()
        self.action, self.proposal, self.proof, self.evidence = self.flow.create("SYNTH-CRASH", "crash")
        self.before = self.flow.l04.counts()

    def crashing(self, point):
        return self.flow.make_adapter(fault_hook=crash_at(point))

    def test_a_crash_before_l04_commit_leaves_nothing_durable(self):
        adapter = self.flow.make_adapter(store_overrides={"fault_hook": crash_at("before_commit")})
        with self.assertRaises(Crash):
            self.admit(self.proposal, self.proof, self.evidence, adapter=adapter)
        self.assertEqual(self.flow.l04.counts(), self.before)
        self.assertEqual(self.flow.ledger.lookup(self.evidence["evidenceId"])["state"], EL.RESERVED)
        self.assertRejected(self.flow.read(), "NOT_READABLE")
        self.assertRejected(self.admit(self.proposal, self.proof, self.evidence), "EVIDENCE_ALREADY_CONSUMED",
                            "EVIDENCE_ALREADY_RESERVED")

    def test_a2_crash_after_reservation_before_apply_leaves_nothing_durable(self):
        with self.assertRaises(Crash):
            self.admit(self.proposal, self.proof, self.evidence, adapter=self.crashing("before_apply"))
        self.assertEqual(self.flow.l04.counts(), self.before)
        self.assertRejected(self.flow.read(), "NOT_READABLE")
        self.assertRejected(self.admit(self.proposal, self.proof, self.evidence), "EVIDENCE_ALREADY_CONSUMED",
                            "EVIDENCE_ALREADY_RESERVED")

    def test_b_crash_after_commit_before_link_is_stored_but_never_accepted(self):
        with self.assertRaises(Crash):
            self.admit(self.proposal, self.proof, self.evidence, adapter=self.crashing("after_l04_commit"))
        self.assertIsNotNone(self.flow.l04.store().get_active(*self.action.identity))   # row may exist
        self.assertIsNone(self.flow.links.get(self.proposal))
        self.assertRejected(self.accept(self.proof, self.evidence, self.proposal), "ADMISSION_LINK_MISSING")
        self.assertRejected(self.flow.read(), "ADMISSION_LINK_MISSING")                  # excluded from reads
        for _ in range(2):
            self.assertRejected(self.admit(self.proposal, self.proof, self.evidence), "EVIDENCE_ALREADY_CONSUMED",
                                "EVIDENCE_ALREADY_RESERVED")
        counts = self.flow.l04.counts()
        self.assertEqual(counts["memory_item"], 1)            # no duplicate independent durable effect
        self.assertEqual(counts["memory_apply_audit"], 1)

    def test_b2_crash_after_link_before_authority_confirmation_is_not_accepted(self):
        with self.assertRaises(Crash):
            self.admit(self.proposal, self.proof, self.evidence, adapter=self.crashing("after_link"))
        self.assertIsNotNone(self.flow.links.get(self.proposal))
        self.assertEqual(self.flow.ledger.lookup(self.evidence["evidenceId"])["state"], EL.RESERVED)
        self.assertRejected(self.accept(self.proof, self.evidence, self.proposal), "EVIDENCE_USE_MISMATCH")
        self.assertRejected(self.flow.read(), "EVIDENCE_USE_MISMATCH")
        self.assertRejected(self.admit(self.proposal, self.proof, self.evidence), "EVIDENCE_ALREADY_CONSUMED",
                            "EVIDENCE_ALREADY_RESERVED")
        self.assertEqual(self.flow.l04.counts()["memory_item"], 1)

    def test_c_crash_after_link_and_confirmation_before_verification(self):
        with self.assertRaises(Crash):
            self.admit(self.proposal, self.proof, self.evidence, adapter=self.crashing("after_confirm"))
        self.assertEqual(self.accept(self.proof, self.evidence, self.proposal).status, V2.ACCEPTED_MEMORY)
        self.assertEqual(self.flow.read().status, V2.ACCEPTED_MEMORY)
        self.assertRejected(self.admit(self.proposal, self.proof, self.evidence), "EVIDENCE_ALREADY_CONSUMED",
                            "EVIDENCE_ALREADY_CONSUMED")
        self.assertEqual(self.flow.l04.counts()["memory_item"], 1)
        self.assertEqual(AD.FAULT_POINTS, ("before_apply", "after_l04_commit", "after_link", "after_confirm"))


# ------------------------------------- 6. forged internal rows and reads ---

class ForgedInternalRowReadTests(HardeningCase):
    def test_forged_policy_consent_rows_never_make_a_row_accepted(self):
        l04 = self.flow.l04
        action, encoded = l04.action("SYNTH-ROWS")
        proposal = l04.proposal(action, encoded, nonce="rows")   # complete, valid V1 internal rows
        self.assertRejected(self.admit(proposal, T.owner_proof(action, "och.rows"), None),
                            "AUTHORITY_EVIDENCE_MISSING")
        self.assertEqual(self.raw_store().apply(proposal).outcome, canonical_store.ACCEPTED)  # V1 storage only
        self.assertRejected(self.flow.read(), "ADMISSION_LINK_MISSING")


# ----------------------------------------------- 7. B2a equivalence ---

OWNER_PROOF_REASONS = frozenset(B2A.REASONS[:B2A.REASONS.index("OWNER_SIGNATURE_INVALID") + 1])
# Parse failures that can also arise in steps 7-9 (evidence, keys, admission).
SHARED_REASONS = frozenset({"MALFORMED_ARTIFACT", "UNSUPPORTED_SCHEMA_VERSION"})


class B2aEquivalenceTests(unittest.TestCase):
    def test_verify_owner_proof_matches_every_b2a_matrix_case(self):
        seen = []
        original = B2A_TESTS.verify

        def both(chain, **replace):
            kwargs = chain.kwargs(**replace)
            full = B2A.verify_accepted_memory(**kwargs)
            owner = B2A.verify_owner_proof(**{k: kwargs[k] for k in (
                "context", "action", "challenge_json", "challenge_record", "assertion", "owner_credential")})
            seen.append((full.reason, owner.status, owner.reason))
            return full

        B2A_TESTS.verify = both
        try:
            for name, run, reason in B2A_TESTS.CASES:
                with self.subTest(case=name):
                    self.assertEqual(run().reason, reason)
        finally:
            B2A_TESTS.verify = original
        self.assertEqual(len(seen), len(B2A_TESTS.CASES))
        for full_reason, owner_status, owner_reason in seen:
            if owner_status == B2A.NOT_ACCEPTED:
                # Steps 1-6 failed: the full verifier failed first, identically.
                self.assertEqual(owner_reason, full_reason)
            else:
                # Steps 1-6 passed: the full verifier failed later, never with
                # a reason only steps 1-6 can produce.
                self.assertEqual((owner_status, owner_reason), (B2A.VERIFIED_OWNER_PROOF, None))
                self.assertNotIn(full_reason, OWNER_PROOF_REASONS - SHARED_REASONS)
        chain = SC.Chain()
        self.assertEqual(B2A.verify_accepted_memory(**chain.kwargs()).facts["truthClaim"], False)
        self.assertEqual(B2A.verify_accepted_memory(**chain.kwargs()).facts["epistemicBasis"], "USER_ASSERTED")


# ------------------------------------------------ 9. policy equality ---

class PolicyEqualityTests(HardeningCase):
    def test_owner_challenge_policy_must_equal_authority_policy(self):
        action, proposal, proof, evidence = self.flow.create("SYNTH-POLICY", "policy")
        v1_proof = T.owner_proof(action, "och.policy.v1", policyVersion="policy.synthetic.v1")
        record = {"schemaVersion": 1, "challengeId": "och.policy.v1", "state": "CONSUMED",
                  "consumedCredentialRecordId": "ocred.synthetic", "consumedAt": "2026-09-26T12:00:20Z",
                  "ledgerEpoch": SC.LEDGER_EPOCH}
        adapter = AD.L04V2AdmissionAdapter(
            AD.v2_admission_store(self.flow.l04.store()), owner_context=SC.context(),
            authority_context=T.authority_context(), registry_provider=lambda: self.flow.registry_doc,
            link_store=self.flow.links, evidence_use_ledger=self.flow.ledger)
        result = adapter.admit(AD.V2AdmissionRequestV1(proposal, evidence, v1_proof.challenge_json, record,
                                                       v1_proof.assertion, v1_proof.credential))
        self.assertRejected(result, "CHALLENGE_AUTHORITY_CONTEXT_MISMATCH")
        self.assertIsNone(self.flow.ledger.lookup(evidence["evidenceId"]))  # refused before reservation
        self.assertEqual(self.admit(proposal, proof, evidence).status, AD.L04_ADMITTED)  # equal policies


if __name__ == "__main__":
    unittest.main()
