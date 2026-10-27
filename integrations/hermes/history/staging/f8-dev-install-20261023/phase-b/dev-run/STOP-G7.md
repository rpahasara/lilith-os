# STOP at G-7 (F8r4 Phase B, lilith-dev-01, 2026-10-23 12:57 UTC)

**Status:**
- **1 real Groq request made** (budget 1/5; ledger `R 12:57:52 0d00769ac01a`, `T 81`).
- The smoke was killed while held, before any 2nd request. R-1 applied.
- G-7d, G-8, G-9 and G-10 were NOT run.

## Request #1 (held and validated; it passed every request-level check)

| Field | Value |
|---|---|
| Gate record | FORWARDED, status **200** (authenticated), model `openai/gpt-oss-120b`, stream |
| Tokens | max_completion_tokens 1024; prompt 950 / completion 81; `token_cap_anomaly:false` |
| Timing and size | 718 ms; bytes in 21,258 / out 4,332; dropped_fields [] |
| Rate-limit headers | limit-requests **10** (= project RPD 10), limit-tokens **8000** (= project TPM 8,000), remaining 9 / 6,673 |
| Budget | used 1, day_requests 1, day_output_tokens 81 |
| Router V2 shadow decision (real inference turn) | `platform lilith_os`, `chat_id f8b-s1`, `mode social`, confidence 0.5, reason "conversational default", **`live:false`**; 1 line, the only one in the log |
| Gateway | 0 non-loopback connections |

## Why it stopped (false positive in my hold wrapper)

- The validator scanned the gate's whole journal instead of only lines written after the smoke started.
- It found `REFUSED CONNECT example.com:443` (405) at **12:52:50**: the deliberate G-6b probe P20, five minutes before the smoke.
- During the smoke the only refusals were Hermes' local GET capability probes (404, never forwarded), which the smoke's own B3 check allows.
- So no unexpected provider behaviour occurred. The stop came from the wrapper, not the system.

## After R-1 (`post-G7-check.txt` sha `e28f1676…3207`)

- Gateway, gate and timer are stopped; 9901 and 9911 are closed. The gateway shows `failed` (Hermes exits 1 on SIGTERM; N-1).
- Protected services unchanged: api 176771, broker 3411, authority 128648, witness 127192, 0 restarts, same InvocationIDs.
- Observation vs G-1: EQUAL in all 6 sections. DR-5: `F8_DR5_EQUAL 7fe21378…`. Core API ok.

## Budget consequence (owner decision)

- 4 requests remain. The runbook needs 4 (G-7 smoke) + 1 (G-10) = 5. The owner forbids a reset and caps the total at 5.
- **A:** re-run the unmodified G-7 smoke (4 requests → 5/5) with a corrected hold (lines since the smoke start only).
  - G-7d/G-8/G-9 then run normally.
  - G-10 sends one UI message, which must be refused by the gate with BUDGET_EXHAUSTED and **no upstream request**. That proves UI → DEV → Hermes → gate and budget enforcement, but not a real model reply through the UI.
- **B:** G-10 with a real request (#2) through the UI, and G-7 stays a partial (1 of 4 turns validated; no Core API relay turn, no multi-session evidence).
- **C:** an owner-approved budget RESET (total 6). This changes the owner's 5-request condition and needs an explicit amendment.
