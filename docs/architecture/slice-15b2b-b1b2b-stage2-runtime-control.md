# Slice 15B2b-B1b-2b Stage-II runtime control: API baseline repair

## Research record

**STAGE-II CONTROL MODEL DEFECT — VOLATILE DEV API PROCESS IDENTITY WAS INCORRECTLY ENCODED AS A DURABLE SOURCE-CONTROL INVARIANT.** The original trusted Stage-II source required Core API PID `80100` and its September 23 start time. A separately owner-authorized bootstrap restart legitimately changed that process identity while the service remained healthy and its trusted configuration and custody were unchanged. Read-only Stage-II preflight therefore stopped before authorization or activation. This was a control-model defect, not an API deployment defect.

The correction pins durable DEV API identity and custody in trusted source, then captures volatile process identity for each future authorization. It does not pin replacement PID `88740` or its start time in source. The old and new identities are test fixtures only.

## Durable and observed boundaries

The pinned DEV host check still requires exact GCE project, zone, instance ID/name, local FQDN, and machine ID, and explicitly rejects PROD. Stage-I release, identities, configuration, database custody, and inert broker/socket checks remain unchanged. API service name, loaded/active/running state, `lilith` user/group, exact working directory, fragment path, absence of drop-ins, executable and command line, app SHA-256, API unit SHA-256, canonical-runtime and legacy DEV DB SHA-256, `NRestarts=0`, and healthy `/health` result are durable acceptance conditions. PID must be positive and start time present, but neither value is source-pinned. The exact unit hash also anchors the on-disk service command and configuration.

`ApiRuntimeBaselineV1` is a closed record with `schemaVersion=1`, service name, `MainPID`, `ExecMainStartTimestamp`, `NRestarts`, active/substate, service user/group, working directory, observed `ExecStart`, app and unit SHA-256, health result, custody hashes, and UTC capture timestamp. Its digest is SHA-256 of UTF-8 JSON with sorted keys and compact separators, matching the existing marker serialization convention. `ExecStart` includes the process start and PID as observed by systemd, so session drift is also visible there.

The Stage-II authorization marker is now a closed schema version 2 record. It contains the full trusted API baseline and `apiBaselineDigest`; schema version 1 is rejected. Before the single-use marker is consumed or any activation mutation, the control reruns the complete inert Stage-I/API preflight and immediately re-observes the API against the marker-bound baseline. It does not silently recapture or replace authorization when PID, start time, restart count, health, command, binary, unit, or custody changes. After the Stage-II experiment, it compares the complete API observation again using the authorized capture timestamp. Any drift is an API non-interference failure; existing failure containment stops broker and socket and preserves evidence.

This control-only repair grants no activation. The prior owner activation decision is not carried forward. After a protected merge and read-only preflight, a fresh owner decision is required before Stage-II marker creation or runtime mutation. No Stage-III, PROD, IAM, real-credential, live-authority, or real-memory capability is introduced.
