"""15B2b-B1b-3e M-B6 PROVISION_LEDGER remediation (TEST-ONLY): the ledger tool halves, the fixed CLI, the
installer P1B-6 contract, the read-only M-B6 verifier / W6 classifier, the bounded recovery tool, the
owner-computed expected head, and the M-B6 operator.

Record: docs/architecture/slice-15b2b-b1b3e-mb6-ledger-remediation.md.

The host is the M-B4/M-B5 synthetic tree (the PR-1S installer `FakeHost` under a TEMPORARY root) brought to
`status --expect P1B-5` with the TEST world's anchors and Registry V1 (throwaway TEST keys). The ledger is
provisioned by the unchanged reviewed `ledger_tool` / `DurableAuthorityLedgerV1` with the test process as the
"signer". Crash windows are produced by the real code, interrupted (a snapshot of the files at the crash
point). Nothing touches `/`, DEV, the S25 or any real key. Failure messages redact every 64-hex value.

Some tests need a non-root uid (the signer half refuses euid 0), and the installer P1B-6 positive contract
needs the test uid to satisfy the system-account contract (0 < uid < 1000) or root; each such test says so
when it is skipped.
"""

from __future__ import annotations

import contextlib
import dataclasses
import gzip
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _p in (ROOT / "services/core-api", ROOT / "services/owner-memory-control", TOOLS,
           ROOT / "services/authority-dev", ROOT / "services/authority-dev/ceremony",
           ROOT / "services/authority-dev/tests", ROOT / "services/recovery-witness", Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

POSIX = os.name == "posix"
HAVE_CRYPTO = all(importlib.util.find_spec(m) is not None for m in ("cryptography", "rfc8785", "fido2"))
HAVE_DESERIALIZE = hasattr(sqlite3.Connection, "deserialize")
UID = os.getuid() if POSIX else 0
GID = os.getgid() if POSIX else 0
NON_ROOT = POSIX and UID != 0

import mb6_ledger_verifier as V  # noqa: E402  (stdlib only at import)
import mb6_operator as O  # noqa: E402
import post_reboot_repin as RP  # noqa: E402

if HAVE_CRYPTO and POSIX:
    import install_authority_dev as I
    import mb4_mb5_installable_inputs as D
    import mb4_mb5_trust_install_verifier as V5
    import mb6_expected_ledger_head as E
    import mb6_ledger_recovery as R
    import test_pr1s_installer_upgrade as U
    from lilith_authority_dev import ledger as L
    from lilith_authority_host import inputs as HI
    from lilith_authority_host import paths as P
    from lilith_authority_root import cli as CLI
    from lilith_authority_root import ledger_tool as LT
    from lilith_owner_memory import authority_ledger_journal as J
    from test_b1b3e_mb4_mb5_installable_inputs import P as WP, TestSources
    from test_custody_preparation import build_archive, fake_wheels

STANDIN_KWIT = b"TEST_ONLY stand-in K-WIT ciphertext (never a credential)"
REAL_PIN_DERIVED_HEAD = "19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630"
REAL_GENESIS_OP_JCS_SHA256 = "8e3bdbdf3f3730de5ad031d36eb390888fc6e0f65307d947522b0138ffcd7b60"
REAL_SCHEMA_FINGERPRINT = "65127a68c61d4dba390e01c61d01a76fdc54e830c374cb05069b0ab0c50d9cb7"


def _r(text: str) -> str:
    import re
    return re.sub(r"[0-9a-f]{64}", "<redacted>", str(text))


class Redacted:
    def _formatMessage(self, msg, standardMsg):
        return _r(super()._formatMessage(msg, standardMsg))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tree(root: Path) -> dict[str, tuple]:
    out = {}
    for directory, dirs, files in os.walk(root):
        for name in dirs + files:
            path = Path(directory) / name
            meta = os.lstat(path)
            digest = sha(path.read_bytes()) if stat.S_ISREG(meta.st_mode) else None
            out[str(path.relative_to(root))] = (stat.S_IFMT(meta.st_mode), stat.S_IMODE(meta.st_mode), meta.st_ino,
                                                meta.st_uid, digest)
    return out


class _SnapshotOnClose:
    """A connection proxy: on `close()` (after COMMIT) copy the ledger files first — the crash point."""

    def __init__(self, conn, path: Path, out: Path):
        self._conn, self._path, self._out = conn, path, out

    def execute(self, *args):
        return self._conn.execute(*args)

    def close(self):
        if not self._out.exists():
            self._out.mkdir()
            for suffix in ("", "-wal", "-shm"):
                source = Path(f"{self._path}{suffix}")
                if source.exists():
                    shutil.copyfile(source, self._out / source.name)
        self._conn.close()


# --------------------------------------------------------------------------------------------- world ---

@unittest.skipUnless(HAVE_CRYPTO and POSIX and HAVE_DESERIALIZE,
                     "POSIX owner/mode semantics, sqlite3 deserialize, cryptography/rfc8785/fido2 required")
class Mb6Base(Redacted, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        world = Path(cls._tmp.name) / "world"
        world.mkdir()
        cls.src = TestSources(world)
        cls.files = dict(D.derive_from_members(cls.src.members, cls.src.pins).files)
        other = Path(cls._tmp.name) / "other"
        other.mkdir()
        cls.other = TestSources(other)
        cls.other_files = dict(D.derive_from_members(cls.other.members, cls.other.pins).files)
        w = cls.src.world.accepted
        cls.trust_pins = V5.TrustInstallPinsV1(
            root_anchor_sha256=sha(cls.files["registry-root.json"]),
            witness_anchor_sha256=sha(cls.files["witness-anchor.json"]),
            registry_sha256=sha(cls.files["authority-registry.v1.json"]), registry_digest=cls.src.pins.registry_digest,
            kroot_public_key_sha256=w.kroot_public_key_sha256, root_key_id=WP.L.ROOT_KEY_ID,
            kwit_public_key_sha256=w.kwit_public_key_sha256, kwit_key_id=w.kwit_key_id,
            kact_public_key_sha256=w.kact_public_key_sha256, kact_key_id=w.kact_key_id, epoch_random=WP.EPOCH,
            policy_version=WP.L.POLICY_VERSION)
        cls.pins = V.LedgerPinsV1(schema_fingerprint=V.ACCEPTED_PINS.schema_fingerprint, kact_key_id=w.kact_key_id,
                                  epoch_counter=1, epoch_random=WP.EPOCH, policy_version=WP.L.POLICY_VERSION,
                                  registry_version=1)
        cls.expected_pins = E.ExpectedPinsV1(
            registry_sha256=cls.trust_pins.registry_sha256, root_anchor_sha256=cls.trust_pins.root_anchor_sha256,
            registry_digest=cls.src.pins.registry_digest, kroot_public_key_sha256=w.kroot_public_key_sha256,
            root_key_id=WP.L.ROOT_KEY_ID, kact_key_id=w.kact_key_id,
            kact_public_key_sha256=w.kact_public_key_sha256, epoch_random=WP.EPOCH,
            policy_version=WP.L.POLICY_VERSION)
        cls.op = V.pinned_genesis_op(cls.pins)
        cls.head = V.ledger_head(cls.op)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        directory = self.stack.enter_context(tempfile.TemporaryDirectory())
        out = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.scratch = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        wheels = self.stack.enter_context(fake_wheels())
        self.stack.enter_context(U.accepted_current())
        self.host, self.system = U.old_host(directory)
        archive, attestation, _ = build_archive(Path(out), wheels)
        baseline = I.parse_baseline(U.baseline_file(out, self.system), U.OLD)
        U.full_upgrade(self.host, self.system, baseline, archive, attestation)
        for stage_ in (I.stage_custody, I.stage_witness_account, I.stage_witness_units):
            self.assertEqual(stage_(self.system, U.NEW)["result"], "PASS")
        self.host.daemon_reload()
        self.assertEqual(I.stage_skeleton(self.system, U.NEW)["result"], "PASS")
        blob = self.target(I.WITNESS_BLOB)
        blob.write_bytes(STANDIN_KWIT)
        os.chmod(blob, 0o600)
        inputs = Path(out) / "inputs"
        inputs.mkdir()
        for name, data in self.files.items():
            (inputs / name).write_bytes(data)
        self.assertEqual(I.stage_install_anchors(self.system, U.NEW, inputs / "registry-root.json",
                                                 inputs / "witness-anchor.json")["result"], "PASS")
        self.assertEqual(I.stage_install_registry(self.system, U.NEW, inputs / "authority-registry.v1.json")["result"],
                         "PASS")
        self.assertEqual(self.status("P1B-5")["result"], "PASS")
        self.root = self.host.root

    # ------------------------------------------------------------------------------------------ helpers ---

    def target(self, absolute: str) -> Path:
        return self.host.root / absolute.lstrip("/")

    def status(self, stage):
        return I.status(self.system, stage, U.NEW)

    def verify(self, head=None, signer=None, **kw) -> dict:
        return V.evaluate(head or self.head, root=self.root, owner_uid=UID, owner_gid=GID,
                          signer=signer or (UID, GID), pins=kw.pop("pins", self.pins),
                          trust_pins=kw.pop("trust_pins", self.trust_pins))

    def provision(self, *, as_signer=True) -> dict:
        """The two reviewed halves on the synthetic root; the signer half is the real one when not root."""
        calls = []

        def run_as_signer(version):
            calls.append(version)
            if as_signer:
                LT.provision_as_signer(environment="dev", registry_version=version, root=self.root, owner_uid=UID,
                                       euid=UID, signer_uid=UID)
            else:
                L.DurableAuthorityLedgerV1.provision(self.target(P.AUTHORITY_LEDGER), environment="dev",
                                                     genesis=J.genesis_op(self.registry()), expected_uid=UID)
            return 0
        result = LT.provision(environment="dev", registry_version=1, euid=0, signer_uid=UID, signer_gid=GID,
                              run_as_signer=run_as_signer, root=self.root, owner_uid=UID, chown=False)
        self.assertEqual(calls, [1])
        return result

    def registry(self) -> dict:
        return json.loads(self.files["authority-registry.v1.json"])

    def state(self) -> Path:
        return self.target(V.STATE_DIR)

    def exact_dir(self):
        self.state().mkdir(mode=0o700)
        os.chmod(self.state(), 0o700)

    def crash_snapshot(self) -> Path:
        """Provision with the real durable ledger, but capture the files at the first connection's close
        (after COMMIT, before the checkpoint): the W6-4 crash window with the data still in the WAL."""
        snap = self.scratch / "crash"
        real = L._connect
        path = self.target(P.AUTHORITY_LEDGER)
        first = []

        def connect(p):
            conn = real(p)
            if not first:
                first.append(1)
                return _SnapshotOnClose(conn, path, snap)
            return conn
        with mock.patch.object(L, "_connect", connect):
            self.provision(as_signer=False)
        shutil.rmtree(self.state())
        return snap

    def place(self, files: dict[str, bytes]):
        self.exact_dir()
        for name, data in files.items():
            p = self.state() / name
            p.write_bytes(data)
            os.chmod(p, 0o600)


# ---------------------------------------------------------------------------- the ledger tool halves ---

class LedgerToolTests(Mb6Base):
    @unittest.skipUnless(NON_ROOT, "the signer half refuses euid 0; needs a non-root test uid")
    def test_root_half_and_signer_half_success(self):
        before = tree(self.root)
        result = self.provision()
        self.assertEqual(result["stateDirectory"], "CREATED")
        self.assertEqual((result["ledgerSequence"], result["ledgerHead"]), (1, self.head))
        self.assertEqual(result["genesisOp"], self.op)
        self.assertIs(result["authorityGranted"], False)
        # only the state directory and the ledger appeared; nothing else changed (no later state)
        after = tree(self.root)
        added = sorted(set(after) - set(before))
        self.assertEqual(added, ["var/lib/lilith-authority-dev", "var/lib/lilith-authority-dev/authority_ledger.db"])
        self.assertEqual({k: v for k, v in after.items() if k in before}, before)
        observed = L.observe_copy(self.target(P.AUTHORITY_LEDGER), environment="dev")
        self.assertEqual((observed.sequence, observed.head), (1, self.head))

    @unittest.skipUnless(NON_ROOT, "the signer half refuses euid 0; needs a non-root test uid")
    def test_signer_half_alone_success_and_refusals(self):
        self.exact_dir()
        observed = LT.provision_as_signer(environment="dev", registry_version=1, root=self.root, owner_uid=UID,
                                          euid=UID, signer_uid=UID)
        self.assertEqual((observed.sequence, observed.head), J.initial_position(self.registry()))
        self.assertEqual(observed.head, self.head)
        with self.assertRaises(LT.LedgerToolError) as caught:
            LT.provision_as_signer(environment="dev", registry_version=1, root=self.root, owner_uid=UID, euid=UID,
                                   signer_uid=UID)
        self.assertEqual(caught.exception.reason, "LEDGER_TOOL_ALREADY_PROVISIONED")     # existing DB refusal
        with self.assertRaises(LT.LedgerToolError) as caught:
            LT.provision_as_signer(environment="dev", registry_version=1, root=self.root, owner_uid=UID, euid=0,
                                   signer_uid=0)
        self.assertEqual(caught.exception.reason, "LEDGER_TOOL_NOT_SIGNER")

    @unittest.skipUnless(NON_ROOT, "the signer half refuses euid 0; needs a non-root test uid")
    def test_exact_empty_directory_is_adopted_and_unsafe_directory_refused(self):
        self.exact_dir()
        self.assertEqual(self.provision()["stateDirectory"], "ADOPTED_NO_MUTATION")
        shutil.rmtree(self.state())
        self.state().mkdir(mode=0o755)
        os.chmod(self.state(), 0o755)
        with self.assertRaises(LT.LedgerToolError) as caught:
            self.provision()
        self.assertEqual(caught.exception.reason, "LEDGER_TOOL_STATE_DIRECTORY_UNSAFE")
        self.assertEqual(sorted(os.listdir(self.state())), [])                  # refused before any file

    def test_sidecar_or_journal_before_provisioning_is_refused(self):
        for name in ("authority_ledger.db", "authority_ledger.db-wal", "authority_ledger.db-shm",
                     "authority_ledger.db-journal"):
            with self.subTest(name):
                self.exact_dir()
                (self.state() / name).write_bytes(b"")
                with self.assertRaises(LT.LedgerToolError) as caught:
                    LT.prepare_state_directory(root=self.root, signer_uid=UID, signer_gid=GID, chown=False)
                self.assertEqual(caught.exception.reason, "LEDGER_TOOL_ALREADY_PROVISIONED")
                shutil.rmtree(self.state())

    def test_ledger_tool_never_activates_a_unit(self):
        for module in (LT, CLI):
            source = Path(module.__file__).read_text(encoding="utf-8").split('"""', 2)[2]
            for forbidden in ("systemctl", "daemon-reload", "systemd-creds", "credstore"):
                self.assertNotIn(forbidden, source, (module.__name__, forbidden))


# ---------------------------------------------------------------------------------- the fixed CLI ---

class CliTests(Mb6Base):
    def _patched(self):
        stack = contextlib.ExitStack()
        real_inputs = HI.read_host_inputs
        stack.enter_context(mock.patch.object(HI, "read_host_inputs", lambda **kw: real_inputs(
            environment=kw["environment"], root=self.root, owner_uid=UID)))
        stack.enter_context(mock.patch.object(P, "AUTHORITY_STATE", str(self.state())))
        stack.enter_context(mock.patch.object(P, "AUTHORITY_LEDGER", str(self.target(P.AUTHORITY_LEDGER))))
        stack.enter_context(mock.patch.object(CLI, "_signer_ids", lambda: (UID, GID)))
        return stack

    @unittest.skipUnless(NON_ROOT, "the signer half refuses euid 0; needs a non-root test uid")
    def test_cli_provision_and_observe(self):
        seen = []

        def fake_run(argv, env=None, check=None, timeout=None):
            seen.append((argv, env, timeout))
            return subprocess.CompletedProcess(argv, CLI.main(argv[4].rsplit("/", 1)[1], argv[5:], euid=UID))
        out, err = io.StringIO(), io.StringIO()
        # The real root half runs unpatched: the state paths point into the synthetic root, and its chown is
        # to the test process's own uid/gid (permitted unprivileged).
        with self._patched(), mock.patch.object(CLI.subprocess, "run", fake_run), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = CLI.main("lilith-authority-ledger-dev", ["provision", "1"], euid=0)
        self.assertEqual((code, err.getvalue()), (0, ""))
        self.assertEqual(seen, [(["/usr/sbin/runuser", "-u", "lilith-authority-dev", "--",
                                  "/usr/local/sbin/lilith-authority-ledger-dev", "provision-as-signer", "1"],
                                 CLI.FIXED_ENV, 120)])
        stdout = out.getvalue().encode("ascii")
        self.assertEqual(stdout, V.expected_cli_stdout(self.head, "CREATED", self.pins))
        self.assertEqual(V.classify_transcript(0, stdout, b"", expected_head=self.head, state_directory="CREATED",
                                               pins=self.pins), (V.CLI_SUCCESS_EXACT, None))
        out = io.StringIO()
        with self._patched(), contextlib.redirect_stdout(out):
            self.assertEqual(CLI.main("lilith-authority-ledger-dev", ["observe"], euid=0), 0)
        observed = json.loads(out.getvalue())
        self.assertEqual((observed["ledgerSequence"], observed["ledgerHead"], observed["authorityGranted"]),
                         (1, self.head, False))
        err = io.StringIO()
        with self._patched(), contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(CLI.main("lilith-authority-ledger-dev", ["provision", "1"], euid=0), 2)
        self.assertEqual(err.getvalue(), "lilith-authority-ledger-dev: REFUSED LEDGER_TOOL_ALREADY_PROVISIONED\n")

    def test_signer_timeout_is_an_uncaught_traceback_in_the_installed_cli(self):
        """F: characterization. The installed CLI does not catch `TimeoutExpired`; the operator, not the
        runtime, classifies it (`CLI_FAILED_UNCLASSIFIED`), and the host is then classified by the verifier."""
        def timeout(argv, **_kw):
            raise subprocess.TimeoutExpired(argv, 120)
        with self._patched(), mock.patch.object(CLI.subprocess, "run", timeout):
            with self.assertRaises(subprocess.TimeoutExpired):
                CLI.main("lilith-authority-ledger-dev", ["provision", "1"], euid=0)
        self.assertEqual(sorted(os.listdir(self.state())), [])                   # W6-2: the root half finished
        self.assertEqual(self.verify()["phase"], V.W6_2)
        traceback = b"Traceback (most recent call last):\n  ...\nsubprocess.TimeoutExpired: ...\n"
        self.assertEqual(V.classify_transcript(1, b"", traceback, expected_head=self.head, state_directory="CREATED"),
                         (V.CLI_FAILED_UNCLASSIFIED, "EXIT_1"))


# ------------------------------------------------------------------------- installer P1B-6 contract ---

class InstallerContractTests(Mb6Base):
    def test_positive_status_expect_p1b6(self):
        if 0 < UID < 1000:
            signer = self.host.users[I.SERVICE_USER]
            signer.pw_uid, signer.pw_gid = UID, GID
            self.host.groups[I.SERVICE_GROUP].gr_gid = GID
            self.assertEqual(self.status("P1B-5")["result"], "PASS")
            self.provision()
        elif UID == 0:
            self.provision(as_signer=False)
            signer = self.host.users[I.SERVICE_USER]
            for path in (self.state(), self.target(P.AUTHORITY_LEDGER)):
                os.chown(path, signer.pw_uid, signer.pw_gid)
        else:
            self.skipTest("the system-account contract needs 0 < uid < 1000, or root to chown (CI runs uid >= 1000)")
        report = self.status("P1B-6")
        self.assertEqual(report["result"], "PASS", report["failures"])
        self.assertIn("UNEXPECTED_PRESENT:" + I.AUTHORITY_STATE, self.status("P1B-5")["failures"])   # stage-exact
        self.assertEqual(self.status("P1B-8")["result"], "FAIL")                 # nothing beyond M-B6 exists
        for unit in I.AUTHORITY_UNITS + I.WITNESS_UNITS:                          # no witness / signer activation
            self.assertEqual(report[unit]["ActiveState"] if unit in report else
                             self.host.units[unit]["ActiveState"], "inactive")
        self.assertFalse(any(call[:2] == ["/usr/bin/systemctl", "start"] or "start" in call[1:2]
                             for call in self.host.calls if call and call[0].endswith("systemctl")))


# ------------------------------------------------------------------------ verifier and W6 classifier ---

class VerifierTests(Mb6Base):
    def test_w6_0_pre_mutation_and_the_w5_gaps(self):
        report = self.verify()
        self.assertEqual(report["phase"], V.W6_0, report["failures"])
        self.assertEqual(set(report["hostInputReasons"]), V.EXPECTED_HOST_INPUT_REASONS)
        self.assertEqual(report["evidence"], dict.fromkeys(V.EVIDENCE, False))
        self.assertEqual((report["registryEffective"], report["authorityActive"], report["authorityGranted"]),
                         (False, False, False))

    def test_w6_1_and_w6_2_directory_windows(self):
        self.exact_dir()
        self.assertEqual(self.verify()["phase"], V.W6_2)
        # W6-1: created by root (the owner seam) but not yet given to the signer (the signer seam differs)
        self.assertEqual(self.verify(signer=(UID + 1, GID + 1))["phase"], V.W6_1)
        os.chmod(self.state(), 0o750)
        self.assertEqual(self.verify(signer=(UID + 1, GID + 1))["phase"], V.UNCLASSIFIED)   # group bits: unsafe
        os.chmod(self.state(), 0o700)
        (self.state() / "authority_ledger.db").write_bytes(b"")
        os.chmod(self.state() / "authority_ledger.db", 0o600)
        self.assertEqual(self.verify(signer=(UID + 1, GID + 1))["phase"], V.UNCLASSIFIED)   # inexact dir + entries

    def test_w6_3_uncommitted_windows(self):
        snap = self.crash_snapshot()
        wal = (snap / "authority_ledger.db-wal").read_bytes()
        frames = V.parse_wal(wal)
        self.assertTrue(frames["headerValid"] and frames["committedFrames"] >= 1, frames)
        page = frames["pageSize"]
        last_commit_end = 32 + frames["committedFrames"] * (24 + page)
        corrupt = bytearray(wal)
        corrupt[last_commit_end - 1] ^= 0xFF                                      # torn last frame
        cases = {
            "empty-db": {"authority_ledger.db": b""},
            "empty-db-empty-wal": {"authority_ledger.db": b"", "authority_ledger.db-wal": b"",
                                   "authority_ledger.db-shm": b""},
            "truncated-before-commit": {"authority_ledger.db": b"",
                                        "authority_ledger.db-wal": wal[:last_commit_end - 1]},
            "checksum-broken": {"authority_ledger.db": b"", "authority_ledger.db-wal": bytes(corrupt)},
        }
        for name, files in cases.items():
            with self.subTest(name):
                self.place(files)
                report = self.verify()
                self.assertEqual(report["phase"], V.W6_3, report["failures"])
                self.assertEqual(report["evidence"], dict.fromkeys(V.EVIDENCE, False))
                shutil.rmtree(self.state())
        # a database put in WAL mode but never written (the signer half stopped before BEGIN)
        self.exact_dir()
        path = self.state() / "authority_ledger.db"
        os.close(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.close()
        self.assertEqual(self.verify()["phase"], V.W6_3)

    def test_w6_4_committed_in_the_wal_is_exact_and_matches_sqlite(self):
        snap = self.crash_snapshot()
        files = {p.name: p.read_bytes() for p in snap.iterdir()}
        self.assertIn("authority_ledger.db-wal", files)
        image, _ = V.committed_image(files["authority_ledger.db"], files["authority_ledger.db-wal"])
        examined = V.examine_image(image)
        # differential: SQLite's own recovery of an on-disk copy gives the same committed rows
        copy = self.scratch / "copy"
        copy.mkdir()
        for name in ("authority_ledger.db", "authority_ledger.db-wal"):
            (copy / name).write_bytes(files[name])
        conn = sqlite3.connect(copy / "authority_ledger.db")
        rows = [[s, o, bytes(p).decode(), ph, h, e] for s, o, p, ph, h, e in conn.execute(
            "SELECT seq, op, payload, prev_head, head, ledger_epoch FROM authority_journal_v1 ORDER BY seq")]
        conn.close()
        self.assertEqual(examined["journal"], rows)
        self.place({k: v for k, v in files.items() if k != "authority_ledger.db-shm"})
        report = self.verify()
        self.assertEqual(report["phase"], V.COMMITTED, report["failures"])
        self.assertFalse(report["ledgerClean"])
        self.assertEqual(report["sidecars"], ["authority_ledger.db-wal"])
        self.assertEqual(V.classify_sequence(host_phase=report["phase"], ledger_clean=False, attempt_consumed=True,
                                             transcript=V.CLI_SUCCESS_EXACT, post_verified=False), V.W6_4)

    @unittest.skipUnless(NON_ROOT, "the signer half refuses euid 0; needs a non-root test uid")
    def test_committed_clean_ledger_is_the_post_state(self):
        self.provision()
        snapshot = tree(self.root)
        report = self.verify()
        self.assertEqual(tree(self.root), snapshot)                                  # read-only
        self.assertEqual(report["phase"], V.COMMITTED, report["failures"])
        self.assertTrue(report["ledgerClean"])
        self.assertEqual(report["evidence"], dict.fromkeys(V.EVIDENCE, True))
        self.assertEqual(report["observedLedgerHead"], self.head)
        self.assertEqual(report["image"]["schemaFingerprint"], L.SCHEMA_FINGERPRINT)
        self.assertTrue(all(report["checks"].values()), report["checks"])
        # L: M-B6 success does not clear the W5 gaps
        self.assertEqual(set(report["hostInputReasons"]), V.EXPECTED_HOST_INPUT_REASONS)
        self.assertEqual((report["ownerRegisterCopyPresent"], report["genesisPinCopyPresent"],
                          report["witnessGenesisPresent"]), (False, False, False))
        self.assertEqual((report["registryEffective"], report["authorityActive"]), (False, False))
        # the committed image of a clean file is the file itself
        db = self.target(P.AUTHORITY_LEDGER).read_bytes()
        self.assertEqual(V.committed_image(db, None)[0], db)
        # sequence classes from the operator's records
        for transcript, post, expected in ((V.CLI_SUCCESS_EXACT, False, V.W6_5), (V.CLI_SUCCESS_EXACT, True, V.W6_6),
                                           (V.CLI_FAILED_UNCLASSIFIED, False, V.W6_4),
                                           (V.TRANSPORT_FAILED, False, V.W6_4), (V.CLI_REFUSED, False, V.UNCLASSIFIED)):
            self.assertEqual(V.classify_sequence(host_phase=V.COMMITTED, ledger_clean=True, attempt_consumed=True,
                                                 transcript=transcript, post_verified=post), expected)
        self.assertEqual(V.classify_sequence(host_phase=V.COMMITTED, ledger_clean=True, attempt_consumed=False,
                                             transcript=V.NOT_INVOKED, post_verified=False), V.UNCLASSIFIED)

    @unittest.skipUnless(NON_ROOT, "the signer half refuses euid 0; needs a non-root test uid")
    def test_owner_head_mismatch_and_unexpected_artifacts(self):
        self.provision()
        wrong = self.verify(head="1" * 64)
        self.assertEqual(wrong["phase"], V.UNCLASSIFIED)
        self.assertIn("OWNER_HEAD_NOT_THE_HEAD_OF_REGISTRY_V1", wrong["failures"])
        self.assertEqual(wrong["evidence"], dict.fromkeys(V.EVIDENCE, False))
        journal = self.state() / "authority_ledger.db-journal"
        journal.write_bytes(b"x")
        os.chmod(journal, 0o600)
        self.assertEqual(self.verify()["phase"], V.UNCLASSIFIED)                  # a -journal is never produced
        journal.unlink()
        os.chmod(self.target(P.AUTHORITY_LEDGER), 0o640)
        self.assertEqual(self.verify()["phase"], V.UNCLASSIFIED)
        os.chmod(self.target(P.AUTHORITY_LEDGER), 0o600)
        extra = self.state() / "other"
        extra.write_bytes(b"")
        self.assertEqual(self.verify()["phase"], V.UNCLASSIFIED)
        extra.unlink()
        self.assertEqual(self.verify()["phase"], V.COMMITTED)

    def test_wrong_signing_key_ids_and_wrong_registry(self):
        self.exact_dir()
        bad = dict(self.op, signingKeyIds=["test-only.someone-else.1"])
        L.DurableAuthorityLedgerV1.provision(self.target(P.AUTHORITY_LEDGER), environment="dev", genesis=bad,
                                             expected_uid=UID)
        report = self.verify()
        self.assertEqual(report["phase"], V.UNCLASSIFIED)
        self.assertFalse(report["checks"]["content.signingKeyIdsEqualKAct"])
        self.assertFalse(report["checks"]["content.headEqualsOwnerComputed"])
        foreign = dataclasses.replace(self.trust_pins, registry_sha256="2" * 64)
        self.assertIn("TRUST_REGISTRY_NOT_EXACT", self.verify(trust_pins=foreign)["failures"])

    def test_later_state_is_out_of_scope(self):
        for name, setup in (("witness state", lambda: self.target(P.WITNESS_STATE).mkdir()),
                            ("genesis pin copy", lambda: self.target(P.GENESIS_PIN_COPY).write_bytes(b"{}")),
                            ("signer running", lambda: self.target(P.AUTHORITY_CREDENTIALS_RUNTIME).mkdir(parents=True))):
            with self.subTest(name):
                setup()
                self.assertEqual(self.verify()["phase"], V.LATER_STATE)
                path = {"witness state": P.WITNESS_STATE, "genesis pin copy": P.GENESIS_PIN_COPY,
                        "signer running": P.AUTHORITY_CREDENTIALS_RUNTIME}[name]
                p = self.target(path)
                p.rmdir() if p.is_dir() else p.unlink()

    def test_verifier_is_read_only_by_construction(self):
        source = (TOOLS / "mb6_ledger_verifier.py").read_text(encoding="utf-8").split('"""', 2)[2]
        for forbidden in ("os.unlink", "os.remove", "os.rename", "os.rmdir", "os.chmod", "os.chown", "os.mkdir",
                          "O_WRONLY", "O_RDWR", "O_CREAT", "subprocess", "socket", "shutil", "tempfile",
                          ".write_bytes", ".write_text", "systemctl", "mode=rw", "credstore", "witness.cred",
                          "fsync"):
            self.assertNotIn(forbidden, source, forbidden)
        self.assertEqual(V.ACCEPTED_PINS.schema_fingerprint, L.SCHEMA_FINGERPRINT)
        self.assertEqual(V.ACCEPTED_PINS.schema_fingerprint, REAL_SCHEMA_FINGERPRINT)
        with self.assertRaises(V.Refused):
            self.verify(head="xyz")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(V.main(["observe", self.head]), 2)                   # not DEV (or not root)
            self.assertEqual(V.main(["observe"]), 2)                              # USAGE
            self.assertEqual(V.main(["expect", "W6_9", self.head]), 2)
        self.assertIn("REFUSED", err.getvalue())


# --------------------------------------------------------------------------------------- recovery ---

class RecoveryTests(Mb6Base):
    def host_(self, **kw) -> "R.Host":
        value = dict(root=self.root, owner_uid=UID, owner_gid=GID, signer=(UID, GID), euid=lambda: 0,
                     hostname=lambda: "lilith-dev-01", trust_pins=self.trust_pins, pins=self.pins)
        value.update(kw)
        return R.Host(**value)

    def outside(self) -> dict:
        return {k: v for k, v in tree(self.root).items() if not k.startswith("var/lib/lilith-authority-dev")}

    def test_w6_1_remove_empty_directory(self):
        self.exact_dir()
        host = self.host_(signer=(UID + 1, GID + 1))                              # W6-1 under the signer seam
        before = self.outside()
        plan = R.plan(host, self.head)
        self.assertEqual((plan["phase"], plan["action"], plan["mutating"]), (V.W6_1, R.REMOVE_DIRECTORY, True))
        with self.assertRaises(R.Refused) as caught:
            R.recover(host, self.head, "0" * 64)
        self.assertEqual(caught.exception.reason, "PLAN_CHANGED")
        result = R.recover(host, self.head, plan["planDigest"])
        self.assertEqual((result["phaseAfter"], result["result"]), (V.W6_0, "MB6_RECOVERY_DONE"))
        self.assertFalse(self.state().exists())
        self.assertEqual(self.outside(), before)

    def test_w6_3_remove_uncommitted_files_and_plan_binding(self):
        self.place({"authority_ledger.db": b"", "authority_ledger.db-wal": b"", "authority_ledger.db-shm": b""})
        host = self.host_()
        before = self.outside()
        plan = R.plan(host, self.head)
        self.assertEqual((plan["phase"], plan["action"]), (V.W6_3, R.REMOVE_FILES))
        self.assertEqual([t["name"] for t in plan["targets"]],
                         ["authority_ledger.db-wal", "authority_ledger.db-shm", "authority_ledger.db"])
        (self.state() / "authority_ledger.db-wal").write_bytes(b"\x00")           # changed after review
        with self.assertRaises(R.Refused) as caught:
            R.recover(host, self.head, plan["planDigest"])
        self.assertEqual(caught.exception.reason, "PLAN_CHANGED")
        plan = R.plan(host, self.head)
        result = R.recover(host, self.head, plan["planDigest"])
        self.assertEqual((result["phaseAfter"], result["result"]), (V.W6_2, "MB6_RECOVERY_DONE"))
        self.assertEqual(os.listdir(self.state()), [])
        self.assertEqual(self.outside(), before)

    @unittest.skipUnless(NON_ROOT, "the signer half refuses euid 0; needs a non-root test uid")
    def test_w6_4_clean_committed_ledger_is_adopted_never_deleted(self):
        self.provision()
        before = tree(self.root)
        plan = R.plan(self.host_(), self.head)
        self.assertEqual((plan["phase"], plan["action"]), (V.COMMITTED, R.ADOPT))
        result = R.recover(self.host_(), self.head, plan["planDigest"])
        self.assertEqual((result["phaseAfter"], result["result"]), (V.COMMITTED, "MB6_RECOVERY_DONE"))
        self.assertEqual(tree(self.root), before)                                   # durability only: no byte changed
        source = (TOOLS / "mb6_ledger_recovery.py").read_text(encoding="utf-8").split('"""', 2)[2]
        self.assertEqual(source.count("os.unlink("), 1)
        self.assertEqual(source.count("os.rmdir("), 1)
        for forbidden in ("O_WRONLY", "O_RDWR", "O_CREAT", "write_bytes", "shutil", "subprocess", "systemctl",
                          "provision", "chmod", "chown", "rename", "credstore", "witness.cred"):
            self.assertNotIn(forbidden, source, forbidden)

    def test_w6_4_with_wal_needs_owner_adjudication(self):
        snap = self.crash_snapshot()
        self.place({p.name: p.read_bytes() for p in snap.iterdir() if not p.name.endswith("-shm")})
        plan = R.plan(self.host_(), self.head)
        self.assertEqual((plan["phase"], plan["action"], plan["mutating"]), (V.COMMITTED, R.ADJUDICATE, False))
        with self.assertRaises(R.Refused) as caught:
            R.recover(self.host_(), self.head, plan["planDigest"])
        self.assertEqual(caught.exception.reason, R.ADJUDICATE)

    def test_refusals_outside_the_pre_mb9b_bound(self):
        self.exact_dir()
        self.target(P.WITNESS_STATE).mkdir()
        with self.assertRaises(R.Refused) as caught:
            R.plan(self.host_(), self.head)
        self.assertEqual(caught.exception.reason, "NOT_RECOVERABLE:" + V.LATER_STATE)
        self.target(P.WITNESS_STATE).rmdir()
        self.target(P.AUTHORIZATION_REGISTER_COPY).write_bytes(b"{}")
        with self.assertRaises(R.Refused) as caught:
            R.plan(self.host_(), self.head)
        self.assertEqual(caught.exception.reason, "NOT_RECOVERABLE:" + V.LATER_STATE)
        self.target(P.AUTHORIZATION_REGISTER_COPY).unlink()
        for bad, reason in ((self.host_(euid=lambda: 1000), "NOT_ROOT"),
                            (self.host_(hostname=lambda: "lilith-prod-01"), "NOT_DEV_HOST")):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(R.main(["plan", self.head], bad), 2)
            self.assertIn(reason, err.getvalue())
        with self.assertRaises(R.Refused) as caught:
            R.recover(self.host_(), self.head, R.plan(self.host_(), self.head)["planDigest"])
        self.assertEqual(caught.exception.reason, R.NOTHING)                          # W6-2: nothing to recover
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(R.main(["recover", self.head, "not-a-digest"], self.host_()), 2)


# ------------------------------------------------------------------------- owner-computed expected head ---

class ExpectedHeadTests(Mb6Base):
    def test_derive_from_the_owner_files(self):
        result = E.derive(self.files["authority-registry.v1.json"], self.files["registry-root.json"],
                          self.expected_pins)
        self.assertEqual((result["derivation"], result["ledgerSequence"]), ("OWNER_COMPUTED_FROM_REGISTRY_V1", 1))
        self.assertEqual(result["ledgerHead"], self.head)
        self.assertEqual(result["ledgerHead"], result["independentLedgerHead"])
        self.assertEqual(result["ledgerHead"], result["pinDerivedLedgerHead"])
        self.assertEqual(result["ledgerHead"], J.initial_position(self.registry())[1])
        self.assertEqual(result["genesisOp"], J.genesis_op(self.registry()))
        self.assertEqual((result["accepted"], result["pinned"], result["authorityGranted"]), (False, False, False))
        self.assertEqual(result, E.derive(self.files["authority-registry.v1.json"], self.files["registry-root.json"],
                                          self.expected_pins))                       # deterministic

    def test_refusals(self):
        f, p = self.files, self.expected_pins
        cases = (
            ((self.other_files["authority-registry.v1.json"], f["registry-root.json"], p),
             "REGISTRY_NOT_THE_ACCEPTED_INSTALLABLE"),
            ((f["authority-registry.v1.json"] + b"\n", f["registry-root.json"],
              dataclasses.replace(p, registry_sha256=sha(f["authority-registry.v1.json"] + b"\n"))),
             "INPUT_NOT_CANONICAL"),
            ((f["authority-registry.v1.json"], self.other_files["registry-root.json"],
              dataclasses.replace(p, root_anchor_sha256=sha(self.other_files["registry-root.json"]))),
             "REGISTRY_NOT_VERIFIED"),                                               # registry vs a foreign root
            ((f["authority-registry.v1.json"], f["registry-root.json"],
              dataclasses.replace(p, kact_key_id="test-only.other.1")), "REGISTRY_KEY_NOT_KACT"),
        )
        for args, reason in cases:
            with self.subTest(reason):
                with self.assertRaises(E.OwnerToolError) as caught:
                    E.derive(*args)
                self.assertEqual(caught.exception.reason, reason)

    def test_real_pin_derived_value(self):
        result = E.from_pins()
        self.assertEqual(result["derivation"], "PIN_DERIVED_CROSS_CHECK")
        self.assertEqual(result["ledgerHead"], REAL_PIN_DERIVED_HEAD)
        self.assertEqual(result["genesisOpJcsSha256"], REAL_GENESIS_OP_JCS_SHA256)
        self.assertEqual(V.ledger_head(V.pinned_genesis_op()), REAL_PIN_DERIVED_HEAD)
        self.assertEqual(V.pinned_genesis_op(), E.pin_derived_op())
        self.assertFalse(result["ownerComputed"] or result["accepted"] or result["pinned"])
        source = (TOOLS / "mb6_expected_ledger_head.py").read_text(encoding="utf-8").split('"""', 2)[2]
        for forbidden in ("subprocess", "socket", "write_bytes", "write_text", "open(", "gcloud", "ssh"):
            self.assertNotIn(forbidden, source, forbidden)


# ---------------------------------------------------------------------------------------- operator ---

class FakeRun:
    """Scripted runner: git from the working tree; ssh by command class; every argv recorded."""

    def __init__(self, provision=None, pre_phase=V.W6_0, verifier_report=None):
        self.calls: list[list[str]] = []
        self.provision = provision or (lambda: subprocess.CompletedProcess([], 0, b"", b""))
        self.pre_phase = pre_phase
        self.verifier_report = verifier_report

    def __call__(self, argv):
        argv = list(argv)
        self.calls.append(argv)
        if argv[0] == "git":
            args = argv[3:]
            if args[:1] == ["rev-parse"]:
                return subprocess.CompletedProcess(argv, 0, b"a" * 40 + b"\n", b"")
            if args[:1] == ["status"]:
                return subprocess.CompletedProcess(argv, 0, b"", b"")
            if args[:1] == ["show"]:
                return subprocess.CompletedProcess(argv, 0, (ROOT / args[1].split(":", 1)[1]).read_bytes(), b"")
        command = argv[-1]
        if command.endswith(O.PROVISION):
            return self.provision()
        if "readlink /opt/lilith-authority-dev/current" in command:
            probe = {"release": "/opt/lilith-authority-dev/current", "deserialize": True, "ledgerCli": O.LEDGER_CLI_SHA256,
                     "modules": {path: [path, digest] for path, digest
                                 in {**O.RELEASE_MODULES, **O.PROVISION_MODULES}.items()}}
            return subprocess.CompletedProcess(argv, 0, (f"releases/{O.RELEASE_SHA}\nRELEASE_PYTHON=executable\n"
                                                         + json.dumps(probe) + "\n").encode(), b"")
        if "mb6_ledger_verifier" in command:
            report = self.verifier_report or {"phase": self.pre_phase}
            return subprocess.CompletedProcess(argv, 0, json.dumps(report).encode(), b"")
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    def provisions(self) -> int:
        return sum(1 for call in self.calls if call[-1].endswith(O.PROVISION))


class OperatorTests(Redacted, unittest.TestCase):
    head = REAL_PIN_DERIVED_HEAD

    def setUp(self):
        self.enterContext(RP.current_tree(O))
        self.work = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (self.work / "expected").mkdir()
        (self.work / "expected" / "expected-ledger.json").write_text(json.dumps({
            "derivation": "OWNER_COMPUTED_FROM_REGISTRY_V1", "ledgerSequence": 1, "ledgerHead": self.head,
            "independentLedgerHead": self.head, "pinDerivedLedgerHead": self.head}), encoding="utf-8")

    def go(self, pre=V.W6_0, drop=None) -> Path:
        lines = [line.format(control="a" * 40, operator=sha((TOOLS / "mb6_operator.py").read_bytes()), head=self.head,
                             pre=pre) for line in O.MB6_GO_LINES]
        if drop is not None:
            del lines[drop]
        path = self.work / "go.txt"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_tool_pins_are_the_tree(self):
        for path, pin in O.TOOL_PINS.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), RP.tree_pin(path, pin), path)
        self.assertEqual(O.Operator(gcloud=("gcloud",), run=FakeRun()).pins(ROOT)["result"], "MB6_TOOL_PINS_EXACT")

    def test_one_attempt_exactly_one_provision(self):
        stdout = V.expected_cli_stdout(self.head, "CREATED")
        run = FakeRun(provision=lambda: subprocess.CompletedProcess([], 0, stdout, b""))
        op = O.Operator(gcloud=("gcloud",), run=run)
        result = op.mb6(ROOT, self.work, self.go())
        self.assertEqual((result["result"], result["transcript"], result["attempt"]),
                         ("MB6_INVOKED_ONCE", V.CLI_SUCCESS_EXACT, "CONSUMED"))
        self.assertEqual(run.provisions(), 1)
        provision = [c for c in run.calls if c[-1].endswith(O.PROVISION)][0]
        self.assertEqual(provision[-1], '--command=test "$(hostname)" = lilith-dev-01 || exit 97; '
                                        'sudo -n /usr/local/sbin/lilith-authority-ledger-dev provision 1')
        marker = json.loads((self.work / "attempts" / "mb6.json").read_text())
        self.assertEqual(marker["invocationsPermitted"], 1)
        with self.assertRaises(O.Stop) as caught:                                     # never a second attempt
            op.mb6(ROOT, self.work, self.go())
        self.assertEqual(caught.exception.code, "ATTEMPT_ALREADY_CONSUMED:mb6")
        self.assertEqual(run.provisions(), 1)
        consumed, transcript, post = op._records(self.work)
        self.assertEqual((consumed, transcript, post), (True, V.CLI_SUCCESS_EXACT, False))

    def test_post_then_classify_w6_5_to_w6_6(self):
        stdout = V.expected_cli_stdout(self.head, "CREATED")
        run = FakeRun(provision=lambda: subprocess.CompletedProcess([], 0, stdout, b""))
        op = O.Operator(gcloud=("gcloud",), run=run)
        op.mb6(ROOT, self.work, self.go())
        run.verifier_report = {"phase": V.COMMITTED, "ledgerClean": True, "evidence": dict.fromkeys(V.EVIDENCE, True),
                               "registryEffective": False, "authorityGranted": False}
        result = op.post(ROOT, self.work)
        self.assertEqual((result["result"], result["sequencePhase"]), ("MB6_POST_VERIFIED", V.W6_6))
        self.assertIn("M-B7 is not authorized", result["next"])
        record = json.loads((self.work / "post" / "POST_VERIFIED.json").read_text())
        self.assertEqual((record["phase"], record["ownerAccepted"]), (V.W6_6, False))
        with self.assertRaises(O.Stop) as caught:
            op.post(ROOT, self.work)
        self.assertEqual(caught.exception.code, "POST_ALREADY_VERIFIED")
        self.assertEqual(op.classify(ROOT, self.work, self.work / "classify")["sequencePhase"], V.W6_6)
        self.assertEqual(run.provisions(), 1)                                        # POST and classify never mutate

    def test_post_after_an_incomplete_cli_is_w6_4(self):
        run = FakeRun(provision=lambda: subprocess.CompletedProcess([], 255, b"", b"ssh: lost"))
        op = O.Operator(gcloud=("gcloud",), run=run)
        op.mb6(ROOT, self.work, self.go())
        run.verifier_report = {"phase": V.COMMITTED, "ledgerClean": True, "evidence": dict.fromkeys(V.EVIDENCE, True),
                               "registryEffective": False, "authorityGranted": False}
        result = op.post(ROOT, self.work)
        self.assertEqual((result["result"], result["sequencePhase"]), ("MB6_POST_NOT_VERIFIED", V.W6_4))
        self.assertFalse((self.work / "post" / "POST_VERIFIED.json").exists())
        self.assertEqual(run.provisions(), 1)

    def test_failures_consume_the_go_and_never_retry(self):
        for name, provision, expected in (
                ("refused", lambda: subprocess.CompletedProcess(
                    [], 2, b"", b"lilith-authority-ledger-dev: REFUSED LEDGER_TOOL_ALREADY_PROVISIONED\n"),
                 V.CLI_REFUSED),
                ("traceback", lambda: subprocess.CompletedProcess([], 1, b"", b"Traceback ...\n"),
                 V.CLI_FAILED_UNCLASSIFIED),
                ("ssh", lambda: subprocess.CompletedProcess([], 255, b"", b"ssh: connect"), V.TRANSPORT_FAILED),
                ("timeout", lambda: (_ for _ in ()).throw(subprocess.TimeoutExpired(["gcloud"], 900)),
                 V.TRANSPORT_FAILED)):
            with self.subTest(name):
                shutil.rmtree(self.work / "attempts", ignore_errors=True)
                run = FakeRun(provision=provision)
                result = O.Operator(gcloud=("gcloud",), run=run).mb6(ROOT, self.work, self.go())
                self.assertEqual((result["result"], result["transcript"]), ("MB6_STOP", expected))
                self.assertEqual(run.provisions(), 1)
                self.assertTrue((self.work / "attempts" / "mb6.json").is_file())

    def test_refusals_before_the_marker(self):
        for name, kwargs, go, code in (
                ("missing go line", {}, lambda: self.go(drop=8), "GO_LINE_MISSING"),
                ("pre-state differs", {"pre_phase": V.W6_2}, lambda: self.go(), "PRE_STATE_NOT_AS_GO"),
                ("no pre-state", {}, lambda: self.go(pre="W6_5_CLI_SUCCEEDED_POST_PENDING"), "GO_PRE_STATE_MISSING")):
            with self.subTest(name):
                run = FakeRun(**kwargs)
                with self.assertRaises(O.Stop) as caught:
                    O.Operator(gcloud=("gcloud",), run=run).mb6(ROOT, self.work, go())
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(run.provisions(), 0)
                self.assertFalse((self.work / "attempts" / "mb6.json").exists())
        with mock.patch.dict(O.TOOL_PINS, {O.VERIFIER: "0" * 64}):
            run = FakeRun()
            with self.assertRaises(O.Stop) as caught:
                O.Operator(gcloud=("gcloud",), run=run).mb6(ROOT, self.work, self.go())
            self.assertTrue(caught.exception.code.startswith("TOOL_PIN_MISMATCH"))
            self.assertEqual(run.provisions(), 0)

    def test_the_go_template_binds_the_accepted_continuity_and_boundaries(self):
        text = " ".join(O.MB6_GO_LINES)
        for needed in ("MB6_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_ONE_GO", "exactly one invocation",
                       "KNOWN_EMPTY", "AUTHORIZATION_REGISTER_COPY_MISSING and GENESIS_PIN_COPY_MISSING remain",
                       "does not authorize M-B7", "after the attempt marker consumes this go",
                       "There is no automatic retry", "The deploy freeze holds", "{head}", "{pre}", "{control}"):
            self.assertIn(needed, text)
        source = (TOOLS / "mb6_operator.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("self.ssh(PROVISION)"), 1)                 # one invocation path only
        import re
        self.assertEqual(len(re.findall(r"\bPROVISION\b", source)), 2)            # the definition and that one call
        # Module-pin lines name release files (e.g. `pr1_bootstrap.py`); they are hashes, never commands.
        code = re.sub(r'^ {4}"lilith_[a-z_]+/[a-z0-9_]+\.py": "[0-9a-f]{64}",\n', "", source, flags=re.MULTILINE)
        self.assertEqual(source.count("pr1_bootstrap"), 1)
        for forbidden in ("provision-as-signer", "genesis-candidate", "install-owner-inputs", "bootstrap",
                          "create-initial-held", "systemctl start", "systemctl enable", "daemon-reload"):
            self.assertNotIn(forbidden, code, forbidden)

    @unittest.skipUnless(POSIX, "the bundle runs only on DEV (Linux); the pinned W5 verifier needs os.geteuid at import")
    def test_bundle_loader_is_hash_gated_and_runs_in_memory(self):
        op = O.Operator(gcloud=("gcloud",), run=FakeRun())
        command = op.bundled(ROOT, O.RECOVERY_BUNDLE, "USAGE-PROBE")
        blob = command.split("B=", 1)[1].split(";", 1)[0]
        boot_args = command.split("-c ", 1)[1]
        loader = boot_args.split('"')[1]
        pins, entry = boot_args.split('" ', 1)[1].split()[:2]
        data = __import__("base64").b64decode(blob)
        with tempfile.TemporaryDirectory() as cwd:
            ok = subprocess.run([sys.executable, "-I", "-B", "-c", loader, pins, entry, "nonsense"], input=data,
                                capture_output=True, cwd=cwd, timeout=120)
            self.assertEqual(ok.returncode, 2, ok.stderr)                          # loaded; main() refused USAGE
            self.assertIn(b"mb6_ledger_recovery: REFUSED USAGE", ok.stderr)
            self.assertEqual(os.listdir(cwd), [])                                  # wrote nothing
            bad = pins.replace(O.TOOL_PINS[O.RECOVERY], "0" * 64)
            refused = subprocess.run([sys.executable, "-I", "-B", "-c", loader, bad, entry, "nonsense"], input=data,
                                     capture_output=True, cwd=cwd, timeout=120)
            self.assertEqual(refused.returncode, 96)
        names = json.loads(gzip.decompress(data))
        self.assertEqual(list(names), ["mb4_mb5_trust_install_verifier", "mb6_ledger_verifier", "mb6_ledger_recovery"])

    def test_transcript_classes(self):
        good = V.expected_cli_stdout(self.head, "CREATED")
        cases = ((0, good, b"", V.CLI_SUCCESS_EXACT), (0, good.replace(b"\n", b"\r\n"), b"", V.CLI_SUCCESS_EXACT),
                 (0, good, b"warning\n", V.CLI_FAILED_UNCLASSIFIED),
                 (0, V.expected_cli_stdout(self.head, "ADOPTED_NO_MUTATION"), b"", V.CLI_FAILED_UNCLASSIFIED),
                 (0, good + good, b"", V.CLI_FAILED_UNCLASSIFIED), (97, b"", b"", V.GUARD_STOPPED),
                 (96, b"", b"", V.GUARD_STOPPED), (None, b"", b"", V.TRANSPORT_FAILED),
                 (2, b"", b"lilith-authority-ledger-dev: REFUSED NOT_ROOT\n", V.CLI_REFUSED))
        for code, out, err, expected in cases:
            self.assertEqual(V.classify_transcript(code, out, err, expected_head=self.head,
                                                   state_directory="CREATED")[0], expected, (code, out[:20], err))


if __name__ == "__main__":
    unittest.main()
