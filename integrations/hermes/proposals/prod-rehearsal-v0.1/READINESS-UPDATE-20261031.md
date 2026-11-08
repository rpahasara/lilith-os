# Readiness update, after the DEV auth window

Adds to `dev-exit-v0.1/MINIMUM-FOUNDATION.md`, which stays as merged: editing a merged file would deploy.

**1 of 39 is done, A5. 14 are partial, 2 are proposed, and 22 are open.**

| Item | Was | Now |
|---|---|---|
| A19 write auth | open | **partial:** enforced on DEV, not PROD |
| A20 read auth | open | **partial:** enforced on DEV, not PROD |
| A34 rollback tested live | open | **partial:** Core API return and forward on DEV, plus 2 real recoveries. Timed at 2 seconds each way. No cognition release has returned live |

**Cutover 1 blockers still open:** PROD baseline, rehearsal, off-host backups with a proven restore, firewall and deployer narrowing, signed acceptance.

**Rehearsal needs four things:** approval of G1, approval of G2, the Privacy decision for G3, and owner review of the 12 identity prompts. Snapshot retention is a fifth decision before G1 if a new snapshot should be kept beyond the rehearsal.

**R-13 still holds:** no OAuth reactivation, and no new real data capture.
