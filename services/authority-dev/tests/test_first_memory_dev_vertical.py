"""First Memory DEV vertical slice, end to end (TEST_ONLY, synthetic credentials, no provider, no DEV contact).

Everything below is the real code path the DEV host will run, with only the host boundary replaced:

- the real authority signer core with the DEV runtime wiring (`dev_runtime_profile`, the per-request owner
  registration, the RR-39 governed issuance and the evidence-use transport), on a synthetic PR-1 host (K-ROOT
  registry, witness chain, durable ledger, RELEASED governing hold), reached through its real frame protocol;
- the root bridge (`lilith_authority_root.cli.serve_bridge`, which adds root's own hold snapshot) on a real socket
  pair to the unprivileged host's `BridgeTransportV1`;
- the First Memory DEV host (`tools/first_memory_dev_host.py`) composing `first_memory_conversation` with the L04 V2
  adapter and accepted read on a canonical-migrated L04 DB whose admission link was installed by the reviewed
  migration tool (`tools/first_memory_l04_migration.py`);
- the real Privacy store with the historical First Interaction FORGET and the real Track B freshness steps;
- the owner-device software authenticator and its registration (`tools/first_memory_owner_credential_dev.py`).
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _path in (ROOT / "services/owner-memory-control/tests", ROOT / "services/owner-memory-control/tools",
              ROOT / "services/core-api/tests", ROOT / "services/owner-memory-control", ROOT / "services/core-api",
              ROOT / "services/authority-dev", HERE):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import first_memory_dev_host as HOST  # noqa: E402
import first_memory_l04_migration as MIGRATION  # noqa: E402
import first_memory_owner_credential_dev as OWNER  # noqa: E402
import pr1s_fixtures as X  # noqa: E402
import synthetic_b1b3b as T  # noqa: E402
import test_rr39_issuance as RR39  # noqa: E402
from privacy_freshness_fixture import FreshnessHarness  # noqa: E402
from lilith_authority_dev import core as CORE  # noqa: E402
from lilith_authority_dev import credential as CRED  # noqa: E402
from lilith_authority_dev import issuance as ISS  # noqa: E402
from lilith_authority_dev import protocol as W  # noqa: E402
from lilith_authority_dev import server as SERVER  # noqa: E402
from lilith_authority_dev import state as STATE  # noqa: E402
from lilith_authority_dev.profile import dev_runtime_profile  # noqa: E402
from lilith_authority_host import inputs as HI  # noqa: E402
from lilith_authority_host import paths as P  # noqa: E402
from lilith_authority_root import cli as ROOT_CLI  # noqa: E402
from lilith_memory import canonical_contracts as C  # noqa: E402
from lilith_memory import learning_v2  # noqa: E402
from lilith_memory import memory_v2  # noqa: E402
from lilith_memory import privacy_forget_runner as FR  # noqa: E402
from lilith_memory import privacy_governance as PG  # noqa: E402
from lilith_memory import slice15b2a_migration  # noqa: E402
from lilith_owner_memory import first_memory_conversation as FMC  # noqa: E402

DEV = "dev"
NOW = datetime(2026, 9, 27, 12, 0, 0, tzinfo=timezone.utc)
TEST_ONLY_PRIVACY_SECRET = b"TEST_ONLY first-memory DEV vertical privacy secret"
REMEMBER = "Remember my project codename is SYNTH-ORCHID"
ASK = "What is my project codename?"
RELEASE_SHA = "1" * 40                                       # TEST stand-in for the accepted signer release


class RootBridgeHarness:
    """The real root bridge on a real socket pair; only the signer socket itself is replaced by in-process frames.
    `hold` is root's own hold-store read (the synthetic host's genuine store)."""

    def __init__(self, case):
        self.case = case
        self.frames = []
        self.hold = case.signer.released_snapshot
        server, client = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        self.client = HOST.BridgeTransportV1(client)
        self._sockets = (server, client)
        self._thread = threading.Thread(target=ROOT_CLI.serve_bridge, args=(server,), kwargs=dict(
            hold_snapshot=lambda: self.hold(), exchange=self.exchange, max_requests=10_000), daemon=True)
        self._thread.start()

    def exchange(self, frame):
        message = W.parse_frame(frame)
        self.frames.append(message.operation)
        result = self.case.core.dispatch(message)
        return json.loads(W.encode_response(result)[4:])["payload"]

    def close(self):
        for conn in self._sockets:
            conn.close()
        self._thread.join(5)

    def issue(self, payload):
        return self.client.issue(payload)

    def use(self, operation, payload):
        return self.client.use(operation, payload)


@unittest.skipUnless(X.POSIX, "ownership and modes are POSIX")
class FirstMemoryDevVerticalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        # ---- signer host (K-ROOT registry, witness chain, ledger, custody) -----------------------------------
        self.signer = RR39.DevHost(base / "host").genesis_host()
        self.credentials = base / "credentials"
        self.credentials.mkdir(mode=0o700)
        RR39.write_credential(self.credentials, RR39.PB.private(RR39.K_ACT))
        self.core = self.make_core()
        # ---- owner device: a software authenticator; only its PUBLIC record leaves the device --------------
        self.device = base / "owner-device"
        self.device.mkdir(mode=0o700)
        OWNER.create(self.device / "owner.key", self.device / "owner.public.json", now=NOW)
        self.public = json.loads((self.device / "owner.public.json").read_bytes())
        # ---- L04 (canonical-migrated) + the reviewed link migration ------------------------------------------
        self.l04 = T.L04Harness()
        self.addCleanup(self.l04.close)
        self.cognitive = self.l04.db
        backups = base / "backups"
        backups.mkdir()
        self.assertEqual(MIGRATION.plan(self.cognitive)["state"], MIGRATION.LINK_ABSENT)
        applied = MIGRATION.apply(self.cognitive, backups)
        self.assertEqual((applied["mutation"], applied["linkRows"]), ("LINK_TABLE_CREATED", 0))
        # ---- Privacy: the authoritative store, the F9c2 FORGET, the Track B freshness steps -----------------
        self.drill = base / "f9-drill"
        self.drill.mkdir()
        self.privacy_db = self.drill / "privacy_governance.f9drill.db"
        self.stale = base / "data" / "privacy_governance.dev.db"
        self.stale.parent.mkdir()
        slice15b2a_migration.migrate_privacy(self.privacy_db, applied_at="2026-10-26T00:00:00.000000Z")
        privacy = PG.PrivacyGovernanceStore(self.privacy_db, TEST_ONLY_PRIVACY_SECRET, self.l04.actor)
        self.pre_forget = base / "privacy.pre-forget.copy.db"
        self.copy_db(self.privacy_db, self.pre_forget)
        self.forget_first_interaction(privacy)
        self.fresh = FreshnessHarness(base, self.privacy_db)
        self.fresh.genesis()
        self.actor_secret = self.drill / "actor-authority.f9drill.key"
        self.actor_secret.write_bytes(T.TEST_ONLY_V1_ACTOR_HMAC_SECRET)
        self.privacy_secret = self.drill / "privacy-authority.f9drill.key"
        self.privacy_secret.write_bytes(TEST_ONLY_PRIVACY_SECRET)
        self.config = base / "first-memory-dev" / "canonical-config.json"
        self.config.parent.mkdir()
        self.set_config(enabled=True)
        self.hermes = base / "hermes"
        self.hermes.mkdir()
        (self.hermes / "state.db").write_bytes(b"TEST_ONLY Hermes conversation history stand-in")
        self.transport = RootBridgeHarness(self)
        self.addCleanup(self.transport.close)

    # ------------------------------------------------------------------------------------------ helpers ---

    @staticmethod
    def copy_db(source, target):
        src, dst = sqlite3.connect(source), sqlite3.connect(target)
        try:
            src.backup(dst)
        finally:
            src.close()
            dst.close()

    def forget_first_interaction(self, privacy):
        action = FR.first_interaction_forget_action(self.l04.actor.ACTOR.actor_ref_id)
        evidence = self.l04.actor.issue(action=action, request_digest="1" * 64, nonce="f9c2.historical")
        _r, auth, _s = privacy.begin_forget(
            action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id, intent_ref_id="intent.f9c2",
            memory_item_id=None, resource_owners=("L04", "L18_V2"), confirmation_event_ref="confirm.f9c2")
        for owner in (memory_v2.L04PrivacyErasureOwner(self.l04.db, privacy),
                      memory_v2.L18V2PrivacyErasureOwner(self.l04.db, privacy)):
            owner.erase_authorized(auth.authorization_ref_id, auth.execution_nonce)
        privacy.complete(auth.authorization_ref_id, auth.execution_nonce)

    def register_owner(self, *publics):
        document = OWNER.registration_document(list(publics or (self.public,)), release_sha=RELEASE_SHA)
        self.signer.document(P.OWNER_REGISTRATION, document)
        os.chmod(self.signer.path(P.OWNER_REGISTRATION_DIR), 0o755)
        return document

    def set_config(self, *, enabled, capabilities=(C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE,)):
        self.config.write_text(json.dumps({"schemaVersion": 1, "canonicalLtmEnabled": enabled,
                                           "activeCapabilities": list(capabilities)}), encoding="utf-8")

    def make_core(self):
        """`server.build_core`'s DEV wiring, at the synthetic host's root (the only difference: TEST paths)."""
        handler = ISS.IssuanceHandlerV1(
            profile=dev_runtime_profile(),
            view=lambda: STATE.signer_view(environment=DEV, root=self.signer.root, owner_uid=X.UID),
            open_ledger=self.signer.ledger,
            load_signing_key=lambda: CRED.load_owner_actor_signing_key(str(self.credentials),
                                                                       expected_directory=str(self.credentials)),
            record_ledger_advance=self.record_ledger_advance,
            registration=lambda: HI.read_owner_registration(environment=DEV, root=self.signer.root, owner_uid=X.UID),
            now_fn=lambda: NOW)
        status = CRED.CredentialStatusV1(CRED.CREDENTIAL_PRESENT_UNVERIFIED, "ab" * 32)
        return CORE.DevAuthoritySignerCoreV1(status, issuance=handler)

    def record_ledger_advance(self, previous, sequence, head):
        self.signer.writer().record_ledger_advance(previous_witness_digest=previous, ledger_sequence=sequence,
                                                   ledger_head=head, context=self.signer.context(),
                                                   updated_at="2026-09-27T12:00:40Z")
        return {"status": "OK"}

    def paths(self, **overrides):
        values = dict(privacy_db=self.privacy_db, authoritative_privacy_db=self.privacy_db,
                      stale_privacy_db=self.stale, cognitive_db=self.cognitive, actor_secret=self.actor_secret,
                      privacy_secret=self.privacy_secret, canonical_config=self.config, host_root=self.signer.root,
                      host_owner_uid=X.UID)
        values.update(overrides)
        return HOST.HostPathsV1(**values)

    def host(self, **paths):
        """A FRESH host process: nothing is carried over but the files on disk."""
        return HOST.FirstMemoryDevHostV1(transport=self.transport, paths=self.paths(**paths),
                                         freshness=self.fresh.gate(), now_fn=lambda: NOW)

    def owner_signs(self, offer, key=None):
        assertion = OWNER.sign_assertion(OWNER.load_private(key or self.device / "owner.key"),
                                         self.public["credential"], bytes.fromhex(offer["webauthnChallenge"]))
        return {"assertion": assertion, "credentialRecordId": self.public["credential"]["recordId"]}

    def journal_ops(self):
        ledger = self.signer.ledger()
        try:
            return [op["op"] for op in ledger.journal()]
        finally:
            ledger.close()

    def canonical_counts(self):
        conn = sqlite3.connect(self.cognitive)
        try:
            return {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in ("memory_admission", "memory_admission_authority_link")}
        finally:
            conn.close()

    def remember(self, host=None, session="sess.a", signer=None):
        offers = []

        def owner(offer):
            offers.append(offer)
            return (signer or self.owner_signs)(offer)

        result = HOST.remember(host or self.host(), session, REMEMBER, owner)
        return result, offers

    def assertHostRefused(self, call, code):
        with self.assertRaises((HOST.HostRefused, FMC.FirstMemoryRefused)) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    # --------------------------------------------------------------------------- 1. no owner, no consent ---

    def test_without_a_registered_owner_nothing_is_admitted(self):
        self.assertHostRefused(lambda: self.remember(), HI.OWNER_REGISTRATION_MISSING)
        self.assertEqual(self.transport.frames, [])
        # and the signer itself re-reads the registration per request: withdrawn after the offer, it refuses
        self.register_owner()

        def withdrawn(offer):
            self.signer.path(P.OWNER_REGISTRATION).unlink()
            return self.owner_signs(offer)

        result, _ = self.remember(signer=withdrawn)
        self.assertEqual((result["status"], result["reason"]),
                         (FMC.NOT_ADMITTED, "SIGNER_REFUSED:" + HI.OWNER_REGISTRATION_MISSING))
        self.assertEqual(self.journal_ops(), ["GENESIS"])
        self.assertEqual(self.canonical_counts(), {"memory_admission": 0, "memory_admission_authority_link": 0})

    def test_without_consent_or_with_a_foreign_authenticator_nothing_is_admitted(self):
        self.register_owner()
        def declines(offer):
            raise FMC.FirstMemoryRefused("OWNER_DECLINED")                  # offered, never consented

        self.assertHostRefused(lambda: self.remember(signer=declines), "OWNER_DECLINED")
        self.assertEqual(self.journal_ops(), ["GENESIS"])
        self.assertEqual(self.canonical_counts()["memory_admission"], 0)
        intruder = Path(self.tmp.name) / "intruder"
        intruder.mkdir()
        OWNER.create(intruder / "k", intruder / "p.json", now=NOW)
        result, _ = self.remember(signer=lambda offer: self.owner_signs(offer, key=intruder / "k"))
        self.assertEqual((result["status"], result["reason"]),
                         (FMC.NOT_ADMITTED, "SIGNER_REFUSED:OWNER_PROOF_REJECTED:OWNER_SIGNATURE_INVALID"))
        self.assertEqual(self.journal_ops(), ["GENESIS"])
        self.assertEqual(self.canonical_counts()["memory_admission"], 0)
        self.assertEqual(HOST.recall(self.host(), "sess.b", ASK)["status"], FMC.NOTHING_RECALLED)

    def test_memory_creation_stays_disabled_until_the_owner_enables_it(self):
        self.register_owner()
        self.set_config(enabled=False)
        self.assertHostRefused(lambda: self.remember(), "MEMORY_CREATION_NOT_AUTHORIZED")
        self.set_config(enabled=True, capabilities=())
        self.assertHostRefused(lambda: self.remember(), "MEMORY_CREATION_NOT_AUTHORIZED")
        self.config.unlink()
        self.assertHostRefused(lambda: self.remember(), "MEMORY_CREATION_NOT_AUTHORIZED")
        self.assertEqual(self.transport.frames, [])
        self.assertEqual(self.journal_ops(), ["GENESIS"])

    # ------------------------------------------------- 2-4. exactly one memory, recalled from canonical storage ---

    def test_one_owner_authorized_memory_is_admitted_and_recalled_in_a_new_session(self):
        self.register_owner()
        result, offers = self.remember(session="sess.a")
        self.assertEqual(result["status"], FMC.ADMITTED, result)
        self.assertEqual(offers[0]["codename"], "SYNTH-ORCHID")
        self.assertEqual(self.journal_ops(), ["GENESIS", "PREPARE", "CONSUME", "ISSUE", "RESERVE", "CONFIRM"])
        self.assertEqual(self.canonical_counts(), {"memory_admission": 1, "memory_admission_authority_link": 1})
        # 3. a fresh session and a fresh runtime composition read it from canonical storage
        recalled = HOST.recall(self.host(), "sess.b-new", ASK)
        self.assertEqual((recalled["status"], recalled["codename"]), (FMC.RECALLED, "SYNTH-ORCHID"), recalled)
        # 4. with every conversation history gone, canonical recall is unchanged
        shutil.rmtree(self.hermes)
        recalled = HOST.recall(self.host(), "sess.c-after-history-removal", ASK)
        self.assertEqual((recalled["status"], recalled["codename"]), (FMC.RECALLED, "SYNTH-ORCHID"))
        # the authority-side use record is exactly this admission's
        evidence_id = self.issued_evidence_id()
        use = HOST.SignerEvidenceUseLedgerV1(self.transport).lookup(evidence_id)
        self.assertEqual(use["state"], "CONSUMED")

    def issued_evidence_id(self):
        ledger = self.signer.ledger()
        try:
            return next(op["evidenceId"] for op in ledger.journal() if op["op"] == "ISSUE")
        finally:
            ledger.close()

    # ---------------------------------------------------------------------- 5. explicit refusals ---

    def test_wrong_boot_stale_privacy_and_the_old_db_path_refuse_explicitly(self):
        self.register_owner()
        self.assertEqual(self.remember()[0]["status"], FMC.ADMITTED)
        self.fresh.reboot()                                                 # a new boot, not yet unlocked
        self.assertHostRefused(lambda: HOST.recall(self.host(), "sess.d", ASK),
                               "PRIVACY_FRESHNESS_NOT_READY:FRESHNESS_MARKER_UNAVAILABLE")
        self.assertHostRefused(lambda: self.remember(session="sess.d"),
                               "PRIVACY_FRESHNESS_NOT_READY:FRESHNESS_MARKER_UNAVAILABLE")
        self.fresh.unlock()
        self.assertEqual(HOST.recall(self.host(), "sess.d", ASK)["codename"], "SYNTH-ORCHID")
        self.assertHostRefused(lambda: self.host(privacy_db=self.stale).compose(), "PRIVACY_DB_NOT_AUTHORITATIVE")
        self.stale.write_bytes(b"")                                         # the old Core API path reappears
        self.assertHostRefused(lambda: HOST.recall(self.host(), "sess.e", ASK), "STALE_PRIVACY_PATH_PRESENT")
        self.stale.unlink()
        self.copy_db(self.pre_forget, self.privacy_db)                      # a restored, pre-FORGET store
        self.assertHostRefused(lambda: HOST.recall(self.host(), "sess.f", ASK),
                               "PRIVACY_FRESHNESS_NOT_READY:OLDER_THAN_ANCHOR")

    def test_replayed_proof_evidence_and_use_are_refused(self):
        self.register_owner()
        captured = {}

        def owner(offer):
            captured["first"] = self.owner_signs(offer)
            return captured["first"]

        result, _ = self.remember(signer=owner)
        self.assertEqual(result["status"], FMC.ADMITTED)
        # the same owner assertion for a new offer: it signs another challenge
        replay, _ = self.remember(session="sess.r", signer=lambda offer: captured["first"])
        self.assertEqual((replay["status"], replay["reason"]),
                         (FMC.NOT_ADMITTED, "SIGNER_REFUSED:OWNER_PROOF_REJECTED:OWNER_SIGNATURE_INVALID"))
        # a second RESERVE of the consumed evidence, and a CONFIRM of a non-reserved use
        uses = HOST.SignerEvidenceUseLedgerV1(self.transport)
        evidence_id = self.issued_evidence_id()
        record = uses.lookup(evidence_id)
        again = uses.reserve(evidence_id=evidence_id, evidence_digest=record["evidenceDigest"],
                             challenge_id=record["challengeId"], proposal_ref_id="proposal.replay",
                             action_digest=record["actionDigest"])
        self.assertEqual(again.status, "REFUSED")
        self.assertIn("EVIDENCE_ALREADY_USED", str(self.core.dispatch(W.parse_frame(W.encode_frame(
            W.RESERVE_EVIDENCE_USE, {"evidenceId": evidence_id, "evidenceDigest": record["evidenceDigest"],
                                     "challengeId": record["challengeId"], "proposalRefId": "proposal.replay",
                                     "actionDigest": record["actionDigest"],
                                     "holdStore": self.signer.released_snapshot()})))))
        self.assertEqual(uses.confirm(evidence_id=evidence_id, proposal_ref_id="proposal.replay",
                                      admission_id="adm.x", revision_id="rev.x").status, "REFUSED")
        self.assertEqual(self.canonical_counts(), {"memory_admission": 1, "memory_admission_authority_link": 1})
        self.assertEqual(self.journal_ops(), ["GENESIS", "PREPARE", "CONSUME", "ISSUE", "RESERVE", "CONFIRM"])

    def test_an_unregistered_credential_and_a_held_custody_refuse(self):
        self.register_owner()
        self.assertHostRefused(lambda: self.remember(
            signer=lambda offer: {**self.owner_signs(offer), "credentialRecordId": "ocred.x"}),
            "OWNER_CREDENTIAL_NOT_REGISTERED")
        self.assertEqual(self.journal_ops(), ["GENESIS"])
        held = self.signer.released_snapshot(state=RR39.SC.HELD)
        self.transport.hold = lambda: held
        result, _ = self.remember()
        self.assertEqual(result["status"], FMC.NOT_ADMITTED)
        self.assertTrue(result["reason"].startswith("SIGNER_REFUSED:HOLD_NOT_RELEASED_FOR_ISSUANCE"), result)
        self.assertEqual(self.journal_ops(), ["GENESIS"])

    # ------------------------------------------------------------- 6. the historical FORGET stays enforced ---

    def test_the_historical_first_interaction_forget_stays_enforced(self):
        self.register_owner()
        composed = self.host().compose()
        self.assertTrue(composed.conversation._privacy.resolver.is_held(*FR.IDENTITY))
        self.assertNotEqual(HOST.GOVERNED_TUPLE.identity, tuple(FR.IDENTITY))
        fi = memory_v2.MemoryTuplePolicyV1(
            memory_class=FR.IDENTITY[0], subject_namespace=FR.IDENTITY[1], subject_key=FR.IDENTITY[2],
            value_schema=learning_v2.VALUE_SCHEMA, capability=C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE,
            read_allowed=True, write_allowed=True)
        with self.assertRaises(FMC.FirstMemoryRefused) as caught:
            FMC.FirstMemoryConversationV1(privacy=composed.conversation._privacy, l04=composed.conversation._l04,
                                          adapter=composed.conversation._adapter,
                                          reader=composed.conversation._reader,
                                          issuer=composed.conversation._issuer, tuple_policy=fi,
                                          challenge_context=composed.conversation._context)
        self.assertEqual(caught.exception.code, "FIRST_INTERACTION_IDENTITY_SUPPRESSED")

    # ------------------------------------------------- 7. signer recovery and refusal boundaries intact ---

    def test_signer_boundaries_remain_intact(self):
        dev_core = SERVER.build_core(CRED.CredentialStatusV1(CRED.CREDENTIAL_PRESENT_UNVERIFIED, "ab" * 32))
        health = dev_core.dispatch(W.parse_frame(W.encode_frame(W.HEALTH, {})))["health"]
        self.assertEqual((health["signing"], health["readiness"]), ("SIGNING_NOT_AVAILABLE", "NOT_READY"))
        self.assertIn("ISSUANCE_UNWIRED", health["reasons"])                # self-view never claims readiness
        bare = CORE.DevAuthoritySignerCoreV1(CRED.CredentialStatusV1(CRED.CREDENTIAL_PRESENT_UNVERIFIED, "ab" * 32))
        for operation, payload in ((W.LOOKUP_EVIDENCE_USE, {"evidenceId": "aev.x"}),
                                   (W.RECOVERY_VOID_CHALLENGE, {"holdStore": {}})):
            self.assertIn(bare.dispatch(W.parse_frame(W.encode_frame(operation, payload)))["reason"],
                          ("EVIDENCE_USE_NOT_WIRED", "RECOVERY_NOT_WIRED"))
        self.assertEqual(self.core.dispatch(W.parse_frame(W.encode_frame(W.RESERVE_EVIDENCE_USE, {
            "evidenceId": "aev.x", "evidenceDigest": "0" * 64, "challengeId": "och.x", "proposalRefId": "p.x",
            "actionDigest": "0" * 64, "holdStore": self.signer.released_snapshot()})))["reason"],
            "EVIDENCE_NOT_ISSUED_HERE")
        self.assertEqual(self.journal_ops(), ["GENESIS"])


if __name__ == "__main__":
    unittest.main()
