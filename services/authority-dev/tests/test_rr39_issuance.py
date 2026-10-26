"""RR-39: governed DEV_SYNTHETIC OwnerEvidenceV2 issuance through the real signer core (TEST_ONLY, POSIX).

A synthetic DEV host under a temporary root, built only through the live-capable components (`pr1s_fixtures`):
pinned K-ROOT and witness anchors (environment `dev`), K-ROOT registry v1 publishing the DEV K-ACT
`test-only.dev-synthetic.actor.b1b3d.1`, the durable authority ledger, the filesystem witness store and writer, the
owner genesis pin and register copies, and a RELEASED INITIAL_CUSTODY hold. The K-ACT key and every other key are
the existing TEST_ONLY fixture seeds; the owner is the fixed DEV_SYNTHETIC synthetic WebAuthn identity. Nothing here
reads a live credential, contacts DEV, or signs with real material.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pr1s_fixtures as X
import synthetic_authority as SA
import synthetic_b1b3e as F
import synthetic_b1b3e_prep_b as PB
import synthetic_chain as SCH
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from lilith_authority_dev import core as CORE
from lilith_authority_dev import credential as CRED
from lilith_authority_dev import issuance as ISS
from lilith_authority_dev import protocol as W
from lilith_authority_dev import state as STATE
from lilith_authority_dev.ledger import DurableAuthorityLedgerV1
from lilith_authority_dev.profile import DevSyntheticSignerProfileV1
from lilith_authority_host import inputs as HI
from lilith_authority_host import paths as P
from lilith_authority_root.hold_store import HoldStoreV1
from lilith_memory import canonical_contracts as C
from lilith_memory import owner_proof as OP
from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import authority_verifier as AV
from lilith_owner_memory import contracts as K
from lilith_owner_memory import pr1_acceptance as PA
from lilith_owner_memory import pr1_bootstrap as B
from lilith_owner_memory import successor_custody as SC
from lilith_owner_memory import witness_readiness as WR

DEV = "dev"
POSIX = X.POSIX
K_ACT = PB.P0                                      # test-only.dev-synthetic.actor.b1b3d.1
DEV_ROOT = SA.trusted_root("dev-root", SA.DEV_ROOT_KEY_ID, DEV)
AUTHORITY_DOMAIN = SCH.AUTHORITY_DOMAIN
LOGICAL_OWNER = SCH.LOGICAL_OWNER
NOW = datetime(2026, 9, 27, 12, 0, 30, tzinfo=timezone.utc)
ISSUED_AT = "2026-09-27T12:00:00Z"
EXPIRES_AT = "2026-09-27T12:01:00Z"
PROFILE = DevSyntheticSignerProfileV1(environment=DEV, key_id=K_ACT, authority_domain=AUTHORITY_DOMAIN,
                                      logical_owner_id=LOGICAL_OWNER, policy_version=PB.POLICY)
OWNER_PROOF = ISS.OwnerProofSettingsV1(owner_principal=SCH.OWNER_PRINCIPAL, rp_id=SCH.RP, origin=SCH.ORIGIN,
                                       registry_tuple_version=SCH.REGISTRY_VERSION,
                                       privacy_notice_version=SCH.PRIVACY_NOTICE,
                                       broker_releases=frozenset({SCH.BROKER_RELEASE}))


def dev_registry() -> dict:
    """K-ROOT registry v1 for DEV: the initial K-ACT as the single current OWNER_ACTOR key."""
    return SA.registry("dev-root", keys=[PB.key(K_ACT, version=1, environment=DEV)], registryVersion=1,
                       recoveryEpoch=PB.EG.to_dict(), policyVersion=PB.POLICY, issuedAt="2026-09-26T06:00:00Z",
                       environment=DEV, registryRootKeyId=SA.DEV_ROOT_KEY_ID)


class DevHost(X.Pr1Host):
    """`Pr1Host` in the DEV environment (the fixture's own steps, DEV anchors/profiles)."""

    def __init__(self, directory, *, registry=None):
        super().__init__(directory, registry=registry or dev_registry())
        self.holds = HoldStoreV1(environment=DEV, root=self.root, owner_uid=X.UID, owner_gid=X.GID)

    def install_public(self):
        self.document(P.REGISTRY_ROOT_ANCHOR, {"schemaVersion": 1, "rootKeyId": SA.DEV_ROOT_KEY_ID,
                                               "environment": DEV, "algorithm": "Ed25519",
                                               "publicKey": SA.public_b64("dev-root")})
        self.document(P.WITNESS_ANCHOR, {"schemaVersion": 1, "witnessKeyId": B.WITNESS_KEY_ID, "environment": DEV,
                                         "algorithm": "Ed25519", "publicKey": F.public_b64("witness")})
        self.document(f"{P.REGISTRY_DIR}/{HI.registry_file_name(self.registry['registryVersion'])}", self.registry)
        return self

    def provision_ledger(self):
        from lilith_owner_memory import authority_ledger_journal as J
        return DurableAuthorityLedgerV1.provision(self.path(P.AUTHORITY_LEDGER), environment=DEV,
                                                  genesis=J.genesis_op(self.registry), expected_uid=X.UID)

    def ledger(self):
        return DurableAuthorityLedgerV1.open_existing(self.path(P.AUTHORITY_LEDGER), environment=DEV,
                                                      expected_uid=X.UID)

    def candidate(self, updated_at=X.T_GENESIS):
        return B.build_genesis_candidate(registry=self.registry, registry_root=DEV_ROOT,
                                         ledger_observation=self.ledger_observation(), updated_at=updated_at,
                                         profile=B.witness_profile(DEV))

    def install_owner_inputs(self, pin_digest):
        from lilith_owner_memory import rotation_contracts as RC
        self.document(P.GENESIS_PIN_COPY, WR.OwnerGenesisPinV1(DEV, pin_digest).to_dict())
        self.document(P.AUTHORIZATION_REGISTER_COPY, {
            "registerType": WR.REGISTER_TYPE, "schemaVersion": WR.REGISTER_SCHEMA_VERSION, "environment": DEV,
            "authorizations": [], "headRegistries": [RC.registry_head(self.registry).to_dict()]})
        return self

    def inputs(self):
        return HI.read_host_inputs(environment=DEV, root=self.root, owner_uid=X.UID)

    def writer(self, **overrides):
        value = dict(signing_key=X.signing_key(), storage=self.storage, profile=B.witness_profile(DEV))
        value.update(overrides)
        from lilith_recovery_witness.writer import DevSyntheticWitnessWriterV1
        return DevSyntheticWitnessWriterV1(**value)

    def head_digest(self) -> str:
        scan = WR.classify_witness_store(observation=self.witness_store(), context=self.context())
        return scan.head.digest

    def released_snapshot(self, *, state: str = SC.RELEASED, witness: str | None = None) -> dict:
        ceremony = SC.initial_ceremony_id(DEV, K_ACT)
        reason = SC.OWNER_RELEASE_AFTER_ELIGIBILITY if state == SC.RELEASED else SC.INITIAL_CUSTODY_BOOTSTRAP
        record = SC.CeremonyHoldV1(DEV, ceremony, SC.INITIAL_CUSTODY, state, reason, None, K_ACT,
                                   witness or self.head_digest()).to_dict()
        return PA.hold_snapshot_document(SC.hold_store(record), environment=DEV)

    def ledger_epoch(self) -> str:
        ledger = self.ledger()
        try:
            return ledger.replay().ledger_epoch
        finally:
            ledger.close()


def write_credential(directory: Path, key) -> None:
    raw = key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
    path = directory / "owner-actor-signing-key"
    path.write_bytes(raw)
    os.chmod(path, 0o400)


def codename_action(value: str = "SYNTH-RR39") -> C.FrozenMemoryActionV1:
    digest = hashlib.sha256(json.dumps({"codename": value}, separators=(",", ":")).encode("ascii")).hexdigest()
    return C.FrozenMemoryActionV1(
        schema_version=1, actor_ref_id="actor.synthetic", operation=C.CREATE, memory_class="PROJECT_CODENAME_FACT",
        subject_namespace="project.homelab", subject_key="codename", value_schema="HomelabCodenameV1",
        payload_digest=digest, expected_active_revision_id=None, restore_revision_id=None,
        purpose=C.LONG_TERM_PERSONAL_PROJECT_RECALL)


def action_dict(action: C.FrozenMemoryActionV1) -> dict:
    return {"schemaVersion": action.schema_version, "actorRefId": action.actor_ref_id,
            "operation": action.operation, "memoryClass": action.memory_class,
            "subjectNamespace": action.subject_namespace, "subjectKey": action.subject_key,
            "valueSchema": action.value_schema, "payloadDigest": action.payload_digest,
            "expectedActiveRevisionId": action.expected_active_revision_id,
            "restoreRevisionId": action.restore_revision_id, "purpose": action.purpose}


@unittest.skipUnless(POSIX, "ownership and modes are POSIX")
class GovernedIssuanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.host = DevHost(Path(self.directory.name) / "host").genesis_host()
        self.credentials = Path(self.directory.name) / "credentials"
        self.credentials.mkdir(mode=0o700)
        write_credential(self.credentials, PB.private(K_ACT))
        self.registered = [SCH.credential_dict()]
        self.witness_calls = []
        self.now = NOW
        self.core = self.make_core()

    # ------------------------------------------------------------------------------------------ helpers ---

    def record_ledger_advance(self, previous, sequence, head):
        self.witness_calls.append((previous, sequence, head))
        self.host.writer().record_ledger_advance(previous_witness_digest=previous, ledger_sequence=sequence,
                                                 ledger_head=head, context=self.host.context(),
                                                 updated_at="2026-09-27T12:00:40Z")
        return {"status": "OK"}

    def handler(self, **overrides):
        value = dict(
            profile=PROFILE, owner_proof=OWNER_PROOF,
            view=lambda: STATE.signer_view(environment=DEV, root=self.host.root, owner_uid=X.UID),
            open_ledger=self.host.ledger,
            load_signing_key=lambda: CRED.load_owner_actor_signing_key(str(self.credentials),
                                                                       expected_directory=str(self.credentials)),
            registered_credentials=lambda: tuple(self.registered),
            record_ledger_advance=self.record_ledger_advance, now_fn=lambda: self.now)
        value.update(overrides)
        return ISS.IssuanceHandlerV1(**value)

    def make_core(self, **overrides):
        status = CRED.CredentialStatusV1(CRED.CREDENTIAL_PRESENT_UNVERIFIED,
                                         hashlib.sha256(PB.raw_public(K_ACT)).hexdigest())
        return CORE.DevAuthoritySignerCoreV1(status, issuance=self.handler(**overrides))

    def challenge(self, action, challenge_id="och.rr39-1", **overrides):
        value = SCH.challenge_dict(action, challengeId=challenge_id, deploymentEnvironment=DEV,
                                   authorityDomain=AUTHORITY_DOMAIN, logicalOwnerId=LOGICAL_OWNER,
                                   policyVersion=PB.POLICY, ledgerEpoch=self.host.ledger_epoch(),
                                   issuedAt=ISSUED_AT, expiresAt=EXPIRES_AT, memoryItemId=None,
                                   requestDigest=hashlib.sha256(challenge_id.encode()).hexdigest())
        value.update(overrides)
        return K.OwnerMemoryChallengeV2.from_dict(value)

    def payload(self, action=None, *, challenge=None, private=None, credential=None, hold=None, **replace):
        action = action or codename_action()
        challenge = challenge or self.challenge(action)
        value = {"challengeId": challenge["challengeId"], "action": action_dict(action),
                 "assertion": SCH.assertion_dict(challenge.webauthn_challenge(), private),
                 "ownerCredential": credential or SCH.credential_dict(),
                 "challenge": json.loads(challenge.canonical_bytes()),
                 "holdStore": hold or self.host.released_snapshot()}
        value.update(replace)
        return value

    def issue(self, payload=None, core=None):
        frame = W.encode_frame(W.ISSUE_OWNER_EVIDENCE, payload or self.payload())
        return (core or self.core).dispatch(W.parse_frame(frame))

    def journal_ops(self):
        ledger = self.host.ledger()
        try:
            return [op["op"] for op in ledger.journal()]
        finally:
            ledger.close()

    def assertRefused(self, result, reason, detail=None):
        self.assertEqual((result["status"], result["reason"]), ("REFUSED", reason), result)
        if detail is not None:
            self.assertEqual(result["detail"], detail, result)
        self.assertEqual(self.journal_ops(), ["GENESIS"])                   # nothing journalled
        self.assertEqual(self.witness_calls, [])

    # ---------------------------------------------------------------------------------------- positive ---

    def test_a_fully_governed_request_issues_exactly_one_verifiable_evidence(self):
        result = self.issue()
        self.assertEqual(result["status"], ISS.ISSUED, result)
        evidence = result["evidence"]
        self.assertEqual((evidence["environment"], evidence["keyId"], evidence["signingDomain"],
                          evidence["registryVersion"]), (DEV, K_ACT, A.OWNER_ACTOR, 1))
        # Independently verifiable under the B1b-3a verifier, from the pinned DEV root and the registry alone.
        context = A.AuthorityVerificationContextV1(environment=DEV, purpose=A.NEW_ADMISSION, registry_root=DEV_ROOT,
                                                   trusted_minimum_registry_version=1,
                                                   expected_recovery_epoch=PB.EG, policy_version=PB.POLICY)
        expectation = A.OwnerEvidenceExpectationV2(
            evidence_id=evidence["evidenceId"], challenge_id="och.rr39-1",
            challenge_digest=evidence["challengeDigest"], credential_record_id="ocred.synthetic",
            assertion_digest=evidence["assertionDigest"], action_digest=codename_action().action_digest,
            request_digest=evidence["requestDigest"], payload_digest=codename_action().payload_digest,
            logical_owner_id=LOGICAL_OWNER, authority_domain=AUTHORITY_DOMAIN)
        verified = AV.verify_owner_evidence(context=context, registry=self.host.registry, evidence=evidence,
                                            expectation=expectation)
        self.assertEqual(verified.status, AV.VERIFIED_AUTHORITY_EVIDENCE, verified)
        # Durable single-use record: one challenge PREPARE/CONSUME/ISSUE, witnessed at the new position.
        self.assertEqual(self.journal_ops(), ["GENESIS", "PREPARE", "CONSUME", "ISSUE"])
        ledger = self.host.ledger()
        try:
            issued = ledger.replay().issued
        finally:
            ledger.close()
        self.assertEqual(list(issued), [evidence["evidenceId"]])
        self.assertEqual(len(self.witness_calls), 1)
        self.assertEqual(result["challengeRecord"]["state"], "CONSUMED")

    def test_two_distinct_owner_challenges_issue_in_sequence(self):
        self.assertEqual(self.issue()["status"], ISS.ISSUED)
        second = self.challenge(codename_action("SYNTH-SECOND"), "och.rr39-2")
        self.assertEqual(self.issue(self.payload(codename_action("SYNTH-SECOND"), challenge=second))["status"],
                         ISS.ISSUED)
        self.assertEqual(self.journal_ops()[1:], ["PREPARE", "CONSUME", "ISSUE"] * 2)

    # ------------------------------------------------------------------------------------------- replay ---

    def test_a_repeated_challenge_or_evidence_request_is_refused(self):
        payload = self.payload()
        self.assertEqual(self.issue(payload)["status"], ISS.ISSUED)
        again = self.issue(payload)
        self.assertEqual((again["status"], again["reason"], again["detail"]),
                         ("REFUSED", "LEDGER_WRITE_REFUSED", "CHALLENGE_ALREADY_KNOWN"), again)
        self.assertEqual(self.journal_ops(), ["GENESIS", "PREPARE", "CONSUME", "ISSUE"])

    def test_an_unwitnessed_commit_withholds_the_evidence(self):
        core = self.make_core(record_ledger_advance=lambda *_: {"status": "REFUSED", "reason": "X"})
        result = self.issue(core=core)
        self.assertEqual(result["status"], ISS.LEDGER_AHEAD_OF_WITNESS)
        self.assertNotIn("evidence", result)
        later = self.issue(self.payload(challenge=self.challenge(codename_action(), "och.rr39-9")))
        self.assertEqual((later["reason"], later["detail"]), ("LEDGER_NOT_AT_WITNESS", "LEDGER_AHEAD_OF_WITNESS"))

    # ------------------------------------------------------------------------------------ registry/key ---

    def test_missing_registry_is_refused(self):
        os.unlink(self.host.path(f"{P.REGISTRY_DIR}/{HI.registry_file_name(1)}"))
        self.assertRefused(self.issue(), "SIGNER_INPUTS_INCOMPLETE")

    def test_wrong_loaded_key_is_refused(self):
        write = self.credentials / "owner-actor-signing-key"
        os.chmod(write, 0o600)
        write_credential_bytes = PB.private(PB.S2).private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
        write.write_bytes(write_credential_bytes)
        self.assertRefused(self.issue(), "LOADED_KEY_NOT_REGISTRY_KEY")

    def test_missing_signing_credential_is_refused(self):
        os.unlink(self.credentials / "owner-actor-signing-key")
        self.assertRefused(self.issue(), "SIGNING_KEY_UNAVAILABLE")

    def test_a_registry_whose_key_is_revoked_or_another_key_is_refused(self):
        core = self.make_core(profile=DevSyntheticSignerProfileV1(
            environment=DEV, key_id=PB.S2, authority_domain=AUTHORITY_DOMAIN, logical_owner_id=LOGICAL_OWNER,
            policy_version=PB.POLICY))
        self.assertRefused(self.issue(core=core), "PROFILE_KEY_NOT_HEAD_CURRENT")

    def test_a_validly_signed_registry_with_the_key_revoked_is_refused(self):
        revoked = SA.registry("dev-root", keys=[PB.key(K_ACT, version=1, environment=DEV,
                                                       revokedAt="2026-09-26T05:00:00Z", revocationReason="ROUTINE")],
                              registryVersion=1, recoveryEpoch=PB.EG.to_dict(), policyVersion=PB.POLICY,
                              issuedAt="2026-09-26T06:00:00Z", environment=DEV,
                              registryRootKeyId=SA.DEV_ROOT_KEY_ID)
        try:
            self.host = DevHost(Path(self.directory.name) / "revoked", registry=revoked).genesis_host()
        except Exception as exc:  # noqa: BLE001 - the governed bootstrap itself refuses such a registry
            self.assertNotIsInstance(exc, AssertionError)
            return
        self.core = self.make_core()
        result = self.issue()
        self.assertEqual(result["status"], "REFUSED", result)
        self.assertIn(result["reason"], ("KEY_TRANSITION_NOT_VERIFIED", "PROFILE_KEY_NOT_HEAD_CURRENT",
                                         "LOADED_KEY_NOT_REGISTRY_KEY"), result)
        self.assertEqual(self.journal_ops(), ["GENESIS"])

    def test_a_tampered_registry_fails_history_verification(self):
        tampered = copy.deepcopy(self.host.registry)
        tampered["keys"][0]["revokedAt"] = "2026-09-26T07:00:00Z"
        tampered["keys"][0]["revocationReason"] = "ROUTINE"
        self.host.document(f"{P.REGISTRY_DIR}/{HI.registry_file_name(1)}", tampered)   # K-ROOT signature breaks
        result = self.issue()
        self.assertEqual(result["status"], "REFUSED")
        self.assertIn(result["reason"], ("SIGNER_INPUTS_INCOMPLETE", "HISTORY_NOT_VERIFIED"), result)
        self.assertEqual(self.journal_ops(), ["GENESIS"])

    # ---------------------------------------------------------------------------------- epoch/witness ---

    def test_a_challenge_for_another_epoch_is_refused(self):
        stale = self.challenge(codename_action(), ledgerEpoch="0123456789abcdef0123456789abcdef")
        self.assertRefused(self.issue(self.payload(challenge=stale)), "CHALLENGE_CONTEXT_MISMATCH")

    def test_missing_witness_is_refused(self):
        import shutil
        payload = self.payload()
        shutil.rmtree(self.host.path(P.WITNESS_STATE))
        os.makedirs(self.host.path(P.WITNESS_STATE), mode=0o750)
        result = self.issue(payload)
        self.assertEqual(result["status"], "REFUSED")
        self.assertIn(result["reason"], ("SIGNER_INPUTS_INCOMPLETE", "HISTORY_NOT_VERIFIED"), result)
        self.assertEqual(self.journal_ops(), ["GENESIS"])

    def test_an_invalid_ledger_is_refused(self):
        payload = self.payload()
        os.unlink(self.host.path(P.AUTHORITY_LEDGER))
        result = self.issue(payload)
        self.assertEqual((result["status"], result["reason"]), ("REFUSED", "AUTHORITY_STATE_MISSING"), result)

    # --------------------------------------------------------------------------------------------- hold ---

    def test_a_held_or_absent_custody_hold_is_refused(self):
        held = self.host.released_snapshot(state=SC.HELD, witness=self.host.head_digest())
        self.assertRefused(self.issue(self.payload(hold=held)), "HOLD_NOT_RELEASED_FOR_ISSUANCE")
        empty = PA.hold_snapshot_document(SC.hold_store(), environment=DEV)
        self.assertRefused(self.issue(self.payload(hold=empty)), "HOLD_NOT_RELEASED_FOR_ISSUANCE")

    def test_a_partial_or_malformed_hold_snapshot_is_refused(self):
        snapshot = self.host.released_snapshot()
        snapshot = {**snapshot, "listingDigest": "0" * 64}
        self.assertRefused(self.issue(self.payload(hold=snapshot)), "HOLD_SNAPSHOT_INVALID")

    # -------------------------------------------------------------------------------------------- owner ---

    def test_an_unregistered_owner_credential_is_refused(self):
        self.registered = []
        self.assertRefused(self.issue(), "OWNER_CREDENTIAL_NOT_REGISTERED")

    def test_a_forged_webauthn_assertion_is_refused(self):
        forged = self.payload(private=SCH.owner_key(SCH.TEST_ONLY_ATTACKER_SCALAR))
        self.assertRefused(self.issue(forged), "OWNER_PROOF_REJECTED")

    def test_an_assertion_over_another_challenge_is_refused(self):
        action = codename_action()
        other = self.challenge(action, "och.rr39-other")
        payload = self.payload(action)
        payload["assertion"] = SCH.assertion_dict(other.webauthn_challenge())
        self.assertRefused(self.issue(payload), "OWNER_PROOF_REJECTED")

    def test_an_expired_challenge_is_refused(self):
        self.now = NOW + timedelta(minutes=5)
        self.assertRefused(self.issue(self.payload()), "CHALLENGE_EXPIRED")

    def test_an_action_that_is_not_the_challenged_one_is_refused(self):
        payload = self.payload()
        payload["action"] = action_dict(codename_action("SYNTH-SWAPPED"))
        self.assertRefused(self.issue(payload), "OWNER_PROOF_REJECTED")

    # ------------------------------------------------------------------- no arbitrary signing surface ---

    def test_no_request_can_choose_bytes_domain_key_or_digest(self):
        for extra in ({"signingDomain": "PRIVACY"}, {"keyId": "test-only.dev-synthetic.actor.b1b3e.9"},
                      {"bytes": "AAAA"}, {"evidenceDigest": "0" * 64}, {"policyVersion": "policy.x"}):
            payload = {**self.payload(), **extra}
            with self.assertRaises(W.ProtocolError) as caught:
                W.parse_frame(W.encode_frame(W.ISSUE_OWNER_EVIDENCE, payload))
            self.assertEqual(caught.exception.code, "INVALID_PAYLOAD_FIELDS")
        for operation in ("SIGN", "SIGN_BYTES", "ISSUE"):
            with self.assertRaises(W.ProtocolError):
                W.parse_frame(W.encode_frame(operation, {}))
        self.assertEqual(self.journal_ops(), ["GENESIS"])

    def test_a_forget_or_non_codename_purpose_is_refused_before_any_state(self):
        payload = self.payload()
        payload["action"] = {**payload["action"], "operation": "FORGET", "valueSchema": None}
        with self.assertRaises(W.ProtocolError) as caught:
            W.parse_frame(W.encode_frame(W.ISSUE_OWNER_EVIDENCE, payload))
        self.assertIn(caught.exception.code, ("PRIVACY_OWNED_OPERATION", "INVALID_ACTION"))
        payload = self.payload()
        payload["action"] = {**payload["action"], "purpose": "OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION"}
        with self.assertRaises(W.ProtocolError) as caught:
            W.parse_frame(W.encode_frame(W.ISSUE_OWNER_EVIDENCE, payload))
        self.assertEqual(caught.exception.code, "INVALID_ACTION")

    # ---------------------------------------------------------------------- existing refusals unchanged ---

    def test_without_the_handler_or_in_the_legacy_form_issuance_stays_refused(self):
        status = CRED.CredentialStatusV1(CRED.CREDENTIAL_PRESENT_UNVERIFIED, "ab" * 32)
        unwired = CORE.DevAuthoritySignerCoreV1(status)
        self.assertEqual(self.issue(core=unwired)["reason"], "SIGNING_NOT_AVAILABLE")
        legacy = {k: v for k, v in self.payload().items() if k not in ("challenge", "holdStore")}
        self.assertEqual(self.issue(legacy)["reason"], "SIGNING_NOT_AVAILABLE")
        absent = CORE.DevAuthoritySignerCoreV1(CRED.CredentialStatusV1(CRED.CREDENTIAL_ABSENT),
                                               issuance=self.handler())
        self.assertEqual(self.issue(core=absent)["reason"], "SIGNING_NOT_AVAILABLE")
        self.assertEqual(self.journal_ops(), ["GENESIS"])

    def test_the_dev_runtime_still_constructs_no_issuance_handler(self):
        from lilith_authority_dev import server
        core = server.build_core(CRED.CredentialStatusV1(CRED.CREDENTIAL_PRESENT_UNVERIFIED, "ab" * 32))
        self.assertIsNone(core._issuance)
        self.assertIn("ISSUANCE_UNWIRED", STATE.STRUCTURAL_SELF_VIEW_REASONS)


# ===================================================== First Memory (2df33b8) with the real signer ===

@unittest.skipUnless(POSIX, "ownership and modes are POSIX")
class FirstMemoryWithRealSignerTests(unittest.TestCase):
    """The unchanged First Memory composition (2df33b8), its consent issued by the real governed signer path."""

    def setUp(self):
        import test_first_memory_conversation as FMT
        from lilith_authority_signer import synthetic_evidence_ledger as EL
        from lilith_owner_memory import first_memory_conversation as FMC
        self.FMC = FMC
        self.fm_case = FMT.FirstMemoryConversationTests("test_ordinary_dialogue_is_not_a_memory_request")
        self.fm_case.setUp()
        self.addCleanup(self.fm_case.doCleanups)
        self.signer = GovernedIssuanceTests("test_a_fully_governed_request_issues_exactly_one_verifiable_evidence")
        self.signer.setUp()
        self.addCleanup(self.signer.doCleanups)
        self.records = {}
        self.ledger_epoch = self.signer.host.ledger_epoch()
        self.use_ledger = EL.SyntheticEvidenceUseLedgerV1()     # authority-side use ledger (DEV transport: absent)

    def owner_context(self) -> K.AcceptanceContextV1:
        return K.AcceptanceContextV1(
            deployment_environment=DEV, authority_domain=AUTHORITY_DOMAIN, logical_owner_id=LOGICAL_OWNER,
            owner_principal=SCH.OWNER_PRINCIPAL, rp_id=SCH.RP, origin=SCH.ORIGIN, policy_version=PB.POLICY,
            registry_tuple_version=SCH.REGISTRY_VERSION, ledger_epoch=self.ledger_epoch,
            privacy_notice_version=SCH.PRIVACY_NOTICE, broker_releases=frozenset({SCH.BROKER_RELEASE}))

    def authority_context(self, purpose=A.NEW_ADMISSION) -> A.AuthorityVerificationContextV1:
        return A.AuthorityVerificationContextV1(environment=DEV, purpose=purpose, registry_root=DEV_ROOT,
                                                trusted_minimum_registry_version=1, expected_recovery_epoch=PB.EG,
                                                policy_version=PB.POLICY)

    def challenge_context(self) -> dict:
        return {"protocol": OP.PROTOCOL, "schemaVersion": K.CHALLENGE_V2_SCHEMA_VERSION,
                "ownerPrincipal": SCH.OWNER_PRINCIPAL, "privacyNoticeVersion": SCH.PRIVACY_NOTICE, "rpId": SCH.RP,
                "deploymentEnvironment": DEV, "authorityDomain": AUTHORITY_DOMAIN, "logicalOwnerId": LOGICAL_OWNER,
                "policyVersion": PB.POLICY, "registryTupleVersion": SCH.REGISTRY_VERSION,
                "ledgerEpoch": self.ledger_epoch}

    def conversation(self):
        from lilith_owner_memory import accepted_read_v2 as AR
        from lilith_owner_memory import l04_v2_adapter as AD
        from lilith_memory import memory_v2
        fm, flow, l04 = self.fm_case, self.fm_case.flow, self.fm_case.flow.l04
        signer, records = self.signer, self.records

        class RealSignerIssuer:
            def __init__(self):
                self.challenges = {}

            def prepare(self, challenge_json):
                challenge = json.loads(challenge_json)
                self.challenges[challenge["challengeId"]] = challenge     # journalled by the signer at issue

            def issue(self, challenge_id, action, assertion, credential):
                payload = {"challengeId": challenge_id, "action": action_dict(action), "assertion": dict(assertion),
                           "ownerCredential": dict(credential), "challenge": self.challenges[challenge_id],
                           "holdStore": signer.host.released_snapshot()}
                result = signer.issue(payload)
                if result.get("status") != ISS.ISSUED:
                    raise fm_module.FirstMemoryRefused(str(result.get("reason")))
                records[challenge_id] = result["challengeRecord"]
                return fm_module.IssuedEvidenceV1(result["evidence"], result["challengeRecord"])

        fm_module = self.FMC

        def adapter():
            return AD.L04V2AdmissionAdapter(
                AD.v2_admission_store(l04.store()), owner_context=self.owner_context(),
                authority_context=self.authority_context(), registry_provider=lambda: signer.host.registry,
                link_store=flow.links, evidence_use_ledger=self.use_ledger)

        def reader():
            resolver = fm.binding.resolver
            facade = memory_v2.CanonicalMemoryReadFacade(
                l04.store(privacy_hold_resolver=resolver), registry=l04.tuple_registry, consent_store=l04.consent,
                privacy_hold_resolver=resolver, actor_resolver=lambda actor: actor == l04.actor.ACTOR)
            return AR.AcceptedMemoryReadFacadeV2(
                facade, l04.store(), owner_context=self.owner_context(),
                authority_context=self.authority_context(A.HISTORICAL_VERIFICATION),
                registry_provider=lambda: signer.host.registry,
                challenge_record_provider=lambda cid: records.get(cid) or flow.links.challenge_record(cid),
                link_store=flow.links, evidence_use_ledger=self.use_ledger)

        issued_at = datetime(2026, 9, 27, 12, 0, 0, tzinfo=timezone.utc)
        return self.FMC.FirstMemoryConversationV1(
            privacy=fm.binding, l04=self.FMC.L04ComponentsV1(l04.actor, l04.policy, l04.consent, l04.learning),
            adapter=adapter, reader=reader, issuer=RealSignerIssuer(), tuple_policy=l04.registry_policy,
            challenge_context=self.challenge_context(), now_fn=lambda: issued_at)

    def test_real_signer_evidence_admits_and_a_new_session_recalls(self):
        conversation = self.conversation()
        offer = conversation.offer("sess.a", "Remember my project codename is SYNTH-ORCHID")
        self.assertEqual(offer.status, self.FMC.OFFERED)
        assertion, credential = SCH.assertion_dict(offer.webauthn_challenge), SCH.credential_dict()
        result = conversation.consent(offer.offer_id, "sess.a", assertion, credential)
        self.assertEqual(result.status, self.FMC.ADMITTED, result)
        self.assertEqual(self.signer.journal_ops(), ["GENESIS", "PREPARE", "CONSUME", "ISSUE"])
        recalled = self.conversation().recall("sess.b-new", "What is my project codename?")
        self.assertEqual((recalled.status, recalled.codename), (self.FMC.RECALLED, "SYNTH-ORCHID"), recalled)

    def test_a_forged_owner_assertion_admits_nothing(self):
        conversation = self.conversation()
        offer = conversation.offer("sess.a", "Remember my project codename is SYNTH-ORCHID")
        forged = SCH.assertion_dict(offer.webauthn_challenge, SCH.owner_key(SCH.TEST_ONLY_ATTACKER_SCALAR))
        result = conversation.consent(offer.offer_id, "sess.a", forged, SCH.credential_dict())
        self.assertEqual((result.status, result.reason),
                         (self.FMC.NOT_ADMITTED, "SIGNER_REFUSED:OWNER_PROOF_REJECTED"))
        self.assertEqual(self.signer.journal_ops(), ["GENESIS"])
        self.assertEqual(self.conversation().recall("sess.b", "What is my project codename?").status,
                         self.FMC.NOTHING_RECALLED)


if __name__ == "__main__":
    unittest.main()
