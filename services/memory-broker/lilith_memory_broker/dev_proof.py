"""Broker-local, synthetic-DEV-only B1a verification boundary.

The decisive verification/consumption sequence mirrors the governed B1a
verifier.  Its different entry guard is deliberately confined to this module:
the Core API's test-only ``.invalid`` RP guard is never changed or bypassed.
No result from this module is ActorEvidence or a live owner authority token.
"""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import datetime, timezone
from typing import Callable

import rfc8785
from lilith_memory import owner_proof as P
from lilith_memory.canonical_contracts import FrozenMemoryActionV1

from .request import SYNTHETIC_ACCESS_IDENTITY


class DevSyntheticProofVerifier:
    """Exact synthetic RP with a DEV-only guard independent of B1a test mode."""

    def __init__(self, store: P.DurableOwnerChallengeStore, *, now_fn: Callable[[], datetime] | None = None):
        if os.environ.get("LILITH_ENV") != "dev":
            raise P.OwnerProofError("DEV_SYNTHETIC_ENV_REQUIRED")
        self.store = store
        self.owner_principal = SYNTHETIC_ACCESS_IDENTITY
        self.rp_id = P.SYNTHETIC_RP_ID
        self.origin = P.SYNTHETIC_ORIGIN
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))

    def verify_and_consume(
        self, challenge_id: str, assertion: P.OwnerAssertionV1, *,
        expected_action: FrozenMemoryActionV1,
        expected_request_digest: str,
        expected_memory_item_id: str | None,
        expected_restore_target_digest: str | None,
        expected_privacy_notice_version: str,
    ) -> P.OwnerProofVerificationResultV1:
        if os.environ.get("LILITH_ENV") != "dev":
            raise P.OwnerProofError("DEV_SYNTHETIC_ENV_REQUIRED")
        P._id(challenge_id, "challenge_id")
        assertion.validate()
        expected_action.validate()
        P._digest(expected_request_digest, "request_digest")
        conn = self.store._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT challenge_json,state FROM owner_proof_challenge_v1 WHERE challenge_id=?", (challenge_id,)).fetchone()
            if row is None:
                raise P.OwnerProofError("UNKNOWN_CHALLENGE")
            if row[1] != "PREPARED":
                raise P.OwnerProofError("CHALLENGE_NOT_PREPARED")
            raw = bytes(row[0])
            challenge_data = P._json_object(raw, allowed=P._CHALLENGE_FIELDS)
            challenge = P.OwnerMemoryChallengeV1.from_dict(challenge_data)
            if raw != challenge.canonical_bytes():
                raise P.OwnerProofError("NONCANONICAL_STORED_CHALLENGE")
            now = self._trusted_now()
            if now >= P._instant(challenge.expires_at):
                conn.execute("UPDATE owner_proof_challenge_v1 SET state='EXPIRED' WHERE challenge_id=? AND state='PREPARED'", (challenge_id,))
                conn.commit()
                raise P.OwnerProofError("CHALLENGE_EXPIRED")
            if now < P._instant(challenge.issued_at):
                raise P.OwnerProofError("CHALLENGE_NOT_YET_VALID")
            if (
                challenge.challenge_id != challenge_id
                or challenge.owner_principal != self.owner_principal
                or challenge.rp_id != self.rp_id
                or challenge.action_digest != expected_action.action_digest
                or challenge.request_digest != expected_request_digest
                or challenge.payload_digest != expected_action.payload_digest
                or challenge.operation != expected_action.operation
                or challenge.memory_class != expected_action.memory_class
                or challenge.subject_namespace != expected_action.subject_namespace
                or challenge.subject_key != expected_action.subject_key
                or challenge.purpose != expected_action.purpose
                or challenge.expected_active_revision_id != expected_action.expected_active_revision_id
                or challenge.restore_target_revision_id != expected_action.restore_revision_id
                or challenge.memory_item_id != expected_memory_item_id
                or challenge.restore_target_digest != expected_restore_target_digest
                or challenge.privacy_notice_version != expected_privacy_notice_version
            ):
                raise P.OwnerProofError("ACTION_BINDING_MISMATCH")
            credential_row = conn.execute("SELECT credential_json FROM owner_proof_test_credential_v1 WHERE record_id=?", (assertion.credential_record_id,)).fetchone()
            if credential_row is None:
                raise P.OwnerProofError("UNKNOWN_CREDENTIAL")
            credential_bytes = bytes(credential_row[0])
            credential_data = P._json_object(credential_bytes, allowed=P._CREDENTIAL_FIELDS)
            credential = P.OwnerCredentialV1.from_dict(credential_data)
            if credential_bytes != rfc8785.dumps(credential.to_dict()):
                raise P.OwnerProofError("NONCANONICAL_CREDENTIAL")
            if credential.status != "ACTIVE" or credential.owner_principal != self.owner_principal or credential.rp_id != self.rp_id:
                raise P.OwnerProofError("CREDENTIAL_NOT_AUTHORIZED")
            if assertion.credential_record_id != credential.record_id or assertion.credential_id != credential.credential_id:
                raise P.OwnerProofError("CREDENTIAL_MISMATCH")
            client_raw = P._b64u_decode(assertion.client_data_json, "client_data", 1, 2048)
            client_fields = P._json_object(client_raw, allowed=frozenset({"type", "challenge", "origin", "crossOrigin"}))
            if set(client_fields) not in ({"type", "challenge", "origin"}, {"type", "challenge", "origin", "crossOrigin"}) or client_fields.get("crossOrigin", False) is not False:
                raise P.OwnerProofError("INVALID_CLIENT_DATA")
            auth_raw = P._b64u_decode(assertion.authenticator_data, "authenticator_data", 37, 1024)
            signature = P._b64u_decode(assertion.signature, "signature", 1, 512)
            cose_raw = P._b64u_decode(credential.public_key_cose, "public_key", 16, 2048)
            try:
                cose_map, rest = P.cbor.decode_from(cose_raw)
                if rest or not isinstance(cose_map, dict) or cose_map.get(3) != -7:
                    raise ValueError("unsupported COSE key")
                cose_key = P.CoseKey.parse(cose_map)
                public_credential = P.AttestedCredentialData.create(b"\x00" * 16, P._b64u_decode(credential.credential_id, "credential_id", 16, 1024), cose_key)
                response = P.AuthenticationResponse(
                    raw_id=public_credential.credential_id,
                    response=P.AuthenticatorAssertionResponse(
                        client_data=P.CollectedClientData(client_raw),
                        authenticator_data=P.AuthenticatorData(auth_raw),
                        signature=signature,
                    ),
                )
                server = P.Fido2Server(P.PublicKeyCredentialRpEntity(name="LILITH owner proof", id=self.rp_id), verify_origin=lambda value: value == self.origin)
                _, state = server.authenticate_begin([public_credential], user_verification=P.UserVerificationRequirement.REQUIRED, challenge=challenge.webauthn_challenge())
                server.authenticate_complete(state, [public_credential], response)
                observed = response.response.authenticator_data.counter
            except (ValueError, TypeError, KeyError, IndexError, OverflowError) as exc:
                raise P.OwnerProofError("INVALID_WEBAUTHN_ASSERTION") from exc
            now = self._trusted_now()
            if now >= P._instant(challenge.expires_at):
                conn.execute("UPDATE owner_proof_challenge_v1 SET state='EXPIRED' WHERE challenge_id=? AND state='PREPARED'", (challenge_id,))
                conn.commit()
                raise P.OwnerProofError("CHALLENGE_EXPIRED")
            if now < P._instant(challenge.issued_at):
                raise P.OwnerProofError("CHALLENGE_NOT_YET_VALID")
            consumed_at = now.isoformat(timespec="seconds").replace("+00:00", "Z")
            changed = conn.execute("UPDATE owner_proof_challenge_v1 SET state='CONSUMED',consumed_credential_record_id=?,consumed_at=? WHERE challenge_id=? AND state='PREPARED'", (credential.record_id, consumed_at, challenge_id)).rowcount
            if changed != 1:
                raise P.OwnerProofError("REPLAY")
            counter_risk = observed > 0 and credential.last_observed_sign_count > 0 and observed <= credential.last_observed_sign_count
            if observed > credential.last_observed_sign_count:
                updated = replace(credential, last_observed_sign_count=observed)
                conn.execute("UPDATE owner_proof_test_credential_v1 SET credential_json=? WHERE record_id=?", (rfc8785.dumps(updated.to_dict()), credential.record_id))
            conn.commit()
            return P.OwnerProofVerificationResultV1(
                challenge_id, credential.record_id, self.owner_principal,
                challenge.action_digest, challenge.request_digest, observed, counter_risk,
            )
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _trusted_now(self) -> datetime:
        now = self.now_fn()
        if now.tzinfo is None or now.utcoffset() != timezone.utc.utcoffset(now):
            raise P.OwnerProofError("INVALID_NOW")
        return now
