# Development Notes

## Foundation phase

The repository currently contains architecture, research, security, and workflow scaffolding rather than product code. Toolchain choices should follow the imported implementation and an ADR where they create long-lived constraints.

## Local validation

Requires Python 3.10 or later and no third-party packages:

```shell
python scripts/validate_repository.py
```

The validator checks required files, empty Markdown files, local documentation links, research IDs, ADR naming/status, placeholder deployment safety, and repository-specific invariants.

## Future quality gates

When product code is introduced, define commands for:

- deterministic formatting;
- lint and static analysis;
- type checking;
- unit tests;
- contract/schema compatibility;
- integration tests with synthetic data;
- concurrency, timeout, retry, and crash-recovery tests;
- security and dependency scans;
- migration and restore tests;
- end-to-end verification scenarios.

Do not add a green but meaningless quality gate. Each check should protect a documented invariant or known failure class.

## Suggested package boundaries

The implementation layout is intentionally undecided. Regardless of language, dependency rules should reflect architecture:

```text
clients → application/control contracts
control plane → domain policy and ports
runtime adapters → runtime port
capability adapters → capability port
infrastructure → persistence, queues, secrets, telemetry
```

Domain policy should not import client frameworks, Hermes-specific types, or vendor SDKs. Architecture tests should enforce these boundaries when code exists.

## Test taxonomy

- **Unit:** deterministic policy, fingerprints, lifecycle transitions, ranking, and schemas.
- **Contract:** runtime, capability, connector, state, approval, and evidence interfaces.
- **Integration:** real adapters against sandbox or disposable dependencies.
- **Fault injection:** timeout at commit boundary, duplicate delivery, stale revision, lost response, partial effect, corrupt evidence.
- **Security:** prompt injection, permission bypass, replay, parameter substitution, secret leakage, provenance poisoning.
- **Compatibility:** model/runtime upgrades against identity and policy invariants.
- **Human evaluation:** corrections, interruption appropriateness, continuity, transparency, and trust repair.

## Data and fixtures

Use synthetic fixtures by default. Test data must be labeled and must not be eligible for durable personal memory. Any consented real data requires documented purpose, handling, retention, and deletion.

## Definition of done

A change is done when its observable outcome, failure behavior, documentation, tests, security impact, telemetry, and rollback are addressed in proportion to risk. For capability changes, the definition also includes authority and verification contracts.
