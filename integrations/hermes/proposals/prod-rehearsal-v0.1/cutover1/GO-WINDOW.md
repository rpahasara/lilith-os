# OWNER GO: Cutover 1 window (NOT APPROVED, NOT RUN)

**Approval 2 of 2.** Needs, all first: the five baseline turns sent after the preflight, one scheduled snapshot READY, `BASELINE-SIGNED.txt`, `ACCEPTANCE-SIGNED.txt`.

| Step | Changes |
|---|---|
| `w0` | Nothing. Fingerprints and digests |
| Snapshot | New `lilith-01-cutover1-<date>`, kept until you decide |
| `w1` | Token file, open drop-in |
| Deploy | `deploy.yml` at `75ca0db`: `app.py` to `53dfae2a` |
| `w3`, `w4` | Enforce writes, then reads. Core API restarts about three times in all, a few seconds each |
| `w5` | Nothing. Comparison |

The gateway isn't restarted. No provider request is made by the window.

**When:** not between 02:15 and 03:00 UTC, because of the morning brief. **`main` must stay at `75ca0db`,** so #311 and everything else stay unmerged until `w5` passes.

**Failure:** one return to `bb0a4139`, with no retry; a failed return stops and reports.

**Run:** write this manifest's digest to `APPROVED_WINDOW`, then `python -B drive_c1.py --phase window --execute`.
