"""Linux-only proof of the snapshot process's Lilith-relevant read/write boundary."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import trusted_broker_snapshot_invocation as invocation
from scripts import trusted_broker_snapshot as tool
from scripts.test_broker_dev_lifecycle import accepted_fixture
from scripts.test_trusted_broker_snapshot import fixture_release, sudo_entries, encode_sudo


PROBE = r'''
import importlib.util, json, os, sys
from pathlib import Path
source, owner, broker, config = sys.argv[1:]
spec = importlib.util.spec_from_file_location("snapshot_tool", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.verify_confinement()
result = {}
for name, filename in (("owner", owner), ("broker", broker), ("config", config)):
    path = Path(filename)
    content = path.read_bytes()
    try:
        with path.open("ab") as output:
            output.write(b"forbidden")
    except OSError:
        result[name] = content.decode("ascii")
    else:
        raise SystemExit("WRITE_SUCCEEDED:" + name)
print(json.dumps(result, sort_keys=True))
'''


ACCOUNT_PROBE = r'''
import importlib.util, json, os, subprocess, sys, types
from importlib.machinery import SourceFileLoader
from pathlib import Path
source, control_path, fixture_path, protected_path = sys.argv[1:]
spec = importlib.util.spec_from_loader("snapshot_tool", SourceFileLoader("snapshot_tool", source))
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
tool.CONTROL = Path(control_path)
tool.verify_runtime = lambda runtime: None  # CI runtime is not the pinned DEV runtime.
fixture = json.loads(Path(fixture_path).read_text())
original_lifecycle = tool._lifecycle
original_read_text = Path.read_text
original_exists = Path.exists
def lifecycle_fixture(release_dir):
    module = original_lifecycle(release_dir)
    module._host = module.expected_host
    identities = {
        "lilith-memory-broker": (999, 987, [987]),
        "lilith-memory-relay": (997, 986, [986, 988]),
    }
    def getpwnam(name):
        uid, gid, groups = identities[name]
        return types.SimpleNamespace(pw_uid=uid, pw_gid=gid,
                                     pw_dir="/nonexistent", pw_shell="/usr/sbin/nologin")
    def getgrnam(name):
        if name == "lilith-memory-ipc":
            return types.SimpleNamespace(gr_gid=988, gr_mem=["lilith-memory-relay"])
        raise KeyError(name)
    module.pwd = types.SimpleNamespace(getpwnam=getpwnam)
    module.grp = types.SimpleNamespace(getgrnam=getgrnam)
    module.os.getgrouplist = lambda name, gid: identities[name][2]
    def read_text(path, *args, **kwargs):
        if str(path) == "/etc/passwd":
            return "".join(f"{name}:x:{uid}:{gid}::/nonexistent:/usr/sbin/nologin\n"
                           for name, (uid, gid, _) in identities.items())
        if str(path) == "/etc/shadow":
            return "".join(f"{name}:!:0:0:99999:7:::\n" for name in identities)
        return original_read_text(path, *args, **kwargs)
    def exists(path):
        if str(path).startswith(("/home/lilith-memory-", "/etc/ssh/authorized_keys/lilith-memory-")):
            return False
        return original_exists(path)
    Path.read_text = read_text
    Path.exists = exists
    def no_nested_sudo(*args, **kwargs):
        raise RuntimeError("NESTED_SUDO_CALLED")
    module.subprocess.run = no_nested_sudo
    def collect(observation):
        accounts = module._accounts(observation)
        assert accounts == fixture["accounts"], accounts
        return fixture
    module.collect_accepted = collect
    return module
tool._lifecycle = lifecycle_fixture
sys.argv = [source, tool.OPERATION]
tool.main()
try:
    with Path(protected_path).open("ab") as output:
        output.write(b"forbidden")
except OSError:
    print("WRITE_DENIED", file=sys.stderr)
else:
    raise SystemExit("WRITE_SUCCEEDED")
'''


BROKER_PROCESS_PROBE = r'''
import errno, importlib.util, json, os, sys
from pathlib import Path
source, pid_text = sys.argv[1:]
pid = int(pid_text)
spec = importlib.util.spec_from_file_location("broker_lifecycle", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
# These exact reads failed on DEV without CAP_SYS_PTRACE. Prove the test has
# reproduced that boundary before exercising the real validator functions.
denied = []
for name in ("exe", "cwd"):
    try:
        os.readlink(f"/proc/{pid}/{name}")
    except OSError as exc:
        if exc.errno != errno.EACCES:
            raise
        denied.append(name)
    else:
        raise SystemExit("BROKER_PTRACE_BOUNDARY_NOT_REPRODUCED:" + name)
print(json.dumps({"denied": denied, "process": module._broker_process(pid),
                  "incarnation": module._process_incarnation(pid)}, sort_keys=True))
'''


@unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux systemd mount namespace")
class LinuxConfinementTests(unittest.TestCase):
    def test_real_broker_observation_without_ptrace_authority(self):
        if os.geteuid() != 0:
            self.fail("Linux broker-process proof must run as root in credential-free CI")
        source = Path(__file__).with_name("verify_broker_dev_lifecycle.py")
        broker = subprocess.Popen(
            ["/usr/bin/python3", "-I", "-B", "-c", "import time; time.sleep(60)"],
            user=65534, group=65534, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            self.assertIsNone(broker.poll())
            command = (
                "/usr/bin/systemd-run", "--pipe", "--wait", "--collect", "--quiet",
                *("--property=" + item for item in invocation.PROPERTIES),
                "--", "/usr/bin/python3", "-I", "-B", "-c", BROKER_PROCESS_PROBE,
                str(source), str(broker.pid),
            )
            result = subprocess.run(command, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            proof = json.loads(result.stdout)
            self.assertEqual(proof["denied"], ["exe", "cwd"])
            self.assertEqual(proof["process"]["pid"], broker.pid)
            self.assertEqual(proof["process"]["uid"], [65534] * 4)
            self.assertEqual(proof["process"]["gid"], [65534] * 4)
            self.assertNotIn("exe", proof["process"])
            self.assertNotIn("cwd", proof["process"])
            self.assertEqual(proof["incarnation"]["pid"], broker.pid)
            self.assertGreater(proof["incarnation"]["startTicks"], 0)
        finally:
            broker.terminate()
            try:
                broker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                broker.kill()
                broker.wait(timeout=5)

    def test_real_snapshot_cli_account_path_has_no_nested_sudo(self):
        if os.geteuid() != 0:
            self.fail("Linux account-path proof must run as root in credential-free CI")
        with tempfile.TemporaryDirectory(prefix="lilith-snapshot-ci-", dir="/opt") as artifact, \
             tempfile.TemporaryDirectory(prefix="lilith-snapshot-ci-", dir="/etc") as config:
            Path(artifact).chmod(0o755)
            control = Path(artifact, "control")
            releases = control / "releases"
            releases.mkdir(parents=True)
            control.chmod(0o755)
            releases.chmod(0o755)
            folder, release_id = fixture_release(releases)
            (control / "current").symlink_to("releases/" + release_id)
            fixture_path = Path(artifact, "accepted.json")
            fixture_path.write_text(json.dumps(accepted_fixture(), sort_keys=True))
            protected = Path(config, "protected.json")
            protected.write_bytes(b"accepted-config")
            before = hashlib.sha256(protected.read_bytes()).hexdigest()
            command = (
                "/usr/bin/systemd-run", "--pipe", "--wait", "--collect", "--quiet",
                *("--property=" + item for item in invocation.PROPERTIES),
                "--setenv=" + invocation.SUDO_ENV + "=" + encode_sudo(sudo_entries()),
                "--", "/usr/bin/python3", "-I", "-B", "-c", ACCOUNT_PROBE,
                str(folder / "bin/lilith-broker-dev-snapshot"), str(control),
                str(fixture_path), str(protected),
            )
            result = subprocess.run(command, capture_output=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            self.assertIn(tool.FRAME, result.stdout)
            self.assertIn(b"WRITE_DENIED", result.stderr)
            self.assertEqual(hashlib.sha256(protected.read_bytes()).hexdigest(), before)

    def test_read_required_evidence_and_deny_representative_writes(self):
        if os.geteuid() != 0:
            self.fail("Linux confinement proof must run as root in credential-free CI")
        source = Path(__file__).with_name("trusted_broker_snapshot.py")
        with tempfile.TemporaryDirectory(prefix="lilith-snapshot-ci-", dir="/var/lib") as state, \
             tempfile.TemporaryDirectory(prefix="lilith-snapshot-ci-", dir="/opt") as artifact, \
             tempfile.TemporaryDirectory(prefix="lilith-snapshot-ci-", dir="/etc") as config:
            owner = Path(state, "owner_control.db")
            broker = Path(artifact, "release")
            settings = Path(config, "dev.json")
            for path, content in ((owner, b"synthetic-owner"), (broker, b"reviewed-release"),
                                  (settings, b"accepted-config")):
                path.write_bytes(content)
                path.chmod(0o600)
            os.chown(owner, 999, 987)
            before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in (owner, broker, settings)}
            command = (
                "/usr/bin/systemd-run", "--pipe", "--wait", "--collect", "--quiet",
                *("--property=" + item for item in invocation.PROPERTIES),
                "--", "/usr/bin/python3", "-B", "-c", PROBE,
                str(source), str(owner), str(broker), str(settings),
            )
            result = subprocess.run(command, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"owner": "synthetic-owner"', result.stdout)
            self.assertIn('"broker": "reviewed-release"', result.stdout)
            self.assertIn('"config": "accepted-config"', result.stdout)
            after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in (owner, broker, settings)}
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
