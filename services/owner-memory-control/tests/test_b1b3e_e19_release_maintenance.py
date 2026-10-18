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

import e19_maintenance_observer as O  # noqa: E402
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


# The installed E-19 release's `pr1_acceptance.py` (0d2e6cca). The repository judge has since moved on (OD-M12-10,
# not built or installed), so the E-19 history is checked against these retained bytes, not the working tree.
E19_PR1_ACCEPTANCE_BYTES = (Path(__file__).resolve().parent / "fixtures/e19_new_pr1_acceptance.py.txt").read_bytes()


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
            result = PA.evaluate_pr1_acceptance(inputs, mode=SR.HOLD_RELEASE_ELIGIBILITY)
            return result.package["evidence"]["activation"]

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
        raw = E19_PR1_ACCEPTANCE_BYTES
        self.assertEqual(sha(raw), E.PR1_ACCEPTANCE_E19_SHA256)
        # The release file set now pins the repository judge (OD-M12-10, unbuilt), no longer the E-19 bytes.
        self.assertEqual(RFS.SHARED_HASHES[E.PR1_ACCEPTANCE_SOURCE], sha((ROOT / E.PR1_ACCEPTANCE_SOURCE).read_bytes()))
        self.assertNotEqual(RFS.SHARED_HASHES[E.PR1_ACCEPTANCE_SOURCE], E.PR1_ACCEPTANCE_E19_SHA256)
        self.assertEqual(sha(E.reverse_e19(raw)), E.PR1_ACCEPTANCE_OLD_SHA256)

    def test_reversal_refuses_anything_but_the_pinned_bytes(self):
        raw = E19_PR1_ACCEPTANCE_BYTES
        for tampered in (raw + b"\n", raw.replace(b"GRANT_ABSENT", b"GRANT_ABSENT ", 1), b""):
            with self.subTest(size=len(tampered)), self.assertRaises(E.Refused):
                E.reverse_e19(tampered)

    def test_the_new_payload_differs_from_aee323e_in_exactly_one_member(self):
        """Against the accepted aee323e module pins (mb6_operator; 38 release modules) and the CLI / unit pins."""
        payloads = {**RFS.runtime_payloads(ROOT), E.PR1_ACCEPTANCE_MEMBER: E19_PR1_ACCEPTANCE_BYTES}
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
        # Post-U5 (E-19 completion record): the current bindings name NEW; every remaining OLD mention is classified
        # as history or provenance (`e19_completion`). The pre-transition map stays in the contract, as merged.
        import e19_completion as C
        self.assertEqual(set(E.CURRENT_RELEASE_BINDINGS) - {"services/owner-memory-control/tools/mb6_operator.py",
                                                             "services/owner-memory-control/tools/mb9_operator.py",
                                                             "services/owner-memory-control/tools/mb12_os_denial_proof.py"},
                         set(C.REPINNED_TO_NEW))
        bound = {f"services/owner-memory-control/tools/{p.name}" for p in TOOLS.glob("*.py")
                 if OLD[:7] in p.read_text(encoding="utf-8")}
        self.assertEqual(bound, set(C.OLD_RELEASE_MENTIONS))
        self.assertTrue(E.HISTORICAL_RELEASE_BINDINGS <= set(C.OLD_RELEASE_MENTIONS))
        self.assertEqual(M6.PROVISION_MODULES[E.PR1_ACCEPTANCE_MEMBER], E.PR1_ACCEPTANCE_OLD_SHA256)  # historical
        self.assertEqual(M6.RELEASE_SHA, OLD)                                                       # byte-identical
        self.assertEqual(RI.DEV_PINS["releaseSha"], E.NEW_RELEASE)
        self.assertEqual(RI.DEV_PINS["attestedManifestSha256"], E.NEW_MANIFEST_SHA256)
        # NEW is named by the contract and by exactly the re-pinned current bindings.
        named_new = {f"services/owner-memory-control/tools/{p.name}" for p in TOOLS.glob("*.py")
                     if E.NEW_RELEASE[:12] in p.read_text(encoding="utf-8")
                     or E.NEW_MANIFEST_SHA256[:12] in p.read_text(encoding="utf-8")}
        self.assertEqual(named_new, set(C.REPINNED_TO_NEW) | {"services/owner-memory-control/tools/e19_p1b10_upgrade.py"})

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

BOOT_HEX = E.BOOT_ID.replace("-", "")
SEQNUM_ID = H32("journal seqnum id")


def cursor(i: str, *, seqnum=SEQNUM_ID, boot=BOOT_HEX) -> str:
    return f"s={seqnum};i={i};b={boot};m=1a2b;t=5f1e2d3c4b5a6;x=9c8d7e6f"


CURSOR0 = cursor("1f4a")            # the U0 baseline cursor
LATER = cursor("2b01")              # any later observation


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
                loads=(), opt=("current", "releases"), trees=None, sockets=None, n_restarts="0", at=LATER,
                after=CURSOR0, health="default"):
    sockets = sockets or (("active", "active") if witness == "RUNNING" else ("inactive", "inactive"))
    shas = [e for e in entries if re.fullmatch(r"[0-9a-f]{40}", e)]
    if health == "default":
        health = dict(E.HEALTH_EXACT) if witness == "RUNNING" else None
    return {
        "observationType": E.OBSERVATION_TYPE, "schemaVersion": 1, "mode": E.MODE, "oldRelease": OLD,
        "newRelease": NEW, "bootId": E.BOOT_ID, "journalCursor": at, "optEntries": list(opt),
        "releaseEntries": list(entries), "currentTarget": f"releases/{target}",
        "treeVerified": trees if trees is not None else {s: True for s in shas},
        "witness": {"service": service(witness, identity, n_restarts), "ownerSocket": {"ActiveState": sockets[0]},
                    "signerSocket": {"ActiveState": sockets[1]},
                    "cwd": None if cwd is None else f"{E.OPT}/releases/{cwd}",
                    "invocations": {"afterCursor": after, "ids": list(loads)}, "health": health,
                    "restartBoundary": copy.deepcopy(E.RESTART_BOUNDARY)},
        "signer": copy.deepcopy(E.SIGNER_DARK), "preserved": preserved()}


BASE_OBS = observation(at=CURSOR0)
PATH = {
    E.U0: observation(),
    E.U1: observation(entries=(OLD, NEW)),
    E.U2: observation(entries=(OLD, NEW), witness="STOPPED", cwd=None),
    E.U3: observation(entries=(OLD, NEW), target=NEW, witness="STOPPED", cwd=None),
    E.U4: observation(entries=(OLD, NEW), target=NEW, identity=REPLACEMENT, cwd=NEW, loads=(REPLACEMENT[0],)),
    E.U5: observation(entries=(NEW,), target=NEW, identity=REPLACEMENT, cwd=NEW, loads=(REPLACEMENT[0],)),
}


def u0_acceptance(obs=None):
    """What the operator would hold after the owner issues the canonical U0 statement verbatim (B3 / D3 pattern)."""
    obs = BASE_OBS if obs is None else obs
    statement = E.render_u0_statement(obs, new_release=NEW)
    record = E.acceptance_record(E.U0_RECORD_TYPE, obs, statement, new_release=NEW, invocation=E.ENDING_INCARNATION,
                                 cursor=obs["journalCursor"])
    return {"observation": copy.deepcopy(obs), "statement": statement.decode("ascii"), "record": record}


U0_ACCEPT = u0_acceptance()


def post9a_evidence(obs=None, *, baseline_obs=None, **overrides):
    obs = PATH[E.U4] if obs is None else obs
    ident = {"InvocationID": obs["witness"]["service"]["InvocationID"], "MainPID": obs["witness"]["service"]["MainPID"]}
    evidence = {"evidenceType": E.POST9A_R_TYPE, "schemaVersion": 1, "mode": E.MODE,
                "baselineSubjectSha256": E.document_sha256(BASE_OBS if baseline_obs is None else baseline_obs),
                "observation": copy.deepcopy(obs), "w9PhaseDirect": "W9_LATER_STATE",
                "w9PhaseSeamed": "W9_5_GENESIS_COMMITTED_EXACT", "w10Phase": "W10_1_HELD_EXACT",
                "w10OutputSha256": sha(b"synthetic w10 verifier output"),
                "healthCapture": {"before": dict(ident), "after": dict(ident), "health": dict(E.HEALTH_EXACT)},
                "denials": dict(E.POST9A_R_DENIALS)}
    evidence.update(overrides)
    return evidence


def replacement_acceptance(evidence=None, baseline=None):
    evidence = post9a_evidence() if evidence is None else evidence
    baseline = U0_ACCEPT if baseline is None else baseline
    statement = E.render_replacement_statement(evidence, baseline, new_release=NEW)
    report = E.post9a_r(evidence, baseline, new_release=NEW)
    record = E.acceptance_record(E.REPLACEMENT_RECORD_TYPE, evidence, statement, new_release=NEW,
                                 invocation=(report["invocationId"], report["mainPid"]),
                                 cursor=baseline["observation"]["journalCursor"])
    return {"evidence": evidence, "statement": statement.decode("ascii"), "record": record}


REPL_ACCEPT = replacement_acceptance()


def judge(doc, baseline=U0_ACCEPT, replacement=REPL_ACCEPT):
    return E.classify(doc, baseline, replacement, new_release=NEW)


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
        self.assertEqual(E.classify(BASE_OBS, new_release=NEW)["phase"], E.U0)       # the U0 candidate alone

    def test_routes_follow_the_order_and_name_a_separate_owner_act(self):
        steps = [E.ROUTES[p][0] for p in E.EXACT_PHASES]
        self.assertEqual(steps, ["STAGE_NEW_RELEASE", "STOP_WITNESS_SERVICE_AND_SOCKETS", "SELECT_NEW_RELEASE",
                                 "START_REPLACEMENT_WITNESS",
                                 "POST9A_R_THEN_LOCAL_REPLACEMENT_ACCEPTANCE_THEN_RETIRE_OLD",
                                 "FINAL_POST_AND_FIRST_DEPLOY_DR5_THEN_OWNER_COMPLETION"])
        self.assertIn("8af12bd6", E.ROUTES[E.U1][1])
        self.assertIn("STOP_COMMAND", E.ROUTES[E.U1][1])
        self.assertIn("exactly one K-WIT load", E.ROUTES[E.U3][1])
        self.assertIn("local digest-bound replacement acceptance", E.ROUTES[E.U4][1])
        self.assertIn("completion record", E.ROUTES[E.U5][1])
        self.assertIn("NOT IMPLEMENTED", E.ROUTES[E.U0][1])

    def test_the_repository_pins_exactly_the_attested_new_release_and_no_replacement(self):
        # The owner pin of the attested build (record e19-new-release-pin): the SOURCE commit of the archive.
        self.assertEqual(E.NEW_RELEASE, "ba943e1a188d98f4108c9eec7149c0cf1a8f68bb")
        self.assertEqual(E.NEW_MANIFEST_SHA256, "b8393015e505495a81629411a4ecd33c0c372c7b16d2761094eb4e018bc300a2")
        self.assertNotEqual(E.NEW_RELEASE, OLD)
        self.assertNotEqual(E.NEW_MANIFEST_SHA256, E.OLD_MANIFEST_SHA256)
        self.assertEqual(E.NEW_RELEASE_ATTESTATION["archiveSha256"],
                         "a4ad24e8c261c6e5858c559f4102ac8d6cc6923cfc19a9a7ffe5720408ae3faf")
        self.assertEqual(E.NEW_RELEASE_ATTESTATION["attestationDigest"],
                         "d6f7f709d3b40dc42d6fb9c936137bb6c6871c36917c9d27f8f2faa634ff51d2")
        self.assertFalse(hasattr(E, "ACCEPTED_REPLACEMENT_INCARNATIONS"))   # R2: no repository merge during U4
        self.assertEqual(E.NEW_DR5_TARGETS_STATUS, "DERIVED_PINNED_NOT_ACCEPTED")
        # Evidence for any other NEW (here the synthetic one) is refused by the pinned defaults.
        for call in (lambda: E.classify(PATH[E.U0]), lambda: E.render_u0_statement(BASE_OBS),
                     lambda: E.trusted_baseline(U0_ACCEPT), lambda: E.post9a_r(post9a_evidence(), U0_ACCEPT)):
            with self.assertRaises(E.Refused) as caught:
                call()
            self.assertEqual(caught.exception.reason, "OBSERVATION_RELEASES")
        with self.assertRaises(E.Refused) as caught:
            E.classify(PATH[E.U0], new_release=None)
        self.assertEqual(caught.exception.reason, "NEW_RELEASE_NOT_ESTABLISHED")
        for bad in (OLD, "0" * 39, NEW.upper()):
            with self.subTest(bad=bad), self.assertRaises(E.Refused):
                E.classify(PATH[E.U0], new_release=bad)

    def test_the_pinned_new_release_is_installed_only_from_the_select(self):
        """U0..U4 under the merged pins: before U3 `current` stays OLD and the witness runs from OLD; NEW is only a
        staged sibling. Pinning NEW never makes the installed release read as NEW."""
        def pinned(doc):
            return json.loads(json.dumps(doc).replace(NEW, E.NEW_RELEASE))
        base = pinned(BASE_OBS)
        statement = E.render_u0_statement(base)
        u0 = {"observation": base, "statement": statement.decode("ascii"),
              "record": E.acceptance_record(E.U0_RECORD_TYPE, base, statement, new_release=E.NEW_RELEASE,
                                            invocation=E.ENDING_INCARNATION, cursor=base["journalCursor"])}
        for phase in (E.U0, E.U1, E.U2, E.U3, E.U4):
            doc = pinned(PATH[phase])
            with self.subTest(phase=phase):
                self.assertEqual(E.classify(doc, u0)["phase"], phase)
                selected = doc["currentTarget"].split("/", 1)[1]
                self.assertEqual(selected, OLD if phase in (E.U0, E.U1, E.U2) else E.NEW_RELEASE)
        early = pinned(observation(entries=(OLD, NEW), target=NEW))          # NEW selected under the running OLD
        self.assertEqual(E.classify(early, u0)["phase"], E.STOP_MIXED)

    def test_u5_only_with_the_verified_replacement_acceptance(self):
        self.assertEqual(judge(PATH[E.U5], replacement=None)["phase"], E.STOP_RETIRED_EARLY)
        other = observation(entries=(OLD, NEW), target=NEW, identity=(H32("other"), "777"), cwd=NEW,
                            loads=(H32("other"),))
        other_accept = replacement_acceptance(post9a_evidence(other))          # valid, but for another identity
        self.assertEqual(judge(PATH[E.U5], replacement=other_accept)["phase"], E.STOP_RETIRED_EARLY)
        with self.assertRaises(E.Refused) as caught:
            E.classify(PATH[E.U5], None, REPL_ACCEPT, new_release=NEW)
        self.assertEqual(caught.exception.reason, "BASELINE_REQUIRED")

    def test_the_ending_and_historical_incarnations(self):
        self.assertEqual(E.ENDING_INCARNATION, ("8af12bd64d024d0eba56bbcedbc534a6", "1580"))
        self.assertEqual(E.HISTORICAL_INCARNATIONS, (("5136ea7af2544450b9370fa412786c98", "143946"),))
        for identity in E.HISTORICAL_INCARNATIONS:
            doc = observation(entries=(OLD, NEW), target=NEW, identity=identity, cwd=NEW, loads=(identity[0],))
            self.assertEqual(judge(doc)["phase"], E.STOP_ORIGINAL_RESTARTED)
        # The ending incarnation's own journal entries are not a load (real systemd 255): an observation that shows
        # it still running while current -> NEW is the running-across-select STOP, never an exact phase.
        doc = observation(entries=(OLD, NEW), target=NEW, cwd=NEW, loads=(E.ENDING_INCARNATION[0],))
        self.assertEqual(judge(doc)["phase"], E.STOP_MIXED)

    def test_without_a_baseline_only_the_u0_candidate_is_judged(self):
        """Without the accepted baseline a later observation is never exact: its invocation list is anchored to a
        cursor it cannot prove (STOP), and a self-anchored non-U0 shape is refused (BASELINE_REQUIRED)."""
        for phase in (E.U1, E.U2, E.U3, E.U4, E.U5):
            with self.subTest(phase=phase):
                self.assertEqual(E.classify(PATH[phase], new_release=NEW)["phase"], E.STOP_JOURNAL)
                self_anchored = copy.deepcopy(PATH[phase])
                self_anchored["witness"]["invocations"]["afterCursor"] = self_anchored["journalCursor"]
                with self.assertRaises(E.Refused) as caught:
                    E.classify(self_anchored, new_release=NEW)
                self.assertEqual(caught.exception.reason, "BASELINE_REQUIRED")


class BaselineTrustTests(unittest.TestCase):
    """R1: the baseline is an owner-accepted, digest-bound, exactly-U0 observation, re-verified on every use."""

    def test_moved_ledger_regression_substituted_u3_baseline_is_refused(self):
        """Review probe (a): a U3 observation carrying a moved ledger, offered as the baseline, made U4 exact."""
        moved_u3 = copy.deepcopy(PATH[E.U3])
        moved_u3["preserved"]["ledgerBytesSha256"] = "MOVED"
        later = copy.deepcopy(PATH[E.U4])
        later["preserved"]["ledgerBytesSha256"] = "MOVED"
        with self.assertRaises(E.Refused) as caught:
            E.render_u0_statement(moved_u3, new_release=NEW)
        self.assertEqual(caught.exception.reason, "BASELINE_NOT_U0")
        forged = {"observation": moved_u3, "statement": U0_ACCEPT["statement"], "record": U0_ACCEPT["record"]}
        with self.assertRaises(E.Refused) as caught:
            judge(later, baseline=forged, replacement=None)
        self.assertEqual(caught.exception.reason, "BASELINE_NOT_U0")
        # Against the genuine accepted U0 baseline the moved ledger is a proven change: HALT.
        verdict = judge(later, replacement=None)
        self.assertEqual((verdict["phase"], verdict["reasons"]), (E.HALT_PRESERVED, ["PRESERVED:ledgerBytesSha256"]))

    def test_no_non_u0_observation_can_be_a_baseline(self):
        for phase in (E.U1, E.U2, E.U3, E.U4, E.U5):
            with self.subTest(phase=phase), self.assertRaises(E.Refused) as caught:
                E.render_u0_statement(PATH[phase], new_release=NEW)
            self.assertEqual(caught.exception.reason, "BASELINE_NOT_U0")
        service_unit = E.WITNESS_SERVICE
        for mutate in (lambda d: d["witness"]["restartBoundary"]["units"][service_unit].update(Restart="on-failure"),
                       lambda d: d["witness"]["invocations"].update(afterCursor=cursor("1")),
                       lambda d: d["witness"].update(health=None)):
            doc = copy.deepcopy(BASE_OBS)
            mutate(doc)
            with self.subTest(mutate=mutate), self.assertRaises(E.Refused) as caught:
                E.render_u0_statement(doc, new_release=NEW)
            self.assertEqual(caught.exception.reason, "BASELINE_NOT_U0")

    def test_the_statement_and_record_bind_this_exact_observation(self):
        text = U0_ACCEPT["statement"]
        self.assertIn(E.document_sha256(BASE_OBS), text)
        self.assertIn(CURSOR0, text)
        self.assertIn(E.document_sha256(E.RESTART_BOUNDARY), text)
        self.assertTrue(text.endswith("authorizes nothing further: not staging, not the witness stop, not a K-WIT "
                                      "load, not a release switch or retirement, not the signer, not authority.\n"))
        self.assertEqual(E.trusted_baseline(U0_ACCEPT, new_release=NEW)["journalCursor"], CURSOR0)

    def test_caller_made_reworded_or_rebound_acceptances_are_refused(self):
        def variant(**change):
            bundle = copy.deepcopy(U0_ACCEPT)
            for key, value in change.items():
                bundle[key] = value(bundle) if callable(value) else value
            return bundle

        record = U0_ACCEPT["record"]
        other_obs = copy.deepcopy(BASE_OBS)
        other_obs["preserved"]["hostKeyIdentity"] = H32("another host key identity")
        cases = {
            "caller dict": {"accepted": True, "observation": BASE_OBS},
            "extra key": variant(extra=1),
            "CRLF": variant(statement=lambda b: b["statement"].replace("\n", "\r\n")),
            "trailing space": variant(statement=lambda b: b["statement"].replace(".\n", ". \n", 1)),
            "reworded": variant(statement=lambda b: b["statement"].replace("nothing further", "the stop")),
            "missing line": variant(statement=lambda b: "".join(b["statement"].splitlines(True)[:-1])),
            "non-ascii": variant(statement=lambda b: b["statement"] + "é"),
            "statement as object": variant(statement={"text": "x"}),
            "observation swapped": variant(observation=other_obs),
            "record subject": variant(record=dict(record, subjectSha256="0" * 64)),
            "record statement": variant(record=dict(record, statementSha256="0" * 64)),
            "record identity": variant(record=dict(record, mainPid="1581")),
            "record cursor": variant(record=dict(record, journalCursor=LATER)),
            "record type": variant(record=dict(record, recordType=E.REPLACEMENT_RECORD_TYPE)),
            "record extra": variant(record=dict(record, accepted=True)),
        }
        for name, bundle in cases.items():
            with self.subTest(name=name), self.assertRaises(E.Refused):
                E.trusted_baseline(bundle, new_release=NEW)
            with self.subTest(name=name, via="classify"), self.assertRaises(E.Refused):
                judge(PATH[E.U1], baseline=bundle, replacement=None)


class ReplacementAcceptanceTests(unittest.TestCase):
    """R2 + R3: POST9A-R is replacement-witness acceptance at U4 under the two-release contract (not package READY);
    the acceptance is local and digest-bound; no repository merge happens during U4."""

    def test_post9a_r_verifies_at_u4_without_single_release_status_or_e01(self):
        report = E.post9a_r(post9a_evidence(), U0_ACCEPT, new_release=NEW)
        self.assertEqual((report["result"], report["reasons"]), ("POST9A_R_VERIFIED", []))
        self.assertEqual((report["invocationId"], report["mainPid"]), REPLACEMENT)
        self.assertEqual(report["notRequired"], ["INSTALLER_STATUS_P1B10_RELEASE_SET", "E01_INSTALLED_RELEASE",
                                                 "PR1_PACKAGE_READY"])
        self.assertEqual(report["authorizes"], "NOTHING")
        # The same U4 state is one the single-release judge refuses: there is no acceptance cycle through E-01.
        entries = tuple(PATH[E.U4]["releaseEntries"])
        observed = PA.InstalledReleaseObservationV1(f"releases/{NEW}", entries, b"{}", (), None, {})
        self.assertEqual(PA.verify_installed_release(observed, release_sha=NEW, attested_manifest_sha256="0" * 64,
                                                     host_targets={}).reason, "RELEASE_SET_UNEXPECTED")
        self.assertNotIn("status", E.POST9A_R_FIELDS)

    def test_post9a_r_rejects_every_missing_or_wrong_element(self):
        ident = {"InvocationID": REPLACEMENT[0], "MainPID": REPLACEMENT[1]}
        moved = {"InvocationID": REPLACEMENT[0], "MainPID": "48212"}
        cases = {
            "observation U3": post9a_evidence(PATH[E.U3]),
            "observation U5": post9a_evidence(PATH[E.U5]),
            "w9 direct": post9a_evidence(w9PhaseDirect="W9_5_GENESIS_COMMITTED_EXACT"),
            "w9 seamed": post9a_evidence(w9PhaseSeamed="W9_5S_GENESIS_COMMITTED_STOPPED"),
            "w10": post9a_evidence(w10Phase="W10_1S_HELD_EXACT_WITNESS_STOPPED"),
            "w10 digest": post9a_evidence(w10OutputSha256="xyz"),
            "health before": post9a_evidence(healthCapture={"before": moved, "after": ident,
                                                            "health": dict(E.HEALTH_EXACT)}),
            "health after": post9a_evidence(healthCapture={"before": ident, "after": moved,
                                                           "health": dict(E.HEALTH_EXACT)}),
            "health class": post9a_evidence(healthCapture={"before": ident, "after": ident, "health": dict(
                E.HEALTH_EXACT, classification="INCONSISTENT")}),
            "health key": post9a_evidence(healthCapture={"before": ident, "after": ident, "health": dict(
                E.HEALTH_EXACT, publicKeySha256="0" * 64)}),
            "denial": post9a_evidence(denials=dict(E.POST9A_R_DENIALS, **{"P1B-9b": "FAIL"})),
            "denial missing": post9a_evidence(denials={"P1B-9b": "PASS", "P1B-10": "PASS"}),
            "baseline": post9a_evidence(baselineSubjectSha256="0" * 64),
        }
        for name, evidence in cases.items():
            with self.subTest(name=name):
                report = E.post9a_r(evidence, U0_ACCEPT, new_release=NEW)
                self.assertEqual(report["result"], "POST9A_R_NOT_VERIFIED")
                with self.assertRaises(E.Refused) as caught:
                    E.render_replacement_statement(evidence, U0_ACCEPT, new_release=NEW)
                self.assertEqual(caught.exception.reason, "POST9A_R_NOT_VERIFIED")

    def test_caller_made_or_rebound_replacement_acceptances_are_refused(self):
        record = REPL_ACCEPT["record"]
        other_baseline_obs = observation(at=cursor("1f00"), after=cursor("1f00"))
        other_u0 = u0_acceptance(other_baseline_obs)
        cases = {
            "caller dict": {"invocationId": REPLACEMENT[0], "mainPid": REPLACEMENT[1], "accepted": True},
            "statement reworded": dict(REPL_ACCEPT, statement=REPL_ACCEPT["statement"].replace("historical", "x")),
            "record pid": dict(REPL_ACCEPT, record=dict(record, mainPid="1")),
            "record subject": dict(REPL_ACCEPT, record=dict(record, subjectSha256="0" * 64)),
            "record cursor": dict(REPL_ACCEPT, record=dict(record, journalCursor=LATER)),
            "evidence not verified": dict(REPL_ACCEPT, evidence=post9a_evidence(denials={})),
            "evidence edited": dict(REPL_ACCEPT, evidence=post9a_evidence(w10OutputSha256=sha(b"other"))),
        }
        for name, bundle in cases.items():
            with self.subTest(name=name), self.assertRaises(E.Refused):
                E.trusted_replacement(bundle, U0_ACCEPT, new_release=NEW)
            with self.subTest(name=name, via="classify"), self.assertRaises(E.Refused):
                judge(PATH[E.U5], replacement=bundle)
        # An acceptance issued under one U0 baseline is not valid under another.
        with self.assertRaises(E.Refused):
            E.trusted_replacement(REPL_ACCEPT, other_u0, new_release=NEW)
        self.assertEqual(E.trusted_replacement(REPL_ACCEPT, U0_ACCEPT, new_release=NEW), REPLACEMENT)

    def test_the_replacement_statement_names_its_evidence_and_limits(self):
        text = REPL_ACCEPT["statement"]
        self.assertIn(E.document_sha256(REPL_ACCEPT["evidence"]), text)
        self.assertIn(sha(U0_ACCEPT["statement"].encode("ascii")), text)
        self.assertIn(f"InvocationID {REPLACEMENT[0]}, MainPID {REPLACEMENT[1]}", text)
        self.assertIn("not the retirement of releases/" + OLD, text)
        self.assertIn("not package READY", text)


class RestartBoundaryTests(unittest.TestCase):
    """R4: verified witness restart protection is a prerequisite in EVERY phase, including U0 (the ending
    incarnation can crash too). Candidate files only; nothing is installed."""

    def test_the_candidate_overlay_files_are_pinned(self):
        files = {f"{E.UNIT_DIR}/{p.parent.name}/{p.name}": sha(p.read_bytes())
                 for p in E.DROPIN_SOURCE.rglob("*") if p.is_file()}
        self.assertEqual(files, E.WITNESS_DROPINS)
        service_text = (E.DROPIN_SOURCE / f"{E.WITNESS_SERVICE}.d/10-no-implicit-restart.conf").read_text("ascii")
        self.assertTrue(service_text.endswith("[Service]\nRestart=no\n"))
        for unit in (E.OWNER_SOCKET, E.SIGNER_SOCKET):
            text = (E.DROPIN_SOURCE / f"{unit}.d/10-no-reactivation.conf").read_text("ascii")
            self.assertTrue(text.endswith("[Unit]\nStopWhenUnneeded=yes\nRefuseManualStart=yes\n"))
        for text in [p.read_text("ascii") for p in E.DROPIN_SOURCE.rglob("*.conf")]:
            self.assertIn("NOT accepted, NOT installed anywhere.", text)

    def test_the_unit_facts_that_make_the_boundary_necessary(self):
        deploy = ROOT / "services/recovery-witness/deploy"
        unit = (deploy / E.WITNESS_SERVICE).read_text(encoding="utf-8")
        for line in ("Restart=on-failure", "RestartSec=5s", "StartLimitBurst=3", "StartLimitIntervalSec=60",
                     "Requires=lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket"):
            self.assertIn(line, unit)
        for name in (E.OWNER_SOCKET, E.SIGNER_SOCKET):
            text = (deploy / name).read_text(encoding="utf-8")
            self.assertIn("Accept=no", text)
            self.assertIn("Service=lilith-recovery-witness.service", text)
            self.assertIn("RemoveOnStop=yes", text)
        for path in deploy.iterdir():                     # static units: nothing starts them at boot
            self.assertNotIn("[Install]", path.read_text(encoding="utf-8"), path.name)

    def test_stop_is_one_transaction_and_start_is_the_service_only(self):
        self.assertEqual(E.STOP_COMMAND, "/usr/bin/systemctl stop lilith-recovery-witness.service "
                                         "lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket")
        self.assertEqual(E.START_COMMAND, "/usr/bin/systemctl start lilith-recovery-witness.service")
        self.assertNotIn("socket", E.START_COMMAND)           # a manual socket start is refused by the boundary

    def test_an_inexact_boundary_is_a_stop_in_every_phase(self):
        mutations = {
            "restart on-failure": lambda b: b["units"][E.WITNESS_SERVICE].update(Restart="on-failure"),
            "no service drop-in": lambda b: b["units"][E.WITNESS_SERVICE].update(DropInPaths=""),
            "reload pending": lambda b: b["units"][E.WITNESS_SERVICE].update(NeedDaemonReload="yes"),
            "owner socket": lambda b: b["units"][E.OWNER_SOCKET].update(StopWhenUnneeded="no"),
            "signer socket": lambda b: b["units"][E.SIGNER_SOCKET].update(RefuseManualStart="no"),
            "drop-in bytes": lambda b: b["dropIns"].update({E.SERVICE_DROPIN: "0" * 64}),
            "extra drop-in": lambda b: b["dropIns"].update({"/etc/systemd/system/x.conf": "0" * 64}),
        }
        for phase, doc in PATH.items():
            for name, mutate in mutations.items():
                changed = copy.deepcopy(doc)
                mutate(changed["witness"]["restartBoundary"])
                with self.subTest(phase=phase, name=name):
                    self.assertEqual(judge(changed)["phase"], E.STOP_BOUNDARY)

    def test_no_socket_contact_while_stopped(self):
        self.assertEqual(E.NO_SOCKET_CONTACT_PHASES, (E.U2, E.U3))
        for phase in E.NO_SOCKET_CONTACT_PHASES:
            doc = copy.deepcopy(PATH[phase])
            doc["witness"]["health"] = dict(E.HEALTH_EXACT)
            with self.subTest(phase=phase):
                self.assertEqual(judge(doc)["phase"], E.STOP_SOCKET_CONTACT)

    def test_automatic_restarts_of_the_ending_witness_are_stops(self):
        one = (H32("auto restart"),)
        auto = (H32("auto restart"), "2222")
        # U0 / U1: a restart after a crash ends 8af12bd6 without a go and loads K-WIT from OLD.
        for entries in ((OLD,), (OLD, NEW)):
            with self.subTest(entries=entries):
                self.assertEqual(judge(observation(entries=entries, identity=auto, loads=one))["phase"],
                                 E.STOP_RESTARTED_ON_OLD)
                self.assertEqual(judge(observation(entries=entries, n_restarts="1"))["phase"],
                                 E.STOP_WITNESS_TRANSITIONAL)
                # With the boundary: the crashed witness stays down, its sockets stop as unneeded.
                self.assertEqual(judge(observation(entries=entries, witness="failed/failed", cwd=None,
                                                   sockets=("inactive", "inactive")))["phase"],
                                 E.STOP_WITNESS_TRANSITIONAL)
        # U4: a restart of the replacement is a second load.
        doc = observation(entries=(OLD, NEW), target=NEW, identity=REPLACEMENT, cwd=NEW,
                          loads=(REPLACEMENT[0], H32("second")))
        self.assertEqual(judge(doc)["phase"], E.STOP_LOADS)


class JournalBindingTests(unittest.TestCase):
    def test_invocations_are_counted_after_the_accepted_u0_cursor_only(self):
        cases = {
            "another after-cursor": observation(entries=(OLD, NEW), after=cursor("1f49")),
            "cursor of another boot": observation(entries=(OLD, NEW), at=cursor("2b01", boot=H32("other boot"))),
            "another journal seqnum id": observation(entries=(OLD, NEW), at=cursor("2b01", seqnum=H32("x"))),
            "cursor before the baseline": observation(entries=(OLD, NEW), at=cursor("1f49")),
            "malformed cursor": observation(entries=(OLD, NEW), at="s=1;i=2"),
            "malformed after-cursor": observation(entries=(OLD, NEW), after="cursor"),
        }
        for name, doc in cases.items():
            with self.subTest(name=name):
                self.assertEqual(judge(doc)["phase"], E.STOP_JOURNAL)
        self.assertEqual(judge(observation(entries=(OLD, NEW), at=CURSOR0))["phase"], E.U1)   # same cursor is fine


class JournalLoadCountingTests(unittest.TestCase):
    """Real systemd 255 (PR #190 probe): `journalctl -u … --after-cursor` returns the running ending incarnation's own
    log lines and its stop entries with its InvocationID. A K-WIT load is a DISTINCT, NEWLY STARTED invocation."""

    ENDING = E.ENDING_INCARNATION[0]

    def test_the_ending_incarnations_own_entries_never_count_in_any_phase(self):
        cases = {
            E.U0: observation(loads=(self.ENDING,)),                                         # its log lines
            E.U1: observation(entries=(OLD, NEW), loads=(self.ENDING,)),
            E.U2: observation(entries=(OLD, NEW), witness="STOPPED", cwd=None, loads=(self.ENDING,)),  # its stop
            E.U3: observation(entries=(OLD, NEW), target=NEW, witness="STOPPED", cwd=None, loads=(self.ENDING,)),
            E.U4: observation(entries=(OLD, NEW), target=NEW, identity=REPLACEMENT, cwd=NEW,
                              loads=(self.ENDING, REPLACEMENT[0])),
            E.U5: observation(entries=(NEW,), target=NEW, identity=REPLACEMENT, cwd=NEW,
                              loads=(REPLACEMENT[0], self.ENDING)),
        }
        for phase, doc in cases.items():
            with self.subTest(phase=phase):
                self.assertEqual(judge(doc)["phase"], phase)

    def test_exactly_one_replacement_and_nothing_else(self):
        one = observation(entries=(OLD, NEW), target=NEW, identity=REPLACEMENT, cwd=NEW, loads=(REPLACEMENT[0],))
        self.assertEqual(judge(one)["phase"], E.U4)
        extra = H32("an unexpected additional incarnation")
        for loads, phase in (((self.ENDING, REPLACEMENT[0], extra), E.STOP_LOADS),
                             ((extra, REPLACEMENT[0]), E.STOP_LOADS),
                             ((self.ENDING,), E.STOP_LOADS),                  # the replacement never logged a start
                             ((), E.STOP_LOADS)):
            doc = observation(entries=(OLD, NEW), target=NEW, identity=REPLACEMENT, cwd=NEW, loads=loads)
            with self.subTest(loads=loads):
                self.assertEqual(judge(doc)["phase"], phase)
        for doc, phase in ((observation(entries=(OLD, NEW), loads=(self.ENDING, extra)), E.STOP_ORIGINAL_RESTARTED),
                           (observation(entries=(OLD, NEW), witness="STOPPED", cwd=None, loads=(self.ENDING, extra)),
                            E.STOP_START_FAILED),
                           (observation(entries=(OLD, NEW), target=NEW, witness="STOPPED", cwd=None,
                                        loads=(E.HISTORICAL_INCARNATIONS[0][0],)), E.STOP_START_FAILED)):
            with self.subTest(phase=phase):
                self.assertEqual(judge(doc)["phase"], phase)

    def test_repeated_messages_are_one_invocation(self):
        lines = [json.dumps({"_SYSTEMD_INVOCATION_ID": self.ENDING, "MESSAGE": f"line {i}"}) for i in range(5)]
        lines += [json.dumps({"INVOCATION_ID": self.ENDING, "UNIT": E.WITNESS_SERVICE, "MESSAGE": "Stopped"})]
        self.assertEqual(O.parse_invocations(lines), [self.ENDING])
        lines += [json.dumps({"INVOCATION_ID": REPLACEMENT[0], "MESSAGE": "Started"})] * 3
        self.assertEqual(O.parse_invocations(lines), [self.ENDING, REPLACEMENT[0]])
        duplicated = observation(entries=(OLD, NEW), target=NEW, identity=REPLACEMENT, cwd=NEW,
                                 loads=(REPLACEMENT[0], REPLACEMENT[0]))
        with self.assertRaises(E.Refused) as caught:                    # a document must carry distinct ids
            judge(duplicated)
        self.assertEqual(caught.exception.reason, "OBSERVATION_FIELDS")

    def test_a_missing_or_unbound_baseline_cursor_is_never_success(self):
        doc = copy.deepcopy(PATH[E.U4])
        doc["witness"]["invocations"]["ids"] = None                     # an unretained cursor (observer F4)
        self.assertEqual(judge(doc)["phase"], E.UNKNOWN)
        doc = copy.deepcopy(PATH[E.U4])
        doc["witness"]["invocations"]["afterCursor"] = None
        self.assertEqual(judge(doc)["phase"], E.UNKNOWN)
        doc = copy.deepcopy(PATH[E.U4])
        doc["witness"]["invocations"]["afterCursor"] = cursor("1f49")
        self.assertEqual(judge(doc)["phase"], E.STOP_JOURNAL)


class InterruptedAndUnsafeStateTests(unittest.TestCase):
    def assertPhase(self, doc, phase, **kw):
        verdict = judge(doc, **kw)
        self.assertEqual(verdict["phase"], phase, verdict["reasons"])
        self.assertEqual(verdict["next"], "STOP")
        self.assertEqual(verdict["recovery"], E.RECOVERY[phase])
        self.assertEqual(verdict["authorizes"], "NOTHING")
        return verdict

    def test_interrupted_stage(self):
        self.assertPhase(observation(entries=(OLD, f".{NEW}.staging")), E.STOP_STAGING)
        self.assertPhase(observation(entries=(OLD, NEW), trees={OLD: True, NEW: False}), E.STOP_NEW_TREE)
        self.assertPhase(observation(entries=(OLD, NEW), trees={OLD: True, NEW: None}), E.UNKNOWN)

    def test_interrupted_or_unclean_stop(self):
        for state in ("deactivating/stop-sigterm", "failed/failed", "activating/auto-restart", "activating/start"):
            with self.subTest(state=state):
                self.assertPhase(observation(entries=(OLD, NEW), witness=state, cwd=None), E.STOP_WITNESS_TRANSITIONAL)
        for sockets in (("active", "inactive"), ("inactive", "active"), ("active", "active")):
            with self.subTest(sockets=sockets):
                self.assertPhase(observation(entries=(OLD, NEW), witness="STOPPED", cwd=None, sockets=sockets),
                                 E.STOP_WITNESS_TRANSITIONAL)
        self.assertPhase(observation(witness="STOPPED", cwd=None), E.STOP_OUT_OF_ORDER)      # stop before stage

    def test_interrupted_or_out_of_order_select(self):
        self.assertPhase(observation(entries=(OLD, NEW), witness="STOPPED", cwd=None,
                                     opt=("current", "releases", ".current.tmp")), E.STOP_SELECTOR)
        self.assertPhase(observation(entries=(OLD, NEW), target=NEW), E.STOP_MIXED)
        self.assertPhase(observation(entries=(OLD, NEW), target="0" * 40), E.STOP_RELEASE_SET)

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
        self.assertPhase(observation(entries=(OLD, NEW), identity=REPLACEMENT, cwd=OLD, loads=one),
                         E.STOP_RESTARTED_ON_OLD)
        for health in (dict(E.HEALTH_EXACT, classification="INCONSISTENT"),
                       dict(E.HEALTH_EXACT, publicKeySha256="0" * 64), dict(E.HEALTH_EXACT, witnessKeyId="x")):
            doc = observation(entries=(OLD, NEW), target=NEW, identity=REPLACEMENT, cwd=NEW, loads=one, health=health)
            self.assertPhase(doc, E.STOP_UNHEALTHY)

    def test_the_ending_incarnation_must_not_change_before_the_stop(self):
        self.assertPhase(observation(identity=(E.ENDING_INCARNATION[0], "1581")), E.STOP_ORIGINAL_RESTARTED)
        self.assertPhase(observation(entries=(OLD, NEW), loads=(H32("x"),)), E.STOP_ORIGINAL_RESTARTED)
        doc = observation(entries=(OLD, NEW), health=dict(E.HEALTH_EXACT, classification="INCONSISTENT"))
        self.assertPhase(doc, E.STOP_ORIGINAL_RESTARTED)

    def test_interrupted_or_early_retire(self):
        one = (REPLACEMENT[0],)
        partial = observation(entries=(OLD, NEW), target=NEW, identity=REPLACEMENT, cwd=NEW, loads=one,
                              trees={OLD: False, NEW: True})
        self.assertPhase(partial, E.STOP_RETIRE_PARTIAL)
        self.assertPhase(partial, E.STOP_OLD_TREE, replacement=None)          # retire began before acceptance
        self.assertPhase(observation(entries=(OLD, NEW), trees={OLD: False, NEW: True}), E.STOP_OLD_TREE)
        self.assertPhase(observation(entries=(NEW,), target=NEW, cwd=OLD), E.STOP_DELETED)
        self.assertPhase(observation(entries=(NEW,), target=NEW, witness="STOPPED", cwd=None), E.STOP_OUT_OF_ORDER)
        self.assertPhase(PATH[E.U5], E.STOP_RETIRED_EARLY, replacement=None)

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


class ReviewProbeRegressionTests(unittest.TestCase):
    """The PR #188 owner-review probes (b) … (h); probe (a) is BaselineTrustTests."""

    def assertUnknown(self, doc, path):
        verdict = judge(doc)
        self.assertEqual(verdict["phase"], E.UNKNOWN, verdict["reasons"])
        self.assertIn("UNOBSERVED:" + path, verdict["reasons"])

    def test_b_unobserved_health_on_a_running_witness_is_unknown(self):
        for phase in (E.U0, E.U1, E.U4, E.U5):
            doc = copy.deepcopy(PATH[phase])
            doc["witness"]["health"] = None
            with self.subTest(phase=phase):
                self.assertUnknown(doc, "witness.health")

    def test_c_d_unobserved_preserved_or_signer_facts_are_unknown_not_halt(self):
        for name in sorted(E.PRESERVED_FIELDS):
            doc = copy.deepcopy(PATH[E.U2])
            doc["preserved"][name] = None
            with self.subTest(name=name):
                self.assertUnknown(doc, "preserved." + name)
        for name in sorted(E.SIGNER_FIELDS):
            doc = copy.deepcopy(PATH[E.U2])
            doc["signer"][name] = None
            with self.subTest(name=name):
                self.assertUnknown(doc, "signer." + name)
        doc = copy.deepcopy(PATH[E.U2])
        doc["preserved"]["holdListing"] = [None]
        self.assertUnknown(doc, "preserved.holdListing[0]")

    def test_e_f_unobserved_cwd_selector_and_other_slots_are_unknown(self):
        cases = {"witness.cwd": (E.U4, lambda d: d["witness"].update(cwd=None)),
                 "currentTarget": (E.U1, lambda d: d.update(currentTarget=None)),
                 "journalCursor": (E.U1, lambda d: d.update(journalCursor=None)),
                 "witness.invocations.ids": (E.U4, lambda d: d["witness"]["invocations"].update(ids=None)),
                 "witness.restartBoundary": (E.U3, lambda d: d["witness"].update(restartBoundary=None)),
                 "witness.service.MainPID": (E.U1, lambda d: d["witness"]["service"].update(MainPID=None)),
                 "witness.ownerSocket": (E.U2, lambda d: d["witness"].update(ownerSocket=None))}
        for path, (phase, mutate) in cases.items():
            doc = copy.deepcopy(PATH[phase])
            mutate(doc)
            with self.subTest(path=path):
                self.assertUnknown(doc, path)

    def test_g_package_readiness_classifies_independently(self):
        for forged in ({"phase": E.U5}, judge(PATH[E.U5])):
            ok, reason = E.package_ready_admissible(forged, U0_ACCEPT, REPL_ACCEPT, release_sha=NEW, new_release=NEW)
            self.assertEqual((ok, reason), (False, "REFUSED:OBSERVATION_FIELDS"))
        self.assertEqual(E.package_ready_admissible(PATH[E.U5], U0_ACCEPT, REPL_ACCEPT, release_sha=NEW,
                                                    new_release=NEW), (True, "U5_SINGLE_NEW_RELEASE"))

    def test_h_pid_reuse_with_a_new_invocation_id_is_still_the_replacement(self):
        """Identity is the InvocationID: a replacement that happens to get PID 1580 is not the ending incarnation."""
        reuse = (H32("r2"), E.ENDING_INCARNATION[1])
        doc = observation(entries=(OLD, NEW), target=NEW, identity=reuse, cwd=NEW, loads=(reuse[0],))
        self.assertEqual(judge(doc)["phase"], E.U4)


class HaltTests(unittest.TestCase):
    def test_every_proven_preserved_fact_change_is_a_halt_in_every_phase(self):
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

    def test_a_proven_halt_takes_precedence_over_unknown_and_stop(self):
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
                       lambda d: d["witness"]["invocations"].update(ids=["NOTHEX"]),
                       lambda d: d["witness"].update(health={"classification": "CONSISTENT"}),
                       lambda d: d.update(treeVerified={OLD: True, NEW: True})):
            doc = copy.deepcopy(PATH[E.U0])
            mutate(doc)
            with self.subTest(mutate=mutate), self.assertRaises(E.Refused):
                judge(doc)


class PackageReadyTests(unittest.TestCase):
    def test_package_ready_is_refused_in_every_intermediate_and_old_state(self):
        for phase, doc in PATH.items():
            for release in (OLD, NEW):
                ok, reason = E.package_ready_admissible(doc, U0_ACCEPT, REPL_ACCEPT, release_sha=release,
                                                        new_release=NEW)
                with self.subTest(phase=phase, release=release):
                    self.assertEqual(ok, phase == E.U5 and release == NEW, reason)
                    if phase in E.TWO_RELEASE_PHASES:
                        self.assertEqual(reason, "TWO_RELEASE_INTERMEDIATE")
        self.assertEqual(E.package_ready_admissible(PATH[E.U5], U0_ACCEPT, None, release_sha=NEW, new_release=NEW),
                         (False, "NOT_EXACT:" + E.STOP_RETIRED_EARLY))
        self.assertEqual(E.package_ready_admissible(PATH[E.U5], U0_ACCEPT, REPL_ACCEPT, release_sha=NEW),
                         (False, "REFUSED:OBSERVATION_RELEASES"))     # a NEW other than the pinned one
        mixed = observation(entries=(OLD, NEW), target=NEW)
        self.assertEqual(E.package_ready_admissible(mixed, U0_ACCEPT, REPL_ACCEPT, release_sha=NEW, new_release=NEW),
                         (False, "NOT_EXACT:" + E.STOP_MIXED))

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

    def test_the_pinned_e19_targets_are_the_swap_of_the_accepted_w10_texts_to_the_pinned_new(self):
        self.assertEqual(set(E.NEW_DR5_TARGETS), set(E.NEW_DR5_SOURCES))
        self.assertEqual(set(E.NEW_DR5_SOURCES.values()), {T10.RUNNING_HELD, T10.STOPPED_HELD})
        for target, source in E.NEW_DR5_SOURCES.items():
            texts = self.w10[source]["texts"]
            swapped = E.derive_release_swap(texts, old=OLD, new=E.NEW_RELEASE)
            again = E.derive_release_swap({k: list(v) for k, v in texts.items()}, old=OLD, new=E.NEW_RELEASE)
            for name in T9.SETS:
                with self.subTest(target=target, name=name):
                    self.assertEqual(swapped[name], again[name])                           # deterministic
                    self.assertEqual((len(swapped[name]), T9.digest(swapped[name])), E.NEW_DR5_TARGETS[target][name])
                    self.assertEqual(swapped[name].count(E.DR5_RELEASE_LINE.format(sha=E.NEW_RELEASE)),
                                     E.DR5_RELEASE_LINE_COUNTS[name])
                    self.assertFalse(any(OLD in line for line in swapped[name]))
                    T9._invariants(name, swapped[name])
                    # the historical W10_1 targets are unchanged and differ wherever a release line moved
                    self.assertEqual(E.NEW_DR5_TARGETS[target][name] == T10.TARGETS[source][name],
                                     name == "predeploy-block")

    def test_the_historical_w10_targets_stay_pinned_and_unaccepted_targets_have_no_phase(self):
        self.assertEqual(T10.TARGETS[T10.RUNNING_HELD], {
            "result-set": (192, "593c90e1778b0e90326cdf96314b328948c00b2207960d27be2b41874d05ff65"),
            "dr5-block": (153, "ace51f27ac17a2d719ec19da582d09e21f0c7fb4be7b6ec81e1dd53cb369fd5a"),
            "predeploy-block": (29, "f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae")})
        self.assertEqual(T10.PHASE_TARGETS, {"W10_1_HELD_EXACT": T10.RUNNING_HELD,
                                             "W10_1S_HELD_EXACT_WITNESS_STOPPED": T10.STOPPED_HELD})
        self.assertEqual(sha((TOOLS / "mb10_dr5_target.py").read_bytes()),
                         "29c359617605f67e812732c4bb6a9ca1b9439bfffcf22285e44d9f6c1999ccf0")
        for name in E.NEW_DR5_TARGETS:                     # no routine comparison can select an E-19 target yet
            self.assertNotIn(name, T10.PHASE_TARGETS.values())
            with self.assertRaises(T9.TargetError):
                T10.target_for(name)

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
        for needle in ("import subprocess", "import socket", "import os", "plink", "gcloud", "Popen", "check_call",
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
