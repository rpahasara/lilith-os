# F9-C: Governed Hermes erasure integration. DESIGN FOR REVIEW (2026-10-23)

**Status:** design only.
- No code, DEV change, Groq call, commit, deployment or upgrade script.
- Builds on the locally validated F9-A (no Hermes onboarding) and F9-B (no conversation text in operating logs; content-free request dumps).

**Inputs (read-only):**
- canonical repository `origin/main` = `b9eb32c` (the DEV-deployed commit), files `services/core-api/lilith_memory/{privacy_governance,memory_v2,canonical_authority,canonical_contracts}.py`;
- `services/owner-memory-control/lilith_owner_memory/{authority_contracts,authority_verifier}.py`;
- the pin sets in `services/authority-dev/release_file_set.py`, `scripts/memory_broker_os_release.py` and `scripts/memory_broker_validation.py`;
- F9-B measured inventory.

**Architectural rule applied throughout:** **Privacy Governance is the only FORGET authority.** It owns the request, hold, authorization, restore suppression and completion. Every resource owner, L18_V2 included, is an *independently validating* executor of one Privacy authorization. Hermes erasure becomes **a new peer resource owner**: neither a second authority nor an extension of L18_V2.

---

## 0. What the existing contracts actually say (facts that constrain the design)

| # | Fact (b9eb32c) | Consequence |
|---|---|---|
| F1 | `PrivacyGovernanceStore.begin_forget(action, actor_evidence_ref_id, intent_ref_id, memory_item_id, resource_owners, confirmation_event_ref)` validates a `FrozenMemoryActionV1` FORGET, resolves and consumes actor evidence, and atomically writes request + **ACTIVE hold** + HMAC-bound `ErasureAuthorizationV1` + owner set + **restore-suppression selector** (immutable, monotonic, never deleted). | All erasure starts here; Hermes erasure must be one of the authorization's owners. |
| F2 | The owner registry is closed **twice**: the Python `OWNER_SET` frozenset **and** a SQL `CHECK(resource_owner IN ('L04',…,'PENDING'))` on `privacy_erasure_authorization_owner` (schema v1). The store's SQLite authorizer **denies** CREATE/ALTER/DROP at runtime. | Adding an owner = a code change **plus** an offline governed schema migration v1→v2 (table rebuild), in the pattern of `slice15b2a_migration.py`. |
| F3 | **The caller chooses `resource_owners`**; Privacy checks only `owners ⊆ OWNER_SET`, not a minimum set. | A runner could omit the Hermes owner. Privacy must enforce a required-owner floor (§2). |
| F4 | Owners validate independently: `erase_authorized(authorization_ref_id, execution_nonce)` → `resolve_erasure_authorization(…, owner=OWNER)` checks the owner is listed, the nonce, the **HMAC fingerprint** (Privacy secret) and that the **hold is ACTIVE**. The owner erases in its own exclusive transaction (`secure_delete=ON`, `wal_checkpoint(TRUNCATE)`), then calls `record_owner_result`. | The Hermes owner follows the same contract. |
| F5 | `privacy_erasure_execution` has `UNIQUE(authorization_ref_id, resource_owner)`, and status is COMPLETE or FAILED. Existing owners **only ever record COMPLETE**; failures raise without a row. `complete()` refuses unless every required owner is COMPLETE, **so the hold stays ACTIVE**. | Recording FAILED would make that authorization permanently uncompletable. The Hermes owner raises on any failure and never records FAILED, so retries stay possible. |
| F6 | `complete()` writes an immutable receipt (owner results + suppression ref), then deletes the request/hold/authorization rows. | After completion a replayed authorization no longer resolves: replay-safe. |
| F7 | **No production FORGET runner exists.** `begin_forget` is called only by `scripts/run_core_api_dev_durability_probe.py`; `app.py` notes "the First Interaction FORGET runner must pass exactly this to L18_V2". | F9-C depends on a governed runner that does not exist yet (§2.4, approval A-6). |
| F8 | `FrozenMemoryActionV1` (in `canonical_contracts.py`, **signer- and broker-pinned** `f93d26d8…`) accepts only purpose `LONG_TERM_PERSONAL_PROJECT_RECALL`; FM-02's `memory_action_v2` adds the First Interaction family. | No new "forget conversation history" action or memory class without a signer/broker release program. Hermes erasure attaches to **existing** FORGET actions. |
| F9 | `privacy_governance.py` and `memory_v2.py` are **not** in the signer/broker hash pins (`canonical_authority.py` is in the broker validation `SHARED_FILES`). | The Privacy change is a governed **Core API** change (PR, review, DEV deploy pipeline), not a signer/broker release. |
| F10 | V2 authority contracts define a signed **`PrivacyAuthorizationV2`** (fields include `authorizationId`, `executionNonce`, `forgetRequestId`, `holdId`, `resourceOwners`, memory identity), verified by `verify_privacy_authorization` against the authority registry (public keys; module pinned in the signer `SHARED_HASHES`). No Privacy signing key is provisioned in DEV custody today. | Target state: the executor validates a signed envelope without any Privacy secret. Interim: V1 HMAC validation (§4). |
| F11 | Restore suppression is per **memory identity selector**; `RestoreSuppressionVerifier` applies to L04 identities; `validate_backup_retention` never deletes automatically. | Hermes backups need their own suppression rule (§5). |

---

## 1. Proposed contract and trust boundaries

```
 OWNER (UI, owner auth — not yet available; DEV: DEV_SYNTHETIC owner proof only)
   │  FORGET intent (existing FrozenMemoryActionV1 / FirstInteractionActionV1, unchanged)
   ▼
 ┌───────────────────────────── Core API process (uid lilith, existing unit) ─────────────────────────────┐
 │  FORGET RUNNER (new, governed; the only caller of begin_forget)                                         │
 │    1 begin_forget(action, …, resource_owners ⊇ REQUIRED_OWNERS)  ──► PRIVACY GOVERNANCE (sole authority)│
 │         Privacy enforces the required-owner floor, writes hold + HMAC authorization + suppression       │
 │    2 for each owner: owner.erase_authorized(auth_ref, nonce)   (existing owners unchanged)              │
 │    3 HermesConversationErasureOwner.erase_authorized(auth_ref, nonce)                                   │
 │         a  resolve_erasure_authorization(owner=HERMES_DEV_CONVERSATION)   ← independent check #1        │
 │         b  write request {auth_ref, nonce} ONLY → /run/hermes-forget/spool (0730 root:lilith-forget)    │
 │         c  wait for receipt (bounded); verify receipt binds auth_ref+nonce+COMPLETE+checks              │
 │         d  record_owner_result(COMPLETE) — or raise (no FAILED row; hold stays ACTIVE; retryable)       │
 │    4 complete() → receipt; hold released only if EVERY owner COMPLETE                                  │
 └────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                     │ spool file (no session ids, no paths, no scope fields)
   ════════════════ TRUST BOUNDARY: uid lilith → root executor (systemd path activation, no sudo/polkit) ═══
                     ▼
 ┌──────────── hermes-forget-executor.service (root oneshot, sandboxed; Conflicts=hermes-gateway-dev) ─────┐
 │  i   re-validate authorization independently                         ← independent check #2           │
 │      (interim V1: Privacy DB read-only + Privacy secret read-only; target V2: signed envelope)          │
 │  ii  derive scope from the AUTHORIZATION (never from the request): DEV policy = whole Hermes store      │
 │  iii gateway already stopped by Conflicts=; verify no hermes process, ports 9901 closed                 │
 │  iv  idempotent phases (journal in /var/lib/hermes-forget/<auth_ref>.state): H1…H11 erase + verify      │
 │  v   append erasure EPOCH (monotonic) → restore refusal for older Hermes copies                        │
 │  vi  write content-free receipt → /run/hermes-forget/receipts/<auth_ref>.json (root, 0640 root:lilith-forget)│
 │  vii success: reset-failed + start gateway (OnSuccess); failure: gateway stays STOPPED (fail closed)    │
 └────────────────────────────────────────────────────────────────────────────────────────────────────────┘
   Touches ONLY: HERMES_HOME conversation/runtime/log paths, the hermes-gateway-dev journal namespace,
   /var/backups/hermes-gateway-dev conversation-bearing copies. NEVER: Core API/broker/authority/witness
   data, Privacy DB (read-only), canonical stores, gate ledger, SOUL.md, DR-5-scoped paths.

 Hermes gateway (uid lilith, sandboxed): cannot see the spool, the receipts, the Privacy DB or the secret (InaccessiblePaths).
 Provider (Groq): ZDR — provider-attested only; never claimed as verified erasure.
```

**Invariants enforced by construction:**
- **No standalone Hermes FORGET endpoint:** the only trigger is a spool request that is worthless without a live Privacy authorization naming this owner.
- **No deletion from caller-supplied session ids:** the request schema has exactly `{authorization_ref_id, execution_nonce}`. Extra fields reject the request, and the scope comes from the authorization and the governed mapping (§3).
- **The hold stays active** until Hermes and every other required owner record COMPLETE (F5).
- **No canonical, authority or Privacy writes by the executor:** the Privacy DB is opened read-only.
- **DR-5 preserved:** no sudoers, polkit or deployer change; §4.

---

## 2. Exact changes to the Privacy owner registry and FORGET runner

### 2.1 `privacy_governance.py` (governed Core API change; not signer/broker-pinned)

1. `OWNER_SET` gains `"HERMES_DEV_CONVERSATION"`.
2. A **required-owner floor**: a new module constant plus check in `begin_forget`:
   - `REQUIRED_OWNERS = frozenset()` by default (no behaviour change for existing deployments).
   - A deployment config row `privacy_governance_config.required_owners`, written only by the migration tool, sets `{"HERMES_DEV_CONVERSATION"}` on DEV when Hermes is installed.
   - `begin_forget` raises `PrivacyError("required erasure owner missing")` unless `owners ⊇ required_owners`.
   - Fail closed: an unreadable config refuses FORGET.
3. The schema **v1 → v2 migration** (offline tool, same pattern as `slice15b2a_migration.py`, run by the deploy pipeline with the Core API stopped):
   - rebuild `privacy_erasure_authorization_owner` with the extended CHECK list;
   - add the `required_owners` config column or row;
   - bump `privacy_schema_migration` to 2;
   - recreate the immutability triggers;
   - verify row counts and fingerprints are unchanged;
   - `CHECK(schema_version=1)` on `privacy_forget_request` stays (request rows are unchanged).
4. No change to the authorization or receipt formats, the HMAC semantics, suppression or `complete()`.
5. Tests:
   - extend `test_slice15b2a.py`'s static boundaries to the new constant;
   - migration tests (v1 DB with in-flight authorizations → v2, fingerprints preserved);
   - floor tests (missing owner refused);
   - `resolve_erasure_authorization(owner="HERMES_DEV_CONVERSATION")` positive and negative.

### 2.2 New owner adapter (Core API side), e.g. `lilith_memory/hermes_erasure_owner.py`

- **Peer of L18_V2, not inside it.** Separate privilege, separate failure isolation. F4 placed the capture DB inside L18_V2 because it lives in the Core API's own trust domain; the Hermes store does not.
- `OWNER = "HERMES_DEV_CONVERSATION"`. `erase_authorized(auth_ref, nonce)` does:
  - resolve (independent check #1);
  - spool request (atomic `O_EXCL` write);
  - bounded wait (default 300 s; the gate needs ~31 s to bind plus the erasure);
  - receipt verification: file owned by root, mode, exact `auth_ref`/`nonce`, `status COMPLETE`, every check true, schema version;
  - `record_owner_result({"owner": OWNER, "status": "COMPLETE", "phases": n, "epoch": e})`.

  Any failure raises `PrivacyError`, records nothing, leaves the hold ACTIVE and is retryable.
- When Hermes is not installed (PROD, or DEV before F9): the owner is not in `required_owners`, and the adapter refuses if called.

### 2.3 Unchanged

`canonical_contracts.py` (signer/broker-pinned), `memory_action_v2.py`, L04, L18_V1, L18_V2, all authority owners, owner proof, `admission_v2`, and the signer, broker and witness releases.

### 2.4 FORGET runner (prerequisite, governed; does not exist yet, F7)

- A single runner in the Core API is the only `begin_forget` caller. It:
  - derives `resource_owners` from the governed owner policy: the family-specific owners **plus** `required_owners`;
  - calls each owner;
  - calls `complete()` only when every owner returned COMPLETE;
  - on any exception, returns `INCOMPLETE_HOLD_ACTIVE` with the authorization ref for retry.
- **No HTTP FORGET route is added by F9-C.** The owner-facing route depends on owner authentication, which doesn't exist yet. The DEV drill invokes the runner through a DEV-only operator entry point using DEV_SYNTHETIC owner proof (owner approval A-6).

---

## 3. Identity ↔ Hermes session mapping (decision)

**Problem:** Privacy FORGET is keyed by memory identity (`memory_class`, `subject_namespace`, `subject_key`); Hermes history is keyed by session/chat. Hermes has no notion of memory identity.

| Option | Scope erased per authorized FORGET | Precision | Feasible now | Limits |
|---|---|---|---|---|
| **M1 (recommended for DEV)**: whole-store purge | **All** Hermes conversation state (H1–H9) + conversation-bearing copies (H11) | over-erases (all chats), never under-erases | yes | valid **only** while DEV Hermes serves a single human principal (the owner) on the single `lilith_os` platform. Must be enforced: executor pre-check refuses `MULTI_PRINCIPAL_STORE` if Hermes config/allowlists show any other platform or user. Every FORGET also deletes unrelated history (acceptable on DEV, documented in the receipt). |
| M2: provenance-scoped | Only sessions linked to the identity through a governed provenance record (e.g. FI capture session id ↔ Hermes chat id, written at capture time by the Core API) | exact for captured conversations | no (new governed provenance store + capture-path change) | non-captured chatter about the identity stays (needs an M1 fallback); required before multi-principal or PROD |
| M3: new "conversation history" memory class | owner-chosen | n/a | **no** (F8: signer/broker-pinned purpose set) | release program |

**Decision proposed:** **M1 for DEV**, with the mapping written as policy, not as caller input:
- **D-C2a:** the Hermes owner is required for **every** authorized FORGET on DEV (simplest; conservative).
- **D-C2b (alternative):** required only for First-Interaction-family FORGETs.
- M2 is a **mandatory** later milestone before more than one principal or any PROD use. It is tracked; it is not part of F9.
- A standalone "forget all my conversations" without a memory identity has **no governed path today**. It is not invented here (it would need M3 or a new Privacy request type: owner decision, out of F9-C).

---

## 4. Executor privilege and authorization model

### Trigger (no new sudo/polkit, so the deployer's DR-5 boundary is unchanged)

- `hermes-forget.path` (root): `PathExistsGlob=/run/hermes-forget/spool/*.req` activates `hermes-forget-executor.service`.
- The spool directory is `root:lilith-forget 0730`. `lilith-forget` is a new group containing only the Core API's identity.
- The gateway sandbox gets `InaccessiblePaths=/run/hermes-forget /var/lib/hermes-forget`. It cannot see or trigger the spool, and can't read the Privacy DB/secret (already hidden: probe P12).
- **Known weakness to accept or fix (A-3b):** the Core API and the Hermes gateway share uid `lilith`; isolation between them is the gateway's systemd sandbox, not the uid. Option: run the gateway under a dedicated uid in a later slice.

### Executor unit (root oneshot, least privilege by sandbox)

- `Conflicts=hermes-gateway-dev.service` (starting the executor **stops** the gateway). `OnSuccess=` starts the gateway after `reset-failed`. **No `OnFailure` restart:** the gateway stays stopped on failure (fail closed: no new conversation data while erasure is incomplete).
- `ProtectSystem=strict`; `ReadWritePaths=` only HERMES_HOME conversation/runtime/log paths, `/var/lib/hermes-forget`, `/run/hermes-forget/receipts`, `/var/backups/hermes-gateway-dev`, `/var/log/journal/<machine-id>.hermes-gateway-dev`.
- `ReadOnlyPaths=` the Privacy DB and the Privacy secret.
- `InaccessiblePaths=` the Core API data, broker, authority, witness, credstore, gate credentials and sudoers.
- `PrivateNetwork=yes`, `CapabilityBoundingSet=` minimal (`CAP_DAC_OVERRIDE`, `CAP_FOWNER`, `CAP_CHOWN` for lilith-owned HERMES_HOME), `NoNewPrivileges`, `SystemCallFilter=@system-service`.
- D-Bus is needed only for journald namespace rotation and gateway reset-failed/start. Alternative: the vacuum step is a separate `ExecStartPost` helper.

### Authorization validation (independent check #2)

- **Interim (V1):** the executor opens the Privacy DB with `mode=ro`, loads the Privacy secret read-only, and calls `resolve_erasure_authorization(auth_ref, owner="HERMES_DEV_CONVERSATION", execution_nonce=…)`. It uses the **deployed Core API release's** `privacy_governance` module, imported read-only and hash-checked against the Core API release manifest. That checks the owner is listed, the nonce, the HMAC and that the hold is ACTIVE.
  - Cost: root reads the Privacy secret (it could anyway; the sandbox makes it read-only and explicit).
- **Target (V2):** a Privacy authority key signs a `PrivacyAuthorizationV2`; the executor runs `verify_privacy_authorization` against the trusted registry (public keys only, no secret). It needs a provisioned Privacy key and custody (owner approval A-4). It is not required for DEV synthetic drills.

### Request and receipt

- **Request:** JSON `{"v":1,"authorizationRefId":…,"executionNonce":…}`, ≤ 1 KiB, `O_NOFOLLOW`, owned by the Core API uid. Anything else is rejected.
- **Receipt:** content-free JSON with `authorizationRefId`, `executionNonce`, `owner`, `status`, `scope:"WHOLE_STORE_SINGLE_PRINCIPAL"`, the per-phase status, verification counts, `erasureEpoch`, `gateway:{stoppedAt,restarted}` and `claim:"LOGICAL_ERASURE_VERIFIED"`, plus a hash over the receipt body.
  - Integrity comes from location and ownership (root-only writable). Phase 2 can add a signature by the executor key.

### DR-5 and protected services

- No change to sudoers, polkit, the deployer identity or protected units.
- New units, group and paths belong to the F9 package allowlist.
- **Install gates must show DR-5 EQUAL `7fe21378…` and observation EQUAL.** If the new group or path unit changes the observed "accounts"/"units" sections, the observation baseline update is an explicit owner-approved step (A-3).

---

## 5. Erasure inventory and backup restore-suppression

### Executor phases (all idempotent; journal `/var/lib/hermes-forget/<auth_ref>.state`, fsync'd per phase)

| Phase | Action | Verification |
|---|---|---|
| P0 VALIDATE | independent authorization check; single-principal precondition; lock `/run/hermes-forget/lock` | — |
| P1 STOP | Conflicts= stopped the gateway; confirm no hermes PID, 9901 closed | `ActiveState != active` |
| P2 SQLITE (H1–H3) | open `state.db` (the WAL is replayed by opening; never delete `-wal`); `BEGIN EXCLUSIVE`; `secure_delete=ON`; for every session `delete_session(sid, sessions_dir)` (Hermes' own semantics: messages, children, system prompts, transcript and request-dump files); FTS consistency (`'rebuild'` on `messages_fts*`); `COMMIT`; `wal_checkpoint(TRUNCATE)`; `VACUUM`; `integrity_check` | sessions = 0, messages = 0, FTS rows = 0, freelist = 0, `-wal` size 0, integrity ok |
| P3 FILES (H4–H9) | remove `logs/*` (incl. rotated and diag), rewrite or remove `lilith-router-decisions.log`, purge `pending_messages/`, `channel_directory.json`, `gateway_state.json`, `runtime/*`, `state/*`, `gateway/*`, `cache/*`, `audio_cache/*`, `image_cache/*`, `cron/executions.db`; keep code/config/SOUL.md/memories/.env | directories empty; protected files hash-unchanged (SOUL.md, config.yaml, .env, `lilith_router/`, `plugins/`) |
| P4 JOURNAL (H6) | export the content-free gate FORWARDED records needed as audit (optional, owner policy), then `journalctl --namespace=hermes-gateway-dev --rotate` + `--vacuum-time=1s` (namespace only) | namespace journal files absent or empty; system journal untouched |
| P5 BACKUPS (H11) | enumerate `/var/backups/hermes-gateway-dev`; for every conversation-bearing artefact (`state.db*`, `sessions/`, `logs/`, `pending_messages/`, `*.hermes-gateway-dev` journal dirs, `hermes-dev-home.tar`): delete it, leaving a **tombstone manifest** (path, size, sha256 before, epoch); code/config parts of preserved releases stay | no conversation-bearing artefact remains; tombstones present |
| P6 EPOCH | append `epoch=<n> at=<utc> auth=<auth_ref digest>` to root-only `/var/lib/hermes-forget/epochs.log` (fsync, append-only, never truncated) | monotonic |
| P7 RECEIPT | write the receipt; mark the state COMPLETE | — |
| P8 RESTART | `reset-failed` + start the gateway (start-limit safe); F9-A guarantees no onboarding note on the emptied store | gateway ready; the receipt records restart status (erasure COMPLETE does not depend on restart) |

### Restore suppression for Hermes copies

1. **Backups going forward are code/config only.** `backup_pre_install`, `preserve_*` and `rollback.sh` quarantines exclude `state.db*`, `sessions/`, `logs/`, `pending_messages/`, caches and the journal namespace. They record a "conversation store excluded" marker instead.
2. **Restore refusal:** every restore script (`restore_f8r2.sh`, the future `restore_f8r4.sh`/F9 restore) reads `/var/lib/hermes-forget/epochs.log` and refuses to restore any conversation-bearing artefact whose capture time precedes the latest epoch. After any epoch, the only allowed restore is **code/config-only with an empty conversation store** (`F8_RESTORE_CONVERSATION_SUPPRESSED`).
3. **Existing synthetic copies** (`f8r2-preserved-*`, `rollback-*`, `upgrade-pre-*`, `f8r4-evidence/` decision copies with previews) are erased by the **first** governed FORGET drill (P5). Their tombstones keep the evidence of what existed. Non-sensitive F8 acceptance evidence (ledger, decisions without text, SHA manifests, DR-5 outputs, acceptance records) is kept (D-8).
4. **Accepted F8r4 rollback baseline:** F8r2 preserved state is synthetic only. Recommendation: keep it **until the F9 install is accepted**, then let the first FORGET drill strip its conversation store. The F8r2 code/config stays restorable via the conversation-suppressed restore mode (owner approval A-5).

---

## 6. Failure, retry, verification and rollback test matrix (mirror first; DEV drill synthetic, 0 provider calls)

| # | Case | Expected |
|---|---|---|
| T1 | valid FORGET, all owners incl. Hermes | receipt COMPLETE; Privacy `complete()` receipt; hold released; store empty; gateway restarted; F9-A: next first message has no note |
| T2 | runner omits the Hermes owner | `begin_forget` refuses (required-owner floor) |
| T3 | wrong nonce / owner not listed / tampered HMAC / hold not ACTIVE | adapter check #1 refuses; executor check #2 refuses (each tested alone by bypassing the other) |
| T4 | replay after `complete()` | authorization no longer resolves → refused, nothing touched |
| T5 | spool request with extra fields (e.g. session ids), oversize, symlink, wrong owner | rejected before any action |
| T6 | gateway sandbox tries to read/write the spool | denied (InaccessiblePaths); probe added to `sandbox_probe` |
| T7 | executor SIGKILL at each phase P1…P7 | gateway stays stopped; hold ACTIVE; retry with the same auth resumes or repeats idempotently; final state equals T1 |
| T8 | host reboot mid-erasure | the state journal survives; the path unit re-triggers on the pending request; same as T7 |
| T9 | SQLite locked / gateway refuses to stop | fail: no deletion, gateway stopped, raise; hold ACTIVE |
| T10 | WAL present after a SIGTERM stop (known) | the WAL is replayed by the exclusive open, then checkpointed; nothing lost; verified counts |
| T11 | disk full during VACUUM | VACUUM fails → raise; data already deleted stays deleted (transaction committed); retry completes VACUUM; receipt only after verify |
| T12 | journald vacuum failure | phase fails → no receipt; hold ACTIVE |
| T13 | backup tombstone write fails | phase fails; retry |
| T14 | start-limit hit at restart (crash + restart + executor) | `reset-failed` before start; if the start still fails → receipt COMPLETE with `gatewayRestart: FAILED` (erasure done; availability is an ops alert) |
| T15 | another owner fails (e.g. L18_V2) while Hermes succeeds | Hermes COMPLETE recorded; `complete()` refuses; hold ACTIVE; a retry of the remaining owner completes |
| T16 | Hermes executor times out (adapter wait) | adapter raises; executor may still finish; on retry the adapter re-reads the existing receipt for the same auth/nonce and records COMPLETE (idempotent) |
| T17 | multi-principal precondition violated (other platform/user configured) | executor refuses `MULTI_PRINCIPAL_STORE` |
| T18 | restore of a pre-epoch preserved/quarantined copy | `F8_RESTORE_CONVERSATION_SUPPRESSED`; code/config-only restore works |
| T19 | canary scan after T1 (console, relay, UI-path synthetic turns + budget-refused turns) | 0 canary bytes anywhere on the host (incl. backups and journal), except tombstone metadata (no content) |
| T20 | protected services | PIDs/InvocationIDs unchanged; DR-5 EQUAL; observation EQUAL (or the approved new baseline) |
| T21 | F8r4 → F9 upgrade then rollback (with the new preserve/restore) | exact code/config restore; conversation store per epoch rule |
| T22 | Privacy schema migration v1→v2 with in-flight authorizations | fingerprints and holds preserved; old authorizations still resolve for old owners |
| T23 | SOUL.md, `lilith_router/`, config, UI | hash-unchanged across every case |
| T24 | receipt and executor logs | content-free (canary 0) |
| T25 | provider side | not tested; the receipt states "PROVIDER: ZDR attested, not verified" |

**Claims allowed in receipts:** `LOGICAL_ERASURE_VERIFIED` (row/file/journal-level). Never "physically destroyed": SSD wear-levelling, ext4 freed blocks, the page cache, journald compression and any disk snapshot (none by F8 policy) are outside verification.

---

## 7. Required owner approvals

| ID | Approval |
|---|---|
| A-1 | Governed Privacy change: `OWNER_SET` + SQL CHECK extension via offline schema migration v1→v2, plus the required-owner floor (§2.1). Core API PR + DEV deploy pipeline. |
| A-2 | Mapping: **M1 whole-store DEV purge**, attached to **every** FORGET (D-C2a) or FI-family only (D-C2b); M2 as a mandatory pre-multi-principal milestone. |
| A-3 | Executor architecture: root oneshot via a path unit, the `lilith-forget` group and spool, sandbox, `Conflicts=`/`OnSuccess=` lifecycle; acceptance of any observation-baseline update. **A-3b:** accept the shared-uid (Core API/gateway) weakness for DEV or schedule a dedicated gateway uid. |
| A-4 | Validation mode: interim V1 HMAC (the executor reads the Privacy DB and secret read-only) for DEV synthetic; V2 signed `PrivacyAuthorizationV2` (Privacy key custody) before any real data. |
| A-5 | Backup policy: code/config-only backups; epoch-based restore refusal; first-drill erasure of the existing synthetic conversation copies (incl. the F8r2 preserved state, after F9 acceptance), with tombstones. |
| A-6 | The governed FORGET runner (prerequisite) and its DEV-only DEV_SYNTHETIC entry point; no owner-facing FORGET route until owner authentication exists. |
| A-7 | F8r4→F9 upgrade scripts (`preserve_f8r4`/`restore_f8r4`) honouring the backup policy; mirror rehearsal. |
| A-8 | DEV FORGET drill with synthetic canary and **0 provider requests** (the budget stays exhausted; refused turns still create Hermes state to erase). |

---

## 8. Recommended order (each step stops for review; no step implies the next)

1. **F9-C review:** this document; decisions A-1…A-8.
2. **Privacy change, local:** OWNER_SET, migration tool, required-owner floor, owner adapter, tests (Core API suite + slice15b2a static boundaries + new migration tests).
3. **FORGET runner, local:** governed orchestration; DEV_SYNTHETIC entry; tests with all existing owners + a Hermes owner stub.
4. **Executor + units + sandbox, local:** in the Hermes DEV package (`f293e72-f9c1` = F9-B + executor). Mirror test matrix T1–T25 (synthetic).
5. **Upgrade scripts** F8r4→F9 + restore suppression; mirror rehearsal including T18/T21.
6. **Combined mirror rehearsal:** Core API with the Privacy change + runner, Hermes with the executor, end to end.
7. **Review and authorization** for DEV:
   - **(a)** Core API deploy via the normal pipeline (DR-5 EQUAL);
   - **(b)** Hermes F9 install via the upgrade ladder (DR-5 EQUAL, F8r4 preserved);
   - **(c)** Privacy schema migration on DEV.

   Separate approvals.
8. **DEV FORGET drill** (A-8): synthetic canary, 0 provider calls, full host scan. Owner acceptance.
9. **Later, before any real conversation:** owner authentication, V2 signed Privacy authorization (A-4), M2 provenance mapping if more than one principal, PROD review. Then the First Memory milestone path. The single milestone document comes only after genuine First Memory verification.

## 9. Explicit non-goals and limits

- No standalone Hermes FORGET API; no deletion by session id; no new FORGET authority; no change to L18_V2's code or semantics.
- No change to canonical contracts, signer, broker, witness, owner proof, SOUL.md, cognitive architecture, UI or PROD.
- Whole-store purge is **DEV/single-principal only**.
- No physical-erasure or provider-side erasure claims.
- F9-C does not lift the "no real personal conversations" restriction.
