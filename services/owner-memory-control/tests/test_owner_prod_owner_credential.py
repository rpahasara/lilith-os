"""OWNER_PROD owner credential tool (D-8/D-12): the PROD twin of the DEV software authenticator.

TEST_ONLY: every key here is a throwaway generated in a temporary directory and deleted with it; the identities use
the reserved documentation domain `example.org` (RFC 2606), never the owner's. Proven here:
1. a PROD credential's possession proof, assertion and registration verify through the PROD host's own parser and
   the owner-memory verifier's own WebAuthn check, for exactly that relying party and origin;
2. DEV and PROD never cross: a DEV credential, proof or registration is refused on the PROD path and the reverse;
3. every invalid or synthetic identity and every malformed input is refused before any key is written;
4. the DEV tool is byte-identical to main and its module keeps its DEV identity.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import os
import secrets
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _p in (ROOT / "services/owner-memory-control/tools", ROOT / "services/owner-memory-control",
           ROOT / "services/core-api", ROOT / "services/authority-dev", HERE):   # tools, verifier, owner_proof, host inputs
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    import fido2  # noqa: F401
    import rfc8785  # noqa: F401
    HAVE_CRYPTO = True
except ImportError:                                            # the Windows checkout has no fido2: CI and WSL do
    HAVE_CRYPTO = False

RP, ORIGIN, PRINCIPAL = "lilith.example.org", "https://lilith.example.org", "user:owner@example.org"
BASE = "28d471168b34370591df06c37134d83057d4d68e"      # the DEV tool must stay byte-identical to main before this PR
RELEASE = "88a1168bd41797109772ffce7df7352c1ae40e4c"

if HAVE_CRYPTO:
    import first_memory_owner_credential_dev as DEV
    import owner_prod_owner_credential as PC
    from lilith_authority_host import inputs as HI
    from lilith_memory import owner_proof as OP
    from lilith_owner_memory import verifier as V


class _Challenge:
    def __init__(self, raw: bytes):
        self.raw = raw

    def webauthn_challenge(self) -> bytes:
        return self.raw


@unittest.skipUnless(HAVE_CRYPTO, "fido2 and rfc8785 are needed (CI and WSL have them)")
class ProdOwnerCredentialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.tool = PC.ProdCredentialTool(RP, ORIGIN, PRINCIPAL)

    def make(self, tool=None, name="cred"):
        tool = tool or self.tool
        key, public = self.dir / f"{name}.key", self.dir / f"{name}.public.json"
        out = tool.create(key, public)
        return key, json.loads(public.read_bytes()), out

    def refused(self, reason, fn, prefix=False):
        with self.assertRaises(PC.Refused) as caught:
            fn()
        got = caught.exception.reason
        self.assertTrue(got.startswith(reason) if prefix else got == reason, got)

    # ---------------------------------------------------------------------------------------------- positive ---
    def test_create_writes_only_the_private_key_file_and_a_public_record_for_this_identity(self):
        key, public, out = self.make()
        self.assertEqual(stat.S_IMODE(os.stat(key).st_mode), 0o600)
        self.assertTrue(key.read_bytes().startswith(b"-----BEGIN PRIVATE KEY-----"))
        credential = public["credential"]
        self.assertEqual((credential["ownerPrincipal"], credential["rpId"], credential["status"], credential["algorithm"]),
                         (PRINCIPAL, RP, "ACTIVE", -7))
        self.assertTrue(credential["recordId"].startswith("ocred.owner-prod."))
        self.assertEqual(out["recordId"], credential["recordId"])
        self.assertNotIn("BEGIN", (self.dir / "cred.public.json").read_text())         # public material only
        self.assertEqual(OP.OwnerCredentialV1.from_dict(credential).to_dict(), credential)
        with self.assertRaises(FileExistsError):                                       # O_EXCL: never overwritten
            self.tool.create(key, self.dir / "other.json")

    def test_the_registration_is_exactly_what_the_prod_host_parses(self):
        _key, public, _out = self.make()
        _key2, public2, _out2 = self.make(name="second")
        document = self.tool.registration([public, public2], release_sha=RELEASE)
        self.assertEqual((document["protocol"], document["environment"]), ("LILITH_OWNER_REGISTRATION_PROD", "prod"))
        self.assertEqual(document["protocol"], HI.OWNER_REGISTRATION_PROTOCOLS["prod"])
        parsed = HI.parse_owner_registration(document, environment="prod")
        self.assertEqual((parsed.owner_principal, parsed.rp_id, parsed.origin), (PRINCIPAL, RP, ORIGIN))
        self.assertEqual((parsed.registry_tuple_version, parsed.privacy_notice_version),
                         ("tuple.owner-prod.v1", "privacy.owner-prod.v1"))
        self.assertEqual(len(parsed.credentials), 2)
        with self.assertRaises(ValueError):                                            # never readable as DEV
            HI.parse_owner_registration(document, environment="dev")

    def test_a_registration_the_prod_host_would_reject_is_refused_by_the_tool(self):
        """The DEV builder has no credential limit; the PROD host allows at most MAX_OWNER_CREDENTIALS. The tool runs
        the host's own parser, so it refuses instead of printing a registration PROD would reject."""
        publics = [self.make(name=f"c{i}")[1] for i in range(HI.MAX_OWNER_CREDENTIALS + 1)]
        self.refused("REGISTRATION_NOT_OWNER_PROD:OWNER_REGISTRATION_CREDENTIALS",
                     lambda: self.tool.registration(publics, release_sha=RELEASE))
        HI.parse_owner_registration(self.tool.registration(publics[:HI.MAX_OWNER_CREDENTIALS], release_sha=RELEASE),
                                    environment="prod")                          # at the limit it is accepted

    def test_an_assertion_verifies_through_the_owner_memory_verifier_for_this_rp_and_origin_only(self):
        key, public, _out = self.make()
        challenge = secrets.token_bytes(32)
        assertion = OP.OwnerAssertionV1.from_dict(self.tool.assertion(key, public, challenge))
        credential = OP.OwnerCredentialV1.from_dict(public["credential"])
        V._verify_webauthn(_Challenge(challenge), assertion, credential, rp_id=RP, origin=ORIGIN)       # no raise
        for rp_id, origin in ((DEV.RP_ID, DEV.ORIGIN), (RP, "https://other.example.org"), ("example.org", ORIGIN)):
            with self.subTest(rp_id=rp_id, origin=origin), self.assertRaises(Exception):
                V._verify_webauthn(_Challenge(challenge), assertion, credential, rp_id=rp_id, origin=origin)
        with self.assertRaises(Exception):                                             # another challenge
            V._verify_webauthn(_Challenge(secrets.token_bytes(32)), assertion, credential, rp_id=RP, origin=ORIGIN)

    def test_a_subdomain_origin_on_the_rp_is_accepted(self):
        tool = PC.ProdCredentialTool("example.org", "https://lilith.example.org", PRINCIPAL)
        _key, public, _out = self.make(tool, "sub")
        HI.parse_owner_registration(tool.registration([public], release_sha=RELEASE), environment="prod")

    # ------------------------------------------------------------------------------------- cross-environment ---
    def test_dev_and_prod_material_never_cross(self):
        _key, prod_public, _out = self.make()
        dev_key, dev_public = self.dir / "dev.key", self.dir / "dev.public.json"
        DEV.create(dev_key, dev_public)
        dev_public = json.loads(dev_public.read_bytes())
        self.refused("CREDENTIAL_NOT_OWNER_PROD", lambda: self.tool.verify_possession(dev_public))
        self.refused("CREDENTIAL_NOT_OWNER_PROD", lambda: self.tool.registration([dev_public], release_sha=RELEASE))
        with self.assertRaises(DEV.Refused):                                           # the DEV tool refuses PROD
            DEV.verify_possession(prod_public)
        dev_document = DEV.registration_document([dev_public], release_sha=RELEASE)
        with self.assertRaises(ValueError):
            HI.parse_owner_registration(dev_document, environment="prod")
        # a DEV-domain proof relabelled as PROD (record prefix and identity swapped) still fails: the proof domain differs
        forged = json.loads(json.dumps(dev_public))
        forged["credential"].update(recordId="ocred.owner-prod." + forged["credential"]["recordId"].split(".")[-1],
                                    ownerPrincipal=PRINCIPAL, rpId=RP)
        forged["possessionProof"]["credentialRecordId"] = forged["credential"]["recordId"]
        self.refused("PROOF_", lambda: self.tool.verify_possession(forged), prefix=True)

    def test_a_proof_made_under_the_dev_registration_domain_is_refused_even_for_the_prod_identity(self):
        """Domain separation alone: the same identity and record, signed by a DEV-domain instance, never verifies."""
        spec = importlib.util.spec_from_file_location("dev_domain_instance", PC.DEV_TOOL)
        dev_domain = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dev_domain)
        dev_domain.OWNER_PRINCIPAL, dev_domain.RP_ID, dev_domain.ORIGIN = PRINCIPAL, RP, ORIGIN   # identity only
        _key, public, _out = self.make()
        private = dev_domain.ec.generate_private_key(dev_domain.ec.SECP256R1())
        credential = dict(public["credential"], publicKeyCose=dev_domain.b64(dev_domain.cbor.encode(
            dev_domain.ES256.from_cryptography_key(private.public_key()))))
        forged = {"credential": credential, "possessionProof": dev_domain.sign_assertion(
            private, credential, dev_domain.registration_challenge(credential))}
        dev_domain.verify_possession(forged)                                   # valid under the DEV domain
        self.refused("PROOF_CHALLENGE_MISMATCH", lambda: self.tool.verify_possession(forged))

    def test_another_prod_identity_is_not_this_owner(self):
        _key, public, _out = self.make()
        other = PC.ProdCredentialTool("lilith.example.net", "https://lilith.example.net", "user:owner@example.net")
        self.refused("CREDENTIAL_NOT_THIS_OWNER", lambda: other.verify_possession(public))

    def test_the_dev_tool_is_byte_identical_and_keeps_its_dev_identity(self):
        base = subprocess.run(["git", "-C", str(ROOT), "show", f"{BASE}:{PC.DEV_TOOL.relative_to(ROOT).as_posix()}"],
                              capture_output=True, check=True).stdout
        self.assertEqual(PC.DEV_TOOL.read_bytes(), base)
        PC.ProdCredentialTool(RP, ORIGIN, PRINCIPAL)                                    # a private instance only
        self.assertEqual((DEV.OWNER_PRINCIPAL, DEV.RP_ID, DEV.ORIGIN, DEV.REGISTRATION_PROTOCOL),
                         ("user:synthetic-owner@example.invalid", "owner.lilith.invalid", "https://owner.lilith.invalid",
                          "LILITH_OWNER_REGISTRATION_DEV"))
        self.assertIsNot(self.tool.module, DEV)

    # ---------------------------------------------------------------------------------- invalid identities ---
    def test_every_synthetic_or_invalid_identity_is_refused_before_any_key_is_written(self):
        cases = {
            "the DEV synthetic owner": (DEV.RP_ID, DEV.ORIGIN, DEV.OWNER_PRINCIPAL),
            "an .invalid rp": ("lilith.invalid", "https://lilith.invalid", PRINCIPAL),
            "an .invalid principal": (RP, ORIGIN, "user:owner@example.invalid"),
            "http origin": (RP, "http://lilith.example.org", PRINCIPAL),
            "origin on another domain": (RP, "https://lilith.example.net", PRINCIPAL),
            "origin with a path": (RP, ORIGIN + "/login", PRINCIPAL),
            "uppercase rp": ("Lilith.Example.org", "https://Lilith.Example.org", PRINCIPAL),
            "rp without a tld": ("lilith", "https://lilith", PRINCIPAL),
            "rp with a numeric tld": ("lilith.example.123", "https://lilith.example.123", PRINCIPAL),
            "principal without the user: prefix": (RP, ORIGIN, "owner@example.org"),
            "principal with a space": (RP, ORIGIN, "user:the owner@example.org"),
            "empty principal name": (RP, ORIGIN, "user:@example.org"),
            "non-string rp": (None, ORIGIN, PRINCIPAL),
            "empty values": ("", "", ""),
        }
        for label, (rp_id, origin, principal) in cases.items():
            with self.subTest(label):
                before = sorted(os.listdir(self.dir))
                self.refused("IDENTITY_NOT_OWNER_PROD", lambda: PC.ProdCredentialTool(rp_id, origin, principal))
                self.assertEqual(sorted(os.listdir(self.dir)), before)

    # ---------------------------------------------------------------------------------------- malformed input ---
    def test_malformed_inputs_are_refused(self):
        key, public, _out = self.make()
        tampered = json.loads(json.dumps(public))
        sig = base64.urlsafe_b64decode(tampered["possessionProof"]["signature"] + "==")
        tampered["possessionProof"]["signature"] = base64.urlsafe_b64encode(sig[:-1] + bytes([sig[-1] ^ 1])).rstrip(
            b"=").decode()
        other_record = json.loads(json.dumps(public))
        other_record["possessionProof"]["credentialRecordId"] = "ocred.owner-prod.0000000000000000"
        missing = {"credential": public["credential"]}
        cases = {
            "a challenge that is not 32 bytes": (lambda: self.tool.assertion(key, public, b"\x00" * 31), "CHALLENGE_INVALID"),
            "a tampered signature": (lambda: self.tool.verify_possession(tampered), "PROOF_SIGNATURE_INVALID"),
            "a proof naming another credential": (lambda: self.tool.verify_possession(other_record),
                                                  "PROOF_NAMES_ANOTHER_CREDENTIAL"),
            "a public document missing its proof": (lambda: self.tool.verify_possession(missing), "PUBLIC_DOCUMENT_INVALID"),
            "not a document at all": (lambda: self.tool.verify_possession(["x"]), "CREDENTIAL_NOT_OWNER_PROD"),
            "an invalid release sha": (lambda: self.tool.registration([public], release_sha="88a1168"), "RELEASE_SHA_INVALID"),
            "the same credential twice": (lambda: self.tool.registration([public, public], release_sha=RELEASE),
                                          "CREDENTIALS_INVALID"),
            "no credential": (lambda: self.tool.registration([], release_sha=RELEASE), "CREDENTIALS_INVALID"),
        }
        for label, (fn, reason) in cases.items():
            with self.subTest(label):
                self.refused(reason, fn)
        wrong_key = self.dir / "p384.key"
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        wrong_key.write_bytes(ec.generate_private_key(ec.SECP384R1()).private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        self.refused("KEY_INVALID", lambda: self.tool.assertion(wrong_key, public, b"\x00" * 32))

    def test_the_cli_refuses_usage_and_identity_errors_without_writing(self):
        key = self.dir / "cli.key"
        for argv in ([], ["create"], ["sign", RP, ORIGIN, PRINCIPAL], ["create", RP, ORIGIN, PRINCIPAL, str(key)],
                     ["create", DEV.RP_ID, DEV.ORIGIN, DEV.OWNER_PRINCIPAL, str(key), str(self.dir / "p.json")]):
            with self.subTest(argv=argv):
                self.assertEqual(PC.main(argv), 2)
                self.assertFalse(key.exists())

    def test_no_secret_or_owner_identity_is_committed_in_the_tool(self):
        source = Path(PC.__file__).read_text(encoding="utf-8")
        for marker in ("BEGIN PRIVATE", "BEGIN EC PRIVATE", "-----BEGIN"):
            self.assertNotIn(marker, source)
        self.assertNotIn("example.org", source)                    # no identity baked in: D-8 arrives on every call


if __name__ == "__main__":
    unittest.main()
