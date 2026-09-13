# Target Architecture

This is a directional architecture. Components should be introduced only when a vertical slice demonstrates the responsibility they own.

## Target responsibilities

```mermaid
flowchart TB
    subgraph Clients
      Web[Web]
      Voice[Voice]
      Native[Future native clients]
    end

    subgraph LILITH[Governed LILITH control plane]
      Gateway[Intent gateway]
      Context[Context assembly]
      Goals[Goals and task lifecycle]
      Plan[Playbooks / planner]
      Policy[Policy, risk, and approval]
      Sync[Canonical state and sync authority]
      Identity[Identity and relationship model]
      Memory[Memory lifecycle]
      Verify[Verification and evidence]
      Attention[Attention / interruption]
      Audit[Audit and observability]
    end

    subgraph RuntimePlane[Replaceable runtime plane]
      HA[Hermes adapter]
      LA[Local runtime adapter]
      CA[Cloud/specialist adapter]
      Registry[Capability registry]
      Workers[Bounded workers]
    end

    subgraph External
      Services[External services and devices]
    end

    Clients --> Gateway
    Gateway --> Context
    Identity --> Context
    Memory --> Context
    Context --> Goals
    Goals --> Plan
    Plan --> Policy
    Policy --> HA
    Policy --> LA
    Policy --> CA
    HA --> Registry
    LA --> Registry
    CA --> Registry
    Registry --> Workers
    Workers --> Services
    Services --> Verify
    Verify --> Goals
    Sync <--> Goals
    Sync <--> Identity
    Sync <--> Memory
    Attention --> Clients
    LILITH --> Audit
```

## Capability contract

Every executable operation should eventually declare:

```text
identity and version
typed input and output
resource and authority scope
intrinsic risk and contextual risk inputs
reversibility and compensating action
credential requirements
preconditions and policy rules
approval and fingerprint requirements
idempotency behavior
timeout, cancellation, and retry semantics
verification contract
evidence and audit schema
data sensitivity and retention
```

## Proposed task lifecycle

```mermaid
stateDiagram-v2
    [*] --> Proposed
    Proposed --> Planned
    Planned --> Denied: policy denies
    Planned --> AwaitingApproval: approval required
    Planned --> Ready: preauthorized
    AwaitingApproval --> Denied: user denies
    AwaitingApproval --> Cancelled: cancel / expiry
    AwaitingApproval --> Ready: exact proposal approved
    Ready --> Executing
    Executing --> Unknown: outcome cannot be determined
    Executing --> Verifying: action returned
    Executing --> Failed: proven failure
    Unknown --> Reconciling
    Reconciling --> Verifying: effect found
    Reconciling --> Ready: safe retry established
    Reconciling --> Blocked: cannot resolve safely
    Verifying --> Completed: contract passes
    Verifying --> Partial: partial goal state
    Verifying --> Failed: verification fails
    Partial --> Planned: replan
    Completed --> [*]
    Denied --> [*]
    Cancelled --> [*]
    Failed --> [*]
    Blocked --> [*]
```

## Delivery strategy

Build end-to-end slices through the control loop. Avoid constructing a large speculative hierarchy before one bounded capability proves its contracts. Each autonomy increase requires an evaluation gate and threat-model update.
