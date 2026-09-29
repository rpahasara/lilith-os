# Slice 15B2b-B1b-3e — B-4 Decision: K-ROOT Custody and Genesis-Pin Topology

Status:

- **OWNER DECISION RECORDED** (2026-09-29), **DEV_SYNTHETIC only**: Option **A1**
- Closes the B-4 **custody topology** question of the
  [PR-1B eligibility review](slice-15b2b-b1b3e-pr1b-eligibility-review.md)
- **Real K-ROOT generation NOT authorized.** A Termux capability
  rehearsal (throwaway TEST key) is authorized for **preparation and review
  only**; see the [rehearsal preparation](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal.md)
- `LIVE_MUTATION = NONE`; no DEV, phone, or replica contact
- **PR-1B remains `PR1B_NOT_ELIGIBLE`**: B-3 and B-5 are open, and the
  rehearsal must be reviewed before the real M-B1

```text
owner-side != agent-independent
custody decision != K-ROOT exists != K-ROOT authority
genesis-pin storage != freshness replica storage
```

## 1. Owner statement (verbatim)

> I choose B-4 custody Option A1 for LILITH DEV_SYNTHETIC.
> K-ROOT will be generated and retained only in S25 Termux private storage. The K-ROOT passphrase will be entered only on the S25 and will not be entered or stored on the agent-reachable laptop.
> The S25 copy of the K-ROOT public anchor and `publicKeySha256` is the authoritative owner fingerprint copy. The laptop may hold a working public copy only. No public repository mirror is required at this stage.
> The two M-B8 owner genesis-pin copies will be:
>
> * P-A: a dedicated owner pin directory on the laptop, outside Replica A and its parent.
> * P-B: a dedicated Termux-private pin directory on the S25, outside Replica B and its parent.
>
> The public `reproduce` inputs required to re-derive the genesis pin will be retained on both devices.
> I accept the availability concentration that K-ROOT, Replica B, and pin B reside on the S25. Phone compromise is a K-ROOT compromise and requires STOP. Phone loss after lineage binding may require re-bootstrap. This acceptance does not claim phone-compromise resistance.
> I do not authorize generation of the real K-ROOT yet.
> Before M-B1, I authorize preparation and review of a Termux capability rehearsal using only a throwaway TEST key and synthetic inputs for `root-keygen`, `registry-v1`, and `reproduce`. The rehearsal must leave no real authority material and must be separately reviewed before the real M-B1 ceremony.
> This decision closes B-4 custody topology only. It does not lift `REAL_ACCEPTANCE_ENABLED`, does not authorize PR-1B execution, does not create K-ROOT, K-WIT, a genesis pin, record 1, or First Memory.

## 2. Chosen topology

**K-ROOT private key.**

| Item | Decision |
| --- | --- |
| generation and retention | S25, Termux private storage only. `root-keygen` runs on the phone from a reviewed bundle. The tool writes exactly one encrypted PKCS#8 file (`O_EXCL`, `0600`) and no temporary copy |
| passphrase | entered only on the S25 (`getpass`), never entered or stored on the laptop |
| signing (M-B3 and later transitions) | `registry-v1` runs on the phone. The inputs (K-ACT publication) and outputs (signed registry) are public |
| DEV | K-ROOT is never present on DEV. DEV receives only the public anchor and the signed registry |
| backup | **none** (A1). Loss follows T-10 and §4 |
| "owner workstation" | the tool docstring says the tool runs on the "owner workstation". For K-ROOT, that device is the **S25** |

**K-ROOT public identity.**

- **Canonical form:** `publicKeySha256`, the lowercase hex SHA-256 of the
  32-byte raw Ed25519 public key, plus the `TrustedRegistryRootV1` anchor.
  Both are printed by `root-keygen`.
- **Authoritative copy:** on the S25, saved at generation.
- **Working copy:** the laptop may hold a public working copy only.
- **Public mirror:** none at this stage.
- **Owner confirmation:**
  1. at M-B1, from the phone screen;
  2. at M-B4, when the installed anchors must equal the owner copies;
  3. at record 1, check R1-3.

**Genesis pin (M-B8).**

| Copy | Location |
| --- | --- |
| P-A | a dedicated owner pin directory on the laptop, **outside Replica A and outside its parent** |
| P-B | a dedicated Termux-private pin directory on the S25, **outside Replica B and outside its parent** |
| on-host | `/etc/lilith-authority-dev/owner/genesis-pin.json`, the protocol copy, **not** an owner copy |

- **Retained on both devices:** the public `reproduce` inputs (registry v1,
  root anchor, witness anchor, `updatedAt`), so the pin can be re-derived.
- **Independent confirmation:** `reproduce` is run on the S25 and the
  `genesisCandidateDigest` is read on the phone screen. The equality chain
  is:

  ```text
  P-A = P-B = on-host copy = both reproduce results = host candidate (M-B7) = committed genesis (M-B9b)
  ```

  A mismatch at M-B9b is crash-matrix entry C-12, `REBOOTSTRAP_FORBIDDEN`:
  STOP.
- **No reviewed pin writer exists.** Create-only handling is procedural,
  and the equality chain makes any divergence visible.
- **Creating the pin does not make freshness `CURRENT`.** The register
  stays empty and `FRESHNESS_UNKNOWN` until record 1 is on both replicas.

## 3. Property established, and not established

**Established.** Compromise, rollback, or loss of the agent-reachable laptop
**alone** cannot:

- produce a K-ROOT signature;
- alter the S25 fingerprint copy or pin copy P-B;
- make owner freshness `CURRENT`.

**Not established:**

- resistance to compromise of the phone;
- the provenance of DEV-originated inputs. The laptop is the only channel
  to DEV. The defenses are the on-phone checks against accepted public
  values and the equality checks at M-B4 and M-B7.

**Accepted concentration.** K-ROOT, Replica B, and pin B are on the S25.

- **Phone compromise** is a K-ROOT compromise and requires **STOP**.
- **Phone loss** after lineage binding may require a re-bootstrap (R-1).
  Before M-B3 it only requires a new K-ROOT.
- The coupling is an availability coupling. Losing either device fails
  closed.

## 4. Loss and recovery (no automatic mechanism)

| Event | Consequence |
| --- | --- |
| K-ROOT lost | before M-B3: regenerate (C-2 applies before the fingerprint is recorded). After binding: no transitions possible; re-bootstrap (R-1), separately reviewed |
| one pin copy lost | re-derive with `reproduce` from the retained inputs; compare with the surviving copy and the on-host copy |
| both pin copies lost | re-derive only if the retained inputs survive. **Never** rebuild the pin from DEV alone; otherwise STOP. After record 1, the records carry `genesisWitnessDigest` |
| phone lost | K-ROOT, Replica B, and pin B are lost: `FRESHNESS_UNKNOWN`, then re-bootstrap (R-1). The tool never copies between replicas |
| laptop compromised | Replica A, pin A, and every laptop-relayed input are untrusted: STOP and re-verify from the phone. K-ROOT is unaffected |
| laptop rolled back | the replicas diverge, which fails closed; an older or missing pin A is detected |
| phone rolled back | a pre-ceremony archive removes B (`REPLICA_MISSING`); any other rollback diverges from A. The K-ROOT file is immutable |
| accidental extra K-ROOT copy | every copy the owner makes must be recorded. An unrecorded copy is custody debt or a suspected compromise. A second `root-keygen` run makes a **different** key, which the M-B4 anchor equality catches |

## 5. Points of no return (P3-5)

| Point | Step |
| --- | --- |
| K-ROOT becomes a custody commitment | end of **M-B1**, when the fingerprint is recorded off-host (E-21). Before that, crash-matrix entry C-2 (discard and regenerate) applies. It is bound to the lineage at M-B9b |
| public identity is owner-confirmed | **M-B1** (phone screen), re-confirmed at M-B4 and R1-3 |
| genesis pin is immutable | **M-B8** (`PIN_GENESIS`, `PONR_RECORD`), irrevocably bound at **M-B9b** (`PONR_LINEAGE`; mismatch = C-12) |

## 6. PR-1B blocker state

| # | Blocker | State |
| --- | --- | --- |
| B-1 | PR-3 tooling not accepted | **CLOSED** |
| B-2 | open risks not acknowledged | **CLOSED** |
| B-3 | source-level real-acceptance block (plus the guard and runbook text) | open |
| B-4 | K-ROOT custody and pin-copy topology | **topology CLOSED** (§1). The Termux rehearsal is prepared, not reviewed; its review is a precondition of the real M-B1 |
| B-5 | PR-1B not authorized | open |

**`PR1B_NOT_ELIGIBLE`.**

## 7. Nonclaims

This decision does **not**:

- create K-ROOT, K-WIT, a registry, a genesis pin, record 1, or an
  envelope;
- authorize real K-ROOT generation or PR-1B execution;
- lift `REAL_ACCEPTANCE_ENABLED`;
- claim resistance to phone compromise;
- change owner freshness. Real freshness remains `FRESHNESS_UNKNOWN`;
- apply to PROD.

## Explicitly not done

```text
NO K-ROOT GENERATED
NO K-WIT GENERATED
NO GENESIS PIN CREATED
NO DEV / PHONE / REPLICA CONTACT
NO REAL_ACCEPTANCE_ENABLED CHANGE
NO REAL RECORD 1
REAL FRESHNESS REMAINS UNKNOWN
PR-1B NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
```
