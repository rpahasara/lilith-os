"""15B2b-B1b-3e: both restart-boundary installers carry their pinned drop-in bytes in memory (TEST-ONLY, no host).

The live route runs tools through the pinned mb6 BOOT loader, which gives every module a synthetic `__file__`
(`<mb6-bundle:NAME>`), so no drop-in file exists beside them on DEV. Before this change `install` read its payload
from a path derived from `__file__` and failed there (WRB_1 attempt 2026-10-13, stopped before DEV contact).
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _p in (TOOLS, ROOT / "services/authority-dev"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import e19_p1b10_upgrade as E  # noqa: E402
import e19_witness_restart_boundary_install as W  # noqa: E402
import mb6_operator as M6  # noqa: E402
import mb11_restart_boundary as B  # noqa: E402
import mb11_restart_boundary_install as I  # noqa: E402

BUNDLE = ("mb11_restart_boundary", "mb11_restart_boundary_install", "e19_p1b10_upgrade", "e19_maintenance_observer",
          "e19_witness_restart_boundary_install")
PROBE = '''
import hashlib, json, sys
import e19_witness_restart_boundary_install as W
import mb11_restart_boundary as B


def main(argv):
    sys.stdout.write(json.dumps({
        "signer": {u: hashlib.sha256(B.candidate_bytes(u)).hexdigest() for u in B.DROPINS},
        "witness": {u: hashlib.sha256(W.candidate_bytes(u)).hexdigest() for u in W.UNITS},
        "files": [B.__file__, W.__file__, W.E.__file__],
        "sourceDirsExist": [B.DROPIN_ROOT.exists(), W.E.DROPIN_SOURCE.exists()]}, sort_keys=True))
    return 0
'''


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class InMemoryPayloadTests(unittest.TestCase):
    def test_embedded_bytes_are_exactly_the_approved_files(self):
        for unit, (name, pin) in B.DROPINS.items():
            self.assertEqual(B.candidate_bytes(unit), (B.DROPIN_ROOT / f"{unit}.d" / name).read_bytes())
            self.assertEqual(sha(B.DROPIN_BYTES[unit]), pin)
        for unit, (name, pin) in W.DROPINS.items():
            self.assertEqual(W.candidate_bytes(unit), (E.DROPIN_SOURCE / f"{unit}.d" / name).read_bytes())
            self.assertEqual(sha(W.DROPIN_BYTES[unit]), pin)
            self.assertEqual(pin, E.WITNESS_DROPINS[f"{E.UNIT_DIR}/{unit}.d/{name}"])

    def test_both_installers_reach_their_pinned_bytes_through_the_mb6_boot_bundle(self):
        sources = {name: (TOOLS / f"{name}.py").read_text(encoding="utf-8") for name in BUNDLE}
        sources["wrb_payload_probe"] = PROBE
        pins = ",".join(f"{n}={sha(s.encode('utf-8'))}" for n, s in sources.items())
        loader = "import base64;exec(base64.b64decode('" + base64.b64encode(M6.BOOT.encode("ascii")).decode() + "'))"
        with tempfile.TemporaryDirectory() as empty:          # no tool or drop-in file reachable from the cwd
            result = subprocess.run([sys.executable, "-I", "-B", "-c", loader, pins, "wrb_payload_probe"],
                                    input=gzip.compress(json.dumps(sources).encode("utf-8"), mtime=0),
                                    capture_output=True, cwd=empty, timeout=120, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        out = json.loads(result.stdout)
        self.assertEqual(out["signer"], {u: pin for u, (_name, pin) in B.DROPINS.items()})
        self.assertEqual(out["witness"], {u: pin for u, (_name, pin) in W.DROPINS.items()})
        self.assertEqual(out["files"], ["<mb6-bundle:mb11_restart_boundary>",
                                        "<mb6-bundle:e19_witness_restart_boundary_install>",
                                        "<mb6-bundle:e19_p1b10_upgrade>"])
        self.assertEqual(out["sourceDirsExist"], [False, False])

    def test_tampered_embedded_bytes_refuse_install_before_any_observation_or_write(self):
        observe = mock.Mock(side_effect=AssertionError("observed"))
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            with mock.patch.dict(W.DROPIN_BYTES, {E.OWNER_SOCKET: b"[Unit]\n"}), mock.patch.object(W, "observe", observe):
                with self.assertRaises(E.Refused):
                    W.install("0" * 64, "s=x", root=root, chown=False)
            with mock.patch.dict(B.DROPIN_BYTES, {B.SOCKET_UNIT: b"[Unit]\n"}), mock.patch.object(I, "observe", observe):
                with self.assertRaises(I.Refused) as caught:
                    I.install("0" * 64, root=root, chown=False)
            self.assertEqual(caught.exception.reason, "CANDIDATE_DROPIN_PIN_MISMATCH:" + B.SOCKET_UNIT)
            self.assertEqual(list(root.iterdir()), [])
        observe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
