# F9-C Slice 2: HERMES_DEV_CONVERSATION erasure-owner adapter (Core API side). LOCAL result (2026-10-24)

**Status:** LOCAL ONLY, in worktree `lilith-os-f9c1` (branch `feat/f9c-privacy-hermes-owner-v0.1` at `b9eb32c`).
- **Uncommitted:** new files are intent-to-add only.
- **No:** executor, systemd unit, privileged operation, FORGET runner, real Hermes file, DEV/PROD contact, Groq call or budget reset.
- **Cumulative patch (Slice 1 + fix + Slice 2):** `f9c-slice1-2-cumulative.patch`, sha256 `cca8cf34257504888a219818a31fc4d055fc0160b9a33c2cecd0f8ee732c15cb` (5 files, +1419/−2).

## Exact Slice 2 changes

| File | sha256 | Change |
|---|---|---|
| `services/core-api/lilith_memory/hermes_erasure_owner.py` (new, 186 lines) | `280d9236…0856` | contracts + owner adapter (below) |
| `services/core-api/lilith_memory/privacy_governance.py` | `8d736641…6f59` (Slice 1: `94addcf7…`) | **+19 lines:** read-only `owner_result(authorization_ref_id, execution_nonce, owner)`. It returns the recorded status only for a live authorization with the **exact** nonce, else `None`; it never writes. It exists so an owner retry can be idempotent instead of colliding with its own earlier result. Nothing else changed in Privacy; Slice 1 and its floor enforcement are untouched (`privacy_schema_v2.py` `691260b3…` unchanged). |
| `services/core-api/tests/test_hermes_erasure_owner.py` (new) | `ac35103f…f1ef8` | 22 tests (§3) |

**Not touched:** L04, L18_V2 and every other owner; canonical contracts (signer/broker-pinned); canonical stores; `app.py`; the 15B2a record copies; SOUL.md; cognitive modules; UI; signer/broker/witness/authority-dev; DR-5 tooling.

## Contracts

### Authorization (consumed, never created)

The adapter calls the existing `PrivacyGovernanceStore.resolve_erasure_authorization(ref, owner="HERMES_DEV_CONVERSATION", execution_nonce=nonce)`. That checks the owner is listed, the exact nonce, the **HMAC integrity**, and that the **hold is ACTIVE**. The adapter also requires the identity to equal the First Interaction identity (**`AUTHORIZATION_OUT_OF_SCOPE`** otherwise). It re-resolves after the receipt and before recording, so a hold released or an authorization gone mid-flight is refused.

### Request to the executor: `erasure_request()`, exact fields

```json
{"v": 1, "owner": "HERMES_DEV_CONVERSATION", "authorizationRefId": "<ref>", "executionNonce": "<nonce>"}
```

- No session ids, paths, scope or any other caller-chosen field. `erase_authorized` takes only `(authorization_ref_id, execution_nonce)`; this is tested.
- The executor must validate the authorization independently and derive scope from it (the next slice).

### Executor interface (`HermesErasureExecutor` Protocol)

- `submit(request)` **queues only** and must be idempotent per reference.
- `read_receipt(authorization_ref_id) -> Optional[Mapping]` returns the executor's **durable** receipt.
- A missing executor or any exception gives `EXECUTOR_UNAVAILABLE`. No receipt before the bounded deadline (default 300 s, max 3600 s) gives `EXECUTOR_TIMEOUT`. **Queued is never COMPLETE.**

### Receipt (`verify_receipt`): exact field set; anything missing or extra is `RECEIPT_MALFORMED`

| Field | Requirement |
|---|---|
| `v`, `owner` | `1`, `HERMES_DEV_CONVERSATION` |
| `authorizationRefId`, `executionNonce`, `authorizationFingerprint`, `holdId` | must equal the resolved authorization; otherwise `RECEIPT_AUTHORIZATION_MISMATCH` |
| `identityScope` `{memoryClass, subjectNamespace, subjectKey}`, `scope` | the authorization identity, and `WHOLE_STORE_SINGLE_PRINCIPAL`; otherwise `RECEIPT_SCOPE_MISMATCH` |
| `status` | `COMPLETE` (`REJECTED` → `EXECUTOR_REJECTED`, `FAILED` → `EXECUTOR_FAILED`, anything else → `RECEIPT_INCOMPLETE`) |
| `phases` | exactly `VALIDATE, STOP, SQLITE, FILES, JOURNAL, BACKUPS, EPOCH`, all `COMPLETE` |
| `checks` | exactly `single_principal, sessions_zero, messages_zero, fts_zero, wal_truncated, integrity_ok, files_purged, journal_vacuumed, backups_conversation_free, protected_files_unchanged`, all `true` (boolean) |
| `erasureEpoch` | int ≥ 1 (not bool) |
| `claim`, `providerErasure` | exactly `LOGICAL_ERASURE_VERIFIED` and `ATTESTED_ZDR_NOT_VERIFIED`; any physical or provider claim is `RECEIPT_OVERCLAIM` |
| `completedAt` | non-empty string |
| `receiptDigest` | sha256 over the canonical JSON of all other fields (sorted keys); otherwise `RECEIPT_DIGEST_MISMATCH` |

**Recorded Privacy owner result:** `{"owner","status":"COMPLETE","receiptDigest","erasureEpoch"}`. It is content-free and only written after a verified receipt plus re-resolution.

### Failure semantics (all keep Privacy incomplete)

- Every non-COMPLETE path **raises and records nothing**: no owner row, hold ACTIVE, `complete()` refuses, same authorization retryable.
- A pre-existing `FAILED` owner row means `OWNER_RESULT_TERMINAL` (never overwritten).
- **Idempotent retry:**
  - after a recorded COMPLETE, it returns `idempotent: true` with no resubmit;
  - after an interrupted attempt, it reuses the durable receipt with no resubmit.

### Environment gate (A-4)

Construction outside `DEV_SYNTHETIC` raises `INTERIM_V1_PATH_DEV_SYNTHETIC_ONLY`. The V1 HMAC path is disabled everywhere else; a signed `PrivacyAuthorizationV2` stays mandatory before live use.

## Tests (synthetic, durable file-backed executor double; no privileged operation)

**22 tests, all OK, including a 23-variant receipt subtest. They cover:**
- the environment gate (5 values);
- an exact request with no session parameter;
- the happy path with Privacy completing over L04 + L18_V2 + Hermes;
- **missing executor, unavailable submit, unreadable receipt store;**
- **queued-but-never-executed → `EXECUTOR_TIMEOUT`;**
- **rejected and failed receipts;**
- **forged reference and wrong-secret HMAC, refused before the executor is touched;**
- **wrong nonce, refused before the executor;**
- an out-of-scope authorization;
- **23 forged, incomplete or overclaiming receipt variants:**
  - a phase FAILED or missing; a check false or a string;
  - epoch 0 or bool; status QUEUED;
  - a missing field; an extra `sessionIds`; wrong version or owner;
  - wrong nonce, reference, fingerprint or hold;
  - wrong subject key or scope;
  - a physical or provider overclaim; a bad digest;
- digest-after-edit;
- **interrupted execution, then a retry reusing the late durable receipt** (no resubmit);
- **idempotent retry after a recorded COMPLETE** (one row, one submission);
- **replay after Privacy completion refused;**
- **a foreign authorization's receipt refused;**
- **the hold released between receipt and record refused;**
- terminal FAILED never overwritten;
- the read helper's exact-nonce rule and that it can't write;
- the floor triggers still present after the adapter path.

**Mutation check: 12/12 detected:**
- queued counted as complete;
- receipt unverified;
- no re-resolution;
- no scope check;
- digest not checked;
- fingerprint/hold not bound;
- phases unchecked;
- overclaim allowed;
- environment gate removed;
- terminal FAILED ignored;
- helper ignoring the nonce;
- session ids added to the request.

Sources were verified restored.

## Regressions

| Environment | Suite | b9eb32c | Slice 1 + fix + Slice 2 |
|---|---|---|---|
| Windows, Py 3.13 | Core API | 146 OK | **198 OK** (+30 Slice 1, +22 Slice 2) |
| Windows | durability-probe test / cognitive regressions / compile | 26 OK (2 skipped) / 382 / OK | **same** |
| **Linux** (WSL Ubuntu 24.04), Py 3.12 + l1deps | owner-memory-control, run 1 and run 2 | 2111 OK (16 skipped) | **2111 OK (16 skipped) ×2; failure set identical (empty)** |
| **Linux**, Py 3.11 offline FastAPI env | Core API `discover` | 125 run, 1 import error | **177 run, same 1 import error** (`test_owner_proof`, see below) |
| **Linux**, Py 3.12 + l1deps | `test_owner_proof` | 22 OK | **22 OK** |
| **Linux**, Py 3.11 and 3.12 | Slice 1 + 2 modules | — | **52/52** each |

**FastAPI on Linux, resolved without changing project dependencies and without downloading anything.** An offline Linux test environment `/root/coreapi-deps`:
- **Pinned:** `fastapi 0.116.1` + `starlette 0.47.3`, the exact Core API pin set, copied as pure Python from the existing Windows environment.
- **From the local F8 Linux wheelhouse:** `pydantic 2.13.4` / `pydantic-core 2.46.4` (cp311) and `anyio`, `idna`, `sniffio`, `typing_extensions`, `typing_inspection`, `annotated_types`.
- **Interpreter:** the local CPython 3.11.16.
- **Result:** the 4 previously un-importable modules now run and pass on Linux (22 + 22 + 7 + 17).
- **Remaining difference:** `test_owner_proof` can't import under that 3.11 environment only because the local `cryptography` Rust binding was built for 3.12, so it runs under 3.12 instead (22 OK). **Linux coverage = all Core API modules; total 176 + 22 = 198, matching Windows.**
- **Differences from CI** (Python 3.12, freshly resolved `pydantic`): Python 3.11 for the 4 FastAPI modules and `pydantic 2.13.4` vs `2.13.5`.

Scripts: `f9c2-linux.sh`, `f9c2-ownerproof.sh` (copied here).

## Authority boundary

- **Privacy Governance stays the sole FORGET authority:** the adapter consumes an authorization; it never constructs, widens or replays one, and holds no secret beyond what Privacy itself uses.
- **No session-level deletion input exists anywhere** in the Core API path.
- **No DR-5 effect** (no deployment, no deployer or privilege change).
- **Schema v2, downgrade protection and the First Interaction floor are unchanged** (the Slice 1 tests all pass, and the triggers are present after the adapter path).

## Remaining blockers (not started; each needs separate approval)

1. **Privileged executor:**
   - root, sandboxed, path-activated;
   - independent re-validation (V1 HMAC, DEV_SYNTHETIC only);
   - the H1–H11 phases with durable receipts in exactly this contract;
   - gateway lifecycle, start-rate limit;
   - plus the mirror T1–T25 matrix.
2. **Governed FORGET runner** + DEV-only DEV_SYNTHETIC entry. It is the only caller of `begin_forget`, applies the owner policy including the floor, and is where this adapter will be wired.
3. **F8r4→F9 upgrade/rollback scripts** + epoch-based restore suppression.
4. **Operational, separately authorized:** DEV Privacy DB v1→v2 + floor provisioning; Core API deploy; Hermes F9 install.
5. **Before live use:**
   - a signed `PrivacyAuthorizationV2` (Privacy key custody);
   - a dedicated Hermes service account;
   - the M2 per-identity mapping for broader or PROD use;
   - receipt-integrity hardening (Phase 2 executor signature; today integrity rests on root-only receipt location plus the digest).
6. **Permanent obligations (owner instruction):**
   - the downgrade-bypass regression stays;
   - any Privacy schema or authorization-flow change must preserve the database-level floor;
   - the triggers' transaction and write-order assumptions need source-level review before deployment.
