"""TEST-ONLY synthetic identity fixtures for the Identity V1 draft. Never a real LILITH identity.

The synthetic identifier is derived from a fixed label so golden vectors are reproducible. A real identifier comes
only from the separately reviewed, owner-controlled generation procedure (charter draft §6), never like this.

There is deliberately no helper that builds an ACCEPTED_MEMORY result: acceptance must come from genuine V2
verification inside `identity_profile.verify_identity_bound_memory_v1`.
"""

from __future__ import annotations

import hashlib
import json

import synthetic_authority as SA
from lilith_owner_memory import identity_profile as IP

SYNTHETIC_CHARTER_BYTES = b"LILITH Identity Charter V1 - TEST_ONLY SYNTHETIC FIXTURE\n"
SYNTHETIC_CHARTER_VERSION = "1.0.0-test"
SYNTHETIC_IDENTITY_ID = "lid1." + hashlib.sha256(b"TEST_ONLY synthetic lilith identity 1").hexdigest()[:32]

# Real-world identity cues that must never stand in for the identity (charter §3).
OWNER_ID = "owner.ravindu.v1"
WITNESS_GENESIS = "ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4"
REGISTER_HEAD = "77752db11d80eef50eaeaa8b931d65a489bb919f9e864584fbf8d00746e2cec6"
SOUL_DIGEST = hashlib.sha256(b"TEST_ONLY SOUL.md persona projection").hexdigest()
HOST, MODEL, RUNTIME = "lilith-dev-01", "claude-opus-5-5", "hermes"

KNOWN_VALUES = frozenset({
    OWNER_ID, SA.LOGICAL_OWNER, SA.ROOT_KEY_ID, SA.EPOCH.random, str(SA.EPOCH.counter), WITNESS_GENESIS,
    REGISTER_HEAD, SOUL_DIGEST, HOST, "lilith-01", MODEL, RUNTIME,
})


def profile(**overrides) -> IP.IdentityProfileV1:
    value = dict(environment="test", lilith_identity_id=SYNTHETIC_IDENTITY_ID,
                 charter_version=SYNTHETIC_CHARTER_VERSION,
                 charter_digest=IP.charter_digest(SYNTHETIC_CHARTER_BYTES))
    value.update(overrides)
    return IP.IdentityProfileV1(**value)


def context(**overrides) -> IP.IdentityVerificationContextV1:
    value = dict(environment="test", trusted_profile=profile(), known_values=KNOWN_VALUES)
    value.update(overrides)
    return IP.IdentityVerificationContextV1(**value)


def candidate_value(binding=None, **extra) -> str:
    """A caller-built JSON value carrying a binding. Never admitted: used only to show that such a value cannot
    stand in for the admitted value."""
    value = {"statement": "TEST_ONLY caller-supplied candidate"}
    value[IP.BINDING_FIELD] = profile().binding() if binding is None else binding
    value.update(extra)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
