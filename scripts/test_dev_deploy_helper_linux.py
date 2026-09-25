"""15B2b-B1c behavioral regressions for the fixed DEV deploy helper (Linux).

The real helper runs in a sandbox: only its fixed paths are redirected to a
temporary tree, and runuser/systemctl/flock/curl/journalctl plus the venv
python are stubs that record what happened. This reproduces the first merged
DEV deploy failure (private OS Login cwd + EXIT trap reading function locals)
and pins the fix: controlled cwd, global state, rollback before activation.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/dev_deployer/lilith-dev-deploy"
FAILED_HELPER_COMMIT = "def790c0e393c2b5bd1e50f417048a298f9dafdb"
NEW_SHA = "b9aae0f693825b64fc203a4c85ec51cd47e58f19"
OLD_SHA = "4c450633895667e5aaa7ef70561222d2c94eaa09"

STUBS = {
    "runuser": 'while [ "$1" != "--" ]; do shift; done; shift; exec "$@"',
    "flock": "exit 0",
    "journalctl": "exit 0",
    "curl": 'echo "curl $*" >> "$SANDBOX/log"; [ "${STUB_HEALTH_RC:-0}" = 0 ] && echo ok',
    "systemctl": '''echo "systemctl $*" >> "$SANDBOX/log"
case "$1" in
  is-enabled) echo enabled ;;
  is-active) exit 0 ;;
  show) case "$*" in *"--value"*) cat "$SANDBOX/pid" ;; *) echo "MainPID=$(cat "$SANDBOX/pid")" ;; esac ;;
  restart) echo $(( $(cat "$SANDBOX/pid") + 1 )) > "$SANDBOX/pid" ;;
esac''',
}
FAKE_PYTHON = '''#!/bin/bash
echo "python $*" >> "$SANDBOX/log"
case "$1" in
  -c) exec python3 "$@" ;;
  -m) exit 0 ;;
  */verify_core_api_bundle.py)
    while [ $# -gt 0 ]; do case "$1" in --destination) d="$2"; shift ;; --expected-sha) s="$2"; shift ;; esac; shift; done
    mkdir -p "$d/lilith_memory" "$d/tests"
    printf '{"candidateSha": "%s"}' "$s" > "$d/deployment-manifest.json"
    echo "bundle-digest" > "$d/.bundle-sha256"; : > "$d/app.py"; : > "$d/requirements.txt" ;;
  */run_core_api_dev_durability_probe.py)
    [ "$2" = prepare ] && exit "${STUB_PREPARE_RC:-0}"; exit 0 ;;
  *) echo "unexpected python $*" >&2; exit 98 ;;
esac
'''


def sandboxed(source: str, sandbox: Path) -> str:
    replacements = {
        r"^export PATH=/usr/sbin:/usr/bin:/sbin:/bin$": f"export PATH={sandbox}/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        r'^readonly APP_ROOT="[^"]*"$': f'readonly APP_ROOT="{sandbox}/app"',
        r'^readonly LIB_DIR="[^"]*"$': f'readonly LIB_DIR="{sandbox}/lib"',
        r'^readonly LOCK_PATH="[^"]*"$': f'readonly LOCK_PATH="{sandbox}/lock"',
        r'^readonly WORK_PARENT="[^"]*"$': f'readonly WORK_PARENT="{sandbox}/vartmp"',
        r'^  work="\$\(mktemp -d /var/tmp/': f'  work="$(mktemp -d {sandbox}/vartmp/',
    }
    for pattern, value in replacements.items():
        source = re.sub(pattern, value.replace("\\", "\\\\"), source, flags=re.M)
    return source.replace("-user root", f"-user {os.getuid()}")


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("bash"), "needs Linux bash")
class DeployHelperBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.box = Path(self.tmp.name)
        for name in ("bin", "lib", "vartmp", "app/releases", "app/api-venv/bin", "private-home"):
            (self.box / name).mkdir(parents=True)
        for name, body in STUBS.items():
            self._exe(self.box / "bin" / name, "#!/bin/bash\n" + body + "\n")
        self._exe(self.box / "app/api-venv/bin/python", FAKE_PYTHON)
        (self.box / "lib/verify_core_api_bundle.py").write_text("# pinned\n")
        (self.box / "lib/run_core_api_dev_durability_probe.py").write_text("# pinned\n")
        old = self.box / "app/releases" / OLD_SHA
        old.mkdir()
        (old / "deployment-manifest.json").write_text(json.dumps({"candidateSha": OLD_SHA}))
        (self.box / "app/current").symlink_to(old)
        (self.box / "pid").write_text("100\n")
        (self.box / "log").write_text("")
        self.payload = self.box / "payload.tar"
        with tarfile.open(self.payload, "w") as tar:
            for name in ("lilith-core-api.tar.gz", "lilith-core-api.attestation.json"):
                path = self.box / name
                path.write_text(name)
                tar.add(path, arcname=name)

    def tearDown(self):
        os.chmod(self.box / "private-home", 0o700)
        self.tmp.cleanup()

    def _exe(self, path, text):
        path.write_text(text)
        path.chmod(0o755)

    def run_helper(self, source=None, *, private_cwd=False, env=None):
        helper = self.box / "helper.sh"
        helper.write_text(sandboxed(source or HELPER.read_text(encoding="utf-8"), self.box))
        cwd = self.box / ("private-home" if private_cwd else "vartmp")
        # Model the OS Login home: the helper starts in a cwd it cannot traverse.
        enter = f'cd "{cwd}" && ' + ("chmod 000 . && " if private_cwd else "")
        with open(self.payload, "rb") as stdin:
            return subprocess.run(["bash", "-c", enter + f'exec bash "{helper}" deploy {NEW_SHA}'],
                                  stdin=stdin, capture_output=True, text=True, timeout=60,
                                  env={"PATH": "/usr/bin:/bin", "SANDBOX": str(self.box), **(env or {})})

    def current(self):
        return Path(os.readlink(self.box / "app/current")).name

    def log(self):
        return (self.box / "log").read_text()

    def assertNoLeftovers(self):
        self.assertEqual([p.name for p in (self.box / "app/releases").iterdir() if ".staging." in p.name], [])
        self.assertEqual(list((self.box / "vartmp").iterdir()), [])

    def test_private_untraversable_cwd_now_deploys(self):
        result = self.run_helper(private_cwd=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Failed to restore initial working directory", result.stderr)
        self.assertIn("--- DEV DEPLOYMENT COMPLETE ---", result.stdout)
        self.assertEqual(self.current(), NEW_SHA)
        self.assertIn(f"systemctl restart lilith-os-api-dev.service", self.log())
        self.assertNoLeftovers()

    def test_clean_invocation_from_another_cwd_deploys(self):
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.current(), NEW_SHA)
        self.assertNoLeftovers()

    def test_probe_preparation_failure_rolls_back_without_activation(self):
        result = self.run_helper(env={"STUB_PREPARE_RC": "1"})
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("unbound variable", result.stderr)
        self.assertIn("--- DEV BUNDLE ROLLBACK ---", result.stdout)
        self.assertEqual(self.current(), OLD_SHA)
        self.assertNotIn("systemctl restart", self.log())
        self.assertNotIn("systemctl stop", self.log())
        self.assertIn("run_core_api_dev_durability_probe.py cleanup", self.log())
        self.assertNoLeftovers()

    def test_health_failure_after_restart_restores_previous_release(self):
        result = self.run_helper(env={"STUB_HEALTH_RC": "1"})
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("unbound variable", result.stderr)
        self.assertEqual(self.current(), OLD_SHA)
        self.assertEqual(self.log().count("systemctl restart lilith-os-api-dev.service"), 2)
        self.assertNoLeftovers()

    def test_stale_artifacts_of_an_aborted_run_are_removed_under_lock(self):
        (self.box / f"app/releases/.{NEW_SHA}.staging.128584/release").mkdir(parents=True)
        (self.box / "vartmp/lilith-dev-deploy.AbCdEf12").mkdir()
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNoLeftovers()

    def test_failed_helper_reproduces_the_first_merged_deploy_failure(self):
        original = subprocess.run(["git", "-C", str(ROOT), "show",
                                   f"{FAILED_HELPER_COMMIT}:scripts/dev_deployer/lilith-dev-deploy"],
                                  capture_output=True, text=True)
        if original.returncode != 0:
            self.skipTest("failed helper revision unavailable in this checkout")
        result = self.run_helper(original.stdout, private_cwd=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Failed to restore initial working directory", result.stderr)
        self.assertIn("probe_prepared: unbound variable", result.stderr)
        self.assertEqual(self.current(), OLD_SHA)
        self.assertNotIn("systemctl restart", self.log())
        self.assertTrue(any(".staging." in p.name for p in (self.box / "app/releases").iterdir()))


class DeployHelperStaticTests(unittest.TestCase):
    SOURCE = HELPER.read_text(encoding="utf-8")

    def test_controlled_cwd_precedes_every_privilege_drop(self):
        self.assertLess(self.SOURCE.index("\ncd /\n"), self.SOURCE.index("as_app() {"))

    def test_trap_state_is_global_and_initialized(self):
        for name in ("CANDIDATE_SHA", "STAGING", "WORK", "PREVIOUS_RELEASE",
                     "SWITCHED", "RESTARTED", "PROBE_PREPARED", "COMPLETED"):
            self.assertRegex(self.SOURCE, rf"(?m)^{name}=")
        cleanup = self.SOURCE.split("cleanup() {", 1)[1].split("\n}\n", 1)[0]
        self.assertNotRegex(cleanup, r"\$\{?(probe_prepared|staging|work|candidate_sha|previous_release)\b")

    def test_switch_is_marked_before_it_happens_and_pid_checked_before_switch(self):
        self.assertLess(self.SOURCE.index("SWITCHED=1"), self.SOURCE.index('as_app mv -Tf "${next_link}" "${CURRENT_LINK}"'))
        self.assertLess(self.SOURCE.index('|| die "DEV service has no pre-restart PID"'), self.SOURCE.index("SWITCHED=1"))
        self.assertLess(self.SOURCE.index("PROBE_PREPARED=1"), self.SOURCE.index('"${PROBE}" prepare'))


if __name__ == "__main__":
    unittest.main()
