"""F2/F3 First Interaction conversation evidence (synthetic, Core API level).

- StoreTests: the relay's capture store (app.py, which never imports the canonical runtime) records OWNER/LILITH
  exchanges and seals exact transcript bytes; sealed, unknown, faulted or out-of-order captures are refused; text that
  is not exactly acceptable is sealed as-is and refused by the gate, never repaired; the tables are append-only.
- GateTests: the candidate gate runs `verify_episode_evidence` against the sealed bytes and binds the trusted identity;
  invented transcripts, wrong digests, changed quotations, spoofed speakers, mismatched sessions and environments,
  and payload-supplied identities are refused; nothing claims acceptance.
- LearningGateTests: L18 V2 refuses a First Interaction intent/candidate unless the gate verifies it; the codename path
  is unchanged; candidate creation never admits or accepts memory.
- RelayTests: the existing `POST /os/conversation` relay records only authenticated capture sessions, refuses
  unauthenticated or spoofed requests before relaying, and relays every other session exactly as before.

Synthetic dialogue and a fake console only; no real conversation, identity, credential or memory.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from fastapi import HTTPException

from test_first_interaction_l04 import (  # noqa: F401  (also puts the Core API on sys.path)
    FI_PURPOSE,
    SYNTHETIC_BINDING,
    FirstInteractionCase,
    fi_action,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402

from lilith_memory import canonical_contracts as C  # noqa: E402
from lilith_memory import conversation_evidence as CE  # noqa: E402
from lilith_memory import first_interaction_v1 as FI  # noqa: E402
from lilith_memory import learning_v2  # noqa: E402
from lilith_memory import privacy_governance as privacy  # noqa: E402
from lilith_memory import slice15b2a_migration  # noqa: E402

T0 = datetime(2026, 11, 1, 18, 0, 0, tzinfo=timezone.utc)
OWNER_1 = "TEST_ONLY hi LILITH — café?"
LILITH_1 = "TEST_ONLY hello! is it moring already? \U0001f319"
OWNER_2 = "TEST_ONLY it's evening.\nLILITH: (that line is mine, not yours)"
LILITH_2 = "TEST_ONLY sorry, I guessed wrong. good night"
TEST_ONLY_CAPTURE_TOKEN = "TEST_ONLY-capture-credential-0123456789abcdef"


def stamp(seconds: float) -> str:
    return app._capture_stamp(T0 + timedelta(seconds=seconds))


def trusted(environment: str = "test") -> CE.TrustedIdentityBindingV1:
    return CE.TrustedIdentityBindingV1(environment, SYNTHETIC_BINDING)


def episode_value(evidence: dict, transcript: bytes, *, binding=None, quotations=None) -> str:
    """The FirstInteractionEpisodeV1 value an owner would build from sealed evidence (OPENING = first turn,
    CLOSING = last turn), canonicalized by the L04-owned normalizer."""
    turns = json.loads(transcript.decode("utf-8"))["turns"]
    first, last = turns[0], turns[-1]
    value = {
        "schemaVersion": 1, "valueSchema": FI.VALUE_SCHEMA,
        "identityBinding": dict(SYNTHETIC_BINDING if binding is None else binding),
        "truthBasis": FI.RECORDED_INTERACTION,
        "eventTime": {"startedAt": first["at"], "endedAt": last["at"]},
        "transcript": {"schema": FI.TRANSCRIPT_SCHEMA, "evidenceRef": evidence["evidenceRef"],
                       "sha256": evidence["sha256"], "turnCount": evidence["turnCount"]},
        "quotations": quotations or [
            {"position": FI.OPENING, "turnIndex": 0, "speaker": first["speaker"], "start": 0,
             "end": len(first["text"]), "text": first["text"]},
            {"position": FI.CLOSING, "turnIndex": len(turns) - 1, "speaker": last["speaker"], "start": 0,
             "end": len(last["text"]), "text": last["text"]},
        ],
        "access": dict(FI.ACCESS), "retention": dict(FI.RETENTION),
    }
    return FI.normalize_first_interaction_episode(value)[0]


class EvidenceCase(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.tmp_evidence = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_evidence.cleanup)
        self.evidence_db = Path(self.tmp_evidence.name) / "conversation-evidence.test.db"
        self.evidence = app.ConversationCaptureStore(self.evidence_db, now_fn=lambda: T0 + timedelta(hours=1))
        self.reader = CE.ConversationEvidenceReader(self.evidence_db)

    def capture(self, exchanges=((OWNER_1, LILITH_1), (OWNER_2, LILITH_2))) -> tuple[str, dict, bytes]:
        session = self.evidence.open_session()
        for i, (owner, lilith) in enumerate(exchanges):
            self.evidence.record_exchange(session, owner_text=owner, owner_at=stamp(10 * i),
                                          lilith_text=lilith, lilith_at=stamp(10 * i + 4.25))
        sealed = self.evidence.seal(session)
        return session, sealed, self.reader.sealed_transcript(sealed["evidenceRef"])

    def gate(self, *, identity="trusted", environment: str = "test") -> CE.FirstInteractionEvidenceGate:
        return CE.FirstInteractionEvidenceGate(
            self.reader, trusted_identity=trusted() if identity == "trusted" else identity,
            deployment_environment=environment)

    def assert_refused(self, code: str, fn, *args, **kwargs):
        with self.assertRaises((CE.ConversationEvidenceError, app.CaptureRefused)) as caught:
            fn(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)


class StoreTests(EvidenceCase):
    def test_capture_seals_exact_transcript_bytes(self):
        session, sealed, transcript = self.capture()
        self.assertEqual(sealed["sha256"], hashlib.sha256(transcript).hexdigest())
        self.assertEqual((sealed["conversationRef"], sealed["turnCount"], sealed["firstMemoryAccepted"]),
                         (session, 4, False))
        parsed = FI.parse_transcript(transcript)
        self.assertEqual([(t["speaker"], t["text"]) for t in parsed["turns"]],
                         [(FI.OWNER, OWNER_1), (FI.LILITH, LILITH_1), (FI.OWNER, OWNER_2), (FI.LILITH, LILITH_2)])
        self.assertEqual([t["at"] for t in parsed["turns"]], [stamp(0), stamp(4.25), stamp(10), stamp(14.25)])
        self.assertIn(OWNER_2.encode("utf-8").replace(b"\n", b"\\n"), transcript)   # verbatim, UTF-8, not escaped
        self.assertEqual((sealed["startedAt"], sealed["endedAt"]), (stamp(0), stamp(14.25)))

    def test_sealed_unknown_and_short_sessions_refuse(self):
        session, sealed, _ = self.capture()
        self.assert_refused("CAPTURE_SESSION_SEALED", self.evidence.require_capturable, session)
        self.assert_refused("CAPTURE_SESSION_SEALED", self.evidence.seal, session)
        self.assert_refused("CAPTURE_SESSION_NOT_OPEN", self.evidence.record_exchange, session, owner_text="x",
                            owner_at=stamp(99), lilith_text="y", lilith_at=stamp(100))
        self.assert_refused("CAPTURE_SESSION_UNKNOWN", self.evidence.require_capturable, "fi-capture-" + "0" * 32)
        self.assert_refused("CAPTURE_TOO_SHORT", self.evidence.seal, self.evidence.open_session())
        self.assertIsNone(self.reader.sealed_transcript("evidence.conv.invented"))

    def test_faulted_session_can_never_be_sealed(self):
        session = self.evidence.open_session()
        self.evidence.record_exchange(session, owner_text=OWNER_1, owner_at=stamp(0), lilith_text=LILITH_1,
                                      lilith_at=stamp(1))
        self.evidence.record_fault(session, "RELAY_504")
        self.assert_refused("CAPTURE_INCOMPLETE", self.evidence.require_capturable, session)
        self.assert_refused("CAPTURE_INCOMPLETE", self.evidence.seal, session)

    def test_out_of_order_exchange_is_refused(self):
        session = self.evidence.open_session()
        self.evidence.record_exchange(session, owner_text=OWNER_1, owner_at=stamp(10), lilith_text=LILITH_1,
                                      lilith_at=stamp(11))
        self.assert_refused("CAPTURE_ORDER_INVALID", self.evidence.record_exchange, session, owner_text=OWNER_2,
                            owner_at=stamp(5), lilith_text=LILITH_2, lilith_at=stamp(12))
        self.assert_refused("CAPTURE_ORDER_INVALID", self.evidence.record_exchange, session, owner_text=OWNER_2,
                            owner_at=stamp(13), lilith_text=LILITH_2, lilith_at=stamp(12))

    def test_unrepairable_text_is_sealed_exactly_and_refused_by_the_gate(self):
        _session, sealed, transcript = self.capture(((OWNER_1, "TEST_ONLY bell\u0007"), (OWNER_2, LILITH_2)))
        self.assertIn("TEST_ONLY bell\u0007".encode("utf-8").replace(b"\x07", b"\\u0007"), transcript)
        self.assert_refused("TEXT_PROHIBITED_CHARACTER", CE.FirstInteractionEvidenceGate(
            self.reader, trusted_identity=trusted(), deployment_environment="test"),
            episode_value(sealed, transcript))

    def test_evidence_tables_are_append_only(self):
        session, sealed, _ = self.capture()
        conn = sqlite3.connect(self.evidence_db)
        try:
            for sql in ("UPDATE fi_capture_turn SET text='forged' WHERE session_id=?",
                        "DELETE FROM fi_capture_turn WHERE session_id=?",
                        "UPDATE fi_conversation_evidence SET sha256=sha256 WHERE session_id=?",
                        "DELETE FROM fi_conversation_evidence WHERE session_id=?"):
                with self.subTest(sql=sql), self.assertRaises(sqlite3.DatabaseError):
                    conn.execute(sql, (session,))
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("INSERT INTO fi_capture_turn VALUES (?,?,?,?,?)",
                             (session, 4, "OWNER", stamp(99), "TEST_ONLY late"))
        finally:
            conn.close()


class GateTests(EvidenceCase):
    def test_valid_captured_value_passes_without_claiming_acceptance(self):
        session, sealed, transcript = self.capture()
        value = episode_value(sealed, transcript)
        facts = self.gate()(value, expected_conversation_ref=session)
        self.assertEqual((facts["truthClaim"], facts["authorizesAdmission"], facts["firstMemoryAccepted"]),
                         (False, False, False))
        self.assertEqual((facts["evidenceRef"], facts["conversationRef"], facts["transcriptSha256"]),
                         (sealed["evidenceRef"], session, sealed["sha256"]))
        self.assertEqual(facts["payloadDigest"], hashlib.sha256(value.encode("ascii")).hexdigest())

    def test_invented_transcript_is_refused(self):
        _session, sealed, transcript = self.capture()
        invented = app._capture_transcript_bytes("conv.invented", [(FI.OWNER, stamp(0), OWNER_1),
                                                         (FI.LILITH, stamp(1), "TEST_ONLY invented reply")])
        fake = {"evidenceRef": "evidence.conv.invented", "sha256": hashlib.sha256(invented).hexdigest(),
                "turnCount": 2}
        self.assert_refused("EVIDENCE_UNKNOWN", self.gate(), episode_value(fake, invented))
        borrowed = dict(fake, evidenceRef=sealed["evidenceRef"])          # a real reference, invented bytes
        self.assert_refused("TRANSCRIPT_DIGEST_MISMATCH", self.gate(), episode_value(borrowed, invented))

    def test_wrong_digest_is_refused(self):
        _session, sealed, transcript = self.capture()
        wrong = dict(sealed, sha256=hashlib.sha256(transcript + b" ").hexdigest())
        self.assert_refused("TRANSCRIPT_DIGEST_MISMATCH", self.gate(), episode_value(wrong, transcript))

    def test_changed_quotation_is_refused(self):
        _session, sealed, transcript = self.capture()
        changed = LILITH_2.replace("wrong", "right")
        quotes = [{"position": FI.OPENING, "turnIndex": 0, "speaker": FI.OWNER, "start": 0, "end": len(OWNER_1),
                   "text": OWNER_1},
                  {"position": FI.CLOSING, "turnIndex": 3, "speaker": FI.LILITH, "start": 0, "end": len(changed),
                   "text": changed}]
        self.assert_refused("QUOTATION_NOT_VERBATIM", self.gate(), episode_value(sealed, transcript,
                                                                                 quotations=quotes))

    def test_spoofed_speaker_is_refused(self):
        _session, sealed, transcript = self.capture()
        quotes = [{"position": FI.OPENING, "turnIndex": 0, "speaker": FI.LILITH, "start": 0, "end": len(OWNER_1),
                   "text": OWNER_1},
                  {"position": FI.CLOSING, "turnIndex": 3, "speaker": FI.LILITH, "start": 0, "end": len(LILITH_2),
                   "text": LILITH_2}]
        self.assert_refused("QUOTATION_SPEAKER_MISMATCH", self.gate(), episode_value(sealed, transcript,
                                                                                     quotations=quotes))

    def test_mismatched_session_is_refused(self):
        session_a, sealed_a, transcript_a = self.capture()
        _session_b, sealed_b, _transcript_b = self.capture(((OWNER_1, "TEST_ONLY another reply"),))
        self.assert_refused("CONVERSATION_MISMATCH", self.gate(), episode_value(sealed_a, transcript_a),
                            expected_conversation_ref=_session_b)
        crossed = dict(sealed_a, evidenceRef=sealed_b["evidenceRef"])   # session A's value, session B's evidence
        self.assert_refused("TRANSCRIPT_DIGEST_MISMATCH", self.gate(), episode_value(crossed, transcript_a))
        self.assertEqual(self.gate()(episode_value(sealed_a, transcript_a))["conversationRef"], session_a)

    def test_environment_and_identity_are_trusted_never_from_the_value(self):
        _session, sealed, transcript = self.capture()
        value = episode_value(sealed, transcript)
        self.assert_refused("IDENTITY_ENVIRONMENT_MISMATCH", self.gate(environment="dev"), value)
        self.assert_refused("IDENTITY_ENVIRONMENT_MISMATCH", CE.FirstInteractionEvidenceGate(
            self.reader, trusted_identity=trusted("dev"), deployment_environment="test"), value)
        self.assert_refused("IDENTITY_PROFILE_UNAVAILABLE", self.gate(identity=None), value)
        supplied = dict(SYNTHETIC_BINDING, lilithIdentityId="lid1." + "cd" * 16)    # payload-chosen identity
        self.assert_refused("IDENTITY_BINDING_MISMATCH", self.gate(),
                            episode_value(sealed, transcript, binding=supplied))
        with self.assertRaises(CE.ConversationEvidenceError):
            CE.TrustedIdentityBindingV1("staging", SYNTHETIC_BINDING)


class LearningGateTests(EvidenceCase, FirstInteractionCase):
    def setUp(self) -> None:
        super().setUp()
        self.migrate_fi()
        self.enable_fi()

    def store_with_gate(self, gate):
        return learning_v2.LearningV2Store(
            self.db, privacy_hold_resolver=self.hold, containment_ready=lambda: True, actor_authority=self.actor,
            policy_store=self.policy, consent_store=self.consent, now_fn=lambda: self.now,
            first_interaction_evidence_gate=gate)

    def fi_rows(self) -> int:
        conn = sqlite3.connect(self.db)
        try:
            return sum(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                       for t in ("learning_fi_intent_v1", "learning_fi_candidate_v1"))
        finally:
            conn.close()

    def action_for(self, value: str):
        return fi_action(json.loads(value))

    def test_captured_value_reaches_a_candidate_that_is_not_accepted_memory(self):
        _session, sealed, transcript = self.capture()
        action, encoded = self.action_for(episode_value(sealed, transcript))
        self.learning = self.store_with_gate(self.gate())
        _proposal, ref, _consent = self.proposal_with(action, encoded, nonce="captured")
        self.assertTrue(ref.proposal_ref_id)
        conn = sqlite3.connect(self.db)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM memory_item WHERE memory_class=?",
                                          (action.memory_class,)).fetchone()[0], 0)   # nothing admitted
        finally:
            conn.close()
        self.assertIsNone(self.fi_store().get_active(action.memory_class, action.subject_namespace,
                                                     action.subject_key))

    def test_without_gate_or_with_refused_evidence_nothing_is_stored(self):
        _session, sealed, transcript = self.capture()
        good = episode_value(sealed, transcript)
        wrong = episode_value(dict(sealed, sha256="0" * 64), transcript)
        for i, (gate, value, reason) in enumerate((
                                    (None, good, "gate is unavailable"),
                                    (self.gate(), wrong, "TRANSCRIPT_DIGEST_MISMATCH"),
                                    (self.gate(environment="dev"), good, "IDENTITY_ENVIRONMENT_MISMATCH"),
                                    (lambda _v: {"payloadDigest": "0" * 64}, good, "GATE_RESULT_INVALID"))):
            with self.subTest(reason=reason):
                self.learning = self.store_with_gate(gate)
                with self.assertRaisesRegex(learning_v2.LearningV2Error, reason):
                    self.proposal_with(*self.action_for(value), nonce=f"refused.{i}")
                self.assertEqual(self.fi_rows(), 0)                              # no plaintext intent stored

    def test_codename_path_needs_no_evidence_gate(self):
        self.learning = self.store_with_gate(None)
        result, _ref, _consent = self.create()
        self.assertTrue(result.revision_id)


class FakeConsole:
    """The localhost `lilith_os` console, faked: records what the relay sent and answers with a fixed reply."""

    def __init__(self, replies=(LILITH_1, LILITH_2), fail: bool = False) -> None:
        self.replies, self.fail, self.sent = list(replies), fail, []

    def __call__(self, req, timeout=None):
        self.sent.append(json.loads(req.data.decode("utf-8")))
        if self.fail:
            raise app._urlerr.URLError("TEST_ONLY console down")
        body = json.dumps({"reply": self.replies.pop(0), "session": self.sent[-1]["session"], "state": "ok"})
        response = mock.MagicMock()
        response.read.return_value = body.encode("utf-8")
        response.__enter__.return_value = response
        return response


class RelayTests(EvidenceCase):
    def setUp(self) -> None:
        super().setUp()
        privacy_db = Path(self.tmp_evidence.name) / "privacy.test.db"
        slice15b2a_migration.migrate_privacy(privacy_db, applied_at="2026-11-01T17:00:00Z")   # no hold: open
        self.privacy_store = privacy.PrivacyGovernanceStore(privacy_db, b"TEST_ONLY relay privacy secret (32+ b)",
                                                            None)
        self.env = {"LILITH_FI_EVIDENCE_CAPTURE": "1", "LILITH_OS_OWNER_CAPTURE_TOKEN": TEST_ONLY_CAPTURE_TOKEN,
                    "LILITH_FI_EVIDENCE_DB": str(self.evidence_db), "LILITH_PRIVACY_DB_PATH": str(privacy_db)}

    def call(self, fn, payload, credential=TEST_ONLY_CAPTURE_TOKEN, *, env=None, console=None):
        console = console or FakeConsole()
        with mock.patch.dict(os.environ, self.env if env is None else env), \
                mock.patch.object(app, "_hermes_env", lambda key, default="": default), \
                mock.patch.object(app._urlreq, "urlopen", console):
            return fn(payload, credential)

    def refused(self, status: int, detail: str, fn, payload, credential=TEST_ONLY_CAPTURE_TOKEN, **kwargs):
        with self.assertRaises(HTTPException) as caught:
            self.call(fn, payload, credential, **kwargs)
        self.assertEqual((caught.exception.status_code, caught.exception.detail), (status, detail))

    def open(self) -> str:
        CE.provision_capture_store(self.evidence_db, self.privacy_store)  # operator step; the relay never creates
        return self.call(app.os_conversation_evidence, {"action": "open"})["session"]

    def test_existing_sessions_are_relayed_exactly_as_before(self):
        for env in ({}, self.env):
            console = FakeConsole()
            out = self.call(app.os_conversation, {"message": "  hi  ", "session": "lilith-os-abc"}, None, env=env,
                            console=console)
            self.assertEqual(out, {"reply": LILITH_1, "session": "lilith-os-abc", "state": "ok"})
            self.assertEqual(console.sent, [{"message": "hi", "session": "lilith-os-abc"}])
        self.assertFalse(self.evidence_db.exists())                              # capture never touched

    def test_authenticated_capture_records_exactly_what_was_relayed(self):
        session = self.open()
        console = FakeConsole()
        first = self.call(app.os_conversation, {"message": OWNER_1, "session": session}, console=console)
        self.call(app.os_conversation, {"message": OWNER_2, "session": session}, console=console)
        self.assertEqual((first["reply"], first["capture"]), (LILITH_1, {"state": "OPEN", "captured": True}))
        self.assertEqual([s["message"] for s in console.sent], [OWNER_1, OWNER_2])
        sealed = self.call(app.os_conversation_evidence, {"action": "seal", "session": session})
        read = self.call(app.os_conversation_evidence, {"action": "transcript", "session": session})
        transcript = read["transcript"].encode("utf-8")
        self.assertEqual(hashlib.sha256(transcript).hexdigest(), sealed["sha256"])
        turns = FI.parse_transcript(transcript)["turns"]
        self.assertEqual([(t["speaker"], t["text"]) for t in turns],
                         [(FI.OWNER, OWNER_1), (FI.LILITH, LILITH_1), (FI.OWNER, OWNER_2), (FI.LILITH, LILITH_2)])
        facts = self.gate()(episode_value(sealed, transcript), expected_conversation_ref=session)
        self.assertFalse(facts["firstMemoryAccepted"])
        self.refused(409, "CAPTURE_SESSION_SEALED", app.os_conversation, {"message": "late", "session": session})

    def test_unauthenticated_capture_is_refused_before_relaying(self):
        session = self.open()
        for credential in (None, "", "TEST_ONLY-wrong-credential-0123456789abcdef", mock.sentinel.header):
            with self.subTest(credential=credential):
                console = FakeConsole()
                self.refused(401, "CAPTURE_NOT_AUTHENTICATED", app.os_conversation,
                             {"message": OWNER_1, "session": session}, credential, console=console)
                self.assertEqual(console.sent, [])
        self.refused(401, "CAPTURE_NOT_AUTHENTICATED", app.os_conversation_evidence,
                     {"action": "seal", "session": session}, None)
        self.refused(401, "CAPTURE_NOT_AUTHENTICATED", app.os_conversation_evidence, {"action": "open"}, "x")
        self.assert_refused("CAPTURE_TOO_SHORT", self.evidence.seal, session)       # nothing was captured

    def test_inactive_or_unconfigured_capture_refuses(self):
        inactive = dict(self.env, LILITH_FI_EVIDENCE_CAPTURE="0")       # even with a valid credential configured
        console = FakeConsole()
        self.refused(403, "CAPTURE_INACTIVE", app.os_conversation,
                     {"message": OWNER_1, "session": "fi-capture-" + "a" * 32}, env=inactive, console=console)
        for payload in ({"action": "open"}, {"action": "seal", "session": "fi-capture-" + "a" * 32},
                        {"action": "transcript", "session": "fi-capture-" + "a" * 32}):
            with self.subTest(payload=payload):
                self.refused(403, "CAPTURE_INACTIVE", app.os_conversation_evidence, payload, env=inactive)
        self.assertEqual(console.sent, [])
        self.assertFalse(self.evidence_db.exists())                              # nothing created or exposed
        self.refused(503, "CAPTURE_CREDENTIAL_UNCONFIGURED", app.os_conversation_evidence, {"action": "open"},
                     env=dict(self.env, LILITH_OS_OWNER_CAPTURE_TOKEN="short"))

    def test_spoofed_payloads_and_unknown_sessions_are_refused(self):
        session = self.open()
        for extra in ({"speaker": "LILITH"}, {"reply": LILITH_1}, {"turns": []}, {"at": stamp(0)}):
            with self.subTest(extra=extra):
                console = FakeConsole()
                self.refused(400, "CAPTURE_PAYLOAD_INVALID", app.os_conversation,
                             {"message": OWNER_1, "session": session, **extra}, console=console)
                self.assertEqual(console.sent, [])
        self.refused(400, "CAPTURE_PAYLOAD_INVALID", app.os_conversation, {"message": " padded", "session": session})
        self.refused(404, "CAPTURE_SESSION_UNKNOWN", app.os_conversation,
                     {"message": OWNER_1, "session": "fi-capture-" + "b" * 32})
        self.refused(404, "EVIDENCE_UNKNOWN", app.os_conversation_evidence, {"action": "transcript",
                                                                             "session": session})

    def test_relay_failure_poisons_the_capture_session(self):
        session = self.open()
        self.call(app.os_conversation, {"message": OWNER_1, "session": session})
        with self.assertRaises(HTTPException):
            self.call(app.os_conversation, {"message": OWNER_2, "session": session}, console=FakeConsole(fail=True))
        self.refused(409, "CAPTURE_INCOMPLETE", app.os_conversation, {"message": OWNER_2, "session": session})
        self.refused(409, "CAPTURE_INCOMPLETE", app.os_conversation_evidence, {"action": "seal", "session": session})


if __name__ == "__main__":
    unittest.main()
