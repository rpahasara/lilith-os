#!/usr/bin/env python3
"""Dormant, fixed Stage-III A2 recovery and exact-frame relay adapters.

No CLI or workflow registers these adapters. The future final controller must
retain a Session in its guarded process and independently prove barrier/kill.
Nothing here issues authority, prepares proof, writes an arm, or signals broker.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
import re
import sqlite3
import stat
import struct
import subprocess

from scripts import memory_broker_stage2_control as control
from scripts import memory_broker_stage3_liveness as liveness
from scripts import memory_broker_stage3_transition as transition


class AdapterError(control.Stage2Error):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise AdapterError(code)


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def exact_confirm_frame(proposal: dict) -> bytes:
    """Freeze the prepared assertion once; never call the signing relay again."""
    require(isinstance(proposal, dict) and set(proposal) == {
        "schemaVersion", "recordType", "authorizationId", "challenge",
        "assertion", "arm", "armSha256", "armWritten", "proofConsumed"} and
        type(proposal["schemaVersion"]) is int and
        proposal["schemaVersion"] == 1 and
        proposal["recordType"] == "Stage3A2ExecutionProposalV1" and
        proposal["armWritten"] is False and proposal["proofConsumed"] is False and
        isinstance(proposal["challenge"], dict) and
        isinstance(proposal["arm"], dict) and
        isinstance(proposal["armSha256"], str) and
        re.fullmatch(r"[0-9a-f]{64}", proposal["armSha256"]) is not None and
        isinstance(proposal["assertion"], dict) and
        set(proposal["assertion"]) == {"credentialRecordId", "credentialId",
                                       "clientDataJSON", "authenticatorData",
                                       "signature"} and
        isinstance(proposal["challenge"].get("challengeId"), str) and
        re.fullmatch(r"och\.[0-9a-f]{32}",
                     proposal["challenge"]["challengeId"]) is not None,
        "STAGE3_EXACT_FRAME_PROPOSAL")
    value = {"protocol": "LILITH_MEMORY_BROKER", "schemaVersion": 1,
             "operation": "CONFIRM_SYNTHETIC",
             "payload": {"challengeId": proposal["challenge"]["challengeId"],
                         "assertion": proposal["assertion"]}}
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    # All closed fields are ASCII; sorted JSON is the candidate protocol's
    # RFC 8785 form for this specific object (no floats or Unicode strings).
    require(raw.isascii() and 0 < len(raw) <= 16 * 1024,
            "STAGE3_EXACT_FRAME_ENCODING")
    return struct.pack(">I", len(raw)) + raw


# Fixed relay-UID child.  Metadata plus the canonical pre-generated frame
# arrive on anonymous stdin.  No proof bytes enter argv, env, files or output.
RELAY_SENDER_SOURCE = r'''
import hashlib,json,os,pwd,re,socket,struct,sys
try:
    if (os.name != "posix" or os.geteuid() == 0 or
            os.geteuid() != pwd.getpwnam("lilith-memory-relay").pw_uid):
        raise ValueError("identity")
    meta = json.loads(sys.stdin.buffer.readline(512))
    frame = sys.stdin.buffer.read(16389)
    if (set(meta) != {"phase","challengeId","frameSha256"} or
            meta["phase"] not in ("INITIAL","REPLAY") or
            not isinstance(meta["challengeId"],str) or
            re.fullmatch(r"och\.[0-9a-f]{32}",meta["challengeId"]) is None or
            not isinstance(meta["frameSha256"],str) or
            re.fullmatch(r"[0-9a-f]{64}",meta["frameSha256"]) is None or
            not 4 < len(frame) <= 16388 or
            struct.unpack(">I",frame[:4])[0] != len(frame)-4 or
            hashlib.sha256(frame).hexdigest() != meta["frameSha256"]):
        raise ValueError("binding")
    value = json.loads(frame[4:])
    raw = json.dumps(value,sort_keys=True,separators=(",",":"),
                     ensure_ascii=False).encode("utf-8")
    if (not raw.isascii() or raw != frame[4:] or
            set(value) != {"protocol","schemaVersion","operation","payload"} or
            value["protocol"] != "LILITH_MEMORY_BROKER" or
            type(value["schemaVersion"]) is not int or
            value["schemaVersion"] != 1 or
            value["operation"] != "CONFIRM_SYNTHETIC" or
            set(value["payload"]) != {"challengeId","assertion"} or
            value["payload"]["challengeId"] != meta["challengeId"] or
            not isinstance(value["payload"]["assertion"],dict) or
            set(value["payload"]["assertion"]) != {
                "credentialRecordId","credentialId","clientDataJSON",
                "authenticatorData","signature"}):
        raise ValueError("frame")
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
        conn.settimeout(3)
        conn.connect("/run/lilith-memory/owner.sock")
        conn.sendall(frame)
        if meta["phase"] == "REPLAY" and conn.recv(1) != b"":
            raise ValueError("unexpected response")
    print(json.dumps({"status":"FRAME_SENT" if meta["phase"] == "INITIAL"
                      else "NO_RESPONSE", "frameSha256":meta["frameSha256"]},
                     sort_keys=True,separators=(",",":")))
except BaseException:
    raise SystemExit(1) from None
'''


# Fixed broker-UID child. The candidate code, config and state paths are
# constants, not caller-selected targets. Root verifies the V2/journal binding
# and the A2 no-claim branch, then fsyncs an attempt before launching it.
RECOVERY_SOURCE = r'''
import json,os,pwd,re,socket,sys
from pathlib import Path
try:
    if (os.name != "posix" or os.environ.get("LILITH_ENV") != "dev" or
            os.geteuid() == 0 or
            os.geteuid() != pwd.getpwnam("lilith-memory-broker").pw_uid or
            any(os.environ.get(key) for key in (
                "PYTHONPATH","LILITH_COGNITIVE_DB_PATH","LILITH_PRIVACY_DB_PATH",
                "LILITH_ACTOR_KEY_PATH","LILITH_PRIVACY_KEY_PATH",
                "LILITH_CONTAINMENT_KEY_PATH"))):
        raise ValueError("identity")
    value = json.loads(sys.stdin.buffer.read(256))
    if (set(value) != {"challengeId"} or
            not isinstance(value["challengeId"],str) or
            re.fullmatch(r"och\.[0-9a-f]{32}",value["challengeId"]) is None):
        raise ValueError("challenge")
    from lilith_memory_broker.dev_config import DevConfig
    from lilith_memory_broker.dev_core import DevSyntheticBrokerCore
    from lilith_memory_broker.dev_state import DevOwnerControlState
    from lilith_memory_broker.synthetic_evidence import SyntheticEvidenceStore
    release = "4a04f2d09a2b32aecedfe777090fd2e1a27ec909"
    root = Path("/opt/lilith-memory-broker")
    if os.readlink(root / "current") != "releases/" + release:
        raise ValueError("selector")
    manifest = json.loads((root / "current/release-manifest.json").read_bytes())
    config = DevConfig.from_file(Path("/etc/lilith-memory-broker/dev.json"))
    if manifest.get("candidateSha") != release or config.release_sha != release:
        raise ValueError("release")
    owner = DevOwnerControlState(
        Path("/var/lib/lilith-memory-broker/owner-control/owner_control.db"),
        config,expected_uid=os.geteuid())
    evidence = SyntheticEvidenceStore(
        Path("/var/lib/lilith-memory-broker/state/synthetic_evidence.db"),
        release_sha=release,expected_uid=os.geteuid())
    broker = DevSyntheticBrokerCore(
        config,owner,evidence,hostname=socket.gethostname(),
        machine_id=Path("/etc/machine-id").read_text(encoding="ascii").strip(),
        release_sha=release)
    result = broker.recover(value["challengeId"])
    if result != {"status":"PROOF_BURNED_NO_CLAIM",
                  "challengeId":value["challengeId"]}:
        raise ValueError("unexpected recovery")
    print(json.dumps(result,sort_keys=True,separators=(",",":")))
except BaseException:
    raise SystemExit(1) from None
'''


class Session:
    """One in-memory assertion and one durable attempt per closed action."""

    __slots__ = ("_proposal", "_frame", "_frame_sha", "_pid")

    def __init__(self, proposal: dict):
        self._proposal = json.loads(canonical(proposal))
        self._frame = exact_confirm_frame(self._proposal)
        self._frame_sha = digest(self._frame)
        self._pid = os.getpid()

    def __repr__(self) -> str:
        return "<Stage3A2AdapterSession redacted>"

    @property
    def frame_sha256(self) -> str:
        return self._frame_sha

    def _db_state(self, expected_state: str) -> None:
        challenge = self._proposal["challenge"]
        identifier = challenge["challengeId"]
        with sqlite3.connect(f"file:{control.OWNER_DB.as_posix()}?mode=ro",
                             uri=True) as owner, sqlite3.connect(
                                 f"file:{control.EVIDENCE_DB.as_posix()}?mode=ro",
                                 uri=True) as evidence:
            rows = owner.execute(
                "SELECT state,challenge_json FROM owner_proof_challenge_v1 "
                "WHERE challenge_id=?", (identifier,)).fetchall()
            requests = owner.execute(
                "SELECT request_digest,request_json FROM owner_request_v1 "
                "WHERE challenge_id=?", (identifier,)).fetchall()
            claims = owner.execute(
                "SELECT COUNT(*) FROM synthetic_claim_v1 WHERE challenge_id=?",
                (identifier,)).fetchone()[0]
            emitted = evidence.execute(
                "SELECT COUNT(*) FROM synthetic_evidence_v1 WHERE challenge_id=?",
                (identifier,)).fetchone()[0]
        require(len(rows) == len(requests) == 1 and
                rows[0][0] == expected_state and
                json.loads(bytes(rows[0][1])) == challenge and
                requests[0][0] == challenge["requestDigest"] and
                json.loads(bytes(requests[0][1]))["actionDigest"] ==
                    challenge["actionDigest"] and
                claims == emitted == 0, "STAGE3_ADAPTER_A2_STATE_DRIFT")

    def _binding(self, phase: str) -> dict:
        require(os.getpid() == self._pid and
                phase in ("INITIAL", "RECOVERY", "REPLAY"),
                "STAGE3_ADAPTER_PROCESS_OR_PHASE")
        control.assert_host()
        control.stage3_verify_candidate_release(selected=True)
        journal_phase, candidate = transition.Journal(transition.VAULT).last()
        require(journal_phase == "CANDIDATE_ACTIVE", "STAGE3_ADAPTER_JOURNAL_PHASE")
        intent = json.loads(transition.regular(
            transition.VAULT / "000-INTENT.json", uid=0, gid=0, mode=0o600))["record"]
        require(not os.path.lexists(control.STAGE3_MARKER),
                "STAGE3_ADAPTER_ACTIVE_AUTHORIZATION")
        raw = transition.regular(control.STAGE3_USED, uid=0, gid=0, mode=0o600)
        marker_value = json.loads(raw)
        issued = datetime.fromisoformat(marker_value["issuedAt"].replace("Z", "+00:00"))
        marker = control.stage3_validate_authorization_value(raw, now=issued)
        proposal = self._proposal
        arm = proposal["arm"]
        arm_issued = datetime.fromisoformat(arm["issuedAt"].replace("Z", "+00:00"))
        expected = control.stage3_arm_proposal(
            marker, proposal["challenge"], proposal["assertion"],
            now=arm_issued, nonce=arm["armNonce"])
        if phase == "INITIAL":
            moment = datetime.now(timezone.utc)
            expiry = (proposal["challenge"]["expiresAt"], arm["expiresAt"],
                      marker["expiresAt"])
            require(all(moment < datetime.fromisoformat(
                value.replace("Z", "+00:00")) for value in expiry),
                "STAGE3_ADAPTER_INITIAL_EXPIRED")
        require(proposal == expected and
                marker["authorizationId"] == intent["authorizationId"] ==
                    proposal["authorizationId"] and
                marker["instrumentedReleaseId"] == intent["candidateRelease"] ==
                    control.STAGE3_RELEASE and
                intent["acceptedSnapshotSha256"] == control.STAGE3_ACCEPTED_SNAPSHOT_SHA and
                intent["candidateManifestSha256"] == control.STAGE3_MANIFEST_SHA and
                digest(self._frame) == self._frame_sha and
                exact_confirm_frame(proposal) == self._frame and
                os.readlink(control.ROOT / "current") ==
                    f"releases/{control.STAGE3_RELEASE}",
                "STAGE3_ADAPTER_BINDING_DRIFT")
        liveness.verify(liveness.Paths(vault=transition.VAULT),
                        marker["authorizationId"])
        control.assert_unit_state(socket_active=True, service_active=True)
        observed = control.show(control.SERVICE, "InvocationID", "MainPID")
        require(observed.get("InvocationID") and
                int(observed.get("MainPID", "0")) > 1 and
                ((phase == "INITIAL" and
                  observed["InvocationID"] == candidate["invocationId"]) or
                 (phase != "INITIAL" and
                  observed["InvocationID"] != candidate["invocationId"])),
                "STAGE3_ADAPTER_INVOCATION")
        if phase == "INITIAL":
            parent = control.STAGE3_ARM.parent.lstat()
            require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == 0 and
                    parent.st_gid == 987 and stat.S_IMODE(parent.st_mode) == 0o750 and
                    digest(transition.regular(control.STAGE3_ARM, uid=0, gid=987,
                                              mode=0o640)) == proposal["armSha256"],
                    "STAGE3_ADAPTER_ARM_CUSTODY")
        else:
            require(not os.path.lexists(control.STAGE3_ARM),
                    "STAGE3_ADAPTER_ARM_REMAINS")
        self._db_state("PREPARED" if phase == "INITIAL" else "CONSUMED")
        return {"authorizationId": marker["authorizationId"],
                "challengeId": proposal["challenge"]["challengeId"],
                "frameSha256": self._frame_sha,
                "candidateInvocationId": candidate["invocationId"],
                "observedInvocationId": observed["InvocationID"]}

    @staticmethod
    def _receipt(name: str, expected: dict) -> None:
        value = json.loads(transition.regular(
            transition.VAULT / name, uid=0, gid=0, mode=0o600))
        require(value == expected, "STAGE3_ADAPTER_RECEIPT_DRIFT")

    @staticmethod
    def _run_child(user: str, source: str, payload: bytes) -> dict:
        require((user, source) in (("lilith-memory-relay", RELAY_SENDER_SOURCE),
                                   ("lilith-memory-broker", RECOVERY_SOURCE)),
                "STAGE3_ADAPTER_CHILD_SCOPE")
        args = ["/usr/sbin/runuser", "-u", user, "--", "/usr/bin/env",
                "LILITH_ENV=dev", "PYTHONDONTWRITEBYTECODE=1",
                "PYTHONNOUSERSITE=1", str(control.ROOT / "current/venv/bin/python"),
                "-B", "-c", source]
        result = subprocess.run(
            args, cwd=control.ROOT / "current", input=payload,
            capture_output=True, timeout=15,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C",
                 "HOME": "/nonexistent"})
        require(result.returncode == 0 and result.stderr == b"" and
                0 < len(result.stdout) <= 512,
                "STAGE3_ADAPTER_CHILD_FAILED")
        try:
            return json.loads(result.stdout)
        except (ValueError, UnicodeError) as exc:
            raise AdapterError("STAGE3_ADAPTER_CHILD_RESPONSE") from exc

    def _one_shot(self, name: str, binding: dict, operation) -> dict:
        require(name in ("initial-submit", "recovery", "replay-submit"),
                "STAGE3_ADAPTER_ACTION_SCOPE")
        vault = transition.VAULT
        attempt = vault / (name + "-attempt.json")
        result_path = vault / (name + "-result.json")
        require(not os.path.lexists(attempt) and not os.path.lexists(result_path),
                "STAGE3_ADAPTER_ALREADY_ATTEMPTED")
        transition.exclusive(attempt, canonical({"schema": "Stage3A2AdapterAttemptV1",
                                                 "action": name, **binding}))
        result = operation()
        transition.exclusive(result_path, canonical({
            "schema": "Stage3A2AdapterResultV1", "action": name,
            "challengeId": binding["challengeId"],
            "frameSha256": binding["frameSha256"],
            "observedInvocationId": binding["observedInvocationId"],
            "result": result}))
        return result

    @staticmethod
    def _guarded(operation, reason: str) -> dict:
        try:
            return operation()
        except BaseException:
            transition.contain_failure(transition.Journal(transition.VAULT),
                                       liveness.Paths(vault=transition.VAULT),
                                       reason)
            raise

    def _send(self, phase: str) -> dict:
        binding = self._binding(phase)
        if phase == "REPLAY":
            self._receipt("recovery-result.json", {
                "schema": "Stage3A2AdapterResultV1", "action": "recovery",
                "challengeId": binding["challengeId"],
                "frameSha256": binding["frameSha256"],
                "observedInvocationId": binding["observedInvocationId"],
                "result": {"status": "PROOF_BURNED_NO_CLAIM",
                           "challengeId": binding["challengeId"]}})
        else:
            require(phase == "INITIAL", "STAGE3_ADAPTER_SEND_PHASE")
        name = "initial-submit" if phase == "INITIAL" else "replay-submit"

        def operation() -> dict:
            meta = canonical({"phase": phase,
                              "challengeId": binding["challengeId"],
                              "frameSha256": self._frame_sha})
            result = self._run_child("lilith-memory-relay", RELAY_SENDER_SOURCE,
                                     meta + self._frame)
            require(result == {"status": "FRAME_SENT" if phase == "INITIAL"
                                      else "NO_RESPONSE",
                               "frameSha256": self._frame_sha},
                    "STAGE3_ADAPTER_RELAY_RESULT")
            if phase == "REPLAY":
                self._db_state("CONSUMED")
                require(control.relay("health").get("status") == "HEALTH_OK",
                        "STAGE3_ADAPTER_REPLAY_HEALTH")
            return result

        return self._one_shot(name, binding, operation)

    def submit_initial_once(self) -> dict:
        return self._guarded(lambda: self._send("INITIAL"),
                             "ADAPTER_INITIAL_REVIEW_REQUIRED")

    def _recover_once(self) -> dict:
        binding = self._binding("RECOVERY")
        self._receipt("initial-submit-result.json", {
            "schema": "Stage3A2AdapterResultV1", "action": "initial-submit",
            "challengeId": binding["challengeId"],
            "frameSha256": binding["frameSha256"],
            "observedInvocationId": binding["candidateInvocationId"],
            "result": {"status": "FRAME_SENT",
                       "frameSha256": binding["frameSha256"]}})

        def operation() -> dict:
            result = self._run_child(
                "lilith-memory-broker", RECOVERY_SOURCE,
                canonical({"challengeId": binding["challengeId"]}))
            require(result == {"status": "PROOF_BURNED_NO_CLAIM",
                               "challengeId": binding["challengeId"]},
                    "STAGE3_ADAPTER_RECOVERY_RESULT")
            self._db_state("CONSUMED")
            return result

        return self._one_shot("recovery", binding, operation)

    def recover_once(self) -> dict:
        return self._guarded(self._recover_once,
                             "ADAPTER_RECOVERY_REVIEW_REQUIRED")

    def replay_exact_once(self) -> dict:
        return self._guarded(lambda: self._send("REPLAY"),
                             "ADAPTER_REPLAY_REVIEW_REQUIRED")
