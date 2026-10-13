"""15B2b-B1b-3e E-19 controlled release transition: installer stages, stop / start, two-release reads, live observer.

Record: docs/architecture/slice-15b2b-b1b3e-e19-transition-implementation.md. TEST-ONLY: synthetic host trees, a fake
DEV behind the operator's transport seams, and the REAL mb6 BOOT loader in a subprocess from an empty working
directory. Nothing here contacts DEV, runs systemctl, loads a credential or builds the NEW release.
"""

from __future__ import annotations

import base64
import contextlib
import gzip
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _p in (TOOLS, ROOT / "services/authority-dev/ceremony", ROOT / "services/authority-dev",
           ROOT / "services/owner-memory-control", ROOT / "services/core-api", HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import build_authority_dev_release as BUILD  # noqa: E402
import e19_maintenance_observer as O  # noqa: E402
import e19_operator as X  # noqa: E402
import e19_p1b10_upgrade as E  # noqa: E402
import e19_release_stages as S  # noqa: E402
import install_authority_dev as I  # noqa: E402
import mb6_operator as M6  # noqa: E402
import test_b1b3e_e19_maintenance_observer as OT  # noqa: E402  (helpers only: SyntheticHost, acceptances)

POSIX = os.name == "posix"
OLD = E.OLD_RELEASE
NEW = OT.NEW
REPLACEMENT = OT.REPLACEMENT
INSTALLER_PIN = "fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487"   # M6 / M9 / M10 (completed)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def boot_loader() -> str:
    return "import base64;exec(base64.b64decode('" + base64.b64encode(M6.BOOT.encode("ascii")).decode() + "'))"


def run_boot(sources: dict[str, str], entry: str, *args: str) -> subprocess.CompletedProcess:
    """The REAL mb6 BOOT loader, isolated (`-I -B`), from an empty working directory: no tool file is reachable."""
    pins = ",".join(f"{name}={sha(text.encode('utf-8'))}" for name, text in sources.items())
    with tempfile.TemporaryDirectory() as empty:
        return subprocess.run([sys.executable, "-I", "-B", "-c", boot_loader(), pins, entry, *args],
                              input=gzip.compress(json.dumps(sources).encode("utf-8"), mtime=0),
                              capture_output=True, cwd=empty, timeout=120, check=False)


def sources_of(paths) -> dict[str, str]:
    return {Path(path).stem: (ROOT / path).read_text(encoding="utf-8") for path in paths}


# ================================================================================================ pins and guards ===

class PinTests(unittest.TestCase):
    def test_every_pinned_tool_is_exact_and_reused_pins_are_unchanged(self):
        for path, pin in X.TOOL_PINS.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)
        reused = {path for path in X.TOOL_PINS if path in X.M10.TOOL_PINS}
        self.assertTrue(reused)
        for path in reused:
            self.assertEqual(X.TOOL_PINS[path], X.M10.TOOL_PINS[path], path)
        self.assertEqual(sha(Path(X.M10.__file__).read_bytes()), X.TOOL_PINS[X.MB10_OPERATOR])

    def test_the_completed_ceremony_installer_is_byte_unchanged(self):
        self.assertEqual(sha((ROOT / X.M9.INSTALLER).read_bytes()), INSTALLER_PIN)
        self.assertEqual(M6.TOOL_PINS[M6.INSTALLER], INSTALLER_PIN)
        self.assertEqual(X.TOOL_PINS[X.M9.INSTALLER], INSTALLER_PIN)
        source = (ROOT / X.M9.INSTALLER).read_text(encoding="utf-8")
        self.assertIn('raise InstallError("UPGRADE_UNEXPECTED_PRESENT:" + path)', source)   # custody host refused

    def test_constants_agree_with_the_contract(self):
        self.assertEqual(S.OLD_RELEASE, E.OLD_RELEASE)
        self.assertEqual((S.DELTA_OLD_SHA256, S.DELTA_NEW_SHA256), E.PAYLOAD_DELTA[S.DELTA_MEMBER])
        self.assertEqual(S.ENDING_INVOCATION, E.ENDING_INCARNATION[0])
        self.assertEqual(S.WITNESS_SERVICE, E.WITNESS_SERVICE)
        self.assertEqual(O.BROKER_SHA256, X.M9.TOOL_PINS[X.M9.BROKER])
        self.assertEqual(Path(X.M9.BROKER).stem, O.BROKER_MODULE)
        self.assertEqual(X.TOOL_PINS[X.CONTRACT], O.E19_CONTRACT_SHA256)
        self.assertEqual(X.STOP_COMMAND, "sudo -n /usr/bin/systemctl stop lilith-recovery-witness.service "
                                         "lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket")
        self.assertEqual(X.START_COMMAND, "sudo -n /usr/bin/systemctl start lilith-recovery-witness.service")
        self.assertEqual(X.GENESIS, E.PRESERVED_PINS["witnessGenesis"])
        self.assertEqual(X.LEDGER_HEAD, E.PRESERVED_PINS["ledgerHead"])
        self.assertEqual([Path(p).stem for p in X.STAGES_BUNDLE],
                         ["install_authority_dev", "e19_p1b10_upgrade", "e19_release_stages"])
        self.assertIs(S.E, E)
        self.assertEqual(Path(X.OBSERVER_BUNDLE[-1]).stem, "e19_maintenance_observer")

    @staticmethod
    def code(name: str) -> str:
        """The source without docstrings or comments (`ast.unparse`)."""
        import ast

        tree = ast.parse((TOOLS / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if isinstance(body, list) and body and isinstance(body[0], ast.Expr)                     and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                body.pop(0)
                if not body:
                    body.append(ast.Pass())
        return ast.unparse(tree)

    def test_go_lines_survive_the_go_check_normalisation(self):
        for step, lines in X.GO_LINES.items():
            for line in lines + X.GO_COMMON:
                self.assertNotIn(">", line, step)

    def test_no_unreviewed_unit_command_or_credential_path(self):
        stages = self.code("e19_release_stages.py")
        operator = self.code("e19_operator.py")
        for forbidden in ("daemon-reload", "systemctl restart", "systemctl enable", "systemd-creds", "keygen",
                          "create-initial-held", "provision", "socket.socket", "--force"):
            self.assertNotIn(forbidden, stages, forbidden)
        code = [line for line in stages.splitlines() if "systemctl" in line and not line.lstrip().startswith("#")]
        self.assertEqual(len(code), 1)
        self.assertIn("'show'", code[0])
        self.assertNotIn("daemon-reload", operator)
        self.assertNotIn("systemctl", operator)              # only the contract's two reviewed commands, by reference
        self.assertEqual(operator.count("E.START_COMMAND"), 1)
        self.assertEqual(operator.count("E.STOP_COMMAND"), 1)


class RecordTests(unittest.TestCase):
    RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-e19-transition-implementation.md"

    def test_the_record_pins_every_new_or_reused_tool_and_runs_nothing(self):
        text = self.RECORD.read_text(encoding="utf-8")
        for path in (X.STAGES, X.OBSERVER, X.CONTRACT, X.M9.INSTALLER, X.MB10_OPERATOR):
            self.assertIn(f"`{path}`", text, path)
            self.assertIn(f"`{X.TOOL_PINS[path]}`", text, path)
        state = text.split("## 6. State", 1)[1]
        for line in ("NOTHING RUN", "LIVE_MUTATION = NONE", "NEW_RELEASE = NOT BUILT / NOT PINNED"):
            self.assertIn(line, state)
        self.assertIsNone(E.NEW_RELEASE)
        self.assertIsNone(E.NEW_MANIFEST_SHA256)


# ======================================================================================= installer stages (A) ===

@contextlib.contextmanager
def stand_in_wheels():
    saved = (I.WHEEL_HASHES, I.LOCK)
    with tempfile.TemporaryDirectory() as directory:
        house, hashes = Path(directory), {}
        for index, name in enumerate(saved[0]):
            data = f"stand-in wheel {index}".encode()
            (house / name).write_bytes(data)
            hashes[name] = sha(data)
        I.WHEEL_HASHES = hashes
        I.LOCK = "".join(f"x{i}==1 --hash=sha256:{h}\n" for i, h in enumerate(hashes.values())).encode()
        try:
            yield house
        finally:
            I.WHEEL_HASHES, I.LOCK = saved


class StageHost:
    """A synthetic DEV root: OLD installed and selected; fake systemctl / venv / runuser; the installer `status` seam."""

    def __init__(self, root: Path, old_payloads: dict[str, bytes]):
        self.root, self.calls, self.status_calls, self.installer_failures = root, [], [], []
        (root / "etc").mkdir(parents=True)
        (root / "etc/machine-id").write_text(I.DEV_MACHINE_ID + "\n", encoding="ascii")
        (root / "proc").mkdir()
        self.units = {u: {"ActiveState": "inactive", "SubState": "dead", "MainPID": "0", "InvocationID": "",
                          "NRestarts": "0"} for u in I.WITNESS_UNITS + I.AUTHORITY_UNITS}
        write_tree(root, OLD, old_payloads)
        os.symlink(f"releases/{OLD}", root / "opt/lilith-authority-dev/current")
        self.running(E.ENDING_INCARNATION, OLD)
        self.custody = {p: f"synthetic {p}".encode() for p in (
            "/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred",
            "/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred",
            "/var/lib/lilith-authority-custody/holds/" + E.PRESERVED_PINS["holdListing"][0],
            "/var/lib/lilith-recovery-witness/witness.json", "/var/lib/lilith-authority-dev/authority_ledger.db",
            "/etc/systemd/system/lilith-recovery-witness.service.d/10-no-implicit-restart.conf")}
        for path, data in self.custody.items():
            target = root / path.lstrip("/")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)

    def snapshot(self) -> dict[str, str | None]:
        return {p: sha((self.root / p.lstrip("/")).read_bytes()) if (self.root / p.lstrip("/")).is_file() else None
                for p in self.custody}

    def running(self, identity, release) -> None:
        self.units[I.WITNESS_UNITS[0]].update(ActiveState="active", SubState="running", MainPID=identity[1],
                                              InvocationID=identity[0], NRestarts="0")
        for socket in I.WITNESS_UNITS[1:]:
            self.units[socket].update(ActiveState="active", SubState="listening")
        link = self.root / f"proc/{identity[1]}/cwd"
        link.parent.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(link):
            link.unlink()
        os.symlink(f"{I.RELEASES}/{release}", link)

    def stopped(self) -> None:
        self.units[I.WITNESS_UNITS[0]].update(ActiveState="inactive", SubState="dead", MainPID="0", InvocationID="")
        for socket in I.WITNESS_UNITS[1:]:
            self.units[socket].update(ActiveState="inactive", SubState="dead")

    def run(self, argv, cwd=None, **_kw):
        argv = list(argv)
        self.calls.append(argv)
        name, out = Path(argv[0]).name, ""
        if name == "systemctl" and argv[1] == "show":
            out = "\n".join(f"{k}={v}" for k, v in self.units[argv[-1]].items())
        elif name == "python3" and argv[1:3] == ["-m", "venv"]:
            (Path(argv[3]) / "bin").mkdir(parents=True)
            (Path(argv[3]) / "bin/python").write_bytes(b"#!/bin/false\n")
            os.chmod(Path(argv[3]) / "bin/python", 0o755)
        return subprocess.CompletedProcess(argv, 0, out, "")

    def system(self, **overrides) -> I.System:
        value = dict(root=self.root, run=self.run, user=lambda _n: None, group=lambda _n: None,
                     grouplist=lambda _n, gid: [gid], euid=lambda: 0, hostname=lambda: I.DEV_HOSTNAME, chown=False,
                     owner_uid=os.getuid(), owner_gid=os.getgid())
        value.update(overrides)
        return I.System(**value)

    def status(self, system: I.System, stage: str, release: str) -> dict:
        """The installer `status --expect P1B-10 <release>` seam: RELEASE_SET unless exactly that one release."""
        self.status_calls.append((stage, release))
        entries = [e for e in I._release_entries(system) if not e.startswith(".")]
        failures = (["RELEASE_SET"] if entries != [release] else []) + list(self.installer_failures)
        return {"result": "FAIL" if failures else "PASS", "failures": failures}


def write_tree(root: Path, release: str, payloads: dict[str, bytes]) -> None:
    top = root / f"opt/lilith-authority-dev/releases/{release}"
    manifest = I.manifest_for(release, payloads)
    for relative, data in {**payloads, I.MANIFEST: I.canonical(manifest)}.items():
        target = top.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        os.chmod(target, 0o755 if relative in I.CLI_TARGETS else 0o644)
    (top / "venv").mkdir()
    for directory, _subdirs, _files in os.walk(root / "opt"):
        os.chmod(directory, 0o755)


def archive_for(directory: Path, release: str, payloads: dict[str, bytes]) -> tuple[Path, Path, str]:
    manifest = I.manifest_for(release, payloads)
    raw = I.write_archive(payloads, manifest)
    archive, stamp = directory / f"release-{release}.tar.gz", directory / f"release-{release}.json"
    archive.write_bytes(raw)
    manifest_sha = I.digest(I.canonical(manifest))
    stamp.write_bytes(I.canonical({"schemaVersion": 1, "artifactRole": I.ROLE, "candidateSha": release,
                                   "archiveByteSize": len(raw), "archiveSha256": I.digest(raw),
                                   "manifestSha256": manifest_sha}))
    return archive, stamp, manifest_sha


@unittest.skipUnless(POSIX, "release trees need POSIX modes and symlinks")
class InstallerStageTests(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        house = stack.enter_context(stand_in_wheels())
        self.root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        self.out = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        self.new_payloads = BUILD.build_payloads(ROOT, house)                       # the REAL E-19 payload
        self.assertEqual(sha(self.new_payloads[S.DELTA_MEMBER]), S.DELTA_NEW_SHA256)
        self.old_payloads = dict(self.new_payloads)
        self.old_payloads[S.DELTA_MEMBER] = E.reverse_e19(self.new_payloads[S.DELTA_MEMBER])   # = aee323e bytes
        self.host = StageHost(self.root, self.old_payloads)
        self.system = self.host.system()
        self.archive, self.stamp, self.manifest = archive_for(self.out, NEW, self.new_payloads)

    def status(self):
        return S.e19_status(self.system, OLD, NEW, status=self.host.status)

    def stage(self, **kw):
        kw.setdefault("manifest_sha256", self.manifest)
        return S.stage_e19_stage(self.system, OLD, NEW, kw["manifest_sha256"], self.archive, self.stamp,
                                 status=self.host.status)

    def select(self):
        return S.stage_e19_select(self.system, OLD, NEW, status=self.host.status)

    def retire(self, invocation=REPLACEMENT[0]):
        return S.stage_e19_retire_old(self.system, OLD, NEW, invocation, status=self.host.status)

    def to_selected(self):
        self.stage()
        self.host.stopped()
        self.select()

    def test_u0_layout_is_old_only(self):
        report = self.status()
        self.assertEqual((report["state"], report["result"], report["witness"]), (S.OLD_ONLY, "PASS", "RUNNING"),
                         report["failures"])
        self.assertEqual(report["installerStatus"]["releaseSha"], OLD)

    def test_the_full_release_sequence_with_custody_untouched(self):
        before = self.host.snapshot()
        staged = self.stage()
        self.assertEqual((staged["state"], staged["result"], staged["mutation"]), (S.STAGED, "PASS", "STAGED"),
                         staged["failures"])
        self.assertEqual(os.readlink(self.root / "opt/lilith-authority-dev/current"), f"releases/{OLD}")
        self.assertEqual(staged["installerStatus"]["failures"], ["RELEASE_SET"])           # the only admitted one
        self.host.stopped()                                                                # the separate E19-GO-STOP
        selected = self.select()
        self.assertEqual((selected["state"], selected["result"]), (S.SELECTED, "PASS"), selected["failures"])
        self.assertEqual(os.readlink(self.root / "opt/lilith-authority-dev/current"), f"releases/{NEW}")
        self.host.running(REPLACEMENT, NEW)                                                # the separate E19-GO-START
        retired = self.retire()
        self.assertEqual((retired["state"], retired["result"]), (S.RETIRED, "PASS"), retired["failures"])
        self.assertFalse((self.root / f"opt/lilith-authority-dev/releases/{OLD}").exists())
        self.assertEqual(retired["installerStatus"]["failures"], [])                       # single release restored
        self.assertEqual(self.host.snapshot(), before)
        commands = [Path(call[0]).name + " " + " ".join(call[1:3]) for call in self.host.calls]
        self.assertFalse(any(c.startswith("systemctl ") and not c.startswith("systemctl show") for c in commands))

    def test_stage_refuses_an_unpinned_manifest_and_writes_nothing(self):
        with self.assertRaises(I.InstallError) as caught:
            self.stage(manifest_sha256="0" * 64)
        self.assertEqual(caught.exception.reason, "E19_MANIFEST_NOT_THE_PINNED_MANIFEST")
        self.assertEqual(sorted(p.name for p in (self.root / "opt/lilith-authority-dev/releases").iterdir()), [OLD])

    def test_stage_refuses_any_payload_delta_other_than_pr1_acceptance(self):
        for name, mutate in (("extra member changed", lambda p: p.update(
                {"lilith_authority_dev/ledger.py": p["lilith_authority_dev/ledger.py"] + b"# x\n"})),
                             ("no E-19 change", lambda p: p.update({S.DELTA_MEMBER: self.old_payloads[S.DELTA_MEMBER]}))):
            with self.subTest(name):
                payloads = dict(self.new_payloads)
                mutate(payloads)
                archive, stamp, manifest = archive_for(self.out, NEW, payloads)
                with self.assertRaises(I.InstallError) as caught:
                    S.stage_e19_stage(self.system, OLD, NEW, manifest, archive, stamp, status=self.host.status)
                self.assertTrue(caught.exception.reason.startswith("E19_PAYLOAD_DELTA:"), caught.exception.reason)
                self.assertFalse(any(e.startswith(".") or e == NEW for e in
                                     os.listdir(self.root / "opt/lilith-authority-dev/releases")))

    def test_stage_never_overwrites_and_never_reruns(self):
        (self.root / f"opt/lilith-authority-dev/releases/.{NEW}.staging").mkdir()
        with self.assertRaises(I.InstallError) as caught:
            self.stage()
        self.assertIn("STAGING_RESIDUE", caught.exception.reason)
        shutil.rmtree(self.root / f"opt/lilith-authority-dev/releases/.{NEW}.staging")
        self.stage()
        with self.assertRaises(I.InstallError) as caught:                      # already STAGED: no second stage
            self.stage()
        self.assertTrue(caught.exception.reason.startswith(f"E19_PRE_STATE:{S.STAGED}"))

    def test_select_only_while_the_witness_is_stopped(self):
        with self.assertRaises(I.InstallError):                                 # from OLD_ONLY
            self.select()
        self.stage()
        with self.assertRaises(I.InstallError) as caught:                       # ending incarnation running
            self.select()
        self.assertEqual(caught.exception.reason, "E19_WITNESS_NOT_STOPPED:RUNNING")
        self.host.stopped()
        self.host.units[I.WITNESS_UNITS[1]]["ActiveState"] = "active"           # a lone listening socket
        with self.assertRaises(I.InstallError) as caught:
            self.select()
        self.assertEqual(caught.exception.reason, "E19_WITNESS_NOT_STOPPED:TRANSITIONAL")
        self.assertEqual(os.readlink(self.root / "opt/lilith-authority-dev/current"), f"releases/{OLD}")

    def test_retire_only_for_the_accepted_replacement_running_from_new(self):
        self.stage()
        with self.assertRaises(I.InstallError):                                 # from STAGED
            self.retire()
        self.host.stopped()
        self.select()
        for name, setup, invocation, reason in (
                ("stopped", lambda: None, REPLACEMENT[0], "E19_ACCEPTED_REPLACEMENT_NOT_RUNNING"),
                ("ending id", lambda: self.host.running(REPLACEMENT, NEW), E.ENDING_INCARNATION[0],
                 "E19_REPLACEMENT_INVOCATION_INVALID"),
                ("other id", lambda: self.host.running(REPLACEMENT, NEW), "f" * 32,
                 "E19_ACCEPTED_REPLACEMENT_NOT_RUNNING"),
                ("from OLD", lambda: self.host.running(REPLACEMENT, OLD), REPLACEMENT[0],
                 "E19_REPLACEMENT_NOT_ON_NEW")):
            with self.subTest(name):
                setup()
                with self.assertRaises(I.InstallError) as caught:
                    self.retire(invocation)
                self.assertEqual(caught.exception.reason, reason)
                self.assertTrue((self.root / f"opt/lilith-authority-dev/releases/{OLD}").is_dir())
        self.host.running(REPLACEMENT, NEW)
        self.host.units[I.WITNESS_UNITS[0]]["NRestarts"] = "1"
        with self.assertRaises(I.InstallError):
            self.retire()

    def test_status_is_exact_or_inconsistent(self):
        self.host.installer_failures = ["UNIT_BYTES:/etc/systemd/system/lilith-recovery-witness.service"]
        self.assertEqual(self.status()["result"], "FAIL")
        self.host.installer_failures = []
        (self.root / "opt/lilith-authority-dev/.current.tmp").symlink_to("releases/x")
        self.assertEqual((self.status()["state"], self.status()["result"]), (S.OLD_ONLY, "FAIL"))
        (self.root / "opt/lilith-authority-dev/.current.tmp").unlink()
        write_tree(self.root, "1" * 40, self.old_payloads)                      # a foreign third release
        self.assertEqual(self.status()["state"], S.INCONSISTENT)
        shutil.rmtree(self.root / f"opt/lilith-authority-dev/releases/{'1' * 40}")
        with self.assertRaises(I.InstallError):
            S.e19_status(self.system, "2" * 40, NEW, status=self.host.status)  # OLD must be aee323e
        self.to_selected()
        tree = self.root / f"opt/lilith-authority-dev/releases/{OLD}/lilith_authority_dev/ledger.py"
        tree.write_bytes(tree.read_bytes() + b"# changed\n")
        self.assertTrue(any(f.startswith(f"TREE:{OLD}:") for f in self.status()["failures"]))

    def test_cli_refuses_off_host_and_unknown_forms(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(S.main(["e19-status", OLD, NEW], self.host.system(euid=lambda: 1000)), 2)
            self.assertEqual(S.main(["e19-retire", OLD, NEW], self.system), 2)


# ============================================================================== the real BOOT loader (A, D) ===

PROBE = '''
import json, sys
import e19_maintenance_observer as O


def _try(call):
    try:
        value = call()
        return value if isinstance(value, (dict, str, bool)) else "OK"
    except Exception as exc:  # noqa: BLE001
        return "REFUSED:" + str(getattr(exc, "reason", type(exc).__name__))


def main(argv):
    out = {"bundled": O.BUNDLED, "file": O.__file__,
           "contract": _try(O._check_contract),
           "broker": _try(lambda: O.broker_module().__file__),
           "inputs": _try(lambda: O.decode_inputs(argv[0], argv[1])),
           "forged": _try(lambda: O.decode_inputs(argv[0], "0" * 64))}
    sys.stdout.write(json.dumps(out, sort_keys=True))
    return 0
'''
INPUTS = {"newRelease": NEW, "afterCursor": "s=1;i=2", "expectedHead": X.LEDGER_HEAD, "candidateDigest": X.GENESIS,
          "updatedAt": X.GENESIS_UPDATED_AT}


@unittest.skipUnless(POSIX, "the bundles run on the DEV Linux host (synthetic `__file__` and root checks are POSIX)")
class BootBundleTests(unittest.TestCase):
    """Both live bundles under the REAL loader, with no tool, script or drop-in file reachable."""

    def observer_sources(self, **replace: str) -> dict[str, str]:
        sources = sources_of(X.OBSERVER_BUNDLE)
        sources.update(replace)
        return sources

    def test_the_observer_bundle_needs_no_source_file(self):
        encoded, digest = O.encode_inputs(INPUTS)
        result = run_boot({**self.observer_sources(), "e19_boot_probe": PROBE}, "e19_boot_probe", encoded, digest)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        out = json.loads(result.stdout)
        self.assertEqual(out, {"bundled": True, "file": "<mb6-bundle:e19_maintenance_observer>",
                               "contract": "OK", "broker": "<mb6-bundle:verify_broker_dev_current_incarnation>",
                               "inputs": INPUTS, "forged": "REFUSED:INPUTS_DIGEST"})

    def test_a_substituted_contract_or_broker_is_refused_under_the_loader(self):
        encoded, digest = O.encode_inputs(INPUTS)
        contract = (ROOT / X.CONTRACT).read_text(encoding="utf-8") + "\n# substituted\n"
        broker = (ROOT / X.M9.BROKER).read_text(encoding="utf-8") + "\n# substituted\n"
        out = json.loads(run_boot({**self.observer_sources(e19_p1b10_upgrade=contract), "e19_boot_probe": PROBE},
                                  "e19_boot_probe", encoded, digest).stdout)
        self.assertEqual(out["contract"], "REFUSED:E19_CONTRACT_PIN_MISMATCH")
        out = json.loads(run_boot({**self.observer_sources(verify_broker_dev_current_incarnation=broker),
                                   "e19_boot_probe": PROBE}, "e19_boot_probe", encoded, digest).stdout)
        self.assertEqual(out["broker"], "REFUSED:BROKER_NOT_BUNDLED")

    def test_observe_inline_checks_its_inputs_before_the_host(self):
        encoded, digest = O.encode_inputs(INPUTS)
        forged = run_boot(self.observer_sources(), "e19_maintenance_observer", "observe-inline", encoded, "0" * 64)
        self.assertEqual(forged.returncode, 3)
        self.assertIn(b"REFUSED INPUTS_DIGEST", forged.stderr)
        genuine = run_boot(self.observer_sources(), "e19_maintenance_observer", "observe-inline", encoded, digest)
        self.assertNotEqual(genuine.returncode, 0)                    # off-host: the DEV root check, never a read
        self.assertIn(b"NOT_", genuine.stderr)
        self.assertNotIn(b"INPUTS", genuine.stderr)

    def test_the_stage_bundle_loads_with_the_unchanged_installer(self):
        result = run_boot(sources_of(X.STAGES_BUNDLE), "e19_release_stages", "e19-status", OLD, NEW)
        self.assertEqual(result.returncode, 2, result.stderr.decode(errors="replace"))
        self.assertRegex(result.stderr.decode(), r"\Ae19_release_stages: REFUSED NOT_(ROOT|DEV_HOST)\n\Z")


# ====================================================================== the operator (B, C) on a fake DEV ===

class FakeDev:
    """DEV behind the operator's transport seams. Observations are the REAL observer over the synthetic host; the
    stages, STOP and START move the synthetic host exactly as the reviewed commands would."""

    PASS_LINES = {"P1B-9b": b"MB9_WITNESS_DENIAL_PROOF=PASS phase=P1B-9b denied=7 allowed_by_design=1 allowed=0\n",
                  "P1B-10": b"MB10_HOLD_DENIAL_PROOF=PASS phase=P1B-10 denied=4 allowed=0\n",
                  "P1B-5": b"AUTHORITY_CUSTODY_DENIAL_PROOF=PASS phase=P1B-5\n"}

    def __init__(self, host: OT.SyntheticHost):
        self.host, self.mutations, self.observations = host, [], 0
        self.start_effect = "ONE_LOAD"
        self.host_reads: dict[str, bytes] = {}
        self.e19_state = None

    @staticmethod
    def done(code=0, out=b"", err=b""):
        return subprocess.CompletedProcess([], code, out, err)

    def plink(self, command: str, payload: bytes):
        match = re.search(r"grep -qx '([0-9a-f]{64})'.*sudo -n (\S+) -I -B -c \"[^\"]+\" (\S+) (\S+) (.*)\Z", command)
        assert match is not None, command
        digest, interpreter, pins, entry, args = match.groups()
        assert sha(payload.rstrip(b"\n")) == digest                       # the remote shell's own check
        sources = json.loads(gzip.decompress(base64.b64decode(payload)))
        declared = dict(item.split("=", 1) for item in pins.split(","))
        assert sorted(sources) == sorted(declared) and all(sha(s.encode()) == declared[n] for n, s in sources.items())
        argv = shlex.split(args)
        if entry == "e19_maintenance_observer":
            assert interpreter == X.M9.RELEASE_PYTHON and argv[0] == "observe-inline"
            self.observations += 1
            inputs = O.decode_inputs(argv[1], argv[2])
            h = self.host
            bundle = O.observe(inputs, root=h.root, units=h.units, journal_tail=lambda: h.tail,
                               invocations=h.invocations, cwd=h.cwd, activation=lambda: h.activation,
                               health=h.health_call, w10=lambda _i, _r: h.w10(), broker=lambda: dict(h.broker),
                               cursor_retained=lambda _c: h.retained, new_release=NEW, owner=h.owner)
            return self.done(out=json.dumps(bundle).encode())
        if entry == "e19_release_stages":
            assert interpreter == X.M9.SYSTEM_PYTHON
            if argv[0] == "e19-status":
                return self.done(out=json.dumps({"state": self.e19_state, "result": "PASS"}).encode())
            self.mutations.append(argv[0])
            if argv[0] == "e19-stage":
                assert argv[1:4] == [OLD, NEW, MANIFEST]
                self.host.to_u1()
            elif argv[0] == "e19-select":
                self.host.select(NEW)
            elif argv[0] == "e19-retire-old":
                assert argv[3] == REPLACEMENT[0]
                shutil.rmtree(self.host.p(f"{O.RELEASES}/{OLD}"))
            return self.done(out=b'{"result": "PASS"}')
        return self.done()                                                 # W9 / W10 host-read bundles

    def mutation(self, command: str):
        self.mutations.append(command)
        if command == X.STOP_COMMAND:
            self.host.witness = ("STOPPED", ("", "0"), OLD)
        elif command == X.START_COMMAND:
            if self.start_effect == "FAILED":
                self.host.witness_loads = ["a" * 32]
                return self.done(code=1, err=b"Job for lilith-recovery-witness.service failed")
            self.host.witness = ("RUNNING", REPLACEMENT, NEW)
            self.host.witness_loads = [REPLACEMENT[0]] + (["b" * 32] if self.start_effect == "TWO_LOADS" else [])
        return self.done()

    def read(self, command: str):
        for proof, line in self.PASS_LINES.items():
            if command.endswith(f"-I -B - {proof}"):
                return self.done(out=line)
        return self.done()


MANIFEST = hashlib.sha256(b"synthetic NEW manifest").hexdigest()


class FakeOperator(X.Operator):
    def bind(self, dev: FakeDev) -> "FakeOperator":
        self.dev = dev
        return self

    def pins(self, repo):
        return {"control": "c" * 40, "operatorSha256": "d" * 64, "tools": dict(X.TOOL_PINS),
                "result": "E19_TOOL_PINS_EXACT"}

    def tool_bytes(self, repo, path):
        data = (ROOT / path).read_bytes()
        assert sha(data) == X.TOOL_PINS[path], path
        return data

    def plink_stdin(self, command, data):
        return self.dev.plink(command, data)

    def _invoke(self, command):
        return self.dev.mutation(command)

    def ssh(self, command):
        return self.dev.read(command)


@unittest.skipUnless(POSIX, "the synthetic host needs POSIX symlinks, ownership and modes")
class OperatorCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.dict(E.PRESERVED_PINS, OT.SYNTHETIC_PINS)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.host = OT.SyntheticHost(Path(tmp.name) / "host")
        self.work = Path(tmp.name) / "work"
        self.work.mkdir()
        self.dev = FakeDev(self.host)
        self.op = FakeOperator(new_release=NEW, new_manifest=MANIFEST).bind(self.dev)
        self.repo = ROOT

    def write(self, name: str, text: str) -> Path:
        path = self.work.parent / name
        path.write_bytes(text.encode("ascii"))
        return path

    def accept_u0(self):
        self.assertEqual(self.op.observe(self.repo, self.work, "U0")["phase"], E.U0)
        statement = self.write("u0.txt", self.op.render(self.repo, self.work, "U0")["text"])
        self.op.accept_u0(self.repo, self.work, statement)
        self.host.tail = OT.cursor("2b01")
        self.assertEqual(self.op.observe(self.repo, self.work, "U0_AGAIN")["phase"], E.U0)

    def go(self, step: str) -> Path:
        return self.write(f"go-{step}.txt", self.op.render(self.repo, self.work, step)["text"])

    def step(self, step: str) -> dict:
        return getattr(self.op, step.lower())(self.repo, self.work, self.go(step))

    def run_to(self, last: str) -> None:
        for step in ("STAGE", "STOP", "SELECT", "START"):
            report = self.step(step)
            self.assertTrue(report["result"].startswith(f"E19_{step}_REACHED_"), report)
            if step == last:
                return

    def accept_replacement(self) -> dict:
        verified = self.op.post9a_r(self.repo, self.work)
        self.assertEqual(verified["result"], "POST9A_R_VERIFIED", verified["reasons"])
        statement = self.write("replacement.txt", self.op.render(self.repo, self.work, "REPLACEMENT")["text"])
        return self.op.accept_replacement(self.repo, self.work, statement)


class OperatorTests(OperatorCase):
    def test_the_full_controlled_transition_u0_to_u5(self):
        self.accept_u0()
        self.run_to("START")
        self.accept_replacement()
        report = self.step("RETIRE")
        self.assertEqual(report["result"], f"E19_RETIRE_REACHED_{E.U5}", report)
        self.assertEqual(self.dev.mutations, ["e19-stage", X.STOP_COMMAND, "e19-select", X.START_COMMAND,
                                              "e19-retire-old"])                    # exactly one invocation each
        self.assertEqual(sorted(p.name for p in (self.work / "attempts").iterdir()),
                         sorted(f"{marker}.json" for *_, marker in X.STEPS.values()))
        for marker in ("e19-stop", "e19-start"):
            record = json.loads((self.work / "attempts" / f"{marker}.json").read_text(encoding="ascii"))
            self.assertEqual(record["invocationsPermitted"], 1)

    def test_no_step_runs_out_of_order_or_twice(self):
        self.accept_u0()
        with self.assertRaises(X.Stop) as caught:
            self.op.render(self.repo, self.work, "STOP")                          # latest observation is U0
        self.assertTrue(caught.exception.code.startswith("LATEST_OBSERVATION_NOT_U1"))
        self.run_to("STOP")
        go = self.work.parent / "go-STOP.txt"
        with self.assertRaises(X.Stop):
            self.op.stop(self.repo, self.work, go)                                  # consumed: never again
        self.assertEqual(self.dev.mutations.count(X.STOP_COMMAND), 1)
        with self.assertRaises(X.Stop) as caught:
            self.op.start(self.repo, self.work, go)                                 # a STOP go is not a START go
        self.assertIn(caught.exception.code, ("GO_LINE_MISSING", f"LATEST_OBSERVATION_NOT_{E.U3}:{E.U2}"))
        self.assertNotIn(X.START_COMMAND, self.dev.mutations)

    def test_a_changed_host_fails_the_fresh_gate_before_the_marker(self):
        self.accept_u0()
        self.run_to("STAGE")
        go = self.go("STOP")
        self.host.witness = ("RUNNING", (OT.H32("restarted"), "4242"), OLD)         # changed after the render
        self.host.witness_loads = [OT.H32("restarted")]
        with self.assertRaises(X.Stop) as caught:
            self.op.stop(self.repo, self.work, go)
        self.assertTrue(caught.exception.code.startswith(f"GATE_NOT_{E.U1}"), caught.exception.code)
        self.assertFalse((self.work / "attempts" / "e19-stop.json").exists())
        self.assertNotIn(X.STOP_COMMAND, self.dev.mutations)

    def test_a_failed_start_is_a_counted_load_and_never_retried(self):
        self.accept_u0()
        self.run_to("SELECT")
        self.dev.start_effect = "FAILED"
        report = self.step("START")
        self.assertEqual((report["result"], report["postPhase"]), ("E19_START_STOP", E.STOP_START_FAILED))
        with self.assertRaises(X.Stop):
            self.op.start(self.repo, self.work, self.work.parent / "go-START.txt")
        self.assertEqual(self.dev.mutations.count(X.START_COMMAND), 1)

    def test_an_additional_witness_load_is_a_stop(self):
        self.accept_u0()
        self.run_to("SELECT")
        self.dev.start_effect = "TWO_LOADS"
        report = self.step("START")
        self.assertEqual((report["result"], report["postPhase"]), ("E19_START_STOP", E.STOP_LOADS))

    def test_retire_needs_post9a_r_and_the_owner_acceptance_first(self):
        self.accept_u0()
        self.run_to("START")
        with self.assertRaises(X.Stop) as caught:
            self.op.render(self.repo, self.work, "RETIRE")
        self.assertEqual(caught.exception.code, "REPLACEMENT_ACCEPTANCE_REQUIRED")
        with self.assertRaises(X.Stop):
            self.op.render(self.repo, self.work, "REPLACEMENT")                    # no POST9A-R yet
        self.accept_replacement()
        go = self.go("RETIRE")
        self.host.witness = ("RUNNING", (OT.H32("another"), "777"), NEW)            # not the accepted identity
        with self.assertRaises(X.Stop):
            self.op.retire(self.repo, self.work, go)
        self.assertNotIn("e19-retire-old", self.dev.mutations)
        self.assertTrue(self.host.p(f"{O.RELEASES}/{OLD}").is_dir())

    def test_a_reworded_statement_is_refused(self):
        self.op.observe(self.repo, self.work, "U0")
        text = self.op.render(self.repo, self.work, "U0")["text"].replace("I accept", "I  accept")
        with self.assertRaises(X.Stop):
            self.op.accept_u0(self.repo, self.work, self.write("u0.txt", text))
        self.assertFalse((self.work / X.ACCEPT_DIR / X.U0_FILE).exists())

    def test_inputs_not_echoed_or_new_release_missing_are_refused(self):
        original = self.dev.plink

        def tampered(command, payload):
            result = original(command, payload)
            bundle = json.loads(result.stdout)
            bundle["inputsSha256"] = "0" * 64
            return self.dev.done(out=json.dumps(bundle).encode())
        self.dev.plink = tampered
        self.assertEqual(self.op.observe(self.repo, self.work, "U0")["result"], "E19_OBSERVATION_NOT_RECEIVED")
        with self.assertRaises(X.Stop) as caught:
            FakeOperator().bind(self.dev).observe(self.repo, self.work, "U0")      # the merged pins are still None
        self.assertEqual(caught.exception.code, "NEW_RELEASE_NOT_ESTABLISHED")

    def test_missing_journal_evidence_is_never_a_phase(self):
        self.accept_u0()
        self.host.retained = False                                                 # the U0 cursor was rotated out
        self.assertEqual(self.op.observe(self.repo, self.work, "LATE")["phase"], E.UNKNOWN)
        with self.assertRaises(X.Stop):
            self.op.render(self.repo, self.work, "STAGE")


# ================================================================== two-release-aware host reads (C) ===

def readiness(release: str, modules: dict[str, str]) -> bytes:
    probe = {"modules": {f"m{i}": [path, digest] for i, (path, digest) in enumerate(sorted(modules.items()))},
             "ledgerCli": M6.LEDGER_CLI_SHA256, "verifyCli": X.A.VERIFY_CLI_SHA256,
             "witnessOwnerCli": X.M9.OWNER_CLI_SHA256, "release": "/opt/lilith-authority-dev/current",
             "deserialize": True}
    return f"releases/{release}\nRELEASE_PYTHON=executable\n{json.dumps(probe)}\n".encode()


class ReadinessTests(unittest.TestCase):
    OLD_MODULES = {**M6.RELEASE_MODULES, **M6.PROVISION_MODULES}

    def test_each_release_by_its_own_pins(self):
        new_modules = E.new_release_module_pins(self.OLD_MODULES)
        self.assertEqual({k for k in new_modules if new_modules[k] != self.OLD_MODULES[k]}, {S.DELTA_MEMBER})
        self.assertTrue(X.readiness_ok_for(readiness(OLD, self.OLD_MODULES), OLD, NEW))
        self.assertTrue(X.readiness_ok_for(readiness(NEW, new_modules), NEW, NEW))
        self.assertTrue(X.M9.Operator.readiness_ok(readiness(OLD, self.OLD_MODULES)))   # = the M-B10 judgement

    def test_mixed_or_wrong_release_fails(self):
        new_modules = E.new_release_module_pins(self.OLD_MODULES)
        for raw, release in ((readiness(NEW, self.OLD_MODULES), NEW),          # NEW selected, OLD bytes loaded
                             (readiness(OLD, new_modules), OLD),               # OLD selected, NEW bytes loaded
                             (readiness(NEW, new_modules), OLD),               # selector not the phase's release
                             (readiness("1" * 40, new_modules), "1" * 40)):    # a foreign release has no pins
            self.assertFalse(X.readiness_ok_for(raw, release, NEW))
        self.assertFalse(X.M9.Operator.readiness_ok(readiness(NEW, new_modules)))   # why M-B10 fails after select


@unittest.skipUnless(POSIX, "the synthetic host needs POSIX symlinks, ownership and modes")
class HostReadTests(OperatorCase):
    def host_reads(self, phase: str, release: str, state: str, readiness_release: str) -> dict:
        modules = {**M6.RELEASE_MODULES, **M6.PROVISION_MODULES}
        if readiness_release == NEW:
            modules = E.new_release_module_pins(modules)
        outputs = {"identity": b"", "custody": b"TMP_RESIDUE_END\n", "readiness": readiness(release, modules),
                   "preservation": b"", "observer": b"", "w5verifier": b"", "mb6verifier": b"", "w8verifier": b""}
        self.dev.e19_state = state
        with mock.patch.object(FakeOperator, "_package_b_commands",
                               lambda _self, _repo, _args: {k: (lambda v=v: self.dev.done(out=v))
                                                            for k, v in outputs.items()}):
            return self.op.host(self.repo, self.work, phase)

    def test_u4_and_u5_pass_on_new_and_u0_u1_on_old(self):
        for phase, release, state in ((E.U0, OLD, "E19_OLD_ONLY"), (E.U1, OLD, "E19_NEW_STAGED"),
                                      (E.U4, NEW, "E19_NEW_SELECTED"), (E.U5, NEW, "E19_OLD_RETIRED")):
            with self.subTest(phase):
                report = self.host_reads(phase, release, state, release)
                self.assertEqual(report["result"], f"E19_HOST_{phase}_PASS", report)

    def test_the_wrong_release_or_state_is_not_pass(self):
        self.assertEqual(self.host_reads(E.U4, NEW, "E19_NEW_SELECTED", OLD)["result"], f"E19_HOST_{E.U4}_NOT_PASS")
        self.assertEqual(self.host_reads(E.U4, NEW, "E19_NEW_STAGED", NEW)["result"], f"E19_HOST_{E.U4}_NOT_PASS")
        with self.assertRaises(X.Stop):
            self.op.host(self.repo, self.work, E.U2)                       # no socket contact phase: observer only


if __name__ == "__main__":
    unittest.main()
