# PROD Hermes timezone → Asia/Colombo: proposal and controlled change procedure (v0.1)

**Status: PROPOSED; not executed.** Preparation and read-only verification only. The change needs the owner's separate
authorization. PR #412 (nightly-review conversation dates) is gated separately and is **not** part of this change.

## What changes

| | Before | After |
| --- | --- | --- |
| `~/.hermes/config.yaml` | no `timezone` key (sha `a6f340f2…`) | one appended top-level line `timezone: Asia/Colombo`; every other key provably identical |
| Nightly review `e161234245f3` | `30 16 * * *` in UTC | `0 22 * * *` in Asia/Colombo |
| **Nightly review instant** | **16:30Z = 22:00 Colombo** | **16:30Z = 22:00 Colombo (unchanged)** |

Nothing else is edited. No other job, reminder, memory, Core API, router, unit, credential or systemd timer is touched.

## Read-only PROD inventory (2026-11-10, lilith-01)

| | |
| --- | --- |
| Hermes | 0.20.5 (pyproject, dist), Python 3.11.16, clean git checkout |
| Timezone sources | `hermes_time.py` `3f4ee146…`, `cron/jobs.py` `edf2469d…`, `cron/scheduler.py` `fe1defe7…`, `agent/system_prompt.py` `1d1c1bfb…`, `gateway/message_timestamps.py` `daa620ef…`, `agent/context_compressor.py` `2180855b…`. All **byte-identical** to the DEV release used for the rehearsal |
| `gateway/run.py` | `394e3c35…` = the repo mirror `deploy/prod/hermes_gateway/run.py`. It bridges `config.yaml timezone` into `HERMES_TIMEZONE` |
| Current zone | host `Etc/UTC`; no `timezone` key; no `HERMES_TIMEZONE`/`TZ` in the gateway; no managed-config override |
| Gateway | `hermes-gateway` active since 2026-11-09 13:15Z, PID 81534, `Restart=always`, no `ExecStartPre` |
| Core API | `lilith-os-api` active, PID 18196 (not touched by this change) |
| Deploys | the PROD deploy is `workflow_dispatch` only and never writes `config.yaml` or `cron/jobs.json`, so a later deploy cannot silently revert the zone |
| Scheduler | heartbeat 19 s old; `executions.db` healthy |

**Cron jobs** (every stored timestamp is zone-aware):

| Job | Schedule | Kind | Delivery | Next run (before) |
| --- | --- | --- | --- | --- |
| nightly review `e161234245f3` | `30 16 * * *` | agent + script | telegram | daily 16:30Z |
| proposal snapshot `f56407e4cef8` | `*/10 * * * *` | no-agent | local | every :x0 UTC |
| commitment sync `5365cfb456d4` | `* * * * *` | no-agent | local | every minute |
| "Drink water reminder" `7e481025f885` | once, `2026-11-09T07:08:18+00:00` | completed, disabled | origin | none |

**Pending reminders: 0. Open commitments: 0** (one `commitment.once`, COMPLETED). **Timezone-less jobs or reminders: 0.**

**systemd timers** (host clock; Hermes' setting does not apply):
- `lilith-morning-brief` `OnCalendar=*-*-* 08:00:00 Asia/Colombo` (02:30Z; explicit zone, unchanged).
- gmail and agenda every 10 min; career and meeting-prep every 15 min.

## Effect on each schedule (expected UTC instants)

| Item | Before | After | Change |
| --- | --- | --- | --- |
| Nightly review | 16:30Z daily | `22:00+05:30` = **16:30Z** daily | none |
| Proposal snapshot | :00, :10, … UTC | the same instants (+05:30 is three whole 10-minute steps) | none |
| Commitment sync | every minute | every minute | none |
| Completed one-shot | n/a | n/a | none (disabled, zone-aware) |
| Morning brief (systemd) | 02:30Z | 02:30Z | none |
| **New** reminders given without a zone ("remind me at 20:00") | read as 20:00 **UTC** = 01:30 Colombo next day | read as 20:00 **Colombo** = 14:30Z | **intended fix**; affects new reminders only |
| Agent "Conversation started" line | UTC date | Colombo date, e.g. "(Asia/Colombo, +0530, UTC+05:30)" | date flips at Colombo midnight (18:30Z) |
| Compaction summary date | UTC date | Colombo date | follows the zone |
| Stored message timestamps | epoch | epoch | none (rehearsal S8) |

Sri Lanka has no daylight saving: +05:30 all year, so 22:00 Colombo is 16:30Z every day (tested for all 12 months).

## Evidence

- **DEV sandbox rehearsal 2026-11-10** (`docs/engineering/prod-work-note-2026-11-07.md`, PR #412 branch; DEV release code, synthetic jobs): 14/14 PASS.
  - **S2:** the zone without the schedule change drifts the review to 11:00Z from day 2. This is why both change together.
  - **S3–S5:** update or direct edit keeps 16:30Z daily; the other jobs stay on time (319/319, 3186/3186); no double run.
  - **S6:** an unzoned 20:00 one-shot fires once at 14:30Z.
  - **S7:** the agent's date line flips correctly at local midnight.
  - **S8:** stored timestamps unchanged.
  - **S10–S11:** after a restart, one catch-up at most, and none if the review time was not crossed.
- **Hermes' own tests:** timezone plus 9 scheduler suites, 243/243 with no zone and 243/243 under Asia/Colombo; full `tests/cron` 878 pass (2 order-dependent media failures, unrelated).
- **DEV↔PROD source identity:** the four timezone files are hash-identical, and two more were checked here.
- **PROD read-only, with these tools** (`tz_ops.py`, PROD's own interpreter and Hermes code):
  - `jobs-plan` computed `0 22 * * *` under Asia/Colombo → next run `2026-11-10T22:00:00+05:30` = `16:30:00Z` (`same_instant: true`);
  - `jobs-inspect` matched the inventory;
  - `datecheck` showed today's line `Conversation started: Tuesday, November 10, 2026 (UTC, UTC+00:00)`;
  - `precheck` refused inside the 16:00–17:00Z blackout, as designed;
  - at 17:01Z, the full **`precheck` → `TZ_PRECHECK_PASS`**: planned review `2026-11-11T22:00:00+05:30` = `16:30:00Z`;
    the 2026-11-10 review ran once at 16:30:56Z (status ok), next 2026-11-11 16:30Z;
  - nothing was written (`config.yaml` unchanged); temporary files were under `/run` and removed.
- **Offline:** `test_tz_ops.py` 10/10 (config append, refusals, job-set guard, the 16:30Z instant, no DST).
- **End-to-end rehearsal** of the real scripts with root/lilith ownership: see below.

## Change window

Requirements:
- **not** 16:00–17:00Z (review at 16:30Z) and **not** 02:00–03:00Z (morning brief at 02:30Z); `tz_window.sh` enforces both;
- **no** PROD deploy dispatched or running, and no DEV deploy running (operator checks GitHub immediately before);
- no FORGET or erasure work, no canonical-memory work, no other release in the same window;
- **no** #412 deployment in the same window.

**Proposed:** any time outside the blackouts. 04:00–15:30Z is the widest gap.

**Outage:** about 20 s. Gateway stop to active takes a few seconds, plus platform reconnects. Measured on PROD's
2026-11-09 13:15:26Z restart: Telegram and Discord connected at +15 s, console at +16 s, "Gateway running with 3
platform(s)" at +16 s. Messages sent during it are delivered on reconnect. Commitment sync misses about one
minute and catches up once (S10).

## Exact procedure

Root on `lilith-01`, from Git at the merge of this proposal. Copy `tz_ops.py` and `tz_window.sh` into a root-only 0700
directory and check their SHA-256 against the PR.

```bash
bash tz_window.sh precheck            # read-only; must end TZ_PRECHECK_PASS
bash tz_window.sh change              # prepare -> stop -> config + review -> start + proof; ends TZ_CHANGED backup=/root/tz-colombo-<ts>
bash tz_window.sh verify h60 colombo  # at +60 s   (exit 0 only if V1-V7 all pass)
bash tz_window.sh verify h600 colombo # at +10 min
bash tz_window.sh verify review colombo   # after the next 16:30Z review, plus the review's last_run_at
```

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | done |
| `1` | refused or failed, with nothing changed, or the previous state restored, verified and **running** (`TZ_FAIL`, `TZ_FAIL_RECOVERED`, `TZ_FAIL_ROLLED_BACK`) |
| `3` | `TZ_ESCALATE`: files could not be verified, so the gateway is **left stopped** for a human |

**`change`, step by step:**

1. **Precheck**, read-only; any difference refuses:
   - root, on `lilith-01`, outside the blackouts;
   - host zone UTC (with no Hermes zone, Hermes uses the host zone; the "before" state assumes PROD's `Etc/UTC`);
   - the four source hashes;
   - `config.yaml` = `a6f340f2…`, `lilith:lilith 0600`, no `timezone` key;
   - the gateway is running and was started with no zone in its environment;
   - the job set is exactly the inventory (three enabled recurring jobs, nothing else enabled, all timestamps
     zone-aware);
   - `jobs-plan` gives 16:30Z;
   - the live scheduler ran commitment sync in the last 180 s, in UTC;
   - Core API active; disk; `/root` root 0700.
2. **Prepare, with the gateway still running.** A failure here changes nothing.
   - Create the backup directory `/root/tz-colombo-<ts>` (root 0700). Only root writes there.
   - Back up `config.yaml` (root 0600) and hash-check it against `a6f340f2…`.
   - `tz_ops.py config-render` (as `lilith`, read-only) prints the new config to stdout; **root** writes
     `config.new`.
   - `config-validate` reads `config.new` on stdin and proves it is the live config plus exactly
     `timezone: Asia/Colombo`.

   `tz_ops.py` runs from a fresh `/run/tz-colombo-ops.*` directory, root-owned 0755 with the file 0644: `lilith` can
   read it but not change it. It is removed on exit.
3. **Stop** the gateway, and wait until MainPID is 0. If it does not stop: refuse; nothing changed. Then record the
   checksums of `config.yaml` and `jobs.json`.
4. **Back up `jobs.json`** (root 0600), compare it with the recorded checksum, and write and check `SHA256SUMS`.
   - If this fails, nothing has been modified: confirm both files still have their recorded checksums, start the
     gateway, and prove it. **`TZ_FAIL_RECOVERED`**, exit 1.
5. **Install the config**: `config.new` → `config.yaml` (`lilith:lilith 0600`, atomic), then confirm the checksum and
   `{"timezone": "Asia/Colombo"}`.
6. **Move the review**: `tz_ops.py jobs-apply` (as `lilith`, `HERMES_TIMEZONE=Asia/Colombo`) calls Hermes' own
   `update_job(e161234245f3, {"schedule": "0 22 * * *"})`. It asserts:
   - `expr` = `0 22 * * *`;
   - next run at `+05:30`, on the next 16:30Z;
   - every other job identical.
7. **Any failure in steps 5–6:** restore both files exactly from the backup, verify their checksums, start the gateway
   and prove it. **`TZ_FAIL_RECOVERED`**, exit 1.
   - If the restore cannot be verified: **`TZ_ESCALATE`**, exit 3, gateway left stopped.
8. **Start, and prove it.** `systemctl` accepting the start is never enough. All of these must hold:
   - active/running within 90 s;
   - the same MainPID and no extra restart after 10 s;
   - `✓ telegram connected`, `✓ discord connected`, `✓ lilith_os connected` and `Gateway running with 3 platform(s)`
     logged **after this start's timestamp**;
   - the **live scheduler** has run commitment sync since this start and written its next run at `+05:30`. This is the
     only direct evidence of the zone the running gateway uses: Hermes sets `HERMES_TIMEZONE` inside the process, so
     `/proc/<pid>/environ` never shows it.

   If the proof fails, the **documented rollback** runs automatically: stop, exact config restore, review back to UTC,
   start, prove it in UTC. **`TZ_FAIL_ROLLED_BACK`**, exit 1. If the rollback cannot be verified: **`TZ_ESCALATE`**,
   exit 3.

## Post-change checks and failure criteria

`tz_window.sh verify LABEL colombo`, at +60 s, at +10 min, and after the next review. It **exits nonzero if any check
fails**.

| # | Pass | Failure response |
| --- | --- | --- |
| V1 | gateway active/running | rollback |
| V2 | `config.yaml` timezone Asia/Colombo; the live scheduler has run commitment sync since the current start and written its next run at `+05:30` (polls up to 150 s) | rollback |
| V3 | `datecheck`: zone Asia/Colombo; date line `(Asia/Colombo, +0530, UTC+05:30)` | rollback |
| V4 | review `0 22 * * *`, next run `…T22:00:00+05:30` = `…T16:30:00Z` | rollback |
| V5 | commitment sync under 150 s ago and snapshot under 700 s ago, both `ok` | investigate, then rollback |
| V6 | `✓ telegram/discord/lilith_os connected` and `Gateway running with 3 platform(s)` **after the current start** (systemd `ActiveEnterTimestamp`); an earlier start's lines never count | investigate (not zone-related) |
| V7 | Core API active (untouched) | investigate |
| Next review | runs once at 16:30Z (`last_run_at` ≈ 16:30Z, ok), not at 11:00Z, not twice | rollback |

## Rollback (idempotent; outside the blackouts)

```bash
bash tz_window.sh rollback /root/tz-colombo-<ts>
```

1. **Refuses unless** the config holds Asia/Colombo and the backup's `SHA256SUMS` verifies.
2. **Stop** the gateway.
3. **Restore `config.yaml` exactly** (hash `a6f340f2…`).
4. **Move the review back:** `tz_ops.py jobs-revert` (Hermes' `update_job` → `30 16 * * *` in UTC; asserts next run
   16:30Z and every other job unchanged). The scheduler's live counters are kept. If `jobs-revert` fails, `jobs.json` is
   restored exactly from the backup (checksum-verified) instead.
5. **Start and prove**, in UTC.

Any unverifiable step → **`TZ_ESCALATE`**, exit 3, gateway left stopped.

**Known Hermes behaviour on rollback:** a recurring job whose stored next run carries the old `+05:30` offset with a
still-future wall clock is recomputed rather than fired (`cron.jobs._stored_wall_clock_is_future`). So commitment sync
skips one minute, and the snapshot may skip one 10-minute occurrence. The proof allows 150 s for this. The review is set
explicitly in both directions and never skips. The forward change does not hit this: the old `+00:00` wall clocks are
in the past under Colombo.

## End-to-end rehearsal

`rehearse_tz_window.sh` runs the real `tz_window.sh` and `tz_ops.py` end to end:
- **Sandbox:** WSL Ubuntu 24.04 as root, in private mount **and** hostname namespaces with the hostname `lilith-01`;
  overlays on `/etc /home /root /opt`; a fresh `/run`; host zone `Etc/UTC` and `/root` 0700, as on PROD.
- **Hermes:** DEV's Hermes 0.20.5 release, whose timezone and scheduler sources are byte-identical to PROD's.
- **Ownership:** a real `lilith` user owns `~/.hermes` with PROD's modes.
- **Jobs:** PROD's job IDs, created through Hermes' own `create_job`.
- **Gateway stand-in:** bridges `config.yaml`'s zone as `run.py` does, logs platform connections in gateway.run's
  format, and runs Hermes' real scheduler loop. Nothing is executed or delivered.
- **`systemctl` stand-in:** bind-mounted inside the namespace.

Cases:
- **Permissions:** `lilith` cannot write the root 0700 backup directory (the original defect); the script refuses to
  run as `lilith`.
- **Precheck refusals:** blackouts (16:20, 02:10), a changed `config.yaml`, an extra enabled reminder, the Core API
  down, the gateway down.
- **An injected failure at every boundary:**
  - while preparing → nothing changed, gateway never stopped (same PID);
  - after stop, and on `jobs.json` backup failure → nothing modified, restart proven;
  - after backup, after config, at `jobs-apply`, after jobs → exact restore verified, restart proven;
  - at start → rollback, proven in UTC;
  - **a gateway that dies on the new config after systemd accepted the start** → rollback, proven in UTC;
  - **running but no platform evidence from this start** → rollback;
  - **an unverifiable backup during recovery** → `TZ_ESCALATE`, exit 3, gateway left stopped.
- **Backups:** every backup directory is root 0700 with root 0600 files, unreadable to `lilith`; no ops directories
  left in `/run`.
- **Success:**
  - `TZ_CHANGED`, with the gateway proven in the new zone;
  - `config.yaml` = the original plus one line, `lilith` 0600;
  - review `0 22 * * *` at `+05:30` = 16:30Z; snapshot and sync unchanged; the live scheduler writes `+05:30`; the
    completed reminder untouched.
- **`verify`:**
  - passes `colombo`;
  - **fails with a nonzero exit** for `utc`, with the gateway down (V1), and after a start that logged no platforms
    (V6, an earlier start's lines do not count);
  - after a plain restart, the zone and the 16:30Z review persist.
- **A second `change` refuses.**
- **Rollback:**
  - refuses inside the blackout;
  - an unverifiable restore → `TZ_ESCALATE`;
  - `jobs-revert` failing → exact `jobs.json` fallback, proven in UTC;
  - the documented path → config byte-identical to the original, review `30 16` UTC = 16:30Z, `verify utc` passes;
  - change again → rollback again.

**Result (2026-11-10, these exact bytes):** **40/40 PASS, `REHEARSAL_RESULT PASS`**.
- Script hashes: `tz_window.sh` `d632029f…`, `tz_ops.py` `0bb16caa…`, `rehearse_tz_window.sh` `672febb0…`.
- The rehearsal also corrected several assumptions:
  - V2 must use live-scheduler evidence, not `/proc` environ;
  - backups must be root-owned (`cp -p` kept `lilith`);
  - rollback must allow for Hermes' one-occurrence skip after a zone change;
  - with no Hermes zone, Hermes uses the **host** zone, so the precheck pins PROD's host to UTC.

**PROD read-only `precheck` with these bytes** (2026-11-10 18:47Z): **`TZ_PRECHECK_PASS`** (host UTC, `/root` 0700,
live scheduler in UTC). `config.yaml` and the gateway PID were unchanged; temporary files removed.

## Not in this change

- #412 (separately gated).
- Any reminder rescheduling: none pending; existing timestamps are zone-aware and keep their instants.
- systemd timers, the Core API, memory or canonical authority, DEV.
- Timeline stays shadow; P-5 stays off.

## Recommendation

**GO**, subject to the window rules and a `precheck` that ends `TZ_PRECHECK_PASS` immediately before `change`.

Basis:
- two edits, rehearsed end to end on byte-identical Hermes code with PROD's ownership model;
- every failure path restores and proves the previous state, or stops for a human;
- the only wall-clock job keeps 16:30Z;
- nothing timezone-less to reinterpret.

Remaining risks for the owner:
1. **About 20 s of messaging downtime** for the restart (about 2 min if a recovery or rollback runs).
2. **Rollback skips about one minute of commitment sync** and possibly one snapshot occurrence (Hermes behaviour,
   harmless).
3. **The rehearsal's gateway is a stand-in.** It runs Hermes' real scheduler and config bridge, but not the real
   messaging gateway. Platform reconnection on PROD is proven live by step 8 and V6, and a failure there rolls back
   automatically.
4. **A `TZ_ESCALATE` leaves Hermes messaging down until a human acts.** It happens only if a backup or restore cannot be
   verified.
