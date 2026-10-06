# Slice 15B2b-B1b-3e — M-B2 / GENERATE_K_WIT PR-2 Continuity: Owner Decision

Status:

- **`MB2_PR2_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_ATTEMPT`**
  (owner decision, 2026-10-06). It defines what "fresh PR-2 immediately
  before `GENERATE_K_WIT`" means for DEV_SYNTHETIC M-B2, and resolves the gaps
  M2-A … M2-F of the
  [M-B2 preflight](slice-15b2b-b1b3e-mb2-kwit-preflight.md) (§3).
- It extends the event- and sequence-bounded model of the
  [Condition 3 validity-window decision](slice-15b2b-b1b3e-condition3-validity-window-owner-decision.md)
  and the [M-B1 continuity decision](slice-15b2b-b1b3e-mb1-sequence-continuity-owner-decision.md)
  to the M-B2 PR-2 window. Both stay in force for their own windows.
- **Governance semantics only.** No runtime, sequencer, keygen, installer,
  workflow or infrastructure code changed.
- **It authorizes nothing.** M-B2 / `GENERATE_K_WIT` is NOT AUTHORIZED. The
  runbook (§5) and go template (§6) are documentation only. Owner freshness
  is `FRESHNESS=UNKNOWN`. No live system was contacted.

```text
continuity defined != M-B2 sequence authorized != fresh PR-2 PASS != M-B2 go != K-WIT generated
K_WIT_CUSTODIED != registry / signing authority
```

| Field | Value |
| --- | --- |
| Control `main` at the decision | `cd417be472bebfb65d70d096ebc4e3e7a20eb5ea` (merge of PR #150) |
| Environment | DEV_SYNTHETIC only |

## 1. Owner decision (verbatim)

> I adopt `MB2_PR2_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_ATTEMPT`.
>
> For DEV_SYNTHETIC M-B2 / `GENERATE_K_WIT`, a fresh PR-2 result is usable only
> inside one explicitly owner-authorized, owner-attended M-B2 sequence. There is
> no wall-clock TTL; validity is event-bounded and sequence-bounded.
>
> “Fresh PR-2 immediately before `GENERATE_K_WIT`” means that fresh DR-5 and all
> other accepted M-B2 prerequisites are first established, then the required
> fresh PR-2 is collected as the final topology/rollback-currentness revalidation
> before the owner M-B2 go and the single K-WIT keygen invocation. Between that
> PR-2 PASS and keygen, only the required read-only final gate checks and the owner
> go may occur; no unrelated work or relevant mutation may intervene.
>
> After fresh DR-5 is established, merges to `main`, workflow reruns capable of
> deployment, manual deployments, or other actions capable of changing relevant
> DEV deployment state are frozen until M-B2 completes or the sequence aborts.
>
> The sequence ends and the fresh PR-2 becomes non-reusable if any of the
> following occurs or becomes uncertain: a new/unreviewed deployment; any PR-2-
> scope topology, snapshot, image, backup, disk, replication, sync or owner-
> freshness-topology change; reboot; broker replacement; IAM or relevant host-
> topology change; K-ACT CURRENT change; installed release/keygen change; witness
> credential already present; owner register no longer `KNOWN_EMPTY`; applicable
> B-5 stop/invalidator; explicit owner pause/suspension/end; or any uncertainty
> about the required current evidence.
>
> The separate M-B2 go is one-attempt and authorizes exactly one invocation of
> `lilith-authority-keygen-dev witness` on `lilith-dev-01`. Any `REFUSED`,
> `FAILED`, unexpected prompt, or other STOP condition consumes that go and ends
> the sequence, even if no private K-WIT candidate was created. A new attempt
> requires a new sequence, fresh current evidence including fresh PR-2, and a new
> explicit owner go.
>
> The M-B2 go must bind at minimum:
>
> - DEV_SYNTHETIC scope;
> - current accepted control commit;
> - the successful fresh PR-2 window;
> - E-21 K-ROOT fingerprint
>   `publicKeySha256=cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf`;
> - host `lilith-dev-01`;
> - fixed K-WIT keyId `test-only.witness.dev-synthetic.b1b3d.1`;
> - command `lilith-authority-keygen-dev witness`;
> - credential path
>   `/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred`;
> - exactly one invocation.
>
> The K-ROOT passphrase must not be requested or entered during M-B2. Any
> passphrase prompt is a STOP.
>
> The public K-WIT fingerprint/publication must be recorded immediately off-host
> in the owner-controlled external M-B2 evidence set on the laptop. It may later
> be copied into the repository completion/acceptance record as public evidence.
> No private K-WIT material may enter that evidence set.
>
> Burn handling is sequence-ending:
>
> - If a failed/discarded real K-WIT candidate has a known public fingerprint,
>   record that fingerprint as a burned real K-WIT identity in the external
>   evidence and later update/review the canonical burned-identity record before
>   any replacement attempt.
> - If a candidate existed but its public identity was never captured, record an
>   append-only `UNKNOWN_REAL_KWIT_BURN` tombstone containing the known public/
>   non-secret provenance available for that candidate (control commit, host,
>   keyId, timestamp, failure window, and blob hash if safely available) and
>   destroy/custody it according to the accepted crash procedure. Do not pretend
>   an unknown fingerprint is known.
> - No replacement K-WIT may be generated under the same go or sequence.
>   Replacement requires a new owner-authorized sequence.
>
> Successful M-B2 ends at `K_WIT_CUSTODIED` / accepted public fingerprint capture
> and post-step verification. That state confers no signing or registry authority
> by itself.
>
> This decision does not authorize M-B2 now. It does not authorize M-B3,
> registry/genesis, record 1, First Memory, PROD activity, or any later bootstrap
> stage. `FRESHNESS=UNKNOWN` remains unchanged.

## 2. Semantics recorded

**Validity.** A fresh PR-2 result is usable only inside **one explicitly
owner-authorized, owner-attended M-B2 sequence**. There is **no wall-clock
TTL**. Validity is **event-bounded and sequence-bounded**. A PR-2 result from
any other window, including the M-B1 Condition 3 window, is not usable.

**Ordering ("immediately before").**

1. Fresh DR-5 and every other accepted M-B2 prerequisite are established
   **first**.
2. The fresh PR-2 is then collected as the **final topology /
   rollback-currentness revalidation**.
3. Between that PR-2 PASS and the keygen invocation, **only** the required
   read-only final gate checks and the owner go may occur. No unrelated work
   or relevant mutation may intervene.

**Deployment freeze.** From the moment fresh DR-5 is established until M-B2
completes or the sequence aborts, the following are frozen: merges to `main`,
workflow reruns capable of deployment, manual deployments, and any other
action capable of changing relevant DEV deployment state.

**Sequence terminators.** If any of the following occurs **or becomes
uncertain**, the sequence ends and its fresh PR-2 becomes non-reusable:

| # | Terminator |
| --- | --- |
| T-1 | a new or unreviewed deployment |
| T-2 | any PR-2-scope topology, snapshot, image, backup, disk, replication, sync or owner-freshness-topology change |
| T-3 | a reboot |
| T-4 | broker replacement |
| T-5 | an IAM or relevant host-topology change |
| T-6 | a K-ACT CURRENT change |
| T-7 | an installed release or keygen change |
| T-8 | the witness credential already present |
| T-9 | the owner register no longer `KNOWN_EMPTY` |
| T-10 | an applicable B-5 stop or invalidator |
| T-11 | an explicit owner pause, suspension or end |
| T-12 | any uncertainty about the required current evidence |

**The go.**

- Separate from the sequence authorization; given only after the fresh PR-2
  PASS and the final gate checks.
- **One-attempt.** It authorizes **exactly one invocation** of
  `lilith-authority-keygen-dev witness` on `lilith-dev-01`.
- **Any `REFUSED`, `FAILED`, unexpected prompt, or other STOP consumes the go
  and ends the sequence, even if no private K-WIT candidate was created.**
- A new attempt requires a new sequence, fresh current evidence including a
  fresh PR-2, and a new explicit owner go.
- It binds at minimum the nine items in §6.

**K-ROOT passphrase.** It must not be requested or entered during M-B2. Any
passphrase prompt is a STOP. (M-B2 performs no K-ROOT operation; preflight
§2 item 4.)

**Off-host fingerprint record.** The public K-WIT fingerprint and publication
are recorded **immediately** off-host, in the **owner-controlled external
M-B2 evidence set on the laptop**. They may later be copied into the
repository completion / acceptance record as public evidence. **No private
K-WIT material may enter that evidence set.**

**Burn handling (sequence-ending).** See §7.

**Terminal state.** Successful M-B2 ends at **`K_WIT_CUSTODIED`**, after
accepted public fingerprint capture and post-step verification. It confers
no signing or registry authority by itself (§8).

## 3. Gap reconciliation

| Gap ([preflight](slice-15b2b-b1b3e-mb2-kwit-preflight.md) §4) | Resolution | State |
| --- | --- | --- |
| M2-A fresh PR-2 expiry / invalidation | sequence- and event-bounded, no TTL; PR-2 collected last, before the go; terminators T-1 … T-12 (§2) | **RESOLVED** |
| M2-B deployment freeze | frozen from fresh DR-5 until M-B2 completes or aborts, including workflow reruns capable of deployment (§2) | **RESOLVED** |
| M2-C one-attempt / refusal semantics | exactly one invocation per go; any `REFUSED` / `FAILED` / unexpected prompt / STOP consumes the go and ends the sequence; new attempt = new sequence + fresh PR-2 + new go (§2) | **RESOLVED** |
| M2-D off-host fingerprint location | the owner-controlled external M-B2 evidence set on the laptop; public only; may later be copied into the repository record (§2) | **RESOLVED** |
| M2-E known burned real K-WIT | recorded as a burned real K-WIT identity in the external evidence; the canonical burned-identity record is updated and reviewed before any replacement attempt (§7) | **RESOLVED** |
| M2-F unknown real K-WIT burn | append-only `UNKNOWN_REAL_KWIT_BURN` tombstone with known non-secret provenance; never an invented fingerprint; destroy / custody per C-3 (§7) | **RESOLVED** |
| reviewed M-B2 procedure (B-5 decision packet §4) | documented in §5 with the go template in §6; it becomes the reviewed procedure when the owner reviews and merges this record | **DOCUMENTED** |

## 4. Consistency with existing contracts

Checked against the repository. No code change is required to represent
this decision.

| Point | Existing contract | Result |
| --- | --- | --- |
| stricter refusal rule | a keygen `REFUSED` exits before key generation and writes nothing, so it passes no point of no return; the decision still ends the sequence and consumes the go | stricter governance; no conflict |
| replacement timing | C-3: regenerate before M-B4 only | the decision adds "new owner-authorized sequence"; both apply |
| one-time keygen | `witness_preflight` refuses a non-empty `credentials/` (`WITNESS_CREDENTIAL_ALREADY_PRESENT`) | a burned blob must be destroyed before any replacement sequence can pass its preflight |
| blob destruction | C-3 is `MANUAL_RECOVERY_REQUIRED` | the M-B2 go authorizes one keygen invocation only. Destroying a burned blob is a separate live mutation and needs its own owner authorization; until then the blob stays in custody in place (`root:root 0600`, untouched) |
| fixed keyId | `WITNESS_KEY_ID` is a constant | a replacement K-WIT reuses the keyId with a new key; identity is the public key fingerprint, never the keyId |
| canonical burned set | `burned_identities.py` (`CANONICAL_COUNT == 20`); B-5 packet §9 voids on an unreviewed change | an update is needed only after a real burn, as a separately reviewed change before any replacement attempt; nothing changes now |
| K-ACT distinctness input | live-install preflight §24 "publication relation"; the owner-retained K-ACT L2b.2 publication is on the host (PR-1A read-only preflight D-7) | read read-only in the §24 re-proof; supplies the K-ACT `publicKeySha256` |
| registry-related distinctness | `pr1_bootstrap.witness_distinctness_reason` needs registry v1 and the witness anchor | not evaluable at M-B2; it is re-checked at M-B3 / M-B4 |
| executor | keygen docstring: run by the owner, as root, inside a separately authorized ceremony step | the invocation happens only under the owner go, in the owner-attended sequence |

## 5. Future M-B2 runbook (documentation only; NOT executed, NOT authorized)

Any terminator T-1 … T-12 at any step ends the sequence (§2). Every check is
read-only except the single keygen invocation at step 9.

| # | Step | Required result | Basis |
| --- | --- | --- | --- |
| 0 | the owner explicitly authorizes **one M-B2 sequence** (not the go) | explicit owner statement | this decision |
| 1 | repository prerequisites: clean control checkout; HEAD = `origin/main` = the control commit; this record merged | equal | M-B1 runbook precedent |
| 2 | **fresh DR-5 through the latest deployment**: every DEV deployment since `37422198636` (`11c08cf`) compared with the accepted run on the full result set (`f1869234…`), DR-5 block (`a1d98773…`) and pre-deploy block (`f5087042…`); `PR1_AUTHORITY_BOUNDARY maturity=P1A-9`; `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`; `GRANT_ABSENT`; nothing queued | equal; **deployment freeze ACTIVE** from here | completion record §6; this decision |
| 3 | B-5 grant usable; no B-5 stop or G-1 … G-9 invalidator known, suspected or uncertain | none | B-5 grant §7 |
| 4 | fresh read-only **Replica A** read (0 records; manifest, entries and inodes equal to the accepted baseline) and an **owner-run, screen-only Replica B block** on the S25 (canonical path, not nested; manifest `c068e533…`; 0 records; inodes `973613 / 973617 / 973618`; no SSH / `sshd` / ADB). The block reads no K-ROOT and prompts for no passphrase | both unchanged and empty | packet refresh §2.3 procedure |
| 5 | **owner register = `KNOWN_EMPTY`** (`owner_register_state`: two replicas, distinct, same environment and profile, zero records) | `KNOWN_EMPTY` | `pr1b_sequencing._gate` |
| 6 | **re-prove K-ACT CURRENT and host / install preservation** (root, read-only, on `lilith-dev-01`): same boot as the accepted baseline (or a reviewed re-baseline); §24 CURRENT (path, `root:root 0600`, identity, times, SHA-256 `6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3`, credstore exactly one entry, publication relation using the owner-retained K-ACT publication); installer `status --expect P1A-9 aee323e94412accbe321bc84eae78c5b8cf95afc` PASS; keygen CLI SHA-256 `1fa50327bb9cb402dc38f6e8a3742362901ba4dbd5c48f8474dc7c6c4e134472`; `/etc/lilith-recovery-witness` lists only `credentials`, `credentials/` empty, both `root:root 0700`; units inactive and not enabled; activation `GRANT_ABSENT`; broker preservation PASS | all equal | live-install preflight §24–§26, §28 |
| 7 | **fresh PR-2** as the final topology / rollback-currentness revalidation: the P3-5 §13 scope, compared with the last accepted window (the M-B1 Condition 3 window, cloud set 23 artifacts) | `PR2` PASS: no change; the window start and end are recorded | P3-5 §13; this decision |
| 8 | **required read-only final gate checks only**: `origin/main` unchanged and no new deployment run started or queued; `credentials/` still empty; no terminator observed | unchanged | this decision |
| 9 | the owner gives the **separate one-attempt M-B2 go** (§6 template), naming the step 7 window | explicit owner statement | this decision |
| 10 | **exactly one invocation**, as root on `lilith-dev-01`: `lilith-authority-keygen-dev witness`. stdout is captured directly into the external M-B2 evidence set on the laptop; stderr and the exit code are captured | exit 0, empty stderr, no prompt. Anything else: STOP, go consumed (§7) | keygen `main`; this decision |
| 11 | **capture the public publication / fingerprint**: `publicationType = LILITH_WITNESS_KEY_PUBLICATION`; profile `DEV_SYNTHETIC`; `witnessKeyId = test-only.witness.dev-synthetic.b1b3d.1`; environment `dev`; `Ed25519`; `credentialName = recovery-witness-signing-key`; `credentialPath` = the fixed path; `withKey = host`; `machineId = ae929170e6fa4c8ab9cc7b9547238d9d` | all equal | `pr1_bootstrap.witness_publication` |
| 12 | **verify the blob against the publication**: root `sha256sum` of the blob (read as ciphertext, never decrypted) = `blobSha256`; size = `blobByteSize`; `root:root 0600`; the only entry in `credentials/` | equal | M-B2 POST (live-install preflight §27) |
| 13 | **verify distinct from K-ACT and E-21 K-ROOT**: K-WIT `publicKeySha256` ≠ `cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf`; ≠ the K-ACT `publicKeySha256`; K-WIT `blobSha256` ≠ `6a61c350…` | all distinct | `kWitDistinctFromKActAndKRoot`; preflight §11 |
| 14 | **verify not a burned identity**: not in the canonical 20 (`burned_identities.BURNED_PUBLIC_KEY_SHA256`) and not in any recorded real K-WIT burn | not burned | B-5 decision packet §7 item 4 |
| 15 | **secret scan / no private-output leakage**: stdout, stderr, the transcript and the whole evidence set hold no private-key marker (PKCS#8, `PRIVATE KEY`, raw or base64 private bytes) | 0 hits | `secretScansClean`; M-B2 STOP "any private pattern" |
| 16 | **immediately record the public fingerprint off-host** in the owner-controlled external M-B2 evidence set on the laptop (public only) | recorded | `kWitFingerprintRecordedOffHost`; this decision |
| 17 | **post-step checks**: installer `status --expect P1B-2 aee323e94412accbe321bc84eae78c5b8cf95afc` PASS; §24 CURRENT unchanged; same boot; units inactive, not enabled; activation `GRANT_ABSENT`; broker preservation PASS (custody paths are reported, not judged). The observer `stableSha256` changes because the blob now exists; its new value is recorded, not compared with the old one | all PASS | installer `P1B-2` contract; preflight §24 |
| 18 | **`K_WIT_CUSTODIED`**: crash window C-4 `KNOWN_CUSTODY_DEBT` (the blob and the host key share the PR-2 snapshot domain) recorded | recorded | P3-5 §3, §9 |
| 19 | **the sequence completes**; the deployment freeze ends | — | this decision |

**OR** at any point: abort, and burn handling under §7. The sequence ends;
the freeze ends with the abort.

## 6. M-B2 owner-go template (TEMPLATE ONLY; not given)

Placeholders are in angle brackets. Every other value is fixed.

> I authorize M-B2 / `GENERATE_K_WIT` now for exactly one attempt within this
> current DEV_SYNTHETIC M-B2 sequence.
>
> Scope: DEV_SYNTHETIC only.
>
> Control commit: `<CONTROL_SHA>` (current accepted `main`).
>
> Fresh PR-2 window: `<PR2_WINDOW_START>`–`<PR2_WINDOW_END>`, result PASS.
>
> E-21 K-ROOT fingerprint:
> `publicKeySha256=cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf`.
>
> This authorization permits exactly one invocation, as root on host
> `lilith-dev-01`, of the command `lilith-authority-keygen-dev witness`, which
> creates the K-WIT with the fixed keyId
> `test-only.witness.dev-synthetic.b1b3d.1` at the credential path
> `/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred`.
>
> The K-ROOT passphrase must not be requested or entered. Any passphrase prompt
> is a STOP.
>
> Any `REFUSED`, `FAILED`, unexpected prompt, or other STOP consumes this go
> and ends the sequence, even if no private K-WIT candidate was created. There
> is no retry in this sequence. A new attempt needs a new sequence, a fresh
> PR-2 and a new go.
>
> The public K-WIT fingerprint and publication are recorded immediately in my
> external M-B2 evidence set on the laptop. No private K-WIT material may enter
> it.
>
> This authorization does not authorize M-B3 / `SIGN_REGISTRY_V1`,
> registry/genesis mutation, record 1, First Memory, PROD activity, or any
> later bootstrap stage. `FRESHNESS=UNKNOWN` remains unchanged.

## 7. Abort and burn handling

Every abort ends the sequence. No replacement K-WIT may be generated under
the same go or sequence; replacement requires a new owner-authorized
sequence (and, by C-3, must happen before M-B4).

| Case | What is known | Handling |
| --- | --- | --- |
| refusal or STOP before any candidate exists (for example a keygen `REFUSED`, which exits before key generation) | no private material | the go is consumed; the sequence ends; nothing is burned; the stop is recorded in the external evidence |
| a candidate exists **and** its public fingerprint is known (publication captured), then it is failed or discarded | `publicKeySha256` | record it as a **burned real K-WIT identity** in the external evidence; **update and review the canonical burned-identity record before any replacement attempt** |
| a candidate existed, but its public identity was **never captured** (C-3). Every keygen `FAILED` occurs after key generation and prints nothing, whether or not a blob was written (for example `ENCRYPT_FAILED` before the write, or `CURRENT_CHANGED` after it) | provenance only | record an append-only **`UNKNOWN_REAL_KWIT_BURN`** tombstone (below); **never invent or infer a fingerprint**; destroy / custody the blob under the accepted crash procedure (C-3, `MANUAL_RECOVERY_REQUIRED`) |

**`UNKNOWN_REAL_KWIT_BURN` tombstone fields** (known, public or non-secret
provenance only):

- control commit;
- host (`lilith-dev-01`);
- keyId (`test-only.witness.dev-synthetic.b1b3d.1`);
- timestamp;
- failure window (for example C-3);
- blob SHA-256, **only if a blob exists and can be read safely** as
  ciphertext by root (otherwise recorded as absent or not read);
- fingerprint: `UNKNOWN`. It is never filled in afterwards.

**Custody of a burned blob.** It stays in place, untouched, until a
separately owner-authorized recovery step destroys it. The M-B2 go does not
authorize its destruction. Destruction is permitted only before M-B4. Because
the keygen refuses a non-empty `credentials/`, it must be completed before any
replacement sequence. A `FAILED CURRENT_CHANGED` additionally means a K-ACT
CURRENT change (T-6), which is its own STOP.

## 8. Terminal state

```text
K_WIT_CUSTODIED
K_WIT_CUSTODIED != registry / signing authority
```

`K_WIT_CUSTODIED` means: the K-WIT blob exists in RR-36 custody, its public
publication and fingerprint are captured and recorded off-host, and the
post-step checks passed. It is P3-5 lifecycle stages GENERATED, CUSTODIED and
IDENTITY_PUBLISHED, and nothing more:

- K-WIT signs only `RecoveryWitnessV2`, and nothing has been signed;
- K-WIT is not in any registry, and no witness anchor is installed;
- no witness is started and no genesis exists;
- K-WIT validity is not freshness.

## 9. State

```text
MB2_PR2_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_ATTEMPT
FRESH PR-2 USABLE ONLY INSIDE ONE OWNER-AUTHORIZED, OWNER-ATTENDED M-B2 SEQUENCE
NO WALL-CLOCK TTL; VALIDITY EVENT-BOUNDED AND SEQUENCE-BOUNDED
FRESH DR-5 AND ALL OTHER PREREQUISITES FIRST; FRESH PR-2 LAST, BEFORE THE GO
BETWEEN PR-2 PASS AND KEYGEN: ONLY READ-ONLY FINAL GATE CHECKS AND THE OWNER GO
DEPLOYMENT FREEZE FROM FRESH DR-5 UNTIL M-B2 COMPLETES OR THE SEQUENCE ABORTS
TERMINATORS T-1 … T-12 END THE SEQUENCE; FRESH PR-2 THEN NON-REUSABLE
M-B2 GO ONE-ATTEMPT: EXACTLY ONE INVOCATION OF lilith-authority-keygen-dev witness ON lilith-dev-01
REFUSED / FAILED / UNEXPECTED PROMPT / STOP CONSUMES THE GO AND ENDS THE SEQUENCE
NEW ATTEMPT = NEW SEQUENCE + FRESH PR-2 + NEW OWNER GO
K-ROOT PASSPHRASE NOT REQUESTED OR ENTERED; ANY PASSPHRASE PROMPT IS A STOP
E-21 publicKeySha256=cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf
KEYID test-only.witness.dev-synthetic.b1b3d.1
CREDENTIAL PATH /etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred
PUBLIC K-WIT FINGERPRINT RECORDED IMMEDIATELY OFF-HOST IN THE OWNER EXTERNAL M-B2 EVIDENCE SET ON THE LAPTOP; PUBLIC ONLY
KNOWN BURNED REAL K-WIT: RECORDED; CANONICAL BURNED SET UPDATED AND REVIEWED BEFORE ANY REPLACEMENT
UNKNOWN_REAL_KWIT_BURN: APPEND-ONLY TOMBSTONE; NO INVENTED FINGERPRINT
NO REPLACEMENT K-WIT UNDER THE SAME GO OR SEQUENCE
SUCCESSFUL TERMINAL STATE: K_WIT_CUSTODIED
K_WIT_CUSTODIED CONFERS NO SIGNING OR REGISTRY AUTHORITY
M2-A … M2-F RESOLVED
RUNBOOK DOCUMENTED; NOT AUTHORIZED; NOT EXECUTED
M-B2 GO TEMPLATE ONLY; NOT GIVEN
M-B2 / GENERATE_K_WIT = NOT AUTHORIZED
M-B3 / SIGN_REGISTRY_V1 = NOT AUTHORIZED
REGISTRY / GENESIS = NOT AUTHORIZED
RECORD 1 = NOT AUTHORIZED
FIRST MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
NO RUNTIME, SEQUENCER, KEYGEN, INSTALLER, WORKFLOW OR INFRASTRUCTURE CHANGE
NO LIVE SYSTEM CONTACTED
```
