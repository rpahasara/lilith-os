"""15B2b-B1b-3e PR-3 P3-6: owner acceptance envelope foundation (TEST-ONLY, offline).

Record: docs/architecture/slice-15b2b-b1b3e-pr3-owner-acceptance-envelope.md.

Replicas and acceptance stores are temporary directories. Chains are real
K-WIT-signed TEST chains (TEST_ONLY profile). The real owner Replica A is
never touched. The real (DEV_SYNTHETIC) profile stays blocked.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import unittest
from pathlib import Path

import synthetic_authority as SA  # noqa: F401  (sets sys.path)
import synthetic_b1b3e as F
import test_b1b3e_pr3_p32_owner_freshness_tool as P32
from lilith_owner_memory import owner_acceptance as OA
from lilith_owner_memory import owner_freshness as OF
from lilith_owner_memory import owner_freshness_tool as T
from lilith_owner_memory import pr1b_sequencing as S
from lilith_owner_memory import recovery_contracts as R

ROOT = SA.ROOT
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-pr3-owner-acceptance-envelope.md"
ENV, PROFILE = F.ENV, "TEST_ONLY"
EVIDENCE = [f"PR2_REVALIDATION={hashlib.sha256(b'pr2 revalidation record').hexdigest()}",
            f"P3_3_INDEPENDENCE={hashlib.sha256(b'p3-3 independence evidence').hexdigest()}"]


def ledger_step(s: F.Scenario, challenge_id: str) -> None:
    lep = R.ledger_epoch_id(F.E2, ENV)
    s.commit(lambda st: st.prepare(challenge_id, lep, ready=F.seeded_ready(st)))


class Owner(P32.Workstation):
    def __init__(self, test: unittest.TestCase, scenario: F.Scenario):
        super().__init__(test)
        self.scenario = scenario
        self.pin_path = self.pin(P32._genesis_digest(scenario.writer.chain))
        self.sa, self.sb = self.dir / "acceptance-a", self.dir / "acceptance-b"
        for store, copy_id in ((self.sa, "vault-a"), (self.sb, "offline-b")):
            code, out = self.cli("init-acceptance-store", "--store", str(store), "--custody-copy-id", copy_id,
                                 "--environment", ENV, "--profile", PROFILE)
            assert code == 0, out

    def stores(self) -> list[str]:
        return ["--store", str(self.sa), "--store", str(self.sb)]

    def acceptance(self) -> dict:
        code, result = self.cli("classify-acceptance", *self.replicas(), *self.stores(), "--pin", str(self.pin_path))
        assert code == 0, result
        return result

    def freshness(self, chain_docs) -> dict:
        return self.classify(chain_docs)

    def record_ceremony(self, kind: str, chain_docs, evidence=EVIDENCE) -> tuple[Path, Path, dict]:
        """P3-6 steps 1–10: package BEFORE the append, then the two record appends."""
        chain = self.chain(chain_docs)
        code, proposed, candidate = self.propose(kind, chain, self.pin_path)
        assert code == 0, proposed
        self.n += 1
        package = self.dir / f"package-{self.n}.json"
        code, built = self.cli("build-review-package", *self.replicas(), *self.world(chain), "--pin",
                               str(self.pin_path), "--candidate", str(candidate), "--out", str(package),
                               *[x for item in evidence for x in ("--evidence", item)])
        assert code == 0, built
        for target, peer in ((self.a, self.b), (self.b, self.a)):
            code, out = self.append(target, peer, candidate, chain, self.pin_path, proposed["recordDigest"])
            assert code == 0, out
        return chain, package, built

    def propose_envelope(self, package: Path) -> tuple[int, dict, Path]:
        self.n += 1
        out = self.dir / f"envelope-{self.n}.json"
        code, result = self.cli("propose-envelope", *self.replicas(), *self.stores(), "--package", str(package),
                                "--out", str(out))
        return code, result, out

    def append_envelope(self, store: Path, peer: Path, candidate: Path, chain: Path, confirm: str):
        return self.cli("append-envelope", *self.replicas(), *self.world(chain), "--pin", str(self.pin_path),
                        "--store", str(store), "--peer-store", str(peer), "--candidate", str(candidate),
                        "--confirm-digest", confirm)

    def envelope_ceremony(self, chain: Path, package: Path, observe=None) -> dict:
        """P3-6 steps 11–13."""
        code, proposed, candidate = self.propose_envelope(package)
        assert code == 0, proposed
        first = self.append_envelope(self.sa, self.sb, candidate, chain, proposed["envelopeDigest"])
        assert first[0] == 0 and first[1]["replication"] == "PEER_PENDING", first
        if observe:
            observe(self.acceptance())
        second = self.append_envelope(self.sb, self.sa, candidate, chain, proposed["envelopeDigest"])
        assert second[0] == 0 and second[1]["replication"] == "COPIES_IDENTICAL", second
        return proposed

    def bundles(self, store: Path) -> list[tuple[str, dict]]:
        directory = store / T.ENVELOPES
        return [(n, json.loads((directory / n).read_bytes())) for n in sorted(os.listdir(directory))]

    def put(self, store: Path, bundle: dict) -> str:
        """Write a bundle by hand (out-of-band), under its canonical name."""
        digest = OA.envelope_digest(bundle["envelope"])
        name = f"{bundle['envelope']['freshnessRecordVersion']:06d}-{digest}.json"
        (store / T.ENVELOPES / name).write_bytes(OF.record_bytes(bundle))
        return name


class CeremonyTests(unittest.TestCase):
    def setUp(self):
        self.s = F.Scenario()
        self.o = Owner(self, self.s)

    def test_full_record_1_acceptance_ceremony(self):
        genesis = self.s.writer.chain
        chain, package, built = self.o.record_ceremony("genesis", genesis)
        record_name = self.o.records(self.o.a)[0]
        record_bytes = (self.o.a / T.RECORDS / record_name).read_bytes()
        record_digest = OF.record_digest(json.loads(record_bytes))
        self.assertEqual(self.o.freshness(genesis)["freshness"], OF.CURRENT)
        self.assertEqual(self.o.acceptance()["state"], OA.ACCEPTANCE_NOT_PRESENT)     # CURRENT without evidence
        seen = []
        proposed = self.o.envelope_ceremony(chain, package, seen.append)
        self.assertEqual(seen[0]["state"], OA.ACCEPTANCE_PARTIAL)
        final = self.o.acceptance()
        self.assertEqual((final["state"], final["evidencedRecordVersion"]), (OA.ACCEPTANCE_COMPLETE, 1))
        # record identity unchanged by the envelope
        self.assertEqual((self.o.a / T.RECORDS / record_name).read_bytes(), record_bytes)
        self.assertEqual(OF.record_digest(json.loads(record_bytes)), record_digest)
        envelope = self.o.bundles(self.o.sa)[0][1]["envelope"]
        self.assertEqual(envelope["freshnessRecordDigest"], record_digest)
        self.assertIsNone(envelope["previousAcceptanceEnvelopeDigest"])
        self.assertEqual(envelope["acceptanceMethod"], OA.EXPLICIT_OWNER_DIGEST_CONFIRMATION)
        self.assertEqual(envelope["ownerReviewPackageDigest"], built["packageDigest"])
        self.assertEqual(proposed["envelopeDigest"], OA.envelope_digest(envelope))
        # replica roots unchanged in shape; evidence lives in sibling stores
        self.assertEqual(sorted(os.listdir(self.o.a)), [T.MANIFEST, T.RECORDS])
        self.assertEqual(sorted(os.listdir(self.o.sa)), [T.ACCEPTANCE_MANIFEST, T.ENVELOPES])
        self.assertEqual(self.o.freshness(genesis)["freshness"], OF.CURRENT)            # freshness unaffected

    def test_successor_envelope_chains(self):
        chain, package, _ = self.o.record_ceremony("genesis", self.s.writer.chain)
        self.o.envelope_ceremony(chain, package)
        self.s.to_current()
        chain2, package2, built2 = self.o.record_ceremony("accept", self.s.writer.chain, evidence=[])
        self.assertEqual(self.o.acceptance()["state"], OA.ACCEPTANCE_NOT_PRESENT)     # newer record, stale envelope
        self.o.envelope_ceremony(chain2, package2)
        final = self.o.acceptance()
        self.assertEqual((final["state"], final["evidencedRecordVersion"]), (OA.ACCEPTANCE_COMPLETE, 2))
        (_, first), (_, second) = self.o.bundles(self.o.sa)
        self.assertEqual(second["envelope"]["previousAcceptanceEnvelopeDigest"], OA.envelope_digest(first["envelope"]))
        self.assertEqual(second["package"]["packageKind"], OA.SUCCESSOR)
        self.assertEqual(second["package"]["freshnessBefore"]["freshness"], OF.AHEAD_UNACCEPTED)

    def test_package_is_reproducible_and_record_1_needs_owner_evidence(self):
        chain = self.o.chain(self.s.writer.chain)
        _, proposed, candidate = self.o.propose("genesis", chain, self.o.pin_path)
        outs = []
        for index in range(2):
            out = self.o.dir / f"pkg-repro-{index}.json"
            code, result = self.o.cli("build-review-package", *self.o.replicas(), *self.o.world(chain), "--pin",
                                      str(self.o.pin_path), "--candidate", str(candidate), "--out", str(out),
                                      *[x for item in EVIDENCE for x in ("--evidence", item)])
            self.assertEqual(code, 0, result)
            outs.append(out.read_bytes())
        self.assertEqual(outs[0], outs[1])                                             # independent rebuild
        code, result = self.o.cli("build-review-package", *self.o.replicas(), *self.o.world(chain), "--pin",
                                  str(self.o.pin_path), "--candidate", str(candidate), "--out",
                                  str(self.o.dir / "pkg-no-evidence.json"))
        self.assertEqual((code, result["reason"]), (T.EXIT_REFUSED, "PACKAGE_NOT_BUILDABLE"))
        self.assertIn("RECORD_1_EVIDENCE_MISSING", result["detail"])
        self.assertNotIn("/", json.dumps(json.loads(outs[0])["attachedEvidence"]))   # no paths in the package
        package = json.loads(outs[0])
        for forbidden in ("path", "mount", "device", "time", "At"):
            self.assertFalse(any(forbidden in key for key in package), forbidden)

    def test_candidate_envelope_is_not_acceptance_and_confirmation_is_required(self):
        chain, package, _ = self.o.record_ceremony("genesis", self.s.writer.chain)
        code, proposed, candidate = self.o.propose_envelope(package)
        self.assertEqual((code, proposed["accepted"]), (0, False))
        self.assertEqual(self.o.acceptance()["state"], OA.ACCEPTANCE_NOT_PRESENT)
        for confirm in ("", proposed["envelopeDigest"][:-1] + "0", F.digest("other")):
            code, result = self.o.append_envelope(self.o.sa, self.o.sb, candidate, chain, confirm)
            self.assertEqual(code, T.EXIT_REFUSED)
            self.assertIn(result["reason"], {"OWNER_CONFIRMATION_REQUIRED", "OWNER_CONFIRMATION_MISMATCH"})
        self.assertEqual(self.o.bundles(self.o.sa), [])
        document = json.loads(candidate.read_text(encoding="utf-8"))
        forged = self.o.write("forged-envelope.json", {**document, "accepted": True})
        self.assertEqual(self.o.append_envelope(self.o.sa, self.o.sb, forged, chain, proposed["envelopeDigest"])[1]
                         ["reason"], "ENVELOPE_CANDIDATE_MALFORMED")

    def test_hand_edited_package_is_refused(self):
        chain, package, _ = self.o.record_ceremony("genesis", self.s.writer.chain)
        _, proposed, candidate = self.o.propose_envelope(package)
        document = json.loads(candidate.read_text(encoding="utf-8"))
        document["package"]["presentedChainLength"] = 2
        document["envelope"]["ownerReviewPackageDigest"] = OA.review_package_digest(document["package"])
        document["envelopeDigest"] = OA.envelope_digest(document["envelope"])
        edited = self.o.write("edited-envelope.json", document)
        code, result = self.o.append_envelope(self.o.sa, self.o.sb, edited, chain, document["envelopeDigest"])
        self.assertEqual((code, result["reason"]), (T.EXIT_REFUSED, "PACKAGE_NOT_REPRODUCIBLE"))

    def test_envelope_for_stale_record_is_not_buildable(self):
        chain, package, _ = self.o.record_ceremony("genesis", self.s.writer.chain)
        self.s.to_current()
        self.o.record_ceremony("accept", self.s.writer.chain, evidence=[])            # record 2, no envelope 1
        code, result, _ = self.o.propose_envelope(package)                            # package for record 1
        self.assertEqual((code, result["reason"]), (T.EXIT_REFUSED, "ENVELOPE_NOT_NEXT"))


class AttackTests(unittest.TestCase):
    """Each case starts from a COMPLETE record-1 acceptance."""

    def setUp(self):
        self.s = F.Scenario()
        self.o = Owner(self, self.s)
        self.chain, self.package, _ = self.o.record_ceremony("genesis", self.s.writer.chain)
        self.o.envelope_ceremony(self.chain, self.package)
        self.assertEqual(self.o.acceptance()["state"], OA.ACCEPTANCE_COMPLETE)
        self.name, self.bundle = self.o.bundles(self.o.sa)[0]

    def replace_in_both(self, bundle: dict) -> None:
        for store in (self.o.sa, self.o.sb):
            os.unlink(store / T.ENVELOPES / self.name)
            self.o.put(store, bundle)

    def mutated(self, **envelope_changes) -> dict:
        bundle = copy.deepcopy(self.bundle)
        bundle["envelope"].update(envelope_changes)
        return bundle

    def test_valid_record_without_envelope(self):
        for store in (self.o.sa, self.o.sb):
            os.unlink(store / T.ENVELOPES / self.name)
        self.assertEqual(self.o.acceptance()["state"], OA.ACCEPTANCE_NOT_PRESENT)
        self.assertEqual(self.o.freshness(self.s.writer.chain)["freshness"], OF.CURRENT)   # not downgraded

    def test_wrong_freshness_digest(self):
        self.replace_in_both(self.mutated(freshnessRecordDigest=F.digest("other record")))
        result = self.o.acceptance()
        self.assertEqual((result["state"], result["reason"]), (OA.ACCEPTANCE_INVALID, "ENVELOPE_RECORD_MISMATCH"))

    def test_wrong_package_digest(self):
        bundle = copy.deepcopy(self.bundle)
        bundle["package"]["attachedEvidence"]["PR2_REVALIDATION"] = F.digest("another package")
        self.replace_in_both(bundle)
        self.assertEqual(self.o.acceptance()["reason"], "ENVELOPE_PACKAGE_MISMATCH")

    def test_wrong_replica_set_digest(self):
        other = OA.replica_set_digest(environment=ENV, authority_profile=PROFILE, replica_ids=["vault-a", "usb-z"])
        self.replace_in_both(self.mutated(replicaSetDigest=other))
        self.assertEqual(self.o.acceptance()["reason"], "ENVELOPE_REPLICA_SET_MISMATCH")
        with self.assertRaises(Exception):
            OA.replica_set_digest(environment=ENV, authority_profile=PROFILE, replica_ids=["vault-a", "vault-a"])
        self.assertEqual(OA.replica_set_digest(environment=ENV, authority_profile=PROFILE,
                                               replica_ids=["offline-b", "vault-a"]),
                         OA.replica_set_digest(environment=ENV, authority_profile=PROFILE,
                                               replica_ids=["vault-a", "offline-b"]))

    def test_duplicate_and_skipped_envelope_versions(self):
        self.o.put(self.o.sa, self.mutated(ownerReviewPackageDigest=F.digest("dup")))
        with self.assertRaises(T.ToolRefusal) as caught:
            T.load_acceptance_store(self.o.sa)
        self.assertEqual(caught.exception.reason, "ENVELOPE_VERSION_DUPLICATED")
        self.assertEqual(self.o.acceptance()["state"], OA.ACCEPTANCE_UNKNOWN)
        shutil.rmtree(self.o.sb / T.ENVELOPES)
        os.mkdir(self.o.sb / T.ENVELOPES)
        skipped = self.mutated(freshnessRecordVersion=3, previousAcceptanceEnvelopeDigest=F.digest("x"))
        self.o.put(self.o.sb, skipped)
        with self.assertRaises(T.ToolRefusal) as caught:
            T.load_acceptance_store(self.o.sb)
        self.assertEqual(caught.exception.reason, "ENVELOPE_VERSION_GAP")

    def test_same_version_different_digest_across_copies(self):
        os.unlink(self.o.sb / T.ENVELOPES / self.name)
        bundle = copy.deepcopy(self.bundle)
        bundle["package"]["attachedEvidence"]["P3_3_INDEPENDENCE"] = F.digest("other evidence")
        bundle["envelope"]["ownerReviewPackageDigest"] = OA.review_package_digest(bundle["package"])
        self.o.put(self.o.sb, bundle)
        result = self.o.acceptance()
        self.assertEqual((result["state"], result["reason"]), (OA.ACCEPTANCE_CONFLICTING, "ACCEPTANCE_COPIES_FORKED"))

    def test_envelope_chain_fork_and_break(self):
        self.s.to_current()
        chain2, package2, _ = self.o.record_ceremony("accept", self.s.writer.chain, evidence=[])
        self.o.envelope_ceremony(chain2, package2)
        name2, second = self.o.bundles(self.o.sa)[1]
        broken = copy.deepcopy(second)
        broken["envelope"]["previousAcceptanceEnvelopeDigest"] = F.digest("not envelope 1")
        for store in (self.o.sa, self.o.sb):
            os.unlink(store / T.ENVELOPES / name2)
            self.o.put(store, broken)
        self.assertEqual(self.o.acceptance()["reason"], "PREVIOUS_ENVELOPE_DIGEST_MISMATCH")
        for store in (self.o.sa, self.o.sb):
            for name in os.listdir(store / T.ENVELOPES):
                if name.startswith("000002-"):
                    os.unlink(store / T.ENVELOPES / name)
        self.o.put(self.o.sa, second)
        forked = copy.deepcopy(second)
        forked["package"]["attachedEvidence"] = {"LATE_NOTE": F.digest("late")}
        forked["envelope"]["ownerReviewPackageDigest"] = OA.review_package_digest(forked["package"])
        self.o.put(self.o.sb, forked)
        self.assertEqual(self.o.acceptance()["state"], OA.ACCEPTANCE_CONFLICTING)

    def test_stale_freshness_record_with_newer_envelope(self):
        snapshot = [self.o.dir / "snap-a", self.o.dir / "snap-b"]
        shutil.copytree(self.o.a, snapshot[0])
        shutil.copytree(self.o.b, snapshot[1])
        self.s.to_current()
        chain2, package2, _ = self.o.record_ceremony("accept", self.s.writer.chain, evidence=[])
        self.o.envelope_ceremony(chain2, package2)
        for live, saved in ((self.o.a, snapshot[0]), (self.o.b, snapshot[1])):   # freshness replicas rolled back
            shutil.rmtree(live)
            shutil.copytree(saved, live)
        result = self.o.acceptance()
        self.assertEqual((result["state"], result["reason"]), (OA.ACCEPTANCE_CONFLICTING, "ENVELOPE_AHEAD_OF_REGISTER"))
        # freshness alone (the joint-rollback limitation) would call the old world CURRENT; acceptance evidence exposes it
        self.assertEqual(self.o.freshness(self.s.writer.chain[:1])["freshness"], OF.CURRENT)

    def test_envelope_rolled_back_but_record_survives(self):
        self.s.to_current()
        chain2, package2, _ = self.o.record_ceremony("accept", self.s.writer.chain, evidence=[])
        self.o.envelope_ceremony(chain2, package2)
        for store in (self.o.sa, self.o.sb):
            for name in os.listdir(store / T.ENVELOPES):
                if name.startswith("000002-"):
                    os.unlink(store / T.ENVELOPES / name)
        result = self.o.acceptance()
        self.assertEqual((result["state"], result["evidencedRecordVersion"]), (OA.ACCEPTANCE_NOT_PRESENT, 1))
        self.assertEqual(self.o.freshness(self.s.writer.chain)["freshness"], OF.CURRENT)   # not downgraded

    def test_copied_envelope_from_another_environment_or_profile(self):
        def install(bundle):
            for store in (self.o.sa, self.o.sb):
                shutil.rmtree(store / T.ENVELOPES)
                os.mkdir(store / T.ENVELOPES)
                self.o.put(store, bundle)

        for changes in ({"environment": "dev"}, {"environment": "dev", "authorityProfile": "DEV_SYNTHETIC"},
                        {"authorityProfile": "DEV_SYNTHETIC"}):
            bundle = self.mutated(**changes)
            if changes != {"environment": "dev", "authorityProfile": "DEV_SYNTHETIC"}:
                with self.assertRaises(Exception):                 # env/profile disagree: malformed
                    OA.OwnerFreshnessAcceptanceEnvelopeV1.from_dict(bundle["envelope"])
            install(bundle)
            with self.assertRaises(T.ToolRefusal) as caught:
                T.load_acceptance_store(self.o.sa)
            self.assertIn(caught.exception.reason, {"ENVELOPE_MALFORMED", "ENVELOPE_PROFILE_MISMATCH"}, changes)
            self.assertEqual(self.o.acceptance()["state"], OA.ACCEPTANCE_UNKNOWN)
        install(self.bundle)
        self.assertEqual(self.o.acceptance()["state"], OA.ACCEPTANCE_COMPLETE)
        dev_like = self.mutated(environment="dev", authorityProfile="DEV_SYNTHETIC")["envelope"]
        register = T.load_register([self.o.a, self.o.b])[0]
        pure = OA.classify_acceptance(register=register,
                                      copies=[[{"envelope": dev_like, "package": self.bundle["package"]}]] * 2,
                                      replica_ids=["vault-a", "offline-b"], pin=json.loads(self.o.pin_path.read_text()))
        self.assertEqual((pure.state, pure.reason), (OA.ACCEPTANCE_INVALID, "ENVELOPE_PROFILE_MISMATCH"))

    def test_unsigned_envelope_is_accepted_only_through_custody_and_ceremony(self):
        # The only writer requires the repeated digest (tested in CeremonyTests). An envelope
        # written out of band is structurally indistinguishable: under PR3-D2 its authority is
        # custody of the owner copies, not the file. This is the documented limitation.
        for store in (self.o.sa, self.o.sb):
            os.unlink(store / T.ENVELOPES / self.name)
            self.o.put(store, self.bundle)
        self.assertEqual(self.o.acceptance()["state"], OA.ACCEPTANCE_COMPLETE)
        self.assertEqual(self.bundle["envelope"]["acceptanceMethod"], OA.EXPLICIT_OWNER_DIGEST_CONFIRMATION)

    def test_signature_presence_never_implies_acceptance(self):
        signed = copy.deepcopy(self.bundle)
        signed["envelope"]["signature"] = "A" * 86
        with self.assertRaises(Exception):
            OA.OwnerFreshnessAcceptanceEnvelopeV1.from_dict(signed["envelope"])
        with_proof = {**copy.deepcopy(self.bundle), "presenceProof": {"signature": "A" * 86}}
        hardware = self.mutated(acceptanceMethod="HARDWARE_OWNER_PRESENCE_V1")
        with self.assertRaises(Exception):
            OA.OwnerFreshnessAcceptanceEnvelopeV1.from_dict(hardware["envelope"])
        for bad in (with_proof, hardware):
            os.unlink(self.o.sa / T.ENVELOPES / self.name)
            name = f"000001-{OA.envelope_digest(self.bundle['envelope'])}.json"
            (self.o.sa / T.ENVELOPES / name).write_bytes(OF.record_bytes(bad))
            with self.assertRaises(T.ToolRefusal) as caught:
                T.load_acceptance_store(self.o.sa)
            self.assertIn(caught.exception.reason, {"ENVELOPE_MALFORMED", "ENVELOPE_NAME_MISMATCH"})
            os.unlink(self.o.sa / T.ENVELOPES / name)
            self.o.put(self.o.sa, self.bundle)
        self.assertIn("HARDWARE_OWNER_PRESENCE_V1", OA.RESERVED_METHODS)
        self.assertNotIn("HARDWARE_OWNER_PRESENCE_V1", OA.ACCEPTANCE_METHODS)

    def test_stores_must_pair_with_replicas_and_stay_outside_replica_roots(self):
        code, result = self.o.cli("init-acceptance-store", "--store", str(self.o.a / "acceptance"),
                                  "--custody-copy-id", "vault-a", "--environment", ENV, "--profile", PROFILE)
        self.assertEqual(result["reason"], "ACCEPTANCE_STORE_INSIDE_REPLICA")
        stray = self.o.dir / "acceptance-stray"
        self.o.cli("init-acceptance-store", "--store", str(stray), "--custody-copy-id", "usb-z",
                   "--environment", ENV, "--profile", PROFILE)
        code, result = self.o.cli("classify-acceptance", *self.o.replicas(), "--store", str(self.o.sa), "--store",
                                  str(stray), "--pin", str(self.o.pin_path))
        self.assertEqual((result["state"], result["reason"]),
                         (OA.ACCEPTANCE_UNKNOWN, "ACCEPTANCE_STORES_NOT_PAIRED_WITH_REPLICAS"))
        shutil.rmtree(self.o.sb)
        self.assertEqual(self.o.acceptance()["state"], OA.ACCEPTANCE_UNKNOWN)


class BoundaryTests(unittest.TestCase):
    def test_p3_3_hard_block_on_real_profile(self):
        self.assertIs(OA.REAL_ACCEPTANCE_ENABLED, False)
        self.assertEqual(OA.real_acceptance_block("DEV_SYNTHETIC"), "P3_3_STORAGE_INCOMPLETE")
        self.assertIsNone(OA.real_acceptance_block("TEST_ONLY"))
        complete = OA.AcceptanceResultV1(OA.ACCEPTANCE_COMPLETE, evidenced_record_version=1)
        self.assertEqual(OA.real_acceptance_gate(complete, authority_profile="TEST_ONLY"),
                         (OA.REAL_ACCEPTANCE_GATE_BLOCKED, "SYNTHETIC_PROFILE"))        # synthetic never satisfies
        self.assertEqual(OA.real_acceptance_gate(complete, authority_profile="DEV_SYNTHETIC"),
                         (OA.REAL_ACCEPTANCE_GATE_BLOCKED, "P3_3_STORAGE_INCOMPLETE"))
        w = P32.Workstation(self)
        dummy = w.write("dummy.json", {})
        code, result = w.cli("append", "--replica", str(w.a), "--peer", str(w.b), "--candidate", str(dummy),
                             "--trust", str(w.trust), "--chain", str(dummy), "--environment", "dev",
                             "--profile", "DEV_SYNTHETIC", "--pin", str(dummy), "--confirm-digest", "x")
        self.assertEqual((code, result["reason"], result["detail"]),
                         (T.EXIT_REFUSED, "REAL_ACCEPTANCE_DISABLED", "P3_3_STORAGE_INCOMPLETE"))
        code, result = w.cli("append-envelope", "--replica", str(w.a), "--replica", str(w.b), "--trust", str(w.trust),
                             "--chain", str(dummy), "--environment", "dev", "--profile", "DEV_SYNTHETIC", "--pin",
                             str(dummy), "--store", str(w.a), "--peer-store", str(w.b), "--candidate", str(dummy),
                             "--confirm-digest", "x")
        self.assertEqual((code, result["reason"]), (T.EXIT_REFUSED, "REAL_ACCEPTANCE_DISABLED"))

    def test_envelope_scope_authorizes_nothing(self):
        for name in OA.ENVELOPE_FIELDS:
            for word in ("authoriz", "grant", "permit", "allow", "memory", "privacy", "activation", "time", "At"):
                self.assertNotIn(word, name, name)
        acceptance = OA.AcceptanceResultV1(OA.ACCEPTANCE_COMPLETE, evidenced_record_version=1)
        for operation in OF.GATED_OPERATIONS:
            self.assertFalse(OF.freshness_gate(acceptance, operation).met)          # never a freshness result
        current = OF.FreshnessResultV1(OF.AUTHENTIC, OF.CURRENT)
        self.assertEqual(S.first_memory_gate("FULL_READINESS", freshness=current, a1_a7_accepted=False,
                                             owner_accepted_proofs=False), (S.FIRST_MEMORY_BLOCKED, "A1_A7_REQUIRED"))

    def test_sequencer_requires_complete_acceptance_after_current(self):
        order = [step.action for step in S.STEPS]
        self.assertLess(order.index("APPEND_RECORD_1_REPLICA_B"), order.index("APPEND_ENVELOPE_1_COPY_A"))
        self.assertLess(order.index("APPEND_ENVELOPE_1_COPY_B"), order.index("WRITE_HELD"))
        self.assertEqual(S.ACCEPTANCE_REQUIRED, frozenset(order[order.index("APPEND_ENVELOPE_1_COPY_B"):]))
        self.assertNotIn("APPEND_RECORD_1_REPLICA_B", S.ACCEPTANCE_REQUIRED)       # CURRENT never waits on the envelope
        s = S.BootstrapSequencerV1()
        for step in S.STEPS:
            if step.action == "WRITE_HELD":
                break
            evidence = {name: True for name in step.evidence}
            if step.action == "CHECK_ELIGIBILITY":
                evidence = {"eligibilityResult": S.evaluate_eligibility({n: True for n in S.PRECONDITIONS})}
            evidence["ownerRegister"] = OF.OwnerRegisterResultV1(OF.REGISTER_NOT_VERIFIED, "OWNER_REGISTER_EMPTY")
            evidence["freshness"] = OF.FreshnessResultV1(OF.AUTHENTIC, OF.CURRENT)
            evidence["acceptance"] = OA.AcceptanceResultV1(OA.ACCEPTANCE_COMPLETE, evidenced_record_version=1)
            self.assertTrue(s.advance(step.action, evidence).advanced, step.action)
        held = {name: True for name in S.BY_ACTION["WRITE_HELD"].evidence}
        held["freshness"] = OF.FreshnessResultV1(OF.AUTHENTIC, OF.CURRENT)
        for state in (OA.ACCEPTANCE_PARTIAL, OA.ACCEPTANCE_NOT_PRESENT, OA.ACCEPTANCE_CONFLICTING,
                      OA.ACCEPTANCE_INVALID, OA.ACCEPTANCE_UNKNOWN):
            result = s.advance("WRITE_HELD", {**held, "acceptance": OA.AcceptanceResultV1(state)})
            self.assertEqual((result.reason, result.detail), ("OWNER_ACCEPTANCE_NOT_COMPLETE", state))
        self.assertTrue(s.advance("WRITE_HELD", {**held, "acceptance": OA.AcceptanceResultV1(
            OA.ACCEPTANCE_COMPLETE, evidenced_record_version=1)}).advanced)

    def test_design_record_exists(self):
        text = RECORD.read_text(encoding="utf-8")
        for line in ("OwnerFreshnessAcceptanceEnvelopeV1", "EXPLICIT_OWNER_DIGEST_CONFIRMATION",
                     "unsigned != unauthenticated storage", "signed != owner accepted", "ACCEPTANCE_PARTIAL",
                     "If an acceptance envelope exists, the owner must have accepted it", "P3_3_STORAGE_INCOMPLETE"):
            self.assertIn(line, text, line)


if __name__ == "__main__":
    unittest.main()
