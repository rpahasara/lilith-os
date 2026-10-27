# F9-C Slice 1: Privacy schema v2 + Hermes erasure-owner contract. LOCAL result (2026-10-23)

> **REVISION 2 (owner-requested WSL confirmation + downgrade review).** It supersedes the GO in the original text below.
> - **Downgrade bypass CONFIRMED in the original Slice 1:** NO-GO.
> - **Fixed** by database-level floor enforcement (§R2).
> - **Current patch** `f9c-slice1-privacy-hermes-owner-v2fix.patch` sha256 `225ed79609d20db52fa1d56cc054b920900591489cc1b71b1b356712d6afb72a` (3 files, +856/−2).
>
> ## R1. WSL/Linux results (Ubuntu-24.04, Python 3.12.3, `PYTHONPATH=/root/l1deps`; trees streamed via `git ls-files`)
>
> | Suite | b9eb32c baseline | Slice 1 (pre-fix) | Slice 1 + fix |
> |---|---|---|---|
> | owner-memory-control, run 1 | 2111 OK (16 skipped) | 2111 OK (16 skipped) | **2111 OK (16 skipped)** |
> | owner-memory-control, run 2 (order/state check) | 2111 OK (16 skipped) | 2111 OK (16 skipped) | **2111 OK (16 skipped)** |
> | failure sets (base↔slice, run1↔run2) | — | identical (empty) | **identical (empty)** |
> | Core API `discover` | 82 run, 4 import errors | 102 run, same 4 | **112 run, same 4** |
> | `test_privacy_hermes_owner_v2` alone (Linux) | — | — | **30/30 OK** |
>
> - The 4 Core API errors are identical on all trees: `test_conversation_evidence`, `test_goal_executive`, `test_memory_projection_epistemic` and `test_privacy_forget_capture` fail to import with `ModuleNotFoundError: fastapi`, which isn't present in the WSL dependency set. Those modules pass on Windows (176/176 OK, below).
> - The earlier Windows owner-memory-control differences (61 vs 65) **don't occur on Linux.** There, both trees are fully green and identical across two runs, so the differences were Windows platform/order effects.
>
> ## R2. Downgrade-bypass test and fix
>
> **Scenario (as specified):**
> 1. v1 → v2.
> 2. Provision the DEV_SYNTHETIC First Interaction floor.
> 3. Run the **exact b9eb32c Privacy module** (the frozen record copy, hash-pinned `3c57b9c1…`) on that database.
> 4. Begin a First Interaction FORGET with L04 + L18_V2 only, then complete it.
>
> **Pre-fix outcome: VULNERABLE.** The old code authorized it, both owners recorded COMPLETE, `complete()` released the hold and wrote a receipt. A First Interaction FORGET completed **without Hermes erasure**. Both new tests failed.
>
> **Fix: the smallest governed, fail-closed, database-level enforcement.** The floor isn't weakened, no signer/broker module changes, and no new privilege is added.
> - **Two triggers installed atomically with the floor row** by `provision_hermes_owner_floor`, and dropped atomically with it by `retire_hermes_owner_floor`:
>   - **`privacy_floor_hermes_fi_authorization`**: `BEFORE INSERT ON privacy_restore_suppression_manifest`. It refuses if the authorization being created (largest rowid, in the same `begin_forget` transaction) is First Interaction-scoped and has no `HERMES_DEV_CONVERSATION` owner row.
>   - **`privacy_floor_hermes_fi_completion`**: `BEFORE DELETE ON privacy_hold`. It refuses to release a First Interaction hold unless the receipt being written (largest rowid; receipts are immutable) records Hermes `COMPLETE`.
> - The triggers carry the scope as **literals** and read **only v1 tables**, so they bind every code version. Referencing the floor table would have been denied by the old code's SQLite authorizer, breaking even its codename FORGETs.
> - **Provisioning precondition:** refused while any First Interaction authorization without Hermes is in flight. Complete it first, so legitimate older FORGETs never get stuck.
> - **Provisioning idempotency:** an exact re-provision is a no-op. A partial or altered floor or trigger state is refused.
> - **Runtime tamper detection (new code):** if a floor row exists but either trigger is missing, `begin_forget` fails closed.
>
> **Post-fix results:**
> - The old code is refused at **begin** with `IntegrityError: required erasure owner HERMES_DEV_CONVERSATION is missing` (no authorization or hold written).
> - At **complete**, `IntegrityError: First Interaction FORGET cannot complete without HERMES_DEV_CONVERSATION` (hold kept, no receipt).
> - The old code **still completes codename FORGETs** on v2 + floor.
> - The new code completes First Interaction FORGETs that include Hermes.
> - After governed retirement, the old code may FORGET without Hermes, by design.
>
> **Old authorizations (task 5):**
> - A legitimate pre-floor First Interaction authorization (issued by the old code on v1) survives the upgrade and **blocks provisioning** until it completes normally under the new code; then provisioning succeeds.
> - Even if the precondition were bypassed (floor and triggers inserted manually after such an authorization), **completion is blocked at the database level**: the hold stays, no receipt.
> - A dropped or neutered trigger is detected (runtime fail-closed; the tool refuses).
>
> **Tests:** the Slice 1 module grows from 20 to **30** (+2 downgrade, +3 downgrade compatibility, +5 old-authorization/tamper). **30/30 on Windows and Linux.**
>
> **Mutations: 9/9 detected**, with sources verified restored. They cover the original 4 plus:
> - provisioning without triggers;
> - the authorization trigger neutered;
> - the completion trigger neutered;
> - the runtime tamper check removed;
> - the in-flight precondition removed.
>
> **Regressions (Windows, fixed tree):** Core API **176/176 OK** (146 baseline + 30); durability probe OK (2 skipped); cognitive regressions **382**; compile OK.
>
> ## R3. Fingerprints and boundaries
>
> | Fingerprint | Value |
> |---|---|
> | **v1** (fresh 15B2a provisioning) | `900b57647f078ec9…fdeb40`, **identical on b9eb32c and Slice 1** (v1 DDL untouched) |
> | **v2** | `90dd41e57e3b92c1…bdbd69`, deterministic, **unchanged by floor provisioning** (the triggers are outside the v2 schema object set) |
> | Complete fingerprint with the floor provisioned | `b7256ac033da99e6…fcb3ed` |
>
> **Source hashes:** `privacy_governance.py` `94addcf7…f215`, `privacy_schema_v2.py` `691260b3…34f7`, test `3c849be3…bc28`.
>
> **Authority boundaries:**
> - Privacy Governance stays the sole FORGET authority; the triggers are part of the Privacy database's own schema, enforcing its own rule.
> - No signer/broker/witness pin, governed shared module, canonical store, owner contract, UI, SOUL.md or cognitive module is touched.
> - DR-5 isn't affected: no deployment, no deployer boundary change.
>
> **Rollback semantics after the fix:** a Core API code rollback to b9eb32c on a v2 + floor database keeps codename FORGETs working. First Interaction FORGETs **fail closed** until the new code returns or the floor is retired through governance.
>
> **Review note:** the triggers rely on the existing insert/delete order inside `begin_forget` and `complete()`, which is the same in b9eb32c and Slice 1. Any future Privacy change that reorders those statements must keep this order; the tests would catch a violation.
>
> ## R4. Slice 1 verdict
>
> - **Original Slice 1:** **NO-GO** (downgrade bypass).
> - **Slice 1 + database-level floor enforcement:** **GO for local acceptance**, subject to your approval of the fix design.
> - Nothing is committed or deployed. The next slice (owner adapter) is **not started**.
>
> ---

**Status:** LOCAL ONLY, in git worktree `C:\Users\edufo\Documents\Projects\lilith-os-f9c1` (branch `feat/f9c-privacy-hermes-owner-v0.1` created at `b9eb32c`).
- **No commit, push, deployment, DEV/PROD contact or Groq call.**
- New files are marked intent-to-add (`git add -N`) only, so they appear in the diff.
- Patch: `f9c-slice1-privacy-hermes-owner.patch` (sha256 `7dbc8d035d9a9f02f9cd5a9c034fae34d5e0ad7f940822d7f1b4669248e60599`).

## Exact changes (3 files, +647 / −2)

| File | sha256 | Change |
|---|---|---|
| `services/core-api/lilith_memory/privacy_governance.py` | `fa49383b…0346` (was `3c57b9c1…6d15`) | **+51/−2.** `OWNER_SET` is split into `OWNER_SET_V1` (unchanged 10 owners) + `SCOPED_OWNERS = {HERMES_DEV_CONVERSATION}`; `OWNER_SET` = their union. Constants `PRIVACY_SCHEMA_V1/V2`, `REQUIRED_OWNER_FLOOR_TABLE`. The authorizer may **read** the floor table, never write it. `_owner_floor()` returns schema version + floor for the identity's `(memory_class, subject_namespace)` (v1 → empty; unknown version or missing floor table → `PrivacyError`, fail closed). `_check_owner_scope()`: on v1 only V1 owners are accepted; the floor must be ⊆ owners; a scoped owner is accepted only where the floor names it. `begin_forget` checks scope **before the actor evidence is consumed** and **re-checks inside its write transaction** (`BEGIN IMMEDIATE`), aborting with nothing written if the floor changed. **Unchanged:** authorization/HMAC semantics, `resolve_erasure_authorization`, `record_owner_result`, `complete()`, suppression, receipts, the v1 DDL. |
| `services/core-api/lilith_memory/privacy_schema_v2.py` (new) | `c2103568…8a12` | **Governed offline tool**, never imported by the serving store. `upgrade_privacy_v1_to_v2()`: one `BEGIN EXCLUSIVE` transaction; verifies the v1 ledger, table set and **v1 schema fingerprint**, integrity and foreign keys; content digests of every table; rebuilds `privacy_erasure_authorization_owner` (rename → create with the extended CHECK → copy every row → drop → recreate the immutability trigger); creates `privacy_required_owner_floor` (CHECK owner=`HERMES_DEV_CONVERSATION`, environment=`DEV_SYNTHETIC`) + no-update trigger; **all v1 table digests verified unchanged**; ledger v2 + v2 fingerprint. Idempotent on a matching v2 database; refuses a drifted v1, an unknown version or a tampered v2. `provision_hermes_owner_floor()`: **DEV_SYNTHETIC only**, only the First Interaction scope, v2 required, idempotent. `retire_hermes_owner_floor()`: governed removal; already-issued authorizations keep their owners. Reuses the 15B2a migration helpers (`_connect`, fingerprints, `utc_now`) without changing that module. |
| `services/core-api/tests/test_privacy_hermes_owner_v2.py` (new) | `e8836863…cd1` | **20 synthetic tests** (below). |

**Not touched:**
- `canonical_contracts.py` (signer/broker-pinned `f93d26d8…`), `memory_action_v2.py`, `memory_v2.py` (L04/L18_V2 owners), `canonical_authority.py`, `slice15b2a_migration.py`, `app.py`;
- the frozen Slice 15B2a record copies under `docs/architecture/slice-15b2a/`;
- all signer/broker/witness/authority-dev sources and pins, owner-memory-control, the UI, SOUL.md.

## Tests (Windows, Python 3.13; CI uses 3.12)

| Suite | Baseline `b9eb32c` | With slice 1 |
|---|---|---|
| New `test_privacy_hermes_owner_v2` | — | **20/20 OK** |
| Core API `discover services/core-api/tests` | 146 OK | **166 OK** (146 + 20) |
| `scripts/test_core_api_dev_durability_probe.py` (uses Privacy) | 26 OK (2 skipped) | **26 OK (2 skipped)** |
| `scripts/run_cognitive_regressions.py` (Slices 8–15, incl. the 15B2a record) | 382 | **382** |
| `compileall` Core API | OK | **OK** |
| owner-memory-control `discover` (1,995) | 61 failing (known Windows-only baseline) | 65 failing. The difference is entirely in `test_b1b3e_mb3_registry_package` (5 errors: test root-key deserialisation) and `test_b1b3e_mb1_kroot_package` (1 baseline failure absent). Run on their own, **both modules pass 67/67 on unchanged `b9eb32c` and on slice 1**, so the difference is order/fixture-dependent on Windows and unrelated (neither imports a Privacy module). A Linux/WSL confirmation is still to do. |

**The 20 tests:**
- **Migration:**
  - v2 created and idempotent; the v2 fingerprint is deterministic across databases.
  - **An in-flight v1 authorization survives the upgrade:** owner rows are identical, the HMAC fingerprint still resolves, and it completes.
  - **A crash mid-upgrade leaves v1 intact** (ledger, owner-table DDL, no floor/retired table, authorization still resolves) and a retry succeeds.
  - Drifted v1 / version 3 refused; tampered v2 refused.
- **Scope and floor:**
  - On v1, Hermes is refused **without consuming the actor evidence** (the same evidence is then used successfully).
  - On v2 without a floor, Hermes is refused and existing FORGETs work.
  - Provisioning is DEV_SYNTHETIC-only (PROD/DEV/case variants/empty refused), needs v2, and is idempotent.
  - With the floor: a First Interaction FORGET without Hermes is refused (evidence not consumed), with Hermes it is accepted; a codename FORGET naming Hermes is refused; a codename FORGET without Hermes is accepted.
  - The serving store cannot insert or delete floor rows, and floor rows can't be updated.
  - A floor change during `begin_forget` aborts with no request or hold written.
  - Retiring the floor: new First Interaction FORGETs no longer need Hermes, but an issued authorization naming Hermes still cannot complete without it.
- **Authorization and failure:**
  - Hermes validates independently (wrong nonce, wrong secret/HMAC, owner not listed, unknown owner → `None`).
  - **A Hermes failure keeps the hold ACTIVE, and a retry with the same authorization completes.** The receipt lists all three owners, suppression stays monotonic, and a replay after completion doesn't resolve.
  - Recording FAILED is terminal (a later COMPLETE is refused, the hold stays), which documents why owners must raise instead.
  - A duplicate COMPLETE is refused, so retries must reuse the existing result.
- **Compatibility:**
  - **The exact `b9eb32c` Privacy module** (the frozen record copy, hash-pinned `3c57b9c1…`) runs unchanged on a v2 database, completing existing FORGETs.
  - An authorization naming Hermes issued by the new code **cannot be completed by the rolled-back code**: fail closed, hold kept.
  - The new code on a not-yet-upgraded v1 database keeps existing FORGETs.
  - **The real, unchanged L04 + L18_V2 owners** complete a codename FORGET on an upgraded v2 database with the floor provisioned.

**Mutation check:** 4/4 detected (no in-transaction re-check; no pre-consumption check; floor not enforced; upgrade drops owner rows). Source files restored byte-identical (hash-verified).

## Authority-boundary implications

- **Privacy Governance stays the only FORGET authority.** Hermes is only a peer resource owner, and only where the governed floor requires it. It's not added to, and nothing is changed in, L18_V2 or any existing owner.
- **The required-owner floor is a governed, offline act:** the serving store can read but not write it. It is limited by CHECK to `HERMES_DEV_CONVERSATION` + `DEV_SYNTHETIC`, and by code to the First Interaction scope. **It cannot be provisioned for PROD or live use** (A-4 interim path explicitly confined).
- **Holds:** unchanged semantics. A failure or missing Hermes result keeps the hold ACTIVE; owners never record FAILED.
- **Release and DR-5:** no signer/broker/witness pin, governed shared module or deployer boundary is touched, so DR-5 isn't affected by this slice. When eventually merged, the change classifies as a **Core API deploy** (not a broker/signer release). The **v2 upgrade of the DEV Privacy database is a separate, explicitly authorized operational step**: the tool exists, but nothing runs it.
- **Rollback:** the `b9eb32c` code runs on a v2 database, so a Core API code rollback is safe. In-flight Hermes authorizations then stay held (fail closed) until the v2 code returns. A schema downgrade v2→v1 is not provided (not needed for code rollback).

## Remaining blockers (next slices; none started)

1. **Hermes owner adapter** (Core API side): request spool, bounded wait, receipt verification, idempotent re-read of an existing receipt, raise-don't-record-FAILED.
2. **Governed FORGET runner** + DEV-only DEV_SYNTHETIC entry point (no production runner exists). It is the only caller of `begin_forget`, with the owner policy including the floor.
3. **Root executor + units + sandbox** in the Hermes package (independent check #2; V1 HMAC interim, DEV_SYNTHETIC-only guard), plus the T1–T25 mirror matrix.
4. **F8r4→F9 upgrade/rollback scripts** and the epoch-based restore suppression.
5. **Operational:** DEV Privacy DB v1→v2 upgrade and floor provisioning (separate authorization, after the code is deployed).
6. **Before any live owner conversation:** signed `PrivacyAuthorizationV2` (a Privacy key in custody), a dedicated Hermes service account, and the M2 per-identity mapping for broader or PROD use.
7. **Linux/WSL confirmation** of the owner-memory-control suite with this patch (the Windows run differences were shown unrelated in isolation).
