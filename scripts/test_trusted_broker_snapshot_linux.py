"""Linux-only proof of the snapshot process's Lilith-relevant read/write boundary."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import trusted_broker_snapshot_invocation as invocation


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


@unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux systemd mount namespace")
class LinuxConfinementTests(unittest.TestCase):
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
