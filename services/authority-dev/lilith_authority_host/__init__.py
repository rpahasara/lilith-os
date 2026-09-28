"""15B2b-B1b-3e PR-1S: fixed DEV_SYNTHETIC host paths and read-only observers.

Record: docs/architecture/slice-15b2b-b1b3e-pr1s-runtime-wiring.md.

Shared by the authority signer (`lilith_authority_dev`), the recovery
witness (`lilith_recovery_witness`), and the root tooling
(`lilith_authority_root`), so none of them imports another service's
runtime. Everything here READS: fixed paths only, no symlink following, no
repair, no key material, and no private credential path is ever opened
(CURRENT and the K-WIT blob are stat/hash observations in root tooling only).

    observation != authority
"""

__all__ = ("paths", "inputs", "store_observer")
