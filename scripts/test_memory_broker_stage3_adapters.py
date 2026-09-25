"""Source-only Stage-III adapter contracts; no DEV or operational authority."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from scripts import memory_broker_stage2_control as control
from scripts import memory_broker_stage3_adapters as adapters
from scripts import memory_broker_stage3_transition as transition


NOW = datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc)
AUTH = "a" * 32
CHALLENGE = "och." + "b" * 32


def proposal() -> dict:
    marker = control.stage3_authorization_value(NOW, AUTH)
    challenge = {
        "ownerPrincipal": control.STAGE3_ACCESS_IDENTITY,
        "challengeId": CHALLENGE, "requestDigest": "c" * 64,
        "actionDigest": "d" * 64,
        "expiresAt": (NOW + timedelta(seconds=60)).isoformat(
            timespec="seconds").replace("+00:00", "Z"),
    }
    assertion = {
        "credentialRecordId": control.STAGE3_CREDENTIAL_RECORD_ID,
        "credentialId": control.STAGE3_CREDENTIAL_ID,
        "clientDataJSON": "AQ", "authenticatorData": "Ag", "signature": "Aw",
    }
    return control.stage3_arm_proposal(marker, challenge, assertion,
                                       now=NOW, nonce="e" * 64)


def binding(invocation: str) -> dict:
    return {"authorizationId": AUTH, "challengeId": CHALLENGE,
            "frameSha256": "f" * 64,
            "candidateInvocationId": "initial",
            "observedInvocationId": invocation}


class Stage3AdapterContracts(unittest.TestCase):
    def test_exact_frame_is_closed_canonical_and_frozen(self):
        value = proposal()
        session = adapters.Session(value)
        original = session._frame
        self.assertEqual(struct.unpack(">I", original[:4])[0], len(original) - 4)
        decoded = json.loads(original[4:])
        self.assertEqual(decoded["operation"], "CONFIRM_SYNTHETIC")
        self.assertEqual(decoded["payload"]["assertion"], value["assertion"])
        self.assertEqual(session.frame_sha256, hashlib.sha256(original).hexdigest())
        self.assertNotIn("signature", repr(session))
        value["assertion"]["signature"] = "SUBSTITUTED"
        self.assertEqual(session._frame, original)
        self.assertEqual(session._proposal["assertion"]["signature"], "Aw")
        for altered in ({**proposal(), "armWritten": True},
                        {**proposal(), "schemaVersion": True},
                        {**proposal(), "extra": 1}):
            with self.assertRaisesRegex(adapters.AdapterError,
                                        "STAGE3_EXACT_FRAME_PROPOSAL"):
                adapters.Session(altered)

    def test_fixed_children_receive_authority_only_on_stdin(self):
        sent = []

        def fake_run(args, **kwargs):
            sent.append((args, kwargs))
            return subprocess.CompletedProcess(args, 0,
                                               b'{"status":"FRAME_SENT"}', b"")

        with patch.object(adapters.subprocess, "run", side_effect=fake_run):
            self.assertEqual(adapters.Session._run_child(
                "lilith-memory-relay", adapters.RELAY_SENDER_SOURCE,
                b"synthetic-proof-frame"), {"status": "FRAME_SENT"})
        args, kwargs = sent[0]
        self.assertEqual(args[:4], ["/usr/sbin/runuser", "-u",
                                    "lilith-memory-relay", "--"])
        self.assertEqual(args[-2:], ["-c", adapters.RELAY_SENDER_SOURCE])
        self.assertNotIn(b"synthetic-proof-frame", str(args).encode())
        self.assertNotIn(b"synthetic-proof-frame", str(kwargs["env"]).encode())
        self.assertEqual(kwargs["input"], b"synthetic-proof-frame")
        with self.assertRaisesRegex(adapters.AdapterError,
                                    "STAGE3_ADAPTER_CHILD_SCOPE"):
            adapters.Session._run_child("root", adapters.RECOVERY_SOURCE, b"{}")

    def test_attempt_is_fsynced_before_child_and_cannot_be_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            session = adapters.Session(proposal())
            seen = []

            def operation():
                seen.append((vault / "recovery-attempt.json").is_file())
                return {"status": "PROOF_BURNED_NO_CLAIM",
                        "challengeId": CHALLENGE}

            with patch.object(transition, "VAULT", vault):
                result = session._one_shot("recovery", binding("restarted"),
                                           operation)
                self.assertEqual(result["status"], "PROOF_BURNED_NO_CLAIM")
                self.assertEqual(seen, [True])
                self.assertEqual(json.loads((vault / "recovery-result.json").read_bytes())[
                    "observedInvocationId"], "restarted")
                with self.assertRaisesRegex(adapters.AdapterError,
                                            "STAGE3_ADAPTER_ALREADY_ATTEMPTED"):
                    session._one_shot("recovery", binding("restarted"), operation)
            self.assertEqual(seen, [True])

    def test_initial_recovery_replay_use_one_frame_and_fixed_identities(self):
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            session = adapters.Session(proposal())
            frame_sha = session.frame_sha256
            received = []

            def bound(phase):
                return {**binding("initial" if phase == "INITIAL" else "restarted"),
                        "frameSha256": frame_sha}

            def child(user, source, payload):
                received.append((user, source, payload))
                if user == "lilith-memory-broker":
                    return {"status": "PROOF_BURNED_NO_CLAIM",
                            "challengeId": CHALLENGE}
                meta, frame = payload.split(b"\n", 1)
                self.assertEqual(frame, session._frame)
                self.assertEqual(json.loads(meta)["frameSha256"], frame_sha)
                return {"status": "FRAME_SENT" if len(received) == 1
                        else "NO_RESPONSE", "frameSha256": frame_sha}

            def regular(path, **_kwargs):
                return path.read_bytes()

            with patch.object(transition, "VAULT", vault), \
                 patch.object(transition, "regular", side_effect=regular), \
                 patch.object(adapters.Session, "_binding", side_effect=bound), \
                 patch.object(adapters.Session, "_db_state"), \
                 patch.object(adapters.Session, "_run_child", side_effect=child), \
                 patch.object(control, "relay", return_value={"status": "HEALTH_OK"}):
                session.submit_initial_once()
                session.recover_once()
                session.replay_exact_once()
            self.assertEqual([item[0] for item in received], [
                "lilith-memory-relay", "lilith-memory-broker",
                "lilith-memory-relay"])
            self.assertEqual(received[0][2].split(b"\n", 1)[1],
                             received[2][2].split(b"\n", 1)[1])
            self.assertEqual(json.loads(received[1][2]),
                             {"challengeId": CHALLENGE})
            self.assertTrue((vault / "initial-submit-attempt.json").is_file())
            self.assertTrue((vault / "recovery-attempt.json").is_file())
            self.assertTrue((vault / "replay-submit-attempt.json").is_file())

    def test_ambiguous_child_failure_keeps_attempt_and_contains(self):
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            session = adapters.Session(proposal())
            with patch.object(transition, "VAULT", vault), \
                 patch.object(adapters.Session, "_binding",
                              return_value=binding("initial")), \
                 patch.object(adapters.Session, "_run_child",
                              side_effect=adapters.AdapterError("AMBIGUOUS")), \
                 patch.object(transition, "contain_failure") as contain:
                with self.assertRaisesRegex(adapters.AdapterError, "AMBIGUOUS"):
                    session.submit_initial_once()
            self.assertTrue((vault / "initial-submit-attempt.json").is_file())
            self.assertFalse((vault / "initial-submit-result.json").exists())
            contain.assert_called_once()

    def test_child_sources_are_fixed_and_do_not_regenerate_proof(self):
        compile(adapters.RELAY_SENDER_SOURCE, "relay-child", "exec")
        compile(adapters.RECOVERY_SOURCE, "recovery-child", "exec")
        self.assertEqual(adapters.RECOVERY_SOURCE.count("broker.recover("), 1)
        self.assertIn(control.STAGE3_RELEASE, adapters.RECOVERY_SOURCE)
        self.assertIn('conn.sendall(frame)', adapters.RELAY_SENDER_SOURCE)
        self.assertNotIn("assertion(challenge", adapters.RELAY_SENDER_SOURCE)
        self.assertNotIn("RECOVER", adapters.RELAY_SENDER_SOURCE)

    def test_initial_binding_rejects_expired_material_before_child(self):
        value = proposal()
        session = adapters.Session(value)
        marker = control.stage3_authorization_value(NOW, AUTH)
        intent = {"record": {"authorizationId": AUTH}}

        def read_bound(path, **_kwargs):
            if path == control.STAGE3_USED:
                return adapters.canonical(marker)
            return adapters.canonical(intent)

        with patch.object(control, "assert_host"), \
             patch.object(control, "stage3_verify_candidate_release"), \
             patch.object(transition.Journal, "last",
                          return_value=("CANDIDATE_ACTIVE", {})), \
             patch.object(transition, "regular", side_effect=read_bound), \
             patch.object(adapters.os.path, "lexists", return_value=False), \
             patch.object(adapters.Session, "_run_child") as child:
            with self.assertRaisesRegex(adapters.AdapterError,
                                        "STAGE3_ADAPTER_INITIAL_EXPIRED"):
                session._binding("INITIAL")
        child.assert_not_called()

    @unittest.skipUnless(os.name == "posix" and os.geteuid() != 0,
                         "synthetic Unix relay fixture requires non-root POSIX")
    def test_relay_child_forwards_exact_bytes_to_synthetic_socket(self):
        with tempfile.TemporaryDirectory() as directory:
            socket_path = str(Path(directory) / "synthetic.sock")
            source = adapters.RELAY_SENDER_SOURCE.replace(
                'pwd.getpwnam("lilith-memory-relay").pw_uid', 'os.geteuid()').replace(
                    '/run/lilith-memory/owner.sock', socket_path)
            session = adapters.Session(proposal())
            received = []
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(socket_path)
            server.listen(2)

            def receive_twice():
                for _ in range(2):
                    conn, _ = server.accept()
                    with conn:
                        data = b""
                        while len(data) < len(session._frame):
                            data += conn.recv(len(session._frame) - len(data))
                        received.append(data)

            thread = threading.Thread(target=receive_twice, daemon=True)
            thread.start()
            try:
                for phase in ("INITIAL", "REPLAY"):
                    meta = adapters.canonical({"phase": phase,
                                               "challengeId": CHALLENGE,
                                               "frameSha256": session.frame_sha256})
                    child = subprocess.run([sys.executable, "-c", source],
                                           input=meta + session._frame,
                                           capture_output=True, timeout=10)
                    self.assertEqual(child.returncode, 0, child.stderr)
                thread.join(timeout=5)
                self.assertEqual(received, [session._frame, session._frame])
            finally:
                server.close()


if __name__ == "__main__":
    unittest.main()
