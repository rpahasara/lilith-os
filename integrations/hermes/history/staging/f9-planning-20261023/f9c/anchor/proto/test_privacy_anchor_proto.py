"""F9-C Privacy rollback anchor: synthetic failure/recovery matrix for the PROTOTYPE (A1-A14). Real Core API Privacy
store and FORGET flow (test fixtures); the witness side is simulated by WitnessAnchorStore.

    F9C_CORE_API=<core-api dir> python -m unittest test_privacy_anchor_proto
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import unittest
from pathlib import Path

CORE = Path(os.environ["F9C_CORE_API"])
sys.path.insert(0, str(CORE / "tests"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_privacy_hermes_owner_v2 import HERMES, HermesOwnerCase, StubOwner  # noqa: E402

from lilith_memory import memory_action_v2 as MA  # noqa: E402

import privacy_anchor_proto as A  # noqa: E402

ENV = "DEV_SYNTHETIC"
FI = MA.FIRST_INTERACTION_IDENTITY


class AnchorCase(HermesOwnerCase):
    def setUp(self) -> None:
        super().setUp()
        self.upgrade()
        self.provision()
        self.witness = A.WitnessAnchorStore(ENV)
        self.last_seen = 0

    def forget(self, *, first_interaction=True, complete=True):
        owners = ("L04", "L18_V2", HERMES) if first_interaction else ("L04", "L18_V2")
        auth, _ = self.begin(owners, first_interaction=first_interaction)
        if complete:
            for owner in owners:
                StubOwner(self.store, owner).erase_authorized(auth.authorization_ref_id, auth.execution_nonce)
            self.store.complete(auth.authorization_ref_id, auth.execution_nonce)
        return auth

    def genesis(self):
        count, head, entries = A.high_water(self.privacy_db, ENV)
        return self.witness.genesis(count, head, entries, A.utc())

    def advance(self):
        return A.advance_from_privacy(self.witness, self.privacy_db, A.utc())

    def check(self, anchor="current", **kw):
        doc = self.witness.current if anchor == "current" else anchor
        served = None
        if doc is not None:                                    # the witness serves the set its signed head commits to
            served = [tuple(e) for d in self.witness.history[:doc["anchorVersion"]] for e in d["appended"]]
        result = A.check(self.privacy_db, doc, kw.pop("key", self.witness.public_key), environment=ENV,
                         witness_key_id=self.witness.key_id, last_seen_version=kw.pop("last_seen", self.last_seen),
                         anchored_entries=served)
        if result.ready and doc:
            self.last_seen = max(self.last_seen, doc["anchorVersion"])
        return result

    def snapshot(self, name):
        path = self.root / f"privacy.{name}.db"
        conn = sqlite3.connect(self.privacy_db)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
        shutil.copy2(self.privacy_db, path)
        return path

    def restore(self, path):
        for suffix in ("-wal", "-shm"):
            Path(str(self.privacy_db) + suffix).unlink(missing_ok=True)
        shutil.copy2(path, self.privacy_db)


class AnchorMatrix(AnchorCase):
    def test_A1_genesis_on_an_empty_store_serves(self):
        self.genesis()
        self.assertEqual(self.check().status, A.AT_OR_AFTER)

    def test_A2_a_forget_is_unanchored_until_advanced_then_serves(self):
        self.genesis()
        self.forget(complete=False)
        self.assertEqual(self.check().status, A.AHEAD)                 # refuse: newest suppression not anchored
        self.advance()
        self.assertEqual(self.check().status, A.AT_OR_AFTER)
        # completion adds a receipt but no new suppression row: still current
        ref, nonce = self.store.in_flight_authorization(FI)
        for owner in ("L04", "L18_V2", HERMES):
            StubOwner(self.store, owner).erase_authorized(ref, nonce)
        self.store.complete(ref, nonce)
        self.assertEqual(self.check().status, A.AT_OR_AFTER)

    def test_A3_a_restored_older_privacy_db_is_detected(self):
        self.genesis()
        old = self.snapshot("before-forget")
        self.forget()
        self.advance()
        self.restore(old)                                              # the newer suppression is gone
        self.assertFalse(self.store.is_held(*FI))                      # Privacy alone would now serve FI
        result = self.check()
        self.assertEqual((result.status, result.local_count, result.anchor_count), (A.OLDER, 0, 1))

    def test_A4_a_fork_after_restore_is_detected(self):
        self.genesis()
        old = self.snapshot("before")
        self.forget()
        self.advance()
        self.restore(old)
        self.forget(first_interaction=False)                           # a different suppression, same count
        self.assertEqual(self.check().status, A.DIVERGED)
        with self.assertRaises(A.AnchorError) as caught:
            self.advance()
        self.assertEqual(caught.exception.code, A.DIVERGED)

    def test_A5_replayed_old_anchor_and_non_successor_advances_are_refused(self):
        first = self.genesis()
        old = self.snapshot("before")
        self.assertEqual(self.check().status, A.AT_OR_AFTER)
        self.forget()
        self.advance()
        self.assertEqual(self.check().status, A.AT_OR_AFTER)           # last seen = version 2
        self.restore(old)
        self.assertEqual(self.check(anchor=first).status, A.REPLAYED)  # a valid but older signed anchor
        with self.assertRaises(A.AnchorError) as caught:               # the witness only accepts extensions
            self.witness.advance([("suppress.forged", "0" * 64)], "f" * 64, A.utc())
        self.assertEqual(caught.exception.code, "ANCHOR_NOT_AN_EXTENSION")

    def test_A6_forged_or_foreign_anchors_are_unverifiable(self):
        self.forget()                                                  # so the tampering changes signed content
        self.genesis()
        doc = dict(self.witness.current)
        tampered = {**doc, "suppressionCount": 0, "setHead": A.set_head(ENV, ())}
        other = A.WitnessAnchorStore(ENV)
        self.assertEqual(self.check(anchor=tampered).status, A.UNVERIFIABLE)
        self.assertEqual(self.check(key=other.public_key).status, A.UNVERIFIABLE)
        self.assertEqual(A.check(self.privacy_db, doc, self.witness.public_key, environment="PROD",
                                 witness_key_id=self.witness.key_id).status, A.UNVERIFIABLE)

    def test_A7_missing_anchor_or_missing_privacy_fails_closed(self):
        self.assertEqual(self.check(anchor=None).status, A.UNAVAILABLE)
        self.genesis()
        self.privacy_db.rename(self.privacy_db.with_suffix(".moved"))
        self.assertEqual(self.check().status, A.UNAVAILABLE)

    def test_A8_concurrent_forgets_anchor_as_one_set_and_forged_entries_are_refused(self):
        self.genesis()
        self.forget(complete=False)
        self.forget(first_interaction=False, complete=False)
        _count, head, entries = A.high_water(self.privacy_db, ENV)
        for bad in (entries + [entries[0]], entries + [("suppress.forged", "0" * 64)]):
            with self.subTest(bad=len(bad)), self.assertRaises(A.AnchorError):   # duplicate / not this set
                self.witness.advance(bad, head, A.utc())
        self.witness.advance(list(reversed(entries)), head, A.utc())   # order is irrelevant: a set commitment
        self.assertEqual((self.check().status, self.witness.current["suppressionCount"]), (A.AT_OR_AFTER, 2))

    def test_A8b_a_vacuum_renumbering_rowids_does_not_matter(self):
        self.forget()
        self.forget(first_interaction=False)
        self.genesis()
        conn = sqlite3.connect(self.privacy_db)
        conn.execute("VACUUM")
        conn.close()
        self.assertEqual(self.check().status, A.AT_OR_AFTER)

    def test_A9_anchor_write_failure_keeps_serving_refused_until_a_retry(self):
        self.genesis()
        self.forget()
        self.witness.fail_next_persist = True
        with self.assertRaises(A.AnchorError):
            self.advance()
        self.assertEqual(self.witness.current["anchorVersion"], 1)     # nothing half-written
        self.assertEqual(self.check().status, A.AHEAD)
        self.advance()
        self.assertEqual(self.check().status, A.AT_OR_AFTER)
        self.assertEqual(self.advance()["anchorVersion"], 2)           # idempotent re-advance

    def test_A10_power_loss_mid_advance_then_retry(self):
        path = self.root / "witness.anchor.json"
        self.witness = A.WitnessAnchorStore(ENV, path=path)
        self.genesis()
        self.forget()
        self.witness.fail_next_persist = True                          # "power loss" before the durable write
        with self.assertRaises(A.AnchorError):
            self.advance()
        import json
        self.assertEqual(len(json.loads(path.read_text())), 1)          # durable state unchanged
        self.advance()
        self.assertEqual(len(json.loads(path.read_text())), 2)

    def test_A11_legitimate_restore_plus_governed_resuppression(self):
        self.genesis()
        old = self.snapshot("backup")
        self.forget()
        self.advance()
        self.restore(old)
        self.assertEqual(self.check().status, A.OLDER)
        added = A.resuppress_from_anchor(self.privacy_db, self.witness, authority="PRIVACY_GOVERNANCE_AUTHORITY_V1",
                                         at=A.utc())
        self.assertEqual(added, 1)
        self.assertEqual(self.check().status, A.AT_OR_AFTER)
        self.assertTrue(self.store.is_held(*FI))                       # the forgotten identity is suppressed again
        self.assertTrue(self.store.suppression_matches(FI))

    def test_A11b_resuppression_refuses_a_diverged_restore(self):
        self.genesis()
        old = self.snapshot("backup")
        self.forget()
        self.advance()
        self.restore(old)
        self.forget(first_interaction=False)
        with self.assertRaises(A.AnchorError) as caught:
            A.resuppress_from_anchor(self.privacy_db, self.witness, authority="PRIVACY_GOVERNANCE_AUTHORITY_V1",
                                     at=A.utc())
        self.assertEqual(caught.exception.code, A.DIVERGED)

    def test_A12_rollback_to_a_mid_forget_snapshot_keeps_the_suppression(self):
        self.genesis()
        self.forget(complete=False)
        self.advance()
        mid = self.snapshot("mid-forget")                              # hold ACTIVE, suppression row present
        ref, nonce = self.store.in_flight_authorization(FI)
        for owner in ("L04", "L18_V2", HERMES):
            StubOwner(self.store, owner).erase_authorized(ref, nonce)
        self.store.complete(ref, nonce)
        self.restore(mid)
        self.assertEqual(self.check().status, A.AT_OR_AFTER)          # suppression state identical
        self.assertTrue(self.store.is_held(*FI))                      # the in-flight hold came back: still held

    def test_A13_migration_genesis_anchors_existing_suppressions(self):
        self.forget()
        self.forget(first_interaction=False)
        doc = self.genesis()
        self.assertEqual((doc["suppressionCount"], self.check().status), (2, A.AT_OR_AFTER))
        with self.assertRaises(A.AnchorError):
            self.genesis()                                             # genesis happens once

    def test_A14_a_tampered_suppression_row_is_detected(self):
        self.forget()
        self.genesis()
        conn = sqlite3.connect(self.privacy_db)
        try:
            for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND "
                                        "tbl_name='privacy_restore_suppression_manifest'").fetchall():
                conn.execute(f'DROP TRIGGER "{name}"')
            conn.execute("UPDATE privacy_restore_suppression_manifest SET identity_selector=?", ("0" * 64,))
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(self.check().status, A.DIVERGED)


if __name__ == "__main__":
    unittest.main()
