# Slice 15B1 — Canonical LTM Foundations · Deployment Record (PASS)

- **Date:** 2026-09-09
- **Target:** `lilith-01`, offline/internal L04 storage infrastructure
- **Final L18 mode:** `memory_consolidation_enabled: true`, `memory_consolidation_mode: SHADOW`
- **Final L04 mode:** `canonical_ltm_enabled: false`
- **Production canonical rows:** zero

## Baseline

- Repository: `C:/Users/edufo/Documents/Projects/lilith-os`
- Branch: `master`
- Starting HEAD: `149d0bcd6ca0bf9d32f479b51cb0b54a38e8501b` — `docs: record Slice 15A Learning Consolidation architecture`
- Initial status: exactly ` M .claude/launch.json`
- Initial staged files: none
- Initial untracked files: none
- `.claude/launch.json` remained untouched, unstaged, and uncommitted.
- Local `CURRENT_STATE.md` was absent and was not created. Production `lilith_router/CURRENT_STATE.md` remained byte-identical.

## Fingerprint terminology and starting database

Before Slice 15B1, `cognitive_memory.db` contained only the six Slice 15A L18 tables. The two starting fingerprints were deliberately recorded under different names:

- L18 internal migration fingerprint: `07b0c8a7b59b2d8687acc103f0059a9f37c50653fd4ee3eae0df82d2379d400e`
- complete `cognitive_memory.db` schema fingerprint: `b1fd47f0378f595c574c67d808907910f607a209a170be041c078a7753810a90`

Starting L18 rows were `learning_schema_migration=1`, `learning_job=1`, `learning_cursor=1`, `learning_candidate=3`, `learning_candidate_source=3`, and `learning_assessment=3`. The cursor was `CAREER_WATCHER / career_events / INTEGER_EVENT_ID = 6`. No `learning_proposal` or `memory_*` table existed. Integrity was `ok`, foreign-key violations were zero, permissions were `0600 lilith:lilith`, and 8.42 GB was free.

## Verified pre-migration backup

The SQLite online-backup API created:

`/home/lilith/.hermes/lilith-os/data/cognitive_memory.db.bak.slice15b1.20260909T164925Z`

- SHA-256: `2ae2cfcee290845cfdf0d8aa72099f4e7e2f22e20e35abaa230a275e2555ec56`
- size: 73,728 bytes
- owner/group: uid/gid `1002:1002` (`lilith:lilith`)
- permissions: `0600`
- backup `integrity_check`: `ok`
- backup schema fingerprint: exact match to the pre-migration complete fingerprint
- backup table counts: exact match to all six pre-migration L18 counts
- source identity bound by resolved path, device, and inode

The migration revalidated the backup checksum and source identity immediately before beginning.

## Runtime files and hashes

| Runtime file | Starting SHA-256 | Final SHA-256 |
|---|---|---|
| `config.py` | `bb04943f4b51b7b4a7f1ecad531d7cf9f3305a8ed90a1a8fe96f0bbcfefdffb5` | `14b0a6e870eb18a7494574fc403c7002ea18bd8761a3f897368572d4f4b60b2d` |
| `router.yaml` | `df37c6c3c5403835872e457c539a049c2c7e592507e56d6749647adee54a7201` | `7d14b571abc73766782fbe2d534e85a4fb1fef628592b478b9747f7c76639586` |
| `memory_contracts.py` | `943ff813564fa667fae6a376a6396c9bd53be254b8f1762391a8a29f652fd273` | `40fe5cfe303668e745e9114cfe5bdc0388c806a5bbcf7314969ef5152481cac6` |
| `learning.py` | `20f7ee3fa2af5e6b789937dfb96b39ee32253c76dd051068dd82e8329315abdf` | `7a74ebbcbfb77c7a68399581b1dd6c4ea74fd432c95a1a0c235bdcf9fcfd87f0` |
| `learning_store.py` | `9b8c54e9e4b4aa3638fe661f7d47f3e053f8f55b92ec224ec0f447f5bf691c5d` | `b8ad2baa35af505593c0043c89979e9b5be617cd82f883464f5a9d7501f9a306` |
| `learning_worker.py` | `9b52d1fd4fa658cd1685c298acfcfd74ace97493ad4fa43217d38fb98be03b5c` | unchanged |
| `memory_store.py` | new | `d9f339c6bcfe2c0d5c50c6da59971a7a5d77d6d1ebd47a83c77e3608bea2001e` |
| `tests/test_learning_consolidation.py` | `49ba1bd1f1b6be61a2ab8a9e2e6e84d0179f42e715b328d70cdcbbeb0450c29c` | `d3539a11f4be37f46c0f8f9c7ac4c3f43af8be1f422cfda06f98f4f3afd2c57c` |
| `tests/test_canonical_ltm.py` | new | `870731860d21c80a4aa3026a50bfc2cbcc4e28722544d64ba900f624b84869a4` |

Every pre-existing runtime target has a `.bak.slice15b1.20260909T164925Z` byte backup with the recorded starting hash. The test-only deployment helper is hash-pinned to all expected starting files and does not install any synthetic registry or authority fixture outside the test module.

The pre-commit diff audit caught and corrected one over-bound fingerprint input: source `occurredAt` was removed so all timestamps are excluded from semantic proposal identity as required. Before installing that code/test-only correction, the immediately prior deployed bytes were preserved as `memory_contracts.py.bak.slice15b1.20260909T171839Z` (`464c791e8e480a668e3e4b0a357734a134c1223e065d0816d300afe24f8ae1bf`) and `tests/test_canonical_ltm.py.bak.slice15b1.20260909T171839Z` (`bb56ccb4ffa9d4add8cbb7bd71342fa45a0de1db08d9bc214055d3910dc7baa9`). The local 109-test suite, remote staging 335-test suite, installed 335-test suite, and installed 53-test canonical subset all passed after the correction.

## Final schema

Migration added only:

- L18: `learning_proposal`
- L04: `memory_schema_migration`, `memory_item`, `memory_revision`, `memory_revision_source`, `memory_active_revision`, `memory_admission`, and `memory_apply_audit`

Final fingerprints:

- preserved L18 internal migration fingerprint: `07b0c8a7b59b2d8687acc103f0059a9f37c50653fd4ee3eae0df82d2379d400e`
- L04 internal migration fingerprint: `ed4e86f675143cc1ea5beaf2abc6a4f171c66013c92dd082a7e712acdc83ed11`
- complete `cognitive_memory.db` schema fingerprint: `7a574619adaef806a567ae7ba6e1d556e4b19c9dfa5c380f2e9a7bbe8c40ae40`

The complete fingerprint uses sorted non-internal `sqlite_master` type/name/table/SQL tuples encoded as canonical JSON. It is not interchangeable with either internal migration fingerprint.

Final database state was `0600 lilith:lilith`, 217,088 bytes, `integrity_check=ok`, and zero foreign-key violations.

### Final row counts

| Table | Before | After |
|---|---:|---:|
| `learning_schema_migration` | 1 | 1 |
| `learning_job` | 1 | 1 |
| `learning_cursor` | 1 | 1 |
| `learning_candidate` | 3 | 3 |
| `learning_candidate_source` | 3 | 3 |
| `learning_assessment` | 3 | 3 |
| `learning_proposal` | absent | 0 |
| `memory_schema_migration` | absent | 1 |
| `memory_item` | absent | 0 |
| `memory_revision` | absent | 0 |
| `memory_revision_source` | absent | 0 |
| `memory_active_revision` | absent | 0 |
| `memory_admission` | absent | 0 |
| `memory_apply_audit` | absent | 0 |

The L18 cursor remained exactly `CAREER_WATCHER / career_events / INTEGER_EVENT_ID / 6 / schema v1`.

Indexes enforce unique proposal fingerprints, exact item identity, revision/audit lookups, and provenance lookup. Foreign keys bind revisions to items/proposals, source snapshots to revisions, apply audits to admissions/revisions, and the active pointer's `(item, revision)` pair to a revision from that same item. Triggers make proposal, candidate/source/assessment, item, revision/source, admission, and audit rows immutable; the active pointer permits only its narrowly validated advance.

No `memory_trace`, embedding, rank, summary, confidence, expiry, deletion, privacy-erasure, personalization, or procedural-skill table exists.

## Production safeguards

- Strict config load: `canonical_ltm_enabled=false`, valid boolean, effective enabled state false.
- `MemoryStore.apply()` checks the switch before database open/mutation.
- Direct production probe returned `REJECTED / CANONICAL_LTM_DISABLED` with null item, revision, active revision, and operation IDs.
- Complete schema, every table count, migration row, cursor, index list, trigger list, integrity result, and foreign-key result were identical before and after the direct probe.
- Production `MemoryRegistry.active_keys()` returned an empty list.
- A constructor guard rejects any non-empty registry targeting the production path.
- Consent, Verifier, and Rollback resolvers are unavailable in production.
- Synthetic schema, registry, and authority fixtures exist only in the isolated test module.

## CREATE / SUPERSEDE / RESTORE acceptance

All mechanics ran with the deployed exact code against temporary databases explicitly guarded from the production path.

| Case | Result |
|---|---|
| A — CREATE | PASS: exact item, immutable revision/provenance, accepted admission, active pointer, and audit committed atomically |
| B — CREATE replay | PASS: `ALREADY_APPLIED`, same identities, no duplicate admission/revision |
| C — SUPERSEDE | PASS: new revision supersedes prior active and advances pointer |
| D — stale SUPERSEDE | PASS: `PRECONDITION_FAILED / ACTIVE_REVISION_MISMATCH`, no partial write |
| E — RESTORE | PASS: creates a new restoring revision from validated historical value |
| F — RESTORE replay | PASS: same apply result, no duplicate revision |
| G — cross-item RESTORE | PASS: rejected with old pointer and rows intact |
| H — missing Consent | PASS: fails closed through unavailable production-style resolver |
| I — invalid/revoked Consent fixture | PASS: rejected; fixture confirms only its explicit isolated reference |
| J — missing Verifier | PASS: procedural-like test policy fails closed; task/HTTP/exit status are not proof |
| K — missing rollback authority | PASS: RESTORE rejected before revision creation |
| L — exact-key retrieval | PASS: returns only the active canonical revision |
| M — lineage | PASS: returns the ordered immutable revision history |
| N — provenance explanation | PASS: bounded source/admission/audit data, no raw payload |
| O — reopen persistence | PASS: item, active pointer, lineage, and audit survive database reopen |
| P — forced transaction failure | PASS: admission/revision/source/pointer/audit all roll back |

## Validation results

- Local artifact compile: PASS.
- Local Slice 15A + Slice 15B1 suite: 109 tests PASS; three expected skips for deployed-package/POSIX-only checks.
- Production-interpreter isolated staging compile: PASS.
- Isolated staging full Slice 8–15B1 discovery: 335 tests PASS.
- Installed tree before migration: 335 tests PASS.
- Installed tree after migration: 335 tests PASS.
- Installed canonical LTM suite: 53 tests PASS.
- Classifier standalone: 18/18 PASS.
- Social Guard standalone: 34/34 PASS.
- Integration fail-open standalone: 14/14 PASS.
- World-context standalone: all checks PASS.

The canonical suite covers separation of candidate/proposal/admission/apply, closed contracts, fingerprints, immutable ledgers, SQL ownership, migration safety/idempotency, verified-backup enforcement, authorities, kill-switch behavior, identity, active-pointer constraints, CREATE/SUPERSEDE/RESTORE, provenance, exact retrieval, lineage, capacity pause, restart persistence, and transaction rollback.

## Existing databases and source

All six pre-existing schema fingerprints remained byte-for-byte equal to preflight:

| Database | Starting = final schema fingerprint |
|---|---|
| `lilith-os/data/lilith.db` | `e95e8d81b8915a01e0b0ec13802b7dcdb183aa08b08357d696918b3a4b43ac46` |
| `state.db` | `25a2c06e1ff93af7d26dda7a9e9f09f57cae55d9ba4abbd62219c8f86b9abf51` |
| `kanban.db` | `f9eddda0793ea44e163a7799e1ee3953fad59adc9d8d523f3597c31b4af6bbcb` |
| `verification_evidence.db` | `18b0262422ffc4058fe43b3aa032ef4972cc60fac0e66b052f29d65c4ffe8f21` |
| `cron/notepad.db` | `1c9e6de77a6795f1b017d3907b45b075c0e52df7ee3e8013d2b346d2bd9c1492` |
| `cron/executions.db` | `ee3647f0011fe520415c708bc9daae2e2e4764152ada88dd29d53efb29be72df` |

The ordered six-field `career_events` projection (`id,event_type,entity_type,entity_id,source,created_at`) remained 11 rows, 11 distinct IDs, range 4–17, zero triggers, fingerprint `a81c8d2d48dd8e210c11e2e0fb4a271e101e9a89a5665781808033b99d8f5865`. No existing career candidate generated a proposal.

## Protected owners and legacy surfaces

| Protected file | Starting = final SHA-256 |
|---|---|
| `world_context.py` | `46b8187e3f6f2ac72c920de9dab12fd9c2841551f6c2aa7c20fd91941e3f0104` |
| `policy.py` | `3eca1aec75716b8a862330f225f29a4c616f807251a88a02ee41417ed2592e1f` |
| `social_guard.py` | `edbc7eec6dc9e2b73463e3a65d563486f31eb2e2f894d75cdc7b370dcf55033e` |
| `gateway_integration.py` | `aef313140372497775b23b482a40c4f72a32de4a00506ad307ba1c541b6b9641` |
| `SOUL.md` | `d082db5aa1a8745460c1c3a3edebaf6fcd196336f5e1a5e8ef7108303bda5ccd` |
| Hermes `gateway/run.py` | `2774eee5e585d80cbb45f5865f2718832c2ec86fdfddf8ead1f781e9b21c2553` |
| Hermes personality | `520cf5dbcda99247e39fecf520eac897d270e28dd26908a5c1686131a0d5f6b0` |
| Hermes background reviewer | `d637a390acdc974e84d2aaaf8a7ec40fd01536347346feffca212e39e3d47239` |
| API `app.py` (Goals and current `/memory/*` owner) | `743a804aa7e3cbb8edf7ff8e3a698a74d4bc17cce2cfefe24c353b52c214d6e2` |
| career source owner | `8ec99391d78b2354bf47dc13332b10c092ac689a999da859c48643b5e4a90c21` |
| Verifier `verification_evidence.py` | `d59e4cc44cb1cb9a971780aab7c9c2c1101f414993ce07d458572ce3b60f57af` |
| Verifier `verification_stop.py` | `dc06e76e711e2c3349ac355ee2d80be1086be0799bac597ca6366b43d5df492a` |
| Verifier `verify_hooks.py` | `bc659e05d1e562dfcf47d8ec17e197674e4199b7687f43b9a9bce420ee1884c6` |
| production `CURRENT_STATE.md` | `1a4bfbbf0212fffa8c892a2790b521760ae0725ba63113cb7cadf6f486612de2` |
| `MEMORY.md` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `USER.md` | `6d7804efb32b158105e017e38857abc09ea6c44b5fb6f39636840c290b792d9c` |

The protected Hermes skills tree remained 2,439 files; the post-deployment canonical path/size/mtime-ns metadata fingerprint is `c7d3d2563657daa24c8d04bc5a5600ddccdcb3354cd9eccbffe1759ca5cf441e`. The deployment did not access or write a skills path.

There was no MEMORY.md, USER.md, skills, background-review, World, Goal, Policy, SOUL, personality, Verifier, legacy `/memory/*`, prompt, retrieval, gateway integration, app.py, frontend, Hsin, OAuth, connector, or external-execution change.

## Restart and units

- Gateway restart: **NONE**.
- Gateway PID: `250061` before and after.
- Final gateway: `active/running`, result `success`, exit status `0`, `NRestarts=0`.
- Daemon reload: **NONE**.
- New systemd service: **NONE**.
- New systemd timer: **NONE**.
- Scheduler: **NONE**.

## Rollback

The fast safety action is already in force: `canonical_ltm_enabled=false`. Because production contains no proposal, admission, revision, pointer, or audit data, no semantic-memory rollback is required.

Code rollback restores the timestamped byte backups and removes only the two newly installed Python/test files under an explicit maintenance action. The empty additive tables may remain because they are backward-compatible. They must not be dropped automatically. If database corruption were ever established, restore the verified pre-migration database only through an explicitly authorized maintenance procedure.

## Boundary preserved

Slice 15B1 did not begin Slice 15B2. No real user, career, or procedural memory was admitted. No real Consent Authority, generalized Verifier authority, Rollback Authority, privacy erasure, prompt consumer, retrieval consumer, scheduler, semantic search, embedding, or LLM consolidation was implemented.

The next slice must separately approve a real class/schema/namespace, real authority integration, privacy/retention policy, retrieval semantics, production enablement, and the first real-memory acceptance.
