# Isolated PROD snapshot rehearsal: design (PROPOSAL, nothing created)

Serves A8, A29, A30 and A31, and details section 9 of the roadmap. **Nothing here has been run. No PROD access, no copy of real data and no runtime change happens until the owner approves each gate below.**

**What it must show:** PROD's identity, real memories, goals and current behaviour survive the migration, and a failure can be undone in a measured time.

## The hazard that shapes the design

**A PROD copy isn't inert.** Booted as it is, it would use the real Telegram and Discord tokens, taking messages from PROD's own bots. Its timers would send a real morning brief, and its lanes would spend real provider money. So:

**The copy is never booted from.** It's attached as a data disk to a new rehearsal VM, and only reviewed files are copied out of it. Nothing on it starts by itself.

## Isolation

| Rule | How it's enforced | Proved by |
|---|---|---|
| No path to PROD or the internet | New VPC with no external IP, no NAT, no peering; deny-all egress | A failed outbound probe, recorded before real data is attached |
| No credentials | `.env`, `auth.json`, `*.env`, Google tokens, the WhatsApp session and the secrets bundle are excluded by name | A scan of the working tree: names only, never values |
| Authority keys | Excluded from the working tree; the rehearsal uses its own throwaway keys | Fingerprints differ from PROD's recorded metadata |
| No provider | Provider gate absent or stopped; the baseline uses captured prompts only | 0 forwarded |
| No operator shortcuts | One named identity, IAP only, logged | The session log |
| Destruction | The disk, VM and evidence that holds content are destroyed under a separate approved procedure, and the result recorded | The deletion record |

**The copy holds real personal data,** so it needs its own Privacy decision. The evidence leaving the rehearsal is counts, digests and verdicts, never content.

## Stages

| Stage | What happens | Stop if | Approval |
|---|---|---|---|
| **R0** | Owner decisions from `PROD-PARITY-MATRIX.md`, and this design | anything unsigned | Owner |
| **R1** | Build the empty VPC and VM; prove isolation with a synthetic disk | any outbound success | Owner, infrastructure only |
| **R2** | Take a **fresh** PROD snapshot, on top of the 2026-10-27 one, which it does not replace. Snapshot API only; nothing on the host changes | PROD disk or VM state changes | Owner, separate |
| **R3** | Create a disk from the snapshot and attach it read-only. Re-read every count and hash | a count moved and isn't explained | Owner, opens real data |
| **R4** | Copy into a working tree, excluding the named credentials. Recover each SQLite file: the snapshot is crash-consistent and `state.db` had a live WAL. Run `integrity_check` | integrity failure, or a credential found | automatic |
| **R5** | **Baseline:** digests of every table, persona and profile hashes, the capability inventory, and the fixed prompt set with the provider off | the unchanged stack doesn't run | automatic |
| **R6** | Migrate a copy of the tree: Core API from `519b309`, additive schema only, Hermes, lanes per the signed table | any row or table changes unexpectedly | automatic |
| **R7** | Compare with R5, row by row | any unexplained difference | automatic |
| **R8** | **Keep-deleted:** seed synthetic canaries beside the real data, erase only the canaries' scope on a **further** copy, restore, replay, then fire both rebuild routes and a simulated mail redelivery | a canary returns, or a real row is lost | Owner: the FORGET candidates need PROD's table list first, and a scoped erasure, which doesn't exist yet |
| **R9** | Roll back to the R5 tree, timed. Re-run R7 against the baseline | not byte-identical, or longer than the agreed limit | automatic |
| **R10** | Model window, only if separately approved: bounded budget, synthetic owner prompts, on the copy | budget reached | Owner, separate budget |
| **R11** | Record, then destroy | | Owner |

**Any unexplained difference stops the plan.** Nothing is corrected in place and retried: a fix goes through review, and the rehearsal starts again from R4.

## What "preserved" means

| Asset | Pass |
|---|---|
| Persona, `SOUL.md` | Hash `d082db5a...` unchanged; the fixed prompt set judged by the owner, before and after |
| User profile, `USER.md` | Hash `6d7804ef...` unchanged, or the signed decision applied |
| Conversation history | Row count and per-table digest equal; FTS answers the same synthetic query |
| Real memories | L04 stays 0 rows, L18's 3 candidates unchanged. "Memory" on PROD today means `USER.md`, `state.db` and the World Model, not L04 |
| World Model | 31 beliefs, 93 evidence, 93 trace, cursor 17, row-identical; a working-memory read returns the same belief keys |
| Goals | 3 goals, same states and revisions; focus is the same goal; `goal_trace` stays 11 with `LILITH_OS_FOCUS_READ_ONLY=1` |
| Tasks, drafts | 7 and 10, row-identical |
| Current functionality | Each PRESERVE row in the matrix has a recorded pass, and each DISABLE row a signature |

## What must be ready first

- `core_erasure.ALLOWED_TABLES` built from the real PROD table list. It refuses PROD's schema today, on purpose: `os_audit_log` isn't decided.
- Message tombstones in the extractor, and every watcher off on the copy, so nothing re-delivers.
- The Hermes adapter sending the read header. Without it, enforced read auth leaves every lane reading nothing, with no visible error.
- Provider-bound prompts captured and measured: DEV's prompts never held real rows.
- Core API on the rehearsal VM with read and write auth enforced. The VM has no route in, so the bind isn't what protects it.
- `LILITH_OS_FOCUS_READ_ONLY=1`. The offline sweep on a PROD-shaped store shows focus is the only GET that writes, and that the flag stops it.
- The identity prompt set, fixed and reviewed **before** any baseline runs, so it can't be tuned to the result.
- A scripted, offline dry run of R3 to R9 on a synthetic disk of PROD's shape.

## Not proven by a rehearsal

- That OAuth, Telegram or Discord work: credentials are absent by design.
- Real provider behaviour, unless R10 runs.
- Anything about PROD after the snapshot was taken. Cutover needs a final fresh snapshot.
