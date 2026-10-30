# Workspace shadow: preflight and install plan against r1 (PLAN, NOT APPROVED)

DEV only. This is the plan for a sealed package still to be built, on the pattern of the accepted r1 package. Nothing here has run.

## Blockers, in order

| # | Blocker | Owner of it |
|---|---|---|
| 1 | r1 shadow acceptance | **done**, owner-accepted 2026-10-30 (#294) |
| 2 | Detector candidate accepted: PR #295, merged into this branch | owner decision |
| 3 | G3 | **closed**: owner accepted it as partial evidence, no re-run (#297) |
| 4 | `drafts` gate, [DRAFTS-BOOTSTRAP.md](DRAFTS-BOOTSTRAP.md): DB write, needs its own approval | owner |
| 5 | Stable candidate ids removed from the log | **done in source** |
| 6 | #293 merged and classified. It is `CONTROL_ONLY_NO_DEPLOY` as long as it adds only new files | owner |

## Why Workspace depends on the detector

Workspace runs only inside a Reasoning match, so the detector sets its read load.

| Message set | Deployed false matches | Candidate false matches | Core API reads, at up to 5 each |
|---|---|---|---|
| Held-out casual, of 45 | 27 | 0 | up to 135 against 0 |
| Validation 2 work look-ups, unseen, of 17 | 0 | 1 | 0 against up to 5 |

Reads stay bounded and write nothing on an empty store. A focus read with a goal present does write a trace, which is why the verifier needs an empty goal store.

**This release now carries both changes** as members, with digests pinned in the verifier, installer and delta. If #295 changes, these pins move.

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
| Installer precondition | the r1 adapter and `workspace.py` are the expected bytes, and the r1 template renders to the installed verifier. `install_w1.sh` proves these before any change |

## Sequence

| Step | Action | Changes |
|---|---|---|
| P0 | preflight | none |
| S1 | stop r1 gateway | one stop |
| S2 | transfer pinned bundle | root-only staging |
| S3 | `install_w1.sh install` | release, router, verifier, adapter, `workspace.py` |
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
| T2 | `TEST_ONLY what information is missing to resolve this?` | workspace, reasoning, routing | exactly 5 reads, ending in `GET /os/world`, measured offline |
| T3 | `TEST_ONLY which goal has priority?` | goal, routing | 0 |
| T4 | `TEST_ONLY hey how are you` | routing | 0 |

**Pass needs all of:** exact records; 0 message text; no candidate id in any record; all reads 200 and no write; DB digest and file
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
