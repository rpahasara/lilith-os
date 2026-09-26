"""15B2b-B2a accepted-memory contracts and verifier, 15B2b-B1b-3a authority
evidence and key registry contracts, and the 15B2b-B1b-3b V2 owner-authority
chain and L04 V2 admission adapter (TEST-ONLY).

This package holds public verification material only. It never signs and never
imports the separate TEST signer package.

Importing this package creates no database, key, credential, network
connection, or authority. It requires `lilith_memory` (services/core-api) to be
importable; it never modifies `sys.path` itself.
"""
