# Cutover 1 runbook (PREPARED, NOT APPROVED, NOT RUN)

**Changes what's around LILITH, not LILITH.** Only `app.py` moves, from `bb0a4139` to `53dfae2a` (main at `75ca0db`). Persona, memories, databases, router, Hermes, plugins and `router.yaml` aren't touched, and every lane stays live. Follows `MIGRATION-PLAN.md`.

## Order

| # | Step | Who | Changes |
|---|---|---|---|
| 1 | `prepare.ps1 -Confirm PREPARE-CUTOVER1` | **Approval 1** | Firewall target, deployer access, daily snapshots, guest files in `/var/tmp/c1` |
| 2 | `drive_c1.py --phase preflight --execute` | same | Nothing on LILITH: read-only review, digests in `/root/cutover1-20261101` |
| 3 | Baseline turns, `BASELINE-TEST.md` | Owner sends | Up to 5 provider requests; normal conversation history |
| 4 | First scheduled snapshot READY; sign both sheets | Owner | Nothing |
| 5 | `drive_c1.py --phase window --execute` | **Approval 2** | See below |
| 6 | `cc_env.ps1`, tunnel, restart Next | Owner | `.env.local` only |
| 7 | Same turns again; sign acceptance | Owner | Up to 5 provider requests |
| 8 | 48-hour return window | Owner, with checks at 24 and 48 hours | Nothing |

**Step 3 must follow step 2.** Whatever the baseline turns move is what later comparisons treat as normal growth.

## 1. Backups

| Item | Choice |
|---|---|
| Schedule | `lilith-01-daily`: daily at 18:00 UTC, kept 30 days, on `lilith-01` only |
| Location | `asia` multi-region, so it survives the loss of the host or one region |
| If the disk is deleted | Snapshots are kept |
| Cost | Under $1 a month at today's 814 MB of changes |

**Restore layers, fastest first:**

| Layer | Use | Loses | Evidence |
|---|---|---|---|
| `drive_c1.py --phase return` | Any trigger, any time | nothing | Copy: 1 second, data equal. Logic: simulation |
| Snapshot to a disk, read data from it | Recover a file or table | nothing live | **G3-B, on a real PROD snapshot:** four databases intact, every table digest equal |
| `restore_disk.ps1` | Host unrecoverable, within 48 hours | everything after that snapshot | **Scripted gcloud only** |

**Limits, stated plainly:**

- `restore_disk.ps1` has never swapped a real boot disk, and PROD has never been rebooted from a snapshot. It's the last resort, for a change with no schema migration and its own 1-second return. I don't recommend a drill before Cutover 1.
- Snapshots stay in the same Google project, so the owner account can delete them. It covers host and region loss, not account compromise.
- Snapshots keep erased data for 30 days. That holds R-13's limit: erasure is never claimed complete.

## 2. Deployer and firewall

| Item | Now | After |
|---|---|---|
| Deployer login | none | `compute.osAdminLogin` on `lilith-01` only |
| Deployer tunnel | none | `lilith-01` only, **port 22 only** (`destination.port == 22`) |
| Project-wide tunnel or login | removed by G3-A | stays removed. `restore_deployer.ps1` is not used |
| `lilith-api-iap` | every VM in `lilith-vpc` | VMs tagged `lilith-vm` |

**The firewall step can't separate DEV from PROD:** both carry `lilith-vm`, and both keep their route. It stops a new VM inheriting port 8765. Who can reach PROD's port is decided by tunnel IAM, and what they get is decided by the credential. A separate PROD tag would add a DEV change for no gain.

The deployer's first real use is the dispatch. If its access is wrong, `deploy.yml` fails before installing, and the window returns.

**Undo:** `undo_prepare.ps1 -Confirm UNDO-PREPARE` reverses every step and keeps any snapshot already taken.

## 3. Command Center

Proxy mode only. `direct` mode can't hold a credential, and `cc_env.ps1` refuses it. The owner runs it after the window: it copies both tokens from PROD into the gitignored `.env.local`, and prints neither.

```bash
gcloud compute start-iap-tunnel lilith-01 8765 --local-host-port=localhost:8765 --zone=asia-southeast1-b --project=lilith-agent-260823-27389
```

`LILITH_API_URL` must point at that local port. **Not tested end to end offline:** the header code is on main, and the first real check is the post-window baseline.

## 4. The window

| Step | Does | On failure |
|---|---|---|
| `w0` | Fingerprints, digests twice 130 seconds apart | Nothing changed; stop |
| `snap` | `lilith-01-cutover1-<date>`, READY | Nothing changed; stop |
| `w1` | Tokens (root, 600), open drop-in. No restart | Return |
| `deploy` | `deploy.yml` at `75ca0db`. Backs up, installs, restarts, rolls itself back on a failed health check | Return |
| `w2` | New code, backup digest, reads still open | Return |
| `w3` | Enforce writes, one restart. Stranger 401; owner and router reach validation | Return |
| `w4` | Enforce reads and focus, one restart. 11 routes refuse a stranger; router reads 200 | Return |
| `w5` | Data, identity, settings, gateway PID, units, no token in journal | Return |

**One failure, one return, no retry.** A failed return stops and reports. Lost transport reads status once. The driver refuses to start if `main` has moved from `75ca0db`, so **nothing merges to main between sealing and the window.**

**Expected interruption:** Core API restarts three times, a few seconds each. The gateway isn't restarted.

## 5. The 48-hour return window

Starts when `w5` passes; `RETURN-WINDOW.txt` holds the close.

| Return | When | Loses |
|---|---|---|
| `drive_c1.py --phase return` | Any time, even after 48 hours | Nothing: same database, previous code, routes open again |
| `restore_disk.ps1` | Only inside 48 hours; refuses afterwards | Everything since the snapshot |

**Triggers,** from `ROLLOUT-PLAN.md`: an identity failure on the fixed prompts, a row lost or changed unexpectedly, a 401 on a real caller that isn't understood, grounding silently gone, a provider fallback not in the plan, a write from a GET.

**Checks at 24 and 48 hours:** `sudo -n bash /var/tmp/c1/guest_c1.sh w5` is read-only. A table reported `UNEXPECTED` after real conversation isn't automatically a fault: read it before deciding. Identity, schema and lost rows are.

## Evidence

| Check | Result | Kind |
|---|---|---|
| `test_drive_c1.py` | 22/22 | Driver order, recovery, approvals, deploy, on a fake host |
| `test_live_compare.py` | 9/9 | Real SQLite in WAL mode, with writers open |
| `sim_c1.sh` | 50/50 | Real guest script as root in Linux, stand-in Core API, real databases |
| `test_cloud.ps1` | 58/58 | Real PowerShell against a scripted gcloud |
| `deploy.yml`'s unit suite | 328 run, 36 skipped, 5 modules unimportable here | Local venv lacks `cryptography`. CI passed the full suite at `75ca0db` |
| Real `app.py`, every auth stage | 9/9 | From the DEV auth package; `app.py` is byte-identical |
| DEV auth window | PASS | Real host, 2026-10-31 |
| G3-B | PASS | Real data, on a copy |

**Not run anywhere:** this package against real PROD or real GCP. Simulation has missed real-host defects before, so the preflight is a real read-only pass ahead of the window, and it's where a wrong assumption about PROD should surface.
