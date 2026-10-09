"""Package C C1 environment fix: the acquisition runs on Windows with the standard library only.

Record: docs/architecture/slice-15b2b-b1b3e-pkgc-record1-envelope-package.md §12.2. Pure and local (TEST_ONLY
synthetic world, a fake runner in place of the two pinned read-only mb9_operator forms): nothing contacts DEV.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_b1b3e_pkgc_record1_envelope as PK  # noqa: E402  (World fixture; sets sys.path for the tools)

import pkgc_operator as P  # noqa: E402
from lilith_owner_memory import owner_acceptance as OA  # noqa: E402
from lilith_owner_memory import owner_freshness as OF  # noqa: E402
from lilith_owner_memory import owner_freshness_tool as T  # noqa: E402
from lilith_owner_memory import witness_readiness as WR  # noqa: E402

ROOT = PK.ROOT
TOOLS = ROOT / "services/owner-memory-control/tools"
DISTRO = "Ubuntu-24.04"
BLOCKED = ("rfc8785", "fido2", "cryptography")
# The pins the acquisition binds. Unchanged by this fix (the mb9_operator transport stays as accepted).
EXPECTED_TOOL_PINS = {
    "services/owner-memory-control/lilith_owner_memory/owner_freshness_tool.py":
        "fd7abe2aa5e5efae41b87553efe8fe8058b437748accf866c2fa5ee71c8a7c27",
    "services/owner-memory-control/tools/mb9_operator.py":
        "2312e26a9cc8c2076539ae8bdde98cc5d79c2bbeb5138d66d07863ec3303c928",
    "services/owner-memory-control/tools/mb9_witness_verifier.py":
        "e4aca11dcc925e8ebdb280c2d4a7da1cf4f9a8fcc4e2abb080e22d6917080e78",
    "services/owner-memory-control/tools/mb9_owner_genesis_verify.py":
        "30b66fd2be9f29e820041840a75dc87f7623eff44551c025a0141790e7c89a5a",
}

# Runs in a fresh interpreter (-I: no PYTHONPATH, no user site) with the three pinned packages made unimportable,
# as on the Windows owner laptop. The fake runner replays the synthetic DEV world's outputs from a template.
WINDOWS_SCRIPT = r"""
import importlib.abc, json, shutil, sys
from pathlib import Path

BLOCKED = {blocked!r}

class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED:
            raise ImportError("not installed on Windows: " + name)
        return None

sys.meta_path.insert(0, Block())
sys.path.insert(0, {tools!r})
import pkgc_operator as P

template = Path({template!r})
stdout = json.loads((template / "stdout.json").read_text())

def runner(argv):
    assert argv[0] in ("host", "chain-export"), argv
    shutil.copytree(template / argv[0], argv[3])
    return 0, stdout[argv[0]].encode()

result = P.acquire_windows(Path("repo"), {distro!r}, {wsl!r}, {sequence!r}, Path("mb9-workdir"),
                           root=Path({root!r}), runner=runner, pinned={pinned!r})
loaded = sorted(m for m in sys.modules if m.split(".")[0] in BLOCKED + ("lilith_owner_memory", "lilith_memory"))
try:
    P.T.MANIFEST
    other_forms = "IMPORTED"
except ImportError:
    other_forms = "NEED_PINNED_PACKAGES"
print(json.dumps({{"result": result, "loaded": loaded, "otherForms": other_forms}}))
"""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Windows:
    """The synthetic World plus the Windows view of its work directory: `root` stands for the UNC share `wsl$`."""

    def __init__(self, test: unittest.TestCase):
        self.test = test
        self.w = PK.World(test)
        self.w.open()
        self.root = self.w.dir
        self.wsl = "/" + self.w.workdir.relative_to(self.root).as_posix()
        self.sequence = json.loads((self.w.workdir / P.C1_FILE).read_text())["sequenceId"]
        self.calls: list[list[str]] = []

    def runner(self, argv):
        self.calls.append(list(argv))
        return self.w.runner(argv)

    def acquire(self, **kw) -> dict:
        args = dict(distro=DISTRO, wsl_workdir=self.wsl, sequence_id=self.sequence)
        args.update(kw)
        return P.acquire_windows(Path("repo"), args["distro"], args["wsl_workdir"], args["sequence_id"],
                                 Path("mb9-workdir"), root=self.root, runner=self.runner,
                                 pinned={"control": self.w.control, "operator": "o" * 64})

    def export(self, result: dict) -> Path:
        return self.w.workdir / P.EXPORTS_DIR / result["acquisition"]


class StandardLibraryOnlyTests(unittest.TestCase):
    def test_the_windows_acquisition_runs_without_the_pinned_packages(self):
        win = Windows(self)
        template = win.w.dir / "template"
        template.mkdir()
        stdout = {}
        for form, args in (("host", ["POST9B"]), ("chain-export", [])):
            code, out = win.w.runner([form, "repo", "mb9", str(template / form), *args])
            self.assertEqual(code, 0)
            stdout[form] = out.decode()
        (template / "stdout.json").write_text(json.dumps(stdout))
        script = WINDOWS_SCRIPT.format(blocked=BLOCKED, tools=str(TOOLS), template=str(template), distro=DISTRO,
                                       wsl=win.wsl, sequence=win.sequence, root=str(win.root),
                                       pinned={"control": win.w.control, "operator": "o" * 64})
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
        run = subprocess.run([sys.executable, "-I", "-B", "-c", script], capture_output=True, text=True, env=env,
                             timeout=120)
        self.assertEqual(run.returncode, 0, run.stderr)
        out = json.loads(run.stdout)
        self.assertEqual(out["result"]["result"], "PKGC_ACQUIRED")
        self.assertEqual(out["loaded"], [])                      # nothing beyond the standard library was imported
        self.assertEqual(out["otherForms"], "NEED_PINNED_PACKAGES")  # every other form keeps its dependencies
        # The WSL side (with the pinned packages) accepts the Windows read with the unchanged verifier and binds it.
        export = win.w.workdir / P.EXPORTS_DIR / out["result"]["acquisition"]
        self.assertEqual(P.verify_acquisition(win.w.workdir, export)["acquisition"], export.name)
        self.assertTrue(P.check_export(win.w.workdir, export, win.w.pins)["exact"])
        self.assertEqual(win.w.bind(export)["result"], "PKGC_BINDING_EXACT")

    def test_the_operator_imports_none_of_the_pinned_modules_at_load(self):
        tree = ast.parse((TOOLS / "pkgc_operator.py").read_text(encoding="utf-8"))
        top = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
        names = {alias.name for node in top for alias in node.names} | {
            node.module for node in top if isinstance(node, ast.ImportFrom) and node.module}
        self.assertFalse(names & {"lilith_owner_memory", *BLOCKED}, names)
        self.assertTrue(all(isinstance(getattr(P, n), P._OnDemand) for n in ("OA", "OF", "T", "WR")))

    def test_on_demand_modules_are_the_canonical_ones(self):
        self.assertIs(P.T.load_replica, T.load_replica)
        self.assertIs(P.OA.AcceptanceResultV1, OA.AcceptanceResultV1)
        self.assertIs(P.OF.FreshnessResultV1, OF.FreshnessResultV1)
        self.assertIs(P.WR.document_bytes, WR.document_bytes)

    def test_standard_library_helpers_equal_the_canonical_ones(self):
        self.assertEqual(P.MAX_INPUT_BYTES, T.MAX_INPUT_BYTES)
        corpus = [b'{"a":1,"b":[1,2,{"c":null}]}', b'"x"', b"[]", b"0", b'{"a":1,"a":2}', b'{"a":{"b":1,"b":1}}',
                  b"", b"\xff\xfe", b"{", b"NaN", b'{"a":Infinity}', b"\xef\xbb\xbf{}", b"[" * 100000,
                  "{\"é\":\"ü\"}".encode("utf-8"), b' {"k" : true} ']
        for raw in corpus:
            with self.subTest(raw=raw[:20]):
                try:
                    expected, ok = WR._json(raw), True
                except Exception:  # noqa: BLE001
                    ok = False
                if ok:
                    self.assertEqual(json.dumps(P._json(raw, "R")), json.dumps(expected))  # NaN != NaN
                else:
                    with self.assertRaises(P.Stop):
                        P._json(raw, "R")
        with tempfile.TemporaryDirectory() as d:
            big = Path(d) / "big.json"
            big.write_bytes(b" " * (T.MAX_INPUT_BYTES + 1))
            with self.assertRaises(P.Stop) as caught:
                P._read(big, "R")
            self.assertEqual(caught.exception.reason, "R:big.json")
            big.write_bytes(b" " * T.MAX_INPUT_BYTES)
            self.assertEqual(len(P._read(big, "R")), T.MAX_INPUT_BYTES)


class SameSequenceTests(unittest.TestCase):
    def setUp(self):
        self.win = Windows(self)

    def test_windows_acquire_and_wsl_open_bind_share_one_sequence(self):
        result = self.win.acquire()
        self.assertEqual((result["result"], result["sequenceId"]), ("PKGC_ACQUIRED", self.win.sequence))
        self.assertEqual(result["workdir"], P.wsl_windows_path(DISTRO, self.win.wsl))
        export = self.win.export(result)
        receipt = json.loads((export / P.RECEIPT_FILE).read_text())
        self.assertEqual(receipt["sequenceId"], self.win.sequence)
        log = sorted(os.listdir(self.win.w.workdir / P.ACQUISITIONS_DIR))
        self.assertEqual(log, [f"{export.name}.completed.json", f"{export.name}.started.json"])
        self.assertEqual([c[0] for c in self.win.calls], ["host", "chain-export"])     # only the two read-only forms
        self.assertEqual(self.win.w.bind(export)["result"], "PKGC_BINDING_EXACT")
        # Single use, as for any acquisition.
        with self.assertRaises(P.Stop) as caught:
            self.win.w.bind(export)
        self.assertNotEqual(caught.exception.reason, "")

    def test_the_receipt_is_the_canonical_acquire_receipt(self):
        windows = json.loads((self.win.export(self.win.acquire()) / P.RECEIPT_FILE).read_text())
        wsl = json.loads((self.win.w.acquire() / P.RECEIPT_FILE).read_text())
        self.assertEqual(set(windows), set(wsl))
        for key in ("receiptType", "schemaVersion", "sequenceId", "control", "operatorSha256", "toolPins", "facts",
                    "artifacts"):
            self.assertEqual(windows[key], wsl[key], key)
        for form in ("host", "chain"):
            self.assertEqual({k: v for k, v in windows["commands"][form].items() if k != "args"},
                             {k: v for k, v in wsl["commands"][form].items() if k != "args"})
        self.assertEqual((windows["index"], wsl["index"]), (1, 2))

    def test_freshness_refusals_are_unchanged(self):
        export = self.win.export(self.win.acquire())
        # Copied into another sequence: not fresh there.
        other = PK.World(self)
        other.open()
        copy = other.workdir / P.EXPORTS_DIR / export.name
        shutil.copytree(export, copy)
        with self.assertRaises(P.Stop) as caught:
            P.verify_acquisition(other.workdir, copy)
        self.assertTrue(caught.exception.reason.startswith("ACQUISITION_NOT_FRESH"), caught.exception.reason)
        # Edited after the read: not fresh.
        (export / "host" / "identity.out").write_bytes(b"edited\n")
        with self.assertRaises(P.Stop) as caught:
            P.verify_acquisition(self.win.w.workdir, export)
        self.assertTrue(caught.exception.reason.startswith("ACQUISITION_NOT_FRESH"), caught.exception.reason)
        # A failed read is recorded, never fresh.
        self.win.w.dev = {"hostResult": "MB9_HOST_POST9B_NOT_PASS"}
        failed = self.win.export(self.win.acquire())
        with self.assertRaises(P.Stop) as caught:
            P.verify_acquisition(self.win.w.workdir, failed)
        self.assertIn("commandsExact", caught.exception.reason)

    def test_control_drift_is_refused(self):
        with self.assertRaises(P.Stop) as caught:
            P.acquire_windows(Path("repo"), DISTRO, self.win.wsl, self.win.sequence, Path("mb9"), root=self.win.root,
                              runner=self.win.runner, pinned={"control": "d" * 40, "operator": "o" * 64})
        self.assertEqual(caught.exception.reason, "CONTROL_CHANGED")
        self.assertEqual(self.win.calls, [])


class PathContractTests(unittest.TestCase):
    def test_the_windows_path_is_deterministic(self):
        self.assertEqual(P.wsl_windows_path("Ubuntu-24.04", "/root/lilith-pkgc-seq1"),
                         "\\\\wsl$\\Ubuntu-24.04\\root\\lilith-pkgc-seq1")
        self.assertEqual(P.wsl_windows_path("Ubuntu-24.04", "/root/a/b_c.d"), "\\\\wsl$\\Ubuntu-24.04\\root\\a\\b_c.d")
        for distro, wsl in (("Ubuntu-24.04", "root/x"), ("Ubuntu-24.04", "/root/x/"), ("Ubuntu-24.04", "/root//x"),
                            ("Ubuntu-24.04", "/root/../x"), ("Ubuntu-24.04", "/root/./x"), ("Ubuntu-24.04", "/"),
                            ("Ubuntu-24.04", "/mnt/c/Users/x"), ("Ubuntu-24.04", "/root/a b"),
                            ("Ubuntu-24.04", "/root/a\\b"), ("Ubuntu-24.04", "/root/.hidden"), ("", "/root/x"),
                            ("../x", "/root/x"), ("Ubuntu 24.04", "/root/x"), ("Ubuntu-24.04", None)):
            with self.subTest(distro=distro, wsl=wsl):
                with self.assertRaises(P.Stop) as caught:
                    P.wsl_windows_path(distro, wsl)
                self.assertIn(caught.exception.reason, ("WSL_DISTRO_INVALID", "WSL_WORKDIR_INVALID"))

    def test_refusals_happen_before_any_dev_contact_and_create_nothing(self):
        win = Windows(self)
        before = sorted(p.relative_to(win.root).as_posix() for p in win.root.rglob("*"))
        cases = {
            "WSL_WORKDIR_NOT_FOUND": dict(wsl_workdir=win.wsl + "-other"),
            "SEQUENCE_MISMATCH": dict(sequence_id="0" * 32),
            "SEQUENCE_ID_INVALID": dict(sequence_id="not-a-sequence"),
            "WSL_WORKDIR_INVALID": dict(wsl_workdir=win.wsl + "/../x"),
        }
        for reason, kw in cases.items():
            with self.subTest(reason):
                with self.assertRaises(P.Stop) as caught:
                    win.acquire(**kw)
                self.assertEqual(caught.exception.reason, reason)
        # A directory without a C1 opening: no sequence is created there.
        bare = win.root / "laptop" / "not-opened"
        bare.mkdir()
        with self.assertRaises(P.Stop) as caught:
            win.acquire(wsl_workdir="/laptop/not-opened")
        self.assertTrue(caught.exception.reason.startswith("SEQUENCE_NOT_OPENED"))
        self.assertEqual(list(bare.iterdir()), [])
        bare.rmdir()
        # A Windows clock behind the WSL opening refuses before the read.
        with self.assertRaises(P.Stop) as caught:
            P.acquire_windows(Path("repo"), DISTRO, win.wsl, win.sequence, Path("mb9"), root=win.root,
                              runner=win.runner, now=lambda: "2000-01-01T00:00:00Z",
                              pinned={"control": win.w.control, "operator": "o" * 64})
        self.assertEqual(caught.exception.reason, "CLOCK_BEFORE_OPENING")
        self.assertEqual(win.calls, [])
        self.assertEqual(sorted(p.relative_to(win.root).as_posix() for p in win.root.rglob("*")), before)

    def test_the_cli_form(self):
        self.assertEqual(P.main(["acquire-windows", "repo", DISTRO, "/root/x/", "0" * 32, "mb9"]), 2)
        self.assertEqual(P.main(["acquire-windows", "repo", DISTRO, "/root/x"]), 2)          # USAGE


class BoundaryTests(unittest.TestCase):
    def test_no_owner_record_and_no_authority_change(self):
        win = Windows(self)
        tree = P.tree_digest(win.w.ra)
        export = win.export(win.acquire())
        self.assertEqual(P.tree_digest(win.w.ra), tree)                  # Replica A unchanged
        self.assertEqual(len(T.load_replica(win.w.ra).records), 0)        # record 1 absent
        checks = P.check_export(win.w.workdir, export, win.w.pins)["checks"]
        for name in ("holdStoreEmpty", "signerNoLaterState", "registryNotEffective", "authorityNotActive"):
            self.assertTrue(checks[name], name)
        source = (TOOLS / "pkgc_operator.py").read_text(encoding="utf-8")
        body = source[source.index("def acquire_windows("):source.index("def verify_acquisition(")]
        called = {node.func.id for node in ast.walk(ast.parse(body)) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name)}
        self.assertEqual(called - {"wsl_windows_path", "_need", "isinstance", "Path", "_opening", "now", "acquire"},
                         set())
        for writer in ("append", "append_envelope", "init_acceptance_store", "open_sequence", "_new_dir", "_create"):
            self.assertNotIn(writer + "(", body)

    def test_tool_pins_and_transport_are_unchanged(self):
        self.assertEqual(P.TOOL_PINS, EXPECTED_TOOL_PINS)
        for path, pin in EXPECTED_TOOL_PINS.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)
        source = (TOOLS / "pkgc_operator.py").read_text(encoding="utf-8")
        acquire = source[source.index("def acquire("):source.index("# Record §12.2. The two-environment")]
        self.assertEqual(sorted(set(re.findall(r'"(host|chain-export)"', acquire))),
                         ["chain-export", "host"])
        self.assertIn('"POST9B"', acquire)


if __name__ == "__main__":
    unittest.main()
