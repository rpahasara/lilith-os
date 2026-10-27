# F8r4 Phase B on lilith-dev-01: result (2026-10-23, 12:28–14:03 UTC)

**Package:** `16c7417dc97a11ba6cf65fe44ef639e255bff22257f65d5f9bcefaab1af9d41a` (release `f293e72-f8r4`); F8r2 preserved for restore.

**Status:**
- Every reviewed gate and the owner-approved amended continuation (A0–A5) are complete.
- **Real Groq requests: 5 of 5** (budget exhausted, never reset).
- STOPPED for owner acceptance. The acceptance itself is the owner's act, and G-11 (Groq console count) is the owner's check.

## Real Groq requests (gate ledger, `R` lines; every one FORWARDED, status 200, `openai/gpt-oss-120b`, stream, cap 1024, `token_cap_anomaly:false`)

| # | Request id | When (UTC) | Scenario | Prompt / completion tokens | Rate-limit remaining (req / tok) |
|---|---|---|---|---|---|
| 1 | `0d00769ac01a` | 12:57:52 | G-7 turn 1, `f8b-s1` (console) | 950 / 81 | 9 / 6673 |
| 2 | `16a4638872fa` | 13:56:03 | G-7 turn 2, `f8b-s1` (same session, after a gateway restart) | 1035 / 36 | 8 / 6602 |
| 3 | `c35fae77929f` | 13:56:05 | G-7 turn 3, `f8b-s2` (second session) | 732 / 45 | 7 / 6069 |
| 4 | `8df969257c86` | 13:56:06 | G-7 turn 4, `f8b-core` (Core API relay) | 730 / 52 | 6 / 5786 |
| 5 | `2d93d54e305a` | 14:02:06 | G-10, finalized UI → Core API → Hermes → gate | 730 / 25 | 5 / 6884 |

- The rate-limit headers report `limit-requests 10` and `limit-tokens 8000`, which equal the owner's project RPD 10 and TPM 8,000 (O-3). RPM and TPD are not reported in the headers.
- The ledger is the initial RESET plus 5 R/T pairs. RESET lines: 1 (initial only).
- The budget is `budget_used 5, state BUDGET_EXHAUSTED`. Day output tokens: 239.
- Final ledger sha256: see `f8r4-evidence/SHA256SUMS` on DEV.

## Results by gate

| Gate | Result |
|---|---|
| U-0, G-2, G-1/G-1b, U-1, G-3/G-3b, G-4, G-5, G-5b (owner), G-5c | PASS (see NOTES.md) |
| G-6 (first) | **FAIL**: the wrapper checked 9911 at +9 s, but the gate binds at about +31 s. R-1 applied. Option A re-run: **PASS** |
| G-6b | PASS (sandbox 23/23, gate probe) |
| G-7 (first) | **STOPPED after request #1**: the hold-wrapper defect (whole-journal scan matched G-6b's CONNECT probe). R-1 applied. Request #1 was itself valid. |
| A0 | PASS: `TURN1_REPLY_OK` from a private state.db/WAL copy; originals hash-identical |
| A1 | PASS: verifier staged; G-6/G-6b with budget 1/5 |
| A2 = G-7 turns 2–4 + G-7d | PASS: hold on #2 validated; `F8_RESUME_PASS turns=3 38/38`; C1–C4 PASS |
| A2b continuity | PASS: C5–C8 `CONTINUITY_STORED_OK`; originals unchanged; restart G-6/G-6b PASS (budget 4/5) |
| A3 = G-8 + G-9 | PASS: retention success; observation EQUAL; DR-5 EQUAL; evidence preserved |
| A4 = G-10 | PASS: exactly one POST `/api/lilith/conversation` → 200, `state: completed`, real reply rendered in the UI |
| A5 | PASS: budget 5/5; request #5 valid; 1 new shadow decision; key absent; final parity |

## Original G-7 acceptance (35 smoke checks) and how each is proven

- **Turn 1 (S5.1, R1, B1–B3 for request #1):** A0 + STOP-G7 evidence. The one exception is the console's HTTP `state: completed` field for turn 1, which is not recoverable because the killed client never read it. The stored assistant reply (172 chars, no error notice) stands in for it.
- **All other checks:** A2's resume run, 38/38 (S0–S4, S5.2, S5.3, S6×9, S6z, S10, S11, R0, R1×3, B1–B3, K0–K2, S7–S9), plus C1–C4.
- **S9** ("same gateway process") holds per run only. Turn 1 ran on PID 221439 and turns 2–4 on 227336; G-10 ran on 231245.
- Real replies (synthetic prompts):
  - turn 2 answered "Your previous turn was turn 1." (continuity);
  - turn 3 gave one sentence on synthetic text;
  - turn 4 confirmed the relay.

## Continuity

- **Stored, DEV, A2b:** exactly one `f8b-s1` session `20261023_125745_4cab16ae`. Its messages are user(t1) → assistant → user(t2) → assistant, all active and not compacted. Turn 1 was stored before the A1 restart (epoch 1792763643) and turn 2 after it.
- **Sent text:** the DEV effective sent-text hash of turn 1, `d08326f8f5a1f7e4`, is byte-identical to the mirror's.
- **C9 (request actually assembled for turn 2):** proven against the **synthetic provider in the local WSL mirror** (36/36), on identical release bytes. **It is not independently observed at real Groq**, because the gate logs no request bodies by design. DEV supporting evidence:
  - turn 2's prompt_tokens 1035 > turn 1's 950;
  - the reply referenced turn 1.

## Router V2 shadow evidence (`logs/lilith-router-decisions.log`; preserved copies under `/var/backups/hermes-gateway-dev/f8r4-evidence/`, root 0700)

5 lines, all `platform lilith_os`, `live:false`:

| Session | Mode | Reason |
|---|---|---|
| f8b-s1 (turn 1) | social | conversational default |
| f8b-s1 (turn 2) | social | conversational default |
| f8b-s2 | social | conversational default |
| f8b-core | technical | bare technical term (safe default) |
| `lilith-os-b4734155-e4da-4e22-a03f-4305f2bd0f3c` (UI) | social | conversational default |

Router mode is shadow; `cognitive_enabled: false`; `canonical_ltm_enabled: false`.

## Service integrity (final, A5)

- DR-5 `F8_DR5_EQUAL 7fe21378…` at every checkpoint.
- Observation vs G-1: EQUAL in all 6 sections at every checkpoint.
- Release verify full PASS. Core API ok.
- Protected services unchanged throughout (0 restarts, same InvocationIDs): api 176771, broker 3411, authority 128648, witness 127192.
- Gateway 231245 and gate 231242 are active, static (not enabled), 0 restarts. Listeners are exactly `127.0.0.1:9901` and `127.0.0.1:9911`; 0 non-loopback gateway connections.
- Gate: uid 64597 (dynamic), CapEff 0, NoNewPrivs. The key is absent from HERMES_HOME, the gateway journal and the gateway environ; lilith cannot read the credential.

## Local leftovers (all reverted)

- The IAP tunnel `localhost:18765 → lilith-dev-01:8765` is stopped.
- The UI dev server on `127.0.0.1:3210` is stopped.
- The temporary `.claude/launch.json` entry is reverted byte-exact (`f911f307…`).
- `lilith-os-devui` is clean at `b9eb32c`. No commits, pushes or UI changes.

## Unresolved issues (must be addressed before any personal conversation)

1. **Hermes first-message onboarding injection (OPEN, must be corrected).** For a session's first message, Hermes sends `api_content` = the user text + a hidden "[System note: … very first message ever … OFFER … to build a short profile … name, what they do …]". The model then solicits personal data (DEV turn 1 did). The G-10 UI session (a new session) did not show it in its reply; whether the note fires once per user is not verified.
2. **FORGET gap (B-6):** Hermes state.db, gateway logs, Router `preview` fields and provider-held data are not covered by FORGET.
3. **C9 is mirror-only** (no request-body observation on DEV).
4. **Gate startup about 31 s** from fork to bind (reproducible, cause unknown; within the 90 s limit).
5. **Hermes exits 1 on SIGTERM** (unit shows `failed`; WAL left behind).
6. **Budget exhausted:** any further provider use needs a separate owner decision (RESET via `gate_budget.sh reset --owner-approved`).
7. **G-11 (owner):** confirm the Groq console shows exactly 5 requests for `lilith-dev-f8`.
8. **Owner housekeeping, when decided:**
   - revoke the key if Phase B is not continued;
   - purge `/var/tmp/f8` (incl. `/var/tmp/f8/amend`);
   - the earlier quarantines under `/var/backups/hermes-gateway-dev`.
