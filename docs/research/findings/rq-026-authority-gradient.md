# REPO:RQ-026 — Authority gradient, risk, and the ethics boundary

> **Namespace (primary-source pass, 2026-09-26).** This finding is filed
> under **REPO:RQ-026** (in-repo register). MASTER equivalent: MASTER:RQ-019 (SEMANTIC MATCH); MASTER:RQ-108 PARTIAL OVERLAP; related MASTER:RQ-020, 024, 025, 018.
> See the [crosswalk](../rq-register-crosswalk.md).
>
> **Primary-source evidence added:**
> - S4 (2026-08-24) approval classes AUTO / PREVIEW / APPROVE, capability tokens, kill switch, and "autonomy expands by policy, never by ambiguity".
> - MASTER:RQ-019 proposes base levels R0–R5 plus contextual factors; MASTER:RQ-108 adds "confidence or affection must never expand delegated authority".
> - PRIVATE HISTORICAL SOURCE S3 — Infrastructure, CI/CD & Operations v1.0 — SHA-256 `ff7ed4dadb5ecd06c47e0a9ee87b6690fb810e34cd71dfae44e9d142c92caf90` (2026-09-14) records the single deployer identity with OS Admin Login on both VMs (the same role set is public in the B1c acceptance record) — the tier collapse B1c later split for DEV.

## Research question

How should contextual action risk be calculated? (In-repo RQ-026; related
RQ-027 friction reduction, RQ-030 urgency, RQ-031 predelegation, RQ-032
nondelegable actions. Master topics: permission gradient; preference/policy
separation.)

## Why it matters to LILITH

Every capability LILITH gains needs a place on a gradient from "just do it"
to "never". If the gradient is decided by the model, or relaxed by learning,
autonomy grows without anyone deciding it should.

## Original hypothesis / problem

Effective risk combines intrinsic class, environment, blast radius, timing,
reversibility, uncertainty, system health, and policy.

## Architecture explored

The project built a **static, layered authority gradient**, not a contextual
risk score:

| Tier | Mechanism | Where |
| --- | --- | --- |
| READ | no approval | Slice 5 |
| INTERNAL_WRITE | explicit approval, exact preview, read-back, TTL 15 min | Slices 4–5 |
| EXTERNAL_WRITE / DESTRUCTIVE | stricter TTL, no silent retry (defined, unused) | Slice 5 |
| PROHIBITED | never allowed regardless of planner output (`mail.send_email`) | Slice 5 |
| Canonical memory mutation | per-action owner WebAuthn proof, ≤60 s | B1a, 15B2b-B design |
| Capability activation | owner-signed grant verified by an isolated verifier | B1c-1A |
| Routine deployment | fixed helper, no root, cannot activate | B1c |

Separately, **ethics deliberates but never governs**
([Slice 13](../../architecture/slice-13-ethical-deliberation-design.md)):
four fixed principles, advisory outcomes, no ALLOW/DENY vocabulary; CA-V1 §11
formula lets ethics subtract but never add permission.

## Experiments / implementation slices

Slice 5 60/60 and probes; Slice 13 54/54 and acceptance A–G; B1c 28 denials;
activation `NOT_ACCEPTED` in every observation.

## Evidence

- OPERATIONAL (pre-DEV live): prohibited-capability probe blocked before
  execution (Slice 5, REPORTED); ethics returned
  `SKIPPED_KNOWN_PROHIBITION` for a recruiter email, labelled
  `authoritativePolicyEvaluation=false`, and `HUMAN_REVIEW_RECOMMENDED` for
  an irreversible delete (Slice 13).
- DEV: routine deployer denied generic root, broker, owner socket, Stage III,
  activation paths (B1c run 36179649106).

## Negative findings / failures

- No contextual factors (timing, blast radius, system health) are computed.
- The ethics "subtract" gate is deferred: there is no live executor on the
  Router path for it to restrain.
- Static policy mirrors used by Slices 12–13 can drift from the authoritative
  registry.
- The legacy PROD deployer remains root-capable across environments (N-33).

## Current answer

- **PROVEN (pre-DEV live, DEV):** a static class-based gradient with a
  non-negotiable prohibition tier, and separate authority mechanisms for
  memory mutation, activation, and deployment, can be enforced outside the
  model.
- **DESIGNED:** ethics as advisory and subordinate to policy; learning may
  propose but never lower restrictions (no path exists).
- **INFERRED:** current evidence supports *separate keys and verifiers per
  authority tier* ("compromising one never yields the other") as the
  project's actual answer so far, rather than a numeric risk function.
- **UNKNOWN:** contextual risk; safe predelegation (RQ-031); emergency
  behaviour (RQ-030).

## Confidence / maturity

Medium for the static gradient; none for contextual risk.

## What remains unanswered

A labelled scenario set for contextual risk; a values review for
nondelegable actions (RQ-032); predelegation envelopes.

## Related RQs

RQ-027, RQ-030, RQ-031, RQ-032, RQ-028, RQ-048.

## Related slices

4, 5, 12, 13, B1a, B1c, 15B2b-B design.

## Publication notes

Mature for a **security case study** ("one authority mechanism per tier").
Avoid implying a contextual risk engine exists.
