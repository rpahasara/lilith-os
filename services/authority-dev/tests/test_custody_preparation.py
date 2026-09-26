"""15B2b-B1b-3d L2 custody-preparation tests (repository only).

Everything runs against temporary directories with injected OS lookups and
commands. No test calls `Ed25519PrivateKey.generate()`, runs `systemd-creds`,
touches `/`, contacts DEV/PROD, or reuses a B1b-3a fixture seed. The one
in-process key below is a local constant used only to exercise the pipeline.
"""

from __future__ import annotations

import base64
import contextlib
import fnmatch
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "ceremony"
ROOT = HERE.parents[2]
for path in (HERE, ROOT / "scripts", ROOT / "services/authority-dev", ROOT / "services/core-api",
             ROOT / "services/owner-memory-control", ROOT / "services/owner-memory-control/tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from cryptography.hazmat.primitives.serialization import (  # noqa: E402
    Encoding, NoEncryption, PrivateFormat, PublicFormat,
)

import build_authority_dev_release as B  # noqa: E402
import install_authority_dev as I  # noqa: E402
import lilith_authority_keygen_dev as G  # noqa: E402
import release_file_set as RFS  # noqa: E402
from lilith_authority_dev import credential as CRED  # noqa: E402
from lilith_authority_dev import profile as PR  # noqa: E402
from lilith_owner_memory import authority_contracts as A  # noqa: E402

POSIX = os.name == "posix"
SHA = "c608fc0ffaeee41d7ebf007dc0a66321a1907d31"
# Local pipeline-exercise key: not a B1b-3a seed, never packaged, never on DEV.
PIPELINE_KEY_BYTES = bytes(range(32))
KEYGEN_SOURCE = (HERE / "lilith_authority_keygen_dev.py").read_text(encoding="utf-8")
INSTALLER_SOURCE = (HERE / "install_authority_dev.py").read_text(encoding="utf-8")
def code_only(source: str) -> str:
    """Source with every docstring and comment removed."""
    import ast
    tree = ast.parse(source)
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            body.pop(0)
            if not body:
                body.append(ast.Pass())
    return ast.unparse(tree)


RUNBOOK = (ROOT / "docs/architecture/slice-15b2b-b1b3d-l2-custody-preparation.md").read_text(encoding="utf-8")


def pipeline_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(PIPELINE_KEY_BYTES)


def fake_encrypt(record: list):
    def encrypt(plaintext: bytes) -> bytes:
        record.append(plaintext)
        return b"FAKE-SYSTEMD-CREDS-CIPHERTEXT:" + hashlib.sha256(plaintext).hexdigest().encode()
    return encrypt


class FakeHost:
    """A temporary host tree plus fake accounts, units, and commands."""

    def __init__(self, directory: str):
        self.root = Path(directory)
        self.calls: list[list[str]] = []
        pw = types.SimpleNamespace
        self.users = {"lilith": pw(pw_uid=1001, pw_gid=1002, pw_dir="/home/lilith", pw_shell="/bin/bash"),
                      "lilith-memory-broker": pw(pw_uid=999, pw_gid=987, pw_dir="/nonexistent", pw_shell=I.NOLOGIN),
                      "lilith-memory-relay": pw(pw_uid=997, pw_gid=986, pw_dir="/nonexistent", pw_shell=I.NOLOGIN)}
        self.groups: dict[str, types.SimpleNamespace] = {}
        self.units = {u: {"LoadState": "not-found", "ActiveState": "inactive", "UnitFileState": "",
                          "NeedDaemonReload": "no"} for u in ("lilith-authority-dev.service", "lilith-authority-dev.socket")}
        for d in ("opt", "etc/systemd/system", "etc/tmpfiles.d", "etc/needrestart/conf.d", "usr/local/sbin", "usr/bin",
                  "var/lib/systemd", "proc"):
            (self.root / d).mkdir(parents=True, exist_ok=True)
        (self.root / "etc/machine-id").write_text(I.DEV_MACHINE_ID + "\n", encoding="ascii")
        (self.root / "etc/shadow").write_text("root:*:1::::::\n", encoding="utf-8")
        (self.root / "proc/swaps").write_text("Filename\tType\tSize\tUsed\tPriority\n", encoding="ascii")
        (self.root / "etc/needrestart/conf.d/lilith-authority-sensitive.conf").write_bytes(
            (ROOT / "services/memory-broker/deploy/needrestart-lilith-authority-sensitive.conf").read_bytes())
        creds = self.root / "usr/bin/systemd-creds"
        creds.write_bytes(b"#!/bin/false\n")
        os.chmod(creds, 0o755)

    def run(self, argv, cwd=None, **_kw):
        argv = list(argv)
        self.calls.append(argv)
        name = Path(argv[0]).name
        out = ""
        if name == "useradd":
            user = argv[-1]
            self.users[user] = types.SimpleNamespace(pw_uid=990, pw_gid=980, pw_dir=I.NO_HOME, pw_shell=I.NOLOGIN)
            self.groups[user] = types.SimpleNamespace(gr_gid=980, gr_mem=[])
            with open(self.root / "etc/shadow", "a", encoding="utf-8") as shadow:
                shadow.write(f"{user}:!:1::::::\n")
        elif name == "systemctl" and argv[1] == "show":
            out = "\n".join(f"{k}={v}" for k, v in self.units[argv[-1]].items())
        elif name == "sudo":
            out = f"User {I.SERVICE_USER} is not allowed to run sudo on {I.DEV_HOSTNAME}.\n"
        elif name == "python3" and argv[1:3] == ["-m", "venv"]:
            venv = Path(argv[3])
            (venv / "bin").mkdir(parents=True)
            (venv / "bin/python").write_bytes(b"#!/bin/false\n")
            os.chmod(venv / "bin/python", 0o755)
        return subprocess.CompletedProcess(argv, 0, out, "")

    def system(self, **overrides) -> I.System:
        value = dict(root=self.root, run=self.run, user=self.users.get, group=self.groups.get,
                     grouplist=lambda name, gid: [gid], euid=lambda: 0, hostname=lambda: "lilith-dev-01",
                     chown=False, owner_uid=os.getuid() if POSIX else 0, owner_gid=os.getgid() if POSIX else 0)
        value.update(overrides)
        return I.System(**value)

    def keygen_host(self) -> G.Host:
        return G.Host(self.root, owner_uid=os.getuid() if POSIX else 0, owner_gid=os.getgid() if POSIX else 0)

    def daemon_reload(self) -> None:
        for state in self.units.values():
            state.update(LoadState="loaded", UnitFileState="static", NeedDaemonReload="no")

    def systemd_creds_setup(self) -> None:
        key = self.root / "var/lib/systemd/credential.secret"
        key.write_bytes(b"host key stand-in")
        os.chmod(key, 0o400)


@contextlib.contextmanager
def fake_wheels():
    """Replace the pinned wheel set with local stand-ins for the duration."""
    saved = (I.WHEEL_HASHES, I.LOCK, I.EXPECTED_PATHS)
    with tempfile.TemporaryDirectory() as directory:
        wheelhouse = Path(directory)
        hashes = {}
        for index, name in enumerate(saved[0]):
            data = f"stand-in wheel {index}".encode()
            (wheelhouse / name).write_bytes(data)
            hashes[name] = hashlib.sha256(data).hexdigest()
        I.WHEEL_HASHES = hashes
        I.LOCK = "".join(f"x{i}==1 --hash=sha256:{h}\n" for i, h in enumerate(hashes.values())).encode()
        try:
            yield wheelhouse
        finally:
            I.WHEEL_HASHES, I.LOCK, I.EXPECTED_PATHS = saved


def build_archive(directory: Path, wheelhouse: Path) -> tuple[Path, Path, bytes]:
    payloads = B.build_payloads(ROOT, wheelhouse)
    manifest = I.manifest_for(SHA, payloads)
    raw = I.write_archive(payloads, manifest)
    archive, attestation = directory / "release.tar.gz", directory / "release.json"
    archive.write_bytes(raw)
    attestation.write_bytes(I.canonical({
        "schemaVersion": 1, "artifactRole": I.ROLE, "candidateSha": SHA, "archiveByteSize": len(raw),
        "archiveSha256": I.digest(raw), "manifestSha256": I.digest(I.canonical(manifest))}))
    return archive, attestation, raw


# ---------------------------------------------------------------- keygen ---

class KeygenContractTests(unittest.TestCase):
    """Req 1-10, 12."""

    def test_fixed_values_match_l1_profile_and_design(self):
        self.assertEqual(G.KEY_ID, PR.PROPOSED_K_ACT_KEY_ID)
        self.assertEqual(G.KEY_ID, "test-only.dev-synthetic.actor.b1b3d.1")
        self.assertEqual((G.PROFILE, G.ENVIRONMENT, G.SIGNING_DOMAIN, G.EVIDENCE_TYPES, G.ALGORITHM),
                         (PR.PROFILE, PR.ENVIRONMENT, A.OWNER_ACTOR, (A.OWNER_MEMORY_OPERATION,), A.ALGORITHM))
        self.assertEqual((G.CREDENTIAL_NAME, G.CREDENTIAL_PATH), (PR.CREDENTIAL_NAME, PR.CREDENTIAL_SOURCE))
        self.assertEqual(G.ENCRYPT_ARGV, ("/usr/bin/systemd-creds", "encrypt", "--with-key=host",
                                          "--name=owner-actor-signing-key", "-", "-"))
        self.assertEqual(G.DEV_MACHINE_ID, I.DEV_MACHINE_ID)

    def test_only_actor_invocation_is_accepted(self):
        G.parse_argv(["actor"])
        with self.assertRaises(G.Refused) as caught:
            G.parse_argv(["witness"])
        self.assertEqual(caught.exception.reason, "WITNESS_NOT_IN_SCOPE")
        for argv in ([], ["ACTOR"], ["actor", "actor"], ["privacy"], ["PRIVACY"], ["actor", "--domain", "PRIVACY"],
                     ["actor", "--algorithm", "ecdsa"], ["actor", "--prod"], ["actor", "--environment", "prod"],
                     ["export"], ["actor", "--output", "/tmp/key.pem"], ["actor", "--seed", "00"],
                     ["actor", "--key-id", "x"], ["actor", "--force"], ["--help"], ["sign", "x"]):
            with self.assertRaises(G.Refused) as caught:
                G.parse_argv(argv)
            self.assertEqual(caught.exception.reason, "USAGE_ONLY_ACTOR", argv)

    def test_no_forbidden_capability_in_source(self):
        code = code_only(KEYGEN_SOURCE)
        for needle in ("PRIVACY", '"prod"', "argparse", "Encoding.PEM", "OpenSSH", "from_private_bytes",
                       "SEEDS", "TEST_ONLY", "synthetic_", ".sign(", "socket", "urllib", "http", "sqlite",
                       "requests", "systemctl", "enable", "registry", "lilith_owner_memory", "load_der"):
            self.assertNotIn(needle, code, needle)
        self.assertIs(G.ceremony.__kwdefaults__["key_factory"].__func__, Ed25519PrivateKey.generate.__func__)
        self.assertIn('ALGORITHM = "Ed25519"', KEYGEN_SOURCE)
        for marker in (b"-----" + b"BEGIN", b"PRIVATE" + b" KEY"):
            self.assertNotIn(marker, KEYGEN_SOURCE.encode())
        self.assertTrue(KEYGEN_SOURCE.startswith("#!/usr/bin/python3 -IB\n"))

    def test_no_b1b3a_seed_or_pipeline_key_in_runtime_artifacts(self):
        import synthetic_authority as SA  # the B1b-3a TEST fixture, test-side only
        blobs = [KEYGEN_SOURCE.encode(), INSTALLER_SOURCE.encode()] + list(RFS.runtime_payloads(ROOT).values())
        for data in blobs:
            for seed in list(SA.SEEDS.values()) + [PIPELINE_KEY_BYTES]:
                self.assertNotIn(seed, data)
                self.assertNotIn(seed.hex().encode(), data)
                self.assertNotIn(base64.urlsafe_b64encode(seed).rstrip(b"="), data)

    def test_malformed_invocation_fails_closed_without_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            host = FakeHost(directory)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(G.main(["actor", "--prod"], host=host.keygen_host()), G.EXIT_REFUSED)
                self.assertEqual(G.main(["witness"], host=host.keygen_host()), G.EXIT_REFUSED)
            self.assertIn("REFUSED USAGE_ONLY_ACTOR", err.getvalue())
            self.assertFalse((host.root / "etc/credstore.encrypted").exists())


@unittest.skipUnless(POSIX, "owner and mode semantics are POSIX")
class KeygenCeremonyTests(unittest.TestCase):
    """Req 1, 4, 11: preconditions, plaintext lifetime, public output."""

    def ready(self, directory: str) -> FakeHost:
        host = FakeHost(directory)
        host.systemd_creds_setup()
        store = host.root / "etc/credstore.encrypted"
        store.mkdir(mode=0o700)
        os.chmod(store, 0o700)
        return host

    def preflight(self, host: FakeHost, **overrides):
        value = dict(euid=0, isolated=True, hostname="lilith-dev-01")
        value.update(overrides)
        return G.preflight(host.keygen_host(), **value)

    def assertRefused(self, host, reason, **overrides):
        with self.assertRaises(G.Refused) as caught:
            self.preflight(host, **overrides)
        self.assertEqual(caught.exception.reason, reason)

    def test_preconditions(self):
        with tempfile.TemporaryDirectory() as directory:
            host = self.ready(directory)
            self.assertEqual(self.preflight(host), I.DEV_MACHINE_ID)
            self.assertRefused(host, "NOT_ROOT", euid=1000)
            self.assertRefused(host, "INTERPRETER_NOT_ISOLATED", isolated=False)
            self.assertRefused(host, "NOT_DEV_HOST", hostname="lilith-prod-01")
            (host.root / "proc/swaps").write_text("Filename\n/swapfile file 1 0 -2\n", encoding="ascii")
            self.assertRefused(host, "SWAP_ACTIVE")
            (host.root / "proc/swaps").write_text("Filename\n", encoding="ascii")
            os.chmod(host.root / "var/lib/systemd/credential.secret", 0o600)
            self.assertRefused(host, "HOST_CREDENTIAL_KEY_CUSTODY")
            (host.root / "var/lib/systemd/credential.secret").unlink()
            self.assertRefused(host, "HOST_CREDENTIAL_KEY_ABSENT")
        with tempfile.TemporaryDirectory() as directory:
            host = self.ready(directory)
            (host.root / "etc/machine-id").write_text("0" * 32, encoding="ascii")
            self.assertRefused(host, "NOT_DEV_HOST")
        with tempfile.TemporaryDirectory() as directory:
            host = self.ready(directory)
            os.chmod(host.root / "etc/credstore.encrypted", 0o755)
            self.assertRefused(host, "CREDSTORE_CUSTODY")
            os.rmdir(host.root / "etc/credstore.encrypted")
            self.assertRefused(host, "CREDSTORE_ABSENT")
        with tempfile.TemporaryDirectory() as directory:
            host = self.ready(directory)
            (host.root / "etc/credstore.encrypted/other.cred").write_bytes(b"x")
            self.assertRefused(host, "CREDSTORE_NOT_EMPTY")
            (host.root / "etc/credstore.encrypted/other.cred").unlink()
            (host.root / G.CREDENTIAL_PATH.lstrip("/")).write_bytes(b"x")
            self.assertRefused(host, "CREDENTIAL_ALREADY_PRESENT")

    def test_host_key_is_never_read(self):
        with tempfile.TemporaryDirectory() as directory:
            host = self.ready(directory)
            original = Path.read_bytes, Path.read_text, os.open
            touched = []

            def guard(path, *a, **k):
                if "credential.secret" in str(path):
                    touched.append(str(path))
                return original[2](path, *a, **k)

            os.open = guard
            try:
                self.preflight(host)
                G.ceremony(host.keygen_host(), I.DEV_MACHINE_ID, key_factory=pipeline_key, encrypt=fake_encrypt([]))
            finally:
                os.open = original[2]
            self.assertEqual(touched, [])

    def test_plaintext_only_reaches_the_encryptor(self):
        with tempfile.TemporaryDirectory() as directory:
            host = self.ready(directory)
            seen: list[bytes] = []
            result = G.ceremony(host.keygen_host(), I.DEV_MACHINE_ID, key_factory=pipeline_key,
                                encrypt=fake_encrypt(seen))
            der = pipeline_key().private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
            self.assertEqual(seen, [der])
            for path in host.root.rglob("*"):
                if path.is_file():
                    data = path.read_bytes()
                    self.assertNotIn(der, data, path)
                    self.assertNotIn(PIPELINE_KEY_BYTES, data, path)
            blob = host.root / G.CREDENTIAL_PATH.lstrip("/")
            self.assertEqual(oct(blob.stat().st_mode & 0o777), "0o600")
            self.assertEqual(result["custodyEvidence"]["blobSha256"], hashlib.sha256(blob.read_bytes()).hexdigest())
            printed = G.canonical(result)
            self.assertNotIn(der, printed)
            self.assertNotIn(base64.urlsafe_b64encode(der).rstrip(b"="), printed)
            with self.assertRaises(G.Refused):  # a second run never overwrites
                self.preflight(host)

    def test_leaking_encryptor_and_bad_factory_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            host = self.ready(directory)
            with self.assertRaises(G.Failed) as caught:
                G.ceremony(host.keygen_host(), I.DEV_MACHINE_ID, key_factory=pipeline_key,
                           encrypt=lambda plaintext: b"prefix" + plaintext)
            self.assertEqual(caught.exception.reason, "CIPHERTEXT_CONTAINS_PLAINTEXT")
            with self.assertRaises(G.Failed) as caught:
                G.ceremony(host.keygen_host(), I.DEV_MACHINE_ID, key_factory=pipeline_key,
                           encrypt=lambda plaintext: base64.b64encode(plaintext))
            self.assertEqual(caught.exception.reason, "CIPHERTEXT_CONTAINS_PLAINTEXT")
            with self.assertRaises(G.Failed):
                G.ceremony(host.keygen_host(), I.DEV_MACHINE_ID, key_factory=lambda: b"k", encrypt=fake_encrypt([]))
            self.assertFalse((host.root / G.CREDENTIAL_PATH.lstrip("/")).exists())

    def test_process_restriction_applies_on_linux(self):
        if not sys.platform.startswith("linux"):
            self.skipTest("prctl is Linux-only")
        code = ("import sys, resource; sys.path.insert(0, sys.argv[1]); import lilith_authority_keygen_dev as G; "
                "G.restrict_process(); print(resource.getrlimit(resource.RLIMIT_CORE), "
                "open('/proc/self/status').read().count('\\n'))")
        result = subprocess.run([sys.executable, "-c", code, str(HERE)], capture_output=True, text=True, check=True)
        self.assertTrue(result.stdout.startswith("(0, 0)"), result.stdout)

    def test_encryptor_uses_fixed_argv_and_environment(self):
        captured = {}
        original = subprocess.run
        try:
            subprocess.run = lambda argv, **kw: captured.update(argv=argv, **kw) or \
                subprocess.CompletedProcess(argv, 0, b"ciphertext", b"diagnostic never echoed")
            self.assertEqual(G.systemd_encrypt(b"plaintext"), b"ciphertext")
        finally:
            subprocess.run = original
        self.assertEqual(captured["argv"], G.ENCRYPT_ARGV)
        self.assertEqual(captured["env"], G.FIXED_ENV)
        self.assertEqual(captured["input"], b"plaintext")
        self.assertNotIn("shell", captured)


class PublicationTests(unittest.TestCase):
    """Req 11: deterministic public material, usable for AuthorityKeyRecordV1."""

    def test_deterministic_and_separated(self):
        public = pipeline_key().public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        first = G.canonical(G.publication(public, b"ciphertext", I.DEV_MACHINE_ID))
        second = G.canonical(G.publication(public, b"ciphertext", I.DEV_MACHINE_ID))
        self.assertEqual(first, second)
        self.assertTrue(first.endswith(b"}\n") and b" " not in first)
        value = json.loads(first)
        self.assertEqual(set(value), {"publicationType", "schemaVersion", "profile", "publicVerificationMaterial",
                                      "custodyEvidence"})
        self.assertEqual(set(value["publicVerificationMaterial"]), {
            "keyId", "signingDomain", "evidenceTypes", "environment", "algorithm", "publicKey", "publicKeySha256"})
        self.assertEqual(set(value["custodyEvidence"]), {
            "credentialName", "credentialPath", "withKey", "machineId", "blobByteSize", "blobSha256"})
        # The runbook's documented one-line shape has exactly these keys in this order.
        documented = re.search(r'^\{"custodyEvidence".*\}$', RUNBOOK, re.MULTILINE).group(0)
        self.assertEqual(re.findall(r'"([A-Za-z0-9]+)":', documented), re.findall(r'"([A-Za-z0-9]+)":', first.decode()))

    def test_public_material_builds_a_valid_key_record_and_matches_l1_fingerprint(self):
        der = pipeline_key().private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
        public = pipeline_key().public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        result = G.publication(public, b"ciphertext", I.DEV_MACHINE_ID)
        material = result["publicVerificationMaterial"]
        record = A.AuthorityKeyRecordV1.from_dict({
            "schemaVersion": 1, "keyId": material["keyId"], "signingDomain": material["signingDomain"],
            "evidenceTypes": material["evidenceTypes"], "environment": material["environment"],
            "algorithm": material["algorithm"], "publicKey": material["publicKey"],
            "createdAt": "2026-09-27T00:00:00Z", "notBefore": "2026-09-27T00:00:00Z", "retiredAt": None,
            "revokedAt": None, "revocationReason": None, "compromisedSince": None,
            "recoveryEpoch": {"counter": 0, "random": "0" * 32}, "policyVersion": "policy.dev-synthetic.v1",
            "registryVersion": 1})
        self.assertEqual(record.key_id, PR.PROPOSED_K_ACT_KEY_ID)
        self.assertEqual(CRED._classify(der).public_key_sha256, material["publicKeySha256"])


# ------------------------------------------------------------- installer ---

@unittest.skipUnless(POSIX, "owner and mode semantics are POSIX")
class InstallerLadderTests(unittest.TestCase):
    """Req 13, 14: every stage, one transition, exact POST contract."""

    def test_full_ladder_on_a_fake_host(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as out, fake_wheels() as wheels:
            host = FakeHost(directory)
            system = host.system()
            archive, attestation, _raw = build_archive(Path(out), wheels)
            self.assertEqual(I.status(system, "L0")["result"], "PASS")
            self.assertEqual(I.stage_accounts(system)["result"], "PASS")
            self.assertEqual(I.stage_release(system, SHA, archive, attestation)["result"], "PASS")
            self.assertEqual(I.stage_select(system, SHA)["result"], "PASS")
            self.assertEqual(I.stage_units(system, SHA)["result"], "PASS")
            self.assertEqual(I.status(system, "L1c.2", SHA)["result"], "FAIL")  # not yet reloaded
            host.daemon_reload()
            self.assertEqual(I.status(system, "L1c.2", SHA)["result"], "PASS")
            self.assertEqual(I.stage_cli(system, SHA)["result"], "PASS")
            self.assertEqual(I.status(system, "L2a", SHA)["result"], "FAIL")
            host.systemd_creds_setup()
            self.assertEqual(I.status(system, "L2a", SHA)["result"], "PASS")
            self.assertEqual(I.stage_credstore(system, SHA)["result"], "PASS")
            result = G.ceremony(host.keygen_host(), I.DEV_MACHINE_ID, key_factory=pipeline_key,
                                encrypt=fake_encrypt([]))
            final = I.status(system, "L2b.2", SHA)
            self.assertEqual(final["result"], "PASS", final["failures"])
            self.assertEqual(final["observed"]["credentialBlobSha256"], result["custodyEvidence"]["blobSha256"])
            # Commands: only fixed ones; never enable/start/reload/systemd-creds.
            names = {Path(call[0]).name for call in host.calls}
            self.assertEqual(names, {"useradd", "systemctl", "sudo", "python3", "python", "runuser"})
            for call in host.calls:
                if Path(call[0]).name == "systemctl":
                    self.assertEqual(call[1], "show")
            runuser = [call for call in host.calls if Path(call[0]).name == "runuser"]
            self.assertEqual(runuser[0][1:4], ["-u", I.SERVICE_USER, "--"])
            # Deferred paths stay absent.
            for path in I.DEFERRED_PATHS:
                self.assertFalse(os.path.lexists(host.root / path.lstrip("/")), path)
            installed = (host.root / "etc/systemd/system/lilith-authority-dev.service").read_bytes()
            self.assertEqual(installed, (ROOT / "services/authority-dev/deploy/lilith-authority-dev.service").read_bytes())

    def test_each_stage_refuses_out_of_order_and_on_collision(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as out, fake_wheels() as wheels:
            host = FakeHost(directory)
            system = host.system()
            archive, attestation, _ = build_archive(Path(out), wheels)
            for stage in (lambda: I.stage_release(system, SHA, archive, attestation),
                          lambda: I.stage_select(system, SHA), lambda: I.stage_units(system, SHA),
                          lambda: I.stage_cli(system, SHA), lambda: I.stage_credstore(system, SHA)):
                with self.assertRaises(I.InstallError):
                    stage()
            I.stage_accounts(system)
            with self.assertRaises(I.InstallError):
                I.stage_accounts(system)  # never corrects an existing identity
            I.stage_release(system, SHA, archive, attestation)
            with self.assertRaises(I.InstallError):
                I.stage_release(system, SHA, archive, attestation)
            with self.assertRaises(I.InstallError):
                I.stage_units(system, SHA)  # needs select first
            with self.assertRaises(I.InstallError):
                I.stage_accounts(host.system(euid=lambda: 1000))
            with self.assertRaises(I.InstallError):
                I.require_dev_root(host.system(hostname=lambda: "lilith-prod-01"))

    def test_account_contract_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            host = FakeHost(directory)
            I.stage_accounts(host.system())
            host.users[I.SERVICE_USER].pw_shell = "/bin/bash"
            self.assertIn("ACCOUNT_CONTRACT", I.status(host.system(), "L1a")["failures"])
            host.users[I.SERVICE_USER].pw_shell = I.NOLOGIN
            self.assertIn("ACCOUNT_CONTRACT", I.status(
                host.system(grouplist=lambda n, g: [g, 988]), "L1a")["failures"])
            host.users[I.SERVICE_USER].pw_uid = 1001
            self.assertIn("ACCOUNT_CONTRACT", I.status(host.system(), "L1a")["failures"])

    def test_active_or_enabled_unit_fails_status(self):
        with tempfile.TemporaryDirectory() as directory:
            host = FakeHost(directory)
            host.units["lilith-authority-dev.socket"]["ActiveState"] = "active"
            self.assertIn("UNIT_ACTIVE:lilith-authority-dev.socket", I.status(host.system(), "L0")["failures"])
            host.units["lilith-authority-dev.socket"].update(ActiveState="inactive", UnitFileState="enabled")
            self.assertIn("UNIT_ENABLEABLE_OR_ENABLED:lilith-authority-dev.socket",
                          I.status(host.system(), "L0")["failures"])

    def test_needrestart_control_must_be_present(self):
        with tempfile.TemporaryDirectory() as directory:
            host = FakeHost(directory)
            (host.root / "etc/needrestart/conf.d/lilith-authority-sensitive.conf").write_bytes(b"changed\n")
            self.assertIn("NEEDRESTART_CONTROL_CHANGED", I.status(host.system(), "L0")["failures"])


@unittest.skipUnless(POSIX, "owner and mode semantics are POSIX")
class HostPrerequisiteTests(unittest.TestCase):
    """AMBIENT HOST PREREQUISITE != LILITH CEREMONY ARTIFACT (run 36264031829)."""

    def secure_credstore(self, host: FakeHost) -> Path:
        store = host.root / "etc/credstore.encrypted"
        store.mkdir(mode=0o700)
        os.chmod(store, 0o700)
        return store

    def test_dev_observed_fixture_is_l0(self):  # regression 11 (root-side view)
        with tempfile.TemporaryDirectory() as directory:
            host = FakeHost(directory)
            self.secure_credstore(host)
            report = I.status(host.system(), "L0")
            self.assertEqual(report["result"], "PASS", report["failures"])
            self.assertEqual(report["observed"]["hostPrerequisites"],
                             {I.HOST_KEY: "ABSENT", I.CREDSTORE: "PRESENT_SECURE"})
            self.assertIsNone(report["observed"]["credentialBlobSha256"])

    def test_secure_prerequisites_do_not_imply_any_ladder_step(self):  # regressions 1-4
        with tempfile.TemporaryDirectory() as directory:
            host = FakeHost(directory)
            self.secure_credstore(host)
            host.systemd_creds_setup()
            self.assertEqual(I.status(host.system(), "L0")["result"], "PASS")
            self.assertEqual(I.status(host.system(), "L1a")["result"], "FAIL")  # nothing LILITH exists

    def test_unsafe_prerequisites_fail_closed(self):  # regression 5
        with tempfile.TemporaryDirectory() as directory:
            host = FakeHost(directory)
            store = self.secure_credstore(host)
            os.chmod(store, 0o755)
            self.assertIn(f"HOST_PREREQ_UNSAFE:{I.CREDSTORE}", I.status(host.system(), "L0")["failures"])
        with tempfile.TemporaryDirectory() as directory:
            host = FakeHost(directory)
            host.systemd_creds_setup()
            os.chmod(host.root / "var/lib/systemd/credential.secret", 0o600)
            self.assertIn(f"HOST_PREREQ_UNSAFE:{I.HOST_KEY}", I.status(host.system(), "L0")["failures"])
        with tempfile.TemporaryDirectory() as directory:
            host = FakeHost(directory)
            (self.secure_credstore(host) / "other.cred").write_bytes(b"x")
            self.assertIn("CREDSTORE_NOT_EMPTY", I.status(host.system(), "L0")["failures"])

    def test_out_of_order_lilith_blob_fails_closed(self):  # regression 6
        with tempfile.TemporaryDirectory() as directory:
            host = FakeHost(directory)
            (self.secure_credstore(host) / "lilith-authority-dev.owner-actor.cred").write_bytes(b"x")
            failures = I.status(host.system(), "L0")["failures"]
            self.assertIn(f"UNEXPECTED_PRESENT:{I.CREDENTIAL}", failures)
            self.assertIn("CREDSTORE_NOT_EMPTY", failures)

    def run_ladder_to_l2a(self, host: FakeHost, wheels: Path, out: Path, *, adopt_host_key: bool) -> I.System:
        system = host.system()
        archive, attestation, _ = build_archive(out, wheels)
        I.stage_accounts(system)
        I.stage_release(system, SHA, archive, attestation)
        I.stage_select(system, SHA)
        I.stage_units(system, SHA)
        host.daemon_reload()
        I.stage_cli(system, SHA)
        if not adopt_host_key:
            host.systemd_creds_setup()  # owner L2a transition when ABSENT
        self.assertEqual(I.status(system, "L2a", SHA)["result"], "PASS")
        return system

    def test_l2a_and_l2b1_adopt_existing_secure_prerequisites_without_mutation(self):  # regressions 7, 9, 10
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as out, fake_wheels() as wheels:
            host = FakeHost(directory)
            store = self.secure_credstore(host)  # ambient, before any LILITH ceremony
            host.systemd_creds_setup()           # ambient too
            key = host.root / "var/lib/systemd/credential.secret"
            before = (os.stat(store), os.stat(key), key.read_bytes())
            system = self.run_ladder_to_l2a(host, wheels, Path(out), adopt_host_key=True)
            report = I.stage_credstore(system, SHA)
            self.assertEqual(report["result"], "PASS", report["failures"])
            self.assertEqual(report["mutation"], "ADOPTED_NO_MUTATION")
            after = (os.stat(store), os.stat(key), key.read_bytes())
            for b, a in zip(before[:2], after[:2]):
                self.assertEqual((b.st_ino, b.st_mtime_ns, b.st_mode), (a.st_ino, a.st_mtime_ns, a.st_mode))
            self.assertEqual(before[2], after[2])
            for call in host.calls:
                self.assertNotIn("systemd-creds", " ".join(call))
            G.ceremony(host.keygen_host(), I.DEV_MACHINE_ID, key_factory=pipeline_key, encrypt=fake_encrypt([]))
            final = I.status(system, "L2b.2", SHA)
            self.assertEqual(final["result"], "PASS", final["failures"])
            self.assertEqual(final["observed"]["hostPrerequisites"],
                             {I.HOST_KEY: "PRESENT_SECURE", I.CREDSTORE: "PRESENT_SECURE"})

    def test_l2b1_creates_credstore_only_when_absent(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as out, fake_wheels() as wheels:
            host = FakeHost(directory)
            system = self.run_ladder_to_l2a(host, wheels, Path(out), adopt_host_key=False)
            report = I.stage_credstore(system, SHA)
            self.assertEqual((report["result"], report["mutation"]), ("PASS", "CREATED"))

    def test_l2b2_requires_both_prerequisites_and_the_complete_ladder(self):  # regression 7
        with tempfile.TemporaryDirectory() as directory:
            host = FakeHost(directory)
            (self.secure_credstore(host) / "lilith-authority-dev.owner-actor.cred").write_bytes(b"x")
            os.chmod(host.root / "etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred", 0o600)
            failures = I.status(host.system(), "L2b.2", SHA)["failures"]
            for needed in ("ACCOUNT_ABSENT", f"MISSING:{I.HOST_KEY}", f"MISSING:{I.OPT}", f"MISSING:{I.KEYGEN_CLI}"):
                self.assertIn(needed, failures)


class ReleaseArchiveTests(unittest.TestCase):
    """Req 8, 9, 15: deterministic, pinned, no custody material."""

    def test_layout_pins(self):
        self.assertEqual(I.RUNTIME_PATHS, frozenset(RFS.RUNTIME_SOURCE_MAP.values()))
        import memory_broker_os_release as BR
        import probe_needrestart_lilith_override as NR
        self.assertEqual(I.WHEEL_HASHES, BR.WHEEL_HASHES)
        self.assertEqual(I.LOCK, BR.LOCK)
        self.assertEqual(I.NEEDRESTART_SHA256, NR.ARTIFACT_SHA256)
        self.assertEqual(I.NEEDRESTART, NR.INSTALL_PATH)
        self.assertEqual((I.SERVICE_USER, I.CREDENTIAL, I.OPT), (PR.SERVICE_USER, PR.CREDENTIAL_SOURCE, PR.RELEASE_ROOT))
        self.assertEqual(I.KEYGEN_CLI, "/usr/local/sbin/lilith-authority-keygen-dev")
        for name in I.EXPECTED_PATHS:
            self.assertIsNone(I.FORBIDDEN_MEMBER.search(name), name)
        for name in ("owner-actor.cred", "etc/credstore.encrypted/x", "key.pem", "k.key", "credential.secret"):
            self.assertIsNotNone(I.FORBIDDEN_MEMBER.search(name), name)

    def test_archive_is_deterministic_and_round_trips(self):
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two, fake_wheels() as wheels:
            a1, s1, raw1 = build_archive(Path(one), wheels)
            _a2, _s2, raw2 = build_archive(Path(two), wheels)
            self.assertEqual(raw1, raw2)
            manifest, payloads = I.verify_archive(a1, s1, SHA)
            self.assertEqual(set(payloads), I.EXPECTED_PATHS)
            self.assertEqual(payloads[I.CLI_PATH], KEYGEN_SOURCE.encode())
            with tarfile.open(fileobj=io.BytesIO(raw1), mode="r:gz") as tar:
                self.assertTrue(all(m.mtime == 0 and m.mode == 0o600 for m in tar))

    def test_tampered_or_custody_bearing_archives_are_refused(self):
        with tempfile.TemporaryDirectory() as out, fake_wheels() as wheels:
            archive, attestation, raw = build_archive(Path(out), wheels)
            with self.assertRaises(I.InstallError):
                I.verify_archive(archive, attestation, "0" * 40)
            payloads = B.build_payloads(ROOT, wheels)
            for extra in ({"credstore/lilith-authority-dev.owner-actor.cred": b"x"},
                          {"lilith_authority_dev/core.py": payloads["lilith_authority_dev/core.py"]
                           + b"\n# -----" + b"BEGIN " + b"PRIVATE" + b" KEY-----\n"}):
                bad = {**payloads, **extra}
                with self.assertRaises(I.InstallError):
                    I.check_payloads(bad)
            archive.write_bytes(raw[:-10] + b"0" * 10)
            with self.assertRaises(I.InstallError):
                I.verify_archive(archive, attestation, SHA)


class BoundaryTests(unittest.TestCase):
    """Req 14, 15, 16: no enablement, no routine packaging, no PROD trigger."""

    def test_units_cannot_be_enabled_at_boot(self):
        for name in ("lilith-authority-dev.service", "lilith-authority-dev.socket"):
            text = (ROOT / "services/authority-dev/deploy" / name).read_text(encoding="utf-8")
            self.assertNotIn("[Install]", text)
            for key in ("WantedBy", "RequiredBy", "UpheldBy", "Alias", "Also"):
                self.assertNotRegex(text, rf"(?m)^{key}=")
        code = code_only(INSTALLER_SOURCE)
        for needle in ('"enable"', '"start"', '"restart"', '"daemon-reload"', "systemd-creds", "systemd-tmpfiles",
                       '"--now"', "Ed25519PrivateKey"):
            self.assertNotIn(needle, code, needle)

    def test_routine_deployment_cannot_package_authority_material(self):
        for path in (ROOT / ".github/workflows/deploy-dev.yml", ROOT / ".github/workflows/deploy.yml",
                     ROOT / "scripts/build_core_api_bundle.py", ROOT / "scripts/deploy_core_api_remote.sh",
                     *sorted(p for p in (ROOT / "scripts/dev_deployer").iterdir() if p.is_file())):
            text = path.read_text(encoding="utf-8")
            for needle in ("authority-dev/ceremony", "authority-keygen", "credstore", "owner-actor",
                           "credential.secret"):
                self.assertNotIn(needle, text, f"{path.name}: {needle}")

    def test_no_prod_trigger(self):
        deploy = (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
        filters = re.findall(r'^\s+- "([^"]+)"', deploy.split("paths:", 1)[1].split("permissions:", 1)[0], re.MULTILINE)
        self.assertTrue(filters)
        new = [p.relative_to(ROOT).as_posix() for p in HERE.iterdir() if p.is_file()] + [
            "services/authority-dev/tests/test_custody_preparation.py",
            "docs/architecture/slice-15b2b-b1b3d-l2-custody-preparation.md"]
        for path in new:
            for pattern in filters:
                self.assertFalse(fnmatch.fnmatch(path, pattern.replace("**", "*")), (path, pattern))
        for text in (KEYGEN_SOURCE, INSTALLER_SOURCE):
            self.assertNotIn("lilith-prod", text)

    def test_dev_classifier_gives_no_special_lane(self):
        import classify_dev_deployment as CL
        for path in ("services/authority-dev/ceremony/install_authority_dev.py",
                     "services/authority-dev/ceremony/lilith_authority_keygen_dev.py"):
            self.assertNotIn(path, CL.CONTROL_ONLY_PATHS)

    @unittest.skipUnless(POSIX, "the installer is Linux-only")
    def test_installer_runs_streamed_from_stdin_without_staging(self):
        # L0 is READ_ONLY only if the tool needs no staged file. Off DEV it must
        # refuse (NOT_ROOT or NOT_DEV_HOST) and leave nothing behind.
        self.assertNotIn("__file__", INSTALLER_SOURCE)
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-I", "-B", "-", "preflight"], input=INSTALLER_SOURCE.encode(),
                                    capture_output=True, cwd=directory, timeout=60)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertRegex(result.stderr.decode(), r"REFUSED (NOT_ROOT|NOT_DEV_HOST)")
            self.assertEqual(os.listdir(directory), [])
        self.assertIn("READ_ONLY OBSERVATION  !=  STAGING  !=  INSTALLATION", RUNBOOK)
        self.assertNotIn("/tmp/b1b3d-l2", RUNBOOK)

    def test_runbook_contract_equals_installer(self):
        rows = re.findall(r"^\| `(/[^`]+)` \| (dir|file|symlink) \| root:root \| (\d{4}|—) \| (L[0-9a-z.]+) \|$",
                          RUNBOOK, re.MULTILINE)
        documented = {path.replace("<SHA>", SHA): (kind, mode, stage) for path, kind, mode, stage in rows}
        final = I.expected_paths("L2b.2", SHA)
        contract = {path: (spec[0], spec[3] or "—") for path, spec in final.items() if spec is not None}
        self.assertEqual({p: v[:2] for p, v in documented.items()}, contract)
        for path, (_kind, _mode, stage) in documented.items():
            required = I.expected_paths(stage, SHA)[path]
            self.assertIsNotNone(required, path)
            self.assertNotIsInstance(required, I.HostPrerequisite, path)
            earlier = I.expected_paths(I.STAGES[I.STAGES.index(stage) - 1], SHA)[path]
            if path in I.HOST_PREREQUISITES:
                # Generic host prerequisite: before its step it may already exist
                # securely (run 36264031829); it is never LILITH maturity.
                self.assertIsInstance(earlier, I.HostPrerequisite, path)
                self.assertEqual(tuple(earlier), required)
            else:
                self.assertIsNone(earlier, path)
        self.assertEqual(set(I.HOST_PREREQUISITES), {I.HOST_KEY, I.CREDSTORE})
        for path in I.DEFERRED_PATHS:
            if "witness.cred" not in path:
                self.assertIn(f"`{path}`", RUNBOOK)
        self.assertIn(f"`{I.NEEDRESTART_SHA256[:6]}…{I.NEEDRESTART_SHA256[-4:]}`", RUNBOOK)


if __name__ == "__main__":
    unittest.main()
