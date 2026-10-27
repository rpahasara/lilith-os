# F9-C Privacy rollback anchor: final decision review (C-1..C-5, D-1..D-7, P1-a)

**Status:** review only (2026-10-24).
- **Approved so far:** the owner approved the recovery witness as the anchor holder (DESIGN DIRECTION ONLY). The owner also accepted the executor finalization correction as locally validated (M7 included).
- **Not changed:** no governed component (witness, signer, broker, authority, DR-5), and no DEV or PROD contact, provider call, commit or push.
- **Basis:** a read-only source review of the f9c1 worktree at b9eb32c and `F9C-ROLLBACK-ANCHOR-DESIGN.md`.

## 0. Source facts that change the earlier design

| # | Fact (read-only check) | Consequence |
|---|---|---|
| F-1 | The witness README and `credential.py` say K-WIT signs **only** `RecoveryWitnessV2`, and that there is no Privacy signing path. | If K-WIT signs anchors, that changes K-WIT's accepted purpose (M-B2 custody). → a dedicated key (D-2). |
| F-2 | The witness has two sockets: `owner.sock` (root 0600, peer uid 0) and `signer.sock` (authority uid). | An append-only advance can run over the **existing root socket** through a root helper. No third socket, and no new peer principal (D-8). |
| F-3 | `owner_freshness.py`: "proves nothing about time and **prevents no rollback**". Its records are owner-side and unsigned, and no host gate consumes them. | Layer 2 as designed does **not** meet requirement 4. It needs a host-side check against owner-held evidence (C-8). |
| F-4 | Pinned in `SHARED_HASHES`: `recovery_contracts.py` f4a14cff, `witness_readiness.py` 129d4479, `pr1_bootstrap.py` 9a09a472, plus Core API `owner_proof.py` / `canonical_contracts.py`. The witness runtime modules and units are in `witness_release_file_set.py`; `lilith_authority_host/paths.py` is a pinned host module. | Every C-item below that touches these goes through the authority-dev release program. |
| F-5 | `owner_freshness.py` is **not** in `SHARED_HASHES`. Its record format is still an accepted PR-3 owner-ceremony format. | Changing it is a governance change, not a pin change. |

## 1. Contract changes: C-1..C-5 (plus the C-8/C-9 additions this review found)

| # | Change | Recommended form | Pinned / approval |
|---|---|---|---|
| **C-1** | `PrivacyAnchorV1` contract | New pure module `privacy_anchor_contracts.py`, with:<br>• set commitment (never rowid)<br>• chain (version+1, previous digest)<br>• `appended` extension rule<br>• domain `LILITH-PRIVACY-ANCHOR-V1\0`<br>• verify-only API for the Core API<br>• **its own key-id prefix**, `test-only.privacy-anchor.dev-synthetic.*` | New `SHARED_HASHES` entry + witness file set → **release program** |
| **C-2** | `PrivacyBoundaryObservationV1` gets a real source | Source `WITNESS_PRIVACY_ANCHOR`; `CANONICAL_PRIVACY_EPOCH_EXISTS = True`. Add the statuses `DIVERGED`, `ANCHOR_BEHIND`, `UNVERIFIABLE`, `REPLAYED`, each mapping to refusal (today only AT_OR_AFTER / OLDER / UNAVAILABLE / NOT_MODELLED exist). | `recovery_contracts.py` **re-pin** |
| **C-3** | Witness document binds the anchor | `RecoveryWitnessV3` adds `privacyAnchorVersion` and `privacyAnchorDigest` (never lower). **Refresh is lazy:** on each ledger advance and on demand before an owner freshness ceremony, **not** on every Privacy advance (this avoids racing the signer's `previousWitnessDigest` chain). The signer's `witness_client.py` must accept V3. | `recovery_contracts.py` + `witness_readiness.py` **re-pin**; authority-dev runtime change; owner-freshness format change (F-5) |
| **C-4** | Anchor signing key | **Dedicated key K-PAN.** It is witness-custodied (same uid, a **separate** systemd credential and `LoadCredentialEncrypted=` line), with its own signer class that signs only `PrivacyAnchorV1` bodies, its own key id and its own domain. K-WIT stays V2/V3-witness-only. The public key is pinned for the Core API gate. | `pr1_bootstrap.py` **re-pin** (new profile); `credential.py`; service unit; **keygen + custody ceremony** |
| **C-5** | Advance / read transport | **No third socket.**<br>• **Advance:** new op `ADVANCE_PRIVACY_ANCHOR` on the existing **root** owner socket, called by a root path-activated oneshot. It follows the executor pattern: hash-pinned modules checked before import, Privacy opened read-only/immutable, and it sends `local − anchored` only.<br>• **Read:** the witness publishes the signed anchor + anchored set to a witness-owned read-only file. The gate verifies the signature, so no socket and no secret are needed.<br>• `READ_PRIVACY_ANCHOR` is on the owner socket for root tooling. | `protocol.py`, `core.py`, `writer.py`, `storage.py`, `server.py`, tmpfiles, `paths.py` (**pinned host module**) → witness runtime release; host observation baseline (+2 root units); **DR-5 EQUAL must hold** (no deployer, sudoers or polkit change) |
| C-6 | Genesis ceremony | One owner ceremony per environment. The witness refuses a second genesis. | operational |
| C-7 | Core API (unpinned) | Suppression-set head, gate anchor probe, advance spool, hold-first runner (P1-a), re-suppression tool | normal Core API review; **gate semantics change** |
| **C-8** *(new)* | Whole-host rollback check | `OwnerFreshnessUnlockV1`, owner-signed with a new owner-proof purpose/domain. It binds `{environment, boot_id, host nonce, witness V3 head digest, privacyAnchorVersion}`. Memory serving is refused after every boot or witness restart until a valid unlock for the **current** head arrives. The owner issues one only when `classify_presented_world` = CURRENT against Replicas A+B. | new owner-proof purpose → `owner_proof.py` or `contracts.py` **re-pin**; owner tooling |
| **C-9** *(new)* | Hold-first FORGET (P1-a) | The runner writes a spool INTENT. A root oneshot then sets the marker and stops the gateway (`Conflicts=`). The runner waits, bounded, for the marker, and only then calls `begin_forget`. If the intent is never authorized, it is released only by reconcile proof (no in-flight authorization and no journal). | F9-C executor package (unpinned); new units → observation baseline |

## 2. Owner decisions

| # | Decision | Options | **Recommendation** |
|---|---|---|---|
| **D-1** | Anchor holder | witness / new boundary | **Witness.** This is already approved as direction (req. 1: the witness only attests freshness, and Privacy stays the sole FORGET authority). |
| **D-2** | Signing key | (a) dedicated K-PAN; (b) K-WIT with a formally reviewed domain separation; (c) no anchor signature: the head lives only inside the K-WIT-signed V3 document | **(a).** (b) changes K-WIT's accepted purpose (F-1). (c) couples every FORGET to the authority ledger chain. (a) costs one extra keygen ceremony. |
| **D-3** | Before genesis | strict refuse / DEV_SYNTHETIC tolerance | **Strict everywhere.** No tolerance code path that could reach live (req. 3). |
| **D-4** | `ANCHOR_BEHIND` / witness unavailable | strict / grace window / degrade | **Strict refuse, no grace, no degrade.** The normal advance takes about a second, and the reconcile timer heals. |
| **D-5** | Whole-host rollback (req. 4) | (a) owner-replica binding only (does **not** protect, F-3); (b) C-3 + **C-8 boot unlock** + per-FORGET off-host record; (c) an external append-only log (for example a retention-locked bucket in a separate project) | **(b), mandatory before live First Memory.** (c) can come later to cut ceremony load, but it is a new boundary and needs its own design. |
| **D-6** | Privacy restore path | the re-suppression tool as the only sanctioned path | **Yes.** Root only, offline (Core API + gateway stopped). It needs an owner-approved recovery record (V1 HMAC for DEV_SYNTHETIC, V2 signed before live). It is **add-only**: it re-adds exactly the anchored entries the restore lost, then the restore-suppression verifier erases restored content. `DIVERGED` is never auto-resolved; it goes to owner investigation. **An anchor reset or re-genesis is not a recovery tool.** It would act as a suppression-deletion capability, so it is possible only through a K-ROOT-authorized witness epoch ceremony. |
| **D-7** | Sequencing | anchor release before or after the DEV operational upgrade | **After.** The DEV upgrade ships the executor, finalization and restore gate **without** the anchor probe. The anchor (C-1..C-9) then ships as its own authority-dev/witness release program, and the probe and genesis are enabled together. **This is a hard prerequisite for live First Memory.** |
| **D-8** *(req. 7)* | Third socket | (a) new `privacy.sock`, peer = Core API uid; (b) the existing root owner socket + a root helper + a signed published file; (c) the signer socket | **(b).** The Core API identity never reaches the witness, the witness exposure stays root + authority, and the root helper reuses the accepted executor pattern. Cost: a root process parses a SQLite file the Core API uid controls (read-only/immutable, the same exposure the executor accepted). (c) is rejected (wrong principal). |
| **P1-a** *(req. 8)* | Interval before executor activation | accept / hold-first | **Hold-first (C-9).** No new turn starts once the FORGET intent is recorded, and the gateway is stopped before the hold becomes ACTIVE. A turn already in flight is terminated (SIGTERM). Anything it wrote is removed by the later whole-store purge. |

## 3. FORGET advancement (req. 5): required sequence

1. Hold-first:
   - INTENT is written;
   - marker set and gateway stopped;
   - the runner confirms the marker.
2. `begin_forget` commits the hold and the suppression rows. The gate now sees `L ⊋ S` → `ANCHOR_BEHIND` → **all memory serving refused**.
3. The advance oneshot sends `local − anchored`. The witness:
   - refuses any duplicate, non-extension or version/time regression;
   - takes its flock;
   - writes atomically, pin-before-commit;
   - publishes the signed anchor.
4. The gate sees `L == S` and serving resumes, still subject to the ACTIVE hold.
5. Two owner-facing statuses:
   - **"FORGET accepted"** is reported only once anchor ≥ the post-FORGET version;
   - **"FORGET durable"** is reported only once an off-host owner freshness record covers it (D-5b).
6. Owners erase; the executor finalizes (accepted M7 behaviour).

**Properties:**
- **Crash-safe:** the advance is stateless and idempotent, and a crash leaves `ANCHOR_BEHIND` (refused) until reconcile heals it.
- **Monotonic:** the witness enforces extension only.
- **Never serves newly suppressed memory while the advance is pending:** this is step 2's refusal.

## 4. Exact release dependencies (in order; each step is a separate owner approval)

1. **This matrix is approved** (D-1..D-8, P1-a, C-8/C-9 added).
2. **Contract PR (pure and offline):**
   - C-1 new module;
   - C-2/C-3 edits to `recovery_contracts.py` and `witness_readiness.py`;
   - C-4 K-PAN profile in `pr1_bootstrap.py`;
   - C-8 unlock contract;
   - `SHARED_HASHES` re-pins, each listed with its old and new digest.
3. **Witness runtime PR:**
   - credential (second signer class);
   - protocol / core / writer / storage / server;
   - service unit (2nd credential);
   - tmpfiles + `paths.py` (publish file, advance spool);
   - `witness_release_file_set.py`;
   - **signer `witness_client.py` V3 acceptance** (authority-dev runtime).
4. **Core API + F9-C package PR (unpinned):** C-7 and C-9 (advance oneshot/path, hold oneshot/path, reconcile extension) and the re-suppression tool.
5. **K-PAN custody ceremony (DEV_SYNTHETIC test-only):** keygen, encrypted credential, public-key pin record.
6. **authority-dev release program:**
   - build;
   - attestation;
   - install ladder;
   - E-19-style release maintenance;
   - **DR-5 EQUAL before and after**;
   - host observation re-baseline (new units only).
7. **Owner freshness:** the record format binds V3 (anchor) and the unlock tooling exists. First Replica A+B record.
8. **Genesis ceremony (C-6)**, then the first boot unlock.
9. **DEV-only live matrix:**
   - W1–W7 from the design;
   - W8 boot unlock (missing, replayed, stale-head);
   - W9 hold-first (in-flight turn, intent never authorized);
   - W10 whole-host snapshot rollback → refused.
10. **Live First Memory additionally needs:** V2 signed Privacy authorization (A-4) and the dedicated Hermes service account (A-3). These are already owner-recorded conditions.

## 5. Operational implications

- **Memory availability now depends on:**
  - the witness being up;
  - the published anchor being current;
  - an **owner unlock after every boot or witness restart**;
  - each FORGET's advance (about a second; the reconcile timer otherwise).
- **Every FORGET** stops the gateway (hold-first) and is not "durable" until an owner freshness ceremony. FORGET is rare, but each one now involves the owner twice: the request and the freshness record.
- **The Privacy restore runbook** = stop → restore → re-suppression (owner-approved) → verifier → gate check. A cognitive-only restore is unchanged.
- **The witness state is now a Privacy-critical asset.** Its loss means memory serving is refused until a K-ROOT witness epoch ceremony and a new genesis.
- **New root units:** advance, hold and their path/timer units. No deployer, sudoers or polkit change.

## 6. Remaining risks (not closed by this design)

1. **Same-host root compromise** defeats the witness, the executor and the gate together. Out of scope for every same-host design.
2. **Between FORGET and the off-host record**, a whole-host rollback undoes the FORGET and the boot unlock cannot see it, because the owner's latest record also predates it. The mitigation is honesty: the status stays "not durable" until recorded. **Strict option:** also refuse memory serving until the record exists.
3. **The seconds-long window between `begin_forget` and the advance:** a host rollback in that window loses the FORGET. Mitigation: it is never reported "accepted", so the owner re-issues it.
4. **A root helper parses SQLite that the Core API uid controls** (same as the executor).
5. **The V3 lazy refresh** contends with the signer's ledger chain (optimistic retry). This needs W3/W6 testing.
6. **Anchored-set growth:** unbounded but small (opaque selectors). Advances are well below the 64 KiB frame limit.
7. **The DR-5-pinned durability probe facade** is ungated. It must stay a non-serving path and is left unchanged.
8. **The evidence so far is prototype-only** (16/16, simulated witness). There is no real-witness evidence until step 9.
9. **Hermes independence:** the anchor, witness, gate and C-8 are Hermes- and provider-free. Hold-first only stops the ingress unit; it uses no Hermes code (req. 10).

## 7. Requirement traceability

| Req | Met by |
|---|---|
| 1 | D-1. The anchor holds opaque selectors only, and the witness cannot remove suppression or authorize anything. |
| 2 | D-2a / C-4 |
| 3 | D-3, D-4, C-2 statuses (all refuse) |
| 4 | D-5b / C-3 + C-8 (+ the risk 2 statement) |
| 5 | §3 |
| 6 | D-6 |
| 7 | D-8b |
| 8 | P1-a / C-9 |
| 9 | §1 pin column + §4 |
| 10 | risk 9 |

**STOP. Waiting for the owner's review before any implementation.**
