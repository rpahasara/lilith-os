# DEV release `f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1-gv1`: the startup verifier's goal rule, corrected

**Status: CANDIDATE_NOT_INSTALLED.** This package is for preparation and offline validation only. Installing it on DEV
is a separate, owner-authorized window. No PROD component is involved.

## Why

DEV runs e1. Its startup verifier (`ExecStartPre`) refuses with `GOAL_STORE_NOT_EMPTY`, so the **next DEV gateway start
will fail**. The gateway last passed this check at its 2026-11-04 08:32Z start.

The rule came from w1 (`f634039`, 2026-10-30) and was carried unchanged through m1, p1 and e1. Its stated purpose (w1
README, INSTALL-PLAN): a `GET /os/goals/focus` read with a goal present writes an arbitration trace, so the Workspace
shadow lane would not be write-free. "No goal row" stood in for "no focus read can write".

The goals now in DEV's store came from the owner-run P4-4 commitment-sync test on 2026-11-09 (work note on PR #412). No
DEV component wrote them:

| | |
| --- | --- |
| Goals | 6, all `commitment.once`, source `SCHEDULED` |
| States | 2 COMPLETED, 2 FAILED, 2 CANCELLED (all terminal) |
| Traces | 20, all `transition` |
| Arbitration traces | 0 |
| Core API | runs with `LILITH_OS_FOCUS_READ_ONLY=1` |

So the literal rule is violated, but the invariant it stood in for still holds.

## What changes

Only `bin/verify_release.py` and `RELEASE_ID` change. `HERMES_HOME`, `router.yaml`, every `lilith_router` module, the
units, sudoers, the Core API, its DB and every goal are untouched.

The check `count(goal) == 0` is replaced by what it protects. Each line below is a refusal, so anything that can't be
established refuses the start:

| Refusal | When |
| --- | --- |
| `GOAL_FOCUS_CANDIDATE <state> <n>` | any ACTIVE or PENDING goal (what `_arbitrate` ranks) |
| `GOAL_STATE_NOT_TERMINAL <state> <n>` | any state other than COMPLETED, FAILED or CANCELLED, including BLOCKED, SUSPENDED, NULL or unknown (conservative); free text prints as `<non-identifier>` |
| `GOAL_ARBITRATION_TRACE_PRESENT <n>` | any arbitration trace: evidence a focus read already wrote |
| `GOAL_TRACE_KIND_UNKNOWN <kind> <n>` | any trace kind other than `transition` |
| `CORE_API_NOT_RUNNING` | the Core API unit is not active with a main PID within 20 s (bounded wait: the gateway has no boot ordering on it) |
| `FOCUS_READ_ONLY_NOT_PERSISTENT` | `LILITH_OS_FOCUS_READ_ONLY=1` is not in the unit's environment, so a Core API restart would drop it |
| `FOCUS_READ_ONLY_NOT_IN_EFFECT` | the live process environment (`/proc/<pid>/environ`) lacks exactly `=1` |
| `CORE_API_DB_MISMATCH` | the process's `LILITH_DB_PATH` is not the store checked here |
| `CORE_API_IDENTITY` | not `api-venv/bin/uvicorn app:app`, or cwd not under `lilith-os-dev/releases/` |
| `CORE_API_CODE_CHANGED_SINCE_START` | `app.py` is newer than the process, so the running code is unknown |
| `FOCUS_GUARD_*`, `ARBITRATION_WRITER_UNEXPECTED` | an AST check of the `app.py` the process runs finds that `_record_focus_trace` is not called only from `goal_focus` and only under exactly `os.getenv("LILITH_OS_FOCUS_READ_ONLY") != "1"`, or that another function writes an arbitration trace |
| `CORE_API_UNREACHABLE` / `_FOCUS_STATUS` / `_FOCUS_UNPARSEABLE` | the real focus read fails |
| `FOCUS_HAS_WINNER` | the Core API sees a candidate the verifier did not |
| `FOCUS_READ_WROTE_TRACE` | the trace row counts differ before and after one real `GET /os/goals/focus` (loopback, trusted read) |

The live focus read happens only after every store, flag, identity and code check has passed, so two independent guards
already rule out a write: no candidate, and the flag in code and process. Only states, kinds and counts are read (`mode=ro`),
never goal text.

**Limit (same as w1's).** The verifier runs at start. `reopen` can return a terminal goal to PENDING while the gateway
runs. The next start refuses that, and in between the Core API flag keeps every focus read write-free. A test proves it
through the real app.

## Validation (offline and isolated; live DEV untouched)

| Suite | Where | Result |
| --- | --- | --- |
| `tests/test_gv1_release.py`, portable | Windows, Python 3.13 | 29 pass, 9 skipped (Linux root only) |
| `tests/test_gv1_release.py`, all | WSL Ubuntu 24.04 as root | 38/38 |
| `services/core-api/tests/test_focus_read_only_dev_store.py` | real app, TestClient | 7/7 (the guard-contract test also runs in CI) |
| Core API full suite | Windows | 422 OK (21 skipped) |
| `tests/sim_install_gv1.sh` | WSL as root, private namespace, overlays | **73/73, `SIM_RESULT PASS`** |

**Live DEV, read-only, 2026-11-10 14:10Z.** The exact gv1 verifier bytes were rendered with DEV's own token into a root
0700 directory under `/run`, run, and removed:
- `F8_VERIFY_PASS full …-e1` in 1.3 s, and `F8_VERIFY_PASS pre-start` in 0.24 s;
- trace rows 20, arbitration 0, goals 6, before and after;
- gateway, pins and `current` unchanged; nothing left behind.

So the switch-time dry run is expected to pass on DEV as it is today.

What each suite covers:

- **Release definition.**
  - Exact identity and pins. The diff from e1's template removes only the six goal-rule lines; every other policy
    constant is identical.
  - DEV's Core API (`app.py` `44200ce9…`, same as main) passes the guard check.
  - `stage` and `check` never require or touch the gateway; `switch`, `install` and `revert` require it stopped.
  - The installer deletes nothing.
- **Goal store.** Empty store; terminal-only (DEV's six, where e1 still says `GOAL_STORE_NOT_EMPTY`); ACTIVE; PENDING;
  BLOCKED, SUSPENDED, NULL, lowercase and free-text states; arbitration traces; unknown kinds; missing, unreadable and
  mismatched schema. The rule never writes.
- **Runtime.**
  - The intended DEV configuration passes, with exactly one focus read and the DB unchanged.
  - Every failure in the table above is reachable; none of the flag or code failures issues a focus read.
  - Waits for a Core API that is still starting, and catches a focus read that writes.
  - The loopback read ignores `http_proxy` (tested with a proxy pointed at a dead port).
- **Full host (root).** gv1 passes an e1-shaped host outright, where e1 refuses with exactly `GOAL_STORE_NOT_EMPTY`.
  Release-manifest tampering, a changed pinned file at restart, a Core API that is down, a goal that became ACTIVE, and
  `current` not being a release all still refuse.
- **Real process (root).** Real `/proc` reads of a process laid out like DEV's Core API, plus a real HTTP read: the flag
  passes with the DB byte-identical; no flag refuses before any read; a stopped process refuses.
- **Real Core API.**
  - Focus reads on a DEV-shaped store (built through the real create and transition paths) write nothing, with or
    without the flag.
  - With the flag, a new candidate or a reopened goal still writes nothing. Control: no flag plus a candidate does write.
  - **CI contract:** the gv1 guard check runs against `app.py` in CI, so a focus-route refactor fails at review, not as a
    refused DEV start after the next deploy.
- **Installer simulation.** The repo-built f9c2 → … → e1 chain, DEV's store reproduced (e1 refuses exactly as DEV does),
  a fake Core API with DEV's layout, and a `systemctl` shim. The cases:
  - **Host refusals:** wrong host, tampered or extra payload files, gateway states, a FORGET intent, a held FORGET lock,
    e1 refusing for a second reason.
  - **Dry-run refusals:** the 10 unsafe Core API or goal-store states.
  - **Two-phase:**
    - with the gateway **running**, `stage` refuses an unsafe host, then succeeds, and only the new release directory
      appears;
    - a second `stage` refuses; `check` passes and changes nothing;
    - `switch` refuses while the gateway runs, and `switch` or `check` refuse before staging;
    - a changed or extra staged file, or the e1 verifier swapped in with a matching rebuilt manifest, makes `check` and
      `switch` refuse;
    - a goal that becomes a candidate after staging makes `check` and `switch` refuse with `current` still e1;
    - **race:** `check` passes, the Core API then loses its flag, and `switch` refuses with `current` still e1;
    - the full stage → check → switch passes, using exactly the checked tree;
    - `stage` after the switch refuses, and `revert` returns to the baseline.
  - **Failure handling:** a staging failure is kept aside; injected failures after `home` and after the switch revert
    automatically.
  - **Single-phase `install`:** `HERMES_HOME` byte-identical, goal and trace rows unchanged, only the verifier and
    `RELEASE_ID` differ from e1.
  - **Restart checks:** pass, no flag, Core API down, a reopened goal, a changed pin, pass again.
  - **Revert:** interrupted before and after the switch, then resumed. This case found and fixed a defect: a revert
    interrupted after the switch kept the gv1 pins. Also revert from `failed/failed`, ending with the pins naming e1 only.

## Package and hashes

| File | SHA-256 |
| --- | --- |
| `templates/bin/verify_release.py.tmpl` (gv1) | `ba814bdcacdc0882c57d9f84feff587ade40a459822a95291dda1f90e1591115` |
| e1 template (`…-e1/templates/bin/verify_release.py.tmpl`) | `f1086cacc440d84850b30b033b23120e41f34919d2761ddb2e867761eb3b65d5` |
| e1 router (`…-e1/home/router.yaml`, unchanged) | `be8c08d1c5e88e03306d33869239823bd61d367740a160a8133fd9353943e6f4` |
| `RELEASE_ID` | `c33363446fcdcb8776c1db052751f96505e592d7066ce201652a46e1eac02618` |
| `bin/install_gv1.sh` (holds the payload pins above) | `1a3bbb8865cc3e7bec16e2fe942c9e8052ee1d91f4f99e856b342c1fcbdd7707` |

The rendered `bin/verify_release.py` is the gv1 template with the host's gate token. The installer takes the token from
the installed e1 verifier and refuses on any render mismatch, so the token never leaves the host. `staged_ok` re-derives
the render's hash in memory at every later phase.

Pins on install:
- `RELEASE.sha256` is regenerated for the staged release.
- `/etc/hermes-gateway-dev/critical.sha256` is re-pinned by the release's own `pin_critical.sh`. Its verifier line moves to
  the gv1 release.

## Deployment contract (for a separately authorized DEV window)

### Live preconditions (read-only, reconfirmed 2026-11-10 14:10Z; re-run at window start)

| Check | Value |
| --- | --- |
| Host | `lilith-dev-01`, machine-id `ae929170…` |
| `current` | e1 |
| e1 release | `RELEASE.sha256` all 18,227 files OK; root 0555 |
| `critical.sha256` | `459b7557…`, all 52 entries OK, 8 naming e1 |
| `HERMES_HOME` | router `be8c08d1…`, adapter `f1ee561d…`, ethics `d6a1c20b…`, PROD module `46b8187e…` (e1's) |
| e1 verifier | exactly `F8_VERIFY_FAIL GOAL_STORE_NOT_EMPTY` (`--full` 5.3 s, `--pre-start` 0.12 s) |
| Goals | CANCELLED 2, COMPLETED 2, FAILED 2 |
| Traces | 20 `transition`, 0 arbitration |
| Core API | active, PID 572371, 0 restarts, flag in unit and process, `LILITH_DB_PATH` = goal store, `app.py` `44200ce9…`, `/health` 200 in 20 ms |
| FORGET | no marker, 0 intents, executor inactive, path units waiting |
| Disk | 3,221 MB free; e1 is 390 MB |
| Gateway | active since 2026-11-04 08:32Z; `Restart=on-failure` (10 s); start timeout 90 s; `StartLimitBurst=3` per 5 min; systemd 255 |
| Unrelated | an older `…-e1-l1` release directory exists, unused (not `current`, not touched) |

### Sequence (two-phase; root on `lilith-dev-01`; payload from Git at the merge commit)

The gateway keeps serving through phases 0–2. Only phase 3 needs it stopped.

```bash
# 0. preconditions (read-only): the table above; dr5_check.sh baseline; provider-gate ledger line count
# 1. payload: exactly verify_release.gv1.py.tmpl, verify_release.e1.py.tmpl, router.e1.yaml, RELEASE_ID; hashes as above
install -d -o root -g root -m 0700 /root/gv1-payload
# 2. stage + check while the gateway RUNS (no service impact; only releases/<gv1> is written)
bash install_gv1.sh stage /root/gv1-payload      # expect GV1_STAGED ... dry run PASS ... gateway untouched
bash install_gv1.sh check /root/gv1-payload      # expect GV1_CHECK_PASS   (run again right before step 3)
# 3. switch (outage starts here)
systemctl stop hermes-gateway-dev
bash install_gv1.sh switch /root/gv1-payload     # expect GV1_INSTALLED current=...-e1-gv1
systemctl start hermes-gateway-dev               # ExecStartPre: F8_VERIFY_PASS pre-start ...-e1-gv1
# 4. post-install health checks (below)
```

No main merges or `deploy-dev` runs during the window: they restart the Core API. Merge #413 first, and let its own
`deploy-dev` run finish before the window.

**Estimated outage.** The console is down only from `systemctl stop` until the gateway is stable:
- stop: a few seconds;
- `switch`: about 20–40 s (e1 verdict ≤ 5 s, staged-tree hash check of 18k files, dry run, re-pin, `verify --full` ≤ 5 s);
- start, plus `ExecStartPre` (about 0.3 s) and stabilisation: about 20–30 s.

**About 1–2 minutes.** The single-phase `install` adds staging to the outage, so it is not used.

If `switch` refuses, nothing has changed (`current` is still e1), but the gateway is already stopped and cannot start on
e1. The `check` immediately before the stop is what makes that unlikely: it runs the same checks on the same state
seconds earlier.

### Post-install health checks, with failure criteria

All checks are read-only. **Pass requires every line.**

| # | Check | Pass | Failure |
| --- | --- | --- | --- |
| H1 | `switch` output; `verify_release.py --full` | `GV1_INSTALLED`; `F8_VERIFY_PASS full …-e1-gv1` | anything else |
| H2 | gateway start | `active/running` within 90 s; journal has `F8_VERIFY_PASS pre-start …-e1-gv1` | any `F8_VERIFY_FAIL`, `failed`, or a start-limit hit |
| H3 | stability | MainPID unchanged and `NRestarts=0` at +60 s and +10 min | any restart |
| H4 | console | port 9901 listening (loopback) | not listening |
| H5 | provider budget | gate ledger lines unchanged across the start (0 requests at startup) | any new line |
| H6 | goal store | goal states 2/2/2 terminal, traces 20 `transition`, 0 arbitration (counts only) at +60 s and +10 min | any change |
| H7 | `HERMES_HOME` and pins | the four e1 hashes unchanged; `critical.sha256` verifies and names the gv1 verifier | any difference |
| H8 | Core API untouched | PID 572371, `NRestarts=0`, flag still in unit and process | restarted or flag missing |
| H9 | deployer boundary | `dr5_check.sh` identical to the step-0 baseline | not identical |

On any failure, stop and follow the runbook below. **Never** bypass `ExecStartPre`, edit the verifier or pins by hand,
or delete or alter the six historical goals.

### Recovery runbook if gv1 does not start after the switch

First read the refusal (`journalctl -u hermes-gateway-dev -o cat | grep F8_VERIFY`). The cause decides the response:

| Class | Codes | Meaning | Response | New release needed? |
| --- | --- | --- | --- | --- |
| A. Core API side | `CORE_API_NOT_RUNNING`, `_UNREACHABLE`, `_RUNTIME_UNREADABLE`, `_FOCUS_STATUS`, `_CODE_CHANGED_SINCE_START`, `_DB_MISMATCH`, `_IDENTITY`, `FOCUS_READ_ONLY_NOT_*` | the API was restarting, was redeployed without a restart, or lost the flag | Confirm read-only. If the API simply restarted, one more `systemctl start hermes-gateway-dev` (inside the window). Otherwise a separately authorized Core API action: restart it, or restore the drop-in. | **No** |
| B. Goal store | `GOAL_FOCUS_CANDIDATE`, `GOAL_STATE_NOT_TERMINAL`, `GOAL_ARBITRATION_TRACE_PRESENT`, `GOAL_TRACE_KIND_UNKNOWN` | a goal or trace changed during the window | Stop. Owner decision; any goal transition is separately authorized. Never delete. | No |
| C. Integrity | `HASH_MISMATCH`, `MANIFEST_*`, `CURRENT_NOT_A_RELEASE`, `NOT_ROOT_OWNED`, … | a pinned file changed | Stop and investigate. `revert` restores e1, but **not service**. | No, unless the gv1 tree itself is damaged (then re-stage the same release) |
| D. gv1 defect | a refusal that read-only evidence shows is wrong, or a traceback | the verifier is wrong in the systemd context | DEV console stays down; prepare a corrected release (gv2), separately reviewed, tested and authorized. Do not hand-edit gv1. | **Yes** |
| E. Hermes itself | `ExecStartPre` passed, but the gateway exits | not gv1 (Hermes code is identical to e1's) | Diagnose from the journal. A revert does not help (e1 cannot start). | No (not a gv1 matter) |

systemd retries a failed start every 10 s, at most 3 times in 5 minutes, then stops. Each retry runs the verifier: reads
only, plus one focus read that is write-free with the flag on. After fixing the cause (classes A–C), `systemctl
reset-failed hermes-gateway-dev` and then `systemctl start` within the window.

**Rollback** is idempotent, with the gateway stopped:

```bash
bash install_gv1.sh revert /root/gv1-payload     # expect GV1_REVERTED current=...-e1 (e1 verifier: GOAL_ONLY)
```

It restores e1 exactly, but **not service**: e1 refuses `GOAL_STORE_NOT_EMPTY`, as it would at DEV's next start without
gv1. The gv1 release directory is kept for inspection, and nothing is deleted.

### Remaining risks for the owner's explicit acceptance

1. **Outage if gv1 refuses after the switch for a gv1-specific reason (class D).** The DEV console stays down until a
   corrected release is authorized. Likelihood is low:
   - the exact bytes passed on live DEV today, read-only;
   - `check` repeats that seconds before the stop;
   - the remaining difference is the systemd `ExecStartPre=+` context: root, no sandbox, unit environment. The verifier
     ignores `PYTHON*` (`-I`), uses absolute `/usr/bin/systemctl`, and ignores proxies.

   It cannot be exercised without a real start.
2. **Rollback does not restore service.** This is structural. The only alternatives are deleting the six historical
   goals or weakening the rule, and both are excluded.
3. **New coupling to the Core API.** Every DEV gateway start now requires the Core API to be up, flagged and unmodified
   since start, and its focus route to keep the guarded shape. The CI contract test catches route changes at review;
   `deploy-dev` restarts the API, so code-since-start stays consistent. Avoid windows that overlap a deploy.
4. **Start-only check.** A goal reopened while the gateway runs is refused at the next start. In between, the flag keeps
   reads write-free.
5. **About 1–2 minutes of DEV console downtime** during the switch.

## Not in scope

- Deleting or changing the six TEST_ONLY goals.
- Changing the Core API, its units or its flag.
- Weakening any other verifier rule.
- Any PROD change.
- Timeline stays shadow; P-5 stays off; PR #412 is separately gated.
