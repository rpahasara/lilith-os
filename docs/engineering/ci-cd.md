# CI/CD Foundation

## Current protected-main flow

Pull requests run `.github/workflows/ci.yml` with three candidate-validation
jobs:

1. **Repository contracts** — whitespace and repository/documentation rules.
2. **Frontend build and command core** — locked install, production dependency
   audit, production build, and Command Core self-test.
3. **Core API tests** — dependency install, full Core API/package compilation,
   service test discovery, and deterministic Slice 8–15 cognitive regressions.

After those checks succeed for a same-repository pull request to the default
branch, `.github/workflows/deploy-dev.yml` publishes the required
`LILITH DEV deployment` status. It authenticates with GitHub OIDC and Google
Workload Identity Federation, reaches the private VM through IAP, deploys the
exact CI-validated SHA, and verifies service health and deployed identity.

The DEV workflow intentionally checks out two revisions:

- deployment builder, verifier, bootstrap, and remote installer controls from
  the trusted default branch;
- candidate runtime and tests from the exact successful CI SHA.

Therefore a pull request that changes the trusted deployment controls cannot
exercise those new controls until they are present on the trusted branch. The
old trusted workflow remains authoritative meanwhile; this is a deliberate
bootstrap boundary, not permission to run candidate-controlled deploy logic.

## Multi-file Core API DEV artifact

The DEV artifact is a deterministic gzip/tar bundle built from an explicit
allowlist. It contains `app.py`, requirements, the Git-governed
`lilith_memory` package, and isolated Core API tests. It excludes working-tree
files, frontend assets, secrets, databases, backups, caches, and unrelated
repository content.

The attestation records the candidate SHA, every file path/hash/size, and the
archive hash/size. A trusted verifier requires the exact member set, rejects
links and path traversal, verifies every byte, and writes the bundle identity
into the staged release.

The remote installer uses SHA-named immutable release directories and an atomic
`current` symlink. Before switching it compiles the candidate and runs the
isolated synthetic Core API suite. After switching it restarts the DEV service,
checks systemd and `/health`, then reads back the candidate SHA and bundle hash.
Failure restores the previous symlink and service.

DEV uses dedicated cognitive and Privacy database paths and a server-owned
canonical config whose initial state is:

```json
{"activeCapabilities":[],"canonicalLtmEnabled":false,"schemaVersion":1}
```

Tests and synthetic fixtures reject the production database path. Deployment
does not run a migration automatically.

## Production

Production Core API delivery remains governed by ADR-0005. Slice 15B2b-A does
not broaden the production workflow, deploy the canonical package, run a
canonical schema migration, activate a tuple/capability/kill switch, or mutate
production state. Production deployment changes require a later reviewed stage
and the normal protected-main path.

## Required evidence

- candidate SHA equals the CI workflow-run SHA;
- bundle and per-file hashes verify before install;
- no secret or unallowlisted path enters the artifact;
- isolated tests pass before the switch;
- service restart and `/health` pass after the switch;
- deployed SHA and bundle hash read back exactly;
- failure returns to the prior release;
- database migration has separate fresh backup evidence;
- deployment authority remains separate from canonical-memory capability
  authority.
