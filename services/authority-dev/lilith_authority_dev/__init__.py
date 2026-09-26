"""15B2b-B1b-3d L1 DEV_SYNTHETIC OWNER_ACTOR authority-signer source foundation.

Design: docs/architecture/slice-15b2b-b1b3d-dev-synthetic-custody-design.md.
Record: docs/architecture/slice-15b2b-b1b3d-l1-authority-signer-foundation.md.

This package is the distinct `lilith-authority-dev` signer. It is not the
memory broker, the application, Hermes, or a Privacy signer. It reuses the
accepted B1b-3a `OwnerEvidenceV2` / `AuthorityKeyRecordV1` contracts from
`lilith_owner_memory.authority_contracts`; it defines no other authority format.

Importing it creates no key, credential, ledger, socket, file, or authority.
It never generates, derives, embeds, or falls back to a private key. The
runtime reads private material from exactly one place: the systemd credential
`owner-actor-signing-key` in `$CREDENTIALS_DIRECTORY` of
`lilith-authority-dev.service`.

L1 status: SOURCE FOUNDATION ONLY. The service can never report authority
readiness and can never sign: the registry, witness, and durable authority
ledger that readiness depends on are not part of L1.
"""

__all__ = ("profile", "credential", "evidence_minter", "protocol", "core", "server")
