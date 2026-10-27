# F8 Phase B: completed design and f8r3 package (direct Groq, DEV only)

**Status:** DESIGNED, BUILT, LOCALLY VALIDATED against a SYNTHETIC Groq provider in the WSL DEV mirror.
- No DEV change, no provider account or credential, no real provider call.
- No PROD contact, no commit or push.
- Phase A (`269dde95…`, owner-accepted) is still the running DEV state.

**Package:** `hermes-gateway-dev-f293e72-f8r3.tar.gz`, sha256 **`3938796f9477fc4641fe8cd1f09a92814cc980b7744ae2f20276b117e958bc6e`** (deterministic: two builds, identical bytes).
**MANIFEST:** 14,305 files, sha256 `63ea7ebdc16434db81186668b3c3d49ddd5ab6bce1c0368ca01dec11c9322ef2`.

## 1. Groq facts verified (official docs, 2026-10-23; re-check at owner setup)

| Topic | Finding | Source |
|---|---|---|
| Model | `openai/gpt-oss-120b`: 131,072 context, 65,536 max output. Listed prices are $0.15 per 1M input tokens, $0.075 per 1M cached input and $0.60 per 1M output. | [model page](https://console.groq.com/docs/model/openai/gpt-oss-120b) |
| Reasoning | `reasoning_effort` low / medium / high; `include_reasoning` (default true); reasoning returned in `message.reasoning`; `reasoning_format` not supported for GPT-OSS | [reasoning](https://console.groq.com/docs/reasoning) |
| Data / ZDR | By default Groq does not retain inference inputs/outputs, except reliability/abuse logs for up to 30 days. ZDR (in Data Controls, org admin, global or per-feature) stops those. Data is stored in US GCP. The Services Agreement says "Eligible Customers" for ZDR, while the docs say "all customers". **Owner must confirm ZDR is shown as enabled.** | [your data](https://console.groq.com/docs/your-data), [services agreement](https://console.groq.com/docs/legal/services-agreement) |
| Projects | Isolated workspace with **project-scoped API keys**. Custom per-project rate limits can be set ≤ org limits (examples are RPM). ITPM/OTPM are org-level only. No project-level spend limit. | [projects](https://console.groq.com/docs/projects) |
| Spend limits | **Paid plans only, org-wide (all keys), monthly**, resetting on the 1st. Hard block (400 `blocked_api_access`), but usage is updated every 10–15 min, so a small overrun is possible. No per-key or per-project limit. | [spend limits](https://console.groq.com/docs/spend-limits), [billing FAQ](https://console.groq.com/docs/billing-faqs) |
| Rate limits | The Developer-plan table lists gpt-oss-120b at 30 RPM / 1K RPD / 8K TPM / 200K TPD. **Free-tier numbers were not retrievable; the console Limits page is authoritative.** 429 responses carry `retry-after`. | [rate limits](https://console.groq.com/docs/rate-limits) |

**B-1 answer:**
- The **free tier is likely sufficient for the 5-turn acceptance**. Those 5 requests are far below any plausible free RPD/TPD. But the free tier has **no spend-limit feature**: free usage costs nothing, but the cap is only rate limits.
- If you prefer a paid account for ZDR eligibility or certainty, set the org spend limit to the minimum the console allows. I propose USD 5/month and usage alerts at USD 1.
- Spend is also bounded locally (§3): at most **5 upstream requests ever** until you reset the budget, and **≤ 1,024 output tokens each**. That is about 5 × (≈ 2–3k input + ≤ 1,024 output) tokens, **< USD 0.01** at the listed prices.

## 2. Credential architecture (B-2): credential-injecting provider gate

**Problem stated by the owner:** a gateway that cannot access the key, behind a blind TLS proxy that cannot insert it, cannot authenticate.

**Solution:** the gateway never talks TLS to Groq. It talks plain HTTP on loopback to a **separate gate process that is the only holder of the key**, and the gate makes the TLS call.

```
Hermes gateway (uid lilith, loopback-only sandbox, NO key, NO DNS)
   │ POST http://127.0.0.1:9911/openai/v1/chat/completions   Bearer __LILITH_GATE_CLIENT_TOKEN__ (non-secret)
   ▼
hermes-provider-gate-dev (systemd DynamicUser, its own sandbox)
   • key: LoadCredential=groq-api-key:/etc/hermes-provider-gate-dev/credentials/groq-api-key (root 0600, dir 0700)
     → /run/credentials/<unit>/groq-api-key, readable ONLY by the dynamic uid (not by lilith = gateway + Core API)
   • policy: path == /openai/v1/chat/completions; model ∈ {openai/gpt-oss-120b}; tools/functions/response_format…
     refused; n=1; max_completion_tokens = min(asked, 1024); reasoning_effort default low; 256 KiB body cap
   • budget (persistent, before any upstream call): 5 requests total (owner resets), 10/day, 10k output tokens/day
   • TLS to the single host api.groq.com:443, system CA store, hostname verified; resolved IP must be global unicast
   • never retries; streams the reply back; one metadata log line per request (never content, never the key)
   ▼
api.groq.com (ZDR on; DEV project-scoped key)
```

Least privilege, as tested in the mirror:
- **Gateway:**
  - the key is absent from its environment, command line, HERMES_HOME, logs and journals;
  - uid `lilith` cannot read the key file or the gate's credential;
  - its sandbox still allows only `127.0.0.1` (no DNS, metadata, internet or PROD);
  - it has no non-loopback connection.
- **Gate:**
  - the key is held as a credential **file**, not in its environment;
  - its sandbox denies metadata, the VPC, RFC1918, CGNAT, other loopback addresses and IPv6;
  - it allows only `127.0.0.1` (listen), `127.0.0.53` (DNS) and public internet. The code additionally restricts upstream to the one host.
- **Provisioning (owner action G-5b):** `provision_provider_key.sh` reads the key from your **interactive** terminal (hidden input, `gsk_` format check, refuses pipes or an existing key) and prints only a sha256 prefix.
- **Revocation:** in the Groq console. R-2 moves the key file into a root-only quarantine for a later purge.
- **Without a key:** the gate still starts (placeholder credential) and answers 503 `KEY_NOT_PROVISIONED`, so the gateway replies with an error notice and nothing goes upstream.
- **Hermes side:** `model.provider: custom`, `base_url: http://127.0.0.1:9911/openai/v1`, `api_key: __LILITH_GATE_CLIENT_TOKEN__`, `context_length` set. There is no built-in groq provider at f293e72. The PROD Groq user plugin would load `$HERMES_HOME/groq.env`, which install and verify forbid.

**Residuals:**
- The gate's client token is readable by uid `lilith`, so the Core API process could also call the gate. That is bounded by the same budget, model and cap.
- The gate's IP filter allows `127.0.0.1`, so it could reach other loopback services, but its code only connects to the resolved upstream.

## 3. Request bounds (B-3)

| Layer | Bound |
|---|---|
| Acceptance plan | exactly **5 synthetic turns**: 3 direct + 1 Core API relay (smoke G-7) + 1 UI turn (G-10) |
| Gate (authoritative) | **5 upstream requests in total** (persistent; reset only via `gate_budget.sh reset --owner-approved`); 10/day; 10k output tokens/day; `max_completion_tokens` ≤ 1024 |
| Hermes | `api_max_retries: 1` (one attempt), `empty_response_guard` off, no fallback provider, `title_generation` off, `compression` off, `reasoning_effort: low`, `max_turns: 4`, zero tools; `max_concurrent_sessions: 8` caps *open sessions* (a value of 1 refused every second console session) |
| Probes | Hermes sends local capability GETs (`/props`, `/version`, `/models`, `/api/tags`); the gate answers 404 locally and **never forwards** them |
| Groq | project rate limits (owner); org spend limit if paid |

Mirror proof:
- 4 smoke turns = 4 gate requests = 4 provider requests, each `max_completion_tokens: 1024`, `reasoning_effort: low`, no tools, key injected.
- Turn 5 used the last budget slot. Turn 6 was refused (`BUDGET_EXHAUSTED`) with **0** upstream requests.
- An upstream 500 produced exactly **1** attempt and no retry.
- Slash commands consumed no budget.

## 4. Startup readiness (B-4): minimal adapter correction (reviewed diff, 74 lines; `76948218…` → `8c3b0055…`)

1. `submit()` returns state `starting` while the gateway runner's `_startup_restore_in_progress` is set. HTTP answers **503 `{"error":"starting"}`** and nothing is dispatched. The Core API surfaces it as 502 "starting".
2. `on_processing_complete(SUCCESS)` does not resolve a waiter during startup restore, because the replayed turn delivers the real reply.
3. **Per-session serialization:** turn N+1 is dispatched only after turn N's `on_processing_complete` (the session's idle event; 180 s self-heal).
   - **Defect found in the mirror:** a second turn sent ~30 ms after the first reply was queued by Hermes as a busy-session follow-up. Turn 1's completion hook (FIFO) then resolved turn 2's waiter with an empty reply, and turn 2's real reply was lost or delivered one turn late.
   - After the fix, back-to-back turns in one session both return their real replies (smoke S5.1/S5.2).

Race test: three turns sent at listener-up after a restart produced **no empty replies**.

## 5. Session privacy and logging (B-5)

- **VALIDATE profile** (installed by f8r3): INFO logging (inbound previews written; synthetic text only), 7-day history, 7-day logs.
- **OPERATE profile:** `apply_profile.sh operate`, prepared and mirror-tested. It sets:
  - `logging.level: WARNING`, so INFO message previews are no longer written (verified: no `msg=` line for the turn);
  - `sessions.retention_days: 1` and an idle reset after 60 min, so **history is 24 h**;
  - the retention drop-in: prune at 1 day, logs and the decisions log at **2 days**;
  - the journal namespace at **2 days**.

  The switch is C-3-guarded, re-pins the critical set and keeps protected services unchanged.
- **Secrets:** the key never enters the gateway. The gate logs metadata only. A check confirms the key is absent from all gateway-reachable files and journals.

## 6. FORGET gap (B-6), stated explicitly

- Hermes `state.db`, transcripts, logs, the decisions log and the gateway journal namespace are **not** covered by the L18_V2 FORGET path.
- Groq-side data is outside our control. With ZDR on and the default no-retention-for-inference policy, Groq states it keeps no inputs/outputs, but **we cannot erase or verify erasure on Groq's side**.
- Phase B therefore stays **synthetic-only**. A Hermes-DEV erasure adapter, invoked by the FORGET runner, must exist and be tested **before any real personal conversation or genuine First Memory recording**.

## 7. Router V2 evidence (B-7)

- Every model turn must leave a **Router V2 decision line** in `logs/lilith-router-decisions.log`: `chat_id` = the turn's session, `live: false`, a classification (`mode` = social/work/…) and its signals. `router.yaml mode` must be `shadow`.
- This evidence is independent of the reply text. It is cross-checked against the gate's per-request log and the provider-side request records (count equality).
- Mirror: 4/4 turns produced decision lines (`social / conversational default`, `live: false`).
- If decisions are missing, the smoke test fails (R1) and the acceptance **stops**. A plain Hermes reply is not accepted as proof.

## 8. Installation path on DEV (when authorized)

Upgrade from the running Phase A:
1. G-1 (backup + observation + DR-5) and G-2 (transfer + verify `3938796f9477fc4641fe8cd1f09a92814cc980b7744ae2f20276b117e958bc6e`).
2. **R-1, then R-2 of f8r2** with the f8r2 package's `rollback.sh`. The Phase A runtime state goes to quarantine. Mirror-tested: CLEAN.
3. f8r3 G-3 install, G-3b DR-5, G-4 F7 suite, G-5 token.
4. **G-5b, an owner action:** `provision_provider_key.sh`, typed interactively.
5. G-6 start: the gateway pulls in the gate.
6. G-7 smoke `--phase B --core-api`: 4 turns, R1/B1–B3/K0–K2.
7. G-7b sandbox probe (23 checks, including the explicit P7) and G-7c gate probe.
8. G-8 retention, G-9 parity + DR-5.
9. G-10: one UI turn (the 5th budget slot).
10. STOP for acceptance. The OPERATE profile only after acceptance.

## 9. Remaining owner actions (none taken)

1. **Create a separate Groq DEV project and a project-scoped API key.** Name the project e.g. `lilith-dev-f8`. Never reuse a PROD key.
2. **Enable ZDR** (Data Controls, org-wide) and confirm it shows as enabled.
3. **Set project rate limits** at or below the org limits (e.g. 2 RPM; whatever the console offers).
4. **Free tier or paid:**
   - free: confirm the Limits page covers gpt-oss-120b, and record that there is no spend-limit feature;
   - paid: set the org spend limit (≈ USD 5/month) and usage alerts.
5. Authorize the f8r3 DEV install (a separate decision) and type the key at G-5b yourself.
6. Accept the adapter change (B-4, `8c3b0055…`) and the new gate component.
7. Decide when to apply the OPERATE profile, and when to build the Hermes-DEV FORGET adapter (B-6).

## 10. Local validation evidence (WSL DEV mirror, synthetic Groq)

**Mirror:**
- Real Core API at b9eb32c; stand-in broker, authority and witness with DEV unit texts.
- Full DR-5 ladder + deployer. The pinned DR-5 reproduces the DEV block `7fe21378…` byte for byte.
- **Synthetic Groq:** a test-CA `api.groq.com` certificate on a dummy global IP `1.2.3.4`, a synthetic `gsk_` key, and a request recorder. It answers with gpt-oss-style `reasoning` fields and SSE streaming.

**Final run (run 6, package `3938796f…`): 61/61 rows PASS/CLEAN.** Confirmation run 7 on the identical package: **61/61 PASS/CLEAN** (evidence `run7-evidence.tgz` `fee41fb1…`; run 6 `run6-evidence.tgz` `7cc2b471…`).

| Area | Result |
|---|---|
| Upgrade from Phase A | f8r2 installed + running → f8r2 R-1/R-2 → CLEAN (obs == G-1 == M0, DR-5 EQUAL) |
| Install / F7 | staged; DR-5 EQUAL; F7 19/19 including the B-4 adapter; verify full PASS without and with the key |
| G-5b key | interactive provisioning via pty works; empty / non-key input refused |
| G-6 | gateway + gate active, 0 restarts, static; listeners exactly 127.0.0.1:9901 and 127.0.0.1:9911; the gate runs as a dynamic user |
| B-4 race | 3 turns at listener-up after a restart: no empty replies |
| G-7 smoke | 35/35: 4 model turns with real (synthetic) replies; Router V2 decision per turn (R0/R1); gate budget +4, 4 forwarded, ≤ 1024 tokens; no refused POSTs; key absent everywhere the gateway can reach (K1); lilith cannot read the key (K2) |
| Provider side | 4 requests, all `auth_ok`, model pinned, `max_completion_tokens: 1024`, `reasoning_effort: low`, no tools, UA `lilith-f8-gate/1` |
| G-7b / G-7c | gateway probe 23/23 (P7 explicit); gate probe PASS (metadata, VPC, RFC1918, CGNAT, other loopback blocked; key not in the gate's environment; credential readable only by the gate uid) |
| Budget | turn 5 used the last slot (5/5); turn 6 refused `BUDGET_EXHAUSTED`, upstream +0 |
| Gate policy | tools 400, model 400, token 401, path 404, size 413, GET 404, CONNECT 405; upstream +0 |
| Failures | upstream 500 → exactly 1 attempt, no retry; no key → the gate runs, 503 `KEY_NOT_PROVISIONED`, upstream +0; gate SIGKILL ×4 → StartLimit, gateway stays up; gate.json tamper → gateway start refused (hash + limits) |
| G-8 / G-9 | retention success; protected services identical throughout; observation EQUAL with both running; DR-5 EQUAL |
| OPERATE | profile applied (WARNING); the turn works with no message preview logged; journal 2 d, history 24 h, logs 2 d |
| Rollback | R-1/R-2 CLEAN; the key moved to a root-only quarantine |
| Failure injection | 8/8 install stages stop and roll back CLEAN |
| Guards | pending-reload refusal; rollback hold under a pending reload; CLEAN |
| FINAL | M0 == FINAL; DR-5 EQUAL |

Defects the mirror found during f8r3 preparation, all fixed in the final package:
1. **Lost or late replies (adapter):** the completion hook (FIFO) resolved the *next* turn's waiter. Fixed by per-session serialization (B-4).
2. **Session cap:** `max_concurrent_sessions: 1` refused any second console session. Raised to 8, because it caps open sessions, not spend.
3. **Empty fallback credential:** systemd rejects an empty `SetCredential=` value, so a missing key failed the gate (243/CREDENTIALS) and restart-looped it. Fixed with the `NOT-PROVISIONED` placeholder.
4. **Budget reset:** it restarted the gate and counted against StartLimitBurst. It is now file-only, because the gate re-reads state on every request.
5. **Rollback hold:** rollback's pending-reload filter ignored the gate unit, so it held needlessly and left stale units. It now excludes all F8-owned units, and install and rollback wait up to 60 s for transient systemd jobs.
6. **Observation false differences:** the observer compared the gate listener and ephemeral UDP client sockets. Both are now excluded; real listeners are still compared.

## 11. Residual risks before DEV

- **Real Groq behavior is unverified:** TLS chain, actual gpt-oss output and streaming format, rate-limit responses and token accounting. Verifying them is exactly the 5-turn DEV acceptance.
- **No hard spend control on the free tier:** the free tier has no spend-limit feature, and a paid limit may overrun by a small amount (10–15 min update lag). The gate's 5-request budget is the hard local bound.
- **Gate client token readable by uid `lilith`:** the Core API process could also use the gate, bounded by the same budget, model and cap.
- **The gate's IP filter allows 127.0.0.1:** it could reach other loopback services, though its code connects only to the resolved upstream.
- **Startup race:** turns sent during the ~1 s startup restore get a clear 503 "starting" (no longer empty). The UI shows it as a transient error.
- **FORGET gap (B-6)** and provider-side erasure: unchanged, explicit. Synthetic-only.
- **The mirror is WSL, not GCE:** no `/etc/hosts` metadata entry, no NAT or IAP. DEV re-proves DR-5 and the probes at G-1b, G-3b, G-7b and G-9.

## 12. Recommendation

**GO** for owner review of f8r3 `3938796f…` as the Phase B package, subject to:
1. the owner completing §9 items 1–4 in the Groq console (project, project key, ZDR confirmed, limits);
2. the owner accepting the B-4 adapter diff and the provider-gate component;
3. a separate authorization for the DEV install, which is still out of scope here.

**NO-GO** for any real personal conversation or First Memory recording until B-6 is resolved.
