# Stage-III A2 control-side adapters (source-only)

Status: dormant source contract. This change does not register a CLI or a workflow action, deploy to DEV, or execute Stage-III. A separately reviewed final controller must prove the A2 barrier, exact stopped/killed process identity, restart, and evidence sequence before it may call these adapters or seal the experiment.

## Exact scope

The adapters reside in `scripts/memory_broker_stage3_adapters.py`. The pinned A2 broker release, broker IPC protocol, proof verifier, A2 fault seam, synthetic credential custody, and existing general relay behavior are unchanged.

The root final controller creates one `Session` from the single JIT `Stage3A2ExecutionProposalV1` returned by `stage3_prepare_package()`. The session copies the proposal and freezes one length-prefixed, canonical `CONFIRM_SYNTHETIC` frame in memory. The assertion never enters command arguments, environment, a persisted adapter receipt, or child output. Its SHA-256, challenge ID, authorization ID, and observed broker invocation are recorded in root-owned, fsynced one-shot attempt/result receipts. A missing result after an attempt is ambiguous and terminal; there is no retry path. The session is process-bound and redacts its representation.

Before each action, the adapter rechecks the authorized DEV host, exact selected/installed candidate, root transition journal in `CANDIDATE_ACTIVE`, terminal-used closed V2 authorization and journal intent, proposal/arm derivation, liveness guard, exact service/socket state and invocation, and the bound challenge/request in the experimental owner database. It requires no claim and no synthetic evidence for the challenge. The initial action additionally requires an unexpired challenge/arm/authorization and the exact root-owned arm bytes. Recovery and replay require the arm to be absent and a new broker invocation. The used authorization is checked against its original issuance time only to verify its closed historical binding; it is not reissued or treated as fresh authority.

## Relay-UID exact sender

The fixed `lilith-memory-relay` child receives metadata and the frozen frame through an anonymous stdin pipe. It checks its UID, frame length and canonical shape, challenge binding, and frame digest. It sends `conn.sendall(frame)` to the fixed broker socket without regenerating, resigning, or substituting the assertion. The initial send records only that the bytes were sent; the final controller must independently prove the A2 barrier and crash. The one later replay sends the **same frame bytes** and requires connection EOF with no response. A post-replay database check still requires `CONSUMED`, no claim, and no synthetic evidence, plus a healthy broker. EOF and state checks do not claim to expose a private verifier error code.

## Broker-UID one-shot recovery

The fixed `lilith-memory-broker` child accepts only the exact challenge ID over an anonymous stdin pipe. It checks its UID and DEV context, fixed selected release/config, and opens only the governed experimental owner/evidence paths. It instantiates the pinned candidate `DevSyntheticBrokerCore` and calls `recover(challenge_id)` exactly once. The root controller has already checked the consumed/no-claim state, and the child accepts only `PROOF_BURNED_NO_CLAIM`. The parent checks that result and the no-claim/no-evidence state again. No `RECOVER` broker IPC or generic recovery target is added. The pinned core's no-claim branch is observational; its other reconciliation branches are rejected by the precondition and result check.

## Remaining operational gate

These are narrow source primitives, not a complete live experiment controller. They do not create proof or an arm, observe or kill a stopped broker, invoke service restart, restore the accepted release, or seal evidence. Before any separately authorized DEV execution, the final controller must compose and validate those steps against the existing transition and OS-liveness contracts. Focused tests cover immutable frame reuse, fixed child identities and pipe transport, one-shot durability, failure containment, and a disposable Unix-socket exact-byte fixture; they do not run either child against DEV.
