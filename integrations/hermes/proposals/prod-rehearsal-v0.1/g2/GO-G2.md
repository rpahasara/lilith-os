# OWNER GO: G2-20261101, isolated rehearsal infrastructure (NOT APPROVED, NOT RUN)

Stage R1 of `prod-rehearsal-v0.1/REHEARSAL-RUNBOOK.md`. **No real data is involved:** the snapshot is verified and never attached. Opening it is G3.

## The snapshot this depends on

| Field | Value |
|---|---|
| Snapshot | `lilith-01-rehearsal-20261101` |
| Id | `<id>` |
| Source | disk `lilith-01`, id `<id>` |
| Status | `READY`, verified 2026-10-31 |
| Holds | **a full copy of PROD's disk, including credentials** |
| Retention | until the rehearsal record is accepted and Cutover 1's return window closes, **no later than 2026-12-01** unless the owner extends it |
| Deletion | **manual, under its own owner approval.** The `delete-after` label deletes nothing |

The October snapshot `lilith-01-preserve-20261027`, id `<id>`, is unchanged.

## What this GO authorizes

1. `preflight.ps1`, read-only, re-run within the hour.
2. `create.ps1`, on a fresh `PASS`, in this order:

| Step | Resource |
|---|---|
| 1, 2 | VPC `lilith-rehearsal`, subnet `<private-ip>`, no Private Google Access |
| 3 | `rehearsal-deny-all-egress`, **before any VM exists** |
| 4 | `rehearsal-allow-iap-ssh`: tcp:22 from the IAP range, to the tag only |
| 5 | blank 10 GB `lilith-rehearsal-synthetic` |
| 6 | VM `lilith-rehearsal-01`: e2-medium, stock Ubuntu 24.04, 60 GB boot, no address, **no service account,** no startup script |

3. `verify.ps1`: control-plane checks, then `isolation_probe.sh` inside the VM only.

**One change from the design:** the VM has no service account at all, not a new one with no roles. That's stricter and simpler.

**The probe proves:** the public internet, PROD and DEV by address, and Google APIs are all unreachable; no metadata token exists; a read-only mount refuses writes.

## What it never does

No use of the snapshot, no contact with `lilith-01` or `lilith-dev-01`, no change to `lilith-vpc`, no IAM change, no NAT, router or peering, no retry. It uses the shared project, in a separate network.

## On failure

Stop and record. Anything already created stays until `destroy.ps1` runs, under its own approval: that removes only these exact names, never a snapshot, and refuses if any non-synthetic disk is attached.

## Before G3: a finding from the real preflight

**`github-lilith-deployer@` holds project-wide `roles/iap.tunnelResourceAccessor` and `roles/compute.osAdminLogin`,** so it would reach this VM too. For G2 that's harmless, because no real data exists there. **For G3 it isn't:** the design requires one named identity, and an admin login on a VM holding real data breaks that. Remove or condition those bindings for the rehearsal window, or sign the exception. Removing them affects PROD deploys, which are dispatch-only and idle.

**Also still open at G3:** the metadata server stays reachable from any VM, including its DNS. With no service account it grants nothing, but DNS can't be blocked by a firewall rule.

## Cost

e2-medium and 70 GB of disk while it exists. Stop or destroy it when idle.

## Evidence

`tests/run_tests.ps1`, 47/47, against a scripted `gcloud`. **The real read-only preflight passed.** Not run on real GCP: `create.ps1`, `verify.ps1`, the probe, `destroy.ps1`.
