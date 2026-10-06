"""15B2b-B1b-3e M-B3: the SIGN_REGISTRY_V1 ceremony package (library, builder, S25 script, laptop verifier) (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-mb3-registry-ceremony-package.md.

Nothing here runs on the phone, contacts anything, or creates a real registry.
Every key is a throwaway TEST key in a temporary directory, under a TEST
passphrase; the "accepted" identities in these tests are those TEST keys.
Failure messages redact every 64-hex value (burned-identity rule).
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "services/owner-memory-control/tools"
OWNER_TOOL = ROOT / "services/authority-dev/ceremony/lilith_authority_owner_dev.py"
KEYGEN = ROOT / "services/authority-dev/ceremony/lilith_authority_keygen_dev.py"
for _p in (ROOT / "services/core-api", ROOT / "services/owner-memory-control"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

HAVE_CRYPTO = all(importlib.util.find_spec(m) is not None for m in ("cryptography", "rfc8785", "fido2"))
TEST_PASSPHRASE = "TEST_ONLY m-b3 package passphrase 42"
REAL_E21 = "cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf"
REAL_KWIT = "5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf"
REAL_KWIT_BLOB = "f87593701ee5e9272363a473a115b87cc06179df3c0b233af4aa62bb5b9b97be"
REAL_KWIT_PUBLICATION = "9e9dd0787b3d6df8d40730c6abab728cacbe5136269ca4421160da830bb23472"
REAL_KACT = "dd13a1fb302375a4e7ec81131a72920e23e365e06a0b6dc9bb7ab124dadc01ed"
REAL_KACT_BLOB = "6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _r(text: str) -> str:
    return re.sub(r"[0-9a-f]{64}", "<redacted>", str(text))


class RedactedFailures:
    def _formatMessage(self, msg, standardMsg):
        return _r(super()._formatMessage(msg, standardMsg))


if HAVE_CRYPTO:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    L = _load("mb3_registry_ceremony_t", TOOLS / "mb3_registry_ceremony.py")
    PHONE = _load("mb3_phone_ceremony_t", TOOLS / "mb3_phone_ceremony.py")
    BUILD = _load("build_mb3_registry_bundle_t", TOOLS / "build_mb3_registry_bundle.py")
    OWNER = _load("mb3_test_owner_tool", OWNER_TOOL)
    KG = _load("mb3_test_keygen", KEYGEN)
    from lilith_owner_memory import authority_contracts as A
    from lilith_owner_memory import burned_identities as BI
    from lilith_owner_memory import pr1_bootstrap as B
    from lilith_owner_memory import successor_custody as SC


def _raw(key) -> bytes:
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


class World:
    """TEST K-ROOT (encrypted file), TEST K-ACT and K-WIT publications, and matching TEST 'accepted' identities."""

    def __init__(self, directory: Path):
        self.dir = directory
        self.key_path = directory / "k-root.der"
        out = OWNER.root_keygen(self.key_path, passphrase=TEST_PASSPHRASE.encode())
        self.root_raw = L.canonical_bytes(out)
        kact = Ed25519PrivateKey.generate()
        kwit = Ed25519PrivateKey.generate()
        self.kact_raw = SC.canonical_publication_bytes(
            KG.publication(_raw(kact), b"TEST-ONLY kact ciphertext", "0" * 32))
        self.kwit_raw = SC.canonical_publication_bytes(
            B.witness_publication(_raw(kwit), b"TEST-ONLY kwit ciphertext", "0" * 32))
        kact_value = json.loads(self.kact_raw)
        kwit_value = json.loads(self.kwit_raw)
        self.accepted = L.AcceptedIdentitiesV1(
            kroot_public_key_sha256=out["publicKeySha256"],
            kwit_public_key_sha256=kwit_value["witnessKey"]["publicKeySha256"],
            kwit_key_id=kwit_value["witnessKey"]["witnessKeyId"],
            kwit_blob_sha256=kwit_value["custodyEvidence"]["blobSha256"],
            kwit_publication_sha256=hashlib.sha256(self.kwit_raw).hexdigest(),
            kact_key_id=kact_value["publicVerificationMaterial"]["keyId"],
            kact_public_key_sha256=kact_value["publicVerificationMaterial"]["publicKeySha256"],
            kact_blob_sha256=kact_value["custodyEvidence"]["blobSha256"])
        self.kact_sha = hashlib.sha256(self.kact_raw).hexdigest()

    def root_key(self):
        return OWNER._root_key(self.key_path, TEST_PASSPHRASE.encode())

    def parsed(self):
        _, root = L.verify_root_anchor_bytes(self.root_raw, self.accepted)
        kact_value, kact = L.verify_kact_publication_bytes(self.kact_raw, self.kact_sha, self.accepted)
        kwit_value, kwit = L.verify_kwit_publication_bytes(self.kwit_raw, self.accepted)
        return root, kact_value, kact, kwit_value, kwit


EPOCH = "0123456789abcdef0123456789abcdef"
ISSUED = "2026-10-06T12:00:00Z"


def _manifest_for(world: World, candidate, *, control="a" * 40, bundle="b" * 64, script="c" * 64):
    root, kact_value, kact, kwit_value, kwit = world.parsed()
    anchor_raw = L.canonical_bytes(L.witness_anchor(kwit))
    tokens = L.presign_tokens(candidate, root=root, kact_value=kact_value, kact=kact, kwit_value=kwit_value,
                              kwit=kwit, epoch_random=EPOCH, policy_version=L.POLICY_VERSION, issued_at=ISSUED)
    return L.build_manifest(
        control_sha=control, bundle_sha256=bundle, source_commit=control, script_sha256=script,
        accepted=world.accepted, root_anchor_sha256=hashlib.sha256(world.root_raw).hexdigest(),
        kact_publication_sha256=world.kact_sha, kact=kact,
        kwit_publication_sha256=hashlib.sha256(world.kwit_raw).hexdigest(),
        witness_anchor_sha256=hashlib.sha256(anchor_raw).hexdigest(), epoch_random=EPOCH, issued_at=ISSUED,
        candidate=candidate,
        input_files={"kact-publication.json": world.kact_sha,
                     "kwit-publication.json": hashlib.sha256(world.kwit_raw).hexdigest(),
                     "root-anchor.json": hashlib.sha256(world.root_raw).hexdigest(),
                     "witness-anchor.json": hashlib.sha256(anchor_raw).hexdigest()},
        presign=tokens)


@unittest.skipUnless(HAVE_CRYPTO, "cryptography, rfc8785 and fido2 are required")
class LibraryTests(RedactedFailures, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.world = World(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def candidate(self):
        return L.capture_candidate(OWNER.registry_v1, json.loads(self.world.kact_raw), epoch_random=EPOCH,
                                   policy_version=L.POLICY_VERSION, issued_at=ISSUED)

    def signed(self):
        return OWNER.registry_v1(self.world.root_key(), json.loads(self.world.kact_raw), epoch_random=EPOCH,
                                 policy_version=L.POLICY_VERSION, issued_at=ISSUED)

    def test_accepted_model_and_real_identities(self):
        self.assertEqual(L.CONTINUITY, "OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_ATTEMPT_OFFHOST")
        self.assertEqual(L.POLICY_VERSION, "policy.dev-synthetic.v1")
        self.assertEqual(L.ROOT_KEY_ID, "test-only.registry-root.dev-synthetic.b1b3d.1")
        self.assertEqual((L.E0_COUNTER, L.REGISTRY_VERSION, L.TERMINAL_STATE), (1, 1, "REGISTRY_SIGNED"))
        a = L.ACCEPTED
        self.assertEqual((a.kroot_public_key_sha256, a.kwit_public_key_sha256, a.kwit_blob_sha256,
                          a.kwit_publication_sha256, a.kact_public_key_sha256, a.kact_blob_sha256),
                         (REAL_E21, REAL_KWIT, REAL_KWIT_BLOB, REAL_KWIT_PUBLICATION, REAL_KACT, REAL_KACT_BLOB))
        self.assertEqual(a.kwit_key_id, "test-only.witness.dev-synthetic.b1b3d.1")
        self.assertEqual(a.kact_key_id, SC.INITIAL_KEY_ID)
        self.assertEqual(L.S25_KEY_PATH, "~/lilith-kroot-dev-synthetic/k-root.der")
        self.assertEqual(L.OWNER_TOOL, "services/authority-dev/ceremony/lilith_authority_owner_dev.py")
        every = BI.BURNED_PUBLIC_KEY_SHA256 | BI.BURNED_REGISTRY_DIGESTS | BI.BURNED_GENESIS_WITNESS_DIGESTS
        self.assertTrue({REAL_E21, REAL_KWIT, REAL_KACT}.isdisjoint(every))

    def test_epoch_random_is_token_hex_16_once(self):
        calls = []

        def token_hex(n):
            calls.append(n)
            return "f" * 32
        self.assertEqual(L.new_epoch_random(token_hex), "f" * 32)
        self.assertEqual(calls, [16])
        for bad in ("F" * 32, "f" * 31, "f" * 64, 5):
            with self.assertRaises(L.Mb3Refusal):
                L.new_epoch_random(lambda n, b=bad: b)
        self.assertRegex(L.new_epoch_random(), r"^[0-9a-f]{32}$")

    def test_issued_at_is_utc_second_resolution(self):
        moment = datetime(2026, 10, 6, 9, 8, 7, 654321, tzinfo=timezone.utc)
        self.assertEqual(L.new_issued_at(lambda: moment), "2026-10-06T09:08:07Z")
        with self.assertRaises(L.Mb3Refusal):
            L.new_issued_at(lambda: datetime(2026, 10, 6, 9, 8, 7))
        with self.assertRaises(L.Mb3Refusal):
            L.new_issued_at(lambda: datetime(2026, 10, 6, 9, 8, 7, tzinfo=timezone(timedelta(hours=5))))

    def test_capture_equals_the_real_signed_bytes_and_digest_is_frozen_first(self):
        candidate = self.candidate()
        signed = self.signed()
        self.assertEqual({k: v for k, v in signed.items() if k != "signature"}, dict(candidate.unsigned))
        root = Ed25519PublicKey.from_public_bytes(_raw(self.world.root_key()))
        root.verify(base64_decode(signed["signature"]), candidate.signing_bytes)   # the frozen bytes are what K-ROOT signs
        self.assertEqual(L.RC.registry_digest(signed), candidate.registry_digest)
        self.assertEqual(hashlib.sha256(candidate.signing_bytes).hexdigest(), candidate.registry_digest)
        self.assertTrue(candidate.signing_bytes.startswith(b"LILITH_AUTHORITY_REGISTRY_V1\x00"))

    def test_capture_signer_has_no_key_and_signs_once(self):
        capture = L.CaptureSigner()
        self.assertEqual(capture.sign(b"x"), bytes(64))
        with self.assertRaises(L.Mb3Refusal):
            capture.sign(b"y")
        self.assertFalse(any(hasattr(capture, n) for n in ("private_bytes", "public_key", "key")))

    def test_expected_kact_record_equals_owner_tool_record(self):
        _, _, kact, _, _ = self.world.parsed()
        self.assertEqual(self.signed()["keys"], [L.expected_kact_record(kact, epoch_random=EPOCH,
                                                                         policy_version=L.POLICY_VERSION,
                                                                         issued_at=ISSUED)])
        registry = dict(self.signed())
        registry["keys"] = [dict(registry["keys"][0], createdAt="2026-10-06T11:00:00Z")]
        self.assertEqual(L.kact_record_reason(registry, kact, epoch_random=EPOCH, policy_version=L.POLICY_VERSION,
                                              issued_at=ISSUED), "KACT_RECORD_NOT_PUBLICATION")

    def test_presign_tokens(self):
        root, kact_value, kact, kwit_value, kwit = self.world.parsed()
        tokens = L.presign_tokens(self.candidate(), root=root, kact_value=kact_value, kact=kact,
                                  kwit_value=kwit_value, kwit=kwit, epoch_random=EPOCH,
                                  policy_version=L.POLICY_VERSION, issued_at=ISSUED)
        for token in ("REGISTRY_FIELDS_EXACT", "REGISTRY_SCHEMA_VALID", "SINGLE_CURRENT_KACT",
                      "KACT_RECORD_EQUALS_PUBLICATION", "KACT_FINGERPRINT_RECOMPUTED", "KWIT_NOT_IN_REGISTRY",
                      "KWIT_KACT_KROOT_DISTINCT", "NOT_A_BURNED_IDENTITY", "NOT_A_KNOWN_REAL_REGISTRY_BURN",
                      "EXPECTED_DIGEST_FROZEN_BEFORE_SIGNING"):
            self.assertIn(token, tokens)
        with self.assertRaises(L.Mb3Refusal) as caught:
            L.presign_tokens(self.candidate(), root=root, kact_value=kact_value, kact=kact, kwit_value=kwit_value,
                             kwit=kwit, epoch_random=EPOCH, policy_version="policy.other", issued_at=ISSUED)
        self.assertEqual(caught.exception.code, "POLICY_VERSION_NOT_ACCEPTED")

    def test_kact_publication_fingerprint_is_recomputed_and_pinned(self):
        with self.assertRaises(L.Mb3Refusal) as caught:
            L.verify_kact_publication_bytes(self.world.kact_raw, "0" * 64, self.world.accepted)
        self.assertEqual(caught.exception.code, "KACT_PUBLICATION_SHA256_MISMATCH")
        value = json.loads(self.world.kact_raw)
        value["publicVerificationMaterial"]["publicKey"] = L._b64u(_raw(Ed25519PrivateKey.generate()))
        forged = SC.canonical_publication_bytes(value)          # the publicKeySha256 field still claims the accepted key
        with self.assertRaises(L.Mb3Refusal) as caught:
            L.verify_kact_publication_bytes(forged, hashlib.sha256(forged).hexdigest(), self.world.accepted)
        self.assertEqual(caught.exception.code, "KACT_PUBLICATION_FINGERPRINT_INVALID")
        with self.assertRaises(L.Mb3Refusal) as caught:      # the real accepted K-ACT is not this TEST key
            L.verify_kact_publication_bytes(self.world.kact_raw, self.world.kact_sha, L.ACCEPTED)
        self.assertEqual(caught.exception.code, "KACT_FINGERPRINT_NOT_ACCEPTED")
        with self.assertRaises(L.Mb3Refusal) as caught:
            L.verify_kact_publication_bytes(self.world.kact_raw.rstrip(b"\n") + b" \n",
                                            hashlib.sha256(self.world.kact_raw.rstrip(b"\n") + b" \n").hexdigest(),
                                            self.world.accepted)
        self.assertEqual(caught.exception.code, "KACT_PUBLICATION_MALFORMED")

    def test_exact_kroot_and_kwit_identities(self):
        with self.assertRaises(L.Mb3Refusal) as caught:
            L.verify_root_anchor_bytes(self.world.root_raw)              # real E-21 expected
        self.assertEqual(caught.exception.code, "ROOT_FINGERPRINT_NOT_E21")
        with self.assertRaises(L.Mb3Refusal) as caught:
            L.verify_kwit_publication_bytes(self.world.kwit_raw)          # real K-WIT publication expected
        self.assertEqual(caught.exception.code, "KWIT_PUBLICATION_SHA256_MISMATCH")
        accepted = L.AcceptedIdentitiesV1(**{**self.world.accepted.__dict__, "kwit_key_id": "test-only.other"})
        with self.assertRaises(L.Mb3Refusal) as caught:
            L.verify_kwit_publication_bytes(self.world.kwit_raw, accepted)
        self.assertEqual(caught.exception.code, "KWIT_KEY_ID_NOT_ACCEPTED")

    def verify(self, registry_raw, manifest, **kw):
        return L.verify_signed_registry(registry_raw=registry_raw, manifest_raw=L.canonical_bytes(manifest),
                                        root_anchor_raw=self.world.root_raw, kact_raw=self.world.kact_raw,
                                        kwit_raw=self.world.kwit_raw, accepted=self.world.accepted,
                                        registry_v1=OWNER.registry_v1, **kw)

    def test_verification_passes_on_the_real_signature(self):
        manifest = _manifest_for(self.world, self.candidate())
        result = self.verify(L.canonical_bytes(self.signed()), manifest)
        self.assertTrue(result.verified, result.reason)
        for token in ("MANIFEST_VALID_NON_AUTHORITATIVE", "ROOT_FINGERPRINT_E21", "KACT_PUBLICATION_PINNED_AND_RECOMPUTED",
                      "KWIT_PUBLICATION_ACCEPTED", "REGISTRY_BYTES_CANONICAL", "SIGNING_BYTES_AND_DIGEST_EXPECTED",
                      "KROOT_SIGNATURE_VERIFIED", "SINGLE_CURRENT_KACT", "KACT_RECORD_EQUALS_PUBLICATION",
                      "KWIT_NOT_IN_REGISTRY", "KWIT_KACT_KROOT_DISTINCT", "NOT_A_BURNED_IDENTITY",
                      "OWNER_TOOL_RECONSTRUCTION_EQUAL"):
            self.assertIn(token, result.tokens)
        self.assertEqual(result.registry_digest, manifest["expectedRegistryDigest"])

    def test_verification_refuses_tampering(self):
        manifest = _manifest_for(self.world, self.candidate())
        good = self.signed()
        bad_sig = dict(good, signature=L._b64u(bytes(64)))
        self.assertEqual(self.verify(L.canonical_bytes(bad_sig), manifest).reason,
                         "KROOT_SIGNATURE_REGISTRY_SIGNATURE_INVALID")
        other = OWNER.registry_v1(Ed25519PrivateKey.generate(), json.loads(self.world.kact_raw), epoch_random=EPOCH,
                                  policy_version=L.POLICY_VERSION, issued_at=ISSUED)
        self.assertEqual(self.verify(L.canonical_bytes(other), manifest).reason,
                         "KROOT_SIGNATURE_REGISTRY_SIGNATURE_INVALID")
        later = OWNER.registry_v1(self.world.root_key(), json.loads(self.world.kact_raw), epoch_random=EPOCH,
                                  policy_version=L.POLICY_VERSION, issued_at="2026-10-06T12:00:01Z")
        self.assertEqual(self.verify(L.canonical_bytes(later), manifest).reason, "REGISTRY_DIGEST_NOT_EXPECTED")
        pretty = json.dumps(good, indent=1).encode()
        self.assertEqual(self.verify(pretty, manifest).reason, "REGISTRY_NOT_CANONICAL")
        burns = [L.known_real_registry_burn(registry_digest=manifest["expectedRegistryDigest"],
                                            digest_source="SIGNED_OUTPUT", case="C_OWNER_REJECTED",
                                            control_sha="a" * 40, manifest_sha256="d" * 64,
                                            recorded_at="2026-10-06T12:00:00Z")]
        self.assertEqual(self.verify(L.canonical_bytes(good), manifest, real_registry_burns=burns).reason,
                         "KNOWN_REAL_REGISTRY_BURN")

    def test_kwit_in_registry_is_refused(self):
        _, _, _, kwit_value, kwit = self.world.parsed()
        signed = self.signed()
        record = dict(signed["keys"][0], keyId="test-only.zz", publicKey=kwit_value["witnessKey"]["publicKey"],
                      retiredAt=ISSUED)
        unsigned = {k: v for k, v in signed.items() if k != "signature"}
        unsigned["keys"] = signed["keys"] + [record]
        registry = dict(unsigned, signature=L._b64u(self.world.root_key().sign(A.registry_signing_bytes(unsigned))))
        root, kact_value, kact, kwit_value, kwit = self.world.parsed()
        with self.assertRaises(L.Mb3Refusal) as caught:
            L._structure_tokens(registry, "e" * 64, root=root, kact_value=kact_value, kact=kact, kwit_value=kwit_value,
                                kwit=kwit, epoch_random=EPOCH, policy_version=L.POLICY_VERSION, issued_at=ISSUED,
                                real_registry_burns=())
        self.assertEqual(caught.exception.code, "REGISTRY_KEY_COUNT")
        self.assertEqual(B.witness_distinctness_reason(witness_publication=kwit_value, actor_publication=kact_value,
                                                       registry=registry, registry_root=root,
                                                       anchor=L.witness_anchor(kwit)), "WITNESS_KEY_IN_REGISTRY")

    def test_manifest_is_public_and_non_authoritative(self):
        manifest = _manifest_for(self.world, self.candidate())
        self.assertIs(manifest["authoritative"], False)
        self.assertEqual(manifest["authorizes"], "NOTHING")
        self.assertEqual(manifest["continuity"], L.CONTINUITY)
        self.assertEqual(manifest["signerCommand"]["argv"][:3],
                         ["registry-v1", "~/lilith-kroot-dev-synthetic/k-root.der",
                          "~/lilith-mb3/inputs/kact-publication.json"])
        self.assertEqual(manifest["signerCommand"]["invocations"], 1)
        self.assertIs(manifest["signerCommand"]["automaticRetry"], False)
        text = json.dumps(manifest).lower()
        self.assertNotIn(TEST_PASSPHRASE.lower(), text)
        for forbidden in ("private", "pkcs8", "-----begin"):
            self.assertNotIn(forbidden, text)
        for name, value in (("authoritative", True), ("authorizes", "M-B3"), ("policyVersion", "x"),
                            ("registryVersion", 2)):
            with self.assertRaises(L.Mb3Refusal):
                L.parse_manifest(L.canonical_bytes(dict(manifest, **{name: value})), self.world.accepted)
        self.assertNotIn("manifestSha256", manifest)                       # a document never names its own hash

    def test_classify_signer_exit(self):
        self.assertEqual(L.classify_signer_exit(exit_code=2, stdout=b"",
                                                stderr=b"lilith_authority_owner_dev: REFUSED bad\n"), L.OUTCOME_A)
        self.assertEqual(L.classify_signer_exit(exit_code=0, stdout=b"{}\n", stderr=b""), L.OUTCOME_B)
        for code, out, err in ((1, b"", b"Traceback ...\n"), (2, b"{", b"lilith_authority_owner_dev: REFUSED x\n"),
                               (-2, b"", b""), (None, b"", b""), (2, b"", b"warning\nlilith_authority_owner_dev: REFUSED x\n")):
            self.assertEqual(L.classify_signer_exit(exit_code=code, stdout=out, stderr=err), L.OUTCOME_D)

    def test_wrong_passphrase_is_outcome_a(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = OWNER.main(["registry-v1", str(self.world.key_path), str(self._kact_file()), EPOCH,
                               L.POLICY_VERSION, ISSUED], passphrase=lambda: b"TEST_ONLY wrong passphrase")
        self.assertEqual(L.classify_signer_exit(exit_code=code, stdout=out.getvalue().encode(),
                                                stderr=err.getvalue().encode()), L.OUTCOME_A)

    def _kact_file(self) -> Path:
        path = self.world.dir / "kact.json"
        if not path.exists():
            path.write_bytes(self.world.kact_raw)
        return path


def base64_decode(text: str) -> bytes:
    import base64
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


@unittest.skipUnless(HAVE_CRYPTO, "cryptography, rfc8785 and fido2 are required")
class BurnTests(unittest.TestCase):
    def known(self, digest="1" * 64, case="C_VERIFICATION_FAILED"):
        return L.known_real_registry_burn(registry_digest=digest, digest_source="SIGNED_OUTPUT", case=case,
                                          control_sha="a" * 40, manifest_sha256="b" * 64,
                                          recorded_at="2026-10-06T12:00:00Z")

    def test_known_burn(self):
        entry = self.known()
        self.assertEqual((entry["status"], entry["neverInstall"], entry["neverResign"]),
                         ("PERMANENTLY_BURNED", True, True))
        frozen = L.known_real_registry_burn(registry_digest="2" * 64, digest_source="PRE_SIGN_FROZEN_MANIFEST",
                                            case="D_OUTPUT_LOST_OR_UNCERTAIN", control_sha="a" * 40,
                                            manifest_sha256="b" * 64, recorded_at="2026-10-06T12:00:00Z")
        self.assertEqual(frozen["digestSource"], "PRE_SIGN_FROZEN_MANIFEST")
        for bad in (dict(entry, neverInstall=False), dict(entry, registryDigest="UNKNOWN"), dict(entry, case="X")):
            with self.assertRaises(L.Mb3Refusal):
                L.validate_burn_entry(bad)

    def test_unknown_tombstone_never_invents_a_digest(self):
        entry = L.unknown_real_registry_burn(failure_window="SIGN after invocation", control_sha="a" * 40,
                                             manifest_sha256=None, provenance="output and manifest lost",
                                             recorded_at="2026-10-06T12:00:00Z")
        self.assertEqual((entry["burnType"], entry["registryDigest"]), ("UNKNOWN_REAL_REGISTRY_BURN", "UNKNOWN"))
        with self.assertRaises(L.Mb3Refusal) as caught:
            L.validate_burn_entry(dict(entry, registryDigest="3" * 64))
        self.assertEqual(caught.exception.code, "TOMBSTONE_INVENTS_DIGEST")
        with self.assertRaises(L.Mb3Refusal):
            L.validate_burn_entry(dict(entry, provenance=""))

    def test_append_only_register(self):
        first = L.append_burn([], self.known("4" * 64))
        tomb = L.unknown_real_registry_burn(failure_window="w", control_sha="a" * 40, manifest_sha256=None,
                                            provenance="p", recorded_at="2026-10-06T12:00:00Z")
        second = L.append_burn(first, tomb)
        self.assertTrue(L.register_extends(first, second))
        self.assertFalse(L.register_extends(second, first))
        self.assertFalse(L.register_extends(first, [dict(first[0], recordedAt="2026-10-06T12:00:01Z")]))
        with self.assertRaises(L.Mb3Refusal):
            L.append_burn(second, self.known("4" * 64))
        self.assertEqual(L.known_burned_registry_digests(second), frozenset({"4" * 64}))

    def test_no_real_burn_is_recorded_in_the_repository(self):
        self.assertEqual(BI.CANONICAL_COUNT, 20)
        self.assertEqual(len(BI.BURNED_REGISTRY_DIGESTS), 3)


def _vendor_from_installed(target: Path) -> Path | None:
    vendor = target / "vendor"
    vendor.mkdir()
    for top in ("fido2", "rfc8785"):
        origin = Path(importlib.util.find_spec(top).origin).parent
        shutil.copytree(origin, vendor / top, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        infos = list(origin.parent.glob(f"{top}-*.dist-info"))
        if len(infos) != 1:
            return None
        shutil.copytree(infos[0], vendor / infos[0].name)
    if sorted(p.name for p in vendor.iterdir()) != sorted(BUILD.VENDOR_TOPS):
        return None
    return vendor


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _temp_repo(directory: Path) -> tuple[Path, str]:
    """A throwaway git repo holding the current working-tree closure and phone script, committed once."""
    repo = directory / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    for name in (*BUILD.CLOSURE, BUILD.PHONE_SCRIPT, "services/owner-memory-control/tools/build_mb1_kroot_bundle.py"):
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, repo / name)
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "fixture")
    return repo, _git(repo, "rev-parse", "HEAD")


@unittest.skipUnless(HAVE_CRYPTO and shutil.which("git"), "crypto deps and git are required")
class BuilderTests(RedactedFailures, unittest.TestCase):
    def test_closure_is_owner_tool_closure_plus_library(self):
        mods = {"lilith_owner_memory": ROOT / "services/owner-memory-control/lilith_owner_memory",
                "lilith_memory": ROOT / "services/core-api/lilith_memory"}
        seen: set[Path] = set()

        def visit(path: Path) -> None:
            if path in seen:
                return
            seen.add(path)
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom) and node.level:
                    for name in ([node.module] if node.module else [a.name for a in node.names]):
                        candidate = path.parent / (name.split(".")[0] + ".py")
                        if candidate.exists():
                            visit(candidate)
                    continue
                names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                         else [node.module] + [f"{node.module}.{a.name}" for a in node.names]
                         if isinstance(node, ast.ImportFrom) else [])
                for name in names:
                    parts = name.split(".")
                    if parts[0] in mods:
                        visit(mods[parts[0]] / "__init__.py")
                        for i in range(len(parts), 1, -1):
                            candidate = mods[parts[0]].joinpath(*parts[1:i]).with_suffix(".py")
                            if candidate.exists():
                                visit(candidate)
                                break
        for start in (OWNER_TOOL, ROOT / "services/owner-memory-control/lilith_owner_memory/burned_identities.py",
                      TOOLS / "mb3_registry_ceremony.py"):
            visit(start)
        self.assertEqual(sorted(p.relative_to(ROOT).as_posix() for p in seen), sorted(BUILD.CLOSURE))
        self.assertNotIn(BUILD.PHONE_SCRIPT, BUILD.CLOSURE)
        self.assertNotIn("services/authority-dev/ceremony/lilith_authority_keygen_dev.py", BUILD.CLOSURE)

    def test_bundle_is_deterministic_public_only_and_never_self_hashed(self):
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            vendor = _vendor_from_installed(d)
            if vendor is None:
                self.skipTest("installed fido2 / rfc8785 dist-info layout differs")
            repo, commit = _temp_repo(d)
            first = BUILD.build(repo, commit, vendor, d / "one.tar")
            second = BUILD.build(repo, commit, vendor, d / "two.tar")
            self.assertEqual((d / "one.tar").read_bytes(), (d / "two.tar").read_bytes())
            self.assertEqual(first["tarSha256"], second["tarSha256"])
            self.assertEqual(first["phoneScriptSha256"],
                             hashlib.sha256((ROOT / BUILD.PHONE_SCRIPT).read_bytes()).hexdigest())
            raw = (d / "one.tar").read_bytes()
            self.assertNotIn(first["tarSha256"].encode(), raw)               # no recursive self-hash
            with tarfile.open(d / "one.tar") as tar:
                names = [m.name.split("/", 1)[1] for m in tar.getmembers() if m.isfile()]
                sums = tar.extractfile(f"{first['top']}/SHA256SUMS").read().decode()
            self.assertEqual(first["top"], f"lilith-mb3-registry-{commit[:7]}")
            self.assertNotIn("SHA256SUMS", [line.split("  ", 1)[1] for line in sums.splitlines()])
            self.assertNotIn(BUILD.PHONE_SCRIPT, names)
            for name in names:
                for part in ("k-root", ".der", ".pem", ".cred", "secret", "passphrase", "publication", "mb3-inputs"):
                    self.assertNotIn(part, name.lower())
            self.assertIn(BUILD.LIBRARY, names)
            self.assertIn("services/authority-dev/ceremony/lilith_authority_owner_dev.py", names)
            with self.assertRaises(BUILD.BuildError):
                BUILD.build(repo, "z" * 40, vendor, d / "three.tar")


# ------------------------------------------------------------- phone script ---

class _Signer:
    """Runs the bundle's owner tool in-process with a TEST passphrase, writing to the given fds."""

    def __init__(self, passphrase: str, override=None):
        self.passphrase = passphrase.encode()
        self.calls: list[tuple[list[str], dict[str, str]]] = []
        self.override = override

    def __call__(self, argv, out_fd, err_fd, env):
        self.calls.append((list(argv), dict(env)))
        if self.override is not None:
            return self.override(argv, out_fd, err_fd)
        tool = _load("mb3_bundle_owner_tool_run", Path(argv[2]))
        out = io.TextIOWrapper(os.fdopen(os.dup(out_fd), "wb"), encoding="utf-8")
        err = io.TextIOWrapper(os.fdopen(os.dup(err_fd), "wb"), encoding="utf-8")
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = tool.main(argv[3:], passphrase=lambda: self.passphrase)
        out.close()
        err.close()
        return code


@unittest.skipUnless(HAVE_CRYPTO and shutil.which("git") and os.name == "posix", "posix, git and crypto deps required")
class PhoneScriptTests(RedactedFailures, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        cls.vendor = _vendor_from_installed(d)
        if cls.vendor is None:
            raise unittest.SkipTest("installed fido2 / rfc8785 dist-info layout differs")
        cls.repo, cls.commit = _temp_repo(d)
        cls.built = BUILD.build(cls.repo, cls.commit, cls.vendor, d / "bundle.tar")
        cls.bundle_raw = (d / "bundle.tar").read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.case_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.case_dir.name) / "home"
        self.home.mkdir()
        self.world = World(Path(self.case_dir.name))
        (self.home / "storage/downloads").mkdir(parents=True)
        (self.home / "storage/downloads" / f"lilith-mb3-registry-{self.commit[:7]}.tar").write_bytes(self.bundle_raw)
        (self.home / "storage/downloads/mb3-kact-publication.json").write_bytes(self.world.kact_raw)
        (self.home / "storage/downloads/mb3-kwit-publication.json").write_bytes(self.world.kwit_raw)
        pub = self.home / "lilith-kroot-dev-synthetic-public"
        pub.mkdir(mode=0o700)
        (pub / "k-root-anchor.json").write_bytes(self.world.root_raw)
        keydir = self.home / "lilith-kroot-dev-synthetic"
        keydir.mkdir(mode=0o700)
        shutil.copyfile(self.world.key_path, keydir / "k-root.der")
        os.chmod(keydir / "k-root.der", 0o600)
        os.chmod(keydir, 0o700)
        self.out: list[str] = []
        self.tokens: list[int] = []
        self.nows: list[int] = []
        self.confirms: list[str] = []

    def tearDown(self):
        self.case_dir.cleanup()

    def phone(self, signer=None, answer=None, key_guard=False, **kw):
        test = self

        class TestPhone(PHONE.Phone):
            def key_path(self):
                if key_guard:
                    raise AssertionError("PREPARE touched the K-ROOT path")
                return super().key_path()

        def token_hex(n):
            test.tokens.append(n)
            return "ab" * n

        def now():
            test.nows.append(1)
            return datetime(2026, 10, 6, 12, 0, 0, tzinfo=timezone.utc)

        def confirm(prompt):
            test.confirms.append(prompt)
            return answer if answer is not None else prompt.split("'")[1]

        fields = dict(home=self.home, require_termux_private=False, proc=self.home / "noproc",
                      environ={"PATH": os.environ.get("PATH", "")}, interactive=lambda: True, confirm=confirm,
                      show=lambda text: test.out.append("SHOW " + text), run_signer=signer or _Signer("x"),
                      token_hex=token_hex, now=now, accepted=self.world.accepted,
                      script=ROOT / BUILD.PHONE_SCRIPT, out=test.out.append)
        fields.update(kw)
        return TestPhone(**fields)

    def run_prepare(self, phone=None, **kw):
        args = dict(control_sha=self.commit, bundle_sha256=self.built["tarSha256"],
                    kact_publication_sha256=self.world.kact_sha)
        args.update(kw)
        return PHONE.prepare(phone or self.phone(key_guard=True), **args)

    def manifest_sha(self):
        return hashlib.sha256((self.home / "lilith-mb3/mb3-inputs.json").read_bytes()).hexdigest()

    def run_sign(self, phone, manifest_sha=None):
        return PHONE.sign(phone, control_sha=self.commit, bundle_sha256=self.built["tarSha256"],
                          manifest_sha256=manifest_sha or self.manifest_sha())

    # PREPARE ---------------------------------------------------------------

    def test_prepare_freezes_one_candidate_without_kroot(self):
        self.assertEqual(self.run_prepare(), 0)
        self.assertEqual(self.tokens, [16])                  # epochRandom generated exactly once
        self.assertEqual(len(self.nows), 1)                  # issuedAt generated exactly once
        work = self.home / "lilith-mb3"
        manifest = json.loads((work / "mb3-inputs.json").read_bytes())
        self.assertEqual(manifest["epochRandom"], "ab" * 16)
        self.assertEqual(manifest["issuedAt"], "2026-10-06T12:00:00Z")
        self.assertEqual(manifest["policyVersion"], "policy.dev-synthetic.v1")
        self.assertEqual(manifest["bundleSha256"], self.built["tarSha256"])
        self.assertEqual(manifest["scriptSha256"], self.built["phoneScriptSha256"])
        self.assertEqual(manifest["expectedRegistryDigest"],
                         hashlib.sha256((work / "registry-signing-bytes.bin").read_bytes()).hexdigest())
        self.assertFalse((work / "sign").exists())
        self.assertFalse((self.home / "lilith-mb3-registry-public").exists())
        self.assertIn(PHONE.NOT_AUTHORIZATION, self.out)
        self.assertIn("K-ROOT WAS NOT ACCESSED. NO PASSPHRASE WAS REQUESTED. NOTHING WAS SIGNED.", self.out)
        self.assertTrue(self.out[-1].startswith("STOP: the owner decides"))
        self.assertIn(f"MANIFEST_SHA256 {self.manifest_sha()}", self.out)
        self.assertEqual(self.confirms, [])                  # PREPARE asks nothing

    def test_prepare_source_never_names_kroot_private_paths(self):
        tree = ast.parse((ROOT / BUILD.PHONE_SCRIPT).read_text(encoding="utf-8"))
        prepare = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "prepare")
        text = ast.unparse(prepare)
        for forbidden in ("key_path", "k-root.der", "lilith-kroot-dev-synthetic/", "getpass", "run_signer",
                          "_root_key", "load_der_private_key"):
            self.assertNotIn(forbidden, text)
        library = (TOOLS / "mb3_registry_ceremony.py").read_text(encoding="utf-8")
        for forbidden in ("import getpass", "getpass.", "load_der_private_key", "_root_key", "open(",
                          "Ed25519PrivateKey", "private_bytes"):
            self.assertNotIn(forbidden, library)

    def test_prepare_is_single_use(self):
        self.assertEqual(self.run_prepare(), 0)
        with self.assertRaises(PHONE.Stop):
            self.run_prepare()
        self.assertEqual(self.tokens, [16])

    def test_prepare_refusals(self):
        with self.assertRaises(PHONE.Stop):
            self.run_prepare(bundle_sha256="0" * 64)
        shutil.rmtree(self.home / "lilith-mb3")
        with self.assertRaises(PHONE.Stop) as caught:
            self.run_prepare(kact_publication_sha256="0" * 64)
        self.assertIn("KACT_PUBLICATION_SHA256_MISMATCH", str(caught.exception))
        shutil.rmtree(self.home / "lilith-mb3")
        with self.assertRaises(PHONE.Stop):
            PHONE.prepare(self.phone(key_guard=True, environ={"SSH_CONNECTION": "1 2 3 4"}),
                          control_sha=self.commit, bundle_sha256=self.built["tarSha256"],
                          kact_publication_sha256=self.world.kact_sha)
        self.assertEqual(self.tokens, [])

    def test_sshd_or_adbd_stops(self):
        proc = self.home / "noproc" / "123"
        proc.mkdir(parents=True)
        (proc / "comm").write_text("adbd\n")
        with self.assertRaises(PHONE.Stop):
            self.run_prepare()

    # SIGN ------------------------------------------------------------------

    def test_sign_success_is_registry_signed_and_requires_owner_acceptance(self):
        self.run_prepare()
        manifest_sha = self.manifest_sha()
        signer = _Signer(TEST_PASSPHRASE)
        self.assertEqual(self.run_sign(self.phone(signer=signer), manifest_sha), 0)
        self.assertEqual(len(signer.calls), 1)
        argv, env = signer.calls[0]
        manifest = json.loads((self.home / "lilith-mb3/mb3-inputs.json").read_bytes())
        self.assertEqual(argv[1:2] + argv[3:], ["-B", "registry-v1", str(self.home / "lilith-kroot-dev-synthetic/k-root.der"),
                                                str(self.home / "lilith-mb3/inputs/kact-publication.json"),
                                                manifest["epochRandom"], "policy.dev-synthetic.v1", manifest["issuedAt"]])
        self.assertTrue(argv[2].endswith("services/authority-dev/ceremony/lilith_authority_owner_dev.py"))
        self.assertEqual(sorted(env), ["HOME", "PATH", "PYTHONDONTWRITEBYTECODE", "PYTHONPATH"])
        self.assertNotIn(TEST_PASSPHRASE, json.dumps([argv, env]))
        self.assertEqual(len(self.confirms), 1)
        self.assertIn(f"MB3_TECHNICAL_STATE=REGISTRY_SIGNED", self.out)
        self.assertIn("STOP: separate owner acceptance is required. M-B4/M-B5 NOT AUTHORIZED.", self.out)
        public = self.home / "lilith-mb3-registry-public/authority-registry.v1.json"
        digest = (self.home / "lilith-mb3-registry-public/authority-registry.v1.digest").read_text().strip()
        self.assertEqual(digest, manifest["expectedRegistryDigest"])
        self.assertEqual(public.read_bytes(), (self.home / "lilith-mb3/sign/registry-v1.stdout").read_bytes())
        with tarfile.open(self.home / "lilith-mb3-export.tar") as tar:
            self.assertEqual(sorted(m.name for m in tar.getmembers()), list(PHONE.SUCCESS_EXPORT))
            for member in tar.getmembers():
                self.assertNotIn(TEST_PASSPHRASE.encode(), tar.extractfile(member).read())
                self.assertNotIn(self.world.key_path.read_bytes()[:32], tar.extractfile(member).read())
        V = _load("verify_mb3_registry_t", TOOLS / "verify_mb3_registry.py")
        ok, lines, detail = V.verify_export(self.home / "lilith-mb3-export.tar", control_sha=self.commit,
                                            bundle_sha256=self.built["tarSha256"], manifest_sha256=manifest_sha,
                                            kact_publication_sha256=self.world.kact_sha,
                                            accepted=self.world.accepted)
        self.assertTrue(ok, detail)
        self.assertEqual(detail, digest)
        self.assertIn("OWNER_TOOL_RECONSTRUCTION_EQUAL", lines)
        ok, _, detail = V.verify_export(self.home / "lilith-mb3-export.tar", control_sha=self.commit,
                                        bundle_sha256=self.built["tarSha256"], manifest_sha256="0" * 64,
                                        kact_publication_sha256=self.world.kact_sha, accepted=self.world.accepted)
        self.assertEqual((ok, detail), (False, "MANIFEST_SHA256_NOT_GO"))
        # one attempt only: a second SIGN is refused before anything runs
        again = _Signer(TEST_PASSPHRASE)
        with self.assertRaises(PHONE.Stop) as caught:
            self.run_sign(self.phone(signer=again), manifest_sha)
        self.assertIn("ATTEMPT_ALREADY_CONSUMED", str(caught.exception))
        self.assertEqual(again.calls, [])

    def outcome(self):
        return json.loads((self.home / "lilith-mb3/evidence/sign-outcome.json").read_bytes())

    def test_wrong_passphrase_consumes_the_go_without_burn(self):
        self.run_prepare()
        signer = _Signer("TEST_ONLY wrong passphrase")
        with self.assertRaises(PHONE.Stop):
            self.run_sign(self.phone(signer=signer))
        self.assertEqual(len(signer.calls), 1)
        self.assertEqual(self.outcome()["outcome"], "A_NO_SIGNATURE")
        self.assertFalse((self.home / "lilith-mb3/burn").exists())
        self.assertFalse((self.home / "lilith-mb3-registry-public").exists())
        self.assertTrue((self.home / "lilith-mb3-failure-export.tar").is_file())
        with self.assertRaises(PHONE.Stop):
            self.run_sign(self.phone(signer=_Signer(TEST_PASSPHRASE)))     # no same-go retry

    def test_output_lost_after_signing_burns_the_frozen_digest(self):
        self.run_prepare()

        def crash(argv, out_fd, err_fd):
            os.write(err_fd, b"Traceback (most recent call last):\nOSError: [Errno 28] No space left\n")
            return 1
        with self.assertRaises(PHONE.Stop):
            self.run_sign(self.phone(signer=_Signer(TEST_PASSPHRASE, override=crash)))
        burn = json.loads((self.home / "lilith-mb3/burn/real-registry-burn.json").read_bytes())
        L.validate_burn_entry(burn)
        manifest = json.loads((self.home / "lilith-mb3/mb3-inputs.json").read_bytes())
        self.assertEqual((burn["registryDigest"], burn["digestSource"], burn["case"]),
                         (manifest["expectedRegistryDigest"], "PRE_SIGN_FROZEN_MANIFEST", "D_OUTPUT_LOST_OR_UNCERTAIN"))
        self.assertEqual(self.outcome()["outcome"], "D_SIGNATURE_UNCERTAIN_BURN_FROZEN")
        with tarfile.open(self.home / "lilith-mb3-failure-export.tar") as tar:
            names = {m.name for m in tar.getmembers()}
        self.assertIn("lilith-mb3/burn/real-registry-burn.json", names)
        self.assertTrue(names <= set(PHONE.FAILURE_EXPORT_REQUIRED) | set(PHONE.FAILURE_EXPORT_OPTIONAL))

    def test_signed_but_invalid_burns_the_signed_digest_and_is_never_published(self):
        self.run_prepare()
        manifest = json.loads((self.home / "lilith-mb3/mb3-inputs.json").read_bytes())
        intruder = Ed25519PrivateKey.generate()

        def wrong_key(argv, out_fd, err_fd):
            registry = OWNER.registry_v1(intruder, json.loads(self.world.kact_raw), epoch_random=manifest["epochRandom"],
                                         policy_version=manifest["policyVersion"], issued_at=manifest["issuedAt"])
            os.write(out_fd, L.canonical_bytes(registry))
            return 0
        with self.assertRaises(PHONE.Stop):
            self.run_sign(self.phone(signer=_Signer(TEST_PASSPHRASE, override=wrong_key)))
        burn = json.loads((self.home / "lilith-mb3/burn/real-registry-burn.json").read_bytes())
        self.assertEqual((burn["digestSource"], burn["case"]), ("SIGNED_OUTPUT", "C_VERIFICATION_FAILED"))
        self.assertEqual(self.outcome()["outcome"], "C_SIGNED_INVALID_BURN")
        self.assertFalse((self.home / "lilith-mb3-registry-public").exists())
        self.assertFalse((self.home / "lilith-mb3-export.tar").exists())

    def test_confirmation_mismatch_consumes_without_invocation(self):
        self.run_prepare()
        signer = _Signer(TEST_PASSPHRASE)
        with self.assertRaises(PHONE.Stop):
            self.run_sign(self.phone(signer=signer, answer="yes"))
        self.assertEqual(signer.calls, [])
        self.assertEqual(self.outcome()["outcome"], "A_NO_SIGNATURE")
        with self.assertRaises(PHONE.Stop) as caught:
            self.run_sign(self.phone(signer=signer))
        self.assertIn("ATTEMPT_ALREADY_CONSUMED", str(caught.exception))

    def test_manifest_pin_mismatch_and_tampering_stop_before_invocation(self):
        self.run_prepare()
        signer = _Signer(TEST_PASSPHRASE)
        with self.assertRaises(PHONE.Stop):
            self.run_sign(self.phone(signer=signer), manifest_sha="0" * 64)
        self.assertEqual(signer.calls, [])

    def test_changed_input_after_prepare_stops(self):
        self.run_prepare()
        path = self.home / "lilith-mb3/inputs/kwit-publication.json"
        os.chmod(path, 0o600)
        path.write_bytes(path.read_bytes() + b" ")
        signer = _Signer(TEST_PASSPHRASE)
        with self.assertRaises(PHONE.Stop):
            self.run_sign(self.phone(signer=signer))
        self.assertEqual(signer.calls, [])

    def test_real_subprocess_never_feeds_stdin(self):
        source = (ROOT / BUILD.PHONE_SCRIPT).read_text(encoding="utf-8")
        self.assertIn("stdin=subprocess.DEVNULL", source)
        self.assertEqual(source.count("phone.run_signer("), 1)
        self.assertNotIn("import getpass", source)          # only the signer's own getpass asks, on /dev/tty
        self.assertNotIn("getpass.", source)

    def test_export_refuses_private_names(self):
        (self.home / "lilith-mb3").mkdir()
        (self.home / "lilith-mb3/k-root.der").write_bytes(b"x")
        with self.assertRaises(PHONE.Stop):
            PHONE._build_export(self.phone(), self.home / "x.tar", ("lilith-mb3/k-root.der",), ())


if __name__ == "__main__":
    unittest.main()
