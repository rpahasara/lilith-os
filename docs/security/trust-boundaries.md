# Trust Boundaries

## Boundary inventory

| Boundary | Untrusted or less-trusted input | Primary protections to design |
| --- | --- | --- |
| User/client → LILITH | Forged state, stale UI, ambiguous voice intent | Authentication, intent confirmation, server-side policy, replay protection |
| Retrieved content → cognition | Direct/indirect prompt injection, poisoned data | Treat as data, provenance, content isolation, capability constraints |
| LILITH → runtime | Excess context or authority, private data | Data minimization, delegation envelope, expiry, allowlist |
| Runtime → LILITH | Malformed plans, fabricated evidence, policy manipulation | Schema validation, policy outside runtime, independent verification |
| Runtime → capability | Tool abuse, parameter substitution, secret exposure | Typed contract, exact binding, scoped credential handle, egress policy |
| Capability → external service | Partial failure, duplicate effect, changed precondition | Idempotency, state binding, timeout semantics, compensation |
| External service → verifier | Stale or attacker-controlled response | Freshness, source authentication, independent signals, uncertainty |
| Client/runtime cache → canonical state | Stale revision, offline conflict | Expected revision, operation ID, leases/conflict record |
| Logs/telemetry → operators | Personal data and credentials | Redaction, purpose limitation, access control, retention |
| Backup/export → restore/import | Rollback of revocation, tampering, identity fork | Integrity, lineage, encryption, restore reconciliation |
| Plugin/connector supply chain → system | Malicious update or overbroad permissions | Pinning, provenance, review, sandboxing, permission manifest |

## Authority path

```text
authenticated principal
  → captured intent
  → canonical task revision
  → policy and contextual risk
  → exact proposal fingerprint
  → approval or bounded delegation
  → runtime envelope
  → capability scope
  → external effect
  → independent evidence
  → canonical outcome
```

Every arrow is a validation point. A shortcut is a governance defect until proven otherwise.
