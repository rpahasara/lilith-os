"""15B2b-B1b-3e Source Prep B tests for the successor-capable authority-dev release.

`successor <N>` keygen form, the custody installer stage (L2c), the unit's
custody deny boundary, the single loadable slot, and the release file set.
Everything runs against temporary directories with injected OS lookups.
No test runs `systemd-creds`, calls `Ed25519PrivateKey.generate()`, touches
`/`, or contacts DEV/PROD. SOURCE ONLY: nothing here is installed.
"""

from __future__ import annotations

import base64
import contextlib
import dataclasses
import hashlib
import io
import json
import os
import re
import stat
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "ceremony"
ROOT = HERE.parents[2]
for path in (HERE, ROOT / "scripts", ROOT / "services/authority-dev", ROOT / "services/core-api",
             ROOT / "services/owner-memory-control", Path(__file__).resolve().parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat  # noqa: E402

import install_authority_dev as I  # noqa: E402
import lilith_authority_keygen_dev as G  # noqa: E402
import release_file_set as RFS  # noqa: E402
from lilith_authority_dev import profile as PR  # noqa: E402
from lilith_owner_memory import rotation_contracts as RC  # noqa: E402
from lilith_owner_memory import successor_custody as SC  # noqa: E402
from lilith_owner_memory import witness_readiness as WR  # noqa: E402
from test_custody_preparation import (  # noqa: E402
    PIPELINE_KEY_BYTES, SHA, FakeHost, build_archive, fake_encrypt, fake_wheels, pipeline_key,
)

POSIX = os.name == "posix"
UNIT = (ROOT / "services/authority-dev/deploy/lilith-authority-dev.service").read_text(encoding="utf-8")
KEYGEN_SOURCE = (HERE / "lilith_authority_keygen_dev.py").read_text(encoding="utf-8")
INSTALLER_SOURCE = (HERE / "install_authority_dev.py").read_text(encoding="utf-8")
CURRENT_CIPHERTEXT = b"FAKE-SYSTEMD-CREDS-CIPHERTEXT:initial-current-blob"


class SuccessorFormContractTests(unittest.TestCase):
    def test_fixed_values_match_the_owner_side_contract(self):
        self.assertEqual(G.CREDENTIAL_NAME, PR.CREDENTIAL_NAME)          # RR-11-D2: one runtime name
        self.assertEqual(G.CREDENTIAL_NAME, SC.CREDENTIAL_NAME)
        self.assertEqual(G.CREDENTIAL_PATH, SC.CURRENT_PATH)
        self.assertEqual((G.PREPARED_PATH, G.RETIRED_PATH), (SC.PREPARED_PATH, SC.RETIRED_PATH))
        self.assertEqual((G.CUSTODY_ROOT, G.PREPARED_DIR, G.RETIRED_DIR),
                         (I.CUSTODY_ROOT, I.PREPARED_DIR, I.RETIRED_DIR))
        self.assertEqual(G.KEY_ID, SC.INITIAL_KEY_ID)
        self.assertEqual((G.SUCCESSOR_KEY_ID_PREFIX, G.SUCCESSOR_CEREMONY_ID_PREFIX),
                         (SC.SUCCESSOR_KEY_ID_PREFIX, SC.SUCCESSOR_CEREMONY_ID_PREFIX))
        self.assertEqual((G.SUCCESSOR_ORDINAL_MIN, G.SUCCESSOR_ORDINAL_MAX), (2, 9999))
        self.assertEqual((SC.SUCCESSOR_ORDINAL_MIN, SC.SUCCESSOR_ORDINAL_MAX), (2, 9999))
        self.assertEqual(G.ENCRYPT_ARGV[3], "--name=owner-actor-signing-key")  # never ordinal-specific

    def test_authority_dev_profile_is_dev_synthetic_only(self):
        self.assertEqual((PR.PROFILE, PR.ENVIRONMENT, G.ENVIRONMENT), ("DEV_SYNTHETIC", "dev", "dev"))
        self.assertEqual(SC.DEV_SYNTHETIC_CUSTODY_PROFILE.environment, "dev")
        for environment in ("test", "prod"):
            with self.assertRaises(PR.ProfileError):
                PR.DevSyntheticSignerProfileV1(environment, PR.PROPOSED_K_ACT_KEY_ID, "authority.dev.memory",
                                               "owner.dev-synthetic.v1", "policy.dev-synthetic.v1").validate()
        publication = G.publication(bytes(range(32)), b"c", G.DEV_MACHINE_ID, key_id=G.successor_key_id(2),
                                    credential_path=G.PREPARED_PATH)
        raw = G.canonical(publication)
        record = SC.build_successor_ceremony_record(publication_bytes=raw, reviewed_release_sha=SHA)
        test_profile = SC.custody_profile("test")
        self.assertEqual(SC.verify_successor_ceremony_record(record=record, publication_bytes=raw,
                                                             reviewed_release_sha=SHA, profile=test_profile).reason,
                         "PUBLICATION_PROFILE_MISMATCH")  # a DEV publication never passes a TEST context

    def test_keygen_and_owner_derivations_agree_for_every_ordinal(self):
        seen_keys, seen_ceremonies = set(), set()
        for n in range(G.SUCCESSOR_ORDINAL_MIN, G.SUCCESSOR_ORDINAL_MAX + 1):
            identity = SC.successor_identity(n)
            self.assertEqual((G.successor_key_id(n), G.successor_ceremony_id(n)),
                             (identity.key_id, identity.ceremony_id))
            self.assertEqual(G.successor_ordinal(identity.key_id), n)
            seen_keys.add(identity.key_id)
            seen_ceremonies.add(identity.ceremony_id)
        self.assertEqual(len(seen_keys), len(seen_ceremonies))
        self.assertEqual(len(seen_keys), 9998)
        self.assertNotIn(G.KEY_ID, seen_keys)
        self.assertEqual(G.successor_key_id(2), "test-only.dev-synthetic.actor.b1b3e.2")
        self.assertEqual(G.successor_ceremony_id(2), "dev-synthetic.owner-actor.successor.2")
        for bad in (1, 10000, 0, "2", 2.0, True):
            with self.assertRaises(ValueError):
                G.successor_key_id(bad)

    def test_successor_argv_is_closed(self):
        self.assertEqual(G.parse_argv(["successor", "2"]), G.Form(G.SUCCESSOR, 2))
        self.assertEqual(G.parse_argv(["successor", "9999"]), G.Form(G.SUCCESSOR, 9999))
        self.assertEqual(G.parse_argv(["actor"]), G.Form(G.ACTOR))
        cases = {
            ("successor",): "USAGE_SUCCESSOR_ORDINAL",
            ("successor", "2", "3"): "USAGE_SUCCESSOR_ORDINAL",
            ("successor", "2", "--output", "/tmp/x"): "USAGE_SUCCESSOR_ORDINAL",
            ("successor", "2", "--key-id", "x"): "USAGE_SUCCESSOR_ORDINAL",
            ("successor", "1"): "SUCCESSOR_ORDINAL_OUT_OF_RANGE",
            ("successor", "10000"): "SUCCESSOR_ORDINAL_OUT_OF_RANGE",
            ("successor", "0"): "SUCCESSOR_ORDINAL_INVALID",
            ("successor", "02"): "SUCCESSOR_ORDINAL_INVALID",
            ("successor", "-2"): "SUCCESSOR_ORDINAL_INVALID",
            ("successor", "+2"): "SUCCESSOR_ORDINAL_INVALID",
            ("successor", " 2"): "SUCCESSOR_ORDINAL_INVALID",
            ("successor", "2.0"): "SUCCESSOR_ORDINAL_INVALID",
            ("successor", "0x2"): "SUCCESSOR_ORDINAL_INVALID",
            ("successor", "two"): "SUCCESSOR_ORDINAL_INVALID",
            ("successor", "２"): "SUCCESSOR_ORDINAL_INVALID",  # fullwidth digit
            ("successor", "1" * 17): "SUCCESSOR_ORDINAL_INVALID",
            ("successor", "--force"): "SUCCESSOR_ORDINAL_INVALID",
            ("SUCCESSOR", "2"): "USAGE_ONLY_ACTOR",
            ("actor", "successor", "2"): "USAGE_ONLY_ACTOR",
            ("successor-2",): "USAGE_ONLY_ACTOR",
        }
        for argv, reason in cases.items():
            with self.subTest(argv=argv), self.assertRaises(G.Refused) as caught:
                G.parse_argv(list(argv))
            self.assertEqual(caught.exception.reason, reason, argv)

    def test_malformed_successor_invocation_has_no_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            host = FakeHost(directory)
            err, out = io.StringIO(), io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
                self.assertEqual(G.main(["successor", "1"], host=host.keygen_host()), G.EXIT_REFUSED)
            self.assertIn("REFUSED SUCCESSOR_ORDINAL_OUT_OF_RANGE", err.getvalue())
            self.assertEqual(out.getvalue(), "")
            self.assertFalse((host.root / "etc/lilith-authority-custody").exists())

    def test_publication_identity_is_one_of_two_closed_forms(self):
        public = bytes(range(32))
        for key_id, path in ((G.KEY_ID, G.PREPARED_PATH), (G.successor_key_id(2), G.CREDENTIAL_PATH),
                             (G.successor_key_id(2), G.RETIRED_PATH), ("test-only.dev-synthetic.actor.x", G.PREPARED_PATH)):
            with self.assertRaises(ValueError):
                G.publication(public, b"c", G.DEV_MACHINE_ID, key_id=key_id, credential_path=path)


@unittest.skipUnless(POSIX, "owner and mode semantics are POSIX")
class SuccessorKeygenCeremonyTests(unittest.TestCase):
    """RR-11-D1, RR-26, §7.2-§7.4: preconditions, PREPARED only, CURRENT untouched."""

    def ready(self, directory: str) -> FakeHost:
        host = FakeHost(directory)
        host.systemd_creds_setup()
        for relative in ("etc/credstore.encrypted", "etc/lilith-authority-custody",
                         "etc/lilith-authority-custody/prepared", "etc/lilith-authority-custody/retired"):
            path = host.root / relative
            path.mkdir(mode=0o700)
            os.chmod(path, 0o700)
        current = host.root / G.CREDENTIAL_PATH.lstrip("/")
        current.write_bytes(CURRENT_CIPHERTEXT)
        os.chmod(current, 0o600)
        return host

    def preflight(self, host: FakeHost, ordinal: int = 2, keygen_host: G.Host | None = None, **overrides):
        value = dict(euid=0, isolated=True, hostname="lilith-dev-01")
        value.update(overrides)
        return G.successor_preflight(keygen_host or host.keygen_host(), ordinal, **value)

    def assertRefused(self, host, reason, **overrides):
        with self.assertRaises(G.Refused) as caught:
            self.preflight(host, **overrides)
        self.assertEqual(caught.exception.reason, reason)

    def snapshot(self, host: FakeHost, relative: str) -> tuple:
        path = host.root / relative.lstrip("/")
        meta = os.lstat(path)
        return meta.st_ino, meta.st_dev, meta.st_mode, meta.st_size, meta.st_mtime_ns, path.read_bytes()

    def run_ceremony(self, host: FakeHost, ordinal: int = 2, **kwargs) -> dict:
        machine_id, before = self.preflight(host, ordinal)
        kwargs.setdefault("key_factory", pipeline_key)
        kwargs.setdefault("encrypt", fake_encrypt([]))
        return G.successor_ceremony(host.keygen_host(), machine_id, ordinal, before, **kwargs)

    def test_successor_writes_only_prepared_and_current_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            host = self.ready(directory)
            before = self.snapshot(host, G.CREDENTIAL_PATH)
            seen: list[bytes] = []
            result = self.run_ceremony(host, encrypt=fake_encrypt(seen))
            self.assertEqual(self.snapshot(host, G.CREDENTIAL_PATH), before)
            self.assertEqual(os.listdir(host.root / "etc/lilith-authority-custody/retired"), [])
            self.assertEqual(sorted(os.listdir(host.root / "etc/credstore.encrypted")), [G.SLOT_NAME])
            prepared = host.root / G.PREPARED_PATH.lstrip("/")
            self.assertEqual(sorted(os.listdir(prepared.parent)), [G.SLOT_NAME])
            self.assertEqual(stat.S_IMODE(os.lstat(prepared).st_mode), 0o600)
            self.assertTrue(stat.S_ISREG(os.lstat(prepared).st_mode))
            material, custody = result["publicVerificationMaterial"], result["custodyEvidence"]
            self.assertEqual(material["keyId"], "test-only.dev-synthetic.actor.b1b3e.2")
            self.assertEqual(custody["credentialPath"], G.PREPARED_PATH)
            self.assertEqual(custody["credentialName"], "owner-actor-signing-key")
            self.assertEqual(custody["blobSha256"], hashlib.sha256(prepared.read_bytes()).hexdigest())
            der = pipeline_key().private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
            self.assertEqual(seen, [der])
            printed = G.canonical(result)
            for secret in (der, PIPELINE_KEY_BYTES, base64.urlsafe_b64encode(der).rstrip(b"=")):
                self.assertNotIn(secret, printed)
                for path in host.root.rglob("*"):
                    if path.is_file():
                        self.assertNotIn(secret, path.read_bytes(), path)
            # A rerun never mutates an existing PREPARED successor.
            self.assertRefused(host, "PREPARED_NOT_EMPTY")
            with self.assertRaises(G.Refused):
                self.preflight(host, 3)

    def test_publication_is_the_unchanged_v1_shape_and_binds_a_ceremony_record(self):
        with tempfile.TemporaryDirectory() as directory:
            host = self.ready(directory)
            result = self.run_ceremony(host)
            actor = G.publication(bytes(range(32)), b"x", G.DEV_MACHINE_ID)
            self.assertEqual(set(result), set(actor))
            self.assertEqual(set(result["publicVerificationMaterial"]), set(actor["publicVerificationMaterial"]))
            self.assertEqual(set(result["custodyEvidence"]), set(actor["custodyEvidence"]))
            self.assertEqual(RC.KeyPublicationV1.from_dict(result).key_id, G.successor_key_id(2))
            raw = G.canonical(result)
            self.assertEqual(SC.canonical_publication_bytes(json.loads(raw)), raw)
            record = SC.build_successor_ceremony_record(publication_bytes=raw, reviewed_release_sha=SHA)
            self.assertEqual((record["ceremonyId"], record["successorOrdinal"]), (G.successor_ceremony_id(2), 2))
            observed = hashlib.sha256((host.root / G.PREPARED_PATH.lstrip("/")).read_bytes()).hexdigest()
            verified = SC.verify_successor_ceremony_record(record=record, publication_bytes=raw,
                                                           reviewed_release_sha=SHA,
                                                           observed_prepared_blob_sha256=observed)
            self.assertTrue(verified.verified, verified.reason)
            self.assertIs(verified.facts["authorityGranted"], False)
            other_release = SC.verify_successor_ceremony_record(record=record, publication_bytes=raw,
                                                                reviewed_release_sha="f" * 40)
            self.assertEqual(other_release.reason, "REVIEWED_RELEASE_MISMATCH")
            # The ordinal is burned: an abandoned-and-rerun ordinal 2 is refused by the register.
            register = SC.register_successor_ceremony(SC.empty_ceremony_register(), record).register
            (host.root / G.PREPARED_PATH.lstrip("/")).unlink()  # abandon: destroy PREPARED (NOT_IN_HEAD)
            rerun = self.run_ceremony(host, key_factory=lambda: Ed25519PrivateKey.from_private_bytes(
                bytes(range(1, 33))))
            second = SC.build_successor_ceremony_record(publication_bytes=G.canonical(rerun), reviewed_release_sha=SHA)
            self.assertEqual(SC.register_successor_ceremony(register, second).reason, "ORDINAL_BURNED")
            self.assertEqual(SC.check_ordinal_unburned(register, 2).reason, "ORDINAL_BURNED")
            self.assertTrue(SC.check_ordinal_unburned(register, 3).ok)

    def test_refusal_matrix(self):
        def fresh(mutate):
            directory = tempfile.mkdtemp()
            self.addCleanup(lambda: __import__("shutil").rmtree(directory))
            host = self.ready(directory)
            mutate(host.root)
            return host

        custody = "etc/lilith-authority-custody"
        cases = {
            "custody root absent": (lambda r: [os.rmdir(r / custody / "prepared"), os.rmdir(r / custody / "retired"),
                                               os.rmdir(r / custody)], "CUSTODY_ROOT_ABSENT"),
            "custody root mode": (lambda r: os.chmod(r / custody, 0o755), "CUSTODY_ROOT_CUSTODY"),
            "custody root extra entry": (lambda r: (r / custody / "abandoned").mkdir(), "CUSTODY_ROOT_UNEXPECTED_ENTRY"),
            "prepared replaced by another name": (lambda r: [os.rmdir(r / custody / "prepared"),
                                                             (r / custody / "x").mkdir()],
                                                  "CUSTODY_ROOT_UNEXPECTED_ENTRY"),
            "prepared mode": (lambda r: os.chmod(r / custody / "prepared", 0o755), "PREPARED_CUSTODY"),
            "prepared symlink": (lambda r: [os.rmdir(r / custody / "prepared"),
                                            os.symlink(r / "tmp-target", r / custody / "prepared"),
                                            (r / "tmp-target").mkdir(mode=0o700)], "PREPARED_CUSTODY"),
            "prepared is a file": (lambda r: [os.rmdir(r / custody / "prepared"),
                                              (r / custody / "prepared").write_bytes(b"x")], "PREPARED_CUSTODY"),
            "prepared occupied": (lambda r: (r / custody / "prepared" / G.SLOT_NAME).write_bytes(b"old"),
                                  "PREPARED_NOT_EMPTY"),
            "prepared stale other name": (lambda r: (r / custody / "prepared" / "next.cred").write_bytes(b"old"),
                                          "PREPARED_NOT_EMPTY"),
            "retired occupied": (lambda r: (r / custody / "retired" / G.SLOT_NAME).write_bytes(b"old"),
                                 "RETIRED_NOT_EMPTY"),
            "retired symlink": (lambda r: [os.rmdir(r / custody / "retired"),
                                           os.symlink(r / custody / "prepared", r / custody / "retired")],
                                "RETIRED_CUSTODY"),
            "credstore extra blob": (lambda r: (r / "etc/credstore.encrypted/other.cred").write_bytes(b"x"),
                                     "CREDSTORE_NOT_EXACTLY_CURRENT"),
            "credstore empty": (lambda r: (r / G.CREDENTIAL_PATH.lstrip("/")).unlink(),
                                "CREDSTORE_NOT_EXACTLY_CURRENT"),
            "current mode": (lambda r: os.chmod(r / G.CREDENTIAL_PATH.lstrip("/"), 0o644), "CURRENT_CUSTODY"),
            "current symlink": (lambda r: [(r / G.CREDENTIAL_PATH.lstrip("/")).unlink(),
                                           os.symlink(r / "etc/machine-id", r / G.CREDENTIAL_PATH.lstrip("/"))],
                                "CURRENT_CUSTODY"),
            "credstore mode": (lambda r: os.chmod(r / "etc/credstore.encrypted", 0o755), "CREDSTORE_CUSTODY"),
            "host key custody": (lambda r: os.chmod(r / "var/lib/systemd/credential.secret", 0o600),
                                 "HOST_CREDENTIAL_KEY_CUSTODY"),
            "swap active": (lambda r: (r / "proc/swaps").write_text("Filename\n/swap file 1 0 -2\n", encoding="ascii"),
                            "SWAP_ACTIVE"),
        }
        for name, (mutate, reason) in cases.items():
            with self.subTest(name):
                host = fresh(mutate)
                self.assertRefused(host, reason)
                if name != "prepared occupied":  # nothing generated, nothing written
                    self.assertFalse(os.path.lexists(host.root / G.PREPARED_PATH.lstrip("/")), name)
        with tempfile.TemporaryDirectory() as directory:
            host = self.ready(directory)
            self.assertRefused(host, "NOT_ROOT", euid=1000)
            self.assertRefused(host, "INTERPRETER_NOT_ISOLATED", isolated=False)
            self.assertRefused(host, "NOT_DEV_HOST", hostname="lilith-prod-01")
            prepared = str(host.root / G.PREPARED_DIR.lstrip("/"))
            split = dataclasses.replace(host.keygen_host(), device_of=lambda p: 2 if str(p) == prepared else 1)
            with self.assertRaises(G.Refused) as caught:
                self.preflight(host, keygen_host=split)
            self.assertEqual(caught.exception.reason, "CUSTODY_FILESYSTEM_MISMATCH")
            self.assertEqual(os.listdir(prepared), [])

    def test_current_changed_during_the_ceremony_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            host = self.ready(directory)
            current = host.root / G.CREDENTIAL_PATH.lstrip("/")

            def tamper_encrypt(plaintext: bytes) -> bytes:
                current.write_bytes(b"swapped by an adversary")
                return fake_encrypt([])(plaintext)

            with self.assertRaises(G.Failed) as caught:
                self.run_ceremony(host, encrypt=tamper_encrypt)
            self.assertEqual(caught.exception.reason, "CURRENT_CHANGED")
            self.assertEqual(os.listdir(host.root / G.PREPARED_DIR.lstrip("/")), [])  # nothing was written
        with tempfile.TemporaryDirectory() as directory:
            host = self.ready(directory)
            current = host.root / G.CREDENTIAL_PATH.lstrip("/")
            original = G.write_successor_blob

            def write_then_tamper(*args, **kwargs):
                original(*args, **kwargs)
                os.chmod(current, 0o640)

            G.write_successor_blob = write_then_tamper
            try:
                with self.assertRaises(G.Failed) as caught:
                    self.run_ceremony(host)
            finally:
                G.write_successor_blob = original
            self.assertEqual(caught.exception.reason, "CURRENT_CHANGED")
            # The PREPARED blob is now an abandoned successor: ordinal burned, destroyed, never reused.
            self.assertEqual(os.listdir(host.root / G.PREPARED_DIR.lstrip("/")), [G.SLOT_NAME])

    def test_prepared_swapped_or_filled_after_preflight(self):
        with tempfile.TemporaryDirectory() as directory:
            host = self.ready(directory)
            machine_id, before = self.preflight(host)
            prepared = host.root / G.PREPARED_DIR.lstrip("/")
            os.rmdir(prepared)
            elsewhere = host.root / "elsewhere"
            elsewhere.mkdir(mode=0o700)
            os.symlink(elsewhere, prepared)
            with self.assertRaises(G.Failed) as caught:
                G.successor_ceremony(host.keygen_host(), machine_id, 2, before, key_factory=pipeline_key,
                                     encrypt=fake_encrypt([]))
            self.assertEqual(caught.exception.reason, "PREPARED_CUSTODY")
            self.assertEqual(os.listdir(elsewhere), [])
        with tempfile.TemporaryDirectory() as directory:
            host = self.ready(directory)
            machine_id, before = self.preflight(host)
            (host.root / G.PREPARED_PATH.lstrip("/")).write_bytes(b"raced")
            with self.assertRaises(G.Failed) as caught:
                G.successor_ceremony(host.keygen_host(), machine_id, 2, before, key_factory=pipeline_key,
                                     encrypt=fake_encrypt([]))
            self.assertEqual(caught.exception.reason, "PREPARED_NOT_EMPTY")
            self.assertEqual((host.root / G.PREPARED_PATH.lstrip("/")).read_bytes(), b"raced")  # never mutated

    def test_plaintext_leak_and_bad_factory_fail_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            host = self.ready(directory)
            with self.assertRaises(G.Failed) as caught:
                self.run_ceremony(host, encrypt=lambda plaintext: b"x" + plaintext)
            self.assertEqual(caught.exception.reason, "CIPHERTEXT_CONTAINS_PLAINTEXT")
            with self.assertRaises(G.Failed):
                self.run_ceremony(host, key_factory=lambda: b"k")
            self.assertEqual(os.listdir(host.root / G.PREPARED_DIR.lstrip("/")), [])

    def test_host_key_is_never_read(self):
        with tempfile.TemporaryDirectory() as directory:
            host = self.ready(directory)
            original, touched = os.open, []

            def guard(path, *a, **k):
                if "credential.secret" in str(path):
                    touched.append(str(path))
                return original(path, *a, **k)

            os.open = guard
            try:
                self.run_ceremony(host)
            finally:
                os.open = original
            self.assertEqual(touched, [])

    def test_prepared_blob_feeds_the_owner_custody_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            host = self.ready(directory)
            result = self.run_ceremony(host)
            p_sha = hashlib.sha256(CURRENT_CIPHERTEXT).hexdigest()
            s_sha = result["custodyEvidence"]["blobSha256"]
            ceremony = SC.CustodyCeremonyV1(G.successor_ceremony_id(2), G.KEY_ID, p_sha, G.successor_key_id(2), s_sha)

            def location(role, absolute):
                path = host.root / absolute.lstrip("/")
                meta = os.lstat(path)
                entries = tuple(WR.CredentialFileObservationV1(
                    name, WR.REGULAR, 0, 0, stat.S_IMODE(os.lstat(path / name).st_mode),
                    hashlib.sha256((path / name).read_bytes()).hexdigest()) for name in sorted(os.listdir(path)))
                return WR.CredentialLocationObservationV1(role, WR.DIRECTORY, 0, 0, stat.S_IMODE(meta.st_mode),
                                                          entries), meta.st_dev

            observed = [location(WR.CREDSTORE, G.CREDSTORE), location(WR.PREPARED, G.PREPARED_DIR),
                        location(WR.RETIRED, G.RETIRED_DIR)]
            observation = SC.CustodyObservationV1(
                WR.CredentialInventoryObservationV1(tuple(item[0] for item in observed)),
                {SC.CURRENT: observed[0][1], SC.PREPARED: observed[1][1], SC.RETIRED: observed[2][1]},
                SC.CustodyRootFactsV1(WR.DIRECTORY, 0, 0, 0o700, ("prepared", "retired")), (1, 1))
            self.assertEqual(SC.custody_state(observation, ceremony).state, SC.STATE_A_PREPARED)


class UnitCustodyBoundaryTests(unittest.TestCase):
    """§8, §12, gate SW-2: one loadable slot; PREPARED and RETIRED denied."""

    def directives(self, name: str) -> list[str]:
        return re.findall(rf"(?m)^{name}=(.*)$", UNIT)

    def test_exactly_one_credential_mapping_to_current(self):
        loads = self.directives("LoadCredentialEncrypted")
        self.assertEqual(loads, [f"{SC.CREDENTIAL_NAME}:{SC.CURRENT_PATH}"])
        for other in ("LoadCredential", "SetCredential", "SetCredentialEncrypted", "ImportCredential"):
            self.assertEqual(self.directives(other), [], other)
        self.assertNotIn("*", loads[0])
        self.assertNotRegex(UNIT, r"(?m)^LoadCredentialEncrypted=[^:]+:/etc/credstore\.encrypted/?$")
        self.assertEqual(UNIT.count(SC.CREDENTIAL_NAME), 1)

    def test_custody_directories_are_inaccessible(self):
        denied = self.directives("InaccessiblePaths")
        self.assertEqual(len(denied), 1)
        paths = denied[0].split()
        self.assertIn("/etc/lilith-authority-custody", paths)   # covers prepared/ and retired/
        self.assertIn("/etc/credstore.encrypted", paths)
        for line in self.directives("ReadOnlyPaths") + self.directives("ReadWritePaths") + \
                self.directives("BindReadOnlyPaths") + self.directives("BindPaths"):
            self.assertNotIn("lilith-authority-custody", line)
        self.assertNotIn(SC.PREPARED_PATH, UNIT)
        self.assertNotIn(SC.RETIRED_PATH, UNIT)
        # PR-1S: the credential custody root and the separate hold root (RR-34), each denied once.
        self.assertEqual(UNIT.count("/etc/lilith-authority-custody"), 1)
        self.assertEqual(UNIT.count("/var/lib/lilith-authority-custody"), 1)
        self.assertIn("/var/lib/lilith-authority-custody", paths)
        self.assertIn("/etc/lilith-recovery-witness", paths)  # RR-36: the K-WIT credential root

    def test_prep_a_unit_binding_contract_still_matches(self):
        contract = WR.DEV_SYNTHETIC_SLOT_CONTRACT
        name, source = self.directives("LoadCredentialEncrypted")[0].split(":", 1)
        self.assertEqual((name, source), (contract.credential_name, contract.current_slot_path))
        self.assertEqual(PR.CREDENTIAL_SOURCE, source)
        self.assertEqual(PR.CREDENTIALS_DIRECTORY, "/run/credentials/lilith-authority-dev.service")

    def test_signer_still_requires_its_one_credential(self):
        server = (ROOT / "services/authority-dev/lilith_authority_dev/server.py").read_text(encoding="utf-8")
        credential = (ROOT / "services/authority-dev/lilith_authority_dev/credential.py").read_text(encoding="utf-8")
        self.assertIn("CREDENTIAL_ABSENT", server)
        self.assertIn("CREDENTIAL_NAME", credential)
        for source in (server, credential):
            self.assertNotIn("prepared", source.lower())
            self.assertNotIn("retired", source.lower())
            self.assertNotIn("successor", source.lower())


@unittest.skipUnless(POSIX, "owner and mode semantics are POSIX")
class InstallerCustodyStageTests(unittest.TestCase):
    """RR-25, RR-26: the L2c custody stage and the single installed release."""

    def ladder(self, directory: str, out: Path, wheels: Path) -> tuple[FakeHost, I.System]:
        host = FakeHost(directory)
        system = host.system()
        archive, attestation, _ = build_archive(out, wheels)
        I.stage_accounts(system)
        I.stage_release(system, SHA, archive, attestation)
        I.stage_select(system, SHA)
        I.stage_units(system, SHA)
        host.daemon_reload()
        I.stage_cli(system, SHA)
        host.systemd_creds_setup()
        I.stage_credstore(system, SHA)
        G.ceremony(host.keygen_host(), I.DEV_MACHINE_ID, key_factory=pipeline_key, encrypt=fake_encrypt([]))
        self.assertEqual(I.status(system, "L2b.2", SHA)["result"], "PASS")
        return host, system

    def test_custody_stage_creates_empty_root_only_directories(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as out, fake_wheels() as wheels:
            host, system = self.ladder(d, Path(out), wheels)
            self.assertIn(f"MISSING:{I.CUSTODY_ROOT}", I.status(system, "L2c", SHA)["failures"])
            report = I.stage_custody(system, SHA)
            self.assertEqual(report["result"], "PASS", report["failures"])
            for directory in I.CUSTODY_DIRS:
                meta = os.lstat(host.root / directory.lstrip("/"))
                self.assertTrue(stat.S_ISDIR(meta.st_mode))
                self.assertEqual(stat.S_IMODE(meta.st_mode), 0o700)
            self.assertEqual(os.listdir(host.root / I.PREPARED_DIR.lstrip("/")), [])
            self.assertEqual(os.listdir(host.root / I.RETIRED_DIR.lstrip("/")), [])
            # The credential blob was never touched; the earlier POST no longer matches (collision guard).
            self.assertEqual(report["observed"]["credentialBlobSha256"],
                             I.status(system, "L2c", SHA)["observed"]["credentialBlobSha256"])
            self.assertIn(f"UNEXPECTED_PRESENT:{I.CUSTODY_ROOT}", I.status(system, "L2b.2", SHA)["failures"])
            with self.assertRaises(I.InstallError):
                I.stage_custody(system, SHA)  # never corrects existing state
            # The successor keygen preflight accepts exactly this state.
            machine_id, _before = G.successor_preflight(host.keygen_host(), 2, euid=0, isolated=True,
                                                        hostname="lilith-dev-01")
            self.assertEqual(machine_id, I.DEV_MACHINE_ID)
            names = {Path(call[0]).name for call in host.calls}
            self.assertNotIn("systemd-creds", names)

    def test_custody_post_facts(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as out, fake_wheels() as wheels:
            host, system = self.ladder(d, Path(out), wheels)
            I.stage_custody(system, SHA)
            (host.root / I.PREPARED_DIR.lstrip("/") / "stale.cred").write_bytes(b"x")
            self.assertIn(f"CUSTODY_NOT_EMPTY:{I.PREPARED_DIR}", I.status(system, "L2c", SHA)["failures"])
            (host.root / I.PREPARED_DIR.lstrip("/") / "stale.cred").unlink()
            (host.root / I.CUSTODY_ROOT.lstrip("/") / "abandoned").mkdir(mode=0o700)
            self.assertIn("CUSTODY_ROOT_UNEXPECTED_ENTRY", I.status(system, "L2c", SHA)["failures"])
            os.rmdir(host.root / I.CUSTODY_ROOT.lstrip("/") / "abandoned")
            os.chmod(host.root / I.RETIRED_DIR.lstrip("/"), 0o755)
            self.assertIn(f"CONTRACT:{I.RETIRED_DIR}", I.status(system, "L2c", SHA)["failures"])

    def test_stage_is_refused_off_the_ladder_and_via_main(self):
        with tempfile.TemporaryDirectory() as d:
            host = FakeHost(d)
            with self.assertRaises(I.InstallError):
                I.stage_custody(host.system(), SHA)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(I.main(["custody", SHA], host.system()), 2)
                self.assertEqual(I.main(["custody"], host.system()), 2)
            self.assertIn("REFUSED", err.getvalue())
            self.assertFalse((host.root / I.CUSTODY_ROOT.lstrip("/")).exists())

    def test_release_set_is_the_single_installed_release_contract(self):
        self.assertIn("RR-25", INSTALLER_SOURCE)
        self.assertIn("exactly\n            # one executable release", INSTALLER_SOURCE)
        self.assertIn("Release rollback != authority rollback", INSTALLER_SOURCE)
        self.assertEqual(INSTALLER_SOURCE.count('failures.append("RELEASE_SET")'), 1)
        # PR-1S: the B1b-3d ladder ends L2b.2 -> L2c; only PR-1 phase contracts follow.
        self.assertEqual(I.STAGES[I.STAGES.index("L2b.2"):I.STAGES.index("L2c") + 1], ("L2b.2", "L2c"))
        self.assertTrue(all(stage.startswith(("P1A-", "P1B-")) for stage in I.STAGES[I.STAGES.index("L2c") + 1:]))
        code = "\n".join(line for line in INSTALLER_SOURCE.splitlines() if not line.lstrip().startswith("#"))
        for needle in ('"enable"', '"start"', '"daemon-reload"', "Ed25519PrivateKey", "os.rename(system.path(CREDENTIAL",
                       "unlink"):
            self.assertNotIn(needle, code, needle)


class ReleaseFileSetTests(unittest.TestCase):
    """§13, §38: the successor-capable release is one closed, pinned file set."""

    def test_file_set_and_payload(self):
        RFS.check_source_tree(ROOT)
        self.assertIn("services/authority-dev/tests/test_successor_custody.py", RFS.SOURCE_FILES)
        payloads = RFS.runtime_payloads(ROOT)
        self.assertEqual(payloads["assets/lilith-authority-dev.service"], UNIT.encode())
        self.assertNotIn("cli/lilith-authority-keygen-dev", payloads)  # the keygen is a separate CLI member
        with fake_wheels() as wheels:
            import build_authority_dev_release as BUILD
            release = BUILD.build_payloads(ROOT, wheels)
        self.assertEqual(release[I.CLI_PATH], KEYGEN_SOURCE.encode())
        self.assertEqual(set(release), I.EXPECTED_PATHS)
        for marker in (b".generate()", b"Ed25519PrivateKey.generate", b"lilith_owner_memory.successor"):
            for name, data in payloads.items():
                self.assertNotIn(marker, data, name)
        # PR-1S (S-10): the C-4 gate is wired into the signer ONLY through `recovery.py`, which imports no minter.
        wired = [name for name, data in payloads.items() if name.startswith("lilith_authority_dev/")
                 and b"successor_readiness" in data]
        self.assertEqual(wired, ["lilith_authority_dev/recovery.py"])
        self.assertNotIn(b"evidence_minter", payloads["lilith_authority_dev/recovery.py"])

    def test_source_release_identity_is_deterministic(self):
        first, second = source_release_identity(), source_release_identity()
        self.assertEqual(first, second)
        self.assertEqual(set(first), {"runtimeManifestSha256", "keygenCliSha256", "unitSha256"})


def source_release_identity() -> dict[str, str]:
    """The SOURCE identity of the successor-capable release (not installed)."""
    manifest = RFS.runtime_manifest(ROOT)
    return {
        "runtimeManifestSha256": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
        "keygenCliSha256": hashlib.sha256(KEYGEN_SOURCE.encode()).hexdigest(),
        "unitSha256": hashlib.sha256(UNIT.encode()).hexdigest(),
    }


if __name__ == "__main__":
    unittest.main()
