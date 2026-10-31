# Detached driver: review of the p1 run

**Finding:** the p1 runbook said foreground, and the driver ran detached so a tool timeout could not stop it partway. **This didn't change the p1 result,** which is proven by its own evidence. But the review found three gaps in the driver that exist in either mode, and detached running makes two of them matter more. All three are fixed in `package/drive_e1.py`. **p1 wasn't rerun and its installed release wasn't touched.**

## Effect on each question

| Question | p1 run | Gap, in either mode | e1 driver |
|---|---|---|---|
| **Run completion evidence** | Sound. Every step has its own `raw/*.out`, the driver printed `DRIVE_COMPLETE`, and independent read-only checks agreed | The only summary was stdout, in whatever file it was redirected to | `raw/drive.journal`, flushed to disk on every line. `BEGIN` and `END` around each step, a verdict, then `RESULT` last |
| **Transport loss** | Not exercised | None. Handled per step by the same read-only probe in both modes | Unchanged |
| **Telling success from partial completion** | Not exercised: it finished | **Real gap.** A dead driver and a running driver looked the same: no result line yet | `--status` says `RUNNING`, `FINISHED` or `INTERRUPTED`, and names the open step. It's decided by an OS lock, so a reused process id can't fool it, and it never touches the host |
| **Automatic rollback** | Not exercised | **Real limit, and unchanged.** The rollback lives in the driver process. If that process dies, nothing rolls back, and DEV can be left with the gateway stopped | Stated, not hidden. `INTERRUPTED` means stop, read `status_ro.sh` once, and take it to the owner. **Automatic resume would be improvising on an unknown state** |
| **Duplicate execution** | Ran once | **Real gap.** A second launch would be stopped by S1's window directory, but it would then print `DRIVE_NOCHANGE`, which is false while the first run is working. Two launches could also both run P0 | `raw/drive.started` is created exclusively and never removed, and `raw/drive.lock` is held for the process's life. A second launch does nothing and says `DRIVE_REFUSED_RUNNING` or `DRIVE_REFUSED_ALREADY_STARTED` |

## Which mode is right

**Detached, and the runbook now says so.** Foreground has no advantage: a timeout kills the same process and leaves the same unknown state, with less on disk. Killing it mid-window is the failure to avoid.

## Evidence

`package/test_drive_e1.py`, 24/24 on a scripted fake host: the 13 recovery cases carried over from p1, plus 11 for this review, including a driver that dies mid-step, a real second process refused by the lock, and the OS freeing the lock when that process is killed.

**Not proven:** a power cut, or a driver killed on a real host. Neither has happened.

## p1's own package

It stays as run, as the record of what happened. Its `RUNBOOK.md` isn't edited, because that would rewrite evidence.
