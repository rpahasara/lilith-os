# Stage-III A2 fixed operational wiring (source-only)

Status: dormant source/control-plane work based on protected main
`6de7f6dddd93cd65671b58e627ad3c92746c9fbd`. No DEV installation,
authority issuance, or experiment is part of this change. The already reviewed
candidate release, accepted stores, synthetic owner/credential/fixture, and
final controller are not modified.

## Immutable, exact control release

`memory_broker_stage3_wiring_install.py` has one fixed `--install-fixed` verb,
no operator-supplied path, release, service, database, signal, or script. Its
fixed execution path is `/tmp/lilith-stage3-a2-final-control-installer.py`:
the owner must independently verify that installer's SHA-256 against the
protected source before a later, separately authorized invocation. It imports
no project module before the staging bytes have passed exact custody and
digest checks; the accepted-baseline read uses only verified control bytes
loaded from memory. A future installer invocation requires the pinned DEV host
and accepted read-only snapshot before any write. It accepts a root-owned
`0700` fixed staging directory containing **only** the seven named Stage-III
control files. Every member must be a root-owned, single-link `0600` regular
file with the exact protected-source SHA-256 pinned in the installer; no tar
paths, symlinks, selectors, or extra members are accepted. Staging and release
identity must be independently reviewed before a later DEV transfer.

The installer creates `/opt/lilith-stage3-a2-final-v1` only if absent, writes
each fixed file exclusively and fsyncs it, writes a canonical manifest of the
base commit and all seven digests, verifies installed bytes, and leaves the
root-owned release directories `0555` and files `0644`. It then installs one
exact root-owned unit at
`/etc/systemd/system/lilith-stage3-a2-final.service`, reloads systemd, and
requires it to be static and inactive. It does **not** enable, start, dispatch,
or invoke any Stage-III code. An incomplete install is a terminal collision
for review; there is no automatic overwrite, cleanup, or retry.

## Closed launch and one-shot boundary

The unit is manually startable only through root-controlled systemd service
operation. It has a fixed `ExecStart` of `/usr/bin/python3 -I -B` on the
installed dispatcher, `Type=exec`, `Restart=no`, no `[Install]` section, and a
bounded runtime. It has no environment or argument input for arbitrary target
selection. No CI/CD workflow or API endpoint is registered to start it.

The dispatcher checks exact release membership, root custody, all helper
digests, canonical manifest, fixed unit file custody, systemd invocation ID,
`MainPID`, zero restarts, and exact Python command line **before** importing
control modules or claiming authority. It then checks the pinned DEV host and
creates a separate root-owned, fsynced, exclusive dispatch-attempt tombstone
under `/var/lib`. A second launch fails before V2 issuance, including after a
pre-transition failure. It calls `FinalController.execute_once()` synchronously
in the same systemd main process; there is no detached child, shell, timer,
auto-resume, or replacement process. The existing pidfd guard therefore binds
to that exact root process throughout the experimental interval. Unexpected
termination while experimental bindings are active still makes the broker and
socket inert through the reviewed OS dependency, independent of Python cleanup.

The merged final controller retains its separate durable attempt marker, exact
V2 JIT authorization, challenge/proof/arm one-shot behavior, pidfd kill,
recovery/replay receipts, evidence sealing, and restoration checks. This
wiring does not loosen those contracts. A later owner decision must separately
authorize DEV transfer/installation and the single live service start after
verifying the accepted baseline and exact artifact. The earlier live-execution
authorization is not exercised by merging this source.

## Failure and test boundary

Malformed staging, release drift, systemd-origin mismatch, old attempt/vault,
or ambiguous unit state fails closed. Once the dispatch tombstone is written,
there is no second invocation even if the final controller fails before its
own marker. Partial transition uses the already-reviewed fail-inert path; no
installer or dispatcher cleanup removes evidence. The unit has no restart or
auto-start relationship, and manual service stop/death is contained by the
existing guard once the experimental transition is active.

Focused tests pin all source hashes, reject extra/mismatched staging members,
check exact systemd process binding, verify the unit has no enable/restart
surface, and prove the dispatch tombstone is exclusive. The isolated Ubuntu
24.04 WSL2 fixture ran real systemd as PID 1 with a synthetic runtime-only
unit and worker derived from the fixed unit. It observed `Type=exec` retaining
one active main process, `NRestarts=0`, a static/non-enabled unit, and no
restart after killing only that synthetic main process. The runtime unit and
failure state were removed afterwards. Neither these tests nor this source
work ran a LILITH service, issued owner authority, or contacted DEV. The
isolated fixture does not substitute for later DEV baseline/installation
review or authorize a live service start.

## Protected-main DEV transport and dispatch entrypoint

The later source-only workflow
`.github/workflows/memory-broker-dev-stage3-a2-final.yml` is **manual only**.
It has no push, merge, timer, or workflow-run trigger. It accepts only two
operation choices, `INSTALL_CONTROL_ONLY` and `DISPATCH_ONCE`, each with a
different exact owner confirmation and a separately approved protected-main
commit SHA. It rejects a non-owner actor, non-main ref, dirty or mismatched
checkout, changed byte-pinned sources, and GitHub job reruns **before** cloud
authentication. The two operations are separately dispatched; installing the
control release never launches it. A source merge does not contact DEV.

The workflow reuses the existing GitHub OIDC provider, deployer service
account, DEV instance identity, zone, and IAP SSH/SCP mechanism. It adds no
credential or IAM action. Failure to authenticate, inspect the pinned VM, or
obtain the existing narrow SSH/sudo access is terminal for that run and must
be reviewed rather than repaired by widening IAM. The exact eight protected
sources are transferred into an exclusive, unprivileged `0700` inbound
directory. The fixed transport helper rejects extra members, symlinks,
non-regular files, wrong custody, and any digest drift before creating the
root-owned installer and seven-file staging directory. It validates the
accepted snapshot before staging, invokes only the fixed `--install-fixed`
installer, and independently rechecks installed bytes, manifest, and static
inactive unit. A partial transfer or installation is left for review; there
is no automatic cleanup or retry.

`DISPATCH_ONCE` requires an independently accepted DEV snapshot, the exact
inactive candidate release, the byte-pinned installed control, the unchanged
static/inactive unit, and absent one-shot markers before issuing exactly one
`systemctl start lilith-stage3-a2-final.service`. It accepts no alternate
unit, script, release, database, or signal input. The helper only observes the
result afterwards; it never starts again, restarts, stops, or performs
recovery. A successful systemd result and sealed restored report are required
to report success. Uncertain transport or runtime state is a terminal review
condition; the existing controller and OS liveness dependency remain
responsible for fail-inert containment and evidence preservation.

This entrypoint is dormant until separately owner-dispatched after protected
review. Its source validation cannot prove the live cloud identity's current
permissions or substitute for the later accepted-baseline and installed-byte
checks on DEV.
