# DEV release candidate `f293e72-f9c2-cog1-wm1-g1-r1`: World Model, Goals and Reasoning in shadow (CANDIDATE, not installed)

This release is `f293e72-f9c2-cog1-wm1-g1`, which is running on DEV, with **one more** lane: Slice 9 Reasoning, in
**shadow**, for the `lilith_os` console only. World Model and Goals stay in shadow. Every other lane stays off. Nothing
here has been installed. The g2 Goals live release stays on disk on DEV but is not an input to this one.

## What changes against g1

[`RELEASE-DELTA.json`](RELEASE-DELTA.json) lists the three members that change:

| Member | g1 | r1 |
|---|---|---|
| `RELEASE_ID` | `f293e72-f9c2-cog1-wm1-g1` | `f293e72-f9c2-cog1-wm1-g1-r1` |
| `lilith_router/router.yaml` | `d931f1b6…`: Reasoning off | [`home/router.yaml`](home/router.yaml): `reasoning_enabled: true`, `reasoning_mode: shadow`; nothing else |
| `bin/verify_release.py` | g1 template `839a52b8…` | [`templates/bin/verify_release.py.tmpl`](templates/bin/verify_release.py.tmpl): `SHADOW_LANES` gains Reasoning; only the lane policy changes |

The governed adapter, the PROD Working Memory, the hardened gateway, the `lilith_os` adapter, the provider gate, FORGET,
and every other file are identical. Reasoning has no channel setting of its own: it uses `cognitive_channels`.

**The start-time gate refuses unless all of these hold:**
- `cognitive_enabled`, `goals_enabled` and `reasoning_enabled` are each exactly `true`;
- their three `*_mode` keys are each present and exactly `shadow`;
- `cognitive_channels` and `live_channels` are each exactly `["lilith_os"]`;
- the router's `mode` is `shadow`;
- every other lane is `false`, and `router.yaml` holds no key the router does not read.

The installed g1 verifier refuses this router (`LANE_NOT_OFF reasoning_enabled`), and this verifier refuses the g1
router.

## What Reasoning shadow does

In shadow, the gateway's Reasoning branch does exactly two things:
1. it runs the recovered PROD `detect_reasoning_intent`, which is pure regular-expression matching;
2. it appends one decision-log record.

`build_reasoning_input`, Core API reads, the tool-less model call and `reasoning.py` itself are reached only in **live**
mode. The record comes before the other lanes and does not stop them, so the turn then continues as it does on g1.

| Effect (offline: real gateway and adapter; real Core API source) | Measured |
|---|---|
| Core API reads | **0**, including `/os/goals`, `/os/goals/focus`, `/os/world`, `/os/tasks`, `/os/drafts` |
| Core API writes | **0** |
| Model or provider calls, network connections | **0** |
| User-visible routing | identical to g1 for every test message |
| World Model, Goals and routing records | identical to g1 |
| `reasoning.py` and later lanes | not imported |
| Files under `HERMES_HOME` | none changed, apart from the decision log |
| Other platforms | not observed |

Because nothing reads the database, this release does not depend on the goal schema. The Goals live window showed the
installed DB has `goal` and `goal_trace`; the tests here also pass on a DB without them.

## Decision-log record, retention and redaction

One record per matching turn, in the same file as the other lanes, so the 7-day retention and FORGET apply:

`ts`, `platform`, `chat_id`, `lane: reasoning`, `reasoning_mode: shadow`, `intent` (`mode`, `subtype`, `app_id`),
`trace: null`, `event_id`, `msg_chars`, `msg_lines`.

**No message text.** `app_id` is a number taken from the message. The decision log already treats records as sensitive
metadata, and `chat_id` is the session id.

## Detection

Reasoning **yields** to the World Model draft and pending paths and to every Goals turn. The fixtures in
[`tests/test_r1_shadow.py`](tests/test_r1_shadow.py) pin that precedence.

**Known over-matching, not changed here:** the detector also matches casual text such as "what next on the playlist",
"the next step is to feed the cat", "I am not sure what to cook", "the song title is unknown" and "evaluate this python
expression". In shadow each costs one record. In live each would trigger a reasoning call, so precision must be measured
and improved before any live proposal. Shadow records from a test window are the input to that decision.

## Not covered: Reasoning live

Shadow proves detection and logging only. Live is a separate proposal and would need at least:

- **Reads:** `build_reasoning_input` calls `/os/world`, `/os/goals`, `/os/goals/focus`, `/os/tasks?limit=200` and
  `/os/drafts?limit=200`. On DEV the last runs `_drafts_db()` DDL and would **create the `drafts` table** on a GET, and
  `/os/goals/focus` writes a trace row when the winner changes.
- **Provider data:** the full message plus beliefs, goal titles, task titles and draft ids in one prompt, in a separate
  tool-less model call. If that answer fails validation the turn falls through, so one turn can make **two** provider
  requests. The gate budget and the P-1 decision would both need revisiting.
- **A verifier schema rule** for `drafts`, as g2 has for the goal tables.
- **Detector precision** as above.

## Install and rollback

[`bin/install_r1.sh`](bin/install_r1.sh) is the merged `install_g2.sh` with only the release renamed (a test requires
this): same FORGET lock, stopped-gateway check, pinned payload, host-rendered verifier, quarantined staging and automatic
revert. Rollback is `install_r1.sh revert` to g1. The further steps down to wm1 and cog1 are unchanged.

It needs the payload files from this release and g1, in a root-only directory, with the gateway stopped. Installing it
is a separate owner decision, with its own preflight, stop, install and start gates.

## Tests

```bash
python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1/tests -p "test_*.py"
```

As root on a disposable Linux machine: `sudo bash integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1/tests/sim_install_r1.sh .`
