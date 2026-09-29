# Slice 15B2b-B1b-3e — B-4 Termux K-ROOT Rehearsal: Acceptance (Run 2)

Status:

- **`B4_TERMUX_KROOT_REHEARSAL=ACCEPTED`**. **Run 2 is the accepted
  rehearsal.**
- **Run 1 keeps its historical status:**
  `B4_TERMUX_KROOT_REHEARSAL=PASS_OBSERVED`,
  `B4_REVIEWED_GATE_EVIDENCE=INCOMPLETE`. It is not accepted, and this
  record does not revise it.
- **B-4 is CLOSED:** both the custody topology decision and the mandatory
  S25/Termux rehearsal prerequisite.
- **Classification: `B4_TERMUX_REHEARSAL_ACCEPTANCE_READY`**.
- This record is documentation only. It makes no change to ceremony logic,
  gates, owner or phone tooling, or `REAL_ACCEPTANCE_ENABLED`. No phone
  contact was made to prepare it.
- **Real M-B1 NOT AUTHORIZED**; **PR-1B NOT AUTHORIZED**.

```text
rehearsal accepted != K-ROOT exists != M-B1 authorized != PR-1B authorized
```

| Field | Value |
| --- | --- |
| Control `main` | `ae903f3b2945c0b59993270d8b4d5e867c34f119` |
| Operator script | `b4_phone_commands.run2.sh`, SHA-256 `f0768b6e2b1faa120d1136c467cccfa99b2f2fa83f59ad719ddabc2b4d1b1fe9` ([run-2 record](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-run2.md) §3; the pinned diff against the reviewed `353c988f`) |
| Bundle | `lilith-b4-kroot-rehearsal-ff13bc6.tar`, `659c50a476c85ff9ed005af97bc70a48989a87890ec53b23f940d97901bee0b3` (unchanged) |
| Evidence received | `lilith-b4-rehearsal-2-evidence.tar`, laptop-received SHA-256 `84eb48e52c1f33ddb897dd1c4fce8a551e009f7e71c28ad4a80244c1b73d128e` |

## 1. Evidence review (laptop, read-only)

**Transport.**

- The hash `84eb48e5…128e` was computed on the laptop after the MTP copy.
- **Phone-to-laptop transport integrity of this tar is not claimed.** It is
  established only if the owner confirms that the phone-side pre-transfer
  SHA-256 was exactly this value.
- Evidence integrity within the tar is shown below.

**Contents.**

- The tar holds `lilith-b4-rehearsal-2/evidence/` (8 files, all owned by
  Termux uid `u0_a492`, mode `0600`), `evidence.sha256`, and the transcript.

**Integrity.**

- `evidence.sha256` has exactly **8** entries. It records Android absolute
  paths.
- The prefix `/data/data/com.termux/files/home/lilith-b4-rehearsal-2/` was
  deterministically rebased to `./`. After that, all 8 verify, with
  `sha256sum -c --strict`:
  - `g0.txt`
  - `gate.txt`
  - `rehearsal.exit`
  - `rehearsal.json`
  - `rehearsal.stderr`
  - `replica-b-after.txt`
  - `replica-b-before.txt`
  - `verify.txt`

| Check | Result |
| --- | --- |
| transcript | ends `RUN_EXIT=0`; **0** lines beginning `STOP` |
| token sequence | **exactly** the reviewed run-2 §5 order: `HOME_TERMUX_PRIVATE`, `TMP_TERMUX_PRIVATE`, `CRYPTOGRAPHY_OK`, `STAGING_ABSENT`, `TMP_NO_STALE`, `NO_KROOT_FILES_BEFORE`, `REPLICA_B_PRESENT`, `NESTED_REPLICA_ABSENT`, `REPLICA_B_BASELINE_OK`, `…tar: OK`, `SHA256SUMS: OK`, `BUNDLE_VERIFIED`, `SOURCE_COMMIT_OK`, `FILE_COUNT_OK`, `BUNDLE_IN_TERMUX_PRIVATE`, `exit=0`, `B4_KROOT_REHEARSAL=PASS`, `REHEARSAL_GATE_PASS`, `TMP_CLEAN`, `NO_KEY_FILE_ANYWHERE`, `BUNDLE_UNCHANGED`, `STDERR_EMPTY`, `REPLICA_B_UNCHANGED`, `TRANSPORT_COPY_REMOVED`, `RUN_EXIT=0` |
| `g0.txt` | `HOME_PRIVATE yes`, `TMP_PRIVATE yes`, Python `3.14.6`, `cryptography` `50.0.1`, `aarch64` |
| `rehearsal.exit` | `exit=0` |
| `rehearsal.stderr` | 0 bytes |
| `gate.txt` | first line `REHEARSAL_GATE_PASS`; exactly 6 `BURNED` lines; no `STOP` line; `ENV` Android / `aarch64` / Python `3.14.6` / `cryptography` `50.0.1`. The reviewed gate program, **re-run on the laptop against `rehearsal.json`, reproduces `gate.txt` byte for byte** |
| `verify.txt` | exactly `TMP_CLEAN`, `NO_KEY_FILE_ANYWHERE`, `BUNDLE_UNCHANGED`, `STDERR_EMPTY`, `REPLICA_B_UNCHANGED` |
| Replica B baseline | the reviewed `snap()` format, with the `parent lilith-owner-offline-dev-synthetic-01` line and `~/` paths |
| Replica B before and after | **byte-identical**; manifest `c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4`; records `0` before and after |
| Replica B continuity | the run-2 baseline equals the post-hoc collection's reviewed snapshot byte for byte: inodes `973613 / 973617 / 973618`, modes `700 / 600 / 700`, mtime `1790654695`. That is the same replica, unchanged since run 1's baseline |
| canonical path | `$HOME/lilith-owner-offline-dev-synthetic-01`; the old nested path remained absent (`NESTED_REPLICA_ABSENT`) |
| transport copy | `TRANSPORT_COPY_REMOVED`, after every gate and the seal |

Every run-2 acceptance criterion
([run-2 record](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-run2.md) §6)
is met, except transport integrity, which is pending owner confirmation.

## 2. Acceptance

> **`B4_TERMUX_KROOT_REHEARSAL=ACCEPTED`.**
>
> **What ran.** Run 2 of the B-4 Termux K-ROOT capability rehearsal ran on
> the S25 in Termux private storage, offline (airplane mode ON, USB
> unplugged). It used:
>
> - the unchanged bundle `ff13bc6` (`659c50a4…0b3`);
> - the final hard-stop operator script `f0768b6e…1fe9`, whose every
>   difference from the reviewed `353c988f` block is a pinned, tested
>   diff;
> - the canonical Replica B at `$HOME/lilith-owner-offline-dev-synthetic-01`.
>
> **The result.** It completed with `RUN_EXIT=0` and no STOP. Every reviewed
> pre-run and post-run gate printed its PASS token, in order.
>
> **What it proves.** `root-keygen`, `registry-v1`, and `reproduce` work on
> the S25 under Termux with a throwaway TEST key. Specifically:
>
> - the key was encrypted at rest, with mode `0600`;
> - overwrite and wrong-passphrase attempts were refused;
> - the function and CLI outputs agreed;
> - reproduction was deterministic;
> - cleanup was complete;
> - nothing was left in TMPDIR or `$HOME`;
> - the bundle was unchanged;
> - Replica B was byte-for-byte unchanged, with 0 records.
>
> **This closes only the B-4 mandatory rehearsal prerequisite.** Together
> with the custody topology decision, B-4 is CLOSED.
>
> **It does NOT mean** that any of these exists: a real K-ROOT, K-WIT,
> registry v1, a genesis pin, or owner freshness record 1. It does not mean
> freshness is CURRENT, and it does not authorize real M-B1, PR-1B, or
> First Memory.

## 3. Run 1 and run 2

| | Run 1 | Run 2 |
| --- | --- | --- |
| script | not the exact reviewed block: the snapshot lacked the `parent` line and `~/` paths; `g0.txt`, `verify.txt`, and `evidence.sha256` were never written | `f0768b6e…1fe9`, run as one file with a transcript |
| result | `PASS_OBSERVED`; gate reproduced; 6 identities burned | `ACCEPTED`; every reviewed run-time gate evidenced |
| reviewed-gate evidence | `INCOMPLETE` (it cannot be reconstructed; see the [hold record](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-evidence-hold.md) §5) | complete |
| post-hoc | the read-only collection was `ACCEPTED` (current safety and Replica B continuity; see the [run-2 record](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-run2.md) §1) | n/a |
| status after this record | **unchanged historical record**. It is not the accepted rehearsal, and it is not relied on | **the accepted rehearsal** |

Run 1's staging directory, the post-hoc check directory, and run 2's
staging directory stay on the phone as evidence. None holds a key.

## 4. Burned TEST identities (run 2)

These are **permanently burned**. They were created only as throwaway TEST
material. None may ever be used or accepted in any of:

- M-B1 or M-B2;
- the real registry v1;
- the witness genesis or genesis pin;
- record 1 or any acceptance envelope;
- any later lineage.

| Identity | Value |
| --- | --- |
| `rehearsalCliRootPublicKeySha256` | `0ca5c028fe5dd3c34b7ee56fd93a6eeba9a11a66b7e13ca086eb5ae218208b99` |
| `rehearsalGenesisCandidateDigest` | `abb70064a0ea21ebe12c8281eca0212add1467d62eb55992ab7a7f6bc5d5cc01` |
| `rehearsalRegistryDigest` | `19a3a24b040509b730562f3edf691a0fb22ffbd28b217d495686a3dd1d3f139e` |
| `rehearsalRootPublicKeySha256` | `40cfefff370ce490ad1861d1e2ed9b3f1f43e8fb1573453766689b22a5a31242` |
| `syntheticKActPublicKeySha256` | `6ea7b60ef789123e5af8efb4e8b3de24adad13a3b151c3d80255b20740e82b41` |
| `syntheticKWitPublicKeySha256` | `95cc52110f3d5975e825117de74bdf63c0cefa93bdc8ab81eed8e7879ac17822` |

- All six are distinct.
- None equals any of run 1's six. Run 1's remain burned too
  ([hold record](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-evidence-hold.md)
  §4).
- **The real M-B1 review must check that the real K-ROOT fingerprint, and
  every real identity derived later, is none of these twelve**, nor any
  offline pre-check identity.

## 5. Blocker state

| # | Blocker | State |
| --- | --- | --- |
| B-1 | PR-3 tooling not accepted | **CLOSED** |
| B-2 | open risks not acknowledged | **CLOSED** |
| B-3 | source-level real-acceptance block (plus the guard and runbook text) | **OPEN** |
| B-4 | K-ROOT custody and pin-copy topology, and the mandatory S25/Termux rehearsal | **CLOSED**: topology per the [decision](slice-15b2b-b1b3e-b4-kroot-custody-decision.md); rehearsal accepted here (run 2) |
| B-5 | PR-1B not authorized | **OPEN** |

**`PR1B_NOT_ELIGIBLE`** (B-3 and B-5 open).

- `REAL_ACCEPTANCE_ENABLED` is unchanged (`False`).
- Real M-B1 may be **prepared** only through a separate reviewed step after
  B-3.
- It is not authorized here.

The historical P3-3B status block ("Not executed") remains separate
historical-status debt.

## Explicitly not done

```text
NO PHONE CONTACT
NO PHONE MUTATION
NO REPLICA MUTATION
NO REAL K-ROOT
NO K-WIT
NO REGISTRY V1
NO GENESIS PIN
NO REAL RECORD 1
NO REAL_ACCEPTANCE_ENABLED CHANGE
FRESHNESS=UNKNOWN
PR-1B NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
```
