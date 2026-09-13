# ADR-0003: Execution and verification are separate responsibilities

- **Status:** Accepted
- **Date:** 2026-09-13
- **Owners:** Project maintainers
- **Related:** RQ-033, RQ-034, RQ-035, RQ-036, RQ-037

## Context

An API can return success while producing the wrong resource, wrong content, partial effect, or an effect that immediately degrades. A timeout can occur after the effect succeeded. Treating an executor's response as goal completion creates false PASS outcomes and unsafe retries.

## Decision

Execution produces an action result. Verification separately compares expected goal state with task-specific evidence. Consequential capabilities require independent read-back where feasible. Unknown and partial outcomes are first-class lifecycle states.

Independence is proportional to consequence: it may mean a separate request, API, credential, worker, observation channel, or stability window. The same physical service may host both responsibilities only when their contracts remain distinct and correlated failure is understood.

## Alternatives considered

### Trust transport or executor success

Simple but confuses request acceptance with user-goal achievement.

### Ask the model to self-check

May catch reasoning mistakes but is not independent evidence of external state.

### Verify every action maximally

Can be expensive, slow, invasive, and impossible. Verification must be risk- and task-specific.

## Consequences

### Positive

- Fewer false-success claims and duplicate side effects.
- Better evidence, recovery, and user trust.
- Explicit handling of partial and unknown state.

### Negative and tradeoffs

- Additional calls, latency, and capability-specific contracts.
- Some systems offer weak read-back, requiring documented residual risk.

## Security, privacy, and trust boundaries

Verification can expand data access. It must use minimum necessary scope and prevent attacker-controlled evidence from becoming authoritative without validation.

## Validation

- Inject successful, failed, partial, delayed, duplicated, and ambiguous outcomes.
- Measure false PASS, false FAIL, partial classification, and unresolved UNKNOWN rates.
- Test correlated executor/verifier failure.

## Revisit triggers

- New evidence sources or connectors change independence options.
- Evaluation shows verification cost exceeds benefit for a task class.
