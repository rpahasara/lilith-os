"""15B2b-B1b-3e M-B6 remediation record (TEST-ONLY, stdlib): the record, its pins, the errata, and the
governance boundaries it must keep.

Record: docs/architecture/slice-15b2b-b1b3e-mb6-ledger-remediation.md.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "services/owner-memory-control/tools"
ARCH = ROOT / "docs/architecture"
RECORD = ARCH / "slice-15b2b-b1b3e-mb6-ledger-remediation.md"
PREFLIGHT = ARCH / "slice-15b2b-b1b3e-pr1-live-install-preflight.md"
SEQUENCING = ARCH / "slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import mb6_ledger_recovery as R  # noqa: E402
import mb6_ledger_verifier as V  # noqa: E402
import mb6_operator as O  # noqa: E402

PIN_DERIVED_HEAD = "19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630"
CONTINUITY = "OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_ONE_GO"
DR5_RULE = "PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA"
B5_STATUS = "HISTORICAL_AFTER_MB1_EXERCISED"
B5_PACKET = ARCH / "slice-15b2b-b1b3e-b5-pr1b-authorization-decision.md"
B5_GRANT = ARCH / "slice-15b2b-b1b3e-b5-pr1b-authorization-current-grant.md"
MB4_MB5_PACKAGE = ARCH / "slice-15b2b-b1b3e-mb4-mb5-ceremony-package.md"
UNCHANGED = {
    "services/authority-dev/ceremony/install_authority_dev.py":
        "fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487",
    "services/owner-memory-control/tools/mb4_mb5_trust_install_verifier.py":
        "78f57c01811e20a03ebb06bc114847bad440c7435e85ceb0249a488c659b2361",
    "scripts/authority_custody_denial_proof.py":
        "f4e39c81c24a01be5702f6a65a581fcd08f97e1c5ad4a07326883b605fef1455",
    "scripts/deployer_authority_boundary_proof.sh":
        "9b569f9bee8f07f0bf13ec1d20e2607d9e01c601a2e94a2988320e5bc4160f43",
    "services/owner-memory-control/tools/mb4_mb5_operator.py":
        "e380ab1852ba72fe511c650446867c8d229d95776af3c1d4266fa949c0a9de1a",
    "services/owner-memory-control/tools/mb4_mb5_remove_before_mb6.py":
        "db0629a6a5f39ca65e23010aeeccc565978b7d8990f38d6b8bb6c361046ee104",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def flat(text: str) -> str:
    return " ".join(re.sub(r"^\s*>", " ", text, flags=re.MULTILINE).split())


class Mb6RemediationRecordTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = self.text.split("## 17. State", 1)[1]
        self.decisions = self.text.split("## Owner decisions (2026-10-07)", 1)[1].split("## 1. ", 1)[0]

    def test_state_keeps_every_boundary(self):
        for line in ("TRUST_INSTALLED = YES", "REGISTRY_EFFECTIVE = NO", "AUTHORITY_ACTIVE = NO", "M-B6 = NOT AUTHORIZED",
                     "M-B7 = NOT AUTHORIZED", "M-B8 = NOT AUTHORIZED", "M-B9a / M-B9b = NOT AUTHORIZED",
                     "GENESIS = NOT AUTHORIZED", "RECORD_1 = NOT AUTHORIZED", "FIRST_MEMORY = NOT AUTHORIZED",
                     "PROD = NOT AUTHORIZED", "FRESHNESS=UNKNOWN", "REGISTRY_INSTALLED = YES",
                     "AUTHORIZATION_REGISTER_COPY_MISSING + GENESIS_PIN_COPY_MISSING = PRESERVED (M-B8 WORK)",
                     "RUNTIME TIMEOUT FIX = DEFERRED; NO RELEASE-PAYLOAD CHANGE"):
            self.assertIn(line, self.state)
        for claim in ("M-B6 = AUTHORIZED", "M-B7 = AUTHORIZED", "GENESIS = AUTHORIZED", "REGISTRY_EFFECTIVE = YES",
                      "AUTHORITY_ACTIVE = YES", "FRESHNESS=CURRENT", "MB6_CONTINUITY = PROPOSED",
                      "POST_MB6_DR5_BASELINE = ACCEPTED", "Proposed, for a later explicit owner decision"):
            self.assertNotIn(claim, self.text)

    def test_record_pins_equal_the_operator_and_the_tree(self):
        for name in ("mb6_ledger_verifier.py", "mb6_ledger_recovery.py", "mb6_expected_ledger_head.py",
                     "mb6_ledger_denial_proof.py"):
            path = f"services/owner-memory-control/tools/{name}"
            digest = sha(ROOT / path)
            self.assertEqual(O.TOOL_PINS[path], digest, name)
            self.assertIn(f"SHA-256 `{digest}`", self.text, name)
        for path, digest in UNCHANGED.items():
            self.assertEqual(sha(ROOT / path), digest, path)
            if path in O.TOOL_PINS:
                self.assertEqual(O.TOOL_PINS[path], digest, path)

    def test_pin_derived_head_is_reported_as_a_cross_check_only(self):
        self.assertEqual(V.ledger_head(V.pinned_genesis_op()), PIN_DERIVED_HEAD)
        self.assertIn(f"PIN-DERIVED LEDGER HEAD = {PIN_DERIVED_HEAD} (CROSS-CHECK ONLY; NOT OWNER-COMPUTED; NOT ACCEPTED)",
                      self.state)
        self.assertNotIn("PIN-DERIVED LEDGER HEAD = " + PIN_DERIVED_HEAD + " (ACCEPTED", self.text)

    def test_errata_are_appended_and_originals_preserved(self):
        pre, seq = PREFLIGHT.read_text(encoding="utf-8"), SEQUENCING.read_text(encoding="utf-8")
        for original in ("| M-B6 | signer uid (via root) | ledger | provision `authority_ledger.db` at sequence 1 | sequence 1; "
                         "head = owner value; fingerprint | remove (before M-B9 only) |",
                         "| M-B8 | owner / root | pin | owner stores the pin off-host (PR-3 foundation); root installs the "
                         "on-host copy |",
                         "creates the directory `0700`, the DB, and exactly one `GENESIS` op from registry v1"):
            self.assertIn(original, pre)
        self.assertIn("there is no state with storage but no genesis row", seq)
        for erratum, where in (("M-B6 remediation D-5", pre), ("M-B6 remediation D-3", pre),
                               ("M-B6 remediation D-2 and D-4", pre), ("M-B6 remediation D-1", seq)):
            self.assertIn(f"> **Erratum (2026-10-07, {erratum};", where)
        self.assertIn("installs **both** the on-host genesis-pin copy and the authorization-register copy", flat(pre))
        self.assertIn("is **before M-B9b**", flat(pre))

    def test_dr5_delta_is_grounded_in_the_unchanged_dr5_source(self):
        dr5 = (ROOT / "scripts/deployer_authority_boundary_proof.sh").read_text(encoding="utf-8")
        self.assertIn('readonly AB_LATER="/var/lib/lilith-authority-dev ', dr5)
        self.assertIn("/var/lib/lilith-authority-dev|/var/lib/lilith-authority-dev/authority_ledger.db", dr5)
        later = dr5.split("ab_check_later_state() {", 1)[1].split("\n}", 1)[0]
        self.assertLess(later.index('ab_deny -w "${path}"'), later.index('ab_deny -r "${path}"'))
        self.assertLess(later.index('ab_deny -r "${path}"'), later.index('ab_deny -x "${path}"'))
        self.assertIn('ab_say "DEFERRED_UNTIL_OBJECT_EXISTS: ${path} (later step)"', later)
        self.assertIn('ab_say "UNOBSERVABLE_BY_DESIGN: ${leaf} (beneath root-only ${parent}; checked only by root tooling)"',
                      dr5)
        self.assertIn('ab_say "DENIED: test $1 $2"', dr5)
        for line in ("`DEFERRED_UNTIL_OBJECT_EXISTS: /var/lib/lilith-authority-dev (later step)`",
                     "`DENIED: test -w /var/lib/lilith-authority-dev`",
                     "`UNOBSERVABLE_BY_DESIGN: /var/lib/lilith-authority-dev/authority_ledger.db (beneath root-only "
                     "/var/lib/lilith-authority-dev; checked only by root tooling)`"):
            self.assertIn(line, self.text)

    def test_known_empty_and_w5_gap_statements(self):
        self.assertIn("KNOWN_EMPTY (owner freshness register) != OwnerAuthorizationRegisterV1 (authorization-register copy) "
                      "!= OwnerGenesisPinV1", self.text)
        self.assertEqual(V.EXPECTED_HOST_INPUT_REASONS,
                         {"AUTHORIZATION_REGISTER_COPY_MISSING", "GENESIS_PIN_COPY_MISSING"})
        go = " ".join(O.MB6_GO_LINES)
        self.assertIn("KNOWN_EMPTY was freshly established in this sequence from Replica A and Replica B", go)
        self.assertIn("M-B6 does not install either copy", go)

    def test_index_and_ledger(self):
        readme = (ARCH / "README.md").read_text(encoding="utf-8")
        self.assertIn("(slice-15b2b-b1b3e-mb6-ledger-remediation.md)", readme)
        ledger = (ARCH / "current-architecture-acceptance-ledger-v0.1.md").read_text(encoding="utf-8")
        self.assertIn("### 13.1ae Current-state reconciliation (M-B6 PROVISION_LEDGER repository remediation / design", ledger)
        self.assertIn("### 13.1af Current-state reconciliation (M-B6 owner governance decisions, 2026-10-07)", ledger)
        self.assertIn("FRESHNESS=UNKNOWN (§13.1af) | UNASSIGNED |", ledger)
        self.assertLess(ledger.index("### 13.1ae"), ledger.index("### 13.1af"))
        self.assertLess(ledger.index("### 13.1af"), ledger.index("### 13.2 Checks"))


class OwnerDecisionTests(unittest.TestCase):
    """The owner decisions of 2026-10-07 (R-1, R-2A, R-2B, R-3, R-6, timeout, owner head)."""

    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.flat = flat(self.text)
        self.state = self.text.split("## 17. State", 1)[1]
        self.s8 = flat(self.text.split("## 8. M-B6 continuity", 1)[1].split("## 9. ", 1)[0])
        self.s12 = flat(self.text.split("### 12.2 Accepted rule", 1)[1].split("### 12.3", 1)[0])
        self.s123 = flat(self.text.split("### 12.3 B-5 §9 after M-B1", 1)[1].split("## 13. ", 1)[0])
        self.s61 = flat(self.text.split("### 6.1 W6-4 policy", 1)[1].split("## 7. ", 1)[0])

    # -- R-1 ---------------------------------------------------------------------------------------
    def test_mb6_continuity_is_the_exact_accepted_value(self):
        self.assertIn(f"MB6_CONTINUITY = {CONTINUITY} (OWNER-ACCEPTED 2026-10-07, R-1; M-B6 ONLY)", self.state)
        self.assertIn(f"| R-1 | M-B6 continuity model | `MB6_CONTINUITY = {CONTINUITY}` | §8 |", self.text)
        self.assertIn(f"Continuity: MB6_CONTINUITY = {CONTINUITY}.", O.MB6_GO_LINES)
        self.assertIn("It is not broadened to later M-steps", self.s8)
        table = self.text.split("| # | Accepted semantics |", 1)[1].split("\n\n", 1)[0]
        self.assertEqual(re.findall(r"^\| (MC-\d+) \|", table, flags=re.MULTILINE), [f"MC-{n}" for n in range(1, 16)])

    def test_one_sequence_one_go_one_provision(self):
        for needed in ("| MC-1 | One owner-attended, evidence-bounded preparation/execution sequence. |",
                       "| MC-2 | One fresh evidence set. |", "| MC-6 | Exactly one explicit M-B6 owner go. |",
                       "| MC-7 | Exactly one physical `/usr/local/sbin/lilith-authority-ledger-dev provision 1` invocation. |",
                       "| MC-4 | The owner-computed expected ledger head must be derived and pinned before the M-B6 go. |",
                       "| MC-5 | KNOWN_EMPTY must be freshly established from accepted Replica A and Replica B evidence "
                       "before eligibility/go. |"):
            self.assertIn(needed, self.text)
        source = (TOOLS / "mb6_operator.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("self.ssh(PROVISION)"), 1)
        self.assertEqual(O.PROVISION, "sudo -n /usr/local/sbin/lilith-authority-ledger-dev provision 1")
        self.assertIn('"invocationsPermitted": 1', source)
        self.assertIn("Command: /usr/local/sbin/lilith-authority-ledger-dev provision 1, exactly one invocation.",
                      O.MB6_GO_LINES)

    def _operator(self, provision):
        calls: list[list[str]] = []

        def run(argv):
            argv = list(argv)
            calls.append(argv)
            if argv[0] == "git":
                if argv[3] == "rev-parse":
                    return subprocess.CompletedProcess(argv, 0, b"a" * 40 + b"\n", b"")
                if argv[3] == "status":
                    return subprocess.CompletedProcess(argv, 0, b"", b"")
                return subprocess.CompletedProcess(argv, 0, (ROOT / argv[-1].split(":", 1)[1]).read_bytes(), b"")
            if argv[-1].endswith(O.PROVISION):
                return provision()
            return subprocess.CompletedProcess(argv, 0, json.dumps({"phase": V.W6_0}).encode(), b"")

        return O.Operator(gcloud=("gcloud",), run=run), calls

    def _work(self, root: Path, drop: int | None = None) -> Path:
        (root / "expected").mkdir()
        (root / "expected" / "expected-ledger.json").write_text(json.dumps({
            "derivation": "OWNER_COMPUTED_FROM_REGISTRY_V1", "ledgerSequence": 1, "ledgerHead": PIN_DERIVED_HEAD,
            "independentLedgerHead": PIN_DERIVED_HEAD, "pinDerivedLedgerHead": PIN_DERIVED_HEAD}), encoding="utf-8")
        lines = [line.format(control="a" * 40, head=PIN_DERIVED_HEAD, pre=V.W6_0) for line in O.MB6_GO_LINES]
        if drop is not None:
            del lines[drop]
        (root / "go.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return root / "go.txt"

    def test_pre_marker_failure_consumes_no_go(self):
        self.assertIn("| MC-9 | Failures before the attempt marker is created consume nothing. |", self.text)
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            go = self._work(work, drop=1)
            op, calls = self._operator(lambda: self.fail("provision must not run"))
            with self.assertRaises(O.Stop) as caught:
                op.mb6(ROOT, work, go)
            self.assertEqual(caught.exception.code, "GO_LINE_MISSING")
            self.assertFalse((work / "attempts" / "mb6.json").exists())
            self.assertFalse(any(c[-1].endswith(O.PROVISION) for c in calls))

    def test_post_marker_failure_consumes_the_go_and_there_is_no_automatic_retry(self):
        self.assertIn("| MC-8 | A REFUSED, FAILED, traceback, timeout, SSH loss, unexpected output, or other post-marker "
                      "STOP consumes the go. |", self.text)
        self.assertIn("| MC-10 | There is no automatic retry. |", self.text)
        self.assertIn("There is no automatic retry.", " ".join(O.MB6_GO_LINES))
        for name, provision in (
                ("refused", lambda: subprocess.CompletedProcess([], 2, b"", b"lilith-authority-ledger-dev: REFUSED X\n")),
                ("traceback", lambda: subprocess.CompletedProcess([], 1, b"", b"Traceback\n")),
                ("ssh loss", lambda: subprocess.CompletedProcess([], 255, b"", b"")),
                ("timeout", lambda: (_ for _ in ()).throw(subprocess.TimeoutExpired(["gcloud"], 900)))):
            with self.subTest(name), tempfile.TemporaryDirectory() as work:
                work = Path(work)
                go = self._work(work)
                op, calls = self._operator(provision)
                result = op.mb6(ROOT, work, go)
                self.assertEqual((result["attempt"], result["result"]), ("CONSUMED", "MB6_STOP"))
                self.assertTrue((work / "attempts" / "mb6.json").is_file())
                with self.assertRaises(O.Stop) as caught:
                    op.mb6(ROOT, work, go)
                self.assertEqual(caught.exception.code, "ATTEMPT_ALREADY_CONSUMED:mb6")
                self.assertEqual(sum(1 for c in calls if c[-1].endswith(O.PROVISION)), 1)

    def test_partial_state_requires_the_classifier_and_reviewed_recovery(self):
        self.assertIn("| MC-11 | Partial outcomes are classified using the reviewed W6 classifier and may enter only an "
                      "explicitly reviewed recovery/adoption path. |", self.text)
        for host in (V.W6_1, V.W6_2, V.W6_3):
            phase = V.classify_sequence(host_phase=host, ledger_clean=False, attempt_consumed=True,
                                        transcript=V.CLI_FAILED_UNCLASSIFIED, post_verified=False)
            self.assertEqual(phase, host)
        self.assertEqual(V.classify_sequence(host_phase=V.COMMITTED, ledger_clean=True, attempt_consumed=True,
                                             transcript=V.TRANSPORT_FAILED, post_verified=False), V.W6_4)
        self.assertEqual(R.MUTATING, (R.REMOVE_DIRECTORY, R.REMOVE_FILES, R.ADOPT))
        self.assertIn("RECOVERY_LINES", (TOOLS / "mb6_operator.py").read_text(encoding="utf-8"))

    def test_technical_success_is_not_acceptance_and_not_mb7(self):
        self.assertIn("| MC-12 | Technical M-B6 success and owner acceptance of `LEDGER_PROVISIONED` are separate. |",
                      self.text)
        self.assertIn("| MC-13 | M-B6 acceptance does NOT authorize M-B7. |", self.text)
        source = (TOOLS / "mb6_operator.py").read_text(encoding="utf-8")
        self.assertIn('"ownerAccepted": False', source)
        self.assertIn("M-B7 is not authorized", source)
        self.assertIn("This go does not accept LEDGER_PROVISIONED, and does not authorize M-B7", " ".join(O.MB6_GO_LINES))
        self.assertIn("| MC-14 | No wall-clock TTL. |", self.text)
        self.assertIn("| MC-15 | Relevant drift or uncertainty means REVALIDATE / current sequence not reusable. |",
                      self.text)

    # -- R-2A --------------------------------------------------------------------------------------
    def test_phase_bound_dr5_rule_is_accepted_and_the_pre_baseline_preserved(self):
        self.assertIn(f"POST_MB6_DR5_RULE = {DR5_RULE} (OWNER-ACCEPTED 2026-10-07, R-2A); DR-5 UNCHANGED; "
                      "NO GLOBAL REBASELINE", self.state)
        self.assertIn("PRE_MB6_DR5_BASELINE = PRESERVED (HISTORICAL EVIDENCE)", self.state)
        self.assertIn("POST_MB6_DR5_BASELINE = NOT DERIVED; NOT ACCEPTED", self.state)
        self.assertIn("| DR6-1 | Preserve the accepted pre-M-B6 DR-5 baseline unchanged as historical evidence (run "
                      "`36552218231`", self.text)
        self.assertEqual(len(re.findall(r"^\| DR6-\d+ \|", self.text, flags=re.MULTILINE)), 12)
        self.assertEqual(sha(ROOT / "scripts/deployer_authority_boundary_proof.sh"),
                         UNCHANGED["scripts/deployer_authority_boundary_proof.sh"])

    def test_arbitrary_dr5_drift_remains_failure(self):
        for rule in ("| DR6-4 | Do NOT treat arbitrary differences as expected. |",
                     "| DR6-6 | W6-1, W6-2 or W6-3 do not establish an accepted post-M-B6 DR-5 baseline. |",
                     "| DR6-7 | A deploy while the host is in an unresolved partial M-B6 phase is a STOP. |",
                     "| DR6-8 | Only a verified successful M-B6 state may use the post-M-B6 expected baseline. |",
                     "| DR6-9 | Any `ALLOWED` result remains an unexpected failure. |",
                     "| DR6-10 | Any change to `GRANT_ABSENT` remains an unexpected failure. |",
                     "| DR6-11 | Any difference outside the explicitly derived M-B6 delta remains drift. |",
                     "| DR6-12 | Acceptance of the derived post-M-B6 baseline is separate from the technical M-B6 "
                     "invocation. |"):
            self.assertIn(rule, self.text)
        self.assertIn("The **rule** is accepted. The derived post-M-B6 **baseline** is not", self.s12)

    # -- R-2B --------------------------------------------------------------------------------------
    def test_b5_section_9_is_historical_after_mb1(self):
        self.assertIn(f"B5_SECTION_9_POST_MB1_STATUS = {B5_STATUS}", self.text)
        self.assertIn(f"B5_SECTION_9_POST_MB1_STATUS = {B5_STATUS} (OWNER-ACCEPTED 2026-10-07, R-2B; CLARIFICATION, "
                      "PRIOR TEXT PRESERVED)", self.state)
        self.assertIn("This does **not** retroactively alter M-B1, M-B2, M-B3, M-B4 or M-B5", self.s123)
        self.assertIn("does not replay historical PASS evidence as current evidence", self.s123)
        for path in (B5_PACKET, B5_GRANT, MB4_MB5_PACKAGE):
            text = path.read_text(encoding="utf-8")
            self.assertEqual(text.count("> **Governance clarification (2026-10-07, owner decision R-2B, M-B6 remediation; "
                                        "the text above is unchanged).**"), 1, path.name)
            self.assertIn(f"`B5_SECTION_9_POST_MB1_STATUS = {B5_STATUS}`", text)

    def test_prior_b5_history_is_not_rewritten(self):
        packet = B5_PACKET.read_text(encoding="utf-8")
        section9 = packet.split("## 9. Stop conditions that invalidate an authorization before M-B1", 1)[1]
        self.assertTrue(flat(section9).startswith("Any one of these voids a GRANTED authorization. The owner must then "
                                                  "re-decide."))
        self.assertIn("- a DR-5 result set other than the accepted one after any deployment;", section9)
        self.assertLess(section9.index("come from a merged SHA."), section9.index("> **Governance clarification"))
        grant = B5_GRANT.read_text(encoding="utf-8")
        self.assertIn("**VOID (controlling record: decision packet §9).** The packet §9 states", grant)
        self.assertIn("GRANT SUBJECT TO DECISION PACKET §9 (VOID) AND ADR-0015 (REVALIDATE)", grant)
        package = MB4_MB5_PACKAGE.read_text(encoding="utf-8")
        self.assertIn("  - **T-11** any B-5 §9 stop condition or G-1 … G-9 invalidator.", package)
        self.assertIn("| E-15 | B-5 stop conditions absent |", package)
        self.assertLess(package.index("**T-11**"), package.index("> **Governance clarification"))

    # -- R-6 ---------------------------------------------------------------------------------------
    def test_w6_4_clean_adoption_is_bounded(self):
        self.assertIn("W6_4_CLEAN_COMMITTED = REVIEWED_ADOPTION_PATH_ALLOWED (R-6; BOUNDED)", self.state)
        for condition in ("`LEDGER_COMMITTED_EXACT`;", "sequence = 1;", "the schema fingerprint is exact;",
                          "the exact GENESIS op;", "the exact owner-computed head;", "no later bootstrap state;",
                          "the ledger is clean (the database is the only entry);"):
            self.assertIn(condition, self.s61)
        self.assertIn("The valid committed ledger must not be deleted merely because the original CLI response was lost",
                      self.s61)
        self.assertEqual(R.AFTER[R.ADOPT], V.COMMITTED)
        source = (TOOLS / "mb6_ledger_recovery.py").read_text(encoding="utf-8")
        self.assertIn('action = ADOPT if report["ledgerClean"] else ADJUDICATE', source)

    def test_w6_4_wal_only_is_stop_owner_adjudication(self):
        self.assertIn("W6_4_DATA_ONLY_IN_WAL = STOP / OWNER_ADJUDICATION_REQUIRED (R-6)", self.state)
        for verb in ("checkpoint it;", "delete it;", "adopt it;", "rerun `provision`;", "mutate it;",
                     "infer successful durability."):
            self.assertIn(verb, self.s61)
        self.assertEqual(R.ADJUDICATE, "OWNER_ADJUDICATION_REQUIRED")
        self.assertNotIn(R.ADJUDICATE, R.MUTATING)
        self.assertNotIn(R.ADJUDICATE, R.AFTER)
        source = (TOOLS / "mb6_ledger_recovery.py").read_text(encoding="utf-8").split('"""', 2)[2]
        for forbidden in ("wal_checkpoint", "checkpoint", "sqlite3.connect", "VACUUM"):
            self.assertNotIn(forbidden, source, forbidden)

    # -- timeout and owner head --------------------------------------------------------------------
    def test_runtime_timeout_fix_remains_deferred(self):
        self.assertIn("**Owner decision (2026-10-07): DEFERRED.**", self.text)
        cli = (ROOT / "services/authority-dev/lilith_authority_root/cli.py").read_text(encoding="utf-8")
        self.assertNotIn("TimeoutExpired", cli)

    def test_real_owner_ledger_head_is_still_unaccepted_and_unpinned(self):
        self.assertIn("OWNER-COMPUTED LEDGER HEAD = NOT DERIVED; NOT PINNED; NOT ACCEPTED", self.state)
        self.assertIn("`CROSS_CHECK_ONLY / NOT_OWNER_COMPUTED / NOT_ACCEPTED`", self.text)
        for name in ("mb6_operator.py", "mb6_ledger_verifier.py", "mb6_ledger_recovery.py", "mb6_expected_ledger_head.py",
                     "mb6_ledger_denial_proof.py"):
            self.assertNotIn(PIN_DERIVED_HEAD, (TOOLS / name).read_text(encoding="utf-8"), name)
        self.assertNotIn("{head}", "".join(O.RECOVERY_LINES).replace("{plan}", ""))
        self.assertIn("Owner-computed expected ledger head: {head} (ledger sequence 1).", O.MB6_GO_LINES)
        for claim in ("OWNER-COMPUTED LEDGER HEAD = 19bf", "EXPECTED HEAD = ACCEPTED", "OWNER HEAD PINNED"):
            self.assertNotIn(claim, self.text)

    def test_decision_table_lists_every_owner_decision(self):
        for row in ("| R-1 |", "| R-2A |", "| R-2B |", "| R-3 |", "| R-6 |"):
            self.assertIn(row, flat(self.text.split("## Owner decisions (2026-10-07)", 1)[1].split("## 1. ", 1)[0]))
        self.assertIn("owner decision recorded != M-B6 authorized", self.text)


if __name__ == "__main__":
    unittest.main()
