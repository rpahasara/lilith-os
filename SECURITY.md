# Security Policy

## Project status

LILITH is currently an experimental architecture and research project. No version is declared production-ready or suitable for sensitive, irreversible, financial, safety-critical, or production-infrastructure actions.

## Reporting a vulnerability

Do not open a public issue for a vulnerability, exposed secret, privacy incident, approval bypass, or unsafe capability path.

Until a dedicated private reporting address is configured, use GitHub's private vulnerability-reporting feature on the repository. The repository owner should add a monitored security contact before the first public release.

Include:

- affected component and revision;
- reproduction conditions;
- expected and observed behavior;
- potential impact and blast radius;
- whether credentials or personal data may be involved;
- any safe mitigation already tested.

Do not access data that is not yours, perform destructive testing, degrade a service, or publish exploit details before remediation is coordinated.

## Security design expectations

Changes that introduce capabilities, external writes, memory, authentication, connectors, multi-runtime synchronization, or proactive actions must update the [threat model](docs/security/threat-model.md).

Minimum expectations include least privilege, explicit capability contracts, policy evaluation, approval binding, replay protection, idempotency, secrets isolation, provenance, audit evidence, safe failure, and independent read-back where consequences justify it.

## Supported versions

There are no supported production versions yet. This section will be replaced with a version-support table before the first release.
