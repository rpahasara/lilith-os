"""First Memory: minimum DEV_SYNTHETIC conversation -> consent -> canonical L04 -> new-session recall (TEST_ONLY).

Real components throughout: the unchanged L04 V2 store with the durable admission link (fresh A1-A7), the real
Privacy Governance store with a real First Interaction FORGET (the F9c2 state), the real Track B root freshness
steps (`privacy_freshness_fixture.FreshnessHarness`: anchor, owner checkpoint, boot unlock, marker), the
restore-gated hold resolver, the L04 V2 adapter and the accepted-memory read facade. TEST_ONLY stand-ins: the
synthetic owner WebAuthn authenticator and the TEST broker signer. The installed DEV signer core is exercised
in-process through its real frame protocol to show what it does today.
"""

from __future__ import annotations

import sqlite3
import sys
import unittest
from datetime import timedelta
from pathlib import Path

import synthetic_authority as SA
import synthetic_b1b3b as T
import synthetic_chain as SC

ROOT = Path(__file__).resolve().parents[3]
for _path in (ROOT / "services/core-api/tests", ROOT / "services/authority-dev"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from privacy_freshness_fixture import FreshnessHarness  # noqa: E402
from lilith_authority_dev import core as SIGNER_CORE  # noqa: E402
from lilith_authority_dev import credential as SIGNER_CRED  # noqa: E402
from lilith_authority_dev import protocol as SIGNER_WIRE  # noqa: E402
from lilith_authority_signer import synthetic_broker as B  # noqa: E402
from lilith_memory import canonical_contracts as C  # noqa: E402
from lilith_memory import learning_v2  # noqa: E402
from lilith_memory import memory_v2  # noqa: E402
from lilith_memory import owner_proof as P  # noqa: E402
from lilith_memory import privacy_forget_runner as R  # noqa: E402
from lilith_memory import privacy_freshness as F  # noqa: E402
from lilith_memory import privacy_governance as PG  # noqa: E402
from lilith_memory import slice15b2a_migration  # noqa: E402
from lilith_owner_memory import accepted_read_v2 as AR  # noqa: E402
from lilith_owner_memory import contracts as K  # noqa: E402
from lilith_owner_memory import first_memory_conversation as FMC  # noqa: E402

TEST_ONLY_PRIVACY_SECRET = b"TEST_ONLY first-memory conversation privacy secret"
REMEMBER = "Remember my project codename is SYNTH-ORCHID"
ASK = "What is my project codename?"


def challenge_context() -> dict:
    """The deployment's trusted challenge context (here: the synthetic owner and TEST broker policy)."""
    return {"protocol": P.PROTOCOL, "schemaVersion": K.CHALLENGE_V2_SCHEMA_VERSION,
            "ownerPrincipal": SC.OWNER_PRINCIPAL, "privacyNoticeVersion": SC.PRIVACY_NOTICE, "rpId": SC.RP,
            "deploymentEnvironment": SC.ENVIRONMENT, "authorityDomain": SC.AUTHORITY_DOMAIN,
            "logicalOwnerId": SC.LOGICAL_OWNER, "policyVersion": SA.POLICY,
            "registryTupleVersion": SC.REGISTRY_VERSION, "ledgerEpoch": SC.LEDGER_EPOCH}


class TestBrokerIssuer:
    """TEST_ONLY: the B1b-3b TEST broker as the trusted signer (it verifies and consumes the owner proof itself)."""

    def __init__(self, flow: T.Flow):
        self.flow = flow
        self.calls = 0

    def prepare(self, challenge_json: bytes) -> None:
        assert self.flow.broker.prepare_challenge(challenge_json).status == B.PREPARED

    def issue(self, challenge_id, action, assertion, credential):
        self.calls += 1
        self.flow.clock.value = T.CHALLENGE_ISSUED + timedelta(seconds=20)
        consumed = self.flow.broker.consume_owner_proof(challenge_id, action=action, assertion=assertion,
                                                        owner_credential=credential)
        if consumed.status != B.CONSUMED:
            raise FMC.FirstMemoryRefused(str(consumed.reason))
        issued = self.flow.broker.issue_owner_evidence(B.OwnerEvidenceRequestV1(challenge_id, action, assertion,
                                                                                credential))
        if issued.status != B.ISSUED:
            raise FMC.FirstMemoryRefused(str(issued.reason))
        return FMC.IssuedEvidenceV1(dict(issued.evidence), self.flow.broker.ledger_record(challenge_id))


class InstalledSignerIssuer:
    """The installed DEV signer core (authority-dev L1 / PR-1S), reached through its real frame protocol."""

    def __init__(self):
        status = SIGNER_CRED.CredentialStatusV1(SIGNER_CRED.CREDENTIAL_PRESENT_UNVERIFIED, "ab" * 32)
        self.core = SIGNER_CORE.DevAuthoritySignerCoreV1(status)

    def prepare(self, challenge_json: bytes) -> None:
        pass                                                                 # the installed signer has no ledger op

    def issue(self, challenge_id, action, assertion, credential):
        payload = {"challengeId": challenge_id, "action": {
            "schemaVersion": action.schema_version, "actorRefId": action.actor_ref_id, "operation": action.operation,
            "memoryClass": action.memory_class, "subjectNamespace": action.subject_namespace,
            "subjectKey": action.subject_key, "valueSchema": action.value_schema,
            "payloadDigest": action.payload_digest, "expectedActiveRevisionId": action.expected_active_revision_id,
            "restoreRevisionId": action.restore_revision_id, "purpose": action.purpose},
            "assertion": dict(assertion), "ownerCredential": dict(credential)}
        response = self.core.dispatch(SIGNER_WIRE.parse_frame(
            SIGNER_WIRE.encode_frame(SIGNER_WIRE.ISSUE_OWNER_EVIDENCE, payload)))
        raise FMC.FirstMemoryRefused(str(response.get("reason")))           # it never issues today


class FirstMemoryConversationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.flow = T.Flow(durable=True)
        self.addCleanup(self.flow.l04.close)
        l04 = self.flow.l04
        self.root = l04.root
        self.privacy_db = self.root / "f9-drill" / "privacy_governance.f9drill.db"
        self.stale = self.root / "data" / "privacy_governance.dev.db"
        self.privacy_db.parent.mkdir()
        self.stale.parent.mkdir()
        slice15b2a_migration.migrate_privacy(self.privacy_db, applied_at="2026-10-26T00:00:00.000000Z")
        self.privacy = PG.PrivacyGovernanceStore(self.privacy_db, TEST_ONLY_PRIVACY_SECRET, l04.actor)
        self.pre_forget = self.root / "privacy.pre-forget.copy.db"
        self.copy_db(self.privacy_db, self.pre_forget)
        self.forget_first_interaction()                                     # the historical F9c2 FORGET
        self.fresh = FreshnessHarness(self.root, self.privacy_db)
        self.fresh.genesis()                                                # anchor v1 + checkpoint 1 + unlock
        self.binding = self.bind()
        l04.privacy = self.binding.resolver                                 # every L04 owner uses the binding
        l04.learning = learning_v2.LearningV2Store(
            l04.db, privacy_hold_resolver=self.binding.resolver, containment_ready=lambda: True,
            actor_authority=l04.actor, policy_store=l04.policy, consent_store=l04.consent, now_fn=lambda: l04.now)
        self.issuer = TestBrokerIssuer(self.flow)
        self.fm = self.conversation(self.issuer)

    # ------------------------------------------------------------------------------------------ helpers ---

    @staticmethod
    def copy_db(source: Path, target: Path) -> None:
        src, dst = sqlite3.connect(source), sqlite3.connect(target)
        try:
            src.backup(dst)
        finally:
            src.close()
            dst.close()

    def forget_first_interaction(self) -> None:
        l04 = self.flow.l04
        action = R.first_interaction_forget_action(l04.actor.ACTOR.actor_ref_id)
        evidence = l04.actor.issue(action=action, request_digest="1" * 64, nonce="f9c2.historical")
        _r, auth, _s = self.privacy.begin_forget(
            action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id, intent_ref_id="intent.f9c2",
            memory_item_id=None, resource_owners=("L04", "L18_V2"), confirmation_event_ref="confirm.f9c2")
        for owner in (memory_v2.L04PrivacyErasureOwner(l04.db, self.privacy),
                      memory_v2.L18V2PrivacyErasureOwner(l04.db, self.privacy)):
            owner.erase_authorized(auth.authorization_ref_id, auth.execution_nonce)
        self.privacy.complete(auth.authorization_ref_id, auth.execution_nonce)

    def bind(self, **kw) -> FMC.PrivacyBindingV1:
        values = dict(authoritative=self.privacy_db, stale=self.stale, freshness=self.fresh.gate())
        values.update(kw)
        return FMC.PrivacyBindingV1(self.privacy_db, self.privacy, self.flow.l04.db, **values)

    def reader(self) -> AR.AcceptedMemoryReadFacadeV2:
        l04, resolver = self.flow.l04, self.binding.resolver
        facade = memory_v2.CanonicalMemoryReadFacade(
            l04.store(privacy_hold_resolver=resolver), registry=l04.tuple_registry, consent_store=l04.consent,
            privacy_hold_resolver=resolver, actor_resolver=lambda actor: actor == l04.actor.ACTOR)
        return AR.AcceptedMemoryReadFacadeV2(
            facade, l04.store(), owner_context=T.owner_context(), authority_context=SA.historical_context(),
            registry_provider=lambda: self.flow.registry_doc, challenge_record_provider=self.flow.challenge_record,
            link_store=self.flow.links, evidence_use_ledger=self.flow.ledger)

    def conversation(self, issuer, binding=None) -> FMC.FirstMemoryConversationV1:
        l04 = self.flow.l04
        return FMC.FirstMemoryConversationV1(
            privacy=binding or self.binding, l04=FMC.L04ComponentsV1(l04.actor, l04.policy, l04.consent, l04.learning),
            adapter=self.flow.make_adapter, reader=self.reader, issuer=issuer, tuple_policy=l04.registry_policy,
            challenge_context=challenge_context(), now_fn=lambda: T.CHALLENGE_ISSUED)

    def owner_consents(self, offer, *, private=None):
        """The owner's authenticator signs exactly the offered challenge (TEST_ONLY synthetic WebAuthn)."""
        return SC.assertion_dict(offer.webauthn_challenge, private), SC.credential_dict()

    def rows(self) -> dict:
        counts = self.flow.l04.counts()
        conn = sqlite3.connect(self.flow.l04.db)
        try:
            for table in ("learning_v2_intent", "learning_v2_candidate", "learning_v2_proposal_ref"):
                try:
                    counts[table] = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                except sqlite3.OperationalError:
                    pass
        finally:
            conn.close()
        return counts

    def remember(self, session="sess.a"):
        offer = self.fm.offer(session, REMEMBER)
        self.assertEqual(offer.status, FMC.OFFERED)
        assertion, credential = self.owner_consents(offer)
        return offer, self.fm.consent(offer.offer_id, session, assertion, credential)

    # -------------------------------------------------------------------------------------------- tests ---

    def test_authorized_memory_persists_and_a_new_session_recalls_it(self):
        offer, result = self.remember("sess.a")
        self.assertEqual(offer.codename, "SYNTH-ORCHID")
        self.assertEqual(result.status, FMC.ADMITTED, result)
        # A new session, a new composition object, nothing carried over but canonical storage.
        fresh_process = self.conversation(TestBrokerIssuer(self.flow))
        recalled = fresh_process.recall("sess.b-new", ASK)
        self.assertEqual((recalled.status, recalled.codename), (FMC.RECALLED, "SYNTH-ORCHID"), recalled)

    def test_ordinary_dialogue_is_not_a_memory_request(self):
        before = self.rows()
        for text in ("my project codename is SYNTH-ORCHID", "maybe remember it later", "remember this: SYNTH-X"):
            self.assertEqual(self.fm.offer("sess.a", text).status, FMC.NOT_A_MEMORY_REQUEST)
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.issuer.calls, 0)

    def test_no_consent_means_no_memory(self):
        before = self.rows()
        offer = self.fm.offer("sess.a", REMEMBER)                           # offered, never consented
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.fm.recall("sess.b", ASK).status, FMC.NOTHING_RECALLED)
        # a forged authenticator (not the owner's key) is refused by the signer: still nothing written
        assertion, credential = self.owner_consents(offer, private=SC.owner_key(SC.TEST_ONLY_ATTACKER_SCALAR))
        result = self.fm.consent(offer.offer_id, "sess.a", assertion, credential)
        self.assertEqual(result.status, FMC.NOT_ADMITTED)
        self.assertTrue(result.reason.startswith("SIGNER_REFUSED:"), result)
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.fm.recall("sess.b", ASK).status, FMC.NOTHING_RECALLED)

    def test_consent_is_single_use_and_bound_to_its_session(self):
        offer = self.fm.offer("sess.a", REMEMBER)
        assertion, credential = self.owner_consents(offer)
        with self.assertRaises(FMC.FirstMemoryRefused) as caught:
            self.fm.consent(offer.offer_id, "sess.other", assertion, credential)
        self.assertEqual(caught.exception.code, "OFFER_OF_ANOTHER_SESSION")
        with self.assertRaises(FMC.FirstMemoryRefused) as caught:
            self.fm.consent(offer.offer_id, "sess.a", assertion, credential)
        self.assertEqual(caught.exception.code, "NO_SUCH_OFFER")
        self.assertEqual(self.fm.recall("sess.b", ASK).status, FMC.NOTHING_RECALLED)

    def test_installed_dev_signer_refuses_so_nothing_is_admitted(self):
        fm = self.conversation(InstalledSignerIssuer())
        before = self.rows()
        offer = fm.offer("sess.a", REMEMBER)
        assertion, credential = self.owner_consents(offer)
        result = fm.consent(offer.offer_id, "sess.a", assertion, credential)
        self.assertEqual((result.status, result.reason), (FMC.NOT_ADMITTED, "SIGNER_REFUSED:SIGNING_NOT_AVAILABLE"))
        self.assertEqual(self.rows(), before)
        self.assertEqual(fm.recall("sess.b", ASK).status, FMC.NOTHING_RECALLED)

    def test_stale_core_api_privacy_path_refuses_every_operation(self):
        self.stale.write_bytes(b"")                                         # a second source of truth appears
        for call in (lambda: self.fm.offer("sess.a", REMEMBER), lambda: self.fm.recall("sess.b", ASK)):
            with self.assertRaises(FMC.FirstMemoryRefused) as caught:
                call()
            self.assertEqual(caught.exception.code, "STALE_PRIVACY_PATH_PRESENT")
        with self.assertRaises(FMC.FirstMemoryRefused) as caught:
            self.bind()
        self.assertEqual(caught.exception.code, "STALE_PRIVACY_PATH_PRESENT")

    def test_only_the_authoritative_privacy_db_binds(self):
        with self.assertRaises(FMC.FirstMemoryRefused) as caught:
            self.bind(authoritative=self.stale)
        self.assertEqual(caught.exception.code, "PRIVACY_DB_NOT_AUTHORITATIVE")
        with self.assertRaises(FMC.FirstMemoryRefused) as caught:
            FMC.PrivacyBindingV1(self.privacy_db, self.privacy, self.flow.l04.db)   # DEV defaults: not this DB
        self.assertEqual(caught.exception.code, "PRIVACY_DB_NOT_AUTHORITATIVE")

    def test_stale_privacy_freshness_refuses_explicitly(self):
        _offer, result = self.remember("sess.a")
        self.assertEqual(result.status, FMC.ADMITTED)
        self.fresh.reboot()                                                 # new boot, no unlock yet
        for call in (lambda: self.fm.offer("sess.c", REMEMBER), lambda: self.fm.recall("sess.c", ASK)):
            with self.assertRaises(FMC.FirstMemoryRefused) as caught:
                call()
            self.assertEqual(caught.exception.code, "PRIVACY_FRESHNESS_NOT_READY:FRESHNESS_MARKER_UNAVAILABLE")
        self.fresh.unlock()                                                 # the owner's per-boot unlock
        self.assertEqual(self.fm.recall("sess.c", ASK).codename, "SYNTH-ORCHID")

    def test_a_privacy_store_older_than_the_anchor_is_refused(self):
        _offer, result = self.remember("sess.a")
        self.assertEqual(result.status, FMC.ADMITTED)
        self.copy_db(self.pre_forget, self.privacy_db)                      # a restored, pre-FORGET Privacy DB
        for call in (lambda: self.fm.offer("sess.d", REMEMBER), lambda: self.fm.recall("sess.d", ASK)):
            with self.assertRaises(FMC.FirstMemoryRefused) as caught:
                call()
            self.assertEqual(caught.exception.code, "PRIVACY_FRESHNESS_NOT_READY:OLDER_THAN_ANCHOR")
        with self.assertRaises(F.FreshnessStepRefused) as refused:                # and no new unlock can be had
            self.fresh.challenge()
        self.assertEqual(refused.exception.code, "OLDER_THAN_ANCHOR")

    def test_first_interaction_identity_is_never_reused(self):
        fi = memory_v2.MemoryTuplePolicyV1(
            memory_class=R.IDENTITY[0], subject_namespace=R.IDENTITY[1], subject_key=R.IDENTITY[2],
            value_schema=learning_v2.VALUE_SCHEMA, capability=C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE,
            read_allowed=True, write_allowed=True)
        l04 = self.flow.l04
        with self.assertRaises(FMC.FirstMemoryRefused) as caught:
            FMC.FirstMemoryConversationV1(
                privacy=self.binding, l04=FMC.L04ComponentsV1(l04.actor, l04.policy, l04.consent, l04.learning),
                adapter=self.flow.make_adapter, reader=self.reader, issuer=self.issuer, tuple_policy=fi,
                challenge_context=challenge_context())
        self.assertEqual(caught.exception.code, "FIRST_INTERACTION_IDENTITY_SUPPRESSED")
        self.assertTrue(self.binding.resolver.is_held(*R.IDENTITY))         # still suppressed (F9c2)

    def test_recall_does_not_depend_on_any_session_or_conversation_state(self):
        _offer, result = self.remember("sess.a")
        self.assertEqual(result.status, FMC.ADMITTED)
        self.fm._pending.clear()                                            # no offer/session state survives
        for session in ("sess.x", "sess.y"):
            self.assertEqual(self.fm.recall(session, ASK).codename, "SYNTH-ORCHID")
        self.assertEqual(self.fm.recall("sess.x", "tell me something").status, FMC.NOT_A_MEMORY_REQUEST)


if __name__ == "__main__":
    unittest.main()
