"""B-4: offline tests for the Termux K-ROOT capability rehearsal and its bundle builder (TEST ONLY).

Nothing here generates a real K-ROOT, contacts a device, or touches a real
replica or pin. The rehearsal runs against a temporary base directory with
the Termux gate bypassed only through the pure `rehearse(base)` function.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "services/owner-memory-control/tools"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module              # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


R = _load("termux_kroot_rehearsal", TOOLS / "termux_kroot_rehearsal.py")
BUILD = _load("build_termux_kroot_rehearsal_bundle", TOOLS / "build_termux_kroot_rehearsal_bundle.py")


@unittest.skipUnless(os.name == "posix", "file modes are POSIX")
class RehearsalTests(unittest.TestCase):
    def rehearse(self):
        with tempfile.TemporaryDirectory() as base:
            result = R.rehearse(Path(base))
            self.assertEqual(os.listdir(base), [], "the rehearsal left something behind")
        return result

    def test_full_rehearsal_passes_and_leaves_nothing(self):
        result = self.rehearse()
        self.assertEqual(result["REHEARSAL"], "PASS", result["checks"])
        self.assertTrue(all(v == "PASS" for v in result["checks"].values()), result["checks"])
        for name in ("rootKeygen", "keyFileRegular0600", "keyFileOnlyEntry", "keyNotLoadableWithoutPassphrase",
                     "keyNotLoadableWithWrongPassphrase", "anchorMatchesKeyAndFingerprint",
                     "existingKeyNeverOverwritten", "shortPassphraseRefused", "rootKeygenCli", "syntheticInputs",
                     "registryV1", "registryV1CliEqualsFunction", "registryV1WrongPassphraseRefused",
                     "witnessAnchor", "reproduceDeterministicAndVerified", "cleanup"):
            self.assertIn(name, result["checks"])
        self.assertEqual(result["realAuthorityMaterial"], "NONE")
        self.assertIs(result["testOnly"], True)
        self.assertIn("NOT_K_ROOT", result["nonclaims"])
        self.assertEqual(sorted(result["removedEntries"]), sorted(
            [R.ROOT_KEY_FILE, R.CLI_KEY_FILE, "kact.json", "kwit.json", "root-anchor.json", "registry.json",
             "witness-anchor.json"]))

    def test_every_created_identity_is_reported_burned(self):
        burned = self.rehearse()["burnedTestIdentities"]
        self.assertEqual(set(burned), {"rehearsalRootPublicKeySha256", "rehearsalCliRootPublicKeySha256",
                                       "syntheticKActPublicKeySha256", "syntheticKWitPublicKeySha256",
                                       "rehearsalRegistryDigest", "rehearsalGenesisCandidateDigest"})
        for value in burned.values():
            self.assertRegex(value, r"^[0-9a-f]{64}$")
        self.assertEqual(len(set(burned.values())), len(burned))
        # two runs never produce the same throwaway root key
        self.assertNotEqual(burned["rehearsalRootPublicKeySha256"],
                            self.rehearse()["burnedTestIdentities"]["rehearsalRootPublicKeySha256"])

    def test_transcript_holds_no_secret(self):
        result = self.rehearse()
        text = json.dumps(result)
        self.assertNotIn(R.TEST_PASSPHRASE.decode(), text)
        for token in ("PRIVATE", "privateKey", "passphrase", "BEGIN", "MII"):
            self.assertNotIn(token, text)

    def test_nothing_is_written_outside_the_temporary_directory(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as base:
            before = sorted(Path(home).rglob("*"))
            with mock.patch.dict(os.environ, {"HOME": home}):
                result = R.rehearse(Path(base))
            self.assertEqual(result["REHEARSAL"], "PASS", result["checks"])
            self.assertEqual(sorted(Path(home).rglob("*")), before)
            self.assertEqual(os.listdir(base), [])

    def test_a_failing_step_is_contained_and_cleanup_still_runs(self):
        real_load = R._load

        def broken(name, path):
            module = real_load(name, path)
            if name == "lilith_authority_owner_dev":
                module.registry_v1 = mock.Mock(side_effect=RuntimeError("boom"))
            return module
        with mock.patch.object(R, "_load", broken), tempfile.TemporaryDirectory() as base:
            result = R.rehearse(Path(base))
            self.assertEqual(os.listdir(base), [])
        self.assertEqual(result["REHEARSAL"], "FAIL")
        self.assertEqual(result["checks"]["registryV1"], "FAIL:RuntimeError")
        self.assertEqual(result["checks"]["cleanup"], "PASS")


class GateTests(unittest.TestCase):
    def test_refuses_outside_termux_private_storage(self):
        with tempfile.TemporaryDirectory() as base, mock.patch.dict(os.environ, {"TMPDIR": base, "PREFIX": ""}):
            with self.assertRaises(SystemExit) as caught:
                R.termux_base()
        self.assertIn("not Termux private app storage", str(caught.exception))

    def test_usage(self):
        with mock.patch("sys.stderr", io.StringIO()):
            self.assertEqual(R.main([]), 2)
            self.assertEqual(R.main(["rehearse", "--real"]), 2)
            self.assertEqual(R.main(["generate"]), 2)

    def test_source_is_offline_and_test_only(self):
        source = (TOOLS / "termux_kroot_rehearsal.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        imported |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        for forbidden in ("socket", "urllib", "http", "subprocess", "requests", "getpass"):
            self.assertNotIn(forbidden, imported)
        self.assertTrue(R.TEST_PASSPHRASE.startswith(b"TEST_ONLY"))
        self.assertNotEqual(R.SYNTHETIC_MACHINE_ID, "ae929170e6fa4c8ab9cc7b9547238d9d")   # never the DEV machine id
        self.assertIn("REHEARSAL-TEST", R.ROOT_KEY_FILE)
        self.assertIn("TEST", R.WORKDIR_PREFIX)
        for path in ("owner-freshness", "lilith-owner-freshness", "pin", "Replica"):
            self.assertNotIn(f'"{path}', source)


class ClosureTests(unittest.TestCase):
    def test_builder_closure_is_the_exact_import_closure(self):
        mods = {"lilith_owner_memory": ROOT / "services/owner-memory-control/lilith_owner_memory",
                "lilith_memory": ROOT / "services/core-api/lilith_memory"}
        seen: set[Path] = set()

        def visit(path: Path) -> None:
            if path in seen:
                return
            seen.add(path)
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom) and node.level:
                    names = [node.module] if node.module else [a.name for a in node.names]
                    for name in names:
                        candidate = path.parent / (name.split(".")[0] + ".py")
                        if candidate.exists():
                            visit(candidate)
                    continue
                names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                         else [node.module] + [f"{node.module}.{a.name}" for a in node.names]
                         if isinstance(node, ast.ImportFrom) else [])
                for name in names:
                    parts = name.split(".")
                    if parts[0] in mods:
                        visit(mods[parts[0]] / "__init__.py")
                        for i in range(len(parts), 1, -1):
                            candidate = mods[parts[0]].joinpath(*parts[1:i]).with_suffix(".py")
                            if candidate.exists():
                                visit(candidate)
                                break
        for tool in ("lilith_authority_owner_dev.py", "lilith_authority_keygen_dev.py"):
            visit(ROOT / "services/authority-dev/ceremony" / tool)
        closure = sorted(p.relative_to(ROOT).as_posix() for p in seen)
        self.assertEqual(closure, sorted(BUILD.CLOSURE))


class BundleTests(unittest.TestCase):
    def fake_vendor(self, directory: Path) -> Path:
        vendor = directory / "vendor"
        for top in BUILD.VENDOR_TOPS:
            (vendor / top).mkdir(parents=True)
            (vendor / top / "__init__.py").write_text(f"# {top}\n", encoding="utf-8")
        return vendor

    def head(self) -> str | None:
        try:
            commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], check=True,
                                    capture_output=True, text=True).stdout.strip()
            subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{commit}:{BUILD.REHEARSAL}"], check=True,
                           capture_output=True)
            return commit
        except (OSError, subprocess.CalledProcessError):
            return None

    def test_bundle_is_deterministic_and_exact(self):
        commit = self.head()
        if commit is None:
            self.skipTest("the rehearsal is not committed at HEAD (or git is unavailable)")
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            vendor = self.fake_vendor(d)
            first = BUILD.build(ROOT, commit, vendor, d / "a.tar")
            second = BUILD.build(ROOT, commit, vendor, d / "b.tar")
            self.assertEqual(first["tarSha256"], second["tarSha256"])
            self.assertEqual((d / "a.tar").read_bytes(), (d / "b.tar").read_bytes())
            with tarfile.open(d / "a.tar") as tar:
                members = tar.getmembers()
                files = {m.name.split("/", 1)[1]: tar.extractfile(m).read() for m in members if m.isfile()}
                self.assertTrue(all(m.mtime == 0 and m.uid == 0 and m.gid == 0 for m in members))
                self.assertTrue(all(m.mode == (0o755 if m.isdir() else 0o644) for m in members))
                self.assertTrue(all(m.name.startswith(first["top"]) for m in members))
            expected = set(BUILD.CLOSURE) | {BUILD.REHEARSAL, "SOURCE_COMMIT", "SHA256SUMS"} | {
                f"vendor/{top}/__init__.py" for top in BUILD.VENDOR_TOPS}
            self.assertEqual(set(files), expected)
            sums = dict(reversed(line.split("  ", 1)) for line in files["SHA256SUMS"].decode().splitlines())
            self.assertEqual(set(sums), expected - {"SHA256SUMS"})
            for name, digest in sums.items():
                self.assertEqual(hashlib.sha256(files[name]).hexdigest(), digest, name)
            self.assertEqual(files["SOURCE_COMMIT"].decode().strip(), commit)
            self.assertEqual(first["sha256sumsSha256"], hashlib.sha256(files["SHA256SUMS"]).hexdigest())

    def test_builder_refusals(self):
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            vendor = self.fake_vendor(d)
            with self.assertRaises(BUILD.BuildError):
                BUILD.bundle_members(ROOT, "HEAD", vendor)
            with self.assertRaises(BUILD.BuildError) as caught:
                BUILD.bundle_members(ROOT, "0" * 40, vendor)             # no such commit
            self.assertEqual(str(caught.exception), "SOURCE_NOT_AT_COMMIT")
            (vendor / "extra").mkdir()
            with self.assertRaises(BUILD.BuildError) as caught:
                BUILD.bundle_members(ROOT, "0" * 40, vendor)
            self.assertEqual(str(caught.exception), "VENDOR_SET_MISMATCH")
            (d / "exists.tar").write_bytes(b"x")
            with mock.patch("sys.stderr", io.StringIO()):
                self.assertEqual(BUILD.main(["--repo", str(ROOT), "--commit", "0" * 40, "--vendor-dir", str(vendor),
                                             "--out", str(d / "exists.tar")]), 2)


DOCS = ROOT / "docs/architecture"
STAGING_DOC = DOCS / "slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-staging.md"
PREP_DOC = DOCS / "slice-15b2b-b1b3e-b4-termux-kroot-rehearsal.md"
# The accepted real Replica B (P3-3B), confirmed on the phone read-only: directly under the
# Termux $HOME, NOT under the nested ~/lilith-owner-freshness/ the P3-3B design had planned.
CANONICAL_REPLICA_B = "$HOME/lilith-owner-offline-dev-synthetic-01"
OLD_NESTED_REPLICA_B = "$HOME/lilith-owner-freshness/owner-offline-dev-synthetic-01"


def _bash_block(doc: Path) -> str:
    """The one ```bash block that is the B-4 operator block (exactly as staged as b4_phone_commands.sh)."""
    blocks = [part.split("\n```", 1)[0] + "\n" for part in doc.read_text(encoding="utf-8").split("```bash\n")[1:]]
    operator = [block for block in blocks if block.startswith("# ===") and "B-4 Termux K-ROOT capability rehearsal" in block]
    assert len(operator) == 1, doc
    return operator[0]


class OperatorBlockTests(unittest.TestCase):
    """Pins the B-4 operator block to the canonical real Replica B path."""

    def setUp(self):
        self.block = _bash_block(STAGING_DOC)

    def test_replica_path_is_the_canonical_replica_b(self):
        assignments = [line for line in self.block.splitlines() if line.startswith("R=")]
        self.assertEqual(len(assignments), 1, assignments)
        self.assertEqual(assignments[0].split("#")[0].strip(), f'R="{CANONICAL_REPLICA_B}"')
        prep = [line for line in _bash_block(PREP_DOC).splitlines() if line.startswith("R=")]
        self.assertEqual([line.split("#")[0].strip() for line in prep], [f'R="{CANONICAL_REPLICA_B}"'])

    def test_old_nested_path_is_only_the_absence_gate(self):
        uses = [line for line in self.block.splitlines() if "lilith-owner-freshness" in line]
        self.assertEqual(len(uses), 1, uses)
        self.assertTrue(uses[0].startswith(f'test ! -e "{OLD_NESTED_REPLICA_B}" && echo NESTED_REPLICA_ABSENT'))
        self.assertNotIn("lilith-owner-freshness", _bash_block(PREP_DOC))

    def test_parent_listing_is_home(self):
        self.assertIn("""echo "parent $(ls -A "$HOME" | grep '^lilith-owner' | LC_ALL=C sort | tr '\\n' ' ')\"""",
                      self.block)
        self.assertIn('grep -qE "^parent (.* )?lilith-owner-offline-dev-synthetic-01 "', self.block)

    def test_recorded_operator_script_digest_matches_the_block(self):
        text = STAGING_DOC.read_text(encoding="utf-8")
        start = text.index("`b4_phone_commands.sh` (SHA-256")
        recorded = text[start:start + 200].split("`")[3]
        self.assertEqual(recorded, hashlib.sha256(self.block.encode()).hexdigest())

    @unittest.skipUnless(os.name == "posix", "runs the operator block's replica gates under bash")
    def test_replica_gates_under_bash(self):
        lines = self.block.splitlines()
        prelude = "\n".join(lines[:next(i for i, line in enumerate(lines) if line.startswith("# ---- G0"))])
        gates = "\n".join(line for line in lines if line.startswith(("test -f \"$R/REPLICA.json\"",
                                                                    f'test ! -e "{OLD_NESTED_REPLICA_B}"')))
        regex = next(line for line in lines if "REPLICA_B_BASELINE_OK" in line).split('grep -qE "')[1].split('"')[0]
        script = f'{prelude}\n{gates}\nsnap\nsnap | grep -qE "{regex}" && echo PARENT_OK || echo PARENT_NOT_OK\n'

        def run(layout):
            with tempfile.TemporaryDirectory() as home:
                for relative in layout:
                    path = Path(home, relative)
                    if relative.endswith("REPLICA.json"):
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text("{}", encoding="utf-8")
                    else:
                        path.mkdir(parents=True, exist_ok=True)
                env = dict(os.environ, HOME=home, TMPDIR=home, PREFIX=home)
                return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env).stdout

        direct = ["lilith-owner-offline-dev-synthetic-01/REPLICA.json", "lilith-owner-offline-dev-synthetic-01/records"]
        unrelated = ["storage/downloads", "lilith-p3-3b/evidence", "lilith-b4-rehearsal/evidence"]
        nested = ["lilith-owner-freshness/owner-offline-dev-synthetic-01/REPLICA.json",
                  "lilith-owner-freshness/owner-offline-dev-synthetic-01/records"]

        out = run(direct + unrelated)
        self.assertIn("REPLICA_B_PRESENT\nNESTED_REPLICA_ABSENT\n", out)
        self.assertIn("entries REPLICA.json records \nparent lilith-owner-offline-dev-synthetic-01 \n", out)
        self.assertIn("~/lilith-owner-offline-dev-synthetic-01 ", out)
        self.assertTrue(out.endswith("PARENT_OK\n"), out)
        self.assertNotIn("STOP", out)

        out = run(direct + unrelated + ["lilith-owner-freshness"])        # an empty leftover parent is tolerated
        self.assertIn("parent lilith-owner-freshness lilith-owner-offline-dev-synthetic-01 \n", out)
        self.assertTrue(out.endswith("PARENT_OK\n"), out)
        self.assertNotIn("STOP", out)

        out = run(direct + nested)                                         # a second, nested replica stops
        self.assertIn("STOP: a second Replica B exists at the old nested path", out)

        out = run(nested + unrelated)                                      # the old nested layout alone stops
        self.assertIn("STOP: Replica B missing", out)
        self.assertTrue(out.endswith("PARENT_NOT_OK\n"), out)


if __name__ == "__main__":
    unittest.main()
