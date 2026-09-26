"""15B2b-B1b-3a authority evidence and key registry contracts: golden vectors,
signing-domain separation (distinct from the logical authorityDomain),
retirement vs compromise, environment/domain/epoch rules, registry evolution
and downgrade, full negative matrix, B2a/V1 immutability, isolation
(TEST_ONLY)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import inspect
import json
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import synthetic_authority as S
from lilith_memory import owner_proof as P
from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import authority_verifier as V
from lilith_owner_memory import contracts as K
from lilith_owner_memory import verifier as B2A

GOLDEN = json.loads(S.GOLDEN_PATH.read_text(encoding="utf-8"))
B2A_GOLDEN = Path(__file__).with_name("owner_memory_b2a_golden.json")
OTHER = "f" * 64


def unsigned(artifact: dict) -> dict:
    return {k: v for k, v in artifact.items() if k != "signature"}


def tampered(artifact: dict, **fields) -> dict:
    """Change signed fields WITHOUT re-signing."""
    return {**artifact, **fields}


def flip_signature(artifact: dict) -> dict:
    raw = bytearray(P._b64u_decode(artifact["signature"], "signature", 64, 64))
    raw[0] ^= 0x01
    return {**artifact, "signature": S.b64(bytes(raw))}


def resign_registry(**overrides) -> dict:
    return S.registry(**overrides)


def keys_with(key_id: str, **overrides) -> list:
    return [({**k, **overrides} if k["keyId"] == key_id else k) for k in S.default_keys()]


def reg_result(**kwargs):
    ctx = kwargs.pop("ctx", None) or S.context()
    reg = kwargs.pop("reg")
    return V.verify_authority_registry(context=ctx, registry=reg)


def containment_signed_owner() -> dict:
    """An Ed25519 key derived from containment PRF bytes claims an Actor key."""
    rogue = Ed25519PrivateKey.from_private_bytes(S.TEST_ONLY_CONTAINMENT_KEY)
    body = S.owner_evidence_unsigned()
    return {**body, "signature": S.b64(rogue.sign(A.owner_evidence_signing_bytes(body)))}


def containment_hmac_owner() -> dict:
    """The containment key used as an HMAC 'signature' (32-byte tag)."""
    body = S.owner_evidence_unsigned()
    tag = hmac.new(S.TEST_ONLY_CONTAINMENT_KEY, A.owner_evidence_signing_bytes(body), hashlib.sha256).digest()
    return {**body, "signature": S.b64(tag)}


def prod_registry(keys=None) -> dict:
    keys = keys if keys is not None else [S.key_record("actor.current-2", environment="prod",
                                                       createdAt="2026-09-26T00:00:00Z",
                                                       notBefore="2026-09-26T00:00:00Z", registryVersion=3)]
    return S.registry(keys=keys, environment="prod")


def prod_context(**overrides):
    return S.context(environment="prod", registry_root=S.trusted_root(environment="prod"), **overrides)


# (name, callable returning a result, expected NOT_ACCEPTED reason)
CASES = [
    # Trusted context
    ("context-not-a-context", lambda: S.verify_owner(ctx={"environment": "test"}), "MALFORMED_CONTEXT"),
    ("context-unknown-purpose", lambda: S.verify_owner(ctx=S.context(purpose="ANY")), "MALFORMED_CONTEXT"),
    ("context-bool-trusted-version", lambda: S.verify_owner(ctx=S.context(trusted_minimum_registry_version=True)), "MALFORMED_CONTEXT"),
    ("expectation-not-typed", lambda: S.verify_owner(expectation={"evidence_id": "aev.synthetic-create"}), "MALFORMED_CONTEXT"),
    ("registry-root-not-test-only", lambda: S.verify_owner(ctx=S.context(registry_root=S.trusted_root(key_id="owner.registry-root-1"))), "REGISTRY_ROOT_NOT_TEST_ONLY"),
    # Registry presence, form, and signature
    ("registry-missing", lambda: reg_result(reg=None), "REGISTRY_MISSING"),
    ("registry-not-a-mapping", lambda: reg_result(reg=[S.registry()]), "REGISTRY_MALFORMED"),
    ("registry-unsigned", lambda: reg_result(reg=S.registry_unsigned()), "REGISTRY_UNSIGNED"),
    ("registry-null-signature", lambda: reg_result(reg={**S.registry(), "signature": None}), "REGISTRY_UNSIGNED"),
    ("registry-extra-field", lambda: reg_result(reg={**S.registry(), "acceptedBy": "lilith"}), "REGISTRY_MALFORMED"),
    ("registry-malformed-signature", lambda: reg_result(reg={**S.registry(), "signature": "AAAA"}), "REGISTRY_MALFORMED"),
    ("registry-wrong-signer", lambda: reg_result(reg=S.registry(signer="attacker-root")), "REGISTRY_SIGNATURE_INVALID"),
    ("registry-signed-by-authority-key", lambda: reg_result(reg=S.registry(signer="actor.current-2")), "REGISTRY_SIGNATURE_INVALID"),
    ("registry-root-id-substituted", lambda: reg_result(reg=S.registry(signer="attacker-root", registryRootKeyId="test-only.attacker")), "REGISTRY_ROOT_MISMATCH"),
    ("registry-mutated-key-set", lambda: reg_result(reg=tampered(S.registry(), keys=S.default_keys()[:-1])), "REGISTRY_SIGNATURE_INVALID"),
    ("registry-signature-mutated", lambda: reg_result(reg=flip_signature(S.registry())), "REGISTRY_SIGNATURE_INVALID"),
    ("registry-unsupported-schema", lambda: reg_result(reg=S.registry(schemaVersion=2)), "UNSUPPORTED_SCHEMA_VERSION"),
    ("registry-other-protocol", lambda: reg_result(reg=S.registry(protocol="LILITH_ACTIVATION_GRANT")), "UNSUPPORTED_SCHEMA_VERSION"),
    ("registry-malformed-issued-at", lambda: reg_result(reg=S.registry(issuedAt="2026-09-26 06:00:00")), "REGISTRY_MALFORMED"),
    ("registry-bool-version", lambda: reg_result(reg=S.registry(registryVersion=True)), "REGISTRY_MALFORMED"),
    # Key records inside a validly signed registry
    ("key-wrong-algorithm", lambda: reg_result(reg=S.registry(keys=keys_with("actor.current-2", algorithm="Ed448"))), "KEY_ALGORITHM_UNSUPPORTED"),
    ("key-hmac-algorithm", lambda: reg_result(reg=S.registry(keys=keys_with("actor.current-2", algorithm="HMAC-SHA256"))), "KEY_ALGORITHM_UNSUPPORTED"),
    ("key-unsupported-schema", lambda: reg_result(reg=S.registry(keys=keys_with("actor.current-2", schemaVersion=2))), "UNSUPPORTED_SCHEMA_VERSION"),
    ("key-malformed-public-key", lambda: reg_result(reg=S.registry(keys=keys_with("actor.current-2", publicKey=S.b64(b"\x01" * 31)))), "KEY_RECORD_INVALID"),
    ("key-containment-domain", lambda: reg_result(reg=S.registry(keys=keys_with("actor.current-2", signingDomain="CONTAINMENT"))), "KEY_RECORD_INVALID"),
    ("key-cross-domain-evidence-type", lambda: reg_result(reg=S.registry(keys=keys_with("actor.current-2", evidenceTypes=["OWNER_MEMORY_OPERATION", "PRIVACY_ERASURE_AUTHORIZATION"]))), "KEY_RECORD_INVALID"),
    ("key-record-carries-logical-authority-domain", lambda: reg_result(reg=S.registry(keys=keys_with("actor.current-2", authorityDomain=S.LOGICAL_AUTHORITY_DOMAIN))), "REGISTRY_MALFORMED"),
    ("key-record-legacy-authority-domain-field", lambda: reg_result(reg=S.registry(keys=[({**{k: v for k, v in r.items() if k != "signingDomain"}, "authorityDomain": r["signingDomain"]} if r["keyId"] == "actor.current-2" else r) for r in S.default_keys()])), "REGISTRY_MALFORMED"),
    ("key-empty-evidence-types", lambda: reg_result(reg=S.registry(keys=keys_with("actor.current-2", evidenceTypes=[]))), "KEY_RECORD_INVALID"),
    ("key-actor-key-reused-as-privacy", lambda: reg_result(reg=S.registry(keys=keys_with("privacy.current-1", publicKey=S.public_b64("actor.current-2")))), "KEY_RECORD_INVALID"),
    ("key-registry-root-as-authority-key", lambda: reg_result(reg=S.registry(keys=keys_with("actor.current-2", publicKey=S.public_b64("root")))), "KEY_RECORD_INVALID"),
    ("key-duplicate-key-id", lambda: reg_result(reg=S.registry(keys=S.default_keys() + [S.key_record("privacy.current-1", seed_name="attacker")])), "KEY_RECORD_INVALID"),
    ("key-unsorted", lambda: reg_result(reg=S.registry(keys=list(reversed(S.default_keys())))), "KEY_RECORD_INVALID"),
    ("key-future-registry-version", lambda: reg_result(reg=S.registry(keys=keys_with("actor.current-2", registryVersion=4))), "KEY_RECORD_INVALID"),
    ("key-current-in-stale-epoch", lambda: reg_result(reg=S.registry(keys=keys_with("actor.epoch1-1", retiredAt=None))), "KEY_RECORD_INVALID"),
    ("key-forked-epoch", lambda: reg_result(reg=S.registry(keys=keys_with("actor.current-2", recoveryEpoch=S.FORK_EPOCH.to_dict()))), "KEY_RECORD_INVALID"),
    ("key-current-stale-policy", lambda: reg_result(reg=S.registry(keys=keys_with("actor.current-2", policyVersion="policy.synthetic.v1"))), "KEY_RECORD_INVALID"),
    ("key-future-dated", lambda: reg_result(reg=S.registry(keys=keys_with("actor.current-2", createdAt="2026-09-27T00:00:00Z", notBefore="2026-09-27T00:00:00Z"))), "KEY_RECORD_INVALID"),
    ("key-not-before-precedes-creation", lambda: reg_result(reg=S.registry(keys=keys_with("actor.current-2", notBefore="2026-09-25T00:00:00Z"))), "KEY_RECORD_INVALID"),
    ("key-compromise-without-since", lambda: reg_result(reg=S.registry(keys=keys_with("actor.compromised-1", compromisedSince=None))), "KEY_RECORD_INVALID"),
    ("key-compromised-since-after-revocation", lambda: reg_result(reg=S.registry(keys=keys_with("actor.compromised-1", compromisedSince="2026-09-25T06:00:00Z"))), "KEY_RECORD_INVALID"),
    ("key-revocation-without-reason", lambda: reg_result(reg=S.registry(keys=keys_with("actor.revoked-1", revocationReason=None))), "KEY_RECORD_INVALID"),
    ("key-malformed-timestamp", lambda: reg_result(reg=S.registry(keys=keys_with("actor.current-2", notBefore="2026-09-26"))), "REGISTRY_MALFORMED"),
    ("key-dev-record-in-test-registry", lambda: reg_result(reg=S.registry(keys=keys_with("actor.current-2", environment="dev"))), "KEY_ENVIRONMENT_MISMATCH"),
    ("key-dev-record-in-prod-registry", lambda: reg_result(ctx=prod_context(), reg=prod_registry([S.key_record("actor.current-2", environment="dev", createdAt="2026-09-26T00:00:00Z", notBefore="2026-09-26T00:00:00Z", registryVersion=3)])), "KEY_ENVIRONMENT_MISMATCH"),
    # Registry binding to trusted context
    ("registry-dev-in-test-context", lambda: reg_result(reg=S.registry(environment="dev", keys=[S.key_record("actor.current-2", environment="dev", createdAt="2026-09-26T00:00:00Z", notBefore="2026-09-26T00:00:00Z", registryVersion=3)])), "REGISTRY_ENVIRONMENT_MISMATCH"),
    ("registry-root-for-other-environment", lambda: reg_result(ctx=S.context(registry_root=S.trusted_root(environment="dev")), reg=S.registry()), "REGISTRY_ENVIRONMENT_MISMATCH"),
    ("registry-prod-in-dev-context", lambda: reg_result(ctx=S.context(environment="dev", registry_root=S.trusted_root(environment="dev")), reg=prod_registry()), "REGISTRY_ENVIRONMENT_MISMATCH"),
    ("registry-downgrade", lambda: reg_result(reg=S.registry(registryVersion=2, keys=[k for k in S.default_keys() if k["keyId"] != "actor.current-2"])), "REGISTRY_DOWNGRADE"),
    ("registry-stale-version-vs-trusted-higher", lambda: reg_result(ctx=S.context(trusted_minimum_registry_version=7), reg=S.registry()), "REGISTRY_DOWNGRADE"),
    ("registry-old-epoch-context", lambda: reg_result(ctx=S.context(expected_recovery_epoch=S.OLD_EPOCH), reg=S.registry()), "REGISTRY_EPOCH_MISMATCH"),
    ("registry-forked-epoch-context", lambda: reg_result(ctx=S.context(expected_recovery_epoch=S.FORK_EPOCH), reg=S.registry()), "REGISTRY_EPOCH_MISMATCH"),
    ("registry-policy-mismatch", lambda: reg_result(ctx=S.context(policy_version="policy.synthetic.v3"), reg=S.registry()), "REGISTRY_POLICY_MISMATCH"),
    # Owner evidence form
    ("evidence-missing", lambda: V.verify_owner_evidence(context=S.context(), registry=S.registry(), evidence=None, expectation=S.owner_expectation()), "EVIDENCE_MISSING"),
    ("evidence-extra-field", lambda: S.verify_owner({**S.owner_evidence(), "acceptanceStatus": "ACCEPTED"}), "EVIDENCE_MALFORMED"),
    ("evidence-missing-field", lambda: S.verify_owner({k: v for k, v in S.owner_evidence().items() if k != "challengeDigest"}), "EVIDENCE_MALFORMED"),
    ("evidence-unsupported-schema", lambda: S.verify_owner(S.owner_evidence(schemaVersion=3)), "UNSUPPORTED_SCHEMA_VERSION"),
    ("evidence-b2a-envelope-not-promoted", lambda: S.verify_owner(json.loads(Path(__file__).with_name("owner_memory_b2a_golden.json").read_text(encoding="utf-8"))["evidenceV1"][0]["envelope"]), "EVIDENCE_MALFORMED"),
    ("evidence-malformed-signature", lambda: S.verify_owner({**S.owner_evidence(), "signature": "AAAA"}), "EVIDENCE_MALFORMED"),
    ("evidence-malformed-timestamp", lambda: S.verify_owner(S.owner_evidence(issuedAt="2026-09-26T12:00:21.000Z")), "EVIDENCE_MALFORMED"),
    ("evidence-malformed-epoch", lambda: S.verify_owner(S.owner_evidence(recoveryEpoch={"counter": -1, "random": S.EPOCH.random})), "EVIDENCE_MALFORMED"),
    ("evidence-epoch-without-random", lambda: S.verify_owner(S.owner_evidence(recoveryEpoch={"counter": 2})), "EVIDENCE_MALFORMED"),
    ("evidence-string-registry-version", lambda: S.verify_owner(S.owner_evidence(registryVersion="3")), "EVIDENCE_MALFORMED"),
    ("evidence-malformed-digest", lambda: S.verify_owner(S.owner_evidence(actionDigest="ABC")), "EVIDENCE_MALFORMED"),
    ("privacy-artifact-as-owner-evidence", lambda: S.verify_owner(S.privacy_authorization()), "EVIDENCE_MALFORMED"),
    # Domain, type, environment, key
    ("evidence-claims-privacy-signing-domain", lambda: S.verify_owner(S.owner_evidence(signingDomain="PRIVACY")), "SIGNING_DOMAIN_MISMATCH"),
    ("signing-domain-value-as-logical-context", lambda: S.verify_owner(S.owner_evidence(authorityDomain="OWNER_ACTOR")), "EVIDENCE_MALFORMED"),
    ("logical-context-as-signing-domain", lambda: S.verify_owner(S.owner_evidence(signingDomain=S.LOGICAL_AUTHORITY_DOMAIN)), "EVIDENCE_MALFORMED"),
    ("evidence-wrong-evidence-type", lambda: S.verify_owner(S.owner_evidence(evidenceType="PRIVACY_ERASURE_AUTHORIZATION")), "EVIDENCE_TYPE_MISMATCH"),
    ("evidence-wrong-environment", lambda: S.verify_owner(S.owner_evidence(environment="prod")), "ENVIRONMENT_MISMATCH"),
    ("cross-environment-replay-test-into-dev", lambda: S.verify_owner(ctx=S.dev_context(), reg=S.dev_registry()), "ENVIRONMENT_MISMATCH"),
    ("dev-key-evidence-in-prod-context", lambda: S.verify_owner(S.owner_evidence(signer="dev.actor.current-1", environment="dev"), ctx=prod_context(), reg=prod_registry()), "ENVIRONMENT_MISMATCH"),
    ("prod-key-evidence-in-dev-context", lambda: S.verify_owner(S.owner_evidence(environment="prod"), ctx=S.dev_context(), reg=S.dev_registry()), "ENVIRONMENT_MISMATCH"),
    ("relabelled-environment-replay", lambda: S.verify_owner(tampered(S.owner_evidence(), environment="dev"), ctx=S.dev_context(), reg=S.dev_registry()), "SIGNATURE_INVALID"),
    ("unknown-key", lambda: S.verify_owner(S.owner_evidence(signer="attacker", keyId="actor.attacker-1")), "KEY_UNKNOWN"),
    ("containment-key-id-unknown", lambda: S.verify_owner(S.owner_evidence(signer="attacker", keyId="containment.legacy-1")), "KEY_UNKNOWN"),
    ("privacy-key-signs-actor-evidence", lambda: S.verify_owner(S.owner_evidence(signer="privacy.current-1", keyId="privacy.current-1")), "KEY_SIGNING_DOMAIN_MISMATCH"),
    ("actor-key-signs-privacy-typed", lambda: S.verify_privacy(S.privacy_authorization(signer="actor.current-2", keyId="actor.current-2")), "KEY_SIGNING_DOMAIN_MISMATCH"),
    ("privacy-key-claims-actor-key-id", lambda: S.verify_owner(S.owner_evidence(signer="privacy.current-1")), "SIGNATURE_INVALID"),
    ("containment-derived-ed25519-signs-actor", lambda: S.verify_owner(containment_signed_owner()), "SIGNATURE_INVALID"),
    ("containment-hmac-tag-as-signature", lambda: S.verify_owner(containment_hmac_owner()), "EVIDENCE_MALFORMED"),
    ("attacker-signs-with-real-key-id", lambda: S.verify_owner(S.owner_evidence(signer="attacker")), "SIGNATURE_INVALID"),
    ("signature-mutation", lambda: S.verify_owner(flip_signature(S.owner_evidence())), "SIGNATURE_INVALID"),
    ("signature-right-length-garbage", lambda: S.verify_owner({**S.owner_evidence(), "signature": S.b64(b"\x00" * 64)}), "SIGNATURE_INVALID"),
    ("owner-signature-under-privacy-separator", lambda: S.verify_owner({**S.owner_evidence_unsigned(), "signature": S.b64(S.private("actor.current-2").sign(A.PRIVACY_AUTHORIZATION_DOMAIN_SEPARATOR + K._canonical(S.owner_evidence_unsigned())))}), "SIGNATURE_INVALID"),
    ("payload-digest-mutation-unsigned", lambda: S.verify_owner(tampered(S.owner_evidence(), payloadDigest=OTHER)), "SIGNATURE_INVALID"),
    ("action-digest-mutation-unsigned", lambda: S.verify_owner(tampered(S.owner_evidence(), actionDigest=OTHER)), "SIGNATURE_INVALID"),
    ("evidence-id-substitution-unsigned", lambda: S.verify_owner(tampered(S.owner_evidence(), evidenceId="aev.other")), "SIGNATURE_INVALID"),
    ("nonce-substitution-unsigned", lambda: S.verify_owner(tampered(S.owner_evidence(), evidenceNonce="och.other")), "SIGNATURE_INVALID"),
    ("challenge-reference-substitution-unsigned", lambda: S.verify_owner(tampered(S.owner_evidence(), challengeDigest=OTHER)), "SIGNATURE_INVALID"),
    # Compromise
    ("compromised-key-after-compromise", lambda: S.verify_owner(S.owner_evidence(keyId="actor.compromised-1", registryVersion=2, issuedAt="2026-09-24T12:00:00Z"), ctx=S.historical_context()), "KEY_COMPROMISED"),
    ("compromised-key-backdated", lambda: S.verify_owner(S.owner_evidence(keyId="actor.compromised-1", registryVersion=2, issuedAt="2026-09-11T00:00:00Z"), ctx=S.historical_context()), "KEY_COMPROMISED"),
    ("compromised-key-new-admission", lambda: S.verify_owner(S.owner_evidence(keyId="actor.compromised-1")), "KEY_COMPROMISED"),
    # Epoch, registry version, policy
    ("wrong-recovery-epoch-forked", lambda: S.verify_owner(S.owner_evidence(recoveryEpoch=S.FORK_EPOCH.to_dict())), "RECOVERY_EPOCH_MISMATCH"),
    ("wrong-recovery-epoch-old-new-admission", lambda: S.verify_owner(S.owner_evidence(keyId="actor.epoch1-1", registryVersion=1, recoveryEpoch=S.OLD_EPOCH.to_dict(), issuedAt="2026-09-05T12:00:00Z")), "RECOVERY_EPOCH_MISMATCH"),
    ("old-epoch-evidence-relabelled-current-epoch", lambda: S.verify_owner(S.owner_evidence(keyId="actor.epoch1-1", registryVersion=1, issuedAt="2026-09-05T12:00:00Z"), ctx=S.historical_context()), "RECOVERY_EPOCH_MISMATCH"),
    ("evidence-version-before-key-publication", lambda: S.verify_owner(S.owner_evidence(registryVersion=2)), "REGISTRY_VERSION_MISMATCH"),
    ("wrong-registry-version-future", lambda: S.verify_owner(S.owner_evidence(registryVersion=4)), "REGISTRY_VERSION_MISMATCH"),
    ("evidence-version-beyond-verified-registry", lambda: S.verify_owner(S.owner_evidence(keyId="actor.retired-1", registryVersion=4, issuedAt="2026-09-20T12:00:00Z")), "REGISTRY_VERSION_MISMATCH"),
    ("wrong-policy-version", lambda: S.verify_owner(S.owner_evidence(policyVersion="policy.synthetic.v1")), "POLICY_VERSION_MISMATCH"),
    # Validity interval, retirement, routine revocation
    ("evidence-before-not-before", lambda: S.verify_owner(S.owner_evidence(issuedAt="2026-09-25T23:59:59Z")), "KEY_NOT_YET_VALID"),
    ("retired-key-historical-before-not-before", lambda: S.verify_owner(S.owner_evidence(keyId="actor.retired-1", registryVersion=2, issuedAt="2026-09-05T00:00:00Z"), ctx=S.historical_context()), "KEY_NOT_YET_VALID"),
    ("retired-key-new-evidence-historical", lambda: S.verify_owner(S.owner_evidence(keyId="actor.retired-1", registryVersion=2, issuedAt="2026-09-26T00:00:00Z"), ctx=S.historical_context()), "KEY_RETIRED"),
    ("retired-key-new-admission", lambda: S.verify_owner(S.owner_evidence(keyId="actor.retired-1", issuedAt="2026-09-26T00:00:00Z")), "KEY_RETIRED"),
    ("revoked-key-after-revocation", lambda: S.verify_owner(S.owner_evidence(keyId="actor.revoked-1", registryVersion=2, issuedAt="2026-09-21T00:00:00Z"), ctx=S.historical_context()), "KEY_REVOKED"),
    ("revoked-key-new-admission", lambda: S.verify_owner(S.owner_evidence(keyId="actor.revoked-1", issuedAt="2026-09-21T00:00:00Z")), "KEY_REVOKED"),
    # Binding to the independently verified expectation
    ("logical-owner-mismatch", lambda: S.verify_owner(S.owner_evidence(logicalOwnerId="owner.other.v1")), "LOGICAL_OWNER_MISMATCH"),
    ("logical-authority-domain-mismatch", lambda: S.verify_owner(S.owner_evidence(authorityDomain="authority.synthetic.other")), "AUTHORITY_DOMAIN_MISMATCH"),
    ("logical-authority-domain-expectation-mismatch", lambda: S.verify_owner(expectation=S.owner_expectation(authority_domain="authority.synthetic.other")), "AUTHORITY_DOMAIN_MISMATCH"),
    ("evidence-id-substitution", lambda: S.verify_owner(S.owner_evidence(evidenceId="aev.synthetic-other")), "EVIDENCE_ID_MISMATCH"),
    ("nonce-substitution", lambda: S.verify_owner(S.owner_evidence(evidenceNonce="och.synthetic-other")), "EVIDENCE_NONCE_MISMATCH"),
    ("challenge-id-substitution", lambda: S.verify_owner(S.owner_evidence(challengeId="och.synthetic-other", evidenceNonce="och.synthetic-other")), "CHALLENGE_REFERENCE_MISMATCH"),
    ("challenge-digest-substitution", lambda: S.verify_owner(S.owner_evidence(challengeDigest=OTHER)), "CHALLENGE_REFERENCE_MISMATCH"),
    ("assertion-digest-substitution", lambda: S.verify_owner(S.owner_evidence(assertionDigest=OTHER)), "OWNER_PROOF_REFERENCE_MISMATCH"),
    ("credential-record-substitution", lambda: S.verify_owner(S.owner_evidence(credentialRecordId="ocred.other")), "OWNER_PROOF_REFERENCE_MISMATCH"),
    ("request-digest-substitution", lambda: S.verify_owner(S.owner_evidence(requestDigest=OTHER)), "REQUEST_DIGEST_MISMATCH"),
    ("action-digest-mutation", lambda: S.verify_owner(S.owner_evidence(actionDigest=OTHER)), "ACTION_DIGEST_MISMATCH"),
    ("payload-digest-mutation", lambda: S.verify_owner(S.owner_evidence(payloadDigest=OTHER)), "PAYLOAD_DIGEST_MISMATCH"),
    # Privacy authorization
    ("privacy-missing", lambda: V.verify_privacy_authorization(context=S.context(), registry=S.registry(), authorization=None, expectation=S.privacy_expectation()), "EVIDENCE_MISSING"),
    ("owner-artifact-as-privacy", lambda: S.verify_privacy(S.owner_evidence()), "EVIDENCE_MALFORMED"),
    ("privacy-unsorted-resource-owners", lambda: S.verify_privacy(S.privacy_authorization(resourceOwners=["PRIVACY", "L04"])), "EVIDENCE_MALFORMED"),
    ("privacy-unsupported-schema", lambda: S.verify_privacy(S.privacy_authorization(schemaVersion=1)), "UNSUPPORTED_SCHEMA_VERSION"),
    ("privacy-claims-actor-signing-domain", lambda: S.verify_privacy(S.privacy_authorization(signingDomain="OWNER_ACTOR")), "SIGNING_DOMAIN_MISMATCH"),
    ("privacy-wrong-evidence-type", lambda: S.verify_privacy(S.privacy_authorization(evidenceType="OWNER_MEMORY_OPERATION")), "EVIDENCE_TYPE_MISMATCH"),
    ("privacy-signature-under-owner-separator", lambda: S.verify_privacy({**S.privacy_unsigned(), "signature": S.b64(S.private("privacy.current-1").sign(A.OWNER_EVIDENCE_DOMAIN_SEPARATOR + K._canonical(S.privacy_unsigned())))}), "SIGNATURE_INVALID"),
    ("privacy-hold-mutation-unsigned", lambda: S.verify_privacy(tampered(S.privacy_authorization(), holdId="phold.other")), "SIGNATURE_INVALID"),
    ("privacy-wrong-epoch", lambda: S.verify_privacy(S.privacy_authorization(recoveryEpoch=S.OLD_EPOCH.to_dict())), "RECOVERY_EPOCH_MISMATCH"),
    ("privacy-logical-owner", lambda: S.verify_privacy(S.privacy_authorization(logicalOwnerId="owner.other.v1")), "LOGICAL_OWNER_MISMATCH"),
    ("privacy-logical-authority-domain", lambda: S.verify_privacy(S.privacy_authorization(authorityDomain="authority.synthetic.other")), "AUTHORITY_DOMAIN_MISMATCH"),
    ("privacy-authorization-id-substitution", lambda: S.verify_privacy(S.privacy_authorization(authorizationId="pauth.other")), "EVIDENCE_ID_MISMATCH"),
    ("privacy-nonce-substitution", lambda: S.verify_privacy(S.privacy_authorization(executionNonce="pnonce.other")), "EVIDENCE_NONCE_MISMATCH"),
    ("privacy-forget-request-substitution", lambda: S.verify_privacy(S.privacy_authorization(forgetRequestId="pforget.other")), "FORGET_REQUEST_MISMATCH"),
    ("privacy-hold-substitution", lambda: S.verify_privacy(S.privacy_authorization(holdId="phold.other")), "HOLD_MISMATCH"),
    ("privacy-owner-evidence-substitution", lambda: S.verify_privacy(S.privacy_authorization(ownerEvidenceId="aev.other")), "OWNER_EVIDENCE_REFERENCE_MISMATCH"),
    ("privacy-subject-substitution", lambda: S.verify_privacy(S.privacy_authorization(subjectKey="other")), "MEMORY_IDENTITY_MISMATCH"),
    ("privacy-item-substitution", lambda: S.verify_privacy(S.privacy_authorization(memoryItemId=None)), "MEMORY_IDENTITY_MISMATCH"),
    ("privacy-action-digest-mutation", lambda: S.verify_privacy(S.privacy_authorization(actionDigest=OTHER)), "ACTION_DIGEST_MISMATCH"),
    ("privacy-resource-owner-dropped", lambda: S.verify_privacy(S.privacy_authorization(resourceOwners=["L04", "PRIVACY"])), "RESOURCE_OWNERS_MISMATCH"),
]


class NegativeMatrixTests(unittest.TestCase):
    def test_every_case_is_not_accepted_with_exact_reason(self):
        names = [name for name, _, _ in CASES]
        self.assertEqual(len(names), len(set(names)))
        for name, run, reason in CASES:
            with self.subTest(case=name):
                result = run()
                self.assertEqual(result.status, V.NOT_ACCEPTED, name)
                self.assertEqual(result.reason, reason, name)
                self.assertFalse(result.verified)
                self.assertEqual(dict(result.facts), {})

    def test_taxonomy_is_closed_and_fully_covered(self):
        self.assertEqual(len(V.REASONS), len(set(V.REASONS)))
        self.assertEqual({reason for _, _, reason in CASES}, set(V.REASONS))

    def test_every_signed_registry_field_is_bound(self):
        reg = S.registry()
        mutations = {
            "protocol": "LILITH_OTHER", "schemaVersion": 2, "environment": "dev", "registryVersion": 4,
            "recoveryEpoch": S.FORK_EPOCH.to_dict(), "policyVersion": "policy.synthetic.v3",
            "registryRootKeyId": S.ROOT_KEY_ID, "issuedAt": "2026-09-26T06:00:01Z",
            "keys": S.default_keys()[1:],
        }
        self.assertEqual(set(mutations), A.REGISTRY_SIGNED_FIELDS)
        for name, value in mutations.items():
            if name == "registryRootKeyId":
                continue  # root id substitution is covered by REGISTRY_ROOT_MISMATCH
            with self.subTest(field=name):
                result = reg_result(reg=tampered(reg, **{name: value}))
                self.assertEqual((result.status, result.reason), (V.NOT_ACCEPTED, "REGISTRY_SIGNATURE_INVALID"))

    def test_every_signed_evidence_field_is_bound(self):
        for contract, artifact, verify in (
            (A.OwnerEvidenceV2, S.owner_evidence(), S.verify_owner),
            (A.PrivacyAuthorizationV2, S.privacy_authorization(), S.verify_privacy),
        ):
            for name in sorted(contract.signed_fields() - {"protocol", "schemaVersion", "signingDomain",
                                                           "evidenceType", "environment", "keyId"}):
                with self.subTest(contract=contract.__name__, field=name):
                    value = artifact[name]
                    changed = (OTHER if isinstance(value, str) and len(value) == 64
                               else value + 1 if isinstance(value, int)
                               else {**value, "counter": value["counter"] + 1} if isinstance(value, dict)
                               else value + ["ZZZ"] if isinstance(value, list)
                               else "2026-09-26T12:10:00Z" if name == "issuedAt"
                               else "owner.other.v1" if name == "logicalOwnerId"
                               else "mitem.other" if value is None
                               else value + ".x")
                    result = verify(tampered(artifact, **{name: changed}))
                    self.assertEqual((result.status, result.reason), (V.NOT_ACCEPTED, "SIGNATURE_INVALID"))


class PositivePathTests(unittest.TestCase):
    def test_registry_verifies(self):
        result = V.verify_authority_registry(context=S.context(), registry=S.registry())
        self.assertEqual(result.status, V.VERIFIED_REGISTRY)
        self.assertEqual(result.facts["registryVersion"], 3)
        self.assertEqual(result.facts["recoveryEpoch"], S.EPOCH.to_dict())

    def test_higher_registry_version_than_trusted_minimum_is_accepted(self):
        result = V.verify_authority_registry(context=S.context(), registry=S.registry(registryVersion=4))
        self.assertEqual(result.status, V.VERIFIED_REGISTRY)

    def test_owner_evidence_verifies_but_is_not_memory_acceptance(self):
        result = S.verify_owner()
        self.assertEqual(result.status, V.VERIFIED_AUTHORITY_EVIDENCE)
        self.assertNotEqual(result.status, B2A.ACCEPTED_MEMORY)
        self.assertIs(result.facts["memoryAcceptance"], False)
        self.assertIs(result.facts["truthClaim"], False)
        self.assertIs(result.facts["authorizesNewAdmission"], True)
        self.assertEqual(result.facts["keyStatus"], "CURRENT")
        self.assertEqual(result.facts["signingDomain"], A.OWNER_ACTOR)
        self.assertEqual(result.facts["authorityDomain"], S.LOGICAL_AUTHORITY_DOMAIN)
        self.assertEqual(result.facts["registryVersionBasis"], V.REGISTRY_VERSION_BASIS)
        self.assertIs(result.facts["historicalRegistrySnapshotVerified"], False)

    def test_privacy_authorization_verifies(self):
        result = S.verify_privacy()
        self.assertEqual(result.status, V.VERIFIED_AUTHORITY_EVIDENCE)
        self.assertEqual(result.facts["signingDomain"], A.PRIVACY)
        self.assertEqual(result.facts["authorityDomain"], S.LOGICAL_AUTHORITY_DOMAIN)
        self.assertIs(result.facts["memoryAcceptance"], False)

    def test_dev_environment_is_self_consistent_only(self):
        dev = S.owner_evidence(signer="dev.actor.current-1", environment="dev")
        self.assertEqual(S.verify_owner(dev, ctx=S.dev_context(), reg=S.dev_registry()).status,
                         V.VERIFIED_AUTHORITY_EVIDENCE)
        self.assertEqual(S.verify_owner(dev).reason, "ENVIRONMENT_MISMATCH")


class RetirementAndCompromiseTests(unittest.TestCase):
    def test_retired_key_historical_evidence_inside_interval_remains_valid(self):
        evidence = S.owner_evidence(keyId="actor.retired-1", registryVersion=2, issuedAt="2026-09-25T23:59:59Z")
        result = S.verify_owner(evidence, ctx=S.historical_context())
        self.assertEqual(result.status, V.VERIFIED_AUTHORITY_EVIDENCE)
        self.assertEqual(result.facts["keyStatus"], "RETIRED_AFTER_ISSUANCE")
        self.assertIs(result.facts["authorizesNewAdmission"], False)

    def test_retirement_boundary_is_half_open(self):
        at_retirement = S.owner_evidence(keyId="actor.retired-1", registryVersion=2, issuedAt="2026-09-26T00:00:00Z")
        at_not_before = S.owner_evidence(keyId="actor.retired-1", registryVersion=2, issuedAt="2026-09-10T00:00:00Z")
        self.assertEqual(S.verify_owner(at_retirement, ctx=S.historical_context()).reason, "KEY_RETIRED")
        self.assertTrue(S.verify_owner(at_not_before, ctx=S.historical_context()).verified)

    def test_routine_revocation_behaves_like_retirement(self):
        evidence = S.owner_evidence(keyId="actor.revoked-1", registryVersion=2, issuedAt="2026-09-15T00:00:00Z")
        for ctx in (S.context(), S.historical_context()):
            with self.subTest(purpose=ctx.purpose):
                result = S.verify_owner(evidence, ctx=ctx)
                self.assertEqual(result.facts["keyStatus"], "REVOKED_AFTER_ISSUANCE")

    def test_rotation_does_not_invalidate_in_flight_evidence(self):
        in_flight = S.owner_evidence(keyId="actor.retired-1", registryVersion=2, issuedAt="2026-09-25T23:59:00Z")
        result = S.verify_owner(in_flight)
        self.assertEqual(result.status, V.VERIFIED_AUTHORITY_EVIDENCE)
        self.assertIs(result.facts["authorizesNewAdmission"], True)
        self.assertEqual(result.facts["keyStatus"], "RETIRED_AFTER_ISSUANCE")

    def test_no_signer_controlled_timestamp_rescues_a_compromised_key(self):
        for issued in ("2026-09-10T00:00:00Z", "2026-09-15T00:00:00Z", "2026-09-23T23:59:59Z",
                       "2026-09-24T00:00:00Z", "2026-09-26T12:00:00Z"):
            for ctx in (S.context(), S.historical_context()):
                with self.subTest(issued=issued, purpose=ctx.purpose):
                    for version in (2, 3):
                        evidence = S.owner_evidence(keyId="actor.compromised-1", registryVersion=version,
                                                    issuedAt=issued)
                        self.assertEqual(S.verify_owner(evidence, ctx=ctx).reason, "KEY_COMPROMISED")

    def test_b2a_revoked_after_issuance_semantics_are_not_promoted(self):
        # B2a would accept evidence issued before revocation; B1b-3a never
        # accepts compromised-key evidence, and never lets a revoked key
        # support NEW_ADMISSION.
        before = S.owner_evidence(keyId="actor.compromised-1", issuedAt="2026-09-11T00:00:00Z")
        self.assertEqual(S.verify_owner(before).reason, "KEY_COMPROMISED")
        after = S.owner_evidence(keyId="actor.revoked-1", issuedAt="2026-09-21T00:00:00Z")
        self.assertEqual(S.verify_owner(after).reason, "KEY_REVOKED")


class RegistryEvolutionTests(unittest.TestCase):
    """Registry evolution alone never invalidates otherwise-valid evidence."""

    def test_unrelated_monotonic_registry_updates_keep_pending_evidence_valid(self):
        pending = S.owner_evidence()  # issued under registry version 3
        extra = S.key_record("privacy.zz-added-4", seed_name="attacker", registryVersion=4)
        for version, keys in ((3, None), (4, S.default_keys() + [extra]), (9, None)):
            with self.subTest(registry_version=version):
                reg = S.registry(registryVersion=version, keys=keys)
                result = S.verify_owner(pending, reg=reg)
                self.assertEqual(result.status, V.VERIFIED_AUTHORITY_EVIDENCE)
                self.assertEqual(result.facts["evidenceRegistryVersion"], 3)
                self.assertEqual(result.facts["registryVersion"], version)
                self.assertIs(result.facts["historicalRegistrySnapshotVerified"], False)

    def test_evidence_version_bounds(self):
        # Key first published at 3: evidence may not claim 2, nor exceed the
        # verified registry.
        self.assertEqual(S.verify_owner(S.owner_evidence(registryVersion=2)).reason, "REGISTRY_VERSION_MISMATCH")
        self.assertEqual(S.verify_owner(S.owner_evidence(registryVersion=4)).reason, "REGISTRY_VERSION_MISMATCH")
        later = S.owner_evidence(registryVersion=4)
        self.assertTrue(S.verify_owner(later, reg=S.registry(registryVersion=4)).verified)

    def test_downgrade_still_rejected_and_current_compromise_still_applies(self):
        pending = S.owner_evidence()
        self.assertEqual(S.verify_owner(pending, ctx=S.context(trusted_minimum_registry_version=4)).reason,
                         "REGISTRY_DOWNGRADE")
        # A later registry marks the signing key compromised: retroactive.
        compromised = S.registry(registryVersion=4, keys=[
            ({**k, "revokedAt": "2026-09-26T06:00:00Z", "revocationReason": "COMPROMISED",
              "compromisedSince": "2026-09-26T00:00:00Z"} if k["keyId"] == "actor.current-2" else k)
            for k in S.default_keys()])
        self.assertEqual(S.verify_owner(pending, reg=compromised).reason, "KEY_COMPROMISED")

    def test_key_record_registry_version_means_first_publication(self):
        self.assertEqual(GOLDEN["fieldSemantics"]["keyRecord.registryVersion"],
                         "the registry version in which this key was first published")
        self.assertIn("first published", " ".join(A.AuthorityKeyRecordV1.__doc__.split()))
        record = next(k for k in S.default_keys() if k["keyId"] == "actor.retired-1")
        self.assertEqual(record["registryVersion"], 2)  # unchanged by its later retirement
        self.assertIsNotNone(record["retiredAt"])


class SigningDomainSemanticsTests(unittest.TestCase):
    """logical authority context != cryptographic signing domain."""

    def test_field_sets(self):
        self.assertIn("signingDomain", A.KEY_RECORD_FIELDS)
        self.assertNotIn("authorityDomain", A.KEY_RECORD_FIELDS)
        for contract in (A.OwnerEvidenceV2, A.PrivacyAuthorizationV2):
            self.assertIn("signingDomain", contract.FIELDS)
            self.assertIn("authorityDomain", contract.FIELDS)
        self.assertEqual(A.SIGNING_DOMAINS, frozenset({"OWNER_ACTOR", "PRIVACY"}))
        self.assertFalse(hasattr(A, "AUTHORITY_DOMAINS"))

    def test_b2a_authority_domain_semantics_are_unchanged(self):
        # B2a keeps authorityDomain as the logical scope; the B1b-3a logical
        # value is the same synthetic scope, and it is not a signing domain.
        import synthetic_chain
        self.assertEqual(synthetic_chain.AUTHORITY_DOMAIN, S.LOGICAL_AUTHORITY_DOMAIN)
        self.assertNotIn(S.LOGICAL_AUTHORITY_DOMAIN, A.SIGNING_DOMAINS)
        self.assertIn("authorityDomain", K.CHALLENGE_V2_FIELDS)
        self.assertIn("authorityDomain", K.EVIDENCE_FIELDS)
        self.assertNotIn("signingDomain", K.CHALLENGE_V2_FIELDS | K.EVIDENCE_FIELDS)

    def test_golden_vectors_make_the_distinction_explicit(self):
        semantics = GOLDEN["fieldSemantics"]
        self.assertIn("cryptographic", semantics["signingDomain"])
        self.assertIn("logical", semantics["authorityDomain"])
        self.assertEqual(GOLDEN["ownerEvidenceV2"]["signingDomain"], "OWNER_ACTOR")
        self.assertEqual(GOLDEN["ownerEvidenceV2"]["authorityDomain"], "authority.synthetic.memory")
        self.assertEqual(GOLDEN["privacyAuthorizationV2"]["signingDomain"], "PRIVACY")
        self.assertEqual(GOLDEN["privacyAuthorizationV2"]["authorityDomain"], "authority.synthetic.memory")
        for record in GOLDEN["registry"]["keys"]:
            self.assertIn(record["signingDomain"], {"OWNER_ACTOR", "PRIVACY"})
            self.assertNotIn("authorityDomain", record)


class EpochTests(unittest.TestCase):
    def test_old_epoch_evidence_is_history_only(self):
        evidence = S.owner_evidence(keyId="actor.epoch1-1", registryVersion=1,
                                    recoveryEpoch=S.OLD_EPOCH.to_dict(), issuedAt="2026-09-05T12:00:00Z")
        historical = S.verify_owner(evidence, ctx=S.historical_context())
        self.assertTrue(historical.verified)
        self.assertIs(historical.facts["authorizesNewAdmission"], False)
        self.assertEqual(historical.facts["evidenceRecoveryEpoch"], S.OLD_EPOCH.to_dict())
        self.assertEqual(S.verify_owner(evidence).reason, "RECOVERY_EPOCH_MISMATCH")

    def test_epoch_equality_uses_both_counter_and_random(self):
        self.assertNotEqual(S.EPOCH, S.FORK_EPOCH)
        self.assertEqual(S.EPOCH.counter, S.FORK_EPOCH.counter)
        self.assertEqual(A.RecoveryEpochV1.from_dict(S.EPOCH.to_dict()), S.EPOCH)

    def test_malformed_epochs_are_rejected(self):
        for value in ({"counter": True, "random": S.EPOCH.random}, {"counter": 1, "random": "ABC"},
                      {"counter": 1, "random": S.EPOCH.random, "extra": 1}, {"counter": 2**53, "random": S.EPOCH.random}):
            with self.subTest(value=value):
                with self.assertRaises(P.OwnerProofError):
                    A.RecoveryEpochV1.from_dict(value)


class GoldenVectorTests(unittest.TestCase):
    def test_golden_file_is_reproduced_exactly(self):
        self.assertEqual(S.golden_document(), GOLDEN)

    def test_domain_separators_are_frozen_and_distinct(self):
        self.assertEqual(A.REGISTRY_DOMAIN_SEPARATOR, b"LILITH_AUTHORITY_REGISTRY_V1\x00")
        self.assertEqual(A.OWNER_EVIDENCE_DOMAIN_SEPARATOR, b"LILITH_ACTOR_EVIDENCE_V2\x00")
        self.assertEqual(A.PRIVACY_AUTHORIZATION_DOMAIN_SEPARATOR, b"LILITH_PRIVACY_AUTHORIZATION_V2\x00")
        separators = {A.REGISTRY_DOMAIN_SEPARATOR, A.OWNER_EVIDENCE_DOMAIN_SEPARATOR,
                      A.PRIVACY_AUTHORIZATION_DOMAIN_SEPARATOR, K.EVIDENCE_DOMAIN_SEPARATOR,
                      K.CHALLENGE_V2_DOMAIN_SEPARATOR, K.ASSERTION_DIGEST_DOMAIN_SEPARATOR, P.DOMAIN_SEPARATOR}
        self.assertEqual(len(separators), 7)
        self.assertEqual(GOLDEN["domainSeparators"], {
            "registry": "LILITH_AUTHORITY_REGISTRY_V1\x00",
            "ownerEvidence": "LILITH_ACTOR_EVIDENCE_V2\x00",
            "privacyAuthorization": "LILITH_PRIVACY_AUTHORIZATION_V2\x00",
        })

    def test_golden_artifacts_verify_with_published_public_keys(self):
        ctx = S.context(registry_root=A.TrustedRegistryRootV1.from_dict({
            "schemaVersion": 1, "rootKeyId": S.ROOT_KEY_ID, "environment": "test",
            "algorithm": "Ed25519", "publicKey": GOLDEN["publicKeys"]["root"]}))
        self.assertTrue(V.verify_authority_registry(context=ctx, registry=GOLDEN["registry"]).verified)
        self.assertTrue(V.verify_owner_evidence(context=ctx, registry=GOLDEN["registry"],
                                                evidence=GOLDEN["ownerEvidenceV2"],
                                                expectation=S.owner_expectation()).verified)
        self.assertTrue(V.verify_privacy_authorization(context=ctx, registry=GOLDEN["registry"],
                                                       authorization=GOLDEN["privacyAuthorizationV2"],
                                                       expectation=S.privacy_expectation()).verified)
        self.assertEqual(hashlib.sha256(A.registry_signing_bytes(unsigned(GOLDEN["registry"]))).hexdigest(),
                         GOLDEN["registrySigningDigest"])
        self.assertEqual(hashlib.sha256(A.owner_evidence_signing_bytes(unsigned(GOLDEN["ownerEvidenceV2"]))).hexdigest(),
                         GOLDEN["ownerEvidenceSigningDigest"])
        self.assertEqual(hashlib.sha256(A.privacy_authorization_signing_bytes(
            unsigned(GOLDEN["privacyAuthorizationV2"]))).hexdigest(), GOLDEN["privacyAuthorizationSigningDigest"])

    def test_outcome_vectors(self):
        self.assertEqual([v["name"] for v in GOLDEN["outcomes"]], [
            "retirement-historical-accepted", "retirement-new-admission-rejected",
            "registry-update-keeps-in-flight-evidence",
            "compromise-backdated-rejected", "epoch-old-evidence-historical-only",
            "epoch-old-evidence-new-admission-rejected", "cross-domain-actor-key-signs-privacy",
            "cross-domain-privacy-key-signs-actor", "cross-domain-owner-evidence-as-privacy",
            "logical-authority-context-mismatch-with-valid-signing-domain",
            "environment-test-evidence-in-dev",
        ])
        for vector in GOLDEN["outcomes"]:
            with self.subTest(vector=vector["name"]):
                result = S.evaluate_vector(vector)
                self.assertEqual((result.status, result.reason), (vector["status"], vector["reason"]))
                if "keyStatus" in vector:
                    self.assertEqual(result.facts["keyStatus"], vector["keyStatus"])

    def test_registry_signing_bytes_are_key_order_independent(self):
        value = S.registry_unsigned()
        self.assertEqual(A.registry_signing_bytes(value), A.registry_signing_bytes(dict(reversed(list(value.items())))))


class ImmutabilityTests(unittest.TestCase):
    def test_b2a_and_v1_contracts_are_unchanged(self):
        self.assertEqual(hashlib.sha256(B2A_GOLDEN.read_bytes()).hexdigest(),
                         "86c439583b0e7f74d5bec78f046f0d410cd4915d76bb3ee3f590fc47666f3a25")
        self.assertEqual(K.EVIDENCE_DOMAIN_SEPARATOR, b"LILITH_BROKER_MEMORY_EVIDENCE_V1\x00")
        self.assertEqual(K.CHALLENGE_V2_DOMAIN_SEPARATOR, b"LILITH_OWNER_MEMORY_CHALLENGE_V2\x00")
        self.assertEqual(P.DOMAIN_SEPARATOR, b"LILITH_OWNER_MEMORY_CHALLENGE_V1\x00")
        self.assertEqual(len(B2A.REASONS), 43)

    def test_b2a_broker_key_type_is_not_used_by_b1b3a(self):
        for module in (A, V):
            source = inspect.getsource(module)
            self.assertNotIn("BrokerVerificationKeyV1", source.split('"""', 2)[2])
            self.assertNotIn("broker_keys", source)


class IsolationTests(unittest.TestCase):
    def test_no_private_key_io_env_network_or_runtime_in_contract_modules(self):
        for module in (A, V):
            source = inspect.getsource(module)
            for forbidden in ("Ed25519PrivateKey", "open(", "os.environ", "getenv", "socket", "subprocess",
                              "sqlite3", "urllib", "requests", "Path(", "import os", "lilith_memory_broker",
                              "canonical_store", "privacy_governance", "memory_v2"):
                with self.subTest(module=module.__name__, forbidden=forbidden):
                    self.assertNotIn(forbidden, source)

    def test_fixture_keys_are_labelled_synthetic_and_roots_are_distinct(self):
        fixture = inspect.getsource(S)
        self.assertNotIn("open(\"/", fixture)
        self.assertNotIn("home", fixture.lower().replace("homelab", ""))
        publics = {name: S.public_b64(name) for name in S.SEEDS}
        self.assertEqual(len(set(publics.values())), len(publics))
        authority_publics = {k["publicKey"] for k in S.default_keys()}
        self.assertNotIn(publics["root"], authority_publics)
        self.assertTrue(S.trusted_root().test_only)
        # Not the B2a synthetic broker key either.
        import synthetic_chain
        b2a_broker = S.public_b64(synthetic_chain.broker_key())
        self.assertNotIn(b2a_broker, set(publics.values()))

    def test_contract_modules_are_not_imported_by_runtime_packages(self):
        root = S.ROOT / "services"
        for path in list((root / "core-api").rglob("*.py")) + list((root / "memory-broker").rglob("*.py")):
            if ".venv" in path.parts or "tests" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn("authority_contracts", text, str(path))
            self.assertNotIn("authority_verifier", text, str(path))


if __name__ == "__main__":
    unittest.main()
