"""Relationship origin: the owner-directed DEV FORGET tool on the First Memory DEV vertical (TEST_ONLY, synthetic).

The `test_relationship_origin_dev_vertical` harness unchanged (the real signer core and root bridge, the DEV host
composition, schema v3, the real Privacy store with the historical F9c2 FORGET and the Track B freshness steps). The
tool composes the merged origin FORGET profile, the hold-first intent and the durability barrier; the root hold is
simulated by holder = this process (the executor's own hold is proven in the staged executor tests), the gateway by a
stopped fake. Nothing contacts DEV.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
for _path in (ROOT / "services/authority-dev/tests",):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import test_first_memory_dev_vertical as V  # noqa: E402
import test_relationship_origin_dev_vertical as RV  # noqa: E402
from test_first_memory_dev_vertical import FMC, HOST  # noqa: E402

import relationship_origin_forget_dev as TOOL  # noqa: E402
from lilith_memory import canonical_authority as CA  # noqa: E402
from lilith_memory import memory_action_v2 as MA  # noqa: E402
from lilith_memory import privacy_forget_intent as I  # noqa: E402
from lilith_memory import privacy_forget_runner as R  # noqa: E402
from lilith_memory import privacy_governance as PG  # noqa: E402


class StoppedGateway:
    def stopped(self) -> bool:
        return True


@unittest.skipUnless(V.X.POSIX, "ownership and modes are POSIX")
class OriginForgetDevTests(unittest.TestCase):
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
    remember = RV.RelationshipOriginDevVerticalTests.remember

    def setUp(self):
        RV.RelationshipOriginDevVerticalTests.setUp(self)        # harness, schema v3, both capabilities named
        self.intent_dir = self.fresh.intent_dir
        self.intent_dir.mkdir(exist_ok=True)

    def intents(self, profile=TOOL.PROFILE):
        return I.ForgetIntentStore(self.intent_dir, holder_uid=os.getuid(), profile=profile)

    def tool(self):
        return TOOL.OriginForgetDevV1(paths=self.paths(), freshness=self.fresh.gate(), intents=self.intents(),
                                      gateway=StoppedGateway(), hold_timeout_seconds=0.0)

    def privacy(self):
        actor = CA.LocalOwnerAuthority(self.cognitive, self.actor_secret.read_bytes())
        return PG.PrivacyGovernanceStore(self.privacy_db, self.privacy_secret.read_bytes(), actor)

    def refused(self, code, call, *args):
        with self.assertRaises((TOOL.OriginForgetRefused, FMC.FirstMemoryRefused, I.ForgetIntentError)) as caught:
            call(*args)
        self.assertEqual(caught.exception.code, code)

    def admit_both(self):
        self.register_owner()
        self.assertEqual(self.remember(V.REMEMBER, "sess.codename")[0]["status"], FMC.ADMITTED)
        self.assertEqual(self.remember(RV.ORIGIN, "sess.origin")[0]["status"], FMC.ADMITTED)
        self.set_config(enabled=False)                                   # creation DISABLED again, as on DEV

    def test_origin_forget_is_durable_before_erase_and_erases_and_suppresses_only_the_origin(self):
        self.admit_both()
        codename = HOST.recall(self.host(), "sess.before", V.ASK)
        self.assertEqual(codename["status"], FMC.RECALLED)
        status = self.tool().status()
        self.assertEqual((status["intent"], status["inFlight"], status["completed"], status["freshness"]),
                         (I.ABSENT, False, False, "READY"))
        rows = status["originRows"]
        self.assertGreater(rows, 0)

        first = self.tool().forget("owner-go.origin.1")
        self.assertEqual(first["status"], R.INCOMPLETE_HOLD_ACTIVE, first)
        self.assertTrue(first["failure"].startswith("DURABILITY_BARRIER:"), first)
        self.assertEqual(self.tool().origin_rows(), rows)                   # nothing erased before durability
        self.assertHostRefused(lambda: HOST.recall(self.host(), "sess.mid", RV.ASK_ORIGIN),
                               "PRIVACY_FRESHNESS_NOT_READY:FORGET_INTENT_PENDING")

        self.fresh.anchor_and_checkpoint()                                  # witness advance + owner K-PCK checkpoint
        done = self.tool().resume()
        self.assertEqual((done["status"], done["completedOwners"]), (R.COMPLETE, ["L04", "L18_V2"]), done)
        status = self.tool().status()
        self.assertEqual((status["originRows"], status["completed"], status["inFlight"]), (0, True, False))
        self.assertEqual(status["intent"], I.HELD)                          # only root releases it

        (self.intent_dir / "relationship-origin.intent").unlink()            # the executor's reconcile, simulated
        self.assertEqual(HOST.recall(self.host(), "sess.after", RV.ASK_ORIGIN)["status"], FMC.NOTHING_RECALLED)
        self.assertEqual(HOST.recall(self.host(), "sess.after", V.ASK), codename)
        privacy = self.privacy()
        self.assertTrue(privacy.suppression_matches(MA.RELATIONSHIP_ORIGIN_IDENTITY))
        self.assertTrue(privacy.suppression_matches(MA.FIRST_INTERACTION_IDENTITY))  # the F9c2 FORGET intact
        self.refused("ORIGIN_ALREADY_FORGOTTEN", self.tool().forget, "owner-go.origin.2")

    def test_refusals_hold_nothing(self):
        self.register_owner()
        self.refused("OWNER_APPROVAL_REF_INVALID", self.tool().forget, "owner go")
        self.refused("ORIGIN_MEMORY_ABSENT", self.tool().forget, "owner-go.a")      # nothing admitted yet
        self.assertEqual(self.remember(RV.ORIGIN, "sess.origin")[0]["status"], FMC.ADMITTED)
        actor = CA.LocalOwnerAuthority(self.cognitive, self.actor_secret.read_bytes())
        actor.issue(action=R.forget_action(TOOL.PROFILE, actor.ACTOR.actor_ref_id), request_digest="2" * 64,
                    nonce="origin-forget-dev.owner-go.used", ttl_seconds=300)
        self.refused("OWNER_APPROVAL_REF_ALREADY_USED", self.tool().forget, "owner-go.used")
        self.intents(R.FIRST_INTERACTION_FORGET).record(intent_ref_id="intent.fi", actor_ref_id="actor.x")
        self.refused("FORGET_INTENT_PENDING_OTHER_IDENTITY", self.tool().forget, "owner-go.b")
        (self.intent_dir / "first-interaction.intent").unlink()
        self.fresh.reboot()                                                 # Privacy not READY for this boot
        self.refused("PRIVACY_FRESHNESS_NOT_READY:FRESHNESS_MARKER_UNAVAILABLE", self.tool().forget, "owner-go.c")
        self.assertEqual(self.intents().state(), I.ABSENT)
        self.assertIsNone(self.privacy().in_flight_authorization(MA.RELATIONSHIP_ORIGIN_IDENTITY))
        self.assertFalse(self.privacy().suppression_matches(MA.RELATIONSHIP_ORIGIN_IDENTITY))

    def test_main_refuses_root_and_any_other_form(self):
        with mock.patch.object(TOOL.HOST, "unprivileged_reason", return_value="HOST_HAS_ROOT_IDENTITY"):
            self.assertEqual(TOOL.main(["status"]), 2)
        for argv in ([], ["forget"], ["forget", "--owner-approval"], ["erase", "--owner-approval", "x"]):
            with self.subTest(argv=argv):
                self.assertEqual(TOOL.main(argv), 2)

    def test_the_tool_never_names_hermes_or_first_interaction_owners(self):
        source = (ROOT / "services/owner-memory-control/tools/relationship_origin_forget_dev.py").read_text(
            encoding="utf-8")
        for needle in ("hermes_erasure_owner", "HermesConversationErasureOwner", "FIRST_INTERACTION_FORGET",
                       "first_interaction_forget_action", "capture_evidence_path", "unlink(", "rmtree"):
            self.assertNotIn(needle, source, needle)


if __name__ == "__main__":
    unittest.main()
