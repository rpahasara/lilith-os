"""15B2b-B1b-3e Package A (M-B7 PREPARE_GENESIS_CANDIDATE + M-B8 PIN_GENESIS) (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-mb7-mb8-genesis-prep-package.md.

Two layers:

- stdlib (every platform): tool pins, the three owner-text templates, the transcript / sequence classifiers and
  their routing, the P1B-8 denial proof on fake probes, the operator's one-attempt and refusal-before-marker
  semantics on a fake transport, the DR-5 phase rule, and the record;
- POSIX + cryptography (the M-B6 synthetic host, under a TEMPORARY root, with throwaway TEST keys): the owner
  candidate against the reviewed `reproduce` form and against the host M-B7 code path (`genesis.candidate`,
  byte-exact stdout), the W8 verifier through the real installer `install-owner-inputs`, every partial
  state, the bounded removal and the re-run it enables.

Nothing touches `/`, DEV, the S25 or any real key. Failure messages redact every 64-hex value.
"""

from __future__ import annotations

import contextlib
import dataclasses
import gzip
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "services/owner-memory-control/tools"
ARCH = ROOT / "docs/architecture"
PACKAGE = ARCH / "slice-15b2b-b1b3e-mb7-mb8-genesis-prep-package.md"
for _p in (ROOT / "services/core-api", ROOT / "services/owner-memory-control", TOOLS,
           ROOT / "services/authority-dev", ROOT / "services/authority-dev/ceremony",
           ROOT / "services/authority-dev/tests", ROOT / "services/recovery-witness", Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

POSIX = os.name == "posix"
HAVE_CRYPTO = all(importlib.util.find_spec(m) is not None for m in ("cryptography", "rfc8785", "fido2"))
UID = os.getuid() if POSIX else 0
GID = os.getgid() if POSIX else 0

import mb6_operator as M6  # noqa: E402
import mb7_genesis_candidate as C  # noqa: E402  (stdlib at import)
import mb7_mb8_operator as O  # noqa: E402
import mb8_owner_input_denial_proof as DP  # noqa: E402
import mb8_owner_input_removal as RM  # noqa: E402
import mb8_owner_input_verifier as W  # noqa: E402

HEAD = "19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630"
REGISTRY_DIGEST = "fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc"
CONTROL = "e6fde13a54384c63016b3591beed18cb1a505e24"
UPDATED_AT = "2026-10-08T00:00:00Z"
NOT_AUTHORIZED = ("M-B7 = NOT AUTHORIZED", "M-B8 = NOT AUTHORIZED", "M-B9a = NOT AUTHORIZED",
                  "M-B9b = NOT AUTHORIZED", "WITNESS_GENESIS = NOT AUTHORIZED", "RECORD_1 = NOT AUTHORIZED",
                  "FIRST_MEMORY = NOT AUTHORIZED", "AUTHORITY_ACTIVATION = NOT AUTHORIZED", "PROD = NOT AUTHORIZED",
                  "REGISTRY_EFFECTIVE = NO", "AUTHORITY_ACTIVE = NO", "FRESHNESS=UNKNOWN")
FORBIDDEN_CLAIMS = ("M-B7 = AUTHORIZED", "M-B8 = AUTHORIZED", "M-B9a = AUTHORIZED", "M-B9b = AUTHORIZED",
                    "REGISTRY_EFFECTIVE = YES", "AUTHORITY_ACTIVE = YES", "FRESHNESS=CURRENT",
                    "MB7_MB8_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_STAGE (PROPOSED",
                    "M-B7 performs zero filesystem writes", "M-B7 writes nothing",
                    "M-B7 = OWNER-ACCEPTED", "M-B8 = OWNER-ACCEPTED", "GENESIS_PINNED = YES")


def _r(text: str) -> str:
    return re.sub(r"[0-9a-f]{64}", "<redacted>", str(text))


class Redacted:
    def _formatMessage(self, msg, standardMsg):
        return _r(super()._formatMessage(msg, standardMsg))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def flat(text: str) -> str:
    return " ".join(text.split())


def synthetic_derivation(updated_at: str = UPDATED_AT, pins: C.CandidatePinsV1 = C.ACCEPTED_PINS) -> dict:
    """The derivation dict from the independent restatement alone (no crypto): enough for `write_emitted`."""
    unsigned = C.expected_unsigned(updated_at, pins)
    digest = C.independent_digest(unsigned)
    pin, register = C.document_bytes(C.pin_document(digest)), C.document_bytes(C.register_document(pins))
    record = C.document_bytes(C.pin_record_document(digest, updated_at, pin, register, pins))
    return {"candidateDigest": digest, "updatedAt": updated_at, "ledgerHead": pins.ledger_head,
            "unsignedGenesis": unsigned, "genesisPinBytes": pin.decode("ascii"),
            "authorizationRegisterBytes": register.decode("ascii"), "pinRecordBytes": record.decode("ascii"),
            "expectedHostStdout": C.host_stdout(digest, unsigned).decode("ascii")}


# ------------------------------------------------------------------------------------------- pins ---

class PinTests(Redacted, unittest.TestCase):
    def test_every_tool_hashes_to_its_pin_and_m6_pins_are_reused_unchanged(self):
        for path, pin in O.TOOL_PINS.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)
        for path in (O.INSTALLER, O.W5_VERIFIER, O.MB6_VERIFIER, O.OBSERVER, O.BROKER, O.DENIAL, O.LEDGER_DENIAL,
                     O.DR5_TARGET):
            self.assertEqual(O.TOOL_PINS[path], M6.TOOL_PINS[path], path)
        self.assertEqual(O.TOOL_PINS[O.MB6_OPERATOR], sha(Path(M6.__file__).read_bytes()))
        self.assertNotIn(O.OPERATOR, O.TOOL_PINS)                       # bound into each owner text at runtime

    def test_accepted_identities_are_the_recorded_ones(self):
        p = C.ACCEPTED_PINS
        self.assertEqual((p.ledger_head, p.registry_digest, p.registry_issued_at), (HEAD, REGISTRY_DIGEST,
                                                                                    "2026-10-06T15:16:21Z"))
        self.assertEqual(O.LEDGER_HEAD, HEAD)
        if not POSIX:
            self.skipTest("the pinned W5 verifier needs os.geteuid at import")
        import mb4_mb5_trust_install_verifier as V5
        a = V5.ACCEPTED_PINS
        self.assertEqual((p.registry_sha256, p.root_anchor_sha256, p.witness_anchor_sha256, p.kwit_key_id,
                          p.kwit_public_key_sha256, p.epoch_random, p.policy_version),
                         (a.registry_sha256, a.root_anchor_sha256, a.witness_anchor_sha256, a.kwit_key_id,
                          a.kwit_public_key_sha256, a.epoch_random, a.policy_version))

    def test_verify_cli_pin_is_the_release_member(self):
        wrapper = (ROOT / "services/authority-dev/bin/lilith-authority-verify-dev").read_bytes()
        self.assertEqual(sha(wrapper), O.VERIFY_CLI_SHA256)
        self.assertIn("'verifyCli':", O.READINESS_PROBE)
        self.assertEqual(O.READINESS_PROBE.count("'ledgerCli':"), 1)


# ------------------------------------------------------------------------------- the candidate (pure) ---

class CandidatePureTests(Redacted, unittest.TestCase):
    def test_unsigned_genesis_is_exactly_the_genesis_shape(self):
        unsigned = C.expected_unsigned(UPDATED_AT)
        self.assertEqual(set(unsigned), {
            "protocol", "schemaVersion", "environment", "witnessVersion", "previousWitnessDigest",
            "currentRecoveryEpoch", "registryVersion", "registryDigest", "policyVersion", "ledgerSequence",
            "ledgerHead", "consumedAuthorizationId", "updatedAt", "witnessKeyId"})
        self.assertEqual((unsigned["witnessVersion"], unsigned["previousWitnessDigest"],
                          unsigned["consumedAuthorizationId"], unsigned["ledgerSequence"], unsigned["ledgerHead"]),
                         (1, None, None, 1, HEAD))
        self.assertEqual(C.independent_digest(unsigned),
                         sha(b"LILITH_RECOVERY_WITNESS_V2\x00" + json.dumps(unsigned, sort_keys=True,
                                                                           separators=(",", ":")).encode()))
        self.assertNotEqual(C.independent_digest(unsigned), C.independent_digest(C.expected_unsigned(
            "2026-10-08T00:00:01Z")))                                  # updatedAt is part of the candidate

    def test_install_bytes_are_the_installer_form(self):
        digest = "a" * 64
        pin = C.document_bytes(C.pin_document(digest))
        self.assertEqual(pin, W.expected_pin_bytes(digest))
        self.assertEqual(C.document_bytes(C.register_document()), W.expected_register_bytes(REGISTRY_DIGEST))
        self.assertFalse(pin.endswith(b"\n"))
        self.assertEqual(json.loads(C.document_bytes(C.register_document())),
                         {"registerType": "LILITH_OWNER_AUTHORIZATION_REGISTER", "schemaVersion": 1,
                          "environment": "dev", "authorizations": [],
                          "headRegistries": [{"registryVersion": 1, "registryDigest": REGISTRY_DIGEST}]})

    def test_updated_at_rules(self):
        now = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)
        C.check_updated_at("2026-10-06T15:16:21Z", now=now)
        for value, reason in (("2026-10-06T15:16:20Z", "UPDATED_AT_BEFORE_REGISTRY_ISSUED_AT"),
                              ("2026-10-08T12:00:01Z", "UPDATED_AT_IN_THE_FUTURE"),
                              ("2026-10-08 00:00:00Z", "UPDATED_AT_INVALID"), ("2026-13-08T00:00:00Z",
                                                                              "UPDATED_AT_INVALID")):
            with self.assertRaises(C.CandidateError) as caught:
                C.check_updated_at(value, now=now)
            self.assertEqual(caught.exception.reason, reason, value)

    def test_emitted_directory_round_trip_and_comparisons(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "genesis"
            derived = synthetic_derivation()
            result = C.write_emitted(derived, out)
            self.assertEqual(result["candidateDigest"], derived["candidateDigest"])
            with self.assertRaises(C.CandidateError):
                C.write_emitted(derived, out)                          # never over an existing directory
            files = C.load_emitted(out)
            self.assertNotIn(b"\r", b"".join(files.values()))
            self.assertEqual(C.compare_host(out, files["expected-host-stdout.txt"])["result"],
                             "MB7_HOST_CANDIDATE_EQUAL")
            other = C.host_stdout("b" * 64, derived["unsignedGenesis"])
            differs = C.compare_host(out, other)
            self.assertEqual((differs["result"], differs["differingFields"]),
                             ("MB7_HOST_CANDIDATE_DIFFERS", ["candidateDigest", "pin"]))
            record = json.loads(files["pin-record.json"])
            self.assertEqual((record["updatedAt"], record["candidateDigest"], record["genesisPinSha256"],
                              record["authorizationRegisterSha256"]),
                             (UPDATED_AT, derived["candidateDigest"], sha(files["genesis-pin.json"]),
                              sha(files["authorization-register.json"])))
            (out / "genesis-pin.json").chmod(0o600)
            (out / "genesis-pin.json").write_bytes(b"{}")
            with self.assertRaises(C.CandidateError) as caught:
                C.load_emitted(out)
            self.assertEqual(caught.exception.reason, "EMITTED_SHA256SUMS_MISMATCH")


    def test_owner_record_is_create_only_and_binds_one_updated_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, pin_dir = Path(tmp) / "genesis", Path(tmp) / "p-a"
            C.write_emitted(synthetic_derivation(), out)
            with self.assertRaises(C.CandidateError) as caught:
                C.check_copy(out, pin_dir)
            self.assertEqual(caught.exception.reason, "OWNER_RECORD_DIRECTORY_ABSENT")
            first = C.record(out, pin_dir)
            self.assertEqual((first["result"], first["written"]), ("OWNER_PIN_RECORDED", list(C.OWNER_RECORD_FILES)))
            self.assertEqual(sorted(p.name for p in pin_dir.iterdir()), sorted(C.OWNER_RECORD_FILES))
            self.assertEqual(C.check_copy(out, pin_dir)["result"], "OWNER_COPY_EQUAL")
            self.assertEqual(C.record(out, pin_dir)["result"], "OWNER_PIN_ALREADY_RECORDED_EQUAL")   # no byte written
            # once recorded, a different MB7_MB8_UPDATED_AT is refused before anything is derived
            with self.assertRaises(C.CandidateError) as caught:
                C.emit(b"", b"", b"", "2026-10-08T00:00:01Z", Path(tmp) / "other", pin_dir=pin_dir)
            self.assertEqual(caught.exception.reason, "UPDATED_AT_ALREADY_PINNED")
            self.assertFalse((Path(tmp) / "other").exists())
            # a different candidate never replaces the record
            other_out = Path(tmp) / "genesis-other"
            C.write_emitted(synthetic_derivation("2026-10-08T00:00:01Z"), other_out)
            with self.assertRaises(C.CandidateError) as caught:
                C.record(other_out, pin_dir)
            self.assertEqual(caught.exception.reason, "OWNER_RECORD_CONFLICT")
            self.assertEqual(C.check_copy(other_out, pin_dir)["result"], "OWNER_COPY_DIFFERS")
            self.assertEqual(C.check_copy(out, pin_dir)["result"], "OWNER_COPY_EQUAL")
            (pin_dir / "notes.txt").write_text("x", encoding="ascii")
            with self.assertRaises(C.CandidateError) as caught:
                C.check_copy(out, pin_dir)
            self.assertEqual(caught.exception.reason, "OWNER_RECORD_DIRECTORY_UNEXPECTED_ENTRY")

    def test_p_a_and_p_b_are_dedicated_and_outside_the_replicas(self):
        self.assertEqual((C.P_A_DIR, C.P_B_DIR), ("/root/lilith-genesis-pin-dev-synthetic",
                                                 "$HOME/lilith-genesis-pin-dev-synthetic"))
        self.assertEqual((O.P_A_DIR, O.P_B_DIR), (C.P_A_DIR, C.P_B_DIR))
        for path in (C.P_A_DIR, C.P_B_DIR):
            name = path.rsplit("/", 1)[1]
            self.assertFalse(name.startswith("lilith-owner"))          # never inside a replica parent listing
            self.assertNotIn("kroot", name)
        self.assertFalse(C.P_A_DIR.startswith("/root/lilith-owner-freshness"))


# ---------------------------------------------------------------------------- classifiers and routing ---

def p1b8_report(result="PASS", failures=()):
    return json.dumps({"stage": "P1B-8", "result": result, "failures": list(failures)}).encode()


class ClassifierTests(Redacted, unittest.TestCase):
    def test_transcript_classes(self):
        cases = ((0, p1b8_report(), b"", W.INSTALL_PASS), (0, p1b8_report(), b"warning\n", W.FAILED_UNCLASSIFIED),
                 (1, p1b8_report("FAIL", ["LISTING:x"]), b"", W.INSTALL_STATUS_FAIL),
                 (2, b"", b"install_authority_dev: REFUSED PRECONDITION_FAILED:LISTING:/etc/x\n", W.INSTALL_REFUSED),
                 (1, b"", b"Traceback (most recent call last):\n  ...\nFileExistsError\n", W.FAILED_UNCLASSIFIED),
                 (96, b"", b"", W.GUARD_STOPPED), (97, b"", b"", W.GUARD_STOPPED), (255, b"", b"", W.TRANSPORT_FAILED),
                 (None, b"", b"", W.TRANSPORT_FAILED),
                 (0, json.dumps({"stage": "P1B-6", "result": "PASS", "failures": []}).encode(), b"",
                  W.FAILED_UNCLASSIFIED))
        for code, out, err, expected in cases:
            self.assertEqual(W.classify_transcript(code, out, err)[0], expected, (code, out[:30], err[:30]))

    def test_sequence_phases(self):
        seq = W.classify_sequence
        self.assertEqual(seq(host_phase=W.W8_0, attempt_consumed=False, transcript=W.NOT_INVOKED,
                             post_verified=False), W.W8_0)
        self.assertEqual(seq(host_phase=W.EXACT, attempt_consumed=False, transcript=W.NOT_INVOKED,
                             post_verified=False), W.UNCLASSIFIED)                # installed outside this sequence
        self.assertEqual(seq(host_phase=W.W8_0, attempt_consumed=True, transcript=W.NOT_INVOKED,
                             post_verified=False), W.UNCLASSIFIED)
        for transcript in (W.INSTALL_REFUSED, W.GUARD_STOPPED, W.TRANSPORT_FAILED, W.FAILED_UNCLASSIFIED):
            self.assertEqual(seq(host_phase=W.W8_0, attempt_consumed=True, transcript=transcript,
                                 post_verified=False), W.S8_R, transcript)
        for phase in W.PARTIAL_PHASES:
            self.assertEqual(seq(host_phase=phase, attempt_consumed=True, transcript=W.FAILED_UNCLASSIFIED,
                                 post_verified=False), phase)
            self.assertEqual(seq(host_phase=phase, attempt_consumed=True, transcript=W.INSTALL_PASS,
                                 post_verified=False), W.UNCLASSIFIED)
        self.assertEqual(seq(host_phase=W.EXACT, attempt_consumed=True, transcript=W.INSTALL_PASS,
                             post_verified=False), W.S8_5)
        self.assertEqual(seq(host_phase=W.EXACT, attempt_consumed=True, transcript=W.INSTALL_PASS,
                             post_verified=True), W.S8_6)
        for transcript in (W.TRANSPORT_FAILED, W.FAILED_UNCLASSIFIED, W.INSTALL_STATUS_FAIL):
            self.assertEqual(seq(host_phase=W.EXACT, attempt_consumed=True, transcript=transcript,
                                 post_verified=False), W.S8_4, transcript)
        for transcript in (W.INSTALL_REFUSED, W.GUARD_STOPPED):
            self.assertEqual(seq(host_phase=W.EXACT, attempt_consumed=True, transcript=transcript,
                                 post_verified=False), W.UNCLASSIFIED)
        for phase in (W.FOREIGN, W.LATER_STATE, W.UNCLASSIFIED):
            self.assertEqual(seq(host_phase=phase, attempt_consumed=True, transcript=W.INSTALL_PASS,
                                 post_verified=False), phase)

    def test_every_sequence_phase_is_routed_and_no_route_is_destructive_by_default(self):
        self.assertEqual(set(W.ROUTING), set(W.SEQUENCE_PHASES))
        labels = {route for route, _ in W.ROUTING.values()}
        self.assertLessEqual(labels, {W.SAFE_RETRY, W.SAFE_REMOVE_AND_RETRY, W.SAFE_ADOPT, W.STOP_OWNER_ADJUDICATION})
        for phase in (W.FOREIGN, W.LATER_STATE, W.UNCLASSIFIED):
            self.assertEqual(W.ROUTING[phase][0], W.STOP_OWNER_ADJUDICATION)
        for phase in W.PARTIAL_PHASES:
            self.assertEqual(W.ROUTING[phase][0], W.SAFE_REMOVE_AND_RETRY)
            self.assertIn("separate authorization", W.ROUTING[phase][1])
        self.assertEqual(O.PARTIAL_PHASES, W.PARTIAL_PHASES)
        self.assertEqual(O.DR5_PHASES, (W.W8_0, W.EXACT))


# ------------------------------------------------------------------------------ P1B-8 denial proof ---

def _st(mode: int, uid=0, gid=0, nlink=1):
    return os.stat_result((mode, 1, 1, nlink, uid, gid, 10, 0, 0, 0))


class DenialProofTests(Redacted, unittest.TestCase):
    def probes(self, *, lstat=None, listdir=None, run=None, unit="inactive", activation=None):
        lines: list[str] = []
        files = {DP.OWNER_INPUT_DIR: _st(stat.S_IFDIR | 0o755), **{p: _st(stat.S_IFREG | 0o644) for p in DP.COPIES}}
        ok = DP.prove("P1B-8", run=run or (lambda argv: 1), lstat=lstat or files.get,
                      listdir=listdir or (lambda p: sorted((DP.PIN_NAME, DP.REGISTER_NAME))),
                      unit_state=lambda u: unit,
                      activation=activation or (lambda: (1, DP.GRANT_ABSENT + " advisoryConfigEnabled=False\n")),
                      euid=lambda: 0, say=lines.append)
        return ok, lines

    def test_pass_transcript_is_exact_and_deterministic(self):
        ok, lines = self.probes()
        self.assertTrue(ok)
        self.assertEqual(len(lines), 18)
        self.assertEqual(sum(line.startswith("DENIED: ") for line in lines), 10)
        self.assertEqual(lines[-1], "MB8_OWNER_INPUT_DENIAL_PROOF=PASS phase=P1B-8 denied=10 allowed=0")
        self.assertEqual(self.probes()[1], lines)
        self.assertTrue(all(DP.SIGNER in line or DP.WITNESS in line or DP.BROKER in line or DP.DEPLOYER in line
                            or DP.APPLICATION in line for line in lines if line.startswith("DENIED")))

    def test_allowed_inconclusive_and_preconditions_fail(self):
        self.assertFalse(self.probes(run=lambda argv: 0)[0])
        self.assertFalse(self.probes(run=lambda argv: 2)[0])
        self.assertFalse(self.probes(unit="active")[0])
        self.assertFalse(self.probes(activation=lambda: (0, "ACTIVATION=ACCEPTED {}\n"))[0])
        self.assertFalse(self.probes(listdir=lambda p: [DP.PIN_NAME])[0])
        bad = {DP.OWNER_INPUT_DIR: _st(stat.S_IFDIR | 0o755), DP.COPIES[0]: _st(stat.S_IFREG | 0o664),
               DP.COPIES[1]: _st(stat.S_IFREG | 0o644)}
        ok, lines = self.probes(lstat=bad.get)
        self.assertFalse(ok)
        self.assertIn("probes=0", lines[-1])
        self.assertFalse(DP.prove("P1B-6", euid=lambda: 0, say=lambda _: None))


# ------------------------------------------------------------------------- the operator (fake transport) ---

class FakeRun:
    """git reads the worktree; ssh answers by command shape. Records every argv."""

    def __init__(self, *, w8_phase="W8_0_NO_OWNER_INPUTS", install=(0, p1b8_report(), b"")):
        self.calls: list[list[str]] = []
        self.w8_phase, self.install = w8_phase, install

    def __call__(self, argv):
        argv = list(argv)
        self.calls.append(argv)
        done = lambda rc=0, out=b"", err=b"": subprocess.CompletedProcess(argv, rc, out, err)  # noqa: E731
        if argv[:1] == ["git"]:
            if argv[3:5] == ["rev-parse", "HEAD"]:
                return done(out=(CONTROL + "\n").encode())
            if argv[3:4] == ["status"]:
                return done()
            if argv[3] == "show" and argv[4].startswith("HEAD:"):
                return done(out=(ROOT / argv[4][5:]).read_bytes())
        command = argv[-1] if argv and argv[-1].startswith("--command=") else ""
        if "install-owner-inputs" in command:
            return done(*self.install)
        if "mb8_owner_input_verifier" in command:
            phase = self.w8_phase
            rc = 0 if f"expect {phase}" in command or "observe" in command else 1
            return done(rc, json.dumps({"phase": phase, "evidence": {}}).encode())
        return done()

    def remote(self) -> list[str]:
        return [c[-1] for c in self.calls if c[-1].startswith("--command=")]


class OperatorTests(Redacted, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name) / "work"
        self.work.mkdir()
        C.write_emitted(synthetic_derivation(), self.work / "genesis")
        self.c = O.Operator.candidate(self.work)
        self.operator_sha = sha(Path(O.__file__).read_bytes())

    def text(self, lines, **values) -> Path:
        path = Path(self.tmp.name) / f"text-{len(os.listdir(self.tmp.name))}.txt"
        path.write_text("\n".join("> " + line.format(**values) for line in lines) + "\n", encoding="utf-8")
        return path

    def go(self, **overrides):
        values = dict(control=CONTROL, operator=self.operator_sha, candidate=self.c["candidate"], pin=self.c["pin"],
                      record=self.c["record"], updated_at=UPDATED_AT,
                      register=self.c["register"])
        values.update(overrides)
        return self.text(O.MB8_GO_LINES, **values)

    def ready_for_mb8(self):
        (self.work / "mb7").mkdir()
        for name in ("MB7_TECHNICAL_PASS.json", "GENESIS_PREPARED_ACCEPTED.json"):
            (self.work / "mb7" / name).write_text("{}\n", encoding="ascii")

    def test_mb8_refuses_before_the_marker(self):
        run = FakeRun()
        op = O.Operator(gcloud=("gcloud",), run=run)
        with self.assertRaises(O.Stop) as caught:
            op.mb8(ROOT, self.work, self.go())
        self.assertEqual(caught.exception.code, "MB7_TECHNICAL_PASS_ABSENT")
        self.ready_for_mb8()
        for go, code in ((self.go(candidate="0" * 64), "GO_LINE_MISSING"), (self.go(pin="0" * 64), "GO_LINE_MISSING"),
                         (self.go(operator="0" * 64), "GO_LINE_MISSING")):
            with self.assertRaises(O.Stop) as caught:
                op.mb8(ROOT, self.work, go)
            self.assertEqual(caught.exception.code, code)
        stop = O.Operator(gcloud=("gcloud",), run=FakeRun(w8_phase="W8_2_PIN_ONLY_EXACT"))
        with self.assertRaises(O.Stop) as caught:
            stop.mb8(ROOT, self.work, self.go())
        self.assertEqual(caught.exception.code, "PRE_STATE_NOT_W8_0")
        self.assertFalse((self.work / "attempts" / "mb8.json").exists())        # nothing consumed
        self.assertFalse(any("install-owner-inputs" in c for c in run.remote()))

    def test_mb8_is_exactly_one_invocation_and_the_marker_consumes_the_go(self):
        self.ready_for_mb8()
        run = FakeRun()
        op = O.Operator(gcloud=("gcloud",), run=run)
        result = op.mb8(ROOT, self.work, self.go())
        self.assertEqual((result["result"], result["transcript"]), ("MB8_INVOKED_ONCE", "INSTALL_PASS"))
        installs = [c for c in run.remote() if "install-owner-inputs" in c]
        self.assertEqual(len(installs), 1)
        self.assertIn(f"install-owner-inputs {O.RELEASE_SHA} {O.STAGE_DIR}/genesis-pin.json "
                      f"{O.STAGE_DIR}/authorization-register.json", installs[0])
        with self.assertRaises(O.Stop) as caught:
            op.mb8(ROOT, self.work, self.go())
        self.assertEqual(caught.exception.code, "ATTEMPT_ALREADY_CONSUMED:mb8")
        self.assertEqual(len([c for c in run.remote() if "install-owner-inputs" in c]), 1)

    def test_a_failure_after_the_marker_is_recorded_not_retried(self):
        self.ready_for_mb8()
        run = FakeRun(install=(255, b"", b"ssh: connection lost\n"))
        result = O.Operator(gcloud=("gcloud",), run=run).mb8(ROOT, self.work, self.go())
        self.assertEqual((result["result"], result["transcript"], result["attempt"]),
                         ("MB8_STOP", "TRANSPORT_FAILED", "CONSUMED"))
        self.assertEqual(len([c for c in run.remote() if "install-owner-inputs" in c]), 1)

    def test_owner_texts_are_separate_and_bounded(self):
        joined = flat(" ".join(O.SEQUENCE_LINES))
        self.assertIn("authorizes the read-only M-B7 only", joined)
        self.assertNotIn("I authorize M-B8", joined)
        act2 = flat(" ".join(O.GENESIS_PREPARED_LINES))
        self.assertIn("does not authorize the M-B8 host install", act2)
        self.assertIn("create-only, in P-A /root/lilith-genesis-pin-dev-synthetic", act2)
        self.assertIn("MB7_MB8_UPDATED_AT: {updated_at}, captured once", flat(" ".join(O.SEQUENCE_LINES)))
        go = flat(" ".join(O.MB8_GO_LINES))
        for phrase in ("exactly one attempt", "does not authorize M-B9a, M-B9b", "There is no automatic retry",
                       "OWNER_REGISTER = KNOWN_EMPTY", "byte-identical and separately hash-verified",
                       "MB7_MB8_UPDATED_AT: {updated_at}", "GENESIS_PREPARED was owner-accepted"):
            self.assertIn(phrase, go)
        self.assertIn("is not a new pin", flat(" ".join(O.REMOVAL_LINES)))

    def test_accept_b7_needs_the_technical_pass_and_the_exact_statement(self):
        op = O.Operator(gcloud=("gcloud",), run=FakeRun())
        statement = self.text(O.GENESIS_PREPARED_LINES, candidate=self.c["candidate"], updated_at=UPDATED_AT,
                              pin=self.c["pin"], register=self.c["register"], record=self.c["record"],
                              stdout=self.c["stdout"])
        with self.assertRaises(O.Stop):
            op.accept_b7(self.work, statement)
        (self.work / "mb7").mkdir()
        (self.work / "mb7" / "MB7_TECHNICAL_PASS.json").write_text("{}\n", encoding="ascii")
        with self.assertRaises(O.Stop):
            op.accept_b7(self.work, self.text(O.GENESIS_PREPARED_LINES, candidate="0" * 64, updated_at=UPDATED_AT,
                                              pin=self.c["pin"], register=self.c["register"], record=self.c["record"],
                                              stdout=self.c["stdout"]))
        self.assertEqual(op.accept_b7(self.work, statement)["result"], "GENESIS_PREPARED_OWNER_ACCEPTANCE_RECORDED")
        with self.assertRaises(O.Stop) as caught:
            op.accept_b7(self.work, statement)
        self.assertEqual(caught.exception.code, "GENESIS_PREPARED_ALREADY_RECORDED")

    def test_mb7_is_read_only_and_needs_the_sequence_authorization(self):
        run = FakeRun()
        op = O.Operator(gcloud=("gcloud",), run=run)
        auth = self.text(O.SEQUENCE_LINES, control=CONTROL, operator=self.operator_sha, candidate=self.c["candidate"],
                         updated_at=UPDATED_AT)
        bad = self.text(O.SEQUENCE_LINES, control=CONTROL, operator=self.operator_sha, candidate="0" * 64,
                        updated_at=UPDATED_AT)
        with self.assertRaises(O.Stop):
            op.mb7(ROOT, self.work, Path(self.tmp.name) / "ev0", bad)
        result = op.mb7(ROOT, self.work, Path(self.tmp.name) / "ev1", auth)
        self.assertEqual(result["result"], "MB7_NOT_PASS")                 # the fake host prints no stdout
        commands = run.remote()
        cli = [c for c in commands if "genesis-candidate" in c]
        self.assertEqual(len(cli), 1)
        self.assertIn(f"sudo -n {O.VERIFY_CLI} genesis-candidate 1 {UPDATED_AT}", cli[0])
        for command in commands:
            for forbidden in ("install-owner-inputs", " bootstrap", "systemctl start", "provision"):
                self.assertNotIn(forbidden, command)
        self.assertFalse((self.work / "mb7" / "MB7_TECHNICAL_PASS.json").exists())

    def test_source_has_one_mutation_path_and_no_later_forms(self):
        source = Path(O.__file__).read_text(encoding="utf-8")
        code = source.split('"""', 2)[2]
        self.assertEqual(code.count('f"install-owner-inputs {RELEASE_SHA}'), 1)   # the one call (the go line differs)
        self.assertEqual(code.count("self.ssh(self.streamed(repo, INSTALLER, SYSTEM_PYTHON, args))"), 1)
        for forbidden in ("execute-head-advance", "create-initial-held", "provision-as-signer", "systemctl start",
                          "systemctl enable", "daemon-reload", "witness-state", "'bootstrap'", '"bootstrap"'):
            self.assertNotIn(forbidden, code, forbidden)

    def test_dr5_is_bound_to_a_verified_w8_phase(self):
        op = O.Operator(gcloud=("gcloud",), run=FakeRun())
        log = Path(self.tmp.name) / "deploy.log"
        lines = ["DENIED: test -w /opt", "PR1_AUTHORITY_BOUNDARY maturity=P1A-9",
                 "AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3", "DENIED: sudo -n true",
                 "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=False"]
        log.write_text("\n".join("2026-10-08T00:00:00.0000000Z " + line for line in lines) + "\n", encoding="utf-8")
        target = O.load_tool(ROOT, O.DR5_TARGET, "mb6_dr5_target_test")
        sets = target.extract(log.read_text(encoding="utf-8"))
        post = {name: (len(v), target.digest(v)) for name, v in sets.items()}
        with mock.patch.object(O, "load_tool", return_value=target), mock.patch.dict(target.POST, post):
            for phase in O.DR5_PHASES:
                self.assertEqual(op.dr5(ROOT, phase, log)["result"], "EQUAL")
            for phase in ("W8_2_PIN_ONLY_EXACT", "LEDGER_COMMITTED_EXACT", "UNCLASSIFIED_STOP"):
                with self.assertRaises(O.Stop) as caught:
                    op.dr5(ROOT, phase, log)
                self.assertTrue(caught.exception.code.startswith("NO_BASELINE_STOP"))
        self.assertEqual(op.dr5(ROOT, O.DR5_PHASES[0], log)["result"], "DRIFT")       # the real accepted pins


# ------------------------------------------------------------------------------------ bounded removal ---

@unittest.skipUnless(POSIX, "POSIX owner/mode semantics")
class RemovalTests(Redacted, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.host = RM.Host(root=root, owner_uid=UID, owner_gid=GID, euid=lambda: 0, hostname=lambda: "lilith-dev-01")
        for directory in ("etc/lilith-authority-dev/owner", "var/lib/lilith-authority-dev",
                          "var/lib/lilith-authority-custody/holds"):
            (root / directory).mkdir(parents=True)
        os.chmod(root / "etc/lilith-authority-dev/owner", 0o755)
        (root / "var/lib/lilith-authority-dev/authority_ledger.db").write_bytes(b"ledger")
        (root / "etc/machine-id").write_text(RM.DEV_MACHINE_ID + "\n", encoding="ascii")
        self.root = root

    def place(self, name: str, data: bytes):
        path = self.root / "etc/lilith-authority-dev/owner" / name
        path.write_bytes(data)
        os.chmod(path, 0o644)
        return path

    def test_plan_and_remove_a_partial_state(self):
        self.place("genesis-pin.json", b'{"pinType"')
        plan = RM.plan(self.host)
        self.assertEqual(plan["remove"], [RM.PIN_COPY])
        with self.assertRaises(RM.Refused) as caught:
            RM.remove(self.host, "0" * 64)
        self.assertEqual(caught.exception.reason, "PLAN_CHANGED")
        done = RM.remove(self.host, plan["planDigest"])
        self.assertEqual((done["removed"], done["result"]), ([RM.PIN_COPY], "PRE_MB8_RESTORED"))
        self.assertEqual(os.listdir(self.root / "etc/lilith-authority-dev/owner"), [])
        self.assertTrue((self.root / "var/lib/lilith-authority-dev/authority_ledger.db").exists())
        with self.assertRaises(RM.Refused) as caught:
            RM.remove(self.host, RM.plan(self.host)["planDigest"])
        self.assertEqual(caught.exception.reason, "NOTHING_TO_REMOVE")

    def test_removal_order_is_the_reverse_of_the_install_order(self):
        self.place("genesis-pin.json", b"{}")
        self.place("authorization-register.json", b"{}")
        self.assertEqual(RM.plan(self.host)["remove"], [RM.REGISTER_COPY, RM.PIN_COPY])

    def test_refusals(self):
        self.place("genesis-pin.json", b"{}")
        for setup, reason in (
                (lambda: (self.root / "var/lib/lilith-recovery-witness").mkdir(), "LATER_STATE_PRESENT"),
                (lambda: (self.root / "var/lib/lilith-authority-custody/holds/x.json").write_bytes(b"{}"),
                 "LATER_STATE_PRESENT"),
                (lambda: self.place("other.json", b"{}"), "OWNER_INPUT_DIRECTORY_UNEXPECTED"),
                (lambda: os.link(self.root / "etc/lilith-authority-dev/owner/genesis-pin.json",
                                 self.root / "hardlink"), "FILE_UNEXPECTED"),
                (lambda: (self.root / "var/lib/lilith-authority-dev/authority_ledger.db").unlink(), "NOT_POST_LEDGER")):
            with self.subTest(reason):
                setup()
                with self.assertRaises(RM.Refused) as caught:
                    RM.plan(self.host)
                self.assertTrue(caught.exception.reason.startswith(reason), caught.exception.reason)
                self.setUp()
                self.place("genesis-pin.json", b"{}")
        os.unlink(self.root / "etc/lilith-authority-dev/owner/genesis-pin.json")
        os.symlink("/etc/passwd", self.root / "etc/lilith-authority-dev/owner/genesis-pin.json")
        with self.assertRaises(RM.Refused):
            RM.plan(self.host)

    def test_removal_source_touches_only_the_two_copies(self):
        source = Path(RM.__file__).read_text(encoding="utf-8").split('"""', 2)[2]
        self.assertEqual(source.count("os.unlink("), 1)
        for forbidden in ("rmtree", "rmdir", "os.remove", "authority_ledger.db\")", "systemctl"):
            self.assertNotIn(forbidden, source.replace('LEDGER = "/var/lib/lilith-authority-dev/authority_ledger.db"',
                                                       ""))


# ----------------------------------------------------------------------------------------- the record ---

class RecordTests(Redacted, unittest.TestCase):
    def setUp(self):
        self.text = PACKAGE.read_text(encoding="utf-8")
        self.flat = flat(self.text)
        self.state = self.text.split("## 20. State", 1)[1]

    def test_state_and_boundaries(self):
        for line in NOT_AUTHORIZED + ("LEDGER_HEAD = " + HEAD, "LEDGER_SEQUENCE = 1",
                                      "AUTHORIZATION_REGISTER_COPY_MISSING = TRUE", "GENESIS_PIN_COPY_MISSING = TRUE",
                                      "GRANT_ABSENT = TRUE", "authorityGranted = false",
                                      "MB7_MB8_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_STAGE "
                                      "(OWNER-ACCEPTED 2026-10-08, OD-1)",
                                      "MB7_TEMP_LEDGER_COPY = EPHEMERAL_SCRATCH_IO_ONLY (OWNER-ACCEPTED 2026-10-08, OD-5)",
                                      "P_A = /root/lilith-genesis-pin-dev-synthetic",
                                      "P_B = $HOME/lilith-genesis-pin-dev-synthetic",
                                      "MB7_MB8_UPDATED_AT = NOT CAPTURED"):
            self.assertIn(line, self.state)
        for claim in FORBIDDEN_CLAIMS:
            self.assertNotIn(claim, self.text.split("## 14.", 1)[0] + self.state)

    def test_tool_pins_in_the_record_equal_the_code(self):
        for path, pin in O.TOOL_PINS.items():
            self.assertIn(f"`{path}`", self.text)
            self.assertIn(pin, self.text, path)

    def test_owner_texts_are_reproduced_verbatim(self):
        for lines in (O.SEQUENCE_LINES, O.GENESIS_PREPARED_LINES, O.MB8_GO_LINES, O.REMOVAL_LINES):
            for line in lines:
                literal = line.replace("{control}", "<control>").replace("{operator}", "<operator>")
                literal = literal.replace("{{updated_at}}", "<updatedAt>").replace("{updated_at}", "<updatedAt>")
                for key in ("candidate", "pin", "register", "record", "stdout", "plan", "phase"):
                    literal = literal.replace("{" + key + "}", f"<{key}>")
                self.assertIn(flat(literal), self.flat, literal[:60])

    def test_first_memory_hard_boundary(self):
        section = self.text.split("## 18.", 1)[1].split("## 19.", 1)[0]
        for phrase in ("inferred by tooling", "auto-generated", "selected by Claude", "selected by a model",
                       "readiness gates pass", "FIRST_MEMORY_READY", "execution MUST STOP"):
            self.assertIn(phrase, section)

    def test_ledger_and_index(self):
        ledger = (ARCH / "current-architecture-acceptance-ledger-v0.1.md").read_text(encoding="utf-8")
        self.assertIn("### 13.1aj Current-state reconciliation (Package A: M-B7 + M-B8 design and tooling", ledger)
        self.assertLess(ledger.index("### 13.1ai"), ledger.index("### 13.1aj"))
        self.assertLess(ledger.index("### 13.1aj"), ledger.index("### 13.2 Checks"))
        self.assertIn("FRESHNESS=UNKNOWN (§13.1aj)", ledger)                   # AUTH-02 (later passes append)
        aj = ledger.split("### 13.1aj", 1)[1].split("\n### 13.", 1)[0]       # §13.1aj only, up to the next section
        for claim in FORBIDDEN_CLAIMS:
            self.assertNotIn(claim, aj)
        self.assertIn("owner decisions OD-1 … OD-5", aj)
        readme = (ARCH / "README.md").read_text(encoding="utf-8")
        self.assertIn("(slice-15b2b-b1b3e-mb7-mb8-genesis-prep-package.md)", readme)

    def test_dr5_and_point_of_no_return_statements(self):
        for phrase in ("POST_MB8_DR5_TARGET = NOT DERIVED (NO DR-5-OBSERVABLE DELTA)",
                       "M-B7 = NOT LINEAGE-COMMITTING", "M-B9b = LINEAGE POINT OF NO RETURN",
                       "OWNER PIN (P-A, P-B) = RECORD POINT OF NO RETURN"):
            self.assertIn(phrase, self.text)


# --------------------------------------------------------------------------- synthetic host (crypto) ---

if HAVE_CRYPTO and POSIX:
    import install_authority_dev as I
    import mb6_ledger_verifier as V6
    import test_b1b3e_mb6_ledger_remediation as T6
    from lilith_authority_host import paths as P
    from lilith_authority_root import genesis as G
    from test_b1b3e_mb4_mb5_installable_inputs import P as WP
    _Base = T6.Mb6Base
else:  # pragma: no cover - the stdlib layer still runs
    _Base = unittest.TestCase


@unittest.skipUnless(HAVE_CRYPTO and POSIX and hasattr(__import__("sqlite3").Connection, "deserialize"),
                     "POSIX owner/mode semantics, sqlite3 deserialize, cryptography/rfc8785/fido2 required")
class HostTests(_Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        registry = json.loads(cls.files["authority-registry.v1.json"])
        w = cls.src.world.accepted
        cls.candidate_pins = C.CandidatePinsV1(
            registry_sha256=sha(cls.files["authority-registry.v1.json"]),
            root_anchor_sha256=sha(cls.files["registry-root.json"]),
            witness_anchor_sha256=sha(cls.files["witness-anchor.json"]), registry_digest=cls.src.pins.registry_digest,
            registry_issued_at=registry["issuedAt"], ledger_head=cls.head, kwit_key_id=w.kwit_key_id,
            kwit_public_key_sha256=w.kwit_public_key_sha256, epoch_random=WP.EPOCH, policy_version=WP.L.POLICY_VERSION)
        cls.updated_at = registry["issuedAt"]
        cls.owner_tool = C.load_owner_tool()
        cls.derived = C.derive(cls.files["authority-registry.v1.json"], cls.files["registry-root.json"],
                               cls.files["witness-anchor.json"], cls.updated_at, pins=cls.candidate_pins,
                               now=lambda: datetime(2100, 1, 1, tzinfo=timezone.utc), owner_tool=cls.owner_tool)
        cls.digest = cls.derived["candidateDigest"]

    def setUp(self):
        super().setUp()
        signer = self.host.users[I.SERVICE_USER]
        if 0 < UID < 1000:
            signer.pw_uid, signer.pw_gid = UID, GID
            self.host.groups[I.SERVICE_GROUP].gr_gid = GID
            self.provision()
        elif UID == 0:
            self.provision(as_signer=False)
            for path in (self.state(), self.target(P.AUTHORITY_LEDGER)):
                os.chown(path, signer.pw_uid, signer.pw_gid)
        else:
            self.skipTest("the system-account contract needs 0 < uid < 1000, or root to chown (CI runs uid >= 1000)")
        self.signer_ids = (signer.pw_uid, signer.pw_gid)
        self.assertEqual(self.status("P1B-6")["result"], "PASS")
        self.inputs = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        (self.inputs / "genesis-pin.json").write_bytes(self.derived["genesisPinBytes"].encode())
        (self.inputs / "authorization-register.json").write_bytes(self.derived["authorizationRegisterBytes"].encode())

    # ------------------------------------------------------------------------------------------ helpers ---

    def w8(self, digest=None, updated_at=None) -> dict:
        return W.evaluate(self.head, digest or self.digest, updated_at or self.updated_at, root=self.root,
                          owner_uid=UID, owner_gid=GID, signer=self.signer_ids, pins=self.pins,
                          trust_pins=self.trust_pins)

    def install(self) -> dict:
        return I.stage_install_owner_inputs(self.system, T6.U.NEW, self.inputs / "genesis-pin.json",
                                            self.inputs / "authorization-register.json")

    def owner_file(self, name: str, data: bytes, mode: int = 0o644) -> Path:
        path = self.target(P.OWNER_INPUT_DIR) / name
        path.write_bytes(data)
        os.chmod(path, mode)
        return path

    # -------------------------------------------------------------------------------------------- M-B7 ---

    def test_owner_candidate_equals_reproduce_and_the_host_m_b7_path_byte_for_byte(self):
        self.assertEqual(self.derived["unsignedGenesis"]["witnessKeyId"], self.candidate_pins.kwit_key_id)
        before = T6.tree(self.root)
        built, _inputs, _ledger = G.candidate(environment="dev", registry_version=1, updated_at=self.updated_at,
                                              root=self.root, owner_uid=UID)
        stdout = json.dumps(G.candidate_report(built), sort_keys=True, separators=(",", ":")).encode() + b"\n"
        self.assertEqual(built.digest, self.digest)
        self.assertEqual(stdout, self.derived["expectedHostStdout"].encode())
        self.assertEqual(T6.tree(self.root), before)                     # M-B7 wrote nothing under the host root
        report = self.w8()
        self.assertEqual(report["phase"], W.W8_0, report["failures"])
        self.assertEqual(report["evidence"], {"hostCandidateDigestEqualsOwnerDigest": True,
                                              "onHostPinCopyEqualsOffHost": False, "pinEqualsCandidateDigest": False})
        self.assertEqual(set(report["hostInputReasons"]), W.W5_GAPS)

    def test_owner_derivation_refusals(self):
        derive = lambda pins=self.candidate_pins, updated=self.updated_at, files=None, now=None: C.derive(  # noqa: E731
            *(files or (self.files["authority-registry.v1.json"], self.files["registry-root.json"],
                        self.files["witness-anchor.json"])), updated, pins=pins,
            now=now or (lambda: datetime(2100, 1, 1, tzinfo=timezone.utc)), owner_tool=self.owner_tool)
        cases = ((dict(pins=dataclasses.replace(self.candidate_pins, ledger_head="0" * 64)),
                  "LEDGER_POSITION_NOT_OWNER_ACCEPTED"),
                 (dict(pins=dataclasses.replace(self.candidate_pins, registry_sha256="0" * 64)),
                  "REGISTRY_NOT_THE_ACCEPTED_INSTALLABLE"),
                 (dict(files=(self.files["authority-registry.v1.json"], self.files["registry-root.json"],
                              self.files["registry-root.json"])), "WITNESS_ANCHOR_NOT_THE_ACCEPTED_INSTALLABLE"),
                 (dict(now=lambda: datetime(2000, 1, 1, tzinfo=timezone.utc)), "UPDATED_AT_IN_THE_FUTURE"))
        for kwargs, reason in cases:
            with self.subTest(reason), self.assertRaises(C.CandidateError) as caught:
                derive(**kwargs)
            self.assertEqual(caught.exception.reason, reason)
        self.assertNotEqual(self.digest, self.w8(updated_at="2099-01-01T00:00:00Z")["hostCandidateDigest"])
        self.assertEqual(self.w8(updated_at="2099-01-01T00:00:00Z")["phase"], W.UNCLASSIFIED)

    # -------------------------------------------------------------------------------------------- M-B8 ---

    def test_install_owner_inputs_reaches_exact_and_changes_nothing_else(self):
        before = T6.tree(self.root)
        report = self.install()
        self.assertEqual(report["result"], "PASS", report["failures"])
        after = T6.tree(self.root)
        added = sorted(set(after) - set(before))
        self.assertEqual(added, ["etc/lilith-authority-dev/owner/authorization-register.json",
                                 "etc/lilith-authority-dev/owner/genesis-pin.json"])
        changed = sorted(k for k in before if after[k] != before[k])
        self.assertEqual(changed, [])                                     # (mtime is not part of `tree`)
        result = self.w8()
        self.assertEqual(result["phase"], W.EXACT, result["failures"])
        self.assertEqual(result["evidence"], dict.fromkeys(W.EVIDENCE, True))
        self.assertEqual(result["hostInputReasons"], [])
        self.assertEqual((result["registryEffective"], result["authorityActive"], result["authorityGranted"]),
                         (False, False, False))
        self.assertFalse(result["witnessGenesisPresent"])
        # the accepted M-B6 tool's scope has ended (owner inputs present); the W5 verifier is unchanged
        mb6 = self.verify()
        self.assertEqual(mb6["phase"], V6.LATER_STATE)
        import mb4_mb5_trust_install_verifier as V5
        w5 = V5.evaluate(root=self.root, owner_uid=UID, owner_gid=GID, pins=self.trust_pins)
        self.assertEqual(w5["phase"], "OUT_OF_SCOPE_POST_LEDGER")
        self.assertTrue(all(w5["evidence"].values()))
        self.assertEqual(self.status("P1B-8")["result"], "PASS")
        self.assertIn("LISTING:" + I.OWNER_INPUT_DIR, self.status("P1B-6")["failures"])
        # the host M-B7 path still derives the same candidate, and the pin now gates it (RR-35 step 4)
        built, inputs, _ = G.candidate(environment="dev", registry_version=1, updated_at=self.updated_at,
                                       root=self.root, owner_uid=UID)
        from lilith_owner_memory import pr1_bootstrap as B
        self.assertIsNone(B.candidate_pin_reason(inputs.genesis_pin, built, environment="dev"))

    def test_partial_states(self):
        pin, register = self.derived["genesisPinBytes"].encode(), self.derived["authorizationRegisterBytes"].encode()
        cases = (
            ({"genesis-pin.json": (b"", 0o644)}, W.W8_1),
            ({"genesis-pin.json": (pin[:20], 0o644)}, W.W8_1),
            ({"genesis-pin.json": (pin, 0o600)}, W.W8_1),                 # bytes complete, chmod not reached
            ({"genesis-pin.json": (pin, 0o644)}, W.W8_2),
            ({"genesis-pin.json": (pin, 0o644), "authorization-register.json": (register[:7], 0o644)}, W.W8_3),
            ({"genesis-pin.json": (pin, 0o644), "authorization-register.json": (b"", 0o600)}, W.W8_3),
            ({"authorization-register.json": (register, 0o644)}, W.UNCLASSIFIED),       # not reachable
            ({"genesis-pin.json": (pin[:5], 0o644), "authorization-register.json": (b"", 0o644)}, W.UNCLASSIFIED),
            ({"genesis-pin.json": (C.document_bytes(C.pin_document("e" * 64)), 0o644)}, W.FOREIGN),
            ({"genesis-pin.json": (pin, 0o664)}, W.FOREIGN),
            ({"genesis-pin.json": (pin, 0o644), "authorization-register.json": (pin, 0o644)}, W.FOREIGN),
            ({"genesis-pin.json": (pin, 0o644), "other.json": (b"{}", 0o644)}, W.UNCLASSIFIED),
        )
        for files, phase in cases:
            with self.subTest(sorted(files), phase=phase):
                try:
                    for name, (data, mode) in files.items():
                        self.owner_file(name, data, mode)
                    report = self.w8()
                    self.assertEqual(report["phase"], phase, report["failures"])
                    self.assertEqual(report["evidence"], dict.fromkeys(W.EVIDENCE, False))
                    self.assertEqual(report["routing"], W.ROUTING[phase][0])
                finally:
                    for name in files:
                        (self.target(P.OWNER_INPUT_DIR) / name).unlink()
        self.owner_file("genesis-pin.json", pin)
        os.symlink("genesis-pin.json", self.target(P.OWNER_INPUT_DIR) / "authorization-register.json")
        self.assertEqual(self.w8()["phase"], W.FOREIGN)

    def test_later_state_is_out_of_scope(self):
        self.install()
        self.target(P.WITNESS_STATE).mkdir(mode=0o750)
        self.assertEqual(self.w8()["phase"], W.LATER_STATE)
        with self.assertRaises(RM.Refused):
            RM.plan(RM.Host(root=self.root, owner_uid=UID, owner_gid=GID, euid=lambda: 0,
                            hostname=lambda: "lilith-dev-01"))

    def test_interrupted_m_b8_blocks_rerun_until_the_bounded_removal(self):
        real = I._install_once
        calls = []

        def crash_on_register(system, absolute, data):
            calls.append(absolute)
            if absolute == I.AUTHORIZATION_REGISTER_COPY:
                raise OSError("simulated crash between the two writes")
            return real(system, absolute, data)
        with mock.patch.object(I, "_install_once", crash_on_register), self.assertRaises(OSError):
            self.install()
        self.assertEqual(calls, [I.GENESIS_PIN_COPY, I.AUTHORIZATION_REGISTER_COPY])
        self.assertEqual(self.w8()["phase"], W.W8_2)
        self.assertEqual(W.classify_sequence(host_phase=W.W8_2, attempt_consumed=True,
                                             transcript=W.FAILED_UNCLASSIFIED, post_verified=False), W.W8_2)
        before = T6.tree(self.root)
        with self.assertRaises(I.InstallError) as caught:                   # no retry path: P1B-6 no longer holds
            self.install()
        self.assertTrue(caught.exception.reason.startswith("PRECONDITION_FAILED"))
        self.assertEqual(T6.tree(self.root), before)
        host = RM.Host(root=self.root, owner_uid=UID, owner_gid=GID, euid=lambda: 0, hostname=lambda: "lilith-dev-01")
        (self.root / "etc/machine-id").write_text(RM.DEV_MACHINE_ID + "\n", encoding="ascii")
        plan = RM.plan(host)
        self.assertEqual(plan["remove"], [RM.PIN_COPY])
        self.assertEqual(RM.remove(host, plan["planDigest"])["result"], "PRE_MB8_RESTORED")
        self.assertEqual(self.w8()["phase"], W.W8_0)
        self.assertEqual(self.status("P1B-6")["result"], "PASS")
        self.assertEqual(self.install()["result"], "PASS")                   # a NEW attempt (a new go) succeeds
        self.assertEqual(self.w8()["phase"], W.EXACT)


if __name__ == "__main__":
    unittest.main()
