"""15B2b-B1b-3e PR-3: owner / off-host freshness foundation (TEST-ONLY, offline).

Record: docs/architecture/slice-15b2b-b1b3e-pr3-owner-offhost-foundation.md.

Every witness chain here is a real K-WIT-signed TEST chain from the B1b-3e
synthetic scenario, verified from genesis. No key, file, network, DEV host,
or owner register is touched.
"""

from __future__ import annotations

import ast
import copy
import json
import unittest

import synthetic_authority as SA  # noqa: F401  (sets sys.path)
import synthetic_b1b3e as F
from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import owner_freshness as OF
from lilith_owner_memory import recovery_contracts as R
from lilith_owner_memory import rotation_contracts as RC

ROOT = SA.ROOT
MODULE = ROOT / "services/owner-memory-control/lilith_owner_memory/owner_freshness.py"
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-pr3-owner-offhost-foundation.md"
ENV, PROFILE = F.ENV, "TEST_ONLY"


def verify(chain) -> RC.ChainResultV1:
    return RC.verify_witness_v2_chain(anchor=F.anchor(), chain=list(chain), environment=ENV, registry_root=F.root(),
                                      authority_public_keys=RC._authority_keys(F.v3(), F.v4(), F.v5()))


def ledger_step(s: F.Scenario, challenge_id: str) -> None:
    lep = R.ledger_epoch_id(F.E2, ENV)
    s.commit(lambda st: st.prepare(challenge_id, lep, ready=F.seeded_ready(st)))


class Owner:
    """The owner side of the test: an append-only list of accepted records,
    written only through proposals the owner 'reviews' (here: asserts)."""

    def __init__(self, chain):
        candidate = OF.propose_genesis_record(chain=verify(chain[:1]), environment=ENV, authority_profile=PROFILE)
        assert candidate.proposed, candidate
        self.records = [dict(candidate.record)]

    def register(self, copies: int = 2) -> OF.OwnerRegisterResultV1:
        return OF.reconcile_owner_replicas([copy.deepcopy(self.records) for _ in range(copies)])

    def accept(self, chain) -> dict:
        candidate = OF.propose_acceptance(register=self.register(), chain=verify(chain), environment=ENV,
                                          authority_profile=PROFILE)
        assert candidate.proposed, candidate
        self.records.append(dict(candidate.record))
        return candidate.record

    def reject(self, chain) -> dict:
        candidate = OF.propose_rejection(register=self.register(), chain=verify(chain), environment=ENV,
                                         authority_profile=PROFILE)
        assert candidate.proposed, candidate
        self.records.append(dict(candidate.record))
        return candidate.record

    def classify(self, chain, **kwargs) -> OF.FreshnessResultV1:
        register = kwargs.pop("register", None) or self.register()
        return OF.classify_presented_world(register=register, chain=verify(chain), environment=kwargs.pop(
            "environment", ENV), authority_profile=kwargs.pop("authority_profile", PROFILE))


def rehash(records: list[dict]) -> list[dict]:
    """Re-link a hand-edited register so only the edited rule is under test."""
    previous = None
    for record in records:
        record["previousRecordDigest"] = previous
        previous = OF.record_digest(record)
    return records


class RegisterContractTests(unittest.TestCase):
    def setUp(self):
        self.s = F.Scenario()                             # W1: genesis at v3
        self.owner = Owner(self.s.writer.chain)

    def test_01_genesis_register_validates(self):
        result = OF.verify_owner_register(self.owner.records)
        self.assertTrue(result.verified, result)
        record = result.facts.latest
        genesis = RC.RecoveryWitnessV2.from_verified_dict(self.s.writer.chain[0])
        self.assertEqual((record.record_version, record.previous_record_digest, record.decision), (1, None, OF.ACCEPT_CURRENT))
        self.assertEqual(record.witness_digest, genesis.digest)
        self.assertEqual(record.genesis_witness_digest, genesis.digest)
        self.assertTrue(record.matches(genesis))
        self.assertEqual(set(self.owner.records[0]), OF.RECORD_FIELDS)
        self.assertEqual(self.owner.classify(self.s.writer.chain).freshness, OF.CURRENT)

    def test_02_valid_monotonic_successor(self):
        self.s.to_current()                               # W2 head advance to v4, W3 ledger advance
        chain = self.s.writer.chain
        self.assertEqual(self.owner.classify(chain).freshness, OF.AHEAD_UNACCEPTED)
        record = self.owner.accept(chain)
        self.assertEqual(record["recordVersion"], 2)
        self.assertEqual(record["previousRecordDigest"], OF.record_digest(self.owner.records[0]))
        self.assertEqual(record["registryVersion"], 4)
        result = self.owner.classify(chain)
        self.assertEqual((result.authenticity, result.freshness), (OF.AUTHENTIC, OF.CURRENT))
        self.assertTrue(result.current)

    def test_07_broken_previous_record_digest_chain(self):
        self.s.to_current()
        self.owner.accept(self.s.writer.chain)
        broken = copy.deepcopy(self.owner.records)
        broken[1]["previousRecordDigest"] = F.digest("not the previous record")
        self.assertEqual(OF.verify_owner_register(broken).reason, "PREVIOUS_RECORD_DIGEST_MISMATCH")
        gap = copy.deepcopy(self.owner.records)
        gap[1]["recordVersion"] = 3
        self.assertEqual(OF.verify_owner_register(gap).reason, "RECORD_VERSION_NOT_SUCCESSOR")
        edited = copy.deepcopy(self.owner.records)
        edited[1]["registryVersion"] = 5                  # the latest record edited in place
        self.assertTrue(OF.verify_owner_register(edited).verified)   # links only point backwards
        # so an edited latest record is caught against the witness it names, not by the chain
        result = self.owner.classify(self.s.writer.chain, register=OF.reconcile_owner_replicas([edited, edited]))
        self.assertEqual((result.freshness, result.reason), (OF.FRESHNESS_UNKNOWN, "OWNER_RECORD_INCONSISTENT"))
        truncated = OF.reconcile_owner_replicas([self.owner.records[:1], self.owner.records])
        self.assertEqual(truncated.reason, "REPLICAS_DIVERGENT")

    def test_13_malformed_canonical_encoding_rejected(self):
        record = self.owner.records[0]
        canonical = OF.record_bytes(record)
        self.assertTrue(OF.verify_owner_register([canonical]).verified)
        pretty = json.dumps(record, indent=1).encode()
        self.assertEqual(OF.verify_owner_register([pretty]).reason, "RECORD_MALFORMED")
        duplicate = canonical[:-1] + b',"recordType":"LILITH_OWNER_FRESHNESS_RECORD"}'
        self.assertEqual(OF.verify_owner_register([duplicate]).reason, "RECORD_MALFORMED")
        for mutate in (lambda r: r.update(extra=1), lambda r: r.pop("registryDigest"),
                       lambda r: r.update(schemaVersion=2), lambda r: r.update(schemaVersion=True),
                       lambda r: r.update(recordType="LILITH_OWNER_AUTHORIZATION_REGISTER"),
                       lambda r: r.update(decision="ACCEPT"), lambda r: r.update(witnessVersion=0),
                       lambda r: r.update(previousRecordDigest=F.digest("x")),
                       lambda r: r.update(decision=OF.REJECT_CANDIDATE),
                       lambda r: r.update(witnessDigest=F.digest("not genesis"))):
            bad = copy.deepcopy(record)
            mutate(bad)
            self.assertEqual(OF.verify_owner_register([bad]).reason, "RECORD_MALFORMED", bad)
        self.assertEqual(OF.verify_owner_register("not a list").reason, "RECORD_MALFORMED")
        self.assertEqual(OF.verify_owner_register([]).reason, "OWNER_REGISTER_EMPTY")

    def test_record_digest_is_domain_separated_and_deterministic(self):
        record = self.owner.records[0]
        import hashlib
        expected = hashlib.sha256(b"LILITH_OWNER_FRESHNESS_RECORD_V1\x00" + OF.record_bytes(record)).hexdigest()
        self.assertEqual(OF.record_digest(record), expected)
        self.assertEqual(OF.record_digest(copy.deepcopy(record)), expected)
        self.assertEqual(OF.verify_owner_register([record]).facts.head_digest, expected)
        again = Owner(F.Scenario().writer.chain).records[0]
        self.assertEqual(OF.record_digest(again), expected)

    def test_register_monotonicity_rules(self):
        self.s.to_current()
        self.owner.accept(self.s.writer.chain)
        cases = {
            "ACCEPTED_REGISTRY_REGRESSION": {"registryVersion": 2},
            "ACCEPTED_REGISTRY_DIGEST_CONFLICT": {"registryVersion": 3, "registryDigest": F.digest("other v3")},
            "ACCEPTED_EPOCH_REGRESSION": {"recoveryEpoch": A.RecoveryEpochV1(1, F.E2.random).to_dict()},
            "ACCEPTED_EPOCH_FORKED": {"recoveryEpoch": A.RecoveryEpochV1(F.E2.counter, F.E3.random).to_dict()},
            "REGISTER_GENESIS_CHANGED": {"genesisWitnessDigest": F.digest("other genesis")},
            "WITNESS_DECIDED_TWICE": {"witnessVersion": 1, "witnessDigest": self.owner.records[0]["witnessDigest"]},
        }
        for reason, changes in cases.items():
            records = copy.deepcopy(self.owner.records)
            records[1].update(changes)
            self.assertEqual(OF.verify_owner_register(rehash(records)).reason, reason, reason)
        behind = copy.deepcopy(self.owner.records)
        behind.append({**behind[1], "witnessVersion": 2, "witnessDigest": F.digest("older"), "recordVersion": 3})
        self.assertEqual(OF.verify_owner_register(rehash(behind)).reason, "ACCEPTED_WITNESS_NOT_ADVANCING")

    def test_genesis_pin_consistency(self):
        register = self.owner.register()
        pin = {"pinType": "LILITH_RECOVERY_WITNESS_V2_GENESIS_PIN", "schemaVersion": 1, "environment": ENV,
               "genesisWitnessDigest": self.owner.records[0]["genesisWitnessDigest"]}
        self.assertTrue(OF.genesis_pin_consistent(register, pin))
        self.assertFalse(OF.genesis_pin_consistent(register, {**pin, "genesisWitnessDigest": F.digest("x")}))
        self.assertFalse(OF.genesis_pin_consistent(register, {**pin, "environment": "dev"}))
        self.assertFalse(OF.genesis_pin_consistent(OF.reconcile_owner_replicas(None), pin))


class FreshnessClassificationTests(unittest.TestCase):
    def test_03_registry_regression_is_stale(self):
        s = F.Scenario()
        owner = Owner(s.writer.chain)
        ledger_step(s, "c3")                              # W2: ledger only, still v3
        before_head_advance = s.writer.chain
        s.to_current()                                    # W3 head advance to v4, W4 ledger
        owner.accept(s.writer.chain)
        result = owner.classify(before_head_advance)
        self.assertEqual((result.authenticity, result.freshness, result.reason),
                         (OF.AUTHENTIC, OF.STALE, "REGISTRY_REGRESSION"))

    def test_04_recovery_epoch_regression_is_stale(self):
        s = F.Scenario().to_current()                     # W1..W3 at epoch 2
        owner = Owner(s.writer.chain)
        before_epoch = s.writer.chain
        s.epoch_advance()                                 # epoch 3, registry v5
        owner.accept(s.writer.chain)
        result = owner.classify(before_epoch)
        self.assertEqual((result.freshness, result.reason), (OF.STALE, "RECOVERY_EPOCH_REGRESSION"))

    def test_06_witness_sequence_regression_is_stale(self):
        s = F.Scenario().to_current()                     # W2 head advance (v4), W3 ledger (v4)
        owner = Owner(s.writer.chain)
        owner.accept(s.writer.chain)
        result = owner.classify(s.writer.chain[:2])
        self.assertEqual((result.freshness, result.reason), (OF.STALE, "WITNESS_SEQUENCE_REGRESSION"))

    def test_09_dev_older_than_owner_is_authentic_and_stale(self):
        s = F.Scenario()
        owner = Owner(s.writer.chain)
        snapshot = s.writer.chain                         # "disk snapshot" at T
        s.to_current()
        owner.accept(s.writer.chain)
        restored = owner.classify(snapshot)               # DEV restored to T
        self.assertEqual((restored.authenticity, restored.freshness, restored.reason),
                         (OF.AUTHENTIC, OF.STALE, "EARLIER_ACCEPTED_STATE"))
        self.assertFalse(restored.current)
        self.assertTrue(verify(snapshot).verified)        # still cryptographically valid
        self.assertEqual(restored.facts["ownerLatestWitnessVersion"], 3)

    def test_10_exact_match_is_current(self):
        s = F.Scenario().to_current()
        owner = Owner(s.writer.chain)
        owner.accept(s.writer.chain)
        self.assertTrue(owner.classify(s.writer.chain).current)

    def test_11_dev_ahead_is_unaccepted(self):
        s = F.Scenario()
        owner = Owner(s.writer.chain)
        ledger_step(s, "c3")
        ledger_step(s, "c4")
        ahead = owner.classify(s.writer.chain)
        self.assertEqual((ahead.freshness, ahead.reason, ahead.detail), (OF.AHEAD_UNACCEPTED, "AHEAD_LEDGER_ONLY", "2"))
        s.to_current()
        changing = owner.classify(s.writer.chain)
        self.assertEqual((changing.freshness, changing.reason), (OF.AHEAD_UNACCEPTED, "AHEAD_AUTHORITY_CHANGING"))

    def test_05_same_version_different_digest_conflicts(self):
        a, b = F.Scenario(), F.Scenario()
        self.assertEqual(a.writer.chain[0], b.writer.chain[0])       # one shared genesis
        owner = Owner(a.writer.chain)
        a.to_current()                                    # W2 = head advance
        ledger_step(b, "c3")                              # W2' = ledger only
        owner.accept(a.writer.chain[:2])
        result = owner.classify(b.writer.chain)
        self.assertEqual((result.authenticity, result.freshness, result.reason),
                         (OF.AUTHENTIC, OF.CONFLICTING, "SAME_VERSION_DIGEST_MISMATCH"))

    def test_12_competing_successors_conflict(self):
        a, b = F.Scenario(), F.Scenario()
        owner = Owner(a.writer.chain)
        a.to_current()
        ledger_step(b, "c3")
        ledger_step(b, "c4")
        ledger_step(b, "c5")
        owner.accept(a.writer.chain[:2])                  # owner accepted branch A at W2
        forked = owner.classify(b.writer.chain)           # branch B is longer, also from W1
        self.assertEqual((forked.freshness, forked.reason, forked.detail),
                         (OF.CONFLICTING, "FORKED_FROM_ACCEPTED_HISTORY", "2"))
        self.assertFalse(OF.propose_acceptance(register=owner.register(), chain=verify(b.writer.chain),
                                               environment=ENV, authority_profile=PROFILE).proposed)
        # two owner copies that accepted different successors never resolve by length or last write
        other = Owner(a.writer.chain[:1])
        other.accept(b.writer.chain[:2])
        divergent = OF.reconcile_owner_replicas([owner.records, other.records])
        self.assertEqual((divergent.reason, divergent.detail), ("REPLICAS_DIVERGENT", "replica1:FORK"))
        self.assertEqual(owner.classify(a.writer.chain, register=divergent).freshness, OF.FRESHNESS_UNKNOWN)

    def test_replica_behind_or_ahead_is_divergent_not_latest(self):
        s = F.Scenario()
        owner = Owner(s.writer.chain)
        old_copy = copy.deepcopy(owner.records)           # owner workstation rolled back
        s.to_current()
        owner.accept(s.writer.chain)
        for replicas in ([owner.records, old_copy], [old_copy, owner.records]):
            result = OF.reconcile_owner_replicas(replicas)
            self.assertEqual((result.reason, result.detail[-6:]), ("REPLICAS_DIVERGENT", "PREFIX"))
        self.assertTrue(OF.reconcile_owner_replicas([owner.records, owner.records]).verified)
        # both copies rolled back together: NOT detected (documented limit)
        together = OF.reconcile_owner_replicas([old_copy, old_copy])
        self.assertTrue(together.verified)
        self.assertEqual(owner.classify(s.writer.chain[:1], register=together).freshness, OF.CURRENT)

    def test_08_missing_register_is_freshness_unknown(self):
        s = F.Scenario().to_current()
        owner = Owner(s.writer.chain)
        owner.accept(s.writer.chain)
        for register, reason in ((OF.reconcile_owner_replicas(None), "OWNER_REGISTER_UNAVAILABLE"),
                                 (OF.reconcile_owner_replicas([]), "OWNER_REGISTER_UNAVAILABLE"),
                                 (OF.reconcile_owner_replicas([owner.records]), "REPLICA_QUORUM_UNMET")):
            result = owner.classify(s.writer.chain, register=register)
            self.assertEqual((result.authenticity, result.freshness, result.reason),
                             (OF.AUTHENTIC, OF.FRESHNESS_UNKNOWN, "OWNER_REGISTER_NOT_VERIFIED"))
            self.assertTrue(result.detail.startswith(reason), result.detail)
            for operation in OF.GATED_OPERATIONS:
                self.assertFalse(OF.freshness_gate(result, operation).met, operation)

    def test_presented_world_not_authentic(self):
        s = F.Scenario().to_current()
        owner = Owner(s.writer.chain)
        owner.accept(s.writer.chain)
        tampered = [dict(w) for w in s.writer.chain]
        tampered[-1]["ledgerSequence"] += 1               # signature no longer verifies
        chain = verify(tampered)
        self.assertFalse(chain.verified)
        result = OF.classify_presented_world(register=owner.register(), chain=chain, environment=ENV,
                                             authority_profile=PROFILE)
        self.assertEqual((result.authenticity, result.freshness, result.reason),
                         (OF.NOT_AUTHENTIC, OF.FRESHNESS_UNKNOWN, "PRESENTED_NOT_AUTHENTIC"))
        rogue = F.Scenario(writer=F.witness_writer("rogue-witness"))
        self.assertFalse(verify(rogue.writer.chain).verified)

    def test_genesis_mismatch_conflicts(self):
        s = F.Scenario()
        owner = Owner(s.writer.chain)
        other = F.Scenario()
        other.ticks = 50                                  # a different genesis
        other.writer.restore_chain(())
        other.writer.genesis(registry=F.v3(), registry_root=F.root(), ledger=other.ledger, updated_at=other.tick())
        result = owner.classify(other.writer.chain)
        self.assertEqual((result.freshness, result.reason), (OF.CONFLICTING, "GENESIS_MISMATCH"))


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.s = F.Scenario()
        self.owner = Owner(self.s.writer.chain)

    def test_14_environment_mismatch_rejected(self):
        dev = copy.deepcopy(self.owner.records[0])
        dev["environment"] = "dev"                        # TEST_ONLY admits only test
        self.assertEqual(OF.verify_owner_register([dev]).reason, "RECORD_MALFORMED")
        result = self.owner.classify(self.s.writer.chain, environment="dev", authority_profile="DEV_SYNTHETIC")
        self.assertEqual((result.freshness, result.reason), (OF.REFUSED, "ENVIRONMENT_MISMATCH"))
        mismatch = self.owner.classify(self.s.writer.chain, environment="dev")
        self.assertEqual((mismatch.freshness, mismatch.reason), (OF.REFUSED, "PROFILE_MISMATCH"))

    def test_15_test_and_dev_synthetic_isolation(self):
        dev_record = copy.deepcopy(self.owner.records[0])
        dev_record.update(environment="dev", authorityProfile="DEV_SYNTHETIC")
        dev_register = OF.reconcile_owner_replicas([[dev_record], [dev_record]])
        self.assertTrue(dev_register.verified)
        crossed = OF.classify_presented_world(register=dev_register, chain=verify(self.s.writer.chain),
                                              environment=ENV, authority_profile=PROFILE)
        self.assertEqual((crossed.freshness, crossed.reason), (OF.REFUSED, "ENVIRONMENT_MISMATCH"))
        self.assertNotEqual(OF.record_digest(dev_record), OF.record_digest(self.owner.records[0]))
        for profile in ("PROD", "prod", "DEV", None):
            bad = copy.deepcopy(self.owner.records[0])
            bad["authorityProfile"] = profile
            self.assertEqual(OF.verify_owner_register([bad]).reason, "RECORD_MALFORMED", profile)
            self.assertEqual(self.owner.classify(self.s.writer.chain, authority_profile=profile).freshness, OF.REFUSED)
        mixed = [copy.deepcopy(self.owner.records[0])]
        self.s.to_current()
        self.owner.accept(self.s.writer.chain)
        mixed.append(copy.deepcopy(self.owner.records[1]))
        mixed[1].update(environment="dev", authorityProfile="DEV_SYNTHETIC")
        self.assertEqual(OF.verify_owner_register(rehash(mixed)).reason, "REGISTER_ENVIRONMENT_CHANGED")
        self.assertEqual(OF.PROFILE_ENVIRONMENTS, {"TEST_ONLY": "test", "DEV_SYNTHETIC": "dev"})


class GateAndProposalTests(unittest.TestCase):
    def test_gate_requires_exactly_current(self):
        s = F.Scenario()
        owner = Owner(s.writer.chain)
        current = owner.classify(s.writer.chain)
        for operation in OF.GATED_OPERATIONS:
            gate = OF.freshness_gate(current, operation)
            self.assertEqual((gate.status, gate.operation), (OF.FRESHNESS_PRECONDITION_MET, operation))
        ledger_step(s, "c3")
        ahead = owner.classify(s.writer.chain)
        self.assertEqual(ahead.reason, "AHEAD_LEDGER_ONLY")
        for operation in OF.GATED_OPERATIONS:
            self.assertEqual(OF.freshness_gate(ahead, operation).reason, "AUTHENTIC:AHEAD_UNACCEPTED")
        self.assertEqual(OF.freshness_gate(current, "ISSUE_EVIDENCE").reason, "UNKNOWN_OPERATION")
        self.assertEqual(OF.freshness_gate(None, OF.FIRST_MEMORY).reason, "MALFORMED_INPUT")
        self.assertEqual(OF.GATED_OPERATIONS, {"REGISTRY_HEAD_ADVANCE", "RECOVERY_EPOCH_ADVANCE",
                                               "SUCCESSOR_READINESS", "INITIAL_CUSTODY_RELEASE",
                                               "AUTHORITY_CHANGING_ISSUANCE", "FIRST_MEMORY"})

    def test_owner_cannot_be_led_to_accept_a_stale_or_conflicting_world(self):
        s = F.Scenario()
        owner = Owner(s.writer.chain)
        snapshot = s.writer.chain
        s.to_current()
        owner.accept(s.writer.chain)
        for chain in (snapshot, s.writer.chain):          # stale; current
            candidate = OF.propose_acceptance(register=owner.register(), chain=verify(chain), environment=ENV,
                                              authority_profile=PROFILE)
            self.assertFalse(candidate.proposed, candidate)
        self.assertEqual(OF.propose_rejection(register=owner.register(), chain=verify(snapshot), environment=ENV,
                                              authority_profile=PROFILE).reason, "STALE:EARLIER_ACCEPTED_STATE")
        self.assertFalse(OF.propose_acceptance(register=OF.reconcile_owner_replicas(None), chain=verify(snapshot),
                                               environment=ENV, authority_profile=PROFILE).proposed)
        self.assertEqual(OF.propose_genesis_record(chain=verify(s.writer.chain), environment=ENV,
                                                   authority_profile=PROFILE).reason, "NOT_GENESIS")

    def test_rejection_is_terminal_and_poisons_the_lineage(self):
        s = F.Scenario()
        owner = Owner(s.writer.chain)
        s.to_current()
        record = owner.reject(s.writer.chain)             # owner declines this transition
        self.assertEqual(record["decision"], OF.REJECT_CANDIDATE)
        register = owner.register()
        self.assertEqual(register.facts.latest.record_version, 1)   # latest accepted is unchanged
        result = owner.classify(s.writer.chain)
        self.assertEqual((result.freshness, result.reason), (OF.CONFLICTING, "OWNER_REJECTED_LINEAGE"))
        ledger_step(s, "c3")                              # descendants of a rejected head stay refused
        self.assertEqual(owner.classify(s.writer.chain).reason, "OWNER_REJECTED_LINEAGE")
        self.assertFalse(OF.propose_acceptance(register=register, chain=verify(s.writer.chain), environment=ENV,
                                               authority_profile=PROFILE).proposed)
        late_accept = copy.deepcopy(owner.records)
        late_accept.append({**late_accept[1], "recordVersion": 3, "decision": OF.ACCEPT_CURRENT})
        self.assertEqual(OF.verify_owner_register(rehash(late_accept)).reason, "WITNESS_DECIDED_TWICE")
        self.assertTrue(owner.classify(s.writer.chain[:1]).current)  # the accepted world is still current

    def test_candidate_is_not_acceptance(self):
        s = F.Scenario()
        owner = Owner(s.writer.chain)
        s.to_current()
        candidate = OF.propose_acceptance(register=owner.register(), chain=verify(s.writer.chain), environment=ENV,
                                          authority_profile=PROFILE)
        self.assertTrue(candidate.proposed)
        self.assertEqual(candidate.record_digest, OF.record_digest(candidate.record))
        # proposing changed nothing: the owner has not appended it
        self.assertEqual(owner.classify(s.writer.chain).freshness, OF.AHEAD_UNACCEPTED)


class SourceBoundaryTests(unittest.TestCase):
    def test_module_is_pure_and_offline(self):
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
                    for alias in node.names}
        imported |= {node.module.split(".")[0] for node in ast.walk(tree)
                     if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module}
        self.assertTrue(imported <= {"__future__", "hashlib", "dataclasses", "typing", "lilith_memory"}, imported)
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        self.assertFalse(names & {"open", "eval", "exec", "__import__"})
        source = MODULE.read_text(encoding="utf-8")
        for forbidden in ("Ed25519PrivateKey", "generate", "sign(", "subprocess", "socket", "os.environ"):
            self.assertNotIn(forbidden, source, forbidden)

    def test_design_record_exists_with_canonical_lines(self):
        text = RECORD.read_text(encoding="utf-8")
        for line in ("OFF_HOST_OWNER_FRESHNESS_ANCHOR", "storage != acceptance", "signature validity != freshness",
                     "PR3-D1", "PR3-D10", "WHOLE-HOST ROLLBACK RESISTANCE = NOT ESTABLISHED"):
            self.assertIn(line, text, line)


if __name__ == "__main__":
    unittest.main()
