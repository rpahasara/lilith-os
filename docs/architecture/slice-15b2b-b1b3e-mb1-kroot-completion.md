# Slice 15B2b-B1b-3e — M-B1 / `GENERATE_K_ROOT`: Completion and Owner Acceptance (2026-10-06)

Status:

- **`M-B1 = COMPLETED / ACCEPTED`. `GENERATE_K_ROOT = COMPLETED / ACCEPTED`.**
  The real DEV_SYNTHETIC K-ROOT was generated on the S25, in one
  owner-attended continuous sequence under
  [`MB1_SEQUENCE_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_HANDOFF`](slice-15b2b-b1b3e-mb1-sequence-continuity-owner-decision.md).
  The owner accepted it (§7).
- **E-21 owner record:**
  `publicKeySha256=cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf`.
- **This closes M-B1 / `GENERATE_K_ROOT` only.** `GENERATE_K_WIT` (M-B2),
  registry / genesis mutation, record 1, First Memory and every later
  bootstrap step remain **NOT AUTHORIZED**. A fresh PR-2 immediately before
  `GENERATE_K_WIT` remains mandatory. Owner freshness is `FRESHNESS=UNKNOWN`.
- Operational record. Raw evidence and the public export are operator-held
  outside the repository. No private K-ROOT material left the S25. No
  repository file changed during the live sequence.

```text
eligibility success != owner M-B1 go != one-attempt M-B1 execution != technical completion != owner acceptance
M-B1 accepted != K-WIT authorized != registry / genesis != record 1 != First Memory != freshness CURRENT
```

## 1. Identities

| Item | Value |
| --- | --- |
| control `main` | `11c08cf6cc44650a1af97f1b5da2894be8475f6c` (merge of PR #149; unchanged through the sequence) |
| sequence | started `2026-10-06T06:29:39Z`; completed `2026-10-06T07:21:35Z` (UTC) |
| pinned phone operator script | `09cbc9bee7b58af7bab45bb903c6e10cb51ae6c62b20705be12de274bbe5216b` |
| pinned M-B1 bundle | `7f07e158aa5a0b3c31ee63e25ae25116c92f26a402bc6924422d7c95e2edc2c1` |
| phone-side export | SHA-256 `740cf10ab9042b95eef192af6ca9e63b661cf91af3a36fe5d0aafbd2b3547db5` (recomputed equal on the laptop) |
| phone transcript (public) | SHA-256 `03b9a4fb77533369d8187ad308755f2413cbaec95721f1fd7951e0936a9da31a` |
| eligibility output | SHA-256 `7a35a4b11c0be5c42a3153e244f14ebeb71301c9471d60210b31798eaa7b664d` |
| raw evidence bundle | operator-held (147 files), `SHA256SUMS` SHA-256 `dd42deb77096b9eaf72f8a84663e65ad85ce3ec2206d3ffd6d33e468c611ba78`; secret scan 0 hits; location not published |

## 2. Prerequisites and eligibility (inside the sequence)

| Step | Result |
| --- | --- |
| repository / control | `origin/main = 11c08cf…`; clean detached control checkout |
| Condition 1 | **PASS**: staged tar and script equal the pins; inner `SHA256SUMS` `4816f8c9…` verifies 73/73; 74 files; source commit `1e2eae3` an ancestor; the 17 bundled sources equal `origin/main`; closure and builder unchanged; the pins-record script block equals the staged script; `test_b1b3e_mb1_finalization.py` 8/8 |
| DR-5 | **CURRENT**: deploys `37415889584` (`e614573`), `37417296089` (`4c38ddc`) and `37422198636` (`11c08cf`) each equal the accepted run on the full result set (`f1869234…`), DR-5 block (`a1d98773…`) and pre-deploy block (`f5087042…`); `P1A-9`, `L1c.3`, `GRANT_ABSENT`, no `ALLOWED`. `37365210560` skipped; nothing queued |
| deployment freeze | **ACTIVE** from `06:31:08Z` |
| B-5 grant | usable; no §9 stop; no G-1 … G-9 |
| owner phone / Replica B / custody block | **PASS** at `06:35:31Z` (accepted block `72f99d4e…`): no SSH / `sshd`, local TTY, private storage, no `k-root*`, Replica B `c068e533…` with 0 records and inodes `973613 / 973617 / 973618`, not nested; settings OFF; owner custody attestation |
| unattended upgrade | ran `06:48:32Z`–`06:48:37Z`, **installed nothing**; Condition 3 opened only after it |
| final Condition 3 | **PASS**, `06:50:38Z`–`06:57:14Z`: cloud 23/23 byte-identical; same boot `eea461c3…`; broker preservation PASS (`c4b9cb38…` / `a30bd7d6…`); observer `c54f21ba…`; P1A-9 PASS; `GRANT_ABSENT`; no mapped package pending; needrestart and Replica A identical |
| evaluator import preflight | PASS in WSL `Ubuntu-24.04`, closure verified against `11c08cf`; 0 calls |
| `CHECK_ELIGIBILITY` | **called exactly once** at `06:57:37Z`: `PR1B_ELIGIBLE`, `reasons = []`, all 12 inputs `True` |

Transient anomalies, both resolved inside the window:

- a local `gcloud` client segfault on one systemd read. The single read
  was rerun once, cleanly; it differed from the baseline only in
  `MemoryAvailable`;
- a new `/etc` directory mtime in the storage probe, caused by the routine
  `google-oslogin-cache` timer run. Non-material; no cron entry changed.

## 3. Owner M-B1 go (one attempt)

Given at `07:01:06Z`, after `PR1B_ELIGIBLE`, within the same sequence:

> I authorize M-B1 now for exactly one attempt within this current DEV_SYNTHETIC continuous sequence.
> This authorization permits real GENERATE_K_ROOT execution on the S25 in Termux private storage using only the reviewed and pinned M-B1 materials:
> script SHA-256
> 09cbc9bee7b58af7bab45bb903c6e10cb51ae6c62b20705be12de274bbe5216b
> bundle SHA-256
> 7f07e158aa5a0b3c31ee63e25ae25116c92f26a402bc6924422d7c95e2edc2c1
> from merged main control commit
> 11c08cf6cc44650a1af97f1b5da2894be8475f6c.
> The passphrase must be entered only on the S25 and must not be exposed to the laptop or any remote session.
> The accepted laptop-to-S25 handoff may now proceed: verify both pins on the laptop, MTP-copy only the accepted tar and mb1_phone_commands.sh to the phone's Download folder, disconnect the phone, enable airplane mode, and continue locally in Termux.
> G0, G1 and T1 must pass. At C0, my manual entry of GENERATE is the explicit act that permits K-ROOT generation for this one invocation.
> I will record the resulting K-ROOT fingerprint on the phone and confirm that it does not match any of the 20 burned identities.
> If any G0/G1/T1 or other STOP: occurs before C0, this go is void, the sequence ends, and it must not be retried or reused. If a STOP occurs after K1, failed-candidate custody rules apply and there is still no retry under this go.
> This authorization does not authorize GENERATE_K_WIT, registry/genesis mutation, First Memory, or any later bootstrap step. Fresh PR-2 immediately before GENERATE_K_WIT remains mandatory.

Both pins were verified on the laptop immediately afterwards. The freeze
was still intact (`origin/main = 11c08cf`, no new run).

## 4. Execution (one attempt, S25 Termux)

The owner made the MTP transfer of only the tar and the script, unplugged,
enabled airplane mode, and ran the pinned script in a local Termux session.
The passphrase was typed only on the phone.

- G0, G1 and T1 passed: no SSH / `sshd`; local terminal; Python 3.14.6 and
  `cryptography` 50.0.1 (`aarch64`); no prior staging, K-ROOT, public,
  export or failed candidate; Replica B baseline OK; bundle, `SHA256SUMS`,
  source commit, 74 files and private-storage checks OK.
- C0: `OWNER_CONFIRMED_ON_PHONE`.
- K1 / K2: `root-keygen` `exit=0`; key file regular, `0600`, the only entry
  in a `0700` directory; stderr empty; `ANCHOR_VALID`;
  `NOT_A_BURNED_IDENTITY`; `KEY_ENCRYPTED_AT_REST`;
  `KEY_UNLOCKS_AND_MATCHES_ANCHOR`.
- V: `TMP_CLEAN`, `NO_OTHER_KEY_FILE`, `NO_KEY_IN_SHARED_STORAGE`,
  `EVIDENCE_HOLDS_NO_KEY`, `BUNDLE_UNCHANGED`, `REPLICA_B_UNCHANGED`.
- P / S / X: `PUBLIC_COPY_WRITTEN`; evidence sealed; `EXPORT_PUBLIC_ONLY`;
  `TRANSPORT_COPY_REMOVED`.

```text
RUN_EXIT=0
STOP LINES = 0
MB1_KROOT_GENERATED (last token before RUN_EXIT)
MB1_KROOT_FINGERPRINT publicKeySha256=cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf
```

## 5. Laptop review of the public export

| Check | Result |
| --- | --- |
| export SHA-256 | `740cf10a…7db5`, equal to the phone-side `PHONE_SIDE_EXPORT_SHA256` |
| contents | **exactly the 14-file public allowlist** ([ceremony package](slice-15b2b-b1b3e-mb1-kroot-ceremony-package.md) §8); no key directory, `k-root.der`, quarantine or tar |
| `evidence.sha256` | verifies every evidence file |
| anchor | byte-identical to the `root-keygen` output; `Ed25519`, environment `dev` |
| fingerprint | SHA-256 of the anchor's 32-byte public key = `cb36daf1…92cf`, equal to the public fingerprint file and `root-keygen.json` |
| burned identities | **not** among the canonical 20 (`CANONICAL_COUNT == 20`, checked against `burned_identities.py` at `11c08cf`) |
| key material | no private-key markers anywhere in the export |
| Replica B | `replica-b-before.txt` == `replica-b-after.txt` |

**Custody.** The private K-ROOT stays only in S25 Termux private storage,
encrypted at rest. The laptop holds only the public export and the
transcript. `~/lilith-kroot-dev-synthetic/` was never copied (owner
statement; the export allowlist excludes it).

## 6. Sequence completion and the deployment freeze

The sequence completed at `07:21:35Z`, when the export review finished
successfully. Under the continuity decision, the deployment freeze lasts
"until M-B1 completes or the sequence aborts", so **it ended at
`07:21:35Z`**. Any later deployment needs its own fresh DR-5 comparison
before it is relied on by a later step.

## 7. Owner acceptance (verbatim)

> I accept M-B1 as successfully completed for the current DEV_SYNTHETIC bootstrap.
>
> I accept the generated real K-ROOT public fingerprint as the E-21 owner record:
> publicKeySha256=cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf
>
> I accept the M-B1 execution evidence as satisfying the accepted M-B1 completion
> criteria: RUN_EXIT=0, no STOP: lines, MB1_KROOT_GENERATED, public export
> verification, burned-identity exclusion, Replica B preservation, and private
> K-ROOT custody remaining on the S25.
>
> This acceptance closes M-B1 / GENERATE_K_ROOT for this DEV_SYNTHETIC bootstrap.
>
> It does not authorize GENERATE_K_WIT / M-B2, registry/genesis mutation,
> record 1, First Memory, or any later bootstrap step.
>
> A fresh PR-2 immediately before GENERATE_K_WIT remains mandatory, and K-WIT
> still requires a separate explicit owner authorization.
>
> FRESHNESS=UNKNOWN remains unchanged.

## 8. What remains

- **M-B2 `GENERATE_K_WIT`** requires a **fresh PR-2 revalidation
  immediately before it**
  ([P3-5](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md) §13; the
  replacement OR-8 acknowledgement) **and** a separate, explicit owner
  authorization. **M-B1 completion cannot substitute for that PR-2**, and
  this sequence's Condition 3 does not satisfy it.
- M-B1 completion **does not imply authorization** for M-B2 or any later
  stage.
- The sequencer's crash window after M-B1 is "C-2 K-ROOT generated /
  fingerprint not recorded". The fingerprint **is** recorded (E-21, on the
  phone and here), so C-2 does not apply.

## 9. State

```text
M-B1 = COMPLETED / ACCEPTED
GENERATE_K_ROOT = COMPLETED / ACCEPTED
OWNER ACCEPTANCE RECORDED (VERBATIM)
E-21 publicKeySha256=cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf
ELIGIBILITY PREREQUISITE: CHECK_ELIGIBILITY CALLED EXACTLY ONCE IN THIS SEQUENCE -> PR1B_ELIGIBLE
OWNER M-B1 GO: ONE ATTEMPT, AFTER PR1B_ELIGIBLE, NAMING BOTH PINS
RUN_EXIT=0
STOP LINES = 0
MB1_KROOT_GENERATED
PUBLIC EXPORT VERIFIED (EXACT 14-FILE ALLOWLIST)
NOT IN THE CANONICAL 20 BURNED IDENTITIES
REPLICA B PRESERVED
TRANSPORT COPY REMOVED
PRIVATE K-ROOT REMAINED S25-ONLY
DEPLOYMENT FREEZE ENDED AT SEQUENCE COMPLETION (2026-10-06T07:21:35Z)
GENERATE_K_WIT / M-B2 = NOT AUTHORIZED
FRESH PR-2 IMMEDIATELY BEFORE GENERATE_K_WIT REMAINS MANDATORY; M-B1 COMPLETION CANNOT SUBSTITUTE FOR IT
M-B1 COMPLETION DOES NOT AUTHORIZE M-B2 OR LATER STAGES
REGISTRY / GENESIS = NOT AUTHORIZED
RECORD 1 = NOT AUTHORIZED
FIRST MEMORY = NOT AUTHORIZED
FRESHNESS=UNKNOWN
NO RUNTIME, SEQUENCER, SCRIPT, BUNDLE OR WORKFLOW CHANGE
```
