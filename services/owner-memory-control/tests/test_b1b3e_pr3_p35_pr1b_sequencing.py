"""15B2b-B1b-3e PR-3 P3-5: PR-1B bootstrap sequencing (TEST-ONLY, offline).

Record: docs/architecture/slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md.

The sequencer is exercised with synthetic evidence. One full run drives
temporary replicas and a real K-WIT-signed TEST chain through the P3-2 tool.
No DEV host, cloud resource, key, or real owner replica is touched.
"""

from __future__ import annotations

import unittest

import synthetic_authority as SA  # noqa: F401  (sets sys.path)
import synthetic_b1b3e as F
import test_b1b3e_pr3_p32_owner_freshness_tool as P32
from lilith_owner_memory import owner_freshness as OF
from lilith_owner_memory import owner_freshness_tool as T
from lilith_owner_memory import pr1b_sequencing as S

ROOT = SA.ROOT
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md"

EMPTY = OF.OwnerRegisterResultV1(OF.REGISTER_NOT_VERIFIED, "OWNER_REGISTER_EMPTY")
CURRENT = OF.FreshnessResultV1(OF.AUTHENTIC, OF.CURRENT)
ALL_PRECONDITIONS = {name: True for name in S.PRECONDITIONS}


def evidence(step: S.StepV1, **extra):
    value = {name: True for name in step.evidence}
    if step.action == "CHECK_ELIGIBILITY":
        value = {"eligibilityResult": S.evaluate_eligibility(ALL_PRECONDITIONS)}
    if step.gate == S.REQUIRED_UNKNOWN_BLOCK or step.action in ("COMMIT_WITNESS_GENESIS", "APPEND_RECORD_1_REPLICA_A"):
        value["ownerRegister"] = EMPTY
    if step.gate == S.REQUIRED_CURRENT or step.action == "APPEND_RECORD_1_REPLICA_B":
        value["freshness"] = CURRENT
    value.update(extra)
    return value


def run_until(sequencer: S.BootstrapSequencerV1, action: str) -> None:
    for step in S.STEPS:
        if step.action == action:
            return
        if step.action in sequencer.history:
            continue
        result = sequencer.advance(step.action, evidence(step))
        assert result.advanced, result


class EligibilityTests(unittest.TestCase):
    def test_pr1b_blocked_while_p33_incomplete(self):
        real_state = dict(ALL_PRECONDITIONS, p33Complete=False, twoRealReplicasExist=False,
                          replicaIndependenceEstablished=False, replicasAgentUnreachableCopy=False,
                          pr1bAuthorized=False)
        result = S.evaluate_eligibility(real_state)
        self.assertEqual(result.status, S.PR1B_NOT_ELIGIBLE)
        self.assertIn("P3_3_INCOMPLETE", result.reasons)
        s = S.BootstrapSequencerV1()
        refused = s.advance("CHECK_ELIGIBILITY", {"eligibilityResult": result})
        self.assertEqual((refused.reason, s.state), (S.PR1B_NOT_ELIGIBLE, "PR1B_INELIGIBLE"))

    def test_synthetic_rehearsal_cannot_override_p33(self):
        facts = dict(ALL_PRECONDITIONS, p33Complete=False, syntheticRehearsalPassed=True)
        result = S.evaluate_eligibility(facts)
        self.assertFalse(result.eligible)
        self.assertIn("P3_3_INCOMPLETE", result.reasons)
        self.assertTrue(any(r.startswith("UNKNOWN_PRECONDITION") for r in result.reasons))

    def test_every_precondition_is_required_and_truthiness_is_not_enough(self):
        for name, reason in S.PRECONDITIONS.items():
            for value in (False, None, 1, "yes"):
                result = S.evaluate_eligibility(dict(ALL_PRECONDITIONS, **{name: value}))
                self.assertIn(reason, result.reasons, (name, value))
        self.assertTrue(S.evaluate_eligibility(ALL_PRECONDITIONS).eligible)
        stale = S.evaluate_eligibility(dict(ALL_PRECONDITIONS, pr2InventoryRevalidated=False))
        self.assertEqual(stale.reasons, (S.PR2_REVALIDATION_REQUIRED,))
        self.assertEqual(S.evaluate_eligibility(None).status, S.PR1B_NOT_ELIGIBLE)


class OrderingTests(unittest.TestCase):
    def test_full_valid_synthetic_sequence_reaches_full_readiness(self):
        s = S.BootstrapSequencerV1()
        run_until(s, None)
        self.assertEqual(s.state, "FULL_READINESS")
        self.assertEqual(len(s.history), len(S.STEPS))
        self.assertEqual(S.STATES[-1], "FULL_READINESS")

    def test_invalid_order_rejected(self):
        s = S.BootstrapSequencerV1()
        run_until(s, "PIN_GENESIS")
        for action in ("COMMIT_WITNESS_GENESIS", "APPEND_RECORD_1_REPLICA_A", "WRITE_HELD", "WRITE_RELEASED",
                       "GENERATE_K_WIT"):
            result = s.advance(action, evidence(S.BY_ACTION[action]))
            self.assertFalse(result.advanced, action)
            self.assertIn(result.reason, {"TRANSITION_OUT_OF_ORDER", "REPEATED_IRREVERSIBLE_TRANSITION"}, action)
        self.assertEqual(s.state, "GENESIS_PREPARED")

    def test_no_record_1_before_genesis_pin_and_witness_material(self):
        for stop_before in ("PIN_GENESIS", "START_WITNESS", "COMMIT_WITNESS_GENESIS"):
            s = S.BootstrapSequencerV1()
            run_until(s, stop_before)
            result = s.advance("APPEND_RECORD_1_REPLICA_A", evidence(S.BY_ACTION["APPEND_RECORD_1_REPLICA_A"]))
            self.assertEqual(result.reason, "TRANSITION_OUT_OF_ORDER", stop_before)
        order = [step.action for step in S.STEPS]
        self.assertLess(order.index("PIN_GENESIS"), order.index("COMMIT_WITNESS_GENESIS"))
        self.assertLess(order.index("COMMIT_WITNESS_GENESIS"), order.index("APPEND_RECORD_1_REPLICA_A"))
        self.assertLess(order.index("APPEND_RECORD_1_REPLICA_B"), order.index("WRITE_HELD"))
        self.assertLess(order.index("WRITE_HELD"), order.index("START_SIGNER"))
        self.assertLess(order.index("PROVISION_LEDGER"), order.index("PREPARE_GENESIS_CANDIDATE"))

    def test_repeated_irreversible_transition_rejected(self):
        s = S.BootstrapSequencerV1()
        run_until(s, "SIGN_REGISTRY_V1")
        again = s.advance("GENERATE_K_WIT", evidence(S.BY_ACTION["GENERATE_K_WIT"]))
        self.assertEqual(again.reason, "REPEATED_IRREVERSIBLE_TRANSITION")
        run_until(s, "START_SIGNER")
        self.assertEqual(s.advance("WRITE_HELD", evidence(S.BY_ACTION["WRITE_HELD"])).reason,
                         "REPEATED_IRREVERSIBLE_TRANSITION")
        self.assertEqual(s.reset().reason, "REBOOTSTRAP_FORBIDDEN")

    def test_reset_only_before_any_point_of_no_return(self):
        s = S.BootstrapSequencerV1()
        run_until(s, "GENERATE_K_WIT")                    # K-ROOT is off-host; no PONR yet
        self.assertTrue(s.reset().advanced)
        run_until(s, "SIGN_REGISTRY_V1")                  # K-WIT generated: custody PONR
        self.assertEqual(s.reset().reason, "REBOOTSTRAP_FORBIDDEN")

    def test_halt_is_terminal(self):
        s = S.BootstrapSequencerV1()
        run_until(s, "COMMIT_WITNESS_GENESIS")
        committed_differs = s.advance("COMMIT_WITNESS_GENESIS",
                                      evidence(S.BY_ACTION["COMMIT_WITNESS_GENESIS"], committedDigestEqualsPin=False))
        self.assertEqual(committed_differs.reason, "EVIDENCE_MISSING")
        self.assertEqual(s.halt().state, S.TERMINAL_HALT)
        self.assertEqual(s.advance("COMMIT_WITNESS_GENESIS", evidence(S.BY_ACTION["COMMIT_WITNESS_GENESIS"])).reason,
                         "BOOTSTRAP_HALTED")
        self.assertEqual(s.reset().reason, "REBOOTSTRAP_FORBIDDEN")

    def test_evidence_must_be_literally_true(self):
        s = S.BootstrapSequencerV1()
        run_until(s, "GENERATE_K_WIT")
        for bad in (False, None, 1, "true"):
            result = s.advance("GENERATE_K_WIT", evidence(S.BY_ACTION["GENERATE_K_WIT"], secretScansClean=bad))
            self.assertEqual((result.reason, result.detail), ("EVIDENCE_MISSING", "secretScansClean"))
        self.assertEqual(s.state, "K_ROOT_GENERATED")


class FreshnessGateTests(unittest.TestCase):
    def test_no_blanket_bootstrap_bypass(self):
        self.assertTrue(all(step.gate in S.GATE_CATEGORIES for step in S.STEPS))
        special = [step.action for step in S.STEPS if step.gate == S.BOOTSTRAP_SPECIAL_CASE]
        self.assertEqual(special, ["COMMIT_WITNESS_GENESIS", "APPEND_RECORD_1_REPLICA_A", "APPEND_RECORD_1_REPLICA_B"])
        for step in S.STEPS:
            if step.gate == S.BOOTSTRAP_SPECIAL_CASE:
                self.assertTrue(step.special_case_justification, step.action)
            else:
                self.assertIsNone(step.special_case_justification, step.action)
        after = [step for step in S.STEPS][[s.action for s in S.STEPS].index("APPEND_RECORD_1_REPLICA_B") + 1:]
        self.assertTrue(after)
        self.assertEqual({step.gate for step in after}, {S.REQUIRED_CURRENT})
        before = S.STEPS[:[s.action for s in S.STEPS].index("COMMIT_WITNESS_GENESIS")]
        self.assertEqual({step.gate for step in before}, {S.NOT_APPLICABLE_PRE_GENESIS, S.REQUIRED_UNKNOWN_BLOCK})
        host_writes = {"GENERATE_K_WIT", "INSTALL_TRUST_AND_REGISTRY", "PROVISION_LEDGER", "PIN_GENESIS",
                       "START_WITNESS"}
        self.assertEqual({s.action for s in before if s.gate == S.REQUIRED_UNKNOWN_BLOCK}, host_writes)

    def test_special_cases_still_require_known_empty_register_and_pin(self):
        s = S.BootstrapSequencerV1()
        run_until(s, "COMMIT_WITNESS_GENESIS")
        for register in (None, OF.OwnerRegisterResultV1(OF.REGISTER_NOT_VERIFIED, "REPLICA_QUORUM_UNMET"),
                         OF.OwnerRegisterResultV1(OF.REGISTER_NOT_VERIFIED, "REPLICAS_DIVERGENT"),
                         OF.OwnerRegisterResultV1(OF.REGISTER_VERIFIED)):
            result = s.advance("COMMIT_WITNESS_GENESIS",
                               evidence(S.BY_ACTION["COMMIT_WITNESS_GENESIS"], ownerRegister=register))
            self.assertEqual(result.reason, "OWNER_REGISTER_NOT_KNOWN_EMPTY")
        no_pin = s.advance("COMMIT_WITNESS_GENESIS",
                           evidence(S.BY_ACTION["COMMIT_WITNESS_GENESIS"], pinEqualsCandidateDigest=False))
        self.assertEqual(no_pin.reason, "EVIDENCE_MISSING")

    def test_no_authority_changing_operation_during_partial_acceptance(self):
        s = S.BootstrapSequencerV1()
        run_until(s, "APPEND_RECORD_1_REPLICA_B")
        self.assertEqual(s.state, S.PARTIAL_STATE)
        unknown = OF.FreshnessResultV1(OF.AUTHENTIC, OF.FRESHNESS_UNKNOWN, "OWNER_REGISTER_NOT_VERIFIED")
        for action in ("WRITE_HELD", "START_SIGNER", "WRITE_RELEASED", "EVALUATE_FULL_READINESS"):
            self.assertFalse(s.advance(action, evidence(S.BY_ACTION[action], freshness=unknown)).advanced)
        self.assertFalse(S.authority_changing_permitted(s.state, CURRENT))
        completing = s.advance("APPEND_RECORD_1_REPLICA_B",
                               evidence(S.BY_ACTION["APPEND_RECORD_1_REPLICA_B"], freshness=unknown))
        self.assertEqual((completing.reason, completing.detail), ("FRESHNESS_NOT_CURRENT", "AUTHENTIC:FRESHNESS_UNKNOWN"))
        for operation in OF.GATED_OPERATIONS:
            self.assertFalse(OF.freshness_gate(unknown, operation).met)

    def test_no_released_before_current(self):
        s = S.BootstrapSequencerV1()
        run_until(s, "WRITE_RELEASED")
        for state in (OF.STALE, OF.AHEAD_UNACCEPTED, OF.CONFLICTING, OF.FRESHNESS_UNKNOWN, OF.REFUSED):
            result = s.advance("WRITE_RELEASED",
                               evidence(S.BY_ACTION["WRITE_RELEASED"], freshness=OF.FreshnessResultV1(OF.AUTHENTIC, state)))
            self.assertEqual(result.reason, "FRESHNESS_NOT_CURRENT", state)
        not_authentic = OF.FreshnessResultV1(OF.NOT_AUTHENTIC, OF.CURRENT)
        self.assertEqual(s.advance("WRITE_RELEASED", evidence(S.BY_ACTION["WRITE_RELEASED"],
                                                             freshness=not_authentic)).reason, "FRESHNESS_NOT_CURRENT")
        self.assertEqual(s.advance("WRITE_RELEASED", evidence(S.BY_ACTION["WRITE_RELEASED"], freshness=True)).reason,
                         "FRESHNESS_NOT_CURRENT")                        # a boolean is not freshness
        self.assertEqual(s.state, "OWNER_ACCEPTANCE_COMPLETE")
        self.assertTrue(s.advance("WRITE_RELEASED", evidence(S.BY_ACTION["WRITE_RELEASED"])).advanced)


class CrashAndFirstMemoryTests(unittest.TestCase):
    def test_crash_state_recovery_classifications(self):
        self.assertTrue(all(cls in S.CRASH_CLASSES for _, cls, _ in S.CRASH_MATRIX.values()))
        self.assertTrue(all(state in S.STATES for state, _, _ in S.CRASH_MATRIX.values()))
        by_prefix = {key.split(" ")[0]: cls for key, (_, cls, _) in S.CRASH_MATRIX.items()}
        expected = {"C-3": S.MANUAL_RECOVERY_REQUIRED, "C-4": S.KNOWN_CUSTODY_DEBT, "C-5": S.RECOVERABLE_INCOMPLETE,
                    "C-11": S.SAFE_RETRY, "C-12": S.REBOOTSTRAP_FORBIDDEN, "C-13": S.RECOVERABLE_INCOMPLETE,
                    "C-14": S.RECOVERABLE_INCOMPLETE, "C-15": S.MANUAL_RECOVERY_REQUIRED, "C-16": S.SAFE_RETRY,
                    "C-17": S.RECOVERABLE_INCOMPLETE, "C-18": S.SAFE_RETRY, "C-19": S.MANUAL_RECOVERY_REQUIRED}
        for prefix, cls in expected.items():
            self.assertEqual(by_prefix[prefix], cls, prefix)
        self.assertEqual(set(by_prefix.values()), S.CRASH_CLASSES)

    def test_first_memory_still_blocked_at_full_readiness(self):
        s = S.BootstrapSequencerV1()
        run_until(s, None)
        self.assertEqual(S.first_memory_gate(s.state, freshness=CURRENT, a1_a7_accepted=False,
                                             owner_accepted_proofs=False), (S.FIRST_MEMORY_BLOCKED, "A1_A7_REQUIRED"))
        self.assertEqual(S.first_memory_gate(s.state, freshness=CURRENT, a1_a7_accepted=True,
                                             owner_accepted_proofs=False)[1], "OWNER_ACCEPTANCE_OF_A1_A7_REQUIRED")
        self.assertEqual(S.first_memory_gate("INITIAL_CUSTODY_RELEASED", freshness=CURRENT, a1_a7_accepted=True,
                                             owner_accepted_proofs=True)[1], "FULL_READINESS_REQUIRED")
        stale = OF.FreshnessResultV1(OF.AUTHENTIC, OF.STALE)
        self.assertEqual(S.first_memory_gate(s.state, freshness=stale, a1_a7_accepted=True,
                                             owner_accepted_proofs=True)[1], "FRESHNESS_NOT_CURRENT")
        best = S.first_memory_gate(s.state, freshness=CURRENT, a1_a7_accepted=True, owner_accepted_proofs=True)
        self.assertEqual(best, (S.FIRST_MEMORY_REVIEW_ELIGIBLE, None))     # never an authorization
        self.assertNotIn("AUTHORIZED", best[0])


class SyntheticEndToEndTests(unittest.TestCase):
    """The record-1 steps driven by the real P3-2 tool over temporary replicas."""

    def test_record_1_ceremony_inside_the_sequence(self):
        w, scenario = P32.Workstation(self), F.Scenario()
        pin = w.pin(P32._genesis_digest(scenario.writer.chain))
        chain = w.chain(scenario.writer.chain)
        trust = T.load_trust(w.trust)

        def register():
            return T.load_register([w.a, w.b])[0]

        def freshness():
            return OF.classify_presented_world(register=register(), chain=T.verify_chain(trust, chain, F.ENV),
                                               environment=F.ENV, authority_profile="TEST_ONLY")

        s = S.BootstrapSequencerV1()
        run_until(s, "COMMIT_WITNESS_GENESIS")
        self.assertEqual(S.owner_register_state(register()), S.KNOWN_EMPTY)
        self.assertTrue(s.advance("COMMIT_WITNESS_GENESIS", evidence(S.BY_ACTION["COMMIT_WITNESS_GENESIS"],
                                                                     ownerRegister=register())).advanced)
        code, proposed, candidate = w.propose("genesis", chain, pin)
        first = w.append(w.a, w.b, candidate, chain, pin, proposed["recordDigest"])
        self.assertEqual(first[1]["replication"], "PEER_PENDING")
        # after the first append the register is no longer KNOWN_EMPTY (one copy ahead)
        self.assertEqual(register().reason, "REPLICAS_DIVERGENT")
        self.assertEqual(S.owner_register_state(register()), S.REGISTER_UNKNOWN)
        self.assertTrue(s.advance("APPEND_RECORD_1_REPLICA_A", evidence(S.BY_ACTION["APPEND_RECORD_1_REPLICA_A"],
                                                                        ownerRegister=EMPTY)).advanced)
        partial = freshness()
        self.assertEqual(partial.freshness, OF.FRESHNESS_UNKNOWN)
        self.assertFalse(s.advance("APPEND_RECORD_1_REPLICA_B", evidence(S.BY_ACTION["APPEND_RECORD_1_REPLICA_B"],
                                                                         freshness=partial)).advanced)
        w.append(w.b, w.a, candidate, chain, pin, proposed["recordDigest"])
        current = freshness()
        self.assertTrue(current.current)
        self.assertTrue(s.advance("APPEND_RECORD_1_REPLICA_B", evidence(S.BY_ACTION["APPEND_RECORD_1_REPLICA_B"],
                                                                        freshness=current)).advanced)
        for step in S.STEPS[[x.action for x in S.STEPS].index("WRITE_HELD"):]:
            self.assertTrue(s.advance(step.action, evidence(step, freshness=freshness())).advanced, step.action)
        self.assertEqual(s.state, "FULL_READINESS")

    def test_mixed_empty_replicas_are_divergent_not_empty(self):
        w, scenario = P32.Workstation(self), F.Scenario()
        pin = w.pin(P32._genesis_digest(scenario.writer.chain))
        chain = w.chain(scenario.writer.chain)
        _, proposed, candidate = w.propose("genesis", chain, pin)
        w.append(w.a, w.b, candidate, chain, pin, proposed["recordDigest"])
        for order in ([w.a, w.b], [w.b, w.a]):
            result = T.load_register(order)[0]
            self.assertEqual(result.reason, "REPLICAS_DIVERGENT", order)
        self.assertEqual(T.load_register([w.b])[0].reason, "REPLICA_QUORUM_UNMET")   # one empty copy is not "empty"

    def test_design_record_names_the_gates(self):
        text = RECORD.read_text(encoding="utf-8")
        for line in ("PR1B_NOT_ELIGIBLE", "BOOTSTRAP_SPECIAL_CASE", "PREPARED", "PINNED", "COMMITTED",
                     "SIGNED_REGISTRY != EFFECTIVE_CURRENT_REGISTRY", "P3_3_STORAGE_INCOMPLETE",
                     "PR2_REVALIDATION_REQUIRED", "If every final artifact is valid"):
            self.assertIn(line, text, line)
        for step in S.STEPS:
            self.assertIn(step.action, text, step.action)


if __name__ == "__main__":
    unittest.main()
