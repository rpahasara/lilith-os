"""15B2b-B1c-1A: deployment cannot fabricate ACCEPTED canonical activation.

Accepted activation is the output of the owner-installed verifier over an
owner-signed grant. These tests prove that everything reachable by replaceable
DEV code or the routine deployer -- advisory config, self-minted keys, grants in
lilith-writable locations, tampering, environment -- yields NOT_ACCEPTED.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER_PATH = ROOT / "scripts/dev_deployer/lilith_activation_verify.py"
VERIFIER_SOURCE = VERIFIER_PATH.read_text(encoding="utf-8")
HELPER = "\n".join(
    line for line in (ROOT / "scripts/dev_deployer/lilith-dev-deploy").read_text(encoding="utf-8").splitlines()
    if not line.lstrip().startswith("#")
)
WORKFLOW = (ROOT / ".github/workflows/deploy-dev.yml").read_text(encoding="utf-8")
INSTALLER = (ROOT / "scripts/dev_deployer/install_dev_deployer_boundary.sh").read_text(encoding="utf-8")
CONFIG = (ROOT / "services/core-api/lilith_memory/config.py").read_text(encoding="utf-8")

spec = importlib.util.spec_from_file_location("lilith_activation_verify", VERIFIER_PATH)
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)

SSH_KEYGEN = shutil.which("ssh-keygen")
MACHINE = "ae929170e6fa4c8ab9cc7b9547238d9d"
CAPABILITY = "canonical_memory.project_codename.mutate"


class StaticActivationBoundaryTests(unittest.TestCase):
    def test_verifier_is_isolated_from_replaceable_code_and_caller_input(self):
        # Linux passes the whole shebang tail as ONE argument: flags must be combined.
        self.assertTrue(VERIFIER_SOURCE.startswith("#!/usr/bin/python3 -IS\n"))
        for forbidden in ("lilith_memory", "os.environ", "getenv", "argparse", "sys.path"):
            self.assertNotIn(forbidden, VERIFIER_SOURCE)
        self.assertEqual(V.AUTHORITY_DIR, Path("/etc/lilith-os-dev/activation"))
        self.assertEqual(V.SSH_KEYGEN, "/usr/bin/ssh-keygen")
        self.assertIn('env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"}', VERIFIER_SOURCE)
        self.assertIn("if sys.argv[1:]:", VERIFIER_SOURCE)
        self.assertEqual(V.verify.__defaults__, (V.AUTHORITY_DIR, V.MACHINE_ID))
        self.assertEqual(V.verify.__kwdefaults__["uid"], 0)

    def test_advisory_config_is_never_an_input_to_acceptance(self):
        body = VERIFIER_SOURCE.split("def verify(", 1)[1].split("def _advisory_enabled", 1)[0]
        self.assertNotIn("ADVISORY_CONFIG", body)
        self.assertNotIn("canonical-runtime", body)

    def test_routine_deploy_has_no_activation_operation(self):
        for forbidden in ("activation", "ssh-keygen", "grant", "allowed-signers", "/etc/lilith-os-dev"):
            self.assertNotIn(forbidden, HELPER)
        self.assertNotIn("allowed-signers", INSTALLER)
        self.assertNotIn("ssh-keygen -Y sign", WORKFLOW + INSTALLER)
        self.assertIn('"ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT "*) ;;', WORKFLOW)
        self.assertIn("/etc/lilith-os-dev/activation/allowed-signers", WORKFLOW)

    def test_app_config_loader_remains_advisory_and_unprivileged(self):
        # The replaceable loader never names the authority directory, so no app
        # change can be mistaken for the enforcement point.
        self.assertNotIn("/etc/lilith-os-dev/activation", CONFIG)


@unittest.skipUnless(sys.platform.startswith("linux") and os.path.exists("/usr/bin/python3"),
                     "needs Linux /usr/bin/python3")
class InstalledExecutableTests(unittest.TestCase):
    def test_verifier_executes_through_its_real_shebang_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            installed = Path(tmp) / "lilith-activation-verify"
            shutil.copyfile(VERIFIER_PATH, installed)
            os.chmod(installed, 0o755)
            result = subprocess.run([str(installed)], capture_output=True, text=True, timeout=20,
                                    env={"PATH": "/usr/bin:/bin"}, stdin=subprocess.DEVNULL)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertRegex(result.stdout, r"^ACTIVATION=NOT_ACCEPTED reason=[A-Z_]+ advisoryConfigEnabled=")
            if not Path("/etc/lilith-os-dev").exists():
                self.assertIn("reason=AUTHORITY_DIRECTORY_ABSENT", result.stdout)
            rejected = subprocess.run([str(installed), "--authority-dir", tmp], capture_output=True,
                                      text=True, timeout=20, stdin=subprocess.DEVNULL)
            self.assertEqual(rejected.returncode, 2)


@unittest.skipUnless(sys.platform.startswith("linux") and SSH_KEYGEN, "needs Linux ssh-keygen")
class ActivationAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.keys = base / "keys"
        self.keys.mkdir(mode=0o700)
        self.parent = base / "etc/lilith-os-dev"
        self.parent.mkdir(parents=True)
        os.chmod(self.parent, 0o755)
        self.authority = self.parent / "activation"
        self.authority.mkdir(mode=0o755)
        os.chmod(self.authority, 0o755)
        self.machine = base / "machine-id"
        self.machine.write_text(MACHINE + "\n", encoding="ascii")
        self.owner = self._key("owner")
        self.attacker = self._key("lilith")
        self._write(V.SIGNERS, f'{V.IDENTITY} namespaces="{V.NAMESPACE}" {self._pub(self.owner)}\n')
        self.uid = os.getuid()

    def tearDown(self):
        self.tmp.cleanup()

    def _key(self, name):
        path = self.keys / name
        subprocess.run([SSH_KEYGEN, "-q", "-t", "ed25519", "-N", "", "-f", str(path)], check=True)
        return path

    def _pub(self, key):
        return Path(str(key) + ".pub").read_text(encoding="ascii").strip()

    def _write(self, name, text):
        path = self.authority / name
        path.write_text(text, encoding="utf-8")
        os.chmod(path, 0o644)
        return path

    def _grant(self, **changes):
        now = int(time.time())
        grant = {"schema": V.SCHEMA, "environment": "dev", "hostMachineId": MACHINE,
                 "capabilities": [CAPABILITY], "grantId": "0123456789abcdef0123456789abcdef",
                 "notBefore": now - 60, "notAfter": now + 3600}
        grant.update(changes)
        return json.dumps(grant, sort_keys=True)

    def _sign(self, key, namespace=V.NAMESPACE):
        grant = self.authority / V.GRANT
        sig = self.authority / V.SIGNATURE
        if sig.exists():
            sig.unlink()
        subprocess.run([SSH_KEYGEN, "-q", "-Y", "sign", "-f", str(key), "-n", namespace, str(grant)],
                       check=True, capture_output=True)
        os.chmod(sig, 0o644)

    def _verify(self, **kwargs):
        return V.verify(self.authority, self.machine, uid=kwargs.pop("uid", self.uid),
                        ssh_keygen=SSH_KEYGEN, **kwargs)

    def _rejected(self, reason, **kwargs):
        with self.assertRaises(V.NotAccepted) as caught:
            self._verify(**kwargs)
        self.assertEqual(caught.exception.reason, reason)

    def test_owner_signed_grant_is_the_only_accepted_state(self):
        self._write(V.GRANT, self._grant())
        self._sign(self.owner)
        accepted = self._verify()
        self.assertEqual(accepted["capabilities"], [CAPABILITY])

    def test_no_grant_means_not_accepted_even_if_advisory_config_enables(self):
        (self.parent / "canonical-runtime.json").write_text(json.dumps(
            {"schemaVersion": 1, "canonicalLtmEnabled": True, "activeCapabilities": [CAPABILITY]}))
        self._rejected("GRANT_ABSENT")

    def test_lilith_minted_key_cannot_produce_accepted_activation(self):
        self._write(V.GRANT, self._grant())
        self._sign(self.attacker)
        self._rejected("SIGNATURE_INVALID")

    def test_owner_key_signature_outside_activation_namespace_is_rejected(self):
        self._write(V.GRANT, self._grant())
        self._sign(self.owner, namespace="file")
        self._rejected("SIGNATURE_INVALID")

    def test_tampering_after_owner_signature_is_rejected(self):
        self._write(V.GRANT, self._grant())
        self._sign(self.owner)
        self._write(V.GRANT, self._grant(notAfter=int(time.time()) + 10 ** 8))
        self._rejected("SIGNATURE_INVALID")

    def test_authority_in_a_location_not_owned_by_the_authority_uid_is_rejected(self):
        # Models /etc/lilith-os-dev/activation owned by lilith or the deployer.
        self._write(V.GRANT, self._grant())
        self._sign(self.owner)
        self._rejected("UNTRUSTED_AUTHORITY_PATH", uid=self.uid + 1)

    def test_group_or_world_writable_authority_is_rejected(self):
        self._write(V.GRANT, self._grant())
        self._sign(self.owner)
        for target in (self.parent, self.authority, self.authority / V.SIGNERS, self.authority / V.GRANT):
            with self.subTest(target=target.name):
                mode = target.stat().st_mode & 0o777
                os.chmod(target, mode | 0o022)
                self._rejected("UNTRUSTED_AUTHORITY_PATH")
                os.chmod(target, mode)

    def test_symlinked_grant_is_rejected(self):
        real = self.keys / "grant.json"
        real.write_text(self._grant(), encoding="utf-8")
        (self.authority / V.GRANT).symlink_to(real)
        self._rejected("UNTRUSTED_AUTHORITY_PATH")

    def test_missing_owner_signer_is_rejected(self):
        self._write(V.GRANT, self._grant())
        self._sign(self.owner)
        (self.authority / V.SIGNERS).unlink()
        self._rejected("OWNER_SIGNER_ABSENT")

    def test_grant_scope_is_bound_to_dev_host_capability_and_time(self):
        now = int(time.time())
        for changes, reason in (
            ({"environment": "prod"}, "GRANT_ENVIRONMENT_MISMATCH"),
            ({"hostMachineId": "0" * 32}, "GRANT_HOST_MISMATCH"),
            ({"capabilities": ["canonical_memory.everything"]}, "GRANT_CAPABILITY_INVALID"),
            ({"capabilities": []}, "GRANT_CAPABILITY_INVALID"),
            ({"notBefore": now - 7200, "notAfter": now - 3600}, "GRANT_NOT_CURRENT"),
            ({"schema": "other"}, "GRANT_MALFORMED"),
        ):
            with self.subTest(reason=reason):
                self._write(V.GRANT, self._grant(**changes))
                self._sign(self.owner)
                self._rejected(reason)

    def test_extra_fields_cannot_smuggle_authority(self):
        self._write(V.GRANT, self._grant()[:-1] + ', "canonicalLtmEnabled": true}')
        self._sign(self.owner)
        self._rejected("GRANT_MALFORMED")


if __name__ == "__main__":
    unittest.main()
