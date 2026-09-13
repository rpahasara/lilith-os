# Glossary

## Core system terms

**LILITH** — the persistent, governed personal AI operating system. It owns continuity concerns: identity, relationship state, memory, goals, policy, delegated authority, canonical task state, and provenance.

**Hermes** — a runtime/execution substrate through which LILITH may invoke models and capabilities. Hermes is replaceable and must not become the implicit owner of LILITH identity or canonical durable state.

**Runtime** — an execution environment capable of reasoning, planning, or invoking capabilities on LILITH's behalf. Future runtimes may be local, cloud, specialized, or temporarily offline.

**Client** — a user-facing interface such as web, voice, mobile, desktop, or ambient presence. A client presents state and captures intent; it does not bypass governance to execute capabilities directly.

**Cognitive core** — the bounded control path that interprets intent, constructs or selects plans, coordinates policy and capabilities, and updates task state.

**Capability** — an explicitly registered operation with typed inputs and outputs, authority scope, risk, reversibility, credential requirements, preconditions, execution behavior, and verification contract.

**Worker** — a specialized, bounded agent or service delegated a defined responsibility. A worker receives authority for a task; it does not inherit unlimited authority from the parent system.

## State and evidence

**Canonical state** — the authoritative durable record against which conflicting runtime or client state is reconciled.

**Task state** — durable lifecycle state for a bounded unit of work, distinct from conversational history and long-running goals.

**Goal** — a durable desired outcome that may span conversations, tasks, plans, and time. Goals may be active, paused, stale, blocked, completed, abandoned, or superseded.

**Memory** — durable information used beyond the immediate interaction. It must be classified; conversation context, task state, episodic memory, semantic memory, preferences, evidence, and operational state are not interchangeable.

**Provenance** — information that explains where a claim came from, when it was observed, how it was transformed, and how trustworthy or fresh it is.

**Evidence** — an observation that supports or challenges a claim about system or goal state. An executor's success response is evidence, but not necessarily sufficient evidence.

**Verification** — comparison of expected goal state with independently observable evidence after execution.

## Governance and safety

**Policy** — deterministic or reviewable rules that constrain whether, when, and how a capability may be proposed or executed.

**Approval** — explicit authorization for a canonical, fingerprinted proposal under defined conditions and expiry. Approval is not a general grant of trust.

**Delegated authority** — permission granted in advance for a bounded class of actions, with conditions, scope, expiry, risk ceiling, and verification requirements.

**Risk class** — the intrinsic consequence category of an action. Effective risk also depends on context, uncertainty, timing, blast radius, reversibility, and system health.

**Break-glass** — exceptional emergency authority subject to narrow preconditions, strong audit, notification, and post-event review. It is not an approval bypass.

**Presence** — the user-facing expression of LILITH's semantic operating state. Presence should not leak raw chain-of-thought or become a second source of cognitive state.

## Research maturity

**Implemented** means a mechanism exists in code and passes its declared checks. **Validated** means evidence supports it under stated operating conditions. Neither term means universally solved.
