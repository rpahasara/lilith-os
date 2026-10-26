"""Track B: Privacy activation, end to end over the REAL components (synthetic data, per-test keys, no host).

* the recovery witness's K-PAN anchor service (``lilith_recovery_witness.privacy_anchor``), reached through exactly the
  owner-socket path of ``server.py`` (``encode_response(dispatch(parse_frame(frame)))``) over its own file store;
* the owner device's K-PCK tool (``privacy_checkpoint_tool``: keygen / checkpoint / unlock, temporary custody);
* the root host steps (``privacy_freshness_host``) driving the real ``issue_challenge`` / ``apply_unlock`` /
  ``apply_checkpoint`` and the marker;
* the real Privacy store, L04 / L18 V2 owners, the gated canonical read path and the FORGET runner with the governed
  ``DurabilityBarrier``.

Keys are generated in temporary directories with TEST-ONLY key ids and never leave them. Nothing contacts a host.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from test_canonical_runtime import TEST_CLASS  # noqa: F401  (puts the Core API on sys.path)
from test_privacy_forget_runner import FAREWELL, FI
from test_privacy_restore_gate import GatedPathMixin
from test_privacy_restore_suppression import CODENAME, RestoreCase

from lilith_memory import memory_v2
from lilith_memory import privacy_anchor_contracts as A
from lilith_memory import privacy_forget_runner as R
from lilith_memory import privacy_freshness as F
from lilith_memory import privacy_freshness_host as H

SERVICES = Path(__file__).resolve().parents[2]
for _path in (SERVICES / "recovery-witness", SERVICES / "authority-dev", SERVICES / "owner-memory-control",
              SERVICES / "owner-memory-control/tools"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from lilith_recovery_witness import credential as CRED  # noqa: E402
from lilith_recovery_witness import privacy_anchor as PAN  # noqa: E402
import privacy_checkpoint_tool as OWNER  # noqa: E402  (the owner device's K-PCK tool, off-host)

ENV = "DEV_SYNTHETIC"
KPAN_ID = "kpan.test-only.dev-synthetic.01"
KPCK_ID = "kpck.test-only.dev-synthetic.01"


class Clock:
    def __init__(self, minute: int):
        self.minute, self.n = minute, 0

    def __call__(self) -> str:
        self.n += 1
        return f"2026-10-26T{self.minute:02d}:{self.n // 60:02d}:{self.n % 60:02d}.000000Z"


@unittest.skipUnless(os.name == "posix", "the witness anchor store uses directory descriptors and flock")
class PrivacyActivationIntegration(GatedPathMixin, RestoreCase):
    def setUp(self) -> None:
        super().setUp()
        self.anchor_dir = self.root / "var-lib-lilith-privacy-anchor"
        self.anchor_dir.mkdir(mode=0o700)
        self.witness_key = CRED.PrivacyAnchorSigningKeyV1(Ed25519PrivateKey.generate(), anchor_key_id=KPAN_ID)
        self.witness_clock = Clock(10)
        self.owner_clock = Clock(30)
        self.custody = self.root / "owner-device-kpck"
        OWNER.keygen(self.custody, environment=ENV, key_id=KPCK_ID)
        self.kpan_pin = self.root / "etc-lilith-privacy-fresh" / "kpan.pin.json"
        self.kpan_pin.parent.mkdir()
        self.kpan_pin.write_text(json.dumps(OWNER.public_pin(self.witness_key.verifying_key(), environment=ENV,
                                                             key_id=KPAN_ID, family="K-PAN")), encoding="ascii")
        self.kpck_pin = self.kpan_pin.parent / "kpck.pin.json"
        shutil.copyfile(self.custody / OWNER.PIN_FILE, self.kpck_pin)
        self.keys = H.load_keys(self.kpan_pin, self.kpck_pin, environment=ENV)
        self.client = H.WitnessAnchorClient(self.witness_transport, self.keys)
        self.run_dir = self.root / "run-lilith-privacy-fresh"
        self.marker = self.run_dir / "verified"
        self.state = self.run_dir / "challenge.json"
        self.boot_id = "boot-1"

    # ---- the three parties -------------------------------------------------------------------------------------
    def witness_transport(self, frame: bytes) -> bytes:
        """server.py's owner-socket path for an anchor frame, over the real store and the real K-PAN signer."""
        service = PAN.PrivacyAnchorServiceV1(store=PAN.AnchorStoreV1(self.anchor_dir), signing_key=self.witness_key,
                                             clock=self.witness_clock)
        self.assertTrue(PAN.is_anchor_frame(frame))
        return PAN.encode_response(service.dispatch(PAN.parse_frame(frame)))

    def owner_files(self, name: str, doc) -> Path:
        path = self.root / "owner-transfer" / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(doc), encoding="ascii")
        return path

    def owner_checkpoint(self):
        chain = self.owner_files("anchor-chain.json", self.client.chain_documents())
        return OWNER.checkpoint(self.custody, anchor_chain=chain, anchor_pin=self.kpan_pin, at=self.owner_clock())

    def owner_unlock(self, challenge):
        chain = self.owner_files("anchor-chain.json", self.client.chain_documents())
        return OWNER.unlock(self.custody, challenge=self.owner_files("challenge.json", challenge),
                            anchor_chain=chain, anchor_pin=self.kpan_pin, at=self.owner_clock())

    # ---- the host --------------------------------------------------------------------------------------------
    def gate(self) -> F.PrivacyFreshnessGate:
        return F.PrivacyFreshnessGate(self.privacy_db, environment=ENV, marker_path=self.marker,
                                      intent_dir=self.root / "intent", boot_id=lambda: self.boot_id,
                                      require_root_marker=False)

    def gated(self, store=None):
        return memory_v2.restore_gated_hold_resolver(store or self.privacy, self.db, freshness=self.gate())

    def runner(self, owners=None, store=None):
        return R.FirstInteractionForgetRunner(store or self.privacy, owners or self.owners(store),
                                              deployment_environment="DEV_SYNTHETIC",
                                              durability_barrier=F.DurabilityBarrier(self.gate()))

    def challenge(self):
        return H.challenge(self.client, self.keys, self.privacy_db, boot_id=self.boot_id, state_path=self.state)

    def unlock(self, unlock_doc, checkpoint_doc):
        return H.unlock(self.client, self.keys, self.privacy_db, unlock_doc, checkpoint_doc, boot_id=self.boot_id,
                        state_path=self.state, marker_path=self.marker)

    def boot_unlock(self, checkpoint_doc):
        return self.unlock(self.owner_unlock(self.challenge()), checkpoint_doc)

    def apply_checkpoint(self, checkpoint_doc):
        return H.checkpoint(self.client, self.keys, self.privacy_db, checkpoint_doc, boot_id=self.boot_id,
                            marker_path=self.marker, require_root_marker=False)

    def reboot(self, boot_id: str) -> None:
        self.boot_id = boot_id
        shutil.rmtree(self.run_dir, ignore_errors=True)                  # tmpfs: marker and challenge are gone

    def refused(self, code_prefix, call, *args, **kwargs):
        with self.assertRaises((H.HostStepRefused, OWNER.ToolRefusal)) as caught:
            call(*args, **kwargs)
        self.assertTrue(caught.exception.code.startswith(code_prefix), caught.exception.code)

    def assert_locked(self, code):
        """Every canonical read refuses with the freshness code: an explicit refusal, never a miss or a stale row."""
        for identity in (CODENAME, FI):
            with self.subTest(identity=identity), self.assertRaises(F.PrivacyFreshnessNotReady) as caught:
                self.read(identity)
            self.assertEqual(caught.exception.code, code)

    def snapshot(self, name: str) -> Path:
        """A whole-host image: Privacy, cognitive memory and the witness anchor store (the K-PCK chain is off-host)."""
        image = self.root / ("image-" + name)
        image.mkdir()
        shutil.copyfile(self.privacy_db, image / "privacy.db")
        shutil.copyfile(self.db, image / "cognitive.db")
        shutil.copytree(self.anchor_dir, image / "anchor")
        return image

    def restore(self, image: Path) -> None:
        shutil.copyfile(image / "privacy.db", self.privacy_db)
        shutil.copyfile(image / "cognitive.db", self.db)
        shutil.rmtree(self.anchor_dir)
        shutil.copytree(image / "anchor", self.anchor_dir)

    # ---- the proof -------------------------------------------------------------------------------------------
    def test_privacy_activation_end_to_end(self):
        # 1. Untrusted until activation: no marker, no anchor; every read refuses explicitly (never a miss).
        self.assert_locked(F.MARKER_UNAVAILABLE)
        self.refused("ANCHOR_NOT_PROVISIONED", self.challenge)
        self.assertEqual(H.plan(self.client, self.keys, self.privacy_db).kind, "GENESIS")

        # 2. Genesis (witness K-PAN, explicit owner set-head pin) and the owner's independent off-host checkpoint.
        step = H.plan(self.client, self.keys, self.privacy_db)
        self.refused("EXPECTED_SET_HEAD_MISMATCH", H.genesis, self.client, self.keys, self.privacy_db,
                     expected_set_head="0" * 64)
        self.assertEqual(self.client.chain_documents(), [])                # nothing was signed
        done = H.genesis(self.client, self.keys, self.privacy_db, expected_set_head=step.expected_set_head)
        self.assertEqual((done["result"], done["anchorVersion"]), ("GENESIS_COMMITTED", 1))
        self.refused("GENESIS_NOT_APPLICABLE", H.genesis, self.client, self.keys, self.privacy_db,
                     expected_set_head=step.expected_set_head)
        checkpoint_1 = self.owner_checkpoint()
        self.assertEqual((checkpoint_1["checkpointSeq"], checkpoint_1["anchorVersion"]), (1, 1))
        self.assert_locked(F.MARKER_UNAVAILABLE)                          # anchored + checkpointed != unlocked

        # 3. A boot-specific owner unlock makes matching canonical memory eligible.
        marker = self.boot_unlock(checkpoint_1)
        self.assertEqual((marker["bootId"], marker["anchorVersion"], marker["checkpointSeq"]), ("boot-1", 1, 1))
        self.assertFalse(self.state.exists())                              # the challenge is single-use
        self.assertIn("SYNTH-ALPHA", self.read(CODENAME)["normalized_value_json"])
        self.assertIn(FAREWELL.decode(), self.read(FI)["normalized_value_json"])
        before_forget = self.snapshot("before-forget")

        # 5a. A replayed unlock (same boot, challenge already consumed) and a divergent unlock are refused.
        replay = self.owner_unlock(self.challenge())
        self.challenge()                                                   # a newer challenge supersedes it
        self.refused("REPLAYED", self.unlock, replay, checkpoint_1)
        self.refused("NO_CHALLENGE_FOR_THIS_BOOT", H.unlock, self.client, self.keys, self.privacy_db, replay,
                     checkpoint_1, boot_id="boot-other", state_path=self.state, marker_path=self.marker)

        # 6. A pending FORGET cannot erase before its suppression is anchored AND owner-checkpointed.
        result = self.forget()
        self.assert_incomplete(result, "DURABILITY_BARRIER:" + F.ANCHOR_BEHIND)
        self.assertTrue(self.fi_present())                                  # nothing erased
        self.assert_locked(F.ANCHOR_BEHIND)                                 # L ⊋ S: all memory refused meanwhile
        step = H.plan(self.client, self.keys, self.privacy_db)
        self.assertEqual((step.kind, len(step.entries)), ("ADVANCE", 1))
        H.advance(self.client, self.keys, self.privacy_db, expected_set_head=step.expected_set_head)
        self.assert_incomplete(self.runner().resume(), "DURABILITY_BARRIER:" + F.ANCHOR_BEHIND)
        self.assertTrue(self.fi_present())                                  # anchored, not yet checkpointed
        self.refused("CHECKPOINT_NOT_AN_EXTENSION", self.apply_checkpoint, checkpoint_1)

        # 7. The owner's correct new checkpoint restores eligibility without resurrecting the forgotten memory.
        checkpoint_2 = self.owner_checkpoint()
        self.assertEqual((checkpoint_2["checkpointSeq"], checkpoint_2["anchorVersion"]), (2, 2))
        self.apply_checkpoint(checkpoint_2)
        result = self.runner().resume()
        self.assertEqual(result.status, R.COMPLETE, result)
        self.assert_fi_suppressed()
        self.assertIsNone(self.read(FI))
        self.assertIn("SYNTH-ALPHA", self.read(CODENAME)["normalized_value_json"])

        # 4. A whole-host rollback to the pre-FORGET image (Privacy, memory AND witness anchor) is refused at boot:
        #    the host is internally consistent, but the owner's off-host checkpoint is ahead of it.
        self.restore(before_forget)
        self.reboot("boot-2")
        self.assert_locked(F.MARKER_UNAVAILABLE)
        rolled_back_challenge = self.challenge()
        self.assertEqual(rolled_back_challenge["anchorVersion"], 1)
        self.refused("UNLOCK_REFUSED:" + A.OLDER_THAN_CHECKPOINT, self.owner_unlock, rolled_back_challenge)
        self.refused("REPLAYED", self.unlock, replay, checkpoint_1)         # an earlier boot's unlock is refused
        self.refused("UNVERIFIABLE", self.unlock, {**replay, "signature": "0" * 128}, checkpoint_1)
        self.assert_locked(F.MARKER_UNAVAILABLE)                           # the forgotten memory is never served
        alarms = (self.custody / OWNER.ALARM_FILE).read_text(encoding="ascii")
        self.assertIn("UNLOCK_REFUSED:" + A.OLDER_THAN_CHECKPOINT, alarms)

    def test_a_divergent_host_state_is_refused_before_any_signature(self):
        step = H.plan(self.client, self.keys, self.privacy_db)
        H.genesis(self.client, self.keys, self.privacy_db, expected_set_head=step.expected_set_head)
        self.boot_unlock(self.owner_checkpoint())
        conn = sqlite3.connect(self.privacy_db)                            # a row Privacy never wrote
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(privacy_restore_suppression_manifest)")]
            values = {"suppression_ref_id": "suppress.forged", "authority": "PRIVACY_GOVERNANCE_AUTHORITY_V1",
                      "identity_selector": "f" * 64, "state": "ACTIVE", "created_at": "2026-10-26T00:00:00Z",
                      "completed_at": None}
            row = [values[col] for col in cols]
            conn.execute(f"INSERT INTO privacy_restore_suppression_manifest VALUES ({','.join('?' * len(row))})", row)
            conn.commit()
        finally:
            conn.close()
        self.assert_locked(F.ANCHOR_BEHIND)                                 # a forged row is never served past
        self.reboot("boot-2")
        self.refused(F.ANCHOR_BEHIND, self.challenge)                        # and no challenge is ever issued

    def test_a_privacy_only_restore_behind_the_anchor_is_refused_by_every_step(self):
        step = H.plan(self.client, self.keys, self.privacy_db)
        H.genesis(self.client, self.keys, self.privacy_db, expected_set_head=step.expected_set_head)
        self.boot_unlock(self.owner_checkpoint())
        shutil.copyfile(self.privacy_db, self.root / "privacy.at-genesis.db")
        self.assert_incomplete(self.forget(), "DURABILITY_BARRIER:" + F.ANCHOR_BEHIND)
        step = H.plan(self.client, self.keys, self.privacy_db)
        H.advance(self.client, self.keys, self.privacy_db, expected_set_head=step.expected_set_head)
        self.apply_checkpoint(self.owner_checkpoint())
        self.assertEqual(self.runner().resume().status, R.COMPLETE)
        shutil.copyfile(self.root / "privacy.at-genesis.db", self.privacy_db)   # Privacy alone rolled back
        self.refused(F.OLDER_THAN_ANCHOR, H.plan, self.client, self.keys, self.privacy_db)
        self.assert_locked(F.OLDER_THAN_ANCHOR)
        self.reboot("boot-2")
        self.refused(F.OLDER_THAN_ANCHOR, self.challenge)

    def test_the_witness_frame_codec_is_byte_compatible(self):
        payload = {"fromVersion": 1}
        self.assertEqual(H.encode_request(H.READ, payload), PAN.encode_frame(PAN.READ_PRIVACY_ANCHOR, payload))
        response = PAN.encode_response({"status": "UNINITIALIZED", "anchorVersion": 0})
        self.assertEqual(H.decode_response(response), {"status": "UNINITIALIZED", "anchorVersion": 0})
        self.assertEqual((H.ANCHOR_PROTOCOL, H.MAX_FRAME_BYTES, H.MAX_ENTRIES_PER_ADVANCE),
                         (PAN.PROTOCOL, PAN.MAX_FRAME_BYTES, PAN.MAX_ENTRIES_PER_ADVANCE))

    def test_pins_must_be_the_owner_tool_format_and_family(self):
        self.refused("K-PAN_PIN_INVALID", H.load_keys, self.kpck_pin, self.kpck_pin, environment=ENV)
        self.refused("K-PAN_PIN_INVALID", H.load_keys, self.kpan_pin, self.kpck_pin, environment="DEV")
        self.refused("K-PAN_PIN_UNAVAILABLE", H.load_keys, self.root / "missing.json", self.kpck_pin, environment=ENV)



if __name__ == "__main__":
    unittest.main()
