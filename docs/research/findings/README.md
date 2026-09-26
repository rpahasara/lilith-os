# Research Findings

Status: **RECONCILIATION RECORDS** — evidence-based findings for research
questions that have meaningful project evidence. They are the factual
foundation for future articles and papers. They are not accepted architecture,
not canonical status changes, and not publications.

Each record is filed under its primary in-repo RQ number and names related
questions. *(Primary-source pass, 2026-09-26: every finding refers to the
**REPO** namespace, `REPO:RQ-NNN`; each now opens with its MASTER equivalent
from the [crosswalk](../rq-register-crosswalk.md) and the primary-source
evidence that replaced earlier REPORTED claims.)* Questions with no project evidence have no finding record; they
remain visibly open in the [RQ evidence map](../rq-evidence-map.md).

## Claim discipline

Every "Current answer" separates five kinds of statement:

| Label | Meaning |
| --- | --- |
| **PROVEN** | Demonstrated by cited tests or runs, **within the stated scope and environment only**. |
| **DESIGNED** | A design or invariant exists; not demonstrated. |
| **INFERRED** | This record's interpretation of evidence. |
| **HYPOTHESIS** | A falsifiable proposition not yet tested. |
| **UNKNOWN** | No evidence either way. |

Scope words matter: "TEST" means synthetic data in CI or sandbox; "DEV" means
synthetic state on `lilith-dev-01`; "pre-DEV live" means real data on
`lilith-01` before a DEV environment existed (2026-09-07 → 09-10). No finding
involves real canonical memory or real owner authority, because neither exists.

Wording rule: use "current evidence supports …", never universal claims. No
novelty, "first", consciousness, or human-emotion claims are made; none is
supported by a literature review.

## Index

| Finding | Primary RQ (REPO) | MASTER semantic match | Related REPO RQs | Maturity of the answer |
| --- | --- | --- | --- | --- |
| [Identity continuity](rq-001-identity-continuity.md) | REPO:RQ-001 | MASTER:RQ-001 | 002, 003 | Design only; key artifact missing |
| [Shared canonical state across channels](rq-004-shared-state-across-channels.md) | REPO:RQ-004 | MASTER:RQ-002 | 005, 007, 024 | Operational for channels; runtimes untested |
| [Duplicate-action prevention](rq-008-duplicate-action-prevention.md) | REPO:RQ-008 | MASTER:RQ-026 | 033, 039 | Proven for internal writes |
| [Memory admission](rq-009-memory-admission.md) | REPO:RQ-009 | MASTER:RQ-003 | 010, 014, 017 | Mechanics proven (TEST/DEV); criteria untested |
| [Forgetting and deletion](rq-011-forgetting-and-deletion.md) | REPO:RQ-011 | MASTER:RQ-005 | 016, 049 | Mechanics proven (TEST); decay and backups open |
| [Contradiction and supersession](rq-012-contradiction-and-supersession.md) | REPO:RQ-012 | MASTER:RQ-006 | 013, 038 | Proven for beliefs (pre-DEV live) |
| [Provenance and explanation](rq-013-provenance-and-explanation.md) | REPO:RQ-013 | MASTER:RQ-007 | 038, 036 | Proven for beliefs and synthetic memory chains |
| [Inference is not memory](rq-015-inference-is-not-memory.md) | REPO:RQ-015 | MASTER:RQ-009 | 009, 047 | Structural separation proven; not adversarially tested |
| [Goal arbitration and executive focus](rq-019-goal-arbitration.md) | REPO:RQ-019 | MASTER:RQ-011 | 018, 020 | Deterministic arbitration proven (pre-DEV live) |
| [Playbooks, planning, replanning](rq-021-playbooks-and-planning.md) | REPO:RQ-021 | MASTER:RQ-013 | 022, 023, 025 | Deterministic paths live; model paths not wired |
| [Authority gradient and ethics boundary](rq-026-authority-gradient.md) | REPO:RQ-026 | MASTER:RQ-019 | 027, 030, 031, 032 | Static gradient proven; contextual risk open |
| [Approval and owner-authorization binding](rq-028-approval-binding.md) | REPO:RQ-028 | MASTER:RQ-021 | 029 | Strongest evidence in the portfolio (scoped) |
| [Unknown state and crash semantics](rq-033-unknown-state-and-crash-semantics.md) | REPO:RQ-033 | MASTER:RQ-027 | 008, 037 | Unit-proven; live crash experiment did not run |
| [Execution is not verification](rq-034-execution-is-not-verification.md) | REPO:RQ-034 | MASTER:RQ-028 | 035, 036, 037 | Proven repeatedly, including through failures |
| [Attention, motivation, and affect boundaries](rq-040-attention-motivation-affect.md) | REPO:RQ-040 | MASTER:RQ-048 (+ MASTER:RQ-121 for affect) | 041, 014 | Mechanics live; behavioural effect near zero |
| [Evaluation and regression](rq-044-evaluation-and-regression.md) | REPO:RQ-044 | MASTER:RQ-068 | 045, 050 | Engineering regression only |
| [Injection, secrets, and deployer authority](rq-047-injection-secrets-authority.md) | REPO:RQ-047 | MASTER:RQ-035, 037 (partial) | 046, 048 | Structural controls; custody gap open |

## Record template

```markdown
# RQ-NNN — Title

Research question · Why it matters to LILITH · Original hypothesis / problem ·
Architecture explored · Experiments / implementation slices · Evidence ·
Negative findings / failures · Current answer (PROVEN / DESIGNED / INFERRED /
HYPOTHESIS / UNKNOWN) · Confidence / maturity · What remains unanswered ·
Related RQs · Related slices · Publication notes
```
