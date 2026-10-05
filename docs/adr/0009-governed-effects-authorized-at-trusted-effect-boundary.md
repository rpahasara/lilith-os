# ADR-0009: Governed effects are authorized at a non-bypassable trusted effect boundary

- **Status:** Accepted
- **Date:** 2026-10-05
- **Owners:** Project maintainers
- **Related:** ADR-0001, ADR-0002, ADR-0003, ADR-0004, ADR-0006, ADR-0007;
  ledger D-2, G2, G1 (separation only), ACT-01, ACT-03, ACT-04, ACT-06, C-02,
  GOAL-04, GOAL-05, INIT-05, COMP-H, R1, R8; principles P-03, P-09;
  threat-model invariants #2, #3, #6, #8; threats T-02, T-21;
  `docs/security/trust-boundaries.md`

## Context

ADR-0004 decides that clients cannot directly execute governed capabilities.
It says governed execution passes through the LILITH control plane, including
policy evaluation and approval where required. It rejects client-side policy
checks as "insufficient as an authorization boundary because clients can be
modified or stale", and it places clients "outside the principal authorization
boundary". It does not say what makes a boundary authoritative, where that
boundary sits for a given effect, or what approval must be bound to. It also
covers clients only. It does not address runtimes, internal services or other
callers.

The [Current Architecture & Acceptance Ledger v0.1](../architecture/current-architecture-acceptance-ledger-v0.1.md)
records the result as audit finding **G2** (§7.2), conflict **C-02** and row
**ACT-01**. Decision **D-2** asks where the authoritative policy and approval
boundary sits under ADR-0004.

Repository evidence at `ff393cb` (static reading only; no route was called, no
exploit attempted, no live system contacted):

- **REPO CODE.** Policy evaluation, approval TTL, the approval fingerprint
  freeze, connector gating and read-back verification run in `RealCommandCore`
  (`src/lib/command/core/real-core.ts`, `::onApprove`, `::runSteps`,
  `::gateConnector`). It is instantiated in a `"use client"` provider
  (`src/components/command/command-provider.tsx:1`, `:101`, `:130`).
- **REPO CODE.** `POST /os/drafts` (`services/core-api/app.py::create_draft`)
  validates shape, size, schema version, IDs and kind, dedupes on the
  idempotency key, and inserts. It checks no approval, actor or owner evidence.
  `taskId` and `stepId` are caller-supplied fields. The section header calls
  this an "approval-gated internal write", but the gate is not in the handler.
- **REPO CODE.** `DELETE /os/drafts/{id}` (`::discard_draft`) soft-discards
  with no approval or actor check.
- **REPO CODE.** `POST /os/tasks` and `PATCH /os/tasks/{id}` accept a full
  task record. `_validate_record` checks that `approvalState` is one of
  `not_required | required | approved | denied | expired`. It does not check who
  set it. A caller can therefore persist `approvalState: "approved"` in the
  canonical task record.
- **REPO CODE.** `POST /os/goals`, `POST /os/goals/{id}/transition` and
  `POST /os/goals/{id}/link_task` mutate goal state with no authorization
  dependency. The original ledger §7.2 inventory listed only the first two;
  the same change that proposes this ADR adds `link_task` to it.
- **REPO CODE.** `app.py` contains no FastAPI `Depends`, auth header, API key or
  middleware check on any of these routes. The handlers contain no local policy
  or approval boundary.
- **REPO CODE.** The Next.js route handlers `src/app/api/lilith/drafts/route.ts`
  (`POST`), `drafts/[draftId]/route.ts` (`DELETE`), `tasks/route.ts` (`POST`)
  and `tasks/[taskId]/route.ts` (`PATCH`) forward the request body to the
  backend with no policy or approval check. The generic `[...path]` proxy is
  GET-only with an allow-list. No goal-write proxy exists in `src/`.
- **REPO RECORD (HISTORICAL).** The Slice 8 goal lane posts to `POST /os/goals`
  from the host (`docs/architecture/slice-8/world_context.goal-block.py`). The
  Slice 12 and 13 designs say the authoritative policy engine lives "only in
  the frontend `RealCommandCore`", and the Router path has none.
- **REPO RECORD.** Runtime agent tools are not gated by a LILITH enforcement
  boundary in the repository (ACT-03). Their live state is UNKNOWN.
- **UNKNOWN.** Network exposure, topology, authentication and any external
  enforcement in front of the Next.js app and the backend are not established
  in the repository (ledger §10.3). Nothing here says whether any route is
  reachable by an untrusted caller in any deployment, or whether some other
  boundary sits in front of it.

Precedent for a conforming shape exists in accepted architecture. ADR-0006's
L04 "independently resolves every authority and precondition", and "callers and
model payloads cannot activate these controls". The owner-proof design binds an
owner proof to an unchanged frozen-action digest built by the broker, not by the
client (T-21). Canonical memory remains dark (ADR-0006), so this is design and
test precedent, not live evidence.

Without a decision, the boundary gets placed by convenience. A route behind a
proxy looks protected. A browser that is honest looks like authority. A record
field named `approvalState` looks like approval.

## Decision

LILITH adopts the following rule for governed effects:

> Authoritative policy and approval enforcement for a governed effect happens
> at a trusted boundary that controls whether the effect can occur. That
> boundary is defined by its control of the effect, not by its location, its
> name, or the honesty of the caller.

### Definitions

- **Effect.** A state transition in LILITH canonical or durable state (ADR-0002)
  or an external side effect produced by a capability.
- **Governed effect.** An effect that an accepted policy, or an accepted action
  or domain contract, places under authorization governance. In particular:
  - every governed capability under ADR-0004 is a governed effect;
  - a canonical-state write is a governed effect where its accepted contract
    requires action authorization. A write is not governed by this ADR merely
    because ADR-0002 assigns its state a canonical authority.

  Where a write targets a canonical domain, the destination domain's acceptance
  under ADR-0007 remains independently required where applicable. Semantic
  ownership or acceptance does not itself grant action permission (ADR-0007
  OD-10). Which existing routes produce governed effects, and under which
  policy class, is conformance work (R1). This ADR does not classify routes.
- **Requester.** The party that submits a request for an effect: a UI, a
  client, a model-driven lane, a runtime, a tool adapter, an internal service
  or a person.
- **Policy evaluation.** Deciding which requirements apply to a requested
  effect, such as permitted without interactive approval, approval required,
  stronger approval required, or prohibited.
- **Approver.** A principal whom accepted policy recognizes as able to approve
  that effect. An approver acts only where policy requires approval.
- **Approval evidence.** Evidence that a recognized approval authority or
  approver approved an exact effect, or an explicitly bounded scope, under an
  accepted policy or contract. A bounded scope may include an explicitly
  accepted cardinality or reuse model. Approval evidence may be transient,
  portable or persisted. It is input to authorization. It is not
  authorization.
- **Authoritative enforcement boundary.** The component that, for a given
  effect, establishes from trusted state whether the applicable policy
  requirements are met, and permits or refuses the effect on that basis.
- **Executor / applier.** The mechanism that performs the effect once it is
  authorized.
- **Verifier.** The component that independently checks the effect where
  ADR-0003 requires it.

These are semantic roles. One process may host several of them (see
"Executor separation"). No role requires its own service.

### Core rules

- **EB-1.** Every governed effect has an authoritative enforcement boundary on
  the trusted side of that effect. Other checks may exist in front of it. They
  do not replace it.
- **EB-2.** A boundary is authoritative for an effect only if all of the
  following hold:
  - it mediates the effect;
  - the effect cannot validly occur through an ungoverned path that bypasses
    the authoritative enforcement required by accepted policy or contract;
  - it evaluates, or consumes from a trusted source, the policy decision for
    the exact request;
  - where policy requires approval, it establishes valid approval evidence
    bound to the exact requested effect, or to an explicitly bounded scope
    that contains it (EB-7);
  - it refuses absent, invalid, mismatched, expired, out-of-scope or
    insufficient authorization;
  - no caller can make itself authoritative by changing client, UI, request or
    record state.

  Being a server, backend, gateway, proxy or "policy service" does not make a
  component authoritative. A component whose required enforcement can be
  bypassed through an ungoverned path, or that only logs or forwards, is not
  authoritative.
- **EB-3.** A client or UI may capture intent, show previews, run local policy
  checks, warn, explain, reject early, collect approval and package approval
  evidence. These checks are permitted as UX and defense in depth. Where the
  client can be bypassed or modified independently of the effect, its checks
  are not sufficient authority. Their absence or failure must not make a
  governed effect bypassable.
- **EB-4.** The boundary enforces the policy outcome that accepted policy
  assigns. That outcome may be "permitted without interactive approval",
  "approval required", "stronger approval or review required", or "prohibited".
  This ADR does not require human approval for every effect. A permitted
  effect still passes the boundary, which checks that the request is within
  what policy permits. A prohibited effect is refused regardless of any
  approval evidence.
- **EB-5.** Where policy requires approval, the boundary establishes, before
  the effect, that valid approval evidence exists for that exact effect, or
  for an explicitly bounded scope under accepted policy or contract that
  contains it. A caller's assertion is not approval evidence. That includes a request field
  such as `approved: true`, a client-computed "allowed" decision, or a
  caller-written approval state in a record. Such an assertion counts only if
  the boundary independently establishes that it was produced by a recognized
  approver for this effect under the accepted contract.
- **EB-6.** Approval is not execution. Approval evidence does not prove that
  execution was authorized correctly, that it occurred, or that it achieved
  its goal. Policy evaluation and authorization are also distinct steps. An
  evaluation is an input. The authorization is the boundary's decision for one
  bound request.
- **EB-7.** Approval is bound to the effect it approves. Approval for effect A
  is not approval for effect B, unless accepted policy explicitly places B
  inside A's approved scope. A material change to the bound dimensions
  invalidates the approval (P-03). See "Effect binding".
- **EB-8.** Requesting, proposing, transporting, rendering or performing an
  effect grants no approval authority. Where accepted policy requires
  independent approval, the requester, proposer or executor of that effect
  cannot satisfy the requirement through its own assertion or decision. That
  applies to a model, prompt, runtime, tool adapter, caller, executor, Hermes
  and Hsin alike. This ADR grants no bounded autonomous approval authority to
  any component. A later accepted policy or design may define bounded
  authority. None is created here.
- **EB-9.** Direct calls, alternate routes, proxies, internal callers on the
  same host, and routes not exposed in any UI must not bypass a required
  policy or approval check. Every path that can produce a governed effect is
  either mediated by an accepted authoritative boundary or refused. There must
  be no ungoverned bypass path to a governed effect. An alternate path, such as
  a separately accepted recovery, administrative or emergency path, is
  compatible with this ADR only if it has its own accepted authoritative
  governance appropriate to the effect and cannot be used as an ungoverned
  route around the normal boundary. More than one accepted, governed path for
  the same class of effect is not a bypass merely because more than one path
  exists. This ADR designs no such alternate path.
- **EB-10.** An authorization covers the exact effect, or the explicitly
  bounded scope, to which it is bound under the accepted policy or contract,
  and nothing more. Retry, replay, repeated submission or
  reuse of an authorization or operation identity must not:
  - widen the authorization;
  - exceed its accepted scope or cardinality;
  - create an unintended duplicate effect;
  - create a materially different effect.

  Where accepted policy explicitly grants bounded multi-use authorization, that
  explicit scope and cardinality control. Deduplication and idempotency
  mechanics remain governed by ADR-0002, ADR-0003 and P-06. This ADR does not
  define them.
- **EB-11.** If the boundary cannot establish the conditions that policy
  requires, it refuses the effect. Unavailable policy state, unavailable
  approval state, or an unknown authorization outcome is never read as
  permitted (P-05; ADR-0007 "Failure and default-deny").
- **EB-12.** Authorization establishes only that a specific effect may proceed.
  It does not establish semantic ownership, truth, verification, freshness,
  currentness or successful execution. Semantic ownership does not establish
  authorization (ADR-0007 OD-10).
- **EB-13.** Accepting this ADR creates a conformance rule. It does not
  establish that any existing route, client, runtime or deployment conforms.

### Authoritative enforcement boundary

For a server-backed effect, the authoritative boundary is normally a component
on the server side that sits in front of the mutation and that every write
path must pass. Placing it in a proxy only satisfies EB-2 if the protected
store or service cannot be reached except through that proxy. That property
must be shown, not assumed.

In the current repository the backend handlers contain no local policy or
approval check (Context), so no handler is itself an authoritative
enforcement boundary. The repository does not establish that the backend is
reachable only through the Next.js route handlers, so a Next.js-only boundary
cannot be accepted as authoritative without topology and bypass evidence.
Repository evidence does not establish system-level conformance or
non-conformance either. A route's effect would be non-conforming if that route
can produce the governed effect without passing another accepted, unavoidable
authoritative boundary.

The boundary may sit in the same process as the store or the executor, provided
its decision is distinct and the effect cannot occur without it (OD-11 pattern).

### Client and UI role

The client role stays as ADR-0004 states it: capture intent and present semantic
state. Under this ADR a client may also:

- run the same policy evaluation locally to preview, warn or reject early;
- show the exact preview that approval will be bound to;
- collect the approver's decision and package it as approval evidence;
- submit the governed request with that evidence.

None of these makes the client authoritative. Defense-in-depth checks in the
client remain useful. They must stay consistent with the authoritative decision
and must not be relied on in its place.

### Approval semantics

- A user pressing "Approve" produces approval evidence, an expression of
  intent. It does not by itself authorize execution. The boundary validates
  that evidence against the exact governed request and its policy context.
- The approver must be a principal that policy recognizes. This ADR does not
  define principal authentication. Authentication identifies the principal.
  It does not by itself authorize any effect.
- Approval evidence may be transient, portable or persisted. Whatever its
  form, the boundary must independently establish:
  - its authenticity and provenance;
  - its binding to the exact requested effect, or to an explicitly bounded
    scope that contains that effect (see "Effect binding");
  - its scope;
  - its validity;
  - where the accepted policy or contract requires them, its permitted reuse
    or replay semantics, its cardinality or consumption semantics, and any
    applicable freshness or expiry constraints;
  - any other condition that policy requires.

  This ADR does not require every authorization to be single-use or to
  expire. Those are policy and contract questions. EB-10 is the conformance
  rule for replay, retry and reuse.
- A client's own assertion, or state whose claimed authority or provenance
  derives only from the client's write, is not sufficient by itself (EB-5).
- Evidence may pass through, or be held by, an untrusted client, provided the
  boundary can independently verify it under an accepted contract. Where it
  is held matters less than whether the boundary can verify it.
- If an approval record is persisted as governed state, its canonical
  authority and mutation rules follow ADR-0002 and, where applicable,
  ADR-0007.
- This ADR does not require an approval ledger or a retention period.
- The boundary's authorization outcome for a governed effect is
  security-relevant and must be attributable to the request it decided
  (ADR-0002 "auditable provenance"; threat-model invariant #8). This ADR does
  not define a format or store for it.
- An approval must not be usable beyond its bound scope and cardinality
  (EB-10). Whether a given capability's approval is single-use or bounded
  multi-use is policy. Without an explicit policy grant, using the same
  approval for a second distinct effect is not allowed (T-02).

### Effect binding

The binding must be strong enough that approval for one effect cannot be
silently reused for a materially different one. Drawing on P-03,
`component-boundaries.md` (Approval service: "fingerprinted proposal, approver,
scope, expiry, decision") and T-02, the binding covers at minimum the
dimensions that make the effect what it is:

- the operation or capability;
- the target resource;
- the meaningful parameters or content, as the approver saw them in the
  preview;
- the approver, and the requester or actor where policy depends on it;
- the approved scope;
- the policy class or context under which approval was given;
- expiry, and precondition or state binding (for example expected revision),
  where policy requires them.

This ADR decides the invariant, not the representation. A typed request, a
canonical digest, a structured effect description or another accepted form may
satisfy it later. Representation, canonicalization and any cryptography are
implementation decisions. The existing browser `fingerprintDraft` digest is an
example of a binding computed on the wrong side of the boundary. It may be
reused as a binding representation only if the boundary computes or verifies
it independently.

### Policy outcomes

The browser policy engine's vocabulary (`PolicyClass`: `READ`,
`INTERNAL_WRITE`, `EXTERNAL_WRITE`, `DESTRUCTIVE`, `PROHIBITED`;
`ApprovalMode`: `none`, `explicit`, `elevated`) maps onto EB-4's outcomes. This
ADR neither accepts nor rejects that vocabulary and does not define a policy
language. It requires only that whichever accepted policy applies is enforced
at the authoritative boundary, not only in the client.

### Executor separation

Authorization and execution are distinct roles, as execution and verification
are under ADR-0003. One process may host the boundary, the executor and the
verifier, provided:

- the boundary's decision is made before, and independently of, the
  executor's attempt;
- the executor cannot produce or upgrade its own authorization;
- the verifier does not treat the executor's report or the authorization as
  proof the effect matched its goal.

### Model, runtime and Hsin boundary

- **Models** produce proposals and recommendations. Model output, confidence or
  a planner step is not approval evidence or permission merely because a model
  produced it (threat-model invariant #2).
- **Hermes and other runtimes** orchestrate. They may submit governed requests.
  They do not become approval authorities, and runtime orchestration is not
  permission. The same rule applies to runtime-held tools. Inventorying those
  tools remains R5 and ACT-03.
- **Hsin, voice and other presence surfaces** carry intent and may carry
  approval evidence. A future authenticated owner approval through Hsin could
  produce approval evidence for a boundary to validate. Hsin does not become an
  authority by carrying it. This ADR does not design Hsin authentication.

### Server-backed and trusted-local cases

The rule is about control of the effect, not about cloud infrastructure:

| Requesting surface | Authoritative boundary |
| --- | --- |
| Browser | Server-side component that controls the backend mutation |
| Mobile or ambient UI | Trusted local service or server-side component that controls the effect |
| Hermes or another runtime | LILITH trusted action boundary in front of the effect |
| Hsin | LILITH trusted action boundary in front of the effect |

For a protected local effect, the same invariant holds. The requesting surface
must not be able to bypass the boundary that controls the effect. This ADR does
not define any local or offline authority boundary. A trusted-local effect
needs a later accepted design or decision appropriate to that effect. ADR-0004
lists "Platform constraints require a local operation and an ADR defines its
authority boundary" and "A formally scoped offline capability model is
accepted" among its revisit triggers. It also notes that "Local/offline
features require carefully defined exceptions". The ADR README's "When an ADR
is required" guidance may also apply where such a design changes trust
boundaries or authority.

### Historical wording disposition

The Slice 9, 12 and 13 design records describe the browser `RealCommandCore` as
"authoritative" or say the "approval-gated draft path stays authoritative".
These are repository records of their date (rank 3). They contrast the browser
core with the static, non-authoritative policy mirror on the Router path. Under
this ADR, once accepted, the browser core is not an authoritative enforcement
boundary for any server-backed effect (EB-2, EB-3). The records are not
rewritten. They remain accurate history of what was built.

### Non-goals

This ADR does **not**:

- implement server-side authorization, or change any code, route, proxy or
  test;
- change `RealCommandCore`, `/os/drafts`, `/os/tasks` or `/os/goals`;
- classify existing routes into policy classes;
- close G2 or G1;
- define a policy language, a principal authentication scheme, an approval
  token format, or approval cryptography;
- require human approval for every effect;
- create capability grants or bounded autonomous authority;
- change semantic ownership (ADR-0007) or personality ownership (ADR-0008);
- accept any of the 16 proposed PDFs;
- change Hermes, Hsin or model routing;
- establish any current live, deployment, authority or freshness state;
- authorize B-5, M-B1, PR-1B, First Memory, deployment or any authority or
  witness transition.

## Compatibility with accepted ADRs

| ADR | Relationship | Result |
| --- | --- | --- |
| ADR-0001 | LILITH retains "final authority for governed state transitions" above runtimes. EB-8 applies this to approval. | Agrees |
| ADR-0002 | Where approval or policy records are persisted as governed state, they have a canonical authority and follow ADR-0002's mutation rules. Caches are not silently authoritative, so client-held state is never authority by itself. This ADR does not require approval evidence to be persisted. It requires the boundary to verify evidence independently, wherever the evidence is held ("Approval semantics"). | Agrees; consistent |
| ADR-0003 | Execution is not verification. EB-6 and "Executor separation" add that authorization is neither. The co-location rule is the same. | Agrees; parallel |
| ADR-0004 | See below. | Instantiates and clarifies; supplements for non-client callers. No conflict |
| ADR-0005 | Deployment delivers source. It is not an action authority. The deployment workflow "owns source delivery only" (ADR-0005), and deployment ≠ activation: deploying, installing, or making a component or boundary present or reachable does not by itself activate any authority or make that component an authoritative boundary for any effect. | No interaction |
| ADR-0006 | L04 independently resolves every authority and precondition; callers and model payloads cannot activate controls. That is a conforming boundary under EB-2 for canonical memory apply. | Agrees; reference case (design and test; memory remains dark) |
| ADR-0007 | See below. | Orthogonal; complementary |
| ADR-0008 | Personality ownership grants no action permission (PERS-11). | Agrees; no interaction |

### Relationship to ADR-0004

ADR-0004 states:

- the decision: "Governed capability execution must pass through the LILITH
  control plane, including canonical task creation, policy evaluation, approval
  where required, runtime delegation, and verification";
- the rejected alternative: "Client-side policy checks: useful for early
  feedback but insufficient as an authorization boundary because clients can be
  modified or stale";
- a consequence: "Approval and state transitions cannot be skipped by UI code";
- the trust statement: "Clients are outside the principal authorization
  boundary";
- the validation: "approval-required actions cannot execute through alternate
  endpoints" and "forged client state and replayed approvals".

This ADR:

- **instantiates** ADR-0004 by stating what makes a boundary authoritative
  (EB-2) and that approval is effect-bound (EB-7);
- **clarifies** that a client may still run policy checks for UX and defense in
  depth (EB-3), which ADR-0004 calls "useful for early feedback";
- **supplements** ADR-0004 by applying the same rule to non-client callers
  (runtimes, internal services, model lanes) and to governed canonical-state
  writes, not only to capability execution.

Nothing in ADR-0004's accepted wording conflicts with this ADR. ADR-0004 is not
amended or superseded. Its revisit triggers on local and offline operations
are unchanged.

### Relationship to ADR-0007

ADR-0007 decides who owns a domain's meaning and accepts its transitions. This
ADR decides whether a requested effect may proceed. They are separate
questions:

```text
semantic owner (ADR-0007)  ≠  authorization boundary (this ADR)  ≠  executor
```

A goal write, for example, needs both: the goal domain's acceptance (OD-5) and
the action-policy authorization that applies to it. Neither substitutes for the
other. Goal-domain ownership does not make every goal writer authorized (OD-10,
EB-12). Passing authorization does not make the caller a goal-domain acceptor.

Physical co-location of owner, boundary and executor is permitted (OD-11). To
avoid circular authority (OD-8), the authorization for an effect must not
depend on state that the same request writes. A task record whose
`approvalState` the requester itself sets cannot serve as approval evidence for
that requester's effect.

ADR-0007 already records the `/os/drafts` approval bypass as an ADR-0004
defect outside its scope. This ADR is where that defect is measured.

## G1 and G2 separation

- **G2** (ledger §7.2, ACT-01, C-02) is the absence of an authoritative
  boundary for governed writes. This ADR provides the yardstick. G2 stays
  **OPEN**. It can close only after the relevant routes are inventoried,
  classified, hardened and tested against EB-1 to EB-11. Fixing the drafts
  routes alone does not close it.
- **G1** (ledger §7.1, ACT-02, C-03) is a policy-composition defect: capability
  overrides can weaken class defaults. This ADR does not resolve it. An
  authoritative boundary that consumed a non-monotonic policy would enforce the
  wrong policy faithfully. G1 stays **OPEN** under R2.

## Existing repository evidence

Classification is limited to what the repository proves. For each backend
handler, the repository shows only that the handler itself is not an
authoritative enforcement boundary. Repository evidence does not establish
system-level conformance. The effect would be non-conforming if this route can
produce the governed effect without passing another accepted, unavoidable
authoritative boundary. Nothing here says a route is reachable, exploited or
deployed. Whether each effect is governed at all is R1 classification.

| Path | Effect | Evidence | What the repository proves | Under this ADR |
| --- | --- | --- | --- | --- |
| `RealCommandCore` (browser) | Policy, approval, fingerprint, verification for Command Center | REPO CODE | Runs client-side (`"use client"`) | Permitted as UX and defense in depth (EB-3); not authoritative |
| `POST /os/drafts` | Create draft record | REPO CODE | No local approval, actor or owner check | Handler is not an authoritative boundary. If governed, the effect is non-conforming unless another accepted, unavoidable boundary mediates it (EB-2, EB-5, EB-9). System-level conformance: NOT ESTABLISHED |
| `DELETE /os/drafts/{id}` | Soft-discard draft | REPO CODE | No local approval or actor check | Same |
| `POST /os/tasks` | Create canonical task | REPO CODE | No local auth; caller-set `approvalState` stored after enum check | Same; caller-set approval state is not evidence (EB-5) |
| `PATCH /os/tasks/{id}` | Update canonical task | REPO CODE | Same as above; expected revision checked only if supplied | Same |
| `POST /os/goals` | Create goal | REPO CODE | No local auth; caller-asserted `source` | Same; also GOAL-04 under ADR-0007 |
| `POST /os/goals/{id}/transition` | Goal FSM transition | REPO CODE | No local auth | Same |
| `POST /os/goals/{id}/link_task` | Link task to goal | REPO CODE | No local auth | Same; missing from the original ledger §7.2 inventory, now corrected |
| Next.js `drafts`, `tasks` route handlers | Forward writes | REPO CODE | Body forwarded verbatim, no check | Not a boundary as written. The repository does not establish that the backend is reachable only through these handlers, so a Next.js-only boundary cannot be accepted as authoritative without topology and bypass evidence |
| Slice 8 goal lane → `POST /os/goals` | Create goal from utterance | REPO RECORD (HISTORICAL) | Host-side caller of the goal API | Internal callers are covered by EB-9; currentness UNKNOWN |
| Runtime agent tools | Tool effects on host | REPO RECORD | Ungated in repository (ACT-03) | Covered by EB-8 and EB-9; inventory is R5 |
| `POST /os/conversation` | Forwards a message to the Hermes platform plugin | REPO CODE | Uses a server-held token toward Hermes | Not itself a canonical write; effects of the resulting turn fall under the runtime row |
| L04 canonical memory apply | Canonical memory revision | ACCEPTED ADR (0006), LOCAL TEST | Server-side independent resolution of authority | Reference shape for EB-2; memory dark |

## Alternatives considered

### The browser core stays the authoritative boundary

This is the status quo. It contradicts ADR-0004's accepted wording and makes
approval depend on a client that can be bypassed or modified. Rejected.

### "Everything on the server is authoritative"

Simple, but false. A proxy that forwards, a logging service, or a route that
trusts `approved: true` is server-side and still bypassable or credulous. It
would also wrongly rule out a future trusted local boundary. Rejected in favor
of the property definition in EB-2.

### Human approval for every write

Easy to state, but it contradicts the existing class model (reads and some
writes need no interactive approval) and would push users to approve without
reading. Rejected (EB-4).

### Define the full protocol now

Choosing token format, cryptography, approval ledger and route classes in this
ADR would decide implementation before the route inventory exists. Rejected.
The invariant is decided here; mechanisms follow in R1.

### Fold D-2 into ADR-0007

ADR-0007 deliberately excludes action permission (OD-10). Merging the two would
blur ownership and authorization. Rejected.

### Status quo

D-2 stays open, R1 has no yardstick, and G2 cannot be measured or closed.

## Consequences

### Positive

- G2 and R1 get a precise conformance test.
- "Is this boundary authoritative?" becomes a checkable question about control
  and bypass, not about location.
- Approval reuse across different effects is ruled out by design.
- Runtime and model lanes fall under the same rule as clients.
- Local and future device execution is not ruled out.

### Negative and tradeoffs

- None of the backend write handlers listed above is itself an authoritative
  boundary. System-level conformance is NOT ESTABLISHED. Once this ADR is
  accepted, each governed effect they can produce has an unresolved
  conformance-evidence disposition until R1 either establishes an accepted,
  unavoidable authoritative boundary on that path or adds one. If R1 finds
  that a governed effect can occur without such a boundary, that effect is
  non-conforming. Recording this open conformance-evidence debt is not a fix.
- Server-side enforcement adds latency and an availability dependency for
  governed writes (ADR-0004 already accepts this).
- Approval evidence must travel from the client to the boundary in a
  verifiable form. That needs principal authentication, which no accepted
  record yet defines.
- Client and server policy evaluation can drift. Divergence must resolve in the
  boundary's favor.

### Operational and migration impact

No code, configuration, schema, runtime or deployment change follows from
proposing or accepting this ADR. Conformance work is recorded as R1 debt (see
"Open follow-ups").

## Security, privacy, and trust boundaries

- Places the principal authorization boundary on the trusted side of each
  effect, as `trust-boundaries.md` already assumes ("server-side policy",
  "Every arrow is a validation point").
- Directly supports threat-model invariants #2, #3 and #6 and threats T-02,
  T-05 and T-12.
- Does not weaken any existing control. The browser checks stay as defense in
  depth.
- Does not by itself enforce anything. Every path in the evidence table stays
  as it is until R1 lands.

## Validation

Acceptance does not prove conformance. Later evidence includes:

- an inventory of every path that can produce a governed effect, with its
  policy class and its authoritative boundary (or "none");
- negative tests: a direct call that omits, forges, alters or replays approval
  evidence for an approval-required effect is refused and leaves state
  unchanged (ADR-0004 Validation);
- binding tests: approval for A presented with B (changed target, content,
  scope, policy class or expired) is refused;
- tests that caller-asserted approval fields, including a caller-written
  `approvalState`, do not authorize an effect;
- tests that a prohibited effect is refused whatever evidence is presented;
- a check that no ungoverned path bypasses each claimed boundary, including
  direct reachability of the backing store or service;
- tests that retry or replay under one authorization creates no additional or
  different effect.

## Revisit triggers

- A trusted local or offline execution model is proposed (ADR-0004 revisit
  trigger).
- Bounded autonomous approval authority is proposed for any component.
- A principal authentication design is accepted that changes what approval
  evidence can be.
- A proposed contract-set clause defines the policy or approval boundary
  differently.
- Evidence that server-side enforcement makes a conversational path
  unacceptably slow (HX-03). Performance never justifies a bypass.

## Open follow-ups

- D-2 is resolved by owner acceptance of this ADR (2026-10-05). Acceptance
  establishes the conformance yardstick only. It establishes no implementation
  and no conformance of any existing route, client, runtime or deployment. G2
  and G1 remain OPEN.
- **R1** (not authorized here):
  1. inventory every write route and every other path to a governed effect;
  2. classify each effect under accepted policy;
  3. place or confirm an authoritative boundary for each, with no ungoverned
     bypass path;
  4. harden `/os/drafts` POST and DELETE first;
  5. inventory and disposition `POST /os/tasks`, `PATCH /os/tasks/{id}`
     (including caller-set `approvalState`), `POST /os/goals`,
     `POST /os/goals/{id}/transition` and `POST /os/goals/{id}/link_task`;
  6. add negative bypass and binding tests;
  7. only then assess whether G2 can close.
- **R2:** G1 tighten-only enforcement, independent of this ADR.
- **R5:** runtime tool-path inventory (ACT-03) against EB-8 and EB-9. Needs
  separate live-inspection authorization.
- **R8:** goal acceptor and caller authorization, where ADR-0007 and this ADR
  meet. Idempotency payload binding (ACT-06, GOAL-05) stays there.
- Principal authentication for approvers and callers: needs its own decision.
- Network exposure of the backend and Next.js app: REVALIDATE under separate
  authorization.

## Hidden-assumption review

What assumption could make this design look correct while it is wrong?

- **"Server-side means trusted."** False. EB-2 defines authority by control and
  non-bypass. The current Next.js handlers are server-side and contain no
  policy or approval check.
- **"The UI being honest means the API is protected."** False. The backend
  handlers contain no local policy or approval check (REPO CODE), and the
  repository does not establish what, if anything, sits in front of them.
  UI correctness says nothing about other callers (EB-9).
- **"`approved: true` proves approval."** False. The task store already accepts
  a caller-written `approvalState: "approved"` (EB-5).
- **"The same user approved before, so later actions are approved."** False.
  Approval binds to one effect and scope (EB-7).
- **"Approval of a preview covers the changed request."** False. A material
  change invalidates it (EB-7, P-03).
- **"Policy evaluation is authorization."** False. Evaluation is an input. The
  boundary decides for one bound request (EB-6).
- **"The executor may authorize itself."** False where policy requires
  independent approval. The executor's own decision cannot satisfy that
  requirement (EB-8, "Executor separation").
- **"Owning a domain grants write permission."** False (EB-12, OD-10).
- **"Every action needs human approval."** False (EB-4).
- **"A route not in the UI cannot be called."** False. `link_task` has no UI
  caller and is still a write route with no local check (EB-9).
- **"HTTPS makes the client authoritative."** False. Transport security protects
  the channel, not the caller's honesty.
- **"Authentication is authorization."** False. Authentication identifies a
  principal. Policy and the boundary decide the effect.
- **"A model's confidence or recommendation is permission."** False (EB-8;
  threat-model invariant #2).
- **"Historical route behavior describes the current deployment."** False.
  Runtime and deployment rows are HISTORICAL or UNKNOWN. Nothing here
  establishes current exposure.
- **"A section header saying 'approval-gated' means the handler is gated."**
  False. `create_draft` sits under such a header and checks no approval.
- **"Fixing drafts fixes G2."** False. Tasks and goals remain (EB-13; ledger
  R1).
