## Outcome

Describe the user, research, or engineering outcome this pull request delivers.

## Links

- Issue:
- Research question:
- ADR:

Use `N/A` where a link is not applicable.

## Change type

- [ ] Documentation only
- [ ] Research method or result
- [ ] Architecture or contract
- [ ] Tooling / CI/CD
- [ ] Product code
- [ ] Security-sensitive change

## Architectural check

- [ ] The LILITH/Hermes boundary remains explicit.
- [ ] State ownership and authority are documented.
- [ ] Trust-boundary changes are reflected in the threat model.
- [ ] New external side effects have a risk class, approval rule, and verification contract.
- [ ] No design-only mechanism is described as implemented or validated.

## Verification evidence

List checks performed and attach or link evidence. For failures or skipped checks, explain why.

```text
python scripts/validate_repository.py
```

## Failure and rollback

Describe expected failure modes, partial-success behavior, recovery, and rollback.

## Privacy and security

Describe personal data, credentials, logs, model inputs, untrusted content, and retention impact. Write `No change` only after review.

## Reviewer notes

Call out the hardest tradeoff or most uncertain assumption.
