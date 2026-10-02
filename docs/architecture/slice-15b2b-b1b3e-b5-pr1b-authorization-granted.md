# Slice 15B2b-B1b-3e — B-5: PR-1B Owner Authorization (GRANTED)

Status:

- **`B5_OWNER_AUTHORIZATION=GRANTED`** (owner statement, 2026-09-30). This
  is Outcome A of the
  [B-5 decision packet](slice-15b2b-b1b3e-b5-pr1b-authorization-decision.md)
  §12.
- **B-5 is CLOSED.** Every PR-1B review blocker (B-1..B-5) is now closed.
- `pr1bAuthorized = True` is authorized **for the PR-1B eligibility
  evaluation only**. It is an owner-asserted input to `evaluate_eligibility`.
  It is not a source flag, and it is not persisted anywhere.
- **M-B1 is NOT AUTHORIZED.** No M-B1 command may be issued until every
  condition in §2 is met.
- **`CHECK_ELIGIBILITY` (P1B-0) has not been run.** It still requires a
  fresh PR-2 revalidation immediately before it.
- There is no real K-ROOT, K-WIT, registry v1, genesis pin, or record 1.
  Freshness is `FRESHNESS_UNKNOWN`. **First Memory is NOT AUTHORIZED.**

```text
B-5 GRANTED != M-B1 go != K-ROOT exists != freshness CURRENT != First Memory
```

| Field | Value |
| --- | --- |
| Control `main` at the decision | `cfa0b3e542e821ae2d4a3bb4ba0f198ee9e6fb58` |
| Decision packet | `slice-15b2b-b1b3e-b5-pr1b-authorization-decision.md` (`ed86677`) |

## 1. Owner statement (verbatim)

> I authorize PR-1B for DEV_SYNTHETIC under the accepted custody plan and accepted rollback/freshness debt.
>
> This is B5_OWNER_AUTHORIZATION=GRANTED.
>
> I authorize setting pr1bAuthorized=True for the PR-1B eligibility evaluation only.
>
> This authorization does not authorize M-B1 yet.
>
> No M-B1 command may be issued until:
> 1. the real M-B1 bundle and phone operator script are prepared and reviewed;
> 2. the cfa0b3e DEV deploy boundary results are reviewed and accepted;
> 3. a fresh PR-2 revalidation passes immediately before eligibility;
> 4. the eligibility evaluation returns PR1B_ELIGIBLE;
> 5. I separately give the explicit M-B1 go statement.
>
> All custody obligations remain in force:
> - K-ROOT only in S25 Termux private storage;
> - K-ROOT passphrase entered only on the S25;
> - no laptop copy of K-ROOT;
> - all 12 rehearsal identities remain permanently burned;
> - real identities must not match any burned identity;
> - Replica B remains independent/offline except deliberate ceremony steps.
>
> FIRST MEMORY remains NOT AUTHORIZED.

> **Burned-set note (2026-09-30).** The owner's "all 12 rehearsal identities" remain burned. The canonical, mechanically enforced set they belong to is now **20** ([expansion](slice-15b2b-b1b3e-burned-identities-expansion.md)). Real identities must match none of the 20.

## 2. M-B1 gate: all five conditions are required, in order

| # | Condition | State |
| --- | --- | --- |
| 1 | the real M-B1 bundle and phone operator script are prepared and reviewed (from merged `main`) | **NOT MET**: not yet prepared |
| 2 | the `cfa0b3e` DEV deployment boundary results are reviewed and accepted | **NOT MET**: not yet reviewed |
| 3 | a fresh PR-2 revalidation passes immediately before eligibility | **NOT MET** |
| 4 | the eligibility evaluation returns `PR1B_ELIGIBLE` (P1B-0 `CHECK_ELIGIBILITY`, with `pr1bAuthorized = True`) | **NOT MET**: not yet run |
| 5 | the owner separately gives the explicit M-B1 go statement (packet §12 template) | **NOT GIVEN** |

## 3. Obligations and limits still in force

- The custody obligations in the packet §7 and the owner statement: K-ROOT
  only on the S25; the passphrase only on the S25; no laptop or DEV copy;
  all 12 rehearsal identities burned; no real identity matching a burned
  one; Replica B offline except deliberate ceremony steps.
- The accepted debt in the packet §8. Whole-host rollback resistance is
  **NOT ESTABLISHED**, and there is **NO** independently persisted
  freshness state.
- **Stop conditions** (packet §9): any of them voids this grant before
  M-B1, and the owner must then re-decide.
- **Not authorized:** First Memory, A1–A7, activation, issuance, and any
  PROD action.

## 4. Blocker state

| # | Blocker | State |
| --- | --- | --- |
| B-1 | PR-3 tooling not accepted | **CLOSED** |
| B-2 | open risks not acknowledged | **CLOSED** |
| B-3 | real-acceptance gate | **CLOSED** (merged `cfa0b3e`) |
| B-4 | K-ROOT custody and the Termux rehearsal | **CLOSED** |
| B-5 | PR-1B not authorized | **CLOSED**: GRANTED (this record) |

## Explicitly not done

```text
M-B1 NOT AUTHORIZED
NO M-B1 COMMAND ISSUED
CHECK_ELIGIBILITY NOT RUN
NO REAL K-ROOT
NO K-WIT
NO REGISTRY V1
NO GENESIS PIN
NO REAL RECORD 1
NO REPLICA A / B CHANGE
FRESHNESS=UNKNOWN
FIRST MEMORY NOT AUTHORIZED
```
