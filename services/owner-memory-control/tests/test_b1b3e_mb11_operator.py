"""15B2b-B1b-3e M-B11 START_SIGNER operator: gate, go, one start, post (HEALTH capture + the unchanged W11 verifier).

Record: docs/architecture/slice-15b2b-b1b3e-mb11-signer-start-operator.md. TEST-ONLY: a fake DEV behind the operator's
transport seams runs the REAL host-side tail (`mb11_start_remote.run_form`) and the REAL W11 verifier
(`mb11_signer_verifier.evaluate` / `classify`) over synthetic signer facts, and the REAL mb6 BOOT loader runs the real
bundle from an empty working directory. Nothing here contacts DEV, runs systemctl, opens a socket or loads a credential.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _p in (TOOLS, HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import mb11_operator as OP  # noqa: E402
import mb11_signer_verifier as W  # noqa: E402
import mb11_start_remote as R  # noqa: E402
import mb6_operator as M6  # noqa: E402
import test_b1b3e_mb11_signer_start as T  # noqa: E402  (helpers only: exact HEALTH / readiness / unit facts)

POSIX = os.name == "posix"
HAVE_JCS = importlib.util.find_spec("rfc8785") is not None
WITNESS = OP.WITNESS
SIGNER = "a" * 32
DB = "c" * 64
CURSOR = "s=4704cb6f;i=b0001;b=cb0d71da;m=1;t=2;x=3"
LATER_CURSOR = "s=4704cb6f;i=b0002;b=cb0d71da;m=1;t=2;x=4"
ENVELOPE = b'{"envelopeType":"SYNTHETIC"}\n'
INPUTS = {"synthetic": "owner inputs (TEST)"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def good_current() -> dict:
    """The canonical release `observe_current_blob().to_dict()` form of the pinned DEV CURRENT slot (synthetic times)."""
    return {"path": "/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred", "kind": "REGULAR", "uid": 0,
            "gid": 0, "mode": "0600", "device": "2049", "inode": "1738", "size": 219, "mtimeNs": "1790493331258019177",
            "ctimeNs": "1790493331258019177",
            "sha256": "6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3"}


def stopped_units() -> dict:
    units = T.stopped_units()
    for name in W.SIGNER_UNITS:
        units[name].update(FragmentPath=f"/etc/systemd/system/{name}")
    return units


class FakeDev:
    """DEV behind the operator's seams. The host-side tail and the W11 verifier are REAL; the signer facts are synthetic
    and move exactly as one `systemctl start` of the service would (or as the chosen failure would)."""

    def __init__(self, root: Path):
        self.root = root
        self.mutations: list[str] = []
        self.remote_forms: list[str] = []
        self.health_calls = 0
        self.start_effect = "ONE_LOAD"
        self.units_now = stopped_units()
        self.invocations: list[dict] = []
        self.boundary: list[str] = []
        self.witness = WITNESS
        self.cwd = W.RELEASE_CWD
        self.health_value = T.good_health()
        self.paths = {"credentials": {"present": False}, "ownerSocket": {"present": False}}
        self.tail = CURSOR
        self.current_doc = good_current()
        self.current_module = "/opt/lilith-authority-dev/current/lilith_authority_root/observers.py"
        self.clock = "2026-10-15T08:00:00Z"
        ledger = root / "var/lib/lilith-authority-dev"
        ledger.mkdir(parents=True)
        (ledger / W.LEDGER_NAME).write_bytes(b"synthetic ledger bytes")
        self.db = sha(b"synthetic ledger bytes")

    @staticmethod
    def done(code=0, out=b"", err=b""):
        return subprocess.CompletedProcess([], code, out, err)

    # ---- the signer facts ----
    def units(self, names):
        return {name: dict(self.units_now[name]) for name in names if name in self.units_now}

    def run(self):
        self.units_now = T.running_units()
        for name in W.SIGNER_UNITS:
            self.units_now[name].update(FragmentPath=f"/etc/systemd/system/{name}")
        self.units_now[W.SIGNER_SERVICE]["MainPID"] = "4242"
        self.paths = {"credentials": {"present": True, "kind": "dir", "uid": 995, "gid": 985, "mode": 0o500,
                                      "names": [W.CREDENTIAL_NAME]},
                      "ownerSocket": {"present": True, "kind": "socket", "uid": 0, "gid": 0, "mode": 0o600}}

    def path_facts(self, path, *, names=False):
        return dict(self.paths["credentials" if "credentials" in str(path) else "ownerSocket"])

    def health(self):
        self.health_calls += 1
        if self.units_now[W.SIGNER_SERVICE]["ActiveState"] != "active":
            raise AssertionError("HEALTH contacted while the service is not running")
        return dict(self.health_value)

    def w10(self, head, candidate, updated, *, root, units, **_seams):
        import mb6_ledger_verifier as V6

        V6._lstat(W._host(root, W.SIGNER_CREDENTIALS))
        V6._lstat(W._host(root, W.SIGNER_OWNER_SOCKET))
        view = units(list(W.SIGNER_UNITS))
        running = view[W.SIGNER_SERVICE]["ActiveState"] == "active"
        return {"phase": "W10_SIGNER_OR_LATER_STATE" if running else W.W10_1, "holdClass": "HELD_EXACT",
                "witnessInvocationId": self.witness[0], "witnessMainPid": self.witness[1], "w9Failures": [],
                "failures": []}

    def readiness(self, _owner, health, **_kw):
        return T.good_readiness() if health is not None else {"eligibility": {"status": "NOT_READY"},
                                                              "full": {"status": "NOT_READY"}}

    def process(self, _root, pid):
        if pid != "4242":
            return None
        return {"cwd": self.cwd, "argv": list(W.EXEC_ARGV), "uid": 995, "gid": 985}

    def remote(self, doc):
        with mock.patch.object(W, "_path_facts", self.path_facts):
            return R.run_form(doc, root=self.root, W=W, units=self.units, health=self.health, tail=lambda: self.tail,
                              ids=lambda: [995, 985], journal=lambda _c: {"readable": True,
                                                                          "invocations": list(self.invocations)},
                              process=self.process, w10=self.w10, readiness=self.readiness,
                              restart_boundary=lambda _r, _u: {"reasons": list(self.boundary)},
                              current=self.observe_current, clock=lambda: self.clock)

    def observe_current(self, root):
        assert Path(root) == self.root
        return dict(self.current_doc), self.current_module

    # ---- the transport ----
    def plink(self, command: str, payload: bytes):
        match = re.search(r"grep -qx '([0-9a-f]{64})'.*sudo -n (\S+) -I -B -c \"[^\"]+\" (\S+) (\S+) (\S+) (\S+)\Z",
                          command)
        assert match is not None, command
        digest, interpreter, pins, entry, form, evidence = match.groups()
        assert sha(payload.rstrip(b"\n")) == digest and interpreter == OP.M9.RELEASE_PYTHON and entry == "mb11_start_remote"
        sources = json.loads(gzip.decompress(base64.b64decode(payload)))
        declared = dict(item.split("=", 1) for item in pins.split(","))
        assert list(sources) == list(declared) and all(sha(s.encode()) == declared[n] for n, s in sources.items())
        assert list(sources)[-2:] == [R.EVIDENCE_MODULE, "mb11_start_remote"]
        namespace: dict = {}
        exec(sources[R.EVIDENCE_MODULE], namespace)                       # noqa: S102 - the generated data module
        doc = R.check_evidence(namespace["DOC"], form)
        assert R.evidence_digest(doc) == evidence
        self.remote_forms.append(form)
        return self.done(out=json.dumps(self.remote(doc), default=str).encode())

    def mutation(self, command: str):
        self.mutations.append(command)
        assert command == OP.START_SIGNER_COMMAND, command
        effect = self.start_effect
        if effect == "FAILED":
            self.invocations = [{"id": SIGNER, "credentials": W.FAILED}]
            self.units_now[W.SIGNER_SERVICE].update(Result="exit-code", ExecMainStatus="243")
            return self.done(code=1, err=b"Job for lilith-authority-dev.service failed")
        self.run()
        self.invocations = [{"id": SIGNER, "credentials": W.LOADED}]
        if effect == "TWO_LOADS":
            self.invocations = [{"id": "b" * 32, "credentials": W.LOADED}] + self.invocations
            self.units_now[W.SIGNER_SERVICE]["NRestarts"] = "1"
        elif effect == "KEY":
            self.health_value = T.good_health(publicKeySha256="e" * 64)
        elif effect == "WRONG_RELEASE":
            self.cwd = "/opt/lilith-authority-dev/releases/" + "aee323e94412accbe321bc84eae78c5b8cf95afc"
        elif effect == "TRANSPORT_LOST":
            return self.done(code=None)
        return self.done()


class FakeOperator(OP.Operator):
    def bind(self, dev: FakeDev) -> "FakeOperator":
        self.dev = dev
        return self

    def pins(self, repo):
        return {"control": "c" * 40, "operatorSha256": "d" * 64, "tools": dict(OP.TOOL_PINS),
                "result": "MB11_TOOL_PINS_EXACT"}

    def tool_bytes(self, repo, path):
        data = (ROOT / path).read_bytes()
        assert sha(data) == OP.TOOL_PINS[path], path
        return data

    def owner_inputs(self, raw):
        assert raw == ENVELOPE
        return dict(INPUTS)

    def plink_stdin(self, command, data):
        return self.dev.plink(command, data)

    def _invoke(self, command):
        return self.dev.mutation(command)


class OperatorCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.dev = FakeDev(self.base / "host")
        self.op = FakeOperator().bind(self.dev)
        self.work = self.base / "work"
        self.work.mkdir()
        self.envelope = self.base / "inputs.envelope"
        self.envelope.write_bytes(ENVELOPE)

    def gate(self) -> dict:
        return self.op.gate(ROOT, self.work, self.envelope)

    def go(self) -> Path:
        path = self.base / "go.txt"
        path.write_bytes(self.op.render(ROOT, self.work)["text"].encode("ascii"))
        return path

    def start(self, go: Path | None = None) -> dict:
        return self.op.start(ROOT, self.work, go or self.go())

    def marker(self) -> Path:
        return self.work / M6.ATTEMPT_DIR / f"{OP.MARKER}.json"


class GateTests(OperatorCase):
    def test_gate_is_w11_0_on_the_accepted_stopped_host(self):
        report = self.gate()
        self.assertEqual(report["result"], "MB11_GATE_W11_0", report["reasons"])
        self.assertEqual((report["journalCursor"], report["dbSha256"]), (CURSOR, self.dev.db))
        self.assertEqual(self.dev.mutations, [])
        self.assertEqual(self.dev.health_calls, 0)                       # never contacts a stopped signer

    def test_wrong_boundary_unexpected_signer_state_or_witness_is_not_a_gate(self):
        cases = {"boundary": lambda d: setattr(d, "boundary", ["DROPIN_SET_NOT_EXACT"]),
                 "running": lambda d: (d.run(), setattr(d, "invocations", [{"id": SIGNER, "credentials": W.LOADED}])),
                 "loaded_before": lambda d: setattr(d, "invocations", [{"id": SIGNER, "credentials": W.LOADED}]),
                 "witness": lambda d: setattr(d, "witness", ("f" * 32, "1")),
                 "no_cursor": lambda d: setattr(d, "tail", None)}
        for name, change in cases.items():
            with self.subTest(case=name):
                self.setUp()
                change(self.dev)
                report = self.gate()
                self.assertEqual(report["result"], "MB11_GATE_STOP", name)
                with self.assertRaises(OP.Stop):
                    self.op.render(ROOT, self.work)
                self.assertEqual(self.dev.mutations, [])

    @unittest.skipUnless(HAVE_JCS, "mb12_readiness_inputs needs rfc8785")
    def test_owner_inputs_are_required_and_never_defaulted(self):
        op = OP.Operator()
        with self.assertRaises(OP.Stop) as caught:
            op.owner_inputs(b'{"not": "an envelope"}')
        self.assertTrue(caught.exception.code.startswith("OWNER_INPUTS_REFUSED:"))


class StartTests(OperatorCase):
    def test_success_one_start_one_load_w11_1(self):
        self.gate()
        report = self.start()
        self.assertEqual(report["result"], "MB11_START_REACHED_" + OP.W11_1, report)
        self.assertEqual(report["kActLoadCount"], 1)
        self.assertEqual(self.dev.mutations, [OP.START_SIGNER_COMMAND])  # the service path; never the socket, no stop
        self.assertEqual(self.dev.remote_forms, ["gate", "gate", "post"])
        self.assertEqual(self.dev.health_calls, 1)                       # one HEALTH capture, reused for E and F
        self.assertTrue(self.marker().exists())
        record = json.loads((self.work / OP.STEP_DIR / "01-START" / OP.START_FILE).read_bytes())
        self.assertEqual(record["result"], report["result"])

    def test_replay_is_denied_after_the_go_is_consumed(self):
        self.gate()
        go = self.go()
        self.start(go)
        with self.assertRaises(OP.Stop) as caught:
            self.start(go)
        self.assertIn("ATTEMPT_ALREADY_CONSUMED", caught.exception.code)
        with self.assertRaises(OP.Stop):
            self.gate()                                                  # no new gate after a consumed attempt
        self.assertEqual(self.dev.mutations, [OP.START_SIGNER_COMMAND])

    def test_stale_approval_changed_ledger_or_newer_gate_is_refused_before_the_marker(self):
        self.gate()
        go = self.go()
        self.dev.root.joinpath("var/lib/lilith-authority-dev", W.LEDGER_NAME).write_bytes(b"changed")
        with self.assertRaises(OP.Stop):
            self.start(go)
        self.assertFalse(self.marker().exists())
        self.assertEqual(self.dev.mutations, [])
        # a newer gate makes the earlier go non-canonical
        self.setUp()
        self.gate()
        go = self.go()
        self.dev.tail = LATER_CURSOR
        self.gate()
        with self.assertRaises(OP.Stop) as caught:
            self.start(go)
        self.assertEqual(caught.exception.code, "GO_NOT_CANONICAL_FOR_THE_LATEST_GATE")
        self.assertFalse(self.marker().exists())

    def test_a_reworded_or_tampered_go_is_refused(self):
        self.gate()
        go = self.go()
        go.write_bytes(go.read_bytes().replace(b"exactly one invocation", b"one invocation"))
        with self.assertRaises(OP.Stop):
            self.start(go)
        self.assertEqual(self.dev.mutations, [])

    def test_unexpected_state_at_the_fresh_gate_is_refused_before_the_marker(self):
        self.gate()
        go = self.go()
        self.dev.boundary = ["EFFECTIVE_RESTART_NOT_NO"]
        with self.assertRaises(OP.Stop) as caught:
            self.start(go)
        self.assertTrue(caught.exception.code.startswith("FRESH_GATE_NOT_W11_0"))
        self.assertFalse(self.marker().exists())
        self.assertEqual(self.dev.mutations, [])

    def test_failures_after_the_start_stop_without_retry_or_automatic_stop(self):
        expected = {"FAILED": W.W11_CREDENTIAL, "TWO_LOADS": W.W11_RESTART, "KEY": W.W11_KEY,
                    "WRONG_RELEASE": W.W11_UNIT}
        for effect, phase in expected.items():
            with self.subTest(effect=effect):
                self.setUp()
                self.dev.start_effect = effect
                self.gate()
                report = self.start()
                self.assertEqual(report["result"], "MB11_START_STOP:" + phase, report)
                self.assertEqual(self.dev.mutations, [OP.START_SIGNER_COMMAND])     # one invocation, no stop
                self.assertTrue(self.marker().exists())

    def test_a_lost_transport_is_still_one_consumed_attempt_judged_by_the_post(self):
        self.dev.start_effect = "TRANSPORT_LOST"
        self.gate()
        report = self.start()
        self.assertEqual(report["startCode"], None)
        self.assertNotEqual(report["result"], "MB11_START_REACHED_" + OP.W11_1)      # rc unknown is never success
        self.assertEqual(report["postPhase"], OP.W11_1)                  # the host fact is still recorded
        self.assertEqual(self.dev.mutations, [OP.START_SIGNER_COMMAND])

    def test_a_partial_or_unparseable_post_is_unknown(self):
        self.gate()
        original = self.dev.plink

        def broken(command, payload):
            if " post " in command:
                return self.dev.done(out=b'{"remoteType": "LILITH_MB11_START_REMOTE", "form": "post"')
            return original(command, payload)
        self.dev.plink = broken
        report = self.start()
        self.assertEqual(report["result"], "MB11_START_UNKNOWN_POST_NOT_RECEIVED")
        self.assertEqual(self.dev.mutations, [OP.START_SIGNER_COMMAND])

    def test_health_is_never_requested_unless_the_service_runs(self):
        self.dev.start_effect = "FAILED"
        self.gate()
        self.start()
        self.assertEqual(self.dev.health_calls, 0)


@unittest.skipUnless(HAVE_JCS, "mb12_readiness_inputs needs rfc8785")
class CurrentTests(OperatorCase):
    def current(self) -> dict:
        return self.op.current(ROOT, self.work)

    def test_current_is_one_read_only_release_observation_judged_against_the_dev_pins(self):
        report = self.current()
        self.assertEqual(report["result"], "MB11_CURRENT_EXACT", report["reasons"])
        self.assertEqual(report["observation"], good_current())
        self.assertEqual(report["observedAt"], self.dev.clock)
        self.assertEqual(self.dev.remote_forms, ["current"])
        self.assertEqual((self.dev.mutations, self.dev.health_calls), ([], 0))
        out = self.work / OP.CURRENT_DIR / "01-CURRENT"
        self.assertEqual(sha((out / "remote.out").read_bytes()), report["observationSha256"])
        self.assertEqual(json.loads((out / OP.CURRENT_FILE).read_bytes())["result"], "MB11_CURRENT_EXACT")
        self.assertFalse(self.marker().exists())                         # never consumes the start attempt

    def test_current_mismatch_is_a_stop_never_an_input(self):
        cases = {
            "CURRENT_SHA256_NOT_PINNED": lambda d: d.current_doc.update(sha256="0" * 64),
            "CURRENT_NOT_PINNED_SLOT": lambda d: d.current_doc.update(mode="0644"),
            "CURRENT_NOT_ROOT_OWNED": lambda d: d.current_doc.update(uid=995),
            "CURRENT_IDENTITY_MALFORMED": lambda d: d.current_doc.update(inode="01738"),
            "CURRENT_NOT_CANONICAL": lambda d: d.current_doc.update(nlink=1),
            "CURRENT_NOT_AFTER_FRESHNESS_CUTOFF": lambda d: setattr(d, "clock", "2026-10-14T18:26:59Z"),
            "CURRENT_NOT_THE_RELEASE_OBSERVER": lambda d: setattr(d, "current_module", "/tmp/observers.py"),
        }
        for reason, change in cases.items():
            with self.subTest(reason=reason):
                self.setUp()
                change(self.dev)
                report = self.current()
                self.assertEqual(report["result"], "MB11_CURRENT_STOP")
                self.assertIn(reason, report["reasons"])
                self.assertEqual(self.dev.mutations, [])

    def test_a_lost_or_unparseable_current_is_not_received(self):
        self.dev.plink = lambda command, payload: self.dev.done(out=b'{"remoteType": "LILITH_MB11_START_REMOTE"')
        report = self.current()
        self.assertEqual((report["result"], report["reasons"]), ("MB11_CURRENT_STOP", ["CURRENT_NOT_RECEIVED"]))


class RemoteTests(unittest.TestCase):
    def test_evidence_is_exact_and_digest_bound(self):
        doc = {"form": "gate", "expectedHead": "h", "candidateDigest": "d", "updatedAt": "u",
               "witness": list(WITNESS), "ownerInputs": INPUTS}
        self.assertEqual(R.check_evidence(doc, "gate"), doc)
        for bad in ({**doc, "extra": 1}, {**doc, "form": "post"}, {**doc, "witness": ["x"]}):
            with self.assertRaises(R.Refused):
                R.check_evidence(bad, "gate")
        with self.assertRaises(R.Refused):
            R.check_evidence({**doc, "form": "post", "baseline": {"dbSha256": DB}}, "post")
        namespace: dict = {}
        exec(R.evidence_module_source(doc), namespace)                   # noqa: S102
        self.assertEqual(namespace["DOC"], doc)
        self.assertEqual(R.check_evidence({"form": "current"}, "current"), {"form": "current"})
        for bad in ({"form": "current", "ownerInputs": INPUTS}, {"form": "gate"}):
            with self.assertRaises(R.Refused):
                R.check_evidence(bad, "current")

    @unittest.skipUnless(POSIX, "the bundled W10 chain needs POSIX (os.geteuid)")
    def test_the_bundle_runs_under_the_real_boot_loader_and_refuses_off_host(self):
        op = FakeOperator()
        doc = op._doc("gate", dict(INPUTS))
        command, payload = op.bundle(ROOT, doc)
        pins, entry, form, digest = command.split('"')[-1].split()
        raw = base64.b64decode(payload)
        boot = "import base64;exec(base64.b64decode('" + base64.b64encode(M6.BOOT.encode()).decode() + "'))"
        with tempfile.TemporaryDirectory() as empty:
            ok = subprocess.run([sys.executable, "-I", "-B", "-c", boot, pins, entry, form, digest], input=raw,
                                capture_output=True, cwd=empty, timeout=120, check=False)
            wrong = subprocess.run([sys.executable, "-I", "-B", "-c", boot, pins, entry, form, "0" * 64], input=raw,
                                   capture_output=True, cwd=empty, timeout=120, check=False)
        self.assertEqual(ok.returncode, 2, ok.stderr)                    # refused: not root on lilith-dev-01
        self.assertIn(b"mb11_start_remote: REFUSED", ok.stderr)
        self.assertNotIn(b"EVIDENCE", ok.stderr)
        self.assertEqual(wrong.returncode, 2)
        self.assertIn(b"EVIDENCE_DIGEST_MISMATCH", wrong.stderr)         # before any host read
        command, payload = op.bundle(ROOT, {"form": "current"})
        pins, entry, form, digest = command.split('"')[-1].split()
        self.assertEqual(form, "current")
        with tempfile.TemporaryDirectory() as empty:
            refused = subprocess.run([sys.executable, "-I", "-B", "-c", boot, pins, entry, form, digest],
                                     input=base64.b64decode(payload), capture_output=True, cwd=empty, timeout=120,
                                     check=False)
        self.assertEqual(refused.returncode, 2, refused.stderr)          # refused off-host before the observation
        self.assertIn(b"mb11_start_remote: REFUSED", refused.stderr)

    def test_the_remote_never_starts_stops_or_writes(self):
        source = (TOOLS / "mb11_start_remote.py").read_text(encoding="utf-8")
        for needle in ("systemctl", "write_bytes", "write_text", "open(", ".unlink", "daemon-reload", "socket.socket"):
            self.assertNotIn(needle, source.split('"""', 2)[2], needle)


class PinTests(unittest.TestCase):
    def test_every_pinned_tool_is_exact_and_bindings_match_the_accepted_records(self):
        for path, pin in OP.TOOL_PINS.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)
        record = json.loads((ROOT / OP.E19_RECORD).read_bytes())
        self.assertEqual((record["replacementAcceptance"]["invocationId"],
                          record["replacementAcceptance"]["mainPid"]), WITNESS)
        import mb11_restart_boundary_install as RBI
        self.assertEqual((RBI.RELEASE_SHA, W.RELEASE_SHA), (OP.RELEASE, OP.RELEASE))
        self.assertTrue(W.RELEASE_CWD.endswith(OP.RELEASE))
        record_doc = (ROOT / "docs/architecture/slice-15b2b-b1b3e-mb11-p1b10r-owner-acceptance.md").read_text("utf-8")
        self.assertIn(OP.P1B10R_PLAN, record_doc)

    def test_the_only_mutation_is_the_service_start_and_go_lines_survive_normalisation(self):
        source = (TOOLS / "mb11_operator.py").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"systemctl \w+", source), ["systemctl start"] * source.count("systemctl start"))
        self.assertNotIn("lilith-authority-dev.socket", source)
        for line in OP.GO_LINES:
            self.assertNotIn(">", line)
            self.assertTrue(line.isascii())


if __name__ == "__main__":
    unittest.main()
