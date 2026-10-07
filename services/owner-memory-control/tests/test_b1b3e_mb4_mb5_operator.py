"""15B2b-B1b-3e M-B4/M-B5: the reviewed operator tool (TEST-ONLY, no network, no DEV).

Record: docs/architecture/slice-15b2b-b1b3e-mb4-mb5-ceremony-package.md.

Every remote call goes to a fake runner that records argv; git is answered
from the working tree. Nothing contacts GCP, DEV or the S25. Pins the tool
and module hashes, the hash-gated stream, the closed command shapes (read-only
except the two one-attempt installer stages, staging and the bounded
removal), the go-file checks and the one-attempt markers.
"""

from __future__ import annotations

import base64
import contextlib
import dataclasses
import gzip
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
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _p in (TOOLS, Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import mb4_mb5_operator as O  # noqa: E402

HAVE_CRYPTO = all(importlib.util.find_spec(m) is not None for m in ("cryptography", "rfc8785", "fido2"))

CONTROL = "c" * 40
MUTATING = re.compile(r"\b(rm|rmdir|mkdir|mv|cp|chmod|chown|tee|dd|truncate|ln|install-anchors|install-registry|"
                      r"daemon-reload|systemd-creds|keygen|enable|disable|restart)\b|systemctl (start|stop)|remove ")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FakeRunner:
    def __init__(self, *, clean=True, remote=None, scp_rc=0):
        self.calls: list[list[str]] = []
        self.clean, self.remote, self.scp_rc = clean, remote or (lambda cmd: (0, b"")), scp_rc

    def __call__(self, argv):
        argv = list(argv)
        self.calls.append(argv)
        if argv[0] == "git":
            sub = argv[3:]
            if sub[:2] == ["rev-parse", "HEAD"]:
                return subprocess.CompletedProcess(argv, 0, (CONTROL + "\n").encode(), b"")
            if sub[0] == "status":
                return subprocess.CompletedProcess(argv, 0, b"" if self.clean else b" M x\n", b"")
            if sub[0] == "show":
                return subprocess.CompletedProcess(argv, 0, (ROOT / sub[1].split(":", 1)[1]).read_bytes(), b"")
        if "ssh" in argv:
            command = next(a for a in argv if a.startswith("--command="))[len("--command="):]
            rc, out = self.remote(command)
            return subprocess.CompletedProcess(argv, rc, out, b"")
        if "scp" in argv:
            return subprocess.CompletedProcess(argv, self.scp_rc, b"", b"")
        return subprocess.CompletedProcess(argv, 0, b"[]", b"")

    def commands(self):
        return [next(a for a in c if a.startswith("--command="))[len("--command="):] for c in self.calls if "ssh" in c]


def go_text(lines, **values) -> str:
    return "\n".join("> " + line.format(**values) for line in lines) + "\n"


class PinTests(unittest.TestCase):
    def test_tool_pins_equal_the_reviewed_files(self):
        for path, pin in O.TOOL_PINS.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)

    def test_release_module_pins_equal_the_aee323e_sources(self):
        mapping = {"lilith_authority_host/": "services/authority-dev/lilith_authority_host/",
                   "lilith_memory/": "services/core-api/lilith_memory/",
                   "lilith_owner_memory/": "services/owner-memory-control/lilith_owner_memory/"}
        for module, pin in O.RELEASE_MODULES.items():
            prefix = next(p for p in mapping if module.startswith(p))
            self.assertEqual(sha((ROOT / (mapping[prefix] + module[len(prefix):])).read_bytes()), pin, module)
        source = (ROOT / "services/authority-dev/release_file_set.py").read_text(encoding="utf-8")
        for module, pin in O.RELEASE_MODULES.items():
            if not module.startswith("lilith_authority_host/"):
                self.assertIn(pin, source, module)            # equal to the release file-set SHARED_HASHES

    def test_representation_pins_agree_everywhere(self):
        verifier = (TOOLS / "mb4_mb5_trust_install_verifier.py").read_text(encoding="utf-8")
        for field_, value in (("root_anchor_sha256", O.DERIVED["registry-root.json"]),
                              ("witness_anchor_sha256", O.DERIVED["witness-anchor.json"]),
                              ("registry_sha256", O.DERIVED["authority-registry.v1.json"]),
                              ("registry_digest", O.REGISTRY_DIGEST), ("kroot_public_key_sha256", O.E21),
                              ("kwit_public_key_sha256", O.KWIT)):
            self.assertIn(f'{field_}="{value}"', verifier)
        text = (TOOLS / "mb4_mb5_installable_inputs.py").read_text(encoding="utf-8")
        for pin in O.DERIVED.values():
            self.assertIn(pin, text)


class StreamAndShapeTests(unittest.TestCase):
    def setUp(self):
        self.runner = FakeRunner()
        self.op = O.Operator(gcloud=("gcloud",), run=self.runner)

    def test_hash_gated_stream_carries_the_exact_tool(self):
        command = self.op.streamed(ROOT, O.INSTALLER, O.SYSTEM_PYTHON, f"status --expect P1B-2 {O.RELEASE_SHA}")
        blob = re.match(r"B=([A-Za-z0-9+/=]+); ", command).group(1)
        self.assertEqual(gzip.decompress(base64.b64decode(blob)), (ROOT / O.INSTALLER).read_bytes())
        self.assertIn(f"| sha256sum | cut -c1-64 | grep -qx '{O.TOOL_PINS[O.INSTALLER]}' || exit 96;", command)
        self.assertTrue(command.endswith(f"| sudo -n /usr/bin/python3 -I -B - status --expect P1B-2 {O.RELEASE_SHA}"))
        self.assertLess(command.index("exit 96"), command.index("sudo -n"))   # the gate precedes execution

    def test_unpinned_tool_bytes_stop(self):
        runner = FakeRunner()
        original = runner.__call__

        def tampered(argv):
            result = original(argv)
            if argv[0] == "git" and argv[3] == "show":
                return subprocess.CompletedProcess(argv, 0, result.stdout + b"\n# changed\n", b"")
            return result
        op = O.Operator(gcloud=("gcloud",), run=tampered)
        with self.assertRaises(O.Stop) as caught:
            op.streamed(ROOT, O.VERIFIER, O.RELEASE_PYTHON, "observe")
        self.assertTrue(caught.exception.code.startswith("TOOL_PIN_MISMATCH"))

    def test_ssh_is_guarded_and_fixed(self):
        self.op.ssh("true")
        argv = self.runner.calls[-1]
        self.assertEqual(argv[:4], ["gcloud", "compute", "ssh", "lilith-dev-01"])
        self.assertIn("--zone=asia-southeast1-b", argv)
        self.assertIn("--project=lilith-agent-260823-27389", argv)
        self.assertIn("--tunnel-through-iap", argv)
        self.assertTrue(self.runner.commands()[-1].startswith('test "$(hostname)" = lilith-dev-01 || exit 97; '))

    def test_pins_form_requires_clean_control(self):
        self.assertEqual(self.op.pins(ROOT)["result"], "MB4_MB5_TOOL_PINS_EXACT")
        dirty = O.Operator(gcloud=("gcloud",), run=FakeRunner(clean=False))
        with self.assertRaises(O.Stop) as caught:
            dirty.pins(ROOT)
        self.assertEqual(caught.exception.code, "CONTROL_CHECKOUT_NOT_CLEAN")

    def test_cloud_capture_is_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.op.cloud(Path(directory) / "cloud", "2026-10-07T00:00:00Z")
            self.assertEqual(len(result["captures"]), 13)
        verbs = {tuple(c[1:3]) for c in self.runner.calls}
        for call in self.runner.calls:
            self.assertTrue(any(word in call for word in ("describe", "list", "get-iam-policy", "read")), call)
            self.assertFalse(any(word in call for word in ("create", "delete", "update", "set-iam-policy", "add",
                                                           "remove", "ssh", "scp")), call)
        self.assertIn(("logging", "read"), verbs)
        with self.assertRaises(O.Stop):
            self.op.cloud(Path(tempfile.gettempdir()) / "never", "yesterday")

    def test_host_reproof_commands_are_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            for phase in ("W0", "W3", "W5"):
                self.op.host(ROOT, Path(directory) / phase, phase)
        commands = self.runner.commands()
        self.assertEqual(len(commands), 21)
        for command in commands:
            visible = re.sub(r"B=[A-Za-z0-9+/=]+; ", "", command)
            self.assertIsNone(MUTATING.search(visible), visible[:160])
            self.assertNotIn("witness.cred |", visible)
        joined = "\n".join(commands)
        for expected in ("status --expect P1B-2 ", "status --expect P1B-4 ", "status --expect P1B-5 ",
                         "expect W0_PRE_INSTALL", "expect W3_ANCHORS_INSTALLED_REGISTRY_ABSENT",
                         "expect W5_INSTALLED_CONTENT_VERIFIED", " - preservation", " - observe",
                         f"sudo -n {O.RELEASE_PYTHON} -I -B -c"):
            self.assertIn(expected, joined)
        with self.assertRaises(O.Stop):
            self.op.host(ROOT, Path(tempfile.gettempdir()) / "x-never", "W4")

    def test_readiness_probe_judgement(self):
        modules = {name.replace("/", ".").removesuffix(".py").removesuffix(".__init__"): [name, pin]
                   for name, pin in O.RELEASE_MODULES.items()}
        good = {"interpreter": O.RELEASE_PYTHON, "release": "/opt/lilith-authority-dev/current", "modules": modules,
                "rfc8785": "0.1.4", "cryptography": "50.0.1"}
        raw = lambda probe, first=f"releases/{O.RELEASE_SHA}": (  # noqa: E731
            f"{first}\nRELEASE_PYTHON=executable\n{json.dumps(probe)}\n").encode()
        self.assertTrue(O.Operator.readiness_ok(raw(good)))
        self.assertFalse(O.Operator.readiness_ok(raw(good, first="releases/" + "0" * 40)))
        extra = dict(good, modules=dict(modules, x=["lilith_owner_memory/other.py", "0" * 64]))
        self.assertFalse(O.Operator.readiness_ok(raw(extra)))
        changed = dict(good, modules=dict(modules, **{"lilith_owner_memory.authority_verifier":
                                                      ["lilith_owner_memory/authority_verifier.py", "1" * 64]}))
        self.assertFalse(O.Operator.readiness_ok(raw(changed)))
        self.assertFalse(O.Operator.readiness_ok(b"releases/x\n"))
        self.assertIn("open(f,'rb')", O.READINESS_PROBE)
        self.assertNotRegex(O.READINESS_PROBE, r"\bwrite|unlink|remove|subprocess|os\.system")


class StagingTests(unittest.TestCase):
    def workdir(self, directory: str) -> Path:
        files = Path(directory) / "derived" / "files"
        files.mkdir(parents=True)
        for name in O.DERIVED:
            (files / name).write_bytes(b"x")
        return Path(directory)

    def test_stage_requires_pinned_local_files(self):
        with tempfile.TemporaryDirectory() as directory:
            op = O.Operator(gcloud=("gcloud",), run=FakeRunner())
            with self.assertRaises(O.Stop) as caught:
                op.stage(self.workdir(directory))
            self.assertTrue(caught.exception.code.startswith("LOCAL_STAGE_REHASH"))

    def test_stage_check_and_cleanup_commands(self):
        runner = FakeRunner(remote=lambda cmd: (0, b"STAGE_CREATED\n" if "mkdir" in cmd else
                                                b"STAGE_DIR_ABSENT\n" if "rmdir" in cmd else b"OK\n"))
        op = O.Operator(gcloud=("gcloud",), run=runner)
        result = op.staged_check()
        self.assertEqual(result["result"], "MB4_MB5_STAGED_FILES_PINNED_ON_HOST")
        check = runner.commands()[-1]
        self.assertIn(f"cd {O.STAGE_DIR} && ", check)
        self.assertIn("LC_ALL=C sort", check)
        self.assertIn("'SHA256SUMS authority-registry.v1.json registry-root.json witness-anchor.json '", check)
        self.assertIn("sha256sum -c --strict SHA256SUMS", check)
        op.cleanup(Path("."))
        cleanup = runner.commands()[-1]
        self.assertIn("rm -f " + " ".join(f"{O.STAGE_DIR}/{n}" for n in O.STAGED), cleanup)
        self.assertIn(f"rmdir {O.STAGE_DIR}", cleanup)
        self.assertNotIn("rm -r", cleanup)
        self.assertNotIn("sudo", cleanup)
        self.assertTrue(O.STAGE_DIR.startswith(O.OPERATOR_HOME + "/"))

    def test_derive_writes_new_files_and_never_changes_the_export(self):
        class FakeDerivation:
            ACCEPTED_SOURCES = object()

            def __init__(self):
                self.calls = 0

            def read_export(self, path, pins):
                assert pins is self.ACCEPTED_SOURCES
                return {"x": Path(path).read_bytes()}

            def derive_from_members(self, members, pins):
                assert pins is self.ACCEPTED_SOURCES
                self.calls += 1
                return type("D", (), {"files": {name: name.encode() for name in O.DERIVED}})()

            def check_pins(self, derivation, expected):
                assert expected is O.DERIVED

            def _write_outputs(self, out, derivation):
                out.mkdir(mode=0o700)
                for name, data in derivation.files.items():
                    (out / name).write_bytes(data)
        with tempfile.TemporaryDirectory() as directory:
            export = Path(directory) / "export.tar"
            export.write_bytes(b"export bytes")
            saved = (O.EXPORT_SHA256, dict(O.DERIVED))
            O.EXPORT_SHA256 = sha(b"export bytes")
            O.DERIVED.clear()
            O.DERIVED.update({name: sha(name.encode()) for name in saved[1]})
            try:
                derivation = FakeDerivation()
                result = O.Operator(run=FakeRunner()).derive(ROOT, export, Path(directory), derivation)
                self.assertEqual(derivation.calls, 2)                # derived twice, compared
                self.assertTrue(result["exportUnchanged"])
                sums = (Path(directory) / "derived/files/SHA256SUMS").read_text(encoding="ascii")
                self.assertEqual(sums.splitlines(), [f"{O.DERIVED[n]}  {n}" for n in O.DERIVED])
                self.assertEqual(export.read_bytes(), b"export bytes")
                with self.assertRaises(O.Stop):
                    O.Operator(run=FakeRunner()).derive(ROOT, export, Path(directory), derivation)   # never overwrites
            finally:
                O.EXPORT_SHA256 = saved[0]
                O.DERIVED.clear()
                O.DERIVED.update(saved[1])


class OneAttemptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.markers_seen = []

        def remote(command):
            if "install-anchors" in command or "install-registry" in command:
                self.markers_seen.append(sorted(os.listdir(self.work / O.ATTEMPT_DIR)))
            return 0, b"OK\n"
        self.runner = FakeRunner(remote=remote)
        self.op = O.Operator(gcloud=("gcloud",), run=self.runner)

    def go(self, name, lines, **values):
        path = self.work / name
        path.write_text(go_text(lines, **values), encoding="utf-8")
        return path

    def test_mb4_requires_the_exact_go_and_runs_once(self):
        bad = self.go("bad.txt", O.MB4_GO_LINES[:-2], control=CONTROL)          # missing the acknowledgement
        with self.assertRaises(O.Stop) as caught:
            self.op.mb4(ROOT, self.work, bad)
        self.assertEqual(caught.exception.code, "GO_LINE_MISSING")
        wrong = self.go("wrong.txt", O.MB4_GO_LINES, control="d" * 40)          # another control commit
        with self.assertRaises(O.Stop):
            self.op.mb4(ROOT, self.work, wrong)
        good = self.go("mb4.txt", O.MB4_GO_LINES, control=CONTROL)
        result = self.op.mb4(ROOT, self.work, good)
        self.assertEqual(result["result"], "MB4_INVOKED_ONCE")
        self.assertEqual(self.markers_seen, [["mb4.json"]])                     # the marker precedes the invocation
        installs = [c for c in self.runner.commands() if "install-anchors" in c]
        self.assertEqual(len(installs), 1)
        self.assertTrue(installs[0].endswith(f"- install-anchors {O.RELEASE_SHA} {O.STAGE_DIR}/registry-root.json "
                                             f"{O.STAGE_DIR}/witness-anchor.json"))
        with self.assertRaises(O.Stop) as caught:
            self.op.mb4(ROOT, self.work, good)
        self.assertEqual(caught.exception.code, "ATTEMPT_ALREADY_CONSUMED:mb4")
        self.assertEqual(len([c for c in self.runner.commands() if "install-anchors" in c]), 1)
        marker = json.loads((self.work / O.ATTEMPT_DIR / "mb4.json").read_text(encoding="ascii"))
        self.assertEqual(marker["invocationsPermitted"], 1)
        self.assertEqual(marker["goSha256"], sha(good.read_bytes()))

    def test_failed_mb4_still_consumes_the_go(self):
        op = O.Operator(gcloud=("gcloud",), run=FakeRunner(remote=lambda c: (2, b"") if "install-anchors" in c
                                                           else (0, b"OK\n")))
        good = self.go("mb4.txt", O.MB4_GO_LINES, control=CONTROL)
        result = op.mb4(ROOT, self.work, good)
        self.assertEqual(result["result"], "MB4_STOP")
        with self.assertRaises(O.Stop):
            op.mb4(ROOT, self.work, good)

    def test_mb5_needs_mb4_in_this_sequence_and_its_own_go(self):
        mb5 = self.go("mb5.txt", O.MB5_GO_LINES, control=CONTROL)
        with self.assertRaises(O.Stop) as caught:
            self.op.mb5(ROOT, self.work, mb5)
        self.assertEqual(caught.exception.code, "MB4_NOT_IN_THIS_SEQUENCE")
        self.op.mb4(ROOT, self.work, self.go("mb4.txt", O.MB4_GO_LINES, control=CONTROL))
        with self.assertRaises(O.Stop):
            self.op.mb5(ROOT, self.work, self.go("mb4-as-mb5.txt", O.MB4_GO_LINES, control=CONTROL))
        result = self.op.mb5(ROOT, self.work, mb5)
        self.assertEqual(result["result"], "MB5_INVOKED_ONCE")
        installs = [c for c in self.runner.commands() if "install-registry" in c]
        self.assertEqual(len(installs), 1)
        self.assertTrue(installs[0].endswith(f"- install-registry {O.RELEASE_SHA} {O.STAGE_DIR}/authority-registry.v1.json"))
        with self.assertRaises(O.Stop):
            self.op.mb5(ROOT, self.work, mb5)

    def test_removal_needs_its_own_authorization(self):
        digest = "a" * 64
        with self.assertRaises(O.Stop):
            self.op.removal(ROOT, self.work, digest, self.go("r.txt", O.MB4_GO_LINES, control=CONTROL))
        auth = self.go("removal.txt", O.REMOVAL_LINES, plan=digest)
        with self.assertRaises(O.Stop):
            self.op.removal(ROOT, self.work, "b" * 64, auth)                     # a different plan
        self.assertEqual(self.op.removal(ROOT, self.work, digest, auth)["result"], "REMOVAL_INVOKED_ONCE")
        self.assertTrue(self.runner.commands()[-1].endswith(f"- remove {digest}"))
        with self.assertRaises(O.Stop):
            self.op.removal(ROOT, self.work, digest, auth)

    def test_go_templates_bind_the_pins(self):
        mb4, mb5 = " ".join(O.MB4_GO_LINES), " ".join(O.MB5_GO_LINES)
        for pin in (O.DERIVED["registry-root.json"], O.DERIVED["witness-anchor.json"], O.E21, O.KWIT,
                    O.TOOL_PINS[O.INSTALLER], O.RELEASE_SHA):
            self.assertIn(pin, mb4)
        self.assertIn("M-B4 closes the K-WIT burn/regenerate option.", mb4)
        self.assertIn("does not authorize M-B5", mb4)
        for pin in (O.DERIVED["authority-registry.v1.json"], O.REGISTRY_DIGEST, O.TOOL_PINS[O.INSTALLER]):
            self.assertIn(pin, mb5)
        self.assertIn("W3_ANCHORS_INSTALLED_REGISTRY_ABSENT", mb5)
        self.assertIn("does not accept TRUST_INSTALLED", mb5)

    def test_cli_and_closed_forms(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(O.main([], self.op), 2)
            self.assertEqual(O.main(["install-anchors"], self.op), 2)
            self.assertEqual(O.main(["host", str(ROOT), str(self.work / "h"), "W9"], self.op), 1)
        code = (TOOLS / "mb4_mb5_operator.py").read_text(encoding="utf-8").split('"""', 2)[2]
        for forbidden in ("shell=True", "os.system", "systemd-creds", "daemon-reload", "lilith-authority-keygen-dev",
                          "k-root", "passphrase", "getpass", "lilith-authority-ledger-dev", "lilith-authority-hold-dev",
                          "lilith-recovery-witness-owner-dev", "lilith-authority-recovery-dev", "provision",
                          "bootstrap", "install-owner-inputs", "witness-state", "systemctl start", "systemctl stop"):
            self.assertNotIn(forbidden, code, forbidden)
        self.assertEqual(code.count("install-anchors {RELEASE_SHA}"), 1)
        self.assertEqual(code.count("install-registry {RELEASE_SHA}"), 1)

    def test_gcloud_prefix_override(self):
        old = os.environ.get("LILITH_MB4_MB5_GCLOUD")
        try:
            os.environ["LILITH_MB4_MB5_GCLOUD"] = json.dumps(["py.exe", "gcloud.py"])
            self.assertEqual(O.Operator().gcloud, ("py.exe", "gcloud.py"))
            os.environ["LILITH_MB4_MB5_GCLOUD"] = json.dumps([])
            with self.assertRaises(O.Stop):
                O.Operator()
        finally:
            if old is None:
                os.environ.pop("LILITH_MB4_MB5_GCLOUD", None)
            else:
                os.environ["LILITH_MB4_MB5_GCLOUD"] = old


@unittest.skipUnless(HAVE_CRYPTO, "cryptography, rfc8785 and fido2 are required")
class RealDerivationLoadTests(unittest.TestCase):
    """The defect that escaped the fake-derivation test: the REAL derivation module, loaded by the operator itself.

    The first preparation sequence stopped at E-21 because `derive` executed
    `mb4_mb5_installable_inputs.py` without registering it in `sys.modules`
    (dataclass AttributeError). These tests run the real loader and the real
    derivation on a synthetic TEST world (the M-B3 package test keys, a
    synthetic export tar). The only substitution is the source / export /
    derived pins, set on the freshly loaded real module. The accepted export
    is never read here."""

    @classmethod
    def setUpClass(cls):
        import test_b1b3e_mb4_mb5_installable_inputs as T
        cls.T = T
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        (base / "world").mkdir()
        cls.src = T.TestSources(base / "world")
        cls.export = cls._export(base / "synthetic-export.tar", cls.src.members)
        cls.export_sha = sha(cls.export.read_bytes())
        cls.source_pins = dataclasses.replace(cls.src.pins, export_sha256=cls.export_sha)
        independent = T.D.derive_from_members(cls.src.members, cls.src.pins)   # the test's own import of the module
        cls.expected_files = dict(independent.files)
        cls.expected = {name: sha(independent.files[name]) for name in O.DERIVED}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.addCleanup(sys.modules.pop, O.DERIVATION_MODULE, None)

    @classmethod
    def _export(cls, path: Path, members: dict) -> Path:
        """A synthetic export tar holding the five members the derivation reads."""
        with tarfile.open(path, "w") as archive:
            for key, name in cls.T.D.EXPORT_MEMBERS.items():
                data = members[key]
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = len(data), 0o644, 0
                archive.addfile(info, io.BytesIO(data))
        return path

    @contextlib.contextmanager
    def synthetic(self, loaded: list, source_pins=None):
        """The REAL loader runs; then the TEST source pins replace the accepted ones on the fresh module."""
        real = O.load_derivation
        pins = source_pins or self.source_pins

        def load(repo):
            module = real(repo)
            loaded.append(module)
            values = {f.name: getattr(pins, f.name) for f in dataclasses.fields(pins)}
            module.ACCEPTED_SOURCES = module.SourcePinsV1(**values)
            return module

        with mock.patch.object(O, "load_derivation", load), \
                mock.patch.object(O, "EXPORT_SHA256", pins.export_sha256), \
                mock.patch.dict(O.DERIVED, self.expected, clear=True):
            yield

    def test_old_unregistered_pattern_is_the_escaped_defect(self):
        name = "mb4_mb5_installable_inputs_unregistered_probe"
        spec = importlib.util.spec_from_file_location(name, TOOLS / "mb4_mb5_installable_inputs.py")
        module = importlib.util.module_from_spec(spec)
        with self.assertRaises(AttributeError):
            spec.loader.exec_module(module)                      # the E-21 failure, reproduced
        self.assertNotIn(name, sys.modules)

    def test_real_module_is_registered_before_exec_and_its_dataclasses_initialize(self):
        seen = []
        real_spec = importlib.util.spec_from_file_location

        def spy(name, location, *args, **kwargs):                # observes; the real loader still executes
            spec = real_spec(name, location, *args, **kwargs)
            if name == O.DERIVATION_MODULE:
                real_exec = spec.loader.exec_module

                def exec_module(module):
                    seen.append(("before", sys.modules.get(name) is module))
                    real_exec(module)
                    seen.append(("after", sys.modules.get(name) is module))
                spec.loader.exec_module = exec_module
            return spec

        with mock.patch.object(importlib.util, "spec_from_file_location", spy):
            module = O.load_derivation(ROOT)
        self.assertEqual(seen, [("before", True), ("after", True)])
        self.assertIs(sys.modules[O.DERIVATION_MODULE], module)
        self.assertEqual(Path(module.__file__).resolve(), (TOOLS / "mb4_mb5_installable_inputs.py").resolve())
        self.assertIsNot(module, self.T.D)
        for cls in (module.SourcePinsV1, module.DerivationV1):
            self.assertTrue(dataclasses.is_dataclass(cls))
            self.assertEqual(cls.__module__, O.DERIVATION_MODULE)
        self.assertIsInstance(module.ACCEPTED_SOURCES, module.SourcePinsV1)
        self.assertEqual(module.ACCEPTED_SOURCES.export_sha256, O.EXPORT_SHA256)
        self.assertEqual(module.DERIVED_SHA256, O.DERIVED)       # the accepted pins, unchanged

    def test_real_derive_end_to_end_through_the_cli(self):
        loaded = []
        with tempfile.TemporaryDirectory() as directory, self.synthetic(loaded):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(O.main(["derive", str(ROOT), str(self.export), directory]), 0)
            result = json.loads(out.getvalue())
            self.assertEqual(result["result"], "MB4_MB5_DERIVED_PINNED")
            self.assertEqual(result["derived"], self.expected)
            self.assertTrue(result["exportUnchanged"])
            self.assertEqual([m.__name__ for m in loaded], [O.DERIVATION_MODULE])
            files = Path(directory) / "derived/files"
            self.assertEqual(sorted(os.listdir(files)), sorted(list(self.expected) + ["SHA256SUMS"]))
            for name, data in self.expected_files.items():
                self.assertEqual((files / name).read_bytes(), data)
            self.assertEqual((files / "SHA256SUMS").read_bytes().decode("ascii").splitlines(),
                             [f"{self.expected[n]}  {n}" for n in self.expected])
        # the representation rules held: registry = transport minus exactly one LF; no output ends in a newline
        self.assertEqual(self.expected_files["authority-registry.v1.json"] + b"\n", self.src.transport)
        self.assertFalse(any(data.endswith(b"\n") for data in self.expected_files.values()))
        self.assertEqual(sha(self.export.read_bytes()), self.export_sha)

    def test_real_derivation_logic_refuses_and_writes_nothing(self):
        members = dict(self.src.members, kwit=self.src.members["kwit"] + b" ")      # not the pinned K-WIT bytes
        with tempfile.TemporaryDirectory() as directory:
            export = self._export(Path(directory) / "tampered.tar", members)
            pins = dataclasses.replace(self.source_pins, export_sha256=sha(export.read_bytes()))
            work = Path(directory) / "work"
            work.mkdir()
            loaded = []
            with self.synthetic(loaded, pins), self.assertRaises(Exception) as caught:
                O.Operator().derive(ROOT, export, work)
            self.assertEqual(type(caught.exception).__name__, "DerivationRefusal")      # the real module's refusal
            self.assertEqual(type(caught.exception).__module__, O.DERIVATION_MODULE)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(os.listdir(work), [])

    def test_repeated_invocation_loads_fresh_modules_and_replaces_stale_state(self):
        stale = types.ModuleType(O.DERIVATION_MODULE)
        stale.ACCEPTED_SOURCES = "stale"
        sys.modules[O.DERIVATION_MODULE] = stale
        first = O.load_derivation(ROOT)
        second = O.load_derivation(ROOT)
        self.assertIsNot(first, stale)
        self.assertIsNot(second, first)
        self.assertIsNot(second.SourcePinsV1, first.SourcePinsV1)
        self.assertIs(sys.modules[O.DERIVATION_MODULE], second)
        loaded = []
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b, self.synthetic(loaded):
            one = O.Operator().derive(ROOT, self.export, Path(a))
            two = O.Operator().derive(ROOT, self.export, Path(b))
            self.assertEqual(one["derived"], self.expected)
            self.assertEqual(two["derived"], self.expected)
            for name, data in self.expected_files.items():
                self.assertEqual((Path(a) / "derived/files" / name).read_bytes(),
                                 (Path(b) / "derived/files" / name).read_bytes())
        self.assertEqual(len(loaded), 2)
        self.assertIsNot(loaded[0], loaded[1])

    def test_load_failure_is_fail_closed_with_no_output(self):
        with tempfile.TemporaryDirectory() as directory:
            loaded = []
            with self.synthetic(loaded), mock.patch.dict(sys.modules, {"mb3_registry_ceremony": None}):
                sys.modules.pop(O.DERIVATION_MODULE, None)
                with self.assertRaises(O.Stop) as caught:     # a real exec failure: the module's own import fails
                    O.Operator().derive(ROOT, self.export, Path(directory))
                self.assertEqual(caught.exception.code, "DERIVATION_LOAD_FAILED")
                self.assertIsInstance(caught.exception.__cause__, ImportError)
                self.assertNotIn(O.DERIVATION_MODULE, sys.modules)   # no half-executed module left behind
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    self.assertEqual(O.main(["derive", str(ROOT), str(self.export), directory]), 1)
                self.assertEqual(out.getvalue(), "")
                self.assertIn("STOP DERIVATION_LOAD_FAILED", err.getvalue())
            self.assertEqual(loaded, [])
            self.assertEqual(os.listdir(directory), [])
        self.assertEqual(sha(self.export.read_bytes()), self.export_sha)

    def test_unpinned_derivation_bytes_are_never_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / O.DERIVATION
            target.parent.mkdir(parents=True)
            target.write_bytes(b"raise SystemExit('must never run')\n")
            sys.modules.pop(O.DERIVATION_MODULE, None)
            with self.assertRaises(O.Stop) as caught:
                O.load_derivation(Path(directory))
            self.assertEqual(caught.exception.code, "TOOL_PIN_MISMATCH:" + O.DERIVATION)
            self.assertNotIn(O.DERIVATION_MODULE, sys.modules)


if __name__ == "__main__":
    unittest.main()
