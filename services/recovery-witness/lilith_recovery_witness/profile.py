"""Fixed DEV_SYNTHETIC RecoveryWitness identity (PR-1S).

The identity values are the pure `pr1_bootstrap` witness profile (keyId,
credential name, RR-36 credential source, state) plus the fixed OS identity
and sockets. Nothing is read from a file, the environment, or the network.
"""

from __future__ import annotations

from lilith_authority_host import paths as P
from lilith_owner_memory import pr1_bootstrap as B

PROFILE = B.DEV_SYNTHETIC_WITNESS_PROFILE
ENVIRONMENT = PROFILE.environment
WITNESS_KEY_ID = PROFILE.witness_key_id
CREDENTIAL_NAME = PROFILE.credential_name
CREDENTIAL_SOURCE = PROFILE.credential_path

SERVICE_USER = P.WITNESS_USER
SERVICE_GROUP = P.WITNESS_USER
SERVICE_UNIT = P.WITNESS_SERVICE
STATE_DIR = P.WITNESS_STATE
RUNTIME_DIR = P.WITNESS_RUNTIME
OWNER_SOCKET_PATH = P.WITNESS_OWNER_SOCKET
SIGNER_SOCKET_PATH = P.WITNESS_SIGNER_SOCKET
# systemd exposes a unit's credentials only here, only to the unit uid.
CREDENTIALS_DIRECTORY = P.WITNESS_CREDENTIALS_RUNTIME

# The authority signer is the only non-root peer, and only on the signer socket.
SIGNER_PEER_USER = P.AUTHORITY_USER
# Principals that must never share the witness uid or gid.
DISTINCT_PRINCIPALS = ("lilith", "lilith-memory-broker", "lilith-memory-relay", P.AUTHORITY_USER)
