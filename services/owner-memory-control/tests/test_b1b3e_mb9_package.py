"""15B2b-B1b-3e Package B (M-B9a START_WITNESS + M-B9b COMMIT_WITNESS_GENESIS) (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-mb9-witness-genesis-package.md.

Two layers:

- stdlib (every platform): tool pins, the DR-5 targets derived from the ACCEPTED post-M-B6 texts, the W9 phase
  and sequence tables, the transcript / health / sequence classifiers, the witness denial proof on fake probes,
  the P1B-6 / P1B-8 phase limitation, the operator's marker, go-binding and refusal semantics on a fake
  transport, and the records;
- POSIX + cryptography (the M-B6 synthetic host + the real installer + the REAL witness writer and filesystem
  store, under a TEMPORARY root, with throwaway TEST keys): every W9 host phase reached through real code and
  real fault points, the commit point, the bounded removal, and the owner offline verification.

Nothing touches `/`, DEV, the S25 or any real key. Failure messages redact every 64-hex value.
"""

from __future__ import annotations

import ast
import contextlib
import dataclasses
import hashlib
import importlib.util
import json
import os
import re
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "services/owner-memory-control/tools"
ARCH = ROOT / "docs/architecture"
PACKAGE = ARCH / "slice-15b2b-b1b3e-mb9-witness-genesis-package.md"
COMPLETION_A = ARCH / "slice-15b2b-b1b3e-mb7-mb8-package-a-completion.md"
FIXTURE = Path(__file__).resolve().parent / "b1b3e_mb9_post_mb6_dr5_baseline.json"
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
import mb7_genesis_candidate as C  # noqa: E402
import mb7_mb8_operator as A  # noqa: E402
import mb9_dr5_target as T  # noqa: E402
import mb9_operator as O  # noqa: E402
import mb9_owner_genesis_verify as OV  # noqa: E402
import mb9_witness_denial_proof as DP  # noqa: E402
import mb9_witness_state_removal as RM  # noqa: E402
import mb9_witness_verifier as W  # noqa: E402

HEAD = "19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630"
REGISTRY_DIGEST = "fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc"
REGISTRY_SHA256 = "46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e"
CANDIDATE = "ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4"
ACCEPTED_UPDATED_AT = "2026-10-08T07:21:43Z"
KWIT = "5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf"
CONTROL = "29c2b824cae187037e4434a1ad7f9466f4eb2ab6"
UPDATED_AT = "2026-10-08T00:00:00Z"
INVOCATION, MAINPID = "0123456789abcdef0123456789abcdef", "4242"
PACKAGE_A_TOOL_PINS = {   # the accepted Package A pins (handoff + Package A completion record): unchanged here
    "services/owner-memory-control/tools/mb7_mb8_operator.py":
        "9f13411f363dc956795ce4832d1948e7e6a9a7f7c8d1057291de852e9e2a20cd",
    "services/owner-memory-control/tools/mb7_genesis_candidate.py":
        "d50fcb36afab51a79c7918a7a43c86f97338241f62144c780d8b342c68b3c8b2",
    "services/owner-memory-control/tools/mb8_owner_input_verifier.py":
        "b190c255c88a1bdca0ff8d9cb050443ad24d42f269d49947d47b87775351e341",
    "services/owner-memory-control/tools/mb8_owner_input_removal.py":
        "d9a6e0d5dcfb07558ca7533e8144b7f2b7c29b1b4db28400571aede55b99f7f5",
    "services/owner-memory-control/tools/mb8_owner_input_denial_proof.py":
        "5d63137a2c6e43f12f663febdd4e22fd7b2b519a6c0cfa544dad12f0bc958517",
    "services/authority-dev/ceremony/install_authority_dev.py":
        "fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487",
}
NEW_TOOLS = (O.VERIFIER, O.WITNESS_DENIAL, O.REMOVAL, O.DR5_TARGET, O.OWNER_VERIFY)
FORBIDDEN_CLAIMS = ("M-B9a = AUTHORIZED", "M-B9b = AUTHORIZED", "M-B9a = OWNER-ACCEPTED", "M-B9b = OWNER-ACCEPTED",
                    "WITNESS_GENESIS = COMMITTED", "RECORD 1 = PRESENT", "FRESHNESS=CURRENT", "FRESHNESS = CURRENT",
                    "REGISTRY_EFFECTIVE = YES", "AUTHORITY_ACTIVE = YES", "E-A18 = PERFORMED", "E-A18 = PASS",
                    "FIRST MEMORY = AUTHORIZED", "FIRST_MEMORY = AUTHORIZED")


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
    unsigned = C.expected_unsigned(updated_at, pins)
    digest = C.independent_digest(unsigned)
    pin, register = C.document_bytes(C.pin_document(digest)), C.document_bytes(C.register_document(pins))
    record = C.document_bytes(C.pin_record_document(digest, updated_at, pin, register, pins))
    return {"candidateDigest": digest, "updatedAt": updated_at, "ledgerHead": pins.ledger_head,
            "unsignedGenesis": unsigned, "genesisPinBytes": pin.decode("ascii"),
            "authorizationRegisterBytes": register.decode("ascii"), "pinRecordBytes": record.decode("ascii"),
            "expectedHostStdout": C.host_stdout(digest, unsigned).decode("ascii")}


def fixture_sets() -> dict[str, list[str]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["sets"]


# ------------------------------------------------------------------------------------------- pins ---

class PinTests(Redacted, unittest.TestCase):
    def test_every_tool_hashes_to_its_pin_and_reused_pins_are_unchanged(self):
        for path, pin in O.TOOL_PINS.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)
        for path in (O.INSTALLER, O.W5_VERIFIER, O.MB6_VERIFIER, O.OBSERVER, O.BROKER, O.DENIAL, O.LEDGER_DENIAL):
            self.assertEqual(O.TOOL_PINS[path], M6.TOOL_PINS[path], path)
        for path in (O.MB6_OPERATOR, O.CANDIDATE, O.MB8_VERIFIER, O.OWNER_DENIAL):
            self.assertEqual(O.TOOL_PINS[path], A.TOOL_PINS[path], path)
        self.assertNotIn(O.OPERATOR, O.TOOL_PINS)                       # bound into each owner text at runtime
        for path in NEW_TOOLS:
            self.assertIn(path, O.TOOL_PINS)

    def test_package_a_tooling_is_byte_unchanged(self):
        for path, pin in PACKAGE_A_TOOL_PINS.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)
        self.assertEqual(O.TOOL_PINS[O.MB7_MB8_OPERATOR], PACKAGE_A_TOOL_PINS[O.MB7_MB8_OPERATOR])

    def test_registry_v1_hash_is_the_canonical_64_hex_value_everywhere_in_package_b(self):
        self.assertEqual(C.ACCEPTED_PINS.registry_sha256, REGISTRY_SHA256)
        self.assertEqual(len(REGISTRY_SHA256), 64)
        truncated = re.compile(r"099f8b1(?![0-9a-f])")
        for path in [ROOT / p for p in NEW_TOOLS + (O.OPERATOR,)] + [PACKAGE, COMPLETION_A, Path(__file__)]:
            text = path.read_text(encoding="utf-8").replace("099f8b1(?![0-9a-f])", "")
            self.assertIsNone(truncated.search(text), path.name)

    def test_owner_witness_cli_pin_is_the_release_member_and_in_readiness(self):
        wrapper = (ROOT / "services/authority-dev/bin/lilith-recovery-witness-owner-dev").read_bytes()
        self.assertEqual(sha(wrapper), O.OWNER_CLI_SHA256)
        self.assertEqual(O.READINESS_PROBE.count("'witnessOwnerCli':"), 1)
        self.assertEqual(O.READINESS_PROBE.count("'verifyCli':"), 1)

    def test_accepted_identities(self):
        self.assertEqual((O.LEDGER_HEAD, O.REGISTRY_DIGEST, O.KWIT_PUBLIC_KEY_SHA256, O.KWIT_KEY_ID),
                         (HEAD, REGISTRY_DIGEST, KWIT, C.ACCEPTED_PINS.kwit_key_id))
        self.assertEqual(C.ACCEPTED_PINS.kwit_public_key_sha256, KWIT)
        self.assertEqual((OV.ACCEPTED_CANDIDATE_DIGEST, OV.ACCEPTED_UPDATED_AT), (CANDIDATE, ACCEPTED_UPDATED_AT))
        # the accepted candidate and the three owner record files are re-derived from the accepted identities alone
        derived = synthetic_derivation(ACCEPTED_UPDATED_AT)
        self.assertEqual(derived["candidateDigest"], CANDIDATE)
        self.assertEqual((sha(derived["genesisPinBytes"].encode()), sha(derived["authorizationRegisterBytes"].encode()),
                          sha(derived["pinRecordBytes"].encode())),
                         ("357477369ab53790245b42cbecbe2a630110477bede5b599696699e4f5c3a590",
                          "8d5ab87564d0e531b7d1467c18b6d106f2a468d5d155ce9f2acb64758df85575",
                          "009a0596ca1d7f2f8d941c949c0671f2091b83668aa9315486dbc7f2a0f1e0ae"))


# ------------------------------------------------------------------------------------------- DR-5 ---

class Dr5TargetTests(Redacted, unittest.TestCase):
    def setUp(self):
        self.sets = fixture_sets()
        self.encoded = {name: T.encode(lines) for name, lines in self.sets.items()}

    def test_fixture_is_the_accepted_post_mb6_baseline(self):
        for name in T.SETS:
            self.assertEqual((len(self.sets[name]), T.digest(self.sets[name])), T.BASE[name], name)
        self.assertEqual(T.counts(self.sets["result-set"]), {"lines": 188, "DENIED": 161, "ALLOWED": 0, "FAIL": 0,
                                                              "DEFERRED_UNTIL_OBJECT_EXISTS": 3,
                                                              "UNOBSERVABLE_BY_DESIGN": 6})
        deferred = [line for line in self.sets["result-set"] if line.startswith("DEFERRED_UNTIL_OBJECT_EXISTS")]
        self.assertEqual(deferred, ["DEFERRED_UNTIL_OBJECT_EXISTS: /run/credentials/lilith-authority-dev.service "
                                    "(later step)",
                                    "DEFERRED_UNTIL_OBJECT_EXISTS: /var/lib/lilith-recovery-witness (later step)",
                                    "DEFERRED_UNTIL_OBJECT_EXISTS: /run/credentials/lilith-recovery-witness.service "
                                    "(later step)"])
        for op in ("-w", "-r", "-x"):
            self.assertIn(f"DENIED: test {op} /run/lilith-recovery-witness", self.sets["result-set"])

    def test_derivation_proves_the_owner_reviewed_counts(self):
        result = T.derive(self.encoded)                                       # pinned targets are checked inside
        stopped, running = (result["targets"][name]["sets"] for name in (T.STOPPED, T.RUNNING))
        self.assertEqual(stopped["result-set"]["counts"], {"lines": 190, "DENIED": 164, "ALLOWED": 0, "FAIL": 0,
                                                           "DEFERRED_UNTIL_OBJECT_EXISTS": 2,
                                                           "UNOBSERVABLE_BY_DESIGN": 6})
        self.assertEqual(running["result-set"]["counts"], {"lines": 192, "DENIED": 167, "ALLOWED": 0, "FAIL": 0,
                                                           "DEFERRED_UNTIL_OBJECT_EXISTS": 1,
                                                           "UNOBSERVABLE_BY_DESIGN": 6})
        self.assertEqual((stopped["dr5-block"]["lines"], running["dr5-block"]["lines"]), (151, 153))
        for target in (stopped, running):
            self.assertEqual(target["predeploy-block"]["sha256"], T.BASE["predeploy-block"][1])
        self.assertEqual((result["accepted"], result["derived"], result["rule"]),
                         (False, True, "PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA"))
        self.assertEqual(T.derive(self.encoded), result)                       # deterministic

    def test_only_the_two_witness_lines_change_and_order_is_kept(self):
        result = T.derive(self.encoded)
        base = self.sets["result-set"]
        running = result["targets"][T.RUNNING]["texts"]["result-set"]
        removed = [line for line in base if line not in running]
        added = [line for line in running if line not in base]
        self.assertEqual(removed, [T.STATE_SUBSTITUTION[0], T.CREDENTIAL_SUBSTITUTION[0]])
        self.assertEqual(added, list(T.STATE_SUBSTITUTION[1] + T.CREDENTIAL_SUBSTITUTION[1]))
        untouched = [line for line in base if line not in removed]
        self.assertEqual([line for line in running if line in untouched], untouched)
        i = base.index(T.STATE_SUBSTITUTION[0])
        self.assertEqual(running[i:i + 3], list(T.STATE_SUBSTITUTION[1]))

    def test_substitutions_are_the_exact_dr5_source_lines_and_mb9b_adds_none(self):
        dr5 = (ROOT / "scripts/deployer_authority_boundary_proof.sh").read_text(encoding="utf-8")
        self.assertIn('ab_say "DEFERRED_UNTIL_OBJECT_EXISTS: ${path} (later step)"', dr5)
        later = dr5.split('readonly AB_LATER="', 1)[1].split('"', 1)[0].split()
        self.assertIn(T.WITNESS_STATE, later)
        self.assertIn(T.WITNESS_CREDENTIALS, later)
        body = dr5.split("ab_check_later_state() {", 1)[1].split("\n}", 1)[0]
        self.assertIn("/var/lib/*|/run/*) ab_deny -r", body)
        # nothing beneath the witness state is ever named by the script: M-B9b's chain/, 1.json, witness.json and
        # authorizations/ cannot change a DR-5 line
        for leaf in ("/var/lib/lilith-recovery-witness/", "chain/1.json", "witness.json", "authorizations"):
            self.assertNotIn(leaf, dr5.replace("readonly AB_LATER=", ""), leaf)
        self.assertTrue(T.derive(self.encoded)["mb9bAddsNoDr5Line"])

    def test_phase_bound_comparison_and_no_baseline_stop(self):
        result = T.derive(self.encoded)

        def log(lines):
            return "".join(f"2026-10-08T00:00:00.0000000Z {line}\n" for line in lines)
        running = result["targets"][T.RUNNING]["texts"]["result-set"]
        stopped = result["targets"][T.STOPPED]["texts"]["result-set"]
        self.assertEqual(T.compare("W9_5_GENESIS_COMMITTED_EXACT", log(running))["result"], "EQUAL")
        self.assertEqual(T.compare("W9_2_STARTED_UNINITIALIZED", log(running))["result"], "EQUAL")
        self.assertEqual(T.compare("W9_5S_GENESIS_COMMITTED_STOPPED", log(stopped))["result"], "EQUAL")
        self.assertEqual(T.compare("W9_0_PRE_WITNESS", log(self.sets["result-set"]))["result"], "EQUAL")
        self.assertEqual(T.compare("W9_5_GENESIS_COMMITTED_EXACT", log(stopped))["result"], "DRIFT")
        self.assertEqual(T.compare("W9_0_PRE_WITNESS", log(running))["result"], "DRIFT")
        self.assertTrue(set(T.PHASE_TARGETS) <= set(W.HOST_PHASES))
        for phase in set(W.HOST_PHASES) - set(T.PHASE_TARGETS):
            with self.assertRaises(T.TargetError) as caught:
                T.compare(phase, log(running))
            self.assertEqual(caught.exception.reason, "NO_BASELINE_STOP:" + phase)
        for phase in ("W9_1P_STATE_DIR_PARTIAL", "W9_3_PRECOMMIT_DIRS", "W9_4_COMMITTED_POINTER_PENDING",
                      "W9_TORN_GENESIS", "W9_GENESIS_MISMATCH", "OWNER_INPUTS_INSTALLED_EXACT"):
            self.assertNotIn(phase, T.PHASE_TARGETS)

    def test_derive_refusals(self):
        bad = dict(self.encoded, **{"dr5-block": T.encode(self.sets["dr5-block"][:-1])})
        with self.assertRaises(T.TargetError) as caught:
            T.derive(bad)
        self.assertEqual(caught.exception.reason, "BASE_NOT_ACCEPTED:dr5-block")
        twice = {name: T.encode(lines + ([T.STATE_SUBSTITUTION[0]] if name != "predeploy-block" else []))
                 for name, lines in self.sets.items()}
        with self.assertRaises(T.TargetError) as caught:
            T.derive(twice, base_pins={n: (len(T.decode(v)), sha(v)) for n, v in twice.items()}, target_pins=None)
        self.assertEqual(caught.exception.reason, "SUBSTITUTION_SOURCE_NOT_EXACTLY_ONCE")
        allowed = {name: T.encode(lines + ["ALLOWED(unexpected) test -w /opt"]) for name, lines in self.sets.items()}
        with self.assertRaises(T.TargetError) as caught:
            T.derive(allowed, base_pins={n: (len(T.decode(v)), sha(v)) for n, v in allowed.items()}, target_pins=None)
        self.assertTrue(caught.exception.reason.startswith("TARGET_HAS_ALLOWED_OR_FAIL"))

    def test_extraction_rule_equals_the_accepted_m_b6_rule(self):
        import mb6_dr5_target as T6
        text = "".join(f"2026-10-08T00:00:00.0000000Z {line}\n" for line in self.sets["result-set"])
        self.assertEqual(T.extract(text), T6.extract(text))
        self.assertEqual(T.BASE, T6.POST)


# ------------------------------------------------------------------------------ W9 tables and routing ---

class PhaseTableTests(Redacted, unittest.TestCase):
    def test_every_host_phase_has_a_complete_row(self):
        self.assertEqual(set(W.PHASE_TABLE), set(W.HOST_PHASES))
        self.assertEqual(len(W.HOST_PHASES), len(set(W.HOST_PHASES)))
        for phase, (route, reversible, owner_act, note) in W.PHASE_TABLE.items():
            self.assertIn(route, W.ROUTES, phase)
            self.assertIn(reversible, (W.YES, W.NO, W.UNDETERMINED), phase)
            self.assertTrue(owner_act and note, phase)
        for phase in W.LINEAGE_COMMITTED_PHASES:
            self.assertEqual(W.PHASE_TABLE[phase][1], W.NO, phase)
        self.assertEqual(W.PHASE_TABLE[W.W9_MISMATCH][0], W.HALT)
        self.assertEqual(W.PHASE_TABLE[W.W9_TORN][:2], (W.STOP_OWNER_ADJUDICATION, W.UNDETERMINED))
        for phase in (W.FOREIGN, W.LATER_STATE, W.UNCLASSIFIED, W.W9_FAILED, W.W9_ABNORMAL, W.W9_4):
            self.assertEqual(W.PHASE_TABLE[phase][0], W.STOP_OWNER_ADJUDICATION, phase)
        # the Package A W8 reporting defect cannot recur: the exact states have their own explicit SAFE_ADOPT route
        self.assertEqual(W.PHASE_TABLE[W.W9_2][0], W.SAFE_ADOPT)
        self.assertEqual(W.PHASE_TABLE[W.W9_5][0], W.SAFE_ADOPT)

    def test_every_sequence_phase_is_routed(self):
        self.assertEqual(set(W.SEQUENCE_ROUTING), set(W.SEQUENCE_PHASES))
        for phase, (route, note) in W.SEQUENCE_ROUTING.items():
            self.assertIn(route, W.ROUTES, phase)
            self.assertTrue(note)
        self.assertEqual(W.SEQUENCE_ROUTING[W.S9_HALT][0], W.HALT)
        self.assertIn("never an automatic retry", W.SEQUENCE_ROUTING[W.S9B_R][1])
        self.assertIn("B3 is not M-B9b authorization", W.SEQUENCE_ROUTING[W.S9A_ACCEPTED][1])

    def test_removal_restart_and_running_sets_agree(self):
        self.assertEqual(O.REMOVABLE_PHASES, W.REMOVABLE_PHASES)
        self.assertEqual(O.RESTARTABLE_PHASES, W.RESTARTABLE_PHASES)
        self.assertFalse(set(W.REMOVABLE_PHASES) & set(W.LINEAGE_COMMITTED_PHASES))
        self.assertEqual(O.RUNNING_PHASES, (W.W9_2, W.W9_5))
        self.assertEqual(O.W9_PHASE, {"PRE": W.W9_0, "POST9A": W.W9_2, "POST9B": W.W9_5})

    def test_units_parser_and_runtime_classes(self):
        text = ("Id=lilith-recovery-witness.service\nActiveState=active\nSubState=running\nMainPID=42\n\n"
                "Id=lilith-recovery-witness-owner.socket\nActiveState=active\n\n"
                "Id=lilith-recovery-witness-signer.socket\nActiveState=active\n")
        units = W.parse_units(text)
        self.assertEqual(W.runtime_class(units, credentials=True, sockets=(True, True)), "RUNNING")
        self.assertEqual(W.runtime_class(units, credentials=False, sockets=(True, True)), "ABNORMAL")
        stopped = {name: {"ActiveState": "inactive", "SubState": "dead", "MainPID": "0"} for name in W.WITNESS_UNITS}
        self.assertEqual(W.runtime_class(stopped, credentials=False, sockets=(False, False)), "STOPPED")
        self.assertEqual(W.runtime_class(stopped, credentials=True, sockets=(False, False)), "ABNORMAL")
        sockets_only = dict(units, **{W.WITNESS_SERVICE: {"ActiveState": "inactive", "MainPID": "0"}})
        self.assertEqual(W.runtime_class(sockets_only, credentials=False, sockets=(True, True)), "ABNORMAL")
        failed = dict(stopped, **{W.WITNESS_SERVICE: {"ActiveState": "failed", "MainPID": "0"}})
        self.assertEqual(W.runtime_class(failed, credentials=False, sockets=(False, False)), "ABNORMAL")


# ------------------------------------------------------------------------------------ classifiers ---

def p1b9a_report(result="PASS", failures=()):
    return json.dumps({"stage": "P1B-9a", "result": result, "failures": list(failures)}).encode()


def bootstrap_ok(digest=CANDIDATE):
    return json.dumps({"authorityGranted": False, "classification": "CONSISTENT", "genesisDigest": digest,
                       "pinned": True}, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def health_reply(classification="UNINITIALIZED", **changes):
    health = {"profile": "DEV_SYNTHETIC", "environment": "dev", "witnessKeyId": C.ACCEPTED_PINS.kwit_key_id,
              "publicKeySha256": KWIT, "classification": classification, "inputs": [],
              "genericSigning": "NOT_AVAILABLE", "authorityGranted": False}
    health.update(changes)
    return json.dumps({"status": "OK", "health": health}, sort_keys=True, separators=(",", ":")).encode() + b"\n"


class TranscriptTests(Redacted, unittest.TestCase):
    def test_stage_transcript(self):
        cases = ((0, p1b9a_report(), b"", W.STAGE_PASS), (0, p1b9a_report(), b"warning\n", W.FAILED_UNCLASSIFIED),
                 (1, p1b9a_report("FAIL", ["LISTING:x"]), b"", W.STAGE_STATUS_FAIL),
                 (2, b"", b"install_authority_dev: REFUSED PRECONDITION_FAILED:x\n", W.STAGE_REFUSED),
                 (1, b"", b"Traceback (most recent call last):\nFileExistsError\n", W.FAILED_UNCLASSIFIED),
                 (96, b"", b"", W.GUARD_STOPPED), (97, b"", b"", W.GUARD_STOPPED), (255, b"", b"", W.TRANSPORT_FAILED),
                 (None, b"", b"", W.TRANSPORT_FAILED),
                 (0, json.dumps({"stage": "P1B-8", "result": "PASS", "failures": []}).encode(), b"",
                  W.FAILED_UNCLASSIFIED))
        for code, out, err, expected in cases:
            self.assertEqual(W.classify_stage_transcript(code, out, err)[0], expected, (code, out[:20], err[:20]))

    def test_start_transcript_says_only_that_systemd_accepted_the_jobs(self):
        self.assertEqual(W.classify_start_transcript(0, b"", b"")[0], W.START_OK)
        self.assertEqual(W.classify_start_transcript(1, b"", b"Job failed\n")[0], W.START_FAILED)
        self.assertEqual(W.classify_start_transcript(0, b"", b"warning\n")[0], W.START_FAILED)
        self.assertEqual(W.classify_start_transcript(255, b"", b"")[0], W.TRANSPORT_FAILED)
        self.assertEqual(W.classify_start_transcript(None, b"", b"")[0], W.TRANSPORT_FAILED)

    def test_bootstrap_transcript_never_proves_lineage_by_itself(self):
        cls = lambda code, out=b"", err=b"": W.classify_bootstrap_transcript(  # noqa: E731
            code, out, err, candidate_digest=CANDIDATE)[0]
        self.assertEqual(cls(0, bootstrap_ok()), W.BOOTSTRAP_PASS)
        self.assertEqual(cls(0, bootstrap_ok("0" * 64)), W.FAILED_UNCLASSIFIED)        # a different genesis
        self.assertEqual(cls(0, bootstrap_ok(), b"x\n"), W.FAILED_UNCLASSIFIED)
        refused = lambda reason: (b"lilith-recovery-witness-owner-dev: REFUSED " + reason.encode() + b"\n")  # noqa
        for reason in sorted(W.BEFORE_WITNESS_REASONS):
            self.assertEqual(cls(2, b"", refused(reason)), W.BOOTSTRAP_REFUSED_BEFORE_WITNESS, reason)
        self.assertEqual(cls(2, b"", refused("GENESIS_WITNESS_REFUSED")), W.BOOTSTRAP_WITNESS_REFUSED)
        self.assertEqual(cls(2, b"", refused("GENESIS_COMMITTED_NOT_PINNED")), W.BOOTSTRAP_COMMITTED_NOT_PINNED)
        self.assertEqual(cls(2, b"", refused("OSError")), W.BOOTSTRAP_REFUSED_OTHER)
        self.assertEqual(cls(255), W.TRANSPORT_FAILED)
        self.assertEqual(cls(None), W.TRANSPORT_FAILED)
        self.assertEqual(cls(1, b"", b"Traceback\n"), W.FAILED_UNCLASSIFIED)
        # the CLI prints only the reason: a witness-side post-commit STOP is indistinguishable from a pre-sign
        # refusal, so the sequence classifier never trusts this class for lineage absence
        cli = (ROOT / "services/authority-dev/lilith_authority_root/cli.py").read_text(encoding="utf-8")
        self.assertIn('print(f"{name}: REFUSED {exc.reason}", file=sys.stderr)', cli)
        genesis = (ROOT / "services/authority-dev/lilith_authority_root/genesis.py").read_text(encoding="utf-8")
        self.assertIn('raise GenesisToolError("GENESIS_WITNESS_REFUSED"', genesis)

    def test_health_check_binds_the_accepted_kwit_identity(self):
        check = lambda reply, expected="UNINITIALIZED": W.check_health(  # noqa: E731
            reply, expected_classification=expected, kwit_public_key_sha256=KWIT,
            witness_key_id=C.ACCEPTED_PINS.kwit_key_id)
        self.assertTrue(check(health_reply())["exact"])
        self.assertTrue(check(health_reply("CONSISTENT"), "CONSISTENT")["exact"])
        for changes, failure in (({"publicKeySha256": "0" * 64}, "publicKeySha256"),
                                 ({"witnessKeyId": "test-only.witness.other.1"}, "witnessKeyId"),
                                 ({"inputs": ["GENESIS_PIN_COPY_MISSING"]}, "inputsEmpty"),
                                 ({"genericSigning": "AVAILABLE"}, "genericSigningNotAvailable"),
                                 ({"authorityGranted": True}, "authorityNotGranted"),
                                 ({"classification": "CONSISTENT"}, "classification")):
            result = check(health_reply(**changes))
            self.assertFalse(result["exact"])
            self.assertIn(failure, result["failures"])
        self.assertEqual(check(b"not json")["failures"], ["HEALTH_NOT_JSON"])


class SequenceTests(Redacted, unittest.TestCase):
    def seq(self, host, markers=(), **kw):
        return W.classify_sequence(host_phase=host, markers=list(markers), **kw)

    def test_m_b9a_overlay(self):
        m1, m2 = ("mb9a-1",), ("mb9a-1", "mb9a-2")
        self.assertEqual(self.seq(W.W9_0), W.S9_0)
        self.assertEqual(self.seq(W.W9_1), W.UNCLASSIFIED)                    # state outside this sequence
        self.assertEqual(self.seq(W.W9_0, m1), W.UNCLASSIFIED)                # marker without a transcript
        for stage in (W.STAGE_REFUSED, W.STAGE_STATUS_FAIL, W.TRANSPORT_FAILED, W.GUARD_STOPPED):
            self.assertEqual(self.seq(W.W9_0, m1, stage=stage), W.S9A1_R, stage)
        self.assertEqual(self.seq(W.W9_0, m1, stage=W.STAGE_PASS), W.UNCLASSIFIED)
        self.assertEqual(self.seq(W.W9_1P, m1, stage=W.FAILED_UNCLASSIFIED), W.S9A1_PARTIAL)
        self.assertEqual(self.seq(W.W9_1, m1, stage=W.STAGE_PASS), W.S9A1_EXACT)
        self.assertEqual(self.seq(W.W9_1, m1, stage=W.TRANSPORT_FAILED), W.S9A1_INCOMPLETE)
        # stage 9A-2 is never legitimate unless stage 9A-1 was exact
        self.assertEqual(self.seq(W.W9_2, m2, stage=W.TRANSPORT_FAILED, start=W.START_OK), W.UNCLASSIFIED)
        self.assertEqual(self.seq(W.W9_2, ("mb9a-2",), stage=W.STAGE_PASS, start=W.START_OK), W.UNCLASSIFIED)
        ok = dict(stage=W.STAGE_PASS)
        self.assertEqual(self.seq(W.W9_1, m2, start=W.START_FAILED, **ok), W.S9A2_R)
        self.assertEqual(self.seq(W.W9_1, m2, start=W.START_OK, **ok), W.UNCLASSIFIED)
        self.assertEqual(self.seq(W.W9_FAILED, m2, start=W.START_FAILED, **ok), W.S9A2_PARTIAL)
        self.assertEqual(self.seq(W.W9_2, m2, start=W.START_OK, **ok), W.S9A_POST_PENDING)
        self.assertEqual(self.seq(W.W9_2, m2, start=W.TRANSPORT_FAILED, **ok), W.S9A2_INCOMPLETE)   # reply lost
        self.assertEqual(self.seq(W.W9_2, m2, start=W.START_OK, post9a_current=True, **ok), W.S9A_POST_VERIFIED)
        self.assertEqual(self.seq(W.W9_2, m2, start=W.START_OK, post9a_current=True, accepted9a_current=True, **ok),
                         W.S9A_ACCEPTED)
        self.assertEqual(self.seq(W.W9_2, m2, start=W.START_OK, stale9a=True, **ok), W.S9A_STALE)   # new incarnation
        self.assertEqual(self.seq(W.W9_2S, m2, start=W.START_OK, accepted9a_current=False, **ok), W.S9A_STOPPED)
        for later in (W.W9_3, W.W9_4, W.W9_5, W.W9_5S):
            self.assertEqual(self.seq(later, m2, start=W.START_OK, **ok), W.UNCLASSIFIED, later)

    def test_m_b9b_overlay_trusts_the_host_not_the_transcript(self):
        marks = ("mb9a-1", "mb9a-2", "mb9b")
        ok = dict(stage=W.STAGE_PASS, start=W.START_OK)
        self.assertEqual(self.seq(W.W9_2, marks, **ok), W.UNCLASSIFIED)                    # no recorded invocation
        for transcript in (W.BOOTSTRAP_REFUSED_BEFORE_WITNESS, W.BOOTSTRAP_WITNESS_REFUSED, W.TRANSPORT_FAILED,
                           W.FAILED_UNCLASSIFIED, W.BOOTSTRAP_REFUSED_OTHER):
            for host in (W.W9_2, W.W9_3):
                self.assertEqual(self.seq(host, marks, bootstrap=transcript, **ok), W.S9B_R, (host, transcript))
            # the same transcript with a committed host is a committed lineage: never "absent"
            self.assertEqual(self.seq(W.W9_5, marks, bootstrap=transcript, **ok), W.S9B_UNACKNOWLEDGED)
            self.assertEqual(self.seq(W.W9_4, marks, bootstrap=transcript, **ok), W.S9B_POINTER)
        self.assertEqual(self.seq(W.W9_2, marks, bootstrap=W.BOOTSTRAP_PASS, **ok), W.UNCLASSIFIED)  # contradiction
        self.assertEqual(self.seq(W.W9_5, marks, bootstrap=W.BOOTSTRAP_PASS, **ok), W.S9B_POST_PENDING)
        self.assertEqual(self.seq(W.W9_5, marks, bootstrap=W.BOOTSTRAP_PASS, post9b=True, **ok), W.S9B_POST_VERIFIED)
        self.assertEqual(self.seq(W.W9_5, marks, bootstrap=W.TRANSPORT_FAILED, post9b=True, **ok),
                         W.S9B_ADOPTION_PENDING)
        self.assertEqual(self.seq(W.W9_5S, marks, bootstrap=W.BOOTSTRAP_PASS, **ok), W.S9B_STOPPED)
        self.assertEqual(self.seq(W.W9_MISMATCH, marks, bootstrap=W.BOOTSTRAP_COMMITTED_NOT_PINNED, **ok), W.S9_HALT)
        self.assertEqual(self.seq(W.W9_MISMATCH), W.S9_HALT)
        for stop in (W.W9_TORN, W.LATER_STATE, W.FOREIGN, W.UNCLASSIFIED):
            self.assertEqual(self.seq(stop, marks, bootstrap=W.BOOTSTRAP_PASS, **ok), stop)
        self.assertEqual(self.seq(W.W9_5, ("mb9b",), bootstrap=W.BOOTSTRAP_PASS), W.UNCLASSIFIED)  # out of order
        self.assertEqual(self.seq(W.W9_5, ("mb9z",)), W.UNCLASSIFIED)

    def test_every_sequence_phase_is_reachable(self):
        reached = set()
        hosts = W.HOST_PHASES
        stages = W.STAGE_CLASSES
        for host in hosts:
            for marks in ((), ("mb9a-1",), ("mb9a-1", "mb9a-2"), ("mb9a-1", "mb9a-2", "mb9b")):
                for stage in stages:
                    for start in W.START_CLASSES:
                        for boot in (W.NOT_INVOKED, W.BOOTSTRAP_PASS, W.TRANSPORT_FAILED):
                            for flags in ({}, {"post9a_current": True}, {"accepted9a_current": True},
                                          {"stale9a": True}, {"post9b": True}):
                                reached.add(self.seq(host, marks, stage=stage, start=start, bootstrap=boot, **flags))
        self.assertEqual(reached, set(W.SEQUENCE_PHASES))


# ------------------------------------------------------------------------------ witness denial proof ---

def _st(kind: int, mode: int, uid=0, gid=0, nlink=1):
    return os.stat_result((kind | mode, 1, 1, nlink, uid, gid, 10, 0, 0, 0))


WIT, SIGNER_UID, SVC = 991, 990, 980


def denial_fs(phase: str) -> dict:
    files = {
        DP.WITNESS_STATE: _st(stat.S_IFDIR, 0o2750, WIT, SVC), DP.LOCK: _st(stat.S_IFREG, 0o640, WIT, SVC),
        DP.AUTHORITY_STATE: _st(stat.S_IFDIR, 0o700, SIGNER_UID, SVC), DP.LEDGER: _st(stat.S_IFREG, 0o600, SIGNER_UID, SVC),
        DP.OWNER_INPUT_DIR: _st(stat.S_IFDIR, 0o755), DP.PIN_COPY: _st(stat.S_IFREG, 0o644),
        DP.REGISTER_COPY: _st(stat.S_IFREG, 0o644), DP.RUNTIME: _st(stat.S_IFDIR, 0o710, 0, SVC),
        DP.OWNER_SOCKET: _st(stat.S_IFSOCK, 0o600), DP.SIGNER_SOCKET: _st(stat.S_IFSOCK, 0o660, WIT, SVC),
        DP.CREDENTIALS: _st(stat.S_IFDIR, 0o500, WIT, WIT),
    }
    if phase == "P1B-9b":
        files.update({DP.CHAIN: _st(stat.S_IFDIR, 0o2750, WIT, SVC), DP.AUTHORIZATIONS: _st(stat.S_IFDIR, 0o2750, WIT, SVC),
                      DP.GENESIS: _st(stat.S_IFREG, 0o640, WIT, SVC), DP.POINTER: _st(stat.S_IFREG, 0o640, WIT, SVC)})
    return files


def denial_listing(phase: str) -> dict:
    return {DP.WITNESS_STATE: DP.STATE_ENTRIES[phase], DP.AUTHORITY_STATE: [DP.LEDGER_NAME],
            DP.OWNER_INPUT_DIR: ["authorization-register.json", "genesis-pin.json"], DP.CHAIN: ["1.json"],
            DP.AUTHORIZATIONS: []}


def realistic_probe(argv) -> int:
    """`runuser -u <p> -- test <op> <path>`: 0 only for the explicit by-design rows (the real modes)."""
    principal, op, path = argv[2], argv[5], argv[6]
    for _first, row_op, row_path, _denied, by_design in DP.ROWS:
        if (row_op, row_path) == (op, path) and principal in by_design:
            return 0
    return 1


class WitnessDenialProofTests(Redacted, unittest.TestCase):
    def prove(self, phase="P1B-9a", *, run=realistic_probe, files=None, listing=None, units=None, activation=None):
        lines: list[str] = []
        files = files if files is not None else denial_fs(phase)
        listing = listing if listing is not None else denial_listing(phase)
        units = units or {**dict.fromkeys(DP.WITNESS_UNITS, "active"), **dict.fromkeys(DP.SIGNER_UNITS, "inactive")}
        ok = DP.prove(phase, run=run, lstat=files.get, listdir=lambda p: listing[p],
                      ids=lambda: {"witness": WIT, "signer": SIGNER_UID, "signerGid": SVC, "witnessGid": WIT},
                      unit_state=units.get,
                      activation=activation or (lambda: (1, DP.GRANT_ABSENT + " advisoryConfigEnabled=False\n")),
                      euid=lambda: 0, say=lines.append)
        return ok, lines

    def test_pass_transcripts_and_derived_counts_are_pinned(self):
        for phase, (denied, by_design, total) in {"P1B-9a": (91, 5, 107), "P1B-9b": (125, 11, 148)}.items():
            ok, lines = self.prove(phase)
            self.assertTrue(ok, lines[-3:])
            self.assertEqual(DP.expected_counts(phase), (denied, by_design))
            self.assertEqual(sum(line.startswith("DENIED: ") for line in lines), denied)
            self.assertEqual(sum(line.startswith("ALLOWED_BY_DESIGN: ") for line in lines), by_design)
            self.assertEqual(len(lines), total)
            self.assertEqual(lines[-1], f"MB9_WITNESS_DENIAL_PROOF=PASS phase={phase} denied={denied} "
                                        f"allowed_by_design={by_design} allowed=0")
            self.assertEqual(self.prove(phase)[1], lines)                       # deterministic
            self.assertFalse(any(re.search(r"\d{4}-\d\d-\d\dT", line) for line in lines))

    def test_allowed_by_design_rows_are_explicit_and_signer_only(self):
        rows = [(op, path, tuple(by)) for _f, op, path, _d, by in DP.ROWS if by]
        self.assertEqual(rows, [
            ("-r", DP.WITNESS_STATE, (DP.SIGNER,)), ("-x", DP.WITNESS_STATE, (DP.SIGNER,)), ("-r", DP.LOCK, (DP.SIGNER,)),
            ("-r", DP.CHAIN, (DP.SIGNER,)), ("-x", DP.CHAIN, (DP.SIGNER,)), ("-r", DP.GENESIS, (DP.SIGNER,)),
            ("-r", DP.POINTER, (DP.SIGNER,)), ("-r", DP.AUTHORIZATIONS, (DP.SIGNER,)),
            ("-x", DP.AUTHORIZATIONS, (DP.SIGNER,)), ("-x", DP.RUNTIME, (DP.SIGNER,)),
            ("-w", DP.SIGNER_SOCKET, (DP.SIGNER,))])
        for _first, op, path, denied, by_design in DP.ROWS:
            self.assertFalse(set(denied) & set(by_design), path)
            if op == "-w" and path.startswith(DP.WITNESS_STATE):
                self.assertIn(DP.SIGNER, denied)                                  # no non-witness write, ever
            if path in (DP.WITNESS_STATE, DP.LOCK, DP.CHAIN, DP.GENESIS, DP.POINTER, DP.AUTHORIZATIONS):
                self.assertTrue(set(DP.OUTSIDERS) <= set(denied), path)
        self.assertEqual([denied for _f, op, path, denied, _b in DP.ROWS if path == DP.OWNER_SOCKET], [DP.EVERYONE])

    def test_witness_is_denied_mutation_of_ledger_owner_inputs_trust_registry_and_kwit(self):
        for path in (DP.AUTHORITY_STATE, DP.LEDGER, DP.PIN_COPY, DP.REGISTER_COPY, DP.ROOT_ANCHOR, DP.WITNESS_ANCHOR,
                     DP.REGISTRY_V1, DP.KWIT_BLOB):
            writes = [denied for _f, op, row_path, denied, _b in DP.ROWS if row_path == path and op == "-w"]
            self.assertEqual(len(writes), 1, path)
            self.assertIn(DP.WITNESS, writes[0], path)
        self.assertIn(DP.WITNESS, [d for _f, op, p, d, _b in DP.ROWS if p == DP.KWIT_BLOB and op == "-r"][0])

    def test_p1b6_and_p1b8_rows_are_recovered_with_the_witness_active(self):
        import mb6_ledger_denial_proof as P6
        import mb8_owner_input_denial_proof as P8
        mine = {(op, path): set(denied) for _f, op, path, denied, _b in DP.ROWS}
        for op, path in P6.ROWS:
            self.assertEqual(mine[(op, path)], set(P6.PRINCIPALS), (op, path))
        for op, path in P8.ROWS:
            self.assertEqual(mine[(op, path)], set(P8.PRINCIPALS), (op, path))

    def test_failures(self):
        allowed = lambda argv: 0 if argv[2] == DP.APPLICATION else realistic_probe(argv)  # noqa: E731
        ok, lines = self.prove(run=allowed)
        self.assertFalse(ok)
        self.assertTrue(any(line.startswith("FAIL: ALLOWED(unexpected) lilith") for line in lines))
        denied_by_design = lambda argv: 1  # noqa: E731
        ok, lines = self.prove(run=denied_by_design)
        self.assertFalse(ok)
        self.assertTrue(any(line.startswith("FAIL: BY_DESIGN_ACCESS_DENIED lilith-authority-dev") for line in lines))
        self.assertFalse(self.prove(run=lambda argv: 2)[0])
        stopped = {**dict.fromkeys(DP.WITNESS_UNITS, "inactive"), **dict.fromkeys(DP.SIGNER_UNITS, "inactive")}
        self.assertFalse(self.prove(units=stopped)[0])
        signer = {**dict.fromkeys(DP.WITNESS_UNITS, "active"), **dict.fromkeys(DP.SIGNER_UNITS, "active")}
        self.assertFalse(self.prove(units=signer)[0])
        self.assertFalse(self.prove(activation=lambda: (0, "ACTIVATION=ACCEPTED {}\n"))[0])
        self.assertFalse(self.prove("P1B-9b", listing=denial_listing("P1B-9a"))[0])
        two = dict(denial_listing("P1B-9b"), **{DP.CHAIN: ["1.json", "2.json"]})
        self.assertFalse(self.prove("P1B-9b", listing=two)[0])
        wrong = dict(denial_fs("P1B-9a"), **{DP.LOCK: _st(stat.S_IFREG, 0o664, WIT, SVC)})
        ok, lines = self.prove(files=wrong)
        self.assertFalse(ok)
        self.assertIn("probes=0", lines[-1])
        self.assertFalse(DP.prove("P1B-9c", euid=lambda: 0, say=lambda _: None))
        self.assertFalse(DP.prove("P1B-9a", euid=lambda: 1000, say=lambda _: None))

    def test_p1b6_and_p1b8_are_out_of_phase_once_the_witness_runs_and_p1b5_is_not(self):
        import mb6_ledger_denial_proof as P6
        import mb8_owner_input_denial_proof as P8
        self.assertIn("lilith-recovery-witness.service", P6.UNITS)
        self.assertIn("lilith-recovery-witness.service", P8.UNITS)
        lines: list[str] = []
        files = {P8.OWNER_INPUT_DIR: _st(stat.S_IFDIR, 0o755), **{p: _st(stat.S_IFREG, 0o644) for p in P8.COPIES}}
        ok = P8.prove("P1B-8", run=lambda argv: 1, lstat=files.get, listdir=lambda p: sorted((P8.PIN_NAME, P8.REGISTER_NAME)),
                      unit_state=lambda u: "active" if "recovery-witness" in u else "inactive",
                      activation=lambda: (1, P8.GRANT_ABSENT + " advisoryConfigEnabled=False\n"), euid=lambda: 0,
                      say=lines.append)
        self.assertFalse(ok)
        self.assertIn("FAIL: UNIT_NOT_INACTIVE lilith-recovery-witness.service", lines)
        self.assertIn("reason=PRECONDITION probes=0", lines[-1])
        custody = (ROOT / O.DENIAL).read_text(encoding="utf-8")
        self.assertNotIn("UNIT_NOT_INACTIVE", custody)                       # P1B-5 has no unit precondition
        if not POSIX:
            self.skipTest("the pinned P1B-5 proof needs os.geteuid at import")
        spec = importlib.util.spec_from_file_location("p1b5_custody_proof_mb9", ROOT / O.DENIAL)
        P5 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(P5)
        package_b_objects = ("/var/lib/lilith-recovery-witness", "/run/lilith-recovery-witness",
                             "/run/credentials/lilith-recovery-witness.service")
        witness_rows = [row for row in P5.ROWS if row[3].startswith(package_b_objects)]
        self.assertTrue(witness_rows)
        self.assertTrue(all(row[0] == "P1B-12" for row in witness_rows))   # deferred: constant across Package B


# ------------------------------------------------------------------------- the operator (fake transport) ---

class FakeRun:
    """git reads the worktree; ssh answers by command shape. Records every argv."""

    def __init__(self, *, w9=("W9_0_PRE_WITNESS", "W9_1_STATE_DIR_ONLY", "W9_2_STARTED_UNINITIALIZED"),
                 stage=(0, p1b9a_report(), b""), start=(0, b"", b""), health=None, boot=None,
                 invocation=INVOCATION, mainpid=MAINPID):
        self.calls: list[list[str]] = []
        self.w9 = list(w9)
        self.stage, self.start, self.health = stage, start, health or (0, health_reply(), b"")
        self.boot = boot or (0, bootstrap_ok(), b"")
        self.invocation, self.mainpid = invocation, mainpid

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
        if "mb9_witness_verifier" in command:
            phase = self.w9.pop(0) if len(self.w9) > 1 else self.w9[0]
            report = {"phase": phase, "witnessInvocationId": self.invocation, "witnessMainPid": self.mainpid,
                      "witnessNRestarts": "0", "evidence9a": dict.fromkeys(W.EVIDENCE_9A, True),
                      "routing": W.PHASE_TABLE[phase][0], "store": {"listing": ["witness.lock"], "chain": {}},
                      "runtime": "RUNNING" if phase in O.RUNNING_PHASES else "STOPPED",
                      "storeClassification": "UNINITIALIZED", "committedGenesis": {}}
            rc = 0 if f"expect {phase}" in command or " observe " in command else 1
            return done(rc, json.dumps(report).encode())
        if "witness-state" in command:
            return done(*self.stage)
        if "systemctl start" in command:
            return done(*self.start)
        if "owner-dev health" in command:
            return done(*self.health)
        if "bootstrap 1" in command:
            return done(*self.boot)
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

    def values(self, **overrides):
        values = dict(control=CONTROL, operator=self.operator_sha, candidate=self.c["candidate"], pin=self.c["pin"],
                      register=self.c["register"], record=self.c["record"], updated_at=UPDATED_AT,
                      invocation=INVOCATION, mainpid=MAINPID, post9a="")
        values.update(overrides)
        return values

    def open(self, op):
        return op.open_sequence(ROOT, self.work, self.text(O.SEQUENCE_LINES, **self.values()))

    def remote_with(self, run, needle):
        return [c for c in run.remote() if needle in c]

    def test_open_sequence_is_read_only_and_bound(self):
        run = FakeRun()
        op = O.Operator(gcloud=("gcloud",), run=run)
        with self.assertRaises(O.Stop):
            op.open_sequence(ROOT, self.work, self.text(O.SEQUENCE_LINES, **self.values(candidate="0" * 64)))
        self.assertEqual(self.open(op)["result"], "PACKAGE_B_SEQUENCE_OPENED_READ_ONLY")
        with self.assertRaises(O.Stop) as caught:
            self.open(op)
        self.assertEqual(caught.exception.code, "SEQUENCE_ALREADY_OPENED")
        self.assertEqual(run.remote(), [])                                       # nothing reached DEV

    def test_mb9a_refuses_before_any_marker(self):
        run = FakeRun()
        op = O.Operator(gcloud=("gcloud",), run=run)
        go = self.text(O.MB9A_GO_LINES, **self.values())
        with self.assertRaises(O.Stop) as caught:
            op.mb9a(ROOT, self.work, go)
        self.assertEqual(caught.exception.code, "SEQUENCE_NOT_OPENED")
        self.open(op)
        for bad in (dict(candidate="0" * 64), dict(pin="0" * 64), dict(operator="0" * 64), dict(control="0" * 40)):
            with self.assertRaises(O.Stop) as caught:
                op.mb9a(ROOT, self.work, self.text(O.MB9A_GO_LINES, **self.values(**bad)))
            self.assertEqual(caught.exception.code, "GO_LINE_MISSING", bad)
        stop = O.Operator(gcloud=("gcloud",), run=FakeRun(w9=("W9_1_STATE_DIR_ONLY",)))
        with self.assertRaises(O.Stop) as caught:
            stop.mb9a(ROOT, self.work, go)
        self.assertEqual(caught.exception.code, "PRE_STATE_NOT_W9_0")
        self.assertFalse((self.work / "attempts").exists())                      # nothing consumed
        self.assertFalse(self.remote_with(run, "witness-state"))

    def test_mb9a_two_markers_in_order_each_one_invocation(self):
        run = FakeRun()
        op = O.Operator(gcloud=("gcloud",), run=run)
        self.open(op)
        result = op.mb9a(ROOT, self.work, self.text(O.MB9A_GO_LINES, **self.values()))
        self.assertEqual(result["result"], "MB9A_STARTED", result)
        self.assertEqual((result["invocationId"], result["mainPid"]), (INVOCATION, MAINPID))
        stage, start = self.remote_with(run, "witness-state"), self.remote_with(run, "systemctl start")
        self.assertEqual((len(stage), len(start)), (1, 1))
        self.assertIn(f"witness-state {O.RELEASE_SHA}", stage[0])
        self.assertIn(O.START_COMMAND, start[0])
        commands = run.remote()
        self.assertLess(commands.index(stage[0]), commands.index(start[0]))
        self.assertEqual(len(self.remote_with(run, "owner-dev health")), 1)
        self.assertLess(commands.index(start[0]), commands.index(self.remote_with(run, "owner-dev health")[0]))
        markers = sorted(p.name for p in (self.work / "attempts").glob("mb9a-?.json"))
        self.assertEqual(markers, ["mb9a-1.json", "mb9a-2.json"])
        with self.assertRaises(O.Stop) as caught:
            op.mb9a(ROOT, self.work, self.text(O.MB9A_GO_LINES, **self.values()))
        self.assertEqual(caught.exception.code, "ATTEMPT_ALREADY_CONSUMED:mb9a-1")
        self.assertEqual(len(self.remote_with(run, "witness-state")), 1)

    def test_no_second_stage_when_the_first_is_not_exact(self):
        cases = (FakeRun(stage=(255, b"", b"ssh: lost\n"), w9=("W9_0_PRE_WITNESS", "W9_1_STATE_DIR_ONLY")),
                 FakeRun(w9=("W9_0_PRE_WITNESS", "W9_1P_STATE_DIR_PARTIAL")),
                 FakeRun(stage=(2, b"", b"install_authority_dev: REFUSED PRECONDITION_FAILED:x\n"),
                         w9=("W9_0_PRE_WITNESS",)))
        for run in cases:
            with self.subTest(run.stage[0]):
                work = Path(tempfile.mkdtemp(dir=self.tmp.name))
                C.write_emitted(synthetic_derivation(), work / "genesis")
                op = O.Operator(gcloud=("gcloud",), run=run)
                op.open_sequence(ROOT, work, self.text(O.SEQUENCE_LINES, **self.values()))
                result = op.mb9a(ROOT, work, self.text(O.MB9A_GO_LINES, **self.values()))
                self.assertEqual((result["result"], result["stage2"]), ("MB9A_STOP_AFTER_STAGE_1", "NOT_RUN"))
                self.assertFalse((work / "attempts" / "mb9a-2.json").exists())
                self.assertFalse(self.remote_with(run, "systemctl start"))
                self.assertFalse(self.remote_with(run, "owner-dev health"))
                self.assertEqual(len(self.remote_with(run, "witness-state")), 1)   # consumed, never retried

    def test_health_is_never_requested_unless_observed_running(self):
        run = FakeRun(start=(1, b"", b"Job failed\n"), w9=("W9_0_PRE_WITNESS", "W9_1_STATE_DIR_ONLY", "W9_FAILED_START"))
        op = O.Operator(gcloud=("gcloud",), run=run)
        self.open(op)
        result = op.mb9a(ROOT, self.work, self.text(O.MB9A_GO_LINES, **self.values()))
        self.assertEqual((result["result"], result["hostPhase"]), ("MB9A_STOP", "W9_FAILED_START"))
        self.assertFalse(self.remote_with(run, "owner-dev health"))
        with self.assertRaises(O.Stop) as caught:
            O.Operator(gcloud=("gcloud",), run=FakeRun(w9=("W9_2S_STOPPED_UNINITIALIZED",))).health(
                ROOT, self.work, Path(self.tmp.name) / "h")
        self.assertEqual(caught.exception.code, "WITNESS_NOT_RUNNING_NO_SOCKET_CONTACT")

    def ready_for_mb9b(self, op, run):
        self.open(op)
        op.mb9a(ROOT, self.work, self.text(O.MB9A_GO_LINES, **self.values()))
        post = self.work / "post9a-1"
        post.mkdir()
        data = O.Operator._record(post / "POST9A_VERIFIED.json", {"invocationId": INVOCATION, "mainPid": MAINPID})
        statement = self.text(O.WITNESS_STARTED_LINES, **self.values(post9a=sha(data)))
        self.assertEqual(op.accept_9a(self.work, statement)["result"], "WITNESS_STARTED_OWNER_ACCEPTANCE_RECORDED")
        run.w9 = ["W9_2_STARTED_UNINITIALIZED", "W9_5_GENESIS_COMMITTED_EXACT"]
        return sha(data)

    def test_mb9b_binds_the_accepted_incarnation_and_the_ponr_acknowledgement(self):
        run = FakeRun(boot=(0, bootstrap_ok(self.c["candidate"]), b""))
        op = O.Operator(gcloud=("gcloud",), run=run)
        post9a = self.ready_for_mb9b(op, run)
        without_ponr = [line for line in O.MB9B_GO_LINES if line != O.PONR_ACKNOWLEDGEMENT]
        with self.assertRaises(O.Stop) as caught:
            op.mb9b(ROOT, self.work, self.text(without_ponr, **self.values(post9a=post9a)))
        self.assertEqual(caught.exception.code, "GO_LINE_MISSING")
        run.w9 = ["W9_2_STARTED_UNINITIALIZED"]
        run.invocation = "f" * 32                                                 # a restarted witness
        with self.assertRaises(O.Stop) as caught:
            op.mb9b(ROOT, self.work, self.text(O.MB9B_GO_LINES, **self.values(post9a=post9a)))
        self.assertEqual(caught.exception.code, "WITNESS_INCARNATION_CHANGED_OR_NOT_ACCEPTED")
        self.assertFalse((self.work / "attempts" / "mb9b.json").exists())
        self.assertFalse(self.remote_with(run, "bootstrap 1"))
        run.invocation, run.w9 = INVOCATION, ["W9_2_STARTED_UNINITIALIZED", "W9_5_GENESIS_COMMITTED_EXACT"]
        result = op.mb9b(ROOT, self.work, self.text(O.MB9B_GO_LINES, **self.values(post9a=post9a)))
        self.assertEqual((result["result"], result["transcript"]), ("MB9B_COMMITTED", W.BOOTSTRAP_PASS))
        boots = self.remote_with(run, "bootstrap 1")
        self.assertEqual(len(boots), 1)
        self.assertIn(f"sudo -n {O.OWNER_CLI} bootstrap 1 {UPDATED_AT}", boots[0])
        with self.assertRaises(O.Stop) as caught:
            op.mb9b(ROOT, self.work, self.text(O.MB9B_GO_LINES, **self.values(post9a=post9a)))
        self.assertEqual(caught.exception.code, "ATTEMPT_ALREADY_CONSUMED:mb9b")
        self.assertEqual(len(self.remote_with(run, "bootstrap 1")), 1)

    def test_a_failure_after_the_mb9b_marker_is_recorded_not_retried(self):
        run = FakeRun(boot=(255, b"", b"ssh: connection lost\n"))
        op = O.Operator(gcloud=("gcloud",), run=run)
        post9a = self.ready_for_mb9b(op, run)
        run.w9 = ["W9_2_STARTED_UNINITIALIZED", "W9_5_GENESIS_COMMITTED_EXACT"]
        result = op.mb9b(ROOT, self.work, self.text(O.MB9B_GO_LINES, **self.values(post9a=post9a)))
        self.assertEqual((result["result"], result["transcript"], result["attempt"], result["hostPhase"]),
                         ("MB9B_STOP", W.TRANSPORT_FAILED, "CONSUMED", "W9_5_GENESIS_COMMITTED_EXACT"))
        self.assertEqual(len(self.remote_with(run, "bootstrap 1")), 1)
        verifier = O._verifier_module(ROOT)
        records = op._records(self.work, {"witnessInvocationId": INVOCATION, "witnessMainPid": MAINPID}, verifier)
        self.assertEqual(verifier.classify_sequence(host_phase="W9_5_GENESIS_COMMITTED_EXACT", **records),
                         W.S9B_UNACKNOWLEDGED)                                    # committed, never "absent"
        timeout = FakeRun()
        timeout_op = O.Operator(gcloud=("gcloud",), run=timeout)
        work = self.work
        self.work = Path(tempfile.mkdtemp(dir=self.tmp.name))
        C.write_emitted(synthetic_derivation(), self.work / "genesis")
        post9a = self.ready_for_mb9b(timeout_op, timeout)

        def raise_timeout(command):
            if "bootstrap 1" in command:
                raise subprocess.TimeoutExpired(command, 900)
            return M6.Operator.ssh(timeout_op, command)
        with mock.patch.object(timeout_op, "ssh", raise_timeout):
            result = timeout_op.mb9b(ROOT, self.work, self.text(O.MB9B_GO_LINES, **self.values(post9a=post9a)))
        self.assertEqual(result["transcript"], W.TRANSPORT_FAILED)
        self.work = work

    def test_accept_9a_needs_a_matching_post_and_records_once(self):
        op = O.Operator(gcloud=("gcloud",), run=FakeRun())
        with self.assertRaises(O.Stop) as caught:
            op.accept_9a(self.work, self.text(O.WITNESS_STARTED_LINES, **self.values(post9a="0" * 64)))
        self.assertEqual(caught.exception.code, "NO_POST9A_MATCHES_STATEMENT")

    def test_owner_texts_are_separate_and_bounded(self):
        joined = flat(" ".join(O.SEQUENCE_LINES))
        self.assertIn("read-only evidence only", joined)
        self.assertIn("E-A18 was completed and owner-recorded before this act", joined)
        self.assertNotIn("I authorize M-B9a", joined)
        go = flat(" ".join(O.MB9A_GO_LINES))
        for phrase in ("exactly one attempt", "marker mb9a-1", "marker mb9a-2", "only after stage 9A-1 is exact",
                       "no enable and no daemon-reload", "does not authorize BOOTSTRAP, M-B9b",
                       "does not accept WITNESS_STARTED", "stage 9A-2 never runs unless stage 9A-1 is exact",
                       "OWNER_REGISTER = KNOWN_EMPTY", "P1B-5, P1B-6 and P1B-8 denial proofs passed"):
            self.assertIn(phrase, go)
        b3 = flat(" ".join(O.WITNESS_STARTED_LINES))
        self.assertIn("It is not M-B9b authorization", b3)
        self.assertIn("{invocation}", b3)
        b4 = flat(" ".join(O.MB9B_GO_LINES))
        for phrase in (O.PONR_ACKNOWLEDGEMENT, "REBOOTSTRAP_FORBIDDEN", "exactly one invocation",
                       "previousWitnessDigest null", "consumedAuthorizationId null", "the witness has run continuously",
                       "does not accept WITNESS_GENESIS_COMMITTED", "There is no automatic retry", "{invocation}",
                       "{mainpid}", "{post9a}", "after WITNESS_STARTED"):
            self.assertIn(phrase, b4)
        self.assertEqual(O.PONR_ACKNOWLEDGEMENT,
                         "I understand that the witness lineage becomes irreversible at the canonical chain-directory "
                         "fsync commit point and that no second witness genesis or automatic retry is authorized after "
                         "that point.")
        b5 = flat(" ".join(O.PACKAGE_B_ACCEPTANCE_LINES))
        self.assertIn("This acceptance authorizes nothing further", b5)
        self.assertIn("freeze ends now", b5)
        self.assertIn("removes no lineage", flat(" ".join(O.REMOVAL_LINES)))
        self.assertIn("a fresh POST is required", flat(" ".join(O.RESTART_LINES)))

    def test_source_has_only_the_reviewed_mutation_paths(self):
        source = Path(O.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        prose = set()                                       # owner texts and docstrings are prose, not commands
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and (t.id.endswith("_LINES") or t.id in (
                    "PONR_ACKNOWLEDGEMENT", "USAGE")) for t in node.targets):
                prose |= {id(n) for n in ast.walk(node.value) if isinstance(n, ast.Constant)}
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and ast.get_docstring(node) is not None:
                prose.add(id(node.body[0].value))
        strings = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)
                   and isinstance(node.value, str) and id(node) not in prose]
        commands = " ".join(s for s in strings if "sudo" in s or "systemctl" in s)
        for forbidden in ("systemctl enable", "systemctl stop", "systemctl restart", "daemon-reload", "reset-failed",
                          "execute-head-advance", "execute-epoch-advance", "create-initial-held",
                          "lilith-authority-hold-dev", "lilith-authority-ledger-dev", "provision",
                          "lilith-authority-recovery-dev", "start lilith-authority-dev", "advance-epoch",
                          "systemd-creds", "keygen", "append", "first-memory", "first_memory", "activation-grant"):
            self.assertNotIn(forbidden, commands, forbidden)
        # the only start is START_COMMAND, and it names exactly the three witness units (sockets first)
        self.assertEqual(commands.count("systemctl start"), O.START_COMMAND.count("systemctl start"))
        self.assertEqual(O.START_COMMAND, "sudo -n /usr/bin/systemctl start lilith-recovery-witness-owner.socket "
                                          "lilith-recovery-witness-signer.socket && sudo -n /usr/bin/systemctl start "
                                          "lilith-recovery-witness.service")
        self.assertEqual(source.count('f"witness-state {RELEASE_SHA}"'), 1)
        self.assertEqual(source.count("self._invoke(START_COMMAND)"), 2)            # 9A-2 and the authorized restart
        self.assertEqual(source.count('bootstrap 1 {c[\'updated_at\']}"'), 1)
        self.assertEqual(source.count('" remove {digest}"') + source.count('f"remove {digest}"'), 1)

    def test_verifier_never_contacts_a_socket(self):
        source = Path(W.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {alias.name for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
                    for alias in node.names} | {node.module for node in ast.walk(tree)
                                                 if isinstance(node, ast.ImportFrom) and node.module}
        self.assertNotIn("socket", imported)
        self.assertNotIn("lilith_authority_root.clients", imported)
        self.assertNotIn("clients", imported)
        calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute)}
        self.assertFalse(calls & {"connect", "connect_ex", "sendall", "witness_owner", "witness_signer"})

    def test_dr5_form_is_bound_to_a_verified_w9_phase(self):
        op = O.Operator(gcloud=("gcloud",), run=FakeRun())
        log = Path(self.tmp.name) / "deploy.log"
        derived = T.derive({name: T.encode(lines) for name, lines in fixture_sets().items()})
        log.write_text("".join(f"2026-10-08T00:00:00.0000000Z {line}\n"
                               for line in derived["targets"][T.RUNNING]["texts"]["result-set"]), encoding="utf-8")
        self.assertEqual(op.dr5(ROOT, "W9_5_GENESIS_COMMITTED_EXACT", log)["result"], "EQUAL")
        for phase in ("W9_4_COMMITTED_POINTER_PENDING", "OWNER_INPUTS_INSTALLED_EXACT", "UNCLASSIFIED_STOP"):
            with self.assertRaises(O.Stop) as caught:
                op.dr5(ROOT, phase, log)
            self.assertTrue(caught.exception.code.startswith("NO_BASELINE_STOP"), phase)

    def test_removal_and_restart_bind_their_plan_digest(self):
        run = FakeRun(w9=("W9_2S_STOPPED_UNINITIALIZED",))
        op = O.Operator(gcloud=("gcloud",), run=run)
        plan = op.restart_plan(ROOT, self.work, Path(self.tmp.name) / "rp")
        self.assertTrue(plan["restartable"])
        bad = self.text(O.RESTART_LINES, plan="0" * 64, phase="W9_2S_STOPPED_UNINITIALIZED")
        with self.assertRaises(O.Stop) as caught:
            op.restart(ROOT, self.work, Path(self.tmp.name) / "rp", bad)
        self.assertEqual(caught.exception.code, "GO_LINE_MISSING")
        good = self.text(O.RESTART_LINES, plan=plan["planDigest"], phase="W9_2S_STOPPED_UNINITIALIZED")
        run.w9 = ["W9_3_PRECOMMIT_DIRS"]                                           # the host changed since the plan
        with self.assertRaises(O.Stop) as caught:
            op.restart(ROOT, self.work, Path(self.tmp.name) / "rp", good)
        self.assertEqual(caught.exception.code, "PLAN_CHANGED")
        self.assertFalse(self.remote_with(run, "systemctl start"))
        run.w9 = ["W9_2S_STOPPED_UNINITIALIZED", "W9_2_STARTED_UNINITIALIZED"]
        result = op.restart(ROOT, self.work, Path(self.tmp.name) / "rp", good)
        self.assertEqual(result["result"], "MB9_WITNESS_RESTARTED")
        self.assertEqual(len(self.remote_with(run, "systemctl start")), 1)
        with self.assertRaises(O.Stop):
            op.restart(ROOT, self.work, Path(self.tmp.name) / "rp", good)          # one start per plan
        running = O.Operator(gcloud=("gcloud",), run=FakeRun(w9=("W9_2_STARTED_UNINITIALIZED",)))
        self.assertFalse(running.restart_plan(ROOT, self.work, Path(self.tmp.name) / "rp2")["restartable"])
        self.assertFalse(set(O.RESTARTABLE_PHASES) & set(O.RUNNING_PHASES))     # never a stop of a running witness


# --------------------------------------------------------------------------- synthetic host (crypto) ---

if HAVE_CRYPTO and POSIX:
    import install_authority_dev as I
    import mb4_mb5_trust_install_verifier as V5
    import mb6_ledger_verifier as V6
    import mb8_owner_input_verifier as V8
    import test_b1b3e_mb6_ledger_remediation as T6
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from lilith_authority_host import inputs as HI
    from lilith_authority_host import paths as P
    from lilith_authority_root import genesis as G
    from lilith_owner_memory import witness_readiness as WR
    from lilith_recovery_witness import writer as WRITER
    from lilith_recovery_witness.credential import WitnessSigningKeyV1
    from lilith_recovery_witness.storage import FilesystemWitnessStorageV1
    from test_b1b3e_mb4_mb5_installable_inputs import P as WP
    _Base = T6.Mb6Base
else:  # pragma: no cover - the stdlib layer still runs
    _Base = unittest.TestCase


class Crash(Exception):
    """A simulated process death at one writer fault point."""


def _no_socket(*_a, **_k):
    raise AssertionError("the W9 verifier opened a socket")


@unittest.skipUnless(HAVE_CRYPTO and POSIX and hasattr(__import__("sqlite3").Connection, "deserialize"),
                     "POSIX owner/mode semantics, sqlite3 deserialize, cryptography/rfc8785/fido2 required")
class WitnessHostTests(_Base):
    @classmethod
    def setUpClass(cls):
        keys = []
        original = Ed25519PrivateKey.generate

        def capture():
            key = original()
            keys.append(key)
            return key
        with mock.patch.object(Ed25519PrivateKey, "generate", side_effect=capture):
            super().setUpClass()
        w = cls.src.world.accepted
        raw = lambda key: key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)  # noqa: E731
        found = [key for key in keys if sha(raw(key)) == w.kwit_public_key_sha256]
        assert len(found) == 1, "the TEST K-WIT of the synthetic world was not captured"
        cls.kwit = found[0]
        registry = json.loads(cls.files["authority-registry.v1.json"])
        cls.updated_at = registry["issuedAt"]
        cls.candidate_pins = C.CandidatePinsV1(
            registry_sha256=sha(cls.files["authority-registry.v1.json"]),
            root_anchor_sha256=sha(cls.files["registry-root.json"]),
            witness_anchor_sha256=sha(cls.files["witness-anchor.json"]), registry_digest=cls.src.pins.registry_digest,
            registry_issued_at=registry["issuedAt"], ledger_head=cls.head, kwit_key_id=w.kwit_key_id,
            kwit_public_key_sha256=w.kwit_public_key_sha256, epoch_random=WP.EPOCH, policy_version=WP.L.POLICY_VERSION)

    def setUp(self):
        if UID != 0:
            self.skipTest("the witness and signer account contracts need root to chown (CI runs uid >= 1000)")
        super().setUp()
        signer, witness = self.host.users[I.SERVICE_USER], self.host.users[I.WITNESS_USER]
        self.provision(as_signer=False)
        for path in (self.state(), self.target(P.AUTHORITY_LEDGER)):
            os.chown(path, signer.pw_uid, signer.pw_gid)
        self.signer_ids = (signer.pw_uid, signer.pw_gid)
        # the witness runs as its own account; files it creates in the setgid state directory get the signer group
        self.witness_ids = ((witness.pw_uid, witness.pw_gid), signer.pw_gid)
        self.root_system = self.host.system(chown=True)                       # the root installer chowns
        built, _inputs, _ledger = G.candidate(environment="dev", registry_version=1, updated_at=self.updated_at,
                                              root=self.root, owner_uid=UID)
        self.digest = built.digest
        self.assertEqual(self.digest, C.independent_digest(C.expected_unsigned(self.updated_at, self.candidate_pins)))
        inputs = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        (inputs / "genesis-pin.json").write_bytes(V8.expected_pin_bytes(self.digest))
        (inputs / "authorization-register.json").write_bytes(V8.expected_register_bytes(self.src.pins.registry_digest))
        self.assertEqual(I.stage_install_owner_inputs(self.system, T6.U.NEW, inputs / "genesis-pin.json",
                                                      inputs / "authorization-register.json")["result"], "PASS")
        self.runtime = "STOPPED"
        self.unit_overrides: dict[str, dict] = {}
        self.invocation = "1" * 32

    # ------------------------------------------------------------------------------------------ helpers ---

    def view(self, names):
        out = {}
        for name in names:
            state = {"Id": name, "LoadState": "loaded", "UnitFileState": "static", "NeedDaemonReload": "no",
                     "ActiveState": "inactive", "SubState": "dead", "MainPID": "0", "NRestarts": "0",
                     "InvocationID": "", "Result": "success"}
            if name in W.WITNESS_UNITS and self.runtime == "RUNNING":
                state.update(ActiveState="active", SubState="running" if name == W.WITNESS_SERVICE else "listening",
                             MainPID="777" if name == W.WITNESS_SERVICE else "0",
                             InvocationID=self.invocation if name == W.WITNESS_SERVICE else "")
            if name == W.WITNESS_SERVICE and self.runtime == "FAILED":
                state.update(ActiveState="failed", Result="exit-code")
            if name in (W.WITNESS_OWNER_UNIT, W.WITNESS_SIGNER_UNIT) and self.runtime == "SOCKETS_ONLY":
                state.update(ActiveState="active", SubState="listening")
            state.update(self.unit_overrides.get(name, {}))
            out[name] = state
        return out

    def set_runtime(self, runtime: str) -> None:
        self.runtime = runtime
        credentials = self.target(W.WITNESS_CREDENTIALS)
        sockets = [self.target(W.WITNESS_OWNER_SOCKET), self.target(W.WITNESS_SIGNER_SOCKET)]
        if runtime in ("RUNNING", "SOCKETS_ONLY"):
            runtime_dir = sockets[0].parent                                    # tmpfiles: d 0710 root signer-group
            runtime_dir.mkdir(parents=True, exist_ok=True)
            os.chown(runtime_dir, 0, self.witness_ids[1])
            os.chmod(runtime_dir, 0o710)
            for path in sockets:
                path.write_bytes(b"")
        else:
            for path in sockets:
                if path.exists():
                    path.unlink()
        if runtime == "RUNNING":
            credentials.mkdir(parents=True, exist_ok=True)
        elif credentials.exists():
            credentials.rmdir()

    def w9(self, digest=None) -> dict:
        with mock.patch.object(socket, "socket", _no_socket), mock.patch.object(socket, "create_connection", _no_socket):
            return W.evaluate(self.head, digest or self.digest, self.updated_at, root=self.root, owner_uid=UID,
                              owner_gid=GID, signer=self.signer_ids, witness=self.witness_ids, units=self.view,
                              pins=self.pins, trust_pins=self.trust_pins)

    def witness_state(self) -> dict:
        report = I.stage_witness_state(self.root_system, T6.U.NEW)
        self.assertEqual(report["result"], "PASS", report["failures"])
        return report

    def own(self) -> None:
        """What the witness process (its own uid) leaves: re-own every entry this root test process created."""
        (wuid, _wgid), sgid = self.witness_ids
        for directory, dirs, files in os.walk(self.target(P.WITNESS_STATE)):
            for name in dirs + files:
                os.chown(Path(directory) / name, wuid, sgid, follow_symlinks=False)

    def store(self):
        return FilesystemWitnessStorageV1(self.target(P.WITNESS_STATE))

    def context(self):
        inputs = HI.read_host_inputs(environment="dev", root=self.root, owner_uid=UID)
        return inputs, inputs.store_context(authority_public_keys=HI.authority_public_keys(inputs))

    def start_witness(self) -> None:
        """The service start: the witness's own startup recovery (it creates the lock), then running."""
        WRITER.recover(self.store(), context=self.context()[1])
        self.own()
        self.set_runtime("RUNNING")

    def bootstrap(self, fault=None):
        built, inputs, ledger = G.candidate(environment="dev", registry_version=1, updated_at=self.updated_at,
                                            root=self.root, owner_uid=UID)
        registry = next(r for r in inputs.registries if r.get("registryVersion") == 1)
        writer = WRITER.DevSyntheticWitnessWriterV1(signing_key=WitnessSigningKeyV1(self.kwit), storage=self.store(),
                                                    fault_hook=fault)
        try:
            return writer.bootstrap(registry=registry, ledger_observation=ledger, context=self.context()[1],
                                    updated_at=self.updated_at)
        finally:
            self.own()

    def removal_host(self, units="inactive"):
        (wuid, _wgid), sgid = self.witness_ids
        return RM.Host(root=self.root, ids=lambda: (wuid, sgid), units=lambda us: dict.fromkeys(us, units),
                       euid=lambda: 0, hostname=lambda: "lilith-dev-01")

    def started(self) -> None:
        self.witness_state()
        self.start_witness()

    @staticmethod
    def crash_at(point):
        def hook(label):
            if label == point:
                raise Crash(label)
        return hook

    def genesis_path(self) -> Path:
        return self.target(P.WITNESS_STATE) / "chain" / "1.json"

    # ----------------------------------------------------------------------------------------- M-B9a ---

    def test_w9_0_is_the_accepted_package_a_end_state(self):
        report = self.w9()
        self.assertEqual(report["phase"], W.W9_0, report["failures"])
        self.assertEqual(report["routing"], W.SAFE_RETRY)
        self.assertTrue(all(report["base"].values()))
        self.assertEqual(report["hostInputReasons"], [])
        self.assertEqual((report["registryEffective"], report["authorityActive"], report["authorityGranted"]),
                         (False, False, False))
        self.assertEqual(V8.evaluate(self.head, self.digest, self.updated_at, root=self.root, owner_uid=UID,
                                     owner_gid=GID, signer=self.signer_ids, pins=self.pins,
                                     trust_pins=self.trust_pins)["phase"], V8.EXACT)

    def test_witness_state_stage_reaches_w9_1_and_changes_only_the_state_directory(self):
        before = T6.tree(self.root)
        self.witness_state()
        added = sorted(set(T6.tree(self.root)) - set(before))
        self.assertEqual(added, ["var/lib/lilith-recovery-witness"])
        meta = os.lstat(self.target(P.WITNESS_STATE))
        self.assertEqual(stat.S_IMODE(meta.st_mode), 0o2750)
        report = self.w9()
        self.assertEqual(report["phase"], W.W9_1, report["failures"])
        self.assertEqual(report["routing"], W.SAFE_CONTINUE_OR_REMOVE)
        self.assertTrue(report["evidence9a"]["stateDirectoryExact"])
        self.assertFalse(report["evidence9a"]["witnessRunning"])
        # the Package A tools' scope has ended: W8 and M-B6 report later state; W5 evidence is unchanged
        self.assertEqual(V8.evaluate(self.head, self.digest, self.updated_at, root=self.root, owner_uid=UID,
                                     owner_gid=GID, signer=self.signer_ids, pins=self.pins,
                                     trust_pins=self.trust_pins)["phase"], V8.LATER_STATE)
        self.assertEqual(self.verify()["phase"], V6.LATER_STATE)
        w5 = V5.evaluate(root=self.root, owner_uid=UID, owner_gid=GID, pins=self.trust_pins)
        self.assertEqual(w5["phase"], "OUT_OF_SCOPE_POST_LEDGER")
        self.assertTrue(all(w5["evidence"].values()))
        self.assertEqual(self.status("P1B-9a")["result"], "PASS", self.status("P1B-9a")["failures"])

    def test_interrupted_witness_state_is_w9_1p_removable_and_never_rerun_over(self):
        with mock.patch.object(I.os, "chmod", side_effect=OSError("simulated crash before chmod")):
            with self.assertRaises(OSError):
                I.stage_witness_state(self.root_system, T6.U.NEW)
        report = self.w9()
        self.assertEqual(report["phase"], W.W9_1P, report["failures"])
        self.assertEqual(report["routing"], W.SAFE_REMOVE_AND_RETRY)
        with self.assertRaises(I.InstallError) as refused:                    # no re-run over it: P1B-8 fails first
            I.stage_witness_state(self.root_system, T6.U.NEW)
        self.assertIn("UNEXPECTED_PRESENT:/var/lib/lilith-recovery-witness", refused.exception.reason)
        host = self.removal_host()
        plan = RM.plan(host)
        self.assertEqual(plan["remove"], [RM.WITNESS_STATE])
        with self.assertRaises(RM.Refused) as caught:
            RM.remove(host, "0" * 64)
        self.assertEqual(caught.exception.reason, "PLAN_CHANGED")
        self.assertEqual(RM.remove(host, plan["planDigest"])["result"], "PRE_MB9A_RESTORED")
        self.assertEqual(self.w9()["phase"], W.W9_0)
        self.assertEqual(self.status("P1B-8")["result"], "PASS", self.status("P1B-8")["failures"])
        self.witness_state()                                                  # a NEW attempt (a new go) succeeds
        self.assertEqual(self.w9()["phase"], W.W9_1)

    def test_started_witness_is_w9_2_and_a_stopped_one_is_w9_2s(self):
        self.started()
        report = self.w9()
        self.assertEqual(report["phase"], W.W9_2, report["failures"])
        self.assertEqual(report["evidence9a"], dict.fromkeys(W.EVIDENCE_9A, True))
        self.assertEqual(report["storeClassification"], WR.UNINITIALIZED)
        self.assertEqual(report["store"]["listing"], ["witness.lock"])
        self.assertEqual((report["witnessInvocationId"], report["witnessMainPid"], report["witnessNRestarts"]),
                         (self.invocation, "777", "0"))
        self.assertEqual(report["routing"], W.SAFE_ADOPT)
        self.assertEqual(self.status("P1B-9a")["result"], "PASS", self.status("P1B-9a")["failures"])
        self.set_runtime("STOPPED")                                           # e.g. a reboot: units are not enabled
        stopped = self.w9()
        self.assertEqual(stopped["phase"], W.W9_2S)
        self.assertEqual(stopped["routing"], W.SAFE_RESTART_OR_REMOVE)
        self.assertEqual(W.classify_sequence(host_phase=W.W9_2S, markers=["mb9a-1", "mb9a-2"], stage=W.STAGE_PASS,
                                             start=W.START_OK, accepted9a_current=True), W.S9A_STOPPED)

    def test_abnormal_pre_commit_runtime_is_failed_start(self):
        self.started()
        for runtime in ("FAILED", "SOCKETS_ONLY"):
            with self.subTest(runtime):
                self.set_runtime(runtime)
                report = self.w9()
                self.assertEqual(report["phase"], W.W9_FAILED, report["runtime"])
                self.assertEqual(report["lineageReversible"], W.YES)

    def test_unit_and_runtime_inconsistencies(self):
        self.started()
        self.unit_overrides = {W.WITNESS_SERVICE: {"UnitFileState": "enabled"}}
        self.assertEqual(self.w9()["phase"], W.FOREIGN)
        self.unit_overrides = {W.WITNESS_OWNER_UNIT: {"NeedDaemonReload": "yes"}}
        self.assertEqual(self.w9()["phase"], W.UNCLASSIFIED)
        self.unit_overrides = {"lilith-authority-dev.service": {"ActiveState": "active"}}
        self.assertEqual(self.w9()["phase"], W.LATER_STATE)                   # the signer is outside Package B
        self.unit_overrides = {}

        def unreadable(_names):
            raise W.Refused("UNITS_UNREADABLE")
        with mock.patch.object(self, "view", unreadable):
            self.assertEqual(self.w9()["phase"], W.UNCLASSIFIED)               # UNKNOWN is never absence
        self.target(W.SIGNER_CREDENTIALS).mkdir(parents=True)
        self.assertEqual(self.w9()["phase"], W.LATER_STATE)

    # ----------------------------------------------------------------------------------------- M-B9b ---

    def test_bootstrap_commits_exactly_the_pin(self):
        self.started()
        signed = self.bootstrap()
        report = self.w9()
        self.assertEqual(report["phase"], W.W9_5, report["failures"])
        self.assertEqual(report["evidence9b"], dict.fromkeys(W.EVIDENCE_9B, True))
        self.assertEqual(report["committedGenesis"]["digest"], self.digest)
        self.assertTrue(report["committedGenesis"]["fieldsEqualCandidate"])
        self.assertEqual(report["lineageReversible"], W.NO)
        genesis = self.genesis_path().read_bytes()
        self.assertEqual(genesis, WR.document_bytes(signed))
        self.assertEqual((self.target(P.WITNESS_STATE) / "witness.json").read_bytes(), genesis)
        self.assertEqual(sorted(os.listdir(self.target(P.WITNESS_STATE))),
                         ["authorizations", "chain", "witness.json", "witness.lock"])
        self.assertEqual(os.listdir(self.target(P.WITNESS_STATE) / "authorizations"), [])
        unsigned = {k: v for k, v in signed.items() if k != "signature"}
        self.assertEqual(unsigned, C.expected_unsigned(self.updated_at, self.candidate_pins))
        self.assertEqual((unsigned["previousWitnessDigest"], unsigned["consumedAuthorizationId"],
                          unsigned["witnessVersion"], unsigned["ledgerSequence"], unsigned["ledgerHead"]),
                         (None, None, 1, 1, self.head))
        self.assertEqual(self.status("P1B-9b")["result"], "PASS", self.status("P1B-9b")["failures"])
        # the lineage is forward only: no second genesis and no removal
        with self.assertRaises(WRITER.WitnessRefusal) as caught:
            self.bootstrap()
        self.assertEqual(caught.exception.reason, "STORE_NOT_UNINITIALIZED")
        self.set_runtime("STOPPED")
        self.assertEqual(self.w9()["phase"], W.W9_5S)
        with self.assertRaises(RM.Refused) as caught:
            RM.plan(self.removal_host())
        self.assertTrue(caught.exception.reason.startswith("LINEAGE_OR_FOREIGN_ENTRY"), caught.exception.reason)
        self.assertEqual(self.genesis_path().read_bytes(), genesis)

    def test_commit_point_windows_through_the_real_writer(self):
        expectations = {
            "BEFORE_CHAIN_CREATE": W.W9_3, "AFTER_CHAIN_WRITE": W.W9_4, "AFTER_CHAIN_FILE_FSYNC": W.W9_4,
            "AFTER_CHAIN_DIRECTORY_FSYNC": W.W9_4, "AFTER_POINTER_SCRATCH_WRITE": W.W9_4,
            "AFTER_POINTER_SCRATCH_FSYNC": W.W9_4, "AFTER_POINTER_REPLACE": W.W9_5,
            "AFTER_POINTER_DIRECTORY_FSYNC": W.W9_5,
        }
        self.assertTrue(set(expectations) <= set(WRITER.FAULT_POINTS))
        for point, phase in expectations.items():
            with self.subTest(point):
                self.setUp()
                self.started()
                with self.assertRaises(Crash):
                    self.bootstrap(self.crash_at(point))
                report = self.w9()
                self.assertEqual(report["phase"], phase, (report["storeClassification"], report["failures"]))
                marks = ["mb9a-1", "mb9a-2", "mb9b"]
                if phase == W.W9_3:                                          # C-11: no lineage; same candidate again
                    self.assertEqual(report["storeClassification"], WR.UNINITIALIZED)
                    self.assertFalse(report["lineageCommitted"])
                    self.assertEqual(W.classify_sequence(host_phase=phase, markers=marks, stage=W.STAGE_PASS,
                                                         start=W.START_OK, bootstrap=W.TRANSPORT_FAILED), W.S9B_R)
                    self.bootstrap()                                        # a NEW go: idempotent directories
                    self.assertEqual(self.w9()["phase"], W.W9_5)
                elif phase == W.W9_4:                                        # committed: forward only
                    self.assertTrue(report["lineageCommitted"])
                    self.assertEqual(report["lineageReversible"], W.NO)
                    self.assertEqual(W.classify_sequence(host_phase=phase, markers=marks, stage=W.STAGE_PASS,
                                                         start=W.START_OK, bootstrap=W.TRANSPORT_FAILED), W.S9B_POINTER)
                    self.set_runtime("STOPPED")
                    with self.assertRaises(RM.Refused):
                        RM.plan(self.removal_host())
                    with self.assertRaises(WRITER.WitnessRefusal):          # never a second genesis
                        self.bootstrap()
                    self.start_witness()                                     # an authorized restart rolls forward
                    self.assertEqual(self.w9()["phase"], W.W9_5)
                else:
                    self.assertEqual(report["evidence9b"], dict.fromkeys(W.EVIDENCE_9B, True))

    def test_writer_commit_order_is_the_canonical_one(self):
        source = (ROOT / "services/recovery-witness/lilith_recovery_witness/writer.py").read_text(encoding="utf-8")
        commit = source.split("def _commit(", 1)[1].split("\n    def ", 1)[0]
        order = [commit.index(token) for token in ("create_exclusive(WR.CHAIN_DIRECTORY", "fsync_file(WR.CHAIN_DIRECTORY",
                                                   "fsync_directory(WR.CHAIN_DIRECTORY", "_publish_pointer(")]
        self.assertEqual(order, sorted(order))
        storage = (ROOT / "services/recovery-witness/lilith_recovery_witness/storage.py").read_text(encoding="utf-8")
        self.assertIn("self._write(directory, name, data, os.O_EXCL)", storage)
        self.started()
        self.bootstrap()
        with self.assertRaises(FileExistsError):                              # chain/1.json is create-only
            self.store().create_exclusive("chain", "1.json", b"{}")

    def test_torn_genesis_stops_with_no_automated_action(self):
        self.started()
        with self.assertRaises(Crash):
            self.bootstrap(self.crash_at("AFTER_CHAIN_WRITE"))
        path = self.genesis_path()
        data = path.read_bytes()
        os.truncate(path, len(data) // 2)
        report = self.w9()
        self.assertEqual(report["phase"], W.W9_TORN, report["storeClassification"])
        self.assertEqual(report["routing"], W.STOP_OWNER_ADJUDICATION)
        self.set_runtime("STOPPED")
        with self.assertRaises(RM.Refused):
            RM.plan(self.removal_host())
        self.assertNotIn(W.W9_TORN, W.RESTARTABLE_PHASES)
        self.assertEqual(path.read_bytes(), data[:len(data) // 2])            # nothing was repaired or deleted

    def test_genesis_mismatch_is_halt(self):
        self.started()
        built, _inputs, _ledger = G.candidate(environment="dev", registry_version=1, updated_at=self.updated_at,
                                              root=self.root, owner_uid=UID)
        other = dict(built.unsigned, updatedAt="2099-01-01T00:00:00Z")
        signed = WitnessSigningKeyV1(self.kwit).sign_recovery_witness_v2(other)
        storage = self.store()
        for directory in ("chain", "authorizations"):
            storage.make_directory(directory)
        storage.create_exclusive("chain", "1.json", WR.document_bytes(signed))
        pointer = self.target(P.WITNESS_STATE) / "witness.json"
        pointer.write_bytes(WR.document_bytes(signed))
        os.chmod(pointer, 0o640)
        self.own()
        report = self.w9()
        self.assertEqual(report["phase"], W.W9_MISMATCH, report["storeClassification"])
        self.assertEqual(report["routing"], W.HALT)
        self.assertEqual(W.classify_sequence(host_phase=W.W9_MISMATCH, markers=["mb9a-1", "mb9a-2", "mb9b"],
                                             stage=W.STAGE_PASS, start=W.START_OK, bootstrap=W.BOOTSTRAP_PASS),
                         W.S9_HALT)
        with self.assertRaises(WRITER.WitnessRefusal):                         # never a second genesis
            self.bootstrap()

    def test_later_and_foreign_states(self):
        self.started()
        self.bootstrap()
        chain = self.target(P.WITNESS_STATE) / "chain"
        (chain / "2.json").write_bytes((chain / "1.json").read_bytes())
        os.chmod(chain / "2.json", 0o640)
        self.own()
        self.assertEqual(self.w9()["phase"], W.LATER_STATE)
        (chain / "2.json").unlink()
        hold = self.target(W.HOLD_STORE) / "x.json"
        hold.write_bytes(b"{}")
        self.assertEqual(self.w9()["phase"], W.LATER_STATE)
        hold.unlink()
        notes = self.target(P.WITNESS_STATE) / "notes"
        notes.write_bytes(b"x")
        self.assertEqual(self.w9()["phase"], W.FOREIGN)
        notes.unlink()
        lock = self.target(P.WITNESS_STATE) / "witness.lock"
        os.chmod(lock, 0o664)
        self.assertEqual(self.w9()["phase"], W.FOREIGN)
        os.chmod(lock, 0o640)
        lock.unlink()
        os.symlink("/etc/passwd", lock)
        self.assertEqual(self.w9()["phase"], W.FOREIGN)
        lock.unlink()
        self.assertEqual(self.w9()["phase"], W.W9_5)                           # back to exact (the lock is optional)

    def test_bounded_removal_is_pre_commit_only(self):
        self.started()
        with self.assertRaises(RM.Refused) as caught:
            RM.plan(self.removal_host())                                      # running: never stops anything
        self.assertTrue(caught.exception.reason.startswith("RUNTIME_PRESENT"), caught.exception.reason)
        self.set_runtime("STOPPED")
        with self.assertRaises(RM.Refused) as caught:
            RM.plan(self.removal_host(units="active"))
        self.assertTrue(caught.exception.reason.startswith("UNIT_NOT_INACTIVE"))
        with self.assertRaises(Crash):
            self.bootstrap(self.crash_at("BEFORE_CHAIN_CREATE"))
        self.assertEqual(self.w9()["phase"], W.W9_3)
        host = self.removal_host()
        plan = RM.plan(host)
        self.assertEqual(plan["remove"], [RM.CHAIN, RM.AUTHORIZATIONS, RM.LOCK, RM.WITNESS_STATE])
        for residue, reason in ((("chain", "1.json"), "LINEAGE_OR_FOREIGN_ENTRY:chain/"),
                                (("witness.json",), "LINEAGE_OR_FOREIGN_ENTRY:witness.json"),
                                ((".witness.json.tmp",), "LINEAGE_OR_FOREIGN_ENTRY:.witness.json.tmp"),
                                (("authorizations", "a" * 64 + ".json"), "LINEAGE_OR_FOREIGN_ENTRY:authorizations/"),
                                (("notes",), "LINEAGE_OR_FOREIGN_ENTRY:notes")):
            with self.subTest(reason):
                path = self.target(P.WITNESS_STATE).joinpath(*residue)
                path.write_bytes(b"{")                                        # even a partial file
                with self.assertRaises(RM.Refused) as caught:
                    RM.plan(host)
                self.assertEqual(caught.exception.reason, reason)
                path.unlink()
        self.target(W.WITNESS_CREDENTIALS).mkdir(parents=True)
        with self.assertRaises(RM.Refused):
            RM.plan(host)
        self.target(W.WITNESS_CREDENTIALS).rmdir()
        stale = RM.plan(host)["planDigest"]
        (self.target(P.WITNESS_STATE) / "authorizations").rmdir()
        with self.assertRaises(RM.Refused) as caught:
            RM.remove(host, stale)
        self.assertEqual(caught.exception.reason, "PLAN_CHANGED")
        done = RM.remove(host, RM.plan(host)["planDigest"])
        self.assertEqual(done["result"], "PRE_MB9A_RESTORED")
        self.assertFalse(self.target(P.WITNESS_STATE).exists())
        self.assertEqual(self.w9()["phase"], W.W9_0)
        self.assertEqual(self.status("P1B-8")["result"], "PASS", self.status("P1B-8")["failures"])
        self.assertTrue(self.target(P.AUTHORITY_LEDGER).exists())
        with self.assertRaises(RM.Refused) as caught:
            RM.remove(host, RM.plan(host)["planDigest"])
        self.assertEqual(caught.exception.reason, "NOTHING_TO_REMOVE")

    def test_removal_source_touches_only_the_witness_skeleton(self):
        source = Path(RM.__file__).read_text(encoding="utf-8").split('"""', 2)[2]
        self.assertEqual(source.count("os.unlink("), 1)
        self.assertEqual(source.count("os.rmdir("), 1)
        for forbidden in ("rmtree", "os.remove(", "systemctl stop", "systemctl start", "chmod", "chown"):
            self.assertNotIn(forbidden, source)

    # ------------------------------------------------------------------------------ owner verification ---

    def owner_record(self) -> Path:
        out = Path(self.stack.enter_context(tempfile.TemporaryDirectory())) / "genesis"
        C.write_emitted(synthetic_derivation(self.updated_at, self.candidate_pins), out)
        pin_dir = out.parent / "p-a"
        C.record(out, pin_dir)
        return pin_dir

    def test_owner_offline_verification(self):
        self.started()
        self.bootstrap()
        evidence = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        chain, pointer, anchor = evidence / "chain-1.json", evidence / "witness.json", evidence / "witness-anchor.json"
        chain.write_bytes(self.genesis_path().read_bytes())
        pointer.write_bytes((self.target(P.WITNESS_STATE) / "witness.json").read_bytes())
        anchor.write_bytes(self.files["witness-anchor.json"])
        pin_dir = self.owner_record()

        def verify(**kw):
            return OV.verify(pin_dir, kw.get("anchor", anchor), kw.get("chain", chain), kw.get("pointer", pointer),
                             expected_digest=self.digest, updated_at=self.updated_at, pins=self.candidate_pins)
        result = verify()
        self.assertEqual(result["result"], "MB9B_OWNER_GENESIS_VERIFIED", result["checks"])
        self.assertTrue(all(result["checks"].values()))
        self.assertTrue(all(result["fields"].values()))
        self.assertEqual(result["committedDigest"], self.digest)
        self.assertEqual((result["record1"], result["freshness"], result["accepted"]), ("NOT CREATED", "UNKNOWN", False))
        document = json.loads(chain.read_bytes())
        tampered = evidence / "tampered.json"
        signature = document["signature"]
        flipped = ("A" if signature[0] != "A" else "B") + signature[1:]
        tampered.write_bytes(C.independent_jcs(dict(document, signature=flipped)))
        self.assertFalse(verify(chain=tampered)["checks"]["kwitSignatureVerifies"])
        moved = evidence / "moved.json"
        moved.write_bytes(C.independent_jcs(dict(document, updatedAt="2099-01-01T00:00:00Z")))
        self.assertFalse(verify(chain=moved)["checks"]["genesisFieldsEqualExpected"])
        self.assertFalse(verify(chain=moved, pointer=moved)["checks"]["committedDigestEqualsOwnerPin"])
        self.assertFalse(verify(pointer=tampered)["checks"]["pointerEqualsGenesis"])
        other_anchor = evidence / "other-anchor.json"
        other_anchor.write_bytes(self.other_files["witness-anchor.json"])
        bad = verify(anchor=other_anchor)
        self.assertFalse(bad["checks"]["anchorIsAcceptedInstallable"])
        self.assertFalse(bad["checks"]["kwitSignatureVerifies"])
        (pin_dir / "notes.txt").write_text("x", encoding="ascii")
        with self.assertRaises(OV.VerifyError) as caught:
            verify()
        self.assertEqual(caught.exception.reason, "PIN_DIRECTORY_INEXACT")
        self.assertNotIn("replica", Path(OV.__file__).read_text(encoding="utf-8").split('"""', 2)[2].lower())


# ----------------------------------------------------------------------------------------- the records ---

class RecordTests(Redacted, unittest.TestCase):
    def setUp(self):
        self.text = PACKAGE.read_text(encoding="utf-8")
        self.flat = flat(self.text)
        self.state = self.text.split("## 21. State", 1)[1]
        self.completion = COMPLETION_A.read_text(encoding="utf-8")
        self.ledger = (ARCH / "current-architecture-acceptance-ledger-v0.1.md").read_text(encoding="utf-8")

    def section(self, start: str, end: str) -> str:
        return self.text.split(start, 1)[1].split(end, 1)[0]

    def test_state_and_boundaries(self):
        for line in ("PACKAGE_B (M-B9a + M-B9b) = REPOSITORY ONLY (SOURCE + TESTS + DOCS); NOT MERGED; NOT RUN",
                     "PACKAGE_B_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_AUTHORITY_BOUNDARIES "
                     "(OWNER-ACCEPTED 2026-10-08, OD-B1)", "PACKAGE_A = COMPLETED / OWNER-ACCEPTED",
                     "E-A18 = NOT YET PERFORMED", "M-B9a = NOT AUTHORIZED", "M-B9b = NOT AUTHORIZED",
                     "WITNESS_GENESIS = NOT COMMITTED", "RECORD 1 = ABSENT", "FIRST MEMORY = NOT AUTHORIZED",
                     "PROD = NOT AUTHORIZED", "REGISTRY_EFFECTIVE = NO", "AUTHORITY_ACTIVE = NO", "GRANT_ABSENT = TRUE",
                     "FRESHNESS = UNKNOWN", "PACKAGE_B_SEQUENCE = NOT AUTHORIZED"):
            self.assertIn(line, self.state)
        before_templates = self.text.split("## 10. Owner acts", 1)[0]
        for claim in FORBIDDEN_CLAIMS:
            self.assertNotIn(claim, before_templates + self.state, claim)

    def test_tool_pins_in_the_record_equal_the_code(self):
        table = self.section("## 16. Tool pins", "## 17.")
        for path, pin in O.TOOL_PINS.items():
            self.assertIn(f"| `{path}` | `{pin}` |", table, path)
        self.assertEqual(len(re.findall(r"^\| `[^`]+` \| `[0-9a-f]{64}` \|$", table, re.M)), len(O.TOOL_PINS))
        for path in NEW_TOOLS:                                            # no provisional pin left anywhere
            name = re.escape(Path(path).name)
            for text in (self.text, Path(__file__).read_text(encoding="utf-8")):
                cited = re.findall(rf"{name}` \| `([0-9a-f]{{64}})`", text) + re.findall(
                    rf"{name} SHA-256 ([0-9a-f]{{64}})", text)
                self.assertEqual(set(cited) - {O.TOOL_PINS[path]}, set(), path)

    def test_owner_texts_are_reproduced_verbatim(self):
        for lines in (O.SEQUENCE_LINES, O.MB9A_GO_LINES, O.WITNESS_STARTED_LINES, O.MB9B_GO_LINES,
                      O.PACKAGE_B_ACCEPTANCE_LINES, O.REMOVAL_LINES, O.RESTART_LINES):
            for line in lines:
                literal = line.replace("{updated_at}", "<updatedAt>")
                for key in ("control", "operator", "candidate", "pin", "register", "record", "invocation", "mainpid",
                            "post9a", "post9b", "genesis", "plan", "phase"):
                    literal = literal.replace("{" + key + "}", f"<{key}>")
                self.assertIn("> " + literal, self.text, literal[:60])

    def test_point_of_no_return_and_object_separation(self):
        ponr = self.section("## 5. The lineage point of no return", "## 6.")
        for phrase in ("created `O_EXCL`", "its bytes are fsynced", "`chain/` is fsynced",
                       "THE CHAIN DIRECTORY FSYNC IS THE LINEAGE COMMIT POINT", "WITNESS LINEAGE = FORWARD ONLY",
                       "roll-forward-recoverable", "`REBOOTSTRAP_FORBIDDEN`", "no second witness genesis, ever",
                       "`STORE_NOT_UNINITIALIZED`"):
            self.assertIn(phrase, ponr)
        objects = self.section("## 4. The witness genesis (exact)", "## 5.")
        for name in ("ledger `GENESIS` op", "witness genesis candidate", "`OwnerGenesisPinV1`", "`genesis-pin.json`",
                     "`authorization-register.json`", "committed witness genesis `chain/1.json`", "`witness.json`",
                     "Registry V1 material", "record 1 / `OwnerFreshnessRecordV1`"):
            self.assertIn(name, objects)
        self.assertIn(REGISTRY_SHA256, objects)
        self.assertIn(O.PONR_ACKNOWLEDGEMENT, self.text)

    def test_every_w9_phase_is_documented_with_its_route(self):
        table = self.section("### 6.1 W9 host phases", "### 6.2")
        for phase in W.HOST_PHASES:
            route, reversible, _act, _note = W.PHASE_TABLE[phase]
            row = next((line for line in table.splitlines() if line.startswith(f"| `{phase}` |")), None)
            self.assertIsNotNone(row, phase)
            self.assertIn(f"`{route}`", row, phase)
            self.assertIn(f"| {reversible} |", row, phase)
        sequence = self.section("### 6.2", "### 6.3")
        for phase in W.SEQUENCE_PHASES:
            if phase.startswith("S9"):
                self.assertIn(f"`{phase}`", sequence, phase)

    def test_dr5_and_denial_tables_equal_the_code(self):
        dr5 = self.section("## 12. DR-5 by phase", "## 13.")
        for target, label in ((T.STOPPED, "witness state present, service stopped"), (T.RUNNING, "witness running")):
            row = next(line for line in dr5.splitlines() if line.startswith(f"| {label} |"))
            lines, digest = T.TARGETS[target]["result-set"]
            self.assertIn(f"{lines} lines, `{digest}`", row)
            self.assertIn(f"{T.TARGETS[target]['dr5-block'][0]}, `{T.TARGETS[target]['dr5-block'][1]}`", row)
        self.assertIn("190 lines", dr5)
        self.assertIn("164 `DENIED`, 0 `ALLOWED`, 0 `FAIL`, 2 deferred, 6 unobservable", dr5)
        self.assertIn("167 `DENIED`, 0 `ALLOWED`, 0 `FAIL`, 1 deferred, 6 unobservable", dr5)
        self.assertIn("**M-B9b adds no DR-5 line:**", dr5)
        self.assertIn("`NO_BASELINE_STOP`", dr5)
        self.assertIn("**Both are PROPOSED; neither is accepted**", dr5)
        denial = self.section("## 11. Denial proofs", "## 12.")
        for phase in DP.PHASES:
            denied, by_design = DP.expected_counts(phase)
            self.assertIn(f"| {phase} | {denied} | {by_design} |", denial)
        self.assertIn("out of their valid phase (not drift, not failure)", denial)

    def test_e_a18_b5_and_w8_defect(self):
        e_a18 = self.section("## 13. E-A18", "## 14.")
        for phase in ("E-A18 candidate", "`OWNER_INPUTS_INSTALLED_EXACT`", "a separate owner merge decision",
                      "a small E-A18 record PR", "only then may that merge commit become the Package B live control"):
            self.assertIn(phase, e_a18)
        b5 = self.section("## 17. B-5 qualification", "## 18.")
        for phrase in ("remains governing for applicable PR-1B continuation and sequencing",
                       "**However, the old B-5 §9 post-M-B1 deployment-baseline condition is HISTORICAL**",
                       "`B5_SECTION_9_POST_MB1_STATUS = HISTORICAL_AFTER_MB1_EXERCISED`",
                       "never resurrects it", "`PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA`"):
            self.assertIn(phrase, b5)
        self.assertIn("**OPEN FUTURE REMEDIATION**", self.section("## 18.", "## 19."))
        self.assertIn("**OPEN FUTURE REMEDIATION:**", self.completion)

    def test_first_memory_hard_boundary(self):
        section = self.section("## 19. First Memory hard boundary", "## 20.")
        for phrase in ("inferred by tooling", "auto-generated", "selected by Claude", "selected by a model",
                       "readiness gates pass", "FIRST_MEMORY_READY", "execution MUST STOP", "the owner is told explicitly"):
            self.assertIn(phrase, section)

    def test_package_a_completion_record(self):
        state = self.completion.split("## 12. State", 1)[1]
        for line in ("PACKAGE_A = COMPLETED / OWNER-ACCEPTED", "M-B7 = OWNER-ACCEPTED", "M-B8 = OWNER-ACCEPTED",
                     "GENESIS_PREPARED = YES", "GENESIS_PINNED = YES",
                     "HOST OWNER INPUTS = OWNER_INPUTS_INSTALLED_EXACT", "E-A17 = COMPLETE", "LEDGER_SEQUENCE = 1",
                     "LEDGER_HEAD = " + HEAD, "registryEffective = false", "authorityActive = false",
                     "authorityGranted = false", "GRANT_ABSENT = TRUE", "WITNESS = INACTIVE", "SIGNER = INACTIVE",
                     "WITNESS_GENESIS = NOT COMMITTED", "RECORD 1 = ABSENT", "E-A18 = NOT YET PERFORMED",
                     "PACKAGE_A_FINAL_EVIDENCE_SEAL = 71a503d8b99240bfff61e8da23cf95aa225868b31a23ad507614c2f358b1551d",
                     "PACKAGE_A_PRIOR_SEAL_PRESERVED = 50e8804c066420b0c15f89ce6a5d8d7672b31251640900162139f8b7db348e0a",
                     "M-B9a = NOT AUTHORIZED", "M-B9b = NOT AUTHORIZED", "FIRST MEMORY = NOT AUTHORIZED"):
            self.assertIn(line, state)
        for claim in ("E-A18 = PERFORMED", "E-A18 = PASS", "M-B9a = AUTHORIZED", "WITNESS_GENESIS = COMMITTED"):
            self.assertNotIn(claim, self.completion)
        accepted = self.completion.split("## 6. Owner acceptance", 1)[1].split("## 7.", 1)[0]
        for value in (CANDIDATE, ACCEPTED_UPDATED_AT, "e5441b5a260a314925c8393d7afa69adc7a6ed031a6608d077d25ffa19c6e2e6",
                      "This acceptance authorizes nothing further. The deployment freeze ends now"):
            self.assertIn(value, accepted)
        self.assertIn(REGISTRY_SHA256, self.completion)
        for pin in PACKAGE_A_TOOL_PINS.values():
            self.assertIn(pin, self.completion)

    def test_ledger_and_index(self):
        ledger = self.ledger
        for heading in ("### 13.1ak Current-state reconciliation (Package A: M-B7 + M-B8 completion and owner acceptance",
                        "### 13.1al Current-state reconciliation (Package B: M-B9a + M-B9b design and tooling"):
            self.assertIn(heading, ledger)
        self.assertLess(ledger.index("### 13.1aj"), ledger.index("### 13.1ak"))
        self.assertLess(ledger.index("### 13.1ak"), ledger.index("### 13.1al"))
        self.assertLess(ledger.index("### 13.1al"), ledger.index("### 13.2 Checks"))
        self.assertIn("FRESHNESS=UNKNOWN (§13.1ak)", ledger)
        self.assertIn("FRESHNESS=UNKNOWN (§13.1al)", ledger)   # the AUTH-02 cell
        ak = ledger.split("### 13.1ak", 1)[1].split("### 13.1al", 1)[0]
        al = ledger.split("### 13.1al", 1)[1].split("### 13.2 Checks", 1)[0]
        self.assertIn("**E-A18 is NOT YET PERFORMED.**", ak)
        self.assertIn("`PACKAGE_A = COMPLETED / OWNER-ACCEPTED`", ak)
        self.assertIn("**the B-5 qualification**", al)
        self.assertIn("`B5_SECTION_9_POST_MB1_STATUS = HISTORICAL_AFTER_MB1_EXERCISED`", al)
        for claim in FORBIDDEN_CLAIMS:
            self.assertNotIn(claim, ak + al, claim)
        readme = (ARCH / "README.md").read_text(encoding="utf-8")
        self.assertIn("(slice-15b2b-b1b3e-mb9-witness-genesis-package.md)", readme)
        self.assertIn("(slice-15b2b-b1b3e-mb7-mb8-package-a-completion.md)", readme)


if __name__ == "__main__":
    unittest.main()
