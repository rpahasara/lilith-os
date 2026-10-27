# F8r4 Phase B: OWNER ACCEPTANCE (2026-10-23)

**Decision (owner, in chat):**

> "I formally ACCEPT F8r4 Phase B as a successful synthetic-only inference milestone."

**Scope:** package `16c7417dc97a11ba6cf65fe44ef639e255bff22257f65d5f9bcefaab1af9d41a` (release `f293e72-f8r4`) on lilith-dev-01, per `PHASE-B-RESULT.md`. The acceptance covers synthetic-only inference.

**Not authorized:** personal conversations, owner recording, canonical memory admission, First Memory, a budget reset, further provider requests, or changes to the running environment.

## G-11 owner verification (Groq Console)

- **Model:** `openai/gpt-oss-120b`.
- **Request graph:** **5 requests** on 2026-10-23. API key `f8-dev-gate`. No Playground requests.
- **Token usage:** about 4.4K, which matches DEV. The gate records sum to prompt 4,177 + completion 239 = **4,416**.

## Exact request ledger (preserved; never reset)

Gate ledger `/var/lib/private/hermes-provider-gate-dev/ledger.log` on DEV, as read at A5 (`A5.out`):

```
RESET 2026-10-23T12:43:12+00:00 initial-ledger
R 2026-10-23T12:57:52+00:00 0d00769ac01a
T 2026-10-23T12:57:53+00:00 81
R 2026-10-23T13:56:03+00:00 16a4638872fa
T 2026-10-23T13:56:03+00:00 36
R 2026-10-23T13:56:05+00:00 c35fae77929f
T 2026-10-23T13:56:05+00:00 45
R 2026-10-23T13:56:06+00:00 8df969257c86
T 2026-10-23T13:56:06+00:00 52
R 2026-10-23T14:02:06+00:00 2d93d54e305a
T 2026-10-23T14:02:07+00:00 25
```

- The first 9 lines hash to `f30152d28183a67a123174c0e91572a6f2ef8b685b78cee0c8a86d59d0fe217b` (the A2 snapshot), which proves the earlier entries were never rewritten.
- Budget state: `budget_used 5, BUDGET_EXHAUSTED`.

## Router V2 shadow decisions (preserved)

`logs/lilith-router-decisions.log`, 5 lines, all `platform lilith_os`, `live:false`:

| # | chat_id | mode | reason |
|---|---|---|---|
| 1 | f8b-s1 | social | conversational default |
| 2 | f8b-s1 | social | conversational default |
| 3 | f8b-s2 | social | conversational default |
| 4 | f8b-core | technical | bare technical term (safe default) |
| 5 | lilith-os-b4734155-e4da-4e22-a03f-4305f2bd0f3c (UI) | social | conversational default |

- **Root-only copies on DEV:** `/var/backups/hermes-gateway-dev/f8r4-evidence/` (`SHA256SUMS` inside).
- **A3 hashes:**
  - decisions (4 lines) `857174ee…a9`;
  - ledger `f30152d2…7b`;
  - gate journal `a9b7e112…a1`.
- **A5 copies:** `gate-journal-a5.txt`, `lilith-router-decisions-a5.log` and `gate-ledger-a5.log`, appended to the same `SHA256SUMS`.

## DR-5 results

`F8_DR5_EQUAL 7fe21378bb97f57aed3a6c60f6fc216e08d646f9da42d9c35feb7509f5468f1c` at every checkpoint:
- U-0, G-1b, G-3b;
- after R-1 (G-6 stop), G-6 re-run, after R-1 (G-7 stop);
- A0, A1, A2b, A3, A5.

The host observation vs G-1 was EQUAL (6/6 sections) at every one of those checkpoints. Protected services were unchanged throughout: api 176771, broker 3411, authority 128648, witness 127192, 0 restarts, same InvocationIDs.

## Accepted deviations

| ID | Deviation | Disposition |
|---|---|---|
| P7 | GCE `/etc/hosts` maps `metadata.google.internal` (carried over from Phase A) | ACCEPTED_DEVIATION; the probe expects `HOSTS_ONLY`, and no packets are sent |
| N-1 | Hermes exits 1 on SIGTERM, so the unit shows `failed` after every stop | accepted; operational note |
| D-G6 | The first G-6 readiness check ran at +9 s; the gate binds at about +31 s. G6_FAIL → R-1 → owner Option A re-run PASS | accepted; wrapper fixed |
| D-G7 | The first G-7 hold wrapper scanned the whole gate journal and matched G-6b's CONNECT probe. Stopped after valid request #1 → R-1 | accepted; position-based wrapper |
| D-ALLOC | Amended allocation: #1 = G-7 turn 1; #2–#4 via `smoke_resume.py` (harness importing the reviewed smoke read-only); #5 = G-10 | owner-approved (A0–A5) |
| D-S5.1 | Turn 1's HTTP `state: completed` was not observable (client killed); proven from stored state (`TURN1_REPLY_OK`) | accepted |
| D-S9 | "Same gateway process" holds per run (turns ran on 221439, 227336; G-10 on 231245) | accepted; C5–C8 cover continuity |
| D-C9 | The turn-2 request structure (C9) was proven against the synthetic provider in the WSL mirror, not observed at real Groq | accepted; recorded as mirror-only |
| D-GATE | Gate fork-to-bind about 31 s (cause unknown; within 90 s) | accepted; open item |

## Open issues carried into F9

1. Hermes first-message profile-onboarding injection (`api_content` system note).
2. Hermes conversation-history and log erasure (FORGET) gaps.
3. Preserving LILITH's governed First Memory design.

## Environment state at acceptance (unchanged by this record)

- Gateway and gate are running, static (not enabled). The budget is exhausted, so any further provider request is refused locally.
- The key stays root-only on DEV.
- `/var/tmp/f8` (package + amend harness) and the backups remain until the owner decides on housekeeping.

## Local evidence index

`dev-run/*.out` (each ends with the sha256 of its DEV-side file):

| Step | Output sha256 (prefix) |
|---|---|
| A0 | `d3682a28` |
| A1 | `f822f7f2` |
| A2 | `68413e0e` |
| A2b | `d225766b` |
| A3 | `721a939d` |
| A5 | `40c1934c` |
| G-6 re-run | `a4f3b06a` |
| G-7 stop | `d8c862ba` |
| R-1 | `780e54dc` |
| post-G7 | `e28f1676` |

The file hashes of the whole folder are in `EVIDENCE-SHA256SUMS`.
