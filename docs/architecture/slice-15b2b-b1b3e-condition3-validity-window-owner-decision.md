# Slice 15B2b-B1b-3e — M-B1 Condition 3: Validity-Window Owner Decision

Status:

- **`CONDITION_3_VALIDITY_MODEL=EVENT_BOUNDED_AND_SEQUENCE_BOUNDED`** (owner
  decision, 2026-10-05). **No universal fixed wall-clock duration is
  accepted.**
- It resolves, **for the Condition 3 / eligibility window only**, the
  "exact validity-window durations" decision that the
  [Substrate Drift and Evidence Revalidation Policy v0.1](substrate-drift-and-evidence-revalidation-policy-v0.1.md)
  §11 left open. Fixed durations for other evidence classes remain open where
  applicable.
- It also records the owner's package, apt-timer and needrestart decisions
  (§3).
- Made at the owner review of the
  [2026-10-05 fresh read-only rebaseline](slice-15b2b-b1b3e-dev-synthetic-fresh-readonly-rebaseline.md).
  It applies to **future** Condition 3 windows. It does not re-interpret any
  dated historical record: the
  [Condition 3 PASS](slice-15b2b-b1b3e-condition3-fresh-pr2-pass.md)
  validity limit and the
  [C-04 disposition](slice-15b2b-b1b3e-condition3-c04-owner-disposition.md)
  keep their original meaning.
- **Documentation only.** No live system was contacted. It grants no B-5,
  runs no `CHECK_ELIGIBILITY`, and authorizes no M-B1, First Memory, package,
  timer, needrestart, runtime or cloud action.

```text
validity model decided != Condition 3 current != B-5 granted != eligible != M-B1 authorized
```

## 1. Condition 3 validity model

```text
CONDITION 3 VALIDITY MODEL: EVENT-BOUNDED + SEQUENCE-BOUNDED
NO UNIVERSAL FIXED WALL-CLOCK DURATION
```

A future final Condition 3 evidence window may support `CHECK_ELIGIBILITY`
only when **all** of the following hold:

1. the required evidence is freshly collected or revalidated;
2. it is collected **immediately before** `CHECK_ELIGIBILITY`;
3. it remains inside the **same continuous owner-authorized eligibility
   sequence**;
4. all required evidence remains current under
   [ADR-0015](../adr/0015-operational-evidence-invalidated-by-material-substrate-drift.md),
   with no accepted invalidating event between collection and use.

## 2. Expiry and revalidation triggers

The Condition 3 window expires at the **earliest** of:

| # | Trigger |
| --- | --- |
| a | the next relevant unattended package-install opportunity |
| b | any material dependency drift under ADR-0015 |
| c | any applicable global invalidator G-1 … G-9 (policy §2) |
| d | broker process replacement |
| e | host reboot |
| f | a relevant deployment, until DR-5 has been freshly re-compared and found equal to the accepted result set |
| g | another accepted stop or revalidation trigger |
| h | suspension or end of the authorized eligibility sequence |

```text
time / sequence expiry -> evidence NOT CURRENT / REVALIDATE (not reusable)
time / sequence expiry -/-> control FAIL
```

Expiry alone does not show that any control failed (ADR-0015 SD-1, SD-6).

## 3. Package, apt-timer and needrestart decisions

| Topic | Owner decision |
| --- | --- |
| package holds | **No package-hold strategy is accepted.** No hold is authorized |
| package strategy | schedule the final eligibility revalidation immediately around the owner-authorized eligibility sequence (scheduling, not holds) |
| security updates | remain permitted; not delayed as a standing strategy |
| apt timers | **no apt timer change** is accepted |
| needrestart | the currently accepted exclusion posture (`/etc/needrestart/conf.d/lilith-authority-sensitive.conf`, SHA-256 `503279…`) **remains unchanged**; no needrestart mutation is authorized |

This creates **no** permanent package safety. Mapped-package drift remains
governed by ADR-0015 and policy §3–§5; trigger (a) and trigger (b) apply to
it.

## 4. What remains open

- Fixed validity durations for evidence classes other than the Condition 3 /
  eligibility window, where applicable.
- Whether a controlled broker restart can avoid a full PR-2 window.
- Network exposure as a global invalidator.
- Clock-trust policy.

## 5. Current posture (unchanged)

```text
B-5 = WITHHELD
FRESHNESS=UNKNOWN
CONDITION 3 = NOT CURRENTLY ESTABLISHED
CHECK_ELIGIBILITY = NOT RUN / NOT AUTHORIZED
M-B1 NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
B5_EVIDENCE_PACKET_READINESS = NOT_READY
```

## Explicitly not done

```text
NO LIVE SYSTEM CONTACTED (DEV_SYNTHETIC, REPLICA A / B, CUSTODY DEVICE, PROD)
NO PACKAGE HOLD
NO APT TIMER CHANGE
NO NEEDRESTART CHANGE
NO RESTART, REBOOT OR RE-PIN
NO CHECK_ELIGIBILITY RUN
NO B-5 GRANT
NO M-B1
NO REAL K-ROOT / K-WIT / REGISTRY V1 / GENESIS PIN / RECORD 1
NO HISTORICAL RECORD EDITED
FIRST MEMORY NOT AUTHORIZED
```
