# Slice 15B2b-B1b-3e — M-B15 W14 post-RELEASED read-only verification package (DEV_SYNTHETIC)

**Status:** PACKAGE PREPARED FOR OWNER REVIEW. Repository only; nothing here ran against DEV. M-B15
(`EVALUATE_FULL_READINESS`) is **NOT AUTHORIZED**, and running `observe` needs its own owner authorization.
`CUSTODY = RELEASED`, `AUTHORITY = DARK`, `REGISTRY V1 = NOT EFFECTIVE`, `FIRST MEMORY = NONE`.

```text
W14_1 (technical observation) != M-B15 established != owner acceptance != activation != First Memory
root FULL_READINESS READY = local readiness facts only; issuance stays unwired (RR-39)
```

## 1. What M-B15 needs, and what this package covers

The accepted contract is sequencing step 17 `EVALUATE_FULL_READINESS`
([bootstrap sequencing](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md) §3, §10) and preflight §27 row M-B15
([PR-1 preflight](slice-15b2b-b1b3e-pr1-live-install-preflight.md)): FULL_READINESS READY from the root verifier,
read-only; activation dark; DR-5 and preservation; freshness `REQUIRED_CURRENT` + `ACCEPTANCE_COMPLETE`; READY reproduced
by the independent root verifier and the owner (§17, RR-38). This package adds only the missing read-only tooling for
the root part.

| M-B15 requirement | This package |
| --- | --- |
| root FULL_READINESS READY over the RELEASED store | **W14** (`observe`, then `classify`) |
| activation dark, issuance unwired | W14: package flags, E-19 inside the FULL package, the summary facts |
| independent reproduction | `classify`: re-judged off-host from the retained transcripts; package digests recomputed |
| owner freshness CURRENT (S25 Replica B) | **OUTSTANDING**: an owner act, not observed by W14 |
| preservation set under RELEASED | **OUTSTANDING**: see §5 (proposal only) |
| currency of the owner-input envelope | **OUTSTANDING**: owner decision (§4) |
| DR-5 at M-B15 time; the pending-reboot window | **OUTSTANDING**: sequencing §12 (never inside the window) |
| the M-B15 owner decision | **OUTSTANDING** |

## 2. Tooling (reuse first)

| File | Role |
| --- | --- |
| `services/owner-memory-control/tools/mb15_full_remote.py` (SHA-256 `9021982a3a498de467747d49dc2705153a3503eb902b6b0616cbe64ee27722d6`) | read-only host tail, last in the pinned W11 BOOT bundle after the unchanged E-22 tail. ONE HEALTH frame (the E-22 `package_report` capture: only from an exact RUNNING pair, bound before and after), then the release verifier's own `evaluate` in **both** modes over that frame and **one** hold observation; plus the W11 signer observation, restart boundary and ledger bytes. It judges nothing |
| `services/owner-memory-control/tools/mb15_operator.py` | subclasses the pinned M-B14 operator (transport, owner-inputs reader, hold `observe` / staging / units read-back and judge, expected RELEASED). Forms `pins`, `observe` (read-only DEV), `classify` (local). Holds the W14 judge |
| `services/owner-memory-control/tests/test_b1b3e_mb15_w14_full_readiness.py` | synthetic judge and flow tests; the REAL verifier on the synthetic PR-1 host before and after a REAL `release_initial` |

Unchanged: the W10 / W11 verifiers, the M-B11 / E-22 tails and operators, the M-B14 operator, the release verifier, the
DR-5 tools and target, and every historical HELD-based pin. No custody, issuance, activation or registry code changes.

## 3. W14 judge

`W14_1_RELEASED_FULL_READY_OBSERVED` only when every item holds; anything missing, malformed or different is
`W14_STOP` with reasons (never a default):

- the M-B14 read-back: all three observations exit 0; the hold store is **exactly** the RELEASED record
  `bb7576f4437fb61dd31adafe50ac56eba467c7f98b329b7149942e630f1ef003` (listing
  `c4cb131983b450d1e931d1121e5b125a98c2dc1625934db0ff0a5f3f661e195c`), so no HELD record remains; the staging path
  absent; signer `efbc0784…` / 128648 and witness `8cbfbed2…` / 127192 (E-22 completion);
- FULL_READINESS: status READY, reasons `[]`; every package check PASS (E-22 may be only the pinned owner-risk
  adjudication); package hold evidence = the RELEASED record; witness CONSISTENT, chain 1, head = genesis; loaded-key
  binding PASS; the package digest recomputed off-host equal;
- HOLD_RELEASE_ELIGIBILITY: NOT_READY with exactly `CEREMONY_HOLD:HOLD_NOT_HELD` (package:
  `E16_HOLD_STORE:CEREMONY_HOLD:HOLD_NOT_HELD`, `E17_READINESS:READINESS_NOT_READY`), as the real verifier produces on
  the synthetic host;
- authority dark: package `authorityGranted`, `activationGranted`, `issuanceWired` false (contract constants of
  `pr1_acceptance._package`: they catch only tampering or a contract change, never live activation); facts
  `authorityGranted`, `liveEntryAuthorized` not true. `issuanceReady` / `successorCurrent` are readiness fact names the contract sets at
  FULL READY; they are reported and are not darkness failures here (W11 HALTs on them only because FULL must not be
  READY while HELD; W11 is unchanged);
- the signer: RUNNING as that incarnation, `NRestarts` 0, static and loaded units, the release process from
  `releases/129f2be…`, credentials directory with exactly one name, root 0600 owner socket, effective restart
  boundary, HEALTH exactly H (still `NOT_READY`: the signer cannot observe the hold store) with key B3, bound to the
  incarnation; the ledger directory is exactly the database.

Every W14 result carries `mb15Established: false`, `authorityGranted: false` and the OUTSTANDING list.

## 4. Owner-input envelope and provenance (decision needed)

The release verifier judges E-19 (activation), the proof transcripts, the snapshot inventory and the off-host material
from the **owner-supplied** input envelope, not from a live read. `observe` accepts any envelope the pinned reader
admits and records its SHA-256; W14 does not judge its currency. Reusing the M-B12 envelope `3128a0a8…` would present
the M-B12-era activation line and proofs, and could still give W14_1. Whether M-B15 needs a fresh envelope is an owner
decision.

So every W14 result names that provenance explicitly:

| Field | Value |
| --- | --- |
| `activationDarkSource` | `OWNER_ENVELOPE_ACTIVATION_LINE` |
| `activationObservedLive` | `false` (W14 never observes activation) |
| `activationEvidence` | the activation line and `b1cUnchanged` as carried in the FULL package |
| `ownerInputChecks` | the status of E-07, E-08, E-09, E-19, E-20, E-21, E-22, E-23 (judged on envelope inputs) |
| `ownerInputBoundChecks` | the status of E-04, E-18 (a live observation compared with an owner pin or material) |
| `envelopeCurrency` / `ownerFreshness` | `NOT_JUDGED` / `NOT_EVALUATED` |

W14_1 is observation success only. It never satisfies the M-B15 `REQUIRED_CURRENT` freshness or the owner decision.

## 5. Preservation under RELEASED (proposal only; NOT adopted)

E-19 `PRESERVED_PINS` pins `heldSha256` = `c713ea1d…`, which is historical after M-B14 and HALTs by design. A
RELEASED preservation judgement would need a new owner-reviewed pin naming the accepted RELEASED record `bb7576f4…`
(and listing `c4cb1319…`) beside the unchanged historical pin. This package does not add or change any pin.

## 6. Off-host reproduction

`classify <outdir>` re-checks every transcript digest and the envelope, re-derives the expected RELEASED record,
re-judges the read-back from its transcripts, recomputes both package digests and re-runs W14, then requires an
existing `W14.json` to equal the re-judgement. The owner runs it from a clean control checkout; no DEV contact.

**Code identity.** `observe` records `codeIdentity` in `OBSERVATION.json`: this operator's SHA-256, the pin-table
digest, the `full` tail's pin and the SHA-256 of the exact stdin bundle (the payload digest the host itself checks
before running, exit 96 otherwise). `classify` rebuilds that bundle from its own checkout's pinned bytes (every tool
re-checked against its pin) and stops with `CODE_NOT_THE_OBSERVED_CODE` unless the identity is equal. A classifier
running other code, or a changed record, cannot reproduce the observation.

## 7. State

```text
M-B14 = COMPLETED / OWNER-ACCEPTED;  CUSTODY = RELEASED;  AUTHORITY = DARK;  REGISTRY V1 = NOT EFFECTIVE
W14 tooling = PREPARED (repository only, not run);  M-B15 = NOT AUTHORIZED
freshness, preservation, envelope currency, DR-5 at M-B15 time, reboot window, owner decision = OUTSTANDING
```
