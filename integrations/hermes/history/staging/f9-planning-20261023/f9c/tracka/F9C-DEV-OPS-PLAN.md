# F9-C: minimum DEV operational steps (B-2, B-3, B-4), for review (2026-10-24)

**Status:** plan only.
- **Not done:** no DEV contact, no DEV database touched, nothing deployed, no Groq call or budget change.
- **Inputs:**
  - PR [rpahasara/lilith-os#249](https://github.com/rpahasara/lilith-os/pull/249) (commit `8c9f07b`);
  - Hermes package `f293e72-f9c1` `4f899311…` (local);
  - `F9C-TRACKA-RESULT.md`.

## 0. Facts that shape the plan (read from source, not assumed)

| # | Fact | Consequence |
|---|---|---|
| F-1 | `deploy-dev.yml` deploys `main` to DEV automatically after CI on push | **Merging #249 is a DEV Core API deploy.** It needs its own owner go-ahead |
| F-2 | On DEV, `data/privacy_governance.dev.db` and `data/cognitive_memory.dev.db` belong to the **durability probe**: every deploy runs `prepare`, then `verify`, then `cleanup`. `prepare` **refuses if either exists**; `cleanup` **deletes both** | DEV has **no persistent Privacy DB**, so there is nothing to migrate. Drill state at those paths would block every later deploy, and cleanup would delete the drill's FORGET records. **The drill must use its own paths** |
| F-3 | The deployed Core API release is lilith-owned under `…/lilith-os-dev/releases/<sha>` | Already handled: `install_f9c.sh` makes a root-owned pinned copy for the executor |
| F-4 | The package's executor and reconcile units bind exactly `data/privacy_governance.dev.db` into their sandbox | A small respin is needed to bind the drill DB path instead (§2) |
| F-5 | CI on #249: **Core API tests PASS, Repository contracts PASS**. **Frontend audit FAIL**: new critical Next.js advisory after `next 16.3.8` (main passed on 2026-10-22). The aggregate check `LILITH DEV deployment` FAIL | External advisory drift, unrelated to #249. A separate Next security PR must land before any merge |

**Compatibility of #249 with the installed F8r4 DEV** (if merged, i.e. deployed):
- **Inert.**
  - `app.py` relays exactly as before on a host without `/var/lib/hermes-forget` (DEV today; tested).
  - The new modules have no route and nothing imports them at runtime.
  - The probe's fresh v1 Privacy DB has no owner floor, so FORGET follows the b9eb32c code path (CI probe test + b9eb32c compatibility tests).
  - The F8r4 gateway is untouched.
- **The only effect is the normal deployer restart of `lilith-os-api-dev`.**
- **After F9 is installed:** every later Core API deploy needs `install_f9c.sh --repin` before the next FORGET. The executor imports its pinned copy, and the copy must match the deployed code.

## 1. B-4: read-only DEV preflight (one script, root, IAP; output content-free)

1. **Host:** hostname is `lilith-dev-01`.
2. **F8r4:** `readlink -f /opt/hermes-gateway-dev/current` = `f293e72-f8r4`, and its `RELEASE.sha256` digest = the accepted F8r4 digest (needed by U-1).
3. **Core API:**
   - `lilith-os-api-dev` active;
   - `current` → release SHA, plus `.bundle-sha256`;
   - owner of the `lilith_memory/` files;
   - the five pinned module files present.
4. **Probe baseline clean:** `data/*.dev.db` and `data/canonical-durability-probe` are absent (as `prepare` requires).
5. **No F9-C leftovers:** no `/var/lib/hermes-forget`, `/etc/hermes-forget` or `/home/lilith/.hermes/lilith-os-dev/f9-drill`; no group `lilith-forget`; no `hermes-forget*` units.
6. **systemd hygiene:**
   - no unit with `NeedDaemonReload=yes`;
   - no queued jobs;
   - no dpkg lock;
   - `apt-daily*` not within 45 min.
7. **Space and tools:** free space on `/opt`, `/var` and `/home` (≥ 2 GiB); system `python3` and `systemd-analyze` present.
8. **DR-5:** `dr5_check.sh` from the installed F8r4 release = `F8_DR5_EQUAL 7fe21378…`.
9. **Provider gate (read-only):** key file present (sha prefix only); `gate_budget.sh show` (no reset).
10. **Backups:** `/var/backups/hermes-gateway-dev` inventory (names and sizes).

**STOP and report.**

## 2. The two small changes needed before DEV (local first, then a short re-validation)

These are **no new components**. Package respin `f293e72-f9c2` = f9c1 + the changes below.

1. **Drill paths:**
   - The executor/reconcile units bind `/home/lilith/.hermes/lilith-os-dev/f9-drill/privacy_governance.f9drill.db` (+ `-wal`/`-shm`) instead of `data/privacy_governance.dev.db`.
   - `install_f9c.sh` defaults `F9C_PRIVACY_DB` to that path.
2. **`bin/f9c_dev_drill.py`:** one operator tool, run as `lilith` with the **deployed Core API venv**. It calls only existing library functions:

| Phase | What it does (existing functions) |
|---|---|
| `provision` (B-2) | in the drill dir: `memory_store.migrate` + `slice15b2a_migration.migrate_cognitive` + `first_interaction_migration.migrate` (cognitive DB, with `backup.create_backup` manifests); `slice15b2a_migration.migrate_privacy` (fresh v1), then `privacy_schema_v2.upgrade_privacy_v1_to_v2` + `provision_hermes_owner_floor(DEV_SYNTHETIC)`. It prints only the fingerprints (must equal the accepted v2 `90dd41e5…` / floor `b7256ac0…`). It refuses if any drill file already exists |
| `forget` (B-3) | `LocalOwnerAuthority.from_secret_file` (drill cognitive DB + drill actor key) issues **one** DEV_SYNTHETIC evidence for `first_interaction_forget_action`. Then `HoldFirstForgetRunner(FirstInteractionForgetRunner(PrivacyGovernanceStore.from_secret_file(drill DB, drill key, actor), {L04, L18_V2 (memory_v2) on the drill cognitive DB, HermesConversationErasureOwner(…, SpoolHermesErasureExecutor())}), ForgetIntentStore(), GatewayProbe())` — the same composition as the 51/51 rehearsal |
| `resume` / `status` | `HoldFirstForgetRunner.resume()`; status = intent state, in-flight yes/no, `identity_forget_completed` (no content) |

- **Cancel** stays the root executor's `--cancel-intent --confirm-owner-approved`.

**Re-validation (local, once):**
- the executor mirror P-1 (sandbox sees the drill DB read-only) + M1;
- the rehearsal with the tool replacing the test fixture (D-1, H2/H6/H9, R-0..R-3).

**Never run the mirror's test fixtures on DEV.** The tool creates its own fresh drill stores and never writes `data/*.dev.db`.

## 3. B-2 and B-3 on DEV (after B-4 PASS, #249 merged/deployed, f9c2 accepted)

| Step | Who | Action | Expect |
|---|---|---|---|
| G-0 | owner | authorize the F9 DEV run | |
| U-1 | root | `F8R4_RELEASE_SHA=… preserve_f8r4.sh` | `F8R4_PRESERVED`; Groq key quarantined (no provider call possible afterwards) |
| U-2 | root | `backup_pre_install.sh`; `install.sh` | `F8_INSTALL_STAGED f293e72-f9c2` |
| B-2a | root | create `…/f9-drill` (lilith 0700); drill Privacy key (32 random bytes, `root:lilith 0640`, never printed); drill actor key (lilith 0600) | |
| B-2b | lilith | `f9c_dev_drill.py provision` | fingerprints = accepted v2/floor |
| U-3 | root | `F9C_CORE_API_DIR=$CORE/current/lilith_memory F9C_PRIVACY_SECRET=<drill key> install_f9c.sh` | `F9C_INSTALLED`; DR-5 EQUAL |
| U-3b | owner/deployer | restart `lilith-os-api-dev` (gains `lilith-forget`) | the group is on the process |
| U-4 | root | console token; `verify_release.py --full`; start the gateway | `F8_VERIFY_PASS`; 9901 listening |
| B-3a | operator | 2–3 synthetic canary turns through the Core API relay (no provider: gate `KEY_NOT_PROVISIONED`) | canary in `state.db` only |
| B-3b | lilith | `f9c_dev_drill.py forget` | during the hold: relay 503 `FORGET_HOLD_ACTIVE`, gateway start refused; then `COMPLETE` (L04, L18_V2, HERMES) |
| B-3c | root | canary scan (HERMES_HOME, backups incl. the F8r4 quarantine, `/var/lib/hermes-forget`, namespace journal); receipt + epoch 1; intent and marker gone; gateway back; DR-5 EQUAL | 0 hits |
| keep | | the drill DBs stay (they are the FORGET record); outside the probe's paths, so later deploys are unaffected | |

**Rollback (any time no FORGET is pending):** `rollback.sh remove`, then `restore_f8r4.sh <preserved>`. It is refused while an intent or marker exists; then finish the FORGET or cancel it first.

## 4. Owner decisions before any of this

| # | Decision | Recommendation |
|---|---|---|
| O-1 | A separate security PR bumping `next` past the new critical advisory, to unblock CI for #249 and every other PR | yes, minimal exact pin, no UI change |
| O-2 | Approve the f9c2 respin (drill paths) + `f9c_dev_drill.py`, with the one local re-validation | yes |
| O-3 | DEV FORGET evidence = a DEV_SYNTHETIC `LocalOwnerAuthority` with its own drill key (interim V1, as the DEV probe already does; A-4) | yes |
| O-4 | Drill scope: Hermes store + the First Interaction identity **without** seeding a synthetic FI memory first (L04/L18_V2 erase nothing and record COMPLETE) | yes for the first drill. **Unverified:** that L04/L18_V2 record COMPLETE on an identity with no rows has no test today; the f9c2 re-validation must prove it (if not, seed one synthetic FI memory with the fixture-free tool) |
| O-5 | When to merge #249, given that merge = DEV deploy | after O-1, B-4 PASS and the f9c2 re-validation; immediately before the F9 run |

**STOP. No merge, no deployment, no DEV change.**
