"""15B2b-B1b-3e Source Prep A: witness durability, recovery, and readiness (TEST-ONLY).

Gate: docs/architecture/slice-15b2b-b1b3e-live-rehearsal-gate.md (SW-3 .. SW-8).
Record: docs/architecture/slice-15b2b-b1b3e-source-prep-a-witness-readiness.md.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import inspect
import itertools
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

import synthetic_authority as SA  # noqa: F401  (sets sys.path)
import synthetic_b1b3e as F
import synthetic_b1b3e_prep_a as P
from lilith_authority_signer import synthetic_witness_store as WS
from lilith_authority_signer import synthetic_witness_v2 as W2
from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import recovery_contracts as R
from lilith_owner_memory import rotation_contracts as RC
from lilith_owner_memory import witness_readiness as WR

ROOT = SA.ROOT
PACKAGE = ROOT / "services/owner-memory-control/lilith_owner_memory"
SIGNER_PACKAGE = ROOT / "services/owner-memory-control/lilith_authority_signer"
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-source-prep-a-witness-readiness.md"
GOLDEN_SHA256 = "aafe021bb3763acb70d497aa9fedd3b698603c8b838c2cfc3b17e1b6dccf2ec0"
STATE, CHAIN, AUTHS = WS.STATE, WR.CHAIN_DIRECTORY, WR.AUTHORIZATION_DIRECTORY
C = WR.DEV_SYNTHETIC_SLOT_CONTRACT


def _imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            found.add(node.module or "")
    return found


def _witness_sign(document: dict, name: str = "witness", **changes) -> dict:
    """K-WIT (or a rogue key) signs arbitrary content: the K-WIT misuse model."""
    unsigned = {k: v for k, v in document.items() if k != "signature"}
    unsigned.update(changes)
    return {**unsigned, "signature": SA.b64(F.private(name).sign(RC.witness_v2_signing_bytes(unsigned)))}


def _bytes(document: dict) -> bytes:
    return WR.document_bytes(document)


def _doc(storage, directory: str, name: str) -> dict:
    return json.loads(storage.read(directory, name))


def _rotated() -> P.DurableScenario:
    return P.DurableScenario().rotate()


def _ledger_step(ledger, challenge: str = "c3"):
    """One ordinary authority recovery ledger journal step (a new PREPARED challenge)."""
    return ledger.prepare(challenge, R.ledger_epoch_id(F.E2, F.ENV), ready=F.seeded_ready(ledger))


def _log_index(log, *item) -> int:
    return log.index(tuple(item))


# ------------------------------------------------------ SW-3 / GC-3 binding ---

class CredentialBindingTests(unittest.TestCase):
    """GC-3: fixed embedded credential name and "no other authority blob"."""

    @classmethod
    def setUpClass(cls):
        cls.scenario = _rotated()
        cls.head = cls.scenario.scan().head

    def bind(self, **overrides):
        value = dict(registry_root=F.root(), witness=self.head, head_registry=F.v4(), signing_domain=A.OWNER_ACTOR,
                     evidence_type=A.OWNER_MEMORY_OPERATION, observed_blob_sha256=F.SUCCESSOR_BLOB_SHA256,
                     publication=F.publication(), health=F.health(), unit_credentials=P.unit_credentials(),
                     inventory=P.inventory(), inventory_phase=WR.STEADY)
        value.update(overrides)
        return WR.verify_current_credential_binding(**value)

    def test_valid_binding_includes_gc3_conditions_and_grants_nothing(self):
        result = self.bind()
        self.assertTrue(result.verified, result.reason)
        self.assertEqual(result.facts["credentialName"], "owner-actor-signing-key")
        self.assertEqual(result.facts["otherAuthorityBlobsInCredstore"], 0)
        self.assertFalse(result.facts["authorityGranted"])
        self.assertEqual(result.facts["signerClaim"], "B4")

    def test_rr14_binding_is_still_required(self):
        self.assertEqual(self.bind(observed_blob_sha256=P.OTHER_BLOB_SHA256,
                                   inventory=P.inventory(current=(P.blob(sha256=P.OTHER_BLOB_SHA256),))).reason,
                         "BLOB_HASH_MISMATCH")
        self.assertEqual(self.bind(health=F.health("other")).reason, "HEALTH_FINGERPRINT_MISMATCH")

    def test_missing_gc3_inputs_fail_closed(self):
        for name, key in (("unit_credentials", "B5_UNIT_CREDENTIALS"), ("inventory", "B6_CREDENTIAL_INVENTORY")):
            with self.subTest(name=name):
                result = self.bind(**{name: None})
                self.assertEqual((result.reason, result.detail), ("BINDING_INPUT_MISSING", key))

    def test_wrong_unit_is_refused(self):
        self.assertEqual(self.bind(unit_credentials=P.unit_credentials(unit="lilith-recovery-witness.service")).reason,
                         "UNIT_MISMATCH")

    def test_second_or_no_unit_credential_reference_is_refused(self):
        current = WR.UnitCredentialReferenceV1(WR.LOAD_CREDENTIAL_ENCRYPTED, C.credential_name, C.current_slot_path)
        second = WR.UnitCredentialReferenceV1(WR.LOAD_CREDENTIAL_ENCRYPTED, "owner-actor-signing-key-next",
                                              "/root/prepared/successor.cred")
        self.assertEqual(self.bind(unit_credentials=P.unit_credentials(current, second)).reason,
                         "UNIT_CREDENTIAL_REFERENCES_UNEXPECTED")
        self.assertEqual(self.bind(unit_credentials=WR.UnitCredentialObservationV1(C.unit_name, ())).reason,
                         "UNIT_CREDENTIAL_REFERENCES_UNEXPECTED")

    def test_plaintext_credential_directive_is_refused(self):
        plain = WR.UnitCredentialReferenceV1("LoadCredential", C.credential_name, C.current_slot_path)
        self.assertEqual(self.bind(unit_credentials=P.unit_credentials(plain)).reason,
                         "UNIT_CREDENTIAL_DIRECTIVE_UNEXPECTED")

    def test_wrong_embedded_credential_name_is_refused(self):
        renamed = WR.UnitCredentialReferenceV1(WR.LOAD_CREDENTIAL_ENCRYPTED, "owner-witness-signing-key",
                                               C.current_slot_path)
        self.assertEqual(self.bind(unit_credentials=P.unit_credentials(renamed)).reason, "CREDENTIAL_NAME_MISMATCH")

    def test_unit_loading_another_path_is_refused(self):
        moved = WR.UnitCredentialReferenceV1(WR.LOAD_CREDENTIAL_ENCRYPTED, C.credential_name,
                                             C.credstore_directory + "/lilith-authority-dev.owner-actor.next.cred")
        self.assertEqual(self.bind(unit_credentials=P.unit_credentials(moved)).reason, "UNIT_CREDENTIAL_PATH_MISMATCH")

    def test_blob_minted_under_another_name_is_refused(self):
        publication = F.publication()
        publication["custodyEvidence"]["credentialName"] = "owner-witness-signing-key"
        self.assertEqual(self.bind(publication=publication).reason, "PUBLICATION_CREDENTIAL_NAME_MISMATCH")

    def test_second_blob_in_the_credstore_is_refused(self):
        for name in ("lilith-authority-dev.owner-actor.cred.bak", "lilith-authority-dev.owner-actor.next.cred"):
            with self.subTest(name=name):
                inv = P.inventory(current=(None, P.blob(name=name, sha256=P.OTHER_BLOB_SHA256)))
                result = self.bind(inventory=inv)
                self.assertEqual((result.reason, result.detail),
                                 ("CREDENTIAL_INVENTORY_NOT_VERIFIED", "UNEXPECTED_CREDENTIAL_BLOB"))

    def test_prepared_blob_outside_its_phase_is_refused(self):
        inv = P.inventory(prepared=(P.blob(name="successor.cred", sha256=P.OTHER_BLOB_SHA256),))
        self.assertEqual(self.bind(inventory=inv).detail, "PREPARED_SLOT_NOT_PERMITTED")
        # Valid for SUCCESSOR_PREPARED, but that phase is never issuance-ready.
        self.assertEqual(self.bind(inventory=inv, inventory_phase=WR.SUCCESSOR_PREPARED).reason,
                         "CREDENTIAL_INVENTORY_PHASE_NOT_READY")

    def test_inventory_current_blob_must_equal_b2(self):
        inv = P.inventory(current=(P.blob(sha256=P.OTHER_BLOB_SHA256),))
        self.assertEqual(self.bind(inventory=inv).reason, "INVENTORY_CURRENT_BLOB_MISMATCH")

    def test_cutover_installed_passes_and_the_retired_predecessor_never_binds(self):
        retired = P.blob(name="predecessor.cred", sha256=P.PREDECESSOR_BLOB_SHA256)
        inv = P.inventory(retired=(retired,))
        self.assertTrue(self.bind(inventory=inv, inventory_phase=WR.CUTOVER_INSTALLED).verified)
        # A retained P in the CURRENT slot can never satisfy the binding.
        swapped = P.inventory(current=(P.blob(sha256=P.PREDECESSOR_BLOB_SHA256),))
        self.assertEqual(self.bind(inventory=swapped, observed_blob_sha256=P.PREDECESSOR_BLOB_SHA256).reason,
                         "BLOB_HASH_MISMATCH")

    def test_taxonomy_extends_rr14_and_the_rr14_verifier_is_unchanged(self):
        self.assertEqual(WR.CREDENTIAL_BINDING_REASONS[:len(RC.BINDING_REASONS)], RC.BINDING_REASONS)
        self.assertEqual(set(inspect.signature(RC.verify_loaded_key_binding).parameters), {
            "registry_root", "witness", "head_registry", "signing_domain", "evidence_type", "observed_blob_sha256",
            "publication", "health"})


# ------------------------------------------------------- SW-4 V2 genesis ---

class GenesisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario = P.DurableScenario()
        cls.genesis = cls.scenario.genesis

    def verify(self, genesis=None, **overrides):
        value = dict(anchor=F.anchor(), genesis=genesis or self.genesis, expectation=P.genesis_expectation(),
                     registry=F.v3(), registry_root=F.root())
        value.update(overrides)
        return WR.verify_witness_v2_genesis(**value)

    def test_valid_genesis_binds_the_exact_accepted_head(self):
        result = self.verify()
        self.assertTrue(result.verified, result.reason)
        self.assertEqual(result.facts["registryHead"], RC.registry_head(F.v3()).to_dict())
        self.assertFalse(result.facts["headTransitionPermitted"])
        self.assertFalse(result.facts["authorityGranted"])
        self.assertIsNone(self.genesis["previousWitnessDigest"])
        self.assertIsNone(self.genesis["consumedAuthorizationId"])
        self.assertEqual(self.genesis["witnessVersion"], 1)
        self.assertEqual(self.genesis["schemaVersion"], RC.WITNESS_V2_SCHEMA_VERSION)

    def test_each_expectation_field_is_bound(self):
        head = RC.registry_head(F.v3())
        cases = {
            "GENESIS_EPOCH_MISMATCH": dict(recovery_epoch=F.E3),
            "GENESIS_REGISTRY_VERSION_MISMATCH": dict(registry_head=RC.RegistryHeadV1(4, head.digest)),
            "GENESIS_REGISTRY_DIGEST_MISMATCH": dict(registry_head=RC.RegistryHeadV1(3, F.digest("other head"))),
            "GENESIS_POLICY_MISMATCH": dict(policy_version="policy.synthetic.v9"),
            "GENESIS_LEDGER_POSITION_MISMATCH": dict(ledger_sequence=F.seeded_ledger().sequence + 1),
        }
        for reason, change in cases.items():
            with self.subTest(reason=reason):
                self.assertEqual(self.verify(expectation=P.genesis_expectation(**change)).reason, reason)
        other_head = P.genesis_expectation(ledger_head=F.digest("other ledger head"))
        self.assertEqual(self.verify(expectation=other_head).reason, "GENESIS_LEDGER_POSITION_MISMATCH")

    def test_wrong_environment_is_refused(self):
        dev = P.genesis_expectation(environment="dev")
        result = self.verify(expectation=dev)
        self.assertEqual((result.reason, result.detail), ("GENESIS_WITNESS_UNVERIFIED", "WITNESS_ENVIRONMENT_MISMATCH"))
        parsed = RC.RecoveryWitnessV2.from_verified_dict(self.genesis)
        self.assertEqual(WR.genesis_expectation_reason(parsed, dev), "GENESIS_ENVIRONMENT_MISMATCH")

    def test_non_genesis_shapes_are_refused(self):
        digest = RC.witness_v2_digest(self.genesis)
        for change in (dict(previousWitnessDigest=digest), dict(consumedAuthorizationId="rhaa.b1b3e-rotation-1"),
                       dict(witnessVersion=2, previousWitnessDigest=digest)):
            with self.subTest(change=change):
                self.assertEqual(self.verify(_witness_sign(self.genesis, **change)).reason, "GENESIS_NOT_GENESIS")

    def test_invalid_or_rogue_signature_is_refused(self):
        tampered = dict(self.genesis, signature=SA.b64(b"\x00" * 64))
        self.assertEqual((self.verify(tampered).reason, self.verify(tampered).detail),
                         ("GENESIS_WITNESS_UNVERIFIED", "WITNESS_SIGNATURE_INVALID"))
        self.assertEqual(self.verify(_witness_sign(self.genesis, "rogue-witness")).detail, "WITNESS_SIGNATURE_INVALID")

    def test_v1_witness_is_refused_as_the_live_start(self):
        v1_shaped = _witness_sign(self.genesis, schemaVersion=R.WITNESS_SCHEMA_VERSION)
        self.assertEqual(self.verify(v1_shaped).detail, "UNSUPPORTED_SCHEMA_VERSION")
        for name in ("raise_registry_floor", "advance_epoch_v1", "migrate_v1", "genesis_v1"):
            self.assertFalse(hasattr(WS.DurableWitnessV2WriterV1, name))

    def test_genesis_registry_must_verify_at_the_head(self):
        self.assertEqual((self.verify(registry=None).reason, self.verify(registry=None).detail),
                         ("GENESIS_REGISTRY_UNVERIFIED", "REGISTRY_MISSING"))
        self.assertEqual(self.verify(registry=F.v4()).reason, "GENESIS_REGISTRY_UNVERIFIED")

    def test_bound_plan_refuses_any_expectation_mismatch_and_multiple_current_keys(self):
        good = WR.plan_bound_witness_v2_genesis(expectation=P.genesis_expectation(), registry=F.v3(),
                                                registry_root=F.root(), updated_at=F.stamp(1))
        self.assertTrue(good.planned)
        self.assertIsNone(good.successor_unsigned["consumedAuthorizationId"])
        bad = WR.plan_bound_witness_v2_genesis(expectation=P.genesis_expectation(policy_version="policy.other"),
                                               registry=F.v3(), registry_root=F.root(), updated_at=F.stamp(1))
        self.assertEqual(bad.reason, "GENESIS_POLICY_MISMATCH")
        two = F.two_current_registry()
        refused = WR.plan_bound_witness_v2_genesis(expectation=P.genesis_expectation(two), registry=two,
                                                   registry_root=F.root(), updated_at=F.stamp(1))
        self.assertEqual(refused.reason, "GENESIS_REGISTRY_UNVERIFIED")

    def test_bootstrap_is_refused_over_any_existing_state(self):
        expectation = P.genesis_expectation()
        consistent = P.DurableScenario()
        with self.assertRaises(WS.DurableWitnessRefusal) as caught:
            consistent.writer.bootstrap(expectation=expectation, registry=F.v3(), context=consistent.context(),
                                        updated_at=consistent.tick())
        self.assertEqual((caught.exception.reason, caught.exception.detail), ("STORE_NOT_UNINITIALIZED", "CONSISTENT"))
        # A pointer without its chain is never re-bootstrapped (no auto-bootstrap).
        chainless = P.DurableScenario()
        chainless.storage.drop(CHAIN, "1.json")
        with self.assertRaises(WS.DurableWitnessRefusal) as caught:
            chainless.writer.bootstrap(expectation=expectation, registry=F.v3(), context=chainless.context(),
                                       updated_at=chainless.tick())
        self.assertEqual(caught.exception.detail, "CHAIN_MISSING")

    def test_bootstrap_refuses_an_unbound_genesis_and_writes_nothing(self):
        storage = P.SimulatedDurableStorage()
        writer = WS.DurableWitnessV2WriterV1(signing_key=F.private("witness"), witness_key_id=F.WITNESS_KEY_ID,
                                             environment=F.ENV, storage=storage)
        context = WR.WitnessStoreContextV1(anchor=F.anchor(), environment=F.ENV, registry_root=F.root())
        with self.assertRaises(WS.DurableWitnessRefusal) as caught:
            writer.bootstrap(expectation=P.genesis_expectation(recovery_epoch=F.E3), registry=F.v3(), context=context,
                             updated_at=F.stamp(1))
        self.assertEqual((caught.exception.reason, caught.exception.detail),
                         ("GENESIS_REFUSED", "GENESIS_EPOCH_MISMATCH"))
        self.assertEqual(storage.names(STATE), [])

    def test_bootstrap_interrupted_before_commit_stays_uninitialized(self):
        for point in ("BEFORE_CHAIN_CREATE", "AFTER_CHAIN_WRITE", "AFTER_CHAIN_FILE_FSYNC"):
            with self.subTest(point=point):
                storage = P.SimulatedDurableStorage()
                writer = WS.DurableWitnessV2WriterV1(signing_key=F.private("witness"),
                                                     witness_key_id=F.WITNESS_KEY_ID, environment=F.ENV,
                                                     storage=storage, fault_hook=P.fault_at(point))
                context = WR.WitnessStoreContextV1(anchor=F.anchor(), environment=F.ENV, registry_root=F.root())
                with self.assertRaises(P.InjectedFault):
                    writer.bootstrap(expectation=P.genesis_expectation(), registry=F.v3(), context=context,
                                     updated_at=F.stamp(1))
                storage.crash()
                scan = WR.classify_witness_store(observation=WS.observe_witness_store(storage), context=context)
                self.assertEqual((scan.classification, scan.decision),
                                 (WR.UNINITIALIZED, WR.OWNER_BOOTSTRAP_REQUIRED))

    def test_genesis_is_not_permission_for_a_head_transition(self):
        scenario = P.DurableScenario()
        with self.assertRaises(WS.DurableWitnessRefusal) as caught:
            scenario.publish(None)
        self.assertEqual((caught.exception.reason, caught.exception.detail),
                         ("AUTHORIZATION_NOT_VERIFIED", "AUTHORIZATION_MISSING"))
        self.assertEqual(scenario.storage.names(CHAIN), ["1.json"])


# ------------------------------------------------------ SW-8 genesis pin ---

class GenesisPinTests(unittest.TestCase):
    def setUp(self):
        self.scenario = P.DurableScenario()
        self.parsed = RC.RecoveryWitnessV2.from_verified_dict(self.scenario.genesis)

    def test_exact_genesis_digest_passes(self):
        self.assertIsNone(WR.genesis_pin_reason(self.scenario.pin, self.parsed, environment=F.ENV))
        self.assertEqual(self.scenario.scan().classification, WR.CONSISTENT)

    def test_one_bit_mismatch_fails_closed(self):
        digest = self.scenario.pin["genesisWitnessDigest"]
        flipped = digest[:-1] + format(int(digest[-1], 16) ^ 1, "x")
        pin = P.genesis_pin(self.scenario.genesis, genesisWitnessDigest=flipped)
        self.assertEqual(WR.genesis_pin_reason(pin, self.parsed, environment=F.ENV), "GENESIS_MISMATCH")
        scan = self.scenario.scan(genesis_pin=pin)
        self.assertEqual((scan.classification, scan.decision, scan.detail),
                         (WR.GENESIS_MISMATCH, WR.FAIL_CLOSED, "GENESIS_MISMATCH"))

    def test_wrong_environment_missing_and_malformed_pins_fail_closed(self):
        self.assertEqual(WR.genesis_pin_reason(P.genesis_pin(self.scenario.genesis, environment="dev"), self.parsed,
                                               environment=F.ENV), "GENESIS_PIN_ENVIRONMENT_MISMATCH")
        self.assertEqual(WR.genesis_pin_reason(None, self.parsed, environment=F.ENV), "GENESIS_PIN_MISSING")
        for bad in ({**self.scenario.pin, "signature": "x"}, {**self.scenario.pin, "schemaVersion": 2}, "pin"):
            self.assertEqual(WR.genesis_pin_reason(bad, self.parsed, environment=F.ENV), "GENESIS_PIN_MALFORMED")
        self.assertEqual((self.scenario.scan(genesis_pin=None).classification,
                          self.scenario.scan(genesis_pin=None).detail),
                         (WR.RECOVERY_INPUT_INVALID, "GENESIS_PIN_MISSING"))

    def test_pin_cannot_authorize_a_later_witness(self):
        self.scenario.rotate()
        later = self.scenario.scan().head
        later_pin = WR.OwnerGenesisPinV1(F.ENV, later.digest).to_dict()
        self.assertEqual(WR.genesis_pin_reason(later_pin, later, environment=F.ENV), "GENESIS_NOT_GENESIS")
        self.assertEqual(self.scenario.scan(genesis_pin=later_pin).classification, WR.GENESIS_MISMATCH)

    def test_pin_cannot_substitute_for_k_root(self):
        # K-WIT promotes a staged candidate under a fake ID; the pin still matches.
        forged = _witness_sign(self.scenario.genesis, witnessVersion=2,
                               previousWitnessDigest=RC.witness_v2_digest(self.scenario.genesis),
                               registryVersion=4, registryDigest=RC.registry_digest(F.v4()),
                               consumedAuthorizationId="rhaa.fake-1", updatedAt=F.stamp(5))
        self.scenario.storage.plant(CHAIN, "2.json", _bytes(forged))
        self.scenario.storage.plant(STATE, WR.POINTER_NAME, _bytes(forged))
        self.scenario.heads.add(RC.registry_head(F.v4()))
        self.assertTrue(RC.verify_witness_v2_chain(anchor=F.anchor(), chain=[self.scenario.genesis, forged],
                                                   environment=F.ENV, registry_root=F.root()).verified)
        scan = self.scenario.scan()
        self.assertEqual(scan.classification, WR.AUTHORIZATION_HISTORY_INVALID)
        self.assertTrue(scan.detail.startswith("RETAINED_AUTHORIZATION_MISSING"))

    def test_pin_cannot_substitute_for_k_wit(self):
        # The digest excludes the signature, so a forged-signature genesis still matches the pin.
        tampered = dict(self.scenario.genesis, signature=SA.b64(b"\x01" * 64))
        self.assertEqual(RC.witness_v2_digest(tampered), self.scenario.pin["genesisWitnessDigest"])
        self.scenario.storage.plant(CHAIN, "1.json", _bytes(tampered))
        self.scenario.storage.plant(STATE, WR.POINTER_NAME, _bytes(tampered))
        scan = self.scenario.scan()
        self.assertEqual((scan.classification, scan.detail), (WR.CHAIN_CORRUPT, "1:GENESIS_INVALID"))

    def test_second_genesis_over_the_same_anchor_fails(self):
        other = P.DurableScenario(ticks=40)
        self.assertNotEqual(other.pin, self.scenario.pin)
        scan = other.scan(genesis_pin=self.scenario.pin)
        self.assertEqual(scan.classification, WR.GENESIS_MISMATCH)

    def test_pin_is_a_minimal_unsigned_non_authority_input(self):
        self.assertEqual(WR.GENESIS_PIN_FIELDS, {"pinType", "schemaVersion", "environment", "genesisWitnessDigest"})
        self.assertEqual({f.name for f in dataclasses.fields(WR.OwnerGenesisPinV1)},
                         {"environment", "genesis_witness_digest"})


# ------------------------------------------ SW-7 authorization re-verification ---

class AuthorizationHistoryTests(unittest.TestCase):
    """RR-20a: every authority-changing witness transition re-verified under K-ROOT."""

    @classmethod
    def setUpClass(cls):
        cls.scenario = _rotated()
        cls.scan = cls.scenario.scan()
        cls.authorization = cls.scenario.issued and F.head_authorization()
        cls.epoch = _rotated()
        cls.epoch.epoch_advance()
        cls.epoch_scan = cls.epoch.scan()

    def history(self, scan=None, *, retained=None, register=None, root=None, chain=None, scenario=None):
        scenario = scenario or self.scenario
        scan = scan or self.scan
        return WR.verify_authorization_history(chain=chain or scan.chain,
                                               retained=scan.retained if retained is None else retained,
                                               register=scenario.register() if register is None else register,
                                               registry_root=root or F.root())

    def swap_head_authorization(self, **overrides):
        """Replace the retained + registered head authorization with a variant (same ID)."""
        variant = F.head_authorization(F.v3(), F.v4(), **overrides)
        issued = dict(self.scenario.issued)
        issued.update([P.register_entry(variant, WR.REGISTRY_HEAD_ADVANCE)])
        return self.history(retained={variant["authorizationId"]: _bytes(variant)},
                            register=P.owner_register(issued, self.scenario.heads))

    def swap_epoch_authorization(self, **overrides):
        prior = self.epoch_scan.chain.witnesses[-2]
        variant = F.epoch_authorization(prior, F.v5(), **overrides)
        issued = dict(self.epoch.issued)
        issued.update([P.register_entry(variant, WR.EPOCH_ADVANCE)])
        retained = dict(self.epoch_scan.retained)
        retained[variant["authorizationId"]] = _bytes(variant)
        return self.history(self.epoch_scan, scenario=self.epoch, retained=retained,
                            register=P.owner_register(issued, self.epoch.heads))

    # registry-head advance --------------------------------------------------
    def test_valid_head_transition_reverifies(self):
        result = self.history()
        self.assertTrue(result.verified, result.reason)
        self.assertEqual(result.facts["verifiedTransitions"],
                         [{"witnessVersion": 2, "authorizationId": "rhaa.b1b3e-rotation-1",
                           "kind": WR.REGISTRY_HEAD_ADVANCE}])
        self.assertFalse(result.facts["authorityGranted"])

    def test_wrong_root_fails(self):
        result = self.history(root=SA.trusted_root("attacker-root"))
        self.assertEqual((result.reason, result.detail.split(":")[-1]),
                         ("AUTHORIZATION_NOT_VERIFIED", "AUTHORIZATION_SIGNATURE_INVALID"))

    def test_wrong_authorization_id_fails(self):
        witnesses = list(self.scan.chain.witnesses)
        witnesses[1] = dataclasses.replace(witnesses[1], consumed_authorization_id="rhaa.other-1")
        chain = RC.WitnessChainFactsV1(witnesses[-1], tuple(witnesses), frozenset({"rhaa.other-1"}), frozenset())
        raw = self.scan.retained["rhaa.b1b3e-rotation-1"]
        issued = {"rhaa.other-1": (WR.REGISTRY_HEAD_ADVANCE, WR.authorization_sha256(raw))}
        result = self.history(chain=chain, retained={"rhaa.other-1": raw},
                              register=P.owner_register(issued, self.scenario.heads))
        self.assertEqual(result.reason, "AUTHORIZATION_ID_MISMATCH")

    def test_wrong_prior_or_target_head_fails(self):
        self.assertEqual(self.swap_head_authorization(priorRegistryDigest=F.digest("other prior")).reason,
                         "PRIOR_HEAD_MISMATCH")
        self.assertEqual(self.swap_head_authorization(targetRegistryDigest=RC.registry_digest(F.v4_fork())).reason,
                         "TARGET_HEAD_MISMATCH")

    def test_wrong_witness_predecessor_or_successor_fails(self):
        witnesses = list(self.scan.chain.witnesses)
        moved = dataclasses.replace(witnesses[0], registry_digest=F.digest("other genesis head"))
        chain = RC.WitnessChainFactsV1(witnesses[-1], (moved,) + tuple(witnesses[1:]), frozenset(), frozenset())
        heads = (set(self.scenario.heads) - {witnesses[0].registry_head}) | {moved.registry_head}
        self.assertEqual(self.history(chain=chain, register=P.owner_register(self.scenario.issued, heads)).reason,
                         "PRIOR_HEAD_MISMATCH")
        forked = dataclasses.replace(witnesses[1], registry_digest=RC.registry_digest(F.v4_fork()))
        chain = RC.WitnessChainFactsV1(forked, (witnesses[0], forked), frozenset(), frozenset())
        heads = (set(self.scenario.heads) - {witnesses[1].registry_head}) | {forked.registry_head}
        self.assertEqual(self.history(chain=chain, register=P.owner_register(self.scenario.issued, heads)).reason,
                         "TARGET_HEAD_MISMATCH")

    def test_wrong_epoch_fails(self):
        self.assertEqual(self.swap_head_authorization(recoveryEpoch=F.E3.to_dict()).reason, "EPOCH_MISMATCH")

    def test_clock_window_is_defence_in_depth(self):
        self.assertEqual(self.swap_head_authorization(issuedAt="2026-09-27T07:00:00Z",
                                                      notAfter="2026-09-27T08:01:00Z").reason,
                         "AUTHORIZATION_EXPIRED")
        self.assertEqual(self.swap_head_authorization(issuedAt="2026-09-27T09:00:00Z").reason,
                         "AUTHORIZATION_NOT_YET_VALID")

    def test_replay_fails_independently_of_chain_facts(self):
        witnesses = list(self.scan.chain.witnesses)
        replay = dataclasses.replace(witnesses[2], consumed_authorization_id="rhaa.b1b3e-rotation-1")
        chain = RC.WitnessChainFactsV1(replay, (witnesses[0], witnesses[1], replay), frozenset(), frozenset())
        self.assertEqual(self.history(chain=chain).reason, "AUTHORIZATION_REPLAYED")

    def test_tampered_missing_or_unregistered_retained_copies_fail(self):
        raw = self.scan.retained["rhaa.b1b3e-rotation-1"]
        tampered = raw.replace(b"SUCCESSOR_ROTATION", b"COMPROMISE_MARKING")
        self.assertEqual(self.history(retained={"rhaa.b1b3e-rotation-1": tampered}).reason,
                         "RETAINED_AUTHORIZATION_DIGEST_MISMATCH")
        self.assertEqual(self.history(retained={}).reason, "RETAINED_AUTHORIZATION_MISSING")
        self.assertEqual(self.history(register=P.owner_register({}, self.scenario.heads)).reason,
                         "AUTHORIZATION_NOT_REGISTERED")

    def test_owner_register_digest_mismatch_fails(self):
        issued = {"rhaa.b1b3e-rotation-1": (WR.REGISTRY_HEAD_ADVANCE, F.digest("another authorization"))}
        self.assertEqual(self.history(register=P.owner_register(issued, self.scenario.heads)).reason,
                         "RETAINED_AUTHORIZATION_DIGEST_MISMATCH")

    def test_registered_digest_with_different_bytes_fails(self):
        raw = self.scan.retained["rhaa.b1b3e-rotation-1"]
        pretty = json.dumps(json.loads(raw), indent=2).encode()
        self.assertEqual(self.history(retained={"rhaa.b1b3e-rotation-1": pretty}).reason,
                         "RETAINED_AUTHORIZATION_DIGEST_MISMATCH")
        issued = {"rhaa.b1b3e-rotation-1": (WR.REGISTRY_HEAD_ADVANCE, WR.authorization_sha256(pretty))}
        self.assertEqual(self.history(retained={"rhaa.b1b3e-rotation-1": pretty},
                                      register=P.owner_register(issued, self.scenario.heads)).reason,
                         "RETAINED_AUTHORIZATION_MALFORMED")

    def test_same_id_cannot_map_to_two_digests(self):
        register = self.scenario.register()
        register["authorizations"].append({**register["authorizations"][0],
                                           "authorizationSha256": F.digest("second digest")})
        result = self.history(register=register)
        self.assertEqual((result.reason, result.detail), ("REGISTER_MALFORMED", "REGISTER_AUTHORIZATION_ID_DUPLICATED"))
        heads = self.scenario.register()
        heads["headRegistries"].append({"registryVersion": 4, "registryDigest": RC.registry_digest(F.v4_fork())})
        self.assertEqual(self.history(register=heads).detail, "REGISTER_HEAD_VERSION_DUPLICATED")

    def test_register_must_cover_every_head_kind_and_environment(self):
        self.assertEqual(self.history(register=P.owner_register(self.scenario.issued,
                                                                {RC.registry_head(F.v3())})).reason,
                         "HEAD_NOT_REGISTERED")
        wrong_kind = {k: (WR.EPOCH_ADVANCE, d) for k, (_, d) in self.scenario.issued.items()}
        self.assertEqual(self.history(register=P.owner_register(wrong_kind, self.scenario.heads)).reason,
                         "TRANSITION_TYPE_MISMATCH")
        self.assertEqual(self.history(register=self.scenario.register(environment="dev")).reason,
                         "REGISTER_ENVIRONMENT_MISMATCH")
        self.assertEqual(WR.verify_authorization_history(chain=self.scan.chain, retained=self.scan.retained,
                                                         register=None, registry_root=F.root()).reason,
                         "REGISTER_MISSING")

    # epoch advance ------------------------------------------------------------
    def test_valid_epoch_transition_reverifies(self):
        result = self.history(self.epoch_scan, scenario=self.epoch)
        self.assertTrue(result.verified, result.reason)
        self.assertEqual([t["kind"] for t in result.facts["verifiedTransitions"]],
                         [WR.REGISTRY_HEAD_ADVANCE, WR.EPOCH_ADVANCE])

    def test_epoch_transition_negative_matrix(self):
        prior = self.epoch_scan.chain.witnesses[-2]
        cases = {
            "PRIOR_WITNESS_MISMATCH": dict(expectedPriorWitnessDigest=F.digest("other witness")),
            "TARGET_HEAD_MISMATCH": dict(targetRegistryDigest=F.digest("other target")),
            "EPOCH_MISMATCH": dict(successorRecoveryEpoch=A.RecoveryEpochV1(3, F.nonce("other epoch 3")).to_dict()),
            "AUTHORIZATION_EXPIRED": dict(notAfter="2026-09-27T07:31:00Z"),
            "AUTHORIZATION_NOT_YET_VALID": dict(issuedAt="2026-09-27T09:00:00Z"),
        }
        self.assertEqual(prior.witness_version + 1, self.epoch_scan.head.witness_version)
        for reason, change in cases.items():
            with self.subTest(reason=reason):
                self.assertEqual(self.swap_epoch_authorization(**change).reason, reason)
        root = self.history(self.epoch_scan, scenario=self.epoch, root=SA.trusted_root("attacker-root"))
        self.assertEqual(root.reason, "AUTHORIZATION_NOT_VERIFIED")

    def test_epoch_retained_copy_missing_tampered_or_wrong_type_fails(self):
        retained = dict(self.epoch_scan.retained)
        del retained["eaa.b1b3e-recovery-1"]
        self.assertEqual(self.history(self.epoch_scan, scenario=self.epoch, retained=retained).reason,
                         "RETAINED_AUTHORIZATION_MISSING")
        retained["eaa.b1b3e-recovery-1"] = self.epoch_scan.retained["eaa.b1b3e-recovery-1"] + b" "
        self.assertEqual(self.history(self.epoch_scan, scenario=self.epoch, retained=retained).reason,
                         "RETAINED_AUTHORIZATION_DIGEST_MISMATCH")
        wrong = {k: (WR.REGISTRY_HEAD_ADVANCE, d) for k, (_, d) in self.epoch.issued.items()}
        self.assertEqual(self.history(self.epoch_scan, scenario=self.epoch,
                                      register=P.owner_register(wrong, self.epoch.heads)).reason,
                         "TRANSITION_TYPE_MISMATCH")

    def test_epoch_authorization_id_replay_fails(self):
        witnesses = list(self.epoch_scan.chain.witnesses)
        replay = dataclasses.replace(witnesses[-1], consumed_authorization_id="rhaa.b1b3e-rotation-1")
        chain = RC.WitnessChainFactsV1(replay, tuple(witnesses[:-1]) + (replay,), frozenset(), frozenset())
        self.assertEqual(self.history(self.epoch_scan, scenario=self.epoch, chain=chain).reason,
                         "AUTHORIZATION_REPLAYED")

    # cross-cutting --------------------------------------------------------------
    def test_valid_k_wit_chain_without_k_root_authorization_fails_readiness(self):
        scenario = P.DurableScenario()
        forged = _witness_sign(scenario.genesis, witnessVersion=2,
                               previousWitnessDigest=RC.witness_v2_digest(scenario.genesis),
                               registryVersion=4, registryDigest=RC.registry_digest(F.v4()),
                               consumedAuthorizationId="rhaa.fake-1", updatedAt=F.stamp(5))
        scenario.storage.plant(CHAIN, "2.json", _bytes(forged))
        scenario.storage.plant(STATE, WR.POINTER_NAME, _bytes(forged))
        scenario.heads.add(RC.registry_head(F.v4()))
        scenario.registries.append(F.v4())
        result = WR.evaluate_witness_readiness(scenario.readiness_inputs())
        self.assertFalse(result.ready)
        self.assertEqual(result.checks["WITNESS_CHAIN"].reason, WR.AUTHORIZATION_HISTORY_INVALID)
        self.assertEqual(result.checks["AUTHORIZATION_HISTORY"].reason, "RETAINED_AUTHORIZATION_MISSING")
        self.assertEqual(result.checks["GENESIS_PIN"].status, WR.PASS)

    def test_valid_authorization_without_witness_execution_does_not_become_current(self):
        scenario = P.DurableScenario()
        scenario.issue_head_advance()
        result = WR.evaluate_witness_readiness(scenario.readiness_inputs())
        self.assertFalse(result.ready)
        self.assertEqual(result.facts["witnessedHead"], RC.registry_head(F.v3()).to_dict())
        self.assertEqual(result.checks["LOADED_KEY_BINDING"].reason, "PUBLICATION_SCOPE_MISMATCH")

    def test_on_host_copy_absent_from_the_register_is_refused_before_any_write(self):
        scenario = P.DurableScenario()
        authorization = F.head_authorization()
        before = list(scenario.storage.log)
        with self.assertRaises(WS.DurableWitnessRefusal) as caught:
            scenario.publish(authorization)
        self.assertEqual(caught.exception.reason, "AUTHORIZATION_NOT_REGISTERED")
        written = [op for op in scenario.storage.log[len(before):] if op[0] in {"create", "write", "replace"}]
        self.assertEqual(written, [])

    def test_register_digest_mismatch_is_refused_before_any_write(self):
        scenario = P.DurableScenario()
        authorization = scenario.issue_head_advance()
        scenario.issued[authorization["authorizationId"]] = (WR.REGISTRY_HEAD_ADVANCE, F.digest("wrong"))
        mark = len(scenario.storage.log)
        with self.assertRaises(WS.DurableWitnessRefusal) as caught:
            scenario.publish(authorization)
        self.assertEqual(caught.exception.reason, "AUTHORIZATION_REGISTER_MISMATCH")
        self.assertFalse([op for op in scenario.storage.log[mark:] if op[0] == "create"])

    def test_write_once_retention_refuses_different_bytes_under_one_id(self):
        scenario = P.DurableScenario(fault_hook=P.fault_at("BEFORE_CHAIN_CREATE"))
        first = scenario.issue_head_advance()
        with self.assertRaises(P.InjectedFault):
            scenario.publish(first)
        scenario.fault_hook = None
        second = F.head_authorization(nonce=F.nonce("second body same id"))
        scenario.issued.update([P.register_entry(second, WR.REGISTRY_HEAD_ADVANCE)])
        with self.assertRaises(WS.DurableWitnessRefusal) as caught:
            scenario.publish(second)
        self.assertEqual(caught.exception.reason, "RETAINED_AUTHORIZATION_CONFLICT")
        self.assertEqual(scenario.storage.names(CHAIN), ["1.json"])


# ------------------------------------ retention retry (RETAINED != CONSUMED) ---

class RetentionRetryTests(unittest.TestCase):
    """Owner-accepted ambiguity 3: an exact retained-but-unconsumed authorization retries idempotently."""

    NAME = WR.retained_authorization_name("rhaa.b1b3e-rotation-1")

    def retained_then_refused(self):
        scenario = P.DurableScenario()
        authorization = scenario.issue_head_advance()
        with self.assertRaises(WS.DurableWitnessRefusal) as caught:  # B. planning then fails
            scenario.publish(authorization, target=F.v4_fork())
        self.assertEqual(caught.exception.detail, "TARGET_REGISTRY_MISMATCH")
        self.assertEqual(scenario.writer.last_retention, "RETAINED")  # A. first retention succeeded
        self.assertEqual(scenario.storage.names(AUTHS), [self.NAME])
        self.assertEqual(scenario.storage.names(CHAIN), ["1.json"])  # no witness consumed A
        return scenario, authorization

    def refusal(self, scenario, authorization, **overrides):
        with self.assertRaises(WS.DurableWitnessRefusal) as caught:
            scenario.publish(authorization, **overrides)
        return caught.exception

    def test_exact_retry_is_already_retained_and_executes(self):
        scenario, authorization = self.retained_then_refused()
        original = scenario.storage.read(AUTHS, self.NAME)
        mark = len(scenario.storage.log)
        scenario.publish(copy.deepcopy(authorization))  # C. the same exact A, target now valid
        self.assertEqual(scenario.writer.last_retention, "ALREADY_RETAINED")
        self.assertFalse([op for op in scenario.storage.log[mark:] if op[:2] == ("create", AUTHS)])
        self.assertEqual(scenario.storage.names(AUTHS), [self.NAME])  # D. one retained artifact
        self.assertEqual(scenario.storage.read(AUTHS, self.NAME), original)
        scan = scenario.scan()
        self.assertEqual((scan.classification, scan.head.registry_version), (WR.CONSISTENT, 4))
        self.assertEqual(scan.head.consumed_authorization_id, "rhaa.b1b3e-rotation-1")

    def test_same_id_with_altered_bytes_fails_permanently(self):
        scenario, _ = self.retained_then_refused()
        altered = F.head_authorization(nonce=F.nonce("altered body same id"))
        scenario.issued.update([P.register_entry(altered, WR.REGISTRY_HEAD_ADVANCE)])  # even when registered
        for _ in range(2):  # E.
            self.assertEqual(self.refusal(scenario, altered).reason, "RETAINED_AUTHORIZATION_CONFLICT")
        self.assertEqual(scenario.storage.names(CHAIN), ["1.json"])

    def test_same_id_with_altered_digest_or_kind_fails_permanently(self):
        scenario, authorization = self.retained_then_refused()
        digest = scenario.issued["rhaa.b1b3e-rotation-1"][1]
        for registered in ((WR.REGISTRY_HEAD_ADVANCE, F.digest("altered digest")),  # F.
                           (WR.EPOCH_ADVANCE, digest)):
            with self.subTest(registered=registered):
                scenario.issued["rhaa.b1b3e-rotation-1"] = registered
                for _ in range(2):
                    self.assertEqual(self.refusal(scenario, authorization).reason, "AUTHORIZATION_REGISTER_MISMATCH")
        self.assertEqual(scenario.storage.names(AUTHS), [self.NAME])
        self.assertEqual(scenario.storage.names(CHAIN), ["1.json"])

    def test_retry_after_consumption_is_replay(self):
        scenario, authorization = self.retained_then_refused()
        scenario.publish(authorization)
        mark = len(scenario.storage.log)
        refused = self.refusal(scenario, authorization, prior=F.v3())  # G.
        self.assertEqual((refused.reason, refused.detail), ("AUTHORIZATION_CONSUMED", "rhaa.b1b3e-rotation-1"))
        self.assertFalse([op for op in scenario.storage.log[mark:] if op[0] in {"create", "write", "fsync_file"}])
        self.assertEqual(scenario.storage.names(CHAIN), ["1.json", "2.json"])

    def test_epoch_authorization_retry_after_consumption_is_replay(self):
        scenario = _rotated()
        scenario.epoch_advance()
        authorization = F.epoch_authorization(scenario.scan().chain.witnesses[-2], F.v5())
        with self.assertRaises(WS.DurableWitnessRefusal) as caught:
            scenario.writer.execute_epoch_advance(
                authorization=authorization, prior_registry=F.v4(), target_registry=F.v5(),
                adoption_record=scenario.ledger.log[-1], ledger_sequence=scenario.ledger.sequence,
                ledger_head=scenario.ledger.head, context=scenario.context(), updated_at=scenario.tick())
        self.assertEqual(caught.exception.reason, "AUTHORIZATION_CONSUMED")


# --------------------------------------------- SW-5 durable write ordering ---

class DurableWriteOrderTests(unittest.TestCase):
    def test_authority_changing_write_follows_the_accepted_order(self):
        scenario = P.DurableScenario()
        mark = len(scenario.storage.log)
        scenario.publish(scenario.issue_head_advance())
        log = scenario.storage.log[mark:]
        retained = WR.retained_authorization_name("rhaa.b1b3e-rotation-1")
        order = [_log_index(log, "create", AUTHS, retained), _log_index(log, "fsync_file", AUTHS, retained),
                 _log_index(log, "fsync_dir", AUTHS), _log_index(log, "create", CHAIN, "2.json"),
                 _log_index(log, "fsync_file", CHAIN, "2.json"), _log_index(log, "fsync_dir", CHAIN),
                 _log_index(log, "write", STATE, WR.POINTER_SCRATCH_NAME),
                 _log_index(log, "fsync_file", STATE, WR.POINTER_SCRATCH_NAME),
                 _log_index(log, "replace", STATE, WR.POINTER_SCRATCH_NAME, WR.POINTER_NAME),
                 _log_index(log, "fsync_dir", STATE)]
        self.assertEqual(order, sorted(order))
        self.assertEqual(log[0], ("lock",))
        self.assertEqual(log[-1], ("unlock",))

    def test_ledger_only_advance_retains_nothing(self):
        scenario = P.DurableScenario()
        mark = len(scenario.storage.log)
        scenario.ledger = _ledger_step(scenario.ledger)
        scenario.record_ledger()
        self.assertFalse([op for op in scenario.storage.log[mark:] if op[1:2] == (AUTHS,)])
        self.assertEqual(scenario.scan().classification, WR.CONSISTENT)

    def test_retention_not_durable_first_means_no_commit(self):
        for point in ("BEFORE_RETENTION_CREATE", "AFTER_RETENTION_WRITE", "AFTER_RETENTION_FILE_FSYNC"):
            with self.subTest(point=point):
                scenario = P.DurableScenario(fault_hook=P.fault_at(point))
                mark = len(scenario.storage.log)
                with self.assertRaises(P.InjectedFault):
                    scenario.publish(scenario.issue_head_advance())
                self.assertFalse([op for op in scenario.storage.log[mark:] if op[1:2] == (CHAIN,)])

    def test_plan_refused_after_retention_leaves_an_unexecuted_copy_only(self):
        scenario = P.DurableScenario()
        authorization = scenario.issue_head_advance()
        with self.assertRaises(WS.DurableWitnessRefusal) as caught:
            scenario.publish(authorization, target=F.v4_fork())
        self.assertEqual((caught.exception.reason, caught.exception.detail), ("PLAN_REFUSED", "TARGET_REGISTRY_MISMATCH"))
        scan = scenario.scan()
        self.assertEqual((scan.classification, scan.head.witness_version), (WR.CONSISTENT, 1))
        self.assertEqual(scan.facts["unexecutedRetainedAuthorizations"], ["rhaa.b1b3e-rotation-1"])
        scenario.publish(authorization)  # still executable: the prior head is unchanged
        self.assertEqual(scenario.scan().head.registry_version, 4)

    def test_writer_refuses_while_the_store_is_not_consistent(self):
        scenario = P.DurableScenario(fault_hook=P.fault_at("AFTER_CHAIN_DIRECTORY_FSYNC"))
        with self.assertRaises(P.InjectedFault):
            scenario.publish(scenario.issue_head_advance())
        scenario.fault_hook = None
        with self.assertRaises(WS.DurableWitnessRefusal) as caught:
            scenario.record_ledger()
        self.assertEqual((caught.exception.reason, caught.exception.detail),
                         ("STORE_NOT_CONSISTENT", WR.POINTER_BEHIND_BY_ONE))

    def test_single_writer_lock(self):
        scenario = P.DurableScenario()
        with scenario.storage.lock():
            with self.assertRaises(P.LockHeld):
                scenario.record_ledger()
            with self.assertRaises(P.LockHeld):
                scenario.recover()


# ------------------------------------------------- SW-5 recovery algorithm ---

class WitnessRecoveryTests(unittest.TestCase):
    def assertScan(self, scenario, classification, decision=None, **overrides):
        scan = scenario.scan(**overrides)
        self.assertEqual(scan.classification, classification, scan.detail)
        if decision is not None:
            self.assertEqual(scan.decision, decision)
        return scan

    def assertUnchangedByRecovery(self, scenario):
        before = scenario.storage.snapshot()
        run = scenario.recover()
        self.assertEqual(run.actions, ())
        self.assertEqual(scenario.storage.snapshot(), before)
        return run

    def test_clean_genesis_and_clean_linear_chain(self):
        scenario = P.DurableScenario()
        self.assertEqual(self.assertScan(scenario, WR.CONSISTENT, WR.NO_ACTION).head.witness_version, 1)
        self.assertUnchangedByRecovery(scenario)
        scenario.rotate()
        scan = self.assertScan(scenario, WR.CONSISTENT, WR.NO_ACTION)
        self.assertEqual((scan.head.witness_version, scan.head.registry_version), (3, 4))
        self.assertUnchangedByRecovery(scenario)

    def test_uninitialized_needs_the_owner_bootstrap(self):
        storage = P.SimulatedDurableStorage()
        context = WR.WitnessStoreContextV1(anchor=F.anchor(), environment=F.ENV, registry_root=F.root())
        run = WS.recover_witness_store(storage, context=context)
        self.assertEqual((run.before.classification, run.before.decision, run.actions),
                         (WR.UNINITIALIZED, WR.OWNER_BOOTSTRAP_REQUIRED, ()))
        self.assertEqual(storage.names(STATE), [])

    def test_predecessor_pointer_without_successor_is_consistent(self):
        scenario = P.DurableScenario(fault_hook=P.fault_at("BEFORE_CHAIN_CREATE"))
        authorization = scenario.issue_head_advance()
        with self.assertRaises(P.InjectedFault):
            scenario.publish(authorization)
        scenario.storage.crash()
        scenario.fault_hook = None
        self.assertEqual(self.assertScan(scenario, WR.CONSISTENT).head.witness_version, 1)
        scenario.publish(authorization)  # nothing committed: the authorization may be re-presented
        self.assertEqual(scenario.scan().head.registry_version, 4)

    def test_durable_successor_with_stale_pointer_rolls_forward_only(self):
        scenario = P.DurableScenario(fault_hook=P.fault_at("AFTER_CHAIN_DIRECTORY_FSYNC"))
        authorization = scenario.issue_head_advance()
        with self.assertRaises(P.InjectedFault):
            scenario.publish(authorization)
        scenario.storage.crash()
        scenario.fault_hook = None
        chain_before = {n: scenario.storage.read(CHAIN, n) for n in scenario.storage.names(CHAIN)}
        run = scenario.recover()
        self.assertEqual((run.before.classification, run.actions), (WR.POINTER_BEHIND_BY_ONE,
                                                                     ("POINTER_ROLLED_FORWARD",)))
        self.assertEqual((run.after.classification, run.after.head.witness_version), (WR.CONSISTENT, 2))
        self.assertEqual({n: scenario.storage.read(CHAIN, n) for n in scenario.storage.names(CHAIN)}, chain_before)
        self.assertFalse(run.facts["producedWitness"])
        with self.assertRaises(WS.DurableWitnessRefusal) as caught:
            scenario.publish(authorization)
        self.assertEqual(caught.exception.reason, "AUTHORIZATION_CONSUMED")

    def test_pointer_missing_or_corrupt_rolls_forward(self):
        for pointer in (None, b"", b"{not json", b'{"a":1}'):
            with self.subTest(pointer=pointer):
                scenario = _rotated()
                if pointer is None:
                    scenario.storage.drop(STATE, WR.POINTER_NAME)
                else:
                    scenario.storage.plant(STATE, WR.POINTER_NAME, pointer)
                run = scenario.recover()
                self.assertIn(run.before.classification, {WR.POINTER_MISSING, WR.POINTER_CORRUPT})
                self.assertEqual((run.after.classification, run.after.head.witness_version), (WR.CONSISTENT, 3))

    def test_re_encoded_pointer_is_rewritten_from_the_chain(self):
        scenario = _rotated()
        head = _doc(scenario.storage, CHAIN, "3.json")
        scenario.storage.plant(STATE, WR.POINTER_NAME, json.dumps(head, indent=1).encode())
        self.assertScan(scenario, WR.POINTER_CORRUPT, WR.ROLL_FORWARD)
        self.assertEqual(scenario.recover().after.classification, WR.CONSISTENT)
        self.assertEqual(scenario.storage.read(STATE, WR.POINTER_NAME), scenario.storage.read(CHAIN, "3.json"))

    def test_never_rolls_backward(self):
        scenario = _rotated()
        scenario.storage.plant(STATE, WR.POINTER_NAME, scenario.storage.read(CHAIN, "1.json"))
        self.assertScan(scenario, WR.POINTER_BEHIND_MULTI, WR.FAIL_CLOSED)
        self.assertUnchangedByRecovery(scenario)

    def test_torn_or_corrupt_successor_fails_closed_without_losing_committed_state(self):
        good = _rotated().storage.read(CHAIN, "2.json")
        corrupt = good.replace(b'"signature":"', b'"signature":"A', 1)
        for label, damaged in (("truncated", good[:-17]), ("empty", b""), ("corrupt", corrupt)):
            with self.subTest(label=label):
                scenario = P.DurableScenario()
                scenario.issue_head_advance()
                scenario.storage.plant(CHAIN, "2.json", damaged)
                scan = self.assertScan(scenario, WR.TORN_TAIL, WR.FAIL_CLOSED)
                self.assertEqual(scan.head.witness_version, 1)
                self.assertUnchangedByRecovery(scenario)
                with self.assertRaises(WS.DurableWitnessRefusal) as caught:
                    scenario.record_ledger()
                self.assertEqual(caught.exception.detail, WR.TORN_TAIL)

    def test_corruption_below_the_head_fails_closed(self):
        scenario = _rotated()
        scenario.storage.plant(CHAIN, "2.json", scenario.storage.read(CHAIN, "2.json")[:-5])
        scan = self.assertScan(scenario, WR.CHAIN_CORRUPT, WR.FAIL_CLOSED)
        self.assertEqual(scan.detail, "2")
        self.assertUnchangedByRecovery(scenario)

    def test_file_fsynced_but_directory_not_is_not_committed(self):
        scenario = P.DurableScenario(fault_hook=P.fault_at("AFTER_CHAIN_FILE_FSYNC"))
        with self.assertRaises(P.InjectedFault):  # the writer never returned a committed witness
            scenario.publish(scenario.issue_head_advance())
        scenario.storage.crash()
        self.assertEqual(self.assertScan(scenario, WR.CONSISTENT).head.witness_version, 1)
        self.assertEqual(scenario.storage.names(CHAIN), ["1.json"])

    def test_contents_not_fsynced_but_entry_persisted_is_torn(self):
        scenario = P.DurableScenario(fault_hook=P.fault_at("AFTER_CHAIN_WRITE"))
        with self.assertRaises(P.InjectedFault):
            scenario.publish(scenario.issue_head_advance())
        scenario.storage.fsync_directory(CHAIN)  # some unrelated later directory fsync
        scenario.storage.crash()
        self.assertScan(scenario, WR.TORN_TAIL, WR.FAIL_CLOSED)

    def test_visible_but_not_durable_head_is_made_durable_before_publication(self):
        scenario = P.DurableScenario(fault_hook=P.fault_at("AFTER_CHAIN_FILE_FSYNC"))
        with self.assertRaises(P.InjectedFault):
            scenario.publish(scenario.issue_head_advance())
        scenario.fault_hook = None
        mark = len(scenario.storage.log)
        run = scenario.recover()
        self.assertEqual(run.before.classification, WR.POINTER_BEHIND_BY_ONE)
        log = scenario.storage.log[mark:]
        self.assertLess(_log_index(log, "fsync_file", CHAIN, "2.json"), _log_index(log, "fsync_dir", CHAIN))
        self.assertLess(_log_index(log, "fsync_dir", CHAIN), _log_index(log, "write", STATE, WR.POINTER_SCRATCH_NAME))
        scenario.storage.crash()
        self.assertEqual(self.assertScan(scenario, WR.CONSISTENT).head.witness_version, 2)

    def test_pointer_ahead_of_the_chain_fails_closed(self):
        scenario = P.DurableScenario()
        scenario.publish(scenario.issue_head_advance())
        scenario.storage.drop(CHAIN, "2.json")
        self.assertScan(scenario, WR.POINTER_AHEAD, WR.FAIL_CLOSED)
        self.assertUnchangedByRecovery(scenario)

    def test_two_valid_successors_from_one_predecessor_fork(self):
        scenario = P.DurableScenario()
        scenario.publish(scenario.issue_head_advance())
        rival = _witness_sign(_doc(scenario.storage, CHAIN, "2.json"), updatedAt=F.stamp(30))
        for where in (WR.POINTER_NAME, WR.POINTER_SCRATCH_NAME):
            with self.subTest(where=where):
                forked = scenario.clone()
                forked.storage.plant(STATE, where, _bytes(rival))
                self.assertScan(forked, WR.FORK, WR.FAIL_CLOSED)
                self.assertUnchangedByRecovery(forked)

    def test_successor_with_head_registry_unavailable(self):
        scenario = P.DurableScenario(fault_hook=P.fault_at("AFTER_CHAIN_DIRECTORY_FSYNC"))
        with self.assertRaises(P.InjectedFault):
            scenario.publish(scenario.issue_head_advance())
        scenario.storage.crash()
        scenario.registries = [F.v3()]
        # Freshness rolls forward (the retained authorization binds the target digest) ...
        self.assertEqual(scenario.recover().after.classification, WR.CONSISTENT)
        # ... but readiness fails closed until the head registry bytes are reinstated.
        result = WR.evaluate_witness_readiness(scenario.readiness_inputs())
        self.assertEqual(result.checks["HEAD_REGISTRY"].reason, "REGISTRY_MISSING")
        self.assertEqual(result.checks["REGISTRY_HISTORY"].reason, "REGISTRY_MISSING")
        self.assertFalse(result.ready)

    def test_successor_with_authorization_unavailable_fails_closed(self):
        scenario = P.DurableScenario(fault_hook=P.fault_at("AFTER_CHAIN_DIRECTORY_FSYNC"))
        with self.assertRaises(P.InjectedFault):
            scenario.publish(scenario.issue_head_advance())
        scenario.storage.crash()
        scenario.storage.drop(AUTHS, WR.retained_authorization_name("rhaa.b1b3e-rotation-1"))
        scan = self.assertScan(scenario, WR.AUTHORIZATION_HISTORY_INVALID, WR.FAIL_CLOSED)
        self.assertTrue(scan.detail.startswith("RETAINED_AUTHORIZATION_MISSING"))
        self.assertUnchangedByRecovery(scenario)

    def test_consumed_authorization_replay_in_the_chain_fails_closed(self):
        scenario = _rotated()
        head = _doc(scenario.storage, CHAIN, "3.json")
        replay = _witness_sign(head, witnessVersion=4, previousWitnessDigest=RC.witness_v2_digest(head),
                               registryVersion=5, registryDigest=F.digest("staged v5"),
                               consumedAuthorizationId="rhaa.b1b3e-rotation-1", updatedAt=F.stamp(20))
        scenario.storage.plant(CHAIN, "4.json", _bytes(replay))
        scenario.storage.plant(STATE, WR.POINTER_NAME, _bytes(replay))
        self.assertScan(scenario, WR.REPLAY_IN_CHAIN, WR.FAIL_CLOSED)

    def test_orphans_and_gaps_fail_closed(self):
        scenario = _rotated()
        head = _doc(scenario.storage, CHAIN, "3.json")
        beyond = _witness_sign(head, witnessVersion=5, previousWitnessDigest=F.digest("missing 4"),
                               ledgerSequence=head["ledgerSequence"] + 1, updatedAt=F.stamp(20))
        gap = scenario.clone()
        gap.storage.plant(CHAIN, "5.json", _bytes(beyond))
        self.assertEqual(self.assertScan(gap, WR.ORPHAN, WR.FAIL_CLOSED).detail, "GAP:4")
        unlinked = _witness_sign(head, witnessVersion=4, previousWitnessDigest=F.digest("not the head"),
                                 ledgerSequence=head["ledgerSequence"] + 1, updatedAt=F.stamp(20))
        tail = scenario.clone()
        tail.storage.plant(CHAIN, "4.json", _bytes(unlinked))
        self.assertEqual(self.assertScan(tail, WR.ORPHAN).detail, "4:WITNESS_CHAIN_BROKEN")
        headless = scenario.clone()
        headless.storage.drop(CHAIN, "1.json")
        self.assertEqual(self.assertScan(headless, WR.ORPHAN).detail, "GENESIS_ABSENT")

    def test_missing_or_corrupt_genesis_and_missing_chain_fail_closed(self):
        scenario = _rotated()
        corrupt = scenario.clone()
        corrupt.storage.plant(CHAIN, "1.json", b"{}")
        self.assertEqual(self.assertScan(corrupt, WR.CHAIN_CORRUPT).detail, "1:GENESIS_INVALID")
        empty = scenario.clone()
        for name in empty.storage.names(CHAIN):
            empty.storage.drop(CHAIN, name)
        self.assertScan(empty, WR.CHAIN_MISSING, WR.FAIL_CLOSED)
        self.assertUnchangedByRecovery(empty)

    def test_scratch_is_discarded_only_when_safe(self):
        scenario = _rotated()
        for label, scratch in (("copy", scenario.storage.read(CHAIN, "3.json")), ("garbage", b"\x00\x01"),
                               ("older", scenario.storage.read(CHAIN, "2.json"))):
            with self.subTest(label=label):
                case = scenario.clone()
                case.storage.plant(STATE, WR.POINTER_SCRATCH_NAME, scratch)
                run = case.recover()
                self.assertEqual((run.before.classification, run.actions), (WR.CONSISTENT, ("SCRATCH_DISCARDED",)))
                self.assertNotIn(WR.POINTER_SCRATCH_NAME, case.storage.names(STATE))
        head = _doc(scenario.storage, CHAIN, "3.json")
        ahead = _witness_sign(head, witnessVersion=4, previousWitnessDigest=RC.witness_v2_digest(head),
                              ledgerSequence=head["ledgerSequence"] + 1, updatedAt=F.stamp(20))
        scenario.storage.plant(STATE, WR.POINTER_SCRATCH_NAME, _bytes(ahead))
        self.assertScan(scenario, WR.SCRATCH_ORDERING_VIOLATION, WR.FAIL_CLOSED)
        self.assertUnchangedByRecovery(scenario)

    def test_unexpected_entries_fail_closed(self):
        scenario = P.DurableScenario()
        cases = [(CHAIN, "latest.json", WR.REGULAR), (CHAIN, "02.json", WR.REGULAR), (CHAIN, "2.json", WR.SYMLINK),
                 (CHAIN, "2.json", WR.DIRECTORY), (CHAIN, "2.json", WR.OTHER), (STATE, "witness.json.bak", WR.REGULAR),
                 (STATE, WR.POINTER_NAME, WR.SYMLINK), (STATE, "fifo", WR.OTHER), (AUTHS, "x.json", WR.REGULAR)]
        for directory, name, kind in cases:
            with self.subTest(directory=directory, name=name, kind=kind):
                case = scenario.clone()
                case.storage.drop(directory, name)
                case.storage.plant(directory, name, b"{}", kind=kind)
                self.assertScan(case, WR.UNEXPECTED_ENTRY, WR.FAIL_CLOSED)

    def test_retention_store_corruption_fails_closed(self):
        scenario = _rotated()
        name = WR.retained_authorization_name("rhaa.b1b3e-rotation-1")
        misnamed = scenario.clone()
        misnamed.storage.plant(AUTHS, WR.retained_authorization_name("rhaa.other-1"), misnamed.storage.read(AUTHS, name))
        self.assertScan(misnamed, WR.RETENTION_CORRUPT, WR.FAIL_CLOSED)
        torn = scenario.clone()
        torn.storage.plant(AUTHS, WR.retained_authorization_name("rhaa.unused-1"), b'{"authorizationId":')
        self.assertScan(torn, WR.RETENTION_CORRUPT, WR.FAIL_CLOSED)

    def test_filenames_never_decide_the_head(self):
        scenario = _rotated()
        swapped = scenario.clone()
        two, three = swapped.storage.read(CHAIN, "2.json"), swapped.storage.read(CHAIN, "3.json")
        swapped.storage.plant(CHAIN, "2.json", three)
        swapped.storage.plant(CHAIN, "3.json", two)
        self.assertEqual(self.assertScan(swapped, WR.CHAIN_CORRUPT).detail, "2")

    def test_no_mtime_and_no_listing_order_dependence(self):
        self.assertEqual({f.name for f in dataclasses.fields(WR.StoreEntryV1)}, {"name", "kind", "data"})
        forward, backward = _rotated(), _rotated()
        backward.storage.reverse_listing = True
        a, b = forward.scan(), backward.scan()
        self.assertEqual((a.classification, a.head, a.facts), (b.classification, b.head, b.facts))
        shuffled = WS.observe_witness_store(forward.storage)
        shuffled = WR.WitnessStoreObservationV1(tuple(reversed(shuffled.state_entries)),
                                                tuple(reversed(shuffled.chain_entries)),
                                                tuple(reversed(shuffled.authorization_entries)))
        c = WR.classify_witness_store(observation=shuffled, context=forward.context())
        self.assertEqual((c.classification, c.head, c.facts), (a.classification, a.head, a.facts))

    def test_recovery_is_idempotent(self):
        scenario = P.DurableScenario(fault_hook=P.fault_at("AFTER_POINTER_SCRATCH_WRITE"))
        with self.assertRaises(P.InjectedFault):
            scenario.publish(scenario.issue_head_advance())
        first = scenario.recover()
        snapshot = scenario.storage.snapshot()
        for _ in range(3):
            again = scenario.recover()
            self.assertEqual((again.before.classification, again.actions), (WR.CONSISTENT, ()))
            self.assertEqual(scenario.storage.snapshot(), snapshot)
        self.assertEqual(first.after.head, again.after.head)

    def test_recovery_holds_no_key_and_cannot_produce_a_witness(self):
        self.assertEqual(set(inspect.signature(WS.recover_witness_store).parameters),
                         {"storage", "context", "fault_hook"})
        source = inspect.getsource(WS.recover_witness_store)
        for forbidden in ("sign", "_signed", "signing_key", "private"):
            self.assertNotIn(forbidden, source.split('"""')[2])
        self.assertFalse(WR.classify_witness_store(observation=WS.observe_witness_store(_rotated().storage),
                                                   context=_rotated().context()).facts["producesWitness"])


# ---------------------------------------------------------- fault seams ---

# (seam, committed?) for one head advance. Committed means the chain entry
# reached the commit point before the fault (RR-9 §6.2).
WRITER_SEAMS = {
    "BEFORE_RETENTION_CREATE": False, "AFTER_RETENTION_WRITE": False, "AFTER_RETENTION_FILE_FSYNC": False,
    "AFTER_RETENTION_DIRECTORY_FSYNC": False, "BEFORE_CHAIN_CREATE": False, "AFTER_CHAIN_WRITE": False,
    "AFTER_CHAIN_FILE_FSYNC": False, "AFTER_CHAIN_DIRECTORY_FSYNC": True, "AFTER_POINTER_SCRATCH_WRITE": True,
    "AFTER_POINTER_SCRATCH_FSYNC": True, "AFTER_POINTER_REPLACE": True, "AFTER_POINTER_DIRECTORY_FSYNC": True,
}


class FaultSeamTests(unittest.TestCase):
    def test_seam_table_covers_every_writer_seam(self):
        self.assertEqual(tuple(WRITER_SEAMS), WS.FAULT_POINTS)

    def test_every_writer_seam_after_a_crash(self):
        for point, committed in WRITER_SEAMS.items():
            with self.subTest(point=point):
                scenario = P.DurableScenario(fault_hook=P.fault_at(point))
                authorization = scenario.issue_head_advance()
                with self.assertRaises(P.InjectedFault):
                    scenario.publish(authorization)
                scenario.storage.crash()
                scenario.fault_hook = None
                run = scenario.recover()
                expected_before = {False: {WR.CONSISTENT},
                                   True: {WR.POINTER_BEHIND_BY_ONE, WR.CONSISTENT}}[committed]
                self.assertIn(run.before.classification, expected_before)
                if point == "AFTER_POINTER_DIRECTORY_FSYNC":
                    self.assertEqual(run.before.classification, WR.CONSISTENT)
                elif committed:
                    self.assertEqual(run.before.classification, WR.POINTER_BEHIND_BY_ONE)
                self.assertEqual(run.after.classification, WR.CONSISTENT)
                self.assertEqual(run.after.head.witness_version, 2 if committed else 1)
                if not committed:
                    scenario.publish(authorization)
                    self.assertEqual(scenario.scan().head.registry_version, 4)

    def test_every_writer_seam_without_a_crash(self):
        for point in WS.FAULT_POINTS:
            with self.subTest(point=point):
                scenario = P.DurableScenario(fault_hook=P.fault_at(point))
                authorization = scenario.issue_head_advance()
                with self.assertRaises(P.InjectedFault):
                    scenario.publish(authorization)
                scenario.fault_hook = None
                run = scenario.recover()
                self.assertEqual(run.after.classification, WR.CONSISTENT)
                # A durable-by-recovery head survives a later crash; nothing rolls back.
                head = run.after.head.witness_version
                scenario.storage.crash()
                self.assertEqual(scenario.scan().head.witness_version, head)
                if head == 1:
                    scenario.publish(authorization)
                self.assertEqual(scenario.scan().head.registry_version, 4)

    def test_restart_during_recovery_at_every_recovery_seam(self):
        for point in WS.RECOVERY_FAULT_POINTS[:-1]:
            with self.subTest(point=point):
                scenario = P.DurableScenario(fault_hook=P.fault_at("AFTER_CHAIN_DIRECTORY_FSYNC"))
                with self.assertRaises(P.InjectedFault):
                    scenario.publish(scenario.issue_head_advance())
                scenario.storage.crash()
                scenario.fault_hook = None
                with self.assertRaises(P.InjectedFault):
                    scenario.recover(fault_hook=P.fault_at(point))
                scenario.storage.crash()
                run = scenario.recover()
                self.assertEqual((run.after.classification, run.after.head.witness_version), (WR.CONSISTENT, 2))
                self.assertEqual(scenario.storage.names(CHAIN), ["1.json", "2.json"])

    def test_restart_during_scratch_discard(self):
        scenario = _rotated()
        scenario.storage.plant(STATE, WR.POINTER_SCRATCH_NAME, b"scratch")
        with self.assertRaises(P.InjectedFault):
            scenario.recover(fault_hook=P.fault_at("RECOVERY_AFTER_SCRATCH_REMOVE"))
        scenario.storage.crash()
        run = scenario.recover()
        self.assertEqual((run.before.classification, run.actions), (WR.CONSISTENT, ("SCRATCH_DISCARDED",)))
        self.assertEqual(run.after.classification, WR.CONSISTENT)

    def test_epoch_advance_seams_after_a_crash(self):
        for point, committed in (("AFTER_RETENTION_DIRECTORY_FSYNC", False), ("AFTER_CHAIN_FILE_FSYNC", False),
                                 ("AFTER_CHAIN_DIRECTORY_FSYNC", True), ("AFTER_POINTER_REPLACE", True)):
            with self.subTest(point=point):
                scenario = _rotated()
                scenario.fault_hook = P.fault_at(point)
                with self.assertRaises(P.InjectedFault):
                    scenario.epoch_advance()
                scenario.storage.crash()
                scenario.fault_hook = None
                run = scenario.recover()
                self.assertEqual(run.after.classification, WR.CONSISTENT)
                self.assertEqual(run.after.head.current_recovery_epoch == F.E3, committed)


# ------------------------------------------------ SW-6 credential inventory ---

class CredentialInventoryTests(unittest.TestCase):
    def check(self, inventory, phase=WR.STEADY):
        return WR.verify_credential_inventory(inventory=inventory, phase=phase)

    def test_expected_current_only(self):
        result = self.check(P.inventory())
        self.assertTrue(result.verified, result.reason)
        self.assertEqual(result.facts["currentSlotSha256"], F.SUCCESSOR_BLOB_SHA256)
        self.assertEqual(result.facts["loadableBlobs"], 1)
        self.assertFalse(result.facts["authorityGranted"])
        self.assertFalse(result.facts["selectsAuthoritativeKey"])

    def test_prepared_successor_only_where_the_phase_permits(self):
        prepared = P.inventory(prepared=(P.blob(name="successor.cred", sha256=P.OTHER_BLOB_SHA256),))
        self.assertTrue(self.check(prepared, WR.SUCCESSOR_PREPARED).verified)
        self.assertEqual(self.check(prepared).reason, "PREPARED_SLOT_NOT_PERMITTED")
        self.assertEqual(self.check(P.inventory(), WR.SUCCESSOR_PREPARED).reason, "PREPARED_SLOT_MISSING")

    def test_current_missing_or_not_permitted(self):
        self.assertEqual(self.check(P.inventory(current=())).reason, "CURRENT_SLOT_MISSING")
        vacated = P.inventory(current=(), prepared=(P.blob(name="s.cred", sha256=P.OTHER_BLOB_SHA256),),
                              retired=(P.blob(name="p.cred", sha256=P.PREDECESSOR_BLOB_SHA256),))
        self.assertTrue(self.check(vacated, WR.CUTOVER_VACATED).verified)
        crowded = P.inventory(prepared=(P.blob(name="s.cred", sha256=P.OTHER_BLOB_SHA256),),
                              retired=(P.blob(name="p.cred", sha256=P.PREDECESSOR_BLOB_SHA256),))
        self.assertEqual(self.check(crowded, WR.CUTOVER_VACATED).reason, "CURRENT_SLOT_NOT_PERMITTED")

    def test_duplicate_or_current_looking_blobs_are_refused(self):
        for name in ("lilith-authority-dev.owner-actor.cred.bak", "lilith-authority-dev.owner-actor.next.cred",
                     "owner-actor-signing-key"):
            with self.subTest(name=name):
                inv = P.inventory(current=(None, P.blob(name=name, sha256=P.OTHER_BLOB_SHA256)))
                self.assertEqual((self.check(inv).reason, self.check(inv).detail),
                                 ("UNEXPECTED_CREDENTIAL_BLOB", name))
        copy_of_current = P.inventory(prepared=(P.blob(name="successor.cred"),))
        self.assertEqual(self.check(copy_of_current, WR.SUCCESSOR_PREPARED).reason, "DUPLICATE_CREDENTIAL_BLOB")

    def test_entry_type_owner_group_and_mode(self):
        cases = {
            "CREDENTIAL_ENTRY_NOT_REGULAR": [dict(kind=WR.SYMLINK), dict(kind=WR.DIRECTORY), dict(kind=WR.OTHER)],
            "CREDENTIAL_OWNER_MISMATCH": [dict(uid=990)],
            "CREDENTIAL_GROUP_MISMATCH": [dict(gid=990)],
            "CREDENTIAL_MODE_MISMATCH": [dict(mode=0o640), dict(mode=0o400)],
            "CREDENTIAL_HASH_UNOBSERVED": [dict(sha256=None), dict(sha256="xyz")],
        }
        for reason, changes in cases.items():
            for change in changes:
                with self.subTest(reason=reason, change=change):
                    self.assertEqual(self.check(P.inventory(current=(P.blob(**change),))).reason, reason)
        unobserved = P.inventory(current=(P.blob(uid=None),))
        self.assertEqual(self.check(unobserved).reason, "CREDENTIAL_OWNER_MISMATCH")

    def test_unexpected_directory_entry_in_the_credstore(self):
        inv = P.inventory(current=(None, P.blob(name="subdir", kind=WR.DIRECTORY, sha256=None)))
        self.assertEqual(self.check(inv).reason, "CREDENTIAL_ENTRY_NOT_REGULAR")

    def test_two_candidate_successors_or_retired_blobs(self):
        two = P.inventory(prepared=(P.blob(name="a.cred", sha256=P.OTHER_BLOB_SHA256),
                                    P.blob(name="b.cred", sha256=P.PREDECESSOR_BLOB_SHA256)))
        self.assertEqual(self.check(two, WR.SUCCESSOR_PREPARED).reason, "MULTIPLE_PREPARED_CANDIDATES")
        retired = P.inventory(retired=(P.blob(name="a.cred", sha256=P.OTHER_BLOB_SHA256),
                                       P.blob(name="b.cred", sha256=P.PREDECESSOR_BLOB_SHA256)))
        self.assertEqual(self.check(retired, WR.CUTOVER_INSTALLED).reason, "MULTIPLE_RETIRED_BLOBS")
        one = P.inventory(retired=(P.blob(name="a.cred", sha256=P.OTHER_BLOB_SHA256),))
        self.assertEqual(self.check(one).reason, "RETIRED_SLOT_NOT_PERMITTED")
        self.assertEqual(self.check(P.inventory(), WR.CUTOVER_INSTALLED).reason, "RETIRED_SLOT_MISSING")

    def test_locations(self):
        base = P.inventory()
        no_credstore = WR.CredentialInventoryObservationV1(base.locations[1:])
        self.assertEqual(self.check(no_credstore).reason, "CREDSTORE_MISSING")
        for change, reason in ((dict(kind=WR.SYMLINK), "LOCATION_NOT_DIRECTORY"),
                               (dict(uid=990), "LOCATION_OWNER_MISMATCH"), (dict(gid=990), "LOCATION_GROUP_MISMATCH"),
                               (dict(mode=0o755), "LOCATION_MODE_MISMATCH")):
            with self.subTest(reason=reason):
                changed = dataclasses.replace(base.locations[0], **change)
                self.assertEqual(self.check(WR.CredentialInventoryObservationV1((changed,) + base.locations[1:])).reason,
                                 reason)
        prepared = P.location(WR.PREPARED, uid=990)
        self.assertEqual(self.check(WR.CredentialInventoryObservationV1(
            (base.locations[0], prepared, base.locations[2]))).reason, "LOCATION_OWNER_MISMATCH")
        extra = P.inventory(extra=(P.location("BACKUP"),))
        self.assertEqual(self.check(extra).reason, "UNEXPECTED_LOCATION")
        twice = P.inventory(extra=(P.location(WR.PREPARED),))
        self.assertEqual(self.check(twice).reason, "UNEXPECTED_LOCATION")
        self.assertEqual(self.check(base, "S_CURRENT").reason, "INVENTORY_PHASE_UNKNOWN")
        self.assertEqual(self.check(None).reason, "INVENTORY_INPUT_MALFORMED")

    def test_phase_by_inventory_matrix(self):
        hashes = iter(hashlib.sha256(f"TEST_ONLY matrix blob {i}".encode()).hexdigest() for i in range(10 ** 6))
        for counts in itertools.product(range(3), repeat=3):
            current = tuple(P.blob(sha256=next(hashes)) for _ in range(min(counts[0], 1)))
            if counts[0] == 2:
                current += (P.blob(name="lilith-authority-dev.owner-actor.cred.2", sha256=next(hashes)),)
            prepared = tuple(P.blob(name=f"p{i}.cred", sha256=next(hashes)) for i in range(counts[1]))
            retired = tuple(P.blob(name=f"r{i}.cred", sha256=next(hashes)) for i in range(counts[2]))
            inv = P.inventory(current=current, prepared=prepared, retired=retired)
            for phase, expected in WR.INVENTORY_PHASES.items():
                with self.subTest(counts=counts, phase=phase):
                    self.assertEqual(self.check(inv, phase).verified, counts == expected)

    def test_valid_inventory_with_the_wrong_key_grants_nothing(self):
        scenario = _rotated()
        inv = P.inventory(current=(P.blob(sha256=P.OTHER_BLOB_SHA256),))
        self.assertTrue(self.check(inv).verified)
        result = WR.evaluate_witness_readiness(scenario.readiness_inputs(
            credential_inventory=inv, observed_blob_sha256=P.OTHER_BLOB_SHA256))
        self.assertFalse(result.ready)
        self.assertEqual(result.checks["CREDENTIAL_INVENTORY"].status, WR.PASS)
        self.assertEqual(result.checks["LOADED_KEY_BINDING"].reason, "BLOB_HASH_MISMATCH")

    def test_unexpected_inventory_blocks_readiness(self):
        scenario = _rotated()
        inv = P.inventory(current=(None, P.blob(name="stray.cred", sha256=P.OTHER_BLOB_SHA256)))
        result = WR.evaluate_witness_readiness(scenario.readiness_inputs(credential_inventory=inv))
        self.assertFalse(result.ready)
        self.assertEqual(result.checks["CREDENTIAL_INVENTORY"].reason, "UNEXPECTED_CREDENTIAL_BLOB")
        self.assertEqual(result.checks["LOADED_KEY_BINDING"].reason, "CREDENTIAL_INVENTORY_NOT_VERIFIED")

    def test_slot_contract_equals_current_authority_dev_source(self):
        sys.path.insert(0, str(ROOT / "services/authority-dev"))
        from lilith_authority_dev import profile
        self.assertEqual(C.credential_name, profile.CREDENTIAL_NAME)
        self.assertEqual(C.current_slot_path, profile.CREDENTIAL_SOURCE)
        self.assertEqual(C.unit_name, profile.SERVICE_UNIT)
        keygen = (ROOT / "services/authority-dev/ceremony/lilith_authority_keygen_dev.py").read_text(encoding="utf-8")
        self.assertIn(f'CREDENTIAL_NAME = "{C.credential_name}"', keygen)
        self.assertIn(f'CREDSTORE = "{C.credstore_directory}"', keygen)
        self.assertIn("_root_owned(host, host.path(CREDSTORE), kind=\"dir\", mode=0o700", keygen)
        self.assertIn("os.open(path, flags, 0o600)", keygen)
        unit = (ROOT / "services/authority-dev/deploy/lilith-authority-dev.service").read_text(encoding="utf-8")
        references = re.findall(r"^(\w*Credential\w*)=(.*)$", unit, flags=re.M)
        self.assertEqual(references, [(WR.LOAD_CREDENTIAL_ENCRYPTED, f"{C.credential_name}:{C.current_slot_path}")])


# ---------------------------------------------------- readiness aggregation ---

class ReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario = _rotated()

    def evaluate(self, scenario=None, **overrides):
        return WR.evaluate_witness_readiness((scenario or self.scenario).readiness_inputs(**overrides))

    def failing(self, result):
        return {name for name, outcome in result.checks.items() if outcome.status != WR.PASS}

    def test_all_checks_pass_but_nothing_is_granted_or_authorized(self):
        result = self.evaluate()
        self.assertTrue(result.ready, result.reasons)
        self.assertEqual(tuple(result.checks), WR.READINESS_CHECKS)
        self.assertEqual(result.facts["authorityGranted"], False)
        self.assertEqual(result.facts["liveEntryAuthorized"], False)
        self.assertEqual(result.facts["wholeHostRollbackProtected"], False)
        self.assertFalse(result.facts["loadedKeyBinding"]["authorityGranted"])

    def test_each_condition_fails_independently(self):
        ahead = _ledger_step(self.scenario.ledger)
        cases = {
            "GENESIS_PIN": dict(store=self.scenario.context(genesis_pin=P.genesis_pin(
                self.scenario.genesis, genesisWitnessDigest=F.digest("pin")))),
            "AUTHORIZATION_HISTORY": dict(store=self.scenario.context(
                owner_register=P.owner_register({}, self.scenario.heads))),
            "HEAD_REGISTRY": dict(head_registries=(F.v3(),)),
            "REGISTRY_HISTORY": dict(head_registries=(F.v4(),)),
            "SINGLE_CURRENT_KEY": dict(evidence_type="PRIVACY_AUTHORIZATION"),
            "AUTHORITY_LEDGER_POSITION": dict(ledger_observation=W2.observe_authority_recovery_ledger(ahead)),
            "CREDENTIAL_INVENTORY": dict(credential_inventory=P.inventory(current=())),
            "LOADED_KEY_BINDING": dict(health=F.health("other")),
            "CEREMONY_HOLD": dict(hold_present=True),
        }
        expected = {
            # A chain not anchored at the pinned genesis is never evaluated further.
            "GENESIS_PIN": set(WR.READINESS_CHECKS) - {"CREDENTIAL_INVENTORY", "CEREMONY_HOLD"},
            "AUTHORIZATION_HISTORY": {"WITNESS_CHAIN", "AUTHORIZATION_HISTORY"},
            "HEAD_REGISTRY": {"HEAD_REGISTRY", "REGISTRY_HISTORY", "SINGLE_CURRENT_KEY", "LOADED_KEY_BINDING"},
            "REGISTRY_HISTORY": {"REGISTRY_HISTORY"},
            "SINGLE_CURRENT_KEY": {"SINGLE_CURRENT_KEY", "LOADED_KEY_BINDING"},
            "AUTHORITY_LEDGER_POSITION": {"AUTHORITY_LEDGER_POSITION"},
            "CREDENTIAL_INVENTORY": {"CREDENTIAL_INVENTORY", "LOADED_KEY_BINDING"},
            "LOADED_KEY_BINDING": {"LOADED_KEY_BINDING"},
            "CEREMONY_HOLD": {"CEREMONY_HOLD"},
        }
        for name, change in cases.items():
            with self.subTest(check=name):
                result = self.evaluate(**change)
                self.assertFalse(result.ready)
                self.assertEqual(self.failing(result), expected[name], result.reasons)

    def test_stale_pointer_is_not_repaired_by_readers(self):
        scenario = P.DurableScenario(fault_hook=P.fault_at("AFTER_CHAIN_DIRECTORY_FSYNC"))
        with self.assertRaises(P.InjectedFault):
            scenario.publish(scenario.issue_head_advance())
        before = scenario.storage.snapshot()
        result = self.evaluate(scenario)
        self.assertEqual((result.checks["WITNESS_CHAIN"].reason, result.checks["WITNESS_CHAIN"].detail),
                         ("WITNESS_POINTER_STALE", WR.POINTER_BEHIND_BY_ONE))
        self.assertEqual(scenario.storage.snapshot(), before)

    def test_unverifiable_chain_leaves_dependent_checks_not_evaluated(self):
        scenario = _rotated()
        for name in scenario.storage.names(CHAIN):
            scenario.storage.drop(CHAIN, name)
        result = self.evaluate(scenario)
        self.assertEqual(result.checks["WITNESS_CHAIN"].reason, WR.CHAIN_MISSING)
        for name in ("GENESIS_PIN", "AUTHORIZATION_HISTORY", "HEAD_REGISTRY", "LOADED_KEY_BINDING"):
            self.assertEqual(result.checks[name].status, WR.NOT_EVALUATED)
        self.assertEqual(result.checks["CEREMONY_HOLD"].status, WR.PASS)

    def test_every_failure_is_reported_not_collapsed(self):
        result = self.evaluate(hold_present=None, credential_inventory=P.inventory(current=()),
                               ledger_observation=None)
        self.assertEqual(set(result.reasons), {"AUTHORITY_LEDGER_POSITION:LEDGER_OBSERVATION_ABSENT",
                                               "CREDENTIAL_INVENTORY:CURRENT_SLOT_MISSING",
                                               "LOADED_KEY_BINDING:CREDENTIAL_INVENTORY_NOT_VERIFIED",
                                               "CEREMONY_HOLD:CEREMONY_HOLD_UNOBSERVED"})

    def test_successor_prepared_phase_is_never_ready(self):
        inv = P.inventory(prepared=(P.blob(name="s.cred", sha256=P.OTHER_BLOB_SHA256),))
        result = self.evaluate(credential_inventory=inv, inventory_phase=WR.SUCCESSOR_PREPARED)
        self.assertEqual(result.checks["CREDENTIAL_INVENTORY"].reason, "CREDENTIAL_INVENTORY_PHASE_NOT_READY")
        self.assertFalse(result.ready)

    def test_whole_host_rollback_is_not_detected(self):
        scenario = P.DurableScenario()
        saved = copy.deepcopy((scenario.storage, scenario.ledger))
        scenario.rotate()
        scenario.storage, scenario.ledger = saved
        scenario.writer._storage = scenario.storage
        scan = scenario.scan()
        self.assertEqual((scan.classification, scan.head.witness_version), (WR.CONSISTENT, 1))
        self.assertFalse(scan.facts["wholeHostRollbackProtected"])
        self.assertEqual(scan.facts["rollbackDetectionScope"], "LEDGER_ONLY")


# -------------------------------------------------- real temp directory ---

@unittest.skipUnless(os.name == "posix" and hasattr(os, "O_DIRECTORY"), "POSIX directory fsync")
class TempDirectoryStorageTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory(prefix="b1b3e-prep-a-")
        self.storage = P.TempDirectoryStorage(self._dir.name)

    def tearDown(self):
        self._dir.cleanup()

    def test_bootstrap_rotation_and_recovery_on_a_real_directory(self):
        scenario = P.DurableScenario(storage=self.storage)
        scenario.rotate()
        self.assertEqual(scenario.scan().classification, WR.CONSISTENT)
        self.assertEqual(sorted(os.listdir(os.path.join(self._dir.name, CHAIN))), ["1.json", "2.json", "3.json"])
        self.assertIn(("fsync_dir", CHAIN), self.storage.log)
        mode = os.stat(os.path.join(self._dir.name, CHAIN, "2.json")).st_mode & 0o777
        self.assertEqual(mode & 0o077, 0)

    def test_fault_then_recovery_on_a_real_directory(self):
        scenario = P.DurableScenario(storage=self.storage)
        scenario.fault_hook = P.fault_at("AFTER_CHAIN_DIRECTORY_FSYNC")
        with self.assertRaises(P.InjectedFault):
            scenario.publish(scenario.issue_head_advance())
        scenario.fault_hook = None
        run = scenario.recover()
        self.assertEqual((run.before.classification, run.after.classification),
                         (WR.POINTER_BEHIND_BY_ONE, WR.CONSISTENT))

    def test_exclusive_create_and_no_link_following(self):
        scenario = P.DurableScenario(storage=self.storage)
        with self.assertRaises(FileExistsError):
            self.storage.create_exclusive(CHAIN, "1.json", b"x")
        os.symlink(os.path.join(self._dir.name, CHAIN, "1.json"), os.path.join(self._dir.name, CHAIN, "2.json"))
        self.assertEqual(scenario.scan().classification, WR.UNEXPECTED_ENTRY)

    def test_special_file_is_unexpected(self):
        scenario = P.DurableScenario(storage=self.storage)
        os.mkfifo(os.path.join(self._dir.name, "fifo"))
        self.assertEqual(scenario.scan().classification, WR.UNEXPECTED_ENTRY)

    def test_flock_serializes_writers(self):
        scenario = P.DurableScenario(storage=self.storage)
        with self.storage.lock():
            with self.assertRaises(P.LockHeld):
                scenario.record_ledger()


# ----------------------------------------- compatibility and structure ---

class CompatibilityAndStructureTests(unittest.TestCase):
    def test_contract_module_is_pure_and_holds_no_key(self):
        path = PACKAGE / "witness_readiness.py"
        source = path.read_text(encoding="utf-8")
        for forbidden in ("os", "sys", "subprocess", "socket", "pathlib", "sqlite3", "urllib", "http", "requests",
                          "lilith_memory_broker", "lilith_memory.config", "time", "random", "secrets", "shutil"):
            self.assertFalse(any(n == forbidden or n.startswith(forbidden + ".") for n in _imports(path)), forbidden)
        for forbidden in ("open(", "os.environ", "getenv", "datetime.now", "Ed25519PrivateKey", "sign(",
                          "private_bytes", "/home/"):
            self.assertNotIn(forbidden, source)

    def test_store_module_performs_no_io_of_its_own(self):
        path = SIGNER_PACKAGE / "synthetic_witness_store.py"
        source = path.read_text(encoding="utf-8")
        for forbidden in ("os", "sys", "subprocess", "socket", "pathlib", "sqlite3", "shutil", "tempfile", "fcntl",
                          "time", "random", "secrets", "lilith_memory_broker"):
            self.assertFalse(any(n == forbidden or n.startswith(forbidden + ".") for n in _imports(path)), forbidden)
        code = re.sub(r'"""[\s\S]*?"""', "", source)
        for forbidden in ("open(", "datetime.now", "owner_control", "synthetic_evidence_ledger", "l04_v2_adapter",
                          "memory_broker", "/etc/", "/var/", "credstore"):
            self.assertNotIn(forbidden, code)

    def test_new_modules_are_not_reachable_from_runtime_code(self):
        runtime = [p for p in list((ROOT / "services/core-api").rglob("*.py"))
                   + list((ROOT / "services/memory-broker").rglob("*.py")) + list((ROOT / "scripts").rglob("*.py"))
                   + list((ROOT / "services/authority-dev").rglob("*.py"))
                   if ".venv" not in p.parts and "tests" not in p.parts]
        self.assertTrue(runtime)
        for path in runtime:
            text = path.read_text(encoding="utf-8", errors="ignore")
            # B1b-3e PR-1S (S-4..S-15) imports the pure readiness contracts in the authority-dev
            # release; the TEST durable writer stays unreachable everywhere.
            authority = "authority-dev" in path.parts
            for forbidden in ("synthetic_witness_store",) if authority else ("witness_readiness",
                                                                              "synthetic_witness_store"):
                with self.subTest(path=path.name, forbidden=forbidden):
                    self.assertIsNone(re.search(rf"(?<![A-Za-z0-9_]){forbidden}(?![A-Za-z0-9_])", text))

    def test_entry_points_take_public_material_only(self):
        for function in (WR.verify_witness_v2_genesis, WR.plan_bound_witness_v2_genesis, WR.genesis_pin_reason,
                         WR.verify_authorization_history, WR.classify_witness_store, WR.verify_credential_inventory,
                         WR.verify_current_credential_binding, WR.evaluate_witness_readiness,
                         WR.verify_head_registry_history, WS.recover_witness_store):
            parameters = set(inspect.signature(function).parameters)
            with self.subTest(function=function.__name__):
                self.assertFalse({p for p in parameters if "private" in p or "seed" in p or "signer" in p
                                  or p.endswith("_key")})

    def test_writer_is_test_only(self):
        storage = P.SimulatedDurableStorage()
        with self.assertRaises(ValueError):
            WS.DurableWitnessV2WriterV1(signing_key=F.private("witness"), witness_key_id=F.WITNESS_KEY_ID,
                                        environment="dev", storage=storage)
        with self.assertRaises(ValueError):
            WS.DurableWitnessV2WriterV1(signing_key=F.private("witness"),
                                        witness_key_id="dev-synthetic.witness.1", environment=F.ENV, storage=storage)
        writer = WS.DurableWitnessV2WriterV1(signing_key=F.private("witness"), witness_key_id=F.WITNESS_KEY_ID,
                                             environment=F.ENV, storage=storage)
        for attempt in (copy.copy, copy.deepcopy):
            with self.assertRaises(TypeError):
                attempt(writer)

    def test_prior_contracts_are_unchanged(self):
        import test_b1b3e_rotation_recovery as E
        self.assertEqual(hashlib.sha256(F.GOLDEN_PATH.read_bytes()).hexdigest(), E.GOLDEN_SHA256)
        import test_b1b3b_broker_signing_l04_v2 as B3B
        for relative, expected in B3B.GOLDEN_SHA256.items():
            with self.subTest(path=relative):
                self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), expected)
        self.assertEqual(RC.WITNESS_V2_FIELDS, frozenset({
            "protocol", "schemaVersion", "environment", "witnessVersion", "previousWitnessDigest",
            "currentRecoveryEpoch", "registryVersion", "registryDigest", "policyVersion", "ledgerSequence",
            "ledgerHead", "consumedAuthorizationId", "updatedAt", "witnessKeyId", "signature"}))
        self.assertEqual(RC.WITNESS_V2_SCHEMA_VERSION, 2)
        self.assertEqual(R.WITNESS_SCHEMA_VERSION, 1)

    def test_compromise_is_still_retroactive(self):
        evidence = SA.owner_evidence(keyId="actor.compromised-1", registryVersion=2, issuedAt="2026-09-20T12:00:00Z")
        from lilith_owner_memory import authority_verifier as AV
        result = AV.verify_owner_evidence(context=SA.historical_context(), registry=SA.registry(), evidence=evidence,
                                          expectation=SA.owner_expectation())
        self.assertEqual(result.reason, "KEY_COMPROMISED")

    def test_record_states_the_honest_status(self):
        text = RECORD.read_text(encoding="utf-8")
        for status in ("**SOURCE IMPLEMENTED / TEST PROVEN**", "**LIVE INSTALL ABSENT**",
                       "**LIVE REHEARSAL NOT AUTHORIZED**", "**WHOLE-HOST ROLLBACK UNRESOLVED**"):
            self.assertIn(status, text)
        for remaining in ("SW-1", "SW-2", "SW-9", "PR-1", "PR-2", "PR-3", "RR-11-D1", "RR-11-D2"):
            self.assertIn(remaining, text)
        self.assertNotRegex(text, r"(?i)whole-host rollback (is )?(solved|protected|detected)\b")
        self.assertNotRegex(text, r"(?i)(?<!no )(?<!not )\blive[ -](entry|rehearsal) (is |was )?authori[sz]ed")


# ---------------------------------------------------------------- golden ---

class GoldenVectorTests(unittest.TestCase):
    def test_golden_file_matches_the_fixture(self):
        committed = json.loads(P.GOLDEN_PATH.read_text(encoding="utf-8"))
        self.assertEqual(committed, json.loads(json.dumps(P.golden_document())))

    def test_golden_file_is_pinned(self):
        self.assertEqual(hashlib.sha256(P.GOLDEN_PATH.read_bytes()).hexdigest(), GOLDEN_SHA256)

    def test_golden_genesis_verifies_and_matches_its_pin(self):
        golden = json.loads(P.GOLDEN_PATH.read_text(encoding="utf-8"))
        result = WR.verify_witness_v2_genesis(anchor=F.anchor(), genesis=golden["genesisWitness"],
                                              expectation=P.genesis_expectation(), registry=F.v3(),
                                              registry_root=F.root())
        self.assertTrue(result.verified, result.reason)
        self.assertEqual(result.facts["genesisWitnessDigest"], golden["genesisPin"]["genesisWitnessDigest"])
        self.assertEqual(golden["chainEntryNames"], ["1.json", "2.json", "3.json"])


if __name__ == "__main__":
    unittest.main()
