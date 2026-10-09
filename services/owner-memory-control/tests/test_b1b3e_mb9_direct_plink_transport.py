"""15B2b-B1b-3e Package B remediation R-B5: the read-only verifier bundles over a directly launched plink (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-mb9-seq2-stdin-stop-direct-plink.md and the Package B record §8.2.

Package B sequence 2 stopped because `gcloud compute ssh` on the owner's Windows workstation hands its SSH client
the two bytes "y\\n" instead of the caller's stdin (Cloud SDK 581.0.0, ssh/putty_force_connect), so every R-B1
verifier bundle was refused by the remote digest gate (exit 96). R-B4 proved that the same client, launched
directly over the same IAP tunnel, carries stdin exactly. These tests pin that route: the client, key, OS Login
user, host alias, host key and tunnel; the bundle bytes alone on the child's stdin; fail-closed handling of every
transport failure; no fallback; and every mutation, the stop and every other form unchanged from R-B1.

Nothing here contacts DEV or runs a real plink. The integration cases launch a stand-in client (this interpreter
running a small script) as a real child process; the end-to-end case additionally needs a POSIX bash.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import test_b1b3e_mb9_package as P  # noqa: E402  (shared fixtures; binds the synthetic plink and key)

O, M6, C = P.O, P.M6, P.C
ROOT = P.ROOT
RECORD = P.ARCH / "slice-15b2b-b1b3e-mb9-seq2-stdin-stop-direct-plink.md"
BUNDLES = {"w9": O.VERIFIER_BUNDLE, "w8": O.W8_BUNDLE, "mb6": O.MB6_VERIFIER_BUNDLE}
SHELL_TOOLS = all(shutil.which(t) for t in ("bash", "base64", "sha256sum", "cut", "grep"))

# R-B4 (owner-accepted 2026-10-09): the bindings and the tunnel command proven byte-exact for raw stdin.
EXPECTED = {
    "PLINK_SHA256": "7308e9d356f14aa1f08cab1af363f71a077bf35dcb49e50b363418044758cd1e",
    "PPK_PUBLIC_KEY_SHA256": "e830598a20880490d8b1644d48a448e600503367d3ab130d051e67d2a6e1a12e",
}
OSLOGIN_USER = "ravindupahasara2_gmail_com"
HOST_ALIAS = "compute.7687007163730582258"
HOST_KEY = "SHA256:XfNINpbMvAzlla6rma0q+whKd6UT12C4Fhc0mpOrEXU"
SDK = r"C:\Users\edufo\AppData\Local\Google\Cloud SDK\google-cloud-sdk"
R_B4_GCLOUD = (SDK + r"\platform\bundledpython\python.exe", SDK + r"\lib\gcloud.py")
R_B4_PROXYCMD = (
    r'"C:\\Users\\edufo\\AppData\\Local\\Google\\Cloud SDK\\google-cloud-sdk\\platform\\bundledpython'
    r'\\python.exe" "C:\\Users\\edufo\\AppData\\Local\\Google\\Cloud SDK\\google-cloud-sdk\\lib\\'
    r'gcloud.py" compute start-iap-tunnel "lilith-dev-01" %port --listen-on-stdin "--project=lilith-agent-260823-27389" '
    r'"--zone=asia-southeast1-b" "--verbosity=warning"')
GUARD = f'test "$(hostname)" = {M6.DEV} || exit 97; '
# SHA-256 over {name: SHA-256(source)} of every Operator method and every *_LINES / *_COMMAND constant of the R-B1
# operator (1a91bb2b…) except `remote_bundle` and `ssh_stdin`, the only two R-B5 replaces.
RB1_UNCHANGED_SEGMENTS = "dff3ddcf753abd1a6ae4d457928b143b0c1188043120064340105da3dac21141"
RB1_OPERATOR = "1a91bb2b0258cbec0028346ceede9c6e43135d556756fffe4f8696da66abbc29"

FAKE_PLINK = r'''
import json, os, subprocess, sys
out = os.environ["FAKE_PLINK_OUT"]
data = sys.stdin.buffer.read()
with open(os.path.join(out, "argv.json"), "w", encoding="utf-8") as f:
    json.dump(sys.argv[1:], f)
with open(os.path.join(out, "stdin.bin"), "wb") as f:
    f.write(data)
mode = os.environ.get("FAKE_PLINK_MODE", "ok")
if mode == "exec":
    command = sys.argv[-1].replace(os.environ["FAKE_PLINK_SUDO"], os.environ["FAKE_PLINK_PYTHON"])
    command = command.replace('"$(hostname)"', os.environ["FAKE_PLINK_HOSTNAME"], 1)   # the stand-in host's name
    done = subprocess.run(["bash", "-c", command], input=data, capture_output=True)
    sys.stdout.buffer.write(done.stdout); sys.stderr.buffer.write(done.stderr); sys.exit(done.returncode)
if mode == "stderr":
    sys.stderr.write("Access granted. Press Return to begin session.\n")
if mode == "hostkey":
    sys.stderr.write("FATAL ERROR: Host key did not match any configured key\n"); sys.exit(1)
sys.stdout.write(json.dumps({"phase": "OBSERVED", "bytes": len(data)}))
sys.exit({"ok": 0, "stderr": 0, "exit96": 96}[mode])
'''


def proven(argv) -> dict:
    """The argv parts that must be exactly the R-B4 route (synthetic client path and key path aside)."""
    return {"flags": argv[1:5], "hostkey": argv[argv.index("-hostkey") + 1], "key": argv[argv.index("-i") + 1],
            "target": argv[-2], "guard": argv[-1].startswith(GUARD)}


def segments(source: str) -> dict:
    tree, out = ast.parse(source), {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Operator":
            for f in node.body:
                if isinstance(f, ast.FunctionDef):
                    out[f.name] = P.sha(ast.get_source_segment(source, f).encode())
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and \
                node.targets[0].id.endswith(("_LINES", "_COMMAND")):
            out[node.targets[0].id] = P.sha(ast.get_source_segment(source, node).encode())
    return out


class _Work(P.Redacted, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name) / "work"
        self.work.mkdir()
        C.write_emitted(P.synthetic_derivation(), self.work / "genesis")

    def text(self, lines, **values) -> Path:
        path = Path(self.tmp.name) / f"text-{len(os.listdir(self.tmp.name))}.txt"
        path.write_text("\n".join("> " + line.format(**values) for line in lines) + "\n", encoding="utf-8")
        return path

    def values(self):
        c = O.Operator.candidate(self.work)
        return dict(control=P.CONTROL, operator=P.sha(Path(O.__file__).read_bytes()), candidate=c["candidate"],
                    pin=c["pin"], register=c["register"], record=c["record"], updated_at=P.UPDATED_AT,
                    invocation=P.INVOCATION, mainpid=P.MAINPID, post9a="")


class BindingTests(P.Redacted, unittest.TestCase):
    def test_the_repository_pins_are_the_r_b4_bindings(self):
        for name, value in EXPECTED.items():
            self.assertEqual(P.REAL_DIRECT_PLINK[name], value, name)
            self.assertIn(f'{name} = "{value}"', Path(O.__file__).read_text(encoding="utf-8"))
        self.assertEqual(P.REAL_DIRECT_PLINK["PPK_PATH"], Path.home() / ".ssh" / "google_compute_engine.ppk")
        self.assertEqual((O.OSLOGIN_USER, O.HOST_ALIAS, O.HOST_KEY), (OSLOGIN_USER, HOST_ALIAS, HOST_KEY))
        self.assertEqual(O.PLINK_FLAGS, ("-ssh", "-T", "-batch", "-noagent"))
        self.assertEqual(O.PLINK_ENV, "LILITH_MB9_PLINK")
        self.assertNotEqual(O.PLINK_ENV, "LILITH_MB6_GCLOUD")                   # never overloads the gcloud input
        self.assertEqual(O.TRANSPORT_STDERR_EXIT, 95)
        self.assertEqual(M6.DEV, "lilith-dev-01")

    def test_the_tunnel_command_is_the_one_r_b4_proved(self):
        self.assertEqual(O.iap_proxy_command(R_B4_GCLOUD), R_B4_PROXYCMD)
        for part in ("compute start-iap-tunnel", "%port --listen-on-stdin", "--project=lilith-agent-260823-27389",
                     "--zone=asia-southeast1-b", "--verbosity=warning"):
            self.assertIn(part, O.iap_proxy_command(("gcloud",)))
        with self.assertRaises(O.Stop) as caught:
            O.iap_proxy_command(("gcloud\n",))
        self.assertEqual(caught.exception.code, "PROXYCMD_BAD_CHARACTER")

    def test_the_ppk_binding_reads_only_the_public_blob(self):
        path = Path(tempfile.mkdtemp()) / "k.ppk"
        self.addCleanup(shutil.rmtree, path.parent, True)
        path.write_bytes(P.synthetic_ppk().replace(b"\n", b"\r\n"))
        self.assertEqual(O.ppk_public_key_sha256(path), P.sha(P.SYNTHETIC_PUBLIC_BLOB))
        for bad, code in ((b"no key here\n", "PPK_MALFORMED"), (b"Public-Lines: 1\n!!!!\n", "PPK_MALFORMED"),
                          (b"\xff\xfe", "PPK_UNAVAILABLE")):
            path.write_bytes(bad)
            with self.assertRaises(O.Stop) as caught:
                O.ppk_public_key_sha256(path)
            self.assertEqual(caught.exception.code, code)
        with self.assertRaises(O.Stop) as caught:
            O.ppk_public_key_sha256(path.parent / "absent.ppk")
        self.assertEqual(caught.exception.code, "PPK_UNAVAILABLE")


class RouteTests(_Work):
    def test_m_b6_w8_and_w9_reads_use_direct_plink_with_the_exact_bundle(self):
        for name, paths in BUNDLES.items():
            with self.subTest(name):
                run = P.FakeRun()
                op = O.Operator(gcloud=R_B4_GCLOUD, run=run)
                op.remote_bundle(ROOT, paths, "observe x")
                (argv,), (data,) = run.calls[-1:], run.inputs[-1:]
                command, payload = op.bundled(ROOT, paths, "observe x")
                self.assertEqual(data, payload)                                  # the bundle and nothing else
                self.assertFalse(data.startswith(b"y"))
                self.assertNotIn(b"y\n", data[:2])
                self.assertEqual(argv[0], os.environ[O.PLINK_ENV])
                self.assertEqual(proven(argv), {"flags": ["-ssh", "-T", "-batch", "-noagent"], "hostkey": HOST_KEY,
                                                "key": str(O.PPK_PATH), "target": f"{OSLOGIN_USER}@{HOST_ALIAS}",
                                                "guard": True})
                self.assertEqual(argv[argv.index("-proxycmd") + 1], R_B4_PROXYCMD)
                self.assertEqual(argv[-1], GUARD + command)
                self.assertNotIn("-legacy-stdio-prompts", argv)
                self.assertNotIn("-t", argv)
                self.assertFalse(any(a.startswith("--command=") for a in argv))  # never the gcloud wrapper
                self.assertNotIn("ssh", argv)
                self.assertNotIn(payload.strip().decode("ascii"), " ".join(argv))
                self.assertIn(f"B=$(cat); printf %s \"$B\" | sha256sum | cut -c1-64 | grep -qx '{P.sha(payload.strip())}'"
                              " || exit 96;", argv[-1])
                for path in paths:
                    self.assertIn(f"{Path(path).stem}={O.TOOL_PINS[path]}", argv[-1])
                for forbidden in ("mktemp", "tee ", " > ", ">>", "/tmp/", ".sock", " health", "witness-state",
                                  "systemctl", "bootstrap"):
                    self.assertNotIn(forbidden, argv[-1])

    def test_host_uses_plink_only_for_the_three_bundles(self):
        run = P.FakeRun()
        O.Operator(gcloud=("gcloud",), run=run).host(ROOT, self.work, Path(self.tmp.name) / "h", "PRE")
        plink = [(argv, data) for argv, data in zip(run.calls, run.inputs) if "-proxycmd" in argv]
        gcloud = [argv for argv in run.calls if argv[:3] == ["gcloud", "compute", "ssh"]]
        self.assertEqual(len(plink), 3)
        self.assertEqual(sorted(argv[-1].rsplit(" expect ", 1)[0].split(" ")[-1] for argv, _ in plink),
                         ["mb6_ledger_verifier", "mb8_owner_input_verifier", "mb9_witness_verifier"])
        self.assertTrue(all(data is not None for _, data in plink))
        self.assertEqual(len(gcloud), 7)                                          # identity … W5: unchanged channel
        self.assertTrue(all(data is None for argv, data in zip(run.calls, run.inputs)
                            if argv[:3] == ["gcloud", "compute", "ssh"]))

    def test_mutations_and_their_reads_keep_gcloud_compute_ssh(self):
        run = P.FakeRun()
        op = O.Operator(gcloud=("gcloud",), run=run)
        op.open_sequence(ROOT, self.work, self.text(O.SEQUENCE_LINES, **self.values()))
        self.assertEqual(op.mb9a(ROOT, self.work, self.text(O.MB9A_GO_LINES, **self.values()))["result"],
                         "MB9A_STARTED")
        for argv, data in zip(run.calls, run.inputs):
            if any(m in argv[-1] for m in ("witness-state", "systemctl start", "owner-dev health")):
                self.assertEqual(argv[:4], ["gcloud", "compute", "ssh", M6.DEV])
                self.assertIsNone(data)
            if "-proxycmd" in argv:
                self.assertIn(" mb9_witness_verifier ", argv[-1])

    def test_every_form_but_the_bundle_client_is_byte_identical_to_r_b1(self):
        current = segments(Path(O.__file__).read_text(encoding="utf-8"))
        unchanged = {k: v for k, v in current.items() if k not in ("remote_bundle", "plink_argv", "plink_stdin")}
        self.assertEqual(len(unchanged), 51)
        self.assertEqual(P.sha(json.dumps(unchanged, sort_keys=True).encode()), RB1_UNCHANGED_SEGMENTS)
        self.assertNotIn("ssh_stdin", current)
        self.assertEqual(P.sha((ROOT / O.MB6_OPERATOR).read_bytes()), O.TOOL_PINS[O.MB6_OPERATOR])  # its `ssh`

    def test_there_is_no_fallback_channel(self):
        source = Path(O.__file__).read_text(encoding="utf-8")
        self.assertEqual(source.count("self.plink_stdin("), 1)
        self.assertNotIn("ssh_stdin", source)
        self.assertNotIn("-legacy-stdio-prompts\"", source)
        self.assertNotIn("'-legacy-stdio-prompts'", source)
        body = source.split("    def plink_stdin(", 1)[1].split("\n    def ", 1)[0]
        self.assertNotIn("self.ssh(", body)
        self.assertNotIn("compute\", \"ssh", body)
        for forbidden in ("os-login", "ssh-keys", "ImportSshPublicKey", "SshHostKeys", "putty_force_connect=True",
                          "keygen", "scp", "--flags-file"):
            self.assertNotIn(forbidden, source.split('"""', 2)[2], forbidden)
        run = P.FakeRun()
        with mock.patch.dict(os.environ, {O.PLINK_ENV: ""}):
            with self.assertRaises(O.Stop) as caught:
                O.Operator(gcloud=("gcloud",), run=run).classify(ROOT, self.work, Path(self.tmp.name) / "c")
        self.assertEqual(caught.exception.code, "PLINK_UNSET")
        self.assertEqual(run.remote(), [])                                       # no read went any other way

    def test_client_and_key_bindings_stop_before_launch(self):
        other = Path(self.tmp.name) / "other-plink.exe"
        other.write_bytes(b"another client\n")
        key = Path(self.tmp.name) / "other.ppk"
        key.write_bytes(P.synthetic_ppk(b"\x00\x00\x00\x07ssh-rsa" + b"\x01" * 64))
        cases = ((dict(env=str(Path(self.tmp.name) / "absent.exe")), "PLINK_UNAVAILABLE"),
                 (dict(env=str(other)), "PLINK_PIN_MISMATCH"),
                 (dict(ppk=Path(self.tmp.name) / "absent.ppk"), "PPK_UNAVAILABLE"),
                 (dict(ppk=key), "PPK_KEY_MISMATCH"))
        for change, code in cases:
            with self.subTest(code):
                run = P.FakeRun()
                with mock.patch.dict(os.environ, {O.PLINK_ENV: change.get("env", os.environ[O.PLINK_ENV])}), \
                        mock.patch.object(O, "PPK_PATH", change.get("ppk", O.PPK_PATH)):
                    with self.assertRaises(O.Stop) as caught:
                        O.Operator(gcloud=("gcloud",), run=run).remote_bundle(ROOT, O.VERIFIER_BUNDLE, "observe")
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(run.remote(), [])                               # nothing launched

    def test_transport_failures_are_never_a_pass(self):
        replies = {"hostkey": (1, b"", b"FATAL ERROR: Host key did not match any configured key\n"),
                   "auth": (1, b"", b"FATAL ERROR: No supported authentication methods available\n"),
                   "iap": (1, b"", b"FATAL ERROR: Remote side unexpectedly closed network connection\n"),
                   "integrity": (96, b"", b""), "guard": (97, b"", b""),
                   "stderr": (0, b'{"phase": "W9_0_PRE_WITNESS"}', b"Access granted\n"),
                   "malformed": (0, b"not json", b"")}
        for name, reply in replies.items():
            with self.subTest(name):
                def answer(argv, input=None, reply=reply):                       # noqa: A002
                    if "-proxycmd" in argv:
                        return subprocess.CompletedProcess(argv, *reply)
                    return P.FakeRun()(argv, input)
                calls = []
                counting = lambda argv, input=None: (calls.append(list(argv)), answer(argv, input))[1]  # noqa: E731
                op = O.Operator(gcloud=("gcloud",), run=counting)
                with self.assertRaises(O.Stop) as caught:
                    op.classify(ROOT, self.work, Path(self.tmp.name) / f"c-{name}")
                self.assertEqual(caught.exception.code, "VERIFIER_FAILED")
                self.assertEqual(sum("-proxycmd" in a for a in calls), 1)       # one read, never retried
                result = op.host(ROOT, self.work, Path(self.tmp.name) / f"h-{name}", "PRE")
                self.assertEqual(result["result"], "MB9_HOST_PRE_NOT_PASS")
                if name == "stderr":
                    self.assertEqual(result["codes"]["w9verifier"], O.TRANSPORT_STDERR_EXIT)

        def timeout(argv, input=None):                                         # noqa: A002
            if "-proxycmd" in argv:
                raise subprocess.TimeoutExpired(argv, 900)
            return P.FakeRun()(argv, input)
        with self.assertRaises(subprocess.TimeoutExpired):
            O.Operator(gcloud=("gcloud",), run=timeout).classify(ROOT, self.work, Path(self.tmp.name) / "t")

    def test_the_default_runner_writes_only_the_bundle_to_the_client(self):
        op = O.Operator(gcloud=("gcloud",))
        self.assertIs(op.run, M6._default_run)
        with mock.patch.object(O.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 0, b"ok", b"")) as fake:
            op.plink_stdin("true", b"PAYLOAD\n")
        (argv,), kwargs = fake.call_args
        self.assertEqual(kwargs, {"input": b"PAYLOAD\n", "capture_output": True, "timeout": 900, "check": False})
        self.assertEqual(argv[-1], GUARD + "true")

    def test_the_stop_boundary_is_unchanged(self):
        self.assertEqual(O.STOP_LINES[0], "I stop this Package B sequence now, before M-B9a, for this current "
                                          "DEV_SYNTHETIC sequence only.")
        source = Path(O.__file__).read_text(encoding="utf-8")
        self.assertIn('_need(not attempts.exists() or not any(attempts.iterdir()), "STOP_REFUSED_ATTEMPT_MARKER_PRESENT")',
                      source)
        run = P.FakeRun()
        op = O.Operator(gcloud=("gcloud",), run=run)
        op.open_sequence(ROOT, self.work, self.text(O.SEQUENCE_LINES, **self.values()))
        b1 = P.sha((self.work / "sequence" / "B1_SEQUENCE_AUTHORIZATION.json").read_bytes())
        stop = self.text(O.STOP_LINES, control=P.CONTROL, b1=b1, operator=self.values()["operator"])
        self.assertEqual(op.stop_sequence(ROOT, self.work, stop)["result"], "PACKAGE_B_SEQUENCE_STOPPED_BEFORE_MB9A")
        self.assertEqual(run.remote(), [])


class FakePlinkIntegrationTests(_Work):
    """The operator's default runner launches a real child process (a stand-in client); the bundle crosses the
    process boundary on stdin, far larger than the Windows command-line limit, while the argv stays small."""

    def setUp(self):
        super().setUp()
        self.out = Path(self.tmp.name) / "out"
        self.out.mkdir()
        self.client = Path(self.tmp.name) / "fake_plink.py"
        self.client.write_text(FAKE_PLINK, encoding="utf-8")
        patches = (mock.patch.dict(os.environ, {O.PLINK_ENV: str(self.client), "FAKE_PLINK_OUT": str(self.out)}),
                   mock.patch.object(O, "PLINK_SHA256", P.sha(self.client.read_bytes())))
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.launched = []
        real = subprocess.run

        def launch(argv, **kwargs):                                             # the client is a script here
            self.launched.append((list(argv), dict(kwargs)))
            return real([sys.executable, str(self.client), *argv[1:]], **kwargs)
        patcher = mock.patch.object(O.subprocess, "run", launch)
        patcher.start()
        self.addCleanup(patcher.stop)
        filler = "\n".join(f"# {i:05d} " + P.sha(str(i).encode()) + P.sha(str(-i).encode()) for i in range(2000))
        self.big = (f"{filler}\nimport sys\n"
                    "def main(argv):\n"
                    "    print('PROBE_OK', ' '.join(argv))\n"
                    "    return 0\n")
        self.path = "synthetic/mb9_synthetic_probe.py"
        pins = mock.patch.object(O, "TOOL_PINS", dict(O.TOOL_PINS, **{self.path: P.sha(self.big.encode("utf-8"))}))
        pins.start()
        self.addCleanup(pins.stop)
        self.op = O.Operator(gcloud=R_B4_GCLOUD)
        original = self.op.tool_bytes
        self.op.tool_bytes = lambda repo, path: self.big.encode("utf-8") if path == self.path else original(repo, path)

    def test_the_child_receives_exactly_the_bundle_and_the_intended_argv(self):
        command, payload = self.op.bundled(ROOT, (self.path,), "observe 1 2")
        self.assertGreater(len(payload), 2 * O.COMMAND_LINE_LIMIT)
        result = self.op.remote_bundle(ROOT, (self.path,), "observe 1 2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"phase": "OBSERVED", "bytes": len(payload)})
        self.assertEqual((self.out / "stdin.bin").read_bytes(), payload)        # exact, no prompt bytes
        (argv, kwargs), = self.launched
        self.assertEqual(json.loads((self.out / "argv.json").read_text(encoding="utf-8")), argv[1:])
        self.assertEqual(argv, [str(self.client), "-ssh", "-T", "-batch", "-noagent", "-hostkey", HOST_KEY, "-i",
                                str(O.PPK_PATH), "-proxycmd", R_B4_PROXYCMD, f"{OSLOGIN_USER}@{HOST_ALIAS}",
                                GUARD + command])
        self.assertEqual(kwargs, {"input": payload, "capture_output": True, "timeout": 900, "check": False})
        self.assertLess(len(subprocess.list2cmdline(argv)), 4000)
        self.assertNotIn(payload.strip().decode("ascii")[:200], subprocess.list2cmdline(argv))

    def test_child_stderr_and_exit_codes_are_preserved_and_never_a_pass(self):
        for mode, code in (("stderr", O.TRANSPORT_STDERR_EXIT), ("exit96", 96), ("hostkey", 1)):
            with self.subTest(mode), mock.patch.dict(os.environ, {"FAKE_PLINK_MODE": mode}):
                result = self.op.remote_bundle(ROOT, (self.path,), "observe")
                self.assertEqual(result.returncode, code)
                if mode != "exit96":
                    self.assertTrue(result.stderr)

    @unittest.skipUnless(P.POSIX and SHELL_TOOLS, "needs a POSIX bash with base64 and sha256sum")
    def test_end_to_end_the_remote_gate_loads_an_oversized_bundle_and_refuses_any_change(self):
        env = {"FAKE_PLINK_MODE": "exec", "FAKE_PLINK_SUDO": f"sudo -n {O.RELEASE_PYTHON}",
               "FAKE_PLINK_PYTHON": shlex.quote(sys.executable), "FAKE_PLINK_HOSTNAME": M6.DEV}
        with mock.patch.dict(os.environ, dict(env, FAKE_PLINK_HOSTNAME="some-other-host")):
            self.assertEqual(self.op.remote_bundle(ROOT, (self.path,), "observe").returncode, 97)   # the guard holds
        with mock.patch.dict(os.environ, env):
            result = self.op.remote_bundle(ROOT, (self.path,), "observe 1 2")
            self.assertEqual(result.returncode, 0, result.stderr[-300:])
            self.assertEqual(result.stdout.decode().split(), ["PROBE_OK", "observe", "1", "2"])
            command, payload = self.op.bundled(ROOT, (self.path,), "observe")
            mid = len(payload) // 2
            flipped = payload[:mid] + (b"A" if payload[mid:mid + 1] != b"A" else b"B") + payload[mid + 1:]
            for name, wire in (("flipped", flipped), ("truncated", payload[:-200] + b"\n"),
                               ("appended", payload.strip() + b"QQ\n"), ("y-newline", b"y\n"), ("empty", b"")):
                with self.subTest(name):
                    reply = self.op.plink_stdin(command, wire)
                    self.assertEqual(reply.returncode, 96, name)
                    self.assertNotIn(b"PROBE_OK", reply.stdout)
            bad = command.replace(f"mb9_synthetic_probe={O.TOOL_PINS[self.path]}", "mb9_synthetic_probe=" + "0" * 64)
            self.assertEqual(self.op.plink_stdin(bad, payload).returncode, 96)    # the module pin gate


class RecordTests(P.Redacted, unittest.TestCase):
    STOP_SHA = "0b1912420f0b50a6a7c05f46d69dca93cfcb392442d71adb2bb97aa9647e2b46"

    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = set(self.text.split("## 8. State", 1)[1].splitlines())

    def test_the_owner_stop_is_reproduced_verbatim(self):
        block = self.text.split("## 2. Owner stop (verbatim)", 1)[1].split("```text\n", 1)[1].split("```", 1)[0]
        self.assertEqual(P.sha(block.encode("utf-8")), self.STOP_SHA)
        self.assertIn("Control commit: 103efe50d42ea8f016d671d8ee5f052b9ce961ae. B1 record SHA-256: "
                      "3a9bd61ba39103b899fc18fbdbd0f305105c96cc7a5dca1f71aff035792313c1.", block)

    def test_the_operator_pin_is_current_and_r_b1_superseded(self):
        current = P.sha(Path(O.__file__).read_bytes())
        self.assertNotEqual(current, RB1_OPERATOR)
        # The R-B5 operator, historical since the post-reboot re-pin of its broker verifier pin.
        self.assertEqual(current, P.RP.CURRENT_MB9_OPERATOR_PIN)
        self.assertIn(f"| `mb9_operator.py` after R-B5 | `{P.RP.HISTORICAL_MB9_OPERATOR_PIN}` |", self.text)
        self.assertIn(f"`mb9_operator.py` SHA-256 `{RB1_OPERATOR}`", self.text)
        self.assertIn("OPERATOR_1a91bb2b = SUPERSEDED (MUST NOT BE USED)", self.state)
        self.assertNotIn(RB1_OPERATOR, P.PACKAGE.read_text(encoding="utf-8"))

    def test_history_identities_and_state(self):
        for value in ("103efe50d42ea8f016d671d8ee5f052b9ce961ae", "37813766810", EXPECTED["PLINK_SHA256"],
                      EXPECTED["PPK_PUBLIC_KEY_SHA256"], HOST_KEY, HOST_ALIAS, OSLOGIN_USER,
                      "98466cc306e135700c340724189bbcc0eed2056fab98b32c8c400a4300fd741f",
                      "a841b70ebef4ad9a5fbdfbde047bab5ed3e741c972d9f8c9eee49189790735f7",
                      "6e2edcaba87c48f47309a33bb04955e6e11e0e84399480dc08835eb937aff465",
                      "dfdba43b817b354ebb181e3947e9797f211def4bb40288222871fc4764f26649",
                      "3bb2abb69ebb27fbfe63c7639624c6ec5e331b841a5bc8c3ebc10b9285e90877", "34009", "43688"):
            self.assertIn(value, self.text)
        for line in ("PACKAGE_B_SEQUENCE_2 = OPENED THEN STOPPED BEFORE M-B9a / HISTORICAL / NON-REUSABLE",
                     "W9 (SEQUENCE 2) = UNKNOWN", "WITNESS_MUTATION = NONE",
                     "PACKAGE_B_CONTROL_5ce067c = CONSUMED (NON-REUSABLE)",
                     "PACKAGE_B_CONTROL_103efe5 = CONSUMED (NON-REUSABLE)",
                     "WINDOWS_GCLOUD_STDIN_RAW_TRANSPORT = NOT_EXACT",
                     "GCLOUD_Y_NEWLINE_SOURCE = PROVEN_PUTTY_FORCE_CONNECT_STDIN_INJECTION",
                     "DIRECT_PLINK_STDIN_RAW_TRANSPORT = EXACT_FOR_PROBE_SET",
                     "R-B5_DIRECT_PLINK_VERIFIER_TRANSPORT = NOT YET EXERCISED LIVE", "PACKAGE_B = NOT OPEN",
                     "B2 = NOT AUTHORIZED", "M-B9a = NOT AUTHORIZED", "M-B9b = NOT AUTHORIZED",
                     "WITNESS_GENESIS = NOT COMMITTED", "RECORD 1 = ABSENT", "FIRST MEMORY = NOT AUTHORIZED",
                     "PROD = NOT AUTHORIZED", "FRESHNESS=UNKNOWN"):
            self.assertIn(line, self.state)
        self.assertIn("This proves the raw byte route only.", self.text)
        for claim in P.FORBIDDEN_CLAIMS + ("PACKAGE_B = OPEN", "B2 = AUTHORIZED", "R-B5 = MERGED",
                                           "VERIFIER WRAPPER = PROVEN"):
            self.assertNotIn(claim, self.text.split("## 2.", 1)[0] + self.text.split("## 3.", 1)[1], claim)

    def test_order_package_record_ledger_and_index(self):
        order = P.flat(self.text.split("## 7. Required order", 1)[1].split("## 8.", 1)[0])
        steps = ("R-B5 PR merge", "preservation", "DR-5 EQUAL", "owner preservation acceptance",
                 "new Package B live-control", "new canonical B1", "complete opening evidence from scratch",
                 "first live direct-plink", "B2 closing gate", "separate owner B2 GO")
        positions = [order.index(step) for step in steps]
        self.assertEqual(positions, sorted(positions))
        package = P.PACKAGE.read_text(encoding="utf-8")
        self.assertIn("### 8.2 Verifier client (remediation R-B5)", package)
        self.assertLess(package.index("### 8.1 Verifier transport"), package.index("### 8.2 Verifier client"))
        self.assertIn("(slice-15b2b-b1b3e-mb9-seq2-stdin-stop-direct-plink.md)", package)
        ledger = (P.ARCH / "current-architecture-acceptance-ledger-v0.1.md").read_text(encoding="utf-8")
        self.assertLess(ledger.index("### 13.1an"), ledger.index("### 13.1ao"))
        self.assertLess(ledger.index("### 13.1ao"), ledger.index("### 13.2 Checks"))
        self.assertIn("FRESHNESS=UNKNOWN (§13.1ao)", ledger)   # the AUTH-02 cell (§13.1ap follows)
        ao = ledger.split("### 13.1ao", 1)[1].split("### 13.2 Checks", 1)[0]
        for needed in ("`PACKAGE_B_SEQUENCE_2 = OPENED THEN STOPPED BEFORE M-B9a", "CONSUMED", "None is authorized.",
                       "This pass contacted no live system."):
            self.assertIn(needed, ao)
        readme = (P.ARCH / "README.md").read_text(encoding="utf-8")
        self.assertIn("(slice-15b2b-b1b3e-mb9-seq2-stdin-stop-direct-plink.md)", readme)


if __name__ == "__main__":
    unittest.main()
