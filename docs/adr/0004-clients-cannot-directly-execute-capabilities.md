# ADR-0004: Clients cannot directly execute governed capabilities

- **Status:** Accepted
- **Date:** 2026-09-13
- **Owners:** Project maintainers
- **Related:** RQ-026, RQ-028, RQ-047, RQ-048

## Context

Web, voice, mobile, and future ambient clients process untrusted input and may be compromised, stale, or inconsistently updated. If they directly invoke external capabilities, policy, approval binding, canonical task state, and audit can be bypassed.

## Decision

Clients capture user intent and present semantic state. Governed capability execution must pass through the LILITH control plane, including canonical task creation, policy evaluation, approval where required, runtime delegation, and verification.

Clients may perform narrowly defined local presentation operations that do not cross a governed capability boundary.

## Alternatives considered

### Direct client integration

Reduces latency and backend work but distributes credentials, policy, and audit across untrusted surfaces.

### Client-side policy checks

Useful for early feedback but insufficient as an authorization boundary because clients can be modified or stale.

## Consequences

### Positive

- One reviewable governance and evidence path.
- Clients remain replaceable and lower privilege.
- Approval and state transitions cannot be skipped by UI code.

### Negative and tradeoffs

- Control-plane availability and latency affect actions.
- Local/offline features require carefully defined exceptions.

## Security, privacy, and trust boundaries

Clients are outside the principal authorization boundary. They should receive minimum data, store minimal secrets, and render untrusted content safely.

## Validation

- Architecture tests ensure capability adapters are inaccessible from client packages.
- End-to-end tests prove approval-required actions cannot execute through alternate endpoints.
- Penetration tests cover forged client state and replayed approvals.

## Revisit triggers

- A formally scoped offline capability model is accepted.
- Platform constraints require a local operation and an ADR defines its authority boundary.
