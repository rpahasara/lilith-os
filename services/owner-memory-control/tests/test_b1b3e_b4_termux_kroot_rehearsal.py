"""B-4: offline tests for the Termux K-ROOT capability rehearsal and its bundle builder (TEST ONLY).

Nothing here generates a real K-ROOT, contacts a device, or touches a real
replica or pin. The rehearsal runs against a temporary base directory with
the Termux gate bypassed only through the pure `rehearse(base)` function.
"""

from __future__ import annotations

import ast
import difflib
import hashlib
import importlib.util
import io
import json
import os
import re
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


RUN2_DOC = DOCS / "slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-run2.md"
REVIEWED_OPERATOR_SHA256 = "353c988f67cd855372c7037f0b55d8655af63d52bb4ac26a44f1d43a7c98d6a7"
REPLICA_B_MANIFEST = (b'{"authorityProfile":"DEV_SYNTHETIC","environment":"dev","replicaId":"owner-offline-dev-synthetic-01",'
                      b'"replicaType":"LILITH_OWNER_FRESHNESS_REPLICA","schemaVersion":1}')


def _doc_block(doc: Path, fence: str, first: str) -> str:
    blocks = [part.split("\n```", 1)[0] + "\n" for part in doc.read_text(encoding="utf-8").split(f"```{fence}\n")[1:]]
    found = [block for block in blocks if block.startswith(first)]
    assert len(found) == 1, (doc, fence, first)
    return found[0]


def _run2_block() -> str:
    return _doc_block(RUN2_DOC, "bash", "# ===== B-4 FRESH")


class RunTwoTests(unittest.TestCase):
    """Pins run 2 to the reviewed 353c988f block: every difference is the recorded diff, and nothing else."""

    def test_reviewed_block_is_unchanged(self):
        self.assertEqual(hashlib.sha256(_bash_block(STAGING_DOC).encode()).hexdigest(), REVIEWED_OPERATOR_SHA256)
        self.assertEqual(hashlib.sha256(REPLICA_B_MANIFEST).hexdigest(),
                         "c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4")

    def test_every_difference_from_the_reviewed_block_is_the_recorded_diff(self):
        reviewed, run2 = _bash_block(STAGING_DOC), _run2_block()
        diff = "".join(difflib.unified_diff(reviewed.splitlines(keepends=True), run2.splitlines(keepends=True),
                                            fromfile="353c988f", tofile="run2", n=0))
        self.assertEqual(diff, _doc_block(RUN2_DOC, "diff", "--- 353c988f"))

    def test_recorded_run2_digest_matches_the_block(self):
        text = RUN2_DOC.read_text(encoding="utf-8")
        start = text.index("`b4_phone_commands.run2.sh` (SHA-256")
        recorded = text[start:start + 200].split("`")[3]
        self.assertEqual(recorded, hashlib.sha256(_run2_block().encode()).hexdigest())

    def test_run2_structure(self):
        run2 = _run2_block()
        code = [line for line in run2.splitlines() if not line.lstrip().startswith("#")]
        self.assertFalse([line for line in code if re.search(r'(?<!builtin )echo "STOP', line)])  # every STOP is stop()
        self.assertNotIn('} | tee "$E/verify.txt"', run2)                           # no gate inside a pipeline group
        self.assertNotIn("echo()", run2)                                           # no echo redefinition
        self.assertIn('stop() { builtin echo "STOP: $*" >&2; exit 1; }', run2)
        for fixed in (f'R="{CANONICAL_REPLICA_B}"', 'W="$HOME/lilith-b4-rehearsal-2"',
                      "TAR_SHA=659c50a476c85ff9ed005af97bc70a48989a87890ec53b23f940d97901bee0b3",
                      "SUMS_SHA=dbb9dfbeaeefb59e47cb2ae64aaa651bbe9b89daa443e0912787c10d0b0e2288",
                      "SRC=ff13bc6f72156c332b29ad1605d24410c2abf232",
                      'grep -qx "sha c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4"'):
            self.assertIn(fixed, run2)
        snap_of = lambda block: block.split("\nsnap() ", 1)[1].split("\n\n", 1)[0]
        self.assertEqual(snap_of(run2), snap_of(_bash_block(STAGING_DOC)))          # the reviewed snap() format

    @unittest.skipUnless(os.name == "posix", "runs bash")
    def test_documented_invocation_preserves_the_script_exit(self):
        text = RUN2_DOC.read_text(encoding="utf-8")
        line = next(l.strip() for l in text.splitlines()
                    if l.strip().startswith('bash "$HOME/storage/downloads/b4_phone_commands.run2.sh" 2>&1 | tee'))
        with tempfile.TemporaryDirectory() as home:
            os.makedirs(os.path.join(home, "storage/downloads"))
            Path(home, "storage/downloads/b4_phone_commands.run2.sh").write_text('echo A\necho "STOP: x" >&2\nexit 1\n',
                                                                                encoding="utf-8")
            subprocess.run(["bash", "-c", line], env=dict(os.environ, HOME=home), capture_output=True, check=False)
            self.assertEqual(Path(home, "lilith-b4-rehearsal-2.transcript.txt").read_text(encoding="utf-8"),
                             "A\nSTOP: x\nRUN_EXIT=1\n")


_GATE_CHECKS = ["rootKeygen", "keyFileRegular0600", "keyFileOnlyEntry", "keyNotLoadableWithoutPassphrase",
                "keyNotLoadableWithWrongPassphrase", "anchorMatchesKeyAndFingerprint", "existingKeyNeverOverwritten",
                "shortPassphraseRefused", "rootKeygenCli", "syntheticInputs", "registryV1", "registryV1CliEqualsFunction",
                "registryV1WrongPassphraseRefused", "witnessAnchor", "reproduceDeterministicAndVerified",
                "allFilesInsideWorkdir", "cleanup"]
_REMOVED = ["k-root.REHEARSAL-TEST.der", "k-root-cli.REHEARSAL-TEST.der", "kact.json", "kwit.json",
            "root-anchor.json", "registry.json", "witness-anchor.json"]
# A stub of the rehearsal program: it emits a gate-passing transcript and injects exactly one FAULT.
_STUB_REHEARSAL = f"""import json, os, sys
f = os.environ.get("FAULT", "")
checks = {{k: "PASS" for k in {_GATE_CHECKS!r}}}
if f == "gate":
    checks["cleanup"] = "FAIL"
burned = {{f"id{{i}}": f"{{i:064x}}" for i in range(6)}}
print(json.dumps({{"REHEARSAL": "PASS", "checks": checks, "testOnly": True, "realAuthorityMaterial": "NONE",
                  "removedEntries": {_REMOVED!r}, "burnedTestIdentities": burned,
                  "environment": {{"python": "stub"}}}}, indent=1))
print("B4_KROOT_REHEARSAL=PASS")
home, tmp = os.environ["HOME"], os.environ["TMPDIR"]
if f == "stderr":
    print("warning", file=sys.stderr)
if f == "tmpleft":
    os.mkdir(os.path.join(tmp, ".lilith-b4-kroot-rehearsal-TEST-left"))
if f == "keyleft":
    open(os.path.join(home, "k-root.REHEARSAL-TEST.der"), "w").close()
if f == "bundle":
    open(__file__, "a").write("#\\n")
if f == "replica":
    os.utime(os.path.join(home, "lilith-owner-offline-dev-synthetic-01", "REPLICA.json"), (1, 1))
if f == "cleanup":
    open(os.path.join(home, "storage/downloads/lilith-b4-kroot-rehearsal-ff13bc6.tar"), "ab").write(b"x")
sys.exit(3 if f == "exit" else 0)
"""
_CLEAN_TOKENS = ["HOME_TERMUX_PRIVATE", "TMP_TERMUX_PRIVATE", "CRYPTOGRAPHY_OK", "STAGING_ABSENT", "TMP_NO_STALE",
                 "NO_KROOT_FILES_BEFORE", "REPLICA_B_PRESENT", "NESTED_REPLICA_ABSENT", "REPLICA_B_BASELINE_OK",
                 "lilith-b4-kroot-rehearsal-ff13bc6.tar: OK", "SHA256SUMS: OK", "BUNDLE_VERIFIED", "SOURCE_COMMIT_OK",
                 "FILE_COUNT_OK", "BUNDLE_IN_TERMUX_PRIVATE", "exit=0", "B4_KROOT_REHEARSAL=PASS", "REHEARSAL_GATE_PASS",
                 "TMP_CLEAN", "NO_KEY_FILE_ANYWHERE", "BUNDLE_UNCHANGED", "STDERR_EMPTY", "REPLICA_B_UNCHANGED",
                 "TRANSPORT_COPY_REMOVED"]


@unittest.skipUnless(os.name == "posix" and importlib.util.find_spec("cryptography"),
                     "runs run 2 under bash (G0 imports cryptography)")
class RunTwoHardStopTests(unittest.TestCase):
    """Runs the pinned run-2 text against a stub bundle. Only the bundle pins (TAR_SHA, SUMS_SHA, SRC), the
    75-file count, and the Termux path prefix in priv() are substituted; the control flow is the pinned text."""

    def run2(self, fault: str = ""):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(subprocess.run, ["rm", "-rf", str(root)])
        home, tmp, bindir = root / "home", root / "tmp", root / "bin"
        downloads = home / "storage/downloads"
        for d in (downloads, tmp, bindir):
            d.mkdir(parents=True)
        (bindir / "python").symlink_to(sys.executable)
        replica = home / "lilith-owner-offline-dev-synthetic-01"
        (replica / "records").mkdir(parents=True)
        (replica / "REPLICA.json").write_bytes(REPLICA_B_MANIFEST)
        top = "lilith-b4-kroot-rehearsal-ff13bc6"
        files = {"services/owner-memory-control/tools/termux_kroot_rehearsal.py": _STUB_REHEARSAL.encode(),
                 "SOURCE_COMMIT": b"stub0commit\n"}
        files["SHA256SUMS"] = "".join(f"{hashlib.sha256(v).hexdigest()}  {k}\n" for k, v in sorted(files.items())).encode()
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            for name, data in files.items():
                info = tarfile.TarInfo(f"{top}/{name}")
                info.size, info.mode = len(data), 0o644
                tar.addfile(info, io.BytesIO(data))
        (downloads / f"{top}.tar").write_bytes(buf.getvalue())
        script = (_run2_block()
                  .replace("TAR_SHA=659c50a476c85ff9ed005af97bc70a48989a87890ec53b23f940d97901bee0b3",
                           f"TAR_SHA={hashlib.sha256(buf.getvalue()).hexdigest()}")
                  .replace("SUMS_SHA=dbb9dfbeaeefb59e47cb2ae64aaa651bbe9b89daa443e0912787c10d0b0e2288",
                           f"SUMS_SHA={hashlib.sha256(files['SHA256SUMS']).hexdigest()}")
                  .replace("SRC=ff13bc6f72156c332b29ad1605d24410c2abf232", "SRC=stub0commit")
                  .replace('wc -l)" = 75', f'wc -l)" = {len(files)}')
                  .replace("/data/data/com.termux/*|/data/user/0/com.termux/*", f"{root}/*"))
        (root / "run2.sh").write_text(script, encoding="utf-8")
        env = {"HOME": str(home), "TMPDIR": str(tmp), "PREFIX": str(root), "PATH": f"{bindir}:/usr/bin:/bin", "FAULT": fault}
        result = subprocess.run(["bash", str(root / "run2.sh")], cwd=home, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
        return result.returncode, result.stdout, home / "lilith-b4-rehearsal-2", downloads / f"{top}.tar"

    def assertStopped(self, fault: str, message: str):
        rc, out, w, download = self.run2(fault)
        self.assertEqual(rc, 1, out)
        self.assertTrue(out.endswith(f"STOP: {message}\n"), out)                 # the STOP is the last thing that ran
        self.assertNotIn("TRANSPORT_COPY_REMOVED", out)
        self.assertTrue(download.exists())                                          # the transport copy is preserved
        return out, w, download

    def test_I_clean_run(self):
        rc, out, w, download = self.run2()
        self.assertEqual(rc, 0, out)
        self.assertFalse([line for line in out.splitlines() if line.startswith("STOP")], out)
        variable = ("PYTHON ", "CRYPTOGRAPHY ", "~/", "BURNED ", "ENV ", "sha ", "records ", "entries ", "parent ")
        tokens = [line for line in out.splitlines()
                  if not line.startswith(variable) and not re.fullmatch(r"[0-9a-f]{64}  .*", line)]
        self.assertEqual(tokens, _CLEAN_TOKENS)
        self.assertEqual(len([line for line in out.splitlines() if line.startswith("BURNED ")]), 6)
        e = w / "evidence"
        self.assertEqual(sorted(os.listdir(e)), ["g0.txt", "gate.txt", "rehearsal.exit", "rehearsal.json",
                                                 "rehearsal.stderr", "replica-b-after.txt", "replica-b-before.txt",
                                                 "verify.txt"])
        self.assertEqual((e / "verify.txt").read_text(),
                         "TMP_CLEAN\nNO_KEY_FILE_ANYWHERE\nBUNDLE_UNCHANGED\nSTDERR_EMPTY\nREPLICA_B_UNCHANGED\n")
        self.assertEqual((e / "rehearsal.exit").read_text(), "exit=0\n")
        self.assertEqual((e / "replica-b-before.txt").read_bytes(), (e / "replica-b-after.txt").read_bytes())
        self.assertIn("parent lilith-owner-offline-dev-synthetic-01 \n", (e / "replica-b-before.txt").read_text())
        subprocess.run(["sha256sum", "-c", "--quiet", str(w / "evidence.sha256")], check=True)
        self.assertFalse(download.exists())

    def test_A_rehearsal_exit_nonzero(self):
        _, w, _ = self.assertStopped("exit", "rehearsal exited non-zero (3)")
        self.assertEqual((w / "evidence/rehearsal.exit").read_text(), "exit=3\n")
        for later in ("evidence/gate.txt", "evidence/verify.txt", "evidence/replica-b-after.txt", "evidence.sha256"):
            self.assertFalse((w / later).exists(), later)

    def test_B_gate_stop(self):
        _, w, _ = self.assertStopped("gate", "rehearsal gate failed")
        self.assertTrue((w / "evidence/gate.txt").read_text().startswith("STOP: rehearsal gate failed cleanup"))
        self.assertFalse((w / "evidence/verify.txt").exists())
        self.assertFalse((w / "evidence.sha256").exists())

    def test_C_tmp_leftover(self):
        _, w, _ = self.assertStopped("tmpleft", "rehearsal directory left in TMPDIR")
        self.assertFalse((w / "evidence.sha256").exists())

    def test_D_test_key_leftover(self):
        _, w, _ = self.assertStopped("keyleft", "a TEST key file remains")
        self.assertFalse((w / "evidence.sha256").exists())

    def test_E_bundle_changed(self):
        _, w, _ = self.assertStopped("bundle", "unexpected file in bundle")
        self.assertFalse((w / "evidence.sha256").exists())

    def test_F_stderr_nonempty(self):
        _, w, _ = self.assertStopped("stderr", "rehearsal wrote to stderr")
        self.assertFalse((w / "evidence.sha256").exists())

    def test_G_replica_changed(self):
        _, w, _ = self.assertStopped("replica", "Replica B changed")
        self.assertFalse((w / "evidence.sha256").exists())

    def test_H_cleanup_cmp_failure(self):
        _, w, download = self.assertStopped("cleanup", "transport copy differs from the staged tar")
        self.assertTrue((w / "evidence.sha256").exists())                           # sealing precedes cleanup
        self.assertNotEqual(download.read_bytes(), (w / "lilith-b4-kroot-rehearsal-ff13bc6.tar").read_bytes())


if __name__ == "__main__":
    unittest.main()
