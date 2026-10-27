# F9-C rollback anchor: design revision 1 (narrow)

**Status:** review only (2026-10-24).
- **Supersedes:** only the revised items of `F9C-ANCHOR-DECISION-REVIEW.md`. Everything the owner ACCEPTED stands unchanged.
- **Not changed:** no governed component, and no DEV/PROD contact, Groq call, commit or push.
- **Basis:** read-only source checks in the f9c1 worktree at b9eb32c.

## 0. New source facts behind this revision

| # | Fact | Effect |
|---|---|---|
| N-1 | `PrivacyBoundaryObservationV1` has exactly one consumer: the signer's `synthetic_recovery_ledger.py` (`PRIVACY_BOUNDARY_STALE`), which is authority **recovery** readiness. The memory-serving gate is in the Core API and does not use it. | **C-2 is unnecessary.** It is dropped. |
| N-2 | The authority signer's `witness_client.py` and root `clients.py` import `lilith_recovery_witness.protocol`. | Witness `protocol.py` must stay **byte-identical**, so the anchor protocol lives in a new witness module. |
| N-3 | `/run/lilith-recovery-witness` is `0710 root:lilith-authority-dev`, so the Core API uid cannot traverse it. | The gate reads a **root-published copy** owned by the F9-C package, not a witness path. No witness tmpfiles or `paths.py` change. |
| N-4 | `begin_forget` calls `actor_authority.resolve_and_consume(...)` **before** its `BEGIN IMMEDIATE` Privacy transaction. | A crash between the two consumes the evidence with no request row. This is pre-existing, and §4 handles it. |

## 1. Off-host durability (revision 1)

### Checkpoint

**New contract `PrivacyDurabilityCheckpointV1`** (Core API, so not signer-pinned):
- **Fields:** `{environment, checkpointSeq, previousCheckpointDigest, anchorVersion, anchorDigest, setHead, suppressionCount, checkpointedAt, checkpointKeyId, signature}`.
- **Domain:** `LILITH-PRIVACY-CHECKPOINT-V1\0`.
- **Signing key:** never present on the VM. Two interchangeable signers use one contract:
  - **K-PCK** (an owner-held checkpoint key): manual, and the permanent fallback;
  - **E** (an external freshness service): unattended, long-term (§2).
- **The checkpoint holder enforces extension only:** `anchorVersion` strictly increasing, `previousCheckpointDigest` chained. A submission at or below its latest version is refused **and recorded as a fork alarm**. This is how a rolled-back host that tries to continue gets detected.

### Ordering: durable before erase (replaces "durable later")

```
INTENT → hold-first (gateway stopped) → begin_forget (hold ACTIVE + suppression rows)
→ witness advance (K-PAN anchor v+1) → off-host checkpoint for v+1 → verify checkpoint
→ ONLY THEN: owners erase → executor → finalization → complete()
```

- **"FORGET accepted"** is reported to the owner **only after the checkpoint verifies**. There is one owner-visible state, and it is durable by construction.
- **Affected data stays blocked until the checkpoint verifies.** Until then:
  - the hold stays ACTIVE (held content is never served);
  - erasure has not started;
  - the gateway stays stopped.

  Unaffected memory may serve once the local set equals the anchored set (L == S), but the gateway is stopped anyway.

### Rollback detection: proof sketch

- **Notation:**
  - v_E = latest checkpointed anchor version (held off-host; it never rolls back with the host);
  - v_W = the host witness anchor version;
  - L = the local Privacy set;
  - S = the anchored set.
- **Invariant:** every accepted FORGET f has a checkpoint with version ≥ v_f.
- **A whole-host rollback to before f** gives v_W < v_f ≤ v_E. The boot freshness check (§2) obtains a **nonce-bound** statement of v_E and its digest, then requires v_E ≤ v_W and the host chain digest at v_E = the checkpoint digest. A rolled-back host fails with `OLDER_THAN_CHECKPOINT`. A forked host fails the digest check → `DIVERGED`.
- **Replay** of an old checkpoint statement is impossible, because the nonce is fresh per boot.
- **A Privacy-only restore** is caught locally by the witness (L ⊊ S), with no network.
- **A witness-only rollback** gives L ⊋ S → `ANCHOR_BEHIND`. Its next advance is refused by the checkpoint holder as a non-extension, and the boot check catches it too.

### The vulnerable period, stated exactly

| Phase | Where the newest state lives | A whole-host rollback here… | Why it is acceptable |
|---|---|---|---|
| P0 before `INTENT_RECORDED` | nowhere | the request never existed | the owner got no acknowledgement and re-issues |
| P1 intent → hold → `begin_forget` → witness advance | host only | the FORGET is lost | the owner was told only `INTENT_RECORDED`, never "accepted"; the owner client keeps the request pending (off-host, on the owner device) and alarms if no "accepted" arrives within T |
| P2 witness advanced, checkpoint pending | host only | the FORGET is lost | same as P1; nothing is erased yet, so nothing has been claimed |
| P3 checkpoint verified | off-host | **detected at boot** → serving refused | the proof above |

**The irreducible gap is P1–P2.** No design can protect a request that exists only on a host that is then rolled back. The guarantee is that such a request is **never reported accepted** and is **always still pending on the owner device**.

## 2. Boot recovery (revision 2: C-8 revised)

**One boot freshness check, two ways to pass.**
- **Where it runs:** a root oneshot at boot and on each witness or Core API restart.
- **What a pass writes:** `/run/lilith-privacy-fresh/verified` (tmpfs, so it is gone after every boot), bound to `boot_id` + `v_W`.
- **What requires the marker:**
  - the Core API memory gate;
  - the gateway drop-in, `ConditionPathExists=/run/lilith-privacy-fresh/verified`.

  The gateway needs it because a rolled-back Hermes conversation store is itself memory: the executor's restore epoch rolls back with the host.

**Path (a), unattended (long term):** the host sends a nonce. E returns the signed latest `(v_E, digest)` bound to that nonce, and the host verifies it against the pinned E key and its own anchor chain.
- **Pass:** the marker is written with no human involved.
- **Unreachable, refused or inconsistent:** no marker; fall back to path (b).
- **Requirement 2 holds:** recovery never relies on host-rollbackable state alone. The nonce-bound statement comes from outside the host, and the host chain must match it.

**Path (b), manual:** the owner reads the host's nonce and its `(v_W, digest)`, then compares them with the owner-held checkpoint chain and signs an unlock with K-PCK.
- **DEV:** acceptable as the only path.
- **Long term:** it remains the fallback whenever E is unavailable.

**E (designed later, not built now):**
- **Recommended shape:** a separate GCP project; a non-exportable asymmetric KMS key; a monotonic store (a transactional document, with a retention-locked append log for audit).
- **Host access:** the VM holds only a **submit/read** identity and never a signing key.
- **Rejected:**
  - a public transparency log (it publishes timing and metadata, and the repo is public);
  - the owner's home device (availability).
- **This is a new boundary, so it needs its own design and approval.** It is **not** needed for DEV or for a first live start if the owner accepts manual operation (D-11).

## 3. Minimum governed changes (revision 3)

### Is witness V3 / signer acceptance necessary? **No. Dropped.**

V3 existed only to fold the anchor into owner freshness through the K-WIT witness document. The checkpoint chain (§1) signs the anchor head **directly** and off-host. That is stronger, because it is verifiable by the host at boot, and it needs no change to `RecoveryWitnessV2`, `witness_readiness.py`, `owner_freshness.py` or the signer. C-2 is dropped (N-1).

### Smallest safe witness modification

| File | Change | Category |
|---|---|---|
| `owner-memory-control/lilith_owner_memory/privacy_anchor_contracts.py` | **NEW**: `PrivacyAnchorV1` (set commitment, chain, extension rule, verify); K-PAN key-id prefix + credential name | **SHARED_HASHES addition** (new entry; no existing entry re-pinned) |
| `recovery-witness/lilith_recovery_witness/privacy_anchor.py` | **NEW**: separate frame protocol id `LILITH_PRIVACY_ANCHOR_DEV`; ops `READ_PRIVACY_ANCHOR` / `ADVANCE_PRIVACY_ANCHOR`; own state file under the existing `/var/lib/lilith-recovery-witness`; own flock; atomic pin-before-commit | witness runtime (new) |
| `recovery-witness/lilith_recovery_witness/credential.py` | **+** `PrivacyAnchorSigningKeyV1`: loads only `privacy-anchor-signing-key` and signs only `PrivacyAnchorV1` bodies; the K-WIT class is unchanged | witness runtime |
| `recovery-witness/lilith_recovery_witness/server.py` | on the **owner socket only**, frames carrying the new protocol id go to `privacy_anchor`; the signer socket refuses them | witness runtime |
| `recovery-witness/deploy/lilith-recovery-witness.service` | **+1** `LoadCredentialEncrypted=privacy-anchor-signing-key:…` | witness deploy asset |
| `recovery-witness/witness_release_file_set.py`, `README.md` | +1 module, purpose text | witness release set |
| `authority-dev/release_file_set.py` | +1 `SHARED_HASHES` entry | authority release set |
| `authority-dev` installer / observer / keygen ceremony files | install, observe and generate the K-PAN blob | ceremony files |

**Byte-identical (each is a compatibility check):**
- witness `protocol.py`, `profile.py`, `core.py`, `writer.py`, `storage.py`;
- `lilith_authority_host/paths.py`;
- all `lilith_authority_dev/*` and `lilith_authority_root/*` runtime modules;
- **every existing `SHARED_HASHES` entry** (`recovery_contracts` f4a14cff, `witness_readiness` 129d4479, `pr1_bootstrap` 9a09a472, `owner_proof` 3a3eb714, …);
- the broker;
- K-WIT and its credential.

**Re-pins of existing entries:** **none.** What changes is the **authority-dev release candidate** (the new witness files and the release set). That means a new build attestation and an install ladder in the E-19 release-maintenance pattern.

### Custody changes
1. **K-PAN:** DEV_SYNTHETIC test-only key id; keygen ceremony; encrypted credential under the existing witness credential root; custody record; public-key pin for the Core API gate and for the checkpoint holder.
2. **K-PCK:** owner-held, never on the VM, Replica A/B custody; public-key pin on the host.
3. **E key:** later, with E (§2).
4. **K-WIT, K-ROOT, authority and broker keys:** unchanged.
5. **K-PAN rotation and compromise:** design deferred, **required before live** (risk R-8).

### Compatibility checks (gate for the release)
1. The existing `SHARED_HASHES` entries and every signer-imported module are byte-identical.
2. Recorded witness transcripts (`READ_WITNESS`, `RECORD_LEDGER_ADVANCE`, the owner ops) give byte-identical responses; the V2 witness digest and chain are unchanged across the upgrade restart.
3. The new protocol id is refused on the signer socket, and is refused by the old witness binary (a downgrade fails closed: no anchor → refuse).
4. Cross-domain: K-PAN cannot sign V2 bodies and K-WIT cannot sign anchors.
5. The forbidden-marker scan; OMC 2114 with the failure set identical to b9eb32c; the witness suites.
6. The witness restart preserves the broker and authority (M-B1 Condition 3 style).

### DR-5 implications
- **No deployer, sudoers or polkit change**, so the DR-5 boundary must compare **EQUAL** to baseline 3640ca01 before and after.
- **The host observation baseline changes** (one new credential blob and a witness unit hash). That is recorded as a separate, expected delta.
- **The F9-C package units** (hold, advance, freshness check, publish) are outside the authority observation set and go through the F9-C install record.

## 4. Hold-first safety (revision 4)

### Mechanism (it revises C-9)

1. The Core API writes the durable intent `I` to `/var/lib/lilith-forget/intent/<id>`, with fsync on the file and its directory. `I` carries `{requestId, actorEvidenceRefId, intentRefId, createdAt}` and no content. The owner gets `INTENT_RECORDED`.
2. A path unit → root hold oneshot:
   - creates the **persistent** marker `M`, fsynced, **before** it stops anything;
   - stops the gateway (`Conflicts=`) and verifies it is inactive;
   - writes the ack `A(I-digest)`.
3. The runner waits for `A`, then calls `begin_forget`, then continues with §1.

**Gateway drop-in:**
- `ConditionPathExistsGlob=!/var/lib/lilith-forget/intent/*`
- `ConditionPathExists=!M`
- plus the freshness marker (§2).

The hold unit has `Before=` the gateway and runs at boot.

**Core API memory gate:** refuses reads and admissions while any `I` exists. This is defense in depth if the gateway is still running before step 2 finishes.

**Removal rules (the change from the earlier review):**
- `I` **never auto-expires.** It is removed only:
  - (a) after its FORGET's checkpoint verifies and the request row exists; or
  - (b) by an **owner-authenticated cancel** (V1 HMAC for DEV, V2 signed before live), which root executes.
- `M` is released only when **all** of these hold:
  - no unreleased journal;
  - **no pending `I`**;
  - Privacy shows no in-flight authorization;
  - for each finished FORGET, completion is proven (the accepted M7 rule).
- Reconcile can never release `M` while an intent is pending.

### Crash matrix (proof obligations; each one becomes an offline test plus a mirror test)

| # | Crash point | State after reboot or restart | Resumption? | Intent lost? |
|---|---|---|---|---|
| H1 | before `I` is durable | nothing | — | the owner was never acknowledged → re-issues |
| H2 | `I` durable, `M` absent | the gateway's `!I` condition blocks start; the hold unit runs `Before=` the gateway | **no** | no (`I` is durable) |
| H3 | `M` durable, gateway still running (oneshot killed) | `Restart=` / the path unit re-runs the hold; the Core API gate refuses memory meanwhile | not a resumption (never stopped); no memory served | no |
| H4 | gateway stopped, `A` missing | `I` + `M` block; the hold re-verifies and writes `A` | **no** | no |
| H5 | `A` present, evidence not yet consumed | the runner `resume()` sees `I` + `A` + no request row → retries `begin_forget` | **no** | no |
| H6 | **evidence consumed, Privacy tx not committed (N-4)** | `I` stays (no auto-expiry), the gateway stays blocked, status `INTENT_STALLED_EVIDENCE_CONSUMED` | **no** | **no**, but the owner must supply fresh confirmation evidence for the same intent (or cancel) |
| H7 | `begin_forget` committed, before the advance | `ANCHOR_BEHIND` → everything refused; reconcile advances | **no** | no (in Privacy) |
| H8 | after the advance, before the checkpoint | gateway blocked; not reported accepted; the checkpoint is retried | **no** | no (host); P2 rule (§1) for whole-host rollback |
| H9 | Core API uid deletes `I` before `M` exists | that is the Core API cancelling its own unacknowledged request; `M` is root-only, and the Core API cannot remove it | — | treated as P0/P1 (§1) |

**Statement proved by H1–H9:** the gateway can start only when no intent and no marker exist and freshness is verified. An intent leaves only through a completed, durable FORGET or an owner-authenticated cancel. An acknowledged intent is therefore never silently lost on the host, and conversation never resumes without one of those two outcomes. The **only** non-mechanical case is H6, where the owner must re-confirm. The fix for N-4 is a small Core API change: record "evidence consumed for intent X" in the same store before consumption. It is optional and can come in a later slice.

## 5. Operational cost (revision 5)

| Unavailable | Memory reads and admissions | Conversation (gateway) | FORGET | Continues normally |
|---|---|---|---|---|
| **Witness** (steady state, published copy from this boot, L == S) | **serve** (the anchor is verified from the signed copy; no newer state can exist without an advance) | runs | new FORGET: intent + hold are recorded, then block at the advance → gateway stays stopped until the witness returns | health, monitoring, the signer, the broker, DR-5 observation, backups, logs |
| **Witness** at boot (no copy this boot) | **refused** | **blocked** (no freshness marker) | intents still recordable | same |
| **E / checkpoint** in steady state | serve | runs | blocks at the checkpoint step (gateway stopped, nothing erased) until E or a manual K-PCK checkpoint | same |
| **E** at boot | refused until manual unlock | blocked until manual unlock | intents recordable | same |
| **Owner** (with E available) | unaffected | unaffected | unaffected | everything |
| **Owner and E** at boot | refused | blocked | intents recordable | everything except memory and conversation |
| **Any check fails** (DIVERGED, OLDER, UNVERIFIABLE, REPLAYED) | refused | blocked | refused | health and alarms; owner investigation |

**What must block:** memory reads, memory admissions and capture, Hermes conversation (its store is memory), and FORGET progress beyond the failed step.

**What never blocks:**
- health and monitoring endpoints;
- authority, witness and broker services;
- DR-5 and observation;
- backups and logs;
- FORGET **intake** (an intent can always be recorded, and recording one only blocks more).

**Steady-state cost with E:** zero human steps. **Without E:** one owner step per boot and per FORGET.

## 6. Implementation sequence (revision 6)

**Track A: F9 DEV_SYNTHETIC operational integration. No governed change and no witness dependency.**
1. Core API:
   - intent spool;
   - hold-first runner;
   - the memory gate refuses while an intent exists;
   - the revised `M`-release rule;
   - owner cancel (V1 HMAC).
2. F9-C package: hold oneshot/path units, gateway conditions (`!I`, `!M`), and the accepted executor + finalization.
3. Offline H1–H9 matrix + real-systemd mirror; existing suites unchanged.
4. Owner approval → DEV_SYNTHETIC install + erasure drill (separate approval).

**The claim for Track A:** "erasure, restore-suppression and hold-first on synthetic data; **no rollback anchor; not live-eligible**".
- The anchor probe and the freshness marker are **not shipped** in Track A. There is no tolerance flag; the code is simply absent.
- This is safe because DEV_SYNTHETIC holds no personal data, so a rollback can expose only synthetic content.

**Track B: governed anchor release (after final approval).**
1. B1: the `privacy_anchor_contracts.py` contract, plus the Core API checkpoint contract and verifiers (local).
2. B2: witness modifications (§3) + compatibility checks 1–6 (local).
3. B3: K-PAN and K-PCK custody ceremony preparation.
4. B4: authority-dev release program (build, attestation, ladder, DR-5 EQUAL, observation delta).
5. B5: Core API anchor probe; advance and publish helper; boot freshness check (path b); manual K-PCK checkpoint and unlock tooling; the gateway freshness condition.
6. B6: genesis + genesis checkpoint; DEV governed rehearsal, including a **whole-host snapshot rollback → refused** and the H/W matrices.

**Track C: E unattended recovery.** Its own design and approval. It is **not** a prerequisite for B or for a manual-mode live start.

**Live First Memory requires:** A + B + V2 signed Privacy authorization (A-4) + the dedicated Hermes service account (A-3) + (C **or** owner-accepted manual mode).

## 7. Final revised decision matrix

| # | Item | Final recommendation | Status |
|---|---|---|---|
| C-1 | `PrivacyAnchorV1` | new pinned contract file (SHARED_HASHES **addition**) | keep |
| C-2 | Privacy boundary source in `recovery_contracts` | **drop**; the slot stays `NOT_MODELLED` for authority recovery readiness | **dropped** |
| C-3 | witness V3 + signer acceptance | **drop**; replaced by the off-host checkpoint chain | **dropped** |
| C-4 | K-PAN | dedicated key, witness-custodied, own credential | accepted |
| C-5 | transport | new witness module; separate protocol id on the owner socket; `protocol.py` byte-identical; gate reads a root-published signed copy | revised |
| C-6 | genesis | genesis + **genesis checkpoint** | revised |
| C-7 | Core API | probe, advance and publish, re-suppression, checkpoint verify | keep |
| C-8 | boot recovery | freshness check: E (unattended) or K-PCK manual unlock; tmpfs marker; the gateway is conditioned on it | revised |
| C-9 | hold-first | durable intent; never auto-expires; gateway `!I`/`!M`; `M` never released while an intent is pending | revised |
| C-10 | **NEW** `PrivacyDurabilityCheckpointV1` | durable-before-erase; K-PCK now, E later; extension-only holder | new |
| D-1 / D-2 / D-6 / D-8 / P1-a | witness, K-PAN, re-suppression, no third socket, hold-first | as accepted | accepted |
| D-3 | before genesis | strict refusal in Track B; Track A ships no probe (no tolerance flag) | revised |
| D-4 | witness down | serve **only** from a signed copy published this boot with L == S; otherwise refuse; no grace window | owner choice |
| D-5 | whole-host rollback | off-host checkpoint + boot freshness check (§1–§2) | revised |
| D-7 | sequencing | Track A independent; Track B governed; Track C separate | revised |
| **D-9** | checkpoint ordering | **durable-before-erase** (vs erase-then-checkpoint) | new |
| **D-10** | N-4 evidence-consumption gap | accept H6 (owner re-confirms) now; fix in the Core API later | new |
| **D-11** | live start without E | allowed in manual mode (one owner step per boot and per FORGET), or wait for E | new; owner choice |

## 8. Remaining risks

1. **R-1:** root or host compromise defeats the witness, the gate, the systemd conditions and the published copy together. This applies to every same-host design.
2. **R-2:** P1–P2 (§1). A whole-host rollback before the checkpoint loses an unaccepted FORGET. It relies on the owner device keeping it pending.
3. **R-3:** E compromise, or compromise of the owner's cloud account controlling E. E is independent of the VM, **not** of the owner account (Track C must address this).
4. **R-4:** H6 (N-4) needs an owner re-confirmation until it is fixed.
5. **R-5:** the D-4 witness-down serving relies on a root-owned tmpfs copy. That is the same trust level as the witness itself.
6. **R-6:** in manual mode, every boot stops memory and conversation until the owner acts.
7. **R-7:** the root advance and publish helpers parse SQLite controlled by the Core API uid (read-only/immutable, as the executor already does).
8. **R-8:** the K-PAN rotation and compromise procedure is not designed yet. It is required before live.
9. **R-9:** the DR-5-pinned durability-probe facade stays ungated and must never become a serving path.
10. **R-10:** all anchor evidence is still prototype-only (simulated witness) until B6.

**STOP. Waiting for final approval before any pinned witness or authority change. Track A can also wait for its own approval.**
