"""OWNER_PROD ceremony tooling (P3; TEST_ONLY synthetic keys in temporary trees; no host, no real key).

The three production tools (`owner-memory-control/tools/owner_prod_{keygen,owner_tool,kpan_keygen}.py`) are separate
from the DEV tools, which stay byte-identical. Proven here:
1. the committed source refuses every PROD form (PROD_MACHINE_ID_SHA256 unpinned); with a pin, they run only on a PROD-shaped
   host with the OWNER_PROD deployment, and never on the DEV machine;
2. K-ACT + K-WIT publications chain through the PROD owner tool into a `prod` registry, anchor and genesis that the
   runtime verifies under a `prod` context, and that a DEV context refuses;
3. no fallback: DEV publications, anchors and roots are refused on the PROD path.
"""

from __future__ import annotations

import copy
import re
import dataclasses
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _path in (ROOT / "services/owner-memory-control", ROOT / "services/core-api", ROOT / "services/authority-dev",
              ROOT / "services/authority-dev/ceremony", ROOT / "services/recovery-witness", HERE, TOOLS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import pr1s_fixtures as X  # noqa: E402
from pr1s_fixtures import B, F, PB  # noqa: E402

if X.POSIX:
    import lilith_authority_keygen_dev as G  # noqa: E402
    import owner_prod_keygen as PK  # noqa: E402
    import owner_prod_kpan_keygen as PKP  # noqa: E402
    import owner_prod_owner_tool as PO  # noqa: E402
    import test_custody_preparation as L2  # noqa: E402
    from lilith_authority_dev import profile as SP  # noqa: E402
    from lilith_owner_memory import authority_contracts as A  # noqa: E402
    from lilith_owner_memory import authority_verifier as AV  # noqa: E402
    from lilith_owner_memory import rotation_contracts as RC  # noqa: E402
    from lilith_recovery_witness import credential as WC  # noqa: E402

PROD_MID = "0123456789abcdef0123456789abcdef"
PASS = b"TEST_ONLY passphrase 123"
DEPLOYMENT = b'{"environment":"prod","profile":"OWNER_PROD","schemaVersion":1}\n'
BASE = "75ca0db084ef43f39462e3fe77b2f3fce8f5a0e2"


@unittest.skipUnless(X.POSIX, "owner and mode semantics are POSIX")
class SeparationTests(unittest.TestCase):
    def test_the_dev_tools_are_byte_identical_and_the_prod_ids_match_the_runtime(self):
        for path in ("services/authority-dev/ceremony/lilith_authority_keygen_dev.py",
                     "services/authority-dev/ceremony/lilith_authority_owner_dev.py",
                     "services/owner-memory-control/tools/trackb_kpan_keygen.py"):
            base = subprocess.run(["git", "-C", str(ROOT), "show", f"{BASE}:{path}"], capture_output=True,
                                  check=True).stdout
            self.assertEqual((ROOT / path).read_bytes(), base, path)
        self.assertEqual(PK.KEY_ID, SP.PROD_K_ACT_KEY_ID)
        self.assertEqual(PK.WITNESS_KEY_ID, B.OWNER_PROD_WITNESS_PROFILE.witness_key_id)
        self.assertEqual(PKP.KEY_ID, WC.PROD_PRIVACY_ANCHOR_KEY_ID)
        self.assertEqual(PKP.ENVIRONMENT, WC.PROD_PRIVACY_ANCHOR_ENVIRONMENT)
        self.assertTrue(PO.ROOT_KEY_ID.startswith(A.PROD_ROOT_PREFIX))
        self.assertEqual(PO.POLICY_VERSION, SP.PROD_POLICY_VERSION)
        self.assertEqual((PK.PROD_MACHINE_ID_SHA256, PKP.PROD_MACHINE_ID_SHA256), (None, None))   # unpinned, kept equal
        self.assertEqual((PK.HOSTNAME, PK.DEPLOYMENT), (PKP.HOSTNAME, PKP.DEPLOYMENT))
        import lilith_authority_owner_dev as DEV_OWNER        # the imported DEV module keeps its DEV identity
        self.assertEqual((DEV_OWNER.ENVIRONMENT, DEV_OWNER.ROOT_KEY_ID),
                         ("dev", "test-only.registry-root.dev-synthetic.b1b3d.1"))
        self.assertIsNot(PO.T, DEV_OWNER)


@unittest.skipUnless(X.POSIX, "owner and mode semantics are POSIX")
class KeygenTests(unittest.TestCase):
    def host(self, directory, *, machine_id=PROD_MID, deployment=DEPLOYMENT):
        host = L2.FakeHost(directory)
        host.systemd_creds_setup()
        (host.root / "etc/machine-id").write_text(machine_id + "\n", encoding="ascii")
        store = host.root / "etc/credstore.encrypted"
        store.mkdir(mode=0o700)
        os.chmod(store, 0o700)
        if deployment is not None:
            d = host.root / "etc/lilith-authority-dev"
            d.mkdir(parents=True, exist_ok=True)
            (d / "deployment.json").write_bytes(deployment)
            os.chmod(d / "deployment.json", 0o644)
        return host

    def preflight(self, host, *, hostname="lilith-01", pin=PROD_MID):
        return PK.actor_preflight(host.keygen_host(), euid=0, isolated=True, hostname=hostname, machine_pin=pin)

    def refused(self, fn, reason):
        with self.assertRaises(G.Refused) as caught:
            fn()
        self.assertEqual(caught.exception.reason, reason)

    def test_the_committed_source_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            host = self.host(d)
            self.refused(lambda: PK.actor_preflight(host.keygen_host(), euid=0, isolated=True, hostname="lilith-01"),
                         "PROD_MACHINE_ID_NOT_PINNED")
        self.assertEqual(PK.main(["successor", "2"]), G.EXIT_REFUSED)
        self.assertEqual(PK.main(["actor", "--dev"]), G.EXIT_REFUSED)

    def test_actor_and_witness_on_the_prod_host(self):
        with tempfile.TemporaryDirectory() as d:
            host = self.host(d)
            machine_id = self.preflight(host)
            pub = PK.actor_ceremony(host.keygen_host(), machine_id, key_factory=L2.pipeline_key,
                                    encrypt=L2.fake_encrypt([]))
            parsed = RC.KeyPublicationV1.from_dict(pub)
            self.assertEqual((pub["profile"], parsed.environment, parsed.key_id),
                             ("OWNER_PROD", "prod", "prod.owner-prod.actor.1"))
            for name in ("lilith-recovery-witness", "lilith-recovery-witness/credentials"):
                p = host.root / "etc" / name
                p.mkdir(mode=0o700)
                os.chmod(p, 0o700)
            machine_id, before = PK.witness_preflight(host.keygen_host(), euid=0, isolated=True, hostname="lilith-01",
                                                      machine_pin=PROD_MID)
            wit = PK.witness_ceremony(host.keygen_host(), machine_id, before, key_factory=L2.pipeline_key,
                                      encrypt=L2.fake_encrypt([]))
            self.assertEqual(B.WitnessKeyPublicationV1.from_dict(wit).witness_key_id, "prod.witness.owner-prod.1")

    def test_every_wrong_host_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            self.refused(lambda: self.preflight(self.host(d), hostname="lilith-dev-01"), "NOT_PROD_HOST")
        with tempfile.TemporaryDirectory() as d:                 # the DEV machine, even if pinned by mistake
            self.refused(lambda: self.preflight(self.host(d, machine_id=G.DEV_MACHINE_ID), pin=G.DEV_MACHINE_ID),
                         "NOT_PROD_HOST")
        with tempfile.TemporaryDirectory() as d:
            self.refused(lambda: self.preflight(self.host(d, deployment=None)), "DEPLOYMENT_NOT_OWNER_PROD")
        with tempfile.TemporaryDirectory() as d:
            self.refused(lambda: self.preflight(self.host(d, deployment=b'{"environment":"dev"}')), "DEPLOYMENT_INVALID")

    def test_publication_labels_are_bound_to_their_environment(self):
        prod_witness = PK.witness_publication(b"\x02" * 32, b"c", PROD_MID)
        self.assertEqual(B.WitnessKeyPublicationV1.from_dict(prod_witness).environment, "prod")
        forged = copy.deepcopy(prod_witness)
        forged["profile"] = "DEV_SYNTHETIC"                      # DEV label on a PROD key
        with self.assertRaises(Exception):
            B.WitnessKeyPublicationV1.from_dict(forged)
        forged = copy.deepcopy(G.witness_publication(b"\x02" * 32, b"c", G.DEV_MACHINE_ID))
        forged["profile"] = "OWNER_PROD"                         # PROD label on a DEV key
        with self.assertRaises(Exception):
            B.WitnessKeyPublicationV1.from_dict(forged)

    def test_the_kpan_twin(self):
        with tempfile.TemporaryDirectory() as d:
            host = self.host(d)
            unpinned = PKP.instance()
            with self.assertRaises(unpinned.Refused) as caught:
                unpinned.preflight(unpinned.Host(host.root), euid=0, isolated=True, hostname="lilith-01")
            self.assertEqual(caught.exception.reason, "PROD_MACHINE_ID_NOT_PINNED")
            dev_pinned = PKP.instance(machine_pin=G.DEV_MACHINE_ID)
            with self.assertRaises(dev_pinned.Refused) as caught:
                dev_pinned.preflight(dev_pinned.Host(host.root), euid=0, isolated=True, hostname="lilith-01")
            self.assertEqual(caught.exception.reason, "NOT_PROD_HOST")
        pinned = PKP.instance(machine_pin=PROD_MID)
        self.assertEqual((pinned.ENVIRONMENT, pinned.KEY_ID), ("OWNER_PROD", "kpan.owner-prod.01"))
        import trackb_kpan_keygen as KP                          # the DEV tool's own module is untouched
        self.assertEqual((KP.ENVIRONMENT, KP.KEY_ID, KP.DEV_HOSTNAME),
                         ("DEV_SYNTHETIC", "kpan.dev-synthetic.01", "lilith-dev-01"))


@unittest.skipUnless(X.POSIX, "owner and mode semantics are POSIX")
class MachineDigestPinTests(KeygenTests):
    """D-9: both PROD keygens pin lilith-01 by the SHA-256 of its exact /etc/machine-id bytes (what the COMPLETE audit
    run 2 recorded), never by a committed raw ID. The raw ID read on the host still goes into the custody evidence."""

    DIGEST = hashlib.sha256((PROD_MID + "\n").encode("ascii")).hexdigest()

    def actor(self, host, *, hostname="lilith-01", digest=None):
        return PK.actor_preflight(host.keygen_host(), euid=0, isolated=True, hostname=hostname,
                                  machine_digest=self.DIGEST if digest is None else digest)

    def kpan(self, host, *, hostname="lilith-01", digest=None):
        module = PKP.instance(machine_digest=self.DIGEST if digest is None else digest)
        return module, lambda: module.preflight(module.Host(host.root), euid=0, isolated=True, hostname=hostname)

    def test_the_pinned_host_passes_both_keygens_and_custody_keeps_the_raw_id(self):
        with tempfile.TemporaryDirectory() as d:
            host = self.host(d)
            machine_id = self.actor(host)
            self.assertEqual(machine_id, PROD_MID)
            self.assertEqual(PK.publication(F.raw_public("second-current"), b"TEST_ONLY c", machine_id)
                             ["custodyEvidence"]["machineId"], PROD_MID)          # evidence semantics unchanged
            module, run = self.kpan(host)
            try:                                  # past the identity gate the DEV tool needs K-WIT (not in this fixture)
                run()
            except module.Refused as exc:
                self.assertNotIn(exc.reason, ("NOT_PROD_HOST", "NOT_DEV_HOST", "PROD_MACHINE_ID_NOT_PINNED"))
            except OSError:
                pass
            self.assertEqual(module.DEV_MACHINE_ID, PROD_MID)                   # the digest-proven host, at run time

    def test_wrong_machine_wrong_host_dev_machine_and_malformed_ids_refuse(self):
        other = hashlib.sha256(b"fedcba9876543210fedcba9876543210\n").hexdigest()
        dev = hashlib.sha256((G.DEV_MACHINE_ID + "\n").encode("ascii")).hexdigest()
        cases = (
            ("wrong machine", {}, {"digest": other}),
            ("wrong host", {}, {"hostname": "lilith-dev-01"}),
            ("dev machine, even if pinned to it", {"machine_id": G.DEV_MACHINE_ID}, {"digest": dev}),
            ("uppercase", {"machine_id": PROD_MID.upper()}, {"digest": hashlib.sha256((PROD_MID.upper() + "\n").encode()).hexdigest()}),
        )
        for label, host_kw, call_kw in cases:
            with self.subTest(label), tempfile.TemporaryDirectory() as d:
                host = self.host(d, **host_kw)
                self.refused(lambda: self.actor(host, **call_kw), "NOT_PROD_HOST")
                module, run = self.kpan(host, **call_kw)
                with self.assertRaises(module.Refused) as caught:
                    run()
                # a wrong hostname is refused by the DEV K-PAN tool's own host check, whose code is NOT_DEV_HOST
                self.assertIn(caught.exception.reason, ("NOT_PROD_HOST", "NOT_DEV_HOST") if label == "wrong host"
                              else ("NOT_PROD_HOST",))
        for label, content in (("no newline", PROD_MID.encode()), ("two lines", (PROD_MID + "\n\n").encode()),
                               ("trailing space", (PROD_MID + " \n").encode())):
            with self.subTest(label), tempfile.TemporaryDirectory() as d:
                host = self.host(d)
                (host.root / "etc/machine-id").write_bytes(content)
                digest = hashlib.sha256(content).hexdigest()                     # even its own exact digest
                self.refused(lambda: self.actor(host, digest=digest), "NOT_PROD_HOST")
                module, run = self.kpan(host, digest=digest)
                with self.assertRaises(module.Refused):
                    run()

    def test_unpinned_source_refuses_and_no_raw_id_is_committed(self):
        with tempfile.TemporaryDirectory() as d:
            host = self.host(d)
            self.refused(lambda: PK.actor_preflight(host.keygen_host(), euid=0, isolated=True, hostname="lilith-01"),
                         "PROD_MACHINE_ID_NOT_PINNED")
            unpinned = PKP.instance()
            with self.assertRaises(unpinned.Refused) as caught:
                unpinned.preflight(unpinned.Host(host.root), euid=0, isolated=True, hostname="lilith-01")
            self.assertEqual(caught.exception.reason, "PROD_MACHINE_ID_NOT_PINNED")
        for name in ("owner_prod_keygen.py", "owner_prod_kpan_keygen.py"):
            source = (ROOT / "services/owner-memory-control/tools" / name).read_text(encoding="utf-8")
            self.assertNotIn("PROD_MACHINE_ID:", source)                       # the raw constant is gone
            self.assertEqual([h for h in re.findall(r"\b[0-9a-f]{32}\b", source) if h != G.DEV_MACHINE_ID], [], name)

    def test_the_raw_pin_seam_and_the_digest_agree(self):
        self.assertEqual(PK.machine_digest_pin(machine_pin=PROD_MID), self.DIGEST)
        with tempfile.TemporaryDirectory() as d:
            host = self.host(d)
            self.assertEqual(self.preflight(host), self.actor(host))           # the legacy test seam = the digest path


@unittest.skipUnless(X.POSIX, "file modes are POSIX")
class OwnerChainTests(unittest.TestCase):
    def test_the_prod_chain_verifies_only_under_a_prod_context(self):
        with tempfile.TemporaryDirectory() as d:
            key_path = Path(d) / "k-root-prod.der"
            root = PO.root_keygen(key_path, passphrase=PASS, key_factory=L2.pipeline_key)["registryRoot"]
            self.assertEqual((root["rootKeyId"], root["environment"]), ("prod.registry-root.owner-prod.1", "prod"))
            kact = PK.publication(F.raw_public("second-current"), b"TEST_ONLY c", PROD_MID)
            kwit = PK.witness_publication(F.raw_public("rogue-witness"), b"TEST_ONLY c", PROD_MID)
            key = PO._root_key(key_path, PASS)
            registry = PO.registry_v1(key, kact, epoch_random="2" * 32, policy_version=PO.POLICY_VERSION,
                                      issued_at="2026-11-04T00:00:00Z")
            anchor = PO.witness_anchor(kwit)
            result = PO.reproduce(registry, root, anchor, "2026-11-04T00:10:00Z")
            self.assertTrue(result["registryVerified"], result.get("registryReason"))
            self.assertEqual(result["ledgerGenesisOp"]["signingKeyIds"], ["prod.owner-prod.actor.1"])
            self.assertEqual(result["unsignedGenesis"]["witnessKeyId"], "prod.witness.owner-prod.1")
            self.assertEqual(result["genesisPin"]["environment"], "prod")

            ctx = A.AuthorityVerificationContextV1(
                environment="prod", purpose=A.NEW_ADMISSION, registry_root=A.TrustedRegistryRootV1.from_dict(root),
                trusted_minimum_registry_version=1,
                expected_recovery_epoch=A.RecoveryEpochV1.from_dict(registry["recoveryEpoch"]),
                policy_version=PO.POLICY_VERSION)
            self.assertEqual(AV.verify_authority_registry(context=ctx, registry=registry).status, AV.VERIFIED_REGISTRY)
            self.assertNotEqual(AV.verify_authority_registry(context=dataclasses.replace(ctx, environment="dev"),
                                                             registry=registry).status, AV.VERIFIED_REGISTRY)

            # --- no fallback ---
            dev_kact = copy.deepcopy(PB.publication(PB.P0, environment="dev"))
            with self.assertRaises(PO.OwnerToolError):          # a DEV K-ACT never enters a PROD registry
                PO.registry_v1(key, dev_kact, epoch_random="2" * 32, policy_version=PO.POLICY_VERSION,
                               issued_at="2026-11-04T00:00:00Z")
            dev_kwit = B.witness_publication(F.raw_public("witness"), b"TEST_ONLY c", PB.MACHINE_ID)
            with self.assertRaises(PO.OwnerToolError):          # a DEV K-WIT never anchors PROD
                PO.witness_anchor(dev_kwit)
            dev_root = dict(root, rootKeyId="test-only.registry-root.dev-synthetic.b1b3d.1")
            with self.assertRaises(PO.OwnerToolError) as caught:  # a test-only root claiming prod
                PO.reproduce(registry, dev_root, anchor, "2026-11-04T00:10:00Z")
            self.assertIn("GENESIS_REGISTRY_UNVERIFIED", str(caught.exception))

    def test_forms_are_closed(self):
        for argv in (["package-digest", "x"], ["root-keygen"], ["prod-root-keygen", "x"], ["nope"]):
            self.assertEqual(PO.main(argv, passphrase=lambda: PASS), 2, argv)


if __name__ == "__main__":
    unittest.main()
