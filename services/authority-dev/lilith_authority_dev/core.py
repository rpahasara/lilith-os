"""Authority signer dispatch and L1 readiness (B1b-3d L1).

Readiness is separate from process liveness and from credential presence:

    process running      != SERVICE_AVAILABLE with authority
    credential present   != key verified against the registry
    anything in L1       == NOT_READY, SIGNING_NOT_AVAILABLE

Design §18 orders startup checks as custody preflight, key fingerprint vs
registry, witness under its anchor, then B1b-3c readiness. None of the
registry, witness, or durable ledger components exist in L1, so readiness is
always `NOT_READY` and every signing request is refused before any key could
be touched. The core holds no private key and no minter.
"""

from __future__ import annotations

from typing import Any

from . import protocol as W
from .credential import CREDENTIAL_ABSENT, CREDENTIAL_INVALID, CredentialStatusV1
from .profile import PROFILE, SIGNING_DOMAIN

SERVICE_AVAILABLE = "SERVICE_AVAILABLE"
SIGNING_NOT_AVAILABLE = "SIGNING_NOT_AVAILABLE"
NOT_READY = "NOT_READY"
REFUSED = "REFUSED"
OK = "OK"
FOUNDATION = "B1B3D_L1_SOURCE_FOUNDATION"

# Readiness inputs that L1 does not provide. Terms are the design's own:
# REGISTRY_MISSING (B1b-3a verifier), WITNESS_MISSING (§18),
# AUTHORITY_STATE_MISSING (§12, no auto-initialisation of the ledger).
L1_ABSENT_COMPONENTS = ("REGISTRY_MISSING", "WITNESS_MISSING", "AUTHORITY_STATE_MISSING")


def readiness_reasons(credential: CredentialStatusV1) -> tuple[str, ...]:
    """Ordered NOT_READY reasons. Never empty in L1."""
    reasons: list[str] = []
    if credential.state in (CREDENTIAL_ABSENT, CREDENTIAL_INVALID):
        reasons.append(credential.state)
    reasons.extend(L1_ABSENT_COMPONENTS)
    return tuple(reasons)


class DevAuthoritySignerCoreV1:
    def __init__(self, credential: CredentialStatusV1):
        if not isinstance(credential, CredentialStatusV1):
            raise TypeError("credential status is required")
        self._credential = credential

    def health(self) -> dict[str, Any]:
        return {
            "profile": PROFILE,
            "signingDomain": SIGNING_DOMAIN,
            "foundation": FOUNDATION,
            "service": SERVICE_AVAILABLE,
            "credential": self._credential.state,
            "publicKeySha256": self._credential.public_key_sha256,
            "signing": SIGNING_NOT_AVAILABLE,
            "readiness": NOT_READY,
            "reasons": list(readiness_reasons(self._credential)),
        }

    def dispatch(self, message: W.AuthorityMessageV1) -> dict[str, Any]:
        if not isinstance(message, W.AuthorityMessageV1) or message.operation not in W.OPERATIONS:
            return {"status": REFUSED, "reason": "UNSUPPORTED_OPERATION"}
        if message.operation == W.HEALTH:
            return {"status": OK, "health": self.health()}
        # ISSUE_OWNER_EVIDENCE: re-validate the structured request, then refuse.
        # L1 has no path from here to a key: readiness is never READY.
        try:
            W.parse_issue_request(message.payload)
        except W.ProtocolError as exc:
            return {"status": REFUSED, "reason": exc.code}
        return {
            "status": REFUSED,
            "reason": SIGNING_NOT_AVAILABLE,
            "readiness": NOT_READY,
            "reasons": list(readiness_reasons(self._credential)),
        }
