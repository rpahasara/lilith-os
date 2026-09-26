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

    # READ_ONLY SECURITY OBSERVATION != APPLICATION DEPLOYMENT.
    LIVE_PROOF_STEPS = (
        "Record GitHub OIDC claims presented to DEV federation",
        "Authenticate to Google Cloud",
        "Set up Google Cloud CLI",
        "Verify DEV deployment identity and target",
        "Prove the routine DEV deployer has no root, broker, or Stage III reach",
        "Prove the routine DEV deployer has no authority-custody reach",
    )
    DEPLOY_ONLY_STEPS = (
        "Build deterministic exact-SHA Core API bundle",
        "Detect broker component from exact candidate SHA",
        "Build separate exact-SHA broker validation artifact",
        "Validate broker candidate transiently before any cloud authentication",
        "Set up pinned Python for inert broker release validation",
        "Build and verify inert exact-SHA synthetic broker release",
        "Package exact-SHA bundle for the fixed DEV helper",
        "Deploy through the fixed root-owned DEV helper",
        "Verify DEV service health",
        "Prove routine DEV federation cannot obtain PROD or the legacy privileged identity",
    )
    BOTH = ("steps.classify.outputs.mode == 'DEPLOY_REQUIRED' || "
            "steps.classify.outputs.mode == 'CONTROL_ONLY_NO_DEPLOY'")

    @staticmethod
    def steps(source: str) -> dict[str, str]:
        parts = re.split(r"(?m)^      - name: ", source)[1:]
        return {part.split("\n", 1)[0]: part for part in parts}

    def test_control_only_runs_read_only_live_proofs_but_never_deploys(self):
        steps = self.steps(job(DEPLOY, "deploy"))
        for name in self.LIVE_PROOF_STEPS:
            with self.subTest(step=name):
                body = steps[name]
                if name == "Authenticate to Google Cloud":
                    self.assertIn("(steps.classify.outputs.mode == 'DEPLOY_REQUIRED' ||\n"
                                  "           steps.classify.outputs.mode == 'CONTROL_ONLY_NO_DEPLOY') &&\n"
                                  "          github.event.workflow_run.event == 'push' &&\n"
                                  "          github.event.workflow_run.head_branch == github.event.repository.default_branch\n",
                                  body)
                    self.assertIn("service_account: ${{ env.GCP_DEPLOY_SA }}", body)
                else:
                    self.assertIn(f"        if: {self.BOTH}\n", body)
                for forbidden in ("lilith-dev-deploy deploy", "lilith-dev-payload", "curl -fsS '${HEALTH_URL}'",
                                  "compute scp", "systemctl restart lilith-os-api", "always()", "continue-on-error"):
                    self.assertNotIn(forbidden, body)
        for name in self.DEPLOY_ONLY_STEPS:
            with self.subTest(step=name):
                condition = steps[name].split("\n", 2)[1]
                self.assertTrue(condition.startswith("        if: steps.classify.outputs.mode == 'DEPLOY_REQUIRED'"),
                                condition)
                self.assertNotIn("CONTROL_ONLY_NO_DEPLOY", condition)
                self.assertNotIn("||", condition)
        # Every step that CONTROL_ONLY_NO_DEPLOY can reach is on an exact allowlist.
        reachable = {name for name, body in steps.items()
                     if "CONTROL_ONLY_NO_DEPLOY'" in body.split("\n        uses:", 1)[0].split("\n        shell:", 1)[0]
                     and "outputs.mode ==" in body}
        self.assertEqual(reachable, set(self.LIVE_PROOF_STEPS) | {"Validate control-only candidate on the ephemeral runner"})
        order = [job(DEPLOY, "deploy").index(f"      - name: {name}\n") for name in self.LIVE_PROOF_STEPS]
        self.assertEqual(order, sorted(order))
        self.assertLess(order[-1], job(DEPLOY, "deploy").index("      - name: Package exact-SHA bundle for the fixed DEV helper\n"))
        self.assertEqual(DEPLOY.count("sudo -n /usr/local/sbin/lilith-dev-deploy deploy ${VALIDATED_SHA}"), 1)
        self.assertIn("sudo -n /usr/local/sbin/lilith-dev-deploy deploy ${VALIDATED_SHA}",
                      steps["Deploy through the fixed root-owned DEV helper"])
        for name in ("broker_candidate", "broker_postflight"):
            with self.subTest(job=name):
                guard = job(DEPLOY, name).split("    runs-on:", 1)[0]
                self.assertIn("needs.deploy.outputs.mode == 'BROKER_CANDIDATE_VALIDATE_ONLY'", guard)

    def test_control_only_success_reports_no_mutation_and_is_not_a_deployment(self):
        steps = self.steps(job(DEPLOY, "deploy"))
        status = steps["Publish successful DEV deployment status"]
        self.assertIn("if: ${{ success() && steps.classify.outputs.mode != 'BROKER_CANDIDATE_VALIDATE_ONLY' }}", status)
        self.assertIn("'MODE=CONTROL_ONLY_NO_DEPLOY DEV_MUTATION=NONE DEV_READ_ONLY_BOUNDARY_PROOF=PASS (no deployment)'",
                      status)
        self.assertIn("'MODE=DEPLOY_REQUIRED DEV deployment and health passed'", status)
        self.assertIn("context: 'LILITH DEV deployment'", status)
        self.assertNotIn("DEV_CONTACT=NONE", DEPLOY)
        validate = steps["Validate control-only candidate on the ephemeral runner"]
        self.assertIn("echo 'DEV_MUTATION=NONE'", validate)
        self.assertLess(len("MODE=CONTROL_ONLY_NO_DEPLOY DEV_MUTATION=NONE DEV_READ_ONLY_BOUNDARY_PROOF=PASS "
                            "(no deployment)"), 140)  # GitHub commit-status description limit

    def test_this_change_classifies_control_only_without_enlarging_the_control_set(self):
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        import classify_dev_deployment as C

        def entries(*paths):
            return [(path, "M", "100644", "100644") for path in paths]

        this_pr = (".github/workflows/deploy-dev.yml", "scripts/test_pr_ci_dev_separation.py")
        for path in this_pr:
            self.assertIn(path, C.CONTROL_ONLY_PATHS)
        self.assertEqual(C.classify_entries(entries(*this_pr), {}), C.CONTROL_ONLY_NO_DEPLOY)
        for extra in ("scripts/deployer_authority_boundary_proof.sh", "services/core-api/app.py",
                      "docs/architecture/slice-15b2b-b1b3d-deployer-authority-boundary.md",
                      ".github/workflows/deploy-dev.yml.bak", ".github/workflows/"):
            self.assertEqual(C.classify_entries(entries(*this_pr, extra), {}), C.DEPLOY_REQUIRED, extra)
        broker = sorted(C.BROKER_CANDIDATE_PATHS)[0]
        self.assertEqual(C.classify_entries(entries(*this_pr, broker), {}), C.DEPLOY_REQUIRED)
        self.assertTrue(all("*" not in path and not path.endswith("/") for path in C.CONTROL_ONLY_PATHS))

    def test_manual_dispatch_is_not_an_authority_boundary_proof_path(self):
        guard = job(DEPLOY, "deploy").split("    runs-on:", 1)[0]
        self.assertIn("github.event.workflow_run.conclusion == 'success'", guard)
        self.assertNotIn("workflow_dispatch", guard)
        for name in ("premerge_gate", "broker_candidate", "broker_postflight"):
            with self.subTest(job=name):
                source = job(DEPLOY, name)
                self.assertNotIn("deployer_authority_boundary_proof.sh", source)
                self.assertNotIn("google-github-actions/auth", source)
                self.assertNotIn("compute ssh", source)
        self.assertEqual(DEPLOY.count("uses: google-github-actions/auth@v3"), 1)
        self.assertEqual(DEPLOY.count("deployer_authority_boundary_proof.sh"), 1)

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
