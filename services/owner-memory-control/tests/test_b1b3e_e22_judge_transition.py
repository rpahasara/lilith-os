"""15B2b-B1b-3e M-B12: the PROPOSED one-member judge transition contract (`e22_judge_upgrade`) and OD-M12-11.

Record: docs/architecture/slice-15b2b-b1b3e-e22-judge-transition.md. Repository only: nothing is built, staged,
selected, stopped, started or loaded.
"""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _path in (ROOT / "services/core-api", ROOT / "services/owner-memory-control", TOOLS, ROOT / "services/authority-dev"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import e19_p1b10_upgrade as E19  # noqa: E402
import e22_judge_upgrade as J  # noqa: E402
import mb6_operator as M6  # noqa: E402
import mb12_readiness_inputs as RI  # noqa: E402
import mb12_secret_hygiene_proof as SH  # noqa: E402
import release_file_set as RFS  # noqa: E402
from lilith_owner_memory import pr1_acceptance as PA  # noqa: E402

E19_BYTES = (HERE / "fixtures/e19_new_pr1_acceptance.py.txt").read_bytes()      # installed judge (0d2e6cca)
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-e22-judge-transition.md"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def installed_pins() -> dict[str, str]:
    """The installed E-19 NEW module map: the accepted aee323e pins moved by the accepted E-19 delta."""
    return E19.new_release_module_pins({**M6.RELEASE_MODULES, **M6.PROVISION_MODULES})


def installed_payload_pins() -> dict[str, str]:
    """The COMPLETE installed payload map (member -> SHA-256): the repository payload with the judge at its installed
    E-19 bytes. Its module members are exactly the accepted installed module pins (checked below)."""
    pins = {member: sha(data) for member, data in RFS.runtime_payloads(ROOT).items()}
    pins[J.PR1_ACCEPTANCE_MEMBER] = sha(E19_BYTES)
    return pins


class ReleaseAndDeltaTests(unittest.TestCase):
    def test_old_is_the_installed_e19_release_and_new_is_unpinned(self):
        self.assertEqual((J.OLD_RELEASE, J.OLD_MANIFEST_SHA256),
                         (RI.DEV_PINS["releaseSha"], RI.DEV_PINS["attestedManifestSha256"]))
        self.assertEqual(J.OLD_RELEASE, "ba943e1a188d98f4108c9eec7149c0cf1a8f68bb")
        self.assertIsNone(J.NEW_RELEASE)
        self.assertIsNone(J.NEW_MANIFEST_SHA256)
        self.assertEqual(J.STATUS, "PROPOSED_NOT_ACCEPTED")

    def test_the_delta_is_the_merged_judge_over_the_installed_bytes(self):
        source = (ROOT / J.PR1_ACCEPTANCE_SOURCE).read_bytes()
        self.assertEqual(sha(source), J.PR1_ACCEPTANCE_NEW_SHA256)
        self.assertEqual(RFS.SHARED_HASHES[J.PR1_ACCEPTANCE_SOURCE], J.PR1_ACCEPTANCE_NEW_SHA256)
        self.assertEqual(sha(E19_BYTES), J.PR1_ACCEPTANCE_OLD_SHA256)
        self.assertEqual(J.reverse_e22(source), E19_BYTES)
        self.assertEqual(list(J.PAYLOAD_DELTA), [J.PR1_ACCEPTANCE_MEMBER])
        self.assertIn(b"OWNER_RISK_ADJUDICATED", source)
        self.assertNotIn(b"OWNER_RISK_ADJUDICATED", E19_BYTES)

    def test_reversal_refuses_anything_but_the_pinned_bytes(self):
        source = (ROOT / J.PR1_ACCEPTANCE_SOURCE).read_bytes()
        for tampered in (source + b"\n", source.replace(b"OWNER_RISK_ADJUDICATED", b"OWNER_RISK_ADJUDICATEX", 1),
                         E19_BYTES, b""):
            with self.subTest(size=len(tampered)), self.assertRaises(J.Refused) as caught:
                J.reverse_e22(tampered)
            self.assertEqual(caught.exception.reason, "E22_SOURCE_NOT_PINNED")

    def test_the_repository_payload_differs_from_the_installed_release_in_exactly_one_member(self):
        payloads = RFS.runtime_payloads(ROOT)
        pins = installed_pins()
        expected = J.new_release_module_pins(pins)
        self.assertEqual({member for member in pins if pins[member] != expected[member]}, {J.PR1_ACCEPTANCE_MEMBER})
        complete = installed_payload_pins()
        self.assertEqual({member: complete[member] for member in pins}, pins)     # the accepted module pins
        J.check_payload(payloads, complete)                                       # the merged tree is the candidate

    def test_any_other_payload_is_refused(self):
        payloads = RFS.runtime_payloads(ROOT)
        pins = installed_payload_pins()
        other = next(member for member in sorted(pins) if member != J.PR1_ACCEPTANCE_MEMBER)
        cases = {
            "another member changed": {**payloads, other: payloads[other] + b"\n"},
            "judge unchanged (E-19 bytes)": {**payloads, J.PR1_ACCEPTANCE_MEMBER: E19_BYTES},
            "judge altered": {**payloads, J.PR1_ACCEPTANCE_MEMBER: payloads[J.PR1_ACCEPTANCE_MEMBER] + b"#\n"},
        }
        for label, candidate in cases.items():
            with self.subTest(label=label), self.assertRaises(J.Refused) as caught:
                J.check_payload(candidate, pins)
            self.assertEqual(caught.exception.reason, "PAYLOAD_DELTA_NOT_EXACT")
        missing = dict(payloads)
        del missing[other]
        with self.assertRaises(J.Refused) as caught:
            J.check_payload(missing, pins)
        self.assertEqual(caught.exception.reason, "PAYLOAD_MEMBER_MISSING")

    def test_an_unexpected_extra_member_is_refused(self):
        payloads = RFS.runtime_payloads(ROOT)
        pins = installed_payload_pins()
        for extra in ("lilith_owner_memory/extra.py", "lilith_authority_dev/__pycache__/x.pyc", "assets/extra"):
            with self.subTest(extra=extra), self.assertRaises(J.Refused) as caught:
                J.check_payload({**payloads, extra: b""}, pins)
            self.assertEqual((caught.exception.reason, caught.exception.detail), ("PAYLOAD_MEMBER_UNEXPECTED", extra))
        # Judged against an incomplete installed map, the merged payload's other members are extras too: refused.
        with self.assertRaises(J.Refused) as caught:
            J.check_payload(payloads, installed_pins())
        self.assertEqual(caught.exception.reason, "PAYLOAD_MEMBER_UNEXPECTED")
        with self.assertRaises(J.Refused) as caught:
            J.new_release_module_pins({**pins, J.PR1_ACCEPTANCE_MEMBER: "0" * 64})
        self.assertEqual(caught.exception.reason, "INSTALLED_MODULE_PIN_UNEXPECTED")


class PhaseTests(unittest.TestCase):
    def test_no_unit_runs_across_the_select_or_from_a_retired_tree(self):
        for phase, (releases, selector, signer, witness) in J.PHASE_STATE.items():
            with self.subTest(phase=phase):
                self.assertIn(selector, releases)
                for running in (signer, witness):
                    self.assertIn(running, (None, selector))                     # only the selected tree, or stopped
        before, after = J.PHASES.index(J.V3), J.PHASES.index(J.V4)
        self.assertEqual(J.PHASE_STATE[J.PHASES[before]][1:], ("OLD", None, None))   # both stopped, then select
        self.assertEqual(J.PHASE_STATE[J.PHASES[after]][1:], ("NEW", None, None))

    def test_order_signer_stops_first_witness_starts_first_retire_last(self):
        self.assertEqual(J.PHASE_STATE[J.V2][2:], (None, "OLD"))                 # the client (signer) stops first
        self.assertEqual(J.PHASE_STATE[J.V5][2:], (None, "NEW"))                 # the witness starts first
        self.assertEqual(J.PHASE_STATE[J.V6][2:], ("NEW", "NEW"))
        self.assertEqual(J.PHASE_STATE[J.V7][0], ("NEW",))
        self.assertTrue(all(len(J.PHASE_STATE[p][0]) == 2 for p in J.PHASES[1:-1]))   # the staging exception only
        J.check_phase_order([J.V0, J.V1, J.V2])
        for bad in ([J.V0, J.V2], [J.V1], [J.V0, J.V1, J.V1], [J.V0, J.V1, J.V2, J.V4]):
            with self.subTest(bad=bad), self.assertRaises(J.Refused):
                J.check_phase_order(bad)

    def test_commands_name_exactly_the_reviewed_units(self):
        self.assertEqual(J.SIGNER_STOP_COMMAND.split()[2:], list(PA.SIGNER_UNITS))
        self.assertEqual(J.WITNESS_STOP_COMMAND.split()[2:], list(PA.WITNESS_UNITS))
        self.assertEqual(J.WITNESS_START_COMMAND, E19.START_COMMAND)


class OdM1211Tests(unittest.TestCase):
    def test_two_counted_loads_each_its_own_event(self):
        self.assertEqual(J.LOAD_EVENTS, {J.V5: ("K-WIT", 1), J.V6: ("K-ACT", 1)})
        self.assertEqual(J.KACT_LOAD_COUNT_AFTER, 2)
        for text in ("records its own window", "retains its transcript", "same boot", "12 attributed matches",
                     "never inherit the OD-M12-10 risk acceptance"):
            self.assertIn(text, J.OD_M12_11_RULE)

    def test_the_historical_adjudication_and_ceremony_table_are_untouched(self):
        self.assertEqual(RI.adjudication_digest(RI.E22_ADJUDICATION_V1), RI.E22_ADJUDICATION_SHA256)
        self.assertEqual(list(SH.CEREMONIES), ["B1B3D-L2b", "M-B1", "M-B2", "M-B3", "M-B9a", "M-B9b", "M-B11"])
        self.assertEqual(RI.E22_ADJUDICATION_V1["attribution"]["matches"], 12)

    def test_record_states_the_rule_and_the_decision(self):
        text = RECORD.read_text(encoding="utf-8")
        for needle in ("OD-M12-11", "I accept OD-M12-11 as recommended (decision only)", J.MODE,
                       J.PR1_ACCEPTANCE_NEW_SHA256, J.PR1_ACCEPTANCE_OLD_SHA256, "NOT AUTHORIZED"):
            self.assertIn(needle, text)
        # Proposed (decision only) until the owner confirms it by merging; never stated as accepted.
        self.assertIn("Status: OD-M12-11 PROPOSED (decision only) until the owner confirms it by merging", text)
        self.assertNotIn("OWNER-ACCEPTED", text)


if __name__ == "__main__":
    unittest.main()
