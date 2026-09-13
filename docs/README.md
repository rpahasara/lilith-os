# LILITH Documentation

This directory is the architectural and research source of truth for LILITH. It separates observed current state, accepted decisions, target designs, research hypotheses, and future intentions so that they cannot be mistaken for one another.

## Reading order

1. [Glossary](glossary.md)
2. [Architecture Overview](architecture/README.md)
3. [Architectural Principles](architecture/principles.md)
4. [Current State](architecture/as-is.md)
5. [Target Architecture](architecture/target.md)
6. [Research Question Register](research/research-question-register.md)
7. [Roadmap](roadmap/roadmap.md)
8. [Threat Model](security/threat-model.md)
9. [ADR Index](adr/README.md)

## Document authority

When documents disagree, use this precedence for architectural claims:

1. Tested behavior and versioned contracts
2. Accepted ADRs
3. Current-state architecture backed by repository evidence
4. Target architecture
5. Research hypotheses and engineering-journal entries

Conflicts should be made explicit and resolved through an ADR or corrective pull request. A later date alone does not make a document authoritative.

## Documentation labels

Use these labels in prose where ambiguity is possible:

- **OBSERVED** — directly supported by code, trace, test, or deployed-system evidence.
- **REPORTED** — recorded in prior engineering material but not yet reproduced here.
- **DECIDED** — governed by an accepted ADR.
- **PROPOSED** — concrete target awaiting acceptance or implementation.
- **HYPOTHESIS** — falsifiable research proposition.
- **UNKNOWN** — an unresolved question with no preferred answer.

## Maintenance rule

Every product pull request should answer: what documentation became false because of this change? Every research result should update its question, evidence, limitations, and next action. Every superseded decision should retain its history and point to its replacement.
