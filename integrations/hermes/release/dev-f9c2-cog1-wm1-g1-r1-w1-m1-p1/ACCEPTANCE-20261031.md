# Planning shadow on DEV, 2026-10-31: PASS, awaiting owner acceptance

**The owner has not yet accepted this result.** Merging this record does not accept it.

**Result: every step passed, once, with no retry and no rollback.** The driver reported `DRIVE_COMPLETE`. DEV stays on p1 with World Model, Goals, Reasoning, Workspace, Motivation and Planning in shadow on `lilith_os` only. Every other lane is off.

**This validates shadow behaviour only.** Planning Live has not been demonstrated, no model saw any plan, and plan quality on real data is unknown because every store is empty.

## Runtime and approval

| Item | Value |
|---|---|
| Host | `lilith-dev-01`, boot `cb0d71da...`, unchanged |
| Approval | one owner-approved run, synthetic `TEST_ONLY` messages only |
| Source | #303 reviewed head `7a5aff8`, merge `8e35b7f`; real main run `CONTROL_ONLY_NO_DEPLOY`, `DEV_MUTATION=NONE`, boundary proof PASS |
| Package | manifest `fad6cfe5...`, bundle `fcf99739...`; all 30 files verified, and merged source equal to the bundle pins, before the run |
| Start | m1, gateway 392210, gate 392817, budget 3/5, ledger 29 lines, DB `88b76a79...` |

**How it ran:** the runbook said foreground. The driver ran detached instead, so a tool timeout could not stop it partway. Nothing else about the sequence changed, and each step ran once.

**A manifest detail:** `OWNER-APPROVAL.md` doesn't state the digest. The owner's approval gave its first 8 characters, and the computed digest matches them and the full value recorded when the package was sealed.

## Steps

| Step | Result |
|---|---|
| P0 preflight | PASS |
| S1 stop m1 | PASS |
| S2, S2b transfer | PASS, bundle digest `6391b5a7...` on the host |
| S3 install | PASS, verifier `--full` |
| S4 start p1 | PASS, gateway PID 400044 |
| S5 post-verify | PASS, 0 Core API requests before the test |
| S6 shadow test | PASS |
| S7 final | PASS |
| R1 to R4 return to m1 | not needed |

## S6, gate isolated

The gate was confirmed stopped (`inactive`, nothing listening on 9911) before any turn. It was started again afterwards with the same budget.

| Turn | Message | Records, in order | Core API |
|---|---|---|---|
| T1 | `TEST_ONLY what are my options for application 14?` | motivation `SATISFIED`, workspace `NO_CANDIDATE`, reasoning `OPTION_GENERATION`, cognitive, routing | 5 GETs |
| T2 | `TEST_ONLY what information is missing to resolve this?` | motivation `SATISFIED`, workspace `NO_CANDIDATE`, reasoning `UNCERTAINTY_ANALYSIS`, routing | 5 GETs |
| T3 | `TEST_ONLY which goal has priority?` | goal, routing | 0 |
| T4 | `TEST_ONLY hey how are you` | routing | 0 |
| T5 | `TEST_ONLY plan how to follow up on application 14 but do not do it` | planning `PLAN_PROPOSED`, 3 steps; routing | 6 GETs |
| T6 | `TEST_ONLY make a plan for dinner` | routing | 0 |

Every turn returned the expected failed-model message, because no provider was reachable.

## Validation

| Check | Result |
|---|---|
| Records | exact, in order, for all six turns: 15 records |
| Text or identifiers | the S6 check found no message text, application number, goal reference, stable plan id or candidate id. A separate count over all 15 records found 0 set `app_id`, 0 `TEST_ONLY`, 0 goal references and 0 `application 14` |
| Core API | exactly the 16 expected GETs; no write. T1 fell from m1's 8 reads to 5 |
| Provider | 0 FORWARDED, budget 3/5, ledger 29 lines `5764da8e...`, no reset |
| Database | logical `88b76a79...`; 0 rows in all 11 tables; integrity ok; no focus trace |
| Request dumps | 12 to 18, 0 with message text |
| FORGET | 0 intents, no marker |
| Services | gateway 400044, gate 400644, Core API 304463, broker 3411, authority 309023, witness 308690; 0 restarts; no failed units |
| Verifier | `F8_VERIFY_PASS full`, re-run after the test |

**Installed:** router `666b5f20...`, `planning.py` `4c74337d...`, adapter `a96d705f...`, rendered verifier `300b9c23...`. `motivation.py`, `workspace.py`, `ethics.py` and `ethics_principles.py` are unchanged.

## Rollback readiness

The m1 and p1 releases are intact against their manifests, and `/root/p1-install-20261030/payload` is root 0700. The return to m1 passed the simulations.

**Failure-triggered rollback remains untested live.** No return has run on any release, so neither the driver's failure paths nor a real revert have been exercised.

## What this proved

- p1 installs and starts on a real host from the sealed package.
- Planning runs only on a named piece of work: `make a plan for dinner` makes no read and no planning record.
- One read per route holds on the real gateway.
- No application number reaches any lane's record, including the lanes m1 still exposed.
- Provider isolation held.

## What remains untested

- **Populated stores.** With empty stores, Planning can only build its template. Steps, ordering and goal links on real data are proven offline at most.
- **Model behaviour.** No model saw any turn, so nothing here says a reply would be better, or even coherent, with these lanes.
- **Planning Live,** and any plan reaching the reply.
- **Real wording.** Only 6 synthetic turns ran, with no real traffic.
- **Failure-triggered rollback,** as above.
- **A goal added while running.** The verifier checks at start only.

## Known issues, not blocking

- **The Core API's own access log still names the application** in its query string. Only the decision log is free of it. The journal keeps its existing retention.
- **Stale labels.** Several S5 and S7 section headers still say `m1` or `g1`. They're labels only: the checks and pins under them are p1's.
- **Seven lanes aren't integrated.** Ethics stays off, so this is six lanes on a host.

## Effect on other packages

Gateway and gate PIDs moved, and the dump count is now 18, so any package pinned to the earlier values must be regenerated before use, including the backup disposition package.
