# Slice 15B2b-B1b-3e — M-B2 / `GENERATE_K_WIT`: Completion and Owner Acceptance (2026-10-06)

Status:

- **`M-B2 = COMPLETED / ACCEPTED`. `GENERATE_K_WIT = COMPLETED / ACCEPTED`.**
  The real DEV_SYNTHETIC K-WIT was generated on `lilith-dev-01` by exactly
  one invocation of `lilith-authority-keygen-dev witness`. That invocation
  ran inside one owner-authorized, owner-attended M-B2 sequence under
  [`MB2_PR2_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_ATTEMPT`](slice-15b2b-b1b3e-mb2-pr2-continuity-owner-decision.md).
  The owner accepted it (§8).
- **K-WIT owner public record:**
  `publicKeySha256=5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf`,
  `witnessKeyId=test-only.witness.dev-synthetic.b1b3d.1`, credential blob
  `blobSha256=f87593701ee5e9272363a473a115b87cc06179df3c0b233af4aa62bb5b9b97be`.
- **`K_WIT_CUSTODIED = ESTABLISHED`. `KNOWN_CUSTODY_DEBT = RECORDED`** (crash
  window C-4).
- **This closes M-B2 / `GENERATE_K_WIT` only.** `K_WIT_CUSTODIED` confers
  no signing or registry authority. M-B3 / `SIGN_REGISTRY_V1`, registry /
  genesis mutation, record 1, First Memory, PROD and every later bootstrap
  step remain **NOT AUTHORIZED**. Owner freshness is `FRESHNESS=UNKNOWN`.
- Operational record. The raw evidence and the public publication are
  owner-held outside the repository, in the owner-controlled external M-B2
  evidence set on the laptop. No private K-WIT or K-ROOT material was read,
  decrypted or copied. No repository file changed during the live sequence.

```text
M-B2 sequence authorized != fresh DR-5 != deployment freeze != owner register KNOWN_EMPTY
  != K-ACT / host preservation != fresh PR-2 != final read-only gates != one-attempt M-B2 go
  != one GENERATE_K_WIT invocation != technical success != K_WIT_CUSTODIED != owner acceptance
K_WIT_CUSTODIED != signing authority
K_WIT_CUSTODIED != registry authority
M-B2 completion != M-B3 authorization
```

## 1. Identities

| Item | Value |
| --- | --- |
| control `main` | `4d16d762f00e43783b9b388b526a969fbffa6772` (merge of PR #151, the M-B2 continuity decision; unchanged through the sequence) |
| sequence | started `2026-10-06T08:45:54Z`; completed `2026-10-06T09:11:38Z` (UTC) |
| host | `lilith-dev-01` (machine ID `ae929170e6fa4c8ab9cc7b9547238d9d`) |
| installed release / keygen | `aee323e94412accbe321bc84eae78c5b8cf95afc`; keygen CLI SHA-256 `1fa50327bb9cb402dc38f6e8a3742362901ba4dbd5c48f8474dc7c6c4e134472` |
| E-21 K-ROOT (preceding record) | `publicKeySha256=cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf` ([M-B1 completion](slice-15b2b-b1b3e-mb1-kroot-completion.md)) |
| K-ACT CURRENT | blob SHA-256 `6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3`; public `publicKeySha256=dd13a1fb302375a4e7ec81131a72920e23e365e06a0b6dc9bb7ab124dadc01ed` (from the owner-retained K-ACT L2b.2 publication on the host, public material only) |
| K-WIT publication (public) | SHA-256 `9e9dd0787b3d6df8d40730c6abab728cacbe5136269ca4421160da830bb23472` (682 bytes, canonical JSON) |
| owner acceptance (external, verbatim) | SHA-256 `1d143881346b50ce4fc50411315a82db64032d7355733c17b7ddc07dcd230593` |
| external evidence set | owner-held (151 files), `SHA256SUMS` SHA-256 `df64675c5ced4e1d45f378c95c9dedd2f41f8c25660288cc1ef9692fc274ca84`; secret scan 0 hits; location not published |

## 2. Sequence authorization (owner, before the sequence)

The owner authorized **one** DEV_SYNTHETIC owner-attended M-B2 preparation
sequence under `MB2_PR2_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_ATTEMPT`,
on control `4d16d76`.

- **Authorized:** fresh DR-5 through the latest applicable DEV deployment
  (including `37435321602`); the deployment freeze once DR-5 was
  established; fresh Replica A and owner-run Replica B reads to establish
  `KNOWN_EMPTY`; fresh K-ACT CURRENT and host / install preservation checks;
  fresh B-5 stop / invalidator checks; fresh PR-2 as the final topology /
  rollback-currentness revalidation; the required read-only final gates
  immediately after PR-2.
- **Not authorized by it:** `GENERATE_K_WIT`; any invocation of
  `lilith-authority-keygen-dev witness`; M-B3; registry / genesis; record 1;
  First Memory; PROD; any later step. If every gate passed, the sequence was
  to **stop and wait for the owner**.

The sequence authorization was not the M-B2 go (§4).

## 3. Prerequisites, PR-2 and final gates (inside the sequence)

| Step | Result |
| --- | --- |
| repository / control | `origin/main = 4d16d76…`; clean control checkout at that commit |
| fresh DR-5 | **CURRENT**: deploys `37430819328` (`cd417be`) and `37435321602` (`4d16d76`), every applicable deploy since `37422198636`, each equal to the accepted run on the full result set (`f1869234…`), DR-5 block (`a1d98773…`) and pre-deploy block (`f5087042…`); `PR1_AUTHORITY_BOUNDARY maturity=P1A-9`; `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`; `GRANT_ABSENT`; no `ALLOWED`; nothing queued or in progress |
| deployment freeze | **ACTIVE** from `08:50:34Z` |
| B-5 | grant usable, not void; no §9 stop; no G-1 … G-9 (the control diff since `11c08cf` is documentation and tests only) |
| Replica A | fresh read `08:51:06Z`: 0 records; manifest `fbdd045c…`, entries and inodes `59905 / 59906 / 59907` equal to the accepted baseline |
| Replica B | owner-run, screen-only block `72f99d4e…` on the S25 at `08:54:28Z`, local Termux session (no SSH / `sshd` / ADB / automation): canonical path, not nested; manifest `c068e533…`; 0 records; inodes `973613 / 973617 / 973618`; settings OFF; owner custody attestation. `KROOT_FILES=PRESENT` is expected after M-B1 (the block matches names only and reads no K-ROOT) |
| owner register | **`KNOWN_EMPTY`** (`08:57:05Z`) |
| K-ACT / host preservation | **PASS** (`08:57:45Z`–`08:59:26Z`, read-only, root): same boot `eea461c3…` as the accepted baseline; K-ACT CURRENT unchanged (path, `root:root 0600`, 219 bytes, inode, times, SHA-256 `6a61c350…`); the credstore holds exactly that one entry; `/etc/lilith-recovery-witness` lists only `credentials`, which is empty, both `root:root 0700`; keygen `1fa50327…`; `status --expect P1A-9 aee323e…` PASS; units inactive and not enabled; activation `GRANT_ABSENT`; broker preservation PASS (`c4b9cb38…` / `a30bd7d6…`); observer `c54f21ba…` identical |
| **fresh PR-2** | **PASS**, window **`2026-10-06T08:59:59Z`–`2026-10-06T09:04:46Z`**: P3-5 §13 scope; cloud set 23/23 byte-identical to the last accepted window (the M-B1 Condition 3 window); compute audit unchanged; Admin Activity since `06:50:39Z` holds only `iam.serviceAccounts.actAs` entries (owner IAP sessions and the deployer during the two reviewed deploys); Replica A re-read unchanged |
| final read-only gates | **PASS** (`09:05:23Z`–`09:05:55Z`): `origin/main` unchanged; no new deployment run started or queued; `credentials/` still empty; K-ACT, boot, broker, P1A-9 and activation unchanged; no terminator T-1 … T-12 |

Transient anomalies, both non-material and resolved inside the sequence:

- a local `gcloud` client segfault on the needrestart configuration read. Its
  output was complete and byte-identical to the baseline;
- `MemoryAvailable` and systemd timer timestamps differed from the baseline.

The sequence stopped after the final gates and waited for the owner.

## 4. Owner M-B2 go (one attempt)

Given at `09:07:44Z`, after the fresh PR-2 PASS and the final gates, within
the same sequence:

> I authorize M-B2 / GENERATE_K_WIT now for exactly one attempt within this current DEV_SYNTHETIC M-B2 sequence.
> Scope: DEV_SYNTHETIC only.
> Control commit: 4d16d762f00e43783b9b388b526a969fbffa6772.
> Fresh PR-2 window: 2026-10-06T08:59:59Z–2026-10-06T09:04:46Z, result PASS.
> E-21 K-ROOT fingerprint: publicKeySha256=cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf.
> This authorization permits exactly one invocation, as root on host lilith-dev-01, of:
> lilith-authority-keygen-dev witness
> creating the K-WIT with fixed keyId:
> test-only.witness.dev-synthetic.b1b3d.1
> at:
> /etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred
> The K-ROOT passphrase must not be requested or entered. Any passphrase prompt is a STOP.
> Any REFUSED, FAILED, unexpected prompt, or other STOP consumes this go and ends the sequence, even if no private K-WIT candidate was created. There is no retry within this sequence. A new attempt requires a new sequence, fresh current evidence including fresh PR-2, and a new explicit owner go.
> The public K-WIT fingerprint and publication must be recorded immediately in my owner-controlled external M-B2 evidence set on the laptop. No private K-WIT material may enter that evidence set.
> This authorization does not authorize M-B3 / SIGN_REGISTRY_V1, registry/genesis mutation, record 1, First Memory, PROD activity, or any later bootstrap step.
> FRESHNESS=UNKNOWN remains unchanged.

It binds all nine items of the
[go template](slice-15b2b-b1b3e-mb2-pr2-continuity-owner-decision.md) §6.
Immediately before the invocation, `origin/main` was still `4d16d76` and no
workflow run was active.

## 5. Execution (exactly one invocation)

| Fact | Value |
| --- | --- |
| invocations | **exactly one**, `09:08:57Z`–`09:09:04Z`; no retry |
| command | `lilith-authority-keygen-dev witness` (`/usr/local/sbin`, the installed release CLI) |
| host / user | `lilith-dev-01`, as root (`sudo -n`, non-interactive) |
| stdin | `/dev/null` |
| exit code | **0** |
| stderr | **0 bytes** (no `REFUSED`, no `FAILED`) |
| prompts | **none**; the K-ROOT passphrase was not requested or entered; no K-ROOT operation |
| stdout | captured directly into the external M-B2 evidence set on the laptop: one canonical public publication |

```text
KG_RC=0
KG_STDERR_BYTES=0
MB2_KWIT_FINGERPRINT publicKeySha256=5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf
witnessKeyId=test-only.witness.dev-synthetic.b1b3d.1
blobSha256=f87593701ee5e9272363a473a115b87cc06179df3c0b233af4aa62bb5b9b97be
```

## 6. Post-step verification (runbook steps 11–17)

| # | Check | Result |
| --- | --- | --- |
| 11 | publication fields | `publicationType = LILITH_WITNESS_KEY_PUBLICATION`; `profile = DEV_SYNTHETIC`; `schemaVersion = 1`; `witnessKeyId = test-only.witness.dev-synthetic.b1b3d.1`; environment `dev`; `Ed25519`; `credentialName = recovery-witness-signing-key`; `credentialPath` = the fixed path; `withKey = host`; `machineId = ae929170…`. The fingerprint is the SHA-256 of the 32-byte public key |
| 12 | blob against publication | root `sha256sum` of the blob, read as ciphertext and never decrypted, = `blobSha256` `f8759370…`; size 219 = `blobByteSize`; regular file, `root:root 0600`; the only entry in `credentials/`; both witness directories still `root:root 0700` |
| 13 | distinctness | K-WIT `publicKeySha256` ≠ E-21 K-ROOT `cb36daf1…92cf`; ≠ K-ACT `dd13a1fb…01ed`; K-WIT `blobSha256` ≠ K-ACT blob `6a61c350…` |
| 14 | burned identities | **not** among the canonical 20 (`CANONICAL_COUNT == 20`, checked against `burned_identities.py` at `4d16d76`); no recorded real K-WIT burn exists |
| 15 | secret scan | **0 hits** for private-key markers across stdout, stderr and the whole evidence set |
| 16 | off-host record | public fingerprint recorded in the external M-B2 evidence set at `09:10:25Z`; public only |
| 17 | post-step host checks (`09:10:26Z`–`09:10:57Z`) | installer `status --expect P1B-2 aee323e…` **PASS**, no failures; K-ACT CURRENT unchanged (`6a61c350…`, same inode and times, credstore one entry); same boot `eea461c3…`; keygen unchanged; units inactive, not enabled; activation `GRANT_ABSENT`; broker preservation **PASS** (`c4b9cb38…`). The observer `stableSha256` changed to `94cb28f01571904e277a142e518326dd3930b8ca2f90f364aff6ee24b704c70c` **as expected, because K-WIT now exists**; the new value is recorded, not compared with `c54f21ba…` |

## 7. Custody state, crash window and sequence completion

- **`K_WIT_CUSTODIED = ESTABLISHED`.** The blob exists in RR-36 custody, its
  public publication and fingerprint are captured and recorded off-host, and
  the post-step checks passed. This is P3-5 lifecycle stages GENERATED,
  CUSTODIED and IDENTITY_PUBLISHED, and nothing more
  ([continuity decision](slice-15b2b-b1b3e-mb2-pr2-continuity-owner-decision.md) §8):
  - K-WIT signs only `RecoveryWitnessV2`, and nothing has been signed;
  - K-WIT is not in any registry, and no witness anchor is installed;
  - no witness is started and no genesis exists;
  - K-WIT validity is not freshness.
- **`KNOWN_CUSTODY_DEBT = RECORDED`** for crash window C-4: the K-WIT blob
  and the host credential key share the PR-2 snapshot domain
  ([P3-5](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md) §3, §9).
- No burn occurred: there was no `REFUSED`, `FAILED`, prompt or STOP, so no
  burned real K-WIT identity and no `UNKNOWN_REAL_KWIT_BURN` tombstone exist.
  The canonical burned set is unchanged.
- **The sequence completed at `09:11:38Z`**, after the post-step checks.
  Under the continuity decision the deployment freeze lasts "until M-B2
  completes or the sequence aborts", so **it ended at `09:11:38Z`**. Any
  later deployment needs its own fresh DR-5 comparison before a later step
  relies on it.

Sequence lifecycle (UTC, 2026-10-06):

| Event | Time |
| --- | --- |
| preparation sequence start | `08:45:54Z` |
| fresh DR-5 CURRENT; deployment freeze ACTIVE | `08:50:34Z` |
| owner register `KNOWN_EMPTY` | `08:57:05Z` |
| fresh PR-2 window | `08:59:59Z`–`09:04:46Z` |
| final read-only gates | `09:05:23Z`–`09:05:55Z` |
| one-attempt M-B2 go | `09:07:44Z` |
| the one K-WIT invocation | `09:08:57Z`–`09:09:04Z` |
| off-host fingerprint record | `09:10:25Z` |
| post-step verification | `09:10:26Z`–`09:10:57Z` |
| sequence completion; deployment freeze end | `09:11:38Z` |
| owner acceptance recorded externally | `09:15:16Z` |

## 8. Owner acceptance (verbatim)

> I accept M-B2 / GENERATE_K_WIT as successfully completed for the current DEV_SYNTHETIC bootstrap.
> I accept the generated real K-WIT public fingerprint as the owner public record:
> publicKeySha256=5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf
> with witness keyId:
> test-only.witness.dev-synthetic.b1b3d.1
> and credential blob SHA-256:
> f87593701ee5e9272363a473a115b87cc06179df3c0b233af4aa62bb5b9b97be.
> I accept the M-B2 execution evidence as satisfying the reviewed M-B2 completion criteria: exactly one authorized invocation of lilith-authority-keygen-dev witness, exit code 0, no stderr, no prompt or K-ROOT passphrase use, successful public publication capture, credential blob verification, distinction from K-ROOT and K-ACT, exclusion from the canonical burned identities, public-only off-host recording, successful P1B-2 post-step verification, and K-ACT / host preservation.
> I accept the resulting state as K_WIT_CUSTODIED and the crash-window classification as KNOWN_CUSTODY_DEBT.
> This acceptance closes M-B2 / GENERATE_K_WIT for the current DEV_SYNTHETIC bootstrap.
> K_WIT_CUSTODIED does not confer registry or signing authority by itself.
> This acceptance does not authorize M-B3 / SIGN_REGISTRY_V1, registry/genesis mutation, record 1, First Memory, PROD activity, or any later bootstrap step.
> FRESHNESS=UNKNOWN remains unchanged.

## 9. What remains

- **M-B3 / `SIGN_REGISTRY_V1`** (P3-5 step 3, `K_WIT_CUSTODIED →
  REGISTRY_SIGNED`) is the next stage. It is the first K-ROOT use and needs
  its own reviewed procedure and a separate, explicit owner authorization.
  **M-B2 completion does not authorize it.**
- The registry-related distinctness check
  (`pr1_bootstrap.witness_distinctness_reason`) was not evaluable at M-B2;
  it is re-checked at M-B3 / M-B4.
- C-4 `KNOWN_CUSTODY_DEBT` stays recorded until a later accepted record
  changes it.
- This sequence's fresh PR-2 and other evidence were bounded to this
  sequence and are **not reusable** for any later step.

## 10. State

```text
M-B2 = COMPLETED / ACCEPTED
GENERATE_K_WIT = COMPLETED / ACCEPTED
K_WIT_CUSTODIED = ESTABLISHED
KNOWN_CUSTODY_DEBT = RECORDED
OWNER ACCEPTANCE RECORDED (VERBATIM)
K-WIT publicKeySha256=5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf
K-WIT witnessKeyId=test-only.witness.dev-synthetic.b1b3d.1
K-WIT blobSha256=f87593701ee5e9272363a473a115b87cc06179df3c0b233af4aa62bb5b9b97be
SEQUENCE AUTHORIZATION: ONE OWNER-ATTENDED M-B2 PREPARATION SEQUENCE; NOT THE GO
FRESH DR-5 CURRENT THROUGH 37435321602
DEPLOYMENT FREEZE ACTIVE FROM FRESH DR-5
OWNER REGISTER KNOWN_EMPTY (FRESH REPLICA A + OWNER-RUN REPLICA B)
K-ACT / HOST PRESERVATION PASS BEFORE PR-2
FRESH PR-2 PASS 2026-10-06T08:59:59Z-2026-10-06T09:04:46Z (FINAL TOPOLOGY / ROLLBACK REVALIDATION)
FINAL READ-ONLY GATES PASS
OWNER M-B2 GO: ONE ATTEMPT, AFTER PR-2 PASS AND FINAL GATES, NAMING THE PR-2 WINDOW
EXACTLY ONE INVOCATION OF lilith-authority-keygen-dev witness ON lilith-dev-01 AS ROOT
STDIN /dev/null; EXIT 0; STDERR 0 BYTES
NO PROMPT; NO K-ROOT PASSPHRASE REQUESTED OR ENTERED
PUBLICATION CAPTURED OFF-HOST
BLOB HASH / SIZE / PATH / MODE VERIFIED
K-WIT DISTINCT FROM E-21 K-ROOT
K-WIT DISTINCT FROM K-ACT
K-WIT BLOB DISTINCT FROM K-ACT BLOB
NOT IN THE CANONICAL 20 BURNED IDENTITIES
SECRET SCAN 0 HITS
PUBLIC FINGERPRINT RECORDED OFF-HOST; PUBLIC ONLY
POST-STEP status --expect P1B-2 PASS
K-ACT CURRENT UNCHANGED
SAME BOOT
BROKER PRESERVATION PASS
ACTIVATION GRANT_ABSENT
OBSERVER stableSha256 CHANGED AS EXPECTED (K-WIT EXISTS); NEW VALUE RECORDED
NO BURN; CANONICAL BURNED SET UNCHANGED
DEPLOYMENT FREEZE ENDED AT SEQUENCE COMPLETION (2026-10-06T09:11:38Z)
K_WIT_CUSTODIED != SIGNING AUTHORITY
K_WIT_CUSTODIED != REGISTRY AUTHORITY
M-B2 COMPLETION != M-B3 AUTHORIZATION
M-B3 / SIGN_REGISTRY_V1 = NOT AUTHORIZED
REGISTRY / GENESIS = NOT AUTHORIZED
RECORD 1 = NOT AUTHORIZED
FIRST MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
NO RUNTIME, SEQUENCER, KEYGEN, INSTALLER, WORKFLOW OR INFRASTRUCTURE CHANGE
```
