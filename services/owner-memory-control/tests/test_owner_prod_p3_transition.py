"""OWNER_PROD P3 (F0 … F7): `owner_prod_release_stages` and `owner_prod_operator` on the E-23 fake-systemd DEV root.

Record: docs/architecture/canonical-memory-p3-dev-transition.md. TEST-ONLY: the FM-2 transition tests moved to P3. The
host is the E-23 synthetic root (`test_trackb_e23_release_stages.E23Host`) in the post-FM-2 shape (d82f7da installed,
the unchanged E-23 witness units loaded, K-PAN present, the Privacy anchor v1 chain written, the FM-2 accepted signer
and witness running); NEW is this tree's payload (= the 88a1168 merge) in archive layout v3. The operator's transport
seams deliver every BOOT bundle to the REAL stage tool and every reviewed unit command to the fake units. Nothing
contacts DEV, runs systemctl, opens a socket or touches a credential. `TransformTests` prove the P3 tools are the FM-2
tools moved by exactly `owner_prod_transform`; `ReturnTests` rehearse the owner-adjudicated return from every phase.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _p in (TOOLS, HERE, ROOT / "services/authority-dev/ceremony"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import test_personal_memory_fm2_transition as FT  # noqa: E402  (the FM-2 payload builder and fakes)
import test_trackb_e23_release_stages as H  # noqa: E402  (the E-23 fake-systemd host and fixtures)
from test_trackb_e23_release_stages import E23, I, T19  # noqa: E402

import fm2_signer_upgrade as FM2  # noqa: E402
import owner_prod_operator as OP  # noqa: E402
import owner_prod_release_stages as S  # noqa: E402
import owner_prod_signer_upgrade as P3  # noqa: E402
import owner_prod_transform as X  # noqa: E402

OLD, NEW = P3.OLD_RELEASE, P3.NEW_RELEASE
NEW_SIGNER = ("5" * 32, "4242")
NEW_WITNESS = ("6" * 32, "4343")
ANCHOR_V1 = FT.ANCHOR_V1
sha, done = FT.sha, FT.done


def build_new(root: Path, wheelhouse: Path) -> dict[str, bytes]:
    """The P3 NEW payload (archive layout v3): this tree's build (its runtime members are the 88a1168 bytes)."""
    import build_authority_dev_release as B

    return B.build_payloads(root, wheelhouse)


class P3Host(H.E23Host):
    """The synthetic root at F0: d82f7da selected with the (E-23 NEW, unchanged since) witness unit files loaded,
    K-WIT and K-PAN present, the anchor directory holding the v1 chain, and the FM-2 accepted signer and witness
    running from OLD. No `deployment.json`: the DEV host stays DEV_SYNTHETIC."""

    def __init__(self, root: Path, old_payloads: dict[str, bytes]):  # noqa: D107
        with mock.patch.object(H, "OLD", OLD):                          # the E-23 host, installed at d82f7da
            super().__init__(root, old_payloads)
        self.keygen()
        anchor = self.p(S.ANCHOR_DIR)
        (anchor / "chain").mkdir(parents=True)
        os.chmod(anchor, 0o700)
        (anchor / "anchor.lock").write_bytes(b"")
        (anchor / "chain/00000001.json").write_bytes(ANCHOR_V1)
        self.signer_stopped()
        self.stopped()
        self.running(S.ENDING_WITNESS_INCARNATION, OLD)
        self.signer_running(S.ENDING_SIGNER_INCARNATION, OLD)


class Base(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        house = stack.enter_context(T19.stand_in_wheels())
        self.root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        self.out = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        self.old_payloads = FT.build_fm2(ROOT, house)                    # the installed d82f7da payload (layout v3)
        self.new_payloads = build_new(ROOT, house)                       # the 88a1168 payload (layout v3)
        self.host = P3Host(self.root, self.old_payloads)
        self.system = self.host.system()
        with S.layout_v3():
            self.archive, self.stamp, self.manifest = T19.archive_for(self.out, NEW, self.new_payloads)
        # Stand-in wheels: the archive cannot carry the attested manifest; only the manifest pin is patched (the delta
        # pins and NEW are the contract's).
        stack.enter_context(mock.patch.object(P3, "NEW_MANIFEST_SHA256", self.manifest))
        stack.enter_context(mock.patch.object(S.I, "verify_archive", self.verify_v3))

    def verify_v3(self, archive, attestation, expected):
        assert set(P3.LAYOUT_ADDED) | set(E23.PAYLOAD_ADDED) <= I.EXPECTED_PATHS, "stage must bind layout v3"
        return VERIFY(archive, attestation, expected)

    def status(self):
        return S.p3_status(self.system, OLD, NEW, status=self.host.status)

    def stage(self, manifest=None, archive=None, stamp=None):
        return S.stage_p3_stage(self.system, OLD, NEW, manifest or self.manifest, archive or self.archive,
                                stamp or self.stamp, status=self.host.status)

    def select(self):
        return S.stage_p3_select(self.system, OLD, NEW, status=self.host.status)

    def retire(self, signer=NEW_SIGNER[0], witness=NEW_WITNESS[0]):
        return S.stage_p3_retire_old(self.system, OLD, NEW, signer, witness, status=self.host.status)

    def refused(self, prefix, call, *args, **kwargs):
        with self.assertRaises(I.InstallError) as caught:
            call(*args, **kwargs)
        self.assertTrue(caught.exception.reason.startswith(prefix), caught.exception.reason)

    def private_state(self) -> dict[str, str]:
        """Every byte the transition must never write: custody, ledger, witness state, anchor chain, credentials."""
        return self.host.snapshot()


VERIFY = I.verify_archive


@unittest.skipUnless(T19.POSIX, "release trees need POSIX modes and symlinks")
class StageTests(Base):
    def test_f0_is_the_post_fm2_host(self):
        report = self.status()
        self.assertEqual((report["state"], report["result"], report["phase"]), (S.OLD_ONLY, "PASS", S.F0),
                         report["failures"])
        self.assertEqual((report["kPan"], report["witnessUnits"], report["witnessCredentials"]),
                         ("PRESENT_EXACT", "NEW", S.WITNESS_CREDENTIALS))
        self.assertEqual(report["anchor"]["chain"], {"00000001.json": sha(ANCHOR_V1)})
        self.assertEqual(sorted(report["oldReleaseUsers"]), sorted([S.ENDING_SIGNER_INCARNATION[1],
                                                                    S.ENDING_WITNESS_INCARNATION[1]]))
        self.assertFalse(self.host.p("/etc/lilith-authority-dev/deployment.json").exists())

    def test_the_full_f0_to_f7_rehearsal_stops_both_units_before_the_select(self):
        before, anchor = self.private_state(), self.status()["anchor"]
        seen = [self.status()["phase"], self.stage()["phase"]]
        self.host.signer_stopped()
        seen.append(self.status()["phase"])
        self.host.stopped()
        seen.append(self.status()["phase"])
        seen.append(self.select()["phase"])
        self.host.running(NEW_WITNESS, NEW)                              # one start: K-WIT + K-PAN, the P3 witness
        seen.append(self.status()["phase"])
        self.host.signer_running(NEW_SIGNER, NEW)                        # one start: K-ACT
        seen.append(self.status()["phase"])
        retired = self.retire()
        seen.append(retired["phase"])
        self.assertEqual(seen, list(S.PHASES))
        self.assertEqual((retired["state"], retired["result"], retired["oldReleaseUsers"]), (S.RETIRED, "PASS", []))
        self.assertFalse(self.host.p(f"{I.RELEASES}/{OLD}").exists())
        self.assertEqual(self.private_state(), before)                   # custody, ledger, witness state untouched
        self.assertEqual(retired["anchor"], anchor)                      # the Privacy anchor chain untouched
        self.assertEqual(retired["foreignUnits"], H.FOREIGN)
        mutating = [c for c in self.host.calls if Path(c[0]).name in ("systemctl", "systemd-tmpfiles")
                    and c[1] != "show"]
        self.assertEqual(mutating, [])
        installed = {p: sha(self.host.p(f"{I.RELEASES}/{NEW}/{p}").read_bytes()) for p in P3.PAYLOAD_DELTA}
        self.assertEqual(installed, {p: after for p, (_b, after) in P3.PAYLOAD_DELTA.items()})
        self.assertFalse(self.host.p("/etc/lilith-authority-dev/deployment.json").exists())   # never PROD

    def test_select_needs_both_units_stopped_a_witness_on_old_never_crosses_the_selector(self):
        self.stage()
        self.refused("P3_PRE_PHASE:F1_NEW_STAGED", self.select)
        self.host.signer_stopped()
        self.refused("P3_PRE_PHASE:F2_SIGNER_STOPPED", self.select)
        self.assertEqual(os.readlink(self.root / "opt/lilith-authority-dev/current"), f"releases/{OLD}")
        self.host.stopped()
        self.select()
        self.host.running(S.ENDING_WITNESS_INCARNATION, OLD)
        self.assertEqual(self.status()["phase"], S.STOP_ACROSS_SELECT)
        self.host.running(S.ENDING_WITNESS_INCARNATION, NEW)
        self.host.units[S.WITNESS_SERVICE]["NRestarts"] = "1"
        self.assertEqual(self.status()["phase"], S.STOP_RESTARTED)

    def test_old_cannot_be_retired_while_anything_uses_it(self):
        self.stage()
        self.host.signer_stopped()
        self.host.stopped()
        self.select()
        self.host.running(NEW_WITNESS, NEW)
        self.refused("P3_PRE_PHASE:F5_WITNESS_RUNNING", self.retire)
        self.host.signer_running(NEW_SIGNER, NEW)
        self.refused("P3_REPLACEMENT_INVOCATION_INVALID", self.retire, S.ENDING_SIGNER_INCARNATION[0])
        self.refused("P3_ACCEPTED_REPLACEMENTS_NOT_RUNNING", self.retire, "8" * 32)
        stray = self.root / "proc/999"
        stray.mkdir()
        (stray / "maps").write_text(f"7f00-7f10 r-xp 0 08:01 1 {I.RELEASES}/{OLD}/venv/lib/x.so\n", encoding="ascii")
        self.refused("P3_OLD_RELEASE_IN_USE:999", self.retire)
        self.assertTrue(self.host.p(f"{I.RELEASES}/{OLD}").is_dir())
        (stray / "maps").unlink()
        self.assertEqual(self.retire()["phase"], S.F7)

    def test_stage_refuses_any_other_payload_or_manifest(self):
        cases = {
            "a witness member with other bytes": {**self.new_payloads, "lilith_recovery_witness/server.py":
                                                  self.new_payloads["lilith_recovery_witness/server.py"] + b"\n"},
            "a delta member left at OLD": {**self.new_payloads, "lilith_authority_dev/core.py":
                                           self.old_payloads["lilith_authority_dev/core.py"]},
            "a member outside the delta": {**self.new_payloads, "lilith_authority_dev/protocol.py":
                                           self.new_payloads["lilith_authority_dev/protocol.py"] + b"\n"},
        }
        for label, payloads in cases.items():
            with self.subTest(label=label):
                out = Path(tempfile.mkdtemp(dir=self.out))
                with S.layout_v3():
                    archive, stamp, manifest = T19.archive_for(out, NEW, payloads)
                self.refused("P3_MANIFEST_PIN_INVALID", self.stage, manifest, archive, stamp)
                with mock.patch.object(P3, "NEW_MANIFEST_SHA256", manifest):
                    self.refused("P3_PAYLOAD_DELTA", self.stage, manifest, archive, stamp)
        self.assertEqual(sorted(os.listdir(self.root / "opt/lilith-authority-dev/releases")), [OLD])
        self.stage()
        self.refused("P3_PRE_PHASE:F1_NEW_STAGED", self.stage)

    def test_credentials_units_and_anchor_are_stops_in_every_phase(self):
        os.chmod(self.host.p(S.KPAN_BLOB), 0o640)
        self.assertEqual(self.status()["phase"], S.STOP_KPAN)
        os.chmod(self.host.p(S.KPAN_BLOB), 0o600)
        target = H.S.WITNESS_HOST_FILES["assets/lilith-recovery-witness.service"]
        saved = self.host.p(target).read_bytes()
        self.host.write(target, saved + b"\n")
        self.assertEqual(self.status()["phase"], S.STOP_UNITS)
        self.host.write(target, saved)
        (self.host.p(S.ANCHOR_DIR) / "unexpected").write_bytes(b"")
        self.assertEqual(self.status()["phase"], S.STOP_UNITS)
        (self.host.p(S.ANCHOR_DIR) / "unexpected").unlink()
        self.assertEqual(self.status()["phase"], S.F0)
        self.refused("P3_OLD_RELEASE_NOT_THE_INSTALLED_RELEASE", S.p3_status, self.system, FM2.OLD_RELEASE, NEW)
        self.refused("P3_NEW_RELEASE_NOT_THE_PINNED_RELEASE", S.p3_status, self.system, OLD, "b" * 40)

    def test_a_non_dev_host_is_refused_by_every_form(self):
        system = self.host.system(hostname=lambda: "lilith-01")
        for form in (["p3-stage", OLD, NEW, self.manifest, str(self.archive), str(self.stamp)],
                     ["p3-select", OLD, NEW], ["p3-status", OLD, NEW], ["p3-retire-old", OLD, NEW, "5" * 32,
                                                                        "6" * 32]):
            with self.subTest(form=form[0]):
                self.assertEqual(S.main(form, system=system), 2)
        self.assertEqual(S.main(["p3-witness-units", OLD, NEW], system=self.system), 2)


@unittest.skipUnless(T19.POSIX, "release trees need POSIX modes and symlinks")
class ReturnTests(Base):
    """The owner-adjudicated return from a STOP, with the reviewed unit commands only. A return ends the ladder: the
    returned units are new incarnations on OLD (`FS_ENDING_INCARNATION_CHANGED`), so no later step can run from it."""

    def walk(self, last: int) -> None:
        steps = (self.stage, self.host.signer_stopped, self.host.stopped, self.select,
                 lambda: self.host.running(NEW_WITNESS, NEW))
        for step in steps[:last]:
            step()

    def reselect_old(self) -> None:
        """The return selector change (F4 / F5 only, both units stopped): the inverse of `p3-select`."""
        tmp = self.system.path(S.S19.SELECTOR_TMP)
        os.symlink(f"releases/{OLD}", tmp)
        os.rename(tmp, self.system.path(I.CURRENT))

    def test_every_phase_has_a_return_to_old(self):
        for last, label in ((1, "F1"), (2, "F2"), (3, "F3"), (4, "F4"), (5, "F5")):
            with self.subTest(label):
                self.tearDown_host()
                self.walk(last)
                before = self.private_state()
                if last == 5:
                    self.host.stopped()                                  # the NEW witness stops first
                if last >= 4:
                    self.reselect_old()
                    self.assertEqual(self.status()["phase"], S.F3)
                self.host.running(("a" * 32, "5151"), OLD)
                self.host.signer_running(("b" * 32, "5252"), OLD)
                report = self.status()
                self.assertEqual(report["currentTarget"], f"releases/{OLD}")
                self.assertEqual(report["phase"], S.STOP_RESTARTED)      # returned: the ladder cannot continue
                self.assertEqual(self.private_state(), before)
                if last >= 1:                                            # the staged NEW is removed by its own go
                    shutil.rmtree(self.host.p(f"{I.RELEASES}/{NEW}"))
                self.assertEqual(self.status()["state"], S.OLD_ONLY)

    def tearDown_host(self) -> None:
        self.root = Path(tempfile.mkdtemp(dir=self.out))
        self.host = P3Host(self.root, self.old_payloads)
        self.system = self.host.system()


class FakeOperator(OP.Operator):
    def attach(self, dev) -> "FakeOperator":
        self.dev = dev
        return self

    def pins(self, repo):
        return {"control": "c" * 40, "operatorSha256": "d" * 64, "tools": dict(OP.ALL_PINS),
                "result": "P3_TOOL_PINS_EXACT"}

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


class Dev(FT.Dev):
    """lilith-dev-01, synthetic, with the P3 entry point and forms."""

    def plink(self, command: str, payload: bytes):
        import base64
        import gzip
        import re

        match = re.search(r"grep -qx '([0-9a-f]{64})'.*sudo -n (\S+) -I -B -c \"[^\"]+\" (\S+) (\S+) (.*)\Z", command)
        assert match is not None, command
        digest, interpreter, pins, entry, rest = match.groups()
        assert sha(payload.rstrip(b"\n")) == digest
        sources = json.loads(gzip.decompress(base64.b64decode(payload)))
        declared = dict(item.split("=", 1) for item in pins.split(","))
        assert list(sources) == list(declared) and all(sha(s.encode()) == declared[n] for n, s in sources.items())
        assert entry == "owner_prod_release_stages" and interpreter == OP.M9.SYSTEM_PYTHON
        assert list(sources) == [Path(p).stem for p in OP.STAGES_BUNDLE]
        args = rest.split()
        assert args[1:3] == [OLD, NEW], args
        if args[0] != "p3-status":
            self.mutations.append(args[0])
        t = self.test
        try:
            if args[0] == "p3-status":
                report = t.status()
            elif args[0] == "p3-stage":
                assert args[4:] == [f"{OP.TRANSFER_DIR}/release-{NEW}.tar.gz", f"{OP.TRANSFER_DIR}/release-{NEW}.json"]
                report = t.stage(args[3])
            elif args[0] == "p3-select":
                report = t.select()
            else:
                assert args[0] == "p3-retire-old"
                report = t.retire(args[3], args[4])
        except I.InstallError as exc:
            return done(2, err=f"owner_prod_release_stages: REFUSED {exc.reason}\n".encode())
        return done(0 if report["result"] == "PASS" else 1, out=json.dumps(report).encode())

    def invoke(self, command: str):
        self.mutations.append(command)
        selected = (self.host.root / "opt/lilith-authority-dev/current").readlink().name
        if command == OP.SIGNER_STOP_COMMAND:
            self.host.signer_stopped()
        elif command == OP.WITNESS_STOP_COMMAND:
            self.host.stopped()
        elif command == OP.WITNESS_START_COMMAND:
            self.host.running(NEW_WITNESS, selected)
        elif command == OP.SIGNER_START_COMMAND:
            self.host.signer_running(NEW_SIGNER, selected)
        else:
            raise AssertionError(command)
        return done()


@unittest.skipUnless(T19.POSIX, "release trees need POSIX modes and symlinks")
class OperatorTests(Base):
    def setUp(self):
        super().setUp()
        self.work = Path(tempfile.mkdtemp(dir=self.out))
        self.dev = Dev(self)
        self.op = FakeOperator(new_manifest=self.manifest).attach(self.dev)
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
        self.assertEqual(verified["result"], f"P3_{kind}_VERIFIED", verified["reasons"])
        statement = self.work / f"accept-{kind}.txt"
        statement.write_bytes(self.op.render(self.repo, self.work, "ACCEPT_" + kind)["text"].encode("ascii"))
        return self.op._accept(self.repo, self.work, kind, statement)

    def stop(self, reason: str, call, *args):
        with self.assertRaises(OP.Stop) as caught:
            call(*args)
        self.assertIn(reason, str(caught.exception))

    def to(self, last: str) -> None:
        self.assertEqual(self.op.preflight(self.repo, self.work)["result"], "P3_PREFLIGHT_EXACT")
        for step in OP.ORDER[:OP.ORDER.index(last) + 1]:
            if step == "SIGNER_START":
                self.accept("WITNESS")
            if step == "RETIRE":
                self.accept("SIGNER")
            self.assertTrue(self.run_step(step)["result"].startswith(f"P3_{step}_REACHED"), step)

    def test_the_full_mocked_transition_f0_to_f7(self):
        before = self.private_state()
        phases = [self.op.preflight(self.repo, self.work)["result"]]
        for step in OP.ORDER:
            if step == "SIGNER_START":
                self.accept("WITNESS")
            if step == "RETIRE":
                self.accept("SIGNER")
            record = self.run_step(step)
            self.assertEqual(record["result"], f"P3_{step}_REACHED_{record['expected']}", record)
            phases.append(record["postPhase"])
        self.assertEqual(phases, ["P3_PREFLIGHT_EXACT", *S.PHASES[1:]])
        self.assertEqual(self.dev.mutations, [
            "p3-stage", OP.SIGNER_STOP_COMMAND, OP.WITNESS_STOP_COMMAND, "p3-select", OP.WITNESS_START_COMMAND,
            OP.SIGNER_START_COMMAND, "p3-retire-old"])
        self.assertFalse((self.root / f"opt/lilith-authority-dev/releases/{OLD}").exists())
        markers = sorted(p.name for p in (self.work / OP.M6.ATTEMPT_DIR).iterdir())
        self.assertEqual(markers, sorted(f"{m}.json" for _s, _p, _q, m in OP.STEPS.values()))
        self.assertEqual(self.private_state(), before)

    def test_every_go_names_the_p3_release_and_only_its_own_step(self):
        self.to("SELECT")
        self.op.status(self.repo, self.work, "F4")
        text = self.op.render(self.repo, self.work, "WITNESS_START")["text"]
        self.assertIn("exactly one K-WIT and one K-PAN load", text)
        self.assertIn("(its 2 changed members)", text)
        self.assertIn(P3.NEW_RELEASE_ATTESTATION["archiveSha256"], text)
        self.assertIn(P3.MODE, text)
        self.assertNotIn("PROD release", text)
        self.run_step("WITNESS_START")
        self.op.status(self.repo, self.work, "F5")
        self.stop("WITNESS_ACCEPTANCE_REQUIRED", self.op.render, self.repo, self.work, "SIGNER_START")

    def test_a_changed_anchor_or_credential_is_never_a_verified_witness(self):
        self.to("WITNESS_START")
        (self.host.p(S.ANCHOR_DIR) / "chain/00000002.json").write_bytes(b"{}")
        verified = self.op.verify(self.repo, self.work, "WITNESS")
        self.assertEqual(verified["result"], "P3_WITNESS_STOP")
        self.assertIn("ANCHOR_STATE_CHANGED", verified["reasons"])
        self.stop("WITNESS_NOT_VERIFIED", self.op.render, self.repo, self.work, "ACCEPT_WITNESS")

    def test_retire_refuses_before_consuming_its_go_while_old_is_in_use(self):
        self.to("SIGNER_START")
        self.accept("SIGNER")
        self.op.status(self.repo, self.work, "F6")
        go = self.go("RETIRE")
        stray = self.root / "proc/999"
        stray.mkdir()
        (stray / "cwd").symlink_to(f"{I.RELEASES}/{OLD}")
        self.stop("OLD_RELEASE_IN_USE:999", self.op._step, self.repo, self.work, "RETIRE", go)
        self.assertFalse((self.work / OP.M6.ATTEMPT_DIR / "p3-retire.json").exists())
        self.assertNotIn("p3-retire-old", self.dev.mutations)

    def test_an_unexpected_incarnation_refuses_the_preflight(self):
        self.host.signer_running(("7" * 32, "77"), OLD)
        self.assertEqual(self.op.preflight(self.repo, self.work)["result"], "P3_PREFLIGHT_STOP")
        self.stop("LATEST_PREFLIGHT_NOT_EXACT", self.op.render, self.repo, self.work, "STAGE")
        self.assertEqual(self.dev.mutations, [])

    def test_steps_never_run_out_of_order_or_twice(self):
        self.assertEqual(self.op.preflight(self.repo, self.work)["result"], "P3_PREFLIGHT_EXACT")
        self.op.status(self.repo, self.work, "F0")
        for step in OP.ORDER[1:]:
            with self.subTest(step):
                self.stop("EARLIER_STEP_NOT_REACHED", self.op.render, self.repo, self.work, step)
        go = self.go("STAGE")
        self.op._step(self.repo, self.work, "STAGE", go)
        self.stop("ATTEMPT_ALREADY_CONSUMED:p3-stage", self.op._step, self.repo, self.work, "STAGE", go)
        self.assertEqual(self.dev.mutations, ["p3-stage"])

    def test_a_mutation_failure_is_a_stop_with_no_retry(self):
        self.to("STAGE")
        self.op.status(self.repo, self.work, "F1")
        go = self.go("SIGNER_STOP")
        self.dev.invoke = lambda command: (self.dev.mutations.append(command), done(1))[1]   # the stop fails
        record = self.op._step(self.repo, self.work, "SIGNER_STOP", go)
        self.assertEqual(record["result"], "P3_SIGNER_STOP_STOP")
        self.assertIn("no retry", record["next"])
        self.assertEqual(self.dev.mutations.count(OP.SIGNER_STOP_COMMAND), 1)
        self.stop("STEP_NOT_REACHED:SIGNER_STOP", self.op.render, self.repo, self.work, "WITNESS_STOP")

    def test_a_crashed_post_read_counts_only_after_one_clean_independent_recheck(self):
        self.to("SELECT")
        self.op.status(self.repo, self.work, "F4")
        go = self.go("WITNESS_START")
        plink, state = self.dev.plink, {"n": 0}

        def crash_once(command, payload):
            result = plink(command, payload)
            if "p3-status" in command and OP.WITNESS_START_COMMAND in self.dev.mutations and state["n"] == 0:
                state["n"] = 1
                return done(OP.CLIENT_EXIT_CRASH, out=result.stdout)
            return result

        self.dev.plink = crash_once
        record = self.op._step(self.repo, self.work, "WITNESS_START", go)
        self.assertEqual((record["result"], record["postPhase"]), ("P3_WITNESS_START_REACHED_F5_WITNESS_RUNNING", S.F5))
        self.assertTrue(record["postRecheck"].endswith("WITNESS_START_POST_RECHECK"))
        self.assertEqual(self.dev.mutations.count(OP.WITNESS_START_COMMAND), 1)


class TransformTests(unittest.TestCase):
    def test_the_p3_tools_are_the_fm2_tools_moved_by_exactly_the_transform(self):
        values = {"contract": sha((TOOLS / "owner_prod_signer_upgrade.py").read_bytes()),
                  "stages": sha((TOOLS / "owner_prod_release_stages.py").read_bytes())}
        for name, blocks in (("release_stages", X.STAGES_BLOCKS), ("operator", X.OPERATOR_BLOCKS)):
            with self.subTest(name):
                fm2 = (TOOLS / f"fm2_{name}.py").read_text(encoding="utf-8")
                p3 = (TOOLS / f"owner_prod_{name}.py").read_text(encoding="utf-8")
                self.assertEqual(X.body(p3), X.transform(X.body(fm2), blocks, **values))

    def test_the_fm2_tools_are_byte_unchanged(self):
        self.assertEqual(sha((TOOLS / "fm2_release_stages.py").read_bytes()),
                         "15a2594fb08b043645693d0e36abbb405a48dedc9fbf7eb3e43d828ebea866aa")
        self.assertEqual(sha((TOOLS / "fm2_signer_upgrade.py").read_bytes()),
                         "fe2e5fb80f1a5706fca0e591f515b8af11fd191fe240ef58aa05adce2075b584")


class PinTests(unittest.TestCase):
    def test_no_adjudicated_step_and_the_one_known_client_crash_rule(self):
        self.assertEqual(OP.ADJUDICATED_STEPS, {})
        self.assertEqual(OP.CLIENT_EXIT_CRASH, 3221225477)

    def test_releases_and_ending_incarnations_are_the_fm2_accepted_ones(self):
        self.assertEqual((OLD, P3.OLD_MANIFEST_SHA256), (FM2.NEW_RELEASE, FM2.NEW_MANIFEST_SHA256))
        self.assertEqual(NEW, "88a1168bd41797109772ffce7df7352c1ae40e4c")
        self.assertEqual(S.ENDING_SIGNER_INCARNATION, ("c32457250aff4155bce1f54f1648945f", "309023"))
        self.assertEqual(S.ENDING_WITNESS_INCARNATION, ("1089ad88e0eb4c55b167a48cdb898aa1", "308690"))
        fm2 = " ".join((ROOT / "docs/architecture/personal-memory-fm2-dev-activation.md").read_text(
            encoding="utf-8").split())
        self.assertIn(f"Witness `{S.ENDING_WITNESS_INCARNATION[0]}` / {S.ENDING_WITNESS_INCARNATION[1]}", fm2)
        self.assertIn(f"signer `{S.ENDING_SIGNER_INCARNATION[0]}` / {S.ENDING_SIGNER_INCARNATION[1]}", fm2)
        record = (ROOT / "docs/architecture/canonical-memory-p3-dev-transition.md").read_text(encoding="utf-8")
        for value in P3.NEW_RELEASE_ATTESTATION.values():
            self.assertIn(str(value), record)
        for value in (P3.NEW_RELEASE, P3.NEW_MANIFEST_SHA256, *S.ENDING_SIGNER_INCARNATION,
                      *S.ENDING_WITNESS_INCARNATION):
            self.assertIn(value, record)

    def test_layout_v3_binding_equals_the_v3_installer(self):
        import install_authority_dev_v3 as V3

        with S.layout_v3():
            self.assertEqual(I.EXPECTED_PATHS, V3.EXPECTED_PATHS)
        self.assertEqual(frozenset(P3.LAYOUT_ADDED), V3.ADDED_RUNTIME_PATHS)

    def test_operator_pins_and_bundle(self):
        for path, pin in OP.TOOL_PINS.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)
        for path, pin in OP.E23OP.ALL_PINS.items():
            self.assertEqual(OP.ALL_PINS[path], pin, path)
        self.assertEqual(OP.STAGES_BUNDLE[:-4], OP.E23OP.STAGES_BUNDLE)
        self.assertEqual([Path(p).stem for p in OP.STAGES_BUNDLE[-4:]],
                         ["fm1_signer_upgrade", "fm2_signer_upgrade", "owner_prod_signer_upgrade",
                          "owner_prod_release_stages"])
        self.assertEqual(OP.TRANSFER_DIR.rsplit("/", 1)[1], "lilith-p3-transfer")

    def test_bundled_modules_never_touch_sys_path(self):
        for name in ("owner_prod_release_stages", "owner_prod_signer_upgrade"):
            source = (TOOLS / f"{name}.py").read_text(encoding="utf-8")
            module = types.ModuleType(name)
            module.__file__ = f"<mb6-bundle:{name}>"
            before = list(sys.path)
            with mock.patch.dict(sys.modules, {"fm2_signer_upgrade": FM2}):
                exec(compile(source, module.__file__, "exec"), module.__dict__)  # noqa: S102 - the reviewed source
            self.assertEqual(sys.path, before, name)

    def test_the_p3_tools_never_start_stop_reload_read_a_credential_or_name_prod(self):
        source = (TOOLS / "owner_prod_release_stages.py").read_text(encoding="utf-8")
        for needle in ("\"start\"", "\"stop\"", "\"restart\"", "\"enable\"", "daemon-reload", "systemd-tmpfiles",
                       "systemd-creds", "subprocess", "open("):
            self.assertNotIn(needle, source, needle)
        self.assertEqual(source.count("read_bytes()"), 1)
        for name in ("owner_prod_release_stages.py", "owner_prod_operator.py", "owner_prod_signer_upgrade.py"):
            text = (TOOLS / name).read_text(encoding="utf-8")
            for needle in ("deployment.json", "lilith-01", "prod.", "LILITH_ENV"):
                self.assertNotIn(needle, text, (name, needle))


if __name__ == "__main__":
    unittest.main()
