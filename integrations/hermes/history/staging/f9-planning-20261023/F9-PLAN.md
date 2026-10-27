# F9 plan: Hermes privacy hardening before any personal conversation (DRAFT for owner review)

**Prepared:** 2026-10-23, after the owner accepted F8r4 Phase B (synthetic-only).

**Status:** planning only.
- No DEV or PROD change, commit, deployment or provider request.
- All findings come from the packaged Hermes source `f293e72` (F8r4 package `16c7417d…`, read locally) and the Phase B evidence.

**Goal of F9:** make Hermes on DEV a governed conversational front end with no independent memory or profiling. Its conversation history and logs must be erasable under LILITH's FORGET authority, and LILITH's governed First Memory path must stay the only route to durable personal memory.

Real personal conversations stay NOT authorized until F9 is accepted and the separate owner-authentication prerequisites (FI evidence, owner WebAuthn) exist.

---

## F9-1: Disable Hermes's independent profile onboarding

### Root cause (verified in source)

- **Trigger:** `gateway/run.py` (around line 20245) runs when the turn has **no history** and the session store has **no sessions at all** (`has_any_sessions()` false), i.e. the first conversation on the install.
  - It appends a hidden sidecar note to the user message, sent as `api_content`; `content` stores the raw text.
- **Which note:** if `onboarding.profile_build` is `"ask"` (the **default**; `agent/onboarding.py:profile_build_mode`) and `onboarding.seen.profile_build_offered` is false, the note is `profile_build_directive()`.
  - That directive tells the model to offer a profile and collect "name, what they do, how they like you to work".
  - It may also use web_search and save facts with `memory(target="user")`.
  - Otherwise a plain intro note is appended ("briefly introduce yourself … /help").
- **Independent of the memory switches:** `memory.memory_enabled: false` and `user_profile_enabled: false` do **not** suppress it. Only `onboarding.profile_build: off` does.
- **Re-arm defect on DEV:** `mark_seen()` writes `config.yaml`, which is root-owned and read-only to the gateway on DEV, so the "seen" flag never persists. The offer therefore **re-fires whenever the session store becomes empty again**. That happens after a 7-day prune of all sessions, and, critically, after any F9-2 erasure of all sessions.
- **Other hidden sidecar notes** (audit list; none solicit data):
  - `run.py` ~19322: auto-reset "fresh conversation" notes (24 h idle reset is configured);
  - ~20346: voice-channel awareness (not applicable to lilith_os);
  - a one-time **home-channel** user-facing notice (`/sethome`, admin-only on DEV).

### Options (owner decision D-1)

- **A (recommended, config-only):** add `onboarding: {profile_build: off}` to the DEV `config.yaml`. The file is critical-pinned, so this means a package respin to f8r5 and its install. No Hermes code change. The plain intro note remains: benign, about one sentence, and `/help` is refused anyway.
- **B (stricter):** A plus a small vendored patch so lilith_os turns carry **no** first-contact sidecar note at all. This is a source change to the Hermes tree (new F7-style patch and tests). Choose it if the owner wants zero hidden instructions beyond the system prompt.

### Acceptance tests (mirror, synthetic provider, 0 real calls)

1. **Fresh store:** the first message's `api_content` contains no `profile`/`memory`/`web_search` directive (A: only the plain intro note; B: `api_content` is NULL).
2. **Re-arm:** after deleting all sessions (F9-2 adapter), the next first message still has no profile directive.
3. **Request structure** (the C9 method from Phase B): the provider request's first user message equals the expected effective text.
4. **Pins:** `verify_release.py` critical pins include the onboarding key; the F7 suite stays 19/19.

---

## F9-2: Close Hermes conversation-history and log erasure gaps

### Data inventory on DEV (what can hold conversation content)

| # | Location | Content | Today |
|---|---|---|---|
| H1 | `HERMES_HOME/state.db` (+ `-wal`, `-shm`): `sessions`, `messages` (`content`, `api_content`, `reasoning*`), FTS5 indexes (`messages_fts*`) | full transcripts | 7-day prune of **ended** sessions; no secure delete. Deleted rows persist in free pages and WAL frames until VACUUM and checkpoint. |
| H2 | `HERMES_HOME/sessions/` transcript files (`.json`, `.jsonl`, `request_dump_*`) | transcripts, request dumps | removed only via `delete_session(sessions_dir=…)` |
| H3 | `logs/gateway.log`, `agent.log`, `errors.log` | INFO inbound previews (VALIDATE profile); errors may quote content | 2-day age deletion |
| H4 | `logs/lilith-router-decisions.log` | ≤ 60-char `preview` per turn | 2-day age deletion |
| H5 | journald namespace `hermes-gateway-dev` (gateway and gate) | gateway messages; the gate logs **no** bodies | 2-day journal retention |
| H6 | `pending_messages/`, `gateway_state.json`, `channel_directory.json`, `cache/`, `image_cache/`, `audio_cache/`, `state/`, `memories/` | queued messages, metadata, media | not covered |
| H7 | `/var/backups/hermes-gateway-dev/`: `upgrade-pre-*`/`pre-*` (tar of HERMES_HOME), `rollback-*` and `f8r2-preserved-*` quarantines, `f8r4-evidence/` | full copies of H1–H6 | never erased |
| H8 | Groq (provider) | request and response | ZDR enabled (O-2); provider attestation only |
| H9 | Core API `/os/conversation` relay | none for non-capture sessions (F2/F3 finding); capture sessions are already covered by L18_V2 (F4/F5) | covered |

### Proposed design (owner decisions D-2 to D-6)

**Hermes erasure owner:** a root-run oneshot `hermes-gateway-dev-forget.service` is invoked by the existing **L18_V2 FORGET** runner as a subordinate erasure owner, in the same pattern as F4's `capture_evidence_path`. It is not an independent deletion API. Sequence:
1. Stop the gateway (exclusive access).
2. Run `delete_session()` for every selected session (D-3: owner-wide = every `lilith_os` session on single-owner DEV), including `sessions_dir` files.
3. Delete orphaned FTS rows, `PRAGMA secure_delete=ON`, `wal_checkpoint(TRUNCATE)`, `VACUUM`.
4. Rotate and remove H3 files. Rewrite H4 without the erased chats' lines, or drop `preview` going forward (D-2).
5. Rotate and vacuum the H5 namespace (journald cannot delete selectively; D-4 = keep content out of the journal with the WARNING profile, and vacuum the whole namespace on FORGET).
6. Purge H6 entries.
7. Purge or forbid H7 copies (D-5).
8. Restart the gateway.

**Receipt:** counts and hashes only, joined to the L18_V2 receipt. It is retryable with the same authorization (the F4 pattern). It fails closed: if any step fails, Privacy stays incomplete.

**Restore suppression:** no backup or quarantine of HERMES_HOME may be restored after FORGET. Either backups carry no conversation state (`backup_pre_install` excludes `state.db`/logs/sessions), or they are enumerated and erased.

**Ordering constraint:** **F9-1 must land before F9-2.** Erasing all sessions re-arms the onboarding trigger (`has_any_sessions()` false).

### Verification method

A **canary test** in the mirror. A unique synthetic marker goes through console, Core API relay and a UI-path turn. Then FORGET runs, followed by a raw byte scan of `state.db`/`-wal`/`-shm`, `sessions/`, logs, decisions log, journal files, backups and quarantines. The required result is **0 occurrences**, plus `has_any_sessions()` semantics and F9-1 test 2 (no re-armed profile offer).

---

## F9-3: Preserve LILITH's governed First Memory design

Invariants F9 must keep, each enforced by pins or tests:

- **FM-I1: Hermes is never a memory of record.** These stay off and critical-pinned:
  - `memory.memory_enabled`, `user_profile_enabled`;
  - the `memory` and `session_search` toolsets;
  - `onboarding.profile_build`;
  - skills, curator, background review.

  Hermes state is a bounded conversational cache (24 h reset, 7-day prune, FORGET-erasable).
- **FM-I2: one path to durable memory.** Only LILITH's governed First Memory path admits durable memory:
  - FI evidence capture (owner-token gated relay, `conversation_evidence` gate);
  - `admission_v2`/L04 V2 with the FM-02 `FirstInteractionEpisodeV1` profile;
  - signer and witness;
  - owner proof.

  Hermes output never feeds canonical admission directly. `canonical_ltm_enabled: false` stays, and `app.py` never imports `lilith_memory` (existing test).
- **FM-I3: FORGET authority stays with L18_V2.** The Hermes erasure is a subordinate owner whose receipt joins the L18_V2 receipt. The F5 restore-suppression manifest also covers Hermes copies.
- **FM-I4: no personal data before readiness.** Hermes receives no personal data until F9 is accepted, owner authentication exists, and the FI capture UI path is owner-authorized.
- **FM-I5: no governed-module drift.** F9 changes no governed shared module (`canonical_contracts.py`, signer/broker pins); DR-5 stays EQUAL. If F9-2 integration touches `privacy_governance.py`/`memory_v2.py`, check first whether they are in any governed pin set.

---

## Proposed slices (each needs separate owner approval)

| Slice | Scope | Environment | Provider calls |
|---|---|---|---|
| F9-A | Owner review of this plan; decisions D-1 to D-8 | none | 0 |
| F9-B | f8r5 package: onboarding off (+ option B patch if chosen), the decisions-log `preview` policy, backup exclusion; mirror tests (F9-1 tests 1–4) | local + WSL mirror | 0 (synthetic) |
| F9-C | Hermes erasure owner (oneshot + scripts) + canary test in the mirror; then the Core API L18_V2 runner integration as a reviewed PR | local + mirror; repo PR later | 0 |
| F9-D | DEV install of f8r5 (upgrade from accepted f8r4, F8r4 preserved for rollback) + DEV FORGET drill on synthetic sessions with the canary scan | DEV | 0–2 (D-7) |
| F9-E | Owner acceptance; housekeeping of F8 artefacts (D-8) | DEV | 0 |

## Owner decisions needed

| ID | Decision |
|---|---|
| D-1 | Onboarding: config-only `profile_build: off` (A, recommended) or A + no-sidecar patch (B) |
| D-2 | Router decisions log `preview`: drop (recommended), hash, or keep and erase on FORGET |
| D-3 | Erasure granularity on DEV: owner-wide (all lilith_os sessions, recommended for single-owner DEV) or per-session selector |
| D-4 | Journal: keep content out (WARNING profile) + vacuum the whole namespace on FORGET (recommended) |
| D-5 | Backups/quarantines of HERMES_HOME: exclude conversation state from future backups + erase existing copies on FORGET (recommended) |
| D-6 | Provider side: accept Groq ZDR (O-2) as the provider-side erasure position, documented as attestation, not verified |
| D-7 | DEV validation budget: validate F9-1 on DEV with a small, separately approved provider budget (a new owner-approved RESET), or rely on the mirror plus a DEV config/pin check only. Budget is currently exhausted. |
| D-8 | Housekeeping of F8 artefacts holding synthetic conversation copies: `/var/tmp/f8` incl. `amend`, `upgrade-pre-*`, `rollback-*`, `f8r2-preserved-*`, `f8r4-evidence` (keep as acceptance evidence or purge after F9) |

## Out of scope for F9

- Real personal conversations, owner recording, First Memory activation, canonical admission;
- PROD Hermes (the same onboarding default and erasure gaps likely apply there; a separate, PROD-specific review is needed);
- cognitive lanes;
- the gate's ~31 s startup delay (tracked separately).
