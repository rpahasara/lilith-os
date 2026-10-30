# DEV release candidate `f293e72-f9c2-cog1-wm1-g1-r1-w1`: Workspace in shadow (CANDIDATE, not installed)

This release is `f293e72-f9c2-cog1-wm1-g1-r1` with Slice 10 Global Workspace also in **shadow**, for `lilith_os` only. World
Model, Goals and Reasoning stay in shadow, and every other lane stays off. Nothing here has been installed. **It depends on PR #295,** merged into this branch. See [INSTALL-PLAN.md](INSTALL-PLAN.md).

**Order:** r1 must run on DEV and pass its shadow test first. Then the [`drafts` bootstrap gate](DRAFTS-BOOTSTRAP.md). Only then
this release. Unlike r1, this lane reads the Core API, so it is a separate step.

## What changes against r1

[`RELEASE-DELTA.json`](RELEASE-DELTA.json) lists five members: `RELEASE_ID`, `router.yaml` (`workspace_enabled: true`, `workspace_mode: shadow`), the
verifier template, the adapter with the detector candidate from #295, and `workspace.py` with the counts-only trace. The verifier adds
Workspace to `SHADOW_LANES`, pins both new files, and has one new check.

**`check_cognition_schema` refuses to start unless all of these hold, reading only (`mode=ro`):**
- `goal`, `goal_trace` and `drafts` exist with exactly their Core API columns;
- the `goal` table has **0 rows**.

The second rule is the focus-trace safeguard below. It must be revisited before Workspace runs beside real or synthetic goals.

## What Workspace shadow does

Only inside a matching Reasoning turn, it builds one ephemeral snapshot from durable state and writes one metadata record. The
reply path is unchanged, and no model is called.

| Measured on the real gateway, adapter and Core API | Result |
|---|---|
| Analytic turn naming an application | exactly 5 reads: `/os/goals?limit=200`, `/os/goals/focus`, `/os/drafts?limit=200`, `/os/tasks?limit=200`, `/os/world?…entity_id=14`; all 200 |
| Schema, rows, traces on the bootstrapped DB | unchanged |
| Social, goal and pending turns | 0 Workspace reads where the lane does not match |
| Core API outage | fails open; the reply path is unchanged |
| Provider calls | 0 |

## Safeguards

| Risk | Safeguard |
|---|---|
| **`GET /os/drafts` runs DDL** | The bootstrap gate creates the table first; the verifier refuses without it. A test shows the table would otherwise appear on a GET |
| **`GET /os/goals/focus` writes a trace when the winner changes** | The verifier refuses while any goal row exists. An empty store has no winner. A test shows one goal produces one trace. The check runs at start only, so a goal added later is not caught; the adapter refuses goal creation, and no DEV component writes goals |
| **Detector over-matching** | Casual text can match Reasoning, for example "what next on the playlist". Each match costs at most 5 reads, within the adapter's per-call budget, and writes nothing. Review r1 shadow records first: if false matches are common, tighten the detector before installing this |
| **Read load** | The adapter's breaker and per-call bound apply unchanged |

## Candidate IDs and privacy

The record holds `ts`, `platform`, `chat_id`, `lane`, `workspace_mode`, `trace`, `event_id`, `msg_chars` and `msg_lines`.

**The trace holds:** correlation id, candidate count, source-type counts, selected primary id and class, secondary and
suppressed ids, deciding rule, capacity, duration, fallback reason.

**Tested with canary text in a goal title, a goal description, a draft subject and a draft body: none reaches the record.**

**Why ids were removed:** a candidate id was an unsalted hash, stable across turns, so it linked turns about one item. Nothing read it.
The record now holds counts and classes only:

| Control | State |
|---|---|
| Retention | the decision log is in `logs/`, rotated daily and removed after 7 days by `hermes-gateway-dev-retention` |
| FORGET | `logs` is in the executor's `PURGE_DIRS`, so a principal FORGET removes it. There is no per-item erasure |
| Deleting one goal | does not remove its id from existing log records, which stay until retention |
| Observation | gates print counts and classes, never the ids |

**Decision: stable ids should not be in shadow logs.** Nothing reads them. The candidate in
[`overlays/dev-workspace-private-trace`](../../overlays/dev-workspace-private-trace/README.md) records counts instead, and this release
adopts it: no candidate id reaches a record, and tests pin that on the real gateway.

## Install and rollback

[`bin/install_w1.sh`](bin/install_w1.sh) is the merged `install_r1.sh` moved one step, enforced by a test. Rollback is
`install_w1.sh revert` to r1. It needs r1 installed.

## Tests

```bash
python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1/tests -p "test_*.py"
```

As root on a disposable Linux machine: `sudo bash integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1/tests/sim_install_w1.sh .`
