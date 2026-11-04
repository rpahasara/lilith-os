# Canonical memory: PROD release preparation and plan (offline, 2026-11-04)

Status: PREPARATION ONLY. Nothing here has changed PROD, DEV, a key or a provider budget. Each PROD step below needs its
own owner go. Inputs: step 1 (`canonical-memory-release-step1.md`, draft PR rpahasara/lilith-os#312) and owner
decisions D-1 to D-5 (2026-11-04).

| Decision | Owner ruling |
|---|---|
| D-1 | entirely new PROD authority and keys; DEV test keys are never reused |
| D-2 | FORGET scope `CANONICAL_RECORDS_ONLY`; never claim conversation-history erasure |
| D-3 | PROD USER.md stays authoritative until reviewed reconciliation; no silent import, overwrite or deletion |
| D-4 | the existing manual Privacy unlock after each reboot is accepted for the first release; recall fails closed while locked and LILITH otherwise works normally; no automatic-unlock engineering |
| D-5 | personal recall in the authenticated Command Center first, then the owner's private Telegram chat; never in shared Discord channels |

## 1. The 73 DEV-profile references and 41 authority paths, classified

Counts are non-test Python files under `services/`. Tests add 47 files naming `DEV_SYNTHETIC` and 40 with
authority paths. Tests change only where they assert the profile set.

| Class | `DEV_SYNTHETIC` files | `/lilith-authority-dev` files | What they are | PROD needs |
|---|---|---|---|---|
| **Runtime profile layer** | 27 | 8 | the signer profile, owner-proof policy, host inputs, ledger DDL, custody/witness/readiness profiles, Privacy runtime gates, First Memory environment | **yes**: the PROD profile (§2) |
| Ceremony tools (`authority-dev/ceremony/`) | 4 | 3 | keygen, owner tool, installer | yes: profile parameter only |
| `release_file_set.py` | 1 | 1 | the archive layout | no change (paths kept, §2.4) |
| Historical DEV operators (`owner-memory-control/tools/`) | 35 | 29 | M-B/E-19..E-23/FM ladders, DR-5 targets, hostname-pinned to `lilith-dev-01` | **no**: closed DEV history, never run on PROD |
| Docstrings only | 6 | 0 | `privacy_forget_intent`, `synthetic_witness_store` and four package `__init__` notes | no |

The cryptographic contracts below the profile layer already take `environment ∈ {test, dev, prod}` and need no
change: `authority_contracts`, `authority_verifier`, `admission_v2`, `identity_profile`, `owner_freshness` core,
`recovery_contracts`, `rotation_contracts`, `authority_ledger_journal`, `privacy_anchor_contracts` and
`canonical_contracts`. So the PROD work is a profile addition, not a redesign.

### Runtime profile-layer touchpoints (the complete list)

| Module | DEV lock today | Signer/broker pinned? |
|---|---|---|
| `authority-dev/lilith_authority_dev/profile.py` | `environment == "dev"`, key ids `test-only.…dev-synthetic…`, refuses prod | release member |
| `authority-dev/lilith_authority_dev/{issuance,evidence_minter,recovery,ledger}.py` | require the DEV profile; ledger `CHECK(profile='DEV_SYNTHETIC')` | release members |
| `authority-dev/lilith_authority_host/inputs.py` | owner registration must be the synthetic owner `user:synthetic-owner@example.invalid` | release member |
| `authority-dev/lilith_authority_root/verifier.py` | DEV slot contract | release member |
| `core-api/lilith_memory/owner_proof.py` | `DEV_SYNTHETIC` policy pins the synthetic owner, RP and `.invalid` origin | **signer + broker SHARED** |
| `owner-memory-control/lilith_owner_memory/{pr1_bootstrap,successor_custody,successor_readiness,witness_readiness,verifier,pr1_acceptance}.py` | profiles and slot contracts are DEV only; `pr1_bootstrap` refuses `prod` | **signer SHARED** |
| `owner-memory-control/lilith_owner_memory/{owner_acceptance,owner_freshness,first_memory_conversation}.py` | `REAL_PROFILES = {DEV_SYNTHETIC}`, `PROFILE_ENVIRONMENTS`, `ENVIRONMENT = "DEV_SYNTHETIC"` | host tree |
| `core-api/lilith_memory/{privacy_forget_runner,hermes_erasure_owner,privacy_schema_v2,privacy_freshness_host}.py` | interim V1 (HMAC) FORGET path refused outside `DEV_SYNTHETIC`; schema `CHECK(deployment_environment='DEV_SYNTHETIC')` | Core API |
| `recovery-witness/lilith_recovery_witness/{profile,credential,privacy_anchor,core,writer}.py` | DEV witness profile, `PRIVACY_ANCHOR_ENVIRONMENT = "DEV_SYNTHETIC"` | witness release |

## 2. The smallest PROD profile adaptation

**Principle.** Add one second profile, `OWNER_PROD` (environment `prod`), beside `DEV_SYNTHETIC` in every
touchpoint above. Every DEV value, DDL string and refusal stays byte-identical, so DEV keeps working on its installed
releases. Then build a new attested signer/witness/broker release that contains both profiles. Prove it on DEV first:
the DEV transition, DR-5 EQUAL, and the DEV vertical tests unchanged. Then install it fresh on PROD with `OWNER_PROD`
selected.

### 2.1 What `OWNER_PROD` fixes

| Item | `DEV_SYNTHETIC` | `OWNER_PROD` |
|---|---|---|
| environment | `dev` | `prod` |
| key-id prefix / label | `test-only.` / `.dev-synthetic.` | `prod.` / `.owner.`; a test refuses `test-only.` here and `prod.` in DEV |
| K-ROOT / K-ACT / K-WIT / K-PAN / K-PCK | DEV_SYNTHETIC keys | fresh keys from the same keygen tools run with `--profile OWNER_PROD` (D-1) |
| owner identity (owner proof) | `user:synthetic-owner@example.invalid`, `.invalid` RP | the owner's own principal and a real RP id/origin (the `B1A_EXISTING` rule already refuses `.invalid`); one new policy kind `OWNER_PROD` in `owner_proof.py` |
| authority domain / logical owner / policy | `authority.dev-synthetic.memory` / `owner.dev-synthetic.v1` / `policy.dev-synthetic.v1` | `authority.owner-prod.memory` / `owner.prod.v1` / `policy.owner-prod.v1` |
| ledger DDL | `CHECK(profile='DEV_SYNTHETIC')` | the same DDL generated with `'OWNER_PROD'` (a fresh PROD ledger; the DEV DDL bytes are pinned unchanged) |
| Privacy FORGET authorization | interim V1 (HMAC), DEV only | see 2.2 |

### 2.2 One decision inside the profile work (D-6, needs the owner)

The FORGET runner only implements the interim V1 HMAC authorization and gates it to DEV. The design notes say a
signed `PrivacyAuthorizationV2` should come "before any live owner conversation". The V2 contract and verifier exist;
there is no PRIVACY-domain key and the runner is not wired for it.

- **D-6a (smallest): allow V1 HMAC under `OWNER_PROD`.** This matches PROD's existing Privacy V1 key class
  (`privacy_authority.key` already lives in PROD's data dir). The limit, documented: anyone with root on PROD could
  forge a FORGET. The worst case is unwanted erasure of canonical records, never disclosure.
- **D-6b: wire signed V2.** Add a PRIVACY-domain owner key and teach the runner to verify V2. Every FORGET would need
  an offline owner signature. This adds real engineering to the critical path.

Recommendation: D-6a for RC1, with V2 as a tracked follow-up. FORGET is rare, and D-2 already limits its claim.

### 2.3 Size

The 27 runtime files gain an `OWNER_PROD` branch or entry, the 4 ceremony tools gain a `--profile` argument, and the
tests gain PROD cases plus "DEV bytes unchanged" pins. Signer-pinned SHARED modules change, so this means:

- a new attested signer release;
- a witness release, because the witness profile changes;
- a broker release, because `owner_proof.py` is broker-pinned.

It is one source PR and three builds. No new contract, protocol, operation or store is involved.

### 2.4 Kept as-is in RC1 (naming debt, documented)

Unit, user and path names keep their `-dev` spelling on PROD: `/opt/lilith-authority-dev`,
`lilith-authority-dev.service` and so on. Renaming touches 41 files and every installer and operator pin, and it buys
no security, because the profile, keys and environment are what is enforced. Cost: confusing names on PROD. A later
rename can follow once RC1 is accepted.

## 3. PROD reconciliation process (D-3)

1. **Copy (read-only, owner-run or separately approved):**
   `gcloud compute ssh lilith-01 … --command "sudo -n tar -C /home/lilith/.hermes/memories --exclude=*.lock -czf - . | base64 -w0"`
   into a new local folder. Decode it there and check the digests: USER.md 1,241 B `6d7804ef…`, as the 2026-10-27
   audit recorded; `projects/lilith-memory-v2.md` 330 B. Nothing on PROD is written.
2. **Propose:** `reconciliation_importer.py propose <copy> <out>` writes `proposals.json` and `REVIEW.md`, one
   proposal per USER.md entry or note paragraph, verbatim with provenance, plus the review flags.
3. **Owner review:** the owner writes `decisions.json` (`LilithReconciliationDecisionsV1`, bound to the proposal set's
   SHA-256). Each proposal gets CONFIRM, CORRECT (with wording), REJECT, MARK_STALE or KEEP_IN_USER_MD_ONLY.
   Operating rules (style, autonomy) cannot be confirmed as memories; they stay in USER.md.
4. **Check:** `reconciliation_importer.py decide <out> decisions.json` reports pending, invalid, kept, rejected,
   stale and the **admission queue**. It writes and admits nothing. Today `admissibleNow` is 0: no canonical family
   holds owner-profile facts.
5. **Admission (later, separately approved):** only once a reviewed owner-profile family exists, each queued entry is
   admitted individually with owner consent, the same way the origin statement was. USER.md is never edited by any of
   this. If the owner later wants USER.md trimmed, that is a separate, explicit edit.
6. **The origin statement** is re-admitted under PROD authority by the owner (P6 below). DEV admissions are DEV-bound
   and are never copied.

`verify <copy> <out>` proves at any time that the copy is unchanged and every proposal is still pending.

## 4. Private Telegram owner channel: the minimum

The console path validated on DEV does not carry over as is. Telegram's adapter is upstream Hermes code, so there is
no LILITH adapter hook, and PROD's lean social route builds its own prompt.

| # | Change | Where | Why |
|---|---|---|---|
| T1 | one hunk in the existing PROD `gateway/run.py` patch: before the agent-cache signature, call `lilith_router.canonical_note(ctx)` and append it to `combined_ephemeral` | PROD Hermes patch (already carries P1 and the router seam) | one injection point for every platform; the note is then part of the cache signature, so a changed or forgotten memory forces a fresh agent (verified in Hermes `_agent_config_signature`) |
| T2 | `canonical_note(ctx)`: `lilith_os` → channel `lilith_os`; Telegram **only** when `chat_type` is private AND `user_id` equals the owner id already in PROD's Telegram allowlist → channel `telegram_owner_dm`; anything else (Discord, groups, other users) → channel `public` | `lilith_router` (new small module) | channel isolation is decided in root-owned, pinned gateway code; Discord never asks for an owner channel |
| T3 | the lean social reply (`social_lean.reply`) receives the note too | `gateway_integration.py` / `social_lean.py` | today `groq_lean` uses `SOCIAL_POLICY` only, so a casual Telegram turn would drop the memory |
| T4 | the grant v2 gains `"channels": ["lilith_os", "telegram_owner_dm"]` (exact set, no wildcard) in place of the single `channel` | `canonical_context_service.py` + tests | the owner authorizes each owner channel explicitly; `public` can never be granted |
| T5 | the console then uses T1 too, and the DEV-style adapter hunk is not needed on PROD | — | one code path to validate |

What T1–T5 do not change: Discord behaviour, SOUL.md, USER.md loading, routing lanes, tools. Telegram-specific
limitation (D-2): Telegram keeps its own copy of every message LILITH sends, and so does `state.db`. A FORGET never
reaches those.

Validation before enabling Telegram: offline seam tests (private owner DM gets personal memory; a group, another
user and Discord get only `public`); then one owner Telegram check in its own approved window.

## 5. D-4: the owner procedure after a PROD reboot

**While locked:** `/run/lilith-privacy-fresh/verified` is gone, so the gate is not READY. The context service answers
UNAVAILABLE and there is no canonical note. LILITH answers from SOUL.md, USER.md and history as today. Admission and
FORGET refuse. Nothing else is affected (Telegram, Discord, career, goals, timers).

**Unlock** (three phases, about 5–10 minutes, owner's PC with the WSL custody folder):

1. **Challenge (PROD, root):** the host step reads the current boot id and the witness anchor and writes a boot-bound
   challenge (`/run/lilith-privacy-fresh/challenge.json`).
2. **Sign (owner, WSL):** the owner tool signs the challenge with K-PCK from its offline custody folder. The key never
   leaves WSL; only the public unlock document moves.
3. **Apply (PROD, root):** the host verifies the unlock, checks that the Privacy anchor chain equals the K-PCK
   checkpoint chain (no rollback), and writes the marker. The gate is READY and recall works from the next turn. No
   restart is needed.

**PROD-specific requirements (from the DEV run):**
- the driver must read the boot id at run time; DEV's driver hard-codes it;
- the context socket must be **enabled** on PROD, so the route is back after a reboot and simply answers UNAVAILABLE
  until the unlock (on DEV it is started, not enabled);
- one owner-visible "canonical memory is locked" notice after a reboot is optional and out of RC1 unless approved.

**Limitations:**
- Restoring a PROD snapshot taken before a FORGET or a checkpoint rolls the Privacy DB back. The gate then refuses
  until the owner reconciles, which is correct. Every later window's return plan must include this.
- Losing the K-PCK custody folder means no unlock at all. The owner's offline backup of K-PCK is a prerequisite
  for PROD; on DEV that backup was never made.

## 6. Consolidated release plan

Each row is its own owner go and window. PROD stays byte-unchanged in user-visible behaviour until P7, and P8 is the
only Telegram change. Every PROD window starts with a fresh snapshot and has a reviewed return.

| Step | Where | What | Done when |
|---|---|---|---|
| P0 | owner | D-6 (recommend 6a); approve the read-only `memories/` copy; review draft PR #312 | decisions recorded |
| P1 | source | merge #312 (routine DEV Core API deploy; the DEV route is unaffected: its files live outside the Core API) | main green, DEV re-checked with `cm1_window.sh check` |
| P2 | source | PROD profile PR (§2) + PROD adapter path (§4 T1–T5 for the console; Telegram behind its own flag) | offline suites green, DEV bytes pinned unchanged |
| P3 | DEV | build the new signer/witness/broker releases from P2's merge; one DEV transition (FM-2 ladder); DR-5 EQUAL; `cm1_window.sh check` + one bounded recall turn | DEV unchanged in behaviour on the new release |
| P4 | owner | PROD custody ceremony with `--profile OWNER_PROD`: K-ROOT, K-ACT, K-WIT, K-PAN, K-PCK, owner credential; offline backups made and verified | pins recorded, no DEV key involved |
| P5 | PROD | snapshot; inert install: authority/witness/broker releases, Core API memory package, L04 v1→v3 and Privacy V1→v2 migrations with backups (existing rows proven equal), anchor, host tree, owner registration; `canonicalLtmEnabled=false`; context units installed **but no grant** | existing data equal; gateway and the 14 protected files untouched; LILITH unchanged |
| P6 | PROD | Privacy activation: pins, genesis, K-PCK checkpoint, first unlock → READY | gate READY; still no grant |
| P7 | owner + PROD | origin statement re-admitted (enable only its capability, one consented turn, disable); importer proposals reviewed (`decide`); then the console grant v2 (`lilith_os` only) | owner console check: origin recalled, voice and routing unchanged, no-write check equal |
| P8 | owner + PROD | Telegram: grant adds `telegram_owner_dm`; one owner Telegram DM check; Discord check shows no personal memory | owner acceptance |

G-3 (Hermes conversation-history erasure) is not on this path (D-2). An owner-profile canonical family (needed to admit
USER.md facts) is a separate, later slice; until then USER.md stays authoritative.

**Rollback per step:** P5 to P6 are inert, so the return is the snapshot plus restored files and DBs from that step's
backups. P7 and P8 return by removing the grant: one file, effective on the next turn.
