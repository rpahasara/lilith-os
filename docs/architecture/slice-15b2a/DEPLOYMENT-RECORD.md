# Slice 15B2a — Canonical Memory Authority Foundations · Deployment Record (PASS)

- Date: 2026-09-10
- Target: `lilith-01`
- Scope: authority, privacy, containment, L18 V2, L04 V2, and read-facade foundations only
- Final L18 mode: `memory_consolidation_enabled: true`, `memory_consolidation_mode: SHADOW`
- Final L04 mode: `canonical_ltm_enabled: false`
- Final production canonical classes and memory rows: zero

## Baseline and stop-gate result

- Repository: `C:/Users/edufo/Documents/Projects/lilith-os`
- Branch: `master`
- Starting HEAD: `f56247d77bf8678cbeaaff768c286a99827e922d` — `docs: record Slice 15B1 Canonical LTM architecture`
- Initial status: exactly ` M .claude/launch.json`
- Initial staged files: none
- Initial untracked files: none
- `.claude/launch.json` remained untouched, unstaged, and uncommitted.
- Local `CURRENT_STATE.md` was absent and was not created.
- Production Slice 15B1 counts, configuration, empty registry, unavailable Consent/Rollback resolvers, permissions, integrity, and foreign keys matched the approved baseline.
- Exact pre-deployment scans of Memory/User, skills, pending/state text, and SQLite databases found zero occurrences of all three forbidden acceptance values.

Service baseline and final state were identical:

| Unit | State/result | Main PID | Restarts | Classification and dependency |
|---|---|---:|---:|---|
| `hermes-gateway.service` | active/running, success | 250061 | 0 | Healthy; no restart required |
| `lilith-os-api.service` | active/running, success | 222144 | 0 | Healthy; no restart required |
| `lilith-career-watcher.service` | failed, exit 1 | 0 | 0 | Known unrelated Google OAuth `invalid_grant` (expired/revoked token); 15B2a does not depend on it |
| `lilith-meeting-prep.service` | failed, exit 1 | 0 | 0 | Known unrelated Google OAuth `invalid_grant` (expired/revoked token); 15B2a does not depend on it |

No failed service was repaired, no service was restarted, and no daemon reload was run.

## Reviewed artifact and staging

The final nine-file source/test archive was:

- local source: `%TEMP%/lilith-slice15b2a-predeploy-20260910T030930Z.tar`
- remote staging source: `/tmp/lilith-slice15b2a-predeploy-20260910T030930Z.tar`
- size: 312,832 bytes
- SHA-256: `74e38b8107f15648f13a91aa66eb7ff53980d676a1f7e8c72ed1d4f64790150c`

The checksum matched on the VM. The suite ran under the Hermes production interpreter against temporary databases. The installer was also applied twice to an exact copied source tree; both runs produced tree digest `db985df1fb29d3f3524091a223390aeef8439286eb3d82973d2ae9f85e67f035`, proving idempotence for the original staged target set. The final focused changes were independently compiled and retested.

Two gates found issues before final acceptance:

1. The first post-install regression found the Slice 14 test's old, hard-coded `policy.py` hash. Only that expected hash was advanced after the authorized Policy extension was diff-reviewed.
2. A deeper containment audit found that a recognized marker could fall through when the valid production registry was empty, and that skill replay needed an explicit pre-bypass recheck. The gate was changed to return `LEGACY_CONTAINMENT_NOT_READY`; a regression and installed integration probe were added. No real Home memory lane existed and no content was persisted during either issue.

No regression was waived.

## Files installed or narrowly patched

New production modules:

- `lilith_router/canonical_contracts.py`
- `lilith_router/canonical_authority.py`
- `lilith_router/learning_v2.py`
- `lilith_router/memory_v2.py`
- `lilith_router/privacy_governance.py`
- `lilith_router/slice15b2a_migration.py`
- `hermes-agent/tools/legacy_canonical_containment.py`

Narrowly patched production files:

- `lilith_router/policy.py`: metadata-only INTERNAL_WRITE capability and lazy Policy store factory
- `lilith_router/learning_store.py`: recognizes additive owner tables without granting L18 V1 ownership
- `lilith_router/memory_store.py`: recognizes additive owner tables without granting L04 V1 ownership
- `hermes-agent/tools/write_approval.py`: containment before pending persistence
- `hermes-agent/tools/memory_tool.py`: containment at direct, batch, staging, and replay paths
- `hermes-agent/tools/skill_manager_tool.py`: containment at direct, staging, and replay-before-bypass paths
- `hermes-agent/agent/background_review.py`: typed memory-lane exclusion before prompt construction
- `lilith_router/tests/test_social_presence.py`: advances only the authorized Policy protected hash

The rollback suffix for all pre-existing source/test targets is `slice15b2a.20260910T024935Z`.

### Runtime source hashes

| File | Before | After |
|---|---|---|
| `policy.py` | `3eca1aec75716b8a862330f225f29a4c616f807251a88a02ee41417ed2592e1f` | `54db43909d8b066fe96e50be1897167c76f568a071522433f630f7f4345a74db` |
| `learning_store.py` | `b8ad2baa35af505593c0043c89979e9b5be617cd82f883464f5a9d7501f9a306` | `b093089f155a0670612e026618fc901df78ebb722f0247fb6cec31f0d417acb8` |
| `memory_store.py` | `d9f339c6bcfe2c0d5c50c6da59971a7a5d77d6d1ebd47a83c77e3608bea2001e` | `84e51fd9995b18fdbc06ae8c6d3f95a70b121fe2f9113b80a62a732cab47e403` |
| `write_approval.py` | `4a98656eebf1f4d5ff57bd67237bb9d540172676fd1301a4a21d8822b1fd23b4` | `38deca1ed2219ddae686965c2c78fe0538be6d3810afcb4d8cb66582a1952e9a` |
| `memory_tool.py` | `7fc28391681c0e3291b6176535a6d88af6aa3673341018a2e7bfed3d6b0b8eb9` | `1c792dae4d30fe6c52e888339bab2e22d52b4f82388c0e2f3ba494f73be73e6e` |
| `skill_manager_tool.py` | `7d55d5704acb3923ef4bdf107cba58a0404b56d1734019594b593da62c23f767` | `82b82a7588269d8f1e96cccfbe162dd3f4da7c4407af7cc08cea52b2f0368512` |
| `background_review.py` | `d637a390acdc974e84d2aaaf8a7ec40fd01536347346feffca212e39e3d47239` | `c0e929ccb903af91f2ddc3556f6d8334a21369aa61dcfd04faba7b840b0b8430` |
| `test_social_presence.py` | `ca2d04593a4fd13e77bc87bfec46c369fe9c1f6f9a005f72d9eb236b70d748e3` | `9e1566b6d3316e83c6b369d30538dea8db90f601bdf6af1fb72f711b2f8cba25` |

New module hashes:

| File | SHA-256 |
|---|---|
| `canonical_contracts.py` | `f93d26d8a7e01d78d25f1f1d9540577cf2a55dfd4d52c4b64c87bef93ad887e0` |
| `canonical_authority.py` | `bd2cfcc1b6852b9a13a3f95a95e1ebc4097124565418ee57fd4719efd44c0540` |
| `learning_v2.py` | `e3fe629dc9109e37728793e21801950b3b43d9fe09e5ca2409303dbbfe96ed31` |
| `memory_v2.py` | `14a98a799084262da0a58112046f09fe25450bce426db3f24c1ebf675a247190` |
| `privacy_governance.py` | `3c57b9c10d19dd7ef127eeaf4a4c124bd9c31b517a68f94f75e6d68a0b166d15` |
| `slice15b2a_migration.py` | `b038e89587e012e2a2b7cc8afae2b3b0a1b461109e0ad90e124e559fc8be9ef5` |
| `legacy_canonical_containment.py` | `c1667e6210a24c95079c2424d65299592bc569de925787ef0b61e852cae5df7e` |

## Secrets and permissions

Three independent 32-byte keys were generated server-side and never displayed:

- `actor_authority.key`
- `privacy_authority.key`
- `legacy_containment.key`

Each is `0600 lilith:lilith`. Loaders reject keys shorter than 32 bytes and, on POSIX, any mode other than `0600`. No key, key content, fixture, database, backup, or production path is committed to the repository.

## Verified pre-migration backup

SQLite's online-backup API created:

`/home/lilith/.hermes/lilith-os/data/backups/cognitive_memory.pre-slice15b2a.20260910T024741Z.db`

- source identity: `/home/lilith/.hermes/lilith-os/data/cognitive_memory.db:2049:1153127`
- pre-migration complete schema fingerprint: `7a574619adaef806a567ae7ba6e1d556e4b19c9dfa5c380f2e9a7bbe8c40ae40`
- backup SHA-256: `f346cf8f96ea1d9a349b7e2103e604310d88396addb6bccd714e7b6a0a6a8ad6`
- size: 217,088 bytes
- mode/owner: `0600 lilith:lilith`
- integrity: `ok`
- foreign-key violations: zero
- schema and every pre-migration table count: exact source match

The migration revalidated the proof immediately before beginning.

## Schema fingerprints and database state

Cognitive owner fingerprints:

| Owner ledger | Fingerprint |
|---|---|
| `actor_schema_migration` | `79ff5aaf1811ef83afd46eb536c228d5554ef3e71c3c8de9153cc2d1c3ac44f2` |
| `consent_schema_migration` | `ab77d9f50389cd2618846cf200ce6a8a71525c7782d70adef10cba2db657ed1d` |
| `policy_schema_migration` | `de3b99f43e5d566172358fd02221c574f38bf6e72cce292900172c05bdcde909` |
| `rollback_schema_migration` | `db44d22c4c68db17e42659c48b5e5b9917af52c1d8083b989f6c127f271c6669` |
| `learning_v2_schema_migration` | `7d0cdfd3bf28d75c15a4c376868c8c844099369ba8a45f6c67be653a4dedb6e2` |
| `memory_registry_schema_migration` | `fecbabf4e878241a08ce7328575517c8663950cd6c455ac8755994c96e4cff5c` |

- final complete cognitive fingerprint: `405f532ddef67bd7d17ec06eef68a7a7a973a641ea1dc288b07641c7e39c9565`
- Privacy owner/complete fingerprint: `900b57647f078ec9b101a2db8f9cae6e2623d2124d85f3eaaeb05f4bf2fdeb40`
- cognitive database: 462,848 bytes, `0600 lilith:lilith`, integrity `ok`, zero FK violations
- Privacy database: 126,976 bytes, `0600 lilith:lilith`, integrity `ok`, zero FK violations
- Privacy config: `PRIVACY_GOVERNANCE_AUTHORITY_V1`, maximum backup retention 30 days, restore suppression required

### Production rows before and after

| Family/table | Before | After |
|---|---:|---:|
| Slice 15A V1 jobs/cursor/candidates/sources/assessments | `1/1/3/3/3` | `1/1/3/3/3` |
| `learning_proposal` V1 | 0 | 0 |
| existing `memory_item/revision/source/active/admission/audit` | `0/0/0/0/0/0` | `0/0/0/0/0/0` |
| actor evidence/consumption | absent | `0/0` |
| Consent grant/revocation | absent | `0/0` |
| Policy decision | absent | 0 |
| Rollback authorization/consumption | absent | `0/0` |
| L18 V2 intent/candidate/descriptor/source/assessment/proposal-ref/proposal | absent | all 0 |
| full-tuple registry entries | absent | 0 |
| Privacy request/hold/authorization/owners/execution/results/receipt/suppression | absent | all 0 |

Each new cognitive migration ledger has one row. The Privacy migration ledger and configuration table each have one row. Those are schema/configuration metadata, not authority grants or memory data. No synthetic production row exists.

## Acceptance and regression results

- Final local Slice 15B2a suite: 55 tests, PASS.
- Final production-interpreter Slice 15B2a suite: 55 tests, PASS; one expected skip because repository-only Home TypeScript sources are not in the `/tmp` archive. The same test passed locally.
- Full router discovery before deployment: 335 tests, PASS.
- Full router discovery after code, after migration, and after final containment correction: 335 tests each, PASS.
- Goal/Executive API suite: 22 tests, PASS.
- Slice 9 Reasoning: 18 tests, PASS.
- Slice 10 Workspace: 24 tests, PASS.
- Slice 11 Motivation: 32 tests, PASS.
- Slice 12 Planning: 40 tests, PASS.
- Slice 13 Ethics: 54 tests, PASS.
- Slice 14 Social Cognition/Presence: 49 tests, PASS.
- Slice 15A Learning: 56 tests, PASS.
- Slice 15B1 canonical mechanics: 53 tests, PASS.
- classifier standalone: 18/18 PASS.
- Social Guard standalone: 34/34 PASS.
- integration fail-open standalone: 14/14 PASS.
- World-context standalone: 39/39 PASS.

The installed containment probe returned `LEGACY_CONTAINMENT_NOT_READY` from the empty-registry gate, pending staging, direct Memory helper, approved Memory replay, and approved skill replay. Pending counts were `memory=0, skills=0` before and after.

### A–DL acceptance matrix

All evidence below is synthetic/isolated unless explicitly marked as a read-only production probe.

| ID | Result and evidence |
|---|---|
| A | PASS — `test_browser_session_and_operator_strings_have_zero_actor_authority` |
| B | PASS — same actor-authority test rejects `operator` |
| C | PASS — local `test_home_conversation_transport_has_no_memory_authority_lane`; production Home sources unchanged |
| D | PASS — `test_actor_evidence_is_hmac_action_request_nonce_and_expiry_bound` |
| E | PASS — `test_modified_request_and_wrong_actor_are_rejected` |
| F | PASS — `test_wrong_action_and_expired_evidence_are_rejected` |
| G | PASS — `test_actor_evidence_replay_is_rejected` |
| H | PASS — `test_modified_request_and_wrong_actor_are_rejected` |
| I | PASS — `test_wrong_action_and_expired_evidence_are_rejected` |
| J | PASS — `test_issuer_secret_is_absent_from_contract_and_database`; repository secret scan |
| K | PASS — `test_cancelled_and_expired_challenges_leave_no_grant` |
| L | PASS — same challenge test |
| M | PASS — `test_consent_grant_is_immutable_and_legacy_approval_is_not_consent` |
| N | PASS — `test_consent_is_separate_payload_purpose_operation_and_actor_bound` |
| O | PASS — same binding test |
| P | PASS — same binding test and operation-drift test |
| Q | PASS — same binding test |
| R | PASS — `test_consent_and_policy_reject_revision_operation_and_restore_drift` |
| S | PASS — same revision/restore-drift test |
| T | PASS — `test_consent_revocation_is_append_only_and_suppresses_resolution` |
| U | PASS — immutable/legacy-approval separation test |
| V | PASS — `test_policy_deny_blocks_consent_challenge_and_grant` |
| W | PASS — action/revision drift and L04 independent-resolution tests |
| X | PASS — action/revision drift tests |
| Y | PASS — `test_policy_decision_is_computed_not_caller_declared` |
| Z | PASS — `test_rollback_rejects_caller_string_and_revision_drift` |
| AA | PASS — `test_rollback_is_restore_only_exact_and_single_use` |
| AB | PASS — rollback caller/revision drift test |
| AC | PASS — rollback caller/revision drift test |
| AD | PASS — rollback exact/single-use test |
| AE | PASS — `test_forget_requires_grounded_actor_and_forget_operation` |
| AF | PASS — `test_forget_creates_exact_hold_keyed_suppression_and_hmac_authorization` |
| AG | PASS — read-facade hold suppression test |
| AH | PASS — L18/L04 privacy-hold tests |
| AI | PASS — `test_runtime_sql_authorizers_preserve_owner_boundaries` |
| AJ | PASS — same SQLite-authorizer test |
| AK | PASS — same authorizer test and immutable Consent test |
| AL | PASS — L04/L18 exact privileged-erasure tests |
| AM | PASS — exact-lineage and authority-owner erasure tests preserve neighbor |
| AN | PASS — `test_l04_and_l18_v1_privileged_erasure_removes_exact_lineage_only` |
| AO | PASS — L04/L18 V1 and V2 owner-erasure tests |
| AP | PASS — `test_l18_v2_and_authority_owner_erasure_is_exact_and_minimized` |
| AQ | PASS — minimized authority-owner erasure test |
| AR | PASS — same test verifies no plaintext receipt |
| AS | PASS — exact hold/keyed-suppression/HMAC test |
| AT | PASS — `test_restore_suppression_verifier_erases_restored_identity_before_ready` |
| AU | PASS — `test_partial_or_failed_erasure_cannot_complete_and_hold_remains` |
| AV | PASS — same partial-failure test |
| AW | PASS — privileged-erasure tests plus production integrity check |
| AX | PASS — privileged-erasure tests plus production FK check |
| AY | PASS — grounded-actor/operation test rejects non-FORGET operations |
| AZ | PASS — same operation test rejects RESTORE |
| BA | PASS — `test_background_review_excludes_typed_memory_lane` |
| BB | PASS — same background-review exclusion test |
| BC | PASS — `test_value_tuple_batch_and_historical_action_are_blocked` plus installed Memory helper probe |
| BD | PASS — same gate and installed Memory helper probe |
| BE | PASS — gate tests plus installed skill-replay probe |
| BF | PASS — value/tuple/batch/historical-action test |
| BG | PASS — installed pending-stage probe; count remained zero |
| BH | PASS — installed Memory and skill replay probes |
| BI | PASS — installed direct-helper probe |
| BJ | PASS — replay tests and installed replay probes |
| BK | PASS — historical-action/value-fingerprint test |
| BL | PASS — `test_unrelated_legacy_write_is_unchanged` |
| BM | PASS — unavailable, weak-key, empty, and nonmatching registry tests |
| BN | PASS — empty/nonmatching registry regression plus no Home authority lane |
| BO | PASS — `test_migration_is_additive_empty_and_fingerprinted`; production V1 counts unchanged |
| BP | PASS — `test_v1_proposal_reference_does_not_reinterpret_v1_rows` |
| BQ | PASS — same V1 reference test and unchanged source rows |
| BR | PASS — same V1 reference test and unchanged assessment rows |
| BS | PASS — same V1 reference test; V1 proposal remains zero |
| BT | PASS — same V1 proposal-reference test |
| BU | PASS — `test_v2_candidate_is_digest_only_and_proposal_is_closed` |
| BV | PASS — same closed candidate/proposal test |
| BW | PASS — `test_normalizer_rejects_arbitrary_payload` |
| BX | PASS — digest-only candidate test |
| BY | PASS — `test_l18_requires_authoritative_refs_and_fresh_semantics` |
| BZ | PASS — same authoritative-reference test |
| CA | PASS — same authoritative-reference test |
| CB | PASS — `test_privacy_hold_and_containment_readiness_block_real_eligibility` |
| CC | PASS — same eligibility test and `test_containment_not_ready_defers_candidate` |
| CD | PASS — `test_each_new_mutation_gets_fresh_candidate_and_candidate_cannot_drift` |
| CE | PASS — same fresh-candidate test |
| CF | PASS — `test_v2_proposal_and_ref_are_immutable_and_fingerprint_bound` |
| CG | PASS — `test_proposal_family_dispatch_and_l04_independent_validation` |
| CH | PASS — `test_unknown_proposal_family_is_rejected_at_registry_boundary` |
| CI | PASS — proposal-family dispatch/L04 independent-validation test |
| CJ | PASS — unknown-family test |
| CK | PASS — independent-validation test |
| CL | PASS — independent-validation test |
| CM | PASS — independent-validation test |
| CN | PASS — `test_l04_restore_requires_exact_one_time_rollback_authority` |
| CO | PASS — `test_l04_privacy_hold_revocation_and_actor_failure_are_independent` |
| CP | PASS — `test_l04_kill_switch_and_empty_family_fail_closed` |
| CQ | PASS — same kill-switch test |
| CR | PASS — same kill-switch test |
| CS | PASS — `test_production_registry_guard_and_empty_registry` |
| CT | PASS — same production-path registry guard test |
| CU | PASS — installed Slice 15B1 53-test mechanics suite |
| CV | PASS — installed Slice 15B1 53-test mechanics suite |
| CW | PASS — installed Slice 15B1 53-test mechanics suite |
| CX | PASS — installed Slice 15B1 stale-precondition regression |
| CY | PASS — installed Slice 15B1 idempotency regressions |
| CZ | PASS — installed Slice 15B1 transaction-rollback regression |
| DA | PASS — facade-only boundary tests; no route exports raw reader |
| DB | PASS — `test_requires_actor_and_exact_registry` |
| DC | PASS — same actor/registry test |
| DD | PASS — `test_hold_revocation_and_miss_return_no_fallback` |
| DE | PASS — same hold/revocation test |
| DF | PASS — `test_valid_exact_read_returns_only_l04_row` |
| DG | PASS — hold/revocation/miss test |
| DH | PASS — `test_read_facade_has_no_legacy_or_context_fallback` |
| DI | PASS — same no-fallback test |
| DJ | PASS — same no-fallback test |
| DK | PASS — same no-fallback test |
| DL | PASS — same no-fallback test |

## Protected-owner proof

Byte-identical before/after:

| Protected file | SHA-256 |
|---|---|
| `world_context.py` | `46b8187e3f6f2ac72c920de9dab12fd9c2841551f6c2aa7c20fd91941e3f0104` |
| `social_guard.py` | `edbc7eec6dc9e2b73463e3a65d563486f31eb2e2f894d75cdc7b370dcf55033e` |
| `gateway_integration.py` | `aef313140372497775b23b482a40c4f72a32de4a00506ad307ba1c541b6b9641` |
| production `CURRENT_STATE.md` | `1a4bfbbf0212fffa8c892a2790b521760ae0725ba63113cb7cadf6f486612de2` |
| `SOUL.md` | `d082db5aa1a8745460c1c3a3edebaf6fcd196336f5e1a5e8ef7108303bda5ccd` |
| `MEMORY.md` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `USER.md` | `6d7804efb32b158105e017e38857abc09ea6c44b5fb6f39636840c290b792d9c` |
| Hermes `gateway/run.py` | `2774eee5e585d80cbb45f5865f2718832c2ec86fdfddf8ead1f781e9b21c2553` |
| Hermes personality | `520cf5dbcda99247e39fecf520eac897d270e28dd26908a5c1686131a0d5f6b0` |
| Verifier evidence/stop/hooks | `d59e4cc…f57af` / `dc06e76…f492a` / `bc659e0…884c6` |
| API `app.py` and current `/memory/*` owner | `743a804aa7e3cbb8edf7ff8e3a698a74d4bc17cce2cfefe24c353b52c214d6e2` |
| career event owner | `5aa0193fbdb891f7dd7c33f56dba3f5fa9da4d390b3d4c03f1206b86c77265a1` |

The two intentional protected-owner changes are fully scoped: Policy gained only the inactive canonical-memory capability/store seam, and background review gained only typed-lane exclusion/fail-closed handling. Their before/after hashes are recorded above. Goal, World, Social Cognition, personality, Verifier, current `/memory/*`, gateway, API, frontend, Hsin, OAuth, connectors, and existing career semantics were not modified.

Final exact forbidden-value scans again returned zero text-store hits and zero SQLite hits. No vector, graph, embedding, Telegram, scheduler, timer, daemon, model, or prompt integration was added.

## Repository closure

The reviewed commit contains only this design record and the `docs/architecture/slice-15b2a/` implementation, test, installer, migration, and deployment artifacts. The commit subject is `docs: record Slice 15B2a canonical memory authority foundations`. The exact immutable commit hash is reported after commit creation because a commit cannot contain its own hash. Final status must contain only the pre-existing unstaged `.claude/launch.json` modification.

## Rollback

1. Leave `canonical_ltm_enabled=false` and both registries empty.
2. If code rollback is required, stop only the directly affected consumer under separate authorization, restore the exact `.bak.slice15b2a.20260910T024935Z` source/test files, and remove only the seven new modules and three keys after resolving exact paths.
3. Do not drop additive tables automatically. The empty authority/registry/Privacy schema may remain backward-compatible.
4. Do not restore the old cognitive database over newer Privacy state. If corruption is established, use only the verified backup through explicit maintenance, replay Privacy suppression before availability, verify integrity/FKs/counts, and then start the consumer.
5. No semantic-memory rollback is presently needed because no production class, authority record, proposal, or memory row exists.

## Boundary preserved and remaining blockers

Slice 15B2b remains entirely undone: no production project-codename tuple, real acceptance value, remember/update/restore/forget action, canonical query path, confirmation UX, Home activation, Telegram, vector retrieval, or graph retrieval exists.

Approved milestone statement:

> LILITH has grounded local-owner, payload-bound consent, privacy-removal, rollback-authorization, policy-binding, legacy-containment, and schema foundations for one future closed canonical-memory class. Canonical writes remain disabled and no real canonical memory exists.
