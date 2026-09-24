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
        for name in ("deploy", "broker_preflight", "broker_postflight"):
            source = job(DEPLOY, name)
            guard = source.split("    runs-on:", 1)[0]
            with self.subTest(job=name):
                self.assertIn("github.event.workflow_run.event == 'push'", guard)
                self.assertIn("github.event.workflow_run.head_branch == github.event.repository.default_branch", guard)
                self.assertIn("github.event.workflow_run.head_repository.full_name == github.repository", guard)
                self.assertNotIn("github.event.workflow_run.event == 'pull_request'", guard)
                auth = source.index("uses: google-github-actions/auth@v3")
                self.assertIn("github.event.workflow_run.event == 'push'", source[auth - 350:auth])
        self.assertIn("github.event.workflow_run.conclusion == 'success'", job(DEPLOY, "deploy"))

    def test_main_candidate_is_exact_and_classified_against_first_parent(self):
        source = job(DEPLOY, "deploy")
        self.assertIn('test "$(git rev-parse HEAD)" = "${VALIDATED_SHA}"', source)
        self.assertIn('test "$(git -C candidate rev-parse HEAD)" = "${VALIDATED_SHA}"', source)
        self.assertIn('BASE_SHA="$(git -C candidate rev-parse HEAD^)"', source)
        self.assertIn('git checkout --detach "${BASE_SHA}"', source)
        self.assertIn("python scripts/classify_dev_deployment.py", source)
        self.assertIn("steps.classify.outputs.mode == 'DEPLOY_REQUIRED'", source)
        self.assertIn("steps.classify.outputs.mode == 'CONTROL_ONLY_NO_DEPLOY'", source)


if __name__ == "__main__":
    unittest.main()
