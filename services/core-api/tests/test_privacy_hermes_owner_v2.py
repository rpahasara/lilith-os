"""F9-C Slice 1: the Hermes DEV conversation erasure owner under Privacy Governance (schema v2 + required-owner floor).

Privacy Governance stays the only FORGET authority. HERMES_DEV_CONVERSATION is a peer resource owner, scope-bound to the
First Interaction identity by a governed floor that only the offline tool provisions (DEV_SYNTHETIC only). Synthetic
temporary databases only; Hermes itself is represented by a stub that follows the owner contract (independent
resolve_erasure_authorization, COMPLETE or raise).
"""

from __future__ import annotations

import hashlib
import importlib
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_canonical_runtime import CanonicalRuntimeCase, digest, stamp_text  # noqa: F401  (puts the Core API on sys.path)
from test_privacy_forget_lineage import ForgetLineageCase

from lilith_memory import canonical_contracts as contracts
from lilith_memory import memory_action_v2 as MA
from lilith_memory import privacy_governance as privacy
from lilith_memory import privacy_schema_v2 as V2
from lilith_memory import slice15b2a_migration

SECRET = b"TEST_ONLY F9-C privacy secret for Hermes owner (32+ bytes)"
HERMES = privacy.HERMES_DEV_CONVERSATION
FI_PURPOSE = MA.OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION
B9EB32C_PRIVACY_SHA256 = "3c57b9c10d19dd7ef127eeaf4a4c124bd9c31b517a68f94f75e6d68a0b166d15"
FROZEN_PRIVACY = Path(__file__).resolve().parents[3] / "docs" / "architecture" / "slice-15b2a" / "privacy_governance.py"


class StubOwner:
    """Follows the existing owner contract: validate independently, then COMPLETE, or raise and record nothing."""

    def __init__(self, store, owner: str):
        self.store, self.owner = store, owner

    def erase_authorized(self, auth_ref: str, nonce: str, *, fail: bool = False) -> dict:
        authorization = self.store.resolve_erasure_authorization(auth_ref, owner=self.owner, execution_nonce=nonce)
        if authorization is None:
            raise PermissionError("PRIVACY_ERASURE_NOT_AUTHORIZED")
        if fail:
            raise RuntimeError("TEST_ONLY synthetic executor failure")
        result = {"owner": self.owner, "status": "COMPLETE"}
        self.store.record_owner_result(auth_ref, nonce, result)
        return result


class HermesOwnerCase(CanonicalRuntimeCase):
    def setUp(self) -> None:
        super().setUp()
        self.privacy_db = self.root / "privacy.test.db"
        slice15b2a_migration.migrate_privacy(self.privacy_db, applied_at=stamp_text(3))
        self.store = privacy.PrivacyGovernanceStore(self.privacy_db, SECRET, self.actor, now_fn=lambda: self.now)
        self._n = 0

    def upgrade(self) -> str:
        return V2.upgrade_privacy_v1_to_v2(self.privacy_db, applied_at=stamp_text(4))[0]

    def provision(self) -> bool:
        return V2.provision_hermes_owner_floor(self.privacy_db, deployment_environment=V2.DEV_SYNTHETIC,
                                               applied_at=stamp_text(5))

    def forget_action(self, *, first_interaction: bool = True):
        if first_interaction:
            memory_class, namespace, key = MA.FIRST_INTERACTION_IDENTITY
        else:
            memory_class, namespace, key = ("TEST_ONLY_CLASS", "lilith.test.codename", "codename-f9c")
        fields = dict(schema_version=1, actor_ref_id=self.actor.ACTOR.actor_ref_id, operation=contracts.FORGET,
                      memory_class=memory_class, subject_namespace=namespace, subject_key=key, value_schema=None,
                      payload_digest="0" * 64, expected_active_revision_id=None, restore_revision_id=None)
        if first_interaction:
            return MA.action_from_fields(**fields, purpose=FI_PURPOSE)
        return contracts.FrozenMemoryActionV1(**fields, purpose=contracts.LONG_TERM_PERSONAL_PROJECT_RECALL)

    def evidence(self, action):
        self._n += 1
        return self.actor.issue(action=action, request_digest=digest(f"forget:{self._n}"),
                                nonce=f"forget.f9c.{self._n}")

    def begin(self, owners, *, first_interaction: bool = True, evidence=None, store=None):
        action = self.forget_action(first_interaction=first_interaction)
        evidence = evidence or self.evidence(action)
        _request, auth, suppression = (store or self.store).begin_forget(
            action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            intent_ref_id=f"intent.f9c.{self._n}", memory_item_id=None, resource_owners=owners,
            confirmation_event_ref=f"confirm.f9c.{self._n}")
        return auth, suppression

    def rows(self, sql: str, *params):
        conn = sqlite3.connect(self.privacy_db)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def frozen_store(self, package_root: Path):
        """The exact b9eb32c Privacy module (the frozen Slice 15B2a record copy), with today's contracts."""
        self.assertEqual(hashlib.sha256(FROZEN_PRIVACY.read_bytes()).hexdigest(), B9EB32C_PRIVACY_SHA256)
        package = package_root / "pg_b9eb32c"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        shutil.copyfile(FROZEN_PRIVACY, package / "privacy_governance.py")
        for name in ("canonical_contracts", "canonical_authority"):
            (package / f"{name}.py").write_text(
                f"import sys\nfrom lilith_memory import {name} as _m\nsys.modules[__name__] = _m\n", encoding="utf-8")
        sys.path.insert(0, str(package_root))
        self.addCleanup(lambda: (sys.path.remove(str(package_root)),
                                 [sys.modules.pop(m) for m in list(sys.modules) if m.startswith("pg_b9eb32c")]))
        module = importlib.import_module("pg_b9eb32c.privacy_governance")
        return module, module.PrivacyGovernanceStore(self.privacy_db, SECRET, self.actor, now_fn=lambda: self.now)

    def owner_table_sql(self) -> str:
        return self.rows("SELECT sql FROM sqlite_master WHERE name='privacy_erasure_authorization_owner'")[0][0]


class MigrationTests(HermesOwnerCase):
    def test_upgrade_creates_v2_and_is_idempotent(self):
        fingerprint = self.upgrade()
        self.assertEqual(self.rows("SELECT version FROM privacy_schema_migration ORDER BY version"), [(1,), (2,)])
        self.assertIn(f"'{HERMES}'", self.owner_table_sql())
        self.assertEqual(self.rows(f"SELECT COUNT(*) FROM {V2.FLOOR_TABLE}"), [(0,)])
        self.assertEqual(self.rows("PRAGMA integrity_check"), [("ok",)])
        again, _complete = V2.upgrade_privacy_v1_to_v2(self.privacy_db)
        self.assertEqual(again, fingerprint)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM privacy_schema_migration"), [(2,)])

    def test_v2_fingerprint_is_deterministic_across_databases(self):
        other = self.root / "privacy.other.db"
        slice15b2a_migration.migrate_privacy(other, applied_at=stamp_text(9))
        self.assertEqual(V2.upgrade_privacy_v1_to_v2(other)[0], self.upgrade())

    def test_in_flight_v1_authorization_survives_the_upgrade(self):
        auth, _suppression = self.begin(("L04", "L18_V2"))
        StubOwner(self.store, "L04").erase_authorized(auth.authorization_ref_id, auth.execution_nonce)
        before = self.rows("SELECT * FROM privacy_erasure_authorization_owner ORDER BY 1,2")
        self.upgrade()
        self.assertEqual(self.rows("SELECT * FROM privacy_erasure_authorization_owner ORDER BY 1,2"), before)
        resolved = self.store.resolve_erasure_authorization(
            auth.authorization_ref_id, owner="L18_V2", execution_nonce=auth.execution_nonce)
        self.assertEqual(resolved.authorization_fingerprint, auth.authorization_fingerprint)
        StubOwner(self.store, "L18_V2").erase_authorized(auth.authorization_ref_id, auth.execution_nonce)
        receipt = self.store.complete(auth.authorization_ref_id, auth.execution_nonce)
        self.assertEqual(receipt.verification_status, "COMPLETE")

    def test_failed_upgrade_leaves_v1_intact_and_a_retry_succeeds(self):
        auth, _ = self.begin(("L04",), first_interaction=False)
        v1_sql = self.owner_table_sql()
        with mock.patch.object(V2, "_content_digests", side_effect=[{"x": "1"}, RuntimeError("TEST_ONLY crash")]):
            with self.assertRaises(RuntimeError):
                self.upgrade()
        self.assertEqual(self.rows("SELECT version FROM privacy_schema_migration"), [(1,)])
        self.assertEqual(self.owner_table_sql(), v1_sql)
        self.assertEqual(self.rows(f"SELECT name FROM sqlite_master WHERE name IN ('{V2.FLOOR_TABLE}',"
                                   f"'{V2.OWNER_TABLE_RETIRED}')"), [])
        self.assertIsNotNone(self.store.resolve_erasure_authorization(
            auth.authorization_ref_id, owner="L04", execution_nonce=auth.execution_nonce))
        self.upgrade()
        self.assertIsNotNone(self.store.resolve_erasure_authorization(
            auth.authorization_ref_id, owner="L04", execution_nonce=auth.execution_nonce))

    def test_upgrade_refuses_drifted_or_unknown_schemas(self):
        conn = sqlite3.connect(self.privacy_db)
        conn.execute("DROP TRIGGER privacy_hold_no_update")                    # v1 schema drift
        conn.commit()
        conn.close()
        with self.assertRaises(V2.MigrationError):
            self.upgrade()
        other = self.root / "privacy.v3.db"
        slice15b2a_migration.migrate_privacy(other, applied_at=stamp_text(9))
        conn = sqlite3.connect(other)
        conn.execute("INSERT INTO privacy_schema_migration VALUES (3,'x','y')")
        conn.commit()
        conn.close()
        with self.assertRaises(V2.MigrationError):
            V2.upgrade_privacy_v1_to_v2(other)

    def test_upgrade_refuses_a_tampered_v2(self):
        self.upgrade()
        conn = sqlite3.connect(self.privacy_db)
        conn.execute(f"DROP TRIGGER {V2.FLOOR_TRIGGER}")
        conn.commit()
        conn.close()
        with self.assertRaises(V2.MigrationError):
            self.upgrade()


class FloorScopeTests(HermesOwnerCase):
    def test_v1_database_refuses_hermes_before_consuming_evidence(self):
        action = self.forget_action()
        evidence = self.evidence(action)
        with self.assertRaisesRegex(privacy.PrivacyError, "requires privacy schema v2"):
            self.begin(("L04", "L18_V2", HERMES), evidence=evidence)
        auth, _ = self.begin(("L04", "L18_V2"), evidence=evidence)              # evidence was not consumed
        self.assertIsNotNone(auth)

    def test_v2_without_floor_refuses_hermes_and_allows_existing_forgets(self):
        self.upgrade()
        with self.assertRaisesRegex(privacy.PrivacyError, "not provisioned for this scope"):
            self.begin(("L04", "L18_V2", HERMES))
        self.assertIsNotNone(self.begin(("L04", "L18_V2"))[0])

    def test_floor_provisioning_is_dev_synthetic_only_and_needs_v2(self):
        with self.assertRaises(V2.MigrationError):
            self.provision()                                                       # still v1
        self.upgrade()
        for environment in ("PROD", "DEV", "dev_synthetic", ""):
            with self.subTest(environment=environment), self.assertRaises(V2.MigrationError):
                V2.provision_hermes_owner_floor(self.privacy_db, deployment_environment=environment)
        self.assertTrue(self.provision())
        self.assertFalse(self.provision())                                         # idempotent
        self.assertEqual(self.rows(f"SELECT memory_class,subject_namespace,resource_owner,deployment_environment "
                                   f"FROM {V2.FLOOR_TABLE}"),
                         [(*MA.FIRST_INTERACTION_IDENTITY[:2], HERMES, V2.DEV_SYNTHETIC)])

    def test_floor_requires_hermes_for_first_interaction_only(self):
        self.upgrade()
        self.provision()
        action = self.forget_action()
        evidence = self.evidence(action)
        with self.assertRaisesRegex(privacy.PrivacyError, "required erasure resource owner is missing"):
            self.begin(("L04", "L18_V2"), evidence=evidence)
        auth, _ = self.begin(("L04", "L18_V2", HERMES), evidence=evidence)      # same evidence: not consumed
        self.assertEqual(auth.resource_owners, tuple(sorted(("L04", "L18_V2", HERMES))))
        with self.assertRaisesRegex(privacy.PrivacyError, "not provisioned for this scope"):
            self.begin(("L04", "L18_V2", HERMES), first_interaction=False)
        self.assertIsNotNone(self.begin(("L04", "L18_V2"), first_interaction=False)[0])

    def test_serving_store_cannot_write_the_floor_and_rows_are_immutable(self):
        self.upgrade()
        self.provision()
        conn = self.store._connect()
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute(f"DELETE FROM {V2.FLOOR_TABLE}")
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute(f"INSERT INTO {V2.FLOOR_TABLE} VALUES ('a','b','{HERMES}','DEV_SYNTHETIC','t')")
        finally:
            conn.close()
        raw = sqlite3.connect(self.privacy_db)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                raw.execute(f"UPDATE {V2.FLOOR_TABLE} SET resource_owner=resource_owner")
        finally:
            raw.close()

    def test_floor_change_during_forget_aborts_without_writing(self):
        self.upgrade()
        self.provision()
        real = privacy.PrivacyGovernanceStore._owner_floor
        calls = []

        def flip(conn, memory_class, namespace):
            calls.append(1)
            version, floor = real(conn, memory_class, namespace)
            return (version, floor) if len(calls) == 1 else (version, frozenset())

        with mock.patch.object(privacy.PrivacyGovernanceStore, "_owner_floor", staticmethod(flip)):
            with self.assertRaisesRegex(privacy.PrivacyError, "floor changed"):
                self.begin(("L04", "L18_V2", HERMES))
        self.assertEqual(self.rows("SELECT COUNT(*) FROM privacy_forget_request"), [(0,)])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM privacy_hold"), [(0,)])

    def test_retiring_the_floor_keeps_issued_authorizations_strict(self):
        self.upgrade()
        self.provision()
        auth, _ = self.begin(("L04", "L18_V2", HERMES))
        self.assertTrue(V2.retire_hermes_owner_floor(self.privacy_db))
        self.assertFalse(V2.retire_hermes_owner_floor(self.privacy_db))           # idempotent
        # New First Interaction FORGETs no longer require Hermes (separate database: one active hold per identity).
        other = self.root / "privacy.retired.db"
        slice15b2a_migration.migrate_privacy(other, applied_at=stamp_text(9))
        V2.upgrade_privacy_v1_to_v2(other)
        V2.provision_hermes_owner_floor(other, deployment_environment=V2.DEV_SYNTHETIC)
        V2.retire_hermes_owner_floor(other)
        other_store = privacy.PrivacyGovernanceStore(other, SECRET, self.actor, now_fn=lambda: self.now)
        self.assertIsNotNone(self.begin(("L04", "L18_V2"), store=other_store)[0])
        for owner in ("L04", "L18_V2"):
            StubOwner(self.store, owner).erase_authorized(auth.authorization_ref_id, auth.execution_nonce)
        with self.assertRaisesRegex(privacy.PrivacyError, "incomplete"):
            self.store.complete(auth.authorization_ref_id, auth.execution_nonce)


class AuthorizationAndFailureTests(HermesOwnerCase):
    def setUp(self) -> None:
        super().setUp()
        self.upgrade()
        self.provision()
        self.auth, _ = self.begin(("L04", "L18_V2", HERMES))

    def resolve(self, owner=HERMES, nonce=None, store=None):
        return (store or self.store).resolve_erasure_authorization(
            self.auth.authorization_ref_id, owner=owner, execution_nonce=nonce or self.auth.execution_nonce)

    def test_hermes_owner_validates_independently(self):
        self.assertEqual(self.resolve().resource_owners, self.auth.resource_owners)
        self.assertIsNone(self.resolve(nonce="execution." + "0" * 32))           # wrong nonce
        other = privacy.PrivacyGovernanceStore(self.privacy_db, b"TEST_ONLY another secret of 32+ bytes!!", self.actor)
        self.assertIsNone(self.resolve(store=other))                               # HMAC does not verify
        unlisted, _ = self.begin(("L04", "L18_V2"), first_interaction=False)
        self.assertIsNone(self.store.resolve_erasure_authorization(
            unlisted.authorization_ref_id, owner=HERMES, execution_nonce=unlisted.execution_nonce))
        self.assertIsNone(self.resolve(owner="NOT_AN_OWNER"))

    def test_hermes_failure_keeps_the_hold_and_a_retry_completes(self):
        ref, nonce = self.auth.authorization_ref_id, self.auth.execution_nonce
        for owner in ("L04", "L18_V2"):
            StubOwner(self.store, owner).erase_authorized(ref, nonce)
        with self.assertRaises(RuntimeError):
            StubOwner(self.store, HERMES).erase_authorized(ref, nonce, fail=True)
        with self.assertRaisesRegex(privacy.PrivacyError, "incomplete; privacy hold remains active"):
            self.store.complete(ref, nonce)
        self.assertTrue(self.store.is_held(*MA.FIRST_INTERACTION_IDENTITY))
        self.assertEqual(self.rows("SELECT COUNT(*) FROM privacy_hold"), [(1,)])
        StubOwner(self.store, HERMES).erase_authorized(ref, nonce)                # retry, same authorization
        receipt = self.store.complete(ref, nonce)
        self.assertEqual(self.rows("SELECT resource_owner FROM privacy_completion_owner_result "
                                   "WHERE receipt_id=? ORDER BY 1", receipt.receipt_id),
                         [("HERMES_DEV_CONVERSATION",), ("L04",), ("L18_V2",)])
        self.assertTrue(self.store.is_held(*MA.FIRST_INTERACTION_IDENTITY))      # monotonic suppression
        self.assertIsNone(self.resolve())                                         # replay after completion

    def test_recording_failed_is_terminal_so_owners_must_raise_instead(self):
        ref, nonce = self.auth.authorization_ref_id, self.auth.execution_nonce
        self.store.record_owner_result(ref, nonce, {"owner": HERMES, "status": "FAILED"})
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.record_owner_result(ref, nonce, {"owner": HERMES, "status": "COMPLETE"})
        for owner in ("L04", "L18_V2"):
            StubOwner(self.store, owner).erase_authorized(ref, nonce)
        with self.assertRaisesRegex(privacy.PrivacyError, "incomplete"):
            self.store.complete(ref, nonce)
        self.assertTrue(self.store.is_held(*MA.FIRST_INTERACTION_IDENTITY))

    def test_a_duplicate_complete_is_refused_so_retries_must_reuse_the_result(self):
        ref, nonce = self.auth.authorization_ref_id, self.auth.execution_nonce
        StubOwner(self.store, HERMES).erase_authorized(ref, nonce)
        with self.assertRaises(sqlite3.IntegrityError):
            StubOwner(self.store, HERMES).erase_authorized(ref, nonce)


class CompatibilityTests(HermesOwnerCase):
    def test_b9eb32c_privacy_code_runs_unchanged_on_a_v2_database(self):
        self.upgrade()
        self.provision()
        with tempfile.TemporaryDirectory() as root:
            old_module, old = self.frozen_store(Path(root))
            self.assertNotIn(HERMES, old_module.OWNER_SET)
            auth, _ = self.begin(("L04", "L18_V2"), first_interaction=False, store=old)
            for owner in ("L04", "L18_V2"):
                StubOwner(old, owner).erase_authorized(auth.authorization_ref_id, auth.execution_nonce)
            self.assertEqual(old.complete(auth.authorization_ref_id, auth.execution_nonce).verification_status,
                             "COMPLETE")
            new_auth, _ = self.begin(("L04", "L18_V2", HERMES))                   # issued by the new code
            self.assertIsNone(old.resolve_erasure_authorization(
                new_auth.authorization_ref_id, owner=HERMES, execution_nonce=new_auth.execution_nonce))
            for owner in ("L04", "L18_V2"):
                StubOwner(old, owner).erase_authorized(new_auth.authorization_ref_id, new_auth.execution_nonce)
            with self.assertRaises(old_module.PrivacyError):                     # rolled-back code fails closed
                old.complete(new_auth.authorization_ref_id, new_auth.execution_nonce)

    def test_new_code_on_a_v1_database_keeps_existing_forgets(self):
        auth, _ = self.begin(("L04", "L18_V2"))
        for owner in ("L04", "L18_V2"):
            StubOwner(self.store, owner).erase_authorized(auth.authorization_ref_id, auth.execution_nonce)
        self.assertEqual(self.store.complete(auth.authorization_ref_id, auth.execution_nonce).verification_status,
                         "COMPLETE")


class DowngradeBypassTests(HermesOwnerCase):
    """Rolled-back b9eb32c Privacy code on a v2 database with the First Interaction floor provisioned must not be able
    to authorize or complete a First Interaction FORGET without HERMES_DEV_CONVERSATION."""

    def setUp(self) -> None:
        super().setUp()
        self.upgrade()
        self.provision()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.old_module, self.old = self.frozen_store(Path(self._tmp.name))

    def test_old_code_cannot_complete_a_first_interaction_forget_without_hermes(self):
        completed = False
        try:
            auth, _ = self.begin(("L04", "L18_V2"), store=self.old)
            for owner in ("L04", "L18_V2"):
                StubOwner(self.old, owner).erase_authorized(auth.authorization_ref_id, auth.execution_nonce)
            self.old.complete(auth.authorization_ref_id, auth.execution_nonce)
            completed = True
        except (self.old_module.PrivacyError, sqlite3.DatabaseError):
            pass
        self.assertFalse(completed, "b9eb32c code completed a First Interaction FORGET without Hermes erasure")
        self.assertEqual(self.rows("SELECT COUNT(*) FROM privacy_completion_receipt"), [(0,)])

    def test_old_code_cannot_even_authorize_it(self):
        with self.assertRaises((self.old_module.PrivacyError, sqlite3.DatabaseError)):
            self.begin(("L04", "L18_V2"), store=self.old)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM privacy_erasure_authorization"), [(0,)])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM privacy_hold"), [(0,)])

    def test_old_code_keeps_working_for_codename_forgets(self):
        auth, _ = self.begin(("L04", "L18_V2"), first_interaction=False, store=self.old)
        for owner in ("L04", "L18_V2"):
            StubOwner(self.old, owner).erase_authorized(auth.authorization_ref_id, auth.execution_nonce)
        self.assertEqual(self.old.complete(auth.authorization_ref_id, auth.execution_nonce).verification_status,
                         "COMPLETE")

    def test_new_code_completes_the_first_interaction_forget_with_hermes(self):
        auth, _ = self.begin(("L04", "L18_V2", HERMES))
        for owner in ("L04", "L18_V2", HERMES):
            StubOwner(self.store, owner).erase_authorized(auth.authorization_ref_id, auth.execution_nonce)
        self.assertEqual(self.store.complete(auth.authorization_ref_id, auth.execution_nonce).verification_status,
                         "COMPLETE")

    def test_after_governed_retirement_old_code_may_forget_without_hermes(self):
        self.assertTrue(V2.retire_hermes_owner_floor(self.privacy_db))
        self.assertEqual(self.rows("SELECT name FROM sqlite_master WHERE name IN (?,?)",
                                   *privacy.FLOOR_ENFORCEMENT_TRIGGERS), [])
        auth, _ = self.begin(("L04", "L18_V2"), store=self.old)
        for owner in ("L04", "L18_V2"):
            StubOwner(self.old, owner).erase_authorized(auth.authorization_ref_id, auth.execution_nonce)
        self.assertEqual(self.old.complete(auth.authorization_ref_id, auth.execution_nonce).verification_status,
                         "COMPLETE")


class OldAuthorizationTests(HermesOwnerCase):
    """Authorizations issued before the floor are completed legitimately but can never bypass it."""

    def frozen(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        return self.frozen_store(Path(self._tmp.name))[1]

    def test_in_flight_pre_floor_authorization_blocks_provisioning_until_completed(self):
        old = self.frozen()
        auth, _ = self.begin(("L04", "L18_V2"), store=old)                       # legitimate v1 FI FORGET in flight
        self.upgrade()
        with self.assertRaisesRegex(V2.MigrationError, "in flight"):
            self.provision()
        self.assertEqual(self.rows(f"SELECT COUNT(*) FROM {V2.FLOOR_TABLE}"), [(0,)])
        for owner in ("L04", "L18_V2"):                                          # completes under the new code
            StubOwner(self.store, owner).erase_authorized(auth.authorization_ref_id, auth.execution_nonce)
        self.assertEqual(self.store.complete(auth.authorization_ref_id, auth.execution_nonce).verification_status,
                         "COMPLETE")
        self.assertTrue(self.provision())

    def test_database_blocks_completion_even_if_the_precondition_were_bypassed(self):
        self.upgrade()
        auth, _ = self.begin(("L04", "L18_V2"))                                  # no floor yet: allowed
        conn = sqlite3.connect(self.privacy_db)                                   # simulate a precondition bypass
        conn.execute(f"INSERT INTO {V2.FLOOR_TABLE} VALUES (?,?,?,?,?)",
                     (*V2.FLOOR_SCOPE, HERMES, V2.DEV_SYNTHETIC, "t"))
        for name in privacy.FLOOR_ENFORCEMENT_TRIGGERS:
            conn.execute(V2.FLOOR_ENFORCEMENT_SQL[name])
        conn.commit()
        conn.close()
        for owner in ("L04", "L18_V2"):
            StubOwner(self.store, owner).erase_authorized(auth.authorization_ref_id, auth.execution_nonce)
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.complete(auth.authorization_ref_id, auth.execution_nonce)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM privacy_hold"), [(1,)])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM privacy_completion_receipt"), [(0,)])

    def test_floor_without_enforcement_fails_closed_and_cannot_be_reprovisioned(self):
        self.upgrade()
        self.provision()
        conn = sqlite3.connect(self.privacy_db)
        conn.execute(f'DROP TRIGGER "{privacy.FLOOR_ENFORCEMENT_TRIGGERS[1]}"')
        conn.commit()
        conn.close()
        with self.assertRaisesRegex(privacy.PrivacyError, "enforcement is missing"):
            self.begin(("L04", "L18_V2", HERMES))
        with self.assertRaisesRegex(V2.MigrationError, "partially provisioned"):
            self.provision()

    def test_altered_enforcement_is_refused_by_the_tool(self):
        self.upgrade()
        self.provision()
        name = privacy.FLOOR_ENFORCEMENT_TRIGGERS[0]
        conn = sqlite3.connect(self.privacy_db)
        conn.execute(f'DROP TRIGGER "{name}"')
        conn.execute(f"CREATE TRIGGER {name} BEFORE INSERT ON privacy_restore_suppression_manifest "
                     "BEGIN SELECT 1; END")                                       # same name, neutered body
        conn.commit()
        conn.close()
        with self.assertRaisesRegex(V2.MigrationError, "partially provisioned or altered"):
            self.provision()

    def test_provisioning_installs_the_exact_enforcement(self):
        self.upgrade()
        self.assertTrue(self.provision())
        conn = sqlite3.connect(self.privacy_db)
        try:
            self.assertTrue(V2._enforcement_exact(conn))
        finally:
            conn.close()
        self.assertFalse(self.provision())


class RealOwnersOnV2Tests(ForgetLineageCase):
    """The unchanged L04 and L18_V2 erasure owners complete a codename FORGET on an upgraded v2 database."""

    def setUp(self) -> None:
        super().setUp()
        V2.upgrade_privacy_v1_to_v2(self.root / "privacy.test.db", applied_at=stamp_text(4))
        V2.provision_hermes_owner_floor(self.root / "privacy.test.db", deployment_environment=V2.DEV_SYNTHETIC)

    def test_codename_forget_with_real_owners(self):
        first, _ref = self.apply("TEST-ONLY-F9C", nonce="f9c")
        l04, l18, receipt = self.forget()
        self.assertEqual((l04["status"], l18["status"], receipt.verification_status),
                         ("COMPLETE", "COMPLETE", "COMPLETE"))
        self.assertNotIn(b"TEST-ONLY-F9C", self.db.read_bytes())
        self.assert_clean()


if __name__ == "__main__":
    unittest.main()
