"""Track B: Privacy rollback protection (anchor + off-host checkpoint + boot freshness + fail-closed serving).

Contracts are exercised directly; the runtime runs over the real Privacy store, the real L04 / L18 V2 owners and the
F9-C mock Hermes executor, with a simulated K-PAN witness and K-PCK owner device (privacy_freshness_fixture). The
negative controls show what the F9-C restore-suppression gate alone serves after a Privacy rollback.
Synthetic temporary databases and per-test keys only.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from test_canonical_runtime import TEST_CLASS, stamp_text  # noqa: F401  (puts the Core API on sys.path)
from test_privacy_forget_runner import FAREWELL, FI
from test_privacy_restore_gate import GatedPathMixin
from test_privacy_restore_suppression import CODENAME, RestoreCase

from privacy_freshness_fixture import ENV, KPAN_ID, KPCK_ID, FreshnessHarness, OwnerDevice, Witness, stamp
from lilith_memory import memory_v2
from lilith_memory import privacy_anchor_contracts as A
from lilith_memory import privacy_forget_runner as R
from lilith_memory import privacy_freshness as F
from lilith_memory import privacy_governance as privacy

SEL = "a" * 64


def entry(n: int):
    return (f"suppress.{n:032x}", f"{n:064x}")


# ===================================================================================================== contracts ===

class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.w, self.o = Witness(), OwnerDevice()
        self.kpan, self.kpck = self.w.key.public_key(), self.o.key.public_key()

    def chain(self, docs):
        return A.verify_anchor_chain(docs, self.kpan, environment=ENV, key_id=KPAN_ID)

    def anchors(self, *batches):
        docs, chain = [], None
        for i, batch in enumerate(batches):
            docs.append(self.w.sign(A.unsigned_anchor_advance(chain, batch, environment=ENV, updated_at=stamp(i),
                                                              key_id=KPAN_ID)))
            chain = self.chain(docs)
        return docs, chain

    def test_set_head_is_order_free_environment_bound_and_refuses_duplicates(self):
        a, b = entry(1), entry(2)
        self.assertEqual(A.suppression_set_head(ENV, [a, b]), A.suppression_set_head(ENV, [b, a]))
        self.assertNotEqual(A.suppression_set_head(ENV, [a]), A.suppression_set_head("DEV", [a]))
        for bad in ([a, a], [("x", "short")], [("bad ref", SEL)]):
            with self.assertRaises(A.PrivacyAnchorError):
                A.suppression_set_head(ENV, bad)

    def test_anchor_chain_genesis_and_extension_verify(self):
        docs, chain = self.anchors([], [entry(1)], [entry(2), entry(3)])
        self.assertEqual((chain.version, chain.count), (3, 3))
        self.assertEqual(chain.set_head, A.suppression_set_head(ENV, [entry(1), entry(2), entry(3)]))
        self.assertIsNone(docs[0]["previousAnchorDigest"])
        self.assertEqual(docs[2]["previousAnchorDigest"], A.anchor_digest(docs[1]))

    def test_the_signer_side_rule_never_produces_a_regression(self):
        _docs, chain = self.anchors([entry(1)])
        for bad in ([entry(1)], []):
            with self.assertRaises(A.PrivacyAnchorError):
                A.unsigned_anchor_advance(chain, bad, environment=ENV, updated_at=stamp(9), key_id=KPAN_ID)

    def test_tampered_or_non_extending_chains_are_refused(self):
        docs, _ = self.anchors([entry(1)], [entry(2)])
        cases = {}
        t = copy.deepcopy(docs); t[1]["appended"] = [list(entry(3))]; cases["tampered"] = t
        t = copy.deepcopy(docs); t[1] = self.w.sign({k: v for k, v in {**t[1], "appended": [list(entry(1))],
                                                     "setHead": t[0]["setHead"], "suppressionCount": 1}.items()
                                                     if k != "signature"}); cases["re-append"] = t
        t = copy.deepcopy(docs); t[1] = self.w.sign({k: v for k, v in {**t[1], "anchorVersion": 3}.items()
                                                     if k != "signature"}); cases["gap"] = t
        t = copy.deepcopy(docs); t[1] = self.w.sign({k: v for k, v in {**t[1], "previousAnchorDigest": SEL}.items()
                                                     if k != "signature"}); cases["link"] = t
        t = copy.deepcopy(docs); t[1] = self.w.sign({k: v for k, v in {**t[1], "updatedAt": "2026-10-24T00:00:00Z"}
                                                     .items() if k != "signature"}); cases["time"] = t
        for name, bad in cases.items():
            with self.subTest(name), self.assertRaises(A.PrivacyAnchorError):
                self.chain(bad)

    def test_key_families_and_domains_cannot_cross(self):
        docs, chain = self.anchors([entry(1)])
        # K-PCK signing an anchor body (with a kpan id) does not verify under K-PAN
        forged = {**{k: v for k, v in docs[0].items() if k != "signature"}}
        forged["signature"] = self.o.key.sign(A.signing_bytes("anchor", forged)).hex()
        with self.assertRaises(A.PrivacyAnchorError) as c:
            self.chain([forged])
        self.assertEqual(c.exception.code, "SIGNATURE_INVALID")
        # a kpck key id is refused for an anchor, a kpan id for a checkpoint
        with self.assertRaises(A.PrivacyAnchorError):
            A.unsigned_anchor_advance(None, [], environment=ENV, updated_at=stamp(1), key_id=KPCK_ID)
        with self.assertRaises(A.PrivacyAnchorError):
            A.unsigned_checkpoint(None, chain, environment=ENV, checkpointed_at=stamp(1), key_id=KPAN_ID)
        # a K-PAN signature over a checkpoint body does not verify as a checkpoint
        body = A.unsigned_checkpoint(None, chain, environment=ENV, checkpointed_at=stamp(1), key_id=KPCK_ID)
        cp = {**body, "signature": self.w.key.sign(A.signing_bytes("checkpoint", body)).hex()}
        with self.assertRaises(A.PrivacyAnchorError):
            A.verify_checkpoint(cp, self.kpck, environment=ENV, key_id=KPCK_ID)
        # the same body signed under the anchor domain does not verify either
        cp = {**body, "signature": self.o.key.sign(A.ANCHOR_DOMAIN + A.signing_bytes("checkpoint", body)[
            len(A.CHECKPOINT_DOMAIN):]).hex()}
        with self.assertRaises(A.PrivacyAnchorError):
            A.verify_checkpoint(cp, self.kpck, environment=ENV, key_id=KPCK_ID)

    def test_checkpoint_holder_is_extension_only_with_a_fork_alarm(self):
        _docs, chain1 = self.anchors([entry(1)])
        first = self.o.checkpoint(chain1)
        with self.assertRaises(A.PrivacyAnchorError) as c:           # same anchor version again
            A.unsigned_checkpoint(first, chain1, environment=ENV, checkpointed_at=stamp(5), key_id=KPCK_ID)
        self.assertEqual(c.exception.code, "CHECKPOINT_FORK_ALARM")
        _docs, chain2 = self.anchors([entry(1)], [entry(2)])
        second = self.o.checkpoint(chain2)
        self.assertEqual(A.verify_checkpoint_chain([first, second], self.kpck, environment=ENV, key_id=KPCK_ID),
                         second)
        with self.assertRaises(A.PrivacyAnchorError):
            A.verify_checkpoint_chain([second], self.kpck, environment=ENV, key_id=KPCK_ID)

    def boot(self, docs, chain, checkpoint=None, nonce="1" * 64, boot="boot-a", **override):
        challenge = A.make_challenge(chain, environment=ENV, boot_id=boot, nonce=nonce, issued_at=stamp(20))
        unlock = self.o.unlock(challenge)
        return A.classify_boot_freshness(override.get("challenge", challenge), override.get("unlock", unlock),
                                         checkpoint or self.o.latest, override.get("host", chain), self.kpck,
                                         environment=ENV, checkpoint_key_id=KPCK_ID,
                                         boot_id=override.get("boot_id", boot), nonce=override.get("nonce_", nonce))

    def test_boot_freshness_statuses(self):
        docs, chain = self.anchors([entry(1)], [entry(2)])
        self.o.checkpoint(chain)
        self.assertEqual(self.boot(docs, chain).status, A.FRESH)
        # whole-host rollback: host chain at v1, owner checkpoint at v2
        rolled = self.chain(docs[:1])
        self.assertEqual(self.boot(docs[:1], rolled).status, A.OLDER_THAN_CHECKPOINT)
        # fork: a different v2 on the host
        fork = docs[:1] + [self.w.sign(A.unsigned_anchor_advance(rolled, [entry(9)], environment=ENV,
                                                                 updated_at=stamp(3), key_id=KPAN_ID))]
        self.assertEqual(self.boot(fork, self.chain(fork)).status, A.DIVERGED)
        # replay: an unlock answered for another boot / nonce
        self.assertEqual(self.boot(docs, chain, boot_id="boot-b").status, A.REPLAYED)
        self.assertEqual(self.boot(docs, chain, nonce_="2" * 64).status, A.REPLAYED)
        # tampered unlock signature
        challenge = A.make_challenge(chain, environment=ENV, boot_id="boot-a", nonce="1" * 64, issued_at=stamp(20))
        bad = {**self.o.unlock(challenge), "checkpointSeq": 9}
        self.assertEqual(self.boot(docs, chain, unlock=bad).status, A.UNVERIFIABLE)
        # a challenge that is not the host chain
        other = A.make_challenge(rolled, environment=ENV, boot_id="boot-a", nonce="1" * 64, issued_at=stamp(20))
        result = A.classify_boot_freshness(other, self.o.unlock(other), self.o.latest, chain, self.kpck,
                                           environment=ENV, checkpoint_key_id=KPCK_ID, boot_id="boot-a",
                                           nonce="1" * 64)
        self.assertEqual(result.status, A.DIVERGED)

    def test_host_ahead_of_the_checkpoint_is_fresh_but_marked_pending(self):
        docs, chain1 = self.anchors([entry(1)])
        self.o.checkpoint(chain1)
        docs, chain2 = self.anchors([entry(1)], [entry(2)])
        result = self.boot(docs, chain2)
        self.assertEqual((result.status, result.checkpoint_anchor_version), (A.FRESH, 1))


# ======================================================================================================= runtime ===

class FreshnessCase(GatedPathMixin, RestoreCase):
    def setUp(self) -> None:
        super().setUp()
        self.h = FreshnessHarness(self.root, self.privacy_db)
        self.pre_forget_privacy = self.root / "privacy.pre-forget.copy.db"
        shutil.copyfile(self.privacy_db, self.pre_forget_privacy)

    def gated(self, store=None):
        return memory_v2.restore_gated_hold_resolver(store or self.privacy, self.db, freshness=self.h.gate())

    def assert_fresh_refusal(self, code, identity=CODENAME):
        with self.assertRaises(F.PrivacyFreshnessNotReady) as caught:
            self.read(identity)
        self.assertEqual(caught.exception.code, code)

    def barrier_runner(self):
        return R.FirstInteractionForgetRunner(self.privacy, self.owners(), deployment_environment="DEV_SYNTHETIC",
                                              durability_barrier=F.DurabilityBarrier(self.h.gate()))

    def forget_durably(self):
        """The Track B order: begin_forget → barrier refuses (nothing erased) → anchor + checkpoint → resume."""
        result = self.forget(self.barrier_runner())
        self.assert_incomplete(result, "DURABILITY_BARRIER:" + F.ANCHOR_BEHIND)
        self.assertTrue(self.fi_present())
        self.h.anchor_and_checkpoint()
        result = self.barrier_runner().resume()
        self.assertEqual(result.status, R.COMPLETE, result)
        return result


class GateTests(FreshnessCase):
    def test_no_marker_refuses_all_memory_serving(self):
        self.assert_fresh_refusal(F.MARKER_UNAVAILABLE)
        self.assert_fresh_refusal(F.MARKER_UNAVAILABLE, FI)

    def test_genesis_and_unlock_serve_and_reboot_refuses_until_the_next_unlock(self):
        self.h.genesis()
        self.assertIn("SYNTH-ALPHA", self.read(CODENAME)["normalized_value_json"])
        self.assertIn(FAREWELL.decode(), self.read(FI)["normalized_value_json"])
        self.h.boot_id = "boot-next"                                   # marker left behind: still refused
        self.assert_fresh_refusal(F.STALE_BOOT)
        self.h.reboot()
        self.assert_fresh_refusal(F.MARKER_UNAVAILABLE)
        self.h.unlock()
        self.assertIn("SYNTH-ALPHA", self.read(CODENAME)["normalized_value_json"])

    def test_a_pending_intent_refuses_reads(self):
        self.h.genesis()
        self.h.intent_dir.mkdir()
        (self.h.intent_dir / "first-interaction.intent").write_text("{}")
        self.assert_fresh_refusal(F.INTENT_PENDING)

    def test_an_untrusted_or_malformed_marker_is_refused(self):
        self.h.genesis()
        if os.name == "posix":
            os.chmod(self.h.marker, 0o666)
            self.assert_fresh_refusal(F.MARKER_UNTRUSTED)
            os.chmod(self.h.marker, 0o644)
        doc = json.loads(self.h.marker.read_text())
        self.h.marker.write_text(json.dumps({**doc, "extra": 1}))
        self.assert_fresh_refusal(F.MARKER_INVALID)
        self.h.marker.write_text("not json")
        self.assert_fresh_refusal(F.MARKER_INVALID)

    def test_every_hold_answer_requires_freshness_not_only_require_ready(self):
        resolver = self.gated()
        with self.assertRaises(F.PrivacyFreshnessNotReady):
            resolver.is_held(*FI)                                       # direct callers (learning, canonical store)
        self.h.genesis()
        self.assertFalse(resolver.is_held(*CODENAME))
        self.h.reboot()
        with self.assertRaises(F.PrivacyFreshnessNotReady):
            resolver.is_held(*CODENAME)

    def test_resolver_construction_requires_a_real_freshness_gate(self):
        with self.assertRaises(TypeError):
            memory_v2.restore_gated_hold_resolver(self.privacy, self.db)
        with self.assertRaises(TypeError):
            memory_v2.restore_gated_hold_resolver(self.privacy, self.db, freshness=object())
        with self.assertRaises(TypeError):
            F.DurabilityBarrier(object())
        with self.assertRaises(R.ForgetRunnerError):
            R.FirstInteractionForgetRunner(self.privacy, self.owners(), deployment_environment="DEV_SYNTHETIC",
                                           durability_barrier="not callable")


class DurableForgetTests(FreshnessCase):
    def test_owners_erase_only_after_the_new_suppression_is_anchored_and_checkpointed(self):
        self.h.genesis()
        result = self.forget(self.barrier_runner())
        self.assert_incomplete(result, "DURABILITY_BARRIER:" + F.ANCHOR_BEHIND)
        self.assertEqual(result.completed_owners, ())
        self.assertTrue(self.fi_present())                             # nothing erased before durability
        self.assert_fresh_refusal(F.ANCHOR_BEHIND)                      # L ⊋ S: all memory refused meanwhile
        self.h.witness.advance_to(self.h.keys, self.privacy_db)        # anchored, checkpoint still pending
        self.assert_incomplete(self.barrier_runner().resume(), "DURABILITY_BARRIER:" + F.ANCHOR_BEHIND)
        checkpoint = self.h.owner.checkpoint(self.h.witness.chain(self.h.keys))
        F.apply_checkpoint(self.h.keys, self.h.witness.docs, self.privacy_db, checkpoint, boot_id=self.h.boot_id,
                           verified_at=self.h.now(), marker_path=self.h.marker, require_root_marker=False)
        result = self.barrier_runner().resume()
        self.assertEqual(result.status, R.COMPLETE, result)
        self.assert_fi_suppressed()
        self.assertIsNone(self.read(FI))
        self.assertIn("SYNTH-ALPHA", self.read(CODENAME)["normalized_value_json"])

    def test_without_this_boot_marker_the_forget_never_erases(self):
        self.h.genesis()
        self.h.reboot()
        self.assert_incomplete(self.forget(self.barrier_runner()), "DURABILITY_BARRIER:" + F.MARKER_UNAVAILABLE)
        self.assertTrue(self.fi_present())

    def test_a_raising_barrier_is_a_refusal(self):
        self.h.genesis()
        def boom():
            raise OSError("TEST_ONLY")
        runner = R.FirstInteractionForgetRunner(self.privacy, self.owners(), deployment_environment="DEV_SYNTHETIC",
                                                durability_barrier=boom)
        self.assert_incomplete(self.forget(runner), "DURABILITY_BARRIER:OSError")
        self.assertTrue(self.fi_present())

    def test_apply_checkpoint_refuses_non_extensions_and_other_boots(self):
        self.h.genesis()
        before = self.h.marker.read_bytes()
        stale = self.h.owner.latest
        with self.assertRaises(F.FreshnessStepRefused) as c:           # the checkpoint already applied
            F.apply_checkpoint(self.h.keys, self.h.witness.docs, self.privacy_db, stale, boot_id=self.h.boot_id,
                               verified_at=self.h.now(), marker_path=self.h.marker, require_root_marker=False)
        self.assertEqual(c.exception.code, "CHECKPOINT_NOT_AN_EXTENSION")
        with self.assertRaises(F.FreshnessStepRefused) as c:
            F.apply_checkpoint(self.h.keys, self.h.witness.docs, self.privacy_db, stale, boot_id="boot-other",
                               verified_at=self.h.now(), marker_path=self.h.marker, require_root_marker=False)
        self.assertEqual(c.exception.code, F.STALE_BOOT)
        self.assertEqual(self.h.marker.read_bytes(), before)


class RollbackTests(FreshnessCase):
    def test_privacy_only_restore_after_a_forget_is_refused_where_the_f9c_gate_alone_serves(self):
        self.h.genesis()
        self.forget_durably()
        self.assertIsNone(self.read(FI))
        # restore BOTH the Privacy store and the cognitive store to their pre-FORGET copies (same boot)
        shutil.copyfile(self.pre_forget_privacy, self.privacy_db)
        self.restore()
        self.assertTrue(self.fi_present())
        # negative control: the F9-C restore gate alone sees no suppression and would serve the forgotten content
        legacy = self.gated()._inner._gate.check()
        self.assertTrue(legacy.ready_to_serve, legacy)
        self.assertFalse(self.privacy.suppression_matches(FI))         # the restored Privacy forgot the FORGET
        # Track B: L ⊊ S → refused for every identity
        self.assert_fresh_refusal(F.OLDER_THAN_ANCHOR, FI)
        self.assert_fresh_refusal(F.OLDER_THAN_ANCHOR, CODENAME)

    def test_whole_host_rollback_is_refused_at_boot(self):
        self.h.genesis()
        witness_before = list(self.h.witness.docs)
        self.forget_durably()
        # the host (Privacy, cognitive store, witness state) rolls back to before the FORGET and reboots;
        # the owner device keeps its newer checkpoint
        shutil.copyfile(self.pre_forget_privacy, self.privacy_db)
        self.restore()
        self.h.witness.docs = witness_before
        self.h.reboot()
        challenge, nonce = self.h.challenge()                          # the rolled-back host can still ask ...
        unlock = self.h.owner.unlock(challenge)
        with self.assertRaises(F.FreshnessStepRefused) as c:           # ... but never gets a marker
            F.apply_unlock(self.h.keys, self.h.witness.docs, self.privacy_db, challenge, unlock,
                           self.h.owner.latest, boot_id=self.h.boot_id, nonce=nonce, verified_at=self.h.now(),
                           marker_path=self.h.marker)
        self.assertTrue(c.exception.code.startswith(A.OLDER_THAN_CHECKPOINT), c.exception.code)
        self.assertFalse(self.h.marker.exists())
        self.assert_fresh_refusal(F.MARKER_UNAVAILABLE, FI)

    def test_a_replayed_unlock_from_an_earlier_boot_is_refused(self):
        self.h.genesis()
        old_challenge, old_nonce = self.h.challenge()
        old_unlock = self.h.owner.unlock(old_challenge)
        self.h.reboot()
        with self.assertRaises(F.FreshnessStepRefused) as c:
            F.apply_unlock(self.h.keys, self.h.witness.docs, self.privacy_db, old_challenge, old_unlock,
                           self.h.owner.latest, boot_id=self.h.boot_id, nonce=old_nonce, verified_at=self.h.now(),
                           marker_path=self.h.marker)
        self.assertTrue(c.exception.code.startswith(A.REPLAYED), c.exception.code)
        self.assertFalse(self.h.marker.exists())

    def test_witness_rolled_back_alone_is_refused(self):
        self.h.genesis()
        witness_before = list(self.h.witness.docs)
        self.forget_durably()
        self.h.witness.docs = witness_before                           # only the witness state rolled back
        self.h.reboot()
        with self.assertRaises(F.FreshnessStepRefused) as c:
            self.h.unlock()
        self.assertEqual(c.exception.code, F.ANCHOR_BEHIND)            # L ⊋ S at the challenge: no marker
        self.assert_fresh_refusal(F.MARKER_UNAVAILABLE)

    def test_a_forged_privacy_row_is_divergence(self):
        self.h.genesis()
        conn = __import__("sqlite3").connect(self.privacy_db)
        try:
            row = conn.execute("SELECT * FROM privacy_restore_suppression_manifest").fetchone()
        finally:
            conn.close()
        self.assertIsNone(row)                                         # fresh store: empty manifest at genesis
        self.forget_durably()
        conn = __import__("sqlite3").connect(self.privacy_db)
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(privacy_restore_suppression_manifest)")]
            row = list(conn.execute("SELECT * FROM privacy_restore_suppression_manifest").fetchone())
            conn.execute("DROP TRIGGER IF EXISTS privacy_restore_suppression_no_delete")
            conn.execute("DELETE FROM privacy_restore_suppression_manifest")
            row[cols.index("identity_selector")] = SEL
            conn.execute(f"INSERT INTO privacy_restore_suppression_manifest VALUES ({','.join('?' * len(row))})",
                         row)
            conn.commit()
        finally:
            conn.close()
        self.assert_fresh_refusal(F.DIVERGED)


if __name__ == "__main__":
    unittest.main()
