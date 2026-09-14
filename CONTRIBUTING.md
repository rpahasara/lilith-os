# Contributing to LILITH

Thank you for helping improve LILITH. Contributions may include product code, tests, architecture analysis, research questions, threat scenarios, experiments, documentation, and operational improvements.

## Ground rules

- Preserve the boundary between **LILITH** (persistent identity and governed control plane) and **Hermes** (a replaceable execution substrate).
- Preserve ownership boundaries among identity, relationship, memory, goals, cognition, governance, execution, verification, and presence.
- Treat tool output, retrieved content, connector data, memory candidates, and model-generated claims as untrusted until validated.
- Do not label work **AS-IS** or `IMPLEMENTED` without code or operational evidence, `VERIFIED` without stated evidence, or `VALIDATED` without defined operating conditions and evaluation criteria.
- Keep TARGET, RESEARCH, and HISTORICAL material visibly distinct from current implementation.
- Prefer small, reviewable changes with explicit scope, failure behavior, verification, and rollback or recovery considerations.
- Never commit credentials, private keys, personal data, secret-bearing transcripts, production state, or unredacted security material.
- Do not edit `main`, DEV, or PROD directly. Git and the governed pull-request pipeline are the authority for changes.

## Ways to contribute

- Open a [research question](.github/ISSUE_TEMPLATE/research-question.yml).
- Propose an architectural change using the [ADR proposal](.github/ISSUE_TEMPLATE/architecture-decision.yml).
- Report a problem with the [bug form](.github/ISSUE_TEMPLATE/bug-report.yml).
- Propose a capability or improvement with the [feature form](.github/ISSUE_TEMPLATE/feature-request.yml).
- Add an engineering-journal entry using [the journal template](docs/journal/entry-template.md).
- Improve the frontend, Core API, tests, validation, security boundaries, or documentation.

## Governed development flow

`main` is production-ready only. The supported change path is:

1. Create or select an issue that defines the problem, scope, risks, and acceptance evidence.
2. Create a feature branch. Do not work directly on `main` or on a deployment host.
3. Add or update an ADR before implementation when a change alters ownership, trust boundaries, public contracts, durable state, authority, or a consequential architecture decision.
4. Make the smallest coherent change and add tests for the intended behavior, failure paths, and relevant recovery behavior.
5. Run the applicable repository, frontend, and Core API validation locally.
6. Update affected documentation, research status, threat model, roadmap, and operational guidance in the same change.
7. Open a pull request using the repository template.
8. Keep the branch up to date and resolve all failures against the exact candidate commit.
9. Merge only after the four required checks pass.
10. For Core API deployment-path changes, confirm the post-merge production workflow and health evidence. Use a follow-up pull request for corrections; do not patch PROD directly.

The four merge gates are:

1. `Repository contracts`
2. `Frontend build and command core`
3. `Core API tests`
4. `LILITH DEV deployment`

The first three checks validate the pull-request candidate. After CI succeeds, the exact candidate SHA is deployed to isolated DEV using trusted deployment controls from the default branch. The DEV gate reports success only after the service and `/health` checks pass.

The current solo-repository ruleset requires zero human approvals, but this does not remove governance: a pull request, an up-to-date branch, and all four machine-verifiable checks remain mandatory. Approval requirements should be revisited as the contributor base or release risk grows.

## Local validation

Run validation proportional to the affected area and ensure it mirrors the intent of CI.

Repository contract validation includes whitespace checks and:

```shell
python scripts/validate_repository.py
```

Frontend validation includes:

- clean dependency installation;
- a high-severity production dependency audit;
- a production build; and
- the Command Core self-test.

Core API validation uses Python 3.12 and includes:

- dependency installation;
- compilation of `services/core-api/app.py`; and
- unit-test discovery and execution.

Consult [Development Notes](docs/engineering/development.md) and the current workflows for supported commands and environment prerequisites. A local pass is useful evidence, but the required checks on the pull-request SHA remain authoritative for merge.

## Pull-request expectations

A pull request should:

- explain the outcome and why the change is needed;
- link relevant issues, research questions, and ADRs;
- identify affected state owners, trust boundaries, capabilities, and external side effects;
- distinguish implemented behavior from target or research intent;
- include validation evidence for success and failure paths;
- describe rollback, compensation, or reconciliation behavior where state or external systems can change;
- identify schema, migration, compatibility, privacy, or deployment effects;
- update documentation and operational guidance where behavior changed; and
- exclude unrelated formatting changes, secrets, personal data, and unnecessary generated artifacts.

An API call or green process exit is not sufficient proof of user-visible success when independent read-back is practical and proportionate to the consequence.

## Research-question lifecycle

Every research question should have a stable ID, domain, status, motivation, current hypothesis, evidence, proposed experiment, success criteria, risks, dependencies, and next action. Questions are not closed merely because an attractive design exists.

Valid maturity states are:

- `UNKNOWN`: the problem is recognized but poorly bounded.
- `RESEARCH`: alternatives or evaluation methods are under investigation.
- `DESIGNED`: a proposed answer and contracts exist.
- `PARTIAL`: a foundation exists, but the question is not resolved end to end.
- `IMPLEMENTED`: the mechanism exists and has passed its stated tests.
- `VALIDATED`: evidence supports the mechanism under defined operating conditions.
- `SUPERSEDED`: a later question or decision replaces it.

When implementation changes the evidence, update the research entry without rewriting its history. Record negative results and unresolved uncertainty. Do not make unsupported claims of novelty, consciousness, subjective experience, or solved welfare.

## ADR lifecycle

Use a four-digit sequence and short slug, for example `0005-memory-ownership.md`. ADR statuses are `Proposed`, `Accepted`, `Rejected`, `Deprecated`, or `Superseded by ADR-NNNN`.

An ADR records a decision, not a meeting. Include:

- context and the invariant or problem being decided;
- the decision and ownership boundaries;
- alternatives considered;
- consequences and compatibility impact;
- security, privacy, authority, and data-lifecycle impact;
- validation and operational evidence; and
- revisit or supersession triggers.

Accepted ADRs govern implementation until explicitly superseded. If code and an ADR diverge, resolve the inconsistency rather than silently treating one as stale.

## Security and threat-model updates

Update the [Threat Model](docs/security/threat-model.md) when a change introduces or materially alters:

- external writes or irreversible effects;
- authentication, authorization, approvals, or delegated authority;
- secrets, credentials, connectors, workers, or runtime adapters;
- canonical memory, relationship state, identity, provenance, or deletion behavior;
- prompt-injection or memory-poisoning exposure;
- cross-device or multi-runtime synchronization;
- proactive behavior, schedules, background work, or notifications;
- CI/CD identity, cloud IAM, network access, deployment, rollback, or environment boundaries; or
- handling of personal, sensitive, sealed, or local-only data.

Design for least privilege, approval binding, expiry and revocation, replay protection, idempotency, provenance, auditable evidence, safe failure, and independent read-back where consequences justify it. Keep DEV and PROD identities, state, credentials, and personal data isolated.

Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md), not in a public issue or pull request.

## Commit style

Use clear, imperative summaries. Conventional Commit prefixes are encouraged but not required:

```text
docs: define the runtime identity boundary
research: add evaluation plan for memory decay
security: model approval replay threats
ci: validate internal documentation links
```

## Conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
