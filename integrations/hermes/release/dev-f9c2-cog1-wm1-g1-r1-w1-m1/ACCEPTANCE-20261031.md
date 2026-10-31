# Motivation shadow on DEV, 2026-10-30: PASS, owner accepted

**The owner accepted this result on 2026-10-31, within its demonstrated shadow-only scope.**

**Result: every step passed, once, with no retry and no rollback.** The driver reported `DRIVE_COMPLETE`. DEV stays on m1 with World Model, Goals, Reasoning, Workspace and Motivation in shadow on `lilith_os` only.

**This validates shadow behaviour only.** Motivation Live has not been demonstrated. Motivation candidates did not enter the Workspace pool, no model saw any Motivation output, and both drives read `SATISFIED` because every store is empty.

**Workspace:** the owner accepted Workspace Shadow within its demonstrated scope on 2026-10-31, and its record merged as `6a059b0`. That record's title predates the acceptance and still reads "pending". This line supersedes it. Its limits stand: empty stores, untested live cognition, and an unexercised live rollback.

## Runtime and approval

| Item | Value |
|---|---|
| Host | `lilith-dev-01`, boot `cb0d71da...`, unchanged |
| Approval | one owner-approved run, synthetic `TEST_ONLY` messages only |
| Source | #299 `76c2fe8`, `CONTROL_ONLY_NO_DEPLOY` |
| Package | manifest `ede2d353...`, bundle `f1de4249...`; all 30 files verified before the run |
| Start | w1, gateway 384910, gate 385519, budget 3/5, ledger 29 lines, DB `88b76a79...` |

## Steps

| Step | Result |
|---|---|
| P0 preflight | PASS |
| S1 stop w1 | PASS |
| S2 transfer | PASS, bundle digest `b6c229a0...` |
| S3 install | PASS, verifier `--full` |
| S4 start m1 | PASS, gateway PID 392210 |
| S5 post-verify | PASS, 0 Core API requests before the test |
| S6 shadow test | PASS |
| S7 final | PASS |
| R1 to R4 return to w1 | not needed |

This was the first live use of the recovery driver. Only its forward path ran.

## S6, gate isolated

The gate was confirmed stopped (`inactive`, nothing listening on 9911) before any turn. It was started again afterwards with the same budget.

| Turn | Message | Records, in order | Core API |
|---|---|---|---|
| T1 | `TEST_ONLY what are my options for application 14?` | motivation `SATISFIED`, workspace `NO_CANDIDATE`, reasoning `OPTION_GENERATION`, cognitive, routing | 8 GETs |
| T2 | `TEST_ONLY what information is missing to resolve this?` | motivation `SATISFIED`, workspace `NO_CANDIDATE`, reasoning `UNCERTAINTY_ANALYSIS`, routing | 8 GETs |
| T3 | `TEST_ONLY which goal has priority?` | goal, routing | 0 |
| T4 | `TEST_ONLY hey how are you` | routing | 0 |

Every turn returned the expected failed-model message, because no provider was reachable.

## Validation

| Check | Result |
|---|---|
| Records | exact, in order, for all four turns |
| Text or identifiers | 0 message text, candidate ids, goal ids, `relatedGoalIds` or `resolutionConditions`, also re-checked independently in the log |
| Cross-turn identifiers | the 2 Motivation records have distinct `correlation_id` values |
| Core API | exactly the 16 expected GETs, all 200; no write |
| Provider | 0 FORWARDED, budget 3/5, ledger 29 lines `5764da8e...`, no reset |
| Database | logical `88b76a79...`, file `1d8a87e3...`, byte-identical; 0 rows everywhere; integrity ok; no focus trace |
| Request dumps | 8 to 12, all `lilith:lilith` 0600, 0 with message text; removed with their sessions by retention |
| FORGET | 0 intents, no marker |
| Services | gateway 392210, gate 392817, Core API 304463, broker 3411, authority 309023, witness 308690; 0 restarts; no failed units |
| Verifier | `F8_VERIFY_PASS full`, re-run after the test |

**Installed:** router `3ff4d3dc...`, `motivation.py` `fd6c1189...`, adapter `848fdb7d...`.

## Rollback readiness

The m1 and w1 releases are intact against their manifests. `/root/m1-install-20261030/payload` is root 0700 with all 7 files. The return to w1 passed the simulations, and has **not** been run live.

## What this proved

- m1 installs and starts on a real host from the sealed package.
- Motivation runs only inside a matching turn, with exact reads and no write on an empty store.
- Records stay content-free on the real gateway.
- Provider isolation held.

## What remains untested

- **Drive quality.** Empty stores give `SATISFIED`. The blocked-goal path is proven offline only.
- **Motivation Live**, and Motivation candidates in Workspace.
- **Any effect on a reply.** Every model call failed by design.
- **Real wording.** Only 4 synthetic turns ran.
- **The live return to w1**, and the driver's failure paths.
- **A goal added while running.** The verifier checks at start only. The record stays counts-only, but a focus read would write a trace.

## Effect on other packages

Gateway and gate PIDs moved, so the backup disposition package must be regenerated before use.
