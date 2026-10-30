# Acceptance record: Reasoning shadow on DEV (`f293e72-f9c2-cog1-wm1-g1-r1`), 2026-10-30

**Decision:** owner-accepted as **PASS** on 2026-10-30, for the verified shadow-only scope: detection, routing, metadata-only
logging, zero Core API reads and writes, and provider-gate isolation. This does not establish Reasoning Live or model-based
reasoning: no reasoning input was built, no reasoning model call was made, and no model replied to any turn. DEV stays on r1.

## Runtime tested

| Item | Value |
|---|---|
| Host | `lilith-dev-01` (boot `cb0d71da…`, unchanged throughout) |
| Release | `f293e72-f9c2-cog1-wm1-g1-r1` (PR #288, merged as `d3a8def`); bundle `21c90b2c…`; router `47579562…` |
| Lanes | World Model, Goals and Reasoning `shadow`, on `lilith_os` only; every other lane `false`; router `mode: shadow` |
| Package | owner-approved, manifest `d51450f7…`; every file verified before the run |
| Rollback target | g1, intact |

Console downtime was 11:57:06 to about 12:00:47Z. The gateway moved from PID 363555 to **369445**; the provider gate from 339513
to **370064**.

## Install (each step run once, rc 0, empty stderr)

| Step | Result |
|---|---|
| P0 read-only | PASS |
| S1 stop g1 | PASS. Exit status 1 as usual; port 9901 closed; other units unchanged |
| S2 transfer | PASS. `CHUNK OK 3ded1dd6…` |
| S3 install | PASS. `verify --full` PASS; 0 changes under Privacy, broker, authority, witness and FORGET |
| S4 start r1 | PASS. PID 369445, 0 restarts, 0 forwards at startup |
| S5 post-verify | PASS. Three lanes shadow; DB unchanged; 0 Core API requests |
| S6 shadow test | PASS, below |
| S7 final read-only | PASS. Same gateway PID; DB, budget and ledger unchanged; 4 dumps as expected |

## Provider isolation

Checked read-only before S6, on the running host:

| Check | Result |
|---|---|
| Gateway sandbox | `IPAddressDeny` all; `IPAddressAllow` only `127.0.0.1/32` |
| Model endpoint | `http://127.0.0.1:9911/openai/v1`, the gate |
| Fallback | `fallback_providers: []` |
| Provider keys in the gateway `.env` | none; names present are only `LILITH_OS_PORT` and `LILITH_OS_TOKEN` |
| Loopback listeners | the Core API, 9901, 9911 and DNS; none is another provider |

With the gate stopped, port 9911 had 0 listeners before any turn was sent. All four turns then failed on connection, and the gate
recorded 0 FORWARDED. The gate's ledger was byte-identical before and after.

## The four turns, TEST_ONLY, fresh sessions, gate stopped

| Turn | Message | Reply | Records, in order | Result |
|---|---|---|---|---|
| T1 | `TEST_ONLY what are my options for application 14?` | 200 `completed`, error text 117 chars | reasoning `OPTION_GENERATION` (`app_id: 14`, `trace: null`); cognitive shadow; routing `live: false` | exact |
| T2 | `TEST_ONLY what information is missing to resolve this?` | same | reasoning `UNCERTAINTY_ANALYSIS` (`trace: null`); routing | exact |
| T3 | `TEST_ONLY which goal has priority?` | same | goal shadow (`goal_query: true`); routing. Reasoning yielded | exact |
| T4 | `TEST_ONLY hey how are you` | same | routing only | exact |

| Criterion | Result |
|---|---|
| Message text in the decision log | 0 |
| Core API requests since the r1 start | **0** |
| Database | digest `b2913725…`, file mtime and size unchanged, 0 rows |
| Budget | `True OK 2 5 True` before and after |
| Ledger | 27 lines, `a05fe17e…` before and after |
| Gateway | PID 369445, 0 restarts |
| Request dumps | 4, mode 0600, 708 bytes each, `content_free: true`, 0 with message text |
| Dump bodies | identical shape: `gpt-oss-120b`, 2 messages, one `max_retries_exhausted` per turn |
| Protected services and FORGET | unchanged; 0 intents, no marker |

## Detector

**Live:** 2 of 2 analytic turns matched with the expected mode; 2 of 2 others did not match Reasoning. Four turns prove the
seam, not a detection rate.

**Offline corpus** ([`test_r1_detector_corpus.py`](tests/test_r1_detector_corpus.py), 50 synthetic messages, same author):

| Set | Result |
|---|---|
| Analytic requests matched | **20 of 25** |
| Casual messages matched in error | **18 of 25** |

The detector over-matches heavily on casual text containing `not sure`, `unknown`, `assess`, `what next`, `what's missing`, or
`what can you do`. It also misses `pros and cons`, `which option`, and `should I…`, and a message with `reply` goes to the draft
path first.

On r1 a false match costs one metadata record. **Under Workspace, each one costs up to 5 Core API reads,** so the detector should
be tightened or its rate measured on real shadow records before Workspace runs on real traffic. The corpus is a warning, not a
measured rate.

## Limitations

- **Detection only.** `build_reasoning_input`, `reasoning.py` and any reasoning model call were not reached, by design.
- **"No reasoning context to the model" is shown by the code path and offline tests, not by byte capture.** The dump shows the
  same shape on every turn, but it is content-free and holds no per-message sizes. The earlier g2 size comparison could not be
  repeated, because no request was forwarded.
- **The turn after a failed model call was not exercised.** Normal gateway behaviour on r1 with a working gate, including a
  successful reply, is unproven until a turn is forwarded. None was authorized.
- **One gate restart** is the only protected-service change. Four dumps remain under retention until pruned.
- **`app_id` in records** is sensitive metadata. Here it is synthetic.
