# Cross-lane test matrix

**Superseded for per-lane status by `COVERAGE-MATRIX.md`.** The findings below still stand.

**All seven lanes are not integrated.** DEV runs six in shadow since the p1 run of 2026-10-31; Ethics is a built candidate that no host runs. `test_cross_lane.py` runs all seven together on **source**, in one assembled home, on the real gateway, adapter and Core API, with no host, no model and no real traffic.

## Evidence levels

| Level | Meaning |
|---|---|
| **HOST** | ran live on DEV |
| **SOURCE** | ran here, on integrated source, on the real gateway, adapter and Core API |
| **SIM** | ran on a fake host or stubbed services |
| **PLANNED** | not run |

## Coverage

| Area | HOST | SOURCE | SIM | PLANNED |
|---|---|---|---|---|
| Intent ownership and precedence | 6 lanes, 6 messages (p1) | **7 lanes, 24 messages, pinned** | | 7 lanes on a host |
| False matches | few synthetic | 9 pinned here, plus each corpus | | real wording, which needs real traffic |
| Multiple intents in one message | none | 4 pinned here | | |
| Empty store | 6 lanes (p1) | 7 lanes | | 7 lanes on a host |
| Synthetic populated store | **no lane** | all lanes reached, with goals, a blocked goal, a task, a draft and a belief | | PROD-shaped data, A2 |
| No unintended writes | empty store only (p1) | empty: none. Populated: only `goal_trace` grows | | PROD-shaped data |
| Privacy-safe records | 6 lanes (p1), `app_id` null on every lane | all messages, both stores, canaries, no ids, no `app_id` | | real data on the snapshot rehearsal |
| Provider budget | 0 forwarded (p1) | no socket to the gate or off-host, on any turn. Core API: at most 6 reads, each route once | | a metered model window, A3 |
| Startup verification | p1 verifier | p1 verifier: refuses Ethics on, Planning off or live, changed pins | installer chain, 36/36; e1 verifier and installer, 36/36 | a seven-lane verifier on a host |
| Failure: Core API down or corrupt, lane raises | none | fails open on every message | window sim, 44/44 | live fault injection |
| Rollback | **no return has run live on any release** | | 36/36 and 44/44 | a live return, A34 |

## What the suite found

| Finding | State |
|---|---|
| **A message with two intents keeps only the first.** `what are my options for application 14, and which goal has priority?` records goal and cognitive; the options are not analysed | pinned as today's behaviour; acceptable in shadow, needs a decision before any Live lane |
| **`is it ethical to plan a follow up...` belongs to Ethics, not Planning** | pinned: a normative question wins |
| **A focus read doesn't always write a trace,** so the count is at most one per read. Goal, task, draft and belief rows never changed | pinned as "traces grow, nothing else does". The write itself remains PROD blocker P-5 |
| **Workspace and Motivation respond to data:** 4 candidates and a `MILD` drive on the synthetic store | first evidence of either lane on non-empty data, on source only |

## Not proven by any of this

Reply quality, model behaviour, real wording, PROD's data shape, performance, concurrency, or any live return to a previous release.

**Run:** `python -B integrations/hermes/proposals/cross-lane-v0.1/test_cross_lane.py`
