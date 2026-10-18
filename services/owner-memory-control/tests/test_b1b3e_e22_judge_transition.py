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
    def test_old_is_the_installed_e19_release_and_new_is_the_attested_build(self):
        # Re-pinned after V7 (record e22-completion): the readiness pins name the installed E-22 release.
        self.assertEqual((J.NEW_RELEASE, J.NEW_MANIFEST_SHA256),
                         (RI.DEV_PINS["releaseSha"], RI.DEV_PINS["attestedManifestSha256"]))
        self.assertEqual(J.OLD_RELEASE, "ba943e1a188d98f4108c9eec7149c0cf1a8f68bb")
        self.assertEqual(J.NEW_RELEASE, "129f2bed617334be61dcac5204cd409946a7a566")       # the PR #219 merge
        self.assertEqual(J.NEW_MANIFEST_SHA256, "fc7dbf08bb5b8260716a762fd2fbccdb44fbf0e438e2e21d0cfddcd6f1a3348a")
        self.assertEqual(J.NEW_RELEASE_ATTESTATION["archiveSha256"],
                         "baa317262896061626e6bf17151c95eea990beb01b707ffbabb7f68f3465daab")
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


def inspection(source: str, *, judge: bytes, installed: bool = False, **changes) -> dict:
    """A synthetic build inspection of the real payload map (the attest tool's identity shape)."""
    import json
    files = {member: {"sha256": sha(data), "size": len(data), "installMode": "0644"}
             for member, data in RFS.runtime_payloads(ROOT).items()}
    files[J.PR1_ACCEPTANCE_MEMBER] = {"sha256": sha(judge), "size": len(judge), "installMode": "0644"}
    identity = {
        "sourceCommit": source, "releaseRole": "lilith-authority-dev",
        "archive": {"sha256": J.OLD_ARCHIVE_SHA256 if installed else sha(b"new archive " + source.encode())},
        "manifest": {"sha256": J.OLD_MANIFEST_SHA256 if installed else sha(b"new manifest " + source.encode())},
        "payload": files, "unitDigests": {"assets/unit": "1" * 64}, "cliDigests": {"cli/x": "2" * 64},
        "hostTargets": {"/usr/local/sbin/x": {"member": "cli/x"}}, "dependencyInventory": {"sha256": "3" * 64},
        "runtimeDigests": {"authority": sha(judge), "witness": "4" * 64, "rootTooling": "5" * 64},
        "tarMembers": [{"name": name} for name in sorted(files)],
    }
    for key, value in changes.items():
        identity[key] = value
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return {"inspectionType": J.INSPECTION_TYPE, "schemaVersion": 1, "identity": identity,
            "identitySha256": sha(canonical)}


class BuildGateTests(unittest.TestCase):
    NEW_SOURCE = J.NEW_RELEASE                                     # the pinned NEW source commit

    def setUp(self):
        self.source = (ROOT / J.PR1_ACCEPTANCE_SOURCE).read_bytes()
        self.installed = inspection(J.OLD_RELEASE, judge=E19_BYTES, installed=True)

    def test_a_one_member_build_passes(self):
        self.assertEqual(J.check_inspection_delta(inspection(self.NEW_SOURCE, judge=self.source), self.installed), [])

    def test_every_other_difference_fails(self):
        base = inspection(self.NEW_SOURCE, judge=self.source)
        other = dict(base["identity"]["payload"])
        member = next(m for m in sorted(other) if m != J.PR1_ACCEPTANCE_MEMBER)
        cases = {
            "judge unchanged": (inspection(self.NEW_SOURCE, judge=E19_BYTES), "PAYLOAD_DELTA_NOT_EXACT"),
            "another member": (inspection(self.NEW_SOURCE, judge=self.source,
                                          payload={**other, member: {**other[member], "sha256": "0" * 64}}),
                               "PAYLOAD_DELTA_NOT_EXACT"),
            "extra member": (inspection(self.NEW_SOURCE, judge=self.source,
                                        payload={**other, "lilith_owner_memory/extra.py": other[member]}),
                             "PAYLOAD_FILE_SET"),
            "unit changed": (inspection(self.NEW_SOURCE, judge=self.source, unitDigests={"assets/unit": "9" * 64}),
                             "IDENTITY_CHANGED:unitDigests"),
            "root tooling changed": (inspection(self.NEW_SOURCE, judge=self.source, runtimeDigests={
                "authority": "a" * 64, "witness": "4" * 64, "rootTooling": "b" * 64}),
                "RUNTIME_DIGEST_CHANGED:rootTooling"),
            "source is the installed commit": (inspection(J.OLD_RELEASE, judge=self.source),
                                               "NEW_SOURCE_COMMIT_INVALID"),
        }
        for label, (candidate, failure) in cases.items():
            with self.subTest(label=label):
                failures = J.check_inspection_delta(candidate, self.installed)
                self.assertTrue(any(f.startswith(failure) for f in failures), failures)

    def test_the_installed_side_is_bound_to_the_e19_build(self):
        other = inspection(J.OLD_RELEASE, judge=E19_BYTES)                     # not the pinned E-19 archive
        self.assertIn("INSTALLED_INSPECTION_NOT_THE_E19_BUILD",
                      J.check_inspection_delta(inspection(self.NEW_SOURCE, judge=self.source), other))
        tampered = dict(self.installed, identitySha256="0" * 64)
        with self.assertRaises(J.Refused) as caught:
            J.check_inspection_delta(inspection(self.NEW_SOURCE, judge=self.source), tampered)
        self.assertEqual(caught.exception.reason, "INSPECTION_IDENTITY_DIGEST")
        self.assertEqual((J.OLD_ARCHIVE_SHA256, J.OLD_MANIFEST_SHA256),
                         (E19.NEW_RELEASE_ATTESTATION["archiveSha256"], E19.NEW_MANIFEST_SHA256))

    def test_cli_form(self):
        self.assertEqual(J.main([]), 2)
        self.assertEqual(J.main(["check-build", "/nonexistent/a.json", "/nonexistent/b.json"]), 1)


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


class NewReleasePinTests(unittest.TestCase):
    PIN_RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-e22-new-release-pin.md"

    def test_the_post_v7_target_is_the_swap_of_the_mb11_running_signer_texts(self):
        import mb11_dr5_target as D11
        import mb9_dr5_target as T9
        import test_b1b3e_mb11_signer_start as T11

        self.assertEqual(J.NEW_DR5_TARGETS_STATUS, "DERIVED_PINNED_NOT_ACCEPTED")
        self.assertEqual(set(J.NEW_DR5_TARGETS), set(J.NEW_DR5_SOURCES))
        texts = D11.derive(T11.accepted_sets(), T11.SCRIPT)["targets"]
        for target, source in J.NEW_DR5_SOURCES.items():
            self.assertEqual(source, D11.RUNNING_SIGNER_HELD)
            swapped = E19.derive_release_swap(texts[source]["texts"], old=J.OLD_RELEASE, new=J.NEW_RELEASE)
            for name in T9.SETS:
                with self.subTest(target=target, name=name):
                    self.assertEqual((len(swapped[name]), T9.digest(swapped[name])), J.NEW_DR5_TARGETS[target][name])
                    self.assertFalse(any(J.OLD_RELEASE in line for line in swapped[name]))
                    T9._invariants(name, swapped[name])
                    # the accepted W11 target is unchanged and differs exactly where a release line moved
                    self.assertEqual(J.NEW_DR5_TARGETS[target][name] == D11.TARGETS[source][name],
                                     name == "predeploy-block")
        self.assertNotIn(J.NEW_DR5_TARGETS, list(D11.PHASE_TARGETS.values()))   # no routine compare selects it yet

    def test_the_pin_record_states_every_pin_and_runs_nothing(self):
        import e22_operator as OP

        text = self.PIN_RECORD.read_text(encoding="utf-8")
        for value in (J.NEW_RELEASE, J.NEW_MANIFEST_SHA256, *map(str, J.NEW_RELEASE_ATTESTATION.values()),
                      OP.TOOL_PINS[OP.CONTRACT]):
            self.assertIn(f"`{value}`", text)
        for target, sets in J.NEW_DR5_TARGETS.items():
            self.assertIn(f"`{target}`", text)
            for _lines, digest in sets.values():
                self.assertIn(f"`{digest}`", text)
        state = text.split("## 7. State", 1)[1]
        for line in ("LIVE_MUTATION = NONE", "DEV_CONTACT = NONE", "INSTALLED = ba943e1",
                     "NEW_DR5_TARGETS = DERIVED_PINNED_NOT_ACCEPTED"):
            self.assertIn(line, state)
