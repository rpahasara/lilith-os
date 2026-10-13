"""15B2b-B1b-3e E-19 maintenance observer and two-release-aware verification (TEST-ONLY, synthetic host).

Record: docs/architecture/slice-15b2b-b1b3e-e19-maintenance-observer.md. No live system: the host is a temporary
directory tree; systemd, the journal, the owner CLI, the activation verifier, W10 and the broker read are fakes. The
synthetic custody bytes cannot equal the accepted DEV digests, so the file-digest pins of the merged contract are
patched to the synthetic files' digests for the duration of each test (the drop-in pins are the real ones: the real
candidate files are copied in). The NEW release SHA is synthetic and passed explicitly; the repository pins none.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _p in (TOOLS, ROOT / "services/authority-dev/ceremony", ROOT / "services/owner-memory-control",
           ROOT / "services/core-api"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import e19_maintenance_observer as O  # noqa: E402
import e19_p1b10_upgrade as E  # noqa: E402

POSIX = os.name == "posix"
NEW = hashlib.sha1(b"synthetic NEW release (not built)").hexdigest()
OLD = E.OLD_RELEASE
H32 = lambda label: hashlib.sha256(label.encode()).hexdigest()[:32]  # noqa: E731
REPLACEMENT = (H32("replacement incarnation"), "48211")
SEQ = H32("journal seqnum id")
BOOT_HEX = E.BOOT_ID.replace("-", "")


def cursor(i: str) -> str:
    return f"s={SEQ};i={i};b={BOOT_HEX};m=1a2b;t=5f1e2d3c4b5a6;x=9c8d7e6f"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


FILE_PINS = {   # contract pin -> synthetic host path and bytes
    "kActCurrentBlobSha256": (O.CREDENTIAL, b"synthetic K-ACT ciphertext"),
    "kActPublicationFileSha256": (O.KACT_PUBLICATION, b'{"synthetic":"k-act publication"}\n'),
    "kWitBlobSha256": (O.WITNESS_BLOB, b"synthetic K-WIT ciphertext"),
    "registryRootAnchorSha256": (O.TRUST_DIR + "/registry-root.json", b'{"anchor":"root"}\n'),
    "witnessAnchorSha256": (O.TRUST_DIR + "/witness-anchor.json", b'{"anchor":"witness"}\n'),
    "registrySha256": (O.REGISTRY, b'{"registry":1}\n'),
    "witnessChain1Sha256": (O.WITNESS_STATE + "/chain/1.json", b'{"witness":"genesis"}\n'),
    "witnessJsonSha256": (O.WITNESS_STATE + "/witness.json", b'{"witness":"genesis"}\n'),
    "heldSha256": (f"{O.HOLD_STORE}/{O.HELD_NAME}", b'{"held":"initial custody"}\n'),
}
SYNTHETIC_PINS = {name: sha(data) for name, (_path, data) in FILE_PINS.items()}
OTHER_FILES = {
    O.HOST_KEY: b"host credential key (never read by the observer)",
    O.OWNER_INPUTS[0]: b'{"pin":1}\n', O.OWNER_INPUTS[1]: b'{"register":1}\n',
    O.LEDGER_STATE + "/authority_ledger.db": b"SQLite format 3\x00synthetic",
    **{path: f"unit {path}\n".encode() for path in O.SIGNER_UNIT_FILES + O.WITNESS_UNIT_FILES},
    **{path: f"#!/bin/sh\n# {path}\n".encode() for path in O.CLIS},
}


def health_reply(**override) -> bytes:
    health = {"classification": "CONSISTENT", "publicKeySha256": E.KWIT_PUBLIC_KEY_SHA256,
              "witnessKeyId": E.KWIT_KEY_ID, "inputs": [], "genericSigning": "NOT_AVAILABLE",
              "authorityGranted": False, "environment": "dev"}
    health.update(override)
    return json.dumps({"status": "OK", "health": health}).encode() + b"\n"


W10_EXACT_REPORT = {"phase": "W10_1_HELD_EXACT", "w9PhaseDirect": "W9_LATER_STATE",
                    "w9PhaseHoldJudgedSeparately": "W9_5_GENESIS_COMMITTED_EXACT",
                    "committedGenesisDigest": E.PRESERVED_PINS["witnessGenesis"], "w9Failures": [], "failures": []}
BROKER_PASS = {"BROKER_PRESERVATION": "PASS", "runtimeIncarnation": E.PRESERVED_PINS["brokerInvocationId"],
               "baselineCandidateSha256": E.PRESERVED_PINS["brokerBaselineSha256"]}
DENIALS_PASS = {
    "P1B-9b": (b"DENIED: x\nMB9_WITNESS_DENIAL_PROOF=PASS phase=P1B-9b denied=40 allowed_by_design=2 allowed=0\n", 0),
    "P1B-10": (b"DENIED: y\nMB10_HOLD_DENIAL_PROOF=PASS phase=P1B-10 denied=40 allowed=0\n", 0),
    "P1B-5": (b"DENIED: z\nAUTHORITY_CUSTODY_DENIAL_PROOF=PASS phase=P1B-5\n", 0),
}


class SyntheticHost:
    """A temporary host root plus the fake systemd / journal / CLI / W10 / broker seams, mutated per phase."""

    def __init__(self, root: Path):
        import install_authority_dev as I

        self.I, self.root = I, root
        self.owner = (os.getuid(), os.getgid())
        for path, data in [*((p, d) for p, d in FILE_PINS.values()), *OTHER_FILES.items()]:
            self.write(path, data)
        os.makedirs(self.p(O.CUSTODY_ROOT + "/prepared"))
        os.makedirs(self.p(O.CUSTODY_ROOT + "/retired"))
        for path, digest in E.WITNESS_DROPINS.items():          # the REAL merged candidate bytes
            unit_dir = Path(path).parent.name
            self.write(path, (E.DROPIN_SOURCE / unit_dir / Path(path).name).read_bytes())
        self.write("/proc/sys/kernel/random/boot_id", (E.BOOT_ID + "\n").encode())
        os.makedirs(self.p(O.RELEASES), mode=0o755)
        self.release(OLD)
        self.select(OLD)
        self.boundary = copy.deepcopy(E.RESTART_BOUNDARY["units"])
        self.witness = ("RUNNING", E.ENDING_INCARNATION, OLD)
        self.witness_loads: list[str] = []
        self.signer_loads: list[str] = []
        self.tail = cursor("1f4a")
        self.health = health_reply()
        self.health_calls = 0
        self.change_identity_on_health = False
        self.w10_report = copy.deepcopy(W10_EXACT_REPORT)
        self.broker = dict(BROKER_PASS)
        self.activation = E.ACTIVATION_LINE_E19
        self.retained = True
        self.w10_identity = None              # None: the report describes the observed witness (the real W10 does)
        self.fail = set()

    def p(self, absolute: str) -> Path:
        return self.root / absolute.lstrip("/")

    def write(self, absolute: str, data: bytes) -> None:
        path = self.p(absolute)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def release(self, sha_: str) -> None:
        payloads = {"lilith_owner_memory/pr1_acceptance.py": f"# judge {sha_}\n".encode(),
                    "assets/lilith-recovery-witness.service": b"[Service]\n", "cli/lilith-authority-hold-dev": b"#!\n"}
        top = self.p(f"{O.RELEASES}/{sha_}")
        for relative, data in payloads.items():
            target = top / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            os.chmod(target, 0o755 if relative.startswith("cli/") else 0o644)
        (top / O.MANIFEST).write_bytes(self.I.canonical(self.I.manifest_for(sha_, payloads)))
        os.chmod(top / O.MANIFEST, 0o644)
        (top / "venv").mkdir()
        for directory, subdirs, _files in os.walk(top):
            os.chmod(directory, 0o755)

    def select(self, sha_: str) -> None:
        link = self.p(O.CURRENT)
        if os.path.lexists(link):
            link.unlink()
        os.symlink(f"releases/{sha_}", link)

    # ---- seams
    def units(self, names):
        if "units" in self.fail:
            raise OSError("systemctl unavailable")
        state, identity, _cwd = self.witness
        service = {"active": ("active", "running", identity[1], identity[0], "0", "success"),
                   "stopped": ("inactive", "dead", "0", "", "0", "success")}
        socket_state = "active" if state == "RUNNING" else "inactive"
        if state == "RUNNING":
            row = service["active"]
        elif state == "STOPPED":
            row = service["stopped"]
        elif state.startswith("SOCKETS_LEFT"):
            row, socket_state = service["stopped"], "active"
        else:
            active, sub = state.split("/")
            row = (active, sub, "0", "", "0", "exit-code")
        out = {}
        for name in names:
            base = {"Id": name, "LoadState": "loaded", "UnitFileState": "static", "NeedDaemonReload": "no",
                    "DropInPaths": "", "Restart": "no", "StopWhenUnneeded": "no", "RefuseManualStart": "no",
                    "FragmentPath": f"/etc/systemd/system/{name}"}
            if name == E.WITNESS_SERVICE:
                base.update(dict(zip(("ActiveState", "SubState", "MainPID", "InvocationID", "NRestarts", "Result"),
                                     row)))
            elif name in (E.OWNER_SOCKET, E.SIGNER_SOCKET):
                base.update(ActiveState=socket_state)
            elif name == O.SIGNER_SERVICE:
                base.update(ActiveState="inactive", SubState="dead", MainPID="0", InvocationID="", NRestarts="0")
            elif name == O.BROKER_SERVICE:
                base.update(ActiveState="active", SubState="running", MainPID=E.PRESERVED_PINS["brokerMainPid"])
            if name in self.boundary:
                base.update(self.boundary[name])
            out[name] = base
        return out

    def invocations(self, unit, after):
        if "journal" in self.fail:
            return None
        return list(self.witness_loads if unit == E.WITNESS_SERVICE else self.signer_loads)

    def w10(self):
        """The W10 report as the unchanged verifier would produce it for the CURRENT witness state."""
        if self.w10_report is None:
            return None
        state, identity, _cwd = self.witness
        running = state == "RUNNING"
        report = copy.deepcopy(self.w10_report)
        report.update(witnessInvocationId=identity[0] if running else None,
                      witnessMainPid=identity[1] if running else "0", witnessNRestarts="0")
        if self.w10_identity is not None:
            report.update(witnessInvocationId=self.w10_identity[0], witnessMainPid=self.w10_identity[1])
        return report

    def cwd(self, _root, _pid):
        return f"{O.OPT}/releases/{self.witness[2]}"

    def health_call(self):
        self.health_calls += 1
        if self.change_identity_on_health:
            self.witness = ("RUNNING", (H32("changed"), "999"), self.witness[2])
        return self.health

    def observe(self, after=None, new_release=NEW):
        inputs = {"newRelease": NEW, "afterCursor": after, "expectedHead": E.PRESERVED_PINS["ledgerHead"],
                  "candidateDigest": E.PRESERVED_PINS["witnessGenesis"], "updatedAt": "2026-10-09T08:00:00Z"}
        return O.observe(inputs, root=self.root, units=self.units, journal_tail=lambda: self.tail,
                         invocations=self.invocations, cwd=self.cwd, activation=lambda: self.activation,
                         health=self.health_call, w10=lambda _i, _r: self.w10(),
                         broker=lambda: dict(self.broker), cursor_retained=lambda _c: self.retained,
                         new_release=new_release, owner=self.owner)

    # ---- phase transitions (what the separately authorized operations would leave behind)
    def to_u1(self):
        self.release(NEW)

    def to_u2(self):
        self.to_u1()
        self.witness = ("STOPPED", ("", "0"), OLD)

    def to_u3(self):
        self.to_u2()
        self.select(NEW)

    def to_u4(self):
        self.to_u3()
        self.witness = ("RUNNING", REPLACEMENT, NEW)
        self.witness_loads = [REPLACEMENT[0]]

    def to_u5(self):
        self.to_u4()
        shutil.rmtree(self.p(f"{O.RELEASES}/{OLD}"))


def u0_acceptance(observation):
    statement = E.render_u0_statement(observation, new_release=NEW)
    record = E.acceptance_record(E.U0_RECORD_TYPE, observation, statement, new_release=NEW,
                                 invocation=E.ENDING_INCARNATION, cursor=observation["journalCursor"])
    return {"observation": observation, "statement": statement.decode("ascii"), "record": record}


def replacement_acceptance(evidence, u0):
    statement = E.render_replacement_statement(evidence, u0, new_release=NEW)
    report = E.post9a_r(evidence, u0, new_release=NEW)
    record = E.acceptance_record(E.REPLACEMENT_RECORD_TYPE, evidence, statement, new_release=NEW,
                                 invocation=(report["invocationId"], report["mainPid"]),
                                 cursor=u0["observation"]["journalCursor"])
    return {"evidence": evidence, "statement": statement.decode("ascii"), "record": record}


@unittest.skipUnless(POSIX, "the synthetic host needs POSIX symlinks, ownership and modes")
class ObserverTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(E.PRESERVED_PINS, SYNTHETIC_PINS)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.host = SyntheticHost(Path(self.tmp.name))
        baseline = self.host.observe()                       # the U0 candidate, self-anchored
        self.u0 = u0_acceptance(baseline["observation"])
        self.host.tail = cursor("2b01")                      # later observations

    def later(self, **kw):
        return self.host.observe(after=self.u0["observation"]["journalCursor"], **kw)

    def verify(self, bundle, replacement=None):
        return O.verify(bundle, self.u0, replacement, new_release=NEW)


class PhaseObservationTests(ObserverTestCase):
    def test_the_u0_candidate_is_exact_and_self_anchored(self):
        obs = self.u0["observation"]
        self.assertEqual(E.classify(obs, new_release=NEW)["phase"], E.U0)
        self.assertEqual(obs["witness"]["invocations"], {"afterCursor": cursor("1f4a"), "ids": []})
        self.assertEqual(obs["releaseEntries"], [OLD])
        self.assertEqual(obs["currentTarget"], f"releases/{OLD}")
        self.assertEqual(obs["witness"]["cwd"], f"{O.OPT}/releases/{OLD}")
        self.assertEqual(obs["witness"]["restartBoundary"], E.RESTART_BOUNDARY)
        self.assertEqual(obs["preserved"]["ledgerHead"], E.PRESERVED_PINS["ledgerHead"])
        self.assertEqual(obs["preserved"]["holdListing"], [O.HELD_NAME])

    def test_every_phase_u0_to_u5_is_observed_and_verified_exactly(self):
        steps = [(E.U0, lambda: None), (E.U1, self.host.to_u1), (E.U2, lambda: setattr(
            self.host, "witness", ("STOPPED", ("", "0"), OLD))), (E.U3, lambda: self.host.select(NEW)),
            (E.U4, lambda: (setattr(self.host, "witness", ("RUNNING", REPLACEMENT, NEW)),
                            setattr(self.host, "witness_loads", [REPLACEMENT[0]])))]
        for phase, step in steps:
            step()
            bundle = self.later()
            verdict = self.verify(bundle)
            with self.subTest(phase=phase):
                self.assertEqual((verdict["phase"], verdict["reasons"]), (phase, []))
                self.assertIs(verdict["maintenanceReady"], True)
                self.assertEqual(verdict["restartBoundaryReasons"], [])
                self.assertEqual(verdict["authorizes"], "NOTHING")
                self.assertEqual(bundle["socketContacted"], phase in (E.U0, E.U1, E.U4))
        u4 = self.later()
        report = O.post9a_r(u4, DENIALS_PASS, self.u0, new_release=NEW)
        self.assertEqual((report["result"], report["reasons"]), ("POST9A_R_VERIFIED", []))
        self.assertIs(report["acceptanceGranted"], False)
        replacement = replacement_acceptance(report["evidence"], self.u0)
        shutil.rmtree(self.host.p(f"{O.RELEASES}/{OLD}"))
        u5 = self.later()
        self.assertEqual(self.verify(u5)["phase"], E.STOP_RETIRED_EARLY)      # no acceptance supplied
        verdict = self.verify(u5, replacement)
        self.assertEqual((verdict["phase"], verdict["maintenanceReady"]), (E.U5, True))

    def test_post9a_r_is_two_release_aware_and_grants_nothing(self):
        self.host.to_u4()
        bundle = self.later()
        self.assertEqual(bundle["observation"]["releaseEntries"], sorted([OLD, NEW]))
        report = O.post9a_r(bundle, DENIALS_PASS, self.u0, new_release=NEW)
        self.assertEqual(report["result"], "POST9A_R_VERIFIED")
        self.assertEqual(report["notRequired"], ["INSTALLER_STATUS_P1B10_RELEASE_SET", "E01_INSTALLED_RELEASE",
                                                 "PR1_PACKAGE_READY"])
        self.assertEqual(report["evidence"]["healthCapture"]["before"],
                         {"InvocationID": REPLACEMENT[0], "MainPID": REPLACEMENT[1]})
        self.assertEqual(report["evidence"]["w10OutputSha256"], E.document_sha256(bundle["w10Report"]))
        self.assertEqual(bundle["w10Report"]["witnessInvocationId"], REPLACEMENT[0])
        source = (TOOLS / "e19_maintenance_observer.py").read_text(encoding="utf-8")
        self.assertNotIn("status --expect", source)
        self.assertNotIn("verify_installed_release", source)


class UnknownVersusDriftTests(ObserverTestCase):
    def assertPhase(self, bundle, phase, replacement=None):
        verdict = self.verify(bundle, replacement)
        self.assertEqual(verdict["phase"], phase, verdict["reasons"])
        self.assertIs(verdict["maintenanceReady"], False)
        return verdict

    def test_unreadable_reads_are_unknown(self):
        self.host.fail.add("units")
        verdict = self.assertPhase(self.later(), E.UNKNOWN)
        self.assertIn("UNOBSERVED:witness.service", verdict["reasons"])
        self.host.fail = {"journal"}
        verdict = self.assertPhase(self.later(), E.UNKNOWN)
        self.assertIn("UNOBSERVED:witness.invocations.ids", verdict["reasons"])
        self.assertIn("UNOBSERVED:signer", verdict["reasons"])

    def test_an_unreadable_file_is_unknown_but_an_absent_file_is_drift(self):
        cred = self.host.p(O.CREDENTIAL)
        real = O._sha_file
        with mock.patch.object(O, "_sha_file", side_effect=lambda path: None if path == cred else real(path)):
            verdict = self.assertPhase(self.later(), E.UNKNOWN)       # a read error: UNKNOWN, never drift
        self.assertIn("UNOBSERVED:preserved.kActCurrentBlobSha256", verdict["reasons"])
        cred.unlink()                                                 # absent: observed drift
        verdict = self.assertPhase(self.later(), E.HALT_PRESERVED)
        self.assertIn("PRESERVED:kActCurrentBlobSha256", verdict["reasons"])
        cred.mkdir()                                                  # replaced by a directory: observed drift
        verdict = self.assertPhase(self.later(), E.HALT_PRESERVED)
        self.assertIn("PRESERVED:kActCurrentBlobIdentity", verdict["reasons"])

    def test_failed_side_reads_are_unknown(self):
        cases = {"activationLine": ("activation", None), "brokerInvocationId": ("broker", None),
                 "ledgerHead": ("w10_report", None)}
        for name, (attr, value) in cases.items():
            host = self.host
            saved = getattr(host, attr)
            setattr(host, attr, value)
            with self.subTest(name=name):
                verdict = self.assertPhase(self.later(), E.UNKNOWN)
                self.assertIn("UNOBSERVED:preserved." + name, verdict["reasons"])
            setattr(host, attr, saved)

    def test_observed_drift_is_a_halt(self):
        cases = {
            "registrySha256": lambda h: h.write(O.REGISTRY, b'{"registry":2}\n'),
            "heldSha256": lambda h: h.write(f"{O.HOLD_STORE}/{O.HELD_NAME}", b"{}\n"),
            "holdListing": lambda h: h.write(f"{O.HOLD_STORE}/{'0' * 64}.json", b"{}\n"),
            "credstoreListing": lambda h: h.write(O.CREDSTORE + "/extra.cred", b"x"),
            "custodyListing": lambda h: h.write(O.CUSTODY_ROOT + "/prepared/successor.cred", b"x"),
            "ownerInputsSha256": lambda h: h.write(O.OWNER_INPUTS[0], b'{"pin":2}\n'),
            "installedClisSha256": lambda h: h.write(O.CLIS[0], b"#!/bin/sh\nexit 0\n"),
            "activationLine": lambda h: setattr(h, "activation", "ACTIVATION=ACCEPTED {} advisoryConfigEnabled=false"),
            "brokerInvocationId": lambda h: h.broker.update(runtimeIncarnation=H32("other broker")),
            "ledgerHead": lambda h: h.w10_report.update(w9Failures=["LEDGER_FILE_INEXACT"]),
            "witnessGenesis": lambda h: h.w10_report.update(committedGenesisDigest=None),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                self.setUp()
                mutate(self.host)
                verdict = self.assertPhase(self.later(), E.HALT_PRESERVED)
                self.assertIn("PRESERVED:" + name, verdict["reasons"])

    def test_signer_activity_is_a_halt(self):
        self.host.signer_loads = [H32("a K-ACT load")]
        self.assertPhase(self.later(), E.HALT_SIGNER)

    def test_reboot_is_a_stop(self):
        self.host.write("/proc/sys/kernel/random/boot_id", b"00000000-0000-0000-0000-000000000000\n")
        self.assertPhase(self.later(), E.STOP_BOOT)


class ReleaseSetTests(ObserverTestCase):
    def assertPhase(self, phase):
        verdict = self.verify(self.later())
        self.assertEqual(verdict["phase"], phase, verdict["reasons"])
        self.assertIs(verdict["maintenanceReady"], False)

    def test_interrupted_stage_and_select_residue(self):
        (self.host.p(f"{O.RELEASES}/.{NEW}.staging")).mkdir()
        self.assertPhase(E.STOP_STAGING)
        self.setUp()
        self.host.to_u2()
        self.host.p(O.OPT + "/.current.tmp").symlink_to(f"releases/{NEW}")
        self.assertPhase(E.STOP_SELECTOR)

    def test_foreign_release_sets_and_selectors(self):
        self.host.release("1" * 40)
        self.assertPhase(E.STOP_RELEASE_SET)
        self.setUp()
        link = self.host.p(O.CURRENT)
        link.unlink()
        link.mkdir()
        self.assertPhase(E.STOP_RELEASE_SET)
        self.setUp()
        self.host.p(O.CURRENT).unlink()
        self.assertPhase(E.STOP_RELEASE_SET)

    def test_tampered_trees(self):
        def tamper_file(h):
            path = h.p(f"{O.RELEASES}/{NEW}/lilith_owner_memory/pr1_acceptance.py")
            path.write_bytes(b"# tampered\n")

        def extra(h):
            h.write(f"{O.RELEASES}/{NEW}/extra.py", b"x")
            os.chmod(h.p(f"{O.RELEASES}/{NEW}/extra.py"), 0o644)

        def symlink(h):
            os.symlink("/etc/passwd", h.p(f"{O.RELEASES}/{NEW}/assets/link"))

        def mode(h):
            os.chmod(h.p(f"{O.RELEASES}/{NEW}/cli/lilith-authority-hold-dev"), 0o777)

        for mutate in (tamper_file, extra, symlink, mode):
            with self.subTest(mutate=mutate.__name__):
                self.setUp()
                self.host.to_u1()
                mutate(self.host)
                self.assertPhase(E.STOP_NEW_TREE)
        self.setUp()
        self.host.to_u4()
        self.host.p(f"{O.RELEASES}/{OLD}/{O.MANIFEST}").write_bytes(b"{}\n")
        self.assertPhase(E.STOP_OLD_TREE)

    def test_the_tree_check_equals_the_installer_check(self):
        I = self.host.I
        system = types.SimpleNamespace(path=self.host.p, owner_uid=self.host.owner[0], owner_gid=self.host.owner[1])
        self.host.to_u1()
        self.assertEqual(I.release_tree_failures(system, NEW), [])
        self.assertIs(O.release_tree_verified(self.host.root, NEW, self.host.owner), True)
        self.host.write(f"{O.RELEASES}/{NEW}/extra.py", b"x")
        os.chmod(self.host.p(f"{O.RELEASES}/{NEW}/extra.py"), 0o644)
        self.assertNotEqual(I.release_tree_failures(system, NEW), [])
        self.assertIs(O.release_tree_verified(self.host.root, NEW, self.host.owner), False)
        self.assertIs(O.release_tree_verified(self.host.root, "2" * 40, self.host.owner), False)


class RestartBoundaryTests(ObserverTestCase):
    def test_a_missing_or_ineffective_boundary_refuses_maintenance_readiness(self):
        def missing_dropin(h):
            h.p(E.SERVICE_DROPIN).unlink()

        def changed_dropin(h):
            h.write(E.SOCKET_DROPINS[E.OWNER_SOCKET], b"[Unit]\nStopWhenUnneeded=yes\n")

        cases = {
            "drop-in absent": (missing_dropin, f"DROPIN:{E.SERVICE_DROPIN}:ABSENT"),
            "drop-in bytes": (changed_dropin, f"DROPIN:{E.SOCKET_DROPINS[E.OWNER_SOCKET]}:BYTES"),
            "Restart=on-failure": (lambda h: h.boundary[E.WITNESS_SERVICE].update(Restart="on-failure"),
                                   f"{E.WITNESS_SERVICE}:Restart"),
            "reload pending": (lambda h: h.boundary[E.SIGNER_SOCKET].update(NeedDaemonReload="yes"),
                               f"{E.SIGNER_SOCKET}:NeedDaemonReload"),
            "extra drop-in path": (lambda h: h.boundary[E.WITNESS_SERVICE].update(
                DropInPaths=E.SERVICE_DROPIN + " /etc/systemd/system/lilith-recovery-witness.service.d/x.conf"),
                f"{E.WITNESS_SERVICE}:DropInPaths"),
            "socket reactivation": (lambda h: h.boundary[E.OWNER_SOCKET].update(StopWhenUnneeded="no"),
                                    f"{E.OWNER_SOCKET}:StopWhenUnneeded"),
        }
        for name, (mutate, reason) in cases.items():
            for phase_step in ("to_u1", "to_u3"):
                with self.subTest(name=name, phase=phase_step):
                    self.setUp()
                    getattr(self.host, phase_step)()
                    mutate(self.host)
                    bundle = self.later()
                    verdict = self.verify(bundle)
                    self.assertIs(verdict["maintenanceReady"], False)
                    self.assertIn(reason, verdict["restartBoundaryReasons"])
                    self.assertIn(verdict["phase"], (E.STOP_BOUNDARY, E.UNKNOWN))
                    self.assertEqual(self.host.health_calls, 1)   # only the U0 baseline in setUp contacted it
                    self.assertIs(bundle["socketContacted"], False)

    def test_a_boundary_failure_on_the_u0_candidate_refuses_the_baseline(self):
        self.setUp()
        self.host.p(E.SERVICE_DROPIN).unlink()
        self.host.tail = cursor("1f4a")
        with self.assertRaises(E.Refused) as caught:
            u0_acceptance(self.host.observe()["observation"])
        self.assertEqual(caught.exception.reason, "BASELINE_NOT_U0")


class SocketContactTests(ObserverTestCase):
    def test_a_stopped_or_transitional_witness_is_never_contacted(self):
        for state in (("STOPPED", ("", "0"), OLD), ("failed/failed", ("", "0"), OLD),
                      ("activating/auto-restart", ("", "0"), OLD), ("SOCKETS_LEFT_LISTENING", ("", "0"), OLD)):
            with self.subTest(state=state[0]):
                self.setUp()
                self.host.to_u1()
                self.host.witness = state
                before = self.host.health_calls
                bundle = self.later()
                self.assertEqual(self.host.health_calls, before)
                self.assertIs(bundle["socketContacted"], False)
                self.assertIsNone(bundle["observation"]["witness"]["health"])
                self.assertIn(self.verify(bundle)["phase"], (E.U2, E.STOP_WITNESS_TRANSITIONAL))

    def test_an_identity_change_around_health_is_not_a_capture(self):
        self.host.to_u1()
        self.host.change_identity_on_health = True
        bundle = self.later()
        self.assertIsNone(bundle["healthCapture"])
        self.assertEqual(self.verify(bundle)["phase"], E.UNKNOWN)

    def test_a_drifted_health_reply_is_observed_drift(self):
        self.host.to_u1()
        self.host.health = health_reply(authorityGranted=True)
        bundle = self.later()
        self.assertTrue(bundle["observation"]["witness"]["health"]["classification"].startswith("NOT_EXACT:"))
        self.assertEqual(self.verify(bundle)["phase"], E.STOP_ORIGINAL_RESTARTED)


class ForgedInputTests(ObserverTestCase):
    def test_forged_u0_acceptances_are_refused(self):
        bundle = self.later()
        forged = [{"accepted": True}, dict(self.u0, statement=self.u0["statement"].replace("nothing", "everything")),
                  dict(self.u0, record=dict(self.u0["record"], mainPid="1"))]
        self.host.to_u3()
        u3 = self.later()["observation"]
        forged.append({"observation": u3, "statement": self.u0["statement"], "record": self.u0["record"]})
        for item in forged:
            with self.subTest(item=str(item)[:40]), self.assertRaises(E.Refused):
                O.verify(bundle, item, new_release=NEW)

    def test_forged_post9a_r_inputs_do_not_verify(self):
        self.host.to_u4()
        bundle = self.later()
        bad_denials = {
            "wrong line": {**DENIALS_PASS, "P1B-5": (b"AUTHORITY_CUSTODY_DENIAL_PROOF=PASS phase=P1B-12\n", 0)},
            "exit 1": {**DENIALS_PASS, "P1B-10": (DENIALS_PASS["P1B-10"][0], 1)},
            "CRLF": {**DENIALS_PASS, "P1B-9b": (DENIALS_PASS["P1B-9b"][0].replace(b"\n", b"\r\n"), 0)},
            "allowed": {**DENIALS_PASS,
                        "P1B-10": (b"MB10_HOLD_DENIAL_PROOF=PASS phase=P1B-10 denied=4 allowed=1\n", 0)},
            "PASS not last": {**DENIALS_PASS, "P1B-5": (DENIALS_PASS["P1B-5"][0] + b"FAIL: later\n", 0)},
        }
        for name, denials in bad_denials.items():
            with self.subTest(name=name):
                self.assertEqual(O.post9a_r(bundle, denials, self.u0, new_release=NEW)["result"],
                                 "POST9A_R_NOT_VERIFIED")
        with self.assertRaises(E.Refused):
            O.post9a_r(bundle, {"P1B-5": DENIALS_PASS["P1B-5"]}, self.u0, new_release=NEW)
        tampered = copy.deepcopy(bundle)
        tampered["w10Report"]["phase"] = "W10_1_HELD_EXACT_FORGED"
        with self.assertRaises(E.Refused) as caught:
            O.post9a_r(tampered, DENIALS_PASS, self.u0, new_release=NEW)
        self.assertEqual(caught.exception.reason, "W10_NOT_BOUND")
        foreign_capture = copy.deepcopy(bundle)
        foreign_capture["healthCapture"]["before"] = {"InvocationID": H32("other"), "MainPID": "1"}
        self.assertEqual(O.post9a_r(foreign_capture, DENIALS_PASS, self.u0, new_release=NEW)["result"],
                         "POST9A_R_NOT_VERIFIED")
        self.host.w10_report["phase"] = "W10_WITNESS_NOT_EXACT"
        self.assertEqual(O.post9a_r(self.later(), DENIALS_PASS, self.u0, new_release=NEW)["result"],
                         "POST9A_R_NOT_VERIFIED")

    def test_inputs_and_release_identity_are_refused_when_not_established(self):
        with self.assertRaises(E.Refused) as caught:
            self.host.observe(new_release=None)
        self.assertEqual(caught.exception.reason, "NEW_RELEASE_NOT_ESTABLISHED")
        with self.assertRaises(E.Refused) as caught:
            O.observe({"newRelease": NEW}, root=self.host.root, new_release=NEW)
        self.assertEqual(caught.exception.reason, "INPUT_FIELDS")
        self.assertEqual(E.NEW_RELEASE, "ba943e1a188d98f4108c9eec7149c0cf1a8f68bb")   # the merged owner pin
        with self.assertRaises(E.Refused) as caught:              # inputs for another NEW, against the pinned default
            self.host.observe(new_release=E.NEW_RELEASE)
        self.assertEqual(caught.exception.reason, "NEW_RELEASE_NOT_ESTABLISHED")
        with self.assertRaises(E.Refused):
            O.verify({"bundleType": "X"}, self.u0, new_release=NEW)


class ReadOnlyTests(ObserverTestCase):
    def snapshot(self):
        out = {}
        for directory, subdirs, files in os.walk(self.host.root):
            for name in subdirs + files:
                path = Path(directory) / name
                meta = os.lstat(path)
                out[str(path)] = (meta.st_mode, meta.st_size, meta.st_mtime_ns, meta.st_ino,
                                  sha(path.read_bytes()) if stat.S_ISREG(meta.st_mode) else os.readlink(path)
                                  if stat.S_ISLNK(meta.st_mode) else None)
        return out

    def test_observing_every_phase_changes_nothing_on_the_host(self):
        for step in ("to_u1", "to_u2", "to_u3", "to_u4", "to_u5"):
            self.setUp()
            getattr(self.host, step)()
            before = self.snapshot()
            self.later()
            with self.subTest(step=step):
                self.assertEqual(self.snapshot(), before)

    def test_the_default_host_reads_are_read_only_commands(self):
        calls = []

        def run(argv, **kw):
            calls.append(list(argv))
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")

        O._units(("lilith-recovery-witness.service",), run=run)
        O._journal_tail(run=run)
        O._invocations(E.WITNESS_SERVICE, cursor("1f4a"), run=run)
        O._activation(run=run)
        O._health(run=run)
        self.assertEqual([c[:2] for c in calls], [[O.SYSTEMCTL, "show"], [O.JOURNALCTL, "-n"], [O.JOURNALCTL, "-u"],
                                                  [O.ACTIVATION_VERIFY], [O.OWNER_CLI, "health"]])
        self.assertIn("--after-cursor=" + cursor("1f4a"), calls[2])
        self.assertIsNone(O._invocations(E.WITNESS_SERVICE, "bad cursor", run=run))


class SourceTests(unittest.TestCase):
    def test_the_observer_has_no_mutating_operation(self):
        import ast

        source = (TOOLS / "e19_maintenance_observer.py").read_text(encoding="utf-8")
        source = source.replace(ast.get_docstring(ast.parse(source), clean=False), "")   # code only, not prose
        for needle in ("write_bytes", "write_text", "os.remove", "unlink", "rmtree", ".rename(", "os.replace",
                       "os.symlink(", "chmod", "chown", "mkdir", "makedirs", "daemon-reload", '"start"', '"stop"',
                       '"restart"', '"enable"', "\"bootstrap\"", "create-initial-held", "socket.socket", "plink",
                       "gcloud", "O_WRONLY", "O_CREAT"):
            self.assertNotIn(needle, source, needle)
        commands = [line for line in source.splitlines() if "= run(" in line]
        self.assertEqual(len(commands), 5)          # systemctl show, journalctl x2, activation verify, health

    def test_contract_pin_and_unchanged_merged_tools(self):
        self.assertEqual(sha((TOOLS / "e19_p1b10_upgrade.py").read_bytes()), O.E19_CONTRACT_SHA256)
        for name, digest in E.WITNESS_DROPINS.items():
            unit_dir = Path(name).parent.name
            self.assertEqual(sha((E.DROPIN_SOURCE / unit_dir / Path(name).name).read_bytes()), digest)

    def test_host_paths_equal_the_installer_and_operator_constants(self):
        import install_authority_dev as I
        import mb6_operator as M6

        self.assertEqual((O.OPT, O.RELEASES, O.CURRENT, O.MANIFEST), (I.OPT, I.RELEASES, I.CURRENT, I.MANIFEST))
        self.assertEqual((O.CREDENTIAL, O.CREDSTORE, O.HOST_KEY, O.CUSTODY_ROOT), (I.CREDENTIAL, I.CREDSTORE,
                                                                                  I.HOST_KEY, I.CUSTODY_ROOT))
        self.assertEqual((O.WITNESS_CREDENTIAL_ROOT, O.WITNESS_BLOB), (I.WITNESS_CREDENTIAL_ROOT, I.WITNESS_BLOB))
        self.assertEqual((O.TRUST_DIR + "/registry-root.json", O.TRUST_DIR + "/witness-anchor.json"),
                         (I.REGISTRY_ROOT_ANCHOR, I.WITNESS_ANCHOR))
        self.assertEqual(O.OWNER_INPUTS, (I.GENESIS_PIN_COPY, I.AUTHORIZATION_REGISTER_COPY))
        self.assertEqual((O.WITNESS_STATE, O.HOLD_STORE, O.LEDGER_STATE), (I.WITNESS_STATE, I.HOLD_STORE,
                                                                           I.AUTHORITY_STATE))
        self.assertEqual(set(O.SIGNER_UNIT_FILES), set(I.UNIT_TARGETS.values()))
        self.assertEqual(set(O.WITNESS_UNIT_FILES), set(I.WITNESS_UNIT_TARGETS.values()))
        self.assertEqual(set(O.CLIS), set(I.CLI_TARGETS.values()))
        self.assertEqual(O.KACT_PUBLICATION, M6.KACT_PUBLICATION)
        import mb11_restart_boundary_install as RBI

        self.assertEqual(O.SHADOW_BASES, RBI.SHADOW_BASES)
        self.assertIn("/run/systemd/system", O.SHADOW_BASES)
        self.assertTrue(O.REGISTRY.startswith(I.REGISTRY_DIR + "/"))

    def test_invocation_parsing(self):
        a, b = H32("a"), H32("b")
        lines = [json.dumps({"_SYSTEMD_INVOCATION_ID": a}), json.dumps({"INVOCATION_ID": b, "UNIT": "x"}),
                 json.dumps({"_SYSTEMD_INVOCATION_ID": a}), json.dumps({"MESSAGE": "no id"}), ""]
        self.assertEqual(O.parse_invocations(lines), [a, b])
        self.assertIsNone(O.parse_invocations(["not json"]))
        self.assertIsNone(O.parse_invocations(["[1]"]))
        self.assertEqual(O.parse_invocations([]), [])

    def test_ledger_head_and_genesis_derivation(self):
        exact = dict(W10_EXACT_REPORT)
        self.assertEqual(O._ledger_head(exact), E.PRESERVED_PINS["ledgerHead"])
        self.assertEqual(O._ledger_head(dict(exact, phase="W10_1S_HELD_EXACT_WITNESS_STOPPED",
                                             w9PhaseHoldJudgedSeparately="W9_5S_GENESIS_COMMITTED_STOPPED")),
                         E.PRESERVED_PINS["ledgerHead"])
        self.assertEqual(O._ledger_head(dict(exact, w9Failures=["LEDGER_IMAGE_X"])), "LEDGER_NOT_EXACT")
        self.assertIsNone(O._ledger_head(dict(exact, phase="W10_WITNESS_NOT_EXACT")))
        self.assertIsNone(O._ledger_head(None))
        self.assertEqual(O._genesis(dict(exact, committedGenesisDigest=None)), O.ABSENT)
        self.assertIsNone(O._genesis(None))



class Pr189ReviewRegressionTests(ObserverTestCase):
    """The PR #189 owner-review probes P1–P5 (findings F2, F3, F5, F1, F4), each now refused."""

    def test_p1_f2_a_stale_w10_report_cannot_be_spliced_into_post9a_r(self):
        u0_bundle = self.later()                                  # W10 while the ending incarnation ran
        self.assertEqual(u0_bundle["w10Report"]["witnessInvocationId"], E.ENDING_INCARNATION[0])
        self.host.to_u4()
        u4 = self.later()
        spliced = dict(u4, w10Report=u0_bundle["w10Report"], w10ReportSha256=u0_bundle["w10ReportSha256"])
        with self.assertRaises(E.Refused) as caught:
            O.post9a_r(spliced, DENIALS_PASS, self.u0, new_release=NEW)
        self.assertEqual(caught.exception.reason, "W10_NOT_THIS_OBSERVATION")
        self.assertEqual(O.post9a_r(u4, DENIALS_PASS, self.u0, new_release=NEW)["result"], "POST9A_R_VERIFIED")
        # At observe time a report for another incarnation is discarded: ledger head and genesis become UNKNOWN.
        self.host.w10_identity = E.ENDING_INCARNATION
        stale = self.later()
        self.assertIsNone(stale["w10Report"])
        verdict = self.verify(stale)
        self.assertEqual(verdict["phase"], E.UNKNOWN)
        self.assertIn("UNOBSERVED:preserved.ledgerHead", verdict["reasons"])
        self.assertIn("UNOBSERVED:preserved.witnessGenesis", verdict["reasons"])

    def test_p2_f3_a_shadow_unit_or_foreign_fragment_refuses_readiness(self):
        self.host.to_u1()
        self.assertEqual(self.verify(self.later())["unitFragmentReasons"], [])
        shadow = f"/run/systemd/system/{E.WITNESS_SERVICE}"
        self.host.write(shadow, b"[Service]\nExecStart=/bin/true\n")
        verdict = self.verify(self.later())
        self.assertIs(verdict["maintenanceReady"], False)
        self.assertIn("SHADOW:" + shadow, verdict["unitFragmentReasons"])
        self.host.p(shadow).unlink()
        dropin_dir = f"/run/systemd/system/{E.OWNER_SOCKET}.d"
        self.host.p(dropin_dir).mkdir(parents=True)
        self.assertIn("SHADOW:" + dropin_dir, self.verify(self.later())["unitFragmentReasons"])
        self.host.p(dropin_dir).rmdir()
        real = self.host.units

        def foreign(names):
            out = real(names)
            if E.SIGNER_SOCKET in out:
                out[E.SIGNER_SOCKET]["FragmentPath"] = f"/run/systemd/transient/{E.SIGNER_SOCKET}"
            return out

        self.host.units = foreign
        verdict = self.verify(self.later())
        self.assertEqual(verdict["unitFragmentReasons"], [f"{E.SIGNER_SOCKET}:FragmentPath"])
        self.assertIs(verdict["maintenanceReady"], False)
        self.assertEqual(O.unit_fragment_reasons({}), ["UNIT_IDENTITY_UNOBSERVED"])

    def test_p3_f5_the_release_venv_must_be_a_genuine_root_directory(self):
        self.host.to_u1()
        venv = self.host.p(f"{O.RELEASES}/{NEW}/venv")
        self.assertIs(O.release_tree_verified(self.host.root, NEW, self.host.owner), True)
        foreign = self.host.p("/tmp/foreign-venv")
        foreign.mkdir(parents=True)

        def symlinked():
            venv.rmdir()
            os.symlink(foreign, venv)

        def regular_file():
            venv.unlink()
            venv.write_bytes(b"not a directory")

        def wide_mode():
            venv.unlink()
            venv.mkdir()
            os.chmod(venv, 0o777)

        def missing():
            venv.rmdir()

        for mutate in (symlinked, regular_file, wide_mode, missing):
            mutate()
            with self.subTest(case=mutate.__name__):
                self.assertIs(O.release_tree_verified(self.host.root, NEW, self.host.owner), False)
                self.assertEqual(self.verify(self.later())["phase"], E.STOP_NEW_TREE)

    def test_p4_f1_observer_execution_writes_no_bytecode(self):
        import subprocess

        with tempfile.TemporaryDirectory() as work:
            tools = Path(work) / "tools"
            tools.mkdir()
            for name in ("e19_maintenance_observer.py", "e19_p1b10_upgrade.py", "mb11_restart_boundary_install.py",
                         "mb11_restart_boundary.py"):
                shutil.copyfile(TOOLS / name, tools / name)
            release = Path(work) / "release" / "lilith_probe"
            release.mkdir(parents=True)
            (release / "__init__.py").write_text("VALUE = 1\n", encoding="ascii")
            code = ("import runpy, sys; sys.path.insert(0, sys.argv[1]); "
                    "runpy.run_path(sys.argv[1] + '/e19_maintenance_observer.py', run_name='observer_probe'); "
                    "sys.path.insert(0, sys.argv[2]); import lilith_probe; assert lilith_probe.VALUE == 1")
            env = {k: v for k, v in os.environ.items() if k not in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX")}
            result = subprocess.run([sys.executable, "-c", code, str(tools), str(release.parent)], env=env,
                                    capture_output=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
            written = [str(p) for p in Path(work).rglob("*") if p.name == "__pycache__" or p.suffix == ".pyc"]
            self.assertEqual(written, [])
        self.assertIn("sys.dont_write_bytecode = True", (TOOLS / "e19_maintenance_observer.py").read_text("utf-8"))

    def test_p5_f4_an_unretained_baseline_cursor_makes_loads_unknown(self):
        self.host.to_u4()
        for retained in (False, None):
            self.host.retained = retained
            bundle = self.later()
            with self.subTest(retained=retained):
                self.assertIsNone(bundle["observation"]["witness"]["invocations"]["ids"])
                self.assertIs(bundle["baselineCursorRetained"], retained)
                verdict = self.verify(bundle)
                self.assertEqual(verdict["phase"], E.UNKNOWN)
                self.assertIn("UNOBSERVED:witness.invocations.ids", verdict["reasons"])
                self.assertIs(verdict["maintenanceReady"], False)
        self.setUp()                                               # the U0 candidate needs a retained cursor too
        self.host.retained = False
        self.host.tail = cursor("1f4a")
        with self.assertRaises(E.Refused) as caught:
            u0_acceptance(self.host.observe()["observation"])
        self.assertEqual(caught.exception.reason, "BASELINE_NOT_U0")

    def test_p5_f4_retention_is_proven_by_the_exact_entry_at_the_cursor(self):
        base = cursor("1f4a")

        class Proc:
            def __init__(self, line):
                self.stdout = types.SimpleNamespace(readline=lambda limit: line)
                self.killed = False

            def kill(self):
                self.killed = True

            def wait(self, timeout):
                return 0

        calls = []

        def popen(line):
            def make(argv, **kw):
                calls.append(argv)
                proc = Proc(line)
                calls.append(proc)
                return proc
            return make

        cases = {json.dumps({"__CURSOR": base}) + "\n": True,                  # the exact entry is retained
                 json.dumps({"__CURSOR": cursor("2000")}) + "\n": False,       # vacuumed: the nearest entry
                 "": False, "not json\n": None}
        for line, expected in cases.items():
            with self.subTest(line=line[:30]):
                self.assertIs(O._cursor_retained(base, popen=popen(line)), expected)
                self.assertIn("--cursor=" + base, calls[-2])
                self.assertNotIn("--after-cursor=" + base, calls[-2])
                self.assertTrue(calls[-1].killed)
        self.assertIsNone(O._cursor_retained("has space", popen=popen("")))


if __name__ == "__main__":
    unittest.main()
