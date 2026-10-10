"""15B2b-B1b-3e M-B10 (WRITE_HELD) design slice: verifier, classifiers, DR-5 target, denial proof, owner
eligibility and operator (TEST-ONLY; synthetic fixtures; no live system).

Record: docs/architecture/slice-15b2b-b1b3e-mb10-held-package.md.

Layers: the stdlib layer runs everywhere; the contract layer needs `cryptography` / `rfc8785` / `fido2`; the
synthetic-host layer (the REAL release hold writer on a synthetic root with a committed synthetic witness genesis)
needs POSIX and root, like the Package B host tests.
"""

from __future__ import annotations

import ast
import base64
import hashlib
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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-mb10-held-package.md"
for _p in (ROOT / "services/core-api", ROOT / "services/owner-memory-control", TOOLS, ROOT / "services/authority-dev",
           ROOT / "services/authority-dev/ceremony", ROOT / "services/authority-dev/tests",
           ROOT / "services/recovery-witness", HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import test_b1b3e_mb9_package as P9  # noqa: E402  (its synthetic plink binding and fixtures)
import mb10_dr5_target as D  # noqa: E402
import mb10_hold_denial_proof as DP  # noqa: E402
import mb10_held_verifier as V  # noqa: E402
import mb10_operator as O  # noqa: E402
import mb10_owner_eligibility as E  # noqa: E402
import mb10_scratch_recovery as SR  # noqa: E402
import mb9_dr5_target as T9  # noqa: E402
import mb9_operator as M9  # noqa: E402
import mb9_witness_verifier as W9  # noqa: E402

POSIX = os.name == "posix"
HAVE_CRYPTO = P9.HAVE_CRYPTO
UID, GID = P9.UID, P9.GID
GENESIS = "ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4"
CONTROL = P9.CONTROL
NEW_TOOLS = (O.MB10_VERIFIER, O.MB10_DENIAL, O.MB10_DR5, O.MB10_ELIGIBILITY, O.MB10_SCRATCH)
NOW = datetime(2026, 10, 10, 9, 0, 0, tzinfo=timezone.utc)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def flat(text: str) -> str:
    return " ".join(text.split())


# ------------------------------------------------------------------------------------------- pins ---

class PinTests(P9.Redacted, unittest.TestCase):
    def test_every_tool_hashes_to_its_pin(self):
        for path, pin in O.TOOL_PINS.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)

    def test_reused_tools_are_unchanged(self):
        self.assertEqual({k: v for k, v in O.TOOL_PINS.items() if k in M9.TOOL_PINS}, M9.TOOL_PINS)
        self.assertEqual(O.TOOL_PINS[M9.VERIFIER], "e4aca11dcc925e8ebdb280c2d4a7da1cf4f9a8fcc4e2abb080e22d6917080e78")
        self.assertEqual(O.TOOL_PINS[M9.DR5_TARGET], D.MB9_DR5_TARGET_SHA256)
        self.assertEqual(sha(Path(M9.__file__).read_bytes()), O.TOOL_PINS[O.MB9_OPERATOR])
        self.assertEqual(O.TOOL_PINS[O.PKGC_OPERATOR], E.PKGC_OPERATOR_SHA256)
        self.assertEqual(O.TOOL_PINS[O.DR5_SCRIPT], D.DR5_SCRIPT_SHA256)

    def test_w9_phases_and_targets_are_not_reinterpreted(self):
        self.assertIn(W9.LATER_STATE, W9.HOST_PHASES)
        self.assertEqual(W9.PHASE_TABLE[W9.LATER_STATE][0], W9.STOP_OWNER_ADJUDICATION)
        self.assertFalse(set(D.PHASE_TARGETS) & set(T9.PHASE_TARGETS))
        self.assertFalse(set(V.HOST_PHASES) & set(W9.HOST_PHASES) - {V.UNCLASSIFIED})
        self.assertEqual(T9.PHASE_TARGETS["W9_5_GENESIS_COMMITTED_EXACT"], T9.RUNNING)

    def test_the_bundle_runs_the_unchanged_w9_verifier_first(self):
        self.assertEqual(O.W10_BUNDLE[:-1], M9.VERIFIER_BUNDLE)
        self.assertEqual(O.W10_BUNDLE[-1], O.MB10_VERIFIER)


# ---------------------------------------------------------------------------------- expected HELD ---

class ExpectedHeldTests(P9.Redacted, unittest.TestCase):
    def test_the_pinned_record_is_fully_determined_by_fixed_context(self):
        held = V.pinned_expected_held(GENESIS)
        self.assertEqual((held["name"], held["sha256"], held["length"]),
                         (V.EXPECTED_HELD_NAME, V.EXPECTED_HELD_SHA256, V.EXPECTED_HELD_LENGTH))
        self.assertEqual(held["name"], sha(V.INITIAL_CEREMONY_ID.encode()) + ".json")
        self.assertEqual(held["record"], {
            "protocol": "LILITH_CEREMONY_HOLD", "schemaVersion": 1, "environment": "dev",
            "ceremonyId": "dev.initial-custody.test-only.dev-synthetic.actor.b1b3d.1", "transitionKind": "INITIAL_CUSTODY",
            "state": "HELD", "reason": "INITIAL_CUSTODY_BOOTSTRAP", "expectedPredecessorKeyId": None,
            "expectedSuccessorKeyId": "test-only.dev-synthetic.actor.b1b3d.1", "observedWitnessDigest": GENESIS})
        self.assertNotIn(b" ", held["bytes"])
        self.assertEqual(DP.HELD_NAME, V.EXPECTED_HELD_NAME)
        self.assertEqual(O.Operator.expected(ROOT)["held_sha"], V.EXPECTED_HELD_SHA256)
        self.assertNotEqual(V.pinned_expected_held("0" * 64)["sha256"], held["sha256"])
        for bad in ("", "AC892DC2" + "0" * 56, "0" * 63, None):
            with self.assertRaises(V.Refused):
                V.pinned_expected_held(bad)

    def test_cli_stdout_is_the_record_wrapped_once(self):
        held = V.pinned_expected_held(GENESIS)
        self.assertEqual(V.expected_cli_stdout(held), b'{"record":' + held["bytes"] + b"}\n")
        self.assertEqual(V.scratch_name(held), "." + V.EXPECTED_HELD_NAME + ".tmp")

    @unittest.skipUnless(HAVE_CRYPTO, "the release contract needs cryptography / rfc8785 / fido2")
    def test_the_release_contract_derives_exactly_the_pinned_record(self):
        from lilith_owner_memory import successor_custody as SC

        held = V.expected_held(GENESIS)
        self.assertEqual(held, V.pinned_expected_held(GENESIS))
        holds, reason, _ = SC.parse_hold_store(SC.hold_store(held["record"]), profile=SC.custody_profile("dev"))
        self.assertIsNone(reason)
        (hold,) = holds.values()
        self.assertEqual((hold.state, hold.transition_kind, hold.observed_witness_digest), (SC.HELD, SC.INITIAL_CUSTODY,
                                                                                            GENESIS))
        self.assertFalse(SC.CeremonyHoldV1.authority_granted)
        self.assertEqual(SC.hold_record_name(held["ceremonyId"]), V.EXPECTED_HELD_NAME)
        self.assertEqual(SC.custody_profile("dev").initial_key_id, V.INITIAL_KEY_ID)


# ------------------------------------------------------------------------------------------ DR-5 ---

def accepted_sets() -> dict[str, bytes]:
    return {name: T9.encode(lines) for name, lines in P9.fixture_sets().items()}


SCRIPT = (ROOT / D.DR5_SCRIPT).read_bytes()


class Dr5TargetTests(P9.Redacted, unittest.TestCase):
    def test_the_post_held_delta_is_empty_and_proven_from_the_pinned_script(self):
        derived = D.derive(accepted_sets(), SCRIPT)
        self.assertEqual(derived["delta"], "EMPTY_PROVEN_FROM_PINNED_SCRIPT")
        self.assertTrue(derived["proof"]["holdStoreUnobservable"])
        self.assertFalse(derived["accepted"])
        for target, source in D.SOURCE.items():
            for name in D.SETS:
                got = derived["targets"][target]["sets"][name]
                self.assertEqual((got["lines"], got["sha256"]), T9.TARGETS[source][name], (target, name))
                self.assertEqual((got["added"], got["removed"]), ([], []))
        self.assertEqual(D.TARGETS[D.RUNNING_HELD]["result-set"],
                         (192, "593c90e1778b0e90326cdf96314b328948c00b2207960d27be2b41874d05ff65"))

    def test_any_script_that_could_observe_the_hold_store_is_refused(self):
        with self.assertRaises(D.TargetError) as caught:
            D.derive(accepted_sets(), SCRIPT + b"\n")
        self.assertEqual(caught.exception.reason, "DR5_SCRIPT_PIN_MISMATCH")
        text = SCRIPT.decode()
        mutations = {
            "HOLD_PATH_OBSERVED_BY_SCRIPT:AB_LATER": text.replace(
                'readonly AB_LATER="', 'readonly AB_LATER="/var/lib/lilith-authority-custody/holds '),
            "HOLD_STORE_NOT_AN_UNOBSERVABLE_LEAF": text.replace(
                "/var/lib/lilith-authority-custody|/var/lib/lilith-authority-custody/holds\n", ""),
            "HOLD_PARENT_ROW_NOT_ROOT_ONLY": text.replace(
                "P1A-9|/var/lib/lilith-authority-custody|directory|700|-r -x", "P1A-9|/var/lib/lilith-authority-custody|directory|755|"),
        }
        for reason, mutated in mutations.items():
            data = mutated.encode()
            self.assertNotEqual(data, SCRIPT)
            with mock.patch.object(D, "DR5_SCRIPT_SHA256", sha(data)):
                with self.assertRaises(D.TargetError) as caught:
                    D.prove_hold_unobservable(data)
            self.assertEqual(caught.exception.reason, reason)

    def test_compare_uses_only_an_independently_verified_w10_phase(self):
        texts = D.derive(accepted_sets(), SCRIPT)["targets"]
        log = "\n".join(texts[D.RUNNING_HELD]["texts"]["result-set"]) + "\n"
        result = D.compare("W10_1_HELD_EXACT", log)
        self.assertEqual((result["result"], result["target"], result["targetAccepted"]), ("EQUAL", D.RUNNING_HELD, False))
        self.assertIn("not evidence of HELD", result["note"])
        for phase in ("W9_5_GENESIS_COMMITTED_EXACT", "W10_0_PRE_HELD_EXACT", "W10_HOLD_RECORD_MALFORMED",
                      "UNCLASSIFIED_STOP"):
            with self.assertRaises(D.TargetError) as caught:
                D.compare(phase, log)
            self.assertTrue(caught.exception.reason.startswith("NO_BASELINE_STOP"))
        drift = log.replace("DENIED: test -w /opt\n", "ALLOWED(unexpected) test -w /opt\n", 1)
        self.assertEqual(D.compare("W10_1_HELD_EXACT", drift)["result"], "DRIFT")

    def test_the_cli_derives_from_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for name, data in accepted_sets().items():
                path = Path(tmp) / name
                path.write_bytes(data)
                paths.append(str(path))
            script = Path(tmp) / "script.sh"
            script.write_bytes(SCRIPT)
            out = subprocess.run([sys.executable, "-B", str(TOOLS / "mb10_dr5_target.py"), "derive", *paths, str(script)],
                                 capture_output=True, check=False)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["delta"], "EMPTY_PROVEN_FROM_PINNED_SCRIPT")


# ----------------------------------------------------------------------------------- transcripts ---

class TranscriptTests(P9.Redacted, unittest.TestCase):
    def setUp(self):
        self.held = V.pinned_expected_held(GENESIS)

    def classify(self, rc, out=b"", err=b""):
        return V.classify_hold_transcript(rc, out, err, expected=self.held)[0]

    def test_only_the_exact_reply_is_held_returned_exact(self):
        exact = V.expected_cli_stdout(self.held)
        self.assertEqual(self.classify(0, exact), V.HELD_RETURNED_EXACT)
        self.assertEqual(self.classify(0, exact, b"warning\n"), V.HELD_RETURNED_NOT_EXACT)
        self.assertEqual(self.classify(0, exact.replace(GENESIS.encode(), b"0" * 64)), V.HELD_RETURNED_NOT_EXACT)
        self.assertEqual(self.classify(0, b""), V.HELD_RETURNED_NOT_EXACT)

    def test_refusals_never_prove_absence_but_are_classified(self):
        refuse = lambda reason: (2, b"", f"lilith-authority-hold-dev: REFUSED {reason}\n".encode())  # noqa: E731
        for reason in ("HOLD_STORE_NOT_EMPTY", "HOLD_WITNESS_NOT_CONSISTENT", "NOT_ROOT", "HOST_INPUTS_INCOMPLETE:X"):
            self.assertEqual(self.classify(*refuse(reason)), V.REFUSED_BEFORE_WRITE, reason)
        for reason in ("OSError", "ValueError", "HOLD_CEREMONY_EXISTS"):
            self.assertEqual(self.classify(*refuse(reason)), V.REFUSED_AMBIGUOUS, reason)
        self.assertEqual(self.classify(96), V.GUARD_STOPPED)
        self.assertEqual(self.classify(97), V.GUARD_STOPPED)
        self.assertEqual(self.classify(255), V.TRANSPORT_FAILED)
        self.assertEqual(self.classify(None), V.TRANSPORT_FAILED)
        self.assertEqual(self.classify(1), V.FAILED_UNCLASSIFIED)
        self.assertEqual(self.classify(2, b"x", b"lilith-authority-hold-dev: REFUSED NOT_ROOT"), V.FAILED_UNCLASSIFIED)


# ------------------------------------------------------------------------------ sequence table ---

class SequenceTests(P9.Redacted, unittest.TestCase):
    def seq(self, host, hold, marker=True, transcript=V.NOT_INVOKED, **kw):
        return V.classify_sequence(host_phase=host, hold_class=hold, marker=marker, transcript=transcript, **kw)

    def test_the_required_failure_and_recovery_cases(self):
        cases = [
            # (case, host, hold, marker, transcript, extra, expected sequence phase, expected disposition)
            ("no attempt", V.W10_0, V.HS_EMPTY, False, V.NOT_INVOKED, {}, V.S10_0, V.CONTINUE),
            ("marker written, writer not invoked", V.W10_0, V.HS_EMPTY, True, V.NOT_INVOKED, {}, V.S10_R,
             V.ENDS_LINKED_SUCCESSOR),
            ("writer REFUSED before write", V.W10_0, V.HS_EMPTY, True, V.REFUSED_BEFORE_WRITE, {}, V.S10_R,
             V.ENDS_LINKED_SUCCESSOR),
            ("ambiguous refusal, nothing written", V.W10_0, V.HS_EMPTY, True, V.REFUSED_AMBIGUOUS, {}, V.S10_R,
             V.ENDS_LINKED_SUCCESSOR),
            ("HELD written, acknowledged", V.W10_1, V.HS_HELD_EXACT, True, V.HELD_RETURNED_EXACT, {},
             V.S10_POST_PENDING, V.CONTINUE),
            ("HELD written but response lost", V.W10_1, V.HS_HELD_EXACT, True, V.TRANSPORT_FAILED, {},
             V.S10_UNACKNOWLEDGED, V.CONTINUE),
            ("HELD written, refusal after rename", V.W10_1, V.HS_HELD_EXACT, True, V.REFUSED_AMBIGUOUS, {},
             V.S10_UNACKNOWLEDGED, V.CONTINUE),
            ("pending / temp artifact", V.W10_SCRATCH, V.HS_SCRATCH, True, V.TRANSPORT_FAILED, {}, V.S10_SCRATCH,
             V.STOP_ADJUDICATION),
            ("malformed HELD", V.W10_MALFORMED, V.HS_MALFORMED, True, V.HELD_RETURNED_NOT_EXACT, {}, V.S10_HALT,
             V.HALT_PERMANENT),
            ("misbound HELD", V.W10_MISBOUND, V.HS_MISBOUND, True, V.HELD_RETURNED_NOT_EXACT, {}, V.S10_HALT,
             V.HALT_PERMANENT),
            ("duplicate / extra records", V.W10_UNEXPECTED, V.HS_UNEXPECTED, True, V.REFUSED_BEFORE_WRITE, {},
             V.S10_HALT, V.HALT_PERMANENT),
            ("valid HELD, POST failed", V.W10_1, V.HS_HELD_EXACT, True, V.HELD_RETURNED_EXACT, {"post_failed": True},
             V.S10_POST_NOT_VERIFIED, V.STOP_ADJUDICATION),
            ("valid HELD, POST verified", V.W10_1, V.HS_HELD_EXACT, True, V.HELD_RETURNED_EXACT,
             {"post_verified": True}, V.S10_POST_VERIFIED, V.CONTINUE),
            ("valid HELD, POST verified, adoption", V.W10_1, V.HS_HELD_EXACT, True, V.TRANSPORT_FAILED,
             {"post_verified": True, "adoption_required": True}, V.S10_ADOPTION, V.CONTINUE),
            ("valid HELD, DR-5 mismatch", V.W10_1, V.HS_HELD_EXACT, True, V.HELD_RETURNED_EXACT,
             {"post_verified": True, "accepted": True, "dr5": "DRIFT"}, V.S10_DR5_DRIFT, V.STOP_ADJUDICATION),
            ("accepted, DR-5 EQUAL", V.W10_1, V.HS_HELD_EXACT, True, V.HELD_RETURNED_EXACT,
             {"post_verified": True, "accepted": True, "dr5": "EQUAL"}, V.S10_ACCEPTED, V.CONTINUE),
            ("host drift after marker, nothing written", V.W10_WITNESS, V.HS_EMPTY, True, V.TRANSPORT_FAILED, {},
             V.S10_R_DRIFT, V.ENDS_REVALIDATE),
            ("host drift after marker, HELD exact", V.W10_WITNESS, V.HS_HELD_EXACT, True, V.HELD_RETURNED_EXACT, {},
             V.S10_HELD_DRIFT, V.STOP_ADJUDICATION),
            ("signer after marker, HELD exact", V.W10_LATER, V.HS_HELD_EXACT, True, V.HELD_RETURNED_EXACT, {},
             V.S10_HELD_DRIFT, V.STOP_ADJUDICATION),
            ("witness stopped, HELD exact", V.W10_1S, V.HS_HELD_EXACT, True, V.HELD_RETURNED_EXACT, {},
             V.S10_WITNESS_STOPPED, V.STOP_ADJUDICATION),
            ("HELD without any marker", V.W10_1, V.HS_HELD_EXACT, False, V.NOT_INVOKED, {}, V.S10_UNEXPLAINED,
             V.HALT_PERMANENT),
            ("HELD after a marker with no recorded invocation", V.W10_1, V.HS_HELD_EXACT, True, V.NOT_INVOKED, {},
             V.S10_UNEXPLAINED, V.HALT_PERMANENT),
            ("malformed without marker", V.W10_MALFORMED, V.HS_MALFORMED, False, V.NOT_INVOKED, {}, V.S10_HALT,
             V.HALT_PERMANENT),
            ("claimed success, store empty", V.W10_0, V.HS_EMPTY, True, V.HELD_RETURNED_EXACT, {}, V.S10_UNCLASSIFIED,
             V.READ_BACK),
            ("unknown host", V.UNCLASSIFIED, V.HS_UNREADABLE, True, V.TRANSPORT_FAILED, {}, V.S10_UNCLASSIFIED,
             V.READ_BACK),
        ]
        for case, host, hold, marker, transcript, extra, phase, disposition in cases:
            got = self.seq(host, hold, marker, transcript, **extra)
            self.assertEqual(got, phase, case)
            self.assertEqual(V.SEQUENCE_TABLE[got][0], disposition, case)

    def test_unknown_inputs_are_never_success(self):
        self.assertEqual(self.seq("W9_5_GENESIS_COMMITTED_EXACT", V.HS_EMPTY), V.S10_UNCLASSIFIED)
        self.assertEqual(self.seq(V.W10_1, "SOMETHING"), V.S10_UNCLASSIFIED)
        self.assertEqual(self.seq(V.W10_1, V.HS_HELD_EXACT, transcript="PASS"), V.S10_UNCLASSIFIED)

    def test_every_state_has_one_of_the_named_dispositions(self):
        dispositions = {V.ENDS_LINKED_SUCCESSOR, V.ENDS_REVALIDATE, V.CONTINUE, V.READ_BACK, V.STOP_ADJUDICATION,
                        V.HALT_PERMANENT}
        self.assertTrue(all(value[0] in dispositions for value in V.SEQUENCE_TABLE.values()))
        self.assertTrue(all(value[0] in (V.PROCEED_BY_GATE_AND_GO, V.SAFE_ADOPT, V.SAFE_RESTART, V.STOP_REVALIDATE,
                                         V.STOP_OWNER_ADJUDICATION, V.HALT) for value in V.PHASE_TABLE.values()))
        self.assertEqual(set(V.PHASE_TABLE), set(V.HOST_PHASES))
        self.assertTrue(all(V.PHASE_TABLE[phase][0] == V.HALT for phase in V.HALT_PHASES))


# -------------------------------------------------------------------------- hold-store observer ---

@unittest.skipUnless(POSIX, "POSIX owner / mode semantics")
class HoldStoreObservationTests(P9.Redacted, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.parent = self.root / V.HOLD_PARENT.lstrip("/")
        self.store = self.parent / "holds"
        self.store.mkdir(parents=True)
        os.chmod(self.parent, 0o700)
        os.chmod(self.store, 0o700)
        self.held = V.pinned_expected_held(GENESIS)

    def put(self, name: str, data: bytes, mode=0o600, where=None) -> Path:
        path = (where or self.store) / name
        path.write_bytes(data)
        os.chmod(path, mode)
        return path

    def observe(self):
        return V.observe_hold_store(self.root, self.held, owner=(UID, GID))

    def test_empty_exact_and_scratch(self):
        self.assertEqual(self.observe()["holdClass"], V.HS_EMPTY)
        scratch = self.put(V.scratch_name(self.held), self.held["bytes"][:10], where=self.parent)
        self.assertEqual(self.observe()["holdClass"], V.HS_SCRATCH)
        self.put(self.held["name"], self.held["bytes"])
        self.assertEqual(self.observe()["holdClass"], V.HS_UNSAFE)                    # unreachable combination
        scratch.unlink()
        report = self.observe()
        self.assertEqual(report["holdClass"], V.HS_HELD_EXACT)
        self.assertEqual(report["entries"][self.held["name"]]["sha256"], V.EXPECTED_HELD_SHA256)

    def test_metadata_and_set_violations(self):
        self.put(self.held["name"], self.held["bytes"], mode=0o644)
        self.assertEqual(self.observe()["holdClass"], V.HS_MALFORMED)
        os.chmod(self.store / self.held["name"], 0o600)
        self.put("0" * 64 + ".json", self.held["bytes"])
        self.assertEqual(self.observe()["holdClass"], V.HS_UNEXPECTED)
        (self.store / ("0" * 64 + ".json")).unlink()
        os.link(self.store / self.held["name"], self.parent / "hardlink")
        self.assertEqual(self.observe()["holdClass"], V.HS_UNSAFE)                    # foreign parent entry
        (self.parent / "hardlink").unlink()
        os.chmod(self.store, 0o755)
        self.assertEqual(self.observe()["holdClass"], V.HS_UNSAFE)
        os.chmod(self.store, 0o700)
        (self.store / self.held["name"]).unlink()
        os.symlink("/etc/passwd", self.store / self.held["name"])
        self.assertEqual(self.observe()["holdClass"], V.HS_MALFORMED)

    def test_a_missing_store_is_unsafe_never_empty(self):
        self.store.rmdir()
        self.assertEqual(self.observe()["holdClass"], V.HS_UNSAFE)

    @unittest.skipUnless(HAVE_CRYPTO, "diagnosis uses the release contract")
    def test_content_diagnosis(self):
        from lilith_owner_memory import successor_custody as SC

        pretty = json.dumps(self.held["record"], sort_keys=True, indent=1).encode()
        path = self.put(self.held["name"], pretty)
        self.assertEqual(self.observe()["holdClass"], V.HS_MALFORMED)                 # not the canonical bytes
        path.write_bytes(V.pinned_expected_held("1" * 64)["bytes"])
        self.assertEqual(self.observe()["holdClass"], V.HS_MISBOUND)
        released = dict(self.held["record"], state=SC.RELEASED, reason=SC.OWNER_RELEASE_AFTER_ELIGIBILITY)
        path.write_bytes(SC.hold_record_bytes(released))
        self.assertEqual(self.observe()["holdClass"], V.HS_UNEXPECTED)
        path.write_bytes(b"not json")
        self.assertEqual(self.observe()["holdClass"], V.HS_MALFORMED)


# ---------------------------------------------------------------------- verifier (seamed W9) ---

def w9_stub(base_phase="W9_5_GENESIS_COMMITTED_EXACT", *, consult=True, signer=False, committed=GENESIS):
    def evaluate(head, candidate, updated_at, *, root, **_kw):
        holds = V.V6._listing(Path(root), W9.HOLD_STORE) if consult else []
        phase = W9.LATER_STATE if (holds != [] or signer) else base_phase
        return {"phase": phase, "committedGenesis": {"digest": committed}, "witnessInvocationId": "a" * 32,
                "witnessMainPid": "1580", "witnessNRestarts": "0", "runtime": "RUNNING",
                "units": {name: {"ActiveState": "active" if signer else "inactive"} for name in W9.SIGNER_UNITS},
                "signerLaterState": {"/run/lilith-authority-dev/owner.sock": signer}, "failures": []}
    return evaluate


@unittest.skipUnless(POSIX and HAVE_CRYPTO, "POSIX modes and the release contract")
class VerifierTests(HoldStoreObservationTests):
    def evaluate(self, w9=None, canonical=None):
        names = sorted(os.listdir(self.store))
        cross = canonical or (lambda root, owner: {"observed": True, "entries": names})
        return V.evaluate(P9.HEAD, GENESIS, P9.ACCEPTED_UPDATED_AT, root=self.root, owner_uid=UID, owner_gid=GID,
                          w9=w9 or w9_stub(), canonical=cross)

    def test_empty_store_is_w10_0_and_held_is_w10_1(self):
        report = self.evaluate()
        self.assertEqual((report["phase"], report["holdClass"], report["w9PhaseDirect"]),
                         (V.W10_0, V.HS_EMPTY, "W9_5_GENESIS_COMMITTED_EXACT"))
        self.put(self.held["name"], self.held["bytes"])
        report = self.evaluate()
        self.assertEqual((report["phase"], report["w9PhaseDirect"], report["w9PhaseHoldJudgedSeparately"]),
                         (V.W10_1, W9.LATER_STATE, "W9_5_GENESIS_COMMITTED_EXACT"))
        self.assertEqual(report["observedHeldSha256"], V.EXPECTED_HELD_SHA256)
        self.assertEqual((report["heldGrantsAuthority"], report["issuanceAuthority"], report["authorityGranted"],
                          report["registryEffective"], report["authorityActive"]), (False, "NONE", False, False, False))
        self.assertEqual(self.evaluate(w9=w9_stub("W9_5S_GENESIS_COMMITTED_STOPPED"))["phase"], V.W10_1S)

    def test_disagreements_and_unknowns_are_unclassified(self):
        self.put(self.held["name"], self.held["bytes"])
        self.assertEqual(self.evaluate(w9=w9_stub(consult=False))["phase"], V.UNCLASSIFIED)   # seam not consulted
        self.assertEqual(self.evaluate(canonical=lambda r, o: {"observed": False, "reason": "HOLD_STORE_BUSY"})["phase"],
                         V.UNCLASSIFIED)
        self.assertEqual(self.evaluate(canonical=lambda r, o: {"observed": True, "entries": []})["phase"],
                         V.UNCLASSIFIED)
        self.assertEqual(self.evaluate(w9=w9_stub("W9_LATER_STATE"))["phase"], V.W10_LATER)
        (self.store / self.held["name"]).unlink()
        self.assertEqual(self.evaluate(canonical=lambda r, o: {"observed": False, "reason": "X"})["phase"],
                         V.UNCLASSIFIED)
        self.assertEqual(self.evaluate(w9=w9_stub("UNCLASSIFIED_STOP"))["phase"], V.UNCLASSIFIED)

    def test_witness_and_signer_drift(self):
        self.assertEqual(self.evaluate(w9=w9_stub("W9_4_COMMITTED_POINTER_PENDING"))["phase"], V.W10_WITNESS)
        self.assertEqual(self.evaluate(w9=w9_stub("W9_5S_GENESIS_COMMITTED_STOPPED"))["phase"], V.W10_WITNESS)
        self.assertEqual(self.evaluate(w9=w9_stub(committed="1" * 64))["phase"], V.W10_WITNESS)
        self.assertEqual(self.evaluate(w9=w9_stub(signer=True))["phase"], V.W10_LATER)

    def test_invalid_hold_content_dominates_and_halts(self):
        self.put(self.held["name"], V.pinned_expected_held("1" * 64)["bytes"])
        for w9 in (w9_stub(), w9_stub("W9_4_COMMITTED_POINTER_PENDING"), w9_stub(signer=True)):
            report = self.evaluate(w9=w9)
            self.assertEqual(report["phase"], V.W10_MISBOUND)
            self.assertEqual(report["routing"], V.HALT)
        self.put(V.scratch_name(self.held), b"", where=self.parent)
        self.assertEqual(self.evaluate()["phase"], V.W10_FOREIGN)


# --------------------------------------------------------------------------------- denial proof ---

def _st(kind, mode, uid=0, gid=0, nlink=1):
    return os.stat_result((kind | mode, 1, 1, nlink, uid, gid, 0, 0, 0, 0))


class HoldDenialProofTests(P9.Redacted, unittest.TestCase):
    def fs(self):
        return {DP.HOLD_PARENT: _st(stat.S_IFDIR, 0o700), DP.HOLD_STORE: _st(stat.S_IFDIR, 0o700),
                DP.HELD: _st(stat.S_IFREG, 0o600)}

    def prove(self, run=lambda argv: 1, fs=None, listing=None, units=None, activation=None, euid=0):
        lines = []
        fs = fs if fs is not None else self.fs()
        listing = listing or {DP.HOLD_PARENT: ["holds"], DP.HOLD_STORE: [DP.HELD_NAME]}
        state = units or {**dict.fromkeys(DP.WITNESS_UNITS, "active"), **dict.fromkeys(DP.SIGNER_UNITS, "inactive")}
        ok = DP.prove("P1B-10", run=run, lstat=fs.get, listdir=lambda p: listing.get(p, []), accounts=lambda: True,
                      unit_state=state.get, activation=activation or (lambda: (1, DP.GRANT_ABSENT + " x\n")),
                      euid=lambda: euid, say=lines.append)
        return ok, lines

    def test_pass_denies_every_principal_everywhere(self):
        calls = []
        ok, lines = self.prove(run=lambda argv: calls.append(argv) or 1)
        self.assertTrue(ok, lines)
        self.assertEqual(DP.EXPECTED_DENIED, 40)
        self.assertEqual(lines[-1], "MB10_HOLD_DENIAL_PROOF=PASS phase=P1B-10 denied=40 allowed=0")
        self.assertEqual(len(calls), 40)
        self.assertFalse(any("ALLOWED_BY_DESIGN" in line for line in lines))
        self.assertIn(DP.SCOPE_LINE, lines)

    def test_any_access_or_doubt_fails(self):
        self.assertFalse(self.prove(run=lambda argv: 0)[0])
        self.assertFalse(self.prove(run=lambda argv: 2)[0])
        self.assertFalse(self.prove(euid=1000)[0])
        self.assertEqual(DP.main([]), 2)

    def test_preconditions_stop_before_any_probe(self):
        calls = []
        run = lambda argv: calls.append(argv) or 1  # noqa: E731
        variants = [
            dict(listing={DP.HOLD_PARENT: ["holds"], DP.HOLD_STORE: []}),
            dict(listing={DP.HOLD_PARENT: ["holds", ".x.tmp"], DP.HOLD_STORE: [DP.HELD_NAME]}),
            dict(fs={**self.fs(), DP.HELD: _st(stat.S_IFREG, 0o644)}),
            dict(fs={**self.fs(), DP.HELD: _st(stat.S_IFREG, 0o600, nlink=2)}),
            dict(units={**dict.fromkeys(DP.WITNESS_UNITS, "active"), DP.SIGNER_UNITS[0]: "active",
                        DP.SIGNER_UNITS[1]: "inactive"}),
            dict(activation=lambda: (0, "ACTIVATION=ACCEPTED\n")),
        ]
        for variant in variants:
            ok, lines = self.prove(run=run, **variant)
            self.assertFalse(ok, variant)
            self.assertTrue(lines[-1].endswith("reason=PRECONDITION probes=0"), lines[-1])
        self.assertEqual(calls, [])


# ------------------------------------------------------------------------------ owner eligibility ---

SEQ = "f" * 32


def eligible_facts(**changes):
    facts = {"mb10Sequence": SEQ, "mb10OpenedAt": "2026-10-10T09:00:00Z",
             "exportReceipt": {"sequenceId": SEQ}, "exportReceiptSha256": "a" * 64,
             "s25Record": {"sequenceId": SEQ, "recordedAt": "2026-10-10T09:02:00Z", "transcriptionSha256": "b" * 64},
             "s25RecordSha256": "c" * 64, "s25": {"exact": True, "transcriptionSha256": "b" * 64},
             "sequenceId": E.SEQUENCE, "c5AcceptanceSha256": E.C5_ACCEPTANCE_SHA256, "stopPresent": False,
             "bindingSha256": E.BINDING_SHA256, "replicaADigests": [E.RECORD_1], "replicaAId": E.REPLICA_A_ID,
             "storeADigests": [E.ENVELOPE_1], "storeACustody": E.REPLICA_A_ID,
             "freshness": ["AUTHENTIC", "CURRENT"], "acceptance": "ACCEPTANCE_COMPLETE", "pendingFiles": 0,
             "freshChainSha256": E.CHAIN_1_SHA256, "freshPointerSha256": E.CHAIN_1_SHA256,
             "freshChainEqualsBinding": True}
    facts.update(changes)
    return facts


def s25_lines(sequence=SEQ):
    return E.s25_expected(sequence, a_tree="1" * 64, store_tree="2" * 64, record_file_sha256="3" * 64,
                          envelope_file_sha256="4" * 64)


def transcription(lines) -> str:
    return "\n".join(lines) + "\nRESULT_BLOCK_SHA256=" + E.result_block_sha256(lines) + "\n"


class OwnerEligibilityTests(P9.Redacted, unittest.TestCase):
    def test_eligible_only_when_every_fact_is_exact(self):
        self.assertEqual(E.judge(eligible_facts()), {"result": E.ELIGIBLE, "reasons": []})
        drift = {
            "freshness": (["AUTHENTIC", "FRESHNESS_UNKNOWN"], "FRESHNESS_NOT_AUTHENTIC_CURRENT"),
            "acceptance": ("ACCEPTANCE_PARTIAL", "ACCEPTANCE_NOT_COMPLETE"),
            "replicaADigests": ([E.RECORD_1, "0" * 64], "REPLICA_A_NOT_RECORD_1_ONLY"),
            "storeADigests": (["0" * 64], "STORE_A_NOT_ENVELOPE_1_ONLY"),
            "freshChainSha256": ("0" * 64, "FRESH_CHAIN_NOT_THE_COMMITTED_GENESIS"),
            "freshChainEqualsBinding": (False, "FRESH_CHAIN_NOT_THE_BOUND_CHAIN"),
            "pendingFiles": (1, "PENDING_FILES"),
            "c5AcceptanceSha256": ("0" * 64, "C5_NOT_THE_ACCEPTED_RECORD"),
            "stopPresent": (True, "PACKAGE_C_STOPPED"),
            "bindingSha256": ("0" * 64, "BINDING_CHANGED"),
            "exportReceipt": ({"sequenceId": "e" * 32}, "EXPORT_NOT_OF_THIS_SEQUENCE"),
            "s25": ({"exact": False, "transcriptionSha256": "b" * 64}, "S25_OBSERVATION_NOT_EXACT"),
        }
        for name, (value, reason) in drift.items():
            self.assertEqual(E.judge(eligible_facts(**{name: value})), {"result": E.REVALIDATE, "reasons": [reason]},
                             name)

    def test_the_fresh_s25_observation_is_bound_to_this_sequence_after_d1(self):
        record = {"sequenceId": SEQ, "recordedAt": "2026-10-10T08:59:59Z", "transcriptionSha256": "b" * 64}
        self.assertEqual(E.judge(eligible_facts(s25Record=record))["reasons"], ["S25_NOT_AFTER_D1"])
        self.assertEqual(E.judge(eligible_facts(s25Record=dict(record, sequenceId="e" * 32)))["reasons"],
                         ["S25_NOT_OF_THIS_SEQUENCE"])
        self.assertEqual(E.judge(eligible_facts(s25={"exact": True, "transcriptionSha256": "d" * 64}))["reasons"],
                         ["S25_TRANSCRIPTION_NOT_THE_RECORDED_ONE"])
        self.assertIn("UNKNOWN:s25", E.judge(eligible_facts(s25=None))["reasons"])

    def test_the_s25_expectation_and_comparison(self):
        lines = s25_lines()
        self.assertEqual(lines[:2], ["MB10_S25_STAGE=MB10_PRE", f"MB10_SEQUENCE={SEQ}"])
        for needed in (f"REPLICA_B_HEAD={E.RECORD_1}", "REPLICA_B_RECORDS=1", f"STORE_B_FILE=000001-{E.ENVELOPE_1}.json",
                       "STORE_B_ENVELOPES=1", "PENDING=0", "FRESHNESS=AUTHENTIC:CURRENT", "ACCEPTANCE=ACCEPTANCE_COMPLETE",
                       f"BUNDLE_SHA256={O.S25_BUNDLE_SHA256}", f"CHAIN_GENESIS={GENESIS}"):
            self.assertIn(needed, lines)
        self.assertTrue(E.s25_check(lines, transcription(lines))["exact"])
        for bad in (transcription(lines).replace("PENDING=0", "PENDING=1"),
                    transcription(lines).replace("FRESHNESS=AUTHENTIC:CURRENT", "FRESHNESS=AUTHENTIC:FRESHNESS_UNKNOWN"),
                    transcription(s25_lines("e" * 32)), "\n".join(lines) + "\n"):
            self.assertFalse(E.s25_check(lines, bad)["exact"])

    def test_unknown_is_revalidate_never_eligibility(self):
        facts = eligible_facts()
        del facts["acceptance"]
        self.assertEqual(E.judge(facts)["reasons"], ["UNKNOWN:acceptance"])
        facts = eligible_facts(freshness=None, unknown=["freshness:OSError:"])
        self.assertEqual(E.judge(facts), {"result": E.REVALIDATE, "reasons": ["UNKNOWN:freshness:OSError:"]})

    def test_gather_records_any_failure_as_unknown(self):
        class Broken:
            def __getattr__(self, name):
                raise OSError(name)

        with tempfile.TemporaryDirectory() as tmp:
            facts = E.gather(Path(tmp), "01-x", "01-MB10_PRE", Path(tmp), Path(tmp), Path(tmp), pkgc=Broken())
        self.assertTrue(facts["unknown"])
        self.assertEqual(E.judge(facts)["result"], E.REVALIDATE)

    def test_evaluate_writes_one_new_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "eligibility.json"
            args = (Path(tmp), "01-aa", "01-MB10_PRE", Path(tmp), Path(tmp), Path(tmp))
            with mock.patch.object(E, "gather", lambda *a, **k: eligible_facts()):
                result = E.evaluate(*args, out, now=lambda: NOW)
                self.assertEqual(result["result"], E.ELIGIBLE)
                record = json.loads(out.read_text())
                self.assertEqual((record["exportName"], record["s25Name"], record["sequenceId"], record["observedAt"],
                                  record["authorityGranted"]), ("01-aa", "01-MB10_PRE", SEQ, "2026-10-10T09:00:00Z", False))
                with self.assertRaises(E.Refused) as caught:
                    E.evaluate(*args, out)
                self.assertEqual(caught.exception.reason, "OUTPUT_EXISTS")
            with self.assertRaises(E.Refused):
                E.evaluate(Path(tmp), "../x", "01-MB10_PRE", Path(tmp), Path(tmp), Path(tmp), Path(tmp) / "y.json")

    def test_the_pkgc_operator_is_hash_gated(self):
        self.assertEqual(sha((TOOLS / "pkgc_operator.py").read_bytes()), E.PKGC_OPERATOR_SHA256)
        with mock.patch.object(E, "PKGC_OPERATOR_SHA256", "0" * 64):
            with self.assertRaises(E.Refused):
                E.load_pkgc()


# ---------------------------------------------------------------------------------- S25 phone stage ---

PHONE = (ROOT / O.MB10_PHONE).read_text(encoding="utf-8")


class PhoneStageTests(P9.Redacted, unittest.TestCase):
    def test_the_phone_stage_is_read_only(self):
        self.assertNotIn("\r", PHONE)
        body = "\n".join(line for line in PHONE.splitlines() if not line.lstrip().startswith("#"))
        for forbidden in ("T append", "append-envelope", "init-acceptance-store", "init-replica", "propose-", " rm ",
                          "rm -", "rmdir", " mv ", "set -C", "> \"$MB10_RB", "> \"$MB10_SB", "> \"$MB10_PB"):
            self.assertNotIn(forbidden, body, forbidden)
        for read_only in ("T verify-replica --replica \"$MB10_RB\"", "T verify-acceptance-store --store \"$MB10_SB\"",
                          "T classify --replica", "T classify-acceptance --replica"):
            self.assertIn(read_only, body)
        self.assertIn('mkdir -m 700 "$e" || { mb10_stop "this sequence\'s observation already ran"', body)

    def test_the_phone_emits_the_expected_lines_in_order(self):
        block = PHONE.split("lines+=(", 1)[1].split("printf '%s", 1)[0]
        emitted = re.findall(r'"([A-Z][A-Z0-9_]*)(?:=|")', block)
        expected = [line.split("=", 1)[0] for line in s25_lines()]
        self.assertEqual(emitted, expected)

    def test_render_gives_copy_paste_ready_phone_commands(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        work = Path(tmp.name)
        P9.C.write_emitted(P9.synthetic_derivation(), work / "genesis")
        op = O.Operator(gcloud=("gcloud",), run=FakeRun10(), now=lambda: NOW)
        facts = work / "facts.json"
        facts.write_text(json.dumps({"lastDeployRunId": "1", "workflowQueueEmpty": True, "predecessorWorkdir": None}))
        statement = work / "d1.txt"
        statement.write_text(op.render(ROOT, work, "D1", facts)["text"])
        sequence = op.open(ROOT, work, statement, facts)["sequenceId"]
        text = op.render(ROOT, work, "S25")["text"]
        self.assertIn(f"MB10_SEQUENCE={sequence}\n", text)
        self.assertIn(f"PKGC_BUNDLE_SHA256={O.S25_BUNDLE_SHA256}\n", text)
        self.assertIn(O.TOOL_PINS[O.MB10_PHONE], text)
        self.assertNotIn("<", text)
        with self.assertRaises(O.Stop) as caught:
            bad = work / "t.txt"
            bad.write_text("\n".join(s25_lines("e" * 32)))
            op.s25_record(ROOT, work, bad)
        self.assertEqual(caught.exception.code, "TRANSCRIPTION_NOT_OF_THIS_SEQUENCE")


# --------------------------------------------------------------------------------- scratch recovery ---

@unittest.skipUnless(POSIX, "POSIX owner / mode semantics")
class ScratchRecoveryTests(P9.Redacted, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.parent = self.root / SR.HOLD_PARENT.lstrip("/")
        (self.parent / "holds").mkdir(parents=True)
        os.chmod(self.parent, 0o700)
        os.chmod(self.parent / "holds", 0o700)
        self.owner = (UID, GID)

    def scratch(self, data=None, mode=0o600) -> Path:
        path = self.parent / SR.SCRATCH_NAME
        path.write_bytes(SR.expected_bytes()[:200] if data is None else data)
        os.chmod(path, mode)
        return path

    def test_the_expected_bytes_are_the_verifier_s(self):
        self.assertEqual(SR.expected_bytes(), V.pinned_expected_held(GENESIS)["bytes"])
        self.assertEqual(SR.SCRATCH_NAME, V.scratch_name(V.pinned_expected_held(GENESIS)))

    def test_plan_then_recover_exactly_the_writer_scratch(self):
        self.scratch()
        planned = SR.plan(root=self.root, owner=self.owner)
        self.assertEqual((planned["size"], planned["holdStore"], planned["canonicalHeld"], planned["complete"]),
                         (200, "EMPTY", "ABSENT", False))
        with self.assertRaises(SR.Refused) as caught:
            SR.recover("0" * 64, root=self.root, owner=self.owner)
        self.assertEqual(caught.exception.reason, "PLAN_CHANGED")
        self.assertTrue((self.parent / SR.SCRATCH_NAME).exists())
        result = SR.recover(planned["planDigest"], root=self.root, owner=self.owner)
        self.assertEqual((result["result"], result["heldWritten"]), ("MB10_SCRATCH_RECOVERED", False))
        self.assertEqual(sorted(os.listdir(self.parent)), ["holds"])
        with self.assertRaises(SR.Refused):                                         # nothing left to recover
            SR.recover(planned["planDigest"], root=self.root, owner=self.owner)

    def test_anything_else_is_refused_and_untouched(self):
        cases = []
        self.scratch(data=b"{\"not\":\"the record\"}")
        cases.append("SCRATCH_BYTES_NOT_A_PREFIX_OF_THE_EXPECTED_HELD")
        for reason in cases:
            with self.assertRaises(SR.Refused) as caught:
                SR.plan(root=self.root, owner=self.owner)
            self.assertEqual(caught.exception.reason, reason)
        self.scratch(mode=0o644)
        with self.assertRaises(SR.Refused) as caught:
            SR.plan(root=self.root, owner=self.owner)
        self.assertEqual(caught.exception.reason, "SCRATCH_METADATA_NOT_THE_WRITER_FORM")
        self.scratch(data=SR.expected_bytes() + b"x")
        with self.assertRaises(SR.Refused):
            SR.plan(root=self.root, owner=self.owner)
        self.scratch()
        held = self.parent / "holds" / SR.EXPECTED_HELD_NAME
        held.write_bytes(SR.expected_bytes())
        os.chmod(held, 0o600)
        with self.assertRaises(SR.Refused) as caught:                              # the canonical HELD exists
            SR.plan(root=self.root, owner=self.owner)
        self.assertEqual(caught.exception.reason, "HOLD_STORE_NOT_EMPTY")
        held.unlink()
        (self.parent / "other").write_bytes(b"")
        with self.assertRaises(SR.Refused) as caught:
            SR.plan(root=self.root, owner=self.owner)
        self.assertEqual(caught.exception.reason, "PARENT_NOT_EXACTLY_HOLDS_AND_THE_SCRATCH")
        self.assertTrue((self.parent / SR.SCRATCH_NAME).exists())


# ---------------------------------------------------------------------------------------- operator ---

HELD = V.pinned_expected_held(GENESIS)


def w10_report(phase="W10_0_PRE_HELD_EXACT", hold=None, witness=O.ACCEPTED_WITNESS, held_sha=None):
    hold = hold or {"W10_0_PRE_HELD_EXACT": "EMPTY", "W10_1_HELD_EXACT": "HELD_EXACT",
                    "W10_P_SCRATCH_RESIDUE_NOT_HELD": "SCRATCH_ONLY"}.get(phase, "EMPTY")
    return {"phase": phase, "holdClass": hold, "witnessInvocationId": witness[0], "witnessMainPid": witness[1],
            "witnessNRestarts": "0", "routing": V.PHASE_TABLE[phase][0],
            "w9PhaseDirect": "W9_LATER_STATE" if hold == "HELD_EXACT" else "W9_5_GENESIS_COMMITTED_EXACT",
            "w9PhaseHoldJudgedSeparately": "W9_5_GENESIS_COMMITTED_EXACT",
            "observedHeldSha256": held_sha if held_sha is not None else (HELD["sha256"] if hold == "HELD_EXACT" else None)}


PLAN = {"planDigest": "9" * 64, "scratch": SR.SCRATCH_NAME, "holdStore": "EMPTY", "canonicalHeld": "ABSENT"}


class FakeRun10:
    """git reads the worktree; remote commands answer by shape. Records every argv."""

    def __init__(self, w10=("W10_0_PRE_HELD_EXACT", "W10_1_HELD_EXACT"), hold=None, witness=O.ACCEPTED_WITNESS):
        self.calls: list[list[str]] = []
        self.w10 = list(w10)
        self.hold = hold or (0, V.expected_cli_stdout(HELD), b"")
        self.witness = witness
        self.on_hold = None

    def __call__(self, argv, input=None):                     # noqa: A002
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
        command = argv[-1] if argv and ("-proxycmd" in argv or argv[-1].startswith("--command=")) else ""
        if "mb10_held_verifier" in command:
            phase = self.w10.pop(0) if len(self.w10) > 1 else self.w10[0]
            rc = 0 if f"expect {phase}" in command or " observe " in command else 1
            return done(rc, json.dumps(w10_report(phase, witness=self.witness)).encode())
        if "create-initial-held" in command:
            if self.on_hold:
                self.on_hold()
            return done(*self.hold)
        if command.endswith(" - plan"):
            return done(0, json.dumps(PLAN).encode())
        if " - recover " in command:
            return done(0, json.dumps({"result": "MB10_SCRATCH_RECOVERED"}).encode())
        return done()

    def remote(self) -> list[str]:
        return [c[-1] for c in self.calls if c[-1].startswith("--command=") or "-proxycmd" in c]


class OperatorTests(P9.Redacted, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = self.new_work()
        self.facts = self.file({"lastDeployRunId": "38038318626", "workflowQueueEmpty": True,
                                "predecessorWorkdir": None})

    def new_work(self) -> Path:
        work = Path(tempfile.mkdtemp(dir=self.tmp.name))
        P9.C.write_emitted(P9.synthetic_derivation(), work / "genesis")
        return work

    def file(self, value, name=None) -> Path:
        path = Path(self.tmp.name) / (name or f"f-{len(os.listdir(self.tmp.name))}.json")
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def text(self, text: str) -> Path:
        path = Path(self.tmp.name) / f"t-{len(os.listdir(self.tmp.name))}.txt"
        path.write_text(text, encoding="utf-8")
        return path

    def op(self, run=None, now=NOW):
        return O.Operator(gcloud=("gcloud",), run=run or FakeRun10(), now=lambda: now)

    def opened(self, op, work=None, facts=None):
        work = work or self.work
        rendered = op.render(ROOT, work, "D1", facts or self.facts)
        op.open(ROOT, work, self.text(rendered["text"]), facts or self.facts)
        return json.loads((work / "sequence" / "D1_OPENING.json").read_text())

    def host_pre(self, opening, *, report=None, boot=O.ACCEPTED_BOOT_ID, result="MB10_HOST_PRE_PASS",
                 preservation=0):
        hosts = self.work / "host"
        name = f"{len(list(hosts.iterdir())) + 1 if hosts.is_dir() else 1:02d}-PRE"
        out = hosts / name
        out.mkdir(parents=True)
        (out / "HOST_RESULT.json").write_text(json.dumps({"sequenceId": opening["sequenceId"], "result": result,
                                                          "codes": {"preservation": preservation}}))
        (out / "w10verifier.out").write_text(json.dumps(report or w10_report()))
        (out / "identity.out").write_text(f"2026-10-10T09:01:00Z\nlilith-dev-01\nm\n{boot}\nk\nREBOOT_REQUIRED=absent\n")
        return name

    def export(self, opening, *, files=None, started="2026-10-10T09:02:00Z", sequence=None) -> tuple[str, str]:
        exports = self.work / "exports"
        name = f"{len(list(exports.iterdir())) + 1 if exports.is_dir() else 1:02d}-{os.urandom(4).hex()}"
        out = exports / name
        out.mkdir(parents=True)
        receipt = {"sequenceId": sequence or opening["sequenceId"], "startedAt": started,
                   "completedAt": "2026-10-10T09:03:00Z",
                   "files": files or {"chain-1.json": O.CHAIN_1_SHA256, "witness.json": O.CHAIN_1_SHA256}}
        (out / "RECEIPT.json").write_bytes(json.dumps(receipt).encode())
        return name, sha((out / "RECEIPT.json").read_bytes())

    def s25(self, op, opening, *, recorded=None) -> tuple[str, str]:
        path = self.text(transcription(s25_lines(opening["sequenceId"])))
        result = O.Operator(gcloud=("gcloud",), run=FakeRun10(),
                            now=lambda: recorded or datetime(2026, 10, 10, 9, 2, 30, tzinfo=timezone.utc)
                            ).s25_record(ROOT, self.work, path)
        return result["s25"], result["recordSha256"]

    def eligibility(self, opening, export, s25, **changes) -> Path:
        value = {"sequenceId": opening["sequenceId"], "result": E.ELIGIBLE, "reasons": [], "exportName": export[0],
                 "exportReceiptSha256": export[1], "s25Name": s25[0], "s25RecordSha256": s25[1],
                 "observedAt": "2026-10-10T09:04:00Z"}
        value.update(changes)
        return self.file(value)

    def gate(self, op, opening, *, host=None, export=None, s25=None, facts=None, **changes):
        host_dir = self.host_pre(opening, **(host or {}))
        export = self.export(opening, **(export or {}))
        s25 = self.s25(op, opening, **(s25 or {}))
        facts = self.file(facts or {"lastDeployRunId": "38038318626", "workflowQueueEmpty": True})
        return op.gate(ROOT, self.work, host_dir, self.eligibility(opening, export, s25, **changes), facts)

    def test_opening_is_read_only_and_starts_the_freeze(self):
        run = FakeRun10()
        op = self.op(run)
        rendered = op.render(ROOT, self.work, "D1", self.facts)
        for needed in ("Predecessor sequence: none.", V.EXPECTED_HELD_SHA256, "Freeze: BEGINS_AT_THIS_OPENING.",
                       "package or OS upgrade", "one fresh read-only S25 observation", "any S25 write"):
            self.assertIn(needed, rendered["text"])
        with self.assertRaises(O.Stop) as caught:
            op.open(ROOT, self.work, self.text(rendered["text"].replace("38038318626", "1")), self.facts)
        self.assertEqual(caught.exception.code, "GO_LINE_MISSING")
        self.assertFalse((self.work / "sequence").exists())
        opening = self.opened(op)
        self.assertEqual((opening["lastDeployRunId"], opening["predecessor"], opening["freeze"]),
                         ("38038318626", "none", "BEGINS_AT_THIS_OPENING"))
        self.assertEqual(op.freeze_state(self.work), "IN_FORCE")
        with self.assertRaises(O.Stop):
            op.open(ROOT, self.work, self.text(rendered["text"]), self.facts)
        self.assertEqual(run.remote(), [])

    def test_ordinary_staleness_revalidates(self):
        op = self.op()
        opening = self.opened(op)
        self.assertEqual(self.gate(op, opening)["result"], "MB10_GATE_PASS")
        ordinary = [
            ({"host": {"result": "MB10_HOST_PRE_NOT_PASS"}}, "HOST_PRE_NOT_PASS"),
            ({"result": E.REVALIDATE}, "OWNER_NOT_ELIGIBLE"),
            ({"export": {"files": {"chain-1.json": "0" * 64}}}, "EXPORT_NOT_GENESIS"),
            ({"export": {"started": "2026-10-10T08:00:00Z"}}, "ELIGIBILITY_NOT_AFTER_EXPORT"),
            ({"export": {"sequence": "e" * 32}}, "EXPORT_NOT_BOUND_TO_THIS_SEQUENCE"),
            ({"s25": {"recorded": datetime(2026, 10, 10, 9, 5, tzinfo=timezone.utc)}},
             "S25_NOT_AFTER_D1_OR_NOT_BEFORE_ELIGIBILITY"),
            ({"facts": {"lastDeployRunId": "38038318626"}}, "EVIDENCE_UNKNOWN"),
            ({"facts": {"lastDeployRunId": "38038318626", "workflowQueueEmpty": False}}, "WORKFLOW_QUEUE_NOT_EMPTY"),
        ]
        for kw, event in ordinary:
            result = self.gate(op, opening, **kw)
            self.assertEqual((result["result"], result["materialEvents"]), ("MB10_GATE_REVALIDATE", []), event)
            self.assertIn(event, result["events"])
        self.assertFalse((self.work / "sequence" / "ENDED.json").exists())
        with self.assertRaises(O.Stop) as caught:
            op.gate(ROOT, self.work, "01-PRE", self.file({}), self.facts)
        self.assertEqual(caught.exception.code, "HOST_READ_REUSED")

    def test_material_substrate_change_ends_the_sequence_and_keeps_the_freeze(self):
        material = [({"host": {"boot": "x"}}, "BOOT_CHANGED"),
                    ({"host": {"report": w10_report(witness=("b" * 32, "9"))}}, "WITNESS_INCARNATION_CHANGED"),
                    ({"host": {"preservation": 1, "result": "MB10_HOST_PRE_NOT_PASS"}}, "BROKER_PRESERVATION_NOT_PASS"),
                    ({"host": {"report": w10_report("W10_1_HELD_EXACT")}}, "HOST_NOT_W10_0"),
                    ({"facts": {"lastDeployRunId": "1", "workflowQueueEmpty": True}}, "DEPLOY_SINCE_OPENING")]
        for kw, event in material:
            with self.subTest(event=event):
                self.work = self.new_work()
                op = self.op()
                opening = self.opened(op)
                result = self.gate(op, opening, **kw)
                self.assertEqual(result["result"], "MB10_SEQUENCE_ENDED_MATERIAL_CHANGE")
                self.assertIn(event, result["materialEvents"])
                ended = json.loads((self.work / "sequence" / "ENDED.json").read_text())
                self.assertEqual(ended["freeze"], "IN_FORCE_UNTIL_STOP_OR_RELEASE")
                self.assertEqual(op.freeze_state(self.work), "IN_FORCE")
                for form in (lambda: op.render(ROOT, self.work, "D2"), lambda: self.gate(op, opening),
                             lambda: op.export(ROOT, self.work)):
                    with self.assertRaises(O.Stop) as caught:
                        form()
                    self.assertEqual(caught.exception.code, "SEQUENCE_ENDED")
                stop = op.render(ROOT, self.work, "STOP")["text"]           # only an explicit STOP releases it
                op.stop(ROOT, self.work, self.text(stop))
                self.assertEqual(op.freeze_state(self.work), "RELEASED_BY_STOP")

    def ready(self, run):
        op = self.op(run)
        opening = self.opened(op)
        self.assertEqual(self.gate(op, opening)["result"], "MB10_GATE_PASS")
        return op, self.text(op.render(ROOT, self.work, "D2")["text"])

    def holds(self, run):
        return [c for c in run.remote() if "create-initial-held" in c]

    def test_an_old_d2_bound_to_a_superseded_gate_is_refused(self):
        run = FakeRun10()
        op, old = self.ready(run)
        opening = json.loads((self.work / "sequence" / "D1_OPENING.json").read_text())
        first = sha(sorted((self.work / "gates").iterdir())[0].read_bytes())
        self.assertIn("superseded gates: none.", old.read_text())
        self.assertEqual(self.gate(op, opening)["result"], "MB10_GATE_PASS")
        with self.assertRaises(O.Stop) as caught:
            op.mb10(ROOT, self.work, old)
        self.assertEqual(caught.exception.code, "GO_BOUND_TO_SUPERSEDED_GATE")
        new = op.render(ROOT, self.work, "D2")["text"]
        self.assertIn(f"superseded gates: {first}.", new)
        self.assertEqual(self.holds(run), [])
        self.assertEqual(op.mb10(ROOT, self.work, self.text(new))["result"], "MB10_HELD")

    def test_mb10_one_marker_before_one_write_then_read_back(self):
        run = FakeRun10()
        op, go = self.ready(run)
        marker = self.work / "attempts" / "mb10.json"
        run.on_hold = lambda: self.assertTrue(marker.is_file())                 # the marker precedes the write
        result = op.mb10(ROOT, self.work, go)
        self.assertEqual((result["result"], result["transcript"], result["sequencePhase"], result["freeze"]),
                         ("MB10_HELD", V.HELD_RETURNED_EXACT, V.S10_POST_PENDING, "IN_FORCE"))
        self.assertEqual(len(self.holds(run)), 1)
        self.assertIn(O.HOLD_COMMAND, self.holds(run)[0])
        self.assertEqual(json.loads(marker.read_text())["invocationsPermitted"], 1)
        with self.assertRaises(O.Stop) as caught:                              # never a second attempt
            op.mb10(ROOT, self.work, go)
        self.assertEqual(caught.exception.code, "ATTEMPT_ALREADY_CONSUMED:mb10")
        self.assertEqual(len(self.holds(run)), 1)
        for act in ("STOP", "D2"):
            with self.assertRaises(O.Stop):
                op.render(ROOT, self.work, act)

    def test_mb10_refuses_before_any_marker(self):
        run = FakeRun10()
        op = self.op(run)
        opening = self.opened(op)
        with self.assertRaises(O.Stop) as caught:
            op.render(ROOT, self.work, "D2")
        self.assertEqual(caught.exception.code, "FRESH_GATE_REQUIRED")
        self.assertEqual(self.gate(op, opening)["result"], "MB10_GATE_PASS")
        text = op.render(ROOT, self.work, "D2")["text"]
        for bad in (text.replace(O.PONR_ACKNOWLEDGEMENT, ""), text.replace(V.EXPECTED_HELD_SHA256, "0" * 64),
                    text.replace(O.ACCEPTED_WITNESS[0], "c" * 32)):
            with self.assertRaises(O.Stop) as caught:
                op.mb10(ROOT, self.work, self.text(bad))
            self.assertEqual(caught.exception.code, "GO_LINE_MISSING")
        for w10, witness, code in ((("W10_1_HELD_EXACT",), O.ACCEPTED_WITNESS, "PRE_STATE_NOT_W10_0"),
                                   (("W10_0_PRE_HELD_EXACT",), ("d" * 32, "1"), "WITNESS_INCARNATION_CHANGED_SINCE_GATE")):
            stop = FakeRun10(w10=w10, witness=witness)
            with self.assertRaises(O.Stop) as caught:
                self.op(stop).mb10(ROOT, self.work, self.text(text))
            self.assertEqual(caught.exception.code, code)
            self.assertEqual(self.holds(stop), [])
        self.assertFalse((self.work / "attempts").exists())                     # nothing consumed
        self.assertEqual(self.holds(run), [])

    def test_post_marker_not_written_keeps_the_freeze_into_a_linked_successor(self):
        run = FakeRun10(w10=("W10_0_PRE_HELD_EXACT",),
                        hold=(2, b"", b"lilith-authority-hold-dev: REFUSED HOLD_WITNESS_NOT_CONSISTENT\n"))
        op, go = self.ready(run)
        result = op.mb10(ROOT, self.work, go)
        self.assertEqual((result["result"], result["sequencePhase"], result["freeze"]),
                         ("MB10_STOP", V.S10_R, "IN_FORCE"))
        self.assertEqual(len(self.holds(run)), 1)
        with self.assertRaises(O.Stop) as caught:                                 # never a STOP after the marker
            op.render(ROOT, self.work, "STOP")
        self.assertEqual(caught.exception.code, "STOP_REFUSED_ATTEMPT_MARKER_PRESENT")
        successor = self.new_work()
        facts = self.file({"lastDeployRunId": "38038318626", "workflowQueueEmpty": True,
                           "predecessorWorkdir": str(self.work)})
        with self.assertRaises(O.Stop) as caught:                                 # not classified yet
            op.render(ROOT, successor, "D1", facts)
        self.assertEqual(caught.exception.code, "PREDECESSOR_NOT_ENDED_WITHOUT_WRITE")
        classified = op.classify(ROOT, self.work)
        self.assertEqual((classified["sequencePhase"], classified["freeze"]), (V.S10_R, "IN_FORCE"))
        predecessor = sha((self.work / "sequence" / "D1_OPENING.json").read_bytes())
        rendered = op.render(ROOT, successor, "D1", facts)["text"]
        self.assertIn(f"Freeze: CONTINUES_UNBROKEN_FROM {predecessor}.", rendered)
        self.assertIn(f"Predecessor sequence: {predecessor}.", rendered)
        moved = self.file({"lastDeployRunId": "2", "workflowQueueEmpty": True, "predecessorWorkdir": str(self.work)})
        with self.assertRaises(O.Stop) as caught:
            op.render(ROOT, successor, "D1", moved)
        self.assertEqual(caught.exception.code, "DEPLOY_DURING_CONTINUOUS_FREEZE")
        # only the owner's explicit release ends the freeze after a consumed marker
        release = op.render(ROOT, self.work, "RELEASE")["text"]
        self.assertIn(V.S10_R, release)
        self.assertEqual(op.release_freeze(ROOT, self.work, self.text(release))["freeze"], "RELEASED_BY_OWNER")
        self.assertIn("Freeze: BEGINS_AT_THIS_OPENING.", op.render(ROOT, successor, "D1", moved)["text"])

    def test_held_without_exact_reply_is_adopted_only_through_post_and_d3(self):
        run = FakeRun10(w10=("W10_0_PRE_HELD_EXACT", "W10_1_HELD_EXACT"), hold=(None, b"", b""))
        op, go = self.ready(run)
        result = op.mb10(ROOT, self.work, go)
        self.assertEqual(result["sequencePhase"], V.S10_UNACKNOWLEDGED)
        classified = op.classify(ROOT, self.work)
        self.assertEqual(classified["records"]["adoption_required"], True)
        with self.assertRaises(O.Stop) as caught:                                 # never a release of HELD's freeze
            op.render(ROOT, self.work, "RELEASE")
        self.assertEqual(caught.exception.code, "NOT_A_CLASSIFIED_NOT_WRITTEN_OUTCOME")

    def test_scratch_residue_stops_and_only_the_authorized_recovery_removes_it(self):
        run = FakeRun10(w10=("W10_0_PRE_HELD_EXACT", "W10_P_SCRATCH_RESIDUE_NOT_HELD",
                             "W10_P_SCRATCH_RESIDUE_NOT_HELD", "W10_0_PRE_HELD_EXACT"), hold=(255, b"", b""))
        op, go = self.ready(run)
        self.assertEqual(op.mb10(ROOT, self.work, go)["sequencePhase"], V.S10_SCRATCH)
        with self.assertRaises(O.Stop) as caught:                                 # not classified yet
            op.scratch_plan(ROOT, self.work)
        self.assertEqual(caught.exception.code, "NOT_CLASSIFIED_SCRATCH")
        self.assertEqual(op.classify(ROOT, self.work)["sequencePhase"], V.S10_SCRATCH)
        planned = op.scratch_plan(ROOT, self.work)
        self.assertEqual((planned["result"], planned["planDigest"]), ("MB10_SCRATCH_PLAN_RECORDED", "9" * 64))
        text = op.render(ROOT, self.work, "SCRATCH", Path(planned["planDir"]))["text"]
        self.assertIn("9" * 64, text)
        self.assertFalse([c for c in run.remote() if " - recover " in c])          # nothing removed without the act
        with self.assertRaises(O.Stop):
            op.scratch_recover(ROOT, self.work, planned["planDir"], self.text(text.replace("9" * 64, "8" * 64)))
        result = op.scratch_recover(ROOT, self.work, planned["planDir"], self.text(text))
        self.assertEqual((result["result"], result["freeze"]), ("MB10_SCRATCH_RECOVERED", "IN_FORCE"))
        self.assertEqual(len([c for c in run.remote() if " - recover " in c]), 1)
        with self.assertRaises(O.Stop) as caught:
            op.scratch_recover(ROOT, self.work, planned["planDir"], self.text(text))
        self.assertTrue(caught.exception.code.startswith("ATTEMPT_ALREADY_CONSUMED:scratch-recovery-"))
        self.assertEqual(len(self.holds(run)), 1)                                 # never a second write

    def test_post_verifies_bytes_proofs_and_witness_then_acceptance_ends_the_freeze(self):
        chain = b'{"synthetic":"genesis"}'
        probe = {"modules": {str(i): [f, d] for i, (f, d) in enumerate({**M9.M6.RELEASE_MODULES,
                                                                         **M9.M6.PROVISION_MODULES}.items())},
                 "ledgerCli": M9.M6.LEDGER_CLI_SHA256, "verifyCli": M9.A.VERIFY_CLI_SHA256,
                 "witnessOwnerCli": M9.OWNER_CLI_SHA256, "release": "/opt/lilith-authority-dev/current",
                 "deserialize": True}

        class PostRun(FakeRun10):
            def __call__(inner, argv, input=None):                               # noqa: A002, N805
                command = list(argv)[-1]
                done = lambda out=b"": subprocess.CompletedProcess(list(argv), 0, out, b"")  # noqa: E731
                if "readlink /opt/lilith-authority-dev/current" in command:
                    inner.calls.append(list(argv))
                    return done((f"releases/{M9.RELEASE_SHA}\nRELEASE_PYTHON=executable\n" + json.dumps(probe)
                                 + "\n").encode())
                if "TMP_RESIDUE_END" in command:
                    inner.calls.append(list(argv))
                    return done(b"TMP_RESIDUE_END\n")
                if "owner-dev health" in command:
                    inner.calls.append(list(argv))
                    return done(P9.health_reply("CONSISTENT"))
                if "hold-dev observe" in command:
                    inner.calls.append(list(argv))
                    return done(json.dumps({"listingDigest": "e" * 64, "authorityGranted": False,
                                            "snapshot": {"entries": [HELD["name"]]}}).encode())
                if "base64 -w0" in command:
                    inner.calls.append(list(argv))
                    data = HELD["bytes"] if "holds/" in command else chain
                    return done(base64.b64encode(data))
                return FakeRun10.__call__(inner, argv, input)

        run = PostRun(w10=("W10_0_PRE_HELD_EXACT", "W10_1_HELD_EXACT"))
        op, go = self.ready(run)
        self.assertEqual(op.mb10(ROOT, self.work, go)["result"], "MB10_HELD")
        with self.assertRaises(O.Stop) as caught:
            op.render(ROOT, self.work, "D3")
        self.assertEqual(caught.exception.code, "POST10_NOT_VERIFIED")
        with mock.patch.object(O, "CHAIN_1_SHA256", sha(chain)):
            result = op.post(ROOT, self.work)
        self.assertEqual(result["result"], "MB10_POST_VERIFIED", result.get("checks"))
        for proof in ("P1B-10", "P1B-9b", "P1B-5"):
            self.assertTrue(any(f" - {proof}" in c for c in run.remote()), proof)
        self.assertEqual(len(self.holds(run)), 1)                                # POST never writes
        with self.assertRaises(O.Stop) as caught:
            op.post(ROOT, self.work)
        self.assertEqual(caught.exception.code, "POST10_ALREADY_VERIFIED")
        rendered = op.render(ROOT, self.work, "D3")
        self.assertNotIn(O.ADOPTION_LINE, rendered["text"])
        self.assertIn("The M-B10 freeze ends now", rendered["text"])
        self.assertEqual(op.freeze_state(self.work), "IN_FORCE")
        self.assertEqual(op.accept(ROOT, self.work, self.text(rendered["text"]))["result"], "MB10_ACCEPTED")
        self.assertEqual(op.freeze_state(self.work), "ENDED_BY_D3")

    def test_dr5_form_uses_the_post_held_target_only(self):
        op = self.op()
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "log.txt"
            log.write_text("\n".join(D.derive(accepted_sets(), SCRIPT)["targets"][D.RUNNING_HELD]["texts"]["result-set"])
                           + "\n")
            self.assertEqual(op.dr5(ROOT, "W10_1_HELD_EXACT", log)["result"], "EQUAL")
            with self.assertRaises(O.Stop):
                op.dr5(ROOT, "W9_5_GENESIS_COMMITTED_EXACT", log)


# ------------------------------------------------------------------------------- static boundary ---

class BoundaryTests(P9.Redacted, unittest.TestCase):
    SOURCES = {path: (ROOT / path).read_text(encoding="utf-8") for path in (O.OPERATOR, *NEW_TOOLS)}

    @staticmethod
    def code_strings(source: str) -> list[str]:
        """Every string constant that is code (docstrings excluded), f-string parts included."""
        tree = ast.parse(source)
        docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                      if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body
                      and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)}
        return [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)
                and isinstance(node.value, str) and id(node) not in docstrings]

    def test_exactly_two_mutation_paths_and_no_later_milestone(self):
        source = self.SOURCES[O.OPERATOR]
        tree = ast.parse(source)
        invokes = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "_invoke"]
        self.assertEqual(len(invokes), 2)
        self.assertEqual(source.count("self._invoke(HOLD_COMMAND)"), 1)
        self.assertEqual(source.count('self._invoke(self.streamed(repo, MB10_SCRATCH, M9.SYSTEM_PYTHON, f"recover '
                                      '{digest}"))'), 1)
        strings = self.code_strings(source)
        self.assertEqual(sorted(s for s in strings if "create-initial-held" in s),
                         [" create-initial-held", " create-initial-held, exactly one invocation."])
        for forbidden in ("release-initial", "create-successor-held", "create-maintenance-held",
                          "create-custody-debt-held", "release-ceremony", "systemctl start", "systemctl enable",
                          "systemctl restart", "execute-head-advance", "execute-epoch-advance", "advance-epoch",
                          "keygen", "systemd-creds", "bootstrap 1", "append-envelope", "init-acceptance-store"):
            self.assertFalse([s for s in strings if forbidden in s], forbidden)
        for path in NEW_TOOLS:
            strings = self.code_strings(self.SOURCES[path])
            self.assertFalse([s for s in strings if "create-initial-held" in s], path)   # only the operator writes
            self.assertFalse([s for s in strings if "systemctl start" in s or "release-initial" in s], path)

    def test_templates_bind_the_boundaries_and_the_accepted_decisions(self):
        go = flat(" ".join(O.GO_LINES))
        for needed in (O.PONR_ACKNOWLEDGEMENT, "exactly one invocation", "grants no issuance or other authority",
                       "does not authorize the signer (M-B11), authority activation, Registry V1 effectiveness, First "
                       "Memory or PROD", "there is no automatic retry, and the freeze stays in force",
                       "This go supersedes every earlier D2 of this sequence", "Fresh S25 observation SHA-256"):
            self.assertIn(needed, go)
        opening = flat(" ".join(O.OPEN_LINES))
        self.assertIn(O.FREEZE_RULES, opening)
        self.assertIn("Its normal end is the accepted D3; a pre-marker STOP or my explicit freeze release may end it "
                      "earlier.", opening)
        self.assertIn("It does not authorize M-B10, HELD, any S25 write, the signer, authority activation, First "
                      "Memory or PROD", opening)
        for word in ("merge", "deploy", "reboot", "witness restart", "broker restart", "package or OS upgrade",
                     "signer action", "Registry effectiveness", "authority activation"):
            self.assertIn(word, O.FREEZE_RULES)
        accept = flat(" ".join(O.ACCEPT_LINES))
        self.assertIn("authorizes nothing further: not the signer (M-B11), authority activation, First Memory or PROD",
                      accept)
        self.assertIn("REGISTRY_EFFECTIVE remains NO. AUTHORITY_ACTIVE remains NO. authorityGranted remains false.",
                      accept)
        self.assertIn("It authorizes no retry", flat(" ".join(O.RELEASE_LINES)))
        self.assertIn("this removal is not a retry of M-B10 and writes no HELD", flat(" ".join(O.SCRATCH_LINES)))
        for lines in (O.OPEN_LINES, O.GO_LINES, O.ACCEPT_LINES, O.STOP_LINES, O.RELEASE_LINES, O.SCRATCH_LINES):
            text = flat(" ".join(lines))
            self.assertNotIn("FIRST_MEMORY_READY", text)
            self.assertNotIn("authorize First Memory", text.replace("not authorize", ""))


# ------------------------------------------------------------------- the real writer (synthetic host) ---

@unittest.skipUnless(HAVE_CRYPTO and POSIX and hasattr(__import__("sqlite3").Connection, "deserialize"),
                     "POSIX owner/mode semantics, sqlite3 deserialize, cryptography/rfc8785/fido2 required")
class HeldHostTests(P9.WitnessHostTests):
    """The REAL release hold writer (`HoldStoreV1.create_initial_held`) on the synthetic root with a committed
    synthetic witness genesis, judged by the REAL W9 and W10 verifiers."""

    def w10(self) -> dict:
        with mock.patch.object(P9.socket, "socket", P9._no_socket), \
                mock.patch.object(P9.socket, "create_connection", P9._no_socket):
            return V.evaluate(self.head, self.digest, self.updated_at, root=self.root, owner_uid=UID, owner_gid=GID,
                              signer=self.signer_ids, witness=self.witness_ids, units=self.view, pins=self.pins,
                              trust_pins=self.trust_pins)

    def committed(self) -> None:
        self.started()
        self.bootstrap()
        self.assertEqual(self.w9()["phase"], W9.W9_5)

    def holds(self):
        from lilith_authority_root.hold_store import HoldStoreV1

        return HoldStoreV1(environment="dev", root=self.root, owner_uid=UID, owner_gid=GID)

    def write_held(self):
        from lilith_authority_host.store_observer import observe_witness_state

        _inputs, context = self.context()
        return self.holds().create_initial_held(witness_store=observe_witness_state(self.target(P9.P.WITNESS_STATE)),
                                                context=context)

    def test_w10_0_then_the_real_writer_reaches_w10_1_exactly(self):
        self.committed()
        before = self.w10()
        self.assertEqual((before["phase"], before["holdClass"], before["w9PhaseDirect"]),
                         (V.W10_0, V.HS_EMPTY, W9.W9_5), before["failures"])
        record = self.write_held()
        expected = V.expected_held(self.digest)
        self.assertEqual(record, expected["record"])
        after = self.w10()
        self.assertEqual((after["phase"], after["holdClass"], after["w9PhaseDirect"],
                          after["w9PhaseHoldJudgedSeparately"]), (V.W10_1, V.HS_HELD_EXACT, W9.LATER_STATE, W9.W9_5),
                         after["failures"])
        self.assertEqual(after["observedHeldSha256"], expected["sha256"])
        self.assertTrue(after["releaseObserver"]["observed"])
        self.assertEqual(self.w9()["phase"], W9.LATER_STATE)                     # the unchanged W9 judgement
        self.assertEqual(self.status("P1B-10")["result"], "PASS", self.status("P1B-10")["failures"])
        self.assertEqual(self.status("P1B-9b")["result"], "FAIL")              # the earlier stage no longer holds
        from lilith_authority_root.hold_store import HoldStoreError

        with self.assertRaises(HoldStoreError) as caught:                       # forward only: never a second HELD
            self.write_held()
        self.assertEqual(caught.exception.reason, "HOLD_STORE_NOT_EMPTY")
        self.set_runtime("STOPPED")
        self.assertEqual(self.w10()["phase"], V.W10_1S)

    def test_a_crash_before_the_rename_leaves_scratch_and_no_held(self):
        self.committed()
        from lilith_authority_root import hold_store as HS

        with mock.patch.object(HS.os, "rename", side_effect=OSError("simulated crash before rename")):
            with self.assertRaises(OSError):
                self.write_held()
        report = self.w10()
        self.assertEqual((report["phase"], report["holdClass"]), (V.W10_SCRATCH, V.HS_SCRATCH), report["failures"])
        with self.assertRaises(HS.HoldStoreError) as caught:                    # the scratch blocks every writer
            self.write_held()
        self.assertEqual(caught.exception.reason, "HOLD_PARENT_UNEXPECTED_ENTRY")
        # MB10_SCRATCH_RECOVERY (OD-M10-6) recognizes exactly this writer scratch and removes only it
        synthetic = V.expected_held(self.digest)
        with mock.patch.object(SR, "GENESIS", self.digest), \
                mock.patch.object(SR, "EXPECTED_HELD_SHA256", synthetic["sha256"]):
            planned = SR.plan(root=self.root, owner=(UID, GID))
            self.assertTrue(planned["complete"])
            self.assertEqual(SR.recover(planned["planDigest"], root=self.root, owner=(UID, GID))["result"],
                             "MB10_SCRATCH_RECOVERED")
        self.assertEqual(self.w10()["phase"], V.W10_0)
        self.write_held()                                                       # a linked successor's one write
        self.assertEqual(self.w10()["phase"], V.W10_1)

    def test_tampered_or_rebound_held_halts(self):
        self.committed()
        self.write_held()
        path = self.target(V.HOLD_STORE) / V.expected_held(self.digest)["name"]
        path.write_bytes(V.pinned_expected_held("1" * 64)["bytes"])
        self.assertEqual(self.w10()["phase"], V.W10_MISBOUND)
        path.write_bytes(b"{}")
        self.assertEqual(self.w10()["phase"], V.W10_MALFORMED)


for _name in [n for n in dir(P9.WitnessHostTests) if n.startswith("test")]:
    setattr(HeldHostTests, _name, None)                                        # run only the M-B10 host tests here
for _name in [n for n in dir(HoldStoreObservationTests) if n.startswith("test")]:
    if _name not in VerifierTests.__dict__:
        setattr(VerifierTests, _name, None)


# --------------------------------------------------------------------------------------- record ---

class RecordTests(P9.Redacted, unittest.TestCase):
    DECISIONS = "b76d9cf2e28c1f82af4b7b3c4302f7a90ce85774959d1e1aea4cc7d9ef33a641"

    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.verbatim = self.text.split("### 10.1 Verbatim", 1)[1].split("```text\n", 1)[1].split("\n```", 1)[0] + "\n"
        self.canonical = self.text.replace(self.verbatim, "")

    def test_the_owner_decisions_are_preserved_verbatim(self):
        self.assertEqual(sha(self.verbatim.encode("utf-8")), self.DECISIONS)
        self.assertIn(f"`{self.DECISIONS}`", self.text)
        for od in range(1, 9):
            self.assertIn(f"OD-M10-{od} — ", self.verbatim)
            self.assertIn(f"| OD-M10-{od} |", self.text.split("### 10.2", 1)[1])

    def test_the_record_pins_the_tools_and_the_expected_held(self):
        for path in (*NEW_TOOLS, O.MB10_PHONE):
            self.assertIn(f"`{path}`", self.text)
            self.assertIn(O.TOOL_PINS[path], self.text)
        for value in (V.EXPECTED_HELD_NAME, V.EXPECTED_HELD_SHA256, GENESIS, O.CONTINUITY.split(" = ")[1]):
            self.assertIn(value, self.text)

    def test_only_canonical_phase_names_outside_the_verbatim_text(self):
        self.assertEqual(re.findall(r"(?<![A-Z0-9_])W10_[01]S?(?![A-Z0-9_])", self.canonical), [])
        self.assertEqual(re.findall(r"(?<![A-Z0-9_])W9_5S?(?![A-Z0-9_])", self.canonical), [])
        self.assertNotIn("…_", self.canonical)
        self.assertNotIn("_…", self.canonical)
        for phase in (*V.HOST_PHASES, *V.SEQUENCE_TABLE):
            if phase != V.UNCLASSIFIED:
                self.assertIn(f"`{phase}`", self.canonical, phase)

    def test_the_record_keeps_every_boundary(self):
        state = self.text.split("## 15. State", 1)[1]
        for line in ("MB10 = DESIGN / REPOSITORY ONLY; NOT RUN", "MB10_CONTINUITY = OWNER-ACCEPTED (OD-M10-1, 2026-10-10)",
                     "OWNER_DECISIONS OD-M10-1..OD-M10-8 = OWNER-ACCEPTED (2026-10-10; semantics only)",
                     "MB10_SCRATCH_RECOVERY = DEFINED AND TESTED; NOT AUTHORIZED",
                     "FRESH_S25_OBSERVATION = REQUIRED PER SEQUENCE; NOT RUN",
                     "HELD = ABSENT", "REGISTRY_EFFECTIVE = NO", "AUTHORITY_ACTIVE = NO", "authorityGranted = false",
                     "SIGNER = INACTIVE", "M-B10 = NOT AUTHORIZED", "M-B11 = NOT AUTHORIZED",
                     "FIRST_MEMORY = NOT AUTHORIZED", "FIRST_MEMORY_READY = NOT REACHED", "PROD = NOT AUTHORIZED"):
            self.assertIn(line, state.splitlines())
        for claim in ("HELD = PRESENT", "HELD = WRITTEN", "M-B10 = AUTHORIZED", "FIRST_MEMORY = AUTHORIZED",
                      "FIRST_MEMORY_READY = REACHED", "REGISTRY_EFFECTIVE = YES", "AUTHORITY_ACTIVE = YES",
                      "MB10_SCRATCH_RECOVERY = AUTHORIZED"):
            self.assertNotIn(claim, self.text)


if __name__ == "__main__":
    unittest.main()
