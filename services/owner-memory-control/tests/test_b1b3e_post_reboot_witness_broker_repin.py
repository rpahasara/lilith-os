"""Post-reboot re-pin of the witness and broker identities (2026-10-09).

Record: docs/architecture/slice-15b2b-b1b3e-post-reboot-witness-broker-repin.md. Pure and local: nothing
contacts DEV. Proves the re-pinned values, the exact hash cascade, that each changed file differs from the
merged control only by this re-pin, and that the historical identities can no longer satisfy the pins.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path

import post_reboot_repin as RP
import test_b1b3e_pkgc_record1_envelope as PK  # noqa: E402  (World fixture; sets sys.path for the tools)

import mb4_mb5_operator as M45  # noqa: E402
import mb6_operator as M6  # noqa: E402
import mb7_mb8_operator as A  # noqa: E402
import mb9_operator as O  # noqa: E402
import pkgc_operator as P  # noqa: E402

ROOT = RP.ROOT
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-post-reboot-witness-broker-repin.md"
_spec = importlib.util.spec_from_file_location("post_reboot_repin_broker_gate", ROOT / RP.BROKER)
gate = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = gate
_spec.loader.exec_module(gate)

NEW_WITNESS = ("8af12bd64d024d0eba56bbcedbc534a6", "1580")
OLD_WITNESS = ("5136ea7af2544450b9370fa412786c98", "143946")
NEW_BROKER = ("ed35e343bc9f4ec687f753ed7b3a53b2", "ff3a432d9d8e5c23718be41898be9568dd8914f0e2e28bb4c27f8e0bccaa3ef1",
              "cb0d71da-32a7-402b-b85e-5748da012bff")
OLD_BROKER = ("c4b9cb38d7a041dc91db0d8ada7e8d04", "a30bd7d6e26a75e4eba863c08622aebbbaf72928bc9dc7737fc1f7aa6473069d",
              "eea461c3-60f0-4b10-8ee9-556dcef19711")
GENESIS = "ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4"
CHAIN_1 = "252c32204bebf3fa1ca0981d8791115e2abb6cd8ddb0925285c64213317cfb99"
PKGC_BEFORE = "d7aaf9022982edecf5ff21d53faa1e34e04cf9ef9501a8622b1e3f327b9df298"
PKGC_AFTER = "7577c10bfe1e612bf11b81ac069e90cd47b4abc2c77e388c040bdd52bd1803fa"
MB6_OPERATOR_PIN = "4a91d98421e38326858e141152180c127f5a67306eebe51a8ca8762f0504dcc5"
MB7_MB8_OPERATOR_PIN = "9f13411f363dc956795ce4832d1948e7e6a9a7f7c8d1057291de852e9e2a20cd"
MB4_MB5_OPERATOR_PIN = "e380ab1852ba72fe511c650446867c8d229d95776af3c1d4266fa949c0a9de1a"

# This re-pin's edits, as (after, before) text pairs per file. Reversing them must give back the merged bytes.
REVERSE = {
    RP.BROKER: (RP.CURRENT_BROKER_PIN, RP.HISTORICAL_BROKER_PIN, [
        ("""# Owner-accepted broker continuity baseline, accepted after the M-R1 reboot of
# 2026-10-09 and the one M-R2 broker start (docs/architecture/slice-15b2b-b1b3e-post-reboot-witness-broker-repin.md
# §2, which records the owner acceptance verbatim and pins it).
""", """# Owner-accepted broker continuity baseline, accepted after the controlled
# broker restart of 2026-10-02 (docs/architecture/slice-15b2b-b1b3e-broker-restart-recovery.md
# §6; pinned by docs/architecture/slice-15b2b-b1b3e-broker-restart-repin.md).
"""),
        ('ACCEPTED_CURRENT_INCARNATION = "ed35e343bc9f4ec687f753ed7b3a53b2"',
         'ACCEPTED_CURRENT_INCARNATION = "c4b9cb38d7a041dc91db0d8ada7e8d04"'),
        ('ACCEPTED_CURRENT_BASELINE_SHA256 = "ff3a432d9d8e5c23718be41898be9568dd8914f0e2e28bb4c27f8e0bccaa3ef1"',
         'ACCEPTED_CURRENT_BASELINE_SHA256 = "a30bd7d6e26a75e4eba863c08622aebbbaf72928bc9dc7737fc1f7aa6473069d"'),
        ("""# requires a different one.
ACCEPTED_CURRENT_BOOT_ID = "cb0d71da-32a7-402b-b85e-5748da012bff"
""", """# requires a different one. The 2026-10-02 restart kept the 2026-09-29 boot.
ACCEPTED_CURRENT_BOOT_ID = "eea461c3-60f0-4b10-8ee9-556dcef19711"
"""),
        ('"pid": 3411, "startTicks": 125335,', '"pid": 35622, "startTicks": 26369693,'),
        ("""    # Ended by the M-R1 reboot on 2026-10-09 (kernel 7.0.0-1014-gcp).
    {"runtimeIncarnation": "c4b9cb38d7a041dc91db0d8ada7e8d04", "bootId": "eea461c3-60f0-4b10-8ee9-556dcef19711",
     "baselineCandidateSha256": "a30bd7d6e26a75e4eba863c08622aebbbaf72928bc9dc7737fc1f7aa6473069d",
     "record": "docs/architecture/slice-15b2b-b1b3e-broker-restart-recovery.md"},
""", ""),
    ]),
    O.OPERATOR: (RP.CURRENT_MB9_OPERATOR_PIN, RP.HISTORICAL_MB9_OPERATOR_PIN, [
        ("""    **{path: M6.TOOL_PINS[path] for path in (INSTALLER, W5_VERIFIER, MB6_VERIFIER, OBSERVER, DENIAL, LEDGER_DENIAL)},
    # The broker verifier re-pinned to the owner-accepted post-reboot broker baseline (2026-10-09; record
    # docs/architecture/slice-15b2b-b1b3e-post-reboot-witness-broker-repin.md). The pinned M-B6 and Package A
    # operators stay byte-unchanged and keep their historical pin of it.
    BROKER: "b90ed6efa203f7aade5519120e1658b866aa9f0d4f559e6ac39fcc51573ebfcf",
""", """    **{path: M6.TOOL_PINS[path] for path in (INSTALLER, W5_VERIFIER, MB6_VERIFIER, OBSERVER, BROKER, DENIAL,
                                             LEDGER_DENIAL)},
"""),
    ]),
    P.OPERATOR: (PKGC_AFTER, PKGC_BEFORE, [
        ("read-only tools Package C relies on.\n", "read-only tools Package C relies on. Unchanged here.\n"),
        ("""    # Re-pinned for the post-reboot broker verifier (record slice-15b2b-b1b3e-post-reboot-witness-broker-repin.md).
    MB9_OPERATOR: "2312e26a9cc8c2076539ae8bdde98cc5d79c2bbeb5138d66d07863ec3303c928",
""", """    MB9_OPERATOR: "066fc8213b40c392e3e2bfd609da4a7f2a4e0b6f05da011daee9add3caf13973",
"""),
        ("""    # The owner-accepted post-reboot witness incarnation (2026-10-09, NRestarts 0); the Package B incarnation
    # 5136ea7af2544450b9370fa412786c98 / 143946 is historical (record slice-15b2b-b1b3e-post-reboot-witness-broker-repin.md).
    witness_invocation_id="8af12bd64d024d0eba56bbcedbc534a6",
    witness_main_pid="1580",
""", """    witness_invocation_id="5136ea7af2544450b9370fa412786c98",
    witness_main_pid="143946",
"""),
    ]),
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class CascadeTests(unittest.TestCase):
    def test_each_changed_file_is_the_merged_file_plus_only_this_repin(self):
        for path, (after, before, edits) in REVERSE.items():
            with self.subTest(path):
                data = (ROOT / path).read_bytes()
                self.assertEqual(sha(data), after)
                text = data.decode("utf-8")
                for new, old in edits:
                    self.assertEqual(text.count(new), 1, new)
                    text = text.replace(new, old)
                self.assertEqual(sha(text.encode("utf-8")), before)

    def test_the_current_chain_pins_the_final_bytes(self):
        self.assertEqual(sha((ROOT / RP.BROKER).read_bytes()), RP.CURRENT_BROKER_PIN)
        self.assertEqual(O.TOOL_PINS[O.BROKER], RP.CURRENT_BROKER_PIN)
        self.assertEqual(sha((ROOT / O.OPERATOR).read_bytes()), RP.CURRENT_MB9_OPERATOR_PIN)
        self.assertEqual(P.TOOL_PINS[P.MB9_OPERATOR], RP.CURRENT_MB9_OPERATOR_PIN)
        for path, pin in {**O.TOOL_PINS, **P.TOOL_PINS}.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)
        self.assertEqual(sha((ROOT / P.OPERATOR).read_bytes()), PKGC_AFTER)

    def test_completed_ceremony_operators_are_byte_unchanged_and_fail_closed(self):
        self.assertEqual(sha(Path(M6.__file__).read_bytes()), MB6_OPERATOR_PIN)
        self.assertEqual(sha(Path(A.__file__).read_bytes()), MB7_MB8_OPERATOR_PIN)
        self.assertEqual(sha(Path(M45.__file__).read_bytes()), MB4_MB5_OPERATOR_PIN)
        # mb9 checks those bytes at run time: unchanged, so its pins of them hold.
        self.assertEqual((O.TOOL_PINS[O.MB6_OPERATOR], O.TOOL_PINS[O.MB7_MB8_OPERATOR]),
                         (MB6_OPERATOR_PIN, MB7_MB8_OPERATOR_PIN))
        for module in (M45, M6, A):
            self.assertEqual(module.TOOL_PINS[RP.BROKER], RP.HISTORICAL_BROKER_PIN, module.__name__)
        # Their own hash gate (`tool_bytes` over `git show HEAD:<path>`) refuses the re-pinned verifier.
        for module in (M45, M6, A):
            with self.subTest(module.__name__):
                operator = module.Operator(gcloud=("gcloud",), run=_tree_show)
                with self.assertRaises((M45.Stop, M6.Stop)) as caught:
                    operator.tool_bytes(ROOT, RP.BROKER)
                self.assertEqual(caught.exception.code, "TOOL_PIN_MISMATCH:" + RP.BROKER)
        # The current Package B operator streams it.
        self.assertEqual(O.Operator(gcloud=("gcloud",), run=_tree_show).tool_bytes(ROOT, RP.BROKER),
                         (ROOT / RP.BROKER).read_bytes())


def _tree_show(argv, **_):
    """`git -C <repo> show HEAD:<path>` answered from the working tree (the PR head)."""
    import subprocess

    argv = list(argv)
    assert argv[:2] == ["git", "-C"] and argv[3] == "show", argv
    return subprocess.CompletedProcess(argv, 0, (ROOT / argv[4].split(":", 1)[1]).read_bytes(), b"")


class BrokerPinTests(unittest.TestCase):
    def test_new_broker_identity_is_current_and_old_is_retired(self):
        self.assertEqual((gate.ACCEPTED_CURRENT_INCARNATION, gate.ACCEPTED_CURRENT_BASELINE_SHA256,
                          gate.ACCEPTED_CURRENT_BOOT_ID), NEW_BROKER)
        self.assertEqual((gate.ACCEPTED_CURRENT_IDENTITY["pid"], gate.ACCEPTED_CURRENT_IDENTITY["startTicks"],
                          gate.ACCEPTED_CURRENT_IDENTITY["nRestarts"]), (3411, 125335, "0"))
        retired = {(r["runtimeIncarnation"], r["baselineCandidateSha256"], r["bootId"])
                   for r in gate.RETIRED_BROKER_BASELINES}
        self.assertIn(OLD_BROKER, retired)
        self.assertNotIn(NEW_BROKER, retired)
        self.assertNotEqual(gate.ACCEPTED_CURRENT_BOOT_ID, OLD_BROKER[2])


class WitnessPinTests(unittest.TestCase):
    def setUp(self):
        self.w = PK.World(self)
        self.w.open()
        self.real = dataclasses.replace(self.w.pins, witness_invocation_id=P.ACCEPTED_PINS.witness_invocation_id,
                                        witness_main_pid=P.ACCEPTED_PINS.witness_main_pid)

    def check(self, invocation: str, pid: str) -> dict:
        export = self.w.acquire(report={"witnessInvocationId": invocation, "witnessMainPid": pid})
        return P.check_export(self.w.workdir, export, self.real)

    def test_new_witness_incarnation_is_the_accepted_pin(self):
        self.assertEqual((P.ACCEPTED_PINS.witness_invocation_id, P.ACCEPTED_PINS.witness_main_pid), NEW_WITNESS)
        result = self.check(*NEW_WITNESS)
        self.assertTrue(result["checks"]["incarnationAccepted"])
        self.assertTrue(result["exact"], result["checks"])

    def test_historical_witness_incarnation_cannot_satisfy_package_c(self):
        for invocation, pid in (OLD_WITNESS, (NEW_WITNESS[0], OLD_WITNESS[1]), (OLD_WITNESS[0], NEW_WITNESS[1])):
            with self.subTest(invocation=invocation, pid=pid):
                result = self.check(invocation, pid)
                self.assertFalse(result["checks"]["incarnationAccepted"])
                self.assertFalse(result["exact"])

    def test_witness_lineage_and_other_package_c_pins_are_unchanged(self):
        pins = P.ACCEPTED_PINS
        self.assertEqual((pins.genesis_digest, pins.chain_1_sha256), (GENESIS, CHAIN_1))
        self.assertEqual((pins.environment, pins.authority_profile), ("dev", "DEV_SYNTHETIC"))
        self.assertEqual((pins.registry_sha256, pins.root_anchor_sha256, pins.witness_anchor_sha256),
                         ("46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e",
                          "bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687",
                          "be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a"))
        self.assertEqual((pins.pin_sha256, pins.register_sha256, pins.pin_record_sha256),
                         ("357477369ab53790245b42cbecbe2a630110477bede5b599696699e4f5c3a590",
                          "8d5ab87564d0e531b7d1467c18b6d106f2a468d5d155ce9f2acb64758df85575",
                          "009a0596ca1d7f2f8d941c949c0671f2091b83668aa9315486dbc7f2a0f1e0ae"))
        self.assertEqual((pins.replica_a_id, pins.replica_b_id, pins.replica_b_manifest_sha256),
                         ("owner-primary-dev-synthetic-01", "owner-offline-dev-synthetic-01",
                          "c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4"))


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = self.text.split("## 8. State", 1)[1]

    def test_owner_acceptances_carry_every_pinned_value(self):
        witness = self.text.split("**Witness incarnation**", 1)[1].split("**Broker baseline**", 1)[0]
        broker = self.text.split("**Broker baseline**", 1)[1].split("## 3.", 1)[0]
        for value in (*NEW_WITNESS, GENESIS, CHAIN_1, NEW_BROKER[2], "NRestarts 0"):
            self.assertIn(value, witness)
        for value in (*NEW_BROKER, "PID 3411", "start ticks 125335", "NRestarts 0", *NEW_WITNESS, GENESIS):
            self.assertIn(value, broker)
        self.assertIn(f"The earlier incarnation {OLD_WITNESS[0]} / {OLD_WITNESS[1]} is historical.", witness)
        self.assertIn(f"incarnation {OLD_BROKER[0]} and baseline {OLD_BROKER[1]} are historical.", broker)
        for block in (witness, broker):
            self.assertIn("authorizes nothing further", block)

    def test_record_states_the_final_hashes(self):
        for value in (RP.HISTORICAL_BROKER_PIN, RP.CURRENT_BROKER_PIN, RP.HISTORICAL_MB9_OPERATOR_PIN,
                      RP.CURRENT_MB9_OPERATOR_PIN, PKGC_BEFORE, PKGC_AFTER):
            self.assertIn(f"`{value}`", self.text)

    def test_nothing_is_opened_or_widened(self):
        for line in ("LIVE_MUTATION = NONE", "DEV_CONTACT = NONE", "REGISTRY_EFFECTIVE = NO", "AUTHORITY_ACTIVE = NO",
                     "authorityGranted = false", "SIGNER = INACTIVE", "HOLD_STORE = EMPTY", "RECORD_1 = ABSENT",
                     "PACKAGE_C = NOT OPENED", "C1 = NOT STARTED", "C2 / C3 / C4A / C4B = NOT AUTHORIZED",
                     "FIRST_MEMORY = NOT AUTHORIZED", "PROD = NOT AUTHORIZED",
                     f"WITNESS_GENESIS = {GENESIS} (UNCHANGED)"):
            self.assertIn(line, self.state)
        for claim in ("PACKAGE_C = OPENED", "C1 = STARTED", "RECORD_1 = PRESENT", "FIRST_MEMORY = AUTHORIZED",
                      "AUTHORITY_ACTIVE = YES", "REGISTRY_EFFECTIVE = YES", "SIGNER = ACTIVE"):
            self.assertNotIn(claim, self.text)
        # The Package C acquisition still requires every no-authority fact; the re-pin moved no check.
        source = (ROOT / P.OPERATOR).read_text(encoding="utf-8")
        for check in ('"holdStoreEmpty"', '"signerNoLaterState"', '"registryNotEffective"', '"authorityNotActive"',
                      '"incarnationAccepted"', '"noRestart"', '"rebootRequiredAbsent"', '"BOOT_ID_CHANGED"'):
            self.assertIn(check, source)

    def test_index_lists_the_record(self):
        index = (ROOT / "docs/architecture/README.md").read_text(encoding="utf-8")
        self.assertIn("(slice-15b2b-b1b3e-post-reboot-witness-broker-repin.md)", index)


if __name__ == "__main__":
    unittest.main()
