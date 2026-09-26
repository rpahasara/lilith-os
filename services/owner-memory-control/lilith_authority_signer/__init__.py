"""15B2b-B1b-3b TEST-ONLY authority-domain (broker) signer.

This package is the authority side of the B1b-3 custody split. It is kept
physically separate from `lilith_owner_memory`, which holds only contracts,
public-registry verifiers, and the L04 V2 admission adapter. Nothing in
`lilith_owner_memory`, `services/core-api`, or the memory broker imports it.

Importing this package creates no key, ledger, file, network connection, or
authority. A signer exists only when a caller constructs one with an
in-process TEST_ONLY key object; this package never derives, loads, or stores
private key material itself.
"""
