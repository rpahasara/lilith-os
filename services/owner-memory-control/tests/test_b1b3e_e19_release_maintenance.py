"""15B2b-B1b-3e E-19 release maintenance (TEST-ONLY, synthetic).

Record: docs/architecture/slice-15b2b-b1b3e-e19-release-maintenance.md. No live system: the E-19 judge runs over
in-memory observations, the upgrade observations are synthetic documents with a synthetic NEW release SHA, and the
DR-5 derivation uses the accepted post-M-B6 baseline texts (repository fixture) and a synthetic NEW SHA. Nothing here
replaces a release, stops or starts a witness, loads a key or contacts DEV.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _p in (TOOLS, ROOT / "services/authority-dev", ROOT / "services/owner-memory-control",
           ROOT / "services/core-api"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import e19_p1b10_upgrade as E  # noqa: E402
import mb6_operator as M6  # noqa: E402
import mb9_dr5_target as T9  # noqa: E402
import mb9_operator as M9  # noqa: E402
import mb10_dr5_target as T10  # noqa: E402
import mb11_restart_boundary_install as RBI  # noqa: E402
import mb12_readiness_inputs as RI  # noqa: E402
import release_file_set as RFS  # noqa: E402
from lilith_owner_memory import pr1_acceptance as PA  # noqa: E402
from lilith_owner_memory import successor_readiness as SR  # noqa: E402

NEW = hashlib.sha1(b"synthetic NEW release (not built)").hexdigest()
OLD = E.OLD_RELEASE
H32 = lambda label: hashlib.sha256(label.encode()).hexdigest()[:32]  # noqa: E731
REPLACEMENT = (H32("replacement incarnation"), "48211")
REAL_HOST_LINE = "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=false"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------- E-19 judge ---

def e19(activation) -> tuple[str, str | None]:
    """The real judge's E-19 outcome for one activation observation (every other input absent)."""
    inputs = PA.Pr1AcceptanceInputsV1(
        environment="test", readiness=None, release_sha=None, installed_release=None, attested_manifest_sha256=None,
        host_targets={}, reviewed_runtime_digests=None, current_first_preflight=None, current_now=None,
        pinned_current_sha256=None, unit_states=(), witness_publication=None, witness_anchor=None, proofs={},
        activation=activation)
    outcome = PA.evaluate_pr1_acceptance(inputs, mode=SR.HOLD_RELEASE_ELIGIBILITY).checks["E19_ACTIVATION_DARK"]
    return outcome.status, outcome.reason


class E19JudgeTests(unittest.TestCase):
    def test_the_complete_host_line_passes(self):
        self.assertEqual(PA.ACTIVATION_DARK_LINE, REAL_HOST_LINE)
        self.assertEqual(e19(PA.ActivationObservationV1(REAL_HOST_LINE, True)), (PA.PASS, None))

    def test_malformed_and_unsafe_variants_fail_closed(self):
        class Sub(str):
            pass

        variants = (
            "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT",                                    # the old 3-field form
            "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=true",
            "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=unreadable",
            "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=False",
            "ACTIVATION=NOT_ACCEPTED reason=GRANT_INVALID advisoryConfigEnabled=false",
            "ACTIVATION=NOT_ACCEPTED reason=GRANT_EXPIRED advisoryConfigEnabled=false",
            "ACTIVATION=ACCEPTED {} advisoryConfigEnabled=false",
            'ACTIVATION=ACCEPTED {"grant":"x"} advisoryConfigEnabled=false',
            REAL_HOST_LINE + " ", " " + REAL_HOST_LINE, REAL_HOST_LINE + "\r", REAL_HOST_LINE + "\n",
            REAL_HOST_LINE + "\r\n", REAL_HOST_LINE + "\n" + REAL_HOST_LINE, "\n" + REAL_HOST_LINE,
            REAL_HOST_LINE + "\x00", REAL_HOST_LINE.replace(" ", "  ", 1), REAL_HOST_LINE.replace(" ", "\t"),
            REAL_HOST_LINE.replace(" ", "\u00a0"), REAL_HOST_LINE.lower(),
            "ACTIVATION=NOT_ACCEPTED advisoryConfigEnabled=false reason=GRANT_ABSENT",      # field order
            REAL_HOST_LINE + " extra=1", "\ufeff" + REAL_HOST_LINE, "",
            "\ud800" + REAL_HOST_LINE, REAL_HOST_LINE[:-1] + "\u0435",          # lone surrogate, homoglyph
        )
        for line in variants:
            with self.subTest(line=line):
                self.assertEqual(e19(PA.ActivationObservationV1(line, True)), (PA.FAIL, "ACTIVATION_NOT_DARK"))
        # Every non-string a JSON input document can carry, and a str subclass (exact type required).
        for line in (None, 0, 1.5, True, [REAL_HOST_LINE], {"line": REAL_HOST_LINE}, Sub(REAL_HOST_LINE)):
            with self.subTest(line=repr(line)):
                self.assertEqual(e19(PA.ActivationObservationV1(line, True)), (PA.FAIL, "ACTIVATION_NOT_DARK"))
        for unchanged in (False, None, 1, "true", "True"):
            with self.subTest(b1c=unchanged):
                self.assertEqual(e19(PA.ActivationObservationV1(REAL_HOST_LINE, unchanged)),
                                 (PA.FAIL, "ACTIVATION_NOT_DARK"))
        self.assertEqual(e19(None), (PA.FAIL, "ACTIVATION_UNOBSERVED"))
        self.assertEqual(e19({"line": REAL_HOST_LINE, "b1cUnchanged": True}), (PA.FAIL, "ACTIVATION_NOT_DARK"))

    def test_evidence_keeps_a_wrong_line_verbatim_and_nulls_a_malformed_one(self):
        def evidence(line, unchanged=True):
            inputs = PA.Pr1AcceptanceInputsV1(
                environment="test", readiness=None, release_sha=None, installed_release=None,
                attested_manifest_sha256=None, host_targets={}, reviewed_runtime_digests=None,
                current_first_preflight=None, current_now=None, pinned_current_sha256=None, unit_states=(),
                witness_publication=None, witness_anchor=None, proofs={},
                activation=PA.ActivationObservationV1(line, unchanged))
            return PA.evaluate_pr1_acceptance(inputs, mode=SR.HOLD_RELEASE_ELIGIBILITY).package["evidence"]["activation"]

        wrong = REAL_HOST_LINE.replace("false", "true")
        self.assertEqual(evidence(wrong), {"line": wrong, "b1cUnchanged": True})
        self.assertEqual(evidence(REAL_HOST_LINE, 1), {"line": REAL_HOST_LINE, "b1cUnchanged": None})
        for line in (1.5, "\ud800", ["x"]):
            with self.subTest(line=repr(line)):
                self.assertEqual(evidence(line), {"line": None, "b1cUnchanged": True})

    def test_the_b1c_printer_produces_exactly_this_form(self):
        source = (ROOT / "scripts/dev_deployer/lilith_activation_verify.py").read_text(encoding="utf-8")
        self.assertEqual(source.count('print(f"ACTIVATION=NOT_ACCEPTED reason={exc.reason} '
                                      'advisoryConfigEnabled={advisory}")'), 1)
        self.assertIn('.get("canonicalLtmEnabled") is True).lower()', source)          # "true" / "false" only
        self.assertIn('return "unreadable"', source)                                     # which E-19 refuses

    def test_every_repository_copy_of_the_line_agrees(self):
        for value in (RBI.ACTIVATION_DARK, RI.HOST_ACTIVATION_DARK_LINE, E.ACTIVATION_LINE_E19,
                      E.PRESERVED_PINS["activationLine"]):
            self.assertEqual(value, PA.ACTIVATION_DARK_LINE)
        self.assertTrue(T9.GRANT_ABSENT.startswith(E.ACTIVATION_LINE_OLD))             # DR-5 prefix rule unchanged


class ReleasePinTests(unittest.TestCase):
    def test_source_and_release_file_set_pins(self):
        raw = (ROOT / E.PR1_ACCEPTANCE_SOURCE).read_bytes()
        self.assertEqual(sha(raw), E.PR1_ACCEPTANCE_E19_SHA256)
        self.assertEqual(RFS.SHARED_HASHES[E.PR1_ACCEPTANCE_SOURCE], E.PR1_ACCEPTANCE_E19_SHA256)
        self.assertEqual(sha(E.reverse_e19(raw)), E.PR1_ACCEPTANCE_OLD_SHA256)

    def test_reversal_refuses_anything_but_the_pinned_bytes(self):
        raw = (ROOT / E.PR1_ACCEPTANCE_SOURCE).read_bytes()
        for tampered in (raw + b"\n", raw.replace(b"GRANT_ABSENT", b"GRANT_ABSENT ", 1), b""):
            with self.subTest(size=len(tampered)), self.assertRaises(E.Refused):
                E.reverse_e19(tampered)

    def test_the_new_payload_differs_from_aee323e_in_exactly_one_member(self):
        """Against the accepted aee323e module pins (mb6_operator; 38 release modules) and the CLI / unit pins."""
        payloads = RFS.runtime_payloads(ROOT)
        old_pins = {**M6.RELEASE_MODULES, **M6.PROVISION_MODULES}
        new_pins = E.new_release_module_pins(old_pins)
        self.assertEqual({k for k in old_pins if old_pins[k] != new_pins[k]}, {E.PR1_ACCEPTANCE_MEMBER})
        for member, pin in new_pins.items():
            self.assertEqual(sha(payloads[member]), pin, member)
        clis = RFS.cli_payloads(ROOT)
        self.assertEqual(sha(clis["cli/lilith-authority-ledger-dev"]), M6.LEDGER_CLI_SHA256)
        self.assertEqual(sha(clis["cli/lilith-recovery-witness-owner-dev"]), M9.OWNER_CLI_SHA256)
        for unit, pin in RBI.FRAGMENTS.items():                                         # aee323e fragments
            self.assertEqual(sha(payloads[f"assets/{unit}"]), pin, unit)
        os_denial = (TOOLS / "mb12_os_denial_proof.py").read_text(encoding="utf-8")       # POSIX-only import
        self.assertIn(f'FRAGMENT_SHA256 = "{RBI.FRAGMENTS["lilith-authority-dev.service"]}"', os_denial)
        with self.assertRaises(E.Refused):
            E.new_release_module_pins({E.PR1_ACCEPTANCE_MEMBER: "0" * 64})

    @unittest.skipUnless(subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{OLD}^{{commit}}"],
                                        capture_output=True).returncode == 0, "aee323e not in this clone")
    def test_full_payload_and_cli_set_against_the_aee323e_commit(self):
        changed = []
        sources = {**{source: target for source, target in RFS.RUNTIME_SOURCE_MAP.items()},
                   **{source: member for member, source in RFS.CLI_SOURCES.items()}}
        for source, target in sorted(sources.items()):
            old = subprocess.run(["git", "-C", str(ROOT), "show", f"{OLD}:{source}"], capture_output=True, check=True)
            if old.stdout != (ROOT / source).read_bytes():
                changed.append(target)
        self.assertEqual(changed, [E.PR1_ACCEPTANCE_MEMBER])

    def test_the_witness_imports_the_changed_module(self):
        """Why the witness cannot keep running across the swap: its code path includes pr1_acceptance, but the
        release's prefix-based witness runtime digest does not cover it."""
        core = (ROOT / "services/recovery-witness/lilith_recovery_witness/core.py").read_text(encoding="utf-8")
        self.assertIn("from lilith_owner_memory import pr1_acceptance as PA", core)
        self.assertFalse(E.PR1_ACCEPTANCE_MEMBER.startswith(PA.WITNESS_RUNTIME_PREFIXES))
        self.assertTrue(E.PR1_ACCEPTANCE_MEMBER.startswith(PA.AUTHORITY_RUNTIME_PREFIXES))
        unit = (ROOT / "services/recovery-witness/deploy/lilith-recovery-witness.service").read_text(encoding="utf-8")
        for line in ("WorkingDirectory=/opt/lilith-authority-dev/current",
                     "ExecStart=/opt/lilith-authority-dev/current/venv/bin/python -B -m lilith_recovery_witness.server",
                     "LoadCredentialEncrypted=recovery-witness-signing-key:", "Restart=on-failure"):
            self.assertIn(line, unit)

    def test_every_aee323e_binding_in_the_tools_is_classified(self):
        bound = {f"services/owner-memory-control/tools/{p.name}" for p in TOOLS.glob("*.py")
                 if OLD[:7] in p.read_text(encoding="utf-8") and p.name != "e19_p1b10_upgrade.py"}
        self.assertEqual(bound, set(E.CURRENT_RELEASE_BINDINGS) | E.HISTORICAL_RELEASE_BINDINGS)
        self.assertFalse(set(E.CURRENT_RELEASE_BINDINGS) & E.HISTORICAL_RELEASE_BINDINGS)
        self.assertEqual(M6.PROVISION_MODULES[E.PR1_ACCEPTANCE_MEMBER], E.PR1_ACCEPTANCE_OLD_SHA256)  # historical
        self.assertEqual(M6.RELEASE_SHA, OLD)
        self.assertEqual(RI.DEV_PINS["releaseSha"], OLD)
        self.assertEqual(RI.DEV_PINS["attestedManifestSha256"], E.OLD_MANIFEST_SHA256)

    def test_preserved_pins_equal_the_accepted_records(self):
        import mb3_registry_ceremony as M3C
        import mb4_mb5_trust_install_verifier as V5
        import mb7_mb8_operator as M78
        import mb10_held_verifier as V10
        sys.path.insert(0, str(ROOT / "scripts"))
        import verify_broker_dev_current_incarnation as BR

        P = E.PRESERVED_PINS
        self.assertEqual(P["kActCurrentBlobSha256"], M3C.ACCEPTED.kact_blob_sha256)
        self.assertEqual(P["kActCurrentBlobSha256"], RI.DEV_PINS["pinnedCurrentSha256"])
        self.assertEqual(P["kActPublicationFileSha256"], RI.DEV_PINS["kActPublicationFileSha256"])
        self.assertEqual(P["kWitBlobSha256"], M3C.ACCEPTED.kwit_blob_sha256)
        self.assertEqual(E.KWIT_PUBLIC_KEY_SHA256, V5.ACCEPTED_PINS.kwit_public_key_sha256)
        self.assertEqual((P["registryRootAnchorSha256"], P["witnessAnchorSha256"], P["registrySha256"]),
                         (V5.ACCEPTED_PINS.root_anchor_sha256, V5.ACCEPTED_PINS.witness_anchor_sha256,
                          V5.ACCEPTED_PINS.registry_sha256))
        self.assertEqual(P["ledgerHead"], M78.LEDGER_HEAD)
        self.assertEqual(P["witnessGenesis"], V10.ACCEPTED_GENESIS)
        self.assertEqual(P["heldSha256"], V10.EXPECTED_HELD_SHA256)
        self.assertEqual((P["brokerInvocationId"], P["brokerBaselineSha256"], E.BOOT_ID),
                         (BR.ACCEPTED_CURRENT_INCARNATION, BR.ACCEPTED_CURRENT_BASELINE_SHA256,
                          BR.ACCEPTED_CURRENT_BOOT_ID))
        self.assertEqual(sha((ROOT / "services/authority-dev/bin/lilith-authority-verify-dev").read_bytes()),
                         M78.VERIFY_CLI_SHA256)                                        # CLIs unchanged too


# ------------------------------------------------------------ the upgrade contract ---

def service(state: str, identity=E.ENDING_INCARNATION, n_restarts="0"):
    if state == "RUNNING":
        return {"ActiveState": "active", "SubState": "running", "MainPID": identity[1], "InvocationID": identity[0],
                "NRestarts": n_restarts, "Result": "success"}
    if state == "STOPPED":
        return {"ActiveState": "inactive", "SubState": "dead", "MainPID": "0", "InvocationID": "",
                "NRestarts": "0", "Result": "success"}
    active, sub = state.split("/")
    return {"ActiveState": active, "SubState": sub, "MainPID": "0", "InvocationID": "", "NRestarts": n_restarts,
            "Result": "exit-code"}


def preserved():
    host = {name: H32("host " + name) for name in E.PRESERVED_HOST_FACTS}
    host["credstoreListing"] = ["lilith-authority-dev.owner-actor.cred"]
    return {**copy.deepcopy(E.PRESERVED_PINS), **host}


def observation(*, entries=(OLD,), target=OLD, witness="RUNNING", identity=E.ENDING_INCARNATION, cwd=OLD,
                loads=(), opt=("current", "releases"), trees=None, sockets=None, n_restarts="0"):
    sockets = sockets or (("active", "active") if witness == "RUNNING" else ("inactive", "inactive"))
    shas = [e for e in entries if re.fullmatch(r"[0-9a-f]{40}", e)]
    return {
        "observationType": E.OBSERVATION_TYPE, "schemaVersion": 1, "mode": E.MODE, "oldRelease": OLD,
        "newRelease": NEW, "bootId": E.BOOT_ID, "optEntries": list(opt), "releaseEntries": list(entries),
        "currentTarget": f"releases/{target}", "treeVerified": trees if trees is not None else {s: True for s in shas},
        "witness": {"service": service(witness, identity, n_restarts), "ownerSocket": {"ActiveState": sockets[0]},
                    "signerSocket": {"ActiveState": sockets[1]},
                    "cwd": None if cwd is None else f"{E.OPT}/releases/{cwd}", "invocationsSinceBaseline": list(loads),
                    "health": "CONSISTENT" if witness == "RUNNING" else None,
                    "kWitPublicKeySha256": E.KWIT_PUBLIC_KEY_SHA256 if witness == "RUNNING" else None},
        "signer": copy.deepcopy(E.SIGNER_DARK), "preserved": preserved()}


BASELINE = observation()
ACCEPTED = {REPLACEMENT[0]: REPLACEMENT[1]}
# The proposed path, one exact observation per phase.
PATH = {
    E.U0: observation(),
    E.U1: observation(entries=(OLD, NEW)),
    E.U2: observation(entries=(OLD, NEW), witness="STOPPED", cwd=None),
    E.U3: observation(entries=(OLD, NEW), target=NEW, witness="STOPPED", cwd=None),
    E.U4: observation(entries=(OLD, NEW), target=NEW, identity=REPLACEMENT, cwd=NEW, loads=(REPLACEMENT[0],)),
    E.U5: observation(entries=(NEW,), target=NEW, identity=REPLACEMENT, cwd=NEW, loads=(REPLACEMENT[0],)),
}


def judge(doc, baseline=BASELINE, accepted=ACCEPTED):
    return E.classify(doc, baseline, new_release=NEW, accepted_replacements=accepted)


class TransitionPhaseTests(unittest.TestCase):
    def test_each_proposed_phase_is_exact_and_authorizes_nothing(self):
        for phase, doc in PATH.items():
            with self.subTest(phase=phase):
                verdict = judge(doc)
                self.assertEqual((verdict["phase"], verdict["reasons"]), (phase, []))
                self.assertEqual(verdict["authorizes"], "NOTHING")
                self.assertIs(verdict["packageReadyAdmissible"], False)
                self.assertEqual(verdict["twoReleaseException"], phase in (E.U1, E.U2, E.U3, E.U4))
                self.assertEqual(verdict["next"], E.ROUTES[phase][0])

    def test_routes_follow_the_order_and_name_a_separate_owner_act(self):
        steps = [E.ROUTES[p][0] for p in E.EXACT_PHASES]
        self.assertEqual(steps, ["STAGE_NEW_RELEASE", "STOP_WITNESS_SERVICE_AND_SOCKETS", "SELECT_NEW_RELEASE",
                                 "START_REPLACEMENT_WITNESS", "POST9A_R_THEN_OWNER_ACCEPTANCE_THEN_RETIRE_OLD",
                                 "FINAL_POST_AND_FIRST_DEPLOY_DR5_THEN_OWNER_COMPLETION"])
        self.assertIn("8af12bd6", E.ROUTES[E.U1][1])
        self.assertIn("one K-WIT load", E.ROUTES[E.U3][1])
        self.assertIn("NOT IMPLEMENTED", E.ROUTES[E.U0][1])

    def test_the_repository_establishes_no_new_release_and_no_replacement(self):
        self.assertIsNone(E.NEW_RELEASE)
        self.assertIsNone(E.NEW_MANIFEST_SHA256)
        self.assertEqual(dict(E.ACCEPTED_REPLACEMENT_INCARNATIONS), {})
        self.assertEqual(set(E.NEW_DR5_TARGETS.values()), {None})
        with self.assertRaises(E.Refused) as caught:
            E.classify(PATH[E.U0])
        self.assertEqual(caught.exception.reason, "NEW_RELEASE_NOT_ESTABLISHED")
        for bad in (OLD, "0" * 39, NEW.upper()):
            with self.subTest(bad=bad), self.assertRaises(E.Refused):
                E.classify(PATH[E.U0], new_release=bad)
        # Without a merged acceptance record, the single-NEW-release state is a STOP, never U5.
        self.assertEqual(judge(PATH[E.U5], accepted={})["phase"], E.STOP_RETIRED_EARLY)

    def test_the_ending_and_historical_incarnations(self):
        self.assertEqual(E.ENDING_INCARNATION, ("8af12bd64d024d0eba56bbcedbc534a6", "1580"))
        self.assertEqual(E.HISTORICAL_INCARNATIONS, (("5136ea7af2544450b9370fa412786c98", "143946"),))
        for identity in E.HISTORICAL_INCARNATIONS:
            doc = observation(entries=(OLD, NEW), target=NEW, identity=identity, cwd=NEW, loads=(identity[0],))
            self.assertEqual(judge(doc)["phase"], E.STOP_ORIGINAL_RESTARTED)
        # A replacement is never the ending incarnation: reusing its InvocationID is not this contract.
        doc = observation(entries=(OLD, NEW), target=NEW, cwd=NEW, loads=(E.ENDING_INCARNATION[0],))
        self.assertEqual(judge(doc)["phase"], E.STOP_ORIGINAL_RESTARTED)

    def test_a_baseline_is_required_after_u0_and_must_be_u0(self):
        self.assertEqual(E.classify(PATH[E.U0], new_release=NEW)["phase"], E.U0)
        for phase in (E.U1, E.U2, E.U3, E.U4, E.U5):
            with self.subTest(phase=phase), self.assertRaises(E.Refused) as caught:
                E.classify(PATH[phase], new_release=NEW, accepted_replacements=ACCEPTED)
            self.assertEqual(caught.exception.reason, "BASELINE_REQUIRED")


class InterruptedAndUnsafeStateTests(unittest.TestCase):
    def assertPhase(self, doc, phase, **kw):
        verdict = judge(doc, **kw)
        self.assertEqual(verdict["phase"], phase, verdict["reasons"])
        self.assertEqual(verdict["next"], "STOP")
        self.assertEqual(verdict["recovery"], E.RECOVERY[phase])
        self.assertEqual(verdict["authorizes"], "NOTHING")
        return verdict

    # -- stage
    def test_interrupted_stage(self):
        self.assertPhase(observation(entries=(OLD, f".{NEW}.staging")), E.STOP_STAGING)
        self.assertPhase(observation(entries=(OLD, NEW), trees={OLD: True, NEW: False}), E.STOP_NEW_TREE)
        self.assertPhase(observation(entries=(OLD, NEW), trees={OLD: True, NEW: None}), E.UNKNOWN)

    # -- stop
    def test_interrupted_or_unclean_stop(self):
        for state in ("deactivating/stop-sigterm", "failed/failed", "activating/auto-restart", "activating/start"):
            with self.subTest(state=state):
                self.assertPhase(observation(entries=(OLD, NEW), witness=state, cwd=None), E.STOP_WITNESS_TRANSITIONAL)
        # Service stopped but a socket still listening: the next connection would start it and load K-WIT.
        for sockets in (("active", "inactive"), ("inactive", "active"), ("active", "active")):
            with self.subTest(sockets=sockets):
                self.assertPhase(observation(entries=(OLD, NEW), witness="STOPPED", cwd=None, sockets=sockets),
                                 E.STOP_WITNESS_TRANSITIONAL)
        self.assertPhase(observation(witness="STOPPED", cwd=None), E.STOP_OUT_OF_ORDER)      # stop before stage

    # -- select
    def test_interrupted_or_out_of_order_select(self):
        self.assertPhase(observation(entries=(OLD, NEW), witness="STOPPED", cwd=None,
                                     opt=("current", "releases", ".current.tmp")), E.STOP_SELECTOR)
        # Select while the ending incarnation still runs: never an endpoint.
        self.assertPhase(observation(entries=(OLD, NEW), target=NEW), E.STOP_MIXED)
        self.assertPhase(observation(entries=(OLD, NEW), target="0" * 40), E.STOP_RELEASE_SET)

    # -- start
    def test_interrupted_or_unsafe_start(self):
        one = (REPLACEMENT[0],)
        two = (REPLACEMENT[0], H32("second"))
        self.assertPhase(observation(entries=(OLD, NEW), target=NEW, witness="STOPPED", cwd=None, loads=one),
                         E.STOP_START_FAILED)
        self.assertPhase(observation(entries=(OLD, NEW), target=NEW, witness="failed/failed", cwd=None, loads=one),
                         E.STOP_WITNESS_TRANSITIONAL)
        self.assertPhase(observation(entries=(OLD, NEW), target=NEW, identity=REPLACEMENT, cwd=NEW, loads=two),
                         E.STOP_LOADS)
        self.assertPhase(observation(entries=(OLD, NEW), target=NEW, identity=REPLACEMENT, cwd=NEW, loads=()),
                         E.STOP_LOADS)
        self.assertPhase(observation(entries=(OLD, NEW), target=NEW, identity=REPLACEMENT, cwd=NEW, loads=one,
                                     n_restarts="1"), E.STOP_WITNESS_TRANSITIONAL)
        # A start before the select: a new incarnation (a K-WIT load) on the OLD release.
        self.assertPhase(observation(entries=(OLD, NEW), identity=REPLACEMENT, cwd=OLD, loads=one),
                         E.STOP_RESTARTED_ON_OLD)
        doc = observation(entries=(OLD, NEW), target=NEW, identity=REPLACEMENT, cwd=NEW, loads=one)
        doc["witness"]["health"] = "INCONSISTENT"
        self.assertPhase(doc, E.STOP_UNHEALTHY)
        doc = observation(entries=(OLD, NEW), target=NEW, identity=REPLACEMENT, cwd=NEW, loads=one)
        doc["witness"]["kWitPublicKeySha256"] = "0" * 64
        self.assertPhase(doc, E.STOP_UNHEALTHY)

    # -- the ending incarnation
    def test_the_ending_incarnation_must_not_change_before_the_stop(self):
        self.assertPhase(observation(n_restarts="1"), E.STOP_WITNESS_TRANSITIONAL)
        self.assertPhase(observation(identity=(E.ENDING_INCARNATION[0], "1581")), E.STOP_ORIGINAL_RESTARTED)
        self.assertPhase(observation(entries=(OLD, NEW), loads=(H32("x"),)), E.STOP_ORIGINAL_RESTARTED)
        doc = observation(entries=(OLD, NEW))
        doc["witness"]["health"] = "INCONSISTENT"
        self.assertPhase(doc, E.STOP_ORIGINAL_RESTARTED)

    # -- retire
    def test_interrupted_or_early_retire(self):
        one = (REPLACEMENT[0],)
        partial = observation(entries=(OLD, NEW), target=NEW, identity=REPLACEMENT, cwd=NEW, loads=one,
                              trees={OLD: False, NEW: True})
        self.assertPhase(partial, E.STOP_RETIRE_PARTIAL)
        self.assertPhase(partial, E.STOP_OLD_TREE, accepted={})            # retire began before acceptance
        self.assertPhase(observation(entries=(OLD, NEW), trees={OLD: False, NEW: True}), E.STOP_OLD_TREE)
        # Retire while the ending incarnation still runs from OLD: a witness on a retired tree.
        self.assertPhase(observation(entries=(NEW,), target=NEW, cwd=OLD), E.STOP_DELETED)
        # Retire before any replacement started.
        self.assertPhase(observation(entries=(NEW,), target=NEW, witness="STOPPED", cwd=None), E.STOP_OUT_OF_ORDER)
        self.assertPhase(PATH[E.U5], E.STOP_RETIRED_EARLY, accepted={})
        self.assertPhase(PATH[E.U5], E.STOP_RETIRED_EARLY, accepted={REPLACEMENT[0]: "1"})

    def test_foreign_release_sets_and_selectors(self):
        third = "1" * 40
        for entries in ((OLD, NEW, third), (third,), (OLD, OLD), (), (OLD, "notes")):
            with self.subTest(entries=entries):
                doc = observation(entries=entries)
                doc["treeVerified"] = {s: True for s in set(entries) if re.fullmatch(r"[0-9a-f]{40}", s)}
                self.assertPhase(doc, E.STOP_RELEASE_SET)
        self.assertPhase(observation(opt=("current", "releases", "x")), E.STOP_RELEASE_SET)
        self.assertPhase(observation(entries=(NEW,), target=OLD, cwd=NEW, identity=REPLACEMENT,
                                     loads=(REPLACEMENT[0],)), E.STOP_RELEASE_SET)

    def test_reboot_is_a_material_stop(self):
        doc = copy.deepcopy(PATH[E.U2])
        doc["bootId"] = "00000000-0000-0000-0000-000000000000"
        self.assertPhase(doc, E.STOP_BOOT)

    def test_unknown_is_never_success(self):
        for path in (("bootId",), ("optEntries",), ("releaseEntries",), ("treeVerified",), ("signer",),
                     ("preserved",), ("witness", "service"), ("witness", "ownerSocket"), ("witness", "signerSocket"),
                     ("witness", "invocationsSinceBaseline")):
            with self.subTest(path=path):
                doc = copy.deepcopy(PATH[E.U1])
                target = doc
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = None
                self.assertPhase(doc, E.UNKNOWN)


class HaltTests(unittest.TestCase):
    def test_every_preserved_fact_is_a_halt_in_every_phase(self):
        for phase, doc in PATH.items():
            for name in sorted(E.PRESERVED_FIELDS):
                with self.subTest(phase=phase, name=name):
                    moved = copy.deepcopy(doc)
                    moved["preserved"][name] = ["moved"] if isinstance(moved["preserved"][name], list) else "moved"
                    verdict = judge(moved)
                    self.assertEqual(verdict["phase"], E.HALT_PRESERVED)
                    self.assertEqual(verdict["reasons"], ["PRESERVED:" + name])

    def test_the_held_listing_and_activation_line_are_preserved_exactly(self):
        for value in ([], E.PRESERVED_PINS["holdListing"] * 2, ["0" * 64 + ".json"]):
            doc = copy.deepcopy(PATH[E.U3])
            doc["preserved"]["holdListing"] = value
            self.assertEqual(judge(doc)["phase"], E.HALT_PRESERVED)
        doc = copy.deepcopy(PATH[E.U3])
        doc["preserved"]["activationLine"] = E.ACTIVATION_LINE_OLD
        self.assertEqual(judge(doc)["phase"], E.HALT_PRESERVED)

    def test_the_signer_must_stay_dark_with_no_k_act_load(self):
        changes = {"ActiveState": "active", "SubState": "running", "MainPID": "77", "InvocationID": H32("s"),
                   "NRestarts": "1", "UnitFileState": "enabled",
                   "DropInPaths": "/etc/systemd/system/lilith-authority-dev.service.d/10-no-implicit-restart.conf",
                   "invocationsEver": [H32("one K-ACT load")]}
        for phase, doc in PATH.items():
            for name, value in changes.items():
                with self.subTest(phase=phase, name=name):
                    changed = copy.deepcopy(doc)
                    changed["signer"][name] = value
                    self.assertEqual(judge(changed)["phase"], E.HALT_SIGNER)

    def test_halt_takes_precedence_over_unknown_and_stop(self):
        doc = copy.deepcopy(PATH[E.U1])
        doc["bootId"] = None
        doc["witness"]["service"] = None
        doc["preserved"]["heldSha256"] = "0" * 64
        self.assertEqual(judge(doc)["phase"], E.HALT_PRESERVED)

    def test_malformed_observations_are_refused(self):
        for mutate in (lambda d: d.pop("signer"), lambda d: d.update(extra=1), lambda d: d.update(mode="X"),
                       lambda d: d.update(oldRelease=NEW), lambda d: d["witness"].pop("cwd"),
                       lambda d: d["witness"]["service"].update(Extra="1"), lambda d: d["preserved"].pop("ledgerHead"),
                       lambda d: d.update(treeVerified={"x": True}), lambda d: d.update(releaseEntries="x"),
                       lambda d: d["witness"].update(invocationsSinceBaseline=["NOTHEX"]),
                       lambda d: d.update(treeVerified={OLD: True, NEW: True})):
            doc = copy.deepcopy(PATH[E.U0])
            mutate(doc)
            with self.subTest(mutate=mutate), self.assertRaises(E.Refused):
                judge(doc)


class PackageReadyTests(unittest.TestCase):
    def test_package_ready_is_refused_in_every_intermediate_and_old_state(self):
        for phase, doc in PATH.items():
            verdict = judge(doc)
            for release in (OLD, NEW):
                ok, reason = E.package_ready_admissible(verdict, release_sha=release, new_release=NEW)
                with self.subTest(phase=phase, release=release):
                    self.assertEqual(ok, phase == E.U5 and release == NEW, reason)
                    if phase in E.TWO_RELEASE_PHASES:
                        self.assertEqual(reason, "TWO_RELEASE_INTERMEDIATE")
        self.assertEqual(E.package_ready_admissible(judge(PATH[E.U5]), release_sha=NEW),
                         (False, "RELEASE_NOT_THE_ACCEPTED_NEW_RELEASE"))       # the repository has no NEW
        self.assertEqual(E.package_ready_admissible({"phase": E.STOP_MIXED}, release_sha=NEW, new_release=NEW),
                         (False, "NOT_EXACT"))

    def test_the_release_judge_itself_refuses_two_installed_releases(self):
        """E-01 (`verify_installed_release`) requires `releases/` to hold exactly the release under judgement."""
        for entries, target in (((OLD, NEW), NEW), ((OLD, NEW), OLD), ((NEW, OLD), NEW)):
            observed = PA.InstalledReleaseObservationV1(f"releases/{target}", entries, b"{}", (), None, {})
            result = PA.verify_installed_release(observed, release_sha=target, attested_manifest_sha256="0" * 64,
                                                 host_targets={})
            with self.subTest(entries=entries, target=target):
                self.assertEqual(result.reason, "RELEASE_SET_UNEXPECTED")


class Dr5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = json.loads((HERE / "b1b3e_mb9_post_mb6_dr5_baseline.json").read_text(encoding="utf-8"))
        base = {name: T9.encode(lines) for name, lines in fixture["sets"].items()}
        script = (ROOT / T10.DR5_SCRIPT).read_bytes()
        cls.w10 = T10.derive(base, script)["targets"]
        cls.script = script.decode("utf-8")

    def test_the_release_swap_moves_exactly_the_release_lines(self):
        for target in (T10.RUNNING_HELD, T10.STOPPED_HELD):
            texts = self.w10[target]["texts"]
            swapped = E.derive_release_swap(texts, old=OLD, new=NEW)
            for name in T9.SETS:
                with self.subTest(target=target, name=name):
                    before, after = texts[name], swapped[name]
                    self.assertEqual(len(before), len(after))
                    moved = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
                    self.assertEqual(len(moved), E.DR5_RELEASE_LINE_COUNTS[name])
                    for i in moved:
                        self.assertEqual((before[i], after[i]), (E.DR5_RELEASE_LINE.format(sha=OLD),
                                                                 E.DR5_RELEASE_LINE.format(sha=NEW)))
                    T9._invariants(name, after)
                    expected_equal = name == "predeploy-block"
                    self.assertEqual(T9.digest(after) == T10.TARGETS[target][name][1], expected_equal)

    def test_the_swap_refuses_inexact_inputs(self):
        texts = self.w10[T10.RUNNING_HELD]["texts"]
        with self.assertRaises(E.Refused):
            E.derive_release_swap(E.derive_release_swap(texts, old=OLD, new=NEW), old=OLD, new=NEW)
        broken = {name: list(lines) for name, lines in texts.items()}
        broken["dr5-block"].append(E.DR5_RELEASE_LINE.format(sha=OLD))                  # an intermediate (3 lines)
        with self.assertRaises(E.Refused):
            E.derive_release_swap(broken, old=OLD, new=NEW)
        for old, new in ((OLD, OLD), ("x", NEW)):
            with self.assertRaises(E.Refused):
                E.derive_release_swap(texts, old=old, new=new)

    def test_the_script_names_a_release_at_exactly_two_sites(self):
        self.assertEqual(self.script.count('ab_deny -w "${AB_OPT}/releases/${entry}"'), 1)
        self.assertEqual(self.script.count('ab_deny -w "${AB_OPT}/${target}"'), 1)
        self.assertIn("still fails the proof: no routine deployment runs mid-upgrade", self.script)


class SourceGuardTests(unittest.TestCase):
    def test_the_tool_contacts_nothing_and_writes_nothing(self):
        source = (TOOLS / "e19_p1b10_upgrade.py").read_text(encoding="utf-8")
        for needle in ("import subprocess", "import socket", "import os", "plink", "gcloud", "systemctl ",
                       "os.system", "write_bytes", "write_text", "open(", "urllib", "unlink", "rmtree", ".rename(",
                       "os.replace", "symlink("):
            self.assertNotIn(needle, source)

    def test_the_existing_upgrade_mode_cannot_run_after_p1b10(self):
        """`UPGRADE_EXISTING_DEV_SYNTHETIC` (PR-1A) refuses a host with the custody root or a witness blob, and has
        no witness, HELD or ledger preservation: this contract needs its own installer stages (not implemented)."""
        installer = (ROOT / "services/authority-dev/ceremony/install_authority_dev.py").read_text(encoding="utf-8")
        self.assertIn("for path in DEFERRED_PATHS + tuple(CUSTODY_DIRS):", installer)
        self.assertIn('failures.append("PRESERVATION:UNEXPECTED_WITNESS_CREDENTIAL")', installer)
        self.assertNotIn(E.MODE, installer)

    def test_the_release_tree_file_set_is_unchanged(self):
        RFS.check_source_tree(ROOT)
        self.assertFalse(any("e19" in path for path in RFS.SOURCE_FILES))


if __name__ == "__main__":
    unittest.main()
