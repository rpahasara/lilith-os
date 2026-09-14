# Security Policy

## Project status and scope

LILITH is an experimental engineering and research project.

The project has a private PROD deployment for the backend/Core API, reached through the governed repository delivery process. This is an operational environment, not a supported public or general-purpose production release. Production frontend hosting has not been established.

No current version is represented as safe or supported for sensitive, irreversible, financial, safety-critical, or production-infrastructure actions. The existence of a PROD environment, passing health check, successful tool call, or implemented control is not a claim of complete system safety.

## Reporting a vulnerability

Do not open a public issue or pull request for a vulnerability, exposed secret, privacy incident, approval bypass, unsafe capability path, prompt-injection exploit, memory-poisoning path, or deployment-boundary weakness.

Until a dedicated private reporting address is configured, use GitHub's private vulnerability-reporting feature on the repository. The repository owner should add a monitored security contact before the first public release.

Include:

- the affected component, environment, and revision or candidate SHA;
- reproduction conditions and required privileges;
- expected and observed behavior;
- potential impact and blast radius;
- affected authority, trust, state, data, or deployment boundaries;
- whether credentials, personal data, canonical memory, or external side effects may be involved; and
- any safe mitigation or containment already tested.

Do not access data that is not yours, perform destructive testing, degrade a service, persist access, or publish exploit details before remediation is coordinated. Stop testing when further work could create external effects or expose private data.

## Security design expectations

Changes that introduce or alter capabilities, external writes, memory, identity, authentication, approvals, delegated authority, connectors, workers, multi-runtime or cross-device synchronization, proactive actions, or deployment infrastructure must update the [Threat Model](docs/security/threat-model.md).

Minimum expectations include:

- least privilege and explicit capability contracts;
- policy evaluation before execution;
- approvals bound to the exact action, parameters, scope, actor, target, and validity window;
- expiry, revocation, replay protection, and idempotency;
- separation of proposal, authorization, execution, and verification;
- isolated secrets and credentials that are never treated as model context or repository content;
- provenance, append-only or tamper-evident audit evidence where appropriate, and traceable state revisions;
- safe failure, bounded retries, cancellation semantics, and explicit handling of ambiguous outcomes;
- independent read-back and evidence sufficiency for consequential actions;
- strict ownership boundaries for identity, relationship, canonical memory, goals, policy, and verification; and
- environment isolation so DEV cannot use PROD credentials, personal state, or canonical production data.

## Untrusted content, prompt injection, and memory poisoning

Model output, tool output, retrieved documents, webpages, connector payloads, messages, files, and other external content are untrusted inputs. Content must not be able to grant itself authority, change policy, approve an action, expand capability scope, expose secrets, or bypass verification.

Memory writes require governed admission. Candidate memories should retain source, time, confidence, sensitivity, derivation, and contradiction information. Untrusted content must not silently become canonical identity, relationship truth, policy, permission, or autobiographical memory. Corrections and deletion must be traceable, and retrieved memory remains subject to current authority and privacy policy.

Controls should address indirect prompt injection, instruction/data confusion, malicious tool results, poisoned retrieval, provenance loss, approval replay, stale authority, cross-context leakage, and deceptive verification evidence.

## CI/CD and cloud boundaries

- Git is the authority for source. DEV and PROD hosts are deployment targets, not editing environments.
- `main` is protected and contains production-ready commits only. Direct changes to `main` or production hosts are outside the supported model.
- A pull-request candidate must pass `Repository contracts`, `Frontend build and command core`, `Core API tests`, and `LILITH DEV deployment` before merge.
- DEV deployment uses trusted controls from the default branch and deploys the exact CI-validated candidate SHA to an isolated environment.
- The DEV deployment status succeeds only after the service and `/health` checks pass. A health response proves a bounded service condition, not the correctness or safety of every workflow.
- Relevant Core API changes merged to `main` can trigger the private PROD deployment, which validates, backs up the current source, restarts, reads back service health, and invokes rollback on defined restart or health failures.
- Cloud authentication uses short-lived OIDC/Workload Identity Federation rather than committed long-lived Google service-account keys.
- Runtime access is through private hosts using IAP and OS Login. Network, IAM, service-account, and firewall scope must remain least-privileged and auditable.
- Runtime secrets remain on the runtime side of the trust boundary. Logs, build output, artifacts, caches, and failure reports must not expose them.
- DEV and PROD state, databases, identities, and credentials must remain isolated. Deployment success does not authorize migration or copying of personal production state into DEV.
- A failed or interrupted deployment can be ambiguous. Reconcile the actual service, revision, health, and external effects before retrying. Source rollback alone is not disaster recovery.

## Supported versions

There are no supported public production versions at this time. This section will be replaced with a version-support table and defined security-maintenance policy before the first supported release.
