"""15B2b-B1b-3e M-B12 E-22 operator (V0 … V7): phase transitions, STOP conditions, OD-M12-11 windows, K-ACT count.

Record: docs/architecture/slice-15b2b-b1b3e-e22-judge-transition.md §6. TEST-ONLY: a synthetic DEV behind the
operator's transport seams runs the REAL E-22 host tail (`e22_transition_remote.run_form`), the REAL M-B11 host tail and
the REAL W11 verifier over synthetic signer facts, and the REAL pure V-phase judge (`e22_release_stages.phase`) over
synthetic `e22-status` reports. Nothing here contacts DEV, runs systemctl, opens a socket or loads a credential.
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
import types
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _p in (TOOLS, HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import e22_judge_upgrade as J  # noqa: E402
import e22_operator as OP  # noqa: E402
import e22_transition_remote as Q  # noqa: E402
import mb11_operator as M11  # noqa: E402
import mb11_signer_verifier as W  # noqa: E402
import mb6_operator as M6  # noqa: E402
import test_b1b3e_mb11_signer_start as T  # noqa: E402  (helpers only: exact HEALTH / readiness / unit facts)

S22 = OP.stages_module()
HAVE_DEPS = all(importlib.util.find_spec(m) is not None for m in ("rfc8785", "cryptography"))
OLD, NEW, MANIFEST = J.OLD_RELEASE, "e22" + "1" * 37, "9" * 64
ENDING_SIGNER, ENDING_WITNESS = J.ENDING_SIGNER_INCARNATION, J.ENDING_WITNESS_INCARNATION
NEW_WITNESS, NEW_SIGNER = ("6" * 32, "4343"), ("5" * 32, "4242")
ENVELOPE = b'{"envelopeType":"SYNTHETIC"}\n'
INPUTS = {"synthetic": "owner inputs (TEST)"}
BOOT = "b" * 32
DENIAL_LINES = {"P1B-9b": b"MB9_WITNESS_DENIAL_PROOF=PASS phase=P1B-9b denied=3 allowed_by_design=1 allowed=0\n",
                "P1B-10": b"MB10_HOLD_DENIAL_PROOF=PASS phase=P1B-10 denied=2 allowed=0\n",
                "P1B-5": b"AUTHORITY_CUSTODY_DENIAL_PROOF=PASS phase=P1B-5\n"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def done(code=0, out=b"", err=b""):
    return subprocess.CompletedProcess([], code, out, err)


class Dev:
    """Synthetic DEV: the release layout, the signer and witness units and the journal, moved exactly as each
    reviewed command would move them (or as the chosen failure would)."""

    def __init__(self, root: Path):
        self.root, self.seq, self.boot = root, 1, BOOT
        self.releases, self.selector = ["OLD"], "OLD"
        self.signer = {"id": ENDING_SIGNER, "release": "OLD", "restarts": "0"}      # None = stopped
        self.witness = {"id": ENDING_WITNESS, "release": "OLD"}
        self.signer_loads, self.witness_loads = [(1, ENDING_SIGNER[0])], []
        self.mutations: list[str] = []
        self.effect: dict[str, str] = {}
        self.denials = dict(DENIAL_LINES)
        ledger = root / "var/lib/lilith-authority-dev"
        ledger.mkdir(parents=True)
        (ledger / W.LEDGER_NAME).write_bytes(b"synthetic ledger bytes")
        self.db = sha(b"synthetic ledger bytes")

    def cursor(self) -> str:
        return f"s=e22;i={self.seq:x}"

    def after(self, loads, cursor):
        n = int(cursor.rsplit("i=", 1)[1], 16)
        return {"readable": True, "invocations": [{"id": i, "credentials": W.LOADED} for s, i in loads if s > n]}

    # ---- e22-status (synthetic report; the V-phase is the REAL pure judge) ----
    def status(self) -> dict:
        rel = {"OLD": OLD, "NEW": NEW}
        state = {(("OLD",), "OLD"): S22.OLD_ONLY, (("NEW", "OLD"), "OLD"): S22.STAGED,
                 (("NEW", "OLD"), "NEW"): S22.SELECTED, (("NEW",), "NEW"): S22.RETIRED}.get(
            (tuple(sorted(self.releases)), self.selector), S22.INCONSISTENT)

        def unit(proc):
            if proc is None:
                return {"ActiveState": "inactive", "SubState": "dead", "MainPID": "0", "InvocationID": "",
                        "NRestarts": "0"}
            return {"ActiveState": "active", "SubState": "running", "MainPID": proc["id"][1],
                    "InvocationID": proc["id"][0], "NRestarts": proc.get("restarts", "0")}

        report = {"schemaVersion": 1, "mode": J.MODE, "oldRelease": OLD, "newRelease": NEW, "state": state,
                  "currentTarget": f"releases/{rel[self.selector]}", "failures": [],
                  "signer": "STOPPED" if self.signer is None else "RUNNING",
                  "witness": "STOPPED" if self.witness is None else "RUNNING",
                  "units": {S22.SIGNER_SERVICE: unit(self.signer), S22.SIGNER_SOCKET: unit(self.signer),
                            S22.WITNESS_SERVICE: unit(self.witness)},
                  "signerCwd": None if self.signer is None else f"{S22.I.RELEASES}/{rel[self.signer['release']]}",
                  "witnessCwd": None if self.witness is None else f"{S22.I.RELEASES}/{rel[self.witness['release']]}",
                  "result": "PASS" if state != S22.INCONSISTENT else "FAIL"}
        report["phase"] = S22.phase(report)
        return report

    # ---- signer facts for the W11 verifier ----
    def units(self, names):
        units = T.stopped_units() if self.signer is None else T.running_units()
        if self.signer is not None:
            units[W.SIGNER_SERVICE].update(InvocationID=self.signer["id"][0], MainPID=self.signer["id"][1],
                                           NRestarts=self.signer["restarts"])
        for name in W.SIGNER_UNITS:
            units[name].update(FragmentPath=f"/etc/systemd/system/{name}")
        return {name: units[name] for name in names if name in units}

    def path_facts(self, path, *, names=False):
        if self.signer is None:
            return {"present": False}
        if "credentials" in str(path):
            return {"present": True, "kind": "dir", "uid": 995, "gid": 985, "mode": 0o500, "names": [W.CREDENTIAL_NAME]}
        return {"present": True, "kind": "socket", "uid": 0, "gid": 0, "mode": 0o600}

    def process(self, _root, pid):
        if self.signer is None or pid != self.signer["id"][1]:
            return None
        sha_ = {"OLD": OLD, "NEW": NEW}[self.signer["release"]]
        return {"cwd": "/opt/lilith-authority-dev/releases/" + sha_, "argv": list(W.EXEC_ARGV), "uid": 995, "gid": 985}

    def w10(self, head, candidate, updated, *, root, units, **_seams):
        import mb6_ledger_verifier as V6

        V6._lstat(W._host(root, W.SIGNER_CREDENTIALS))                      # the signer side the W11 mask judges
        V6._lstat(W._host(root, W.SIGNER_OWNER_SOCKET))
        view = units(list(W.SIGNER_UNITS))
        if self.witness is None:
            return {"phase": "W10_1S_HELD_EXACT_WITNESS_STOPPED", "holdClass": "HELD_EXACT", "w9Failures": [],
                    "failures": []}
        running = view[W.SIGNER_SERVICE]["ActiveState"] == "active"
        return {"phase": "W10_SIGNER_OR_LATER_STATE" if running else W.W10_1, "holdClass": "HELD_EXACT",
                "witnessInvocationId": self.witness["id"][0], "witnessMainPid": self.witness["id"][1],
                "w9Failures": [], "failures": []}

    def health(self):
        assert self.signer is not None, "HEALTH contacted while the service is not running"
        return T.good_health()

    def e22_remote(self, doc):
        with mock.patch.object(W, "_path_facts", self.path_facts):
            return Q.run_form(doc, root=self.root, W=W, tail=self.cursor, boot=lambda: self.boot,
                              clock=lambda: "2026-10-19T08:00:00Z",
                              kact=lambda c: self.after(self.signer_loads, c),
                              kwit=lambda c: self.after(self.witness_loads, c),
                              units=self.units, health=self.health, ids=lambda: [995, 985],
                              journal=lambda c: self.after(self.signer_loads, c), process=self.process, w10=self.w10,
                              readiness=lambda _o, h, **_k: T.good_readiness() if h is not None else
                              {"eligibility": {"status": "NOT_READY"}, "full": {"status": "NOT_READY"}},
                              restart_boundary=lambda _r, _u: {"reasons": []},
                              evaluate=self.evaluate)

    def evaluate(self, document, frame):
        """The release verifier's eligibility report (synthetic), only ever called with a captured HEALTH frame."""
        assert frame == T.good_health() and document == INPUTS
        return {"mode": "HOLD_RELEASE_ELIGIBILITY", "status": "READY", "reasons": [], "packageDigest": "f" * 64,
                "package": {"status": "READY"}, "authorityGranted": False}

    # ---- the transport ----
    def plink(self, command: str, payload: bytes):
        match = re.search(r"grep -qx '([0-9a-f]{64})'.*sudo -n (\S+) -I -B -c \"[^\"]+\" (\S+) (\S+) (.*)\Z", command)
        assert match is not None, command
        digest, interpreter, pins, entry, rest = match.groups()
        assert sha(payload.rstrip(b"\n")) == digest
        sources = json.loads(gzip.decompress(base64.b64decode(payload)))
        declared = dict(item.split("=", 1) for item in pins.split(","))
        assert list(sources) == list(declared) and all(sha(s.encode()) == declared[n] for n, s in sources.items())
        assert list(sources)[-1] == entry
        args = rest.split()
        if entry == "e22_release_stages":
            assert interpreter == OP.M9.SYSTEM_PYTHON and list(sources) == [Path(p).stem for p in OP.STAGES_BUNDLE]
            if args[0] != "e22-status":
                self.stage(args)
            return done(out=json.dumps(self.status()).encode())
        assert entry == "e22_transition_remote" and interpreter == OP.M9.RELEASE_PYTHON
        assert list(sources)[-2] == Q.EVIDENCE_MODULE
        namespace: dict = {}
        exec(sources[Q.EVIDENCE_MODULE], namespace)                       # noqa: S102 - the generated data module
        doc = Q.check_evidence(namespace["DOC"], args[0])
        assert Q.evidence_digest(doc) == args[1]
        if doc["form"] == "window" and doc["label"].endswith("CLOSE") and self.effect.get("WINDOW") == "REBOOT":
            self.boot = "d" * 32
        return done(out=json.dumps(self.e22_remote(doc), default=str).encode())

    def stage(self, args):
        self.mutations.append(args[0])
        if args[0] == "e22-stage":
            assert args[1:4] == [OLD, NEW, MANIFEST]
            self.releases.append("NEW")
        elif args[0] == "e22-select":
            self.selector = "NEW"
        else:
            assert args[0] == "e22-retire-old" and args[1:3] == [OLD, NEW]
            self.releases.remove("OLD")

    def ssh(self, command: str):
        proof = command.rsplit(" ", 1)[1]
        return done(out=self.denials[proof])

    def invoke(self, command: str):
        self.mutations.append(command)
        if command == OP.SIGNER_STOP_COMMAND:
            self.signer = None
        elif command == OP.WITNESS_STOP_COMMAND:
            self.witness = None
        elif command == OP.WITNESS_START_COMMAND:
            self.seq += 1
            self.witness = {"id": NEW_WITNESS, "release": self.selector}
            self.witness_loads.append((self.seq, NEW_WITNESS[0]))
            if self.effect.get("WITNESS") == "TWO_LOADS":
                self.seq += 1
                self.witness_loads.append((self.seq, NEW_WITNESS[0][:-1] + "7"))
        elif command == OP.SIGNER_START_COMMAND:
            if self.effect.get("SIGNER") == "TWO_LOADS":
                self.seq += 1
                self.signer_loads.append((self.seq, "8" * 32))
            self.seq += 1
            self.signer = {"id": NEW_SIGNER, "release": self.selector, "restarts": "0"}
            self.signer_loads.append((self.seq, NEW_SIGNER[0]))
        else:
            raise AssertionError(command)
        return done()


TOOL_BYTES: dict[str, bytes] = {}


class FakeOperator(OP.Operator):
    def attach(self, dev: Dev) -> "FakeOperator":
        self.dev = dev
        return self

    def pins(self, repo):
        return {"control": "c" * 40, "operatorSha256": "d" * 64, "tools": dict(OP.TOOL_PINS),
                "result": "E22_TOOL_PINS_EXACT"}

    def tool_bytes(self, repo, path):
        if path not in TOOL_BYTES:
            TOOL_BYTES[path] = (ROOT / path).read_bytes()
        assert sha(TOOL_BYTES[path]) == OP.TOOL_PINS[path], path
        return TOOL_BYTES[path]

    def owner_inputs(self, raw):
        assert raw == ENVELOPE
        return dict(INPUTS)

    def plink_stdin(self, command, data):
        return self.dev.plink(command, data)

    def _invoke(self, command):
        return self.dev.invoke(command)

    def ssh(self, command):
        return self.dev.ssh(command)


def write_mb11_workdir(work: Path, dev: Dev) -> None:
    """The accepted M-B11 start as `mb11_operator` left it: gate W11_0, the consumed marker, START W11_1, POST11."""
    gate_cursor = "s=e22;i=0"
    gate = work / M11.GATE_DIR / "01-GATE"
    gate.mkdir(parents=True)
    (gate / "remote.out").write_bytes(b"{}\n")
    (gate / M11.ENVELOPE_FILE).write_bytes(ENVELOPE)
    (gate / M11.GATE_FILE).write_text(json.dumps({
        "result": "MB11_GATE_W11_0", "reasons": [], "observationSha256": sha(b"{}\n"),
        "envelopeSha256": sha(ENVELOPE), "journalCursor": gate_cursor, "dbSha256": dev.db}), encoding="ascii")
    doc = M11.Operator._doc(None, "post", dict(INPUTS), {"dbSha256": dev.db, "journalCursor": gate_cursor})
    with mock.patch.object(W, "_path_facts", dev.path_facts):
        post = M11.R.run_form(doc, root=dev.root, W=W, units=dev.units, health=dev.health, ids=lambda: [995, 985],
                              journal=lambda c: dev.after(dev.signer_loads, c), process=dev.process, w10=dev.w10,
                              readiness=lambda *_a, **_k: T.good_readiness(),
                              restart_boundary=lambda _r, _u: {"reasons": []})
    assert post["report"]["phase"] == W.W11_1, post["report"]["reasons"]
    raw = json.dumps(post, default=str).encode()
    start = work / M11.STEP_DIR / "01-START"
    start.mkdir(parents=True)
    (start / "post.out").write_bytes(raw)
    (start / M11.START_FILE).write_text(json.dumps({
        "result": "MB11_START_REACHED_" + W.W11_1, "kActLoadCount": 1, "postSha256": sha(raw), "gate": gate.name,
        "goSha256": "e" * 64}), encoding="ascii")
    (work / M6.ATTEMPT_DIR).mkdir()
    (work / M6.ATTEMPT_DIR / f"{M11.MARKER}.json").write_text("{}\n", encoding="ascii")


class Case(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.dev = Dev(self.base / "host")
        self.op = FakeOperator(new_release=NEW, new_manifest=MANIFEST).attach(self.dev)
        self.work, mb11 = self.base / "e22", self.base / "mb11"
        write_mb11_workdir(mb11, self.dev)
        self.envelope = self.base / "inputs.envelope"
        self.envelope.write_bytes(ENVELOPE)
        self.op.bind(ROOT, self.work, mb11)

    def text(self, what: str) -> Path:
        path = self.base / f"{what}.txt"
        path.write_bytes(self.op.render(ROOT, self.work, what)["text"].encode("ascii"))
        return path

    def step(self, form: str, label: str | None = None) -> dict:
        step, pre, _post, _marker = OP.STEPS[form]
        self.assertEqual(self.op.status(ROOT, self.work, label or step)["phase"], pre)
        return self.op._step(ROOT, self.work, step, self.text(step))

    def marker(self, form: str) -> Path:
        return self.work / M6.ATTEMPT_DIR / f"{OP.STEPS[form][3]}.json"

    def to_v5(self) -> None:
        self.assertEqual(self.op.v0(ROOT, self.work)["result"], "E22_V0_EXACT")
        for form in ("stage", "stop-signer", "stop-witness", "select", "start-witness"):
            report = self.step(form)
            self.assertTrue(report["result"].endswith("REACHED_" + OP.STEPS[form][2]), report)

    def accept(self, kind: str) -> dict:
        return getattr(self.op, f"accept_{kind.lower()}")(ROOT, self.work, self.text("ACCEPT_" + kind))

    def to_v6(self) -> None:
        self.to_v5()
        self.assertEqual(self.op.post_witness(ROOT, self.work, self.envelope)["result"], "E22_WITNESS_POST_VERIFIED")
        self.accept("WITNESS")
        self.assertEqual(self.step("start-signer")["result"], "E22_SIGNER_START_REACHED_" + J.V6)


class TransitionTests(Case):
    def test_v0_to_v7_each_mutation_once_in_order_kact_count_two(self):
        self.to_v6()
        post = self.op.post_signer(ROOT, self.work, self.envelope)
        self.assertEqual(post["result"], "E22_SIGNER_POST_VERIFIED", post["reasons"])
        self.assertEqual((post["kActLoadCount"], post["invocationId"]), (2, NEW_SIGNER[0]))
        self.accept("SIGNER")
        self.assertEqual(self.step("retire")["result"], "E22_RETIRE_REACHED_" + J.V7)
        self.assertEqual(self.dev.mutations, ["e22-stage", OP.SIGNER_STOP_COMMAND, OP.WITNESS_STOP_COMMAND,
                                              "e22-select", OP.WITNESS_START_COMMAND, OP.SIGNER_START_COMMAND,
                                              "e22-retire-old"])
        self.assertEqual([s for s, _ in self.dev.signer_loads], [1, self.dev.seq])          # two K-ACT loads ever
        windows = self.op.windows(ROOT, self.work)
        self.assertEqual(set(windows["windows"]), {"K-WIT", "K-ACT"})
        self.assertEqual((windows["readsBootId"], windows["kActLoadCount"]), (BOOT, 2))
        step_dir = next((self.work / OP.STEP_DIR).glob("*-SIGNER_START"))
        window = json.loads((step_dir / OP.WINDOW_FILE).read_bytes())
        self.assertEqual(set(window["transcript"]), {f"{n}.{x}" for n in ("window-open", "e22-signer-start",
                                                                            "window-close") for x in ("out", "err", "rc")})
        self.assertFalse(window["joinsCeremoniesTable"])

    def test_go_texts_name_the_exact_commands_and_bind_the_accepted_replacements(self):
        self.to_v6()
        self.op.post_signer(ROOT, self.work, self.envelope)
        self.accept("SIGNER")
        self.op.status(ROOT, self.work, "R")
        text = self.op.render(ROOT, self.work, "RETIRE")["text"]
        self.assertIn(f"signer {NEW_SIGNER[0]} and witness {NEW_WITNESS[0]}", text)
        self.assertIn(J.SIGNER_STOP_COMMAND, OP.GO_LINES["SIGNER_STOP"][0])


class StopTests(Case):
    def test_out_of_order_step_is_refused_before_any_marker(self):
        self.op.v0(ROOT, self.work)
        self.op.status(ROOT, self.work, "X")
        for step in ("SELECT", "SIGNER_STOP", "WITNESS_START", "RETIRE"):
            with self.subTest(step=step), self.assertRaises(OP.Stop):
                self.op.render(ROOT, self.work, step)
        self.assertEqual(self.dev.mutations, [])
        self.assertFalse((self.work / M6.ATTEMPT_DIR).exists())

    def test_replay_and_tampered_go_are_refused(self):
        self.op.v0(ROOT, self.work)
        self.op.status(ROOT, self.work, "S")
        go = self.text("STAGE")
        tampered = self.base / "tampered.txt"
        tampered.write_bytes(go.read_bytes().replace(b"exactly one", b"one"))
        with self.assertRaises(OP.Stop):
            self.op._step(ROOT, self.work, "STAGE", tampered)
        self.op._step(ROOT, self.work, "STAGE", go)
        with self.assertRaises(OP.Stop):
            self.op._step(ROOT, self.work, "STAGE", go)                    # latest status is now V1, marker consumed
        self.assertEqual(self.dev.mutations, ["e22-stage"])

    def test_host_changed_since_the_go_is_refused_at_the_fresh_gate(self):
        self.op.v0(ROOT, self.work)
        self.step("stage")
        self.op.status(ROOT, self.work, "G")
        go = self.text("SIGNER_STOP")
        self.dev.signer = None                                             # stopped outside the operator
        with self.assertRaises(OP.Stop) as caught:
            self.op._step(ROOT, self.work, "SIGNER_STOP", go)
        self.assertTrue(caught.exception.code.startswith("GATE_NOT_" + J.V1))
        self.assertFalse(self.marker("stop-signer").exists())
        self.assertEqual(self.dev.mutations, ["e22-stage"])

    def test_unit_running_from_old_after_select_is_a_stop_phase(self):
        self.op.v0(ROOT, self.work)
        self.step("stage")
        self.dev.selector = "NEW"                                          # select with both units still running
        self.assertEqual(self.op.status(ROOT, self.work, "V")["phase"], S22.STOP_ACROSS_SELECT)
        with self.assertRaises(OP.Stop):
            self.op.render(ROOT, self.work, "SIGNER_STOP")

    def test_new_release_not_established_refuses_every_dev_form(self):
        op = FakeOperator(new_release=None, new_manifest=None).attach(self.dev)
        self.assertEqual((FakeOperator().new_release, FakeOperator().new_manifest),
                         (J.NEW_RELEASE, J.NEW_MANIFEST_SHA256))                 # the merged pins (the attested NEW)
        for call in (lambda: op.status(ROOT, self.work, "N"), lambda: op.v0(ROOT, self.work)):
            with self.assertRaises(OP.Stop) as caught:
                call()
            self.assertEqual(caught.exception.code, "NEW_RELEASE_NOT_ESTABLISHED")

    def test_signer_start_needs_the_witness_acceptance(self):
        self.to_v5()
        self.assertEqual(self.op.post_witness(ROOT, self.work, self.envelope)["result"], "E22_WITNESS_POST_VERIFIED")
        self.op.status(ROOT, self.work, "A")
        with self.assertRaises(OP.Stop) as caught:
            self.op.render(ROOT, self.work, "SIGNER_START")
        self.assertEqual(caught.exception.code, "WITNESS_ACCEPTANCE_REQUIRED")
        statement = self.base / "bad.txt"
        statement.write_bytes(self.op.render(ROOT, self.work, "ACCEPT_WITNESS")["text"].replace("only", "").encode())
        with self.assertRaises(OP.Stop):
            self.op.accept_witness(ROOT, self.work, statement)

    def test_a_reboot_inside_the_window_is_a_stop(self):
        self.op.v0(ROOT, self.work)
        for form in ("stage", "stop-signer", "stop-witness", "select"):
            self.step(form)
        self.dev.effect["WINDOW"] = "REBOOT"
        self.assertEqual(self.step("start-witness")["result"], "E22_WITNESS_START_STOP")
        with self.assertRaises(OP.Stop) as caught:
            self.op.post_witness(ROOT, self.work, self.envelope)
        self.assertIn("STEP_NOT_REACHED", caught.exception.code)


class LoadCountTests(Case):
    def test_second_kact_load_is_counted_from_the_journal_and_an_extra_one_stops(self):
        self.to_v5()
        self.op.post_witness(ROOT, self.work, self.envelope)
        self.accept("WITNESS")
        self.dev.effect["SIGNER"] = "TWO_LOADS"
        self.step("start-signer")
        post = self.op.post_signer(ROOT, self.work, self.envelope)
        self.assertEqual(post["result"], "E22_SIGNER_POST_STOP")
        self.assertEqual(post["kActLoadCount"], 3)
        self.assertTrue(any(r.startswith(("KACT_LOADS_NOT_EXACTLY_2", "W11_NOT_ONE")) for r in post["reasons"]))
        with self.assertRaises(OP.Stop):
            self.op.render(ROOT, self.work, "ACCEPT_SIGNER")

    def test_v0_needs_exactly_the_mb11_load(self):
        self.dev.signer_loads.append((2, "8" * 32))
        self.dev.seq = 2
        report = self.op.v0(ROOT, self.work)
        self.assertEqual(report["result"], "E22_V0_STOP")
        self.op.status(ROOT, self.work, "S")
        with self.assertRaises(OP.Stop) as caught:
            self.op.render(ROOT, self.work, "STAGE")
        self.assertEqual(caught.exception.code, "LATEST_V0_NOT_EXACT")

    def test_witness_post_needs_one_kwit_load_the_stopped_signer_and_passing_denials(self):
        cases = {"two_kwit": lambda d: d.effect.update(WITNESS="TWO_LOADS"),
                 "denial": lambda d: d.denials.update({"P1B-10": b"MB10_HOLD_DENIAL_PROOF=FAIL\n"})}
        for name, change in cases.items():
            with self.subTest(case=name):
                self.setUp()
                change(self.dev)
                self.to_v5()
                post = self.op.post_witness(ROOT, self.work, self.envelope)
                self.assertEqual(post["result"], "E22_WITNESS_POST_STOP", name)
                with self.assertRaises(OP.Stop):
                    self.op.render(ROOT, self.work, "ACCEPT_WITNESS")


class ImportPathTests(unittest.TestCase):
    @unittest.skipUnless(HAVE_DEPS, "the owner-inputs reader needs rfc8785 and cryptography")
    def test_the_owner_inputs_reader_loads_without_pythonpath(self):
        """The first live `v0` failed here (ModuleNotFoundError: lilith_memory) with only the tools dir on the path."""
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        outside = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep)      # third-party deps only
                   if p and ROOT not in Path(p).resolve().parents and Path(p).resolve() != ROOT]
        code = ("import sys, e22_operator as O; O.Operator().readiness_tool(); "
                "print(sys.path.index(str(O.HERE)) < sys.path.index(str(O.HERE.parents[1] / 'core-api')))")
        with tempfile.TemporaryDirectory() as cwd:
            out = subprocess.run([sys.executable, "-B", "-c", code], cwd=cwd, env={**env, "PYTHONPATH": os.pathsep.join([str(TOOLS), *outside])},
                                 capture_output=True, text=True, timeout=120)
        self.assertEqual((out.returncode, out.stdout.strip()), (0, "True"), out.stderr[-2000:])


class PackageTests(Case):
    def test_package_returns_the_verifier_report_only_from_a_running_signer(self):
        out = self.base / "package"
        report = self.op.package(ROOT, out, self.envelope)
        self.assertEqual((report["result"], report["status"], report["packageDigest"]),
                         ("E22_PACKAGE_READY", "READY", "f" * 64))
        self.assertTrue((out / "PACKAGE.json").is_file())
        self.assertEqual(self.dev.mutations, [])                          # read-only
        with self.assertRaises(OP.Stop):
            self.op.package(ROOT, out, self.envelope)                     # never overwrites evidence
        self.dev.signer = None                                            # no HEALTH frame -> nothing evaluated
        stopped = self.op.package(ROOT, self.base / "package-stopped", self.envelope)
        self.assertEqual((stopped["result"], stopped["packageDigest"]), ("E22_PACKAGE_NOT_EVALUATED", None))

    def test_package_evidence_is_closed(self):
        with self.assertRaises(Q.Refused):
            Q.check_evidence({"form": "package", "ownerInputs": {}, "extra": 1}, "package")
        with self.assertRaises(Q.Refused):
            Q.check_evidence({"form": "package", "ownerInputs": "x"}, "package")


class RemoteAndPinTests(unittest.TestCase):
    def test_remote_evidence_is_closed_and_the_release_binding_is_restored(self):
        with self.assertRaises(Q.Refused):
            Q.check_evidence({"form": "window", "label": "V7_OPEN"}, "window")
        with self.assertRaises(Q.Refused):
            Q.check_evidence({"form": "window", "label": "V5_OPEN", "extra": 1}, "window")
        before = W.RELEASE_CWD
        with self.assertRaises(RuntimeError), Q.release_of_phase(W, NEW):
            self.assertEqual(W.RELEASE_CWD, Q.RELEASES + NEW)
            raise RuntimeError
        self.assertEqual(W.RELEASE_CWD, before)

    def test_tool_pins_are_the_tree_bytes(self):
        for path, pin in OP.TOOL_PINS.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)

    def test_bundled_contract_never_puts_the_remote_cwd_on_sys_path(self):
        source = (TOOLS / "e22_judge_upgrade.py").read_text(encoding="utf-8")
        module = types.ModuleType("e22_judge_upgrade_bundled")
        module.__file__ = "<mb6-bundle:e22_judge_upgrade>"
        before = list(sys.path)
        exec(compile(source, module.__file__, "exec"), module.__dict__)  # noqa: S102 - the reviewed source
        self.assertEqual(sys.path, before)


if __name__ == "__main__":
    unittest.main()
