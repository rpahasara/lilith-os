"""Pure accepted-state comparison tests; no GCP or VM access."""

from __future__ import annotations

import copy
import unittest

from scripts import broker_candidate_dev_snapshot as guard
from scripts import verify_broker_dev_lifecycle as lifecycle
from scripts.test_broker_dev_lifecycle import accepted_fixture


def fixture() -> dict:
    value = accepted_fixture()
    value["api"]["MainPID"] = "88740"
    value["runtimeIncarnations"] = {
        "broker": {"pid": 96650, "bootId": "a" * 36, "startTicks": 91036598},
        "api": {"pid": 88740, "bootId": "a" * 36, "startTicks": 86941441},
    }
    return value


class BrokerCandidateSnapshotTests(unittest.TestCase):
    def test_exact_accepted_snapshot_has_stable_digest(self):
        observed = guard.summarize(fixture())
        self.assertEqual(observed["acceptedBaselineDigest"], guard.ACCEPTED_DIGEST)
        self.assertEqual(observed["installedReleaseSha"], lifecycle.RELEASE_SHA)
        self.assertEqual(observed["brokerPid"], "96650")
        self.assertEqual(observed["apiPid"], "88740")
        self.assertEqual(observed["ownerDbSha256"], lifecycle.ACCEPTED_OWNER_DB_SHA)
        self.assertEqual(observed["evidenceDbSha256"], lifecycle.ACCEPTED_EVIDENCE_DB_SHA)
        self.assertEqual(observed, guard.summarize(fixture()))

    def test_api_broker_and_history_drift_change_complete_snapshot(self):
        original = guard.summarize(fixture())["snapshotSha256"]
        mutations = (
            lambda s: s["runtimeIncarnations"]["api"].__setitem__("startTicks", 2),
            lambda s: s["runtimeIncarnations"]["broker"].__setitem__("startTicks", 2),
            lambda s: s["api"].__setitem__("MainPID", "88741"),
            lambda s: s["units"][lifecycle.SERVICE].__setitem__("MainPID", "96651"),
            lambda s: s["databases"]["owner"]["rowHashes"]["owner_request_v1"].__setitem__(
                lifecycle.ACCEPTED_RETRY_CHALLENGE, "0" * 64),
            lambda s: s["usedAuthorizations"]["retry2"].__setitem__("sha256", "0" * 64),
            lambda s: s["api"]["custody"][str(lifecycle.API_ROOT / "data/lilith-dev.db")].__setitem__(
                "sha256", "0" * 64),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                value = fixture()
                mutation(value)
                try:
                    changed = guard.summarize(value)["snapshotSha256"]
                except guard.SnapshotError:
                    continue
                self.assertNotEqual(changed, original)

    def test_wrong_profile_release_digest_or_unhealthy_api_rejected(self):
        mutations = (
            lambda s: s.__setitem__("profile", lifecycle.POST_STAGE_I),
            lambda s: s["stage2AcceptedBaseline"].__setitem__(
                "stage2AcceptedBaselineDigest", "0" * 64),
            lambda s: s["release"].__setitem__("candidateSha", "0" * 40),
            lambda s: s["ownerSocket"].__setitem__("listening", False),
            lambda s: s["api"]["health"].__setitem__("status", "down"),
            lambda s: s.__setitem__("runtimeIncarnations", {}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                value = copy.deepcopy(fixture())
                mutation(value)
                with self.assertRaises(guard.SnapshotError):
                    guard.summarize(value)


if __name__ == "__main__":
    unittest.main()
