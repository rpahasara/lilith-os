# Isolated PROD rehearsal: runbook for Cutover 1 (PREPARED, NOT APPROVED, NOT RUN)

Detail for stages R0 to R9 of `dev-exit-v0.1/SNAPSHOT-REHEARSAL-DESIGN.md`. **Cutover 1 changes `app.py` and settings only, so this rehearsal is mostly proving that nothing else moved.** Nothing here touches PROD until its gate is approved. **The copy is never booted:** it holds real tokens and timers.

| Gate | Stages | Touches PROD? | Real data? |
|---|---|---|---|
| **G1 PROD baseline** | P1, P2 | cloud reads and a snapshot call; nothing on the host | **creates a copy of all of it,** unopened |
| **G2 Isolated VM** | R1 | no | none: a synthetic disk |
| **G3 Open the copy** | R3 to R9 | no | **opened: needs the Privacy decision** |

**The snapshot holds real PROD data, including sensitive files and credentials,** from the moment it exists. It's as sensitive as PROD itself, opened or not.

## G1: PROD baseline

| Step | Action | Stop if |
|---|---|---|
| P1 | Network and IAP review, as gates inside the sealed G1 preflight. It replaces `core-api-security-v0.1/prod_exposure_preflight.sh`, whose last command doesn't exist in `gcloud` | any unexpected finding: nothing is created |
| P2 | One snapshot, `lilith-01-rehearsal-20261101`, only on a fresh `PASS`, then a read-only verification | any failure: no retry |

**Package:** `C:\Users\edufo\lilith-g1-snapshot-20261101`, manifest `6f180f208f7a4514a4b19db6e4c3acb3dd362a62e850d8242cd6e9e5af4c3839`. `GO-G1.md` there is the approval text.

**G1 never boots, mounts, shares, exports or inspects the snapshot,** and the 2026-10-27 snapshot stays. **Retention:** keep until the rehearsal record is accepted and Cutover 1's return window has closed, no later than 2026-12-01 unless the owner extends it; deletion is manual, under its own approval.

**Coverage:** the snapshot copies the whole disk, and G1 proves PROD has only one, so the databases and `state.db`'s WAL are included as they stand on disk. It's crash-consistent, and only R4 can confirm that on the copy.

## G2: isolated VM

1. New VPC `lilith-rehearsal`: no external IP, no NAT, no peering, deny-all egress, IAP SSH only.
2. New VM, new service account with no roles. Boot image: stock Ubuntu, **never the snapshot.**
3. Attach a synthetic disk. A probe to the internet, the DEV VPC and PROD's address must all fail.

**Stop if** any outbound succeeds.

## G3: open the copy

| Stage | Action | Tool | Stop if |
|---|---|---|---|
| R3 | Disk from the snapshot, attached **read-only** to the VM, not as boot | `gcloud compute instances attach-disk --mode=ro` | any write path |
| R4 | Copy the tree to a working volume, leaving out everything `credentials` names, and throwaway authority keys in place of the real ones. `credentials` must then report none | `rehearsal_compare.py credentials` | a name is found |
| R4 | Confirm `app.py` is `bb0a4139` | `sha256sum` | **a different digest: the delta no longer applies** |
| R4 | Recover each SQLite file by opening a second copy, once, for the WAL; run the baseline tool on that | `rehearsal_compare.py baseline` | integrity not ok |
| R5 | Baseline: identity prompts' assembled text, with the provider off and the watchers absent | `IDENTITY-PROMPTS.md` | stack won't run |
| R6 | Install the drop-in, then `app.py` at the approved main SHA; enforcement and `LILITH_OS_TRUST_LOOPBACK=1`, `LILITH_OS_FOCUS_READ_ONLY=1` | as Cutover 1 | start failure |
| R7 | Baseline again, compare. **Only a pass is an empty list**, apart from new `conversation-evidence.db`, which must not appear with capture off | `rehearsal_compare.py compare` | any line |
| R7 | Router reads on the copy with real rows; capability inventory | parity matrix | any PRESERVE row fails |
| R9 | Restore `app.py`, timed, then compare again | same | not equal, or over the limit |
| R10 | Real replies, **only if the owner approves a budget** | `IDENTITY-PROMPTS.md` | budget reached |
| R11 | Record, then destroy under its own approval | | |

**R8, the erasure test, doesn't apply to Cutover 1** under R-13. It belongs to the FORGET work.

**Any unexplained difference stops the plan.** Nothing is fixed in place: a fix goes through review, and the rehearsal restarts at R4.

## Evidence leaving the copy

Counts, digests, verdicts and the names of differing tables. **Never rows, prompts or replies.**

## Not proven by this tool

Text the comparison doesn't cover: `state.db` is compared by digest, never read. Whether a reply sounds like LILITH needs R10 and the owner.

**Dry run:** `test_rehearsal_compare.py`, on a synthetic PROD-shaped store with the real Core API.
