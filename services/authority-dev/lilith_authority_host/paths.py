"""Every fixed DEV_SYNTHETIC authority / witness / custody host path (PR-1S).

One source of truth for the signer, witness, root tooling, installer tests,
and the DR-5 / broker / denial proofs (tests pin each copy against this
module). Paths only; importing this creates nothing.

Two different roots with similar names are never inferred from each other
(preflight §16): `/etc/lilith-authority-custody` holds credential custody
slots (RR-26); `/var/lib/lilith-authority-custody` holds ceremony holds
(RR-34).
"""

from __future__ import annotations

# ------------------------------------------------------------- release ---
RELEASE_ROOT = "/opt/lilith-authority-dev"
RELEASES = RELEASE_ROOT + "/releases"
CURRENT_RELEASE = RELEASE_ROOT + "/current"

# ------------------------------------------------------ authority signer ---
AUTHORITY_USER = "lilith-authority-dev"
AUTHORITY_SERVICE = "lilith-authority-dev.service"
AUTHORITY_SOCKET_UNIT = "lilith-authority-dev.socket"
AUTHORITY_CONFIG = "/etc/lilith-authority-dev"
TRUST_DIR = AUTHORITY_CONFIG + "/trust"
REGISTRY_ROOT_ANCHOR = TRUST_DIR + "/registry-root.json"
WITNESS_ANCHOR = TRUST_DIR + "/witness-anchor.json"
REGISTRY_DIR = AUTHORITY_CONFIG + "/registry"
# SOURCE DETAIL: on-host copies of owner inputs (root-owned; count only when
# equal to the owner's off-host record, preflight §13, §22).
OWNER_INPUT_DIR = AUTHORITY_CONFIG + "/owner"
GENESIS_PIN_COPY = OWNER_INPUT_DIR + "/genesis-pin.json"
AUTHORIZATION_REGISTER_COPY = OWNER_INPUT_DIR + "/authorization-register.json"
AUTHORITY_CONFIG_SKELETON = (AUTHORITY_CONFIG, TRUST_DIR, REGISTRY_DIR, OWNER_INPUT_DIR)
AUTHORITY_STATE = "/var/lib/lilith-authority-dev"
AUTHORITY_LEDGER = AUTHORITY_STATE + "/authority_ledger.db"
AUTHORITY_RUNTIME = "/run/lilith-authority-dev"
AUTHORITY_OWNER_SOCKET = AUTHORITY_RUNTIME + "/owner.sock"
AUTHORITY_CREDENTIALS_RUNTIME = "/run/credentials/" + AUTHORITY_SERVICE

# ------------------------------------------------------ K-ACT custody ---
CREDSTORE = "/etc/credstore.encrypted"
CURRENT_SLOT = CREDSTORE + "/lilith-authority-dev.owner-actor.cred"
CUSTODY_ROOT = "/etc/lilith-authority-custody"
PREPARED_DIR = CUSTODY_ROOT + "/prepared"
RETIRED_DIR = CUSTODY_ROOT + "/retired"
HOST_KEY = "/var/lib/systemd/credential.secret"

# ------------------------------------------------------ hold store (RR-34) ---
HOLD_STORE_PARENT = "/var/lib/lilith-authority-custody"
HOLD_STORE = HOLD_STORE_PARENT + "/holds"

# ------------------------------------------------ recovery witness (RR-36) ---
WITNESS_USER = "lilith-recovery-witness"
WITNESS_SERVICE = "lilith-recovery-witness.service"
WITNESS_OWNER_SOCKET_UNIT = "lilith-recovery-witness-owner.socket"
WITNESS_SIGNER_SOCKET_UNIT = "lilith-recovery-witness-signer.socket"
WITNESS_UNITS = (WITNESS_SERVICE, WITNESS_OWNER_SOCKET_UNIT, WITNESS_SIGNER_SOCKET_UNIT)
WITNESS_CREDENTIAL_PARENT = "/etc/lilith-recovery-witness"
WITNESS_CREDENTIAL_ROOT = WITNESS_CREDENTIAL_PARENT + "/credentials"
WITNESS_BLOB = WITNESS_CREDENTIAL_ROOT + "/lilith-recovery-witness.witness.cred"
SUPERSEDED_CREDSTORE_WITNESS_BLOB = CREDSTORE + "/lilith-recovery-witness.witness.cred"
WITNESS_STATE = "/var/lib/lilith-recovery-witness"
WITNESS_RUNTIME = "/run/lilith-recovery-witness"
WITNESS_OWNER_SOCKET = WITNESS_RUNTIME + "/owner.sock"
WITNESS_SIGNER_SOCKET = WITNESS_RUNTIME + "/signer.sock"
WITNESS_CREDENTIALS_RUNTIME = "/run/credentials/" + WITNESS_SERVICE

# ------------------------------------------------------ fixed CLIs ---
SBIN = "/usr/local/sbin"
KEYGEN_CLI = SBIN + "/lilith-authority-keygen-dev"
LEDGER_CLI = SBIN + "/lilith-authority-ledger-dev"
HOLD_CLI = SBIN + "/lilith-authority-hold-dev"
VERIFY_CLI = SBIN + "/lilith-authority-verify-dev"
RECOVERY_CLI = SBIN + "/lilith-authority-recovery-dev"
WITNESS_OWNER_CLI = SBIN + "/lilith-recovery-witness-owner-dev"
FIXED_CLIS = (KEYGEN_CLI, LEDGER_CLI, HOLD_CLI, VERIFY_CLI, RECOVERY_CLI, WITNESS_OWNER_CLI)

# ---------------------------------------------------------- units ---
UNIT_DIR = "/etc/systemd/system"
TMPFILES_DIR = "/etc/tmpfiles.d"

# Host-installed copies of release members (installer stages; §23 evidence).
# The installer keeps its own copy (it runs as one streamed file); a test pins both.
AUTHORITY_UNIT_TARGETS = {
    "assets/lilith-authority-dev.service": UNIT_DIR + "/lilith-authority-dev.service",
    "assets/lilith-authority-dev.socket": UNIT_DIR + "/lilith-authority-dev.socket",
    "assets/lilith-authority-dev.tmpfiles.conf": TMPFILES_DIR + "/lilith-authority-dev.conf",
}
WITNESS_UNIT_TARGETS = {
    "assets/lilith-recovery-witness.service": UNIT_DIR + "/lilith-recovery-witness.service",
    "assets/lilith-recovery-witness-owner.socket": UNIT_DIR + "/lilith-recovery-witness-owner.socket",
    "assets/lilith-recovery-witness-signer.socket": UNIT_DIR + "/lilith-recovery-witness-signer.socket",
    "assets/lilith-recovery-witness.tmpfiles.conf": TMPFILES_DIR + "/lilith-recovery-witness.conf",
}
CLI_TARGETS = {"cli/" + path.rsplit("/", 1)[1]: path for path in FIXED_CLIS}
RELEASE_HOST_TARGETS = {**AUTHORITY_UNIT_TARGETS, **WITNESS_UNIT_TARGETS, **CLI_TARGETS}

# Every PR-1 authority / custody / witness object the broker preservation
# transcript, DR-5, and the denial proof name (preflight §9).
PR1_OBJECTS = (
    CUSTODY_ROOT, PREPARED_DIR, RETIRED_DIR, HOLD_STORE_PARENT, HOLD_STORE, WITNESS_CREDENTIAL_PARENT,
    WITNESS_CREDENTIAL_ROOT, WITNESS_BLOB, WITNESS_STATE, WITNESS_RUNTIME, TRUST_DIR, REGISTRY_DIR,
    OWNER_INPUT_DIR, AUTHORITY_LEDGER,
)
