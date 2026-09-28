"""15B2b-B1b-3e PR-1S: the DEV_SYNTHETIC RecoveryWitnessV2 service (S-5 .. S-8, S-20).

Design: docs/architecture/slice-15b2b-b1b3e-pr1-live-install-preflight.md §10-§13.
Record: docs/architecture/slice-15b2b-b1b3e-pr1s-runtime-wiring.md.

The distinct `lilith-recovery-witness` service: its own account, its own
private key (K-WIT, `recovery-witness-signing-key`), its own state
(`/var/lib/lilith-recovery-witness`), its own units, its own failure
domain. It is not the authority signer and holds no K-ACT, K-ROOT, owner
WebAuthn, activation, or Privacy material.

K-WIT signs exactly one thing: `RecoveryWitnessV2` documents the pure
`rotation_contracts` / `witness_readiness` planners produced. There is no
generic signing interface and no OwnerEvidence, registry, authorization, or
Privacy signing.

    witness freshness != authority
    installed code    != enabled mutation
    service running   != current authority

Importing this package creates no key, credential, socket, file, or witness.
SOURCE PREPARED / NOT INSTALLED.
"""

__all__ = ("profile", "credential", "storage", "writer", "protocol", "core", "server")
