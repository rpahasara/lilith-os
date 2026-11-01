# OWNER GO: preflight, second attempt (NOT APPROVED, NOT RUN)

**Result of the first attempt, 2026-11-01:** preparation PASS under manifest `3191ffe6`. The preflight stopped at its host guard, before reading anything: PROD's `hostname` returns the full domain name, and the guard compared it with `lilith-01`. The simulation's stub returned the short form, so it couldn't show this.

**The correction, one line in `guest_c1.sh`:** the guard reads `hostname -s`. The stub now returns PROD's real form.

**This approval runs:**

1. `restage.ps1 -Confirm RESTAGE-CUTOVER1`: replaces the three guest files in `/var/tmp/c1`, checked by digest, and archives the spent attempt as `raw-attempt1`.
2. `drive_c1.py --phase preflight --execute`: the read-only review, once, including read-only digests of all four databases as lilith. Counts and digests only, no rows.

It changes no IAM, firewall or schedule, and no LILITH file, service or database. No deployment and no provider request.

**Before it runs:** write this manifest's digest to `APPROVED_PREPARE`. The old approval is refused.

**Failure:** stops with no retry. `undo_prepare.ps1` stays available, and nothing here needs it.
