"""15B2b-B1b-3e PR-3 P3-2: offline owner freshness workstation tooling (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-pr3-owner-offhost-foundation.md (§22–§24).

Replicas live in throwaway temporary directories. Witness chains are real
K-WIT-signed TEST chains. No real owner storage, key, network, DEV, or cloud
resource is touched.
"""

from __future__ import annotations

import ast
import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import synthetic_authority as SA  # noqa: F401  (sets sys.path)
import synthetic_b1b3e as F
from lilith_owner_memory import owner_freshness as OF
from lilith_owner_memory import owner_freshness_tool as T
from lilith_owner_memory import recovery_contracts as R

ROOT = SA.ROOT
MODULE = ROOT / "services/owner-memory-control/lilith_owner_memory/owner_freshness_tool.py"
ENV, PROFILE = F.ENV, "TEST_ONLY"


def ledger_step(s: F.Scenario, challenge_id: str) -> None:
    lep = R.ledger_epoch_id(F.E2, ENV)
    s.commit(lambda st: st.prepare(challenge_id, lep, ready=F.seeded_ready(st)))


class Workstation:
    """A temporary owner workstation: two replicas plus owner-held inputs."""

    def __init__(self, test: unittest.TestCase):
        self.dir = Path(tempfile.mkdtemp(prefix="p32-"))
        test.addCleanup(shutil.rmtree, self.dir, True)
        self.a, self.b = self.dir / "replica-a", self.dir / "replica-b"
        for path, replica_id in ((self.a, "vault-a"), (self.b, "offline-b")):
            code, out = self.cli("init-replica", "--replica", str(path), "--replica-id", replica_id,
                                 "--environment", ENV, "--profile", PROFILE)
            assert code == 0, out
        self.trust = self.write("trust.json", {
            "trustType": T.TRUST_TYPE, "schemaVersion": 1, "environment": ENV,
            "witnessAnchor": {"schemaVersion": 1, "witnessKeyId": F.WITNESS_KEY_ID, "environment": ENV,
                              "algorithm": "Ed25519", "publicKey": F.public_b64("witness")},
            "registryRoot": {"schemaVersion": 1, "rootKeyId": SA.ROOT_KEY_ID, "environment": ENV,
                             "algorithm": "Ed25519", "publicKey": SA.public_b64("root")},
            "registries": [F.v3(), F.v4(), F.v5()]})
        self.n = 0

    def write(self, name: str, value) -> Path:
        path = self.dir / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def cli(self, *argv: str):
        return T.run(list(argv))

    def chain(self, chain) -> Path:
        self.n += 1
        return self.write(f"chain-{self.n}.json", list(chain))

    def pin(self, genesis_digest: str, environment: str = ENV) -> Path:
        self.n += 1
        return self.write(f"pin-{self.n}.json", {"pinType": "LILITH_RECOVERY_WITNESS_V2_GENESIS_PIN",
                                                  "schemaVersion": 1, "environment": environment,
                                                  "genesisWitnessDigest": genesis_digest})

    def world(self, chain: Path) -> list[str]:
        return ["--trust", str(self.trust), "--chain", str(chain), "--environment", ENV, "--profile", PROFILE]

    def replicas(self) -> list[str]:
        return ["--replica", str(self.a), "--replica", str(self.b)]

    def propose(self, kind: str, chain: Path, pin: Path):
        self.n += 1
        out = self.dir / f"candidate-{self.n}.json"
        command = ["propose-genesis"] if kind == "genesis" else [f"propose-{kind}", *self.replicas()]
        code, result = self.cli(*command, *self.world(chain), "--pin", str(pin), "--out", str(out))
        return code, result, out

    def append(self, target: Path, peer: Path, candidate: Path, chain: Path, pin: Path, confirm: str):
        return self.cli("append", "--replica", str(target), "--peer", str(peer), "--candidate", str(candidate),
                        *self.world(chain), "--pin", str(pin), "--confirm-digest", confirm)

    def ceremony(self, kind: str, chain_docs, pin: Path) -> dict:
        """The whole owner ceremony: propose, review (confirm the digest), append A, then B."""
        chain = self.chain(chain_docs)
        code, proposed, candidate = self.propose(kind, chain, pin)
        assert code == 0, proposed
        digest = proposed["recordDigest"]
        first = self.append(self.a, self.b, candidate, chain, pin, digest)
        assert first[0] == 0 and first[1]["replication"] == "PEER_PENDING", first
        second = self.append(self.b, self.a, candidate, chain, pin, digest)
        assert second[0] == 0 and second[1]["replication"] == "REPLICAS_IDENTICAL", second
        return proposed

    def classify(self, chain_docs) -> dict:
        code, result = self.cli("classify", *self.replicas(), *self.world(self.chain(chain_docs)))
        assert code == 0, result
        return result

    def records(self, replica: Path) -> list[str]:
        return sorted(os.listdir(replica / T.RECORDS))


class GenesisAndCeremonyTests(unittest.TestCase):
    def setUp(self):
        self.w = Workstation(self)
        self.s = F.Scenario()
        self.genesis = self.s.writer.chain
        self.pin = self.w.pin(_genesis_digest(self.genesis))

    def test_full_genesis_ceremony_and_replica_layout(self):
        proposed = self.w.ceremony("genesis", self.genesis, self.pin)
        self.assertEqual((proposed["recordVersion"], proposed["accepted"]), (1, False))
        name = f"000001-{proposed['recordDigest']}.json"
        self.assertEqual(self.w.records(self.w.a), [name])
        self.assertEqual(self.w.records(self.w.b), [name])
        self.assertEqual((self.w.a / T.RECORDS / name).read_bytes(), (self.w.b / T.RECORDS / name).read_bytes())
        self.assertEqual(set(os.listdir(self.w.a)), {T.MANIFEST, T.RECORDS})
        result = self.w.classify(self.genesis)
        self.assertEqual((result["authenticity"], result["freshness"]), (OF.AUTHENTIC, OF.CURRENT))
        self.assertEqual(set(result["gates"].values()), {OF.FRESHNESS_PRECONDITION_MET})
        code, compared = self.w.cli("compare-replicas", *self.w.replicas())
        self.assertEqual((code, compared["status"]), (0, OF.REGISTER_VERIFIED))

    def test_explicit_owner_confirmation_required(self):
        chain = self.w.chain(self.genesis)
        _, proposed, candidate = self.w.propose("genesis", chain, self.pin)
        for confirm in ("", proposed["recordDigest"][:-1] + "0", F.digest("something else"),
                        proposed["recordDigest"].upper()):
            code, result = self.w.append(self.w.a, self.w.b, candidate, chain, self.pin, confirm)
            self.assertEqual(code, T.EXIT_REFUSED, confirm)
            self.assertIn(result["reason"], {"OWNER_CONFIRMATION_REQUIRED", "OWNER_CONFIRMATION_MISMATCH"})
        code, result = self.w.cli("append", "--replica", str(self.w.a), "--peer", str(self.w.b), "--candidate",
                                  str(candidate), *self.w.world(chain), "--pin", str(self.pin))
        self.assertEqual((code, result["status"]), (T.EXIT_USAGE, "USAGE"))      # --confirm-digest is required
        self.assertEqual(self.w.records(self.w.a), [])

    def test_candidate_is_not_acceptance(self):
        chain = self.w.chain(self.genesis)
        code, proposed, candidate = self.w.propose("genesis", chain, self.pin)
        self.assertEqual((code, proposed["status"], proposed["accepted"]), (0, "CANDIDATE_WRITTEN", False))
        self.assertEqual(self.w.records(self.w.a), [])                            # nothing appended
        self.assertEqual(self.w.classify(self.genesis)["reason"], "OWNER_REGISTER_NOT_VERIFIED")
        document = json.loads(candidate.read_text(encoding="utf-8"))
        self.assertIs(document["accepted"], False)
        # a candidate file dropped into a replica is not a record
        shutil.copy(candidate, self.w.a / T.RECORDS / candidate.name)
        with self.assertRaises(T.ToolRefusal) as caught:
            T.load_replica(self.w.a)
        self.assertEqual(caught.exception.reason, "REPLICA_UNEXPECTED_ENTRY")
        os.unlink(self.w.a / T.RECORDS / candidate.name)
        # a candidate claiming to be accepted is malformed
        forged = self.w.write("forged.json", {**document, "accepted": True})
        code, result = self.w.append(self.w.a, self.w.b, forged, chain, self.pin, proposed["recordDigest"])
        self.assertEqual((code, result["reason"]), (T.EXIT_REFUSED, "CANDIDATE_MALFORMED"))
        # proposing again never overwrites an existing candidate file
        before = candidate.read_bytes()
        code, result = self.w.cli("propose-genesis", *self.w.world(chain), "--pin", str(self.pin),
                                  "--out", str(candidate))
        self.assertEqual((code, result["reason"]), (T.EXIT_REFUSED, "CANDIDATE_FILE_EXISTS"))
        self.assertEqual(candidate.read_bytes(), before)

    def test_record_1_must_bind_the_genesis_pin(self):
        chain = self.w.chain(self.genesis)
        wrong = self.w.pin(F.digest("another genesis"))
        code, result, _ = self.w.propose("genesis", chain, wrong)
        self.assertEqual((code, result["reason"]), (T.EXIT_REFUSED, "GENESIS_PIN_MISMATCH"))
        code, result, _ = self.w.propose("genesis", chain, self.w.pin(_genesis_digest(self.genesis), "dev"))
        self.assertEqual((code, result["reason"]), (T.EXIT_REFUSED, "GENESIS_PIN_ENVIRONMENT_MISMATCH"))
        _, proposed, candidate = self.w.propose("genesis", chain, self.pin)
        code, result = self.w.append(self.w.a, self.w.b, candidate, chain, wrong, proposed["recordDigest"])
        self.assertEqual((code, result["reason"]), (T.EXIT_REFUSED, "GENESIS_PIN_MISMATCH"))
        self.w.ceremony("genesis", self.genesis, self.pin)
        self.s.to_current()
        code, result, _ = self.w.propose("accept", self.w.chain(self.s.writer.chain), wrong)
        self.assertEqual((code, result["reason"]), (T.EXIT_REFUSED, "GENESIS_PIN_MISMATCH"))


def _genesis_digest(chain) -> str:
    from lilith_owner_memory import rotation_contracts as RC
    return RC.RecoveryWitnessV2.from_verified_dict(chain[0]).digest


class AcceptedWorldTests(unittest.TestCase):
    def setUp(self):
        self.w = Workstation(self)
        self.s = F.Scenario()
        self.snapshot = self.s.writer.chain
        self.pin = self.w.pin(_genesis_digest(self.snapshot))
        self.w.ceremony("genesis", self.snapshot, self.pin)
        self.s.to_current()                               # W2 head advance, W3 ledger
        self.w.ceremony("accept", self.s.writer.chain, self.pin)

    def test_accepted_record_cannot_be_overwritten(self):
        before = {n: (self.w.a / T.RECORDS / n).read_bytes() for n in self.w.records(self.w.a)}
        chain = self.w.chain(self.s.writer.chain)
        # replaying the already-appended candidate is refused (it is no longer a successor)
        candidate = sorted(self.w.dir.glob("candidate-*.json"))[-1]
        digest = json.loads(candidate.read_text(encoding="utf-8"))["recordDigest"]
        code, result = self.w.append(self.w.a, self.w.b, candidate, chain, self.pin, digest)
        self.assertEqual((code, result["reason"]), (T.EXIT_REFUSED, "CANDIDATE_NOT_ACCEPTABLE"))
        # the low-level writer never replaces a version that exists, whatever its content
        replica = T.load_replica(self.w.a)
        record = copy.deepcopy(replica.records[1])
        record["registryDigest"] = F.digest("other")
        with self.assertRaises(T.ToolRefusal) as caught:
            T._write_record(replica, record, OF.record_digest(record))
        self.assertEqual(caught.exception.reason, "RECORD_EXISTS")
        with self.assertRaises(T.ToolRefusal):
            T._write_record(replica, replica.records[1], replica.digests[1])
        after = {n: (self.w.a / T.RECORDS / n).read_bytes() for n in self.w.records(self.w.a)}
        self.assertEqual(before, after)
        self.assertEqual([n for n in os.listdir(self.w.a / T.RECORDS) if n.startswith(T.PENDING_PREFIX)], [])

    def test_skipped_record_version_rejected(self):
        replica = T.load_replica(self.w.a)
        record = {**copy.deepcopy(replica.records[1]), "recordVersion": 4}
        (self.w.a / T.RECORDS / f"000004-{OF.record_digest(record)}.json").write_bytes(OF.record_bytes(record))
        with self.assertRaises(T.ToolRefusal) as caught:
            T.load_replica(self.w.a)
        self.assertEqual(caught.exception.reason, "RECORD_VERSION_GAP")
        self.assertEqual(self.w.classify(self.s.writer.chain)["freshness"], OF.FRESHNESS_UNKNOWN)
        # a hand-built candidate that skips a version is not the derived successor
        ledger_step(self.s, "c9")
        chain = self.w.chain(self.s.writer.chain)
        os.unlink(self.w.a / T.RECORDS / f"000004-{OF.record_digest(record)}.json")
        _, proposed, candidate = self.w.propose("accept", chain, self.pin)
        document = json.loads(candidate.read_text(encoding="utf-8"))
        document["record"]["recordVersion"] = 4
        document["recordDigest"] = OF.record_digest(document["record"])
        skipped = self.w.write("skipped.json", document)
        code, result = self.w.append(self.w.a, self.w.b, skipped, chain, self.pin, document["recordDigest"])
        self.assertEqual((code, result["reason"]), (T.EXIT_REFUSED, "CANDIDATE_NOT_ACCEPTABLE"))

    def test_duplicate_version_different_digest_conflicts(self):
        replica = T.load_replica(self.w.a)
        twin = {**copy.deepcopy(replica.records[1]), "registryDigest": F.digest("twin")}
        (self.w.a / T.RECORDS / f"000002-{OF.record_digest(twin)}.json").write_bytes(OF.record_bytes(twin))
        with self.assertRaises(T.ToolRefusal) as caught:
            T.load_replica(self.w.a)
        self.assertEqual(caught.exception.reason, "RECORD_VERSION_DUPLICATED")

    def test_divergent_replicas_fail(self):
        # replica B gets a different record 3 (a ledger-only acceptance A never saw)
        other = F.Scenario().to_current()
        ledger_step(other, "c7")
        ledger_step(self.s, "c8")
        chain_a, chain_b = self.w.chain(self.s.writer.chain), self.w.chain(other.writer.chain)
        _, pa, ca = self.w.propose("accept", chain_a, self.pin)
        self.assertEqual(self.w.append(self.w.a, self.w.b, ca, chain_a, self.pin, pa["recordDigest"])[0], 0)
        # B cannot take a different record 3 while A holds one: not appendable
        _, pb, cb = self.w.propose("accept", chain_b, self.pin)
        self.assertEqual(pb["reason"], "OWNER_REGISTER_NOT_VERIFIED")             # the register is divergent now
        code, compared = self.w.cli("compare-replicas", *self.w.replicas())
        self.assertEqual((code, compared["reason"], compared["detail"]),
                         (T.EXIT_REFUSED, "REPLICAS_DIVERGENT", "replica1:PREFIX"))
        result = self.w.classify(self.s.writer.chain)
        self.assertEqual(result["freshness"], OF.FRESHNESS_UNKNOWN)
        self.assertEqual(set(result["gates"].values()), {OF.FRESHNESS_BLOCKED})
        # forcing a fork by hand is still detected, never resolved
        forked = {**T.load_replica(self.w.a).records[2], "witnessDigest": F.digest("fork")}
        fork_record = dict(forked)
        (self.w.b / T.RECORDS / f"000003-{OF.record_digest(fork_record)}.json").write_bytes(OF.record_bytes(fork_record))
        code, compared = self.w.cli("compare-replicas", *self.w.replicas())
        self.assertEqual((compared["reason"], compared["detail"]), ("REPLICAS_DIVERGENT", "replica1:FORK"))

    def test_missing_replica_is_freshness_unknown(self):
        chain = self.w.chain(self.s.writer.chain)
        code, one = self.w.cli("classify", "--replica", str(self.w.a), *self.w.world(chain))
        self.assertEqual((one["freshness"], one["detail"]), (OF.FRESHNESS_UNKNOWN, "REPLICA_QUORUM_UNMET:1"))
        shutil.rmtree(self.w.b)
        code, gone = self.w.cli("classify", *self.w.replicas(), *self.w.world(chain))
        self.assertEqual((gone["freshness"], gone["reason"]), (OF.FRESHNESS_UNKNOWN, "OWNER_REGISTER_NOT_VERIFIED"))
        self.assertTrue(gone["detail"].startswith("REPLICA_MISSING"))
        self.assertEqual(set(gone["gates"].values()), {OF.FRESHNESS_BLOCKED})

    def test_stale_dev_cannot_be_accepted_current(self):
        restored = self.w.classify(self.snapshot)          # DEV restored from the genesis-time snapshot
        self.assertEqual((restored["authenticity"], restored["freshness"], restored["reason"]),
                         (OF.AUTHENTIC, OF.STALE, "EARLIER_ACCEPTED_STATE"))
        chain = self.w.chain(self.snapshot)
        code, result, _ = self.w.propose("accept", chain, self.pin)
        self.assertEqual((code, result["reason"], result["detail"]),
                         (T.EXIT_REFUSED, "CANDIDATE_NOT_PROPOSED", "STALE:EARLIER_ACCEPTED_STATE"))
        # a hand-made "accept the snapshot" candidate is refused at append time
        replica = T.load_replica(self.w.a)
        record = {**copy.deepcopy(replica.records[0]), "recordVersion": 3, "previousRecordDigest": replica.digests[-1]}
        forged = self.w.write("stale.json", {"candidateType": T.CANDIDATE_TYPE, "schemaVersion": 1, "accepted": False,
                                             "decision": OF.ACCEPT_CURRENT, "recordDigest": None, "record": record})
        code, result = self.w.append(self.w.a, self.w.b, forged, chain, self.pin, "x")
        self.assertEqual(code, T.EXIT_REFUSED)
        self.assertEqual(len(self.w.records(self.w.a)), 2)

    def test_ahead_dev_is_never_accepted_automatically(self):
        ledger_step(self.s, "c9")
        result = self.w.classify(self.s.writer.chain)
        self.assertEqual((result["freshness"], result["reason"]), (OF.AHEAD_UNACCEPTED, "AHEAD_LEDGER_ONLY"))
        self.assertEqual(set(result["gates"].values()), {OF.FRESHNESS_BLOCKED})          # D11
        self.assertEqual(len(self.w.records(self.w.a)), 2)                               # classify wrote nothing
        chain = self.w.chain(self.s.writer.chain)
        _, proposed, candidate = self.w.propose("accept", chain, self.pin)
        self.assertEqual(len(self.w.records(self.w.a)), 2)                               # propose wrote nothing
        code, refused = self.w.append(self.w.a, self.w.b, candidate, chain, self.pin, "")
        self.assertEqual(refused["reason"], "OWNER_CONFIRMATION_REQUIRED")
        self.w.ceremony("accept", self.s.writer.chain, self.pin)                         # only the owner step
        self.assertEqual(self.w.classify(self.s.writer.chain)["freshness"], OF.CURRENT)

    def test_rejected_lineage_remains_rejected(self):
        self.s.epoch_advance()                            # an authority-changing descendant
        rejected_chain = self.s.writer.chain
        self.assertEqual(self.w.classify(rejected_chain)["reason"], "AHEAD_AUTHORITY_CHANGING")
        proposed = self.w.ceremony("reject", rejected_chain, self.pin)
        self.assertEqual(proposed["decision"], OF.REJECT_CANDIDATE)
        result = self.w.classify(rejected_chain)
        self.assertEqual((result["freshness"], result["reason"]), (OF.CONFLICTING, "OWNER_REJECTED_LINEAGE"))
        code, again, _ = self.w.propose("accept", self.w.chain(rejected_chain), self.pin)
        self.assertEqual(code, T.EXIT_REFUSED)
        lep = R.ledger_epoch_id(F.E3, ENV)                # a further witness on top of the rejected head
        self.s.commit(lambda st: st.prepare("c10", lep, ready=F.seeded_ready(st)))
        self.assertGreater(len(self.s.writer.chain), len(rejected_chain))
        self.assertEqual(self.w.classify(self.s.writer.chain)["reason"], "OWNER_REJECTED_LINEAGE")
        # the accepted world is untouched
        self.assertEqual(self.w.classify(self.s.writer.chain[:3])["freshness"], OF.CURRENT)

    def test_git_metadata_and_timestamps_have_zero_freshness_authority(self):
        chain = self.s.writer.chain
        baseline = self.w.classify(chain)
        for replica in (self.w.a, self.w.b):
            for name in self.w.records(replica):
                os.utime(replica / T.RECORDS / name, (0, 0))
        os.utime(self.w.a / T.RECORDS / self.w.records(self.w.a)[0], (4_000_000_000, 4_000_000_000))
        self.assertEqual(self.w.classify(chain), baseline)
        # a replica with fresher mtimes but fewer records is not "newer": it diverges
        behind = self.w.dir / "replica-c"
        self.w.cli("init-replica", "--replica", str(behind), "--replica-id", "usb-c", "--environment", ENV,
                   "--profile", PROFILE)
        first = self.w.records(self.w.a)[0]
        shutil.copy(self.w.a / T.RECORDS / first, behind / T.RECORDS / first)
        os.utime(behind / T.RECORDS / first, (4_100_000_000, 4_100_000_000))
        code, compared = self.w.cli("compare-replicas", "--replica", str(self.w.a), "--replica", str(behind))
        self.assertEqual(compared["reason"], "REPLICAS_DIVERGENT")
        # Git metadata inside a replica is an unexpected entry, never an input
        (self.w.a / ".git").mkdir()
        (self.w.a / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        with self.assertRaises(T.ToolRefusal) as caught:
            T.load_replica(self.w.a)
        self.assertEqual((caught.exception.reason, caught.exception.detail), ("REPLICA_UNEXPECTED_ENTRY", ".git"))
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        self.assertFalse(attributes & {"st_mtime", "st_mtime_ns", "st_ctime", "getmtime", "getctime"})

    def test_hand_edited_candidate_is_refused(self):
        ledger_step(self.s, "c9")
        chain = self.w.chain(self.s.writer.chain)
        _, proposed, candidate = self.w.propose("accept", chain, self.pin)
        document = json.loads(candidate.read_text(encoding="utf-8"))
        document["record"]["registryVersion"] = 5
        document["recordDigest"] = OF.record_digest(document["record"])
        edited = self.w.write("edited.json", document)
        code, result = self.w.append(self.w.a, self.w.b, edited, chain, self.pin, document["recordDigest"])
        self.assertEqual((code, result["reason"], result["detail"]),
                         (T.EXIT_REFUSED, "CANDIDATE_NOT_ACCEPTABLE", "CANDIDATE_DIFFERS_FROM_DERIVED_RECORD"))


class RegisterBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.w = Workstation(self)
        self.s = F.Scenario()
        self.pin = self.w.pin(_genesis_digest(self.s.writer.chain))

    def test_authorization_register_does_not_substitute_for_freshness_register(self):
        authorization_register = {"registerType": "LILITH_OWNER_AUTHORIZATION_REGISTER", "schemaVersion": 1,
                                  "environment": ENV, "authorizations": [], "headRegistries": []}
        raw = OF.record_bytes(authorization_register)
        (self.w.a / T.RECORDS / f"000001-{F.digest('authorization register')}.json").write_bytes(raw)
        with self.assertRaises(T.ToolRefusal) as caught:
            T.load_replica(self.w.a)
        self.assertEqual(caught.exception.reason, "RECORD_MALFORMED")
        self.assertEqual(OF.verify_owner_register([authorization_register]).reason, "RECORD_MALFORMED")
        as_candidate = self.w.write("authreg-candidate.json", authorization_register)
        chain = self.w.chain(self.s.writer.chain)
        code, result = self.w.append(self.w.b, self.w.a, as_candidate, chain, self.pin, "x")
        self.assertEqual((code, result["reason"]), (T.EXIT_REFUSED, "CANDIDATE_MALFORMED"))
        # the genesis pin is not a register either
        pin_as_replica_record = json.loads(self.pin.read_text(encoding="utf-8"))
        self.assertEqual(OF.verify_owner_register([pin_as_replica_record]).reason, "RECORD_MALFORMED")

    def test_replica_identity_and_layout_rules(self):
        code, result = self.w.cli("compare-replicas", "--replica", str(self.w.a), "--replica", str(self.w.a))
        self.assertIn(result["reason"], {"REPLICA_ID_DUPLICATED", "REPLICA_SAME_LOCATION"})
        clone = self.w.dir / "clone"
        shutil.copytree(self.w.a, clone)
        code, result = self.w.cli("compare-replicas", "--replica", str(self.w.a), "--replica", str(clone))
        self.assertEqual(result["reason"], "REPLICA_ID_DUPLICATED")                 # explicit identity
        code, result = self.w.cli("init-replica", "--replica", str(self.w.a), "--replica-id", "again",
                                  "--environment", ENV, "--profile", PROFILE)
        self.assertEqual((code, result["reason"]), (T.EXIT_REFUSED, "REPLICA_PATH_EXISTS"))
        code, result = self.w.cli("init-replica", "--replica", str(self.w.dir / "x"), "--replica-id", "Bad ID",
                                  "--environment", ENV, "--profile", PROFILE)
        self.assertEqual(result["reason"], "REPLICA_ID_INVALID")
        code, result = self.w.cli("init-replica", "--replica", str(self.w.dir / "y"), "--replica-id", "y",
                                  "--environment", "dev", "--profile", PROFILE)
        self.assertEqual(result["reason"], "PROFILE_MISMATCH")
        (self.w.a / "notes.txt").write_text("hello", encoding="utf-8")
        code, result = self.w.cli("verify-replica", "--replica", str(self.w.a))
        self.assertEqual((code, result["reason"]), (T.EXIT_REFUSED, "REPLICA_UNEXPECTED_ENTRY"))

    def test_pending_write_refuses_and_is_not_repaired(self):
        pending = self.w.a / T.RECORDS / f"{T.PENDING_PREFIX}000001-{F.digest('p')}.tmp"
        pending.write_bytes(b"{}")
        code, result = self.w.cli("verify-replica", "--replica", str(self.w.a))
        self.assertEqual((code, result["reason"]), (T.EXIT_REFUSED, "REPLICA_PENDING_WRITE"))
        self.assertTrue(pending.exists())                                              # no silent repair
        record_name = f"000001-{F.digest('n')}.json"
        (self.w.b / T.RECORDS / record_name).write_bytes(b'{"a":1}')
        code, result = self.w.cli("verify-replica", "--replica", str(self.w.b))
        self.assertEqual(result["reason"], "RECORD_MALFORMED")

    def test_inspect_chain_reports_authenticity_only(self):
        chain = self.w.chain(self.s.writer.chain)
        code, result = self.w.cli("inspect-chain", *self.w.world(chain))
        self.assertEqual((code, result["authenticity"], result["headWitnessVersion"]), (0, OF.AUTHENTIC, 1))
        self.assertNotIn("freshness", result)
        tampered = [dict(w) for w in self.s.writer.chain]
        tampered[0]["ledgerSequence"] += 1
        code, result = self.w.cli("inspect-chain", *self.w.world(self.w.chain(tampered)))
        self.assertEqual((code, result["authenticity"]), (T.EXIT_REFUSED, OF.NOT_AUTHENTIC))

    def test_tool_has_no_network_process_or_key_dependency(self):
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
                    for alias in node.names}
        imported |= {node.module.split(".")[0] for node in ast.walk(tree)
                     if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module}
        self.assertTrue(imported <= {"__future__", "argparse", "json", "os", "re", "stat", "sys", "dataclasses",
                                     "pathlib", "typing", "lilith_memory"}, imported)
        source = MODULE.read_text(encoding="utf-8")
        for forbidden in ("socket", "urllib", "http", "subprocess", "cryptography", "gcloud", "git ", "sign("):
            self.assertNotIn(forbidden, source, forbidden)


if __name__ == "__main__":
    unittest.main()
