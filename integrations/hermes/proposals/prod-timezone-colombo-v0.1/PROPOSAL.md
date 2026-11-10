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
  - nothing was written (`config.yaml` unchanged); temporary files were under `/run` and removed.
- **Offline:** `test_tz_ops.py` 10/10 (config append, refusals, job-set guard, the 16:30Z instant, no DST).

## Change window

Requirements:
- **not** 16:00–17:00Z (review at 16:30Z) and **not** 02:00–03:00Z (morning brief at 02:30Z); `tz_window.sh` enforces both;
- **no** PROD deploy dispatched or running, and no DEV deploy running (operator checks GitHub immediately before);
- no FORGET or erasure work, no canonical-memory work, no other release in the same window;
- **no** #412 deployment in the same window.

**Proposed:** any time outside the blackouts. 04:00–15:30Z is the widest gap.

**Outage:** gateway stop to active is a few seconds, plus platform reconnects (Telegram, Discord, console), about 10–30 s
based on PROD's 2026-11-09 restarts. Messages sent during it are delivered on reconnect. Commitment sync misses about one
minute and catches up once (S10).

## Exact procedure

Root on `lilith-01`, from Git at the merge of this proposal. Copy `tz_ops.py` and `tz_window.sh` into a root-only 0700
directory and check their SHA-256 against the PR.

```bash
bash tz_window.sh precheck      # read-only; must end TZ_PRECHECK_PASS
bash tz_window.sh change        # precheck again, backups, stop, config + review, start; ends TZ_CHANGED backup=/root/tz-colombo-<ts>
bash tz_window.sh verify h60    # at +60 s
bash tz_window.sh verify h600   # at +10 min
bash tz_window.sh verify review # after the next 16:30Z review
```

**`change`, step by step:**
1. **Precheck** (refuses on any difference):
   - host;
   - outside blackout;
   - the four source hashes;
   - `config.yaml` = `a6f340f2…`, `lilith:lilith 0600`, no `timezone` key, no zone in the gateway environment;
   - the job set is exactly the inventory (three enabled recurring jobs; nothing else enabled; all timestamps zone-aware);
   - `jobs-plan` gives 16:30Z;
   - gateway running;
   - scheduler ticked under 180 s ago;
   - Core API active;
   - disk.
2. **Backup:** `config.yaml` to `/root/tz-colombo-<ts>/` (0700), hash-checked against `a6f340f2…`.
3. **Stop** the gateway, so the scheduler stops writing `jobs.json`. Then back up `jobs.json` and write `SHA256SUMS`.
4. **Config:** append `timezone: Asia/Colombo` through `tz_ops.py config-apply`:
   - it refuses an existing key, and refuses if any other key would change;
   - it is installed atomically as `lilith:lilith 0600`;
   - re-read: `{"timezone": "Asia/Colombo"}`.
5. **Review schedule:** `tz_ops.py jobs-apply` (as `lilith`, `HERMES_TIMEZONE=Asia/Colombo`) calls Hermes' own
   `update_job(e161234245f3, {"schedule": "0 22 * * *"})`. That is the rehearsed S3/S4 path. It then asserts:
   - `expr` = `0 22 * * *`;
   - `next_run_at` offset is `+05:30`, and its instant is the next 16:30Z;
   - **every other job is identical** to before.
6. **Any failure in steps 4–5:** both files are restored **exactly** from the backup (hash-checked), then the gateway
   restarts on the old configuration.
7. **Start** the gateway and wait for active/running (up to 90 s).

## Post-change checks and failure criteria

`tz_window.sh verify`, at +60 s, at +10 min, and after the next review:

| # | Pass | Failure response |
| --- | --- | --- |
| V1 | gateway active/running, `NRestarts` 0 | rollback |
| V2 | gateway environment `HERMES_TIMEZONE=Asia/Colombo` (bridged); `config.yaml` timezone Asia/Colombo | rollback |
| V3 | `datecheck`: zone Asia/Colombo; date line `(Asia/Colombo, +0530, UTC+05:30)` | rollback |
| V4 | review `0 22 * * *`, next run `…T22:00:00+05:30` = `…T16:30:00Z` | rollback |
| V5 | commitment sync ran under 150 s ago, `ok`; snapshot under 700 s ago, `ok`; scheduler heartbeat under 180 s | investigate, then rollback |
| V6 | gateway log `✓ telegram connected` and the other platforms; `Gateway running with N platform(s)` | investigate (platform outage is not zone-related) |
| V7 | Core API active (untouched) | investigate |
| Next review | executes once at 16:30Z (`last_run_at` ≈ 16:30Z, status ok), not at 11:00Z, not twice | rollback if it ran at the wrong time |

## Rollback (idempotent; outside the blackouts)

```bash
bash tz_window.sh rollback /root/tz-colombo-<ts>
```

It does the following:
1. Stops the gateway.
2. Restores `config.yaml` exactly (hash `a6f340f2…`).
3. Runs `tz_ops.py jobs-revert`: Hermes' `update_job` sets the review back to `30 16 * * *` in UTC, asserts next run
   16:30Z, and asserts every other job is unchanged.
4. Starts the gateway.

The scheduler's live counters in `jobs.json` are kept, so the file is not restored wholesale after the change. The exact
file restore is used only inside `change`, while nothing has run.

## Not in this change

- #412 (separately gated).
- Any reminder rescheduling: none pending; existing timestamps are zone-aware and keep their instants.
- systemd timers, the Core API, memory or canonical authority, DEV.
- Timeline stays shadow; P-5 stays off.

## Recommendation

**GO**, subject to the window rules above and a `precheck` that ends `TZ_PRECHECK_PASS` immediately before `change`.
Basis:
- the change is two edits, both rehearsed on byte-identical code;
- the only scheduled work whose wall clock matters (the review) keeps its instant;
- there is nothing timezone-less to reinterpret;
- rollback is mechanical.
