# Architecture Decision Records

ADRs preserve consequential decisions, their alternatives, evidence, and tradeoffs. They are immutable once accepted except for minor corrections; changing a decision requires a superseding ADR.

## Index

| ADR | Decision | Status | Date |
| --- | --- | --- | --- |
| [0001](0001-lilith-identity-above-runtimes.md) | LILITH identity exists above replaceable runtimes | Accepted | 2026-09-13 |
| [0002](0002-canonical-durable-state.md) | Durable task and identity state has a canonical authority | Accepted | 2026-09-13 |
| [0003](0003-separate-execution-from-verification.md) | Execution and verification are separate responsibilities | Accepted | 2026-09-13 |
| [0004](0004-clients-cannot-directly-execute-capabilities.md) | Clients cannot directly execute governed capabilities | Accepted | 2026-09-13 |
| [0005](0005-git-driven-production-deployment.md) | Production deployment is Git-driven through governed CI/CD | Accepted | 2026-09-13 |
| [0006](0006-family-neutral-canonical-memory-apply.md) | Canonical memory apply uses family-neutral proposal identity | Accepted | 2026-09-22 |

Use [0000-template.md](0000-template.md) for new decisions.

## Numbering and status

- Use the next four-digit number; never reuse a number.
- Filename: `NNNN-short-kebab-case-title.md`.
- Status: `Proposed`, `Accepted`, `Rejected`, `Deprecated`, or `Superseded by ADR-NNNN`.
- An accepted ADR records what the architecture intends to enforce. It does not by itself prove implementation.

## When an ADR is required

Create an ADR when a choice changes identity continuity, state ownership, trust boundaries, external side effects, authority, persistence, interoperability, deployment, data retention, or a hard-to-reverse dependency. Small local implementation details usually do not need one.
