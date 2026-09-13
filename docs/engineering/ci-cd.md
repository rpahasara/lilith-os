# CI/CD Foundation

## Current state

`.github/workflows/ci.yml` performs repository and documentation validation. The product-quality job is deliberately disabled until a product toolchain exists.

`.github/workflows/deploy.yml.example` is deliberately inactive and fails safely if manually copied without implementation. It must not be renamed until the deployment design below is complete and accepted.

## Pull-request CI target

Future CI should enforce:

1. formatting, lint, type, and unit checks;
2. contract and schema compatibility;
3. integration tests with disposable dependencies;
4. lifecycle, idempotency, concurrency, and failure-injection suites;
5. secrets, dependency, source, container, and infrastructure scans;
6. artifact build with immutable identity and provenance;
7. documentation and ADR consistency.

## Deployment gates to decide

- environment model: local, test, staging, production;
- immutable artifact and configuration identity;
- protected GitHub environments and required reviewers;
- workload identity rather than long-lived cloud secrets;
- database migration compatibility, backup, and rollback;
- progressive rollout and health criteria;
- post-deployment read-back and stability window;
- automatic stop versus rollback behavior;
- audit evidence and incident links;
- separation between deployment authority and LILITH capability authority.

## Proposed delivery flow

```text
pull request
  → deterministic checks
  → security and contract tests
  → immutable artifact + provenance
  → sandbox deployment
  → smoke/read-back verification
  → protected environment approval
  → progressive deployment
  → post-deployment verification window
  → complete or rollback
```

## Release readiness checklist

- [ ] Deployment ADR accepted.
- [ ] Threat model names deployment identities and trust boundaries.
- [ ] Artifact is immutable and traceable to source and checks.
- [ ] Secrets use short-lived, scoped identity.
- [ ] Migrations are forward/backward compatible or have tested recovery.
- [ ] Rollback has been exercised, not merely documented.
- [ ] Post-deployment verification checks expected version and behavior.
- [ ] Production environment requires explicit protected approval.
- [ ] Incident owner and evidence retention are defined.

Production should not become the first environment in which failure semantics are discovered.
