"""15B2b-B1b-3e PR-1S recovery-witness tests (repository only).

Every witness here is TEST material: the TEST environment `test`, the
existing TEST_ONLY fixture seeds, in-memory or temporary-directory storage.
Nothing contacts DEV or PROD; no real K-WIT, genesis, or store exists.
"""

from __future__ import annotations

import base64
import configparser
import copy
import json
import os
import pickle
import socket
import struct
import tempfile
import unittest
from pathlib import Path

import rfc8785

import witness_fixtures as X
from witness_fixtures import F, PA_FX, PB, SC, SR, WR, B, J, RC

from lilith_authority_host import inputs as HI
from lilith_authority_host import paths as HP
from lilith_owner_memory import pr1_acceptance as PA
from lilith_recovery_witness import core as CORE
from lilith_recovery_witness import credential as CRED
from lilith_recovery_witness import profile as PR
from lilith_recovery_witness import protocol as WP
from lilith_recovery_witness import server as S
from lilith_recovery_witness import storage as ST
from lilith_recovery_witness import writer as W
from lilith_authority_signer import synthetic_witness_store as TEST_WS

ROOT = X.ROOT
SERVICE = ROOT / "services/recovery-witness"
POSIX = os.name == "posix"
CHAIN, AUTHS, STATE = WR.CHAIN_DIRECTORY, WR.AUTHORIZATION_DIRECTORY, ST.STATE


def _read_unit(name: str) -> dict[str, list[tuple[str, str]]]:
    sections: dict[str, list[tuple[str, str]]] = {}
    current = None
    for line in (SERVICE / "deploy" / name).read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            current = line.strip("[]")
            sections[current] = []
            continue
        key, _, value = line.partition("=")
        sections[current].append((key, value))
    return sections


def _values(section, key):
    return [value for name, value in section if name == key]


def rotated(harness: X.Harness | None = None) -> tuple[X.Harness, dict]:
    """Genesis at g1, then an authorized, HELD-gated rotation to rot2."""
    h = harness or X.Harness()
    genesis = h.bootstrap()
    authorization = h.issue_head_advance(PB.rot2(), reason=SR.SUCCESSOR_ROTATION, authorization_id="rhaa.pr1s-rot-1")
    held = X.hold(kind=SC.ROTATION, ceremony=PB.C2, predecessor=PB.P0, successor=PB.S2,
                  witness=RC.witness_v2_digest(genesis))
    h.writer.execute_registry_head_advance(authorization=authorization, prior_registry=PB.g1(),
                                           target_registry=PB.rot2(), hold_store=SC.hold_store(held),
                                           context=h.context(), updated_at=h.tick())
    return h, held


# ------------------------------------------------------------- identity ---

class WitnessIdentityTests(unittest.TestCase):
    def test_fixed_identity_matches_accepted_records(self):
        self.assertEqual(PR.WITNESS_KEY_ID, "test-only.witness.dev-synthetic.b1b3d.1")
        self.assertEqual(PR.CREDENTIAL_NAME, "recovery-witness-signing-key")
        self.assertEqual(PR.CREDENTIAL_SOURCE,
                         "/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred")
        self.assertEqual((PR.SERVICE_USER, PR.SERVICE_UNIT), ("lilith-recovery-witness", "lilith-recovery-witness.service"))
        self.assertEqual(PR.STATE_DIR, "/var/lib/lilith-recovery-witness")
        self.assertEqual(PR.ENVIRONMENT, "dev")
        self.assertFalse(PR.CREDENTIAL_SOURCE.startswith("/etc/credstore.encrypted"))  # RR-36
        from lilith_memory.owner_proof import _id
        _id(PR.WITNESS_KEY_ID, "witness_key_id")  # the B1a identifier validator accepts the spelling

    def test_k_wit_can_never_alias_k_act(self):
        import dataclasses
        base = B.DEV_SYNTHETIC_WITNESS_PROFILE
        cases = {
            "WITNESS_KEY_ID_IS_AUTHORITY_KEY_ID": dict(witness_key_id=SC.INITIAL_KEY_ID),
            "WITNESS_CREDENTIAL_NAME_IS_AUTHORITY_NAME": dict(credential_name=SC.CREDENTIAL_NAME),
            "WITNESS_CREDENTIAL_IN_AUTHORITY_CUSTODY": dict(credential_path=SC.CURRENT_PATH),
            "WITNESS_ACCOUNT_IS_AUTHORITY_ACCOUNT": dict(service_user="lilith-authority-dev"),
            "WITNESS_STATE_IN_AUTHORITY_STATE": dict(state_dir="/var/lib/lilith-authority-dev"),
            "WITNESS_PROFILE_PROD": dict(environment="prod"),
            "WITNESS_KEY_ID_NOT_TEST_ONLY": dict(witness_key_id="witness.dev-synthetic.1"),
        }
        for reason, change in cases.items():
            with self.subTest(reason=reason):
                self.assertEqual(B.witness_profile_reason(dataclasses.replace(base, **change)), reason)
        self.assertEqual(B.witness_profile_reason(dataclasses.replace(
            base, credential_path="/etc/credstore.encrypted/lilith-recovery-witness.witness.cred")),
            "WITNESS_CREDENTIAL_IN_AUTHORITY_CUSTODY")
        self.assertIsNone(B.witness_profile_reason(base))
        with self.assertRaises(W.WitnessRefusal) as caught:
            W.DevSyntheticWitnessWriterV1(signing_key=X.key(), storage=PA_FX.SimulatedDurableStorage(),
                                          profile=dataclasses.replace(base, environment="prod"))
        self.assertEqual((caught.exception.reason, caught.exception.detail), ("PROFILE_INVALID", "WITNESS_PROFILE_PROD"))
        with self.assertRaises(W.WitnessRefusal):
            W.DevSyntheticWitnessWriterV1(signing_key=CRED.WitnessSigningKeyV1(F.private("witness"),
                                                                               witness_key_id="test-only.witness.x"),
                                          storage=PA_FX.SimulatedDurableStorage(), profile=X.PROFILE)

    def test_witness_publication_is_a_distinct_type_and_identical_keys_fail(self):
        publication = B.witness_publication(F.raw_public("witness"), b"TEST_ONLY c", PB.MACHINE_ID,
                                            profile=X.PROFILE)
        self.assertEqual(publication["publicationType"], "LILITH_WITNESS_KEY_PUBLICATION")
        with self.assertRaises(Exception):
            RC.KeyPublicationV1.from_dict(publication)  # never parses as a K-ACT publication
        with self.assertRaises(Exception):
            B.WitnessKeyPublicationV1.from_dict(PB.publication(PB.P0))
        anchor = B.witness_anchor_document(B.WitnessKeyPublicationV1.from_dict(publication))
        ok = dict(witness_publication=publication, actor_publication=PB.publication(PB.P0), registry=PB.g1(),
                  registry_root=F.root(), anchor=anchor, profile=X.PROFILE)
        self.assertIsNone(B.witness_distinctness_reason(**ok))
        same_key = B.witness_publication(PB.raw_public(PB.P0), b"TEST_ONLY c", PB.MACHINE_ID, profile=X.PROFILE)
        self.assertEqual(B.witness_distinctness_reason(**{**ok, "witness_publication": same_key,
                                                          "anchor": B.witness_anchor_document(
                                                              B.WitnessKeyPublicationV1.from_dict(same_key))}),
                         "WITNESS_KEY_EQUALS_ACTOR_KEY")
        other_anchor = {**anchor, "publicKey": F.public_b64("successor")}
        self.assertEqual(B.witness_distinctness_reason(**{**ok, "anchor": other_anchor}), "WITNESS_ANCHOR_MISMATCH")
        same_blob = copy.deepcopy(publication)
        same_blob["custodyEvidence"]["blobSha256"] = PB.BLOB[PB.P0]
        self.assertEqual(B.witness_distinctness_reason(**{**ok, "witness_publication": same_blob}),
                         "WITNESS_BLOB_EQUALS_ACTOR_BLOB")


# ------------------------------------------------------------ credential ---

class CredentialTests(unittest.TestCase):
    def test_absent_and_invalid_credentials_refuse(self):
        with self.assertRaises(CRED.WitnessCredentialError) as caught:
            CRED.load_witness_signing_key(None)
        self.assertEqual(caught.exception.state, CRED.CREDENTIAL_ABSENT)
        with self.assertRaises(CRED.WitnessCredentialError) as caught:
            CRED.load_witness_signing_key("/tmp/other")
        self.assertEqual(caught.exception.state, CRED.CREDENTIAL_INVALID)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(CRED.WitnessCredentialError) as caught:
                CRED.load_witness_signing_key(directory, expected_directory=directory)
            self.assertEqual(caught.exception.state, CRED.CREDENTIAL_ABSENT)
            (Path(directory) / PR.CREDENTIAL_NAME).write_bytes(b"not a key")
            with self.assertRaises(CRED.WitnessCredentialError) as caught:
                CRED.load_witness_signing_key(directory, expected_directory=directory)
            self.assertEqual(caught.exception.state, CRED.CREDENTIAL_INVALID)

    def test_the_one_signer_signs_only_recovery_witness_v2_bodies(self):
        from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
        with tempfile.TemporaryDirectory() as directory:
            der = F.private("witness").private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
            (Path(directory) / PR.CREDENTIAL_NAME).write_bytes(der)
            signer = CRED.load_witness_signing_key(directory, expected_directory=directory)
        self.assertEqual(signer.public_key(), F.raw_public("witness"))
        public = [name for name in dir(signer) if not name.startswith("_")]
        self.assertEqual(sorted(public), ["public_key", "public_key_sha256", "sign_recovery_witness_v2",
                                          "witness_key_id"])
        for leak in (pickle.dumps, copy.copy, copy.deepcopy):
            with self.assertRaises(TypeError):
                leak(signer)
        h = X.Harness()
        unsigned = dict(h.candidate().unsigned)
        signed = signer.sign_recovery_witness_v2(unsigned)
        self.assertEqual(RC.witness_v2_digest(signed), h.candidate().digest)  # signature is not in the digest
        for body in (PB.publication(PB.P0), PB.g1(), {**unsigned, "witnessKeyId": "test-only.witness.other"},
                     {**unsigned, "schemaVersion": 1}, {k: v for k, v in unsigned.items() if k != "ledgerHead"},
                     F.epoch_authorization_unsigned(RC.RecoveryWitnessV2.from_verified_dict(signed), F.v5())):
            with self.assertRaises(ValueError):
                signer.sign_recovery_witness_v2(body)


# ---------------------------------------------- genesis: pin before commit ---

class GenesisTests(unittest.TestCase):
    def test_candidate_digest_is_deterministic_and_binds_every_unsigned_field(self):
        h = X.Harness()
        first, second = h.candidate(), h.candidate()
        self.assertTrue(first.built)
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(first.unsigned["ledgerSequence"], 1)
        self.assertEqual(first.unsigned["ledgerHead"], J.initial_position(PB.g1())[1])
        self.assertEqual(first.unsigned["witnessKeyId"], B.WITNESS_KEY_ID)
        self.assertNotEqual(h.candidate(updated_at="2026-09-26T07:00:01Z").digest, first.digest)
        for field in sorted(first.unsigned):
            if field in ("previousWitnessDigest", "consumedAuthorizationId"):
                continue
            changed = dict(first.unsigned)
            changed[field] = {"environment": "dev", "witnessVersion": 2}.get(field, changed[field])
            if changed == dict(first.unsigned):
                continue
            self.assertNotEqual(B.candidate_digest(changed), first.digest, field)

    def test_pin_mismatch_blocks_signing_and_commit(self):
        h = X.Harness()
        h.pin = WR.OwnerGenesisPinV1(X.ENV, "0" * 64).to_dict()
        with self.assertRaises(W.WitnessRefusal) as caught:
            h.bootstrap()
        self.assertEqual((caught.exception.reason, caught.exception.detail),
                         ("GENESIS_PIN_MISMATCH", "GENESIS_PIN_CANDIDATE_MISMATCH"))
        self.assertEqual(h.storage.names(STATE), [])  # nothing created, nothing signed
        h.pin = None
        with self.assertRaises(W.WitnessRefusal) as caught:
            h.writer.bootstrap(registry=h.registry, ledger_observation=h.ledger, context=h.context(), updated_at=X.T0)
        self.assertEqual(caught.exception.detail, "GENESIS_PIN_MISSING")

    def test_committed_genesis_equals_the_pin_and_a_second_genesis_is_refused(self):
        h = X.Harness()
        genesis = h.bootstrap()
        self.assertEqual(RC.witness_v2_digest(genesis), h.pin["genesisWitnessDigest"])
        scan = h.scan()
        self.assertEqual((scan.classification, scan.genesis.digest), (WR.CONSISTENT, h.pin["genesisWitnessDigest"]))
        with self.assertRaises(W.WitnessRefusal) as caught:
            h.bootstrap()
        self.assertEqual((caught.exception.reason, caught.exception.detail),
                         ("STORE_NOT_UNINITIALIZED", WR.CONSISTENT))

    def test_ledger_coherence_is_required(self):
        h = X.Harness()
        h.pin_candidate()
        cases = {
            "GENESIS_LEDGER_ABSENT": None,
            "GENESIS_LEDGER_NOT_INITIAL": RC.AuthorityLedgerObservationV1(
                X.ENV, h.ledger.recovery_epoch, 2, h.ledger.head, 1, h.ledger.signing_key_ids),
            "GENESIS_LEDGER_HEAD_MISMATCH": RC.AuthorityLedgerObservationV1(
                X.ENV, h.ledger.recovery_epoch, 1, "f" * 64, 1, h.ledger.signing_key_ids),
            "GENESIS_LEDGER_INCONSISTENT": RC.AuthorityLedgerObservationV1(
                X.ENV, h.ledger.recovery_epoch, 1, h.ledger.head, 1, h.ledger.signing_key_ids, rows_consistent=False),
            "GENESIS_LEDGER_REGISTRY_MISMATCH": RC.AuthorityLedgerObservationV1(
                X.ENV, h.ledger.recovery_epoch, 1, h.ledger.head, 2, h.ledger.signing_key_ids),
        }
        for reason, observation in cases.items():
            with self.subTest(reason=reason):
                with self.assertRaises(W.WitnessRefusal) as caught:
                    h.writer.bootstrap(registry=h.registry, ledger_observation=observation, context=h.context(),
                                       updated_at=X.T0)
                self.assertEqual((caught.exception.reason, caught.exception.detail),
                                 ("GENESIS_CANDIDATE_REFUSED", reason))
                self.assertEqual(h.storage.names(STATE), [])

    def test_a_ledger_that_moved_makes_the_pin_stale(self):
        h = X.Harness()
        h.pin_candidate()
        h.ledger_log.append({"op": J.REGISTRY_VIEW, "registryVersion": 2, "signingKeyIds": [PB.P0],
                             "policyVersion": PB.POLICY})
        with self.assertRaises(W.WitnessRefusal) as caught:
            h.bootstrap()
        self.assertEqual(caught.exception.detail, "GENESIS_LEDGER_NOT_INITIAL")

    def test_interrupted_bootstrap_stays_uninitialized_and_retries_the_same_candidate(self):
        for point in ("BEFORE_CHAIN_CREATE", "AFTER_CHAIN_WRITE", "AFTER_CHAIN_FILE_FSYNC"):
            with self.subTest(point=point):
                h = X.Harness()
                h.fault = PA_FX.fault_at(point)
                with self.assertRaises(PA_FX.InjectedFault):
                    h.bootstrap()
                h.storage.crash()
                h.fault = None
                self.assertEqual(h.scan().classification, WR.UNINITIALIZED)
                with self.assertRaises(W.WitnessRefusal):  # never a silently regenerated candidate
                    h.writer.bootstrap(registry=h.registry, ledger_observation=h.ledger, context=h.context(),
                                       updated_at="2026-09-26T07:05:00Z")
                genesis = h.bootstrap()  # the same pinned candidate
                self.assertEqual(RC.witness_v2_digest(genesis), h.pin["genesisWitnessDigest"])

    def test_commit_point_crash_rolls_forward_to_the_pinned_genesis(self):
        h = X.Harness()
        h.fault = PA_FX.fault_at("AFTER_CHAIN_DIRECTORY_FSYNC")
        with self.assertRaises(PA_FX.InjectedFault):
            h.bootstrap()
        h.storage.crash()
        h.fault = None
        run = W.recover(h.storage, context=h.context())
        self.assertEqual((run.before.classification, run.actions), (WR.POINTER_MISSING, ("POINTER_ROLLED_FORWARD",)))
        self.assertEqual(run.after.genesis.digest, h.pin["genesisWitnessDigest"])
        self.assertFalse(run.facts["usedWitnessKey"])

    def test_genesis_over_a_registry_naming_the_witness_key_is_refused(self):
        h = X.Harness()
        h.pin_candidate()
        context = h.context(authority_public_keys=frozenset({F.raw_public("witness")}))
        with self.assertRaises(W.WitnessRefusal) as caught:
            h.writer.bootstrap(registry=h.registry, ledger_observation=h.ledger, context=context, updated_at=X.T0)
        self.assertEqual(caught.exception.reason, "GENESIS_REFUSED")


# --------------------------------- durability: same algorithm as Prep A ---

class DurabilityTests(unittest.TestCase):
    def test_identical_bytes_and_operation_order_as_the_accepted_test_writer(self):
        ours = X.Harness()
        theirs_storage = PA_FX.SimulatedDurableStorage()
        theirs = TEST_WS.DurableWitnessV2WriterV1(signing_key=F.private("witness"), witness_key_id=B.WITNESS_KEY_ID,
                                                  environment=X.ENV, storage=theirs_storage)
        ours.pin_candidate()
        ours.bootstrap()
        expectation = PA_FX.genesis_expectation(PB.g1(), ours.ledger)
        theirs.bootstrap(expectation=expectation, registry=PB.g1(), context=ours.context(), updated_at=X.T0)
        self.assertEqual(ours.storage.snapshot(), theirs_storage.snapshot())
        self.assertEqual(ours.storage.log, theirs_storage.log)
        ours.ledger_log.append({"op": J.REGISTRY_VIEW, "registryVersion": 2, "signingKeyIds": [PB.P0],
                                "policyVersion": PB.POLICY})
        ledger = ours.ledger
        ours.writer.record_ledger_advance(previous_witness_digest=ours.head.digest, ledger_sequence=ledger.sequence,
                                          ledger_head=ledger.head, context=ours.context(), updated_at=F.stamp(1))
        theirs.record_ledger_advance(ledger_sequence=ledger.sequence, ledger_head=ledger.head,
                                     context=ours.context(), updated_at=F.stamp(1))
        self.assertEqual(ours.storage.snapshot(), theirs_storage.snapshot())
        self.assertEqual(ours.storage.log, theirs_storage.log)

    def test_commit_order_retention_then_chain_then_pointer(self):
        h = X.Harness()
        h.bootstrap()
        mark = len(h.storage.log)
        authorization = h.issue_head_advance(PB.rot2(), reason=SR.SUCCESSOR_ROTATION, authorization_id="rhaa.x-1")
        held = X.hold(kind=SC.ROTATION, witness=h.head.digest)
        h.writer.execute_registry_head_advance(authorization=authorization, prior_registry=PB.g1(),
                                               target_registry=PB.rot2(), hold_store=SC.hold_store(held),
                                               context=h.context(), updated_at=h.tick())
        log = h.storage.log[mark:]
        retained = WR.retained_authorization_name("rhaa.x-1")

        def at(*item):
            return log.index(item)
        order = [at("create", AUTHS, retained), at("fsync_file", AUTHS, retained), at("fsync_dir", AUTHS),
                 at("create", CHAIN, "2.json"), at("fsync_file", CHAIN, "2.json"), at("fsync_dir", CHAIN),
                 at("write", STATE, WR.POINTER_SCRATCH_NAME), at("fsync_file", STATE, WR.POINTER_SCRATCH_NAME),
                 at("replace", STATE, WR.POINTER_SCRATCH_NAME, WR.POINTER_NAME), at("fsync_dir", STATE)]
        self.assertEqual(order, sorted(order))
        self.assertEqual((log[0], log[-1]), (("lock",), ("unlock",)))

    def test_fault_matrix_every_seam_recovers_forward_or_stays_committed(self):
        for point in W.FAULT_POINTS:
            with self.subTest(point=point):
                h = X.Harness()
                h.bootstrap()
                authorization = h.issue_head_advance(PB.rot2(), reason=SR.SUCCESSOR_ROTATION,
                                                     authorization_id="rhaa.fault-1")
                held = SC.hold_store(X.hold(kind=SC.ROTATION, witness=h.head.digest))
                h.fault = PA_FX.fault_at(point)
                with self.assertRaises(PA_FX.InjectedFault):
                    h.writer.execute_registry_head_advance(authorization=authorization, prior_registry=PB.g1(),
                                                           target_registry=PB.rot2(), hold_store=held,
                                                           context=h.context(), updated_at=h.tick())
                h.storage.crash()
                h.fault = None
                run = W.recover(h.storage, context=h.context())
                committed = W.FAULT_POINTS.index(point) >= W.FAULT_POINTS.index("AFTER_CHAIN_DIRECTORY_FSYNC")
                self.assertEqual(run.after.classification, WR.CONSISTENT, run.after.detail)
                self.assertEqual(run.after.head.witness_version, 2 if committed else 1)
                self.assertEqual(W.recover(h.storage, context=h.context()).actions, ())  # idempotent restart

    def test_recovery_never_rolls_back_and_fails_closed_on_damage(self):
        h, _ = rotated()
        h.ledger_log.append({"op": J.REGISTRY_VIEW, "registryVersion": 2, "signingKeyIds": [PB.S2],
                             "policyVersion": PB.POLICY})
        h.record_ledger()
        h.storage.plant(STATE, WR.POINTER_NAME, h.storage.read(CHAIN, "1.json"))
        scan = h.scan()
        self.assertEqual((scan.classification, scan.decision), (WR.POINTER_BEHIND_MULTI, WR.FAIL_CLOSED))
        for label, damage in (("torn", lambda s: s.storage.plant(CHAIN, "3.json", b"{\"witnessVersion\":3")),
                              ("orphan", lambda s: s.storage.plant(CHAIN, "5.json", s.storage.read(CHAIN, "2.json"))),
                              ("unexpected", lambda s: s.storage.plant(STATE, "stray.json", b"{}")),
                              ("corrupt", lambda s: s.storage.plant(CHAIN, "1.json", b"{}")),
                              ("symlink", lambda s: s.storage.plant(STATE, "link", kind=WR.SYMLINK))):
            with self.subTest(label=label):
                s, _ = rotated()
                damage(s)
                before = s.storage.snapshot()
                scan = s.scan()
                self.assertEqual(scan.decision, WR.FAIL_CLOSED, scan.classification)
                run = W.recover(s.storage, context=s.context())
                self.assertEqual((run.actions, s.storage.snapshot()), ((), before))
                with self.assertRaises(W.WitnessRefusal) as caught:
                    s.writer.record_ledger_advance(previous_witness_digest="0" * 64, ledger_sequence=9,
                                                   ledger_head="0" * 64, context=s.context(), updated_at=s.tick())
                self.assertEqual(caught.exception.reason, "STORE_NOT_CONSISTENT")

    def test_invalid_authorization_history_fails_closed(self):
        h, _ = rotated()
        h.storage.drop(AUTHS, WR.retained_authorization_name("rhaa.pr1s-rot-1"))
        scan = h.scan()
        self.assertEqual(scan.classification, WR.AUTHORIZATION_HISTORY_INVALID)
        h2, _ = rotated()
        h2.issued.clear()  # the owner register no longer names the executed authorization
        self.assertEqual(h2.scan().classification, WR.AUTHORIZATION_HISTORY_INVALID)

    def test_single_writer_lock(self):
        h = X.Harness()
        h.bootstrap()
        with h.storage.lock():
            with self.assertRaises(PA_FX.LockHeld):
                h.record_ledger()

    @unittest.skipUnless(POSIX, "real filesystem semantics are POSIX")
    def test_live_filesystem_port_end_to_end_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o750)
            h = X.Harness(ST.FilesystemWitnessStorageV1(directory))
            rotated(h)
            self.assertEqual(sorted(os.listdir(directory)), ["authorizations", "chain", "witness.json", "witness.lock"])
            self.assertEqual(sorted(os.listdir(Path(directory) / "chain")), ["1.json", "2.json"])
            for name in ("1.json", "2.json"):
                self.assertEqual(os.stat(Path(directory) / "chain" / name).st_mode & 0o777, 0o640)
            self.assertEqual(os.stat(Path(directory) / "chain").st_mode & 0o777, 0o750)
            restarted = X.Harness(ST.FilesystemWitnessStorageV1(directory))
            restarted.pin, restarted.issued, restarted.heads = h.pin, h.issued, h.heads
            self.assertEqual(W.recover(restarted.storage, context=restarted.context()).actions, ())
            self.assertEqual(restarted.scan().head.witness_version, 2)
            with ST.FilesystemWitnessStorageV1(directory).lock():
                with self.assertRaises(ST.StorageLocked):
                    with ST.FilesystemWitnessStorageV1(directory).lock():
                        pass
            with self.assertRaises(ST.StorageRefused):
                h.storage.replace(STATE, WR.POINTER_NAME, "other.json")
            with self.assertRaises(ST.StorageRefused):
                h.storage.remove(CHAIN, "1.json")
            with self.assertRaises(FileExistsError):
                h.storage.create_exclusive(CHAIN, "1.json", b"x")

    @unittest.skipUnless(POSIX, "symlink semantics are POSIX")
    def test_live_port_never_follows_links(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as elsewhere:
            os.symlink(elsewhere, Path(directory) / "chain")
            storage = ST.FilesystemWitnessStorageV1(directory)
            with self.assertRaises(OSError):
                storage.create_exclusive(CHAIN, "1.json", b"x")
            self.assertEqual(os.listdir(elsewhere), [])
            link_state = Path(directory) / "state"
            os.symlink(elsewhere, link_state)
            with self.assertRaises(OSError):
                ST.FilesystemWitnessStorageV1(link_state).make_directory(CHAIN)


# ---------------------------------------- execution ops: shipped but inert ---

class ExecutionInertnessTests(unittest.TestCase):
    def test_head_advance_requires_every_gate(self):
        h = X.Harness()
        genesis = h.bootstrap()
        authorization = h.issue_head_advance(PB.rot2(), reason=SR.SUCCESSOR_ROTATION, authorization_id="rhaa.g-1")
        good = X.hold(kind=SC.ROTATION, witness=RC.witness_v2_digest(genesis))

        def attempt(**overrides):
            value = dict(authorization=authorization, prior_registry=PB.g1(), target_registry=PB.rot2(),
                         hold_store=SC.hold_store(good), context=h.context(), updated_at=h.tick())
            value.update(overrides)
            with self.assertRaises(W.WitnessRefusal) as caught:
                h.writer.execute_registry_head_advance(**value)
            return caught.exception.reason
        self.assertEqual(attempt(hold_store=SC.hold_store()), "HOLD_NOT_HELD_FOR_TRANSITION")
        self.assertEqual(attempt(hold_store=SC.hold_store(X.hold(kind=SC.KEY_COMPROMISE_RECOVERY,
                                                                 witness=RC.witness_v2_digest(genesis)))),
                         "HOLD_NOT_HELD_FOR_TRANSITION")
        self.assertEqual(attempt(hold_store=SC.hold_store(X.hold(kind=SC.ROTATION, predecessor=PB.S3,
                                                                 witness=RC.witness_v2_digest(genesis)))),
                         "HOLD_BINDING_MISMATCH")
        self.assertEqual(attempt(hold_store=SC.hold_store(good, PB.initial_hold(witness=RC.witness_v2_digest(genesis)))),
                         "HOLD_SET_OTHER_HELD")
        self.assertEqual(attempt(authorization={**authorization, "signature": authorization["signature"][:-2] + "AA"}),
                         "AUTHORIZATION_NOT_VERIFIED")
        registered = dict(h.issued)
        h.issued.clear()
        self.assertEqual(attempt(), "AUTHORIZATION_NOT_REGISTERED")
        h.issued.update(registered)
        self.assertEqual(attempt(context=h.context(environment="dev")), "CONTEXT_NOT_THIS_WITNESS")
        self.assertEqual(attempt(context=h.context(anchor=F.anchor("successor", key_id=B.WITNESS_KEY_ID))),
                         "CONTEXT_NOT_THIS_WITNESS")
        self.assertEqual(h.scan().head.witness_version, 1)  # nothing executed
        h.writer.execute_registry_head_advance(authorization=authorization, prior_registry=PB.g1(),
                                               target_registry=PB.rot2(), hold_store=SC.hold_store(good),
                                               context=h.context(), updated_at=h.tick())
        self.assertEqual(h.scan().head.registry_version, 2)
        self.assertEqual(attempt(), "AUTHORIZATION_CONSUMED")  # single use

    def test_c4_epoch_advance_executes_only_with_the_compromise_hold(self):
        h = X.Harness()
        genesis = h.bootstrap()
        kcr = X.hold(kind=SC.KEY_COMPROMISE_RECOVERY, witness=RC.witness_v2_digest(genesis))
        marking = h.issue_head_advance(PB.mark2(), reason=SR.COMPROMISE_MARKING, authorization_id="rhaa.mark-1")
        h.writer.execute_registry_head_advance(authorization=marking, prior_registry=PB.g1(),
                                               target_registry=PB.mark2(), hold_store=SC.hold_store(kcr),
                                               context=h.context(), updated_at=h.tick())
        eaa = h.issue_epoch_advance(PB.rec3())
        adoption = J.epoch_adoption_op(tuple(h.ledger_log), authorization=eaa, witness=h.head,
                                       target_registry=PB.rec3(), registry_root=F.root())
        h.ledger_log.append(adoption)

        def run(**overrides):
            ledger = h.ledger
            value = dict(authorization=eaa, prior_registry=PB.mark2(), target_registry=PB.rec3(),
                         adoption_record=adoption, ledger_sequence=ledger.sequence, ledger_head=ledger.head,
                         hold_store=SC.hold_store(kcr), context=h.context(), updated_at=h.tick())
            value.update(overrides)
            return h.writer.execute_epoch_advance(**value)
        for overrides, reason in ((dict(hold_store=SC.hold_store()), "HOLD_NOT_HELD_FOR_TRANSITION"),
                                  (dict(hold_store=SC.hold_store(X.hold(kind=SC.ROTATION,
                                                                        witness=RC.witness_v2_digest(genesis)))),
                                   "HOLD_NOT_HELD_FOR_TRANSITION"),
                                  (dict(adoption_record={**adoption, "authorizationId": "eaa.other"}), "PLAN_REFUSED")):
            with self.subTest(reason=reason):
                with self.assertRaises(W.WitnessRefusal) as caught:
                    run(**overrides)
                self.assertEqual(caught.exception.reason, reason)
        signed = run()
        self.assertEqual(signed["currentRecoveryEpoch"], PB.EN.to_dict())

    def test_epoch_advance_reason_other_than_key_compromise_is_refused(self):
        h = X.Harness()
        genesis = h.bootstrap()
        kcr = X.hold(kind=SC.KEY_COMPROMISE_RECOVERY, witness=RC.witness_v2_digest(genesis))
        eaa = h.issue_epoch_advance(PB.rec3(), reason="OPERATOR_RECOVERY", authorization_id="eaa.op-1")
        with self.assertRaises(W.WitnessRefusal) as caught:
            h.writer.execute_epoch_advance(authorization=eaa, prior_registry=PB.g1(), target_registry=PB.rec3(),
                                           adoption_record={}, ledger_sequence=2, ledger_head="a" * 64,
                                           hold_store=SC.hold_store(kcr), context=h.context(), updated_at=h.tick())
        self.assertEqual(caught.exception.reason, "EPOCH_ADVANCE_REASON_UNSUPPORTED")


# -------------------------------------------------- protocol / core / server ---

class ProtocolTests(unittest.TestCase):
    def frame(self, operation, payload, **overrides):
        value = {"protocol": WP.PROTOCOL, "schemaVersion": WP.VERSION, "operation": operation, "payload": payload}
        value.update(overrides)
        raw = rfc8785.dumps(value)
        return struct.pack(">I", len(raw)) + raw

    def test_closed_operation_sets_per_socket(self):
        self.assertEqual(WP.ROLE_OPERATIONS[WP.OWNER], frozenset({"HEALTH", "READ_WITNESS", "BOOTSTRAP",
                                                                  "EXECUTE_REGISTRY_HEAD_ADVANCE",
                                                                  "EXECUTE_EPOCH_ADVANCE"}))
        self.assertEqual(WP.ROLE_OPERATIONS[WP.SIGNER], frozenset({"READ_WITNESS", "RECORD_LEDGER_ADVANCE"}))
        for operation in ("SIGN", "SIGN_BYTES", "SIGN_WITNESS", "SIGN_OWNER_EVIDENCE", "SIGN_REGISTRY", "ISSUE",
                          "RAISE_REGISTRY_FLOOR", "ADVANCE_EPOCH", "EXPORT_KEY", "GENERIC"):
            for role in (WP.OWNER, WP.SIGNER):
                with self.assertRaises(WP.ProtocolError) as caught:
                    WP.parse_frame(self.frame(operation, {}), role=role)
                self.assertEqual(caught.exception.code, "UNSUPPORTED_OPERATION")
        with self.assertRaises(WP.ProtocolError) as caught:
            WP.parse_frame(self.frame(WP.BOOTSTRAP, {"registryVersion": 1, "ledgerObservation": {},
                                                     "updatedAt": X.T0}), role=WP.SIGNER)
        self.assertEqual(caught.exception.code, "OPERATION_NOT_ON_THIS_SOCKET")

    def test_no_operation_accepts_a_witness_body_or_digest_to_sign(self):
        for operation, fields in WP.PAYLOAD_FIELDS.items():
            self.assertFalse({"witness", "unsigned", "signature", "digest", "body", "key"} & fields, operation)
        with self.assertRaises(WP.ProtocolError):
            WP.parse_frame(self.frame(WP.RECORD_LEDGER_ADVANCE, {"previousWitnessDigest": "0" * 64,
                                                                 "ledgerSequence": 2, "ledgerHead": "0" * 64,
                                                                 "witness": {}}), role=WP.SIGNER)

    def test_canonical_bounded_frames_only(self):
        raw = rfc8785.dumps({"protocol": WP.PROTOCOL, "schemaVersion": 1, "operation": "HEALTH", "payload": {}})
        spaced = raw.replace(b":", b": ")
        with self.assertRaises(WP.ProtocolError) as caught:
            WP.parse_frame(struct.pack(">I", len(spaced)) + spaced, role=WP.OWNER)
        self.assertEqual(caught.exception.code, "NONCANONICAL_JSON")
        with self.assertRaises(WP.ProtocolError):
            WP.parse_frame(struct.pack(">I", WP.MAX_FRAME_BYTES + 1) + b"x", role=WP.OWNER)
        self.assertEqual(WP.parse_frame(WP.encode_frame(WP.HEALTH, {}), role=WP.OWNER).operation, WP.HEALTH)


class CoreTests(unittest.TestCase):
    def host(self, directory: str) -> tuple[X.Harness, CORE.RecoveryWitnessCoreV1]:
        h = X.Harness(ST.FilesystemWitnessStorageV1(directory)) if POSIX else X.Harness()
        h.pin_candidate()

        def inputs():
            return HI.HostInputsV1(environment=X.ENV, registry_root=F.root(), witness_anchor=X.anchor(),
                                   registries=tuple(h.registries), genesis_pin=h.pin, owner_register=h.register())
        core = CORE.RecoveryWitnessCoreV1(writer=h.writer, storage=h.storage, inputs=inputs, clock=h.tick)
        return h, core

    def test_health_and_read_never_mutate(self):
        with tempfile.TemporaryDirectory() as directory:
            h, core = self.host(directory)
            before = h.storage.listing(STATE)
            for role in (WP.OWNER, WP.SIGNER):
                for operation in WP.ROLE_OPERATIONS[role] & {WP.HEALTH, WP.READ_WITNESS}:
                    core.dispatch(role, WP.WitnessMessageV1(operation, {}))
            self.assertEqual(h.storage.listing(STATE), before)  # no entry created, not even the lock
            health = core.dispatch(WP.OWNER, WP.WitnessMessageV1(WP.HEALTH, {}))["health"]
            self.assertEqual((health["genericSigning"], health["authorityGranted"]), ("NOT_AVAILABLE", False))
            self.assertEqual(health["classification"], WR.UNINITIALIZED)

    def test_bootstrap_ledger_advance_and_refusals_over_the_protocol(self):
        with tempfile.TemporaryDirectory() as directory:
            h, core = self.host(directory)
            from lilith_recovery_witness.core import ledger_observation_document
            observation = ledger_observation_document(h.ledger)
            reply = core.dispatch(WP.OWNER, WP.WitnessMessageV1(WP.BOOTSTRAP, {
                "registryVersion": 1, "ledgerObservation": observation, "updatedAt": X.T0}))
            self.assertEqual(reply["status"], "OK", reply)
            self.assertEqual(reply["genesisDigest"], h.pin["genesisWitnessDigest"])
            again = core.dispatch(WP.OWNER, WP.WitnessMessageV1(WP.BOOTSTRAP, {
                "registryVersion": 1, "ledgerObservation": observation, "updatedAt": X.T0}))
            self.assertEqual((again["status"], again["reason"]), ("REFUSED", "STORE_NOT_UNINITIALIZED"))
            read = core.dispatch(WP.SIGNER, WP.WitnessMessageV1(WP.READ_WITNESS, {}))
            self.assertEqual(read["witness"]["witnessVersion"], 1)
            refused = core.dispatch(WP.SIGNER, WP.WitnessMessageV1(WP.RECORD_LEDGER_ADVANCE, {
                "previousWitnessDigest": read["witness"] and RC.witness_v2_digest(read["witness"]),
                "ledgerSequence": 1, "ledgerHead": h.ledger.head}))
            self.assertEqual((refused["status"], refused["reason"]), ("REFUSED", "PLAN_REFUSED"))
            snapshot = PA.hold_snapshot_document(SC.hold_store(), environment=X.ENV)
            head_advance = core.dispatch(WP.OWNER, WP.WitnessMessageV1(WP.EXECUTE_REGISTRY_HEAD_ADVANCE, {
                "authorization": {"x": 1}, "targetRegistryVersion": 2, "holdStore": snapshot}))
            self.assertEqual(head_advance["status"], "REFUSED")
            wrong_socket = core.dispatch(WP.SIGNER, WP.WitnessMessageV1(WP.BOOTSTRAP, {}))
            self.assertEqual(wrong_socket["reason"], "UNSUPPORTED_OPERATION")

    def test_subset_or_forged_hold_snapshot_is_refused(self):
        held = X.hold(kind=SC.ROTATION, witness="a" * 64)
        full = PA.hold_snapshot_document(SC.hold_store(held, PB.initial_hold(witness="b" * 64)), environment=X.ENV)
        observation, reason, _ = PA.parse_hold_snapshot(full, environment=X.ENV)
        self.assertIsNotNone(observation)
        subset = dict(full, entries=full["entries"][:1])
        self.assertEqual(PA.parse_hold_snapshot(subset, environment=X.ENV)[1], "HOLD_SNAPSHOT_DIGEST_MISMATCH")
        self.assertEqual(PA.parse_hold_snapshot(held, environment=X.ENV)[1], "HOLD_SNAPSHOT_MALFORMED")
        self.assertEqual(PA.parse_hold_snapshot(dict(full, environment="dev"), environment=X.ENV)[1],
                         "HOLD_SNAPSHOT_ENVIRONMENT_MISMATCH")
        self.assertEqual(PA.parse_hold_snapshot(dict(full, entries=list(reversed(full["entries"]))),
                                                environment=X.ENV)[1], "HOLD_SNAPSHOT_NOT_SORTED")


class ServerTests(unittest.TestCase):
    @unittest.skipUnless(POSIX and hasattr(socket, "AF_UNIX"), "AF_UNIX")
    def test_each_socket_serves_only_its_peer(self):
        class Core:
            def dispatch(self, role, message):
                return {"status": "OK", "role": role, "operation": message.operation}
        cases = ((WP.OWNER, 0, 0, True), (WP.OWNER, 990, 0, False), (WP.SIGNER, 990, 990, True),
                 (WP.SIGNER, 0, 990, False), (WP.SIGNER, 1001, 990, False))
        for role, peer, authorized, served in cases:
            with self.subTest(role=role, peer=peer):
                left, right = socket.socketpair()
                frame = WP.encode_frame(WP.READ_WITNESS, {})
                left.sendall(frame)
                S.serve_connection(right, Core(), role=role, authorized_uid=authorized,
                                   peer_uid_reader=lambda _conn, uid=peer: uid)
                left.settimeout(2)
                try:
                    reply = left.recv(WP.MAX_FRAME_BYTES + 8)
                except ConnectionResetError:
                    reply = b""  # closed without reading the refused request: nothing was served
                left.close()
                self.assertEqual(bool(reply), served)
                if served:
                    self.assertEqual(WP.parse_response(reply)["role"], role)

    def test_startup_identity_and_environment_are_fixed(self):
        users = {"lilith-recovery-witness": (980, 975), "lilith-authority-dev": (990, 980), "lilith": (1001, 1002),
                 "lilith-memory-broker": (999, 987)}
        groups = {"lilith-recovery-witness": 975}

        def check(uid, gid, extra=(), users=users):
            return S.check_identity(uid, gid, [gid, *extra], user_lookup=users.get, group_lookup=groups.get)
        self.assertEqual(check(980, 975), 990)
        for args in ((0, 0), (990, 980), (980, 975, (980,)), (981, 975)):
            with self.assertRaises(S.ServerError):
                check(*args)
        with self.assertRaises(S.ServerError):
            check(980, 975, users={**users, "lilith-authority-dev": (980, 975)})
        with self.assertRaises(S.ServerError):
            check(980, 975, users={**users, "lilith-authority-dev": (990, 975)})
        for environ in ({}, {"LILITH_ENV": "prod"}, {"LILITH_ENV": "dev", "PYTHONPATH": "/x"},
                        {"LILITH_ENV": "dev", "LILITH_WITNESS_KEY": "x"}):
            with self.assertRaises(S.ServerError):
                S.check_environment(environ)
        S.check_environment({"LILITH_ENV": "dev"})

    def test_startup_recovery_never_bootstraps(self):
        h = X.Harness()
        inputs = HI.HostInputsV1(environment=X.ENV, registry_root=F.root(), witness_anchor=X.anchor(),
                                 registries=(PB.g1(),), genesis_pin=None, owner_register=None)
        run = S.startup_recovery(None, h.storage, inputs)
        self.assertEqual((run.before.classification, run.actions), (WR.UNINITIALIZED, ()))
        self.assertEqual(h.storage.names(STATE), [])
        self.assertIsNone(S.startup_recovery(None, h.storage, HI.HostInputsV1(environment=X.ENV)))

    def test_server_source_has_no_bind_or_generic_signing(self):
        for name in ("server.py", "core.py", "writer.py", "storage.py", "protocol.py"):
            text = (SERVICE / "lilith_recovery_witness" / name).read_text(encoding="utf-8")
            for needle in (".bind(", "AF_INET", "listen(", "sign_bytes", "sign_digest", "evidence_minter",
                           "lilith_authority_signer", "synthetic_", "Ed25519PrivateKey.generate",
                           "authority_ledger.db"):
                self.assertNotIn(needle, text, f"{name}: {needle}")
        credential = (SERVICE / "lilith_recovery_witness/credential.py").read_text(encoding="utf-8")
        self.assertEqual(credential.count(".sign("), 1)
        self.assertIn("RC.witness_v2_signing_bytes", credential)


# ----------------------------------------------------------------- units ---

class UnitTests(unittest.TestCase):
    service = _read_unit("lilith-recovery-witness.service")

    def one(self, key):
        values = _values(self.service["Service"], key)
        self.assertEqual(len(values), 1, key)
        return values[0]

    def test_dedicated_identity_and_one_k_wit_credential(self):
        self.assertEqual((self.one("User"), self.one("Group")), ("lilith-recovery-witness", "lilith-recovery-witness"))
        self.assertEqual(self.one("LoadCredentialEncrypted"), f"{PR.CREDENTIAL_NAME}:{PR.CREDENTIAL_SOURCE}")
        for key in ("LoadCredential", "SetCredential", "SetCredentialEncrypted", "ImportCredential",
                    "SupplementaryGroups", "DynamicUser", "StateDirectory", "EnvironmentFile", "PassEnvironment",
                    "BindPaths", "BindReadOnlyPaths", "ExecStartPre"):
            self.assertEqual(_values(self.service["Service"], key), [], key)
        self.assertEqual(self.one("ExecStart"),
                         "/opt/lilith-authority-dev/current/venv/bin/python -B -m lilith_recovery_witness.server")

    def test_least_reach(self):
        denied = self.one("InaccessiblePaths").split()
        for path in ("/etc/lilith-recovery-witness", "/etc/credstore.encrypted", "/etc/lilith-authority-custody",
                     "/var/lib/lilith-authority-custody", "-/var/lib/lilith-authority-dev", "/etc/lilith-memory-broker",
                     "/var/lib/lilith-memory-broker", "/etc/lilith-os-dev"):
            self.assertIn(path, denied)
        self.assertEqual(self.one("ReadWritePaths"), "/var/lib/lilith-recovery-witness")
        self.assertEqual(self.one("ReadOnlyPaths").split(), ["/opt/lilith-authority-dev", "/etc/lilith-authority-dev"])
        for key, value in {"NoNewPrivileges": "yes", "ProtectSystem": "strict", "PrivateNetwork": "yes",
                           "RestrictAddressFamilies": "AF_UNIX", "IPAddressDeny": "any", "CapabilityBoundingSet": "",
                           "UMask": "0027"}.items():
            self.assertEqual(self.one(key), value, key)

    def test_sockets_and_never_enabled(self):
        owner = _read_unit("lilith-recovery-witness-owner.socket")["Socket"]
        signer = _read_unit("lilith-recovery-witness-signer.socket")["Socket"]
        self.assertEqual((_values(owner, "ListenStream"), _values(owner, "SocketUser"), _values(owner, "SocketMode"),
                          _values(owner, "FileDescriptorName")),
                         ([PR.OWNER_SOCKET_PATH], ["root"], ["0600"], ["owner"]))
        self.assertEqual((_values(signer, "ListenStream"), _values(signer, "SocketGroup"), _values(signer, "SocketMode"),
                          _values(signer, "FileDescriptorName")),
                         ([PR.SIGNER_SOCKET_PATH], ["lilith-authority-dev"], ["0660"], ["signer"]))
        for name in ("lilith-recovery-witness.service", "lilith-recovery-witness-owner.socket",
                     "lilith-recovery-witness-signer.socket"):
            text = (SERVICE / "deploy" / name).read_text(encoding="utf-8")
            self.assertNotIn("[Install]", text)
            for key in ("WantedBy", "RequiredBy", "UpheldBy", "Alias", "Also"):
                self.assertNotRegex(text, rf"(?m)^{key}=")
        self.assertEqual((SERVICE / "deploy/lilith-recovery-witness.tmpfiles.conf").read_text(encoding="utf-8"),
                         "d /run/lilith-recovery-witness 0710 root lilith-authority-dev -\n")

    def test_paths_are_the_shared_host_paths(self):
        self.assertEqual(PR.CREDENTIAL_SOURCE, HP.WITNESS_BLOB)
        self.assertEqual((PR.STATE_DIR, PR.OWNER_SOCKET_PATH, PR.SIGNER_SOCKET_PATH),
                         (HP.WITNESS_STATE, HP.WITNESS_OWNER_SOCKET, HP.WITNESS_SIGNER_SOCKET))
        needrestart = (ROOT / "services/memory-broker/deploy/needrestart-lilith-authority-sensitive.conf").read_text(
            encoding="utf-8")
        self.assertIn("qr(^lilith-recovery-witness\.service$)} = 0", needrestart)


# ----------------------------------------------------------- release set ---

class ReleaseFileSetTests(unittest.TestCase):
    def test_own_manifest_identity_is_deterministic_and_clean(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("wrfs", SERVICE / "witness_release_file_set.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.check_source_tree(ROOT)
        first, second = module.runtime_manifest(ROOT), module.runtime_manifest(ROOT)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "SOURCE_PREPARED_NOT_INSTALLED")
        self.assertTrue(set(first["files"]) <= {f"lilith_recovery_witness/{n}" for n in module.RUNTIME_MODULES}
                        | {f"assets/{n}" for n in module.DEPLOY_ASSETS})
        with tempfile.TemporaryDirectory() as directory:
            for relative in module.SOURCE_FILES:
                target = Path(directory) / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / relative).read_bytes())
            core = Path(directory) / module.RUNTIME_PACKAGE / "core.py"
            core.write_bytes(core.read_bytes() + b"\n# import lilith_authority_signer\n")
            with self.assertRaises(module.FileSetError):
                module.runtime_payloads(Path(directory))


if __name__ == "__main__":
    unittest.main()
