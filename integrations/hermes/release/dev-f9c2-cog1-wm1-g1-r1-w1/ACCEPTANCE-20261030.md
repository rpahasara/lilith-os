# Workspace shadow on DEV, 2026-10-30: PASS, owner acceptance pending

**Result: every planned step passed, once, with no retry.** DEV stays on w1 with World Model, Goals, Reasoning and Workspace in shadow on `lilith_os`.

**This validates shadow behaviour only.** It does not show live reasoning, Workspace-mediated model cognition, or salience ranking on real data. Workspace saw no candidates in any turn.

## Runtime and approval

| Item | Value |
|---|---|
| Host | `lilith-dev-01`, boot `cb0d71da…`, unchanged |
| Approval | one owner-approved installation and shadow test, synthetic messages only |
| Source | #295 `d8aa4ed`, #293 `0bae3df`, both `CONTROL_ONLY_NO_DEPLOY`, `DEV_MUTATION=NONE` |
| Package | manifest `941784b3…`, bundle `fa36e328…`; main bytes equal to the bundle, so no reseal was needed |
| Start | r1, gateway 378068, gate 370064, budget 3/5, ledger 29 lines, DB `88b76a79…` |

## Steps

| Step | Result |
|---|---|
| P0 preflight | PASS |
| S1 stop r1 | PASS |
| S2, S2b transfer | PASS, whole bundle digest `e485962a…` |
| S3 install | PASS, installer verifier `--full` |
| S4 start w1 | PASS, gateway PID 384910, 0 forwards at start |
| S5 post-verify | PASS, 0 Core API requests before the test |
| S6 shadow test | PASS |
| S7 final | PASS. Its PASS line says "0 Core API requests": wrong text inherited from r1. The checks required exactly 10 |
| R1 to R4 rollback | not needed |

## S6, gate isolated

The gate was confirmed stopped (`inactive`, nothing listening on 9911) before any turn was sent. It was started again afterwards, with its key and the same budget.

| Turn | Message | Records, in order | Core API |
|---|---|---|---|
| T1 | `TEST_ONLY what are my options for application 14?` | workspace `NO_CANDIDATE` 0, reasoning `OPTION_GENERATION`, cognitive shadow, routing `live: false` | 5 GETs |
| T2 | `TEST_ONLY what information is missing to resolve this?` | workspace `NO_CANDIDATE` 0, reasoning `UNCERTAINTY_ANALYSIS`, routing | 5 GETs |
| T3 | `TEST_ONLY which goal has priority?` | goal shadow, routing | 0 |
| T4 | `TEST_ONLY hey how are you` | routing | 0 |

Every turn returned 200 `completed` with a 117-character reply: the expected failed-model message, because no provider was reachable.

## Validation

| Check | Result |
|---|---|
| Records | exact, in order, for all four turns |
| Message text or candidate id in any record | 0 |
| Workspace record shape | metadata and counts only; no id fields |
| Core API | exactly the 10 expected GETs, all 200; no write |
| Provider | 0 FORWARDED, budget 3/5, ledger 29 lines `5764da8e…`, no reset |
| Database | logical `88b76a7910fdcb27…`, file `1d8a87e3…`, byte-identical before and after; 0 rows everywhere; integrity ok; no focus trace |
| Request dumps | 4 to 8, all `lilith:lilith` 0600; 0 with message text |
| Dump retention | deployed `prune_sessions` removes `request_dump_{session}_*` with its session, on the daily timer, after 7 days. A dump is removed when its session is pruned, not by its own age |
| Decision log retention | 7 days, and FORGET purges `logs/` |
| FORGET | 0 intents, no marker |
| Services | gateway 384910, gate 385519, Core API 304463, broker 3411, authority 309023, witness 308690; 0 restarts; no failed units |
| Verifier | `F8_VERIFY_PASS full`, re-run after the test |

**Installed:** router `0e5d43fa…`, adapter `848fdb7d…`, `workspace.py` `d79f67e1…`.

## Rollback readiness

The r1 and g1 releases are intact against their manifests, and the w1 release against its own. `/root/w1-install-20261030/payload` is root 0700 with all 9 files. The revert path passed `sim_install_w1.sh` 38/38 and the window simulation 40/40.
It has **not** been run live.

## Limits

- **Empty stores.** Workspace produced 0 candidates in both analytic turns, so selection, ranking and suppression were not exercised on DEV. Offline tests cover the plumbing.
- **No real wording.** The detector pools are synthetic and have one author. The unseen half of the last pool scored 10/13 paraphrases and 1/14 false matches.
- **No model.** Every model call failed by design, so nothing shows how Workspace would affect a reply.
- **Empty goal store check.** The verifier checks it at start only. A goal added later would let a focus read write a trace.
- **Gate PID moved** to 385519, so later packages must re-pin it.
- **Title rule.** It is in the w1 adapter's goal policy, but Goals is in shadow, so no model has seen it.

## Effect on other packages

The backup disposition package pins gateway 378068 and gate 370064, and must be regenerated before use.
