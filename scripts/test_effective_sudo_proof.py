"""15B2b-B1c effective sudo proof: materialized and not-yet-materialized users.

Stub tests cover every branch wherever Linux bash exists. The real-sudo tests
run only on an ephemeral GitHub-hosted runner (they create a throwaway user and
sudoers drop-in, then remove them) to pin the exact `sudo -l` output format.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "scripts/dev_deployer/effective_sudo_proof.sh"
TEMPLATE = (ROOT / "scripts/dev_deployer/sudoers-lilith-dev-deployer.in").read_text(encoding="utf-8")
INSTALLER = (ROOT / "scripts/dev_deployer/install_dev_deployer_boundary.sh").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/deploy-dev.yml").read_text(encoding="utf-8")
USER = "sa_112096412008414111981"
EXACT = ("(root) NOPASSWD: /usr/local/sbin/lilith-dev-deploy deploy *, "
         "/usr/local/sbin/lilith-dev-deploy status")
LINUX_BASH = sys.platform.startswith("linux") and shutil.which("bash") is not None
EPHEMERAL_ROOT = (os.environ.get("GITHUB_ACTIONS") == "true"
                  and os.environ.get("LILITH_EPHEMERAL_RUNNER_ROOT_TESTS") == "1")


def listing(user: str, *rules: str) -> str:
    head = (f"Matching Defaults entries for {user} on lilith-dev-01:\n"
            "    env_reset, mail_badpass, use_pty\n\n")
    if not rules:
        return f"User {user} is not allowed to run sudo on lilith-dev-01.\n"
    body = "".join(f"    {rule}\n" for rule in rules)
    return head + f"User {user} may run the following commands on lilith-dev-01:\n" + body


class StaticWiringTests(unittest.TestCase):
    def test_installer_defers_only_through_the_shared_owner_mode_proof(self):
        self.assertIn('lilith_dev_effective_sudo_proof "${DEPLOYER}" owner', INSTALLER)
        self.assertNotIn('sudo -n -l -U "${DEPLOYER}"', INSTALLER)
        self.assertIn('install -o root -g root -m 0644 "${SOURCE_DIR}/effective_sudo_proof.sh" "${SUDO_PROOF}"', INSTALLER)
        self.assertIn('cmp -s -- "${rendered}" "${SUDOERS}"', INSTALLER)
        self.assertIn('test "$(stat -c \'%U:%G %a\' -- "${SUDOERS}")" = "root:root 440"', INSTALLER)
        self.assertIn("another sudoers entry names the deployer", INSTALLER)
        self.assertNotIn("useradd", INSTALLER)

    def test_template_and_proof_expect_the_same_single_rule(self):
        rules = [line for line in TEMPLATE.splitlines() if line and not line.startswith("#")]
        self.assertEqual(rules, [f"@DEPLOYER@ ALL=(root) NOPASSWD: /usr/local/sbin/lilith-dev-deploy deploy *, "
                                 "/usr/local/sbin/lilith-dev-deploy status"])
        self.assertIn(f"LILITH_DEV_EXPECTED_SUDO='{EXACT}'", PROOF.read_text(encoding="utf-8"))

    def test_routine_workflow_proves_self_mode_before_deploying(self):
        proof = WORKFLOW.index("lilith_dev_effective_sudo_proof sa_112096412008414111981 self || fail=1")
        self.assertLess(proof, WORKFLOW.index("      - name: Deploy through the fixed root-owned DEV helper"))
        self.assertLess(proof, WORKFLOW.index("      - name: Package exact-SHA bundle for the fixed DEV helper"))
        self.assertIn('echo "SUDO_EFFECTIVE_PROOF=FAIL reason=PROOF_CONTROL_MISSING"', WORKFLOW)


@unittest.skipUnless(LINUX_BASH, "needs Linux bash")
class StubbedProofTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        self._stub("getent", '[ "${STUB_RESOLVABLE}" = 1 ] && echo "$3:x:1:1::/home/$3:/bin/bash" || exit 2')
        self._stub("id", 'echo "${STUB_ID}"')
        self._stub("sudo", 'cat "${STUB_LISTING}"; exit "${STUB_SUDO_RC:-0}"')

    def tearDown(self):
        self.tmp.cleanup()

    def _stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/bash\n" + body + "\n", encoding="utf-8")
        path.chmod(0o755)

    def run_proof(self, mode, *, resolvable=True, effective=USER, text=None, rc=0):
        listing_file = Path(self.tmp.name) / "listing.txt"
        listing_file.write_text(text if text is not None else listing(USER, EXACT), encoding="utf-8")
        env = {"PATH": f"{self.bin}:/usr/bin:/bin", "STUB_RESOLVABLE": "1" if resolvable else "0",
               "STUB_ID": effective, "STUB_LISTING": str(listing_file), "STUB_SUDO_RC": str(rc)}
        return subprocess.run(["bash", "-c", f'. "{PROOF}"; lilith_dev_effective_sudo_proof "$1" "$2"',
                               "_", USER, mode], capture_output=True, text=True, env=env, timeout=10)

    def assertOutcome(self, result, rc, marker):
        self.assertEqual(result.returncode, rc, result.stdout + result.stderr)
        self.assertIn(marker, result.stdout)

    # User already materialized.
    def test_materialized_exact_helper_passes_in_owner_and_self_modes(self):
        self.assertOutcome(self.run_proof("owner"), 0, "SUDO_EFFECTIVE_PROOF=PASS")
        self.assertOutcome(self.run_proof("self"), 0, "SUDO_EFFECTIVE_PROOF=PASS")

    def test_materialized_generic_root_fails(self):
        for mode in ("owner", "self"):
            self.assertOutcome(self.run_proof(mode, text=listing(USER, "(ALL) NOPASSWD: ALL")), 1,
                               "reason=UNEXPECTED_SUDO_RULES")
            self.assertOutcome(self.run_proof(mode, text=listing(USER, "(ALL : ALL) NOPASSWD: ALL")), 1,
                               "reason=UNEXPECTED_SUDO_RULES")

    def test_materialized_interpreter_or_extra_rule_fails(self):
        for extra in ("(root) NOPASSWD: /usr/bin/python3", "(root) NOPASSWD: /bin/bash",
                      "(lilith) NOPASSWD: ALL", "(root) NOPASSWD: /usr/bin/systemctl restart lilith-memory-broker.service"):
            with self.subTest(extra=extra):
                self.assertOutcome(self.run_proof("owner", text=listing(USER, EXACT, extra)), 1,
                                   "reason=UNEXPECTED_SUDO_RULES")
                self.assertOutcome(self.run_proof("self", text=listing(USER, extra)), 1,
                                   "reason=UNEXPECTED_SUDO_RULES")

    def test_materialized_without_any_rule_fails(self):
        self.assertOutcome(self.run_proof("owner", text=listing(USER), rc=1), 1, "reason=UNEXPECTED_SUDO_RULES")

    def test_self_mode_rejects_a_different_effective_user(self):
        self.assertOutcome(self.run_proof("self", effective="sa_114167104212223707830"), 1,
                           "reason=UNEXPECTED_EFFECTIVE_USER")

    # User not yet materialized.
    def test_not_materialized_is_deferred_in_owner_mode_only(self):
        result = self.run_proof("owner", resolvable=False, text=listing(USER, "(ALL) NOPASSWD: ALL"))
        self.assertOutcome(result, 0,
                           f"SUDO_EFFECTIVE_PROOF=DEFERRED reason=OSLOGIN_USER_NOT_MATERIALIZED user={USER}")
        self.assertNotIn("PASS", result.stdout)

    def test_not_materialized_after_login_fails_in_self_mode(self):
        self.assertOutcome(self.run_proof("self", resolvable=False), 1,
                           "reason=IDENTITY_NOT_RESOLVABLE_AFTER_LOGIN")

    def test_unknown_mode_fails(self):
        self.assertOutcome(self.run_proof("anything"), 1, "reason=INVALID_MODE")


@unittest.skipUnless(LINUX_BASH and EPHEMERAL_ROOT, "real sudo only on an ephemeral GitHub runner")
class RealSudoOnEphemeralRunnerTests(unittest.TestCase):
    """Pins the parser to real sudo output using a throwaway user and drop-in."""

    def setUp(self):
        self.user = "b1cprobe" + uuid.uuid4().hex[:8]
        self.dropins = []
        self.proof_dir = tempfile.TemporaryDirectory(dir="/tmp")
        os.chmod(self.proof_dir.name, 0o755)
        self.proof = Path(self.proof_dir.name) / "effective_sudo_proof.sh"
        shutil.copyfile(PROOF, self.proof)
        os.chmod(self.proof, 0o644)
        self._root("useradd", "--system", "--no-create-home", "--shell", "/usr/sbin/nologin", self.user)
        self._install("zz-lilith-b1c-" + self.user, TEMPLATE.replace("@DEPLOYER@", self.user))

    def tearDown(self):
        for path in self.dropins:
            subprocess.run(["sudo", "-n", "rm", "-f", path], check=False)
        subprocess.run(["sudo", "-n", "userdel", self.user], check=False)
        self.proof_dir.cleanup()

    def _root(self, *argv):
        subprocess.run(["sudo", "-n", *argv], check=True, capture_output=True, timeout=30)

    def _install(self, name, text):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".sudoers") as handle:
            handle.write(text)
        target = f"/etc/sudoers.d/{name}"
        self._root("visudo", "-cf", handle.name)
        self._root("install", "-o", "root", "-g", "root", "-m", "0440", handle.name, target)
        os.unlink(handle.name)
        self.dropins.append(target)

    def _proof(self, user, mode, as_user=None):
        prefix = ["sudo", "-n", "-u", as_user] if as_user else ["sudo", "-n"]
        return subprocess.run([*prefix, "bash", "-c", f'. "{self.proof}"; lilith_dev_effective_sudo_proof "$1" "$2"',
                               "_", user, mode], capture_output=True, text=True, timeout=30)

    def test_real_materialized_user_passes_owner_and_self_mode(self):
        owner = self._proof(self.user, "owner")
        self.assertEqual(owner.returncode, 0, owner.stdout + owner.stderr)
        self.assertIn("SUDO_EFFECTIVE_PROOF=PASS", owner.stdout)
        self_mode = self._proof(self.user, "self", as_user=self.user)
        self.assertEqual(self_mode.returncode, 0, self_mode.stdout + self_mode.stderr)
        self.assertIn("SUDO_EFFECTIVE_PROOF=PASS", self_mode.stdout)

    def test_real_broader_rule_fails(self):
        self._install("zz-lilith-b1c-broad-" + self.user, f"{self.user} ALL=(ALL) NOPASSWD: ALL\n")
        result = self._proof(self.user, "owner")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("reason=UNEXPECTED_SUDO_RULES", result.stdout)

    def test_real_unmaterialized_user_is_deferred(self):
        absent = "sa_" + str(uuid.uuid4().int)[:21]
        result = self._proof(absent, "owner")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("reason=OSLOGIN_USER_NOT_MATERIALIZED", result.stdout)


if __name__ == "__main__":
    unittest.main()
