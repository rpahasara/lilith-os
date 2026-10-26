"""Relationship origin, end to end on the First Memory DEV vertical (TEST_ONLY, synthetic statement, no DEV contact).

The `test_first_memory_dev_vertical` harness unchanged: the real signer core with the DEV runtime wiring reached
through its real frame protocol, the real root bridge on a socket pair, the DEV host composition, the real Privacy store
with the historical F9c2 FORGET and the Track B freshness steps, and the owner-device software authenticator. The only
additions are the reviewed schema-v3 migration on the cognitive DB and a canonical config that names both capabilities.
"""

from __future__ import annotations

import shutil
import unittest
from pathlib import Path

import test_first_memory_dev_vertical as V
from test_first_memory_dev_vertical import HOST, FMC, P, W, X  # noqa: F401  (paths set up by the harness module)

from lilith_memory import backup
from lilith_memory import canonical_contracts as C
from lilith_memory import memory_action_v2 as MA
from lilith_memory import relationship_origin_migration as ROM
from lilith_owner_memory import hermes_memory_context as HMC

ORIGIN = "Remember our origin: TEST_ONLY synthetic origin statement, with a comma."
STATEMENT = "TEST_ONLY synthetic origin statement, with a comma."
ASK_ORIGIN = "What is our origin?"
BOTH = (C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE, MA.CANONICAL_MEMORY_RELATIONSHIP_ORIGIN_CREATE)
ISSUED = ["PREPARE", "CONSUME", "ISSUE", "RESERVE", "CONFIRM"]


@unittest.skipUnless(X.POSIX, "ownership and modes are POSIX")
class RelationshipOriginDevVerticalTests(unittest.TestCase):
    _HARNESS = V.FirstMemoryDevVerticalTests                    # its helpers, without re-running its tests
    copy_db = staticmethod(_HARNESS.copy_db)
    forget_first_interaction = _HARNESS.forget_first_interaction
    register_owner = _HARNESS.register_owner
    set_config = _HARNESS.set_config
    make_core = _HARNESS.make_core
    record_ledger_advance = _HARNESS.record_ledger_advance
    paths = _HARNESS.paths
    host = _HARNESS.host
    owner_signs = _HARNESS.owner_signs
    journal_ops = _HARNESS.journal_ops
    canonical_counts = _HARNESS.canonical_counts
    assertHostRefused = _HARNESS.assertHostRefused

    def setUp(self):
        V.FirstMemoryDevVerticalTests.setUp(self)
        manifest = backup.create_backup(self.cognitive, Path(self.tmp.name) / "pre-v3.db",
                                        Path(self.tmp.name) / "pre-v3.manifest.json", role="cognitive")
        ROM.migrate(self.cognitive, backup_manifest=manifest, applied_at="2026-10-26T00:00:02.000000Z")
        self.set_config(enabled=True, capabilities=BOTH)

    def remember(self, text, session, signer=None):
        offers = []

        def owner(offer):
            offers.append(offer)
            return (signer or self.owner_signs)(offer)

        return HOST.remember(self.host(), session, text, owner), offers

    def test_one_consented_origin_memory_through_the_real_signer_is_recalled_in_a_new_host(self):
        self.register_owner()
        result, offers = self.remember(ORIGIN, "sess.origin")
        self.assertEqual(result["status"], FMC.ADMITTED, result)
        self.assertEqual((offers[0]["kind"], offers[0]["value"], offers[0]["codename"]),
                         ("relationship-origin", STATEMENT, None))
        self.assertEqual(self.journal_ops(), ["GENESIS"] + ISSUED)
        self.assertEqual(self.canonical_counts(), {"memory_admission": 1, "memory_admission_authority_link": 1})
        recalled = HOST.recall(self.host(), "sess.new", ASK_ORIGIN)
        self.assertEqual((recalled["status"], recalled["kind"], recalled["value"]),
                         (FMC.RECALLED, "relationship-origin", STATEMENT), recalled)
        context = HOST.recall(self.host(), "hermes.new", HMC.CONTEXT_REQUEST)
        self.assertEqual([(m["kind"], m["value"]) for m in context["memories"]], [("relationship-origin", STATEMENT)])
        shutil.rmtree(self.hermes)                                          # chat history gone; canonical unchanged
        self.assertEqual(HOST.recall(self.host(), "hermes.other", HMC.CONTEXT_REQUEST)["memories"],
                         context["memories"])
        self.assertEqual(self.journal_ops(), ["GENESIS"] + ISSUED)          # reads journal nothing

    def test_origin_creation_needs_its_own_capability_and_explicit_consent(self):
        self.register_owner()
        self.set_config(enabled=True, capabilities=(C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE,))
        self.assertHostRefused(lambda: self.remember(ORIGIN, "sess.a"), "MEMORY_CREATION_NOT_AUTHORIZED")
        self.set_config(enabled=True, capabilities=BOTH)

        def declines(offer):
            raise FMC.FirstMemoryRefused("OWNER_DECLINED")

        self.assertHostRefused(lambda: self.remember(ORIGIN, "sess.b", signer=declines), "OWNER_DECLINED")
        self.assertEqual(self.journal_ops(), ["GENESIS"])
        self.assertEqual(self.canonical_counts()["memory_admission"], 0)
        self.assertEqual(HOST.recall(self.host(), "sess.c", ASK_ORIGIN)["status"], FMC.NOTHING_RECALLED)

    def test_the_codename_memory_is_unchanged_and_both_are_recalled(self):
        self.register_owner()
        self.assertEqual(self.remember(V.REMEMBER, "sess.codename")[0]["status"], FMC.ADMITTED)
        before = HOST.recall(self.host(), "sess.x", V.ASK)
        self.assertEqual(self.remember(ORIGIN, "sess.origin")[0]["status"], FMC.ADMITTED)
        self.assertEqual(HOST.recall(self.host(), "sess.y", V.ASK), before)
        self.assertEqual(self.journal_ops(), ["GENESIS"] + ISSUED + ISSUED)
        context = HOST.recall(self.host(), "hermes.new", HMC.CONTEXT_REQUEST)
        self.assertEqual([(m["kind"], m["value"]) for m in context["memories"]],
                         [("codename", "SYNTH-ORCHID"), ("relationship-origin", STATEMENT)])

    def test_privacy_not_ready_refuses_and_the_context_fails_closed(self):
        self.register_owner()
        self.assertEqual(self.remember(ORIGIN, "sess.a")[0]["status"], FMC.ADMITTED)
        self.fresh.reboot()
        self.assertHostRefused(lambda: HOST.recall(self.host(), "sess.b", ASK_ORIGIN),
                               "PRIVACY_FRESHNESS_NOT_READY:FRESHNESS_MARKER_UNAVAILABLE")
        context = HOST.recall(self.host(), "hermes.b", HMC.CONTEXT_REQUEST)
        self.assertEqual((context["status"], context["memories"]), (HMC.UNAVAILABLE, []))
        self.assertTrue(context["reason"].startswith("PRIVACY_FRESHNESS_NOT_READY"))

    def test_the_signer_refuses_the_first_interaction_purpose(self):
        fields = {"schemaVersion": 1, "actorRefId": "actor.local-owner.v1", "operation": C.CREATE,
                  "memoryClass": MA.FIRST_INTERACTION_IDENTITY[0], "subjectNamespace": MA.FIRST_INTERACTION_IDENTITY[1],
                  "subjectKey": MA.FIRST_INTERACTION_IDENTITY[2], "valueSchema": MA.FIRST_INTERACTION_VALUE_SCHEMA,
                  "payloadDigest": "0" * 64, "expectedActiveRevisionId": None, "restoreRevisionId": None,
                  "purpose": MA.OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION}
        with self.assertRaises(W.ProtocolError) as caught:
            W.parse_issue_request({"challengeId": "och.x", "action": fields, "assertion": {}, "ownerCredential": {}})
        self.assertEqual(caught.exception.code, "INVALID_ACTION")
        self.assertEqual(self.journal_ops(), ["GENESIS"])


if __name__ == "__main__":
    unittest.main()
