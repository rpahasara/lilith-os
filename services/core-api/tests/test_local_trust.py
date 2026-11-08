# -*- coding: utf-8 -*-
"""LILITH_OS_TRUST_LOOPBACK: the on-host router keeps working under enforcement, with no change to it, and nothing off the host gains anything. TEST_ONLY; throwaway DB."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402

try:
    from fastapi.testclient import TestClient
except Exception:       # CI has no httpx
    TestClient = None

READ, WRITE = "TEST_ONLY" + "r" * 32, "TEST_ONLY" + "w" * 32
GOAL = {"type": "test_only.synthetic", "title": "TEST_ONLY", "source": "SYSTEM_MAINTENANCE", "owner": "user", "priority": "NORMAL"}
ENFORCED = {"LILITH_OS_READ_AUTH": "enforced", "LILITH_OS_READ_TOKEN": READ, "LILITH_OS_WRITE_AUTH": "enforced", "LILITH_OS_WRITE_TOKEN": WRITE}


@unittest.skipIf(TestClient is None, "httpx not installed")
class LocalTrust(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.dict(os.environ, ENFORCED)
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("LILITH_OS_TRUST_LOOPBACK", None)
        self.tmp = Path(tempfile.mkdtemp(prefix="local-trust-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        app.DB = self.tmp / "core.db"
        app._goal_schema_ready = False
        app._goals_db().close()

    def client(self, host):
        return TestClient(app.app, client=(host, 40000), raise_server_exceptions=False)

    def test_off_by_default_loopback_needs_a_credential(self):
        local = self.client("127.0.0.1")
        self.assertEqual(local.get("/os/goals").status_code, 401)
        self.assertEqual(local.post("/os/goals", json=GOAL).status_code, 401)

    def test_on_the_router_reads_and_writes_with_no_header(self):
        os.environ["LILITH_OS_TRUST_LOOPBACK"] = "1"
        local = self.client("127.0.0.1")
        self.assertEqual(local.get("/os/goals").status_code, 200)
        self.assertLess(local.post("/os/goals", json=GOAL).status_code, 300)

    def test_ipv6_loopback_counts(self):
        os.environ["LILITH_OS_TRUST_LOOPBACK"] = "1"
        self.assertEqual(self.client("::1").get("/os/goals").status_code, 200)

    def test_an_iap_caller_is_never_local(self):
        os.environ["LILITH_OS_TRUST_LOOPBACK"] = "1"
        iap = self.client("35.235.240.1")
        self.assertEqual(iap.get("/os/goals").status_code, 401)
        self.assertEqual(iap.post("/os/goals", json=GOAL).status_code, 401)
        self.assertEqual(iap.get("/os/goals", headers={"X-LILITH-OS-Read": READ}).status_code, 200)

    def test_a_forged_forwarded_header_changes_nothing(self):
        os.environ["LILITH_OS_TRUST_LOOPBACK"] = "1"
        iap = self.client("35.235.240.1")
        forged = {"X-Forwarded-For": "127.0.0.1", "X-Real-IP": "127.0.0.1", "Forwarded": "for=127.0.0.1"}
        self.assertEqual(iap.get("/os/goals", headers=forged).status_code, 401)

    def test_only_the_exact_value_turns_it_on(self):
        for value in ("0", "true", "yes", " 1", ""):
            os.environ["LILITH_OS_TRUST_LOOPBACK"] = value
            self.assertEqual(self.client("127.0.0.1").get("/os/goals").status_code, 401, repr(value))

    def test_an_unconfigured_server_stays_refused_even_for_loopback(self):
        os.environ["LILITH_OS_TRUST_LOOPBACK"] = "1"
        for name in ENFORCED:
            os.environ.pop(name)
        local = self.client("127.0.0.1")
        self.assertEqual(local.get("/os/goals").status_code, 503)
        self.assertEqual(local.post("/os/goals", json=GOAL).status_code, 503)

    def test_the_conversation_relay_is_never_trusted_by_address(self):
        os.environ["LILITH_OS_TRUST_LOOPBACK"] = "1"
        with mock.patch.object(app, "_relay_conversation", side_effect=AssertionError("relayed")):
            self.assertEqual(self.client("127.0.0.1").post("/os/conversation", json={"message": "TEST_ONLY"}).status_code, 401)

    def test_one_caller_does_not_carry_over_to_the_next(self):
        os.environ["LILITH_OS_TRUST_LOOPBACK"] = "1"
        self.assertEqual(self.client("127.0.0.1").get("/os/goals").status_code, 200)
        self.assertEqual(self.client("35.235.240.1").get("/os/goals").status_code, 401)


if __name__ == "__main__":
    unittest.main()
