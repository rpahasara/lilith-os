"""15B2b-B1b-3e B-3: real-acceptance switch, burned rehearsal identities, B-3 != B-5 (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-b3-real-acceptance.md.

Replicas and stores live in throwaway temporary directories. Chains are the
synthetic K-WIT-signed TEST chains. The real-profile code path is exercised on
them by treating TEST_ONLY as a real profile inside `real_path()` only. No real
owner storage, key, DEV, or cloud resource is touched.
"""

from __future__ import annotations

import hashlib
import os
import re
import unittest
from unittest import mock

import synthetic_authority as SA  # noqa: F401  (sets sys.path)
import synthetic_b1b3e as F
import test_b1b3e_pr3_p32_owner_freshness_tool as P32
import test_b1b3e_pr3_p36_acceptance_envelope as P36
from lilith_owner_memory import burned_identities as BI
from lilith_owner_memory import owner_acceptance as OA
from lilith_owner_memory import owner_freshness as OF
from lilith_owner_memory import owner_freshness_tool as T
from lilith_owner_memory import pr1_bootstrap as PB
from lilith_owner_memory import pr1b_sequencing as S
from lilith_owner_memory import rotation_contracts as RC

ROOT = SA.ROOT
DOCS = ROOT / "docs/architecture"
HOLD = DOCS / "slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-evidence-hold.md"       # run 1, §4
ACCEPTANCE = DOCS / "slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-acceptance.md"    # run 2, §4
MODULES = ROOT / "services/owner-memory-control/lilith_owner_memory"


def real_path():
    """Run the real-profile code path on the TEST world: TEST_ONLY counts as real here only."""
    return mock.patch.object(OA, "REAL_PROFILES", frozenset({"DEV_SYNTHETIC", "TEST_ONLY"}))


def burn(keys=(), registries=(), genesis=()):
    return mock.patch.multiple(BI, BURNED_PUBLIC_KEY_SHA256=frozenset(hashlib.sha256(k).hexdigest() for k in keys),
                               BURNED_REGISTRY_DIGESTS=frozenset(registries),
                               BURNED_GENESIS_WITNESS_DIGESTS=frozenset(genesis))


def _burned_table(path) -> dict[str, str]:
    section = path.read_text(encoding="utf-8").split("## 4. Burned TEST identities", 1)[1].split("\n## ", 1)[0]
    return dict(re.findall(r"^\| `(\w+)` \| `([0-9a-f]{64})` \|$", section, re.M))


class BurnedIdentityRecordTests(unittest.TestCase):
    def test_source_equals_the_two_accepted_records(self):
        keys, registries, genesis = set(), set(), set()
        for path in (HOLD, ACCEPTANCE):
            table = _burned_table(path)
            self.assertEqual(len(table), 6, path)
            for name, value in table.items():
                if name.endswith("PublicKeySha256"):
                    keys.add(value)
                elif name == "rehearsalRegistryDigest":
                    registries.add(value)
                elif name == "rehearsalGenesisCandidateDigest":
                    genesis.add(value)
                else:
                    self.fail(name)
        self.assertEqual((keys, registries, genesis), (set(BI.BURNED_PUBLIC_KEY_SHA256), set(BI.BURNED_REGISTRY_DIGESTS),
                                                      set(BI.BURNED_GENESIS_WITNESS_DIGESTS)))
        self.assertEqual(len(keys | registries | genesis), 12)

    def test_pure_check_per_role(self):
        for digest in BI.BURNED_REGISTRY_DIGESTS:
            self.assertEqual(BI.burned_identity(registry_digests=[digest]), f"registryDigest:{digest}")
        for digest in BI.BURNED_GENESIS_WITNESS_DIGESTS:
            self.assertEqual(BI.burned_identity(genesis_witness_digests=[digest]), f"genesisWitnessDigest:{digest}")
        key = os.urandom(32)
        self.assertIsNone(BI.burned_identity(public_keys=[key], registry_digests=["0" * 64],
                                             genesis_witness_digests=["1" * 64]))   # fresh identities pass
        with burn(keys=[key]):
            self.assertEqual(BI.burned_identity(public_keys=[key]), f"publicKeySha256:{hashlib.sha256(key).hexdigest()}")


class MappingTests(unittest.TestCase):
    """The burned values are compared with exactly the fields the rehearsal derived them from."""

    def test_genesis_candidate_digest_is_the_genesis_witness_digest(self):
        genesis = F.Scenario().writer.chain[0]
        unsigned = {k: genesis[k] for k in RC.WITNESS_V2_SIGNED_FIELDS}
        self.assertEqual(PB.candidate_digest(unsigned), RC.witness_v2_digest(genesis))
        self.assertEqual(PB.candidate_digest(unsigned), P32._genesis_digest([genesis]))   # the digest a pin must hold

    def test_registry_digest_is_the_registry_head_digest(self):
        trust = T.load_trust(P32.Workstation(self).trust)
        for registry in (F.v3(), F.v4(), F.v5()):
            self.assertEqual(RC.registry_head(registry).digest, RC.registry_digest(registry))
            self.assertIn(RC.registry_digest(registry), trust.registry_digests)

    def test_public_keys_are_raw_ed25519(self):
        trust = T.load_trust(P32.Workstation(self).trust)
        for key in (trust.registry_root.public_key, trust.anchor.public_key, *trust.authority_public_keys):
            self.assertEqual(len(key), 32)


class RealPathRefusalTests(unittest.TestCase):
    def setUp(self):
        self.s = F.Scenario()
        self.o = P36.Owner(self, self.s)
        self.trust = T.load_trust(self.o.trust)
        self.genesis = self.s.writer.chain

    def roles(self):
        chain = RC.RecoveryWitnessV2.from_verified_dict(self.genesis[0])
        return {"registryRoot": burn(keys=[self.trust.registry_root.public_key]),
                "witnessAnchor": burn(keys=[self.trust.anchor.public_key]),
                "registryKey": burn(keys=[sorted(self.trust.authority_public_keys)[0]]),
                "trustRegistry": burn(registries=[RC.registry_digest(F.v3())]),
                "chainRegistry": burn(registries=[chain.registry_digest]),
                "genesis": burn(genesis=[chain.digest])}

    def assertBurned(self, result):
        code, out = result[0], result[1]
        self.assertEqual((code, out["reason"]), (T.EXIT_REFUSED, BI.BURNED_REHEARSAL_IDENTITY), out)

    def test_propose_refuses_every_role(self):
        chain = self.o.chain(self.genesis)
        with real_path():
            for role, patch in self.roles().items():
                with self.subTest(role=role), patch:
                    code, result, out = self.o.propose("genesis", chain, self.o.pin_path)
                    self.assertBurned((code, result))
                    self.assertFalse(out.exists())                                  # no candidate written

    def test_package_append_and_envelope_refuse(self):
        with real_path():
            chain = self.o.chain(self.genesis)
            code, proposed, candidate = self.o.propose("genesis", chain, self.o.pin_path)
            self.assertEqual(code, 0, proposed)
            with self.roles()["genesis"]:
                self.assertBurned(self.o.cli("build-review-package", *self.o.replicas(), *self.o.world(chain),
                                             "--pin", str(self.o.pin_path), "--candidate", str(candidate),
                                             "--out", str(self.o.dir / "package-burned.json"),
                                             *[x for e in P36.EVIDENCE for x in ("--evidence", e)]))
                self.assertBurned(self.o.append(self.o.a, self.o.b, candidate, chain, self.o.pin_path,
                                                proposed["recordDigest"]))
            self.assertEqual(self.o.records(self.o.a), [])                            # nothing was appended
            chain, package, _ = self.o.record_ceremony("genesis", self.genesis)
            code, proposed, envelope = self.o.propose_envelope(package)
            self.assertEqual(code, 0, proposed)
            with self.roles()["witnessAnchor"]:
                self.assertBurned(self.o.append_envelope(self.o.sa, self.o.sb, envelope, chain,
                                                         proposed["envelopeDigest"]))
            self.assertEqual(self.o.bundles(self.o.sa), [])                           # no envelope written

    def test_fresh_identities_pass_the_whole_real_path(self):
        with real_path():
            chain, package, _ = self.o.record_ceremony("genesis", self.genesis)
            self.o.envelope_ceremony(chain, package)
            self.assertEqual(self.o.freshness(self.genesis)["freshness"], OF.CURRENT)
            self.assertEqual(self.o.acceptance()["state"], OA.ACCEPTANCE_COMPLETE)

    def test_synthetic_profile_is_not_checked(self):
        with self.roles()["genesis"]:                                                  # TEST_ONLY is not real here
            code, result, _ = self.o.propose("genesis", self.o.chain(self.genesis), self.o.pin_path)
            self.assertEqual(code, 0, result)


class B3IsNotB5Tests(unittest.TestCase):
    ALL_TRUE = {name: True for name in S.PRECONDITIONS}

    def test_eligibility_has_no_b3_input_and_still_needs_b5(self):
        self.assertEqual(set(S.PRECONDITIONS), {                                        # exactly; no B-3 input
            "p33Complete", "twoRealReplicasExist", "replicasCapabilityAdmitted", "replicaIndependenceEstablished",
            "replicasAgentUnreachableCopy", "ownerRegisterKnownEmpty", "pr3ToolingAccepted", "pr1aBaselineValid",
            "pr2InventoryRevalidated", "noUnreviewedTopologyChange", "openRisksAcknowledged", "pr1bAuthorized"})
        without_b5 = {**self.ALL_TRUE, "pr1bAuthorized": False}
        result = S.evaluate_eligibility(without_b5)
        self.assertEqual((result.status, result.reasons), (S.PR1B_NOT_ELIGIBLE, ("PR1B_NOT_AUTHORIZED",)))
        injected = S.evaluate_eligibility({**without_b5, "realAcceptanceEnabled": True})
        self.assertEqual(injected.status, S.PR1B_NOT_ELIGIBLE)
        self.assertIn("UNKNOWN_PRECONDITION:realAcceptanceEnabled", injected.reasons)
        self.assertTrue(S.evaluate_eligibility(self.ALL_TRUE).eligible)                # only B-5 itself flips it

    def test_b3_code_never_touches_pr1b_authorization(self):
        for name in ("owner_acceptance.py", "burned_identities.py"):
            source = (MODULES / name).read_text(encoding="utf-8")
            for word in ("pr1bAuthorized", "PR1B_ELIGIBLE", "evaluate_eligibility"):
                self.assertNotIn(word, source, (name, word))
        self.assertNotIn("REAL_ACCEPTANCE_ENABLED", (MODULES / "pr1b_sequencing.py").read_text(encoding="utf-8"))
        for tool in (ROOT / "services/authority-dev/ceremony").glob("*.py"):             # M-B1 tooling is untouched
            self.assertNotIn("owner_acceptance", tool.read_text(encoding="utf-8"), tool.name)

    def test_m_b1_is_not_authorized_by_this_patch(self):
        self.assertIs(OA.REAL_ACCEPTANCE_ENABLED, True)
        sequencer = S.BootstrapSequencerV1()
        evidence = {"offHostWorkstation": True, "kRootFingerprintRecordedOffHost": True}
        self.assertEqual(sequencer.advance("GENERATE_K_ROOT", evidence).reason, "TRANSITION_OUT_OF_ORDER")
        refused = sequencer.advance("CHECK_ELIGIBILITY", {"eligibilityResult": S.evaluate_eligibility(
            {**self.ALL_TRUE, "pr1bAuthorized": False})})
        self.assertEqual((refused.reason, refused.detail), (S.PR1B_NOT_ELIGIBLE, "PR1B_NOT_AUTHORIZED"))
        self.assertEqual(sequencer.advance("APPEND_RECORD_1_REPLICA_A", {}).reason, "TRANSITION_OUT_OF_ORDER")
        self.assertEqual((sequencer.state, sequencer.history), ("PR1B_INELIGIBLE", []))

    def test_freshness_unknown_and_zero_records_before_the_real_ceremony(self):
        w = P32.Workstation(self)
        with real_path():
            result = w.classify(F.Scenario().writer.chain)
            self.assertEqual(result["freshness"], OF.FRESHNESS_UNKNOWN)
        self.assertEqual((w.records(w.a), w.records(w.b)), ([], []))
        register, _ = T.load_register([w.a, w.b])
        self.assertEqual(S.owner_register_state(register), S.KNOWN_EMPTY)
        real = w.dir / "dev"
        os.mkdir(real)
        for name in ("a", "b"):                                                       # the real profile, empty
            code, out = w.cli("init-replica", "--replica", str(real / name), "--replica-id", f"owner-{name}-dev",
                              "--environment", "dev", "--profile", "DEV_SYNTHETIC")
            self.assertEqual(code, 0, out)
        register, replicas = T.load_register([real / "a", real / "b"])
        self.assertEqual((register.reason, [len(r.records) for r in replicas]), ("OWNER_REGISTER_EMPTY", [0, 0]))


class ReplicaSafetyTests(unittest.TestCase):
    def test_one_replica_alone_is_never_current_on_the_real_path(self):
        s = F.Scenario()
        o = P36.Owner(self, s)
        with real_path():
            chain = o.chain(s.writer.chain)
            code, proposed, candidate = o.propose("genesis", chain, o.pin_path)
            self.assertEqual(code, 0, proposed)
            code, out = o.append(o.a, o.b, candidate, chain, o.pin_path, proposed["recordDigest"])
            self.assertEqual((code, out["replication"]), (0, "PEER_PENDING"))
            self.assertNotEqual(o.classify(s.writer.chain)["freshness"], OF.CURRENT)   # A ahead of B
            code, alone = o.cli("classify", "--replica", str(o.a), *o.world(o.chain(s.writer.chain)))
            self.assertEqual((code, alone["freshness"]), (0, OF.FRESHNESS_UNKNOWN))
        self.assertEqual(T.MINIMUM_REPLICAS, 2)


if __name__ == "__main__":
    unittest.main()
