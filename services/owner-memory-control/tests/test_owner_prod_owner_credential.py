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
from unittest import mock
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
        self.refused("OUTPUT_EXISTS:key", lambda: self.tool.create(key, self.dir / "other.json"))   # never overwritten
        self.assertFalse((self.dir / "other.json").exists())

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

    # ------------------------------------------------------------------------------- output-file safety ---
    def snapshot(self, *extra):
        """Every entry under the test directory (and any extra path), never following a link: kind, content, mode."""
        out = {}
        for path in sorted([*self.dir.rglob("*"), *map(Path, extra)]):
            if os.path.islink(path):
                out[str(path)] = ("link", os.readlink(path))
            elif path.is_file():
                out[str(path)] = ("file", path.read_bytes(), stat.S_IMODE(os.lstat(path).st_mode))
            elif path.is_dir():
                out[str(path)] = ("dir",)
        return out

    def test_an_existing_output_file_is_never_overwritten_and_nothing_is_created(self):
        key, public = self.dir / "o.key", self.dir / "o.public.json"
        for existing, reason in ((public, "OUTPUT_EXISTS:public"), (key, "OUTPUT_EXISTS:key")):
            with self.subTest(existing=existing.name):
                for p in (key, public):
                    if p.exists():
                        p.unlink()
                existing.write_bytes(b"precious owner data")
                before = self.snapshot()
                self.refused(reason, lambda: self.tool.create(key, public))
                self.assertEqual(self.snapshot(), before)                    # untouched, and no other file created
        cli_public = self.dir / "cli.public.json"                         # the CLI refuses the same way
        cli_public.write_bytes(b"precious owner data")
        self.assertEqual(PC.main(["create", RP, ORIGIN, PRINCIPAL, str(self.dir / "new.key"), str(cli_public)]), 2)
        self.assertFalse((self.dir / "new.key").exists())
        self.assertEqual(cli_public.read_bytes(), b"precious owner data")

    def test_an_output_path_that_is_a_link_is_refused_and_its_target_never_touched(self):
        outside = Path(self.tmp.name + "-outside")
        outside.mkdir()
        self.addCleanup(lambda: [p.unlink() for p in outside.iterdir()] and None or outside.rmdir())
        target = outside / "victim.json"
        target.write_bytes(b"someone else's file")
        for which in ("public", "key"):
            with self.subTest(which=which):
                key, public = self.dir / f"{which}.key", self.dir / f"{which}.public.json"
                link = public if which == "public" else key
                os.symlink(str(target), link)
                before = self.snapshot(target)
                self.refused("OUTPUT_EXISTS:" + which, lambda: self.tool.create(key, public))
                self.assertEqual(self.snapshot(target), before)
                self.assertEqual(target.read_bytes(), b"someone else's file")
        dangling = self.dir / "dangling.public.json"
        os.symlink(str(outside / "not-there.json"), dangling)                  # a dangling link is not "absent"
        self.refused("OUTPUT_EXISTS:public", lambda: self.tool.create(self.dir / "d.key", dangling))
        self.assertFalse((outside / "not-there.json").exists())

    def test_identical_or_aliased_output_paths_are_refused_before_anything_is_written(self):
        sub = self.dir / "sub"
        sub.mkdir()
        os.symlink(str(sub), self.dir / "alias")
        same = sub / "cred.out"
        cases = {
            "the same path": (same, same),
            "the same path spelled differently": (same, self.dir / "sub" / "." / "cred.out"),
            "through a dotdot": (same, self.dir / "sub" / ".." / "sub" / "cred.out"),
            "through a symlinked directory": (same, self.dir / "alias" / "cred.out"),
        }
        for label, (key, public) in cases.items():
            with self.subTest(label):
                before = self.snapshot()
                self.refused("OUTPUT_PATHS_IDENTICAL", lambda: self.tool.create(key, public))
                self.assertEqual(self.snapshot(), before)

    def test_a_missing_or_unsafe_output_directory_is_refused(self):
        not_a_dir = self.dir / "plain"
        not_a_dir.write_bytes(b"x")
        for key, public, reason in (
                (self.dir / "nope" / "k.key", self.dir / "p.json", "OUTPUT_DIRECTORY_INVALID:key"),
                (self.dir / "k.key", not_a_dir / "p.json", "OUTPUT_DIRECTORY_INVALID:public")):
            with self.subTest(reason=reason):
                before = self.snapshot()
                self.refused(reason, lambda: self.tool.create(key, public))
                self.assertEqual(self.snapshot(), before)

    def test_a_file_or_link_appearing_after_the_checks_is_refused_by_the_exclusive_open_itself(self):
        """The race the pre-checks cannot close: O_CREAT|O_EXCL|O_NOFOLLOW refuses a file or link that appears between
        the checks and the open. Nothing existing is overwritten or followed; what was already created is reported."""
        outside = Path(self.tmp.name + "-race")
        outside.mkdir()
        self.addCleanup(lambda: [p.unlink() for p in outside.iterdir()] and None or outside.rmdir())
        victim = outside / "victim.json"
        victim.write_bytes(b"someone else's file")
        for label, appear in (("a file", lambda p: p.write_bytes(b"appeared")),
                              ("a link", lambda p: os.symlink(str(victim), p))):
            with self.subTest(label):
                key, public = self.dir / f"r-{label[2:]}.key", self.dir / f"r-{label[2:]}.public.json"
                real_check = PC.check_outputs

                def check_then_race(k, p, real_check=real_check, appear=appear):
                    real_check(k, p)
                    appear(p)
                with mock.patch.object(PC, "check_outputs", check_then_race):
                    self.refused("PARTIAL_OUTPUT:key;OUTPUT_EXISTS:public", lambda: self.tool.create(key, public))
                self.assertEqual(victim.read_bytes(), b"someone else's file")         # never followed
                if not os.path.islink(public):
                    self.assertEqual(public.read_bytes(), b"appeared")                 # never overwritten
                self.assertTrue(key.exists())                                          # reported, not deleted

    def test_an_interrupted_write_stops_safely_and_leaves_its_files_for_the_owner(self):
        """A failure after the exclusive creations is PARTIAL_OUTPUT: nothing is deleted automatically, and a retry
        with the same paths is refused instead of overwriting what is there."""
        key, public = self.dir / "i.key", self.dir / "i.public.json"
        real_write = os.write
        calls = []

        def failing_write(fd, data):
            calls.append(len(data))
            if len(calls) == 2:                                        # the second file's write dies
                raise OSError(28, "No space left on device")
            return real_write(fd, data)

        with mock.patch.object(PC.os, "write", failing_write):
            self.refused("PARTIAL_OUTPUT", lambda: self.tool.create(key, public), prefix=True)
        self.assertTrue(key.exists() and public.exists())               # left in place for owner adjudication
        self.assertEqual(stat.S_IMODE(os.lstat(key).st_mode), 0o600)
        before = self.snapshot()
        self.refused("OUTPUT_EXISTS:public", lambda: self.tool.create(key, public))
        self.assertEqual(self.snapshot(), before)

    def test_both_outputs_are_complete_after_short_writes(self):
        key, public = self.dir / "s.key", self.dir / "s.public.json"
        real_write = os.write
        with mock.patch.object(PC.os, "write", lambda fd, data: real_write(fd, data[:7])):      # 7 bytes per call
            self.tool.create(key, public)
        self.tool.verify_possession(json.loads(public.read_bytes()))
        self.assertTrue(key.read_bytes().rstrip().endswith(b"-----END PRIVATE KEY-----"))
        self.assertEqual(stat.S_IMODE(os.lstat(public).st_mode), 0o644)

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


@unittest.skipUnless(HAVE_CRYPTO, "fido2 and rfc8785 are needed (CI and WSL have them)")
class StandaloneCliTests(unittest.TestCase):
    """The tool as the owner runs it: a fresh interpreter, launched outside the repository, with no repository
    directory on PYTHONPATH (only third-party dependency paths survive, e.g. WSL's vendored /root/l1deps). It must find
    every import it needs by itself. The outputs are then checked in-process against the PROD host parser and the
    owner-memory verifier."""

    TOOL = ROOT / "services/owner-memory-control/tools/owner_prod_owner_credential.py"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        root = os.path.realpath(ROOT)
        kept = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep)
                if p and not os.path.realpath(p).startswith(root)]
        self.env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        if kept:
            self.env["PYTHONPATH"] = os.pathsep.join(kept)
        self.assertFalse(any(os.path.realpath(p).startswith(root) for p in kept))       # no repository path leaks in

    def cli(self, *args):
        return subprocess.run([sys.executable, "-B", str(self.TOOL), *map(str, args)], cwd=self.dir, env=self.env,
                              capture_output=True, timeout=120)

    def test_create_assert_and_registration_run_standalone_and_verify_on_the_prod_path(self):
        key, public = self.dir / "s.key", self.dir / "s.public.json"
        created = self.cli("create", RP, ORIGIN, PRINCIPAL, key, public)
        self.assertEqual(created.returncode, 0, created.stderr.decode())
        summary = json.loads(created.stdout)
        self.assertTrue(summary["recordId"].startswith("ocred.owner-prod."))
        self.assertEqual(stat.S_IMODE(os.stat(key).st_mode), 0o600)

        challenge = secrets.token_bytes(32)
        asserted = self.cli("assert", RP, ORIGIN, PRINCIPAL, key, public, challenge.hex())
        self.assertEqual(asserted.returncode, 0, asserted.stderr.decode())
        record = json.loads(public.read_bytes())["credential"]
        V._verify_webauthn(_Challenge(challenge), OP.OwnerAssertionV1.from_dict(json.loads(asserted.stdout)),
                           OP.OwnerCredentialV1.from_dict(record), rp_id=RP, origin=ORIGIN)            # no raise

        registered = self.cli("registration", RP, ORIGIN, PRINCIPAL, RELEASE, public)
        self.assertEqual(registered.returncode, 0, registered.stderr.decode())
        parsed = HI.parse_owner_registration(json.loads(registered.stdout), environment="prod")
        self.assertEqual((parsed.owner_principal, parsed.rp_id, parsed.origin), (PRINCIPAL, RP, ORIGIN))

    def test_standalone_refusals_are_clean_and_write_nothing(self):
        dev = self.cli("create", DEV.RP_ID, DEV.ORIGIN, DEV.OWNER_PRINCIPAL, self.dir / "d.key", self.dir / "d.json")
        self.assertEqual(dev.returncode, 2)
        self.assertIn(b"REFUSED IDENTITY_NOT_OWNER_PROD", dev.stderr)
        self.assertNotIn(b"Traceback", dev.stderr)
        existing = self.dir / "existing.public.json"
        existing.write_bytes(b"precious")
        taken = self.cli("create", RP, ORIGIN, PRINCIPAL, self.dir / "e.key", existing)
        self.assertEqual(taken.returncode, 2)
        self.assertIn(b"REFUSED OUTPUT_EXISTS:public", taken.stderr)
        self.assertEqual(existing.read_bytes(), b"precious")
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["existing.public.json"])


if __name__ == "__main__":
    unittest.main()
