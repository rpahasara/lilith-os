"""15B2b-B1b-3e Package C: record 1 (Replica A, Replica B) + acceptance envelope 1 (copies A, B) design (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-pkgc-record1-envelope-package.md.

Everything here is offline. Replicas, acceptance stores, peer views, exports and work directories are temporary
directories; witness chains are real K-WIT-signed TEST chains (TEST_ONLY profile). The real Replica A, the S25,
DEV, the network and every owner key are never touched. No live Package C step is performed.
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


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def jbytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


# ------------------------------------------------------------------ world ---

class World:
    """A synthetic Package C world: owner-held installables, P-A, the committed genesis, a fresh export, the laptop
    (Replica A) and a simulated S25 (Replica B) in separate temporary directories."""

    def __init__(self, test: unittest.TestCase):
        self.test = test
        self.dir = Path(tempfile.mkdtemp(prefix="pkgc-"))
        test.addCleanup(shutil.rmtree, self.dir, True)
        self.scenario = F.Scenario()
        self.genesis_doc = self.scenario.writer.chain[0]
        self.genesis_bytes = WR.document_bytes(self.genesis_doc)
        self.genesis_digest = T.inspect_chain(self._trust_inputs(), self._chain_file(), ENV)["genesisWitnessDigest"]
        # installables
        self.inst = self.dir / "installables"
        self.inst.mkdir()
        self.raw = {
            "anchor": jbytes({"schemaVersion": 1, "witnessKeyId": F.WITNESS_KEY_ID, "environment": ENV,
                              "algorithm": "Ed25519", "publicKey": F.public_b64("witness")}),
            "root": jbytes({"schemaVersion": 1, "rootKeyId": SA.ROOT_KEY_ID, "environment": ENV,
                            "algorithm": "Ed25519", "publicKey": SA.public_b64("root")}),
            "registry": jbytes(F.v3())}
        for key, name in P.INSTALLABLES.items():
            (self.inst / name).write_bytes(self.raw[key])
        # P-A: the pin (exact OwnerGenesisPinV1) and two owner record files
        self.pa = self.dir / "pin-a"
        self.pa.mkdir()
        self.pin_bytes = jbytes({"pinType": WR.GENESIS_PIN_TYPE, "schemaVersion": 1, "environment": ENV,
                                 "genesisWitnessDigest": self.genesis_digest})
        files = {"genesis-pin.json": self.pin_bytes, "authorization-register.json": b'{"register":"synthetic"}',
                 "pin-record.json": b'{"record":"synthetic"}'}
        for name, data in files.items():
            (self.pa / name).write_bytes(data)
        # laptop Replica A and S25 Replica B (both TEST_ONLY, empty)
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
            witness_invocation_id="5136ea7af2544450b9370fa412786c98", witness_main_pid="143946")
        self.workdir = self.laptop / "pkgc-seq1"
        self.facts = {"control": "c" * 40, "lastDeployRunId": "37888892605", "bootId": "boot-1"}
        self.exports = 0

    # the tool's own format, used only to learn the synthetic genesis digest
    def _trust_inputs(self) -> T.TrustInputsV1:
        path = Path(tempfile.mkdtemp(prefix="pkgc-trust-"))
        self.test.addCleanup(shutil.rmtree, path, True)
        (path / "t.json").write_text(json.dumps({
            "trustType": T.TRUST_TYPE, "schemaVersion": 1, "environment": ENV,
            "witnessAnchor": {"schemaVersion": 1, "witnessKeyId": F.WITNESS_KEY_ID, "environment": ENV,
                              "algorithm": "Ed25519", "publicKey": F.public_b64("witness")},
            "registryRoot": {"schemaVersion": 1, "rootKeyId": SA.ROOT_KEY_ID, "environment": ENV,
                             "algorithm": "Ed25519", "publicKey": SA.public_b64("root")},
            "registries": [F.v3()]}), encoding="utf-8")
        return T.load_trust(path / "t.json")

    def _chain_file(self) -> Path:
        path = Path(tempfile.mkdtemp(prefix="pkgc-chain-")) / "c.json"
        self.test.addCleanup(shutil.rmtree, path.parent, True)
        path.write_text(json.dumps([self.genesis_doc]), encoding="utf-8")
        return path

    def report(self, **overrides) -> dict:
        report = {"verifierType": "LILITH_MB9_W9", "phase": P.W9_5, "failures": [],
                  "evidence9b": dict.fromkeys(("genesisCommitted", "committedDigestEqualsPin", "chainIsGenesisOnly",
                                               "pointerEqualsGenesis", "retainedAuthorizationsEmpty",
                                               "committedEqualsCandidate"), True),
                  "committedGenesis": {"digest": self.genesis_digest, "fieldsEqualCandidate": True},
                  "witnessInvocationId": "5136ea7af2544450b9370fa412786c98", "witnessMainPid": "143946",
                  "witnessNRestarts": "0", "holdStoreListing": [],
                  "signerLaterState": {"/run/credentials/lilith-authority-signer.service": False},
                  "registryEffective": False, "authorityActive": False, "authorityGranted": False}
        report.update(overrides)
        return report

    def export(self, *, report: dict | None = None, genesis: bytes | None = None, pointer: bytes | None = None,
               rc: bytes = b"0\n", err: bytes = b"", inside: bool = True) -> Path:
        self.exports += 1
        parent = (self.workdir / P.EXPORTS_DIR) if inside else self.dir
        out = parent / f"export-{self.exports}"
        out.mkdir()
        genesis = self.genesis_bytes if genesis is None else genesis
        (out / "chain-1.json").write_bytes(genesis)
        (out / "witness.json").write_bytes(genesis if pointer is None else pointer)
        (out / "w9verifier.out").write_bytes(json.dumps(report or self.report()).encode())
        (out / "w9verifier.err").write_bytes(err)
        (out / "w9verifier.rc").write_bytes(rc)
        return out

    def c1(self) -> str:
        return "\n".join(line.format(control=self.facts["control"], operator="o" * 64, freshness_tool="f" * 64,
                                     genesis=self.pins.genesis_digest, chain1=self.pins.chain_1_sha256)
                         for line in P.C1_LINES)

    def open(self) -> dict:
        return P.open_sequence(self.workdir, self.c1(), control=self.facts["control"], operator="o" * 64,
                               freshness_tool="f" * 64, facts=self.facts, pins=self.pins)

    def bind(self, export: Path | None = None) -> dict:
        return P.bind(self.workdir, self.inst, self.pa, export or self.export(), self.ra,
                      EVIDENCE["PR2_REVALIDATION"], EVIDENCE["P3_3_INDEPENDENCE"], pins=self.pins)

    def bundle(self) -> str:
        """Stands in for the S25 bundle tar (its builder is tested separately)."""
        raw = P.bundle_tar({"binding/BINDING.json": (self.workdir / P.BINDING_DIR / P.BINDING_FILE).read_bytes()},
                           "lilith-pkgc-test")
        (self.workdir / P.BUNDLE_FILE).write_bytes(json.dumps({"tarSha256": sha(raw)}).encode())
        return sha(raw)

    def gate(self, stage: str, **fact_overrides) -> dict:
        facts = {**self.facts, "workflowQueueEmpty": True, "rebootRequired": "absent",
                 "s25BundleSha256": P.bundle_record(self.workdir).get("tarSha256"), **fact_overrides}
        path = self.dir / f"facts-{stage}-{self.exports}.json"
        path.write_text(json.dumps(facts), encoding="utf-8")
        return P.gate(self.workdir, stage, self.export(), path, pins=self.pins)

    # the canonical tool, as the owner runs it
    def world(self, at: Path) -> list[str]:
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
    lines = (top / "SHA256SUMS").read_text().splitlines()
    for line in lines:
        digest, name = line.split("  ", 1)
        assert sha((top / name).read_bytes()) == digest, name
    return top


# ----------------------------------------------------------- state machine ---

def fresh(state: str) -> OF.FreshnessResultV1:
    return OF.FreshnessResultV1(OF.AUTHENTIC, state, None)


def acceptance(state: str) -> OA.AcceptanceResultV1:
    return OA.AcceptanceResultV1(state)


class StateMachineTests(unittest.TestCase):
    def run_to(self, target: str) -> P.PackageCSequenceV1:
        q = P.PackageCSequenceV1()
        steps = [
            lambda: q.open(c1_exact=True),
            lambda: q.bind(binding_exact=True, s25_c1_exact=True, register_entry="EMPTY"),
            lambda: q.gate("C2", continuity_exact=True), lambda: q.arm("C2", go_exact=True),
            lambda: q.observe_record_a(replica_a_exact_record1=True, replica_b_empty=True,
                                       freshness=fresh(OF.FRESHNESS_UNKNOWN)),
            lambda: q.gate("C3", continuity_exact=True), lambda: q.arm("C3", go_exact=True),
            lambda: q.observe_record_b(transcription_exact=True, replicas_identical=True, freshness=fresh(OF.CURRENT)),
            lambda: q.gate("C4", continuity_exact=True),
            lambda: q.arm("C4", go_exact=True, freshness=fresh(OF.CURRENT)),
            lambda: q.observe_envelope_a(freshness=fresh(OF.CURRENT), acceptance=acceptance(OA.ACCEPTANCE_PARTIAL)),
            lambda: q.observe_envelope_b(transcription_exact=True, freshness=fresh(OF.CURRENT),
                                         acceptance=acceptance(OA.ACCEPTANCE_COMPLETE)),
            lambda: q.gate("C5", continuity_exact=True),
            lambda: q.accept(c5_exact=True, freshness=fresh(OF.CURRENT), acceptance=acceptance(OA.ACCEPTANCE_COMPLETE)),
        ]
        for step in steps:
            if q.state == target:
                break
            result = step()
            self.assertIn(result.status, ("ADVANCED",), result)
        return q

    def test_full_sequence_reaches_pc5_and_no_further(self):
        q = self.run_to("never")
        self.assertEqual(q.state, P.PC5)
        self.assertEqual(q.authority_boundary(), P.AUTHORITY_BOUNDARY)
        self.assertEqual(P.AUTHORITY_BOUNDARY, {"REGISTRY_EFFECTIVE": "NO", "AUTHORITY_ACTIVE": "NO",
                                                "authorityGranted": False, "signer": "INACTIVE",
                                                "HELD": "NOT AUTHORIZED", "FIRST_MEMORY": "NOT AUTHORIZED",
                                                "PROD": "NOT AUTHORIZED"})
        self.assertIn("NONE", q.next_after_completion())
        for name in dir(q):                                  # no HELD / signer / activation / First Memory transition
            self.assertNotRegex(name.lower(), r"held|signer|activat|first_memory|release|registry_effective")
        self.assertEqual(q.gate("C5", continuity_exact=True).reason, "SEQUENCE_ENDED")

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
        self.assertEqual(q.arm("C2", go_exact=True).reason, "TRANSITION_OUT_OF_ORDER")     # one go, one attempt
        q = self.run_to(P.PC2)
        self.assertEqual(q.arm("C3", go_exact=True).reason, "FRESH_GATE_REQUIRED")       # C2's gate never carries over
        self.assertEqual(q.arm("C4", go_exact=True, freshness=fresh(OF.CURRENT)).reason, "TRANSITION_OUT_OF_ORDER")

    def test_replica_a_alone_is_partial_and_unknown_never_current(self):
        q = self.run_to(P.PC2A)
        bad = q.observe_record_a(replica_a_exact_record1=True, replica_b_empty=True, freshness=fresh(OF.CURRENT))
        self.assertEqual((bad.status, bad.state, bad.reason), ("HALTED", P.HALT, "OWNER_RECORD_INCONSISTENT"))
        q = self.run_to(P.PC2A)
        self.assertEqual(q.observe_record_a(replica_a_exact_record1=True, replica_b_empty=True,
                                            freshness=True).state, P.HALT)              # a boolean is never freshness
        q = self.run_to(P.PC2)
        self.assertEqual(S.BY_ACTION["APPEND_RECORD_1_REPLICA_A"].target, P.BOOTSTRAP_STATE[P.PC2])

    def test_current_requires_record_b_and_the_envelope_requires_current(self):
        q = self.run_to(P.PC3A)
        for freshness in (fresh(OF.FRESHNESS_UNKNOWN), None, True):
            q2 = copy.deepcopy(q)
            self.assertEqual(q2.observe_record_b(transcription_exact=True, replicas_identical=True,
                                                 freshness=freshness).state, P.HALT)
        q2 = copy.deepcopy(q)
        r = q2.observe_record_b(transcription_exact=False, replicas_identical=True, freshness=fresh(OF.CURRENT))
        self.assertEqual((r.status, r.state, r.reason), ("REVALIDATE", P.PC3A, "TRANSCRIPTION_MISMATCH"))
        q = self.run_to(P.PC3)
        q.gate("C4", continuity_exact=True)
        self.assertEqual(q.arm("C4", go_exact=True, freshness=fresh(OF.FRESHNESS_UNKNOWN)).reason,
                         "FRESHNESS_NOT_CURRENT")

    def test_envelope_partial_and_complete_are_explicit(self):
        q = self.run_to(P.PC4A)
        for state in (OA.ACCEPTANCE_COMPLETE, OA.ACCEPTANCE_NOT_PRESENT, OA.ACCEPTANCE_UNKNOWN):
            q2 = copy.deepcopy(q)
            self.assertEqual(q2.observe_envelope_a(freshness=fresh(OF.CURRENT), acceptance=acceptance(state)).state,
                             P.HALT, state)
        q = self.run_to(P.PC4P)
        self.assertEqual(P.BOOTSTRAP_STATE[P.PC4P], "OWNER_ACCEPTANCE_EVIDENCE_PARTIAL")
        q2 = copy.deepcopy(q)
        self.assertEqual(q2.observe_envelope_b(transcription_exact=True, freshness=fresh(OF.CURRENT),
                                               acceptance=acceptance(OA.ACCEPTANCE_PARTIAL)).state, P.HALT)
        self.assertEqual(q.accept(c5_exact=True, freshness=fresh(OF.CURRENT),
                                  acceptance=acceptance(OA.ACCEPTANCE_COMPLETE)).reason, "TRANSITION_OUT_OF_ORDER")
        q = self.run_to(P.PC4)
        self.assertEqual(q.accept(c5_exact=True, freshness=fresh(OF.CURRENT),
                                  acceptance=acceptance(OA.ACCEPTANCE_COMPLETE)).reason, "FRESH_GATE_REQUIRED")

    def test_invalidators_revalidate_or_halt_and_unknown_never_passes(self):
        for event in sorted(P.REVALIDATE_EVENTS):
            q = self.run_to(P.PC2)
            r = q.invalidate(event)
            self.assertEqual((r.status, r.state), ("REVALIDATE", P.PC2), event)
            self.assertEqual(q.arm("C3", go_exact=True).reason, "FRESH_GATE_REQUIRED", event)
        for event in sorted(P.HALT_EVENTS):
            q = self.run_to(P.PC2)
            self.assertEqual(q.invalidate(event).state, P.HALT, event)
            self.assertEqual(q.gate("C3", continuity_exact=True).reason, "SEQUENCE_ENDED")
            self.assertEqual(q.reset().reason, "OWNER_RECORD_PONR_PASSED")
        q = self.run_to(P.PC3)
        self.assertEqual(q.invalidate("SOMETHING_NEW").reason, "EVIDENCE_UNKNOWN")      # UNKNOWN => revalidate

    def test_points_of_no_return_and_stop(self):
        q = self.run_to(P.PC1B)
        self.assertTrue(q.stop().advanced)
        q = self.run_to(P.PC1B)
        self.assertTrue(q.reset().advanced)                                              # nothing owner-held yet
        q = self.run_to(P.PC2A)
        self.assertEqual(q.stop().reason, "STOP_REFUSED_ATTEMPT_MARKER_PRESENT")
        self.assertEqual(q.reset().reason, "OWNER_RECORD_PONR_PASSED")                  # armed = consumed
        for state in (P.PC2, P.PC3, P.PC4P, P.PC4, P.PC5):
            self.assertIn(state, P.PONR_STATES)

    def test_resume_only_at_canonical_recoverable_points(self):
        for entry, state in P.RESUMABLE.items():
            q = P.PackageCSequenceV1()
            q.open(c1_exact=True)
            self.assertEqual(q.bind(binding_exact=True, s25_c1_exact=True, register_entry=entry).state, state)
            self.assertTrue(q.revalidate)
        q = P.PackageCSequenceV1()
        q.open(c1_exact=True)
        self.assertEqual(q.bind(binding_exact=True, s25_c1_exact=True, register_entry="B_ONLY").state, P.HALT)
        self.assertEqual(set(P.RESUMABLE), {"EMPTY", "A_ONLY", "AB_NO_ENVELOPE", "ENVELOPE_A_ONLY"})

    def test_pc_states_map_onto_the_accepted_bootstrap_steps(self):
        steps = [s.target for s in S.STEPS]
        order = [steps.index(P.BOOTSTRAP_STATE[s]) for s in (P.PC2, P.PC3, P.PC4P, P.PC4)]
        self.assertEqual(order, sorted(order))
        self.assertEqual([S.STEPS[i].action for i in order], ["APPEND_RECORD_1_REPLICA_A", "APPEND_RECORD_1_REPLICA_B",
                                                              "APPEND_ENVELOPE_1_COPY_A", "APPEND_ENVELOPE_1_COPY_B"])
        self.assertEqual(S.STEPS[order[-1] + 1].action, "WRITE_HELD")                 # the next step is NOT Package C


# ----------------------------------------------------------------- binding ---

class BindingTests(unittest.TestCase):
    def setUp(self):
        self.w = World(self)
        self.w.open()

    def test_binding_is_exact_deterministic_and_the_tool_reads_it_authentic(self):
        result = self.w.bind()
        self.assertEqual(result["result"], "PKGC_BINDING_EXACT")
        binding, _ = P.load_binding(self.w.workdir)
        self.assertEqual(binding["snapshot"]["phase"], P.W9_5)
        self.assertEqual(binding["attachedEvidence"], EVIDENCE)
        self.assertEqual(binding["freshness"], "UNKNOWN")
        trust = T.load_trust(self.w.workdir / P.BINDING_DIR / P.TRUST_FILE)
        inspected = T.inspect_chain(trust, self.w.workdir / P.BINDING_DIR / P.CHAIN_FILE, ENV)
        self.assertEqual((inspected["authenticity"], inspected["entries"], inspected["genesisWitnessDigest"]),
                         (OF.AUTHENTIC, 1, self.w.genesis_digest))
        self.assertEqual((self.w.workdir / P.BINDING_DIR / P.PIN_FILE).read_bytes(), self.w.pin_bytes)
        # a second, independent world and binding over the same accepted bytes is byte-identical
        other = World(self)
        self.assertEqual(other.pins, self.w.pins)
        other.open()
        other.bind()
        for name in (P.TRUST_FILE, P.CHAIN_FILE, P.PIN_FILE):
            self.assertEqual((other.workdir / P.BINDING_DIR / name).read_bytes(),
                             (self.w.workdir / P.BINDING_DIR / name).read_bytes(), name)

    def test_no_stale_or_foreign_export(self):
        with self.assertRaises(P.Stop) as caught:
            self.w.bind(self.w.export(inside=False))                    # e.g. the historical Package B POST9B export
        self.assertEqual(caught.exception.reason, "EXPORT_NOT_IN_SEQUENCE")
        fresh_world = World(self)
        with self.assertRaises(P.Stop) as caught:
            fresh_world.bind(self.w.export())                            # no C1, no binding
        self.assertEqual(caught.exception.reason, "SEQUENCE_NOT_OPENED")

    def test_export_must_be_exact(self):
        cases = {
            "w9PhaseExact": dict(report=self.w.report(phase="W9_LATER_STATE")),
            "w9NoFailures": dict(report=self.w.report(failures=["X"])),
            "committedDigestIsAccepted": dict(report=self.w.report(committedGenesis={"digest": "0" * 64})),
            "chain1BytesAccepted": dict(genesis=self.w.genesis_bytes + b" "),
            "pointerEqualsGenesis": dict(pointer=b"{}"),
            "incarnationAccepted": dict(report=self.w.report(witnessMainPid="999")),
            "noRestart": dict(report=self.w.report(witnessNRestarts=None)),               # UNKNOWN is not 0
            "holdStoreEmpty": dict(report=self.w.report(holdStoreListing=["held.json"])),
            "signerNoLaterState": dict(report=self.w.report(signerLaterState={"x": True})),
            "registryNotEffective": dict(report=self.w.report(registryEffective=True)),
            "authorityNotActive": dict(report=self.w.report(authorityGranted=True)),
        }
        for check, kwargs in cases.items():
            result = P.check_export(self.w.export(**kwargs), self.w.pins)
            self.assertFalse(result["exact"], check)
            self.assertFalse(result["checks"][check], check)
        for kwargs, reason in ((dict(rc=b"1\n"), "W9_VERIFIER_FAILED"), (dict(err=b"warn"), "W9_VERIFIER_STDERR")):
            with self.assertRaises(P.Stop) as caught:
                P.check_export(self.w.export(**kwargs), self.w.pins)
            self.assertEqual(caught.exception.reason, reason)
        with self.assertRaises(P.Stop) as caught:
            self.w.bind(self.w.export(report=self.w.report(phase="W9_5S_GENESIS_COMMITTED_STOPPED")))
        self.assertTrue(caught.exception.reason.startswith("EXPORT_NOT_EXACT:"))
        self.assertFalse((self.w.workdir / P.BINDING_DIR).exists())                       # nothing written

    def test_owner_held_inputs_must_be_the_accepted_bytes(self):
        for pin_field, reason in (("registry_sha256", "REGISTRY_NOT_ACCEPTED"),
                                  ("witness_anchor_sha256", "WITNESS_ANCHOR_NOT_ACCEPTED"),
                                  ("pin_sha256", "PIN_BYTES_NOT_ACCEPTED")):
            pins = dataclasses.replace(self.w.pins, **{pin_field: "0" * 64})
            with self.assertRaises(P.Stop) as caught:
                P.bind(self.w.workdir, self.w.inst, self.w.pa, self.w.export(), self.w.ra, *EVIDENCE.values(),
                       pins=pins)
            self.assertEqual(caught.exception.reason, reason)
        (self.w.pa / "extra").write_bytes(b"x")
        with self.assertRaises(P.Stop) as caught:
            self.w.bind()
        self.assertEqual(caught.exception.reason, "PIN_DIRECTORY_INEXACT")

    def test_binding_outputs_are_tamper_evident(self):
        self.w.bind()
        path = self.w.workdir / P.BINDING_DIR / P.CHAIN_FILE
        os.chmod(path, 0o600)
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(P.Stop) as caught:
            P.load_binding(self.w.workdir)
        self.assertEqual(caught.exception.reason, "BINDING_OUTPUT_CHANGED:" + P.CHAIN_FILE)
        with self.assertRaises(P.Stop) as caught:
            self.w.bind()
        self.assertEqual(caught.exception.reason, "BINDING_EXISTS")


# -------------------------------------------------------------- continuity ---

class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.w = World(self)
        self.w.open()
        self.w.bind()
        self.w.bundle()

    def test_fresh_gate_passes_and_exports_are_never_reused(self):
        self.assertEqual(self.w.gate("C2")["result"], "PKGC_GATE_PASS")
        binding, _ = P.load_binding(self.w.workdir)
        facts = self.w.dir / "facts.json"
        facts.write_text(json.dumps({**self.w.facts, "workflowQueueEmpty": True, "rebootRequired": "absent",
                                     "s25BundleSha256": P.bundle_record(self.w.workdir)["tarSha256"]}))
        with self.assertRaises(P.Stop) as caught:
            P.gate(self.w.workdir, "C2", self.w.workdir / P.EXPORTS_DIR / binding["inputs"]["exportDirectory"], facts,
                   pins=self.w.pins)
        self.assertEqual(caught.exception.reason, "EXPORT_REUSED")

    def test_each_invalidator(self):
        cases = {
            "DEPLOY_OCCURRED": dict(lastDeployRunId="37999999999"),
            "BOOT_ID_CHANGED": dict(bootId="boot-2"),
            "CONTROL_CHANGED": dict(control="d" * 40),
            "S25_BUNDLE_MISMATCH": dict(s25BundleSha256="e" * 64),
            "WORKFLOW_QUEUE_NOT_EMPTY": dict(workflowQueueEmpty=False),
            "REBOOT_REQUIRED_PRESENT": dict(rebootRequired="present"),
            "EVIDENCE_UNKNOWN": dict(bootId=None),
        }
        for event, overrides in cases.items():
            result = self.w.gate("C2", **overrides)
            self.assertEqual((result["result"], result["events"]), ("PKGC_GATE_REVALIDATE", [event]), event)
        binding, _ = P.load_binding(self.w.workdir)
        opening = json.loads((self.w.workdir / P.C1_FILE).read_text())["facts"]
        facts = {**self.w.facts, "workflowQueueEmpty": True, "rebootRequired": "absent", "s25BundleSha256": "b" * 64}
        reports = {
            "WITNESS_INCARNATION_CHANGED": self.w.report(witnessInvocationId="f" * 32),
            "WITNESS_RESTARTED": self.w.report(witnessNRestarts="1"),
            "CHAIN_ADVANCED": self.w.report(phase="W9_LATER_STATE"),
            "W9_PHASE_NOT_EXACT": self.w.report(phase="W9_5S_GENESIS_COMMITTED_STOPPED"),
            "GENESIS_MISMATCH": self.w.report(committedGenesis={"digest": "0" * 64}),
            "HOLD_STORE_NOT_EMPTY": self.w.report(holdStoreListing=["h"]),
            "SIGNER_ACTIVE": self.w.report(signerLaterState={"s": True}),
            "AUTHORITY_GRANTED": self.w.report(authorityGranted=True),
            "REGISTRY_EFFECTIVE": self.w.report(registryEffective=True),
        }
        for event, report in reports.items():
            exported = P.check_export(self.w.export(report=report), self.w.pins)
            result = P.continuity(binding, exported, facts, opening, "b" * 64)
            self.assertIn(event, result["events"], event)
            self.assertEqual(result["route"], "HALT" if event in P.HALT_EVENTS else "REVALIDATE", event)
        exported = P.check_export(self.w.export(pointer=b"{}"), self.w.pins)
        self.assertEqual(P.continuity(binding, exported, facts, opening, "b" * 64)["route"], "HALT")

    def test_gate_order_and_marker_need_the_last_exact_gate(self):
        self.w.gate("C2", bootId="boot-2")
        with self.assertRaises(P.Stop) as caught:
            P.last_gate(self.w.workdir, "C2")
        self.assertEqual(caught.exception.reason, "FRESH_GATE_REQUIRED")                  # a failed gate is last
        self.w.gate("C2")
        self.assertEqual(P.last_gate(self.w.workdir, "C2")[0]["exact"], True)
        with self.assertRaises(P.Stop):
            P.last_gate(self.w.workdir, "C3")


# ---------------------------------------------------- end-to-end ceremony ---

class CeremonyTests(unittest.TestCase):
    """C1 … C5 with the canonical tool, the laptop and a simulated S25 in separate directories. The operator never
    writes a record; every record / envelope write below is the canonical tool's own `append` / `append-envelope`."""

    def go(self, stage: str, values: dict) -> str:
        return "\n".join(line.format(**values) for line in P.TEMPLATES[stage])

    def phone_lines(self, w: World, stage: str, lines: list[str]) -> str:
        return "\n".join(lines + ["RESULT_BLOCK_SHA256=" + P.result_block_sha256(lines)]) + "\n"

    def test_package_c_end_to_end(self):
        w = World(self)
        q = P.PackageCSequenceV1()
        boot = S.BootstrapSequencerV1(state="WITNESS_GENESIS_COMMITTED")
        # ---- C1: open, export, bind, bundle, S25 read-only gate
        self.assertEqual(w.open()["result"], "PKGC_SEQUENCE_OPENED_READ_ONLY")
        q.open(c1_exact=True)
        w.bind()
        bundle = w.bundle()
        c1_lines = P.s25_expect("C1", bundle_sha256=bundle, pins=w.pins)
        s25 = P.s25_record(w.workdir, "C1", {}, self.phone_lines(w, "C1", c1_lines).encode(), pins=w.pins)
        self.assertTrue(s25["exact"])
        register, _ = T.load_register([w.ra, w.rb])                       # (both empty; stands for A + transcribed B)
        self.assertEqual(S.owner_register_state(register), S.KNOWN_EMPTY)
        self.assertEqual(q.bind(binding_exact=True, s25_c1_exact=True, register_entry="EMPTY").state, P.PC1B)

        # ---- C2 preparation (read-only + candidate files): empty Replica B view, candidate, review package
        views = w.workdir / "views"
        views.mkdir()
        vb0 = views / "replica-b-0"
        P.peer_view("replica-b-0", None, vb0, pins=w.pins)
        cand = w.workdir / "record1-candidate.json"
        proposed = w.tool("propose-genesis", *w.world(w.laptop), "--pin", w.pin(), "--out", str(cand))
        self.assertEqual(proposed["code"], 0, proposed)
        package = w.workdir / "review-package.json"
        built = w.tool("build-review-package", "--replica", str(w.ra), "--replica", str(vb0), *w.world(w.laptop),
                       "--pin", w.pin(), "--candidate", str(cand), "--out", str(package),
                       *[x for k, v in EVIDENCE.items() for x in ("--evidence", f"{k}={v}")])
        self.assertEqual(built["code"], 0, built)
        self.assertEqual(w.gate("C2")["result"], "PKGC_GATE_PASS")
        q.gate("C2", continuity_exact=True)
        paths = {"candidate": str(cand), "package": str(package), "view": str(vb0), "replicaAPath": str(w.ra)}
        values = P.derive_values(w.workdir, "C2", paths, pins=w.pins)
        self.assertEqual(values["record"], proposed["recordDigest"])
        self.assertEqual(values["package"], built["packageDigest"])
        _, binding_sha = P.load_binding(w.workdir)
        _, gate_sha = P.last_gate(w.workdir, "C2")
        wrong = self.go("C2", {**values, "record": "0" * 64, "binding": binding_sha, "gate": gate_sha})
        with self.assertRaises(P.Stop) as caught:
            P.arm(w.workdir, "C2", wrong, paths, pins=w.pins)
        self.assertEqual(caught.exception.reason, "GO_LINE_MISSING")
        go2 = self.go("C2", {**values, "binding": binding_sha, "gate": gate_sha})
        self.assertEqual(P.arm(w.workdir, "C2", go2, paths, pins=w.pins)["result"], "PKGC_ARMED")
        with self.assertRaises(P.Stop) as caught:
            P.arm(w.workdir, "C2", go2, paths, pins=w.pins)
        self.assertEqual(caught.exception.reason, "ATTEMPT_ALREADY_CONSUMED:C2")
        with self.assertRaises(P.Stop) as caught:
            P.record_act(w.workdir, "STOP", "x", {}, pins=w.pins)
        self.assertEqual(caught.exception.reason, "STOP_REFUSED_ATTEMPT_MARKER_PRESENT")
        q.arm("C2", go_exact=True)

        # ---- C2: the owner runs the canonical append once (Replica A, peer = empty B view)
        a = w.tool("append", "--replica", str(w.ra), "--peer", str(vb0), "--candidate", str(cand), *w.world(w.laptop),
                   "--pin", w.pin(), "--confirm-digest", proposed["recordDigest"])
        self.assertEqual((a["code"], a["status"], a["replication"]), (0, "RECORD_APPENDED", "PEER_PENDING"), a)
        self.assertEqual(sorted(os.listdir(vb0 / T.RECORDS)), [])                         # the view is never written
        partial = w.tool("classify", "--replica", str(w.ra), "--replica", str(vb0), *w.world(w.laptop))
        self.assertEqual(partial["freshness"], OF.FRESHNESS_UNKNOWN)
        self.assertEqual(set(partial["gates"].values()), {OF.FRESHNESS_BLOCKED})          # every gate blocked
        # neither the envelope nor anything else can proceed from the partial state
        early = w.tool("propose-envelope", "--replica", str(w.ra), "--replica", str(vb0), "--store", "x", "--store",
                       "y", "--package", str(package), "--out", str(w.workdir / "early.json"))
        self.assertEqual((early["code"], early["reason"]), (T.EXIT_REFUSED, "OWNER_REGISTER_NOT_VERIFIED"))
        register_a, _ = T.load_register([w.ra, vb0])
        freshness_a = OF.classify_presented_world(
            register=register_a, chain=T.verify_chain(T.load_trust(w.workdir / P.BINDING_DIR / P.TRUST_FILE),
                                                      w.workdir / P.BINDING_DIR / P.CHAIN_FILE, ENV),
            environment=ENV, authority_profile=PROFILE)
        self.assertFalse(freshness_a.current)
        self.assertEqual(q.observe_record_a(replica_a_exact_record1=True, replica_b_empty=True,
                                            freshness=freshness_a).state, P.PC2)
        self.assertTrue(boot.advance("APPEND_RECORD_1_REPLICA_A", {
            **dict.fromkeys(S.BY_ACTION["APPEND_RECORD_1_REPLICA_A"].evidence, True), "ownerRegister": register}).advanced)
        self.assertFalse(S.authority_changing_permitted(boot.state, freshness_a))
        self.assertEqual(boot.advance("APPEND_ENVELOPE_1_COPY_A", {}).reason, "TRANSITION_OUT_OF_ORDER")

        # ---- C3: T2 (Replica A view) to the S25; the owner runs the canonical append on Replica B
        t2 = P.build_transfer(w.workdir, "replica-a", {"replicaA": str(w.ra)}, w.dir / "t2.tar", pins=w.pins)
        a_view = tar_extract((w.dir / "t2.tar").read_bytes(), w.phone / "views-a") / "replica-a"
        self.assertEqual(P.tree_digest(a_view), t2["treeSha256"])
        self.assertEqual(w.gate("C3")["result"], "PKGC_GATE_PASS")
        q.gate("C3", continuity_exact=True)
        paths3 = {"replicaA": str(w.ra), "view": str(a_view), "replicaBPath": str(w.rb)}
        values3 = P.derive_values(w.workdir, "C3", paths3, pins=w.pins)
        _, gate_sha = P.last_gate(w.workdir, "C3")
        P.arm(w.workdir, "C3", self.go("C3", {**values3, "binding": binding_sha, "gate": gate_sha}), paths3,
              pins=w.pins)
        q.arm("C3", go_exact=True)
        phone_cand = w.phone / "candidate.json"                     # the S25 derives its own candidate
        again = w.tool("propose-genesis", *w.world(w.phone), "--pin", w.pin(), "--out", str(phone_cand))
        self.assertEqual(again["recordDigest"], proposed["recordDigest"])
        b = w.tool("append", "--replica", str(w.rb), "--peer", str(a_view), "--candidate", str(phone_cand),
                   *w.world(w.phone), "--pin", w.pin(), "--confirm-digest", proposed["recordDigest"])
        self.assertEqual((b["code"], b["replication"]), (0, "REPLICAS_IDENTICAL"), b)
        on_phone = w.tool("classify", "--replica", str(w.rb), "--replica", str(a_view), *w.world(w.phone))
        self.assertEqual((on_phone["authenticity"], on_phone["freshness"]), (OF.AUTHENTIC, OF.CURRENT))
        # the transcription, checked on the laptop; then the laptop's hash-equal view of Replica B
        c3_lines = P.s25_expected(w.workdir, "C3", {"replicaA": str(w.ra)}, pins=w.pins)
        self.assertIn(f"REPLICA_B_FILE=000001-{proposed['recordDigest']}.json", c3_lines)
        self.assertTrue(P.s25_record(w.workdir, "C3", {"replicaA": str(w.ra)},
                                     self.phone_lines(w, "C3", c3_lines).encode(), pins=w.pins)["exact"])
        vb1 = views / "replica-b-1"
        P.peer_view("replica-b-1", w.ra, vb1, pins=w.pins)
        self.assertEqual(P.tree_digest(vb1), P.tree_digest(w.rb))                         # = the real Replica B
        register_ab, _ = T.load_register([w.ra, vb1])
        chain = T.verify_chain(T.load_trust(w.workdir / P.BINDING_DIR / P.TRUST_FILE),
                               w.workdir / P.BINDING_DIR / P.CHAIN_FILE, ENV)
        current = OF.classify_presented_world(register=register_ab, chain=chain, environment=ENV,
                                              authority_profile=PROFILE)
        self.assertTrue(current.current)
        self.assertEqual(q.observe_record_b(transcription_exact=True, replicas_identical=True, freshness=current).state,
                         P.PC3)
        self.assertTrue(boot.advance("APPEND_RECORD_1_REPLICA_B", {
            **dict.fromkeys(S.BY_ACTION["APPEND_RECORD_1_REPLICA_B"].evidence, True), "freshness": current}).advanced)
        self.assertEqual(boot.state, "OWNER_FRESHNESS_CURRENT")

        # ---- C4: stores, envelope copy A on the laptop, then copy B on the S25
        sa, sb0 = w.laptop / "store-a", views / "store-b-0"
        self.assertEqual(w.tool("init-acceptance-store", "--store", str(sa), "--custody-copy-id", A_ID,
                                "--environment", ENV, "--profile", PROFILE)["code"], 0)
        P.peer_view("store-b-0", None, sb0, pins=w.pins)
        ecand = w.workdir / "envelope-candidate.json"
        env = w.tool("propose-envelope", "--replica", str(w.ra), "--replica", str(vb1), "--store", str(sa), "--store",
                     str(sb0), "--package", str(package), "--out", str(ecand))
        self.assertEqual(env["code"], 0, env)
        self.assertEqual(w.gate("C4")["result"], "PKGC_GATE_PASS")
        q.gate("C4", continuity_exact=True)
        paths4 = {"replicaA": str(w.ra), "envelopeCandidate": str(ecand), "package": str(package)}
        values4 = P.derive_values(w.workdir, "C4", paths4, pins=w.pins)
        self.assertEqual(values4["envelope"], env["envelopeDigest"])
        _, gate_sha = P.last_gate(w.workdir, "C4")
        P.arm(w.workdir, "C4", self.go("C4", {**values4, "binding": binding_sha, "gate": gate_sha}), paths4,
              pins=w.pins)
        q.arm("C4", go_exact=True, freshness=current)
        ea = w.tool("append-envelope", "--replica", str(w.ra), "--replica", str(vb1), *w.world(w.laptop), "--pin",
                    w.pin(), "--store", str(sa), "--peer-store", str(sb0), "--candidate", str(ecand),
                    "--confirm-digest", env["envelopeDigest"])
        self.assertEqual((ea["code"], ea["replication"]), (0, "PEER_PENDING"), ea)
        partial_acc = w.tool("classify-acceptance", "--replica", str(w.ra), "--replica", str(vb1), "--store", str(sa),
                             "--store", str(sb0), "--pin", w.pin())
        self.assertEqual(partial_acc["state"], OA.ACCEPTANCE_PARTIAL)
        still = w.tool("classify", "--replica", str(w.ra), "--replica", str(vb1), *w.world(w.laptop))
        self.assertEqual(still["freshness"], OF.CURRENT)                                   # freshness unaffected
        self.assertEqual(q.observe_envelope_a(freshness=current, acceptance=OA.AcceptanceResultV1(
            OA.ACCEPTANCE_PARTIAL)).state, P.PC4P)
        self.assertTrue(boot.advance("APPEND_ENVELOPE_1_COPY_A", {
            **dict.fromkeys(S.BY_ACTION["APPEND_ENVELOPE_1_COPY_A"].evidence, True), "freshness": current}).advanced)
        # T3: store A view + package to the S25; store B init; the S25 derives the same envelope and appends it
        t3 = P.build_transfer(w.workdir, "store-a", {"storeA": str(sa), "package": str(package)}, w.dir / "t3.tar",
                              pins=w.pins)
        top = tar_extract((w.dir / "t3.tar").read_bytes(), w.phone / "views-s")
        s_view, phone_pkg = top / "store-a", top / "package.json"
        self.assertEqual(P.tree_digest(s_view), t3["treeSha256"])
        sb = w.phone / "store-b"
        self.assertEqual(w.tool("init-acceptance-store", "--store", str(sb), "--custody-copy-id", B_ID,
                                "--environment", ENV, "--profile", PROFILE)["code"], 0)
        pe = w.tool("propose-envelope", "--replica", str(w.rb), "--replica", str(a_view), "--store", str(sb),
                    "--store", str(s_view), "--package", str(phone_pkg), "--out", str(w.phone / "env.json"))
        self.assertEqual(pe["envelopeDigest"], env["envelopeDigest"])
        eb = w.tool("append-envelope", "--replica", str(w.rb), "--replica", str(a_view), *w.world(w.phone), "--pin",
                    w.pin(), "--store", str(sb), "--peer-store", str(s_view), "--candidate", str(w.phone / "env.json"),
                    "--confirm-digest", env["envelopeDigest"])
        self.assertEqual((eb["code"], eb["replication"]), (0, "COPIES_IDENTICAL"), eb)
        self.assertEqual(sorted(os.listdir(sa / T.ENVELOPES)), sorted(os.listdir(sb / T.ENVELOPES)))
        name = os.listdir(sa / T.ENVELOPES)[0]
        self.assertEqual((sa / T.ENVELOPES / name).read_bytes(), (sb / T.ENVELOPES / name).read_bytes())  # identical
        complete_phone = w.tool("classify-acceptance", "--replica", str(w.rb), "--replica", str(a_view), "--store",
                                str(sb), "--store", str(s_view), "--pin", w.pin())
        self.assertEqual(complete_phone["state"], OA.ACCEPTANCE_COMPLETE)
        c4_lines = P.s25_expected(w.workdir, "C4", {"replicaA": str(w.ra), "storeA": str(sa)}, pins=w.pins)
        self.assertIn(f"STORE_B_MANIFEST_SHA256={sha((sb / T.ACCEPTANCE_MANIFEST).read_bytes())}", c4_lines)
        self.assertTrue(P.s25_record(w.workdir, "C4", {"replicaA": str(w.ra), "storeA": str(sa)},
                                     self.phone_lines(w, "C4", c4_lines).encode(), pins=w.pins)["exact"])
        sb1 = views / "store-b-1"
        P.peer_view("store-b-1", sa, sb1, pins=w.pins)
        self.assertEqual(P.tree_digest(sb1), P.tree_digest(sb))                           # = the real store B
        complete = OA.classify_acceptance(
            register=register_ab, copies=[list(T.load_acceptance_store(sa).bundles),
                                          list(T.load_acceptance_store(sb1).bundles)],
            replica_ids=[A_ID, B_ID], pin=json.loads(w.pin_bytes))
        self.assertEqual(complete.state, OA.ACCEPTANCE_COMPLETE)
        self.assertEqual(q.observe_envelope_b(transcription_exact=True, freshness=current, acceptance=complete).state,
                         P.PC4)
        self.assertTrue(boot.advance("APPEND_ENVELOPE_1_COPY_B", {
            **dict.fromkeys(S.BY_ACTION["APPEND_ENVELOPE_1_COPY_B"].evidence, True), "freshness": current,
            "acceptance": complete}).advanced)

        # ---- C5: Package C acceptance; the boundary holds
        self.assertEqual(w.gate("C5")["result"], "PKGC_GATE_PASS")
        q.gate("C5", continuity_exact=True)
        values5 = P.derive_values(w.workdir, "C5", {"replicaA": str(w.ra), "storeA": str(sa)}, pins=w.pins)
        self.assertEqual(values5["envelope"], env["envelopeDigest"])
        statement = self.go("C5", {**values5, "binding": binding_sha})
        out = P.record_act(w.workdir, "C5", statement, {"replicaA": str(w.ra), "storeA": str(sa)}, pins=w.pins)
        self.assertEqual(out["authorityBoundary"], P.AUTHORITY_BOUNDARY)
        self.assertEqual(q.accept(c5_exact=True, freshness=current, acceptance=complete).state, P.PC5)
        self.assertEqual(boot.state, "OWNER_ACCEPTANCE_EVIDENCED")                         # HELD is NOT performed
        self.assertFalse(S.authority_changing_permitted(boot.state, current))
        self.assertEqual(S.first_memory_gate(boot.state, freshness=current, a1_a7_accepted=True,
                                             owner_accepted_proofs=True), (S.FIRST_MEMORY_BLOCKED,
                                                                           "FULL_READINESS_REQUIRED"))
        self.assertNotIn("WRITE_HELD", boot.history)
        self.assertFalse(any(name.startswith(("HELD", "SIGNER")) for name in os.listdir(w.workdir)))

    def test_an_envelope_never_makes_freshness_current(self):
        """Out-of-band envelope bytes while only Replica A holds record 1: freshness stays UNKNOWN."""
        w = World(self)
        w.open()
        w.bind()
        vb0 = w.workdir / "vb0"
        P.peer_view("replica-b-0", None, vb0, pins=w.pins)
        cand = w.workdir / "cand.json"
        proposed = w.tool("propose-genesis", *w.world(w.laptop), "--pin", w.pin(), "--out", str(cand))
        w.tool("append", "--replica", str(w.ra), "--peer", str(vb0), "--candidate", str(cand), *w.world(w.laptop),
               "--pin", w.pin(), "--confirm-digest", proposed["recordDigest"])
        sa = w.laptop / "store-a"
        T.init_acceptance_store(sa, custody_copy_id=A_ID, environment=ENV, authority_profile=PROFILE)
        fake = {"envelope": {"envelopeType": "x"}, "package": {}}
        (sa / T.ENVELOPES / f"000001-{'a' * 64}.json").write_bytes(OF.record_bytes(fake))
        result = w.tool("classify", "--replica", str(w.ra), "--replica", str(vb0), *w.world(w.laptop))
        self.assertEqual(result["freshness"], OF.FRESHNESS_UNKNOWN)
        acc = w.tool("classify-acceptance", "--replica", str(w.ra), "--replica", str(vb0), "--store", str(sa),
                     "--store", str(sa), "--pin", w.pin())
        self.assertNotEqual(acc["state"], OA.ACCEPTANCE_COMPLETE)
        boot = S.BootstrapSequencerV1(state="OWNER_RECORD_PARTIAL")
        self.assertEqual(boot.advance("APPEND_ENVELOPE_1_COPY_A", {}).reason, "TRANSITION_OUT_OF_ORDER")

    def test_a_wrong_peer_view_is_refused_and_writes_nothing(self):
        w = World(self)
        w.open()
        w.bind()
        cand = w.workdir / "cand.json"
        proposed = w.tool("propose-genesis", *w.world(w.laptop), "--pin", w.pin(), "--out", str(cand))
        # a "Replica B" view that already holds a record the target does not: neither identical nor target + 1
        odd = w.dir / "odd-replica-a"
        T.init_replica(odd, replica_id=A_ID, environment=ENV, authority_profile=PROFILE)
        vb0 = w.workdir / "vb0"
        P.peer_view("replica-b-0", None, vb0, pins=w.pins)
        w.tool("append", "--replica", str(odd), "--peer", str(vb0), "--candidate", str(cand), *w.world(w.laptop),
               "--pin", w.pin(), "--confirm-digest", proposed["recordDigest"])
        bad_view = w.workdir / "vb1-bad"
        P.peer_view("replica-b-1", odd, bad_view, pins=w.pins)
        os.chmod(bad_view / T.RECORDS, 0o700)
        (bad_view / T.RECORDS / f"000002-{'b' * 64}.json").write_bytes(b"{}")
        r = w.tool("append", "--replica", str(w.ra), "--peer", str(bad_view), "--candidate", str(cand),
                   *w.world(w.laptop), "--pin", w.pin(), "--confirm-digest", proposed["recordDigest"])
        self.assertEqual(r["code"], T.EXIT_REFUSED)
        self.assertEqual(os.listdir(w.ra / T.RECORDS), [])
        with self.assertRaises(P.Stop) as caught:
            P.peer_view("replica-b-1", w.ra, w.workdir / "vb-empty-a", pins=w.pins)         # A has no record 1
        self.assertEqual(caught.exception.reason, "SOURCE_NOT_RECORD_1_ONLY")


# ---------------------------------------------------- S25 + transcription ---

class S25Tests(unittest.TestCase):
    def test_transcription_must_be_exact_ordered_and_hashed(self):
        lines = P.s25_expect("C3", record_digest="1" * 64, bundle_sha256="2" * 64, a_view="3" * 64)
        good = "\n".join(lines + ["RESULT_BLOCK_SHA256=" + P.result_block_sha256(lines)])
        self.assertTrue(P.s25_check(lines, good)["exact"])
        self.assertEqual(P.s25_check(lines, good)["evidenceClass"], "OWNER_SCREEN_TRANSCRIPTION")
        for mutated in ("\n".join(lines),                                                # hash line missing
                        good.replace("FRESHNESS=AUTHENTIC:CURRENT", "FRESHNESS=AUTHENTIC:FRESHNESS_UNKNOWN"),
                        good.replace("REPLICATION=REPLICAS_IDENTICAL", "REPLICATION=PEER_PENDING"),
                        "\n".join([lines[1], lines[0], *lines[2:], "RESULT_BLOCK_SHA256="
                                   + P.result_block_sha256(lines)]),              # reordered
                        good + "\nEXTRA=1",
                        good.replace(good.splitlines()[-1], "RESULT_BLOCK_SHA256=" + "0" * 64)):
            self.assertFalse(P.s25_check(lines, mutated)["exact"])
        with self.assertRaises(P.Stop):
            P.s25_expect("C3", bundle_sha256="2" * 64, a_view="3" * 64)              # unknown record => no expectation
        with self.assertRaises(P.Stop):
            P.s25_expect("C1", bundle_sha256=None)

    def test_expected_lines_state_freshness_per_stage(self):
        c1 = P.s25_expect("C1", bundle_sha256="2" * 64)
        self.assertIn("REPLICA_B_RECORDS=0", c1)
        self.assertFalse(any(line.startswith("FRESHNESS=") for line in c1))
        c3 = P.s25_expect("C3", record_digest="1" * 64, bundle_sha256="2" * 64, a_view="3" * 64)
        self.assertIn("FRESHNESS=AUTHENTIC:CURRENT", c3)
        self.assertIn("ACCEPTANCE_STORE_B=ABSENT", c3)                                     # C3 creates no envelope
        c4 = P.s25_expect("C4", record_digest="1" * 64, envelope_digest="4" * 64, bundle_sha256="2" * 64,
                          a_view="3" * 64, store_view="5" * 64)
        self.assertIn("ACCEPTANCE=ACCEPTANCE_COMPLETE", c4)
        self.assertIn("REPLICATION=COPIES_IDENTICAL", c4)

    def test_phone_script_matches_the_expectation_order(self):
        text = PHONE.read_text(encoding="utf-8")
        emitted = re.findall(r'"([A-Z0-9_]+)=', text) + re.findall(r'"(BUNDLE_VERIFIED)"', text)
        keys = {line.split("=")[0] for st in ("C1", "C3", "C4") for line in P.s25_expect(
            st, record_digest="1" * 64, envelope_digest="4" * 64, bundle_sha256="2" * 64, a_view="3" * 64,
            store_view="5" * 64)}
        self.assertTrue(keys <= set(emitted) | {"BUNDLE_VERIFIED"}, keys - set(emitted))

    def test_phone_script_boundary(self):
        text = PHONE.read_text(encoding="utf-8")
        code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        for forbidden in ("ssh", "adb", "curl", "wget", "pip ", "pkg install", "gcloud", "rm -", "rm \"", "systemctl",
                          "termux-setup-storage", "git "):
            self.assertNotIn(forbidden, code, forbidden)
        writes = re.findall(r"\bT (append-envelope|append|init-acceptance-store|init-real-replica|init-replica)\b", code)
        self.assertEqual(writes, ["append", "init-acceptance-store", "append-envelope"])
        self.assertEqual(code.count("set -C"), 2)                                          # C3, C4-B markers
        c3 = code[code.index("pkgc_c3() {"):code.index("pkgc_c4() {")]
        self.assertLess(c3.index("set -C"), c3.index("T append"))
        self.assertLess(c3.index('"$PKGC_RECORD_DIGEST" ]'), c3.index("set -C"))           # typed digest checked first
        c4 = code[code.index("pkgc_c4() {"):]
        self.assertLess(c4.index("AUTHENTIC:CURRENT"), c4.index("set -C"))                 # CURRENT before any write
        self.assertLess(c4.index("set -C"), c4.index("T init-acceptance-store"))
        c1 = code[code.index("pkgc_c1() {"):code.index("pkgc_c3() {")]
        self.assertNotRegex(c1, r"\bT (append|init|propose)")                               # C1 is read-only
        self.assertIn('"$PKGC_RB"', code)
        self.assertIn('PKGC_RB="$HOME/lilith-owner-offline-dev-synthetic-01"', code)       # canonical, not nested
        self.assertNotIn("lilith-owner-freshness/owner-offline", code)

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
            seen.add(module)
            seen.add(module.split(".")[0])
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
        first, second = P.bundle_tar(members, "lilith-pkgc-x"), P.bundle_tar(dict(reversed(members.items())),
                                                                             "lilith-pkgc-x")
        self.assertEqual(first, second)
        with tarfile.open(fileobj=io.BytesIO(first)) as tar:
            infos = tar.getmembers()
        self.assertTrue(all(i.mtime == 0 and i.uid == 0 and i.gid == 0 for i in infos))
        self.assertIn("lilith-pkgc-x/SHA256SUMS", [i.name for i in infos])


# ---------------------------------------------------------- source / docs ---

class BoundaryTests(unittest.TestCase):
    def test_operator_writes_no_owner_record_and_has_no_authority_form(self):
        tree = ast.parse(OPERATOR.read_text(encoding="utf-8"))
        called = {node.func.attr for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and isinstance(node.func.value, ast.Name) and node.func.value.id == "T"}
        self.assertFalse(called & {"append", "append_envelope", "init_acceptance_store", "init_replica",
                                   "init_real_replica", "_write_record", "_publish", "run", "main", "propose",
                                   "propose_genesis", "propose_envelope", "build_package"}, called)
        source = OPERATOR.read_text(encoding="utf-8")
        code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
        for forbidden in ("subprocess.run([\"ssh", "gcloud", "systemctl", "plink", "adb", "socket", "urllib",
                          "requests", "WRITE_HELD", "START_SIGNER", "bootstrap 1", "lilith-recovery-witness-owner-dev"):
            self.assertNotIn(forbidden, code, forbidden)
        forms = set(re.findall(r'argv\[0\] (?:==|in) \(?"([a-z0-9-]+)"', source)) | set(
            re.findall(r'"([a-z0-9-]+)"\)?:\n', source))
        main_src = source[source.index("def main("):]
        names = set(re.findall(r'argv\[0\] == "([a-z0-9-]+)"', main_src)) | {"arm", "record"}
        self.assertEqual(names, {"pins", "open", "arm", "record", "bind", "gate", "peer-view", "s25-expect",
                                 "s25-check", "transfer", "s25-bundle"})
        self.assertTrue(forms)

    def test_tool_pins_are_the_merged_bytes(self):
        for path, pin in P.TOOL_PINS.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)

    def test_go_templates_never_authorize_more(self):
        for stage in ("C1", "C2", "C3", "C4", "C5"):
            text = " ".join(P.TEMPLATES[stage])
            for item in ("HELD", "the signer", "First Memory", "PROD"):
                self.assertIn(item, text, (stage, item))
        self.assertIn("FRESHNESS_UNKNOWN", " ".join(P.C2_LINES))
        self.assertIn("AUTHENTIC + CURRENT", " ".join(P.C3_LINES))
        self.assertIn("does not make freshness current", " ".join(P.C4_LINES))
        self.assertIn("no SSH and no ADB", " ".join(P.C3_LINES))
        for stage in ("C2", "C3", "C4"):
            self.assertIn("no automatic retry", " ".join(P.TEMPLATES[stage]))
            self.assertIn("exactly one attempt", " ".join(P.TEMPLATES[stage]))
        self.assertIn("does not authorize any owner-record write", " ".join(P.C1_LINES))
        self.assertIn("authorizes nothing further", " ".join(P.C5_LINES))
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

    def test_record_states_the_boundaries(self):
        text = RECORD.read_text(encoding="utf-8")
        for line in ("REGISTRY_EFFECTIVE = NO", "AUTHORITY_ACTIVE = NO", "authorityGranted = false",
                     "SIGNER = INACTIVE", "HELD = NOT AUTHORIZED", "FIRST_MEMORY = NOT AUTHORIZED",
                     "PROD = NOT AUTHORIZED", "FIRST_MEMORY_READY = NOT REACHED",
                     "APPEND_RECORD_1_REPLICA_A = NOT AUTHORIZED", "APPEND_RECORD_1_REPLICA_B = NOT AUTHORIZED",
                     "APPEND_ENVELOPE_1_COPY_A = NOT AUTHORIZED", "APPEND_ENVELOPE_1_COPY_B = NOT AUTHORIZED",
                     "FRESHNESS=UNKNOWN"):
            self.assertIn(line, text, line)
        for stage in ("C1", "C2", "C3", "C4", "C5"):
            for template_line in P.TEMPLATES[stage]:
                self.assertIn("> " + template_line.split("{")[0].strip()[:60], text, (stage, template_line[:40]))


if __name__ == "__main__":
    unittest.main()
