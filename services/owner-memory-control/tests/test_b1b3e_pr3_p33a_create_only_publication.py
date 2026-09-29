"""15B2b-B1b-3e PR-3 P3-3A: Android-safe create-only publication (TEST-ONLY, offline).

Record: docs/architecture/slice-15b2b-b1b3e-pr3-android-replica-publication.md.

Every directory is temporary. No real replica, phone, DEV host, or cloud
resource is touched.
"""

from __future__ import annotations

import ast
import copy
import errno
import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import synthetic_authority as SA  # noqa: F401  (sets sys.path)
import synthetic_b1b3e as F
import test_b1b3e_pr3_p32_owner_freshness_tool as P32
from lilith_owner_memory import create_only_publish as COP
from lilith_owner_memory import owner_acceptance as OA
from lilith_owner_memory import owner_freshness as OF
from lilith_owner_memory import owner_freshness_tool as T

ROOT = SA.ROOT
PUBLISHER = ROOT / "services/owner-memory-control/lilith_owner_memory/create_only_publish.py"
PROBE_SCRIPT = ROOT / "services/owner-memory-control/tools/android_p3_probe.py"
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-pr3-android-replica-publication.md"
POSIX = os.name == "posix"
DATA = b'{"n":1,"probe":"x"}'


def load_probe_script():
    spec = importlib.util.spec_from_file_location("android_p3_probe", PROBE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Temp:
    def __init__(self, test):
        self.dir = Path(tempfile.mkdtemp(prefix="p33a-"))
        test.addCleanup(shutil.rmtree, self.dir, True)

    def sub(self, name: str) -> Path:
        path = self.dir / name
        path.mkdir()
        return path


@unittest.skipUnless(POSIX, "create-only backends are POSIX primitives")
class BackendTests(unittest.TestCase):
    def setUp(self):
        self.t = Temp(self)

    def assert_published(self, directory: Path, name: str, data: bytes = DATA):
        self.assertEqual((directory / name).read_bytes(), data)
        self.assertEqual([n for n in os.listdir(directory) if n.startswith(COP.PENDING_PREFIX)], [])

    def test_01_hardlink_backend_success(self):
        d = self.t.sub("d")
        self.assertEqual(COP.publish(d, "000001-a.json", DATA, backend=COP.HARDLINK_PUBLISH_V1), "PERFORMED")
        self.assert_published(d, "000001-a.json")
        self.assertEqual(os.stat(d / "000001-a.json").st_nlink, 1)             # pending unlinked

    def test_02_hardlink_unavailable(self):
        d = self.t.sub("d")
        with mock.patch.object(COP.os, "link", side_effect=PermissionError(errno.EACCES, "Permission denied")):
            with self.assertRaises(PermissionError):
                COP.publish(d, "000001-a.json", DATA, backend=COP.HARDLINK_PUBLISH_V1)
        self.assertEqual(os.listdir(d), [])                                      # nothing half-published

    def test_03_rename_noreplace_success(self):
        d = self.t.sub("d")
        COP.publish(d, "000001-a.json", DATA, backend=COP.RENAME_NOREPLACE_V1)
        self.assert_published(d, "000001-a.json")
        self.assertEqual(os.listdir(d), ["000001-a.json"])                     # exactly one name, never two

    def test_04_rename_noreplace_refuses_existing_final(self):
        d = self.t.sub("d")
        (d / "000001-a.json").write_bytes(b"ACCEPTED")
        with self.assertRaises(COP.PublishRefused) as caught:
            COP.publish(d, "000001-a.json", DATA, backend=COP.RENAME_NOREPLACE_V1)
        self.assertEqual(caught.exception.reason, "FINAL_EXISTS")
        pending = d / ".pending-race.tmp"                                      # primitive itself, no pre-check
        pending.write_bytes(DATA)
        with self.assertRaises(FileExistsError):
            COP.rename_noreplace(pending, d / "000001-a.json")
        self.assertEqual((d / "000001-a.json").read_bytes(), b"ACCEPTED")
        self.assertTrue(pending.exists())

    def test_05_direct_o_excl_success(self):
        d = self.t.sub("d")
        COP.publish(d, "000001-a.json", DATA, backend=COP.DIRECT_O_EXCL_V1)
        self.assertEqual(os.listdir(d), ["000001-a.json"])
        self.assert_published(d, "000001-a.json")

    def test_06_direct_o_excl_refuses_existing_final(self):
        d = self.t.sub("d")
        (d / "000001-a.json").write_bytes(b"ACCEPTED")
        with self.assertRaises(COP.PublishRefused):
            COP.publish(d, "000001-a.json", DATA, backend=COP.DIRECT_O_EXCL_V1)
        with self.assertRaises(FileExistsError):
            COP.write_new_file(d / "000001-a.json", DATA)
        self.assertEqual((d / "000001-a.json").read_bytes(), b"ACCEPTED")

    def test_09_existing_accepted_final_never_overwritten_by_any_backend(self):
        d = self.t.sub("d")
        COP.publish(d, "000001-a.json", DATA, backend=COP.RENAME_NOREPLACE_V1)
        for backend in COP.BACKENDS:
            with self.assertRaises(COP.PublishRefused, msg=backend):
                COP.publish(d, "000001-a.json", b"OTHER", backend=backend)
        self.assertEqual((d / "000001-a.json").read_bytes(), DATA)
        self.assertEqual(os.listdir(d), ["000001-a.json"])

    def test_rename_unavailable_never_falls_back(self):
        d = self.t.sub("d")
        with mock.patch.object(COP, "rename_noreplace", side_effect=COP.RenameNoReplaceUnavailable(errno.ENOSYS, "x")):
            with self.assertRaises(COP.RenameNoReplaceUnavailable):
                COP.publish(d, "000001-a.json", DATA, backend=COP.RENAME_NOREPLACE_V1)
        self.assertEqual(os.listdir(d), [])
        tree = ast.parse(PUBLISHER.read_text(encoding="utf-8"))
        calls = {f"{node.func.value.id}.{node.func.attr}" for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                 and isinstance(node.func.value, ast.Name)}
        self.assertFalse(calls & {"os.rename", "os.replace", "shutil.move"}, calls)   # plain rename is refused
        with self.assertRaises(COP.PublishRefused):
            COP.publish(d, "x.json", DATA, backend="PLAIN_RENAME")

    def test_10_backend_choice_is_deterministic(self):
        cases = {(True, True): COP.RENAME_NOREPLACE_V1, (True, False): COP.RENAME_NOREPLACE_V1,
                 (False, True): COP.HARDLINK_PUBLISH_V1, (False, False): COP.NONE}
        for (rename, link), expected in cases.items():
            for direct in (True, False):
                capabilities = {COP.RENAME_NOREPLACE_V1: rename, COP.HARDLINK_PUBLISH_V1: link,
                                COP.DIRECT_O_EXCL_V1: direct}
                self.assertEqual(COP.select_backend(capabilities), expected)
        self.assertNotIn(COP.DIRECT_O_EXCL_V1, COP.ADMITTED_PREFERENCE)
        first = T.probe_storage(self.t.sub("p1"))["admittedBackend"]
        self.assertEqual(first, T.probe_storage(self.t.sub("p2"))["admittedBackend"])

    def test_15_unsupported_filesystem_admits_none(self):
        parent = self.t.sub("store")
        with mock.patch.object(T.os, "link", side_effect=PermissionError(errno.EACCES, "Permission denied")), \
                mock.patch.object(COP, "rename_noreplace",
                                  side_effect=COP.RenameNoReplaceUnavailable(errno.EPERM, "blocked")):
            probe = T.probe_storage(parent)
            self.assertEqual((probe["result"], probe["admittedBackend"]), (T.P3_STORAGE_INCAPABLE, COP.NONE))
            self.assertEqual(probe["backends"], {"renameNoReplace": T.UNAVAILABLE, "hardlinkPublish": T.FAIL,
                                                 "directExclusiveFinal": T.PASS})
            with self.assertRaises(T.ToolRefusal) as caught:
                T.init_real_replica(parent / "replica", replica_id="owner-offline-dev-synthetic-01",
                                    environment="dev", authority_profile="DEV_SYNTHETIC")
            self.assertEqual(caught.exception.reason, T.P3_STORAGE_INCAPABLE)
        self.assertEqual(os.listdir(parent), [])


@unittest.skipUnless(POSIX, "create-only backends are POSIX primitives")
class ReplicaTests(unittest.TestCase):
    def setUp(self):
        self.w = P32.Workstation(self)
        self.s = F.Scenario()
        self.pin = self.w.pin(P32._genesis_digest(self.s.writer.chain))
        self.chain = self.w.chain(self.s.writer.chain)
        _, self.proposed, self.candidate = self.w.propose("genesis", self.chain, self.pin)
        self.record = json.loads(self.candidate.read_text(encoding="utf-8"))["record"]
        self.name = f"000001-{self.proposed['recordDigest']}.json"

    def refused(self, replica: Path) -> str:
        with self.assertRaises(T.ToolRefusal) as caught:
            T.load_replica(replica)
        return caught.exception.reason

    def test_tool_append_reports_backend_and_keeps_record_bytes(self):
        code, result = self.w.append(self.w.a, self.w.b, self.candidate, self.chain, self.pin,
                                     self.proposed["recordDigest"])
        self.assertEqual((code, result["publicationBackend"]), (0, COP.RENAME_NOREPLACE_V1))
        self.assertEqual((self.w.a / T.RECORDS / self.name).read_bytes(), OF.record_bytes(self.record))

    def test_07_interrupted_zero_byte_final_refused(self):
        (self.w.a / T.RECORDS / self.name).write_bytes(b"")
        self.assertEqual(self.refused(self.w.a), "RECORD_ZERO_BYTES")
        self.assertTrue((self.w.a / T.RECORDS / self.name).exists())          # never deleted
        code, result = self.w.cli("classify", *self.w.replicas(), *self.w.world(self.chain))
        self.assertEqual(result["freshness"], OF.FRESHNESS_UNKNOWN)

    def test_08_partial_final_refused(self):
        full = OF.record_bytes(self.record)
        for cut in (1, len(full) // 2, len(full) - 1):
            (self.w.a / T.RECORDS / self.name).write_bytes(full[:cut])
            self.assertEqual(self.refused(self.w.a), "RECORD_MALFORMED", cut)
        # a complete-looking file under the wrong digest name is never accepted either
        wrong = f"000001-{F.digest('wrong')}.json"
        os.unlink(self.w.a / T.RECORDS / self.name)
        (self.w.a / T.RECORDS / wrong).write_bytes(full)
        self.assertEqual(self.refused(self.w.a), "RECORD_NAME_MISMATCH")

    def test_11_mixed_backend_replicas_compare_identical(self):
        data = OF.record_bytes(self.record)
        COP.publish(self.w.a / T.RECORDS, self.name, data, backend=COP.HARDLINK_PUBLISH_V1)
        COP.publish(self.w.b / T.RECORDS, self.name, data, backend=COP.RENAME_NOREPLACE_V1)
        code, compared = self.w.cli("compare-replicas", *self.w.replicas())
        self.assertEqual((code, compared["status"]), (0, OF.REGISTER_VERIFIED))
        self.assertEqual((self.w.a / T.RECORDS / self.name).read_bytes(), (self.w.b / T.RECORDS / self.name).read_bytes())
        code, result = self.w.cli("classify", *self.w.replicas(), *self.w.world(self.chain))
        self.assertEqual(result["freshness"], OF.CURRENT)

    def test_12_backend_metadata_never_enters_digests_or_manifests(self):
        before = OF.record_digest(self.record)
        for backend in (COP.HARDLINK_PUBLISH_V1, COP.RENAME_NOREPLACE_V1, COP.DIRECT_O_EXCL_V1):
            directory = self.w.dir / f"pub-{backend}"
            directory.mkdir()
            COP.publish(directory, self.name, OF.record_bytes(self.record), backend=backend)
            self.assertEqual(OF.record_digest(json.loads((directory / self.name).read_bytes())), before)
        for fields in (OF.RECORD_FIELDS, T.REPLICA_FIELDS, OA.ENVELOPE_FIELDS, OA.PACKAGE_FIELDS):
            self.assertFalse({f for f in fields if "backend" in f.lower() or "publish" in f.lower()}, fields)
        manifest = json.loads((self.w.a / T.MANIFEST).read_bytes())
        self.assertEqual(set(manifest), T.REPLICA_FIELDS)

    def test_13_symlink_attack_refused(self):
        elsewhere = self.w.dir / "elsewhere.json"
        elsewhere.write_bytes(OF.record_bytes(self.record))
        os.symlink(elsewhere, self.w.a / T.RECORDS / self.name)
        self.assertEqual(self.refused(self.w.a), "RECORD_MALFORMED")           # NOT_A_REGULAR_FILE
        for backend in COP.BACKENDS:                                           # a symlink occupies the final name
            with self.assertRaises(COP.PublishRefused):
                COP.publish(self.w.a / T.RECORDS, self.name, b"x", backend=backend)
        dangling = self.w.b / T.RECORDS / self.name
        os.symlink(self.w.dir / "missing.json", dangling)
        with self.assertRaises(COP.PublishRefused):
            COP.publish(self.w.b / T.RECORDS, self.name, b"x", backend=COP.DIRECT_O_EXCL_V1)
        self.assertFalse((self.w.dir / "missing.json").exists())                 # never followed

    def test_14_unexpected_temp_artifact_refused(self):
        for name, reason in ((f"{COP.PENDING_PREFIX}{self.name}.tmp", "REPLICA_PENDING_WRITE"),
                             (f"{self.name}.tmp", "REPLICA_UNEXPECTED_ENTRY"), ("000001.json", "REPLICA_UNEXPECTED_ENTRY"),
                             (".DS_Store", "REPLICA_UNEXPECTED_ENTRY")):
            path = self.w.a / T.RECORDS / name
            path.write_bytes(b"x")
            self.assertEqual(self.refused(self.w.a), reason, name)
            os.unlink(path)

    def test_crash_states_per_backend(self):
        data = OF.record_bytes(self.record)
        records = self.w.a / T.RECORDS
        # RENAME / HARDLINK before publication: only the pending name exists -> fail closed, manual
        (records / f"{COP.PENDING_PREFIX}{self.name}.tmp").write_bytes(data)
        self.assertEqual(self.refused(self.w.a), "REPLICA_PENDING_WRITE")
        # HARDLINK after link, before unlink: both names -> fail closed (impossible for RENAME)
        (records / self.name).write_bytes(data)
        self.assertEqual(self.refused(self.w.a), "REPLICA_PENDING_WRITE")
        os.unlink(records / f"{COP.PENDING_PREFIX}{self.name}.tmp")
        # after a complete publication (any backend): the record verifies
        self.assertEqual(T.load_replica(self.w.a).digests, (self.proposed["recordDigest"],))


class AndroidProbeScriptTests(unittest.TestCase):
    def setUp(self):
        self.t = Temp(self)
        self.script = load_probe_script()

    @unittest.skipUnless(POSIX, "POSIX primitives")
    def test_probe_output_format_and_cleanup(self):
        base = self.t.sub("tmp")
        result = self.script.probe(str(base))
        self.assertEqual(os.listdir(base), [])
        text = self.script.render(result)
        lines = text.strip().split("\n")
        self.assertEqual(lines[0], "ANDROID_P3_PROBE")
        self.assertEqual([line.split("=")[0] for line in lines[1:]],
                         ["directory_fsync", "hardlink", "rename_noreplace", "direct_o_excl", "symlink_detection",
                          "canonical_reread", "cleanup", "admitted_backend"])
        self.assertEqual(result["admitted_backend"], "RENAME_NOREPLACE_V1")
        self.assertNotIn(str(base), text)                                       # no paths in the output

    @unittest.skipUnless(POSIX, "POSIX primitives")
    def test_probe_reports_s25_like_hardlink_denial(self):
        with mock.patch.object(self.script.os, "link", side_effect=PermissionError(errno.EACCES, "Permission denied")):
            result = self.script.probe(str(self.t.sub("tmp")))
        self.assertEqual((result["hardlink"], result["admitted_backend"]), ("FAIL", "RENAME_NOREPLACE_V1"))
        with mock.patch.object(self.script.os, "link", side_effect=PermissionError(errno.EACCES, "denied")), \
                mock.patch.object(self.script, "_rename_noreplace", side_effect=self.script.Unavailable()):
            result = self.script.probe(str(self.t.sub("tmp2")))
        self.assertEqual((result["rename_noreplace"], result["admitted_backend"]), ("UNAVAILABLE", "NONE"))

    def test_probe_refuses_shared_storage_non_termux_and_replicas(self):
        for tmpdir in ("/sdcard/Download", "/storage/emulated/0", "/mnt/media_rw/x"):
            with mock.patch.dict(os.environ, {"TMPDIR": tmpdir}):
                with self.assertRaises(SystemExit):
                    self.script._base(require_termux=True)
        with mock.patch.dict(os.environ, {"TMPDIR": str(self.t.dir)}):
            with self.assertRaises(SystemExit):
                self.script._base(require_termux=True)                         # not Termux private storage
        replica = self.t.sub("replica")
        (replica / "REPLICA.json").write_text("{}", encoding="utf-8")
        inside = replica / "tmp"
        inside.mkdir()
        with mock.patch.dict(os.environ, {"TMPDIR": str(inside)}):
            with self.assertRaises(SystemExit):
                self.script._base(require_termux=False)
        source = PROBE_SCRIPT.read_text(encoding="utf-8")
        for forbidden in ("socket", "urllib", "subprocess", "/sdcard/", "REPLICA.json\")\n"):
            if forbidden != "/sdcard/":
                self.assertNotIn(forbidden, source, forbidden)

    def test_design_record(self):
        text = RECORD.read_text(encoding="utf-8")
        for line in ("HARD_LINK = FAIL", "RENAME_NOREPLACE_V1", "DIRECT_O_EXCL_V1", "admittedBackend",
                     "If O_EXCL prevents overwrite, then every crash state is safe",
                     "If the phone is a separate device", "P3_3_STORAGE_INCOMPLETE", "Smart Switch"):
            self.assertIn(line, text, line)


class _NoOsLink:
    """Temporarily remove os.link, as in the Termux Python 3.14 build on the S25."""

    def __enter__(self):
        self.saved = os.link
        del os.link
        return self

    def __exit__(self, *exc):
        os.link = self.saved
        return False


@unittest.skipUnless(POSIX, "POSIX primitives")
class ProbeFailContainmentTests(unittest.TestCase):
    """Regression: the probe crashed with AttributeError when os.link was absent."""

    KEYS = ["directory_fsync", "hardlink", "rename_noreplace", "direct_o_excl", "symlink_detection",
            "canonical_reread", "cleanup", "admitted_backend"]

    def setUp(self):
        self.t = Temp(self)
        self.script = load_probe_script()

    def full_block(self, result) -> None:
        lines = self.script.render(result).strip().split("\n")
        self.assertEqual(lines[0], "ANDROID_P3_PROBE")
        self.assertEqual([line.split("=")[0] for line in lines[1:]], self.KEYS)

    def test_os_link_attribute_absent(self):
        base = self.t.sub("tmp")
        with _NoOsLink():
            self.assertFalse(hasattr(os, "link"))
            result = self.script.probe(str(base))
        self.assertEqual(result["hardlink"], "UNAVAILABLE")
        self.assertEqual(result["rename_noreplace"], "PASS")                 # still evaluated
        self.assertEqual(result["direct_o_excl"], "PASS")
        for key in ("directory_fsync", "symlink_detection", "canonical_reread", "cleanup"):
            self.assertEqual(result[key], "PASS", key)
        self.assertEqual(result["admitted_backend"], "RENAME_NOREPLACE_V1")
        self.full_block(result)
        self.assertEqual(os.listdir(base), [])

    def test_os_link_permission_denied(self):
        with mock.patch.object(self.script.os, "link", side_effect=PermissionError(errno.EACCES, "Permission denied")):
            result = self.script.probe(str(self.t.sub("tmp")))
        self.assertEqual(result["hardlink"], "FAIL")
        self.assertEqual(result["rename_noreplace"], "PASS")
        self.assertEqual(result["admitted_backend"], "RENAME_NOREPLACE_V1")
        self.full_block(result)

    def test_rename_noreplace_evaluated_after_hardlink_failure(self):
        calls = []
        real = self.script._rename_noreplace

        def recording(src, dst):
            calls.append(dst)
            return real(src, dst)

        order = []
        real_backend = self.script._backend

        def tracking(root, name, publish):
            order.append(name)
            return real_backend(root, name, publish)

        with mock.patch.object(self.script, "_rename_noreplace", side_effect=recording),                 mock.patch.object(self.script, "_backend", side_effect=tracking), _NoOsLink():
            result = self.script.probe(str(self.t.sub("tmp")))
        self.assertEqual(set(order), {"rename", "link", "direct"})           # every backend attempted
        self.assertTrue(calls)                                                 # rename-noreplace really called
        self.assertEqual((result["hardlink"], result["rename_noreplace"]), ("UNAVAILABLE", "PASS"))

    def test_admitted_none_when_no_admitted_backend_passes(self):
        with _NoOsLink(), mock.patch.object(self.script, "_rename_noreplace", side_effect=self.script.Unavailable()):
            result = self.script.probe(str(self.t.sub("tmp")))
        self.assertEqual((result["hardlink"], result["rename_noreplace"], result["direct_o_excl"]),
                         ("UNAVAILABLE", "UNAVAILABLE", "PASS"))
        self.assertEqual(result["admitted_backend"], "NONE")                  # DIRECT_O_EXCL is never admitted
        self.full_block(result)

    def test_unexpected_backend_error_is_contained(self):
        with mock.patch.object(self.script, "_rename_noreplace", side_effect=ValueError("unexpected")),                 mock.patch.object(self.script, "_dir_fsync", wraps=self.script._dir_fsync):
            result = self.script.probe(str(self.t.sub("tmp")))
        self.assertEqual(result["rename_noreplace"], "FAIL")
        self.assertEqual(result["hardlink"], "PASS")
        self.assertEqual(result["admitted_backend"], "HARDLINK_PUBLISH_V1")
        self.full_block(result)

    def test_common_check_failure_is_contained(self):
        with mock.patch.object(self.script.os, "symlink", side_effect=PermissionError(errno.EACCES, "no")):
            result = self.script.probe(str(self.t.sub("tmp")))
        self.assertEqual(result["symlink_detection"], "FAIL")
        self.assertEqual(result["rename_noreplace"], "PASS")                   # later checks still ran
        self.assertEqual(result["admitted_backend"], "NONE")                  # a common check failed
        self.full_block(result)

    def test_main_always_emits_the_complete_block(self):
        base = self.t.sub("tmp")
        out = io.StringIO()
        with _NoOsLink(), mock.patch.object(self.script, "_base", return_value=str(base)), redirect_stdout(out):
            self.assertEqual(self.script.main(), 0)
        lines = out.getvalue().strip().split("\n")
        self.assertEqual(lines[0], "ANDROID_P3_PROBE")
        self.assertEqual(len(lines), 1 + len(self.KEYS))
        self.assertIn("admitted_backend=RENAME_NOREPLACE_V1", lines)

    def test_tool_probe_and_publisher_without_os_link(self):
        with _NoOsLink():
            probe = T.probe_storage(self.t.sub("store"))
            self.assertEqual(probe["backends"]["hardlinkPublish"], T.UNAVAILABLE)
            self.assertEqual(probe["backends"]["renameNoReplace"], T.PASS)
            self.assertEqual((probe["result"], probe["admittedBackend"]), (T.P3_STORAGE_CAPABLE, "RENAME_NOREPLACE_V1"))
            d = self.t.sub("d")
            with self.assertRaises(COP.HardLinkUnavailable):
                COP.publish(d, "000001-a.json", DATA, backend=COP.HARDLINK_PUBLISH_V1)
            self.assertEqual(os.listdir(d), [])
            with mock.patch.object(COP, "rename_noreplace",
                                   side_effect=COP.RenameNoReplaceUnavailable(errno.ENOSYS, "x")):
                none = T.probe_storage(self.t.sub("store2"))
            self.assertEqual((none["result"], none["admittedBackend"]), (T.P3_STORAGE_INCAPABLE, "NONE"))


if __name__ == "__main__":
    unittest.main()
