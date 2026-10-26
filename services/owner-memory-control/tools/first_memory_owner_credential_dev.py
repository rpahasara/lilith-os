#!/usr/bin/env python3
"""First Memory owner credential (DEV_SYNTHETIC): the owner-device software authenticator and its registration.

Runs on the OWNER DEVICE (the owner workstation), never on DEV. Three closed forms:

    create <key-out> <public-out>          a new P-256 owner credential. The private key is written ONLY to
                                           <key-out> (0600, O_EXCL) on the owner device; <public-out> gets the
                                           public credential record plus a proof of possession over the fixed
                                           registration challenge for exactly that record.
    assert <key> <public> <challenge-hex>  sign one WebAuthn assertion over the 32-byte challenge an offer printed
                                           (`webauthnChallenge`); prints the assertion JSON.
    registration <release-sha> <public>... verify every proof of possession and print the root-installable
                                           `owner-registration.json` (JCS) for `/etc/lilith-owner-proof-dev/`;
                                           <release-sha> is the 40-hex accepted authority release the evidence is
                                           issued by (the owner context's `brokerReleases`).

What this is and is not:

- The relying party is the synthetic `owner.lilith.invalid`; no browser or platform authenticator can be used for it.
  This is a SOFTWARE authenticator whose user-presence / user-verification flags are self-asserted by this tool:
  possession of the key file is the only factor. A memory admitted with it is owner-authorized in the DEV_SYNTHETIC
  sense only (the owner held the device key and ran the tool for that exact challenge); it does NOT prove a real
  human identity, a hardware authenticator or biometric user verification.
- Registration copies only the PUBLIC credential to DEV; installing it there is a separate, owner-authorized root
  step. Every memory still needs a fresh assertion over its exact challenge.

    registered credential != owner proof != issuance permission
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import rfc8785
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fido2 import cbor
from fido2.cose import ES256, CoseKey

OWNER_PRINCIPAL = "user:synthetic-owner@example.invalid"      # owner_proof._DEV_SYNTHETIC_OWNER
RP_ID = "owner.lilith.invalid"                               # owner_proof.SYNTHETIC_RP_ID
ORIGIN = "https://" + RP_ID                                  # owner_proof.SYNTHETIC_ORIGIN
REGISTRATION_DOMAIN = b"LILITH_OWNER_REGISTRATION_DEV_V1\x00"
REGISTRATION_PROTOCOL = "LILITH_OWNER_REGISTRATION_DEV"
# The deployment's owner-proof settings carried in the registration (lilith_authority_host.inputs).
REGISTRY_TUPLE_VERSION = "tuple.dev-synthetic.v1"
PRIVACY_NOTICE_VERSION = "privacy.dev-synthetic.v1"
FLAGS_UP_UV = 0x05                                           # self-asserted by this software authenticator
PUBLIC_FIELDS = ("schemaVersion", "recordId", "ownerPrincipal", "credentialId", "publicKeyCose", "algorithm",
                 "rpId", "status", "createdAt", "revokedAt", "lastObservedSignCount")


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def registration_challenge(credential: Mapping[str, Any]) -> bytes:
    """The fixed registration challenge: binds exactly this public record (and nothing else)."""
    return hashlib.sha256(REGISTRATION_DOMAIN + rfc8785.dumps({k: credential[k] for k in PUBLIC_FIELDS})).digest()


def sign_assertion(private: ec.EllipticCurvePrivateKey, credential: Mapping[str, Any], challenge: bytes) -> dict:
    if len(challenge) != 32:
        raise Refused("CHALLENGE_INVALID")
    client = json.dumps({"type": "webauthn.get", "challenge": b64(challenge), "origin": ORIGIN, "crossOrigin": False},
                        separators=(",", ":")).encode("ascii")
    auth = hashlib.sha256(RP_ID.encode("ascii")).digest() + bytes([FLAGS_UP_UV]) + (0).to_bytes(4, "big")
    signature = private.sign(auth + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
    return {"credentialRecordId": credential["recordId"], "credentialId": credential["credentialId"],
            "clientDataJSON": b64(client), "authenticatorData": b64(auth), "signature": b64(signature)}


def verify_possession(public: Mapping[str, Any]) -> dict[str, Any]:
    """Check one `create` output: the record is the DEV_SYNTHETIC owner's, and its proof signs the registration
    challenge for exactly that record. Returns the public credential record."""
    if not isinstance(public, Mapping) or set(public) != {"credential", "possessionProof"}:
        raise Refused("PUBLIC_DOCUMENT_INVALID")
    credential, proof = dict(public["credential"]), dict(public["possessionProof"])
    if set(credential) != set(PUBLIC_FIELDS) or (credential["ownerPrincipal"], credential["rpId"], credential["status"],
                                                  credential["algorithm"]) != (OWNER_PRINCIPAL, RP_ID, "ACTIVE", -7):
        raise Refused("CREDENTIAL_NOT_DEV_SYNTHETIC_OWNER")
    if (proof.get("credentialRecordId"), proof.get("credentialId")) != (credential["recordId"],
                                                                        credential["credentialId"]):
        raise Refused("PROOF_NAMES_ANOTHER_CREDENTIAL")
    try:
        client = json.loads(unb64(proof["clientDataJSON"]))
        auth = unb64(proof["authenticatorData"])
        key = CoseKey.parse(cbor.decode(unb64(credential["publicKeyCose"])))
    except (KeyError, ValueError, TypeError) as exc:
        raise Refused("PROOF_MALFORMED") from exc
    if client != {"type": "webauthn.get", "challenge": b64(registration_challenge(credential)), "origin": ORIGIN,
                  "crossOrigin": False}:
        raise Refused("PROOF_CHALLENGE_MISMATCH")
    if len(auth) != 37 or auth[:32] != hashlib.sha256(RP_ID.encode("ascii")).digest() or auth[32] & FLAGS_UP_UV != 5:
        raise Refused("PROOF_AUTHENTICATOR_DATA_INVALID")
    try:
        key.verify(auth + hashlib.sha256(unb64(proof["clientDataJSON"])).digest(), unb64(proof["signature"]))
    except Exception as exc:  # cryptography InvalidSignature and decoding errors alike
        raise Refused("PROOF_SIGNATURE_INVALID") from exc
    return credential


def registration_document(publics: list[Mapping[str, Any]], *, release_sha: str) -> dict[str, Any]:
    if not (isinstance(release_sha, str) and len(release_sha) == 40 and all(c in "0123456789abcdef" for c in release_sha)):
        raise Refused("RELEASE_SHA_INVALID")
    credentials = [verify_possession(p) for p in publics]
    if not credentials or len({c["recordId"] for c in credentials}) != len(credentials):
        raise Refused("CREDENTIALS_INVALID")
    return {"protocol": REGISTRATION_PROTOCOL, "schemaVersion": 1, "environment": "dev",
            "ownerPrincipal": OWNER_PRINCIPAL, "rpId": RP_ID, "origin": ORIGIN,
            "registryTupleVersion": REGISTRY_TUPLE_VERSION, "privacyNoticeVersion": PRIVACY_NOTICE_VERSION,
            "brokerReleases": [release_sha], "credentials": credentials}


def create(key_out: Path, public_out: Path, *, now: datetime | None = None) -> dict[str, Any]:
    private = ec.generate_private_key(ec.SECP256R1())
    credential_id = secrets.token_bytes(32)
    created = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    credential = {"schemaVersion": 1, "recordId": "ocred.dev-synthetic." + credential_id[:8].hex(),
                  "ownerPrincipal": OWNER_PRINCIPAL, "credentialId": b64(credential_id),
                  "publicKeyCose": b64(cbor.encode(ES256.from_cryptography_key(private.public_key()))),
                  "algorithm": -7, "rpId": RP_ID, "status": "ACTIVE",
                  "createdAt": created.strftime("%Y-%m-%dT%H:%M:%SZ"), "revokedAt": None, "lastObservedSignCount": 0}
    public = {"credential": credential,
              "possessionProof": sign_assertion(private, credential, registration_challenge(credential))}
    pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
    fd = os.open(key_out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(pem)
    Path(public_out).write_bytes(rfc8785.dumps(public))     # public material only
    return {"recordId": credential["recordId"], "publicKeyCoseSha256": hashlib.sha256(
        credential["publicKeyCose"].encode("ascii")).hexdigest()}


def load_private(path: Path) -> ec.EllipticCurvePrivateKey:
    key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(key.curve, ec.SECP256R1):
        raise Refused("KEY_INVALID")
    return key


def main(argv: list[str]) -> int:
    try:
        if argv[:1] == ["create"] and len(argv) == 3:
            out = create(Path(argv[1]), Path(argv[2]))
        elif argv[:1] == ["assert"] and len(argv) == 4:
            public = json.loads(Path(argv[2]).read_bytes())
            credential = verify_possession(public)
            out = sign_assertion(load_private(Path(argv[1])), credential, bytes.fromhex(argv[3]))
        elif argv[:1] == ["registration"] and len(argv) >= 3:
            out = registration_document([json.loads(Path(p).read_bytes()) for p in argv[2:]], release_sha=argv[1])
            sys.stdout.buffer.write(rfc8785.dumps(out))
            return 0
        else:
            raise Refused("USAGE")
    except Refused as exc:
        print(f"first-memory-owner-credential: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"first-memory-owner-credential: REFUSED {type(exc).__name__}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(out, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
