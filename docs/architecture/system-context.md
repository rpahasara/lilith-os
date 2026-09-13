# System Context

## Actors

- **Primary user** — owns the relationship, identity configuration, data permissions, goals, and delegated authority.
- **Maintainer/operator** — develops and operates components but does not automatically receive access to personal content.
- **Contributor/researcher** — proposes code, designs, experiments, or documentation under scoped test data.
- **Adversary** — may control content, tool responses, compromised connectors, a runtime, or an account surface.

## Systems

```mermaid
C4Context
  title LILITH system context — target view
  Person(user, "Primary user", "Defines goals, policy, and approvals")
  System(lilith, "LILITH", "Persistent identity, governance, state, memory, goals, and verification")
  System_Ext(hermes, "Hermes", "Replaceable model/tool execution runtime")
  System_Ext(other, "Other runtimes", "Future local, cloud, or specialist execution")
  System_Ext(services, "External services", "Mail, calendar, files, cloud, devices, and APIs")
  System_Ext(idp, "Identity provider / secret store", "Authentication and scoped credentials")

  Rel(user, lilith, "Intent, approvals, corrections")
  Rel(lilith, user, "Results, evidence, interruptions")
  Rel(lilith, hermes, "Scoped task context and authority")
  Rel(lilith, other, "Scoped task context and authority")
  Rel(hermes, services, "Capability calls")
  Rel(other, services, "Capability calls")
  Rel(lilith, idp, "Requests scoped access")
```

## In scope

- coherent personal identity across sessions, clients, models, and runtimes;
- durable tasks, goals, relationship state, policy, memory, and provenance;
- bounded planning and capability execution;
- approval, risk, verification, audit, and attention behavior;
- failure recovery, synchronization, and multi-runtime consistency;
- evaluation of technical reliability and human appropriateness.

## Out of scope for the foundation phase

- unrestricted autonomous action;
- production or safety-critical operation;
- claims of human consciousness or personhood;
- storing all conversation by default;
- implementing every layer shown in target diagrams;
- choosing a permanent model, database, cloud, or client stack.

## External assumptions to challenge

- APIs may time out after succeeding.
- connector data may be stale, partial, adversarial, or unavailable.
- users may be asleep, rushed, mistaken, or unavailable.
- models and runtimes will change behavior across versions.
- clocks, networks, credentials, and devices will fail.
- a successful execution response may not mean the user's goal succeeded.
