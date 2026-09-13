# Contributing to LILITH

Thank you for helping improve LILITH. Contributions can include architecture analysis, research questions, threat scenarios, experiments, documentation, tests, or—when implementation begins—product code.

## Ground rules

- Preserve the boundary between **LILITH** (persistent identity and governed control plane) and **Hermes** (a replaceable runtime substrate).
- Treat tool output, retrieved content, connector data, and model-generated claims as untrusted until validated.
- Do not label work “implemented” without code, “verified” without evidence, or “solved” without stated evaluation criteria.
- Prefer small, reviewable changes with explicit scope and rollback considerations.
- Never commit credentials, personal data, model transcripts containing secrets, or production identifiers.

## Ways to contribute

- Open a [research question](.github/ISSUE_TEMPLATE/research-question.yml).
- Propose an architectural change using the [ADR proposal](.github/ISSUE_TEMPLATE/architecture-decision.yml).
- Report a problem with the [bug form](.github/ISSUE_TEMPLATE/bug-report.yml).
- Propose a capability or improvement with the [feature form](.github/ISSUE_TEMPLATE/feature-request.yml).
- Add an engineering-journal entry using [the journal template](docs/journal/entry-template.md).

## Development flow

1. Create or select an issue that defines the problem and acceptance evidence.
2. For consequential architecture changes, add an ADR in `docs/adr/`.
3. Make the smallest coherent change.
4. Run the repository validation:

   ```shell
   python scripts/validate_repository.py
   ```

5. Update affected documentation, research status, threat model, and roadmap items.
6. Open a pull request using the provided template.

See [Development Notes](docs/engineering/development.md) for the future code-quality model.

## Research-question lifecycle

Every question should have a stable ID, domain, status, motivation, current hypothesis, evidence, proposed experiment, success criteria, risks, dependencies, and next action. Questions are not closed merely because an attractive design exists.

Valid maturity states are:

- `UNKNOWN`: the problem is recognized but poorly bounded.
- `RESEARCH`: alternatives or evaluation methods are under investigation.
- `DESIGNED`: a proposed answer and contracts exist.
- `PARTIAL`: some foundation exists, but the question is not resolved end to end.
- `IMPLEMENTED`: the mechanism exists and has passed its stated tests.
- `VALIDATED`: evidence supports the mechanism under defined operating conditions.
- `SUPERSEDED`: a later question or decision replaces it.

## ADR lifecycle

Use a four-digit sequence and short slug, for example `0005-memory-ownership.md`. ADR statuses are `Proposed`, `Accepted`, `Rejected`, `Deprecated`, or `Superseded by ADR-NNNN`.

An ADR records a decision, not a meeting. Include context, decision, alternatives, consequences, security impact, validation, and revisit triggers.

## Pull-request expectations

- Explain what changed and why.
- Link issues, RQs, and ADRs where applicable.
- Identify affected trust boundaries and state ownership.
- Include verification evidence and failure-path tests.
- State whether the change creates or expands external side effects.
- Keep generated artifacts and unrelated formatting changes out of the diff.

## Commit style

Use clear, imperative summaries. Conventional Commit prefixes are encouraged but not required:

```text
docs: define the runtime identity boundary
research: add evaluation plan for memory decay
security: model approval replay threats
ci: validate internal documentation links
```

## Conduct and security

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md), not in a public issue.
