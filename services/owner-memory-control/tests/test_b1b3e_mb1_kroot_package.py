"""15B2b-B1b-3e M-B1: the real K-ROOT ceremony package (builder, operator script, custody checks) (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-mb1-kroot-ceremony-package.md.

Nothing here runs on the phone or creates a real K-ROOT. Every key below is a
throwaway TEST key in a temporary directory, under a TEST passphrase.
"""

from __future__ import annotations

import ast
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
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-mb1-kroot-ceremony-package.md"
OWNER_TOOL = ROOT / "services/authority-dev/ceremony/lilith_authority_owner_dev.py"
PYPATH = os.pathsep.join(str(ROOT / p) for p in ("services/core-api", "services/owner-memory-control"))
REPLICA_B_MANIFEST = (b'{"authorityProfile":"DEV_SYNTHETIC","environment":"dev","replicaId":"owner-offline-dev-synthetic-01",'
                      b'"replicaType":"LILITH_OWNER_FRESHNESS_REPLICA","schemaVersion":1}')
TEST_PASSPHRASE = "TEST_ONLY m-b1 package passphrase 42"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BUILD = _load("build_mb1_kroot_bundle", TOOLS / "build_mb1_kroot_bundle.py")
HAVE_CRYPTO = all(importlib.util.find_spec(m) is not None for m in ("cryptography", "rfc8785", "fido2"))


def _block() -> str:
    parts = [p.split("\n```", 1)[0] + "\n" for p in RECORD.read_text(encoding="utf-8").split("```bash\n")[1:]]
    found = [p for p in parts if p.startswith("# ===== M-B1")]
    assert len(found) == 1
    return found[0]


def _snippet(name: str) -> str:
    match = re.search(rf"^{name}=\$\(cat <<'PYEOF'\n(.*?)\nPYEOF\n\)$", _block(), re.S | re.M)
    assert match, name
    return match.group(1)


def _code_lines() -> list[str]:
    """Shell lines of the block, outside the Python heredocs and comments."""
    lines, inside = [], False
    for line in _block().splitlines():
        if line.endswith("<<'PYEOF'"):
            inside = True
            continue
        if inside:
            inside = line != "PYEOF"
            continue
        if not line.lstrip().startswith("#"):
            lines.append(line)
    return lines


class BuilderTests(unittest.TestCase):
    def test_closure_is_the_owner_tool_import_closure_plus_burned_identities(self):
        mods = {"lilith_owner_memory": ROOT / "services/owner-memory-control/lilith_owner_memory",
                "lilith_memory": ROOT / "services/core-api/lilith_memory"}
        seen: set[Path] = set()

        def visit(path: Path) -> None:
            if path in seen:
                return
            seen.add(path)
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom) and node.level:
                    for name in ([node.module] if node.module else [a.name for a in node.names]):
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
        visit(OWNER_TOOL)
        visit(ROOT / BUILD.BURNED)
        self.assertEqual(sorted(p.relative_to(ROOT).as_posix() for p in seen), sorted(BUILD.CLOSURE))
        self.assertNotIn("services/owner-memory-control/tools/termux_kroot_rehearsal.py", BUILD.CLOSURE)
        self.assertNotIn("services/authority-dev/ceremony/lilith_authority_keygen_dev.py", BUILD.CLOSURE)

    def fake_vendor(self, directory: Path) -> Path:
        vendor = directory / "vendor"
        for top in BUILD.VENDOR_TOPS:
            (vendor / top).mkdir(parents=True)
            (vendor / top / "__init__.py").write_text(f"# {top}\n", encoding="utf-8")
        return vendor

    def test_bundle_is_deterministic_and_exact(self):
        try:
            commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], check=True, capture_output=True,
                                    text=True).stdout.strip()
            subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{commit}:{BUILD.BURNED}"], check=True,
                           capture_output=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git or the committed source is unavailable")
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            vendor = self.fake_vendor(d)
            first, second = BUILD.build(ROOT, commit, vendor, d / "a.tar"), BUILD.build(ROOT, commit, vendor, d / "b.tar")
            self.assertEqual((d / "a.tar").read_bytes(), (d / "b.tar").read_bytes())
            self.assertEqual(first, {**second, "bundle": "a.tar"})
            self.assertEqual(first["top"], f"lilith-mb1-kroot-{commit[:7]}")
            with tarfile.open(d / "a.tar") as tar:
                members = tar.getmembers()
                files = {m.name.split("/", 1)[1]: tar.extractfile(m).read() for m in members if m.isfile()}
                self.assertTrue(all(m.mtime == 0 and m.uid == 0 and m.gid == 0 for m in members))
            expected = set(BUILD.CLOSURE) | {"SOURCE_COMMIT", "SHA256SUMS"} | {f"vendor/{t}/__init__.py" for t in BUILD.VENDOR_TOPS}
            self.assertEqual(set(files), expected)
            sums = dict(reversed(line.split("  ", 1)) for line in files["SHA256SUMS"].decode().splitlines())
            self.assertEqual(set(sums), expected - {"SHA256SUMS"})
            self.assertTrue(all(hashlib.sha256(files[n]).hexdigest() == h for n, h in sums.items()))
            for path in BUILD.CLOSURE:
                self.assertEqual(files[path], subprocess.run(["git", "-C", str(ROOT), "show", f"{commit}:{path}"],
                                                             check=True, capture_output=True).stdout)

    def test_builder_refusals(self):
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            vendor = self.fake_vendor(d)
            for commit, reason in (("HEAD", "COMMIT_NOT_40_HEX"), ("0" * 40, "SOURCE_NOT_AT_COMMIT")):
                with self.assertRaises(BUILD.BuildError) as caught:
                    BUILD.bundle_members(ROOT, commit, vendor)
                self.assertEqual(str(caught.exception), reason)
            with mock.patch.object(BUILD, "CLOSURE", (*BUILD.CLOSURE, "x/k-root.der")):
                with self.assertRaises(BUILD.BuildError) as caught:
                    BUILD.bundle_members(ROOT, "0" * 40, vendor)
                self.assertEqual(str(caught.exception), "FORBIDDEN_MEMBER_NAME:x/k-root.der")
            (vendor / "extra").mkdir()
            with self.assertRaises(BUILD.BuildError) as caught:
                BUILD.bundle_members(ROOT, "0" * 40, vendor)
            self.assertEqual(str(caught.exception), "VENDOR_SET_MISMATCH")


class RecordAndPinTests(unittest.TestCase):
    def test_recorded_digest_and_pins(self):
        text, block = RECORD.read_text(encoding="utf-8"), _block()
        start = text.index("`mb1_phone_commands.sh` (SHA-256 `")
        self.assertEqual(text[start:start + 200].split("`")[3], hashlib.sha256(block.encode()).hexdigest())
        tar_sha = re.search(r"\*\*bundle SHA-256\*\* \| `([0-9a-f]{64})`", text).group(1)
        sums_sha = re.search(r"`SHA256SUMS` \(inside the bundle\) \| `([0-9a-f]{64})`", text).group(1)
        for pin in (f"TAR_SHA={tar_sha}", f"SUMS_SHA={sums_sha}", "SRC=c6940615875fd13df1636d7c105ad5b65c39d112",
                    "NFILES=74", "TAR=lilith-mb1-kroot-c694061.tar", 'R="$HOME/lilith-owner-offline-dev-synthetic-01"',
                    'K="$HOME/lilith-kroot-dev-synthetic"', 'KEY="$K/k-root.der"'):
            self.assertIn(pin, block)


class StructureTests(unittest.TestCase):
    def test_every_stop_is_a_hard_stop(self):
        code = _code_lines()
        self.assertFalse([l for l in code if re.search(r'(?<!builtin )echo "STOP', l)])
        self.assertIn('stop() { builtin echo "STOP: $*" >&2; exit 1; }', code)
        self.assertFalse([l for l in code if re.search(r"^\s*\{.*\}\s*\|\s*tee", l) or l.startswith("echo()")])

    def test_only_root_keygen_runs_and_nothing_else_of_authority(self):
        block = _block()
        self.assertEqual(block.count(' root-keygen "$KEY"'), 1)
        self.assertEqual(len(re.findall(r'"\$TOOL"', block)), 2)          # root-keygen and the unlock check's import
        for forbidden in ("registry-v1", "witness-anchor", "reproduce", "package-digest", "keygen_dev", "K-WIT",
                          "systemctl", "genesis-pin", "append", "init-real-replica", "owner_freshness_tool"):
            self.assertNotIn(forbidden, "\n".join(_code_lines()), forbidden)
        for command in (r"\bscp\b", r"\bcurl\b", r"\bwget\b", r"\bnc\b", r"\badb\b", r"\brsync\b", r"\bgcloud\b",
                        r"\bssh\s", r"\brm -r", r"\bshred\b", r"\bmv\b", r"\beval\b"):
            self.assertFalse([l for l in _code_lines() if re.search(command, l)], command)

    def test_passphrase_only_through_getpass(self):
        block = _block()
        self.assertFalse(re.search(r"(?i)passphrase=|--passphrase|PASS[A-Z_]*=|read -s|stty", "\n".join(_code_lines())))
        self.assertEqual([l for l in _code_lines() if re.search(r"(^|[;&|]\s*)read\s", l)],
                         ['read -r answer < /dev/tty || stop "no confirmation"'])
        self.assertIn("getpass.getpass(", _snippet("UNLOCK_CHECK"))
        for name in ("ANCHOR_CHECK", "BURNED_CHECK", "AT_REST_CHECK"):
            self.assertNotIn("getpass", _snippet(name))
        self.assertIn('[ -z "${SSH_CONNECTION-}${SSH_CLIENT-}${SSH_TTY-}" ]', block)
        tool = OWNER_TOOL.read_text(encoding="utf-8")
        self.assertIn('getpass.getpass("K-ROOT passphrase: ")', tool)
        self.assertFalse(re.search(r"os\.environ|getenv", tool))           # no environment-variable passphrase

    def test_private_key_never_leaves_its_directory(self):
        for line in _code_lines():
            if '"$KEY"' in line or '"$K"' in line:
                self.assertFalse(re.search(r'\b(cp|mv|tar|cat|dd|base64|xxd|od|tee)\b[^|;]*"\$(KEY|K)"', line), line)
                self.assertNotIn('echo "$KEY', line)
        export = [l for l in _code_lines() if l.startswith('tar -cf "$X"')]
        self.assertEqual(len(export), 1)
        self.assertIn("lilith-kroot-dev-synthetic-public", export[0])
        self.assertNotRegex(export[0], r"lilith-kroot-dev-synthetic( |$)")
        self.assertNotIn('"$K"', export[0])

    def test_replica_b_is_read_only(self):
        for line in _code_lines():
            if '"$R' in line and not line.startswith("R="):
                self.assertFalse(re.search(r"\b(cp|mv|rm|mkdir|touch|tee|chmod|ln)\b|>\s*\"\$R", line), line)


@unittest.skipUnless(HAVE_CRYPTO, "needs cryptography and rfc8785")
class EmbeddedCheckTests(unittest.TestCase):
    def py(self, name: str, *args: str) -> subprocess.CompletedProcess:
        path = os.pathsep.join(p for p in (PYPATH, os.environ.get("PYTHONPATH", "")) if p)
        return subprocess.run([sys.executable, "-B", "-c", _snippet(name), *args], capture_output=True, text=True,
                              env={**os.environ, "PYTHONPATH": path})

    def keygen(self, directory: Path) -> tuple[Path, Path]:
        tool = _load("owner_tool_for_test", OWNER_TOOL)
        key = directory / "k-root.der"
        out = directory / "root-keygen.json"
        out.write_text(tool._jcs(tool.root_keygen(key, passphrase=TEST_PASSPHRASE.encode())) + "\n", encoding="utf-8")
        return key, out

    def test_anchor_check(self):
        with tempfile.TemporaryDirectory() as directory:
            key, out = self.keygen(Path(directory))
            ok = self.py("ANCHOR_CHECK", str(out))
            self.assertEqual(ok.returncode, 0, ok.stderr)
            self.assertEqual(ok.stdout.splitlines()[0], "ANCHOR_VALID")
            fingerprint = json.loads(out.read_text())["publicKeySha256"]
            self.assertEqual(ok.stdout.splitlines()[1], f"FINGERPRINT {fingerprint}")
            for tamper in ({"publicKeySha256": "0" * 64}, {"extra": 1}):
                value = {**json.loads(out.read_text()), **tamper}
                out.write_text(json.dumps(value), encoding="utf-8")
                self.assertNotEqual(self.py("ANCHOR_CHECK", str(out)).returncode, 0, tamper)

    def test_burned_check_refuses_each_of_the_12(self):
        sys.path[:0] = PYPATH.split(os.pathsep)
        from lilith_owner_memory import burned_identities as BI
        every = BI.BURNED_PUBLIC_KEY_SHA256 | BI.BURNED_REGISTRY_DIGESTS | BI.BURNED_GENESIS_WITNESS_DIGESTS
        self.assertEqual(len(every), 12)
        for value in every:
            result = self.py("BURNED_CHECK", value)
            self.assertNotEqual(result.returncode, 0, value)
            self.assertIn("equals a burned rehearsal identity", result.stderr)
        fresh = self.py("BURNED_CHECK", hashlib.sha256(os.urandom(32)).hexdigest())
        self.assertEqual((fresh.returncode, fresh.stdout.strip()), (0, "NOT_A_BURNED_IDENTITY"))

    def test_at_rest_check(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
        with tempfile.TemporaryDirectory() as directory:
            key, _ = self.keygen(Path(directory))
            self.assertEqual(self.py("AT_REST_CHECK", str(key)).stdout.strip(), "KEY_ENCRYPTED_AT_REST")
            plain = Path(directory) / "plain.der"
            plain.write_bytes(Ed25519PrivateKey.generate().private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption()))
            self.assertNotEqual(self.py("AT_REST_CHECK", str(plain)).returncode, 0)


@unittest.skipUnless(os.name == "posix" and HAVE_CRYPTO, "runs the pinned script under a real pseudo-terminal")
class PtyRunTests(unittest.TestCase):
    """The pinned script, run under a pty so getpass reads the terminal exactly as on the S25. Only the bundle
    pins, the file count, the Termux prefix in priv(), and the /proc scan root are substituted."""

    RUN = ('bash "$HOME/storage/downloads/mb1_phone_commands.sh" 2>&1 | tee "$HOME/lilith-mb1.transcript.txt"; '
           'echo "RUN_EXIT=${PIPESTATUS[0]}" | tee -a "$HOME/lilith-mb1.transcript.txt"')

    def setUp(self):
        import pty  # noqa: F401  (POSIX only)
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.root)])
        self.home = self.root / "home"
        self.downloads = self.home / "storage/downloads"
        for d in (self.downloads, self.root / "tmp", self.root / "bin", self.root / "proc/1"):
            d.mkdir(parents=True)
        (self.root / "proc/1/comm").write_text("bash\n")
        (self.root / "bin/python").symlink_to(sys.executable)
        replica = self.home / "lilith-owner-offline-dev-synthetic-01"
        (replica / "records").mkdir(parents=True)
        (replica / "REPLICA.json").write_bytes(REPLICA_B_MANIFEST)
        top = "lilith-mb1-kroot-c694061"
        files = {path: (ROOT / path).read_bytes() for path in BUILD.CLOSURE}
        for package in ("rfc8785", "fido2"):                                 # vendor/, as in the real bundle
            origin = Path(importlib.util.find_spec(package).origin).parent
            for file in sorted(origin.rglob("*")):
                if file.is_file() and "__pycache__" not in file.parts and file.suffix != ".pyc":
                    files[f"vendor/{package}/{file.relative_to(origin).as_posix()}"] = file.read_bytes()
        files["SOURCE_COMMIT"] = b"stub0commit\n"
        files["SHA256SUMS"] = "".join(f"{hashlib.sha256(v).hexdigest()}  {k}\n" for k, v in sorted(files.items())).encode()
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            for name, data in files.items():
                info = tarfile.TarInfo(f"{top}/{name}")
                info.size, info.mode = len(data), 0o644
                tar.addfile(info, io.BytesIO(data))
        (self.downloads / f"{top}.tar").write_bytes(buf.getvalue())
        block = _block()
        script = (block.replace(re.search(r"TAR_SHA=[0-9a-f]{64}", block).group(0), f"TAR_SHA={hashlib.sha256(buf.getvalue()).hexdigest()}")
                  .replace(re.search(r"SUMS_SHA=[0-9a-f]{64}", block).group(0), f"SUMS_SHA={hashlib.sha256(files['SHA256SUMS']).hexdigest()}")
                  .replace("SRC=c6940615875fd13df1636d7c105ad5b65c39d112", "SRC=stub0commit")
                  .replace("NFILES=74", f"NFILES={len(files)}")
                  .replace("/data/data/com.termux/*|/data/user/0/com.termux/*", f"{self.root}/*")
                  .replace("/proc/[0-9]*/comm", f"{self.root}/proc/[0-9]*/comm"))
        (self.downloads / "mb1_phone_commands.sh").write_text(script, encoding="utf-8")

    def run_script(self, answers, env_extra=None) -> tuple[str, str]:
        import pty
        env = {"HOME": str(self.home), "PREFIX": str(self.root), "TMPDIR": str(self.root / "tmp"), "TERM": "dumb",
               "PATH": f"{self.root / 'bin'}:/usr/bin:/bin", **(env_extra or {})}
        pid, fd = pty.fork()
        if pid == 0:
            os.chdir(self.home)
            os.execve("/bin/bash", ["bash", "-c", self.RUN], env)
        out, pending, pos = b"", list(answers), 0
        while True:
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
            while pending and pending[0][0].encode() in out[pos:]:
                prompt, reply = pending.pop(0)
                pos = out.index(prompt.encode(), pos) + len(prompt)
                os.write(fd, (reply + "\n").encode())
        os.waitpid(pid, 0)
        transcript = (self.home / "lilith-mb1.transcript.txt").read_text(encoding="utf-8")
        return transcript, out.decode("utf-8", "replace")

    GEN = ("Type GENERATE to continue: ", "GENERATE")
    KP, RP, UP = (("K-ROOT passphrase: ", TEST_PASSPHRASE), ("repeat: ", TEST_PASSPHRASE),
                  ("K-ROOT passphrase (unlock check): ", TEST_PASSPHRASE))

    def key_dir(self):
        k = self.home / "lilith-kroot-dev-synthetic"
        return sorted(os.listdir(k)) if k.exists() else None

    def assertStopped(self, transcript: str, message: str):
        self.assertTrue(transcript.endswith("RUN_EXIT=1\n"), transcript)
        self.assertIn(f"STOP: {message}", transcript)
        self.assertNotIn("MB1_KROOT_GENERATED", transcript)
        self.assertNotIn("MB1_KROOT_FINGERPRINT", transcript)
        self.assertFalse((self.home / "lilith-mb1-export.tar").exists())
        self.assertTrue((self.downloads / "lilith-mb1-kroot-c694061.tar").exists())

    def test_clean_run(self):
        transcript, _ = self.run_script([self.GEN, self.KP, self.RP, self.UP])
        self.assertTrue(transcript.endswith("MB1_KROOT_GENERATED\nRUN_EXIT=0\n"), transcript)
        self.assertFalse([l for l in transcript.splitlines() if l.startswith("STOP")])
        self.assertNotIn(TEST_PASSPHRASE, transcript)
        key = self.home / "lilith-kroot-dev-synthetic/k-root.der"
        self.assertEqual((self.key_dir(), oct(key.stat().st_mode & 0o777)), (["k-root.der"], "0o600"))
        with tarfile.open(self.home / "lilith-mb1-export.tar") as tar:
            names = sorted(m.name for m in tar.getmembers() if m.isfile())
            blobs = [tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()]
        self.assertFalse([n for n in names if "lilith-kroot-dev-synthetic/" in n or n.endswith(".der")])
        self.assertEqual(len(names), 14)
        self.assertFalse([b for b in blobs if key.read_bytes()[16:48] in b])
        self.assertNotIn(key.read_bytes()[16:48].hex(), transcript)
        fp = re.search(r"MB1_KROOT_FINGERPRINT publicKeySha256=([0-9a-f]{64})", transcript).group(1)
        self.assertEqual((self.home / "lilith-kroot-dev-synthetic-public/k-root.publicKeySha256").read_text().strip(), fp)
        self.assertFalse((self.downloads / "lilith-mb1-kroot-c694061.tar").exists())

    def test_passphrase_mismatch_writes_no_key(self):
        transcript, _ = self.run_script([self.GEN, self.KP, ("repeat: ", TEST_PASSPHRASE + "x")])
        self.assertStopped(transcript, "root-keygen refused or failed (2)")
        self.assertEqual(self.key_dir(), [])

    def test_wrong_unlock_passphrase_presents_no_fingerprint(self):
        transcript, _ = self.run_script([self.GEN, self.KP, self.RP, ("K-ROOT passphrase (unlock check): ", "wrong passphrase 123")])
        self.assertStopped(transcript, "the passphrase does not unlock the key")
        self.assertEqual(self.key_dir(), ["k-root.der"])                     # C-2: kept, never recorded
        self.assertFalse((self.home / "lilith-kroot-dev-synthetic-public").exists())

    def test_ssh_session_stops_before_any_write(self):
        transcript, _ = self.run_script([], {"SSH_CONNECTION": "10.0.0.1 1 10.0.0.2 22"})
        self.assertStopped(transcript, "SSH session")
        self.assertFalse((self.home / "lilith-mb1").exists())

    def test_running_sshd_stops_before_any_write(self):
        (self.root / "proc/2").mkdir()
        (self.root / "proc/2/comm").write_text("sshd\n")
        transcript, _ = self.run_script([])
        self.assertStopped(transcript, "sshd is running")
        self.assertIsNone(self.key_dir())

    def test_owner_decline_stops_before_the_key_directory(self):
        transcript, _ = self.run_script([("Type GENERATE to continue: ", "no")])
        self.assertStopped(transcript, "owner did not confirm")
        self.assertIsNone(self.key_dir())


if __name__ == "__main__":
    unittest.main()
