# Threat Model

## Scope and assumptions

This initial model covers the target control path from user intent through LILITH, Hermes or another runtime, capabilities, external systems, verification, and durable state. It is a living placeholder: implementation-specific endpoints, identities, data stores, and deployments must be added during the AS-IS audit.

The system processes untrusted natural language and may eventually receive sensitive personal data and authority to cause external effects. Models are not trusted security principals or policy enforcement points.

## Assets

- identity charter and relationship continuity;
- user memory, preferences, goals, and personal data;
- policy, approvals, delegation, and revocations;
- credentials and connector tokens;
- canonical tasks, revisions, and action history;
- capability definitions and execution parameters;
- evidence, audit records, and provenance;
- deployment artifacts, source, models, prompts, and configuration;
- user attention and trust.

## Adversaries and failure sources

- malicious external content or indirect prompt injection;
- compromised client, runtime, connector, worker, plugin, dependency, or operator account;
- unauthorized local user or stolen device;
- curious or malicious service provider;
- model error, hallucination, policy confusion, or behavioral drift;
- ordinary distributed-system failures: retries, partitions, stale caches, clock skew, and partial success;
- well-intentioned user error under stress or ambiguity.

## High-priority threat scenarios

| ID | Scenario | Impact | Planned controls | Validation placeholder |
| --- | --- | --- | --- | --- |
| T-01 | Retrieved content instructs the runtime to exfiltrate data or invoke a tool | Privacy loss, unauthorized action | Treat content as data, capability allowlist, policy outside model, egress limits | Adversarial connector corpus |
| T-02 | Approval for proposal A is replayed or substituted for proposal B | Unauthorized external effect | Canonical serialization, fingerprint, expiry, state binding, one-time/limited use | Mutation and replay tests |
| T-03 | Timeout causes a blind retry after the first call succeeded | Duplicate email, deployment, purchase, or mutation | UNKNOWN state, operation ID, external idempotency, read-back reconciliation | Fault injection around commit point |
| T-04 | Runtime fabricates success or verification evidence | False completion and misplaced trust | Independent evidence, authenticated sources, verifier contract | False-PASS benchmark |
| T-05 | Stale client overwrites a cancellation, revocation, or newer task state | Unauthorized continuation | Canonical revisions, expected-revision conflict, leases where needed | Concurrent mutation suite |
| T-06 | A worker or runtime amplifies its delegated authority | Lateral access or broader side effects | Narrow envelope, non-transitive credentials, deny-by-default registry | Nested delegation abuse tests |
| T-07 | Secrets enter model context, logs, traces, or client state | Credential compromise | Secret handles, scoped tokens, redaction, canaries, retention | Canary-secret scans |
| T-08 | Memory poisoning changes identity, preferences, or policy | Persistent manipulation | Provenance, admission rules, separation of inference, user correction, protected policy store | Poisoned-memory scenarios |
| T-09 | Deletion hides data from queries but leaves embeddings or derivatives | Privacy and compliance failure | Data lineage, tombstones, cascading deletion, backup expiry | Deletion audit |
| T-10 | Multi-runtime partition causes conflicting identity or duplicate action | Split identity and real-world harm | Canonical authority, conflict records, leases/idempotency, offline limits | Partition simulation |
| T-11 | Model/runtime upgrade changes judgment or safety behavior | Silent regression | Versioned compatibility suite, shadow evaluation, rollback | Golden scenario gate |
| T-12 | Urgent event pressures the system to bypass approval | Consequential unauthorized action | Urgency/authority separation, predelegation only, escalation policy | Emergency tabletop exercises |
| T-13 | Observability stores excessive personal reasoning or content | Privacy loss and chilling effects | Minimal structured events, redaction, access/retention tiers | Trace privacy review |
| T-14 | Backup restore revives revoked authority or old secrets | Unauthorized actions after recovery | Restore lineage, revocation reconciliation, key rotation, integrity checks | Disaster-recovery exercise |
| T-15 | A V2 proposal ID is interpreted as a V1 proposal or collides across families | Wrong lineage, unauthorized canonical write, failed erasure | Immutable family-neutral proposal refs, closed family dispatch, fingerprint binding | V1 migration and cross-family tests |
| T-16 | RESTORE consumes authorization for a fabricated item or unverified historical digest | Rollback of the wrong identity or value | Resolve exact canonical item/current/history, digest check, transactional one-time consumption | Cross-item, digest-drift, replay, and fault tests |
| T-17 | Caller, browser, or model activates canonical memory or a Policy capability | Unauthorized durable personal memory | Server-only closed config, inactive defaults, independent registry/containment gates | Missing/malformed/inactive config tests and static scans |
| T-18 | Migration runs on import, without a current backup, or against unknown schema | Data loss or unrecoverable state | Explicit CLI, online backup evidence, source identity/fingerprint/count checks, transactional migration | Import-side-effect, stale-backup, unknown-schema, and idempotency tests |
| T-19 | Candidate bundle includes a secret, unrelated working-tree file, or path traversal | Secret disclosure or deployment compromise | Trusted allowlist builder, deterministic manifest, trusted extractor, exact member set, no links | Determinism, tamper, member, and traversal tests |
| T-20 | Failed multi-file install leaves mixed source or reports the wrong SHA | Incoherent runtime or false deployment evidence | SHA-named releases, preflight tests, atomic symlink, health and identity read-back, prior-link rollback | DEV install, restart, health, identity, and rollback exercise |
| T-21 | A client, model, or relay substitutes owner request fields or digests | Authorization for a different memory action | Broker-only closed request construction, unchanged frozen-action digest, domain-separated canonical request digest, exact B1a binding | Golden vectors and unknown/mutated-field tests |
| T-22 | A consumed owner proof is retried across the owner-control and cognitive databases | Duplicate Actor evidence or replayed authority | Durable claim before issuance, challenge ID as unique evidence nonce, conservative read-only reconciliation, no blind reissue | Deterministic crash, concurrent confirmation, and erased-evidence tests |
| T-23 | A missing, corrupt, downgraded, or test-seeded owner-control ledger is accepted as production authority | Forged or reset owner state | Governed startup validation of schema fingerprint, integrity, mode, public credential shape, and foreign keys; no implicit production initialization | Missing/corrupt/schema/mode/fixture startup tests |
| T-24 | Synthetic broker contracts are mistaken for an OS custody boundary | Runtime or deployer retains access to authority material | Explicit synthetic-only gate and documented absence of account, socket, relay, IAM restriction, and DB/key custody | B1b-2/B1b-3 isolation review before live authority |

## Security invariants

1. Untrusted content cannot grant authority.
2. A model's decision cannot replace deterministic authorization.
3. Approval is valid only for the exact proposal and bound conditions.
4. Credentials are not placed in model-visible context.
5. Unknown external state does not permit blind retry.
6. Clients and runtimes cannot directly commit canonical consequential state.
7. Sensitive data collection and retention are explicit and reviewable.
8. Security-relevant state transitions produce durable, access-controlled evidence.
9. Learning may propose canonical memory but only L04 may apply it.
10. Cognitive recovery cannot outrank newer Privacy suppression state.

## Data-flow and privacy review placeholders

Before each integration, add:

- data elements and classification;
- origin, destination, subprocessor, and model route;
- purpose, consent, retention, and deletion path;
- encryption and key ownership;
- log/trace fields and redaction;
- credential scope and rotation;
- abuse cases and incident response owner.

## Risk review cadence

Update this model when adding a capability, connector, external write, memory class, worker, runtime, client, model provider, deployment environment, proactive trigger, or broader delegation. Review after incidents and before every autonomy-level promotion.

See [Trust Boundaries](trust-boundaries.md) and the [Research Register](../research/research-question-register.md).
