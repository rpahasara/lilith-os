# REPO:RQ-028 — Binding approval and owner authorization to exactly what executes

> **Namespace (primary-source pass, 2026-09-26).** This finding is filed
> under **REPO:RQ-028** (in-repo register). MASTER equivalent: MASTER:RQ-021 (SEMANTIC MATCH); related MASTER:RQ-022, 023.
> See the [crosswalk](../rq-register-crosswalk.md).
>
> **Primary-source evidence added:**
> - J1 "Next planned work" (compiled 2026-09-07, PRIMARY) states Slice 4's requirements before it was built: durable approval state, no side effect before approval, action fingerprinting, idempotency, read-back, denial/cancellation, persistent audit.
> - MASTER:RQ-021: "This requirement was explicitly identified for the first real approval-gated write."

## Research question

How is approval bound to exactly what executes? (In-repo RQ-028; related
RQ-029 approval validity over time.)

## Why it matters to LILITH

An approval for action A that can be replayed for B, or that survives a
silent change of parameters, is not an approval. For memory, it means the
owner approves X while Y is stored.

## Original hypothesis / problem

Canonical serialization plus proposal fingerprint, conditions, approver, and
execution-time equality checks.

## Architecture explored

The same principle applied four times, each tighter:

1. **Internal write approval** (Slice 4): the draft is frozen and
   fingerprinted before approval; approve re-checks fingerprint and expiry;
   changed content requires re-approval; idempotency key per step.
2. **Consent** (15B2a): immutable consent bound separately to payload,
   purpose, operation, and actor; revision and restore drift rejected;
   policy decision computed, never caller-declared.
3. **Owner proof** ([B1a](../../architecture/slice-15b2b-b1a-owner-proof-contracts.md)):
   WebAuthn challenge bytes = SHA-256(domain separator ‖ RFC 8785 canonical
   JSON) binding action, request, and payload digests; ≤60 s; durable
   challenge state is the replay authority; expiry re-sampled under lock after
   cryptography.
4. **Acceptance** ([B2a](../../architecture/slice-15b2b-b2a-accepted-memory-verifier.md)):
   V2 challenge adds logical authority context; broker evidence envelope
   (Ed25519) binds nonce = `challengeId`, digests, and the owner-proof
   reference; the verifier re-checks the whole chain.

## Experiments / implementation slices

Slice 4 W-A…W-P (REPORTED counts; stale-fingerprint re-approval, duplicate
approve dedupe); 15B2a M–Y; B1a golden vectors; B1b-1 request golden vector;
B2a 89-case tamper matrix.

## Evidence

- OPERATIONAL (pre-DEV live): approval card showed exact target, content,
  side effect, reversibility; zero drafts before approval; one after; read-back
  verified (Slice 4, REPORTED).
- TEST: every signed field mutated after signing is rejected (B2a); modified
  request, wrong actor, wrong action, expired evidence, replay all rejected
  (15B2a D–I); changing `requestDigest` changes both canonical bytes and the
  WebAuthn challenge (B1a).

## Negative findings / failures

- B1a needed a follow-up commit to bind the request digest and consume-time
  expiry (`bcdfbbb`).
- No external action has ever been approved; all evidence is internal writes
  or synthetic owner proofs.
- No real owner credential, RP domain, or enrollment exists.
- N-35: evidence issuance keys are still readable by the application user.

## Current answer

- **PROVEN (pre-DEV live for internal drafts; TEST for owner proofs):**
  canonical serialization plus digest binding plus durable single-use state
  prevents substitution, replay, and silent parameter drift in every tested
  case.
- **DESIGNED:** logical-context V2 challenges; separate owner key for memory
  and for activation.
- **INFERRED:** current evidence supports this as the most mature answer in
  the research portfolio, scoped to internal writes and synthetic owner
  proofs.
- **UNKNOWN:** external actions; human factors of the approval UI; the real
  enrollment and recovery ceremony.

## Confidence / maturity

High within scope (proposed maturity IMPLEMENTED, scoped). Not validated with
real users or external effects.

## What remains unanswered

Encoding-ambiguity attacks on real clients; approval validity under changing
external reality (RQ-029); real owner enrollment, revocation, recovery.

## Related RQs

RQ-029, RQ-026, RQ-033, RQ-048.

## Related slices

4, 5, 15B2a, B1a, B1b-1, 15B2b-B design, B2a.

## Publication notes

Mature for a **security case study** and possibly a future **academic paper**
section on digest-bound owner authorization for agent memory, provided claims
stay within synthetic scope.
