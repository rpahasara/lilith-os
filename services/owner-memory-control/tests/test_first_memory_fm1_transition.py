"""First Memory FM-1 (F0 … F7): `fm1_release_stages` and `fm1_operator` on the E-23 fake-systemd DEV root.

Record: docs/architecture/first-memory-fm1-release-transition.md. TEST-ONLY: the host is the E-23 synthetic root
(`test_trackb_e23_release_stages.E23Host`) moved to the post-E-23 shape (57bff671 installed, E-23 witness units loaded,
K-PAN present, the Privacy anchor v1 chain written); NEW is the repository (e2324a5) payload in archive layout v3. The
operator's transport seams deliver every BOOT bundle to the REAL stage tool and every reviewed unit command to the
fake units. Nothing contacts DEV, runs systemctl, opens a socket or touches a credential.
"""

from __future__ import annotations

import base64
import contextlib
import gzip
import hashlib
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
for _p in (TOOLS, HERE, ROOT / "services/authority-dev/ceremony"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import test_trackb_e23_release_stages as H  # noqa: E402  (the E-23 fake-systemd host and fixtures)
from test_trackb_e23_release_stages import E23, I, IL, T19  # noqa: E402

import fm1_operator as OP  # noqa: E402
import fm1_release_stages as S  # noqa: E402
import fm1_signer_upgrade as FM1  # noqa: E402

OLD, NEW = FM1.OLD_RELEASE, FM1.NEW_RELEASE
NEW_SIGNER = ("5" * 32, "4242")
NEW_WITNESS = ("6" * 32, "4343")
ANCHOR_V1 = b'{"synthetic":"anchor v1"}'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def done(code=0, out=b"", err=b""):
    return subprocess.CompletedProcess([], code, out, err)


class FM1Host(H.E23Host):
    """The synthetic root at F0: 57bff671 selected with its (E-23 NEW) witness unit files loaded, K-WIT and K-PAN
    present, the anchor directory holding the v1 chain, and the E-23 accepted signer and witness running from OLD."""

    def __init__(self, root: Path, old_payloads: dict[str, bytes]):  # noqa: D107
        with mock.patch.object(H, "OLD", OLD):                          # the E-23 host, installed at 57bff671
            super().__init__(root, old_payloads)
        self.keygen()                                                   # K-PAN (E-23 E5 onward)
        anchor = self.p(S.ANCHOR_DIR)
        (anchor / "chain").mkdir(parents=True)
        os.chmod(anchor, 0o700)
        (anchor / "anchor.lock").write_bytes(b"")
        (anchor / "chain/00000001.json").write_bytes(ANCHOR_V1)       # Privacy genesis (v1)
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
        import build_authority_dev_release as B

        self.old_payloads = IL._build_v2(ROOT, house)                   # the installed 57bff671 payload
        self.new_payloads = B.build_payloads(ROOT, house)                # the e2324a5 payload (layout v3)
        self.host = FM1Host(self.root, self.old_payloads)
        self.system = self.host.system()
        with S.layout_v3():
            self.archive, self.stamp, self.manifest = T19.archive_for(self.out, NEW, self.new_payloads)
        # Stand-in wheels: the archive cannot carry the attested manifest; only the manifest pin is patched (the delta
        # pins and NEW are the merged contract's).
        stack.enter_context(mock.patch.object(FM1, "NEW_MANIFEST_SHA256", self.manifest))
        stack.enter_context(mock.patch.object(S.I, "verify_archive", self.verify_v3))

    def verify_v3(self, archive, attestation, expected):
        assert set(FM1.PAYLOAD_ADDED) | set(E23.PAYLOAD_ADDED) <= I.EXPECTED_PATHS, "stage must bind layout v3"
        return VERIFY(archive, attestation, expected)

    def status(self):
        return S.fm1_status(self.system, OLD, NEW, status=self.host.status)

    def stage(self, manifest=None, archive=None, stamp=None):
        return S.stage_fm1_stage(self.system, OLD, NEW, manifest or self.manifest, archive or self.archive,
                                 stamp or self.stamp, status=self.host.status)

    def select(self):
        return S.stage_fm1_select(self.system, OLD, NEW, status=self.host.status)

    def retire(self, signer=NEW_SIGNER[0], witness=NEW_WITNESS[0]):
        return S.stage_fm1_retire_old(self.system, OLD, NEW, signer, witness, status=self.host.status)

    def refused(self, prefix, call, *args, **kwargs):
        with self.assertRaises(I.InstallError) as caught:
            call(*args, **kwargs)
        self.assertTrue(caught.exception.reason.startswith(prefix), caught.exception.reason)


@unittest.skipUnless(T19.POSIX, "release trees need POSIX modes and symlinks")
class StageTests(Base):
    def test_f0_is_the_post_e23_host(self):
        report = self.status()
        self.assertEqual((report["state"], report["result"], report["phase"]), (S.OLD_ONLY, "PASS", S.F0),
                         report["failures"])
        self.assertEqual((report["kPan"], report["witnessUnits"], report["witnessCredentials"]),
                         ("PRESENT_EXACT", "NEW", S.WITNESS_CREDENTIALS))
        self.assertEqual(report["anchor"]["chain"], {"00000001.json": sha(ANCHOR_V1)})
        self.assertEqual(sorted(report["oldReleaseUsers"]), sorted([S.ENDING_SIGNER_INCARNATION[1],
                                                                    S.ENDING_WITNESS_INCARNATION[1]]))

    def test_the_full_f0_to_f7_rehearsal_stops_both_units_before_the_select(self):
        before, anchor = self.host.snapshot(), self.status()["anchor"]
        seen = [self.status()["phase"], self.stage()["phase"]]
        self.host.signer_stopped()
        seen.append(self.status()["phase"])
        self.host.stopped()
        seen.append(self.status()["phase"])
        seen.append(self.select()["phase"])
        self.host.running(NEW_WITNESS, NEW)                              # one start: K-WIT + K-PAN, unchanged payload
        seen.append(self.status()["phase"])
        self.host.signer_running(NEW_SIGNER, NEW)                        # one start: K-ACT
        seen.append(self.status()["phase"])
        retired = self.retire()
        seen.append(retired["phase"])
        self.assertEqual(seen, list(S.PHASES))
        self.assertEqual((retired["state"], retired["result"], retired["oldReleaseUsers"]), (S.RETIRED, "PASS", []))
        self.assertFalse(self.host.p(f"{I.RELEASES}/{OLD}").exists())
        self.assertEqual(self.host.snapshot(), before)                  # custody, ledger, witness state untouched
        self.assertEqual(retired["anchor"], anchor)                     # the Privacy anchor chain untouched
        self.assertEqual(retired["foreignUnits"], H.FOREIGN)
        mutating = [c for c in self.host.calls if Path(c[0]).name in ("systemctl", "systemd-tmpfiles")
                    and c[1] != "show"]
        self.assertEqual(mutating, [])                                   # no reload, no tmpfiles, no start / stop

    def test_select_needs_both_units_stopped_a_witness_on_old_never_crosses_the_selector(self):
        self.stage()
        self.refused("FM1_PRE_PHASE:F1_NEW_STAGED", self.select)
        self.host.signer_stopped()
        self.refused("FM1_PRE_PHASE:F2_SIGNER_STOPPED", self.select)    # the witness still runs from OLD
        self.assertEqual(os.readlink(self.root / "opt/lilith-authority-dev/current"), f"releases/{OLD}")
        self.host.stopped()
        self.select()
        # If the OLD witness were still running here, `Restart=on-failure` would bring it back from NEW unapproved:
        self.host.running(S.ENDING_WITNESS_INCARNATION, OLD)
        self.assertEqual(self.status()["phase"], S.STOP_ACROSS_SELECT)
        self.host.running(S.ENDING_WITNESS_INCARNATION, NEW)            # an automatic restart into NEW
        self.host.units[S.WITNESS_SERVICE]["NRestarts"] = "1"
        self.assertEqual(self.status()["phase"], S.STOP_RESTARTED)

    def test_old_cannot_be_retired_while_anything_uses_it(self):
        self.stage()
        self.host.signer_stopped()
        self.host.stopped()
        self.select()
        self.host.running(NEW_WITNESS, NEW)
        self.refused("FM1_PRE_PHASE:F5_WITNESS_RUNNING", self.retire)  # signer not yet replaced
        self.host.signer_running(NEW_SIGNER, NEW)
        self.refused("FM1_REPLACEMENT_INVOCATION_INVALID", self.retire, S.ENDING_SIGNER_INCARNATION[0])
        self.refused("FM1_ACCEPTED_REPLACEMENTS_NOT_RUNNING", self.retire, "8" * 32)
        stray = self.root / "proc/999"
        stray.mkdir()
        (stray / "maps").write_text(f"7f00-7f10 r-xp 0 08:01 1 {I.RELEASES}/{OLD}/venv/lib/x.so\n", encoding="ascii")
        self.assertEqual(self.status()["oldReleaseUsers"], ["999"])
        self.refused("FM1_OLD_RELEASE_IN_USE:999", self.retire)
        self.assertTrue(self.host.p(f"{I.RELEASES}/{OLD}").is_dir())
        (stray / "maps").unlink()
        self.assertEqual(self.retire()["phase"], S.F7)

    def test_stage_refuses_any_other_payload_or_manifest(self):
        cases = {
            "a witness member": {**self.new_payloads, "lilith_recovery_witness/server.py":
                                 self.new_payloads["lilith_recovery_witness/server.py"] + b"\n"},
            "a signer member unchanged": {**self.new_payloads, "lilith_authority_dev/core.py":
                                          self.old_payloads["lilith_authority_dev/core.py"]},
        }
        for label, payloads in cases.items():
            with self.subTest(label=label):
                out = Path(tempfile.mkdtemp(dir=self.out))
                with S.layout_v3():
                    archive, stamp, manifest = T19.archive_for(out, NEW, payloads)
                self.refused("FM1_MANIFEST_PIN_INVALID", self.stage, manifest, archive, stamp)
                with mock.patch.object(FM1, "NEW_MANIFEST_SHA256", manifest):
                    self.refused("FM1_PAYLOAD_DELTA", self.stage, manifest, archive, stamp)
        self.assertEqual(sorted(os.listdir(self.root / "opt/lilith-authority-dev/releases")), [OLD])
        self.stage()
        self.refused("FM1_PRE_PHASE:F1_NEW_STAGED", self.stage)          # never re-run, never overwritten

    def test_credentials_units_and_anchor_are_stops_in_every_phase(self):
        os.chmod(self.host.p(S.KPAN_BLOB), 0o640)
        self.assertEqual(self.status()["phase"], S.STOP_KPAN)
        os.chmod(self.host.p(S.KPAN_BLOB), 0o600)
        target = H.S.WITNESS_HOST_FILES["assets/lilith-recovery-witness.service"]
        saved = self.host.p(target).read_bytes()
        self.host.write(target, saved + b"\n")                           # a unit edit (reload pending)
        self.assertEqual(self.status()["phase"], S.STOP_UNITS)
        self.host.write(target, saved)
        (self.host.p(S.ANCHOR_DIR) / "unexpected").write_bytes(b"")
        self.assertEqual(self.status()["phase"], S.STOP_UNITS)
        (self.host.p(S.ANCHOR_DIR) / "unexpected").unlink()
        self.assertEqual(self.status()["phase"], S.F0)
        self.refused("FM1_OLD_RELEASE_NOT_THE_INSTALLED_RELEASE", S.fm1_status, self.system, E23.OLD_RELEASE, NEW)
        self.refused("FM1_NEW_RELEASE_NOT_THE_PINNED_RELEASE", S.fm1_status, self.system, OLD, "b" * 40)

    def test_a_non_dev_host_is_refused_by_every_form(self):
        system = self.host.system(hostname=lambda: "lilith-prod-01")
        for form in (["fm1-stage", OLD, NEW, self.manifest, str(self.archive), str(self.stamp)],
                     ["fm1-select", OLD, NEW], ["fm1-status", OLD, NEW], ["fm1-retire-old", OLD, NEW, "5" * 32,
                                                                          "6" * 32]):
            with self.subTest(form=form[0]):
                self.assertEqual(S.main(form, system=system), 2)
        self.assertEqual(S.main(["fm1-witness-units", OLD, NEW], system=self.system), 2)


VERIFY = I.verify_archive


class Dev:
    """lilith-dev-01, synthetic: bundles run the real stage tool; plain commands move the fake units."""

    def __init__(self, test: Base):
        self.test, self.host = test, test.host
        self.mutations: list[str] = []

    def plink(self, command: str, payload: bytes):
        match = re.search(r"grep -qx '([0-9a-f]{64})'.*sudo -n (\S+) -I -B -c \"[^\"]+\" (\S+) (\S+) (.*)\Z", command)
        assert match is not None, command
        digest, interpreter, pins, entry, rest = match.groups()
        assert sha(payload.rstrip(b"\n")) == digest
        sources = json.loads(gzip.decompress(base64.b64decode(payload)))
        declared = dict(item.split("=", 1) for item in pins.split(","))
        assert list(sources) == list(declared) and all(sha(s.encode()) == declared[n] for n, s in sources.items())
        assert entry == "fm1_release_stages" and interpreter == OP.M9.SYSTEM_PYTHON
        assert list(sources) == [Path(p).stem for p in OP.STAGES_BUNDLE]
        args = rest.split()
        assert args[1:3] == [OLD, NEW], args
        if args[0] != "fm1-status":
            self.mutations.append(args[0])
        t = self.test
        try:
            if args[0] == "fm1-status":
                report = t.status()
            elif args[0] == "fm1-stage":
                assert args[4:] == [f"{OP.TRANSFER_DIR}/release-{NEW}.tar.gz", f"{OP.TRANSFER_DIR}/release-{NEW}.json"]
                report = t.stage(args[3])
            elif args[0] == "fm1-select":
                report = t.select()
            else:
                assert args[0] == "fm1-retire-old"
                report = t.retire(args[3], args[4])
        except I.InstallError as exc:
            return done(2, err=f"fm1_release_stages: REFUSED {exc.reason}\n".encode())
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


class FakeOperator(OP.Operator):
    def attach(self, dev: Dev) -> "FakeOperator":
        self.dev = dev
        return self

    def pins(self, repo):
        return {"control": "c" * 40, "operatorSha256": "d" * 64, "tools": dict(OP.ALL_PINS),
                "result": "FM1_TOOL_PINS_EXACT"}

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
        self.assertEqual(verified["result"], f"FM1_{kind}_VERIFIED", verified["reasons"])
        statement = self.work / f"accept-{kind}.txt"
        statement.write_bytes(self.op.render(self.repo, self.work, "ACCEPT_" + kind)["text"].encode("ascii"))
        return self.op._accept(self.repo, self.work, kind, statement)

    def stop(self, reason: str, call, *args):
        with self.assertRaises(OP.Stop) as caught:
            call(*args)
        self.assertIn(reason, str(caught.exception))

    def to(self, last: str) -> None:
        self.assertEqual(self.op.preflight(self.repo, self.work)["result"], "FM1_PREFLIGHT_EXACT")
        for step in OP.ORDER[:OP.ORDER.index(last) + 1]:
            if step == "SIGNER_START":
                self.accept("WITNESS")
            if step == "RETIRE":
                self.accept("SIGNER")
            self.assertTrue(self.run_step(step)["result"].startswith(f"FM1_{step}_REACHED"), step)

    def test_the_full_mocked_transition_f0_to_f7(self):
        phases = [self.op.preflight(self.repo, self.work)["result"]]
        for step in OP.ORDER:
            if step == "SIGNER_START":
                self.accept("WITNESS")
            if step == "RETIRE":
                self.accept("SIGNER")
            record = self.run_step(step)
            self.assertEqual(record["result"], f"FM1_{step}_REACHED_{record['expected']}", record)
            phases.append(record["postPhase"])
        self.assertEqual(phases, ["FM1_PREFLIGHT_EXACT", *S.PHASES[1:]])
        self.assertEqual(self.dev.mutations, [
            "fm1-stage", OP.SIGNER_STOP_COMMAND, OP.WITNESS_STOP_COMMAND, "fm1-select", OP.WITNESS_START_COMMAND,
            OP.SIGNER_START_COMMAND, "fm1-retire-old"])
        self.assertFalse((self.root / f"opt/lilith-authority-dev/releases/{OLD}").exists())
        markers = sorted(p.name for p in (self.work / OP.M6.ATTEMPT_DIR).iterdir())
        self.assertEqual(markers, sorted(f"{m}.json" for _s, _p, _q, m in OP.STEPS.values()))

    def test_the_witness_start_go_names_both_credential_loads_and_the_signer_needs_its_acceptance(self):
        self.to("SELECT")
        self.op.status(self.repo, self.work, "F4")
        text = self.op.render(self.repo, self.work, "WITNESS_START")["text"]
        self.assertIn("exactly one K-WIT and one K-PAN load", text)
        self.assertIn(f"K-PAN inode {os.lstat(self.host.p(S.KPAN_BLOB)).st_ino}", text)
        self.run_step("WITNESS_START")
        self.op.status(self.repo, self.work, "F5")
        self.stop("WITNESS_ACCEPTANCE_REQUIRED", self.op.render, self.repo, self.work, "SIGNER_START")

    def test_a_changed_anchor_or_credential_is_never_a_verified_witness(self):
        self.to("WITNESS_START")
        (self.host.p(S.ANCHOR_DIR) / "chain/00000002.json").write_bytes(b"{}")     # an anchor write: never FM-1's
        verified = self.op.verify(self.repo, self.work, "WITNESS")
        self.assertEqual(verified["result"], "FM1_WITNESS_STOP")
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
        self.assertFalse((self.work / OP.M6.ATTEMPT_DIR / "fm1-retire.json").exists())     # go not consumed
        self.assertNotIn("fm1-retire-old", self.dev.mutations)
        self.assertTrue((self.root / f"opt/lilith-authority-dev/releases/{OLD}").is_dir())

    def test_an_unexpected_incarnation_refuses_the_preflight(self):
        self.host.signer_running(("7" * 32, "77"), OLD)
        self.assertEqual(self.op.preflight(self.repo, self.work)["result"], "FM1_PREFLIGHT_STOP")
        self.stop("LATEST_PREFLIGHT_NOT_EXACT", self.op.render, self.repo, self.work, "STAGE")
        self.assertEqual(self.dev.mutations, [])

    def test_an_owner_adjudicated_stage_stop_continues_only_from_an_exact_fresh_gate(self):
        """The 2026-10-26 recovery: the stage ran (F1) but the post-status read crashed locally, so STEP.json says STOP.
        Only the pinned record digest unblocks the chain; the next step still needs its own fresh F1 gate; the stage
        never re-runs."""
        self.assertEqual(self.op.preflight(self.repo, self.work)["result"], "FM1_PREFLIGHT_EXACT")
        self.op.status(self.repo, self.work, "STAGE_GATE")
        go = self.go("STAGE")
        original = self.dev.plink

        def crash_post(command, payload, state={"stage": False}):
            result = original(command, payload)
            if "fm1-stage" in command:
                state["stage"] = True
            elif state["stage"] and "fm1-status" in command and result.returncode == 0:
                state["stage"] = False
                return done(0xC0000005, out=result.stdout)    # complete output; the local client crashed on exit
            return result

        self.dev.plink = crash_post
        record = self.op._step(self.repo, self.work, "STAGE", go)
        self.dev.plink = original
        self.assertEqual((record["result"], record["code"], record["postPhase"]),
                         ("FM1_STAGE_STOP", 0, "STATUS_NOT_RECEIVED"))
        self.assertEqual(self.status()["phase"], S.F1)                    # the host is exactly F1
        digest = sha((next((self.work / OP.STEP_DIR).glob("*-STAGE")) / OP.STEP_FILE).read_bytes())
        self.op.status(self.repo, self.work, "F1_RECHECK")
        self.stop("STEP_NOT_REACHED:STAGE", self.op.render, self.repo, self.work, "SIGNER_STOP")
        with mock.patch.dict(OP.ADJUDICATED_STEPS, {"STAGE": "0" * 64}):
            self.stop("STEP_NOT_REACHED:STAGE", self.op.render, self.repo, self.work, "SIGNER_STOP")
        with mock.patch.dict(OP.ADJUDICATED_STEPS, {"STAGE": digest}):
            self.host.signer_stopped()                                   # not F1: the fresh gate refuses
            self.op.status(self.repo, self.work, "NOT_F1")
            self.stop("LATEST_STATUS_NOT_F1_NEW_STAGED", self.op.render, self.repo, self.work, "SIGNER_STOP")
            self.host.signer_running(S.ENDING_SIGNER_INCARNATION, OLD)
            for step in OP.ORDER[1:]:
                if step == "SIGNER_START":
                    self.accept("WITNESS")
                if step == "RETIRE":
                    self.accept("SIGNER")
                self.assertTrue(self.run_step(step)["result"].startswith(f"FM1_{step}_REACHED"), step)
            self.stop("ATTEMPT_ALREADY_CONSUMED:fm1-stage", self.op._step, self.repo, self.work, "STAGE", go)
        self.assertEqual(self.dev.mutations.count("fm1-stage"), 1)
        self.assertFalse((self.root / f"opt/lilith-authority-dev/releases/{OLD}").exists())


class PinTests(unittest.TestCase):
    def test_the_only_adjudication_is_the_recorded_stage_stop(self):
        self.assertEqual(set(OP.ADJUDICATED_STEPS), {"STAGE"})
        self.assertRegex(OP.ADJUDICATED_STEPS["STAGE"], r"\A[0-9a-f]{64}\Z")
        record = (ROOT / "docs/architecture/first-memory-fm1-release-transition.md").read_text(encoding="utf-8")
        self.assertIn(OP.ADJUDICATED_STEPS["STAGE"], record)

    def test_the_delta_is_the_git_bytes_of_57bff671_against_the_repository(self):
        import install_authority_dev_v3 as V3
        import release_file_set as RFS

        source_of = {target: source for source, target in RFS.RUNTIME_SOURCE_MAP.items()}
        repo = RFS.runtime_payloads(ROOT)
        for member, (before, after) in FM1.PAYLOAD_DELTA.items():
            self.assertEqual(sha(IL.old_source_bytes(source_of[member], IL.E23_RELEASE)), before, member)
            self.assertEqual(sha(repo[member]), after, member)
        for member, after in FM1.PAYLOAD_ADDED.items():
            self.assertEqual(sha(repo[member]), after, member)
        self.assertEqual(frozenset(FM1.PAYLOAD_ADDED), V3.ADDED_RUNTIME_PATHS)
        changed = {m for m in repo if m not in FM1.PAYLOAD_ADDED
                   and IL.old_source_bytes(source_of[m], IL.E23_RELEASE) != repo[m]}
        self.assertEqual(changed, set(FM1.PAYLOAD_DELTA))               # nothing else moved, no witness member
        self.assertFalse(any("witness" in member for member in FM1.PAYLOAD_DELTA))

    def test_layout_v3_binding_equals_the_v3_installer(self):
        import install_authority_dev_v3 as V3

        with S.layout_v3():
            self.assertEqual(I.EXPECTED_PATHS, V3.EXPECTED_PATHS)
        self.assertEqual(I.EXPECTED_PATHS, V3.EXPECTED_PATHS - V3.ADDED_RUNTIME_PATHS - E23.PAYLOAD_ADDED.keys())

    def test_releases_and_ending_incarnations_are_the_e23_accepted_ones(self):
        self.assertEqual((OLD, FM1.OLD_MANIFEST_SHA256), (E23.NEW_RELEASE, E23.NEW_MANIFEST_SHA256))
        self.assertEqual(NEW, "e2324a5f89200aa5f374c4a43a13cb76b36376f9")
        record = (ROOT / "docs/architecture/trackb-e23-completion.md").read_text(encoding="utf-8")
        self.assertIn(f"witness `{S.ENDING_WITNESS_INCARNATION[0]}` / {S.ENDING_WITNESS_INCARNATION[1]}", record)
        self.assertIn(f"signer `{S.ENDING_SIGNER_INCARNATION[0]}` / {S.ENDING_SIGNER_INCARNATION[1]}", record)

    def test_operator_pins_and_bundle(self):
        for path, pin in OP.TOOL_PINS.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)
        for path, pin in OP.E23OP.ALL_PINS.items():
            self.assertEqual(OP.ALL_PINS[path], pin, path)              # the E-22 / E-23 chain, unchanged
        self.assertEqual(OP.STAGES_BUNDLE[:-2], OP.E23OP.STAGES_BUNDLE)
        self.assertEqual([Path(p).stem for p in OP.STAGES_BUNDLE[-2:]], ["fm1_signer_upgrade", "fm1_release_stages"])

    def test_bundled_modules_never_touch_sys_path(self):
        for name in ("fm1_release_stages", "fm1_signer_upgrade"):
            source = (TOOLS / f"{name}.py").read_text(encoding="utf-8")
            module = types.ModuleType(name)
            module.__file__ = f"<mb6-bundle:{name}>"
            before = list(sys.path)
            exec(compile(source, module.__file__, "exec"), module.__dict__)  # noqa: S102 - the reviewed source
            self.assertEqual(sys.path, before, name)

    def test_the_stage_tool_never_starts_stops_reloads_or_reads_a_credential(self):
        source = (TOOLS / "fm1_release_stages.py").read_text(encoding="utf-8")
        for needle in ("\"start\"", "\"stop\"", "\"restart\"", "\"enable\"", "daemon-reload", "systemd-tmpfiles",
                       "systemd-creds", "subprocess", "open("):
            self.assertNotIn(needle, source, needle)
        self.assertEqual(source.count("read_bytes()"), 1)               # the public anchor chain files only


if __name__ == "__main__":
    unittest.main()
