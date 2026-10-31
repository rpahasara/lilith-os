# Seven-lane shadow on DEV, 2026-10-31: PASS, awaiting owner acceptance

**The owner has not yet accepted this result.** Merging this record does not accept it.

**Result: every step passed, once, with no retry and no rollback.** The driver reported `DRIVE_COMPLETE`. DEV stays on e1 with World Model, Goals, Reasoning, Workspace, Motivation, Planning and Ethics in shadow on `lilith_os` only. Every other lane is off.

## Four separate milestones

| Milestone | State |
|---|---|
| Seven-lane shadow integration | **Demonstrated on DEV,** on empty stores with synthetic turns |
| Functional live cognition | **Not demonstrated.** No model saw any turn |
| Readiness for populated PROD data | **Not demonstrated.** Source tests only |
| Production deployment readiness | **Not ready** |

## Runtime and approval

| Item | Value |
|---|---|
| Host | `lilith-dev-01`, boot `cb0d71da...`, unchanged |
| Approval | one owner-approved run, synthetic `TEST_ONLY` messages only |
| Source | #309 reviewed head `a0a3e69`, merge `59aff47`; real main run `CONTROL_ONLY_NO_DEPLOY`, `DEV_MUTATION=NONE`, boundary proof PASS |
| Package | manifest `7fa01cca...`, bundle `751f03a0...`; all 32 files verified; all 10 bundle members equal the merged commit byte for byte; the three transfer chunks rebuild the bundle |
| Start | p1, gateway 400044, gate 400644, budget 3/5, ledger 29 lines, 18 dumps, DB `88b76a79...` |

## Provenance

**PR #308 at `2e62a44` was never merged.** Its simulated merge reported `DEPLOY_REQUIRED`, because it modified two files already on main. #309 carries the same release as new files only. The package's `RUNBOOK.md` and script headers still name `2e62a44`, because editing them would change the approved manifest. The bytes are identical to #309, verified before the run, and `RUNBOOK-PROVENANCE-ADDENDUM.md` beside the package records this.

**Related history:** commit `f031fea`, the #307 merge, keeps a failed `LILITH DEV deployment` status from a stale-commit guard. That was not cleared by any later run.

## Steps

| Step | Result |
|---|---|
| P0 preflight | PASS |
| S1 stop p1 | PASS |
| S2, S2b, S2c transfer | PASS |
| S3 install | PASS, verifier `--full` |
| S4 start e1 | PASS, gateway PID 407521 |
| S5 post-verify | PASS, 0 Core API requests before the test |
| S6 shadow test | PASS |
| S7 final | PASS |
| R1 to R4 return to p1 | not needed |

The driver ran detached, as this package's runbook requires, and its journal holds a verdict for every step, written to disk as it ran.

## S6, gate isolated

The gate was confirmed stopped (`inactive`, nothing listening on 9911) before any turn. It was started again afterwards, with the same budget, as PID 408170.

| Turn | Message class | Records, in order | Reads |
|---|---|---|---|
| T1 | options for an application | motivation `SATISFIED`, workspace `NO_CANDIDATE`, reasoning `OPTION_GENERATION`, cognitive, routing | 5 |
| T2 | what's missing | motivation, workspace, reasoning `UNCERTAINTY_ANALYSIS`, routing | 5 |
| T3 | which goal has priority | goal, routing | 0 |
| T4 | casual | routing | 0 |
| T5 | plan a follow-up | planning `PLAN_PROPOSED`, 3 steps; routing | 6 |
| T6 | dinner plan | routing | 0 |
| T7 | lying on a cover letter | ethics `THIRD_PARTY_IMPACT`, routing | 5 |
| T8 | wearing jeans | routing | 0 |
| T9 | risks of an offer | motivation, workspace, reasoning `OPTION_GENERATION`, routing | 5 |
| T10 | sharing private legal records | ethics `PRIVACY_EXPOSURE` and `THIRD_PARTY_IMPACT`, cognitive, routing | 6 |

**Precedence held on a host:** T7 went to Ethics with Reasoning yielding, and T9 stayed with Reasoning. **T10 is the live proof of the vocabulary fix:** on the unfixed code, its privacy concern is dropped because of the word "legal". T8 shows the over-match fix.

Every turn returned the expected failed-model message, because no provider was reachable.

## Independent validation

Run separately after the driver finished, read-only, with scripts written after the run and outside the manifest.

| Check | Result |
|---|---|
| Release | `f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1`; `F8_VERIFY_PASS full` |
| Pins | router `be8c08d1...`, `ethics.py` `d6a1c20b...`, adapter `f1ee561d...`, rendered verifier `c989a63c...`; planning, motivation, workspace and principles unchanged |
| Records | 25 in the window, exact and in order |
| Text | 0 hits in the 25 records for message words, role words or data words, including `recruiter`, `employer`, `legal records` and `the public` |
| Identifiers | 0 `app_id` set, 0 goal, candidate or plan references |
| Per-turn ids | 34 hex values in `event_id`, `correlation_id` and `ethical_subject_ref`. **None appears in more than one turn or in any older record** |
| Ethics record | counts, concern types, principles and fixed labels; no free text |
| Core API | exactly the 32 expected GETs, all 200, 12 on goal routes; no write |
| Provider | 0 FORWARDED, budget 3/5, ledger 29 lines `5764da8e...`, no reset |
| Database | digest `88b76a79...`, 0 rows in 11 tables, integrity ok, schema unchanged |
| Request dumps | 18 to 28, 0 with message text |
| FORGET | 0 intents, no marker |
| Services | gateway 407521, gate 408170, Core API 304463, broker 3411, authority 309023, witness 308690; 0 restarts; no failed units |
| Rollback | p1 release present; `/root/e1-install-20261101/payload` root 0700 |
| Offline regressions, after the run | all suites pass, 2 skips that need Linux |

## What this proved

- Seven lanes install, start and run together on a real host from a sealed package.
- Ethics, Reasoning and Planning keep to their own message classes on the tested turns.
- Reads stay bounded with all seven lanes: at most 6 on a turn.
- No content or stable identifier reaches a decision record.
- Provider isolation held.

## What remains untested

- **Populated stores.** Workspace, Motivation and Ethics saw nothing to weigh, so whether a concern is useful is unknown.
- **Model behaviour.** Nothing here says a reply would be better, or even coherent.
- **Real wording.** Ten synthetic turns. Known misses stay pinned in the overlay README, such as `is it ok to say I was sick when I wasn't?`.
- **Two intents in one message.** The first wins; no host turn tested this.
- **Failure-triggered rollback.** Simulated only. No return has run live on any release.
- **Any live lane.** Ethics Live and every other mode stay off.

## Known issues, not blocking

- **T9's Reasoning label is `OPTION_GENERATION`** for a risk question. Plumbing is right; whether the label is apt needs a model window.
- **The Core API's own access log still names the application** in its query string, as with p1.
- **Stale labels.** Some section headers in the package still say `g1` or `m1`. The checks under them are e1's.

## Effect on other packages

Gateway and gate PIDs moved, and the dump count is now 28, so any package pinned to earlier values must be regenerated.
