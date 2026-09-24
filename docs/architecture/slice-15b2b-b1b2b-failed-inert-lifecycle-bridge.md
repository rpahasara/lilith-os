# Slice 15B2b-B1b-2b: failed-inert lifecycle bootstrap bridge

Status: narrowly authorized governance transition; **not** Stage-II acceptance or retry authorization.

The owner-authorized Stage-II run [35924789001](https://github.com/rpahasara/lilith-os/actions/runs/35924789001)
at governed main `782c7bdc15ca7b7b7c94c064292b645ed40bae79` failed its API
non-interference check. Trusted failure-stop left the broker service and socket
inactive, the socket disabled, `MainPID=0`, and `owner.sock` absent. The empty
root:`lilith-memory-ipc` `0710` `/run/lilith-memory` directory remains as
evidence of the attempt. Nothing in this profile declares Stage II accepted.

`POST_STAGE_I` retains its pristine zero-row, no-sidecar, no-prior-attempt
contract. `POST_STAGE_II_FAILED_INERT_V1` is a separate, selected trusted DEV
profile for the exact terminal state created by run 35924789001. It pins the
accepted Stage-I accounts, release, manifest, configuration, units and API
custody; the used authorization ID
`4006ead71ca04c219b3b41e6818010f2`; both complete DB file hashes and
schema fingerprints; every challenge ID and terminal state; every request
digest; the single claim/evidence linkage; empty WAL and preserved SHM; and
the inert service, socket, process and runtime-directory state. The only
evidence ID is
`se.68b647fc14aeea4fb32bdd7d0fada54d8f4af7c272ec6784f5d22c4c8980e7b5`.
Unknown rows, a new marker, changed authority data, corrupted databases,
changed custody, or live broker artifacts fail closed. The consumed marker is
terminal; a future attempt requires a new authorization.

The read-only snapshot includes `historicalBaseline`, a versioned
`Stage2HistoricalBaselineV1`-equivalent JSON value with authorization identity,
database hashes and fingerprints, table counts, challenge/request identities,
claim and evidence linkage, and a canonical SHA-256 state digest. A later,
separately authorized retry control can capture that baseline before a new
attempt and reconcile exact deltas. This bridge performs no retry and does not
change the Stage-II API comparison or IPC test order.

The trusted-main classifier intentionally does **not** classify this validator
change as `CONTROL_ONLY_NO_DEPLOY`. The one-time owner-approved bootstrap
exception is necessary because the prior trusted Stage-II run created a
historical state that the pristine validator cannot recognize. The bridge PR
must be frozen, use an explicit CI-skip commit trailer, and be merged only by
the temporary PR-only owner bypass described in the owner authorization. The
skip leaves required checks pending; it is not evidence that they passed.
The bypass must be removed immediately after merging, before any other work.
No DEV deployment, API restart, broker activation, PROD mutation, IAM change,
or Stage-II retry is authorized by this record.
