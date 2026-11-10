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
| `tests/test_gv1_release.py`, portable | Windows, Python 3.13 | 27 pass, 9 skipped (Linux root only) |
| `tests/test_gv1_release.py`, all | WSL Ubuntu 24.04 as root | 36/36 |
| `services/core-api/tests/test_focus_read_only_dev_store.py` | real app, TestClient | 6/6 |
| Core API full suite | Windows | 421 OK (21 skipped) |
| `tests/sim_install_gv1.sh` | WSL as root, private namespace, overlays | **50/50, `SIM_RESULT PASS`** |

What each covers:

- **Release definition.** Exact identity and pins. The diff from e1's template removes only the six goal-rule lines.
  Every other policy constant is identical. The Core API that DEV runs (`app.py` `44200ce9…`, same as main) passes the
  guard check.
- **Goal store.** Empty store; terminal-only (DEV's six, where e1 still says `GOAL_STORE_NOT_EMPTY`); ACTIVE; PENDING;
  BLOCKED, SUSPENDED, NULL, lowercase and free-text states; arbitration traces; unknown kinds; missing, unreadable and
  mismatched schema. The rule never writes.
- **Runtime.** The intended DEV configuration passes, with exactly one focus read and the DB unchanged. Every failure
  above is reachable, and none of the flag or code failures issues a focus read. Waits for a starting Core API. Catches a
  focus read that writes.
- **Full host (root).** gv1 passes an e1-shaped host outright, where e1 refuses with exactly `GOAL_STORE_NOT_EMPTY`
  (DEV's state). Release-manifest tampering, a changed pinned file at restart, a Core API that is down, a goal that
  became ACTIVE, and `current` not being a release all still refuse.
- **Real process (root).** Real `/proc` reads of a process laid out like DEV's Core API, plus a real HTTP read: the flag
  passes with the DB byte-identical; no flag refuses before any read; a stopped process refuses.
- **Real Core API.** On a DEV-shaped store built through the real create and transition paths:
  - focus reads write nothing, with or without the flag;
  - with the flag, a new candidate or a reopened goal still writes nothing;
  - control: no flag plus a candidate does write.
- **Installer simulation.** Builds f9c2 → … → p1 from this repository and installs e1 with its merged installer. It
  reproduces DEV's store, so e1 refuses exactly as DEV does. A fake Core API runs with DEV's layout, and a `systemctl`
  shim is bind-mounted in the namespace. The cases:
  - **Host refusals:** F8_SIM on `lilith-01` and `lilith-dev-01`; a wrong host; tampered and extra payload files; three
    gateway states; a FORGET intent; a held FORGET lock; e1 refusing for a second reason.
  - **Dry-run refusals,** before any shared change: each of the 10 unsafe Core API or goal-store states.
  - **Failure handling:** a staging failure is kept aside; injected failures after `home` and after the switch revert
    automatically.
  - **Install:** `HERMES_HOME` byte-identical, goal and trace rows unchanged, only the verifier and `RELEASE_ID` differ
    from e1, and e1 and p1 untouched.
  - **Restart checks:** pass, no flag, Core API down, a reopened goal, a changed pin, pass again.
  - **Revert:** interrupted before and after the switch, then resumed. This case found and fixed a defect: a revert
    interrupted after the switch kept the gv1 pins. Also revert with the gateway in `failed/failed`, ending with the pins
    naming e1 only.

## Package and hashes

| File | SHA-256 |
| --- | --- |
| `templates/bin/verify_release.py.tmpl` (gv1) | `2709d99d62ba105a6f6a99515ac04f045a8b29a58994ed254a4a66f256334125` |
| e1 template (`…-e1/templates/bin/verify_release.py.tmpl`) | `f1086cacc440d84850b30b033b23120e41f34919d2761ddb2e867761eb3b65d5` |
| e1 router (`…-e1/home/router.yaml`, unchanged) | `be8c08d1c5e88e03306d33869239823bd61d367740a160a8133fd9353943e6f4` |
| `RELEASE_ID` | `c33363446fcdcb8776c1db052751f96505e592d7066ce201652a46e1eac02618` |
| `bin/install_gv1.sh` (holds the payload pins above) | `dee101bef13a247a349441c81690f9dffab9c82bb27055be7753ce7441c6237a` |

The rendered `bin/verify_release.py` is the gv1 template with the host's gate token. The installer takes the token from
the installed e1 verifier and refuses on any render mismatch, so the token never leaves the host.

Pins on install:
- `RELEASE.sha256` is regenerated for the staged release.
- `/etc/hermes-gateway-dev/critical.sha256` is re-pinned by the release's own `pin_critical.sh`. The verifier path changes
  to the gv1 release.

## Deployment contract (for a separately authorized DEV window)

**Preconditions.** All are read-only. The installer re-checks every one of them except item 3.

1. Host `lilith-dev-01`; `current` is e1; `HERMES_HOME` matches e1 (router, adapter, ethics, PROD module).
2. The e1 verifier says either PASS or exactly `GOAL_STORE_NOT_EMPTY`.
3. `dr5_check.sh` is identical to its expected block (a baseline for the post-check).
4. FORGET is idle, and there is enough space to stage.

**Downtime.** The gateway must be stopped. Today it runs on e1 (since 2026-11-04). Once stopped, it cannot start again on
e1 because of `GOAL_STORE_NOT_EMPTY`. So:
- if the install refuses or reverts, the DEV console stays down until a decision;
- that is the state DEV is already in at its next start;
- no goal is deleted to avoid it.

**Sequence**, run as root on `lilith-dev-01` from Git at the merge commit:

```bash
install -d -o root -g root -m 0700 /root/gv1-payload
# copy exactly: verify_release.gv1.py.tmpl, verify_release.e1.py.tmpl, router.e1.yaml, RELEASE_ID; check the hashes above
systemctl stop hermes-gateway-dev
bash install_gv1.sh install /root/gv1-payload     # expect GV1_INSTALLED ... e1 before: GOAL_ONLY
systemctl start hermes-gateway-dev                # ExecStartPre: F8_VERIFY_PASS pre-start ...-e1-gv1
```

**Post-checks** (read-only):
- the gateway is active and stable for 20 s or more with 0 restarts, and the journal shows the gv1 `F8_VERIFY_PASS`;
- goal rows and trace counts are unchanged (counts only), with 0 arbitration traces;
- `HERMES_HOME` hashes are unchanged;
- `dr5_check.sh` is identical to the baseline;
- 0 provider requests at startup.

**Rollback**, idempotent:

```bash
systemctl stop hermes-gateway-dev
bash install_gv1.sh revert /root/gv1-payload      # expect GV1_REVERTED current=...-e1 (e1 verifier: GOAL_ONLY)
```

After rollback the gateway stays stopped: e1 refuses `GOAL_STORE_NOT_EMPTY`, exactly as before gv1. The gv1 release
directory is kept for inspection, and nothing is deleted.

## Not in scope

- Deleting or changing the six TEST_ONLY goals.
- Changing the Core API, its units or its flag.
- Weakening any other verifier rule.
- Any PROD change.
- Timeline stays shadow; P-5 stays off; PR #412 is separately gated.
