# Stage-III A2 consumed-run forensic inspection

Protected-main source adds one separate, dormant `workflow_dispatch` operation
for consumed DEV dispatch run `36145190507`. It is not a retry or recovery path.
This source change does not contact DEV; use of the operation requires separate
owner authorization for the exact protected-main commit after review.

The workflow pins the owner, branch, run attempt, commit, existing GitHub→DEV
identity and VM instance. It streams one fixed collector through the existing
SSH command channel. No workflow input controls a shell command, path, service,
database, signal, release, or output destination. The collector takes no
arguments. It does not execute installed controller code.

The collector reads only fixed service metadata, bounded journal metadata,
the root-owned Stage-III phase-journal chain, exact preserved evidence/attempt
file presence and hashes, the known selector, and known release manifests. It
does not print evidence contents, proofs, frames, configuration, databases, or
raw journal messages. A missing/inaccessible/invalid item is reported as such;
the collector performs no reconciliation. The phase journal is authoritative
for a validated terminal phase. If it is absent or invalid, the phase is
`UNKNOWN` even if the service has failed.

The existing accepted-state observer cannot run within this operation: its
snapshot implementation starts and collects a transient systemd unit. This
forensic operation records `NOT_RUN_STARTS_TRANSIENT_SYSTEMD_UNIT` and may
report only already-preserved accepted snapshot evidence. It does not claim a
fresh accepted-state equality check. Likewise, journal output is bounded and
restricted to the current boot; unavailable or older logs remain an explicit
limitation. No service start/stop/restart/reset, selector change, restoration,
cleanup, authority issuance, proof action, or A2 replay is possible here.
