"""15B2b-B1b-3e rotation / revocation / restore / recovery source contracts (TEST-ONLY).

Design: docs/architecture/slice-15b2b-b1b3e-rotation-revocation-recovery.md.
Record: docs/architecture/slice-15b2b-b1b3e-source-contracts.md.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import inspect
import json
import re
import sys
import unittest
from pathlib import Path

import synthetic_authority as SA  # noqa: F401  (sets sys.path)
import synthetic_b1b3e as F
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
from lilith_authority_signer import synthetic_recovery_ledger as RL
from lilith_authority_signer import synthetic_witness_v2 as W2
from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import authority_verifier as AV
from lilith_owner_memory import contracts as K
from lilith_owner_memory import recovery_contracts as R
from lilith_owner_memory import rotation_contracts as RC
from lilith_memory import owner_proof as P

ROOT = SA.ROOT
PACKAGE = ROOT / "services/owner-memory-control/lilith_owner_memory"
SIGNER_PACKAGE = ROOT / "services/owner-memory-control/lilith_authority_signer"
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-source-contracts.md"
GOLDEN_SHA256 = "48c0114d2d4bb488d3e247125af5284b6fdce700268a69d6c2d3e7684d826a84"


def _imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            found.add(node.module or "")
    return found


def _resign(document: dict, separator: bytes, signer: str = "root") -> dict:
    return F.sign({k: v for k, v in document.items() if k != "signature"}, separator, signer)


def _head_plan(scenario: F.Scenario, authorization: dict, *, prior=None, target=None, at=None):
    return RC.plan_registry_head_advance(chain=scenario.writer.facts(), authorization=authorization,
                                         registry_root=F.root(), prior_registry=prior or F.v3(),
                                         target_registry=target or F.v4(), updated_at=at or scenario.tick())


def _witness_step(previous: RC.RecoveryWitnessV2, **changes) -> RC.RecoveryWitnessV2:
    base = dict(witness_version=previous.witness_version + 1, previous_witness_digest=previous.digest)
    base.update(changes)
    return dataclasses.replace(previous, **base)


# ----------------------------------------------- separators and registry digest ---

class SeparatorAndDigestTests(unittest.TestCase):
    def test_separators_are_frozen_and_distinct_from_every_earlier_one(self):
        self.assertEqual(RC.EPOCH_ADVANCE_AUTHORIZATION_DOMAIN_SEPARATOR, b"LILITH_EPOCH_ADVANCE_AUTHORIZATION_V1\x00")
        self.assertEqual(RC.REGISTRY_HEAD_ADVANCE_AUTHORIZATION_DOMAIN_SEPARATOR,
                         b"LILITH_REGISTRY_HEAD_ADVANCE_AUTHORIZATION_V1\x00")
        self.assertEqual(RC.WITNESS_V2_DOMAIN_SEPARATOR, b"LILITH_RECOVERY_WITNESS_V2\x00")
        earlier = {A.REGISTRY_DOMAIN_SEPARATOR, A.OWNER_EVIDENCE_DOMAIN_SEPARATOR,
                   A.PRIVACY_AUTHORIZATION_DOMAIN_SEPARATOR, K.EVIDENCE_DOMAIN_SEPARATOR,
                   K.CHALLENGE_V2_DOMAIN_SEPARATOR, K.ASSERTION_DIGEST_DOMAIN_SEPARATOR, P.DOMAIN_SEPARATOR,
                   R.RECOVERY_EPOCH_DOMAIN_SEPARATOR, R.WITNESS_DOMAIN_SEPARATOR, RL.LEDGER_HEAD_DOMAIN_SEPARATOR}
        new = {RC.EPOCH_ADVANCE_AUTHORIZATION_DOMAIN_SEPARATOR, RC.REGISTRY_HEAD_ADVANCE_AUTHORIZATION_DOMAIN_SEPARATOR,
               RC.WITNESS_V2_DOMAIN_SEPARATOR}
        self.assertEqual(len(earlier), 10)
        self.assertEqual(len(new), 3)
        self.assertFalse(earlier & new)
        for separator in earlier | new:
            self.assertTrue(separator.endswith(b"\x00"))

    def test_registry_digest_is_the_exact_k_root_signed_bytes(self):
        registry = F.v3()
        golden = json.loads((ROOT / "services/owner-memory-control/tests/authority_b1b3a_golden.json")
                            .read_text(encoding="utf-8"))
        # The one canonical digest equals the frozen B1b-3a registrySigningDigest.
        self.assertEqual(RC.registry_digest(golden["registry"]), golden["registrySigningDigest"])
        self.assertEqual(RC.registry_digest(registry), golden["registrySigningDigest"])
        unsigned = {k: v for k, v in registry.items() if k != "signature"}
        self.assertEqual(RC.registry_digest(registry),
                         hashlib.sha256(A.REGISTRY_DOMAIN_SEPARATOR + K._canonical(unsigned)).hexdigest())

    def test_registry_digest_excludes_only_the_signature_and_representation(self):
        registry = F.v3()
        resigned = {**registry, "signature": SA.b64(b"\x00" * 64)}
        self.assertEqual(RC.registry_digest(resigned), RC.registry_digest(registry))
        reordered = json.loads(json.dumps(registry, indent=4, sort_keys=False))
        self.assertEqual(RC.registry_digest(reordered), RC.registry_digest(registry))
        for name in A.REGISTRY_SIGNED_FIELDS - {"keys"}:
            with self.subTest(field=name):
                changed = dict(registry)
                changed[name] = {"x": 1} if isinstance(registry[name], dict) else f"{registry[name]}x"
                self.assertNotEqual(RC.registry_digest(changed), RC.registry_digest(registry))
        changed = copy.deepcopy(registry)
        changed["keys"][0]["createdAt"] = "2026-09-10T00:00:01Z"
        self.assertNotEqual(RC.registry_digest(changed), RC.registry_digest(registry))

    def test_registry_digest_refuses_other_shapes(self):
        for bad in (None, [], {"registryVersion": 3}, {**F.v3(), "extra": 1}):
            with self.subTest(bad=type(bad).__name__), self.assertRaises((P.OwnerProofError, TypeError)):
                RC.registry_digest(bad)


# ------------------------------------------------ EpochAdvanceAuthorizationV1 ---

class EpochAdvanceAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.s = F.Scenario().to_current()
        self.auth = F.epoch_authorization(self.s.witness)

    def verify(self, authorization, environment=F.ENV, root=None):
        return RC.verify_epoch_advance_authorization(authorization=authorization, registry_root=root or F.root(),
                                                     environment=environment)

    def test_valid_authorization_verifies_and_binds_every_field(self):
        result = self.verify(self.auth)
        self.assertTrue(result.verified, result)
        parsed = result.authorization
        self.assertEqual(parsed.prior_recovery_epoch, F.E2)
        self.assertEqual(parsed.successor_recovery_epoch, F.E3)
        self.assertEqual(parsed.target, RC.registry_head(F.v5()))
        self.assertEqual(parsed.expected_prior_witness_digest, self.s.witness.digest)
        self.assertEqual(set(self.auth), RC.EPOCH_ADVANCE_AUTHORIZATION_FIELDS)
        for name in ("protocol", "schemaVersion", "environment", "priorRecoveryEpoch", "successorRecoveryEpoch",
                     "targetRegistryVersion", "targetRegistryDigest", "expectedPriorWitnessVersion",
                     "expectedPriorWitnessDigest", "authorizationId", "nonce", "issuedAt", "notAfter", "reason",
                     "registryRootKeyId", "signature"):
            self.assertIn(name, RC.EPOCH_ADVANCE_AUTHORIZATION_FIELDS)

    def test_tampering_any_signed_field_fails(self):
        replacements = {
            "protocol": RC.REGISTRY_HEAD_ADVANCE_AUTHORIZATION_PROTOCOL, "schemaVersion": 2,
            "authorizationId": "eaa.other", "nonce": F.nonce("other"), "environment": "dev",
            "reason": "KEY_COMPROMISE", "priorRecoveryEpoch": SA.OLD_EPOCH.to_dict(),
            "successorRecoveryEpoch": F.E3_FORK.to_dict(), "targetRegistryVersion": 6,
            "targetRegistryDigest": F.digest("other target"), "expectedPriorWitnessVersion": 99,
            "expectedPriorWitnessDigest": F.digest("other witness"), "issuedAt": "2026-09-27T07:31:00Z",
            "notAfter": "2026-09-28T07:31:00Z",
        }
        self.assertEqual(set(replacements) | {"registryRootKeyId", "signature"}, RC.EPOCH_ADVANCE_AUTHORIZATION_FIELDS)
        for name, value in replacements.items():
            with self.subTest(field=name):
                result = self.verify({**self.auth, name: value})
                self.assertFalse(result.verified)
                self.assertEqual(result.reason, "AUTHORIZATION_SIGNATURE_INVALID")
        self.assertEqual(self.verify({**self.auth, "registryRootKeyId": "test-only.other-root"}).reason,
                         "AUTHORIZATION_ROOT_MISMATCH")
        self.assertEqual(self.verify({**self.auth, "signature": SA.b64(b"\x01" * 64)}).reason,
                         "AUTHORIZATION_SIGNATURE_INVALID")

    def test_wrong_separator_and_wrong_root_fail(self):
        for separator in (A.REGISTRY_DOMAIN_SEPARATOR, RC.REGISTRY_HEAD_ADVANCE_AUTHORIZATION_DOMAIN_SEPARATOR,
                          RC.WITNESS_V2_DOMAIN_SEPARATOR, b""):
            with self.subTest(separator=separator):
                self.assertEqual(self.verify(_resign(self.auth, separator)).reason, "AUTHORIZATION_SIGNATURE_INVALID")
        self.assertEqual(self.verify(_resign(self.auth, RC.EPOCH_ADVANCE_AUTHORIZATION_DOMAIN_SEPARATOR,
                                             "attacker-root")).reason, "AUTHORIZATION_SIGNATURE_INVALID")
        # A registry-root that is not test-only is refused outright.
        real_looking = A.TrustedRegistryRootV1(root_key_id="registry-root-1", environment=F.ENV,
                                               public_key=F.root().public_key)
        self.assertEqual(self.verify(self.auth, root=real_looking).reason, "REGISTRY_ROOT_NOT_TEST_ONLY")

    def test_contract_rules(self):
        cases = {
            "EPOCH_FORKED": dict(successorRecoveryEpoch=A.RecoveryEpochV1(2, F.E3.random).to_dict()),
            "EPOCH_NOT_SUCCESSOR": dict(successorRecoveryEpoch=A.RecoveryEpochV1(4, F.E3.random).to_dict()),
            "INVALID_VALIDITY_WINDOW": dict(notAfter="2026-09-27T07:30:00Z"),
            "INVALID_NONCE": dict(nonce="NOT-HEX"),
            "INVALID_AUTHORIZATION_ID": dict(authorizationId=""),
            "INVALID_TARGET_REGISTRY_DIGEST": dict(targetRegistryDigest="abc"),
            "INVALID_EXPECTED_PRIOR_WITNESS_DIGEST": dict(expectedPriorWitnessDigest="z" * 64),
            "INVALID_EXPECTED_PRIOR_WITNESS_VERSION": dict(expectedPriorWitnessVersion=0),
            "INVALID_REASON": dict(reason="BECAUSE"),
        }
        for code, overrides in cases.items():
            with self.subTest(code=code):
                result = self.verify(F.epoch_authorization(self.s.witness, **overrides))
                self.assertEqual((result.reason, result.detail), ("AUTHORIZATION_INVALID", code))
        # Same counter, different random is FORKED even at counter + 0, never succession.
        self.assertEqual(R.compare_epochs(F.E2, A.RecoveryEpochV1(2, F.E3.random)), R.EPOCH_FORKED)
        # counter + 1 with the prior random reused is refused.
        reused = F.epoch_authorization(self.s.witness, successorRecoveryEpoch=A.RecoveryEpochV1(3, F.E2.random).to_dict())
        self.assertEqual(self.verify(reused).detail, "EPOCH_RANDOM_REUSED")
        self.assertEqual(self.verify(F.epoch_authorization(self.s.witness, environment="dev")).reason,
                         "AUTHORIZATION_ENVIRONMENT_MISMATCH")
        self.assertEqual(self.verify(self.auth, environment="dev").reason, "AUTHORIZATION_ENVIRONMENT_MISMATCH")
        self.assertEqual(self.verify(F.epoch_authorization(self.s.witness, schemaVersion=2)).reason,
                         "UNSUPPORTED_SCHEMA_VERSION")
        self.assertEqual(self.verify(None).reason, "AUTHORIZATION_MISSING")
        self.assertEqual(self.verify({k: v for k, v in self.auth.items() if k != "signature"}).reason,
                         "AUTHORIZATION_UNSIGNED")
        self.assertEqual(self.verify({**self.auth, "extra": 1}).reason, "AUTHORIZATION_MALFORMED")
        # The other authorization type is never accepted in its place.
        head = F.head_authorization()
        self.assertEqual(self.verify(head).reason, "AUTHORIZATION_MALFORMED")

    def test_execution_requires_the_exact_transition(self):
        s = self.s
        prior_witness = s.witness
        adopted = W2.adopt_authorized_epoch(s.ledger, authorization=self.auth, witness=prior_witness,
                                            target_registry=F.v5(), registry_root=F.root())

        def plan(authorization=self.auth, target=None, ledger=adopted, chain=None, at=None, prior=None):
            return RC.plan_epoch_advance(chain=chain or s.writer.facts(), authorization=authorization,
                                         registry_root=F.root(), prior_registry=prior or s.registry,
                                         target_registry=target or F.v5(), adoption_record=ledger.log[-1],
                                         ledger_sequence=ledger.sequence, ledger_head=ledger.head,
                                         updated_at=at or s.tick())

        self.assertTrue(plan().planned, plan())
        # stale prior witness: authorization bound to an older witness state
        stale = F.epoch_authorization(RC.RecoveryWitnessV2.from_verified_dict(s.writer.chain[-2]))
        self.assertEqual(plan(stale).reason, "PRIOR_WITNESS_MISMATCH")
        # wrong epoch
        wrong_epoch = F.epoch_authorization(prior_witness, priorRecoveryEpoch=SA.OLD_EPOCH.to_dict(),
                                            successorRecoveryEpoch=A.RecoveryEpochV1(2, F.E3.random).to_dict())
        self.assertEqual(plan(wrong_epoch).reason, "PRIOR_EPOCH_MISMATCH")
        # wrong target registry
        self.assertEqual(plan(target=F.v5(version=5, epoch=F.E3_FORK)).reason, "TARGET_EPOCH_MISMATCH")
        other = F.epoch_authorization(prior_witness, targetRegistryDigest=F.digest("not v5"))
        self.assertEqual(plan(other).reason, "TARGET_REGISTRY_MISMATCH")
        # expired and not yet valid (clock checks are defence in depth only)
        self.assertEqual(plan(at="2026-09-28T08:00:00Z").reason, "AUTHORIZATION_EXPIRED")
        future = F.epoch_authorization(prior_witness, issuedAt="2026-09-28T06:00:00Z",
                                       notAfter="2026-09-29T06:00:00Z")
        self.assertEqual(plan(future).reason, "AUTHORIZATION_NOT_YET_VALID")
        # C-4: the witness executes only over a journalled adoption naming this authorization
        self.assertEqual(plan(ledger=s.ledger).reason, "ADOPTION_RECORD_MISMATCH")
        # prior registry must be the witnessed head
        self.assertEqual(plan(prior=F.v3()).reason, "PRIOR_REGISTRY_NOT_HEAD")

    def test_replay_is_prevented_without_relying_on_the_clock(self):
        s = self.s
        s.epoch_advance(authorization=self.auth)
        consuming = s.writer.facts().entry_consuming(self.auth["authorizationId"])
        self.assertIsNotNone(consuming)
        self.assertEqual(consuming[1].current_recovery_epoch, F.E3)
        # Same authorization again, well inside its clock window: prior-witness binding fails.
        plan = RC.plan_epoch_advance(chain=s.writer.facts(), authorization=self.auth, registry_root=F.root(),
                                     prior_registry=s.registry, target_registry=F.v5(),
                                     adoption_record=s.ledger.log[-1], ledger_sequence=s.ledger.sequence,
                                     ledger_head=s.ledger.head, updated_at=s.tick())
        self.assertEqual(plan.reason, "PRIOR_WITNESS_MISMATCH")
        # The adoption step refuses the replay as well.
        with self.assertRaises(W2.AdoptionRefusal) as caught:
            W2.adopt_authorized_epoch(s.ledger, authorization=self.auth, witness=s.witness, target_registry=F.v5(),
                                      registry_root=F.root())
        self.assertEqual(caught.exception.reason, "PRIOR_WITNESS_MISMATCH")

    def test_fresh_authorization_reusing_a_consumed_id_is_refused(self):
        s = self.s
        s.epoch_advance(authorization=self.auth)
        e4 = A.RecoveryEpochV1(4, F.nonce("epoch 4"))
        keys = F._keys(F.v5())
        keys[F.EPOCH3_KEY]["retiredAt"] = "2026-09-27T13:00:00Z"
        keys["actor.b1b3e-epoch4-1"] = SA.key_record("actor.b1b3e-epoch4-1", seed_name=F.PREDECESSOR,
                                                     publicKey=F.public_b64("other"), createdAt="2026-09-27T13:00:00Z",
                                                     notBefore="2026-09-27T13:00:00Z", recoveryEpoch=e4.to_dict(),
                                                     registryVersion=6)
        target = F.registry_from(keys, registryVersion=6, recoveryEpoch=e4.to_dict(), issuedAt="2026-09-27T13:05:00Z")
        # Correctly bound to the current witness and target, but reusing the consumed ID.
        reuse = F.epoch_authorization(s.witness, target=target, priorRecoveryEpoch=F.E3.to_dict(),
                                      successorRecoveryEpoch=e4.to_dict())
        adopted = W2.adopt_authorized_epoch(s.ledger, authorization=reuse, witness=s.witness, target_registry=target,
                                            registry_root=F.root())
        plan = RC.plan_epoch_advance(chain=s.writer.facts(), authorization=reuse, registry_root=F.root(),
                                     prior_registry=s.registry, target_registry=target,
                                     adoption_record=adopted.log[-1], ledger_sequence=adopted.sequence,
                                     ledger_head=adopted.head, updated_at=s.tick())
        self.assertEqual(plan.reason, "AUTHORIZATION_CONSUMED")
        fresh = F.epoch_authorization(s.witness, target=target, priorRecoveryEpoch=F.E3.to_dict(),
                                      successorRecoveryEpoch=e4.to_dict(), authorizationId="eaa.b1b3e-recovery-2")
        adopted = W2.adopt_authorized_epoch(s.ledger, authorization=fresh, witness=s.witness, target_registry=target,
                                            registry_root=F.root())
        self.assertTrue(RC.plan_epoch_advance(chain=s.writer.facts(), authorization=fresh, registry_root=F.root(),
                                              prior_registry=s.registry, target_registry=target,
                                              adoption_record=adopted.log[-1], ledger_sequence=adopted.sequence,
                                              ledger_head=adopted.head, updated_at=s.tick()).planned)

    def test_consumed_id_and_reused_random_are_refused(self):
        s = self.s
        s.epoch_advance(authorization=self.auth)
        facts = s.writer.facts()
        self.assertIn(self.auth["authorizationId"], facts.consumed_authorization_ids)
        self.assertIn(F.E2.random, facts.seen_epoch_randoms)
        # Next epoch reusing E2's random: refused by the chain's seen-random set.
        target = F.v5(version=6, epoch=F.E4_REUSING_E2_RANDOM)
        auth = F.epoch_authorization(s.witness, target=target, priorRecoveryEpoch=F.E3.to_dict(),
                                     successorRecoveryEpoch=F.E4_REUSING_E2_RANDOM.to_dict(),
                                     authorizationId="eaa.b1b3e-recovery-2")
        plan = RC.plan_epoch_advance(chain=facts, authorization=auth, registry_root=F.root(), prior_registry=s.registry,
                                     target_registry=target, adoption_record={}, ledger_sequence=s.ledger.sequence,
                                     ledger_head=s.ledger.head, updated_at=s.tick())
        self.assertEqual(plan.reason, "EPOCH_RANDOM_REUSED")


# ----------------------------------------- RegistryHeadAdvanceAuthorizationV1 ---

class RegistryHeadAdvanceTests(unittest.TestCase):
    def setUp(self):
        self.s = F.Scenario()

    def test_valid_n_to_n_plus_1_executes_and_binds_the_head(self):
        auth = F.head_authorization()
        self.assertTrue(_head_plan(self.s, auth).planned)
        signed = self.s.writer.execute_registry_head_advance(authorization=auth, prior_registry=F.v3(),
                                                             target_registry=F.v4(), registry_root=F.root(),
                                                             updated_at=self.s.tick())
        witness = RC.RecoveryWitnessV2.from_verified_dict(signed)
        self.assertEqual(witness.registry_head, RC.registry_head(F.v4()))
        self.assertEqual(witness.consumed_authorization_id, auth["authorizationId"])
        self.assertEqual(witness.current_recovery_epoch, F.E2)
        self.assertEqual(set(auth), RC.REGISTRY_HEAD_ADVANCE_AUTHORIZATION_FIELDS)

    def test_same_version_and_gaps_are_refused_by_the_contract(self):
        same = F.head_authorization(target=F.v3(), targetRegistryDigest=F.digest("other v3"))
        gap = F.head_authorization(targetRegistryVersion=5)
        for authorization, code in ((same, "SAME_VERSION_ADVANCE"), (gap, "TARGET_NOT_CONTIGUOUS")):
            with self.subTest(code=code):
                result = RC.verify_registry_head_advance_authorization(authorization=authorization,
                                                                       registry_root=F.root(), environment=F.ENV)
                self.assertEqual((result.reason, result.detail), ("AUTHORIZATION_INVALID", code))
                self.assertEqual(_head_plan(self.s, authorization).reason, "AUTHORIZATION_NOT_VERIFIED")

    def test_stale_prior_head_target_mismatch_and_epoch(self):
        stale = F.head_authorization(priorRegistryDigest=F.digest("some other v3"))
        self.assertEqual(_head_plan(self.s, stale).reason, "PRIOR_HEAD_MISMATCH")
        fork_target = F.head_authorization(target=F.v4_fork())
        self.assertEqual(_head_plan(self.s, fork_target, target=F.v4()).reason, "TARGET_REGISTRY_MISMATCH")
        other_epoch = F.head_authorization(recoveryEpoch=F.E3.to_dict())
        self.assertEqual(_head_plan(self.s, other_epoch).reason, "AUTHORIZATION_EPOCH_MISMATCH")
        e3_target = F.v5(version=4)
        self.assertEqual(_head_plan(self.s, F.head_authorization(target=e3_target), target=e3_target).reason,
                         "TARGET_EPOCH_MISMATCH")
        self.assertEqual(_head_plan(self.s, F.head_authorization(), prior=F.v4()).reason, "PRIOR_REGISTRY_NOT_HEAD")

    def test_non_additive_target_is_refused(self):
        keys = F.v4_keys()
        del keys["actor.retired-1"]
        target = F.v4(keys=keys)
        plan = _head_plan(self.s, F.head_authorization(target=target), target=target)
        self.assertEqual((plan.reason, plan.detail), ("REGISTRY_SUCCESSION_INVALID", "SUCCESSION_RECORD_REMOVED"))

    def test_clock_window_is_defence_in_depth(self):
        auth = F.head_authorization()
        self.assertEqual(_head_plan(self.s, auth, at="2026-09-28T07:00:01Z").reason, "AUTHORIZATION_EXPIRED")
        future = F.head_authorization(issuedAt="2026-09-28T00:00:00Z", notAfter="2026-09-29T00:00:00Z")
        self.assertEqual(_head_plan(self.s, future).reason, "AUTHORIZATION_NOT_YET_VALID")
        self.assertEqual(_head_plan(self.s, auth, at="2026-09-27T07:59:00Z").reason, "WITNESS_TIME_REGRESSION")

    def test_consumed_id_is_refused_even_with_a_matching_prior_head(self):
        s = F.Scenario().to_current()
        consumed = s.authorization["authorizationId"]
        v5 = F.registry_from(F._keys(F.v4()), registryVersion=5, issuedAt="2026-09-27T10:00:00Z")
        again = F.head_authorization(prior=F.v4(), target=v5, authorizationId=consumed)
        plan = RC.plan_registry_head_advance(chain=s.writer.facts(), authorization=again, registry_root=F.root(),
                                             prior_registry=F.v4(), target_registry=v5, updated_at=s.tick())
        self.assertEqual(plan.reason, "AUTHORIZATION_CONSUMED")

    def test_competing_authorizations_first_executed_wins(self):
        first = F.head_authorization(target=F.v4())
        second = F.head_authorization(target=F.v4_fork(), authorizationId="rhaa.b1b3e-rotation-competing",
                                      nonce=F.nonce("competing"))
        self.assertTrue(_head_plan(self.s, second, target=F.v4_fork()).planned)
        self.s.authorize()
        self.s.publish()
        plan = _head_plan(self.s, second, target=F.v4_fork())
        self.assertEqual(plan.reason, "PRIOR_HEAD_MISMATCH")
        # Replay of the executed one fails the same way, inside its clock window.
        self.assertEqual(_head_plan(self.s, first).reason, "PRIOR_HEAD_MISMATCH")
        with self.assertRaises(W2.WitnessV2Refusal) as caught:
            self.s.writer.execute_registry_head_advance(authorization=second, prior_registry=F.v3(),
                                                        target_registry=F.v4_fork(), registry_root=F.root(),
                                                        updated_at=self.s.tick())
        self.assertEqual(caught.exception.reason, "PRIOR_HEAD_MISMATCH")

    def test_signed_registry_is_not_the_effective_head_until_executed(self):
        # signed registry != effective current registry head
        # registry exists != permission to advance freshness
        witness = self.s.witness
        staged = RC.verify_registry_at_witness_head(witness=witness, registry=F.v4(), registry_root=F.root())
        self.assertEqual(staged.reason, "REGISTRY_NOT_WITNESSED_HEAD")
        self.assertTrue(AV.verify_authority_registry(
            context=RC.witness_v2_authority_context(witness, registry_root=F.root(), purpose=A.NEW_ADMISSION),
            registry=F.v4()).verified)  # K-ROOT-valid bytes, yet not the head
        self.assertTrue(RC.verify_registry_at_witness_head(witness=witness, registry=F.v3(),
                                                           registry_root=F.root()).verified)
        # K-ROOT authorization != witness execution: signing it changes nothing.
        F.head_authorization()
        self.assertEqual(self.s.witness.registry_head, RC.registry_head(F.v3()))

    def test_cross_type_and_wrong_separator(self):
        epoch_auth = F.epoch_authorization(self.s.witness)
        self.assertEqual(_head_plan(self.s, epoch_auth).detail, "AUTHORIZATION_MALFORMED")
        wrong = _resign(F.head_authorization(), RC.EPOCH_ADVANCE_AUTHORIZATION_DOMAIN_SEPARATOR)
        self.assertEqual(_head_plan(self.s, wrong).detail, "AUTHORIZATION_SIGNATURE_INVALID")
        rogue = _resign(F.head_authorization(), RC.REGISTRY_HEAD_ADVANCE_AUTHORIZATION_DOMAIN_SEPARATOR,
                        "attacker-root")
        self.assertEqual(_head_plan(self.s, rogue).detail, "AUTHORIZATION_SIGNATURE_INVALID")

    def test_tampering_any_signed_field_fails(self):
        auth = F.head_authorization()
        replacements = {
            "protocol": RC.EPOCH_ADVANCE_AUTHORIZATION_PROTOCOL, "schemaVersion": 2, "authorizationId": "x.y",
            "nonce": F.nonce("tamper"), "environment": "dev", "reason": "COMPROMISE_MARKING",
            "recoveryEpoch": F.E3.to_dict(), "priorRegistryVersion": 2, "priorRegistryDigest": F.digest("p"),
            "targetRegistryVersion": 5, "targetRegistryDigest": F.digest("t"), "issuedAt": "2026-09-27T07:00:01Z",
            "notAfter": "2026-09-28T07:00:01Z",
        }
        self.assertEqual(set(replacements) | {"registryRootKeyId", "signature"},
                         RC.REGISTRY_HEAD_ADVANCE_AUTHORIZATION_FIELDS)
        for name, value in replacements.items():
            with self.subTest(field=name):
                result = RC.verify_registry_head_advance_authorization(
                    authorization={**auth, name: value}, registry_root=F.root(), environment=F.ENV)
                self.assertEqual(result.reason, "AUTHORIZATION_SIGNATURE_INVALID")


# ---------------------------------------------------------- RecoveryWitnessV2 ---

class RecoveryWitnessV2Tests(unittest.TestCase):
    def setUp(self):
        self.s = F.Scenario().to_current()
        self.chain = self.s.writer.chain

    def verify_chain(self, chain, anchor=None):
        return RC.verify_witness_v2_chain(anchor=anchor or F.anchor(), chain=list(chain), environment=F.ENV,
                                          registry_root=F.root(),
                                          authority_public_keys=RC._authority_keys(F.v3(), F.v4()))

    def test_valid_chain_and_fields(self):
        result = self.verify_chain(self.chain)
        self.assertTrue(result.verified, result)
        self.assertEqual(set(self.chain[0]), RC.WITNESS_V2_FIELDS)
        head = result.facts.head
        self.assertEqual(head.registry_head, RC.registry_head(F.v4()))
        self.assertEqual(head.minimum_registry_version, 4)  # inherited floor rule = head version
        self.assertEqual(result.facts.consumed_authorization_ids, frozenset({"rhaa.b1b3e-rotation-1"}))

    def test_v1_and_v2_never_parse_as_each_other(self):
        v2 = self.chain[-1]
        self.assertEqual(R.verify_recovery_witness(anchor=F.anchor(), witness=v2, environment=F.ENV,
                                                   registry_root=F.root()).reason, "WITNESS_MALFORMED")
        with self.assertRaises(P.OwnerProofError):
            R.RecoveryWitnessV1.from_verified_dict(v2)
        v1_shape = {k: v for k, v in v2.items() if k not in {"registryVersion", "registryDigest",
                                                              "consumedAuthorizationId"}}
        v1_shape.update(minimumRegistryVersion=4, schemaVersion=1)
        self.assertEqual(RC.verify_recovery_witness_v2(anchor=F.anchor(), witness=v1_shape, environment=F.ENV,
                                                       registry_root=F.root()).reason, "WITNESS_MALFORMED")
        with self.assertRaises(P.OwnerProofError):
            RC.RecoveryWitnessV2.from_verified_dict({**v2, "schemaVersion": 1})

    def test_signature_tamper_and_authority_key_as_witness(self):
        for name in RC.WITNESS_V2_SIGNED_FIELDS - {"witnessKeyId"}:
            with self.subTest(field=name):
                tampered = dict(self.chain[-1])
                tampered[name] = {"counter": 9, "random": "0" * 32} if name == "currentRecoveryEpoch" else (
                    tampered[name] + 1 if isinstance(tampered[name], int) else "x" + str(tampered[name]))
                result = RC.verify_recovery_witness_v2(anchor=F.anchor(), witness=tampered, environment=F.ENV,
                                                       registry_root=F.root())
                self.assertFalse(result.verified)
        rogue = W2.SyntheticWitnessV2SignerV1(signing_key=F.private("rogue-witness"), witness_key_id=F.WITNESS_KEY_ID,
                                              environment=F.ENV)
        rogue.genesis(registry=F.v3(), registry_root=F.root(), ledger=F.seeded_ledger(), updated_at=F.stamp(1))
        self.assertEqual(self.verify_chain(rogue.chain).detail, "0:WITNESS_SIGNATURE_INVALID")
        as_root = R.TrustedWitnessAnchorV1(F.WITNESS_KEY_ID, F.ENV, F.root().public_key)
        self.assertEqual(RC.verify_recovery_witness_v2(anchor=as_root, witness=self.chain[0], environment=F.ENV,
                                                       registry_root=F.root()).reason, "WITNESS_KEY_IS_AUTHORITY_KEY")

    def test_succession_rules(self):
        head = RC.RecoveryWitnessV2.from_verified_dict(self.chain[-1])
        e3 = F.E3
        cases = {
            "WITNESS_REGISTRY_REGRESSION": dict(registry_version=3),
            "WITNESS_REGISTRY_FORK": dict(registry_digest=F.digest("fork")),
            "WITNESS_REGISTRY_GAP": dict(registry_version=6, registry_digest=F.digest("v6"),
                                         consumed_authorization_id="x.gap"),
            "WITNESS_EPOCH_REGRESSION": dict(current_recovery_epoch=A.RecoveryEpochV1(2, F.E3.random)),
            "WITNESS_EPOCH_NOT_SUCCESSOR": dict(current_recovery_epoch=A.RecoveryEpochV1(4, e3.random)),
            "WITNESS_REGISTRY_NOT_ADVANCED_WITH_EPOCH": dict(current_recovery_epoch=e3,
                                                             ledger_head=F.digest("post journal"),
                                                             consumed_authorization_id="x.epoch"),
            "WITNESS_POLICY_CHANGE_WITHOUT_REGISTRY": dict(policy_version="policy.synthetic.v3"),
            "WITNESS_TRANSITION_UNAUTHORIZED": dict(registry_version=5, registry_digest=F.digest("v5")),
            "WITNESS_AUTHORIZATION_WITHOUT_TRANSITION": dict(ledger_sequence=head.ledger_sequence + 1,
                                                             ledger_head=F.digest("next"),
                                                             consumed_authorization_id="x.nothing"),
            "WITNESS_LEDGER_REGRESSION": dict(ledger_sequence=head.ledger_sequence - 1),
            "WITNESS_TIME_REGRESSION": dict(updated_at=head.updated_at.replace(year=2025)),
            "WITNESS_ENVIRONMENT_MISMATCH": dict(environment="dev"),
            "WITNESS_KEY_CHANGED": dict(witness_key_id="test-only.witness.other"),
        }
        for reason, changes in cases.items():
            with self.subTest(reason=reason):
                self.assertEqual(RC.witness_v2_succession_reason(head, _witness_step(head, **changes)), reason)
        self.assertEqual(RC.witness_v2_succession_reason(head, _witness_step(head, witness_version=head.witness_version)),
                         "WITNESS_VERSION_NOT_SUCCESSOR")
        self.assertEqual(RC.witness_v2_succession_reason(head, _witness_step(head, previous_witness_digest=F.digest("x"))),
                         "WITNESS_CHAIN_BROKEN")
        self.assertIsNone(RC.witness_v2_succession_reason(head, _witness_step(head)))  # no change at all: allowed
        self.assertEqual(set(RC.WITNESS_V2_SUCCESSION_REASONS) - set(cases),
                         {"WITNESS_VERSION_NOT_SUCCESSOR", "WITNESS_CHAIN_BROKEN"})

    def test_forked_and_stale_witnesses(self):
        genesis_only = self.chain[:1]
        other = W2.SyntheticWitnessV2SignerV1(signing_key=F.private("witness"), witness_key_id=F.WITNESS_KEY_ID,
                                              environment=F.ENV)
        other.restore_chain(genesis_only)
        other.record_ledger_advance(ledger=self.s.ledger, updated_at=F.stamp(500))  # divergent v2
        forked = list(self.chain[:1]) + [other.chain[-1]] + list(self.chain[2:])
        result = self.verify_chain(forked)
        self.assertEqual((result.reason, result.detail), ("CHAIN_SUCCESSION_INVALID", "WITNESS_CHAIN_BROKEN"))
        self.assertEqual(self.verify_chain(self.chain[1:]).reason, "CHAIN_NOT_FROM_GENESIS")
        self.assertEqual(self.verify_chain([]).reason, "CHAIN_EMPTY")
        # A duplicated consumed ID in a chain is a replay.
        head = RC.RecoveryWitnessV2.from_verified_dict(self.chain[-1])
        parsed = [RC.RecoveryWitnessV2.from_verified_dict(w) for w in self.chain]
        duplicate = _witness_step(head, registry_version=5, registry_digest=F.digest("v5"),
                                  consumed_authorization_id="rhaa.b1b3e-rotation-1")
        self.assertEqual(RC.witness_v2_chain_facts(parsed + [duplicate]).reason, "CHAIN_AUTHORIZATION_REPLAYED")

    def test_writer_refuses_non_successors_and_genesis_over_a_chain(self):
        with self.assertRaises(W2.WitnessV2Refusal):
            self.s.writer.genesis(registry=F.v3(), registry_root=F.root(), ledger=self.s.ledger, updated_at=F.stamp(900))
        with self.assertRaises(W2.WitnessV2Refusal) as caught:
            self.s.writer.record_ledger_advance(ledger=self.s.ledger, updated_at=F.stamp(900))
        self.assertEqual(caught.exception.reason, "LEDGER_NOT_ADVANCING")
        for bad in (dict(environment="dev"), dict(witness_key_id="witness.not-test-only")):
            kwargs = dict(signing_key=F.private("witness"), witness_key_id=F.WITNESS_KEY_ID, environment=F.ENV)
            kwargs.update(bad)
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                W2.SyntheticWitnessV2SignerV1(**kwargs)
        with self.assertRaises(TypeError):
            copy.deepcopy(self.s.writer)

    def test_v2_context_takes_its_floor_from_the_exact_head(self):
        head = RC.RecoveryWitnessV2.from_verified_dict(self.chain[-1])
        context = RC.witness_v2_authority_context(head, registry_root=F.root(), purpose=A.NEW_ADMISSION)
        self.assertEqual(context.trusted_minimum_registry_version, 4)
        self.assertEqual(context.expected_recovery_epoch, F.E2)
        self.assertEqual(RC.verify_registry_at_witness_head(witness=head, registry=F.v4_fork(),
                                                            registry_root=F.root()).reason,
                         "REGISTRY_HEAD_DIGEST_MISMATCH")
        self.assertEqual(RC.verify_registry_at_witness_head(witness=head, registry=F.v3(),
                                                            registry_root=F.root()).reason, "REGISTRY_DOWNGRADE")
        self.assertEqual(RC.verify_registry_at_witness_head(witness=head, registry=None,
                                                            registry_root=F.root()).reason, "REGISTRY_MISSING")


# ------------------------------------------------------------- registry succession ---

class RegistrySuccessionTests(unittest.TestCase):
    def check(self, following, previous=None, trusted=None):
        return RC.verify_registry_succession(previous or F.v3(), following, trusted_head=trusted)

    def with_record(self, key_id, **changes):
        keys = F.v4_keys()
        keys[key_id].update(changes)
        return F.v4(keys=keys)

    def test_valid_additive_successor(self):
        self.assertTrue(self.check(F.v4()).succeeds)
        self.assertTrue(self.check(F.v4(), trusted=RC.registry_head(F.v3())).succeeds)
        self.assertTrue(RC.verify_registry_succession(F.v4(), F.v5()).succeeds)  # epoch advance, counter + 1

    def test_history_is_additive(self):
        keys = F.v4_keys()
        del keys["actor.epoch1-1"]
        cases = [
            ("deletion", F.v4(keys=keys), "SUCCESSION_RECORD_REMOVED", "actor.epoch1-1"),
            ("createdAt", self.with_record("actor.retired-1", createdAt="2026-09-09T00:00:00Z"),
             "SUCCESSION_RECORD_MUTATED", "actor.retired-1.createdAt"),
            ("notBefore", self.with_record("actor.retired-1", notBefore="2026-09-11T00:00:00Z"),
             "SUCCESSION_RECORD_MUTATED", "actor.retired-1.notBefore"),
            ("publicKey", self.with_record("actor.retired-1", publicKey=F.public_b64("other")),
             "SUCCESSION_RECORD_MUTATED", "actor.retired-1.publicKey"),
            # Under current contracts evidenceTypes is fixed by signingDomain, so a
            # type rewrite is a domain rewrite; signingDomain is checked first.
            ("signingDomain+evidenceTypes", self.with_record(
                "actor.retired-1", signingDomain=A.PRIVACY, evidenceTypes=[A.PRIVACY_ERASURE_AUTHORIZATION]),
             "SUCCESSION_RECORD_MUTATED", "actor.retired-1.signingDomain"),
            ("recoveryEpoch", self.with_record("actor.epoch1-1", recoveryEpoch=A.RecoveryEpochV1(
                1, F.nonce("rewritten epoch 1")).to_dict()),
             "SUCCESSION_RECORD_MUTATED", "actor.epoch1-1.recoveryEpoch"),
            ("registryVersion", self.with_record("actor.retired-1", registryVersion=1),
             "SUCCESSION_RECORD_MUTATED", "actor.retired-1.registryVersion"),
            ("resurrect retired", self.with_record("actor.retired-1", retiredAt=None),
             "SUCCESSION_LIFECYCLE_REOPENED", "actor.retired-1"),
            ("resurrect revoked", self.with_record("actor.revoked-1", revokedAt=None, revocationReason=None),
             "SUCCESSION_LIFECYCLE_REOPENED", "actor.revoked-1"),
            ("rewrite retiredAt", self.with_record("actor.retired-1", retiredAt="2026-09-25T00:00:00Z"),
             "SUCCESSION_LIFECYCLE_REWRITTEN", "actor.retired-1"),
            ("rewrite revokedAt", self.with_record("actor.revoked-1", revokedAt="2026-09-21T00:00:00Z"),
             "SUCCESSION_LIFECYCLE_REWRITTEN", "actor.revoked-1"),
            ("ROUTINE -> SUPERSEDED", self.with_record("actor.revoked-1", revocationReason="SUPERSEDED"),
             "SUCCESSION_LIFECYCLE_REWRITTEN", "actor.revoked-1"),
            ("compromise cleared", self.with_record("actor.compromised-1", revocationReason="ROUTINE",
                                                    compromisedSince=None),
             "SUCCESSION_COMPROMISE_CLEARED", "actor.compromised-1"),
            ("compromisedSince rewritten", self.with_record("actor.compromised-1",
                                                            compromisedSince="2026-09-23T00:00:00Z"),
             "SUCCESSION_LIFECYCLE_REWRITTEN", "actor.compromised-1"),
        ]
        for name, following, reason, detail in cases:
            with self.subTest(case=name):
                result = self.check(following)
                self.assertEqual(result.reason, reason, result)
                if detail is not None:
                    self.assertEqual(result.detail, detail)

    def test_compromise_escalation_is_the_only_later_lifecycle_change(self):
        escalated = self.with_record("actor.revoked-1", revocationReason="COMPROMISED",
                                     compromisedSince="2026-09-19T00:00:00Z")
        self.assertTrue(self.check(escalated).succeeds)

    def test_version_and_epoch_rules(self):
        self.assertEqual(self.check(F.v3(), previous=F.v4()).reason, "SUCCESSION_VERSION_REGRESSION")
        self.assertEqual(self.check(F.v4(registryVersion=5)).reason, "SUCCESSION_VERSION_GAP")
        self.assertEqual(self.check(F.v4_fork(), previous=F.v4()).reason, "SUCCESSION_SAME_VERSION_FORK")
        self.assertEqual(self.check(F.v4(), previous=F.v4()).reason, "SUCCESSION_NO_CHANGE")
        earlier = F.registry_from(F._keys(F.v3()), registryVersion=4, issuedAt="2026-09-26T05:00:00Z")
        self.assertEqual(self.check(earlier).reason, "SUCCESSION_TIME_REGRESSION")
        self.assertEqual(self.check(F.v4(environment="dev")).reason, "SUCCESSION_MALFORMED")
        self.assertEqual(self.check(F.v4(registryRootKeyId="test-only.registry-root-2")).reason,
                         "SUCCESSION_ROOT_OR_ENVIRONMENT_CHANGED")
        skip = RC.verify_registry_succession(F.v4(), F.v5(epoch=A.RecoveryEpochV1(4, F.E3.random)))
        self.assertEqual(skip.reason, "SUCCESSION_EPOCH_INVALID")
        self.assertEqual(self.check(F.v4(), trusted=RC.registry_head(F.v4_fork())).reason,
                         "SUCCESSION_PREVIOUS_NOT_TRUSTED_HEAD")
        self.assertEqual(self.check({"not": "a registry"}).reason, "SUCCESSION_MALFORMED")

    def test_new_records_and_single_current_scope(self):
        keys = F.v4_keys()
        keys[F.SUCCESSOR]["registryVersion"] = 3
        self.assertEqual(self.check(F.v4(keys=keys)).reason, "SUCCESSION_NEW_RECORD_VERSION")
        self.assertEqual(self.check(F.two_current_registry()).reason, "SUCCESSION_CURRENT_KEY_SCOPE")
        dual = F.v4(keys=F.v4_keys(predecessor_reason=None))  # predecessor never revoked
        self.assertEqual(self.check(dual).reason, "SUCCESSION_CURRENT_KEY_SCOPE")

    def test_pure_function_claims_nothing_durable(self):
        doc = inspect.getdoc(RC.verify_registry_succession)
        self.assertIn("does not by itself create durable", doc)
        self.assertIn("recovery witness", doc)


# ------------------------------------------------------------ single current key ---

class SingleCurrentKeyTests(unittest.TestCase):
    def parsed(self, registry):
        return A.AuthorityRegistryV1.from_verified_dict(registry)

    def test_scope_is_signing_domain_and_evidence_type_from_current_source(self):
        self.assertIn("signingDomain", A.KEY_RECORD_FIELDS)
        self.assertIn("evidenceTypes", A.KEY_RECORD_FIELDS)
        self.assertNotIn("authorityDomain", A.KEY_RECORD_FIELDS)
        self.assertIn("authorityDomain", A._COMMON_EVIDENCE_FIELDS)  # logical context on evidence only
        self.assertEqual(RC.ISSUANCE_SCOPES, {(A.OWNER_ACTOR, A.OWNER_MEMORY_OPERATION),
                                              (A.PRIVACY, A.PRIVACY_ERASURE_AUTHORIZATION)})

    def test_one_current_actor_and_separate_privacy(self):
        registry = self.parsed(F.v3())
        self.assertIsNone(RC.single_current_key_reason(registry))
        self.assertEqual(RC.select_current_issuance_key(registry, A.OWNER_ACTOR, A.OWNER_MEMORY_OPERATION).key_id,
                         F.PREDECESSOR)
        self.assertEqual(RC.select_current_issuance_key(registry, A.PRIVACY, A.PRIVACY_ERASURE_AUTHORIZATION).key_id,
                         "privacy.current-1")

    def test_historical_predecessor_with_one_current_successor(self):
        registry = self.parsed(F.v4())
        self.assertIsNone(RC.single_current_key_reason(registry))
        self.assertEqual(RC.select_current_issuance_key(registry, A.OWNER_ACTOR, A.OWNER_MEMORY_OPERATION).key_id,
                         F.SUCCESSOR)
        self.assertEqual(registry.keys[F.PREDECESSOR].revocation_reason, "SUPERSEDED")

    def test_two_current_keys_are_refused_even_before_not_before(self):
        registry = self.parsed(F.two_current_registry())
        self.assertEqual(RC.single_current_key_reason(registry), "MULTIPLE_CURRENT_ISSUANCE_KEYS")
        with self.assertRaises(P.OwnerProofError) as caught:
            RC.select_current_issuance_key(registry, A.OWNER_ACTOR, A.OWNER_MEMORY_OPERATION)
        self.assertEqual(caught.exception.code, "MULTIPLE_CURRENT_ISSUANCE_KEYS")
        keys = F.v4_keys()
        keys["actor.b1b3e-second-current"] = SA.key_record("actor.b1b3e-second-current", seed_name=F.PREDECESSOR,
                                                           publicKey=F.public_b64("second-current"),
                                                           createdAt=F.T_CUT, notBefore="2030-01-01T00:00:00Z",
                                                           registryVersion=4)
        self.assertEqual(RC.single_current_key_reason(self.parsed(F.v4(keys=keys))), "MULTIPLE_CURRENT_ISSUANCE_KEYS")

    def test_scope_mismatch_and_absent_key(self):
        registry = self.parsed(F.v3())
        for domain, evidence_type in ((A.OWNER_ACTOR, A.PRIVACY_ERASURE_AUTHORIZATION),
                                      (A.PRIVACY, A.OWNER_MEMORY_OPERATION), ("CONTAINMENT", A.OWNER_MEMORY_OPERATION)):
            with self.subTest(scope=(domain, evidence_type)), self.assertRaises(P.OwnerProofError) as caught:
                RC.select_current_issuance_key(registry, domain, evidence_type)
            self.assertEqual(caught.exception.code, "ISSUANCE_SCOPE_INVALID")
        with self.assertRaises(P.OwnerProofError) as caught:
            RC.select_current_issuance_key(self.parsed(F.v5()), A.PRIVACY, A.PRIVACY_ERASURE_AUTHORIZATION)
        self.assertEqual(caught.exception.code, "NO_CURRENT_ISSUANCE_KEY")

    def test_selection_never_consults_evidence_time(self):
        parameters = set(inspect.signature(RC.select_current_issuance_key).parameters)
        self.assertEqual(parameters, {"registry", "signing_domain", "evidence_type"})
        self.assertNotIn("issued_at", inspect.getsource(RC.current_issuance_keys).replace("issuedAt", ""))


# -------------------------------------------------------------- rotation state ---

class RotationStateTests(unittest.TestCase):
    STEPS = ("propose", "prepare", "authorize", "publish", "activate", "release_hold")

    def staged(self, upto: int) -> F.Scenario:
        s = F.Scenario()
        for name in self.STEPS[:upto]:
            getattr(s, name)()
        return s

    def test_each_step_reaches_exactly_its_state(self):
        expected = [(RC.P_ACTIVE, "OWNER_INTENT_ABSENT"), (RC.S_PROPOSED, "SUCCESSOR_PUBLICATION_INVALID"),
                    (RC.S_PREPARED, "CANDIDATE_REGISTRY_MISSING"), (RC.S_AUTHORIZED, "HEAD_NOT_ADVANCED"),
                    (RC.S_PUBLISHED, "SIGNER_HEALTH_ABSENT"), (RC.S_ACTIVATED, "LOCAL_HOLD_PRESENT"),
                    (RC.S_CURRENT, None)]
        for upto, (state, blocked) in enumerate(expected):
            with self.subTest(state=state):
                assessment = RC.evaluate_rotation(self.staged(upto).evidence())
                self.assertEqual((assessment.state, assessment.blocked_reason), (state, blocked))
                self.assertEqual(assessment.issuance_ready, state == RC.S_CURRENT)
                self.assertFalse(assessment.facts["authorityGranted"])

    def test_every_allowed_transition_and_every_other_edge_is_refused(self):
        stages = {state: self.staged(i) for i, state in enumerate(RC.ROTATION_STATES)}
        for current in RC.ROTATION_STATES:
            for proposed in RC.ROTATION_STATES:
                evidence = stages[proposed].evidence() if proposed != RC.P_ACTIVE else stages[current].evidence()
                with self.subTest(edge=(current, proposed)):
                    check = RC.validate_rotation_transition(current, proposed, evidence)
                    if proposed in RC.ALLOWED_TRANSITIONS[current]:
                        self.assertTrue(check.allowed, check)
                    else:
                        self.assertEqual(check.reason, "TRANSITION_NOT_ALLOWED")

    def test_skipped_transition_cannot_be_forced_by_evidence(self):
        full = self.staged(6).evidence()
        for current, proposed in ((RC.P_ACTIVE, RC.S_PREPARED), (RC.S_PREPARED, RC.S_PUBLISHED),
                                  (RC.S_PUBLISHED, RC.S_CURRENT), (RC.S_PROPOSED, RC.S_CURRENT),
                                  (RC.S_CURRENT, RC.S_ACTIVATED), (RC.S_PUBLISHED, RC.P_ACTIVE)):
            with self.subTest(edge=(current, proposed)):
                self.assertEqual(RC.validate_rotation_transition(current, proposed, full).reason,
                                 "TRANSITION_NOT_ALLOWED")
        weak = self.staged(2).evidence()
        self.assertEqual(RC.validate_rotation_transition(RC.S_PREPARED, RC.S_AUTHORIZED, weak).reason,
                         "EVIDENCE_INSUFFICIENT")

    def test_proposal_requires_the_local_hold(self):
        s = self.staged(1)
        self.assertTrue(RC.validate_rotation_transition(RC.P_ACTIVE, RC.S_PROPOSED, s.evidence()).allowed)
        self.assertEqual(RC.validate_rotation_transition(RC.P_ACTIVE, RC.S_PROPOSED,
                                                         s.evidence(hold_present=False)).reason, "LOCAL_HOLD_ABSENT")

    def test_s_prepared_cannot_issue(self):
        s = self.staged(2)
        self.assertEqual(RC.evaluate_rotation(s.evidence()).state, RC.S_PREPARED)
        # A successor signature is unknown to the witnessed head registry.
        evidence = SA.owner_evidence(signer="actor.current-2", keyId=F.SUCCESSOR)
        context = RC.witness_v2_authority_context(s.witness, registry_root=F.root(), purpose=A.NEW_ADMISSION)
        result = AV.verify_owner_evidence(context=context, registry=F.v3(), evidence=evidence,
                                          expectation=SA.owner_expectation())
        self.assertEqual(result.reason, "KEY_UNKNOWN")

    def test_s_authorized_is_not_witness_execution(self):
        s = self.staged(3)
        assessment = RC.evaluate_rotation(s.evidence())
        self.assertEqual(assessment.state, RC.S_AUTHORIZED)
        self.assertFalse(assessment.facts["witnessExecuted"])
        self.assertEqual(s.witness.registry_head, RC.registry_head(F.v3()))
        # (A) alone, without (B), is a staged candidate: still S_PREPARED.
        only_a = RC.evaluate_rotation(s.evidence(head_authorization=None))
        self.assertEqual((only_a.state, only_a.blocked_reason), (RC.S_PREPARED, "HEAD_AUTHORIZATION_MISSING"))
        # Abort is allowed only before execution.
        self.assertTrue(RC.validate_rotation_transition(RC.S_AUTHORIZED, RC.P_ACTIVE, s.evidence()).allowed)
        s.publish()
        self.assertEqual(RC.validate_rotation_transition(RC.S_AUTHORIZED, RC.P_ACTIVE, s.evidence()).reason,
                         "ABORT_AFTER_WITNESS_EXECUTION")

    def test_s_published_is_not_issuance_ready(self):
        s = self.staged(4)
        assessment = RC.evaluate_rotation(s.evidence())
        self.assertEqual(assessment.state, RC.S_PUBLISHED)
        self.assertFalse(assessment.issuance_ready)
        self.assertIsNone(assessment.facts["predecessorState"])  # nobody issues here
        observation = W2.observe_authority_recovery_ledger(s.ledger)
        self.assertEqual(RC.authority_ledger_position_reason(observation, s.witness), "BROKER_REGISTRY_VIEW_STALE")

    def test_s_activated_is_not_s_current(self):
        s = self.staged(5)
        assessment = RC.evaluate_rotation(s.evidence())
        self.assertEqual((assessment.state, assessment.blocked_reason), (RC.S_ACTIVATED, "LOCAL_HOLD_PRESENT"))
        self.assertNotEqual(RC.S_ACTIVATED, RC.S_CURRENT)
        s.release_hold()
        # Signer claim alone is not verification: B2 (root-observed blob hash) must match B3.
        bad_blob = RC.evaluate_rotation(s.evidence(observed_blob_sha256=F.digest("other blob")))
        self.assertEqual((bad_blob.state, bad_blob.blocked_reason, bad_blob.detail),
                         (RC.S_ACTIVATED, "LOADED_KEY_BINDING_FAILED", "BLOB_HASH_MISMATCH"))
        no_blob = RC.evaluate_rotation(s.evidence(observed_blob_sha256=None))
        self.assertEqual(no_blob.detail, "BINDING_INPUT_MISSING")

    def test_s_current_requires_all_conditions(self):
        s = self.staged(6)
        ok = RC.evaluate_rotation(s.evidence())
        self.assertEqual(ok.state, RC.S_CURRENT)
        self.assertEqual(ok.facts["predecessorState"], RC.P_SUPERSEDED)
        self.assertTrue(ok.facts["loadedKeyBinding"]["authorityGranted"] is False)
        stale = dataclasses.replace(W2.observe_authority_recovery_ledger(s.ledger), sequence=1)
        cases = {
            "LOCAL_HOLD_PRESENT": dict(hold_present=True),
            "LOADED_KEY_BINDING_FAILED": dict(observed_blob_sha256=F.digest("other blob")),
            "LEDGER_POSITION_NOT_WITNESSED": dict(ledger_observation=stale),
        }
        for reason, overrides in cases.items():
            with self.subTest(reason=reason):
                result = RC.evaluate_rotation(s.evidence(**overrides))
                self.assertEqual((result.state, result.blocked_reason), (RC.S_ACTIVATED, reason))
        # Conditions 1-3 are re-checked at S_CURRENT (registry at the fresh V2 head, single current key).
        source = inspect.getsource(RC.evaluate_rotation)
        for marker in ("HEAD_REGISTRY_NOT_VERIFIED", "SINGLE_CURRENT_KEY_FAILED", "LEDGER_POSITION_NOT_WITNESSED",
                       "LOADED_KEY_BINDING_FAILED", "LOCAL_HOLD_PRESENT"):
            self.assertIn(marker, source)

    def test_predecessor_is_superseded_only_with_s_current(self):
        for upto, expected in ((0, RC.P_ACTIVE), (3, RC.P_ACTIVE), (4, None), (5, None), (6, RC.P_SUPERSEDED)):
            with self.subTest(upto=upto):
                self.assertEqual(RC.evaluate_rotation(self.staged(upto).evidence()).facts["predecessorState"],
                                 expected)

    def test_ambiguous_dual_current_and_rr10_reason(self):
        s = self.staged(2)
        dual = F.v4(keys=F.v4_keys(predecessor_reason=None))
        result = RC.evaluate_rotation(s.evidence(candidate_registry=dual,
                                                 head_authorization=F.head_authorization(target=dual)))
        self.assertEqual((result.state, result.blocked_reason, result.detail),
                         (RC.S_PREPARED, "CANDIDATE_SUCCESSION_INVALID", "SUCCESSION_CURRENT_KEY_SCOPE"))
        routine = F.v4(keys=F.v4_keys(predecessor_reason="ROUTINE"))
        result = RC.evaluate_rotation(s.evidence(candidate_registry=routine,
                                                 head_authorization=F.head_authorization(target=routine)))
        self.assertEqual(result.blocked_reason, "CANDIDATE_PREDECESSOR_NOT_SUPERSEDED")

    def test_head_moved_elsewhere_blocks_authorization(self):
        s = self.staged(3)
        competing = F.head_authorization(target=F.v4_fork(), authorizationId="rhaa.competing", nonce=F.nonce("c"))
        s.writer.execute_registry_head_advance(authorization=competing, prior_registry=F.v3(),
                                               target_registry=F.v4_fork(), registry_root=F.root(),
                                               updated_at=s.tick())
        result = RC.evaluate_rotation(s.evidence())
        self.assertEqual((result.state, result.blocked_reason), (RC.S_PREPARED, "HEAD_ADVANCED_ELSEWHERE"))

    def test_unevaluable_evidence_fails_closed(self):
        s = self.staged(6)
        self.assertEqual(RC.evaluate_rotation(s.evidence(witness_chain=())).state, RC.NOT_EVALUABLE)
        self.assertEqual(RC.evaluate_rotation(s.evidence(successor_key_id=F.PREDECESSOR)).state, RC.NOT_EVALUABLE)
        self.assertEqual(RC.validate_rotation_transition(RC.S_ACTIVATED, RC.S_CURRENT,
                                                         s.evidence(witness_chain=())).reason,
                         "EVIDENCE_NOT_EVALUABLE")


# ------------------------------------------------------------ loaded-key binding ---

class LoadedKeyBindingTests(unittest.TestCase):
    def setUp(self):
        self.s = F.Scenario().to_current()

    def bind(self, **overrides):
        value = dict(registry_root=F.root(), witness=self.s.witness, head_registry=F.v4(),
                     signing_domain=A.OWNER_ACTOR, evidence_type=A.OWNER_MEMORY_OPERATION,
                     observed_blob_sha256=F.SUCCESSOR_BLOB_SHA256, publication=F.publication(), health=F.health())
        value.update(overrides)
        return RC.verify_loaded_key_binding(**value)

    def test_valid_binding_grants_nothing(self):
        result = self.bind()
        self.assertTrue(result.verified, result)
        self.assertEqual(result.facts["keyId"], F.SUCCESSOR)
        self.assertEqual(result.facts["independentInputs"], ["B1", "B2", "B3"])
        self.assertEqual(result.facts["signerClaim"], "B4")
        self.assertFalse(result.facts["authorityGranted"])
        self.assertEqual(result.facts["proofOfPossession"], "NOT_PERFORMED_RR14A_DEFERRED")

    def test_every_mismatch(self):
        other_fp = hashlib.sha256(F.raw_public("other")).hexdigest()
        cases = {
            "BLOB_HASH_MISMATCH": dict(observed_blob_sha256=F.digest("other blob")),
            "PUBLICATION_KEY_MISMATCH": dict(publication=F.publication("other")),
            "PUBLICATION_FINGERPRINT_INVALID": dict(publication=F.publication(public_key_sha256=other_fp)),
            "HEALTH_FINGERPRINT_MISMATCH": dict(health=F.health("other")),
            "PUBLICATION_SCOPE_MISMATCH": dict(publication=F.publication(key_id="actor.not-the-current-key")),
            "HEALTH_CREDENTIAL_NOT_PRESENT": dict(health=F.health(credential="CREDENTIAL_ABSENT",
                                                                  publicKeySha256=None)),
            "HEALTH_SCOPE_MISMATCH": dict(health=F.health(signingDomain=A.PRIVACY)),
            "ISSUANCE_SCOPE_INVALID": dict(evidence_type=A.PRIVACY_ERASURE_AUTHORIZATION),
            "REGISTRY_NOT_AT_WITNESSED_HEAD": dict(head_registry=F.v3()),
        }
        for reason, overrides in cases.items():
            with self.subTest(reason=reason):
                self.assertEqual(self.bind(**overrides).reason, reason)
        env = self.bind(publication=F.publication(environment="dev"))
        self.assertEqual(env.reason, "PUBLICATION_SCOPE_MISMATCH")
        # Wrong domain: the Privacy current key is selected, and the Actor publication does not match it.
        self.assertEqual(self.bind(signing_domain=A.PRIVACY, evidence_type=A.PRIVACY_ERASURE_AUTHORIZATION).reason,
                         "PUBLICATION_SCOPE_MISMATCH")

    def test_each_required_input_missing_fails_closed(self):
        for name, label in (("witness", "B1_WITNESS"), ("head_registry", "B1_REGISTRY"),
                            ("observed_blob_sha256", "B2_BLOB_HASH"), ("publication", "B3_PUBLICATION"),
                            ("health", "B4_HEALTH")):
            with self.subTest(missing=name):
                result = self.bind(**{name: None})
                self.assertEqual((result.reason, result.detail), ("BINDING_INPUT_MISSING", label))
        self.assertEqual(self.bind(observed_blob_sha256="nothex").reason, "BINDING_INPUT_MALFORMED")
        self.assertEqual(self.bind(publication={"publicationType": "X"}).reason, "BINDING_INPUT_MALFORMED")

    def test_health_alone_is_not_independent(self):
        # B4 agrees, but the root-observed blob (B2) does not match the ceremony (B3).
        result = self.bind(observed_blob_sha256=F.digest("swapped slot blob"))
        self.assertEqual(result.reason, "BLOB_HASH_MISMATCH")

    def test_matches_real_authority_dev_publication_and_health(self):
        """Cross-check the exact B1b-3d L1/L2 shapes and the RR-14a finding."""
        for path in (ROOT / "services/authority-dev", ROOT / "services/authority-dev/ceremony"):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        import lilith_authority_keygen_dev as G
        from lilith_authority_dev import core as DC
        from lilith_authority_dev import credential as DK
        key = F.private("successor")
        raw = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        real_publication = G.publication(raw, b"TEST_ONLY synthetic ciphertext", "0" * 32)
        parsed = RC.KeyPublicationV1.from_dict(real_publication)
        self.assertEqual(parsed.public_key, raw)
        self.assertEqual(parsed.public_key_sha256, hashlib.sha256(raw).hexdigest())
        # HEALTH.publicKeySha256 is derived from the loaded private material.
        der = key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
        status = DK._classify(der)
        self.assertEqual(status.public_key_sha256, hashlib.sha256(raw).hexdigest())
        real_health = DC.DevAuthoritySignerCoreV1(status).health()
        self.assertEqual(real_health["credential"], RC.HEALTH_CREDENTIAL_PRESENT)
        self.assertEqual(set(real_health), set(F.health()))
        self.assertTrue(self.bind(health=real_health).verified)
        self.assertEqual(G.PUBLICATION_TYPE, RC.KEY_PUBLICATION_TYPE)


# ------------------------------------------------------------- restore / recovery ---

class RestoreRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.s = F.Scenario().to_current()

    def position(self, ledger=None, witness=None):
        return RC.authority_ledger_position_reason(W2.observe_authority_recovery_ledger(ledger or self.s.ledger),
                                                   witness or self.s.witness)

    def test_current_state_is_consistent(self):
        self.assertIsNone(self.position())

    def test_prepared_is_voided_and_consumed_never_reopens(self):
        before = self.s.ledger
        self.assertEqual(before.challenge("c2")["state"], RL.PREPARED)
        self.s.epoch_advance()
        self.assertEqual(self.s.ledger.challenge("c2")["state"], RL.VOIDED_BY_RECOVERY)
        self.assertEqual(self.s.ledger.challenge("c1")["state"], RL.CONSUMED)
        self.assertIsNone(self.position())
        with self.assertRaises(RL.LedgerRefusal) as caught:
            self.s.ledger.prepare("c1", self.s.ledger.ledger_epoch, ready=F.seeded_ready(self.s.ledger))
        self.assertEqual(caught.exception.reason, "CHALLENGE_ALREADY_KNOWN")
        rows = {t: {k: dict(v) for k, v in self.s.ledger.rows[t].items()} for t in ("challenges", "uses")}
        rows["challenges"]["c1"]["state"] = RL.PREPARED
        reopened = RL.AuthorityLedgerStateV1(self.s.ledger.log, rows)
        self.assertEqual(self.position(reopened), "TERMINAL_STATE_REOPENED")

    def test_stale_epoch_is_rejected(self):
        old_lep = self.s.ledger.ledger_epoch
        self.s.epoch_advance()
        with self.assertRaises(RL.LedgerRefusal) as caught:
            self.s.ledger.prepare("c9", old_lep, ready=F.seeded_ready(self.s.ledger))
        self.assertEqual(caught.exception.reason, "CHALLENGE_EPOCH_NOT_CURRENT")

    def test_restored_old_registry_is_rejected_against_v2(self):
        self.assertEqual(RC.verify_registry_at_witness_head(witness=self.s.witness, registry=F.v3(),
                                                            registry_root=F.root()).reason, "REGISTRY_DOWNGRADE")

    def test_restored_old_ledger_is_rejected_while_the_witness_survives(self):
        old_ledger, _, _ = self.s.snapshot()
        self.s.commit(lambda st: st.terminate(RL.CANCEL, "c2"))
        self.assertEqual(self.position(old_ledger), "LEDGER_BEHIND_WITNESS")
        self.s.epoch_advance()
        self.assertEqual(self.position(old_ledger), "LEDGER_EPOCH_STALE")

    def test_adoption_is_destroy_narrow_only_and_c4_ordered(self):
        s = self.s
        auth = F.epoch_authorization(s.witness)
        adopted = W2.adopt_authorized_epoch(s.ledger, authorization=auth, witness=s.witness,
                                            target_registry=F.v5(), registry_root=F.root())
        self.assertEqual(adopted.rows, s.ledger.rows)  # no row changes: adoption only
        op = adopted.log[-1]
        self.assertEqual((op["op"], op["authorizationId"], op["fromWitnessDigest"]),
                         (RL.ADVANCE_EPOCH, auth["authorizationId"], s.witness.digest))
        # Witness is still at the old epoch: the ledger is ahead until execution (fail closed).
        self.assertEqual(self.position(adopted), "LEDGER_EPOCH_AHEAD_OF_WITNESS")
        s.ledger = adopted
        executed = RC.RecoveryWitnessV2.from_verified_dict(s.writer.execute_epoch_advance(
            authorization=auth, prior_registry=s.registry, target_registry=F.v5(), registry_root=F.root(),
            ledger=adopted, updated_at=s.tick()))
        self.assertEqual((executed.ledger_sequence, executed.ledger_head), (adopted.sequence, adopted.head))
        self.assertEqual(executed.current_recovery_epoch, F.E3)
        self.assertEqual(executed.consumed_authorization_id, auth["authorizationId"])
        # Old issued evidence can never be reserved in the new epoch.
        with self.assertRaises(RL.LedgerRefusal) as caught:
            adopted.reserve("aev.c1", F.digest("evidence aev.c1"), F.E2, "prop.c1", ready=F.seeded_ready(adopted))
        self.assertEqual(caught.exception.reason, "STALE_EPOCH_EVIDENCE")

    def test_adoption_refusals(self):
        s = self.s
        auth = F.epoch_authorization(s.witness)
        cases = [
            (dict(authorization=_resign(auth, A.REGISTRY_DOMAIN_SEPARATOR)), "AUTHORIZATION_NOT_VERIFIED"),
            (dict(witness=RC.RecoveryWitnessV2.from_verified_dict(s.writer.chain[-2])), "PRIOR_WITNESS_MISMATCH"),
            (dict(target_registry=F.v4()), "TARGET_REGISTRY_MISMATCH"),
            (dict(witness=R.RecoveryWitnessV1), "WITNESS_NOT_V2"),
        ]
        for overrides, reason in cases:
            kwargs = dict(authorization=auth, witness=s.witness, target_registry=F.v5(), registry_root=F.root())
            kwargs.update(overrides)
            with self.subTest(reason=reason), self.assertRaises(W2.AdoptionRefusal) as caught:
                W2.adopt_authorized_epoch(s.ledger, **kwargs)
            self.assertEqual(caught.exception.reason, reason)
        rows = {t: {k: dict(v) for k, v in s.ledger.rows[t].items()} for t in ("challenges", "uses")}
        rows["challenges"]["c1"]["state"] = RL.PREPARED
        with self.assertRaises(W2.AdoptionRefusal) as caught:
            W2.adopt_authorized_epoch(RL.AuthorityLedgerStateV1(s.ledger.log, rows), authorization=auth,
                                      witness=s.witness, target_registry=F.v5(), registry_root=F.root())
        self.assertEqual(caught.exception.reason, "LEDGER_INTEGRITY_FAILED")

    def test_whole_host_rollback_remains_undetected_and_unclaimed(self):
        ledger, chain, registry = self.s.snapshot()
        self.s.epoch_advance()
        # Everything rolled back together, including the witness writer's own store.
        self.s.writer.restore_chain(chain)
        restored = RC.RecoveryWitnessV2.from_verified_dict(chain[-1])
        self.assertIsNone(self.position(ledger, restored))
        self.assertTrue(RC.verify_registry_at_witness_head(witness=restored, registry=registry,
                                                           registry_root=F.root()).verified)
        self.assertIs(R.WHOLE_HOST_ROLLBACK_PROTECTED, False)
        self.assertFalse(RC.evaluate_rotation(self.s.evidence()).facts["wholeHostRollbackProtected"])


# ---------------------------------------------------- compatibility and structure ---

class CompatibilityAndStructureTests(unittest.TestCase):
    def test_v1_contracts_are_unchanged(self):
        self.assertEqual(R.WITNESS_FIELDS, frozenset({
            "protocol", "schemaVersion", "environment", "witnessVersion", "previousWitnessDigest",
            "currentRecoveryEpoch", "minimumRegistryVersion", "policyVersion", "ledgerSequence", "ledgerHead",
            "updatedAt", "witnessKeyId", "signature"}))
        self.assertEqual(R.WITNESS_SCHEMA_VERSION, 1)
        self.assertEqual(A.REVOCATION_REASONS, frozenset({"ROUTINE", "COMPROMISED", "SUPERSEDED"}))
        self.assertEqual(RC.EPOCH_ADVANCE_REASONS, RL.RECOVERY_REASONS)
        self.assertTrue(set(RC.LEDGER_POSITION_REASONS) <= set(RL.READINESS_REASONS))
        self.assertTrue(set(RC.WITNESS_V2_SUCCESSION_REASONS) >= set(R.SUCCESSION_REASONS)
                        - {"WITNESS_REGISTRY_MINIMUM_REGRESSION"})

    def test_compromise_semantics_are_unchanged(self):
        # Backdated evidence of a COMPROMISED key is still rejected (B1b-3a, C-1).
        evidence = SA.owner_evidence(keyId="actor.compromised-1", registryVersion=2, issuedAt="2026-09-20T12:00:00Z")
        result = AV.verify_owner_evidence(context=SA.historical_context(), registry=SA.registry(), evidence=evidence,
                                          expectation=SA.owner_expectation())
        self.assertEqual(result.reason, "KEY_COMPROMISED")

    def test_routine_and_superseded_verify_identically(self):
        for reason in ("ROUTINE", "SUPERSEDED"):
            registry = F.v4(keys=F.v4_keys(predecessor_reason=reason))
            ctx = SA.historical_context(trusted_minimum_registry_version=4)
            before = SA.owner_evidence(issuedAt="2026-09-27T08:59:59Z")
            after = SA.owner_evidence(issuedAt=F.T_CUT)
            with self.subTest(reason=reason):
                self.assertTrue(AV.verify_owner_evidence(context=ctx, registry=registry, evidence=before,
                                                         expectation=SA.owner_expectation()).verified)
                self.assertEqual(AV.verify_owner_evidence(context=ctx, registry=registry, evidence=after,
                                                          expectation=SA.owner_expectation()).reason, "KEY_REVOKED")

    def test_existing_golden_vectors_are_unchanged(self):
        import test_b1b3b_broker_signing_l04_v2 as B3B
        for relative, expected in B3B.GOLDEN_SHA256.items():
            with self.subTest(path=relative):
                self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), expected)

    def test_pinned_shared_contracts_are_unchanged(self):
        sys.path.insert(0, str(ROOT / "services/authority-dev"))
        import release_file_set as RFS
        for relative, expected in RFS.SHARED_HASHES.items():
            with self.subTest(path=relative):
                self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), expected)

    def test_contract_module_is_pure_and_holds_no_key(self):
        path = PACKAGE / "rotation_contracts.py"
        source = path.read_text(encoding="utf-8")
        for forbidden in ("os", "sys", "subprocess", "socket", "pathlib", "sqlite3", "urllib", "http", "requests",
                          "lilith_authority_signer", "lilith_memory_broker", "lilith_memory.config", "time", "random",
                          "secrets"):
            self.assertFalse(any(n == forbidden or n.startswith(forbidden + ".") for n in _imports(path)), forbidden)
        for forbidden in ("open(", "os.environ", "getenv", "datetime.now", "Ed25519PrivateKey", "sign("):
            self.assertNotIn(forbidden, source)

    def test_signer_module_touches_only_the_authority_recovery_ledger(self):
        path = SIGNER_PACKAGE / "synthetic_witness_v2.py"
        source = path.read_text(encoding="utf-8")
        for forbidden in ("sqlite3", "os", "sys", "pathlib", "time", "random", "secrets", "lilith_memory_broker"):
            self.assertFalse(any(n == forbidden or n.startswith(forbidden + ".") for n in _imports(path)), forbidden)
        code = re.sub(r'"""[\s\S]*?"""', "", source)
        for forbidden in ("owner_control", "synthetic_evidence_ledger", "l04_v2_adapter", "memory_broker",
                          "open(", "datetime.now", "creates_authority=True"):
            self.assertNotIn(forbidden, code)

    def test_new_modules_are_not_reachable_from_runtime_code(self):
        runtime = [p for p in list((ROOT / "services/core-api").rglob("*.py"))
                   + list((ROOT / "services/memory-broker").rglob("*.py")) + list((ROOT / "scripts").rglob("*.py"))
                   + list((ROOT / "services/authority-dev/lilith_authority_dev").rglob("*.py"))
                   if ".venv" not in p.parts and "tests" not in p.parts]
        self.assertTrue(runtime)
        for path in runtime:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for forbidden in ("rotation_contracts", "synthetic_witness_v2"):
                with self.subTest(path=path.name, forbidden=forbidden):
                    self.assertIsNone(re.search(rf"(?<![A-Za-z0-9_]){forbidden}(?![A-Za-z0-9_])", text))

    def test_entry_points_take_public_material_only(self):
        for function in (RC.verify_epoch_advance_authorization, RC.verify_registry_head_advance_authorization,
                         RC.verify_recovery_witness_v2, RC.verify_witness_v2_chain, RC.verify_registry_succession,
                         RC.plan_registry_head_advance, RC.plan_epoch_advance, RC.verify_loaded_key_binding,
                         RC.evaluate_rotation, RC.verify_registry_at_witness_head):
            parameters = set(inspect.signature(function).parameters)
            with self.subTest(function=function.__name__):
                self.assertFalse({p for p in parameters if "private" in p or "seed" in p or "signer" in p
                                  or p.endswith("_key")})

    def test_fixture_keys_are_distinct_test_only_material(self):
        publics = {F.public_b64(name) for name in F.SEEDS} | {SA.public_b64(name) for name in SA.SEEDS}
        self.assertEqual(len(publics), len(F.SEEDS) + len(SA.SEEDS))
        self.assertTrue(F.anchor().test_only)
        self.assertTrue(F.WITNESS_KEY_ID.startswith(R.TEST_ONLY_WITNESS_PREFIX))

    def test_source_record_states_the_honest_status(self):
        text = RECORD.read_text(encoding="utf-8")
        for status in ("**DESIGN ACCEPTED**", "**SOURCE IMPLEMENTED / TEST PROVEN**",
                       "**LIVE REHEARSAL NOT AUTHORIZED**", "**WHOLE-HOST ROLLBACK UNRESOLVED**",
                       "**REAL AUTHORITY ABSENT**"):
            self.assertIn(status, text)
        self.assertNotRegex(text, r"(?i)B1b-3e (is )?(live[- ]complete|closed live|done live)")
        self.assertNotRegex(text, r"(?i)whole-host rollback (is )?(solved|protected|detected)\b")


# ---------------------------------------------------------------- golden vectors ---

class GoldenVectorTests(unittest.TestCase):
    def test_golden_file_matches_the_fixture(self):
        committed = json.loads(F.GOLDEN_PATH.read_text(encoding="utf-8"))
        self.assertEqual(committed, json.loads(json.dumps(F.golden_document())))

    def test_golden_file_is_pinned(self):
        self.assertEqual(hashlib.sha256(F.GOLDEN_PATH.read_bytes()).hexdigest(), GOLDEN_SHA256)

    def test_golden_artifacts_verify(self):
        golden = json.loads(F.GOLDEN_PATH.read_text(encoding="utf-8"))
        self.assertTrue(RC.verify_registry_head_advance_authorization(
            authorization=golden["registryHeadAdvanceAuthorization"], registry_root=F.root(),
            environment=F.ENV).verified)
        self.assertTrue(RC.verify_epoch_advance_authorization(
            authorization=golden["epochAdvanceAuthorization"], registry_root=F.root(), environment=F.ENV).verified)
        for chain in (golden["rotationWitnessChain"], golden["recoveryWitnessChain"]):
            self.assertTrue(RC.verify_witness_v2_chain(anchor=F.anchor(), chain=chain, environment=F.ENV,
                                                       registry_root=F.root()).verified)
        self.assertEqual(golden["rotationOutcome"]["state"], RC.S_CURRENT)
        self.assertEqual(golden["registryDigests"]["v3"], RC.registry_digest(F.v3()))
        ops = golden["authorityRecoveryLedgerOps"]
        # C-4 order on the authority recovery ledger: adoption, then (after witness execution) quarantine.
        self.assertEqual(ops[-2:], ["ADVANCE_EPOCH", "VOID_CHALLENGE"])


if __name__ == "__main__":
    unittest.main()
