"""15B2b-B1b-3d L1 authority-signer source foundation tests (repository only).

Every key here is an in-process TEST-only Ed25519 key taken from the existing
B1b-3a TEST fixture (`services/owner-memory-control/tests/synthetic_authority.py`).
No key is generated, persisted, or packaged. Nothing contacts DEV or PROD.

Live OS properties (caller denial, credential delivery, unit sandboxing) are
NOT_YET_LIVE_PROVEN; these tests only check the source that later live gates
will exercise.
"""

from __future__ import annotations

import configparser
import copy
import os
import pickle
import socket
import struct
import sys
import tempfile
import unittest
from pathlib import Path

import rfc8785

ROOT = Path(__file__).resolve().parents[3]
SERVICE = ROOT / "services/authority-dev"
for path in (ROOT / "services/core-api", ROOT / "services/owner-memory-control",
             ROOT / "services/owner-memory-control/tests", SERVICE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from cryptography.hazmat.primitives.serialization import (  # noqa: E402
    BestAvailableEncryption, Encoding, NoEncryption, PrivateFormat,
)
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey  # noqa: E402

import release_file_set as RFS  # noqa: E402
import synthetic_authority as SA  # noqa: E402
import synthetic_b1b3b as T  # noqa: E402
from lilith_authority_dev import core as CORE  # noqa: E402
from lilith_authority_dev import credential as CRED  # noqa: E402
from lilith_authority_dev import evidence_minter as M  # noqa: E402
from lilith_authority_dev import profile as PR  # noqa: E402
from lilith_authority_dev import protocol as W  # noqa: E402
from lilith_authority_dev import server as S  # noqa: E402
from lilith_memory import canonical_contracts as C  # noqa: E402
from lilith_owner_memory import authority_contracts as A  # noqa: E402

KEY_ID = PR.PROPOSED_K_ACT_KEY_ID
SEED = "dev.actor.current-1"  # existing TEST-only seed name; never packaged


def dev_key_record_dict(**overrides):
    value = SA.key_record(KEY_ID, seed_name=SEED, environment="dev", createdAt="2026-09-26T00:00:00Z",
                          notBefore="2026-09-26T00:00:00Z", registryVersion=3)
    value.update(overrides)
    return value


def dev_registry(**key_overrides):
    return SA.registry("dev-root", keys=[dev_key_record_dict(**key_overrides)], environment="dev",
                       registryRootKeyId=SA.DEV_ROOT_KEY_ID)


def profile(**overrides):
    value = dict(environment="dev", key_id=KEY_ID, authority_domain=SA.LOGICAL_AUTHORITY_DOMAIN,
                 logical_owner_id=SA.LOGICAL_OWNER, policy_version=SA.POLICY)
    value.update(overrides)
    return PR.DevSyntheticSignerProfileV1(**value)


def minter(**key_overrides):
    return M.OwnerActorEvidenceMinterV1(
        signing_key=SA.private(SEED), profile=profile(),
        key_record=A.AuthorityKeyRecordV1.from_dict(dev_key_record_dict(**key_overrides)))


def unsigned(**overrides):
    value = SA.owner_evidence_unsigned(environment="dev", keyId=KEY_ID)
    value.update(overrides)
    return value


def frame(value) -> bytes:
    raw = rfc8785.dumps(value)
    return struct.pack(">I", len(raw)) + raw


def envelope(operation, payload, **overrides):
    value = {"protocol": W.PROTOCOL, "schemaVersion": W.VERSION, "operation": operation, "payload": payload}
    value.update(overrides)
    return value


ACTION = C.FrozenMemoryActionV1(
    schema_version=1, actor_ref_id="actor.synthetic.b1b3d-l1", operation=C.CREATE,
    memory_class="SYNTHETIC_TEST_CLASS", subject_namespace="synthetic.b1b3d", subject_key="subject-1",
    value_schema="synthetic.value.v1", payload_digest=SA._digest("b1b3d l1 payload"),
    expected_active_revision_id=None, restore_revision_id=None, purpose=C.LONG_TERM_PERSONAL_PROJECT_RECALL)


def issue_payload(**overrides):
    proof = T.owner_proof(ACTION, "och.b1b3d-l1")
    value = {
        "challengeId": proof.challenge["challengeId"],
        "action": proof.action.semantic_dict(),
        "assertion": dict(proof.assertion),
        "ownerCredential": dict(proof.credential),
    }
    value.update(overrides)
    return value


PRESENT = CRED.CredentialStatusV1(CRED.CREDENTIAL_PRESENT_UNVERIFIED, "0" * 64)
ABSENT = CRED.CredentialStatusV1(CRED.CREDENTIAL_ABSENT)
INVALID = CRED.CredentialStatusV1(CRED.CREDENTIAL_INVALID)


class CredentialAbsenceTests(unittest.TestCase):
    """Req 1, 7-state: no credential, no signing; absence != signer failure."""

    def test_unset_directory_is_absent(self):
        self.assertEqual(CRED.inspect_owner_actor_credential(None).state, CRED.CREDENTIAL_ABSENT)
        self.assertEqual(CRED.inspect_owner_actor_credential("").state, CRED.CREDENTIAL_ABSENT)

    def test_missing_file_is_absent_and_nothing_is_created(self):
        with tempfile.TemporaryDirectory() as directory:
            status = CRED.inspect_owner_actor_credential(directory, expected_directory=directory)
            self.assertEqual(status, ABSENT)
            self.assertEqual(os.listdir(directory), [])  # no key fabricated or written

    def test_foreign_directory_is_invalid_not_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(CRED.inspect_owner_actor_credential(directory).state, CRED.CREDENTIAL_INVALID)

    def _with_credential(self, data: bytes) -> CRED.CredentialStatusV1:
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, PR.CREDENTIAL_NAME).write_bytes(data)
            return CRED.inspect_owner_actor_credential(directory, expected_directory=directory)

    def test_malformed_and_wrong_type_credentials_are_invalid(self):
        # Wrong algorithm, from an existing TEST-only seed (no key generation).
        ec = X25519PrivateKey.from_private_bytes(SA.SEEDS["attacker"]).private_bytes(
            Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
        encrypted = SA.private(SEED).private_bytes(Encoding.DER, PrivateFormat.PKCS8,
                                                   BestAvailableEncryption(b"test-only-passphrase"))
        for data in (b"", b"\x00" * 48, b"not der", ec, encrypted, b"\x30" * 1024,
                     SA.private(SEED).private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())):
            self.assertEqual(self._with_credential(data), INVALID)

    def test_present_credential_yields_public_facts_only(self):
        der = SA.private(SEED).private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
        status = self._with_credential(der)
        self.assertEqual(status.state, CRED.CREDENTIAL_PRESENT_UNVERIFIED)
        self.assertRegex(status.public_key_sha256, r"^[0-9a-f]{64}$")
        self.assertEqual(set(vars(status)), {"state", "public_key_sha256"})

    def test_symlinked_credential_is_refused(self):
        if not hasattr(os, "symlink") or os.name == "nt":
            self.skipTest("symlink semantics are Linux-specific")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory, "elsewhere")
            target.write_bytes(SA.private(SEED).private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption()))
            os.symlink(target, Path(directory, PR.CREDENTIAL_NAME))
            self.assertEqual(CRED.inspect_owner_actor_credential(directory, expected_directory=directory), INVALID)

    def test_main_exits_distinctly_without_serving(self):
        served = []
        original = (S.check_environment, S.check_identity, S.serve_forever, S.inspect_owner_actor_credential,
                    S._process_identity)
        try:
            S._process_identity = lambda: (990, 980, [980])
            S.check_environment = lambda environ: None
            S.check_identity = lambda *a, **k: None
            S.serve_forever = served.append
            for status, code in ((ABSENT, S.EXIT_CREDENTIAL_ABSENT), (INVALID, S.EXIT_CREDENTIAL_INVALID)):
                S.inspect_owner_actor_credential = lambda _d, status=status: status
                self.assertEqual(S.main(), code)
            self.assertNotEqual(S.EXIT_CREDENTIAL_ABSENT, S.EXIT_STARTUP_REFUSED)
            self.assertEqual(served, [])
        finally:
            (S.check_environment, S.check_identity, S.serve_forever, S.inspect_owner_actor_credential,
             S._process_identity) = original


class ReadinessTests(unittest.TestCase):
    """Req 1, 7: health never claims authority readiness; signing always refused in L1."""

    def test_health_is_never_ready(self):
        for status in (ABSENT, INVALID, PRESENT):
            health = CORE.DevAuthoritySignerCoreV1(status).health()
            self.assertEqual(health["service"], CORE.SERVICE_AVAILABLE)
            self.assertEqual(health["signing"], CORE.SIGNING_NOT_AVAILABLE)
            self.assertEqual(health["readiness"], CORE.NOT_READY)
            self.assertTrue(health["reasons"])
            self.assertEqual(health["credential"], status.state)
            self.assertNotIn("RESTORE_READY", repr(health))
        self.assertEqual(CORE.DevAuthoritySignerCoreV1(ABSENT).health()["reasons"][0], CRED.CREDENTIAL_ABSENT)
        self.assertEqual(CORE.DevAuthoritySignerCoreV1(PRESENT).health()["reasons"],
                         list(CORE.L1_ABSENT_COMPONENTS))

    def test_issue_is_refused_in_every_credential_state(self):
        message = W.parse_frame(frame(envelope(W.ISSUE_OWNER_EVIDENCE, issue_payload())))
        for status in (ABSENT, INVALID, PRESENT):
            result = CORE.DevAuthoritySignerCoreV1(status).dispatch(message)
            self.assertEqual((result["status"], result["reason"]), (CORE.REFUSED, CORE.SIGNING_NOT_AVAILABLE))
            self.assertNotIn("evidence", result)
            self.assertNotIn("signature", repr(result))

    def test_core_holds_no_key_or_minter(self):
        core = CORE.DevAuthoritySignerCoreV1(PRESENT)
        self.assertEqual(set(vars(core)), {"_credential"})
        source = (SERVICE / "lilith_authority_dev/core.py").read_text(encoding="utf-8")
        server = (SERVICE / "lilith_authority_dev/server.py").read_text(encoding="utf-8")
        for text in (source, server):
            self.assertNotIn("evidence_minter", text)
            self.assertNotIn("OwnerActorEvidenceMinterV1", text)
            self.assertNotIn("load_der_private_key", text)


class ProtocolTests(unittest.TestCase):
    """Req 3, 6, 7, 8, 9: closed protocol; no arbitrary signing; canonical bytes only."""

    def assertRefused(self, raw: bytes, code: str):
        with self.assertRaises(W.ProtocolError) as caught:
            W.parse_frame(raw)
        self.assertEqual(caught.exception.code, code)

    def test_only_health_and_structured_issue_exist(self):
        self.assertEqual(W.OPERATIONS, frozenset({"HEALTH", "ISSUE_OWNER_EVIDENCE"}))
        for operation in ("SIGN", "SIGN_BYTES", "SIGN_MESSAGE", "SIGN_DIGEST", "SIGN_PRIVACY", "RAW",
                          "EXPORT_KEY", "GET_KEY", "PREPARE", "CONSUME", "ADVANCE_EPOCH", "RECONCILE_DECISION"):
            self.assertRefused(frame(envelope(operation, {})), "UNSUPPORTED_OPERATION")

    def test_issue_payload_cannot_carry_signed_values(self):
        for extra in ("message", "bytes", "digest", "signingBytes", "signingDomain", "domainSeparator",
                      "keyId", "registryVersion", "recoveryEpoch", "policyVersion", "evidence", "requestDigest"):
            payload = issue_payload(**{extra: "x"})
            self.assertRefused(frame(envelope(W.ISSUE_OWNER_EVIDENCE, payload)), "INVALID_PAYLOAD_FIELDS")
        self.assertRefused(frame(envelope(W.HEALTH, {"message": "x"})), "INVALID_PAYLOAD_FIELDS")

    def test_privacy_operation_is_refused(self):
        payload = issue_payload()
        payload["action"] = dict(payload["action"], operation=C.FORGET, valueSchema=None,
                                 expectedActiveRevisionId=None, restoreRevisionId=None)
        self.assertRefused(frame(envelope(W.ISSUE_OWNER_EVIDENCE, payload)), "PRIVACY_OWNED_OPERATION")

    def test_malformed_requests_fail_closed(self):
        good = issue_payload()
        cases = {
            "INVALID_CHALLENGE_ID": dict(good, challengeId="x" * 10),
            "INVALID_ACTION": dict(good, action={"operation": "CREATE"}),
            "INVALID_ASSERTION": dict(good, assertion={"signature": "x"}),
            "INVALID_OWNER_CREDENTIAL": dict(good, ownerCredential={}),
        }
        for code, payload in cases.items():
            self.assertRefused(frame(envelope(W.ISSUE_OWNER_EVIDENCE, payload)), code)
        self.assertRefused(b"", "TRUNCATED_FRAME")
        self.assertRefused(struct.pack(">I", 0), "INVALID_FRAME_LENGTH")
        self.assertRefused(struct.pack(">I", W.MAX_FRAME_BYTES + 1) + b"x", "INVALID_FRAME_LENGTH")
        self.assertRefused(struct.pack(">I", 5) + b"{}", "FRAME_LENGTH_MISMATCH")
        self.assertRefused(struct.pack(">I", 3) + b"\xff\xfe{", "INVALID_JSON")
        dup = b'{"operation":"HEALTH","operation":"HEALTH","payload":{},"protocol":"LILITH_AUTHORITY_DEV","schemaVersion":1}'
        self.assertRefused(struct.pack(">I", len(dup)) + dup, "DUPLICATE_FIELD")
        nan = b'{"operation":"HEALTH","payload":{},"protocol":"LILITH_AUTHORITY_DEV","schemaVersion":NaN}'
        self.assertRefused(struct.pack(">I", len(nan)) + nan, "INVALID_JSON_CONSTANT")
        self.assertRefused(frame({"protocol": W.PROTOCOL}), "INVALID_ENVELOPE")
        self.assertRefused(frame(envelope(W.HEALTH, [])), "INVALID_PAYLOAD")

    def test_unsupported_schema_or_protocol_fails_closed(self):
        for overrides in ({"schemaVersion": 2}, {"schemaVersion": 0}, {"schemaVersion": True},
                          {"protocol": "LILITH_MEMORY_BROKER"}, {"protocol": "LILITH_AUTHORITY_PROD"}):
            self.assertRefused(frame(envelope(W.HEALTH, {}, **overrides)), "UNSUPPORTED_VERSION")

    def test_noncanonical_bytes_are_refused(self):
        raw = b'{"protocol":"LILITH_AUTHORITY_DEV","schemaVersion":1,"operation":"HEALTH","payload":{}}'
        self.assertRefused(struct.pack(">I", len(raw)) + raw, "NONCANONICAL_JSON")
        spaced = rfc8785.dumps(envelope(W.HEALTH, {})).replace(b":", b": ")
        self.assertRefused(struct.pack(">I", len(spaced)) + spaced, "NONCANONICAL_JSON")
        self.assertEqual(W.parse_frame(W.encode_frame(W.HEALTH, {})).operation, W.HEALTH)


class MinterTests(unittest.TestCase):
    """Req 4, 5, 6, 8, 9, 10: only structured OwnerEvidenceV2 under OWNER_ACTOR is signable."""

    def test_minted_evidence_verifies_under_the_accepted_b1b3a_verifier(self):
        evidence = minter().mint(unsigned())
        result = SA.verify_owner(evidence, ctx=SA.dev_context(), reg=dev_registry())
        self.assertEqual(result.status, "VERIFIED_AUTHORITY_EVIDENCE", result.reason)
        self.assertEqual(evidence["signingDomain"], A.OWNER_ACTOR)
        # Exactly the accepted signing bytes: the same key signing them directly
        # gives the same (deterministic Ed25519) signature.
        self.assertEqual(evidence, SA.sign_owner(unsigned(), SEED))

    def test_no_raw_signing_surface(self):
        public = {name for name in dir(M.OwnerActorEvidenceMinterV1) if not name.startswith("_")}
        self.assertEqual(public, {"mint", "key_id"})
        m = minter()
        signing_bytes = A.owner_evidence_signing_bytes(unsigned())
        for value in (signing_bytes, signing_bytes.decode("latin-1"), bytearray(signing_bytes), None, 7, ["x"]):
            with self.assertRaises(M.MintRefused) as caught:
                m.mint(value)
            self.assertEqual(caught.exception.reason, "MINT_REQUEST_NOT_STRUCTURED")

    def test_signing_domain_is_owner_actor_only(self):
        with self.assertRaises(M.MintRefused) as caught:
            minter().mint(unsigned(signingDomain=A.PRIVACY))
        self.assertEqual(caught.exception.reason, "SIGNING_DOMAIN_REFUSED")

    def test_privacy_authorization_is_not_signable(self):
        m = minter()
        for value in (SA.privacy_unsigned(), SA.privacy_unsigned(environment="dev", keyId=KEY_ID)):
            with self.assertRaises(M.MintRefused) as caught:
                m.mint(value)
            self.assertEqual(caught.exception.reason, "MINT_FIELDS_MISMATCH")
        with self.assertRaises(M.MintRefused) as caught:
            m.mint(unsigned(evidenceType=A.PRIVACY_ERASURE_AUTHORIZATION))
        self.assertEqual(caught.exception.reason, "EVIDENCE_TYPE_REFUSED")

    def test_privacy_key_record_is_refused_at_construction(self):
        record = dev_key_record_dict(signingDomain=A.PRIVACY, evidenceTypes=[A.PRIVACY_ERASURE_AUTHORIZATION])
        with self.assertRaises(M.MinterConfigurationError):
            M.OwnerActorEvidenceMinterV1(signing_key=SA.private(SEED), profile=profile(),
                                         key_record=A.AuthorityKeyRecordV1.from_dict(record))

    def test_required_identifiers_cannot_be_omitted(self):
        for field in ("keyId", "registryVersion", "recoveryEpoch", "policyVersion", "signingDomain",
                      "evidenceType", "environment", "challengeId", "evidenceNonce", "authorityDomain"):
            value = unsigned()
            del value[field]
            with self.assertRaises(M.MintRefused) as caught:
                minter().mint(value)
            self.assertEqual(caught.exception.reason, "MINT_FIELDS_MISMATCH", field)
        with self.assertRaises(M.MintRefused) as caught:
            minter().mint({**unsigned(), "signature": "A" * 86})
        self.assertEqual(caught.exception.reason, "MINT_FIELDS_MISMATCH")

    def test_malformed_and_unsupported_schema_evidence_is_refused(self):
        for overrides in ({"schemaVersion": 1}, {"schemaVersion": 3}, {"protocol": "LILITH_ACTOR_EVIDENCE_V1"},
                          {"registryVersion": 0}, {"registryVersion": "3"}, {"keyId": ""},
                          {"challengeDigest": "abc"}, {"issuedAt": "yesterday"},
                          {"recoveryEpoch": {"counter": 2}}, {"authorityDomain": A.OWNER_ACTOR}):
            with self.assertRaises(M.MintRefused) as caught:
                minter().mint(unsigned(**overrides))
            self.assertEqual(caught.exception.reason, "MINT_EVIDENCE_MALFORMED", overrides)

    def test_binding_guards(self):
        other_epoch = A.RecoveryEpochV1(3, "a" * 32).to_dict()
        cases = {
            "ENVIRONMENT_REFUSED": unsigned(environment="prod"),
            "KEY_ID_MISMATCH": unsigned(keyId="test-only.dev-synthetic.actor.other"),
            "PROFILE_BINDING_MISMATCH": unsigned(policyVersion="policy.other.v1"),
            "EVIDENCE_NONCE_MISMATCH": unsigned(evidenceNonce="och.other"),
            "RECOVERY_EPOCH_MISMATCH": unsigned(recoveryEpoch=other_epoch),
            "REGISTRY_VERSION_BELOW_KEY": unsigned(registryVersion=2),
            "ISSUED_BEFORE_KEY_VALIDITY": unsigned(issuedAt="2026-09-25T23:59:59Z"),
        }
        for reason, value in cases.items():
            with self.assertRaises(M.MintRefused) as caught:
                minter().mint(value)
            self.assertEqual(caught.exception.reason, reason)
        # key.registryVersion <= evidence.registryVersion stays open upwards;
        # the upper bound (<= verified registry) is the verifier's, unchanged.
        ahead = minter().mint(unsigned(registryVersion=4))
        result = SA.verify_owner(ahead, ctx=SA.dev_context(), reg=dev_registry())
        self.assertEqual(result.status, "NOT_ACCEPTED")

    def test_construction_envelope(self):
        bad_profiles = (profile(environment="prod"), profile(environment="test"),
                        profile(key_id="actor.current-2"), profile(key_id="test-only.actor.1"),
                        profile(authority_domain=A.OWNER_ACTOR), profile(logical_owner_id="nobody"))
        record = A.AuthorityKeyRecordV1.from_dict(dev_key_record_dict())
        for bad in bad_profiles:
            with self.assertRaises(M.MinterConfigurationError):
                M.OwnerActorEvidenceMinterV1(signing_key=SA.private(SEED), profile=bad, key_record=record)
        bad_records = (
            dev_key_record_dict(publicKey=SA.public_b64("attacker")),
            dev_key_record_dict(environment="test"),
            dev_key_record_dict(retiredAt="2026-09-26T06:00:00Z"),
            dev_key_record_dict(policyVersion="policy.other.v1"),
        )
        for raw in bad_records:
            with self.assertRaises(M.MinterConfigurationError):
                M.OwnerActorEvidenceMinterV1(signing_key=SA.private(SEED), profile=profile(),
                                             key_record=A.AuthorityKeyRecordV1.from_dict(raw))
        with self.assertRaises(M.MinterConfigurationError):
            M.OwnerActorEvidenceMinterV1(signing_key=b"\x00" * 32, profile=profile(), key_record=record)

    def test_minter_hygiene(self):
        m = minter()
        self.assertNotIn("private", repr(m).lower())
        for action in (pickle.dumps, copy.copy, copy.deepcopy):
            with self.assertRaises(TypeError):
                action(m)
        self.assertFalse(hasattr(m, "signing_key"))
        self.assertFalse(hasattr(m, "private_key"))
        self.assertNotIn("public_key", dir(m))


class ServerTests(unittest.TestCase):
    """Root-only peer, one frame, no bind. Live SO_PEERCRED denial is NOT_YET_LIVE_PROVEN."""

    def _pair(self):
        if not hasattr(socket, "socketpair") or not hasattr(socket, "AF_UNIX"):
            self.skipTest("AF_UNIX socketpair unavailable")
        return socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)

    def _exchange(self, peer_uid, raw):
        server, client = self._pair()
        with client:
            client.sendall(raw)
            client.shutdown(socket.SHUT_WR)
            S.serve_connection(server, CORE.DevAuthoritySignerCoreV1(PRESENT),
                               peer_uid_reader=lambda _c: peer_uid)
            try:
                return client.recv(W.MAX_FRAME_BYTES + 8)
            except ConnectionResetError:  # closed with the request unread: nothing returned
                return b""

    def test_non_root_peers_receive_nothing(self):
        for uid in (1001, 999, 997, 3826947836, -1, "0", None):
            self.assertEqual(self._exchange(uid, W.encode_frame(W.HEALTH, {})), b"")

    def test_root_peer_gets_not_ready_health(self):
        reply = self._exchange(0, W.encode_frame(W.HEALTH, {}))
        self.assertIn(b'"readiness":"NOT_READY"', reply)
        self.assertIn(b'"signing":"SIGNING_NOT_AVAILABLE"', reply)

    def test_malformed_frame_gets_nothing(self):
        self.assertEqual(self._exchange(0, frame(envelope("SIGN", {"message": "x"}))), b"")

    def test_no_bind_or_listen_in_runtime(self):
        text = (SERVICE / "lilith_authority_dev/server.py").read_text(encoding="utf-8")
        self.assertNotIn(".bind(", text)
        self.assertNotIn(".listen(", text)
        self.assertNotIn("AF_INET", text)
        self.assertEqual(S.AUTHORIZED_PEER_UID, 0)

    def test_inherited_listener_is_required(self):
        saved = {key: os.environ.pop(key, None) for key in ("LISTEN_PID", "LISTEN_FDS")}
        try:
            with self.assertRaises(S.ServerError):
                S.inherited_listener()
        finally:
            for key, value in saved.items():
                if value is not None:
                    os.environ[key] = value

    def test_environment_checks(self):
        S.check_environment({"LILITH_ENV": "dev"})
        for environ in ({}, {"LILITH_ENV": "prod"}, {"LILITH_ENV": "test"},
                        {"LILITH_ENV": "dev", "PYTHONPATH": "/tmp"},
                        {"LILITH_ENV": "dev", "LILITH_ACTOR_KEY_PATH": "/x"},
                        {"LILITH_ENV": "dev", "LILITH_OWNER_ACTOR_SIGNING_KEY": "AAAA"},
                        {"LILITH_ENV": "dev", "LILITH_COGNITIVE_DB_PATH": "/x"}):
            with self.assertRaises(S.ServerError):
                S.check_environment(environ)

    def test_identity_checks(self):
        users = {"lilith-authority-dev": (990, 980), "lilith": (1001, 1002), "lilith-memory-broker": (999, 987)}
        groups = {"lilith-authority-dev": 980}

        def check(uid, gid, extra=(), users=users):
            S.check_identity(uid, gid, [gid, *extra], user_lookup=users.get, group_lookup=groups.get)

        check(990, 980)
        for args in ((0, 0), (1001, 1002), (999, 987), (990, 1002), (990, 980, (988,)), (990, 980, (1002,))):
            with self.assertRaises(S.ServerError):
                check(*args)
        with self.assertRaises(S.ServerError):
            check(990, 980, users={**users, "lilith": (990, 980)})
        with self.assertRaises(S.ServerError):
            check(990, 980, users={"lilith": (1001, 1002)})


def _unit(path: Path) -> dict[str, list[tuple[str, str]]]:
    sections: dict[str, list[tuple[str, str]]] = {}
    current = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            current = line.strip("[]")
            sections[current] = []
            continue
        key, _, value = line.partition("=")
        sections[current].append((key, value))
    return sections


def _values(section, key):
    return [value for name, value in section if name == key]


class UnitMaterialTests(unittest.TestCase):
    """Req 12, 13: dedicated identity; credential never an application path."""

    service = _unit(SERVICE / "deploy/lilith-authority-dev.service")["Service"]
    socket_unit = _unit(SERVICE / "deploy/lilith-authority-dev.socket")

    def one(self, key):
        values = _values(self.service, key)
        self.assertEqual(len(values), 1, key)
        return values[0]

    def test_dedicated_identity(self):
        self.assertEqual(self.one("User"), PR.SERVICE_USER)
        self.assertEqual(self.one("Group"), PR.SERVICE_GROUP)
        for key in ("SupplementaryGroups", "DynamicUser", "PermissionsStartOnly", "ExecStartPre",
                    "ExecStartPost", "ExecReload", "BindPaths", "BindReadOnlyPaths", "EnvironmentFile",
                    "SetCredential", "LoadCredential", "ImportCredential", "PassEnvironment"):
            self.assertEqual(_values(self.service, key), [], key)
        self.assertEqual(self.one("ExecStart"),
                         "/opt/lilith-authority-dev/current/venv/bin/python -B -m lilith_authority_dev.server")

    def test_credential_delivery_and_isolation(self):
        self.assertEqual(self.one("LoadCredentialEncrypted"),
                         f"{PR.CREDENTIAL_NAME}:{PR.CREDENTIAL_SOURCE}")
        inaccessible = self.one("InaccessiblePaths").split()
        for path in ("/etc/credstore.encrypted", "/etc/lilith-memory-broker",
                     "/var/lib/lilith-memory-broker", "/etc/lilith-os-dev"):
            self.assertIn(path, inaccessible)
        self.assertEqual(self.one("ReadOnlyPaths").split(),
                         ["/opt/lilith-authority-dev", "/etc/lilith-authority-dev", "/var/lib/lilith-recovery-witness"])
        self.assertEqual(self.one("ReadWritePaths"), PR.STATE_DIR)
        self.assertEqual(sorted(_values(self.service, "Environment")),
                         ["LILITH_ENV=dev", "PYTHONDONTWRITEBYTECODE=1", "PYTHONNOUSERSITE=1"])

    def test_hardening(self):
        expected = {
            "NoNewPrivileges": "yes", "ProtectSystem": "strict", "ProtectHome": "yes", "PrivateTmp": "yes",
            "PrivateDevices": "yes", "CapabilityBoundingSet": "", "AmbientCapabilities": "",
            "RestrictAddressFamilies": "AF_UNIX", "IPAddressDeny": "any", "UMask": "0077",
            "StateDirectory": "lilith-authority-dev", "StateDirectoryMode": "0700",
        }
        for key, value in expected.items():
            self.assertEqual(self.one(key), value, key)

    def test_socket_is_root_only_and_not_installable(self):
        sock = self.socket_unit["Socket"]
        self.assertEqual(_values(sock, "ListenStream"), [PR.OWNER_SOCKET_PATH])
        self.assertEqual(_values(sock, "SocketUser"), ["root"])
        self.assertEqual(_values(sock, "SocketGroup"), ["root"])
        self.assertEqual(_values(sock, "SocketMode"), ["0600"])
        self.assertEqual(_values(sock, "DirectoryMode"), ["0700"])
        self.assertEqual(_values(sock, "Accept"), ["no"])
        self.assertEqual(_values(sock, "RemoveOnStop"), ["yes"])
        self.assertEqual(_values(sock, "Service"), [PR.SERVICE_UNIT])
        self.assertNotIn("Install", self.socket_unit)  # T-5: never enabled at boot by this material
        self.assertNotIn("Install", _unit(SERVICE / "deploy/lilith-authority-dev.service"))
        self.assertEqual((SERVICE / "deploy/lilith-authority-dev.tmpfiles.conf").read_text(encoding="utf-8"),
                         "d /run/lilith-authority-dev 0700 root root -\n")

    def test_application_and_deployer_paths_never_name_custody(self):
        needles = ("credstore", "owner-actor-signing-key", "lilith-authority-dev", "lilith_authority_dev",
                   "CREDENTIALS_DIRECTORY")
        roots = [ROOT / "services/core-api", ROOT / "services/memory-broker", ROOT / "scripts/dev_deployer"]
        files = [path for base in roots for path in base.rglob("*")
                 if path.is_file() and "__pycache__" not in path.parts and ".venv" not in path.parts
                 and path.name != "needrestart-lilith-authority-sensitive.conf"]
        files += [ROOT / ".github/workflows/deploy.yml", ROOT / ".github/workflows/deploy-dev.yml",
                  ROOT / "scripts/build_core_api_bundle.py", ROOT / "scripts/deploy_core_api_remote.sh"]
        for path in files:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for needle in needles:
                self.assertNotIn(needle, text, f"{path.relative_to(ROOT)} names {needle}")

    def test_runtime_reads_private_material_only_from_the_unit_credentials_directory(self):
        self.assertEqual(PR.CREDENTIALS_DIRECTORY, "/run/credentials/lilith-authority-dev.service")
        for name in RFS.RUNTIME_MODULES:
            text = (SERVICE / "lilith_authority_dev" / name).read_text(encoding="utf-8")
            if name != "profile.py":
                self.assertNotIn("/etc/credstore", text, name)
            self.assertNotRegex(text, r'environ(\.get\(|\[)"LILITH_(?!ENV")', name)
            self.assertNotIn("sqlite", text, name)
        self.assertNotIn("load_der_private_key",
                         "".join((SERVICE / "lilith_authority_dev" / n).read_text(encoding="utf-8")
                                 for n in RFS.RUNTIME_MODULES if n != "credential.py"))


class PackagingTests(unittest.TestCase):
    """Req 2, 11, 14: approved file set only; no private or TEST key material in runtime."""

    def test_source_tree_is_exact(self):
        RFS.check_source_tree(ROOT)

    def test_runtime_payload_is_exact_and_clean(self):
        payloads = RFS.runtime_payloads(ROOT)
        self.assertEqual(set(payloads), set(RFS.RUNTIME_SOURCE_MAP.values()))
        for name in payloads:
            self.assertFalse(name.startswith("tests/") or "/tests/" in name or name.endswith("release_file_set.py"))
            self.assertNotIn("lilith_authority_signer", name)
            self.assertNotIn("synthetic", name)
        seeds = [value for value in SA.SEEDS.values()] + [SA.TEST_ONLY_CONTAINMENT_KEY]
        for data in payloads.values():
            for seed in seeds:
                self.assertNotIn(seed, data)
                self.assertNotIn(SA.b64(seed).encode(), data)
                self.assertNotIn(seed.hex().encode(), data)
        manifest = RFS.runtime_manifest(ROOT)
        self.assertEqual(manifest["status"], "SOURCE_FOUNDATION_NOT_INSTALLED")

    def test_extra_file_and_forbidden_markers_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in set(RFS.SOURCE_FILES) | set(RFS.SHARED_HASHES):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / relative).read_bytes())
            RFS.runtime_payloads(root)
            extra = root / RFS.RUNTIME_PACKAGE / "test_key.py"
            extra.write_text("x = 1\n", encoding="utf-8")
            with self.assertRaises(RFS.FileSetError):
                RFS.runtime_payloads(root)
            extra.unlink()
            core = root / RFS.RUNTIME_PACKAGE / "core.py"
            original = core.read_bytes()
            for marker in (b"-----" + b"BEGIN " + b"PRIVATE" + b" KEY-----", b"Ed25519PrivateKey.generate()",
                           b"from_private_bytes", b"import lilith_authority_signer", b"TEST_ONLY seed"):
                core.write_bytes(original + b"\n# " + marker + b"\n")
                with self.assertRaises(RFS.FileSetError):
                    RFS.runtime_payloads(root)
            core.write_bytes(original)
            shared = root / "services/owner-memory-control/lilith_owner_memory/authority_contracts.py"
            shared.write_bytes(shared.read_bytes() + b"\n")
            with self.assertRaises(RFS.FileSetError):
                RFS.runtime_payloads(root)

    def test_no_private_key_markers_anywhere_in_the_service_tree(self):
        for relative in RFS.SOURCE_FILES:
            data = (ROOT / relative).read_bytes()
            for marker in (b"-----" + b"BEGIN", b"PRIVATE" + b" KEY-----", b"OPENSSH" + b" PRIVATE"):
                self.assertNotIn(marker, data, relative)

    def test_signer_package_does_not_import_the_test_signer(self):
        for name in RFS.RUNTIME_MODULES:
            text = (SERVICE / "lilith_authority_dev" / name).read_text(encoding="utf-8")
            self.assertNotIn("lilith_authority_signer", text)
            self.assertNotIn("authority_verifier", text)
            self.assertNotIn("import synthetic", text)


if __name__ == "__main__":
    unittest.main()
