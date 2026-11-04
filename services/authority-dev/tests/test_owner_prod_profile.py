"""OWNER_PROD profile (P2; TEST_ONLY synthetic values; no host, no key, no provider).

Two properties, for every touched module:
  1. PROD works: the fixed OWNER_PROD shapes validate, compose and select from the root-installed deployment;
  2. the profiles are disjoint and DEV_SYNTHETIC is unchanged: DEV refuses every PROD value and PROD every DEV value
     (`test-only.` keys, the synthetic owner, `.invalid` relying parties, `dev`), and DEV's own values, DDL and
     refusal reasons are exactly what they were.
"""

from __future__ import annotations

import dataclasses
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _path in (ROOT / "services/owner-memory-control", ROOT / "services/owner-memory-control/tests",
              ROOT / "services/core-api", ROOT / "services/recovery-witness", ROOT / "services/authority-dev", HERE):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import pr1s_fixtures as X  # noqa: E402
from lilith_owner_memory import authority_contracts as A  # noqa: E402
from lilith_owner_memory import owner_acceptance as OA  # noqa: E402
from lilith_owner_memory import owner_freshness as OF  # noqa: E402
from lilith_owner_memory import recovery_contracts as RC  # noqa: E402

KEY = "11" * 32


class ContractTests(unittest.TestCase):
    def roots(self, key_id, environment="dev"):
        return A.TrustedRegistryRootV1(key_id, environment, bytes.fromhex(KEY))

    def anchors(self, key_id, environment="dev"):
        return RC.TrustedWitnessAnchorV1(key_id, environment, bytes.fromhex(KEY))

    def test_the_verifying_context_decides_the_root_class(self):
        for key_id, context, admissible in (("test-only.registry-root.x", "dev", True),
                                            ("test-only.registry-root.x", "test", True),
                                            ("prod.registry-root.x", "dev", False),      # DEV: exactly test_only
                                            ("prod.registry-root.x", "test", False),
                                            ("prod.registry-root.x", "prod", True),
                                            ("test-only.registry-root.x", "prod", False),  # never a test root in PROD
                                            ("other.registry-root.x", "prod", False)):
            with self.subTest(key_id=key_id, context=context):
                r = self.roots(key_id)
                self.assertEqual(r.admissible_for(context), admissible)
                if context != "prod":
                    self.assertEqual(r.admissible_for(context), r.test_only)

    def test_witness_anchors_likewise(self):
        for key_id, context, admissible in (("test-only.witness.x", "dev", True), ("prod.witness.x", "dev", False),
                                            ("prod.witness.x", "prod", True), ("test-only.witness.x", "prod", False)):
            with self.subTest(key_id=key_id, context=context):
                a = self.anchors(key_id)
                self.assertEqual(a.admissible_for(context), admissible)
                if context != "prod":
                    self.assertEqual(a.admissible_for(context), a.test_only)

    def test_no_reason_taxonomy_changed(self):
        from lilith_owner_memory import authority_verifier as AV
        from lilith_owner_memory import rotation_contracts as ROT
        self.assertEqual(len(AV.REASONS), 44)                                # the B1b-3b historical vector
        for reasons in (AV.REASONS, ROT.AUTHORIZATION_REASONS, RC.WITNESS_REASONS):
            self.assertFalse(any(r.endswith("_NOT_PROD") for r in reasons))
        self.assertIn("ENVIRONMENT_MISMATCH", AV.REASONS)
        self.assertIn("AUTHORIZATION_ENVIRONMENT_MISMATCH", ROT.AUTHORIZATION_REASONS)
        self.assertIn("WITNESS_ENVIRONMENT_MISMATCH", RC.WITNESS_REASONS)

    def test_profile_maps(self):
        self.assertEqual(OA.REAL_PROFILES, frozenset({"DEV_SYNTHETIC", "OWNER_PROD"}))
        self.assertEqual(OF.PROFILE_ENVIRONMENTS, {"TEST_ONLY": "test", "DEV_SYNTHETIC": "dev", "OWNER_PROD": "prod"})


@unittest.skipUnless(X.POSIX, "the authority packages are POSIX")
class ProfileTests(unittest.TestCase):
    def test_signer_profiles_are_disjoint(self):
        from lilith_authority_dev import profile as SP
        dev, prod = SP.dev_runtime_profile(), SP.prod_runtime_profile()
        self.assertEqual((dev.environment, dev.key_id, dev.policy_version),
                         ("dev", "test-only.dev-synthetic.actor.b1b3d.1", "policy.dev-synthetic.v1"))   # unchanged
        self.assertEqual((prod.environment, prod.key_id, prod.policy_version),
                         ("prod", "prod.owner-prod.actor.1", "policy.owner-prod.v1"))
        self.assertIs(type(SP.runtime_profile("dev")), SP.DevSyntheticSignerProfileV1)
        self.assertIs(type(SP.runtime_profile("prod")), SP.OwnerProdSignerProfileV1)
        for env in ("test", "", "PROD"):
            with self.assertRaises(SP.ProfileError):
                SP.runtime_profile(env)
        for bad in (dataclasses.replace(prod, key_id=dev.key_id), dataclasses.replace(prod, environment="dev"),
                    dataclasses.replace(prod, key_id="prod.dev-synthetic.actor.1")):
            with self.subTest(bad=bad), self.assertRaises(SP.ProfileError):
                bad.validate()
        for bad in (dataclasses.replace(dev, environment="prod"), dataclasses.replace(dev, key_id=prod.key_id)):
            with self.subTest(bad=bad), self.assertRaises(SP.ProfileError):
                bad.validate()

    def test_custody_profiles(self):
        from lilith_owner_memory import successor_custody as SC
        self.assertIs(SC.custody_profile("prod"), SC.OWNER_PROD_CUSTODY_PROFILE)
        self.assertEqual(SC.custody_profile("dev"), SC.DEV_SYNTHETIC_CUSTODY_PROFILE)
        self.assertEqual(SC.custody_profile("test").environment, "test")
        self.assertIs(SC.require_dev_synthetic(SC.OWNER_PROD_CUSTODY_PROFILE), SC.OWNER_PROD_CUSTODY_PROFILE)
        self.assertFalse(SC.is_dev_synthetic(SC.OWNER_PROD_CUSTODY_PROFILE))
        for bad in (dataclasses.replace(SC.OWNER_PROD_CUSTODY_PROFILE, initial_key_id=SC.INITIAL_KEY_ID),
                    dataclasses.replace(SC.DEV_SYNTHETIC_CUSTODY_PROFILE, environment="prod"),
                    dataclasses.replace(SC.OWNER_PROD_CUSTODY_PROFILE, environment="dev")):
            with self.subTest(bad=bad), self.assertRaises(Exception) as ctx:
                SC.require_dev_synthetic(bad)
            self.assertIn("PROFILE_NOT_DEV_SYNTHETIC", str(ctx.exception))
        self.assertIsNone(SC.successor_ordinal_of_key_id(SC.PROD_INITIAL_KEY_ID))   # never a DEV successor

    def test_witness_profiles(self):
        from lilith_owner_memory import pr1_bootstrap as B
        self.assertIs(B.witness_profile("prod"), B.OWNER_PROD_WITNESS_PROFILE)
        self.assertIsNone(B.witness_profile_reason(B.OWNER_PROD_WITNESS_PROFILE))
        self.assertIsNone(B.witness_profile_reason(B.DEV_SYNTHETIC_WITNESS_PROFILE))
        self.assertEqual(B.witness_profile_reason(dataclasses.replace(B.DEV_SYNTHETIC_WITNESS_PROFILE,
                                                                      environment="prod")), "WITNESS_PROFILE_PROD")
        self.assertEqual(B.witness_profile_reason(dataclasses.replace(B.OWNER_PROD_WITNESS_PROFILE,
                                                                      witness_key_id="prod.witness.other")),
                         "WITNESS_PROFILE_PROD")
        self.assertNotEqual(B.witness_profile_reason(dataclasses.replace(B.OWNER_PROD_WITNESS_PROFILE,
                                                                         environment="dev")), None)

    def test_ledger_schemas(self):
        from lilith_authority_dev import ledger as L
        self.assertEqual(L.schema_for("dev"), (L.SCHEMA, L.SCHEMA_FINGERPRINT, "DEV_SYNTHETIC"))
        self.assertEqual(L.schema_for("test")[0], L.SCHEMA)
        statements, fingerprint, profile = L.schema_for("prod")
        self.assertEqual((statements[1:], profile), (L.SCHEMA[1:], "OWNER_PROD"))
        self.assertNotEqual(fingerprint, L.SCHEMA_FINGERPRINT)
        for schema, good, bad in ((L.SCHEMA, ("dev", "DEV_SYNTHETIC"), ("prod", "OWNER_PROD")),
                                  (statements, ("prod", "OWNER_PROD"), ("dev", "DEV_SYNTHETIC"))):
            conn = sqlite3.connect(":memory:")
            for statement in schema:
                conn.execute(statement)
            conn.execute("INSERT INTO authority_meta_v1 VALUES (1, 1, ?, ?)", good)
            conn.execute("DELETE FROM authority_meta_v1")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO authority_meta_v1 VALUES (1, 1, ?, ?)", bad)
            conn.close()

    def test_server_environment_rules(self):
        from lilith_authority_dev import server as S
        S.check_environment({"LILITH_ENV": "dev"})
        S.check_environment({"LILITH_ENV": "prod"}, deployment_environment="prod")
        for environ, deployment, reason in (({"LILITH_ENV": "prod"}, "dev", "DEV_ONLY"),
                                            ({}, "dev", "DEV_ONLY"),
                                            ({"LILITH_ENV": "dev"}, "prod", "DEPLOYMENT_ENVIRONMENT_MISMATCH")):
            with self.subTest(environ=environ, deployment=deployment), self.assertRaises(S.ServerError) as ctx:
                S.check_environment(environ, deployment_environment=deployment)
            self.assertEqual(str(ctx.exception), reason)
        from lilith_recovery_witness import server as W
        W.check_environment({"LILITH_ENV": "dev"})
        W.check_environment({"LILITH_ENV": "prod"}, deployment_environment="prod")
        with self.assertRaises(W.ServerError):
            W.check_environment({"LILITH_ENV": "prod"})

    def test_privacy_paths(self):
        from lilith_memory import hermes_erasure_owner as HE
        from lilith_memory import privacy_forget_runner as FR
        self.assertEqual(FR.V1_ENVIRONMENTS, frozenset({"DEV_SYNTHETIC", "OWNER_PROD"}))
        source = (ROOT / "services/core-api/lilith_memory/hermes_erasure_owner.py").read_text(encoding="utf-8")
        self.assertIn('if deployment_environment != DEV_SYNTHETIC:', source)    # D-2: no Hermes owner in PROD
        self.assertEqual(HE.DEV_SYNTHETIC, "DEV_SYNTHETIC")

    def test_rr39_owner_context(self):
        from lilith_memory import owner_proof as P
        from lilith_owner_memory import verifier as V
        ctx = lambda **kw: types.SimpleNamespace(**{"deployment_environment": "prod", "owner_principal": "user:owner@example.org",  # noqa: E731
                                                    "rp_id": "lilith.example.org", "origin": "https://lilith.example.org", **kw})
        self.assertTrue(V._prod_owner(ctx()))
        for bad in ({"deployment_environment": "dev"}, {"rp_id": "x.invalid", "origin": "https://x.invalid"},
                    {"origin": "http://lilith.example.org"}, {"origin": "https://evil.example.com"},
                    {"owner_principal": P._DEV_SYNTHETIC_OWNER}):
            with self.subTest(bad=bad):
                self.assertFalse(V._prod_owner(ctx(**bad)))
        self.assertFalse(V._dev_synthetic_owner(ctx()))


@unittest.skipUnless(X.POSIX, "ownership and modes are POSIX")
class HostTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        from lilith_authority_host import inputs as HI
        from lilith_authority_host import paths as P
        self.HI, self.P = HI, P

    def write(self, absolute, value, mode=0o644):
        path = self.root / absolute.lstrip("/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value, sort_keys=True, separators=(",", ":")),
                        encoding="ascii")                               # host documents are canonical JSON
        os.chmod(path, mode)

    def deployment(self):
        return self.HI.read_deployment(root=self.root, owner_uid=os.getuid())

    def test_deployment_selection(self):
        self.assertEqual(self.deployment(), ("dev", "DEV_SYNTHETIC"))           # absent: DEV, as every DEV host
        self.write(self.P.DEPLOYMENT, {"schemaVersion": 1, "environment": "prod", "profile": "OWNER_PROD"})
        self.assertEqual(self.deployment(), ("prod", "OWNER_PROD"))
        for bad in ({"schemaVersion": 1, "environment": "prod", "profile": "DEV_SYNTHETIC"},
                    {"schemaVersion": 1, "environment": "test", "profile": "DEV_SYNTHETIC"},
                    {"schemaVersion": 2, "environment": "prod", "profile": "OWNER_PROD"},
                    {"schemaVersion": 1, "environment": "prod", "profile": "OWNER_PROD", "x": 1}, "not json"):
            with self.subTest(bad=bad):
                self.write(self.P.DEPLOYMENT, bad)
                with self.assertRaises(ValueError):
                    self.deployment()                                            # fail closed, never a fallback
        self.write(self.P.DEPLOYMENT, {"schemaVersion": 1, "environment": "prod", "profile": "OWNER_PROD"}, mode=0o664)
        with self.assertRaises(ValueError):
            self.deployment()

    def registration(self, environment, principal, rp, origin):
        import synthetic_chain as SCH
        cred = SCH.credential_dict(ownerPrincipal=principal, rpId=rp)
        return {"protocol": self.HI.OWNER_REGISTRATION_PROTOCOLS[environment], "schemaVersion": 1,
                "environment": environment, "ownerPrincipal": principal, "rpId": rp, "origin": origin,
                "registryTupleVersion": "v1", "privacyNoticeVersion": "v1", "brokerReleases": ["r1"],
                "credentials": [cred]}

    def test_owner_registration_per_environment(self):
        from lilith_memory import owner_proof as OP
        parse = self.HI.parse_owner_registration
        prod = self.registration("prod", "user:owner@example.org", "lilith.example.org", "https://lilith.example.org")
        self.assertEqual(parse(prod, environment="prod").rp_id, "lilith.example.org")
        dev = self.registration("dev", OP._DEV_SYNTHETIC_OWNER, OP.SYNTHETIC_RP_ID, OP.SYNTHETIC_ORIGIN)
        self.assertEqual(parse(dev, environment="dev").owner_principal, OP._DEV_SYNTHETIC_OWNER)   # DEV unchanged
        cases = ((dev, "prod", "OWNER_REGISTRATION_CONTEXT"),                    # DEV document on PROD
                 (prod, "dev", "OWNER_REGISTRATION_CONTEXT"),                    # PROD document on DEV
                 ({**dev, "protocol": self.HI.OWNER_REGISTRATION_PROTOCOLS["prod"], "environment": "prod"}, "prod",
                  "OWNER_REGISTRATION_NOT_OWNER_PROD"),                          # the synthetic owner on PROD
                 ({**prod, "rpId": "x.invalid", "origin": "https://x.invalid"}, "prod", "OWNER_REGISTRATION_NOT_OWNER_PROD"),
                 ({**prod, "origin": "http://lilith.example.org"}, "prod", "OWNER_REGISTRATION_NOT_OWNER_PROD"),
                 ({**prod, "credentials": [dict(prod["credentials"][0], rpId="other.example.org")]}, "prod",
                  "OWNER_REGISTRATION_CREDENTIAL_IDENTITY"))
        for document, environment, reason in cases:
            with self.subTest(reason=reason, environment=environment):
                with self.assertRaises(ValueError) as ctx:
                    parse(document, environment=environment)
                self.assertEqual(str(ctx.exception), reason)


if __name__ == "__main__":
    unittest.main()
