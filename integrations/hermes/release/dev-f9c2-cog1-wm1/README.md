# DEV release candidate `f293e72-f9c2-cog1-wm1`: World Model lane in shadow (CANDIDATE, not installed)

This release is `f293e72-f9c2-cog1` (installed and running on DEV since 2026-10-28) with **exactly one** cognitive
lane turned on: the Slice 7.2 World Model lane, in **shadow**, for the `lilith_os` console only. Every other lane
stays off. Nothing here has been installed, and the live router configuration is unchanged.

## What changes against cog1

[`RELEASE-DELTA.json`](RELEASE-DELTA.json) lists the three members that change:

| Member | cog1 | wm1 |
|---|---|---|
| `RELEASE_ID` | `f293e72-f9c2-cog1` | `f293e72-f9c2-cog1-wm1` |
| `lilith_router/router.yaml` | `7bb4fbb5…`, every lane off | [`home/router.yaml`](home/router.yaml): `cognitive_enabled: true`, `cognitive_mode: shadow`, `cognitive_channels: [lilith_os]`; everything else identical |
| `bin/verify_release.py` | cog1 template `817f7cae…` | [`templates/bin/verify_release.py.tmpl`](templates/bin/verify_release.py.tmpl): only the lane policy changes |

The governed adapter, the PROD Working Memory, the hardened gateway, the `lilith_os` adapter, the provider gate,
FORGET, and every other file are identical.

**The new start-time gate refuses unless all of these hold:**
- `cognitive_enabled` is exactly `true`, `cognitive_mode` is exactly `shadow`, and `cognitive_channels` is exactly
  `["lilith_os"]`;
- every other lane is `false`;
- every `*_mode` key is `shadow`.

It still pins the adapter and the PROD module. Anything else (live mode, `*`, Telegram, a chat-scoped channel,
another lane) stops the gateway from starting.

## Why the World Model lane first

In shadow, the DEV gateway's World Model branch does exactly two things:
1. it runs the recovered PROD `detect_intent`, which is pure regular-expression matching;
2. it appends one decision-log record.

Grounding, the `/os/drafts` path and the model are reached only in **live** mode. The offline tests run the real
gateway and the governed adapter with every socket blocked, and show:

| Effect | Measured |
|---|---|
| Core API reads (`/os/world`, `/os/tasks`, `/os/drafts`, `/os/goals`, **`/os/goals/focus`**, `/career/applications`) | **0**. No GET is sent, so no `goal_trace` arbitration row can be written |
| Core API writes | 0. Draft and goal writes are also refused by the adapter |
| Model or provider calls, network connections | 0 |
| User-visible routing | identical to cog1 for every test message |
| Other lanes, canonical memory, Privacy and learning modules | not imported, not run |
| Files under `HERMES_HOME` | none changed apart from the decision log |
| Other platforms (for example Telegram) | not observed |

Every other lane reads Core API in shadow (workspace, motivation, planning, ethics, reasoning), and through the
attention builder they call `GET /os/goals/focus`. That call can record a `goal_trace` row. Those lanes stay off.

## Decision-log records, retention and redaction

**Records added.** One record per `lilith_os` turn that the PROD detector marks as a World Model, pending-state or
draft question. In the tests, 7 of 9 varied messages matched; even "why is my kubernetes pod pending?" counts as a
pending-state question. Each record's fields are fixed by the reviewed DEV gateway:
- `platform`, `chat_id`;
- `lane: cognitive`, `cognitive_mode: shadow`;
- `intent`: four booleans plus `app_id` (a digit string such as `"14"`, or null);
- `msg_chars`, `msg_lines`, `event_id` (random), `ts`.

**What the records never contain:** message text, Core API data, memory content or the model reply. The tests check
this with canary text.

**Proposed rules (no change needed to code):**
- **Retention:** keep the existing DEV rule. `hermes-gateway-dev-retention.timer` rotates
  `logs/lilith-router-decisions.log` daily, keeps 7 days (`hermes-logrotate.conf`), and deletes any log file older
  than 7 days.
- **FORGET:** the FORGET executor already purges `HERMES_HOME/logs` during an erasure.
- **Redaction:** none needed beyond what the gateway already does. `app_id` is the only value derived from the
  message; it is an application number, not text. Treat these records as conversation metadata under the existing
  DEV rules.
- **Review cadence:** read only the record counts and intent flags during the shadow window. Never copy
  `lilith-router-decisions.log` off the host.

## Provider data

Shadow World Model sends nothing new to any model provider. The lane makes no model call and adds nothing to
`combined_ephemeral`, the prompt suffix that the normal turn sends.

Live World Model would insert World Model beliefs, pending tasks and drafts (`cognitive_mode: live`). That is a
separate Gate F/G decision, and this verifier refuses it.

## Installing and rolling back (each step needs its own approval)

[`bin/install_wm1.sh`](bin/install_wm1.sh) is adapted from the reviewed `install_cog1.sh`. Its guard functions are
the cog1 ones verbatim, and a test checks this:
- it holds the FORGET executor lock;
- it accepts only a fully stopped gateway;
- it uses a digest-pinned payload, render-on-host for the gate token, and staging quarantine;
- it reverts automatically after the first change if anything fails;
- the revert is idempotent;
- the `F8_SIM` guard applies.

| Step | Gate | Operation | Effect |
|---|---|---|---|
| 1 | A | read-only preflight (as the cog1 P0) | none |
| 2 | D | stop `hermes-gateway-dev` | console downtime starts |
| 3 | E | `install_wm1.sh install <payload>` (5 files: two routers, two verifier templates, `RELEASE_ID`) | stages `releases/f293e72-f9c2-cog1-wm1`, replaces `router.yaml`, switches `current`, re-pins, passes `verify --full` |
| 4 | D | `reset-failed` + start | the wm1 start-time gate runs; the shadow lane is live in the process |
| 5 | A | read-only post-start check, then a bounded shadow window | record counts and flags only |

**Rollback:** stop the gateway, run `install_wm1.sh revert <payload>`, then `reset-failed` + start.
- The revert restores the cog1 `router.yaml` (every lane off) and switches `current` back to cog1.
- cog1's own `verify --full` must pass.
- No memory, Privacy, authority, Core API or provider state is involved.
- Removing the shadow lane always requires this revert. Editing `router.yaml` by hand fails the critical-file pin at
  the next start.

**Dependency:** the wm1 venv resolves into `releases/f293e72-f9c2`, so **f9c2 and cog1 must both stay in place**
while wm1 is current.

## Tests

```bash
python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1/tests -p "test_*.py"
sudo COG1_RUN_SIM=1 python3 -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1/tests -p "test_*.py"
```

- **`test_wm1_shadow.py`:** the real gateway and adapter on an assembled cog1 home, in a fresh process with sockets
  blocked. It covers routing parity, zero Core API and provider traffic, content-free records, no other lane or
  memory module, no `HERMES_HOME` change, other platforms ignored, and router revert.
- **`test_wm1_release.py`:** the release definition, the exact router and verifier diffs, and the cog1 and wm1
  verifiers run on the same fixture hosts. It checks acceptance, refusal of live mode, other channels and any other
  lane, and that the adapter and PROD pins are kept.
- **`test_wm1_installer.py`:** payload pins, guards identical to cog1, no service control or deletion, and the
  simulation.
- **`sim_install_wm1.sh`:** root, private namespace and overlays. It installs cog1 with the merged installer, then
  covers refusals, FORGET races, staging and revert failures, install and revert.
