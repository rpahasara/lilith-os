# Testing Strategy

## Objective

Testing must answer more than “did the function return?” LILITH needs evidence that identity, authority, state, execution, and user-facing claims remain correct under ambiguity and failure.

## Highest-value invariants

- Hermes or another runtime cannot own or mutate canonical identity directly.
- Clients cannot bypass policy to execute governed capabilities.
- Changed proposals invalidate approval.
- Stale revisions cannot overwrite current state silently.
- Duplicate requests do not duplicate effects under supported conditions.
- Timeouts after possible success become UNKNOWN before retry.
- Completion requires the declared verification contract.
- Inferred memory cannot be promoted as observed fact.
- Redaction prevents secrets and prohibited personal content from reaching logs or models.

## Scenario format

```yaml
id: stable-scenario-id
given: state, policy, evidence, runtime, and external conditions
when: intent or event
faults: injected timing, duplication, compromise, or outage
then: required state, action, evidence, and user communication
forbidden: effects that must not occur
metrics: latency, calibration, false-pass, correction cost, or other measures
```

## Evaluation artifacts

Store versioned synthetic scenarios, expected results, evaluator rubrics, aggregate metrics, and sanitized failure analyses. Do not commit private interaction transcripts or secrets.
