"""Track B B2: the witness-held Privacy rollback anchor (K-PAN). Repository tests only; temporary directories,
per-test keys; nothing is installed and nothing contacts DEV or PROD.

Covers the Rev 1 compatibility checks that can run locally: the new protocol id is refused on the signer socket and by
the unchanged ``protocol.py`` (3), K-PAN and K-WIT cannot sign each other's documents (4), and the anchor state never
enters the RecoveryWitnessV2 store, whose pinned recovery scan fails closed on any extra entry. Checks 1/2/5/6 (pins,
recorded transcripts, release markers, restart preservation) are asserted by the existing witness and authority-dev
suites, which must stay unchanged.
"""

from __future__ import annotations

import copy
import json
import os
import pickle
import secrets
import socket
import sqlite3
import tempfile
import unittest
from pathlib import Path

import witness_fixtures as X
from witness_fixtures import F, WR

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

from lilith_memory import privacy_anchor_contracts as A
from lilith_memory import privacy_freshness as FR
from lilith_recovery_witness import credential as CRED
from lilith_recovery_witness import privacy_anchor as PAN
from lilith_recovery_witness import protocol as WP
from lilith_recovery_witness import server as S
from lilith_recovery_witness import storage as ST

POSIX = os.name == "posix"
ENV = "DEV_SYNTHETIC"


def der(key: Ed25519PrivateKey) -> bytes:
    return key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())


def entry(n: int) -> list:
    return [f"suppress.{n:032x}", f"{n:064x}"]


def head(entries) -> str:
    return A.suppression_set_head(ENV, entries)


class Clock:
    def __init__(self):
        self.n = 0

    def __call__(self) -> str:
        self.n += 1
        return f"2026-10-25T12:{self.n // 60:02d}:{self.n % 60:02d}Z"


# ------------------------------------------------------------------------------------------------ credential ---

class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.raw = Ed25519PrivateKey.generate()   # TEST_ONLY key, temporary
        self.key = CRED.PrivacyAnchorSigningKeyV1(self.raw)

    def test_loads_only_its_own_credential_and_refuses_k_wit_material(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(CRED.WitnessCredentialError) as c:
                CRED.load_privacy_anchor_key(d, expected_directory=d)
            self.assertEqual(c.exception.state, CRED.CREDENTIAL_ABSENT)
            (Path(d) / CRED.PRIVACY_ANCHOR_CREDENTIAL_NAME).write_bytes(b"not a key")
            with self.assertRaises(CRED.WitnessCredentialError) as c:
                CRED.load_privacy_anchor_key(d, expected_directory=d)
            self.assertEqual(c.exception.state, CRED.CREDENTIAL_INVALID)
            (Path(d) / CRED.PRIVACY_ANCHOR_CREDENTIAL_NAME).write_bytes(der(self.raw))
            loaded = CRED.load_privacy_anchor_key(d, expected_directory=d)
            self.assertEqual(loaded.public_key(), self.key.public_key())
            witness = X.key()                                         # K-WIT
            (Path(d) / CRED.PRIVACY_ANCHOR_CREDENTIAL_NAME).write_bytes(der(F.private("witness")))
            with self.assertRaises(CRED.WitnessCredentialError) as c:
                CRED.load_privacy_anchor_key(d, expected_directory=d, witness_key=witness)
            self.assertEqual(c.exception.state, CRED.CREDENTIAL_INVALID)
        with self.assertRaises(CRED.WitnessCredentialError):
            CRED.load_privacy_anchor_key("/tmp/other")

    def test_the_key_is_closed_and_bound_to_its_family(self):
        self.assertEqual(sorted(n for n in dir(self.key) if not n.startswith("_")),
                         ["anchor_key_id", "environment", "public_key", "public_key_sha256", "sign_privacy_anchor",
                          "verifying_key"])
        for leak in (pickle.dumps, copy.copy, copy.deepcopy):
            with self.assertRaises(TypeError):
                leak(self.key)
        for bad in ("kpck.dev-synthetic.01", "test-only.witness.x", X.B.WITNESS_KEY_ID):
            with self.assertRaises(ValueError):
                CRED.PrivacyAnchorSigningKeyV1(self.raw, anchor_key_id=bad)

    def test_signs_only_strict_extensions_of_the_given_chain(self):
        genesis = A.unsigned_anchor_advance(None, [], environment=ENV, updated_at="2026-10-25T00:00:00Z",
                                            key_id=CRED.PRIVACY_ANCHOR_KEY_ID)
        g = self.key.sign_privacy_anchor([], genesis)
        chain = A.verify_anchor_chain([g], self.key.verifying_key(), environment=ENV, key_id=CRED.PRIVACY_ANCHOR_KEY_ID)
        nxt = A.unsigned_anchor_advance(chain, [entry(1)], environment=ENV, updated_at="2026-10-25T00:00:01Z",
                                        key_id=CRED.PRIVACY_ANCHOR_KEY_ID)
        self.key.sign_privacy_anchor([g], nxt)
        for previous, body in (([], nxt),                              # not the next version of an empty chain
                               ([g], genesis),                         # a second genesis
                               ([g], {**nxt, "environment": "DEV"}),
                               ([g], {**nxt, "anchorKeyId": "kpan.other.01"}),
                               ([g], {**nxt, "setHead": head([entry(9)])}),
                               ([{**g, "setHead": head([entry(2)])}], nxt)):   # a tampered stored chain
            with self.assertRaises(ValueError):
                self.key.sign_privacy_anchor(previous, body)

    def test_k_wit_and_k_pan_cannot_sign_each_others_documents(self):
        """Rev 1 compatibility check 4."""
        anchor_body = A.unsigned_anchor_advance(None, [], environment=ENV, updated_at="2026-10-25T00:00:00Z",
                                                key_id=CRED.PRIVACY_ANCHOR_KEY_ID)
        with self.assertRaises(ValueError):
            X.key().sign_recovery_witness_v2(anchor_body)
        v2_body = dict(X.Harness().candidate().unsigned)
        with self.assertRaises(ValueError):
            self.key.sign_privacy_anchor([], v2_body)
        # a K-WIT key object passed as K-PAN is refused by the service
        with self.assertRaises(TypeError):
            PAN.PrivacyAnchorServiceV1(store=PAN.AnchorStoreV1("/nonexistent"), signing_key=X.key(), clock=Clock())


# ------------------------------------------------------------------------------------------------- protocol ---

class ProtocolTests(unittest.TestCase):
    def test_closed_canonical_operations(self):
        frame = PAN.encode_frame(PAN.READ_PRIVACY_ANCHOR, {"fromVersion": 1})
        self.assertTrue(PAN.is_anchor_frame(frame))
        self.assertEqual(PAN.parse_frame(frame).operation, PAN.READ_PRIVACY_ANCHOR)
        for payload, op in (({}, PAN.READ_PRIVACY_ANCHOR), ({"fromVersion": 0}, PAN.READ_PRIVACY_ANCHOR),
                            ({"entries": [], "expectedSetHead": "x"}, PAN.GENESIS_PRIVACY_ANCHOR),
                            ({"entries": [["a"]], "expectedSetHead": "0" * 64}, PAN.GENESIS_PRIVACY_ANCHOR),
                            ({"entries": [], "expectedSetHead": "0" * 64, "extra": 1}, PAN.GENESIS_PRIVACY_ANCHOR),
                            ({"previousAnchorDigest": None, "entries": [], "expectedSetHead": "0" * 64},
                             PAN.ADVANCE_PRIVACY_ANCHOR)):
            with self.subTest(op=op, payload=payload), self.assertRaises(PAN.AnchorProtocolError):
                PAN.parse_frame(PAN.encode_frame(op, payload))
        raw = json.dumps({"protocol": PAN.PROTOCOL, "schemaVersion": 1, "operation": PAN.READ_PRIVACY_ANCHOR,
                          "payload": {"fromVersion": 1}}, indent=1).encode()
        with self.assertRaises(PAN.AnchorProtocolError):
            PAN.parse_frame(len(raw).to_bytes(4, "big") + raw)          # non-canonical JSON
        with self.assertRaises(PAN.AnchorProtocolError):
            PAN.parse_frame(PAN.encode_frame("SIGN_ANYTHING", {}))

    def test_the_unchanged_witness_protocol_refuses_anchor_frames_on_both_sockets(self):
        """Rev 1 compatibility check 3: the signer socket (and any witness without this module) refuses."""
        frame = PAN.encode_frame(PAN.ADVANCE_PRIVACY_ANCHOR, {"previousAnchorDigest": "0" * 64, "entries": [],
                                                              "expectedSetHead": "0" * 64})
        for role in (WP.OWNER, WP.SIGNER):
            with self.assertRaises(WP.ProtocolError) as c:
                WP.parse_frame(frame, role=role)
            self.assertEqual(c.exception.code, "UNSUPPORTED_VERSION")
        self.assertFalse(PAN.is_anchor_frame(WP.encode_frame(WP.READ_WITNESS, {})))


# ---------------------------------------------------------------------------------------------- the service ---

@unittest.skipUnless(POSIX, "real filesystem semantics (flock, dir-fd link) are POSIX")
class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "lilith-privacy-anchor"
        self.state.mkdir(mode=0o700)
        self.key = CRED.PrivacyAnchorSigningKeyV1(Ed25519PrivateKey.generate())
        self.clock = Clock()

    def service(self, key="default", fault=None):
        return PAN.PrivacyAnchorServiceV1(store=PAN.AnchorStoreV1(self.state, fault=fault),
                                          signing_key=self.key if key == "default" else key, clock=self.clock)

    def call(self, op, payload, service=None):
        return (service or self.service()).dispatch(PAN.parse_frame(PAN.encode_frame(op, payload)))

    def genesis(self, entries=()):
        return self.call(PAN.GENESIS_PRIVACY_ANCHOR, {"entries": [list(e) for e in entries],
                                                      "expectedSetHead": head(entries)})

    def advance(self, previous, new, full):
        return self.call(PAN.ADVANCE_PRIVACY_ANCHOR, {"previousAnchorDigest": previous, "entries": new,
                                                      "expectedSetHead": head(full)})

    def read(self, start=1):
        return self.call(PAN.READ_PRIVACY_ANCHOR, {"fromVersion": start})

    def test_genesis_advance_read_and_the_on_disk_layout(self):
        self.assertEqual(self.read()["status"], "UNINITIALIZED")
        g = self.genesis()
        self.assertEqual((g["status"], g["anchorVersion"], g["suppressionCount"]), ("COMMITTED", 1, 0))
        a = self.advance(g["anchorDigest"], [entry(1)], [entry(1)])
        self.assertEqual((a["status"], a["anchorVersion"], a["suppressionCount"]), ("COMMITTED", 2, 1))
        r = self.read()
        self.assertEqual((r["status"], r["anchorVersion"], r["anchorDigest"], len(r["documents"])),
                         ("OK", 2, a["anchorDigest"], 2))
        self.assertEqual(len(self.read(2)["documents"]), 1)
        chain = A.verify_anchor_chain(r["documents"], self.key.verifying_key(), environment=ENV,
                                      key_id=CRED.PRIVACY_ANCHOR_KEY_ID)
        self.assertEqual(chain.set_head, head([entry(1)]))
        self.assertEqual(sorted(os.listdir(self.state)), ["anchor.lock", "chain", "staging"])
        self.assertEqual(sorted(os.listdir(self.state / "chain")), ["00000001.json", "00000002.json"])
        self.assertEqual(os.listdir(self.state / "staging"), [])
        self.assertEqual(os.stat(self.state / "chain" / "00000002.json").st_mode & 0o777, 0o600)

    def test_refusals_commit_nothing(self):
        self.assertEqual(self.advance("0" * 64, [entry(1)], [entry(1)])["reason"], "ANCHOR_NOT_PROVISIONED")
        bad_pin = self.call(PAN.GENESIS_PRIVACY_ANCHOR, {"entries": [], "expectedSetHead": head([entry(1)])})
        self.assertEqual(bad_pin["reason"], "ANCHOR_PIN_MISMATCH")
        self.assertEqual(self.read()["status"], "UNINITIALIZED")
        g = self.genesis([entry(1)])
        self.assertEqual(self.genesis()["reason"], "ANCHOR_ALREADY_PROVISIONED")
        self.assertEqual(self.advance("1" * 64, [entry(2)], [entry(1), entry(2)])["reason"], "ANCHOR_HEAD_MOVED")
        self.assertEqual(self.advance(g["anchorDigest"], [entry(1)], [entry(1)])["reason"], "ANCHOR_NOT_AN_EXTENSION")
        self.assertEqual(self.advance(g["anchorDigest"], [], [entry(1)])["reason"], "ANCHOR_EMPTY_ADVANCE")
        self.assertEqual(self.advance(g["anchorDigest"], [entry(2)], [entry(3)])["reason"], "ANCHOR_PIN_MISMATCH")
        self.assertEqual(self.read()["anchorVersion"], 1)
        self.assertEqual(self.call(PAN.READ_PRIVACY_ANCHOR, {"fromVersion": 1}, self.service(key=None))["reason"],
                         "ANCHOR_KEY_ABSENT")

    def test_a_damaged_or_foreign_chain_fails_closed_and_is_never_repaired(self):
        g = self.genesis()
        self.advance(g["anchorDigest"], [entry(1)], [entry(1)])
        path = self.state / "chain" / "00000002.json"
        original = path.read_bytes()
        doc = json.loads(original)
        doc["appended"] = [entry(9)]
        path.write_text(json.dumps(doc))
        self.assertTrue(self.read()["reason"].startswith("ANCHOR_STORE_FAIL_CLOSED"))
        self.assertTrue(self.advance("0" * 64, [entry(2)], [entry(1), entry(2)])["reason"]
                        .startswith("ANCHOR_STORE_FAIL_CLOSED"))
        self.assertEqual(path.read_text(), json.dumps(doc))                # untouched
        path.write_bytes(original)
        (self.state / "chain" / "00000004.json").write_text("{}")           # a gap
        self.assertTrue(self.read()["reason"].startswith("ANCHOR_STORE_FAIL_CLOSED"))
        os.unlink(self.state / "chain" / "00000004.json")
        os.rename(self.state / "chain" / "00000002.json", self.state / "chain" / "00000003.json")
        self.assertTrue(self.read()["reason"].startswith("ANCHOR_STORE_FAIL_CLOSED"))  # valid docs, misnamed
        os.rename(self.state / "chain" / "00000003.json", self.state / "chain" / "00000002.json")
        self.assertEqual(self.read()["anchorVersion"], 2)
        other = CRED.PrivacyAnchorSigningKeyV1(Ed25519PrivateKey.generate())   # a chain under another K-PAN
        self.assertTrue(self.call(PAN.READ_PRIVACY_ANCHOR, {"fromVersion": 1}, self.service(key=other))["reason"]
                        .startswith("ANCHOR_STORE_FAIL_CLOSED"))

    def test_crash_at_every_seam_is_either_uncommitted_or_committed(self):
        for point in PAN.FAULT_POINTS:
            with self.subTest(point=point):
                for name in os.listdir(self.state):
                    target = self.state / name
                    if target.is_dir():
                        for f in os.listdir(target):
                            os.unlink(target / f)
                        os.rmdir(target)
                    else:
                        os.unlink(target)
                g = self.genesis()

                def crash(p, point=point):
                    if p == point:
                        raise OSError("TEST crash at " + p)
                result = self.call(PAN.ADVANCE_PRIVACY_ANCHOR,
                                   {"previousAnchorDigest": g["anchorDigest"], "entries": [entry(1)],
                                    "expectedSetHead": head([entry(1)])}, self.service(fault=crash))
                self.assertEqual(result["status"], "REFUSED")
                committed = point in ("AFTER_CHAIN_LINK", "AFTER_CHAIN_DIRECTORY_FSYNC")
                after = self.read()
                self.assertEqual(after["anchorVersion"], 2 if committed else 1, point)
                retry = self.advance(after["anchorDigest"], [entry(1)] if not committed else [entry(2)],
                                     [entry(1)] if not committed else [entry(1), entry(2)])
                self.assertEqual(retry["status"], "COMMITTED", (point, retry))
                self.assertEqual(os.listdir(self.state / "staging"), [])

    def test_a_held_lock_or_missing_state_directory_refuses(self):
        self.genesis()
        with PAN.AnchorStoreV1(self.state).lock():
            self.assertEqual(self.read()["reason"], "ANCHOR_STORE_LOCKED")
        missing = PAN.PrivacyAnchorServiceV1(store=PAN.AnchorStoreV1(Path(self.tmp.name) / "absent"),
                                             signing_key=self.key, clock=self.clock)
        self.assertEqual(self.call(PAN.READ_PRIVACY_ANCHOR, {"fromVersion": 1}, missing)["reason"],
                         "ANCHOR_STORE_UNAVAILABLE")

    def test_anchor_state_must_never_enter_the_recovery_witness_store(self):
        """The pinned witness_readiness scan fails closed on any extra entry: hence the separate directory."""
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o750)
            h = X.Harness(ST.FilesystemWitnessStorageV1(directory))
            h.bootstrap()
            self.assertEqual(h.scan().classification, WR.CONSISTENT)
            (Path(directory) / "anchor.lock").write_bytes(b"")
            scan = h.scan()
            self.assertEqual((scan.classification, scan.fail_closed), (WR.UNEXPECTED_ENTRY, True))


# ---------------------------------------------------------------------------------------------- the server ---

@unittest.skipUnless(POSIX and hasattr(socket, "AF_UNIX"), "AF_UNIX")
class RoutingTests(unittest.TestCase):
    class Core:
        def dispatch(self, role, message):
            return {"status": "OK", "role": role, "operation": message.operation}

    class Anchor(PAN.PrivacyAnchorServiceV1):
        def __init__(self):
            pass

        def dispatch(self, message):
            return {"status": "OK", "anchorOperation": message.operation}

    def exchange(self, frame, role, anchor, uid=0, authorized=0):
        left, right = socket.socketpair()
        left.sendall(frame)
        S.serve_connection(right, self.Core(), role=role, authorized_uid=authorized,
                           peer_uid_reader=lambda _c: uid, anchor=anchor)
        left.settimeout(2)
        try:
            reply = left.recv(WP.MAX_FRAME_BYTES + 8)
        except ConnectionResetError:
            reply = b""
        left.close()
        return reply

    def test_anchor_frames_are_served_on_the_owner_socket_only(self):
        frame = PAN.encode_frame(PAN.READ_PRIVACY_ANCHOR, {"fromVersion": 1})
        reply = self.exchange(frame, WP.OWNER, self.Anchor())
        self.assertEqual(PAN.parse_response(reply)["anchorOperation"], PAN.READ_PRIVACY_ANCHOR)
        self.assertEqual(self.exchange(frame, WP.SIGNER, self.Anchor(), uid=990, authorized=990), b"")
        self.assertEqual(self.exchange(frame, WP.OWNER, None), b"")        # no anchor service: refused as before
        self.assertEqual(self.exchange(frame, WP.OWNER, self.Anchor(), uid=1001), b"")   # wrong peer
        witness = self.exchange(WP.encode_frame(WP.READ_WITNESS, {}), WP.OWNER, self.Anchor())
        self.assertEqual(WP.parse_response(witness)["operation"], WP.READ_WITNESS)   # V2 path unchanged

    def test_build_anchor_service_tolerates_an_absent_k_pan(self):
        with tempfile.TemporaryDirectory() as d:
            service = S.build_anchor_service(X.key(), None, state_dir=d)
            self.assertEqual(service.dispatch(PAN.parse_frame(PAN.encode_frame(PAN.READ_PRIVACY_ANCHOR,
                                                                               {"fromVersion": 1})))["reason"],
                             "ANCHOR_KEY_ABSENT")


# --------------------------------------------------------------------- end to end with the Core API gate ---

@unittest.skipUnless(POSIX, "real filesystem semantics are POSIX")
class EndToEndTests(unittest.TestCase):
    def test_witness_anchor_owner_checkpoint_root_unlock_core_api_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "anchor"
            state.mkdir(mode=0o700)
            privacy_db = root / "privacy.db"
            conn = sqlite3.connect(privacy_db)
            conn.execute("CREATE TABLE privacy_restore_suppression_manifest (suppression_ref_id TEXT PRIMARY KEY, "
                         "identity_selector TEXT NOT NULL)")
            conn.commit()
            conn.close()
            kpan = CRED.PrivacyAnchorSigningKeyV1(Ed25519PrivateKey.generate())
            service = PAN.PrivacyAnchorServiceV1(store=PAN.AnchorStoreV1(state), signing_key=kpan, clock=Clock())

            def op(name, payload):
                return service.dispatch(PAN.parse_frame(PAN.encode_frame(name, payload)))
            op(PAN.GENESIS_PRIVACY_ANCHOR, {"entries": [], "expectedSetHead": head([])})
            docs = op(PAN.READ_PRIVACY_ANCHOR, {"fromVersion": 1})["documents"]
            kpck = Ed25519PrivateKey.generate()                       # TEST_ONLY simulated owner device
            keys = FR.FreshnessKeys(ENV, kpan.verifying_key(), CRED.PRIVACY_ANCHOR_KEY_ID, kpck.public_key(),
                                    "kpck.test-only.e2e.01")
            chain = A.verify_anchor_chain(docs, keys.anchor_key, environment=ENV, key_id=keys.anchor_key_id)
            body = A.unsigned_checkpoint(None, chain, environment=ENV, checkpointed_at="2026-10-25T12:00:00Z",
                                         key_id=keys.checkpoint_key_id)
            checkpoint = {**body, "signature": kpck.sign(A.signing_bytes("checkpoint", body)).hex()}
            boot, nonce = "boot-" + secrets.token_hex(4), secrets.token_hex(32)
            challenge = FR.issue_challenge(keys, docs, privacy_db, boot_id=boot, nonce=nonce,
                                           issued_at="2026-10-25T12:00:01Z")
            ubody = A.unsigned_unlock(challenge, checkpoint, unlocked_at="2026-10-25T12:00:02Z",
                                      key_id=keys.checkpoint_key_id)
            unlock = {**ubody, "signature": kpck.sign(A.signing_bytes("unlock", ubody)).hex()}
            marker = root / "run" / "verified"
            FR.apply_unlock(keys, docs, privacy_db, challenge, unlock, checkpoint, boot_id=boot, nonce=nonce,
                            verified_at="2026-10-25T12:00:03Z", marker_path=marker)
            gate = FR.PrivacyFreshnessGate(privacy_db, environment=ENV, marker_path=marker, intent_dir=root / "i",
                                           boot_id=lambda: boot, require_root_marker=False)
            self.assertTrue(gate.check().ready)
            # a new suppression row (begin_forget) → refused until the witness advances and the owner checkpoints
            conn = sqlite3.connect(privacy_db)
            conn.execute("INSERT INTO privacy_restore_suppression_manifest VALUES (?, ?)", tuple(entry(1)))
            conn.commit()
            conn.close()
            self.assertEqual(gate.check().status, FR.ANCHOR_BEHIND)
            prev = op(PAN.READ_PRIVACY_ANCHOR, {"fromVersion": 1})["anchorDigest"]
            self.assertEqual(op(PAN.ADVANCE_PRIVACY_ANCHOR, {"previousAnchorDigest": prev, "entries": [entry(1)],
                                                             "expectedSetHead": head([entry(1)])})["status"],
                             "COMMITTED")
            docs = op(PAN.READ_PRIVACY_ANCHOR, {"fromVersion": 1})["documents"]
            chain = A.verify_anchor_chain(docs, keys.anchor_key, environment=ENV, key_id=keys.anchor_key_id)
            body = A.unsigned_checkpoint(checkpoint, chain, environment=ENV, checkpointed_at="2026-10-25T12:00:04Z",
                                         key_id=keys.checkpoint_key_id)
            FR.apply_checkpoint(keys, docs, privacy_db,
                                {**body, "signature": kpck.sign(A.signing_bytes("checkpoint", body)).hex()},
                                boot_id=boot, verified_at="2026-10-25T12:00:05Z", marker_path=marker,
                                require_root_marker=False)
            self.assertTrue(gate.check().ready)


if __name__ == "__main__":
    unittest.main()
