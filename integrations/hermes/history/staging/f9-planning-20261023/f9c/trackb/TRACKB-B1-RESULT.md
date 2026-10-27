# Track B (Privacy rollback protection): offline foundation result (2026-10-25)

**Verdict: `TRACK_B_OFFLINE_READY`.**
- **Done:** the non-governed half of Track B (Rev 1 B1 + the Core API part of B5) is implemented and tested offline.
- **Not done:** the governed half (witness K-PAN module, K-PAN / K-PCK ceremonies, authority-dev release, F9-C package install) needs owner approval.

**Constraints held:**
- No DEV, PROD or GCP contact.
- No Groq call, real key, commit or push.

## F9c2 closed

`F9C2_DEV_SYNTHETIC_FORGET=PASS` is recorded in `tracka/devops/F9C2-DRILL-RESULT.md`:
- `F9C2-DRILL-SHA256SUMS`: all 10 entries re-verified OK today;
- result sha16 `e5d18375ced2f9d0`.

The single-use reference `owner-g0-f9c2-drill-20261025` is consumed.

## Source of work

- **Worktree:** `lilith-os-trackb`, branch `feat/trackb-privacy-anchor-v0.1` @ origin/main `3f6b909f` (uncommitted, `git add -N`).
- **Patch:** `trackb-b1-offline-foundation.patch`, sha256 `7483e76a39e2859fdc067c51e779ced782c64dc5187193ed4c91bc037a92a387`, 11 files.
- **Design basis:** `f9c/anchor/F9C-ANCHOR-DESIGN-REVISION-1.md` (owner-approved final architecture). There is no redesign.
  - **One placement choice:** the pure anchor/checkpoint contract lives in `core-api/lilith_memory/` (like the pinned `owner_proof.py`), not in `owner-memory-control/lilith_owner_memory/`. Reason: the Core API (which must verify) never imports OMC, while OMC and the witness may import `lilith_memory`.
  - **Pinning:** the `SHARED_HASHES` pin is still a B4 addition, with no re-pins.

## What already existed and is reused (no change)

| Need | Existing component (source) |
|---|---|
| Hold, erasure, receipt | `privacy_governance.py` (sole FORGET authority, append-only `privacy_restore_suppression_manifest`); `privacy_forget_runner.py`; `hermes_erasure_owner.py`; installed executor (F9c2 PASS) |
| Restore suppression | `RestoreSuppressionGate` / `GatedPrivacyHoldResolver` (privacy_governance.py:1071-1128), `memory_v2.restore_gated_hold_resolver` |
| Hold-first | `privacy_forget_intent.py`, app.py:1572 `503 FORGET_HOLD_ACTIVE`, F9-C hold/executor units, gateway drop-in `!intent` / `!marker` |
| Off-host owner storage pattern | owner freshness replicas + create-only publish (`owner_freshness_tool.py`, Replica A/B). The pattern is reused; the records are NOT, so K-PCK stays separate from K-ROOT custody |
| Freshness transport | witness owner socket design; witness `protocol.py` stays byte-identical (Rev 1 N-2) |

## Exact gaps found (source evidence) and what closed them

1. **A Privacy rollback defeated the F9-C gate.** `RestoreSuppressionGate.check` trusts whatever the local Privacy DB says: privacy_governance.py:1086-1103 lists suppressions from the local store only. A restored pre-FORGET Privacy DB + cognitive DB therefore reads READY and serves forgotten content.
   - Reproduced as a negative control: `test_privacy_only_restore_after_a_forget_is_refused_where_the_f9c_gate_alone_serves`.
   - **Closed offline:** `PrivacyFreshnessGate` (L == S against a root-published, this-boot marker), now REQUIRED by `restore_gated_hold_resolver(..., freshness=...)`.
2. **No anchor, checkpoint or boot unlock existed** (no `PrivacyAnchor` / `DurabilityCheckpoint` / `lilith-privacy-fresh` anywhere in the repo).
   - **Closed offline (contracts):** `privacy_anchor_contracts.py`:
     - `PrivacyAnchorV1` chain (K-PAN);
     - `PrivacyDurabilityCheckpointV1` extension-only chain with a fork alarm (K-PCK);
     - nonce- and boot-bound `PrivacyFreshnessUnlockV1`;
     - `classify_boot_freshness` → FRESH / OLDER_THAN_CHECKPOINT / DIVERGED / REPLAYED / UNVERIFIABLE.
   - The two key families have their own id prefixes (`kpan.` / `kpck.`) and four separate signing domains, so they cannot cross.
3. **The runner erased before durability.** privacy_forget_runner.py `resume()` went from `begin_forget` straight to the owners.
   - **Closed:** an optional `durability_barrier` (`privacy_freshness.DurabilityBarrier`). Owners erase only after the new suppression set is anchored AND owner-checkpointed; otherwise the result is `INCOMPLETE_HOLD_ACTIVE` with nothing erased and `resume()` continues later.
   - It is optional only so that the installed F9c2 DEV drill tool keeps working. The live runner path must pass it (see First Memory item 6).
4. **The Core API memory gate did not refuse while an intent existed** (Rev 1 §4 defense in depth).
   - **Closed:** `PrivacyFreshnessGate` refuses `FORGET_INTENT_PENDING`.
5. **No owner-device tool for K-PCK existed.**
   - **Closed offline:** `owner-memory-control/tools/privacy_checkpoint_tool.py`:
     - keygen custody 0700/0600;
     - extension-only checkpoints, with `alarms.jsonl` on a fork;
     - an unlock signed only after its own FRESH check.
   - It is outside every release set and outside `lilith_owner_memory/`, where `test_b1b3b_broker_signing_l04_v2` forbids private keys. That test caught my first placement.

**Still open (governed; owner approval required):**
- **G-1 (B2):** the witness `privacy_anchor.py` module + `PrivacyAnchorSigningKeyV1` credential class + owner-socket routing. That is witness runtime source.
- **G-2 (B3):** K-PAN (witness-custodied, encrypted credential on DEV) and K-PCK (owner device) ceremonies.
- **G-3 (B4):** the authority-dev release program:
  - a new candidate, a `SHARED_HASHES` addition for `privacy_anchor_contracts.py`, attestation and ladder;
  - DR-5 must stay EQUAL (no deployer/sudoers change); the observation delta is recorded.
- **G-4 (B5 install):** an F9-C package respin, f9c3:
  - root units: boot challenge/unlock, advance + publish after FORGET;
  - the gateway drop-in `ConditionPathExists=/run/lilith-privacy-fresh/verified`;
  - the runner/drill wired with the barrier.
- **G-5 (B6):** genesis + genesis checkpoint on DEV, and a governed rehearsal that includes a whole-host snapshot rollback → refused.
- **R-8:** the K-PAN rotation and compromise procedure (required before live; not designed).

## Tests (all local)

**Windows:**

| Suite | Result |
|---|---|
| Core API | **316 OK** (main baseline in a clean worktree: 293 OK; +23 new; 13 skips unchanged) |
| Track B Core API suite | 23/23 |
| Owner-tool suite | 6/6, stable 8/8 runs after the O_BINARY fix |
| Focused OMC accepted-read (updated) | 3/3 |
| `test_b1b3b_broker_signing_l04_v2` | 42/42 |
| Broker validation closure | 24 OK |
| Cognitive regressions | 382 |
| compileall | OK |

**WSL Ubuntu-24.04 (`PYTHONPATH=/root/l1deps`):** compared with origin/main, using the same environment for both:

| Suite | Track B tree | origin/main |
|---|---|---|
| OMC | 1789 | 1783 |
| authority-dev | 128 | 128 |
| recovery-witness | 44 OK | 44 OK |

- **Failure sets are IDENTICAL** for all three. The 412 OMC + 5 authority-dev errors are environment import gaps present on both trees.
- **Track B freshness suite on Linux:** 23/23, including the real POSIX mode check on the marker.

**Mutations:** 10/10 caught (`mutate_trackb.py`).
- Each mutation weakens one guard: older-L serving; boot id; intent; `is_held` freshness; barrier; replay; host-older; same-version checkpoint; owner FRESH check; anchor re-append.
- One equivalent mutation was replaced with a stronger one, and a direct `is_held` test was added.

**Defect found and fixed:** on Windows `os.open` without `O_BINARY` text-translates raw key bytes, which corrupted 1 key in ~8.

**Boundary checks:**
- No file under authority-dev, recovery-witness or memory-broker changed.
- `canonical_contracts.py`, `owner_proof.py`, `privacy_governance.py` and `app.py` are unchanged.
- No UI or SOUL.md change.
- The broker-packaged closure is unchanged: memory_v2 and privacy_governance are not packaged.

## Next owner action (exact)

**Decision 1 (offline, recommended now):** approve B2 local implementation, in this branch with no install:
- `recovery-witness/lilith_recovery_witness/privacy_anchor.py`;
- `+ PrivacyAnchorSigningKeyV1` in `credential.py`;
- owner-socket routing of protocol id `LILITH_PRIVACY_ANCHOR_DEV` in `server.py`;
- witness release-set entries;
- Rev 1 compatibility checks 1-6 run locally.

`protocol.py`, `core.py`, `writer.py`, `storage.py` and `profile.py` stay byte-identical. The signer, broker, authority runtime, K-WIT and K-ROOT are untouched.

**Decision 2: the first real Track B operation (off-host, owner device; no LILITH host contact):** K-PCK DEV_SYNTHETIC generation.

> I authorize generation of the DEV_SYNTHETIC Privacy checkpoint key K-PCK on my workstation's WSL Ubuntu-24.04 (root; off-host from lilith-dev-01), using `services/owner-memory-control/tools/privacy_checkpoint_tool.py` from patch `7483e76a…a387`:
>
> `keygen --custody /root/lilith-privacy-kpck-dev-synthetic-01 --environment DEV_SYNTHETIC --key-id kpck.dev-synthetic.01`
>
> - Only the public pin (`kpck.pin.json`) may leave that directory.
> - One owner-made offline copy of the custody directory is allowed. It goes to a separate owner location, never the repository, the DEV VM or cloud storage.
> - This key is TEST-scope (DEV_SYNTHETIC). It is distinct from K-ROOT, K-WIT and K-PAN, and it signs nothing until the B6 genesis checkpoint.

**Decision 3 (later, governed):** B3 K-PAN ceremony + B4 release + f9c3 install + B6 genesis/rehearsal. Each needs its own approval.

## First Memory readiness (remaining after Track B)

Path: real conversation → owner-approved memory → L04 admission → verified storage → later recall.

1. **Owner authentication is absent.**
   - `src/lib/conversation/owner-capture-auth.ts:30` always returns `OWNER_AUTHENTICATION_UNAVAILABLE`.
   - `owner_proof.py` verifies WebAuthn assertions (fido2), but there is no owner credential enrollment, login/session, or UI start/seal control.
2. **Consent and owner approval:**
   - Evidence binding exists: `conversation_evidence.FirstInteractionEvidenceGate` runs `verify_episode_evidence`, conversation_evidence.py:166.
   - Still needed: a real owner signature over the episode at admission (WebAuthn, item 1), and owner acceptance of the pinned identity profile + charter.
3. **The signer refuses the FI purpose.**
   - `authority-dev/lilith_authority_dev/protocol.py:146-151` validates with `canonical_contracts.FrozenMemoryActionV1`, and `VALID_PURPOSES = {LONG_TERM_PERSONAL_PROJECT_RECALL}` (canonical_contracts.py:38).
   - `OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION` (memory_action_v2.py:34) therefore needs a signer release (an authority release program).
4. **Privacy V2:** `PrivacyAuthorizationV2` / `verify_privacy_authorization` exist (authority_contracts.py:401, authority_verifier.py:327). The Core API still uses the V1 HMAC (DEV_SYNTHETIC only, A-4), and no Privacy key is provisioned.
5. **Isolation:** a dedicated Hermes service account (A-3) is needed; the gateway still runs as `lilith`, the same uid as the Core API.
6. **Live FORGET path:**
   - `FirstInteractionForgetRunner` refuses non-DEV_SYNTHETIC (`INTERIM_V1_PATH_DEV_SYNTHETIC_ONLY`).
   - A V2 runner with a mandatory durability barrier, and a runner that passes the capture path, are needed.
7. **Recall wiring:** no runtime caller builds the gated resolver yet. The serving and admission runtime must build `restore_gated_hold_resolver(..., freshness=PrivacyFreshnessGate(...))`.
8. **Operations:**
   - disable the hidden onboarding profile-offer note;
   - the Groq budget is exhausted 5/5, so real conversation needs an owner budget decision;
   - provider ZDR is attested, not verified.
