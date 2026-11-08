# OWNER GO: Cutover 1 preparation (NOT APPROVED, NOT RUN)

**Approval 1 of 2.** Runs `prepare.ps1`, then the read-only preflight. No LILITH file, service or database changes. No deployment and no provider request.

| Change | Reversible |
|---|---|
| `lilith-api-iap` targets the `lilith-vm` tag | Yes. Both hosts keep their route |
| Deployer: login on `lilith-01`, tunnel to port 22 there | Yes |
| New schedule `lilith-01-daily`: every day, 30 days, `asia`, on `lilith-01` | Yes. **Each snapshot holds real data** |
| Guest files in `/var/tmp/c1`; digests in `/root/cutover1-20261101` | Yes |

**The deployer regains root on PROD,** on one host, through the same `main`-only dispatch. PROD deploys stay blocked until this runs.

**Your approval also decides:** daily snapshots with 30-day retention, stored in `asia`. Existing snapshots aren't changed.

**The preflight reads** identity and database digests on real PROD, including `state.db`, as lilith, read-only, as G3-B did on the copy: counts and digests, no rows.

**Stops:** anything not as recorded stops before the first change, with no retry. A later failure stops and is reported; `undo_prepare.ps1` reverses it, on your word.

**Evidence:** see `RUNBOOK.md`. Not yet run against real GCP or real PROD.
