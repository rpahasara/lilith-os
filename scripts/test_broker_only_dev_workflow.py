"""Static regression guards for the trusted broker-only required-check lane."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/deploy-dev.yml"


def job(name: str) -> str:
    source = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(rf"(?m)^  {re.escape(name)}:\n", source)
    if match is None:
        raise AssertionError(f"missing job: {name}")
    next_job = re.search(r"(?m)^  [a-z_]+:\n", source[match.end():])
    return source[match.start():match.end() + next_job.start() if next_job else None]


class BrokerOnlyWorkflowTests(unittest.TestCase):
    def test_broker_lane_is_separate_from_full_api_deployment(self):
        full = job("deploy")
        broker = "\n".join(job(name) for name in
                           ("broker_preflight", "broker_candidate", "broker_postflight"))
        self.assertIn("if: steps.classify.outputs.mode == 'DEPLOY_REQUIRED'", full)
        self.assertIn("deploy_core_api_dev_remote.sh", full)
        self.assertNotIn("deploy_core_api_dev_remote.sh", broker)
        self.assertNotIn("systemctl restart", broker)
        self.assertNotIn("bootstrap_core_api_dev", broker)
        self.assertNotIn("memory_broker_os_installer.py", broker)
        self.assertNotIn("run_memory_broker_dev_validation.sh", broker)

    def test_candidate_executes_only_on_credential_free_hosted_runner(self):
        candidate = job("broker_candidate")
        self.assertIn("runs-on: ubuntu-latest", candidate)
        self.assertIn("memory_broker_validation.py verify-run", candidate)
        self.assertIn("memory_broker_os_release.py verify", candidate)
        self.assertNotIn("id-token: write", candidate)
        self.assertNotIn("google-github-actions/auth", candidate)
        self.assertNotIn("gcloud ", candidate)
        self.assertNotIn("compute ssh", candidate)
        self.assertNotIn("compute scp", candidate)

    def test_preflight_postflight_and_same_required_context(self):
        preflight = job("broker_preflight")
        postflight = job("broker_postflight")
        self.assertIn("broker_candidate_dev_snapshot.py", preflight)
        self.assertIn("--run-id '${{ github.run_id }}' --run-attempt '${{ github.run_attempt }}'", preflight)
        self.assertIn("--phase preflight", preflight)
        self.assertIn("--run-id '${{ github.run_id }}' --run-attempt '${{ github.run_attempt }}'", postflight)
        self.assertIn("--phase postflight", postflight)
        self.assertIn("--expected-snapshot-sha", postflight)
        self.assertIn("audit_core_api_production_read_only.py", postflight)
        self.assertIn("context: 'LILITH DEV deployment'", postflight)
        self.assertIn("needs: [deploy, broker_preflight, broker_candidate]", postflight)
        self.assertIn("needs.broker_candidate.result == 'success'", postflight)
        self.assertIn("context: 'LILITH DEV deployment'", job("deploy"))
        self.assertIn("needs.broker_preflight.result == 'success'", job("broker_candidate"))
        self.assertIn("steps.equality.outcome == 'success'", postflight)

    def test_control_only_and_full_mode_routes_remain(self):
        full = job("deploy")
        self.assertIn("steps.classify.outputs.mode == 'CONTROL_ONLY_NO_DEPLOY'", full)
        self.assertIn("steps.classify.outputs.mode == 'DEPLOY_REQUIRED'", full)
        self.assertIn("['DEPLOY_REQUIRED', 'CONTROL_ONLY_NO_DEPLOY']", full)
        self.assertIn("steps.classify.outputs.mode != 'BROKER_CANDIDATE_VALIDATE_ONLY'", full)


if __name__ == "__main__":
    unittest.main()
