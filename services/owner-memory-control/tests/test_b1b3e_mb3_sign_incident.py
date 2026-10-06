"""15B2b-B1b-3e M-B3 SIGN attempt 1 incident: real-terminal regression and end-to-end tests (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-mb3-sign-attempt1-incident.md.

The attempt-1 phone script (`db02909d…`) opened `/dev/tty` with text-mode "r+"
in `_tty_confirm`. That builds a BufferedRandom, which refuses a non-seekable
terminal with `io.UnsupportedOperation: File or stream is not seekable.` before
the confirmation prompt and before the signer. The package tests had replaced
`confirm`, `show` and `run_signer`, so the real terminal path never ran.

These tests run the REAL terminal path under a real pseudo-terminal (`pty.fork`
makes it the child's controlling terminal, so `/dev/tty` is the pty):

- the real `_tty_confirm`, fixed and as reconstructed byte-exactly from the
  incident script (whose SHA-256 is asserted to be the attempt-1 pin);
- an end-to-end SIGN with the real `_tty_show`, `_tty_confirm` and
  `_signer_subprocess` (the real `registry-v1` subprocess, whose `getpass`
  reads the TEST passphrase from the pty), and the failure paths.

Only throwaway TEST keys and TEST passphrases in temporary directories are used.
No real K-ROOT, K-WIT or K-ACT data. Failure messages redact 64-hex values.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import select
import shutil
import signal
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TESTS = Path(__file__).resolve().parent
TOOLS = ROOT / "services/owner-memory-control/tools"
SCRIPT = TOOLS / "mb3_phone_ceremony.py"
ATTEMPT1_SCRIPT_SHA = "db02909d8f769f5a0570386aef55c3a472bdbc6c52949830ab94c1b624e6bd54"
INCIDENT_STOP = "unexpected UnsupportedOperation: File or stream is not seekable."
FIXED_CONFIRM = b'''def _tty_confirm(prompt: str) -> str:
    # Separate write-only and read-only handles: a terminal is not seekable, and text-mode "r+"
    # (BufferedRandom) refuses it with UnsupportedOperation (M-B3 attempt-1 incident).
    with open("/dev/tty", "w", encoding="utf-8") as out, open("/dev/tty", "r", encoding="utf-8") as tty:
        out.write(prompt)
        out.flush()
        return tty.readline().strip()'''
ATTEMPT1_CONFIRM = b'''def _tty_confirm(prompt: str) -> str:
    with open("/dev/tty", "r+", encoding="utf-8") as tty:
        tty.write(prompt)
        tty.flush()
        return tty.readline().strip()'''
POSIX_PTY = os.name == "posix" and importlib.util.find_spec("pty") is not None


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _r(text: str) -> str:
    return re.sub(r"[0-9a-f]{64}", "<redacted>", str(text))


class RedactedFailures:
    def _formatMessage(self, msg, standardMsg):
        return _r(super()._formatMessage(msg, standardMsg))


def attempt1_script_bytes() -> bytes:
    """The exact attempt-1 script: the current script with only the fix reverted."""
    current = SCRIPT.read_bytes()
    assert current.count(FIXED_CONFIRM) == 1, "the fix is not exactly the reviewed one"
    return current.replace(FIXED_CONFIRM, ATTEMPT1_CONFIRM)


def run_in_pty(target, responses=(), timeout=90.0) -> tuple[int, bytes]:
    """Run target() in a child whose controlling terminal is a new pty.

    `responses` is an ordered list of (trigger, reply): each reply is typed once,
    after its trigger appears in output produced since the previous reply.
    Returns (exit code, everything the terminal showed).
    """
    import pty
    pid, fd = pty.fork()
    if pid == 0:                                      # child: never returns into unittest
        code = 99
        try:
            code = int(target())
        except BaseException:                         # noqa: BLE001 - report and exit
            import traceback
            traceback.print_exc()
            code = 98
        finally:
            os._exit(code)
    seen, scan, pending = b"", 0, list(responses)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ready, _, _ = select.select([fd], [], [], 0.2)
        if fd in ready:
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                chunk = b""
            if not chunk:
                break
            seen += chunk
            if pending and pending[0][0] in seen[scan:]:
                os.write(fd, pending.pop(0)[1])
                scan = len(seen)
    else:
        os.kill(pid, signal.SIGKILL)
    os.close(fd)
    _, status = os.waitpid(pid, 0)
    return (os.waitstatus_to_exitcode(status) if hasattr(os, "waitstatus_to_exitcode") else status >> 8), seen


@unittest.skipUnless(POSIX_PTY, "needs a posix pseudo-terminal")
class AttemptOneScriptTests(unittest.TestCase):
    def test_reconstructed_script_is_the_attempt1_pin(self):
        self.assertEqual(hashlib.sha256(attempt1_script_bytes()).hexdigest(), ATTEMPT1_SCRIPT_SHA)
        self.assertNotEqual(hashlib.sha256(SCRIPT.read_bytes()).hexdigest(), ATTEMPT1_SCRIPT_SHA)

    def test_only_tty_confirm_changed(self):
        old = attempt1_script_bytes().decode().splitlines()
        new = SCRIPT.read_bytes().decode().splitlines()
        changed = [line for line in set(old) ^ set(new)]
        for line in changed:
            self.assertTrue(line.strip().startswith(("with open(\"/dev/tty\"", "tty.write", "tty.flush", "out.write",
                                                     "out.flush", "# Separate write-only", "# (BufferedRandom)")),
                            line)
        confirm = SCRIPT.read_text(encoding="utf-8").split("def _tty_confirm", 1)[1].split("\ndef ", 1)[0]
        self.assertNotIn('open("/dev/tty", "r+"', confirm)
        self.assertIn('open("/dev/tty", "w", encoding="utf-8") as out, open("/dev/tty", "r", encoding="utf-8") as tty',
                      confirm)


@unittest.skipUnless(POSIX_PTY, "needs a posix pseudo-terminal")
class RealTtyConfirmTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.fixed = _load("mb3_phone_incident_fixed", SCRIPT)
        old_path = self.dir / "mb3_phone_ceremony_attempt1.py"
        old_path.write_bytes(attempt1_script_bytes())
        self.old = _load("mb3_phone_incident_attempt1", old_path)

    def tearDown(self):
        self.tmp.cleanup()

    def confirm_in_pty(self, module, reply: bytes):
        result = self.dir / "result.json"

        def child():
            try:
                answer = module._tty_confirm("CONFIRM-PROMPT> ")
                result.write_text(json.dumps({"answer": answer}))
            except Exception as exc:                  # noqa: BLE001 - recorded for the parent
                result.write_text(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
            return 0
        code, shown = run_in_pty(child, [(b"CONFIRM-PROMPT> ", reply)])
        return code, shown, json.loads(result.read_text())

    def test_fixed_confirm_shows_prompt_and_reads_answer_on_a_real_terminal(self):
        code, shown, result = self.confirm_in_pty(self.fixed, b"SIGN-ONCE 0123456789abcdef\n")
        self.assertEqual(code, 0)
        self.assertIn(b"CONFIRM-PROMPT> ", shown)
        self.assertEqual(result, {"answer": "SIGN-ONCE 0123456789abcdef"})

    def test_attempt1_confirm_fails_exactly_as_on_the_s25(self):
        code, shown, result = self.confirm_in_pty(self.old, b"never-typed\n")
        self.assertEqual(code, 0)
        self.assertEqual(result, {"error": "UnsupportedOperation: File or stream is not seekable."})
        self.assertNotIn(b"CONFIRM-PROMPT> ", shown)       # the prompt was never displayed

    def test_the_terminal_is_not_seekable(self):
        result = self.dir / "seek.json"

        def child():
            import io
            fd = os.open("/dev/tty", os.O_RDWR)
            result.write_text(json.dumps({"seekable": io.FileIO(fd, closefd=False).seekable()}))
            os.close(fd)
            return 0
        self.assertEqual(run_in_pty(child)[0], 0)
        self.assertEqual(json.loads(result.read_text()), {"seekable": False})


def _site_pth(home: Path) -> None:
    """Test environment only: let the real signer subprocess find the native deps.

    The phone script passes the signer an environment of PATH, HOME, PYTHONPATH
    (the bundle only) and PYTHONDONTWRITEBYTECODE. On the S25, `cryptography` is
    system-installed. Where this test process gets it from PYTHONPATH instead, a
    user-site .pth under the test HOME exposes the same directories.
    """
    dirs = set()
    for name in ("cryptography", "cffi"):
        spec = importlib.util.find_spec(name)
        if spec is not None and spec.origin:
            dirs.add(str(Path(spec.origin).parent.parent))
    backend = importlib.util.find_spec("_cffi_backend")
    if backend is not None and backend.origin:
        dirs.add(str(Path(backend.origin).parent))
    site =home / ".local" / "lib" / f"python{sys.version_info[0]}.{sys.version_info[1]}" / "site-packages"
    site.mkdir(parents=True, exist_ok=True)
    (site / "mb3-test-deps.pth").write_text("\n".join(sorted(dirs)) + "\n")


@unittest.skipUnless(POSIX_PTY and shutil.which("git"), "needs a posix pseudo-terminal and git")
class RealTerminalSignTests(RedactedFailures, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.PKG = _load("mb3_pkg_fixtures_for_incident", TESTS / "test_b1b3e_mb3_registry_package.py")
        if not cls.PKG.HAVE_CRYPTO:
            raise unittest.SkipTest("cryptography, rfc8785 and fido2 are required")
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        cls.vendor = cls.PKG._vendor_from_installed(d)
        if cls.vendor is None:
            raise unittest.SkipTest("installed fido2 / rfc8785 dist-info layout differs")
        cls.repo, cls.commit = cls.PKG._temp_repo(d)
        cls.built = cls.PKG.BUILD.build(cls.repo, cls.commit, cls.vendor, d / "bundle.tar")
        cls.bundle_raw = (d / "bundle.tar").read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.case = tempfile.TemporaryDirectory()
        base = Path(self.case.name)
        self.home = base / "home"
        self.home.mkdir()
        _site_pth(self.home)
        self.world = self.PKG.World(base)
        downloads = self.home / "storage/downloads"
        downloads.mkdir(parents=True)
        (downloads / f"lilith-mb3-registry-{self.commit[:7]}.tar").write_bytes(self.bundle_raw)
        (downloads / "mb3-kact-publication.json").write_bytes(self.world.kact_raw)
        (downloads / "mb3-kwit-publication.json").write_bytes(self.world.kwit_raw)
        pub = self.home / "lilith-kroot-dev-synthetic-public"
        pub.mkdir(mode=0o700)
        (pub / "k-root-anchor.json").write_bytes(self.world.root_raw)
        keydir = self.home / "lilith-kroot-dev-synthetic"
        keydir.mkdir(mode=0o700)
        shutil.copyfile(self.world.key_path, keydir / "k-root.der")
        os.chmod(keydir / "k-root.der", 0o600)
        os.chmod(keydir, 0o700)
        self.out_file = base / "phone-out.txt"
        self.calls_file = base / "signer-calls.txt"

    def tearDown(self):
        self.case.cleanup()

    def module(self, attempt1: bool):
        if not attempt1:
            return _load("mb3_phone_incident_e2e", SCRIPT), SCRIPT
        path = Path(self.case.name) / "mb3_phone_ceremony_attempt1.py"
        path.write_bytes(attempt1_script_bytes())
        return _load("mb3_phone_incident_e2e_attempt1", path), path

    def phone(self, module, script: Path, *, real_terminal: bool):
        out_file, calls_file = self.out_file, self.calls_file

        def counting_signer(argv, out_fd, err_fd, env):
            with open(calls_file, "a", encoding="utf-8") as calls:
                calls.write(json.dumps({"argv": argv, "env": sorted(env)}) + "\n")
            return module._signer_subprocess(argv, out_fd, err_fd, env)     # the REAL subprocess path

        def out(line):
            with open(out_file, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        fields = dict(home=self.home, require_termux_private=False, proc=self.home / "noproc",
                      environ={"PATH": os.environ.get("PATH", "/usr/bin:/bin")}, accepted=self.world.accepted,
                      script=script, out=out, run_signer=counting_signer)
        if not real_terminal:
            fields["interactive"] = lambda: True
        return module.Phone(**fields)                 # confirm / show stay the REAL /dev/tty functions

    def prepare(self, module, script):
        module.prepare(self.phone(module, script, real_terminal=False), control_sha=self.commit,
                       bundle_sha256=self.built["tarSha256"], kact_publication_sha256=self.world.kact_sha)
        manifest_raw = (self.home / "lilith-mb3/mb3-inputs.json").read_bytes()
        return json.loads(manifest_raw), hashlib.sha256(manifest_raw).hexdigest()

    def sign_in_pty(self, module, script, manifest_sha, responses):
        def child():
            try:
                return module.sign(self.phone(module, script, real_terminal=True), control_sha=self.commit,
                                   bundle_sha256=self.built["tarSha256"], manifest_sha256=manifest_sha)
            except module.Stop as stopped:
                with open(self.out_file, "a", encoding="utf-8") as handle:
                    handle.write(f"STOP: {stopped}\n")
                return 1
        return run_in_pty(child, responses)

    def calls(self) -> list:
        return [json.loads(l) for l in self.calls_file.read_text().splitlines()] if self.calls_file.exists() else []

    def outcome(self) -> dict:
        return json.loads((self.home / "lilith-mb3/evidence/sign-outcome.json").read_bytes())

    def assert_retry_refused(self, module, script, manifest_sha):
        before = len(self.calls())
        with self.assertRaises(module.Stop) as caught:
            module.sign(self.phone(module, script, real_terminal=False), control_sha=self.commit,
                        bundle_sha256=self.built["tarSha256"], manifest_sha256=manifest_sha)
        self.assertIn("ATTEMPT_ALREADY_CONSUMED", str(caught.exception))
        self.assertEqual(len(self.calls()), before)

    def test_end_to_end_sign_through_a_real_terminal(self):
        module, script = self.module(attempt1=False)
        manifest, manifest_sha = self.prepare(module, script)
        digest = manifest["expectedRegistryDigest"]
        code, shown = self.sign_in_pty(module, script, manifest_sha, [
            (b"Type 'SIGN-ONCE ", f"SIGN-ONCE {digest[:16]}\n".encode()),
            (b"K-ROOT passphrase: ", (self.PKG.TEST_PASSPHRASE + "\n").encode()),
        ])
        out = self.out_file.read_text()
        self.assertEqual(code, 0, _r(out + shown.decode(errors="replace")))
        self.assertIn(f"CANDIDATE {digest}".encode(), shown)                      # real _tty_show
        self.assertEqual(shown.count(b"Type 'SIGN-ONCE "), 1)                    # real _tty_confirm
        self.assertEqual(shown.count(b"K-ROOT passphrase: "), 1)                 # real getpass, once
        self.assertNotIn(self.PKG.TEST_PASSPHRASE.encode(), shown)               # never echoed
        calls = self.calls()
        self.assertEqual(len(calls), 1)                                          # exactly one signer run
        self.assertEqual(calls[0]["argv"][3:5], ["registry-v1", str(self.home / "lilith-kroot-dev-synthetic/k-root.der")])
        self.assertEqual(calls[0]["env"], ["HOME", "PATH", "PYTHONDONTWRITEBYTECODE", "PYTHONPATH"])
        self.assertIn("MB3_TECHNICAL_STATE=REGISTRY_SIGNED", out)
        self.assertEqual((self.home / "lilith-mb3/sign/registry-v1.exit").read_text(), "exit=0\n")
        self.assertEqual((self.home / "lilith-mb3/sign/registry-v1.stderr").read_bytes(), b"")
        self.assertEqual((self.home / "lilith-mb3-registry-public/authority-registry.v1.digest").read_text().strip(),
                         digest)
        verifier = _load("verify_mb3_registry_incident", TOOLS / "verify_mb3_registry.py")
        ok, lines, detail = verifier.verify_export(
            self.home / "lilith-mb3-export.tar", control_sha=self.commit, bundle_sha256=self.built["tarSha256"],
            manifest_sha256=manifest_sha, kact_publication_sha256=self.world.kact_sha, accepted=self.world.accepted)
        self.assertTrue(ok, detail)
        self.assertEqual(detail, digest)
        self.assertIn("KROOT_SIGNATURE_VERIFIED", lines)
        self.assert_retry_refused(module, script, manifest_sha)

    def test_attempt1_script_reproduces_the_incident_end_to_end(self):
        module, script = self.module(attempt1=True)
        manifest, manifest_sha = self.prepare(module, script)
        code, shown = self.sign_in_pty(module, script, manifest_sha, [
            (b"Type 'SIGN-ONCE ", f"SIGN-ONCE {manifest['expectedRegistryDigest'][:16]}\n".encode()),
        ])
        self.assertEqual(code, 1)
        self.assertIn(f"STOP: {INCIDENT_STOP}", self.out_file.read_text())
        self.assertIn(b"CANDIDATE ", shown)                                     # show worked
        self.assertNotIn(b"Type 'SIGN-ONCE ", shown)                            # the prompt never appeared
        self.assertNotIn(b"K-ROOT passphrase", shown)
        self.assertEqual(self.calls(), [])                                     # signer never invoked
        outcome = self.outcome()
        self.assertEqual((outcome["outcome"], outcome["invoked"], outcome["burnRecorded"], outcome["stop"]),
                         ("A_NO_SIGNATURE", False, False, INCIDENT_STOP))
        for absent in ("sign/registry-v1.stdout", "sign/registry-v1.stderr", "sign/registry-v1.exit", "burn"):
            self.assertFalse((self.home / "lilith-mb3" / absent).exists(), absent)
        self.assertTrue((self.home / "lilith-mb3-failure-export.tar").is_file())
        self.assertFalse((self.home / "lilith-mb3-registry-public").exists())
        self.assert_retry_refused(module, script, manifest_sha)

    def test_wrong_confirmation_on_the_real_terminal_consumes_without_signer(self):
        module, script = self.module(attempt1=False)
        _, manifest_sha = self.prepare(module, script)
        code, shown = self.sign_in_pty(module, script, manifest_sha, [(b"Type 'SIGN-ONCE ", b"no\n")])
        self.assertEqual(code, 1)
        self.assertNotIn(b"K-ROOT passphrase", shown)
        self.assertEqual(self.calls(), [])
        outcome = self.outcome()
        self.assertEqual((outcome["outcome"], outcome["invoked"], outcome["burnRecorded"]),
                         ("A_NO_SIGNATURE", False, False))
        self.assertFalse((self.home / "lilith-mb3/sign/registry-v1.stdout").exists())
        self.assertFalse((self.home / "lilith-mb3/burn").exists())
        self.assert_retry_refused(module, script, manifest_sha)


RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-mb3-sign-attempt1-incident.md"
CANDIDATE = "b7e24530a21757a5bef996ec9adb13ed5932ab04edb1943321f529e3206c0e53"
FIXED_SCRIPT_SHA = "b58b93215dc5c1e724846c7fc16acc2c29d81725a2ba13badcdccfd7b9eaecc7"
REAL_PINS = {
    "MANIFEST_SHA": "52478f462509cb7904791a80cd0e0dfa70316ae48b6fc4d7830dd64e5de2aa2e",
    "FAILURE_SHA": "658f4af661f7933c258acc8ba18fae5fcd60696ed0d2a4d20dcc1157e92e2de3",
    "SCRIPT_SHA": ATTEMPT1_SCRIPT_SHA,
    "BUNDLE_SHA": "fce71811073eeb98ce82b5db60dcefb5b7abb12119ed609d35a055bee7360cb0",
    "KACT_SHA": "d76479762007afef828f3901591647dc4a2fb2205f4afac527b66d2cc9c6b032",
    "KWIT_SHA": "9e9dd0787b3d6df8d40730c6abab728cacbe5136269ca4421160da830bb23472",
    "READBACK_SHA": "27dfb73ce42746eeb8effb0338dae5146bbc69a0e7411745eb0c7457c6da45e4",
}


def disposition_block() -> str:
    parts = [p.split("\n```", 1)[0] + "\n" for p in RECORD.read_text(encoding="utf-8").split("```bash\n")[1:]]
    found = [p for p in parts if p.startswith("# ===== M-B3 attempt-1 incident disposition")]
    assert len(found) == 1
    return found[0]


class IncidentRecordTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = self.text.split("## 10. State", 1)[1]
        self.posture = self.text.split("## 9. Authorization posture", 1)[1].split("## 10.", 1)[0]

    def test_classification_and_facts(self):
        for line in ("MB3_SIGN_ATTEMPT_1 = CLOSED / INCIDENT / A_NO_SIGNATURE", "SIGNER_INVOKED = NO", "KROOT_ACCESSED = NO",
                     "PASSPHRASE_PROMPT_REACHED = NO", "SIGNATURE_POSSIBLE = NO", "BURN_STATUS = NO_REAL_REGISTRY_BURN",
                     f"CANDIDATE {CANDIDATE} = HISTORICAL_ABANDONED_UNSIGNED_CANDIDATE",
                     "HISTORICAL_ABANDONED_UNSIGNED_CANDIDATE != BURNED_REGISTRY_DIGEST",
                     "HISTORICAL RETENTION != PERMISSION TO REUSE", "PACKAGE_REFINALIZATION_REQUIRED = YES",
                     f"PRE-MERGE FIXED PHONE SCRIPT {FIXED_SCRIPT_SHA}"):
            self.assertIn(line, self.state)
        for value in ("a86d032211ebb421e3777aa43cc2da31b0093c28", "1f544e695742fd4a93fcf4fd8dc5d706e24eb452",
                      ATTEMPT1_SCRIPT_SHA, "2026-10-06T12:11:49Z", REAL_PINS["FAILURE_SHA"], INCIDENT_STOP):
            self.assertIn(value, self.text)
        self.assertEqual(hashlib.sha256(SCRIPT.read_bytes()).hexdigest(), FIXED_SCRIPT_SHA)

    def test_candidate_is_not_burned_anywhere(self):
        sys.path.insert(0, str(ROOT / "services/owner-memory-control"))
        from lilith_owner_memory import burned_identities as BI
        every = BI.BURNED_REGISTRY_DIGESTS | BI.BURNED_PUBLIC_KEY_SHA256 | BI.BURNED_GENESIS_WITNESS_DIGESTS
        self.assertNotIn(CANDIDATE, every)
        self.assertEqual(BI.CANONICAL_COUNT, 20)

    def test_nothing_is_authorized(self):
        for line in ("REPLACEMENT M-B3 PREPARATION SEQUENCE = NOT AUTHORIZED", "PHONE INCIDENT CLEANUP = NOT AUTHORIZED",
                     "NEW PREPARE = NOT AUTHORIZED", "NEW SIGN GO = NOT AUTHORIZED", "M-B4/M-B5 = NOT AUTHORIZED",
                     "GENESIS = NOT AUTHORIZED", "RECORD 1 = NOT AUTHORIZED", "FIRST MEMORY = NOT AUTHORIZED",
                     "PROD = NOT AUTHORIZED", "FRESHNESS=UNKNOWN", "M-B3 / REGISTRY_SIGNED = NOT REACHED"):
            self.assertIn(line, self.posture)
        for claim in ("CLEANUP = AUTHORIZED", "NEW SIGN GO = AUTHORIZED", "NEW PREPARE = AUTHORIZED", "FRESHNESS=CURRENT"):
            self.assertNotIn(claim, self.text)

    def test_pointers(self):
        arch = ROOT / "docs/architecture"
        for name in ("slice-15b2b-b1b3e-mb3-registry-ceremony-package.md", "slice-15b2b-b1b3e-mb3-final-package-pins.md",
                     "README.md"):
            self.assertIn("(slice-15b2b-b1b3e-mb3-sign-attempt1-incident.md)", (arch / name).read_text(encoding="utf-8"))

    def test_disposition_block_is_archive_only_and_never_writes_kroot(self):
        block = disposition_block()
        for name, value in REAL_PINS.items():
            self.assertIn(f"{name}={value}\n", block)
        code = [line for line in block.splitlines() if not line.lstrip().startswith("#")]
        destructive = re.compile(r"\brm\b|\bshred\b|\btruncate\b|\bchmod\b|\bchown\b")
        self.assertEqual([line for line in code if destructive.search(line)], [])
        kroot_ref = re.compile(r'"\$K"|"\$P"|\$K/|\$P/')
        for line in code:
            if kroot_ref.search(line) and not line.startswith(("K=", "P=")):
                self.assertRegex(line, r"\bstat\b|\bls -A\b|sha256sum|kroot_meta")
                self.assertNotIn("mv ", line)


@unittest.skipUnless(os.name == "posix" and shutil.which("bash") and shutil.which("sha256sum"), "needs bash and coreutils")
class DispositionProcedureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        h = self.home
        (h / "lilith-mb3/sign").mkdir(parents=True)
        (h / "lilith-mb3/evidence").mkdir()
        (h / "lilith-mb3/inputs").mkdir()
        (h / "lilith-mb3/sign/attempt.json").write_text('{"attemptStartedAt": "2026-10-06T12:11:49Z"}\n')
        (h / "lilith-mb3/evidence/sign-outcome.json").write_text(
            '{"burnRecorded": false, "invoked": false, "outcome": "A_NO_SIGNATURE", "stop": "x"}\n')
        (h / "lilith-mb3/mb3-inputs.json").write_text('{"fixture": "manifest"}\n')
        (h / "lilith-mb3-failure-export.tar").write_bytes(b"fixture failure export")
        (h / "lilith-mb3-prepare.transcript.txt").write_text("fixture transcript\n")
        downloads = h / "storage/downloads"
        downloads.mkdir(parents=True)
        self.dl_files = {"mb3_phone_ceremony.py": b"fixture old script", "lilith-mb3-registry-1f544e6.tar": b"fixture tar",
                         "mb3-kact-publication.json": b"fixture kact", "mb3-kwit-publication.json": b"fixture kwit",
                         "lilith-mb3-prepare-readback.tar": b"fixture readback",
                         "lilith-mb3-failure-export.tar": b"fixture failure export", "unrelated.pdf": b"owner file"}
        for name, data in self.dl_files.items():
            (downloads / name).write_bytes(data)
        (h / "lilith-kroot-dev-synthetic").mkdir(mode=0o700)
        (h / "lilith-kroot-dev-synthetic/k-root.der").write_bytes(b"TEST-ONLY fixture key bytes")
        os.chmod(h / "lilith-kroot-dev-synthetic/k-root.der", 0o600)
        (h / "lilith-kroot-dev-synthetic-public").mkdir(mode=0o700)
        (h / "lilith-kroot-dev-synthetic-public/k-root-anchor.json").write_text('{"fixture": "anchor"}\n')
        (h / "unrelated-termux-file").write_text("keep\n")

        def sha(path):
            return hashlib.sha256(Path(path).read_bytes()).hexdigest()
        self.pins = {"MANIFEST_SHA": sha(h / "lilith-mb3/mb3-inputs.json"),
                     "FAILURE_SHA": sha(h / "lilith-mb3-failure-export.tar"),
                     "SCRIPT_SHA": sha(downloads / "mb3_phone_ceremony.py"),
                     "BUNDLE_SHA": sha(downloads / "lilith-mb3-registry-1f544e6.tar"),
                     "KACT_SHA": sha(downloads / "mb3-kact-publication.json"),
                     "KWIT_SHA": sha(downloads / "mb3-kwit-publication.json"),
                     "READBACK_SHA": sha(downloads / "lilith-mb3-prepare-readback.tar")}
        self.key_stat = os.stat(h / "lilith-kroot-dev-synthetic/k-root.der")

    def tearDown(self):
        self.tmp.cleanup()

    def run_block(self):
        import subprocess
        block = disposition_block()
        for name, value in REAL_PINS.items():          # only the seven pin lines differ from the reviewed block
            block = block.replace(f"{name}={value}\n", f"{name}={self.pins[name]}\n")
        env = {"HOME": str(self.home), "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        return subprocess.run(["bash", "-s"], input=block, capture_output=True, text=True, env=env)

    def assert_kroot_untouched(self):
        key = self.home / "lilith-kroot-dev-synthetic/k-root.der"
        after = os.stat(key)
        self.assertEqual(key.read_bytes(), b"TEST-ONLY fixture key bytes")
        self.assertEqual((after.st_ino, after.st_mtime_ns, after.st_mode),
                         (self.key_stat.st_ino, self.key_stat.st_mtime_ns, self.key_stat.st_mode))
        self.assertEqual(sorted(os.listdir(self.home / "lilith-kroot-dev-synthetic")), ["k-root.der"])
        self.assertTrue((self.home / "lilith-kroot-dev-synthetic-public/k-root-anchor.json").is_file())

    def test_archive_by_rename_and_after_state(self):
        result = self.run_block()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DISPOSITION_BEFORE_STATE_OK", result.stdout)
        self.assertIn("MB3_ATTEMPT1_DISPOSITION_COMPLETE", result.stdout)
        h, a = self.home, self.home / "lilith-mb3-incident-attempt1"
        for gone in ("lilith-mb3", "lilith-mb3-failure-export.tar", "lilith-mb3-registry-public", "lilith-mb3-export.tar",
                     "storage/downloads/mb3_phone_ceremony.py"):
            self.assertFalse((h / gone).exists(), gone)
        for kept in ("lilith-mb3/sign/attempt.json", "lilith-mb3/mb3-inputs.json", "lilith-mb3/evidence/sign-outcome.json",
                     "lilith-mb3-failure-export.tar", "lilith-mb3-prepare.transcript.txt"):
            self.assertTrue((a / kept).is_file(), kept)
        for name, data in self.dl_files.items():
            if name == "unrelated.pdf":
                self.assertEqual((h / "storage/downloads" / name).read_bytes(), data)
            else:
                self.assertEqual((a / "downloads" / name).read_bytes(), data)
        manifest = (h / "lilith-mb3-incident-attempt1.sha256").read_text()
        self.assertIn("./lilith-mb3/sign/attempt.json", manifest)
        self.assertIn(f"ARCHIVE_SHA256 {hashlib.sha256(manifest.encode()).hexdigest()}", result.stdout)
        self.assertEqual((h / "unrelated-termux-file").read_text(), "keep\n")
        self.assert_kroot_untouched()

    def test_refuses_without_moving_anything_when_signer_output_exists(self):
        (self.home / "lilith-mb3/sign/registry-v1.stdout").write_bytes(b"")
        result = self.run_block()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("STOP: signer output or burn present", result.stderr)
        self.assertTrue((self.home / "lilith-mb3").is_dir())
        self.assertFalse((self.home / "lilith-mb3-incident-attempt1").exists())
        self.assert_kroot_untouched()

    def test_refuses_a_non_attempt1_manifest_or_extra_kroot_entry(self):
        (self.home / "lilith-kroot-dev-synthetic/extra").write_text("x")
        result = self.run_block()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("STOP: K-ROOT directory is not exactly k-root.der", result.stderr)
        self.assertTrue((self.home / "lilith-mb3").is_dir())
        os.remove(self.home / "lilith-kroot-dev-synthetic/extra")
        (self.home / "lilith-mb3/mb3-inputs.json").write_text('{"other": "candidate"}\n')
        result = self.run_block()
        self.assertIn("STOP: manifest is not the attempt-1 manifest", result.stderr)
        self.assertFalse((self.home / "lilith-mb3-incident-attempt1").exists())

    def test_rerun_after_completion_refuses(self):
        self.assertEqual(self.run_block().returncode, 0)
        result = self.run_block()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("STOP: an archive already exists", result.stderr)


if __name__ == "__main__":
    unittest.main()
