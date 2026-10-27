# F8r4 Phase B: amended continuation plan after the G-7 stop (for owner approval)

**Prepared:** 2026-10-23, after the owner's request for a narrowly amended allocation.

**Status:**
- Nothing has been sent to DEV, PROD or Groq since the G-7 stop.
- DEV is still in the post-R-1 stopped state: budget 1/5, parity and DR-5 EQUAL (`post-G7-check.txt` sha `e28f1676…`).

## 1. Allocation (no reset; five requests in total)

| # | Use | Status |
|---|---|---|
| 1 | G-7 turn 1, `f8b-s1` (direct console) | DONE 12:57:52 (`0d00769ac01a`); evidence in STOP-G7.md |
| 2 | G-7 turn 2, `f8b-s1` (same session; continuity) | planned: `smoke_resume.py`, **held and validated before #3** |
| 3 | G-7 turn 3, `f8b-s2` (second session) | planned |
| 4 | G-7 turn 4, `f8b-core` (Core API relay) | planned |
| 5 | G-10: one synthetic message through the unmodified finalized UI → Core API → Hermes → gate | planned; afterwards the gate is `BUDGET_EXHAUSTED` |

- The prompts are byte-identical to `smoke_console.py`.
- No RESET line is ever written, and every attempted upstream request counts.
- The gate enforces 5 as a hard ceiling on its own (verified: a 6th turn is refused locally with no upstream request).

## 2. Coverage map: original G-7 smoke checks (35) → amended evidence

| Original check | Where it is proven now |
|---|---|
| S0 ready, G0 gate up/key loaded | resume run (S0, G0) |
| S1 health, S2a/S2b 401, S3 413, S4 400 | resume run (non-spending) |
| **S5.1 turn 1 model reply** | **NOT yet proven on DEV.** The killed client never read the reply. Proven by `turn1_evidence.py` (step A0: read-only, gateway stopped; reads a private copy because Hermes leaves a WAL after SIGTERM). Must print `TURN1_REPLY_OK`, otherwise STOP. |
| S5.2 turn 2 (f8b-s1), S5.3 turn 3 (f8b-s2) | resume run (same text and sessions) |
| S6 ×9 slash commands not executed, S6z config unchanged | resume run (non-spending) |
| S10 Core API relay model reply, S11 capture 403 | resume run |
| R0 router mode shadow | resume run |
| R1 shadow decision per turn, per session | resume run for turns 2–4 (window = this run only); turn 1 from STOP-G7 evidence. **C2** proves the one earlier line is f8b-s1 `live:false`; **C4** proves the totals s1=2, s2=1, core=1, all `live:false`. |
| B1 budget delta == turns | resume run (3 for 3), plus C4 (4 reservations in total, first = `0d00769ac01a`) |
| B2 forwarded == turns, 200, capped, model pinned | resume run (3) + request #1 record; G-7d re-validates all 4 FORWARDED records (incl. `token_cap_anomaly:false` and rate-limit headers) |
| B3 no refused POST | resume run window + request #1 window (only GET probes; verified from timestamps in `post-G7-check.txt`) |
| K0, K1 key never exposed, K2 lilith cannot read | resume run. K1 scans the **whole** gateway journal namespace and HERMES_HOME, so it also covers the request #1 period. |
| S7 listens 9901 only, S8 no non-loopback connections | resume run; request #1 period: 0 non-loopback recorded |
| S9 same gateway process | **Changed meaning:** per run only. Turn 1 ran on gateway PID 221439; turns 2–4 run on a new process after R-1 + G-6. **C3** adds proof that session history survived the restart (turn 2's prompt_tokens > request #1's 950). |

New cross-run checks:
- **C1:** the ledger before the run is exactly request #1.
- **C2:** the earlier decision belongs to request #1 (f8b-s1).
- **C3:** session continuity.
- **C4:** totals after the run.

## 3. Wrapper defect fix

`g7r.sh` takes the gate-journal and decisions-log offsets at its own start and validates only records after them. The rehearsal ran the same validation on the same journal with the stale G-6b CONNECT line present:
- the old whole-journal check FAILS (`CONNECT_NOT_ALLOWED:example.com:443`), reproducing the DEV stop;
- the corrected since-start check passes.

## 4. Local validation (WSL mirror, synthetic Groq only; 0 real provider calls)

`rehearse.sh`, run 3: **28/28 ok** (`rehearsal.tsv` sha `5e433df6…`, evidence `amend-rehearsal-evidence.tgz` sha `f7582e0c…`). It reproduces the DEV sequence:
1. fresh install, budget 0/5, never reset;
2. G-6b leaves the stale CONNECT line;
3. attempt 1 held at R=1, then killed + R-1, leaving budget 1/5;
4. `TURN1_REPLY_OK` from the private copy. The original state.db/-wal/-shm bytes and file set are unchanged, and the copy is removed.
5. G-6 restart;
6. `g7r.sh`: hold at R=2 validated, `F8_RESUME_PASS turns=3 38/38`, C3 continuity (synthetic provider saw 2 → 4 messages for f8b-s1);
7. G-8, G-9 (obs EQUAL, DR-5 EQUAL);
8. request #5 → 200 with a synthetic reply, then `budget_used 5, state BUDGET_EXHAUSTED`. Exactly 5 chat requests reached the provider; ledger R=5, RESET lines 1 (initial only).
9. The mirror was returned to its baseline (M0 == FINAL; stand-ins torn down).

Two earlier rehearsal runs found defects, fixed before run 3:
- the synthetic stand-in sent no `x-ratelimit-*` headers (mirror tooling only; `patch_fake_groq.py` adds Groq-style headers, and the DEV check is not loosened);
- the Hermes WAL after SIGTERM (handled by the private copy);
- a counting bug in the rehearsal script itself.

The UI leg (G-10 via Next.js) is **not** rehearsed in the mirror; the rehearsal sent request #5 to the Core API relay that the UI's server-side route calls.

## 5. Files to stage on DEV (`/var/tmp/f8/amend`, root 0700, verified by `SHA256SUMS` inside g7r.sh)

| File | sha256 |
|---|---|
| `smoke_resume.py` | `f504b39cd7ace065771e5016042620cfc053d6e3f0bcbe3f193998a245260dd3` |
| `turn1_evidence.py` | `6243c06654ef086ec35a63d53b4afa473f53eb53f3b9bd8317adc84758d37749` |
| `g7r.sh` | `3f4117a8cda189896040fec705679b791149d1aee92526571344bb197b204c17` |

These are new **harness** files outside the package. They import the installed `smoke_console.py` read-only. The package (`16c7417d…`), its units, gate config and limits are unchanged.

## 6. DEV sequence once approved (stop on any failure; R-1 on failure as before)

| Step | Action | PASS criterion |
|---|---|---|
| A0 | Stage the 3 files (+SHA256SUMS). Read-only snapshot: ledger sha256 + lines, decisions log line count; run `turn1_evidence.py` (gateway stopped) | ledger = `RESET` + `R … 0d00769ac01a` + `T … 81`; 1 decision line; `TURN1_REPLY_OK`; originals unchanged |
| A1 | G-6 re-start with the corrected readiness wrapper (as accepted in Option A) + G-6b probes | G6_PASS, G6B_PASS, budget **1/5** |
| A2 | `g7r.sh /var/tmp/f8/amend 0d00769ac01a` → requests #2–#4 + G-7d | REQUEST2_OK at the hold; `F8_RESUME_PASS turns=3`, all PASS incl. C1–C4; 4 FORWARDED valid; rate-limit headers vs O-3 (RPD 10, TPM 8000); budget 4/5 |
| A3 | G-8 retention; G-9 observation vs G-1 + DR-5 | success; `F8_OBSERVATION_EQUAL`; `F8_DR5_EQUAL 7fe21378…` |
| A4 | G-10: IAP tunnel `localhost:18765 → lilith-dev-01:8765`; unmodified UI worktree `lilith-os-devui` with DEV-only env, on `127.0.0.1:3210` (Phase A method; temporary `.claude/launch.json` entry reverted afterwards); confirm the DEV signature; send **one** synthetic message | real model reply in the UI; +1 FORWARDED (200, valid), +1 shadow decision `live:false` for the UI session; budget 5/5 `BUDGET_EXHAUSTED`; no further requests |
| A5 | Final observation + DR-5 + service parity; STOP and report. Owner G-11: Groq console shows exactly 5 requests for `lilith-dev-f8` | EQUAL; owner confirms 5 |

## 7. Residual differences and risks for the owner to accept

1. **S9 split:** turns ran on two gateway processes (by necessity). C3 covers continuity across the restart.
2. **S5.1 via stored state, not the HTTP response:** the reply is read from Hermes state.db. The console's `state: completed` field for turn 1 cannot be recovered. A0 adds a **transient private copy** of the synthetic state.db/WAL (root 0700, under `/var/tmp/f8/amend`), removed immediately afterwards.
3. **G-10 is untested in the mirror;** a UI fault could spend #5 with no reply. The gate still prevents any 6th request; a failed G-10 would leave UI end-to-end NOT PROVEN and would not be marked PASS.
4. **No hash chain:** the gate ledger is an append-only, fsync'd text log, not hash-chained. It is preserved by never writing to it except through the gate, and by recording its sha256 at A0 and after every step.
5. **Ongoing:**
   - the gate takes about 31 s from fork to bind (unexplained, within 90 s);
   - Hermes exits 1 on SIGTERM (unit shows `failed`; leaves a WAL);
   - Router decision lines store a message `preview` (FORGET scope, B-6).

---

# Revision 2 (2026-10-23, after A0 PASS): session-continuity proof. Supersedes §5 and §6 above.

## R2.1 New read-only verifier: `continuity_evidence.py`

It runs with the gateway stopped. It copies state.db + -wal into a private 0700 dir, opens the copy, and removes it afterwards; the originals are never opened. Output is roles, ids, lengths and sha256 prefixes only, never dialogue text.

| Check | Proves |
|---|---|
| C5 | exactly one `f8b-s1` session, and it is the A0 turn-1 session `20261023_125745_4cab16ae` (no substituted or child conversation) |
| C6 | its first four conversational messages are user(turn-1 prompt, exact) → assistant(non-empty, no error notice) → user(turn-2 prompt, exact) → assistant(non-empty, no error notice) |
| C7 | all four are still in model context (`active=1`, `compacted=0`) |
| C8 | turn 1 stored before the gateway restart, turn 2 after it (A1 restart epoch) |
| EFFECTIVE_SHAS | hash of the text Hermes actually sent for each message (`api_content` when Hermes rewrote it, otherwise `content`) |

**C9 (request actually assembled for turn 2):** the conversational messages of the turn-2 provider request must equal, byte-exactly and in order, `[user(turn 1 as sent), assistant(turn-1 reply), user(turn 2)]`. Persistence and a prompt-token increase are NOT accepted as proof on their own; C3 stays as a supporting check only.
- **Mirror:** the synthetic provider records each message's role, length and sha256 prefix (`patch_fake_groq_msgs.py`, mirror-only, no text).
- **DEV:** the real request body is not observable by design. The gate logs no bodies, and changing that would alter the package and widen data exposure. C9 is therefore proven in the mirror on the identical release bytes (`16c7417d…`). On DEV, C5–C8 plus EFFECTIVE_SHAS plus C3 are required.

## R2.2 Local results (WSL mirror, synthetic Groq, 0 real calls)

- **Focused tests:** `test_continuity.py` **16/16**. The good case passes. Every negative case is rejected:
  - substituted second session; wrong session id; child session;
  - turn 2 in a new session; wrong order; non-synthetic turn-1 text; error-notice reply;
  - compacted or inactive turn-1 messages; turn 2 stored before the restart;
  - turn-2 request missing the prior assistant, reordered, carrying a foreign assistant text, or with no history.
- **Full rehearsal:** **36/36** (`amend-rehearsal2-evidence.tgz` sha `b8cbd307…fa5d`). All earlier rows plus:
  - C5–C8 4/4 `CONTINUITY_STORED_OK`, with the restart between turn 1 and turn 2;
  - originals (state.db/-wal/-shm, ledger, decisions) unchanged, private copy removed;
  - verifier output has no dialogue text;
  - **C9 PASS:** turn-2 request = user(t1) → assistant(t1 reply) → user(t2), byte-exact against the stored sent text (`u1=d08326f8… a1=d06ef692… u2=d6e0184c…`);
  - budget accounting unchanged: R=5, 1 RESET (initial), BUDGET_EXHAUSTED after #5, G-10 shadow decision present.
- **First C9 attempt FAILED, correctly:** the turn-1 user text Hermes sends differs from what it stores as `content`. See R2.4.

## R2.3 Harness files for DEV (supersedes §5)

| File | sha256 | Status on DEV |
|---|---|---|
| `smoke_resume.py` | `f504b39c…60dd3` | staged at A0 |
| `turn1_evidence.py` | `6243c066…37749` | staged at A0 (used) |
| `g7r.sh` | `3f4117a8…04c17` | staged at A0 |
| `continuity_evidence.py` | `e7a6b7a104fbf1e2086ca25fadeaac4e285af9552502f9738b95dd66146ac513` | **new: to stage at A1** (added to `/var/tmp/f8/amend/SHA256SUMS`) |

The package `16c7417d…` is unchanged. `test_continuity.py`, `patch_fake_groq*.py` and `rehearse.sh` are mirror-only.

## R2.4 New finding: Hermes first-message onboarding rewrite (privacy-relevant)

- For the first message of a session, Hermes stores the user text in `content` but sends `api_content`. That is the user text plus a hidden `[System note: This is the user's very first message ever …]`.
- The note instructs the model to mention `/help` and to OFFER to build a user profile ("name, what they do, how they like you to work").
- This explains DEV turn 1's reply. It is harmless under synthetic-only use, but it **must be reviewed or disabled before any real conversation** (it solicits personal data and creates a profile flow outside FORGET).
- On DEV, A2b will report whether the turn-1 `api_content` is present (expected: yes).

## R2.5 Amended DEV sequence A1–A5 (supersedes §6; stop on any failure, R-1 on failure)

| Step | Action | Requests | PASS criterion |
|---|---|---|---|
| A1 | Stage `continuity_evidence.py` (hash-verified). Record the restart epoch. G-6 start with the corrected readiness wrapper + G-6b probes. | 0 | G6_PASS (9901, 9911, gate START ≤ 90 s; gate uid dynamic, CapEff 0); G6B_PASS; budget **1/5**; ledger sha = A0 `ca3c5c5b…` |
| A2 | `g7r.sh` → #2 held and validated, then #3, #4; G-7d | 3 | `F8_RESUME_PASS turns=3`, all PASS incl. C1–C4; 4 FORWARDED valid (200, model, cap, no anomaly, rate-limit headers vs O-3); budget 4/5 |
| **A2b** | R-1 stop; `continuity_evidence.py --expect-session 20261023_125745_4cab16ae --restart-epoch <A1>`; originals hash-unchanged | 0 | **C5–C8 PASS**, `CONTINUITY_STORED_OK`, EFFECTIVE_SHAS recorded, onboarding rewrite reported; then G-6 restart (G6_PASS, budget 4/5) |
| A3 | G-8 retention; G-9 observation vs G-1 + DR-5 | 0 | success; EQUAL; `F8_DR5_EQUAL 7fe21378…` |
| A4 | G-10: IAP tunnel `localhost:18765` → DEV 8765; unmodified `lilith-os-devui` with DEV-only env on `127.0.0.1:3210` (temporary `.claude/launch.json` entry reverted afterwards); DEV signature confirmed; **one** synthetic message | 1 (#5) | real reply in the UI; +1 FORWARDED valid; +1 shadow decision `live:false` for the UI session; budget 5/5 `BUDGET_EXHAUSTED` |
| A5 | Final observation + DR-5 + service parity; STOP. Owner G-11: Groq console shows exactly 5 requests | 0 | EQUAL; owner confirms 5 |

## R2.6 Amended coverage map (original G-7 + continuity)

| Requirement | Proof |
|---|---|
| S0–S4, S6, S6z, S10, S11, R0, K0–K2, S7, S8 | A2 resume run (as in §2) |
| S5.1 turn-1 reply | **A0 PASS** (`TURN1_REPLY_OK`) |
| S5.2, S5.3 | A2 |
| R1 per-turn shadow decisions | A0 (turn 1) + A2 (turns 2–4) + C2/C4; G-10 adds f8b-ui at A4 |
| B1–B3 budget accounting | request #1 record + A2 (B1–B3, C1, C4) + G-7d; A4 brings it to 5/5 |
| S9 | per run (two gateway processes; accepted change) |
| Session continuity, stored | **A2b C5–C8** |
| Session continuity, sent to provider | **C9: mirror only** (same release bytes); DEV supporting: EFFECTIVE_SHAS + C3 |
| No substituted conversation after the restart | A2b C5 (single session = A0 session id) + C8 |

## R2.7 Residual risks (adds to §7)

6. **C9 is not observable on DEV** (no request bodies by design). DEV proof of "the model received the prior context" rests on the mirror run of identical code, plus DEV stored-history and token evidence.
7. **The first-message onboarding rewrite (R2.4)** is active on DEV.
8. **A2b adds one more gateway stop and start** (gate bind about 31 s; Hermes exits 1 on SIGTERM; the WAL is left behind, which the private copy handles).
