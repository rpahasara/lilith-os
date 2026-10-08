"""15B2b-B1b-3e Package B remediation R-B1: verifier bundles over stdin + the owner pre-M-B9a stop (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-mb9-seq1-w9-transport-stop.md and the Package B record §8.1 / §10.8.

Package B sequence 1 stopped because the W9 verifier bundle (43688 characters) was placed in one
`gcloud compute ssh --command=` argument and Windows refused the launch (WinError 206, limit 32767). These tests
reproduce that defect from the canonical bundle, prove the fixed transport keeps every command line below the
limit, prove the bundle bytes are checked end to end (digest in the command, per-module pins in the unchanged M-B6
loader) including a synthetic payload far beyond the limit, prove transport failures still STOP, and pin the exact
boundary of the new pre-M-B9a stop: available after B1 and before any attempt marker, never after.

Nothing touches DEV, the S25 or any real key. The end-to-end shell cases need a POSIX bash with base64 / sha256sum.

R-B5 moved the channel under these bundles from `gcloud compute ssh` stdin to a directly launched plink (that suite:
test_b1b3e_mb9_direct_plink_transport.py). The R-B1 properties checked here (the digest gate, the per-module pins,
the command length, read-only use only, the stop) are unchanged and now hold on that channel.
"""

from __future__ import annotations

import base64
import gzip
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

import test_b1b3e_mb9_package as P  # noqa: E402  (shared fixtures; its TestCases are not re-collected here)

O, M6, C = P.O, P.M6, P.C
ROOT = P.ROOT
# The owner's Windows gcloud prefix (the bundled-python recipe): the real command line carries both paths.
WINDOWS_GCLOUD = ("C:/Users/edufo/AppData/Local/Google/Cloud SDK/google-cloud-sdk/platform/bundledpython/python.exe",
                  "C:/Users/edufo/AppData/Local/Google/Cloud SDK/google-cloud-sdk/lib/gcloud.py")
BUNDLES = {"w9": O.VERIFIER_BUNDLE, "w8": O.W8_BUNDLE, "mb6": O.MB6_VERIFIER_BUNDLE}
SHELL_TOOLS = all(shutil.which(t) for t in ("bash", "base64", "sha256sum", "cut", "grep"))


def legacy_bundled(op: O.Operator, paths, args: str) -> str:
    """The sequence-1 construction (operator 7f630ed3…): the whole bundle inside the command argument."""
    sources = {Path(p).stem: op.tool_bytes(ROOT, p).decode("utf-8") for p in paths}
    blob = base64.b64encode(gzip.compress(json.dumps(sources).encode("utf-8"), mtime=0)).decode("ascii")
    pins = ",".join(f"{Path(p).stem}={O.TOOL_PINS[p]}" for p in paths)
    boot = base64.b64encode(M6.BOOT.encode("ascii")).decode("ascii")
    return (f"B={blob}; printf %s \"$B\" | base64 -d | sudo -n {O.RELEASE_PYTHON} -I -B -c "
            f"\"import base64;exec(base64.b64decode('{boot}'))\" {pins} {Path(paths[-1]).stem} {args}")


def windows_command_line(command: str) -> str:
    guarded = f'test "$(hostname)" = {M6.DEV} || exit 97; {command}'
    return subprocess.list2cmdline([*WINDOWS_GCLOUD, "compute", "ssh", M6.DEV, f"--zone={M6.ZONE}",
                                    f"--project={M6.PROJECT}", "--tunnel-through-iap", f"--command={guarded}"])


def decode(payload: bytes) -> dict:
    return json.loads(gzip.decompress(base64.b64decode(payload.strip())).decode("utf-8"))


class _Work(P.Redacted, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name) / "work"
        self.work.mkdir()
        C.write_emitted(P.synthetic_derivation(), self.work / "genesis")
        self.c = O.Operator.candidate(self.work)
        self.operator_sha = P.sha(Path(O.__file__).read_bytes())

    def text(self, lines, **values) -> Path:
        path = Path(self.tmp.name) / f"text-{len(os.listdir(self.tmp.name))}.txt"
        path.write_text("\n".join("> " + line.format(**values) for line in lines) + "\n", encoding="utf-8")
        return path

    def values(self, **overrides):
        values = dict(control=P.CONTROL, operator=self.operator_sha, candidate=self.c["candidate"], pin=self.c["pin"],
                      register=self.c["register"], record=self.c["record"], updated_at=P.UPDATED_AT,
                      invocation=P.INVOCATION, mainpid=P.MAINPID, post9a="")
        values.update(overrides)
        return values


class TransportTests(_Work):
    def test_the_sequence_1_defect_reproduces_from_the_canonical_bundle(self):
        op = O.Operator(gcloud=WINDOWS_GCLOUD, run=P.FakeRun())
        args = f"expect W9_0_PRE_WITNESS {op._w9_args(self.work)}"
        legacy = legacy_bundled(op, O.VERIFIER_BUNDLE, args)
        self.assertGreater(len(legacy), O.COMMAND_LINE_LIMIT)                    # 43688 at the stopped control
        self.assertGreater(len(windows_command_line(legacy)), O.COMMAND_LINE_LIMIT)
        command, payload = op.bundled(ROOT, O.VERIFIER_BUNDLE, args)
        self.assertLess(len(windows_command_line(command)), O.COMMAND_LINE_LIMIT)
        self.assertNotIn(payload.strip().decode("ascii"), command)
        self.assertGreater(len(payload), O.COMMAND_LINE_LIMIT)                   # the bytes now ride stdin

    def test_every_verifier_read_travels_over_stdin_with_its_exact_pinned_bundle(self):
        for name, paths in BUNDLES.items():
            with self.subTest(name):
                run = P.FakeRun()
                op = O.Operator(gcloud=WINDOWS_GCLOUD, run=run)
                op.remote_bundle(ROOT, paths, "observe x")
                (argv,), (data,) = run.calls[-1:], run.inputs[-1:]
                self.assertIsNotNone(data)
                command = argv[-1]                                               # R-B5: plink's command
                self.assertIn("-proxycmd", argv)
                self.assertTrue(command.startswith(f'test "$(hostname)" = {M6.DEV} || exit 97; B=$(cat); '))
                self.assertIn(f"grep -qx '{P.sha(data.strip())}' || exit 96", command)
                self.assertLess(len(subprocess.list2cmdline(argv)), O.COMMAND_LINE_LIMIT)
                sources = decode(data)
                self.assertEqual(list(sources), [Path(p).stem for p in paths])          # order = loader entry last
                for path in paths:
                    self.assertEqual(P.sha(sources[Path(path).stem].encode("utf-8")), O.TOOL_PINS[path])
                    self.assertIn(f"{Path(path).stem}={O.TOOL_PINS[path]}", command)
                self.assertIn(f" {Path(paths[-1]).stem} observe x", command)

    def test_every_command_line_the_operator_builds_fits_windows(self):
        run = P.FakeRun(w9=("W9_0_PRE_WITNESS",))
        op = O.Operator(gcloud=WINDOWS_GCLOUD, run=run)
        for phase in ("PRE", "POST9A", "POST9B"):
            op.host(ROOT, self.work, Path(self.tmp.name) / f"host-{phase}", phase)
        for path in (O.INSTALLER, O.BROKER, O.OBSERVER, O.W5_VERIFIER, O.DENIAL, O.LEDGER_DENIAL, O.OWNER_DENIAL,
                     O.WITNESS_DENIAL, O.REMOVAL):
            op.ssh(op.streamed(ROOT, path, O.SYSTEM_PYTHON, "P1B-9b witness-state remove " + "0" * 64))
        remote = [argv for argv in run.calls if argv[-1].startswith("--command=") or "-proxycmd" in argv]
        self.assertGreaterEqual(len(remote), 39)
        for argv in remote:
            self.assertLess(len(subprocess.list2cmdline(argv)), O.COMMAND_LINE_LIMIT, argv[-1][:80])

    def test_the_default_runner_hands_the_payload_to_the_ssh_client_stdin(self):
        op = O.Operator(gcloud=("gcloud",))
        self.assertIs(op.run, M6._default_run)
        with mock.patch.object(O.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 0, b"", b"")) as fake:
            op.plink_stdin("true", b"PAYLOAD\n")                               # R-B5: the client is plink
        (argv,), kwargs = fake.call_args
        self.assertEqual(kwargs, {"input": b"PAYLOAD\n", "capture_output": True, "timeout": 900, "check": False})
        self.assertEqual(argv[0], os.environ[O.PLINK_ENV])
        self.assertEqual(argv[-2:], [f"{O.OSLOGIN_USER}@{O.HOST_ALIAS}", f'test "$(hostname)" = {M6.DEV} || exit 97; true'])

    def test_transport_failures_still_stop(self):
        def timeout(argv, input=None):                                         # noqa: A002
            if input is not None:
                raise subprocess.TimeoutExpired(argv, 900)
            return P.FakeRun()(argv)
        with self.assertRaises(subprocess.TimeoutExpired):                       # a read is never retried or absorbed
            O.Operator(gcloud=("gcloud",), run=timeout).classify(ROOT, self.work, Path(self.tmp.name) / "c1")
        for reply in ((255, b"", b"ssh: connect: lost\n"), (96, b"", b""), (0, b"not json", b"")):
            def answer(argv, input=None, reply=reply):                           # noqa: A002
                if input is not None:
                    return subprocess.CompletedProcess(argv, *reply)
                return P.FakeRun()(argv)
            op = O.Operator(gcloud=("gcloud",), run=answer)
            with self.assertRaises(O.Stop) as caught:
                op.classify(ROOT, self.work, Path(self.tmp.name) / f"c-{reply[0]}-{len(reply[1])}")
            self.assertEqual(caught.exception.code, "VERIFIER_FAILED")
            result = op.host(ROOT, self.work, Path(self.tmp.name) / f"h-{reply[0]}-{len(reply[1])}", "PRE")
            if reply[0]:
                self.assertEqual(result["result"], "MB9_HOST_PRE_NOT_PASS")

    def test_stdin_carries_only_read_only_verifier_bundles(self):
        source = Path(O.__file__).read_text(encoding="utf-8")
        self.assertEqual(source.count("self.plink_stdin("), 1)                    # only inside remote_bundle (R-B5)
        calls = [line.split("remote_bundle(", 1)[1] for line in source.splitlines() if "self.remote_bundle(" in line]
        self.assertEqual(len(calls), 4)
        following = source.split("self.remote_bundle(")[1:]
        for chunk in following:
            self.assertRegex(chunk.split(")", 1)[0], r"(VERIFIER_BUNDLE|MB6_VERIFIER_BUNDLE|W8_BUNDLE)")
        run = P.FakeRun()
        op = O.Operator(gcloud=("gcloud",), run=run)
        op.open_sequence(ROOT, self.work, self.text(O.SEQUENCE_LINES, **self.values()))
        self.assertEqual(op.mb9a(ROOT, self.work, self.text(O.MB9A_GO_LINES, **self.values()))["result"],
                         "MB9A_STARTED")
        stdin_commands = [argv[-1] for argv, data in zip(run.calls, run.inputs) if data is not None]
        self.assertTrue(all("-proxycmd" in argv for argv, data in zip(run.calls, run.inputs) if data is not None))
        self.assertTrue(stdin_commands)
        for command in stdin_commands:
            self.assertIn(" mb9_witness_verifier ", command)
            for mutation in ("witness-state", "systemctl", "bootstrap", " remove ", "owner-dev health"):
                self.assertNotIn(mutation, command)
        for argv, data in zip(run.calls, run.inputs):                            # mutations keep the old channel
            if any(m in argv[-1] for m in ("witness-state", "systemctl start", "owner-dev health")):
                self.assertIsNone(data)

    def test_the_witness_verifier_and_its_pin_are_unchanged(self):
        self.assertEqual(O.TOOL_PINS[O.VERIFIER], "e4aca11dcc925e8ebdb280c2d4a7da1cf4f9a8fcc4e2abb080e22d6917080e78")
        self.assertEqual(P.sha((ROOT / O.VERIFIER).read_bytes()), O.TOOL_PINS[O.VERIFIER])
        self.assertIn("sys.stdin.buffer.read()", M6.BOOT)                         # the loader always read stdin


@unittest.skipUnless(P.POSIX and SHELL_TOOLS, "needs a POSIX bash with base64 and sha256sum")
class EndToEndShellTests(_Work):
    """The real remote command, run by a local bash with the real coreutils; only `sudo -n <release python>` is
    replaced by this interpreter. The synthetic module is far larger than the Windows limit."""

    def setUp(self):
        super().setUp()
        # incompressible filler: the gzip'd, base64'd payload must still exceed the limit several times over
        filler = "\n".join(f"# {i:05d} " + P.sha(str(i).encode()) + P.sha(str(-i).encode()) for i in range(2000))
        self.big = (f"{filler}\nimport hashlib, sys\n"
                    "def main(argv):\n"
                    "    src = sys.modules['mb9_synthetic_probe'].SOURCE_SHA\n"
                    "    print('PROBE_OK', src, ' '.join(argv))\n"
                    "    return 0\n")
        self.source_sha = P.sha(self.big.encode("utf-8"))
        self.big += f"SOURCE_SHA = '{self.source_sha}'\n"
        self.path = "synthetic/mb9_synthetic_probe.py"
        pins = dict(O.TOOL_PINS, **{self.path: P.sha(self.big.encode("utf-8"))})
        patcher = mock.patch.object(O, "TOOL_PINS", pins)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.op = O.Operator(gcloud=("gcloud",), run=P.FakeRun())
        original = self.op.tool_bytes
        self.op.tool_bytes = lambda repo, path: self.big.encode("utf-8") if path == self.path else original(repo, path)

    def remote(self, command: str, data: bytes) -> subprocess.CompletedProcess:
        local = command.replace(f"sudo -n {O.RELEASE_PYTHON}", shlex.quote(sys.executable))
        self.assertNotEqual(local, command)
        return subprocess.run(["bash", "-c", local], input=data, capture_output=True, timeout=60, check=False)

    def test_an_oversized_bundle_is_delivered_and_loaded_exactly(self):
        command, data = self.op.bundled(ROOT, (self.path,), "observe 1 2")
        self.assertGreater(len(data), 2 * O.COMMAND_LINE_LIMIT)
        self.assertLess(len(command), 2000)
        result = self.remote(command, data)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.decode().split(), ["PROBE_OK", self.source_sha, "observe", "1", "2"])

    def test_any_change_on_the_channel_is_refused_before_python_runs(self):
        command, data = self.op.bundled(ROOT, (self.path,), "observe")
        mid = len(data) // 2
        flipped = data[:mid] + (b"A" if data[mid:mid + 1] != b"A" else b"B") + data[mid + 1:]
        for name, wire in (("flipped", flipped), ("truncated", data[:-200] + b"\n"), ("crlf", data.strip() + b"\r\n"),
                           ("empty", b""), ("appended", data.strip() + b"QQ\n")):
            with self.subTest(name):
                result = self.remote(command, wire)
                self.assertEqual(result.returncode, 96, (name, result.stderr[-200:]))
                self.assertNotIn(b"PROBE_OK", result.stdout)

    def test_the_loader_still_refuses_a_module_pin_mismatch(self):
        command, data = self.op.bundled(ROOT, (self.path,), "observe")
        bad = command.replace(f"mb9_synthetic_probe={O.TOOL_PINS[self.path]}", "mb9_synthetic_probe=" + "0" * 64)
        self.assertNotEqual(bad, command)
        result = self.remote(bad, data)
        self.assertEqual(result.returncode, 96)
        self.assertNotIn(b"PROBE_OK", result.stdout)


class PreMb9aStopTests(_Work):
    def stop_values(self, **overrides):
        b1 = P.sha((self.work / "sequence" / "B1_SEQUENCE_AUTHORIZATION.json").read_bytes())
        return dict(dict(control=P.CONTROL, b1=b1, operator=self.operator_sha), **overrides)

    def opened(self):
        run = P.FakeRun()
        op = O.Operator(gcloud=("gcloud",), run=run)
        op.open_sequence(ROOT, self.work, self.text(O.SEQUENCE_LINES, **self.values()))
        return op, run

    def test_stop_needs_a_recorded_b1(self):
        op = O.Operator(gcloud=("gcloud",), run=P.FakeRun())
        with self.assertRaises(O.Stop) as caught:
            op.stop_sequence(ROOT, self.work, self.text(O.STOP_LINES, control=P.CONTROL, b1="0" * 64,
                                                        operator=self.operator_sha))
        self.assertEqual(caught.exception.code, "SEQUENCE_NOT_OPENED")

    def test_stop_before_any_marker_releases_and_blocks_every_later_act(self):
        op, run = self.opened()
        result = op.stop_sequence(ROOT, self.work, self.text(O.STOP_LINES, **self.stop_values()))
        self.assertEqual(result["result"], "PACKAGE_B_SEQUENCE_STOPPED_BEFORE_MB9A")
        record = json.loads((self.work / "sequence" / "B1_SEQUENCE_STOPPED.json").read_text(encoding="ascii"))
        self.assertEqual((record["classification"], record["freeze"], record["controlSelection"]),
                         ("OPENED_THEN_STOPPED_BEFORE_MB9A", "RELEASED", "CONSUMED"))
        self.assertEqual(record["b1RecordSha256"], self.stop_values()["b1"])
        self.assertEqual(run.remote(), [])                                       # local only: nothing reached DEV
        for act, lines in ((op.mb9a, O.MB9A_GO_LINES), (op.mb9b, O.MB9B_GO_LINES)):
            with self.assertRaises(O.Stop) as caught:
                act(ROOT, self.work, self.text(lines, **self.values()))
            self.assertEqual(caught.exception.code, "SEQUENCE_STOPPED")
        with self.assertRaises(O.Stop) as caught:
            op.stop_sequence(ROOT, self.work, self.text(O.STOP_LINES, **self.stop_values()))
        self.assertEqual(caught.exception.code, "SEQUENCE_STOPPED")
        with self.assertRaises(O.Stop) as caught:
            op.open_sequence(ROOT, self.work, self.text(O.SEQUENCE_LINES, **self.values()))
        self.assertEqual(caught.exception.code, "SEQUENCE_ALREADY_OPENED")          # never reopened in place
        self.assertFalse((self.work / "attempts").exists())
        self.assertEqual(run.remote(), [])

    def test_stop_is_never_available_once_an_attempt_marker_exists(self):
        op, run = self.opened()
        self.assertEqual(op.mb9a(ROOT, self.work, self.text(O.MB9A_GO_LINES, **self.values()))["result"],
                         "MB9A_STARTED")
        before = len(run.calls)
        with self.assertRaises(O.Stop) as caught:
            op.stop_sequence(ROOT, self.work, self.text(O.STOP_LINES, **self.stop_values()))
        self.assertEqual(caught.exception.code, "STOP_REFUSED_ATTEMPT_MARKER_PRESENT")
        self.assertFalse((self.work / "sequence" / "B1_SEQUENCE_STOPPED.json").exists())
        self.assertEqual(run.remote()[before:], [])

    def test_any_marker_or_attempt_file_blocks_the_stop(self):
        for name in ("mb9a-1.json", "mb9a-2.json", "mb9b.json", "mb9a-1-transcript.json", "other"):
            with self.subTest(name):
                self.work = Path(tempfile.mkdtemp(dir=self.tmp.name))
                C.write_emitted(P.synthetic_derivation(), self.work / "genesis")
                op, _ = self.opened()
                (self.work / "attempts").mkdir()
                (self.work / "attempts" / name).write_text("{}\n", encoding="ascii")
                with self.assertRaises(O.Stop) as caught:
                    op.stop_sequence(ROOT, self.work, self.text(O.STOP_LINES, **self.stop_values()))
                self.assertEqual(caught.exception.code, "STOP_REFUSED_ATTEMPT_MARKER_PRESENT")
        self.work = Path(tempfile.mkdtemp(dir=self.tmp.name))                     # an empty attempt dir is no marker
        C.write_emitted(P.synthetic_derivation(), self.work / "genesis")
        op, _ = self.opened()
        (self.work / "attempts").mkdir()
        self.assertEqual(op.stop_sequence(ROOT, self.work, self.text(O.STOP_LINES, **self.stop_values()))["result"],
                         "PACKAGE_B_SEQUENCE_STOPPED_BEFORE_MB9A")

    def test_the_stop_text_binds_control_b1_and_operator(self):
        op, _ = self.opened()
        for bad in (dict(b1="0" * 64), dict(operator="0" * 64), dict(control="0" * 40)):
            with self.assertRaises(O.Stop) as caught:
                op.stop_sequence(ROOT, self.work, self.text(O.STOP_LINES, **self.stop_values(**bad)))
            self.assertEqual(caught.exception.code, "GO_LINE_MISSING", bad)
        partial = self.text(O.STOP_LINES[:-1], **self.stop_values())
        with self.assertRaises(O.Stop):
            op.stop_sequence(ROOT, self.work, partial)
        self.assertFalse((self.work / "sequence" / "B1_SEQUENCE_STOPPED.json").exists())

    def test_the_stop_text_authorizes_nothing(self):
        joined = P.flat(" ".join(O.STOP_LINES))
        for phrase in ("before M-B9a", "No B2 was issued", "no M-B9a or M-B9b attempt marker exists",
                       "HISTORICAL / NON-REUSABLE", "must not be replayed", "freeze of this sequence is RELEASED",
                       "authorizes no deployment, merge or DEV change", "CONSUMED by this sequence and is not reusable",
                       "This stop authorizes nothing further", "a new canonical B1"):
            self.assertIn(phrase, joined)
        for forbidden in ("I authorize", "M-B9a = AUTHORIZED", "removal", "restart"):
            self.assertNotIn(forbidden, joined)


class RecordTests(P.Redacted, unittest.TestCase):
    RECORD = P.ARCH / "slice-15b2b-b1b3e-mb9-seq1-w9-transport-stop.md"
    STOP_SHA = "a08d3d08e72badb2652f74d8f43a27be37b889434d85d6a2dd864344c49bae2d"
    OLD_OPERATOR = "7f630ed3106d7d64351d0fe291004b9df651b1c937f83bd9503ec89369b862db"

    def setUp(self):
        self.text = self.RECORD.read_text(encoding="utf-8")
        self.state = set(self.text.split("## 8. State", 1)[1].splitlines())

    def test_the_owner_stop_is_reproduced_verbatim(self):
        block = self.text.split("## 2. Owner stop (verbatim)", 1)[1].split("```text\n", 1)[1].split("```", 1)[0]
        self.assertEqual(P.sha(block.encode("utf-8")), self.STOP_SHA)
        self.assertIn(f"`{self.STOP_SHA}`", self.text)
        for needed in ("I stop Package B sequence 1 for DEV_SYNTHETIC now.", "CLIENT_TRANSPORT_CONSTRUCTION_LIMIT_BEFORE_W9_DEV_CONTACT",
                       "is CONSUMED by Package B sequence 1.", "NEW CANONICAL PRE-M-B9a STOP RULE"):
            self.assertIn(needed, block)

    RB1_OPERATOR = "1a91bb2b0258cbec0028346ceede9c6e43135d556756fffe4f8696da66abbc29"   # superseded by R-B5

    def test_the_operator_pins_are_current_and_the_old_one_superseded(self):
        current = P.sha(Path(O.__file__).read_bytes())
        self.assertNotEqual(current, self.OLD_OPERATOR)
        self.assertNotEqual(current, self.RB1_OPERATOR)                          # the R-B5 record pins the current one
        self.assertIn(f"| `mb9_operator.py` after R-B1 | `{self.RB1_OPERATOR}` |", self.text)
        self.assertIn(f"`mb9_operator.py` SHA-256 `{self.OLD_OPERATOR}`", self.text)
        self.assertIn("OPERATOR_7f630ed3 = SUPERSEDED (MUST NOT BE USED)", self.state)
        package = P.PACKAGE.read_text(encoding="utf-8")
        self.assertNotIn(self.OLD_OPERATOR, package)                           # bound at runtime, never a static pin
        self.assertIn("<operator>", package)

    def test_sequence_1_identities_and_classification(self):
        for value in ("5ce067cf485cafed6ea2487635027955396e7844", "37803630416",
                      "7fa7e028c1cc36d316a175a4f6182f6a898b250f946c7bcf84e9a5f7bfeda9ba",
                      "bacc0376240370d2d7dc7911d907c56492e181fb5c088242b9672d2b9cacb916",
                      "08d88e92405152f55c607e689e179ef35597801fe80674015784b77971005c2b",
                      "6bea4e47e99c7aca55445bd7e6b8d55cec911ddce62fae45d86a886b640e7266",
                      "35e76e93f58dec7be47a2c51904af7f9613844369ebd2d4181493eab50f82af2", "43688", "WinError 206"):
            self.assertIn(value, self.text)
        for line in ("PACKAGE_B_SEQUENCE_1 = OPENED THEN STOPPED DURING OPENING EVIDENCE / TOOL_DEFECT / HISTORICAL / "
                     "NON-REUSABLE", "W9 (SEQUENCE 1) = UNKNOWN", "DEV_W9_CONTACT = NO", "WITNESS_MUTATION = NONE",
                     "PACKAGE_B_FREEZE_SEQUENCE_1 = RELEASED (OWNER DECISION; AUTHORIZES NOTHING)",
                     "PACKAGE_B_CONTROL_5ce067c = CONSUMED (NON-REUSABLE)", "R-B1_STDIN_TRANSPORT = NOT YET EXERCISED LIVE",
                     "PACKAGE_B = NOT OPEN", "B2 = NOT AUTHORIZED", "M-B9a = NOT AUTHORIZED", "M-B9b = NOT AUTHORIZED",
                     "WITNESS_GENESIS = NOT COMMITTED", "RECORD 1 = ABSENT", "FIRST MEMORY = NOT AUTHORIZED",
                     "PROD = NOT AUTHORIZED", "FRESHNESS=UNKNOWN"):
            self.assertIn(line, self.state)
        for claim in P.FORBIDDEN_CLAIMS + ("PACKAGE_B = OPEN", "B2 = AUTHORIZED", "R-B1 = MERGED"):
            self.assertNotIn(claim, self.text.split("## 2.", 1)[0] + self.text.split("## 3.", 1)[1], claim)

    def test_the_package_record_carries_the_transport_rule_and_the_stop(self):
        package = P.PACKAGE.read_text(encoding="utf-8")
        self.assertIn("### 8.1 Verifier transport (remediation R-B1)", package)
        self.assertIn("### 10.8 Owner pre-M-B9a stop (remediation R-B1)", package)
        self.assertIn("`stop-sequence` (the pre-M-B9a stop, local; §10.8)", package)
        self.assertIn("an owner pre-M-B9a stop (§10.8) ends the sequence and releases\nits freeze instead (R-B1)", package)
        self.assertIn("| `stop-sequence <repo> <workdir> <statement>` |", Path(O.__file__).read_text(encoding="utf-8"))
        order = P.flat(self.text.split("## 7. Required order", 1)[1].split("## 8.", 1)[0])
        steps = ("R-B1 PR merge", "preservation", "DR-5 EQUAL", "owner preservation acceptance", "new Package B live-control",
                 "new canonical B1", "complete opening evidence from scratch", "B2 closing gate", "separate owner B2 GO")
        positions = [order.index(step) for step in steps]
        self.assertEqual(positions, sorted(positions))

    def test_ledger_and_index(self):
        ledger = (P.ARCH / "current-architecture-acceptance-ledger-v0.1.md").read_text(encoding="utf-8")
        self.assertLess(ledger.index("### 13.1am"), ledger.index("### 13.1an"))
        self.assertLess(ledger.index("### 13.1an"), ledger.index("### 13.2 Checks"))
        self.assertIn("FRESHNESS=UNKNOWN (§13.1an)", ledger)   # the AUTH-02 cell (§13.1ao follows)
        an = ledger.split("### 13.1an", 1)[1].split("### 13.2 Checks", 1)[0]
        for needed in ("`PACKAGE_B_SEQUENCE_1 = OPENED THEN STOPPED DURING OPENING EVIDENCE", "CONSUMED",
                       "None is authorized.", "This pass contacted no live system."):
            self.assertIn(needed, an)
        readme = (P.ARCH / "README.md").read_text(encoding="utf-8")
        self.assertIn("(slice-15b2b-b1b3e-mb9-seq1-w9-transport-stop.md)", readme)


if __name__ == "__main__":
    unittest.main()
