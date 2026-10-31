# Isolated PROD rehearsal: runbook for Cutover 1 (PREPARED, NOT APPROVED, NOT RUN)

Detail for stages R0 to R9 of `dev-exit-v0.1/SNAPSHOT-REHEARSAL-DESIGN.md`. **Cutover 1 changes `app.py` and settings only, so this rehearsal is mostly proving that nothing else moved.** Nothing here touches PROD until its gate is approved. **The copy is never booted:** it holds real tokens and timers.

| Gate | Stages | Touches PROD? | Holds real data? |
|---|---|---|---|
| **G1 PROD baseline** | P1, P2 | cloud reads and a snapshot call; nothing on the host | no |
| **G2 Isolated VM** | R1 | no | no: a synthetic disk |
| **G3 Open the copy** | R3 to R9 | no | **yes: needs the Privacy decision** |

## G1: PROD baseline

| Step | Action | Stop if |
|---|---|---|
| P1 | Run `core-api-security-v0.1/prod_exposure_preflight.sh` | any rule, address or forwarding beyond the recorded ones |
| P2 | `gcloud compute disks snapshot lilith-01 --zone=asia-southeast1-b --snapshot-names=lilith-01-rehearsal-<date>`; confirm `READY` | any change to the VM or disk |

**The 2026-10-27 snapshot stays,** and the new one doesn't replace it. It's crash-consistent, as `state.db` has a live WAL.

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
