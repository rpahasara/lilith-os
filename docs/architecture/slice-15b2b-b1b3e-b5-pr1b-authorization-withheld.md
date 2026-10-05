# Slice 15B2b-B1b-3e — B-5: PR-1B Owner Re-decision (WITHHELD)

Status:

- **`B5_OWNER_AUTHORIZATION=WITHHELD`** (owner re-decision, 2026-10-05).
  This is Outcome B of the
  [B-5 decision packet](slice-15b2b-b1b3e-b5-pr1b-authorization-decision.md)
  §12, with the wording corrections in §1.
- **No current or effective B-5 grant exists.** The
  [earlier GRANTED record](slice-15b2b-b1b3e-b5-pr1b-authorization-granted.md)
  is historical. It was voided under packet §9 by the
  [Condition 3 STOP](slice-15b2b-b1b3e-condition3-fresh-pr2-stop.md). The
  [Condition 3 PASS](slice-15b2b-b1b3e-condition3-fresh-pr2-pass.md) then
  stated "B-5 GRANT REMAINS VOID". No later record re-granted it.
- **This record does not run `CHECK_ELIGIBILITY` and creates no eligibility
  result.**
- **M-B1 is NOT AUTHORIZED.** Freshness is `FRESHNESS_UNKNOWN`. **First
  Memory is NOT AUTHORIZED.**
- **Documentation only.** No live system was contacted.

```text
B-5 WITHHELD != permanent prohibition; B-5 WITHHELD -> no eligibility, no M-B1 go, no activation
```

## 1. Owner statement (verbatim)

> I, the owner, re-decide B-5 after the prior grant was voided under the B-5 decision packet §9 (Condition 3 STOP, broker preservation other than PASS). The later PASS stated "B-5 GRANT REMAINS VOID", and no accepted record has re-granted it.
>
> This is B5_OWNER_AUTHORIZATION=WITHHELD.
>
> - No current or effective B-5 grant exists.
> - No currently effective accepted record establishes `pr1bAuthorized=True`. The earlier GRANTED record is historical and void under the accepted stop semantics. While B-5 is WITHHELD, the owner-authorization precondition for any future eligibility evaluation is unsatisfied.
> - This record does not run `CHECK_ELIGIBILITY` and creates no eligibility result. While B-5 is WITHHELD, any eligibility evaluation must treat owner authorization as unsatisfied and cannot produce `PR1B_ELIGIBLE`.
> - No M-B1 go statement is given. No M-B1 package is executed.
> - No K-ROOT, K-WIT, registry mutation, genesis pin or record 1 is created or touched. Both replicas are untouched. FRESHNESS remains UNKNOWN.
> - Activation is NOT AUTHORIZED. First Memory is NOT AUTHORIZED. No PROD action is authorized.
> - All custody obligations and burned-identity rules remain in force.
>
> This is a current withholding under current evidence, not a permanent prohibition. Any future B-5 grant requires a new explicit owner decision based on fresh, then-current evidence and the revalidation the accepted procedure requires.
>
> Date: 2026-10-05.

## 2. Effect on the eligibility gate

`evaluate_eligibility`
(`services/owner-memory-control/lilith_owner_memory/pr1b_sequencing.py`)
returns `PR1B_ELIGIBLE` only when every precondition is literally `True`.
One of them is `pr1bAuthorized`; its failure reason is
`PR1B_NOT_AUTHORIZED`. The grant record described `pr1bAuthorized = True` as
an owner-asserted input to that evaluation, not a source flag, and not
persisted anywhere.

While B-5 is WITHHELD, no owner-asserted `pr1bAuthorized = True` input may be
supplied. This record changes no code and evaluates nothing.

## 3. Obligations and open items

- **Custody obligations** (packet §7 and the grant statement) remain in
  force:
  - K-ROOT only in S25 Termux private storage;
  - the passphrase only on the S25;
  - no laptop or DEV copy;
  - Replica B offline except deliberate ceremony steps.
- **Burned-identity rules** remain in force. Real identities must match none
  of the 20 canonical burned identities
  ([expansion](slice-15b2b-b1b3e-burned-identities-expansion.md)).
- **Accepted debt** (packet §8) is unchanged. Whole-host rollback resistance
  is **NOT ESTABLISHED**, and there is **NO** independently persisted
  freshness state.
- **Substrate-drift policy** (Condition 3 STOP §5 item 3): **OPEN**. It is
  not required to withhold B-5. It must be resolved before a future B-5
  re-grant can progress to eligibility.
- **Any future grant** needs all of the following:
  - a new explicit owner decision;
  - a fresh PR-2 revalidation;
  - a fresh check of every packet §1 input;
  - a fresh check of the M-B1 conditions;
  - the substrate-drift decision.

  None of these is authorized here.

## 4. Blocker state

| # | Blocker | State |
| --- | --- | --- |
| B-5 | PR-1B not authorized | **WITHHELD** (this record). The prior GRANTED outcome was voided under packet §9 |

The historical closure of B-1..B-4 is unchanged as record. Any future
re-grant requires a fresh check of their inputs.

## Explicitly not done

```text
B5_OWNER_AUTHORIZATION=WITHHELD
NO CURRENT OR EFFECTIVE B-5 GRANT (EARLIER GRANTED RECORD HISTORICAL AND VOID)
NO CURRENTLY EFFECTIVE pr1bAuthorized=True
NO CHECK_ELIGIBILITY RUN
NO ELIGIBILITY RESULT
NO M-B1 GO STATEMENT
M-B1 NOT AUTHORIZED
NO M-B1 COMMAND ISSUED
NO REAL K-ROOT
NO K-WIT
NO REGISTRY MUTATION
NO GENESIS PIN
NO REAL RECORD 1
NO REPLICA A / B CHANGE
NO LIVE SYSTEM CONTACTED
NO PROD ACTION
FRESHNESS=UNKNOWN
ACTIVATION NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
SUBSTRATE-DRIFT POLICY OPEN
```

> **Later current state (2026-10-06, pointer only; this record is preserved
> as written and was true at its date).** The substrate-drift policy was
> later accepted ([ADR-0015](../adr/0015-operational-evidence-invalidated-by-material-substrate-drift.md)),
> the [B-5 packet](slice-15b2b-b1b3e-b5-packet-refresh-owner-risk-review.md)
> was refreshed, and the owner then made a new explicit decision granting
> B-5 for the current DEV_SYNTHETIC packet:
> [B-5 owner grant for the current packet](slice-15b2b-b1b3e-b5-pr1b-authorization-current-grant.md).
> That grant is not eligibility; M-B1 and First Memory remain NOT
> AUTHORIZED.
