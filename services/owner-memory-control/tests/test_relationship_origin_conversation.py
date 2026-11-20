"""Relationship origin: explicit owner statement -> consent -> canonical L04 -> new-session recall -> Hermes context.

TEST_ONLY. The same real components as `test_first_memory_conversation` (L04 V2 store with the durable admission link,
the real Privacy store with the historical F9c2 First Interaction FORGET, the Track B freshness steps, the L04 V2
adapter and the accepted read), on a database moved to owner-ledger schema v3 by `relationship_origin_migration`.
Every statement here is synthetic; nothing invents the owner's or LILITH's history.

The seven focused proofs:
1. one explicit consent produces one governed admission;
2. no consent, an ordinary sentence or a composition without the origin tuple produces no memory;
3. Privacy not READY refuses everything, and a FORGET of the origin identity removes and suppresses it;
4. a new session (and a fresh composition) recalls the approved statement from L04;
5. the existing codename memory is unchanged;
6. the Hermes context comes from canonical storage, not from chat history, and adds no writer;
7. the signer, bridge and config boundaries admit no new privilege or purpose beyond the one family.
"""

from __future__ import annotations

import ast
import shutil
import sqlite3
import sys
import unittest
from pathlib import Path

import synthetic_b1b3b as T
import synthetic_chain as SC
import test_first_memory_conversation as FMT

ROOT = Path(__file__).resolve().parents[3]
for _path in (ROOT / "services/core-api/tests", ROOT / "services/authority-dev", ROOT / "services/recovery-witness"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from lilith_authority_dev import protocol as SIGNER_WIRE  # noqa: E402
from lilith_memory import backup  # noqa: E402
from lilith_memory import canonical_authority as CA  # noqa: E402
from lilith_memory import canonical_contracts as C  # noqa: E402
from lilith_memory import config as CONFIG  # noqa: E402
from lilith_memory import learning_v2  # noqa: E402
from lilith_memory import memory_action_v2 as MA  # noqa: E402
from lilith_memory import memory_v2  # noqa: E402
from lilith_memory import relationship_origin_migration as ROM  # noqa: E402
from lilith_owner_memory import first_memory_conversation as FMC  # noqa: E402
from lilith_owner_memory import hermes_memory_context as HMC  # noqa: E402

ORIGIN = "Remember our origin: TEST_ONLY synthetic origin statement, with a comma."
STATEMENT = "TEST_ONLY synthetic origin statement, with a comma."
ASK_ORIGIN = "What is our origin?"
ORIGIN_POLICY = memory_v2.MemoryTuplePolicyV1(
    *MA.RELATIONSHIP_ORIGIN_IDENTITY, value_schema=MA.RELATIONSHIP_ORIGIN_VALUE_SCHEMA,
    capability=MA.CANONICAL_MEMORY_RELATIONSHIP_ORIGIN_CREATE, read_allowed=True, write_allowed=True)
CAPABILITIES = frozenset({T.L04_CAPABILITY, MA.CANONICAL_MEMORY_RELATIONSHIP_ORIGIN_CREATE})


class RelationshipOriginConversationTests(unittest.TestCase):
    copy_db = staticmethod(FMT.FirstMemoryConversationTests.copy_db)
    forget_first_interaction = FMT.FirstMemoryConversationTests.forget_first_interaction
    bind = FMT.FirstMemoryConversationTests.bind
    reader = FMT.FirstMemoryConversationTests.reader
    owner_consents = FMT.FirstMemoryConversationTests.owner_consents

    def setUp(self) -> None:
        FMT.FirstMemoryConversationTests.setUp(self)              # F9c2 FORGET, Track B freshness, binding
        l04 = self.flow.l04
        manifest = backup.create_backup(l04.db, self.root / "pre-v3.db", self.root / "pre-v3.manifest.json",
                                        role="cognitive")
        ROM.migrate(l04.db, backup_manifest=manifest, applied_at="2026-10-26T00:00:01.000000Z")
        l04.policy = CA.MemoryPolicyStore(l04.db, l04.actor, active_capabilities=CAPABILITIES, now_fn=lambda: l04.now)
        l04.consent = CA.ConsentStore(l04.db, l04.actor, policy_store=l04.policy, now_fn=lambda: l04.now)
        l04.rollback = CA.RollbackAuthority(l04.db, l04.actor, l04.consent, now_fn=lambda: l04.now)
        l04.learning = learning_v2.LearningV2Store(
            l04.db, privacy_hold_resolver=self.binding.resolver, containment_ready=lambda: True,
            actor_authority=l04.actor, policy_store=l04.policy, consent_store=l04.consent, now_fn=lambda: l04.now)
        l04.tuple_registry = memory_v2.CanonicalTupleRegistry((l04.registry_policy, ORIGIN_POLICY))
        base_store = l04.store

        def store(**overrides):
            values = dict(capability_provider=lambda capability: capability in CAPABILITIES,
                          family_registry=memory_v2.ProposalFamilyRegistry(
                              (learning_v2.V2_PROPOSAL_FAMILY, learning_v2.V1_PROPOSAL_FAMILY,
                               learning_v2.RELATIONSHIP_ORIGIN_PROPOSAL_FAMILY)),
                          containment_ready=lambda identity: True)
            values.update(overrides)
            return base_store(**values)

        l04.store = store
        self.issuer = FMT.TestBrokerIssuer(self.flow)
        self.fm = self.conversation(self.issuer)

    # ------------------------------------------------------------------------------------------ helpers ---

    def conversation(self, issuer, *, origin=True, binding=None) -> FMC.FirstMemoryConversationV1:
        l04 = self.flow.l04
        return FMC.FirstMemoryConversationV1(
            privacy=binding or self.binding, l04=FMC.L04ComponentsV1(l04.actor, l04.policy, l04.consent, l04.learning),
            adapter=self.flow.make_adapter, reader=self.reader, issuer=issuer, tuple_policy=l04.registry_policy,
            challenge_context=FMT.challenge_context(), now_fn=lambda: T.CHALLENGE_ISSUED,
            origin_policy=ORIGIN_POLICY if origin else None)

    def remember(self, text=ORIGIN, session="sess.a", fm=None):
        fm = fm or self.fm
        offer = fm.offer(session, text)
        self.assertEqual(offer.status, FMC.OFFERED)
        assertion, credential = self.owner_consents(offer)
        return offer, fm.consent(offer.offer_id, session, assertion, credential)

    def table_rows(self) -> dict:
        conn = sqlite3.connect(self.flow.l04.db)
        try:
            names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                                "AND (name LIKE 'memory_%' OR name LIKE 'learning_%' "
                                                "OR name IN ('consent_grant','policy_decision'))")]
            return {name: conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in names}
        finally:
            conn.close()

    def codename_rows(self):
        conn = sqlite3.connect(self.flow.l04.db)
        try:
            return conn.execute(
                "SELECT r.revision_id,r.normalized_value_json,r.value_digest,r.epistemic_basis FROM memory_revision r "
                "JOIN memory_item i ON i.memory_item_id=r.memory_item_id WHERE i.memory_class=? ORDER BY 1",
                (T.L04_CLASS,)).fetchall()
        finally:
            conn.close()

    def forget_origin(self):
        l04 = self.flow.l04
        forget = MA.action_from_fields(
            schema_version=1, actor_ref_id=l04.actor.ACTOR.actor_ref_id, operation=C.FORGET,
            memory_class=MA.RELATIONSHIP_ORIGIN_IDENTITY[0], subject_namespace=MA.RELATIONSHIP_ORIGIN_IDENTITY[1],
            subject_key=MA.RELATIONSHIP_ORIGIN_IDENTITY[2], value_schema=None, payload_digest="0" * 64,
            expected_active_revision_id=None, restore_revision_id=None, purpose=MA.LONG_TERM_OWNER_RELATIONSHIP_ORIGIN_RECALL)
        evidence = l04.actor.issue(action=forget, request_digest="2" * 64, nonce="origin.forget")
        _r, auth, _s = self.privacy.begin_forget(
            action=forget, actor_evidence_ref_id=evidence.actor_evidence_ref_id, intent_ref_id="intent.origin.forget",
            memory_item_id=None, resource_owners=("L04", "L18_V2"), confirmation_event_ref="confirm.origin.forget")
        self.fresh.anchor_and_checkpoint()                                   # Track B: durable before erase
        for owner in (memory_v2.L04PrivacyErasureOwner(l04.db, self.privacy),
                      memory_v2.L18V2PrivacyErasureOwner(l04.db, self.privacy)):
            owner.erase_authorized(auth.authorization_ref_id, auth.execution_nonce)
        self.privacy.complete(auth.authorization_ref_id, auth.execution_nonce)

    # ----------------------------------------------------------------- 1 + 4. one consent, one memory, recall ---

    def test_one_explicit_consent_is_one_admission_recalled_in_a_new_session(self):
        before = self.table_rows()
        offer = self.fm.offer("sess.a", ORIGIN)
        self.assertEqual((offer.status, offer.kind, offer.value, offer.codename),
                         (FMC.OFFERED, "relationship-origin", STATEMENT, None))
        self.assertEqual(self.table_rows(), before)                          # an offer is not memory
        assertion, credential = self.owner_consents(offer)
        result = self.fm.consent(offer.offer_id, "sess.a", assertion, credential)
        self.assertEqual(result.status, FMC.ADMITTED, result)
        after = self.table_rows()
        self.assertEqual(after["memory_admission"], before["memory_admission"] + 1)
        self.assertEqual(after["learning_ro_candidate_v1"], 1)
        self.assertEqual(self.issuer.calls, 1)
        fresh = self.conversation(FMT.TestBrokerIssuer(self.flow))           # new composition, new session
        recalled = fresh.recall("sess.b-new", ASK_ORIGIN)
        self.assertEqual((recalled.status, recalled.kind, recalled.value, recalled.codename),
                         (FMC.RECALLED, "relationship-origin", STATEMENT, None))
        self.assertEqual(fresh.recall("sess.b-new", FMT.ASK).status, FMC.NOTHING_RECALLED)   # no codename stored

    # ---------------------------------------------------------- 2. no consent / wrong purpose: no memory ---

    def test_no_consent_ordinary_text_or_an_unconfigured_kind_writes_nothing(self):
        before = self.table_rows()
        for text in ("our origin is TEST_ONLY", "remember our origin", "remember our origin:   ",
                     "Remember my project origin: TEST_ONLY"):
            self.assertEqual(self.fm.offer("sess.a", text).status, FMC.NOT_A_MEMORY_REQUEST, text)
        with self.assertRaises(FMC.FirstMemoryRefused) as caught:
            self.fm.offer("sess.a", "Remember our origin: TEST_ONLY line one\nline two")
        self.assertEqual(caught.exception.code, "VALUE_REFUSED")
        offer = self.fm.offer("sess.a", ORIGIN)                               # offered, never consented
        forged, credential = self.owner_consents(offer, private=SC.owner_key(SC.TEST_ONLY_ATTACKER_SCALAR))
        refused = self.fm.consent(offer.offer_id, "sess.a", forged, credential)
        self.assertEqual(refused.status, FMC.NOT_ADMITTED)
        codename_only = self.conversation(self.issuer, origin=False)         # the origin kind is not composed
        self.assertEqual(codename_only.offer("sess.a", ORIGIN).status, FMC.NOT_A_MEMORY_REQUEST)
        self.assertEqual(codename_only.recall("sess.a", ASK_ORIGIN).status, FMC.NOT_A_MEMORY_REQUEST)
        self.assertEqual(self.table_rows(), before)
        self.assertEqual(self.fm.recall("sess.b", ASK_ORIGIN).status, FMC.NOTHING_RECALLED)
        with self.assertRaises(FMC.FirstMemoryRefused) as caught:            # a codename tuple posing as origin
            self.conversation(self.issuer).__class__(
                privacy=self.binding, l04=FMC.L04ComponentsV1(self.flow.l04.actor, self.flow.l04.policy,
                                                              self.flow.l04.consent, self.flow.l04.learning),
                adapter=self.flow.make_adapter, reader=self.reader, issuer=self.issuer,
                tuple_policy=self.flow.l04.registry_policy, challenge_context=FMT.challenge_context(),
                origin_policy=self.flow.l04.registry_policy)
        self.assertEqual(caught.exception.code, "TUPLE_NOT_THE_ORIGIN_TUPLE")

    # ------------------------------------------------------------- 3. Privacy refusal and suppression ---

    def test_privacy_not_ready_refuses_and_a_forget_removes_and_suppresses(self):
        _offer, result = self.remember()
        self.assertEqual(result.status, FMC.ADMITTED)
        self.fresh.reboot()                                                  # a new boot, not yet unlocked
        for call in (lambda: self.fm.offer("sess.c", ORIGIN), lambda: self.fm.recall("sess.c", ASK_ORIGIN),
                     lambda: self.fm.recall_authorized("sess.c")):
            with self.assertRaises(FMC.FirstMemoryRefused) as caught:
                call()
            self.assertEqual(caught.exception.code, "PRIVACY_FRESHNESS_NOT_READY:FRESHNESS_MARKER_UNAVAILABLE")
        payload = HMC.context_payload(self.fm, "sess.c")
        self.assertEqual((payload["status"], payload["memories"]), (HMC.UNAVAILABLE, []))
        self.assertIsNone(HMC.render_context_note(payload, include_personal=True))
        self.fresh.unlock()
        self.assertEqual(self.fm.recall("sess.c", ASK_ORIGIN).value, STATEMENT)
        self.forget_origin()
        fm = self.conversation(FMT.TestBrokerIssuer(self.flow))
        self.assertEqual(fm.recall("sess.d", ASK_ORIGIN).status, FMC.NOTHING_RECALLED)
        with self.assertRaises(FMC.FirstMemoryRefused) as caught:            # suppressed: never re-offered
            fm.offer("sess.d", ORIGIN)
        self.assertEqual(caught.exception.code, "IDENTITY_HELD_OR_SUPPRESSED")
        self.assertEqual(HMC.context_payload(fm, "sess.d")["memories"], [])
        self.assertTrue(self.privacy.is_held(*MA.RELATIONSHIP_ORIGIN_IDENTITY))
        self.assertEqual(self.table_rows()["learning_ro_candidate_v1"], 0)
        conn = sqlite3.connect(self.flow.l04.db)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM memory_item WHERE memory_class=?",
                                          (MA.RELATIONSHIP_ORIGIN_IDENTITY[0],)).fetchone()[0], 0)
        finally:
            conn.close()

    # --------------------------------------------------------------------- 5. the codename is unchanged ---

    def test_the_existing_codename_memory_is_unchanged(self):
        _offer, result = self.remember(FMT.REMEMBER)
        self.assertEqual(result.status, FMC.ADMITTED)
        codename = self.codename_rows()
        _offer, result = self.remember(ORIGIN, session="sess.b")
        self.assertEqual(result.status, FMC.ADMITTED)
        self.assertEqual(self.codename_rows(), codename)
        fresh = self.conversation(FMT.TestBrokerIssuer(self.flow))
        self.assertEqual(fresh.recall("sess.c", FMT.ASK).codename, "SYNTH-ORCHID")
        self.assertEqual(fresh.recall("sess.c", ASK_ORIGIN).value, STATEMENT)

    # ---------------------------------------------------------- 6. Hermes context: canonical, not history ---

    def test_hermes_context_reads_canonical_memory_not_chat_history(self):
        self.remember(FMT.REMEMBER)
        self.remember(ORIGIN, session="sess.b")
        hermes = self.root / "hermes"
        hermes.mkdir()
        (hermes / "state.db").write_bytes(b"TEST_ONLY Hermes chat history stand-in")
        before = self.table_rows()
        payload = HMC.context_payload(self.conversation(FMT.TestBrokerIssuer(self.flow)), "hermes.new-session")
        self.assertEqual(payload["status"], HMC.CONTEXT)
        self.assertEqual([(m["kind"], m["value"], m["epistemicBasis"], m["sensitivity"]) for m in payload["memories"]],
                         [("codename", "SYNTH-ORCHID", "USER_ASSERTED", MA.PROJECT_FACT),
                          ("relationship-origin", STATEMENT, "USER_ASSERTED", MA.OWNER_PERSONAL)])
        self.assertTrue(all(m["admissionId"] and m["revisionId"] for m in payload["memories"]))
        shutil.rmtree(hermes)                                                # every chat history gone
        again = HMC.context_payload(self.conversation(FMT.TestBrokerIssuer(self.flow)), "hermes.other-session")
        self.assertEqual(again["memories"], payload["memories"])
        self.assertEqual(self.table_rows(), before)                          # reading wrote nothing
        owner_note = HMC.render_context_note(payload, include_personal=True)
        self.assertIn(STATEMENT, owner_note)
        self.assertIn("separate from this chat's history", owner_note)
        public_note = HMC.render_context_note(payload, include_personal=False)
        self.assertNotIn(STATEMENT, public_note)                             # OWNER_PERSONAL stays on the owner channel
        self.assertIn("SYNTH-ORCHID", public_note)
        for bad in (None, {}, {**payload, "schema": "X"}, {**payload, "status": HMC.UNAVAILABLE},
                    {**payload, "memories": [{**payload["memories"][0], "kind": "persona"}]},
                    {**payload, "memories": payload["memories"] * 2},
                    {**payload, "memories": [{**payload["memories"][1], "value": "x" * 601}]}):
            self.assertIsNone(HMC.render_context_note(bad, include_personal=True))
        with self.assertRaises(TypeError):
            HMC.render_context_note(payload, include_personal="yes")

    # ------------------------------------------------------- 7. no new privilege, purpose or writer ---

    def test_no_unauthorized_privilege_signer_route_or_writer(self):
        self.assertEqual(SIGNER_WIRE.SIGNER_PURPOSES, frozenset({C.LONG_TERM_PERSONAL_PROJECT_RECALL,
                                                                 MA.LONG_TERM_OWNER_RELATIONSHIP_ORIGIN_RECALL}))
        # The signer's own restatement of the family equals the Core API definition.
        self.assertEqual((SIGNER_WIRE.RELATIONSHIP_ORIGIN_PURPOSE, SIGNER_WIRE.RELATIONSHIP_ORIGIN_IDENTITY,
                          SIGNER_WIRE.RELATIONSHIP_ORIGIN_VALUE_SCHEMA),
                         (MA.RELATIONSHIP_ORIGIN.purpose, MA.RELATIONSHIP_ORIGIN.identity,
                          MA.RELATIONSHIP_ORIGIN.value_schema))
        offer = self.fm.offer("sess.a", ORIGIN)
        action = self.fm._pending[offer.offer_id].action
        fields = {"schemaVersion": 1, "actorRefId": action.actor_ref_id, "operation": action.operation,
                  "memoryClass": action.memory_class, "subjectNamespace": action.subject_namespace,
                  "subjectKey": action.subject_key, "valueSchema": action.value_schema,
                  "payloadDigest": action.payload_digest, "expectedActiveRevisionId": None,
                  "restoreRevisionId": None, "purpose": action.purpose}
        assertion, credential = self.owner_consents(offer)
        base = {"challengeId": offer.offer_id, "assertion": dict(assertion), "ownerCredential": dict(credential)}
        parsed = SIGNER_WIRE.parse_issue_request({**base, "action": fields})
        self.assertIsInstance(parsed.action, SIGNER_WIRE.RelationshipOriginActionV1)
        self.assertEqual(parsed.action.action_digest, action.action_digest)
        corrected = SIGNER_WIRE.parse_issue_request(                         # owner-approved correction (FM-3)
            {**base, "action": dict(fields, operation=C.SUPERSEDE, expectedActiveRevisionId="mrev.1")})
        self.assertIsInstance(corrected.action, SIGNER_WIRE.RelationshipOriginActionV1)
        fi = dict(fields, memoryClass=MA.FIRST_INTERACTION_IDENTITY[0], subjectNamespace=MA.FIRST_INTERACTION_IDENTITY[1],
                  subjectKey=MA.FIRST_INTERACTION_IDENTITY[2], valueSchema=MA.FIRST_INTERACTION_VALUE_SCHEMA,
                  purpose=MA.OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION)
        for bad in (fi, dict(fields, purpose="UNKNOWN_PURPOSE"), dict(fields, purpose=["x"]),
                    dict(fields, purpose=C.LONG_TERM_PERSONAL_PROJECT_RECALL),        # origin tuple, codename purpose
                    dict(fields, operation=C.SUPERSEDE),                              # correction without a prior revision
                    dict(fields, operation="RESTORE", valueSchema=None, expectedActiveRevisionId="mrev.1",
                         restoreRevisionId="mrev.0")):
            with self.subTest(bad=bad["purpose"]), self.assertRaises(SIGNER_WIRE.ProtocolError) as caught:
                SIGNER_WIRE.parse_issue_request({**base, "action": bad})
            self.assertEqual(caught.exception.code, "INVALID_ACTION")
        cli = (ROOT / "services/authority-dev/lilith_authority_root/cli.py").read_text(encoding="utf-8")
        self.assertIn('\nFIRST_MEMORY_FORMS = ("remember", "recall")\n', cli)   # the root bridge is unchanged (POSIX)
        self.assertNotIn(MA.CANONICAL_MEMORY_FIRST_INTERACTION_CREATE, CONFIG.ALLOWED_CAPABILITIES)
        import release_file_set as RFS
        self.assertEqual(RFS.SHARED_HASHES["services/core-api/lilith_memory/canonical_contracts.py"],
                         "f93d26d8a7e01d78d25f1f1d9540577cf2a55dfd4d52c4b64c87bef93ad887e0")
        self.assertNotIn("services/core-api/lilith_memory/memory_action_v2.py", RFS.SHARED_HASHES)  # no new member
        # The context adapter has no write path and no import-time canonical runtime; the relay never imports it.
        source = (ROOT / "services/owner-memory-control/lilith_owner_memory/hermes_memory_context.py").read_text()
        top_level = [node for node in ast.parse(source).body if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertTrue(all(not (getattr(n, "module", "") or "").startswith(("lilith_memory", "."))
                            for n in top_level))
        for forbidden in ("offer(", "consent(", "admit(", "sqlite3", "open(", "write"):
            self.assertNotIn(forbidden, source.replace("write path", "").replace("writes", ""), forbidden)
        app = (ROOT / "services/core-api/app.py").read_text(encoding="utf-8")
        self.assertNotIn("hermes_memory_context", app)
        self.assertNotIn("lilith_memory", app)


if __name__ == "__main__":
    unittest.main()
