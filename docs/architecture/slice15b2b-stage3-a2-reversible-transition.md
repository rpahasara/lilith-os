# Slice 15B2b Stage III-A — reversible experimental transition V1

Status: **source-only, dormant**. This record describes the implementation at
protected-main base `b97b39444f7f9e0d7ac610755a96db41b8460e96`. It does
not authorize or register a DEV action. The Stage-III final execution controller,
its dispatch authorization, and its deployment remain separate gates.

## Closed identities and boundary

The accepted broker is `817a83e44cec8965479fd97fc30b7a0b3ae49ab2` and
the only experimental candidate is
`4a04f2d09a2b32aecedfe777090fd2e1a27ec909`, with archive SHA-256
`329e286b09610c6d37dab4b343f26743afa36889870cfb6593ef44f62300b66e`
and manifest SHA-256
`784c60d39edbd67b86d670bf568c0d28a1a6eef202c5d19254ec0f6dc74da313`.
The trusted accepted snapshot must have complete SHA-256
`dff5ccddad5884b57f5cf895a9c86c741077fd21857d6e67de57803e6fde68e5`.
Only DEV / `SYNTHETIC_ONLY` / `DISABLED` canonical capability is permitted.
The existing closed, unused V2 authorization must be issued by the later final
controller *before* the transition begins. This module neither issues it nor
creates challenges, proofs, arms, signals, or recovery actions.

## One-shot transition

`scripts/memory_broker_stage3_transition.py` has no CLI or workflow entrypoint.
`TransitionController.activate()` first validates the accepted trusted snapshot,
candidate custody, exact selector/configuration, and unused V2 marker. It creates
a root-owned `0700` vault at `/var/lib/.lilith-memory-broker-stage3-a2` and
fsyncs an exclusive `INTENT` journal record **before** stopping the socket and
service. The vault is on the same filesystem as the synthetic state directory.
Every later journal record is exclusive, root-only, canonical JSON, chained to
the previous record's SHA-256, and fsynced with its containing directory.
Neither a second `INTENT` nor an automatic replay/resume is allowed.

After both units are stopped and no broker-UID process remains, the original
owner and evidence stores (including WAL and SHM sidecars) must hash exactly as
they did before quiescence. Their directories are renamed into the root-only
vault. No SQLite connection is opened on those accepted originals. The
experimental fork is copied from their bytes and verified against the original
physical hashes. Only the **fork** receives the candidate release binding in
`synthetic_schema_v1`; all inherited rows are rehashed and must remain exact.
The provenance record binds accepted snapshot, physical hashes, original and
candidate release identities, and inherited/fork row hashes. Historical rows
remain inherited accepted history, not candidate-created evidence.

The fork directories, candidate `dev.json`, and `current` selector are switched
only while socket and broker remain stopped. Atomic rename/replace is used for
each component; there is deliberately no claim that the multi-path switch is
one filesystem transaction. The durable phase journal and inert service state
make any interruption observable and non-executable. Candidate manifest,
configuration, SQLite release binding, inherited rows, service invocation,
health, and unchanged DEV API baseline are checked before the state is marked
`CANDIDATE_ACTIVE`. The V2 marker must still be fresh at that point. The
existing ten-minute lifetime is not extended.

## Crash evidence and restoration

The future final experiment controller must independently establish the exact
A2 barrier, stopped process incarnation, stopped WAL digest, exact-process kill,
new invocation, single recovery outcome, and rejected replay. Only then may it
pass a closed `Stage3A2CompletedEvidenceV1` record to `seal_evidence()`. The
transition control checks the terminal V2 used marker, absent arm, selected
candidate, restarted invocation, unchanged inherited rows, and exactly one new
consumed challenge/request with no new claim or synthetic evidence. An
unverifiable record stops broker and socket; it cannot unlock restoration.

`restore()` requires sealed evidence. It stops both units, retains the entire
experimental state fork in the vault, and *copies* the accepted originals back
to active paths, leaving the originals in the root-only vault. It restores the
original configuration bytes and accepted selector, then restarts and verifies
health, exact accepted state-file hashes, original configuration hash, unchanged
DEV API baseline, terminal V2 marker, absent arm, and a **new** broker
invocation. The separate `POST_STAGE_III_A_RESTORED_V1` contract does not reuse
the historical `POST_STAGE_II_ACCEPTED_V1` invocation/start-time assertion or
claim that the old complete snapshot digest still describes the new runtime.
Experimental stores, phase journal, provenance, and completed evidence remain
retained for review.

Any uncertainty after `INTENT` triggers a stop of both units and a terminal
`FAILED_INERT` record. If containment itself cannot be verified, the control
raises `STAGE3_CONTAINMENT_UNVERIFIED`; it does not silently retry, reissue
authority, roll back partial state, or start either unit. Recovery from a
partial journal requires a separately reviewed operation and authorization.

## Remaining operational gate

This source is not installed on DEV, has no dispatch registration, and is not
yet an A2 experiment controller. Before any operational use, a separate review
must bind the final controller's independently verified barrier/kill/recovery/
replay evidence to `Stage3A2CompletedEvidenceV1`, validate the exact runtime
environment and state-fork behavior on an isolated synthetic test host, and
authorize any DEV deployment and execution explicitly. In particular, the
final controller must provide an OS-enforced liveness dependency that stops
*both* broker and socket if the root controller process dies after candidate
startup; Python exception containment alone cannot cover an uncatchable
controller termination. The dormant transition source is not an operational
go-ahead until that dependency is reviewed and tested.
