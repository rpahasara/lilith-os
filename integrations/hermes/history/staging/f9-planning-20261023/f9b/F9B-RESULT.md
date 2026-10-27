# F9-B: Hermes conversation-logging privacy + erasure preparation. LOCAL result (2026-10-23)

**Status:** LOCAL ONLY. Implemented on top of the accepted F9-A, then built and tested in the WSL mirror against the synthetic provider.
- **Not installed.** No DEV/PROD contact, Groq request, budget reset, commit or push. No DEV data was read, deleted or modified.
- **Stopped for owner review.**

## 1. Candidate and reproducible fingerprints

| Item | Value |
|---|---|
| Package | `hermes-gateway-dev-f293e72-f9b1.tar.gz`, sha256 **`6da1a721c4ae75cd9b5990c7961a6186e7a0a974e852ec11df4fa6c7199aeab3`** (WSL `/root/f9b/out`, not transferred) |
| Reproducibility | two consecutive builds byte-identical |
| MANIFEST | `0fff1dea07f43aa1bb6c479d00219aa7ccb25bd66b690ae7b51fcc50d2194461` (14,309 entries) |
| Recipe | the reviewed F8r4 stage-2 build + `patch_f9a.py` (unchanged from the accepted F9-A) + `patch_f9b.py` |
| Files changed vs F8r4 | `RELEASE_ID`; **F9-A:** `src/gateway/run.py`, `home/lilith_router/gateway_integration.py`, `home/config.yaml`, `tests/test_f7_offline.py`; **F9-B:** `src/gateway/run.py` (again), `src/agent/turn_context.py`, `src/agent/agent_runtime_helpers.py`, `profiles/operate/config.yaml`; **added** `tests/test_f9a_offline.py`, `tests/test_f9b_offline.py`. Plus build-generated stdlib `.pyc` byproducts. |
| Source hashes | run.py `5928c9f0…`, turn_context.py `70f1ea4d…`, agent_runtime_helpers.py `bdeecae2…`, operate config `dfd304c9…`, gateway_integration.py `5ce4bbd4…` (F9-A), config.yaml `4a28709d…` (F9-A) |
| Unchanged | gate, units, sandbox, scripts, DR-5 pins, `lilith_os` adapter, **SOUL.md** (runtime file, hash `2765a846…` in every run), personality code, Router V2 logic, all memory/canonical modules, Core API, broker, authority, witness, UI |

Review diffs:
- `review/F9B-SOURCE-vs-F9A.diff`: 59 changed lines.
- `review/F9B-SOURCE-vs-F8R4.diff`: the whole F9 change.

## 2. Exact code paths found

1. **`gateway/run.py` `_handle_message_with_agent`:** `logger.info("inbound message: … msg=%r … reply_to_text=%r")`, the first 80 characters of the user text and any reply-to text.
   - It goes to `gateway.log` **and** `agent.log`.
   - **`gateway.log` has a hard-coded INFO handler** (`hermes_logging.setup_logging`), so `logging.level: WARNING` does **not** stop this line. That's why the fix is at the source.
   - Accounts for 1 of the 2 `gateway.log` hits and 1 of the 4 `agent.log` hits per message.
2. **`agent/turn_context.py`:** `logger.info("conversation turn: … msg=%r")` goes to `agent.log` (the other `agent.log` hit).
3. **Found by the audit, not by the canary:** `agent/agent_runtime_helpers.dump_api_request_debug` writes the **full request body** to `HERMES_HOME/sessions/request_dump_*.json`. That includes the system prompt, every history message and the provider error body. Its own comment says it runs "unconditionally on API errors".
   - On DEV it would trigger on any gate refusal (budget exhausted), an upstream error or a timeout.
   - The F8 runs never produced one, which is why the earlier scans missed it.
4. **Compatibility defect:** `apply_profile.sh operate` **replaces** `config.yaml` with `profiles/operate/config.yaml`, which lacked F9-A's `onboarding.profile_build: "off"`.

## 3. Changes (diagnostics kept, content removed)

| Path | Now logs / writes |
|---|---|
| inbound message (run.py) | platform, user, chat id, **`msg_chars`**, reply_to_id, **`reply_to_chars`** |
| conversation turn (turn_context.py) | session, model, provider, platform, history length, **`msg_chars`** |
| request debug dump | `content_free: true`; reason, endpoint, model, scalar parameters, **message roles + sizes**, tool names, error **type/status_code/code/request_id/param/response_status**. **No** message text, structured parameters, error message, error body or response text. Applied before anything is written or printed. |
| OPERATE profile config | `onboarding.profile_build: "off"` (quoted), alongside WARNING logging |
| Router decision log | unchanged from F9-A (`event_id`, `msg_chars`, `msg_lines`, routing decision) |

## 4. Evidence: synthetic content no longer leaks (`f9b-rehearsal.tsv` **45/45**)

**Tests:**
- G-4: F7 **19/19**, F9-A **10/10**, F9-B **6/6**.
- **Negative control:** on the F9-A tree, exactly the 5 F9-B behaviour tests fail. The WARNING-level test passes, as it should.
- G-5c/G-6/G-6b PASS; G-9 observation EQUAL; DR-5 `F8_DR5_EQUAL 7fe21378…`; teardown M0 == FINAL.

**Canary scenarios (`F9B-CANARY-…`), console turns:**

| # | Scenario | Result |
|---|---|---|
| C1 | normal | 200, model reply |
| C2 | upstream 500 | 200 + provider-failure notice; request dump written |
| C3 | upstream 429 | rate-limit notice; dump |
| C4 | stream cut mid-response | partial reply |
| C5 | provider gate stopped | "model server not responding"; dump |
| C6 | budget exhausted (gate 429) | notice; dump |
| C7 | **SIGKILL during an in-flight request** | systemd auto-restart (NRestarts 1); session continues |
| C8 | **SIGTERM restart during an in-flight request** | ready, continues |
| C9 | **OPERATE profile (logging WARNING)**: normal + upstream 500 | 200; notice; dump |

**Byte scan of the whole mirror filesystem**, after the gateway was stopped so every log was flushed. Scanned: `/home`, `/var/backups/hermes-gateway-dev`, `/var/tmp`, `/tmp`, `/var/log` (incl. journal files), `/opt/hermes-gateway-dev`, `/etc`, `/var/lib`, `/run`, `/srv`.
- **Only `HERMES_HOME/state.db` and `state.db-wal` contain the canary**, i.e. the conversation store, as expected.
- `gateway.log` 0, `agent.log` 0, `errors.log` 0.
- Router decisions: 33 records, 0 previews, 33 event ids.
- Journals: Hermes namespace 0, system journal 0, Core API unit 0.
- The error output in the journal carries only summaries such as `HTTP 429: F8_GATE_BUDGET_EXHAUSTED`.
- **13 request dumps, all `content_free`.**
- After rollback, the canary is present **only** in the rollback quarantine's copy of `state.db`/`-wal`, which is a restore-risk input for §6.

**Audit limit, stated honestly:** `run.py` alone has hundreds of WARNING/ERROR sites, so a static audit cannot prove absence. The evidence is empirical: 9 scenarios × both profiles × a full-filesystem and journal scan. The backstop for any unknown path is that F9's governed erasure rotates and removes **all** Hermes logs, not just known lines.

## 5. Conversation-bearing storage inventory (measured, F9-B behaviour)

| ID | Location | Holds | Today | FORGET handling needed |
|---|---|---|---|---|
| H1 | `HERMES_HOME/state.db` (+`-wal`, `-shm`): `sessions`, `messages` (`content`, `api_content`, `reasoning*`), FTS5 indexes | **full text** | 7 d prune (1 d OPERATE) of ended sessions; no secure delete; the WAL survives SIGTERM | stop gateway → `delete_session` per session → FTS consistency → `secure_delete=ON` → `wal_checkpoint(TRUNCATE)` → `VACUUM` → verify by canary |
| H2 | `sessions/request_dump_*.json` | **metadata only** after F9-B (roles, sizes, error codes, session id) | never pruned by Hermes | delete with the session (`delete_session(sessions_dir=…)` removes them) |
| H3 | `sessions/sessions.json` | session index: keys, ids, timestamps (0 canary) | rewritten by Hermes | rewritten consistently by `delete_session`; verify |
| H4 | `logs/gateway.log`, `agent.log`, `errors.log`, `gateway-*-diag.log` | **metadata only** after F9-B (ids, sizes, timings, statuses) | 2 d age delete + logrotate | rotate and remove all on FORGET (also covers unknown paths) |
| H5 | `logs/lilith-router-decisions.log` | metadata only after F9-A (chat id, mode, sizes, event id) | 2 d | remove lines for erased chats, or all, on FORGET |
| H6 | journald namespace `hermes-gateway-dev` (gateway + gate) | metadata only (0 canary); gate records = request ids, tokens, status | 2 d | namespace-wide rotate + vacuum (journald cannot delete selectively) |
| H7 | `pending_messages/` | **queued inbound text** while the agent is busy (empty in the runs) | transient | purge on FORGET (gateway stopped) |
| H8 | `channel_directory.json`, `gateway_state.json`, `runtime/active_sessions.json`, `state/*`, `cron/executions.db`, `gateway/restart_loop.json` | ids/metadata | runtime | reset or purge on FORGET |
| H9 | `cache/` (tool/schema caches), `audio_cache/`, `image_cache/` | no conversation text for `lilith_os` text turns | runtime | purge on FORGET (media would be content) |
| H10 | `memories/` | pre-existing; Hermes memory **disabled** | — | outside Hermes conversation scope; LILITH memory is governed separately |
| H11 | `/var/backups/hermes-gateway-dev/`: `pre-*`/`upgrade-pre-*` (tar of HERMES_HOME), `rollback-*` quarantines (full HERMES_HOME + journal namespace dir), `f8r2-preserved-*`, `f8r4-evidence/` | **full text copies** whenever taken with state present (synthetic today) | never erased | D-5: future backups code/config only; existing copies enumerated → erased or restore-blocked |
| H12 | Groq | request/response | ZDR (provider-attested, D-6) | attestation only |
| H13 | Core API `/os/conversation` relay | nothing for non-capture sessions (0 canary in its unit journal) | — | FI capture is already L18_V2-covered (F4/F5) |

**Metadata note:** even content-free logs retain conversation **metadata** (chat ids, timestamps, sizes, routing modes). F9 should decide whether FORGET removes metadata too. The recommendation is yes, by rotating and removing all Hermes logs and the namespace journal.

## 6. Safe cleanup boundaries

- **Live SQLite:** never touched while the gateway runs, and never deleted or replaced as a file. Erasure runs only with the gateway stopped (exclusive), through Hermes' own `delete_session` semantics, then secure-delete/checkpoint/VACUUM.
  - A SIGTERM stop leaves a non-empty WAL (N-1), so a checkpoint is mandatory. Deleting a `-wal` file without one corrupts or drops committed rows.
  - An emptied store re-arms first-contact logic; F9-A guarantees no note is attached for `lilith_os` (E2 test).
- **Journal namespace:** only the `hermes-gateway-dev` namespace may be rotated or vacuumed, never the system journal. Doing so also removes the gate's FORWARDED records (metadata). Export any record needed as content-free evidence **before** a vacuum.
- **Gate ledger** (`/var/lib/private/hermes-provider-gate-dev/ledger.log`): request ids and token counts only, no content. **Out of erasure scope**, never reset by erasure.
- **Rollback evidence:**
  - `f8r2-preserved-*` (the accepted F8r4 rollback baseline) and every `rollback-*` quarantine contain HERMES_HOME **including `state.db`**. `restore_f8r2.sh` would put that conversation state back.
  - Today it is synthetic only, so there is no personal-data risk now. Once real conversations exist, any quarantine created afterwards holds real text, and a restore after a FORGET would **resurrect erased conversations**.
  - Boundary: restores must refuse after a FORGET (restore suppression), or quarantined conversation stores must be in the FORGET inventory.
  - Nothing existing is deleted by F9-B.
- **Protected services and DR-5:** erasure never touches the Core API, broker, authority or witness data, nor anything pinned by DR-5.
- **Start-rate limit (found in testing):** the gateway unit has `StartLimitBurst=3` / `StartLimitIntervalSec=300`. A crash auto-restart plus a restart plus any further stop/start inside 5 minutes fails with "Start request repeated too quickly". This affects `apply_profile.sh` and any erasure that stops and starts the gateway.
  - Reproduced locally (`repro_operate.sh`): clean state → OPERATE switch PASS; after SIGKILL + restart → start-limit failure.
  - It is an F8 unit property, not an F9 change. The erasure runner must handle it explicitly (reset-failed, or fail closed with a clear status).

## 7. Proposed L18_V2 integration (design for separate review; nothing implemented)

**Facts established (read-only, repo at b9eb32c):**
- `PrivacyGovernanceStore.begin_forget(...)` accepts `resource_owners` only from the **closed** `OWNER_SET` (L04, L18_V1, L18_V2, ACTOR_AUTHORITY, POLICY, CONSENT, ROLLBACK, LEGACY_MEMORY, LEGACY_SKILLS, PENDING).
- Each owner reports via `record_owner_result(authorization_ref_id, execution_nonce, {owner, status: COMPLETE|FAILED})`.
- `complete()` refuses unless **every** owner is COMPLETE, so **the privacy hold stays ACTIVE on any failure** (fail closed, retryable with the same authorization).
- Restore suppression is written at `begin_forget` and never deleted.

**Proposal (not implemented):**
1. Add a resource owner, e.g. `HERMES_DEV_CONVERSATION`, implemented in the F4 pattern. It is never a user-facing route; it only runs inside an L18_V2 FORGET authorization.
2. **Privileged executor:** the Core API runs unprivileged, but erasure needs root (stop the gateway, vacuum the namespace journal, handle root-owned backups). The design is a root oneshot unit that:
   - receives the authorization ref + nonce;
   - **re-resolves it read-only from the Privacy store**;
   - runs H1–H9 (and H11 per D-5);
   - verifies with a canary-free check (row counts, `has_any_sessions`, file absence);
   - returns a content-free receipt.

   The owner adapter then records COMPLETE or FAILED, and any step failure means FAILED, so the hold remains.
3. Gateway stop/start handled explicitly, including the start-rate limit.

**Blockers before any implementation:**
- **B-1:** `OWNER_SET` lives in `privacy_governance.py`, a production module covered by the Slice 15B2a static-boundary tests. Adding an owner is a governed change. Whether the module is in the broker/signer shared-file pins must be checked first (canonical modules are; a signer/broker release program may be required).
- **B-2: scope mismatch.** L18_V2 FORGET is keyed by memory identity (`memory_class`/`subject_namespace`/`subject_key`), while Hermes history is keyed by session/chat. A mapping is needed: owner-wide "forget my conversation history" vs per-memory FORGET. This is an owner and design decision.
- **B-3: privilege path.** Any new root executor triggered from the Core API (sudoers rule, polkit rule or path unit) **changes the DEV authority boundary that DR-5 proves**. It needs its own design, a new expected DR-5 block and explicit authorization.
- **B-4: start-rate limit** interaction (above).
- **B-5: verification limits.** File- and journal-level checks cannot prove physical erasure: SSD wear-levelling, journald field compression, the page cache, and GCE disk snapshots if any exist (F8 policy: none). The receipt must say "logically erased + verified by scan", not "physically destroyed".

## 8. Compatibility with the accepted F8r4 rollback baseline

- **Install path not built yet (blocker for any DEV install):**
  - `install.sh` refuses when F8 paths exist.
  - `preserve_f8r2.sh`/`restore_f8r2.sh` are hard-wired to release `f293e72-f8r2`.
  - Upgrading DEV from F8r4 to F9 needs reviewed `preserve_f8r4`/`restore_f8r4` equivalents and the same U-0…R-3 ladder, rehearsed in the mirror.
  - The preserved copy itself contains `state.db` (§6 restore risk).
- **Logging behaviour change:** DEV diagnostics lose message previews. Smoke readiness ("Press Ctrl+C to stop") and the F8 checks are unaffected (G-4/G-6/E3 PASS).
- **PROD divergence:** `run.py`, `turn_context.py`, `agent_runtime_helpers.py` and `gateway_integration.py` now differ from the F7/PROD copies. PROD stays untouched and needs its own review.
- **Unchanged risks:** the gate's ~31 s startup; Hermes exits 1 on SIGTERM.

## 9. Blockers summary

| # | Blocker | Needed |
|---|---|---|
| 1 | L18_V2 `OWNER_SET` is closed (production module) | governed change review + pin check (B-1) |
| 2 | FORGET scope mapping memory-identity ↔ conversation session | owner design decision (B-2) |
| 3 | Privileged erasure executor changes the DR-5 authority boundary | separate design + new DR-5 expectation + authorization (B-3) |
| 4 | F8r4 → F9 upgrade scripts (preserve/restore for f8r4) | new reviewed scripts + mirror rehearsal before install |
| 5 | Restore of preserved/quarantined state after FORGET | restore-suppression or inventory rule (D-5) |
| 6 | Start-rate limit during profile switch / erasure | explicit handling in runner/profile script |

## 10. Files (staging `f9-planning-20261023/f9b/`)

- **Sources and scripts:** `patch_f9a.py` (copy, unchanged), `patch_f9b.py`, `test_f9a_offline.py`, `test_f9b_offline.py`, `build-f9b.sh`, `f9b-rehearse.sh`, `run.sh`, `run2.sh`, `repro_operate.sh`, `collect.sh`.
- **`review/`:**
  - `F9B-SOURCE-vs-F9A.diff` (`ddac415b…`), `F9B-SOURCE-vs-F8R4.diff` (`85a6bd93…`);
  - `MANIFEST-f9b1.sha256`, package `.sha256`;
  - `inventory-hermes-home.txt`, `inventory-backups.txt`;
  - `f9b-rehearsal-evidence.tgz` (`7d5ff022…`), `SHA256SUMS`.
