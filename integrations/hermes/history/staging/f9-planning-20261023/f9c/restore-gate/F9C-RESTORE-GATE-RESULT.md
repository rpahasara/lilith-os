# F9-C restore-suppression pre-serve gate. LOCAL result (2026-10-24)

**Status:** local only, in worktree `lilith-os-f9c1` (branch `feat/f9c-privacy-hermes-owner-v0.1` at `b9eb32c`).
- **Uncommitted:** new files are intent-to-add only.
- **Never done in this slice:** DEV or PROD contact, Groq call, budget reset, deploy, commit or push.
- **Unchanged:** Slice 1–3 code and the restore-suppression correction. The only change to the restore modules is new code appended to the same two files.
- **The corrected regression stays permanent:** `test_restored_l18_first_interaction_rows_are_suppressed_before_ready` (Slice 3 runner module) and the 24 restore-suppression tests are unchanged and pass.

## What the read path was, and where the gate sits

| Path | Serves | Gate |
|---|---|---|
| `memory_v2.CanonicalMemoryReadFacade.read_exact` | canonical L04 memory (codename, First Interaction) | **gated**: its `privacy_hold_resolver` is the gated resolver; refusal raised before the read and re-checked after it |
| `canonical_store.CanonicalMemoryStoreV2.apply` | canonical admission (writes) | **gated** through the same resolver (raises, writes nothing) |
| `learning_v2.LearningV2Store.assess` | L18 candidate assessment | **gated** through the same resolver |
| owner-memory-control `AcceptedMemoryReadFacadeV2.read_accepted` / `read_historical_v1` (the V2 accepted-memory read First Memory will use) | accepted memory | **gated**: it reads only through the gated L04 facade it is given (no code change in owner-memory-control) |
| `app.py` `/memory/*`, career, tasks, drafts, world, goals, health | legacy Hermes and career stores, no canonical memory | **not gated** (deliberately unaffected; `app.py` never imports `lilith_memory`) |
| `app.py` capture relay (`/os/conversation`, `/os/conversation/evidence` transcript) | First Interaction capture copy | already checks Privacy on every transaction (`_capture_privacy_gate`: hold or suppression selector, fails closed when Privacy is missing); **not the new gate** (blocker 2) |
| `scripts/run_core_api_dev_durability_probe.py` | DEV deploy-time synthetic codename probe | **not changed**: it is the owner-pinned DR-5 deployer probe (blocker 1) |

**There is no deployed DEV runtime that serves canonical memory today.** The facade is the single read boundary; the probe and owner-memory-control assemble it. The gate is therefore enforced where the boundary is assembled: `memory_v2.restore_gated_hold_resolver(...)` is the one resolver every memory-serving component must receive.

## Exact changes (Core API only; both modules unpinned)

### `services/core-api/lilith_memory/privacy_governance.py` (`e65a6cdf…5848`; +238/−13 vs b9eb32c)

Appended after the restore-suppression code:
- **`RestoreSuppressionNotReady(PermissionError)`** with `.code`: an explicit refusal, never a miss.
- **`RestoreSuppressionGate(privacy_store, l04_owner, l18_owner)`**, read-only. It keeps only the owners' `list_identities` and `restore_residue` (both open SQLite `mode=ro`) and has no erasure operation. `check()`, evaluated afresh on every call:
  1. `verify_suppression_integrity()` (receipt and in-flight HMACs and selectors under this secret), else `PRIVACY_RECORDS_UNVERIFIED`;
  2. identities from L04 ∪ L18 (L18 includes the capture copy) that Privacy suppresses;
  3. any such identity with remaining content and **no ACTIVE hold** gives `SUPPRESSED_CONTENT_PRESENT`. Content under an in-flight FORGET is expected, and per-identity `is_held` already refuses it;
  4. any error gives `RESTORE_CHECK_FAILED`.
  `require_ready()` raises `RestoreSuppressionNotReady(code)`.
- **`GatedPrivacyHoldResolver(privacy_store, gate)`** (requires a real gate): `is_held` calls `require_ready()` and then answers from Privacy exactly as before; `require_ready()` is exposed for the facade's post-read check. A not-ready gate raises. It is never reported as "held", which would have written REJECTED admissions.

### `services/core-api/lilith_memory/memory_v2.py` (`a9b72714…fc4b`; +150/−11 vs b9eb32c, +23 here)

- **`CanonicalMemoryReadFacade.read_exact`:** after `get_active`, calls the resolver's `require_ready` if it has one. A database replaced between the hold check and the read is refused. With the plain Privacy store (no `require_ready`) behaviour is unchanged.
- **`restore_gated_hold_resolver(privacy_store, cognitive_path, *, capture_evidence_path=None)`:** builds the gate over that database's L04 and L18 V2 owners (and the capture copy at the relay's path) and returns the gated resolver. The serving runtime gives this one object to the facade, canonical store and learning store.

## Readiness behaviour

- **No readiness flag exists.** Every gated call re-reads Privacy and the cognitive and capture files, so a stale "ready" can't outlive a change:
  - **restore or database replacement:** the next call sees the restored rows (new connection) and refuses with `SUPPRESSED_CONTENT_PRESENT`, until the maintenance step has erased them. Tested with the *same* facade before and after the replacement;
  - **replacement during a read:** the post-read check refuses (`test_a_replacement_between_the_check_and_the_read_is_not_served`);
  - **new suppression:** `begin_forget` writes the selector with an ACTIVE hold. The identity is then refused per identity (held) while other memories keep serving. Once the hold is gone, any content of that identity is, by definition, resurrected and blocks serving;
  - **Privacy missing, replaced, wrong secret or tampered:** `PRIVACY_RECORDS_UNVERIFIED` on the next call. Recovery is automatic once the correct store is back.
- **Scope of a refusal (availability):** a not-ready gate refuses all canonical memory serving (reads, admissions, assessments), because which identities are safe can't be known. Every non-memory Core API route is unaffected, and so is the capture relay with its own Privacy check.
- **Separation:**
  - request paths only ever hold the gated resolver, which can list and count, read-only;
  - cleanup is only `RestoreSuppressionVerifier.verify_and_apply`, the maintenance step, identity-scoped and requiring a Privacy suppression proof per identity. Tests patch both erasure methods during gated reads and assert they are never called and that both DB files stay byte-identical;
  - nothing in the gate, the resolver or the facade can delete.
- **Concurrency, crash and retry:** the check holds no locks and no state. Cleanup is per-owner transactions; an interrupted cleanup leaves the gate not ready, and a re-run finishes (tested). The FORGET runner and restore cleanup are unchanged and idempotent.

**Cost:** each gated call opens about 6–10 short read-only connections (integrity, two listings, per-identity selector and hold, residue). No clean per-call figure was measured: both hosts were heavily I/O-loaded during this work (Core API suite 1006 s vs 57 s normally). On the Windows host, which was heavily loaded during the run, a plain Privacy `is_held` took ~22 ms and the gate ~188 ms. Acceptable for DEV. If needed later, a change-token cache keyed on the files' identity and size/mtime/ctime plus WAL could skip unchanged re-checks; it isn't implemented, because it would weaken requirement 4.

## Tests

**`services/core-api/tests/test_privacy_restore_gate.py`, 17 tests.** The real L04 + L18 V2 + Privacy (v2 plus floor) + Slice 3 runner; the facade, canonical store and learning store are assembled with the gated resolver as a serving runtime must be.

| Requirement 8 / 9 case | Test |
|---|---|
| clean database startup | migrated empty DB: ready; reads miss; a codename written is then served |
| normal serving | First Interaction and codename served before any FORGET |
| completed FORGET | First Interaction refused (held by suppression), codename served, no maintenance needed |
| in-flight FORGET | content still under the ACTIVE hold (FORGET stalled before any owner erased): **gate ready**, First Interaction held, codename served |
| restored suppressed data | **every** canonical read refused `SUPPRESSED_CONTENT_PRESENT`; maintenance → First Interaction suppressed, codename served |
| blocked write | the gated learning assessment raises; **no admission or assessment row written** |
| replacement after verification | same facade: verified and serving → file replaced → refused → maintenance → serving |
| replacement during a read | post-read check refuses |
| missing Privacy | refused `PRIVACY_RECORDS_UNVERIFIED`; recovers when restored |
| wrong secret | Privacy alone would serve First Interaction (`is_held` False); the gate refuses |
| tampered suppression | the suppression manifest rows were deleted (triggers dropped): Privacy alone would serve First Interaction; the gate refuses |
| interrupted cleanup | crash between L04 and L18: still refused; re-run → serving |
| unavailable cognitive DB | `RESTORE_CHECK_FAILED` |
| separation | gated reads never call either erasure method, and both DBs stay byte-identical; serving objects expose no erase, apply or forget; the gate keeps only `list_identities` and `restore_residue`; a resolver without a gate and a gate without L18 are refused |

**Also added:**
- **`test_privacy_restore_capture.py`** (FastAPI), +1: a restored capture copy alone blocks gated serving until maintenance.
- **`services/owner-memory-control/tests/test_restore_gate_accepted_read.py`, 3 tests:** the real V2 admission path (broker-signed synthetic evidence, adapter admission), read through `AcceptedMemoryReadFacadeV2` over the gated facade:
  - ACCEPTED when ready;
  - **refused when Privacy is missing**;
  - **a restored forgotten memory is refused, then after maintenance reads `NOT_READABLE` with its bytes gone**.

**Mutation check: 10/10 detected, sources verified restored** (`mutate_gate.py`, run on a separate WSL copy so the worktree was never mutated):
- gate skips Privacy integrity;
- gate ignores the L18 probe;
- gate ignores residue;
- **gate drops the in-flight exemption** (survived the first run; detected after adding the stalled-FORGET test);
- check error treated as ready;
- `require_ready` never refuses;
- resolver `is_held` skips the gate;
- resolver accepts any gate;
- facade post-read check removed;
- helper drops the capture copy.

## Regressions (Linux; Windows focused)

| Environment | Suite | Restore fix | Gate |
|---|---|---|---|
| Linux, Py 3.11 offline FastAPI env | Core API `discover` | 236 run (235 + `test_owner_proof` placeholder) | **254 run: 253 OK + the same `test_owner_proof` import placeholder** (235 + 17 gate + 1 capture) |
| Linux, Py 3.12 + l1deps | `test_owner_proof` | 22 OK | **22 OK** (Linux Core API total **275**) |
| Linux, Py 3.11 / 3.12 | gate + restore + Slices 1–3 + F4 + F1 modules | 137 / 116 + 2 import placeholders | **3.11: 155/155 OK. 3.12: 133 OK + 2 import placeholders (the two FastAPI capture modules, cp311-only `pydantic_core`; both pass under 3.11)** |
| Linux, Py 3.12 + l1deps | owner-memory-control ×2 (includes the 3 new tests) | 2111 ×2 | **2114 OK (16 skipped) ×2 (2111 + the 3 new tests); failure set identical to b9eb32c (empty)**. Runs took 4567 s and 3421 s on a heavily I/O-loaded host, under systemd with WSL keep-alive sessions (WSL stops an idle distro, which had killed earlier attempts) |
| Windows | gate (17), capture (5), owner-memory-control gated read (3) | — | all OK (Windows host heavily loaded; the full Windows run was skipped in favour of Linux, as requested) |

## Compatibility risks

1. **Opt-in by wiring.** The facade and stores take whatever resolver they are given. A runtime assembled with the bare Privacy store is ungated (unchanged behaviour, needed for owner-memory-control's existing tests). The rule is that every serving assembly uses `restore_gated_hold_resolver`. Making that structural (refusing an ungated facade in a serving profile) would change owner-memory-control test harnesses; flagged for your decision.
2. **A refusal is now an exception** (`RestoreSuppressionNotReady`, a `PermissionError`), not `None`. Callers that treat `PermissionError` as "unknown tuple" must surface it as "not ready". `AcceptedMemoryReadFacadeV2` propagates it (tested).
3. **Global, not per-identity, refusal on resurrected content.** Deliberate: the restored state is untrusted until maintenance. It does block unrelated canonical memories for that window.
4. **Per-call cost** (above).
5. **Rollback to b9eb32c** removes the gate and the L18 restore suppression together. D-5 code-only backups remain the second defense.

## Remaining blockers (each needs your approval)

1. **The DR-5 deployer probe builds its own facade with the bare Privacy store.** `run_core_api_dev_durability_probe.py` is installed root-owned by you from a reviewed commit and is part of the DR-5 deployer boundary, so I didn't change it. It only reads its synthetic codename identity at deploy time. Gating it means a reviewed probe change plus owner re-installation (a DR-5 boundary update).
2. **The capture relay can't use the gate.**
   - **Constraint:** `app.py` must not import `lilith_memory`, and it holds no Privacy secret.
   - **What it does check:** Privacy (hold or selector) on every transaction, and it fails closed when Privacy is missing.
   - **What it can't detect:** a tampered or forged Privacy manifest, or a wrong-secret configuration.
   - **Options:**
     - (a) give the relay a gate-backed readiness check through a small verified interface;
     - (b) keep capture disabled outside synthetic drills (current default) until owner authentication lands.
3. **A trusted Privacy rollback anchor is required before live First Memory.** The gate can't detect rollback of Privacy itself. A restored older Privacy DB verifies perfectly (its receipts and selectors are genuine, just old), so newer suppressions vanish silently. That needs a monotonic record held outside the Privacy DB, for example:
   - a signed suppression high-water mark (count of selectors plus the latest receipt digest) countersigned by the recovery witness / authority signer, in the B1b-3 ADR-0006 recovery-epoch pattern;
   - or an append-only suppression ledger in the witness.
   The gate would then require `Privacy.selector_count >= anchor.count` and the anchored receipt present. Designing and wiring that anchor touches the authority/witness boundary and needs separate approval. **This gate does not solve Privacy rollback.**
4. **The maintenance step has no operator entry point yet** (`verify_and_apply` is a library call). The restore runbook must run it, with the Core API's memory serving refused until it reports ready. That's an operational procedure for approval with the DEV drill.
5. **Then:** the privileged Hermes executor (not started) and the earlier list (V2 authorization, service account, M2, trigger source review, upgrade scripts, DEV provisioning).

Files: this document, `f9c-gate-cumulative.patch`, `mutate_gate.py`, `f9c3g-linux.sh`.
