"""15B2b-B1b-3e PR-3 P3-4: synthetic owner freshness ceremony rehearsal (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-pr3-owner-offhost-foundation.md (§26).
Runbook: docs/architecture/slice-15b2b-b1b3e-pr3-owner-ceremony-runbook.md.

Every replica is a temporary directory created by the test. The witness
chains are real K-WIT-signed TEST chains from the B1b-3e synthetic scenario
(TEST_ONLY profile; the synthetic witness writer admits only `test`). The
real owner Replica A is never read or written.

    synthetic ceremony success != real owner freshness established
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import unittest
from pathlib import Path

import synthetic_authority as SA  # noqa: F401  (sets sys.path)
import synthetic_b1b3e as F
import test_b1b3e_pr3_p32_owner_freshness_tool as P32
from lilith_owner_memory import owner_freshness as OF
from lilith_owner_memory import owner_freshness_tool as T
from lilith_owner_memory import recovery_contracts as R

ROOT = SA.ROOT
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-pr3-owner-offhost-foundation.md"
RUNBOOK = ROOT / "docs/architecture/slice-15b2b-b1b3e-pr3-owner-ceremony-runbook.md"
ENV, PROFILE = F.ENV, "TEST_ONLY"
MATRIX_OPERATIONS = ("REGISTRY_HEAD_ADVANCE", "RECOVERY_EPOCH_ADVANCE", "SUCCESSOR_READINESS",
                     "INITIAL_CUSTODY_RELEASE", "AUTHORITY_CHANGING_ISSUANCE", "FIRST_MEMORY")


class Rehearsal(P32.Workstation):
    """The runbook's ten steps, one method each, over temporary replicas."""

    def step1_inspect(self, chain_docs) -> tuple[Path, dict]:
        chain = self.chain(chain_docs)
        code, result = self.cli("inspect-chain", *self.world(chain))
        assert code == 0 and result["authenticity"] == OF.AUTHENTIC, result
        return chain, result

    def step2_classify(self, chain: Path) -> dict:
        code, result = self.cli("classify", *self.replicas(), *self.world(chain))
        assert code == 0, result
        return result

    def step3_candidate(self, kind: str, chain: Path, pin: Path) -> tuple[int, dict, Path]:
        return self.propose(kind, chain, pin)

    @staticmethod
    def step4_review(candidate: Path) -> dict:
        document = json.loads(candidate.read_text(encoding="utf-8"))
        assert document["accepted"] is False
        assert OF.record_digest(document["record"]) == document["recordDigest"]
        return document

    def step5_to_8_append(self, candidate: Path, chain: Path, pin: Path, digest: str,
                          observe_intermediate=None) -> tuple[dict, dict]:
        first = self.append(self.a, self.b, candidate, chain, pin, digest)             # step 6
        assert first[0] == 0 and first[1]["replication"] == "PEER_PENDING", first
        if observe_intermediate is not None:
            observe_intermediate(self.step2_classify(chain))                          # step 7
        second = self.append(self.b, self.a, candidate, chain, pin, digest)            # step 8
        assert second[0] == 0 and second[1]["replication"] == "REPLICAS_IDENTICAL", second
        return first[1], second[1]

    def step9_compare(self) -> dict:
        return self.cli("compare-replicas", *self.replicas())[1]

    def full(self, kind: str, chain_docs, pin: Path) -> dict:
        chain, _ = self.step1_inspect(chain_docs)
        _, proposed, candidate = self.step3_candidate(kind, chain, pin)
        document = self.step4_review(candidate)
        self.step5_to_8_append(candidate, chain, pin, document["recordDigest"])
        return document

    def snapshot(self) -> tuple[Path, Path]:
        self.n += 1
        a, b = self.dir / f"snap-{self.n}-a", self.dir / f"snap-{self.n}-b"
        shutil.copytree(self.a, a)
        shutil.copytree(self.b, b)
        return a, b

    def restore(self, snapshot: tuple[Path, Path]) -> None:
        for live, saved in ((self.a, snapshot[0]), (self.b, snapshot[1])):
            shutil.rmtree(live, ignore_errors=True)
            shutil.copytree(saved, live)


def gates(result: dict) -> set[str]:
    return set(result["gates"].values())


def ledger_step(s: F.Scenario, challenge_id: str, epoch=F.E2) -> None:
    lep = R.ledger_epoch_id(epoch, ENV)
    s.commit(lambda st: st.prepare(challenge_id, lep, ready=F.seeded_ready(st)))


class GenesisRehearsal(unittest.TestCase):
    def test_genesis_ceremony_end_to_end(self):
        w, s = Rehearsal(self), F.Scenario()
        pin = w.pin(P32._genesis_digest(s.writer.chain))
        chain, inspected = w.step1_inspect(s.writer.chain)
        self.assertEqual(inspected["genesisWitnessDigest"], json.loads(pin.read_text())["genesisWitnessDigest"])
        before = w.step2_classify(chain)
        self.assertEqual((before["freshness"], before["reason"]), (OF.FRESHNESS_UNKNOWN, "OWNER_REGISTER_NOT_VERIFIED"))
        code, proposed, candidate = w.step3_candidate("genesis", chain, pin)
        self.assertEqual(code, 0)
        document = w.step4_review(candidate)
        # proposal != acceptance: nothing appended, still unknown
        self.assertEqual((w.records(w.a), w.records(w.b)), ([], []))
        self.assertEqual(w.step2_classify(chain)["freshness"], OF.FRESHNESS_UNKNOWN)
        # record 1 binds the synthetic pin exactly
        self.assertEqual(document["record"]["genesisWitnessDigest"], json.loads(pin.read_text())["genesisWitnessDigest"])
        self.assertEqual(document["record"]["witnessDigest"], document["record"]["genesisWitnessDigest"])
        seen = []
        w.step5_to_8_append(candidate, chain, pin, document["recordDigest"], seen.append)
        self.assertEqual((seen[0]["freshness"], seen[0]["reason"]), (OF.FRESHNESS_UNKNOWN, "OWNER_REGISTER_NOT_VERIFIED"))
        self.assertEqual(gates(seen[0]), {OF.FRESHNESS_BLOCKED})
        self.assertEqual(w.step9_compare()["status"], OF.REGISTER_VERIFIED)
        self.assertEqual((w.a / T.RECORDS / w.records(w.a)[0]).read_bytes(),
                         (w.b / T.RECORDS / w.records(w.b)[0]).read_bytes())
        current = w.step2_classify(chain)                                          # step 10
        self.assertEqual((current["authenticity"], current["freshness"]), (OF.AUTHENTIC, OF.CURRENT))
        self.assertEqual(gates(current), {OF.FRESHNESS_PRECONDITION_MET})


class WorldRehearsal(unittest.TestCase):
    """Owner accepted genesis W1; DEV then advances."""

    def setUp(self):
        self.w, self.s = Rehearsal(self), F.Scenario()
        self.old_world = self.s.writer.chain
        self.pin = self.w.pin(P32._genesis_digest(self.old_world))
        self.w.full("genesis", self.old_world, self.pin)

    def test_successor_acceptance(self):
        self.s.to_current()                               # W2 head advance (authority-changing), W3 ledger
        chain, _ = self.w.step1_inspect(self.s.writer.chain)
        ahead = self.w.step2_classify(chain)
        self.assertEqual((ahead["freshness"], ahead["reason"]), (OF.AHEAD_UNACCEPTED, "AHEAD_AUTHORITY_CHANGING"))
        self.assertEqual(gates(ahead), {OF.FRESHNESS_BLOCKED})
        _, _, candidate = self.w.step3_candidate("accept", chain, self.pin)
        document = self.w.step4_review(candidate)
        seen = []
        self.w.step5_to_8_append(candidate, chain, self.pin, document["recordDigest"], seen.append)
        self.assertEqual(seen[0]["freshness"], OF.FRESHNESS_UNKNOWN)                 # first replica only
        self.assertEqual(self.w.step2_classify(chain)["freshness"], OF.CURRENT)      # both replicas
        records = T.load_replica(self.w.a).records
        self.assertEqual([r["recordVersion"] for r in records], [1, 2])
        self.assertEqual(records[1]["previousRecordDigest"], OF.record_digest(records[0]))
        self.assertEqual(records[0]["previousRecordDigest"], None)

    def test_stale_dev_world(self):
        self.s.to_current()
        self.w.full("accept", self.s.writer.chain, self.pin)
        before = sorted(os.listdir(self.w.a / T.RECORDS))
        stale = self.w.step2_classify(self.w.chain(self.old_world))
        self.assertEqual((stale["authenticity"], stale["freshness"], stale["reason"]),
                         (OF.AUTHENTIC, OF.STALE, "EARLIER_ACCEPTED_STATE"))
        self.assertEqual(OF.DEV_STATE_STALE, "DEV_STATE_STALE")
        self.assertEqual(gates(stale), {OF.FRESHNESS_BLOCKED})
        self.assertEqual(sorted(os.listdir(self.w.a / T.RECORDS)), before)          # no repair, no write
        self.assertNotIn("repair", json.dumps(stale).lower())

    def test_conflict_has_no_tiebreaker(self):
        a_world = self.s
        b_world = F.Scenario()
        a_world.to_current()                              # A: head advance, W2..W3
        for index in range(4):                            # B: longer, later-stamped, ledger-only
            ledger_step(b_world, f"b{index}")
        b_world.ticks += 1000
        ledger_step(b_world, "b-late")
        self.assertGreater(len(b_world.writer.chain), len(a_world.writer.chain))
        chain_a, chain_b = self.w.chain(a_world.writer.chain), self.w.chain(b_world.writer.chain)
        both_ahead = [self.w.step2_classify(c)["freshness"] for c in (chain_a, chain_b)]
        self.assertEqual(both_ahead, [OF.AHEAD_UNACCEPTED, OF.AHEAD_UNACCEPTED])     # no automatic witness preference
        self.w.full("accept", a_world.writer.chain, self.pin)                         # the owner chooses A
        longer = self.w.step2_classify(chain_b)
        self.assertEqual((longer["freshness"], longer["reason"]), (OF.CONFLICTING, "FORKED_FROM_ACCEPTED_HISTORY"))
        self.assertEqual(gates(longer), {OF.FRESHNESS_BLOCKED})                       # no longest-chain rule
        # the tool refuses to write a second successor into one replica (no last-write-wins)
        _, refused, _ = self.w.step3_candidate("accept", chain_b, self.pin)
        self.assertEqual(refused["status"], "REFUSED")
        # out-of-band divergence (owner error / tampering) is detected, never resolved
        forked = {**T.load_replica(self.w.b).records[1], "witnessDigest": F.digest("other successor")}
        victim = T.load_replica(self.w.b)
        shutil.rmtree(self.w.b / T.RECORDS)
        os.mkdir(self.w.b / T.RECORDS)
        for record in (victim.records[0], forked):
            name = f"{record['recordVersion']:06d}-{OF.record_digest(record)}.json"
            (self.w.b / T.RECORDS / name).write_bytes(OF.record_bytes(record))
        for replica in (self.w.a, self.w.b):             # newest mtime would favour B: ignored
            for name in os.listdir(replica / T.RECORDS):
                os.utime(replica / T.RECORDS / name, (4_200_000_000 if replica == self.w.b else 0,) * 2)
        compared = self.w.step9_compare()
        self.assertEqual((compared["reason"], compared["detail"]), ("REPLICAS_DIVERGENT", "replica1:FORK"))
        for chain in (chain_a, chain_b):
            result = self.w.step2_classify(chain)
            self.assertEqual(result["freshness"], OF.FRESHNESS_UNKNOWN)
            self.assertTrue(result["detail"].startswith("REPLICAS_DIVERGENT"))
            self.assertEqual(gates(result), {OF.FRESHNESS_BLOCKED})
        (self.w.a / ".git").mkdir()                       # no Git rule: Git metadata is refused, not consulted
        self.assertTrue(self.w.step2_classify(chain_a)["detail"].startswith("REPLICA_UNEXPECTED_ENTRY"))

    def test_rejection_is_terminal(self):
        self.s.to_current()
        rejected_docs = self.s.writer.chain
        chain_before = json.dumps(rejected_docs, sort_keys=True)
        document = self.w.full("reject", rejected_docs, self.pin)
        self.assertEqual(document["decision"], OF.REJECT_CANDIDATE)
        records = T.load_replica(self.w.a).records
        self.assertEqual([(r["recordVersion"], r["decision"]) for r in records],
                         [(1, OF.ACCEPT_CURRENT), (2, OF.REJECT_CANDIDATE)])
        self.assertEqual(records[1]["previousRecordDigest"], OF.record_digest(records[0]))   # chained decision
        self.assertEqual(json.dumps(self.s.writer.chain, sort_keys=True), chain_before)   # DEV not mutated
        result = self.w.step2_classify(self.w.chain(rejected_docs))
        self.assertEqual((result["freshness"], result["reason"]), (OF.CONFLICTING, "OWNER_REJECTED_LINEAGE"))
        ledger_step(self.s, "after-reject")               # a descendant of the rejected head
        descendant = self.w.chain(self.s.writer.chain)
        self.assertEqual(self.w.step2_classify(descendant)["reason"], "OWNER_REJECTED_LINEAGE")
        code, refused, _ = self.w.step3_candidate("accept", descendant, self.pin)
        self.assertEqual((code, refused["reason"]), (T.EXIT_REFUSED, "CANDIDATE_NOT_PROPOSED"))
        # rejection is not a recovery authorization: every gate stays blocked, and the
        # accepted world is unchanged
        self.assertEqual(gates(result), {OF.FRESHNESS_BLOCKED})
        self.assertEqual(self.w.step2_classify(self.w.chain(self.old_world))["freshness"], OF.CURRENT)
        with self.assertRaises(Exception):
            from lilith_owner_memory import witness_readiness as WR
            WR.parse_owner_register(records[1])

    def test_register_loss(self):
        self.s.to_current()
        snapshot = self.w.snapshot()                      # both copies at record 1 (world W1)
        self.w.full("accept", self.s.writer.chain, self.pin)
        chain = self.w.chain(self.s.writer.chain)
        self.assertEqual(self.w.step2_classify(chain)["freshness"], OF.CURRENT)
        full = self.w.snapshot()
        for missing in (self.w.a, self.w.b):
            shutil.rmtree(missing)
            result = self.w.step2_classify(chain)
            self.assertEqual(result["freshness"], OF.FRESHNESS_UNKNOWN)
            self.assertTrue(result["detail"].startswith("REPLICA_MISSING"), result["detail"])
            self.assertEqual(gates(result), {OF.FRESHNESS_BLOCKED})
            self.w.restore(full)
        shutil.rmtree(self.w.b)                           # one copy behind
        shutil.copytree(snapshot[1], self.w.b)
        behind = self.w.step2_classify(chain)
        self.assertEqual((behind["freshness"], behind["detail"]), (OF.FRESHNESS_UNKNOWN, "REPLICAS_DIVERGENT:replica1:PREFIX"))
        shutil.rmtree(self.w.a)
        shutil.rmtree(self.w.b)                           # both unavailable
        self.assertEqual(self.w.step2_classify(chain)["freshness"], OF.FRESHNESS_UNKNOWN)
        # LIMITATION: both copies jointly rolled back to the same old history
        self.w.restore(snapshot)
        self.assertEqual(self.w.step9_compare()["status"], OF.REGISTER_VERIFIED)
        false_current = self.w.step2_classify(self.w.chain(self.old_world))
        self.assertEqual(false_current["freshness"], OF.CURRENT)                     # falsely CURRENT
        newer = self.w.step2_classify(chain)
        self.assertEqual(newer["freshness"], OF.AHEAD_UNACCEPTED)                   # the true latest now looks unaccepted

    def test_recovery_detection_only(self):
        self.s.to_current()
        n_minus_1 = self.s.writer.chain
        self.w.full("accept", n_minus_1, self.pin)        # world N-1 accepted
        ledger_step(self.s, "n")
        self.w.full("accept", self.s.writer.chain, self.pin)   # world N accepted
        restored = self.w.step2_classify(self.w.chain(n_minus_1))
        self.assertEqual((restored["authenticity"], restored["freshness"], restored["reason"]),
                         (OF.AUTHENTIC, OF.STALE, "EARLIER_ACCEPTED_STATE"))
        self.assertEqual(gates(restored), {OF.FRESHNESS_BLOCKED})                    # detect != authorize
        commands = set(T._parser()._subparsers._group_actions[0].choices)
        self.assertFalse({c for c in commands if "recover" in c or "repair" in c or "rollback" in c})
        self.assertEqual(len(self.w.records(self.w.a)), 3)                            # detection wrote nothing


class GateMatrix(unittest.TestCase):
    def test_only_authentic_current_passes(self):
        w, s = Rehearsal(self), F.Scenario()
        genesis_docs = s.writer.chain
        pin = w.pin(P32._genesis_digest(genesis_docs))
        unknown = w.step2_classify(w.chain(genesis_docs))                          # no records yet
        w.full("genesis", genesis_docs, pin)
        s.to_current()
        w.full("accept", s.writer.chain, pin)
        current = w.step2_classify(w.chain(s.writer.chain))
        stale = w.step2_classify(w.chain(genesis_docs))
        ledger_step(s, "ahead")
        ahead = w.step2_classify(w.chain(s.writer.chain))
        other = F.Scenario()
        for index in range(3):                            # a longer fork past the accepted W3
            ledger_step(other, f"fork{index}")
        conflicting = w.step2_classify(w.chain(other.writer.chain))
        tampered = [dict(x) for x in s.writer.chain]
        tampered[-1]["ledgerSequence"] += 1
        not_authentic = w.step2_classify(w.chain(tampered))
        code, refused = w.cli("classify", *w.replicas(), "--trust", str(w.trust), "--chain",
                              str(w.chain(genesis_docs)), "--environment", "dev", "--profile", "DEV_SYNTHETIC")
        rows = {"CURRENT": current, "STALE": stale, "AHEAD_UNACCEPTED": ahead, "CONFLICTING": conflicting,
                "FRESHNESS_UNKNOWN": unknown, "NOT_AUTHENTIC": not_authentic}
        self.assertEqual({k: (v["authenticity"], v["freshness"]) for k, v in rows.items()}, {
            "CURRENT": (OF.AUTHENTIC, OF.CURRENT), "STALE": (OF.AUTHENTIC, OF.STALE),
            "AHEAD_UNACCEPTED": (OF.AUTHENTIC, OF.AHEAD_UNACCEPTED), "CONFLICTING": (OF.AUTHENTIC, OF.CONFLICTING),
            "FRESHNESS_UNKNOWN": (OF.AUTHENTIC, OF.FRESHNESS_UNKNOWN),
            "NOT_AUTHENTIC": (OF.NOT_AUTHENTIC, OF.FRESHNESS_UNKNOWN)})
        self.assertEqual((code, refused["status"]), (T.EXIT_REFUSED, "REFUSED"))   # trust inputs are test-only
        refused_state = OF.FreshnessResultV1(OF.NOT_AUTHENTIC, OF.REFUSED, "ENVIRONMENT_MISMATCH")
        self.assertEqual(sorted(current["gates"]), sorted(MATRIX_OPERATIONS))
        for name, result in rows.items():
            expected = OF.FRESHNESS_PRECONDITION_MET if name == "CURRENT" else OF.FRESHNESS_BLOCKED
            self.assertEqual(set(result["gates"].values()), {expected}, name)
        for operation in MATRIX_OPERATIONS:
            self.assertFalse(OF.freshness_gate(refused_state, operation).met, operation)
            self.assertFalse(OF.freshness_gate(OF.FreshnessResultV1(OF.NOT_AUTHENTIC, OF.CURRENT), operation).met)


class RealStateGuard(unittest.TestCase):
    """Guard modelled in temporary directories only: one EMPTY replica and no
    second replica can never be CURRENT. P3-3 is complete and B-3 enables real
    acceptance, but this invariant is permanent: it is kept."""

    def test_one_empty_replica_and_no_replica_b_is_freshness_unknown(self):
        w, s = Rehearsal(self), F.Scenario()
        shutil.rmtree(w.b)                                # Replica B does not exist
        chain = w.chain(s.writer.chain)
        for replicas in (["--replica", str(w.a)], ["--replica", str(w.a), "--replica", str(w.b)]):
            code, result = w.cli("classify", *replicas, *w.world(chain))
            self.assertEqual((code, result["freshness"]), (0, OF.FRESHNESS_UNKNOWN), replicas)
            self.assertEqual(gates(result), {OF.FRESHNESS_BLOCKED})
        # even with a (synthetic) record 1 in A, a single replica never reaches CURRENT
        document_pin = w.pin(P32._genesis_digest(s.writer.chain))
        _, proposed, candidate = w.propose("genesis", chain, document_pin)
        code, result = w.append(w.a, w.a, candidate, chain, document_pin, proposed["recordDigest"])
        self.assertEqual(code, T.EXIT_REFUSED)                                          # no self-peer
        code, result = w.cli("classify", "--replica", str(w.a), *w.world(chain))
        self.assertEqual(result["freshness"], OF.FRESHNESS_UNKNOWN)
        self.assertEqual(T.MINIMUM_REPLICAS, 2)

    def test_documents_keep_the_guard_and_the_open_state(self):
        record = RECORD.read_text(encoding="utf-8")
        for line in ("P3_3_STORAGE_INCOMPLETE", "P3-4 PASSED", "does NOT close P3-3", "FRESHNESS_UNKNOWN"):
            self.assertIn(line, record)
        runbook = RUNBOOK.read_text(encoding="utf-8")
        for step in ("Inspect the authentic chain", "Classify against the owner records", "Generate the candidate",
                     "Human review", "Confirm the exact digest", "Append to Replica A", "Observe the intermediate",
                     "Append to Replica B", "Compare replicas", "Classify CURRENT"):
            self.assertIn(step, runbook)
        for private in ("/root/", "C:\\Users", "AppData", "ext4.vhdx", "/dev/sd"):
            self.assertNotIn(private, runbook, private)


if __name__ == "__main__":
    unittest.main()
