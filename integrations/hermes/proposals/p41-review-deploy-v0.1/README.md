# #412 PROD deployment procedure: P4-1 conversation dates in the nightly review

**Status:** prepared and rehearsed; **not executed.** It needs:
- the Asia/Colombo migration's final acceptance (the 2026-11-11 16:30Z review);
- #412 merged after that;
- a separate owner GO.

## What changes

One file: `~/.hermes/scripts/owner_memory_review.py`, from `4324525d…` (main `7365bfd`, live since 2026-11-09) to
`e6ec02a1…` (#412).
- **No restart:** Hermes cron reads the script fresh on every run.
- **No config, schema, store, job or unit change.**
- **Dependants unchanged but checked:**
  - `owner_memory_snapshot.py` (every 10 min, `runpy` import of the review script);
  - `commitment_sync.py` (every minute, `from owner_memory_review import …`). That import **fails closed silently**, so
    its "ok" status proves nothing; the tool imports the module itself.

Live file hashes verified read-only on 2026-11-11 04:25Z: review `4324525d…`, snapshot `99f0fd81…`, commitment sync
`6527dd63…`, all identical to main.

## Procedure (root on the Contabo PROD host `vmi3753642`)

Run outside 16:00–17:00Z. The candidate is the file from the #412 merge commit, hash-checked.

```bash
bash review_window.sh precheck /root/p41-review/owner_memory_review.py   # REVIEW_PRECHECK_PASS
bash review_window.sh install  /root/p41-review/owner_memory_review.py   # REVIEW_INSTALLED e6ec02a1… backup=/var/backups/lilith-review/<ts>
bash review_window.sh verify                                             # after the next snapshot run (<= 10 min)
bash review_window.sh verify --dry-run                                   # optional; see below
```

**`precheck`** refuses unless all of these hold:
- outside the blackout;
- the candidate is exactly `e6ec02a1…`;
- the live file is the inventoried `4324525d…` (`lilith:lilith 0644`);
- both dependants match their pins;
- Hermes' timezone is Asia/Colombo;
- the review job is `0 22 * * *` running `owner_memory_review.py`, and the snapshot job's last status is ok;
- the gateway is active.

**`install`:**
1. Back up the live file to `/var/backups/lilith-review/<ts>/` (root 0700, file root 0600), hash-checked.
2. Swap atomically: install as a temporary file next to the target, then rename. The result is `lilith:lilith 0644`.
3. Run the **import check** as `lilith` with PROD's interpreter:
   - the module imports;
   - `review_timezone()` gives Asia/Colombo;
   - both dependants' exact import forms work.

Any failure restores the exact previous file and import-checks it: `REVIEW_FAIL_RESTORED`, exit 1. If the restore
cannot be verified: `REVIEW_ESCALATE`, exit 3.

**`verify`** exits nonzero on any failure:

| # | Check |
| --- | --- |
| R1 | the live file is `e6ec02a1…`, `lilith 0644` |
| R2 | the import check passes |
| R3 | snapshot, commitment-sync and review jobs all report `ok` |
| R4 | `--dry-run` only (below) |

**`--dry-run`** builds tonight's review context **in memory** with `snapshot()` stubbed, so nothing is written. It
prints **counts only**: zone header, day markers, owner and LILITH lines, repeats noted, guidance present. It reads the
owner conversation in-process, the same way the nightly review does, so it runs only if the deploy GO includes it.

## Rollback

```bash
bash review_window.sh rollback /var/backups/lilith-review/<ts>
```

It restores the exact `4324525d…` file, verified, and import-checks it. No restart.

## After deployment

1. **The next real review**, 16:30Z = 22:00 Colombo:
   - the job's `last_run_at` is about 16:30Z and `ok`;
   - it ran exactly once (`executions.db`);
   - the cron output shows day markers in Asia/Colombo. Check the count of `--- said on` lines only, never the text.
2. **After at least 3 reviews with proposals:** the counts-only coverage measurement (`p41-event-date-coverage-v0.1`,
   PR #418), with a separate owner OK.

## Rehearsal

`rehearse_review_window.sh` (WSL, private mount and hostname namespaces as `vmi3753642`, real `lilith` ownership,
main's live scripts plus the #412 candidate, a stand-in scheduler that really runs `owner_memory_snapshot.py` and
commitment sync's import): **19/19 PASS**.

It found one defect, now fixed: the import check required `review_timezone`, which the previous file lacks. Every
restore therefore "failed" verification and would have escalated.

Pins are tested against the real files (`test_review_window.py`, 4/4).
