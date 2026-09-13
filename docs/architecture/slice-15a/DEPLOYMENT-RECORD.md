# Slice 15A — Learning / Memory Consolidation Foundations · Deployment Record (PASS)

- **Date:** 2026-09-09
- **Target:** `lilith-01`, offline Router worker only
- **Final mode:** `memory_consolidation_enabled: true`, `memory_consolidation_mode: SHADOW`

## Baseline

- Repository: `C:/Users/edufo/Documents/Projects/lilith-os`
- Branch: `master`
- Starting HEAD: `6afeaaa2a61ee89fdc3070ddf3c868e7e366c585` — `docs: record Slice 14 Social Cognition architecture`
- Initial status: exactly ` M .claude/launch.json`
- Initial staged files: none
- Initial untracked files: none
- `.claude/launch.json` remained untouched, unstaged, and uncommitted.
- `CURRENT_STATE.md` was absent and was not invented.

## Production source preflight

Source database/table: `/home/lilith/.hermes/lilith-os/data/lilith.db` / `career_events`.

Source owner implementation: `/home/lilith/.hermes/lilith-os/apps/career/career_extractor_v2.py`, SHA-256 `8ec99391d78b2354bf47dc13332b10c092ac689a999da859c48643b5e4a90c21`; its insertion site is at line 1157. The table has an integer primary key, one event-type index, no trigger, and stable ordered IDs.

Starting source state:

- rows: 11
- distinct IDs: 11
- ID range: 4–17
- event types: `career.applied`, `career.discovered`, `career.rejected`
- entity type: `job_application`
- source category: `gmail`
- nulls across the six approved fields: zero
- approved-projection fingerprint: `a81c8d2d48dd8e210c11e2e0fb4a271e101e9a89a5665781808033b99d8f5865`

The exact adapter projection is `id,event_type,entity_type,entity_id,source,created_at`. Existing `confidence`, `payload_json`, and `processed` columns are excluded. The data directory was `0700 lilith:lilith`, `lilith.db` was `0600 lilith:lilith`, approximately 8.2 GB was free, and `cognitive_memory.db` did not exist.

## Starting database schema fingerprints

The fingerprint input was sorted non-internal `sqlite_master` type/name/table/SQL metadata, encoded canonically.

| Database | Starting fingerprint |
|---|---|
| `lilith-os/data/lilith.db` | `e95e8d81b8915a01e0b0ec13802b7dcdb183aa08b08357d696918b3a4b43ac46` |
| `state.db` | `25a2c06e1ff93af7d26dda7a9e9f09f57cae55d9ba4abbd62219c8f86b9abf51` |
| `kanban.db` | `f9eddda0793ea44e163a7799e1ee3953fad59adc9d8d523f3597c31b4af6bbcb` |
| `verification_evidence.db` | `18b0262422ffc4058fe43b3aa032ef4972cc60fac0e66b052f29d65c4ffe8f21` |
| `cron/notepad.db` | `1c9e6de77a6795f1b017d3907b45b075c0e52df7ee3e8013d2b346d2bd9c1492` |
| `cron/executions.db` | `ee3647f0011fe520415c708bc9daae2e2e4764152ada88dd29d53efb29be72df` |

## Tested deployment files and hashes

| Runtime file | Starting hash | Final hash |
|---|---|---|
| `config.py` | `49599036f8a966e9977586fa2b58d1cf033a14af3593e3805ede55493cea5be9` | `bb04943f4b51b7b4a7f1ecad531d7cf9f3305a8ed90a1a8fe96f0bbcfefdffb5` |
| `router.yaml` | `5e205a6ad31c18d9f47b2d50d42a5e58b2c52d1ae224e7821cba802f81a1c69e` | `df37c6c3c5403835872e457c539a049c2c7e592507e56d6749647adee54a7201` |
| `memory_contracts.py` | new | `943ff813564fa667fae6a376a6396c9bd53be254b8f1762391a8a29f652fd273` |
| `learning.py` | new | `20f7ee3fa2af5e6b789937dfb96b39ee32253c76dd051068dd82e8329315abdf` |
| `learning_store.py` | new | `9b8c54e9e4b4aa3638fe661f7d47f3e053f8f55b92ec224ec0f447f5bf691c5d` |
| `learning_worker.py` | new | `9b52d1fd4fa658cd1685c298acfcfd74ace97493ad4fa43217d38fb98be03b5c` |
| `tests/test_learning_consolidation.py` | new | `49ba1bd1f1b6be61a2ab8a9e2e6e84d0179f42e715b328d70cdcbbeb0450c29c` |

The disabled deployment archive SHA-256 was `86dd87af20b8b81e2650ef41d4bd531afc78c2a869f41ae80f586f771bba1450`; the production staging copy matched. Disabled `router.yaml` was `23c1c96f4ece5504f33dfb0ef536aea60752d66b9faa162bb992f02b2a22465a`; final enablement changed only the feature flag and produced the final hash above. A final EOF-only normalization of `learning.py` and `memory_contracts.py` produced their recorded final hashes; the installed 56-test suite was rerun and passed after those bytes were installed.

Rollback backups:

- `config.py.bak.slice15a.20260909T135027Z` — `49599036f8a966e9977586fa2b58d1cf033a14af3593e3805ede55493cea5be9`
- `router.yaml.bak.slice15a.20260909T135027Z` — `5e205a6ad31c18d9f47b2d50d42a5e58b2c52d1ae224e7821cba802f81a1c69e`

## Validation gates

### Local source artifact

- Python compile: PASS
- Slice 15A: 56 tests, PASS; two expected local skips (deployed package context and POSIX permission assertion)

### Deploy-exact isolated tree

- Python compile: PASS
- Full discovered Slice 8–15A suite: 282 tests, PASS; one expected Windows POSIX-permission skip
- This is the previous 226/226 Slice 8–14 regression suite plus 56 Slice 15A tests.
- Classifier standalone: 18/18 PASS
- Social Guard standalone: 34/34 PASS
- Integration fail-open standalone: 14/14 PASS
- World-context standalone: all checks PASS

### Production staging and installed tree

- Production-interpreter staging compile: PASS
- Production-interpreter staging Slice 15A: 56/56 PASS, including `0600` assertion
- Explicit migration executed twice: identical schema fingerprint both times
- Installed-tree Slice 15A: 56/56 PASS
- Disabled real invocation: `DISABLED`, `ledgerMutation=false`; ledger remained empty except its migration row

All source-adapter test data was synthetic and temporary. No production-source mutation test was run.

## Migration and final ledger

Database: `/home/lilith/.hermes/lilith-os/data/cognitive_memory.db`, `0600 lilith:lilith`, 73,728 bytes after acceptance.

- schema version: 1
- internal L18 migration fingerprint: `07b0c8a7b59b2d8687acc103f0059a9f37c50653fd4ee3eae0df82d2379d400e`
- complete database schema fingerprint: `b1fd47f0378f595c574c67d808907910f607a209a170be041c078a7753810a90`
- tables: `learning_schema_migration`, `learning_job`, `learning_cursor`, `learning_candidate`, `learning_candidate_source`, `learning_assessment`
- indexes: partial unique `learning_job_one_open_stream`; provenance lookup `learning_candidate_source_record`
- forbidden/L04/trace tables: none

Final counts:

| Table | Rows |
|---|---:|
| `learning_schema_migration` | 1 |
| `learning_job` | 1 |
| `learning_cursor` | 1 |
| `learning_candidate` | 3 |
| `learning_candidate_source` | 3 |
| `learning_assessment` | 3 |

The one job is `SUCCEEDED`, attempt count 1, `cursor_from=0`, `cursor_through=6`, no failure. The cursor is `CAREER_WATCHER / career_events / INTEGER_EVENT_ID = 6`. All candidates are `VALID`, all assessments are `SHADOW_ELIGIBLE / SOURCE_EVENT_INFRASTRUCTURE_PROOF`, and all three provenance rows retain source record ID, schema version, digest, time, and the bounded subject reference.

A representative safe candidate is:

```json
{
  "candidateClass": "SOURCE_EVENT_CONSOLIDATION_CANDIDATE",
  "admissionBasis": "SOURCE_EVENT_SHADOW_EVALUATION",
  "epistemicBasis": "SOURCE_EVENT",
  "validationState": "VALID",
  "descriptor": {
    "eventType": "career.applied",
    "subjectRef": "career.application:4"
  }
}
```

No source payload, email, note, transcript, CoT, free-form summary, confidence, or numeric score is present.

## Production acceptance A–L

| Case | Result |
|---|---|
| A — fresh bounded batch | PASS: one job, three ordered source refs/candidates/validations/assessments, cursor 0→6, no LTM mutation |
| B — same batch replay | PASS in synthetic deploy-exact test: idempotency hit, zero duplicate candidates/source links |
| C — crash before cursor advancement | PASS in synthetic deploy-exact test: replay after lease expiry, eventual cursor commit, no duplicate |
| D — lease expiry | PASS: reclaim succeeds and stale token cannot commit |
| E — invalid source schema | PASS: terminal failure, no candidate or cursor advance |
| F — oversized/disallowed payload | PASS: structural bound rejects before durable candidate content; excluded payload is never selected |
| G — feature disabled | PASS in production: `DISABLED`, no job/cursor/candidate/trace mutation |
| H — SHADOW enabled | PASS in production: only declared L18 metadata writes; `canonicalMemoryMutation=false` |
| I — legacy memory | PASS: no legacy-memory source/import/symbol exists in the adapter or worker |
| J — verification-like task result | PASS: no procedural source or candidate path; Verification remains independently owned |
| K — Home conversation | PASS by integration boundary: no gateway hook, response mutation, prompt injection, or chat-source candidate path exists |
| L — restart persistence | PASS across separate process invocations/reads; ledger/cursor/candidates persisted; no duplicate in restart test |

Production invocation result:

```json
{"candidateCount":3,"canonicalMemoryMutation":false,"cursorFrom":0,"cursorThrough":6,"idempotentReplayCount":0,"insertedCount":3,"mode":"SHADOW","sourceCount":3,"status":"SUCCEEDED"}
```

The operational trace contained only the approved lane/job/source/count/validation/assessment/cursor/replay/failure/duration/mode/schema/timestamp metadata.

## Post-acceptance proof

The `career_events` approved-projection fingerprint remained exactly `a81c8d2d48dd8e210c11e2e0fb4a271e101e9a89a5665781808033b99d8f5865`, with the same 11 rows, 11 distinct IDs, 4–17 range, and zero triggers.

All six pre-existing database schema fingerprints remained identical to preflight. Protected owners remained byte-identical:

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
| API `app.py` | `743a804aa7e3cbb8edf7ff8e3a698a74d4bc17cce2cfefe24c353b52c214d6e2` |
| Career source owner | `8ec99391d78b2354bf47dc13332b10c092ac689a999da859c48643b5e4a90c21` |

`MEMORY.md`, `USER.md`, and Hermes skills were not accessed or modified. No frontend, Hsin, `/memory/*`, World, Goal, Policy, SOUL, Verifier, connector, task execution, or prompt behavior changed.

## Restart and units

Gateway restart: **NONE**. Daemon reload: **NONE**. Systemd unit/timer additions: **NONE**.

The gateway PID stayed `250061`; final service state was `active/running`, result `success`, exit status unchanged, and `NRestarts=0`.

## Rollback

1. Set `memory_consolidation_enabled: false`; do not invoke the manual worker.
2. For full code rollback, restore the two timestamped backups and remove only `memory_contracts.py`, `learning.py`, `learning_store.py`, `learning_worker.py`, and `tests/test_learning_consolidation.py`.
3. Preserve `cognitive_memory.db` for audit unless deletion is separately authorized.
4. No source/legacy/World/Goal/Policy/SOUL state needs rollback because it was not changed.

No gateway restart or daemon reload is needed for the fast rollback.

## Deferred Slice 15B prerequisites

Canonical L04 item/revision/admission/apply contracts, Consent Authority and `ConsentRef`, qualifying Verifier and `VerificationOutcomeRef` semantics, privacy erasure, retention, rollback/revision policy, approved write proposal/apply flow, and separately reviewed prompt/retrieval consumers remain unresolved and inactive.

**Slice 15B was not begun.**
