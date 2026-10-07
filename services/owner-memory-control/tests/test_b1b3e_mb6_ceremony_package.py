"""15B2b-B1b-3e M-B6 ceremony package, owner head acceptance and DR-5 target (TEST-ONLY, stdlib).

Records: docs/architecture/slice-15b2b-b1b3e-mb6-ceremony-package.md,
docs/architecture/slice-15b2b-b1b3e-mb6-owner-ledger-head-acceptance.md.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "services/owner-memory-control/tools"
ARCH = ROOT / "docs/architecture"
PACKAGE = ARCH / "slice-15b2b-b1b3e-mb6-ceremony-package.md"
HEAD_RECORD = ARCH / "slice-15b2b-b1b3e-mb6-owner-ledger-head-acceptance.md"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import mb6_dr5_target as T  # noqa: E402
import mb6_ledger_verifier as V  # noqa: E402
import mb6_operator as O  # noqa: E402

CONTROL = "78683b2a36dd5bd2674e9664712b13702d1aa404"
HEAD = "19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630"
OP_JCS_SHA = "8e3bdbdf3f3730de5ad031d36eb390888fc6e0f65307d947522b0138ffcd7b60"
OP_JCS = ('{"environment":"dev","op":"GENESIS","policyVersion":"policy.dev-synthetic.v1","recoveryEpoch":{"counter":1,'
          '"random":"11f184889f333dece054f3b91a301632"},"registryVersion":1,"signingKeyIds":'
          '["test-only.dev-synthetic.actor.b1b3d.1"]}')
DERIVE_TOOL_SHA = "5ecaaaaeba57c8a1afe0d76d0fa0ecaa4ef6bff35d291dc84e0fe7a205a019c8"
POST_RESULT_SET = "3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494"
POST_DR5_BLOCK = "d05aa017672c370b49518297c98709c0381765b9c98a7e29ac9a1edf094e7801"
NOT_AUTHORIZED = ("M-B6 = NOT AUTHORIZED", "M-B7 = NOT AUTHORIZED", "GENESIS = NOT AUTHORIZED",
                  "RECORD_1 = NOT AUTHORIZED", "FIRST_MEMORY = NOT AUTHORIZED", "PROD = NOT AUTHORIZED",
                  "REGISTRY_EFFECTIVE = NO", "AUTHORITY_ACTIVE = NO", "FRESHNESS=UNKNOWN")
FORBIDDEN_CLAIMS = ("M-B6 = AUTHORIZED", "M-B7 = AUTHORIZED", "GENESIS = AUTHORIZED", "REGISTRY_EFFECTIVE = YES",
                    "AUTHORITY_ACTIVE = YES", "FRESHNESS=CURRENT", "POST_MB6_DR5_TARGET_ACCEPTED = YES",
                    "LEDGER_PROVISIONED_OWNER_ACCEPTED = YES")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def flat(text: str) -> str:
    return " ".join(text.split())


# --------------------------------------------------------------------------------- owner head acceptance ---

class OwnerHeadAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.text = HEAD_RECORD.read_text(encoding="utf-8")
        self.state = self.text.split("## 5. State", 1)[1]

    def test_acceptance_state_and_boundaries(self):
        for line in ("OWNER_LEDGER_HEAD_DERIVED = YES", "OWNER_LEDGER_HEAD_ACCEPTED = YES",
                     "OWNER_LEDGER_HEAD_PINNED_FOR_MB6 = YES", "EXPECTED_LEDGER_SEQUENCE = 1",
                     f"EXPECTED_LEDGER_HEAD = {HEAD}", *NOT_AUTHORIZED):
            self.assertIn(line, self.state)
        for claim in FORBIDDEN_CLAIMS:
            self.assertNotIn(claim, self.text)
        for denial in ("ledger state", "witness genesis", "authority activation", "Record 1", "First Memory"):
            self.assertIn(denial, section(self.text, "**It is not:**", "## 5."))

    def test_bindings_are_exact(self):
        table = section(self.text, "## 1. The accepted position", "**The accepted GENESIS op**")
        for value in (CONTROL, DERIVE_TOOL_SHA,
                      "46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e",
                      "bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687",
                      "fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc", HEAD, OP_JCS_SHA,
                      "1f6b3fb93dfd7a31f410737766d98fa7825e256f3e8b11ddea331ec8bf5913a8"):
            self.assertIn(value, table)
        self.assertIn("| expected ledger sequence | `1` |", table)
        self.assertIn(OP_JCS, self.text)

    def test_accepted_values_are_the_repository_computation(self):
        self.assertEqual(sha(OP_JCS.encode()), OP_JCS_SHA)
        self.assertEqual(sha(b"LILITH_AUTHORITY_LEDGER_HEAD_V1\x00" + bytes(32) + OP_JCS.encode()), HEAD)
        self.assertEqual(V.ledger_head(V.pinned_genesis_op()), HEAD)
        self.assertEqual(O.TOOL_PINS[O.EXPECTED], DERIVE_TOOL_SHA)
        self.assertEqual(sha((ROOT / O.EXPECTED).read_bytes()), DERIVE_TOOL_SHA)
        self.assertEqual(O.REGISTRY_DIGEST, "fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc")


# ---------------------------------------------------------------------------------------- DR-5 target ---

def synthetic(extra: list[str] | None = None) -> dict[str, list[str]]:
    """A small baseline with the real shape: the DR-5 block between `test -w /opt` and the proof line."""
    pre = ["DENIED: sudo -n true", "DENIED: sudo -n /usr/bin/id",
           "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=unreadable"]
    block = ["DENIED: test -w /opt", "DENIED: test -w /etc/lilith-authority-dev", *T.SUBSTITUTIONS[0][:1],
             "HOST_PREREQ: /etc/credstore.encrypted PRESENT_SECURE (no maturity meaning)", T.SUBSTITUTIONS[1][0],
             "DEFERRED_UNTIL_OBJECT_EXISTS: /var/lib/lilith-recovery-witness (later step)", *(extra or []),
             *T.INVARIANT_LINES]
    return {"result-set": ["OK: identity", *pre, *block, "SUDO_EFFECTIVE_PROOF=PASS user=x mode=self"],
            "dr5-block": block, "predeploy-block": pre}


def pins(sets: dict[str, list[str]]) -> dict[str, tuple[int, str]]:
    return {name: (len(lines), T.digest(lines)) for name, lines in sets.items()}


class Dr5TargetTests(unittest.TestCase):
    def test_pins_equal_the_package_and_the_accepted_baseline(self):
        text = PACKAGE.read_text(encoding="utf-8")
        self.assertEqual(T.PRE["result-set"], (186, "f18692342cd62572affa54c83f9d390d21ac183e85dc8496dbadb0d5f3f49f9b"))
        self.assertEqual(T.PRE["dr5-block"], (147, "a1d98773bcd07c39b2a17f0628f75db858a3e1e6bcd19e7bcd8918c0e79f1390"))
        self.assertEqual(T.PRE["predeploy-block"], (29, "f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae"))
        self.assertEqual(T.POST["result-set"], (188, POST_RESULT_SET))
        self.assertEqual(T.POST["dr5-block"], (149, POST_DR5_BLOCK))
        self.assertEqual(T.POST["predeploy-block"], T.PRE["predeploy-block"])
        target = section(text, "### 4.2", "### 4.3")
        self.assertIn(f"| full result set | **188** | `{POST_RESULT_SET}` | **161** `DENIED`, **0** `ALLOWED`", target)
        self.assertIn(f"| DR-5 block | **149** | `{POST_DR5_BLOCK}` | **133** `DENIED`, 0 `ALLOWED`", target)
        for name, (lines, digest) in T.PRE.items():
            self.assertIn(f"| {lines} | `{digest}` |", section(text, "### 4.1", "### 4.2"))

    def test_substitutions_are_the_exact_dr5_source_lines(self):
        dr5 = (ROOT / "scripts/deployer_authority_boundary_proof.sh").read_text(encoding="utf-8")
        self.assertIn('ab_say "DEFERRED_UNTIL_OBJECT_EXISTS: ${leaf} (${parent} absent)"', dr5)
        self.assertIn('ab_say "UNOBSERVABLE_BY_DESIGN: ${leaf} (beneath root-only ${parent}; checked only by root tooling)"',
                      dr5)
        self.assertIn('ab_say "DEFERRED_UNTIL_OBJECT_EXISTS: ${path} (later step)"', dr5)
        self.assertIn('ab_say "DENIED: test $1 $2"', dr5)
        self.assertIn("/var/lib/lilith-authority-dev|/var/lib/lilith-authority-dev/authority_ledger.db", dr5)
        later = dr5.split("ab_check_later_state() {", 1)[1].split("\n}", 1)[0]
        order = [later.index(f'ab_deny {op} "${{path}}"') for op in ("-w", "-r", "-x")]
        self.assertEqual(order, sorted(order))
        readers = [line for line in dr5.splitlines() if "/var/lib/lilith-authority-dev" in line]
        self.assertEqual(len(readers), 2)                                            # only these two code paths
        self.assertTrue(readers[0].startswith("/var/lib/lilith-authority-dev|"))      # the leaf-loop entry
        self.assertTrue(readers[1].startswith('readonly AB_LATER="/var/lib/lilith-authority-dev '))
        (ledger_old, ledger_new), (state_old, state_new) = T.SUBSTITUTIONS
        self.assertEqual(ledger_old, "DEFERRED_UNTIL_OBJECT_EXISTS: /var/lib/lilith-authority-dev/authority_ledger.db "
                                     "(/var/lib/lilith-authority-dev absent)")
        self.assertEqual(ledger_new, ("UNOBSERVABLE_BY_DESIGN: /var/lib/lilith-authority-dev/authority_ledger.db "
                                      "(beneath root-only /var/lib/lilith-authority-dev; checked only by root tooling)",))
        self.assertEqual(state_old, "DEFERRED_UNTIL_OBJECT_EXISTS: /var/lib/lilith-authority-dev (later step)")
        self.assertEqual(state_new, tuple(f"DENIED: test {op} /var/lib/lilith-authority-dev" for op in ("-w", "-r", "-x")))

    def test_derive_applies_exactly_the_delta(self):
        sets = synthetic()
        result = T.derive({name: T.encode(lines) for name, lines in sets.items()}, pre_pins=pins(sets), post_pins=None)
        post = result["texts"]
        self.assertEqual(len(post["result-set"]), len(sets["result-set"]) + 2)
        self.assertEqual(len(post["dr5-block"]), len(sets["dr5-block"]) + 2)
        self.assertEqual(post["predeploy-block"], sets["predeploy-block"])
        i = sets["dr5-block"].index(T.SUBSTITUTIONS[0][0])
        self.assertEqual(post["dr5-block"][i], T.SUBSTITUTIONS[0][1][0])
        j = sets["dr5-block"].index(T.SUBSTITUTIONS[1][0])
        self.assertEqual(post["dr5-block"][j + 0:j + 3], list(T.SUBSTITUTIONS[1][1]))
        untouched = [line for line in sets["result-set"] if line not in (T.SUBSTITUTIONS[0][0], T.SUBSTITUTIONS[1][0])]
        self.assertEqual([line for line in post["result-set"] if line in untouched], untouched)   # order kept
        c = result["sets"]["result-set"]
        self.assertEqual((c["counts"]["DENIED"] - c["preCounts"]["DENIED"], c["counts"]["ALLOWED"]), (3, 0))
        self.assertEqual(c["counts"]["DEFERRED_UNTIL_OBJECT_EXISTS"], c["preCounts"]["DEFERRED_UNTIL_OBJECT_EXISTS"] - 2)
        self.assertEqual(c["counts"]["UNOBSERVABLE_BY_DESIGN"], c["preCounts"]["UNOBSERVABLE_BY_DESIGN"] + 1)
        self.assertEqual((result["accepted"], result["derived"]), (False, True))
        again = T.derive({name: T.encode(lines) for name, lines in sets.items()}, pre_pins=pins(sets), post_pins=None)
        self.assertEqual(again, result)                                               # deterministic

    def test_derive_refusals(self):
        good = synthetic()
        cases = (
            ("pre not accepted", good, {**pins(good), "dr5-block": (1, "0" * 64)}, "PRE_NOT_ACCEPTED:dr5-block"),
            ("allowed in baseline", synthetic(["ALLOWED(unexpected) test -w /opt"]), None, "TARGET_HAS_ALLOWED_OR_FAIL"),
            ("fail in baseline", synthetic(["FAIL: DENIAL_VACUOUS_PATH_ABSENT -w /x"]), None,
             "TARGET_HAS_ALLOWED_OR_FAIL"),
            ("source twice", synthetic([T.SUBSTITUTIONS[1][0]]), None, "SUBSTITUTION_SOURCE_NOT_EXACTLY_ONCE"),
            ("target already present", synthetic([T.SUBSTITUTIONS[1][1][0]]), None, "SUBSTITUTION_TARGET_ALREADY_PRESENT"),
        )
        for name, sets, pre_pins, reason in cases:
            with self.subTest(name):
                with self.assertRaises(T.TargetError) as caught:
                    T.derive({n: T.encode(lines) for n, lines in sets.items()}, pre_pins=pre_pins or pins(sets),
                             post_pins=None)
                self.assertTrue(caught.exception.reason.startswith(reason), caught.exception.reason)
        missing = synthetic()
        missing["dr5-block"].remove(T.SUBSTITUTIONS[0][0])
        missing["result-set"].remove(T.SUBSTITUTIONS[0][0])
        with self.assertRaises(T.TargetError) as caught:
            T.derive({n: T.encode(lines) for n, lines in missing.items()}, pre_pins=pins(missing), post_pins=None)
        self.assertEqual(caught.exception.reason, "SUBSTITUTION_SOURCE_NOT_EXACTLY_ONCE")
        no_grant = synthetic()
        no_grant["predeploy-block"][-1] = no_grant["result-set"][3] = "ACTIVATION=ACCEPTED {} advisoryConfigEnabled=true"
        with self.assertRaises(T.TargetError) as caught:
            T.derive({n: T.encode(lines) for n, lines in no_grant.items()}, pre_pins=pins(no_grant), post_pins=None)
        self.assertTrue(caught.exception.reason.startswith("TARGET_NOT_GRANT_ABSENT"))
        with self.assertRaises(T.TargetError) as caught:                              # the real pins: a synthetic
            T.derive({n: T.encode(lines) for n, lines in good.items()})              # baseline is not the accepted one
        self.assertTrue(caught.exception.reason.startswith("PRE_NOT_ACCEPTED"))
        crlf = {n: T.encode(lines).replace(b"\n", b"\r\n") for n, lines in good.items()}
        with self.assertRaises(T.TargetError) as caught:
            T.derive(crlf, pre_pins=pins(good), post_pins=None)
        self.assertEqual(caught.exception.reason, "INPUT_NOT_LF_TERMINATED")

    def test_extract_is_the_accepted_rule(self):
        sets = synthetic()
        log = "".join(f"build\tDR-5\t2026-10-07T05:49:49.1234567Z {line}\n" for line in
                      ["+ bash scripts/deployer_authority_boundary_proof.sh", *sets["result-set"], "echo done"])
        extracted = T.extract("﻿" + log)
        self.assertEqual(extracted, sets)
        self.assertEqual(T.extract(log.replace("\n", "\r\n")), sets)

    def test_compare_is_phase_bound(self):
        sets = synthetic()
        post = T.derive({n: T.encode(lines) for n, lines in sets.items()}, pre_pins=pins(sets), post_pins=None)["texts"]
        log_pre = "\n".join(sets["result-set"]) + "\n"
        log_post = "\n".join(post["result-set"]) + "\n"
        with mock.patch.dict(T.PRE, pins(sets)), mock.patch.dict(T.POST, pins(post)):
            self.assertEqual(T.compare(T.PRE_PHASE, log_pre)["result"], "EQUAL")
            self.assertEqual(T.compare(T.POST_PHASE, log_post)["result"], "EQUAL")
            self.assertEqual(T.compare(T.POST_PHASE, log_pre)["result"], "DRIFT")        # unchanged text after M-B6
            self.assertEqual(T.compare(T.PRE_PHASE, log_post)["result"], "DRIFT")
            drift = log_post.replace("DENIED: test -x /var/lib/lilith-authority-dev",
                                     "ALLOWED(unexpected) test -x /var/lib/lilith-authority-dev")
            report = T.compare(T.POST_PHASE, drift)
            self.assertEqual((report["result"], report["allowed"]), ("DRIFT", 1))
            self.assertFalse(report["accepted"])
            for phase in ("W6_1_STATE_DIRECTORY_INEXACT", "W6_2_STATE_DIRECTORY_EXACT_EMPTY", "W6_3_LEDGER_INCOMPLETE",
                          "W6_4_COMMITTED_CLI_INCOMPLETE", "UNCLASSIFIED_STOP", ""):
                with self.assertRaises(T.TargetError) as caught:
                    T.compare(phase, log_post)
                self.assertEqual(caught.exception.reason, "NO_BASELINE_STOP:" + phase)
        self.assertEqual((T.PRE_PHASE, T.POST_PHASE), (V.W6_0, V.COMMITTED))

    def test_cli_forms_and_read_only_source(self):
        with tempfile.TemporaryDirectory() as work:
            log = Path(work) / "run.log"
            log.write_text("\n".join(synthetic()["result-set"]) + "\n", encoding="utf-8")
            out = subprocess.run([sys.executable, "-I", "-B", str(TOOLS / "mb6_dr5_target.py"), "extract", str(log)],
                                 capture_output=True, timeout=60)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(json.loads(out.stdout)["dr5-block"]["lines"], len(synthetic()["dr5-block"]))
            bad = subprocess.run([sys.executable, "-I", "-B", str(TOOLS / "mb6_dr5_target.py"), "compare",
                                  "W6_3_LEDGER_INCOMPLETE", str(log)], capture_output=True, timeout=60)
            self.assertEqual(bad.returncode, 2)
            self.assertIn(b"NO_BASELINE_STOP", bad.stderr)
            self.assertEqual(sorted(os.listdir(work)), ["run.log"])                 # wrote nothing
        source = (TOOLS / "mb6_dr5_target.py").read_text(encoding="utf-8").split('"""', 2)[2]
        for forbidden in ("subprocess", "socket", "urllib", "write_bytes", "write_text", "open(", "gcloud", "ssh"):
            self.assertNotIn(forbidden, source, forbidden)


# ------------------------------------------------------------------------------------------- package ---

class PackageTests(unittest.TestCase):
    def setUp(self):
        self.text = PACKAGE.read_text(encoding="utf-8")
        self.state = self.text.split("## 17. State", 1)[1]

    def test_state_and_boundaries(self):
        for line in (*NOT_AUTHORIZED, "M-B8 = NOT AUTHORIZED", "M-B9a / M-B9b = NOT AUTHORIZED",
                     "POST_MB6_DR5_TARGET_DERIVED = YES", "POST_MB6_DR5_TARGET_ACCEPTED = NO", "MB6_GO = DRAFT TEMPLATE; NOT ISSUED",
                     "MB6_ACCEPTANCE = DRAFT TEMPLATE; NOT ISSUED", "OWNER_LEDGER_HEAD_ACCEPTED = YES"):
            self.assertIn(line, self.state)
        for claim in FORBIDDEN_CLAIMS:
            self.assertNotIn(claim, self.text)
        self.assertIn("`MB6_PACKAGE_SOURCE_AND_DESIGN_READY_FOR_REVIEW`", self.text)

    def test_tool_pins_are_the_tree_and_the_operator(self):
        table = section(self.text, "## 1. Control and pinned tools", "**Not used by M-B6.**")
        rows = dict(re.findall(r"^\| `([^`]+)`[^|]*\| [^|]+\| `([0-9a-f]{64})`", table, re.MULTILINE))
        self.assertEqual(rows[O.OPERATOR], sha((ROOT / O.OPERATOR).read_bytes()))
        for path, pin in O.TOOL_PINS.items():
            self.assertEqual(rows.get(path), pin, path)
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)
        for path, digest in rows.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), digest, path)
        self.assertEqual(rows["scripts/deployer_authority_boundary_proof.sh"],
                         "9b569f9bee8f07f0bf13ec1d20e2607d9e01c601a2e94a2988320e5bc4160f43")
        self.assertEqual(rows["scripts/authority_custody_denial_proof.py"],
                         "f4e39c81c24a01be5702f6a65a581fcd08f97e1c5ad4a07326883b605fef1455")

    def test_release_module_pins(self):
        table = section(self.text, "**R-3 module pins**", "| Installed wrapper |")
        rows = dict(re.findall(r"^\| `(lilith_[^`]+)` \| `([0-9a-f]{64})` \|", table, re.MULTILINE))
        self.assertEqual(rows, {**O.RELEASE_MODULES, **O.PROVISION_MODULES})
        self.assertEqual((len(O.RELEASE_MODULES), len(O.PROVISION_MODULES)), (18, 20))
        self.assertFalse(set(O.RELEASE_MODULES) & set(O.PROVISION_MODULES))
        self.assertIn(f"`{O.LEDGER_CLI_SHA256}`", self.text)
        self.assertEqual(sha((ROOT / "services/authority-dev/bin/lilith-authority-ledger-dev").read_bytes()),
                         O.LEDGER_CLI_SHA256)
        sources = {"lilith_authority_dev": "services/authority-dev", "lilith_authority_host": "services/authority-dev",
                   "lilith_authority_root": "services/authority-dev", "lilith_owner_memory": "services/owner-memory-control",
                   "lilith_memory": "services/core-api", "lilith_recovery_witness": "services/recovery-witness"}
        for module, pin in rows.items():                                               # control bytes = the pins
            self.assertEqual(sha((ROOT / sources[module.split("/")[0]] / module).read_bytes()), pin, module)

    def test_go_template_is_the_operator_lines(self):
        block = section(self.text, "The lines are exactly `mb6_operator.MB6_GO_LINES`:\n\n```text\n", "```")
        operator = sha((ROOT / O.OPERATOR).read_bytes())
        expected = [line.format(control="<CONTROL>", operator=operator, head=HEAD, pre="W6_0_NO_MB6_MUTATION")
                    for line in O.MB6_GO_LINES]
        self.assertEqual(block.splitlines(), expected)
        go = " ".join(expected)
        for needed in ("MB6_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_ONE_GO", O.RELEASE_SHA,
                       f"{O.VERIFIER} SHA-256 {O.TOOL_PINS[O.VERIFIER]}", f"{O.RECOVERY} SHA-256 {O.TOOL_PINS[O.RECOVERY]}",
                       f"{O.LEDGER_DENIAL} SHA-256 {O.TOOL_PINS[O.LEDGER_DENIAL]}", f"{O.OPERATOR} SHA-256 {operator}",
                       "(ledger sequence 1)", HEAD, O.REGISTRY_DIGEST, "Pre-state: W6_0_NO_MB6_MUTATION.", "KNOWN_EMPTY",
                       "The deploy freeze holds", "provision 1, exactly one invocation",
                       "REFUSED, FAILED, traceback, timeout, SSH loss, unexpected output, or other STOP after the "
                       "attempt marker consumes this go", "There is no automatic retry",
                       "A partial state enters only the reviewed W6 classifier", "does not authorize M-B7"):
            self.assertIn(needed, go)
        self.assertIn("This template is **not** an owner go.", self.text)

    def test_operator_binds_its_own_bytes_at_control(self):
        source = (TOOLS / "mb6_operator.py").read_text(encoding="utf-8")
        self.assertIn('_need(operator == sha256_hex(Path(__file__).read_bytes()), "OPERATOR_NOT_AT_CONTROL")', source)
        calls: list[list[str]] = []

        def run(argv):
            argv = list(argv)
            calls.append(argv)
            if argv[0] == "git":
                if argv[3] == "rev-parse":
                    return subprocess.CompletedProcess(argv, 0, b"a" * 40 + b"\n", b"")
                if argv[3] == "status":
                    return subprocess.CompletedProcess(argv, 0, b"", b"")
                data = (ROOT / argv[-1].split(":", 1)[1]).read_bytes()
                if argv[-1].endswith("mb6_operator.py"):
                    data += b"# not the reviewed operator\n"
                return subprocess.CompletedProcess(argv, 0, data, b"")
            return subprocess.CompletedProcess(argv, 0, json.dumps({"phase": V.W6_0}).encode(), b"")

        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            (work / "expected").mkdir()
            (work / "expected" / "expected-ledger.json").write_text(json.dumps({
                "derivation": "OWNER_COMPUTED_FROM_REGISTRY_V1", "ledgerSequence": 1, "ledgerHead": HEAD,
                "independentLedgerHead": HEAD, "pinDerivedLedgerHead": HEAD}), encoding="utf-8")
            (work / "go.txt").write_text("Pre-state: W6_0_NO_MB6_MUTATION.\n", encoding="utf-8")
            with self.assertRaises(O.Stop) as caught:
                O.Operator(gcloud=("gcloud",), run=run).mb6(ROOT, work, work / "go.txt")
            self.assertEqual(caught.exception.code, "OPERATOR_NOT_AT_CONTROL")
            self.assertFalse((work / "attempts").exists())
        self.assertFalse(any(call[-1].endswith(O.PROVISION) for call in calls))

    def test_acceptance_template(self):
        block = flat(section(self.text, "## 12. Owner acceptance", "## 13."))
        for needed in ("exactly one /usr/local/sbin/lilith-authority-ledger-dev provision 1", "CLI_SUCCESS_EXACT",
                       "LEDGER_COMMITTED_EXACT", "POST_VERIFIED (W6-6)", f"head {HEAD}",
                       "equal to the owner-accepted expected head", f"GENESIS op JCS SHA-256 {OP_JCS_SHA}",
                       "schema fingerprint 65127a68c61d4dba390e01c61d01a76fdc54e830c374cb05069b0ab0c50d9cb7",
                       "sequence 1", "MB6_LEDGER_DENIAL_PROOF=PASS phase=P1B-6 denied=20 allowed=0", "GRANT_ABSENT",
                       "PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA", "remains DERIVED and NOT ACCEPTED",
                       "REGISTRY_EFFECTIVE = NO", "AUTHORITY_ACTIVE = NO", "does not authorize M-B7",
                       "AUTHORIZATION_REGISTER_COPY_MISSING and GENESIS_PIN_COPY_MISSING remain",
                       "DRAFT TEMPLATE; NOT ISSUED"):
            self.assertIn(needed, block)
        self.assertEqual(V.ACCEPTED_PINS.schema_fingerprint,
                         "65127a68c61d4dba390e01c61d01a76fdc54e830c374cb05069b0ab0c50d9cb7")

    def test_evidence_gate_terminators_and_recovery(self):
        evidence = section(self.text, "## 6. Fresh evidence", "**Order inside the sequence:**")
        self.assertEqual(re.findall(r"^\| (E-\d+) \|", evidence, re.MULTILINE), [f"E-{n}" for n in range(1, 26)])
        for needed in ("`37577178942`", "compare W6_0_NO_MB6_MUTATION", "all 38 module pins and the wrapper pin",
                       f"`{HEAD}`", "status --expect P1B-5 aee323e…` PASS", "W5_INSTALLED_CONTENT_VERIFIED", "KNOWN_EMPTY",
                       "AUTHORITY_CUSTODY_DENIAL_PROOF=PASS phase=P1B-5", "GRANT_ABSENT", "expect W6_0_NO_MB6_MUTATION",
                       "hostInputReasonsExactlyW5Gaps", "`fbdd045c…`", "`c068e533…`", "c4ea3d66…64d8",
                       "6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3",
                       "f87593701ee5e9272363a473a115b87cc06179df3c0b233af4aa62bb5b9b97be",
                       "d76479762007afef828f3901591647dc4a2fb2205f4afac527b66d2cc9c6b032"):
            self.assertIn(needed, evidence)
        gate = section(self.text, "## 7. Closing gate", "## 8.")
        self.assertEqual(re.findall(r"^\| (G-\d+) \|", gate, re.MULTILINE), [f"G-{n}" for n in range(1, 10)])
        self.assertIn("UNKNOWN is **REVALIDATE: no go**", gate)
        validity = section(self.text, "## 3. Validity", "## 4.")
        self.assertEqual(re.findall(r"^ {2}\| (T-\d+) \|", validity, re.MULTILINE), [f"T-{n}" for n in range(1, 13)])
        self.assertIn("**No B-5 §9 terminator.**", validity)
        recovery = section(self.text, "## 10. Crash windows", "## 11.")
        for phase in ("| W6-0 |", "| W6-1 |", "| W6-2 |", "| W6-3 |", "| W6-4 clean |", "| W6-4, data only in the WAL |",
                      "| W6-5 |", "| W6-6 |"):
            self.assertIn(phase, recovery)
        self.assertIn("**STOP / OWNER_ADJUDICATION_REQUIRED**: no checkpoint, no delete, no adoption, no re-provision, "
                      "no retry", recovery)

    def test_post_model_success_boundary_and_freeze(self):
        post = flat(section(self.text, "## 9. Execution and POST model", "## 10."))
        for needed in ("O_EXCL", "exactly one `sudo -n /usr/local/sbin/lilith-authority-ledger-dev provision 1`",
                       "`W6_5_CLI_SUCCEEDED_POST_PENDING`", "`ownerAccepted=false`", "`ledger-denial <repo> <dir>`",
                       "`MB6_LEDGER_DENIAL_PROOF=PASS phase=P1B-6 denied=20 allowed=0`", f"head = `{HEAD}`",
                       "`65127a68…9cb7`", "`registryEffective=false`, `authorityActive=false`"):
            self.assertIn(needed, post)
        boundary = section(self.text, "## 11. Technical success boundary", "## 12.")
        for line in ("LEDGER_PROVISIONED_OWNER_ACCEPTED = NO", "M-B7 = NOT AUTHORIZED", "REGISTRY_EFFECTIVE = NO",
                     "AUTHORITY_ACTIVE = NO", "AUTHORIZATION_REGISTER_COPY_MISSING remains",
                     "GENESIS_PIN_COPY_MISSING remains", f"head = {HEAD}", "sequence = 1"):
            self.assertIn(line, boundary)
        freeze = flat(section(self.text, "## 13. Deployment freeze", "## 14."))
        self.assertIn("It does **not** end at technical success.", freeze)
        self.assertIn("the owner has issued the §12 acceptance", freeze)
        self.assertIn("**never** while unresolved", freeze)
        self.assertIn("compare LEDGER_COMMITTED_EXACT", freeze)
        self.assertIn("`POST_MB6_DR5_TARGET_ACCEPTED = NO`", freeze)

    def test_index_and_ledger(self):
        readme = (ARCH / "README.md").read_text(encoding="utf-8")
        for name in ("slice-15b2b-b1b3e-mb6-ceremony-package.md", "slice-15b2b-b1b3e-mb6-owner-ledger-head-acceptance.md"):
            self.assertIn(f"({name})", readme)
        ledger = (ARCH / "current-architecture-acceptance-ledger-v0.1.md").read_text(encoding="utf-8")
        self.assertIn("### 13.1ag Current-state reconciliation (M-B6 owner head acceptance, DR-5 target and ceremony "
                      "package", ledger)
        self.assertIn("FRESHNESS=UNKNOWN (§13.1ag) | UNASSIGNED |", ledger)
        self.assertLess(ledger.index("### 13.1af"), ledger.index("### 13.1ag"))
        self.assertLess(ledger.index("### 13.1ag"), ledger.index("### 13.2 Checks"))


# ------------------------------------------------------------------------------------- real readiness ---

def _deps() -> bool:
    return all(importlib.util.find_spec(name) is not None for name in ("rfc8785", "cryptography"))


class ReadinessProbeTests(unittest.TestCase):
    @unittest.skipUnless(_deps(), "the probe imports the release with its pinned wheels (rfc8785, cryptography)")
    def test_real_probe_over_a_release_shaped_tree(self):
        sources = {"lilith_authority_dev": "services/authority-dev", "lilith_authority_host": "services/authority-dev",
                   "lilith_authority_root": "services/authority-dev", "lilith_owner_memory": "services/owner-memory-control",
                   "lilith_memory": "services/core-api", "lilith_recovery_witness": "services/recovery-witness"}
        with tempfile.TemporaryDirectory() as work:
            release = Path(work) / "current"
            release.mkdir()
            for package, base in sources.items():
                shutil.copytree(ROOT / base / package, release / package,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            wrapper = Path(work) / "lilith-authority-ledger-dev"
            shutil.copyfile(ROOT / "services/authority-dev/bin/lilith-authority-ledger-dev", wrapper)
            probe = (O.READINESS_PROBE.replace("/opt/lilith-authority-dev/current", release.as_posix())
                     .replace(O.LEDGER_CLI, wrapper.as_posix()))
            env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH",)}
            deps = [str(Path(importlib.util.find_spec(name).origin).parent.parent) for name in ("rfc8785", "cryptography")]
            out = subprocess.run([sys.executable, "-B", "-c", "import sys;sys.path[:0]=" + json.dumps(deps) + ";" + probe],
                                 capture_output=True, timeout=120, cwd=work, env=env)
            self.assertEqual(out.returncode, 0, out.stderr)
            report = json.loads(out.stdout)
            modules = {file: digest for file, digest in report["modules"].values()}
            self.assertEqual(modules, {**O.RELEASE_MODULES, **O.PROVISION_MODULES})
            self.assertEqual(report["ledgerCli"], O.LEDGER_CLI_SHA256)
            report["release"] = "/opt/lilith-authority-dev/current"
            lines = f"releases/{O.RELEASE_SHA}\nRELEASE_PYTHON=executable\n{json.dumps(report)}\n".encode()
            self.assertTrue(O.Operator.readiness_ok(lines))
            tampered = dict(report, ledgerCli="0" * 64)
            self.assertFalse(O.Operator.readiness_ok(
                f"releases/{O.RELEASE_SHA}\nRELEASE_PYTHON=executable\n{json.dumps(tampered)}\n".encode()))
            short = dict(report, modules={n: v for n, v in report["modules"].items() if n != "lilith_authority_root.cli"})
            self.assertFalse(O.Operator.readiness_ok(
                f"releases/{O.RELEASE_SHA}\nRELEASE_PYTHON=executable\n{json.dumps(short)}\n".encode()))


if __name__ == "__main__":
    unittest.main()
