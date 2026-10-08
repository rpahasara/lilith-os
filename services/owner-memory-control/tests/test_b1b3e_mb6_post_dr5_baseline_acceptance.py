"""15B2b-B1b-3e: post-M-B6 DR-5 baseline owner acceptance and preservation (TEST-ONLY, stdlib).

Record: docs/architecture/slice-15b2b-b1b3e-mb6-post-dr5-baseline-acceptance.md.

Pins: the first post-freeze baseline-establishing deploy and its identities; the accepted baseline (equal to the
canonical tool's pinned target); the verbatim owner acceptance; the PR #166 preservation deploy compared EQUAL;
both phase baselines kept; the earlier completion record still holding NOT ACCEPTED as history; the observer
client anomaly recorded transparently and not as drift; and every later stage, First Memory and PROD unauthorized.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARCH = ROOT / "docs/architecture"
RECORD = ARCH / "slice-15b2b-b1b3e-mb6-post-dr5-baseline-acceptance.md"
COMPLETION = ARCH / "slice-15b2b-b1b3e-mb6-provision-ledger-completion.md"
LEDGER = ARCH / "current-architecture-acceptance-ledger-v0.1.md"
TOOLS = ROOT / "services/owner-memory-control/tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import mb6_dr5_target as T  # noqa: E402

FULL = "3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494"
BLOCK = "d05aa017672c370b49518297c98709c0381765b9c98a7e29ac9a1edf094e7801"
PRE_DEPLOY = "f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae"
HEAD = "19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630"
FORBIDDEN = ("M-B7 = AUTHORIZED", "M-B8 = AUTHORIZED", "FIRST_MEMORY = AUTHORIZED", "REGISTRY_EFFECTIVE = YES",
             "AUTHORITY_ACTIVE = YES", "FRESHNESS=CURRENT", "AUTHORITY_DRIFT = YES", "LEDGER_DRIFT = YES",
             "SUBSTRATE_DRIFT = YES", "PROD = AUTHORIZED")


def flat(text: str) -> str:
    return " ".join(re.sub(r"^\s*>", " ", text, flags=re.MULTILINE).split())


def section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


class PostMb6Dr5AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = self.text.split("## 9. State", 1)[1]

    def test_accepted_baseline_equals_the_canonical_target(self):
        self.assertEqual(T.POST["result-set"], (188, FULL))
        self.assertEqual(T.POST["dr5-block"], (149, BLOCK))
        self.assertEqual(T.POST["predeploy-block"], (29, PRE_DEPLOY))
        phases = section(self.text, "## 1. Phase-bound baselines", "## 2.")
        self.assertIn(f"`POST_MB6_DR5_BASELINE = OWNER-ACCEPTED` | `{FULL}` (188 lines, 161 `DENIED`) | `{BLOCK}` (149 lines) "
                      f"| `{PRE_DEPLOY}` (29 lines) |", phases)

    def test_pre_baseline_preserved_as_history(self):
        phases = section(self.text, "## 1. Phase-bound baselines", "## 2.")
        self.assertIn("`PRE_MB6_DR5_BASELINE = PRESERVED AS HISTORICAL ACCEPTED EVIDENCE` (run `36552218231`)", phases)
        self.assertIn(f"`{T.PRE['result-set'][1]}` (186 lines, 158 `DENIED`)", phases)
        self.assertIn(f"`{T.PRE['dr5-block'][1]}` (147 lines)", phases)
        self.assertIn("PRE_MB6_DR5_BASELINE = PRESERVED AS HISTORICAL ACCEPTED EVIDENCE", self.state)

    def test_first_establishing_deploy(self):
        first = section(self.text, "## 2. The first post-freeze", "## 3.")
        for needed in ("| `FIRST_POST_FREEZE_DEV_DEPLOY` | `37726177957`", "`e1b5a2cf22be9214ccb9cdd429ce1a08b11a9124`",
                       "`37726011359` (`push`), success", "success, 2026-10-08T04:10:10Z–04:13:36Z", "`DEPLOY_REQUIRED`",
                       f"| full result set | 188 | `{FULL}` | 161 `DENIED`, 0 `ALLOWED`, 0 `FAIL`, 3 "
                       "`DEFERRED_UNTIL_OBJECT_EXISTS`, 6 `UNOBSERVABLE_BY_DESIGN` |",
                       f"| DR-5 block | 149 | `{BLOCK}` | 133 `DENIED`, 0 `ALLOWED` |",
                       f"| pre-deploy block | 29 | `{PRE_DEPLOY}` | 28 `DENIED` |"):
            self.assertIn(needed, first)
        self.assertIn("The result was **`EQUAL`**, with `unequal = []`, `allowed = 0` and `fail = 0`", flat(first))

    def test_owner_acceptance_yes_verbatim(self):
        quote = flat(section(self.text, "## 3. Owner acceptance (verbatim)", "```text"))
        for needed in ("I accept the post-M-B6 DR-5 baseline for DEV_SYNTHETIC based on first post-freeze DEV deployment "
                       "37726177957 at control e1b5a2cf22be9214ccb9cdd429ce1a08b11a9124.", FULL, BLOCK, PRE_DEPLOY, HEAD,
                       "Therefore POST_MB6_DR5_TARGET_ACCEPTED = YES.",
                       "This acceptance does not authorize M-B7, M-B8, M-B9a, M-B9b, witness genesis, Record 1, First Memory, "
                       "authority activation or PROD."):
            self.assertIn(needed, quote)
        self.assertIn("POST_MB6_DR5_TARGET_ACCEPTED = YES (2026-10-08; earlier record's NO preserved as history)", self.state)

    def test_preservation_deploy_equal(self):
        preserve = section(self.text, "## 4. The first preservation", "## 5.")
        for needed in ("`dea8a94967cafb2565d61c2339b57f4324cafa01`, merged 2026-10-08T04:26:12Z", "`37727472154` (`push`), success",
                       "`37727603638`, success, 2026-10-08T04:27:54Z–04:31:20Z",
                       "`DEPLOY_REQUIRED`; base `e1b5a2cf22be9214ccb9cdd429ce1a08b11a9124`",
                       f"| full result set | 188 | `{FULL}` | 161 `DENIED`, 0 `ALLOWED`, 0 `FAIL` |",
                       f"| DR-5 block | 149 | `{BLOCK}` | 133 `DENIED`, 0 `ALLOWED` |",
                       "POST_MB6_DR5_COMPARISON = EQUAL", "POST_MB6_ACCEPTED_DR5_BASELINE_PRESERVED = YES"):
            self.assertIn(needed, preserve)
        self.assertIn("POST_MB6_ACCEPTED_DR5_BASELINE_PRESERVED = YES (deploy 37727603638, EQUAL)", self.state)

    def test_ledger_and_authority_preserved(self):
        ledger = flat(section(self.text, "## 5. Ledger and authority preservation", "## 6."))
        for needed in (f"`LEDGER_COMMITTED_EXACT`, sequence 1, head `{HEAD}`", "the committed-image hash (`fae62c87…`)",
                       "The database is still the only ledger-state entry", "`REGISTRY_EFFECTIVE = NO`",
                       "`AUTHORITY_ACTIVE = NO` (`authorityGranted = false`)", "`ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`",
                       "`AUTHORIZATION_REGISTER_COPY_MISSING` and `GENESIS_PIN_COPY_MISSING` remain",
                       "No M-B7-or-later state exists", "no record 1 and no First Memory"):
            self.assertIn(needed, ledger)

    def test_observer_anomaly_recorded_transparently_not_as_drift(self):
        note = flat(section(self.text, "## 6. Procedural note", "## 7."))
        for needed in ("returned **`MB6_HOST_POST_NOT_PASS`**", "exited **`0xC0000005`** (code 3221225477)",
                       "stderr was empty", "`f432b724…`", "re-run returned **`MB6_HOST_POST_PASS`** with all 8 codes 0",
                       "OBSERVER_CLIENT_EXIT_ANOMALY = PROCEDURAL_CLIENT_FAILURE_ONLY", "AUTHORITY_DRIFT = NO",
                       "SUBSTRATE_DRIFT = NO", "LEDGER_DRIFT = NO",
                       "The first process exit is kept on record. The first invocation did **not** succeed"):
            self.assertIn(needed, note)

    def test_rule_going_forward(self):
        rule = flat(section(self.text, "## 7. Rule going forward", "## 8."))
        self.assertIn("a read-only M-B6 verifier read must confirm `LEDGER_COMMITTED_EXACT`", rule)
        self.assertIn("`mb6_dr5_target.py compare LEDGER_COMMITTED_EXACT <fresh-log>` = **`EQUAL`**", rule)
        self.assertIn("**drift requiring owner adjudication**. There is **no automatic rebaseline**", rule)

    def test_boundaries_and_first_memory(self):
        for line in ("M-B7 = NOT AUTHORIZED", "M-B8 = NOT AUTHORIZED", "M-B9a = NOT AUTHORIZED", "M-B9b = NOT AUTHORIZED",
                     "WITNESS GENESIS = NOT AUTHORIZED", "RECORD_1 = NOT AUTHORIZED", "FIRST_MEMORY = NOT AUTHORIZED",
                     "AUTHORITY ACTIVATION = NOT AUTHORIZED", "PROD = NOT AUTHORIZED", "REGISTRY_EFFECTIVE = NO",
                     "AUTHORITY_ACTIVE = NO", "GRANT_ABSENT = TRUE", "AUTHORIZATION_REGISTER_COPY_MISSING = TRUE",
                     "GENESIS_PIN_COPY_MISSING = TRUE", "FRESHNESS=UNKNOWN"):
            self.assertIn(line, self.state)
        for claim in FORBIDDEN:
            self.assertNotIn(claim, self.text)
        boundary = flat(section(self.text, "## 8. Boundaries", "## 9."))
        self.assertIn("Tooling must not infer, choose, draft or write LILITH's First Memory", boundary)
        self.assertIn("the process **STOPS** there. Owner discussion is required before any First Memory content is selected "
                      "or written", boundary)

    def test_earlier_completion_record_keeps_not_accepted_history(self):
        completion = COMPLETION.read_text(encoding="utf-8")
        self.assertIn("POST_MB6_DR5_TARGET_ACCEPTED = NO", completion.split("## 11. State", 1)[1])
        self.assertIn("| `POST_MB6_DR5_TARGET_ACCEPTED` | **NO** |", completion)
        self.assertNotIn("POST_MB6_DR5_TARGET_ACCEPTED = YES", completion)
        self.assertIn("This record supersedes it on this one point only, from 2026-10-08", flat(self.text))

    def test_ledger_and_index(self):
        ledger = LEDGER.read_text(encoding="utf-8")
        self.assertIn("### 13.1ai Current-state reconciliation (post-M-B6 DR-5 baseline owner acceptance and preservation", ledger)
        self.assertLess(ledger.index("### 13.1ah"), ledger.index("### 13.1ai"))
        self.assertLess(ledger.index("### 13.1ai"), ledger.index("### 13.2 Checks"))
        self.assertIn("M-B7 and later, First Memory and PROD NOT AUTHORIZED; FRESHNESS=UNKNOWN (§13.1ai)", ledger)   # AUTH-02
        ah = section(ledger, "### 13.1ah", "### 13.1ai")
        self.assertIn("`POST_MB6_DR5_TARGET_ACCEPTED = NO`", ah)                       # history unchanged
        readme = (ARCH / "README.md").read_text(encoding="utf-8")
        self.assertIn("(slice-15b2b-b1b3e-mb6-post-dr5-baseline-acceptance.md)", readme)


if __name__ == "__main__":
    unittest.main()
