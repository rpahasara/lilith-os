# G3-B result: PASS, within Cutover 1 scope

One rehearsal on a read-only copy of the PROD snapshot, under manifest `eef1b3ec`, on 2026-10-31 from 19:20:08Z to 19:24:54Z by the VM's clock. No retries. PROD's runtime wasn't changed and no provider request was made.

## Proven

| Check | Result |
|---|---|
| Source | stayed read-only; only allow-listed files copied; no credential names |
| PROD code | `app.py` is `bb0a4139` |
| Data | `state.db` 19,854 rows, `lilith.db` 305, `cognitive_memory.db` 19, `privacy_governance.db` 2; integrity ok on all four |
| Control | old code plus one maintenance tick changed nothing |
| Target code, `53dfae2a` | router reads 200; stranger read and write 401; owner read 200 |
| After target code | every table digest, `SOUL.md` and `USER.md` equal to baseline |
| **Rollback** | **1 second;** reads 200; data equal to baseline |
| Log | no token |

All four checkpoint files share digest `ab8c0ff0608fc69a`.

## Not proven

- **Live behaviour.** No Hermes, router process, provider or reply turn ran. Nothing here shows the same LILITH replies.
- **A successful router write.** Router reads were exercised; writes were only checked as refused for a stranger.
- **PROD's timing, and a whole-host restore.** The copy never booted.
- **Cutover 2.** No seven-lane code ran.

## Cleanup

Run once under manifest `eab24c31` on 2026-11-01, and verified directly afterwards. The copy disk, the VM, its boot disk, the synthetic disk, the two firewall rules, the subnet and the network are gone. All three snapshots remain READY with their recorded ids, and the checkpoint files are kept locally.

**`lilith-01-rehearsal-20261101` still holds all of PROD's data** until its own decision, no later than 2026-12-01. The deployer stays narrowed to `roles/compute.viewer`, so PROD deploys are blocked until Cutover 1 grants `lilith-01`-only access.
