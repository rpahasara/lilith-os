"""15B2b-B1b-3e M-B14 (WRITE_RELEASED) operator: expected-record derivation, read-back judge, staging command, flow.

Record: docs/architecture/slice-15b2b-b1b3e-mb14-release-initial-package.md. TEST-ONLY: a synthetic DEV behind the
operator's transport seams; the hold snapshots are the REAL wire form (`pr1_acceptance.hold_snapshot_document`) and
the RELEASED step is checked by the REAL writer rule (`successor_custody.hold_store_transition_reason`). The staging
command runs in a local shell with `sudo -n` and the fixed paths substituted. Nothing here contacts DEV.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import mb10_held_verifier as H10  # noqa: E402
import mb14_operator as OP  # noqa: E402
import mb6_operator as M6  # noqa: E402
from lilith_owner_memory import pr1_acceptance as PA  # noqa: E402
from lilith_owner_memory import successor_custody as SC  # noqa: E402
from lilith_owner_memory import witness_readiness as WR  # noqa: E402

ENVELOPE = b'{"envelopeType":"SYNTHETIC"}\n'
INPUTS = {"synthetic": "owner inputs (TEST)"}
OTHER = "d" * 64


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def done(code=0, out=b"", err=b""):
    return subprocess.CompletedProcess([], code, out, err)


def record(state: str, witness: str = OP.GENESIS) -> dict:
    reason = SC.INITIAL_CUSTODY_BOOTSTRAP if state == SC.HELD else SC.OWNER_RELEASE_AFTER_ELIGIBILITY
    return SC.CeremonyHoldV1("dev", H10.INITIAL_CEREMONY_ID, SC.INITIAL_CUSTODY, state, reason, None,
                             H10.INITIAL_KEY_ID, witness).to_dict()


def observe_out(entries: list[tuple[str, bytes]], granted: bool = False) -> bytes:
    observation = SC.HoldStoreObservationV1(tuple(WR.StoreEntryV1(n, WR.REGULAR, d) for n, d in entries))
    snapshot = PA.hold_snapshot_document(observation, environment="dev")
    return json.dumps({"listingDigest": snapshot["listingDigest"], "snapshot": snapshot,
                       "authorityGranted": granted}, sort_keys=True, separators=(",", ":")).encode() + b"\n"


class Dev:
    """A synthetic DEV: the hold store, the staging path, the units, and the CLI's behaviour for `release-initial`."""

    def __init__(self):
        held = record(SC.HELD)
        self.entries = [(SC.hold_record_name(held["ceremonyId"]), SC.hold_record_bytes(held))]
        self.staged = False
        self.signer = OP.SIGNER
        self.behaviour = "release"        # release | refuse | lost | misbound | leave-staged | signer-changed
        self.root_reads = True            # False: the root stage read fails (no output, exit 1)
        self.units_rc = 0
        self.releases: list[bytes] = []
        self.digest = OP.APPROVED_PACKAGE_DIGEST

    def units(self) -> bytes:
        return (f"Id={OP.E22.SIGNER_SERVICE}\nMainPID={self.signer[1]}\nInvocationID={self.signer[0]}\n\n"
                f"Id={OP.E22.WITNESS_SERVICE}\nMainPID=127192\nInvocationID={'8' * 32}\n").encode()

    def invoke(self, command: str, stdin: bytes | None):
        if stdin is not None:
            return self.release(command, stdin)
        if command == OP.OBSERVE_COMMAND:
            return done(0, observe_out(self.entries))
        if command == OP.STAGE_COMMAND:
            if not self.root_reads:
                return done(1, b"", b"sudo: a password is required\n")
            return done(0, b"STAGE=present\n" if self.staged else b"STAGE=absent\n")
        if command == OP.UNITS_COMMAND:
            return done(self.units_rc, self.units() if self.units_rc == 0 else b"")
        if command.startswith(f"sudo -n /usr/bin/sha256sum {OP.STAGE_FILE}"):
            self.staged = False
            return done(0)
        raise AssertionError(command)

    def release(self, command: str, stdin: bytes):
        assert f"release-initial {OP.APPROVED_PACKAGE_DIGEST} {OP.STAGE_FILE}" in command
        self.releases.append(base64.b64decode(stdin.strip()))
        if self.behaviour == "refuse":
            return done(2, b"MB14_CLI_BEGIN\nMB14_CLI_RC=2\nMB14_UNSTAGED=0\n",
                        b"lilith-authority-hold-dev: REFUSED HOLD_RELEASE_NOT_PERMITTED\n")
        released = record(SC.RELEASED, OTHER if self.behaviour == "misbound" else OP.GENESIS)
        self.entries = [(self.entries[0][0], SC.hold_record_bytes(released))]
        if self.behaviour == "lost":
            return done(None, b"", b"LOCAL_TimeoutExpired")
        self.staged = self.behaviour == "leave-staged"
        if self.behaviour == "signer-changed":
            self.signer = ("7" * 32, "99999")
        cli = json.dumps({"record": released}, sort_keys=True, separators=(",", ":")).encode()
        return done(0, b"MB14_CLI_BEGIN\n" + cli + b"\nMB14_CLI_RC=0\nMB14_UNSTAGED=" +
                    (b"1" if self.staged else b"0") + b"\n")


class FakeOperator(OP.Operator):
    def attach(self, dev: Dev) -> "FakeOperator":
        self.dev = dev
        return self

    def pins(self, repo):
        return {"control": "c" * 40, "operatorSha256": "d" * 64, "result": "MB14_TOOL_PINS_EXACT"}

    def owner_inputs(self, raw):
        assert raw == ENVELOPE
        return dict(INPUTS)

    def _invoke_once(self, command, stdin):
        return self.dev.invoke(command, stdin)

    def plink_argv(self, command):
        if getattr(self, "transport_error", None):
            raise OP.Stop(self.transport_error)
        return ["plink", command]

    def package(self, repo, outdir, envelope):
        outdir.mkdir(mode=0o700, parents=True)
        held = [[H10.INITIAL_CEREMONY_ID, "INITIAL_CUSTODY", "HELD"]]
        report = {"mode": "HOLD_RELEASE_ELIGIBILITY", "status": "READY", "reasons": [], "packageDigest": self.dev.digest,
                  "holdListingDigest": OP.HELD_LISTING_DIGEST,
                  "package": {"evidence": {"holdStore": {"records": held}, "witness": {
                      "classification": "CONSISTENT", "chainLength": 1, "genesisDigest": OP.GENESIS,
                      "headDigest": OP.GENESIS}}}}
        (outdir / "remote.out").write_text(json.dumps({"report": report}), encoding="utf-8")
        return {"result": "E22_PACKAGE_READY", "mode": "HOLD_RELEASE_ELIGIBILITY", "status": "READY", "reasons": [],
                "packageDigest": self.dev.digest}


class Case(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.saved = OP.ENVELOPE_SHA256
        OP.ENVELOPE_SHA256 = sha(ENVELOPE)
        self.addCleanup(setattr, OP, "ENVELOPE_SHA256", self.saved)
        self.dev = Dev()
        self.op = FakeOperator().attach(self.dev)
        self.work = self.base / "mb14"
        self.envelope = self.base / "envelope.out"
        self.envelope.write_bytes(ENVELOPE)

    def text(self, act: str) -> Path:
        path = self.base / f"{act}.txt"
        path.write_bytes(self.op.render(ROOT, self.work, act)["text"].encode("ascii"))
        return path

    def ready(self) -> None:
        self.assertEqual(self.op.prepare(ROOT, self.work, self.envelope)["result"], "MB14_PREPARED")
        self.assertEqual(self.op.pre(ROOT, self.work)["result"], "MB14_PRE_EXACT")

    def marker(self, name: str = OP.MARKER) -> Path:
        return self.work / M6.ATTEMPT_DIR / f"{name}.json"


class DerivationTests(unittest.TestCase):
    def test_stdlib_and_contract_agree_and_reproduce_the_accepted_held(self):
        pinned = OP.pinned_expected_released()
        self.assertEqual(OP.expected_released(), pinned)
        self.assertEqual((pinned["held"]["sha256"], pinned["name"]), (H10.EXPECTED_HELD_SHA256, H10.EXPECTED_HELD_NAME))
        self.assertEqual((pinned["sha256"], pinned["length"]), (OP.EXPECTED_RELEASED_SHA256, 431))
        self.assertEqual(SC.hold_record_bytes(record(SC.RELEASED)), pinned["bytes"])
        self.assertEqual(pinned["record"]["observedWitnessDigest"], OP.GENESIS)

    def test_one_record_per_ceremony_held_to_released_only(self):
        held, released = SC.hold_store(record(SC.HELD)), SC.hold_store(record(SC.RELEASED))
        self.assertIsNone(SC.hold_store_transition_reason(held, released))
        self.assertEqual(SC.hold_store_transition_reason(released, held), "HOLD_ALREADY_RELEASED")
        self.assertEqual(SC.hold_store_transition_reason(held, SC.HoldStoreObservationV1(())), "HOLD_RECORD_REMOVED")
        self.assertEqual(released.entries[0].name, held.entries[0].name)       # the same name: replaced in place

    def test_listing_digests_equal_the_contract(self):
        e = OP.expected_document()
        self.assertEqual(e["held"]["listingDigest"], PA.hold_listing_digest(SC.hold_store(record(SC.HELD))))
        self.assertEqual(e["held"]["listingDigest"], OP.HELD_LISTING_DIGEST)
        self.assertEqual(e["released"]["listingDigest"], PA.hold_listing_digest(SC.hold_store(record(SC.RELEASED))))
        self.assertEqual(e["released"]["listingDigest"], OP.EXPECTED_RELEASED_LISTING)


class JudgeTests(unittest.TestCase):
    def setUp(self):
        self.e = OP.expected_document()
        self.name = self.e["name"]

    def judge(self, entries, rc=0, granted=False):
        return OP.judge_observe(rc, observe_out(entries, granted), self.e)["class"]

    def test_exact_states(self):
        self.assertEqual(self.judge([(self.name, SC.hold_record_bytes(record(SC.HELD)))]), OP.HELD_UNCHANGED)
        self.assertEqual(self.judge([(self.name, SC.hold_record_bytes(record(SC.RELEASED)))]), OP.RELEASED_EXACT)

    def test_everything_else_stops(self):
        released = SC.hold_record_bytes(record(SC.RELEASED))
        self.assertEqual(self.judge([(self.name, SC.hold_record_bytes(record(SC.RELEASED, OTHER)))]), OP.UNEXPECTED)
        self.assertEqual(self.judge([(self.name, released), ("0" * 64 + ".json", released)]), OP.UNEXPECTED)
        self.assertEqual(self.judge([]), OP.UNEXPECTED)
        self.assertEqual(self.judge([(self.name, released)], rc=2), OP.UNOBSERVABLE)
        self.assertEqual(self.judge([(self.name, released)], granted=True), OP.UNOBSERVABLE)
        self.assertEqual(OP.judge_observe(0, b"not json", self.e)["class"], OP.UNOBSERVABLE)


@unittest.skipIf(shutil.which("bash") is None, "needs bash")
class StagingCommandTests(unittest.TestCase):
    """The real release command in a local shell: `sudo -n` removed, the fixed paths substituted."""

    def run_command(self, stage: Path, cli_rc: int, inputs: bytes = b'{"synthetic":1}\n', tamper: bool = False):
        cli = stage.parent / "cli.sh"
        cli.write_text(f"#!/bin/sh\ncat \"$3\" > \"{stage.parent}/seen\"\necho '{{\"record\":1}}'\nexit {cli_rc}\n")
        cli.chmod(0o755)
        command, stdin = OP.Operator.release_command(inputs)
        command = command.replace("sudo -n ", "").replace(OP.STAGE_DIR, stage.as_posix()) \
            .replace(OP.HOLD_CLI, cli.as_posix())
        if tamper:
            stdin = base64.b64encode(b"other") + b"\n"
        return subprocess.run(["bash", "-c", command], input=stdin, capture_output=True, timeout=60)

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.stage = Path(tmp.name) / "stage"

    def test_stages_runs_once_and_unstages(self):
        result = self.run_command(self.stage, 0)
        self.assertEqual(result.returncode, 0, result.stderr)
        cli, rc, unstaged = OP.parse_release(result.stdout)
        self.assertEqual((cli, rc, unstaged), ({"record": 1}, 0, "MB14_UNSTAGED=0"))
        self.assertEqual((self.stage.parent / "seen").read_bytes(), b'{"synthetic":1}\n')
        self.assertFalse(self.stage.exists())

    def test_cli_exit_code_is_returned_and_the_document_still_removed(self):
        result = self.run_command(self.stage, 2)
        self.assertEqual((result.returncode, OP.parse_release(result.stdout)[1]), (2, 2))
        self.assertFalse(self.stage.exists())

    def test_stage_observation_answers_only_from_the_root_shell(self):
        def stage(sudo: str) -> subprocess.CompletedProcess:
            command = OP.STAGE_COMMAND.replace("sudo -n ", sudo).replace(OP.STAGE_DIR, self.stage.as_posix())
            return subprocess.run(["bash", "-c", command], capture_output=True, timeout=60)
        self.assertEqual(stage("").stdout, b"STAGE=absent\n")
        self.stage.mkdir()
        self.assertEqual(stage("").stdout, b"STAGE=present\n")
        self.stage.rmdir()
        failed = stage("/nonexistent/sudo ")                                     # sudo / root unavailable
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(failed.stdout, b"")                                      # never STAGE=absent

    def test_existing_staging_path_or_tampered_payload_refuse_before_the_cli(self):
        self.stage.mkdir()
        self.assertEqual(self.run_command(self.stage, 0).returncode, 95)
        self.assertFalse((self.stage.parent / "seen").exists())
        self.stage.rmdir()
        self.assertEqual(self.run_command(self.stage, 0, tamper=True).returncode, 96)
        self.assertFalse(self.stage.exists())


class FlowTests(Case):
    def test_prepare_refuses_another_envelope_and_an_existing_workdir(self):
        self.envelope.write_bytes(b"{}\n")
        with self.assertRaises(OP.Stop):
            self.op.prepare(ROOT, self.work, self.envelope)
        self.envelope.write_bytes(ENVELOPE)
        self.op.prepare(ROOT, self.work, self.envelope)
        with self.assertRaises(OP.Stop):
            self.op.prepare(ROOT, self.work, self.envelope)

    def test_released_exact_then_acceptance(self):
        self.ready()
        report = self.op.release(ROOT, self.work, self.text("GO"))
        self.assertEqual((report["result"], report["readback"]), ("MB14_RELEASED_EXACT", "MB14_READBACK_RELEASED_EXACT"))
        self.assertEqual(self.dev.releases, [(self.work / OP.INPUTS_FILE).read_bytes()])
        self.assertTrue(self.marker().is_file())
        with self.assertRaises(OP.Stop):                                           # one attempt only
            self.op.render(ROOT, self.work, "GO")
        accept = self.text("ACCEPT")
        self.assertNotIn(OP.ADOPTION_LINE, accept.read_text())
        self.assertEqual(self.op.accept(ROOT, self.work, accept)["result"], "MB14_ACCEPTED")

    def test_pre_not_exact_blocks_the_go(self):
        self.dev.digest = OTHER
        self.op.prepare(ROOT, self.work, self.envelope)
        pre = self.op.pre(ROOT, self.work)
        self.assertEqual((pre["result"], pre["reasons"]), ("MB14_PRE_NOT_EXACT", ["RERUN_DIGEST_NOT_APPROVED"]))
        with self.assertRaises(OP.Stop):
            self.op.render(ROOT, self.work, "GO")

    def test_a_changed_go_or_gate_never_consumes_the_attempt(self):
        self.ready()
        go = self.text("GO")
        go.write_bytes(go.read_bytes().replace(b"exactly one attempt", b"one attempt"))
        with self.assertRaises(OP.Stop):
            self.op.release(ROOT, self.work, go)
        self.dev.staged = True
        with self.assertRaises(OP.Stop):
            self.op.release(ROOT, self.work, self.text("GO"))
        self.assertFalse(self.marker().exists())
        self.assertEqual(self.dev.releases, [])

    def test_refused_write_consumes_the_go_and_reads_back_held(self):
        self.ready()
        self.dev.behaviour = "refuse"
        report = self.op.release(ROOT, self.work, self.text("GO"))
        self.assertEqual(report["result"], "MB14_STOP:MB14_READBACK_NOT_WRITTEN")
        self.assertTrue(self.marker().is_file())
        with self.assertRaises(OP.Stop):
            self.op.render(ROOT, self.work, "ACCEPT")

    def test_lost_response_with_an_exact_readback_needs_adoption(self):
        self.ready()
        self.dev.behaviour = "lost"
        self.assertEqual(self.op.release(ROOT, self.work, self.text("GO"))["result"], "MB14_RELEASED_ADOPTION_REQUIRED")
        self.assertIn(OP.ADOPTION_LINE, self.text("ACCEPT").read_text())

    def test_a_misbound_record_is_a_c19_stop(self):
        self.ready()
        self.dev.behaviour = "misbound"
        self.assertEqual(self.op.release(ROOT, self.work, self.text("GO"))["result"], "MB14_STOP:MB14_READBACK_STOP_C19")

    def test_staging_residue_is_removed_only_by_its_own_statement(self):
        self.ready()
        self.dev.behaviour = "leave-staged"
        self.assertEqual(self.op.release(ROOT, self.work, self.text("GO"))["result"],
                         "MB14_STOP:MB14_READBACK_RELEASED_STAGING_RESIDUE")
        with self.assertRaises(OP.Stop):
            self.op.render(ROOT, self.work, "ACCEPT")
        self.assertEqual(self.op.unstage(ROOT, self.work, self.text("UNSTAGE"))["result"], "MB14_UNSTAGED")
        self.assertTrue(self.marker(OP.UNSTAGE_MARKER).is_file())
        self.assertEqual(self.op.post(ROOT, self.work)["result"], "MB14_READBACK_RELEASED_EXACT")


class ObservationFailureTests(Case):
    def test_a_failed_root_stage_read_is_unknown_and_blocks_the_go(self):
        self.op.prepare(ROOT, self.work, self.envelope)
        self.dev.root_reads = False
        pre = self.op.pre(ROOT, self.work)
        self.assertEqual((pre["stage"], pre["result"]), ("UNKNOWN", "MB14_PRE_NOT_EXACT"))
        self.assertIn("STAGING_PATH_NOT_ABSENT", pre["reasons"])
        with self.assertRaises(OP.Stop):
            self.op.render(ROOT, self.work, "GO")

    def test_a_failed_root_stage_read_after_the_write_is_a_c19_stop_and_blocks_acceptance(self):
        self.ready()
        go = self.text("GO")
        real = self.dev.release

        def release_then_fail_root_reads(command, stdin):
            result = real(command, stdin)
            self.dev.root_reads = False
            return result
        self.dev.release = release_then_fail_root_reads
        self.assertEqual(self.op.release(ROOT, self.work, go)["result"], "MB14_STOP:MB14_READBACK_STOP_C19")
        with self.assertRaises(OP.Stop):
            self.op.render(ROOT, self.work, "ACCEPT")

    def test_no_acceptance_after_a_c19_readback_with_a_changed_signer(self):
        self.ready()
        self.dev.behaviour = "signer-changed"
        self.assertEqual(self.op.release(ROOT, self.work, self.text("GO"))["result"], "MB14_STOP:MB14_READBACK_STOP_C19")
        with self.assertRaises(OP.Stop):
            self.op.render(ROOT, self.work, "ACCEPT")

    def test_no_acceptance_when_the_latest_required_observation_failed(self):
        self.ready()
        self.assertEqual(self.op.release(ROOT, self.work, self.text("GO"))["result"], "MB14_RELEASED_EXACT")
        self.dev.units_rc = 1
        self.assertEqual(self.op.post(ROOT, self.work)["result"], "MB14_READBACK_STOP_C19")
        with self.assertRaises(OP.Stop):                                           # the LATEST read-back decides
            self.op.render(ROOT, self.work, "ACCEPT")

    def test_the_verdict_needs_every_condition(self):
        exact = {"hold": OP.RELEASED_EXACT, "stage": "ABSENT", "signerUnchanged": True,
                 "codes": {"observe": 0, "stage": 0, "units": 0}}
        self.assertEqual(OP.readback_verdict(exact), OP.READBACK_EXACT)
        for change in ({"signerUnchanged": False}, {"stage": "UNKNOWN"},
                       {"codes": {"observe": 0, "stage": 0, "units": 1}}, {"codes": {"observe": 0, "stage": 0}},
                       {"hold": OP.UNEXPECTED}):
            self.assertEqual(OP.readback_verdict(dict(exact, **change)), "MB14_READBACK_STOP_C19", change)


class PostMarkerTests(Case):
    def test_b1_a_local_transport_refusal_never_consumes_the_go(self):
        self.ready()
        self.op.transport_error = "PLINK_UNSET"
        with self.assertRaises(OP.Stop):
            self.op.release(ROOT, self.work, self.text("GO"))
        self.assertFalse(self.marker().exists())
        self.assertEqual(self.dev.releases, [])
        self.op.transport_error = None
        self.assertEqual(self.op.release(ROOT, self.work, self.text("GO"))["result"], "MB14_RELEASED_EXACT")

    def test_b2_an_interrupted_readback_keeps_the_attempt_and_a_later_post_allows_acceptance(self):
        self.ready()
        real_post = self.op.post
        self.op.post = lambda repo, workdir: (_ for _ in ()).throw(OP.Stop("GIT_FAILED"))
        report = self.op.release(ROOT, self.work, self.text("GO"))
        self.assertEqual(report["result"], "MB14_STOP:MB14_READBACK_NOT_COMPLETED:GIT_FAILED")
        attempt = json.loads((self.work / OP.ATTEMPT_FILE).read_text())
        self.assertEqual((attempt["cliExact"], attempt["code"]), (True, 0))
        with self.assertRaises(OP.Stop):                                           # never a second attempt
            self.op.render(ROOT, self.work, "GO")
        self.op.post = real_post
        self.assertEqual(self.op.post(ROOT, self.work)["result"], "MB14_READBACK_RELEASED_EXACT")
        accept = self.text("ACCEPT")
        self.assertNotIn(OP.ADOPTION_LINE, accept.read_text())
        self.assertEqual(self.op.accept(ROOT, self.work, accept)["result"], "MB14_ACCEPTED")


class PinTests(unittest.TestCase):
    def test_root_commands_use_absolute_paths(self):
        command, _ = OP.Operator.release_command(b"{}\n")
        for text in (command, OP.STAGE_COMMAND):
            for word in re.findall(r"sudo -n (\S+)", text):
                self.assertTrue(word.startswith("/"), word)

    def test_tool_pins_are_the_tree_bytes(self):
        for path, pin in OP.TOOL_PINS.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)

    def test_constants_match_the_accepted_records(self):
        self.assertEqual(OP.GENESIS, OP.M10.GENESIS)
        self.assertEqual(OP.HOLD_CLI, "/usr/local/sbin/lilith-authority-hold-dev")
        self.assertTrue(OP.STAGE_FILE.startswith(OP.STAGE_DIR + "/"))
        self.assertFalse(OP.STAGE_DIR.startswith(H10.HOLD_PARENT))


if __name__ == "__main__":
    unittest.main()
