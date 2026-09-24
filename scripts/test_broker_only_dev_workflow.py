"""Static regression guards for the trusted broker-only required-check lane."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/deploy-dev.yml"
SNAPSHOT_HELPER = Path(__file__).resolve().with_name("broker_candidate_dev_snapshot.py")


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
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("runs-on: ubuntu-latest", candidate)
        self.assertIn("memory_broker_validation.py verify-run", candidate)
        self.assertIn("memory_broker_os_release.py verify", candidate)
        self.assertIn("CANDIDATE_AUTH=NONE DEV_ENV=NONE SSH_KEY=NONE DEV_TRANSFER=NONE", candidate)
        self.assertNotIn("id-token: write", candidate)
        self.assertNotIn("google-github-actions/auth", candidate)
        self.assertNotIn("gcloud ", candidate)
        self.assertNotIn("compute ssh", candidate)
        self.assertNotIn("compute scp", candidate)
        self.assertNotIn("  GCP_PROJECT_ID:", workflow.split("jobs:", 1)[0])
        self.assertNotIn("      GCP_PROJECT_ID:", candidate)
        self.assertNotIn("      GCP_DEPLOY_SA:", candidate)

    def test_preflight_postflight_and_same_required_context(self):
        preflight = job("broker_preflight")
        postflight = job("broker_postflight")
        self.assertIn("broker_candidate_dev_snapshot.py", preflight)
        self.assertIn("--phase preflight", preflight)
        self.assertIn("--phase postflight", postflight)
        self.assertIn("--expected-snapshot-sha", postflight)
        self.assertIn("audit_core_api_production_read_only.py", postflight)
        self.assertIn("context: 'LILITH DEV deployment'", postflight)
        self.assertIn("needs: [deploy, premerge_gate, broker_preflight, broker_candidate]", postflight)
        self.assertIn("needs.broker_candidate.result == 'success'", postflight)
        self.assertIn("context: 'LILITH DEV deployment'", job("deploy"))
        self.assertIn("needs.broker_preflight.result == 'success'", job("broker_candidate"))
        self.assertIn("steps.equality.outcome == 'success'", postflight)
        self.assertNotIn("compute scp", preflight + postflight)
        helper = SNAPSHOT_HELPER.read_text(encoding="utf-8")
        self.assertIn('invocation.ssh_command()', helper)
        self.assertIn('TRUSTED_SNAPSHOT_RELEASE_MISMATCH', helper)
        for retired in ('remote_action(', 'pack_source(', 'trusted_source_bytes(',
                        'lifecycle.py.part', 'lifecycle.py', 'source_bytes'):
            self.assertNotIn(retired, helper)
        self.assertIn('ref: ${{ needs.deploy.outputs.base_sha || needs.premerge_gate.outputs.base_sha }}', preflight)
        self.assertIn('ref: ${{ needs.deploy.outputs.base_sha || needs.premerge_gate.outputs.base_sha }}', postflight)
        self.assertIn('Record installed snapshot invocation tool versions', preflight)
        self.assertIn('Record installed snapshot invocation tool versions', postflight)

    def test_control_only_and_full_mode_routes_remain(self):
        full = job("deploy")
        self.assertIn("steps.classify.outputs.mode == 'CONTROL_ONLY_NO_DEPLOY'", full)
        self.assertIn("steps.classify.outputs.mode == 'DEPLOY_REQUIRED'", full)
        self.assertIn("['DEPLOY_REQUIRED', 'CONTROL_ONLY_NO_DEPLOY']", full)
        self.assertIn("steps.classify.outputs.mode != 'BROKER_CANDIDATE_VALIDATE_ONLY'", full)

    def test_manual_gate_is_protected_main_only_and_fails_before_pre(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        gate = job("premerge_gate")
        preflight = job("broker_preflight")
        self.assertIn("  workflow_dispatch:\n", workflow)
        self.assertIn("pr_number:", workflow)
        self.assertIn("candidate_sha:", workflow)
        self.assertIn("test \"$GITHUB_REF\" = refs/heads/main", gate)
        self.assertIn("test \"$REQUESTED_PR\" = 38", gate)
        self.assertIn("test \"$REQUESTED_SHA\" = 379fe8bba45cc0a2ebc79d9aa4c266eb5ffcdc3b", gate)
        self.assertIn("branch.commit.sha !== context.sha", gate)
        self.assertIn("pr.head.sha !== candidate", gate)
        self.assertIn("ruleset_id: 23205011", gate)
        self.assertIn("required_status_checks", gate)
        self.assertIn("matches[0].conclusion !== 'success'", gate)
        self.assertIn("python scripts/classify_dev_deployment.py", gate)
        self.assertIn("BROKER_CANDIDATE_VALIDATE_ONLY", gate)
        self.assertNotIn("id-token: write", gate)
        self.assertNotIn("google-github-actions/auth", gate)
        self.assertIn("Recheck frozen PR head immediately before manual PRE", preflight)
        self.assertLess(preflight.index("Recheck frozen PR head immediately before manual PRE"),
                        preflight.index("Authenticate for read-only DEV observation"))

    def test_manual_pre_post_are_exactly_two_accepted_read_only_observations(self):
        preflight = job("broker_preflight")
        candidate = job("broker_candidate")
        postflight = job("broker_postflight")
        self.assertIn("dff5ccddad5884b57f5cf895a9c86c741077fd21857d6e67de57803e6fde68e5", preflight)
        self.assertIn("needs.premerge_gate.result == 'success'", preflight)
        self.assertIn("needs.broker_candidate.result == 'failure'", postflight)
        self.assertIn("--expected-snapshot-sha", postflight)
        self.assertIn("github.event_name == 'workflow_run'", postflight)
        self.assertIn("steps.equality.outcome == 'success' && github.event_name == 'workflow_run'", postflight)
        self.assertIn("github.event_name == 'workflow_dispatch'", candidate)
        self.assertNotIn("broker_candidate_dev_snapshot.py", candidate)
        for forbidden in ("systemctl restart", "compute scp", "memory_broker_os_installer.py",
                          "Stage3FaultArmV1", "a2-arm.json"):
            self.assertNotIn(forbidden, preflight + candidate + postflight)


if __name__ == "__main__":
    unittest.main()
