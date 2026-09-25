"""15B2b-B1c static and Linux guards for the routine DEV deployer boundary."""

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/deploy-dev.yml").read_text(encoding="utf-8")
HELPER_PATH = ROOT / "scripts/dev_deployer/lilith-dev-deploy"
HELPER = HELPER_PATH.read_text(encoding="utf-8")
SUDOERS = (ROOT / "scripts/dev_deployer/sudoers-lilith-dev-deployer.in").read_text(encoding="utf-8")
INSTALLER = (ROOT / "scripts/dev_deployer/install_dev_deployer_boundary.sh").read_text(encoding="utf-8")
PROBE = (ROOT / "scripts/run_core_api_dev_durability_probe.py").read_text(encoding="utf-8")
BOOTSTRAP = (ROOT / "scripts/bootstrap_core_api_dev.sh").read_text(encoding="utf-8")

DEV_SA = "github-lilith-dev-deployer@lilith-agent-260823-27389.iam.gserviceaccount.com"
LEGACY_SA = "github-lilith-deployer@lilith-agent-260823-27389.iam.gserviceaccount.com"
ACTIVATION = "/etc/lilith-os-dev/canonical-runtime.json"


class RoutineWorkflowAuthorityTests(unittest.TestCase):
    def test_routine_identity_is_the_dev_only_deployer(self):
        self.assertIn(f"GCP_DEPLOY_SA: {DEV_SA}", WORKFLOW)
        self.assertEqual(len(re.findall(r"(?m)^\s+GCP_DEPLOY_SA: ", WORKFLOW)), 1)
        self.assertEqual(WORKFLOW.count("uses: google-github-actions/auth@v3"), 1)
        self.assertEqual(WORKFLOW.count(LEGACY_SA), 1)
        self.assertIn(f"GCP_LEGACY_PRIVILEGED_SA: {LEGACY_SA}", WORKFLOW)

    def test_no_arbitrary_root_execution(self):
        for forbidden in ("sudo bash", "sudo python", "sudo -u lilith", "sudo -n -u lilith python",
                          "compute scp", "bootstrap_core_api_dev", "deploy_core_api_dev_remote",
                          "base64.b64decode(sys.argv[1])"):
            self.assertNotIn(forbidden, WORKFLOW)
        allowed = (
            re.compile(r"sudo -n /usr/local/sbin/lilith-dev-deploy (deploy \$\{VALIDATED_SHA\}|status)"),
            re.compile(r"^\s*sudo -n -l$"),
            re.compile(r"^\s*deny sudo -n "),
            re.compile(r"^\s*if ! \. /usr/local/lib/lilith-dev-deploy/effective_sudo_proof\.sh; then$"),
            re.compile(r"^\s*lilith_dev_effective_sudo_proof sa_112096412008414111981 self \|\| fail=1$"),
        )
        for line in WORKFLOW.splitlines():
            if "sudo" in line.replace("/etc/sudoers.d", ""):
                with self.subTest(line=line.strip()):
                    self.assertTrue(any(p.search(line) for p in allowed))

    def test_routine_workflow_never_logs_into_prod(self):
        self.assertNotIn("GCP_PROD_INSTANCE", WORKFLOW)
        self.assertNotIn("audit_core_api_production_read_only", WORKFLOW)
        for line in WORKFLOW.splitlines():
            if "lilith-01" in line:
                with self.subTest(line=line.strip()):
                    self.assertIn("testIamPermissions", line)
        for ssh in re.findall(r"gcloud compute ssh (\S+)", WORKFLOW):
            self.assertEqual(ssh, '"${GCP_INSTANCE}"')
        self.assertIn("GCP_INSTANCE: lilith-dev-01", WORKFLOW)

    def test_every_deploy_proves_the_boundary(self):
        self.assertIn('test "${legacy_code}" = 403', WORKFLOW)
        self.assertIn('test "${dev_code}" = 200', WORKFLOW)
        for name in ("prod_compute", "prod_iap", "prod_sa"):
            self.assertIn(f"test \"${{{name}}}\" = '[]'", WORKFLOW)
        for probe in ("deny sudo -n true", "deny sudo -n bash -c true",
                      "deny sudo -n /usr/bin/python3 -c 0",
                      "/etc/lilith-memory-broker/b1b2b-stage3-a2-authorization.json",
                      "/run/lilith-memory/owner.sock", "/var/lib/lilith-memory-broker",
                      "/etc/lilith-os-dev/canonical-runtime.json"):
            self.assertIn(probe, WORKFLOW)

    def test_broker_validation_precedes_cloud_credentials(self):
        step = WORKFLOW.index("Validate broker candidate transiently before any cloud authentication")
        self.assertLess(step, WORKFLOW.index("uses: google-github-actions/auth@v3"))


class FixedHelperTests(unittest.TestCase):
    def test_helper_accepts_only_fixed_operations(self):
        self.assertIn('[[ "$#" -eq 2 && "$2" =~ ^[0-9a-f]{40}$ ]] || usage', HELPER)
        self.assertIn('[[ "$#" -eq 1 ]] || usage', HELPER)
        self.assertIn('readonly SERVICE_NAME="lilith-os-api-dev.service"', HELPER)
        self.assertIn("export PATH=/usr/sbin:/usr/bin:/sbin:/bin", HELPER)
        self.assertNotIn("eval", HELPER)
        for call in re.findall(r"systemctl (\w[\w-]*) ([^\n]*)", HELPER):
            with self.subTest(call=call):
                self.assertIn('"${SERVICE_NAME}"', call[1])

    def test_helper_never_touches_broker_stage3_activation_or_prod(self):
        for forbidden in ("memory-broker", "memory_broker", "stage3", "owner.sock", "sudoers",
                          "/etc/lilith-os-dev", "canonical-runtime", "lilith-01", "useradd",
                          "chown", "setfacl", "daemon-reload", "systemctl enable"):
            self.assertNotIn(forbidden, HELPER)

    def test_bundle_bytes_are_handled_as_the_application_user(self):
        for marker in ("as_app tar -x", "as_app \"${VENV_DIR}/bin/python\" \"${VERIFIER}\"",
                       "as_app \"${VENV_DIR}/bin/python\" -m pip install",
                       "as_app mv -Tf \"${next_link}\" \"${CURRENT_LINK}\"",
                       "head -c \"$((MAX_PAYLOAD_BYTES + 1))\""):
            self.assertIn(marker, HELPER)

    @unittest.skipUnless(sys.platform.startswith("linux"), "bash helper argument check")
    def test_helper_rejects_malformed_invocations_before_any_action(self):
        for argv in ([], ["deploy"], ["deploy", "a" * 39], ["deploy", "A" * 40],
                     ["deploy", "a" * 40, "extra"], ["status", "x"], ["restart"],
                     ["deploy", "../" + "a" * 37]):
            with self.subTest(argv=argv):
                result = subprocess.run(["bash", str(HELPER_PATH), *argv], capture_output=True,
                                        text=True, timeout=10, stdin=subprocess.DEVNULL)
                self.assertEqual(result.returncode, 2)
                self.assertIn("usage:", result.stderr)


class SudoersAndActivationTests(unittest.TestCase):
    def test_sudoers_rule_is_exactly_the_helper(self):
        rules = [line for line in SUDOERS.splitlines() if line and not line.startswith("#")]
        self.assertEqual(rules, [
            "@DEPLOYER@ ALL=(root) NOPASSWD: /usr/local/sbin/lilith-dev-deploy deploy *, "
            "/usr/local/sbin/lilith-dev-deploy status"])

    def test_installer_is_owner_only_and_never_activates(self):
        self.assertIn('[[ "${DEPLOYER}" =~ ^sa_[0-9]{10,30}$ ]]', INSTALLER)
        self.assertIn("visudo -cf", INSTALLER)
        self.assertIn('"canonicalLtmEnabled":false', INSTALLER)
        self.assertNotIn('"canonicalLtmEnabled":true', INSTALLER)
        self.assertNotIn("systemctl restart", INSTALLER)
        self.assertNotIn("memory-broker", INSTALLER.replace("/etc/lilith-memory-broker", ""))
        self.assertIn('test "$(stat -c \'%U:%G %a\' -- "${ACTIVATION_DIR}")" = "root:root 755"', INSTALLER)
        self.assertIn('test "$(stat -c \'%U:%G %a\' -- "${ACTIVATION_FILE}")" = "root:lilith 640"', INSTALLER)

    def test_activation_is_beyond_deployable_reach(self):
        self.assertIn(f'DEFAULT_CONFIG_PATH = Path("{ACTIVATION}")', PROBE)
        self.assertIn('("root", "lilith", "0640")', PROBE)
        self.assertIn("parent.st_uid != 0 or parent.st_mode & 0o022", PROBE)
        self.assertIn('ACTIVATION_DIR="/etc/lilith-os-dev"', BOOTSTRAP)
        self.assertIn('install -d -o root -g root -m 755 "${ACTIVATION_DIR}"', BOOTSTRAP)
        self.assertNotIn('DATA_DIR}/canonical-runtime.json', BOOTSTRAP)


if __name__ == "__main__":
    unittest.main()
