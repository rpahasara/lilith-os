# REPO:RQ-047 — Prompt injection, secrets, and deployer authority

> **Namespace (primary-source pass, 2026-09-26).** This finding is filed
> under **REPO:RQ-047** (in-repo register). MASTER equivalent: MASTER:RQ-035 and MASTER:RQ-037 PARTIAL OVERLAP (injection); MASTER:RQ-038 relates to REPO:RQ-048 (secrets, SEMANTIC MATCH); related MASTER:RQ-036.
> See the [crosswalk](../rq-register-crosswalk.md).
>
> **Primary-source evidence added:**
> - S4 (2026-08-24): "Secrets vault — credentials never enter prompts or app state"; sandboxes; capability tokens.
> - PRIVATE HISTORICAL SOURCE S3 — Infrastructure, CI/CD & Operations v1.0 — SHA-256 `ff7ed4dadb5ecd06c47e0a9ee87b6690fb810e34cd71dfae44e9d142c92caf90` (2026-09-14) records OIDC/WIF with no long-lived JSON keys, and the single deployer identity with OS Admin Login on both VMs; it lists "Dedicated DEV/PROD deploy identities" and a secrets broker as targets. B1c (2026-09-25) realized the DEV half.

## Research question

How resilient is policy to direct and indirect prompt injection? (In-repo
RQ-047; related RQ-046 observability without leaking and RQ-048 secret
isolation.)

## Why it matters to LILITH

LILITH reads untrusted content (email-derived career events, chat). If that
content can steer tools, or if any automated identity can reach secrets and
root, then policy is only as strong as its weakest runtime.

## Original hypothesis / problem

Untrusted content remains data, capabilities are least-privileged, and policy
is enforced outside model instructions (RQ-047); capabilities use scoped
credential handles and raw secrets never enter model context (RQ-048).

## Architecture explored

- **Policy outside the model** (Slice 5): prohibition checked before execution
  regardless of planner output.
- **Tool-less model components** (Slices 9, 12, 13): `enabled_toolsets=[]`,
  zero tool schemas, symbol-absence tests.
- **Grounded answers** (7.2, REPORTED): the model answers from reconciled
  state instead of exploring raw stores.
- **Minimal traces** (Slices 14, 15A): no raw input or payload in traces.
- **Deployer authority cut** ([B1c](../../architecture/slice-15b2b-b1c-acceptance-record.md)):
  a DEV-only identity, a fixed root-owned helper, no general sudo, denial
  proofs every run, activation owner-signed and verified outside the app.
- **Custody isolation** (B1b-3, named gate, not started): move Actor,
  Privacy, and containment issuance keys out of the application user.

## Experiments / implementation slices

Slice 5 probes; Slice 9 no-tool proof; Slice 14 trace safety; B1c run
36179649106 and owner gates.

## Evidence

- OPERATIONAL (pre-DEV live): the reasoning agent had zero tools,
  toolsets, and schemas (Slice 9 no-tool proof).
- DEV: 28 denials, zero unexpected allows; the DEV identity cannot mint the
  legacy privileged identity or obtain useful PROD permissions through the
  tested paths (B1c).
- OBSERVED design: private owner credential stays off-host; synthetic test
  scalar never enters release, marker, config, or state (B1a, B1b-2b).

## Negative findings / failures

- N-35: Actor, Privacy, and containment keys are `lilith:lilith 0600`; a
  compromised application user can mint owner-looking evidence.
- N-33: the legacy PROD deployer retains project-wide `osAdminLogin`, can
  reach DEV as root, and is exercised automatically by `deploy.yml`. Level 2
  isolation is **not** claimed.
- No adversarial injection corpus has been run.
- N-32: broker install, recovery, and forensics now require owner
  break-glass — a deliberate availability cost.

## Current answer

- **PROVEN (pre-DEV live, DEV):** model components can be structurally
  unable to call tools; routine deployment can be denied root, broker,
  owner-socket, Stage III, and activation authority.
- **DESIGNED:** key custody outside the application; per-environment keys and
  credentials.
- **INFERRED:** current evidence supports defence by *structural absence of
  capability* rather than by detecting injected instructions.
- **UNKNOWN:** resistance to indirect injection through connector content
  once write connectors exist; complete root isolation of the memory host.

## Confidence / maturity

Medium for structural controls; the custody and cross-environment gaps are
known and open.

## What remains unanswered

Adversarial connector-content cases; B1b-3 custody isolation; retiring the
cross-environment PROD authority (B1d, undefined); canary-secret tests.

## Related RQs

RQ-046, RQ-048, RQ-026, RQ-015.

## Related slices

5, 7.2, 9, 12, 13, 14, 15A, B1a, B1b-2b, B1c, 15B2b-B design.

## Publication notes

The B1c story ("removing root from routine deployment and proving the denials
on every run") is mature for a **security case study**, provided the open
cross-environment debt is stated plainly.
