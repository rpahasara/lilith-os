"""15B2b-B1b-3e B-3: the burned B-4 rehearsal identities (pure, offline).

Records: docs/architecture/slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-evidence-hold.md §4 (run 1) and
docs/architecture/slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-acceptance.md §4 (run 2).

The two S25 Termux rehearsals created throwaway TEST identities that are
permanently burned. This module lets the real owner-freshness path refuse
them mechanically. Refusing a burned identity grants nothing: a fresh
identity passes this check and still faces every other gate.

    burned != revoked in any registry;  not burned != trusted

Mapping (verified against the rehearsal source):

- `*PublicKeySha256` = SHA-256 of the raw 32-byte Ed25519 public key, as
  `root-keygen`, `witness_publication`, and the K-ACT `publication` compute
  it. In the real path the same raw keys appear as the trust inputs'
  registry-root key, the witness-anchor key, and the registry key records.
  A burned key is refused in **any** of those roles.
- `rehearsalRegistryDigest` = `registryHead.registryDigest` =
  `rotation_contracts.registry_digest(registry)`. In the real path it is the
  digest of a trust-input registry and the `registryDigest` of a witness.
- `rehearsalGenesisCandidateDigest` = `pr1_bootstrap.candidate_digest` =
  SHA-256 of the V2 signed-field bytes, which is exactly `witness_v2_digest`
  of the committed genesis witness. `reproduce` writes it as the
  `OwnerGenesisPinV1.genesisWitnessDigest`, and `candidate_pin_reason`
  requires that equality. So it is refused as the pin digest and as the
  chain's genesis witness digest.
"""

from __future__ import annotations

import hashlib
from typing import Iterable

# run 1 (hold record §4) and run 2 (acceptance record §4); each run burned six
BURNED_PUBLIC_KEY_SHA256 = frozenset({
    # run 1
    "1273ab2ef653dab08042a278729bb70812086a46ee2d5ad79272d044f5ba3d95",   # rehearsalCliRootPublicKeySha256
    "d68033f06e49b3de6ea6f30b7cbd9c8c2fefd266ff961f4a7d4819e9c99a3def",   # rehearsalRootPublicKeySha256
    "a20368b64e6168c0cb77f054e63edb3b705f7c1053536a88a92c957579dd7ce0",   # syntheticKActPublicKeySha256
    "e1320162d98565e1f946cf287bb3b5fa0e162301e29dd60bae5596f7dfb03654",   # syntheticKWitPublicKeySha256
    # run 2
    "0ca5c028fe5dd3c34b7ee56fd93a6eeba9a11a66b7e13ca086eb5ae218208b99",   # rehearsalCliRootPublicKeySha256
    "40cfefff370ce490ad1861d1e2ed9b3f1f43e8fb1573453766689b22a5a31242",   # rehearsalRootPublicKeySha256
    "6ea7b60ef789123e5af8efb4e8b3de24adad13a3b151c3d80255b20740e82b41",   # syntheticKActPublicKeySha256
    "95cc52110f3d5975e825117de74bdf63c0cefa93bdc8ab81eed8e7879ac17822",   # syntheticKWitPublicKeySha256
})
BURNED_REGISTRY_DIGESTS = frozenset({
    "c97a689bf9b0c928fc5764b4d1cdff187009bc3464d82da43d4955e1c8a74034",   # run 1 rehearsalRegistryDigest
    "19a3a24b040509b730562f3edf691a0fb22ffbd28b217d495686a3dd1d3f139e",   # run 2 rehearsalRegistryDigest
})
BURNED_GENESIS_WITNESS_DIGESTS = frozenset({
    "c4c095d8b0bcb918555c291362bbcba84a8fe221f7d9de8717c629c1c4733e04",   # run 1 rehearsalGenesisCandidateDigest
    "abb70064a0ea21ebe12c8281eca0212add1467d62eb55992ab7a7f6bc5d5cc01",   # run 2 rehearsalGenesisCandidateDigest
})

BURNED_REHEARSAL_IDENTITY = "BURNED_REHEARSAL_IDENTITY"


def burned_identity(*, public_keys: Iterable[bytes] = (), registry_digests: Iterable[str] = (),
                    genesis_witness_digests: Iterable[str] = ()) -> str | None:
    """The first burned identity found, as `role:value`, or None."""
    for key in sorted(public_keys):
        fingerprint = hashlib.sha256(key).hexdigest()
        if fingerprint in BURNED_PUBLIC_KEY_SHA256:
            return f"publicKeySha256:{fingerprint}"
    for digest in sorted(registry_digests):
        if digest in BURNED_REGISTRY_DIGESTS:
            return f"registryDigest:{digest}"
    for digest in sorted(genesis_witness_digests):
        if digest in BURNED_GENESIS_WITNESS_DIGESTS:
            return f"genesisWitnessDigest:{digest}"
    return None
