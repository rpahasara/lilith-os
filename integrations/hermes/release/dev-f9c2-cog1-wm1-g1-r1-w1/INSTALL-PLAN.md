# Workspace shadow: preflight and install plan against r1 (PLAN, NOT APPROVED)

DEV only. This is the plan for a sealed package still to be built, on the pattern of the accepted r1 package. Nothing here has run.

## Blockers, in order

| # | Blocker | Owner of it |
|---|---|---|
| 1 | r1 shadow acceptance: evidence passed; owner acceptance pending | owner |
| 2 | Detector over-matching: 18 of 25 casual messages matched offline, and each match costs up to 5 reads under Workspace. Tighten it, or accept the read load and measure on real shadow records | owner decision |
| 3 | G3, if wanted, runs first. Its package pins the current DB reference | owner decision |
| 4 | `drafts` gate, [DRAFTS-BOOTSTRAP.md](DRAFTS-BOOTSTRAP.md): DB write, needs its own approval | owner |
| 5 | Candidate ids accepted as sensitive metadata ([README](README.md#candidate-ids-and-privacy)) | owner |
| 6 | #293 merged and classified. It is `CONTROL_ONLY_NO_DEPLOY` as long as it adds only new files | owner |

## Preflight, read-only

Same scope as the r1 `p0_r1.sh`, changed for this baseline:

| Check | Expected |
|---|---|
| Release, router, verifier | r1, `47579562…`, `verify --full` PASS |
| Lanes | World Model, Goals, Reasoning shadow; Workspace and later lanes `false` |
| DB | `88b76a79…`; `drafts` present with exactly its Core API columns; 0 rows in every table; `-journal` absent |
| Goal store | **0 rows.** The w1 verifier refuses otherwise |
| Services | gateway and gate on their current PIDs; Core API, broker, authority, witness unchanged; FORGET idle |
| Budget | current value, unchanged; no reset |
| Rollback | r1 release intact, g1 intact, `/root/r1-install-20261030/payload` present |
| Installer precondition | the r1 template renders to the installed r1 verifier. `install_w1.sh` proves this itself before any change |

## Sequence

| Step | Action | Changes |
|---|---|---|
| P0 | preflight | none |
| S1 | stop r1 gateway | one stop |
| S2 | transfer pinned bundle | root-only staging |
| S3 | `install_w1.sh install` | release, router, verifier |
| S4 | start on w1 | one start |
| S5 | post-verify | none |
| S6 | gate-stopped test, as in r1 | gate stop and start, 4 turns |
| S7 | final | none |
| R1-R4 | `install_w1.sh revert` to r1, start r1 | rollback only |

## S6 expected results

Same gate-stopped method as r1, so no request can be forwarded. Unlike r1, this test **does** read the Core API.

| Turn | Message | Records, in order | Core API |
|---|---|---|---|
| T1 | `TEST_ONLY what are my options for application 14?` | workspace, reasoning, cognitive, routing | exactly the 5 reads |
| T2 | `TEST_ONLY what information is missing to resolve this?` | workspace, reasoning, routing | at most 5 reads, measured offline before sealing |
| T3 | `TEST_ONLY which goal has priority?` | goal, routing | 0 |
| T4 | `TEST_ONLY hey how are you` | routing | 0 |

**Pass needs all of:** exact records; 0 message text; candidate ids not printed; all reads 200 and no write; DB digest and file
stat unchanged, including `goal_trace`; budget and ledger unchanged; 0 FORWARDED; dumps content-free; same gateway PID; gate back
with its key.

## Failure rules

As r1: no retries, and a failed gate restart is reported, never improvised. S6 or S7 failure stops for an owner decision, unless the
DB changed or a write was seen, which makes the rollback immediate.

**Stop rule:** any `POST`, `PUT`, `PATCH` or `DELETE` to the Core API, or any change to the DB digest, is a failure even if the turn
looks correct.

## Limits

- The verifier checks the empty goal store at start only. A goal added later would let a focus read write a trace.
- The w1 test runs on empty stores, so it proves the plumbing and bounded reads, not salience quality.
