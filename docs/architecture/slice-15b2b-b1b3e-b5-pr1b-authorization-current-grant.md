# Slice 15B2b-B1b-3e — B-5: Owner Grant for the Current DEV_SYNTHETIC Packet (2026-10-06)

Status:

- **`B5_OWNER_AUTHORIZATION=GRANTED`** (new explicit owner decision,
  2026-10-06). This is Outcome A of the
  [B-5 decision packet](slice-15b2b-b1b3e-b5-pr1b-authorization-decision.md)
  §12, given for the **current DEV_SYNTHETIC packet**: the
  [B-5 packet refresh and owner risk review](slice-15b2b-b1b3e-b5-packet-refresh-owner-risk-review.md)
  merged in PR #145.
- **B-5 GRANTED is not `PR1B_ELIGIBLE`.** This record does not run
  `CHECK_ELIGIBILITY`, evaluates no eligibility boolean, and creates no
  eligibility result.
- **M-B1 is NOT AUTHORIZED. First Memory is NOT AUTHORIZED.** Owner
  freshness is `FRESHNESS=UNKNOWN`.
- **Documentation only.** No live system was contacted and nothing was
  executed.
- Append-only. The historical
  [2026-09-30 GRANTED record](slice-15b2b-b1b3e-b5-pr1b-authorization-granted.md)
  (void under packet §9) and the
  [2026-10-05 WITHHELD re-decision](slice-15b2b-b1b3e-b5-pr1b-authorization-withheld.md)
  are not edited and remain true as dated history. The packet-ready record
  also remains true: the packet was ready for a separate owner decision.
  This record is that later decision.

```text
packet ready != B-5 GRANTED != PR1B_ELIGIBLE != M-B1 go != First Memory
proposal != authority
approval evidence != execution
policy evaluation != authorization
execution != verification
```

| Field | Value |
| --- | --- |
| Control `main` at the decision | `47f2655` (merge of PR #145) |
| Packet record | [`slice-15b2b-b1b3e-b5-packet-refresh-owner-risk-review.md`](slice-15b2b-b1b3e-b5-packet-refresh-owner-risk-review.md) |
| Decision date | 2026-10-06 |
| Environment | DEV_SYNTHETIC only |

## 1. Owner statement (verbatim)

> I grant B-5 for the current DEV_SYNTHETIC packet.

## 2. Preconditions satisfied before the grant

The packet record established, before this decision:

```text
TECHNICAL_PACKET_COMPONENTS_COMPLETE = YES
B5_PACKET_READY_FOR_SEPARATE_OWNER_DECISION
```

| Component | State at the grant (from the packet record) |
| --- | --- |
| Condition 1 | PASS (fresh) |
| Condition 2 / DR-5 | CURRENT through `53d7405` and the accepted post-#144 comparison |
| Replica B currentness | ESTABLISHED |
| `ownerRegisterKnownEmpty` | ESTABLISHED |
| custody G-9 | ESTABLISHED under the accepted owner-observed procedure only |
| B-5 packet §9 stop conditions | none fired |
| global invalidators G-1 … G-9 | none observed |
| owner risk review OR-1 … OR-9 | complete before the grant (§6) |

The [ADR-0015](../adr/0015-operational-evidence-invalidated-by-material-substrate-drift.md)
SD-13 ordering is respected: substrate-drift policy accepted, then the fresh
evidence packet, then **this** new explicit owner B-5 decision.

## 3. Grant semantics

- **`B5_OWNER_AUTHORIZATION=GRANTED`** for the current DEV_SYNTHETIC packet.
- In the sequencing semantics of the decision packet §3 and §12 Outcome A,
  the grant authorizes the owner-asserted input **`pr1bAuthorized = True`**
  for a future P1B-0 `CHECK_ELIGIBILITY` evaluation **only**. It is not a
  source flag and is not persisted anywhere.
- **The input is authorized, not supplied.** It is not supplied in this
  pass, and nothing is evaluated. It may be supplied only inside a future
  owner-authorized eligibility sequence, and only while this grant is not
  void (§7).
- The grant satisfies **only** the owner-authorization precondition
  (`PR1B_NOT_AUTHORIZED`). Every other eligibility input must be backed by
  evidence current at that moment (ADR-0015 SD-12). A historical PASS may
  not be converted into a current `True`.

## 4. Scope

The grant is:

- **DEV_SYNTHETIC only**;
- tied to the **current accepted B-5 packet** (the packet refresh record
  above), not to any earlier or later packet;
- dependent on that packet's accepted evidence remaining reusable and
  current under ADR-0015 and the
  [substrate-drift policy](substrate-drift-and-evidence-revalidation-policy-v0.1.md);
- subject to every applicable stop, void and revalidation trigger (§7);
- **not applicable to PROD** and not transferable to PROD;
- **not a general future grant**;
- **not permission to bypass later sequencing**.

## 5. What the grant permits

Progression to the **next, separately controlled** eligibility sequence.
It does not establish the final inputs to `CHECK_ELIGIBILITY`. The next
sequence remains:

```text
fresh final Condition 3
  -> CHECK_ELIGIBILITY
  -> separate M-B1 go decision
  -> M-B1
```

None of these steps is performed or authorized by this record. Each needs
its own owner authorization when it is reached:

- the final Condition 3 window must follow the
  [validity-window owner decision](slice-15b2b-b1b3e-condition3-validity-window-owner-decision.md)
  (event- and sequence-bounded; collected immediately before
  `CHECK_ELIGIBILITY` inside one continuous owner-authorized eligibility
  sequence);
- the decision packet §11 preconditions are checked at that moment;
- the M-B1 go statement remains a separate explicit owner statement. Its
  template's burned-identity wording means the canonical 20
  ([expansion](slice-15b2b-b1b3e-burned-identities-expansion.md)).

## 6. What is still not authorized

This repository-only pass authorizes none of:

- live DEV contact, GCP contact, GitHub Actions or log contact;
- phone contact, Replica A or Replica B contact;
- package queries;
- final Condition 3 collection;
- `CHECK_ELIGIBILITY`, or manual evaluation of the eligibility booleans;
- M-B1, `GENERATE_K_ROOT` (K-ROOT), `GENERATE_K_WIT` (K-WIT);
- registry or genesis mutation, record 1;
- First Memory;
- deployment, restart or reboot;
- IAM mutation;
- any live system mutation;
- any PROD action.

## 7. Validity, void and revalidation

No universal wall-clock TTL is set. The grant is bound to the accepted
packet and to ADR-0015. It must not be treated as sufficient once a
relevant accepted stop or invalidation condition has occurred.

Two different outcomes are kept apart:

```text
grant VOID        -> owner must re-decide B-5 (new explicit decision)
evidence REVALIDATE -> grant stands; it cannot be relied on to progress
                       until the affected evidence is re-established
REVALIDATE -/-> B-5 FAILED, unless the controlling record says the grant is void
```

**VOID (controlling record: decision packet §9).** The packet §9 states
that any one of its stop conditions **voids** a GRANTED authorization
before M-B1, and the owner must then re-decide. That remains in force for
this grant, unchanged. It includes, for example: an unreviewed cloud or host
topology or IAM change; a PR-2 revalidation other than PASS; a DR-5 result
set other than the accepted one after a deployment; `status --expect P1A-9`
failing; broker preservation other than PASS; activation other than
`GRANT_ABSENT`; either replica not empty or not byte-continuous, or a nested
Replica B; real authority material appearing before M-B1; an unreviewed
change to `REAL_ACCEPTANCE_ENABLED`, `burned_identities`, the
owner-freshness tool or the sequencer; suspected phone compromise, phone
loss or loss of Termux private storage; laptop compromise or rollback; ADB,
SSH or automation access to Termux; the owner being unable to run M-B1
entirely on the S25; an unreviewed M-B1 package change or a bundle not from
a merged SHA. Where a G-1 … G-9 global invalidator, or a replica or custody
invalidation, is also one of these stop conditions, the grant is **VOID**.

**REVALIDATE (ADR-0015 SD-1, SD-5, SD-6, SD-13).** An event that only makes
evidence not reusable, and is not itself a §9 stop condition, means
**REVALIDATE, not FAIL**, and does not by itself void the grant. Examples:

- relevant material dependency drift (including mapped-package drift);
- a G-1 … G-9 global invalidator that is not a §9 stop condition;
- a later deployment: DR-5 must be freshly re-compared before eligibility.
  An equal result set re-establishes currentness; a different one is a §9
  stop and voids the grant;
- expiry of the separate Condition 3 window under its triggers (a)-(h).

If the re-established evidence is then other than PASS, or not equal to the
accepted result, the matching §9 stop applies and the grant is **VOID**.

**Unknown classification fails closed.** If it is unknown whether an event
is a §9 stop condition, the grant may not be relied on until the owner
records a determination. That is neither a FAIL nor a VOID claim.

**Condition 3 is separate.** Its window is event- and sequence-bounded and
belongs to the future eligibility sequence. The grant does not start,
extend or substitute for that window.

**Not checked in this pass.** Whether any deployment ran after the accepted
DR-5 comparison (for example on the merge of PR #145) was not checked: no
GitHub contact was authorized. Any such deployment needs a fresh DR-5
comparison before eligibility (Condition 3 trigger (f)).

## 8. Owner risk state (unchanged by this grant)

The packet-review dispositions are preserved. None is reopened or altered.

| Item | Disposition |
| --- | --- |
| OR-1 | REAFFIRMED |
| OR-2 / DR-3 | REAFFIRMED |
| cross-environment `osAdminLogin` | REAFFIRMED |
| OR-3 | REAFFIRMED (bounded) |
| OR-4 | REAFFIRMED (qualified) |
| OR-5 | CLOSED |
| OR-6 | CLOSED |
| OR-7 | REAFFIRMED |
| OR-8 | NEW ACKNOWLEDGEMENT ADOPTED |
| OR-9 | LIMIT / NOTED (not an accepted risk) |

Residual facts, **not resolved by this grant**:

1. mapped-package drift can interrupt the future eligibility sequence;
2. F-2 structured eligibility evidence binding remains unimplemented
   (`evaluate_eligibility` still takes plain booleans);
3. mechanical phone-compromise detection remains unestablished.

Custody obligations, burned-identity rules (the canonical 20) and the
accepted debt of decision packet §8 remain in force. Whole-host rollback
resistance is **NOT ESTABLISHED**. Owner freshness does not protect against
rollback or compromise of both replicas simultaneously.

## 9. Blocker state

| # | Blocker | State |
| --- | --- | --- |
| B-5 | PR-1B not authorized | **GRANTED** for the current DEV_SYNTHETIC packet (this record); subject to §7 |

B-1 … B-4 keep their historical closure. Their inputs are checked again
inside the future eligibility sequence.

## 10. State

```text
B5_OWNER_AUTHORIZATION=GRANTED
SCOPE = CURRENT DEV_SYNTHETIC PACKET (PR #145) ONLY
TECHNICAL PACKET COMPLETE BEFORE GRANT
OWNER RISK REVIEW COMPLETE BEFORE GRANT
pr1bAuthorized INPUT AUTHORIZED FOR A FUTURE CHECK_ELIGIBILITY ONLY; NOT SUPPLIED; NOTHING EVALUATED
B-5 GRANTED != PR1B_ELIGIBLE
PR1B_ELIGIBLE = NOT ESTABLISHED
CONDITION_3_CURRENT = NOT_ESTABLISHED
CHECK_ELIGIBILITY = NOT RUN / NOT AUTHORIZED
M-B1 = NOT AUTHORIZED
FIRST MEMORY = NOT AUTHORIZED
FRESHNESS=UNKNOWN
NOT APPLICABLE TO PROD
GRANT SUBJECT TO DECISION PACKET §9 (VOID) AND ADR-0015 (REVALIDATE)
NO REAL K-ROOT / K-WIT / REGISTRY V1 / GENESIS PIN / RECORD 1
NO REPLICA A / B CHANGE
NO LIVE SYSTEM CONTACTED
NO DEV, CLOUD, PACKAGE OR RUNTIME MUTATION
```

> **Later current state (2026-10-05T20:15Z, pointer only; the state above is
> preserved as written and was true at this record's date).** Inside a
> separate owner-authorized eligibility sequence, the canonical evaluator
> was called once and returned `PR1B_ELIGIBLE`
> ([eligibility sequence 3](slice-15b2b-b1b3e-pr1b-eligibility-sequence3.md)).
> Its Condition 3 window has since expired. By a later
> [owner decision](slice-15b2b-b1b3e-mb1-eligibility-carry-forward-owner-decision.md),
> that completed result is not reusable for a later M-B1: a future M-B1
> sequence must freshly establish eligibility. M-B1, K-ROOT, K-WIT and First
> Memory remain NOT AUTHORIZED.
