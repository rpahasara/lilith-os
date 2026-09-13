# Component Boundaries

| Component | Owns | Must not own or bypass |
| --- | --- | --- |
| Client / Presence | Intent capture, accessible presentation, semantic status | Credentials, canonical state, raw reasoning, direct capability execution |
| Intent gateway | Request normalization, session linkage, input provenance | Unreviewed external side effects |
| Context assembly | Policy-filtered retrieval and source labeling | Silent fact creation or durable memory admission |
| Goal/task service | Lifecycle, dependencies, revisions, durable outcomes | Arbitrary tool invocation |
| Planner/playbook selector | Proposed steps, assumptions, expected outcomes | Final authority to execute consequential actions |
| Policy/risk engine | Deterministic constraints and contextual risk evaluation | Inventing user approval or weakening policy through learning |
| Approval service | Fingerprinted proposal, approver, scope, expiry, decision | Reusing approval for changed intent or state |
| Identity service | Versioned identity charter and relationship continuity | Runtime-specific prompts as the only identity record |
| Memory service | Admission, provenance, sensitivity, retention, contradiction | Transcript dumping or treating inference as observed fact |
| Sync authority | Canonical revisions, leases/conflicts, reconciliation | Model judgment about which write “feels right” |
| Runtime adapter | Translate scoped tasks to Hermes or another runtime | Canonical identity, policy, or durable-state ownership |
| Capability registry | Typed operation metadata and executor binding | Hidden unrestricted tools |
| Worker | Bounded delegated task and evidence production | Authority beyond the explicit delegation envelope |
| Verifier | Compare expected state with independent evidence | Trust executor self-report as sufficient by default |
| Audit/observability | Append-only operational evidence and metrics | Sensitive-content collection without retention policy |
| Attention model | Interruption level and delivery timing | Bypassing action authorization because an event is urgent |

## Boundary review questions

For every new component or integration:

1. What invariant, state, trust, or failure boundary justifies it?
2. What exact authority does it receive?
3. What calls it, and what can it call?
4. What happens if it is malicious, stale, duplicated, slow, or unavailable?
5. How can its effect be observed and reversed?
6. Which other component independently verifies it?
