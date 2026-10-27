# F9-C: executor finalization review + trusted Privacy rollback anchor. LOCAL result and DESIGN (2026-10-24)

**Status:**
- **Part 1:** implemented and validated locally (executor correction, offline and real-systemd tests).
- **Part 2:** a design for review, with a pure local prototype and its synthetic matrix.

**Not touched:** no governed authority, witness, signer, broker or DR-5 component changed; no DEV or PROD contact; no Groq; no commit or push.

---

## PART 1: executor finalization window

### Finding

The reviewed sequence was: journal FINISHED → marker released → receipt written. **It did not meet the requirement.**
- After the marker was released, a gateway start was possible while the FORGET was still incomplete at the Privacy level: hold ACTIVE, Hermes result not yet recorded, `complete()` not yet run. A kill between release and receipt left exactly that state.
- Even on the normal path, `OnSuccess=` restarted the gateway before the Core API had recorded COMPLETE.

### Correction (smallest local change)

1. **The receipt is written while the marker is held.** The sequence is EPOCH → `before:receipt` → receipt → journal RECEIPT. Nothing releases the gateway there.
2. **The marker is released only on proof that Privacy completed this authorization with Hermes COMPLETE.**
   - New read-only `PrivacyGovernanceStore.owner_completion_recorded(ref, owner)`: the authorization is no longer in flight **and** an immutable completion row exists whose `result_fingerprint == HMAC(secret, {authorizationRefId, resourceOwner, "COMPLETE"})`.
   - The executor reads Privacy read-only, via the hash-pinned modules.
   - A missing, lost, undelivered or unrecorded receipt can never release anything.
3. **Release paths:**
   - **in-run:** a bounded wait (`releaseWaitSeconds`, default 120) covers the normal path;
   - **`--reconcile`:** non-destructive (`hermes-forget-reconcile.service` + `.timer`, every 30 s while the marker exists, `OnBootSec=60`) covers crashes, late completion, `complete()` failures and reboots;
   - **re-queued request:** for a journal that already holds its receipt, a proven completion counts as success, not as an authorization failure, so the restart still happens.
4. **The marker goes only when no journal is unreleased.** The gateway drop-in `ConditionPathExists=!marker` refuses every start before that. The restart unit has the same condition.

**Files:**
- `pkgfiles/bin/hermes_forget_executor.py` → `229db39c…`;
- `pkgfiles/systemd/hermes-forget-reconcile.{service,timer}` (new);
- Core API `privacy_governance.py` (+22 lines, the read-only helper above).

The restore-suppression gate is unchanged.

**Residual window, stated plainly:** between Privacy `begin_forget` and the executor's VALIDATE, the gateway is not blocked by the marker. This is safe for erasure completeness: the whole-store purge runs afterwards and removes anything written meanwhile, and the executor's `Conflicts=` stops the gateway when it starts. If you want no new turns at all once a FORGET is authorized, the runner would have to stop the gateway at `begin_forget`. That's an owner choice (decision P1-a).

### Evidence

**Offline matrix: 38/38.** T7 now kills at 16 points; at every one the marker is present, the hold is ACTIVE and there's no Privacy completion. New `FinalizationWindowTests` (6):

| Case | Result |
|---|---|
| kill **after** the receipt | receipt present but **not success** (no owner result); reconcile keeps it blocked; adapter retry records COMPLETE with **no resubmit**; **the marker stays until reconcile proves completion** |
| kill **before** the receipt | no receipt; blocked; retry resubmits, receipt written, still blocked until reconcile |
| Privacy `complete()` fails after Hermes was recorded | Hermes COMPLETE but FORGET incomplete: blocked; retry completes; reconcile releases |
| reconcile under a wrong secret | never releases |
| kill inside the release step | the next reconcile finishes the release |
| re-queued request after completion | exit 0 (so the restart happens), no erasure repeated |

**Real systemd mirror (all PASS):** P-1, P-2, M1, M3, M5, M6, plus **M7**. In M7 the path unit was stopped so only the timer could heal, and the executor was SIGKILLed right after writing this run's receipt:
- marker **present**;
- `systemctl start hermes-gateway-dev` → **inactive, `ConditionResult=no`**;
- Privacy **COMPLETE** via the adapter;
- the reconcile timer then released and restarted the gateway.

Teardown was exact. One earlier M7 attempt failed because of a harness bug (it matched a previous scenario's receipt, so the kill landed before VALIDATE); it's fixed and recorded.

**Mutations:** the two new finalization mutations (*release without proven Privacy completion*, *reconcile releases unconditionally*) → **2/2 detected**, source restored. The earlier 19 detected + 2 equivalent stand.

**Regressions (Linux):** Core API 256 OK + placeholder, `test_owner_proof` 22 → 278; focused modules 158/158 (py3.11); owner-memory-control **2114 OK ×2**, failure set identical to b9eb32c; gated accepted read 3 OK; executor matrix **38/38**. Windows: anchor prototype 16/16.

---

## PART 2: trusted Privacy rollback anchor

### Threat

- **What can be lost:** a restored, replaced or rolled-back Privacy DB can lose newer restore-suppression rows: whole-file restore, VM snapshot, disk image or a manual copy.
- **Why the gate doesn't catch it:** the gate's integrity check passes, because the old receipts and selectors are genuine, just old.
- **The effect:** `is_held()` is then false for an identity the owner forgot, so restored or re-admitted content would be served. Shown in prototype A3.

### Existing capabilities evaluated (prefer an established boundary)

| Candidate | Fit | Verdict |
|---|---|---|
| **Recovery witness** (K-WIT, `RecoveryWitnessV2`, own uid, state, units and failure domain) | Its stated role is "independently trusted freshness state… never authority". It already detects ledger-only restores of the broker via `ledgerSequence`/`ledgerHead`. `recovery_contracts.py` already defines **`PrivacyBoundaryObservationV1`** (`AT_OR_AFTER_REQUIRED` / `OLDER_THAN_REQUIRED` / `UNAVAILABLE`), and the readiness gate refuses on `PRIVACY_BOUNDARY_STALE`. The slot explicitly awaits "B1b-3f" to define a canonical Privacy source. | **Recommended** |
| Owner freshness (`owner_freshness.py`, owner-held offline Replica A/B binding witness heads) | Off-host: the only layer that survives whole-host or whole-disk rollback. It already binds `RecoveryWitnessV2` heads. | **Recommended as layer 2**, by folding the anchor digest into the witness document it already covers |
| Authority signer | An authority, not freshness; the witness key must be disjoint from authority keys | Rejected |
| Broker | Owner challenge ledger; wrong domain | Rejected |
| Privacy DB itself / a same-file marker | Rolled back together with Privacy | Rejected |
| A new standalone anchor keeper | A new, unrelated trust boundary | Rejected (requirement 2) |

### Architecture

1. **Canonical Privacy suppression state (Core API, unpinned; no schema change).**
   - The manifest `privacy_restore_suppression_manifest` is append-only and immutable (triggers). Its **set** of `(suppression_ref_id, identity_selector)` entries is the suppression state. Selectors are opaque keyed HMACs: no identity, no content.
   - `head = SHA-256(len-prefixed: "LILITH-PRIVACY-SUPPRESSION-SET-V1" ‖ environment ‖ sorted entries)` and `count = |set|`.
   - **The commitment is a set, never rowid order:** SQLite VACUUM may renumber rowids in a TEXT-keyed table. The first prototype draft used rowid order; this review replaced it. Test A8b: VACUUM doesn't matter.
2. **`PrivacyAnchorV1` (a new witness-signed document)** with fields `protocol, schemaVersion, environment, anchorVersion, previousAnchorDigest, suppressionCount, setHead, appended, updatedAt, witnessKeyId, signature`.
   - Domain separator `LILITH-PRIVACY-ANCHOR-V1\0`; Ed25519.
   - It's a chain: version +1 and the previous digest.
   - `appended` carries only the new opaque entries, so the witness can rebuild its anchored set and verify "new set = anchored set ∪ new entries" **without any Privacy access**.
   - The witness refuses duplicates, already-anchored entries, non-extensions and time regression (A5, A8).
3. **Witness binding (layer 2):** the witness's own document gains `privacyAnchorVersion` and `privacyAnchorDigest`, so the owner-freshness replicas, which already bind witness heads, also cover Privacy against whole-host rollback.
4. **Advance.** The Privacy-side client sends `local set − anchored set` on two occasions:
   - **immediately after each `begin_forget`**, from the FORGET runner, before any owner erases;
   - **periodically**, from a reconcile timer, for crash and anchor-write-failure recovery. It's idempotent (A9).

   The witness serializes advances (its existing flock) and writes atomically (pin-before-commit pattern).

   **Concurrent FORGETs** are one set extension (A8).
5. **Authentication.**
   - **Advance requests:** a new witness socket (a third role, e.g. `privacy.sock`, `SocketGroup` = the Core API identity, `SO_PEERCRED` uid check) with a closed operation set (`READ_PRIVACY_ANCHOR`, `ADVANCE_PRIVACY_ANCHOR`). Advancing can only add opaque entries that a fresh Privacy row must then match: it cannot remove suppression or authorize anything.
   - **Anchor verification:** against the pinned `TrustedWitnessAnchorV1` public key; the check needs no secret.
6. **Check (startup and before every memory-serving call).** `RestoreSuppressionGate.check()` gains one probe, before the integrity check:
   - fetch the current signed anchor and anchored set from the witness (local socket, read-only);
   - verify the signature, environment and key id;
   - check the version is not below the process's last-seen version (replay, A5);
   - compare sets:

| Local set L vs anchored set S | Status | Serving |
|---|---|---|
| L == S | `AT_OR_AFTER_REQUIRED` | allowed |
| L ⊋ S | `ANCHOR_BEHIND` (suppression not yet anchored) | **refused** until advanced |
| L ⊊ S | `OLDER_THAN_REQUIRED` (rolled back or restored) | **refused** |
| neither | `DIVERGED` (fork, tamper, duplicate) | **refused** |
| no anchor / witness down / bad signature / older version | `UNAVAILABLE` / `UNVERIFIABLE` / `REPLAYED` | **refused** |

   Startup runs the same check; there's no cached readiness flag (the gate's existing rule).
7. **Legitimate recovery.**
   - **Restoring an older Privacy backup** is refused until a governed **re-suppression** runs: offline, Core API stopped, it re-adds exactly the anchored entries the restore lost, then the check passes (A11). The forgotten identity is suppressed again, and the existing restore-suppression verifier then erases any restored content.
   - A restore holding entries the anchor never saw → `DIVERGED`, owner investigation (A11b).
   - **Crash recovery:** a crash between `begin_forget` and the advance leaves `ANCHOR_BEHIND`, so serving is refused and the reconcile advance heals it (A9, A10).
   - **A rollback to a mid-FORGET snapshot** keeps the identical suppression set (A12): still held, and the runner resumes.
   - **Migration:** genesis anchors the existing set once, as an owner ceremony (A13). Schema migrations must preserve manifest rows; Slice 1's v1→v2 doesn't touch the manifest.

### Required contract and trust-boundary changes (each needs its own approval)

| # | Change | Where | Pinned? / approval |
|---|---|---|---|
| C-1 | `PrivacyAnchorV1` contract (canonical bytes, digest, verify, set-extension rule) | new `owner-memory-control/lilith_owner_memory/privacy_anchor_contracts.py` | must be added to the signer `SHARED_HASHES` / witness file set → **authority-dev release program** (build, attestation, install ladder) |
| C-2 | `PrivacyBoundaryObservationV1` gains a real source (`WITNESS_PRIVACY_ANCHOR`; today only `TEST_SYNTHETIC`), and `CANONICAL_PRIVACY_EPOCH_EXISTS` becomes true | `recovery_contracts.py` (**pinned** `f4a14cff…`) | contract change + re-pin → owner approval |
| C-3 | the witness document gains `privacyAnchorVersion` and `privacyAnchorDigest` (`RecoveryWitnessV3`) with succession rules (never lower) | `recovery_contracts.py`, `witness_readiness.py` (**pinned** `129d4479…`), `owner_freshness.py` | contract + re-pin; owner-freshness record format change |
| C-4 | K-WIT signs a second document type, **or** a separate witness-custodied key | witness `credential.py` (README: K-WIT signs only `RecoveryWitnessV2`) | **custody/purpose decision** (D-2) |
| C-5 | a third witness socket + closed ops; peer = the Core API identity | witness `protocol.py`, `profile.py`, `deploy/*.socket` | witness runtime release; host **observation-baseline** change (new socket unit); **DR-5 EQUAL must still hold** (no deployer, sudoers or polkit change) |
| C-6 | anchor genesis ceremony for DEV_SYNTHETIC | operational | owner ceremony |
| C-7 | Core API: suppression set + advance client + gate anchor probe + runner advance call + re-suppression tool | `privacy_governance.py`, `memory_v2.py`/gate, runner, new offline tool | normal Core API change (unpinned), but **gate semantics change** (new refusal statuses) |

**Not changed by this design:** Privacy Governance stays the sole FORGET authority; the anchor is freshness evidence only. Also unchanged: the restore-suppression gate's existing checks, canonical stores, SOUL.md, cognitive modules, UI, and anything Hermes- or Groq-specific (the anchor sees only opaque Privacy selectors).

### Failure / recovery matrix

The prototype runs **16/16** on the real Core API Privacy store and FORGET flow, with a simulated witness.

| # | Case | Expected / prototype |
|---|---|---|
| A1 | genesis on an empty store | serves |
| A2 | FORGET begun but not anchored; anchored; completed | `ANCHOR_BEHIND` (refused) → serves → still serves (completion adds no suppression row) |
| A3 | **restore of an older Privacy DB** (Privacy alone would serve the forgotten identity) | `OLDER_THAN_REQUIRED` |
| A4 | restore, then a different FORGET (same count) | `DIVERGED`; advance refused |
| A5 | replay of a valid but older signed anchor; forged advance | `REPLAYED`; `ANCHOR_NOT_AN_EXTENSION` |
| A6 | tampered anchor, foreign key, wrong environment | `UNVERIFIABLE` |
| A7 | no anchor; Privacy DB missing | `UNAVAILABLE` |
| A8 / A8b | concurrent FORGETs as one set (order irrelevant); duplicate or forged entries refused; VACUUM renumbering rowids | serves / refused / serves |
| A9 | anchor write failure | nothing half-written; `ANCHOR_BEHIND` until a retry; idempotent |
| A10 | power loss mid-advance (durable file) | state unchanged; retry advances |
| A11 / A11b | legitimate restore + governed re-suppression; a diverged restore | serves again, identity held / `DIVERGED` refusal |
| A12 | rollback to a mid-FORGET snapshot | same suppression set; still held |
| A13 | migration genesis of existing suppressions; second genesis | serves; refused |
| A14 | tampered suppression row (triggers dropped) | `DIVERGED` |

**Needing the real witness (future, with C-1…C-5):**
- **W1:** witness down → refused.
- **W2:** witness restored *with* Privacy (whole host) → **not detected by layer 1**; detected only via owner freshness (C-3). This is the stated limit of every same-host witness.
- **W3:** concurrent advance race (flock).
- **W4:** clock regression.
- **W5:** socket peer spoofing (wrong uid).
- **W6:** advance during witness epoch advance.
- **W7:** DR-5 EQUAL + observation after install.

### Migration and compatibility implications

- **No Privacy schema change.** Existing DBs are anchored by one genesis. Until genesis the gate must decide: `ANCHOR_NOT_PROVISIONED` refuses (strict), or is tolerated only in DEV_SYNTHETIC (D-3).
- **Availability.**
  - **Witness down:** serving is refused while it's unreachable.
  - **Each FORGET:** serving is refused until the advance lands (milliseconds normally; the reconcile timer otherwise).
  - **Grace periods** are an owner decision (D-4) and weaken the guarantee.
- **Restore runbooks change:** a Privacy restore now needs the re-suppression step. A cognitive-only restore is unchanged (the existing gate).
- **Rollback of this feature** (code revert) removes the protection; the witness's anchor history stays as evidence.
- **PROD:** none of this exists there; PROD has its own review.

### Remaining owner decisions

| # | Decision |
|---|---|
| P1-a | Accept the residual window (gateway not blocked between `begin_forget` and the executor's VALIDATE; safe for erasure completeness), or stop the gateway at `begin_forget` |
| D-1 | Adopt the witness as the anchor holder (vs. a new boundary) |
| D-2 | K-WIT signs `PrivacyAnchorV1` too, or a separate witness-custodied key |
| D-3 | Before genesis: refuse serving (strict) or a DEV_SYNTHETIC-only tolerance |
| D-4 | Strict `ANCHOR_BEHIND` refusal vs. a bounded grace window; refuse vs. degrade when the witness is unavailable |
| D-5 | Layer 2 (owner-freshness coverage via C-3) required before real First Memory? (Recommended yes; without it a whole-host rollback is undetectable.) |
| D-6 | The re-suppression tool as the only sanctioned Privacy-restore path, and who may run it |
| D-7 | Sequencing: C-1…C-5 as an authority-dev/witness release program (separate approvals, DR-5 EQUAL gates), before or after the DEV operational upgrade |

**Files:** `anchor/F9C-ROLLBACK-ANCHOR-DESIGN.md` (this document), `anchor/proto/privacy_anchor_proto.py`, `anchor/proto/test_privacy_anchor_proto.py`. Executor changes are under `executor/`.
