# Slice 15B2b-B1b-3e — B-3: Real-Acceptance Switch and Burned-Identity Enforcement

Status:

- **Update: MERGED.** Rebased as `3ec04be` and merged at `cfa0b3e` (PR #121). **B-3 is CLOSED.** B-5 is unchanged; see the
  [B-5 decision packet](slice-15b2b-b1b3e-b5-pr1b-authorization-decision.md). The status lines below are historical.
- **`B3_PATCH_PREPARED_NOT_LANDED`**. The patch is reviewed on its branch and
  **intentionally not merged**.
- **B-3 stays OPEN on `main`** until this branch merges. B-3 closes only
  when it lands.
- This record is the reviewed B-3 change of the
  [PR-1B eligibility review](slice-15b2b-b1b3e-pr1b-eligibility-review.md)
  §8. It is prepared under the owner decision of 2026-09-29.
- **B-5 is unchanged. PR-1B is NOT AUTHORIZED. M-B1 is NOT AUTHORIZED.**
- There is no real K-ROOT, K-WIT, registry, genesis pin, or record 1. Real
  freshness is `FRESHNESS_UNKNOWN`. Both replicas hold 0 records.
- **Classification: `B3_PATCH_PREPARED_HELD_FOR_B5`**.

```text
B-3 closure != PR-1B authorization (B-5) != M-B1 != record 1 != freshness CURRENT
REAL_ACCEPTANCE_ENABLED != authority;  not burned != trusted
```

| Field | Value |
| --- | --- |
| Base `main` | `cf3a8291003ac55fd1e030caadd3895662f8e669` |
| Branch | `claude/15b2b-b1b3e-b3-real-acceptance-held` (not merged) |
| Source | `owner_acceptance.py` (switch), `owner_freshness_tool.py` (burned check at the real-input boundaries), new `burned_identities.py` |
| Tests | new `test_b1b3e_b3_real_acceptance.py`; `test_b1b3e_pr3_p36_acceptance_envelope.py` `BoundaryTests` rewritten |

## 1. Timing: held until immediately before B-5

The patch is **prepared and reviewed now, but held**. It is merged only
**immediately before the B-5 owner authorization decision**.

**Why.**

- B-3 is logically independent of B-5 (§4). But once merged, the real
  `append` accepts a well-formed, self-consistent lineage for
  `DEV_SYNTHETIC`.
- The trust inputs, chain, and pin are caller-supplied, and no source
  constant ties them to a real K-ROOT.
- **Replica A** is on the laptop's WSL, which agents can reach. It could
  then take an **irreversible**, create-only record from a mistaken or
  fabricated lineage. That grants no authority: Replica B stays on the
  phone, the result would be divergence, and freshness fails closed to
  UNKNOWN. But it would force Replica A to be rebuilt.
- Holding the patch keeps the interval in which real Replica A accepts
  irreversible appends as short as possible.

**Landing procedure** (at B-5, not before):

1. Rebase this branch on the then-current `main`. Re-run the full
   owner-memory-control suite.
2. The owner reviews and merges it. B-3 becomes CLOSED at the merge commit.
3. Only then does the owner make the B-5 decision (P1B-0), with PR-2
   revalidated immediately before `CHECK_ELIGIBILITY`.
4. Every PR-1B tool copy (the laptop tool for Replica A, and the phone
   bundle for Replica B) is built from a merged SHA that contains this
   change. No source change happens mid-sequence (eligibility review, B-3
   row).
5. Until the PR-1B sequence reaches `APPEND_RECORD_1_REPLICA_A` (after
   M-B9b), no real `append` or `append-envelope` is run.

## 2. Semantic change to `REAL_ACCEPTANCE_ENABLED`

| | Before (on `main`) | After (this patch) |
| --- | --- | --- |
| `REAL_ACCEPTANCE_ENABLED` | `False` | `True` |
| `REAL_ACCEPTANCE_BLOCK_REASON` | `P3_3_STORAGE_INCOMPLETE` (stale: P3-3 is complete) | `REAL_ACCEPTANCE_DISABLED_IN_SOURCE` |
| `real_acceptance_block("DEV_SYNTHETIC")` | the reason | `None` |
| `real_acceptance_gate(complete, DEV_SYNTHETIC)` | BLOCKED | MET; still BLOCKED when the acceptance is incomplete |
| `real_acceptance_gate(…, TEST_ONLY)` | `SYNTHETIC_PROFILE` | `SYNTHETIC_PROFILE`: a synthetic envelope never satisfies the real gate |
| real `append` / `append-envelope` | refused `REAL_ACCEPTANCE_DISABLED` | reach their full existing validation; burned identities refused (§3) |

**What the switch gates.**

- Exactly the two real-profile writes: the freshness `append` and
  `append-envelope`.
- It gates nothing in M-B1..M-B9b, `root-keygen`, the authority-dev
  ceremony, `evaluate_eligibility`, or the sequencer.
- `real_acceptance_gate` still has no production caller.

**Setting it back to `False`** is the reversible source-level disable. It
refuses both writes as `REAL_ACCEPTANCE_DISABLED` with the reason
`REAL_ACCEPTANCE_DISABLED_IN_SOURCE` (tested). No input, flag, or envelope
can change it; only a reviewed source change can.

## 3. Burned-identity enforcement

**The 12 identities.** Run 1 and run 2 each burned six:
([hold record](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-evidence-hold.md)
§4, [acceptance](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-acceptance.md)
§4).

- They are pinned in `burned_identities.py`.
- A test re-reads both records' §4 tables and requires exact equality with
  the source.

**Mapping.** Each was verified against the rehearsal and production source.
None is assumed.

| Rehearsal value | How it was computed | Real-path field(s) checked | Equivalence |
| --- | --- | --- | --- |
| `rehearsalRootPublicKeySha256`, `rehearsalCliRootPublicKeySha256` | `sha256(raw 32-byte Ed25519 public key)` (`root-keygen`) | `sha256(trust.registryRoot.publicKey)` | exact (the same raw key and hash) |
| `syntheticKWitPublicKeySha256` | `sha256(raw key)` (`witness_publication`) | `sha256(trust.witnessAnchor.publicKey)` | exact |
| `syntheticKActPublicKeySha256` | `sha256(raw key)` (K-ACT `publication`) | `sha256` of every trust-input registry key record | exact |
| `rehearsalRegistryDigest` | `registryHead.registryDigest` = `RC.registry_digest(registry)` | `RC.registry_digest` of each trust-input registry, and the `registryDigest` of every verified chain witness | exact (tested: `registry_head(r).digest == registry_digest(r)`) |
| `rehearsalGenesisCandidateDigest` | `pr1_bootstrap.candidate_digest(unsigned)` = `sha256(witness_v2_signing_bytes(unsigned))` | `pin.genesisWitnessDigest` and the chain's genesis-witness digest | exact. `reproduce` writes the pin as `OwnerGenesisPinV1(env, candidate digest)`, and `candidate_pin_reason` requires that equality. The candidate digest equals `witness_v2_digest` of the committed genesis witness (tested on a real TEST genesis witness) |

**Scope of the key check.**

- Keys are refused **in any role**: a burned K-ACT key used as a root or
  witness key is still refused.
- **No non-equivalent field was found.** No check was added on a field
  without a verified mapping.

**Entry points.** `_refuse_burned` covers every real-input boundary where
owner trust, chain, or pin inputs become a candidate, a package, or a
write:

- `propose-genesis`, `propose-accept`, `propose-reject`;
- `build-review-package`;
- `append`;
- `append-envelope`.

It runs **before** any candidate, package, record, or envelope is written,
and refuses with `BURNED_REHEARSAL_IDENTITY` and the role and value.

**What it does not cover.**

- The read-only `classify`, `inspect-chain`, and `compare-replicas` are not
  refused. Inspection writes nothing.
- The check applies to real profiles only (`DEV_SYNTHETIC`). **Fresh
  identities pass**, and still face every other gate: authenticity, pin
  binding, the replica state, and owner digest confirmation.

## 4. B-3 != B-5 (tested)

- **`evaluate_eligibility` has no B-3 input.**
  - Every precondition True except `pr1bAuthorized` gives
    `PR1B_NOT_ELIGIBLE`, with exactly `PR1B_NOT_AUTHORIZED`.
  - Injecting `realAcceptanceEnabled` gives `UNKNOWN_PRECONDITION`.
  - Only `pr1bAuthorized` (B-5) flips it.
- **The B-3 code never references PR-1B authorization.** Neither does the
  sequencer read `REAL_ACCEPTANCE_ENABLED`. No authority-dev ceremony tool
  (M-B1 tooling) imports `owner_acceptance`.
- **M-B1 is not authorized.**
  - With the switch on, the sequencer still refuses `GENERATE_K_ROOT`
    before `CHECK_ELIGIBILITY`.
  - `CHECK_ELIGIBILITY` refuses without B-5.
  - `APPEND_RECORD_1_REPLICA_A` is out of order.
  - The state stays `PR1B_INELIGIBLE`.
- **Freshness stays UNKNOWN, with 0 records.**
  - Empty replicas classify `FRESHNESS_UNKNOWN` on the real code path.
  - The register is `KNOWN_EMPTY`.
  - Two fresh `DEV_SYNTHETIC` replicas report `OWNER_REGISTER_EMPTY` with
    `[0, 0]` records.

## 5. Replica safety (tested)

- The P3-4 `RealStateGuard` is kept. Its docstring is updated; its
  behaviour is a permanent invariant.
- **On the real code path, one replica alone is never CURRENT.** After an
  append to A only (`PEER_PENDING`), the pair is not CURRENT, and A alone
  classifies `FRESHNESS_UNKNOWN`. `MINIMUM_REPLICAS = 2`.

## 6. Current-state and historical text

**Updated (current state):**

- the `owner_acceptance.py` docstring and comments;
- the `owner_freshness_tool.py` comments;
- the runbook header.

**Marked superseded (historical records kept as written):**

- the [P3-6 envelope record](slice-15b2b-b1b3e-pr3-owner-acceptance-envelope.md)
  §11;
- the [P3-3 acceptance](slice-15b2b-b1b3e-pr3-p33-storage-acceptance.md)
  §7.

The design-record tests that pin historical `P3_3_STORAGE_INCOMPLETE` text
(P3-3A, P3-4, P3-5, P3-6) still pass unchanged. That text correctly
describes the earlier state.

## 7. Blocker state

| # | Blocker | State |
| --- | --- | --- |
| B-1 | PR-3 tooling not accepted | **CLOSED** |
| B-2 | open risks not acknowledged | **CLOSED** |
| B-3 | source-level real-acceptance block (plus the guard and runbook text) | **OPEN on `main`**. This patch is prepared and held; it **closes on merge**, immediately before B-5 |
| B-4 | K-ROOT custody and the Termux rehearsal | **CLOSED** |
| B-5 | PR-1B not authorized | **OPEN** (unchanged) |

**`PR1B_NOT_ELIGIBLE`.**

## Explicitly not done

```text
B3_PATCH_PREPARED_NOT_LANDED
NOT MERGED
NO REAL K-ROOT
NO K-WIT
NO REGISTRY / GENESIS MATERIAL
NO REAL FRESHNESS RECORD APPENDED
B-5 UNCHANGED
PR-1B NOT AUTHORIZED
M-B1 NOT AUTHORIZED
FRESHNESS=UNKNOWN
FIRST MEMORY NOT AUTHORIZED
```
