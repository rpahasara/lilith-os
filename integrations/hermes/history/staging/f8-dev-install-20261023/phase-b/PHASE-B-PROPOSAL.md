# F8 Phase B proposal: DEV model provider for the Hermes gateway (lilith-dev-01)

**Status:** PROPOSAL ONLY (2026-10-23).
- Nothing is changed, provisioned or installed; no provider account or key exists.
- Phase A (`269dde95…`, owner-accepted) stays exactly as is until a separately authorized f8r3 install.

**Goal:** let the DEV console produce a real model reply through Router V2 in shadow mode. All other Phase A properties stay in place:
- zero tools;
- every cognitive lane off;
- no owner recording or canonical admission;
- synthetic text only;
- not enabled at boot.

## Decisions requested (summary)

| # | Decision | Recommendation |
|---|---|---|
| B-1 | Provider + model | One API-key provider with **prepaid credits** and a **per-key credit cap**. A small, inexpensive chat model; contractual no-training / zero- or short-retention terms. Candidates are compared in §1; final pick is the owner's. |
| B-2 | Egress design | A **provider-only CONNECT proxy** on 127.0.0.1 in its own sandboxed unit; the gateway stays loopback-only (§2). No IP-range allowlist on the gateway. |
| B-3 | Spend limits | Four layers: provider prepaid cap → per-key cap → proxy daily request/byte breaker → Hermes turn caps (§3). |
| B-4 | Startup readiness | Adapter grace fix (a reviewed source change to the F7-accepted adapter) + Core API unchanged (§4). |
| B-5 | Session privacy | Logging at WARNING, 24 h retention, synthetic-only stays mandatory, explicit inventory of where text lives (§5). |
| B-6 | FORGET gap | Keep **real personal conversations unauthorized** until a Hermes-DEV erasure adapter exists and is tested (§6). Phase B itself stays synthetic. |
| B-7 | Router V2 | Phase B's first proof is a live **shadow** decision in `lilith-router-decisions.log` (Phase A never reached the seam). Router `live` mode needs a separate decision. |

## 1. Provider and model (B-1)

Constraints:
- An independent DEV credential, never PROD's `auth.json` (openai-codex OAuth) or any PROD `.env` value.
- API-key authentication, held only in `/etc/hermes-gateway-dev/provider.env` (root 0600, hidden from the service; read by PID 1 at start).
- A hard spend ceiling enforced by the provider, not just alerts.
- Data-use terms: no training on API data, minimal retention. Provider-side copies are outside FORGET (§6).
- A model supported by Hermes upstream f293e72 without lazy installs. Verify in the f8r3 WSL mirror run, where lazy installs stay disabled.

Candidate shapes (current pricing, cap mechanics and retention terms must be verified at selection; not asserted here):

| Option | Ceiling mechanism | Notes |
|---|---|---|
| A. Aggregator with prepaid credits + per-key limit (e.g. OpenRouter) | prepaid balance + per-key credit limit | one host to allow; many small models; check per-model retention / provider routing settings |
| B. First-party API with prepaid credits / workspace spend limit (e.g. Anthropic, OpenAI project) | org/workspace or project limit | one host; first-party retention terms; confirm whether the limit is hard |
| C. Groq API | plan limits | matches Router V2's social lane provider; still needs its own key; Router stays shadow, so not required |

**Recommendation:** option A or B. Choose the provider whose limit is a **hard prepaid ceiling** and whose API-data terms are no-training / zero-retention.
- Start with a USD 5–10 cap and one small model.
- Router V2 `hermes_model` / `hermes_provider` = the same model, used for the social-lane fallback only. Router stays in shadow, so the router changes no routing.

## 2. Narrow provider-only egress (B-2)

**Problem:** systemd `IPAddressAllow` matches IPs, not hostnames, and provider APIs sit behind large CDNs with changing addresses. An IP allowlist would mean "all of the CDN" and would still need DNS inside the gateway.

**Design:**
- **The gateway is unchanged:** `IPAddressAllow=127.0.0.1/32`, no DNS, D-Bus and resolver hidden.
  - New env: `HTTPS_PROXY=http://127.0.0.1:9911`, `NO_PROXY=127.0.0.1,localhost`.
  - Hermes honors these explicitly (`agent/process_bootstrap.py`). The f8r3 mirror run must prove the main provider client uses the proxy.
- **New unit `hermes-provider-proxy-dev.service`**, about 150 lines of stdlib Python, shipped in the package:
  - listens on `127.0.0.1:9911`;
  - accepts **only** `CONNECT <provider-host>:443` for an exact allowlisted hostname (one or two names, pinned in a root-owned file covered by the critical-set hash) and refuses everything else, including plain HTTP;
  - resolves DNS itself and refuses any answer in 127/8, 10/8, 172.16/12, 192.168/16, 100.64/10, 169.254/16, ::1, fc00::/7 or fe80::/10, so DNS rebinding can't reach the metadata server, the VPC or PROD;
  - never terminates TLS (end-to-end to the provider), so it never sees prompts or the key;
  - logs one line per CONNECT (host, bytes, duration; no content) and enforces the §3 circuit breaker.
- **Proxy sandbox:**
  - `DynamicUser=yes`, `ProtectSystem=strict`, `ProtectHome=yes`, `PrivateTmp`, no capabilities;
  - `RestrictAddressFamilies=AF_INET AF_UNIX`;
  - `IPAddressDeny=` RFC1918 / CGNAT / link-local / metadata (plus ::/0), `IPAddressAllow=127.0.0.1/32 127.0.0.53/32` (local stub resolver) and public space only;
  - `MemoryMax=64M`; static, pulled in by the gateway (`Wants=`); no enable.
- **Verification (f8r3 G-7b extension):**
  - from inside the gateway sandbox, direct internet is still blocked;
  - via the proxy, only the provider host connects; any other host, IP-literal or private target is refused (403);
  - the proxy cannot reach 169.254.169.254 or 10.20.0.0/24.
  - P7 is updated **explicitly** in f8r3: it asserts "metadata.google.internal resolves only via `/etc/hosts` to 169.254.169.254 AND every connection to it is blocked", replacing the Phase A ACCEPTED_DEVIATION.

## 3. Spend limits (B-3)

1. **Provider:** prepaid balance (USD 5–10 initial), auto-top-up **off**.
2. **Key:** per-key credit cap at or below the balance; a dedicated DEV key, revocable independently.
3. **Proxy breaker:** at most N CONNECTs per UTC day and at most M bytes upstream per day, e.g. 200 requests and 20 MB.
   - When tripped, it refuses until the next UTC day.
   - It logs `PROXY_BREAKER_OPEN`, and a health gate checks for it.
4. **Hermes:**
   - `agent.max_turns: 4` (default 500);
   - `max_concurrent_sessions: 1`;
   - Router stays shadow.
   - Zero tools means no tool-call loops; each console turn is roughly one or two model calls.
   - Set an output-token cap if Hermes exposes one for the chosen provider (to verify in f8r3).
5. **Operational:**
   - smoke tests use at most about 5 paid turns per run;
   - no automated or periodic traffic (cron pinned empty, curator / background review off).

## 4. Startup readiness (B-4)

Observed in Phase A: console turns sent in the first ~1–2 s after a gateway (re)start are queued by Hermes' startup restore. The adapter's waiter resolves early via `on_processing_complete`, returning "(LILITH completed the turn without a text reply.)", and the real reply is sent later and lost to the caller.

**Proposed adapter change** (reviewed diff to the F7-accepted `plugins/lilith_os/adapter.py`; new adapter hash):
- When `on_processing_complete` fires with no final `notify` reply, keep waiting up to a short grace window (e.g. 20 s) for the queued turn's notify send before returning.
- Additionally, return `503 {"error":"starting"}` until the gateway reports running and the startup queue has drained. The Core API maps it to 502/504 without retry, so the UI shows a transient error instead of an empty reply.
- Tests: an F7-style offline test for both paths; the mirror race test from F8r2 (send at listener-up) must return the real reply or 503, never an empty "completed".

The Core API and the UI are unchanged.

## 5. Session privacy (B-5)

Where console text lives once a provider is enabled:

| Location | Content | Control |
|---|---|---|
| Provider (outside DEV) | full prompt + history + persona | provider terms (no-training / zero-retention); **not erasable by us** |
| `state.db`, `sessions/` | full turns | prune → **24 h** (was 7 d); idle reset 1 h |
| `logs/gateway.log`, `agent.log` | INFO inbound previews `msg=…` | set `logging.level: WARNING` (previews are INFO); daily rotation; 7 d → 2 d |
| `logs/lilith-router-decisions.log` | ≤ 60-char preview per turn | 2 d retention; or `log_path` to a preview-free mode if added later |
| journald namespace | stdout/stderr | 2 d (`MaxRetentionSec`) |
| Core API | relays only; non-capture sessions write nothing | unchanged |
| proxy | host / bytes only, no content | 2 d |

Further controls:
- **Synthetic-only remains a hard rule** for Phase B (owner instruction).
- The UI console label and the runbook state "DEV, synthetic only".
- The persona (`SOUL.md`) stays the Hermes default or a reviewed DEV persona; never PROD's.

## 6. FORGET coverage gap (B-6)

Today the L18_V2 erasure covers the F2/F4 capture DB only. It does **not** cover:
- Hermes `state.db` and transcripts;
- Hermes logs and the decisions log;
- the gateway journal namespace;
- provider-side copies.

Options:
- **(A) Policy only:** synthetic text only, enforced by procedure. This covers Phase B, but is not acceptable for real conversations.
- **(B) Hermes-DEV erasure adapter** (recommended before any real conversation is ever considered), invoked by the FORGET runner after the L18 commit, like F4:
  - stop the gateway;
  - delete the console sessions with `hermes sessions prune --source lilith_os …` or an exact session-id delete;
  - truncate or rotate and delete the Hermes logs and the decisions log;
  - `journalctl --namespace=hermes-gateway-dev --rotate && --vacuum-time=1s`;
  - restart, then record the result.

  It runs as root via a fixed, reviewed helper (deployer boundary unchanged). Tests: mirror run plus synthetic FORGET end-to-end.
- **(C) Provider side:** only contractual zero-retention reduces this. It is still not erasable, so real personal content must not be sent until the owner accepts that residual.

**Recommendation:** Phase B = (A) + 24 h / 2 d retention. Implement (B) as its own slice. Keep real personal conversations unauthorized.

## 7. f8r3 package and gates (outline)

- **Changes vs f8r2:**
  - config (provider, model, `max_turns`, concurrency, logging level, retention);
  - router.yaml `hermes_*`;
  - `verify_release` `PROVIDER_ALLOWED={<KEY_NAME>}`;
  - gateway unit env (`HTTPS_PROXY`/`NO_PROXY`);
  - new proxy unit + allowlist + breaker;
  - adapter readiness fix;
  - P7 probe update;
  - retention timers.
- **Unchanged:** src overlay, venv, sandbox, cron pin, slash gating, lanes off.
- **Preparation:** a WSL mirror run like F8r2, with a stand-in provider endpoint (local TLS test server named by the allowlist), so no paid call happens before authorization. Full failure injection; DR-5 byte-equal.
- **DEV install (separately authorized):**
  - G-1 … G-7 as in Phase A;
  - credential provisioning by the owner on the host;
  - proxy and egress probes;
  - **at most 5 synthetic paid turns**;
  - proof of a shadow decision in the decisions log;
  - spend check on the provider dashboard;
  - G-9 parity + DR-5;
  - stop.
- **Rollback:** R-1 stops the gateway and the proxy. Revoking the provider key is an owner action, independent of the host.

## 8. Open items

1. Owner picks B-1 (provider, model, cap amount) and confirms the data-use terms.
2. Approve the adapter source change (B-4). It modifies F7-accepted code.
3. Approve the new proxy component (B-2): new code, a new unit, and a second network-capable process on DEV.
4. Retention values (B-5) and whether the decisions-log preview is kept.
5. Whether to build the Hermes-DEV FORGET adapter (B-6) now or later.

Not authorized by this proposal: any DEV change, credential, paid call, real conversation, PROD access, UI change.
