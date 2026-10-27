# F9-C Slice 3: governed First Interaction FORGET runner. LOCAL result (2026-10-24)

**Status:** local only, in worktree `lilith-os-f9c1` (branch `feat/f9c-privacy-hermes-owner-v0.1` at `b9eb32c`).
- **Uncommitted:** new files are intent-to-add only.
- **Built on Slice 1 + Slice 2 without changing them:** `hermes_erasure_owner.py` `280d9236…`, `privacy_schema_v2.py` `691260b3…`, and both earlier test modules are byte-identical to the Slice 2 report.
- **Never done in this slice:**
  - privileged executor, systemd unit or privileged operation;
  - HTTP route;
  - real Hermes file, real conversation or memory activation;
  - DEV or PROD contact, Groq call, budget reset, install, commit or push.
- **Cumulative patch (Slices 1–3):** `f9c-slice1-3-cumulative.patch`, sha256 `ec5bcb04b72a68e54c4f80c76038e8e7971f90581ac66c98333bf7e7496820cc` (7 files, +2135/−2).

## Exact Slice 3 changes

| File | sha256 | Change |
|---|---|---|
| `services/core-api/lilith_memory/privacy_forget_runner.py` (new, 176 lines) | `5bdfa8ca…57ea` | the runner (below) |
| `services/core-api/lilith_memory/privacy_governance.py` | `2f8531f0…cf3a` (Slice 2: `8d736641…`) | **+25 lines, two read-only helpers, no write path:** `required_owners(memory_class, subject_namespace)` (the database floor through the existing `_owner_floor`, which fails closed if enforcement triggers are missing) and `in_flight_authorization(identity)` (the reference and nonce of the ACTIVE hold on exactly that identity) |
| `services/core-api/tests/test_privacy_forget_runner.py` (new, 515 lines) | `b3bfbfa0…efd1` | 31 tests |

**Not touched:**
- L04, L18_V1, L18_V2 and every other owner;
- the Hermes adapter;
- canonical contracts (signer/broker-pinned), canonical stores and the actor authority;
- broker, signer and witness;
- `app.py`, the UI and SOUL.md;
- cognitive modules and DR-5 tooling.

## The runner (`FirstInteractionForgetRunner`)

**DEV_SYNTHETIC only.** Any other environment raises `INTERIM_V1_PATH_DEV_SYNTHETIC_ONLY`.

**Construction.** The runner takes a Privacy store plus a map of owner adapters. Each adapter's `OWNER` must equal its key, and the key must be a known owner (otherwise `OWNER_ADAPTER_INVALID`).

**`forget(actor_ref_id, actor_evidence_ref_id, intent_ref_id, confirmation_event_ref)`.** There are no identity, owner, session or authorization parameters. It runs these steps in order; the first four checks run before any evidence is consumed:

1. Build the one canonical First Interaction FORGET action (`first_interaction_forget_action`). The identity is fixed and the purpose is `OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION`.
2. Derive the owners from the governed policy: `L04`, `L18_V2`, then the database floor. The floor must equal exactly `{HERMES_DEV_CONVERSATION}`, otherwise `REQUIRED_OWNER_FLOOR_UNPROVISIONED`, or `…_UNAVAILABLE` if the floor's enforcement triggers are missing.
3. Every owner needs an adapter, otherwise `OWNER_ADAPTER_MISSING`. This is checked before a hold could exist that nobody can finish.
4. Refuse with `FORGET_IN_FLIGHT` if a FORGET is already in flight (use `resume()`).
5. Call `begin_forget`. Privacy resolves and consumes the evidence (issued elsewhere; **the runner never issues evidence**). It then re-checks the floor inside its transaction, and the Slice 1 database triggers enforce it again.
6. Hand over to `resume()`.

**`resume()` (no parameters).**
- It finds the in-flight authorization through Privacy. If there is none, it returns `ALREADY_COMPLETE` (restore suppression exists) or `NOT_STARTED`.
- It re-derives the policy, resolves the authorization (exact nonce, HMAC, ACTIVE hold) and checks the identity.
- The authorization's owner set must equal the policy, otherwise `AUTHORIZATION_OWNER_SET_MISMATCH`: it never runs an authorization it didn't shape.
- Owners run in a fixed order, each validating independently:
  - an owner Privacy already records as COMPLETE is skipped (idempotent retry);
  - **an owner counts as COMPLETE only when Privacy has the record**, never because of the adapter's return value (`OWNER_RESULT_UNVERIFIED`);
  - a FAILED record stops the run (`OWNER_RESULT_TERMINAL`).
- `complete()` is called only when every owner is COMPLETE. Afterwards the runner checks that no hold remains and that suppression matches.
- If completion raises after its commit, the runner reports `ALREADY_COMPLETE` instead of a false INCOMPLETE.

**Results.** Every failure returns `INCOMPLETE_HOLD_ACTIVE`, with the failure code, the failed owner, and the completed and pending owners. Nothing is completed and the hold stays ACTIVE.

## Authorization-flow evidence (`flow_trace.py`; references redacted, no secret or nonce printed)

```
RUN 1: forget(); Hermes executor queues but never executes (mock crash mode)
  required_owners() -> ['HERMES_DEV_CONVERSATION']; in_flight_authorization() -> None
  begin_forget() -> ok; in_flight_authorization() -> (<ref>, <nonce>)
  resolve(L04) ok; owner_result(L04) None -> L04 resolves, records -> owner_result(L04) COMPLETE
  owner_result(L18_V2) None -> L18_V2 resolves, records -> owner_result(L18_V2) COMPLETE
  owner_result(HERMES) None -> Hermes resolves; no receipt -> owner_result(HERMES) None
=> INCOMPLETE_HOLD_ACTIVE failure=EXECUTOR_TIMEOUT completed=(L04, L18_V2) pending=(HERMES)
RUN 2: resume() with a working mock executor
  in_flight -> (<ref>, <nonce>); owner_result(L04)=COMPLETE, (L18_V2)=COMPLETE (skipped, not re-run)
  Hermes resolves -> verified receipt -> re-resolves -> records -> owner_result(HERMES) COMPLETE
  complete() -> PrivacyCompletionReceiptV1; in_flight -> None; suppression_matches -> True
=> COMPLETE completed=(L04, L18_V2, HERMES) receipt=present
RUN 3: resume() replay after completion
  in_flight -> None; suppression_matches -> True
=> ALREADY_COMPLETE
```

## Tests: `test_privacy_forget_runner.py`, 31 tests (30 OK + 1 recorded expected failure)

**Setup:**
- The real L04 and L18_V2 owners run on a First Interaction-migrated cognitive DB holding one admitted First Interaction episode and one codename memory.
- The Slice 2 Hermes owner uses a **mock** executor that resolves the authorization itself and writes durable JSON receipts in a temp directory.
- Privacy is v2 with the floor provisioned.
- Evidence is issued by the existing synthetic test actor authority, the authorized fixture.

| Area | Tests |
|---|---|
| Contract | DEV_SYNTHETIC gate (5 environments); adapter-name validation; no identity, session or owner parameters; source contains no `.issue(`, `resolve_and_consume`, `record_owner_result`, `subprocess`, `systemctl` or `unlink`; the canonical action |
| Happy path | owners run in order L04 → L18_V2 → Hermes; First Interaction rows and plaintext erased, codename kept; exact Hermes request; receipt with 3 owners; no in-flight rows left; suppression permanent |
| Replay | `resume()` after completion: `ALREADY_COMPLETE`, **no owner called, Privacy DB byte-identical**; reused evidence refused; `NOT_STARTED` |
| Authorization failures | evidence for another action, a forged evidence reference, the wrong actor (each: nothing started); **floor unprovisioned → refused before evidence is consumed** (the same evidence then succeeds); v1 database; missing Hermes adapter (evidence unconsumed); **a tampered authorization (raw-file attacker drops the immutability trigger)** → refused, executor untouched; a store with another secret; `forget` while in flight (evidence unconsumed) |
| Omission and downgrade | **a runner that omits Hermes is refused by Privacy** (evidence unconsumed); **frozen b9eb32c Privacy code cannot begin a Hermes-less First Interaction FORGET** (database trigger), and the runner still completes afterwards; **an authorization the runner did not shape (extra owner) is refused with no owner called**; floor retired mid-flight → hold kept until re-provisioned, then completes |
| Partial execution and crash | Hermes missing executor and queued-never-executed (timeout); rejected and incomplete receipts never complete, even on retry with the same durable receipt; **an L18_V2 crash mid-run → resume skips L04 (1 call) and finishes**; **a process kill (KeyboardInterrupt) inside the executor → a fresh store and runner resume and complete**; an adapter claiming COMPLETE without a Privacy record is not trusted; a terminal FAILED record stops the run; completion failure → hold kept, retry completes, Hermes not erased twice; failure after the completion commit → `ALREADY_COMPLETE` |
| Restore suppression | a restored pre-FORGET L04 copy is erased by `RestoreSuppressionVerifier` before serving, codename kept; suppression survives and a second First Interaction FORGET still requires Hermes |
| Read helpers | exact, identity-scoped, and they don't write (DB bytes unchanged) |
| **KNOWN GAP (expected failure)** | see Finding 1 |

**Mutation check: 13/13 detected, sources verified restored** (`mutate_runner.py`):
- environment gate removed;
- floor check skipped;
- policy omits floor owners;
- adapter pre-check skipped;
- in-flight pre-check skipped;
- adapter return trusted;
- owner failure ignored;
- terminal treated as complete;
- **owner-set check skipped** (survived the first run; the added test now detects it);
- completed owners re-run;
- tampered authorization trusted;
- post-commit failure misreported;
- `required_owners` always returns Hermes.

## Finding 1: pre-existing restore-suppression gap (not introduced here; your decision)

`RestoreSuppressionVerifier` (b9eb32c) covers **L04 identities only**. After a restore of a pre-FORGET cognitive DB copy, the verifier erases the First Interaction `memory_item` and reports `ready_to_serve=True`. **The restored L18 First Interaction rows (intent, candidate, source, assessment, proposal; plaintext farewell included) stay.**

Probe (`probe_l18_restore.py`):
```
verifier: ready_to_serve=True, matched=1, suppressed=1
after restore+verify: learning_fi_* = 1 each, memory_item = 0; farewell bytes present: True
```

This isn't fixed, because L18_V2 and the verifier are unchanged by design (A-1 design §2.3). It's recorded as `test_KNOWN_GAP_restore_verifier_does_not_suppress_restored_l18_rows` (`@expectedFailure`), which will start passing, and must then lose its marker, once restore suppression covers L18. Until then, the D-5 "code-only backups" rule, which keeps the cognitive DB out of backups, is what prevents this in practice. The same question applies to the Hermes epoch-based restore suppression in the executor slice.

## Regressions

| Environment | Suite | Slice 2 | Slice 3 |
|---|---|---|---|
| Windows, Py 3.13 | Core API `discover` | 198 OK | **229 OK (1 expected failure)** |
| Windows | durability-probe test / compile | 26 OK (2 skipped) / OK | **26 OK (2 skipped) / OK** |
| Windows | `npm run test:core` (cognitive self-test) | — | **98/98** |
| Linux, Py 3.11 offline FastAPI env | Core API `discover` | 177 run, 1 import error | **208 run: 207 OK (1 expected failure) + the same `test_owner_proof` import placeholder** |
| Linux, Py 3.12 + l1deps | `test_owner_proof` | 22 OK | **22 OK** (Linux total 207 + 22 = **229, matching Windows**) |
| Linux, Py 3.11 and 3.12 | Slice 1 + 2 + 3 modules | 52/52 | **83/83 each (1 expected failure)** |
| Linux, Py 3.12 + l1deps | owner-memory-control ×2 | 2111 OK (16 skipped) ×2 | **2111 OK (16 skipped) ×2; failure set identical to b9eb32c (empty)** (after the flake below) |

**Notes on the regressions:**
- **Cognitive self-test:** the Slice 2 report listed "cognitive regressions 382". I couldn't reconstruct which suite produced that figure, so this report lists only what actually ran: `test:core` 98/98. The worktree has no `node_modules`, so it ran through a **temporary junction** to the main checkout's `node_modules`, removed afterwards. Slice 3 changes no TypeScript.
- **Linux environments:** the same offline environments as Slice 2, with nothing downloaded and no dependency change (`f9c3-linux.sh`).
- **Hung first Linux run (test-harness flake, not a product failure).** The first owner-memory-control run hung for 20 minutes:
  - `test_b1b3e_mb1_kroot_package`'s pty driver does a blocking `os.read` with no deadline. The synthetic ceremony's `root-keygen` sat waiting at a prompt in a throwaway temp home.
  - I killed only those test processes and removed that test's own temp directory.
  - The module then passed alone twice (32 tests, ~15 s each).
  - The rerun caps each owner-memory-control run at 900 s. Adding a read deadline to that pty driver is a separate test-hygiene follow-up; I didn't change it.

## Authority boundary

- **Privacy Governance stays the sole FORGET authority:**
  - the runner holds no secret of its own, never issues evidence, never records owner results, never creates or widens an authorization, and refuses one it didn't shape;
  - the identity and owner set come from the fixed action, the governed policy and the database floor, never from the caller.
- **No session-level input or deletion path anywhere.**
- **No DR-5 effect.**
- **Schema v2, downgrade protection** (the triggers bind old code; re-tested here through the runner) **and the floor are unchanged.**

## Remaining blockers (each needs separate approval)

1. **Privileged executor** (next, not started):
   - root, sandboxed, path-activated;
   - independent re-validation (V1 HMAC, DEV_SYNTHETIC only);
   - H1–H11 phases;
   - durable receipts in the Slice 2 contract;
   - gateway lifecycle and start limits;
   - Hermes epoch-based restore suppression;
   - mirror T1–T25.
2. **A DEV-only operator entry point for the drill.** The runner is a library API. A CLI that loads the DEV Privacy secret and the owners, and gets DEV_SYNTHETIC owner evidence through the governed proof path (not by minting), belongs with the drill (A-8, deferred).
3. **Finding 1:** your decision on L18 restore suppression (fix scope, or rely on D-5 code-only backups).
4. **F8r4→F9 upgrade/rollback scripts;** then the operational steps: DEV Privacy DB v1→v2 plus floor provisioning, Core API deploy, Hermes F9 install.
5. **Before live use:**
   - a signed `PrivacyAuthorizationV2`;
   - a dedicated Hermes service account;
   - the M2 mapping;
   - executor receipt signing.
6. **Permanent obligations:**
   - the downgrade-bypass regression stays;
   - Privacy changes preserve the database floor;
   - source review of the trigger transaction and write-order assumptions before deployment.
7. **Concurrency:** `FORGET_IN_FLIGHT` is a pre-check (TOCTOU). On a race, Privacy's unique hold index refuses the second `begin_forget`, but only after that caller's evidence was consumed. That's acceptable for a single DEV operator; it should be revisited for any multi-caller use.

Files: `privacy_forget_runner.py`, `test_privacy_forget_runner.py` (in the worktree); `f9c-slice1-3-cumulative.patch`, `mutate_runner.py`, `flow_trace.py`, `probe_l18_restore.py`, `f9c3-linux.sh` (here).
