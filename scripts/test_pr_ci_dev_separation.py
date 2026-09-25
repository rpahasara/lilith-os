"""PR source validation and protected-main DEV deployment stay separate."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CI = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
DEPLOY = (ROOT / ".github/workflows/deploy-dev.yml").read_text(encoding="utf-8")


def job(source: str, name: str) -> str:
    match = re.search(rf"(?m)^  {re.escape(name)}:\n", source)
    if match is None:
        raise AssertionError(f"missing job: {name}")
    following = re.search(r"(?m)^  [a-z_-]+:\n", source[match.end():])
    return source[match.start():match.end() + following.start() if following else None]


class PrCiDevSeparationTests(unittest.TestCase):
    def test_pr_validation_has_no_dev_credentials_or_commands(self):
        self.assertIn("  pull_request:\n", CI)
        for forbidden in ("id-token: write", "google-github-actions/auth", "gcloud ",
                          "compute ssh", "compute scp", "systemctl restart"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, CI)

    def test_legacy_required_check_is_source_only(self):
        source = job(CI, "pr-source-required-check")
        self.assertIn("name: LILITH DEV deployment", source)
        self.assertIn("github.event_name == 'pull_request'", source)
        self.assertIn("needs: [repository-contracts, frontend-quality, backend-quality]", source)
        self.assertIn("contents: read", source)
        self.assertIn('test "${CONTRACTS}" = success', source)
        self.assertIn('test "${FRONTEND}" = success', source)
        self.assertIn('test "${BACKEND}" = success', source)
        self.assertIn("DEV_AUTH=NONE DEV_DEPLOYMENT=NONE", source)

    def test_dev_jobs_reject_pr_origin_before_credentials(self):
        self.assertIn("    branches:\n      - main\n", DEPLOY)
        for name in ("deploy", "broker_postflight"):
            source = job(DEPLOY, name)
            guard = source.split("    runs-on:", 1)[0]
            with self.subTest(job=name):
                self.assertIn("github.event.workflow_run.event == 'push'", guard)
                self.assertIn("github.event.workflow_run.head_branch == github.event.repository.default_branch", guard)
                self.assertIn("github.event.workflow_run.head_repository.full_name == github.repository", guard)
                self.assertNotIn("github.event.workflow_run.event == 'pull_request'", guard)
        source = job(DEPLOY, "deploy")
        auth = source.index("uses: google-github-actions/auth@v3")
        auth_step = source[:auth].rsplit("      - name:", 1)[-1]
        self.assertIn("github.event.workflow_run.event == 'push'", auth_step)
        self.assertNotIn("github.event.workflow_run.event == 'pull_request'", auth_step)
        self.assertEqual(DEPLOY.count("uses: google-github-actions/auth@v3"), 1)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", job(DEPLOY, "deploy"))

    def test_main_candidate_is_exact_and_classified_against_first_parent(self):
        source = job(DEPLOY, "deploy")
        self.assertIn('test "$(git rev-parse HEAD)" = "${VALIDATED_SHA}"', source)
        self.assertIn('test "$(git -C candidate rev-parse HEAD)" = "${VALIDATED_SHA}"', source)
        self.assertIn('BASE_SHA="$(git -C candidate rev-parse HEAD^)"', source)
        self.assertIn('git checkout --detach "${BASE_SHA}"', source)
        self.assertIn("python candidate/scripts/classify_dev_deployment.py", source)
        self.assertIn("steps.classify.outputs.mode == 'DEPLOY_REQUIRED'", source)
        self.assertIn("steps.classify.outputs.mode == 'CONTROL_ONLY_NO_DEPLOY'", source)

    def test_control_only_main_diff_exits_before_dev_auth_or_mutation(self):
        source = job(DEPLOY, "deploy")
        self.assertIn("python candidate/scripts/classify_dev_deployment.py", source)
        for step in (
            "Build deterministic exact-SHA Core API bundle",
            "Authenticate to Google Cloud",
            "Set up Google Cloud CLI",
            "Package exact-SHA bundle for the fixed DEV helper",
            "Deploy through the fixed root-owned DEV helper",
            "Prove the routine DEV deployer has no root, broker, or Stage III reach",
            "Prove routine DEV federation cannot obtain PROD or the legacy privileged identity",
        ):
            with self.subTest(step=step):
                section = source.split(f"      - name: {step}\n", 1)[1].split("      - name:", 1)[0]
                self.assertIn("steps.classify.outputs.mode == 'DEPLOY_REQUIRED'", section)
        for name in ("broker_candidate", "broker_postflight"):
            with self.subTest(job=name):
                guard = job(DEPLOY, name).split("    runs-on:", 1)[0]
                self.assertIn("needs.deploy.outputs.mode == 'BROKER_CANDIDATE_VALIDATE_ONLY'", guard)

    def test_manual_entrypoint_cannot_use_candidate_workflow_or_deployment_steps(self):
        gate = job(DEPLOY, "premerge_gate")
        deploy = job(DEPLOY, "deploy")
        candidate = job(DEPLOY, "broker_candidate")
        post = job(DEPLOY, "broker_postflight")
        self.assertIn("  workflow_dispatch:\n", DEPLOY)
        self.assertIn("test \"$GITHUB_REF\" = refs/heads/main", gate)
        self.assertIn("branch.commit.sha !== context.sha", gate)
        self.assertIn("pr.head.sha !== candidate", gate)
        self.assertIn("ruleset_id: 23205011", gate)
        self.assertIn("checks.listForRef", gate)
        self.assertIn("python scripts/classify_dev_deployment.py", gate)
        self.assertIn("github.event.workflow_run.event == 'push'", deploy.split("    runs-on:", 1)[0])
        self.assertNotIn("github.event_name == 'workflow_dispatch'", deploy.split("    runs-on:", 1)[0])
        self.assertIn("contents: read", candidate)
        self.assertNotIn("id-token: write", candidate)
        self.assertNotIn("google-github-actions/auth", candidate)
        self.assertNotIn("compute ssh", candidate)
        self.assertNotIn("compute scp", candidate)
        self.assertNotIn("google-github-actions/auth", post)
        self.assertNotIn("id-token: write", post)
        self.assertIn("if: always() && github.event_name == 'workflow_run'", post)


if __name__ == "__main__":
    unittest.main()
