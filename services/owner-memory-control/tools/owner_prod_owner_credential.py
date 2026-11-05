#!/usr/bin/env python3
"""OWNER_PROD owner credential: the PROD twin of `first_memory_owner_credential_dev.py` (SOURCE ONLY; owner device).

Record: docs/architecture/canonical-memory-prod-owner-decisions.md (D-8, D-12). Runs on the OWNER DEVICE (the owner
workstation, in WSL), never on a LILITH host. The DEV tool stays byte-identical: this tool loads its OWN instance of
that module and sets, on that instance only, the owner's PROD identity, given explicitly on every call:

    create       <rp-id> <origin> <principal> <key-out> <public-out>
    assert       <rp-id> <origin> <principal> <key> <public> <challenge-hex>
    registration <rp-id> <origin> <principal> <release-sha> <public>...

- **Identity (D-8).** `<rp-id>`, `<origin>` and `<principal>` must pass the PROD host's own rule
  (`lilith_authority_host.inputs._require_prod_owner`): a lowercase DNS name with a letter TLD, never `.invalid`;
  origin exactly `https://<rp-id>` or `https://<sub>.<rp-id>`; principal `user:<name>@<domain>`, never the DEV
  synthetic owner. Anything else is `IDENTITY_NOT_OWNER_PROD` before any key is touched.
- **What changes from DEV.** The relying party, origin and principal are the owner's. The registration protocol is
  `LILITH_OWNER_REGISTRATION_PROD` with environment `prod` (the host's PROD protocol). The possession-proof domain is
  `LILITH_OWNER_REGISTRATION_PROD_V1`, so a DEV proof can never be replayed as a PROD one. Record ids are
  `ocred.owner-prod.*`, and the registry tuple and privacy notice versions are `tuple.owner-prod.v1` and
  `privacy.owner-prod.v1`.
- **What is reused unchanged.** The P-256 software authenticator, the WebAuthn assertion shape, the possession proof
  and its verification all come from the DEV tool's own code.
- **Registration.** `registration` verifies every proof of possession and prints the root-installable
  `owner-registration.json` (JCS). The result must also parse under the host's own
  `parse_owner_registration(environment="prod")`, or the tool refuses: what it prints is exactly what PROD accepts.

As on DEV, this is a SOFTWARE authenticator: possession of the key file is the only factor, and the UP/UV flags are
self-asserted. The private key is written only to `<key-out>` (`0600`, `O_EXCL`); nothing here is committed or sent
anywhere. On loss, a new credential needs a new owner registration under K-ROOT.

    registered credential != owner proof != issuance permission
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _p in (ROOT / "services/authority-dev", ROOT / "services/core-api"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

DEV_TOOL = HERE / "first_memory_owner_credential_dev.py"
ENVIRONMENT = "prod"
REGISTRATION_PROTOCOL = "LILITH_OWNER_REGISTRATION_PROD"
REGISTRATION_DOMAIN = b"LILITH_OWNER_REGISTRATION_PROD_V1\x00"
REGISTRY_TUPLE_VERSION = "tuple.owner-prod.v1"
PRIVACY_NOTICE_VERSION = "privacy.owner-prod.v1"
RECORD_PREFIX = "ocred.owner-prod."


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def require_owner_prod(rp_id: str, origin: str, principal: str) -> None:
    """D-8: the PROD host's own identity rule, applied before anything else."""
    from lilith_authority_host import inputs as HI
    from lilith_memory import owner_proof as OP

    try:
        HI._require_prod_owner((principal, rp_id, origin), OP)
    except ValueError as exc:
        raise Refused("IDENTITY_NOT_OWNER_PROD") from exc


class ProdCredentialTool:
    """One OWNER_PROD identity over a private instance of the DEV credential module."""

    def __init__(self, rp_id: str, origin: str, principal: str):
        require_owner_prod(rp_id, origin, principal)
        spec = importlib.util.spec_from_file_location("first_memory_owner_credential_prod_instance", DEV_TOOL)
        module: ModuleType = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.OWNER_PRINCIPAL, module.RP_ID, module.ORIGIN = principal, rp_id, origin
        module.REGISTRATION_DOMAIN, module.REGISTRATION_PROTOCOL = REGISTRATION_DOMAIN, REGISTRATION_PROTOCOL
        module.REGISTRY_TUPLE_VERSION, module.PRIVACY_NOTICE_VERSION = REGISTRY_TUPLE_VERSION, PRIVACY_NOTICE_VERSION
        self.module, self.rp_id, self.origin, self.principal = module, rp_id, origin, principal

    def _refuse(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except self.module.Refused as exc:
            raise Refused(exc.reason) from exc

    def create(self, key_out: Path, public_out: Path, *, now: datetime | None = None) -> dict[str, Any]:
        """A new P-256 owner credential for this identity. The private key goes only to `key_out` (0600, O_EXCL)."""
        M = self.module
        private = M.ec.generate_private_key(M.ec.SECP256R1())
        credential_id = secrets.token_bytes(32)
        created = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
        credential = {"schemaVersion": 1, "recordId": RECORD_PREFIX + credential_id[:8].hex(),
                      "ownerPrincipal": self.principal, "credentialId": M.b64(credential_id),
                      "publicKeyCose": M.b64(M.cbor.encode(M.ES256.from_cryptography_key(private.public_key()))),
                      "algorithm": -7, "rpId": self.rp_id, "status": "ACTIVE",
                      "createdAt": created.strftime("%Y-%m-%dT%H:%M:%SZ"), "revokedAt": None,
                      "lastObservedSignCount": 0}
        public = {"credential": credential,
                  "possessionProof": M.sign_assertion(private, credential, M.registration_challenge(credential))}
        self.verify_possession(public)                       # what is written is exactly what PROD will accept
        pem = private.private_bytes(M.serialization.Encoding.PEM, M.serialization.PrivateFormat.PKCS8,
                                    M.serialization.NoEncryption())
        fd = os.open(key_out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(pem)
        Path(public_out).write_bytes(M.rfc8785.dumps(public))     # public material only
        return {"recordId": credential["recordId"], "publicKeyCoseSha256": hashlib.sha256(
            credential["publicKeyCose"].encode("ascii")).hexdigest()}

    def verify_possession(self, public: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(public, Mapping) or not isinstance(public.get("credential"), Mapping) \
                or not str(public["credential"].get("recordId", "")).startswith(RECORD_PREFIX):
            raise Refused("CREDENTIAL_NOT_OWNER_PROD")
        try:
            return self._refuse(self.module.verify_possession, public)
        except Refused as exc:
            if exc.reason == "CREDENTIAL_NOT_DEV_SYNTHETIC_OWNER":   # the DEV tool's name for "not this identity"
                raise Refused("CREDENTIAL_NOT_THIS_OWNER") from exc
            raise

    def assertion(self, key: Path, public: Mapping[str, Any], challenge: bytes) -> dict[str, Any]:
        credential = self.verify_possession(public)
        private = self._refuse(self.module.load_private, key)
        return self._refuse(self.module.sign_assertion, private, credential, challenge)

    def registration(self, publics: list[Mapping[str, Any]], *, release_sha: str) -> dict[str, Any]:
        """The root-installable OWNER_PROD registration, checked by the PROD host's own parser before it is returned."""
        from lilith_authority_host import inputs as HI

        for public in publics:
            self.verify_possession(public)
        document = self._refuse(self.module.registration_document, publics, release_sha=release_sha)
        document["environment"] = ENVIRONMENT                    # the DEV builder writes "dev"; the protocol is PROD's
        if (document["protocol"], HI.OWNER_REGISTRATION_PROTOCOLS.get(ENVIRONMENT)) != (REGISTRATION_PROTOCOL,) * 2:
            raise Refused("REGISTRATION_PROTOCOL_MISMATCH")
        try:
            HI.parse_owner_registration(document, environment=ENVIRONMENT)
        except ValueError as exc:
            raise Refused("REGISTRATION_NOT_OWNER_PROD:" + str(exc)) from exc
        return document


def main(argv: list[str]) -> int:
    try:
        if len(argv) < 4:
            raise Refused("USAGE")
        form, rp_id, origin, principal, rest = argv[0], argv[1], argv[2], argv[3], argv[4:]
        if form not in ("create", "assert", "registration"):
            raise Refused("USAGE")
        tool = ProdCredentialTool(rp_id, origin, principal)
        if form == "create" and len(rest) == 2:
            out = tool.create(Path(rest[0]), Path(rest[1]))
        elif form == "assert" and len(rest) == 3:
            out = tool.assertion(Path(rest[0]), json.loads(Path(rest[1]).read_bytes()), bytes.fromhex(rest[2]))
        elif form == "registration" and len(rest) >= 2:
            document = tool.registration([json.loads(Path(p).read_bytes()) for p in rest[1:]], release_sha=rest[0])
            sys.stdout.buffer.write(tool.module.rfc8785.dumps(document))
            return 0
        else:
            raise Refused("USAGE")
    except Refused as exc:
        print(f"owner-prod-owner-credential: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"owner-prod-owner-credential: REFUSED {type(exc).__name__}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(out, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
