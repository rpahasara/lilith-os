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
        broker = "\n".join(job(name) for name in ("broker_candidate", "broker_postflight"))
        self.assertIn("if: steps.classify.outputs.mode == 'DEPLOY_REQUIRED'", full)
        self.assertIn("sudo -n /usr/local/sbin/lilith-dev-deploy deploy ${VALIDATED_SHA}", full)
        self.assertNotIn("lilith-dev-deploy", broker)
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

    def test_postflight_publishes_same_required_context_without_dev_authority(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        postflight = job("broker_postflight")
        self.assertNotRegex(workflow, r"(?m)^  broker_preflight:\n")
        self.assertIn("context: 'LILITH DEV deployment'", postflight)
        self.assertIn("context: 'LILITH DEV deployment'", job("deploy"))
        self.assertIn("needs: [deploy, premerge_gate, broker_candidate]", postflight)
        self.assertIn("needs: [deploy, premerge_gate]", job("broker_candidate"))
        self.assertIn("process.env.CANDIDATE_RESULT === 'success'", postflight)
        for forbidden in ("id-token: write", "google-github-actions/auth", "gcloud ", "compute ssh",
                          "compute scp", "broker_candidate_dev_snapshot.py", "audit_core_api_production",
                          "lilith-01", "GCP_DEPLOY_SA"):
            self.assertNotIn(forbidden, postflight)
        helper = SNAPSHOT_HELPER.read_text(encoding="utf-8")
        self.assertIn('invocation.ssh_command()', helper)
        self.assertIn('TRUSTED_SNAPSHOT_RELEASE_MISMATCH', helper)
        for retired in ('remote_action(', 'pack_source(', 'trusted_source_bytes(',
                        'lifecycle.py.part', 'lifecycle.py', 'source_bytes'):
            self.assertNotIn(retired, helper)

    def test_control_only_and_full_mode_routes_remain(self):
        full = job("deploy")
        self.assertIn("steps.classify.outputs.mode == 'CONTROL_ONLY_NO_DEPLOY'", full)
        self.assertIn("steps.classify.outputs.mode == 'DEPLOY_REQUIRED'", full)
        self.assertIn("['DEPLOY_REQUIRED', 'CONTROL_ONLY_NO_DEPLOY']", full)
        self.assertIn("steps.classify.outputs.mode != 'BROKER_CANDIDATE_VALIDATE_ONLY'", full)

    def test_manual_gate_is_protected_main_only_and_fails_before_pre(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        gate = job("premerge_gate")
        self.assertIn("  workflow_dispatch:\n", workflow)
        self.assertIn("pr_number:", workflow)
        self.assertIn("candidate_sha:", workflow)
        self.assertIn("test \"$GITHUB_REF\" = refs/heads/main", gate)
        self.assertIn("test \"$REQUESTED_PR\" = 38", gate)
        self.assertIn('[[ "$REQUESTED_SHA" =~ ^[0-9a-f]{40}$ ]]', gate)
        self.assertNotIn('test "$REQUESTED_SHA" = ', gate)
        self.assertNotRegex(gate, r"\b[0-9a-f]{40}\b")
        self.assertIn("branch.commit.sha !== context.sha", gate)
        self.assertIn("pr.state !== 'open'", gate)
        self.assertIn("pr.base.repo.full_name !== 'rpahasara/lilith-os'", gate)
        self.assertIn("pr.head.repo.full_name !== 'rpahasara/lilith-os'", gate)
        self.assertIn("pr.head.sha !== candidate", gate)
        self.assertIn("ruleset_id: 23205011", gate)
        self.assertIn("required_status_checks", gate)
        self.assertIn("matches[0].conclusion !== 'success'", gate)
        self.assertIn("python scripts/classify_dev_deployment.py", gate)
        self.assertIn("BROKER_CANDIDATE_VALIDATE_ONLY", gate)
        self.assertIn('git -C candidate merge-base --is-ancestor "$BASE_SHA" "$CANDIDATE_SHA"', gate)
        self.assertLess(gate.index('merge-base --is-ancestor'),
                        gate.index('python scripts/classify_dev_deployment.py'))
        self.assertNotIn("id-token: write", gate)
        self.assertNotIn("google-github-actions/auth", gate)

    def test_manual_candidate_lane_has_no_dev_observation_or_mutation(self):
        candidate = job("broker_candidate")
        postflight = job("broker_postflight")
        self.assertIn("needs.broker_candidate.result != 'skipped'", postflight)
        self.assertIn("github.event_name == 'workflow_run'", postflight)
        self.assertIn("github.event_name == 'workflow_dispatch'", candidate)
        self.assertIn("pr.head.sha !== process.env.CANDIDATE_SHA", postflight)
        self.assertNotIn("broker_candidate_dev_snapshot.py", candidate)
        for forbidden in ("systemctl restart", "compute scp", "memory_broker_os_installer.py",
                          "Stage3FaultArmV1", "a2-arm.json"):
            self.assertNotIn(forbidden, candidate + postflight)


if __name__ == "__main__":
    unittest.main()
