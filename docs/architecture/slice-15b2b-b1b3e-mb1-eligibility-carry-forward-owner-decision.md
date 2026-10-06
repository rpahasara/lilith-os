# Slice 15B2b-B1b-3e — M-B1 Eligibility Carry-Forward: Owner Decision (B)

Status:

- **`MB1_ELIGIBILITY_CARRY_FORWARD = B. FRESH_ELIGIBILITY_EVALUATION_REQUIRED_FOR_M_B1`**
  (owner decision, made after
  [eligibility sequence 3](slice-15b2b-b1b3e-pr1b-eligibility-sequence3.md)).
  It resolves the carry-forward question that record left open as
  `C. AMBIGUOUS — OWNER/ARCHITECTURE DECISION REQUIRED`. That analysis stays
  in the Sequence 3 record as pre-decision history.
- **Sequence 3 is unchanged: a completed, successful evaluation.**
  `COMPLETED_HISTORICAL_RESULT = PR1B_ELIGIBLE`;
  `REUSABLE_FOR_LATER_M_B1 = NO`.
- **This decision authorizes nothing.** M-B1, K-ROOT, K-WIT, registry /
  genesis mutation and First Memory are NOT AUTHORIZED. Owner freshness is
  `FRESHNESS=UNKNOWN`.
- A new rule, effective from this decision. It does not claim the rule
  existed earlier. Documentation only; no live system was contacted.

```text
completed PR1B_ELIGIBLE (Sequence 3) != eligibility usable for a later M-B1
PR1B_ELIGIBLE != M-B1 authorization
```

| Field | Value |
| --- | --- |
| Control `main` at the decision | `92ab03927a03dadef66b43101b583926c4e2760f` |
| Resolves | Sequence 3 §9 (pre-decision classification C) |

## 1. Owner decision (verbatim)

> I choose B: a fresh eligibility evaluation is required for M-B1. The
> successful Sequence 3 PR1B_ELIGIBLE result remains accepted as a completed
> historical result, but it is not sufficient by itself to authorize or begin
> a later M-B1 ceremony.
>
> A future owner-authorized M-B1 sequence must freshly re-establish the required
> current evidence, perform the final Condition 3 window, run CHECK_ELIGIBILITY
> once, and only if it returns PR1B_ELIGIBLE may that same continuous sequence
> proceed to the separately authorized M-B1 ceremony.
>
> This decision does not itself authorize M-B1, KROOT, KWIT,
> registry/genesis mutation, or First Memory.

## 2. Sequence 3 stays a successful result

| Fact | Value |
| --- | --- |
| evaluator result at its invocation | `PR1B_ELIGIBLE`, `reasons = []`, `eligible = True` |
| inputs | all 12 `True` |
| evaluator call count | exactly 1 |
| Condition 3 at the call | `CONDITION_3_FRESH_PR2 = PASS`, current |
| Condition 3 after the sequence | expired under trigger (h): REVALIDATE, not FAIL |

The expiry does **not** make Sequence 3 unsuccessful after the fact.

```text
COMPLETED_HISTORICAL_RESULT = PR1B_ELIGIBLE
REUSABLE_FOR_LATER_M_B1 = NO
```

## 3. The rule

A completed `PR1B_ELIGIBLE` result stays historically valid as an outcome.
It is **not sufficient by itself to begin a later M-B1 ceremony** once its
eligibility sequence has ended.

A future M-B1 execution sequence must freshly establish eligibility. That
one continuous, owner-authorized sequence must include, in order:

1. current prerequisite and stop-condition checks (DR-5 currentness, B-5
   grant usability, packet §9, G-1 … G-9, replica and custody state);
2. a fresh final Condition 3 window, under the
   [validity-window decision](slice-15b2b-b1b3e-condition3-validity-window-owner-decision.md);
3. the canonical `CHECK_ELIGIBILITY` (`evaluate_eligibility`), **exactly
   once**;
4. a successful result, `PR1B_ELIGIBLE`;
5. continuation into M-B1 **only inside that same continuous sequence**;
6. M-B1 only if the owner has **separately** authorized M-B1 (§5).

Any other result, or any interruption between steps 3 and 5, means no M-B1
in that sequence.

**The rule is sequence-based.** It sets no wall-clock TTL. If the sequence
is suspended or ends before M-B1 starts, its eligibility cannot be used
later. A later M-B1 needs a new sequence from step 1.

## 4. Alignment with the sequencer crash matrix

The accepted sequencer (`pr1b_sequencing.CRASH_MATRIX`;
[P3-5](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md) §9) classifies
the window **"C-1 eligibility checked / K-ROOT absent"** as `SAFE_RETRY`,
with the action **"re-check eligibility; nothing written"**.
`BootstrapSequencerV1` tracks one bootstrap in memory and persists nothing,
so its `PR1B_ELIGIBLE` state does not outlive the run.

Sequence 3 ended in exactly that window. Under this decision, leaving C-1
now has a definite operational meaning: re-check eligibility in a new
continuous sequence before any M-B1. The decision aligns the operational
rule with the existing crash-recovery posture. **No implementation changed.**

## 5. Execution authorization stays separate

The owner has **not** given an M-B1 go statement. A future go statement
remains a separate, explicit owner statement. Per the
[final package pins](slice-15b2b-b1b3e-mb1-final-package-pins.md) and the
[B-5 decision packet](slice-15b2b-b1b3e-b5-pr1b-authorization-decision.md)
§12, it must name:

| Pin | SHA-256 |
| --- | --- |
| phone operator script | `09cbc9bee7b58af7bab45bb903c6e10cb51ae6c62b20705be12de274bbe5216b` |
| M-B1 bundle | `7f07e158aa5a0b3c31ee63e25ae25116c92f26a402bc6924422d7c95e2edc2c1` |

Real identities must match none of the canonical 20 burned identities.

Unchanged requirements, none authorized here:

- the M-B1 G0 / G1 / T1 phone gates
  ([ceremony package](slice-15b2b-b1b3e-mb1-kroot-ceremony-package.md) §5),
  including Replica B as the accepted empty replica (`c068e533…`, 0 records,
  not nested) and the custody checks (Termux private storage, no SSH /
  `sshd`, local TTY);
- the B-5 grant must remain usable (no packet §9 stop);
- Condition 1 must still hold (bundle and script from merged `main`, pins
  unchanged);
- **a fresh PR-2 revalidation immediately before `GENERATE_K_WIT` (M-B2)
  remains mandatory** (P3-5 §13; the replacement OR-8 acknowledgement). The
  fresh Condition 3 of an M-B1 sequence does not satisfy it.

## 6. State

```text
MB1_ELIGIBILITY_CARRY_FORWARD = B. FRESH_ELIGIBILITY_EVALUATION_REQUIRED_FOR_M_B1
CARRY-FORWARD A (EVALUATION_RESULT_CARRIES_FORWARD) NOT ACCEPTED
CARRY-FORWARD C (AMBIGUOUS) RESOLVED; NO LONGER CURRENT
SEQUENCE 3: COMPLETED_HISTORICAL_RESULT = PR1B_ELIGIBLE
SEQUENCE 3: REUSABLE_FOR_LATER_M_B1 = NO
SEQUENCE 3 CONDITION 3 EXPIRED (TRIGGER (h)): REVALIDATE, NOT FAIL
FUTURE M-B1 SEQUENCE: FRESH FINAL CONDITION 3 REQUIRED
FUTURE M-B1 SEQUENCE: CHECK_ELIGIBILITY EXACTLY ONCE
FUTURE M-B1 SEQUENCE: ELIGIBILITY AND M-B1 IN THE SAME CONTINUOUS SEQUENCE
NO WALL-CLOCK TTL; SEQUENCE-BASED
PR1B_ELIGIBLE != M-B1 AUTHORIZATION
M-B1 GO STATEMENT NOT GIVEN
M-B1 = NOT AUTHORIZED
KROOT = NOT AUTHORIZED
KWIT = NOT AUTHORIZED
REGISTRY / GENESIS MUTATION = NOT AUTHORIZED
FIRST MEMORY = NOT AUTHORIZED
FRESH PR-2 IMMEDIATELY BEFORE GENERATE_K_WIT REMAINS MANDATORY
FRESHNESS=UNKNOWN
NO IMPLEMENTATION CHANGE
NO LIVE SYSTEM CONTACTED
```
