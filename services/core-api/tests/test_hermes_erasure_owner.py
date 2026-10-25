"""F9-C Slice 2: the HERMES_DEV_CONVERSATION erasure owner adapter against a SYNTHETIC executor.

No privileged operation and no real Hermes file is touched: the executor is a test double that writes durable JSON
receipts into a temporary directory. Every non-COMPLETE outcome must leave Privacy incomplete (no owner result, hold
ACTIVE, complete() refused) and keep the same authorization retryable.
"""

from __future__ import annotations

import copy
import inspect
import json
import os
import sqlite3
import unittest
from pathlib import Path

from test_privacy_hermes_owner_v2 import HERMES, HermesOwnerCase, StubOwner  # noqa: F401  (puts Core API on path)

from lilith_memory import hermes_erasure_owner as H
from lilith_memory import memory_action_v2 as MA
from lilith_memory import privacy_governance as privacy


class SyntheticExecutor:
    """Durable, file-backed stand-in for the root executor. It never sees anything but the request it is given."""

    def __init__(self, root: Path, *, mode: str = "complete", ready_after_reads: int = 0, mutate=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.mode, self.ready_after_reads, self.mutate = mode, ready_after_reads, mutate
        self.requests, self.reads = [], 0
        self.authorization = None                       # what the real executor would resolve independently

    def path(self, ref: str) -> Path:
        return self.root / f"{ref}.receipt.json"

    def submit(self, request):
        if self.mode == "unavailable":
            raise OSError("TEST_ONLY spool unavailable")
        self.requests.append(dict(request))
        self.pending = dict(request)

    def build(self, request, status="COMPLETE"):
        a = self.authorization
        receipt = {
            "v": 1, "owner": HERMES, "authorizationRefId": request["authorizationRefId"],
            "executionNonce": request["executionNonce"], "authorizationFingerprint": a.authorization_fingerprint,
            "holdId": a.hold_id, "identityScope": dict(zip(("memoryClass", "subjectNamespace", "subjectKey"),
                                                          a.identity)),
            "scope": H.SCOPE, "status": status, "phases": {p: "COMPLETE" for p in H.REQUIRED_PHASES},
            "checks": {c: True for c in H.REQUIRED_CHECKS}, "erasureEpoch": 1, "claim": H.CLAIM,
            "providerErasure": H.PROVIDER_ERASURE, "completedAt": "2026-10-24T00:00:00.000000Z",
        }
        if self.mutate:
            self.mutate(receipt)
        if "receiptDigest" not in receipt:
            receipt["receiptDigest"] = H.receipt_digest(receipt)
        return receipt

    def write(self, receipt, key=None):
        """Durably file a receipt under the reference it was requested for (default: the one it names)."""
        target = self.path(key or receipt["authorizationRefId"])
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(receipt), encoding="utf-8")
        os.replace(tmp, target)

    def read_receipt(self, ref):
        self.reads += 1
        if self.mode == "unreadable":
            raise OSError("TEST_ONLY receipt store unavailable")
        pending = getattr(self, "pending", None)
        if pending and self.mode in ("complete", "rejected", "failed") and self.reads > self.ready_after_reads:
            self.write(self.build(pending, {"complete": "COMPLETE", "rejected": "REJECTED",
                                            "failed": "FAILED"}[self.mode]), key=pending["authorizationRefId"])
            self.pending = None
        p = self.path(ref)
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def monotonic(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


class AdapterCase(HermesOwnerCase):
    def setUp(self) -> None:
        super().setUp()
        self.upgrade()
        self.provision()
        self.auth, _ = self.begin(("L04", "L18_V2", HERMES))
        self.ref, self.nonce = self.auth.authorization_ref_id, self.auth.execution_nonce
        self.clock = FakeClock()

    def executor(self, **kw):
        ex = SyntheticExecutor(self.root / "executor", **kw)
        ex.authorization = self.auth
        return ex

    def owner(self, executor, *, store=None, timeout=10.0):
        return H.HermesConversationErasureOwner(store or self.store, executor, deployment_environment="DEV_SYNTHETIC",
                                                timeout_seconds=timeout, poll_seconds=1.0, sleep=self.clock.sleep,
                                                monotonic=self.clock.monotonic)

    def others_complete(self):
        for owner in ("L04", "L18_V2"):
            StubOwner(self.store, owner).erase_authorized(self.ref, self.nonce)

    def assert_privacy_incomplete(self):
        self.assertIsNone(self.store.owner_result(self.ref, self.nonce, HERMES))
        self.assertEqual(self.rows("SELECT COUNT(*) FROM privacy_hold"), [(1,)])
        self.others_complete() if self.store.owner_result(self.ref, self.nonce, "L04") is None else None
        with self.assertRaisesRegex(privacy.PrivacyError, "incomplete"):
            self.store.complete(self.ref, self.nonce)
        self.assertTrue(self.store.is_held(*MA.FIRST_INTERACTION_IDENTITY))


class ContractTests(AdapterCase):
    def test_interim_path_is_dev_synthetic_only(self):
        for environment in ("PROD", "DEV", "LIVE", "", "dev_synthetic"):
            with self.subTest(environment=environment), self.assertRaises(H.HermesErasureError) as caught:
                H.HermesConversationErasureOwner(self.store, self.executor(), deployment_environment=environment)
            self.assertEqual(caught.exception.code, "INTERIM_V1_PATH_DEV_SYNTHETIC_ONLY")

    def test_request_carries_only_owner_reference_and_nonce(self):
        ex = self.executor()
        self.owner(ex).erase_authorized(self.ref, self.nonce)
        self.assertEqual(ex.requests, [{"v": 1, "owner": HERMES, "authorizationRefId": self.ref,
                                        "executionNonce": self.nonce}])
        self.assertEqual(set(H.erasure_request("a", "b")), H.REQUEST_FIELDS)
        params = set(inspect.signature(H.HermesConversationErasureOwner.erase_authorized).parameters)
        self.assertEqual(params, {"self", "authorization_ref_id", "execution_nonce"})   # no session/scope input

    def test_happy_path_records_complete_and_privacy_completes(self):
        ex = self.executor(ready_after_reads=3)
        result = self.owner(ex).erase_authorized(self.ref, self.nonce)
        self.assertEqual((result["owner"], result["status"], result["erasureEpoch"]), (HERMES, "COMPLETE", 1))
        self.assertEqual(self.store.owner_result(self.ref, self.nonce, HERMES), "COMPLETE")
        self.others_complete()
        receipt = self.store.complete(self.ref, self.nonce)
        self.assertEqual(self.rows("SELECT resource_owner FROM privacy_completion_owner_result WHERE receipt_id=? "
                                   "ORDER BY 1", receipt.receipt_id), [(HERMES,), ("L04",), ("L18_V2",)])


class FailureTests(AdapterCase):
    def expect(self, code, executor, *, exc=H.HermesErasureError):
        with self.assertRaises(exc) as caught:
            self.owner(executor).erase_authorized(self.ref, self.nonce)
        if exc is H.HermesErasureError:
            self.assertEqual(caught.exception.code, code)
        self.assert_privacy_incomplete()

    def test_missing_executor(self):
        self.expect("EXECUTOR_UNAVAILABLE", None)

    def test_submit_and_receipt_store_unavailable(self):
        self.expect("EXECUTOR_UNAVAILABLE", self.executor(mode="unavailable"))

    def test_unreadable_receipt_store(self):
        self.expect("EXECUTOR_UNAVAILABLE", self.executor(mode="unreadable"))

    def test_queued_but_never_executed_is_not_complete(self):
        ex = self.executor(mode="crash")
        self.expect("EXECUTOR_TIMEOUT", ex)
        self.assertEqual(len(ex.requests), 1)

    def test_rejected_and_failed_receipts(self):
        self.expect("EXECUTOR_REJECTED", self.executor(mode="rejected"))
        (self.root / "executor" / f"{self.ref}.receipt.json").unlink()
        self.expect("EXECUTOR_FAILED", self.executor(mode="failed"))

    def test_forged_authorization_reference_is_refused_before_the_executor(self):
        ex = self.executor()
        with self.assertRaises(PermissionError):
            self.owner(ex).erase_authorized("erase." + "0" * 32, self.nonce)
        other = privacy.PrivacyGovernanceStore(self.privacy_db, b"TEST_ONLY a different 32+ byte secret!!", self.actor)
        with self.assertRaises(PermissionError):                                     # HMAC does not verify
            self.owner(ex, store=other).erase_authorized(self.ref, self.nonce)
        self.assertEqual((ex.requests, ex.reads), ([], 0))
        self.assert_privacy_incomplete()

    def test_wrong_nonce_is_refused_before_the_executor(self):
        ex = self.executor()
        with self.assertRaises(PermissionError):
            self.owner(ex).erase_authorized(self.ref, "execution." + "f" * 32)
        self.assertEqual((ex.requests, ex.reads), ([], 0))
        self.assert_privacy_incomplete()

    def test_out_of_scope_authorization_is_refused(self):
        real = self.store.resolve_erasure_authorization

        def codename_scoped(*args, **kwargs):
            auth = real(*args, **kwargs)
            return None if auth is None else privacy.ErasureAuthorizationV1(**{
                **auth.__dict__, "memory_class": "TEST_ONLY_CLASS", "subject_namespace": "lilith.test.codename"})

        self.store.resolve_erasure_authorization = codename_scoped
        ex = self.executor()
        with self.assertRaises(H.HermesErasureError) as caught:
            self.owner(ex).erase_authorized(self.ref, self.nonce)
        self.assertEqual(caught.exception.code, "AUTHORIZATION_OUT_OF_SCOPE")
        self.assertEqual(ex.requests, [])
        self.store.resolve_erasure_authorization = real
        self.assert_privacy_incomplete()

    def test_incomplete_overclaiming_or_forged_receipts(self):
        def set_(path, value):
            def m(r):
                target = r
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
            return m

        def drop(key):
            return lambda r: r.pop(key)

        cases = {
            "RECEIPT_INCOMPLETE": [set_(("phases", "JOURNAL"), "FAILED"), drop_phase := (lambda r: r["phases"].pop("BACKUPS")),
                                   set_(("checks", "wal_truncated"), False), set_(("checks", "sessions_zero"), "true"),
                                   set_(("erasureEpoch",), 0), set_(("erasureEpoch",), True),
                                   set_(("status",), "QUEUED")],
            "RECEIPT_MALFORMED": [drop("completedAt"), set_(("sessionIds",), ["f8b-s1"]), set_(("v",), 2),
                                  set_(("owner",), "L18_V2")],
            "RECEIPT_AUTHORIZATION_MISMATCH": [set_(("executionNonce",), "execution." + "1" * 32),
                                               set_(("authorizationRefId",), "erase." + "1" * 32),
                                               set_(("authorizationFingerprint",), "0" * 64),
                                               set_(("holdId",), "hold." + "1" * 32)],
            "RECEIPT_SCOPE_MISMATCH": [set_(("identityScope", "subjectKey"), "other"), set_(("scope",), "PER_SESSION")],
            "RECEIPT_OVERCLAIM": [set_(("claim",), "PHYSICALLY_DESTROYED"),
                                  set_(("providerErasure",), "VERIFIED")],
            "RECEIPT_DIGEST_MISMATCH": [set_(("receiptDigest",), "0" * 64)],
        }
        del drop_phase
        for code, mutations in cases.items():
            for i, mutate in enumerate(mutations):
                with self.subTest(code=code, case=i):
                    path = self.root / "executor" / f"{self.ref}.receipt.json"
                    path.unlink(missing_ok=True)
                    ex = self.executor(mutate=mutate)
                    with self.assertRaises(H.HermesErasureError) as caught:
                        self.owner(ex).erase_authorized(self.ref, self.nonce)
                    self.assertEqual(caught.exception.code, code)
                    self.assertIsNone(self.store.owner_result(self.ref, self.nonce, HERMES))
        self.assert_privacy_incomplete()

    def test_digest_is_checked_after_any_field_edit(self):
        ex = self.executor()
        good = ex.build(H.erasure_request(self.ref, self.nonce))
        tampered = copy.deepcopy(good)
        tampered["completedAt"] = "2026-10-24T00:00:01.000000Z"                  # edited after signing digest
        with self.assertRaises(H.HermesErasureError) as caught:
            H.verify_receipt(tampered, self.auth)
        self.assertEqual(caught.exception.code, "RECEIPT_DIGEST_MISMATCH")
        self.assertEqual(H.verify_receipt(good, self.auth)["erasureEpoch"], 1)


class RetryAndReplayTests(AdapterCase):
    def test_interrupted_execution_then_retry_reuses_the_durable_receipt(self):
        late = self.executor(ready_after_reads=1000)                              # executor still working
        with self.assertRaises(H.HermesErasureError) as caught:
            self.owner(late, timeout=3.0).erase_authorized(self.ref, self.nonce)
        self.assertEqual(caught.exception.code, "EXECUTOR_TIMEOUT")
        self.assertIsNone(self.store.owner_result(self.ref, self.nonce, HERMES))
        late.write(late.build(late.requests[0]))                                  # finishes after the adapter gave up
        retry = self.executor()
        result = self.owner(retry).erase_authorized(self.ref, self.nonce)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(retry.requests, [])                                       # reused, not resubmitted

    def test_retry_after_recorded_complete_is_idempotent(self):
        ex = self.executor()
        self.owner(ex).erase_authorized(self.ref, self.nonce)
        again = self.owner(ex).erase_authorized(self.ref, self.nonce)
        self.assertEqual((again["status"], again.get("idempotent")), ("COMPLETE", True))
        self.assertEqual(len(ex.requests), 1)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM privacy_erasure_execution WHERE resource_owner=?", HERMES),
                         [(1,)])

    def test_replay_after_privacy_completion_is_refused(self):
        ex = self.executor()
        self.owner(ex).erase_authorized(self.ref, self.nonce)
        self.others_complete()
        self.store.complete(self.ref, self.nonce)
        with self.assertRaises(PermissionError):
            self.owner(ex).erase_authorized(self.ref, self.nonce)

    def test_a_receipt_for_another_authorization_cannot_satisfy_this_one(self):
        ex = self.executor()
        foreign = ex.build(H.erasure_request("erase." + "2" * 32, "execution." + "2" * 32))
        foreign["authorizationRefId"] = self.ref                                   # replayed under this reference
        foreign["receiptDigest"] = H.receipt_digest(foreign)
        ex.write(foreign)
        with self.assertRaises(H.HermesErasureError) as caught:
            self.owner(ex).erase_authorized(self.ref, self.nonce)
        self.assertEqual(caught.exception.code, "RECEIPT_AUTHORIZATION_MISMATCH")
        self.assert_privacy_incomplete()

    def test_hold_released_between_receipt_and_record_is_refused(self):
        class Racing(SyntheticExecutor):
            def read_receipt(inner, ref):
                receipt = SyntheticExecutor.read_receipt(inner, ref)
                if receipt is not None:
                    self.store.resolve_erasure_authorization = lambda *a, **k: None   # authorization gone
                return receipt

        ex = Racing(self.root / "executor")
        ex.authorization = self.auth
        with self.assertRaises(PermissionError):
            self.owner(ex).erase_authorized(self.ref, self.nonce)
        del self.store.resolve_erasure_authorization
        self.assertIsNone(self.store.owner_result(self.ref, self.nonce, HERMES))

    def test_a_terminal_failed_result_is_never_overwritten(self):
        self.store.record_owner_result(self.ref, self.nonce, {"owner": HERMES, "status": "FAILED"})
        ex = self.executor()
        with self.assertRaises(H.HermesErasureError) as caught:
            self.owner(ex).erase_authorized(self.ref, self.nonce)
        self.assertEqual(caught.exception.code, "OWNER_RESULT_TERMINAL")
        self.assertEqual(ex.requests, [])


class PrivacyReadHelperTests(AdapterCase):
    def test_owner_result_requires_the_exact_nonce(self):
        self.store.record_owner_result(self.ref, self.nonce, {"owner": "L04", "status": "COMPLETE"})
        self.assertEqual(self.store.owner_result(self.ref, self.nonce, "L04"), "COMPLETE")
        self.assertIsNone(self.store.owner_result(self.ref, "execution." + "9" * 32, "L04"))
        self.assertIsNone(self.store.owner_result(self.ref, self.nonce, HERMES))

    def test_owner_result_cannot_write(self):
        conn = self.store._connect()
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute(f"DELETE FROM {privacy.REQUIRED_OWNER_FLOOR_TABLE}")
        finally:
            conn.close()


class DowngradeStillProtectedTests(AdapterCase):
    def test_floor_triggers_still_bind_after_adapter_completion_path(self):
        ex = self.executor()
        self.owner(ex).erase_authorized(self.ref, self.nonce)
        conn = sqlite3.connect(self.privacy_db)
        try:
            names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        finally:
            conn.close()
        self.assertTrue(set(privacy.FLOOR_ENFORCEMENT_TRIGGERS) <= names)


if __name__ == "__main__":
    unittest.main()
