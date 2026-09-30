# Slice 15B2b-B1b-3e — Burned Identity Set Expansion (12 → 19)

Status:

- **The canonical, mechanically enforced burned set is now 19 identities.**
  It was 12.
- `lilith_owner_memory/burned_identities.py` enforces all 19. So does every
  path that uses it: the owner-freshness real-profile refusal (B-3) and the
  M-B1 phone check.
- No real authority material is involved. Every identity here is a
  throwaway TEST identity. M-B1 is NOT AUTHORIZED.

## 1. Rule

**Burn set.** A real-format identity joins the mechanically enforced set
when it is **declared burned** and its **value is recorded**. That means a
public-key fingerprint, a registry digest, or a genesis-witness digest that
was printed, exported, or written to owner-visible evidence.

**Ephemeral test keys.** These are random keys created inside a temporary
directory by unit tests, pty tests, or a simulation, and destroyed with that
directory without their value ever being printed or recorded.

- They are **not candidates** and cannot be enumerated.
- A fresh Ed25519 key colliding with one is negligible (a 2⁻¹²⁸ security
  level).
- To keep them in that class, simulations **must redact** every generated
  fingerprint and digest, and delete the generated material.

A simulation that prints a value makes it a recorded identity, which must
then be burned. Two did, below.

## 2. The 7 added identities

**B-4 path-correction WSL simulation** (2026-09-29).

- This was the offline run of the corrected B-4 block (`353c988f`),
  [staging record](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-staging.md)
  §2, item 3.
- That record declares offline-run identities "burned like the phone's".
- The run printed all six `BURNED` lines in full, but they were never put
  into the enforced set.

**M-B1 package WSL simulation** (2026-09-30).

- This was the clean case of the full-fidelity simulation of the first M-B1
  package ([M-B1 record](slice-15b2b-b1b3e-mb1-kroot-ceremony-package.md)
  §9).
- It printed the candidate's `publicKeySha256` in full. The record declared
  it burned but showed only an abbreviation.

## 4. Burned TEST identities

| Identity | Value |
| --- | --- |
| `b4SimRehearsalCliRootPublicKeySha256` | `5bd1520559e51f320688980164b20b1f2648cae0c4983ed6cb52f9bb5e88633b` |
| `b4SimRehearsalGenesisCandidateDigest` | `8185246e2502f82d073d517ba4180bc47950d90f9986da7c5b6ad26b77d0dfd5` |
| `b4SimRehearsalRegistryDigest` | `98c386c55aa7199ead49f8de8a27b80e0ffaffde6b1a3547004a3edf19885f5e` |
| `b4SimRehearsalRootPublicKeySha256` | `f064dd2e2cdd8fe4e81095b6cb58af76f88feeca1db74d9cf05cd071d263edff` |
| `b4SimSyntheticKActPublicKeySha256` | `e519c7e475e6f16b936fb74dd8ae5d970c117ce07a0e339e94da49d516e85882` |
| `b4SimSyntheticKWitPublicKeySha256` | `6c03535817deb8bf5bb60886d7f6d1d2e2a12a7edbad991b0129f5de48089616` |
| `mb1SimCandidateRootPublicKeySha256` | `ae5d8275dfcb39e7e1b4de435cfc7d3c4797d105fabc31d0305c5d9297025c6c` |

**Roles.**

- The five `…PublicKeySha256` values are SHA-256 fingerprints of raw 32-byte
  Ed25519 public keys: root, CLI root, K-ACT, K-WIT, and the M-B1 candidate
  root. They are refused in any key role.
- The registry digest is `rotation_contracts.registry_digest`.
- The genesis digest is the genesis-candidate / pin / genesis-witness
  digest.

The mappings are the verified B-3 ones
([B-3 record](slice-15b2b-b1b3e-b3-real-acceptance.md) §3).

## 5. Canonical count

| Source | Keys | Registry | Genesis | Total |
| --- | --- | --- | --- | --- |
| B-4 phone run 1 ([hold record](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-evidence-hold.md) §4) | 4 | 1 | 1 | 6 |
| B-4 phone run 2 ([acceptance](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-acceptance.md) §4) | 4 | 1 | 1 | 6 |
| B-4 path-correction WSL simulation (this record) | 4 | 1 | 1 | 6 |
| M-B1 package WSL simulation (this record) | 1 | 0 | 0 | 1 |
| **canonical total** | **13** | **2** | **2** | **19** |

Wherever a record says "12 burned identities", read it as the 12 **phone
rehearsal** identities. They remain burned, and they are a subset of the
canonical 19. The owner's B-5 statement ("all 12 rehearsal identities
remain permanently burned") is unchanged and still true.

**No real identity may match any of the 19.**

## 6. Unrecorded ephemeral identities (§1 class)

These are generated and destroyed without a recorded value, so they are
neither candidates nor enumerable:

- the unit and pty test keys of every test run;
- the M-B1 simulation's other generated candidates (the wrong-unlock and
  Replica-B-touched cases printed no fingerprint);
- any earlier offline run whose values were not printed.

The M-B1 review still compares the real fingerprint against the 19 by hand.
