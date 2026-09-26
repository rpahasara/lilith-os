"""DEV_SYNTHETIC OWNER_ACTOR signer profile and fixed OS identity (B1b-3d L1).

Every value here is taken from the B1b-3d design record (§4, §6, §9, §15).
Nothing is read from a file, the environment, or the network.

The profile is new and separately versioned. It does not widen the B1b-3b
TEST signer (`BrokerSignerConfigV1`, TEST-only) in place. It admits only
`environment=dev`, only `test-only.` key IDs carrying the `dev-synthetic`
label, and only the OWNER_ACTOR signing domain with the
OWNER_MEMORY_OPERATION evidence type. `prod` and `PRIVACY` are refused
structurally.
"""

from __future__ import annotations

from dataclasses import dataclass

from lilith_memory.owner_proof import OwnerProofError, _id
from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import contracts as K

PROFILE = "DEV_SYNTHETIC"
PROFILE_VERSION = 1
ENVIRONMENT = "dev"
SIGNING_DOMAIN = A.OWNER_ACTOR
EVIDENCE_TYPE = A.OWNER_MEMORY_OPERATION
KEY_ID_PREFIX = A.TEST_ONLY_ROOT_PREFIX  # "test-only."
KEY_ID_LABEL = ".dev-synthetic."
# Design §4 proposed K-ACT keyId. The registry record (L3a) must use it.
PROPOSED_K_ACT_KEY_ID = "test-only.dev-synthetic.actor.b1b3d.1"

# Fixed OS identity (design §6, §15). No other principal is used.
SERVICE_USER = "lilith-authority-dev"
SERVICE_GROUP = "lilith-authority-dev"
SERVICE_UNIT = "lilith-authority-dev.service"
SOCKET_UNIT = "lilith-authority-dev.socket"
# Principals that must never share the signer's uid.
DISTINCT_PRINCIPALS = ("lilith", "lilith-memory-broker", "lilith-memory-relay", "lilith-recovery-witness")

# Fixed paths (design §15). This package creates none of them.
RELEASE_ROOT = "/opt/lilith-authority-dev"
CONFIG_DIR = "/etc/lilith-authority-dev"
RUNTIME_DIR = "/run/lilith-authority-dev"
STATE_DIR = "/var/lib/lilith-authority-dev"
OWNER_SOCKET_PATH = RUNTIME_DIR + "/owner.sock"
CREDENTIAL_NAME = "owner-actor-signing-key"
CREDENTIAL_SOURCE = "/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred"
# systemd 255 exposes a unit's credentials only here, only to the unit uid.
CREDENTIALS_DIRECTORY = "/run/credentials/" + SERVICE_UNIT


class ProfileError(ValueError):
    """The profile was constructed outside its DEV_SYNTHETIC envelope."""


@dataclass(frozen=True)
class DevSyntheticSignerProfileV1:
    """What the OWNER_ACTOR signer binds that does not come from an owner proof.

    `authority_domain` keeps its B2a meaning (logical scope); it is never a
    signing-domain name. Registry version and recovery epoch are not profile
    values: they come from the signer's own published key record.
    """

    environment: str
    key_id: str
    authority_domain: str
    logical_owner_id: str
    policy_version: str

    def validate(self) -> None:
        if self.environment != ENVIRONMENT:
            raise ProfileError("the DEV_SYNTHETIC signer profile admits only environment=dev")
        if not isinstance(self.key_id, str) or not self.key_id.startswith(KEY_ID_PREFIX) \
                or KEY_ID_LABEL not in self.key_id:
            raise ProfileError("the DEV_SYNTHETIC signer profile admits only test-only dev-synthetic key IDs")
        try:
            _id(self.key_id, "key_id")
            _id(self.policy_version, "policy_version")
            if _id(self.authority_domain, "authority_domain") in A.SIGNING_DOMAINS:
                raise ProfileError("authorityDomain is a logical context, not a signing domain")
            K._pattern(self.logical_owner_id, K._LOGICAL_OWNER, "logical_owner_id")
        except OwnerProofError as exc:
            raise ProfileError(exc.code) from exc
