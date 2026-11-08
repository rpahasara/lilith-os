# Seven-lane coverage matrix

**Passing here doesn't make a lane production-ready.** Each column is a separate claim, and a lane only earns the ones with evidence. Last column first: **no lane is ready for a PROD compatibility rehearsal yet,** because the rehearsal's own prerequisites aren't met.

| Lane | Offline unit | Offline integration | DEV shadow | DEV live, synthetic state | Populated store | Ready for PROD rehearsal |
|---|---|---|---|---|---|---|
| World Model | yes | yes, seven lanes | yes, wm1 onward | **yes:** one synthetic belief, S1-W and supplemental; S2 stays FAIL | source only, with one synthetic belief on DEV | no |
| Goals | yes | yes | yes, g1 onward | **yes:** Goals Live, one synthetic goal | source only | no |
| Reasoning | yes | yes | yes, r1 onward | **no** | source only | no |
| Global Workspace | yes | yes | yes, w1 onward | **no** | source only: 4 candidates | no |
| Motivation | yes | yes | yes, m1 onward | **no** | source only: a `MILD` drive | no |
| Planning | yes | yes | yes, p1, accepted 2026-10-31 | **no** | source only | no |
| Ethics | yes | yes | **no: e1 not installed** | **no** | source only | no |

"Yes" for DEV shadow means the empty store, except where stated, and no model saw a turn. **Reply quality is unmeasured for every lane.**

## Evidence levels used

| Level | Meaning |
|---|---|
| **HOST** | ran on DEV |
| **SOURCE** | real gateway, adapter and Core API in-process, on the bytes the e1 verifier pins |
| **SIM** | real scripts on a fake host, or real installers in a sandbox |
| **PLANNED** | not run |

## Requested coverage

| Area | Evidence | Where |
|---|---|---|
| World Model grounding | HOST for one belief; SOURCE across seven lanes | `test_seven_lanes.py`, `Stores` |
| Goals detection, priority | HOST (T3); SOURCE | `Ownership`, `Stores` |
| Reasoning detection, precedence | HOST (T1, T2); SOURCE | `Ownership`, 27 messages |
| Workspace candidates | SOURCE on a populated store; HOST only `NO_CANDIDATE` | `test_populated_stores_reach_the_lanes` |
| Motivation state | SOURCE on a populated store; HOST only `SATISFIED` | same |
| Planning detection, snapshot | HOST (T5, T6); SOURCE | `Ownership`, `test_p1_planning.py` |
| Ethics detection, concern types | SOURCE only | `test_ethics_hardening.py`, three corpora |
| Multiple intents | SOURCE only, 4 messages pinned. **The first intent wins; the second goes unanswered** | `Ownership` |
| Unrelated messages | HOST few; SOURCE 13 | `Ownership` |
| Empty store | HOST six lanes; SOURCE seven | `test_an_empty_store_never_changes` |
| Synthetic populated store | SOURCE only | `Stores` |
| Read-only behaviour | HOST empty only. SOURCE populated: only `goal_trace` grows, and #306's flag stops that | `Stores`, `test_populated_reads.py` in #306 |
| Exact bounded Core API calls | HOST for six turns; SOURCE for all ten, route by route | `ExactReads` |
| Content-free logs | HOST six lanes; SOURCE both stores with canaries | `test_records_stay_private_on_both_stores` |
| Identifier and cross-session privacy | SOURCE: the same message in two sessions shares no id or long hash | `Identity` |
| Provider fallback prevention | HOST: gate down, 0 forwarded. SOURCE: no socket to the gate or off-host | `Budgets` |
| Rollback | SIM only: `sim_install_e1.sh`, `window_sim_e1.sh`. **No return has run live on any release** | package |
| Release integrity | SOURCE: suite bytes equal the e1 pins. SIM: verifier negatives | `ReleaseBytes`, `test_e1_verifier.py` |

**Run:** `python -B integrations/hermes/proposals/cross-lane-v0.1/run_all.py`

## What would move the columns

| Column | Needs |
|---|---|
| DEV shadow for Ethics | e1 window |
| DEV live, synthetic | a model window for each lane, A3 |
| Populated store on a host | synthetic rows on DEV, under Privacy's rules, or the rehearsal copy, A2 |
| Ready for PROD rehearsal | FORGET scope, auth wired, Command Center header, signed lane modes: see `proposals/dev-exit-v0.1/` |
