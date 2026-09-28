"""15B2b-B1b-3e PR-1A build-attestation gate: comparator, attestation, host observer.

Everything runs on local temporary trees with stand-in wheels. Nothing
touches `/`, DEV, or PROD; no key, credential, or authority exists here.
"""

from __future__ import annotations

import contextlib
import gzip
import io
import json
import os
import sys
import tarfile
import tempfile
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for path in (HERE, ROOT / "services/authority-dev", ROOT / "services/authority-dev/ceremony"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import attest_authority_dev_build as AT  # noqa: E402
import build_authority_dev_release as BR  # noqa: E402
import install_authority_dev as I  # noqa: E402
from test_custody_preparation import fake_wheels  # noqa: E402

POSIX = os.name == "posix"
SHA = "c608fc0ffaeee41d7ebf007dc0a66321a1907d31"


def write_build(directory: Path, payloads: dict[str, bytes], *, sha: str = SHA, mode_override: dict | None = None,
                gzip_mtime: int = 0) -> tuple[Path, Path]:
    """The builder's exact archive and stamp, with optional deliberate defects."""
    manifest = I.manifest_for(sha, payloads)
    if mode_override is None and gzip_mtime == 0:
        raw = I.write_archive(payloads, manifest)
    else:
        buffer = io.BytesIO()
        with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=gzip_mtime) as zipped:
            with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for path, data in sorted({**payloads, I.MANIFEST: I.canonical(manifest)}.items()):
                    member = tarfile.TarInfo(path)
                    member.size, member.mtime = len(data), 0
                    member.mode = (mode_override or {}).get(path, 0o600)
                    tar.addfile(member, io.BytesIO(data))
        raw = buffer.getvalue()
    directory.mkdir(parents=True, exist_ok=True)
    archive, stamp = directory / "release.tar.gz", directory / "release.attestation.json"
    archive.write_bytes(raw)
    stamp.write_bytes(I.canonical({"schemaVersion": 1, "artifactRole": I.ROLE, "candidateSha": sha,
                                   "archiveByteSize": len(raw), "archiveSha256": I.digest(raw),
                                   "manifestSha256": I.digest(I.canonical(manifest))}))
    return archive, stamp


class BuildAttestationTests(unittest.TestCase):
    def setUp(self):
        self._stack = contextlib.ExitStack()
        self.wheels = self._stack.enter_context(fake_wheels())
        self.out = Path(self._stack.enter_context(tempfile.TemporaryDirectory()))
        self.payloads = BR.build_payloads(ROOT, self.wheels)

    def tearDown(self):
        self._stack.close()

    def inspect(self, name: str, payloads: dict[str, bytes] | None = None, **kw) -> dict:
        archive, stamp = write_build(self.out / name, payloads or self.payloads, **kw)
        return AT.inspect_build(archive, stamp, SHA, ROOT)

    def test_two_independent_builds_reproduce_and_attest(self):
        a, b = self.inspect("a"), self.inspect("b")
        self.assertEqual(AT.differences(a["identity"], b["identity"]), [])
        document = AT.build_attestation(a, b)
        self.assertEqual(document["reproducibility"]["result"], "REPRODUCED")
        self.assertEqual(document["archiveSha256"], a["identity"]["archive"]["sha256"])
        self.assertEqual(set(document["cliDigests"]), set(I.CLI_TARGETS))
        self.assertEqual(set(document["unitDigests"]), {m for m in I.EXPECTED_PATHS if m.startswith("assets/")})
        self.assertEqual({t for t in document["hostTargets"]},
                         set(I.UNIT_TARGETS.values()) | set(I.WITNESS_UNIT_TARGETS.values()) | set(I.CLI_TARGETS.values()))
        self.assertEqual(AT.attestation_digest(document), AT.attestation_digest(json.loads(AT.canonical(document))))
        self.assertTrue(AT.attestation_digest(document) != AT.sha256(AT.canonical(document)))  # domain separated
        self.assertIn("NOT_AUTHORITY", document["nonclaims"])
        self.assertEqual(AT.check_candidate(document, self.inspect("c")), [])

    def test_environment_is_provenance_not_identity(self):
        a, b = self.inspect("a"), self.inspect("b")
        b["environment"] = {"python": "other"}
        AT.build_attestation(a, b)

    def test_one_changed_payload_byte_is_not_reproduced(self):
        changed = dict(self.payloads)
        changed["lilith_authority_dev/core.py"] = changed["lilith_authority_dev/core.py"] + b" "
        with self.assertRaises(AT.AttestError) as ctx:
            AT.build_attestation(self.inspect("a"), self.inspect("b", changed))
        self.assertIn("/payload/lilith_authority_dev/core.py/sha256", ctx.exception.reason)
        self.assertIn("/runtimeDigests/authority", ctx.exception.reason)

    def test_changed_unit_and_cli_bytes_are_named(self):
        for member, key in (("assets/lilith-recovery-witness.service", "/unitDigests/"),
                            ("cli/lilith-authority-hold-dev", "/cliDigests/")):
            changed = dict(self.payloads)
            changed[member] = changed[member] + b"\n"
            with self.assertRaises(AT.AttestError) as ctx:
                AT.build_attestation(self.inspect("a" + key[1]), self.inspect("b" + key[1], changed))
            self.assertIn(key + member, ctx.exception.reason)
            self.assertIn("/hostTargets/", ctx.exception.reason)

    def test_changed_member_mode_and_gzip_timestamp_are_named(self):
        with self.assertRaises(AT.AttestError) as ctx:
            AT.build_attestation(self.inspect("a"), self.inspect("b", mode_override={"requirements.lock": 0o644}))
        self.assertIn("/tarMembers[", ctx.exception.reason)
        self.assertIn("/archive/sha256", ctx.exception.reason)
        with self.assertRaises(AT.AttestError) as ctx:
            AT.build_attestation(self.inspect("c"), self.inspect("d", gzip_mtime=1))
        self.assertIn("/archive/gzipHeader/mtime", ctx.exception.reason)

    def test_extra_removed_or_flipped_artifacts_are_refused(self):
        extra = {**self.payloads, "lilith_authority_dev/extra.py": b"x = 1\n"}
        removed = {k: v for k, v in self.payloads.items() if k != "cli/lilith-authority-verify-dev"}
        for name, payloads in (("extra", extra), ("removed", removed)):
            manifest = I.manifest_for(SHA, payloads)
            raw = I.write_archive(payloads, manifest)
            (self.out / name).mkdir()
            archive, stamp = self.out / name / "a.tar.gz", self.out / name / "a.json"
            archive.write_bytes(raw)
            stamp.write_bytes(I.canonical({"schemaVersion": 1, "artifactRole": I.ROLE, "candidateSha": SHA,
                                           "archiveByteSize": len(raw), "archiveSha256": I.digest(raw),
                                           "manifestSha256": I.digest(I.canonical(manifest))}))
            with self.assertRaises(AT.AttestError):
                AT.inspect_build(archive, stamp, SHA, ROOT)
        archive, stamp = write_build(self.out / "flip", self.payloads)
        raw = bytearray(archive.read_bytes())
        raw[len(raw) // 2] ^= 1
        archive.write_bytes(bytes(raw))
        with self.assertRaises(AT.AttestError):
            AT.inspect_build(archive, stamp, SHA, ROOT)

    def test_check_candidate_names_every_mismatch(self):
        document = AT.build_attestation(self.inspect("a"), self.inspect("b"))
        changed = dict(self.payloads)
        changed["cli/lilith-authority-ledger-dev"] += b"\n"
        failures = AT.check_candidate(document, self.inspect("c", changed))
        self.assertIn("CANDIDATE_MISMATCH:archiveSha256", failures)
        self.assertIn("CANDIDATE_MISMATCH:cliDigests", failures)
        self.assertIn("CANDIDATE_MISMATCH:rootToolingDigest", failures)

    def test_malformed_inspection_is_refused(self):
        a = self.inspect("a")
        a["identity"]["sourceCommit"] = "0" * 40  # identitySha256 no longer matches
        with self.assertRaises(AT.AttestError):
            AT.build_attestation(a, self.inspect("b"))


# ------------------------------------------------------------ host observer ---

def _tree_state(root: Path) -> dict:
    state = {}
    for directory, subdirs, files in os.walk(root, followlinks=False):
        for name in subdirs + files:
            meta = os.lstat(Path(directory, name))
            state[str(Path(directory, name).relative_to(root))] = (meta.st_mode, meta.st_size, meta.st_mtime_ns,
                                                                   meta.st_ctime_ns, meta.st_ino)
    return state


@unittest.skipUnless(POSIX, "the observer uses pwd/grp and POSIX lstat semantics")
class HostObserverTests(unittest.TestCase):
    def setUp(self):
        import observe_authority_dev_host as O
        self.O = O
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        r = self.root
        for d in ("etc/systemd/system/multi-user.target.wants", "etc/tmpfiles.d", "usr/local/sbin", "var/lib/systemd",
                  "proc/sys/kernel/random", "proc/self", "etc/credstore", "run/credentials", "opt/lilith-authority-dev/releases"):
            (r / d).mkdir(parents=True, exist_ok=True)
        (r / "etc/machine-id").write_text(O.DEV_MACHINE_ID + "\n")
        (r / "etc/os-release").write_text('PRETTY_NAME="Ubuntu 24.04.4 LTS"\n')
        (r / "proc/sys/kernel/random/boot_id").write_text("24d1771d-e1b5-4e5f-816d-da08ad8b367a\n")
        (r / "proc/sys/kernel/osrelease").write_text("6.17.0-1022-gcp\n")
        (r / "proc/uptime").write_text("100.0 50.0\n")
        (r / "proc/swaps").write_text("Filename\tType\tSize\tUsed\tPriority\n")
        (r / "proc/self/mountinfo").write_text("25 1 8:1 / / rw,relatime shared:1 - ext4 /dev/root rw\n")
        store = r / "etc/credstore.encrypted"
        store.mkdir(mode=0o700)
        (store / "lilith-authority-dev.owner-actor.cred").write_bytes(b"TEST_ONLY stand-in ciphertext")
        os.chmod(store / "lilith-authority-dev.owner-actor.cred", 0o600)
        (r / "var/lib/systemd/credential.secret").write_bytes(b"TEST_ONLY host key stand-in")
        os.chmod(r / "var/lib/systemd/credential.secret", 0o400)
        top = r / "opt/lilith-authority-dev/releases" / SHA
        payloads = {"assets/lilith-authority-dev.service": b"[Unit]\n", "cli/lilith-authority-keygen-dev": b"#!x\n"}
        for member, data in payloads.items():
            (top / member).parent.mkdir(parents=True, exist_ok=True)
            (top / member).write_bytes(data)
        (top / I.MANIFEST).write_bytes(I.canonical(I.manifest_for(SHA, payloads)))
        (top / "venv/bin").mkdir(parents=True)
        (top / "venv/bin/python").write_bytes(b"#!/bin/false\n")
        for directory, subdirs, _ in os.walk(r / "opt"):
            for name in subdirs:
                os.chmod(Path(directory, name), 0o755)
        os.symlink(f"releases/{SHA}", r / "opt/lilith-authority-dev/current")
        (r / "etc/systemd/system/lilith-authority-dev.service").write_bytes(b"[Unit]\n")
        self.opened: list[str] = []
        pw = types.SimpleNamespace
        users = {"lilith-authority-dev": pw(pw_uid=995, pw_gid=985, pw_dir="/nonexistent", pw_shell="/usr/sbin/nologin")}
        groups = {"lilith-authority-dev": pw(gr_gid=985, gr_mem=[])}
        self.host = O.Host(root=r, run=self._run, euid=lambda: 0, hostname=lambda: "lilith-dev-01",
                           user=users.get, group=groups.get, grouplist=lambda name, gid: [gid])

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, argv):
        self.assertEqual(argv[:3], ["/usr/bin/systemctl", "show", argv[2]])
        self.assertTrue(argv[2].startswith("--property="))
        import subprocess
        return subprocess.CompletedProcess(argv, 0, "LoadState=loaded\nActiveState=inactive\n", "")

    @contextlib.contextmanager
    def record_opens(self):
        real = os.open

        def spy(path, flags, *args, **kw):
            self.opened.append(str(path))
            self.assertFalse(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            return real(path, flags, *args, **kw)
        os.open = spy
        try:
            yield
        finally:
            os.open = real

    def test_observation_is_read_only_and_never_opens_the_host_key(self):
        before = _tree_state(self.root)
        with self.record_opens():
            value = self.O.report(self.O.observe(self.host))
        self.assertEqual(_tree_state(self.root), before)
        self.assertFalse(any(p.endswith("credential.secret") for p in self.opened))
        facts = value["facts"]
        self.assertEqual(facts["hostKey"]["mode"], "0400")
        self.assertEqual(facts["currentBlob"]["mode"], "0600")
        self.assertEqual(len(facts["currentBlob"]["sha256"]), 64)
        self.assertEqual(sorted(facts["listings"]["/etc/credstore.encrypted"]), ["lilith-authority-dev.owner-actor.cred"])
        self.assertEqual(facts["accounts"]["lilith-authority-dev"]["uid"], 995)
        self.assertIsNone(facts["accounts"]["lilith-recovery-witness"])
        self.assertTrue(all(v is None for v in facts["pr1Objects"].values()))
        tree = facts["releases"]["trees"][SHA]
        self.assertEqual((tree["manifest"]["mismatched"], tree["manifest"]["notInManifest"], tree["unexpected"]),
                         ([], [], []))
        self.assertEqual(facts["releases"]["current"]["target"], f"releases/{SHA}")
        self.assertEqual(facts["host"]["bootId"], "24d1771d-e1b5-4e5f-816d-da08ad8b367a")
        self.assertEqual(facts["units"]["enablementOrDropInEntries"], [])
        future = facts["filesystems"]["/etc/lilith-authority-custody"]
        self.assertEqual(future["nearestExisting"], "/etc")
        self.assertEqual(future["device"], facts["filesystems"]["/etc/credstore.encrypted"]["device"])

    def test_stable_digest_reproduces_and_detects_drift(self):
        first = self.O.report(self.O.observe(self.host))
        (self.root / "proc/uptime").write_text("200.0 50.0\n")  # volatile only
        second = self.O.report(self.O.observe(self.host))
        self.assertEqual(first["stableSha256"], second["stableSha256"])
        blob = self.root / "etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred"
        blob.write_bytes(b"TEST_ONLY stand-in ciphertext")  # same bytes, rewritten: identity changes
        third = self.O.report(self.O.observe(self.host))
        self.assertNotEqual(first["sectionSha256"]["currentBlob"], third["sectionSha256"]["currentBlob"])
        (self.root / "etc/lilith-authority-custody").mkdir()
        fourth = self.O.report(self.O.observe(self.host))
        self.assertIsNotNone(fourth["facts"]["pr1Objects"]["/etc/lilith-authority-custody"])
        self.assertNotEqual(third["sectionSha256"]["pr1Objects"], fourth["sectionSha256"]["pr1Objects"])

    def test_tampered_release_file_and_extra_file_are_reported(self):
        top = self.root / "opt/lilith-authority-dev/releases" / SHA
        (top / "cli/lilith-authority-keygen-dev").write_bytes(b"#!y\n")
        (top / "assets/extra.conf").write_bytes(b"x")
        tree = self.O.observe_release_tree(self.host, SHA)
        self.assertEqual(tree["manifest"]["mismatched"], ["cli/lilith-authority-keygen-dev"])
        self.assertEqual(tree["manifest"]["notInManifest"], ["assets/extra.conf"])

    def test_host_key_read_is_refused_and_cli_is_closed(self):
        with self.assertRaises(self.O.ObserveError):
            self.O.file_sha256(self.host, "/var/lib/systemd/credential.secret")
        with self.assertRaises(self.O.ObserveError):
            self.O.read_text(self.host, "/var/lib/systemd/credential.secret")
        for argv in ([], ["observe", "/etc"], ["status"], ["observe", "--root", "/"]):
            self.assertEqual(self.O.main(argv, self.host), 2)

    def test_dev_root_guard(self):
        self.O.require_dev_root(self.host)
        for host in (self.O.Host(root=self.root, euid=lambda: 1000, hostname=lambda: "lilith-dev-01"),
                     self.O.Host(root=self.root, euid=lambda: 0, hostname=lambda: "lilith-01")):
            with self.assertRaises(self.O.ObserveError):
                self.O.require_dev_root(host)
        (self.root / "etc/machine-id").write_text("0" * 32 + "\n")
        with self.assertRaises(self.O.ObserveError):
            self.O.require_dev_root(self.host)

    def test_source_is_standalone_and_has_no_write_primitives(self):
        source = (ROOT / "services/authority-dev/ceremony/observe_authority_dev_host.py").read_text(encoding="utf-8")
        for token in ("import install_authority_dev", "__file__", "O_WRONLY", "O_RDWR", "O_CREAT", "write_bytes",
                      "write_text", ".unlink(", ".rmdir(", "os.chmod", "os.chown", "os.rename", ".mkdir(", "os.remove",
                      "shutil", "urllib", "import socket", "\"systemd-creds\"", "\"daemon-reload\"", "\"start\"",
                      "\"stop\"", "\"restart\""):
            self.assertNotIn(token, source, token)


if __name__ == "__main__":
    unittest.main()
