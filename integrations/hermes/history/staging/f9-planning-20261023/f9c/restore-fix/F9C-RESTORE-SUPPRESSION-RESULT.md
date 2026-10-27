# F9-C L18_V2 restore-suppression correction. LOCAL result (2026-10-24)

**Status:** local only, in worktree `lilith-os-f9c1` (branch `feat/f9c-privacy-hermes-owner-v0.1` at `b9eb32c`).
- **Uncommitted:** new files are intent-to-add only.
- **Never done in this slice:** executor work, DEV or PROD contact, Groq call, deploy, commit or push.
- **Slice 1–3 code unchanged:** `privacy_schema_v2.py` `691260b3…`, `hermes_erasure_owner.py` `280d9236…` and `privacy_forget_runner.py` `5bdfa8ca…` are byte-identical.
- **Narrow integration in the Slice 3 runner tests only:** the two verifier calls now pass the L18 owner, and the expected-failure gap test is now a real, permanent passing test.

**Patches:**
- `f9c-slice1-3-restorefix-cumulative.patch`, sha256 `09c26eeac10d509717514294db30ddcc130a159412cba2a487deb0b9459e6883` (10 files, +2786/−24)
- `restorefix-only-vs-b9eb32c.patch`, sha256 `df0f7a5a47e86f627374020c785bab51659bb69c21a1400cee28be1e8e80667b`

## Root cause

**Reproduced exactly by `test_b9eb32c_verifier_reported_ready_with_l18_plaintext_and_the_fix_does_not`,** which runs the frozen b9eb32c verifier on a restored copy: `ready_to_serve=True` with the First Interaction L18 rows and the plaintext farewell present.

1. **The verifier only knew L04** (`RestoreSuppressionVerifier(privacy, l04_owner)`):
   - it listed identities from L04 `memory_item` only;
   - it erased through L04 only;
   - it judged readiness by re-listing L04 only.
   L18_V2 rows (intent, candidate, source, assessment, proposal, proposal reference) and the First Interaction capture copy were never consulted.
2. **L18_V2 had no restore-suppression path.** Its only erasure needs a live Privacy authorization, and after completion there is none, only the permanent suppression selector.
3. **L04's restore path lacked the F1 fix** that its FORGET path already had:
   - it skipped rejected and precondition-failed admissions, which have no revision lineage;
   - it returned early when no `memory_item` existed, even if such admissions did.
   Left behind, those admissions keep L18 proposal references alive. With L18 cleanup added, they would have blocked it forever through foreign keys. Reproduced by `test_a_rejected_admission_in_the_restored_copy_is_erased_too`; the L04-admission mutation fails it.
4. **Found while testing "missing Privacy data": a wrong or rotated Privacy secret silently disables suppression.** Selectors under another secret match nothing, so any verifier would report "nothing suppressed, ready". There was no check that the store and its secret are the Privacy authority's records.

**What already contained it at runtime:** Privacy's `is_held` includes suppression, so held reads and applies were refused while Privacy was configured. The defects were the at-rest plaintext and a false readiness verdict.

## Implemented changes

Both modules are **unpinned** governed Core API code. `memory_v2.py` and `privacy_governance.py` appear in neither the signer `SHARED_HASHES` nor the broker `SHARED_HASHES`/`SHARED_FILES`; those cover `canonical_contracts.py`, `owner_proof.py`, `__init__.py`, `canonical_authority.py` and `memory_action_v2.py`, all unchanged. **No signer or broker re-pin and no authority-contract change is needed.**

### `services/core-api/lilith_memory/memory_v2.py` (`1ad42fd6…62a0`; +127/−11 vs b9eb32c, all from this fix)

**`L18V2PrivacyErasureOwner`:**
- **`_erase_identity(identity)`** is the existing erasure transaction moved out of `erase_authorized` with identical statements (only `authorization.identity` → `identity`). `erase_authorized` keeps its contract, and the F1 and F4 suites pass unchanged. A restore therefore deletes exactly what an authorized FORGET deletes: identity-scoped, no wider.
- **`erase_restore_suppressed(identity, privacy_store)`**, maintenance-only and mirroring L04:
  - Privacy must prove the opaque selector (`suppression_matches`), else `RESTORE_SUPPRESSION_NOT_AUTHORIZED`;
  - then `_erase_identity`;
  - for First Interaction with a configured capture path, the existing capture erasure runs, re-writing the permanent `fi_capture_privacy_block`;
  - then it raises unless `restore_residue == 0`. Nothing is recorded with Privacy.
- **`list_identities()` (read-only):**
  - every identity in the L18 V2 identity tables (`learning_memory_intent_v2`, `learning_project_codename_candidate_v1`, `learning_proposal_v2`, `learning_fi_intent_v1`, `learning_fi_candidate_v1`, `learning_fi_proposal_v1`);
  - plus First Interaction if any family row (children and proposal references included) or any capture row exists;
  - tables missing from an older restored schema are skipped.
- **`restore_residue(identity)` (read-only):** identity-keyed rows, plus for First Interaction the **whole family** and the capture copy. That's still identity-scoped, because every `learning_fi_*` table CHECKs the single First Interaction identity (`_FI_SCOPE`) and the two child tables reference those rows.

**`L04PrivacyErasureOwner`:**
- **`erase_restore_suppressed`** now also deletes the identity's revision-less admissions (`_identity_admission_refs`, the same helper the FORGET path uses), and no longer returns early when only those exist.
- **`restore_residue(identity)` (read-only):** the item plus identity admissions.

### `services/core-api/lilith_memory/privacy_governance.py` (`d2e64953…1365`; +170/−13 vs b9eb32c for Slices 1–3 plus this fix, Slice 3 alone was +107/−2)

- **`RestoreSuppressionVerifier(privacy_store, l04_owner, l18_owner)`**, where **the L18 owner is required** (`TypeError` or `PrivacyError` otherwise), so an L04-only verifier can no longer be built. `verify_and_apply` does:
  1. **`privacy_store.verify_suppression_integrity()`** first, else `PRIVACY_RECORDS_UNVERIFIED`.
  2. Collect identities from L04 ∪ L18. Only those **this Privacy store suppresses** are matched; the restored database never decides what counts as suppressed.
  3. For each match, erase from L04 then L18_V2 (foreign-key order), each through its governed restore path in its own transaction.
  4. **Ready only if** a re-list finds no suppressed identity **and** every matched identity's L04 and L18 residue is 0. Each of these two independent layers has a test that fails without it.
  5. Any exception gives `RESTORE_VERIFICATION_FAILED`. It fails closed, and a re-run after a crash or partial cleanup is safe.
- **`verify_suppression_integrity()` (read-only):**
  - every completion receipt's HMAC must verify under this secret and still name an existing suppression selector;
  - every in-flight authorization must verify;
  - a wrong secret or tampered or deleted records raise.

## Tests

**`test_privacy_restore_suppression.py`, 24 tests.** Real L04, L18_V2, Privacy (v2 plus floor) and the Slice 3 runner; Hermes uses the mock executor.

| Requirement | Tests |
|---|---|
| 1. Reproduce | frozen b9eb32c verifier: ready with plaintext (reproduced); the fixed verifier: ready only after full suppression |
| 5. Never falsely ready | rows of every First Interaction table are 0, plaintext gone, L04 and L18 residue 0; an L18 owner that skips → `SUPPRESSION_INCOMPLETE`; **a listing defect is caught by residue, and a residue defect by re-listing**; an L04 owner that skips → refused; owner paths refuse an unsuppressed identity |
| 6. Scoped | nothing suppressed → nothing erased; **a codename FORGET + restore erases only the codename** (First Interaction rows and plaintext kept); the First Interaction fix keeps the codename identical in L04 and L18 |
| 7. Repeat and crash | restore → verify → verify → restore → verify (idempotent); **crash between L04 and L18 → refused, L18 content still there → rerun ready**; crash before any cleanup → rerun ready; restore during an in-flight FORGET → verify ready, then the runner completes |
| 7. Corrupted backups | garbage, truncated and missing files → `RESTORE_VERIFICATION_FAILED`; a copy missing a First Interaction immutability trigger → refused on every re-run; a copy with broken foreign-key lineage → refused |
| 7. Missing Privacy data | Privacy DB missing, or an empty DB in its place → `PRIVACY_RECORDS_UNVERIFIED`; **wrong secret** (selectors match nothing) → refused; a tampered receipt or deleted selector → refused; an in-flight authorization under the wrong secret → refused |
| 7. Older schemas | the migration's own pre-First-Interaction backup (`pre-fm02.db`) → ready, codename kept |
| L04 F1 parity | a restored rejected duplicate admission is erased (L04 residue 3 → 0) |
| Read-only | listing and residue counts are exact and leave the DB byte-identical |

**`test_privacy_restore_capture.py`, 4 tests** (FastAPI; real `ConversationCaptureStore`):
- restored cognitive and capture copies are both suppressed, with the permanent block re-written;
- **a restored capture copy alone** (cognitive DB clean) is detected and suppressed, and the check is idempotent;
- a capture copy missing its triggers stays refused;
- an unreadable capture copy fails closed.

**Mutation check: 16/16 detected, sources verified restored** (`mutate_restore.py`):
- verifier ignores L18 identities;
- verifier skips the L18 erase;
- residue check removed*;
- re-list check removed*;
- integrity check skipped;
- receipt HMAC unchecked;
- missing selector tolerated;
- in-flight authorization unchecked;
- verifier builds without L18;
- verifier erases unsuppressed identities;
- L18 restore skips the suppression proof;
- L18 restore skips the capture copy;
- L18 residue omits family rows;
- L18 listing ignores the capture copy;
- L04 restore drops identity admissions;
- L04 residue omits identity admissions.

\* These two survived the first run because each layer covers the other. The two defect tests added afterwards detect each one alone (re-run: 2/2).

## Regressions

| Environment | Suite | Slice 3 | With restore fix |
|---|---|---|---|
| Windows, Py 3.13 | Core API `discover` | 229 OK (1 expected failure) | **257 OK** (the expected failure is now a real pass; +24 +4) |
| Windows | durability-probe test / compile | 26 OK (2 skipped) / OK | **26 OK (2 skipped) / OK** |
| Linux, Py 3.11 offline FastAPI env | Core API `discover` | 208 run (207 + `test_owner_proof` placeholder) | **236 run: 235 OK + the same `test_owner_proof` import placeholder** |
| Linux, Py 3.12 + l1deps | `test_owner_proof` | 22 OK | **22 OK** (Linux total 235 + 22 = **257, matching Windows**) |
| Linux, Py 3.11 and 3.12 | restore fix + Slices 1–3 + F4 + F1 modules | 83/83 (Slices 1–3) | **3.11: 137/137 OK. 3.12: 116 OK + 2 import errors: the two FastAPI capture modules (`pydantic_core` in the offline env is cp311-only; both pass under 3.11)** |
| Linux, Py 3.12 + l1deps | owner-memory-control ×2 | 2111 OK (16 skipped) ×2 | **2111 OK (16 skipped) ×2; failure set identical to b9eb32c (empty)** |

**Notes:**
- **Environments:** the same offline environments as before (`f9c3r-linux.sh`), with nothing downloaded and no dependency change.
- **Slice 2 evidence** is unchanged and included in these runs (`test_hermes_erasure_owner`).

## Compatibility implications

1. **`RestoreSuppressionVerifier` signature (breaking, intended):** it now needs the L18 owner. There are no runtime callers (the ledger calls it "manual, not a startup hook"); only tests were updated. The 15B2a frozen record copy is unaffected.
2. **L04 restore behaviour (deliberately wider, still identity-scoped):** it also erases revision-less admissions of the suppressed identity, matching the F1 FORGET path.
3. **L18_V2 FORGET:** behaviour is unchanged (mechanical extraction). The F1 lineage and F4 capture suites pass unchanged.
4. **Readiness is stricter:** a wrong secret or tampered Privacy records now block readiness (`PRIVACY_RECORDS_UNVERIFIED`), where the old verifier reported ready.
5. **Rollback:** reverting to b9eb32c code reopens this gap, since the old verifier is L04-only (reproduced above). D-5 code-only backups stay as the second defense. Neither is relied on alone.
6. **Wiring:** the L18 owner must be constructed with **the same capture path the relay uses** (`app._capture_db_path()`), or the capture copy isn't covered. The tests assert this behaviour; production wiring is a separate item (blocker 1).

## Remaining blockers (each needs your approval)

1. **The verifier is still not invoked by any restore or startup path** (pre-existing; ledger MEM-12/REC-10). A restored database is "not available" only if the restore runbook or a pre-serve gate runs `verify_and_apply` and refuses to start on `ready_to_serve=False`. Wiring that into the Core API start or restore procedure changes runtime and deploy behaviour, and needs approval.
2. **A restored older Privacy DB can't be detected locally.** If Privacy itself is rolled back, newer suppression selectors are lost and nothing in the cognitive tier can know. That's ADR-0006 / witness territory (a monotonic suppression epoch anchored outside the Privacy DB) and stays open.
3. **Coverage limits (pre-existing, not First Interaction):**
   - legacy L18_V1 codename tables (`learning_proposal`, …) aren't in restore suppression;
   - the Hermes conversation store's own restore suppression (epoch) belongs to the executor slice.
4. **Then:** the privileged Hermes executor (not started), and everything previously listed (operator entry, upgrade and rollback scripts, DEV upgrade and provisioning, V2 authorization, service account, M2, trigger source review).

Files: `F9C-RESTORE-SUPPRESSION-RESULT.md`, both patches, `mutate_restore.py`, `f9c3r-linux.sh` (here).
