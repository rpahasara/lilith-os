# ADR-0005: Production deployment is Git-driven through governed CI/CD

- **Status:** Accepted
- **Date:** 2026-09-13
- **Owners:** Project maintainers
- **Related:** ADR-0002, ADR-0003

## Context

LILITH's Core API historically existed primarily as source code on the production
GCP VM. This made the runtime host both the deployment target and an implicit
source-of-truth, increasing the risk of configuration drift, unreviewed production
changes, weak rollback provenance, and loss of reproducibility.

The Core API source has now been migrated into Git. GCP remains the current
runtime environment, while Git is the canonical source for backend code.

Production deployment therefore needs a controlled path from reviewed Git state
to the runtime without reintroducing manual source editing on the VM.

The deployment mechanism must preserve LILITH's separation between execution and
verification, must not copy runtime secrets or durable state into Git, and must
remain replaceable if LILITH later moves from GCP to another provider or a
private VPS.

## Decision

Production Core API deployment is Git-driven.

Changes to production backend source must originate from the canonical Git
repository and reach production through the deployment workflow associated with
the protected `main` branch.

The current deployment implementation uses GitHub Actions with:

- GitHub OIDC and Google Workload Identity Federation.
- A dedicated GCP deployment service account.
- IAP and OS Login rather than a public VM SSH endpoint.
- Local backend tests before deployment.
- Production-Python syntax validation before replacement.
- A timestamped backup of the currently deployed source file.
- Controlled installation using the `lilith` runtime ownership.
- systemd service restart.
- an independent `/health` read-back after deployment.
- automatic rollback to the previous source file when restart or health
  verification fails.

No long-lived GCP service-account JSON key is stored in GitHub or the repository.

The deployment workflow owns source delivery only. It does not own or replace
production databases, authority keys, OAuth credentials, Hermes runtime state,
memory files, automation state, logs, or other durable runtime data.

GCP-specific deployment logic is an infrastructure adapter, not part of LILITH's
identity or cognitive architecture. Git remains canonical if the deployment
target changes.

## Alternatives considered

### Manual editing directly on the production VM

Simple for early development, but creates configuration drift, bypasses review
and CI, weakens provenance, and makes rollback dependent on operator discipline.

### Long-lived service-account JSON keys in GitHub Secrets

Operationally straightforward but introduces a persistent credential that must
be stored, rotated, and protected. Workload Identity Federation provides
short-lived credentials without maintaining a downloadable service-account key.

### Containerize and replace the entire runtime immediately

Immutable container deployment is a desirable future direction, but introducing
it now would combine source-of-truth migration, packaging, runtime redesign, and
deployment redesign into one change. The current source-only deployment is a
smaller migration step.

### Treat GCP as the permanent platform

Rejected because deployment infrastructure must remain replaceable. A future
private VPS, container platform, or other cloud environment must not require
changes to LILITH's identity or core architecture.

## Consequences

### Positive

- Git is the canonical production source.
- Production changes gain commit and pull-request provenance.
- Long-lived cloud credentials are avoided.
- Backend tests execute before production deployment.
- Deployment performs explicit post-restart verification.
- Failed deployments have a deterministic rollback path.
- GCP remains replaceable by another deployment target.

### Negative and tradeoffs

- GitHub Actions and GCP Workload Identity Federation add operational
  configuration and IAM complexity.
- The deployment identity has bounded administrative capability on the current
  VM through OS Login.
- The current deployment replaces a Python source file rather than an immutable
  application artifact.
- Production deployment currently depends on GitHub Actions availability and
  Google Cloud control-plane availability.

### Operational and migration impact

The current GCP deployment target remains:

`/home/lilith/.hermes/lilith-os/api/app.py`

The service remains:

`lilith-os-api.service`

Existing SQLite databases, Hermes state, credentials, keys, and other runtime
state remain outside Git and are not modified by the deployment workflow.

A future migration to containers or a private VPS should replace the deployment
adapter while preserving the Git-driven deployment contract.

## Security, privacy, and trust boundaries

GitHub Actions receives no long-lived GCP private key.

GitHub authenticates through OIDC to a Workload Identity Federation provider
restricted to the `rpahasara/lilith-os` repository and the `main` branch.

The dedicated deployment identity receives only the cloud permissions required
for VM discovery, IAP tunneling, OS Login administration, and use of the VM
service account where required by Compute Engine.

Production secrets and durable personal state remain on the runtime side of the
deployment boundary.

Deployment success is not inferred from command completion. The workflow requires
service state verification and an HTTP health read-back. A failed restart or
health check initiates rollback.

## Validation

The deployment architecture is considered operationally validated when:

- repository CI passes before merge;
- backend Goal / Executive tests pass in GitHub Actions;
- GitHub authenticates to GCP using OIDC without a JSON service-account key;
- the candidate source passes syntax validation under the production Python
  runtime;
- `lilith-os-api.service` restarts successfully;
- `/health` returns success after deployment;
- failed restart or failed health verification exercises the rollback path;
- production databases and runtime secrets remain unchanged.

The first successful automated deployment provides implementation evidence for
this accepted architectural decision. Acceptance of this ADR does not itself
prove the deployment implementation correct.

## Revisit triggers

Revisit or supersede this ADR when:

- LILITH moves from GCP to a private VPS or another cloud provider;
- deployment moves to immutable containers or another artifact format;
- multiple production nodes require coordinated rollout;
- zero-downtime or blue/green deployment becomes necessary;
- stronger environment approval or release-signing requirements are introduced;
- deployment authority can be further reduced from current OS Login
  administrative permissions.
