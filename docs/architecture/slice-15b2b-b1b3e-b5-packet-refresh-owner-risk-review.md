# Slice 15B2b-B1b-3e — B-5 Packet Refresh and Owner Risk Review (2026-10-05)

Status:

- **`B5_PACKET_READY_FOR_SEPARATE_OWNER_DECISION`** (owner decision,
  2026-10-05). **`TECHNICAL_PACKET_COMPONENTS_COMPLETE = YES`.** The owner
  risk review of OR-1 … OR-9 is complete (§4).
- **This is not a B-5 decision. B-5 remains WITHHELD.** No grant is
  recorded, and no `pr1bAuthorized` input is established. A future B-5 grant
  is a separate, explicit owner decision.
- It refreshes the evidence that the
  [B-5 re-decision (WITHHELD)](slice-15b2b-b1b3e-b5-pr1b-authorization-withheld.md)
  §3 requires before any future grant, and it records new owner dispositions
  of the open risks. It **does not edit** the 2026-09-29
  [open-risk acknowledgement](slice-15b2b-b1b3e-open-risk-acknowledgement.md),
  which stays as dated history. Its OR-8 acknowledgement is superseded by
  §5.
- Builds on the accepted
  [fresh read-only rebaseline](slice-15b2b-b1b3e-dev-synthetic-fresh-readonly-rebaseline.md)
  and the
  [Condition 3 validity-window owner decision](slice-15b2b-b1b3e-condition3-validity-window-owner-decision.md),
  under [ADR-0015](../adr/0015-operational-evidence-invalidated-by-material-substrate-drift.md)
  and the
  [substrate-drift policy](substrate-drift-and-evidence-revalidation-policy-v0.1.md).

```text
packet ready for owner decision != B-5 granted != eligible != M-B1 authorized
```

## 1. Identities

| Item | Value |
| --- | --- |
| control `main` | `53d7405e8193f1e11e0524c3b9b7ce54151650ff` |
| laptop window | `2026-10-05T17:35:09Z`–`17:41:20Z` (Condition 1, repository and staged-file reads) |
| phone window | owner-run, `2026-10-05T17:45:23Z` |
| DR-5 read | GitHub run list and run-log read after the phone window |
| raw evidence | operator-held external bundle, **not canonical repository content**. `SHA256SUMS` SHA-256 `be094fd714db0d28bb79b23036e4c2bc12c44c524134c8f604e9707b286ef023`. Its location is not published |
| contact | no DEV, cloud, Replica A or PROD contact. **The phone was never contacted by the reviewer**: the owner ran the read-only block locally (§2.3). GitHub use was read-only (run list and log read; no rerun, dispatch, cancel or approval) |

## 2. Fresh evidence

### 2.1 Condition 1: fresh check

**`CONDITION_1_FRESH_CHECK=PASS`**, by the procedure of the
[final package pins](slice-15b2b-b1b3e-mb1-final-package-pins.md) §4
precondition 1. Nothing was rebuilt or regenerated.

| Invariant | Observed |
| --- | --- |
| source commit `1e2eae30fb7023a44776d1f8d25e2bb958955e6a` is an ancestor of `origin/main` | yes |
| staged bundle SHA-256 | `7f07e158aa5a0b3c31ee63e25ae25116c92f26a402bc6924422d7c95e2edc2c1` (equal to the pin) |
| staged operator script SHA-256 | `09cbc9bee7b58af7bab45bb903c6e10cb51ae6c62b20705be12de274bbe5216b` (equal to the pin); byte-equal to the block in the pins record |
| bundle contents | 74 files; regular or directory, mtime 0, owner 0:0; inner `SHA256SUMS` `4816f8c9…6498` verifies all 73 listed members; `SOURCE_COMMIT` equals the source commit |
| bundled sources | all 17 byte-equal to `origin/main`; no closure or builder file changed since the source commit |
| burned set | the canonical 20 |
| accepted tests | `test_b1b3e_mb1_finalization.py`: 8 of 9 run, all OK. The fake-vendor build test was not run, to avoid any build |

### 2.2 Condition 2 / DR-5

**`DR5_CURRENTNESS=CURRENT`** through `53d7405`. Run `37348104764` (the
only deploy after the rebaseline window) equals the accepted run
`36552218231` on all three sets: full result set (186 lines, `f1869234…`),
DR-5 block (147 lines, `a1d98773…`), pre-deploy block (29 lines,
`f5087042…`). `PR1_AUTHORITY_BOUNDARY maturity=P1A-9`,
`AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`, `GRANT_ABSENT`, no
`ALLOWED`. Any later deployment needs a fresh comparison.

### 2.3 Replica B and `ownerRegisterKnownEmpty`

The owner opened Termux locally on the S25 and ran a screen-only block
built only from accepted read-only lines (the B-4 staging `snap` and G0 /
G1 gates, and the M-B1 G0 session gates), with no phone-to-laptop
connection and no ADB, SSH, MTP or automation. The owner reported the
output by transcription.

| Field | Fresh | Accepted ([B-4 run 2](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-run2.md)) |
| --- | --- | --- |
| canonical path | `~/lilith-owner-offline-dev-synthetic-01`, present | same |
| nested path | absent | absent |
| manifest | `c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4` | equal |
| records | `0` | `0` |
| entries / parent | `REPLICA.json records` / `lilith-owner-offline-dev-synthetic-01` | equal |
| inodes | `973613 / 973617 / 973618` | equal |
| modes / mtime | `700 / 600 / 700`, `1790654695` | equal |

- **`REPLICA_B_CURRENTNESS=ESTABLISHED`.**
- **`OWNER_REGISTER_KNOWN_EMPTY=ESTABLISHED`.** `owner_register_state`
  (`pr1b_sequencing.py`) is KNOWN_EMPTY only for `OWNER_REGISTER_EMPTY`:
  at least `MINIMUM_REPLICAS = 2` replicas, distinct IDs and locations, the
  same environment and profile, and zero records in every replica. Replica A
  (manifest `fbdd045c…`, 0 records, in the accepted rebaseline) and
  Replica B (above) satisfy it. As in the B-5 packet §1 precedent, this was
  established by separate read-only reads of each replica; the tool was not
  run across both devices.
- This does **not** make owner `FRESHNESS` CURRENT.

### 2.4 Custody device (G-9)

| Accepted requirement | Fresh evidence |
| --- | --- |
| no SSH session; `sshd` not running; local terminal (M-B1 G0) | `G9_SSH_SESSION=ABSENT`, `G9_SSHD=ABSENT`, `G9_LOCAL_TTY=YES` |
| `HOME` / `TMPDIR` in Termux private storage | both private |
| no K-ROOT before M-B1 | `KROOT_FILES=ABSENT` |
| Developer options OFF; Google "Other device data" and Samsung automatic backup OFF ([P3-3B](slice-15b2b-b1b3e-pr3-p33b-replica-b-ceremony.md) §1) | owner observation, nothing changed: all OFF |
| no ADB, SSH or automation access to Termux; phone not lost; no suspected compromise; laptop not compromised or rolled back (B-5 packet §7, §9) | owner attestation |

**`CUSTODY_G9=ESTABLISHED`**: established under the accepted
owner-observed custody procedure for this evidence window. **It does not
establish general compromise detection.** Resistance to phone compromise
remains NOT ESTABLISHED
([custody decision](slice-15b2b-b1b3e-b4-kroot-custody-decision.md)).

### 2.5 Stops and invalidators

No B-5 packet §9 stop condition fired. No global invalidator G-1 … G-9 was
observed in the collected evidence.

## 3. Packet components

| Component | State |
| --- | --- |
| Condition 1 | PASS (fresh) |
| Condition 2 / DR-5 | CURRENT through `53d7405` |
| Condition 3 | strategy accepted; the final window is deferred by accepted sequencing until immediately before `CHECK_ELIGIBILITY` |
| Condition 4 (`CHECK_ELIGIBILITY`) | not run, by design |
| Condition 5 (M-B1 go) | not given, by design |
| Replica B / `ownerRegisterKnownEmpty` | ESTABLISHED |
| custody G-9 | ESTABLISHED (qualified, §2.4) |
| OR-1 … OR-9 owner review | complete (§4) |

```text
TECHNICAL_PACKET_COMPONENTS_COMPLETE = YES
B5_PACKET_READY_FOR_SEPARATE_OWNER_DECISION
```

The earlier `READY_PENDING_OWNER_RISK_REVIEW` state is satisfied with
respect to owner risk review.

## 4. Owner risk dispositions (2026-10-05)

| Item | Risk | Owner disposition |
| --- | --- | --- |
| **OR-1** | whole-disk / whole-host rollback can present a self-consistent old authority world | **REAFFIRMED** (prior accepted risk) |
| **OR-2 / DR-3** | root-equivalent principals and host-local copies remain possible | **REAFFIRMED** |
| **cross-environment `osAdminLogin`** | the PROD deployer has root-equivalent reach on DEV | **REAFFIRMED** |
| **OR-3** | cloud principals can create future snapshots, images or clones | **REAFFIRMED** (bounded) |
| **OR-4** | DEV consumes no independent external freshness before record 1 | **REAFFIRMED**, with the qualification below |
| **OR-5** | pending kernel reboot | **REMAINS CLOSED** (not reopened) |
| **OR-6** | tmpfiles post-boot runtime directories | **REMAINS CLOSED** (not reopened) |
| **OR-7** | `/tmp` and `/var/tmp` remain on the boot disk | **REAFFIRMED** |
| **OR-8** | the PR-2 inventory is point-in-time | **NEW ACKNOWLEDGEMENT ADOPTED** (§5); the 2026-09-29 acknowledgement is void and superseded |
| **OR-9** | visibility scope | **NOTED as a LIMIT, not an accepted risk.** The visible project set includes `au4labs-web-rp-2026`, owner-confirmed unrelated / NON_MATERIAL for the observed 2026-10-05 state. No risk acceptance is created |

**OR-4 qualification.** The fresh Replica B, `ownerRegisterKnownEmpty` and
G-9 evidence show no currently observed void trigger under the accepted
procedure. "Not synced" and custody confidence still rely partly on owner
observation and attestation, not on mechanical compromise detection. The
existing limit stands: **owner freshness does not protect against rollback
or compromise of both replicas simultaneously.**

The reaffirmations carry the 2026-09-29 terms: DEV_SYNTHETIC only; not
mitigation; not rollback resistance; owner freshness not CURRENT; no PR-1B
authorization; void for an item if its stated staleness condition occurs.

## 5. Replacement OR-8 acknowledgement (owner wording)

> OR-8 is ACCEPTABLE_PRECONDITION_DEBT for LILITH DEV_SYNTHETIC only.
>
> The PR-2 rollback/topology inventory is point-in-time evidence.
>
> The 2026-09-29 OR-8 acknowledgement is void under its own time-passing
> condition and is superseded by this owner acknowledgement.
>
> Under ADR-0015 and `CONDITION_3_VALIDITY_MODEL=EVENT_BOUNDED_AND_SEQUENCE_BOUNDED`,
> PR-2 / Condition 3 evidence may support `CHECK_ELIGIBILITY` only when:
>
> - freshly collected immediately before `CHECK_ELIGIBILITY`;
> - collected inside one continuous owner-authorized eligibility sequence;
> - no expiry trigger (a)-(h) occurs between collection and use.
>
> A separate fresh PR-2 revalidation remains mandatory immediately before
> `GENERATE_K_WIT`.
>
> The 2026-10-05 rebaseline is observational evidence only and satisfies
> neither of those future windows.
>
> Expiry means REVALIDATE, not FAIL.
>
> This acknowledgement:
>
> - is not mitigation;
> - establishes no rollback resistance;
> - does not make owner FRESHNESS CURRENT;
> - grants no B-5;
> - authorizes no PR-1B;
> - authorizes no CHECK_ELIGIBILITY;
> - authorizes no M-B1;
> - authorizes no First Memory;
> - does not apply to PROD;
> - becomes void if the validity model changes or an expiry trigger is
>   waived.

## 6. Residual risks (no new OR identifiers; not resolved)

1. **Mapped-package drift** can interrupt the future eligibility sequence
   and cause REVALIDATE (the owner chose scheduling over package holds).
2. **Structured eligibility evidence binding (policy F-2) is not
   implemented.** `evaluate_eligibility` still accepts plain booleans; only
   ADR-0015 SD-12 / policy §9 governance prevents stale evidence from being
   represented as a current `True`.
3. **Mechanical phone-compromise detection is not established.** G-9 is
   satisfied under the accepted owner-observed procedure only.

## 7. State

```text
TECHNICAL_PACKET_COMPONENTS_COMPLETE = YES
B5_PACKET_READY_FOR_SEPARATE_OWNER_DECISION
OR-1 REAFFIRMED
OR-2 / DR-3 REAFFIRMED
CROSS-ENVIRONMENT osAdminLogin REAFFIRMED
OR-3 REAFFIRMED (BOUNDED)
OR-4 REAFFIRMED (QUALIFIED)
OR-5 REMAINS CLOSED
OR-6 REMAINS CLOSED
OR-7 REAFFIRMED
OR-8 NEW ACKNOWLEDGEMENT ADOPTED (2026-09-29 ACKNOWLEDGEMENT VOID AND SUPERSEDED)
OR-9 NOTED AS LIMIT (NOT AN ACCEPTED RISK)
B-5 = WITHHELD
NO B-5 GRANT; NO pr1bAuthorized INPUT ESTABLISHED
CONDITION 3 = NOT CURRENTLY ESTABLISHED
CHECK_ELIGIBILITY = NOT RUN / NOT AUTHORIZED
M-B1 NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
FRESHNESS=UNKNOWN
NO REAL K-ROOT / K-WIT / REGISTRY V1 / GENESIS PIN / RECORD 1
NO REPLICA A / B CHANGE
NO DEV, CLOUD, PACKAGE OR RUNTIME MUTATION
```
