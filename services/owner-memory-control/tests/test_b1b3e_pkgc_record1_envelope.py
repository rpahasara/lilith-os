"""15B2b-B1b-3e Package C: record 1 (Replica A, Replica B) + acceptance envelope 1 (copy A, copy B) design (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-pkgc-record1-envelope-package.md.

Everything here is offline. Replicas, acceptance stores, peer views, acquisitions and work directories are temporary
directories; witness chains are real K-WIT-signed TEST chains (TEST_ONLY profile); the DEV reads are a fake runner
standing in for the pinned read-only mb9_operator forms. The real Replica A, the S25, DEV, the network and every
owner key are never touched. No live Package C step is performed.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

import synthetic_authority as SA  # noqa: F401  (sets sys.path)
import synthetic_b1b3e as F
from lilith_owner_memory import owner_acceptance as OA
from lilith_owner_memory import owner_freshness as OF
from lilith_owner_memory import owner_freshness_tool as T
from lilith_owner_memory import pr1b_sequencing as S
from lilith_owner_memory import witness_readiness as WR

ROOT = SA.ROOT
TOOLS = ROOT / "services/owner-memory-control/tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import pkgc_operator as P  # noqa: E402

RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-pkgc-record1-envelope-package.md"
OPERATOR = TOOLS / "pkgc_operator.py"
PHONE = TOOLS / "pkgc_s25_phone.sh"
ENV, PROFILE = F.ENV, "TEST_ONLY"
A_ID, B_ID = "vault-a", "offline-b"
EVIDENCE = {"PR2_REVALIDATION": hashlib.sha256(b"pr2 revalidation (fresh, C1)").hexdigest(),
            "P3_3_INDEPENDENCE": hashlib.sha256(b"p3-3 independence acceptance").hexdigest()}
INVOCATION, MAIN_PID = "5136ea7af2544450b9370fa412786c98", "143946"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def jbytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def rmtree(path: Path) -> None:
    """Peer views are made read-only; restore write permission so cleanup also works for a non-root user."""
    for item in Path(path).rglob("*"):
        if not item.is_symlink():
            os.chmod(item, 0o700)
    shutil.rmtree(path, True)


def lines_with_hash(lines: list[str]) -> bytes:
    return ("\n".join(lines + ["RESULT_BLOCK_SHA256=" + P.result_block_sha256(lines)]) + "\n").encode()


# ------------------------------------------------------------------ world ---

class World:
    """A synthetic Package C world: owner-held installables, P-A, the committed genesis, a fake presented DEV world
    (read only through the acquisition runner), the laptop (Replica A) and a simulated S25 (Replica B)."""

    def __init__(self, test: unittest.TestCase):
        self.test = test
        self.dir = Path(tempfile.mkdtemp(prefix="pkgc-"))
        test.addCleanup(rmtree, self.dir)
        self.scenario = F.Scenario()
        self.genesis_doc = self.scenario.writer.chain[0]
        self.genesis_bytes = WR.document_bytes(self.genesis_doc)
        tmp = self.dir / "learn"
        tmp.mkdir()
        (tmp / "t.json").write_text(json.dumps(self._trust_doc()), encoding="utf-8")
        (tmp / "c.json").write_text(json.dumps([self.genesis_doc]), encoding="utf-8")
        self.genesis_digest = T.inspect_chain(T.load_trust(tmp / "t.json"), tmp / "c.json", ENV)["genesisWitnessDigest"]
        self.inst = self.dir / "installables"
        self.inst.mkdir()
        self.raw = {"anchor": jbytes(self._trust_doc()["witnessAnchor"]),
                    "root": jbytes(self._trust_doc()["registryRoot"]), "registry": jbytes(F.v3())}
        for key, name in P.INSTALLABLES.items():
            (self.inst / name).write_bytes(self.raw[key])
        self.pa = self.dir / "pin-a"
        self.pa.mkdir()
        self.pin_bytes = jbytes({"pinType": WR.GENESIS_PIN_TYPE, "schemaVersion": 1, "environment": ENV,
                                 "genesisWitnessDigest": self.genesis_digest})
        files = {"genesis-pin.json": self.pin_bytes, "authorization-register.json": b'{"register":"synthetic"}',
                 "pin-record.json": b'{"record":"synthetic"}'}
        for name, data in files.items():
            (self.pa / name).write_bytes(data)
        self.laptop, self.phone = self.dir / "laptop", self.dir / "s25"
        self.laptop.mkdir()
        self.phone.mkdir()
        self.ra, self.rb = self.laptop / "replica-a", self.phone / "replica-b"
        T.init_replica(self.ra, replica_id=A_ID, environment=ENV, authority_profile=PROFILE)
        T.init_replica(self.rb, replica_id=B_ID, environment=ENV, authority_profile=PROFILE)
        self.pins = P.PackageCPinsV1(
            environment=ENV, authority_profile=PROFILE, registry_sha256=sha(self.raw["registry"]),
            root_anchor_sha256=sha(self.raw["root"]), witness_anchor_sha256=sha(self.raw["anchor"]),
            genesis_digest=self.genesis_digest, chain_1_sha256=sha(self.genesis_bytes),
            pin_sha256=sha(self.pin_bytes), register_sha256=sha(files["authorization-register.json"]),
            pin_record_sha256=sha(files["pin-record.json"]), replica_a_id=A_ID, replica_b_id=B_ID,
            replica_b_manifest_sha256=sha((self.rb / T.MANIFEST).read_bytes()),
            witness_invocation_id=INVOCATION, witness_main_pid=MAIN_PID)
        self.workdir = self.laptop / "pkgc-seq1"
        self.control = "c" * 40
        self.facts = {"control": self.control, "lastDeployRunId": "37888892605"}
        self.dev: dict = {}                       # the presented DEV world; overrides per acquisition

    def _trust_doc(self) -> dict:
        return {"trustType": T.TRUST_TYPE, "schemaVersion": 1, "environment": ENV,
                "witnessAnchor": {"schemaVersion": 1, "witnessKeyId": F.WITNESS_KEY_ID, "environment": ENV,
                                  "algorithm": "Ed25519", "publicKey": F.public_b64("witness")},
                "registryRoot": {"schemaVersion": 1, "rootKeyId": SA.ROOT_KEY_ID, "environment": ENV,
                                 "algorithm": "Ed25519", "publicKey": SA.public_b64("root")},
                "registries": [F.v3()]}

    def report(self, **overrides) -> dict:
        report = {"verifierType": "LILITH_MB9_W9", "phase": P.W9_5, "failures": [],
                  "evidence9b": dict.fromkeys(("genesisCommitted", "committedDigestEqualsPin", "chainIsGenesisOnly",
                                               "pointerEqualsGenesis", "retainedAuthorizationsEmpty",
                                               "committedEqualsCandidate"), True),
                  "committedGenesis": {"digest": self.genesis_digest, "fieldsEqualCandidate": True},
                  "witnessInvocationId": INVOCATION, "witnessMainPid": MAIN_PID, "witnessNRestarts": "0",
                  "holdStoreListing": [], "signerLaterState": {"/run/credentials/lilith-authority-signer.service": False},
                  "registryEffective": False, "authorityActive": False, "authorityGranted": False}
        report.update(overrides)
        return report

    # the fake presented DEV world, reached only through the pinned read-only forms
    def runner(self, argv):
        form, out = argv[0], Path(argv[3])
        self.test.assertIn(form, ("host", "chain-export"))                   # never any other mb9 form
        out.mkdir()
        dev = self.dev
        report = json.dumps(self.report(**dev.get("report", {}))).encode()
        if form == "host":
            self.test.assertEqual(argv[4], "POST9B")
            boot, reboot = dev.get("bootId", "boot-1"), dev.get("reboot", "absent")
            (out / "identity.out").write_bytes(
                f"2026-10-09T10:00:00Z\nlilith-dev-01\nmachine\n{boot}\n6.8.0\nREBOOT_REQUIRED={reboot}\n".encode())
            (out / "identity.rc").write_bytes(b"0\n")
            (out / "w9verifier.out").write_bytes(report)
            (out / "w9verifier.err").write_bytes(b"")
            (out / "w9verifier.rc").write_bytes(b"0\n")
            return 0, json.dumps({"result": dev.get("hostResult", "MB9_HOST_POST9B_PASS")}).encode()
        genesis = dev.get("genesis", self.genesis_bytes)
        (out / "chain-1.json").write_bytes(genesis)
        (out / "witness.json").write_bytes(dev.get("pointer", genesis))
        (out / "w9verifier.out").write_bytes(report)
        (out / "w9verifier.err").write_bytes(dev.get("err", b""))
        (out / "w9verifier.rc").write_bytes(dev.get("rc", b"0\n"))
        return 0, json.dumps({"result": "MB9_CHAIN_EXPORTED"}).encode()

    def acquire(self, **dev) -> Path:
        self.dev = dev
        result = P.acquire(Path("repo"), self.workdir, Path("mb9-workdir"), runner=self.runner,
                           pinned={"control": self.control, "operator": "o" * 64})
        return self.workdir / P.EXPORTS_DIR / result["acquisition"]

    def c1(self) -> str:
        return "\n".join(line.format(control=self.control, operator="o" * 64, freshness_tool="f" * 64,
                                     genesis=self.pins.genesis_digest, chain1=self.pins.chain_1_sha256)
                         for line in P.C1_LINES)

    def open(self) -> dict:
        return P.open_sequence(self.workdir, self.c1(), control=self.control, operator="o" * 64,
                               freshness_tool="f" * 64, facts=self.facts, pins=self.pins)

    def bind(self, export: Path | None = None) -> dict:
        return P.bind(self.workdir, self.inst, self.pa, export or self.acquire(), self.ra,
                      EVIDENCE["PR2_REVALIDATION"], EVIDENCE["P3_3_INDEPENDENCE"], pins=self.pins)

    def bundle(self) -> str:
        """Stands in for the S25 bundle tar (its builder is tested separately)."""
        raw = P.bundle_tar({"binding/BINDING.json": (self.workdir / P.BINDING_DIR / P.BINDING_FILE).read_bytes()},
                           "lilith-pkgc-test")
        (self.workdir / P.BUNDLE_FILE).write_bytes(json.dumps({"tarSha256": sha(raw)}).encode())
        return sha(raw)

    def gate(self, stage: str, export: Path | None = None, **fact_overrides) -> dict:
        facts = {"lastDeployRunId": self.facts["lastDeployRunId"], "workflowQueueEmpty": True,
                 "s25BundleSha256": P.bundle_record(self.workdir).get("tarSha256"), **fact_overrides}
        path = self.dir / f"facts-{os.urandom(4).hex()}.json"
        path.write_text(json.dumps(facts), encoding="utf-8")
        return P.gate(self.workdir, stage, export or self.acquire(), path, pins=self.pins)

    def s25(self, stage: str, paths: dict | None = None) -> dict:
        lines = P.s25_expected(self.workdir, stage, paths or {}, pins=self.pins)
        return P.s25_record(self.workdir, stage, paths or {}, lines_with_hash(lines), pins=self.pins)

    def ready(self) -> None:
        """C1 complete: opened, bound, bundled, S25 C1 read recorded."""
        self.open()
        self.bind()
        self.bundle()
        self.s25("C1")

    # the canonical tool, as the owner runs it
    def world(self) -> list[str]:
        b = self.workdir / P.BINDING_DIR
        return ["--trust", str(b / P.TRUST_FILE), "--chain", str(b / P.CHAIN_FILE), "--environment", ENV,
                "--profile", PROFILE]

    def pin(self) -> str:
        return str(self.workdir / P.BINDING_DIR / P.PIN_FILE)

    def tool(self, *argv: str) -> dict:
        code, result = T.run(list(argv))
        return {"code": code, **result}


def tar_extract(raw: bytes, into: Path) -> Path:
    into.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        tar.extractall(into, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    (top,) = list(into.iterdir())
    for line in (top / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        assert sha((top / name).read_bytes()) == digest, name
    return top


def go(stage: str, values: dict) -> str:
    return "\n".join(line.format(**values) for line in P.TEMPLATES[stage])


# ----------------------------------------------------------- state machine ---

def fresh(state: str) -> OF.FreshnessResultV1:
    return OF.FreshnessResultV1(OF.AUTHENTIC, state, None)


def acceptance(state: str) -> OA.AcceptanceResultV1:
    return OA.AcceptanceResultV1(state)


CURRENT = fresh(OF.CURRENT)


class StateMachineTests(unittest.TestCase):
    def steps(self, q: P.PackageCSequenceV1):
        return [
            lambda: q.open(c1_exact=True),
            lambda: q.bind(binding_exact=True, s25_c1_exact=True, register_entry="EMPTY"),
            lambda: q.gate("C2", continuity_exact=True), lambda: q.arm("C2", go_exact=True),
            lambda: q.observe_record_a(replica_a_exact_record1=True, replica_b_empty=True,
                                       freshness=fresh(OF.FRESHNESS_UNKNOWN)),
            lambda: q.gate("C3", continuity_exact=True), lambda: q.arm("C3", go_exact=True),
            lambda: q.observe_record_b(transcription_exact=True, replicas_identical=True, freshness=CURRENT),
            lambda: q.gate("C4A", continuity_exact=True), lambda: q.arm("C4A", go_exact=True, freshness=CURRENT),
            lambda: q.observe_envelope_a(freshness=CURRENT, acceptance=acceptance(OA.ACCEPTANCE_PARTIAL)),
            lambda: q.gate("C4B", continuity_exact=True),
            lambda: q.c4b_eligibility(freshness=CURRENT, acceptance=acceptance(OA.ACCEPTANCE_PARTIAL),
                                      copy_a_exact=True, copy_b_absent=True),
            lambda: q.arm("C4B", go_exact=True, freshness=CURRENT),
            lambda: q.observe_envelope_b(transcription_exact=True, freshness=CURRENT,
                                         acceptance=acceptance(OA.ACCEPTANCE_COMPLETE)),
            lambda: q.gate("C5", continuity_exact=True),
            lambda: q.accept(c5_exact=True, freshness=CURRENT, acceptance=acceptance(OA.ACCEPTANCE_COMPLETE)),
        ]

    def run_to(self, target: str) -> P.PackageCSequenceV1:
        q = P.PackageCSequenceV1()
        for step in self.steps(q):
            if q.state == target:
                break
            result = step()
            self.assertEqual(result.status, "ADVANCED", result)
        return q

    def test_full_sequence_c1_c2_c3_c4a_c4b_c5(self):
        q = self.run_to("never")
        self.assertEqual(q.state, P.PC5)
        self.assertEqual([h for h in q.history if h.startswith("ARM:")], ["ARM:C2", "ARM:C3", "ARM:C4A", "ARM:C4B"])
        self.assertEqual(q.authority_boundary(), {"REGISTRY_EFFECTIVE": "NO", "AUTHORITY_ACTIVE": "NO",
                                                  "authorityGranted": False, "signer": "INACTIVE",
                                                  "HELD": "NOT AUTHORIZED", "FIRST_MEMORY": "NOT AUTHORIZED",
                                                  "PROD": "NOT AUTHORIZED"})
        self.assertIn("NONE", q.next_after_completion())
        for name in dir(q):                                  # no HELD / signer / activation / First Memory transition
            self.assertNotRegex(name.lower(), r"held|signer|activat|first_memory|release|registry_effective")
        self.assertEqual(q.gate("C5", continuity_exact=True).reason, "SEQUENCE_ENDED")

    def test_bootstrap_mapping_is_preserved(self):
        self.assertEqual(P.BOOTSTRAP_STEP, {"C2": "APPEND_RECORD_1_REPLICA_A", "C3": "APPEND_RECORD_1_REPLICA_B",
                                            "C4A": "APPEND_ENVELOPE_1_COPY_A", "C4B": "APPEND_ENVELOPE_1_COPY_B"})
        actions = [s.action for s in S.STEPS]
        order = [actions.index(P.BOOTSTRAP_STEP[s]) for s in P.ARMABLE]
        self.assertEqual(order, sorted(order))
        self.assertEqual(order, list(range(order[0], order[0] + 4)))                       # steps 10, 11, 11a, 11b
        for stage, state in (("C2", P.PC2), ("C3", P.PC3), ("C4A", P.PC4AP), ("C4B", P.PC4B)):
            self.assertEqual(S.BY_ACTION[P.BOOTSTRAP_STEP[stage]].target, P.BOOTSTRAP_STATE[state], stage)
        self.assertEqual(S.STEPS[order[-1] + 1].action, "WRITE_HELD")

    def test_c4a_and_c4b_are_separate_acts(self):
        q = self.run_to(P.PC3)
        self.assertEqual(q.arm("C4B", go_exact=True, freshness=CURRENT).reason, "TRANSITION_OUT_OF_ORDER")
        q.gate("C4A", continuity_exact=True)
        self.assertTrue(q.arm("C4A", go_exact=True, freshness=CURRENT).advanced)
        self.assertEqual(q.arm("C4A", go_exact=True, freshness=CURRENT).reason, "TRANSITION_OUT_OF_ORDER")
        q = self.run_to(P.PC4AP)
        self.assertEqual(q.arm("C4B", go_exact=True, freshness=CURRENT).reason, "FRESH_GATE_REQUIRED")
        q.gate("C4B", continuity_exact=True)
        self.assertEqual(q.arm("C4B", go_exact=True, freshness=CURRENT).reason, "C4B_NOT_ELIGIBLE")
        self.assertTrue({P.PC4AA, P.PC4AP, P.PC4BA, P.PC4B} <= P.PONR_STATES)

    def test_c4b_needs_a_fresh_exact_partial_read_after_its_gate(self):
        q = self.run_to(P.PC4AP)
        ok = dict(freshness=CURRENT, acceptance=acceptance(OA.ACCEPTANCE_PARTIAL), copy_a_exact=True,
                  copy_b_absent=True)
        self.assertEqual(q.c4b_eligibility(**ok).reason, "FRESH_GATE_REQUIRED")           # before its gate
        q.gate("C4B", continuity_exact=True)
        for bad in (dict(ok, acceptance=acceptance(OA.ACCEPTANCE_COMPLETE)),
                    dict(ok, acceptance=acceptance(OA.ACCEPTANCE_NOT_PRESENT)),
                    dict(ok, acceptance=True), dict(ok, copy_a_exact=False), dict(ok, copy_b_absent=False),
                    dict(ok, freshness=fresh(OF.FRESHNESS_UNKNOWN))):
            self.assertEqual(copy.deepcopy(q).c4b_eligibility(**bad).state, P.HALT, bad)
        q.c4b_eligibility(**ok)
        self.assertTrue(q.c4b_eligible)
        q2 = copy.deepcopy(q)                                    # a new gate voids an earlier eligibility read
        q2.gate("C4B", continuity_exact=True)
        self.assertEqual(q2.arm("C4B", go_exact=True, freshness=CURRENT).reason, "C4B_NOT_ELIGIBLE")
        q3 = copy.deepcopy(q)                                    # so does any drift
        q3.invalidate("DEPLOY_OCCURRED")
        self.assertEqual(q3.arm("C4B", go_exact=True, freshness=CURRENT).reason, "FRESH_GATE_REQUIRED")
        self.assertTrue(q.arm("C4B", go_exact=True, freshness=CURRENT).advanced)

    def test_order_is_enforced_and_every_arm_needs_a_fresh_gate(self):
        q = P.PackageCSequenceV1()
        self.assertEqual(q.arm("C2", go_exact=True).reason, "TRANSITION_OUT_OF_ORDER")
        q = self.run_to(P.PC1B)
        self.assertEqual(q.arm("C2", go_exact=True).reason, "FRESH_GATE_REQUIRED")
        self.assertEqual(q.gate("C3", continuity_exact=True).reason, "GATE_OUT_OF_ORDER")
        self.assertEqual(q.gate("C2", continuity_exact=False).reason, "CONTINUITY_NOT_EXACT")
        self.assertEqual(q.arm("C2", go_exact=True).reason, "FRESH_GATE_REQUIRED")
        q.gate("C2", continuity_exact=True)
        self.assertEqual(q.arm("C2", go_exact=False).reason, "GO_NOT_EXACT")
        self.assertTrue(q.arm("C2", go_exact=True).advanced)
        self.assertEqual(q.arm("C2", go_exact=True).reason, "TRANSITION_OUT_OF_ORDER")
        self.assertEqual(self.run_to(P.PC2).arm("C3", go_exact=True).reason, "FRESH_GATE_REQUIRED")
        q = self.run_to(P.PC3)
        q.gate("C4A", continuity_exact=True)
        self.assertEqual(q.arm("C4A", go_exact=True, freshness=fresh(OF.FRESHNESS_UNKNOWN)).reason,
                         "FRESHNESS_NOT_CURRENT")

    def test_replica_a_alone_is_partial_and_unknown_never_current(self):
        q = self.run_to(P.PC2A)
        bad = q.observe_record_a(replica_a_exact_record1=True, replica_b_empty=True, freshness=CURRENT)
        self.assertEqual((bad.status, bad.state, bad.reason), ("HALTED", P.HALT, "OWNER_RECORD_INCONSISTENT"))
        q = self.run_to(P.PC2A)
        self.assertEqual(q.observe_record_a(replica_a_exact_record1=True, replica_b_empty=True,
                                            freshness=True).state, P.HALT)              # a boolean is never freshness

    def test_current_requires_record_b(self):
        q = self.run_to(P.PC3A)
        for freshness in (fresh(OF.FRESHNESS_UNKNOWN), None, True):
            self.assertEqual(copy.deepcopy(q).observe_record_b(transcription_exact=True, replicas_identical=True,
                                                               freshness=freshness).state, P.HALT)
        r = copy.deepcopy(q).observe_record_b(transcription_exact=False, replicas_identical=True, freshness=CURRENT)
        self.assertEqual((r.status, r.state, r.reason), ("REVALIDATE", P.PC3A, "TRANSCRIPTION_MISMATCH"))

    def test_envelope_partial_and_complete_are_explicit(self):
        q = self.run_to(P.PC4AA)
        for state in (OA.ACCEPTANCE_COMPLETE, OA.ACCEPTANCE_NOT_PRESENT, OA.ACCEPTANCE_UNKNOWN):
            self.assertEqual(copy.deepcopy(q).observe_envelope_a(freshness=CURRENT, acceptance=acceptance(state)).state,
                             P.HALT, state)
        q = self.run_to(P.PC4BA)
        self.assertEqual(copy.deepcopy(q).observe_envelope_b(transcription_exact=True, freshness=CURRENT,
                                                             acceptance=acceptance(OA.ACCEPTANCE_PARTIAL)).state,
                         P.HALT)
        q = self.run_to(P.PC4B)
        self.assertEqual(q.accept(c5_exact=True, freshness=CURRENT,
                                  acceptance=acceptance(OA.ACCEPTANCE_COMPLETE)).reason, "FRESH_GATE_REQUIRED")

    def test_drift_never_advances_and_enters_revalidation(self):
        for target in (P.PC1B, P.PC2, P.PC3, P.PC4AP, P.PC4B):
            for event in sorted(P.REVALIDATE_EVENTS):
                q = self.run_to(target)
                r = q.invalidate(event)
                self.assertEqual((r.status, q.state), ("REVALIDATE", target), (target, event))
                self.assertTrue(q.revalidate)
        for event in sorted(P.HALT_EVENTS):
            q = self.run_to(P.PC2)
            self.assertEqual(q.invalidate(event).state, P.HALT, event)
            self.assertEqual(q.gate("C3", continuity_exact=True).reason, "SEQUENCE_ENDED")
            self.assertEqual(q.reset().reason, "OWNER_RECORD_PONR_PASSED")
        self.assertEqual(self.run_to(P.PC3).invalidate("SOMETHING_NEW").reason, "EVIDENCE_UNKNOWN")

    def test_points_of_no_return_and_stop(self):
        self.assertTrue(self.run_to(P.PC1B).stop().advanced)
        self.assertTrue(self.run_to(P.PC1B).reset().advanced)
        q = self.run_to(P.PC2A)
        self.assertEqual(q.stop().reason, "STOP_REFUSED_ATTEMPT_MARKER_PRESENT")
        self.assertEqual(q.reset().reason, "OWNER_RECORD_PONR_PASSED")
        self.assertEqual(P.PONR_STATES, {P.PC2A, P.PC2, P.PC3A, P.PC3, P.PC4AA, P.PC4AP, P.PC4BA, P.PC4B, P.PC5})

    def test_resume_only_at_canonical_recoverable_points(self):
        for entry, state in P.RESUMABLE.items():
            q = P.PackageCSequenceV1()
            q.open(c1_exact=True)
            self.assertEqual(q.bind(binding_exact=True, s25_c1_exact=True, register_entry=entry).state, state)
        q = P.PackageCSequenceV1()
        q.open(c1_exact=True)
        self.assertEqual(q.bind(binding_exact=True, s25_c1_exact=True, register_entry="B_ONLY").state, P.HALT)
        self.assertEqual(P.RESUMABLE["ENVELOPE_A_ONLY"], P.PC4AP)                   # C4B still needs its eligibility


# ------------------------------------------------------------- acquisition ---

class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.w = World(self)
        self.w.open()

    def test_receipt_binds_the_whole_read(self):
        export = self.w.acquire()
        receipt = json.loads((export / P.RECEIPT_FILE).read_text())
        opening = json.loads((self.w.workdir / P.C1_FILE).read_text())
        self.assertEqual(receipt["sequenceId"], opening["sequenceId"])
        self.assertEqual(receipt["control"], self.w.control)
        self.assertEqual(receipt["toolPins"], P.TOOL_PINS)
        self.assertRegex(receipt["startedAt"], r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
        self.assertEqual([receipt["commands"][k]["form"] for k in ("host", "chain")], ["host", "chain-export"])
        self.assertEqual(receipt["commands"]["host"]["args"][3], "POST9B")
        facts = receipt["facts"]
        self.assertEqual((facts["phase"], facts["hostPhase"]), (P.W9_5, P.W9_5))
        self.assertEqual((facts["witnessInvocationId"], facts["witnessMainPid"], facts["witnessNRestarts"]),
                         (INVOCATION, MAIN_PID, "0"))
        self.assertEqual((facts["bootId"], facts["rebootRequired"]), ("boot-1", "absent"))
        self.assertEqual((facts["committedDigest"], facts["chain1Sha256"]),
                         (self.w.genesis_digest, sha(self.w.genesis_bytes)))
        self.assertEqual(receipt["artifacts"]["chain/chain-1.json"], sha(self.w.genesis_bytes))
        self.assertEqual(P.verify_acquisition(self.w.workdir, export)["facts"], facts)
        self.assertEqual(sorted(os.listdir(self.w.workdir / P.ACQUISITIONS_DIR)),
                         [f"{export.name}.completed.json", f"{export.name}.started.json"])

    def test_identical_bytes_are_fine_but_an_old_export_never_counts(self):
        first, second = self.w.acquire(), self.w.acquire()
        self.assertEqual((first / "chain/chain-1.json").read_bytes(), (second / "chain/chain-1.json").read_bytes())
        P.verify_acquisition(self.w.workdir, second)                        # fresh read, same immutable bytes
        copied = self.w.workdir / P.EXPORTS_DIR / f"09-{'a' * 32}"          # old export in a NEW directory
        shutil.copytree(first, copied)
        with self.assertRaises(P.Stop) as caught:
            P.verify_acquisition(self.w.workdir, copied)
        self.assertEqual(caught.exception.reason, "ACQUISITION_NOT_FRESH:NOT_IN_SEQUENCE_LOG")
        bare = self.w.workdir / P.EXPORTS_DIR / f"10-{'b' * 32}"           # a bare historical export, no receipt
        shutil.copytree(first / "chain", bare / "chain")
        with self.assertRaises(P.Stop) as caught:
            P.verify_acquisition(self.w.workdir, bare)
        self.assertEqual(caught.exception.reason, "ACQUISITION_NOT_FRESH:NO_RECEIPT")
        outside = self.w.dir / first.name
        shutil.copytree(first, outside)
        with self.assertRaises(P.Stop) as caught:
            P.verify_acquisition(self.w.workdir, outside)
        self.assertEqual(caught.exception.reason, "EXPORT_NOT_IN_SEQUENCE")

    def test_a_receipt_from_another_sequence_never_counts(self):
        other = World(self)
        other.open()
        theirs = other.acquire()
        mine = self.w.workdir / P.EXPORTS_DIR / theirs.name
        shutil.copytree(theirs, mine)
        (self.w.workdir / P.ACQUISITIONS_DIR).mkdir(exist_ok=True)
        for suffix in ("started", "completed"):                             # even with their log entries
            shutil.copy(other.workdir / P.ACQUISITIONS_DIR / f"{theirs.name}.{suffix}.json",
                        self.w.workdir / P.ACQUISITIONS_DIR / f"{theirs.name}.{suffix}.json")
        with self.assertRaises(P.Stop) as caught:
            P.verify_acquisition(self.w.workdir, mine)
        self.assertIn("sequenceBound", caught.exception.reason)

    def test_tampering_after_the_read_is_detected(self):
        export = self.w.acquire()
        (export / "chain" / "w9verifier.out").write_bytes(json.dumps(self.w.report(witnessMainPid="1")).encode())
        with self.assertRaises(P.Stop) as caught:
            P.verify_acquisition(self.w.workdir, export)
        self.assertIn("artifactsExact", caught.exception.reason)
        export = self.w.acquire()
        receipt = json.loads((export / P.RECEIPT_FILE).read_text())
        os.chmod(export / P.RECEIPT_FILE, 0o600)
        (export / P.RECEIPT_FILE).write_bytes(P._document({**receipt, "control": "d" * 40}))
        with self.assertRaises(P.Stop) as caught:
            P.verify_acquisition(self.w.workdir, export)
        self.assertIn("receiptLogged", caught.exception.reason)

    def test_a_failed_read_is_not_fresh(self):
        export = self.w.acquire(hostResult="MB9_HOST_POST9B_NOT_PASS")
        with self.assertRaises(P.Stop) as caught:
            P.verify_acquisition(self.w.workdir, export)
        self.assertIn("commandsExact", caught.exception.reason)

    def test_acquire_only_runs_the_two_read_only_forms_and_checks_the_control(self):
        seen = []

        def runner(argv):
            seen.append(argv[0])
            return self.w.runner(argv)

        P.acquire(Path("repo"), self.w.workdir, Path("mb9"), runner=runner,
                  pinned={"control": self.w.control, "operator": "o" * 64})
        self.assertEqual(seen, ["host", "chain-export"])
        with self.assertRaises(P.Stop) as caught:
            P.acquire(Path("repo"), self.w.workdir, Path("mb9"), runner=runner,
                      pinned={"control": "d" * 40, "operator": "o" * 64})
        self.assertEqual(caught.exception.reason, "CONTROL_CHANGED")


# ----------------------------------------------------------------- binding ---

class BindingTests(unittest.TestCase):
    def setUp(self):
        self.w = World(self)
        self.w.open()

    def test_binding_is_exact_deterministic_and_the_tool_reads_it_authentic(self):
        self.assertEqual(self.w.bind()["result"], "PKGC_BINDING_EXACT")
        binding, _ = P.load_binding(self.w.workdir)
        self.assertEqual((binding["snapshot"]["phase"], binding["snapshot"]["bootId"]), (P.W9_5, "boot-1"))
        self.assertEqual(binding["attachedEvidence"], EVIDENCE)
        self.assertEqual(binding["freshness"], "UNKNOWN")
        trust = T.load_trust(self.w.workdir / P.BINDING_DIR / P.TRUST_FILE)
        inspected = T.inspect_chain(trust, self.w.workdir / P.BINDING_DIR / P.CHAIN_FILE, ENV)
        self.assertEqual((inspected["authenticity"], inspected["entries"], inspected["genesisWitnessDigest"]),
                         (OF.AUTHENTIC, 1, self.w.genesis_digest))
        other = World(self)
        self.assertEqual(other.pins, self.w.pins)
        other.open()
        other.bind()
        for name in (P.TRUST_FILE, P.CHAIN_FILE, P.PIN_FILE):
            self.assertEqual((other.workdir / P.BINDING_DIR / name).read_bytes(),
                             (self.w.workdir / P.BINDING_DIR / name).read_bytes(), name)

    def test_acquisition_must_be_exact(self):
        cases = {
            "w9PhaseExact": dict(report={"phase": "W9_LATER_STATE"}),
            "w9NoFailures": dict(report={"failures": ["X"]}),
            "committedDigestIsAccepted": dict(report={"committedGenesis": {"digest": "0" * 64}}),
            "chain1BytesAccepted": dict(genesis=self.w.genesis_bytes + b" "),
            "pointerEqualsGenesis": dict(pointer=b"{}"),
            "incarnationAccepted": dict(report={"witnessMainPid": "999"}),
            "noRestart": dict(report={"witnessNRestarts": None}),               # UNKNOWN is not 0
            "rebootRequiredAbsent": dict(reboot="present"),
            "holdStoreEmpty": dict(report={"holdStoreListing": ["held.json"]}),
            "signerNoLaterState": dict(report={"signerLaterState": {"x": True}}),
            "registryNotEffective": dict(report={"registryEffective": True}),
            "authorityNotActive": dict(report={"authorityGranted": True}),
        }
        for check, dev in cases.items():
            result = P.check_export(self.w.workdir, self.w.acquire(**dev), self.w.pins)
            self.assertFalse(result["exact"], check)
            self.assertFalse(result["checks"][check], check)
        for dev, reason in ((dict(rc=b"1\n"), "W9_VERIFIER_FAILED"), (dict(err=b"warn"), "W9_VERIFIER_STDERR")):
            with self.assertRaises(P.Stop) as caught:
                P.check_export(self.w.workdir, self.w.acquire(**dev), self.w.pins)
            self.assertEqual(caught.exception.reason, reason)
        with self.assertRaises(P.Stop) as caught:
            self.w.bind(self.w.acquire(report={"phase": "W9_5S_GENESIS_COMMITTED_STOPPED"}))
        self.assertTrue(caught.exception.reason.startswith("EXPORT_NOT_EXACT:"))
        self.assertFalse((self.w.workdir / P.BINDING_DIR).exists())

    def test_owner_held_inputs_must_be_the_accepted_bytes(self):
        for pin_field, reason in (("registry_sha256", "REGISTRY_NOT_ACCEPTED"),
                                  ("witness_anchor_sha256", "WITNESS_ANCHOR_NOT_ACCEPTED"),
                                  ("pin_sha256", "PIN_BYTES_NOT_ACCEPTED")):
            with self.assertRaises(P.Stop) as caught:
                P.bind(self.w.workdir, self.w.inst, self.w.pa, self.w.acquire(), self.w.ra, *EVIDENCE.values(),
                       pins=dataclasses.replace(self.w.pins, **{pin_field: "0" * 64}))
            self.assertEqual(caught.exception.reason, reason)
        (self.w.pa / "extra").write_bytes(b"x")
        with self.assertRaises(P.Stop) as caught:
            self.w.bind()
        self.assertEqual(caught.exception.reason, "PIN_DIRECTORY_INEXACT")

    def test_binding_outputs_are_tamper_evident_and_acquisitions_single_use(self):
        export = self.w.acquire()
        self.w.bind(export)
        with self.assertRaises(P.Stop) as caught:
            self.w.gate("C2", export)
        self.assertEqual(caught.exception.reason, "EXPORT_REUSED")
        path = self.w.workdir / P.BINDING_DIR / P.CHAIN_FILE
        os.chmod(path, 0o600)
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(P.Stop) as caught:
            P.load_binding(self.w.workdir)
        self.assertEqual(caught.exception.reason, "BINDING_OUTPUT_CHANGED:" + P.CHAIN_FILE)


# -------------------------------------------------------------- continuity ---

class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.w = World(self)
        self.w.ready()

    def test_fresh_gate_passes(self):
        self.assertEqual(self.w.gate("C2")["result"], "PKGC_GATE_PASS")
        self.assertTrue(P.last_gate(self.w.workdir, "C2")[0]["acquisitionReceiptSha256"])

    def test_each_invalidator(self):
        cases = {
            "DEPLOY_OCCURRED": ({}, dict(lastDeployRunId="37999999999")),
            "S25_BUNDLE_MISMATCH": ({}, dict(s25BundleSha256="e" * 64)),
            "WORKFLOW_QUEUE_NOT_EMPTY": ({}, dict(workflowQueueEmpty=False)),
            "EVIDENCE_UNKNOWN": ({}, dict(lastDeployRunId=None)),
            "BOOT_ID_CHANGED": (dict(bootId="boot-2"), {}),
            "REBOOT_REQUIRED_PRESENT": (dict(reboot="present"), {}),
            "WITNESS_INCARNATION_CHANGED": (dict(report={"witnessInvocationId": "f" * 32}), {}),
            "WITNESS_RESTARTED": (dict(report={"witnessNRestarts": "1"}), {}),
            "CHAIN_ADVANCED": (dict(report={"phase": "W9_LATER_STATE"}), {}),
            "W9_PHASE_NOT_EXACT": (dict(report={"phase": "W9_5S_GENESIS_COMMITTED_STOPPED"}), {}),
            "GENESIS_MISMATCH": (dict(report={"committedGenesis": {"digest": "0" * 64}}), {}),
            "CHAIN_BYTES_CHANGED": (dict(pointer=b"{}"), {}),
            "HOLD_STORE_NOT_EMPTY": (dict(report={"holdStoreListing": ["h"]}), {}),
            "SIGNER_ACTIVE": (dict(report={"signerLaterState": {"s": True}}), {}),
            "AUTHORITY_GRANTED": (dict(report={"authorityGranted": True}), {}),
            "REGISTRY_EFFECTIVE": (dict(report={"registryEffective": True}), {}),
        }
        for event, (dev, facts) in cases.items():
            result = self.w.gate("C2", self.w.acquire(**dev), **facts)
            route = "HALT" if event in P.HALT_EVENTS else "REVALIDATE"
            self.assertEqual(result["result"], "PKGC_GATE_" + route, event)
            self.assertIn(event, result["events"], event)
            if not dev.get("report"):
                self.assertEqual(result["events"], [event], event)

    def test_a_stale_export_is_a_revalidation_never_a_pass(self):
        stale = self.w.workdir / P.EXPORTS_DIR / f"20-{'c' * 32}"
        shutil.copytree(self.w.acquire(), stale)
        result = self.w.gate("C2", stale)
        self.assertEqual((result["result"], result["events"]), ("PKGC_GATE_REVALIDATE", ["ACQUISITION_NOT_FRESH"]))
        with self.assertRaises(P.Stop):
            P.last_gate(self.w.workdir, "C2")

    def test_gate_order_and_the_last_exact_gate(self):
        self.w.gate("C2", self.w.acquire(bootId="boot-2"))
        with self.assertRaises(P.Stop) as caught:
            P.last_gate(self.w.workdir, "C2")
        self.assertEqual(caught.exception.reason, "FRESH_GATE_REQUIRED")
        self.w.gate("C2")
        self.assertTrue(P.last_gate(self.w.workdir, "C2")[0]["exact"])
        with self.assertRaises(P.Stop):
            P.last_gate(self.w.workdir, "C3")


# -------------------------------------------------------------- peer views ---

class PeerViewTests(unittest.TestCase):
    def setUp(self):
        self.w = World(self)
        self.w.ready()

    def test_views_are_non_custody_read_only_and_only_under_the_workdir(self):
        result = P.peer_view(self.w.workdir, "replica-b-0", pins=self.w.pins)
        view = self.w.workdir / P.VIEWS_DIR / "replica-b-0"
        provenance = json.loads((self.w.workdir / P.VIEWS_DIR / "replica-b-0.provenance.json").read_text())
        self.assertEqual(provenance["custody"], "NON_CUSTODY_PEER_VIEW")
        self.assertEqual(provenance["treeSha256"], result["viewSha256"])
        self.assertEqual(provenance["evidence"]["s25Stage"], "C1")
        self.assertEqual(sorted(os.listdir(view)), [T.MANIFEST, T.RECORDS])            # provenance beside, not inside
        if os.name == "posix":
            for item in [view, *view.rglob("*")]:
                self.assertEqual(os.stat(item).st_mode & 0o222, 0, item)               # read-only
        self.assertFalse(P._under_custody_root(self.w.workdir))
        for canonical in (self.w.ra, self.w.rb):
            self.assertNotIn(Path(os.path.abspath(canonical)), Path(os.path.abspath(view)).parents)
        with self.assertRaises(P.Stop) as caught:
            P.peer_view(self.w.workdir, "replica-b-0", pins=self.w.pins)
        self.assertEqual(caught.exception.reason, "VIEW_EXISTS")

    def test_never_under_a_canonical_root_and_never_a_canonical_copy_inside(self):
        nested = World(self)
        nested.workdir = nested.ra / "records" / "pkgc"
        with self.assertRaises(P.Stop) as caught:
            nested.open()
        self.assertEqual(caught.exception.reason, "WORKDIR_UNDER_CUSTODY_ROOT")
        inside = World(self)
        inside.open()
        moved = inside.workdir / "replica-a"
        shutil.copytree(inside.ra, moved)
        with self.assertRaises(P.Stop) as caught:
            P.bind(inside.workdir, inside.inst, inside.pa, inside.acquire(), moved, *EVIDENCE.values(),
                   pins=inside.pins)
        self.assertEqual(caught.exception.reason, "CANONICAL_COPY_INSIDE_WORKDIR")
        with self.assertRaises(P.Stop) as caught:
            P.laptop_freshness(self.w.workdir, self.w.workdir / P.VIEWS_DIR, "replica-b-0")
        self.assertEqual(caught.exception.reason, "CANONICAL_COPY_INSIDE_WORKDIR")

    def test_views_are_bound_to_the_opposite_side_transcription(self):
        for kind in ("replica-b-1", "store-b-0", "store-b-1"):
            with self.assertRaises(P.Stop) as caught:
                P.peer_view(self.w.workdir, kind, self.w.ra, pins=self.w.pins)
            self.assertTrue(caught.exception.reason.startswith("S25_TRANSCRIPTION_ABSENT"), (kind, caught.exception))
        mismatch = World(self)
        mismatch.open()
        mismatch.bind()
        mismatch.bundle()
        P.s25_record(mismatch.workdir, "C1", {}, b"PKGC_S25_STAGE=C1\nREPLICA_B_RECORDS=1\n", pins=mismatch.pins)
        with self.assertRaises(P.Stop) as caught:
            P.peer_view(mismatch.workdir, "replica-b-0", pins=mismatch.pins)
        self.assertEqual(caught.exception.reason, "S25_TRANSCRIPTION_NOT_EXACT:C1")

    def test_a_view_never_makes_anything_current_by_existing(self):
        """A hand-made Replica B view holding record 1 while the real B is empty: the canonical tool alone would
        say CURRENT; the operator counts only a provenance-bound view and says UNKNOWN."""
        P.peer_view(self.w.workdir, "replica-b-0", pins=self.w.pins)
        cand = self.w.dir / "cand.json"
        proposed = self.w.tool("propose-genesis", *self.w.world(), "--pin", self.w.pin(), "--out", str(cand))
        view0 = P.load_view(self.w.workdir, "replica-b-0")
        self.w.tool("append", "--replica", str(self.w.ra), "--peer", str(view0), "--candidate", str(cand),
                    *self.w.world(), "--pin", self.w.pin(), "--confirm-digest", proposed["recordDigest"])
        forged = self.w.workdir / P.VIEWS_DIR / "replica-b-1"
        shutil.copytree(self.w.ra, forged)
        (forged / T.MANIFEST).chmod(0o600)
        (forged / T.MANIFEST).write_bytes(P.replica_b_manifest(self.w.pins))
        raw = self.w.tool("classify", "--replica", str(self.w.ra), "--replica", str(forged), *self.w.world())
        self.assertEqual(raw["freshness"], OF.CURRENT)                                 # the tool cannot tell
        counted = P.laptop_freshness(self.w.workdir, self.w.ra, "replica-b-1")
        self.assertEqual((counted.freshness, counted.reason), (OF.FRESHNESS_UNKNOWN, "PEER_VIEW_NOT_PROVEN"))
        acc = P.laptop_acceptance(self.w.workdir, self.w.ra, self.w.laptop / "none", "replica-b-1", "store-b-0")
        self.assertEqual(acc.state, OA.ACCEPTANCE_UNKNOWN)
        self.assertEqual(os.listdir(self.w.rb / T.RECORDS), [])                        # the real B is untouched

    def test_a_changed_view_loses_its_provenance(self):
        P.peer_view(self.w.workdir, "replica-b-0", pins=self.w.pins)
        view = self.w.workdir / P.VIEWS_DIR / "replica-b-0"
        os.chmod(view / T.RECORDS, 0o700)
        (view / T.RECORDS / f"000001-{'d' * 64}.json").write_bytes(b"{}")
        with self.assertRaises(P.Stop) as caught:
            P.load_view(self.w.workdir, "replica-b-0")
        self.assertEqual(caught.exception.reason, "PEER_VIEW_NOT_PROVEN")
        self.assertEqual(P.laptop_freshness(self.w.workdir, self.w.ra, "replica-b-0").reason, "PEER_VIEW_NOT_PROVEN")

    def test_operator_never_discovers_copies(self):
        """Directory enumeration happens only over operator-owned directories or copies being hashed; canonical
        replicas and stores are read only from explicit paths, and freshness only through proven views."""
        source = OPERATOR.read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = [f for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)]
        allowed = {"_artifacts", "tree_digest", "_make_read_only", "_exact_listing", "_consumed", "verify_acquisition",
                   "acquire", "last_gate", "gate", "s25_bundle_members", "build_transfer", "_acquired_facts"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr in ("iterdir", "rglob", "glob", "listdir", "walk", "scandir"):
                owner = min((f for f in functions if f.lineno <= node.lineno <= f.end_lineno),
                            key=lambda f: f.end_lineno - f.lineno).name
                self.assertIn(owner, allowed, (owner, node.lineno))
        register_users = {min((f for f in functions if f.lineno <= n.lineno <= f.end_lineno),
                              key=lambda f: f.end_lineno - f.lineno).name
                          for n in ast.walk(tree) if isinstance(n, ast.Attribute)
                          and n.attr in ("load_register", "classify_acceptance_state")}
        self.assertEqual(register_users, {"laptop_freshness", "laptop_acceptance"})


# ---------------------------------------------------- end-to-end ceremony ---

class CeremonyTests(unittest.TestCase):
    """C1 → C2 → C3 → C4A → C4B → C5 with the canonical tool, the laptop and a simulated S25 in separate directories.
    The operator never writes a record; every record / envelope write is the canonical tool's own."""

    def test_package_c_end_to_end(self):
        w = World(self)
        q = P.PackageCSequenceV1()
        boot = S.BootstrapSequencerV1(state="WITNESS_GENESIS_COMMITTED")
        # ---- C1
        self.assertEqual(w.open()["result"], "PKGC_SEQUENCE_OPENED_READ_ONLY")
        q.open(c1_exact=True)
        w.bind()
        w.bundle()
        self.assertTrue(w.s25("C1")["exact"])
        register, _ = T.load_register([w.ra, w.rb])
        self.assertEqual(S.owner_register_state(register), S.KNOWN_EMPTY)
        self.assertEqual(q.bind(binding_exact=True, s25_c1_exact=True, register_entry="EMPTY").state, P.PC1B)
        _, binding_sha = P.load_binding(w.workdir)

        # ---- C2
        P.peer_view(w.workdir, "replica-b-0", pins=w.pins)
        vb0 = P.load_view(w.workdir, "replica-b-0")
        cand = w.workdir / "record1-candidate.json"
        proposed = w.tool("propose-genesis", *w.world(), "--pin", w.pin(), "--out", str(cand))
        package = w.workdir / "review-package.json"
        built = w.tool("build-review-package", "--replica", str(w.ra), "--replica", str(vb0), *w.world(),
                       "--pin", w.pin(), "--candidate", str(cand), "--out", str(package),
                       *[x for k, v in EVIDENCE.items() for x in ("--evidence", f"{k}={v}")])
        self.assertEqual(built["code"], 0, built)
        self.assertEqual(w.gate("C2")["result"], "PKGC_GATE_PASS")
        q.gate("C2", continuity_exact=True)
        paths2 = {"candidate": str(cand), "package": str(package), "replicaA": str(w.ra)}
        values = P.derive_values(w.workdir, "C2", paths2, pins=w.pins)
        self.assertEqual((values["record"], values["package"]), (proposed["recordDigest"], built["packageDigest"]))
        gate_sha = P.last_gate(w.workdir, "C2")[1]
        with self.assertRaises(P.Stop) as caught:
            P.arm(w.workdir, "C2", go("C2", {**values, "record": "0" * 64, "binding": binding_sha, "gate": gate_sha}),
                  paths2, pins=w.pins)
        self.assertEqual(caught.exception.reason, "GO_LINE_MISSING")
        go2 = go("C2", {**values, "binding": binding_sha, "gate": gate_sha})
        self.assertEqual(P.arm(w.workdir, "C2", go2, paths2, pins=w.pins)["bootstrapStep"],
                         "APPEND_RECORD_1_REPLICA_A")
        with self.assertRaises(P.Stop) as caught:
            P.arm(w.workdir, "C2", go2, paths2, pins=w.pins)
        self.assertEqual(caught.exception.reason, "ATTEMPT_ALREADY_CONSUMED:C2")
        with self.assertRaises(P.Stop) as caught:
            P.record_act(w.workdir, "STOP", "x", {}, pins=w.pins)
        self.assertEqual(caught.exception.reason, "STOP_REFUSED_ATTEMPT_MARKER_PRESENT")
        q.arm("C2", go_exact=True)
        a = w.tool("append", "--replica", str(w.ra), "--peer", str(vb0), "--candidate", str(cand), *w.world(),
                   "--pin", w.pin(), "--confirm-digest", proposed["recordDigest"])
        self.assertEqual((a["code"], a["replication"]), (0, "PEER_PENDING"), a)
        self.assertEqual(os.listdir(vb0 / T.RECORDS), [])                                # the view is never written
        partial = P.laptop_freshness(w.workdir, w.ra, "replica-b-0")
        self.assertEqual(partial.freshness, OF.FRESHNESS_UNKNOWN)
        raw = w.tool("classify", "--replica", str(w.ra), "--replica", str(vb0), *w.world())
        self.assertEqual(set(raw["gates"].values()), {OF.FRESHNESS_BLOCKED})
        early = w.tool("propose-envelope", "--replica", str(w.ra), "--replica", str(vb0), "--store", "x", "--store",
                       "y", "--package", str(package), "--out", str(w.workdir / "early.json"))
        self.assertEqual(early["reason"], "OWNER_REGISTER_NOT_VERIFIED")
        self.assertEqual(q.observe_record_a(replica_a_exact_record1=True, replica_b_empty=True,
                                            freshness=partial).state, P.PC2)
        self.assertTrue(boot.advance("APPEND_RECORD_1_REPLICA_A", {
            **dict.fromkeys(S.BY_ACTION["APPEND_RECORD_1_REPLICA_A"].evidence, True), "ownerRegister": register}).advanced)
        self.assertEqual(boot.advance("APPEND_ENVELOPE_1_COPY_A", {}).reason, "TRANSITION_OUT_OF_ORDER")

        # ---- C3 (S25)
        t2 = P.build_transfer(w.workdir, "replica-a", {"replicaA": str(w.ra)}, w.dir / "t2.tar", pins=w.pins)
        a_view = tar_extract((w.dir / "t2.tar").read_bytes(), w.phone / "lilith-pkgc" / "views" / "a") / "replica-a"
        self.assertEqual(P.tree_digest(a_view), t2["treeSha256"])
        self.assertEqual(w.gate("C3")["result"], "PKGC_GATE_PASS")
        q.gate("C3", continuity_exact=True)
        paths3 = {"replicaA": str(w.ra), "replicaBPath": str(w.rb)}
        values3 = P.derive_values(w.workdir, "C3", paths3, pins=w.pins)
        P.arm(w.workdir, "C3", go("C3", {**values3, "binding": binding_sha, "gate": P.last_gate(w.workdir, "C3")[1]}),
              paths3, pins=w.pins)
        q.arm("C3", go_exact=True)
        phone_cand = w.phone / "candidate.json"
        again = w.tool("propose-genesis", *w.world(), "--pin", w.pin(), "--out", str(phone_cand))
        self.assertEqual(again["recordDigest"], proposed["recordDigest"])
        b = w.tool("append", "--replica", str(w.rb), "--peer", str(a_view), "--candidate", str(phone_cand),
                   *w.world(), "--pin", w.pin(), "--confirm-digest", proposed["recordDigest"])
        self.assertEqual((b["code"], b["replication"]), (0, "REPLICAS_IDENTICAL"), b)
        on_phone = w.tool("classify", "--replica", str(w.rb), "--replica", str(a_view), *w.world())
        self.assertEqual((on_phone["authenticity"], on_phone["freshness"]), (OF.AUTHENTIC, OF.CURRENT))
        self.assertTrue(w.s25("C3", {"replicaA": str(w.ra)})["exact"])
        P.peer_view(w.workdir, "replica-b-1", w.ra, pins=w.pins)
        self.assertEqual(P.tree_digest(P.load_view(w.workdir, "replica-b-1")), P.tree_digest(w.rb))  # = real B
        current = P.laptop_freshness(w.workdir, w.ra, "replica-b-1")
        self.assertTrue(current.current)
        self.assertEqual(q.observe_record_b(transcription_exact=True, replicas_identical=True, freshness=current).state,
                         P.PC3)
        self.assertTrue(boot.advance("APPEND_RECORD_1_REPLICA_B", {
            **dict.fromkeys(S.BY_ACTION["APPEND_RECORD_1_REPLICA_B"].evidence, True), "freshness": current}).advanced)

        # ---- C4A (laptop)
        sa = w.laptop / "store-a"
        P.peer_view(w.workdir, "store-b-0", pins=w.pins)
        sb0, vb1 = P.load_view(w.workdir, "store-b-0"), P.load_view(w.workdir, "replica-b-1")
        self.assertEqual(w.gate("C4A")["result"], "PKGC_GATE_PASS")
        q.gate("C4A", continuity_exact=True)
        # the go binds the envelope digest; a throwaway empty store A' lets the tool propose it (a proposal only)
        prop = w.dir / "store-a-proposal"
        T.init_acceptance_store(prop, custody_copy_id=A_ID, environment=ENV, authority_profile=PROFILE)
        ecand = w.workdir / "envelope-candidate.json"
        env = w.tool("propose-envelope", "--replica", str(w.ra), "--replica", str(vb1), "--store", str(prop),
                     "--store", str(sb0), "--package", str(package), "--out", str(ecand))
        self.assertEqual(env["code"], 0, env)
        paths4a = {"replicaA": str(w.ra), "envelopeCandidate": str(ecand), "package": str(package),
                   "storeAPath": str(sa)}
        values4a = P.derive_values(w.workdir, "C4A", paths4a, pins=w.pins)
        P.arm(w.workdir, "C4A", go("C4A", {**values4a, "binding": binding_sha,
                                           "gate": P.last_gate(w.workdir, "C4A")[1]}), paths4a, pins=w.pins)
        with self.assertRaises(P.Stop) as caught:                                        # C4B is its own act
            P.arm(w.workdir, "C4B", "x", {}, pins=w.pins)
        self.assertEqual(caught.exception.reason, "FRESH_GATE_REQUIRED")
        q.arm("C4A", go_exact=True, freshness=current)
        self.assertEqual(w.tool("init-acceptance-store", "--store", str(sa), "--custody-copy-id", A_ID,
                                "--environment", ENV, "--profile", PROFILE)["code"], 0)
        ea = w.tool("append-envelope", "--replica", str(w.ra), "--replica", str(vb1), *w.world(), "--pin", w.pin(),
                    "--store", str(sa), "--peer-store", str(sb0), "--candidate", str(ecand),
                    "--confirm-digest", env["envelopeDigest"])
        self.assertEqual((ea["code"], ea["replication"]), (0, "PEER_PENDING"), ea)
        partial_acc = P.laptop_acceptance(w.workdir, w.ra, sa, "replica-b-1", "store-b-0")
        self.assertEqual(partial_acc.state, OA.ACCEPTANCE_PARTIAL)
        self.assertTrue(P.laptop_freshness(w.workdir, w.ra, "replica-b-1").current)      # freshness unaffected
        self.assertEqual(q.observe_envelope_a(freshness=current, acceptance=partial_acc).state, P.PC4AP)
        self.assertTrue(boot.advance("APPEND_ENVELOPE_1_COPY_A", {
            **dict.fromkeys(S.BY_ACTION["APPEND_ENVELOPE_1_COPY_A"].evidence, True), "freshness": current}).advanced)

        # ---- C4B (S25): gate, fresh read-only proof, eligibility, go
        t3 = P.build_transfer(w.workdir, "store-a", {"storeA": str(sa), "package": str(package)}, w.dir / "t3.tar",
                              pins=w.pins)
        self.assertEqual(w.gate("C4B")["result"], "PKGC_GATE_PASS")
        q.gate("C4B", continuity_exact=True)
        paths4b = {"replicaA": str(w.ra), "storeA": str(sa)}
        with self.assertRaises(P.Stop) as caught:
            P.c4b_eligibility(w.workdir, paths4b, pins=w.pins)                            # no fresh B read yet
        self.assertTrue(caught.exception.reason.startswith("S25_TRANSCRIPTION_ABSENT"))
        self.assertFalse(os.path.exists(w.phone / "store-b"))
        self.assertTrue(w.s25("C4B_PRE", paths4b)["exact"])                               # copy B absent
        eligible = P.c4b_eligibility(w.workdir, paths4b, pins=w.pins)
        self.assertEqual((eligible["acceptance"], eligible["freshness"]),
                         (OA.ACCEPTANCE_PARTIAL, f"{OF.AUTHENTIC}:{OF.CURRENT}"))
        self.assertTrue(q.c4b_eligibility(freshness=current, acceptance=partial_acc, copy_a_exact=True,
                                          copy_b_absent=True).advanced)
        values4b = P.derive_values(w.workdir, "C4B", paths4b, pins=w.pins)
        self.assertEqual((values4b["envelope"], values4b["store_view"]), (env["envelopeDigest"], t3["treeSha256"]))
        P.arm(w.workdir, "C4B", go("C4B", {**values4b, "binding": binding_sha,
                                           "gate": P.last_gate(w.workdir, "C4B")[1]}), paths4b, pins=w.pins)
        q.arm("C4B", go_exact=True, freshness=current)
        top = tar_extract((w.dir / "t3.tar").read_bytes(), w.phone / "lilith-pkgc" / "views" / "s")
        s_view, phone_pkg = top / "store-a", top / "package.json"
        sb = w.phone / "store-b"
        self.assertEqual(w.tool("init-acceptance-store", "--store", str(sb), "--custody-copy-id", B_ID,
                                "--environment", ENV, "--profile", PROFILE)["code"], 0)
        pe = w.tool("propose-envelope", "--replica", str(w.rb), "--replica", str(a_view), "--store", str(sb),
                    "--store", str(s_view), "--package", str(phone_pkg), "--out", str(w.phone / "env.json"))
        self.assertEqual(pe["envelopeDigest"], env["envelopeDigest"])
        eb = w.tool("append-envelope", "--replica", str(w.rb), "--replica", str(a_view), *w.world(), "--pin",
                    w.pin(), "--store", str(sb), "--peer-store", str(s_view), "--candidate",
                    str(w.phone / "env.json"), "--confirm-digest", env["envelopeDigest"])
        self.assertEqual((eb["code"], eb["replication"]), (0, "COPIES_IDENTICAL"), eb)
        name = os.listdir(sa / T.ENVELOPES)[0]
        self.assertEqual((sa / T.ENVELOPES / name).read_bytes(), (sb / T.ENVELOPES / name).read_bytes())
        self.assertTrue(w.s25("C4B", paths4b)["exact"])
        P.peer_view(w.workdir, "store-b-1", sa, pins=w.pins)
        self.assertEqual(P.tree_digest(P.load_view(w.workdir, "store-b-1")), P.tree_digest(sb))   # = real B
        complete = P.laptop_acceptance(w.workdir, w.ra, sa, "replica-b-1", "store-b-1")
        self.assertEqual(complete.state, OA.ACCEPTANCE_COMPLETE)
        self.assertEqual(q.observe_envelope_b(transcription_exact=True, freshness=current, acceptance=complete).state,
                         P.PC4B)
        self.assertTrue(boot.advance("APPEND_ENVELOPE_1_COPY_B", {
            **dict.fromkeys(S.BY_ACTION["APPEND_ENVELOPE_1_COPY_B"].evidence, True), "freshness": current,
            "acceptance": complete}).advanced)

        # ---- C5
        self.assertEqual(w.gate("C5")["result"], "PKGC_GATE_PASS")
        q.gate("C5", continuity_exact=True)
        values5 = P.derive_values(w.workdir, "C5", paths4b, pins=w.pins)
        out = P.record_act(w.workdir, "C5", go("C5", {**values5, "binding": binding_sha}), paths4b, pins=w.pins)
        self.assertEqual(out["authorityBoundary"], P.AUTHORITY_BOUNDARY)
        self.assertEqual(q.accept(c5_exact=True, freshness=current, acceptance=complete).state, P.PC5)
        self.assertEqual(boot.state, "OWNER_ACCEPTANCE_EVIDENCED")
        self.assertNotIn("WRITE_HELD", boot.history)
        self.assertFalse(S.authority_changing_permitted(boot.state, current))
        self.assertEqual(S.first_memory_gate(boot.state, freshness=current, a1_a7_accepted=True,
                                             owner_accepted_proofs=True),
                         (S.FIRST_MEMORY_BLOCKED, "FULL_READINESS_REQUIRED"))
        self.assertEqual(sorted(os.listdir(w.workdir / P.ATTEMPT_DIR)), ["C2.json", "C3.json", "C4A.json", "C4B.json"])

    def test_copy_b_present_is_never_eligible(self):
        expected = P.s25_expect("C4B_PRE", record_digest="1" * 64, bundle_sha256="2" * 64, a_view="3" * 64)
        self.assertEqual(expected[-1], "ACCEPTANCE_STORE_B=ABSENT")
        present = [ln.replace("ACCEPTANCE_STORE_B=ABSENT", "ACCEPTANCE_STORE_B=PRESENT") for ln in expected]
        self.assertFalse(P.s25_check(expected, lines_with_hash(present).decode())["exact"])

    def test_an_envelope_never_makes_freshness_current(self):
        w = World(self)
        w.ready()
        P.peer_view(w.workdir, "replica-b-0", pins=w.pins)
        vb0 = P.load_view(w.workdir, "replica-b-0")
        cand = w.workdir / "cand.json"
        proposed = w.tool("propose-genesis", *w.world(), "--pin", w.pin(), "--out", str(cand))
        w.tool("append", "--replica", str(w.ra), "--peer", str(vb0), "--candidate", str(cand), *w.world(),
               "--pin", w.pin(), "--confirm-digest", proposed["recordDigest"])
        sa = w.laptop / "store-a"
        T.init_acceptance_store(sa, custody_copy_id=A_ID, environment=ENV, authority_profile=PROFILE)
        (sa / T.ENVELOPES / f"000001-{'a' * 64}.json").write_bytes(OF.record_bytes({"envelope": {}, "package": {}}))
        self.assertEqual(P.laptop_freshness(w.workdir, w.ra, "replica-b-0").freshness, OF.FRESHNESS_UNKNOWN)
        self.assertNotEqual(P.laptop_acceptance(w.workdir, w.ra, sa, "replica-b-0", "store-b-0").state,
                            OA.ACCEPTANCE_COMPLETE)
        self.assertEqual(S.BootstrapSequencerV1(state="OWNER_RECORD_PARTIAL").advance(
            "APPEND_ENVELOPE_1_COPY_A", {}).reason, "TRANSITION_OUT_OF_ORDER")

    def test_a_wrong_peer_is_refused_and_writes_nothing(self):
        w = World(self)
        w.ready()
        cand = w.workdir / "cand.json"
        proposed = w.tool("propose-genesis", *w.world(), "--pin", w.pin(), "--out", str(cand))
        bad = w.dir / "bad-peer"
        T.init_replica(bad, replica_id=B_ID, environment=ENV, authority_profile=PROFILE)
        (bad / T.RECORDS / f"000002-{'b' * 64}.json").write_bytes(b"{}")
        r = w.tool("append", "--replica", str(w.ra), "--peer", str(bad), "--candidate", str(cand), *w.world(),
                   "--pin", w.pin(), "--confirm-digest", proposed["recordDigest"])
        self.assertEqual(r["code"], T.EXIT_REFUSED)
        self.assertEqual(os.listdir(w.ra / T.RECORDS), [])


# ---------------------------------------------------- S25 + transcription ---

class S25Tests(unittest.TestCase):
    def test_transcription_must_be_exact_ordered_and_hashed(self):
        lines = P.s25_expect("C3", record_digest="1" * 64, bundle_sha256="2" * 64, a_view="3" * 64)
        good = lines_with_hash(lines).decode()
        self.assertTrue(P.s25_check(lines, good)["exact"])
        self.assertEqual(P.s25_check(lines, good)["evidenceClass"], "OWNER_SCREEN_TRANSCRIPTION")
        for mutated in ("\n".join(lines),
                        good.replace("FRESHNESS=AUTHENTIC:CURRENT", "FRESHNESS=AUTHENTIC:FRESHNESS_UNKNOWN"),
                        "\n".join([lines[1], lines[0], *lines[2:], "RESULT_BLOCK_SHA256=" + P.result_block_sha256(lines)]),
                        good + "\nEXTRA=1",
                        good.replace(good.splitlines()[-1], "RESULT_BLOCK_SHA256=" + "0" * 64)):
            self.assertFalse(P.s25_check(lines, mutated)["exact"])
        with self.assertRaises(P.Stop):
            P.s25_expect("C3", bundle_sha256="2" * 64, a_view="3" * 64)
        with self.assertRaises(P.Stop):
            P.s25_expect("C4", record_digest="1" * 64, bundle_sha256="2" * 64, a_view="3" * 64)

    def test_expected_lines_per_stage(self):
        c1 = P.s25_expect("C1", bundle_sha256="2" * 64)
        self.assertIn("REPLICA_B_RECORDS=0", c1)
        self.assertFalse(any(line.startswith("FRESHNESS=") for line in c1))
        pre = P.s25_expect("C4B_PRE", record_digest="1" * 64, bundle_sha256="2" * 64, a_view="3" * 64)
        self.assertEqual(pre[-2:], ["FRESHNESS=AUTHENTIC:CURRENT", "ACCEPTANCE_STORE_B=ABSENT"])
        self.assertFalse(any(line.startswith(("APPEND", "STORE_B=")) for line in pre))   # read-only
        c4b = P.s25_expect("C4B", record_digest="1" * 64, envelope_digest="4" * 64, bundle_sha256="2" * 64,
                           a_view="3" * 64, store_view="5" * 64)
        self.assertIn("ACCEPTANCE=ACCEPTANCE_COMPLETE", c4b)
        self.assertIn("REPLICATION=COPIES_IDENTICAL", c4b)

    def test_phone_script_emits_every_expected_key(self):
        text = PHONE.read_text(encoding="utf-8")
        emitted = set(re.findall(r'"([A-Z0-9_]+)=', text)) | {"BUNDLE_VERIFIED"}
        keys = {line.split("=")[0] for st in P.S25_STAGES for line in P.s25_expect(
            st, record_digest="1" * 64, envelope_digest="4" * 64, bundle_sha256="2" * 64, a_view="3" * 64,
            store_view="5" * 64)}
        self.assertTrue(keys <= emitted, keys - emitted)
        for stage in P.S25_STAGES:
            self.assertIn(f"pkgc_finish {stage}\n", text)

    def test_phone_script_boundary(self):
        text = PHONE.read_text(encoding="utf-8")
        code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        for forbidden in ("ssh", "adb", "curl", "wget", "pip ", "pkg install", "gcloud", "rm -", "rm \"", "systemctl",
                          "termux-setup-storage", "git "):
            self.assertNotIn(forbidden, code, forbidden)
        writes = re.findall(r"\bT (append-envelope|append|init-acceptance-store|init-real-replica|init-replica)\b", code)
        self.assertEqual(writes, ["append", "init-acceptance-store", "append-envelope"])
        self.assertEqual(code.count("set -C"), 2)
        c3 = code[code.index("pkgc_c3() {"):code.index("pkgc_c4b_pre() {")]
        self.assertLess(c3.index('"$PKGC_RECORD_DIGEST" ]'), c3.index("set -C"))
        self.assertLess(c3.index("set -C"), c3.index("T append"))
        pre = code[code.index("pkgc_c4b_pre() {"):code.index("pkgc_c4b() {")]
        self.assertNotRegex(pre, r"\bT (append|init|propose)")                              # C4B_PRE is read-only
        self.assertNotIn("set -C", pre)
        c4b = code[code.index("pkgc_c4b() {"):]
        self.assertLess(c4b.index("AUTHENTIC:CURRENT"), c4b.index("set -C"))
        self.assertLess(c4b.index("store B already exists"), c4b.index("set -C"))
        self.assertLess(c4b.index("set -C"), c4b.index("T init-acceptance-store"))
        self.assertIn("attempt-C4B", c4b)
        c1 = code[code.index("pkgc_c1() {"):code.index("pkgc_c3() {")]
        self.assertNotRegex(c1, r"\bT (append|init|propose)")
        self.assertIn('PKGC_RB="$HOME/lilith-owner-offline-dev-synthetic-01"', code)
        self.assertNotIn("lilith-owner-freshness/owner-offline", code)
        self.assertIn('"$PKGC_W/views/', code)                                              # views only in staging

    def test_s25_closure_is_the_import_closure_of_the_canonical_tool(self):
        roots = {"lilith_owner_memory": ROOT / "services/owner-memory-control",
                 "lilith_memory": ROOT / "services/core-api"}

        def path(module: str) -> Path:
            base = roots[module.split(".")[0]].joinpath(*module.split("."))
            return base.with_suffix(".py") if base.with_suffix(".py").exists() else base / "__init__.py"

        seen, todo = set(), ["lilith_owner_memory.owner_freshness_tool"]
        while todo:
            module = todo.pop()
            if module in seen:
                continue
            seen.update((module, module.split(".")[0]))
            for node in ast.walk(ast.parse(path(module).read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom) and node.level:
                    base = ".".join(module.split(".")[:len(module.split(".")) - node.level])
                    todo += ([f"{base}.{node.module}"] if node.module else [f"{base}.{a.name}" for a in node.names])
                elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in roots:
                    todo.append(node.module)
        closure = sorted(path(m).relative_to(ROOT).as_posix() for m in seen if path(m).exists())
        self.assertEqual(closure, sorted(P.S25_CLOSURE))

    def test_bundle_tar_is_deterministic(self):
        members = {"b/x.json": b"{}", "a.txt": b"a"}
        first = P.bundle_tar(members, "lilith-pkgc-x")
        self.assertEqual(first, P.bundle_tar(dict(reversed(members.items())), "lilith-pkgc-x"))
        with tarfile.open(fileobj=io.BytesIO(first)) as tar:
            infos = tar.getmembers()
        self.assertTrue(all(i.mtime == 0 and i.uid == 0 and i.gid == 0 for i in infos))


# ---------------------------------------------------------- source / docs ---

class BoundaryTests(unittest.TestCase):
    def test_operator_writes_no_owner_record_and_has_no_authority_form(self):
        source = OPERATOR.read_text(encoding="utf-8")
        tree = ast.parse(source)
        called = {node.func.attr for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and isinstance(node.func.value, ast.Name) and node.func.value.id == "T"}
        self.assertFalse(called & {"append", "append_envelope", "init_acceptance_store", "init_replica",
                                   "init_real_replica", "_write_record", "_publish", "run", "main", "propose",
                                   "propose_genesis", "propose_envelope", "build_package"}, called)
        code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
        for forbidden in ('["ssh', "gcloud", "systemctl", "plink", "adb", "socket", "urllib", "requests",
                          "WRITE_HELD", "START_SIGNER", "bootstrap 1", "lilith-recovery-witness-owner-dev", '"mb9a"',
                          '"mb9b"', '"removal"', '"restart"'):
            self.assertNotIn(forbidden, code, forbidden)
        main_src = source[source.index("def main("):]
        names = set(re.findall(r'argv\[0\] == "([a-z0-9-]+)"', main_src)) | {"arm", "record"}
        self.assertEqual(names, {"pins", "open", "acquire", "arm", "record", "bind", "gate", "peer-view",
                                 "c4b-eligibility", "s25-expect", "s25-check", "transfer", "s25-bundle"})
        acquire_src = source[source.index("def acquire("):source.index("def verify_acquisition(")]
        self.assertEqual(re.findall(r'\["([a-z-]+)", str\(repo\)', acquire_src), ["host", "chain-export"])

    def test_tool_pins_are_the_merged_bytes(self):
        for path, pin in P.TOOL_PINS.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)

    def test_go_templates_never_authorize_more(self):
        for stage in ("C1", "C2", "C3", "C4A", "C4B", "C5"):
            text = " ".join(P.TEMPLATES[stage])
            for item in ("HELD", "the signer", "First Memory", "PROD"):
                self.assertIn(item, text, (stage, item))
        self.assertIn(P.FREEZE_LINE, P.C1_LINES)
        self.assertIn("no intentional merge, deploy, reboot or witness restart", P.FREEZE_LINE)
        self.assertIn("does not advance the sequence", P.FREEZE_LINE)
        self.assertIn("FRESHNESS_UNKNOWN", " ".join(P.C2_LINES))
        self.assertIn("AUTHENTIC + CURRENT", " ".join(P.C3_LINES))
        self.assertIn("does not authorize APPEND_ENVELOPE_1_COPY_B", " ".join(P.C4A_LINES))
        self.assertIn("exactly ACCEPTANCE_PARTIAL, with copy A exact and copy B absent", " ".join(P.C4B_LINES))
        for stage in ("C4A", "C4B"):
            self.assertIn("does not make freshness current", " ".join(P.TEMPLATES[stage]))
        for stage in ("C3", "C4B"):
            self.assertIn("no SSH and no ADB", " ".join(P.TEMPLATES[stage]))
        for stage in P.ARMABLE:
            self.assertIn("no automatic retry", " ".join(P.TEMPLATES[stage]))
            self.assertIn("exactly one attempt", " ".join(P.TEMPLATES[stage]))
            self.assertIn(P.BOOTSTRAP_STEP[stage], P.TEMPLATES[stage][0])
        self.assertIn("does not authorize any owner-record write", " ".join(P.C1_LINES))
        self.assertIn("REGISTRY_EFFECTIVE remains NO", " ".join(P.C5_LINES))

    def test_accepted_pins_are_the_recorded_package_b_values(self):
        record = (ROOT / "docs/architecture/slice-15b2b-b1b3e-mb9-package-b-completion.md").read_text(encoding="utf-8")
        for value in (P.ACCEPTED_PINS.genesis_digest, P.ACCEPTED_PINS.chain_1_sha256, P.ACCEPTED_PINS.pin_sha256,
                      P.ACCEPTED_PINS.register_sha256, P.ACCEPTED_PINS.pin_record_sha256,
                      P.ACCEPTED_PINS.witness_invocation_id, P.ACCEPTED_PINS.replica_b_manifest_sha256):
            self.assertIn(value, record)
        import mb7_genesis_candidate as C
        self.assertEqual((P.ACCEPTED_PINS.registry_sha256, P.ACCEPTED_PINS.root_anchor_sha256,
                          P.ACCEPTED_PINS.witness_anchor_sha256),
                         (C.ACCEPTED_PINS.registry_sha256, C.ACCEPTED_PINS.root_anchor_sha256,
                          C.ACCEPTED_PINS.witness_anchor_sha256))
        self.assertEqual(P.ACCEPTED_PINS.replica_b_manifest_sha256, sha(P.replica_b_manifest()))

    def test_record_states_the_boundaries_and_templates(self):
        text = RECORD.read_text(encoding="utf-8")
        for line in ("REGISTRY_EFFECTIVE = NO", "AUTHORITY_ACTIVE = NO", "authorityGranted = false",
                     "SIGNER = INACTIVE", "HELD = NOT AUTHORIZED", "FIRST_MEMORY = NOT AUTHORIZED",
                     "PROD = NOT AUTHORIZED", "FIRST_MEMORY_READY = NOT REACHED",
                     "APPEND_RECORD_1_REPLICA_A = NOT AUTHORIZED", "APPEND_RECORD_1_REPLICA_B = NOT AUTHORIZED",
                     "APPEND_ENVELOPE_1_COPY_A = NOT AUTHORIZED", "APPEND_ENVELOPE_1_COPY_B = NOT AUTHORIZED",
                     "FRESHNESS=UNKNOWN", "C1 → C2 → C3 → C4A → C4B → C5", "ACQUISITION_NOT_FRESH",
                     "NON_CUSTODY_PEER_VIEW"):
            self.assertIn(line, text, line)
        for stage in ("C1", "C2", "C3", "C4A", "C4B", "C5", "STOP"):
            for template_line in P.TEMPLATES[stage]:
                rendered = re.sub(r"\{([a-z0-9_]+)\}", r"<\1>", template_line)
                self.assertIn("> " + rendered, text, (stage, template_line[:50]))


if __name__ == "__main__":
    unittest.main()
