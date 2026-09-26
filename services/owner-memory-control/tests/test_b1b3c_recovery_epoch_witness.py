"""15B2b-B1b-3c recovery epoch / registry witness semantics (TEST-ONLY).

RESTORE != AUTHORITY RESTORATION. Old valid evidence is never permission for
a new post-recovery admission. Everything is synthetic, in-process, or in a
temporary directory; no DEV, PROD, broker, L04, Privacy DB, or live witness
is contacted.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import inspect
import json
import pickle
import re
import unittest
from pathlib import Path

import synthetic_authority as SA
import synthetic_b1b3b as T
import synthetic_b1b3c as F
import synthetic_chain as SC
from lilith_authority_signer import synthetic_broker as B
from lilith_authority_signer import synthetic_recovery_ledger as RL
from lilith_memory import canonical_contracts as C
from lilith_memory.owner_proof import OwnerProofError, _id
from lilith_owner_memory import admission_v2 as V2
from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import authority_verifier as AV
from lilith_owner_memory import contracts as K
from lilith_owner_memory import l04_v2_adapter as AD
from lilith_owner_memory import recovery_admission as RA
from lilith_owner_memory import recovery_contracts as R
from lilith_owner_memory import verifier as B2A

ROOT = SA.ROOT
PACKAGE = ROOT / "services/owner-memory-control/lilith_owner_memory"
SIGNER_PACKAGE = ROOT / "services/owner-memory-control/lilith_authority_signer"
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3c-recovery-epoch-witness.md"


def refusal(fn) -> str | None:
    try:
        fn()
    except RL.LedgerRefusal as refused:
        return refused.reason
    return None


# ------------------------------------------- 2. RecoveryEpochV1 canonical ---

class EpochCanonicalizationTests(unittest.TestCase):
    def test_recovery_epoch_shape_is_unchanged_counter_and_random(self):
        self.assertEqual({f.name for f in dataclasses.fields(A.RecoveryEpochV1)}, {"counter", "random"})
        self.assertEqual(F.E1, SA.EPOCH)

    def test_canonical_bytes_are_exact_rfc8785(self):
        self.assertEqual(R.epoch_canonical_bytes(F.E2),
                         ('{"counter":3,"random":"%s"}' % F.E2.random).encode("ascii"))
        self.assertEqual(R.epoch_canonical_bytes(A.RecoveryEpochV1.from_dict(F.E2.to_dict())),
                         R.epoch_canonical_bytes(F.E2))

    def test_digest_is_domain_separated_and_environment_bound(self):
        self.assertNotEqual(R.epoch_digest(F.E1, "test"), R.epoch_digest(F.E1, "dev"))
        self.assertNotEqual(R.ledger_epoch_id(F.E1, "test"), R.ledger_epoch_id(F.E1, "prod"))
        import hashlib
        plain = hashlib.sha256(R.epoch_canonical_bytes(F.E1)).hexdigest()
        self.assertNotEqual(R.epoch_digest(F.E1, "test"), plain)

    def test_ledger_epoch_id_is_a_valid_b1a_identifier(self):
        lep = R.ledger_epoch_id(F.E1, "test")
        self.assertTrue(lep.startswith(R.LEDGER_EPOCH_PREFIX))
        self.assertEqual(len(lep), 69)
        self.assertEqual(_id(lep, "ledger_epoch"), lep)

    def test_ordering_is_a_partial_order_with_forks(self):
        self.assertEqual(R.compare_epochs(F.E2, F.E2), R.EPOCH_EQUAL)
        self.assertEqual(R.compare_epochs(F.E2, F.E1), R.EPOCH_OLDER)
        self.assertEqual(R.compare_epochs(F.E2, F.E3), R.EPOCH_NEWER)
        self.assertEqual(R.compare_epochs(F.E2, F.E2_FORK), R.EPOCH_FORKED)
        self.assertEqual(R.compare_epochs(F.E2_FORK, F.E2), R.EPOCH_FORKED)

    def test_duplicate_counter_different_nonce_is_a_different_epoch(self):
        self.assertEqual(F.E2.counter, F.E2_FORK.counter)
        self.assertNotEqual(F.E2, F.E2_FORK)
        self.assertNotEqual(R.ledger_epoch_id(F.E2, "test"), R.ledger_epoch_id(F.E2_FORK, "test"))
        self.assertFalse(R.ledger_epoch_matches(R.ledger_epoch_id(F.E2_FORK, "test"), F.E2, "test"))

    def test_malformed_epochs_and_environments_are_rejected(self):
        for bad in (None, {"counter": 1, "random": F.E1.random}, A.RecoveryEpochV1(True, F.E1.random),
                    A.RecoveryEpochV1(1, "XYZ"), A.RecoveryEpochV1(-1, F.E1.random)):
            with self.subTest(bad=bad), self.assertRaises(OwnerProofError):
                R.epoch_digest(bad, "test")
        with self.assertRaises(OwnerProofError):
            R.epoch_digest(F.E1, "staging")

    def test_golden_vectors_are_frozen(self):
        committed = json.loads(F.GOLDEN_PATH.read_text(encoding="utf-8"))
        self.assertEqual(committed, json.loads(json.dumps(F.golden_document())))
        self.assertEqual(committed["epochs"]["E1"]["ledgerEpochTest"], F.LEP1)


# ------------------------------------------- 3. ledgerEpoch binding ---

class LedgerEpochBindingTests(unittest.TestCase):
    def setUp(self):
        self.l04 = T.L04Harness()
        self.addCleanup(self.l04.close)
        self.action, _ = self.l04.action("SYNTH-BIND")

    def verify(self, proof, *, ledger_epoch):
        record = {"schemaVersion": 1, "challengeId": proof.challenge["challengeId"], "state": "CONSUMED",
                  "consumedCredentialRecordId": proof.assertion["credentialRecordId"],
                  "consumedAt": "2026-09-26T12:00:20Z", "ledgerEpoch": proof.challenge["ledgerEpoch"]}
        return B2A.verify_owner_proof(context=T.owner_context(ledger_epoch=ledger_epoch), action=self.action,
                                      challenge_json=proof.challenge_json, challenge_record=record,
                                      assertion=proof.assertion, owner_credential=proof.credential)

    def test_challenge_ledger_epoch_is_derived_from_the_recovery_epoch(self):
        proof = T.owner_proof(self.action, "och.bind", ledgerEpoch=F.LEP1)
        self.assertTrue(R.ledger_epoch_matches(proof.challenge["ledgerEpoch"], F.E1, "test"))
        self.assertTrue(self.verify(proof, ledger_epoch=F.LEP1).verified)
        self.assertEqual(self.verify(proof, ledger_epoch=F.LEP2).reason, "LEDGER_EPOCH_MISMATCH")

    def test_legacy_opaque_ledger_epoch_is_bound_to_no_recovery_epoch(self):
        # B1b-3b fixtures use an opaque value; B1b-3c never treats it as current.
        for epoch in (F.E1, F.E2, F.E2_FORK):
            self.assertFalse(R.ledger_epoch_matches(SC.LEDGER_EPOCH, epoch, "test"))

    def test_witness_is_the_single_source_of_trusted_epoch_and_floor(self):
        host = F.Host()
        context = R.witness_authority_context(host.witness_view(), registry_root=SA.trusted_root(),
                                              purpose=A.NEW_ADMISSION)
        self.assertEqual(context, SA.context())
        self.assertEqual(host.witness_view().ledger_epoch, F.LEP1)
        with self.assertRaises(OwnerProofError):
            R.witness_authority_context("not a witness", registry_root=SA.trusted_root(), purpose=A.NEW_ADMISSION)


# ------------------------------------------- 8. witness contract ---

class WitnessContractTests(unittest.TestCase):
    def setUp(self):
        self.host = F.Host()

    def verify(self, witness=None, *, anchor=None, environment="test", authority_keys=frozenset(),
               root=None):
        return R.verify_recovery_witness(anchor=anchor or F.anchor(),
                                         witness=self.host.witness if witness is None else witness,
                                         environment=environment, registry_root=root or SA.trusted_root(),
                                         authority_public_keys=authority_keys)

    def test_valid_witness_verifies_and_exposes_only_freshness_state(self):
        result = self.verify()
        self.assertTrue(result.verified, result)
        w = result.witness
        self.assertEqual((w.witness_version, w.previous_witness_digest, w.current_recovery_epoch,
                          w.minimum_registry_version, w.policy_version, w.ledger_sequence),
                         (1, None, F.E1, 3, SA.POLICY, 1))
        # A witness carries no authority fields at all.
        for authority_field in ("keyId", "signingDomain", "evidenceType", "actionDigest", "challengeId",
                                "authorityDomain", "logicalOwnerId", "keys"):
            self.assertNotIn(authority_field, R.WITNESS_FIELDS)

    def test_witness_negative_matrix(self):
        w = self.host.witness
        tampered = {**w, "minimumRegistryVersion": 2}
        cases = [
            ("missing", dict(witness=None), "WITNESS_MISSING"),
            ("not-a-mapping", dict(witness=["x"]), "WITNESS_MALFORMED"),
            ("unsigned", dict(witness={**w, "signature": None}), "WITNESS_UNSIGNED"),
            ("extra-field", dict(witness={**w, "extra": 1}), "WITNESS_MALFORMED"),
            ("bad-signature-encoding", dict(witness={**w, "signature": "!!"}), "WITNESS_MALFORMED"),
            ("tampered-floor", dict(witness=tampered), "WITNESS_SIGNATURE_INVALID"),
            ("other-key-id", dict(witness={**w, "witnessKeyId": "test-only.witness.other"}), "WITNESS_KEY_MISMATCH"),
            ("rogue-anchor", dict(anchor=F.anchor(F.TEST_ONLY_ROGUE_WITNESS_SEED)), "WITNESS_SIGNATURE_INVALID"),
            ("non-test-anchor", dict(anchor=F.anchor(key_id="witness.real-1")), "WITNESS_ANCHOR_NOT_TEST_ONLY"),
            ("environment", dict(environment="dev"), "WITNESS_ENVIRONMENT_MISMATCH"),
            ("dev-anchor", dict(anchor=F.anchor(environment="dev")), "WITNESS_ENVIRONMENT_MISMATCH"),
            ("malformed-context", dict(environment="staging"), "MALFORMED_CONTEXT"),
        ]
        for name, kwargs, reason in cases:
            if name == "missing":
                result = R.verify_recovery_witness(anchor=F.anchor(), witness=None, environment="test",
                                                   registry_root=SA.trusted_root())
            else:
                result = self.verify(**kwargs)
            with self.subTest(name=name):
                self.assertEqual((result.status, result.reason), (R.WITNESS_NOT_VERIFIED, reason))
        for reason in [c[2] for c in cases]:
            self.assertIn(reason, R.WITNESS_REASONS)

    def test_unsupported_witness_schema_is_reported(self):
        unsigned = {k: v for k, v in self.host.witness.items() if k != "signature"}
        unsigned["schemaVersion"] = 2
        doc = {**unsigned, "signature": SA.b64(F.witness_key().sign(R.witness_signing_bytes(unsigned)))}
        self.assertEqual(self.verify(doc).reason, "UNSUPPORTED_SCHEMA_VERSION")

    def test_witness_is_not_authority(self):
        # The witness key may never be the registry root or an authority key.
        as_root = R.verify_recovery_witness(anchor=F.anchor(), witness=self.host.witness, environment="test",
                                            registry_root=A.TrustedRegistryRootV1(
                                                SA.ROOT_KEY_ID, "test", F.anchor().public_key))
        self.assertEqual(as_root.reason, "WITNESS_KEY_IS_AUTHORITY_KEY")
        as_authority = self.verify(authority_keys=frozenset({F.anchor().public_key}))
        self.assertEqual(as_authority.reason, "WITNESS_KEY_IS_AUTHORITY_KEY")
        broker_as_witness = F.anchor(T.TEST_ONLY_BROKER_SEED)
        ready = self.host.readiness(witness_anchor=broker_as_witness)
        self.assertEqual(ready.reason, "WITNESS_KEY_IS_AUTHORITY_KEY")
        # A witness key cannot sign authority evidence or a registry.
        witness_signed = T.resign(SA.owner_evidence_unsigned(keyId=T.BROKER_KEY_ID), F.TEST_ONLY_WITNESS_SEED)
        self.assertEqual(SA.verify_owner(witness_signed, reg=F.e1_registry()).reason, "SIGNATURE_INVALID")
        own_id = T.resign(SA.owner_evidence_unsigned(keyId=F.WITNESS_KEY_ID), F.TEST_ONLY_WITNESS_SEED)
        self.assertEqual(SA.verify_owner(own_id, reg=F.e1_registry()).reason, "KEY_UNKNOWN")
        unsigned = {k: v for k, v in F.e1_registry().items() if k != "signature"}
        forged = {**unsigned, "signature": SA.b64(F.witness_key().sign(A.registry_signing_bytes(unsigned)))}
        self.assertEqual(AV.verify_authority_registry(context=SA.context(), registry=forged).reason,
                         "REGISTRY_SIGNATURE_INVALID")

    def test_witness_signer_hygiene_and_test_only_envelope(self):
        signer = F.witness_signer()
        for fn in (lambda: pickle.dumps(signer), lambda: copy.copy(signer), lambda: copy.deepcopy(signer)):
            with self.assertRaises(TypeError):
                fn()
        with self.assertRaises(ValueError):
            RL.SyntheticWitnessSignerV1(signing_key=F.witness_key(), witness_key_id="witness.real", environment="test")
        with self.assertRaises(ValueError):
            RL.SyntheticWitnessSignerV1(signing_key=F.witness_key(), witness_key_id=F.WITNESS_KEY_ID,
                                        environment="dev")
        with self.assertRaises(TypeError):
            RL.SyntheticWitnessSignerV1(signing_key=b"seed", witness_key_id=F.WITNESS_KEY_ID, environment="test")
        self.assertNotIn("sign_evidence", dir(signer))
        self.assertEqual(signer.public_key_b64(), T.public_b64(F.TEST_ONLY_WITNESS_SEED))


class WitnessSuccessionTests(unittest.TestCase):
    def setUp(self):
        self.host = F.Host()
        self.host.full_admission("c1")

    def parsed(self, doc):
        return R.RecoveryWitnessV1.from_verified_dict(doc)

    def resigned(self, previous, **changes):
        unsigned = {k: v for k, v in previous.items() if k != "signature"}
        unsigned.update(witnessVersion=previous["witnessVersion"] + 1,
                        previousWitnessDigest=R.witness_digest(previous))
        unsigned.update(changes)
        return {**unsigned, "signature": SA.b64(F.witness_key().sign(R.witness_signing_bytes(unsigned)))}

    def test_every_succession_rule(self):
        prev = self.host.witness
        p = self.parsed(prev)
        later = "2026-09-26T13:59:00Z"
        cases = [
            ("same-state-refresh", dict(updatedAt=later), None),
            ("version-skip", dict(witnessVersion=prev["witnessVersion"] + 2, updatedAt=later),
             "WITNESS_VERSION_NOT_SUCCESSOR"),
            ("chain-broken", dict(previousWitnessDigest="a" * 64, updatedAt=later), "WITNESS_CHAIN_BROKEN"),
            ("epoch-regression", dict(currentRecoveryEpoch=SA.OLD_EPOCH.to_dict(), updatedAt=later),
             "WITNESS_EPOCH_REGRESSION"),
            ("epoch-fork", dict(currentRecoveryEpoch=SA.FORK_EPOCH.to_dict(), updatedAt=later),
             "WITNESS_EPOCH_REGRESSION"),
            ("epoch-skip", dict(currentRecoveryEpoch=F.E3.to_dict(), minimumRegistryVersion=4,
                                ledgerHead="b" * 64, updatedAt=later), "WITNESS_EPOCH_NOT_SUCCESSOR"),
            ("floor-regression", dict(minimumRegistryVersion=2, updatedAt=later),
             "WITNESS_REGISTRY_MINIMUM_REGRESSION"),
            ("advance-without-new-registry", dict(currentRecoveryEpoch=F.E2.to_dict(), ledgerHead="b" * 64,
                                                  updatedAt=later), "WITNESS_REGISTRY_MINIMUM_REGRESSION"),
            ("policy-without-registry", dict(policyVersion="policy.synthetic.v9", updatedAt=later),
             "WITNESS_POLICY_CHANGE_WITHOUT_REGISTRY"),
            ("ledger-rewind", dict(ledgerSequence=p.ledger_sequence - 1, updatedAt=later),
             "WITNESS_LEDGER_REGRESSION"),
            ("ledger-same-sequence-other-head", dict(ledgerHead="c" * 64, updatedAt=later),
             "WITNESS_LEDGER_REGRESSION"),
            ("advance-same-head", dict(currentRecoveryEpoch=F.E2.to_dict(), minimumRegistryVersion=4,
                                       updatedAt=later), "WITNESS_LEDGER_REGRESSION"),
            ("advance-from-shorter-restored-ledger", dict(currentRecoveryEpoch=F.E2.to_dict(), minimumRegistryVersion=4,
                                                          ledgerSequence=2, ledgerHead="d" * 64, updatedAt=later), None),
            ("time-regression", dict(updatedAt="2026-09-26T11:00:00Z"), "WITNESS_TIME_REGRESSION"),
        ]
        for name, changes, reason in cases:
            with self.subTest(name=name):
                self.assertEqual(R.witness_succession_reason(p, self.parsed(self.resigned(prev, **changes))), reason)
        env = dataclasses.replace(self.parsed(self.resigned(prev, updatedAt=later)), environment="dev")
        self.assertEqual(R.witness_succession_reason(p, env), "WITNESS_ENVIRONMENT_MISMATCH")
        self.assertEqual({c[2] for c in cases if c[2]} | {"WITNESS_ENVIRONMENT_MISMATCH"}, set(R.SUCCESSION_REASONS))

    def test_witness_writer_refuses_to_rewind_the_ledger_or_floor(self):
        old = self.host.snapshot()
        self.host.publish_registry(F.e1_registry(4))
        with self.assertRaisesRegex(ValueError, "WITNESS_REGISTRY_MINIMUM_REGRESSION"):
            self.host.signer.sign_state(old[0], updated_at="2026-09-26T14:00:00Z")
        self.host.prepare("c2")
        with self.assertRaisesRegex(ValueError, "WITNESS_LEDGER_REGRESSION"):
            self.host.signer.sign_state(diverged(self.host.state), updated_at="2026-09-26T14:00:00Z")
        self.assertTrue(self.host.readiness().ready)   # refused updates changed nothing


def diverged(state: RL.AuthorityLedgerStateV1) -> RL.AuthorityLedgerStateV1:
    """Same journal length as `state`, different last transition."""
    return RL.AuthorityLedgerStateV1.from_log(
        state.log[:-1] + ({"op": RL.PREPARE, "challengeId": "c-diverged", "ledgerEpoch": state.ledger_epoch},))


# --------------------------------------- 10. trusted minimum registry version ---

def v2_registry():
    broker = SA.key_record(T.BROKER_KEY_ID, seed_name="actor.current-2",
                           publicKey=T.public_b64(T.TEST_ONLY_BROKER_SEED), registryVersion=2)
    keys = [k for k in SA.default_keys() if k["registryVersion"] <= 2] + [broker]
    return T.registry(version=2, keys=sorted(keys, key=lambda r: r["keyId"]))


class TrustedMinimumRegistryVersionTests(unittest.TestCase):
    def test_floor_comes_from_the_witness(self):
        host = F.Host()
        context = R.witness_authority_context(host.witness_view(), registry_root=SA.trusted_root(),
                                              purpose=A.NEW_ADMISSION)
        self.assertEqual(context.trusted_minimum_registry_version, 3)
        self.assertTrue(AV.verify_authority_registry(context=context, registry=F.e1_registry(3)).verified)
        self.assertTrue(AV.verify_authority_registry(context=context, registry=F.e1_registry(4)).verified)
        self.assertEqual(AV.verify_authority_registry(context=context, registry=v2_registry()).reason,
                         "REGISTRY_DOWNGRADE")

    def test_restored_broker_that_thinks_n_minus_1_is_current_is_rejected(self):
        host = F.Host()
        before = host.snapshot()
        host.publish_registry(F.e1_registry(4))
        self.assertTrue(host.readiness().ready)
        self.assertEqual(host.witness_view().minimum_registry_version, 4)
        # Broker state and its registry both restored; the witness survives.
        self.assertEqual(host.readiness(state=before[0], registry=before[2]).reason, "REGISTRY_DOWNGRADE")
        # Broker state restored, current registry supplied.
        self.assertEqual(host.readiness(state=before[0]).reason, "BROKER_REGISTRY_VIEW_STALE")
        # Registry newer than the broker view is also not ready.
        self.assertEqual(host.readiness(registry=F.e1_registry(5)).reason, "BROKER_REGISTRY_VIEW_STALE")
        # Whole-host: witness restored too; the floor goes back with it (unresolved).
        self.assertTrue(host.readiness(state=before[0], registry=before[2], witness=before[1]).ready)


# --------------------------------------- 14. compromised key rollback ---

def broker_evidence(**overrides):
    unsigned = SA.owner_evidence_unsigned(keyId=T.BROKER_KEY_ID, **overrides)
    return T.resign(unsigned)


class CompromisedKeyRollbackTests(unittest.TestCase):
    def setUp(self):
        self.v10 = F.e1_registry(10)
        self.v11 = F.rotated_e1_registry(11, compromised=True)
        self.v11_routine = F.rotated_e1_registry(11)
        self.host = F.Host(registry=self.v10)
        self.before = self.host.snapshot()
        self.host.publish_registry(self.v11, key_ids=(T.NEXT_KEY_ID,))

    def verify(self, registry, purpose=A.NEW_ADMISSION, witness=None):
        witness = self.host.witness_view() if witness is None else R.RecoveryWitnessV1.from_verified_dict(witness)
        context = R.witness_authority_context(witness, registry_root=SA.trusted_root(), purpose=purpose)
        return AV.verify_owner_evidence(context=context, registry=registry, evidence=broker_evidence(),
                                        expectation=SA.owner_expectation())

    def test_compromise_survives_registry_rollback_while_the_witness_survives(self):
        self.assertEqual(self.verify(self.v11).reason, "KEY_COMPROMISED")
        self.assertEqual(self.verify(self.v11, A.HISTORICAL_VERIFICATION).reason, "KEY_COMPROMISED")
        # Restoring v10 (K valid) cannot revive K: the witness floor is 11.
        self.assertEqual(self.verify(self.v10).reason, "REGISTRY_DOWNGRADE")
        self.assertEqual(self.verify(self.v10, A.HISTORICAL_VERIFICATION).reason, "REGISTRY_DOWNGRADE")
        self.assertEqual(self.host.readiness(registry=self.v10).reason, "REGISTRY_DOWNGRADE")
        self.assertEqual(self.host.readiness(state=self.before[0], registry=self.v10).reason, "REGISTRY_DOWNGRADE")

    def test_compromise_is_not_routine_retirement(self):
        routine = F.Host(registry=self.v10)
        routine.publish_registry(self.v11_routine, key_ids=(T.NEXT_KEY_ID,))
        context = R.witness_authority_context(routine.witness_view(), registry_root=SA.trusted_root(),
                                              purpose=A.HISTORICAL_VERIFICATION)
        result = AV.verify_owner_evidence(context=context, registry=self.v11_routine, evidence=broker_evidence(),
                                          expectation=SA.owner_expectation())
        self.assertEqual((result.status, result.facts["keyStatus"]),
                         (AV.VERIFIED_AUTHORITY_EVIDENCE, "RETIRED_AFTER_ISSUANCE"))
        # Compromise is retroactive whatever issuedAt the signer chose.
        backdated = T.resign(SA.owner_evidence_unsigned(keyId=T.BROKER_KEY_ID, issuedAt="2026-09-26T00:00:01Z"))
        self.assertEqual(AV.verify_owner_evidence(
            context=dataclasses.replace(context, purpose=A.HISTORICAL_VERIFICATION), registry=self.v11,
            evidence=backdated, expectation=SA.owner_expectation()).reason, "KEY_COMPROMISED")

    def test_whole_host_rollback_revives_the_compromised_key_unresolved(self):
        # Witness rolled back with the registry and ledger: K verifies again.
        result = self.verify(self.v10, witness=self.before[1])
        self.assertEqual(result.status, AV.VERIFIED_AUTHORITY_EVIDENCE)
        self.assertTrue(self.host.readiness(state=self.before[0], witness=self.before[1],
                                            registry=self.v10).ready)
        self.assertFalse(R.WHOLE_HOST_ROLLBACK_PROTECTED)


# -------------------------------- 5 / 16. challenge and evidence-use recovery ---

class ChallengeAndEvidenceUseRecoveryTests(unittest.TestCase):
    def setUp(self):
        host = F.Host()
        host.full_admission("c-admitted")                  # CONSUMED challenge, CONSUMED use
        for cid, kind in (("c-expired", RL.EXPIRE), ("c-cancelled", RL.CANCEL), ("c-failed", RL.FAIL)):
            host.prepare(cid)
            host.commit(lambda s, cid=cid, kind=kind: s.terminate(kind, cid))
        host.prepare("c-prepared")                         # PREPARED
        host.prepare("c-consumed")
        host.consume("c-consumed")                         # CONSUMED, no evidence
        host.prepare("c-issued")
        host.consume("c-issued")
        host.issue("c-issued")                             # evidence issued, unreserved
        host.prepare("c-reserved")
        host.consume("c-reserved")
        host.issue("c-reserved")
        host.reserve("aev.c-reserved", "prop.reserved")    # RESERVED use
        host.prepare("c-abandoned")
        host.consume("c-abandoned")
        host.issue("c-abandoned")
        host.reserve("aev.c-abandoned", "prop.abandoned")
        host.commit(lambda s: s.abandon("aev.c-abandoned"))  # ABANDONED use
        self.before = host.state
        self.ack = host.recover()
        self.host = host

    def test_prepared_challenge_is_voided_and_never_valid_in_the_new_epoch(self):
        h = self.host
        self.assertEqual(h.state.challenge("c-prepared")["state"], RL.VOIDED_BY_RECOVERY)
        ready = h.readiness()
        self.assertEqual(refusal(lambda: h.state.consume("c-prepared", ready=ready)), "CHALLENGE_NOT_PREPARED")
        self.assertEqual(refusal(lambda: h.state.prepare("c-prepared", h.state.ledger_epoch, ready=ready)),
                         "CHALLENGE_ALREADY_KNOWN")
        self.assertEqual(refusal(lambda: h.state.prepare("c-new", F.LEP1, ready=ready)),
                         "CHALLENGE_EPOCH_NOT_CURRENT")
        self.assertIn("c-prepared", self.ack["voidedChallengeIds"])

    def test_unconsumed_or_unsigned_pre_recovery_proof_is_never_usable(self):
        h, ready = self.host, self.host.readiness()
        self.assertEqual(h.state.challenge("c-consumed")["state"], RL.CONSUMED)
        self.assertEqual(refusal(lambda: h.state.issue("c-consumed", "aev.late", F.digest("late"), ready=ready)),
                         "STALE_EPOCH_CHALLENGE")
        self.assertEqual(refusal(lambda: h.state.reserve("aev.c-issued", F.digest("evidence aev.c-issued"), F.E1,
                                                         "prop.late", ready=ready)), "STALE_EPOCH_EVIDENCE")
        # Relabelling old evidence as current-epoch does not help: the ledger
        # recorded the epoch it was issued in.
        self.assertEqual(refusal(lambda: h.state.reserve("aev.c-issued", F.digest("evidence aev.c-issued"),
                                                         h.state.recovery_epoch, "prop.late", ready=ready)),
                         "STALE_EPOCH_EVIDENCE")
        self.assertEqual(set(self.ack["ownerReauthorizationRequired"]),
                         {"c-prepared", "c-consumed", "c-issued", "c-reserved", "c-abandoned"})

    def test_terminal_states_are_monotonic_across_recovery(self):
        before, after = self.before.rows, self.host.state.rows
        for table, terminal in (("challenges", RL.CHALLENGE_TERMINAL), ("uses", RL.USE_TERMINAL)):
            for key, entry in before[table].items():
                with self.subTest(table=table, key=key):
                    if entry["state"] in terminal:
                        self.assertEqual(after[table][key], entry)
                    else:
                        self.assertIn(after[table][key]["state"], terminal)
        self.assertEqual(self.ack["retainedTerminalChallenges"], len(before["challenges"]))

    def test_evidence_use_states_across_recovery(self):
        h, ready = self.host, self.host.readiness()
        self.assertEqual(h.state.use("aev.c-admitted")["state"], RL.USE_CONSUMED)
        self.assertEqual(h.state.use("aev.c-reserved")["state"], RL.QUARANTINED_BY_RECOVERY)
        self.assertEqual(h.state.use("aev.c-abandoned")["state"], RL.ABANDONED)
        self.assertEqual(self.ack["quarantinedEvidenceIds"], ["aev.c-reserved"])
        self.assertEqual(self.ack["reconciliationRequired"], ["aev.c-reserved"])
        for evidence_id in ("aev.c-admitted", "aev.c-reserved", "aev.c-abandoned"):
            with self.subTest(evidence_id=evidence_id):
                self.assertEqual(refusal(lambda: h.state.confirm(evidence_id, "adm.x", "rev.x", ready=ready)),
                                 "USE_NOT_RESERVED")
                self.assertEqual(refusal(lambda: h.state.abandon(evidence_id)), "USE_NOT_RESERVED")

    def test_consumed_evidence_use_is_never_reusable_even_by_a_stale_application(self):
        h = F.Host()
        h.full_admission("c1")
        ready = h.readiness()
        self.assertEqual(refusal(lambda: h.state.reserve("aev.c1", F.digest("evidence aev.c1"), F.E1, "prop.again",
                                                         ready=ready)), "EVIDENCE_ALREADY_USED")

    def test_missing_authority_state_fails_closed(self):
        self.assertEqual(self.host.readiness(state=None).reason, "AUTHORITY_STATE_MISSING")

    def test_ack_is_a_record_not_an_authority(self):
        ack = self.ack
        self.assertEqual((ack["kind"], ack["authorizationBasis"], ack["historicalEvidenceRetained"],
                          ack["wholeHostRollbackProtected"], ack["rollbackDetectionScope"]),
                         ("RecoveryEpochTransitionV1", "OWNER_SIGNED_REGISTRY_AT_NEW_EPOCH", True, False, "LEDGER_ONLY"))
        self.assertEqual((ack["previousEpoch"], ack["newEpoch"], ack["newLedgerEpoch"]),
                         (F.E1.to_dict(), F.E2.to_dict(), F.LEP2))
        self.assertFalse({"signature", "keyId", "evidenceId"} & set(ack))


# --------------------------------------- 11. recovery-epoch advancement ---

class RecoveryCeremonyTests(unittest.TestCase):
    def test_advance_is_from_the_witness_not_from_a_stale_ledger(self):
        host, snap = F.base_host()
        host.state = snap[0]                                   # ledger-only restore
        self.assertEqual(host.readiness().reason, "LEDGER_BEHIND_WITNESS")
        ack = host.recover()
        self.assertEqual(host.state.recovery_epoch, F.E2)
        self.assertTrue(host.readiness().ready)
        # c2 was consumed after the snapshot; the restored ledger shows it
        # PREPARED. Recovery voids it: a consumed authorization never reopens.
        self.assertEqual(host.state.challenge("c2")["state"], RL.VOIDED_BY_RECOVERY)
        self.assertEqual(ack["restoredLedgerEpoch"], F.E1.to_dict())

    def test_advance_preconditions(self):
        host = F.Host()
        w = host.witness_view()
        base = dict(witness=w, new_random=F.E2.random, registry=F.e2_registry(), registry_root=SA.trusted_root(),
                    reason="OPERATOR_RECOVERY")
        cases = [
            ("reason", dict(reason="APPLICATION_REQUEST"), "RECOVERY_REASON_INVALID"),
            ("witness", dict(witness="forged"), "RECOVERY_WITNESS_INVALID"),
            ("same-random", dict(new_random=F.E1.random), "RECOVERY_EPOCH_NOT_ADVANCING"),
            ("bad-random", dict(new_random="XYZ"), "RECOVERY_EPOCH_NOT_ADVANCING"),
            ("registry-not-above-floor", dict(registry=F.e2_registry(3)), "RECOVERY_REGISTRY_NOT_ADVANCING"),
            ("registry-old-epoch", dict(registry=F.e1_registry(4)), "RECOVERY_REGISTRY_UNVERIFIED"),
            ("registry-fork-epoch", dict(registry=F.e2_registry(epoch=F.E2_FORK)), "RECOVERY_REGISTRY_UNVERIFIED"),
            ("registry-attacker-root", dict(registry=SA.sign_registry(
                {k: v for k, v in F.e2_registry().items() if k != "signature"}, "attacker-root")),
             "RECOVERY_REGISTRY_UNVERIFIED"),
            ("registry-without-signing-key", dict(registry=F.e2_registry(e2_key=F.e2_key_record(
                retiredAt=F.RECOVERY_AT))), "RECOVERY_NO_SIGNING_KEY"),
        ]
        for name, change, reason in cases:
            with self.subTest(name=name):
                self.assertEqual(refusal(lambda: RL.begin_recovery(host.state, **{**base, **change})), reason)

    def test_mid_ceremony_crash_is_not_ready_until_quarantine_completes(self):
        host, snap = F.base_host()
        host.state = snap[0]                                       # restored ledger: c2 PREPARED
        host.recover(crash_after_advance=True)
        self.assertEqual(host.witness_view().current_recovery_epoch, F.E2)   # point of no return
        self.assertEqual(host.readiness().reason, "NONTERMINAL_PRE_RECOVERY_WORK")
        host.state = RL.quarantine_pre_recovery(host.state)
        host.sign()
        self.assertTrue(host.readiness().ready)

    def test_removing_authority_never_needs_readiness_creating_it_always_does(self):
        host = F.Host()
        host.prepare("c1")
        stale_token = host.readiness()
        host.prepare("c2")
        not_ready = host.readiness(state=F.Host().state)
        for token in (None, not_ready, stale_token):
            with self.subTest(token=token):
                self.assertEqual(refusal(lambda: host.state.consume("c1", ready=token)), "NOT_READY_FOR_ISSUANCE")
                self.assertEqual(refusal(lambda: host.state.prepare("c3", host.state.ledger_epoch, ready=token)),
                                 "NOT_READY_FOR_ISSUANCE")
        # Terminalizing needs no readiness at all.
        self.assertEqual(host.state.terminate(RL.CANCEL, "c1").challenge("c1")["state"], RL.CANCELLED)

    def test_tampered_rows_block_every_transition(self):
        host = F.Host()
        host.full_admission("c1")
        tampered = F.tamper_rows(host.state, "challenges", "c1", state=RL.PREPARED)
        self.assertEqual(refusal(lambda: tampered.terminate(RL.EXPIRE, "c1")), "LEDGER_INTEGRITY_FAILED")
        self.assertEqual(refusal(lambda: tampered.consume("c1", ready=host.readiness())), "LEDGER_INTEGRITY_FAILED")


# ------------------------------------------- 12. restore readiness gate ---

class RestoreReadinessTests(unittest.TestCase):
    def test_every_readiness_reason_is_reachable_and_the_gate_fails_closed(self):
        seen = {row["reason"] for row in F.restore_matrix() if row["reason"]}
        host, snap = F.base_host()
        extra = {
            "MALFORMED_INPUT": RL.evaluate_restore_readiness(
                state=host.state, witness=host.witness, witness_anchor="anchor", registry=host.registry,
                registry_root=SA.trusted_root(), environment="test", privacy=F.privacy()),
            "WITNESS_MISSING": host.readiness(witness=None),
            "WITNESS_KEY_IS_AUTHORITY_KEY": host.readiness(witness_anchor=F.anchor(T.TEST_ONLY_BROKER_SEED)),
            "WITNESS_INVALID": host.readiness(witness={**host.witness, "ledgerSequence": 1}),
            "LEDGER_INTEGRITY_FAILED": host.readiness(state=RL.AuthorityLedgerStateV1(
                host.state.log[:1] + ({"op": RL.CONSUME, "challengeId": "c-never"},), host.state.rows)),
            "POLICY_VERSION_NOT_ACCEPTABLE": host.readiness(state=RL.AuthorityLedgerStateV1.genesis(
                environment="test", recovery_epoch=F.E1, policy_version="policy.synthetic.v9",
                registry_version=3, signing_key_ids=(T.BROKER_KEY_ID,))),
            "REGISTRY_MISSING": host.readiness(registry=None),
            "REGISTRY_UNVERIFIED": host.readiness(registry=SA.sign_registry(
                {k: v for k, v in host.registry.items() if k != "signature"}, "attacker-root")),
            "LEDGER_HEAD_MISMATCH": host.readiness(state=diverged(host.state)),
            "PRIVACY_BOUNDARY_STALE": host.readiness(privacy_status=R.PRIVACY_OLDER_THAN_REQUIRED),
            "PRIVACY_BOUNDARY_UNVERIFIED": host.readiness(privacy_status=R.PRIVACY_NOT_MODELLED),
        }
        recovered, _ = F.base_host()
        pre_witness = dict(recovered.witness)
        recovered.recover()
        extra["LEDGER_EPOCH_AHEAD_OF_WITNESS"] = recovered.readiness(witness=pre_witness)
        extra["REGISTRY_EPOCH_MISMATCH"] = recovered.readiness(registry=F.e1_registry(5))
        crashed, crashed_snap = F.base_host()
        crashed.state = crashed_snap[0]                            # restored ledger: c2 PREPARED
        crashed.recover(crash_after_advance=True)
        extra["NONTERMINAL_PRE_RECOVERY_WORK"] = crashed.readiness()
        rotated = F.Host()
        rotated.publish_registry(F.rotated_e1_registry())          # broker key retired, still configured
        extra["REQUIRED_KEY_UNAVAILABLE"] = rotated.readiness()
        extra["AUTHORITY_STATE_MISSING"] = host.readiness(state=None)
        for reason, result in extra.items():
            with self.subTest(reason=reason):
                self.assertEqual((result.status, result.reason), (RL.NOT_READY, reason))
                self.assertFalse(result.facts["authorityIssuanceAllowed"])
                self.assertFalse(result.facts["wholeHostRollbackProtected"])
        seen |= set(extra)
        self.assertEqual(seen, set(RL.READINESS_REASONS))

    def test_privacy_boundary_states(self):
        host = F.Host()
        expected = {R.PRIVACY_AT_OR_AFTER_REQUIRED: None, R.PRIVACY_OLDER_THAN_REQUIRED: "PRIVACY_BOUNDARY_STALE",
                    R.PRIVACY_UNAVAILABLE: "PRIVACY_BOUNDARY_UNVERIFIED",
                    R.PRIVACY_NOT_MODELLED: "PRIVACY_BOUNDARY_UNVERIFIED"}
        for status, reason in expected.items():
            with self.subTest(status=status):
                self.assertEqual(host.readiness(privacy_status=status).reason, reason)
        self.assertFalse(R.CANONICAL_PRIVACY_EPOCH_EXISTS)
        with self.assertRaises(OwnerProofError):
            R.PrivacyBoundaryObservationV1("CURRENT").validate()
        with self.assertRaises(OwnerProofError):
            R.PrivacyBoundaryObservationV1(R.PRIVACY_AT_OR_AFTER_REQUIRED, source="LIVE_PRIVACY_DB").validate()

    def test_ready_result_is_bound_to_the_exact_ledger_state(self):
        host = F.Host()
        result = host.readiness()
        self.assertEqual((result.facts["ledgerSequence"], result.facts["ledgerHead"]),
                         (host.state.sequence, host.state.head))
        self.assertEqual(result.facts["rollbackDetectionScope"], "LEDGER_ONLY")


# ------------------------------------------- 13. snapshot / restore matrix ---

EXPECTED_MATRIX = {
    # scenario: (readiness reason, operation refusal, issuance blocked, historical reads allowed, detected)
    1: (None, None, False, True, True),
    2: ("LEDGER_BEHIND_WITNESS", None, True, True, True),
    3: ("LEDGER_AHEAD_OF_WITNESS", None, True, False, True),
    4: (None, None, False, True, False),
    5: ("REGISTRY_DOWNGRADE", None, True, False, True),
    6: ("BROKER_REGISTRY_VIEW_STALE", None, True, True, True),
    7: ("TERMINAL_STATE_REOPENED", None, True, True, True),
    8: ("LEDGER_EPOCH_STALE", None, True, True, True),
    9: ("REGISTRY_DOWNGRADE", None, True, False, True),
    10: ("REGISTRY_DOWNGRADE", None, True, False, True),
    11: (None, "STALE_EPOCH_EVIDENCE", True, True, True),
    12: (None, "EVIDENCE_ALREADY_USED", True, True, True),
    13: ("LEDGER_BEHIND_WITNESS", None, True, True, True),
    14: ("LEDGER_EPOCH_FORKED", None, True, True, True),
    15: ("ENVIRONMENT_MISMATCH", None, True, False, True),
}


class SnapshotRestoreMatrixTests(unittest.TestCase):
    def test_fifteen_scenarios(self):
        rows = F.restore_matrix()
        self.assertEqual([r["scenario"] for r in rows], list(range(1, 16)))
        for row in rows:
            with self.subTest(scenario=row["scenario"], name=row["name"]):
                self.assertEqual((row["reason"], row["operationRefusal"], row["authorityIssuanceBlocked"],
                                  row["historicalReadsAllowed"], row["detected"]), EXPECTED_MATRIX[row["scenario"]])
                self.assertFalse(row["wholeHostRollbackProtected"])
        unresolved = [r for r in rows if r["unresolved"]]
        self.assertEqual([r["scenario"] for r in unresolved], [4])
        self.assertIn("WHOLE_HOST", unresolved[0]["unresolved"])


# ------------------------------------------- 9 / 18. whole-host limit ---

class WholeHostRollbackUnresolvedTests(unittest.TestCase):
    def test_ledger_only_rollback_is_detected(self):
        host, snap = F.base_host()
        self.assertEqual(host.readiness(state=snap[0]).reason, "LEDGER_BEHIND_WITNESS")

    def test_whole_host_rollback_is_not_detected_and_reopens_consumed_authority(self):
        host, snap = F.base_host()
        # c2 was consumed and its evidence issued after the snapshot.
        self.assertEqual(host.state.challenge("c2")["state"], RL.CONSUMED)
        host.state, host.witness, host.registry = snap
        host.signer.restore_last(host.witness)     # the witness store rolled back too
        result = host.readiness()
        self.assertEqual(result.status, RL.RESTORE_READY)    # nothing detects it
        self.assertEqual((result.facts["rollbackDetectionScope"], result.facts["wholeHostRollbackProtected"]),
                         ("LEDGER_ONLY", False))
        # The consumed authorization is PREPARED again and can be consumed again.
        self.assertEqual(host.state.challenge("c2")["state"], RL.PREPARED)
        host.consume("c2")
        self.assertEqual(host.state.challenge("c2")["state"], RL.CONSUMED)

    def test_no_whole_host_or_level_3_claim_anywhere(self):
        self.assertIs(R.WHOLE_HOST_ROLLBACK_PROTECTED, False)
        self.assertEqual(R.ROLLBACK_DETECTION_SCOPE, "LEDGER_ONLY")
        for path in (PACKAGE / "recovery_contracts.py", PACKAGE / "recovery_admission.py",
                     SIGNER_PACKAGE / "synthetic_recovery_ledger.py", RECORD):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertNotRegex(text, r"WHOLE_HOST_ROLLBACK_PROTECTED\s*=\s*True")
                self.assertNotRegex(text, r"(?i)level 3 (isolation )?(is )?(achieved|complete|proven)")
                self.assertNotRegex(text, r"(?i)off-host monoton\w* (is )?(achieved|implemented|proven)")


# ---------------------------------- 4 / 6. historical vs new admission (L04) ---

class RecoveryIntegrationTests(unittest.TestCase):
    """The real, unchanged L04 V2 store behind the B1b-3b signer and adapter."""

    def setUp(self):
        self.flow = F.RecoveryFlow()
        self.addCleanup(self.flow.close)
        f = self.flow
        self.action, self.proposal, self.proof, self.evidence = f.create("SYNTH-E1", "rec.e1")
        admitted = f.gate.admit(f.request(self.proposal, self.proof, self.evidence))
        self.assertEqual(admitted.status, AD.L04_ADMITTED, admitted)
        self.admitted = admitted
        # A second E1 authorization, signed but never admitted before recovery.
        item = admitted.facts["admission"]["memoryItemId"]
        self.item, self.revision = item, admitted.facts["admission"]["revisionId"]
        self.pending_action, encoded = f.l04.action("SYNTH-E1-PENDING", operation=C.SUPERSEDE,
                                                    expected=self.revision)
        self.pending_proposal = f.l04.proposal(self.pending_action, encoded, nonce="rec.e1.pending")
        self.pending_proof = f.proof(self.pending_action, "rec.e1.pending", memory_item_id=item)
        self.pending = f.signed(self.pending_proof)
        self.e1_gate = f.gate
        self.e1_adapter = f.adapter

    def recover(self):
        f = self.flow
        self.ack = f.recover()
        f.configure(F.E2)

    def assertRefused(self, result, reason, detail=None):
        self.assertEqual((result.status, result.reason), (V2.NOT_ACCEPTED, reason), result)
        if detail is not None:
            self.assertEqual(result.detail, detail)

    def test_e1_admission_is_new_admission_authority_under_e1(self):
        recovery = self.admitted.facts["recovery"]
        self.assertEqual((recovery["validity"], recovery["authorizesNewAdmission"], recovery["evidenceEpochIsCurrent"],
                          recovery["currentLedgerEpoch"]), (R.NEW_ADMISSION_AUTHORITY, True, True, F.LEP1))

    def test_unbound_b1b3b_contexts_are_refused_by_the_gate(self):
        flow = T.Flow()
        self.addCleanup(flow.l04.close)
        gate = self.flow.make_gate(flow.adapter)
        _, proposal, proof, evidence = flow.create("SYNTH-UNBOUND", "rec.unbound")
        self.assertRefused(gate.admit(flow.request(proposal, proof, evidence)), "LEDGER_EPOCH_NOT_BOUND_TO_WITNESS")

    def test_new_admission_rejects_stale_epoch_evidence_after_recovery(self):
        f = self.flow
        counts = f.l04.counts()
        self.recover()
        # The old adapter is still configured for E1: the witness voids it.
        self.assertRefused(self.e1_gate.admit(f.request(self.pending_proposal, self.pending_proof, self.pending,
                                                        epoch=F.E1)), "AUTHORITY_CONTEXT_NOT_BOUND_TO_WITNESS")
        # The E2 gate refuses the E1 challenge and the E1 evidence.
        self.assertRefused(f.gate.admit(f.request(self.pending_proposal, self.pending_proof, self.pending,
                                                  epoch=F.E1)), "STALE_EPOCH_CHALLENGE")
        e2_proof = f.proof(self.pending_action, "rec.e2.mixed", memory_item_id=self.item)
        self.assertRefused(f.gate.admit(f.request(self.pending_proposal, e2_proof, self.pending, epoch=F.E1,
                                                  challenge_record=None)), "STALE_EPOCH_EVIDENCE")
        # Bypassing the gate: the E2 adapter still refuses (defence in depth).
        self.assertRefused(f.adapter.admit(f.request(self.pending_proposal, self.pending_proof, self.pending,
                                                     epoch=F.E1)), "OWNER_PROOF_REJECTED", "LEDGER_EPOCH_MISMATCH")
        # Bypassing the gate with the stale E1 adapter against the E2 registry.
        self.assertRefused(self.e1_adapter.admit(f.request(self.pending_proposal, self.pending_proof, self.pending,
                                                           epoch=F.E1)), "AUTHORITY_EVIDENCE_REJECTED",
                           "REGISTRY_EPOCH_MISMATCH")
        self.assertEqual(f.l04.counts(), counts)

    def test_old_challenge_cannot_be_prepared_in_the_new_epoch(self):
        self.recover()
        result = self.flow.broker.prepare_challenge(self.pending_proof.challenge_json)
        self.assertEqual((result.status, result.reason), (B.REFUSED, "CHALLENGE_CONTEXT_MISMATCH"))

    def test_application_db_changes_cannot_make_e1_evidence_current(self):
        f = self.flow
        self.recover()
        forged_record = {**f.broker_for(F.E1).ledger_record(self.pending_proof.challenge["challengeId"]),
                         "ledgerEpoch": F.LEP2}
        self.assertRefused(f.gate.admit(f.request(self.pending_proposal, self.pending_proof, self.pending,
                                                  epoch=F.E1, challenge_record=forged_record)),
                           "STALE_EPOCH_CHALLENGE")
        # An application-built adapter with E1 contexts over the same DB is refused.
        rogue = AD.L04V2AdmissionAdapter(AD.v2_admission_store(f.l04.store()),
                                         owner_context=f.owner_context(F.E1), authority_context=SA.context(),
                                         registry_provider=lambda: F.e1_registry(), link_store=f.links,
                                         evidence_use_ledger=f.ledger)
        self.assertRefused(f.make_gate(rogue).admit(f.request(self.pending_proposal, self.pending_proof, self.pending,
                                                              epoch=F.E1)), "AUTHORITY_CONTEXT_NOT_BOUND_TO_WITNESS")

    def test_fresh_owner_authorization_admits_in_the_new_epoch(self):
        f = self.flow
        self.recover()
        proof = f.proof(self.pending_action, "rec.e2.fresh", memory_item_id=self.item)
        evidence = f.signed(proof)
        self.assertEqual((evidence["recoveryEpoch"], evidence["keyId"], evidence["registryVersion"]),
                         (F.E2.to_dict(), F.E2_KEY_ID, 4))
        result = f.gate.admit(f.request(self.pending_proposal, proof, evidence))
        self.assertEqual(result.status, AD.L04_ADMITTED, result)
        self.assertEqual((result.facts["recovery"]["currentRecoveryEpoch"], result.facts["recovery"]["validity"]),
                         (F.E2.to_dict(), R.NEW_ADMISSION_AUTHORITY))

    def test_historical_validity_survives_recovery_without_authorizing(self):
        f = self.flow
        self.recover()
        result = f.historical(self.proof, self.evidence, self.proposal, epoch=F.E1)
        self.assertEqual(result.status, V2.ACCEPTED_MEMORY, result)
        recovery, authority = result.facts["recovery"], result.facts["authority"]
        self.assertEqual((recovery["validity"], recovery["authorizesNewAdmission"], recovery["evidenceEpochIsCurrent"],
                          recovery["evidenceLedgerEpoch"], recovery["currentLedgerEpoch"]),
                         (R.HISTORICAL_VALIDITY, False, False, F.LEP1, F.LEP2))
        self.assertEqual((authority["purpose"], authority["authorizesNewAdmission"], authority["keyStatus"]),
                         (A.HISTORICAL_VERIFICATION, False, "RETIRED_AFTER_ISSUANCE"))
        self.assertFalse(result.facts["truthClaim"])

    def test_historical_verification_still_applies_current_registry_rules(self):
        f = self.flow
        self.recover()
        compromised = F.e2_registry(5, broker=F.compromised_broker(), issued_at="2026-09-26T13:20:00Z")
        f.host.publish_registry(compromised)
        f.registry_doc = f.host.registry
        self.assertRefused(f.historical(self.proof, self.evidence, self.proposal, epoch=F.E1),
                           "AUTHORITY_EVIDENCE_REJECTED", "KEY_COMPROMISED")
        # Restoring the pre-compromise registry is a downgrade against the witness.
        self.assertRefused(f.historical(self.proof, self.evidence, self.proposal, epoch=F.E1,
                                        registry=F.e2_registry()), "AUTHORITY_EVIDENCE_REJECTED",
                           "REGISTRY_DOWNGRADE")

    def test_historical_verification_fails_closed(self):
        f = self.flow
        self.recover()
        self.assertRefused(f.historical(self.proof, self.evidence, self.proposal, epoch=F.E1, evidence_use=None),
                           "EVIDENCE_USE_MISSING")
        self.assertRefused(f.historical(self.proof, self.evidence, self.proposal, epoch=F.E1,
                                        witness={**f.witness_doc, "minimumRegistryVersion": 1}),
                           "RECOVERY_WITNESS_UNVERIFIED", "WITNESS_SIGNATURE_INVALID")
        self.assertRefused(f.historical(self.proof, {**self.evidence, "recoveryEpoch": None}, self.proposal,
                                        epoch=F.E1), "HISTORICAL_EPOCH_UNRESOLVED")
        # Challenge from one epoch presented with evidence claiming another.
        relabelled = T.resign(self.evidence, recoveryEpoch=F.E2.to_dict())
        self.assertRefused(f.historical(self.proof, relabelled, self.proposal, epoch=F.E1), "STALE_EPOCH_CHALLENGE")
        self.assertRefused(f.gate.admit("not a request"), "MALFORMED_CONTEXT")
        self.assertRefused(RA.verify_historical_accepted_memory(
            witness=f.witness_doc, witness_anchor=F.anchor(), registry_root=SA.trusted_root(), owner_context=None),
            "MALFORMED_CONTEXT")

    def test_gate_refuses_an_unverified_witness(self):
        f = self.flow
        good = f.host.witness
        f.host.witness = {**good, "ledgerSequence": 99}
        self.assertRefused(f.gate.admit(f.request(self.pending_proposal, self.pending_proof, self.pending)),
                           "RECOVERY_WITNESS_UNVERIFIED", "WITNESS_SIGNATURE_INVALID")
        f.host.witness = good

    def test_newer_privacy_suppression_is_not_defeated_by_older_state(self):
        f = self.flow
        self.recover()
        f.l04.privacy.suppressed = True
        proof = f.proof(self.pending_action, "rec.e2.suppressed", memory_item_id=self.item)
        self.assertRefused(f.gate.admit(f.request(self.pending_proposal, proof, f.signed(proof))),
                           "PRIVACY_HOLD_ACTIVE")
        self.assertEqual(f.host.readiness(privacy_status=R.PRIVACY_OLDER_THAN_REQUIRED).reason,
                         "PRIVACY_BOUNDARY_STALE")

    def test_crash_after_l04_commit_then_recovery_is_never_accepted(self):
        f = self.flow

        def crash(point):
            if point == "after_l04_commit":
                raise RuntimeError(point)

        crashing = AD.L04V2AdmissionAdapter(
            AD.v2_admission_store(f.l04.store()), owner_context=f.adapter.owner_context,
            authority_context=f.adapter.authority_context, registry_provider=lambda: f.registry_doc,
            link_store=f.links, evidence_use_ledger=f.ledger, fault_hook=crash)
        with self.assertRaisesRegex(RuntimeError, "after_l04_commit"):
            f.make_gate(crashing).admit(f.request(self.pending_proposal, self.pending_proof, self.pending))
        self.assertEqual(f.ledger.lookup(self.pending["evidenceId"])["state"], "RESERVED")
        self.recover()
        # Stored but never linked or confirmed: not accepted, historically or new.
        self.assertRefused(f.historical(self.pending_proof, self.pending, self.pending_proposal, epoch=F.E1),
                           "ADMISSION_LINK_MISSING")
        self.assertRefused(f.gate.admit(f.request(self.pending_proposal, self.pending_proof, self.pending,
                                                  epoch=F.E1)), "STALE_EPOCH_CHALLENGE")


# --------------------------------------- 7. registry version relationship ---

class RegistryVersionRelationshipTests(unittest.TestCase):
    def test_owner_binds_tuple_registry_signer_binds_authority_registry(self):
        self.assertIn("registryTupleVersion", K.CHALLENGE_V2_FIELDS)
        self.assertIn("ledgerEpoch", K.CHALLENGE_V2_FIELDS)
        self.assertNotIn("registryVersion", K.CHALLENGE_V2_FIELDS)
        self.assertNotIn("recoveryEpoch", K.CHALLENGE_V2_FIELDS)
        self.assertIn("registryVersion", A.OwnerEvidenceV2.FIELDS)
        self.assertIn("recoveryEpoch", A.OwnerEvidenceV2.FIELDS)
        self.assertIn("challengeDigest", A.OwnerEvidenceV2.FIELDS)
        self.assertNotIn("registryTupleVersion", A.OwnerEvidenceV2.FIELDS)
        self.assertNotIn("ledgerEpoch", A.OwnerEvidenceV2.FIELDS)
        # The witness floors the authority registry only.
        self.assertIn("minimumRegistryVersion", R.WITNESS_FIELDS)
        self.assertNotIn("registryTupleVersion", R.WITNESS_FIELDS)

    def test_tuple_registry_version_reaches_evidence_only_through_the_challenge_digest(self):
        l04 = T.L04Harness()
        self.addCleanup(l04.close)
        action, _ = l04.action("SYNTH-TUPLE")
        a = T.owner_proof(action, "och.tuple", ledgerEpoch=F.LEP1)
        b = T.owner_proof(action, "och.tuple", ledgerEpoch=F.LEP1, registryTupleVersion="registry.synthetic.v2")
        self.assertNotEqual(a.challenge.challenge_digest(), b.challenge.challenge_digest())
        c = T.owner_proof(action, "och.tuple", ledgerEpoch=F.LEP2)
        self.assertNotEqual(a.challenge.challenge_digest(), c.challenge.challenge_digest())


# --------------------------------------- 17. future crash model (S1-S6) ---

class CrashModelAcrossRecoveryTests(unittest.TestCase):
    """What survives a recovery between each step of the B1b-3b sequence."""

    def point(self, steps: int) -> F.Host:
        host = F.Host()
        actions = [lambda: host.prepare("c"), lambda: host.consume("c"), lambda: host.issue("c"),
                   lambda: host.reserve("aev.c", "prop.c"), lambda: None,
                   lambda: host.confirm("aev.c", "adm.c", "rev.c")]
        for action in actions[:steps]:
            action()
        return host

    def test_every_crash_point(self):
        expected = {
            # steps: (challenge state, use state, owner re-authorization, reconciliation)
            1: (RL.VOIDED_BY_RECOVERY, None, True, False),                  # S1 prepared
            2: (RL.CONSUMED, None, True, False),                            # S2 consumed, unsigned
            3: (RL.CONSUMED, None, True, False),                            # S3 signed, unreserved
            4: (RL.CONSUMED, RL.QUARANTINED_BY_RECOVERY, True, True),       # S4 reserved
            5: (RL.CONSUMED, RL.QUARANTINED_BY_RECOVERY, True, True),       # S5 L04 may have committed
            6: (RL.CONSUMED, RL.USE_CONSUMED, False, False),                # S6 confirmed
        }
        for steps, (challenge, use, reauthorize, reconcile) in expected.items():
            with self.subTest(step=f"S{steps}"):
                host = self.point(steps)
                ack = host.recover()
                self.assertEqual(host.state.challenge("c")["state"], challenge)
                self.assertEqual((host.state.use("aev.c") or {}).get("state"), use)
                self.assertEqual("c" in ack["ownerReauthorizationRequired"], reauthorize)
                self.assertEqual("aev.c" in ack["reconciliationRequired"], reconcile)
                ready = host.readiness()
                self.assertTrue(ready.ready)
                # Nothing from the old epoch can progress in the new one.
                for fn in (lambda: host.state.consume("c", ready=ready),
                           lambda: host.state.issue("c", "aev.c2", F.digest("x"), ready=ready),
                           lambda: host.state.reserve("aev.c", F.digest("evidence aev.c"), F.E2, "p", ready=ready),
                           lambda: host.state.confirm("aev.c", "adm.x", "rev.x", ready=ready)):
                    self.assertIsNotNone(refusal(fn))


# --------------------------------------- structural isolation and record ---

def _imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            found.add(node.module or "")
    return found


class StructuralTests(unittest.TestCase):
    def test_verifier_side_modules_hold_public_material_only(self):
        for module in (R, RA):
            path = Path(module.__file__)
            source = path.read_text(encoding="utf-8")
            with self.subTest(module=path.name):
                for forbidden in ("Ed25519PrivateKey", "from_private_bytes", "private_bytes",
                                  "lilith_authority_signer", "synthetic_recovery_ledger", ".sign(", ".apply("):
                    self.assertNotIn(forbidden, source)
                for forbidden in ("os", "subprocess", "socket", "urllib", "http", "sqlite3", "pathlib",
                                  "lilith_memory_broker", "lilith_memory.config", "lilith_memory.privacy_governance"):
                    self.assertFalse(any(n == forbidden or n.startswith(forbidden + ".") for n in _imports(path)),
                                     forbidden)
                for forbidden in ("os.environ", "getenv", "open(", "/home/"):
                    self.assertNotIn(forbidden, source)

    def test_recovery_ledger_is_pure_and_takes_no_seed(self):
        path = SIGNER_PACKAGE / "synthetic_recovery_ledger.py"
        source = path.read_text(encoding="utf-8")
        for forbidden in ("os", "sys", "subprocess", "socket", "pathlib", "sqlite3", "urllib", "http", "time",
                          "random", "secrets", "lilith_memory_broker"):
            self.assertFalse(any(n == forbidden or n.startswith(forbidden + ".") for n in _imports(path)), forbidden)
        for forbidden in ("open(", "os.environ", "getenv", "from_private_bytes", "datetime.now", "token_hex"):
            self.assertNotIn(forbidden, source)

    def test_new_modules_are_not_reachable_from_runtime_code(self):
        runtime = [p for p in list((ROOT / "services/core-api").rglob("*.py"))
                   + list((ROOT / "services/memory-broker").rglob("*.py")) + list((ROOT / "scripts").rglob("*.py"))
                   if ".venv" not in p.parts and "tests" not in p.parts]
        for path in runtime:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for forbidden in ("recovery_contracts", "recovery_admission", "synthetic_recovery_ledger"):
                with self.subTest(path=path.name, forbidden=forbidden):
                    self.assertIsNone(re.search(rf"(?<![A-Za-z0-9_]){forbidden}(?![A-Za-z0-9_])", text))

    def test_gate_entry_points_take_public_material_only(self):
        for function in (RA.RecoveryBoundAdmissionGateV1.__init__, RA.verify_historical_accepted_memory,
                         R.verify_recovery_witness, RL.evaluate_restore_readiness):
            parameters = set(inspect.signature(function).parameters)
            with self.subTest(function=function.__qualname__):
                self.assertFalse({p for p in parameters if "private" in p or "seed" in p or "signer" in p
                                  or p.endswith("_key")})

    def test_existing_vectors_are_unchanged(self):
        import test_b1b3b_broker_signing_l04_v2 as B3B
        import hashlib
        for relative, expected in B3B.GOLDEN_SHA256.items():
            with self.subTest(path=relative):
                self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), expected)

    def test_implementation_record_states_the_honest_status(self):
        text = RECORD.read_text(encoding="utf-8")
        for status in ("**SOURCE IMPLEMENTED**", "**TEST PROVEN**", "**LIVE WITNESS ABSENT**",
                       "**WHOLE-HOST ROLLBACK UNRESOLVED**", "**REAL AUTHORITY ABSENT**"):
            self.assertIn(status, text)
        self.assertNotRegex(text, r"(?i)B1b-3 (is )?(complete|done|closed)\b")


if __name__ == "__main__":
    unittest.main()
