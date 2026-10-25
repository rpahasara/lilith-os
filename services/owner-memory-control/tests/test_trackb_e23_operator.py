"""Track B E-23 operator (E0 … E8): the mocked transition rehearsal and its STOP conditions.

Record: docs/architecture/trackb-e23-transition.md. TEST-ONLY: the operator's transport seams deliver every BOOT
bundle (digest and per-module pins checked) to the REAL `e23_release_stages` running against the fake-systemd host of
`test_trackb_e23_release_stages`, and every reviewed unit command to that host's units. Nothing contacts DEV, runs
systemctl, opens a socket or touches a credential.
"""

from __future__ import annotations

import base64
import contextlib
import gzip
import hashlib
import json
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

import e23_operator as OP  # noqa: E402
import test_trackb_e23_release_stages as H  # noqa: E402  (the fake-systemd host and fixtures)
from test_trackb_e23_release_stages import E23, I, IL, S, T19  # noqa: E402

OLD, NEW = H.OLD, H.NEW
NEW_SIGNER, NEW_WITNESS = H.SIGNER_REPLACEMENT, H.WITNESS_REPLACEMENT


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def done(code=0, out=b"", err=b""):
    return subprocess.CompletedProcess([], code, out, err)


class Dev:
    """lilith-dev-01, synthetic: the fake-systemd host; bundles run the real stage tool, plain commands move units."""

    def __init__(self, host: H.E23Host, archive: Path, stamp: Path):
        self.host, self.system, self.archive, self.stamp = host, host.system(), archive, stamp
        self.mutations: list[str] = []
        self.effect: dict[str, str] = {}

    def plink(self, command: str, payload: bytes):
        match = re.search(r"grep -qx '([0-9a-f]{64})'.*sudo -n (\S+) -I -B -c \"[^\"]+\" (\S+) (\S+) (.*)\Z", command)
        assert match is not None, command
        digest, interpreter, pins, entry, rest = match.groups()
        assert sha(payload.rstrip(b"\n")) == digest
        sources = json.loads(gzip.decompress(base64.b64decode(payload)))
        declared = dict(item.split("=", 1) for item in pins.split(","))
        assert list(sources) == list(declared) and all(sha(s.encode()) == declared[n] for n, s in sources.items())
        assert entry == "e23_release_stages" and interpreter == OP.M9.SYSTEM_PYTHON
        assert list(sources) == [Path(p).stem for p in OP.STAGES_BUNDLE]
        args = rest.split()
        if args[0] != "e23-status":
            self.mutations.append(args[0])
        try:
            report = self.run_form(args)
        except I.InstallError as exc:
            return done(2, err=f"e23_release_stages: REFUSED {exc.reason}\n".encode())
        return done(0 if report["result"] == "PASS" else 1, out=json.dumps(report).encode())

    def run_form(self, args):
        status = self.host.status
        assert args[1:3] == [OLD, NEW], args
        if args[0] == "e23-status":
            return S.e23_status(self.system, OLD, NEW, status=status)
        if args[0] == "e23-stage":
            assert args[4:] == [f"{OP.TRANSFER_DIR}/release-{NEW}.tar.gz", f"{OP.TRANSFER_DIR}/release-{NEW}.json"]
            return S.stage_e23_stage(self.system, OLD, NEW, args[3], self.archive, self.stamp, status=status)
        if args[0] == "e23-select":
            return S.stage_e23_select(self.system, OLD, NEW, status=status)
        if args[0] == "e23-witness-units":
            return S.stage_e23_witness_units(self.system, OLD, NEW, status=status)
        assert args[0] == "e23-retire-old"
        return S.stage_e23_retire_old(self.system, OLD, NEW, args[3], args[4], status=status)

    def selected(self) -> str:
        return (self.host.root / "opt/lilith-authority-dev/current").readlink().name

    def invoke(self, command: str):
        self.mutations.append(command)
        if command == OP.SIGNER_STOP_COMMAND:
            self.host.signer_stopped()
        elif command == OP.WITNESS_STOP_COMMAND:
            self.host.stopped()
        elif command == OP.WITNESS_START_COMMAND:
            if not self.host.p(S.KPAN_BLOB).exists() and self.host.loaded == E23.PAYLOAD_DELTA[
                    "assets/lilith-recovery-witness.service"][1]:
                self.host.units[S.WITNESS_SERVICE].update(ActiveState="failed", SubState="failed")   # credential
                return done(1, err=b"Job for lilith-recovery-witness.service failed.\n")
            self.host.running(NEW_WITNESS, self.selected())
            if self.effect.get("WITNESS_START") == "ACTIVATING":                 # exit 0, unit never settled
                self.host.units[S.WITNESS_SERVICE].update(ActiveState="activating", SubState="start")
        elif command == OP.SIGNER_START_COMMAND:
            self.host.signer_running(NEW_SIGNER, self.selected())
        else:
            raise AssertionError(command)
        return done()


class FakeOperator(OP.Operator):
    def attach(self, dev: Dev) -> "FakeOperator":
        self.dev = dev
        return self

    def pins(self, repo):
        return {"control": "c" * 40, "operatorSha256": "d" * 64, "tools": dict(OP.ALL_PINS),
                "result": "E23_TOOL_PINS_EXACT"}

    def tool_bytes(self, repo, path):
        data = (ROOT / path).read_bytes()
        assert sha(data) == OP.ALL_PINS[path], path
        return data

    def plink_stdin(self, command, data):
        return self.dev.plink(command, data)

    def _invoke(self, command):
        return self.dev.invoke(command)

    def ssh(self, command):
        raise AssertionError("no other remote route: " + command)


@unittest.skipUnless(T19.POSIX, "release trees need POSIX modes and symlinks")
class Rehearsal(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        house = stack.enter_context(T19.stand_in_wheels())
        self.root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        self.work = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        out = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        new_payloads = IL._build_v2(ROOT, house)
        self.host = H.E23Host(self.root, IL.installed_layout(new_payloads))
        with S.layout_v2():
            archive, stamp, self.manifest = T19.archive_for(out, NEW, new_payloads)
        stack.enter_context(mock.patch.object(E23, "NEW_RELEASE", NEW))
        stack.enter_context(mock.patch.object(E23, "NEW_MANIFEST_SHA256", self.manifest))
        self.dev = Dev(self.host, archive, stamp)
        self.op = FakeOperator(new_release=NEW, new_manifest=self.manifest).attach(self.dev)
        self.repo = Path("repo")

    def go(self, step: str) -> Path:
        path = self.work / f"go-{step}.txt"
        path.write_bytes(self.op.render(self.repo, self.work, step)["text"].encode("ascii"))
        return path

    def run_step(self, step: str) -> dict:
        self.op.status(self.repo, self.work, step + "_GATE")
        return self.op._step(self.repo, self.work, step, self.go(step))

    def accept(self, kind: str) -> dict:
        verified = self.op.verify(self.repo, self.work, kind)
        self.assertEqual(verified["result"], f"E23_{kind}_VERIFIED", verified["reasons"])
        statement = self.work / f"accept-{kind}.txt"
        statement.write_bytes(self.op.render(self.repo, self.work, "ACCEPT_" + kind)["text"].encode("ascii"))
        return self.op._accept(self.repo, self.work, kind, statement)

    def stop(self, reason: str, call, *args):
        with self.assertRaises(OP.Stop) as caught:
            call(*args)
        self.assertTrue(str(caught.exception).startswith(reason) or reason in str(caught.exception),
                        str(caught.exception))

    def to(self, last: str) -> None:
        self.assertEqual(self.op.preflight(self.repo, self.work)["result"], "E23_PREFLIGHT_EXACT")
        for step in OP.ORDER[:OP.ORDER.index(last) + 1]:
            if step == "WITNESS_UNITS":
                self.host.keygen()
            if step == "SIGNER_START":
                self.accept("WITNESS")
            if step == "RETIRE":
                self.accept("SIGNER")
            self.assertTrue(self.run_step(step)["result"].startswith(f"E23_{step}_REACHED"), step)

    def test_the_full_mocked_transition_e0_to_e8(self):
        preflight = self.op.preflight(self.repo, self.work)
        self.assertEqual((preflight["result"], preflight["kPan"]), ("E23_PREFLIGHT_EXACT", "ABSENT"))
        self.assertIn("K-PAN credential first", preflight["next"])
        phases = [OP.E0]
        for step in OP.ORDER:
            if step == "WITNESS_UNITS":
                self.host.keygen()                                     # the separately authorized K-PAN ceremony
            if step == "SIGNER_START":
                self.accept("WITNESS")
            if step == "RETIRE":
                self.accept("SIGNER")
            record = self.run_step(step)
            self.assertEqual(record["result"], f"E23_{step}_REACHED_{record['expected']}", record)
            phases.append(record["postPhase"])
        self.assertEqual(phases, list(S.PHASES))
        self.assertEqual(self.dev.mutations, [
            "e23-stage", OP.SIGNER_STOP_COMMAND, OP.WITNESS_STOP_COMMAND, "e23-select", "e23-witness-units",
            OP.WITNESS_START_COMMAND, OP.SIGNER_START_COMMAND, "e23-retire-old"])
        self.assertFalse((self.root / f"opt/lilith-authority-dev/releases/{OLD}").exists())
        markers = sorted(p.name for p in (self.work / OP.M6.ATTEMPT_DIR).iterdir())
        self.assertEqual(markers, sorted(f"{m}.json" for _s, _p, _q, m in OP.STEPS.values()))

    def test_missing_kpan_refuses_before_any_witness_activation(self):
        self.to("SELECT")
        self.op.status(self.repo, self.work, "E4")
        self.stop("KPAN_CREDENTIAL_REQUIRED_BEFORE_WITNESS_UNITS", self.op.render, self.repo, self.work,
                  "WITNESS_UNITS")
        self.host.keygen()
        self.op.status(self.repo, self.work, "E4_KPAN")
        go = self.go("WITNESS_UNITS")                                     # rendered while K-PAN exists ...
        (self.host.p(S.KPAN_BLOB)).unlink()                               # ... and gone before the gate
        self.stop("KPAN_CREDENTIAL_NOT_THE_GO_CREDENTIAL", self.op._step, self.repo, self.work, "WITNESS_UNITS", go)
        self.assertFalse((self.work / OP.M6.ATTEMPT_DIR / "e23-witness-units.json").exists())   # go not consumed
        self.assertNotIn("e23-witness-units", self.dev.mutations)
        self.assertEqual(self.host.unit_sha(), E23.PAYLOAD_DELTA["assets/lilith-recovery-witness.service"][0])
        self.stop("EARLIER_STEP_NOT_REACHED:WITNESS_UNITS", self.op.render, self.repo, self.work, "WITNESS_START")

    def test_incorrect_old_or_new_pins_refuse_before_any_remote_call(self):
        for new, manifest in ((E23.OLD_RELEASE, self.manifest), ("f" * 40, self.manifest), (NEW, "0" * 64),
                              (None, None)):
            with self.subTest(new=new, manifest=manifest):
                op = FakeOperator(new_release=new, new_manifest=manifest).attach(self.dev)
                self.stop("NEW_RELEASE_NOT_THE_E23_PIN", op.preflight, self.repo, self.work)
        self.assertEqual(self.dev.mutations, [])
        self.assertFalse((self.work / OP.OBS_DIR).exists())
        with mock.patch.object(S, "OLD_RELEASE", "a" * 40):              # a host tool bound to another OLD
            self.assertEqual(self.op.preflight(self.repo, self.work)["result"], "E23_PREFLIGHT_STOP")

    def test_unexpected_service_identity_or_state_refuses(self):
        self.host.signer_running(("7" * 32, "77"), OLD)                   # not the E-22 accepted signer
        preflight = self.op.preflight(self.repo, self.work)
        self.assertEqual(preflight["result"], "E23_PREFLIGHT_STOP")
        self.stop("LATEST_PREFLIGHT_NOT_EXACT", self.op.render, self.repo, self.work, "STAGE")
        self.host.signer_running(S.ENDING_SIGNER_INCARNATION, OLD)
        self.to("STAGE")
        go = self.go("SIGNER_STOP")
        self.host.units[S.SIGNER_SERVICE]["NRestarts"] = "1"              # an implicit restart after the render
        self.stop("GATE_NOT_E1_NEW_STAGED:" + S.STOP_RESTARTED, self.op._step, self.repo, self.work, "SIGNER_STOP",
                  go)
        self.assertNotIn(OP.SIGNER_STOP_COMMAND, self.dev.mutations)

    def test_old_cannot_be_retired_while_still_in_use_and_the_go_is_never_retried(self):
        self.to("SIGNER_START")
        self.accept("SIGNER")
        stray = self.root / "proc/999"
        stray.mkdir()
        (stray / "cwd").symlink_to(f"{I.RELEASES}/{OLD}")
        record = self.run_step("RETIRE")
        self.assertEqual((record["result"], record["code"], record["postPhase"]), ("E23_RETIRE_STOP", 2, OP.E7))
        self.assertTrue((self.root / f"opt/lilith-authority-dev/releases/{OLD}").is_dir())
        (stray / "cwd").unlink()
        self.stop("ATTEMPT_ALREADY_CONSUMED:e23-retire", self.op._step, self.repo, self.work, "RETIRE",
                  self.work / "go-RETIRE.txt")

    def test_an_interrupted_phase_never_silently_advances(self):
        self.to("SELECT")
        self.host.keygen()
        real = self.host.run

        def reload_fails(argv, cwd=None, **kw):
            if list(argv) == list(S.DAEMON_RELOAD):
                return subprocess.CompletedProcess(argv, 1, "", "Failed to reload daemon")
            return real(argv, cwd=cwd, **kw)

        self.host.run = reload_fails
        self.dev.system = self.host.system()
        record = self.run_step("WITNESS_UNITS")
        self.assertEqual((record["result"], record["postPhase"]), ("E23_WITNESS_UNITS_STOP", S.STOP_UNITS))
        self.host.run = real
        self.dev.system = self.host.system()
        self.op.status(self.repo, self.work, "AFTER")
        self.stop("STEP_NOT_REACHED:WITNESS_UNITS", self.op.render, self.repo, self.work, "WITNESS_START")
        self.stop("ATTEMPT_ALREADY_CONSUMED:e23-witness-units", self.op._step, self.repo, self.work, "WITNESS_UNITS",
                  self.work / "go-WITNESS_UNITS.txt")
        self.assertNotIn(OP.WITNESS_START_COMMAND, self.dev.mutations)

    def test_steps_cannot_be_skipped_or_reordered(self):
        self.to("STAGE")
        self.host.signer_stopped()                                        # an out-of-band stop (not the operator's)
        self.op.status(self.repo, self.work, "E2_OOB")
        for step in ("WITNESS_STOP", "SELECT", "RETIRE"):
            self.stop("EARLIER_STEP_NOT_REACHED:SIGNER_STOP", self.op.render, self.repo, self.work, step)

    def test_a_failed_witness_start_is_a_stop(self):
        self.to("WITNESS_UNITS")
        self.host.p(S.KPAN_BLOB).unlink()                                 # the blob vanished after the units step
        self.op.status(self.repo, self.work, "E5_GONE")
        self.stop("LATEST_STATUS_NOT_E5", self.op.render, self.repo, self.work, "WITNESS_START")

    def test_a_clean_exit_that_does_not_reach_the_phase_is_a_stop(self):
        self.to("WITNESS_UNITS")
        self.dev.effect["WITNESS_START"] = "ACTIVATING"
        record = self.run_step("WITNESS_START")
        self.assertEqual((record["code"], record["result"], record["postPhase"]),
                         (0, "E23_WITNESS_START_STOP", S.STOP_TRANSITIONAL))
        self.stop("STEP_NOT_REACHED:WITNESS_START", self.op.verify, self.repo, self.work, "WITNESS")
        self.stop("STEP_NOT_REACHED:WITNESS_START", self.op.render, self.repo, self.work, "SIGNER_START")

    def test_verify_refuses_changed_boundaries(self):
        self.to("WITNESS_START")
        self.host.foreign["lilith-os-api-dev.service"]["InvocationID"] = "e" * 32     # e.g. a Core API deploy
        verified = self.op.verify(self.repo, self.work, "WITNESS")
        self.assertEqual(verified["result"], "E23_WITNESS_STOP")
        self.assertIn("FOREIGN_UNIT_INCARNATION_CHANGED", verified["reasons"])
        self.stop("WITNESS_NOT_VERIFIED", self.op.render, self.repo, self.work, "ACCEPT_WITNESS")


class AcceptanceJudgeTests(unittest.TestCase):
    def good(self):
        units = {OP.WITNESS_SERVICE: {"InvocationID": "6" * 32, "MainPID": "4343", "NRestarts": "0"},
                 OP.SIGNER_SERVICE: {"InvocationID": "5" * 32, "MainPID": "4242", "NRestarts": "0"}}
        meta = {"kind": "file", "ino": 1}
        report = {"phase": OP.E7, "result": "PASS", "newManifestSha256": E23.NEW_MANIFEST_SHA256, "units": units,
                  "witnessCredentials": S.WITNESS_CREDENTIALS_NEW, "kWitMeta": meta, "kPanMeta": {"ino": 2},
                  "anchor": {"exact": True, "chainVersions": 0}, "witnessUnits": "NEW", "foreignUnits": {"u": 1},
                  "signerCredentials": ["k"]}
        baseline = {"kWitMeta": meta, "foreignUnits": {"u": 1}, "signerCredentials": ["k"]}
        return report, baseline

    def test_exact_and_each_boundary(self):
        report, baseline = self.good()
        self.assertEqual(OP.judge_acceptance("SIGNER", report, baseline, {"ino": 2}, ("6" * 32, "4343")), [])
        cases = {"KWIT_CREDENTIAL_CHANGED": ("kWitMeta", {"kind": "file", "ino": 9}),
                 "KPAN_CREDENTIAL_CHANGED": ("kPanMeta", {"ino": 3}),
                 "WITNESS_CREDENTIALS_NOT_KWIT_AND_KPAN": ("witnessCredentials", S.WITNESS_CREDENTIALS_OLD),
                 "ANCHOR_STATE_NOT_EMPTY": ("anchor", {"exact": True, "chainVersions": 1}),
                 "SIGNER_CREDENTIALS_CHANGED": ("signerCredentials", ["k", "x"]),
                 "NEW_MANIFEST_NOT_THE_PIN": ("newManifestSha256", "0" * 64)}
        for reason, (key, value) in cases.items():
            with self.subTest(reason=reason):
                bad = dict(report, **{key: value})
                self.assertIn(reason, OP.judge_acceptance("SIGNER", bad, baseline, {"ino": 2}, ("6" * 32, "4343")))
        self.assertIn("WITNESS_NOT_THE_ACCEPTED_REPLACEMENT",
                      OP.judge_acceptance("SIGNER", report, baseline, {"ino": 2}, ("7" * 32, "1")))


class TransportTests(unittest.TestCase):
    def test_every_remote_route_is_lilith_dev_01_only(self):
        calls = []
        op = OP.Operator(run=lambda argv, **kw: calls.append(argv) or done())
        op.ssh("true")
        argv = calls[-1]
        self.assertEqual(argv[argv.index("ssh") + 1], OP.M6.DEV)
        self.assertEqual(OP.M6.DEV, "lilith-dev-01")
        self.assertIn(f"--project={OP.M6.PROJECT}", argv)
        self.assertTrue(argv[-1].startswith(f'--command=test "$(hostname)" = lilith-dev-01 || exit 97; '))
        with mock.patch.dict(OP.M9.os.environ, {OP.M9.PLINK_ENV: ""}):
            with self.assertRaises(OP.Stop):
                op.plink_argv("true")                                     # never a fallback route

    def test_the_operator_names_no_other_host_and_no_prod(self):
        for name in ("e23_operator.py", "e23_release_stages.py"):
            source = (TOOLS / name).read_text(encoding="utf-8")
            for needle in ("gcloud", "compute ssh", "--zone", "--project", "plink.exe", "prod-", "lilith-prod",
                           "subprocess.run", "os.system", "Popen"):
                self.assertFalse(needle in source, f"{name}: {needle}")

    def test_tool_pins_are_the_tree_bytes(self):
        for path, pin in OP.ALL_PINS.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)

    def test_the_accepted_contract_and_historical_tools_are_unchanged(self):
        import e22_operator as E22OP

        self.assertEqual(OP.ALL_PINS[OP.CONTRACT], sha((TOOLS / "e23_privacy_anchor_upgrade.py").read_bytes()))
        for path, pin in E22OP.TOOL_PINS.items():
            self.assertEqual(OP.ALL_PINS[path], pin, path)


if __name__ == "__main__":
    unittest.main()
